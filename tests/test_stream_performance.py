"""Streaming cost, bounded retention, and real counter timing regressions."""
from __future__ import annotations

import json
from types import SimpleNamespace
import unittest
from unittest import mock

import codex_proxy
import response_metrics
import responses_bridge
import session_proxy
from stream_observer import ChunkJSONDecoder


def event(value, ending=b"\n\n"):
    return b"data: " + json.dumps(value, ensure_ascii=False).encode() + ending


class DecoderTests(unittest.TestCase):
    def test_metadata_and_outcome_decode_each_small_payload_once(self):
        metrics = response_metrics.ResponseMetrics("chat-completions", "text/event-stream", "splash")
        wire = (event({"choices": [{"delta": {"reasoning_content": "inspect"}}]})
                + event({"choices": [{"delta": {"tool_calls": [{"function": {"arguments": "{}"}}]},
                                        "finish_reason": "tool_calls"}]})
                + event({"usage": {"prompt_tokens": 1024, "completion_tokens": 64}}))
        original = json.loads
        with mock.patch.object(json, "loads", wraps=original) as decode:
            self.assertTrue(metrics.feed(wire))
            self.assertEqual(decode.call_count, 3)
        self.assertEqual(metrics._decoder.cache, {}, "No prompt/response data retained after a read")
        metrics.finish()
        self.assertEqual(metrics.outcome.result, "completed")
        self.assertEqual(metrics.public_usage(), (1024, 64))

    def test_decode_cache_is_byte_bounded_and_preserves_null(self):
        decoder = ChunkJSONDecoder(12)
        self.assertIsNone(decoder.loads(b"null"))
        self.assertIsNone(decoder.loads(bytearray(b"null")))
        self.assertEqual(decoder.size, 4)
        for value in range(30):
            self.assertEqual(decoder.loads(json.dumps(value).encode()), value)
            self.assertLessEqual(decoder.size, decoder.maximum)
        self.assertEqual(decoder.loads(b'"large uncached payload"'), "large uncached payload")
        decoder.clear()
        self.assertEqual(decoder.size, 0)

    def test_responses_guard_decodes_nonterminal_event_once(self):
        guard = codex_proxy.ResponsesLimitGuard(100, True)
        original = json.loads
        with mock.patch.object(json, "loads", wraps=original) as decode:
            wire = event({"type": "response.output_text.delta", "delta": "answer"})
            self.assertEqual(guard.feed(wire), wire)
            self.assertEqual(decode.call_count, 1)


class BridgeTests(unittest.TestCase):
    def bridge(self):
        return responses_bridge.ChatStreamBridge(SimpleNamespace(
            model="qwen", output_limit=10000,
            by_wire_name={"inspect": responses_bridge.ToolTarget("functions", "inspect")},
        ))

    def test_fragmented_unicode_text_reasoning_and_tool_arguments_are_preserved(self):
        bridge = self.bridge()
        parts = [event({"choices": [{"delta": {
            "tool_calls": [{"index": 0, "id": "call-1", "function": {"name": "inspect"}}],
        }}]}, b"\n\r\n")]
        arguments = []
        for index in range(1000):
            fragment = f"{index}:漢🦙 "
            arguments.append(fragment)
            parts.append(event({"choices": [{"delta": {
                "content": "答", "reasoning_content": "考",
                "tool_calls": [{"index": 0, "function": {"arguments": fragment}}],
            }}]}))
        parts.append(event({"choices": [{"finish_reason": "tool_calls"}]}))
        source = b"".join(parts)
        output = []
        for start in range(0, len(source), 7):
            output.append(bridge.feed(source[start:start + 7]))
        output.append(bridge.finish())
        self.assertEqual(bridge.text, "答" * 1000)
        self.assertEqual(bridge.reasoning, "考" * 1000)
        events = [json.loads(line[6:]) for line in b"".join(output).splitlines() if line.startswith(b"data: ")]
        tool = next(value["item"] for value in events
                    if value.get("item", {}).get("type") == "function_call")
        self.assertEqual(tool["arguments"], "".join(arguments))
        self.assertEqual(events[-1]["type"], "response.completed")

    def test_large_fragmented_event_scans_only_new_bytes(self):
        class MeasuredBuffer(bytearray):
            searched = 0

            def find(self, needle, start=0):
                self.searched += len(self) - start
                return super().find(needle, start)

        bridge = self.bridge()
        measured = bridge.buffer = MeasuredBuffer()
        wire = event({"choices": [{"delta": {"content": "x" * (2 * 1024 * 1024)}}]})
        for start in range(0, len(wire), 4096):
            bridge.feed(wire[start:start + 4096])
        self.assertLess(measured.searched, 3 * len(wire))
        self.assertEqual(len(bridge.text), 2 * 1024 * 1024)

    def test_oversized_event_and_total_output_fail_with_bounded_buffers(self):
        with mock.patch.object(responses_bridge, "MAX_BRIDGE_EVENT_BYTES", 128):
            bridge = self.bridge()
            output = bridge.feed(b"data: " + b"x" * 1000)
            self.assertIn(b"response.failed", output)
            self.assertEqual(bridge.buffer, b"")
            self.assertEqual(bridge.feed(b"more"), b"")
        with mock.patch.object(responses_bridge, "MAX_BRIDGE_OUTPUT_BYTES", 7):
            bridge = self.bridge()
            self.assertNotIn(b"response.failed", bridge.feed(event({"choices": [{"delta": {"content": "漢"}}]})))
            self.assertIn(b"response.failed", bridge.feed(event({"choices": [{"delta": {"content": "🦙🦙"}}]})))
            self.assertEqual(bridge.text, "漢", "Bounds count UTF-8 bytes")


