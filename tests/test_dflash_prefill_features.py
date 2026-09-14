"""Small native-array checks; never load model weights or send a prompt."""
import os
import unittest
from dataclasses import dataclass
from types import SimpleNamespace

from dflash_snapshot import install_chunked_prefill_features


class PrefillInterface(unittest.TestCase):
    def test_unknown_interface_cannot_partially_install(self):
        @dataclass
        class Store:
            prompt_len: int = 0
            _current_hidden: object = None
            def hydrate_from_snapshot(self): pass
            def write_prompt_slice(self): pass
            def _project(self): pass
        @dataclass
        class Chunks:
            total_len: int
            chunks: tuple
            spans: tuple
        original = Store.hydrate_from_snapshot, Store.write_prompt_slice
        for versions, chunks in [(('new', 'new'), Chunks),
                                  (('0.6.4', '0.1.10+omlx.7'), object)]:
            with self.assertRaisesRegex(RuntimeError, 'interface changed'):
                install_chunked_prefill_features(Store, chunks, None, versions=versions)
            self.assertEqual((Store.hydrate_from_snapshot, Store.write_prompt_slice), original)


@unittest.skipUnless(os.environ.get('LLM_LAUNCHER_OMLX_NATIVE') == '1',
                     'opt-in small native MLX arrays; no model weights')
