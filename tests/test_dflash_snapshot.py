import os
import unittest
from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import patch

from dflash_snapshot import install_chunked_snapshot_features

VERSIONS = ('0.6.4', '0.1.10+omlx.7')


class SnapshotInterface(unittest.TestCase):
    def test_changed_native_interface_is_rejected_before_install(self):
        @dataclass
        class Store:
            _prefill_hidden_for_snapshot: object = None
            _generation_chunks: list = field(default_factory=list)
            def generation_snapshot_hidden(self): return 'original'
        @dataclass
        class Chunks:
            total_len: int
            chunks: tuple
            spans: tuple
        original = Store.generation_snapshot_hidden
        for versions, chunks in [(('0.6.5', VERSIONS[1]), Chunks), (VERSIONS, object)]:
            with self.assertRaisesRegex(RuntimeError, 'interface changed'):
                install_chunked_snapshot_features(Store, chunks, versions=versions)
            self.assertIs(Store.generation_snapshot_hidden, original)
        install_chunked_snapshot_features(Store, Chunks, versions=VERSIONS)
        installed = Store.generation_snapshot_hidden
        install_chunked_snapshot_features(Store, Chunks, versions=VERSIONS)
        self.assertIs(Store.generation_snapshot_hidden, installed)
        self.assertIsNone(Store().generation_snapshot_hidden())


@unittest.skipUnless(os.environ.get('LLM_LAUNCHER_OMLX_NATIVE') == '1',
                     'opt-in small native MLX arrays; no model weights')
