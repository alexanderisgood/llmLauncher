import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import omp_runtime
import launcher


class OMPAdapterTests(unittest.TestCase):
    def contract(self, **changes):
        values = dict(provider="launcher-splash-artifact", served="owner/qwen", name="Qwen fixture",
                      base_url="http://127.0.0.1:18090/v1", api_key="fixture-key", backend="splash",
                      context=131072, output=8192, reasoning="low",
                      allowed_reasoning=["auto", "off", "low", "medium", "high"], inputs=["text"])
        return omp_runtime.provider_contract(**{**values, **changes})

    def test_explicit_transport_and_reasoning_history_contract(self):
        data = self.contract()
        self.assertEqual(data["models"][0]["id"], "owner/qwen")
        self.assertEqual(data["api"], "openai-completions")
        compat = data["models"][0]["compat"]
        self.assertTrue(compat["requiresReasoningContentForAllAssistantTurns"])
        self.assertFalse(compat["allowsSyntheticReasoningContentForToolCalls"])
        self.assertFalse(compat["supportsReasoningParams"])
        self.assertEqual(data["models"][0]["thinking"]["efforts"], ["low", "medium", "high"])

    def test_model_default_and_off_do_not_invent_effort(self):
        self.assertNotIn("thinking", self.contract(reasoning="auto", allowed_reasoning=["auto"])["models"][0])
        model = self.contract(reasoning="off")["models"][0]
        self.assertFalse(model["reasoning"])
        self.assertNotIn("thinking", model)

    def test_mtplx_routes_keep_one_stable_session_prefix(self):
        self.assertEqual(self.contract(backend="mtplx", session_id="session-fixture")["headers"],
                         {"x-mtplx-client": "pi", "x-mtplx-session-id": "session-fixture"})
        self.assertEqual(self.contract(backend="kolibri")["headers"], {})

    def test_all_helper_roles_and_retries_stay_on_selected_model(self):
        settings = omp_runtime.settings_overlay("launcher-splash-artifact", "owner/qwen")
        self.assertEqual(set(settings["modelRoles"].values()), {"launcher-splash-artifact/owner/qwen"})
        self.assertFalse(settings["retry"]["modelFallback"])
        self.assertFalse(settings["contextPromotion"]["enabled"])
        self.assertTrue(all(not chain for chain in settings["retry"]["fallbackChains"].values()))

    def test_overlay_is_private_and_cannot_follow_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = omp_runtime.write_overlay(root, {"modelRoles": {"default": "fixture"}})
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(json.loads(path.read_text())["modelRoles"]["default"], "fixture")
            path.unlink()
            target = root / "other.json"
            target.write_text("untouched")
            path.symlink_to(target)
            with self.assertRaises(OSError):
                omp_runtime.write_overlay(root, {})
            self.assertEqual(target.read_text(), "untouched")

    def test_build_preserves_limits_and_never_exposes_key_in_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = SimpleNamespace(agent_host="terminal", run_dir=Path(tmp), run_id="session-fixture",
                backend="kolibri", model={"name":"Kolibri fixture", "backends":{"kolibri":{"agentReasoning":["off","low","medium","high"]}}},
                context=262144, output=65536, reasoning="off", client_env={}, warnings=[])
            route = SimpleNamespace(served="kolibri-fixture", base_url="http://127.0.0.1:18090/v1", api_key="private-fixture-key")
            omp_runtime.build_client(plan, route, binary="/fixture/omp", app_dir=Path("/fixture/app"), provider="launcher-kolibri-fixture", inputs=["text"])
            data = json.loads(plan.client_env["LLM_LAUNCHER_OMP_PROVIDER"])
            self.assertEqual((data["models"][0]["contextWindow"], data["models"][0]["maxTokens"]), (262144,65536))
            self.assertNotIn("private-fixture-key", " ".join(plan.client_argv))
            self.assertIn("--config", plan.client_argv)
            self.assertNotIn("--provider", plan.client_argv)
            self.assertEqual(plan.client_argv[plan.client_argv.index("--model") + 1],
                             "launcher-kolibri-fixture/kolibri-fixture")
            for variable in ("PI_SMOL_MODEL", "PI_SLOW_MODEL", "PI_PLAN_MODEL"):
                self.assertEqual(plan.client_env[variable], "launcher-kolibri-fixture/kolibri-fixture")
            self.assertEqual(plan.client_argv[-2:], ["--thinking","off"])
            plan.agent_host = "console"
            with self.assertRaisesRegex(ValueError, "Terminal"):
                omp_runtime.build_client(plan,route,binary="/fixture/omp",app_dir=Path("/fixture/app"),provider="launcher-kolibri-fixture",inputs=["text"])

    def test_registry_covers_omp_without_reusing_uzu_pi_qualification(self):
        launcher.validate_adapter_registries()
        for backend in ("splash", "kolibri", "omlx", "mtplx"):
            self.assertTrue(launcher.CLIENT_SUPPORT[backend]["omp"]["supported"])
        self.assertFalse(launcher.CLIENT_SUPPORT["uzu"]["omp"]["supported"])

    def test_console_host_is_rejected_before_allocating_port_or_scan(self):
        from unittest import mock
        with mock.patch.object(launcher, "command_version", return_value="18.6.2"), \
                mock.patch.object(launcher, "free_port", side_effect=AssertionError("port allocated")):
            with self.assertRaisesRegex(ValueError, "Terminal"):
                launcher.normalized_request({"backend":"splash", "client":"omp", "agentHost":"console"}, [])

    def test_native_console_requires_exact_qualified_release(self):
        from unittest import mock
        for version in ("18.6.3", "omp/18.6.3"):
            self.assertTrue(omp_runtime.console_supported(version))
            with mock.patch.object(launcher, "command_version", return_value=version):
                launcher._require_omp_console_support("omp", "console")
        for version in (None, "", "omp/18.6.2", "omp/18.6.4", "18.6.3-custom", "Unverified"):
            self.assertFalse(omp_runtime.console_supported(version))
            with mock.patch.object(launcher, "command_version", return_value=version):
                with self.assertRaisesRegex(ValueError, "Terminal"):
                    launcher._require_omp_console_support("omp", "console")
                launcher._require_omp_console_support("omp", "terminal")

    def test_verified_console_keeps_exact_private_route_and_uses_native_rpc(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = SimpleNamespace(agent_host="console", run_dir=Path(tmp), run_id="console-fixture",
                backend="splash", model={"name":"Synthetic Qwen", "backends":{"splash":{"agentReasoning":["off","low"]}}},
                context=8192, output=512, reasoning="off", client_env={}, warnings=[])
            route = SimpleNamespace(served="qwen-fixture", base_url="http://127.0.0.1:18090/v1", api_key="console-private-fixture")
            omp_runtime.build_client(plan, route, binary="/fixture/omp", app_dir=Path("/fixture/app"),
                provider="launcher-splash-fixture", inputs=["text"], console_verified=True)
            self.assertEqual(plan.client_argv[-4:], ["--thinking", "off", "--mode", "rpc"])
            self.assertNotIn("console-private-fixture", " ".join(plan.client_argv))
            contract = json.loads(plan.client_env["LLM_LAUNCHER_OMP_PROVIDER"])
            self.assertEqual((contract["models"][0]["id"], contract["models"][0]["contextWindow"],
                contract["models"][0]["maxTokens"]), ("qwen-fixture",8192,512))
            self.assertIn("Hub Console", plan.warnings[0])


if __name__ == "__main__":
    unittest.main()
