"""HTTP cancellation that interrupts both upstream reads and downstream writes."""
import http.client
import socket
import threading


class InterruptibleHTTPConnection(http.client.HTTPConnection):
    def __init__(self, *args, downstream: socket.socket, **kwargs):
        super().__init__(*args, **kwargs)
        self._downstream = downstream
        self._stream_socket: socket.socket | None = None
        self._cancelled = False
        self._cancel_lock = threading.Lock()

    def connect(self) -> None:
        with self._cancel_lock:
            if self._cancelled:
                raise ConnectionAbortedError("Request cancelled")
        super().connect()
        with self._cancel_lock:
            # HTTPConnection clears .sock for Connection: close responses, but
            # their HTTPResponse file can still be blocked reading that socket.
            self._stream_socket = self.sock
            cancelled = self._cancelled
        if cancelled:
            self.cancel()
            raise ConnectionAbortedError("Request cancelled")

    def cancel(self) -> None:
        with self._cancel_lock:
            self._cancelled = True
            sockets = (self._stream_socket, self._downstream)
        for stream in sockets:
            if stream is not None:
                try:
                    # close() alone does not wake another thread's socket I/O.
                    # The request handler remains responsible for final close.
                    stream.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
