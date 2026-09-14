"""Correctness probes must not silently inherit stochastic launch sampling."""
import copy
import json
from types import SimpleNamespace
import unittest

import launcher


class BenchmarkProbeSamplingTests(unittest.TestCase):
    def plan(self, backend, mode="model"):
        values = {"temperature": 1.0, "top_p": 0.95, "top_k": 20}
        contract = launcher.build_sampling_contract(mode, **{
            "model_defaults" if mode == "model" else "custom": values,
        }).as_dict()
        return SimpleNamespace(backend=backend, client="chat", port=1, reasoning="auto",
            model={"servedId":"synthetic-model", "defaultSampling":values,
                "backends":{backend:{"customSampling":True, "implicitSamplingDefaultsVerified":True}}},
            options={}, secrets={"apiKey":"unused-local-fixture"},
            chat=None, sampling_contract=contract)

    def test_fixed_probe_and_speed_requests_have_distinct_immutable_sampling(self):
        probe = {"temperature":0.0, "top_p":1.0, "top_k":0, "seed":17}
        for backend in ("mtplx", "omlx", "lmstudio"):
            for mode in ("model", "custom"):
                with self.subTest(backend=backend, mode=mode):
                    plan = self.plan(backend, mode)
                    original = copy.deepcopy(plan.sampling_contract)
                    fixed = json.loads(launcher.build_benchmark_completion_request(
                        plan, "Generated check", 64, probe, greedy_probe=True).data)
                    self.assertEqual({key:fixed[key] for key in probe}, probe)
                    speed = json.loads(launcher.build_benchmark_completion_request(
                        plan, "Generated workload", 256, probe).data)
                    self.assertEqual(speed["temperature"], 1.0)
                    self.assertEqual(speed["top_p"], 0.95)
                    self.assertEqual(speed["top_k"], 20)
                    self.assertNotIn("seed", speed)
                    self.assertEqual(plan.sampling_contract, original)

    def test_probe_override_is_explicit_and_fixed(self):
        with self.assertRaisesRegex(ValueError, "contract changed"):
            launcher.build_benchmark_completion_request(self.plan("mtplx"),
                "Generated check", 64, {"temperature":0.5}, greedy_probe=True)
        with self.assertRaisesRegex(ValueError, "packaged sampler"):
            launcher.build_benchmark_completion_request(self.plan("uzu"),
                "Generated check", 64, {"temperature":0, "top_p":1, "top_k":0, "seed":17},
                greedy_probe=True)

    def test_old_core_engine_receipts_cannot_enter_automatic_selection(self):
        for backend in ("omlx", "lmstudio", "mtplx"):
            record = {"id":"historical", "scope":"local", "backend":backend,
                "modelFingerprint":"model", "runtimeVersion":"3.0.0",
                "hardwareFingerprint":"mac"}
            original = copy.deepcopy(record)
            self.assertIn("re-test", launcher.benchmark_probe_integrity_issue(record))
            self.assertEqual(launcher.matching_benchmark_records(
                [record], backend, "model", "3.0.0", {}, "mac"), [])
            self.assertEqual(record, original)
            record["probeContract"] = copy.deepcopy(launcher.BENCHMARK_PROBE_CONTRACT)
            self.assertIsNone(launcher.benchmark_probe_integrity_issue(record))
            self.assertEqual(launcher.matching_benchmark_records(
                [record], backend, "model", "3.0.0", {}, "mac"), [record])
            record["probeContract"]["sampling"]["temperature"] = 1.0
            self.assertIsNotNone(launcher.benchmark_probe_integrity_issue(record))

    def test_operator_exception_is_narrow_and_does_not_supply_verification(self):
        record = {"backend":"mtplx", "kind":"mtplx-long-context-operator-tuning",
            "mtplxOperatorSweep":{"version":5}}
        self.assertIsNone(launcher.benchmark_probe_integrity_issue(record))
        self.assertFalse(launcher._local_benchmark_record_verified({}, record, {}))
        for change in ({"backend":"omlx"}, {"kind":"benchmark"},
                       {"mtplxOperatorSweep":{"version":4}}, {"probeContract":None}):
            self.assertIsNotNone(launcher.benchmark_probe_integrity_issue({**record, **change}))
        self.assertIsNone(launcher.benchmark_probe_integrity_issue({"backend":"uzu"}))


if __name__ == "__main__":
    unittest.main()
