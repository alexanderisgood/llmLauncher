import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import launcher


class BenchmarkEvidencePersistenceTests(unittest.TestCase):
    MACHINE = "goal-bound-benchmark-mac"
    FINGERPRINT = "goal-bound-model-fingerprint"
    SUITE = "agentic"

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(
            prefix="llm-launcher-evidence-persistence-",
        )
        self.state_patch = mock.patch.object(
            launcher, "STATE_DIR", Path(self.temp.name) / "state",
        )
        self.state_patch.start()
        self.model = {
            "backends": {
                "omlx": {
                    "runtimeVersion": "omlx goal-bound test runtime",
                    "benchmarkModelFingerprint": self.FINGERPRINT,
                    "runnable": True,
                    "mtp": False,
                    "dflash": False,
                    "kv": True,
                },
                "mtplx": {
                    "runtimeVersion": "mtplx goal-bound test runtime",
                    "benchmarkModelFingerprint": self.FINGERPRINT,
                    "runnable": True,
                    "mtp": False,
                    "kv": True,
                    "profile": "turbo",
                    "depth": 3,
                    "depthMax": 3,
                },
            },
        }
        self.options = {
            "acceleration": "off",
            "depth": 3,
            "kv": "off",
            "burst": "balanced",
            "anePrefill": "off",
            "memoryGuard": "balanced",
            "profile": "turbo",
            "mtplxOperatorRoute": launcher.MTPLX_LONG_CONTEXT_DEFAULT_ROUTE,
            "fan": "default",
        }

    def tearDown(self) -> None:
        self.state_patch.stop()
        self.temp.cleanup()

    def record(
        self, backend: str, *, preference: str, shootout: str,
        record_id: str, created_at: str,
    ) -> dict:
        capability = self.model["backends"][backend]
        options = launcher.validated_cross_engine_profile_options(
            backend, self.model, capability, self.options,
        )
        return {
            "id": record_id,
            "createdAt": created_at,
            "scope": "local",
            "backend": backend,
            "probeContract": copy.deepcopy(launcher.BENCHMARK_PROBE_CONTRACT),
            "modelFingerprint": self.FINGERPRINT,
            "runtimeVersion": capability["runtimeVersion"],
            "hardwareFingerprint": self.MACHINE,
            "suite": self.SUITE,
            "client": "pi",
            "reasoning": "auto",
            "targetKV": "off",
            "samplingFingerprint": "goal-bound-sampling",
            "contextMin": 32_768,
            "contextMax": 32_768,
            "outputMin": 4_096,
            "outputMax": 4_096,
            "scenarioContract": ["cold", "warmPrefix", "toolIngest", "steadyTurn"],
            "engineSettings": launcher.benchmark_engine_settings(backend, options),
            "winner": "ar",
            "comparedModes": ["ar"],
            "shootoutId": shootout,
            "selectionPreference": preference,
        }

    def reload_benchmark_capabilities(self) -> None:
        persisted = launcher.load_benchmark_records()
        for backend, capability in self.model["backends"].items():
            history = launcher.matching_benchmark_records(
                persisted,
                backend,
                self.FINGERPRINT,
                capability["runtimeVersion"],
                capability,
                self.MACHINE,
            )
            scanned = launcher.latest_benchmark_records_by_identity(history)
            capability["localBenchmarks"] = scanned
            capability["localBenchmark"] = scanned[-1] if scanned else None

    def test_record_identity_keeps_selection_goals_separate(self) -> None:
        throughput = self.record(
            "omlx",
            preference="throughput",
            shootout="throughput-shootout",
            record_id="throughput-omlx",
            created_at="2026-08-20T12:00:00Z",
        )
        fastest = copy.deepcopy(throughput)
        fastest.update({
            "id": "fastest-omlx",
            "createdAt": "2026-08-21T12:00:00Z",
            "shootoutId": "fastest-shootout",
            "selectionPreference": "fastest",
        })

        self.assertNotEqual(
            launcher.benchmark_record_identity(throughput),
            launcher.benchmark_record_identity(fastest),
        )
        self.assertEqual(
            [record["id"] for record in launcher.latest_benchmark_records_by_identity(
                [throughput, fastest],
            )],
            ["throughput-omlx", "fastest-omlx"],
        )

    def test_historical_sampling_receipts_stay_saved_but_are_not_reloaded_as_candidates(self):
        legacy = self.record("omlx", preference="throughput", shootout="old",
            record_id="legacy", created_at="2026-08-20T12:00:00Z")
        legacy.pop("probeContract")
        launcher.save_benchmark_records([legacy])
        self.reload_benchmark_capabilities()
        self.assertEqual(launcher.load_benchmark_records(), [legacy])
        self.assertEqual(self.model["backends"]["omlx"]["localBenchmarks"], [])
        fresh = copy.deepcopy(legacy)
        fresh.update(id="corrected", shootoutId="new", createdAt="2026-08-21T12:00:00Z",
            probeContract=copy.deepcopy(launcher.BENCHMARK_PROBE_CONTRACT))
        launcher.save_benchmark_records([fresh])
        self.reload_benchmark_capabilities()
        self.assertEqual(len(launcher.load_benchmark_records()), 2)
        self.assertEqual(self.model["backends"]["omlx"]["localBenchmarks"], [fresh])

    def test_older_binding_resolves_after_later_different_goal_reload(self) -> None:
        older = [
            self.record(
                backend,
                preference="throughput",
                shootout="throughput-shootout",
                record_id=f"throughput-{backend}",
                created_at="2026-08-20T12:00:00Z",
            )
            for backend in ("omlx", "mtplx")
        ]
        newer = [
            self.record(
                backend,
                preference="fastest",
                shootout="fastest-shootout",
                record_id=f"fastest-{backend}",
                created_at="2026-08-21T12:00:00Z",
            )
            for backend in ("omlx", "mtplx")
        ]
        launcher.save_benchmark_records(older)
        launcher.save_benchmark_records(newer)

        self.reload_benchmark_capabilities()

        for capability in self.model["backends"].values():
            self.assertEqual(
                [record["selectionPreference"] for record in capability["localBenchmarks"]],
                ["throughput", "fastest"],
            )
        binding = launcher.validated_optimizer_evidence_binding({
            "evidenceBinding": {
                "scope": "engine",
                "suite": self.SUITE,
                "preference": "throughput",
                "shootoutId": "throughput-shootout",
                "recordIds": {
                    record["backend"]: record["id"] for record in older
                },
            },
        })
        resolved = launcher.optimizer_bound_engine_settings(
            self.model, ["omlx", "mtplx"], binding, self.options,
        )

        self.assertEqual(
            resolved,
            {record["backend"]: record["engineSettings"] for record in older},
        )

    def test_bound_result_cannot_turn_ane_prefill_back_on(self) -> None:
        self.model["backends"]["omlx"]["aneTuningVerified"] = True
        records = [self.record(
            backend, preference="throughput", shootout="fixed-controls",
            record_id=f"fixed-{backend}", created_at="2026-09-04T12:00:00Z",
        ) for backend in self.model["backends"]]
        records[0]["engineSettings"]["anePrefill"] = "tuned"
        for record in records:
            self.model["backends"][record["backend"]]["localBenchmarks"] = [record]
        binding = {
            "scope": "engine", "suite": self.SUITE, "preference": "throughput",
            "shootoutId": "fixed-controls",
            "recordIds": {record["backend"]: record["id"] for record in records},
        }
        with self.assertRaisesRegex(ValueError, "fixed.*setting"):
            launcher.optimizer_bound_engine_settings(
                self.model, list(self.model["backends"]), binding, self.options,
            )
        matching = {**self.options, "anePrefill": "tuned", "burst": "aggressive"}
        resolved = launcher.optimizer_bound_engine_settings(
            self.model, list(self.model["backends"]), binding, matching,
        )
        self.assertEqual(resolved["omlx"]["anePrefill"], "tuned")
        self.assertEqual(resolved["omlx"]["burst"], "balanced")


if __name__ == "__main__":
    unittest.main()
