from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import codex_proxy
import responses_bridge


def sse_event(kind: str, **payload: object) -> bytes:
    value = {"type": kind, **payload}
    return (
        f"event: {kind}\ndata: "
        f"{json.dumps(value, separators=(',', ':'))}\n\n"
    ).encode("utf-8")


class ResponsesReliabilityTests(unittest.TestCase):
    def test_oversized_event_keeps_usage_correction_across_newline_boundaries(self) -> None:
        with patch.object(codex_proxy, "MAX_RESPONSE_GUARD_BUFFER", 1024):
            for newline in (b"\n", b"\r\n"):
                content = sse_event("response.output_text.delta", delta="x" * 4200).replace(b"\n", newline)
                terminal = sse_event("response.completed", response={
                    "status": "completed", "usage": {"output_tokens": 16},
                }).replace(b"\n", newline)
                wire = content * 2 + terminal
                for size in (1, 3, 7, 64, len(wire)):
                    with self.subTest(newline=newline, chunk_size=size):
                        guard = codex_proxy.ResponsesLimitGuard(16, streaming=True)
                        chunks = []
                        for start in range(0, len(wire), size):
                            chunks.append(guard.feed(wire[start:start + size]))
                            if guard.passthrough_event:
                                self.assertLessEqual(len(guard.pending), 3)
                        result = b"".join(chunks) + guard.finish()
                        self.assertTrue(result.startswith(content * 2))
                        self.assertIn(b"response.incomplete", result[len(content) * 2:])
                        self.assertIn(b'"reason":"max_output_tokens"', result)
                        self.assertFalse(guard.disabled)

    def test_uninspected_large_output_cannot_be_classified_as_reasoning_only(self) -> None:
        reasoning = sse_event("response.reasoning_summary_text.delta", delta="Thinking")
        terminal = sse_event("response.completed", response={
            "status": "completed", "usage": {"output_tokens": 12},
        })
        for content in (
            sse_event("response.output_text.delta", delta="x" * 4200),
            sse_event("response.output_item.done", item={"type": "function_call", "arguments": "x" * 4200}),
        ):
            for size in (7, 65536):
                with self.subTest(chunk_size=size), patch.object(codex_proxy, "MAX_RESPONSE_GUARD_BUFFER", 1024):
                    guard = codex_proxy.ResponsesLimitGuard(100, streaming=True)
                    wire = reasoning + content + terminal
                    result = b"".join(guard.feed(wire[i:i + size]) for i in range(0, len(wire), size)) + guard.finish()
                    self.assertEqual(result, wire)
                    self.assertTrue(guard.output_inspection_incomplete)
                    self.assertFalse(guard.disabled)

    def test_unfinished_oversized_event_is_preserved(self) -> None:
        with patch.object(codex_proxy, "MAX_RESPONSE_GUARD_BUFFER", 1024):
            wire = sse_event("response.output_text.delta", delta="x" * 4200)[:-2]
            guard = codex_proxy.ResponsesLimitGuard(16, streaming=True)
            result = b"".join(guard.feed(wire[i:i + 7]) for i in range(0, len(wire), 7)) + guard.finish()
            self.assertEqual(result, wire)
            self.assertEqual(guard.finish(), b"")

    def test_whallm_off_uses_responses_none_and_proxy_accepts_launcher_vocabulary(self) -> None:
        self.assertEqual(
            codex_proxy.EFFORT_ORDER,
            ("auto", "off", "minimal", "low", "medium", "high", "xhigh", "max"),
        )
        config = {
            "backend": "whallm", "servedModel": "qwen", "outputLimit": 2_048,
            "reasoning": "off",
        }
        transformed = json.loads(codex_proxy.transform_response_request(json.dumps({
            "model": "qwen", "reasoning": {"effort": "xhigh", "summary": "auto"},
            "thinking_budget": 1_024,
        }).encode("utf-8"), config))
        self.assertEqual(transformed["reasoning"], {"effort": "none", "summary": "auto"})
        self.assertNotIn("thinking_budget", transformed)

        config["reasoning"] = "max"
        transformed = json.loads(codex_proxy.transform_response_request(
            b'{"model":"qwen"}', config,
        ))
        self.assertEqual(transformed["reasoning"]["effort"], "max")

    def test_native_stream_rejects_reasoning_only_success_below_limit(self) -> None:
        reasoning = sse_event("response.output_item.added", output_index=0, item={
            "id": "reasoning-1", "type": "reasoning", "status": "in_progress",
            "summary": [],
        })
        terminal = sse_event("response.completed", response={
            "id": "response-1", "status": "completed",
            "usage": {"input_tokens": 4, "output_tokens": 12},
        })
        guard = codex_proxy.ResponsesLimitGuard(100, streaming=True)
        self.assertEqual(guard.feed(reasoning + terminal), reasoning)
        corrected = guard.finish()
        self.assertIn(b"event: response.failed", corrected)
        self.assertIn(b'"status":"failed"', corrected)
        self.assertIn(b'"code":"reasoning_without_final_output"', corrected)
        self.assertNotIn(b"response.completed", corrected)

    def test_native_guard_preserves_answer_and_tool_successes(self) -> None:
        terminal = sse_event("response.completed", response={
            "id": "response-1", "status": "completed",
            "usage": {"input_tokens": 4, "output_tokens": 12},
        })
        for final_event in (
            sse_event(
                "response.output_text.delta", item_id="message-1", output_index=1,
                content_index=0, delta="Answer",
            ),
            sse_event("response.output_item.added", output_index=1, item={
                "id": "call-1", "type": "function_call", "status": "in_progress",
                "call_id": "call-1", "name": "inspect", "arguments": "{}",
            }),
        ):
            guard = codex_proxy.ResponsesLimitGuard(100, streaming=True)
            wire = (
                sse_event("response.output_item.added", output_index=0, item={
                    "id": "reasoning-1", "type": "reasoning", "status": "in_progress",
                    "summary": [],
                })
                + final_event
                + terminal
            )
            guard.feed(wire)
            self.assertIn(b"response.completed", guard.finish())

    def test_native_json_rejects_reasoning_only_success(self) -> None:
        payload = json.dumps({
            "id": "response-json", "object": "response", "status": "completed",
            "usage": {"input_tokens": 2, "output_tokens": 8},
            "output": [{
                "id": "reasoning-1", "type": "reasoning", "status": "completed",
                "summary": [{"type": "summary_text", "text": "private"}],
            }],
        }).encode("utf-8")
        guard = codex_proxy.ResponsesLimitGuard(100, streaming=False)
        guard.feed(payload)
        corrected = json.loads(guard.finish())
        self.assertEqual(corrected["status"], "failed")
        self.assertEqual(corrected["error"]["code"], "reasoning_without_final_output")

    def test_bridge_rejects_reasoning_only_success_below_limit(self) -> None:
        request = responses_bridge.translate_responses_request(json.dumps({
            "model": "served", "input": "Solve", "stream": True,
            "max_output_tokens": 100,
        }).encode("utf-8"), {"servedModel": "served"})
        bridge = responses_bridge.ChatStreamBridge(request)
        source = (
            b'data: {"choices":[{"index":0,"delta":{"reasoning_content":"work"},'
            b'"finish_reason":"stop"}],"usage":{"prompt_tokens":4,"completion_tokens":12}}\n\n'
            b'data: [DONE]\n\n'
        )
        translated = bridge.feed(source) + bridge.finish()
        self.assertIn(b"event: response.failed", translated)
        self.assertIn(b'"code":"reasoning_without_final_output"', translated)
        self.assertNotIn(b"event: response.completed", translated)

    def test_bridge_coalesces_one_assistant_reasoning_message_and_call(self) -> None:
        request = {
            "model": "served", "stream": True, "max_output_tokens": 100,
            "tools": [{
                "type": "function", "name": "inspect",
                "parameters": {"type": "object", "properties": {}},
            }],
            "input": [
                {"type": "message", "role": "user", "content": "Start"},
                {"type": "reasoning", "summary": [
                    {"type": "summary_text", "text": "Consider the route"},
                ]},
                {"type": "message", "role": "assistant", "content": [
                    {"type": "output_text", "text": "I will inspect it."},
                ]},
                {
                    "type": "function_call", "call_id": "call-1", "name": "inspect",
                    "arguments": "{}",
                },
                {"type": "function_call_output", "call_id": "call-1", "output": "ready"},
                {"type": "message", "role": "user", "content": "Continue"},
            ],
        }
        bridged = responses_bridge.translate_responses_request(
            json.dumps(request).encode("utf-8"), {"servedModel": "served"},
        )
        messages = json.loads(bridged.body)["messages"]
        assistants = [message for message in messages if message["role"] == "assistant"]
        self.assertEqual(len(assistants), 1)
        self.assertEqual(assistants[0]["content"], "I will inspect it.")
        self.assertEqual(assistants[0]["reasoning_content"], "Consider the route")
        self.assertEqual(assistants[0]["tool_calls"][0]["id"], "call-1")
        self.assertEqual(messages[2]["role"], "tool")
        self.assertEqual(messages[3], {"role": "user", "content": "Continue"})


if __name__ == "__main__":
    unittest.main()
