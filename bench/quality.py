#!/usr/bin/env python3
"""Deterministic quality probes for engine A/B comparisons.

Runs a fixed set of short greedy prompts against a live engine and records
content, token counts and hashes. Two runs are comparable when their hashes
match; a perf change that alters them is a quality regression until proven
otherwise.

Usage:

    python3 bench/quality.py --engine mtplx --model mtplx-27b-speed --label 27b-q82
    python3 bench/quality.py --engine slotstream --label flash-0200
    python3 bench/quality.py --compare results/<a>.json results/<b>.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness  # noqa: E402
import run as runner  # noqa: E402

PROBES = (
    {
        "id": "arithmetic",
        "prompt": "Compute (17 * 23) + (144 / 12). Reply with only the number.",
        "maxTokens": 32,
    },
    {
        "id": "json-tool",
        "prompt": (
            "Return exactly one JSON object with keys \"status\" and \"count\". "
            "status must be the string \"ready\" and count must be 3. No prose."
        ),
        "maxTokens": 48,
    },
    {
        "id": "code",
        "prompt": (
            "Write a Python function `bounded_add(a, b, limit)` that returns "
            "min(a + b, limit). Reply with the function only."
        ),
        "maxTokens": 96,
    },
    {
        "id": "recall",
        "prompt": (
            "Read this list: cobalt, ember, lattice, quartz, meadow. "
            "Reply with the third item only."
        ),
        "maxTokens": 16,
    },
)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("mtplx", "omlx", "slotstream", "llamacpp"))
    parser.add_argument("--model")
    parser.add_argument("--kv", default="q8")
    parser.add_argument("--context", type=int, default=131072)
    parser.add_argument("--profile", default="turbo")
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--port", type=int, default=harness.DEFAULT_PORT)
    parser.add_argument("--memory-gb", type=float, default=41.0)
    parser.add_argument("--label", default="quality")
    parser.add_argument("--extra-env", action="append")
    parser.add_argument("--attach", action="store_true")
    parser.add_argument("--no-lock", action="store_true")
    parser.add_argument("--compare", nargs=2, metavar=("A", "B"))
    args = parser.parse_args()

    if args.compare:
        return compare(args.compare[0], args.compare[1])
    if not args.engine:
        parser.error("--engine is required unless --compare is used")

    engine_args = argparse.Namespace(
        engine=args.engine,
        model=args.model,
        kv=args.kv,
        context=args.context,
        profile=args.profile,
        depth=args.depth,
        generation="mtp",
        max_response=1024,
        memory_gb=args.memory_gb,
        port=args.port,
        per_model_json=None,
        settings_json=None,
        mtp="on",
        batch=2048,
        ubatch=512,
        flash_attn="on",
        extra_arg=None,
        extra_env=args.extra_env,
        memory_auto=False,
        max_ram_percent=None,
        binary=None,
    )
    engine = runner.build_engine(engine_args)

    import contextlib

    lock = contextlib.nullcontext() if args.no_lock else harness.bench_run(
        f"quality {args.label}", minimum_headroom_gb=20.0,
    )
    payload: dict = {
        "label": args.label,
        "engine": args.engine,
        "kv": args.kv,
        "startedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "command": engine.command_line(),
        "probes": [],
    }
    with lock:
        if not args.attach:
            engine.start()
        try:
            engine.wait_ready()
            for probe in PROBES:
                effort = None if args.engine == "mtplx" else "none"
                result = harness.stream_chat(
                    engine,
                    probe["prompt"],
                    max_tokens=probe["maxTokens"],
                    temperature=0.0,
                    seed=42,
                    reasoning_effort=effort,
                )
                content = result["content"].strip()
                payload["probes"].append({
                    "id": probe["id"],
                    "content": content,
                    "sha256": digest(content),
                    "promptTokens": result["promptTokens"],
                    "completionTokens": result["completionTokens"],
                    "decodeTokensPerSecond": result["decodeTokensPerSecond"],
                })
                print(f"[quality] {probe['id']}: {content[:120]!r} "
                      f"({result['completionTokens']} tokens)", flush=True)
        finally:
            if not args.attach:
                engine.stop()
    path = harness.write_result(f"quality-{args.label}", payload)
    print(f"[quality] wrote {path}")
    return 0


def compare(path_a: str, path_b: str) -> int:
    a = json.loads(pathlib.Path(path_a).read_text())
    b = json.loads(pathlib.Path(path_b).read_text())
    probes_a = {probe["id"]: probe for probe in a["probes"]}
    probes_b = {probe["id"]: probe for probe in b["probes"]}
    mismatches = 0
    for probe_id in sorted(set(probes_a) | set(probes_b)):
        left = probes_a.get(probe_id)
        right = probes_b.get(probe_id)
        if left is None or right is None:
            print(f"{probe_id}: MISSING ({'A' if left is None else 'B'})")
            mismatches += 1
            continue
        same = left["sha256"] == right["sha256"]
        shared = 0
        for x, y in zip(left["content"], right["content"]):
            if x != y:
                break
            shared += 1
        print(f"{probe_id}: {'IDENTICAL' if same else 'DIFFERS'} "
              f"(shared prefix {shared}/{max(len(left['content']), len(right['content']))} chars)")
        if not same:
            mismatches += 1
    print(f"[quality] {mismatches} differing probe(s)")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
