#!/usr/bin/env python3
"""Multi-turn SpecPrefill probe with a sparse prefix cache.

Turn 1 asks about one ledger entry; turn 2 asks for a different planted fact.
Because the prefix cache stores the *sparse* (pruned) target KV, turn 2's
question is answered against turn 1's selection.  If the selector dropped the
chunk turn 2 needs, the answer should fail even though the same question is
answered correctly in a cold single-turn run.

Control: `--no-specprefill` runs the identical two-turn conversation dense.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness  # noqa: E402

BENCH_DIR = pathlib.Path(__file__).resolve().parent
PROMPTS_DIR = BENCH_DIR / "prompts"
DRAFT = BENCH_DIR / "derived/drafts/Qwen3.8-2B-Distill-mlx-5bit"

TURN1_QUESTION = (
    "\n\n## question\n"
    "In exactly one line, state the counter value and delta for entry 000017.\n"
)
TURN2_QUESTION = "Give the vault code for TUNDRA-19."


def chat(
    engine: harness.Engine,
    messages: list[dict],
    *,
    max_tokens: int = 256,
    temperature: float = 0.0,
    seed: int = 42,
) -> dict:
    body = {
        "model": engine.model_id,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": temperature,
        "seed": seed,
        "max_tokens": max_tokens,
        "reasoning_effort": "none",
    }
    request = urllib.request.Request(
        f"http://127.0.0.1:{engine.port}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    started = time.monotonic()
    first_output = None
    usage = None
    content: list[str] = []
    with urllib.request.urlopen(request, timeout=7200.0) as response:
        for raw in response:
            if not raw.startswith(b"data: "):
                continue
            payload = raw[6:].strip()
            if payload == b"[DONE]":
                break
            event = json.loads(payload)
            if "error" in event:
                raise RuntimeError(json.dumps(event["error"]))
            if isinstance(event.get("usage"), dict):
                usage = event["usage"]
            for choice in event.get("choices", []):
                delta = choice.get("delta") or {}
                piece = (delta.get("content") or "") + (delta.get("reasoning_content") or "")
                if piece:
                    if first_output is None:
                        first_output = time.monotonic() - started
                    content.append(piece)
    total = time.monotonic() - started
    cached = int(((usage or {}).get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
    return {
        "content": "".join(content),
        "usage": usage,
        "ttftSeconds": first_output,
        "totalSeconds": total,
        "cachedPromptTokens": cached,
        "promptTokens": int((usage or {}).get("prompt_tokens") or 0),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", type=float, default=0.2)
    parser.add_argument("--no-specprefill", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--label", default="27b-specprefill-multiturn")
    args = parser.parse_args()

    text = (PROMPTS_DIR / "needles-120000.txt").read_text(encoding="utf-8")
    base = text.split("## retrieval questions")[0].rstrip()
    meta = json.loads((PROMPTS_DIR / "needles-120000.needles.json").read_text())
    tundra = next(row for row in meta["needles"] if row["vault"] == "TUNDRA-19")

    entry = re.search(
        r"## entry 000017\n(.*?)(?=\n## entry|\Z)", base, re.DOTALL
    )
    counter = re.search(r"counter:\s*(\d+)\s*delta\s*(-?\d+)", entry.group(1) if entry else "")
    expected_counter = f"{counter.group(1)} {counter.group(2)}" if counter else "?"

    per_model = {
        "specprefill_enabled": not args.no_specprefill,
        "specprefill_keep_pct": args.keep,
        "specprefill_threshold": 8192,
    }
    if not args.no_specprefill:
        per_model["specprefill_draft_model"] = str(DRAFT)
    engine = harness.make_omlx(
        "mtplx-27b-speed",
        context=131072,
        kv="q8",
        memory_guard_gb=41.0,
        max_tokens=4096,
        per_model=per_model,
        extra_settings={
            "scheduler": {
                "chunked_prefill": True,
                "prefill_step_size": 2048,
                "prefill_priority": "context",
            },
            "cache": {
                "enabled": True,
                "hot_cache_max_size": "8GB",
            },
        },
    )

    result: dict = {
        "label": args.label,
        "startedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "keep": args.keep,
        "specprefill": not args.no_specprefill,
        "expected": {"entry000017": expected_counter, "TUNDRA-19": tundra["code"]},
        "turns": [],
    }
    # Serialise with every other bench run: the port and the GPU are shared
    # with sibling agents, and starting outside the lock silently binds to
    # whichever server already owns the port.
    with harness.bench_run(args.label, minimum_headroom_gb=20.0):
        engine.start()
        try:
            engine.wait_ready()
            if engine.process is not None and engine.process.poll() is not None:
                raise RuntimeError(
                    "engine exited during startup; another server may own the port"
                )
            turn1 = chat(
                engine,
                [{"role": "user", "content": base + TURN1_QUESTION}],
                max_tokens=args.max_tokens,
            )
            result["turns"].append({"question": TURN1_QUESTION.strip(), **turn1})
            messages = [
                {"role": "user", "content": base + TURN1_QUESTION},
                {"role": "assistant", "content": turn1["content"]},
                {"role": "user", "content": TURN2_QUESTION},
            ]
            turn2 = chat(engine, messages, max_tokens=args.max_tokens)
            result["turns"].append({"question": TURN2_QUESTION, **turn2})
        finally:
            engine.stop()

    code = tundra["code"]
    t2 = result["turns"][1]["content"].replace(" ", "")
    result["turn2_has_code"] = code in t2
    result["turn2_cached_tokens"] = result["turns"][1]["cachedPromptTokens"]
    path = harness.write_result(args.label, result)
    print(json.dumps({
        "label": args.label,
        "specprefill": result["specprefill"],
        "keep": args.keep,
        "turn1_ttft_s": round(turn1["ttftSeconds"] or 0, 1),
        "turn1_prompt_tokens": turn1["promptTokens"],
        "turn1_cached": turn1["cachedPromptTokens"],
        "turn2_ttft_s": round(result["turns"][1]["ttftSeconds"] or 0, 1),
        "turn2_prompt_tokens": result["turns"][1]["promptTokens"],
        "turn2_cached_tokens": result["turn2_cached_tokens"],
        "expected_TUNDRA": code,
        "turn2_has_TUNDRA_code": result["turn2_has_code"],
    }, indent=2))
    print(f"[bench] wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
