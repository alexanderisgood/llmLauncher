#!/usr/bin/env python3
"""Bit-exact BQ=128 clone of mlx's head-dim-256 NAX attention kernel.

Why this exists
---------------
mlx 0.32.2 sends the 27B's causal prefill attention (head_dim 256, GQA 24/4)
to ``attention_nax_dsplit<T, BQ=64, BK=32, BD=256, WM=4, WN=2>``. In that
kernel family the requested K/V bytes are set by *rows per threadgroup*, i.e.
intensity = rows_per_tg FLOP/byte (d=256): 64 rows -> 64 FLOP/byte -> a
15.7 TFLOP/s ceiling at the machine's 246 GB/s streaming rate, matching the
measured 18.1 TFLOP/s at kv=113K. The kernel asserts ``TQ == 1`` with
``TQ = BQ / (WM * 16)``, so BQ=128 needs WM=8 (512-thread threadgroups) and
doubles the intensity to 128 FLOP/byte, i.e. 31 TFLOP/s at 246 GB/s or 36.7
at the 287 GB/s the stock kernel actually achieves with L2 help.

Everything else is MLX's kernel, verbatim: same BK=32 key walk, same
``scale * log2e`` / ``exp2`` softmax, same pairwise fragment exchange, same
tail-aligned causal offset. Rows are only *regrouped* across threadgroups, so
the per-row arithmetic is unchanged and the output should be exactly equal to
``mx.fast.scaled_dot_product_attention`` — the house byte-exact gate applies.

Source generation
-----------------
The Metal text is generated from mlx's own sources (tag v0.32.2):

    bash mlx/backend/metal/make_compiled_preamble.sh \\
        <outdir> xcrun <mlx-src> steel/attn/kernels/steel_attention_nax
    python3 gen_bq128_source.py <outdir>/steel_attention_nax.cpp ...

``gen_bq128_source.py`` extracts the raw string, replaces the five
``[[function_constant]]`` declarations with concrete values, pulls the
``attention_nax_dsplit`` body out of the template, and renames the thread
attributes to the names ``mx.fast.metal_kernel`` auto-generates.
"""

from __future__ import annotations

import argparse
import math
import pathlib
import struct
import sys
import time

import mlx.core as mx

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_EXPANDED = pathlib.Path(
    "/private/tmp/mlx-preamble/steel_attention_nax.metal")

BQ = 128
BK = 32
BD = 256
WM = 8
WN = 2
THREADS = 32 * WM * WN

PARAM_FIELDS = [
    "B", "H", "D", "qL", "kL", "gqa_factor",
    "NQ", "NK", "NQ_aligned", "NK_aligned", "qL_rem", "kL_rem", "qL_off",
    "Q0", "Q1", "Q2", "K0", "K1", "K2", "V0", "V1", "V2", "O0", "O1", "O2",
]


def _generate_sources(expanded: pathlib.Path):
    sys.path.insert(0, str(HERE))
    import gen_bq128_source as gen  # noqa: PLC0415

    return {
        True: gen.build(expanded, True),
        False: gen.build(expanded, False),
    }


_CACHE: dict = {}
_ACTIVE_EXPANDED = DEFAULT_EXPANDED


def set_expanded(path) -> None:
    """Point the lane at a different expanded-source file (CLI/tests only)."""
    global _ACTIVE_EXPANDED
    _ACTIVE_EXPANDED = pathlib.Path(path)


def _kernels(expanded: pathlib.Path = DEFAULT_EXPANDED):
    key = str(expanded)
    if key in _CACHE:
        return _CACHE[key]
    if not expanded.exists():
        raise FileNotFoundError(
            f"expanded MLX source missing: {expanded}; regenerate it with "
            "make_compiled_preamble.sh (see the module docstring)")
    sources = _generate_sources(expanded)
    kernels = {}
    for align_q, (header, source) in sources.items():
        name = f"mtplx_attn_dsplit_bq{BQ}_wm{WM}_align{int(align_q)}"
        kernels[align_q] = mx.fast.metal_kernel(
            name=name,
            input_names=["Q", "K", "V", "params_int", "scale"],
            output_names=["O"],
            header=header,
            source=source,
            ensure_row_contiguous=True,
        )
    _CACHE[key] = kernels
    return kernels


