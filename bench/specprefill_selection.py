#!/usr/bin/env python3
"""Measure which chunks SpecPrefill keeps, and whether the needles survive.

Runs the shipped draft-scoring pipeline (`omlx.patches.specprefill`) against
the needle prompt and reports, per keep tier:

* selected-chunk share (sanity: should track keep_pct),
* needle-chunk recall (how many of the 20 planted facts survive selection),
* the position of every dropped needle.

Must run with the managed oMLX runtime interpreter, e.g.

    "$HOME/Library/Application Support/LLM Launcher/runtimes/omlx-0.7.0.dev2/bin/python" \
        bench/specprefill_selection.py --keep 0.1 0.2 0.3 0.4
"""
from __future__ import annotations

import argparse
import json
import pathlib

BENCH_DIR = pathlib.Path(__file__).resolve().parent
PROMPTS_DIR = BENCH_DIR / "prompts"
DEFAULT_DRAFT = BENCH_DIR / "derived/drafts/Qwen3.8-2B-Distill-mlx-5bit"
DEFAULT_TARGET = (
    pathlib.Path.home() / ".lmstudio/models/lmstudio-community/Qwen3.8-27B-MLX-6bit"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", type=pathlib.Path, default=PROMPTS_DIR / "needles-120000.txt")
    parser.add_argument(
        "--meta",
        type=pathlib.Path,
        default=PROMPTS_DIR / "needles-120000.needles.json",
    )
    parser.add_argument("--draft", type=pathlib.Path, default=DEFAULT_DRAFT)
    parser.add_argument("--target", type=pathlib.Path, default=DEFAULT_TARGET)
    parser.add_argument("--keep", type=float, nargs="+", default=[0.1, 0.2, 0.3, 0.4])
    parser.add_argument("--chunk-size", type=int, default=32)
    parser.add_argument("--tail-tokens", type=int, default=512)
    parser.add_argument("--json-out", type=pathlib.Path)
    args = parser.parse_args()

    import mlx.core as mx
    from mlx_lm import load
    from tokenizers import Tokenizer

    from omlx.patches.specprefill import score_tokens, select_chunks

    text = args.prompt.read_text(encoding="utf-8")
    meta = json.loads(args.meta.read_text(encoding="utf-8"))
    tokenizer = Tokenizer.from_file(str(args.target / "tokenizer.json"))
    tokens = tokenizer.encode(text).ids
    print(f"prompt tokens: {len(tokens)}", flush=True)

    model, _ = load(str(args.draft))
    importance, _cache = score_tokens(model, tokens, prefill_step_size=2048)
    mx.eval(importance)
    total = int(importance.shape[0])
    print(f"scored {total} tokens", flush=True)

    # Character offsets of each needle block -> token windows.
    needle_windows = []
    for index, needle in enumerate(meta["needles"]):
        block = f"vault: {needle['vault']} code: {needle['code']}"
        char_at = text.find(block)
        if char_at < 0:
            raise SystemExit(f"needle {needle['vault']} not found in prompt")
        start_tok = len(tokenizer.encode(text[:char_at]).ids)
        end_tok = len(tokenizer.encode(text[: char_at + len(block)]).ids)
        needle_windows.append({
            "index": index,
            "vault": needle["vault"],
            "code": needle["code"],
            "char_at": char_at,
            "token_start": start_tok,
            "token_end": end_tok,
        })

    summary = []
    for keep in args.keep:
        selected = select_chunks(
            importance, keep_pct=keep, chunk_size=args.chunk_size, tail_tokens=args.tail_tokens
        )
        selected_list = selected.tolist()
        selected_set = set(selected_list)
        chunk_starts = {
            (index // args.chunk_size) * args.chunk_size for index in selected_list
        }
        rows = []
        for window in needle_windows:
            chunk = (window["token_start"] // args.chunk_size) * args.chunk_size
            kept = chunk in chunk_starts
            rows.append({**window, "chunk": chunk, "kept": kept})
        dropped = [row["vault"] for row in rows if not row["kept"]]
        row = {
            "keep_pct": keep,
            "selected_tokens": len(selected_list),
            "selected_share": len(selected_list) / total,
            "needle_recall": sum(1 for r in rows if r["kept"]),
            "needle_total": len(rows),
            "dropped": dropped,
            "needles": rows,
        }
        summary.append(row)
        print(
            f"keep {keep:.2f}: selected {len(selected_list)}/{total} "
            f"({row['selected_share'] * 100:.1f}%) needles {row['needle_recall']}/{row['needle_total']}"
            + (f" dropped={dropped}" if dropped else ""),
            flush=True,
        )

    if args.json_out:
        args.json_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"wrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
