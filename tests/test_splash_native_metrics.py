"""Request-bound Splash1.2.1 native timing; no model load or global stats."""
import copy
import json
from pathlib import Path
import unittest

from response_metrics import ResponseMetrics


def frames(prompt=2918, completion=48, cached=0, decoded=40,
           start_ms=6281.351, decode_ms=515.845, queue_ms=.536):
    """Default values are an actual bounded Pi tool request from this Mac."""
    header = {"object": "chat.completion.chunk", "id": "chatcmpl-splash-native-fixture",
              "model": "incoai/Qwen3.8-27B-Splash", "created": 1}
    rate = decoded * 1000 / decode_ms if decoded and decode_ms else 0
    terminal = {**header, "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
                "timings": {"prompt_n": prompt, "predicted_n": completion, "cache_n": cached,
                    "prompt_ms": start_ms, "predicted_ms": decode_ms, "predicted_per_second": rate,
                    "prompt_per_second": (prompt - cached) * 1000 / start_ms if start_ms else 0}}
    latency = {"start_to_first_token_ms": start_ms, "first_token_to_done_ms": decode_ms,
               "ttft_ms": start_ms + queue_ms, "queue_to_start_ms": queue_ms,
               "wall_ms": start_ms + queue_ms + decode_ms}
    if decoded:
        latency["stream_tokens_per_second"] = rate
    usage = {**header, "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
             "usage": {"prompt_tokens": prompt, "completion_tokens": completion,
                       "total_tokens": prompt + completion, "prompt_tokens_details": {"cached_tokens": cached}},
             "metrics": {"prefill": {"tokens": prompt - cached}, "decode": {"tokens": decoded},
                         "cache": {"matched_tokens": cached}, "request_latency": latency}}
    return terminal, usage


def feed(metrics, value):
    metrics.feed(("data: " + json.dumps(value) + "\n\n").encode())


