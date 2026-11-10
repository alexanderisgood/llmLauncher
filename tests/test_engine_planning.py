"""Generated private native plans and pre-exec proof, without engine processes."""
import ast
import copy
from contextlib import ExitStack
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

import engine_planning
import launcher
import runtime_identity
from tests.helpers.engine_planning_fixture import make_planner


FIXTURE = Path(__file__).with_name("fixtures") / "engine-planning-v1.json"
CASES = (
    "omlx", "omlx-mtp", "omlx-dflash", "omlx-dflash-q8", "lmstudio", "lmstudio-mtp",
    "mtplx", "mtplx-mtp-q8", "uzu", "swiftlm", "mference", "slotstream", "slotstream-q8",
    "kolibri", "splash", "whallm-native", "whallm-shared", "freetoken-native", "freetoken-remote", "llamacpp",
)


class PrivateEngineFixture:
    def __init__(self, folder):
        self.root = Path(folder).resolve()
        self.model_path = self.root / "model"
        self.model_path.mkdir()
        (self.model_path / "config.json").write_text('{"model_type":"generated"}\n')
        self.binary_dir = self.root / "runtime"
        self.binary_dir.mkdir()
        self.binaries = {}
        for key in ("omlx", "mtplx", "lms", "mirai", "swiftlm", "mference", "slotstream", "splash", "kolibri", "whallm", "freetoken_native", "llamacpp"):
            path = self.binary_dir / key
            path.write_text("#!/bin/sh\nexit 0\n")
            path.chmod(0o700)
            self.binaries[key] = str(path)
        self.bridge = self.root / "freetoken_bridge.py"
        self.bridge.write_text("# generated private bridge fixture\n")
        self.runtime = {
            "ready": True, "version": "generated-runtime", "binaryIdentityPinned": True,
            "nativeBearerAuthentication": True, "oneUseApiKeyFile": True,
            "nativeContextLimit": True, "nativeOutputLimit": True, "boundedContextReady": True,
            "nativeBoundaryContractId": launcher.UZU_NATIVE_BOUNDARY_CONTRACT_ID,
            "networkSandbox": True, "memorySafetyBlocked": False,
            "upstreamCommit": "generated-commit", "sourcePatchSha256": "generated-patch",
            "binary": {"sha256": "generated-runtime-sha", "size": 19, "id": "generated-inode"},
        }
        self.cache = {"ready": True, "path": str(self.model_path), "fingerprint": "model-proof"}
        self.artifact = {"ready": True, "verificationGeneration": 1,
            "receiptFingerprint": "generated-receipt", "firstShard": str(self.model_path / "model.gguf")}
        (self.model_path / "model.gguf").write_bytes(b"GGUF-generated-fixture")
        self.native_contract = {"supported": True, "startup": {"default_allowed": True},
            "runtime": {"freetoken_version": "generated-runtime"},
            "qualification": {"launcher": {"readiness": "qualified-real-checkpoint"}},
            "support": {"continuous_batching": True, "prefix_cache": True, "expert_placement": True}}

    def patches(self):
        stack = ExitStack()
        stack.enter_context(mock.patch.dict(launcher.BINARIES, self.binaries))
        for name, value in {
            "STATE_DIR": self.root / "state", "FREETOKEN_BRIDGE": self.bridge,
            "LLAMACPP_RUNTIME_DIR": self.binary_dir, "LLAMACPP_SERVER_PATH": Path(self.binaries["llamacpp"]),
            "LLAMACPP_RUNTIME_FILE_MANIFEST": (),
            "LLAMACPP_ATOMIC_FILE_MANIFEST": (("model.gguf", 22, "generated-sha"),),
        }.items():
            stack.enter_context(mock.patch.object(launcher, name, value))
        # These are individual read-only artifact/runtime ports, never builders.
        for name, value in {
            "omlx_expert_offload_options": None, "dflash2_capability_valid": True,
            "omlx_plan_runtime_version": "0.6.4", "omlx_runtime_python": "/fixture/python",
            "preserved_qwopus_template": "{{ content }}\n",
            "model_artifact_fingerprint": "model-proof", "physical_memory_bytes": 48 * 1024**3,
            "apple_iogpu_wired_limit_bytes": launcher.LLAMACPP_PLE_MEMORY_CEILING_BYTES,
            "whallm_qualification_conflict": {}, "probe_whallm_endpoint": {"model": launcher.WHALLM_MODEL_ID},
            "uzu_runtime_contract": self.runtime, "uzu_listener_protection_ready": True,
            "_uzu_model_cache_contract": self.cache, "_validated_uzu_offline_catalog": "catalog-proof",
            "llamacpp_runtime_contract": {"ready": True, "version": "generated-runtime"},
            "llamacpp_atomic_artifact_contract": self.artifact,
            "load_freetoken_connection": {"id": "connection-proof", "endpoint": "https://fixture.invalid/v1", "models": ["remote-model"], "apiKey": "generated-upstream-key"},
            "validate_native_freetoken_contract": self.native_contract,
            "inspect_native_freetoken_model": self.native_contract,
            "launch_memory_estimate": {"geometryReady": True, "kvCacheBytes": 1024**3},
        }.items():
            stack.enter_context(mock.patch.object(launcher, name, return_value=copy.deepcopy(value)))
        stack.enter_context(mock.patch.object(launcher, "_ensure_uzu_offline_catalog", side_effect=lambda _cache: None))
        stack.enter_context(mock.patch.object(launcher.secrets, "token_urlsafe", return_value="fixed-test-key"))
        stack.enter_context(mock.patch.object(launcher.secrets, "token_hex", return_value="fixed-test-hex"))
        install = {"ready": True, "binary": self.binaries["slotstream"], "identity": "slotstream-fixture"}
        q8 = dict(install, binary=self.binaries["slotstream"] + "-q8", identity="slotstream-q8-fixture")
        for module, name, value in (
            (launcher.slotstream_runtime, "doctor", {"target_gb": 19.0}),
            (launcher.slotstream_runtime, "planning_arguments", ["--context", "8192", "--fixture-native-plan"]),
            (launcher.kolibri_runtime, "inspect_runtime", {"identity": "kolibri-runtime"}),
            (launcher.kolibri_runtime, "inspect_model", {"identity": "kolibri-model"}),
            (launcher.kolibri_runtime, "current_resource", {}),
            (launcher.kolibri_runtime, "memory_plan", {"ready": True, "expertCacheBytes": 1024**3, "residentExpertsPerLayer": 8}),
            (launcher.splash_runtime, "inspect_install", {"ready": True}),
            (launcher.splash_runtime, "doctor", {}),
            (launcher.whallm_runtime, "inspect_install", {"artifactIdentity": "artifact-proof", "python": "/fixture/python", "app": "/fixture/Whallm.app"}),
            (launcher.whallm_runtime, "launch_config", {"context": 16384, "output": 1024, "port": 18765}),
        ):
            stack.enter_context(mock.patch.object(module, name, return_value=copy.deepcopy(value)))
        stack.enter_context(mock.patch.object(launcher.slotstream_runtime, "inspect_install",
            side_effect=lambda binary, _path: copy.deepcopy(q8 if str(binary).endswith("-q8") else install)))
        stack.enter_context(mock.patch.object(launcher.splash_runtime, "inspect_model", side_effect=lambda _install, pack: copy.deepcopy(pack)))
        # This fixture must never start a native engine or issue a network request.
        stack.enter_context(mock.patch.object(launcher.subprocess, "Popen", side_effect=AssertionError("Engine fixture tried to start a process")))
        return stack

    def plan(self, case):
        backend = "whallm" if case.startswith("whallm-") else "freetoken" if case.startswith("freetoken-") else case.split("-")[0]
        path = self.model_path
        if backend == "mference":
            path = self.root / "model.gturbo"
            path.mkdir(exist_ok=True)
            (path / "manifest.json").write_text('{}\n')
        model = {"id": "fixture-model", "name": "Generated exact model", "path": str(path),
            "lmKey": "owner/generated-model@6bit",
            "defaultSampling": {"temperature": 0.7, "top_p": 0.9, "top_k": 40, "seed": 17},
            "templateReasoningEfforts": ["medium"], "nativeContext": 131072}
        cap = {"runnable": True, "mtp": True, "dflash": True, "kv": True,
            "depth": 2, "depthMax": 4, "runtimeVersion": "generated-runtime",
            "benchmarkModelFingerprint": "model-proof", "modelPath": str(path),
            "ssdStreaming": True, "artifactFingerprint": "model-proof", "nativeExpertTopK": 2,
            "dflashVersion": "2", "dflashDraftPath": str(self.root / "draft"),
            "dflashBlockSize": 4, "dflashMaxBlockSize": 8, "dflashRuntimeVersion": "0.6.4"}
        options = {"acceleration": "off", "depth": 1, "kv": "off"}
        context, reasoning = 8192, "off"
        if "mtp" in case:
            options.update(acceleration="mtp", depth=2)
        if "dflash" in case:
            options.update(acceleration="dflash", depth=4, dflashDraftQuant="q4", dflashVerify="dflash")
            reasoning = "medium"
        if case.endswith("q8"):
            options["kv"] = "q8"
        if backend == "mtplx":
            options.update(profile="sustained", fan="smart")
            reasoning = "medium"
        if backend == "slotstream":
            model["slotstream"] = {"ready": True, "binary": self.binaries["slotstream"], "identity": "slotstream-fixture"}
            model["slotstreamQ8"] = {"ready": True, "binary": self.binaries["slotstream"] + "-q8", "identity": "slotstream-q8-fixture"}
        if backend == "kolibri":
            model["kolibri"] = {"identity": "kolibri-model"}
            cap["runtimeIdentity"] = {"identity": "kolibri-runtime"}
        if backend == "splash":
            model["splash"] = {"identity": "splash-model", "id": "owner/model", "draftCandidates": []}
            context = 16384
        if backend == "uzu":
            model["uzuNative"] = True
            cap.update(runtimeIdentity=copy.deepcopy(self.runtime), modelRegistryId=launcher.UZU_MODEL_REGISTRY_ID,
                modelCommit=launcher.UZU_MODEL_COMMIT, modelToolchainVersion=launcher.UZU_MODEL_TOOLCHAIN_VERSION,
                qualificationSystemContract={"rawListenerProtected": True,
                    "nativeBoundaryContractId": launcher.UZU_NATIVE_BOUNDARY_CONTRACT_ID,
                    "nativeBearerAuthentication": True, "oneUseApiKeyFile": True,
                    "nativeContextLimit": True, "nativeOutputLimit": True})
            context, reasoning = 16384, "auto"
        if backend == "llamacpp":
            cap.update(llamacppPle=True, currentProcessVerified=True, verificationGeneration=1,
                receiptFingerprint=self.artifact["receiptFingerprint"], firstShard=self.artifact["firstShard"])
            reasoning = "auto"
            # The acquisition receipt participates in the real stat identity set.
            (path.parent / launcher.MODEL_ACQUISITION_MARKER).write_text('{}\n')
        if case == "whallm-native":
            model["nativeWhallm"] = {"artifactIdentity": "artifact-proof", "python": "/fixture/python", "app": "/fixture/Whallm.app"}
            cap["nativeWhallm"] = True
            context, reasoning = 16384, "auto"
        if case == "whallm-shared":
            model.update(sharedServer=True, remoteModelId=launcher.WHALLM_MODEL_ID)
            cap["sharedServer"] = True
            context, reasoning = 16384, "medium"
        if case == "freetoken-remote":
            model.update(remote=True, remoteConnectionId="connection-proof", remoteModelId="remote-model")
            cap["connectionId"] = "connection-proof"
        if case == "freetoken-native":
            model["nativeFreetoken"] = True
            cap.update(native=True, nativeBinary=self.binaries["freetoken_native"],
                nativeContract=copy.deepcopy(self.native_contract), nativeMaxContext=8192)
            options.update(maxBatchSize=1, prefixCacheEntries=2, expertCacheSize=4)
        model["backends"] = {backend: cap}
        return SimpleNamespace(run_id="012abcde-1111-4111-8111-111111111111", backend=backend,
            client="chat", model=model, project=str(self.root), context=context, output=1024,
            reasoning=reasoning, options=options, warnings=[], runtime_binary=None,
            purpose="benchmark", chat={}, port=18765, run_dir=self.root / "run",
            engine_argv=[], engine_env={}, client_env={}, secrets={})

    def snapshot(self, plan):
        record = {key: copy.deepcopy(value) for key, value in vars(plan).items() if key != "run_dir"}
        if record["engine_argv"] and record["engine_argv"][0] == sys.executable:
            record["engine_argv"][0] = "PYTHON"
        files = {}
        for path in sorted(plan.run_dir.rglob("*")):
            relative = str(path.relative_to(plan.run_dir))
            if path.is_symlink():
                files[relative] = {"symlink": os.readlink(path)}
            elif path.is_file():
                files[relative] = {"mode": path.stat().st_mode & 0o777, "text": path.read_text()}
            elif path.is_dir():
                files[relative] = {"directory": True}
        record["files"] = files
        return json.loads(json.dumps(record, ensure_ascii=False).replace(str(self.root), "ROOT").replace(str(launcher.APP_DIR), "APP_DIR"))


