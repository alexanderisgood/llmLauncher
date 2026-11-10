from __future__ import annotations

from copy import deepcopy
import json
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

import generation_metrics
import inference_requests
import launcher
from bench import harness
from tests.test_splash_native_metrics import frames as splash_frames


def kolibri_usage(completion=100):
    return {"prompt_tokens": 120, "completion_tokens": completion, "total_tokens": 120 + completion,
            "prompt_tokens_details": {"cached_tokens": 100}, "generation_duration": 10.,
            "generation_tokens_per_second": completion / 10., "prompt_eval_duration": 2.,
            "kolibri_native_stats": {"version": 1, "prompt_tokens": 120,
                                     "processed_prompt_tokens": 20, "cached_prompt_tokens": 100,
                                     "generation_tokens": completion}}


def burst_frames(usage):
    return [
        {"choices": [{"delta": {"content": "first"}}]},
        {"choices": [{"delta": {"content": "second"}, "finish_reason": "stop"}], "usage": usage},
    ]


class Response:
    def __init__(self, values):
        self.values = values
        self.headers = {"Content-Type": "text/event-stream"}
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def __iter__(self):
        for value in self.values:
            yield b"data: " + json.dumps(value).encode() + b"\n"
        yield b"data: [DONE]\n"


class GenerationMetricsTests(unittest.TestCase):
    def measure(self, backend, values):
        plan = SimpleNamespace(backend=backend, options={})
        with mock.patch.object(inference_requests.InferenceRequests, "build_benchmark_completion_request", return_value=object()), mock.patch.object(launcher.urllib.request, "urlopen", return_value=Response(values)), mock.patch.object(launcher.time, "monotonic", side_effect=[0, 10, 10.01, 11]):
            return launcher.run_benchmark_completion(plan, "generated fixture", 128, {}, threading.Event())

    def record(self, backend, sample, claimed_median=9999):
        return {
            "backend": backend, "comparisonContractVersion": launcher.BENCHMARK_COMPARISON_CONTRACT_VERSION,
            "qualityFingerprint": "a" * 64, "qualityCompletionTokens": 32,
            "winner": "ar", "modes": {"ar": {"samples": [{**sample, "targetPromptTokens": 120, "repetition": 1}],
                                                "medianDecodeTokensPerSecond": claimed_median}},
        }

    def test_kolibri_buffered_delivery_uses_request_native_duration_not_burst(self):
        sample = self.measure("kolibri", burst_frames(kolibri_usage()))
        self.assertEqual(sample["decodeTokensPerSecond"], 10)
        self.assertGreater(sample["observedDecodeTokensPerSecond"], 9000)
        self.assertEqual(sample["decodeTimingSource"], "kolibri-native-stats")
        self.assertEqual(sample["generationProof"]["decodeTokenCount"], 100)
        self.assertEqual(sample["generationProof"]["generationSeconds"], 10)
        self.assertEqual(sample["ttftSeconds"], 10)
        self.assertAlmostEqual(sample["endToEndTokensPerSecond"], 100 / 11, places=4)
        measured = launcher.cross_engine_benchmark_measurement(self.record("kolibri", sample))
        self.assertEqual(measured["decodeTokensPerSecond"], 10, "Stored summary numbers must not override raw native proof")

    def test_splash_uses_lifecycle_count_after_first_batch_not_gpu_kernel_rate(self):
        terminal, usage = splash_frames(completion=48, decoded=40, start_ms=100, decode_ms=5000, queue_ms=0)
        terminal["choices"][0]["finish_reason"] = "stop"
        usage["metrics"]["decode"]["tokens_per_second"] = 999999
        sample = self.measure("splash", [*burst_frames({})[:1],
                                        {"choices": [{"delta": {"content": "second"}}]}, terminal, usage])
        self.assertEqual(sample["decodeTokensPerSecond"], 8)
        self.assertEqual(sample["generationProof"]["decodeTokenCount"], 40)
        self.assertEqual(sample["generationProof"]["firstBatchTokens"], 8)
        self.assertEqual(sample["decodeTimingBasis"], "request-lifecycle-excluding-first-native-batch")
        self.assertGreater(sample["observedDecodeTokensPerSecond"], 4000)

    def test_invalid_final_native_counter_clears_native_rate_and_suppresses_burst_fallback(self):
        values = burst_frames(kolibri_usage())
        invalid = kolibri_usage()
        invalid["kolibri_native_stats"]["generation_tokens"] = 99
        values.append({"usage": invalid, "choices": []})
        sample = self.measure("kolibri", values)
        self.assertIsNone(sample["decodeTokensPerSecond"])
        self.assertIsNone(sample["generationProof"])
        self.assertFalse(sample["decodeTimingValid"])
        self.assertGreater(sample["endToEndTokensPerSecond"], 0)

    def test_missing_native_proof_and_entire_first_batch_never_fabricate_generation_speed(self):
        missing = self.measure("splash", burst_frames({"prompt_tokens": 120, "completion_tokens": 16}))
        self.assertIsNone(missing["decodeTokensPerSecond"])
        terminal, usage = splash_frames(completion=16, decoded=0, start_ms=100, decode_ms=0, queue_ms=0)
        terminal["choices"][0]["finish_reason"] = "stop"
        entire = self.measure("splash", [burst_frames({})[0],
                                       {"choices": [{"delta": {"content": "second"}}]}, terminal, usage])
        self.assertEqual(entire["generationProof"]["firstBatchTokens"], 16)
        self.assertEqual(entire["generationProof"]["decodeTokenCount"], 0)
        self.assertIsNone(entire["decodeTokensPerSecond"])
        self.assertGreater(entire["endToEndTokensPerSecond"], 0)

    def test_saved_provenance_is_rederived_and_mutations_cannot_qualify(self):
        sample = self.measure("kolibri", burst_frames(kolibri_usage()))
        for changes in [
            {"generationProof": None}, {"decodeTimingSource": "engine-usage-and-relay-clock"},
            {"decodeTokensPerSecond": 9999}, {"completionTokens": 99},
            {"generationProof": {**sample["generationProof"], "generationSeconds": 1}},
            {"generationProof": {**sample["generationProof"], "decodeTokenCount": None}},
            {"generationProof": {**sample["generationProof"], "basis": "GPU-kernel-rate"}},
        ]:
            with self.subTest(changes=changes):
                self.assertIsNone(generation_metrics.sample_generation_tps({**sample, **changes}, "kolibri"))

    def test_legacy_delivery_generation_is_historical_only_but_end_to_end_remains(self):
        legacy = {"promptTokens": 120, "completionTokens": 100, "totalSeconds": 11,
                  "ttftSeconds": 10, "decodeTokensPerSecond": 9999, "endToEndTokensPerSecond": 100 / 11,
                  "decodeTimingValid": True, "decodeTimingBasis": "client output-event interval estimate"}
        saved = self.record("kolibri", legacy)
        measured = launcher.cross_engine_benchmark_measurement(saved)
        self.assertIsNone(measured["decodeTokensPerSecond"])
        self.assertGreater(measured["score"], 0)
        self.assertIsNone(launcher.benchmark_integrity_issue({**saved, "selectionPreference": "fastest"}))
        self.assertIn("native request proof", launcher.benchmark_integrity_issue({**saved, "selectionPreference": "throughput"}))
        self.assertIsNone(launcher._benchmark_history_value(measured, "throughput")[0])
        self.assertGreater(launcher._benchmark_history_value(measured, "fastest")[0], 0)

    def test_other_engine_reported_sample_median_and_nullable_ttft_are_preserved(self):
        sample = {"promptTokens": 120, "completionTokens": 100, "totalSeconds": 11,
                  "ttftSeconds": None, "decodeTokensPerSecond": 12, "decodeTimingValid": True}
        measured = launcher.cross_engine_benchmark_measurement(self.record("mtplx", sample, claimed_median=9999))
        self.assertEqual(measured["decodeTokensPerSecond"], 12)
        self.assertIsNone(measured["firstTokenSeconds"])
        self.assertGreater(measured["score"], 0)

    def test_read_only_harness_uses_the_same_native_parser_and_no_ttft_prefill_estimate(self):
        engine = SimpleNamespace(name="kolibri", extra={}, model_id="fixture", port=1234, api_key="")
        with mock.patch.object(harness.urllib.request, "urlopen", return_value=Response(burst_frames(kolibri_usage()))), mock.patch.object(harness.time, "monotonic", side_effect=[0, 10, 10.01, 11]):
            measured = harness.stream_chat(engine, "generated fixture")
        self.assertEqual(measured["decodeTokensPerSecond"], 10)
        self.assertEqual(measured["nativeDecodeTokensPerSecond"], 10)
        self.assertEqual(measured["prefillTokensPerSecond"], 10, "Actual native processed20tokens/2seconds, not120tokens/TTFT")
        self.assertEqual(measured["nativeThroughputBasis"], "request-native-generation")
        self.assertEqual(generation_metrics.sample_generation_tps(measured, "kolibri"), 10)

    def test_harness_splash_first_batch_and_invalid_final_do_not_use_delivery_fallback(self):
        engine = SimpleNamespace(name="splash", extra={}, model_id="fixture", port=1234, api_key="")
        terminal, usage = splash_frames(completion=16, decoded=0, start_ms=100, decode_ms=0, queue_ms=0)
        terminal["choices"][0]["finish_reason"] = "stop"
        values = [burst_frames({})[0], {"choices": [{"delta": {"content": "second"}}]}, terminal, usage]
        with mock.patch.object(harness.urllib.request, "urlopen", return_value=Response(values)), mock.patch.object(harness.time, "monotonic", side_effect=[0, 10, 10.01, 11]):
            measured = harness.stream_chat(engine, "generated fixture")
        self.assertIsNone(measured["decodeTokensPerSecond"])
        self.assertIsNone(measured["nativeDecodeTokensPerSecond"])
        self.assertFalse(measured["decodeTimingValid"])
        self.assertGreater(measured["endToEndTokensPerSecond"], 0)

    def test_invalid_authoritative_token_types_never_become_numeric_benchmark_scores(self):
        for value in [True, "100", 100.5, -1]:
            data = kolibri_usage()
            data["completion_tokens"] = value
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, "authoritative|empty|invalid"):
                self.measure("kolibri", burst_frames(data))


