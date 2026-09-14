"""Completed-prompt usage must cover tool loops and recovery, without double counting."""
import unittest
from unittest.mock import Mock, patch
import launcher


class PromptSummary(unittest.TestCase):
    def setUp(self):
        self.console = launcher.AgentConsole(owner_run_id="fixture", plan=Mock(),
            process=Mock(), master_fd=-1, cols=100, rows=30, protocol="pi-rpc")

    def emit(self, kind, **event):
        return launcher.pi_rpc_event_output(self.console, {"type":kind, **event})

    def message(self, stop="stop", usage=None, tool=False):
        message = {"role":"assistant", "stopReason":stop,
            "content":[{"type":"toolCall", "id":"tool", "name":"write", "arguments":{}}
                       if tool else {"type":"text", "text":"Finished."}]}
        if usage is not None:
            message["usage"] = usage
        self.emit("message_start", message=message)
        self.emit("message_end", message=message)
        return message

    def summaries(self):
        return [item for item in self.console.rpc_timeline_items.values() if item["kind"] == "summary"]

    def test_tool_loop_total_and_duplicate_completion(self):
        with patch.object(launcher.time, "monotonic", return_value=100):
            self.emit("agent_start")
        self.message("toolUse", {"input":100, "output":20, "cacheRead":300, "cacheWrite":50}, True)
        final = self.message(usage={"input":200, "output":30, "cacheRead":400})
        self.emit("message_end", message=final)
        self.emit("agent_end")
        self.assertFalse(self.summaries(), "Wait for all work to settle")
        with patch.object(launcher.time, "monotonic", return_value=165):
            self.emit("agent_settled")
            self.emit("agent_settled")
        self.assertEqual(len(self.summaries()), 1)
        self.assertEqual(self.summaries()[0]["title"], "Complete")
        self.assertEqual(self.summaries()[0]["text"],
            "1m 5s · 1,100 total tokens · 1,050 input · 50 output · 700 cached · 1 tool call")
        self.emit("agent_start")
        self.message(usage={"input":10, "output":5})
        self.emit("agent_settled")
        self.assertIn("15 total tokens", self.summaries()[-1]["text"])

    def test_retry_preserves_usage_clock_and_partial_reporting(self):
        with patch.object(launcher.time, "monotonic", return_value=100):
            self.emit("agent_start")
        self.message("error")
        self.emit("agent_end", willRetry=True)
        self.emit("agent_start")
        self.assertEqual(self.console.rpc_prompt_started, 100)
        self.message(usage={"input":100, "output":20})
        self.emit("agent_settled")
        self.assertIn("120 reported tokens", self.summaries()[0]["text"])
        self.assertIn("some usage unavailable", self.summaries()[0]["text"])

    def test_missing_and_invalid_usage_never_invents_zero_total(self):
        for usage in (None, {}, {"input":True, "output":2}, {"input":-1, "output":2},
                      {"input":0, "output":0, "cacheRead":0}):
            totals = {}
            launcher.pi_rpc_add_prompt_usage(totals, {"usage":usage})
            self.assertEqual(launcher.pi_rpc_prompt_summary(totals), "Token usage unavailable")

    def test_aborted_response_is_not_labelled_complete(self):
        self.emit("agent_start")
        self.message("aborted", {"input":100, "output":5})
        self.emit("agent_settled")
        self.assertEqual(self.summaries()[0]["title"], "Stopped")

    def test_loop_guard_abort_is_paused_but_unrelated_errors_stay_failed(self):
        notice = {"role":"custom", "display":True, "customType":"launcher-loop-stop",
                  "content":"Paused after repeated identical results.", "timestamp":1780000000000}
        for error, expected in [("This operation was aborted", "Repetition paused"),
                                ("Connection refused", "Failed")]:
            self.setUp()
            self.emit("agent_start")
            self.emit("message_end", message=notice)
            self.emit("message_end", message={"role":"assistant", "content":[],
                "stopReason":"error", "errorMessage":error})
            self.emit("agent_settled")
            self.assertEqual(self.summaries()[0]["title"], expected)
            self.assertEqual(any(i['kind']=='error' for i in self.console.rpc_timeline_items.values()),
                             expected == "Failed")
            self.emit("agent_start")
            self.assertEqual(self.console.rpc_loop_stop_reason, "")

    def test_historical_loop_notice_cannot_mask_a_live_abort(self):
        launcher.pi_rpc_record_history(self.console,[{"role":"custom", "display":True,
            "customType":"launcher-loop-stop", "content":"Old pause."}])
        self.assertEqual(self.console.rpc_loop_stop_reason, "")

    def test_exhausted_tool_recovery_is_failed_and_does_not_advance_queue(self):
        notice = {"role":"custom", "display":True,
                  "customType":"launcher-tool-format-error", "content":"Recovery exhausted."}
        for notice_first in (True, False):
            self.setUp()
            self.emit("agent_start")
            self.console.rpc_follow_up_queue = ["Next task"]
            if notice_first:
                self.emit("message_end", message=notice)
            self.message("stop", {"input":100, "output":5})
            if not notice_first:
                self.emit("message_end", message=notice)
            self.emit("agent_settled")
            self.assertEqual(self.summaries()[0]["title"], "Tool call failed")
            self.assertFalse(self.console.rpc_queue_advance_allowed)
            self.assertTrue(self.console.rpc_queue_paused)
            self.emit("agent_start")
            self.assertEqual(self.console.rpc_tool_format_error, "")

    def test_saved_tool_recovery_failure_remains_failed_without_affecting_live_state(self):
        user = {"role":"user", "content":"Complete the task"}
        broken = {"role":"assistant", "stopReason":"stop",
                  "content":[{"type":"text", "text":'{"name":"edit"'}],
                  "usage":{"input":100, "output":5}}
        notice = {"role":"custom", "display":True,
                  "customType":"launcher-tool-format-error", "content":"Recovery exhausted."}
        for tail in ([notice, broken], [broken, notice]):
            self.setUp()
            launcher.pi_rpc_record_history(self.console, [user, *tail])
            self.assertEqual(self.summaries()[0]["title"], "Tool call failed")
            self.assertEqual(self.console.rpc_tool_format_error, "")

    def test_history_summary_uses_whole_prompt_without_fabricated_duration(self):
        user = {"role":"user", "content":"Build the level"}
        first = {"role":"assistant", "content":[], "stopReason":"toolUse",
                 "usage":{"input":100, "output":20}}
        final = {"role":"assistant", "content":[{"type":"text", "text":"Done"}],
                 "stopReason":"stop", "usage":{"input":150, "output":30}}
        launcher.pi_rpc_record_history(self.console, [user, first, final])
        self.assertEqual(self.summaries()[0]["text"], "300 total tokens · 250 input · 50 output")
        self.setUp()
        launcher.pi_rpc_record_history(self.console, [first, final])
        self.assertFalse(self.summaries(), "A truncated prompt is not a complete total")


if __name__ == "__main__":
    unittest.main()
