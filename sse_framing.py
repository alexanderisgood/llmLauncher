"""Shared byte framing for local response guards; payloads stay opaque here."""
import json


def pop_event(buffer: bytearray, start: int = 0) -> bytes | None:
    endings = []
    # Every line ends in LF, optionally preceded by CR. Looking for the LF
    # plus the empty next line also accepts legal mixed LF/CRLF boundaries.
    for separator in (b"\n\n", b"\n\r\n"):
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


class ResponseOutcome:
    """Bounded semantic completion tracking; transport EOF alone is not success."""

    def __init__(self, protocol: str, streaming: bool, maximum: int = 256 * 1024, *, decoder=json.loads):
        self.protocol = protocol
        self.streaming = streaming
        self.maximum = maximum
        self.decoder = decoder
        self.buffer = bytearray()
        self.scanner = EventScanner()
        self.discarding = False
        self.invalid = False
        self.failed = False
        self.terminals = set()
        self.finished = False

    def inspect(self, value):
        if not isinstance(value, dict):
            self.invalid = True
            return
        kind = value.get("type")
        if value.get("error") or kind in {"error", "response.failed", "response.error", "response.cancelled"}:
            self.failed = True
        if self.protocol == "responses":
            status = (value.get("response") or {}).get("status") if isinstance(value.get("response"), dict) else value.get("status")
            if kind == "response.completed" or status == "completed":
                self.terminals.add("completed")
            elif kind == "response.incomplete" or status == "incomplete":
                self.terminals.add("truncated")
            elif status in {"failed", "cancelled"}:
                self.failed = True
        else:
            choices = value.get("choices", [])
            if not isinstance(choices, list):
                self.invalid = True
                return
            for choice in choices:
                if not isinstance(choice, dict):
                    self.invalid = True
                    continue
                reason = choice.get("finish_reason")
                if reason in {"stop", "tool_calls", "function_call"}:
                    self.terminals.add("completed")
                elif reason in {"length", "max_tokens", "max_output_tokens", "token_limit"}:
                    self.terminals.add("truncated")
                elif reason is not None:
                    self.invalid = True

    def _event(self, event):
        data = b"\n".join(line[5:].lstrip() for line in event.splitlines() if line.startswith(b"data:"))
        if not data or data.strip() == b"[DONE]":
            return
        try:
            self.inspect(self.decoder(data))
        except (ValueError, TypeError, UnicodeError):
            self.invalid = True

    def feed(self, chunk):
        if not self.streaming:
            if len(self.buffer) + len(chunk) <= self.maximum and not self.discarding:
                self.buffer.extend(chunk)
            else:
                self.buffer.clear()
                self.discarding = self.invalid = True
            return
        # Slice caller chunks too, so even a huge single read stays bounded.
        for start in range(0, len(chunk), 16384):
            self.buffer.extend(chunk[start:start + 16384])
            while True:
                event = self.scanner.pop(self.buffer)
                if event is None:
                    break
                if not self.discarding:
                    if len(event) <= self.maximum:
                        self._event(event)
                    else:
                        self.invalid = True
                self.discarding = False
            if len(self.buffer) > self.maximum:
                self.invalid = self.discarding = True
                self.scanner.forward_prefix(self.buffer)

    def finish(self):
        if self.finished:
            return self.result
        self.finished = True
        if self.streaming:
            if self.buffer.strip():
                self.invalid = True  # Unterminated frame, even if its JSON parses.
        elif not self.discarding:
            try:
                self.inspect(self.decoder(self.buffer))
            except (ValueError, TypeError, UnicodeError):
                self.invalid = True
        self.buffer.clear()
        return self.result

    @property
    def result(self):
        if self.failed:
            return "upstream-error"
        if self.invalid or not self.terminals:
            return "incomplete-stream"
        if "truncated" in self.terminals:
            return "truncated"
        return "completed"
