# Wiring spec: shipping a fused prefill attention kernel

19 September 2026, root. Written so the two kernel lanes (`prefill_fused_src`,
`nax_prefill2`) wire a winner the same way and nobody invents a second
integration path. Read with `bench/notes/27b-prefill-attention-mechanism.md`
(what has to be beaten) and `DESIGN.md` (kernel shape).

## 1. Where the kernel has to be called from

The 27B's full-attention layers run through a hook installed by
`mtplx/attention_split.py` (`_install_split_attention_hook`). For a dense
prefill chunk the hook falls through its verify/2-pass/blockwise/split
branches to

```python
from mlx_lm.models.base import scaled_dot_product_attention   # attention_split.py:170
...
output = scaled_dot_product_attention(queries, keys, values, cache=cache,
                                      scale=self.scale, mask=mask)   # :378
```

which for `head_dim == 256`, `qL >= 1024`, `do_causal` and no array mask calls
`mx.fast.scaled_dot_product_attention` and lands on mlx's NAX dsplit kernel.
The import is *inside* the hook body, so monkeypatching the module attribute
`mlx_lm.models.base.scaled_dot_product_attention` is enough - no source rewrite
of `attention_split.py` is needed, and the same patch covers any other call
site that imports it the same way.

Tensors at that point: `queries [B=1, Hq=24, L, 256]`, `keys`/`values
[1, Hkv=4, K, 256]`, f16, `keys`/`values` are contiguous views of the cache
(a slice along dim 2, stride 1 in the last dimension, so mlx does not copy
them).

## 2. Take-over contract (must be this narrow in the first release)

Intercept only when **all** hold, otherwise call the original function
unchanged:

* `queries.shape[-1] == keys.shape[-1] == values.shape[-1] == 256`
* `queries.shape[2] >= 1024` (the same gate mlx uses; below it, a custom kernel
  would also have to beat the vector path)
* `queries.shape[0] == 1`
* `queries.dtype == keys.dtype == values.dtype == mx.float16`
* `mask` is the causal sentinel (`None` or `"causal"`), never an `mx.array`
* `queries.shape[1] % keys.shape[1] == 0` with `gqa_factor in {6}` (the 27B is
  24/4); other factors keep the stock path
* `keys.shape[2] >= 32768` - the fused lane only pays above ~32K, and the
  decode window must never see it
* the env gate below is on, and the kernel's self-test has passed

Anything else - decode (`L` small), Q8 caches, other head dims, batch > 1,
array masks, dflash/oMLX lanes - returns the stock result. The patch must be
inert when the gate is off, including for other models on the same runtime.

## 3. Env gate and receipts

* `MTPLX_FUSED_PREFILL_SDPA=1` enables the lane; unset or `0` is the shipped
  default until the end-to-end qualification below passes.
* `MTPLX_FUSED_PREFILL_QR` (16 default) and any key-split knob are cell
  tunables, not user knobs.
* The patch must update counters that `mtplx.server.openai`'s `/health`
  payload already collects (`nax_flash_dispatch_counts` style) so the lane's
  engagement is visible without a trace env var.

## 4. Shipping path in this repo (the pattern already used for oMLX)

1. Put the kernel module somewhere importable and side-effect free, e.g.
   `runtime-patches/mtplx-nax-prefill/fused_prefill_sdpa.py`.
2. Add an installer in the style of `dflash_budget_patch.py`: a manifest with
   `beforeSha256`/`afterSha256` for every file it touches (or a `.pth`-free
   runtime monkeypatch installed by the launcher), an `inspect()` that can tell
   pristine from applied, and an `apply()` that takes the runtime lock. Extend
   `runtime_patches/mtplx/2.11.2/admission.json` with the digest of whatever
   function is patched, so a future MTPLX release that changes the call site is
   rejected instead of silently degraded.
3. `launcher.py`'s `build_mtplx` is where the env is set
   (`MTPLX_COMPILED_VERIFY_PROFILE_FENCE` is the current precedent). Add the
   new env var there, and add the module to `CONTROLLER_SOURCE_PATHS` so the
   installer is audited like the rest of the controller.
4. `doctor` must report the lane's state (engaged / inert / gate off) and the
   peak-memory implication, in the same ledger style as
   `slotstream_runtime.Q8_OPTIMIZATION_ENV`.

## 5. Qualification gates, in order (all required before shipping)

1. **Kernel self-test**: vs `mx.fast.scaled_dot_product_attention` at
   `q=2048..4096`, `kv in {32768, 113000}`, fp16 tolerance, plus a
   determinism check (same input twice, identical output).
2. **Microbench**: >= 24 TFLOP/s at the real shape, paired against a
   same-session stock control, three reps, min-time.
3. **Model-level byte gate**: the 256-token greedy continuation on
   `bench/prompts/ledger2-120000.txt` (112,881 tokens) must match the recorded
   27B reference byte-for-byte. Note this is a strict gate - the fused kernel
   changes the reduction order, so expect to have to keep the same fp32
   softmax accumulation and the same per-tile K/V walk order as mlx's kernel to
   pass it. If it cannot pass byte-exact, it does **not** ship, and the result
   is recorded as a rejected arm with the first differing token.
   *Bit-exactness is achievable and must be the first target:* the arithmetic
   of one query row does not depend on which simdgroup computes it, so a fused
   kernel that keeps `BK=32`, the ascending key-tile walk, the
   `scale*log2e`/`exp2` softmax formulation, the 16-wide QK reduction order and
   the pairwise d-half exchange order reproduces mlx's numbers exactly. Check
   it cheaply: `mx.array_equal(fused(q,k,v), mx.fast.scaled_dot_product_attention(q,k,v))`
   at q=1024, kv=4096, causal. If that is exact, the 113K case is exact too.

   **Fallback gate (root sign-off required, evidence pack mandatory)** - only
   if a bit-exact version cannot be reached *and* the speed win is >= 22.1
   TFLOP/s: report (a) microbench max absolute error vs the stock kernel on
   random inputs at the real shape, (b) the first token at which the 256-token
   continuation diverges, with the logit gap between the two candidate tokens
   *at that step* - a confident flip (gap > 0.05) disqualifies the arm, a
   statistical tie does not, (c) the same continuation compared across two
   independent prompts to show it is not prompt-specific, (d) determinism (two
   runs, identical bytes), and (e) an explicit note in `doctor` and the docs
   that the route is numerically different from the stock engine rather than
   bit-identical to it. Nothing ships under the fallback gate on a confident
   flip, a NaN/Inf, or a non-deterministic result.
4. **End-to-end**: `bench/run.py` at 128K, same-session paired, prefill and
   decode both reported, MTP acceptance (depth 3, 78/65/35%) unchanged because
   the lane does not touch the verify window.
5. **Rest of the suite**: `python3 -m pytest tests/ -q` plus the MTPLX long
   context tests, and a `doctor` run on the default and Q8 routes to prove the
   gate is inert where it should be.

## 6. If the kernel does not reach 24 TFLOP/s

Do not ship it. Record the best measured number, the first-difference token if
it fails parity, and the residual list (register pressure, tile shape,
dispatch overhead). The objective's arithmetic is in
`bench/notes/27b-prefill-attention-mechanism.md` section 3: below 24 the 27B
prefill cannot reach 1.5x on this host without a second lever, and the
honest outcome is a documented ceiling rather than a shipped regression.
