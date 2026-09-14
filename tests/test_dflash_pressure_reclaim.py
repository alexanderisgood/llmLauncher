import ast
import asyncio
from dataclasses import dataclass
import inspect
import logging
import os
from pathlib import Path
import threading
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from omlx_hub_runtime import PrefillWriter, install_dflash_pressure_reclaim


GiB = 1024**3
VERSIONS = ("0.6.4", "0.1.10+omlx.7")
NATIVE = (Path.home() / "Library/Application Support/LLM Launcher/runtimes/omlx-0.6.4"
          / "lib/python3.11/site-packages")


@dataclass(frozen=True)
class Token:
    token_id: int = 17
    generated_tokens: int = 1
    fallback_ar: bool = False


class Iterator:
    def __init__(self, values):
        self.values = iter(values)
        self.closed = 0
    def __iter__(self):
        return self
    def __next__(self):
        return next(self.values)
    def close(self):
        self.closed += 1


class PressureReclaimTests(unittest.TestCase):
    def setUp(self):
        class Guard:
            _prefill_memory_guard = True
            _memory_hard_limit_bytes = 40 * GiB
            def record_mlx_active_memory(self, active):
                self.active = active
            def preflight_or_raise(self, **kwargs):
                return kwargs

        class Engine:
            def __init__(self):
                self._loaded = True
                self._in_fallback_mode = False
                self._prefill_guard = Guard()
                self._runtime_context = SimpleNamespace(
                    runtime=SimpleNamespace(clear_cache_boundaries=True))
                self.source = Iterator([Token(), Token(generated_tokens=2)])
                self.flow, self.stops = object(), {2}
            def _stream_dflash_events(self, prompt_tokens, max_tokens, logits_processor_factory=None):
                self.factory = logits_processor_factory
                return self.source, self.flow, self.stops

        class Enforcer:
            _POOL_RECLAIM_FLOOR = 2 * GiB
            def _request_scheduler_cache_reclaim(self, freed_hot):
                pass

        self.Guard, self.Engine, self.Enforcer = Guard, Engine, Enforcer
        self.calls = []
        self.pool = 3 * GiB
        def record(name, result=None):
            def call():
                self.calls.append((name, threading.get_ident()))
                return result() if callable(result) else result
            return call
        self.mx = SimpleNamespace(
            get_cache_memory=mock.Mock(side_effect=record("pool", lambda: self.pool)),
            synchronize=mock.Mock(side_effect=record("sync")),
            clear_cache=mock.Mock(side_effect=record("clear")),
            get_active_memory=mock.Mock(side_effect=record("active", 27 * GiB)),
        )

    def install(self, **kwargs):
        install_dflash_pressure_reclaim(self.Engine, self.Guard, Token,
            self.Enforcer, self.mx, versions=kwargs.get("versions", VERSIONS))

    def stream(self, engine):
        stream, flow, stops = engine._stream_dflash_events([1], 10)
        self.assertIs(flow, engine.flow)
        self.assertIs(stops, engine.stops)
        return stream

    def test_prefill_boundary_consumes_pressure_signal_before_decode(self):
        @dataclass(frozen=True)
        class Prefill:
            tokens_processed: int = 128
            tokens_total: int = 125000
        install_dflash_pressure_reclaim(self.Engine, self.Guard, Token,
            self.Enforcer, self.mx, versions=VERSIONS, prefill_type=Prefill)
        engine = self.Engine()
        event = Prefill()
        engine.source = Iterator([event])
        engine._prefill_guard.request_pressure_reclaim()
        self.assertIs(next(self.stream(engine)), event)
        self.mx.clear_cache.assert_called_once()
        self.assertEqual(engine._prefill_guard._launcher_pressure_reclaim_consumed, 1)

    def test_monitor_only_signals_and_executor_clears_once_without_changing_events(self):
        self.install()
        engine = self.Engine()
        first, second = Token(), Token(generated_tokens=2)
        marker = object()
        engine.source = Iterator([marker, first, second])
        thread = threading.Thread(target=engine._prefill_guard.request_pressure_reclaim)
        thread.start(); thread.join()
        self.assertEqual(self.calls, [])
        stream = self.stream(engine)
        self.assertIs(next(stream), marker)
        self.assertEqual(self.calls, [])
        self.assertIs(next(stream), first)
        self.assertEqual([name for name, _ in self.calls], ["pool", "sync", "clear", "active", "pool"])
        self.assertEqual({tid for _, tid in self.calls}, {threading.get_ident()})
        self.assertIs(next(stream), second)
        self.mx.clear_cache.assert_called_once()
        self.assertEqual(engine._prefill_guard.active, 27 * GiB)
        self.assertEqual(engine._prefill_guard._memory_hard_limit_bytes, 40 * GiB)
        with self.assertRaises(StopIteration):
            next(stream)
        stream.close()
        self.assertEqual(engine.source.closed, 1)

    def test_ordinary_generation_and_already_drained_pool_do_not_synchronize(self):
        self.install()
        engine = self.Engine()
        self.assertEqual(len(list(self.stream(engine))), 2)
        self.assertEqual(self.calls, [])
        engine.source = Iterator([Token()])
        engine._prefill_guard.request_pressure_reclaim()
        self.pool = 0
        list(self.stream(engine))
        self.mx.synchronize.assert_not_called()
        self.assertEqual([name for name, _ in self.calls], ["pool"])

    def test_disabled_guard_fallback_and_disabled_native_clears_are_noops(self):
        self.install()
        for option in ("guard", "limit", "fallback", "clear", "ar"):
            with self.subTest(option=option):
                engine = self.Engine()
                if option == "guard": engine._prefill_guard._prefill_memory_guard = False
                if option == "limit": engine._prefill_guard._memory_hard_limit_bytes = 0
                if option == "fallback": engine._in_fallback_mode = True
                if option == "clear": engine._runtime_context.runtime.clear_cache_boundaries = False
                if option == "ar": engine.source = Iterator([Token(fallback_ar=True)])
                engine._prefill_guard.request_pressure_reclaim()
                list(self.stream(engine))
        self.assertEqual(self.calls, [])

    def test_engine_ownership_replacement_stop_and_cross_thread_never_touch_mlx(self):
        self.install()
        old, other = self.Engine(), self.Engine()
        old._prefill_guard.request_pressure_reclaim()
        list(self.stream(other))
        self.assertEqual(self.calls, [])
        for lifecycle in ("replace", "stop", "cleared_runtime", "fallback", "thread"):
            with self.subTest(lifecycle=lifecycle):
                engine = self.Engine()
                stream = self.stream(engine)
                engine._prefill_guard.request_pressure_reclaim()
                if lifecycle == "replace": engine._prefill_guard = self.Guard()
                if lifecycle == "stop": engine._loaded = False
                if lifecycle == "cleared_runtime": engine._runtime_context = None
                if lifecycle == "fallback": engine._in_fallback_mode = True
                if lifecycle == "thread":
                    thread = threading.Thread(target=lambda: list(stream))
                    thread.start(); thread.join()
                else:
                    list(stream)
        self.assertEqual(self.calls, [])

    def test_new_request_during_sync_survives_and_multiple_queued_requests_coalesce(self):
        self.install()
        engine = self.Engine()
        guard = engine._prefill_guard
        guard.request_pressure_reclaim(); guard.request_pressure_reclaim()
        self.mx.synchronize.side_effect = guard.request_pressure_reclaim
        stream = self.stream(engine)
        next(stream)
        self.mx.clear_cache.assert_called_once()
        self.mx.synchronize.side_effect = None
        next(stream)
        self.assertEqual(self.mx.clear_cache.call_count, 2)
        self.assertEqual(guard._launcher_pressure_reclaim_requested,
                         guard._launcher_pressure_reclaim_consumed)
        stream.close()

    def test_close_before_first_event_and_cancel_close_native_iterator_once(self):
        self.install()
        for started in (False, True):
            engine = self.Engine()
            stream = self.stream(engine)
            if started: next(stream)
            stream.close(); stream.close()
            self.assertEqual(engine.source.closed, 1)
            with self.assertRaises(StopIteration): next(stream)
        self.assertEqual(self.calls, [])

    def test_native_and_reclaim_errors_close_iterator_and_preserve_original_error(self):
        self.install()
        for where in ("native", "reclaim"):
            with self.subTest(where=where):
                engine = self.Engine()
                if where == "native":
                    def fail():
                        raise ValueError("native failure")
                        yield
                    engine.source = Iterator(fail())
                else:
                    engine._prefill_guard.request_pressure_reclaim()
                    self.mx.synchronize.side_effect = ValueError("reclaim failure")
                close = engine.source.close
                def broken_close():
                    close()
                    raise RuntimeError("cleanup failure")
                engine.source.close = broken_close
                with self.assertRaisesRegex(ValueError, where + " failure"):
                    next(self.stream(engine))
                self.assertEqual(engine.source.closed, 1)

    def test_versions_interfaces_and_existing_native_hook_fail_before_mutation(self):
        original = self.Engine._stream_dflash_events
        for versions in (("0.6.5", VERSIONS[1]), (VERSIONS[0], "0.1.11")):
            with self.assertRaisesRegex(RuntimeError, "interface changed"):
                self.install(versions=versions)
        self.assertFalse(hasattr(self.Guard, "request_pressure_reclaim"))
        self.assertIs(self.Engine._stream_dflash_events, original)
        self.Guard.request_pressure_reclaim = lambda _: None
        with self.assertRaisesRegex(RuntimeError, "interface changed"):
            self.install()
        del self.Guard.request_pressure_reclaim
        self.install()
        installed = self.Engine._stream_dflash_events
        self.install()
        self.assertIs(self.Engine._stream_dflash_events, installed)

    def test_thinking_budget_and_scoped_prefill_observer_keep_signature_and_ownership(self):
        from dflash_thinking_budget import install_dflash_thinking_budget
        async def generate(engine, **kwargs):
            stream, flow, stops = engine._stream_dflash_events(
                [1], 10, logits_processor_factory=kwargs.get("logits_processor_factory"))
            return list(stream), flow, stops
        async def stream_generate(engine, **kwargs):
            for event in (await generate(engine, **kwargs))[0]:
                yield event
        self.Engine.generate, self.Engine.stream_generate = generate, stream_generate
        self.install()
        install_dflash_thinking_budget(self.Engine)
        self.assertIn("logits_processor_factory",
                      inspect.signature(self.Engine._stream_dflash_events).parameters)
        engine = self.Engine()
        original = engine._stream_dflash_events
        with tempfile.TemporaryDirectory() as directory:
            writer = PrefillWriter(Path(directory) / "stats.json", "test-response")
            def observed_events(*args, **kwargs):
                iterator, flow, stops = original(*args, **kwargs)
                return writer.events(iterator), flow, stops
            engine._stream_dflash_events = observed_events
            engine._prefill_guard.request_pressure_reclaim()
            values, flow, stops = asyncio.run(engine.generate(thinking_budget=4096))
            self.assertEqual(values, [Token(), Token(generated_tokens=2)])
            self.assertIs(flow, engine.flow)
            self.assertIs(stops, engine.stops)
            self.assertTrue(callable(engine.factory))
            self.assertEqual(engine.source.closed, 1)
            self.mx.clear_cache.assert_called_once()
            engine._stream_dflash_events = original
            self.assertIn("logits_processor_factory", inspect.signature(original).parameters)

    @unittest.skipUnless((NATIVE / "omlx/process_memory_enforcer.py").exists(), "native source unavailable")
    def test_actual_native_enforcer_contract_requests_only_reclaimable_pool(self):
        # Run the installed pure signalling methods, with no native imports or
        # MLX allocation. This checks the real producer of the new guard signal.
        tree = ast.parse((NATIVE / "omlx/process_memory_enforcer.py").read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                   and n.name == "ProcessMemoryEnforcer")
        names = {"_resolve_scheduler", "_pool_bytes", "_request_scheduler_cache_reclaim"}
        cls.body = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
        module = ast.Module(body=[cls], type_ignores=[])
        namespace = {"Any": object, "mx": self.mx, "logger": logging.getLogger(__name__),
                     "_format_gb": str}
        exec(compile(ast.fix_missing_locations(module), "native_enforcer_contract", "exec"), namespace)
        enforcer_type = namespace["ProcessMemoryEnforcer"]
        enforcer_type._POOL_RECLAIM_FLOOR = 2 * GiB
        self.install()
        engine = self.Engine()
        enforcer = enforcer_type()
        enforcer._engine_pool = SimpleNamespace(_entries={"qwen": SimpleNamespace(engine=engine)})
        self.pool = 2 * GiB
        self.assertEqual(enforcer._request_scheduler_cache_reclaim(0), 0)
        self.pool += 1
        self.assertEqual(enforcer._request_scheduler_cache_reclaim(0), 1)
        self.mx.synchronize.assert_not_called()
        list(self.stream(engine))
        self.mx.clear_cache.assert_called_once()

    @unittest.skipUnless(os.environ.get("LLM_LAUNCHER_OMLX_NATIVE") == "1", "opt-in native arrays")
    def test_native_arrays_and_pending_draft_survive_reclaim_without_model_load(self):
        from importlib.metadata import version
        import mlx.core as mx
        from mlx_lm.models.cache import KVCache
        from omlx.engine.dflash import DFlashEngine, _DFlashPrefillGuard
        from omlx.process_memory_enforcer import ProcessMemoryEnforcer
        from dflash_mlx.engine.events import TokenEvent

        class Engine(DFlashEngine):
            def _stream_dflash_events(self, prompt_tokens, max_tokens):
                return self.source, None, set()

        guard = _DFlashPrefillGuard(object(), 2048)
        guard._prefill_memory_guard = True
        guard._memory_hard_limit_bytes = 40 * GiB
        engine = Engine.__new__(Engine)
        engine._prefill_guard = guard
        engine._loaded = True
        engine._in_fallback_mode = False
        engine._runtime_context = SimpleNamespace(runtime=SimpleNamespace(clear_cache_boundaries=True))
        install_dflash_pressure_reclaim(Engine, _DFlashPrefillGuard, TokenEvent,
            ProcessMemoryEnforcer, mx, versions=(version("omlx"), version("dflash-mlx")))
        cache = KVCache()
        keys = mx.arange(256, dtype=mx.float32).reshape(1, 1, 16, 16)
        values = keys + 1
        cache.update_and_fetch(keys, values)
        recurrent = mx.arange(128, dtype=mx.float32)
        snapshot = (cache.keys, cache.values, recurrent)
        mx.eval(*snapshot)
        scratch = mx.ones((1024, 1024), dtype=mx.float32)
        mx.eval(scratch)
        del scratch  # Leave a reclaimable buffer in this test process only.
        draft = mx.arange(256, dtype=mx.float32).reshape(16, 16)
        pending = draft @ draft.T
        mx.async_eval(pending)  # Matches the native next-draft prefetch lifetime.
        event = TokenEvent(token_id=17, generated_tokens=1, acceptance_ratio=.5, cycles_completed=1)
        engine.source = Iterator([event])
        guard.request_pressure_reclaim()
        stream, _, _ = engine._stream_dflash_events([1], 10)
        self.assertIs(next(stream), event)
        self.assertTrue(mx.array_equal(cache.keys[:, :, :16, :], keys).item())
        self.assertTrue(mx.array_equal(cache.values[:, :, :16, :], values).item())
        self.assertTrue(mx.array_equal(recurrent, mx.arange(128, dtype=mx.float32)).item())
        self.assertTrue(mx.array_equal(pending, draft @ draft.T).item())
        self.assertIs(snapshot[0], cache.keys)
        self.assertIs(snapshot[1], cache.values)
        self.assertEqual(guard._memory_hard_limit_bytes, 40 * GiB)
        self.assertGreater(guard._last_mlx_active_memory_bytes, 0)
        stream.close()
        self.assertEqual(engine.source.closed, 1)


if __name__ == "__main__":
    unittest.main()
