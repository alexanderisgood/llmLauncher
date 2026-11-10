from __future__ import annotations

import copy
import importlib.util
import math
import os
import re
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "llm_launcher_mtplx_2111_long_context_tests", ROOT / "launcher.py",
)
assert SPEC and SPEC.loader
launcher = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = launcher
SPEC.loader.exec_module(launcher)


ROUTE_DEFAULT = "default"
ROUTE_LONG_CONTEXT = "dense-27b-long-context-2111"
MINIMUM_CONTEXT = 65_536
NEAR_TIER_PROMPT = 61_440
MINIMUM_NEAR_TIER_PROMPT = math.ceil(MINIMUM_CONTEXT * 0.90)
CONTEXT_OPERATOR_KEYS = {
    "MTPLX_CONTEXT_COPY",
    "MTPLX_LAZY_TARGET_DISTRIBUTIONS",
    "MTPLX_BATCH_TARGET_ARRAYS",
}
CANDIDATE_ENVIRONMENT = {
    "MTPLX_CONTEXT_COPY": "0",
    "MTPLX_LAZY_TARGET_DISTRIBUTIONS": "0",
    "MTPLX_BATCH_TARGET_ARRAYS": "1",
}
BASELINE_ENVIRONMENT = {
    "MTPLX_CONTEXT_COPY": "1",
    "MTPLX_LAZY_TARGET_DISTRIBUTIONS": "1",
    "MTPLX_BATCH_TARGET_ARRAYS": "0",
}
GROWTH_RESERVE = "MTPLX_COMPILED_VERIFY_GROWTH_RESERVE"