class NativePrefillFeatures(unittest.TestCase):
    def setUp(self):
        from importlib.metadata import version
        import mlx.core as mx
        from dflash_mlx.engine.target_features import TargetFeatureStore
        from dflash_mlx.cache.snapshot import TargetHiddenChunks
        self.mx, self.Store, self.Chunks = mx, TargetFeatureStore, TargetHiddenChunks
        self.hydrate = TargetFeatureStore.hydrate_from_snapshot
        self.write = TargetFeatureStore.write_prompt_slice
        install_chunked_prefill_features(TargetFeatureStore, TargetHiddenChunks, mx,
            versions=(version('omlx'), version('dflash-mlx')))
        installed = TargetFeatureStore.hydrate_from_snapshot
        install_chunked_prefill_features(TargetFeatureStore, TargetHiddenChunks, mx,
            versions=(version('omlx'), version('dflash-mlx')))
        self.assertIs(TargetFeatureStore.hydrate_from_snapshot, installed)
        self.addCleanup(setattr, TargetFeatureStore, 'hydrate_from_snapshot', self.hydrate)
        self.addCleanup(setattr, TargetFeatureStore, 'write_prompt_slice', self.write)
        self.addCleanup(delattr, TargetFeatureStore, '_launcher_chunked_prefill_installed')

    def snapshot(self, data, spans):
        return SimpleNamespace(target_hidden_chunks=tuple(data[:, a:b] for a, b in spans),
                               target_hidden_chunk_spans=spans)

    def equal(self, before, after):
        if isinstance(after, self.Chunks):
            after = after.slice(0, after.total_len)
        self.assertEqual(before.shape, after.shape)
        self.assertEqual(before.dtype, after.dtype)
        self.assertTrue(self.mx.array_equal(before, after).item())

    def test_hydrate_write_consumers_and_snapshot_values(self):
        mx = self.mx
        from dflash_mlx.model import ContextOnlyDraftKVCache, DFlashAttention
        from dflash_mlx.engine.prefill import snapshot_covers_prefix
        from dflash_mlx.cache import codecs

        data = mx.arange(2 * 50 * 8).reshape(2, 50, 8).astype(mx.float16)
        # Dense prefix; trimmed gap; and sidecar chunks extending beyond reuse.
        for spans in [((0, 40),), ((0, 4), (30, 40)), ((0, 4), (25, 50))]:
            with self.subTest(spans=spans):
                snap = self.snapshot(data, spans)
                self.assertEqual(snapshot_covers_prefix(snap, 40), spans == ((0, 40),))
                old, new = self.Store(50), self.Store(50)
                expected = self.hydrate(old, snap, snap_prefix_len=40)
                self.equal(expected, new.hydrate_from_snapshot(snap, snap_prefix_len=40))
                calls = []
                new.project_context = lambda x: (calls.append(x), x * 1.25)[1]
                old.project_context = lambda x: x * 1.25
                # Incremental suffix; interior overwrite crossing multiple spans;
                # batch broadcast and FP32→FP16 assignment semantics.
                for start, end in [(40, 45), (45, 50), (2, 48), (0, 1), (1, 50)]:
                    features = mx.ones((1, end-start, 8), dtype=mx.float32) * (start + .1)
                    expected = self.write(old, start=start, end=end, features=features)
                    actual = new.write_prompt_slice(start=start, end=end, features=features)
                    self.equal(expected, actual)
                    for boundary in [0, 4, 40, 50]:
                        self.equal(old.prefix_view(boundary), new.prefix_view(boundary))
                self.assertEqual(len(calls), 5, 'Project new features exactly once per write')
                for cache in [None, ContextOnlyDraftKVCache(4, 8), ContextOnlyDraftKVCache(0, 8)]:
                    before, old_spans = DFlashAttention._context_segments_for_cache(None, expected, cache)
                    after, new_spans = DFlashAttention._context_segments_for_cache(None, actual, cache)
                    self.assertEqual(old_spans, new_spans)
                    self.equal(before, after)
                # Native trimming must see identical sink/tail and full ranges.
                for sink, window in [(0, 0), (0, 8), (4, 8)]:
                    before = codecs._build_target_hidden_chunks(expected,
                        draft_sink_size=sink, draft_window_size=window, clone=False)
                    after = codecs._build_target_hidden_chunks(actual,
                        draft_sink_size=sink, draft_window_size=window, clone=False)
                    self.assertEqual(before[1:], after[1:])
                    for a, b in zip(before[0], after[0]):
                        self.equal(a, b)
                old.freeze_prefill_for_snapshot(enabled=True)
                new.freeze_prefill_for_snapshot(enabled=True)
                frozen = new._prefill_hidden_for_snapshot
                replacement = mx.zeros((2, 2, 8), dtype=mx.float16)
                # Native execution freezes only after its final prefill write.
                # An extra write to the new store must not mutate its frozen
                # chunks; compare against the old store at that freeze point.
                new.write_prompt_slice(start=2, end=4, features=replacement)
                self.assertIs(new._prefill_hidden_for_snapshot, frozen)
                self.equal(old._prefill_hidden_for_snapshot, frozen)
                generated = mx.ones((2, 3, 8), dtype=mx.float16)
                old.commit_generation(generated, collect_snapshot=True)
                new.commit_generation(generated, collect_snapshot=True)
                self.equal(old.current_hidden, new.current_hidden)
                self.equal(old.generation_snapshot_hidden(), new.generation_snapshot_hidden())

    def test_combines_with_chunked_generation_snapshot_adapter(self):
        from dflash_snapshot import install_chunked_snapshot_features
        from dflash_mlx.cache import codecs
        mx = self.mx
        data = mx.arange(80 * 8).reshape(1, 80, 8).astype(mx.float16)
        snap = self.snapshot(data, ((0, 4), (20, 70)))
        old, new = self.Store(80), self.Store(80)
        self.hydrate(old, snap, snap_prefix_len=70)
        new.hydrate_from_snapshot(snap, snap_prefix_len=70)
        self.write(old, start=70, end=80, features=data[:, 70:])
        new.write_prompt_slice(start=70, end=80, features=data[:, 70:])
        for store in (old, new):
            store.freeze_prefill_for_snapshot(enabled=True)
            store.commit_generation(data[:, :3], collect_snapshot=True)
            store.commit_generation(data[:, 3:6], collect_snapshot=True)
        expected = old.generation_snapshot_hidden()
        original = self.Store.generation_snapshot_hidden
        install_chunked_snapshot_features(self.Store, self.Chunks,
                                          versions=('0.6.4', '0.1.10+omlx.7'))
        self.addCleanup(setattr, self.Store, 'generation_snapshot_hidden', original)
        self.addCleanup(delattr, self.Store, '_launcher_chunked_snapshot_installed')
        actual = new.generation_snapshot_hidden()
        self.equal(expected, actual)
        for sink, window in [(0, 0), (4, 16)]:
            before = codecs._build_target_hidden_chunks(expected,
                draft_sink_size=sink, draft_window_size=window, clone=True)
            after = codecs._build_target_hidden_chunks(actual,
                draft_sink_size=sink, draft_window_size=window, clone=True)
            self.assertEqual(before[1:], after[1:])
            for a, b in zip(before[0], after[0]):
                self.equal(a, b)

    def test_exact_and_empty_snapshot_behavior_stays_native(self):
        mx = self.mx
        old, new = self.Store(10), self.Store(10)
        values = mx.ones((1, 10, 8), dtype=mx.float16)
        self.equal(self.write(old, start=0, end=10, features=values),
                   new.write_prompt_slice(start=0, end=10, features=values))
        self.assertIsInstance(new.current_hidden, self.Chunks)
        snapshot = self.snapshot(values, ((0, 3), (7, 10)))
        before = self.hydrate(old, snapshot, snap_prefix_len=10)
        after = new.hydrate_from_snapshot(snapshot, snap_prefix_len=10)
        self.assertEqual(before.spans, after.spans)
        self.assertFalse(new._launcher_chunked_prefill_active)
        self.equal(self.write(old, start=9, end=10, features=values[:, :1]),
                   new.write_prompt_slice(start=9, end=10, features=values[:, :1]))
        with self.assertRaisesRegex(ValueError, 'empty'):
            new.hydrate_from_snapshot(self.snapshot(values, ()), snap_prefix_len=5)

    def test_cold_prefill_projection_and_prefixes_match_native(self):
        mx = self.mx
        from dflash_mlx.model import ContextOnlyDraftKVCache, DFlashAttention
        for dtype in (mx.float16, mx.bfloat16):
            with self.subTest(dtype=dtype):
                calls = []
                project = lambda x: (x[..., :4] * 2).astype(dtype)
                old = self.Store(65, project_context=project)
                new = self.Store(65, project_context=lambda x: (calls.append(x), project(x))[1])
                for start, end in [(0, 16), (16, 32), (32, 48), (48, 64), (64, 65)]:
                    raw = mx.arange(2*(end-start)*8).reshape(2, end-start, 8).astype(mx.float32)
                    expected = self.write(old, start=start, end=end, features=raw)
                    actual = new.write_prompt_slice(start=start, end=end, features=raw)
                    self.equal(expected, actual)
                    self.equal(old.prefix_view(end), new.prefix_view(end))
                self.assertEqual(len(calls), 5)
                for cache in (None, ContextOnlyDraftKVCache(4, 8)):
                    a, spans_a = DFlashAttention._context_segments_for_cache(None, expected, cache)
                    b, spans_b = DFlashAttention._context_segments_for_cache(None, actual, cache)
                    self.equal(a, b)
                    self.assertEqual(spans_a, spans_b)
                old.freeze_prefill_for_snapshot(enabled=True)
                new.freeze_prefill_for_snapshot(enabled=True)
                raw = mx.ones((2, 3, 8), dtype=mx.float32)
                old.commit_generation(raw, collect_snapshot=True)
                new.commit_generation(raw, collect_snapshot=True)
                self.equal(old.generation_snapshot_hidden(), new.generation_snapshot_hidden())

    def test_first_cold_chunk_does_not_allocate_unprocessed_prompt(self):
        import gc
        mx = self.mx
        prompt, step, width = 42000, 2048, 128
        peaks = []
        for patched in (False, True):
            gc.collect()
            mx.synchronize()
            mx.clear_cache()
            before = mx.get_active_memory()
            mx.reset_peak_memory()
            store = self.Store(prompt)
            features = mx.ones((1, step, width), dtype=mx.float16) * 3
            writer = store.write_prompt_slice if patched else lambda **kw: self.write(store, **kw)
            hidden = writer(start=0, end=step, features=features)
            mx.synchronize()
            peaks.append(mx.get_peak_memory()-before)
            prefix = store.prefix_view(step)
            self.assertTrue(mx.all(prefix == 3).item())
            self.assertEqual(hidden.shape, (1, prompt, width))
            del prefix, hidden, features, writer, store
        self.assertGreater(peaks[0], 8 * 1024**2)
        self.assertLess(peaks[1], peaks[0] / 2)
        print('Native first cold-chunk extra peak bytes: before=%d after=%d' % tuple(peaks))

    def test_partial_hit_allocates_suffix_not_dense_prompt(self):
        import gc
        mx = self.mx
        prompt, prefix, width = 42000, 41800, 128
        # Same logical shape as a long cache hit, narrow features to keep this
        # allocation fixture small. Native consumers select sink+tail as usual.
        cached = mx.ones((1, 2048, width), dtype=mx.float16)
        suffix = mx.ones((1, prompt-prefix, width), dtype=mx.float16) * 3
        mx.eval(cached, suffix)
        snapshot = SimpleNamespace(target_hidden_chunks=(cached,),
            target_hidden_chunk_spans=((prefix-2048, prefix),))
        peaks = []
        for patched in [False, True]:
            gc.collect()
            mx.synchronize()
            mx.clear_cache()
            start = mx.get_active_memory()
            mx.reset_peak_memory()
            store = self.Store(prompt)
            if patched:
                store.hydrate_from_snapshot(snapshot, snap_prefix_len=prefix)
                hidden = store.write_prompt_slice(start=prefix, end=prompt, features=suffix)
                result = hidden.slice(prompt-2048, prompt)
            else:
                self.hydrate(store, snapshot, snap_prefix_len=prefix)
                hidden = self.write(store, start=prefix, end=prompt, features=suffix)
                result = hidden[:, prompt-2048:prompt]
            mx.eval(result)
            mx.synchronize()
            peaks.append(mx.get_peak_memory()-start)
            self.assertTrue(mx.all(result[:, :-200] == 1).item())
            self.assertTrue(mx.all(result[:, -200:] == 3).item())
            del result, hidden, store
        self.assertGreater(peaks[0], 8 * 1024**2)
        self.assertLess(peaks[1], peaks[0] / 2)
        print('Native partial-hit prefill extra peak bytes: before=%d after=%d' % tuple(peaks))


if __name__ == '__main__':
    unittest.main()
