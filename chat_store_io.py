"""Bounded collection JSON IO for private Chat History and recovery files.

History can contain many individually bounded transcripts. Decode one record
at a time instead of retaining the entire serialized file alongside all
decoded strings. Writes likewise stream the JSON encoder into an owner-only
temporary file and replace the original only after the complete write/fsync.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import stat
from typing import Any, Callable, TextIO


class StoreReadError(ValueError):
    """A persisted document could not be read safely; never treat it as empty."""


_TOKENS = re.compile(r'[\[\]{}"\\,:]')
_SPACE = re.compile(r'[ \t\r\n]*')


class _CollectionReader:
    def __init__(self, handle: TextIO, maximum_bytes: int, maximum_record_bytes: int, maximum_structural_tokens: int,
                 reject_duplicate_keys: bool = False):
        self.handle = handle
        self.maximum_bytes = maximum_bytes
        self.maximum_record_bytes = maximum_record_bytes
        self.maximum_structural_tokens = maximum_structural_tokens
        self.buffer = ""
        self.position = 0
        self.origin = 0
        self.characters_read = 0
        self.bytes_read = 0
        self.eof = False
        self.reject_duplicate_keys = reject_duplicate_keys

    @staticmethod
    def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate stored field")
            value[key] = item
        return value

    def _fill(self) -> bool:
        if self.position < len(self.buffer):
            return True
        if self.eof:
            return False
        self.origin = self.characters_read
        self.buffer = self.handle.read(64 * 1024)
        self.position = 0
        if not self.buffer:
            self.eof = True
            return False
        self.characters_read += len(self.buffer)
        self.bytes_read += len(self.buffer.encode("utf-8"))
        if self.bytes_read > self.maximum_bytes:
            raise StoreReadError("Saved chats exceed the supported storage limit; the existing file was kept.")
        return True

    def peek(self) -> str:
        while self._fill():
            self.position = _SPACE.match(self.buffer, self.position).end()
            if self.position < len(self.buffer):
                return self.buffer[self.position]
        return ""

    def take(self, expected: str) -> None:
        if self.peek() != expected:
            raise StoreReadError("Saved chats contain invalid JSON; the existing file was kept.")
        self.position += 1

    def value(self, delimiters: str, maximum_bytes: int | None = None) -> Any:
        maximum = self.maximum_record_bytes if maximum_bytes is None else maximum_bytes
        pieces: list[str] = []
        retained_bytes = 0
        depth = 0
        in_string = False
        escaped_at: int | None = None
        structural_tokens = 0
        while self._fill():
            start = self.position
            stop: int | None = None
            for token in _TOKENS.finditer(self.buffer, start):
                character = token.group()
                absolute = self.origin + token.start()
                if in_string:
                    if escaped_at is not None:
                        if absolute == escaped_at:
                            escaped_at = None
                            continue
                        if absolute > escaped_at:
                            escaped_at = None
                    if character == "\\":
                        escaped_at = absolute + 1
                    elif character == '"':
                        in_string = False
                    continue
                structural_tokens += 1
                if structural_tokens > self.maximum_structural_tokens:
                    raise StoreReadError("Saved chats contain excessive structured data; the existing file was kept.")
                if character == '"':
                    in_string = True
                elif character in "[{":
                    depth += 1
                elif character in "]}":
                    if depth:
                        depth -= 1
                    elif character in delimiters:
                        stop = token.start()
                        break
                    else:
                        raise StoreReadError("Saved chats contain invalid JSON; the existing file was kept.")
                elif depth == 0 and character in delimiters:
                    stop = token.start()
                    break
            end = len(self.buffer) if stop is None else stop
            fragment = self.buffer[start:end]
            retained_bytes += len(fragment.encode("utf-8"))
            if retained_bytes > maximum:
                raise StoreReadError("A saved chat record exceeds the supported storage limit; the existing file was kept.")
            pieces.append(fragment)
            self.position = end
            if stop is not None:
                try:
                    return json.loads("".join(pieces),
                        object_pairs_hook=self._unique_object if self.reject_duplicate_keys else None)
                except (ValueError, UnicodeError, RecursionError) as error:
                    raise StoreReadError("Saved chats contain invalid JSON; the existing file was kept.") from error
        raise StoreReadError("Saved chats contain incomplete JSON; the existing file was kept.")

    def collection(self, maximum_records: int, validate_record: Callable[[dict[str, Any]], None] | None) -> list[Any]:
        self.take("[")
        values = []
        if self.peek() == "]":
            self.position += 1
            return values
        while True:
            if len(values) >= maximum_records:
                raise StoreReadError("Saved chats exceed the supported record count; the existing file was kept.")
            record = self.value(",]")
            if not isinstance(record, dict):
                raise StoreReadError("Saved chats contain an invalid record; the existing file was kept.")
            if validate_record is not None:
                validate_record(record)
            values.append(record)
            separator = self.peek()
            if separator == "]":
                self.position += 1
                return values
            self.take(",")
            if self.peek() == "]":
                raise StoreReadError("Saved chats contain invalid JSON; the existing file was kept.")

    def document(self, collection_key: str, maximum_records: int, validate_record: Callable[[dict[str, Any]], None] | None) -> dict[str, Any]:
        self.take("{")
        values: dict[str, Any] = {}
        if self.peek() == "}":
            raise StoreReadError("Saved chats have an unsupported storage format; the existing file was kept.")
        while True:
            if len(values) >= 16:
                raise StoreReadError("Saved chats contain excessive root metadata; the existing file was kept.")
            key = self.value(":", 16 * 1024)
            if not isinstance(key, str) or key in values:
                raise StoreReadError("Saved chats contain duplicate or invalid JSON keys; the existing file was kept.")
            self.take(":")
            values[key] = self.collection(maximum_records, validate_record) if key == collection_key else self.value(",}", 16 * 1024)
            separator = self.peek()
            if separator == "}":
                self.position += 1
                if self.peek():
                    raise StoreReadError("Saved chats contain trailing data; the existing file was kept.")
                if collection_key not in values:
                    raise StoreReadError("Saved chats have an unsupported storage format; the existing file was kept.")
                return values
            self.take(",")
            if self.peek() == "}":
                raise StoreReadError("Saved chats contain invalid JSON; the existing file was kept.")


def _identity(details: os.stat_result) -> tuple[int, ...]:
    return (details.st_dev, details.st_ino, details.st_size, details.st_mtime_ns,
            details.st_ctime_ns, stat.S_IFMT(details.st_mode))


def read_document(
    path: Path, *, collection_key: str, maximum_bytes: int, maximum_record_bytes: int,
    maximum_records: int = 100, validate_record: Callable[[dict[str, Any]], None] | None = None,
    maximum_structural_tokens: int = 200_000,
    reject_symlinks: bool = False, require_owner: bool = False,
    reject_duplicate_keys: bool = False,
) -> dict[str, Any]:
    """Read a stable bounded JSON collection, preserving damaged files for repair."""
    try:
        link_before = path.lstat()
    except FileNotFoundError:
        return {}
    except OSError as error:
        raise StoreReadError("Saved chats could not be read; the existing file was kept.") from error
    if reject_symlinks and stat.S_ISLNK(link_before.st_mode):
        raise StoreReadError("Saved chats use an unsafe symbolic link; the existing file was kept.")
    try:
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
        if reject_symlinks:
            flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
    except OSError as error:
        raise StoreReadError("Saved chats could not be opened; the existing file was kept.") from error
    try:
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise StoreReadError("Saved chats are not stored in a regular file; the existing file was kept.")
            if require_owner and (before.st_uid != os.geteuid() or before.st_mode & 0o022):
                raise StoreReadError("Saved chats are not protected by their owner; the existing file was kept.")
            if before.st_size > maximum_bytes:
                raise StoreReadError("Saved chats exceed the supported storage limit; the existing file was kept.")
            reader = _CollectionReader(handle, maximum_bytes, maximum_record_bytes, maximum_structural_tokens,
                                       reject_duplicate_keys)
            value = reader.document(collection_key, maximum_records, validate_record)
            after = os.fstat(handle.fileno())
        if (_identity(before) != _identity(after) or _identity(after) != _identity(path.stat())
                or _identity(link_before) != _identity(path.lstat())):
            raise StoreReadError("Saved chats changed while being read; refresh before trying again. The file was kept.")
        return value
    except StoreReadError:
        raise
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        raise StoreReadError("Saved chats could not be read safely; the existing file was kept.") from error


def write_document(path: Path, value: Any, *, maximum_bytes: int,
                   before_replace: Callable[[], None] | None = None,
                   compact_root_metadata: bool = False, collection_key: str = "records") -> None:
    """Stream one private atomic write; a rejected document never replaces data."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(12)}.tmp")
    written = 0
    def encoded_pieces():
        if not compact_root_metadata or not isinstance(value, dict):
            yield from json.JSONEncoder(indent=2, ensure_ascii=False).iterencode(value)
            return
        # Keep opaque bounded metadata compact even when records are indented.
        # Pretty-printing a valid compact metadata array can exceed the reader's
        # independent 16 KiB root-value bound.
        yield "{\n"
        # Compact values end immediately at a comma, so formatting whitespace
        # cannot consume their 16 KiB allowance. The collection goes last.
        items = [(key, item) for key, item in value.items() if key != collection_key]
        if collection_key in value:
            items.append((collection_key, value[collection_key]))
        for index, (key, item) in enumerate(items):
            if index:
                yield ",\n"
            yield "  " + json.dumps(key, ensure_ascii=False) + (": " if key == collection_key else ":")
            if key == collection_key:
                for piece in json.JSONEncoder(indent=2, ensure_ascii=False).iterencode(item):
                    yield piece.replace("\n", "\n  ")
            else:
                yield from json.JSONEncoder(ensure_ascii=False, separators=(",", ":")).iterencode(item)
        yield "\n}"
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            for piece in encoded_pieces():
                written += len(piece.encode("utf-8"))
                if written + 1 > maximum_bytes:
                    raise StoreReadError("Saved chats exceed the supported storage limit; the existing file was kept.")
                handle.write(piece)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if before_replace is not None:
            before_replace()
        os.replace(temporary, path)
    except StoreReadError:
        raise
    except (OSError, TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise StoreReadError("Saved chats could not be written safely; the existing file was kept.") from error
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
