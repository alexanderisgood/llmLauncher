# 128K long-context performance (measured on this Mac, September 2026)

All numbers below were measured on an Apple M5 Pro with 48 GB unified memory,
at a **112,881-token prompt** in a 131,072-token window, greedy, with the
launcher's own runtimes and packs. Every row has a result file in
`bench/results/`; the analysis is in `bench/notes/` (`RESULTS.md`,
`27b-route-by-context.md`, `flash-next.md`, `kernel-project.md`).

## What to select in the launcher

| Model | Settings that produce the fastest measured 128K route | Prefill | Decode |
| --- | --- | ---: | ---: |
| **Qwen3.8-27B** | MTPLX · Runtime profile `turbo` (the pack default) · **KV cache precision `off` (full precision)** | 315.7 | 19.3 |
| **Qwen3.8-27B** (Splash pack) | Inco **Splash 1.0** · `splash serve --model incoai/Qwen3.8-27B-Splash` · 4-bit + DFlash 2 draft | **337.9** | **25.3** |
| **Qwen3.8 Flash-Next** | Slotstream · **KV cache precision `Q8`** (pinned `0.2.20-q8.1` runtime, enabled automatically) | 168.9 | 11.3 |
| **Qwen3.8-35B-A3B** (local GGUF) | llama.cpp via `tools/run_qwen35_moe_128k.py` (`--load-mode mlock`) | 392.1 | 32.5 |
| **Bonsai-2-27B** (2-bit ternary MLX pack) | oMLX/MLX runtime · **KV cache precision `off` (full precision)** · `prefill_step_size` 2,048 | 177.4 | 9.0 |
| **Bonsai-2-27B** (2-bit ternary GGUF) | llama.cpp · `-ctk f16 -ctv f16 -fa on -ub 512 --load-mode mlock` | 128.2 | 11.8 |

The compiled-verify fence at long context is now set by the launcher itself
(`build_mtplx`), so nothing extra has to be configured for the 27B. The
Slotstream Q8 route also sets 4,096-token prefill passes, thirteen
engine-validated read-path switches and a 4,096-token MoE workspace tile
automatically.

Splash is available in the launcher. For standalone hosting, its CLI hardcodes
port 8000, so use `python3 tools/run_splash_128k.py` (port 8010, Ctrl-C stops it).
The helper prints a private API-key file path for clients — see
[SPLASH.md](SPLASH.md) for the install, the workload-dependent decode table and
the concurrency numbers.

Two measured options sit on top of those defaults, both quality-neutral
(byte-identical greedy output, unchanged draft acceptance):

* **Flash-Next decode +4.5%** with a larger expert-pool ceiling —
  `--max-ram-percent 80` measured 11.85 tok/s against 11.34 at the default 70%
  (expert hit rate 89.5% vs 86.7%, decode reads 18.5 GB vs 23.2 GB per 256
  tokens). It raises the process ceiling to ~38 GB on a 48 GB machine, so it
  stays an explicit choice; the launcher's headroom guard and the engine's
  admission gate still protect the load.
* **MTP depth stays 2 on this route.** Depth 3 measured 10.67 tok/s against
  11.34 and drops draft acceptance from 52% to 41% — deeper is worse here.

Bonsai's two routes split the metrics: MLX wins prefill (177.4 vs 128.2,
because the GGUF path spends its time on ternary dequantisation), llama.cpp
wins decode (11.8 vs 9.0). Full precision is the right KV choice on both
(GGUF: 128.2/11.8 against 122.8/9.5 on Q8; MLX: 177.4/9.0 against 110.8/5.5).
Speculation on Bonsai-2 at 128K is closed: the published Bonsai-1 dspark
drafter is byte-exact but its acceptance collapses from 64.3% at 4K to 1.8%
at 128K (its own context is 4,096), making it 3.4x slower per committed token.

## Where the 27B prefill time actually goes

