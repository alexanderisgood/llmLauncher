"""Bounded duplex PTY I/O, independent of agent state and transcript rendering.

HTTP handlers enqueue complete commands. The console reader pumps both directions
without waiting for the child to consume input. In particular, a child blocked on
stdout must never stop us draining stdout by filling its stdin buffer.
"""
from collections import deque
import os
import select
import threading


class ConsoleTransport:
    def __init__(self, fd: int, *, max_pending_bytes: int = 256 * 1024,
                 max_pending_messages: int = 128):
        os.set_blocking(fd, False)
        self._fd = fd
        self._lock = threading.Lock()
        self._pending: deque[tuple[memoryview, str | None]] = deque()
        self._keys: set[str] = set()
        self._pending_bytes = 0
        self._max_bytes = max_pending_bytes
        self._max_messages = max_pending_messages

    def send(self, data: bytes, *, coalesce_key: str | None = None) -> None:
        """Accept a whole command or reject it; never wait for the child."""
        with self._lock:
            if self._fd < 0:
                raise ValueError("That agent is no longer accepting input.")
            if coalesce_key is not None and coalesce_key in self._keys:
                return
            if (len(self._pending) >= self._max_messages
                    or self._pending_bytes + len(data) > self._max_bytes):
                raise ValueError("The agent input buffer is full. Wait for it to catch up and try again.")
            if not data:
                return
            self._pending.append((memoryview(data), coalesce_key))
            self._pending_bytes += len(data)
            if coalesce_key is not None:
                self._keys.add(coalesce_key)

    def read(self, size: int = 32 * 1024) -> bytes:
        """Read output while advancing input, preserving partial-write order.

        Only the console reader calls this method. Readiness waits hold no lock;
        the short timeout notices new input/close without another worker thread.
        """
        while True:
            with self._lock:
                fd = self._fd
                if fd < 0:
                    return b""
                writing = bool(self._pending)
            try:
                readable, writable, _ = select.select(
                    [fd], [fd] if writing else [], [], 0.05,
                )
            except (OSError, ValueError):
                with self._lock:
                    if self._fd < 0:
                        return b""
                raise
            with self._lock:
                # close() may have released the descriptor during select().
                # Never operate on a descriptor subsequently reused by the OS.
                if self._fd < 0:
                    return b""
                if writable and self._pending:
                    data, key = self._pending[0]
                    try:
                        written = os.write(fd, data[:32 * 1024])
                    except BlockingIOError:
                        written = 0
                    if written:
                        self._pending_bytes -= written
                        if written == len(data):
                            self._pending.popleft()
                            self._keys.discard(key)
                        else:
                            self._pending[0] = (data[written:], key)
                if readable:
                    try:
                        return os.read(fd, size)
                    except BlockingIOError:
                        pass

    def close(self) -> None:
        with self._lock:
            fd, self._fd = self._fd, -1
            self._pending.clear()
            self._keys.clear()
            self._pending_bytes = 0
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
