"""Native, model-free regressions; run with the selected MTPLX Python."""
import gc
import os
import sqlite3
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
from unittest import mock
import weakref

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mtplx_hub_runtime as adapter

try:
    from importlib.metadata import version
    import mlx.core as mx
    import mtplx.generation as generation
    import mtplx.server.openai as server
    from mtplx.session_bank import SessionBank
    from mtplx.cache_bank.cold_tier import SessionBankColdTier
    from mtplx.cache_bank.codec import ColdEncodeInterrupted
    from mtplx.cache_state import snapshot_cache
    from mlx_lm.models.cache import KVCache
    NATIVE = version('mtplx') == '2.11.2'
except (ImportError, OSError):
    NATIVE = False

GIB = adapter.GIB

class ChunkPolicyTests(unittest.TestCase):
    def test_workspace_controls_chunk_size(self):
        for active, expected in [(20,512),(31,256),(35,128),(41,128)]:
            self.assertEqual(adapter.prefill_chunk_size(active*GIB,40*GIB),expected)
        self.assertEqual(adapter.prefill_chunk_size(0,40*GIB,64),64)

    def test_database_transaction_closes_on_success_and_failure(self):
        for fail in [False,True]:
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as directory:
                path=str(Path(directory)/'test.sqlite')
                connection=sqlite3.connect(path)
                connection.execute('create table records (value integer)')
                try:
                    with adapter.closing_transaction(connection) as conn:
                        conn.execute('insert into records values (1)')
                        if fail:raise ValueError('rollback')
                except ValueError:
                    pass
                with self.assertRaises(sqlite3.ProgrammingError):
                    connection.execute('select 1')
                with adapter.closing_transaction(sqlite3.connect(path)) as conn:
                    self.assertEqual(conn.execute('select count(*) from records').fetchone()[0],0 if fail else 1)

