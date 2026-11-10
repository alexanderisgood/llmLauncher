#!/usr/bin/env python3
"""MLX kernel-ear ceiling microbenchmarks for the 27B prefill route.

Measures effective TFLOP/s of the exact kernels the MTPLX prefill of
Qwen3.8-27B (4-bit affine, group 32; 24 q-heads / 4 kv-heads, head_dim 256)
issues per chunk, on whatever MLX build is on sys.path. Run it with the
MTPLX runtime venv python so the numbers describe the shipping engine:

  "$HOME/Library/Application Support/MTPLX/runtime-venv/bin/python" \
      bench/microbench_mlx.py [--reps 3]

Everything is synthetic; no model weights are read. Times include the
mx.eval of the result, i.e. they are device times plus graph build.
"""

from __future__ import annotations

import argparse
import time

import mlx.core as mx


def _time(fn, reps: int = 3, warm: int = 1) -> float:
    for _ in range(warm):
        mx.eval(fn())
    best = float("inf")
    for _ in range(reps):
        t0 = time.perf_counter()
        mx.eval(fn())
        best = min(best, time.perf_counter() - t0)
    return best


def bench_qmm(m: int, n: int, k: int, bits: int, group: int, reps: int) -> dict:
    w = mx.random.normal((n, k), dtype=mx.float16)
    x = mx.random.normal((m, k), dtype=mx.float16)
    wq, scales, biases = mx.quantize(w, group_size=group, bits=bits)
    flops = 2.0 * m * n * k
    secs = _time(
        lambda: mx.quantized_matmul(
            x, wq, scales, biases, transpose=True, group_size=group, bits=bits
        ),
        reps=reps,
    )
    return {"kernel": f"qmm {bits}bit g{group}", "m": m, "n": n, "k": k,
            "seconds": secs, "tflops": flops / secs / 1e12}


def bench_gemm(m: int, n: int, k: int, dtype, reps: int) -> dict:
    a = mx.random.normal((m, k), dtype=dtype)
    b = mx.random.normal((k, n), dtype=dtype)
    flops = 2.0 * m * n * k
    secs = _time(lambda: a @ b, reps=reps)
    return {"kernel": f"gemm {dtype}", "m": m, "n": n, "k": k,
            "seconds": secs, "tflops": flops / secs / 1e12}


def bench_sdpa(q_len: int, kv_len: int, heads: int, kv_heads: int,
               head_dim: int, causal: bool, reps: int, dtype=mx.float16) -> dict:
    q = mx.random.normal((1, heads, q_len, head_dim), dtype=dtype)
    k = mx.random.normal((1, kv_heads, kv_len, head_dim), dtype=dtype)
    v = mx.random.normal((1, kv_heads, kv_len, head_dim), dtype=dtype)
    mask = "causal" if causal else None
    flops = 2.0 * 2.0 * q_len * kv_len * head_dim * heads
    # Bottom-right-aligned causality only discounts work when the query block
    # is a large fraction of the key window (q ~ kv); at q << kv the discount
    # is q/(2*kv) and is ignored here.
    if causal and q_len >= kv_len // 4:
        flops *= 0.5
    secs = _time(lambda: mx.fast.scaled_dot_product_attention(
        q, k, v, scale=head_dim ** -0.5, mask=mask), reps=reps)
    tag = str(dtype).replace("mlx.core.", "")
    return {"kernel": f"sdpa {tag} {'causal' if causal else 'full'}", "q_len": q_len,
            "kv_len": kv_len, "heads": heads, "kv_heads": kv_heads,
            "head_dim": head_dim, "seconds": secs, "tflops": flops / secs / 1e12}


