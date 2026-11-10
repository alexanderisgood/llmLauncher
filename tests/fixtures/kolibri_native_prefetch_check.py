"""Tiny native Q6 full-logit proof for unqualified fetch-only scheduling."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT / "runtime_patches/kolibri"))
import mlx.core as mx
import mlx.nn as nn
import numpy as np
from mlx.utils import tree_flatten
from kolibri_adapter import register
from streamlx.integrate import install_streaming
from bench.kolibri_prefetch_variant import install


def run(variant):
    os.environ["STREAMLX_PREFETCH"] = "1" if variant in {"prefetch","bias-prefetch"} else "0"
    mx.set_cache_limit(16*1024**2); mx.set_memory_limit(512*1024**2); mx.set_wired_limit(512*1024**2)
    mx.random.seed(37)
    module = register()
    args = module.ModelArgs(model_type="kolibri1",hidden_size=128,num_hidden_layers=2,
        num_attention_heads=2,num_key_value_heads=1,head_dim=64,vocab_size=256,
        num_experts=8,num_experts_per_tok=2,moe_intermediate_size=128,
        shared_expert_intermediate_size=128,layer_types=["sliding_attention","full_attention"],sliding_window=5)
    model = module.Model(args); model.set_dtype(mx.bfloat16)
    nn.quantize(model,group_size=64,bits=6,class_predicate=lambda path,item:
                hasattr(item,"to_quantized") and model.quant_predicate(path,item))
    mx.eval(model.parameters())
    prompts = [mx.array([[i % 256 for i in range(17)]])]
    prompts += [mx.array([[(i*7+11)%256]]) for i in range(96)]
    baseline_cache = model.make_cache(); expected = []
    for prompt in prompts:
        output = model(prompt,cache=baseline_cache); mx.eval(output); expected.append(output)
    budget = install(variant,max_bytes=2*1024**2)
    with tempfile.TemporaryDirectory(prefix="kolibri-prefetch-native-") as directory:
        folder = Path(directory)
        cfg = asdict(args); cfg["quantization"] = {"bits":6,"group_size":64}
        (folder / "config.json").write_text(json.dumps(cfg))
        weights = {key.replace(".mlp.switch_mlp.",".mlp.experts."):value
                   for key,value in tree_flatten(model.parameters())}
        mx.save_safetensors(str(folder / "model-00001-of-00001.safetensors"),weights)
        pools,reader = install_streaming(model,directory,4)
        if budget is not None:
            first,second = model.layers[0],model.layers[1]
            wrapper = first.mlp.switch_mlp
            wrapper._pf_next = (pools[1],second.mlp.gate,first.post_attention_layernorm.weight,
                                second.post_attention_layernorm.weight)
            if variant == "bias-prefetch":
                wrapper._bench_prediction_bias = second.mlp.expert_bias
        trace = []
        for layer in model.layers:
            layer.mlp.switch_mlp.record_sink = trace
        cache = model.make_cache(); digest = hashlib.sha256()
        try:
            for prompt,gold in zip(prompts,expected):
                output = model(prompt,cache=cache); mx.eval(output)
                if not bool(mx.array_equal(output,gold).item()):
                    raise AssertionError(f"Unqualified {variant} changed true Q6 logits")
                digest.update(np.array(output.view(mx.uint8)).tobytes())
            for pool in pools.values():
                if pool._pf is not None and budget is not None:
                    budget.release(pool._pf[2]); pool._pf = None
            if budget is not None:
                budget.close()
            stats = budget.snapshot() if budget is not None else None
            if stats is not None:
                assert stats["outstanding"] == stats["reservedBytes"] == 0
                assert stats["peakOutstanding"] <= 2 and stats["peakReservedBytes"] <= 2*1024**2
            routes = hashlib.sha256()
            for layer,indices in trace:
                routes.update(str(layer).encode()); routes.update(indices.tobytes())
            return {"variant":variant,"qualified":False,"fullModelLoaded":False,
                    "exactLogits":True,"checks":len(prompts),"logitsSha256":digest.hexdigest(),
                    "routingSha256":routes.hexdigest(),"qbits":6,"nativeTopK":2,"slotsPerLayer":4,
                    "peakMlxMemoryBytes":mx.get_peak_memory(),"budget":stats,
                    "prefetchUsed":sum(pool.pf_used for pool in pools.values())}
        finally:
            if budget is not None:
                budget.close()
            reader.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant",required=True,choices=["qualified","no-overlap","prefetch","bias-prefetch"])
    args = parser.parse_args()
    print(json.dumps(run(args.variant),indent=2))
