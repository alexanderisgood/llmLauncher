from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
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
        runtime = self.root / "runtimes" / "uzu-0.5.22" / "mirai"
        runtime.parent.mkdir(parents=True)
        runtime.write_bytes(b"pinned-uZu-0.5.22-test-binary")
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
            "samplingReason": "Packaged model defaults are fixed.",
            "contextWindows": [16_384, 32_768],
            "contextMaximum": 32_768,
            "modelRegistryId": launcher.UZU_MODEL_REGISTRY_ID,
            "modelRepository": launcher.UZU_MODEL_REPOSITORY,
            "modelCommit": launcher.UZU_MODEL_COMMIT,
            "modelToolchainVersion": launcher.UZU_MODEL_TOOLCHAIN_VERSION,
            "benchmarkModelFingerprint": fingerprint,
            "receiptFingerprint": fingerprint,
            "runtimeVersion": "Uzu fixed-test",
            "runtimeIdentity": {
                "ready": True,
                "binary": {"sha256": "b" * 64},
                "networkSandbox": True,
                "memorySafetyBlocked": False,
                "rawListenerAuthenticated": True,
                "rawListenerIsolated": False,
                "listenerIsolationBlocked": False,
            },
            "qualificationSystemContract": {
                "osReserveBytes": max(
                    launcher.SESSION_OS_RESERVE_MIN_BYTES,
                    round(48 * 1024**3 * launcher.SESSION_OS_RESERVE_FRACTION),
                ),
                "sandboxProfileSha256": launcher.UZU_SANDBOX_PROFILE_SHA256,
                "rawListenerProtected": True,
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
            "output": 1_024,
            "reasoning": "auto",
            "mode": "custom",
            "suite": "quick",
            "enginePreference": "throughput",
            "options": {"acceleration": "off", "depth": 1, "kv": "off"},
            "chat": {"systemPrompt": "", "sampling": "model"},
        }
        return model, payload, binary

    def qualification_record(
        self, spec: dict, *, context: int = 16_384,
    ) -> dict:
        total_memory = 48 * 1024**3
        minimum_headroom = 12.0
        samples = []
        for index, scenario in enumerate(launcher.ROUTE_QUALIFICATION_SCENARIOS):
            ttft = 0.5 + index * 0.05
            decode_tps = 30.0 + index
            samples.append({
                "scenario": scenario,
                "scenarioLabel": scenario,
                "cacheExpected": index > 0,
                "targetPromptTokens": 3_000 + index * 500,
                "repetition": 1,
                "promptTokens": 3_000 + index * 500,
                "completionTokens": 256,
                "requestedMaxTokens": launcher.ROUTE_QUALIFICATION_MAX_TOKENS,
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
            "createdAt": "2026-09-03T12:00:00Z",
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
            "outputMin": launcher.ROUTE_QUALIFICATION_MAX_TOKENS,
            "outputMax": launcher.ROUTE_QUALIFICATION_MAX_TOKENS,
            "configuredOutputLimit": 1_024,
            "measuredRequestMaxTokens": launcher.ROUTE_QUALIFICATION_MAX_TOKENS,
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
                "sampleMaxTokens": launcher.ROUTE_QUALIFICATION_MAX_TOKENS,
                "answerReserveTokens": launcher.ROUTE_QUALIFICATION_ANSWER_RESERVE_TOKENS,
                "minimumCompletionTokens": launcher.ROUTE_QUALIFICATION_MINIMUM_COMPLETION_TOKENS,
                "minimumDecodeTokensPerSecond": launcher.UZU_QUALIFICATION_MINIMUM_DECODE_TPS,
                "thinkingBudgetTokens": None,
                "configuredOutputLimit": 1_024,
                "measuredRequestMaxTokens": launcher.ROUTE_QUALIFICATION_MAX_TOKENS,
                "reasoningPolicy": spec["reasoningPolicy"],
                "toolProbeRequired": False,
                "memoryProofRequired": True,
                "memoryCeilingBytes": launcher.UZU_PROCESS_MEMORY_CEILING_BYTES,
                "modelFingerprint": "a" * 64,
                "modelRegistryId": launcher.UZU_MODEL_REGISTRY_ID,
                "modelCommit": launcher.UZU_MODEL_COMMIT,
                "modelToolchainVersion": launcher.UZU_MODEL_TOOLCHAIN_VERSION,
                "runtimeBinarySha256": "b" * 64,
                "fixedAcceleration": "DFlash + Weaver",
                "kvStateDataType": "BF16",
                "prefixCache": True,
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
                    "resourceTelemetry": {
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
                    },
                },
            },
        }

    def test_runtime_contract_accepts_pinned_signature_but_blocks_unsafe_release(self) -> None:
        runtime, sandbox, sha256 = self.runtime_fixture()
        with (
            mock.patch.multiple(
                launcher,
                UZU_RUNTIME_PATH=runtime,
                UZU_RUNTIME_RELEASE_BINARY_SHA256=sha256,
                UZU_SANDBOX_EXECUTABLE=sandbox,
            ),
            mock.patch.object(launcher.sys, "platform", "darwin"),
            mock.patch.object(launcher.platform, "machine", return_value="arm64"),
        ):
            contract = launcher.uzu_runtime_contract(runtime)

        self.assertFalse(contract["ready"])
        self.assertEqual(contract["version"], "Uzu 0.5.22")
        self.assertEqual(contract["binary"]["sha256"], sha256)
        self.assertTrue(contract["publisherSignatureValid"])
        self.assertEqual(contract["publisherTeamIdentifier"], "C39GZ239GY")
        self.assertTrue(contract["networkSandbox"])
        self.assertTrue(contract["memorySafetyBlocked"])
        self.assertTrue(contract["boundedContextReady"])
        self.assertTrue(contract["localOnly"])
        self.assertTrue(contract["telemetryBlocked"])
        self.assertTrue(contract["automaticDownloadsBlocked"])
        self.assertFalse(contract["rawListenerAuthenticated"])
        self.assertFalse(contract["rawListenerIsolated"])
        self.assertTrue(contract["listenerIsolationBlocked"])
        reason = contract["reason"].lower()
        self.assertIn("memory", reason)
        self.assertIn("hotfix", reason)
        self.assertIn("unauthenticated raw listener", reason)
        self.assertIn("fixed release alone", reason)
        self.assertNotIn("signature verification", reason)

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
            (runtime, "0" * 64, "no longer matches the pinned official"),
            (symlink, sha256, "must not be a symbolic link"),
            (wrong_path, sha256, "Only the launcher-managed Uzu 0.5.22"),
        )
        for requested, expected_hash, expected_reason in cases:
            with self.subTest(reason=expected_reason):
                with (
                    mock.patch.multiple(
                        launcher,
                        UZU_RUNTIME_PATH=runtime,
                        UZU_RUNTIME_RELEASE_BINARY_SHA256=expected_hash,
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
        self.assertEqual(capability["contextWindows"], [16_384, 32_768])
        self.assertEqual(capability["contextMaximum"], 32_768)
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
            "binary": {"sha256": "runtime-sha256"},
            "rawListenerAuthenticated": True,
            "rawListenerIsolated": False,
            "listenerIsolationBlocked": False,
        }
        cache_contract = {
            "ready": True,
            "reason": "complete",
            "path": str(self.model_path),
            "fingerprint": fingerprint,
        }
        capability = {
            "runnable": True,
            "benchmarkModelFingerprint": fingerprint,
            "modelRegistryId": launcher.UZU_MODEL_REGISTRY_ID,
            "modelCommit": launcher.UZU_MODEL_COMMIT,
            "modelToolchainVersion": launcher.UZU_MODEL_TOOLCHAIN_VERSION,
            "agentReasoning": ["auto"],
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
                plan = launcher.LaunchPlan(
                    f"uzu-{reasoning}", "uzu", "chat", copy.deepcopy(model),
                    str(self.root), 16_384, 1_024, reasoning, 18_123,
                    "custom", {}, runtime_binary=str(runtime),
                    chat={"systemPrompt": "", "sampling": "model"},
                )
                with (
                    mock.patch.object(
                        launcher, "uzu_runtime_contract",
                        return_value=runtime_contract,
                    ),
                    mock.patch.object(
                        launcher, "_uzu_model_cache_contract",
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
                        "--prefix-cache",
                    ]
                    self.assertEqual(plan.engine_argv, expected_argv)
                    self.assertEqual(plan.engine_env, {})
                    self.assertNotIn("--reasoning-effort", plan.engine_argv)
                    self.assertEqual(
                        launcher.UZU_NETWORK_SANDBOX_PROFILE,
                        "(version 1)(allow default)(deny network-outbound)",
                    )
                    self.assertEqual(
                        identities, ("runtime-sha256", fingerprint),
                    )
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
        with self.assertRaisesRegex(ValueError, "exceeds the selected Uzu context"):
            session_proxy.transform_chat_request(
                json.dumps(oversized).encode("utf-8"), base,
            )

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
            "output": 1_024,
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
        for context in (16_384, 32_768):
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
                self.assertEqual(contract["configuredOutputLimit"], 1_024)
                self.assertEqual(
                    contract["measuredRequestMaxTokens"],
                    launcher.ROUTE_QUALIFICATION_MAX_TOKENS,
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
                self.assertEqual(contract["runtimeBinarySha256"], "b" * 64)
                self.assertEqual(contract["fixedAcceleration"], "DFlash + Weaver")
                self.assertEqual(contract["kvStateDataType"], "BF16")
                self.assertTrue(contract["prefixCache"])
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

    def test_uzu_output_contract_receipts_keep_separate_identities(self) -> None:
        model, _payload, _binary = self.qualification_fixture()
        spec = launcher.route_qualification_spec(model, "uzu", 16_384)
        self.assertIsNotNone(spec)
        assert spec is not None
        first = self.qualification_record(spec)
        second = copy.deepcopy(first)
        second.update({
            "id": "uzu-qualification-record-2048",
            "createdAt": "2026-09-03T12:01:00Z",
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
                    "output": 1_024,
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

    def test_uzu_session_and_route_check_require_a_matching_qualification(self) -> None:
        model, payload, binary = self.qualification_fixture()
        for purpose in ("session", "route-check"):
            with self.subTest(purpose=purpose):
                with mock.patch.dict(
                    launcher.BINARIES, {"mirai": str(binary)}, clear=True,
                ), mock.patch.object(
                    launcher, "free_port", side_effect=[18_080, 18_081],
                ), mock.patch.object(
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

        with mock.patch.dict(
            launcher.BINARIES, {"mirai": str(binary)}, clear=True,
        ), mock.patch.object(
            launcher, "free_port", side_effect=[18_080, 18_081],
        ), mock.patch.object(
            launcher, "verified_route_qualification", return_value={"id": "qualified"},
        ) as verified, mock.patch.object(
            launcher, "build_engine_plan",
        ), mock.patch.object(launcher, "build_client_plan"):
            plan = launcher.normalized_request(payload, [model], purpose="session")
        self.assertEqual(plan.backend, "uzu")
        self.assertEqual(plan.context, 16_384)
        verified.assert_called_once()
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
            launcher.ROUTE_QUALIFICATION_MAX_TOKENS,
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
            launcher.ROUTE_QUALIFICATION_MAX_TOKENS,
        )
        self.assertNotIn("max_tokens", body)
        self.assertNotIn("stream_options", body)
        self.assertEqual(body["reasoning_effort"], "default")
        for key in (
            "temperature", "top_p", "top_k", "presence_penalty",
            "frequency_penalty", "seed",
        ):
            self.assertNotIn(key, body)

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
                return {
                    "memoryAvailable": True,
                    "totalBytes": 48 * 1024**3,
                    "freePercent": free_percentages[index],
                }

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
            return_value={
                "memoryAvailable": False,
                "totalBytes": 48 * 1024**3,
                "freePercent": None,
            },
        ) as pressure_reader, mock.patch.object(
            launcher.time, "monotonic", side_effect=monotonic,
        ), mock.patch.object(manager, "_stop_owned") as stop_owned:
            manager._guard_uzu_memory(plan, process, cancel_event)
        self.assertTrue(stopped["value"])
        stop_owned.assert_called_once_with(plan)
        self.assertGreaterEqual(pressure_reader.call_count, 3)
        self.assertIn("pressure", manager.state["message"].lower())


if __name__ == "__main__":
    unittest.main()
