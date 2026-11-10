"""Synthetic native Q6 cache-aware sweep exactness and IO regression fixture."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime_patches/kolibri"))
import mlx.core as mx
import numpy as np
from streamlx.integrate import StreamingSwitchGLU
from streamlx.pool import StreamingSwitchMLP
from streamlx.reader import ExpertReader
from streamlx.stindex import PARTS, PROJS, SafetensorsIndex


def run():
    mx.set_cache_limit(16 * 2**20)
    mx.set_memory_limit(512 * 2**20)
    mx.set_wired_limit(512 * 2**20)
    mx.random.seed(23)
    with tempfile.TemporaryDirectory(prefix="kolibri-native-sweep-") as directory:
        root = Path(directory)
        weights = {}
        for projection in PROJS:
            incoming, outgoing = (128, 128)
            source = mx.random.normal((16, outgoing, incoming)).astype(mx.bfloat16)
            packed, scales, biases = mx.quantize(source, group_size=64, bits=6)
            for part, value in zip(PARTS, (packed, scales, biases)):
                weights[f"model.layers.0.mlp.experts.{projection}.{part}"] = value
        mx.eval(weights)
        mx.save_safetensors(str(root / "model-00001-of-00001.safetensors"), weights)
        (root / "config.json").write_text(json.dumps({"quantization":{"bits":6,"group_size":64}}))
        index = SafetensorsIndex(directory)
        results = []
        regular = np.array([[[i % 16, (i * 3 + 1) % 16] for i in range(32)]],dtype=np.uint32)
        skewed = np.random.default_rng(23).choice(16,size=(2,37,4),
                                                  p=np.arange(1,17)/136).astype(np.uint32)
        all_resident = np.array([[[i % 8, (i * 3 + 1) % 8] for i in range(32)]],dtype=np.uint32)
        # Direct invocation for a fitting union must also remain exact and
        # read-free. Nonuniform counts exercise final warm-cache selection.
        cases = [("cold",[],regular,True,3),
                 ("interleaved-resident",[0,2,4,6,8,10,12,14],regular,True,3),
                 ("contiguous-resident",list(range(8)),regular,True,3),
                 ("all-resident",list(range(8)),all_resident,True,3),
                 ("batched-count-skew",[0,2,4,6,8,10,12,14],skewed,True,1),
                 ("no-warm",[0,2,4,6,8,10,12,14],skewed,False,3),
                 ("wide-batch",[0,2,4,6,8,10,12,14],skewed,True,16)]
        cases = [(*case,"lru") for case in cases]
        cases.append(("s3fifo-legacy",[0,2,4,6,8,10,12,14],regular,True,3,"s3fifo"))
        for label, initial_ids, idx, warm, batch, policy in cases:
            x = mx.random.normal((*idx.shape[:2],128)).astype(mx.bfloat16)
            checked = []
            for path_label in ("baseline","cached"):
                reader = ExpertReader(index,workers=3,merge_gap=0)
                pool = StreamingSwitchMLP(directory,0,8,index=index,reader=reader)
                pool.policy = policy
                if policy == "s3fifo":
                    # Seed the legacy policy one row at a time: its small
                    # FIFO can reject earlier rows of a cold multi-row batch.
                    for expert in initial_ids:
                        pool.ensure([expert])
                else:
                    pool.ensure(initial_ids)
                mx.eval([pool.pool[p][q] for p in PROJS for q in PARTS])
                pool.reset_stats(); reader.reset_stats()
                wrapper = StreamingSwitchGLU(pool)
                wrapper.sweep_batch = batch
                wrapper.sweep_warm = warm
                begin = time.perf_counter()
                previous = os.environ.get("STREAMLX_PREFILL_CACHE")
                os.environ["STREAMLX_PREFILL_CACHE"] = "0" if path_label == "baseline" else "1"
                try:
                    y = wrapper._expert_sweep(x,idx)
                finally:
                    if previous is None:
                        os.environ.pop("STREAMLX_PREFILL_CACHE",None)
                    else:
                        os.environ["STREAMLX_PREFILL_CACHE"] = previous
                mx.eval(y)
                checked.append({"y":y,"ids":list(pool.id2slot),
                                "slots":dict(pool.id2slot),
                                "seconds":time.perf_counter()-begin,
                                "bytesRead":reader.bytes_read,"usefulBytes":reader.useful_bytes,
                                "pool":{p:{q:pool.pool[p][q] for q in PARTS} for p in PROJS}})
                reader.close()
                if wrapper._sweep_ex is not None:
                    wrapper._sweep_ex.shutdown(wait=True)
            assert bool(mx.array_equal(checked[0]["y"],checked[1]["y"]).item()), "Q6 expert outputs changed"
            assert checked[0]["ids"] == checked[1]["ids"], (initial_ids,checked[0]["ids"],checked[1]["ids"])
            # Slots can differ, but every final cached expert's original
            # packed tensors must be exact in its assigned slot.
            baseline, cached = checked
            for value in checked:
                for expert, slot in value["slots"].items():
                    for projection in PROJS:
                        for part in PARTS:
                            key = f"model.layers.0.mlp.experts.{projection}.{part}"
                            assert bool(mx.array_equal(value["pool"][projection][part][slot],
                                                       weights[key][expert]).item()), "cached Q6 bytes changed"
            union = set(int(e) for e in idx.reshape(-1))
            expected_fraction = len(union-set(initial_ids))/len(union) if policy == "lru" else 1
            assert cached["usefulBytes"] == baseline["usefulBytes"] * expected_fraction
            results.append({"scenario":label,"initialResidentExperts":len(initial_ids),
                            "sweepBatch":batch,"sweepWarm":warm,"routedShape":list(idx.shape),
                            "evictionPolicy":policy,
                            "bitwiseQ6Output":True,"sameWarmExpertOrder":True,
                            "baselineBytes":baseline["bytesRead"],"cachedBytes":cached["bytesRead"],
                            "baselineSeconds":baseline["seconds"],"cachedSeconds":cached["seconds"]})
        # A gathered view is immutable even if the original pool wrapper is
        # updated before the lazy view is materialized. No tensor precision
        # conversion takes place in the candidate resident path.
        source = mx.arange(32,dtype=mx.uint32).reshape(4,8)
        before = source[2]
        source[2] = mx.zeros((8,),dtype=mx.uint32)
        mx.eval(source,before)
        assert bool(mx.array_equal(before,mx.arange(16,24,dtype=mx.uint32)).item())
        return {"measurement":"Synthetic native Q6 expert-major sweep; no checkpoint/model inference", 
                "engineInferenceMeasured":False,"peakMlxMemoryBytes":mx.get_peak_memory(),"checks":results}


if __name__ == "__main__":
    print(json.dumps(run(),indent=2))
