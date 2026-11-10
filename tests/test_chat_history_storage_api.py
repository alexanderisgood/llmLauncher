"""Private storage errors remain visible HTTP JSON and preserve the source file."""
from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

import chat_history_store
import launcher


THREAD = "00000000-0000-4000-8000-000000000001"
TAB = "00000000-0000-4000-8000-000000000002"
TURN = "00000000-0000-4000-8000-000000000003"


class ChatHistoryStorageAPITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.state_patch = mock.patch.object(launcher, "STATE_DIR", self.root)
        self.state_patch.start(); self.addCleanup(self.state_patch.stop)

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

    def assert_visible_error(self, replies):
        self.assertEqual(len(replies), 1)
        value, status = replies[0]
        self.assertEqual(status, 503)
        self.assertFalse(value["ok"])
        self.assertTrue(value["storageError"])
        self.assertGreater(len(value["error"]), 0)
        self.assertLessEqual(len(value["error"]), 600)
        self.assertNotIn("threads", value)
        self.assertNotIn("private fixture transcript", value["error"])

    def test_get_reports_corruption_without_disconnected_request_or_empty_history(self):
        original = b'{"version":8,"threads":["private fixture transcript"'
        launcher.chat_history_path().write_bytes(original)
        handler, replies = self.handler("/api/chat/history")
        launcher.Handler.do_GET(handler)
        self.assert_visible_error(replies)
        handler.send_error.assert_not_called()
        self.assertEqual(launcher.chat_history_path().read_bytes(), original)

    def test_post_history_mutations_report_error_and_do_not_replace_unreadable_data(self):
        original = b'{"version":999,"threads":[]}'
        for path, payload in [
            ("/api/chat/history/get", {"id": THREAD}),
            ("/api/chat/history/update", {"id": THREAD, "title": "Generated title"}),
            ("/api/chat/history/delete", {"id": THREAD}),
        ]:
            with self.subTest(path=path):
                launcher.chat_history_path().write_bytes(original)
                handler, replies = self.handler(path, payload)
                with mock.patch.object(launcher, "controller_source_is_current", return_value=True), mock.patch.object(launcher.CONTROLLER_QUITTING, "is_set", return_value=False):
                    launcher.Handler.do_POST(handler)
                self.assert_visible_error(replies)
                self.assertEqual(launcher.chat_history_path().read_bytes(), original)

    def test_journal_error_during_recover_or_clear_is_visible_and_preserves_history(self):
        launcher.save_chat_history({"id": THREAD, "messages": [{"role": "user", "content": "Generated completed task"},
                                                              {"role": "assistant", "content": "Completed"}]})
        history = launcher.chat_history_path().read_bytes()
        journal = b'{"version":2,"entries":[]}'
        for path, payload in [
            ("/api/chat/turn/recover", {"tabId": TAB}),
            ("/api/chat/turn/clear", {"tabId": TAB, "turnId": TURN}),
        ]:
            with self.subTest(path=path):
                launcher.chat_turn_journal_path().write_bytes(journal)
                handler, replies = self.handler(path, payload)
                with mock.patch.object(launcher, "controller_source_is_current", return_value=True), mock.patch.object(launcher.CONTROLLER_QUITTING, "is_set", return_value=False):
                    launcher.Handler.do_POST(handler)
                self.assert_visible_error(replies)
                self.assertEqual(launcher.chat_history_path().read_bytes(), history)
                self.assertEqual(launcher.chat_turn_journal_path().read_bytes(), journal)

    def test_error_messages_are_bounded_even_for_a_failing_storage_dependency(self):
        handler, replies = self.handler("/api/chat/history")
        with mock.patch.object(launcher, "chat_history_inventory", side_effect=chat_history_store.StoreReadError("Generated bounded error " * 100)):
            launcher.Handler.do_GET(handler)
        self.assert_visible_error(replies)

    def test_controller_private_write_wrapper_retains_none_result(self):
        self.assertIsNone(launcher._write_chat_history_unlocked([]))
        self.assertIsNone(launcher._write_chat_turn_journal_unlocked([]))


if __name__ == "__main__":
    unittest.main()
