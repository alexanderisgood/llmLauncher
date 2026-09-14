"""Cache capacity follows the engine that allocates it, not its fallback knob."""
import copy
import unittest
from unittest import mock

import launcher


class KvCachePolicyTests(unittest.TestCase):
    def setUp(self):
        self.model = {
            "id": "qwen", "name": "Qwen 27B", "size": 22 * 1024**3,
            "memoryGeometry": {
                "ready": True, "fullAttentionLayers": 16,
                "kvHeads": 4, "headDimension": 256,
            },
            "backends": {"omlx": {"dflashDraftSize": 1024**3}},
        }
        self.request = {
            "modelId": "qwen", "backend": "omlx", "client": "pi",
            "context": 131_072, "output": 16_384, "reasoning": "xhigh",
            "options": {"acceleration": "dflash", "kv": "q6"},
        }
        self.resource = {"totalMemoryBytes": 48 * 1024**3, "memoryAvailable": True}

    def dflash_capability(self):
        return {
            "dflash": True, "dflashVersion": "2",
            "dflashPairFingerprint": "pair",
            "dflashRuntimeVersion": "omlx 0.6.4",
            "benchmarkModelFingerprint": "model",
            "runtimeVersion": "omlx 0.6.4",
            "dflashBlockSize": 5, "dflashMaxBlockSize": 8,
            "dflashDraftPath": "/test/draft",
            "depth": 5, "depthMax": 8,
            "kv": True, "mtp": False,
            "preferredAcceleration": "dflash",
            "preferredAccelerationSource": "local-benchmark",
            "dflashPreferred": True, "dflashBenchmarkVerified": True,
            "fallbackAcceleration": "off",
        }

    def evidence(self, kv):
        return {
            "context": 8_192, "output": 1_024, "client": "chat",
            "reasoning": "auto", "kv": kv, "samplingFingerprint": "sample",
        }

    def benchmark(self, kv, winner="dflash2"):
        return {
            "id": f"record-{kv}", "createdAt": "2026-09-12T00:00:00+00:00",
            "scope": "local", "backend": "omlx", "modelFingerprint": "model",
            "runtimeVersion": "omlx 0.6.4", "hardwareFingerprint": "mac",
            "winner": winner, "qualityPassed": True, "baselinePassed": True,
            "winnerSpeedup": 2.0, "worstCaseSpeedup": 2.0,
            "endToEndSpeedup": 2.0, "contextMin": 8_192, "contextMax": 8_192,
            "outputMin": 1_024, "outputMax": 1_024, "client": "chat",
            "reasoning": "auto", "targetKV": kv,
            "samplingFingerprint": "sample", "pairFingerprint": "pair",
            "settings": {
                "blockSize": 5, "draftQuant": "q4", "verifyMode": "dflash",
            },
            "comparedModes": ["ar", "dflash2"],
            "modes": {"ar": {}, "dflash2": {}},
            "probeContract": launcher.BENCHMARK_PROBE_CONTRACT,
            "workloadKind": "throughput",
        }

    def test_dflash_capacity_matches_selected_native_quantization(self):
        for verifier in ("adaptive", "dflash"):
            for kv, gib in (("off", 8), ("q8", 4.25), ("q6", 3.25), ("q4", 2.25)):
                request = copy.deepcopy(self.request)
                request["options"].update(kv=kv, dflashVerify=verifier)
                original = copy.deepcopy(request)
                estimate = launcher.launch_memory_estimate(request, self.model, self.resource)
                self.assertEqual(estimate["kvPrecision"], kv)
                self.assertEqual(estimate["kvCacheBytes"], gib * 1024**3)
                self.assertEqual(estimate["companionBytes"], 1024**3)
                self.assertEqual(request, original)

    def test_ordinary_engines_keep_selected_precision(self):
        for backend in ("omlx", "mtplx"):
            for acceleration in ("auto", "off", "mtp"):
                for kv, gib in (("off", 8), ("q8", 4.25), ("q6", 3.25), ("q4", 2.25)):
                    if backend == "mtplx" and kv == "q6":
                        continue
                    with self.subTest(backend=backend, acceleration=acceleration, kv=kv):
                        request = {**self.request, "backend": backend, "options": {
                            "acceleration": acceleration, "kv": kv,
                        }}
                        estimate = launcher.launch_memory_estimate(request, self.model, self.resource)
                        self.assertEqual(estimate["kvPrecision"], kv)
                        self.assertEqual(estimate["kvCacheBytes"], gib * 1024**3)
                        self.assertEqual(estimate["companionBytes"], 0)

    def test_ddtree_admission_stays_conservative(self):
        # DDTree must never be admitted on the basis of quantized savings.
        request = copy.deepcopy(self.request)
        request["options"]["dflashVerify"] = "ddtree"
        quantized_request = {**request, "options": {"acceleration": "off", "kv": "q6"}}
        quantized = launcher.launch_memory_estimate(quantized_request, self.model, self.resource)
        headroom = quantized["requiredHeadroomBytes"] + 1024**3
        with mock.patch.object(launcher, "validated_launch_profile_request", return_value=request):
            admission = launcher.session_memory_admission(
                request, [self.model], {**self.resource, "headroomBytes": headroom},
                {"phase": "idle"}, {"active": False},
            )
        self.assertEqual(admission["decision"], "review")
        self.assertTrue(admission["requiresAcknowledgement"])
        self.assertEqual(admission["estimate"]["kvCacheBytes"], 8 * 1024**3)
        self.assertEqual(admission["request"]["options"]["kv"], "q6")

    def test_dflash_evidence_uses_effective_primary_precision(self):
        capability = self.dflash_capability()
        for kv, accepted in (("off", True), ("q8", False), ("q6", False), ("q4", False)):
            with self.subTest(kv=kv):
                self.assertEqual(
                    launcher.dflash2_benchmark_verified(
                        capability, self.evidence(kv), self.benchmark(kv),
                    ),
                    accepted,
                )

    def test_local_dflash_records_with_quantized_target_are_history_only(self):
        capability = self.dflash_capability()
        with mock.patch.object(launcher, "hardware_fingerprint", return_value="mac"):
            for kv, accepted in (("off", True), ("q8", False), ("q6", False), ("q4", False)):
                with self.subTest(kv=kv):
                    self.assertEqual(
                        launcher._local_benchmark_record_verified(
                            capability, self.benchmark(kv), self.evidence(kv),
                        ),
                        accepted,
                    )

    def test_clean_quantized_ar_evidence_remains_usable_without_dflash(self):
        capability = self.dflash_capability()
        record = self.benchmark("q6", winner="ar")
        record["comparedModes"] = ["ar"]
        record["modes"] = {"ar": {}}
        with mock.patch.object(launcher, "hardware_fingerprint", return_value="mac"):
            self.assertTrue(
                launcher._local_benchmark_record_verified(
                    capability, record, self.evidence("q6"),
                )
            )

    def test_automatic_dflash_selection_requires_full_precision_kv(self):
        capability = self.dflash_capability()
        quantized_record = self.benchmark("q6")
        capability.update({
            "localBenchmark": quantized_record,
            "localBenchmarks": [quantized_record],
        })
        result = launcher.fastest_safe_options(
            "omlx", capability,
            {"acceleration": "auto", "kv": "q6"},
            self.evidence("q6"),
        )
        self.assertNotEqual(result["options"]["acceleration"], "dflash")

    def test_explicit_dflash_quantized_fallback_is_preserved_for_review(self):
        capability = self.dflash_capability()
        current = {
            "acceleration": "dflash", "kv": "q6", "depth": 5,
            "dflashVerify": "dflash", "dflashDraftQuant": "q4",
            "burst": "balanced", "anePrefill": "off", "memoryGuard": "balanced",
        }
        result = launcher.fastest_safe_options("omlx", capability, current)
        self.assertEqual(result["options"], current)
        self.assertEqual(result["evidenceTier"], "manual-route")
        self.assertEqual(result["changedKeys"], [])
        self.assertEqual(result["appliedKeys"], [])

    def test_full_precision_dflash_evidence_remains_usable(self):
        capability = self.dflash_capability()
        record = self.benchmark("off")
        capability.update({"localBenchmark": record, "localBenchmarks": [record]})
        with mock.patch.object(launcher, "hardware_fingerprint", return_value="mac"):
            result = launcher.fastest_safe_options(
                "omlx", capability,
                {"acceleration": "auto", "kv": "off"},
                self.evidence("off"),
            )
        self.assertEqual(result["options"]["acceleration"], "dflash")
        self.assertEqual(result["evidenceTier"], "local-benchmark")

    def test_explicit_mixed_route_remains_valid_profile_input(self):
        capability = self.dflash_capability()
        model = {"backends": {"omlx": capability}}
        options = launcher.validated_profile_options(
            "omlx", model, capability,
            {"acceleration": "dflash", "kv": "q6", "depth": 5},
        )
        self.assertEqual(options["acceleration"], "dflash")
        self.assertEqual(options["kv"], "q6")


if __name__ == "__main__":
    unittest.main()
