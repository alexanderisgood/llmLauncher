# Design sketch: a NAX flash-attention *prefill* kernel for d=256 GQA

Written 19 September 2026 by root from reading MTPLX's shipped kernels. This is
a starting plan, not a mandate — measure before believing any of it.

## Why the existing kernels cannot be reused as-is

`mtplx/kernels/sdpa_nax_flash.py` (`mtplx_nax_flash_partials`) is grid
`(kv_head, batch=1, kv_block)` with

```
LIVE   = GQA_F * QL            // live query rows for one KV head
NSGM   = ceil(LIVE / 16)       // 16 rows per simdgroup
blocks = 128..512              // key blocks, each ceil(n_kv/blocks) rounded to 32
```

and it writes per-(row, key-block) partials `[1, Hq, QL, blocks, D]` plus
`sums/maxs` that a separate reduce kernel merges. That is exactly right for
`QL <= 10` (verify): the whole live window fits in registers and many key
blocks can be walked in parallel. Its gates (`gqa_factor * q_len > 64`,
`q_len > 10`) exist because larger `QL` blows up both the register file and
the partials buffer.

For prefill (`q_len = 1024..2048`, `GQA_F = 6`, `LIVE = 6144..12288`):

* `LIVE` rows per threadgroup is impossible.
* Partials sized `[1, 24, 2048, blocks, 256]` f16 are 12.9 GB at
  `blocks = 512`, 1.6 GB at `blocks = 64` — too much to write per layer.

## Shape of the fix

Keep the NAXFrag / `matmul2d` inner machinery, change the parallelisation:

* Add a **query-block axis** to the grid: `(kv_head, q_block)` — e.g. 4 kv
  heads × 128 query blocks of 16 rows = 512 threadgroups. Each threadgroup owns
  `QR = 16` query rows for **all 6 q heads** of one kv head
  (`LIVE = GQA_F * QR = 96` rows = 6 simdgroups × 16 rows), so K/V tiles are
  read once per (kv_head, q_block) instead of once per q head.
* Walk the whole KV range **inside** the threadgroup with online softmax, and
  write the final `O` directly: no per-key-block partials, no separate reduce
  pass, no 12.9 GB intermediate. This is the standard flash-attention shape
  and it is what MLX's own steel attention does for d in {64,80,128}.
* Causal skipping: for the tail-aligned causal contract
  (`query i` attends keys `<= i + (n_kv - q_len)`), a query block starting at
  `q0` can stop at key `q0 + QR - 1 + (n_kv - q_len)`. Skip whole 32-key tiles
  beyond that, and mask (not skip) the boundary tile. This is where a prefill
  kernel beats a naive dense pass on the early chunks.
* Merge the existing `TK = 32` key tile, `MROWS = 16`, `desc_nt`/`desc_nn`
  descriptors, `ct_qa/ct_kb/ct_s/ct_pa/ct_vb/ct_o` cooperative tensors and the
  `o_frag[NGROUPS][2][kElemsPerFrag]` accumulator layout unchanged.

## Things that will bite

* **Store path.** The verify kernel stores through threadgroup memory and a
  shuffle dance (`tg_o`, `PHG`, phase loop) because it has to write 16-row
  tiles of a 256-wide D. Reuse it, but check the store cost at QR=16 with 6
  heads — the store is a larger fraction of prefill tiles than of verify.
* **Occupancy vs QR.** Larger `QR` amortises the K/V read but grows the
  threadgroup. Sweep QR ∈ {16, 32, 64} and, if needed, do not tie QR to
  MROWS: a threadgroup may run multiple simdgroup *rounds* over QR rows.
* **Register pressure.** The verify kernel keeps `o_frag[NGROUPS][2][8]` = 64
  floats/thread plus the softmax state; do not add live state (the Slotstream
  Q8 hoist experiment regressed for exactly this reason).
* **Dispatch shape.** The oMLX report of long-dispatch IOGPU preemption at
  high `heads * q_len * keys` does not apply to one threadgroup per
  (kv_head, q_block) — that is many short dispatches — but do keep the grid
  wide enough that the tail chunks (which have the most work) are not left to
  a handful of threadgroups.
* **Numerics.** fp32 softmax accumulation, same scaling, same tail-causal
  contract. Expect ULP-level differences vs MLX's fused SDPA; the model-level
  gate is the greedy continuation (`51f626fefe2f…` for the 27B's 256-token
  reference at 112,881 tokens).

## First milestone

A kernel that, for `B=1, Hq=24, Hkv=4, d=256, f16, q=2048, n_kv ∈ {2048,
32768, 113000}`, matches `mx.fast.scaled_dot_product_attention` within fp16
tolerance **and** beats its measured 15.5-16.9 TFLOP/s on the 113K row after
three timed reps. `bench/microbench_mlx.py --quick --sdpa-q 2048` is the
control harness; extend it with a `--kernel <module>.<function>` arm rather
than writing a new one.
