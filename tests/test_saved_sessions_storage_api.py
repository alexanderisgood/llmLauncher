"""Saved settings storage failures are visible and retain original documents."""
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

import launcher
import saved_sessions


IDENTIFIER = "11111111-1111-4111-8111-111111111111"


class SavedSettingsAPITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        patcher = mock.patch.object(launcher, "STATE_DIR", self.root)
        patcher.start(); self.addCleanup(patcher.stop)

    def handler(self, path, payload=None):
        data = json.dumps(payload or {}).encode()
        handler = object.__new__(launcher.Handler)
        handler.path = path
        handler.headers = {"Host": "127.0.0.1", "X-Launcher-Token": "fixture-token",
                           "Origin": "http://127.0.0.1:1234", "Content-Length": str(len(data))}
        handler.server = SimpleNamespace(csrf_token="fixture-token")
        handler.rfile = io.BytesIO(data)
        handler.wfile = io.BytesIO()
        handler.send_error = mock.Mock()
        replies = []
        handler.json_response = lambda value, status=200: replies.append((value, int(status)))
        return handler, replies

    def assert_error(self, replies):
        self.assertEqual(len(replies), 1)
        value, status = replies[0]
        self.assertEqual(status, 503)
        self.assertFalse(value["ok"])
        self.assertTrue(value["storageError"])
        self.assertGreater(len(value["error"]), 0)
        self.assertLessEqual(len(value["error"]), 600)
        self.assertNotIn("profiles", value)
        self.assertNotIn("sets", value)
        self.assertNotIn("PRIVATE", value["error"])

    def test_get_both_inventories_returns_error_and_preserves_corrupt_documents(self):
        for endpoint, path in (("/api/profiles", launcher.launch_profile_store_path()),
                               ("/api/session-sets", launcher.session_set_store_path())):
            original = b'{"version":1,"PRIVATE":"must not expose",'
            path.write_bytes(original)
            handler, replies = self.handler(endpoint)
            with self.subTest(endpoint=endpoint), mock.patch.object(launcher, "presentation_models", return_value=[]):
                launcher.Handler.do_GET(handler)
            self.assert_error(replies)
            handler.send_error.assert_not_called()
            self.assertEqual(path.read_bytes(), original)

    def test_post_delete_and_set_plan_do_not_replace_unknown_versions(self):
        for endpoint, path, key in (("/api/profiles/delete", launcher.launch_profile_store_path(), "profiles"),
                                    ("/api/session-sets/delete", launcher.session_set_store_path(), "sets"),
                                    ("/api/session-sets/plan", launcher.session_set_store_path(), "sets")):
            original = json.dumps({"version": 999, key: []}).encode()
            path.write_bytes(original)
            handler, replies = self.handler(endpoint, {"id": IDENTIFIER})
            with self.subTest(endpoint=endpoint), mock.patch.object(launcher, "scan_models", return_value=[]), \
                    mock.patch.object(launcher, "presentation_models", return_value=[]), \
                    mock.patch.object(launcher, "ensure_session_set_idle"), \
                    mock.patch.object(launcher, "controller_source_is_current", return_value=True), \
                    mock.patch.object(launcher.CONTROLLER_QUITTING, "is_set", return_value=False):
                launcher.Handler.do_POST(handler)
            self.assert_error(replies)
            self.assertEqual(path.read_bytes(), original)

    def test_shared_storage_exception_is_bounded_and_recovers_on_next_successful_read(self):
        handler, replies = self.handler("/api/profiles")
        with mock.patch.object(launcher, "launch_profile_inventory", side_effect=saved_sessions.SavedSettingsReadError("Readable error " * 200)), \
                mock.patch.object(launcher, "presentation_models", return_value=[]):
            launcher.Handler.do_GET(handler)
        self.assert_error(replies)
        handler, replies = self.handler("/api/profiles")
        with mock.patch.object(launcher, "presentation_models", return_value=[]):
            launcher.Handler.do_GET(handler)
        self.assertEqual(replies[0][1], 200)
        self.assertEqual(replies[0][0]["profiles"], [])

    def test_private_controller_writers_keep_none_return_and_owner_only_permissions(self):
        self.assertIsNone(launcher._write_launch_profiles_unlocked([]))
        self.assertIsNone(launcher._write_session_sets_unlocked([]))
        self.assertEqual(launcher.launch_profile_store_path().stat().st_mode & 0o777, 0o600)
        self.assertEqual(launcher.session_set_store_path().stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
