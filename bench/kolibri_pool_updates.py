"""Measure native expert-slot update graphs, without loading checkpoint weights.

Compare the current row-at-a-time assignment with one batched scatter per
projection/part. This measures exact pool maintenance, not model tokens/s.
Run with the qualified Kolibri Python; random Q6 tensors fit below 300 MiB.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys
import time

import mlx.core as mx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime_patches/kolibri"))
from streamlx.pool import switch_forward
from streamlx.stindex import PARTS, PROJS


def row_updates(pool, rows, slots):
    for row, slot in zip(rows, slots):
        for projection in PROJS:
            for part in PARTS:
                pool[projection][part][slot] = row[projection][part]


def batch_updates(pool, rows, slots):
    indices = mx.array(slots, dtype=mx.uint32)
    for projection in PROJS:
        for part in PARTS:
            values = mx.stack([row[projection][part] for row in rows])
            pool[projection][part][indices] = values


def arrays(pool):
    return [pool[p][q] for p in PROJS for q in PARTS]


def run(slots=108, repeats=100, hidden=640, intermediate=128):
    mx.set_cache_limit(32 * 2**20)
    mx.set_memory_limit(2 * 2**30)
    mx.set_wired_limit(2 * 2**30)
    mx.random.seed(21)
    qparams, initial, rows = {}, {}, [{} for _ in range(6)]
    for projection in PROJS:
        inputs, outputs = ((hidden, intermediate) if projection != "down_proj"
                           else (intermediate, hidden))
        qparams[projection] = (inputs, outputs, 6, 64)
        weight = mx.random.normal((slots, outputs, inputs)).astype(mx.bfloat16)
        packed, scales, biases = mx.quantize(weight, group_size=64, bits=6)
        initial[projection] = dict(zip(PARTS, (packed, scales, biases)))
        for i in range(6):
            rows[i][projection] = {part: initial[projection][part][slots - 1 - i]
                                   for part in PARTS}
    mx.eval(arrays(initial), [[r[p][q] for p in PROJS for q in PARTS] for r in rows])
    x = mx.random.normal((1, 1, hidden)).astype(mx.bfloat16)
    target_slots = [0, 2, 3, 5, 7, 11]
    records = []
    for count in (1, 3, 6):
        checked = []
        for update in (row_updates, batch_updates):
            pool = {p: dict(initial[p]) for p in PROJS}
            update(pool, rows[:count], target_slots[:count])
            mx.eval(arrays(pool))
            output = switch_forward(x, mx.array([[target_slots[:count]]], dtype=mx.uint32), pool, qparams)
            mx.eval(output)
            checked.append((pool, output))
        assert all(bool(mx.array_equal(checked[0][0][p][q], checked[1][0][p][q]).item())
                   for p in PROJS for q in PARTS), "pool bytes changed"
        assert bool(mx.array_equal(checked[0][1], checked[1][1]).item()), "Q6 gather output changed"
        timings = {}
        for label, update in (("row", row_updates), ("batch", batch_updates)):
            graph_ns, eval_ns = [], []
            for attempt in range(repeats + 10):
                pool = {p: dict(initial[p]) for p in PROJS}
                begin = time.perf_counter_ns()
                update(pool, rows[:count], target_slots[:count])
                dispatch = time.perf_counter_ns()
                mx.eval(arrays(pool))
                end = time.perf_counter_ns()
                if attempt >= 10:
                    graph_ns.append(dispatch - begin)
                    eval_ns.append(end - dispatch)
            timings[label] = {
                "medianGraphMicroseconds": statistics.median(graph_ns) / 1000,
                "medianEvalMicroseconds": statistics.median(eval_ns) / 1000,
                "medianTotalMicroseconds": statistics.median([a+b for a,b in zip(graph_ns, eval_ns)]) / 1000,
            }
        records.append({"missingExperts": count, "poolAndQ6OutputBitwiseEqual": True,
                        "timings": timings,
                        "medianTotalSpeedup": timings["row"]["medianTotalMicroseconds"] / timings["batch"]["medianTotalMicroseconds"]})
    return {"measuredAt": datetime.now(timezone.utc).isoformat(),
            "measurement": "Native Q6 expert pool update graph plus materialization",
            "engineInferenceMeasured": False, "python": sys.version.split()[0],
            "geometry": {"slots": slots,"hidden": hidden,"intermediate": intermediate},
            "peakMlxMemoryBytes": mx.get_peak_memory(), "records": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repeats", type=int, default=100)
    args = parser.parse_args()
    result = run(repeats=args.repeats)
    encoded = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(encoded + "\n")
    print(encoded)
