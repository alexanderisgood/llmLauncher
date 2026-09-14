"""Shared byte framing for local response guards; payloads stay opaque here."""


def pop_event(buffer: bytearray, start: int = 0) -> bytes | None:
    endings = []
    for separator in (b"\n\n", b"\r\n\r\n"):
        index = buffer.find(separator, start)
        if index >= 0:
            endings.append((index + len(separator), index))
    if not endings:
        return None
    end, _index = min(endings, key=lambda item: item[1])
    event = bytes(buffer[:end])
    del buffer[:end]
    return event


def forward_event_prefix(buffer: bytearray) -> bytearray:
    """Forward an oversized event while retaining a possible split separator."""
    end = max(0, len(buffer) - 3)
    prefix = buffer[:end]
    del buffer[:end]
    return prefix


class EventScanner:
    """Scan appended data once; reset when the caller otherwise changes its buffer."""

    def __init__(self) -> None:
        self._start = 0

    def reset(self) -> None:
        self._start = 0

    def pop(self, buffer: bytearray) -> bytes | None:
        event = pop_event(buffer, self._start)
        # The longest separator has four bytes. A future append can complete
        # one beginning in the last three bytes, but nowhere earlier.
        self._start = max(0, len(buffer) - 3) if event is None else 0
        return event

    def forward_prefix(self, buffer: bytearray) -> bytearray:
        self.reset()
        return forward_event_prefix(buffer)
