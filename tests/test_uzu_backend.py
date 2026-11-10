from __future__ import annotations
from tests.memory_fixtures import physical_snapshot, physical_telemetry

import copy
import hashlib
import importlib.util
import json
import os
import stat
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import session_proxy


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "llm_launcher_uzu_backend_tests", ROOT / "launcher.py",
)
assert SPEC and SPEC.loader
launcher = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = launcher
SPEC.loader.exec_module(launcher)


class UzuBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry_path = self.root / "registry.json"
        self.resolved_path = self.root / "resolved-models.json"
        catalog_patch = mock.patch.object(launcher, "UZU_RESOLVED_MODELS_PATH", self.resolved_path)
        catalog_patch.start()
        self.addCleanup(catalog_patch.stop)
        self.cache_root = self.root / "models" / "mirai"
        self.model_path = (
            self.cache_root
            / launcher.UZU_MODEL_REGISTRY_ID.replace(":", "-")
            / launcher.UZU_MODEL_TOOLCHAIN_VERSION
        )
        self.geometry_config = {
            "decoder_config": {
                "transformer_config": {
                    "layer_configs": [
                        {
                            "mixer_config": {
                                "type": "AttentionConfig",
                                "num_groups": 8,
                                "head_dim": 128,
                                "num_heads": 32,
                            },
                            "rope_config": {"max_sequence_length": 131_072},
                        },
                        {"mixer_config": {"type": "GatedDeltaNetConfig"}},
                        {
                            "mixer_config": {
                                "type": "AttentionConfig",
                                "num_groups": 8,
                                "head_dim": 128,
                                "num_heads": 32,
                            },
                            "rope_config": {"max_sequence_length": 262_144},
                        },
                    ]
                }
            },
            "generation_config": {"temperature": 0.6, "top_p": 0.95},
        }
        self.file_payloads = {
            "config.json": json.dumps(
                self.geometry_config, separators=(",", ":"),
            ).encode("utf-8"),
            "model.safetensors": b"target-model",
            "speculator/config.json": b'{"kind":"dflash"}',
            "speculator/model.safetensors": b"draft-model",
            "speculator/shapes.json": b'{"depth":1}',
            "tokenizer.json": b'{"version":"test"}',
        }
        self.manifest = tuple(
            (name, len(payload), f"test-crc-{index}")
            for index, (name, payload) in enumerate(self.file_payloads.items())
        )
        self.file_sha256 = {
            name: hashlib.sha256(payload).hexdigest()
            for name, payload in self.file_payloads.items()
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    @contextmanager
    def patched_cache_globals(self):
        with mock.patch.multiple(
            launcher,
            UZU_MODEL_REGISTRY_PATH=self.registry_path,
            UZU_MODEL_CACHE_ROOT=self.cache_root,
            UZU_MODEL_FILE_MANIFEST=self.manifest,
            UZU_MODEL_FILE_SHA256=self.file_sha256,
        ):
            yield

    def registry_entry(self) -> dict:
        files = [
            {
                "name": name,
                "size": size,
                "hashes": [{"method": "crc32c", "value": crc}],
                "url": f"https://assets.trymirai.com/test/{name}",
            }
            for name, size, crc in self.manifest
        ]
        return {
            "id": launcher.UZU_MODEL_REGISTRY_ID,
            "encoding": {"name": "qwen3.5", "type": "hanashi"},
            "family": {
                "id": "alibaba:qwen3.6",
                "vendor": {"id": "alibaba"},
            },
            "properties": {
                "id": "27b",
                "size": 27_000_000_000,
                "version": None,
            },
            "quantization": {
                "bits_per_weight": 4,
                "id": "mirai:mirai-m:4",
                "method": "mirai-m",
                "vendor": {"id": "mirai"},
            },
            "registry": {"id": "mirai"},
            "specializations": [{"type": "chat"}],
            "accessibility": {
                "type": "local",
                "reference": {
                    "type": "mirai",
                    "toolchain_version": launcher.UZU_MODEL_TOOLCHAIN_VERSION,
                    "repository": {
                        "identifier": launcher.UZU_MODEL_REPOSITORY,
                        "commit_hash": launcher.UZU_MODEL_COMMIT,
                    },
                    "files": files,
                },
            },
            "backends": [
                {"id": "uzu", "version": launcher.UZU_MODEL_TOOLCHAIN_VERSION},
            ],
        }

    def write_registry(self, entry: dict | None = None) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(
            json.dumps([entry or self.registry_entry()]), encoding="utf-8",
        )

    def write_cache(
        self, *, omit: str | None = None, wrong_size: str | None = None,
        wrong_crc: str | None = None,
    ) -> None:
        self.model_path.mkdir(parents=True, exist_ok=True)
        for name, size, crc in self.manifest:
            path = self.model_path.joinpath(*name.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            if name == omit:
                partial = path.with_suffix(".part")
                partial.write_bytes(self.file_payloads[name][: max(1, size // 2)])
                continue
            payload = self.file_payloads[name]
            if name == wrong_size:
                payload += b"x"
            path.write_bytes(payload)
            receipt = {
                "version": 1,
                "file_size": size,
                "crc": "wrong-crc" if name == wrong_crc else crc,
            }
            Path(str(path) + ".crc").write_text(
                json.dumps(receipt), encoding="utf-8",
            )

    def runtime_fixture(self) -> tuple[Path, Path, str]:
        runtime = self.root / "runtimes" / f"uzu-{launcher.UZU_RUNTIME_TAG}" / "mirai"
        runtime.parent.mkdir(parents=True, mode=launcher.UZU_RUNTIME_DIRECTORY_MODE)
        runtime.write_bytes(b"pinned-hardened-uZu-test-binary")
        runtime.chmod(0o500)
        sandbox = self.root / "sandbox-exec"
        sandbox.write_bytes(b"test sandbox")
        sandbox.chmod(0o500)
        sha256 = hashlib.sha256(runtime.read_bytes()).hexdigest()
        return runtime, sandbox, sha256

    def qualification_fixture(
        self, context: int = 16_384,
    ) -> tuple[dict, dict, Path]:
        """Return one future-safe, controller-scanned Uzu route contract."""
        binary = self.root / f"mirai-qualified-{context}"
        binary.write_bytes(b"qualified Uzu runtime")
        binary.chmod(0o500)
        fingerprint = "a" * 64
        capability = {
            "runnable": True,
            "reason": "Pinned route ready for qualification.",
            "agentReasoning": ["auto"],
            "codexReasoning": ["auto"],
            "customSampling": False,
            "implicitSamplingDefaultsVerified": True,
            "samplingReason": "Packaged model defaults are fixed.",
            "contextWindows": list(launcher.UZU_SAFE_CONTEXT_WINDOWS),
            "contextMaximum": max(launcher.UZU_SAFE_CONTEXT_WINDOWS),
            "modelRegistryId": launcher.UZU_MODEL_REGISTRY_ID,
            "modelRepository": launcher.UZU_MODEL_REPOSITORY,
            "modelCommit": launcher.UZU_MODEL_COMMIT,
            "modelToolchainVersion": launcher.UZU_MODEL_TOOLCHAIN_VERSION,
            "benchmarkModelFingerprint": fingerprint,
            "receiptFingerprint": fingerprint,
            "runtimeVersion": "Uzu fixed-test",
            "runtimeIdentity": {
                "ready": True,
                "binary": {
                    "sha256": launcher.UZU_RUNTIME_RELEASE_BINARY_SHA256,
                    "size": launcher.UZU_RUNTIME_RELEASE_BINARY_SIZE,
                },
                "upstreamCommit": launcher.UZU_RUNTIME_UPSTREAM_COMMIT,
                "sourcePatchSha256": launcher.UZU_RUNTIME_SOURCE_PATCH_SHA256,
                "networkSandbox": True,
                "binaryIdentityPinned": True,
                "memorySafetyBlocked": False,
                "rawListenerAuthenticated": True,
                "rawListenerIsolated": False,
                "listenerIsolationBlocked": False,
                "boundedContextReady": True,
                "nativeBoundaryContractId": launcher.UZU_NATIVE_BOUNDARY_CONTRACT_ID,
                "nativeBearerAuthentication": True,
                "oneUseApiKeyFile": True,
                "nativeContextLimit": True,
                "nativeOutputLimit": True,
            },
            "qualificationSystemContract": {
                "osReserveBytes": max(
                    launcher.SESSION_OS_RESERVE_MIN_BYTES,
                    round(48 * 1024**3 * launcher.SESSION_OS_RESERVE_FRACTION),
                ),
                "sandboxProfileSha256": launcher.UZU_SANDBOX_PROFILE_SHA256,
                "rawListenerProtected": True,
                "nativeBoundaryContractId": launcher.UZU_NATIVE_BOUNDARY_CONTRACT_ID,
                "nativeBearerAuthentication": True,
                "oneUseApiKeyFile": True,
                "nativeContextLimit": True,
                "nativeOutputLimit": True,
            },
            "runtimeManagedAcceleration": "DFlash + Weaver",
            "runtimeManagedAccelerationReady": True,
            "mtp": False,
            "dflash": False,
            "kv": False,
            "depth": 1,
            "depthMax": 1,
        }
        model = {
            "id": "uzu-qualified",
            "name": "Qwen3.6 27B · Uzu DFlash + Weaver",
            "path": str(self.model_path),
            "ready": True,
            "nativeContext": 262_144,
            "architectureNativeContext": 262_144,
            "uzuNative": True,
            "defaultSampling": {"temperature": 0.6, "top_p": 0.95},
            "backends": {"uzu": capability},
        }
        payload = {
            "backend": "uzu",
            "client": "chat",
            "modelId": model["id"],
            "project": str(self.root),
            "context": context,
            "output": 4_096,
            "reasoning": "auto",
            "mode": "custom",
            "suite": "quick",
            "enginePreference": "throughput",
            "options": {"acceleration": "off", "depth": 1, "kv": "off"},
            "chat": {"systemPrompt": "", "sampling": "model"},
        }
        return model, payload, binary

    def qualification_record(
        self, spec: dict, *, context: int = 16_384, configured_output: int = 4096,
    ) -> dict:
        total_memory = 48 * 1024**3
        minimum_headroom = 12.0
        suite = launcher.BENCHMARK_SUITES[spec["suite"]]
        prefix_tokens = int(suite["prefixTokens"])
        tool_tokens = int(suite["toolTokens"])
        prompt_targets = [
            prefix_tokens,
            prefix_tokens,
            prefix_tokens + tool_tokens,
            prefix_tokens + tool_tokens,
        ]
        samples = []
        for index, scenario in enumerate(launcher.ROUTE_QUALIFICATION_SCENARIOS):
            prompt_targets[index] = launcher.uzu_conversation_target(
                scenario, prompt_targets[index], samples[-1] if samples else None,
                context, launcher.UZU_QUALIFICATION_SAMPLE_MAX_TOKENS,
            )
            ttft = 0.5 + index * 0.05
            decode_tps = 30.0 + index
            samples.append({
                "scenario": scenario,
                "scenarioLabel": scenario,
                "cacheExpected": index > 0,
                "targetPromptTokens": prompt_targets[index],
                "repetition": 1,
                "promptTokens": prompt_targets[index],
                "authoritativeUsage": True,
                "completionTokens": 256,
                "requestedMaxTokens": launcher.uzu_qualification_request_tokens(
                    scenario, prompt_targets[index], context, min(configured_output, launcher.UZU_QUALIFICATION_SAMPLE_MAX_TOKENS),
                ),
                "ttftSeconds": ttft,
                "totalSeconds": round(ttft + 255 / decode_tps, 6),
                "decodeTokensPerSecond": decode_tps,
                "endToEndTokensPerSecond": 25.0 + index,
                "reasoningObserved": True,
                "answerObserved": True,
                "finishReason": "stop",
                "terminalState": "complete",
                "terminalComplete": True,
                "responseLimitReached": False,
                "outputHash": f"uzu-sample-{index}",
            })
        expected_answer = b"RQ-UZU-742"
        return {
            "id": "uzu-qualification-record",
            "createdAt": (
                datetime.now(timezone.utc) - timedelta(minutes=2)
            ).isoformat(),
            "scope": "local",
            "kind": "route-qualification",
            "qualificationVersion": launcher.ROUTE_QUALIFICATION_VERSION,
            "backend": "uzu",
            "modelId": "uzu-qualified",
            "modelName": "Qwen3.6 27B · Uzu DFlash + Weaver",
            "modelFingerprint": "a" * 64,
            "runtimeVersion": "Uzu fixed-test",
            "hardwareFingerprint": "uzu-test-mac",
            "suite": spec["suite"],
            "workloadKind": "agentic",
            "scenarioContract": list(launcher.ROUTE_QUALIFICATION_SCENARIOS),
            "client": "chat",
            "reasoning": "auto",
            "targetKV": "off",
            "samplingFingerprint": "c" * 64,
            "contextMin": context,
            "contextMax": context,
            "outputMin": min(s["requestedMaxTokens"] for s in samples),
            "outputMax": max(s["requestedMaxTokens"] for s in samples),
            "configuredOutputLimit": configured_output,
            "measuredRequestMaxTokens": max(s["requestedMaxTokens"] for s in samples),
            "comparedModes": ["ar"],
            "winner": "ar",
            "baselinePassed": True,
            "qualificationContract": {
                "id": spec["id"],
                "version": spec["version"],
                "scope": "route",
                "clientAgnostic": False,
                "client": "chat",
                "backend": "uzu",
                "exactContext": context,
                "scenarioContract": list(launcher.ROUTE_QUALIFICATION_SCENARIOS),
                "sampleMaxTokens": min(configured_output, launcher.UZU_QUALIFICATION_SAMPLE_MAX_TOKENS),
                "outputBudgetPolicy": launcher.uzu_qualification_output_policy(configured_output),
                "answerReserveTokens": launcher.ROUTE_QUALIFICATION_ANSWER_RESERVE_TOKENS,
                "minimumCompletionTokens": launcher.ROUTE_QUALIFICATION_MINIMUM_COMPLETION_TOKENS,
                "minimumDecodeTokensPerSecond": launcher.UZU_QUALIFICATION_MINIMUM_DECODE_TPS,
                "thinkingBudgetTokens": None,
                "configuredOutputLimit": configured_output,
                "measuredRequestMaxTokens": min(configured_output, launcher.UZU_QUALIFICATION_SAMPLE_MAX_TOKENS),
                "reasoningPolicy": spec["reasoningPolicy"],
                "toolProbeRequired": False,
                "memoryProofRequired": True,
                "memorySemanticsVersion": 2,
                "memoryCeilingBytes": launcher.UZU_PROCESS_MEMORY_CEILING_BYTES,
                "modelFingerprint": "a" * 64,
                "modelRegistryId": launcher.UZU_MODEL_REGISTRY_ID,
                "modelCommit": launcher.UZU_MODEL_COMMIT,
                "modelToolchainVersion": launcher.UZU_MODEL_TOOLCHAIN_VERSION,
                "runtimeBinarySha256": launcher.UZU_RUNTIME_RELEASE_BINARY_SHA256,
                "runtimeBinarySize": launcher.UZU_RUNTIME_RELEASE_BINARY_SIZE,
                "runtimeUpstreamCommit": launcher.UZU_RUNTIME_UPSTREAM_COMMIT,
                "runtimeSourcePatchSha256": launcher.UZU_RUNTIME_SOURCE_PATCH_SHA256,
                "fixedAcceleration": "DFlash + Weaver",
                "kvStateDataType": "BF16",
                "prefixCache": True,
                "promptExercisePolicy": (
                    launcher.uzu_qualification_prompt_exercise_policy(context)
                ),
                "osReservePolicy": "max-4gib-or-10-percent-total-v1",
                "osReserveMinimumBytes": launcher.SESSION_OS_RESERVE_MIN_BYTES,
                "osReserveBytes": max(
                    launcher.SESSION_OS_RESERVE_MIN_BYTES,
                    round(total_memory * launcher.SESSION_OS_RESERVE_FRACTION),
                ),
                "receiptFingerprint": "a" * 64,
                "runtimeVersion": "Uzu fixed-test",
                "sandboxProfileSha256": hashlib.sha256(
                    launcher.UZU_NETWORK_SANDBOX_PROFILE.encode("utf-8")
                ).hexdigest(),
                "rawListenerProtected": True,
                "nativeBoundaryContractId": launcher.UZU_NATIVE_BOUNDARY_CONTRACT_ID,
                "nativeBearerAuthentication": True,
                "oneUseApiKeyFile": True,
                "nativeContextLimitTokens": context,
                "nativeMaxOutputTokens": configured_output,
            },
            "correctnessContract": {
                "id": getattr(
                    launcher, "UZU_QUALIFICATION_CORRECTNESS_ID",
                    "qwen36-uzu-dflash-weaver-correctness-v1",
                ),
                "expectedAnswerSha256": hashlib.sha256(expected_answer).hexdigest(),
                "observedAnswerSha256": hashlib.sha256(expected_answer).hexdigest(),
                "exact": True,
                "terminalComplete": True,
                "authoritativeUsage": True,
            },
            "unloadEvidence": {
                "clean": True,
                "processExited": True,
                "processGroupExited": True,
                "managerIdle": True,
                "portsClosed": True,
                "checkedPorts": [18_080],
                "closedPorts": [18_080],
            },
            "modes": {
                "ar": {
                    "samples": samples,
                    "medianDecodeTokensPerSecond": 31.5,
                    "resourceTelemetry": physical_telemetry({
                        "version": 1,
                        "samplingComplete": True,
                        "sampleCount": 8,
                        "memoryAvailable": True,
                        "memorySampleCount": 8,
                        "memorySource": "memory_pressure -Q",
                        "totalMemoryBytes": total_memory,
                        "baselineHeadroomPercent": 30.0,
                        "minimumHeadroomPercent": minimum_headroom,
                        "peakPressureDeltaBytes": round(
                            total_memory * (30.0 - minimum_headroom) / 100
                        ),
                        "processFootprintAvailable": True,
                        "processFootprintSource": "proc_pid_rusage RUSAGE_INFO_V4",
                        "processAliveSampleCount": 8,
                        "processFootprintSampleCount": 8,
                        "peakProcessPhysicalFootprintBytes": 20 * 1024**3,
                        "processGroupFootprintAvailable": True,
                        "processGroupFootprintSampleCount": 8,
                        "processGroupMemberCountMinimum": 1,
                        "processGroupMemberCountMaximum": 1,
                        "peakProcessGroupPhysicalFootprintBytes": 21 * 1024**3,
                    }),
                },
            },
        }

    def bind_qualification_record(
        self, model: dict, payload: dict, record: dict, spec: dict,
    ) -> None:
        evidence = launcher.optimizer_evidence(
            model, int(record["contextMin"]), int(payload["output"]),
            str(payload["client"]), str(payload["reasoning"]),
            str(payload["options"]["kv"]), payload["chat"],
        )
        record["samplingFingerprint"] = evidence["samplingFingerprint"]
        record.update(launcher.sampling_record_evidence(evidence))
        record["modes"]["ar"]["agenticMetrics"] = {
            "cacheTelemetryAvailable": True,
            "coldTTFTSeconds": 1.0,
            "warmPrefixTTFTSeconds": 0.8,
            "prefixReuseFactor": 1.25,
            "toolIngestTTFTSeconds": 0.9,
            "steadyTurnTTFTSeconds": 0.7,
            "toolReuseFactor": 1.2,
        }
        metrics = launcher.route_qualification_metrics(record, spec)
        self.assertIsNotNone(metrics)
        record["qualification"] = {
            "reasoningEnabled": True,
            "reasoningObserved": True,
            "answerObserved": True,
            "terminalCompletionObserved": True,
            "authoritativeUsage": True,
            "metrics": metrics,
        }
        model["backends"]["uzu"]["localBenchmarks"] = [record]
        model["backends"]["uzu"]["localBenchmark"] = record

    def test_runtime_contract_accepts_only_exact_hardened_build(self) -> None:
        runtime, sandbox, sha256 = self.runtime_fixture()
        with (
            mock.patch.multiple(
                launcher,
                UZU_RUNTIME_PATH=runtime,
                UZU_RUNTIME_RELEASE_BINARY_SHA256=sha256,
                UZU_RUNTIME_RELEASE_BINARY_SIZE=runtime.stat().st_size,
                UZU_SANDBOX_EXECUTABLE=sandbox,
            ),
            mock.patch.object(launcher.sys, "platform", "darwin"),
            mock.patch.object(launcher.platform, "machine", return_value="arm64"),
        ):
            contract = launcher.uzu_runtime_contract(runtime)

        self.assertTrue(contract["ready"])
        self.assertEqual(contract["version"], f"Uzu {launcher.UZU_RUNTIME_TAG}")
        self.assertEqual(contract["binary"]["sha256"], sha256)
        self.assertTrue(contract["binaryIdentityPinned"])
        self.assertEqual(contract["upstreamCommit"], launcher.UZU_RUNTIME_UPSTREAM_COMMIT)
        self.assertEqual(contract["sourcePatchSha256"], launcher.UZU_RUNTIME_SOURCE_PATCH_SHA256)
        self.assertNotIn("publisherSignatureValid", contract)
        self.assertNotIn("notarizationVerified", contract)
        self.assertTrue(contract["networkSandbox"])
        self.assertFalse(contract["memorySafetyBlocked"])
        self.assertTrue(contract["boundedContextReady"])
        self.assertTrue(contract["localOnly"])
        self.assertTrue(contract["telemetryBlocked"])
        self.assertTrue(contract["automaticDownloadsBlocked"])
        self.assertTrue(contract["rawListenerAuthenticated"])
        self.assertFalse(contract["rawListenerIsolated"])
        self.assertFalse(contract["listenerIsolationBlocked"])
        self.assertTrue(contract["nativeBearerAuthentication"])
        self.assertTrue(contract["oneUseApiKeyFile"])
        self.assertTrue(contract["nativeContextLimit"])
        self.assertTrue(contract["nativeOutputLimit"])
        self.assertEqual(
            contract["nativeBoundaryContractId"],
            launcher.UZU_NATIVE_BOUNDARY_CONTRACT_ID,
        )
        reason = contract["reason"].lower()
        self.assertIn("native bearer", reason)
        self.assertNotIn("signed", reason)
        self.assertNotIn("notarized", reason)

    def test_runtime_path_rejects_missing_or_blank_values_as_not_installed(self) -> None:
        for path_value in (None, "", "   \t"):
            with self.subTest(path_value=path_value):
                with self.assertRaisesRegex(
                    ValueError,
                    "launcher-managed Uzu executable is not installed",
                ):
                    launcher._uzu_runtime_path(path_value)

                contract = launcher.uzu_runtime_contract(path_value)
                self.assertFalse(contract["ready"])
                self.assertIn("not installed", contract["reason"])

    def test_runtime_candidate_uses_exact_label_only_for_pinned_bytes(self) -> None:
        runtime, sandbox, sha256 = self.runtime_fixture()
        candidate = {
            "id": "managed-uzu-fixture",
            "runtime": "mirai",
            "path": str(runtime),
            "resolvedPath": str(runtime.resolve()),
            "channel": "launcher-managed",
            "channelLabel": "Launcher-managed Uzu fixture",
        }

        def details(expected_sha256: str) -> dict:
            with (
                mock.patch.multiple(
                    launcher,
                    UZU_RUNTIME_PATH=runtime,
                    UZU_RUNTIME_RELEASE_BINARY_SHA256=expected_sha256,
                    UZU_RUNTIME_RELEASE_BINARY_SIZE=runtime.stat().st_size,
                    UZU_SANDBOX_EXECUTABLE=sandbox,
                ),
                mock.patch.object(launcher.sys, "platform", "darwin"),
                mock.patch.object(launcher.platform, "machine", return_value="arm64"),
                mock.patch.dict(launcher.BINARIES, {"mirai": str(runtime)}, clear=True),
                mock.patch.object(
                    launcher.runtime_catalog.RuntimeCatalog,
                    "runtime_candidates", return_value=[candidate],
                ),
                mock.patch.object(
                    launcher,
                    "command_version",
                    side_effect=AssertionError("an unverified Uzu candidate was executed"),
                ) as command,
            ):
                result = launcher.runtime_candidate_details("mirai")
            command.assert_not_called()
            self.assertEqual(len(result), 1)
            return result[0]

        unverified = details("0" * 64)
        self.assertEqual(
            unverified["version"],
            "Installed (unverified managed runtime)",
        )
        self.assertFalse(unverified["uzuContract"]["binaryIdentityPinned"])

        verified = details(sha256)
        self.assertEqual(verified["version"], f"Uzu {launcher.UZU_RUNTIME_TAG}")
        self.assertTrue(verified["uzuContract"]["binaryIdentityPinned"])

    def test_listener_protection_requires_positive_proof_and_no_open_gate(self) -> None:
        self.assertTrue(launcher.uzu_listener_protection_ready({
            "rawListenerAuthenticated": True,
            "rawListenerIsolated": False,
            "listenerIsolationBlocked": False,
        }))
        self.assertTrue(launcher.uzu_listener_protection_ready({
            "rawListenerAuthenticated": False,
            "rawListenerIsolated": True,
            "listenerIsolationBlocked": False,
        }))
        self.assertFalse(launcher.uzu_listener_protection_ready({
            "rawListenerAuthenticated": True,
            "rawListenerIsolated": False,
            "listenerIsolationBlocked": True,
        }))
        self.assertFalse(launcher.uzu_listener_protection_ready({
            "rawListenerAuthenticated": False,
            "rawListenerIsolated": False,
            "listenerIsolationBlocked": False,
        }))

    def test_runtime_contract_rejects_wrong_hash_symlink_and_unmanaged_path(self) -> None:
        runtime, sandbox, sha256 = self.runtime_fixture()
        wrong_path = self.root / "other-mirai"
        wrong_path.write_bytes(runtime.read_bytes())
        wrong_path.chmod(0o500)
        symlink = self.root / "mirai-link"
        symlink.symlink_to(runtime)
        cases = (
            (runtime, "0" * 64, "no longer matches the pinned hardened"),
            (symlink, sha256, "must not be a symbolic link"),
            (wrong_path, sha256, "Only the launcher-managed hardened Uzu"),
        )
        for requested, expected_hash, expected_reason in cases:
            with self.subTest(reason=expected_reason):
                with (
                    mock.patch.multiple(
                        launcher,
                        UZU_RUNTIME_PATH=runtime,
                        UZU_RUNTIME_RELEASE_BINARY_SHA256=expected_hash,
                        UZU_RUNTIME_RELEASE_BINARY_SIZE=runtime.stat().st_size,
                        UZU_SANDBOX_EXECUTABLE=sandbox,
                    ),
                    mock.patch.object(launcher.sys, "platform", "darwin"),
                    mock.patch.object(
                        launcher.platform, "machine", return_value="arm64",
                    ),
                ):
                    contract = launcher.uzu_runtime_contract(requested)
                self.assertFalse(contract["ready"])
                self.assertIn(expected_reason, contract["reason"])

    def test_runtime_contract_requires_exact_owner_only_install_modes(self) -> None:
        runtime, sandbox, sha256 = self.runtime_fixture()
        patches = (
            mock.patch.multiple(
                launcher,
                UZU_RUNTIME_PATH=runtime,
                UZU_RUNTIME_RELEASE_BINARY_SHA256=sha256,
                UZU_RUNTIME_RELEASE_BINARY_SIZE=runtime.stat().st_size,
                UZU_SANDBOX_EXECUTABLE=sandbox,
            ),
            mock.patch.object(launcher.sys, "platform", "darwin"),
            mock.patch.object(launcher.platform, "machine", return_value="arm64"),
        )
        runtime.parent.chmod(0o755)
        with patches[0], patches[1], patches[2]:
            contract = launcher.uzu_runtime_contract(runtime)
        self.assertFalse(contract["ready"])
        self.assertIn("owner-only mode 0700", contract["reason"])

        runtime.parent.chmod(launcher.UZU_RUNTIME_DIRECTORY_MODE)
        runtime.chmod(0o700)
        with (
            mock.patch.multiple(
                launcher,
                UZU_RUNTIME_PATH=runtime,
                UZU_RUNTIME_RELEASE_BINARY_SHA256=sha256,
                UZU_RUNTIME_RELEASE_BINARY_SIZE=runtime.stat().st_size,
                UZU_SANDBOX_EXECUTABLE=sandbox,
            ),
            mock.patch.object(launcher.sys, "platform", "darwin"),
            mock.patch.object(launcher.platform, "machine", return_value="arm64"),
        ):
            contract = launcher.uzu_runtime_contract(runtime)
        self.assertFalse(contract["ready"])
        self.assertIn("owner-executable mode 0500", contract["reason"])

    def test_runtime_contract_rejects_hardlinks_and_writable_ancestors(self) -> None:
        runtime, sandbox, sha256 = self.runtime_fixture()

        def contract() -> dict:
            with (
                mock.patch.multiple(
                    launcher,
                    UZU_RUNTIME_PATH=runtime,
                    UZU_RUNTIME_RELEASE_BINARY_SHA256=sha256,
                    UZU_RUNTIME_RELEASE_BINARY_SIZE=runtime.stat().st_size,
                    UZU_SANDBOX_EXECUTABLE=sandbox,
                ),
                mock.patch.object(launcher.sys, "platform", "darwin"),
                mock.patch.object(launcher.platform, "machine", return_value="arm64"),
            ):
                return launcher.uzu_runtime_contract(runtime)

        second_name = runtime.with_name("mirai-hardlink")
        os.link(runtime, second_name)
        hardlinked = contract()
        self.assertFalse(hardlinked["ready"])
        self.assertIn("exactly one filesystem link", hardlinked["reason"])

        second_name.unlink()
        unsafe_ancestor = runtime.parent.parent
        original_mode = stat.S_IMODE(unsafe_ancestor.stat().st_mode)
        unsafe_ancestor.chmod(0o770)
        try:
            writable = contract()
        finally:
            unsafe_ancestor.chmod(original_mode)
        self.assertFalse(writable["ready"])
        self.assertIn("writable or untrusted directory ancestor", writable["reason"])

    def test_runtime_hash_rejects_a_file_changed_during_descriptor_read(self) -> None:
        runtime, sandbox, sha256 = self.runtime_fixture()
        real_read = os.read
        changed = False

        def mutate_then_read(descriptor: int, size: int) -> bytes:
            nonlocal changed
            if not changed:
                changed = True
                runtime.chmod(0o700)
            return real_read(descriptor, size)

        try:
            with (
                mock.patch.multiple(
                    launcher,
                    UZU_RUNTIME_PATH=runtime,
                    UZU_RUNTIME_RELEASE_BINARY_SHA256=sha256,
                    UZU_RUNTIME_RELEASE_BINARY_SIZE=runtime.stat().st_size,
                    UZU_SANDBOX_EXECUTABLE=sandbox,
                ),
                mock.patch.object(launcher.os, "read", side_effect=mutate_then_read),
            ):
                contract = launcher.uzu_runtime_contract(runtime)
        finally:
            runtime.chmod(launcher.UZU_RUNTIME_BINARY_MODE)
        self.assertTrue(changed)
        self.assertFalse(contract["ready"])
        self.assertIn("changed while it was being identified", contract["reason"])

    def test_retained_runtime_fd_detects_a_replaced_path(self) -> None:
        runtime, _sandbox, _sha256 = self.runtime_fixture()
        with mock.patch.object(launcher, "UZU_RUNTIME_PATH", runtime):
            opened = launcher._open_uzu_runtime_executable(runtime)
        try:
            displaced = runtime.with_name("mirai-displaced")
            runtime.rename(displaced)
            runtime.write_bytes(displaced.read_bytes())
            runtime.chmod(launcher.UZU_RUNTIME_BINARY_MODE)
            with self.assertRaisesRegex(ValueError, "changed immediately before launch"):
                launcher._confirm_open_uzu_executable(opened)
        finally:
            opened.close()

    @unittest.skipUnless(sys.platform == "darwin", "macOS /dev/fd semantics")
    def test_current_macos_does_not_claim_executable_dev_fd_support(self) -> None:
        runtime, _sandbox, _sha256 = self.runtime_fixture()
        with mock.patch.object(launcher, "UZU_RUNTIME_PATH", runtime):
            opened = launcher._open_uzu_runtime_executable(runtime)
        try:
            if os.access(f"/dev/fd/{opened.fd}", os.X_OK):
                self.skipTest("this macOS host exposes executable descriptor paths")
            self.assertIsNone(launcher._uzu_inherited_executable_path(opened))
        finally:
            opened.close()

    def test_checked_in_hardening_patch_matches_pinned_digest(self) -> None:
        root = ROOT / "runtime_patches" / "uzu" / "0.5.23"
        patches = [root / name for name in launcher.UZU_RUNTIME_SOURCE_PATCHES]
        self.assertTrue(all(patch.is_file() for patch in patches))
        self.assertEqual(
            hashlib.sha256(b"".join(patch.read_bytes() for patch in patches)).hexdigest(),
            launcher.UZU_RUNTIME_SOURCE_PATCH_SHA256,
        )

    def test_frontend_and_controller_share_exact_qualified_binary_identity(self) -> None:
        script = (ROOT / "app.js").read_text()
        for name in ("UZU_RUNTIME_RELEASE_BINARY_SHA256", "UZU_RUNTIME_UPSTREAM_COMMIT",
                     "UZU_RUNTIME_SOURCE_PATCH_SHA256"):
            self.assertIn(f'const {name} = "{getattr(launcher, name)}";', script)
        size_literal = script.split("const UZU_RUNTIME_RELEASE_BINARY_SIZE = ", 1)[1].split(";", 1)[0]
        self.assertEqual(int(size_literal.replace("_", "")), launcher.UZU_RUNTIME_RELEASE_BINARY_SIZE)

    def test_offline_catalog_uses_only_verified_local_files(self) -> None:
        self.write_registry()
        self.write_cache()
        with self.patched_cache_globals():
            cache = launcher._uzu_model_cache_contract()
            self.assertFalse(self.resolved_path.exists(), "Scanning must stay read-only")
            launcher._ensure_uzu_offline_catalog(cache)
            first = self.resolved_path.read_bytes()
            catalog = json.loads(first)
            self.assertEqual(catalog["version"], 2)
            self.assertIsNone(catalog["models"][0]["files"])
            model = catalog["models"][0]["model"]
            self.assertEqual(model["accessibility"], {
                "type": "on_device", "source": {
                    "type": "filesystem", "path": str(self.model_path.resolve()),
                },
            })
            self.assertEqual(model["encoding"], self.registry_entry()["encoding"])
            self.assertEqual(model["backends"], self.registry_entry()["backends"])
            self.assertEqual(stat.S_IMODE(self.resolved_path.stat().st_mode), 0o600)
            launcher._ensure_uzu_offline_catalog(cache)
            self.assertEqual(self.resolved_path.read_bytes(), first)
            model["accessibility"]["source"]["path"] = "/wrong/model"
            self.resolved_path.write_text(json.dumps(catalog))
            changed = self.resolved_path.read_bytes()
            with self.assertRaisesRegex(ValueError, "not been overwritten"):
                launcher._ensure_uzu_offline_catalog(cache)
            self.assertEqual(self.resolved_path.read_bytes(), changed)

    def test_offline_catalog_rejects_symlinks_and_unverified_models(self) -> None:
        self.write_registry()
        self.write_cache()
        with self.patched_cache_globals():
            cache = launcher._uzu_model_cache_contract()
            with self.assertRaisesRegex(ValueError, "Verified"):
                launcher._ensure_uzu_offline_catalog({**cache, "ready": False})
            target = self.root / "untouched.json"
            target.write_text("{}")
            self.resolved_path.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "not been overwritten"):
                launcher._ensure_uzu_offline_catalog(cache)
            self.assertEqual(target.read_text(), "{}")

    def test_complete_model_cache_requires_exact_files_and_receipts(self) -> None:
        self.write_registry()
        self.write_cache()
        with self.patched_cache_globals():
            contract = launcher._uzu_model_cache_contract()

        self.assertIsNotNone(contract)
        assert contract is not None
        self.assertTrue(contract["present"])
        self.assertTrue(contract["ready"])
        self.assertEqual(contract["path"], str(self.model_path.resolve()))
        self.assertEqual(contract["completedBytes"], sum(item[1] for item in self.manifest))
        self.assertEqual(contract["completedBytes"], contract["totalBytes"])
        self.assertEqual(contract["progressPercent"], 100.0)
        self.assertEqual(contract["problems"], [])
        self.assertEqual(contract["config"], self.geometry_config)
        self.assertRegex(contract["fingerprint"], r"^[0-9a-f]{64}$")
        self.assertEqual(contract["manifestIdentity"]["schema"], 2)
        self.assertEqual(
            contract["manifestIdentity"]["registryOperationalContract"],
            launcher.UZU_MODEL_REGISTRY_OPERATIONAL_CONTRACT,
        )
        self.assertEqual(
            [item["name"] for item in contract["manifestIdentity"]["files"]],
            [item[0] for item in self.manifest],
        )

    def test_model_cache_rejects_changed_registry_operational_contract(self) -> None:
        self.write_cache()
        mutations = (
            (
                "encoding",
                lambda entry: entry["encoding"].__setitem__("type", "mlx"),
            ),
            (
                "family",
                lambda entry: entry["family"]["vendor"].__setitem__(
                    "id", "other-vendor",
                ),
            ),
            (
                "properties",
                lambda entry: entry["properties"].__setitem__(
                    "size", 26_000_000_000,
                ),
            ),
            (
                "quantization",
                lambda entry: entry["quantization"].__setitem__(
                    "bits_per_weight", 8,
                ),
            ),
            (
                "registry",
                lambda entry: entry["registry"].__setitem__("id", "other"),
            ),
            (
                "specializations",
                lambda entry: entry.__setitem__(
                    "specializations", [{"type": "completion"}],
                ),
            ),
        )

        with self.patched_cache_globals():
            for field, mutate in mutations:
                with self.subTest(field=field):
                    entry = self.registry_entry()
                    mutate(entry)
                    self.write_registry(entry)
                    contract = launcher._uzu_model_cache_contract()

                    self.assertIsNotNone(contract)
                    assert contract is not None
                    self.assertFalse(contract["ready"])
                    self.assertIn(
                        "changed the pinned model's encoding",
                        contract["reason"],
                    )

    def test_model_cache_rejects_ambiguous_backend_and_repository_paths(self) -> None:
        self.write_cache()
        mutations = (
            (
                "duplicate Uzu backend",
                lambda entry: entry["backends"].append(
                    copy.deepcopy(entry["backends"][0])
                ),
            ),
            (
                "extra backend",
                lambda entry: entry["backends"].append({
                    "id": "other", "version": "1.0.0",
                }),
            ),
            (
                "repository paths",
                lambda entry: entry["accessibility"]["reference"][
                    "repository"
                ].__setitem__("paths", ["alternate"]),
            ),
        )

        with self.patched_cache_globals():
            for label, mutate in mutations:
                with self.subTest(label=label):
                    entry = self.registry_entry()
                    mutate(entry)
                    self.write_registry(entry)
                    contract = launcher._uzu_model_cache_contract()

                    self.assertIsNotNone(contract)
                    assert contract is not None
                    self.assertFalse(contract["ready"])
                    self.assertIn(
                        "no longer matches the pinned Uzu model contract",
                        contract["reason"],
                    )

    def test_incomplete_model_cache_reports_partial_progress(self) -> None:
        missing = "model.safetensors"
        self.write_registry()
        self.write_cache(omit=missing)
        with self.patched_cache_globals():
            contract = launcher._uzu_model_cache_contract()

        self.assertIsNotNone(contract)
        assert contract is not None
        self.assertFalse(contract["ready"])
        self.assertIn(f"{missing} is incomplete", contract["problems"])
        self.assertIn("model.part", contract["activeMarkers"])
        self.assertGreater(contract["completedBytes"], 0)
        self.assertLess(contract["completedBytes"], contract["totalBytes"])
        self.assertGreater(contract["progressPercent"], 0.0)
        self.assertLess(contract["progressPercent"], 100.0)
        self.assertEqual(contract["fingerprint"], "")

    def test_model_cache_rejects_wrong_size(self) -> None:
        self.write_registry()
        self.write_cache(wrong_size="model.safetensors")
        with self.patched_cache_globals():
            contract = launcher._uzu_model_cache_contract()

        self.assertIsNotNone(contract)
        assert contract is not None
        self.assertFalse(contract["ready"])
        self.assertIn(
            "model.safetensors has an unexpected size", contract["problems"],
        )
        self.assertEqual(contract["fingerprint"], "")

    def test_model_cache_rejects_wrong_crc_receipt(self) -> None:
        self.write_registry()
        self.write_cache(wrong_crc="config.json")
        with self.patched_cache_globals():
            contract = launcher._uzu_model_cache_contract()

        self.assertIsNotNone(contract)
        assert contract is not None
        self.assertFalse(contract["ready"])
        self.assertIn(
            "config.json has an invalid completion receipt", contract["problems"],
        )
        self.assertEqual(contract["fingerprint"], "")

    def test_model_cache_rejects_same_size_payload_corruption(self) -> None:
        self.write_registry()
        self.write_cache()
        path = self.model_path / "model.safetensors"
        payload = bytearray(path.read_bytes())
        payload[0] ^= 0x01
        path.write_bytes(payload)

        with self.patched_cache_globals():
            contract = launcher._uzu_model_cache_contract()

        self.assertIsNotNone(contract)
        assert contract is not None
        self.assertFalse(contract["ready"])
        self.assertIn(
            "model.safetensors failed its pinned SHA-256 check",
            contract["problems"],
        )
        self.assertEqual(contract["fingerprint"], "")

    def test_model_cache_rechecks_bytes_after_same_size_in_place_change(self) -> None:
        self.write_registry()
        self.write_cache()
        path = self.model_path / "model.safetensors"
        with self.patched_cache_globals():
            original = launcher._uzu_model_cache_contract()
            self.assertIsNotNone(original)
            assert original is not None
            self.assertTrue(original["ready"])
            original_mtime = path.stat().st_mtime_ns
            payload = bytearray(path.read_bytes())
            payload[-1] ^= 0x01
            path.write_bytes(payload)
            os.utime(path, ns=(path.stat().st_atime_ns, original_mtime))
            changed = launcher._uzu_model_cache_contract()

        self.assertIsNotNone(changed)
        assert changed is not None
        self.assertFalse(changed["ready"])
        self.assertIn(
            "model.safetensors failed its pinned SHA-256 check",
            changed["problems"],
        )

    def test_model_cache_rejects_registry_path_traversal(self) -> None:
        entry = self.registry_entry()
        entry["accessibility"]["reference"]["files"][0]["name"] = "../config.json"
        self.write_registry(entry)
        self.model_path.mkdir(parents=True)
        with self.patched_cache_globals():
            contract = launcher._uzu_model_cache_contract()

        self.assertIsNotNone(contract)
        assert contract is not None
        self.assertFalse(contract["ready"])
        self.assertIn("unsafe file path", contract["reason"])

    def test_geometry_extracts_attention_shape_and_fails_closed_on_mismatch(self) -> None:
        geometry, native_context = launcher._uzu_model_geometry(self.geometry_config)

        self.assertTrue(geometry["ready"])
        self.assertEqual(geometry["layers"], 3)
        self.assertEqual(geometry["fullAttentionLayers"], 2)
        self.assertEqual(geometry["attentionHeads"], 32)
        self.assertEqual(geometry["kvHeads"], 8)
        self.assertEqual(geometry["headDimension"], 128)
        self.assertEqual(geometry["layerSource"], "uzu-layer-configs")
        self.assertEqual(native_context, 262_144)

        inconsistent = copy.deepcopy(self.geometry_config)
        inconsistent["decoder_config"]["transformer_config"]["layer_configs"][2][
            "mixer_config"
        ]["num_groups"] = 4
        rejected, rejected_context = launcher._uzu_model_geometry(inconsistent)
        self.assertFalse(rejected["ready"])
        self.assertIsNone(rejected["kvHeads"])
        self.assertEqual(rejected_context, 262_144)

    def test_128k_capacity_includes_full_bf16_kv_and_long_context_reserve(self) -> None:
        model, payload, _binary = self.qualification_fixture(131_072)
        model["memoryGeometry"] = {
            "ready": True,
            "layers": 64,
            "fullAttentionLayers": 16,
            "attentionHeads": 32,
            "kvHeads": 4,
            "headDimension": 256,
            "layerSource": "uzu-layer-configs",
        }
        resource = {
            "memoryAvailable": True,
            "totalMemoryBytes": 48 * 1024**3,
            "headroomBytes": 38 * 1024**3,
        }

        estimate = launcher.launch_memory_estimate(payload, model, resource)

        self.assertEqual(estimate["contextTokens"], 131_072)
        self.assertEqual(estimate["targetKvCacheBytes"], 8 * 1024**3)
        self.assertEqual(
            estimate["draftKvCacheBytes"],
            131_072 * launcher.UZU_DRAFT_FULL_ATTENTION_BYTES_PER_TOKEN
            + launcher.UZU_DRAFT_SLIDING_CACHE_BYTES,
        )
        self.assertEqual(estimate["prefillTransientReserveBytes"], 2 * 1024**3)
        self.assertLess(
            estimate["estimatedWorkingSetBytes"]
            + launcher.UZU_PROCESS_CEILING_ADMISSION_MARGIN_BYTES,
            launcher.UZU_PROCESS_MEMORY_CEILING_BYTES,
        )
        self.assertTrue(launcher.uzu_estimate_within_process_ceiling(estimate))
        self.assertLess(estimate["requiredHeadroomBytes"], resource["headroomBytes"])

    def test_uzu_context_tiers_stop_at_guarded_128k_not_native_262k(self) -> None:
        model, _payload, _binary = self.qualification_fixture(131_072)
        self.assertEqual(
            launcher.UZU_SAFE_CONTEXT_WINDOWS,
            (16_384, 32_768, 65_536, 131_072),
        )
        self.assertIsNotNone(launcher.route_qualification_spec(model, "uzu", 131_072))
        self.assertIsNone(launcher.route_qualification_spec(model, "uzu", 262_144))
        with self.assertRaisesRegex(ValueError, "fixed context windows"):
            launcher.validate_runtime_context("uzu", 262_144)

    def test_uzu_ceiling_fit_is_fail_closed(self) -> None:
        estimate = {
            "estimatedWorkingSetBytes": 33 * 1024**3,
            "processMemoryCeilingBytes": 36 * 1024**3,
            "processCeilingAdmissionMarginBytes": 2 * 1024**3,
        }
        self.assertTrue(launcher.uzu_estimate_within_process_ceiling(estimate))
        estimate["estimatedWorkingSetBytes"] = 34 * 1024**3
        self.assertFalse(launcher.uzu_estimate_within_process_ceiling(estimate))
        del estimate["processCeilingAdmissionMarginBytes"]
        self.assertFalse(launcher.uzu_estimate_within_process_ceiling(estimate))

    def test_uzu_38gib_ceiling_preserves_stricter_receipts_not_their_overflows(self) -> None:
        self.assertEqual(launcher.UZU_PROCESS_MEMORY_CEILING_BYTES, 38 * 1024**3)
        model, _, _ = self.qualification_fixture(65_536)
        spec = launcher.route_qualification_spec(model, "uzu", 65_536)
        record = self.qualification_record(spec, context=65_536)
        record["qualificationContract"]["memoryCeilingBytes"] = 36 * 1024**3
        self.assertIsNotNone(launcher.route_qualification_metrics(record, spec))
        telemetry = record["modes"]["ar"]["resourceTelemetry"]
        telemetry["peakProcessGroupPhysicalFootprintBytes"] = 36 * 1024**3
        self.assertIsNone(launcher.route_qualification_metrics(record, spec))
        record["qualificationContract"]["memoryCeilingBytes"] = 38 * 1024**3
        self.assertIsNotNone(launcher.route_qualification_metrics(record, spec))
        telemetry["peakProcessGroupPhysicalFootprintBytes"] = 38 * 1024**3
        self.assertIsNone(launcher.route_qualification_metrics(record, spec))
        for invalid in (None, True, 38.0 * 1024**3, 37 * 1024**3, 40 * 1024**3):
            self.assertFalse(launcher.uzu_qualification_memory_ceiling_supported(invalid))

    def test_uzu_live_guard_enforces_38gib_current_or_peak(self) -> None:
        limit = 38 * 1024**3
        for current, peak, should_stop in (
            (37 * 1024**3, 37 * 1024**3, False),
            (limit - 1, limit - 1, False),
            (limit, limit - 1, True),
            (limit - 1, limit, True),
        ):
            with self.subTest(current=current, peak=peak):
                manager = launcher.RunManager()
                plan = mock.Mock(backend="uzu", purpose="session")
                process = mock.Mock(pid=4321)
                process.poll.side_effect = [None, 0]
                cancelled = threading.Event()
                manager.plan, manager.process = plan, process
                manager.state = {"phase": "running", "message": "Running", "events": []}
                with mock.patch.object(launcher.os, "getpgid", return_value=4321), mock.patch.object(
                    launcher, "darwin_process_group_physical_footprint", return_value={
                        "processGroupFootprintAvailable": True,
                        "processGroupMemberCount": 1,
                        "processGroupPhysicalFootprintBytes": current,
                        "processGroupLifetimePeakPhysicalFootprintBytes": peak,
                    },
                ), mock.patch.object(launcher, "apple_memory_pressure_state", return_value=physical_snapshot({
                    "memoryAvailable": True, "totalBytes": 48 * 1024**3, "freePercent": 20,
                })), mock.patch.object(manager, "_stop_owned") as stop:
                    manager._guard_uzu_memory(plan, process, cancelled)
                self.assertEqual(stop.called, should_stop)

    def test_128k_qualification_requires_a_fresh_matching_64k_receipt(self) -> None:
        model, payload, binary = self.qualification_fixture(131_072)
        model["memoryGeometry"] = {
            "ready": True,
            "layers": 64,
            "fullAttentionLayers": 16,
            "attentionHeads": 32,
            "kvHeads": 4,
            "headDimension": 256,
            "layerSource": "uzu-layer-configs",
        }
        snapshot = physical_snapshot({
            "memoryAvailable": True,
            "totalBytes": 48 * 1024**3,
            "freePercent": 80.0,
            "thermalAvailable": True,
            "thermalState": 0,
            "lowPowerMode": False,
            "metalWiredLimitBytes": 0,
        })
        idle_hub = {"phase": "idle", "message": "Ready"}
        idle_operation = {"active": False}

        with mock.patch.dict(
            launcher.BINARIES, {"mirai": str(binary)}, clear=True,
        ), mock.patch.object(
            launcher, "hardware_fingerprint", return_value="uzu-test-mac",
        ):
            missing = launcher.route_qualification_memory_admission(
                payload, [model], resource_snapshot=snapshot,
                hub=idle_hub, operation=idle_operation,
            )
        self.assertFalse(missing["launchable"])
        self.assertEqual(missing["decision"], "qualification")
        self.assertEqual(
            missing["stagedQualification"]["reason"], "missing-64k-receipt",
        )

        spec_64k = launcher.route_qualification_spec(model, "uzu", 65_536)
        self.assertIsNotNone(spec_64k)
        assert spec_64k is not None
        record = self.qualification_record(spec_64k, context=65_536)
        self.bind_qualification_record(model, payload, record, spec_64k)
        with mock.patch.dict(
            launcher.BINARIES, {"mirai": str(binary)}, clear=True,
        ), mock.patch.object(
            launcher, "hardware_fingerprint", return_value="uzu-test-mac",
        ):
            ready = launcher.route_qualification_memory_admission(
                payload, [model], resource_snapshot=snapshot,
                hub=idle_hub, operation=idle_operation,
            )
        self.assertTrue(ready["launchable"])
        proof = ready["stagedQualification"]
        self.assertTrue(proof["required"])
        self.assertTrue(proof["ready"])
        self.assertEqual(proof["receiptId"], record["id"])
        self.assertEqual(
            proof["projected128KProcessGroupPeakWithMarginBytes"],
            proof["measured64KProcessGroupPeakBytes"]
            + proof["estimatedWorkingSetGrowthBytes"]
            + launcher.UZU_PROCESS_CEILING_ADMISSION_MARGIN_BYTES,
        )
        self.assertLess(
            proof["projected128KProcessGroupPeakWithMarginBytes"],
            launcher.UZU_PROCESS_MEMORY_CEILING_BYTES,
        )

        for field, value in (
            ("createdAt", "2025-01-01T00:00:00Z"),
            ("runtimeVersion", "different Uzu runtime"),
            ("modelFingerprint", "b" * 64),
            ("samplingFingerprint", "d" * 64),
        ):
            with self.subTest(mismatch=field):
                broken_model = copy.deepcopy(model)
                broken_record = broken_model["backends"]["uzu"]["localBenchmarks"][0]
                broken_record[field] = value
                broken_model["backends"]["uzu"]["localBenchmark"] = broken_record
                with mock.patch.dict(
                    launcher.BINARIES, {"mirai": str(binary)}, clear=True,
                ), mock.patch.object(
                    launcher, "hardware_fingerprint", return_value="uzu-test-mac",
                ):
                    rejected = launcher.route_qualification_memory_admission(
                        payload, [broken_model], resource_snapshot=snapshot,
                        hub=idle_hub, operation=idle_operation,
                    )
                self.assertFalse(rejected["launchable"])
                self.assertEqual(
                    rejected["stagedQualification"]["reason"],
                    "missing-64k-receipt",
                )

        different_output = copy.deepcopy(payload)
        different_output["output"] = 2_048
        with mock.patch.dict(
            launcher.BINARIES, {"mirai": str(binary)}, clear=True,
        ), mock.patch.object(
            launcher, "hardware_fingerprint", return_value="uzu-test-mac",
        ):
            rejected_output = launcher.route_qualification_memory_admission(
                different_output, [model], resource_snapshot=snapshot,
                hub=idle_hub, operation=idle_operation,
            )
        self.assertFalse(rejected_output["launchable"])
        self.assertEqual(
            rejected_output["stagedQualification"]["reason"],
            "missing-64k-receipt",
        )

    def test_128k_staged_projection_must_stay_strictly_below_live_ceiling(self) -> None:
        model, payload, _binary = self.qualification_fixture(131_072)
        model["memoryGeometry"] = {
            "ready": True,
            "layers": 64,
            "fullAttentionLayers": 16,
            "attentionHeads": 32,
            "kvHeads": 4,
            "headDimension": 256,
            "layerSource": "uzu-layer-configs",
        }
        resource = {
            "memoryAvailable": True,
            "totalMemoryBytes": 48 * 1024**3,
            "headroomBytes": 40 * 1024**3,
        }
        request_64k = copy.deepcopy(payload)
        request_64k["context"] = 65_536
        estimate_64k = launcher.launch_memory_estimate(request_64k, model, resource)
        estimate_128k = launcher.launch_memory_estimate(payload, model, resource)
        growth = (
            estimate_128k["estimatedWorkingSetBytes"]
            - estimate_64k["estimatedWorkingSetBytes"]
        )
        boundary_peak = (
            launcher.UZU_PROCESS_MEMORY_CEILING_BYTES
            - launcher.UZU_PROCESS_CEILING_ADMISSION_MARGIN_BYTES
            - growth
        )
        spec_64k = launcher.route_qualification_spec(model, "uzu", 65_536)
        self.assertIsNotNone(spec_64k)
        assert spec_64k is not None
        record = self.qualification_record(spec_64k, context=65_536)
        telemetry = record["modes"]["ar"]["resourceTelemetry"]
        telemetry["peakProcessGroupPhysicalFootprintBytes"] = boundary_peak
        self.bind_qualification_record(model, payload, record, spec_64k)

        with mock.patch.object(
            launcher, "hardware_fingerprint", return_value="uzu-test-mac",
        ):
            rejected = launcher.uzu_128k_staged_qualification_proof(
                payload, model, resource, estimate_128k,
            )
        self.assertFalse(rejected["ready"])
        self.assertEqual(rejected["reason"], "projected-ceiling")
        self.assertEqual(
            rejected["projected128KProcessGroupPeakWithMarginBytes"],
            launcher.UZU_PROCESS_MEMORY_CEILING_BYTES,
        )

        telemetry["peakProcessGroupPhysicalFootprintBytes"] = boundary_peak - 1
        self.bind_qualification_record(model, payload, record, spec_64k)
        with mock.patch.object(
            launcher, "hardware_fingerprint", return_value="uzu-test-mac",
        ):
            accepted = launcher.uzu_128k_staged_qualification_proof(
                payload, model, resource, estimate_128k,
            )
        self.assertTrue(accepted["ready"])
        self.assertEqual(
            accepted["projected128KProcessGroupPeakWithMarginBytes"],
            launcher.UZU_PROCESS_MEMORY_CEILING_BYTES - 1,
        )

    def test_128k_benchmark_never_starts_without_matching_64k_receipt(self) -> None:
        model, payload, binary = self.qualification_fixture(131_072)
        model["memoryGeometry"] = {
            "ready": True,
            "layers": 64,
            "fullAttentionLayers": 16,
            "attentionHeads": 32,
            "kvHeads": 4,
            "headDimension": 256,
            "layerSource": "uzu-layer-configs",
        }
        request = copy.deepcopy(payload)
        request["scope"] = "qualification"
        snapshot = physical_snapshot({
            "memoryAvailable": True,
            "totalBytes": 48 * 1024**3,
            "freePercent": 80.0,
            "thermalAvailable": True,
            "thermalState": 0,
            "lowPowerMode": False,
            "metalWiredLimitBytes": 0,
        })
        run_manager = launcher.RunManager()
        manager = launcher.BenchmarkManager(run_manager)

        with mock.patch.dict(
            launcher.BINARIES, {"mirai": str(binary)}, clear=True,
        ), mock.patch.object(
            launcher, "physical_memory_bytes", return_value=48 * 1024**3,
        ), mock.patch.object(
            launcher, "apple_resource_snapshot", return_value=snapshot,
        ), mock.patch.object(
            launcher, "hardware_fingerprint", return_value="uzu-test-mac",
        ), mock.patch.object(
            launcher.threading, "Thread",
        ) as worker_thread, mock.patch.object(
            run_manager, "start",
        ) as model_start:
            with self.assertRaisesRegex(ValueError, "64K"):
                manager.start(request, [model])
        worker_thread.assert_not_called()
        model_start.assert_not_called()
        self.assertEqual(manager.snapshot()["phase"], "idle")

        with mock.patch.dict(
            launcher.BINARIES, {"mirai": str(binary)}, clear=True,
        ), mock.patch.object(
            launcher, "physical_memory_bytes", return_value=48 * 1024**3,
        ):
            qualification = launcher.validated_route_qualification_request(
                request, [model],
            )
        rejected_plan = mock.Mock(
            backend="uzu", run_dir=None, secrets={},
        )
        with mock.patch.dict(
            launcher.BINARIES, {"mirai": str(binary)}, clear=True,
        ), mock.patch.object(
            launcher, "normalized_request", return_value=rejected_plan,
        ), mock.patch.object(
            launcher, "apple_resource_snapshot", return_value=snapshot,
        ), mock.patch.object(
            launcher, "hardware_fingerprint", return_value="uzu-test-mac",
        ), mock.patch.object(
            run_manager, "start",
        ) as model_start:
            with self.assertRaisesRegex(RuntimeError, "64K"):
                manager._measure_mode(
                    qualification["job"], [model], "ar", 0, 6,
                )
        model_start.assert_not_called()

    def test_model_record_keeps_native_context_separate_from_safe_windows(self) -> None:
        self.write_registry()
        self.write_cache()
        with (
            self.patched_cache_globals(),
            mock.patch.object(
                launcher, "uzu_runtime_contract",
                return_value={
                    "ready": False,
                    "reason": "fixed release still required",
                },
            ),
            mock.patch.object(launcher, "command_version", return_value="Uzu test"),
            mock.patch.object(
                launcher, "physical_memory_bytes", return_value=48 * 1024**3,
            ),
        ):
            records = launcher.uzu_model_records([], None)

        self.assertEqual(len(records), 1)
        model = records[0]
        capability = model["backends"]["uzu"]
        self.assertEqual(model["nativeContext"], 262_144)
        self.assertEqual(model["architectureNativeContext"], 262_144)
        self.assertEqual(capability["contextWindows"], list(launcher.UZU_SAFE_CONTEXT_WINDOWS))
        self.assertEqual(capability["contextMaximum"], max(launcher.UZU_SAFE_CONTEXT_WINDOWS))
        self.assertFalse(capability["customSampling"])
        self.assertIn("model defaults", capability["samplingReason"])
        self.assertEqual(capability["agentReasoning"], ["auto"])
        self.assertEqual(
            capability["qualificationSystemContract"],
            {
                "osReserveBytes": max(
                    launcher.SESSION_OS_RESERVE_MIN_BYTES,
                    round(48 * 1024**3 * launcher.SESSION_OS_RESERVE_FRACTION),
                ),
                "sandboxProfileSha256": launcher.UZU_SANDBOX_PROFILE_SHA256,
                "rawListenerProtected": False,
                "nativeBoundaryContractId": None,
                "nativeBearerAuthentication": False,
                "oneUseApiKeyFile": False,
                "nativeContextLimit": False,
                "nativeOutputLimit": False,
            },
        )
        self.assertFalse(capability["runnable"])

    def test_builder_pins_sandbox_loopback_cache_and_request_reasoning(self) -> None:
        runtime, sandbox, _sha256 = self.runtime_fixture()
        self.model_path.mkdir(parents=True)
        fingerprint = "f" * 64
        runtime_contract = {
            "ready": True,
            "reason": "verified fixed release",
            "binary": {"sha256": "runtime-sha256", "size": runtime.stat().st_size},
            "upstreamCommit": launcher.UZU_RUNTIME_UPSTREAM_COMMIT,
            "sourcePatchSha256": launcher.UZU_RUNTIME_SOURCE_PATCH_SHA256,
            "binaryIdentityPinned": True,
            "networkSandbox": True,
            "memorySafetyBlocked": False,
            "nativeBoundaryContractId": launcher.UZU_NATIVE_BOUNDARY_CONTRACT_ID,
            "nativeBearerAuthentication": True,
            "oneUseApiKeyFile": True,
            "nativeContextLimit": True,
            "nativeOutputLimit": True,
            "boundedContextReady": True,
            "rawListenerAuthenticated": True,
            "rawListenerIsolated": False,
            "listenerIsolationBlocked": False,
        }
        cache_contract = {
            "ready": True,
            "reason": "complete",
            "path": str(self.model_path),
            "fingerprint": fingerprint,
            "registryEntry": self.registry_entry(),
        }
        capability = {
            "runnable": True,
            "benchmarkModelFingerprint": fingerprint,
            "modelRegistryId": launcher.UZU_MODEL_REGISTRY_ID,
            "modelCommit": launcher.UZU_MODEL_COMMIT,
            "modelToolchainVersion": launcher.UZU_MODEL_TOOLCHAIN_VERSION,
            "agentReasoning": ["auto"],
            "runtimeIdentity": copy.deepcopy(runtime_contract),
            "qualificationSystemContract": {
                "rawListenerProtected": True,
                "nativeBoundaryContractId": launcher.UZU_NATIVE_BOUNDARY_CONTRACT_ID,
                "nativeBearerAuthentication": True,
                "oneUseApiKeyFile": True,
                "nativeContextLimit": True,
                "nativeOutputLimit": True,
            },
        }
        model = {
            "id": "uzu-test",
            "name": "Uzu test",
            "path": str(self.model_path),
            "uzuNative": True,
            "backends": {"uzu": capability},
        }

        for reasoning, request_effort in (("auto", "default"), ("off", "disabled")):
            with self.subTest(reasoning=reasoning):
                run_dir = self.root / f"run-uzu-{reasoning}"
                run_dir.mkdir(mode=0o700)
                plan = launcher.LaunchPlan(
                    f"uzu-{reasoning}", "uzu", "chat", copy.deepcopy(model),
                    str(self.root), 16_384, 1_024, reasoning, 18_123,
                    "custom", {}, runtime_binary=str(runtime),
                    chat={"systemPrompt": "", "sampling": "model"},
                    run_dir=run_dir,
                )
                with (
                    mock.patch.object(
                        launcher, "uzu_runtime_contract",
                        return_value=runtime_contract,
                    ),
                    mock.patch.object(
                        launcher.model_catalog.ModelCatalog, "_uzu_model_cache_contract",
                        return_value=cache_contract,
                    ),
                    mock.patch.object(
                        launcher, "UZU_SANDBOX_EXECUTABLE", sandbox,
                    ),
                ):
                    launcher.build_uzu(plan, capability)
                    identities = launcher.validate_uzu_launch_boundary(plan)

                    expected_argv = [
                        str(sandbox), "-p", launcher.UZU_NETWORK_SANDBOX_PROFILE,
                        str(runtime.resolve()), "server",
                        "--model", launcher.UZU_MODEL_REGISTRY_ID,
                        "--host", "127.0.0.1", "--port", "18123",
                        "--api-key-file", str(run_dir / launcher.UZU_API_KEY_FILE_NAME),
                        "--context-limit", "16384",
                        "--max-output-tokens", "1024",
                        "--prefix-cache",
                    ]
                    self.assertEqual(plan.engine_argv, expected_argv)
                    self.assertEqual(plan.engine_env, {})
                    key_file = launcher._validated_uzu_api_key_file(plan)
                    self.assertEqual(stat.S_IMODE(key_file.stat().st_mode), 0o600)
                    self.assertEqual(key_file.stat().st_nlink, 1)
                    self.assertNotIn(plan.secrets["apiKey"], plan.engine_argv)
                    self.assertNotIn("--reasoning-effort", plan.engine_argv)
                    self.assertEqual(
                        launcher.UZU_NETWORK_SANDBOX_PROFILE,
                        "(version 1)(allow default)(deny network-outbound)",
                    )
                    self.assertEqual(identities[:2], ("runtime-sha256", fingerprint))
                    self.assertEqual(identities[2], launcher._llamacpp_strong_path_identity(key_file))
                    catalog_bytes = self.resolved_path.read_bytes()
                    self.resolved_path.write_text("{}")
                    with self.assertRaisesRegex(ValueError, "offline catalog"):
                        launcher.validate_uzu_launch_boundary(plan)
                    self.resolved_path.write_bytes(catalog_bytes)
                    self.assertEqual(launcher.validate_uzu_launch_boundary(plan), identities)
                    body = json.loads(launcher.build_chat_completion_request(
                        plan, {"messages": [{"role": "user", "content": "hello"}]},
                    ).data)
                    self.assertEqual(body["reasoning_effort"], request_effort)
                    self.assertNotIn("thinking_mode", body)
                    self.assertNotIn("chat_template_kwargs", body)

                    bypassed = list(plan.engine_argv)
                    plan.engine_argv = plan.engine_argv[3:]
                    with self.assertRaisesRegex(ValueError, "fixed local-only"):
                        launcher.validate_uzu_launch_boundary(plan)
                    plan.engine_argv = bypassed
                    launcher.dispose_plan_secrets(plan)
                    self.assertFalse(key_file.exists())

    def test_prepare_launch_uses_retained_fd_when_host_marks_it_executable(self) -> None:
        runtime, sandbox, _sha256 = self.runtime_fixture()
        plan = launcher.LaunchPlan(
            "uzu-fd-handoff", "uzu", "chat",
            {
                "id": "uzu-fd", "name": "Uzu fd fixture", "uzuNative": True,
                "backends": {"uzu": {}},
            },
            str(self.root), 16_384, 1_024, "auto", 18_145, "custom", {},
            runtime_binary=str(runtime), run_dir=self.root / "run-uzu-fd",
        )
        plan.engine_argv = [
            str(sandbox), "-p", launcher.UZU_NETWORK_SANDBOX_PROFILE,
            str(runtime.resolve()), "server",
        ]
        expected = ("runtime", "model", "key", "revision")
        with (
            mock.patch.object(launcher, "UZU_RUNTIME_PATH", runtime),
            mock.patch.object(
                launcher.engine_planning.EnginePlanner, "_validated_uzu_route",
                return_value=(runtime, {}, {}, expected),
            ),
            mock.patch.object(
                launcher.engine_planning.EnginePlanner, "_uzu_inherited_executable_path",
                side_effect=lambda opened: f"/dev/fd/{opened.fd}",
            ),
        ):
            launch = launcher.prepare_uzu_executable_launch(plan, expected)
        descriptor = launch.opened.fd
        try:
            self.assertTrue(launch.executes_from_fd)
            self.assertEqual(launch.pass_fds, (descriptor,))
            self.assertEqual(launch.argv[3], f"/dev/fd/{descriptor}")
            self.assertEqual(plan.engine_argv[3], str(runtime.resolve()))
            self.assertEqual(os.fstat(descriptor).st_ino, runtime.stat().st_ino)
        finally:
            launch.close()
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_worker_passes_only_the_verified_uzu_fd_to_mocked_popen(self) -> None:
        run_dir = self.root / "run-uzu-worker"
        run_dir.mkdir(mode=0o700)
        plan = launcher.LaunchPlan(
            "uzu-worker", "uzu", "chat",
            {"id": "uzu-worker", "name": "Uzu worker", "backends": {"uzu": {}}},
            str(self.root), 16_384, 1_024, "auto", 18_146, "custom", {},
            purpose="benchmark", run_dir=run_dir,
        )
        plan.engine_argv = ["sandbox-exec", "-p", "profile", "named-uzu", "server"]
        fd_argv = ["sandbox-exec", "-p", "profile", "/dev/fd/42", "server"]
        launch = mock.Mock(
            argv=fd_argv, pass_fds=(42,), executes_from_fd=True,
        )
        process = mock.Mock(pid=4_242)
        process.poll.return_value = None
        manager = launcher.RunManager()
        cancel_event = threading.Event()
        manager.plan = plan
        manager.cancel_event = cancel_event
        fake_thread = mock.Mock()
        expected = ("runtime", "model", "key", "revision")
        with (
            mock.patch.object(
                launcher, "validate_uzu_launch_boundary", return_value=expected,
            ),
            mock.patch.object(
                launcher, "prepare_uzu_executable_launch", return_value=launch,
            ),
            mock.patch.object(launcher.subprocess, "Popen", return_value=process) as popen,
            mock.patch.object(manager, "_wait_ready"),
            mock.patch.object(manager, "_verify_lmstudio_reasoning"),
            mock.patch.object(manager, "_verify_client_api"),
            mock.patch.object(launcher.threading, "Thread", return_value=fake_thread),
        ):
            manager._worker(plan, cancel_event)

        popen.assert_called_once()
        args, kwargs = popen.call_args
        self.assertEqual(args[0], fd_argv)
        self.assertEqual(kwargs["pass_fds"], (42,))
        self.assertTrue(kwargs["start_new_session"])
        launch.close.assert_called_once_with()
        self.assertIs(manager.process, process)

    def test_worker_path_fallback_rechecks_fd_and_omits_pass_fds(self) -> None:
        run_dir = self.root / "run-uzu-worker-fallback"
        run_dir.mkdir(mode=0o700)
        argv = ["sandbox-exec", "-p", "profile", "named-uzu", "server"]
        plan = launcher.LaunchPlan(
            "uzu-worker-fallback", "uzu", "chat",
            {
                "id": "uzu-worker-fallback", "name": "Uzu fallback",
                "backends": {"uzu": {}},
            },
            str(self.root), 16_384, 1_024, "auto", 18_147, "custom", {},
            purpose="benchmark", run_dir=run_dir, engine_argv=argv,
        )
        opened = mock.sentinel.opened_uzu_descriptor
        launch = mock.Mock(
            argv=argv, pass_fds=(), executes_from_fd=False, opened=opened,
        )
        process = mock.Mock(pid=4_243)
        process.poll.return_value = None
        manager = launcher.RunManager()
        cancel_event = threading.Event()
        manager.plan = plan
        manager.cancel_event = cancel_event
        expected = ("runtime", "model", "key", "revision")
        with (
            mock.patch.object(
                launcher, "validate_uzu_launch_boundary", return_value=expected,
            ),
            mock.patch.object(
                launcher, "prepare_uzu_executable_launch", return_value=launch,
            ),
            mock.patch.object(
                launcher, "_confirm_open_uzu_executable",
            ) as confirm_opened,
            mock.patch.object(launcher.subprocess, "Popen", return_value=process) as popen,
            mock.patch.object(manager, "_wait_ready"),
            mock.patch.object(manager, "_verify_lmstudio_reasoning"),
            mock.patch.object(manager, "_verify_client_api"),
            mock.patch.object(launcher.threading, "Thread", return_value=mock.Mock()),
        ):
            manager._worker(plan, cancel_event)

        _args, kwargs = popen.call_args
        self.assertNotIn("pass_fds", kwargs)
        confirm_opened.assert_called_once_with(opened)
        launch.close.assert_called_once_with()
        self.assertIs(manager.process, process)

    def test_uzu_reasoning_contract_is_request_scoped_and_binary(self) -> None:
        self.assertEqual(
            launcher.apply_chat_reasoning_contract({}, "uzu", "auto"),
            {"reasoning_effort": "default"},
        )
        self.assertEqual(
            launcher.apply_chat_reasoning_contract({}, "uzu", "off"),
            {"reasoning_effort": "disabled"},
        )
        for reasoning in ("low", "medium", "high"):
            with self.subTest(reasoning=reasoning), self.assertRaisesRegex(
                ValueError, "on or off",
            ):
                launcher.apply_chat_reasoning_contract({}, "uzu", reasoning)

    def test_uzu_one_use_key_is_private_and_generic_cleanup_is_idempotent(self) -> None:
        run_dir = self.root / "uzu-private-key"
        run_dir.mkdir(mode=0o700)
        plan = launcher.LaunchPlan(
            "uzu-private-key", "uzu", "chat",
            {"id": "uzu-key", "name": "Uzu key fixture", "servedId": "uzu-key"},
            str(self.root), 16_384, 1_024, "auto", 18_140, "custom", {},
            purpose="benchmark", run_dir=run_dir,
        )
        key_file, api_key = launcher._create_plan_api_key_file(
            plan, backend="uzu", filename=launcher.UZU_API_KEY_FILE_NAME,
            label="Uzu",
        )
        details = key_file.lstat()
        self.assertTrue(stat.S_ISREG(details.st_mode))
        self.assertEqual(stat.S_IMODE(details.st_mode), 0o600)
        self.assertEqual(details.st_nlink, 1)
        self.assertEqual(key_file.read_text(encoding="utf-8"), api_key + "\n")
        launcher.atomic_json(run_dir / "session-proxy.json", {"upstreamKey": api_key})
        launcher.atomic_json(run_dir / "codex-proxy.json", {"upstreamKey": api_key})

        launcher.dispose_plan_secrets(plan)
        launcher.dispose_plan_secrets(plan)
        self.assertFalse(key_file.exists())
        self.assertFalse((run_dir / "session-proxy.json").exists())
        self.assertFalse((run_dir / "codex-proxy.json").exists())
        self.assertNotIn("apiKey", plan.secrets)

    def test_live_uzu_listener_requires_auth_and_consumes_key_file(self) -> None:
        run_dir = self.root / "uzu-live-auth"
        run_dir.mkdir(mode=0o700)
        plan = launcher.LaunchPlan(
            "uzu-live-auth", "uzu", "chat",
            {"id": "uzu-live", "name": "Uzu live fixture", "servedId": "uzu-live"},
            str(self.root), 16_384, 1_024, "auto", 18_141, "custom", {},
            purpose="benchmark", run_dir=run_dir,
        )
        key_file, _api_key = launcher._create_plan_api_key_file(
            plan, backend="uzu", filename=launcher.UZU_API_KEY_FILE_NAME,
            label="Uzu",
        )
        key_file.unlink()

        class ModelsResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, _kind, _value, _traceback):
                return False

            def read(self, _limit):
                return json.dumps({"data": [{"id": plan.model["servedId"]}]}).encode()

        seen = []

        def protected_listener(request, timeout=0):
            seen.append((request.full_url, request.get_header("Authorization"), timeout))
            if request.full_url.endswith("/v1/models") and request.get_header(
                "Authorization"
            ) == f"Bearer {plan.secrets['apiKey']}":
                return ModelsResponse()
            raise launcher.urllib.error.HTTPError(
                request.full_url, 401, "Unauthorized", {}, None,
            )

        manager = launcher.RunManager()
        with mock.patch.object(
            launcher.urllib.request, "urlopen", side_effect=protected_listener,
        ) as urlopen:
            manager._wait_ready(plan, manager.cancel_event)
        self.assertEqual(urlopen.call_count, 5)
        self.assertEqual(
            seen[0][1], f"Bearer {plan.secrets['apiKey']}",
            "readiness must first succeed with the exact retained bearer",
        )
        self.assertTrue(all(auth != seen[0][1] for _url, auth, _timeout in seen[1:]))

        with mock.patch.object(
            launcher.urllib.request, "urlopen", return_value=mock.MagicMock(),
        ), self.assertRaisesRegex(RuntimeError, "accepted a request"):
            launcher.RunManager._verify_uzu_native_security(plan)

        key_file.write_text(plan.secrets["apiKey"] + "\n", encoding="utf-8")
        key_file.chmod(0o600)
        with mock.patch.object(
            launcher.urllib.request, "urlopen",
        ) as urlopen, self.assertRaisesRegex(RuntimeError, "did not consume"):
            launcher.RunManager._verify_uzu_native_security(plan)
        urlopen.assert_not_called()

    def test_private_relay_pins_uzu_reasoning_output_and_context(self) -> None:
        base = {
            "servedModel": "uzu-model",
            "outputLimit": 4_096,
            "contextLimit": 16_384,
            "backend": "uzu",
            "reasoning": "auto",
        }
        request = {
            "model": "uzu-model",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
            "stream_options": {"include_usage": False},
            "max_tokens": 9_999,
            "max_completion_tokens": 8_000,
            "reasoning_effort": "high",
            "enable_thinking": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        transformed = json.loads(session_proxy.transform_chat_request(
            json.dumps(request).encode("utf-8"), base,
        ))
        self.assertEqual(transformed["reasoning_effort"], "default")
        self.assertEqual(transformed["max_completion_tokens"], 4_096)
        self.assertNotIn("max_tokens", transformed)
        self.assertNotIn("enable_thinking", transformed)
        self.assertNotIn("chat_template_kwargs", transformed)
        self.assertNotIn("stream_options", transformed)

        off = json.loads(session_proxy.transform_chat_request(
            json.dumps({
                "model": "uzu-model",
                "messages": [{"role": "user", "content": "hello"}],
            }).encode("utf-8"),
            {**base, "reasoning": "off"},
        ))
        self.assertEqual(off["reasoning_effort"], "disabled")

        oversized = {
            "model": "uzu-model",
            "messages": [{"role": "user", "content": "x" * 12_000}],
            "max_completion_tokens": 4_096,
        }
        # Bytes are not tokens; the pinned native tokenizer enforces this.
        forwarded = json.loads(session_proxy.transform_chat_request(
            json.dumps(oversized).encode("utf-8"), base,
        ))
        self.assertEqual(forwarded["messages"], oversized["messages"])
        self.assertEqual(forwarded["max_completion_tokens"], 4096)

        with self.assertRaisesRegex(ValueError, "sampling defaults"):
            session_proxy.transform_chat_request(
                json.dumps({
                    "model": "uzu-model",
                    "messages": [{"role": "user", "content": "hello"}],
                    "temperature": 0.5,
                }).encode("utf-8"),
                base,
            )

    def test_profile_options_keep_runtime_owned_route_fixed(self) -> None:
        capability = {"runtimeManagedAcceleration": "DFlash + Weaver"}
        self.assertEqual(
            launcher.validated_profile_options("uzu", {}, capability, {}),
            {"acceleration": "off", "depth": 1, "kv": "off"},
        )
        invalid = (
            {"acceleration": "dflash"},
            {"depth": 2},
            {"kv": "q8"},
            {"weaverWidth": 4},
            {"draftModel": "/tmp/untrusted"},
        )
        for options in invalid:
            with self.subTest(options=options), self.assertRaises(ValueError):
                launcher.validated_profile_options(
                    "uzu", {}, capability, options,
                )

    def test_upstream_vendor_evidence_never_becomes_automatic(self) -> None:
        capability = {
            "modelRegistryId": launcher.UZU_MODEL_REGISTRY_ID,
            "localBenchmark": None,
            "localBenchmarks": [],
        }
        evidence = launcher.route_performance_evidence(
            {"name": "Uzu model"}, "uzu", capability,
        )

        self.assertEqual(evidence["tier"], "upstream-measured")
        self.assertEqual(evidence["source"], "mirai-upstream")
        self.assertEqual(evidence["sourceUrl"], launcher.UZU_MODEL_PAGE_URL)
        self.assertEqual(evidence["sourceHardware"], launcher.UZU_UPSTREAM_HARDWARE)
        self.assertFalse(evidence["automaticEligible"])
        self.assertIsNone(evidence["recordId"])
        self.assertIn("cannot select", evidence["detail"])

    def test_benchmark_exposes_one_fixed_dflash_weaver_route(self) -> None:
        binary = self.root / "mirai"
        binary.write_bytes(b"runtime")
        capability = {
            "runnable": True,
            "agentReasoning": ["auto"],
            "modelRegistryId": launcher.UZU_MODEL_REGISTRY_ID,
            "benchmarkModelFingerprint": "a" * 64,
            "runtimeVersion": "Uzu fixed-test",
            "runtimeManagedAcceleration": "DFlash + Weaver",
            "mtp": False,
            "dflash": False,
        }
        model = {
            "id": "uzu-benchmark",
            "name": "Uzu benchmark",
            "ready": True,
            "nativeContext": 32_768,
            "uzuNative": True,
            "defaultSampling": {"temperature": 0.6},
            "backends": {"uzu": capability},
        }
        payload = {
            "backend": "uzu",
            "client": "chat",
            "modelId": model["id"],
            "project": str(self.root),
            "context": 16_384,
            "output": 4_096,
            "reasoning": "auto",
            "suite": "quick",
            "options": {},
        }
        with mock.patch.dict(launcher.BINARIES, {"mirai": str(binary)}):
            job = launcher.validated_benchmark_request(payload, [model])

        self.assertEqual(job["modes"], ["ar"])
        self.assertEqual(
            launcher.benchmark_job_public_modes(job),
            [{"id": "ar", "label": "Fixed DFlash + Weaver"}],
        )
        routes = launcher.benchmark_job_measurement_routes(job)
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0]["mode"], "ar")
        self.assertEqual(routes[0]["label"], "Fixed DFlash + Weaver")
        self.assertEqual(routes[0]["settings"], {})
        self.assertEqual(
            launcher.benchmark_engine_settings_label("uzu", {}),
            "Bundled DFlash draft · Weaver tree verification · prefix cache",
        )
        self.assertIn(
            "one fixed DFlash + Weaver route",
            launcher.benchmark_mode_summary(model, "uzu", job["modes"]),
        )
        self.assertEqual(
            launcher.benchmark_acceleration_reason(model, "uzu", job["modes"]),
            "Runtime-managed DFlash + Weaver with bundled draft and prefix cache",
        )
        self.assertEqual(
            launcher.benchmark_route_settings_label("uzu", "ar", {}),
            "Fixed DFlash + Weaver",
        )
        self.assertEqual(
            launcher.route_qualification_engine_reason("uzu"),
            "Runs the exact fixed DFlash + Weaver route with packaged reasoning and "
            "requires both reasoning and final-answer output.",
        )
        with mock.patch.dict(
            launcher.BINARIES, {"mirai": str(binary)}, clear=False,
        ):
            report = launcher.model_library_inventory([model])["models"][0]
        uzu = next(engine for engine in report["engines"] if engine["id"] == "uzu")
        self.assertEqual(
            uzu["modes"],
            [{
                "id": "ar", "label": "Fixed DFlash + Weaver",
                "kind": "fixed-route", "available": True,
                "detail": "Runtime-managed bundled DFlash draft and Weaver verification tree",
            }],
        )
        self.assertNotIn("standard AR", json.dumps(report["doctor"]))

    def test_uzu_qualification_is_chat_only_and_binds_each_context(self) -> None:
        for context in launcher.UZU_SAFE_CONTEXT_WINDOWS:
            with self.subTest(context=context):
                model, payload, binary = self.qualification_fixture(context)
                spec = launcher.route_qualification_spec(model, "uzu", context)
                self.assertIsNotNone(spec)
                assert spec is not None
                self.assertEqual(spec["backend"], "uzu")
                self.assertEqual(spec["scope"], "route")
                self.assertFalse(spec["clientAgnostic"])
                self.assertEqual(spec["client"], "chat")
                self.assertEqual(spec["modeLabel"], "Fixed DFlash + Weaver")
                self.assertEqual(spec["version"], 5)
                self.assertEqual(
                    spec["id"],
                    f"qwen36-uzu-dflash-weaver-{context // 1024}k-v5",
                )
                self.assertTrue(spec["memoryProofRequired"])
                self.assertEqual(
                    spec["memoryCeilingBytes"],
                    launcher.UZU_PROCESS_MEMORY_CEILING_BYTES,
                )
                request = {**payload, "scope": "qualification"}
                with mock.patch.dict(
                    launcher.BINARIES, {"mirai": str(binary)}, clear=True,
                ), mock.patch.object(
                    launcher, "physical_memory_bytes", return_value=48 * 1024**3,
                ):
                    qualification = launcher.validated_route_qualification_request(
                        request, [model],
                    )
                self.assertEqual(qualification["executionOrder"], ["uzu"])
                self.assertEqual(qualification["request"]["client"], "chat")
                self.assertEqual(qualification["request"]["context"], context)
                contract = qualification["qualificationContract"]
                self.assertEqual(contract["scope"], "route")
                self.assertFalse(contract["clientAgnostic"])
                self.assertEqual(contract["client"], "chat")
                self.assertEqual(contract["exactContext"], context)
                self.assertEqual(contract["configuredOutputLimit"], 4_096)
                self.assertEqual(
                    contract["measuredRequestMaxTokens"],
                    4096,
                )
                self.assertEqual(
                    contract["minimumCompletionTokens"],
                    launcher.ROUTE_QUALIFICATION_MINIMUM_COMPLETION_TOKENS,
                )
                self.assertEqual(
                    contract["receiptFingerprint"],
                    model["backends"]["uzu"]["benchmarkModelFingerprint"],
                )
                self.assertEqual(
                    contract["modelFingerprint"],
                    model["backends"]["uzu"]["benchmarkModelFingerprint"],
                )
                self.assertEqual(
                    contract["modelRegistryId"], launcher.UZU_MODEL_REGISTRY_ID,
                )
                self.assertEqual(contract["modelCommit"], launcher.UZU_MODEL_COMMIT)
                self.assertEqual(
                    contract["modelToolchainVersion"],
                    launcher.UZU_MODEL_TOOLCHAIN_VERSION,
                )
                self.assertEqual(
                    contract["runtimeBinarySha256"],
                    launcher.UZU_RUNTIME_RELEASE_BINARY_SHA256,
                )
                self.assertEqual(
                    contract["runtimeBinarySize"],
                    launcher.UZU_RUNTIME_RELEASE_BINARY_SIZE,
                )
                self.assertEqual(
                    contract["runtimeUpstreamCommit"],
                    launcher.UZU_RUNTIME_UPSTREAM_COMMIT,
                )
                self.assertEqual(
                    contract["runtimeSourcePatchSha256"],
                    launcher.UZU_RUNTIME_SOURCE_PATCH_SHA256,
                )
                self.assertEqual(contract["fixedAcceleration"], "DFlash + Weaver")
                self.assertEqual(contract["kvStateDataType"], "BF16")
                self.assertTrue(contract["prefixCache"])
                self.assertEqual(
                    contract["promptExercisePolicy"],
                    launcher.uzu_qualification_prompt_exercise_policy(context),
                )
                self.assertEqual(
                    contract["osReservePolicy"],
                    "max-4gib-or-10-percent-total-v1",
                )
                self.assertEqual(
                    contract["osReserveMinimumBytes"],
                    launcher.SESSION_OS_RESERVE_MIN_BYTES,
                )
                self.assertEqual(
                    contract["osReserveBytes"],
                    max(
                        launcher.SESSION_OS_RESERVE_MIN_BYTES,
                        round(48 * 1024**3 * launcher.SESSION_OS_RESERVE_FRACTION),
                    ),
                )
                self.assertEqual(
                    contract["sandboxProfileSha256"],
                    launcher.UZU_SANDBOX_PROFILE_SHA256,
                )
                self.assertTrue(contract["rawListenerProtected"])
                self.assertEqual(
                    contract["nativeBoundaryContractId"],
                    launcher.UZU_NATIVE_BOUNDARY_CONTRACT_ID,
                )
                self.assertTrue(contract["nativeBearerAuthentication"])
                self.assertTrue(contract["oneUseApiKeyFile"])
                self.assertEqual(contract["nativeContextLimitTokens"], context)
                self.assertEqual(contract["nativeMaxOutputTokens"], 4_096)

                for legacy_version in (1, 2, 3, 4):
                    legacy = self.qualification_record(spec, context=context)
                    legacy["qualificationContract"]["id"] = (
                        f"qwen36-uzu-dflash-weaver-{context // 1024}k-v{legacy_version}"
                    )
                    legacy["qualificationContract"]["version"] = legacy_version
                    self.assertIsNone(
                        launcher.route_qualification_metrics(legacy, spec),
                        f"a v{legacy_version} receipt must never authorize the v4 Uzu route",
                    )

                missing_policy = self.qualification_record(spec, context=context)
                del missing_policy["qualificationContract"]["promptExercisePolicy"]
                self.assertIsNone(
                    launcher.route_qualification_metrics(missing_policy, spec),
                    "a receipt without the v4 prompt-exercise policy must fail closed",
                )

    def test_uzu_output_contract_receipts_keep_separate_identities(self) -> None:
        model, _payload, _binary = self.qualification_fixture()
        spec = launcher.route_qualification_spec(model, "uzu", 16_384)
        self.assertIsNotNone(spec)
        assert spec is not None
        first = self.qualification_record(spec)
        second = copy.deepcopy(first)
        second.update({
            "id": "uzu-qualification-record-2048",
            "createdAt": (
                datetime.now(timezone.utc) - timedelta(minutes=1)
            ).isoformat(),
            "configuredOutputLimit": 2_048,
        })
        second["qualificationContract"]["configuredOutputLimit"] = 2_048

        self.assertNotEqual(
            launcher.benchmark_record_identity(first),
            launcher.benchmark_record_identity(second),
        )
        self.assertEqual(
            [record["id"] for record in launcher.latest_benchmark_records_by_identity(
                [first, second],
            )],
            ["uzu-qualification-record", "uzu-qualification-record-2048"],
        )

    def test_both_uzu_agentic_suites_survive_the_full_saved_evidence_audit(self) -> None:
        for context in launcher.UZU_SAFE_CONTEXT_WINDOWS:
            with self.subTest(context=context):
                model, _payload, _binary = self.qualification_fixture(context)
                spec = launcher.route_qualification_spec(model, "uzu", context)
                self.assertIsNotNone(spec)
                assert spec is not None
                record = self.qualification_record(spec, context=context)
                record["modes"]["ar"]["agenticMetrics"] = {
                    "cacheTelemetryAvailable": True,
                    "coldTTFTSeconds": 1.0,
                    "warmPrefixTTFTSeconds": 0.8,
                    "prefixReuseFactor": 1.25,
                    "toolIngestTTFTSeconds": 0.9,
                    "steadyTurnTTFTSeconds": 0.7,
                    "toolReuseFactor": 1.2,
                }
                metrics = launcher.route_qualification_metrics(record, spec)
                self.assertIsNotNone(metrics)
                record["qualification"] = {
                    "reasoningEnabled": True,
                    "reasoningObserved": True,
                    "answerObserved": True,
                    "terminalCompletionObserved": True,
                    "authoritativeUsage": True,
                    "metrics": metrics,
                }
                evidence = {
                    "context": context,
                    "output": 4_096,
                    "client": "chat",
                    "reasoning": "auto",
                    "kv": "off",
                    "samplingFingerprint": "c" * 64,
                }
                with mock.patch.object(
                    launcher, "hardware_fingerprint", return_value="uzu-test-mac",
                ):
                    self.assertTrue(
                        launcher._local_benchmark_record_verified(
                            model["backends"]["uzu"], record, evidence,
                        ),
                        "a completed Uzu receipt must remain reusable instead of looping back to qualification",
                    )

                record["suite"] = "route-qualification-uzu-unknown"
                with mock.patch.object(
                    launcher, "hardware_fingerprint", return_value="uzu-test-mac",
                ):
                    self.assertFalse(
                        launcher._local_benchmark_record_verified(
                            model["backends"]["uzu"], record, evidence,
                        ),
                    )

    def test_uzu_calibration_normalizes_meaningless_fan_choices(self) -> None:
        model, payload, binary = self.qualification_fixture()
        plans = []
        with mock.patch.dict(
            launcher.BINARIES, {"mirai": str(binary)}, clear=True,
        ), mock.patch.object(
            launcher, "route_qualification_memory_admission",
            return_value={
                "decision": "ready",
                "launchable": True,
                "requiresAcknowledgement": False,
                "label": "Ready",
                "detail": "The fixed route fits the verified memory envelope.",
            },
        ):
            for cooling in ("smart", "max"):
                request = copy.deepcopy(payload)
                request["calibrationCooling"] = cooling
                request.setdefault("options", {})["fan"] = cooling
                plans.append(launcher.calibration_plan(request, [model]))

        for plan in plans:
            self.assertTrue(plan["routeQualification"])
            self.assertEqual(plan["calibrationCooling"], "default")
            self.assertEqual(plan["calibrationCoolingLabel"], "System controlled")
            self.assertTrue(plan["calibrationCoolingLocked"])
            self.assertIn("does not expose fan control", plan["calibrationCoolingReason"])
            self.assertNotIn("fan", plan["request"]["options"])
            self.assertEqual(
                plan["engines"][0]["reason"],
                launcher.route_qualification_engine_reason("uzu"),
            )
        self.assertEqual(plans[0]["contractId"], plans[1]["contractId"])

    def test_uzu_qualification_requires_runtime_default_reasoning_on(self) -> None:
        model, payload, binary = self.qualification_fixture()
        spec = launcher.route_qualification_spec(model, "uzu")
        self.assertIsNotNone(spec)
        assert spec is not None
        reasoning = launcher.route_qualification_reasoning_contract(
            payload, model, spec,
        )
        self.assertTrue(reasoning["reasoningEnabled"])
        self.assertTrue(reasoning["runtimeControlled"])
        self.assertEqual(reasoning["measured"], "auto")
        self.assertFalse(reasoning["changesVisibleSettingWhenApplied"])

        disabled = copy.deepcopy(payload)
        disabled["reasoning"] = "off"
        rejected = launcher.route_qualification_reasoning_contract(
            disabled, model, spec,
        )
        self.assertFalse(rejected["reasoningEnabled"])
        with mock.patch.dict(
            launcher.BINARIES, {"mirai": str(binary)}, clear=True,
        ), self.assertRaisesRegex(ValueError, "reasoning|Thinking|thinking"):
            launcher.validated_route_qualification_request(
                {**disabled, "scope": "qualification"}, [model],
            )

    def test_pi_transport_requires_exact_pair_and_ignores_untrusted_override(self) -> None:
        model, _, _ = self.qualification_fixture()
        capability = model["backends"]["uzu"]
        capability["piTransportVersion"] = launcher.UZU_PI_TESTED_VERSION
        capability["runtimeIdentity"]["binary"]["sha256"] = launcher.UZU_PI_TESTED_RUNTIME_SHA256
        self.assertTrue(launcher.resolved_client_support("uzu", "pi", capability)["supported"])
        for key, value in (("runnable", False), ("modelCommit", "changed"),
                           ("modelRegistryId", "another-model"), ("piTransportVersion", "0.84.3"),
                           ("runtimeIdentity", []), ("runtimeIdentity", {"binary": "bad"})):
            changed = copy.deepcopy(capability)
            changed[key] = value
            changed["clientSupport"] = {"pi": {"supported": True}}
            with self.subTest(key=key, value=value):
                self.assertFalse(launcher.resolved_client_support("uzu", "pi", changed)["supported"])
        for malformed in (None, [], "bad", True):
            self.assertFalse(launcher.uzu_pi_transport_supported(malformed))
        for client in ("codex", "opencode"):
            self.assertFalse(launcher.resolved_client_support("uzu", client, capability)["supported"])
        for mutation in ({"binaryIdentityPinned": False}, {"binary": {"sha256": "changed"}}):
            changed = copy.deepcopy(capability)
            changed["runtimeIdentity"].update(mutation)
            self.assertFalse(launcher.uzu_pi_transport_supported(changed))

    def test_pi_capacity_reuses_exact_chat_receipt_without_creating_agent_speed_evidence(self) -> None:
        model, payload, _ = self.qualification_fixture()
        capability = model["backends"]["uzu"]
        capability["piTransportVersion"] = launcher.UZU_PI_TESTED_VERSION
        capability["runtimeIdentity"]["binary"]["sha256"] = launcher.UZU_PI_TESTED_RUNTIME_SHA256
        spec = launcher.route_qualification_spec(model, "uzu")
        record = self.qualification_record(spec)
        self.bind_qualification_record(model, payload, record, spec)
        original = copy.deepcopy(record)
        pi_request = {**payload, "client": "pi", "generation": {"sampling": "model"}}
        with mock.patch.object(launcher, "hardware_fingerprint", return_value="uzu-test-mac"):
            self.assertIsNotNone(launcher._uzu_qualified_session_record(payload, model))
            self.assertIsNotNone(launcher._uzu_qualified_session_record(pi_request, model))
            for key, value in (("context", 32768), ("output", 8192),
                               ("reasoning", "off"), ("client", "opencode")):
                with self.subTest(key=key):
                    self.assertIsNone(launcher._uzu_qualified_session_record({**pi_request, key: value}, model))
            evidence = launcher.optimizer_evidence(model, payload["context"], payload["output"],
                "pi", "auto", "off", payload["chat"])
            launcher.add_benchmark_engine_evidence(evidence, model, payload["options"], ["uzu"])
            self.assertIsNone(launcher.verified_route_qualification(model, "uzu", evidence))
            with mock.patch.object(launcher, "optimal_request", return_value={
                "backend": "uzu", "modelId": model["id"], "options": payload["options"],
            }):
                selected = launcher.best_engine_request(pi_request, [model])
            self.assertEqual(selected["engineNextAction"]["id"], "keep-current")
            self.assertFalse(selected["engineNextAction"]["requiresCalibration"])
            self.assertEqual(selected["engineEvidenceTier"], "local-capacity-only")
            self.assertEqual(selected["qualifiedRoutes"], [])
            self.assertNotIn("engineEvidenceBinding", selected)
            self.assertFalse(launcher.benchmark_backend_eligibility(model, "uzu", "pi", "auto", "off")[0])
            with self.assertRaisesRegex(ValueError, "Pi speed testing is not yet available"):
                launcher.validated_benchmark_request(pi_request, [model])
            self.assertEqual(record, original)
            record["createdAt"] = "2000-01-01T00:00:00+00:00"
            self.assertIsNone(launcher._uzu_qualified_session_record(pi_request, model))

    def test_uzu_capacity_reuses_same_probe_budget_across_response_ceilings(self) -> None:
        model, payload, _ = self.qualification_fixture(131_072)
        payload["output"] = 50_000
        capability = model["backends"]["uzu"]
        capability["piTransportVersion"] = launcher.UZU_PI_TESTED_VERSION
        capability["runtimeIdentity"]["binary"]["sha256"] = launcher.UZU_PI_TESTED_RUNTIME_SHA256
        spec = launcher.route_qualification_spec(model, "uzu", 131_072)
        record = self.qualification_record(spec, context=131_072, configured_output=50_000)
        self.bind_qualification_record(model, payload, record, spec)
        original = copy.deepcopy(record)
        with mock.patch.object(launcher, "hardware_fingerprint", return_value="uzu-test-mac"):
            for client in ("chat", "pi"):
                for output in (8_192, 16_384, 64_000):
                    request = {**payload, "client": client, "output": output, "generation": {"sampling": "model"}}
                    with self.subTest(client=client, output=output):
                        reused = launcher._uzu_qualified_session_record(request, model)
                        self.assertIsNotNone(reused)
                        self.assertEqual(reused["configuredOutputLimit"], 50_000)
            for changes in ({"output":4096}, {"context":65536}, {"reasoning":"off"}, {"client":"opencode"}):
                self.assertIsNone(launcher._uzu_qualified_session_record({**payload, **changes}, model))
            evidence = launcher.optimizer_evidence(model, 131_072, 64_000, "chat", "auto", "off", payload["chat"])
            launcher.add_benchmark_engine_evidence(evidence, model, payload["options"], ["uzu"])
            self.assertIsNone(launcher.verified_route_qualification(model, "uzu", evidence), "speed evidence remains exact")
            for field, bad in (("runtimeVersion", "changed"), ("benchmarkModelFingerprint", "changed")):
                before = capability[field]
                capability[field] = bad
                self.assertIsNone(launcher._uzu_qualified_session_record({**payload, "output":64_000}, model))
                capability[field] = before
            self.assertEqual(record, original)
            record["createdAt"] = "2000-01-01T00:00:00Z"
            self.assertIsNone(launcher._uzu_qualified_session_record({**payload, "output":64_000}, model))

    def test_pi_session_keeps_pi_plan_but_checks_normalized_capacity_request(self) -> None:
        model, payload, binary = self.qualification_fixture()
        capability = model["backends"]["uzu"]
        capability["piTransportVersion"] = launcher.UZU_PI_TESTED_VERSION
        capability["runtimeIdentity"]["binary"]["sha256"] = launcher.UZU_PI_TESTED_RUNTIME_SHA256
        payload.update({"client": "pi", "agentHost": "console", "context": "16384", "output": "4096", "options": None})
        with mock.patch.dict(launcher.BINARIES, {"mirai": str(binary), "pi": "/test/pi"}), \
             mock.patch.object(launcher, "free_port", side_effect=[18080, 18081]), \
             mock.patch.object(launcher, "verified_route_qualification", return_value={"id": "qualified"}) as verified, \
             mock.patch.object(launcher, "build_engine_plan"), \
             mock.patch.object(launcher, "build_client_plan"), \
             mock.patch.object(launcher, "_validated_uzu_route", return_value=(binary, {}, {}, ())) as current_artifact:
            plan = launcher.normalized_request(payload, [model], purpose="session")
        current_artifact.assert_called_once()
        self.assertEqual(current_artifact.call_args.args[0].model["id"], model["id"])
        self.assertEqual(plan.client, "pi")
        self.assertEqual(plan.agent_host, "console")
        evidence = verified.call_args.args[2]
        self.assertEqual(evidence["client"], "chat")
        self.assertEqual(evidence["context"], 16384)
        self.assertEqual(evidence["output"], 4096)
        with mock.patch.object(launcher, "command_version", return_value="changed"), \
             self.assertRaisesRegex(ValueError, "Pi version changed"):
            launcher.build_pi_client(plan, launcher.ClientRoute("fixture", "fixture", "http://127.0.0.1/v1", "fixture"))

    def test_uzu_session_and_route_check_require_a_matching_qualification(self) -> None:
        model, payload, binary = self.qualification_fixture()
        for purpose in ("session", "route-check"):
            with self.subTest(purpose=purpose):
                with mock.patch.dict(
                    launcher.BINARIES, {"mirai": str(binary)}, clear=True,
                ), mock.patch.object(
                    launcher, "free_port", side_effect=[18_080, 18_081],
                ) as allocate_port, mock.patch.object(
                    launcher, "verified_route_qualification", return_value=None,
                ) as verified, mock.patch.object(
                    launcher, "build_engine_plan",
                ), mock.patch.object(
                    launcher, "build_client_plan",
                ):
                    with self.assertRaisesRegex(ValueError, "qualification"):
                        launcher.normalized_request(
                            payload, [model], purpose=purpose,
                        )
                    verified.assert_called_once()
                    allocate_port.assert_not_called()

        with mock.patch.dict(
            launcher.BINARIES, {"mirai": str(binary)}, clear=True,
        ), mock.patch.object(
            launcher, "free_port", side_effect=[18_080, 18_081],
        ), mock.patch.object(
            launcher, "verified_route_qualification", return_value={"id": "qualified"},
        ) as verified, mock.patch.object(
            launcher, "build_engine_plan",
        ), mock.patch.object(launcher, "build_client_plan"), mock.patch.object(
            launcher, "_validated_uzu_route", return_value=(str(binary), {}, Path(model["path"]), {}, ()),
        ) as artifacts:
            plan = launcher.normalized_request(payload, [model], purpose="session")
        self.assertEqual(plan.backend, "uzu")
        self.assertEqual(plan.context, 16_384)
        verified.assert_called_once()
        artifacts.assert_called_once()
        self.assertEqual(artifacts.call_args.args[0].model, model)
        self.assertEqual(artifacts.call_args.args[0].purpose, "session")
        evidence = verified.call_args.args[2]
        self.assertEqual(evidence["context"], 16_384)
        self.assertEqual(evidence["client"], "chat")
        self.assertEqual(evidence["reasoning"], "auto")

    def test_uzu_qualification_metrics_require_global_headroom_and_clean_unload(self) -> None:
        model, _payload, _binary = self.qualification_fixture()
        spec = launcher.route_qualification_spec(model, "uzu")
        self.assertIsNotNone(spec)
        assert spec is not None
        record = self.qualification_record(spec)
        metrics = launcher.route_qualification_metrics(record, spec)
        self.assertIsNotNone(metrics)
        assert metrics is not None
        self.assertEqual(metrics["peakMemoryBytes"], 21 * 1024**3)
        self.assertTrue(metrics["cleanUnloadVerified"])
        self.assertTrue(metrics["correctnessVerified"])

        mutations = (
            lambda value: value["modes"]["ar"]["resourceTelemetry"].update(
                {"memorySampleCount": 7},
            ),
            lambda value: value["modes"]["ar"]["resourceTelemetry"].update(
                {"minimumHeadroomPercent": 9.0},
            ),
            lambda value: value["modes"]["ar"]["resourceTelemetry"].update(
                {"peakProcessGroupPhysicalFootprintBytes": launcher.UZU_PROCESS_MEMORY_CEILING_BYTES},
            ),
            lambda value: value["modes"]["ar"]["resourceTelemetry"].update(
                {"samplingComplete": False},
            ),
            lambda value: value["unloadEvidence"].update({"portsClosed": False}),
            lambda value: value["correctnessContract"].update({"exact": False}),
            lambda value: value["modes"]["ar"]["samples"][0].update(
                {"reasoningObserved": False},
            ),
            lambda value: value["modes"]["ar"]["samples"][0].update(
                {"completionTokens": 127},
            ),
            lambda value: value["modes"]["ar"]["samples"][3].update(
                {"promptTokens": 1_024},
            ),
            lambda value: value["modes"]["ar"]["samples"][3].update(
                {"targetPromptTokens": 1_024},
            ),
            lambda value: value["qualificationContract"].update(
                {"exactContext": 32_768},
            ),
            lambda value: value["qualificationContract"].update(
                {"clientAgnostic": True},
            ),
        )
        for mutation in mutations:
            broken = copy.deepcopy(record)
            mutation(broken)
            self.assertIsNone(launcher.route_qualification_metrics(broken, spec))

    def test_legacy_pressure_receipt_cannot_certify_physical_capacity(self) -> None:
        model, _payload, _binary = self.qualification_fixture()
        spec = launcher.route_qualification_spec(model, "uzu")
        self.assertIsNotNone(spec)
        current = self.qualification_record(spec)
        self.assertIsNotNone(launcher.route_qualification_metrics(current, spec))
        legacy = copy.deepcopy(current)
        legacy["modes"]["ar"]["resourceTelemetry"].update({
            "version": 1, "memorySemanticsVersion": 1,
            "memorySource": "memory_pressure -Q", "minimumHeadroomBytes": None,
            "minimumHeadroomPercent": 84.0,
        })
        self.assertIsNone(launcher.route_qualification_metrics(legacy, spec))
        self.assertEqual(legacy["modes"]["ar"]["medianDecodeTokensPerSecond"], 31.5)
        unversioned = copy.deepcopy(current)
        unversioned["qualificationContract"].pop("memorySemanticsVersion")
        self.assertIsNone(launcher.route_qualification_metrics(unversioned, spec))

    def test_high_context_receipts_require_authoritative_near_tier_prompt_usage(self) -> None:
        for context in (65_536, 131_072):
            model, _payload, _binary = self.qualification_fixture(context)
            spec = launcher.route_qualification_spec(model, "uzu", context)
            self.assertIsNotNone(spec)
            assert spec is not None
            minimum = (context * 9 + 9) // 10
            for scenario in launcher.UZU_QUALIFICATION_NEAR_TIER_SCENARIOS:
                with self.subTest(context=context, scenario=scenario):
                    boundary = self.qualification_record(spec, context=context)
                    sample = next(
                        item for item in boundary["modes"]["ar"]["samples"]
                        if item["scenario"] == scenario
                    )
                    sample["promptTokens"] = minimum
                    rows = boundary["modes"]["ar"]["samples"]
                    rows[3]["targetPromptTokens"] = (
                        rows[2]["promptTokens"] + rows[2]["completionTokens"] + 128
                    )
                    if scenario == "toolIngest":
                        rows[3]["promptTokens"] = rows[3]["targetPromptTokens"]
                    self.assertIsNotNone(
                        launcher.route_qualification_metrics(boundary, spec),
                        "the exact 90% ceiling boundary must remain admissible",
                    )

                    underfilled = copy.deepcopy(boundary)
                    underfilled_sample = next(
                        item for item in underfilled["modes"]["ar"]["samples"]
                        if item["scenario"] == scenario
                    )
                    underfilled_sample["promptTokens"] = minimum - 1
                    self.assertIsNone(
                        launcher.route_qualification_metrics(underfilled, spec),
                        "one token below the near-tier boundary must fail closed",
                    )

                    unauthoritative = copy.deepcopy(boundary)
                    unauthoritative_sample = next(
                        item for item in unauthoritative["modes"]["ar"]["samples"]
                        if item["scenario"] == scenario
                    )
                    unauthoritative_sample["authoritativeUsage"] = False
                    self.assertIsNone(
                        launcher.route_qualification_metrics(unauthoritative, spec),
                    )

                    retargeted = copy.deepcopy(boundary)
                    retargeted_sample = next(
                        item for item in retargeted["modes"]["ar"]["samples"]
                        if item["scenario"] == scenario
                    )
                    retargeted_sample["targetPromptTokens"] = minimum
                    self.assertIsNone(
                        launcher.route_qualification_metrics(retargeted, spec),
                        "the exact generated target remains receipt-bound",
                    )

    def test_uzu_qualification_request_uses_packaged_sampling_and_bounded_field_names(self) -> None:
        plan = mock.Mock(
            backend="uzu",
            model={"servedId": launcher.UZU_MODEL_REGISTRY_ID},
            port=18_080,
            secrets={"apiKey": "private"},
            reasoning="auto",
            options={"_qualificationThinkingBudgetTokens": 384},
        )
        request = launcher.build_benchmark_completion_request(
            plan,
            "generated qualification prompt",
            launcher.UZU_QUALIFICATION_SAMPLE_MAX_TOKENS,
            {
                "temperature": 0.0,
                "top_p": 1.0,
                "top_k": 0,
                "presence_penalty": 0.0,
                "frequency_penalty": 0.0,
                "seed": 17,
            },
        )
        body = json.loads(request.data)
        self.assertEqual(
            body["max_completion_tokens"],
            launcher.UZU_QUALIFICATION_SAMPLE_MAX_TOKENS,
        )
        self.assertNotIn("max_tokens", body)
        self.assertNotIn("stream_options", body)
        self.assertEqual(body["reasoning_effort"], "default")
        for key in (
            "temperature", "top_p", "top_k", "presence_penalty",
            "frequency_penalty", "seed",
        ):
            self.assertNotIn(key, body)

    def test_uzu_budget_is_separate_from_ssd_budget_and_preserves_visible_limit(self) -> None:
        for backend, expected in (("uzu", 4096), ("llamacpp", 512)):
            job = {"backend": backend, "output": 4096, "suite": {}}
            launcher.apply_route_qualification_budget(job)
            self.assertEqual(job["output"], 4096)
            self.assertEqual(job["suite"]["maxTokens"], expected)
            with self.assertRaisesRegex(ValueError, "requires at least"):
                launcher.apply_route_qualification_budget({"backend": backend, "output": (2048 if backend == "uzu" else expected) - 1, "suite": {}})

    def test_old_short_budget_cannot_authorize_new_uzu_contract(self) -> None:
        model, _, _ = self.qualification_fixture()
        spec = launcher.route_qualification_spec(model, "uzu", 16384)
        record = self.qualification_record(spec)
        for target in (record, record["qualificationContract"]):
            target["measuredRequestMaxTokens"] = 512
        record["outputMin"] = record["outputMax"] = 512
        record["qualificationContract"]["sampleMaxTokens"] = 512
        self.assertIsNone(launcher.route_qualification_metrics(record, spec))

    def test_old_synthetic_reply_policy_cannot_authorize_conversation_route(self) -> None:
        model, _, _ = self.qualification_fixture()
        spec = launcher.route_qualification_spec(model, "uzu", 16384)
        record = self.qualification_record(spec)
        record["qualificationContract"]["promptExercisePolicy"]["id"] = (
            "uzu-near-tier-authoritative-prompt-v3-code-fixture"
        )
        self.assertIsNone(launcher.route_qualification_metrics(record, spec))

    def test_unusable_uzu_sample_fails_before_followup_requests(self) -> None:
        sample = {
            "terminalComplete": True, "responseLimitReached": False,
            "reasoningObserved": True, "answerObserved": True,
            "promptTokens": 49100,
        }
        case = {"label": "Cold agent turn", "targetPromptTokens": 49152}
        launcher.validate_uzu_qualification_sample(sample, case, 512)
        for change in (
            {"terminalComplete": False}, {"responseLimitReached": True},
            {"reasoningObserved": False}, {"answerObserved": False},
        ):
            with self.subTest(change=change), self.assertRaisesRegex(RuntimeError, "later turns"):
                launcher.validate_uzu_qualification_sample({**sample, **change}, case, 512)
        with self.assertRaisesRegex(RuntimeError, "intended prompt size"):
            launcher.validate_uzu_qualification_sample({**sample, "promptTokens": 59225}, case, 512)

    def test_failed_uzu_sample_reports_channels_without_generated_text(self) -> None:
        case = {"label": "Cold agent turn", "targetPromptTokens": 49152}
        sample = {
            "terminalComplete": False, "responseLimitReached": True,
            "reasoningObserved": True, "answerObserved": False,
            "completionTokens": 2048, "reasoningCharacters": 8192,
            "answerCharacters": 0, "content": "PRIVATE GENERATED TEXT",
            "finishReason": "PRIVATE FINISH STRING",
        }
        for answer, expected in (
            (False, "Only reasoning output was observed"),
            (True, "Reasoning and answer output were both observed"),
        ):
            with self.subTest(answer=answer), self.assertRaises(RuntimeError) as caught:
                launcher.validate_uzu_qualification_sample(
                    {**sample, "answerObserved": answer}, case, 2048,
                )
            message = str(caught.exception)
            self.assertIn(expected, message)
            self.assertIn("2,048 output tokens", message)
            self.assertIn("8,192 reasoning characters", message)
            self.assertIn("runtime reported a length limit", message)
            self.assertNotIn("PRIVATE", message)

    def test_uzu_conversation_preserves_actual_replies_and_reserves_context(self) -> None:
        suite = launcher.BENCHMARK_SUITES[launcher.ROUTE_QUALIFICATION_UZU_64K_SUITE]
        cases = launcher.benchmark_agentic_cases(suite, require_complete_answer=True)
        history = []
        previous = None
        for index, template in enumerate(cases):
            case = launcher.uzu_conversation_case(template, history, previous, 65536, 2048)
            self.assertEqual(case["messages"][:-1], history if index else template["messages"][:-1])
            self.assertLessEqual(case["targetPromptTokens"] + 2048, 65536)
            self.assertNotIn("reasoning_content", repr(template))
            reply = {"role": "assistant", "content": f" answer {index}\n",
                     "reasoning_content": f" exact reasoning {index} λ\n"}
            history = [*case["messages"], reply]
            previous = {"promptTokens": case["targetPromptTokens"], "completionTokens": 1024}
        self.assertEqual([m for m in history if "reasoning_content" in m], [
            {"role": "assistant", "content": f" answer {i}\n",
             "reasoning_content": f" exact reasoning {i} λ\n"} for i in range(4)
        ])
        with self.assertRaisesRegex(RuntimeError, "response reserve"):
            launcher.uzu_conversation_case(cases[3], history, {
                "promptTokens": 64000, "completionTokens": 2048,
            }, 65536, 2048)
        with self.assertRaisesRegex(RuntimeError, "missing"):
            launcher.uzu_conversation_case(cases[1], [], previous, 65536, 2048)

    def test_uzu_adaptive_output_is_bounded_and_receipt_verified(self) -> None:
        self.assertEqual(launcher.benchmark_repeated_phrase_fraction("short output"), 0)
        self.assertEqual(launcher.benchmark_repeated_phrase_fraction(" ".join(str(i) for i in range(100))), 0)
        self.assertGreater(launcher.benchmark_repeated_phrase_fraction(" repeat this sentence" * 100), .9)
        self.assertEqual(launcher.uzu_qualification_request_tokens("cold", 49152, 65536, 8192), 8192)
        self.assertEqual(launcher.uzu_qualification_request_tokens("toolIngest", 60416, 65536, 8192), 2432)
        self.assertEqual(launcher.uzu_qualification_request_tokens("steadyTurn", 61056, 65536, 8192), 3968)
        self.assertEqual(launcher.route_qualification_sample_tokens("uzu", 4096), 4096)
        model, _, _ = self.qualification_fixture(65536)
        spec = launcher.route_qualification_spec(model, "uzu", 65536)
        record = self.qualification_record(spec, context=65536)
        for output in (2048, 4096, 8192, 16384):
            with self.subTest(output=output):
                bounded = self.qualification_record(spec, context=65536, configured_output=output)
                restored = json.loads(json.dumps(bounded))
                self.assertIsNotNone(launcher.route_qualification_metrics(restored, spec))
                self.assertTrue(launcher.benchmark_record_output_contract_verified(restored, output))
                self.assertLessEqual(restored["outputMax"], min(output, 8192))
        self.assertIsNotNone(launcher.route_qualification_metrics(record, spec))
        self.assertTrue(launcher.benchmark_record_output_contract_verified(record, 4096))
        self.assertFalse(launcher.benchmark_record_output_contract_verified(record, 8192))
        for mutate in (
            lambda r: r["modes"]["ar"]["samples"][2].update(requestedMaxTokens=8192),
            lambda r: r.update(outputMin=8192),
            lambda r: r["qualificationContract"]["outputBudgetPolicy"].update(promptReserveTokens=0),
        ):
            altered = copy.deepcopy(record)
            mutate(altered)
            self.assertIsNone(launcher.route_qualification_metrics(altered, spec))
            self.assertFalse(launcher.benchmark_record_output_contract_verified(altered, 4096))

    def test_uzu_long_context_cases_supply_code_and_preserve_shared_prefix(self) -> None:
        suite = launcher.BENCHMARK_SUITES[launcher.ROUTE_QUALIFICATION_UZU_64K_SUITE]
        cases = launcher.benchmark_agentic_cases(suite, require_complete_answer=True)
        self.assertEqual([c["scenario"] for c in cases], launcher.ROUTE_QUALIFICATION_SCENARIOS)
        base = cases[0]["messages"][:3]
        for case in cases:
            self.assertEqual(case["messages"][:3], base)
            self.assertIn("def reply(model, prompt, reasoning)", case["messages"][1]["content"])
            self.assertIn("context padding", case["messages"][0]["content"])
            self.assertNotIn("detailed engineering assessment", case["messages"][-1]["content"])
        self.assertIn("two regression tests", cases[1]["messages"][-1]["content"])
        self.assertIn("(model, prompt)", cases[2]["messages"][-1]["content"])
        self.assertIn("revision integer", cases[3]["messages"][-1]["content"])

    def test_uzu_live_guard_stops_only_after_sustained_whole_mac_pressure(self) -> None:
        def run_guard(free_percentages: list[float]) -> tuple[bool, mock.Mock, mock.Mock]:
            manager = launcher.RunManager()
            plan = mock.Mock(backend="uzu", purpose="session")
            polls = {"count": 0}
            process = mock.Mock(pid=4_321)

            def poll() -> int | None:
                polls["count"] += 1
                return None if polls["count"] <= 24 else 0

            process.poll.side_effect = poll
            stopped = {"value": False}
            cancel_event = mock.Mock()
            cancel_event.is_set.side_effect = lambda: stopped["value"]
            cancel_event.wait.return_value = False
            cancel_event.set.side_effect = lambda: stopped.__setitem__("value", True)
            manager.plan = plan
            manager.process = process
            manager.state = {"phase": "running", "message": "Running", "events": []}
            pressure_calls = {"count": 0}

            def pressure() -> dict:
                index = min(pressure_calls["count"], len(free_percentages) - 1)
                pressure_calls["count"] += 1
                return physical_snapshot({
                    "memoryAvailable": True,
                    "totalBytes": 48 * 1024**3,
                    "freePercent": free_percentages[index],
                })

            clock = {"value": 0.0}

            def monotonic() -> float:
                clock["value"] += 1.1
                return clock["value"]

            with mock.patch.object(
                launcher.os, "getpgid", return_value=4_321,
            ), mock.patch.object(
                launcher, "darwin_process_group_physical_footprint",
                return_value={
                    "processGroupFootprintAvailable": True,
                    "processGroupMemberCount": 1,
                    "processGroupPhysicalFootprintBytes": 20 * 1024**3,
                    "processGroupLifetimePeakPhysicalFootprintBytes": 21 * 1024**3,
                },
            ), mock.patch.object(
                launcher, "apple_memory_pressure_state", side_effect=pressure,
            ) as pressure_reader, mock.patch.object(
                launcher.time, "monotonic", side_effect=monotonic,
            ), mock.patch.object(manager, "_stop_owned") as stop_owned:
                manager._guard_uzu_memory(plan, process, cancel_event)
            return stopped["value"], stop_owned, pressure_reader

        stopped, stop_owned, pressure_reader = run_guard([8.0, 8.0, 8.0])
        self.assertTrue(stopped)
        stop_owned.assert_called_once()
        self.assertGreaterEqual(pressure_reader.call_count, 2)

        stopped, stop_owned, pressure_reader = run_guard([8.0, 25.0, 25.0])
        self.assertFalse(stopped)
        stop_owned.assert_not_called()
        self.assertGreaterEqual(pressure_reader.call_count, 2)

    def test_uzu_live_guard_fails_closed_when_system_pressure_is_unreadable(self) -> None:
        manager = launcher.RunManager()
        plan = mock.Mock(backend="uzu", purpose="session")
        polls = {"count": 0}
        process = mock.Mock(pid=4_321)

        def poll() -> int | None:
            polls["count"] += 1
            return None if polls["count"] <= 24 else 0

        process.poll.side_effect = poll
        stopped = {"value": False}
        cancel_event = mock.Mock()
        cancel_event.is_set.side_effect = lambda: stopped["value"]
        cancel_event.wait.return_value = False
        cancel_event.set.side_effect = lambda: stopped.__setitem__("value", True)
        manager.plan = plan
        manager.process = process
        manager.state = {"phase": "running", "message": "Running", "events": []}
        clock = {"value": 0.0}

        def monotonic() -> float:
            clock["value"] += 1.1
            return clock["value"]

        with mock.patch.object(
            launcher.os, "getpgid", return_value=4_321,
        ), mock.patch.object(
            launcher, "darwin_process_group_physical_footprint",
            return_value={
                "processGroupFootprintAvailable": True,
                "processGroupMemberCount": 1,
                "processGroupPhysicalFootprintBytes": 20 * 1024**3,
                "processGroupLifetimePeakPhysicalFootprintBytes": 21 * 1024**3,
            },
        ), mock.patch.object(
            launcher, "apple_memory_pressure_state",
            return_value=physical_snapshot({
                "memoryAvailable": False,
                "totalBytes": 48 * 1024**3,
                "freePercent": None,
            }),
        ) as pressure_reader, mock.patch.object(
            launcher.time, "monotonic", side_effect=monotonic,
        ), mock.patch.object(manager, "_stop_owned") as stop_owned:
            manager._guard_uzu_memory(plan, process, cancel_event)
        self.assertTrue(stopped["value"])
        stop_owned.assert_called_once_with(plan)
        self.assertGreaterEqual(pressure_reader.call_count, 3)
        self.assertIn("physical memory", manager.state["message"].lower())


if __name__ == "__main__":
    unittest.main()
