"""Bounded Whallm ownership/contract tests. No model or installed app is run."""
import copy
import hashlib
import json
import os
from pathlib import Path
import plistlib
import tempfile
import threading
import time
import unittest
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest import mock

import launcher
import whallm_runtime as native


class NativeWhallmTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="whallm-native-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.app = self.root / "Whallm.app"
        for name in native._RUNTIME_FILES:
            path = self.app / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("signed-fixture")
        (self.app / "Contents/Info.plist").write_bytes(plistlib.dumps({
            "CFBundleIdentifier":"com.deepseekv4ssd.app", "CFBundleShortVersionString":"1.1.4"}))
        self.binary = self.app / "Contents/MacOS/dsv4-app"
        (self.app / "Contents/MacOS/python3").chmod(0o755)
        self.model_path = self.root / "model.dsv4"
        self.model_path.mkdir()
        names = ["common.bin", "ngram.bin", "config.json", "generation_config.json"]
        names += [f"experts/layer_{i:02d}.bin" for i in range(48)]
        names += [f"tokenizer/{name}" for name in ("tokenizer.json", "tokenizer_config.json", "chat_template.jinja", "vocab.json", "merges.txt")]
        for name in names:
            path = self.model_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"data")
        self.manifest = {"modelID":native.MODEL_ID, "revision":native.MODEL_REVISION,
            "formatVersion":2, "modelKind":"qwen3.8-flash-next", "expertCount":512,
            "selectedExpertCount":10, "layerCount":48, "expertBlobSize":2_611_200,
            "files":[{"path":name,"size":4} for name in names]}
        self.manifest_path = self.model_path / "manifest.json"
        raw = json.dumps(self.manifest).encode()
        self.manifest_path.write_bytes(raw)
        patch = mock.patch.object(native, "MANIFEST_SHA256", hashlib.sha256(raw).hexdigest())
        patch.start(); self.addCleanup(patch.stop)
        patch = mock.patch.object(native, "verify_signature")
        self.signature = patch.start(); self.addCleanup(patch.stop)
        native._cached_signature.cache_clear()
        self.install = native.inspect_install(str(self.binary), self.model_path)
        self.model = native.model_record(self.install,
            [(name, descriptor.label) for name, descriptor in launcher.ENGINE_ADAPTERS.items()], 48 * 1024**3)
        self.config = native.launch_config(self.install, port=18091, context=16_384,
            output=4_096, cache_directory=self.root / "cache")

    def test_verified_manifest_and_all_file_sizes_required(self):
        self.assertEqual(self.install["weightBytes"], 57 * 4)
        self.signature.assert_called_once()
        (self.model_path / "experts/layer_47.bin").write_bytes(b"bad")
        with self.assertRaisesRegex(ValueError, "incomplete"):
            native.inspect_install(str(self.binary), self.model_path)

    def test_visible_route_limits_reject_a_previous_models_output_budget(self):
        self.assertEqual(self.model["backends"]["whallm"]["outputMaximum"], 4096)
        self.assertEqual(launcher.validated_limits(self.model, {"context":16384}), (16384, 4096))
        self.assertEqual(launcher.validated_limits(self.model, {"context":16384, "output":2048}), (16384, 2048))
        with self.assertRaisesRegex(ValueError, "4,096"):
            launcher.validated_limits(self.model, {"context":16384, "output":15360})

    def test_same_size_artifact_replacement_invalidates_install_and_evidence(self):
        replacement = self.model_path / "replacement"
        replacement.write_bytes(b"data")
        replacement.replace(self.model_path / "experts/layer_00.bin")
        changed = native.inspect_install(str(self.binary), self.model_path)
        self.assertNotEqual(changed["artifactIdentity"], self.install["artifactIdentity"])
        changed_model = native.model_record(changed, [("whallm", "Whallm")], 48 * 1024**3)
        self.assertEqual(changed_model["id"], self.model["id"])
        self.assertNotEqual(changed_model["backends"]["whallm"]["benchmarkModelFingerprint"],
                            self.model["backends"]["whallm"]["benchmarkModelFingerprint"])

    def test_wrong_manifest_or_runtime_is_rejected(self):
        self.manifest_path.write_text(json.dumps({**self.manifest, "expertCount":256}))
        with self.assertRaisesRegex(ValueError, "manifest"):
            native.inspect_install(str(self.binary), self.model_path)
        (self.app / "Contents/Info.plist").write_bytes(plistlib.dumps({
            "CFBundleIdentifier":"com.deepseekv4ssd.app", "CFBundleShortVersionString":"1.1.2"}))
        with self.assertRaisesRegex(ValueError, "1.1.4"):
            native.inspect_install(str(self.binary), self.model_path)

    def test_signature_failure_is_not_silently_accepted(self):
        self.signature.side_effect = ValueError("Bad signature")
        with self.assertRaisesRegex(ValueError, "Bad signature"):
            native.inspect_install(str(self.binary), self.model_path, fresh=True)

    def test_scanning_offline_install_adds_one_owned_model(self):
        binaries = {name:None for name in launcher.BINARIES}
        binaries["whallm"] = str(self.binary)
        with mock.patch.dict(launcher.BINARIES, binaries, clear=True), \
             mock.patch.object(launcher, "model_roots", return_value=[]), \
             mock.patch.object(launcher, "probe_whallm_endpoint", return_value={}), \
             mock.patch.object(launcher, "load_freetoken_connection", return_value={}), \
             mock.patch.object(native, "discover", return_value=self.install):
            records = launcher.scan_models()
        owned = [record for record in records if record.get("nativeWhallm")]
        self.assertEqual(len(owned), 1)
        self.assertFalse(owned[0]["sharedServer"])
        self.assertEqual(owned[0]["backends"]["whallm"]["contextWindows"], [16_384])

    def test_external_route_keeps_its_existing_bridge_and_ownership(self):
        with mock.patch.dict(launcher.BINARIES, {"whallm":str(self.binary)}), \
             mock.patch.object(launcher, "model_roots", return_value=[]), \
             mock.patch.object(launcher, "probe_whallm_endpoint", return_value={"model":native.SERVED_ID}), \
             mock.patch.object(launcher, "load_freetoken_connection", return_value={}), \
             mock.patch.object(native, "discover") as discover:
            records = launcher.scan_models()
        discover.assert_not_called()
        shared = [record for record in records if record.get("sharedServer")]
        self.assertEqual(len(shared), 1)
        self.assertFalse(shared[0].get("nativeWhallm"))

    def request(self, **changes):
        return {"backend":"whallm", "client":"chat", "modelId":self.model["id"],
                "project":str(self.root), "context":16_384, "reasoning":"auto", **changes}

    def build(self, **changes):
        with mock.patch.dict(launcher.BINARIES, {"whallm":str(self.binary)}), \
             mock.patch.object(launcher, "RUNS_DIR", self.root / "runs"), \
             mock.patch.object(launcher, "STATE_DIR", self.root / "state"), \
             mock.patch.object(launcher, "free_port", return_value=18091), \
             mock.patch.object(launcher, "whallm_qualification_conflict", return_value={}):
            return launcher.normalized_request(self.request(**changes), [self.model])

    def test_plan_owns_private_python_process_with_fixed_contract_and_thinking(self):
        plan = self.build()
        self.assertEqual(plan.engine_argv[:4], [self.install["python"], "-I", "-S", "-B"])
        self.assertEqual(plan.reasoning, "medium")
        self.assertEqual(plan.output, 4_096)
        self.assertEqual(plan.public()["routeKind"], "local")
        self.assertEqual(plan.engine_env["DEEPSEEK_API_KEY"], plan.secrets["apiKey"])
        self.assertEqual(plan.engine_env["WHALLM_ANE_BRIDGE"], str((self.app / "Contents/Frameworks/libWhallmANE.dylib").resolve()))
        self.assertNotIn(plan.secrets["apiKey"], " ".join(plan.engine_argv))
        config = json.loads(Path(plan.engine_argv[-1]).read_text())
        argv = native.runtime_argv(config)
        self.assertEqual(argv[argv.index("--memory-limit-gib") + 1], "40")
        self.assertEqual(argv[argv.index("--slots") + 1], "4096")
        self.assertEqual(argv[argv.index("--prompt-cache-memory-gib") + 1], "2")
        self.assertNotIn("--mtp", argv)
        self.assertEqual(config["context"], 16_384)
        with self.assertRaises(ValueError): self.build(reasoning="off")
        with self.assertRaises(ValueError): self.build(context=32_768)
        with self.assertRaises(ValueError): self.build(output=8_192)
        self.assertFalse(launcher.resolved_client_support("whallm","codex",self.model["backends"]["whallm"])["supported"])
        self.assertTrue(launcher.resolved_client_support("whallm","codex",{"sharedServer":True})["supported"])

    def test_memory_admission_counts_owned_working_set_and_cannot_override_pressure(self):
        resource = {"memoryAvailable":True, "totalMemoryBytes":48 * 1024**3, "headroomBytes":40 * 1024**3}
        with mock.patch.dict(launcher.BINARIES, {"whallm":str(self.binary)}), \
             mock.patch.object(launcher, "whallm_qualification_conflict", return_value={}):
            accepted = launcher.session_memory_admission(self.request(output=4096), [self.model], resource, {"phase":"idle"}, {})
            refused = launcher.session_memory_admission(self.request(output=4096), [self.model],
                {**resource,"headroomBytes":20 * 1024**3}, {"phase":"idle"}, {})
        self.assertTrue(accepted["launchable"])
        self.assertEqual(accepted["estimate"]["estimatedWorkingSetBytes"], 26 * 1024**3)
        self.assertFalse(accepted["estimate"].get("sharedEngine", False))
        self.assertFalse(refused["launchable"])
        self.assertFalse(refused["requiresAcknowledgement"])

    def test_stop_terminates_the_owned_native_process(self):
        plan = self.build()
        manager = launcher.RunManager()
        manager.plan = plan
        process = mock.Mock()
        manager.process = process
        manager.state.update(phase="running", run=plan.public())
        with mock.patch.object(manager, "_terminate_process") as terminate:
            manager.stop()
        self.assertIn(mock.call(process, 12), terminate.call_args_list)
        self.assertEqual(manager.state["phase"], "idle")
        self.assertNotIn("left untouched", manager.state["message"])

    def test_fixed_configuration_rejects_memory_auto_and_larger_cache(self):
        for key, value in (("memoryGiB",0), ("memoryGiB",48), ("slots",8192), ("promptCacheGiB",8), ("context",32768)):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                native.runtime_argv({**self.config, key:value})

    def test_memory_watchdog_stops_engine_before_waiting_for_agents(self):
        plan = self.build()
        for sample in ({"processGroupFootprintAvailable":True,"processGroupMemberCount":1,
                        "processGroupPhysicalFootprintBytes":40 * 1024**3,
                        "processGroupLifetimePeakPhysicalFootprintBytes":40 * 1024**3}, RuntimeError("probe failed")):
            with self.subTest(sample=type(sample).__name__):
                manager = launcher.RunManager(); manager.plan = plan
                process = mock.Mock(pid=987654); process.poll.return_value = None
                manager.process = process
                cancelled = threading.Event(); order = []
                with mock.patch.object(launcher.os,"getpgid",return_value=987654), \
                     mock.patch.object(launcher,"darwin_process_group_physical_footprint",
                                       side_effect=sample if isinstance(sample,Exception) else None,
                                       return_value=sample), \
                     mock.patch.object(manager,"_terminate_process",side_effect=lambda *_:order.append("engine")), \
                     mock.patch.object(manager,"_stop_owned",side_effect=lambda *_:order.append("cleanup")):
                    manager._guard_owned_memory(plan,process,cancelled,"Whallm",native.MEMORY_BYTES)
                self.assertTrue(cancelled.is_set())
                self.assertEqual(order,["engine","cleanup"])
                self.assertEqual(manager.state["phase"],"failed")

    def test_readiness_requires_explicit_load_and_matching_resident_contract(self):
        state = {"loaded":False, "loadCalls":0}
        config = copy.deepcopy(self.config)
        expected = {"context":config["context"],"output":config["output"],"memoryGiB":40,
                    "manifestSHA256":native.MANIFEST_SHA256,"runtimeIdentity":self.install["runtimeIdentity"]}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self):
                body = {"loaded_model":native.SERVED_ID if state["loaded"] else None, "loading_model":None,
                    "model_path":config["install"]["modelPath"], "launcher_contract":expected,
                    "runtime":{"slots":4096,"read_workers":4,"prompt_cache_memory_gib":2,
                               "ane_prefill_ratio":0.25,"mtp_enabled":False}}
                self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(body).encode())
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                state["loadCalls"] += 1
                state["model"] = body["model"]
                state["authorization"] = self.headers.get("Authorization")
                time.sleep(0.05)
                state["loaded"] = True
                self.send_response(200); self.end_headers(); self.wfile.write(b'{}')
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start(); config["port"] = server.server_port
        try:
            native.wait_ready(config, "private-test-key", threading.Event(), lambda:True, timeout=3)
            self.assertEqual(state["loadCalls"], 1)
            self.assertEqual(state["model"], native.SERVED_ID)
            self.assertEqual(state["authorization"], "Bearer private-test-key")
            expected["context"] = 262144
            with self.assertRaisesRegex(RuntimeError, "does not match"):
                native.wait_ready(config, "private-test-key", threading.Event(), lambda:True, timeout=3)
            cancelled = threading.Event(); cancelled.set()
            with self.assertRaises(InterruptedError):
                native.wait_ready(config, "private-test-key", cancelled, lambda:True, timeout=1)
            with self.assertRaisesRegex(RuntimeError, "exited"):
                native.wait_ready(config, "private-test-key", threading.Event(), lambda:False, timeout=1)
        finally:
            server.shutdown(); server.server_close(); worker.join(2)


