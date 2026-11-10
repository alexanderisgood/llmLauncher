"""Exercise hybrid Kolibri caches with the qualified native MLX Python.

Uses a tiny randomly initialized model, never the user's checkpoint weights.
"""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime_patches/kolibri"))
import mlx.core as mx
from mlx_lm.models.cache import KVCache, QuantizedKVCache, RotatingKVCache
from mlx_lm.models.base import scaled_dot_product_attention
from kolibri_adapter import register

mx.random.seed(7)
module = register()
args = module.ModelArgs(model_type="kolibri1", layer_types=["sliding_attention", "full_attention"],
                        vocab_size=256, hidden_size=128, num_hidden_layers=2,
                        num_attention_heads=4, num_key_value_heads=1, head_dim=128,
                        num_experts=8, num_experts_per_tok=2, moe_intermediate_size=32,
                        shared_expert_intermediate_size=32)
model = module.Model(args)
model.set_dtype(mx.bfloat16)
mx.eval(model.parameters())
tokens = mx.random.randint(0, 256, (1, 640))
baseline_cache = model.make_cache()
baseline = []
for start, end in ((0,128), (128,257), (257,514), (514,639), (639,640)):
    output = model(tokens[:,start:end], cache=baseline_cache)
    mx.eval(output)
    baseline.append(output)
assert baseline_cache[0].offset == baseline_cache[1].offset == 640

results = []
for bits in (8, 6, 4):
    module = register(kv_bits=bits)
    cache = model.make_cache()
    assert isinstance(cache[0], RotatingKVCache)
    assert isinstance(cache[1], QuantizedKVCache)
    assert cache[1].bits == bits and cache[1].group_size == 64
    errors = []
    for i, (start,end) in enumerate(((0,128),(128,257),(257,514),(514,639),(639,640))):
        output = model(tokens[:,start:end], cache=cache)
        mx.eval(output)
        error = float((mx.linalg.norm(output.astype(mx.float32)-baseline[i].astype(mx.float32)) /
                       mx.linalg.norm(baseline[i].astype(mx.float32))).item())
        # Tiny random MoE routers can change selected experts with small
        # attention perturbations; this checks execution, not model accuracy.
        assert error < .30, (bits, i, error)
        assert cache[0].offset == cache[1].offset == end
        assert cache[1].keys[0].shape[-1] == 128 * bits // 32
        errors.append(error)
    assert cache[0].keys.shape[2] == 513, cache[0].keys.shape
    assert cache[1].keys[1].dtype == mx.bfloat16
    # Prefix reuse deep-copies this hybrid state, then continues without
    # quantizing or trimming the rotating cache.
    saved = copy.deepcopy(cache)
    a = model(mx.array([[3]]), cache=cache)
    b = model(mx.array([[3]]), cache=saved)
    mx.eval(a,b)
    assert bool(mx.array_equal(a,b).item())
    full_geometry = SimpleNamespace(model=SimpleNamespace(sliding_window=513), layers=[
        SimpleNamespace(use_sliding=i % 5 != 4) for i in range(50)])
    full_cache = module.Model.make_cache(full_geometry)
    assert sum(isinstance(c, QuantizedKVCache) for c in full_cache) == 10
    assert sum(isinstance(c, RotatingKVCache) for c in full_cache) == 40
    # Isolate quantized attention from expert routing and test its numeric
    # error with a causal prefill mask and a subsequent decode token.
    direct_quant = model.make_cache()[1]
    direct_full = KVCache()
    attention_errors = []
    for count in (129,257,1):
        keys = mx.random.normal((1,1,count,128)).astype(mx.bfloat16)
        values = mx.random.normal((1,1,count,128)).astype(mx.bfloat16)
        queries = mx.random.normal((1,4,count,128)).astype(mx.bfloat16)
        mask = direct_full.make_mask(count,window_size=None,return_array=False)
        k,v = direct_full.update_and_fetch(keys,values)
        qk,qv = direct_quant.update_and_fetch(keys,values)
        full = scaled_dot_product_attention(queries,k,v,cache=direct_full,scale=128**-.5,mask=mask)
        quant = scaled_dot_product_attention(queries,qk,qv,cache=direct_quant,scale=128**-.5,mask=mask)
        mx.eval(full,quant)
        error = float((mx.linalg.norm(quant.astype(mx.float32)-full.astype(mx.float32)) /
                       mx.linalg.norm(full.astype(mx.float32))).item())
        assert error < {8:.025,6:.06,4:.25}[bits], (bits,count,error)
        attention_errors.append(error)
    results.append({"bits":bits,"tokens":641,"maxRelativeLogitError":max(errors),
                    "maxRelativeAttentionError":max(attention_errors),
                    "quantizedLayers":10,"slidingLayers":40,"prefixCopyPassed":True})

module = register()
cache = model.make_cache()
assert isinstance(cache[0],RotatingKVCache) and isinstance(cache[1],KVCache)

# Native prefill progress counts only the uncached suffix. Verify retained
# snapshots use absolute keys matching cache offsets, including the earlier
# boundary needed when the assistant-generation suffix changes next turn.
import serve as stream_server
class Retained:
    max_bytes = 1024**3
    def __init__(self): self.entries = []
    def insert_cache(self,key,tokens,cache,cache_type):
        assert all(c.offset == len(tokens) for c in cache)
        self.entries.append((list(tokens),cache))
lru = Retained()
cache = baseline_cache
assert all(c.offset == 640 for c in cache)
stream_server._STATE["fetch"] = (lru,"fixture-model",list(range(897)))
kwargs = {"prompt_cache":cache,"prompt":list(range(640,897)),"prefill_step_size":64}
stream_server._snapshot_progress(kwargs)
progress = kwargs["prompt_progress_callback"]
progress(0,257)
assert not lru.entries
for processed in (64,128,192,256):
    mx.eval(model(mx.zeros((1,64),dtype=mx.int32),cache=cache))
    progress(processed,257)
assert [len(tokens) for tokens,_ in lru.entries] == [768,896]
assert lru.entries[0][0] == list(range(768))
assert lru.entries[1][0] == list(range(896))
# The default 256-token chunk needs its earlier snapshot at offset 512,
# immediately before the final chunk crosses the 513-token rotating window.
register(kv_bits=8)
cache = model.make_cache()
lru = Retained()
stream_server._STATE["fetch"] = (lru,"fixture-model",list(range(758)))
kwargs = {"prompt_cache":cache,"prompt":list(range(758)),"prefill_step_size":256}
stream_server._snapshot_progress(kwargs)
for processed,count in ((256,256),(512,256),(757,245)):
    mx.eval(model(mx.zeros((1,count),dtype=mx.int32),cache=cache))
    kwargs["prompt_progress_callback"](processed,758)
assert [len(tokens) for tokens,_ in lru.entries] == [512,757]
print(json.dumps({"nativeCacheChecks":results,"fullPrecisionRestorePassed":True,
                  "hybridPrefixSnapshotsPassed":True}))
