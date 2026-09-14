"""Pi RPC streaming, status and context recovery contracts."""
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock
import launcher
import session_proxy


class PiLiveFeatures(unittest.TestCase):
    def setUp(self):
        self.console = launcher.AgentConsole(owner_run_id="fixture", plan=Mock(),
            process=Mock(), master_fd=-1, cols=100, rows=30, protocol="pi-rpc")

    def emit(self, **event):
        return launcher.pi_rpc_event_output(self.console, event)

    def test_live_tools_share_one_identity_until_completed(self):
        for name, identifier, index in (("write", "a", 0), ("write", "b", 1)):
            tool = {"type":"toolCall", "id":identifier, "name":name,
                    "arguments":{"path":identifier + ".py", "content":"print('hello')\n"}}
            blocks = [{}] * index + [tool]
            self.emit(type="message_update", assistantMessageEvent={
                "type":"toolcall_delta", "contentIndex":index, "partial":{"content":blocks}})
            item = self.console.rpc_timeline_events[-1]
            self.assertIn("print('hello')", item["text"])
            self.assertEqual(item["title"], "Writing · write")
            key = item["itemId"]
            self.emit(type="message_update", assistantMessageEvent={
                "type":"toolcall_end", "contentIndex":index, "toolCall":tool})
            self.assertEqual(self.console.rpc_timeline_events[-1]["itemId"], key)
            self.emit(type="tool_execution_start", toolCallId=identifier, toolName=name)
            self.emit(type="tool_execution_update", toolCallId=identifier, toolName=name,
                      partialResult={"content":[{"type":"text", "text":"first line"}]})
            self.assertEqual(self.console.rpc_timeline_events[-1]["itemId"], key + ":result")
            self.emit(type="tool_execution_end", toolCallId=identifier, toolName=name,
                      result={"content":[{"type":"text", "text":"saved"}]})
            self.assertEqual(self.console.rpc_timeline_events[-2]["title"], "Completed · write")
        calls = [i for i in self.console.rpc_timeline_items.values() if i["kind"] == "toolCall"]
        self.assertEqual(len(calls), 2)

    def test_real_rpc_omits_partial_snapshots(self):
        for delta in ('{"path":"app.py","content":"def greet():', '\\n    return 1'):
            self.emit(type="message_update", assistantMessageEvent={
                "type":"toolcall_delta", "contentIndex":1, "delta":delta})
        item = self.console.rpc_timeline_events[-1]
        self.assertEqual(json.loads(item["text"])["content"], "def greet():\n    return 1")

    def test_token_speed_is_plain_metadata_and_removable(self):
        self.emit(type="extension_ui_request", method="setStatus", statusKey="tokenSpeed",
                  statusText="\x1b[38;2;12;40;20m⚡ TPS: 61.2 tok/s\x1b[0m\u200b")
        self.assertEqual(self.console.rpc_statuses["tokenSpeed"]["text"], "⚡ TPS: 61.2 tok/s")
        self.assertFalse(self.console.rpc_timeline_events)
        self.emit(type="extension_ui_request", method="setStatus", statusKey="tokenSpeed")
        self.assertFalse(self.console.rpc_statuses)

    def test_compaction_progress_and_failure_are_distinct(self):
        self.emit(type="compaction_start", reason="overflow")
        self.assertTrue(self.console.rpc_compacting)
        self.emit(type="compaction_end", reason="overflow", errorMessage="Summary failed")
        self.assertFalse(self.console.rpc_compacting)
        self.assertEqual(self.console.rpc_timeline_events[-1]["kind"], "error")
        self.emit(type="compaction_start", reason="overflow")
        self.emit(type="compaction_end", reason="overflow", willRetry=True)
        self.assertIn("Continuing", self.console.rpc_timeline_events[-1]["text"])

    def test_resume_rejects_another_project(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "session.jsonl"
            path.write_text(json.dumps({"type":"session", "cwd":folder}) + "\n")
            self.assertEqual(launcher.validated_pi_session_file(str(path), folder), str(path.resolve()))
            with self.assertRaisesRegex(ValueError, "different project"):
                launcher.validated_pi_session_file(str(path), folder + "/other")

    def test_native_context_error_survives_sdk_message_only_errors(self):
        original = {"error":{"code":"context_length_exceeded", "message":"canonical prompt too large", "type":"invalid_request_error"}}
        value = json.loads(session_proxy.normalize_uzu_context_error(json.dumps(original).encode()))
        self.assertIn("context_length_exceeded", value["error"]["message"])
        other = b'{"error":{"code":"prompt_encoding_failed","message":"encoding failed"}}'
        self.assertEqual(session_proxy.normalize_uzu_context_error(other), other)
        self.assertEqual(session_proxy.normalize_uzu_context_error(b"bad json"), b"bad json")

if __name__ == "__main__":
    unittest.main()
