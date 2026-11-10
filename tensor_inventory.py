"""Stable model metadata reads and bounded safetensors structural inventory.

This module never imports the controller or reads tensor payloads. Every call
opens the current files, verifies file and symlink identity before and after
reading, hashes the current header, and reads the current checkpoint index.
Only the expensive decoding and validation of an identical header is reused.
Cached descriptors are immutable; returned inventory dictionaries belong to
the caller. This cache cannot turn an old model discovery into launch proof.
"""
from __future__ import annotations

from collections import OrderedDict
import hashlib
import json
import os
from pathlib import Path
import stat
import threading
from typing import Any, Callable


MAX_JSON = 4 * 1024 * 1024
MAX_HEADER_BYTES = 64 * 1024 * 1024
_DTYPE_BYTES = {
    "BOOL": 1, "U8": 1, "I8": 1, "F8_E4M3": 1,
    "I16": 2, "U16": 2, "F16": 2, "BF16": 2,
    "I32": 4, "U32": 4, "F32": 4,
    "I64": 8, "U64": 8, "F64": 8,
}
TensorDescriptor = tuple[str, str, tuple[int, ...], tuple[int, int]]


def strict_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def source_stat_metadata(
    path_stat: os.stat_result, link_stat: os.stat_result,
    link_target: str | None,
) -> dict[str, Any]:
    return {
        "device": path_stat.st_dev, "inode": path_stat.st_ino,
        "size": path_stat.st_size, "mtimeNs": path_stat.st_mtime_ns,
        "ctimeNs": path_stat.st_ctime_ns,
        "linkDevice": link_stat.st_dev, "linkInode": link_stat.st_ino,
        "linkSize": link_stat.st_size, "linkMode": stat.S_IFMT(link_stat.st_mode),
        "linkMtimeNs": link_stat.st_mtime_ns,
        "linkCtimeNs": link_stat.st_ctime_ns, "linkTarget": link_target,
    }


def target_stat_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns)


def link_stat_identity(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_size, stat.S_IFMT(value.st_mode),
            value.st_mtime_ns, value.st_ctime_ns)


def _link_target(path: Path, details: os.stat_result) -> str | None:
    return os.readlink(path) if stat.S_ISLNK(details.st_mode) else None