class EnginePlanningTests(unittest.TestCase):
    def test_every_native_plan_and_private_file_matches_frozen_original_builder(self):
        fixture = json.loads(FIXTURE.read_text())
        self.assertEqual(fixture["preExtractionDefinitionsSha256"], "3ffe41a6027bad2aecc4a1df7ebd1d93c1295f9a05265e2363827a0d15c0a5fb")
        self.assertEqual(tuple(case["case"] for case in fixture["cases"]), CASES)
        self.assertEqual(set(engine_planning.ENGINE_BUILD_METHODS), set(launcher.ENGINE_ADAPTERS))
        for case in fixture["cases"]:
            with self.subTest(case=case["case"]), tempfile.TemporaryDirectory(prefix="engine-equivalence-") as folder:
                generated = PrivateEngineFixture(folder)
                with generated.patches():
                    plan = generated.plan(case["case"])
                    make_planner(launcher).build_engine_plan(plan)
                    self.assertEqual(generated.snapshot(plan), case["expected"])

    def test_controller_interpreter_parameter_is_portable_without_relaxing_native_paths(self):
        fixture = json.loads(FIXTURE.read_text())
        wrapped = [case for case in fixture["cases"] if case["expected"]["engine_argv"][0] == "PYTHON"]
        self.assertEqual(len(wrapped), 6)
        for case in wrapped:
            with self.subTest(case=case["case"]), tempfile.TemporaryDirectory(prefix="engine-ci-interpreter-") as folder:
                generated = PrivateEngineFixture(folder)
                with generated.patches(), mock.patch.object(sys, "executable", "/portable-ci/python3.10"):
                    plan = generated.plan(case["case"])
                    make_planner(launcher).build_engine_plan(plan)
                    self.assertEqual(plan.engine_argv[0], "/portable-ci/python3.10")
                    self.assertEqual(generated.snapshot(plan), case["expected"])

    def test_frozen_policy_detaches_nested_tables_and_keeps_launch_authority(self):
        planner = make_planner(launcher)
        source = {"MTPLX_ALLOW_SWAP": "0"}
        policy = replace(planner.policy.mtplx, candidate_environment=source)
        source["MTPLX_ALLOW_SWAP"] = "1"
        self.assertEqual(policy.candidate_environment["MTPLX_ALLOW_SWAP"], "0")
        with self.assertRaises(TypeError):
            policy.candidate_environment["MTPLX_ALLOW_SWAP"] = "1"
        with self.assertRaises(FrozenInstanceError):
            planner.policy.uzu.context_windows = (1,)
        self.assertIsInstance(planner.policy.launch, launcher.launch_contract.LaunchPolicy)

    def test_invalid_options_or_stale_artifacts_create_no_keys_or_private_files(self):
        cases = (
            ("omlx", "acceleration"), ("mtplx", "KV"), ("lmstudio", "GPU"),
            ("uzu", "runtime"), ("swiftlm", "changed"), ("mference", "changed"),
            ("slotstream", "changed"), ("kolibri", "changed"), ("splash", "changed"),
            ("whallm-native", "changed"), ("freetoken-remote", "connection changed"),
            ("llamacpp", "receipt changed"),
        )
        for case, expected in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix="engine-reject-") as folder:
                generated = PrivateEngineFixture(folder)
                with generated.patches(), ExitStack() as extra:
                    plan = generated.plan(case)
                    cap = plan.model["backends"][plan.backend]
                    planner = make_planner(launcher)
                    if case == "omlx": plan.options["acceleration"] = "bad"
                    elif case == "mtplx": plan.options["kv"] = "bad"
                    elif case == "lmstudio": plan.options["gpu"] = "bad"
                    elif case == "uzu": planner.uzu = replace(planner.uzu, runtime_contract=lambda *_a,**_k:{"ready":False})
                    elif case in {"swiftlm", "mference"}: cap["artifactFingerprint"] = "stale"
                    elif case == "slotstream": extra.enter_context(mock.patch.object(engine_planning.slotstream_runtime, "inspect_install", return_value={}))
                    elif case == "kolibri": extra.enter_context(mock.patch.object(engine_planning.kolibri_runtime, "inspect_model", return_value={"identity":"stale"}))
                    elif case == "splash": extra.enter_context(mock.patch.object(engine_planning.splash_runtime, "inspect_model", return_value={"identity":"stale"}))
                    elif case == "whallm-native": extra.enter_context(mock.patch.object(engine_planning.whallm_runtime, "inspect_install", return_value={"artifactIdentity":"stale"}))
                    elif case == "freetoken-remote": plan.model["remoteConnectionId"] = "stale"
                    elif case == "llamacpp": cap["receiptFingerprint"] = "stale"
                    def forbidden(*_a,**_k): raise AssertionError("Invalid engine plan materialized a private file")
                    planner.io = replace(planner.io, atomic_json=forbidden, token_urlsafe=forbidden, token_hex=forbidden)
                    with mock.patch.object(Path,"mkdir",side_effect=forbidden), mock.patch.object(Path,"write_text",side_effect=forbidden), \
                            self.assertRaisesRegex(ValueError, expected):
                        getattr(planner, engine_planning.ENGINE_BUILD_METHODS[plan.backend])(plan, cap)
                    self.assertFalse(plan.run_dir.exists())
                    self.assertEqual(plan.secrets, {})

    def test_uzu_rechecks_live_runtime_and_key_after_materialization(self):
        with tempfile.TemporaryDirectory(prefix="engine-uzu-current-") as folder:
            generated = PrivateEngineFixture(folder)
            with generated.patches():
                plan = generated.plan("uzu")
                planner = make_planner(launcher)
                planner.build_engine_plan(plan)
                before = planner.validate_uzu_launch_boundary(plan)
                self.assertEqual(before[0:2], ("generated-runtime-sha", "model-proof"))
                plan.engine_argv.append("--unsafe-future-override")
                with self.assertRaisesRegex(ValueError, "fixed local-only"):
                    planner.validate_uzu_launch_boundary(plan)
                plan.engine_argv.pop()
                key_file = planner._uzu_api_key_file(plan)
                key_file.write_text("replaced-key\n")
                with self.assertRaisesRegex(ValueError, "API-key file changed"):
                    planner.validate_uzu_launch_boundary(plan)
                key_file.write_text("fixed-test-key\n")
                changed = copy.deepcopy(generated.runtime)
                changed["binary"]["sha256"] = "different-runtime"
                planner.uzu = replace(planner.uzu, runtime_contract=lambda *_a,**_k: changed)
                with self.assertRaisesRegex(ValueError, "runtime contract changed"):
                    planner.validate_uzu_launch_boundary(plan)

    def test_llamacpp_rejects_artifact_change_during_check_and_before_exec(self):
        with tempfile.TemporaryDirectory(prefix="engine-llama-current-") as folder:
            generated = PrivateEngineFixture(folder)
            with generated.patches():
                plan = generated.plan("llamacpp")
                planner = make_planner(launcher)
                cap = plan.model["backends"]["llamacpp"]
                def swapped(path):
                    (path / "model.gguf").write_bytes(b"GGUF-replaced-during-validation")
                    return generated.artifact
                planner.llamacpp = replace(planner.llamacpp, artifact_contract=swapped)
                with self.assertRaisesRegex(ValueError, "changed during validation"):
                    planner._validated_llamacpp_route(plan, cap)
                planner.llamacpp = replace(planner.llamacpp, artifact_contract=lambda _path: generated.artifact)
                planner.build_engine_plan(plan)
                identities = planner.validate_llamacpp_launch_boundary(plan)
                replacement = Path(generated.binaries["llamacpp"]).with_name("replacement")
                replacement.write_bytes(b"new runtime inode")
                replacement.chmod(0o700)
                replacement.replace(generated.binaries["llamacpp"])
                with self.assertRaisesRegex(ValueError, "changed before launch"):
                    planner.confirm_llamacpp_launch_identities(plan, identities)

    def test_uzu_retained_executable_closes_on_error_and_owns_successful_handoff(self):
        for fd_execution in (False, True):
            with self.subTest(fd_execution=fd_execution), tempfile.TemporaryDirectory(prefix="engine-retained-fd-") as folder:
                generated = PrivateEngineFixture(folder)
                with generated.patches():
                    plan = generated.plan("uzu")
                    planner = make_planner(launcher)
                    planner.build_engine_plan(plan)
                    identities = planner.validate_uzu_launch_boundary(plan)
                    retained = []
                    def opened(path):
                        result = runtime_identity.open_executable_revision(Path(path))
                        retained.append(result)
                        return result
                    planner.uzu = replace(planner.uzu, open_executable=opened, confirm_open_executable=lambda _opened: None)
                    with mock.patch.object(planner, "_uzu_inherited_executable_path", side_effect=lambda value:f"/dev/fd/{value.fd}" if fd_execution else None):
                        handoff = planner.prepare_uzu_executable_launch(plan, identities)
                    self.assertIsInstance(handoff, engine_planning.UzuExecutableLaunch)
                    descriptor = handoff.opened.fd
                    os.fstat(descriptor)
                    self.assertEqual(handoff.executes_from_fd, fd_execution)
                    self.assertEqual(handoff.pass_fds, (descriptor,) if fd_execution else ())
                    self.assertEqual(handoff.argv[3], f"/dev/fd/{descriptor}" if fd_execution else generated.binaries["mirai"])
                    handoff.close(); handoff.close()
                    self.assertEqual(handoff.opened.fd, -1)
                    with self.assertRaises(OSError): os.fstat(descriptor)
                    with self.assertRaisesRegex(ValueError, "changed before launch"):
                        planner.prepare_uzu_executable_launch(plan, ("stale",))
                    self.assertEqual(retained[-1].fd, -1)

    def test_bearer_validation_and_cleanup_preserve_unrelated_files_and_symlink_targets(self):
        for case in ("uzu", "llamacpp"):
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix="engine-private-bearer-") as folder:
                generated = PrivateEngineFixture(folder)
                with generated.patches():
                    plan = generated.plan(case)
                    planner = make_planner(launcher)
                    planner.build_engine_plan(plan)
                    key_file = planner._uzu_api_key_file(plan) if case == "uzu" else planner._llamacpp_api_key_file(plan)
                    check = planner._validated_uzu_api_key_file if case == "uzu" else planner._validated_llamacpp_api_key_file
                    self.assertEqual(check(plan), key_file)
                    self.assertEqual(key_file.stat().st_mode & 0o777, 0o600)
                    key_file.chmod(0o644)
                    with self.assertRaisesRegex(ValueError, "changed before launch"): check(plan)
                    key_file.chmod(0o600)
                    other = plan.run_dir / "unrelated-note.txt"
                    other.write_text("keep this unrelated file")
                    target = generated.root / "user-owned-secret.txt"
                    target.write_text("keep this unrelated secret")
                    key_file.unlink(); key_file.symlink_to(target)
                    with self.assertRaisesRegex(ValueError, "changed before launch"): check(plan)
                    for name in ("session-proxy.json", "codex-proxy.json", "omp-settings.json"):
                        (plan.run_dir / name).write_text("generated bearer configuration")
                    plan.secrets.update(clientApiKey="surface-key", proxyControlKey="control-key")
                    plan.client_env["LLM_LAUNCHER_OMP_PROVIDER"] = "private-provider"
                    planner.dispose_plan_secrets(plan); planner.dispose_plan_secrets(plan)
                    self.assertFalse(key_file.is_symlink())
                    self.assertEqual(target.read_text(), "keep this unrelated secret")
                    self.assertEqual(other.read_text(), "keep this unrelated file")
                    self.assertFalse(any((plan.run_dir / name).exists() for name in ("session-proxy.json", "codex-proxy.json", "omp-settings.json")))
                    self.assertFalse({"apiKey", "clientApiKey", "proxyControlKey"} & plan.secrets.keys())
                    self.assertNotIn("LLM_LAUNCHER_OMP_PROVIDER", plan.client_env)

    def test_every_generated_backend_credential_file_and_env_is_disposed_without_global_changes(self):
        base_cases = ("omlx", "lmstudio", "mtplx", "uzu", "swiftlm", "mference", "slotstream",
            "kolibri", "splash", "whallm-native", "whallm-shared", "freetoken-native", "freetoken-remote", "llamacpp")
        expected_files = {
            "omlx": {"omlx/settings.json"}, "mtplx": {"mtplx-api-key"},
            "uzu": {launcher.UZU_API_KEY_FILE_NAME}, "llamacpp": {launcher.LLAMACPP_API_KEY_FILE_NAME},
            "kolibri": {"kolibri.json"}, "whallm-shared": {"whallm-bridge.json"},
            "freetoken-remote": {"freetoken-bridge.json"},
        }
        env_names = ("OMLX_API_KEY", "SPLASH_API_KEY", "DEEPSEEK_API_KEY",
            "LLM_LAUNCHER_PI_PROVIDER", "LLM_LAUNCHER_OMP_PROVIDER",
            "LLM_LAUNCHER_CODEX_API_KEY", "OPENCODE_CONFIG_CONTENT")
        for case in base_cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix="engine-secret-disposal-") as folder:
                generated = PrivateEngineFixture(folder)
                with generated.patches(), mock.patch.dict(os.environ, {key:"inherited-user-value" for key in env_names}):
                    plan = generated.plan(case)
                    planner = make_planner(launcher)
                    planner.build_engine_plan(plan)
                    before_files = {str(path.relative_to(plan.run_dir)):path.read_bytes()
                        for path in plan.run_dir.rglob("*") if path.is_file() and not path.is_symlink()}
                    sensitive = {name for name, raw in before_files.items()
                        if any(key in raw for key in (b"fixed-test-key", b"fixed-test-hex", b"generated-upstream-key"))}
                    self.assertEqual(sensitive, expected_files.get(case, set()))
                    for name in sensitive:
                        self.assertEqual((plan.run_dir/name).stat().st_mode & 0o777, 0o600)
                    unrelated = plan.run_dir / "unrelated-settings.json"
                    unrelated.write_text('{"apiKey":"fixed-test-key","userSetting":"keep"}')
                    for key in env_names[:3]: plan.engine_env[key] = "generated-plan-key"
                    plan.engine_env["KEEP_ENGINE_SETTING"] = "keep"
                    for key in env_names[3:]: plan.client_env[key] = "generated-plan-key"
                    plan.client_env["KEEP_CLIENT_SETTING"] = "keep"
                    global_before = dict(os.environ)
                    planner.dispose_plan_secrets(plan)
                    planner.dispose_plan_secrets(plan)
                    self.assertEqual(os.environ, global_before)
                    for name, raw in before_files.items():
                        if name in sensitive:
                            self.assertFalse((plan.run_dir/name).exists())
                        else:
                            self.assertEqual((plan.run_dir/name).read_bytes(), raw)
                    self.assertEqual(unrelated.read_text(), '{"apiKey":"fixed-test-key","userSetting":"keep"}')
                    self.assertEqual(plan.engine_env["KEEP_ENGINE_SETTING"], "keep")
                    self.assertEqual(plan.client_env["KEEP_CLIENT_SETTING"], "keep")
                    self.assertFalse(set(env_names[:3]) & plan.engine_env.keys())
                    self.assertFalse(set(env_names[3:]) & plan.client_env.keys())

    def test_nested_omlx_cleanup_rejects_parent_symlinks_and_unlinks_only_final_link(self):
        for parent_link in (False, True):
            with self.subTest(parent_link=parent_link), tempfile.TemporaryDirectory(prefix="engine-nested-cleanup-") as folder:
                generated = PrivateEngineFixture(folder)
                with generated.patches():
                    plan = generated.plan("omlx")
                    planner = make_planner(launcher)
                    planner.build_engine_plan(plan)
                    outside = generated.root / "unrelated-user-directory"
                    outside.mkdir()
                    target = outside / "settings.json"
                    target.write_text('{"apiKey":"user-global-key"}')
                    original = plan.run_dir / "omlx"
                    if parent_link:
                        original.rename(plan.run_dir / "retained-model-settings")
                        original.symlink_to(outside, target_is_directory=True)
                    else:
                        (original / "settings.json").unlink()
                        (original / "settings.json").symlink_to(target)
                    planner.dispose_plan_secrets(plan)
                    self.assertEqual(target.read_text(), '{"apiKey":"user-global-key"}')
                    if parent_link:
                        self.assertTrue(original.is_symlink())
                        self.assertTrue((plan.run_dir / "retained-model-settings/model_settings.json").is_file())
                    else:
                        self.assertFalse((original / "settings.json").is_symlink())
                        self.assertTrue((original / "model_settings.json").is_file())

    def test_exclusive_credential_collision_preserves_the_existing_file(self):
        for case in ("uzu", "llamacpp"):
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix="engine-key-collision-") as folder:
                generated = PrivateEngineFixture(folder)
                with generated.patches():
                    plan = generated.plan(case)
                    planner = make_planner(launcher)
                    planner.build_engine_plan(plan)
                    key_file = planner._uzu_api_key_file(plan) if case == "uzu" else planner._llamacpp_api_key_file(plan)
                    before = key_file.read_bytes()
                    identity = key_file.stat().st_ino
                    with self.assertRaisesRegex(ValueError, "Could not create"):
                        getattr(planner, "build_"+case)(plan, plan.model["backends"][case])
                    self.assertEqual(key_file.read_bytes(), before)
                    self.assertEqual(key_file.stat().st_ino, identity)

    def test_partial_credential_write_removes_only_the_inode_created_by_this_call(self):
        for case in ("uzu", "llamacpp"):
            for replacement in (False, True):
                with self.subTest(case=case, replacement=replacement), tempfile.TemporaryDirectory(prefix="engine-key-rollback-") as folder:
                    generated = PrivateEngineFixture(folder)
                    with generated.patches():
                        plan = generated.plan(case)
                        plan.run_dir.mkdir(mode=0o700)
                        planner = make_planner(launcher)
                        key_file = planner._uzu_api_key_file(plan) if case == "uzu" else planner._llamacpp_api_key_file(plan)
                        real_write = os.write
                        wrote_partial = False
                        def fail_write(fd, data):
                            nonlocal wrote_partial
                            if not wrote_partial:
                                wrote_partial = True
                                return real_write(fd, data[:2])
                            if replacement:
                                key_file.rename(plan.run_dir / "renamed-created-inode")
                                key_file.write_text("unrelated replacement, preserve\n")
                            raise OSError("generated short-write failure")
                        def fail_flush(_fd):
                            if replacement:
                                key_file.rename(plan.run_dir / "renamed-created-inode")
                                key_file.write_text("unrelated replacement, preserve\n")
                            raise OSError("generated flush failure")
                        failing = mock.patch.object(os, "write", side_effect=fail_write) if case == "uzu" else mock.patch.object(os, "fsync", side_effect=fail_flush)
                        with failing, self.assertRaisesRegex(ValueError, "Could not create"):
                            getattr(planner, "build_"+case)(plan, plan.model["backends"][case])
                        if replacement:
                            self.assertEqual(key_file.read_text(), "unrelated replacement, preserve\n")
                            self.assertTrue((plan.run_dir / "renamed-created-inode").exists())
                        else:
                            self.assertFalse(key_file.exists())
                        self.assertNotIn("apiKey", plan.secrets)

    def test_invalid_credential_filename_rejects_before_tokens_or_files(self):
        with tempfile.TemporaryDirectory(prefix="engine-key-filename-") as folder:
            generated = PrivateEngineFixture(folder)
            with generated.patches():
                plan = generated.plan("uzu")
                plan.run_dir.mkdir(mode=0o700)
                planner = make_planner(launcher)
                outside = generated.root / "outside-key"
                outside.write_text("preserve this unrelated key")
                def forbidden(*_a,**_k): raise AssertionError("Invalid credential name reached IO")
                planner.io = replace(planner.io, token_urlsafe=forbidden)
                for filename in (None, "", ".", "..", "../outside-key", str(outside), "nested/key", "bad\\key", "bad\0key", "bad\nkey"):
                    with self.subTest(filename=filename), mock.patch.object(os, "open", side_effect=forbidden):
                        with self.assertRaisesRegex(ValueError, "filename"):
                            planner._create_plan_api_key_file(plan, backend="uzu", filename=filename, label="Uzu")
                        with self.assertRaisesRegex(ValueError, "filename"):
                            planner._validated_plan_api_key_file(plan, backend="uzu", filename=filename, label="Uzu")
                    self.assertEqual(outside.read_text(), "preserve this unrelated key")
                self.assertFalse(list(plan.run_dir.iterdir()))

    def test_module_imports_no_controller_or_global_namespace_and_has_no_process_creation(self):
        tree = ast.parse(Path(engine_planning.__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                self.assertNotIn(node.id, {"BINARIES", "RunManager", "LaunchPlan"})
            if isinstance(node, ast.ImportFrom):
                self.assertNotEqual(node.module, "launcher")
            if isinstance(node, ast.Import):
                self.assertNotIn("launcher", {alias.name for alias in node.names})
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"exec", "eval", "globals", "free_port"})


if __name__ == "__main__":
    unittest.main()
