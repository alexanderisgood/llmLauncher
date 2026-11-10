"""Native cached-sweep A/B over a bounded set of original Kolibri Q6 rows.

Loads a few expert rows, never the full model. Both paths use identical fixed
router indices, BF16 inputs, original Q6 bytes, sweep batch and warming policy.
This isolates prefill expert IO+math; it is not a full-model tokens/s result.
Coordinate with other native model benchmarks before running this script.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time

import mlx.core as mx
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT / "runtime_patches/kolibri"))
from bench.harness import BenchLock
from streamlx.integrate import StreamingSwitchGLU
from streamlx.pool import StreamingSwitchMLP
from streamlx.prefill import CACHE_SWEEP_VERSION
from streamlx.reader import ExpertReader
from streamlx.stindex import PARTS, PROJS, SafetensorsIndex


def run(model, layer=0, repeats=16, token_count=64, sweep_batch=16):
    mx.set_cache_limit(32 * 2**20)
    mx.set_memory_limit(1024 * 2**20)
    mx.set_wired_limit(1024 * 2**20)
    index = SafetensorsIndex(str(model))
    triples = index.switch_triples(layer)
    incoming, _, bits, group_size = index.quant_params(triples["up_proj"])
    if bits != 6 or group_size != 64:
        raise ValueError("This benchmark requires original affine Q6/group64 experts.")
    mx.random.seed(29)
    x = mx.random.normal((1,token_count,incoming)).astype(mx.bfloat16)
    idx = np.array([[[ (i+j*3) % 16 for j in range(6)] for i in range(token_count)]],dtype=np.uint32)
    mx.eval(x)
    records = {"baseline":[],"cached":[]}
    exact_output = None
    for attempt in range(repeats + 3):
        labels = ("baseline","cached") if attempt % 2 == 0 else ("cached","baseline")
        checked = {}
        for label in labels:
            reader = ExpertReader(index)
            pool = StreamingSwitchMLP(str(model),layer,8,index=index,reader=reader)
            wrapper = StreamingSwitchGLU(pool)
            wrapper.sweep_batch = sweep_batch
            pool.ensure([0,2,4,6,8,10,12,14])
            mx.eval([pool.pool[p][q] for p in PROJS for q in PARTS])
            reader.reset_stats(); pool.reset_stats()
            previous = os.environ.get("STREAMLX_PREFILL_CACHE")
            os.environ["STREAMLX_PREFILL_CACHE"] = "0" if label == "baseline" else "1"
            try:
                begin = time.perf_counter_ns()
                output = wrapper._expert_sweep(x,idx)
                mx.eval(output)
                elapsed_ns = time.perf_counter_ns() - begin
            finally:
                if previous is None:
                    os.environ.pop("STREAMLX_PREFILL_CACHE",None)
                else:
                    os.environ["STREAMLX_PREFILL_CACHE"] = previous
            checked[label] = (output,list(pool.id2slot))
            if attempt >= 3:
                records[label].append({"microseconds":elapsed_ns/1000,
                                       "logicalPreadBytes":reader.bytes_read,
                                       "usefulExpertBytes":reader.useful_bytes,"preadCalls":reader.reads})
            reader.close()
            if wrapper._sweep_ex is not None:
                wrapper._sweep_ex.shutdown(wait=True)
        assert bool(mx.array_equal(checked["baseline"][0],checked["cached"][0]).item()), "original Q6 outputs changed"
        assert checked["baseline"][1] == checked["cached"][1], "warm expert ordering changed"
        exact_output = checked["cached"][0]
    summary = {}
    for label, values in records.items():
        summary[label] = {"medianMicroseconds":statistics.median(v["microseconds"] for v in values),
                          "medianLogicalPreadBytes":statistics.median(v["logicalPreadBytes"] for v in values),
                          "medianUsefulExpertBytes":statistics.median(v["usefulExpertBytes"] for v in values),
                          "medianPreadCalls":statistics.median(v["preadCalls"] for v in values)}
    return {"version":1,"measuredAt":datetime.now(timezone.utc).isoformat(),
            "measurement":"Native original Q6 expert prefill sweep IO+gather_qmm, fixed router indices",
            "engineInferenceMeasured":False,"physicalSsdTrafficMeasured":False,
            "modelPath":str(model.resolve()),"layer":layer,
            "cacheSweepVersion":CACHE_SWEEP_VERSION,"routedShape":list(idx.shape),
            "poolSlots":8,"routedExperts":16,"residentRoutedExperts":8,
            "prefillChunkTokens":token_count,
            "sweepBatch":sweep_batch,"sweepWarm":True,"qbits":bits,"groupSize":group_size,
            "inputDtype":"bfloat16","outputBitwiseEqual":True,"warmExpertOrderEqual":True,
            "outputSha256":hashlib.sha256(np.array(exact_output.view(mx.uint16)).tobytes()).hexdigest(),
            "peakMlxMemoryBytes":mx.get_peak_memory(),"repeatsPerPath":repeats,
            "sourceSha256":{name:hashlib.sha256((ROOT / "runtime_patches/kolibri/streamlx" / name).read_bytes()).hexdigest()
                            for name in ("prefill.py","integrate.py","pool.py","reader.py","stindex.py")},
            "readPolicy":{"workers":6,"mergeGapBytes":64*1024,"maxSpanBytes":16*1024*1024},
            "limitations":["No full model, attention, KV cache or generation loop was loaded.",
                           "Router picks are fixed for the experiment; no model routing is approximated in runtime.",
                           "Repeated reads can be served by the OS page cache; logical bytes are not physical SSD traffic.",
                           "No full-model prefill/decode tokens-per-second or accuracy claim follows from this fixture."],
            "summary":summary,"medianSpeedup":summary["baseline"]["medianMicroseconds"]/summary["cached"]["medianMicroseconds"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model",type=Path,required=True)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--repeats",type=int,default=16)
    parser.add_argument("--layer",type=int,default=0)
    parser.add_argument("--tokens",type=int,default=64)
    parser.add_argument("--sweep-batch",type=int,default=16)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 100 or not 1 <= args.tokens <= 2048 or not 1 <= args.sweep_batch <= 32:
        parser.error("Use bounded repeats1–100, tokens1–2048, sweep batch1–32.")
    with BenchLock("Kolibri original Q6 rows cache-aware prefill",wait_seconds=60):
        result = run(args.model,args.layer,args.repeats,args.tokens,args.sweep_batch)
    encoded = json.dumps(result,indent=2)
    if args.output:
        args.output.write_text(encoded+"\n")
    print(encoded)
