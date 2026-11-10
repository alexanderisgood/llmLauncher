#!/usr/bin/env python3
"""Measure repeated model-header validation without loading model weights.

Both paths read and hash current headers and revalidate file/link/index state.
The comparison changes only bounded reuse of immutable validated descriptors.
It measures discovery CPU overhead, not engine inference or tokens per second.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tensor_inventory import HeaderCache, safetensors_inventory


def run(tensors: int, repeats: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="llm-launcher-header-benchmark-") as temporary:
        root = Path(temporary)
        header = json.dumps({
            f"model.layers.{index}.self_attn.q_proj.weight": {
                "dtype": "BF16", "shape": [2], "data_offsets": [index * 4, (index + 1) * 4],
            }
            for index in range(tensors)
        }, separators=(",", ":")).encode()
        shard = root / "model.safetensors"
        with shard.open("wb") as handle:
            handle.write(len(header).to_bytes(8, "little"))
            handle.write(header)
            handle.truncate(8 + len(header) + tensors * 4)
        cache = HeaderCache()
        uncached = safetensors_inventory(root, cache=None)
        warmed = safetensors_inventory(root, cache=cache)
        if not uncached[0] or uncached != warmed:
            raise RuntimeError("Cached and uncached structural receipts differ")
        samples: dict[str, list[float]] = {"repeatedFullValidationMs": [], "repeatedCachedValidationMs": []}
        for _ in range(repeats):
            for name, selected_cache in (("repeatedFullValidationMs", None), ("repeatedCachedValidationMs", cache)):
                start = time.perf_counter()
                result = safetensors_inventory(root, cache=selected_cache)
                elapsed = (time.perf_counter() - start) * 1000
                if result != uncached:
                    raise RuntimeError("File identity or structural receipt changed during measurement")
                samples[name].append(elapsed)
        medians = {key: round(statistics.median(values), 3) for key, values in samples.items()}
        return {
            "version": 1, "measuredAt": datetime.now(timezone.utc).isoformat(),
            "platform": platform.platform(), "python": platform.python_version(),
            "scope": "Synthetic safetensors metadata discovery CPU only; current headers still read and hashed on every call",
            "engineInferenceMeasured": False,
            "tensors": tensors, "headerBytes": len(header), "repeats": repeats,
            "identicalInventoryAndSourceReceipts": True, **medians,
            "speedRatio": round(medians["repeatedFullValidationMs"] / medians["repeatedCachedValidationMs"], 3),
            "samplesMs": {key: [round(value, 3) for value in values] for key, values in samples.items()},
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tensors", type=int, default=20_000)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.tensors < 1 or args.repeats < 1:
        parser.error("tensor count and repeat count must be positive")
    encoded = json.dumps(run(args.tensors, args.repeats), indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
