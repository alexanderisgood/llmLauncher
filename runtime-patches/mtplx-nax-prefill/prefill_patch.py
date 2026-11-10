"""Route the 27B's long-context prefill attention to the BQ=128 kernel.

The call site is MTPLX's split-attention hook, which imports
``scaled_dot_product_attention`` from ``mlx_lm.models.base`` inside the hook
body (``mtplx/attention_split.py``), so patching that module attribute is
enough — no engine source rewrite.

Eligibility is deliberately narrow, and the wrapper is inert — it calls the
original function — whenever anything is off:

  * head_dim 256, fp16, batch 1, GQA factor 6 (the 27B geometry)
  * ``mask`` is the causal sentinel (``None`` or ``"causal"``), never an array
  * ``q_len >= 1024`` (mlx's own gate for the fused lane) and
    ``kv_len >= 32768`` (the lane only pays above ~32K keys)
  * the cache is not a quantised cache (``bits`` attribute) and K/V are
    row-contiguous

Byte-exactness is the safety property: the kernel is mlx's own
``attention_nax_dsplit`` with BQ=128/WM=8 (see fused_prefill_bq128.py), so the
per-row arithmetic is unchanged. The launcher's gate is a byte-identical
greedy continuation.
"""

from __future__ import annotations

import os
from typing import Any

COUNTERS: dict[str, Any] = {
    "dispatched": 0,
    "stock": 0,
    "bail": 0,
    "last_bail": "",
    "installed": False,
}


def _enabled() -> bool:
    return str(os.environ.get("MTPLX_FUSED_PREFILL_SDPA", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _min_kv() -> int:
    try:
        return int(os.environ.get("MTPLX_FUSED_PREFILL_MIN_KV", "32768"))
    except ValueError:
        return 32768


def eligible(queries, keys, values, mask, cache) -> tuple[bool, str]:
    try:
        import mlx.core as mx
    except Exception:  # pragma: no cover - GPU-less environments
        return False, "no_mlx"
    if getattr(cache, "bits", None) is not None:
        return False, "quantized_cache"
    if mask is not None and not (isinstance(mask, str) and mask == "causal"):
        return False, "array_mask"
    if not all(hasattr(t, "shape") for t in (queries, keys, values)):
        return False, "not_arrays"
    if queries.ndim != 4 or keys.ndim != 4 or values.ndim != 4:
        return False, "rank"
    b, hq, q_len, head_dim = queries.shape
    kv_b, hkv, kv_len, kv_dim = keys.shape
    if (b, kv_b) != (1, 1) or hq % hkv or hq // hkv != 6:
        return False, "gqa"
    if head_dim != 256 or kv_dim != 256 or values.shape[-1] != 256:
        return False, "head_dim"
    if queries.dtype != mx.float16 or keys.dtype != mx.float16 or values.dtype != mx.float16:
        return False, "dtype"
    if q_len < 1024 or kv_len < _min_kv() or kv_len < q_len:
        return False, "window"
    return True, "ok"


def install() -> bool:
    """Install the pass-through wrapper. Returns True when engaged."""
    if not _enabled():
        return False
    if COUNTERS["installed"]:
        return True
    try:
        from mlx_lm.models import base as _base
    except Exception:
        return False
    original = getattr(_base, "scaled_dot_product_attention", None)
    if original is None or getattr(original, "_mtplx_fused_prefill", False):
        return False

    from fused_prefill_bq128 import attention_bq128  # local module

    def wrapped(queries, keys, values, cache=None, scale=None, mask=None,
                sinks=None):
        ok, reason = eligible(queries, keys, values, mask, cache)
        if not ok or sinks is not None:
            COUNTERS["stock"] += 1
            return original(queries, keys, values, cache=cache, scale=scale,
                            mask=mask, sinks=sinks)
        try:
            out = attention_bq128(queries, keys, values, scale=float(scale))
        except Exception as exc:  # noqa: BLE001 - never fail a request
            COUNTERS["bail"] += 1
            COUNTERS["last_bail"] = f"{type(exc).__name__}: {exc}"[:400]
            COUNTERS["stock"] += 1
            return original(queries, keys, values, cache=cache, scale=scale,
                            mask=mask, sinks=sinks)
        COUNTERS["dispatched"] += 1
        return out

    wrapped._mtplx_fused_prefill = True  # type: ignore[attr-defined]
    _base.scaled_dot_product_attention = wrapped
    COUNTERS["installed"] = True
    return True