class NullableGenerationWorkerTests(unittest.TestCase):
    def exercise(self, preference):
        run = mock.Mock(plan=None, process=None, llamacpp_safety_violation=None,
                        codex_proxy_port=None, session_proxy_port=None)
        run.lock = threading.RLock()
        run.lifecycle_lock = threading.Lock()
        run.cancel_event = threading.Event()
        plan = SimpleNamespace(backend="splash", options={}, port=1234, client_port=1235,
                               run_dir=None, secrets={})
        def accept(value):
            run.plan = value
            run.cancel_event = threading.Event()
        run.start.side_effect = accept
        manager = launcher.BenchmarkManager(run)
        manager.state = {"phase": "queued", "job": {}, "modes": {}, "result": None, "events": []}
        job = {"backend": "splash", "suiteName": "quick", "modes": ["ar"],
               "enginePreference": preference, "output": 128, "context": 4096,
               "workloadKind": "throughput", "speedSampling": {},
               "suite": {"promptTokens": [128], "repetitions": 1, "maxTokens": 128}}
        sampler = mock.Mock(violation=None)
        sampler.stop.return_value = {}
        sample = {"promptTokens": 128, "completionTokens": 32, "authoritativeUsage": True,
                  "ttftSeconds": 1., "totalSeconds": 4., "decodeTokensPerSecond": None,
                  "decodeTimingValid": False, "endToEndTokensPerSecond": 8.,
                  "responseOutcome": "completed", "timingInvalidReason": "Native generation unavailable"}
        unload={"clean":True,"processExited":True,"processGroupExited":True,"managerIdle":True,
                "portsClosed":True,"checkedPorts":[1234,1235],"closedPorts":[1234,1235]}
        with mock.patch.object(manager, "_mode_payload", return_value={}), mock.patch.object(manager, "_mode_settings", return_value={}), mock.patch.object(launcher, "normalized_request", return_value=plan), mock.patch.object(launcher, "require_live_model_load_admission", return_value={}), mock.patch.object(launcher, "BenchmarkTelemetrySampler", return_value=sampler), mock.patch.object(manager, "_wait_for_engine"), mock.patch.object(launcher, "benchmark_clean_unload_evidence", return_value=unload), mock.patch.object(launcher, "run_benchmark_completion", side_effect=[{}, {"outputHash": "a" * 64, "completionTokens": 64}, sample]):
            return manager._measure_mode(job, [], "ar", 0, 3)

    def test_fastest_total_can_complete_without_claiming_generation_tps(self):
        measured, completed = self.exercise("fastest")
        self.assertEqual(completed, 3)
        self.assertIsNone(measured["medianDecodeTokensPerSecond"])
        self.assertEqual(measured["medianEndToEndTokensPerSecond"], 8)

    def test_highest_generation_goal_requires_native_timing(self):
        with self.assertRaisesRegex(RuntimeError, "Native generation unavailable"):
            self.exercise("throughput")


if __name__ == "__main__":
    unittest.main()
