#!/usr/bin/env python3
"""Build and score the 20-needle retrieval prompt used for SpecPrefill quality.

The prompt is the standing long-context ledger with 20 planted facts spread
evenly through the body, followed by 20 questions.  Each fact is a vault ID and
its code; the answer block has to reproduce the code.  Because the ledger text
is a fixed file, the same prompt can be run through any engine and the answers
scored mechanically.

Usage:

    python3 bench/needles.py build            # writes bench/prompts/needles-120000.txt
    python3 bench/needles.py score FILE...    # scores result JSON files
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import re

BENCH_DIR = pathlib.Path(__file__).resolve().parent
PROMPTS_DIR = BENCH_DIR / "prompts"
RESULTS_DIR = BENCH_DIR / "results"

N_NEEDLES = 20
SEED = 20260919

# Fixed vault IDs so every run of this script produces the same prompt.
VAULTS = [
    "ORCHID-07", "FALCON-12", "CINDER-23", "MERIDIAN-31", "QUARTZ-44",
    "LANTERN-52", "HALCYON-63", "PELICAN-71", "VESPER-08", "TUNDRA-19",
    "SAFFRON-26", "NIMBUS-35", "OBSIDIAN-47", "KESTREL-58", "AZURE-66",
    "THISTLE-74", "GARNET-81", "MARINER-93", "SOLSTICE-05", "WILLOW-16",
]


def _codes(rng: random.Random) -> list[str]:
    letters = "ABDEFGHJKLMNPQRSTUVWXYZ"
    codes = []
    seen: set[str] = set()
    while len(codes) < len(VAULTS):
        code = f"{''.join(rng.choice(letters) for _ in range(2))}{rng.randrange(1000, 9999)}"
        if code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def build(base: pathlib.Path, out: pathlib.Path, *, n: int = N_NEEDLES, seed: int = SEED) -> dict:
    """Write the needle prompt and return its metadata."""
    lines = base.read_text(encoding="utf-8").splitlines()
    rng = random.Random(seed)
    codes = _codes(rng)
    vaults = VAULTS[:n]

    body_start = 0
    for index, line in enumerate(lines[:8]):
        if line.startswith("## entry"):
            body_start = index
            break
    body_end = len(lines)

    insertions: list[tuple[int, list[str]]] = []
    for index, (vault, code) in enumerate(zip(vaults, codes)):
        fraction = (index + 0.5) / n
        at = body_start + int(fraction * (body_end - body_start))
        insertions.append((at, [
            "",
            f"## needle {index + 1:02d}",
            f"vault: {vault} code: {code}",
            "",
        ]))

    for at, block in sorted(insertions, reverse=True):
        lines[at:at] = block

    lines.extend([
        "",
        "## retrieval questions",
        "For each vault ID below, output exactly one line of the form "
        "\"<ID>=<code>\", using the code recorded in the ledger above. "
        "No preamble, no explanation, no other text.",
        "",
    ])
    for index, vault in enumerate(vaults, start=1):
        lines.append(f"{index}. {vault}")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    meta = {
        "prompt": str(out),
        "base": str(base),
        "needles": [
            {"vault": vault, "code": code} for vault, code in zip(vaults, codes)
        ],
    }
    meta_path = out.with_suffix(".needles.json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


_NORMALISE = re.compile(r"[^A-Z0-9]")


def _normalise(text: str) -> str:
    return _NORMALISE.sub("", text.upper())


def score_content(content: str, meta: dict) -> dict:
    """Return per-needle and aggregate scores for one response."""
    normalised = _normalise(content)
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    per_needle = []
    for needle in meta["needles"]:
        vault, code = needle["vault"], needle["code"]
        code_norm = _normalise(code)
        vault_norm = _normalise(vault)
        # Loose: the code appears anywhere in the reply.
        loose = code_norm in normalised
        # Strict: a line that names the vault also carries the code.
        strict = any(
            vault_norm in _normalise(line) and code_norm in _normalise(line)
            for line in lines
        )
        per_needle.append({
            "vault": vault,
            "code": code,
            "strict": strict,
            "loose": loose,
        })
    return {
        "strict_hits": sum(1 for row in per_needle if row["strict"]),
        "loose_hits": sum(1 for row in per_needle if row["loose"]),
        "total": len(per_needle),
        "per_needle": per_needle,
    }


def score_result(path: pathlib.Path, meta: dict) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for measurement in payload.get("measurements", []):
        content = measurement.get("content") or ""
        scored = score_content(content, meta)
        scored.update({
            "promptTokens": measurement.get("promptTokens"),
            "prefillTokensPerSecond": measurement.get("prefillTokensPerSecond"),
            "decodeTokensPerSecond": measurement.get("decodeTokensPerSecond"),
            "ttftSeconds": measurement.get("ttftSeconds"),
            "content": content,
        })
        rows.append(scored)
    return {
        "label": payload.get("label"),
        "file": path.name,
        "measurements": rows,
    }


def _divergence(reference: str, other: str) -> dict:
    limit = min(len(reference), len(other))
    at = limit
    for index in range(limit):
        if reference[index] != other[index]:
            at = index
            break
    return {
        "first_difference": at,
        "identical": reference == other,
        "reference_length": len(reference),
        "other_length": len(other),
        "reference_excerpt": reference[max(0, at - 60):at + 60],
        "other_excerpt": other[max(0, at - 60):at + 60],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    build_parser = sub.add_parser("build", help="build the needle prompt")
    build_parser.add_argument(
        "--base",
        type=pathlib.Path,
        default=PROMPTS_DIR / "ledger2-120000.txt",
    )
    build_parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=PROMPTS_DIR / "needles-120000.txt",
    )

    score_parser = sub.add_parser("score", help="score result JSON files")
    score_parser.add_argument("files", nargs="+", type=pathlib.Path)
    score_parser.add_argument(
        "--meta",
        type=pathlib.Path,
        default=PROMPTS_DIR / "needles-120000.needles.json",
    )
    score_parser.add_argument(
        "--reference",
        type=pathlib.Path,
        help="result JSON to diff each other result against (dense control)",
    )
    score_parser.add_argument("--json-out", type=pathlib.Path)

    args = parser.parse_args()
    if args.command == "build":
        meta = build(args.base, args.out)
        print(json.dumps({k: v for k, v in meta.items() if k != "needles"}, indent=2))
        print(f"needles: {len(meta['needles'])}")
        for row in meta["needles"][:3]:
            print(f"  {row['vault']} {row['code']}")
        print(f"wrote {args.out} ({args.out.stat().st_size} bytes)")
        return 0

    meta = json.loads(args.meta.read_text(encoding="utf-8"))
    reference_content = None
    if args.reference:
        payload = json.loads(args.reference.read_text(encoding="utf-8"))
        reference_content = payload["measurements"][0].get("content") or ""

    summary = []
    for path in args.files:
        scored = score_result(path, meta)
        for row in scored["measurements"]:
            if reference_content is not None:
                row["divergence"] = _divergence(reference_content, row["content"])
            print(
                f"{scored['label']}: strict {row['strict_hits']}/{row['total']} "
                f"loose {row['loose_hits']}/{row['total']} "
                f"prefill {row['prefillTokensPerSecond'] and round(row['prefillTokensPerSecond'], 1)} "
                f"decode {row['decodeTokensPerSecond'] and round(row['decodeTokensPerSecond'], 2)}"
            )
            missing = [r["vault"] for r in row["per_needle"] if not r["strict"]]
            if missing:
                print(f"  missing: {', '.join(missing)}")
            if "divergence" in row:
                diff = row["divergence"]
                print(
                    f"  first diff at char {diff['first_difference']}"
                    + (" (identical)" if diff["identical"] else "")
                )
        summary.append(scored)

    if args.json_out:
        args.json_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"wrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