class ThroughputTests(unittest.TestCase):
    def test_observed_rates_stop_before_slow_terminal_delivery(self):
        scheduler = session_proxy.RequestScheduler(1)
        rid = scheduler.begin({"id": "surface", "client": "omp"}, "chat-completions")
        scheduler.await_turn(rid)
        scheduler.records[rid]["startedMonotonic"] = 10
        with mock.patch.object(session_proxy.time, "monotonic", return_value=12):
            scheduler.observe_chunk(rid, 2048, True)
        with mock.patch.object(session_proxy.time, "monotonic", return_value=20):
            scheduler.upstream_completed(rid)
        scheduler.set_usage(rid, 2000, 21)
        with mock.patch.object(session_proxy.time, "monotonic", return_value=100):
            scheduler.finish(rid, "completed", 200)
        recent = scheduler.snapshot([])["recent"][0]
        self.assertEqual(recent["endToEndTokensPerSecond"], 2.1)
        self.assertEqual(recent["decodeTokensPerSecond"], 2.5)
        self.assertEqual(recent["bytesRelayed"], 2048)
        self.assertEqual(recent["surface"], "oh-my-pi")
        self.assertEqual(recent["observedStatsSource"], "engine-usage-and-relay-clock")

    def test_socket_chunk_count_never_becomes_a_token_count(self):
        scheduler = session_proxy.RequestScheduler(1)
        rid = scheduler.begin({"id": "surface", "client": "pi"}, "chat-completions")
        scheduler.await_turn(rid)
        for _ in range(100):
            scheduler.observe_chunk(rid, 1000, True)
        scheduler.finish(rid, "completed", 200)
        recent = scheduler.snapshot([])["recent"][0]
        self.assertIsNone(recent["completionTokens"])
        self.assertIsNone(recent["decodeTokensPerSecond"])
        self.assertFalse(recent["tpsSampleQualified"])

    def test_ttft_only_native_metadata_retains_the_correct_engine_source(self):
        metrics = response_metrics.ResponseMetrics("chat-completions", "application/json", "omlx")
        metrics.feed(json.dumps({"choices": [{"finish_reason": "stop"}], "usage": {
            "prompt_tokens": 20, "completion_tokens": 2, "time_to_first_token": 0.3,
        }}).encode())
        metrics.finish()
        scheduler = session_proxy.RequestScheduler(1)
        rid = scheduler.begin({"id": "surface", "client": "pi"}, "chat-completions")
        scheduler.set_runtime_stats(rid, metrics.public_runtime_stats())
        self.assertEqual(scheduler.snapshot([])["queued"][0]["runtimeStatsSource"], "omlx-native-stats")
        self.assertEqual(metrics._decoder.cache, {})

    def test_kolibri_native_source_and_prompt_timings_survive_scheduler_projection(self):
        scheduler = session_proxy.RequestScheduler(1)
        rid = scheduler.begin({"id":"surface","client":"omp"},"chat-completions")
        scheduler.set_usage(rid,1121,59)
        scheduler.set_runtime_stats(rid,{"runtimeStatsSource":"kolibri-native-stats",
            "runtimeTokensPerSecond":8.6,"runtimeGenerationSeconds":59/8.6,
            "runtimeDecodeTokenCount":59,"runtimeThroughputBasis":"request-native-generation",
            "promptProcessing":{"source":"kolibri-native-stats","processedTokens":1121,
                                "cachedTokens":0,"elapsedSeconds":1121/31.38,"tokensPerSecond":31.38}})
        row=scheduler.snapshot([])["queued"][0]
        self.assertEqual(row["runtimeStatsSource"],"kolibri-native-stats")
        self.assertEqual(row["runtimeTokensPerSecond"],8.6)
        self.assertEqual(row["promptProcessing"]["source"],"kolibri-native-stats")

    def test_buffered_and_speculative_routes_never_fabricate_delivery_decode(self):
        for backend in ("kolibri","splash"):
            with self.subTest(backend=backend):
                scheduler=session_proxy.RequestScheduler(1)
                with mock.patch.object(session_proxy.time,"monotonic",return_value=1):
                    rid=scheduler.begin({"id":"surface","client":"pi"},"chat-completions",backend)
                    scheduler.await_turn(rid)
                with mock.patch.object(session_proxy.time,"monotonic",return_value=1.5):
                    scheduler.observe_chunk(rid,1000,True)
                scheduler.set_usage(rid,200,100)
                with mock.patch.object(session_proxy.time,"monotonic",return_value=1.6):
                    scheduler.upstream_completed(rid)
                    scheduler.finish(rid,"completed",200)
                row=scheduler.snapshot([])["recent"][0]
                self.assertIsNone(row["decodeTokensPerSecond"])
                self.assertAlmostEqual(row["endToEndTokensPerSecond"],166.67,places=2)

    def test_splash_first_batch_only_and_superseded_native_proof_stay_honest(self):
        scheduler=session_proxy.RequestScheduler(1)
        rid=scheduler.begin({"id":"surface","client":"omp"},"chat-completions","splash")
        scheduler.set_usage(rid,200,100)
        native={"runtimeStatsSource":"splash-native-stats","runtimeDecodeTokenCount":92,
                "runtimeFirstBatchTokens":8,"runtimeGenerationSeconds":2,"runtimeTokensPerSecond":46,
                "runtimeThroughputBasis":"request-lifecycle-excluding-first-native-batch"}
        scheduler.set_runtime_stats(rid,native)
        self.assertEqual(scheduler.snapshot([])["queued"][0]["runtimeTokensPerSecond"],46)
        scheduler.set_usage(rid,200,99)
        self.assertIsNone(scheduler.snapshot([])["queued"][0]["runtimeTokensPerSecond"])
        scheduler.set_usage(rid,200,100)
        scheduler.set_runtime_stats(rid,{})
        self.assertIsNone(scheduler.snapshot([])["queued"][0]["runtimeTokensPerSecond"])
        scheduler.set_runtime_stats(rid,{**native,"runtimeDecodeTokenCount":100,
                                       "runtimeFirstBatchTokens":0,"runtimeTokensPerSecond":50})
        self.assertIsNone(scheduler.snapshot([])["queued"][0]["runtimeTokensPerSecond"])
        scheduler.set_usage(rid,200,8)
        scheduler.set_runtime_stats(rid,{**native,"runtimeDecodeTokenCount":0,
                                       "runtimeGenerationSeconds":0,"runtimeTokensPerSecond":None})
        row=scheduler.snapshot([])["queued"][0]
        self.assertEqual(row["runtimeStatsSource"],"splash-native-stats")
        self.assertIsNone(row["runtimeTokensPerSecond"])
        self.assertIsNone(row["decodeTokensPerSecond"])

    def test_invalid_unbounded_native_counters_do_not_overflow_or_make_rates(self):
        metrics = response_metrics.ResponseMetrics("chat-completions", "text/event-stream", "lmstudio")
        huge = 10 ** 400
        metrics.feed(event({"usage": {"prompt_tokens": huge, "completion_tokens": huge},
                            "stats": {"tokens_per_second": huge, "generation_time": huge}}))
        self.assertEqual(metrics.public_usage(), (None, None))
        self.assertEqual(metrics.public_runtime_stats(), {})
        scheduler = session_proxy.RequestScheduler(1)
        rid = scheduler.begin({"id": "surface", "client": "pi"}, "chat-completions")
        scheduler.set_usage(rid, huge, huge)
        scheduler.set_runtime_stats(rid, {"runtimeTokensPerSecond": huge})
        record = scheduler.snapshot([])["queued"][0]
        self.assertFalse(record["usageReported"])
        self.assertIsNone(record["runtimeTokensPerSecond"])


if __name__ == "__main__":
    unittest.main()