def bench_attn_matmuls(q_len: int, kv_len: int, heads: int, kv_heads: int,
                       head_dim: int, causal: bool, reps: int,
                       dtype=mx.float16) -> list[dict]:
    """The two matmuls a flash-attention kernel is made of, at one shape.

    Q@K^T is timed on a batched q (Hq, q, d) @ k^T (Hq, d, kv) with the GQA
    heads expanded, P@V on a same-shaped score buffer @ v. Combined rate is
    4*q*kv*d*Hq / (t_qk + t_pv): the rate a zero-overhead fused kernel whose
    two phases run exactly as fast as these MLX matmuls could reach. Compare
    it with the fused-SDPA row at the same shape; if the fused kernel is
    already at this number, no custom kernel can win by much.
    """
    q = mx.random.normal((heads, q_len, head_dim), dtype=dtype)
    k = mx.random.normal((heads, kv_len, head_dim), dtype=dtype)
    v = mx.random.normal((heads, kv_len, head_dim), dtype=dtype)
    mx.eval(q, k, v)
    flops_one = 2.0 * q_len * kv_len * head_dim * heads

    kt = k.transpose(0, 2, 1)
    secs_qk = _time(lambda: mx.matmul(q, kt), reps=reps)
    scores = mx.matmul(q, kt)
    mx.eval(scores)
    p = scores
    secs_pv = _time(lambda: mx.matmul(p, v), reps=reps)
    combined = 2.0 * flops_one / (secs_qk + secs_pv)
    causal_tag = "causal" if causal else "full"
    extra = {"q_len": q_len, "kv_len": kv_len, "heads": heads,
             "head_dim": head_dim, "note": f"scores {scores.nbytes / 1e9:.1f}GB"}
    return [
        {"kernel": f"QK^T {causal_tag} ({heads}/{kv_heads}hd)", **extra,
         "seconds": secs_qk, "tflops": flops_one / secs_qk / 1e12},
        {"kernel": f"P@V  {causal_tag} ({heads}/{kv_heads}hd)", **extra,
         "seconds": secs_pv, "tflops": flops_one / secs_pv / 1e12},
        {"kernel": f"matmul-pair ceiling {causal_tag}", **extra,
         "seconds": secs_qk + secs_pv, "tflops": combined / 1e12},
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--quick", action="store_true",
                    help="skip the 8192-row GEMM arms")
    ap.add_argument("--skip-sdpa", action="store_true",
                    help="GEMM/qmm arms only (~seconds, low GPU contention)")
    ap.add_argument("--attn-matmul", action="store_true",
                    help="measure the two attention matmuls (Q@K^T and P@V) at "
                         "the real prefill geometry and compare their combined "
                         "rate with fused SDPA; this is the ceiling a custom "
                         "flash kernel could approach")
    ap.add_argument("--sdpa-q", type=int, default=4096,
                    help="query rows for the SDPA arms (prefill chunk width)")
    ap.add_argument("--sdpa-sweep", action="store_true",
                    help="sweep query width / dtype / causality at 113K keys")
    ap.add_argument("--kernel", metavar="MODULE:FUNC", default=None,
                    help="import MODULE and time FUNC(q, k, v, scale) against the "
                         "fused SDPA reference at the reference geometry; the "
                         "callable must return the attention output")
    args = ap.parse_args()

    print(f"mlx {mx.__version__} device {mx.default_device()} "
          f"arch {mx.device_info().get('architecture')}")

    rows = []
    # MLP shapes of the 27B: gate/up [17408, 5120], down [5120, 17408].
    # The shipping pack is 4-bit affine group 32; group 64 is measured as
    # the NAX-kernel-coverage probe (MLX ships _nax_ qmm kernels whose
    # eligibility depends on bits/group size).
    for m in ([2048, 4096] if args.quick else [1024, 2048, 4096, 8192]):
        rows.append(bench_qmm(m, 17408, 5120, 4, 32, args.reps))
        rows.append(bench_qmm(m, 17408, 5120, 4, 64, args.reps))
        rows.append(bench_qmm(m, 5120, 17408, 4, 32, args.reps))
        rows.append(bench_qmm(m, 5120, 17408, 4, 64, args.reps))
        rows.append(bench_qmm(m, 17408, 5120, 8, 64, args.reps))
        rows.append(bench_gemm(m, 17408, 5120, mx.bfloat16, args.reps))
    if not args.skip_sdpa:
        # Full-attention prefill: 24 q-heads, 4 kv-heads, d=256, causal.
        q = args.sdpa_q
        rows.append(bench_sdpa(q, q, 24, 4, 256, True, args.reps))
        rows.append(bench_sdpa(q, 32768, 24, 4, 256, True, args.reps))
        rows.append(bench_sdpa(q, 113000, 24, 4, 256, True, args.reps))
        if args.sdpa_sweep:
            for qq in (512, 1024, 2048, 4096, 8192):
                rows.append(bench_sdpa(qq, 113000, 24, 4, 256, True, args.reps))
            rows.append(bench_sdpa(2048, 113000, 24, 4, 256, True, args.reps,
                                   mx.bfloat16))
            rows.append(bench_sdpa(2048, 113000, 24, 4, 256, False, args.reps))
        # Decode-shaped verify step for reference (3 query rows).
        rows.append(bench_sdpa(3, 113000, 24, 4, 256, False, args.reps))

    if args.kernel:
        import importlib
        mod_name, _, fn_name = args.kernel.partition(":")
        fn = getattr(importlib.import_module(mod_name), fn_name or "attention")
        for kv in (32768, 113000):
            q = mx.random.normal((1, 24, args.sdpa_q, 256), dtype=mx.float16)
            k = mx.random.normal((1, 4, kv, 256), dtype=mx.float16)
            v = mx.random.normal((1, 4, kv, 256), dtype=mx.float16)
            mx.eval(q, k, v)
            scale = 256 ** -0.5
            ref = mx.fast.scaled_dot_product_attention(q, k, v, scale=scale,
                                                       mask="causal")
            mx.eval(ref)
            out = fn(q, k, v, scale)
            mx.eval(out)
            err = float(mx.max(mx.abs(out.astype(mx.float32)
                                     - ref.astype(mx.float32))))
            secs = _time(lambda: fn(q, k, v, scale), reps=args.reps)
            flops = 4.0 * args.sdpa_q * kv * 256 * 24
            rows.append({"kernel": f"custom {fn_name or 'attention'}",
                         "kv_len": kv, "seconds": secs,
                         "tflops": flops / secs / 1e12,
                         "max_abs_vs_fused": round(err, 5)})

    if args.attn_matmul:
        # Real prefill geometry: 24 q-heads / 4 kv-heads, d=256, causal.
        # kv=32768 keeps the materialised score buffer at ~3.2 GB per arm;
        # the 113k rows use q=512 for the matmul pair (2.8 GB) and q=2048 for
        # the fused reference only, which is what the engine actually runs.
        for q_len, kv_len in ((2048, 32768), (512, 113000)):
            rows.extend(bench_attn_matmuls(q_len, kv_len, 24, 4, 256, True,
                                           args.reps))
            rows.append(bench_sdpa(q_len, kv_len, 24, 4, 256, True, args.reps))
            mx.clear_cache()
        rows.extend(bench_attn_matmuls(2048, 113000, 24, 4, 256, True, 1))
        mx.clear_cache()

    width = max(len(r["kernel"]) for r in rows)
    print(f"\n{'kernel'.ljust(width)}  params                  "
          f"{'seconds':>9}  {'TFLOP/s':>8}")
    for r in rows:
        params = " ".join(f"{k}={v}" for k, v in r.items()
                          if k not in {"kernel", "seconds", "tflops"})
        print(f"{r['kernel'].ljust(width)}  {params:<22} "
              f"{r['seconds']:9.4f}  {r['tflops']:8.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