> **Update (19 Sep 2026): the budget below is superseded by a same-session,
> three-point fit of the shipped route (`bench/notes/27b-prefill-ceiling.md`):
> of the 366.8 s prefill at 112,881 tokens, 1.0 s is fixed, **227.1 s is the
> linear term** (5.497 PFLOP of GEMM, of which the measured per-shape qmm
> rates make ~199 s irreducible) and **138.7 s is attention** at 18.0
> TFLOP/s. The stock attention kernel's own ceiling is ~22 TFLOP/s (21.9 at
> kv=8k versus 18.2 at kv=113k), and every re-tiling tried (BQ=128, WN=1, a
> byte-identical clone through `mx.fast.metal_kernel`) measures *slower*. That
> makes ~1.34-1.40x the realistic ceiling for this metric; 1.5x would need
> attention at 33 TFLOP/s, i.e. a kernel that beats Apple's by a wide margin.

Measured on this machine with `bench/microbench_mlx.py` against the MTPLX
runtime's own mlx 0.32.2 (see `bench/notes/27b-prefill-hunt.md`): 4-bit qmm
runs at 27.9-28.3 TFLOP/s, bf16 GEMM at 29.5-30.2, and the fused causal
attention at the real shape (24/4 heads, head_dim 256, q=2048, kv=113,000) at
15.5-16.9 TFLOP/s. Those numbers reproduce the whole 358 s prefill — ~184 s of
GEMM at ~28 TFLOP/s, ~164 s of attention at ~15.5, ~10 s of GatedDeltaNet and
elementwise work — so the 27B prefill is running at the measured ceiling of
this stack, not at a misconfigured half of it. The remaining percent-level
knobs (MTPLX's off-by-default `MTPLX_PREFILL_ASYNC_RUNGS` dispatch rungs,
blocked GDN prefill, 1,024-token chunks, MLX scheduler settings) are being
measured in `bench/notes/27b-prefill-hunt.md`. Going materially past ~1.3x
needs a faster head-dim-256 prefill attention kernel (see
`runtime-patches/mtplx-nax-prefill/README.md`) or a quality-trading sparse
prefill, not a flag.

Two settings that look promising but measure as no-ops or regressions here:
maximum fans (`--fan-mode max` 282.3 against `smart` 289.5 tok/s same-session
on AC power with no thermal warnings) and session-to-session comparisons in
general — the identical 27B config measured 315.0 tok/s at 17:07 and 289.5 at
22:17, so only same-session pairs are trustworthy.

## The two counter-intuitive results

1. **On the 27B at 128K, Q8 KV is *slower* than full precision** — 11.2-12.0
   vs 19.3 decode tok/s — and saves only ~4 GB, because only 16 of the model's
   64 layers are full attention and its FP16 KV at this window is ~8.6 GB. Q8
   routes attention through the slower quantised-paged kernel. Use Q8 only
   when memory is genuinely tight (and note it is also the *lower* precision
   option, so the fast route is the better-quality one).
2. **On Flash-Next the same trade reverses**: the Q8 fork's kernel reads
   packed values directly and skips sparse-invisible keys, so it decodes at
   11.9 tok/s against 4.7 for the full-precision upstream build. Q8 is the
   fast choice there.

Measured alternatives that are **not** worth the time at 128K (all recorded
with evidence): MTPLX `sustained` (ties), `performance-cold` (blocked by the
engine's own long-context guard), prefill chunks 4,096 and admission 2,048
(both regressions), split/blockwise/two-pass attention (regressions), the
llama.cpp 27B GGUF route (113.5 / 10.2), oMLX+DFlash2 at 128K (94.1 / 12.0,
and its prefix cache does not fit), MTPLX 2.11.3 (slower than 2.11.2), and
both Bonsai-2 routes (122.8-177.4 prefill, 9.0-9.5 decode).

oMLX + DFlash2 remains the fast route for the 27B at **64K and below**
(15.0 decode against MTPLX's 11.1 at the same prompt), which is why the
launcher ships both profiles.
