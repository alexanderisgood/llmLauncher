"""Rapid MLX native protocol and private clients on synthetic data only."""
import copy
from http import HTTPStatus
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock
import uuid

import client_planning
import codex_proxy
import launch_contract
import session_proxy
from sampling_contract import build_sampling_contract


CHAT_FIELDS = {"temperature", "top_p", "top_k", "presence_penalty", "frequency_penalty", "repetition_penalty", "seed"}
RESPONSES_FIELDS = {"temperature", "top_p", "top_k", "seed"}
DEFAULTS = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "presence_penalty": 0.2,
            "frequency_penalty": 0.0, "repetition_penalty": 1.0, "seed": 17}


def encode(value):
    return json.dumps(value).encode()


def config(reasoning="auto", *, mode="custom", responses=False, implicit=False):
    fields = RESPONSES_FIELDS if responses else CHAT_FIELDS
    values = DEFAULTS if mode == "model" else {key: value for key, value in DEFAULTS.items() if key in fields}
    contract = build_sampling_contract(mode, **{"model_defaults" if mode == "model" else "custom": values}).as_dict()
    return {"backend": "rapidmlx", "servedModel": "fixture", "reasoning": reasoning, "outputLimit": 8192,
            "samplingContract": contract, "samplingEnforcement": {
                "protocol": "responses" if responses else "chat-completions",
                "representableFields": sorted(fields), "implicitModelDefaults": implicit}}


