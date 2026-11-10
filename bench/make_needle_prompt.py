#!/usr/bin/env python3
"""Build needle-augmented ledger prompts for SpecPrefill quality measurement.

The generated prompt embeds N unique ``vault-code:`` lines spread evenly
through the ledger and replaces the trailing task with an audit question that
asks for all of them. Scoring the greedy answer against the planted codes
measures how much of the context a sparse (SpecPrefill) prefill actually
preserved, and the depth map shows *where* the losses are.

Run with the oMLX runtime python so ``tokenizers`` is available::

    "/Users/.../LLM Launcher/runtimes/omlx-0.7.0.dev2/bin/python" \
        bench/make_needle_prompt.py --source bench/prompts/ledger2-120000.txt \
        --out-prompt bench/prompts/needles-specprefill-128k.txt \
        --out-map bench/prompts/needles-specprefill-128k.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random

DEFAULT_TOKENIZER = pathlib.Path(
    "~/.lmstudio/models/Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed/tokenizer.json"
)

PREFIXES = [
    "KRX", "QTM", "VLT", "ZEP", "NXB", "HRD", "OMC", "PFS", "DRW", "LKT",
    "MVS", "GTH", "BRN", "CWF", "JYP", "TDX", "SQN", "RLV", "WPK", "ZBR",
    "AXM", "CND", "FGR", "HLS", "INV", "KPL", "MTR", "NQV", "OBS", "PWT",
]


def entry_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """Return ``(header_index, next_header_index)`` for every ledger entry."""
    headers = [i for i, line in enumerate(lines) if line.startswith("## entry ")]
    blocks = []
    for n, start in enumerate(headers):
        end = headers[n + 1] if n + 1 < len(headers) else len(lines)
        blocks.append((start, end))
    return blocks


def insert_index(lines: list[str], start: int, end: int) -> int:
    """Insert after the entry's ``counter:`` line (or at the block end)."""
    for i in range(end - 1, start, -1):
        if lines[i].startswith("counter:"):
            return i + 1
    return end


def count_tokens(tokenizer_path: pathlib.Path, text: str) -> int | None:
    try:
        from tokenizers import Tokenizer  # type: ignore
    except Exception:
        return None
    if not tokenizer_path.exists():
        return None
    return len(Tokenizer.from_file(str(tokenizer_path)).encode(text).ids)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--out-prompt", required=True)
    parser.add_argument("--out-map", required=True)
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260919)
    parser.add_argument("--tokenizer", default=str(DEFAULT_TOKENIZER))
    parser.add_argument("--min-depth", type=float, default=0.04)
    parser.add_argument("--max-depth", type=float, default=0.96)
    args = parser.parse_args()

    source = pathlib.Path(args.source)
    lines = source.read_text(encoding="utf-8").splitlines()
    blocks = entry_blocks(lines)
    if len(blocks) < args.count:
        raise SystemExit(f"{source} has only {len(blocks)} entries")

    # Pick entries evenly across the file so needle depth spans the window.
    picks: list[int] = []
    for k in range(args.count):
        frac = args.min_depth + (args.max_depth - args.min_depth) * k / (args.count - 1)
        block = int(round(frac * (len(blocks) - 1)))
        while block in picks:
            block = (block + 1) % len(blocks)
        picks.append(block)
    picks.sort()

    rng = random.Random(args.seed)
    codes = [f"{prefix}-{rng.randint(1000, 9999)}" for prefix in PREFIXES[: args.count]]
    rng.shuffle(codes)

    needles = []
    for block, code in zip(picks, codes):
        start, end = blocks[block]
        header = lines[start]
        entry_id = header.split()[-1]
        needles.append({"entry": entry_id, "code": code, "block": block})

    # Apply insertions bottom-up so earlier indices stay valid.
    inserts = []
    for needle in needles:
        start, end = blocks[needle["block"]]
        inserts.append((insert_index(lines, start, end), needle))
    for at, needle in sorted(inserts, key=lambda item: item[0], reverse=True):
        lines.insert(at, f"vault-code: {needle['code']}")

    end_marker = next(
        (i for i, line in enumerate(lines) if line.strip() == "END OF LEDGER"),
        len(lines),
    )
    order_rng = random.Random(args.seed + 1)
    order = [n["entry"] for n in needles]
    order_rng.shuffle(order)
    task = [
        "",
        "END OF LEDGER",
        "",
        (
            f"Task: without any preamble, output exactly {args.count} lines and "
            "nothing else. Each line must have the form `<entry> = <vault-code>` "
            "for one of the entries listed below, using the six-digit entry "
            "number and copying the vault-code exactly as written in that "
            "entry's `vault-code:` line. Do not add commentary and do not guess."
        ),
        "",
        "Entries, in this order: " + ", ".join(order),
        "",
    ]
    lines = lines[:end_marker] + task
    prompt = "\n".join(lines) + "\n"

    prompt_path = pathlib.Path(args.out_prompt)
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding="utf-8")

    tokenizer_path = pathlib.Path(args.tokenizer).expanduser()
    token_count = count_tokens(tokenizer_path, prompt)

    # Approximate per-needle token depth: encode the text up to each needle.
    depth_map = {}
    if token_count is not None:
        from tokenizers import Tokenizer  # type: ignore

        tokenizer = Tokenizer.from_file(str(tokenizer_path))
        prefix = "\n".join(lines)
        for needle in needles:
            marker = f"vault-code: {needle['code']}"
            char_at = prefix.find(marker)
            if char_at < 0:
                continue
            depth_map[needle["code"]] = len(tokenizer.encode(prefix[:char_at]).ids)

    payload = {
        "source": str(source),
        "promptFile": str(prompt_path),
        "promptChars": len(prompt),
        "promptTokens": token_count,
        "needles": [
            {
                **needle,
                "tokenIndex": depth_map.get(needle["code"]),
                "depth": (
                    round(depth_map[needle["code"]] / token_count, 4)
                    if token_count and needle["code"] in depth_map
                    else None
                ),
            }
            for needle in needles
        ],
        "order": order,
    }
    map_path = pathlib.Path(args.out_map)
    map_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        f"[needles] {prompt_path} chars={len(prompt)} tokens={token_count} "
        f"needles={len(needles)} map={map_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
