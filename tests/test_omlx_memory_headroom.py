import os
import unittest
from types import SimpleNamespace
from omlx_hub_runtime import (install_memory_headroom, snapshot_hidden_copy_bytes,
                             make_snapshot_reclaimer)

GiB = 1024**3

class MemoryHeadroom(unittest.TestCase):
    def setUp(self):
        class Guard:
            _memory_hard_limit_bytes = 40 * GiB
            def preflight_or_raise(self, required):
                if required > self._memory_hard_limit_bytes:
                    raise ValueError('prefill_memory_exceeded')
                return self._memory_hard_limit_bytes
        class Snapshot:
            calls = 0
            def publish(self, **kwargs):
                self.calls += 1
                return 'native snapshot'
        self.usage = 25 * GiB
        install_memory_headroom(Guard, Snapshot, lambda: self.usage, lambda: self.usage)
        self.guard, self.snapshot = Guard(), Snapshot()

    def test_rejects_before_eviction_without_mutating_native_ceiling(self):
        with self.assertRaisesRegex(ValueError, 'prefill_memory_exceeded'):
            self.guard.preflight_or_raise(37 * GiB)
        self.assertEqual(self.guard._memory_hard_limit_bytes, 40 * GiB)
        self.assertEqual(self.guard.preflight_or_raise(35 * GiB), 36 * GiB)

    def test_snapshot_admission_precedes_allocation_and_preserves_safe_cache(self):
        self.guard.preflight_or_raise(30 * GiB)
        cache = [SimpleNamespace(state=(SimpleNamespace(nbytes=2 * GiB), None))]
        self.assertEqual(self.snapshot.publish(target_cache=cache), 'native snapshot')
        self.usage = 33 * GiB
        self.assertIsNone(self.snapshot.publish(target_cache=cache))
        self.assertEqual(self.snapshot.calls, 1)

    def test_unknown_cache_layout_skips_only_optional_snapshot(self):
        self.guard.preflight_or_raise(30 * GiB)
        self.assertIsNone(self.snapshot.publish(target_cache=[object()]))
        self.assertEqual(self.snapshot.calls, 0)

    def test_lower_dynamic_limit_is_respected(self):
        self.guard._memory_hard_limit_bytes = 30 * GiB
        with self.assertRaises(ValueError): self.guard.preflight_or_raise(28 * GiB)
        self.assertEqual(self.guard._memory_hard_limit_bytes, 30 * GiB)
        self.assertIsNone(self.snapshot.publish(target_cache=[SimpleNamespace(nbytes=GiB)]))

    def test_generation_reuses_resident_cache_with_hidden_workspace_reserved(self):
        self.guard.preflight_or_raise(30 * GiB)
        self.snapshot._cache_manager = SimpleNamespace(_store=SimpleNamespace(_l2=None))
        self.usage = 33 * GiB
        payload = dict(
            kind='generation', adopt_cache_arrays=True,
            target_cache=[SimpleNamespace(nbytes=4 * GiB)],
            target_hidden=SimpleNamespace(nbytes=GiB // 2),
        )
        # Native adoption needs 2 GiB additional allowance, not 10 GiB.
        self.assertEqual(self.snapshot.publish(**payload), 'native snapshot')
        self.usage = 35 * GiB
        self.assertIsNone(self.snapshot.publish(**payload))
        self.assertEqual(self.snapshot.calls, 1)

    def test_copied_disk_and_unknown_snapshots_keep_full_workspace_allowance(self):
        self.guard.preflight_or_raise(30 * GiB)
        self.usage = 33 * GiB
        self.snapshot._cache_manager = SimpleNamespace(_store=SimpleNamespace(_l2=None))
        payload = dict(kind='generation', adopt_cache_arrays=True,
                       target_cache=[SimpleNamespace(nbytes=2 * GiB)])
        for changes in ({'adopt_cache_arrays': False}, {'kind': 'prefill'}, {'l2_only': True}):
            self.assertIsNone(self.snapshot.publish(**{**payload, **changes}))
        self.snapshot._cache_manager._store._l2 = object()
        self.assertIsNone(self.snapshot.publish(**payload))
        del self.snapshot._cache_manager._store._l2
        self.assertIsNone(self.snapshot.publish(**payload))
        self.snapshot._cache_manager._store._l2 = None
        self.assertIsNone(self.snapshot.publish(**{**payload, 'target_cache': [object()]}))
        self.assertEqual(self.snapshot.calls, 0)

    def test_ceiling_lowered_after_prefill_still_blocks_snapshot_before_build(self):
        self.guard.preflight_or_raise(30 * GiB)
        self.snapshot._cache_manager = SimpleNamespace(_store=SimpleNamespace(_l2=None))
        self.guard._memory_hard_limit_bytes = 28 * GiB
        self.assertIsNone(self.snapshot.publish(kind='generation', adopt_cache_arrays=True,
                                              target_cache=[SimpleNamespace(nbytes=GiB)]))
        self.assertEqual(self.snapshot.calls, 0)

    def test_changed_hidden_layout_or_builder_retains_full_allowance(self):
        from unittest.mock import Mock
        hidden = SimpleNamespace(nbytes=5 * GiB)
        builder = Mock(side_effect=ValueError('changed native shape contract'))
        self.assertEqual(snapshot_hidden_copy_bytes(self.snapshot, {'target_hidden': hidden}, builder), 5 * GiB)
        builder.assert_not_called()
        hidden.shape, hidden.dtype = (1, 65_536, 4096), SimpleNamespace(size=2)
        self.snapshot._builder = SimpleNamespace(draft_model=None, draft_sink_size=0, draft_window_size=2048)
        self.assertEqual(snapshot_hidden_copy_bytes(
            self.snapshot, {'target_hidden': hidden, 'token_ids': range(65_536)}, builder), 5 * GiB)
        builder.assert_called_once()


class SnapshotReplacementHeadroom(unittest.TestCase):
    def setUp(self):
        import threading
        from unittest.mock import Mock

        class Manager:
            def maybe_insert_snapshot(self): pass
            def lookup(self): pass
        class L1:
            def insert_with_evictions(self): pass
        class Guard:
            _memory_hard_limit_bytes = 40 * GiB
            def preflight_or_raise(self): pass
        class Snapshot:
            calls = 0
            def publish(self, **kwargs):
                self.calls += 1
                return 'native snapshot'

        self.manager_type, self.l1_type = Manager, L1
        self.manager, self.l1 = Manager(), L1()
        self.manager._state_lock = threading.RLock()
        self.manager._retired = False
        self.manager._store = SimpleNamespace(_l1=self.l1, _l2=None)
        self.l1._lock = threading.Lock()
        self.l1._max_entries, self.l1._max_bytes = 1, 9 * GiB
        self.l1._entries = {7: SimpleNamespace(kind='generation', prefix_len=22946)}
        self.l1._lru_order = [7]
        self.l1._stats = {'evictions': 4}
        self.mx = SimpleNamespace(synchronize=Mock(), clear_cache=Mock())
        self.reclaim = make_snapshot_reclaimer(Manager, L1, self.mx,
                                              versions=('0.6.4', '0.1.10+omlx.7'))
        self.usage = 35.8 * GiB
        install_memory_headroom(Guard, Snapshot, lambda: self.usage, lambda: self.usage,
                                snapshot_reclaimer=self.reclaim)
        self.guard, self.service = Guard(), Snapshot()
        self.guard.preflight_or_raise()
        self.service._cache_manager = self.manager
        self.payload = dict(kind='generation', adopt_cache_arrays=True,
                            target_cache=[SimpleNamespace(nbytes=5 * GiB)],
                            target_hidden=SimpleNamespace(nbytes=24 * 1024**2))

    def test_obsolete_generation_released_before_build_and_actual_usage_rechecked(self):
        import weakref
        class OldSnapshot:
            kind, prefix_len = 'generation', 22946
        self.l1._entries[7] = OldSnapshot()
        old = weakref.ref(self.l1._entries[7])
        def clear():
            self.assertIsNone(old(), 'old arrays must not be retained by the observer')
            self.assertEqual(self.service.calls, 0, 'new snapshot built before reclaim')
            self.usage = 34 * GiB
        self.mx.clear_cache.side_effect = clear
        self.assertEqual(self.service.publish(**self.payload), 'native snapshot')
        self.mx.synchronize.assert_called_once()
        self.mx.clear_cache.assert_called_once()
        self.assertEqual(self.l1._stats['evictions'], 5)
        self.assertEqual(self.l1._entries, {})
        self.assertEqual(self.l1._lru_order, [])
        self.assertEqual(self.guard._memory_hard_limit_bytes, 40 * GiB)

    def test_logical_eviction_does_not_count_as_freed_physical_memory(self):
        # Other references may still retain arrays. No measured improvement
        # means no admission even though the logical entry has been released.
        self.assertIsNone(self.service.publish(**self.payload))
        self.assertEqual(self.service.calls, 0)
        self.assertEqual(self.l1._entries, {})

    def test_lowered_ceiling_during_cleanup_is_respected(self):
        def clear():
            self.usage = 33 * GiB
            self.guard._memory_hard_limit_bytes = 37 * GiB
        self.mx.clear_cache.side_effect = clear
        self.assertIsNone(self.service.publish(**self.payload))
        self.assertEqual(self.service.calls, 0)

    def test_healthy_admission_never_evicts_or_synchronizes(self):
        self.usage = 30 * GiB
        self.assertEqual(self.service.publish(**self.payload), 'native snapshot')
        self.mx.synchronize.assert_not_called()
        self.assertIn(7, self.l1._entries)

    def test_native_prefill_disk_multislot_and_oversized_policies_are_preserved(self):
        variants = (
            ('prefill', lambda: setattr(self.l1._entries[7], 'kind', 'prefill')),
            ('disk', lambda: setattr(self.manager._store, '_l2', object())),
            ('multislot', lambda: setattr(self.l1, '_max_entries', 2)),
            ('oversized', lambda: setattr(self.l1, '_max_bytes', GiB)),
            ('retired', lambda: setattr(self.manager, '_retired', True)),
        )
        for label, change in variants:
            with self.subTest(label=label):
                self.setUp()
                change()
                self.assertIsNone(self.service.publish(**self.payload))
                self.mx.clear_cache.assert_not_called()
                self.assertIn(7, self.l1._entries)

    def test_non_adopted_publications_never_reclaim(self):
        for override in ({'kind': 'prefill'}, {'adopt_cache_arrays': False}, {'l2_only': True}):
            with self.subTest(override=override):
                self.assertIsNone(self.service.publish(**{**self.payload, **override}))
        self.mx.clear_cache.assert_not_called()

    def test_unknown_runtime_fails_before_installation(self):
        with self.assertRaisesRegex(RuntimeError, 'interface changed'):
            make_snapshot_reclaimer(self.manager_type, self.l1_type, self.mx,
                                    versions=('0.6.5', '0.1.10+omlx.7'))


@unittest.skipUnless(os.environ.get('LLM_LAUNCHER_OMLX_NATIVE') == '1', 'opt-in tiny native MLX arrays')
class NativeSnapshotReuse(unittest.TestCase):
    def test_native_single_entry_replacement_releases_real_arrays_and_reuses_successor(self):
        import mlx.core as mx
        from mlx_lm.models.cache import KVCache
        from dflash_mlx.cache import codecs
        from dflash_mlx.cache.fingerprints import DFlashPrefixKey
        from dflash_mlx.cache.manager import RuntimeCacheManager
        from dflash_mlx.cache.prefix_l1 import DFlashPrefixCache
        from dflash_mlx.cache.snapshot_service import SnapshotService
        from dflash_mlx.cache.store import PrefixSnapshotStore

        key = DFlashPrefixKey('fixture-target', 'fixture-draft', (0,), 0, 8, 'template', 'policy')
        manager = RuntimeCacheManager(PrefixSnapshotStore(l1=DFlashPrefixCache(
            max_entries=1, max_bytes=16 * 1024**2)))
        builder = codecs.PrefixSnapshotBuilder(key=key, draft_sink_size=0, draft_window_size=8)
        def old_snapshot():
            old_kv = KVCache()
            old_kv.update_and_fetch(mx.ones((1, 2, 4096, 16)), mx.ones((1, 2, 4096, 16)))
            hidden = mx.ones((1, 4096, 16))
            mx.eval(old_kv.state, hidden)
            return builder.build(token_ids=list(range(4096)), target_cache=[old_kv],
                target_hidden=hidden, last_logits=None, kind='generation',
                allow_full_attention_context=False, adopt_cache_arrays=True)
        manager.maybe_insert_snapshot(old_snapshot(), key=key, kind='generation', require_logits=False)
        kv = KVCache()
        kv.update_and_fetch(mx.ones((1, 2, 33, 16)) * 7, mx.ones((1, 2, 33, 16)) * 9)
        hidden = mx.ones((1, 33, 16))
        mx.eval(kv.state, hidden)
        mx.synchronize()
        mx.clear_cache()
        before = mx.get_active_memory()
        # Scale only the baseline to the admission boundary. No model weights
        # are loaded; whether cleanup frees the old buffers is measured by MLX.
        base = 35 * GiB - before - 2 * (8 * 16 * hidden.dtype.size) + 1
        class Guard:
            _memory_hard_limit_bytes = 40 * GiB
            def preflight_or_raise(self): pass
        class GuardedSnapshot(SnapshotService): pass
        reclaim = make_snapshot_reclaimer(RuntimeCacheManager, DFlashPrefixCache, mx,
                                          versions=('0.6.4', '0.1.10+omlx.7'))
        install_memory_headroom(Guard, GuardedSnapshot,
            lambda: base + mx.get_active_memory(), lambda: base + mx.get_active_memory(),
            codecs._build_target_hidden_chunks, reclaim)
        guard = Guard()
        guard.preflight_or_raise()
        service = GuardedSnapshot(cache_manager=manager, builder=builder)
        tokens = [9999, *range(1, 33)]
        try:
            publication = service.publish(token_ids=tokens, target_cache=[kv],
                target_hidden=hidden, last_logits=None, kind='generation', require_logits=False,
                snapshot_boundary=33, allow_full_attention_context=False, adopt_cache_arrays=True)
            self.assertIsNotNone(publication)
            self.assertTrue(publication.admitted)
            self.assertLess(mx.get_active_memory(), before)
            self.assertEqual(manager.stats()['evictions'], 1)
            hit = manager.lookup([*tokens, 34], key)
            self.assertEqual(hit.matched_tokens, 33)
            self.assertEqual(manager.stats()['current_entries'], 0)
            restored = codecs.hydrate_target_cache(hit.snapshot, [KVCache()])
            self.assertTrue(mx.array_equal(restored[0].keys, mx.ones((1, 2, 33, 16)) * 7).item())
            self.assertEqual(guard._memory_hard_limit_bytes, 40 * GiB)
        finally:
            manager.shutdown()

    def test_native_retained_hidden_bound_covers_real_dense_sparse_sidecar_and_full_context_allocations(self):
        from unittest.mock import patch
        import mlx.core as mx
        from dflash_mlx.cache import codecs
        from dflash_mlx.cache.snapshot import TargetHiddenChunks

        rows, width = 45_258, 128
        hidden = (mx.arange(rows * width) % 97).astype(mx.float16).reshape(1, rows, width)
        mx.eval(hidden)
        sparse = TargetHiddenChunks(rows, (hidden[:, :40_000], hidden[:, 40_000:]),
                                    ((0, 40_000), (40_000, rows)))
        full_draft = SimpleNamespace(args=SimpleNamespace(
            layer_types=['full_attention'], sliding_window=0))
        cases = [
            ('dense-tail', hidden, 0, 2048, 0, None, False, rows, 2048),
            ('sink-tail', hidden, 64, 2048, 0, None, False, rows, 2112),
            ('sparse-sidecar', sparse, 0, 2048, 41_394, None, False, rows, 5912),
            ('full-attention', sparse, 0, 2048, 0, full_draft, True, rows, rows),
            ('zero-window', hidden, 0, 0, 0, None, False, rows, rows),
            ('sidecar-overlap', hidden, 64, 2048, 1024, None, False, rows, rows),
            ('trimmed-prefix', hidden, 0, 2048, 0, None, False, 40_000, 2048),
        ]
        for label, features, sink, window, boundary, draft, full, prefix, retained_rows in cases:
            with self.subTest(label=label):
                service = SimpleNamespace(_builder=SimpleNamespace(
                    draft_model=draft, draft_sink_size=sink, draft_window_size=window))
                values = dict(target_hidden=features, token_ids=range(prefix),
                              sidecar_boundary=boundary, allow_full_attention_context=full)
                # Estimating executes upstream policy without native array
                # construction, concatenation or evaluation.
                with patch.object(mx, 'concatenate', side_effect=AssertionError('estimate allocated')):
                    bound = snapshot_hidden_copy_bytes(service, values, codecs._build_target_hidden_chunks)
                self.assertEqual(bound, retained_rows * width * hidden.dtype.size)
                actual_features = features if prefix == rows else features[:, :prefix]
                mx.synchronize()
                mx.clear_cache()
                before = mx.get_active_memory()
                mx.reset_peak_memory()
                with patch.object(codecs, '_clone_array', side_effect=AssertionError('unexpected copy')):
                    chunks, spans, total = codecs._build_target_hidden_chunks(
                        actual_features, draft_model=draft, draft_sink_size=sink,
                        draft_window_size=window, allow_full_attention_context=full,
                        clone=False, cover_boundary=boundary)
                    mx.eval(*chunks)
                mx.synchronize()
                allocated_peak = max(0, mx.get_peak_memory() - before)
                self.assertEqual(total, prefix)
                self.assertEqual(sum(chunk.nbytes for chunk in chunks), bound)
                self.assertLessEqual(allocated_peak, 2 * bound + 1024**2)
                for chunk, (start, end) in zip(chunks, spans):
                    self.assertTrue(mx.array_equal(chunk, hidden[:, start:end]).item())
                del chunk, chunks

        # Reproduce the real skip's dimensions without allocating its 442 MiB
        # payload. The native sidecar policy retains 57.7 MiB, so the same
        # existing 90% ceiling admits publication with >300 MiB to spare.
        live_hidden = SimpleNamespace(shape=(1, rows, 5120), dtype=mx.float16,
                                      nbytes=rows * 5120 * 2)
        service = SimpleNamespace(_builder=SimpleNamespace(
            draft_model=None, draft_sink_size=0, draft_window_size=2048))
        bound = snapshot_hidden_copy_bytes(service, dict(target_hidden=live_hidden,
            token_ids=range(rows), sidecar_boundary=41_394), codecs._build_target_hidden_chunks)
        current, limit = 36_705_978_800, 38_245_650_163
        self.assertGreater(current + 2 * live_hidden.nbytes + GiB, limit)
        self.assertLess(current + 2 * bound + GiB, limit)

    def test_adopted_snapshot_roundtrip_survives_cache_updates_without_model_weights(self):
        from importlib.metadata import version
        from unittest.mock import patch
        import mlx.core as mx
        from mlx_lm.models.cache import KVCache
        from dflash_mlx.cache import codecs
        from dflash_mlx.cache.fingerprints import DFlashPrefixKey
        from dflash_mlx.cache.manager import RuntimeCacheManager
        from dflash_mlx.cache.prefix_l1 import DFlashPrefixCache
        from dflash_mlx.cache.snapshot_service import SnapshotService
        from dflash_mlx.cache.store import PrefixSnapshotStore
        from dflash_mlx.recurrent_rollback_cache import RecurrentRollbackCache
        from omlx_hub_runtime import snapshot_copy_bytes

        self.assertEqual(version('omlx'), '0.6.4')
        key = DFlashPrefixKey('fixture-target', 'fixture-draft', (0,), 0, 8, 'template', 'policy')
        tokens = list(range(33))
        kv = KVCache()
        keys = mx.arange(33 * 16, dtype=mx.float32).reshape(1, 2, 33, 8)
        kv.update_and_fetch(keys, keys + 1)
        recurrent = RecurrentRollbackCache(2)
        recurrent[0], recurrent[1] = mx.ones((1, 3, 8)), mx.ones((1, 2, 4, 4)) * 2
        hidden = mx.arange(33 * 16, dtype=mx.float32).reshape(1, 33, 16)
        logits = mx.arange(64, dtype=mx.float32).reshape(1, 64)
        mx.eval(kv.state, recurrent.state, hidden, logits)
        manager = RuntimeCacheManager(PrefixSnapshotStore(l1=DFlashPrefixCache(
            max_entries=1, max_bytes=2 * 1024**2, max_snapshot_tokens=16)))

        class Guard:
            _memory_hard_limit_bytes = 40 * GiB
            def preflight_or_raise(self):
                pass
        class GuardedSnapshot(SnapshotService):
            pass

        # Simulated pressure only: actual native fixtures occupy kilobytes.
        # The old full-copy estimate rejects this exact safe adoption boundary.
        usage = 35 * GiB - 2 * (8 * 16 * hidden.dtype.size)
        full_bytes = snapshot_copy_bytes([kv, recurrent, hidden, logits])
        self.assertGreater(usage + 2 * full_bytes + GiB, 36 * GiB)
        install_memory_headroom(Guard, GuardedSnapshot, lambda: usage, lambda: usage,
                                codecs._build_target_hidden_chunks)
        guard = Guard()
        guard.preflight_or_raise()
        service = GuardedSnapshot(cache_manager=manager, builder=codecs.PrefixSnapshotBuilder(
            key=key, draft_sink_size=0, draft_window_size=8))
        try:
            payload = dict(
                token_ids=tokens, target_cache=[kv, recurrent], target_hidden=hidden,
                last_logits=logits, kind='generation', require_logits=False,
                snapshot_boundary=33, allow_full_attention_context=False,
                adopt_cache_arrays=True)
            usage += 1
            with patch.object(codecs.PrefixSnapshotBuilder, 'build',
                              side_effect=AssertionError('build before admission')):
                self.assertIsNone(service.publish(**payload))
            usage -= 1
            # No array cloning is permitted on this native publication path.
            with patch.object(codecs, '_clone_array', side_effect=AssertionError('unexpected copy')):
                publication = service.publish(**payload)
            self.assertTrue(publication.admitted)
            # A different prefix must never reuse the snapshot.
            self.assertIsNone(manager.lookup([999, *tokens[1:], 34], key).snapshot)
            hit = manager.lookup([*tokens, 34], key)
            self.assertEqual(hit.matched_tokens, 33)
            self.assertEqual(manager.stats()['current_entries'], 0)
            saved = hit.snapshot
            # The native logical cap includes hidden/state/logits, not just KV.
            kv_bytes = sum(array.nbytes for array in saved.fa_states[0][:2])
            self.assertGreater(saved.nbytes, kv_bytes)
            too_small = DFlashPrefixCache(max_entries=1, max_bytes=kv_bytes)
            self.assertFalse(too_small.insert_with_evictions(saved).admitted)
            exact_capacity = DFlashPrefixCache(max_entries=1, max_bytes=saved.nbytes)
            self.assertTrue(exact_capacity.insert_with_evictions(saved).admitted)
            exact_capacity.clear()
            self.assertIs(saved.gdn_states[1][0], recurrent[0])
            self.assertIs(saved.last_logits, logits)
            with patch.object(codecs, '_clone_array', side_effect=AssertionError('unexpected copy')):
                restored = codecs.hydrate_target_cache(saved, [KVCache(), RecurrentRollbackCache(2)])
            self.assertIs(restored[0].keys, saved.fa_states[0][0])
            self.assertTrue(mx.array_equal(restored[0].state[0], keys).item())
            self.assertTrue(mx.array_equal(restored[0].state[1], keys + 1).item())

            # Both the original spare-capacity cache and the restored exact
            # cache may append; the stored prefix and recurrent state stay exact.
            next_keys = mx.ones((1, 2, 2, 8)) * 99
            kv.update_and_fetch(next_keys, next_keys + 1)
            restored[0].update_and_fetch(next_keys, next_keys + 1)
            recurrent[0] = recurrent[0] + 7
            restored[1][0] = restored[1][0] + 9
            mx.eval(kv.state, restored[0].state, recurrent.state, restored[1].state)
            self.assertEqual(saved.fa_states[0][2], 33)
            self.assertTrue(mx.array_equal(saved.fa_states[0][0], keys).item())
            self.assertTrue(mx.array_equal(saved.gdn_states[1][0], mx.ones((1, 3, 8))).item())
            self.assertTrue(mx.array_equal(saved.target_hidden_chunks[0], hidden[:, -8:, :]).item())
        finally:
            manager.shutdown()

if __name__ == '__main__': unittest.main()
