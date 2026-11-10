#!/usr/bin/env python3
"""Measure Kolibri expert-range planning CPU costs without MLX or model weights.

Replays the former shape-product and list-copy algorithms against the current
runtime implementations. Offsets use Kolibri's Q6 tensor geometry. Each case
checks identical ranges and coalesced spans before timing. No disk reads, GPU
computation, model output or inference tokens/second are measured.
"""
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from math import prod
from pathlib import Path
import platform
import statistics
import sys
from time import perf_counter_ns
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "runtime_patches/kolibri/streamlx"


def load_geometry():
    """Import the standard-library-only tensor metadata implementation."""
    name = "_kolibri_benchmark_geometry"
    spec = importlib.util.spec_from_file_location(name, VENDOR / "stindex.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load Kolibri tensor metadata.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_planner():
    """Compile only the live CPU planner, avoiding MLX/NumPy module imports."""
    source = VENDOR / "reader.py"
    tree = ast.parse(source.read_text(), filename=str(source))
    owner = next(node for node in tree.body
                 if isinstance(node, ast.ClassDef) and node.name == "ExpertReader")
    method = next(node for node in owner.body
                  if isinstance(node, ast.FunctionDef) and node.name == "_plan")
    module = ast.Module(body=[method], type_ignores=[])
    namespace = {}
    exec(compile(module, str(source), "exec"), namespace)
    return namespace["_plan"]


geometry = load_geometry()
current_plan = load_planner()


@dataclass(frozen=True)
class PreviousTensorLoc:
    """The exact former uncached tensor-row geometry algorithm."""
    path: str
    abs_start: int
    nbytes: int
    dtype: str
    shape: tuple
    name: str = ""

    @property
    def row_stride(self):
        return prod(self.shape[1:]) * geometry.DTYPE_SIZE[self.dtype]

    def expert_range(self, expert):
        if not 0 <= expert < self.shape[0]:
            raise IndexError(f"expert {expert} out of range {self.shape[0]}")
        return self.path, self.abs_start + expert * self.row_stride, self.row_stride


def previous_plan(planner, requests):
    """The exact former list-copy coalescing algorithm."""
    spans = []
    for key, path, offset, size in sorted(requests, key=lambda item: (item[1], item[2])):
        if spans:
            old_path, old_offset, old_size, members = spans[-1]
            gap = offset - (old_offset + old_size)
            if (path == old_path and 0 <= gap <= planner.merge_gap
                    and offset + size - old_offset <= planner.max_span):
                spans[-1] = (old_path, old_offset, offset + size - old_offset,
                             members + [(key, offset - old_offset, size)])
                continue
        spans.append((path, offset, size, [(key, 0, size)]))
    return spans


def tensor_locations():
    current, previous = {}, {}
    offset = 8
    for projection in geometry.PROJS:
        current[projection], previous[projection] = {}, {}
        for part in geometry.PARTS:
            weight = part == "weight"
            shape = ((384, 2560, 96 if weight else 8) if projection == "down_proj"
                     else (384, 512, 480 if weight else 40))
            dtype = "U32" if weight else "BF16"
            size = prod(shape) * geometry.DTYPE_SIZE[dtype]
            arguments = ("synthetic-shard", offset, size, dtype, shape)
            current[projection][part] = geometry.TensorLoc(*arguments)
            previous[projection][part] = PreviousTensorLoc(*arguments)
            offset += size
    return current, previous


def requests_for(experts, triples):
    requests = []
    for expert in experts:
        for projection in geometry.PROJS:
            for part in geometry.PARTS:
                path, offset, size = triples[projection][part].expert_range(expert)
                requests.append(((expert, projection, part), path, offset, size))
    return requests


def measure(operation, samples):
    for _ in range(20):
        operation()
    durations = []
    for _ in range(samples):
        start = perf_counter_ns()
        operation()
        durations.append((perf_counter_ns() - start) / 1000)
    return {
        "iterations": samples,
        "medianMicroseconds": round(statistics.median(durations), 3),
        "p95Microseconds": round(sorted(durations)[max(0, int(samples * .95) - 1)], 3),
    }


def run(samples=1000):
    current, previous = tensor_locations()
    planner = SimpleNamespace(merge_gap=64 * 1024, max_span=16 * 1024 * 1024)
    scenarios = []
    for label, experts in (
        ("decode-six", [3, 100, 239, 311, 380, 44]),
        ("prefill-sweep-batch16", list(range(16))),
        ("prefill-cache-union189", list(range(189))),
        ("full-cache-union384", list(range(384))),
    ):
        requests = requests_for(experts, current)
        if requests_for(experts, previous) != requests:
            raise AssertionError(f"{label}: tensor byte ranges differ")
        if previous_plan(planner, requests) != current_plan(planner, requests):
            raise AssertionError(f"{label}: coalesced spans differ")
        before = measure(lambda: previous_plan(planner, requests_for(experts, previous)), samples)
        after = measure(lambda: current_plan(planner, requests_for(experts, current)), samples)
        scenarios.append({
            "scenario": label, "routedExperts": len(experts), "byteRanges": len(requests),
            "identicalRangesAndSpans": True, "previous": before, "optimized": after,
            "medianSpeedup": round(before["medianMicroseconds"] / after["medianMicroseconds"], 3),
        })
    return {
        "version": 1, "measuredAt": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "python": platform.python_version(),
        "engineInferenceMeasured": False,
        "measurement": "CPU expert-byte-range construction and planning only",
        "limitations": [
            "No model server or checkpoint was loaded.",
            "No disk reads, GPU computation, output quality or inference tokens-per-second measured.",
            "Synthetic offsets use validated Kolibri Q6 expert tensor geometry; actual routed sets and misses vary.",
            "Measures warmed geometry; results vary with host load and Python version.",
        ],
        "sourceSha256": {
            name: hashlib.sha256((VENDOR / name).read_bytes()).hexdigest()
            for name in ("reader.py", "stindex.py")
        },
        "scenarios": scenarios,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples must be positive")
    encoded = json.dumps(run(args.samples), indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
