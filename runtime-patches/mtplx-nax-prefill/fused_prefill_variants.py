#!/usr/bin/env python3
"""A/B the mlx dsplit attention kernel against wider-row / no-split variants.

All variants are mlx's own kernel bodies (see gen_bq128_source.py) with
different template parameters, so the only differences are tiling and the
head-dim accumulation order:

  dsplit128  ``attention_nax_dsplit`` BQ=128 WM=8 WN=2   (bit-exact vs stock)
  nosplit64  ``attention_nax``       BQ=64  WM=4 WN=1   (no exchange; order
  nosplit128 ``attention_nax``       BQ=128 WM=8 WN=1    differs from stock)

Use it to answer: is the head-dim split (WN=2) the thing capping the stock
kernel at ~21.9 TFLOP/s, or is it rows-per-threadgroup / occupancy?
"""

from __future__ import annotations

import argparse
import math
import pathlib
import sys
import time

import mlx.core as mx

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fused_prefill_bq128 as base  # noqa: E402
import gen_bq128_source as gen  # noqa: E402

VARIANTS = {
    "dsplit128": dict(kernel="attention_nax_dsplit", bq=128, wm=8, wn=2),
    "dsplit64": dict(kernel="attention_nax_dsplit", bq=64, wm=4, wn=2),
    "nosplit64": dict(kernel="attention_nax", bq=64, wm=4, wn=1),
    "nosplit128": dict(kernel="attention_nax", bq=128, wm=8, wn=1),
}


def kernel_for(variant: str, expanded: pathlib.Path):
    specs = VARIANTS[variant]
    header, source = gen.build(expanded, True, **specs)
    threads = 32 * specs["wm"] * specs["wn"]
    kernel = mx.fast.metal_kernel(
        name=f"mtplx_attn_{variant}",
        input_names=["Q", "K", "V", "params_int", "scale"],
        output_names=["O"],
        header=header,
        source=source,
        ensure_row_contiguous=True,
    )
    return kernel, specs["bq"], threads


def run(variant: str, q, k, v, scale: float, expanded: pathlib.Path):
    kernel, bq, threads = kernel_for(variant, expanded)
    params_int, scale_arr = base._params(q, k, v, scale)
    nq = math.ceil(q.shape[2] / bq)
    (out,) = kernel(
        inputs=[q, k, v, params_int, scale_arr],
        grid=(nq * threads, q.shape[1], 1),
        threadgroup=(threads, 1, 1),
        output_shapes=[tuple(q.shape)],
        output_dtypes=[q.dtype],
    )
    return out


def _time(fn, reps: int) -> float:
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
    parser.add_argument("--kv", type=int, nargs="+", default=[32768, 113000])
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--variants", nargs="+", default=list(VARIANTS))
    parser.add_argument("--expanded", default=str(base.DEFAULT_EXPANDED))
    args = parser.parse_args()
    expanded = pathlib.Path(args.expanded)
    print(f"mlx {mx.__version__} q={args.q} reps={args.reps}")

    for kv in args.kv:
        q = mx.random.normal((1, 24, args.q, 256), dtype=mx.float16)
        k = mx.random.normal((1, 4, kv, 256), dtype=mx.float16)
        v = mx.random.normal((1, 4, kv, 256), dtype=mx.float16)
        mx.eval(q, k, v)
        scale = 256 ** -0.5
        ref = mx.fast.scaled_dot_product_attention(q, k, v, scale=scale,
                                                   mask="causal")
        mx.eval(ref)
        t_ref = _time(lambda: mx.fast.scaled_dot_product_attention(
            q, k, v, scale=scale, mask="causal"), args.reps)
        pairs = args.q * ((kv - args.q) + args.q / 2.0)
        flops = 4.0 * 24 * pairs * 256
        print(f"\nkv={kv}: stock {t_ref * 1e3:8.1f} ms "
              f"{flops / t_ref / 1e12:5.2f} TFLOP/s")
        for variant in args.variants:
            try:
                # Build the kernel and the parameter buffer ONCE per
                # (variant, shape): regenerating the 78 KB source and
                # re-creating the metal_kernel object inside the timing loop
                # costs tens of milliseconds of host time and would be
                # mistaken for kernel overhead.
                kernel, bq, threads = kernel_for(variant, expanded)
                params_int, scale_arr = base._params(q, k, v, scale)
                nq = math.ceil(q.shape[2] / bq)

                def call():
                    (out,) = kernel(
                        inputs=[q, k, v, params_int, scale_arr],
                        grid=(nq * threads, q.shape[1], 1),
                        threadgroup=(threads, 1, 1),
                        output_shapes=[tuple(q.shape)],
                        output_dtypes=[q.dtype],
                    )
                    return out

                out = call()
                mx.eval(out)
                exact = bool(mx.array_equal(out, ref))
                max_abs = float(mx.max(mx.abs(out.astype(mx.float32)
                                             - ref.astype(mx.float32))))
                secs = _time(call, args.reps)
            except Exception as exc:  # noqa: BLE001
                print(f"  {variant:11} FAILED {type(exc).__name__}: {str(exc)[:160]}")
                continue
            print(f"  {variant:11} {secs * 1e3:8.1f} ms "
                  f"{flops / secs / 1e12:5.2f} TFLOP/s  "
                  f"speedup {t_ref / secs:5.3f}  exact={exact} "
                  f"max|d|={max_abs:.2e}")
            del out
        del q, k, v, ref
        mx.clear_cache()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
