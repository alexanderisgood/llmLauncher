#!/usr/bin/env python3
"""Run one oMLX SpecPrefill arm on the needle prompt and score it.

Example (dense reference)::

    python3 bench/run_specprefill.py --keep-pct 1.0 --label specprefill-dense

Example (conservative sparse arm)::

    python3 bench/run_specprefill.py --keep-pct 0.3 \
        --draft-model ~/.lmstudio/models/inference-optimization/Qwen3.8-1.0B-A0.6B \
        --label specprefill-keep30

The runner reuses ``bench/harness.py`` (machine-wide bench lock, oMLX launch
recipe, result schema) and adds needle scoring plus first-divergence analysis
against a reference arm.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import harness  # noqa: E402

CODE_RE = re.compile(r"[A-Z]{2,4}-\d{3,5}")


def score_needles(content: str, needles: list[dict]) -> dict:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    planted = {n["code"] for n in needles}
    details = []
    matched = 0
    for needle in needles:
        entry, want = needle["entry"], needle["code"]
        found = None
        for line in lines:
            if entry in line:
                match = CODE_RE.search(line)
                if match:
                    found = match.group(0)
                    break
        ok = found == want
        matched += int(ok)
        details.append(
            {
                "entry": entry,
                "want": want,
                "found": found,
                "ok": ok,
                "depth": needle.get("depth"),
            }
        )
    emitted = [match.group(0) for line in lines for match in [CODE_RE.search(line)] if match]
    return {
        "matched": matched,
        "total": len(needles),
        "accuracy": matched / len(needles) if needles else None,
        "hallucinated": sorted({code for code in emitted if code not in planted}),
        "details": details,
    }


def first_divergence(reference: str, candidate: str) -> dict:
    limit = min(len(reference), len(candidate))
    for i in range(limit):
        if reference[i] != candidate[i]:
            return {
                "charIndex": i,
                "reference": reference[max(0, i - 60) : i + 60],
                "candidate": candidate[max(0, i - 60) : i + 60],
            }
    if len(reference) != len(candidate):
        return {
            "charIndex": limit,
            "reference": reference[max(0, limit - 60) : limit + 60],
            "candidate": candidate[max(0, limit - 60) : limit + 60],
        }
    return {"charIndex": None, "reference": None, "candidate": None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument(
        "--prompt",
        default="bench/prompts/needles-specprefill-128k.txt",
    )
    parser.add_argument(
        "--needles",
        default="bench/prompts/needles-specprefill-128k.json",
    )
    parser.add_argument(
        "--draft-model",
        default="~/.lmstudio/models/inference-optimization/Qwen3.8-1.0B-A0.6B",
    )
    parser.add_argument("--keep-pct", type=float, default=None)
    parser.add_argument("--threshold", type=int, default=8192)
    parser.add_argument("--gen-tokens", type=int, default=320)
    parser.add_argument("--context", type=int, default=131072)
    parser.add_argument("--kv", default="q8", choices=("off", "q8", "q6", "q4"))
    parser.add_argument("--memory-gb", type=float, default=41.0)
    parser.add_argument("--model", default="mtplx-27b-speed")
    parser.add_argument("--binary", default=None)
    parser.add_argument("--reference", default=None, help="reference result JSON")
    parser.add_argument("--keep-alive", action="store_true")
    args = parser.parse_args()

    prompt_path = pathlib.Path(args.prompt)
    prompt = prompt_path.read_text(encoding="utf-8")
    needle_map = json.loads(pathlib.Path(args.needles).read_text(encoding="utf-8"))
    needles = needle_map["needles"]

    per_model: dict = {}
    if args.keep_pct is not None and args.keep_pct < 1.0:
        draft = str(pathlib.Path(args.draft_model).expanduser())
        if not pathlib.Path(draft).exists():
            raise SystemExit(f"draft model not found: {draft}")
        per_model = {
            "specprefill_enabled": True,
            "specprefill_draft_model": draft,
            "specprefill_keep_pct": args.keep_pct,
            "specprefill_threshold": args.threshold,
        }

    engine = harness.make_omlx(
        args.model,
        context=args.context,
        kv=args.kv,
        memory_guard_gb=args.memory_gb,
        max_tokens=4096,
        per_model=per_model,
        binary=args.binary or harness.OMLX_DEFAULT_BIN,
    )
    extra_body = None
    if per_model:
        extra_body = {
            "specprefill": True,
            "specprefill_keep_pct": args.keep_pct,
            "specprefill_threshold": args.threshold,
        }

    payload: dict = {
        "label": args.label,
        "engine": "omlx-specprefill",
        "config": {
            "keepPct": args.keep_pct,
            "threshold": args.threshold,
            "context": args.context,
            "kv": args.kv,
            "model": args.model,
            "draftModel": per_model.get("specprefill_draft_model"),
            "genTokens": args.gen_tokens,
            "prompt": str(prompt_path),
            "promptTokensInFile": needle_map.get("promptTokens"),
        },
        "command": engine.command_line(),
        "measurements": [],
    }

    with harness.bench_run(f"specprefill {args.label}", minimum_headroom_gb=20.0):
        engine.start()
        try:
            engine.wait_ready()
            measurement = harness.stream_chat(
                engine,
                prompt,
                max_tokens=args.gen_tokens,
                reasoning_effort="none",
                extra_body=extra_body,
            )
            payload["measurements"].append(measurement)
        finally:
            if not args.keep_alive:
                engine.stop()

    measurement = payload["measurements"][0]
    content = measurement.pop("content", "")
    payload["content"] = content
    payload["needles"] = score_needles(content, needles)
    log_path = engine.log_path
    spec_log = []
    if log_path and log_path.exists():
        spec_log = [
            line
            for line in log_path.read_text(errors="replace").splitlines()
            if "SpecPrefill" in line
        ]
    payload["specprefillLog"] = spec_log
    if args.reference:
        reference = json.loads(pathlib.Path(args.reference).read_text(encoding="utf-8"))
        payload["divergence"] = first_divergence(
            reference.get("content", ""), content
        )

    print(
        json.dumps(
            {
                "label": args.label,
                "keepPct": args.keep_pct,
                "promptTokens": measurement.get("promptTokens"),
                "prefillTokensPerSecond": measurement.get("prefillTokensPerSecond"),
                "nativePrefillTokensPerSecond": measurement.get(
                    "nativePrefillTokensPerSecond"
                ),
                "decodeTokensPerSecond": measurement.get("decodeTokensPerSecond"),
                "ttftSeconds": measurement.get("ttftSeconds"),
                "totalSeconds": measurement.get("totalSeconds"),
                "needleAccuracy": payload["needles"]["accuracy"],
                "needlesMatched": payload["needles"]["matched"],
                "hallucinated": payload["needles"]["hallucinated"],
                "specprefillLog": spec_log,
            },
            indent=2,
        )
    )
    path = harness.write_result(args.label, payload)
    print(f"[bench] wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