def _params(q, k, v, scale: float, q_offset: int | None = None) -> mx.array:
    bsz, hq, q_len, head_dim = q.shape
    _, hkv, k_len, _ = k.shape
    gqa = hq // hkv
    q_offset = q_len if q_offset is None else q_offset
    nq = math.ceil(q_len / BQ)
    nk = math.ceil(k_len / BK)
    values = [
        bsz, hq, head_dim, q_len, k_len, gqa,
        nq, nk, q_len // BQ, k_len // BK,
        q_len - (q_len // BQ) * BQ, k_len - (k_len // BK) * BK,
        k_len - q_offset,
        hq * q_len * head_dim, q_len * head_dim, head_dim,
        hkv * k_len * head_dim, k_len * head_dim, head_dim,
        hkv * k_len * head_dim, k_len * head_dim, head_dim,
        hq * q_len * head_dim, q_len * head_dim, head_dim,
    ]
    # 0-d so mx.fast.metal_kernel binds it as `const constant float&` (a
    # 1-element array would be bound as a pointer).
    return mx.array(values, dtype=mx.int32), mx.array(scale, dtype=mx.float32)


def attention_bq128(q, k, v, *, scale: float, q_offset: int | None = None):
    """Causal, tail-aligned attention with a 128-row threadgroup tile."""
    bsz, hq, q_len, head_dim = q.shape
    if head_dim != BD or bsz != 1 or hq % k.shape[1] != 0:
        raise ValueError("unsupported shape for the bq128 lane")
    align_q = (q_len % BQ) == 0
    kernel = _kernels(_ACTIVE_EXPANDED)[align_q]
    params_int, scale_arr = _params(q, k, v, scale, q_offset)
    nq = math.ceil(q_len / BQ)
    (out,) = kernel(
        inputs=[q, k, v, params_int, scale_arr],
        grid=(nq * THREADS, hq, bsz),
        threadgroup=(THREADS, 1, 1),
        output_shapes=[(bsz, hq, q_len, head_dim)],
        output_dtypes=[q.dtype],
    )
    return out


def _time(fn, reps: int = 3) -> float:
    mx.eval(fn())
    best = float("inf")
    for _ in range(reps):
        start = time.perf_counter()
        mx.eval(fn())
        best = min(best, time.perf_counter() - start)
    return best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--q", type=int, default=2048)
    parser.add_argument("--kv", type=int, nargs="+", default=[4096, 32768, 113000])
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--expanded", default=str(DEFAULT_EXPANDED))
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    set_expanded(args.expanded)
    print(f"mlx {mx.__version__} arch {mx.device_info().get('architecture')} "
          f"BQ={BQ} BK={BK} WM={WM} WN={WN} threads={THREADS}")

    rows = []
    for kv in args.kv:
        q = mx.random.normal((1, 24, args.q, BD), dtype=mx.float16)
        k = mx.random.normal((1, 4, kv, BD), dtype=mx.float16)
        v = mx.random.normal((1, 4, kv, BD), dtype=mx.float16)
        mx.eval(q, k, v)
        scale = BD ** -0.5
        ref = mx.fast.scaled_dot_product_attention(q, k, v, scale=scale,
                                                   mask="causal")
        mx.eval(ref)
        out = attention_bq128(q, k, v, scale=scale)
        mx.eval(out)
        exact = bool(mx.array_equal(out, ref))
        max_abs = float(mx.max(mx.abs(out.astype(mx.float32)
                                     - ref.astype(mx.float32))))
        t_ref = _time(lambda: mx.fast.scaled_dot_product_attention(
            q, k, v, scale=scale, mask="causal"), args.reps)
        t_new = _time(lambda: attention_bq128(q, k, v, scale=scale),
                      args.reps)
        pairs = args.q * ((kv - args.q) + args.q / 2.0)
        flops = 4.0 * 24 * pairs * BD
        rows.append({
            "kv": kv,
            "exact": exact,
            "max_abs": max_abs,
            "control_ms": t_ref * 1e3,
            "bq128_ms": t_new * 1e3,
            "control_tflops": flops / t_ref / 1e12,
            "bq128_tflops": flops / t_new / 1e12,
            "speedup": t_ref / t_new,
        })
        del q, k, v, ref, out
        mx.clear_cache()

    print(f"\n{'kv':>8} {'exact':>6} {'max|d|':>9} {'ctl ms':>8} {'new ms':>8} "
          f"{'ctl TF':>7} {'new TF':>7} {'speedup':>7}")
    for row in rows:
        print(f"{row['kv']:>8} {str(row['exact']):>6} {row['max_abs']:>9.2e} "
              f"{row['control_ms']:>8.1f} {row['bq128_ms']:>8.1f} "
              f"{row['control_tflops']:>7.2f} {row['bq128_tflops']:>7.2f} "
              f"{row['speedup']:>7.3f}")
    if args.check_only:
        return 0 if all(r["exact"] for r in rows) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
