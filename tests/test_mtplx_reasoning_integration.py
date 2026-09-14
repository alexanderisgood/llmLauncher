"""Opt-in installed MTPLX encoder check; no model weights are loaded.

Run with MTPLX's Python and LLM_LAUNCHER_QWOPUS_MODEL pointing at the
downloaded Qwopus directory. Checks the actual tokenizer and server encoder.
"""
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from mtplx_reasoning import preserved_qwopus_template


@unittest.skipUnless(os.environ.get("LLM_LAUNCHER_QWOPUS_MODEL"),
                     "opt-in installed Qwopus reasoning check")
class PreservedReasoningIntegrationTests(unittest.TestCase):
    def test_native_mode_removes_conflicting_xml_from_qwopus_json_tool_template(self):
        import json
        from pathlib import Path
        from mtplx.runtime import _load_tokenizer_resilient
        from mtplx.server import openai as server
        path = Path(os.environ["LLM_LAUNCHER_QWOPUS_MODEL"])
        tokenizer = _load_tokenizer_resilient(path, json.loads((path / 'config.json').read_text()))
        tokenizer.chat_template = preserved_qwopus_template(path)
        self.assertIsNotNone(tokenizer.chat_template)
        tools = [{"type":"function", "function":{"name":"read", "description":"Read a file",
            "parameters":{"type":"object", "properties":{"path":{"type":"string"}}, "required":["path"]}}}]
        messages = [server.ChatMessage(role="user", content="Inspect the source file."),
            server.ChatMessage(role="assistant", content="", reasoning_content="ACTIVE_TOOL_REASONING_8193",
                tool_calls=[{"id":"read-1", "type":"function", "function":{
                    "name":"read", "arguments":'{"path":"fixture.txt"}'}}]),
            server.ChatMessage(role="tool", tool_call_id="read-1", content="Observed source content")]
        def encoded(mode):
            return tokenizer.decode(server._encode_messages_uncached(tokenizer, messages,
                enable_thinking=True, scoped_reasoning_history=True, tools=tools, tool_prompt_mode=mode))
        hybrid, native = encoded("hybrid"), encoded("native")
        self.assertIn('<function=read>', hybrid, 'Reproduce the contradictory runtime example')
        self.assertNotIn('<function=', native)
        self.assertNotIn('<parameter=', native)
        self.assertIn('{"name": <function-name>', native)
        self.assertIn('<tool_call>', native)
        self.assertIn('ACTIVE_TOOL_REASONING_8193', native)
        self.assertEqual(server._request_tool_prompt_mode_override(
            headers={"x-mtplx-tool-prompt-mode":"native"}, metadata={}), "native")

    def test_recovery_namespace_prevents_warm_cache_reinserting_the_loop(self):
        from mtplx.server import openai as server
        from mtplx.engine_session import EngineSessionManager
        stale = 'STALE_REPETITIVE_REASONING_5172'
        original = server.ChatMessage(role='assistant', content='Finished')
        restored, count = server._substitute_committed_reasoning_messages(
            [original], [(stale, 'Finished', '')])
        self.assertEqual(count, 1, 'Reproduce native cache restoration of omitted reasoning')
        headers = {'x-mtplx-session-id': 'pi-session:recovery:0123456789abcdef01234567'}
        manager = EngineSessionManager.__new__(EngineSessionManager)
        resolved, source = manager.resolve_session_id(headers=headers)
        self.assertEqual(resolved, headers['x-mtplx-session-id'])
        self.assertEqual(source, 'header.x-mtplx-session-id')
        sessions = Mock()
        sessions.peek.side_effect = lambda key: (
            SimpleNamespace(committed_token_ids=(1, 2, 3)) if key == 'pi-session' else None)
        sessions.resolve_session_id.return_value = (resolved, source)
        state = SimpleNamespace(args=SimpleNamespace(strip_assistant_reasoning_history=False), sessions=sessions)
        with (patch.object(server, '_reasoning_history_scoped_active', return_value=False),
              patch.object(server, '_committed_reasoning_canonicalization_enabled', return_value=True)):
            value = server._maybe_canonicalize_committed_reasoning(
                state, messages=[original], prompt_ids=[4, 5], headers=headers, metadata={},
                request=server.ChatCompletionRequest(messages=[original]), thinking_enabled=True,
                reasoning_effort=None, tools=None, tool_choice=None, tool_prompt_mode='auto',
                template_observability={})
        self.assertIsNone(value)
        sessions.peek.assert_called_once_with(resolved)
        self.assertEqual(original.content, 'Finished', 'Visible answers need no synthetic marker')

    def test_publisher_checkpoint_keeps_active_thinking_and_drops_completed_round(self):
        from transformers import AutoTokenizer
        from mtplx.server import openai as server

        path = os.environ["LLM_LAUNCHER_QWOPUS_MODEL"]
        tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
        template = preserved_qwopus_template(path)
        self.assertIsNotNone(template, "This publisher template needs review")
        self.assertEqual(template, tokenizer.chat_template)
        tokenizer.chat_template = template
        self.assertTrue(server._template_supports_scoped_reasoning(tokenizer))
        messages = [
            server.ChatMessage(role="user", content="Completed task"),
            server.ChatMessage(role="assistant", content="First answer",
                               reasoning_content="COMPLETED_REASONING_7421"),
            server.ChatMessage(role="user", content="Current task"),
            server.ChatMessage(role="assistant", content="", reasoning_content="ACTIVE_REASONING_6172",
                               tool_calls=[{"id":"read-1", "type":"function", "function":{
                                   "name":"read", "arguments":'{"path":"fixture.txt"}'}}]),
            server.ChatMessage(role="tool", tool_call_id="read-1", content="ACTUAL_RESULT_5194"),
        ]
        ids = server._encode_messages_uncached(
            tokenizer, messages, enable_thinking=True, scoped_reasoning_history=True)
        encoded = tokenizer.decode(ids)
        self.assertNotIn("COMPLETED_REASONING_7421", encoded)
        self.assertIn("First answer", encoded)
        self.assertIn("ACTIVE_REASONING_6172", encoded)
        self.assertIn("ACTUAL_RESULT_5194", encoded)
        self.assertIn('<tool_call>', encoded)
        state = SimpleNamespace(
            args=SimpleNamespace(preserve_thinking="auto",
                                 strip_assistant_reasoning_history=False),
            reasoning_history_scoped_capable=True,
        )
        with patch.object(server, "_model_family_for_state", return_value="qwen3_5"):
            self.assertEqual(server._reasoning_history_mode(state), "scoped")
            self.assertFalse(server._reasoning_history_preserve_echo_active(state))


if __name__ == "__main__":
    unittest.main()
