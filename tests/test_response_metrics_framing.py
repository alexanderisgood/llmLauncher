import json
import unittest
from unittest.mock import patch

import session_proxy as proxy


def event(value, ending=b"\n\n"):
    return b"data: " + json.dumps(value, ensure_ascii=False).encode() + ending


USAGE = event({"usage": {"prompt_tokens": 120000, "completion_tokens": 800}})


class ResponseMetricsFramingTests(unittest.TestCase):
    def metrics(self):
        return proxy.ResponseMetrics("chat-completions", "text/event-stream", "omlx")

    def test_usage_survives_oversized_event_in_real_read_chunks(self):
        metrics = self.metrics()
        wire = event({"choices": [{"delta": {"content": "x" * (proxy.MAX_METRICS_BUFFER + 20)}}]}) + USAGE
        for start in range(0, len(wire), 16 * 1024):
            metrics.feed(wire[start:start + 16 * 1024])
            self.assertLessEqual(len(metrics.buffer), proxy.MAX_METRICS_BUFFER)
        metrics.finish()
        self.assertEqual(metrics.public_usage(), (120000, 800))
        self.assertTrue(metrics.overflowed)
        self.assertFalse(metrics.output_seen, "Skipped oversized content cannot supply output evidence")

    def test_oversized_line_suffix_cannot_impersonate_a_new_event(self):
        with patch.object(proxy, "MAX_METRICS_BUFFER", 256):
            metrics = self.metrics()
            metrics.feed(b"x" * 257)
            metrics.feed(USAGE)
            self.assertEqual(metrics.public_usage(), (None, None))
            metrics.feed(USAGE)
            self.assertEqual(metrics.public_usage(), (120000, 800))

    def test_complete_lines_and_fragmented_utf8_keep_metadata(self):
        content = event({"id": "chatcmpl-12345678", "choices": [{"delta": {"content": "漢🦙"}}]}, b"\r\n\r\n")
        wire = b": comment\n" + content + b"data: invalid JSON\n\n" + USAGE.rstrip(b"\n")
        for size in (1, 2, 3, 7, 16, 64, len(wire)):
            with self.subTest(size=size):
                metrics = self.metrics()
                for start in range(0, len(wire), size):
                    metrics.feed(wire[start:start + size])
                metrics.finish()
                self.assertTrue(metrics.output_seen)
                self.assertEqual(metrics.public_usage(), (120000, 800))
                self.assertEqual(metrics.public_runtime_stats(), {"runtimeResponseId": "chatcmpl-12345678"})
                self.assertEqual(metrics.buffer, b"")

    def test_limit_applies_to_each_line_not_a_batch_of_valid_events(self):
        with patch.object(proxy, "MAX_METRICS_BUFFER", 256):
            metrics = self.metrics()
            metrics.feed(USAGE * 50)
            self.assertEqual(metrics.public_usage(), (120000, 800))
            self.assertFalse(metrics.overflowed)
            for size in (1, 3, 63, 257, 1024):
                metrics = self.metrics()
                wire = b"x" * 700 + b"\n" + USAGE
                for start in range(0, len(wire), size):
                    metrics.feed(wire[start:start + size])
                    self.assertLessEqual(len(metrics.buffer), 256)
                self.assertEqual(metrics.public_usage(), (120000, 800))

    def test_non_streaming_limit_and_overflow_stay_unchanged(self):
        metrics = proxy.ResponseMetrics("chat-completions", "application/json")
        payload = json.dumps({"usage": {"input_tokens": 10, "output_tokens": 20}}).encode()
        metrics.feed(payload[:15])
        metrics.feed(payload[15:])
        metrics.finish()
        self.assertEqual(metrics.public_usage(), (10, 20))
        with patch.object(proxy, "MAX_METRICS_BUFFER", 16):
            metrics = proxy.ResponseMetrics("chat-completions", "application/json")
            metrics.feed(payload)
            metrics.finish()
            self.assertEqual(metrics.public_usage(), (None, None))
            self.assertEqual(metrics.complete, b"")


if __name__ == "__main__":
    unittest.main()
