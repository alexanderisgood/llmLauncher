"""Complete private benchmark, ANE and runtime-comparison record persistence.

Owns stable incremental reads, bounded atomic writes, retention/deduplication
and append serialization. Persisted bytes may be reused only while current file
identity matches; callers receive detached records and recheck live eligibility.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import fcntl
import json
import math
import os
from pathlib import Path
import re
import stat
import threading
import time
from typing import Any, Callable

import chat_store_io


class MeasurementStoreError(chat_store_io.StoreReadError):
    pass


@dataclass(frozen=True)
class MeasurementPolicy:
    kind: str
    version: int
    maximum_records: int
    maximum_history_per_route: int = 1
    ssd_backends: frozenset[str] = frozenset()
    maximum_bytes: int = 128 * 1024 * 1024
    maximum_record_bytes: int = 16 * 1024 * 1024
    maximum_nodes: int = 2_000_000
    maximum_depth: int = 64
    append_lock_timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        if self.kind not in {"benchmark", "ane", "promotion"}:
            raise ValueError("Unknown measurement store")
        for key in ("version", "maximum_records", "maximum_history_per_route", "maximum_bytes",
                    "maximum_record_bytes", "maximum_nodes", "maximum_depth"):
            if type(getattr(self, key)) is not int or getattr(self, key) < 1:
                raise ValueError("Measurement bounds must be positive integers")
        if self.maximum_record_bytes > self.maximum_bytes:
            raise ValueError("A measurement record cannot exceed the complete store")
        if (type(self.append_lock_timeout_seconds) not in (int, float)
                or not math.isfinite(self.append_lock_timeout_seconds) or self.append_lock_timeout_seconds <= 0):
            raise ValueError("The measurement append timeout must be finite and positive")
        object.__setattr__(self, "ssd_backends", frozenset(self.ssd_backends))


_REQUIRED = {
    "benchmark": frozenset({"id", "createdAt", "scope", "backend", "modelFingerprint",
        "runtimeVersion", "hardwareFingerprint", "winner", "comparedModes"}),
    "ane": frozenset({"id", "createdAt", "scope", "modelFingerprint", "runtimeVersion",
        "hardwareFingerprint", "sequenceLength", "recommendation", "status"}),
    "promotion": frozenset({"id", "createdAt", "contractId", "planId", "modelFingerprint",
        "hardwareFingerprint", "selected", "candidate", "executionOrder", "qualityMatched",
        "resourceComparable", "canPromote", "measurements"}),
}
_NAMES = {"benchmark": "Benchmark", "ane": "ANE tuning", "promotion": "Runtime promotion"}


def _identity(path: Path) -> tuple[int, ...] | None:
    try:
        details = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise MeasurementStoreError("Saved measurements could not be inspected; the existing file was kept.") from error
    if (not stat.S_ISREG(details.st_mode) or details.st_uid != os.geteuid()
            or details.st_mode & 0o022):
        raise MeasurementStoreError("Saved measurements are not in an owner-controlled regular file; the existing file was kept.")
    return (details.st_dev, details.st_ino, details.st_size, details.st_mtime_ns,
            details.st_ctime_ns, details.st_mode, details.st_uid)


class MeasurementStore:
    def __init__(self, policy: MeasurementPolicy, path: Callable[[], Path], *,
                 route_identity: Callable[[dict[str, Any]], tuple[Any, ...]] | None = None,
                 lock: Any = None) -> None:
        if policy.kind == "benchmark" and route_identity is None:
            raise ValueError("Benchmark retention requires its exact route identity")
        self.policy = policy
        self.path = path
        self.route_identity = route_identity
        self.lock = lock if lock is not None else threading.RLock()
        self._cache_key: tuple[str, tuple[int, ...] | None] | None = None
        self._cache_document: dict[str, Any] | None = None

    def _bounds(self, record: dict[str, Any]) -> None:
        stack: list[tuple[Any, int]] = [(record, 0)]
        nodes = 0
        while stack:
            value, depth = stack.pop()
            nodes += 1
            if nodes > self.policy.maximum_nodes or depth > self.policy.maximum_depth:
                raise MeasurementStoreError("A saved measurement exceeds its structured-data limit; the existing file was kept.")
            if isinstance(value, dict):
                if any(not isinstance(key, str) for key in value):
                    raise MeasurementStoreError("A saved measurement has invalid field names; the existing file was kept.")
                stack.extend((item, depth + 1) for item in value.values())
            elif isinstance(value, (list, tuple)):
                stack.extend((item, depth + 1) for item in value)
            elif isinstance(value, float) and not math.isfinite(value):
                raise MeasurementStoreError("A saved measurement contains a non-finite value; the existing file was kept.")

    def _document(self, path: Path) -> tuple[dict[str, Any], tuple[int, ...] | None]:
        identity = _identity(path)
        key = (str(path.absolute()), identity)
        if self._cache_key == key and self._cache_document is not None:
            return self._cache_document, identity
        try:
            value = chat_store_io.read_document(path, collection_key="records",
                maximum_bytes=self.policy.maximum_bytes,
                maximum_record_bytes=self.policy.maximum_record_bytes,
                maximum_records=self.policy.maximum_records,
                maximum_structural_tokens=self.policy.maximum_nodes * 4,
                validate_record=self._bounds, reject_symlinks=True, require_owner=True,
                reject_duplicate_keys=True)
        except chat_store_io.StoreReadError as error:
            message = str(error).replace("Saved chats", "Saved measurements").replace("saved chat record", "saved measurement record")
            raise MeasurementStoreError(message) from error
        if not value and identity is None:
            value = {"version": self.policy.version, "records": []}
        if type(value.get("version")) is not int or value["version"] != self.policy.version:
            raise MeasurementStoreError("Saved measurements have an unsupported storage version; the existing file was kept.")
        self._metadata(value)
        if _identity(path) != identity:
            raise MeasurementStoreError("Saved measurements changed while being read; refresh before saving. The file was kept.")
        self._cache_key, self._cache_document = key, value
        return value, identity

    def _metadata(self, document: dict[str, Any]) -> None:
        if len(document) > 16:
            raise MeasurementStoreError("Saved measurements exceed their root metadata limit; the existing file was kept.")
        for key, value in document.items():
            if key == "records":
                continue
            self._bounds({key: value})
            try:
                key_bytes = len(json.dumps(key, ensure_ascii=False).encode("utf-8"))
                total = 0
                for piece in json.JSONEncoder(ensure_ascii=False, separators=(",", ":")).iterencode(value):
                    total += len(piece.encode("utf-8"))
                    if total > 16 * 1024:
                        raise MeasurementStoreError("Saved measurement metadata exceeds its encoded limit; the existing file was kept.")
                if key_bytes > 16 * 1024:
                    raise MeasurementStoreError("A saved measurement field name exceeds its encoded limit; the existing file was kept.")
            except (TypeError, ValueError, UnicodeError, RecursionError) as error:
                if isinstance(error, MeasurementStoreError):
                    raise
                raise MeasurementStoreError("Saved measurement metadata could not be encoded safely; the existing file was kept.") from error

    def load(self) -> list[dict[str, Any]]:
        with self.lock:
            document, _ = self._document(self.path())
            return copy.deepcopy(document["records"])

    def _validate_new(self, records: list[dict[str, Any]]) -> None:
        label = _NAMES[self.policy.kind]
        if self.policy.kind == "benchmark" and not records:
            raise ValueError("No benchmark evidence was supplied.")
        if any(not isinstance(record, dict) or not _REQUIRED[self.policy.kind].issubset(record) for record in records):
            raise ValueError(f"{label} evidence is incomplete and was not saved.")
        for record in records:
            self._bounds(record)
            if self.policy.kind == "benchmark":
                backend = str(record.get("backend") or "")
                identity = record.get("ssdComparisonIdentity")
                if backend in self.policy.ssd_backends:
                    if (record.get("ssdStreaming") is not True or not isinstance(identity, str)
                            or re.fullmatch(r"[0-9a-f]{64}", identity) is None):
                        raise ValueError("SSD benchmark evidence is missing its verified source identity.")
                elif record.get("ssdStreaming") is True or identity not in {None, ""}:
                    raise ValueError("Non-SSD benchmark evidence contains an SSD source identity.")

    def _retained(self, old: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self.policy.kind == "benchmark":
            new_ids = {str(record.get("id") or "") for record in new}
            shootouts = {(str(record.get("shootoutId") or ""), str(record.get("backend") or ""))
                         for record in new if record.get("shootoutId")}
            records = [item for item in old if str(item.get("id") or "") not in new_ids
                and (not item.get("shootoutId") or (str(item.get("shootoutId")), str(item.get("backend") or "")) not in shootouts)]
            records.extend(new)
            groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
            for record in records:
                groups.setdefault(self.route_identity(record), []).append(record)
            retained = []
            order = lambda item: (str(item.get("createdAt") or ""), str(item.get("id") or ""))
            for group in groups.values():
                retained.extend(sorted(group, key=order)[-self.policy.maximum_history_per_route:])
            return sorted(retained, key=order)[-self.policy.maximum_records:]
        if self.policy.kind == "ane":
            def key(item):
                return tuple(item.get(field) for field in ("modelFingerprint", "runtimeVersion", "hardwareFingerprint", "sequenceLength"))
            identities = {key(item) for item in new}
            records = [item for item in old if key(item) not in identities]
        else:
            identities = {str(item.get("id") or "") for item in new}
            records = [item for item in old if str(item.get("id") or "") not in identities]
        return (records + new)[-self.policy.maximum_records:]

    def _writable_record(self, record: dict[str, Any]) -> None:
        # Measure at the same nesting/indentation as the actual collection.
        # The small envelope overhead makes the bound conservative on write.
        total = 0
        try:
            for piece in json.JSONEncoder(indent=2, ensure_ascii=False).iterencode({"records": [record]}):
                total += len(piece.encode("utf-8"))
                if total > self.policy.maximum_record_bytes:
                    raise MeasurementStoreError("A saved measurement exceeds its encoded record limit; the existing file was kept.")
        except (TypeError, ValueError, UnicodeError, RecursionError) as error:
            if isinstance(error, MeasurementStoreError):
                raise
            raise MeasurementStoreError("A measurement could not be encoded safely; the existing file was kept.") from error

    def save(self, records: list[dict[str, Any]]) -> None:
        new = copy.deepcopy(records)
        self._validate_new(new)
        with self.lock:
            path = self.path()
            lock_path = path.with_name(path.name + ".lock")
            try:
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
            except OSError as error:
                raise MeasurementStoreError("The measurement append lock could not be opened safely; no data was changed.") from error
            try:
                details = os.fstat(descriptor)
                if not stat.S_ISREG(details.st_mode) or details.st_uid != os.geteuid() or details.st_nlink != 1:
                    raise MeasurementStoreError("The measurement append lock is not owner-controlled; no data was changed.")
                os.fchmod(descriptor, 0o600)
                deadline = time.monotonic() + self.policy.append_lock_timeout_seconds
                while True:
                    try:
                        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            raise MeasurementStoreError("Another process is still saving measurements; try again. The existing file was kept.")
                        time.sleep(0.01)
                document, before = self._document(path)
                retained = self._retained(document["records"], new)
                for record in retained:
                    self._bounds(record)
                    self._writable_record(record)
                value = {**document, "version": self.policy.version, "records": retained}
                self._metadata(value)
                def unchanged():
                    if _identity(path) != before:
                        raise MeasurementStoreError("Saved measurements changed before commit; refresh before saving. The file was kept.")
                try:
                    chat_store_io.write_document(path, value, maximum_bytes=self.policy.maximum_bytes,
                                                 before_replace=unchanged, compact_root_metadata=True)
                except chat_store_io.StoreReadError as error:
                    raise MeasurementStoreError(str(error).replace("Saved chats", "Saved measurements")) from error
                self._cache_key = None
                self._cache_document = None
            except OSError as error:
                raise MeasurementStoreError("Saved measurements could not be appended safely; the existing file was kept.") from error
            finally:
                os.close(descriptor)
