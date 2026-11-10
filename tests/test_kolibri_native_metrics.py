"""No-model proofs for request-bound native Kolibri telemetry and parsing."""
from __future__ import annotations

import copy
from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path
from queue import Queue
import threading
import types
import unittest
from unittest import mock

import session_proxy

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("_kolibri_native_metrics_test",ROOT / "runtime_patches/kolibri/native_metrics.py")
native = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(native)


def usage(prompt=120,completion=60,cached=100):
    return {"prompt_tokens":prompt,"completion_tokens":completion,"total_tokens":prompt+completion,
            "prompt_tokens_details":{"cached_tokens":cached}}


def response(processed=20,generated=60,prompt_tps=10,generation_tps=30):
    return types.SimpleNamespace(prompt_tokens=processed,generation_tokens=generated,prompt_tps=prompt_tps,
                                 generation_tps=generation_tps)


def context(prompt=120,cached=100):
    return types.SimpleNamespace(prompt=list(range(prompt)),prompt_cache_count=cached,_should_stop=False)


def fake_server():
    @dataclass
    class Context:
        prompt:list
        prompt_cache_count:int
        _should_stop:bool = False
    class Handler:
        def completion_usage_response(self,prompt,generated,cached):
            return {"usage":usage(prompt,generated,cached)}
    server = types.SimpleNamespace(GenerationContext=Context,APIHandler=Handler)
    def stream_generate(values):
        yield from values
    server.stream_generate = stream_generate
    class Generator:
        def _serve_single(self, request):
            queue,body,args = request
            ctx = Context(list(range(body["prompt"])),body["cached"])
            queue.put(ctx)
            for value in server.stream_generate(body["responses"]):
                queue.put(value)
            queue.put(None)
        def generate(self, body):
            queue = Queue()
            self._serve_single((queue,body,None))
            ctx = queue.get()
            return ctx,queue
    server.ResponseGenerator = Generator
    return server


class NativeProducerTests(unittest.TestCase):
    def test_cached_prefix_uses_native_suffix_and_preserves_standard_usage(self):
        collector = native.NativeMetrics(); collector.observe(response())
        original = usage(); unchanged = copy.deepcopy(original)
        stats = collector.usage(context(),original)
        self.assertEqual(original,unchanged)
        self.assertEqual(stats["generation_tokens_per_second"],30)
        self.assertEqual(stats["generation_duration"],2)
        self.assertEqual(stats["prompt_eval_duration"],2)
        self.assertEqual(stats["kolibri_native_stats"],{"version":1,"prompt_tokens":120,
            "processed_prompt_tokens":20,"cached_prompt_tokens":100,"generation_tokens":60})

    def test_malformed_or_mismatched_counters_never_emit_native_fields(self):
        collector = native.NativeMetrics(); collector.observe(response())
        for field,value in (("completion_tokens",59),("prompt_tokens",121),("total_tokens",181)):
            data = usage(); data[field] = value
            with self.subTest(field=field):
                self.assertIsNone(collector.usage(context(),data))
        self.assertIsNone(collector.usage(context(cached=99),usage()))
        for bad in (True,float("nan"),float("inf"),-1,0,10**400):
            with self.subTest(rate=str(bad)):
                collector.observe(response(generation_tps=bad))
                self.assertIsNone(collector.usage(context(),usage()))

    def test_cancelled_context_suppresses_incomplete_telemetry(self):
        collector = native.NativeMetrics(); collector.observe(response())
        ctx = context(); ctx._should_stop = True
        self.assertIsNone(collector.usage(ctx,usage()))

    def test_interleaved_http_requests_retain_their_own_producer_counters(self):
        server = fake_server(); native.install(server)
        generator,handler = server.ResponseGenerator(),server.APIHandler()
        first_ready,finish_first = threading.Event(),threading.Event()
        values,errors = {},[]
        def delayed_first():
            try:
                generator.generate({"prompt":120,"cached":100,"responses":[response()]})
                first_ready.set(); finish_first.wait(5)
                values["first"] = handler.completion_usage_response(120,60,100)
            except Exception as error:
                errors.append(error); first_ready.set()
        thread = threading.Thread(target=delayed_first); thread.start()
        self.assertTrue(first_ready.wait(5))
        generator.generate({"prompt":200,"cached":20,"responses":[response(180,8,40,2)]})
        values["second"] = handler.completion_usage_response(200,8,20)
        finish_first.set(); thread.join(5)
        self.assertFalse(thread.is_alive()); self.assertEqual(errors,[])
        self.assertEqual(values["first"]["usage"]["generation_tokens_per_second"],30)
        self.assertEqual(values["second"]["usage"]["generation_tokens_per_second"],2)
        # Usage consumes the request association; a second response cannot
        # inherit the preceding request's native facts.
        self.assertNotIn("kolibri_native_stats",handler.completion_usage_response(200,8,20)["usage"])

    def test_explicit_generator_cancellation_closes_native_iterator(self):
        server = fake_server(); closed = threading.Event()
        def cancellable(values):
            try:
                yield from values
            finally:
                closed.set()
        server.stream_generate = cancellable
        native.install(server)
        iterator = server.stream_generate([response(),response(generated=61)])
        next(iterator); iterator.close()
        self.assertTrue(closed.is_set())

    def test_one_producer_can_finish_a_later_request_before_first_http_usage(self):
        server = fake_server()
        class QueuedGenerator(server.ResponseGenerator):
            def __init__(self):
                self.pending = Queue()
                self.worker = threading.Thread(target=self.work)
                self.worker.start()
            def work(self):
                while True:
                    request = self.pending.get()
                    if request is None:
                        return
                    self._serve_single(request)
            def generate(self,body):
                queue = Queue(); self.pending.put((queue,body,None))
                return queue.get(),queue
        server.ResponseGenerator = QueuedGenerator
        native.install(server)
        generator,handler = QueuedGenerator(),server.APIHandler()
        first_ready,finish_first = threading.Event(),threading.Event()
        values,errors = {},[]
        def drain(queue):
            while queue.get() is not None:
                pass
        def first():
            try:
                _,queue = generator.generate({"prompt":120,"cached":100,"responses":[response()]})
                drain(queue); first_ready.set(); finish_first.wait(5)
                values["first"] = handler.completion_usage_response(120,60,100)
            except Exception as error:
                errors.append(error); first_ready.set()
        thread = threading.Thread(target=first); thread.start()
        try:
            self.assertTrue(first_ready.wait(5))
            _,queue = generator.generate({"prompt":200,"cached":20,"responses":[response(180,8,40,2)]})
            drain(queue)
            values["second"] = handler.completion_usage_response(200,8,20)
            finish_first.set(); thread.join(5)
            self.assertEqual(errors,[]); self.assertFalse(thread.is_alive())
            self.assertEqual(values["first"]["usage"]["generation_tokens_per_second"],30)
            self.assertEqual(values["second"]["usage"]["generation_tokens_per_second"],2)
        finally:
            finish_first.set(); generator.pending.put(None); generator.worker.join(5)


