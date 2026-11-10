"""Exact pre-refactor verdicts and uncached live proof for saved benchmarks."""
import copy
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import benchmark_evidence
import launcher


FIXTURE = Path(__file__).with_name("fixtures") / "benchmark-evidence-v4.json"


class BenchmarkEvidenceDomainTests(unittest.TestCase):
    @staticmethod
    def unload_receipt():
        return {
            "clean": True, "processExited": True, "processGroupExited": True,
            "managerIdle": True, "portsClosed": True,
            "checkedPorts": [54320, 54321], "closedPorts": [54320, 54321],
        }

    @staticmethod
    def measured_route(backend="omlx"):
        """Generated, otherwise valid AR/MTP evidence; no runtime is started."""
        capability = {
            "mtp": True, "dflash": False, "depth": 3, "depthMax": 3,
            "benchmarkModelFingerprint": "generated-model",
            "runtimeVersion": "generated-runtime",
            "preferredAccelerationSource": "local-benchmark",
            "preferredAcceleration": "mtp", "fallbackAcceleration": "off",
        }
        evidence = {
            "context": 8192, "output": 1024, "client": "chat",
            "reasoning": "medium", "kv": "off",
            "samplingFingerprint": "generated-sampling", "engineSettings": {},
        }
        record = {
            "id": "generated-unload-route", "suite": "quick",
            "createdAt": "2026-10-06T00:00:00+00:00",
            "backend": backend, "scope": "local",
            "modelFingerprint": "generated-model", "runtimeVersion": "generated-runtime",
            "hardwareFingerprint": "generated-mac", "baselinePassed": True,
            "probeContract": copy.deepcopy(launcher.BENCHMARK_PROBE_CONTRACT),
            "contextMin": 8192, "contextMax": 8192,
            "outputMin": 1024, "outputMax": 1024,
            "client": "chat", "reasoning": "medium", "targetKV": "off",
            "samplingFingerprint": "generated-sampling",
            "comparedModes": ["ar", "mtp"], "winner": "mtp", "qualityPassed": True,
            "qualityFingerprint": "a" * 64, "qualityCompletionTokens": 64,
            "winnerSpeedup": 1.2, "worstCaseSpeedup": 1.2,
            "settings": {"depth": 3}, "modeSettings": {"ar": {}, "mtp": {"depth": 3}},
            "comparisonContractVersion": launcher.BENCHMARK_COMPARISON_CONTRACT_VERSION,
            "engineSettings": {}, "modes": {},
        }
        for mode, speed in (("ar", 100.0), ("mtp", 120.0)):
            record["modes"][mode] = {
                "qualityHash": "a" * 64, "qualityCompletionTokens": 64,
                "medianDecodeTokensPerSecond": speed,
                "medianEndToEndTokensPerSecond": 64.0,
                "samples": [{
                    "promptTokens": 512, "targetPromptTokens": 512,
                    "completionTokens": 128, "repetition": 1,
                    "ttftSeconds": 0.1, "totalSeconds": 2.0,
                    "decodeTokensPerSecond": speed, "endToEndTokensPerSecond": 64.0,
                }],
            }
        if backend == "lmstudio":
            record["settings"] = launcher.lmstudio_mtp_controls({"depth": 3}, capability)
            record["modeSettings"]["mtp"] = copy.deepcopy(record["settings"])
        return capability, record, evidence

    def assert_cleanup_consumers(self, capability, record, evidence, *, eligible):
        original = copy.deepcopy(record)
        backend = record["backend"]
        capability = dict(capability, localBenchmark=record, localBenchmarks=[record])
        with mock.patch.object(launcher, "hardware_fingerprint", return_value="generated-mac"), \
                mock.patch.object(launcher, "route_qualification_record_is_fresh", return_value=True):
            self.assertEqual(
                launcher._local_benchmark_record_verified(capability, record, evidence), eligible,
            )
            selected = launcher.verified_local_benchmark(capability, evidence)
            self.assertEqual(selected is not None, eligible)
            self.assertEqual(launcher.matching_benchmark_records(
                [record], backend, "generated-model", "generated-runtime", capability,
            ), [record] if eligible else [])
            self.assertEqual(launcher.route_performance_evidence(
                {}, backend, capability, evidence,
            )["automaticEligible"], eligible)
            fastest = launcher.fastest_safe_options(
                backend, capability, {"acceleration": "off", "depth": 1, "kv": "off"}, evidence,
            )
            self.assertEqual(fastest["options"]["acceleration"], "mtp" if eligible else "off")
            self.assertEqual(fastest["evidenceTier"],
                "local-benchmark" if eligible else "safe-runtime-recommendation")
            binding = {"recordId": record["id"], "suite": "quick"}
            if eligible:
                self.assertEqual(launcher.optimizer_evidence_bound_route_record(
                    capability, backend, binding, evidence,
                ), record)
            else:
                with self.assertRaisesRegex(ValueError, "no longer matches"):
                    launcher.optimizer_evidence_bound_route_record(capability, backend, binding, evidence)
            entries = launcher.verified_cross_engine_entries(
                {"backends": {backend: capability}}, [backend], evidence,
            )
            self.assertEqual(len(entries), int(eligible))
        # Eligibility does not mutate history or erase the stored measurement.
        self.assertEqual(record, original)
        measured = launcher.cross_engine_benchmark_measurement(record)
        self.assertIsNotNone(measured)
        self.assertEqual(measured["decodeTokensPerSecond"], 120.0)
        self.assertEqual(measured["score"], 64.0)

    def test_absent_legacy_and_valid_unload_receipts_remain_eligible(self):
        for present in (False, True):
            with self.subTest(present=present):
                capability, record, evidence = self.measured_route()
                if present:
                    for mode in record["modes"].values():
                        mode["unloadEvidence"] = self.unload_receipt()
                self.assertIsNone(launcher.benchmark_integrity_issue(record))
                self.assert_cleanup_consumers(capability, record, evidence, eligible=True)

    def test_present_failed_or_malformed_receipts_block_every_automatic_consumer(self):
        failed = {key: False for key in (
            "clean", "processExited", "processGroupExited", "managerIdle", "portsClosed",
        )}
        failed.update(checkedPorts=[54320], closedPorts=[])
        for label, receipt in (
            ("failed", failed), ("null", None), ("scalar", True), ("list", []),
            ("contradictory", dict(self.unload_receipt(), portsClosed=False)),
        ):
            # AR lost, but its failed unload still invalidates the comparison.
            for mode in ("ar", "mtp"):
                with self.subTest(receipt=label, mode=mode):
                    capability, record, evidence = self.measured_route()
                    record["modes"][mode]["unloadEvidence"] = copy.deepcopy(receipt)
                    self.assertIn("unload", launcher.benchmark_integrity_issue(record))
                    self.assert_cleanup_consumers(capability, record, evidence, eligible=False)

    def test_receipts_require_exact_flags_and_coherent_bounded_port_proof(self):
        variants = []
        for flag in ("clean", "processExited", "processGroupExited", "managerIdle", "portsClosed"):
            for value in (False, 1, "true", None):
                variants.append((f"{flag}-{value}", dict(self.unload_receipt(), **{flag: value})))
            missing = self.unload_receipt()
            del missing[flag]
            variants.append((f"missing-{flag}", missing))
        for label, checked, closed in (
            ("empty", [], []), ("missing", None, None),
            ("bool", [True], [True]), ("zero", [0], [0]),
            ("too-high", [65536], [65536]), ("string", ["54320"], ["54320"]),
            ("duplicate", [54320, 54320], [54320, 54320]),
            ("unsorted", [54321, 54320], [54321, 54320]),
            ("mismatch", [54320, 54321], [54320]),
            ("different", [54320], [54321]),
            ("closed-bool", [1], [True]),
            ("not-list", (54320,), (54320,)),
            ("count-overflow", [1] * 65536, [1] * 65536),
        ):
            variants.append((label, dict(self.unload_receipt(), checkedPorts=checked, closedPorts=closed)))
        for label, receipt in variants:
            with self.subTest(receipt=label):
                _, record, _ = self.measured_route()
                record["modes"]["ar"]["unloadEvidence"] = receipt
                self.assertIn("unload", launcher.benchmark_integrity_issue(record))
        _, record, _ = self.measured_route()
        record["modes"]["ar"]["unloadEvidence"] = dict(
            self.unload_receipt(), checkedPorts=[1, 65535], closedPorts=[1, 65535],
        )
        self.assertIsNone(launcher.benchmark_integrity_issue(record))

    def test_cleanup_integrity_has_no_backend_name_bypass(self):
        for backend in launcher.ENGINE_ADAPTERS:
            with self.subTest(backend=backend):
                _, record, _ = self.measured_route()
                record["backend"] = backend
                record["modes"]["ar"]["unloadEvidence"] = None
                self.assertIn("unload", launcher.benchmark_integrity_issue(record))

    def test_invalid_cleanup_history_and_readable_tps_are_preserved(self):
        capability, record, evidence = self.measured_route()
        record["modes"]["ar"]["unloadEvidence"] = dict(self.unload_receipt(), clean=False)
        with tempfile.TemporaryDirectory(prefix="benchmark-unload-history-") as folder, \
                mock.patch.object(launcher, "STATE_DIR", Path(folder)):
            launcher.save_benchmark_record(record)
            before = launcher.benchmark_store_path().read_bytes()
            self.assertEqual(launcher.load_benchmark_records(), [record])
            self.assert_cleanup_consumers(capability, record, evidence, eligible=False)
            self.assertEqual(launcher.load_benchmark_records(), [record])
            self.assertEqual(launcher.benchmark_store_path().read_bytes(), before)

    @staticmethod
    def shared_model_receipt():
        return {
            "kind": "shared-lmstudio-model-v1", "clean": True,
            "managerIdle": True, "modelUnloaded": True,
            "sharedServerRetained": True, "ownedPortsClosed": True,
            "modelIdentifier": "llm-launcher-012abcde", "sharedServerPort": 54320,
            "checkedPorts": [54321], "closedPorts": [54321],
        }

    def test_shared_lmstudio_model_receipt_proves_distinct_cleanup_contract(self):
        for ports in ([], [54321]):
            with self.subTest(ownedPorts=ports):
                receipt = dict(self.shared_model_receipt(), checkedPorts=ports, closedPorts=list(ports))
                self.assertIsNone(benchmark_evidence.unload_receipt_issue(receipt, "lmstudio"))
                capability, record, evidence = self.measured_route("lmstudio")
                for mode in record["modes"].values():
                    mode["unloadEvidence"] = copy.deepcopy(receipt)
                self.assertIsNone(launcher.benchmark_integrity_issue(record))
                self.assert_cleanup_consumers(capability, record, evidence, eligible=True)
        # Existing honest owned-process receipts need no new discriminator.
        capability, record, evidence = self.measured_route("lmstudio")
        record["modes"]["ar"]["unloadEvidence"] = self.unload_receipt()
        self.assert_cleanup_consumers(capability, record, evidence, eligible=True)

    def test_shared_model_receipt_is_engine_bound_and_rejects_failed_or_mixed_proof(self):
        for backend in launcher.ENGINE_ADAPTERS:
            if backend == "lmstudio":
                continue
            with self.subTest(backend=backend):
                self.assertIsNotNone(benchmark_evidence.unload_receipt_issue(
                    self.shared_model_receipt(), backend,
                ))
                _, record, _ = self.measured_route()
                record["backend"] = backend
                record["modes"]["ar"]["unloadEvidence"] = self.shared_model_receipt()
                self.assertIn("unload", launcher.benchmark_integrity_issue(record))
        variants = []
        for flag in ("clean", "managerIdle", "modelUnloaded", "sharedServerRetained", "ownedPortsClosed"):
            for value in (False, 1, None):
                variants.append((flag, dict(self.shared_model_receipt(), **{flag: value})))
            missing = self.shared_model_receipt()
            del missing[flag]
            variants.append((f"missing-{flag}", missing))
        for identifier in (None, "foreign-model", "llm-launcher-", "llm-launcher-012ABCDE",
                           "llm-launcher-012abcde/other", "llm-launcher-012abcde\n"):
            variants.append(("identifier", dict(self.shared_model_receipt(), modelIdentifier=identifier)))
        for port in (None, True, 0, 65536, "54320"):
            variants.append(("server-port", dict(self.shared_model_receipt(), sharedServerPort=port)))
        variants.extend((
            ("retained-server-closed", dict(self.shared_model_receipt(), checkedPorts=[54320], closedPorts=[54320])),
            ("unclosed-owned-port", dict(self.shared_model_receipt(), closedPorts=[])),
            ("missing-owned-list", dict(self.shared_model_receipt(), checkedPorts=None, closedPorts=None)),
            ("bool-owned-port", dict(self.shared_model_receipt(), checkedPorts=[True], closedPorts=[True])),
            ("unknown-contract", dict(self.shared_model_receipt(), kind="shared-lmstudio-model-v2")),
            ("mixed-process", dict(self.shared_model_receipt(), processExited=True)),
            ("mixed-group", dict(self.shared_model_receipt(), processGroupExited=False)),
            ("mixed-port", dict(self.shared_model_receipt(), portsClosed=True)),
        ))
        for label, receipt in variants:
            with self.subTest(receipt=label):
                self.assertIsNotNone(benchmark_evidence.unload_receipt_issue(receipt, "lmstudio"))
                capability, record, evidence = self.measured_route("lmstudio")
                record["modes"]["ar"]["unloadEvidence"] = receipt
                self.assertIn("unload", launcher.benchmark_integrity_issue(record))
                self.assert_cleanup_consumers(capability, record, evidence, eligible=False)

    def test_frozen_pre_refactor_outputs_match_domain_and_public_facades(self):
        fixture = json.loads(FIXTURE.read_text())
        self.assertEqual(len(fixture["preExtractionFunctionsSha256"]), 64)
        self.assertEqual(len(fixture["cases"]), 59)
        with mock.patch.object(launcher, "hardware_fingerprint", return_value="generated-mac"), \
                mock.patch.object(launcher, "route_qualification_record_is_fresh", return_value=True):
            verifier = launcher._benchmark_evidence_verifier()
            for case in fixture["cases"]:
                for owner in (verifier, launcher):
                    with self.subTest(method=case["method"], owner=type(owner).__name__, args=case["args"][:1]):
                        result = getattr(owner, case["method"])(*copy.deepcopy(case["args"]), **copy.deepcopy(case["kwargs"]))
                        # Serialized snapshots intentionally normalize tuple/list
                        # envelopes; their field values and ordering stay exact.
                        self.assertEqual(json.loads(json.dumps(result, allow_nan=False)), case["expected"])

    def test_policy_detaches_and_freezes_nested_caller_tables(self):
        policy = launcher._benchmark_evidence_verifier().policy
        source = {"version":1, "nested":[{"verified":True}]}
        frozen = replace(policy, benchmark_probe_contract=source)
        source["nested"][0]["verified"] = False
        self.assertTrue(frozen.benchmark_probe_contract["nested"][0]["verified"])
        with self.assertRaises(TypeError):
            frozen.benchmark_probe_contract["nested"][0]["verified"] = False
        with self.assertRaises(TypeError):
            frozen.benchmark_probe_contract["nested"].append({})
        with self.assertRaises(FrozenInstanceError):
            frozen.benchmark_minimum_speedup = 0

    def test_invalid_policy_cannot_weaken_evidence_thresholds(self):
        policy = launcher._benchmark_evidence_verifier().policy
        for threshold in (True, float("nan"), float("inf"), 0.5):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                replace(policy, benchmark_minimum_speedup=threshold)
        with self.assertRaises(ValueError):
            replace(policy, benchmark_comparison_contract_version=True)

    def test_exact_hardware_matching_rechecks_the_live_callback(self):
        base = launcher._benchmark_evidence_verifier()
        hardware = mock.Mock(side_effect=["generated-mac", "different-mac"])
        verifier = benchmark_evidence.EvidenceVerifier(base.policy,
            replace(base.services, hardware_fingerprint=hardware))
        record = {"backend":"omlx", "scope":"local", "modelFingerprint":"fixture",
            "runtimeVersion":"fixture-runtime", "hardwareFingerprint":"generated-mac",
            "probeContract":copy.deepcopy(launcher.BENCHMARK_PROBE_CONTRACT)}
        self.assertEqual(verifier.matching_benchmark_records([record], "omlx", "fixture", "fixture-runtime", {}), [record])
        self.assertEqual(verifier.matching_benchmark_records([record], "omlx", "fixture", "fixture-runtime", {}), [])
        self.assertEqual(hardware.call_count, 2)

    def test_live_dflash_pair_revision_is_not_cached_as_a_positive_verdict(self):
        base = launcher._benchmark_evidence_verifier()
        version = mock.Mock(side_effect=["runtime-a", "runtime-b"])
        services = replace(base.services, runtime_version=version,
            omlx_supports_dflash2=lambda _version:True,
            read_json=lambda _path:{}, weight_completeness=lambda *_args:(True, "complete", 1),
            dflash2_draft_complete=lambda *_args:True,
            matching_dflash2_draft=lambda *_args:{"paired":True},
            dflash2_pair_fingerprint=lambda *_args:"a"*64,
            dflash2_draft_shape=lambda *_args:{"block_size":8})
        verifier = benchmark_evidence.EvidenceVerifier(base.policy, services)
        with tempfile.TemporaryDirectory(prefix="benchmark-pair-fixture-") as folder:
            target, draft = Path(folder)/"target", Path(folder)/"draft"
            target.mkdir(); draft.mkdir()
            capability = {"dflash":True, "dflashVersion":"2", "dflashRuntimeVersion":"runtime-a",
                "dflashDraftPath":str(draft), "dflashPairFingerprint":"a"*64,
                "dflashBlockSize":4, "dflashMaxBlockSize":8}
            self.assertTrue(verifier.dflash2_capability_valid({"path":str(target)}, capability))
            self.assertFalse(verifier.dflash2_capability_valid({"path":str(target)}, capability))
        self.assertEqual(version.call_args_list, [mock.call("omlx"), mock.call("omlx")])

    def test_record_projection_and_matching_do_not_alias_caller_data(self):
        verifier = launcher._benchmark_evidence_verifier()
        records = [{"id":"first", "createdAt":"2026-10-06", "engineSettings":{"depth":2}}]
        result = verifier.latest_benchmark_records_by_identity(records)
        result[0]["engineSettings"]["depth"] = 99
        self.assertEqual(records[0]["engineSettings"]["depth"], 2)
        self.assertNotIn("privateUnlisted", verifier.benchmark_engine_settings("mtplx", {"profile":"turbo", "privateUnlisted":"fixture"}))


if __name__ == "__main__":
    unittest.main()
