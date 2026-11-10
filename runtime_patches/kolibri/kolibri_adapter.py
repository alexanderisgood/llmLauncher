"""Register the publisher's pinned Kolibri implementation for streamlx.

Checkpoint bytes stay unchanged. Adapt the expert module name for streamlx
and optionally quantize only the model's full-attention KV caches.
"""
import sys
import types
from pathlib import Path


def register(kv_bits=None, kv_group_size=64):
    if kv_bits not in (None, 4, 6, 8) or kv_group_size != 64:
        raise ValueError('Kolibri KV requires full precision or Q4/Q6/Q8 with group size 64')
    name = 'mlx_lm.models.kolibri1'
    if name in sys.modules:
        module = sys.modules[name]
        if not hasattr(module, '_kolibri_original_make_cache'):
            raise RuntimeError('An unqualified Kolibri implementation is already registered')
    else:
        path = Path(__file__).with_name('kolibri1.py')
        source = path.read_text()
        if source.count('self.experts') != 2:
            raise RuntimeError('Publisher implementation differs from the reviewed build')
        module = types.ModuleType(name)
        module.__file__ = str(path)
        module.__package__ = 'mlx_lm.models'
        # Rename without adding a second reference to its weights.
        source = source.replace('self.experts', 'self.switch_mlp')
        sys.modules[name] = module
        exec(compile(source, str(path), 'exec'), module.__dict__)
        original = module.Model.sanitize

        def sanitize(self, weights):
            weights = original(self, weights)
            return {key.replace('.mlp.experts.', '.mlp.switch_mlp.'): value
                    for key, value in weights.items()}

        module.Model.sanitize = sanitize
        module._kolibri_original_make_cache = module.Model.make_cache

    from mlx_lm.models.cache import KVCache, QuantizedKVCache
    import mlx.core as mx
    from mlx.utils import tree_map

    class PackedKVCache(QuantizedKVCache):
        def update_and_fetch(self, keys, values):
            if self.bits != 6:
                return super().update_and_fetch(keys, values)
            # mlx-lm 0.31.3 uses dim // (32 // bits) when allocating caches.
            # Q6 packs 128 values into 24 uint32s, not 25. Keep the native
            # cache protocol and quantizer while correcting this allocation.
            batch, heads, count, _ = keys.shape
            prev = self.offset
            if self.keys is None or prev + count > self.keys[0].shape[-2]:
                steps = (self.step + count - 1) // self.step * self.step
                shape = (batch, heads, steps)

                def allocate(dim):
                    return (mx.zeros((*shape, dim * self.bits // 32), dtype=mx.uint32),
                            mx.zeros((*shape, dim // self.group_size), dtype=keys.dtype),
                            mx.zeros((*shape, dim // self.group_size), dtype=keys.dtype))

                if self.keys is None:
                    self.keys, self.values = allocate(keys.shape[-1]), allocate(values.shape[-1])
                else:
                    if prev % self.step:
                        self.keys, self.values = tree_map(lambda x: x[..., :prev, :], (self.keys, self.values))
                    self.keys, self.values = tree_map(
                        lambda x: mx.concatenate([x, mx.zeros((*shape, x.shape[-1]), dtype=x.dtype)], axis=-2),
                        (self.keys, self.values))
            self.offset += count
            qk = mx.quantize(keys, group_size=self.group_size, bits=self.bits)
            qv = mx.quantize(values, group_size=self.group_size, bits=self.bits)
            for i in range(3):
                self.keys[i][..., prev:self.offset, :] = qk[i]
                self.values[i][..., prev:self.offset, :] = qv[i]
            return tree_map(lambda x: x[..., :self.offset, :], (self.keys, self.values))

    def make_cache(self):
        caches = module._kolibri_original_make_cache(self)
        if kv_bits is not None:
            # Rotating caches intentionally retain the publisher's exact
            # sliding-window handling. Quantize full attention from token 0.
            caches = [PackedKVCache(group_size=kv_group_size, bits=kv_bits)
                      if isinstance(cache, KVCache) else cache for cache in caches]
        return caches

    module.Model.make_cache = make_cache
    return module
