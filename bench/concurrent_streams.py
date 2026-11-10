#!/usr/bin/env python3
"""Measure Splash aggregate decode with N concurrent streaming requests.

The single-stream harness (`bench/run.py`) answers "how fast is one chat?".
The engine's geometry caps how many request rows one batch may hold
(`maximum_batch_width` in the pack's manifest), so aggregate throughput is a
separate question — and for agent workloads (several subagents, several
sessions) it is the one that matters.

Usage::

    python3 bench/concurrent_streams.py --streams 4 --prompt-tokens 33000
    python3 bench/concurrent_streams.py --streams 4 --pack bench/derived/splash-bw8

Each stream asks the same prompt, so after the first request every stream
replays a cached prefix; both the per-stream and aggregate decode rates are
reported. One engine launch, one lock, one set of results per invocation.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import json
import pathlib
import sys
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness  # noqa: E402


def chat_stream(port: int, model: str, prompt: str, max_tokens: int, index: int) -> dict:
    """One greedy streaming completion; returns timing and token counts."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": True,
    }).encode()
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    started = time.time()
    first_token = None
    tokens = 0
    with urllib.request.urlopen(request, timeout=3600) as response:
        for raw in response:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            delta = json.loads(payload)["choices"][0].get("delta") or {}
            if delta.get("content") or delta.get("reasoning_content"):
                if first_token is None:
                    first_token = time.time()
                tokens += 1
    ended = time.time()
    decode_seconds = max(ended - (first_token or ended), 1e-9)
    return {
        "stream": index,
        "tokens": tokens,
        "ttftSeconds": None if first_token is None else first_token - started,
        "decodeSeconds": decode_seconds,
        "decodeTokensPerSecond": tokens / decode_seconds,
        "wallSeconds": ended - started,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--streams", type=int, default=4)
    parser.add_argument("--model", default="incoai/Qwen3.8-27B-Splash")
    parser.add_argument("--pack", default=None, help="derived Splash pack root")
    parser.add_argument("--port", type=int, default=harness.DEFAULT_PORT)
    parser.add_argument("--context", type=int, default=131072)
    parser.add_argument("--prompt-tokens", type=int, default=33000)
    parser.add_argument("--gen-tokens", type=int, default=512)
    parser.add_argument("--label", default="splash-concurrent")
    parser.add_argument("--keep-alive", action="store_true")
    parser.add_argument("--no-lock", action="store_true")
    args = parser.parse_args()

    prompt_path = harness.prompt_file("ledger2", args.prompt_tokens, 4.5)
    prompt = prompt_path.read_text()
    engine = harness.make_splash(
        args.model,
        port=args.port,
        context=args.context,
        pack_root=args.pack,
    )
    lock = (
        contextlib.nullcontext()
        if args.no_lock
        else harness.bench_run(f"{args.label} splash", minimum_headroom_gb=20.0)
    )
    with lock:
        with engine as running:
            # Warm the prefix cache with one sequential request, then fan out.
            warm = chat_stream(running.port, args.model, prompt, 8, -1)
            started = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.streams) as pool:
                results = list(pool.map(
                    lambda index: chat_stream(
                        running.port, args.model, prompt, args.gen_tokens, index,
                    ),
                    range(args.streams),
                ))
            wall = time.time() - started
            aggregate = sum(item["tokens"] for item in results) / wall
            native = harness.splash_status(running)
            payload = {
                "label": args.label,
                "engine": "splash",
                "startedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "config": vars(args),
                "command": engine.command_line(),
                "promptFile": str(prompt_path),
                "warm": warm,
                "streams": results,
                "nativeMetrics": native,
                "aggregateTokensPerSecond": aggregate,
                "wallSeconds": wall,
            }
            out = harness.RESULTS_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}-{args.label}.json"
            out.write_text(json.dumps(payload, indent=1))
            print(json.dumps({
                "aggregate": round(aggregate, 2),
                "perStream": [round(item["decodeTokensPerSecond"], 2) for item in results],
                "wallSeconds": round(wall, 1),
                "result": str(out),
            }, indent=1))
            if args.keep_alive:
                print("engine left running; Ctrl-C or kill the child to stop")
                time.sleep(3600)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