class NativeConsumerTests(unittest.TestCase):
    def event(self):
        collector = native.NativeMetrics(); collector.observe(response())
        data = usage(); data.update(collector.usage(context(),data))
        return {"choices":[],"usage":data}

    def metrics(self,event):
        metrics = session_proxy.ResponseMetrics("chat-completions","text/event-stream","kolibri")
        metrics.feed(("data: "+json.dumps(event)+"\n\n").encode())
        return metrics

    def test_buffered_tool_chunk_uses_authoritative_native_rate(self):
        # Sixty decoded tokens took2s; a parser emitted the whole tool JSON
        # nearEOF. Visible-stream timing could report hundreds ofTPS.
        event = self.event()
        metrics = self.metrics(event)
        self.assertEqual(metrics.prompt_tokens,120); self.assertEqual(metrics.completion_tokens,60)
        self.assertEqual(metrics.runtime_stats["runtimeStatsSource"],"kolibri-native-stats")
        self.assertEqual(metrics.runtime_stats["runtimeTokensPerSecond"],30)
        self.assertEqual(metrics.runtime_stats["runtimeGenerationSeconds"],2)
        self.assertEqual(metrics.runtime_stats["runtimeDecodeTokenCount"],60)
        self.assertEqual(metrics.runtime_stats["runtimeThroughputBasis"],"request-native-generation")
        self.assertEqual(metrics.runtime_stats["promptProcessing"]["cachedTokens"],100)
        self.assertEqual(metrics.runtime_stats["promptProcessing"]["processedTokens"],20)

    def test_unversioned_mismatch_and_invalid_durations_fall_back_to_usage_only(self):
        for mutation in (lambda d:d["kolibri_native_stats"].update(version=True),
                         lambda d:d["kolibri_native_stats"].update(version=2),
                         lambda d:d["kolibri_native_stats"].update(generation_tokens=59),
                         lambda d:d["kolibri_native_stats"].update(processed_prompt_tokens=21),
                         lambda d:d["kolibri_native_stats"].update(prompt_tokens=True),
                         lambda d:d.update(generation_duration=0),
                         lambda d:d.update(generation_duration=float("inf")),
                         lambda d:d.update(generation_tokens_per_second=float("nan")),
                         lambda d:d.update(generation_tokens_per_second=999),
                         lambda d:d.pop("kolibri_native_stats")):
            event = self.event(); mutation(event["usage"])
            metrics = self.metrics(event)
            self.assertEqual(metrics.prompt_tokens,120); self.assertEqual(metrics.completion_tokens,60)
            self.assertNotIn("runtimeTokensPerSecond",metrics.runtime_stats)

    def test_changed_final_usage_cannot_keep_an_earlier_native_rate(self):
        metrics = self.metrics(self.event())
        final = {"choices":[],"usage":usage(completion=61)}
        metrics.feed(("data: "+json.dumps(final)+"\n\n").encode())
        self.assertEqual(metrics.completion_tokens,61)
        self.assertNotIn("runtimeTokensPerSecond",metrics.runtime_stats)
        self.assertNotIn("promptProcessing",metrics.runtime_stats)
        self.assertNotIn("runtimeDecodeTokenCount",metrics.runtime_stats)
        self.assertNotIn("runtimeThroughputBasis",metrics.runtime_stats)


if __name__ == "__main__":
    unittest.main()
