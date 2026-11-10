#!/usr/bin/env python3
"""Generate the BQ=128 dsplit attention kernel source from MLX's own kernel.

Background: mlx 0.32.2 dispatches head_dim-256 causal prefill attention to
``attention_nax_dsplit<T, BQ=64, BK=32, BD=256, WM=4, WN=2>``. The kernel's
requested K/V bytes (and therefore its ceiling) are set by *rows per
threadgroup*: 64 rows -> 64 FLOP/byte -> ~16-18 TFLOP/s at 246 GB/s, which is
exactly the measured 18.1 TFLOP/s at kv=113K. The kernel asserts ``TQ == 1``
with ``TQ = BQ / (WM * 16)``, so BQ=128 requires WM=8 (512-thread
threadgroups) and doubles the intensity to 128 FLOP/byte.

Nothing else changes: same BK=32 key walk, same ``scale * log2e`` / ``exp2``
softmax, same pairwise fragment exchange, same causal offset handling. The
per-row arithmetic is therefore bit-identical to the stock fused path, which
keeps the house byte-exact gate available.

Input:  the expanded Metal source produced by MLX's own
        ``mlx/backend/metal/make_compiled_preamble.sh`` for
        ``steel/attn/kernels/steel_attention_nax`` (see the module docstring of
        fused_prefill_bq128.py for the exact command).
Output: header text + body text for ``mx.fast.metal_kernel``.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

BQ = 128
BK = 32
BD = 256
WM = 8
WN = 2

# AttnParams field order from mlx/backend/metal/kernels/steel/attn/params.h,
# flattened into the int32 params buffer (scale travels as its own float
# input). The four stride triples are int64 in the struct; they are int32 here
# because every stride in this problem fits (max 113k * 256).
PARAM_FIELDS = [
    "B", "H", "D", "qL", "kL", "gqa_factor",
    "NQ", "NK", "NQ_aligned", "NK_aligned", "qL_rem", "kL_rem", "qL_off",
    "Q_strides[0]", "Q_strides[1]", "Q_strides[2]",
    "K_strides[0]", "K_strides[1]", "K_strides[2]",
    "V_strides[0]", "V_strides[1]", "V_strides[2]",
    "O_strides[0]", "O_strides[1]", "O_strides[2]",
]


def _replace_function_constants(text: str, align_q: bool) -> str:
    replacements = {
        r"constant bool align_Q \[\[function_constant\(200\)\]\];":
            f"constant bool align_Q = {'true' if align_q else 'false'};",
        r"constant bool align_K \[\[function_constant\(201\)\]\];":
            "constant bool align_K = false;",
        r"constant bool has_mask \[\[function_constant\(300\)\]\];":
            "constant bool has_mask = false;",
        r"constant bool do_causal \[\[function_constant\(301\)\]\];":
            "constant bool do_causal = true;",
        r"constant bool has_sinks \[\[function_constant\(302\)\]\];":
            "constant bool has_sinks = false;",
    }
    for pattern, replacement in replacements.items():
        text, count = re.subn(pattern, replacement, text)
        if count != 1:
            raise SystemExit(f"function constant not found exactly once: {pattern}")
    return text


def _extract_body(text: str, kernel: str = "attention_nax_dsplit") -> str:
    marker = f"void {kernel}("
    start = text.index(marker)
    brace = text.index("{", start)
    depth = 0
    for i in range(brace, len(text)):
        char = text[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[brace + 1:i]
    raise SystemExit(f"unterminated {kernel} body")


def _adapt_body(body: str) -> str:
    # `params->` only: `mask_params->` must keep its arrow.
    body = re.sub(r"(?<![A-Za-z0-9_])params->", "params.", body)
    # The auto-generated mx.fast.metal_kernel signature names its thread
    # attributes differently from MLX's hand-written kernel entry points.
    for old, new in (
        (r"\bsimd_lane_id\b", "thread_index_in_simdgroup"),
        (r"\bsimd_group_id\b", "simdgroup_index_in_threadgroup"),
        (r"\btid\b", "threadgroup_position_in_grid"),
        (r"\blid\b", "thread_position_in_threadgroup"),
    ):
        body = re.sub(old, new, body)
    return body


def build(expanded_path: pathlib.Path, align_q: bool,
          kernel: str = "attention_nax_dsplit", bq: int | None = None,
          bk: int = BK, wm: int | None = None, wn: int | None = None,
          bd: int = BD) -> tuple[str, str]:
    text = expanded_path.read_text()
    text = _replace_function_constants(text, align_q)
    body = _adapt_body(_extract_body(text, kernel))

    if bq is None:
        bq = BQ if kernel == "attention_nax_dsplit" else 64
    if wm is None:
        wm = WM if kernel == "attention_nax_dsplit" else bq // 16
    if wn is None:
        wn = WN if kernel == "attention_nax_dsplit" else 1

    prelude = [
        "typedef half T;",
        "using MaskType = float;",
        "using AccumType = float;",
        f"constant constexpr int BQ = {bq};",
        f"constant constexpr int BK = {bk};",
        f"constant constexpr int BD = {bd};",
        f"constant constexpr int WM = {wm};",
        f"constant constexpr int WN = {wn};",
        "",
    ]
    params_lines = ["  AttnParams params;"]
    for index, field in enumerate(PARAM_FIELDS):
        if field.startswith(("Q_", "K_", "V_", "O_")):
            params_lines.append(
                f"  params.{field} = int64_t(params_int[{index}]);")
        else:
            params_lines.append(f"  params.{field} = params_int[{index}];")
    params_lines.append("  params.scale = scale;")
    # These live in function scope: the mask/sinks paths are dead under
    # has_mask / has_sinks == false, but the identifiers still have to exist
    # for name lookup.
    params_lines.append("  const device MaskType* mask = nullptr;")
    params_lines.append("  const device T* sinks = nullptr;")
    params_lines.append("  const device AttnMaskParams* mask_params = nullptr;")

    header = text + "\n" + "\n".join(prelude)
    source = "\n".join(params_lines) + "\n" + body
    return header, source


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "expanded",
        nargs="?",
        default="/private/tmp/mlx-preamble/steel_attention_nax.metal",
        help="expanded Metal source from MLX's make_compiled_preamble.sh",
    )
    parser.add_argument("--out", default=None, help="write header+source to this file")
    parser.add_argument("--align-q", choices=["true", "false"], default="true")
    args = parser.parse_args()
    header, source = build(pathlib.Path(args.expanded), args.align_q == "true")
    text = header + "\n// ---- kernel body ----\n" + source + "\n"
    if args.out:
        pathlib.Path(args.out).write_text(text)
        print(f"wrote {args.out}: {len(text)} bytes, {text.count(chr(10))} lines")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
