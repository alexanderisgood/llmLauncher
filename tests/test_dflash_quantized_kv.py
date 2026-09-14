"""Native packed cache checks, with tiny arrays and no model weights."""
import json
import os
from dataclasses import replace
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.environ.get("LLM_LAUNCHER_OMLX_NATIVE") == "1", "native GPU opt-in")
class QuantizedPrefixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from importlib.metadata import version
        from dflash_quantized_kv import install_quantized_kv
        from omlx.engine.dflash import DFlashEngine
        cls.bits = int(os.environ.get("TEST_KV_BITS", "6"))
        install_quantized_kv(DFlashEngine, cls.bits,
                             versions=(version("omlx"), version("dflash-mlx")))
        import mlx.core as mx
        from mlx_lm.models.cache import QuantizedKVCache
        from dflash_mlx.cache import codecs, prefix_l2
        cls.mx, cls.Cache, cls.codecs, cls.l2 = mx, QuantizedKVCache, codecs, prefix_l2

    def make(self, length=19):
        from dflash_mlx.cache.fingerprints import DFlashPrefixKey
        from dflash_mlx.recurrent_rollback_cache import RecurrentRollbackCache
        mx = self.mx
        values = mx.sin(mx.arange(4 * length * 256).reshape(1, 4, length, 256)).astype(mx.float16)
        c = self.Cache(bits=self.bits)
        c.update_and_fetch(values, values * .7)
        gdn = RecurrentRollbackCache(size=2)
        gdn.cache = [mx.ones((1, 3, 16)), mx.ones((1, 2, 16, 16))]
        snapshot = self.codecs.build_snapshot(token_ids=list(range(length)),
            target_cache=[c, gdn], target_hidden=mx.ones((1, length, 32)),
            last_logits=mx.ones((1, 32)),
            key=DFlashPrefixKey("test", "draft", (0,), 0, 32, "0" * 64, "1" * 64),
            kind="generation", adopt_cache_arrays=True,
            sidecar_boundary=length - 2, sidecar_gdn_states=(None, tuple(gdn.cache)),
            sidecar_last_logits=mx.ones((1, 32)))
        mx.eval(c.state)
        return c, gdn, snapshot

    def equal(self, a, b):
        if isinstance(a, (tuple, list)):
            self.assertEqual(len(a), len(b))
            for x, y in zip(a, b): self.equal(x, y)
        else:
            self.assertEqual(a.shape, b.shape)
            self.assertTrue(self.mx.array_equal(a, b).item())

    def test_ram_resume_trim_growth_and_immutability(self):
        mx = self.mx
        original, gdn, saved = self.make()
        baseline = tuple(tuple(mx.array(a) for a in tensors) for tensors in saved.fa_states[0][:2])
        mx.eval(baseline)
        resumed, _ = self.codecs.hydrate_target_cache(saved, [self.Cache(bits=self.bits), gdn])
        for length in (2, 260, 3):
            data = mx.cos(mx.arange(4 * length * 256).reshape(1, 4, length, 256)).astype(mx.float16)
            original.update_and_fetch(data, data)
            resumed.update_and_fetch(data, data)
            self.equal(original.state, resumed.state)
            # Exercise rejected speculative suffix rollback, then overwrite.
            original.trim(1)
            resumed.trim(1)
        self.equal(baseline, saved.fa_states[0][:2])
        packed_bytes = sum(a.nbytes for tensors in baseline for a in tensors)
        self.assertEqual(saved.nbytes_breakdown()["fa_kv"], packed_bytes)
        self.assertLess(packed_bytes, 2 * 4 * saved.prefix_len * 256 * 2)
        from mlx_lm.models.base import scaled_dot_product_attention
        q = mx.ones((1, 8, 1, 256), dtype=mx.float16)
        a = scaled_dot_product_attention(q, *original.state, cache=original, scale=.0625, mask=None)
        b = scaled_dot_product_attention(mx.ones((1, 8, 1, 256), dtype=mx.float16),
                                        *resumed.state, cache=resumed, scale=.0625, mask=None)
        self.equal(a, b)

    def test_ssd_roundtrip_and_sidecar_restore(self):
        original, gdn, saved = self.make()
        arrays, meta = self.l2._serialize(saved)
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "cache.safetensors")
            self.mx.save_safetensors(path, arrays, meta)
            arrays, meta = self.mx.load(path, return_metadata=True)
        loaded = self.l2._deserialize(arrays, json.loads(meta["dflash_meta"]))
        self.assertEqual(loaded.nbytes, saved.nbytes)
        restored, _ = self.codecs.hydrate_target_cache(loaded, [self.Cache(bits=self.bits), gdn])
        self.equal(original.state, restored.state)
        sliced = self.codecs.slice_snapshot_at_sidecar_boundary(loaded, require_full_coverage=True)
        restored, _ = self.codecs.hydrate_target_cache(sliced, [self.Cache(bits=self.bits), gdn])
        self.assertEqual(restored.offset, saved.sidecar_boundary)
        self.equal(restored.state, tuple(tuple(a[:, :, :restored.offset, :] for a in t)
                                        for t in original.state))
        with self.assertRaisesRegex(ValueError, "precision"):
            self.codecs.hydrate_target_cache(saved, [self.Cache(bits=4 if self.bits != 4 else 8), gdn])
        malformed = replace(saved, fa_states=((saved.fa_states[0][0], saved.fa_states[0][1], 18,
                                              self.bits, 64), None))
        with self.assertRaises(ValueError):
            self.codecs.hydrate_target_cache(malformed, [self.Cache(bits=self.bits), gdn])

    def test_session_reuses_prefix_and_rejects_mismatching_tokens(self):
        from dflash_mlx.engine.spec_epoch import SpeculativeSession
        from dflash_mlx.runtime.context import build_offline_runtime_context
        _, gdn, saved = self.make()
        for verifier in ("adaptive", "dflash"):
            context = build_offline_runtime_context(quantize_kv_cache=True, verify_mode=verifier)
            draft = SimpleNamespace(target_layer_ids=[0], args=SimpleNamespace(layer_types=[]))
            kwargs = dict(target_model=None, draft_model=draft,
                draft_backend=SimpleNamespace(make_cache=lambda **_: []),
                target_ops=SimpleNamespace(make_cache=lambda *a, **k: [self.Cache(bits=self.bits), gdn]),
                supports_prefix_snapshot=True, allow_full_context_draft_layers=False,
                max_new_tokens=10, prefix_snapshot=saved, quantize_kv_cache=True,
                target_fa_window=0, runtime_context=context)
            session = SpeculativeSession.open(prompt_tokens=list(saved.token_ids) + [99], **kwargs)
            self.assertEqual(session.snap_prefix_len, saved.prefix_len)
            self.assertEqual(session.target_cache[0].offset, saved.prefix_len)
            self.assertTrue(session.quantize_kv_cache)
            session = SpeculativeSession.open(prompt_tokens=[99] + list(saved.token_ids), **kwargs)
            self.assertEqual(session.snap_prefix_len, 0)

    def test_native_qwen_forward_after_snapshot(self):
        from mlx_lm.models.qwen3_5 import TextModel, TextModelArgs
        from dflash_mlx.engine.target_qwen_gdn import QwenGdnTargetOps
        from dflash_mlx.cache.fingerprints import DFlashPrefixKey
        mx = self.mx
        mx.random.seed(7)
        model = TextModel(TextModelArgs(model_type="qwen3_5_text", hidden_size=128,
            intermediate_size=256, num_hidden_layers=4, num_attention_heads=2,
            num_key_value_heads=1, head_dim=64, vocab_size=64,
            linear_num_value_heads=2, linear_num_key_heads=1,
            linear_key_head_dim=64, linear_value_head_dim=64,
            full_attention_interval=2))
        model.set_dtype(mx.float16)
        ops = QwenGdnTargetOps()
        def make():
            return ops.make_cache(model, enable_speculative_linear_cache=True, quantize_kv_cache=True)
        cache = make()
        self.assertTrue(all(c.bits == self.bits for c in cache if hasattr(c, "bits")))
        tokens = mx.array([[1, 2, 3, 4, 5]])
        logits = model(tokens, cache=cache)
        mx.eval(logits, [c.state for c in cache])
        saved = self.codecs.build_snapshot(token_ids=[1, 2, 3, 4, 5], target_cache=cache,
            target_hidden=mx.ones((1, 5, 32)), last_logits=logits[:, -1],
            key=DFlashPrefixKey("tiny-qwen", "draft", (0,), 0, 32, "0"*64, "1"*64),
            adopt_cache_arrays=True)
        restored = self.codecs.hydrate_target_cache(saved, make())
        for suffix in ([6, 7, 8], [9]):
            a = model(mx.array([suffix]), cache=cache)
            b = model(mx.array([suffix]), cache=restored)
            self.assertTrue(mx.allclose(a, b, atol=1e-3, rtol=1e-3).item())
            self.assertEqual(mx.argmax(a[:, -1]).item(), mx.argmax(b[:, -1]).item())

    def test_engine_context_and_prefix_identity(self):
        from omlx.engine.dflash import DFlashEngine
        from dflash_mlx.server.prefix_cache_flow import build_prefix_key
        engine = SimpleNamespace(_resolve_dflash_l2_dir=lambda:None,
            _in_memory_cache_enabled=True, _in_memory_cache_max_entries=1,
            _in_memory_cache_max_bytes=1024**3, _draft_window_size=32,
            _draft_sink_size=0, _verify_mode="adaptive")
        ctx = DFlashEngine._build_runtime_context(engine)
        self.assertTrue(ctx.runtime.quantize_kv_cache)
        self.assertEqual(ctx.runtime.prefill_step_size, 128)
        self.assertTrue(ctx.runtime.prefix_cache)
        provider = SimpleNamespace(model_key=("target", None, "draft"),
            tokenizer=SimpleNamespace(chat_template="test", eos_token_id=2, bos_token_id=1),
            cli_args=None)
        key = build_prefix_key(provider, SimpleNamespace(target_layer_ids=[0]), ctx)
        self.assertTrue(key.target_model_id.endswith(f":launcher-kv-v1-q{self.bits}-g64"))
        from dflash_mlx import runtime
        from dflash_mlx.server.prefix_cache_flow import PrefixCacheFlow
        engine._model_name = "target"
        engine._draft_model_path = "draft"
        engine._target_model = engine._target_ops = engine._draft_model = None
        engine._draft_backend = None
        engine._executor_tokenizer = provider.tokenizer
        engine._runtime_context = ctx
        engine._suppress_token_ids = set()
        engine._block_size = 5
        flow = SimpleNamespace(snapshot=None, snapshot_service=None, stable_prefix_len=0,
            cache_active=True, publish_generation_snapshot=True, hit_kind="miss")
        with patch.object(PrefixCacheFlow, "for_request", return_value=flow), \
                patch.object(runtime, "stream_dflash_generate", return_value=iter(())) as stream:
            DFlashEngine._stream_dflash_events(engine, [1, 2], 4)
        self.assertTrue(stream.call_args.kwargs["quantize_kv_cache"],
                        "The generation call must not silently default back to full precision")
        self.assertIs(stream.call_args.kwargs["runtime_context"], ctx)
        engine._verify_mode = "ddtree"
        with self.assertRaisesRegex(ValueError, "DDTree"):
            DFlashEngine._build_runtime_context(engine)


if __name__ == "__main__": unittest.main()
