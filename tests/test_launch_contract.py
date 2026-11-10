"""Independent launch contract equivalence and rejection before materialization."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import launch_contract as contract


class Checks:
    def __init__(self):
        self.events = []
        self.artifact_error = None
        self.qualified = True
        self.measured = True

    def require_host(self, client, host): self.events.append(("host", client, host))
    def validate_override(self, backend, purpose, requested): return requested
    def require_installed(self, backend, client, override): self.events.append(("installed", backend, client))
    def client_support(self, backend, client, capability): return {"supported": True, "reason": "Exact fixture"}
    def shared_server(self, backend): return contract.SharedServer()
    def resume_session(self, value, project, client): return None
    def expert_offload_options(self, model, options): return None
    def require_current(self, request, options, purpose):
        self.events.append(("artifact", request.backend, purpose))
        if self.artifact_error:
            raise ValueError(self.artifact_error)
    def validate_optimizer_projection(self, request, options): self.events.append(("optimizer", request.backend))
    def qualify_session(self, request, options, purpose):
        self.events.append(("qualification", request.backend, purpose))
        if not self.qualified: raise ValueError("Exact current qualification is missing")
    def fastest(self, request, options): return {"options": contract.thaw(options), "rationale": ["Exact fixture"], "evidenceLabel": "Current"}
    def mtplx_candidate(self, request, options): return self.measured
    def bind_mtplx(self, request, options, purpose): return contract.thaw(options)


class LaunchContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.checks = Checks()
        self.validator = contract.LaunchContractValidator(runtime_checks=self.checks,
                        artifact_checks=self.checks, performance_checks=self.checks)
        capability = {"runnable": True, "mtp": True, "dflash": True, "kv": True,
                      "depth": 2, "depthMax": 4, "agentReasoning": ["auto", "off", "medium"],
                      "codexReasoning": ["auto", "off", "medium"], "aneTuningVerified": True,
                      "customSampling": True}
        self.model = {"id": "fixture", "name": "Exact fixture", "nativeContext": 131072,
                      "defaultOutput": 16384, "defaultSampling": {"temperature": 0.7, "top_p": 0.9, "seed": 17},
                      "backends": {backend: dict(capability) for backend in contract.DEFAULT_POLICY.backend_ids}}
        self.payload = {"backend": "mtplx", "client": "pi", "modelId": "fixture", "project": str(self.root),
                        "context": 8192, "output": 256, "agentHost": "console", "options": {"acceleration": "off", "kv": "off"}}

    def test_88_frozen_pre_refactor_cases_keep_values_and_exact_errors(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/launch-contract-v1.json").read_text())
        for case in fixture["cases"]:
            kwargs = dict(case["kwargs"])
            if case["name"] == "validated_profile_options": kwargs["offload_checks"] = self.checks
            try:
                value = getattr(contract, case["name"])(*case["args"], **kwargs)
                if case["name"] == "validated_limits": self.assertIsInstance(value, tuple)
                result = {"value": value}
            except Exception as error:
                result = {"errorType": type(error).__name__, "error": str(error)}
            with self.subTest(name=case["name"], args=str(case["args"])[-120:]):
                self.assertEqual(json.loads(json.dumps(result)), case["expected"])

    def test_live_and_saved_defaults_are_explicit_and_do_not_change_visible_options(self):
        live = self.validator.validate_live(self.payload, [self.model])
        saved = self.validator.validate_saved(self.payload, [self.model])
        self.assertEqual(live.selected.reasoning, "medium")
        self.assertEqual(saved.selected.reasoning, "auto")
        self.assertEqual(contract.thaw(live.options), self.payload["options"])
        self.assertEqual(saved.options["profile"], "sustained")
        self.assertEqual(saved.options["depth"], 1)
        self.assertEqual(saved.saved_request()["generation"], {"sampling": "model"})
        self.assertIn("artifact", live.completed_stages)
        live.require_validated()

    def test_frozen_nested_contract_has_no_reference_to_mutable_inputs(self):
        live = self.validator.validate_live(self.payload, [self.model])
        self.model["backends"]["mtplx"]["runnable"] = False
        self.payload["options"]["kv"] = "q4"
        self.assertTrue(live.selected.capability["runnable"])
        self.assertEqual(live.options["kv"], "off")
        with self.assertRaises(TypeError): live.selected.model["backends"]["mtplx"]["runnable"] = False
        with self.assertRaises(TypeError): live.options["kv"] = "q4"
        projected = contract.thaw(live.selected.model)
        projected["backends"]["mtplx"]["runnable"] = False
        self.assertTrue(live.selected.capability["runnable"])
        with self.assertRaises(ValueError): replace(live, _proof=None).require_validated()
        for changed in (replace(live, selected=replace(live.selected, output=4096)),
                        replace(live, options={"kv": "q4"}), replace(live, purpose="benchmark"),
                        replace(live, completed_stages=("artifact",)), replace(live, pi_session_file="unvalidated")):
            with self.assertRaises(ValueError): changed.require_validated()

    def test_full_saved_projection_matches_frozen_settings_without_credentials_or_transcript(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/launch-saved-contract-v1.json").read_text())
        for case in fixture["cases"]:
            payload = dict(case["payload"])
            payload["project"] = str(self.root)
            try:
                value = self.validator.validate_saved(payload, [fixture["model"]]).saved_request()
                value["project"] = "PROJECT"
                result = {"value": value}
            except Exception as error:
                result = {"errorType": type(error).__name__, "error": str(error)}
            with self.subTest(backend=payload["backend"], client=payload["client"]):
                self.assertEqual(result, case["expected"])
                self.assertNotIn("NEVER_STORE", json.dumps(result))

    def assert_no_materialization(self, payload, message, **kwargs):
        # These calls are forbidden for every outcome, including invalid input;
        # read-only project/session/artifact checks remain permitted.
        with patch.object(Path, "mkdir", side_effect=AssertionError("Directory allocated")), \
                patch.object(Path, "symlink_to", side_effect=AssertionError("Catalog linked")), \
                patch("secrets.token_urlsafe", side_effect=AssertionError("Secret allocated")), \
                patch("uuid.uuid4", side_effect=AssertionError("Run ID allocated")), \
                patch("socket.socket", side_effect=AssertionError("Port allocated")):
            with self.assertRaisesRegex(ValueError, message):
                self.validator.validate_live(payload, [self.model], **kwargs)

    def test_generated_core_invalid_requests_reject_without_any_materialization(self):
        variants = [({"context": True}, "whole number"), ({"output": 8192}, "smaller than"),
                    ({"reasoning": "high"}, "reasoning choices"), ({"agentHost": "remote"}, "Hub Console"),
                    ({"backend": "unknown"}, "runtime"), ({"client": "unknown"}, "Choose Pi"),
                    ({"generation": {"sampling": "model", "unknown": 1}}, "Unsupported generation"),
                    ({"project": str(self.root / "missing")}, "Project folder")]
        for changes, error in variants:
            with self.subTest(changes=changes): self.assert_no_materialization({**self.payload, **changes}, error)

    def test_unmeasured_mtplx_exact_operator_route_rejects_before_ports_or_files(self):
        self.checks.measured = False
        payload = {**self.payload, "context": 65536,
                   "options": {"profile": "turbo", "acceleration": "mtp", "mtplxOperatorRoute": contract.DEFAULT_POLICY.mtplx_operator_route}}
        self.assert_no_materialization(payload, "Calibration")
        self.assertFalse(any(event[0] == "artifact" for event in self.checks.events))

    def test_exact_uzu_llama_qualification_is_required_before_materialization(self):
        self.checks.qualified = False
        for backend, context in (("uzu", 16384), ("llamacpp", 8192)):
            self.assert_no_materialization({**self.payload, "backend": backend, "context": context}, "qualification")

    def test_omlx_acceleration_kv_and_ane_errors_reject_before_catalog_linking(self):
        for options, error in (({"acceleration": "invalid"}, "acceleration"), ({"kv": "invalid"}, "KV"),
                               ({"anePrefill": "invalid"}, "ANE prefill"),
                               ({"acceleration": "dflash", "kv": "q8", "dflashVerify": "ddtree"}, "full precision"),
                               ({"acceleration": "dflash", "anePrefill": "tuned"}, "cannot share")):
            self.assert_no_materialization({**self.payload, "backend": "omlx", "options": options}, error)

    def test_current_artifact_failure_prevents_a_validated_dto_without_build_io(self):
        self.checks.artifact_error = "Current native kernel receipt changed"
        self.assert_no_materialization({**self.payload, "backend": "omlx"}, "receipt changed")

    def test_freetoken_live_experimental_consent_and_saved_settings_are_separate(self):
        self.model["backends"]["freetoken"].update(native=True, nativeContract={
            "qualification": {"launcher": {"readiness": "experimental_synthetic_only"}}, "support": {}})
        payload = {**self.payload, "backend": "freetoken", "options": {}}
        self.assert_no_materialization(payload, "explicit experimental run")
        saved = self.validator.validate_saved(payload, [self.model])
        self.assertEqual(saved.options["maxBatchSize"], 1)
        self.validator.validate_live({**payload, "options": {"experimentalQualificationConsent": True}}, [self.model])

    def test_missing_topic_checks_and_invalid_run_purpose_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "complete"):
            contract.LaunchContractValidator(runtime_checks=object(), artifact_checks=self.checks, performance_checks=self.checks)
        self.assert_no_materialization(self.payload, "purpose", purpose="saved")


if __name__ == "__main__": unittest.main()
