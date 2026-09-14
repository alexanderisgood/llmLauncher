import errno
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

import launcher


class ControllerPortTests(unittest.TestCase):
    def test_binds_requested_port_without_a_temporary_probe(self):
        with mock.patch.object(launcher, "ControllerHTTPServer") as server, mock.patch.object(
            launcher, "free_port", side_effect=AssertionError("temporary probe used"),
        ):
            self.assertIs(launcher.open_controller_server(18080), server.return_value)
        server.assert_called_once_with(("127.0.0.1", 18080), launcher.Handler)
        self.assertTrue(launcher.ControllerHTTPServer.allow_reuse_address)
        self.assertFalse(launcher.ControllerHTTPServer.allow_reuse_port)

    def test_busy_port_falls_back_but_permission_errors_do_not(self):
        with mock.patch.object(launcher, "ControllerHTTPServer", side_effect=[
            OSError(errno.EADDRINUSE, "busy"), mock.sentinel.server,
        ]) as server:
            self.assertIs(launcher.open_controller_server(18080), mock.sentinel.server)
        self.assertEqual([call.args[0] for call in server.call_args_list],
                         [("127.0.0.1", 18080), ("127.0.0.1", 18081)])
        with mock.patch.object(launcher, "ControllerHTTPServer", side_effect=PermissionError(
            errno.EACCES, "denied",
        )) as server, self.assertRaises(PermissionError):
            launcher.open_controller_server(18080)
        self.assertEqual(server.call_count, 1)

    def test_restart_reuses_port_after_a_real_http_connection(self):
        class Response(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"OK")

            def log_message(self, *_args):
                pass

        try:
            first = ThreadingHTTPServer(("127.0.0.1", 0), Response)
        except PermissionError:
            self.skipTest("Local socket binding is unavailable in this sandbox")
        port = first.server_address[1]
        worker = threading.Thread(target=first.serve_forever, daemon=True)
        worker.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3) as reply:
                self.assertEqual(reply.read(), b"OK")
        finally:
            first.shutdown()
            first.server_close()
            worker.join(timeout=3)
        reopened = launcher.open_controller_server(port)
        try:
            self.assertEqual(reopened.server_address, ("127.0.0.1", port))
        finally:
            reopened.server_close()


if __name__ == "__main__":
    unittest.main()
