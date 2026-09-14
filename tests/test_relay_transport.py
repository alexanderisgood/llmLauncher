"""Real blocked socket I/O: cancellation must wake workers and release lanes."""
import http.client
import socket
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from relay_transport import InterruptibleHTTPConnection
from session_proxy import RequestScheduler


class RelayCancellationTests(unittest.TestCase):
    def test_cancel_releases_downstream_write_and_admits_next_request(self):
        downstream, client = socket.socketpair()
        downstream.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
        connection = InterruptibleHTTPConnection("127.0.0.1", 1, downstream=downstream)
        scheduler = RequestScheduler(1)
        surface = {"id": "fixture", "client": "pi"}
        first = scheduler.begin(surface, "chat-completions")
        self.assertTrue(scheduler.await_turn(first))
        scheduler.set_connection(first, connection)
        second = scheduler.begin(surface, "chat-completions")
        started, done = threading.Event(), threading.Event()

        def write():
            started.set()
            try:
                downstream.sendall(b"x" * (1024 * 1024))
            except OSError:
                pass
            finally:
                scheduler.finish(first, "cancelled")
                done.set()

        worker = threading.Thread(target=write, daemon=True)
        try:
            worker.start()
            self.assertTrue(started.wait(1))
            self.assertFalse(done.wait(0.1), "Fixture did not fill the socket")
            self.assertTrue(scheduler.cancel(first))
            self.assertTrue(done.wait(1), "Cancellation left the relay blocked writing to Pi")
            self.assertTrue(scheduler.await_turn(second))
            self.assertEqual(scheduler.snapshot([])["recent"][0]["result"], "cancelled")
        finally:
            connection.cancel()
            connection.close()
            downstream.close()
            client.close()
            worker.join(timeout=1)

    def test_cancel_interrupts_response_after_http_connection_detaches_socket(self):
        release = threading.Event()

        class Upstream(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", "100")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(b"part")
                self.wfile.flush()
                release.wait(3)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        server.daemon_threads = True
        serving = threading.Thread(target=server.serve_forever, daemon=True)
        serving.start()
        downstream, client = socket.socketpair()
        connection = InterruptibleHTTPConnection(
            "127.0.0.1", server.server_port, timeout=5, downstream=downstream,
        )
        done = threading.Event()
        worker = None
        response = None
        try:
            connection.request("GET", "/")
            response = connection.getresponse()
            self.assertIsNone(connection.sock, "Fixture should detach the response socket")

            def read():
                try:
                    response.read()
                except (OSError, http.client.IncompleteRead):
                    pass
                finally:
                    done.set()

            worker = threading.Thread(target=read, daemon=True)
            worker.start()
            self.assertFalse(done.wait(0.1))
            connection.cancel()
            self.assertTrue(done.wait(1), "Cancellation left the upstream response blocked")
        finally:
            connection.cancel()
            release.set()
            if worker:
                worker.join(timeout=1)
            if response:
                response.close()
            connection.close()
            downstream.close()
            client.close()
            server.shutdown()
            server.server_close()
            serving.join(timeout=1)

    def test_cancellation_before_connect_cannot_reopen_request(self):
        downstream, client = socket.socketpair()
        connection = InterruptibleHTTPConnection("127.0.0.1", 1, downstream=downstream)
        try:
            connection.cancel()
            with self.assertRaises(ConnectionAbortedError):
                connection.request("GET", "/")
        finally:
            connection.close()
            downstream.close()
            client.close()


if __name__ == "__main__":
    unittest.main()
