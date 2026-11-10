"""Production normalizer validates before IO and preserves native plan outputs."""
import copy
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import launcher


class NormalizedContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.model_path = self.root / "model"
        self.model_path.mkdir()
        self.model = {"id": "fixture", "name": "Exact fixture", "path": str(self.model_path), "nativeContext": 131072,
                      "defaultOutput": 1024, "defaultSampling": {"temperature": 0.7, "top_p": 0.9, "seed": 17},
                      "templateReasoningEfforts": ["medium"], "backends": {
            backend: {"runnable": True, "mtp": True, "dflash": True, "kv": True, "depth": 2, "depthMax": 4,
                      "agentReasoning": ["auto", "off", "medium"], "customSampling": True}
            for backend in launcher.ENGINE_ADAPTERS if backend not in {"rec", "strata", "rapidmlx"}}}
        self.payload = {"backend": "omlx", "client": "chat", "modelId": "fixture", "project": str(self.root),
                        "context": 8192, "output": 256, "reasoning": "off", "options": {"acceleration": "off", "kv": "off"}}

    def patches(self, *, ports=True):
        stack = ExitStack()
        stack.enter_context(mock.patch.dict(launcher.BINARIES, {key: f"/fixture/{key}" for key in ("omlx", "mtplx", "splash", "kolibri", "lms", "whallm", "pi")}))
        stack.enter_context(mock.patch.object(launcher, "RUNS_DIR", self.root / "runs"))
        stack.enter_context(mock.patch.object(launcher, "STATE_DIR", self.root / "state"))
        stack.enter_context(mock.patch.object(launcher, "omlx_expert_offload_options", return_value=None))
        if ports:
            stack.enter_context(mock.patch.object(launcher, "free_port", side_effect=[18765, 18766]))
            stack.enter_context(mock.patch.object(launcher.uuid, "uuid4", return_value="11111111-1111-4111-8111-111111111111"))
            stack.enter_context(mock.patch.object(launcher.secrets, "token_urlsafe", return_value="fixed-test-key"))
            stack.enter_context(mock.patch.object(launcher.secrets, "token_hex", return_value="fixed-test-hex"))
        return stack

    def forbid_allocation(self):
        stack = ExitStack()
        for owner, name in ((launcher, "free_port"), (launcher.uuid, "uuid4"), (launcher.secrets, "token_urlsafe"),
                            (launcher.secrets, "token_hex"), (launcher, "atomic_json"), (Path, "mkdir"), (Path, "symlink_to")):
            stack.enter_context(mock.patch.object(owner, name, side_effect=AssertionError("Request rejected after materialization")))
        return stack

    def test_production_invalid_omlx_options_and_current_artifact_fail_before_allocation(self):
        with self.patches(ports=False), self.forbid_allocation():
            for options, error in (({"acceleration": "bad"}, "acceleration"), ({"kv": "bad"}, "KV"),
                                   ({"anePrefill": "bad"}, "ANE"), ({"burst": "bad"}, "burst")):
                with self.subTest(options=options), self.assertRaisesRegex(ValueError, error):
                    launcher.normalized_request({**self.payload, "options": options}, [self.model])
            with mock.patch.object(launcher, "dflash2_capability_valid", return_value=False):
                with self.assertRaisesRegex(ValueError, "DFlash"):
                    launcher.normalized_request({**self.payload, "options": {"acceleration": "dflash"}}, [self.model])

    def test_unmeasured_operator_and_exact_native_qualification_fail_before_allocation(self):
        with self.patches(ports=False), self.forbid_allocation(), mock.patch.object(launcher, "optimizer_evidence", return_value={}), \
                mock.patch.object(launcher, "add_benchmark_engine_evidence"), \
                mock.patch.object(launcher, "verified_mtplx_operator_candidate_record", return_value=None), \
                mock.patch.object(launcher, "_uzu_qualified_session_record", return_value=None), \
                mock.patch.object(launcher, "verified_route_qualification", return_value=None), \
                mock.patch.dict(launcher.BINARIES, {"mirai": "/fixture/mirai", "llamacpp": "/fixture/llamacpp"}):
            with self.assertRaisesRegex(ValueError, "Calibration"):
                launcher.normalized_request({**self.payload, "backend": "mtplx", "context": 65536,
                    "options": {"acceleration": "mtp", "profile": "turbo", "mtplxOperatorRoute": launcher.MTPLX_LONG_CONTEXT_2111_ROUTE}}, [self.model])
            for backend, context in (("uzu", 16384), ("llamacpp", 8192)):
                with self.subTest(backend=backend), self.assertRaisesRegex(ValueError, "fresh successful local qualification"):
                    launcher.normalized_request({**self.payload, "backend": backend, "context": context}, [self.model])

    def test_positive_omlx_and_mtplx_actual_builder_outputs_keep_settings_and_limits(self):
        for backend in ("omlx", "mtplx"):
            with self.subTest(backend=backend), self.patches(), mock.patch.object(launcher, "preserved_qwopus_template", return_value=None):
                plan = launcher.normalized_request({**self.payload, "backend": backend}, [self.model])
            self.assertEqual((plan.context, plan.output, plan.reasoning), (8192, 256, "off"))
            self.assertEqual(plan.options["kv"], "off")
            self.assertEqual(plan.agent_host, "launcher")
            self.assertEqual(plan.client_argv, [])
            if backend == "omlx":
                settings = json.loads((plan.run_dir / "omlx/settings.json").read_text())
                self.assertEqual(settings["sampling"], {"max_context_window": 8192, "max_context_window_policy": 8192, "max_tokens": 256})
                self.assertEqual(plan.engine_argv[-4:], ["--port", "18765", "--max-concurrent-requests", "1"])
                self.assertTrue((plan.run_dir / "omlx/models").is_dir())
            else:
                self.assertIn("--no-mtp", plan.engine_argv)
                self.assertEqual(plan.engine_argv[plan.engine_argv.index("--context-window") + 1], "8192")
                self.assertEqual(plan.engine_argv[plan.engine_argv.index("--max-tokens") + 1], "256")
                self.assertEqual(plan.engine_env["MTPLX_ALLOW_SWAP"], "0")
                self.assertEqual((plan.run_dir / "mtplx-api-key").stat().st_mode & 0o777, 0o600)

    def test_complete_native_plan_and_config_output_matches_frozen_original_normalizer(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/native-launch-plan-v1.json").read_text())
        keys = ("backend", "client", "model", "project", "context", "output", "reasoning", "port", "mode", "options",
                "agent_host", "purpose", "runtime_binary", "client_port", "pi_session_file", "sampling_contract",
                "sampling_enforcement", "chat", "engine_argv", "engine_env", "client_argv", "client_env", "warnings", "secrets")
        for case in fixture["cases"]:
            backend = case["backend"]
            selected = copy.deepcopy(self.model)
            runtime, native = {"identity": "runtime"}, {"identity": "model"}
            selected["kolibri"] = native
            selected["backends"]["kolibri"]["runtimeIdentity"] = runtime
            selected["splash"] = {"identity": "pack", "id": "owner/repo", "draftCandidates": []}
            with self.patches(), mock.patch.object(launcher, "preserved_qwopus_template", return_value=None), \
                    mock.patch.object(launcher.kolibri_runtime, "inspect_runtime", return_value=runtime), \
                    mock.patch.object(launcher.kolibri_runtime, "inspect_model", return_value=native), \
                    mock.patch.object(launcher.kolibri_runtime, "current_resource", return_value={}), \
                    mock.patch.object(launcher.kolibri_runtime, "memory_plan", return_value={"ready": True, "expertCacheBytes": 1024, "residentExpertsPerLayer": 1}), \
                    mock.patch.object(launcher.splash_runtime, "inspect_install", return_value={"ready": True}), \
                    mock.patch.object(launcher.splash_runtime, "inspect_model", return_value=selected["splash"]):
                plan = launcher.normalized_request({**self.payload, "backend": backend,
                    "context": 16384 if backend == "splash" else 8192}, [selected])
            actual = {key: copy.deepcopy(getattr(plan, key)) for key in keys}
            if actual["engine_argv"] and actual["engine_argv"][0] == sys.executable:
                actual["engine_argv"][0] = "PYTHON"
            files = {}
            for path in plan.run_dir.rglob("*"):
                relative = str(path.relative_to(plan.run_dir))
                relevant = relative.startswith("omlx/") if backend == "omlx" else path.name == "mtplx-api-key" if backend == "mtplx" else path.name == backend + ".json"
                if relevant and path.is_file() and not path.is_symlink():
                    files[relative] = {"mode": path.stat().st_mode & 0o777, "text": path.read_text()}
            actual["files"] = files
            normalized = json.loads(json.dumps(actual, ensure_ascii=False).replace(str(self.root), "ROOT").replace(str(launcher.APP_DIR), "APP_DIR"))
            with self.subTest(backend=backend):
                self.assertEqual(normalized, case["expected"])

    def test_positive_kolibri_and_splash_actual_configs_preserve_exact_native_choices(self):
        runtime, model = {"identity": "runtime"}, {"identity": "model"}
        for backend in ("kolibri", "splash"):
            selected = copy.deepcopy(self.model)
            selected["kolibri"] = model
            selected["splash"] = {"identity": "pack", "id": "owner/repo", "draftCandidates": []}
            selected["backends"]["kolibri"]["runtimeIdentity"] = runtime
            with self.subTest(backend=backend), self.patches(), \
                    mock.patch.object(launcher.kolibri_runtime, "inspect_runtime", return_value=runtime), \
                    mock.patch.object(launcher.kolibri_runtime, "inspect_model", return_value=model), \
                    mock.patch.object(launcher.kolibri_runtime, "current_resource", return_value={}), \
                    mock.patch.object(launcher.kolibri_runtime, "memory_plan", return_value={"ready": True, "expertCacheBytes": 1024, "residentExpertsPerLayer": 1}), \
                    mock.patch.object(launcher.splash_runtime, "inspect_install", return_value={"ready": True}), \
                    mock.patch.object(launcher.splash_runtime, "inspect_model", return_value=selected["splash"]):
                context = 16384 if backend == "splash" else 8192
                plan = launcher.normalized_request({**self.payload, "backend": backend, "context": context}, [selected])
            config = json.loads((plan.run_dir / f"{backend}.json").read_text())
            self.assertEqual((config["context"], config["output"]), (context, 256))
            self.assertEqual(plan.options["kv"], "off")
            self.assertIn(str(plan.run_dir / f"{backend}.json"), plan.engine_argv)
            self.assertEqual(plan.model["servedId"], launcher.kolibri_runtime.MODEL_ID if backend == "kolibri" else "owner/repo")

    def test_native_whallm_forbidden_port_rejected_before_allocation_and_auto_excludes_it(self):
        selected = copy.deepcopy(self.model)
        install = {"artifactIdentity": "abcdef", "python": "/fixture/python", "app": "/fixture/app"}
        selected["nativeWhallm"] = install
        selected["backends"]["whallm"]["nativeWhallm"] = True
        payload = {**self.payload, "backend": "whallm", "context": 16384, "reasoning": "medium", "port": 11434}
        with self.patches(ports=False), self.forbid_allocation(), \
                mock.patch.object(launcher.whallm_runtime, "inspect_install", return_value=install), \
                mock.patch.object(launcher, "whallm_qualification_conflict", return_value=None):
            with self.assertRaisesRegex(ValueError, "private launcher port"):
                launcher.normalized_request(payload, [selected])
        with self.patches(), mock.patch.object(launcher.whallm_runtime, "inspect_install", return_value=install), \
                mock.patch.object(launcher, "whallm_qualification_conflict", return_value=None), \
                mock.patch.object(launcher.whallm_runtime, "launch_config", return_value={"context": 16384, "output": 256}) as config, \
                mock.patch.object(launcher, "free_port", side_effect=[18765, 18766]) as ports:
            plan = launcher.normalized_request({**payload, "port": None}, [selected])
            self.assertEqual(ports.call_args_list[0], mock.call(None, exclude={11434}))
            config.assert_called_once()
            self.assertEqual(plan.context, 16384)
            self.assertIn(str(plan.run_dir / "whallm-owned.json"), plan.engine_argv)

    def test_materializer_uses_detached_payload_port_and_preserves_build_recheck(self):
        original = {**self.payload, "port": 18765}
        actual = launcher.LaunchArtifactChecks.require_current
        def check(owner, request, options, purpose):
            original["port"] = 19999
            return actual(owner, request, options, purpose)
        with self.patches(), mock.patch.object(launcher.LaunchArtifactChecks, "require_current", check), \
                mock.patch.object(launcher, "free_port", side_effect=[18765, 18766]) as ports, \
                mock.patch.object(launcher.engine_planning.EnginePlanner, "_prepare_omlx_engine", autospec=True,
                    side_effect=launcher.engine_planning.EnginePlanner._prepare_omlx_engine) as prepare:
            launcher.normalized_request(original, [self.model])
            self.assertEqual(ports.call_args_list[0], mock.call(18765))
            self.assertEqual(prepare.call_count, 2, "Validation cannot replace the fresh engine-build recheck")


if __name__ == "__main__": unittest.main()
