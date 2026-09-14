import ast
import asyncio
import gc
import json
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock
import weakref

from omlx_hub_runtime import install_dflash_sdpa256


GiB = 1024**3
NATIVE = (Path.home() / "Library/Application Support/LLM Launcher/runtimes/omlx-0.6.4"
          / "lib/python3.11/site-packages/omlx")


class DFlashSDPA256(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        sdpa = self.sdpa = ModuleType("fixture_sdpa256")
        sdpa._PATCHED = False
        sdpa._HEADROOM_PROVIDER = None
        sdpa._SDPA256_MIN_Q_LEN = 16
        sdpa._FORCE_TILED = None
        sdpa.apply_sdpa256_attention_patch = mock.Mock(
            side_effect=lambda: setattr(sdpa, "_PATCHED", True))
        sdpa.set_unfused_headroom_provider = lambda method: setattr(
            sdpa, "_HEADROOM_PROVIDER", weakref.WeakMethod(method))
        self.memory = {"active":24*GiB, "footprint":26*GiB, "hot":2*GiB}
        memory = self.memory

        class Guard:
            _memory_hard_limit_bytes = 40*GiB
            def record_mlx_active_memory(self, value):
                self.active = value
            def _current_usage_bytes(self):
                return max(self.active, memory["footprint"] - memory["hot"])

        class Engine:
            def __init__(self):
                self._loaded = False
                self._in_fallback_mode = False
                self._prefill_guard = None
                self.starting_headroom = None
                self.before_start = None
                self.before_stop = None
                self.before_fallback = None
            async def start(self):
                if self._loaded:
                    return
                assert sdpa._PATCHED, "patch must exist before model loading"
                self.starting_headroom = sdpa._HEADROOM_PROVIDER()()
                if self.before_start:
                    await self.before_start()
                self._prefill_guard = Guard()
                self._loaded = True
            async def stop(self):
                if self.before_stop:
                    self.before_stop()
                self._prefill_guard = None
                self._loaded = False
            async def _evict_dflash_and_start_fallback(self):
                if self.before_fallback:
                    self.before_fallback()
                self._in_fallback_mode = True

        self.Engine = Engine
        self.active_memory = mock.Mock(side_effect=lambda: self.memory["active"])

    def install(self):
        install_dflash_sdpa256(self.Engine, self.sdpa, self.active_memory)

    async def test_dflash_first_install_is_idempotent_and_headroom_is_live(self):
        self.install()
        wrapped = self.Engine.start
        self.install()
        self.assertIs(self.Engine.start, wrapped)
        self.sdpa.apply_sdpa256_attention_patch.assert_called_once_with()
        engine = self.Engine()
        await engine.start()
        self.assertEqual(engine.starting_headroom, -1)
        provider = self.sdpa._HEADROOM_PROVIDER()
        self.assertEqual(provider(), 12*GiB)
        self.memory["active"] = 35*GiB
        self.assertEqual(provider(), GiB)
        self.assertEqual(engine._prefill_guard._memory_hard_limit_bytes, 40*GiB)
        self.memory["active"] = 24*GiB
        engine._prefill_guard._memory_hard_limit_bytes = 30*GiB
        self.assertEqual(provider(), 3*GiB)
        engine._prefill_guard._memory_hard_limit_bytes = 0
        self.assertEqual(provider(), -1)
        await engine.stop()
        self.assertIsNone(self.sdpa._HEADROOM_PROVIDER)
        self.assertEqual(provider(), -1)  # A retained callback cannot use a stale guard.

    async def test_old_engine_stop_cannot_clear_new_engine_provider(self):
        self.install()
        old, current = self.Engine(), self.Engine()
        await old.start()
        old_read = self.sdpa._HEADROOM_PROVIDER()
        await current.start()
        current_read = self.sdpa._HEADROOM_PROVIDER()
        await old.stop()
        self.assertEqual(self.sdpa._HEADROOM_PROVIDER(), current_read)
        self.assertEqual(old_read(), -1)
        self.assertEqual(current_read(), 12*GiB)

    async def test_teardown_happens_before_native_cleanup_and_keeps_fallback_owner(self):
        self.install()
        engine = self.Engine()
        await engine.start()
        dflash_read = self.sdpa._HEADROOM_PROVIDER()

        class Scheduler:
            def headroom(self):
                return 1234
        scheduler = Scheduler()
        def begin_fallback():
            self.assertIsNone(self.sdpa._HEADROOM_PROVIDER)
            self.assertEqual(dflash_read(), -1)
            self.sdpa.set_unfused_headroom_provider(scheduler.headroom)
        engine.before_fallback = begin_fallback
        await engine._evict_dflash_and_start_fallback()
        await engine.stop()
        self.assertEqual(self.sdpa._HEADROOM_PROVIDER(), scheduler.headroom)

        fresh = self.Engine()
        await fresh.start()
        def broken_stop():
            self.assertIsNone(self.sdpa._HEADROOM_PROVIDER)
            raise RuntimeError("native cleanup failed")
        fresh.before_stop = broken_stop
        with self.assertRaisesRegex(RuntimeError, "native cleanup failed"):
            await fresh.stop()
        self.assertIsNone(self.sdpa._HEADROOM_PROVIDER)

    async def test_failed_or_cancelled_start_releases_only_its_own_provider(self):
        self.install()
        for failure in (RuntimeError("load failed"), asyncio.CancelledError()):
            with self.subTest(failure=type(failure).__name__):
                engine = self.Engine()
                async def fail():
                    raise failure
                engine.before_start = fail
                with self.assertRaises(type(failure)):
                    await engine.start()
                self.assertIsNone(self.sdpa._HEADROOM_PROVIDER)

        old, current = self.Engine(), self.Engine()
        async def replace_then_fail():
            await current.start()
            raise RuntimeError("old load failed")
        old.before_start = replace_then_fail
        with self.assertRaises(RuntimeError):
            await old.start()
        self.assertIs(self.sdpa._HEADROOM_PROVIDER().__self__.engine(), current)

    async def test_provider_does_not_keep_an_abandoned_engine_alive(self):
        self.install()
        engine = self.Engine()
        await engine.start()
        read = self.sdpa._HEADROOM_PROVIDER()
        reference = weakref.ref(engine)
        del engine
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(read(), -1)

    def test_changed_or_failed_upstream_interface_fails_before_lifecycle_mutation(self):
        original = self.Engine.start
        self.sdpa._SDPA256_MIN_Q_LEN = 4
        with self.assertRaisesRegex(RuntimeError, "interface changed"):
            self.install()
        self.assertIs(self.Engine.start, original)
        self.sdpa.apply_sdpa256_attention_patch.assert_not_called()
        self.sdpa._SDPA256_MIN_Q_LEN = 16
        self.sdpa.apply_sdpa256_attention_patch.side_effect = None
        with self.assertRaisesRegex(RuntimeError, "could not be installed"):
            self.install()
        self.assertIs(self.Engine.start, original)

    @unittest.skipUnless((NATIVE / "patches/sdpa256_attention.py").exists(), "installed oMLX 0.6.4 required")
    async def test_installed_native_routing_remains_adaptive_and_excludes_block_four(self):
        # Execute the installed pure routing functions, without importing MLX,
        # allocating arrays or loading models. Do not reproduce their logic.
        sdpa = self.sdpa
        class Array:
            def __init__(self, shape):
                self.shape = shape
                self.dtype = SimpleNamespace(size=2)
        sdpa.mx = SimpleNamespace(array=Array, bool_="bool")
        sdpa.logger = mock.Mock()
        sdpa._note_tiled_route = mock.Mock()
        sdpa._SDPA_FALLBACK_SCORE_DTYPE_SIZE = 4
        for path, names in (
            (NATIVE / "memory_monitor.py", {"estimate_unfused_sdpa_call_bytes"}),
            (NATIVE / "patches/sdpa256_attention.py", {
                "HEAD_DIM", "_SDPA256_MIN_KV_LEN", "_SDPA256_MIN_Q_LEN",
                "_should_route", "_tiled_route_required"}),
        ):
            nodes = [node for node in ast.parse(path.read_text()).body
                     if (isinstance(node, ast.FunctionDef) and node.name in names)
                     or (isinstance(node, ast.Assign) and any(
                         isinstance(target, ast.Name) and target.id in names for target in node.targets))]
            exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), sdpa.__dict__)
        self.install()
        engine = self.Engine()
        await engine.start()
        keys = Array((1, 4, 16384, 256))
        prompt = Array((1, 24, 2048, 256))
        self.assertFalse(sdpa._should_route(prompt, keys, None, "causal", None))
        self.memory["active"] = 35*GiB + GiB//2
        self.assertTrue(sdpa._should_route(prompt, keys, None, "causal", None))
        self.active_memory.reset_mock()
        for query_length in (1, 4, 15):
            self.assertFalse(sdpa._should_route(Array((1, 24, query_length, 256)), keys, None, "causal", None))
        self.active_memory.assert_not_called()
        # DFlash's per-head GQA path can fold block4 into 6*4 query rows.
        # This crosses the shape gate but its tiny transient still fits,
        # even at the same headroom that requires tiling the real prefill.
        self.assertFalse(sdpa._should_route(
            Array((1, 1, 24, 256)), Array((1, 1, 32768, 256)), None, "causal", None))
        self.assertFalse(sdpa._should_route(prompt, Array((1, 4, 4096, 256)), None, "causal", None))
        self.assertFalse(sdpa._should_route(prompt, keys, SimpleNamespace(bits=8), "causal", None))
        self.memory["active"] = 24*GiB
        self.assertFalse(sdpa._should_route(prompt, keys, None, "causal", None))
        self.assertIsNone(sdpa._FORCE_TILED)


