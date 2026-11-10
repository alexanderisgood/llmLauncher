"""Rapid MLX catalog and real planning paths, without loading any weights."""
import copy
from contextlib import ExitStack
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import subprocess
import unittest
from unittest import mock

import launcher
import rapidmlx_runtime as rapid


class RapidRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.prefix = self.root / "runtime with spaces"
        binary_dir = self.prefix / "bin"
        binary_dir.mkdir(parents=True)
        self.binary = binary_dir / "rapid-mlx"
        self.binary.write_text("#!/bin/sh\nexit 0\n")
        self.binary.chmod(0o700)
        (binary_dir / "python").write_text("fixture")
        (binary_dir / "python").chmod(0o700)
        site = self.prefix / "lib/python3.13/site-packages"
        self.package = site / "rapid_mlx"
        self.package.mkdir(parents=True)
        for name in ("cli_parser.py", "server.py"):
            (self.package / name).write_text("# fixture\n")
        models = site / "mlx_lm/models"
        models.mkdir(parents=True)
        (models / "qwen3_5.py").write_text("# supported local model\n")
        self.metadata = site / f"rapid_mlx-{rapid.VERSION}.dist-info/METADATA"
        self.metadata.parent.mkdir()
        self.metadata.write_text(f"Name: rapid-mlx\nVersion: {rapid.VERSION}\n")
        self.runtime = rapid.inspect_runtime(self.binary)
        self.model_root = self.root / "model with spaces"
        self.model_root.mkdir()
        (self.model_root / "config.json").write_text(json.dumps({
            "model_type": "qwen3_5", "text_config": {
                "model_type": "qwen3_5_text", "max_position_embeddings": 262144}}))
        (self.model_root / "tokenizer.json").write_text("{}")
        (self.model_root / "model.safetensors").write_bytes(b"synthetic fixture bytes")
        self.model = {"id": "rapid-model", "name": "Fixture Qwen", "path": str(self.model_root),
            "format": "mlx", "ready": True, "nativeContext": 262144, "size": 24,
            "defaultSampling": {"temperature": 0.7, "top_p": 0.95, "top_k": 20, "presence_penalty": 1.5},
            "backends": {}}
        self.cap = rapid.capability(self.model, self.runtime)
        self.model["backends"]["rapidmlx"] = self.cap
        self.payload = {"backend": "rapidmlx", "client": "chat", "modelId": self.model["id"],
            "project": str(self.root), "context": 32768, "output": 4096, "reasoning": "auto",
            "mode": "custom", "options": {"acceleration": "off", "depth": 1, "kv": "off"}}
        patcher = mock.patch.dict(launcher.BINARIES, rapidmlx=str(self.binary))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_inspection_is_passive_and_uses_outer_multimodal_model_type(self):
        with mock.patch.object(launcher.subprocess, "Popen", side_effect=AssertionError("a process started")):
            self.assertTrue(rapid.inspect_runtime(self.binary)["ready"])
            self.assertTrue(rapid.capability(self.model, self.runtime)["runnable"])
        self.assertEqual(rapid.inspect_model(self.model_root)["modelType"], "qwen3_5")
        self.assertEqual(self.cap["contextMaximum"], 262144)

    def test_origin_labels_do_not_lock_compatible_weights_and_incomplete_models_fail(self):
        for fmt in ("gguf", "GGUF", "Slotstream MLX 4-bit + SSD"):
            self.assertTrue(rapid.capability({**self.model, "format": fmt}, self.runtime)["runnable"])
        self.metadata.write_text("Version: 0.15.0\n")
        self.assertFalse(rapid.inspect_runtime(self.binary)["ready"])
        (self.model_root / "model.safetensors").unlink()
        self.assertIsNone(rapid.inspect_model(self.model_root))
        blocked = rapid.capability({**self.model, "format": "GGUF"}, self.runtime)
        self.assertFalse(blocked["runnable"])

    def test_changed_runtime_or_model_fails_the_launch_boundary(self):
        rapid.validate_route(str(self.binary), self.model, self.cap, 32768, 4096)
        (self.model_root / "generation_config.json").write_text('{"temperature": 0.2}')
        with self.assertRaisesRegex(ValueError, "changed after scanning"):
            rapid.validate_route(str(self.binary), self.model, self.cap, 32768, 4096)
        self.model["backends"]["rapidmlx"] = rapid.capability(self.model, self.runtime)
        (self.package / "server.py").write_text("# changed runtime\n")
        with self.assertRaisesRegex(ValueError, "changed after scanning"):
            rapid.validate_route(str(self.binary), self.model, self.model["backends"]["rapidmlx"], 32768, 4096)

    def test_unindexed_native_shard_or_custom_code_cannot_bypass_identity(self):
        (self.model_root / "model.safetensors.index.json").write_text(
            json.dumps({"weight_map": {"fixture.weight": "model.safetensors"}}))
        self.cap = rapid.capability(self.model, self.runtime)
        self.assertTrue(self.cap["runnable"])
        extra = self.model_root / "model-extra.safetensors"
        extra.write_bytes(b"unindexed tensor override")
        self.assertIsNone(rapid.inspect_model(self.model_root))
        with self.assertRaisesRegex(ValueError, "changed after scanning"):
            rapid.validate_route(str(self.binary), self.model, self.cap, 32768, 4096)
        extra.unlink()
        config_path = self.model_root / "config.json"
        config = json.loads(config_path.read_text())
        config["model_file"] = "custom.py"
        config_path.write_text(json.dumps(config))
        self.assertIsNone(rapid.inspect_model(self.model_root))

    def test_real_preflight_is_read_only_and_rejects_unimplemented_controls(self):
        with ExitStack() as stack:
            for owner, name in ((launcher, "free_port"), (Path, "mkdir"),
                                (launcher.secrets, "token_urlsafe"), (launcher.subprocess, "Popen")):
                stack.enter_context(mock.patch.object(owner, name, side_effect=AssertionError("preflight allocated")))
            contract = launcher._launch_contract_validator().validate_live(self.payload, [self.model])
            contract.require_validated()
            for options in ({"acceleration": "mtp"}, {"depth": 2}, {"kv": "q8"}):
                with self.subTest(options=options), self.assertRaises(ValueError):
                    launcher._launch_contract_validator().validate_live({**self.payload, "options": options}, [self.model])

    def test_real_session_plan_accepts_unmeasured_rapid_route_without_loading(self):
        model = copy.deepcopy(self.model)
        model["memoryGeometry"] = {"ready": True, "fullAttentionLayers": 2,
                                   "kvHeads": 1, "headDimension": 8}
        resource = {"memoryAvailable": True, "totalMemoryBytes": 48 * 1024**3,
                    "headroomBytes": 40 * 1024**3, "thermalAvailable": True,
                    "thermalState": "nominal"}
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(launcher.MANAGER, "hub_snapshot", return_value={"phase": "idle"}))
            stack.enter_context(mock.patch.object(launcher, "active_launcher_operation", return_value={"active": False}))
            stack.enter_context(mock.patch.object(launcher, "public_session_resource", return_value=resource))
            for owner, name in ((launcher, "free_port"), (Path, "mkdir"),
                                (launcher.secrets, "token_urlsafe"), (launcher.subprocess, "Popen")):
                stack.enter_context(mock.patch.object(owner, name, side_effect=AssertionError("session planning allocated")))
            dashboard = launcher.session_dashboard_plan(self.payload, [model], resource_snapshot={"fixture": True})
        admission = dashboard["admission"]
        self.assertEqual(admission["decision"], "ready", admission.get("detail"))
        self.assertTrue(admission["launchable"])
        self.assertEqual(admission["route"]["backend"], "rapidmlx")
        self.assertEqual(admission["request"]["options"], self.payload["options"])
        self.assertFalse(dashboard["warmRoute"]["canAttach"])
        self.assertIn("rapidmlx", launcher.BENCHMARK_ENGINE_SETTING_KEYS)

    def test_builder_binds_auth_context_output_offline_and_native_defaults(self):
        plan = SimpleNamespace(backend="rapidmlx", client="chat", model=copy.deepcopy(self.model),
            run_id="fixture-run-id", context=32768, output=4096, reasoning="off", port=18081,
            runtime_binary=str(self.binary), options=dict(self.payload["options"]),
            run_dir=self.root, secrets={}, warnings=[])
        launcher.build_rapidmlx(plan, self.cap)
        argv = plan.engine_argv
        self.assertEqual(argv[:3], [str(self.binary), "serve", str(self.model_root)])
        self.assertEqual(argv[argv.index("--host") + 1], "127.0.0.1")
        self.assertEqual(argv[argv.index("--context-length") + 1], "32768")
        self.assertEqual(argv[argv.index("--default-presence-penalty") + 1], "1.5")
        self.assertIn("--no-thinking", argv)
        self.assertIn("--no-spec-decode", argv)
        self.assertIn("--disable-model-downloads", argv)
        self.assertNotIn(plan.secrets["apiKey"], argv)
        self.assertEqual(plan.engine_env["RAPID_MLX_API_KEY"], plan.secrets["apiKey"])
        self.assertEqual(plan.engine_env["RAPID_MLX_MAX_GENERATION_TOKENS"], "4096")
        self.assertEqual(plan.engine_env["HF_HUB_OFFLINE"], "1")
        self.assertEqual(plan.engine_env["RAPID_MLX_TELEMETRY"], "0")

    def test_readiness_requires_completed_warmup_and_exact_served_id(self):
        catalog = {"data": [{"id": "fixture"}]}
        for health in ({}, {"ready": True}, {"ready": False, "model_loaded": True}):
            with self.assertRaises(ValueError):
                rapid.validate_ready(health, catalog, "fixture")
        rapid.validate_ready({"ready": True, "model_loaded": True}, catalog, "fixture")
        with self.assertRaises(ValueError):
            rapid.validate_ready({"ready": True, "model_loaded": True}, catalog, "other")

    def test_inherited_runtime_and_python_overrides_are_cleared(self):
        self.assertEqual(rapid.clean_environment({"PATH": "fixture", "RAPID_MLX_API_KEY": "old",
            "RAPID_MLX_MAX_GENERATION_TOKENS": "9999", "DYLD_INSERT_LIBRARIES": "old", "PYTHONPATH": "old"}),
            {"PATH": "fixture"})

    def test_trained_mtp_head_enables_native_config_and_rebinds_sidecar(self):
        from tests.test_rapidmlx_mtp import head_keys, safetensors
        config_path = self.model_root / "config.json"
        config = json.loads(config_path.read_text())
        config["text_config"]["mtp_num_hidden_layers"] = 1
        config_path.write_text(json.dumps(config))
        head = self.model_root / "mtp/model.safetensors"
        safetensors(head, head_keys())
        cap = rapid.capability(self.model, self.runtime)
        self.assertTrue(cap["mtp"], cap["mtpReason"])
        self.assertEqual(cap["preferredAcceleration"], "mtp")
        model = rapid.inspect_model(self.model_root)
        argv = rapid.server_arguments(self.runtime, model, port=18081, served_id="fixture",
            context=32768, output=4096, reasoning="auto", options={"acceleration": "mtp", "depth": 3})
        specification = json.loads(argv[argv.index("--speculative-config") + 1])
        self.assertEqual(specification, {"method": "mtp", "model": str(head), "num_speculative_tokens": 3,
            "disable_auto_k": False})
        self.assertNotIn("--no-spec-decode", argv)
        self.assertNotIn("--mtp-optimistic", argv)
        self.assertGreater(cap["mtpSidecarBytes"], 0)
        head.write_bytes(head.read_bytes()[:-1])
        with self.assertRaisesRegex(ValueError, "changed after scanning"):
            rapid.validate_route(str(self.binary), self.model, cap, 32768, 4096)

    def test_flash_next_mlx_is_not_locked_to_another_engine(self):
        from tests.test_rapidmlx_mtp import head_keys, safetensors
        config_path = self.model_root / "config.json"
        config_path.write_text(json.dumps({"model_type": "qwen4_exp",
            "text_config": {"max_position_embeddings": 262144, "mtp_num_hidden_layers": 1}}))
        safetensors(self.model_root / "model.safetensors", head_keys("qwen4_exp", "mtp."))
        runtime = {**self.runtime, "modelTypes": [*self.runtime["modelTypes"], "qwen4_exp"]}
        cap = rapid.capability({**self.model, "format": "Slotstream MLX 4-bit + SSD"}, runtime)
        self.assertTrue(cap["runnable"], cap["reason"])
        self.assertTrue(cap["mtp"])
        self.assertEqual(cap["depthChoices"], [1, 2])

    def test_installed_native_cli_parser_accepts_complete_ar_and_mtp_commands(self):
        installed = rapid.inspect_runtime(Path.home() / "Library/Application Support/LLM Launcher/runtimes/rapidmlx-0.16.9/bin/rapid-mlx")
        if not installed or not installed.get("ready"):
            self.skipTest("Optional installed Rapid MLX parser is unavailable")
        model = rapid.inspect_model(self.model_root)
        model["mtp"] = {"supported": True, "sidecarPath": str(self.model_root / "mtp/model.safetensors"),
                        "depth": 3, "depthMax": 6, "depthChoices": [1, 2, 3, 4, 5, 6]}
        source = "import json,sys; from rapid_mlx.cli_parser import build_parser; build_parser().parse_args(json.load(sys.stdin))"
        for acceleration in ("off", "mtp"):
            argv = rapid.server_arguments(installed, model, port=18081, served_id="fixture", context=32768,
                output=4096, reasoning="auto", options={"acceleration": acceleration, "depth": 3})
            result = subprocess.run([installed["python"], "-I", "-c", source], input=json.dumps(argv[1:]),
                text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
