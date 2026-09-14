import json
import unittest

from session_proxy import ChatCompletionLimitGuard, MAX_LIMIT_GUARD_BUFFER


def event(value, newline=b"\n"):
    return b"data: " + json.dumps(value, separators=(",", ":")).encode() + newline * 2


def large_tool(size, newline=b"\n"):
    return event({"choices": [{"delta": {"tool_calls": [{"function": {
        "arguments": "x" * size,
    }}]}}]}, newline)


def terminal(tokens=16, newline=b"\n"):
    return (event({"choices": [{"finish_reason": "stop", "delta": {}}]}, newline)
            + event({"usage": {"completion_tokens": tokens}}, newline)
            + b"data: [DONE]" + newline * 2)


class OversizedChatEventTests(unittest.TestCase):
    def relay(self, guard, wire, chunk_size):
        parts = []
        for offset in range(0, len(wire), chunk_size):
            parts.append(guard.feed(wire[offset:offset + chunk_size]))
            if guard.passthrough_event:
                self.assertLessEqual(len(guard.pending), 3)
        return b"".join(parts) + guard.finish()

    def test_real_sized_tool_event_keeps_later_output_limit_correction(self):
        tool = large_tool(MAX_LIMIT_GUARD_BUFFER + 32768)
        guard = ChatCompletionLimitGuard(16)
        result = self.relay(guard, tool + terminal(), 16384)
        self.assertEqual(result, tool + terminal().replace(b'"stop"', b'"length"'))
        self.assertFalse(guard.disabled)

    def test_lf_crlf_fragmentation_repeated_events_and_usage_below_limit(self):
        for newline in (b"\n", b"\r\n"):
            for size in (1, 2, 3, 7, 1024, 16384):
                for tokens in (15, 16):
                    with self.subTest(newline=newline, size=size, tokens=tokens):
                        guard = ChatCompletionLimitGuard(16)
                        guard.buffer_limit = 1024
                        tools = large_tool(4200, newline) * 2
                        tail = terminal(tokens, newline)
                        result = self.relay(guard, tools + tail, size)
                        expected_tail = tail.replace(b'"stop"', b'"length"') if tokens == 16 else tail
                        self.assertEqual(result, tools + expected_tail)
                        self.assertFalse(guard.disabled)

    def test_memory_error_after_large_tool_remains_compactable(self):
        guard = ChatCompletionLimitGuard(100000, mtplx_memory_recovery=True)
        guard.buffer_limit = 1024
        tool = large_tool(4200)
        failure = event({"choices": [{"delta": {}, "finish_reason": "error"}],
                         "error": {"code": "insufficient_memory", "message":
                                   "insufficient memory: this prompt projects 41 GiB; refused before prefill"}})
        result = self.relay(guard, tool + failure, 7)
        self.assertTrue(result.startswith(tool))
        self.assertIn(b"context_length_exceeded: prefill_memory_exceeded:", result)
        self.assertTrue(guard.memory_refused)
        self.assertFalse(guard.disabled)

    def test_unfinished_event_is_forwarded_exactly_without_fabricated_completion(self):
        wire = large_tool(4200)[:-2]
        guard = ChatCompletionLimitGuard(16)
        guard.buffer_limit = 1024
        self.assertEqual(self.relay(guard, wire, 7), wire)
        self.assertEqual(guard.finish(), b"")


if __name__ == "__main__":
    unittest.main()