@unittest.skipUnless(os.environ.get("LLM_LAUNCHER_OMLX_NATIVE") == "1", "opt-in native MLX operators")
class NativeSDPA256Integration(unittest.IsolatedAsyncioTestCase):
    async def test_real_attention_routing_without_model_weights(self):
        from importlib.metadata import version
        self.assertEqual(version("omlx"), "0.6.4")
        import mlx.core as mx
        from mlx_lm.models import base
        from omlx.engine.dflash import DFlashEngine, _DFlashPrefillGuard
        from omlx.memory_monitor import MemoryMonitor
        from omlx.patches import sdpa256_attention as sdpa

        self.assertFalse(sdpa._PATCHED, "Run this check in a fresh runtime process")
        self.assertIsNone(sdpa._FORCE_TILED)
        stock_sdpa = base.scaled_dot_product_attention
        guard = _DFlashPrefillGuard(MemoryMonitor(max_kv_cache_memory=None, eviction_enabled=False), 2048)
        guard._memory_hard_limit_bytes = 40*GiB
        headroom = {"bytes":GiB}

        async def load_fixture(engine):
            self.assertEqual(sdpa._HEADROOM_PROVIDER()(), -1)
            engine._prefill_guard = guard
            engine._loaded = True
        async def unload_fixture(engine):
            self.assertIsNone(sdpa._HEADROOM_PROVIDER)
            engine._prefill_guard = None
            engine._loaded = False

        # No DFlash start()/model loader executes. Only attention operators use
        # the GPU; virtual pressure selects both routes without filling RAM.
        with mock.patch.object(DFlashEngine, "start", load_fixture), \
             mock.patch.object(DFlashEngine, "stop", unload_fixture), \
             mock.patch.object(guard, "_current_usage_bytes", side_effect=lambda:
                 int(40*GiB*.90) - headroom["bytes"]):
            install_dflash_sdpa256(DFlashEngine, sdpa, mx.get_active_memory)
            self.assertIsNone(sdpa._FORCE_TILED)
            engine = DFlashEngine(model_name="/fixture/no-weights", draft_model_path="/fixture/no-weights")
            await engine.start()
            read = sdpa._HEADROOM_PROVIDER()
            errors = {}
            try:
                mx.random.seed(17)
                def arrays(query_shape, key_shape):
                    return tuple(mx.random.normal(shape).astype(mx.float16)
                                 for shape in (query_shape, key_shape, key_shape))
                def attention(function, tensors):
                    result = function(*tensors, cache=None, scale=1/16, mask="causal")
                    mx.eval(result)
                    self.assertTrue(mx.all(mx.isfinite(result)).item())
                    return result
                def check_close(name, actual, reference):
                    errors[name] = float(mx.max(mx.abs(actual.astype(mx.float32) - reference.astype(mx.float32))).item())
                    self.assertTrue(mx.allclose(actual, reference, atol=.02, rtol=.03).item(), errors[name])

                prompt = arrays((1, 24, 128, 256), (1, 4, 8192, 256))
                reference = attention(stock_sdpa, prompt)
                with mock.patch.object(sdpa, "_flash_sdpa256", wraps=sdpa._flash_sdpa256) as tiled:
                    check_close("unfused", attention(base.scaled_dot_product_attention, prompt), reference)
                    tiled.assert_not_called()
                    headroom["bytes"] = 2*1024**2
                    check_close("tiled", attention(base.scaled_dot_product_attention, prompt), reference)
                    tiled.assert_called_once()

                    # Actual per-head grouped shape for Qwen's 24/4 GQA.
                    folded = arrays((1, 1, 24, 256), (1, 1, 16384, 256))
                    check_close("foldedBlock4", attention(base.scaled_dot_product_attention, folded), attention(stock_sdpa, folded))
                    self.assertEqual(tiled.call_count, 1)
                    headroom["bytes"] = 0
                    decode = arrays((1, 24, 4, 256), (1, 4, 8192, 256))
                    check_close("block4", attention(base.scaled_dot_product_attention, decode), attention(stock_sdpa, decode))
                    self.assertEqual(tiled.call_count, 1)
                    self.assertEqual(guard._memory_hard_limit_bytes, 40*GiB)
            finally:
                await engine.stop()
            self.assertEqual(read(), -1)
            self.assertIsNone(sdpa._HEADROOM_PROVIDER)
            print(json.dumps({"runtime":"0.6.4", "weightsLoaded":False,
                "adaptiveRouting":True, "block4FastPath":True, "providerDetached":True,
                "maxAbsErrors":errors}, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