def bounded_strict_json_file(
    path: Path, maximum_bytes: int = MAX_JSON,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read one current JSON document through a stable descriptor."""
    try:
        link_before = path.lstat()
        link_target = _link_target(path, link_before)
        with open(path, "rb") as handle:
            opened_before = os.fstat(handle.fileno())
            if not stat.S_ISREG(opened_before.st_mode) or not 2 <= opened_before.st_size <= maximum_bytes:
                return {}, {}
            payload = handle.read(maximum_bytes + 1)
            opened_after = os.fstat(handle.fileno())
        path_after = path.stat()
        link_after = path.lstat()
        link_target_after = _link_target(path, link_after)
        if (
            len(payload) != opened_before.st_size
            or target_stat_identity(opened_before) != target_stat_identity(opened_after)
            or target_stat_identity(opened_before) != target_stat_identity(path_after)
            or link_stat_identity(link_before) != link_stat_identity(link_after)
            or link_target != link_target_after
        ):
            return {}, {}
        value = json.loads(payload, object_pairs_hook=strict_json_pairs)
        if not isinstance(value, dict):
            return {}, {}
        return value, source_stat_metadata(opened_after, link_after, link_target_after)
    except (OSError, ValueError, UnicodeError, RecursionError):
        return {}, {}


def _decode_header(header_bytes: bytes, payload_bytes: int) -> tuple[TensorDescriptor, ...]:
    """Return immutable descriptors after checking the complete byte layout."""
    header = json.loads(header_bytes, object_pairs_hook=strict_json_pairs)
    if not isinstance(header, dict):
        raise ValueError("Safetensors header must be an object")
    descriptors: list[TensorDescriptor] = []
    intervals: list[tuple[int, int]] = []
    for name, metadata in header.items():
        if name == "__metadata__":
            continue
        if not isinstance(name, str) or not isinstance(metadata, dict):
            raise ValueError("Invalid tensor metadata")
        offsets = metadata.get("data_offsets")
        shape = metadata.get("shape")
        dtype = metadata.get("dtype")
        width = _DTYPE_BYTES.get(dtype) if isinstance(dtype, str) else None
        if (
            width is None or not isinstance(shape, list)
            or any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in shape)
            or not isinstance(offsets, list) or len(offsets) != 2
            or any(not isinstance(value, int) or isinstance(value, bool) for value in offsets)
            or offsets[0] < 0 or offsets[1] <= offsets[0]
            or offsets[1] > payload_bytes
        ):
            raise ValueError("Invalid tensor type, shape, or byte range")
        # Stop before adversarial dimensions create an enormous integer. Zero
        # element tensors cannot satisfy the established positive-range rule.
        elements = 1
        for dimension in shape:
            if dimension == 0 or elements > payload_bytes // width // dimension:
                raise ValueError("Tensor shape exceeds its payload")
            elements *= dimension
        if offsets[1] - offsets[0] != elements * width:
            raise ValueError("Tensor shape does not match its byte range")
        interval = (offsets[0], offsets[1])
        intervals.append(interval)
        descriptors.append((name, dtype, tuple(shape), interval))
    intervals.sort()
    expected_start = 0
    for start, end in intervals:
        if start != expected_start:
            raise ValueError("Safetensors ranges overlap or leave a gap")
        expected_start = end
    if not descriptors or expected_start != payload_bytes:
        raise ValueError("Safetensors payload is incomplete or has trailing bytes")
    return tuple(descriptors)


class HeaderCache:
    """Bound validated-header reuse by retained bytes and entry count.

    Keys include the freshly checked file/link identity and the SHA-256 of the
    bytes just read. The digest is required even on a hit; metadata equality
    alone never permits a stale header to pass. The cache stores no file path,
    model readiness, admission decision, index, or mutable caller dictionary.
    """

    def __init__(self, maximum_entries: int = 64, maximum_bytes: int = 32 * 1024 * 1024):
        self.maximum_entries = max(0, maximum_entries)
        self.maximum_bytes = max(0, maximum_bytes)
        self._entries: OrderedDict[tuple[Any, ...], tuple[tuple[TensorDescriptor, ...], int]] = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._bytes = 0

    def validated(
        self, header_bytes: bytes, payload_bytes: int,
        digest: str, identity: tuple[Any, ...],
    ) -> tuple[TensorDescriptor, ...]:
        key = (*identity, payload_bytes, digest)
        with self._lock:
            cached = self._entries.get(key)
            if cached is not None:
                self._entries.move_to_end(key)
                return cached[0]
        descriptors = _decode_header(header_bytes, payload_bytes)
        retained = len(header_bytes) + sum(
            512 + len(name) * 4 + len(shape) * 48
            for name, _dtype, shape, _offsets in descriptors
        )
        if not self.maximum_entries or retained > self.maximum_bytes:
            return descriptors
        with self._lock:
            # Another reader may have filled this entry during decoding.
            if key in self._entries:
                self._entries.move_to_end(key)
                return self._entries[key][0]
            self._entries[key] = (descriptors, retained)
            self._bytes += retained
            while len(self._entries) > self.maximum_entries or self._bytes > self.maximum_bytes:
                _key, (_value, cost) = self._entries.popitem(last=False)
                self._bytes -= cost
        return descriptors


HEADER_CACHE = HeaderCache()


def safetensors_inventory(
    path: Path, *, cache: HeaderCache | None = HEADER_CACHE,
    maximum_json_bytes: int = MAX_JSON,
    index_reader: Callable[[Path], tuple[dict[str, Any], dict[str, Any]]] | None = None,
) -> tuple[bool, dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Validate current checkpoint metadata without reading tensor payloads."""
    # mlx_lm consumes model*.safetensors. Auxiliary files must not approve an
    # incomplete checkpoint, and each call must discover shard membership anew.
    shards = sorted(path.glob("model*.safetensors"))
    if not shards:
        return False, {}, []
    tensors: dict[str, dict[str, Any]] = {}
    manifest: list[dict[str, Any]] = []
    for shard in shards:
        try:
            file_stat = shard.stat()
            link_stat = shard.lstat()
            link_target = _link_target(shard, link_stat)
            if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_size <= 8:
                return False, {}, []
            with open(shard, "rb") as handle:
                opened_before = os.fstat(handle.fileno())
                length_bytes = handle.read(8)
                if len(length_bytes) != 8:
                    return False, {}, []
                header_length = int.from_bytes(length_bytes, "little")
                if not 2 <= header_length <= min(MAX_HEADER_BYTES, file_stat.st_size - 8):
                    return False, {}, []
                header_bytes = handle.read(header_length)
                opened_after = os.fstat(handle.fileno())
            file_after = shard.stat()
            link_after = shard.lstat()
            link_target_after = _link_target(shard, link_after)
            if (
                len(header_bytes) != header_length
                or target_stat_identity(file_stat) != target_stat_identity(opened_before)
                or target_stat_identity(opened_before) != target_stat_identity(opened_after)
                or target_stat_identity(opened_after) != target_stat_identity(file_after)
                or link_stat_identity(link_stat) != link_stat_identity(link_after)
                or link_target != link_target_after
            ):
                return False, {}, []
            payload_bytes = file_stat.st_size - 8 - header_length
            digest = hashlib.sha256(header_bytes).hexdigest()
            descriptors = (
                _decode_header(header_bytes, payload_bytes) if cache is None else
                cache.validated(header_bytes, payload_bytes, digest, (
                    *target_stat_identity(opened_after), *link_stat_identity(link_after), link_target_after,
                ))
            )
            for name, dtype, shape, offsets in descriptors:
                if name in tensors:
                    return False, {}, []
                tensors[name] = {
                    "dtype": dtype, "shape": list(shape),
                    "data_offsets": list(offsets), "shard": shard.name,
                }
            manifest.append({
                "name": shard.name, "size": file_stat.st_size,
                "device": file_stat.st_dev, "mtime_ns": file_stat.st_mtime_ns,
                "ctime_ns": file_stat.st_ctime_ns, "inode": file_stat.st_ino,
                "link_device": link_stat.st_dev, "link_inode": link_stat.st_ino,
                "link_size": link_stat.st_size, "link_mode": stat.S_IFMT(link_stat.st_mode),
                "link_mtime_ns": link_stat.st_mtime_ns,
                "link_ctime_ns": link_stat.st_ctime_ns,
                "link_target": link_target, "header_sha256": digest,
            })
        except (OSError, ValueError, UnicodeError, RecursionError):
            return False, {}, []

    index_path = path / "model.safetensors.index.json"
    try:
        index_path.lstat()
        index_present = True
    except FileNotFoundError:
        index_present = False
    except OSError:
        return False, {}, []
    index, index_source = (
        bounded_strict_json_file(index_path, maximum_json_bytes)
        if index_reader is None else index_reader(index_path)
    )
    weight_map = index.get("weight_map")
    # A standalone checkpoint may omit an index. A declared index is part of
    # its current artifact contract and must never disappear into the same
    # fallback merely because it is malformed, unreadable, or a broken link.
    if index_present and (
        not index_source or not isinstance(weight_map, dict) or not weight_map
    ):
        return False, {}, []
    if isinstance(weight_map, dict) and weight_map:
        if any(not isinstance(name, str) or not isinstance(shard, str) for name, shard in weight_map.items()):
            return False, {}, []
        indexed = set(weight_map)
        referenced = set(weight_map.values())
        if indexed != set(tensors) or referenced != {item["name"] for item in manifest}:
            return False, {}, []
        if any(tensors[name]["shard"] != weight_map[name] for name in indexed):
            return False, {}, []
    return True, tensors, manifest