class RapidMLXProtocolTests(unittest.TestCase):
    def test_chat_locks_reasoning_and_limits_without_losing_tool_history(self):
        history = [{"role": "user", "content": "Inspect the fixture"},
            {"role": "assistant", "content": "", "reasoning_content": "I need the inspection result.",
             "tool_calls": [{"id": "call-1", "type": "function", "function": {"name": "inspect", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "call-1", "content": "ready"}]
        request = {"model": "fixture", "messages": history, "max_tokens": 9000,
                   "max_completion_tokens": 6000, "stream": True, "tool_choice": "auto",
                   "reasoning_effort": "xhigh", "enable_thinking": True,
                   "chat_template_kwargs": {"enable_thinking": True}, "reasoning_max_tokens": 100000,
                   "thinking": {"budget_tokens": 100000}, **DEFAULTS}
        before = copy.deepcopy(request)
        for reasoning in ("auto", "off"):
            with self.subTest(reasoning=reasoning):
                rewritten = json.loads(session_proxy.transform_chat_request(encode(request), config(reasoning)))
                self.assertEqual(rewritten["messages"], history)
                self.assertEqual(rewritten["max_tokens"], 6000)
                self.assertNotIn("max_completion_tokens", rewritten)
                self.assertEqual({key: rewritten[key] for key in DEFAULTS}, DEFAULTS)
                self.assertEqual(rewritten["stream_options"], {"include_usage": True})
                self.assertNotIn("chat_template_kwargs", rewritten)
                self.assertNotIn("enable_thinking", rewritten)
                self.assertNotIn("reasoning_max_tokens", rewritten)
                self.assertNotIn("thinking", rewritten)
                self.assertEqual(rewritten.get("reasoning_effort"), "none" if reasoning == "off" else None)
        self.assertEqual(request, before)

    def test_pi_and_omp_summaries_disable_thinking_and_keep_native_budget(self):
        request = {"model": "fixture", "messages": [
            {"role": "system", "content": session_proxy.PI_SUMMARIZATION_SYSTEM_PROMPT},
            {"role": "user", "content": "Summarize the generated fixture"}]}
        for client in ("pi", "omp"):
            rewritten = json.loads(session_proxy.transform_chat_request(encode(request), config(), {"client": client}))
            self.assertEqual(rewritten["max_tokens"], 4096)
            self.assertEqual(rewritten["reasoning_effort"], "none")

    def test_native_responses_keeps_inline_reasoning_and_tool_roundtrip(self):
        history = [{"role": "user", "content": "Inspect the fixture"},
            {"type": "reasoning", "id": "reasoning-1", "summary": [{"type": "summary_text", "text": "Need a tool."}]},
            {"type": "function_call", "call_id": "call-1", "name": "inspect", "arguments": "{}"},
            {"type": "function_call_output", "call_id": "call-1", "output": "ready"}]
        tools = [{"type": "function", "name": "inspect", "parameters": {"type": "object", "properties": {}}}]
        request = {"model": "fixture", "input": history, "tools": tools, "stream": True,
                   "max_output_tokens": 9000, "reasoning": {"effort": "xhigh", "summary": "auto"},
                   "reasoning_max_tokens": 100000}
        for reasoning in ("auto", "off"):
            rewritten = json.loads(codex_proxy.transform_response_request(encode(request), config(reasoning, responses=True)))
            self.assertEqual(rewritten["input"], history)
            self.assertEqual(rewritten["tools"], tools)
            self.assertEqual(rewritten["max_output_tokens"], 8192)
            self.assertFalse(rewritten["store"])
            expected = {"summary": "auto", **({"effort": "none"} if reasoning == "off" else {})}
            self.assertEqual(rewritten["reasoning"], expected)
            self.assertNotIn("reasoning_max_tokens", rewritten)
            self.assertEqual({key: rewritten[key] for key in RESPONSES_FIELDS},
                             {key: DEFAULTS[key] for key in RESPONSES_FIELDS})

    def test_native_responses_uses_pinned_implicit_model_defaults_but_gates_custom_penalties(self):
        capability = {"samplingFields": sorted(CHAT_FIELDS), "implicitSamplingDefaultsVerified": True}
        model_config = config(mode="model", responses=True, implicit=True)
        enforcement = launch_contract.sampling_route_enforcement("rapidmlx", "codex", capability,
            model_config["samplingContract"], protocol="responses")
        self.assertEqual(set(enforcement["representableFields"]), RESPONSES_FIELDS)
        self.assertTrue(enforcement["implicitModelDefaults"])
        model_config["samplingEnforcement"] = enforcement
        rewritten = json.loads(codex_proxy.transform_response_request(encode({"model": "fixture", "input": "fixture", **DEFAULTS}), model_config))
        self.assertEqual({key: rewritten[key] for key in RESPONSES_FIELDS},
                         {key: DEFAULTS[key] for key in RESPONSES_FIELDS})
        self.assertFalse((CHAT_FIELDS - RESPONSES_FIELDS).intersection(rewritten))
        custom = build_sampling_contract("custom", custom=DEFAULTS).as_dict()
        with self.assertRaisesRegex(ValueError, "presence_penalty"):
            launch_contract.sampling_route_enforcement("rapidmlx", "codex", capability, custom, protocol="responses")
        # A stale controller must not persuade the proxy to forward fields the
        # native Responses-to-Chat adapter silently ignores.
        stale = config(responses=True)
        stale["samplingContract"] = custom
        stale["samplingEnforcement"]["representableFields"] = sorted(CHAT_FIELDS)
        with self.assertRaisesRegex(ValueError, "native Responses cannot enforce"):
            codex_proxy.transform_response_request(encode({"model": "fixture", "input": "fixture"}), stale)

    def test_history_references_and_server_storage_fail_before_inference(self):
        for change, message in [
            ({"previous_response_id": "resp-old"}, "previous_response_id"),
            ({"conversation": "conv-old"}, "conversation"),
            ({"prompt": {"id": "pmpt-old"}}, "prompt"),
            ({"input": [{"type": "item_reference", "id": "old-item"}]}, "item_reference"),
            ({"store": True}, "store"), ({"background": True}, "background"),
        ]:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, message):
                codex_proxy.transform_response_request(encode({"model": "fixture", "input": "fixture", **change}), config(responses=True))
        with self.assertRaisesRegex(ValueError, "reasoning must be auto or off"):
            codex_proxy.transform_response_request(encode({"model": "fixture", "input": "fixture"}), config("high", responses=True))
        with self.assertRaisesRegex(ValueError, "reasoning must be auto or off"):
            session_proxy.transform_chat_request(encode({"model": "fixture", "messages": []}), config("high"))

    def test_stored_and_compaction_routes_do_not_reach_native_or_bridge_transport(self):
        for module in (session_proxy, codex_proxy):
            handler = object.__new__(module.ProxyHandler)
            handler.server = SimpleNamespace(config={"backend": "rapidmlx"})
            handler.path = "/v1/responses/compact"
            handler.command = "POST"
            handler.send_json_error = mock.Mock()
            if module is session_proxy:
                handler._forward_body({}, b"{}")
            else:
                handler.authorised = lambda: True
                handler.headers = {"Content-Length": "2"}
                handler.rfile = io.BytesIO(b"{}")
                handler.forward()
            handler.send_json_error.assert_called_once()
            self.assertEqual(handler.send_json_error.call_args.args[0], HTTPStatus.NOT_IMPLEMENTED)
            self.assertIn("Rapid MLX", handler.send_json_error.call_args.args[1])

    def test_private_proxy_configs_admit_only_supported_rapid_reasoning(self):
        identifier = str(uuid.uuid4())
        for module in (session_proxy, codex_proxy):
            for reasoning in ("auto", "off", "high"):
                payload = {**config(reasoning, responses=module is codex_proxy),
                    "version": 2, "listenPort": 18181, "upstreamPort": 18182, "lanes": 1,
                    "controlKey": "control-" + "a" * 32, "upstreamKey": "upstream-" + "b" * 32,
                    "clientKey": "client-" + "c" * 32}
                payload["surfaces"] = [{"id": identifier, "client": "pi", "key": "surface-" + "d" * 32,
                    "samplingContract": payload["samplingContract"], "samplingEnforcement": payload["samplingEnforcement"]}]
                with mock.patch.object(module, "consume_private_config", return_value=encode(payload)), mock.patch.object(module.sys, "stderr", io.StringIO()):
                    if reasoning == "high":
                        with self.assertRaises(SystemExit):
                            module.load_config(Path("/synthetic/proxy.json"))
                    else:
                        self.assertEqual(module.load_config(Path("/synthetic/proxy.json"))["backend"], "rapidmlx")

    def test_private_clients_preserve_reasoning_and_codex_stateless_controls(self):
        with tempfile.TemporaryDirectory(prefix="rapidmlx-client-fixture-") as directory:
            root = Path(directory)
            versions = {"pi": "0.84.2", "omp": "omp/18.6.3", "opencode": "opencode/2.0"}
            services = client_planning.ClientServices(lambda key: key, lambda key: key,
                lambda key: versions.get(key, ""), lambda *_args: "fixture", lambda *_args: {},
                lambda value, _project: value, lambda *_args: None, lambda *_args: ["text"], lambda _size: "fixture-key")
            planner = client_planning.ClientPlanner(client_planning.ClientPolicy("0.84.2"),
                client_planning.ClientPaths(lambda: root, lambda: root), services)
            for reasoning in ("auto", "off"):
                for client in ("pi", "omp", "opencode", "codex"):
                    run_dir = root / f"{client}-{reasoning}"; run_dir.mkdir()
                    plan = SimpleNamespace(run_id="rapid-fixture", backend="rapidmlx", client=client,
                        model={"id": "fixture", "name": "MLX fixture", "servedId": "fixture", "backends": {"rapidmlx": {
                            "agentReasoning": ["auto", "off"], "codexReasoning": ["auto", "off"]}}},
                        project=str(root), context=32768, output=8192, reasoning=reasoning, port=18010, client_port=18011,
                        agent_host="terminal", purpose="interactive", runtime_binary="rapid-mlx", pi_session_file=None,
                        run_dir=run_dir, client_env={}, client_argv=[], secrets={"apiKey": "fixture-key"}, warnings=[])
                    with mock.patch.object(planner, "pi_browser_test_module", return_value=None):
                        planner.build_client_plan(plan)
                    if client == "pi":
                        overlay = json.loads(plan.client_env["LLM_LAUNCHER_PI_PROVIDER"])
                        self.assertEqual(overlay["backend"], "rapidmlx")
                        self.assertTrue(overlay["model"]["compat"]["requiresReasoningContentOnAssistantMessages"])
                        self.assertNotIn("supportsReasoningEffort", overlay["model"])
                    elif client == "omp":
                        overlay = json.loads(plan.client_env["LLM_LAUNCHER_OMP_PROVIDER"])
                        compat = overlay["models"][0]["compat"]
                        self.assertEqual(compat["reasoningContentField"], "reasoning_content")
                        self.assertTrue(compat["requiresReasoningContentForToolCalls"])
                        self.assertFalse(compat["allowsSyntheticReasoningContentForToolCalls"])
                        self.assertFalse(compat["supportsReasoningParams"])
                    elif client == "opencode":
                        overlay = json.loads(plan.client_env["OPENCODE_CONFIG_CONTENT"])
                        model = next(iter(next(iter(overlay["providers"].values()))["models"].values()))
                        self.assertEqual(model["compatibility"]["reasoningField"], "reasoning_content")
                        self.assertEqual(model["compatibility"]["requireReasoning"], reasoning != "off")
                        versions["opencode"] = "opencode/1.2"
                        planner.build_client_plan(plan)
                        old = json.loads(plan.client_env["OPENCODE_CONFIG_CONTENT"])
                        model = next(iter(next(iter(old["provider"].values()))["models"].values()))
                        self.assertEqual(model.get("interleaved"), {"field": "reasoning_content"} if reasoning == "auto" else None)
                        versions["opencode"] = "opencode/2.0"
                    else:
                        arguments = plan.client_argv
                        settings = dict(item.split("=", 1) for index, item in enumerate(arguments) if index and arguments[index - 1] == "-c")
                        self.assertEqual(settings["features.remote_compaction_v2"], "false")
                        self.assertTrue(any(key.endswith(".supports_websockets") and value == "false" for key, value in settings.items()))
                        self.assertTrue(any(key.endswith(".wire_api") and value == '"responses"' for key, value in settings.items()))
                        self.assertEqual(settings.get("model_reasoning_effort"), '"none"' if reasoning == "off" else None)
                        self.assertTrue(any("native stateless Responses" in warning for warning in plan.warnings))


if __name__ == "__main__":
    unittest.main()
