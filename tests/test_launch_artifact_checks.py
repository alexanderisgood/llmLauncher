"""All engine artifact guards run without launch materialization or model loads."""
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import launch_contract as contract
import launcher


class ArtifactBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.model_path = self.root / "fixture.gturbo"
        self.model_path.mkdir()
        self.bridge = launcher.LaunchArtifactChecks()

    def selection(self, backend, *, model=None, cap=None, context=8192, output=256, reasoning="off", client="pi"):
        capability = {"runnable": True, "mtp": True, "kv": True, "depth": 2, "depthMax": 4,
                      "nativeExpertTopK": 8, "agentReasoning": ["auto", "off", "medium"], **(cap or {})}
        data = {"id": "fixture", "name": "Exact fixture", "path": str(self.model_path),
                "nativeContext": 131072, **(model or {})}
        data["backends"] = {backend: capability}
        return contract.SelectedRequest(backend, client, contract._freeze(data), contract._freeze(capability),
            context, output, reasoning, "console", "custom", contract._freeze({}),
            contract._freeze({"schemaVersion": 1, "controlled": True, "mode": "model", "values": {}}),
            contract._freeze({}), None, str(self.root))

    def forbid_materialization(self):
        stack = ExitStack()
        for owner, name in ((launcher, "free_port"), (launcher, "atomic_json"),
                            (launcher, "_ensure_uzu_offline_catalog"), (launcher, "_create_plan_api_key_file"),
                            (launcher.secrets, "token_urlsafe"), (launcher.secrets, "token_hex"),
                            (launcher.uuid, "uuid4"), (Path, "mkdir"), (Path, "symlink_to"),
                            (Path, "write_text"), (launcher.subprocess, "Popen")):
            stack.enter_context(mock.patch.object(owner, name, side_effect=AssertionError("Materialization entered artifact validation")))
        return stack

    def test_all_twelve_backend_positive_branches_do_not_materialize(self):
        with self.forbid_materialization(), ExitStack() as mocks:
            mocks.enter_context(mock.patch.object(launcher, "omlx_expert_offload_options", return_value=None))
            for backend in ("omlx", "mtplx", "lmstudio"):
                self.bridge.require_current(self.selection(backend), {"acceleration": "off", "kv": "off"}, "benchmark")
            for backend, helper in (("uzu", "_validated_uzu_route"), ("llamacpp", "_validated_llamacpp_route")):
                with mock.patch.object(launcher, helper) as verify:
                    self.bridge.require_current(self.selection(backend), {}, "benchmark")
                    verify.assert_called_once()
                    projected = verify.call_args.args[0]
                    self.assertFalse(hasattr(projected, "run_dir"))
                    self.assertFalse(hasattr(projected, "port"))
                    self.assertFalse(hasattr(projected, "secrets"))
            with mock.patch.object(launcher, "_verified_ssd_model_path", return_value=self.model_path):
                for backend in ("swiftlm", "mference"):
                    self.bridge.require_current(self.selection(backend), {}, "benchmark")
            install = {"ready": True, "binary": "/fixture/slotstream"}
            with mock.patch.object(launcher.slotstream_runtime, "inspect_install", return_value=install), \
                    mock.patch.object(launcher.slotstream_runtime, "doctor", return_value={"expected_peak_bytes": 1}):
                self.bridge.require_current(self.selection("slotstream", model={"slotstream": install}), {}, "benchmark")
            runtime, model = {"identity": "runtime"}, {"identity": "model"}
            with mock.patch.object(launcher.kolibri_runtime, "inspect_runtime", return_value=runtime), \
                    mock.patch.object(launcher.kolibri_runtime, "inspect_model", return_value=model), \
                    mock.patch.object(launcher.kolibri_runtime, "current_resource", return_value={}), \
                    mock.patch.object(launcher.kolibri_runtime, "memory_plan", return_value={"ready": True}):
                self.bridge.require_current(self.selection("kolibri", model={"kolibri": model}, cap={"runtimeIdentity": runtime}), {}, "benchmark")
            pack = {"identity": "pack"}
            with mock.patch.object(launcher.splash_runtime, "inspect_install", return_value={"ready": True}), \
                    mock.patch.object(launcher.splash_runtime, "inspect_model", return_value=pack), \
                    mock.patch.object(launcher.splash_runtime, "doctor", return_value={}):
                self.bridge.require_current(self.selection("splash", model={"splash": pack}), {}, "benchmark")
            with mock.patch.object(launcher.whallm_runtime, "inspect_install", return_value=install), \
                    mock.patch.object(launcher, "whallm_qualification_conflict", return_value=None):
                self.bridge.require_current(self.selection("whallm", model={"nativeWhallm": install},
                                            cap={"nativeWhallm": True}, context=16384, reasoning="medium"), {}, "benchmark")
            with mock.patch.object(launcher, "load_freetoken_connection", return_value={"id": "connection", "models": ["remote"]}), \
                    mock.patch.object(Path, "is_file", return_value=True):
                self.bridge.require_current(self.selection("freetoken", model={"remote": True,
                    "remoteConnectionId": "connection", "remoteModelId": "remote"}, cap={"connectionId": "connection"}), {}, "benchmark")

    def test_stale_artifact_blocks_each_backend_without_materialization(self):
        with self.forbid_materialization():
            for backend, helper in (("uzu", "_validated_uzu_route"), ("llamacpp", "_validated_llamacpp_route"),
                                    ("swiftlm", "_verified_ssd_model_path"), ("mference", "_verified_ssd_model_path")):
                with self.subTest(backend=backend), mock.patch.object(launcher, helper, side_effect=ValueError("Current artifact changed")):
                    with self.assertRaisesRegex(ValueError, "artifact changed"):
                        self.bridge.require_current(self.selection(backend), {}, "session")
            with mock.patch.object(launcher.slotstream_runtime, "inspect_install", return_value=None):
                with self.assertRaisesRegex(ValueError, "changed"):
                    self.bridge.require_current(self.selection("slotstream", model={"slotstream": {"ready": True}}), {}, "benchmark")
            with mock.patch.object(launcher.kolibri_runtime, "inspect_runtime", return_value=None), \
                    mock.patch.object(launcher.kolibri_runtime, "inspect_model", return_value={}):
                with self.assertRaisesRegex(ValueError, "changed"):
                    self.bridge.require_current(self.selection("kolibri"), {}, "benchmark")
            with mock.patch.object(launcher.splash_runtime, "inspect_install", return_value={"ready": False}):
                with self.assertRaisesRegex(ValueError, "release hash"):
                    self.bridge.require_current(self.selection("splash", model={"splash": {"identity": "pack"}}), {}, "benchmark")
            with mock.patch.object(launcher.whallm_runtime, "inspect_install", return_value=None):
                with self.assertRaisesRegex(ValueError, "changed"):
                    self.bridge.require_current(self.selection("whallm", model={"nativeWhallm": {"ready": True}},
                                        cap={"nativeWhallm": True}, context=16384, reasoning="medium"), {}, "benchmark")
            with mock.patch.object(launcher, "load_freetoken_connection", return_value={"id": "changed"}):
                with self.assertRaisesRegex(ValueError, "connection changed"):
                    self.bridge.require_current(self.selection("freetoken", model={"remote": True,
                        "remoteConnectionId": "old", "remoteModelId": "remote"}), {}, "benchmark")
            with self.assertRaisesRegex(ValueError, "receipt"):
                self.bridge.require_current(self.selection("freetoken", model={"remote": False}), {}, "benchmark")

    def test_native_whallm_exact_context_output_and_thinking_guards_match_launch_config(self):
        install = {"ready": True}
        with self.forbid_materialization(), mock.patch.object(launcher.whallm_runtime, "inspect_install", return_value=install), \
                mock.patch.object(launcher, "whallm_qualification_conflict", return_value=None):
            for context, output, reasoning, error in ((8192, 256, "medium", "16K context"),
                                                      (16384, 4097, "medium", "4K response"),
                                                      (16384, 256, "off", "Thinking stays enabled")):
                with self.subTest(context=context, output=output, reasoning=reasoning), self.assertRaisesRegex(ValueError, error):
                    self.bridge.require_current(self.selection("whallm", model={"nativeWhallm": install},
                        cap={"nativeWhallm": True}, context=context, output=output, reasoning=reasoning), {}, "session")

    def test_freetoken_dispatch_matches_original_remote_flag_and_is_not_inferred_from_missing_native(self):
        with self.forbid_materialization(), mock.patch.object(launcher, "_preflight_native_freetoken", side_effect=ValueError("Native receipt missing")) as native, \
                mock.patch.object(launcher, "_preflight_remote_freetoken") as remote:
            with self.assertRaisesRegex(ValueError, "Native receipt missing"):
                self.bridge.require_current(self.selection("freetoken", model={"remote": False}), {}, "session")
            native.assert_called_once(); remote.assert_not_called()
            self.bridge.require_current(self.selection("freetoken", model={"remote": True, "nativeFreetoken": True}), {}, "session")
            remote.assert_called_once()

    def test_omlx_current_ane_and_ple_fingerprints_are_required_without_catalog_io(self):
        with self.forbid_materialization(), mock.patch.object(launcher, "omlx_expert_offload_options", return_value=None):
            with mock.patch.object(launcher, "command_version", return_value="changed"), \
                    mock.patch.object(launcher, "omlx_qwen_kernel_status", return_value={"ready": True}), \
                    mock.patch.object(launcher, "verified_ane_tuning_record", return_value=False):
                with self.assertRaisesRegex(ValueError, "trusted ANE"):
                    self.bridge.require_current(self.selection("omlx", cap={"runtimeVersion": "old", "aneTuning": {}}), {"anePrefill": "tuned"}, "session")
            with mock.patch.object(launcher, "read_json", return_value={}), \
                    mock.patch.object(launcher, "weight_completeness", return_value=(True, "complete", 1)), \
                    mock.patch.object(launcher, "command_version", return_value="current"), \
                    mock.patch.object(launcher, "qwen4_ple_profile", return_value={"supported": True, "sourceFingerprint": "new"}):
                with self.assertRaisesRegex(ValueError, "changed after scanning"):
                    self.bridge.require_current(self.selection("omlx", model={"qwen4Ple": {"supported": True, "sourceFingerprint": "old"}}),
                                                {"memoryGuard": "high"}, "session")

    def test_mtplx_baseline_and_hub_python_gates_run_before_any_key_or_template(self):
        cap = {"longContext2111": {"ready": True}, "runtimeVersion": "2.11.1"}
        with self.forbid_materialization(), mock.patch.object(launcher, "mtplx_long_context_2111_contract", return_value=None):
            with self.assertRaisesRegex(ValueError, "inverse baseline"):
                self.bridge.require_current(self.selection("mtplx", cap=cap, context=65536),
                                            {"acceleration": "mtp", "profile": "turbo"}, "benchmark")
        config = {"model_type": "qwen3_8", **launcher.MTPLX_LONG_CONTEXT_DENSE_GEOMETRY}
        with self.forbid_materialization(), mock.patch.object(launcher, "read_json", return_value=config), \
                mock.patch.object(launcher, "physical_memory_bytes", return_value=48 * 1024**3), \
                mock.patch.object(launcher, "omlx_runtime_python", return_value=None):
            with self.assertRaisesRegex(ValueError, "runtime Python is missing"):
                self.bridge.require_current(self.selection("mtplx", cap={"runtimeVersion": "2.11.2"}), {}, "session")

    def test_slotstream_q8_and_memory_ledgers_and_kolibri_memory_gate_are_not_skipped(self):
        base, q8 = {"ready": True, "binary": "base"}, {"ready": True, "binary": "q8"}
        with self.forbid_materialization(), mock.patch.object(launcher.slotstream_runtime, "inspect_install", side_effect=[base, {"ready": True, "binary": "changed"}]):
            with self.assertRaisesRegex(ValueError, "Q8 runtime changed"):
                self.bridge.require_current(self.selection("slotstream", model={"slotstream": base, "slotstreamQ8": q8}), {"kv": "q8"}, "session")
        with self.forbid_materialization(), mock.patch.object(launcher.slotstream_runtime, "inspect_install", return_value=base), \
                mock.patch.object(launcher.slotstream_runtime, "doctor", side_effect=ValueError("Current memory ledger cannot fit")):
            with self.assertRaisesRegex(ValueError, "memory ledger"):
                self.bridge.require_current(self.selection("slotstream", model={"slotstream": base}), {}, "session")
        runtime, model = {"id": "runtime"}, {"id": "model"}
        with self.forbid_materialization(), mock.patch.object(launcher.kolibri_runtime, "inspect_runtime", return_value=runtime), \
                mock.patch.object(launcher.kolibri_runtime, "inspect_model", return_value=model), \
                mock.patch.object(launcher.kolibri_runtime, "current_resource", return_value={}), \
                mock.patch.object(launcher.kolibri_runtime, "memory_plan", return_value={"ready": False}):
            with self.assertRaisesRegex(ValueError, "Free memory"):
                self.bridge.require_current(self.selection("kolibri", model={"kolibri": model}, cap={"runtimeIdentity": runtime}), {}, "session")

    def test_native_freetoken_current_contract_reinspection_and_consent_are_read_only(self):
        executable = self.root / "freetoken"
        executable.write_text("fixture executable")
        executable.chmod(0o700)
        qualification = {"launcher": {"readiness": "experimental_synthetic_only"}}
        receipt = {"supported": True, "startup": {"default_allowed": True},
                   "runtime": {"freetoken_version": "fixture"}, "qualification": qualification}
        cap = {"native": True, "nativeBinary": str(executable), "benchmarkModelFingerprint": "fingerprint",
               "nativeContract": {**receipt, "support": {}}}
        request = self.selection("freetoken", client="chat", model={"nativeFreetoken": True}, cap=cap)
        with self.forbid_materialization(), mock.patch.dict(launcher.BINARIES, {"freetoken_native": str(executable)}), \
                mock.patch.object(launcher, "read_json", return_value={}), \
                mock.patch.object(launcher, "model_artifact_fingerprint", return_value="fingerprint"), \
                mock.patch.object(launcher, "validate_native_freetoken_contract", return_value=receipt), \
                mock.patch.object(launcher, "inspect_native_freetoken_model", return_value=receipt) as inspect:
            with self.assertRaisesRegex(ValueError, "explicit experimental run"):
                self.bridge.require_current(request, {}, "session")
            self.bridge.require_current(request, {"experimentalQualificationConsent": True}, "session")
            self.assertEqual(inspect.call_count, 2)
            self.assertTrue(inspect.call_args.kwargs["force"])
        changed = {**receipt, "qualification": {"launcher": {"readiness": "changed"}}}
        with self.forbid_materialization(), mock.patch.dict(launcher.BINARIES, {"freetoken_native": str(executable)}), \
                mock.patch.object(launcher, "read_json", return_value={}), \
                mock.patch.object(launcher, "model_artifact_fingerprint", return_value="fingerprint"), \
                mock.patch.object(launcher, "validate_native_freetoken_contract", return_value=receipt), \
                mock.patch.object(launcher, "inspect_native_freetoken_model", return_value=changed):
            with self.assertRaisesRegex(ValueError, "capability evidence changed"):
                self.bridge.require_current(request, {"experimentalQualificationConsent": True}, "session")
        with self.forbid_materialization(), self.assertRaisesRegex(ValueError, "Chat only"):
            self.bridge.require_current(replace(request, client="pi"), {"experimentalQualificationConsent": True}, "session")

    def test_shared_whallm_exact_pinned_model_and_remote_connection_remain_required(self):
        request = self.selection("whallm", model={"sharedServer": True, "remoteModelId": launcher.WHALLM_MODEL_ID},
                                 cap={"sharedServer": True}, context=16384)
        with self.forbid_materialization(), mock.patch.object(launcher, "probe_whallm_endpoint", return_value={"model": launcher.WHALLM_MODEL_ID}), \
                mock.patch.object(Path, "is_file", return_value=True):
            self.bridge.require_current(request, {}, "session")
        with self.forbid_materialization(), mock.patch.object(launcher, "probe_whallm_endpoint", return_value={"model": "other"}):
            with self.assertRaisesRegex(ValueError, "pinned Qwen model"):
                self.bridge.require_current(request, {}, "session")
        with self.forbid_materialization(), mock.patch.object(launcher, "load_freetoken_connection", return_value={"id": "connection", "models": []}):
            with self.assertRaisesRegex(ValueError, "no longer advertised"):
                self.bridge.require_current(self.selection("freetoken", model={"remote": True,
                    "remoteConnectionId": "connection", "remoteModelId": "missing"}, cap={"connectionId": "connection"}), {}, "session")


if __name__ == "__main__": unittest.main()