class SplashNativeMetricsTests(unittest.TestCase):
    def observe(self, pair=None, *, backend="splash", protocol="chat-completions", content_type="text/event-stream"):
        metrics = ResponseMetrics(protocol, content_type, backend)
        for frame in pair or frames():
            feed(metrics, frame)
        return metrics

    def test_first_speculative_batch_is_excluded_from_native_interval(self):
        metrics = self.observe()
        stats = metrics.public_runtime_stats()
        self.assertEqual(metrics.public_usage(), (2918, 48))
        self.assertEqual(stats["runtimeStatsSource"], "splash-native-stats")
        self.assertEqual(stats["runtimeFirstBatchTokens"], 8)
        self.assertEqual(stats["runtimeDecodeTokenCount"], 40)
        self.assertAlmostEqual(stats["runtimeTokensPerSecond"], 77.542672702)
        self.assertAlmostEqual(stats["runtimeGenerationSeconds"], .515845)
        self.assertAlmostEqual(stats["runtimeTimeToFirstTokenSeconds"], 6.281887)
        self.assertEqual(stats["runtimeThroughputBasis"], "request-lifecycle-excluding-first-native-batch")
        inflated_single_token_assumption = 47 / .515845
        self.assertGreater(inflated_single_token_assumption, stats["runtimeTokensPerSecond"] * 1.17)

    def test_cached_prompt_uses_processed_count_and_native_request_interval(self):
        metrics = self.observe(frames(prompt=2988, completion=25, cached=2880, decoded=21,
                                      start_ms=472.951, decode_ms=259.114, queue_ms=6.061))
        stats = metrics.public_runtime_stats()
        self.assertAlmostEqual(stats["runtimeTokensPerSecond"], 81.045408585)
        self.assertEqual(stats["promptProcessing"], {"source": "splash-native-stats", "processedTokens": 108,
            "cachedTokens": 2880, "elapsedSeconds": .472951, "tokensPerSecond": 228.35,
            "basis": "request-start-to-first-native-token"})
        # The actual relay saw the visible tool name later than native first
        # emission. Native counts plus that shorter relay clock also inflate.
        self.assertGreater(21 / .173, stats["runtimeTokensPerSecond"] * 1.49)

    def test_all_tokens_in_first_batch_has_no_decode_rate(self):
        metrics = self.observe(frames(completion=8, decoded=0, start_ms=100, decode_ms=0, queue_ms=0))
        self.assertEqual(metrics.runtime_stats["runtimeFirstBatchTokens"], 8)
        self.assertEqual(metrics.runtime_stats["runtimeDecodeTokenCount"], 0)
        self.assertNotIn("runtimeTokensPerSecond", metrics.runtime_stats)

    def test_global_status_counters_are_not_request_rate_evidence(self):
        pair = list(frames())
        pair[1]["metrics"] = {"decode_output_tokens": 48, "decode_tokens_per_second": 999,
                              "prefill_input_tokens": 2918, "prefill_tokens_per_second": 9999}
        self.assertEqual(self.observe(pair).runtime_stats, {})

    def test_usage_without_matching_terminal_raw_counts_is_not_native_evidence(self):
        terminal, usage = frames()
        self.assertEqual(self.observe([usage]).runtime_stats, {})
        terminal["timings"]["predicted_n"] = 47
        self.assertEqual(self.observe([terminal, usage]).runtime_stats, {})

    def test_terminal_id_model_or_finish_scope_mismatch_fails_closed(self):
        for mutate in (lambda t: t.update(id="chatcmpl-other-request"),
                       lambda t: t.update(model="other-model"),
                       lambda t: t["choices"][0].update(finish_reason=None),
                       lambda t: t["choices"][0].update(delta={"content": "not a terminal metadata frame"}),
                       lambda t: t["timings"].update(prompt_n=2917),
                       lambda t: t["timings"].update(cache_n=1),
                       lambda t: t["timings"].update(predicted_ms=516),
                       lambda t: t["timings"].update(predicted_per_second=999),
                       lambda t: t["timings"].update(prompt_per_second=9999),
                       lambda t: t.update(id="x" * 257)):
            with self.subTest(mutation=mutate):
                terminal, usage = frames(); mutate(terminal)
                self.assertEqual(self.observe([terminal, usage]).runtime_stats, {})

    def test_malformed_counter_duration_and_rate_relations_are_rejected(self):
        mutations = (
            lambda v: v["usage"].update(completion_tokens=True),
            lambda v: v["usage"].update(completion_tokens=49, total_tokens=2967),
            lambda v: v["usage"].update(total_tokens=2965),
            lambda v: v["usage"]["prompt_tokens_details"].update(cached_tokens=1),
            lambda v: v["metrics"]["prefill"].update(tokens=2917),
            lambda v: v["metrics"]["decode"].update(tokens=48),
            lambda v: v["metrics"]["decode"].update(tokens=49),
            lambda v: v["metrics"]["decode"].update(tokens=-1),
            lambda v: v["metrics"]["decode"].update(tokens=True),
            lambda v: v["metrics"]["cache"].update(matched_tokens="0"),
            lambda v: v["metrics"]["request_latency"].update(first_token_to_done_ms=0),
            lambda v: v["metrics"]["request_latency"].update(wall_ms=100),
            lambda v: v["metrics"]["request_latency"].update(ttft_ms=6000),
            lambda v: v["metrics"]["request_latency"].update(queue_to_start_ms=10),
            lambda v: v["metrics"]["request_latency"].update(stream_tokens_per_second=999),
            lambda v: v["metrics"]["request_latency"].update(stream_tokens_per_second=float("nan")),
            lambda v: v["metrics"]["request_latency"].update(first_token_to_done_ms=float("inf")),
            lambda v: v["metrics"]["request_latency"].update(stream_tokens_per_second=47 * 1000 / 515.845),
            lambda v: v["metrics"].pop("cache"),
            lambda v: v.update(metrics=None),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                terminal, usage = frames(); mutate(usage)
                self.assertEqual(self.observe([terminal, usage]).runtime_stats, {})

    def test_only_native_chat_sse_metadata_is_accepted(self):
        for options in ({"backend": "lmstudio"}, {"backend": "kolibri"}, {"backend": "omlx"},
                        {"protocol": "responses"}, {"content_type": "application/json"}):
            with self.subTest(options=options):
                self.assertNotEqual(self.observe(**options).runtime_stats.get("runtimeStatsSource"), "splash-native-stats")

    def test_superseded_final_usage_clears_all_previous_native_proof(self):
        metrics = self.observe()
        _, changed = frames(completion=49)
        feed(metrics, changed)
        self.assertEqual(metrics.public_usage(), (2918, 49))
        self.assertEqual(metrics.runtime_stats, {})

    def test_same_counts_without_new_terminal_timing_cannot_reuse_old_rate(self):
        metrics = self.observe()
        _, repeated = frames()
        feed(metrics, repeated)
        self.assertEqual(metrics.runtime_stats, {})

    def test_malformed_later_usage_clears_native_metadata_but_keeps_unrelated_data(self):
        metrics = self.observe()
        metrics.runtime_stats["expertCache"] = {"allocatedBytes": 123}
        feed(metrics, {"usage": None})
        self.assertEqual(metrics.runtime_stats, {"expertCache": {"allocatedBytes": 123}})

    def test_no_rate_is_invented_from_timing_or_usage_alone(self):
        terminal, usage = frames()
        metrics = self.observe([terminal])
        self.assertEqual(metrics.runtime_stats, {})
        usage.pop("metrics")
        feed(metrics, usage)
        self.assertEqual(metrics.public_usage(), (2918, 48))
        self.assertEqual(metrics.runtime_stats, {})

    def test_decoded_payload_api_reuses_parser_results_and_does_not_mutate_frames(self):
        pair = frames(); before = copy.deepcopy(pair)
        metrics = ResponseMetrics("chat-completions", "text/event-stream", "splash")
        for payload in pair:
            metrics.observe_payload(payload)
        self.assertEqual(pair, before)
        self.assertEqual(metrics.public_runtime_stats(), self.observe(pair).public_runtime_stats())

    def test_valid_json_nonstream_response_does_not_claim_sse_native_timing(self):
        terminal, usage = frames()
        usage["timings"] = terminal["timings"]
        metrics = ResponseMetrics("chat-completions", "application/json", "splash")
        metrics.feed(json.dumps(usage).encode()); metrics.finish()
        self.assertEqual(metrics.public_usage(), (2918, 48))
        self.assertEqual(metrics.runtime_stats, {})

    def test_actual_pi_and_omp_native_metadata_fixtures(self):
        root = Path(__file__).resolve().parents[1] / "bench/results"
        paths = (root / "20261006-splash-agents-native-verified.json", root / "20261006-splash-omp-native.json")
        # The public metadata fixtures contain counters/timings only. Build
        # their documented two final native frames without response text.
        for path in paths:
            report = json.loads(path.read_text())
            for agent in report["agents"]:
                for request in agent["nativeRequests"]:
                    terminal, usage = frames()
                    terminal["timings"] = copy.deepcopy(request["timings"])
                    usage["usage"] = copy.deepcopy(request["usage"])
                    usage["metrics"] = copy.deepcopy(request["metrics"])
                    with self.subTest(client=agent["client"], count=usage["usage"]["completion_tokens"]):
                        observed = self.observe([terminal, usage]).runtime_stats
                        self.assertEqual(observed["runtimeStatsSource"], "splash-native-stats")
                        self.assertEqual(observed["runtimeDecodeTokenCount"], request["metrics"]["decode"]["tokens"])
                        self.assertEqual(observed["runtimeTokensPerSecond"], request["metrics"]["request_latency"]["stream_tokens_per_second"])


if __name__ == "__main__":
    unittest.main()
