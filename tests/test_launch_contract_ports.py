"""Concrete controller-owned read-only topic ports preserve existing contracts."""
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import launch_contract as contract
import launcher
from tests.test_launch_contract import Checks


class LaunchContractPortTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.runtime = launcher.LaunchRuntimeChecks()
        self.performance = launcher.LaunchPerformanceChecks()
        self.artifacts = Checks()
        self.model = {"id": "fixture", "name": "Exact fixture", "nativeContext": 131072,
                      "defaultOutput": 16384, "defaultSampling": {"temperature": 0.7, "top_p": 0.9, "seed": 17},
                      "backends": {key: {"runnable": True, "mtp": True, "kv": True, "depth": 2, "depthMax": 4,
                                             "agentReasoning": ["auto", "off", "medium"], "customSampling": True}
                                   for key in launcher.ENGINE_ADAPTERS}}
        self.payload = {"backend": "mtplx", "client": "pi", "modelId": "fixture", "project": str(self.root),
                        "context": 8192, "output": 256, "reasoning": "off", "agentHost": "console",
                        "options": {"acceleration": "off", "kv": "off"}}
        self.selection = contract.LaunchContractValidator(runtime_checks=self.artifacts, artifact_checks=self.artifacts,
                        performance_checks=self.artifacts).validate_live(self.payload, [self.model]).selected

    def forbid_materialization(self):
        stack = ExitStack()
        for owner, name in ((launcher, "free_port"), (launcher, "build_engine_plan"), (launcher, "build_client_plan"),
                            (launcher.secrets, "token_urlsafe"), (launcher.uuid, "uuid4"),
                            (Path, "mkdir"), (Path, "symlink_to")):
            stack.enter_context(mock.patch.object(owner, name, side_effect=AssertionError("Materialization entered validation")))
        return stack

    def test_runtime_override_exact_membership_and_host_guards_are_read_only(self):
        executable = self.root / "omlx"
        executable.write_text("fixture executable")
        with self.forbid_materialization(), mock.patch.object(launcher, "runtime_candidates", return_value=[{"path": str(executable)}]):
            self.assertEqual(self.runtime.validate_override("omlx", "runtime-promotion", str(executable)), str(executable.resolve()))
            with self.assertRaisesRegex(ValueError, "reserved"):
                self.runtime.validate_override("omlx", "session", str(executable))
            with self.assertRaisesRegex(ValueError, "disappeared"):
                self.runtime.validate_override("omlx", "runtime-promotion", str(self.root / "missing"))
        with self.forbid_materialization(), mock.patch.object(launcher, "command_version", return_value="omp/18.6.2"):
            with self.assertRaisesRegex(ValueError, "Choose Terminal"):
                self.runtime.require_host("omp", "console")

    def test_installed_requirements_and_shared_server_safety_do_not_allocate_ports(self):
        with self.forbid_materialization(), mock.patch.dict(launcher.BINARIES, {"mtplx": None, "pi": None}):
            with self.assertRaisesRegex(ValueError, "mtplx is not installed"):
                self.runtime.require_installed("mtplx", "pi", None)
            with self.assertRaisesRegex(ValueError, "pi is not installed"):
                self.runtime.require_installed("mtplx", "pi", "/explicit/omlx")
        with self.forbid_materialization(), mock.patch.object(launcher, "lmstudio_server_status", return_value=(True, 1234)), \
                mock.patch.object(launcher, "lmstudio_server_is_safe", return_value=False):
            with self.assertRaisesRegex(ValueError, "loopback-only"):
                self.runtime.shared_server("lmstudio")
        with self.forbid_materialization(), mock.patch.object(launcher, "lmstudio_server_status", return_value=(True, 1234)), \
                mock.patch.object(launcher, "lmstudio_server_is_safe", return_value=True):
            self.assertEqual(self.runtime.shared_server("lmstudio"), contract.SharedServer(True, 1234))

    def test_resume_and_support_delegate_only_narrow_current_checks(self):
        with self.forbid_materialization(), mock.patch.object(launcher, "validated_pi_session_file", return_value="/checked/session.jsonl") as resume, \
                mock.patch.object(launcher, "resolved_client_support", return_value={"supported": False, "reason": "Current receipt changed"}) as support:
            self.assertEqual(self.runtime.resume_session("/requested", str(self.root), "pi"), "/checked/session.jsonl")
            resume.assert_called_once_with("/requested", str(self.root))
            self.assertEqual(self.runtime.client_support("mtplx", "pi", {}), {"supported": False, "reason": "Current receipt changed"})
            support.assert_called_once_with("mtplx", "pi", {})

    def test_optimizer_and_fastest_exact_evidence_inputs_match_current_normalizer_tail(self):
        expected_options = {"acceleration": "off", "kv": "off"}
        evidence = {"source": "current fixture"}
        result = {"options": expected_options, "evidenceLabel": "Current", "rationale": ["Exact"]}
        with self.forbid_materialization(), mock.patch.object(launcher, "optimizer_evidence", return_value=evidence) as collect, \
                mock.patch.object(launcher, "add_benchmark_engine_evidence") as add, \
                mock.patch.object(launcher, "fastest_safe_options", return_value=result) as fastest:
            self.assertEqual(self.performance.fastest(self.selection, expected_options), result)
            collect.assert_called_once_with(self.model, 8192, 256, "pi", "off", "off", {},
                                            contract.thaw(self.selection.sampling_contract))
            add.assert_called_once_with(evidence, self.model, expected_options, ["mtplx"])
            fastest.assert_called_once_with("mtplx", self.model["backends"]["mtplx"], expected_options, evidence)
        with self.forbid_materialization(), mock.patch.object(launcher, "optimizer_evidence", return_value=evidence), \
                mock.patch.object(launcher, "add_benchmark_engine_evidence"), \
                mock.patch.object(launcher, "fastest_safe_options", return_value=result) as fastest, \
                mock.patch.object(launcher, "optimal_request", side_effect=AssertionError("Recursive canonicalization")):
            self.performance.validate_optimizer_projection(self.selection, expected_options)
            fastest.assert_called_once()

    def test_exact_uzu_and_llama_qualification_remains_current_and_purpose_specific(self):
        for backend in ("uzu", "llamacpp"):
            selection = replace(self.selection, backend=backend)
            name = "_uzu_qualified_session_record" if backend == "uzu" else "verified_route_qualification"
            with self.forbid_materialization(), mock.patch.object(launcher, "optimizer_evidence", return_value={}), \
                    mock.patch.object(launcher, "add_benchmark_engine_evidence"), \
                    mock.patch.object(launcher, name, return_value=None) as verify:
                with self.assertRaisesRegex(ValueError, "fresh successful local qualification"):
                    self.performance.qualify_session(selection, self.payload["options"], "session")
                verify.assert_called_once()
                self.performance.qualify_session(selection, self.payload["options"], "benchmark")
                verify.assert_called_once()

    def test_mtplx_candidate_and_binding_preserve_full_selected_contract(self):
        options = {"acceleration": "mtp", "profile": "turbo", "mtplxOperatorRoute": launcher.MTPLX_LONG_CONTEXT_2111_ROUTE}
        selection = replace(self.selection, context=65536)
        with self.forbid_materialization(), mock.patch.object(launcher, "verified_mtplx_operator_candidate_record", return_value={"id": "current"}) as candidate, \
                mock.patch.object(launcher, "_bind_mtplx_operator_route", return_value={**options, "_mtplxOperatorContractId": "fresh"}) as bind:
            self.assertTrue(self.performance.mtplx_candidate(selection, options))
            candidate.assert_called_once_with(self.model, self.model["backends"]["mtplx"], options,
                65536, 256, "pi", "off", {}, contract.thaw(selection.sampling_contract))
            self.assertEqual(self.performance.bind_mtplx(selection, options, "session")["_mtplxOperatorContractId"], "fresh")
            bind.assert_called_once_with(self.model, self.model["backends"]["mtplx"], options, 65536, "session")

    def test_concrete_saved_projection_equals_existing_root_profile_canonicalizer(self):
        validator = contract.LaunchContractValidator(runtime_checks=self.runtime, artifact_checks=self.artifacts,
                                                   performance_checks=self.performance)
        with self.forbid_materialization(), mock.patch.dict(launcher.BINARIES, {"mtplx": "/fixture/mtplx", "pi": "/fixture/pi"}), \
                mock.patch.object(launcher, "optimizer_evidence", return_value={}), \
                mock.patch.object(launcher, "add_benchmark_engine_evidence"), \
                mock.patch.object(launcher, "fastest_safe_options", return_value={"options": self.payload["options"]}):
            expected = launcher.validated_launch_profile_request(self.payload, [self.model])
            actual = validator.validate_saved(self.payload, [self.model]).saved_request()
        self.assertEqual(actual, expected)


if __name__ == "__main__": unittest.main()
