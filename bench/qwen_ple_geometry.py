#!/usr/bin/env python3
"""Compare exact PLE vocabulary construction without loading a model.

The former constructor restarted enumeration for every head. The current
constructor enumerates the identical prime sequence once and shares it across
heads. These are checkpoint-inspection timings, never inference TPS claims.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import statistics
import sys
import time
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import qwen_ple


def repeated_nth_primes(start: int, count: int) -> list[int]:
    return [qwen_ple._qwen4_ple_nth_prime_after(start, index + 1) for index in range(count)]


def run(repeats: int) -> dict:
    config = {"text_config": {
        "num_hidden_layers": 48, "hidden_size": 2048, "vocab_size": 151936,
        "ple_embed_dim": 2048, "ple_layer_ids": list(range(1, 33)),
        "layer_types": ["linear_attention"] * 48, "eos_token_id": [151645],
        "ngram_size": 3, "heads_per_ngram": 8, "split_ngram_parts": 128,
    }}
    current = qwen_ple._qwen4_ple_geometry(config)
    if current[0] is None:
        raise RuntimeError(current[1])
    with mock.patch.object(qwen_ple, "_qwen4_ple_primes_after", side_effect=repeated_nth_primes):
        former = qwen_ple._qwen4_ple_geometry(config)
    if former != current:
        raise RuntimeError("PLE constructor geometry changed")
    samples = {"formerConstructorMs": [], "currentConstructorMs": []}
    for _ in range(repeats):
        for name, former_algorithm in (("formerConstructorMs", True), ("currentConstructorMs", False)):
            start = time.perf_counter()
            if former_algorithm:
                with mock.patch.object(qwen_ple, "_qwen4_ple_primes_after", side_effect=repeated_nth_primes):
                    result = qwen_ple._qwen4_ple_geometry(config)
            else:
                result = qwen_ple._qwen4_ple_geometry(config)
            samples[name].append((time.perf_counter() - start) * 1000)
            if result != current:
                raise RuntimeError("PLE geometry changed during measurement")
    medians = {name: round(statistics.median(values), 3) for name, values in samples.items()}
    return {
        "version": 1, "measuredAt": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "python": platform.python_version(),
        "scope": "Synthetic Qwen4 PLE checkpoint geometry constructor only; identical prime vocabularies, padding and sharding",
        "engineInferenceMeasured": False, "pleLayers": 32, "ngramHeadsPerLayer": 16,
        "repeats": repeats, "identicalGeometry": True, **medians,
        "speedRatio": round(medians["formerConstructorMs"] / medians["currentConstructorMs"], 3),
        "samplesMs": {name: [round(value, 3) for value in values] for name, values in samples.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeat count must be positive")
    encoded = json.dumps(run(args.repeats), indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