class NativeSnapshotFeatures(unittest.TestCase):
    def setUp(self):
        from importlib.metadata import version
        from dflash_mlx.engine.target_features import TargetFeatureStore
        from dflash_mlx.cache.snapshot import TargetHiddenChunks
        self.store_type, self.chunks_type = TargetFeatureStore, TargetHiddenChunks
        self.original = TargetFeatureStore.generation_snapshot_hidden
        install_chunked_snapshot_features(TargetFeatureStore, TargetHiddenChunks,
            versions=(version('omlx'), version('dflash-mlx')))
        self.addCleanup(setattr, TargetFeatureStore, 'generation_snapshot_hidden', self.original)
        self.addCleanup(delattr, TargetFeatureStore, '_launcher_chunked_snapshot_installed')

    def test_native_snapshot_values_and_restore_match_across_trim_policies(self):
        import mlx.core as mx
        from mlx_lm.models.cache import KVCache
        from dflash_mlx.cache import codecs
        from dflash_mlx.cache.fingerprints import DFlashPrefixKey
        from omlx_hub_runtime import snapshot_hidden_copy_bytes

        prompt, generated, width = 6000, 97, 8
        data = (mx.arange((prompt + generated) * width) % 97).astype(mx.float16)
        data = data.reshape(1, prompt + generated, width)
        mx.eval(data)
        sparse = self.chunks_type(prompt, (data[:, :32], data[:, 5600:prompt]),
                                  ((0, 32), (5600, prompt)))
        full_draft = SimpleNamespace(args=SimpleNamespace(
            layer_types=['full_attention'], sliding_window=0))
        cases = [
            ('tail', data[:, :prompt], 0, 128, 0, None, prompt + generated),
            ('sink-tail', data[:, :prompt], 32, 128, 0, None, prompt + generated),
            ('sidecar', sparse, 32, 128, 5900, None, prompt + generated),
            ('full', data[:, :prompt], 0, 128, 0, full_draft, prompt + generated),
            ('untrimmed', data[:, :prompt], 0, 0, 0, None, prompt + generated),
            ('cut-last-block', sparse, 32, 128, 5900, None, prompt + generated - 2),
        ]
        for label, prefill, sink, window, boundary, draft, prefix in cases:
            with self.subTest(label=label):
                store = self.store_type(prompt_len=prompt)
                store._prefill_hidden_for_snapshot = prefill
                store._generation_chunks = [data[:, prompt:prompt+37], data[:, prompt+37:]]
                original = self.original(store)
                with patch.object(mx, 'concatenate', side_effect=AssertionError('early allocation')):
                    chunked = store.generation_snapshot_hidden()
                cache = KVCache()
                cache.keys = mx.ones((1, 1, prefix, 4), dtype=mx.float16)
                cache.values = cache.keys * 3
                cache.offset = prefix
                kwargs = dict(token_ids=range(prefix), target_cache=[cache],
                    last_logits=None, kind='generation', adopt_cache_arrays=True,
                    key=DFlashPrefixKey('target', 'draft', (0,), sink, window, 'template', 'policy'),
                    draft_sink_size=sink, draft_window_size=window,
                    draft_model=draft, allow_full_attention_context=draft is not None,
                    sidecar_boundary=boundary,
                    sidecar_gdn_states=(None,) if boundary else None,
                    sidecar_last_logits=mx.zeros((1, 8)) if boundary else None)
                before = codecs.build_snapshot(target_hidden=original, **kwargs)
                after = codecs.build_snapshot(target_hidden=chunked, **kwargs)
                self.assertEqual(before.token_ids, after.token_ids)
                self.assertEqual(before.target_hidden_chunk_spans, after.target_hidden_chunk_spans)
                self.assertEqual(before.target_hidden_total_len, after.target_hidden_total_len)
                for expected, actual in zip(before.target_hidden_chunks, after.target_hidden_chunks):
                    self.assertTrue(mx.array_equal(expected, actual).item())
                restored = codecs.hydrate_target_cache(after, [KVCache()])[0]
                self.assertTrue(mx.array_equal(restored.keys, cache.keys).item())
                self.assertTrue(mx.array_equal(restored.values, cache.values).item())
                service = SimpleNamespace(_builder=SimpleNamespace(draft_model=draft,
                    draft_sink_size=sink, draft_window_size=window))
                bound = snapshot_hidden_copy_bytes(service, dict(target_hidden=chunked, **kwargs),
                                                    codecs._build_target_hidden_chunks)
                self.assertEqual(bound, sum(c.nbytes for c in after.target_hidden_chunks))

        store._prefill_hidden_for_snapshot = sparse
        chunked = store.generation_snapshot_hidden()
        # Missing full-context features must still fail native coverage checks.
        for hidden in (self.original(store), chunked):
            with self.assertRaisesRegex(ValueError, 'do not cover'):
                codecs._build_target_hidden_chunks(hidden, draft_sink_size=0,
                    draft_window_size=0, clone=False)
        store._generation_chunks = []
        self.assertIsNone(store.generation_snapshot_hidden())

    def test_large_prompt_handoff_avoids_full_join_allocation(self):
        import gc
        import mlx.core as mx
        from dflash_mlx.cache import codecs

        prompt, generated, width = 41394, 3864, 128
        data = mx.ones((1, prompt + generated, width), dtype=mx.float16)
        mx.eval(data)
        store = self.store_type(prompt_len=prompt)
        store._prefill_hidden_for_snapshot = data[:, :prompt]
        store._generation_chunks = [data[:, start:min(start+128, prompt+generated)]
                                   for start in range(prompt, prompt+generated, 128)]
        mx.eval(store._prefill_hidden_for_snapshot, *store._generation_chunks)
        peaks = []
        for prepare in (lambda: self.original(store), store.generation_snapshot_hidden):
            gc.collect()
            mx.synchronize()
            mx.clear_cache()
            start = mx.get_active_memory()
            mx.reset_peak_memory()
            hidden = prepare()
            chunks, spans, total = codecs._build_target_hidden_chunks(hidden,
                draft_sink_size=0, draft_window_size=2048, cover_boundary=prompt,
                clone=False)
            mx.eval(*chunks)
            mx.synchronize()
            peaks.append(mx.get_peak_memory() - start)
            self.assertEqual(spans, ((prompt-2048, prompt+generated),))
            self.assertEqual(total, prompt+generated)
            self.assertTrue(mx.array_equal(chunks[0], data[:, prompt-2048:]).item())
            del chunks, hidden
        self.assertGreater(peaks[0], 8 * 1024**2)
        self.assertLess(peaks[1], peaks[0] / 2)
        print('Native snapshot extra peak bytes: before=%d after=%d' % tuple(peaks))


if __name__ == '__main__':
    unittest.main()
