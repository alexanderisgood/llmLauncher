import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from omlx_admission import install_prefill_reclaim


class AdmissionReclaim(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.addCleanup(self.executor.shutdown, wait=True)
        self.pool, self.usage, self.limit = 5, 30, 33
        self.main_thread = threading.get_ident()
        self.threads = []
        class Refused(Exception): pass
        self.Refused = Refused
        class Guard:
            _prefill_memory_guard = True
            _memory_hard_limit_bytes = 33
            def record_mlx_active_memory(inner, usage): inner.usage = usage
        self.Guard = Guard
        fixture = self
        class Engine:
            _loaded = True
            _in_fallback_mode = False
            _active_request = False
            def __init__(inner): inner._prefill_guard = Guard(); inner.calls = []
            async def preflight_chat(inner, *, num_prompt_tokens, request_id=None):
                inner.calls.append((num_prompt_tokens, request_id))
                if fixture.usage + num_prompt_tokens > inner._prefill_guard._memory_hard_limit_bytes:
                    raise Refused('admission rejected')
                return 'allowed'
            preflight_completion = preflight_chat
        def clear():
            self.threads.append(threading.get_ident())
            self.usage -= self.pool; self.pool = 0
        self.mx = SimpleNamespace(get_active_memory=lambda:self.usage, get_cache_memory=lambda:self.pool,
                                  synchronize=Mock(), clear_cache=Mock(side_effect=clear))
        install_prefill_reclaim(Engine, Guard, Refused, self.mx, lambda:self.executor,
                               versions=('0.6.4','0.1.10+omlx.7'))
        self.engine = Engine()

    async def test_unused_pool_reclaimed_on_executor_then_same_admission_rechecked(self):
        result = await self.engine.preflight_chat(num_prompt_tokens=4, request_id='same')
        self.assertEqual(result, 'allowed')
        self.assertEqual(self.engine.calls, [(4,'same'),(4,'same')])
        self.assertNotEqual(self.threads[0], self.main_thread)
        self.assertEqual(self.engine._prefill_guard._memory_hard_limit_bytes,33)
        self.mx.clear_cache.assert_called_once()

    async def test_true_overflow_remains_rejected_with_no_retry_loop(self):
        with self.assertRaises(self.Refused):
            await self.engine.preflight_completion(num_prompt_tokens=20)
        self.assertEqual(len(self.engine.calls),2)
        self.mx.clear_cache.assert_called_once()

    async def test_requests_that_fit_do_not_clear_allocator(self):
        await self.engine.preflight_chat(num_prompt_tokens=2)
        self.mx.clear_cache.assert_not_called()
        self.assertEqual(len(self.engine.calls),1)

    async def test_lower_limit_after_cleanup_is_used(self):
        self.mx.synchronize.side_effect=lambda:setattr(self.engine._prefill_guard,'_memory_hard_limit_bytes',20)
        with self.assertRaises(self.Refused):await self.engine.preflight_chat(num_prompt_tokens=4)
        self.assertEqual(self.engine._prefill_guard._memory_hard_limit_bytes,20)

    async def test_busy_or_fallback_engine_never_reclaimed(self):
        for name in ('_active_request','_in_fallback_mode'):
            setattr(self.engine,name,True)
            with self.assertRaises(self.Refused):await self.engine.preflight_chat(num_prompt_tokens=4)
            setattr(self.engine,name,False)
        self.mx.clear_cache.assert_not_called()

    async def test_cancel_while_queued_prevents_late_cleanup(self):
        release=threading.Event()
        future=self.executor.submit(release.wait)
        try:
            task=asyncio.create_task(self.engine.preflight_chat(num_prompt_tokens=4))
            await asyncio.sleep(.01)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
        finally:release.set()
        await asyncio.wrap_future(future)
        await asyncio.get_running_loop().run_in_executor(self.executor, lambda:None)
        self.mx.clear_cache.assert_not_called()

    async def test_engine_replaced_while_waiting_does_not_recheck(self):
        release=threading.Event();future=self.executor.submit(release.wait)
        try:
            task=asyncio.create_task(self.engine.preflight_chat(num_prompt_tokens=4))
            await asyncio.sleep(.01)
            self.engine._prefill_guard=self.Guard()
        finally:release.set()
        await asyncio.wrap_future(future)
        with self.assertRaises(self.Refused):await task
        self.mx.clear_cache.assert_not_called()
        self.assertEqual(len(self.engine.calls),1)

    async def test_cleanup_failure_preserves_admission_error(self):
        self.mx.synchronize.side_effect=RuntimeError('device unavailable')
        with self.assertLogs('omlx_admission',level='WARNING'):
            with self.assertRaises(self.Refused):await self.engine.preflight_chat(num_prompt_tokens=4)
        self.assertEqual(len(self.engine.calls),1)

if __name__=='__main__':unittest.main()
