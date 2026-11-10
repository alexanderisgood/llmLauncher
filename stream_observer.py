"""Small read-scoped helpers for independent consumers of an SSE stream."""
from __future__ import annotations

import json
from typing import Any


class ChunkJSONDecoder:
    """Decode shared small payloads once without keeping request data at rest.

    A relay has independent semantic and performance observers. Most events
    fit in one 16 KiB read; bounding the cache by encoded bytes avoids retaining
    large tool arguments twice. Call clear() after each upstream read.
    """

    def __init__(self, maximum: int = 64 * 1024) -> None:
        self.maximum = maximum
        self.size = 0
        self.cache: dict[bytes, Any] = {}

    def loads(self, payload: bytes | bytearray) -> Any:
        if len(payload) > self.maximum:
            return json.loads(payload)
        key = bytes(payload)
        if key in self.cache:
            return self.cache[key]
        value = json.loads(payload)
        if self.size + len(key) <= self.maximum:
            self.cache[key] = value
            self.size += len(key)
        return value

    def clear(self) -> None:
        self.cache.clear()
        self.size = 0
