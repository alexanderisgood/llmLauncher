#!/usr/bin/env python3
"""Build a semantic (unnamed) retrieval probe for SpecPrefill quality.

The named-needle probe asks for vault IDs that the prompt itself lists, which
is the best case for SpecPrefill's query-driven selector. This probe plants 20
vault facts but marks exactly one ``audit-status: quarantined`` and exactly one
``flag: amber-flagged``; the final question names neither entry, so the
selector has to keep the right chunks by meaning rather than by a token match
with the question.

Outputs a prompt plus a small map with the two expected answers and the token
depth of each marker.
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
]


def entry_blocks(lines: list[str]) -> list[tuple[int, int]]:
    headers = [i for i, line in enumerate(lines) if line.startswith("## entry ")]
    return [
        (start, headers[n + 1] if n + 1 < len(headers) else len(lines))
        for n, start in enumerate(headers)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--out-prompt", required=True)
    parser.add_argument("--out-map", required=True)
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260919)
    parser.add_argument("--tokenizer", default=str(DEFAULT_TOKENIZER))
    args = parser.parse_args()

    lines = pathlib.Path(args.source).read_text(encoding="utf-8").splitlines()
    blocks = entry_blocks(lines)
    picks: list[int] = []
    for k in range(args.count):
        frac = 0.05 + 0.9 * k / (args.count - 1)
        block = int(round(frac * (len(blocks) - 1)))
        while block in picks:
            block = (block + 1) % len(blocks)
        picks.append(block)
    picks.sort()

    rng = random.Random(args.seed)
    codes = [f"{prefix}-{rng.randint(1000, 9999)}" for prefix in PREFIXES[: args.count]]
    rng.shuffle(codes)
    quarantine_at = picks[int(round(0.62 * (len(picks) - 1)))]
    amber_at = picks[int(round(0.33 * (len(picks) - 1)))]

    facts = []
    inserts = []
    for block, code in zip(picks, codes):
        start, end = blocks[block]
        entry = lines[start].split()[-1]
        status = "quarantined" if block == quarantine_at else "clear"
        flag = "amber-flagged" if block == amber_at else "none"
        at = end
        for i in range(end - 1, start, -1):
            if lines[i].startswith("counter:"):
                at = i + 1
                break
        inserts.append(
            (
                at,
                [
                    f"vault-code: {code}",
                    f"audit-status: {status}",
                    f"flag: {flag}",
                ],
            )
        )
        facts.append(
            {"entry": entry, "code": code, "status": status, "flag": flag, "block": block}
        )

    for at, new_lines in sorted(inserts, key=lambda item: item[0], reverse=True):
        lines[at:at] = new_lines

    quarantined = next(f for f in facts if f["status"] == "quarantined")
    amber = next(f for f in facts if f["flag"] == "amber-flagged")
    end_marker = next(
        (i for i, line in enumerate(lines) if line.strip() == "END OF LEDGER"),
        len(lines),
    )
    task = [
        "",
        "END OF LEDGER",
        "",
        (
            "Task: without any preamble, output exactly two lines and nothing "
            "else. Exactly one ledger entry is marked `audit-status: "
            "quarantined`; output its six-digit entry number and vault-code as "
            "`<entry>=<code>`. Exactly one ledger entry is marked `flag: "
            "amber-flagged`; output its six-digit entry number and vault-code "
            "as `<entry>=<code>`. The two entries are different. Do not guess."
        ),
        "",
    ]
    lines = lines[:end_marker] + task
    prompt = "\n".join(lines) + "\n"

    prompt_path = pathlib.Path(args.out_prompt)
    prompt_path.write_text(prompt, encoding="utf-8")
    map_path = pathlib.Path(args.out_map)

    depths = {}
    try:
        from tokenizers import Tokenizer  # type: ignore

        tokenizer_path = pathlib.Path(args.tokenizer).expanduser()
        tokenizer = Tokenizer.from_file(str(tokenizer_path))
        total = len(tokenizer.encode(prompt).ids)
        for fact in facts:
            marker = f"vault-code: {fact['code']}"
            at = prompt.find(marker)
            if at >= 0:
                depths[fact["code"]] = len(tokenizer.encode(prompt[:at]).ids) / total
    except Exception:
        total = None

    map_path.write_text(
        json.dumps(
            {
                "prompt": str(prompt_path),
                "promptTokens": total,
                "expected": {
                    "quarantined": f"{quarantined['entry']}={quarantined['code']}",
                    "amber": f"{amber['entry']}={amber['code']}",
                },
                "quarantinedDepth": depths.get(quarantined["code"]),
                "amberDepth": depths.get(amber["code"]),
                "facts": facts,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"[semantic] {prompt_path} tokens={total} "
        f"quarantined={quarantined['entry']}={quarantined['code']} "
        f"amber={amber['entry']}={amber['code']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