@unittest.skipUnless(NATIVE, 'requires the audited MTPLX runtime and Metal access')
class NativeMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with mock.patch.dict(os.environ, {'MTPLX_MEMORY_LIMIT_BYTES':str(40*GIB)}):
            adapter.install(server,generation,SessionBank,SessionBankColdTier,mx,version='2.11.2')

    def cache(self):
        cache=KVCache()
        values=mx.arange(16).reshape(1,1,4,4).astype(mx.float16)
        cache.update_and_fetch(values,values+1)
        mx.eval(cache.state)
        return [cache]

    def put(self, bank, *, nbytes=1024, tokens=(1,2,3,4)):
        runtime=NS(model_path='/test/qwen',mtp_enabled=True,make_cache=lambda:[KVCache()],make_mtp_cache=lambda:[KVCache()])
        cache=self.cache()
        mtp=self.cache()
        entry=bank.put(runtime=runtime,token_ids=list(tokens),cache=cache,logits=mx.array([1.0]),hidden=mx.array([2.0]),
            keep_live_ref=True,session_id='test',nbytes_override=nbytes,
            mtp_history_cache_ref=mtp,mtp_history_snapshot=snapshot_cache(mtp),snapshot_epoch=4,mtp_snapshot_epoch=4)
        return runtime,entry

    def test_install_rejects_unaudited_runtime(self):
        with self.assertRaisesRegex(RuntimeError,'audited'):
            adapter.install(server,generation,SessionBank,SessionBankColdTier,mx,version='2.11.3')

    def test_prefill_boundaries_cover_every_token_once(self):
        for active,cap in [(20,512),(31,256),(35,128)]:
            with mock.patch.object(mx,'get_active_memory',return_value=active*GIB):
                spans=generation._iter_prefill_chunk_spans(4103,mandatory_edges=(1,511,600,4097),chunk_size=2048)
            self.assertIsInstance(spans,list)
            self.assertEqual([n for start,end in spans for n in range(start,end)],list(range(4103)))
            self.assertTrue(all(end-start<=cap for start,end in spans))
            self.assertTrue({1,511,600,4097}.issubset({end for _,end in spans}))

    def test_bank_absolute_cap_preserves_dynamic_reclamation(self):
        bank=SessionBank(max_bytes=20*GIB,per_session_max_bytes=16*GIB)
        self.assertEqual(bank.max_bytes,12*GIB)
        self.assertEqual(bank.per_session_max_bytes,12*GIB)
        bank.dynamic_ceiling_fn=lambda:7*GIB
        self.assertEqual(bank.effective_max_bytes(),7*GIB)

    def test_nine_gib_snapshot_keeps_clone_and_warm_lease(self):
        for mode in ['clone','reference']:
            bank=SessionBank(max_bytes=12*GIB,per_session_max_bytes=12*GIB)
            runtime,entry=self.put(bank,nbytes=9*GIB)
            self.assertFalse(entry.live_ref_only)
            restored=bank.restore(runtime,[1,2,3,4,5],mode=mode,session_id='test')
            self.assertIsNotNone(restored)
            self.assertEqual(restored.cache[0].offset,4)
            self.assertEqual(restored.cache[0].state[0].tolist(),self.cache()[0].state[0].tolist())
            self.assertIsNotNone(restored.mtp_history_cache)

    def test_periodic_checkpoint_does_not_write_every_tool_turn(self):
        cold=NS(put_entry=mock.Mock(return_value=True),spill_entry=mock.Mock(return_value=True),spill_threshold_bytes=4*GIB)
        bank=SessionBank(cold_tier=cold,max_bytes=12*GIB,per_session_max_bytes=12*GIB)
        jobs=[]
        bank.cold_enqueue_dispatch=jobs.append
        with mock.patch.object(mx,'get_active_memory',return_value=20*GIB):
            self.put(bank,nbytes=4*GIB)
            self.put(bank,nbytes=4*GIB,tokens=(1,2,3,4,5))
        cold.spill_entry.assert_called_once()
        self.assertTrue(jobs, 'normal idle persistence should remain available')

    def test_eviction_releases_queued_snapshot_and_settle(self):
        cold=NS(put_entry=mock.Mock(return_value=True))
        bank=SessionBank(cold_tier=cold)
        jobs=[]
        bank.cold_enqueue_dispatch=jobs.append
        with mock.patch.dict(os.environ,{'MTPLX_SESSION_SNAPSHOT_SETTLE':'1'}):
            _,entry=self.put(bank)
        ref=weakref.ref(entry)
        self.assertGreaterEqual(len(jobs),2)
        bank.clear()
        del entry
        gc.collect()
        self.assertIsNone(ref(), 'queued work retained an evicted snapshot')
        for job in jobs:
            job()
        cold.put_entry.assert_not_called()

    def test_yielded_write_retry_does_not_retain_snapshot(self):
        cold=NS(put_entry=mock.Mock(side_effect=ColdEncodeInterrupted()))
        bank=SessionBank(cold_tier=cold)
        jobs=[]
        bank.cold_enqueue_dispatch=jobs.append
        _,entry=self.put(bank)
        jobs.pop()()
        self.assertTrue(jobs)
        ref=weakref.ref(entry)
        # Mock call history intentionally owns its arguments, unlike the real tier.
        cold.put_entry.reset_mock()
        cold.put_entry.side_effect=None
        bank.clear()
        del entry
        gc.collect()
        self.assertIsNone(ref())
        for job in jobs:
            job()
        cold.put_entry.assert_not_called()

    def test_warm_short_suffix_reserves_full_precision_workspace(self):
        stats={'active_memory_bytes':35*GIB,'cache_memory_bytes':0}
        entry=NS(token_ids=tuple(range(100000)))
        bank=NS(longest_prefix=lambda ids:entry,total_nbytes=9*GIB,
            touch_sessions=mock.Mock(),shrink_to_bytes=mock.Mock(return_value=0))
        state=NS(metal_memory_caps={'memory_limit_bytes':40*GIB},allow_swap=False,
            memory_plan=NS(kv_bytes_per_token=65536,kv_bytes_per_token_effective=19660),sessions=None)
        env=server._prefill_admission_shed.__globals__
        with mock.patch.dict(env,{'_mlx_memory_stats_live':lambda:stats,'_record_guard_event':mock.Mock()}), mock.patch.object(mx,'clear_cache'), mock.patch('builtins.print'):
            result=server._prefill_admission_shed(state,prompt_ids=list(range(100113)),session_bank=bank,session_id='test')
        self.assertIsNotNone(result)
        self.assertEqual(result['miss_tokens'],113)
        self.assertTrue(result['refused'])
        self.assertEqual(result['projected_bytes_after'],35*GIB+100113*65536+3*GIB)
        bank.touch_sessions.assert_called_once()

    def test_compaction_sheds_old_snapshot_before_prefill(self):
        stats={'active_memory_bytes':35*GIB,'cache_memory_bytes':0}
        bank=NS(longest_prefix=lambda ids:None,total_nbytes=9*GIB,shrink_to_bytes=mock.Mock(return_value=0))
        def clear(**kwargs):
            stats['active_memory_bytes']-=9*GIB
            bank.total_nbytes=0
            return 1
        bank.clear=mock.Mock(side_effect=clear)
        state=NS(metal_memory_caps={'memory_limit_bytes':40*GIB},allow_swap=False,
            memory_plan=NS(kv_bytes_per_token=65536,kv_bytes_per_token_effective=19660),sessions=None)
        env=server._prefill_admission_shed.__globals__
        with mock.patch.dict(env,{'_mlx_memory_stats_live':lambda:stats,'_record_guard_event':mock.Mock()}), mock.patch.object(mx,'clear_cache'), mock.patch('builtins.print'):
            result=server._prefill_admission_shed(state,prompt_ids=list(range(100000)),session_bank=bank,session_id='test')
        self.assertNotIn('refused',result)
        bank.clear.assert_called_once_with(session_id='test')
        self.assertLess(result['projected_bytes_after'],40*GIB)

    def test_checkpoint_survives_ram_eviction_and_reopen(self):
        # Byte accounting simulates a large snapshot; actual tensors are tiny.
        for cap in [12*GIB,2*GIB]:
            with self.subTest(cap=cap), tempfile.TemporaryDirectory() as directory:
                cold=SessionBankColdTier(base_dir=directory,mode='on',max_bytes=16*GIB,min_prefix_tokens=1)
                busy=lambda:True
                cold.foreground_busy=busy
                bank=SessionBank(cold_tier=cold,max_bytes=12*GIB,per_session_max_bytes=cap)
                bank.cold_enqueue_dispatch=lambda job:None
                try:
                    with mock.patch.object(cold,'_effective_write_budget',return_value=(16*GIB,None)),mock.patch.object(mx,'get_active_memory',return_value=20*GIB):
                        runtime,entry=self.put(bank,nbytes=4*GIB)
                    self.assertTrue(bank._launcher_checkpoint['stored'])
                    self.assertIs(cold.foreground_busy,busy)
                    bank.clear()
                finally:
                    cold.close()
                reopened=SessionBankColdTier(base_dir=directory,mode='on',max_bytes=16*GIB,min_prefix_tokens=1)
                try:
                    restored=SessionBank(cold_tier=reopened).restore(runtime,[1,2,3,4,5],session_id='test')
                    self.assertIsNotNone(restored)
                    self.assertEqual(restored.cache_source,'ssd')
                    self.assertEqual(restored.cache[0].state[0].tolist(),self.cache()[0].state[0].tolist())
                finally:
                    reopened.close()

    def test_checkpoint_deadline_aborts_without_publishing(self):
        with tempfile.TemporaryDirectory() as directory:
            cold=SessionBankColdTier(base_dir=directory,mode='on',max_bytes=16*GIB,min_prefix_tokens=1)
            busy=lambda:False
            cold.foreground_busy=busy
            _,entry=self.put(SessionBank())
            token=adapter._checkpoint_deadline.set(time.monotonic()-1)
            try:
                with mock.patch.object(cold,'_effective_write_budget',return_value=(16*GIB,None)):
                    with self.assertRaises(ColdEncodeInterrupted):
                        cold.spill_entry(entry,raise_on_yield=True)
                self.assertIs(cold.foreground_busy,busy)
                self.assertIsNone(cold.lookup(entry.token_ids,model_path='/test/qwen',mtp_enabled=True))
            finally:
                adapter._checkpoint_deadline.reset(token)
                cold.close()

if __name__=='__main__':
    unittest.main()
