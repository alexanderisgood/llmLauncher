# MTPLX NAX prefill attention (workstream brief, scaffold)

Status: **open**. This directory is the home for a NAX (MetalPerformancePrimitives
tensor-ops) flash-attention **prefill** kernel for the Qwen3.8-27B's
head-dim-256 GQA causal attention, and for the evidence that says whether it is
worth shipping.

## Why this exists

Measured on this M5 Pro (`applegpu_g17s`, macOS 27.0, mlx 0.32.2, MTPLX 2.11.2 —
see `bench/notes/27b-prefill-hunt.md` and `bench/microbench_mlx.py`):

| Phase | Rate | Share of the 358 s 27B prefill |
| --- | ---: | ---: |
| 4-bit qmm GEMM (MLP + projections) | ~28 TFLOP/s | ~184 s |
| 16 full-attention layers, d=256, GQA 24/4 | **15.5-16.9 TFLOP/s** | ~164 s |
| GDN + elementwise | — | ~10 s |

The attention layers run at ~52% of the GEMM rate, and MTPLX already ships NAX
flash attention kernels for the *decode/verify* shape (`mtplx/kernels/sdpa_nax_flash.py`,
`sdpa_nax_tile.py`) that beat the scalar routes there by 15-35%. There is no
large-M (prefill) NAX kernel in the package: the shipped kernels are built around
`LIVE = GQA_F * QL` rows with `MROWS = 16` per simdgroup, which for `QL = 2048`
means 12,288 rows in one threadgroup — impossible. A prefill kernel must tile the
query axis across threadgroups and merge KV-block partials.

## Target

Beat MLX's fused SDPA (`mx.fast.scaled_dot_product_attention`, which is what
MTPLX calls for the f16-KV route) on:

* B=1, H_q=24, H_kv=4, head_dim=256, f16 **and** bf16, causal, no mask array,
  contiguous K/V
* q_len ∈ {1024, 2048} (MTPLX prefill chunk = 2048), kv_len up to 113,000

Success is ≥ +15% on this shape (≈ +7% on the 27B prefill, ≈ +20 tok/s), with
quality intact. A clean negative — a kernel that cannot beat the fused path, with
the microbenchmark table to prove it — is an acceptable and useful deliverable.

## Required gates before any adoption

1. **Kernel correctness**: vs `mx.fast.scaled_dot_product_attention` on random
   data, small shapes first (max abs/rel error), then the real geometry. fp32
   softmax accumulation, same math, no score materialisation.
2. **Microbenchmark**: same-session A/B against the fused SDPA control, ≥3 timed
   reps, best-of, geometry as above (extend `bench/microbench_mlx.py`).
3. **Model-level A/B**: standing prompt `bench/prompts/ledger2-120000.txt`
   (112,881 tokens) through the harness:

   ```sh
   python3 bench/run.py --engine mtplx --model mtplx-27b-speed --kv off \
     --context 131072 --prompt-tokens 120000 --prompt-name ledger2 \
     --gen-tokens 64 --profile turbo \
     --extra-env MTPLX_COMPILED_VERIFY_MAX_CONTEXT=131072 \
     --label 27b-nax-prefill
   ```

   paired with a same-session control; prefill tok/s is the number that matters,
   and decode/acceptance must not regress (depth 3, 78%/65%/35% by depth).
4. **Quality**: the house gate is a byte-identical greedy continuation. A
   different reduction order may legitimately shift logits by ULPs — MTPLX's own
   shipped NAX verify kernels are "validated, not bit-exact" — so report both the
   divergence (if any) and how far it propagates. Root decides adoption.

## Integration path if it wins

* Ship as a launcher-applied runtime patch the same way `runtime-patches/slotstream-q8/`
  works: a patch file against the installed MTPLX venv plus a manifest with the
  exact hashes, applied by `launcher.py` only when the configured engine version
  matches, with an env kill-switch.
* Keep it off by default until the model-level A/B and the quality evidence have
  both been reproduced twice.

## Constraints

* The bench lock `/tmp/llm-launcher-bench.lock` is an `flock`; file presence does
  not mean held. Never bypass it — other agents run 9-minute 128K benchmarks.
* Keep GPU sessions ≤3 minutes while the prefill campaign is running.
* Do not edit `launcher.py`, `slotstream_runtime.py` or other shipped files from
  this workstream; produce patches and let root wire them in.
