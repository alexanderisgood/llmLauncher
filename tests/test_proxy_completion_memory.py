"""Large complete responses retain semantics without redundant relay buffers."""
import json
import tracemalloc
import unittest

from session_proxy import ChatCompletionLimitGuard


class CompletionMemoryTests(unittest.TestCase):
    def test_complete_body_matches_chunked_guard_and_preserves_original(self):
        cases = [b"invalid JSON", b"[]", b"null", b'{"choices":[]}', b'\xff',
                 *[json.dumps({"choices": choices, "usage": usage}).encode()
                   for choices in (
                       [{"finish_reason": "stop", "message": {"content": "漢🦙"}}],
                       [{"finishReason": "stop"}],
                       [{"finish_reason": "tool_calls"}],
                       [{"finish_reason": "stop"}, {"finish_reason": "stop"}],
                       [None],
                   ) for usage in ({"completion_tokens": 100}, {"output_tokens": 100},
                                   {"completion_tokens": 99}, {"completion_tokens": True}, {})]]
        for raw in cases:
            with self.subTest(payload=raw):
                buffered = ChatCompletionLimitGuard(100, streaming=False)
                for offset in range(0, len(raw), 7):
                    self.assertEqual(buffered.feed(raw[offset:offset + 7]), b"")
                expected = buffered.finish()
                direct = ChatCompletionLimitGuard(100, streaming=False)
                body = bytearray(raw)
                result = direct.finish_completion(body)
                self.assertEqual(result, expected)
                self.assertEqual(body, raw, "Correction cannot mutate the caller's body")
                self.assertEqual(direct.pending, b"", "No second full-body buffer")
                if expected == raw:
                    self.assertIs(result, body, "Unchanged responses reuse the original body")

    def test_large_response_saves_a_full_payload_allocation(self):
        body = bytearray(json.dumps({"choices": [{"message": {"content": "x" * (4 * 1024 * 1024)},
                                                   "finish_reason": "stop"}],
                                     "usage": {"completion_tokens": 100}}).encode())
        def measure(direct):
            guard = ChatCompletionLimitGuard(100, streaming=False)
            tracemalloc.start()
            try:
                if direct:
                    result = guard.finish_completion(body)
                else:
                    guard.feed(bytes(body))
                    result = guard.finish()
                peak = tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()
            return result, peak
        buffered, old_peak = measure(False)
        direct, new_peak = measure(True)
        self.assertEqual(direct, buffered)
        self.assertEqual(json.loads(direct)["choices"][0]["finish_reason"], "length")
        self.assertGreater(old_peak - new_peak, len(body) * 0.9)


if __name__ == "__main__":
    unittest.main()