class MTPLX2111LongContextContractTests(unittest.TestCase):
    """Model-free contract tests for the audited 2.11.1 dense-27B route."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="mtplx-2111-contract-")
        self.root = Path(self.temp.name)
        self.model_path = self.root / "Qwen3.8-27B-MLX-6bit"
        self.model_path.mkdir(parents=True)
        self.model_config = {
            "model_type": "qwen3_5",
            "text_config": {
                "model_type": "qwen3_5_text",
                "num_hidden_layers": 64,
                "vocab_size": 248_320,
                "hidden_size": 5_120,
                "intermediate_size": 17_408,
            },
        }
        launcher.atomic_json(self.model_path / "config.json", self.model_config)
        self.runtime_version = "mtplx 2.11.1 (2.11.1)"
        self.model_fingerprint = launcher.model_artifact_fingerprint(
            self.model_path, self.model_config,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def dense_27b_model(self) -> dict:
        capability = {
            "runnable": True,
            "reason": "Verified MTPLX runtime and model artifact",
            "runtimeVersion": self.runtime_version,
            "benchmarkModelFingerprint": self.model_fingerprint,
            "mtp": True,
            "mtpReason": "Verified integrated MTP tensors",
            "kv": True,
            "profile": "turbo",
            "depth": 3,
            "depthMax": 3,
            "contextMaximum": 262_144,
            "contextWindows": [16_384, 32_768, 65_536, 131_072, 262_144],
            "agentReasoning": ["auto", "off", "low", "medium", "high", "xhigh"],
            "implicitSamplingDefaultsVerified": True,
            "localBenchmarks": [],
        }
        return {
            "id": "qwen38-dense-27b",
            "name": "Qwen3.8-27B-MLX-6bit",
            "path": str(self.model_path),
            "artifact": str(self.model_path),
            "format": "mlx",
            "architecture": "Qwen3_8ForConditionalGeneration",
            "modelType": "qwen3_8",
            "parameterCount": 27_000_000_000,
            "mixtureOfExperts": False,
            "nativeContext": 262_144,
            "quantization": "6-bit",
            "ready": True,
            "defaultSampling": {
                "temperature": 1.0, "top_p": 0.95, "top_k": 20,
            },
            "backends": {"mtplx": capability},
        }

    def flash_next_model(self) -> dict:
        model = self.dense_27b_model()
        model.update({
            "id": "qwen38-flash-next",
            "name": "Qwen3.8-Flash-Next-MLX-4bit",
            "architecture": "Qwen3_8FlashNextForConditionalGeneration",
            "modelType": "qwen3_8_flash_next_moe",
            "parameterCount": 35_000_000_000,
            "mixtureOfExperts": True,
        })
        return model

    def launch_plan(
        self,
        model: dict,
        *,
        context: int = MINIMUM_CONTEXT,
        route: str = ROUTE_DEFAULT,
        contract_id: str | None = None,
        profile: str = "turbo",
        acceleration: str = "mtp",
        run_name: str = "run",
    ) -> launcher.LaunchPlan:
        run_dir = self.root / run_name
        run_dir.mkdir(parents=True, exist_ok=True)
        options = {
            "acceleration": acceleration,
            "depth": 3,
            "kv": "off",
            "profile": profile,
            "fan": "default",
            "mtplxOperatorRoute": route,
        }
        if contract_id is not None:
            options["_mtplxOperatorContractId"] = contract_id
        return launcher.LaunchPlan(
            run_id=run_name,
            backend="mtplx",
            client="chat",
            model=model,
            project=str(self.root),
            context=context,
            output=1_024,
            reasoning="auto",
            port=18_080,
            mode="custom",
            options=options,
            purpose="benchmark",
            run_dir=run_dir,
        )

    def required_callable(self, name: str):
        value = getattr(launcher, name, None)
        self.assertTrue(
            callable(value),
            f"expected-red: launcher.{name} must implement the MTPLX 2.11.1 contract",
        )
        return value

    def mint_contract(self, model: dict | None = None) -> dict:
        target = model or self.dense_27b_model()
        capability = target["backends"]["mtplx"]
        helper = self.required_callable("mtplx_long_context_2111_contract")
        receipt = helper(target, capability, runtime_version=self.runtime_version)
        self.assertIsInstance(receipt, dict)
        return receipt

    @staticmethod
    def context_operator_environment(plan: launcher.LaunchPlan) -> dict[str, str]:
        return {
            key: value for key, value in plan.engine_env.items()
            if key in CONTEXT_OPERATOR_KEYS
        }

    def build(self, plan: launcher.LaunchPlan) -> None:
        with mock.patch.dict(launcher.BINARIES, {"mtplx": "/usr/bin/true"}):
            launcher.build_mtplx(plan, plan.model["backends"]["mtplx"])

    def test_existing_2111_foundation_keeps_swap_off_and_growth_reserve_unset(self) -> None:
        release = launcher.audited_runtime_release("mtplx", self.runtime_version)
        self.assertTrue(release["updateAvailable"])
        self.assertEqual(release["version"], "2.11.2")

        model = self.dense_27b_model()
        plan = self.launch_plan(
            model, context=32_768, acceleration="auto", run_name="ordinary",
        )
        self.build(plan)
        self.assertEqual(plan.engine_env["MTPLX_ALLOW_SWAP"], "0")
        self.assertNotIn(GROWTH_RESERVE, plan.engine_env)
        self.assertEqual(self.context_operator_environment(plan), {})

    def test_compiled_verify_fence_covers_the_selected_window(self) -> None:
        """The turbo profile pins compiled verify at 32,768 tokens; long
        windows must lift the fence or every verify round runs eager (measured
        4.56 -> 10.05 decode tok/s at a 112,881-token prompt on 17 Sep 2026)."""
        model = self.dense_27b_model()
        short = self.launch_plan(
            model,
            context=launcher.MTPLX_COMPILED_VERIFY_PROFILE_FENCE,
            acceleration="auto",
            run_name="short",
        )
        self.build(short)
        self.assertNotIn("MTPLX_COMPILED_VERIFY_MAX_CONTEXT", short.engine_env)

        long = self.launch_plan(
            model, context=131_072, acceleration="auto", run_name="long",
        )
        self.build(long)
        self.assertEqual(
            long.engine_env["MTPLX_COMPILED_VERIFY_MAX_CONTEXT"], "131072",
        )

    def test_child_environment_cannot_inherit_swap_or_growth_reserve_overrides(self) -> None:
        """The effective Popen environment, not just LaunchPlan, owns this safety rule."""
        model = self.dense_27b_model()
        plan = self.launch_plan(
            model, context=32_768, acceleration="auto", run_name="child-env",
        )
        self.build(plan)
        manager = launcher.RunManager()
        cancel_event = threading.Event()
        manager.plan = plan
        manager.cancel_event = cancel_event
        manager.state = {"phase": "queued", "events": []}
        child = mock.Mock()
        child.pid = 12_345
        child.poll.return_value = None

        inherited = {
            "MTPLX_ALLOW_SWAP": "1",
            GROWTH_RESERVE: str(8 * 1024**3),
        }
        with (
            mock.patch.dict(os.environ, inherited, clear=False),
            mock.patch.object(launcher.subprocess, "Popen", return_value=child) as popen,
            mock.patch.object(manager, "_wait_ready"),
            mock.patch.object(manager, "_verify_lmstudio_reasoning"),
            mock.patch.object(manager, "_verify_client_api"),
            mock.patch.object(manager, "_monitor_run"),
        ):
            manager._worker(plan, cancel_event)

        child_env = popen.call_args.kwargs["env"]
        self.assertEqual(child_env["MTPLX_ALLOW_SWAP"], "0")
        self.assertNotIn(GROWTH_RESERVE, child_env)

    def test_static_receipt_binds_exact_dense_27b_runtime_geometry_and_route(self) -> None:
        model = self.dense_27b_model()
        receipt = self.mint_contract(model)

        self.assertEqual(receipt["version"], 1)
        self.assertEqual(receipt["backend"], "mtplx")
        self.assertEqual(receipt["route"], ROUTE_LONG_CONTEXT)
        self.assertEqual(receipt["runtimeVersion"], self.runtime_version)
        self.assertEqual(receipt["modelFingerprint"], self.model_fingerprint)
        self.assertEqual(receipt["minimumContext"], MINIMUM_CONTEXT)
        self.assertEqual(receipt["requiredProfile"], "turbo")
        self.assertEqual(receipt["requiredAcceleration"], "mtp")
        self.assertEqual(receipt["environment"], CANDIDATE_ENVIRONMENT)
        self.assertEqual(receipt["baselineEnvironment"], BASELINE_ENVIRONMENT)
        self.assertEqual(receipt["allowSwap"], "0")
        self.assertEqual(receipt["growthReserve"], "absent")
        self.assertRegex(str(receipt["contractId"]), r"^[0-9a-f]{16,64}$")
        self.assertEqual(
            receipt,
            self.required_callable("mtplx_long_context_2111_contract")(
                copy.deepcopy(model),
                copy.deepcopy(model["backends"]["mtplx"]),
                runtime_version=self.runtime_version,
            ),
            "the scanner receipt must be deterministic for one exact artifact/runtime",
        )

    def test_candidate_route_applies_only_the_audited_operator_trio(self) -> None:
        model = self.dense_27b_model()
        capability = model["backends"]["mtplx"]
        receipt = self.mint_contract(model)
        capability["longContext2111"] = copy.deepcopy(receipt)
        plan = self.launch_plan(
            model,
            route=ROUTE_LONG_CONTEXT,
            contract_id=receipt["contractId"],
            run_name="candidate",
        )

        validator = self.required_callable("validated_mtplx_operator_route")
        self.assertEqual(validator(plan, capability), ROUTE_LONG_CONTEXT)
        self.build(plan)
        self.assertEqual(self.context_operator_environment(plan), CANDIDATE_ENVIRONMENT)
        self.assertEqual(plan.engine_env["MTPLX_ALLOW_SWAP"], "0")
        self.assertNotIn(GROWTH_RESERVE, plan.engine_env)

        public_options = plan.public()["options"]
        self.assertEqual(public_options["mtplxOperatorRoute"], ROUTE_LONG_CONTEXT)
        self.assertNotIn("_mtplxOperatorContractId", public_options)

    def test_default_dense_route_is_the_isolated_inverse_baseline(self) -> None:
        model = self.dense_27b_model()
        capability = model["backends"]["mtplx"]
        capability["longContext2111"] = self.mint_contract(model)
        plan = self.launch_plan(model, route=ROUTE_DEFAULT, run_name="baseline")

        validator = self.required_callable("validated_mtplx_operator_route")
        self.assertEqual(validator(plan, capability), ROUTE_DEFAULT)
        self.build(plan)
        self.assertEqual(self.context_operator_environment(plan), BASELINE_ENVIRONMENT)
        self.assertEqual(plan.engine_env["MTPLX_ALLOW_SWAP"], "0")
        self.assertNotIn(GROWTH_RESERVE, plan.engine_env)

    def test_flash_next_is_never_inverse_pinned_or_eligible_for_dense_route(self) -> None:
        model = self.flash_next_model()
        capability = model["backends"]["mtplx"]
        default_plan = self.launch_plan(model, route=ROUTE_DEFAULT, run_name="flash-default")
        self.build(default_plan)
        self.assertEqual(self.context_operator_environment(default_plan), {})
        self.assertEqual(default_plan.engine_env["MTPLX_ALLOW_SWAP"], "0")
        self.assertNotIn(GROWTH_RESERVE, default_plan.engine_env)

        helper = self.required_callable("mtplx_long_context_2111_contract")
        self.assertIsNone(
            helper(model, capability, runtime_version=self.runtime_version),
            "Flash-Next owns different 2.11.1 defaults and must not mint the dense receipt",
        )
        forged_plan = self.launch_plan(
            model,
            route=ROUTE_LONG_CONTEXT,
            contract_id="f" * 24,
            run_name="flash-forged",
        )
        with self.assertRaises(ValueError):
            self.required_callable("validated_mtplx_operator_route")(
                forged_plan, capability,
            )

    def test_contract_and_launch_fail_closed_on_every_eligibility_binding(self) -> None:
        helper = self.required_callable("mtplx_long_context_2111_contract")

        for version in (
            "mtplx 2.11.0",
            "mtplx 2.11.2",
            "mtplx 2.11.1-beta",
            "mtplx 2.11.1-dev1",
            "mtplx 2.11.1+local",
        ):
            model = self.dense_27b_model()
            with self.subTest(static="runtime", value=version):
                self.assertIsNone(
                    helper(model, model["backends"]["mtplx"], runtime_version=version),
                )

        wrong_model = self.dense_27b_model()
        wrong_model.update({
            "name": "Qwen3.8-35B-A3B-MLX-4bit",
            "parameterCount": 35_000_000_000,
            "mixtureOfExperts": True,
            "modelType": "qwen3_8_moe",
            "architecture": "Qwen3_8MoeForConditionalGeneration",
        })
        self.assertIsNone(
            helper(
                wrong_model, wrong_model["backends"]["mtplx"],
                runtime_version=self.runtime_version,
            ),
        )

        short_model = self.dense_27b_model()
        short_capability = short_model["backends"]["mtplx"]
        short_capability.update({
            "contextMaximum": 32_768,
            "contextWindows": [16_384, 32_768],
        })
        self.assertIsNone(
            helper(short_model, short_capability, runtime_version=self.runtime_version),
        )

        base_model = self.dense_27b_model()
        receipt = self.mint_contract(base_model)
        validator = self.required_callable("validated_mtplx_operator_route")

        cases = []
        missing_receipt = self.dense_27b_model()
        cases.append(("missing receipt", missing_receipt, {}))

        wrong_runtime = self.dense_27b_model()
        wrong_runtime_cap = wrong_runtime["backends"]["mtplx"]
        wrong_runtime_cap["longContext2111"] = copy.deepcopy(receipt)
        wrong_runtime_cap["runtimeVersion"] = "mtplx 2.11.2 (2.11.2)"
        cases.append(("runtime changed", wrong_runtime, {}))

        tampered_receipt = self.dense_27b_model()
        tampered = copy.deepcopy(receipt)
        tampered["environment"]["MTPLX_CONTEXT_COPY"] = "1"
        tampered_receipt["backends"]["mtplx"]["longContext2111"] = tampered
        cases.append(("tampered receipt", tampered_receipt, {}))

        valid_model = self.dense_27b_model()
        valid_model["backends"]["mtplx"]["longContext2111"] = copy.deepcopy(receipt)
        cases.extend([
            ("short context", valid_model, {"context": 32_768}),
            ("wrong profile", valid_model, {"profile": "sustained"}),
            ("wrong acceleration", valid_model, {"acceleration": "off"}),
            ("missing contract id", valid_model, {"contract_id": None}),
            ("wrong contract id", valid_model, {"contract_id": "0" * 24}),
        ])

        for index, (label, model, overrides) in enumerate(cases):
            plan = self.launch_plan(
                model,
                route=ROUTE_LONG_CONTEXT,
                contract_id=(
                    receipt["contractId"]
                    if "contract_id" not in overrides else overrides["contract_id"]
                ),
                context=int(overrides.get("context", MINIMUM_CONTEXT)),
                profile=str(overrides.get("profile", "turbo")),
                acceleration=str(overrides.get("acceleration", "mtp")),
                run_name=f"rejected-{index}",
            )
            capability = model["backends"]["mtplx"]
            with self.subTest(launch=label), self.assertRaises(ValueError):
                validator(plan, capability)

        forged = self.dense_27b_model()
        forged["backends"]["mtplx"]["longContext2111"] = copy.deepcopy(receipt)
        forged["backends"]["mtplx"]["longContext2111"]["contractId"] = "f" * 24
        forged_plan = self.launch_plan(
            forged,
            route=ROUTE_LONG_CONTEXT,
            contract_id="f" * 24,
            run_name="builder-must-revalidate",
        )
        with self.assertRaises(ValueError):
            self.build(forged_plan)

    def test_profile_validation_preserves_only_the_public_route_choice(self) -> None:
        model = self.dense_27b_model()
        capability = model["backends"]["mtplx"]
        validated = launcher.validated_profile_options(
            "mtplx",
            model,
            capability,
            {
                "acceleration": "mtp",
                "depth": 3,
                "kv": "off",
                "profile": "turbo",
                "fan": "default",
                "mtplxOperatorRoute": ROUTE_LONG_CONTEXT,
                "_mtplxOperatorContractId": "untrusted-ui-value",
            },
        )
        self.assertIn(
            "mtplxOperatorRoute", validated,
            "expected-red: preserve the one public operator-route choice",
        )
        self.assertEqual(validated["mtplxOperatorRoute"], ROUTE_LONG_CONTEXT)
        self.assertNotIn("_mtplxOperatorContractId", validated)

    def test_calibration_uses_an_internal_authoritative_near_64k_prompt(self) -> None:
        suite_name = getattr(launcher, "MTPLX_LONG_CONTEXT_64K_SUITE", None)
        self.assertIsInstance(
            suite_name, str,
            "expected-red: define the internal MTPLX long-context suite",
        )
        self.assertIn(suite_name, launcher.BENCHMARK_SUITES)
        suite = launcher.BENCHMARK_SUITES[suite_name]
        self.assertTrue(suite["internal"])
        self.assertEqual(suite["requiredContext"], MINIMUM_CONTEXT)
        self.assertIn(NEAR_TIER_PROMPT, suite["promptTokens"])
        self.assertGreaterEqual(max(suite["promptTokens"]), MINIMUM_NEAR_TIER_PROMPT)
        self.assertLess(max(suite["promptTokens"]), MINIMUM_CONTEXT)
        self.assertLess(max(launcher.BENCHMARK_SUITES["agentic"]["promptTokens"]), MINIMUM_NEAR_TIER_PROMPT)

        model = self.dense_27b_model()
        receipt = self.mint_contract(model)
        model["backends"]["mtplx"]["longContext2111"] = copy.deepcopy(receipt)
        # Start from the ordinary 8K/12K Agentic suite. The dedicated tuning
        # plan must replace that proof workload with its own near-64K contract.
        job = {
            "backend": "mtplx",
            "model": model,
            "modelId": model["id"],
            "modelFingerprint": self.model_fingerprint,
            "runtimeVersion": self.runtime_version,
            "context": MINIMUM_CONTEXT,
            "output": 1_024,
            "reasoning": "auto",
            "options": {
                "acceleration": "mtp", "depth": 3, "kv": "off",
                "profile": "turbo", "fan": "default",
            },
            "modes": ["ar", "mtp"],
            "suiteName": "agentic",
            "suite": copy.deepcopy(launcher.BENCHMARK_SUITES["agentic"]),
        }
        tuning = self.required_callable(
            "mtplx_long_context_operator_tuning_plan",
        )(copy.deepcopy(job))
        self.assertEqual(tuning["strategy"], "isolated-long-context-operator-comparison")
        self.assertEqual(tuning["suiteName"], suite_name)
        self.assertEqual(tuning["requiredContext"], MINIMUM_CONTEXT)
        self.assertEqual(tuning["baselineRoute"], ROUTE_DEFAULT)
        self.assertEqual(tuning["candidateRoute"], ROUTE_LONG_CONTEXT)
        self.assertEqual(tuning["baselineEnvironment"], BASELINE_ENVIRONMENT)
        self.assertEqual(tuning["candidateEnvironment"], CANDIDATE_ENVIRONMENT)
        self.assertTrue(tuning["freshLoadPerRoute"])
        proof = tuning["qualificationContract"]
        self.assertEqual(proof["suiteName"], suite_name)
        self.assertTrue(proof["authoritativeUsageRequired"])
        self.assertGreaterEqual(proof["minimumPromptTokens"], MINIMUM_NEAR_TIER_PROMPT)
        self.assertLessEqual(proof["minimumPromptTokens"], NEAR_TIER_PROMPT)
        self.assertEqual(proof["targetPromptTokens"], NEAR_TIER_PROMPT)

        launcher.prepare_calibration_tuning_plan(job)
        self.assertEqual(job["calibrationTuningPlan"], tuning)
        self.assertNotEqual(
            job["calibrationTuningPlan"]["suiteName"], "agentic",
            "normal 8K/12K Agentic samples cannot qualify the 64K operator route",
        )


if __name__ == "__main__":
    unittest.main()
