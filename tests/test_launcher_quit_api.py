"""The authenticated Quit dispatches even when its HTTP client disappears."""
import io
import tempfile
from pathlib import Path
from http import HTTPStatus
from types import SimpleNamespace
import unittest
from unittest import mock

import launcher


class QuitAPITests(unittest.TestCase):
    def setUp(self):
        launcher.CONTROLLER_QUITTING.clear()
        self.addCleanup(launcher.CONTROLLER_QUITTING.clear)
        self.coordinator = mock.Mock()
        self.handler = object.__new__(launcher.Handler)
        self.handler.path = "/api/quit"
        self.handler.headers = {"X-Launcher-Token": "private-test-token", "Content-Length": "2",
                                "Origin": "http://127.0.0.1:17344"}
        self.handler.server = SimpleNamespace(csrf_token="private-test-token", shutdown_coordinator=self.coordinator)
        self.handler.rfile = io.BytesIO(b"{}")
        self.handler.wfile = mock.Mock()
        self.handler.allowed = mock.Mock(return_value=True)
        self.handler.json_response = mock.Mock()
        self.handler.send_error = mock.Mock()

    def test_quit_authenticates_before_shutdown(self):
        for headers in ({"Origin": "http://127.0.0.1:17344"},
                        {"X-Launcher-Token": "private-test-token", "Origin": "https://untrusted.invalid"}):
            with self.subTest(headers=headers):
                self.handler.headers = headers
                self.handler.do_POST()
                self.handler.send_error.assert_called_with(HTTPStatus.FORBIDDEN)
                self.coordinator.request.assert_not_called()
                self.assertFalse(launcher.CONTROLLER_QUITTING.is_set())

    def test_dispatch_precedes_acknowledgement_and_blocks_new_operations(self):
        def acknowledge(*_args):
            self.coordinator.request.assert_called_once_with(all_local=True)
            self.assertTrue(launcher.CONTROLLER_QUITTING.is_set())
        self.handler.json_response.side_effect = acknowledge
        self.handler.do_POST()
        self.handler.wfile.flush.assert_called_once()
        self.handler.json_response.side_effect = None
        self.handler.path = "/api/launch"
        with mock.patch.object(launcher, "scan_models", side_effect=AssertionError("launch scanned after Quit")):
            self.handler.do_POST()
        self.handler.json_response.assert_called_with(
            {"ok": False, "error": "LLM Launcher is quitting."}, HTTPStatus.CONFLICT)

    def test_broken_acknowledgement_cannot_leave_a_quit_undispatched(self):
        self.handler.json_response.side_effect = BrokenPipeError("synthetic disconnected browser")
        with self.assertRaises(BrokenPipeError):
            self.handler.do_POST()
        self.coordinator.request.assert_called_once_with(all_local=True)
        self.assertTrue(launcher.CONTROLLER_QUITTING.is_set())

    def test_shutdown_status_keeps_errors_available(self):
        state = {"quitting": True, "complete": True, "errors": ["server still stopping"], "processesStopped": 2}
        self.coordinator.snapshot.return_value = state
        self.handler.path = "/api/quit/status"
        self.handler.do_GET()
        self.handler.json_response.assert_called_once_with(state)

    def test_quit_between_terminal_plan_and_publication_never_opens_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = SimpleNamespace(run_dir=Path(directory), project=directory,
                client_argv=["/fixture/pi"], client_env={},client="pi",run_id="terminal-fixture")
            manager = launcher.RunManager()
            manager.plan = plan
            event = manager.cancel_event
            def publish_then_quit(path, _data):
                path.write_text("{}")
                launcher.CONTROLLER_QUITTING.set()
            with mock.patch.object(launcher, "atomic_json", side_effect=publish_then_quit), \
                    mock.patch.object(launcher.subprocess, "run") as open_terminal:
                with self.assertRaises(launcher.LaunchCancelled):
                    manager._launch_terminal_client(plan, event)
                open_terminal.assert_not_called()


if __name__ == "__main__":
    unittest.main()
