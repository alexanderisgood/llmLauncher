"""Preserve the Hub's text and replay contract when sanitizing streamed output."""
import random
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import launcher


def reference_text(value, limit=launcher.PI_RPC_TIMELINE_MAX_EVENT_TEXT_BYTES):
    raw = str(value or "")[:max(0, limit)].replace("\r\n", "\n").replace("\r", "\n")
    controls = {code: "�" for code in (*range(32), *range(127, 160))}
    controls.pop(9)
    controls.pop(10)
    controls[27] = "␛"
    return raw.translate(controls).encode("utf-8")[:max(0, limit)].decode("utf-8", errors="ignore")


class TimelineTextTests(unittest.TestCase):
    def test_all_controls_unicode_and_byte_boundaries_keep_existing_contract(self):
        rng = random.Random(84)
        alphabet = "".join(map(chr, range(160))) + "漢🦙é\u2028\u200d"
        samples = [None, False, 123, "\r\n\r\t\x1b[31mred", alphabet,
                   "🦙漢é" * 30] + ["".join(rng.choices(alphabet, k=800)) for _ in range(40)]
        for sample in samples:
            for limit in (-1, 0, 1, 2, 3, 4, 8, 31, 159, 256, 1000):
                with self.subTest(sample=str(sample)[:20], limit=limit):
                    result = launcher.safe_agent_timeline_text(sample, limit)
                    self.assertEqual(result, reference_text(sample, limit))
                    self.assertLessEqual(len(result.encode()), max(0, limit))

    def test_streaming_and_overflow_replay_are_unchanged(self):
        def replay(sanitizer):
            console = launcher.AgentConsole(owner_run_id="fixture", plan=Mock(), process=Mock(),
                                            master_fd=-1, cols=100, rows=30, protocol="pi-rpc")
            with patch.object(launcher.agent_console_rpc, "safe_agent_timeline_text", sanitizer), \
                    patch.object(launcher.agent_console_rpc, "datetime") as clock:
                clock.now.return_value = datetime(2026, 9, 12, tzinfo=timezone.utc)
                console.append_timeline("user", "Keep this original request")
                launcher.pi_rpc_append_timeline_delta(console, "thinking", "Initial 🦙 reasoning. " * 3500,
                                                      title="Thinking", item_id="thinking")
                for index in range(600):
                    launcher.pi_rpc_append_timeline_delta(console, "thinking", f"\x1b[0m step {index} 漢\r\n",
                                                          title="Thinking", item_id="thinking")
                return console.timeline_slice(0), console.timeline_slice(590)
        expected = replay(reference_text)
        observed = replay(launcher.safe_agent_timeline_text)
        self.assertEqual(observed, expected)
        self.assertTrue(observed[0]["timelineReset"])
        self.assertIn("Earlier text omitted", observed[0]["timelineEvents"][-1]["title"])
        self.assertEqual(observed[0]["timelineEvents"][0]["text"], "Keep this original request")


if __name__ == "__main__":
    unittest.main()