class NativeContractTests(unittest.TestCase):
    def fixture(self):
        @dataclass(frozen=True)
        class Installed:
            maximum_context: int = 262144
            @classmethod
            def open(cls, path): return cls()
        @dataclass(frozen=True)
        class Options:
            max_tokens: int = 999999
        class APIError(ValueError):
            def __init__(self, message, **kwargs):
                super().__init__(message); self.code = kwargs.get("code")
        class Runtime:
            def __init__(self):
                self.metrics = SimpleNamespace(snapshot=lambda:{"runtime_prompt_tokens":100,
                    "runtime_generation_tokens":10,"prompt_cache_reused_tokens":80})
            def _encode_prompt(self, prompt): return [0] * int(prompt)
            def stream(self, prompt, options): return {"prompt":prompt,"limit":options.max_tokens}
        class Manager:
            def _configure(self, value): raise AssertionError("Must be blocked")
            def codex_models(self): return [{"context_window":4096,"max_context_window":4096}]
        server = SimpleNamespace(APIError=APIError, ModelManager=Manager,
            _usage=lambda p,c:{"prompt_tokens":p,"completion_tokens":c},
            _response_usage=lambda p,c:{"input_tokens":p,"output_tokens":c,"input_tokens_details":{"cached_tokens":0}},
            _options=lambda *a,**kw:Options())
        class Handler:
            def _chat(self, payload, model): return server._usage(payload[0], payload[1])
            def _responses(self, payload, model): return server._response_usage(payload[0], payload[1])
            def _completion(self, payload, model): return server._usage(payload[0], payload[1])
            def _validated_response_pieces(self, runtime, prompt, options):
                yield runtime.stream(prompt, options)
        def reasoning(payload, *, responses_api=False, qwen=False):
            if responses_api and payload.get("reasoning") is not None and not isinstance(payload["reasoning"], dict):
                raise APIError("reasoning must be an object")
            return payload
        server._reasoning_settings = reasoning
        server.OpenAIHandler = Handler
        config = {"install":{"modelPath":"/tmp/native-whallm-test"},"context":16384,"output":4096}
        native.install_native_contract(server, Installed, config, Runtime)
        return server, Installed, Runtime, Options

    def test_context_is_eagerly_checked_and_output_capped_before_native_generation(self):
        server, installed, runtime, options = self.fixture()
        self.assertEqual(installed.open("/tmp/native-whallm-test").maximum_context, 16384)
        with self.assertRaises(ValueError): installed.open("/tmp/wrong-model")
        self.assertEqual(runtime().stream("100", options())["limit"], 4096)
        self.assertEqual(runtime().stream("16000", options())["limit"], 384)
        with self.assertRaisesRegex(ValueError, "context limit") as error:
            runtime().stream("16384", options())
        self.assertEqual(error.exception.code, "context_length_exceeded")
        with self.assertRaisesRegex(ValueError, "context limit"):
            server.OpenAIHandler()._validated_response_pieces(runtime(), "16384", options())
        self.assertEqual(list(server.OpenAIHandler()._validated_response_pieces(runtime(), "100", options()))[0]["limit"],4096)
        self.assertEqual(server._options().max_tokens, 4096)
        with self.assertRaisesRegex(ValueError, "owned"):
            server.ModelManager()._configure({"memory_limit_gib":0})
        self.assertEqual(server.ModelManager().codex_models()[0]["context_window"],16384)

    def test_only_exact_current_native_counts_enrich_usage(self):
        server, _, runtime, _ = self.fixture()
        handler = server.OpenAIHandler(); model = SimpleNamespace(runtime=runtime())
        self.assertEqual(handler._chat((100,10), model)["prompt_tokens_details"]["cached_tokens"], 80)
        self.assertEqual(handler._responses((100,10), model)["input_tokens_details"]["cached_tokens"], 80)
        self.assertNotIn("prompt_tokens_details", handler._chat((101,10), model))
        self.assertNotIn("prompt_tokens_details", server._usage(100,10), "No metric reuse outside the current request")
        for cached in (-1, 101, True, "80"):
            self.assertIsNone(native.matched_cached_tokens({"runtime_prompt_tokens":100,
                "runtime_generation_tokens":10,"prompt_cache_reused_tokens":cached},100,10))

    def test_thinking_default_stays_on_and_bad_responses_shape_is_native_error(self):
        server, *_ = self.fixture()
        request = server._reasoning_settings({},qwen=True)
        self.assertEqual(request["thinking_mode"],"thinking")
        self.assertEqual(request["reasoning_effort"],"medium")
        with self.assertRaisesRegex(ValueError,"enabled"):
            server._reasoning_settings({"reasoning_effort":"none"},qwen=True)
        for value in ([], "invalid", 3):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError,"object"):
                server._reasoning_settings({"reasoning":value},qwen=True,responses_api=True)


if __name__ == "__main__":
    unittest.main()
