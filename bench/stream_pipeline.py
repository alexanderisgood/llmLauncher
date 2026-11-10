#!/usr/bin/env python3
"""Reproduce isolated streaming costs without loading or changing any model.

Comparisons change one algorithm at a time: duplicate JSON decoding, scanning
an unfinished event from byte zero, or concatenating growing output strings.
These are relay CPU measurements, never model tokens/second measurements.
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
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from response_metrics import ResponseMetrics
from responses_bridge import ChatStreamBridge, ToolTarget
from sse_framing import EventScanner, pop_event


def event(value):
    return b"data: " + json.dumps(value, separators=(",", ":")).encode() + b"\n\n"


def compare(before, after, repeats):
    times = {"formerAlgorithmMs": [], "currentAlgorithmMs": []}
    for _ in range(repeats):
        for name, operation in (("formerAlgorithmMs", before), ("currentAlgorithmMs", after)):
            start = time.perf_counter()
            operation()
            times[name].append((time.perf_counter() - start) * 1000)
    medians = {key: round(statistics.median(value), 3) for key, value in times.items()}
    return {**medians, "speedRatio": round(medians["formerAlgorithmMs"] / medians["currentAlgorithmMs"], 3),
            "samplesMs": {key: [round(value, 3) for value in values] for key, values in times.items()}}


def run(repeats):
    metadata_wire = b"".join(event({"choices": [{"delta": {"content": f"fragment {index}"}}]})
                             for index in range(20000))

    def metadata(reuse):
        metrics = ResponseMetrics("chat-completions", "text/event-stream")
        if not reuse:
            metrics._decoder.loads = json.loads
            metrics.outcome.decoder = json.loads
        for start in range(0, len(metadata_wire), 16 * 1024):
            metrics.feed(metadata_wire[start:start + 16 * 1024])

    large_event = b"data: " + b"x" * (4 * 1024 * 1024) + b"\n\n"

    def scan(incremental):
        pending = bytearray()
        scanner = EventScanner()
        pop = scanner.pop if incremental else pop_event
        for start in range(0, len(large_event), 4096):
            pending.extend(large_event[start:start + 4096])
            pop(pending)

    # Reproduce the previous += behavior while holding parsing/encoding fixed.
    class ConcatenatingBridge(ChatStreamBridge):
        def _retain(self, parts, value):
            if parts:
                parts[0] += value
            else:
                parts.append(value)
            return True

    request = SimpleNamespace(model="synthetic-qwen", output_limit=100000,
                              by_wire_name={"inspect": ToolTarget(None, "inspect")})
    tool_wire = b"".join([
        event({"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call-1",
                 "function": {"name": "inspect"}}]}}]}),
        *[event({"choices": [{"delta": {"tool_calls": [{"index": 0,
                  "function": {"arguments": "x" * 128}}]}}]}) for _ in range(20000)],
        event({"choices": [{"finish_reason": "tool_calls"}]}),
    ])

    def bridge(linear):
        stream = (ChatStreamBridge if linear else ConcatenatingBridge)(request)
        for start in range(0, len(tool_wire), 16 * 1024):
            stream.feed(tool_wire[start:start + 16 * 1024])
        stream.finish()

    return {"version": 1, "measuredAt": datetime.now(timezone.utc).isoformat(),
            "platform": platform.platform(), "python": platform.python_version(),
            "repeats": repeats, "engineInferenceMeasured": False,
            "scope": "Synthetic relay CPU only; isolated algorithms, not end-to-end inference benchmarks",
            "metadata20000Events": compare(lambda: metadata(False), lambda: metadata(True), repeats),
            "scan4MiBIn4KiBReads": compare(lambda: scan(False), lambda: scan(True), repeats),
            "toolArguments20000Fragments": compare(lambda: bridge(False), lambda: bridge(True), repeats)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    result = run(args.repeats)
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
