"""Pi presentation updates must not displace reasoning or genuine notices."""
import unittest
from unittest.mock import Mock

import launcher


class PiStatusNoiseTests(unittest.TestCase):
    def test_token_status_updates_do_not_fill_transcript(self):
        console = launcher.AgentConsole(
            owner_run_id="fixture", plan=Mock(), process=Mock(),
            master_fd=-1, cols=100, rows=30, protocol="pi-rpc",
        )
        launcher.pi_rpc_event_output(console, {
            "type": "message_update",
            "assistantMessageEvent": {
                "type": "thinking_delta", "contentIndex": 0,
                "delta": "Check the fixture.",
            },
        })
        for index in range(1000):
            output = launcher.pi_rpc_event_output(console, {
                "type": "extension_ui_request", "id": str(index),
                "method": "setStatus", "statusKey": "progress",
                "statusText": f"{index} tokens",
            })
            self.assertEqual(output, b"")
        self.assertEqual(len(console.rpc_timeline_events), 1)
        self.assertEqual(console.rpc_timeline_events[0]["kind"], "thinking")
        for method in ("setWidget", "setTitle", "set_editor_text"):
            self.assertEqual(launcher.pi_rpc_event_output(console, {
                "type": "extension_ui_request", "method": method,
            }), b"")
        output = launcher.pi_rpc_event_output(console, {
            "type": "extension_ui_request", "id": "warning",
            "method": "notify", "message": "Response limit reached.",
        })
        self.assertIn(b"Response limit reached.", output)
        self.assertEqual(console.rpc_timeline_events[-1]["text"], "Response limit reached.")
        launcher.pi_rpc_event_output(console, {
            "type": "extension_ui_request", "id": "confirm",
            "method": "confirm", "title": "Continue?", "message": "Confirm action.",
        })
        self.assertEqual(console.rpc_interactions[0]["id"], "confirm")


if __name__ == "__main__":
    unittest.main()
