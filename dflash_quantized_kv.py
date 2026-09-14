"""Process-local quantized Qwen DFlash KV with reusable RAM/SSD snapshots.

The native cache quantizer and attention kernels own numerical behavior. This
adapter carries their packed arrays and precision through native prefix storage.
It is installed only in a dedicated launcher engine, before any model is loaded.
"""
from dataclasses import replace
from functools import wraps
import inspect
import json
import logging
import textwrap


def _rewrite(function, changes):
    """Patch audited native methods without editing the installation."""
    source = textwrap.dedent(inspect.getsource(function))
    for before, after in changes:
        if source.count(before) != 1:
            raise RuntimeError("The audited DFlash quantized-cache interface changed.")
        source = source.replace(before, after)
    namespace = dict(function.__globals__)
    exec(compile(source, inspect.getfile(function), "exec"), namespace)
    return namespace[function.__name__]


def install_quantized_kv(engine_type, bits, *, versions):
    if bits not in (4, 6, 8):
        raise ValueError("DFlash KV precision must be Q4, Q6, or Q8.")
    if versions != ("0.6.4", "0.1.10+omlx.7"):
        raise RuntimeError("Quantized DFlash KV requires the audited oMLX 0.6.4 runtime.")
    installed = engine_type.__dict__.get("_launcher_quantized_kv_bits")
    if installed is not None:
        if installed != bits:
            raise RuntimeError("KV precision cannot change inside a loaded engine process.")
        return

    import mlx.core as mx
    from mlx_lm.models.cache import QuantizedKVCache
    from dflash_mlx.cache import codecs, snapshot, prefix_l1, prefix_l2
    from dflash_mlx.engine import spec_epoch
    from dflash_mlx.engine.target_qwen_gdn import QwenGdnTargetOps
    from dflash_mlx.server import prefix_cache_manager, prefix_cache_flow
    from dflash_mlx.runtime.config import validate_runtime_config

    # Native allocation truncates 32 / bits before multiplying. That happens
    # to work for Q4/Q8, but allocates 51 words instead of 48 for a Q6 256D head.
    update = _rewrite(QuantizedKVCache.update_and_fetch, [
        ("dim // el_per_int", "dim * self.bits // 32"),
        ("        el_per_int = 8 * mx.uint32.size // self.bits\n", ""),
    ])
    open_session = _rewrite(spec_epoch.SpeculativeSession.open.__func__, [
        ("(quantize_kv_cache or target_fa_window > 0)", "target_fa_window > 0"),
    ])
    stream_events = _rewrite(engine_type._stream_dflash_events, [
        ("        runtime_context=self._runtime_context,\n        logits_processor=",
         "        runtime_context=self._runtime_context,\n        quantize_kv_cache=True,\n        logits_processor="),
    ])
    original_serialize = codecs.serialize_target_cache
    original_hydrate = codecs.hydrate_target_cache
    original_slice = codecs.slice_snapshot_at_sidecar_boundary
    original_eligible = codecs.sidecar_eligible
    original_sizes = snapshot.DFlashPrefixSnapshot.nbytes_breakdown
    original_save, original_load = prefix_l2._serialize, prefix_l2._deserialize
    original_key = prefix_cache_manager.build_prefix_key
    original_make = QwenGdnTargetOps.make_cache
    original_context = engine_type._build_runtime_context

    def quantized(state):
        return state is not None and len(state) == 5

    def serialize(cache, *, clone=True):
        fa, gdn = [], []
        for entry in cache:
            if isinstance(entry, QuantizedKVCache):
                if entry.empty():
                    fa.append(None)
                else:
                    keys, values = entry.state
                    grab = codecs._clone_array if clone else lambda a: a
                    fa.append((tuple(grab(a) for a in keys),
                               tuple(grab(a) for a in values),
                               int(entry.offset), entry.bits, entry.group_size))
                gdn.append(None)
            else:
                f, g = original_serialize([entry], clone=clone)
                fa.extend(f)
                gdn.extend(g)
        return tuple(fa), tuple(gdn)

    def hydrate(saved, template):
        if len(template) != len(saved.fa_states) or len(template) != len(saved.gdn_states):
            raise ValueError("Quantized snapshot layer count does not match the model.")
        codecs._validate_snapshot_cache_prefix_len(saved.fa_states, prefix_len=saved.prefix_len)
        result = []
        for i, entry in enumerate(template):
            state = saved.fa_states[i]
            if isinstance(entry, QuantizedKVCache):
                if not quantized(state) or tuple(state[3:]) != (entry.bits, entry.group_size):
                    raise ValueError("Snapshot KV precision does not match this engine.")
                k, v, offset, precision, group = state
                if (len(k) != 3 or len(v) != 3
                        or any(int(a.shape[2]) != offset for a in (*k, *v))):
                    raise ValueError("Quantized snapshot arrays must have exact prefix lengths.")
                restored = QuantizedKVCache(group_size=group, bits=precision)
                restored.keys, restored.values, restored.offset = k, v, offset
                result.append(restored)
            else:
                if quantized(state):
                    raise ValueError("Cannot restore quantized KV into a full-precision cache.")
                result.extend(original_hydrate(replace(saved, fa_states=(state,),
                    gdn_states=(saved.gdn_states[i],)), [entry]))
        return result

    def slice_boundary(saved, **kwargs):
        # Let upstream validate all boundary, recurrent-state and hidden-feature
        # coverage invariants; slice each packed tensor at the same token index.
        plain = tuple(None if quantized(s) else s for s in saved.fa_states)
        sliced = original_slice(replace(saved, fa_states=plain), **kwargs)
        boundary = sliced.prefix_len
        fa = tuple((tuple(a[:, :, :boundary, :] for a in s[0]),
                    tuple(a[:, :, :boundary, :] for a in s[1]), boundary, *s[3:])
                   if quantized(s) else sliced.fa_states[i]
                   for i, s in enumerate(saved.fa_states))
        return replace(sliced, fa_states=fa)

    def eligible(cache):
        return original_eligible([c for c in cache if not isinstance(c, QuantizedKVCache)])

    def sizes(saved):
        result = original_sizes(replace(saved, fa_states=tuple(
            None if quantized(s) else s for s in saved.fa_states)))
        result["fa_kv"] += sum(int(a.nbytes) for s in saved.fa_states if quantized(s)
                                for tensors in s[:2] for a in tensors)
        return result

    def save(saved):
        # Keep upstream's SSD metadata and validation for every other tensor.
        plain = tuple((s[0][0], s[1][0], s[2]) if quantized(s) else s
                      for s in saved.fa_states)
        arrays, metadata = original_save(replace(saved, fa_states=plain))
        formats = {}
        for i, state in enumerate(saved.fa_states):
            if not quantized(state):
                continue
            formats[str(i)] = list(state[3:])
            for name, tensors in zip(("k", "v"), state[:2]):
                for part in (1, 2):
                    arrays[f"fa_{i}_{name}_quant_{part}"] = tensors[part]
        if formats:
            meta = json.loads(metadata["dflash_meta"])
            meta["launcher_quantized_kv_v1"] = formats
            metadata["dflash_meta"] = json.dumps(meta, separators=(",", ":"))
        return arrays, metadata

    def load(arrays, meta):
        saved = original_load(arrays, meta)
        fa = list(saved.fa_states)
        for index, config in meta.get("launcher_quantized_kv_v1", {}).items():
            i = int(index)
            if config not in ([4, 64], [6, 64], [8, 64]):
                raise ValueError("Unsupported saved DFlash KV format.")
            k, v, offset = fa[i]
            k = (k, arrays[f"fa_{i}_k_quant_1"], arrays[f"fa_{i}_k_quant_2"])
            v = (v, arrays[f"fa_{i}_v_quant_1"], arrays[f"fa_{i}_v_quant_2"])
            fa[i] = (k, v, offset, *config)
        return replace(saved, fa_states=tuple(fa))

    @wraps(original_key)
    def key(*args, **kwargs):
        base = original_key(*args, **kwargs)
        return replace(base, target_model_id=f"{base.target_model_id}:launcher-kv-v1-q{bits}-g64")

    @wraps(original_make)
    def make_cache(ops, model, **kwargs):
        caches = original_make(ops, model, **kwargs)
        for entry in caches:
            if isinstance(entry, QuantizedKVCache):
                entry.bits = bits
        return caches

    @wraps(original_context)
    def context(engine):
        ctx = original_context(engine)
        if ctx.runtime.verify_mode not in ("adaptive", "dflash"):
            raise ValueError("Quantized DFlash KV requires Adaptive or Fixed DFlash; DDTree is incompatible.")
        # Quantized attention materializes scores; the FP16 fused-attention
        # prefill default (2048 queries) creates multi-GiB temporaries at long
        # context and makes the process enforcer evict otherwise reusable KV.
        cfg = validate_runtime_config(replace(ctx.runtime, quantize_kv_cache=True,
            prefill_step_size=min(ctx.runtime.prefill_step_size, 128)))
        return replace(ctx, runtime=cfg)

    # Publish only after all source checks and wrapper construction succeeded.
    QuantizedKVCache.update_and_fetch = update
    codecs.serialize_target_cache = serialize
    codecs.hydrate_target_cache = hydrate
    spec_epoch.hydrate_target_cache = hydrate
    # The rewritten method has its own globals mapping.
    open_session.__func__.__globals__["hydrate_target_cache"] = hydrate
    spec_epoch.SpeculativeSession.open = open_session
    codecs.slice_snapshot_at_sidecar_boundary = slice_boundary
    prefix_l1.slice_snapshot_at_sidecar_boundary = slice_boundary
    codecs.sidecar_eligible = spec_epoch.sidecar_eligible = eligible
    snapshot.DFlashPrefixSnapshot.nbytes_breakdown = sizes
    prefix_l2._serialize, prefix_l2._deserialize = save, load
    prefix_cache_manager.build_prefix_key = prefix_cache_flow.build_prefix_key = key
    QwenGdnTargetOps.make_cache = make_cache
    engine_type._build_runtime_context = context
    engine_type._stream_dflash_events = stream_events
    engine_type._launcher_quantized_kv_bits = bits
    logging.getLogger(__name__).info("DFlash target KV: Q%s, group 64; RAM/SSD prefix reuse enabled", bits)
