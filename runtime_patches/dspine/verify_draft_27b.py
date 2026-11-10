"""Check the DSpine draft patch on MLX CPU with tiny synthetic inputs.

Run with the patched Tencent `dspine_mlx/` directory on PYTHONPATH.
No model weights are used.
"""
from dataclasses import replace
import unittest

import mlx.core as mx
from mlx_lm.models.cache import KVCache
from mlx_lm.models.rope_utils import initialize_rope

from dspine_mlx.config import BridgeConfig, DraftConfig
from dspine_mlx.model import DraftAttention, DSpineDraftModel, SlidingDraftCache


def _released_attention_config():
    return {
        "architectures": ["DFlashDraftModel"],
        "model_type": "qwen3",
        "hidden_size": 5120,
        "num_hidden_layers": 5,
        "intermediate_size": 17408,
        "num_attention_heads": 32,
        "num_key_value_heads": 8,
        "head_dim": 128,
        "vocab_size": 248320,
        "rms_norm_eps": 1e-6,
        "rope_theta": 10000000,
        "max_position_embeddings": 262144,
        "block_size": 16,
        "num_target_layers": 64,
        "is_causal": True,
        "layer_types": ["sliding_attention"] * 5,
        "sliding_window": 8192,
        "use_sliding_window": True,
        "code_bridge_second_pass": {"mode": "serial_table", "first_exact": 4, "head_topk": 16},
        "dflash_config": {
            "draft_block_causal": True,
            "selected_prefix_terminal": False,
            "selected_prefix_decode_mode": "serial",
            "selected_prefix_feature_writes": True,
            "selected_prefix_feature_write_mode": "independent",
            "selected_prefix_code_bridge": {"code_size": 1024, "rank": 512, "eps": 1e-6},
            "selected_prefix_feature_layers": [1, 2, 3, 4, 5],
            "target_layer_ids": [1, 16, 31, 46, 61],
            "mask_token_id": 248070,
        },
    }


class DraftAttentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mx.set_default_device(mx.cpu)

    def setUp(self):
        mx.random.seed(731)
        self.cfg = DraftConfig(
            hidden_size=8, num_hidden_layers=1, intermediate_size=16,
            num_attention_heads=2, num_key_value_heads=1, head_dim=4,
            vocab_size=32, rms_norm_eps=1e-6, rope_theta=10000,
            max_position_embeddings=64, block_size=5, mask_token_id=31,
            target_layer_ids=(0,), num_target_layers=1,
            bridge=BridgeConfig(8, 4, 1e-6), feature_layers=(0,), head_topk=4,
            trained_block_size=5, sliding_window=4,
        )
        self.attention = DraftAttention(self.cfg)
        self.rope = initialize_rope(4, base=10000, traditional=False)
        self.context = mx.random.normal((1, 13, 8))
        self.block = mx.random.normal((1, 5, 8))

    def _assert_close(self, actual, expected):
        self.assertEqual(actual.shape, expected.shape)
        self.assertTrue(bool(mx.allclose(actual, expected, rtol=2e-5, atol=2e-6).item()))

    def _attention_reference(self, attention, context, block, window):
        """Materialize all K/V, then select each query's interval by slicing."""
        prefix = context.shape[1]
        count = block.shape[1]
        keys, values = attention._context_kv(
            mx.concatenate([context, block], axis=1), self.rope, 0,
        )
        queries = attention.q_proj(block).reshape(1, count, 2, 4)
        queries = self.rope(attention.q_norm(queries).transpose(0, 2, 1, 3), offset=prefix)
        rows = []
        for position in range(count):
            end = prefix + position + 1
            start = 0 if window is None else max(0, end - window)
            rows.append(mx.fast.scaled_dot_product_attention(
                queries[:, :, position:position + 1, :],
                keys[:, :, start:end, :], values[:, :, start:end, :],
                scale=attention.scale,
            ))
        output = mx.concatenate(rows, axis=2).transpose(0, 2, 1, 3).reshape(1, count, 8)
        return attention.o_proj(output)

    def test_release_config_requires_consistent_causal_sliding_declarations(self):
        raw = _released_attention_config()
        cfg = DraftConfig.from_dict(raw)
        self.assertEqual(cfg.sliding_window, 8192)
        self.assertEqual(cfg.target_layer_ids, (1, 16, 31, 46, 61))
        self.assertEqual(cfg.concat_size, 25600)
        for mutation in ({"sliding_window": 8191}, {"use_sliding_window": False},
                         {"layer_types": ["full_attention"] * 5}, {"is_causal": False}):
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, "W8192/B16"):
                DraftConfig.from_dict({**raw, **mutation})
        full = DraftConfig.from_dict({**raw, "sliding_window": None,
                                     "layer_types": ["full_attention"] * 5,
                                     "use_sliding_window": False})
        self.assertIsNone(full.sliding_window)

    def test_sliding_cache_evicts_context_and_keeps_absolute_rope_positions(self):
        cache = DSpineDraftModel(self.cfg).make_cache()[0]
        self.assertIsInstance(cache, SlidingDraftCache)
        for start, end in ((0, 2), (2, 9), (9, 11), (11, 13)):
            output = self.attention(self.block, self.context[:, start:end, :], self.rope, cache)
            expected = self._attention_reference(self.attention, self.context[:, :end, :], self.block, 4)
            self._assert_close(output, expected)
            self.assertEqual(cache.offset, end)
            self.assertEqual(cache.keys.shape[2], min(end, 3))
            # A relative-position reset could preserve attention scores while
            # corrupting the absolute cache positions at the next append.
            keys, values = self.attention._context_kv(self.context[:, :end, :], self.rope, 0)
            self._assert_close(cache.keys, keys[:, :, -3:, :])
            self._assert_close(cache.values, values[:, :, -3:, :])
        self._assert_close(self.attention(self.block, None, self.rope, cache), expected)
        self.assertEqual(cache.offset, 13)

    def test_uncached_and_separately_prefilled_sliding_paths_match_reference(self):
        expected = self._attention_reference(self.attention, self.context, self.block, 4)
        uncached = self.attention(self.block, self.context, self.rope)
        self._assert_close(uncached, expected)
        cache = SlidingDraftCache(4)
        self.attention.append_context(self.context, self.rope, cache)
        self._assert_close(self.attention(self.block, None, self.rope, cache), expected)
        self.assertEqual(cache.offset, 13)

    def test_full_attention_retains_context(self):
        cfg = replace(self.cfg, sliding_window=None)
        attention = DraftAttention(cfg)
        cache = DSpineDraftModel(cfg).make_cache()[0]
        self.assertIsInstance(cache, KVCache)
        actual = attention(self.block, self.context, self.rope, cache)
        self._assert_close(actual, self._attention_reference(attention, self.context, self.block, None))
        self.assertEqual(cache.offset, self.context.shape[1])


if __name__ == "__main__":
    unittest.main()
