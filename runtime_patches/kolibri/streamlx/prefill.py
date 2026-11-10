"""Exact resident-first expert-major prefill with bounded mini-pools.

Each row uses its original Q6 weight, scale and bias tensors. Cached experts
are computed first, before any missing expert can evict their slot. Missing
rows retain sorted/coalesced reads and one-batch-ahead IO. A final permutation
restores the exact token/pick order before the model's router-weighted sum.

No full-pool snapshots or additional expert cache is allocated. Mini-pools
keep the configured sweep_batch cap; selected prompt/prefill/KV contracts are
unchanged. Only the LRU path calls this helper. Logical pread bytes can include
OS page-cache hits and do not measure physical SSD traffic.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import time

import mlx.core as mx
import numpy as np

from .pool import switch_forward
from .stindex import PARTS, PROJS

CACHE_SWEEP_VERSION = 1


def cached_expert_sweep(self, x: mx.array, idx: np.ndarray) -> mx.array:
    pool = self.pool
    b, t, k = idx.shape
    x_rows = x.reshape(b * t, -1)
    flat = idx.reshape(-1)
    row_of_pair = np.repeat(np.arange(b * t, dtype=np.uint32), k)
    order = np.argsort(flat, kind="stable")
    sorted_e = flat[order]
    uniq, starts = np.unique(sorted_e, return_index=True)
    bounds = np.append(starts, sorted_e.size)
    counts = bounds[1:] - bounds[:-1]
    axis = {int(e): i for i, e in enumerate(uniq)}
    resident = [int(e) for e in uniq if pool.resident(int(e))]
    missing = [int(e) for e in uniq if not pool.resident(int(e))]
    warm_ids = set()
    if self.sweep_warm:
        top = np.argsort(counts, kind="stable")[::-1][:pool.n_slots]
        warm_ids = {int(uniq[i]) for i in top}
    batches = [(True, resident[i:i+self.sweep_batch])
               for i in range(0, len(resident), self.sweep_batch)]
    batches += [(False, missing[i:i+self.sweep_batch])
                for i in range(0, len(missing), self.sweep_batch)]
    if self._sweep_ex is None:
        self._sweep_ex = ThreadPoolExecutor(max_workers=1)
    # Read the first missing batch while all resident mini-pools compute.
    # This still holds only one raw batch ahead and never creates MLX arrays
    # on the IO thread; cache placements wait until residents are consumed.
    future = (self._sweep_ex.submit(pool.reader.read_experts_raw,
                                    pool.triples_loc, missing[:self.sweep_batch])
              if missing else None)
    protected = False
    outputs, selections = [], []
    for bi, (cached, ids) in enumerate(batches):
        if cached:
            rows = {e: {p: {q: pool.pool[p][q][pool.id2slot[e]]
                            for q in PARTS} for p in PROJS} for e in ids}
        else:
            if not protected:
                # New warm inserts must evict non-warm rows first. The
                # final requested warm set fits the cache by construction.
                for e in resident:
                    if e in warm_ids:
                        pool.id2slot.move_to_end(e)
                protected = True
            if future is None:
                future = self._sweep_ex.submit(pool.reader.read_experts_raw,
                                               pool.triples_loc, ids)
            begin = time.perf_counter()
            raw = future.result()
            pool.sweep_fetch_s += time.perf_counter() - begin
            future = None
            rows = pool.reader.experts_from_raw(pool.triples_loc, ids, raw)
        # Start the next missing batch while this batch's GPU graph runs.
        if (future is None and bi + 1 < len(batches)
                and not batches[bi+1][0]):
            future = self._sweep_ex.submit(pool.reader.read_experts_raw,
                                           pool.triples_loc, batches[bi+1][1])
        mini = {p: {q: mx.stack([rows[e][p][q] for e in ids])
                    for q in PARTS} for p in PROJS}
        sel = np.concatenate([order[bounds[axis[e]]:bounds[axis[e]+1]]
                              for e in ids])
        slots = np.repeat(np.arange(len(ids), dtype=np.uint32),
                          [counts[axis[e]] for e in ids])
        xb = mx.take(x_rows, mx.array(row_of_pair[sel]), axis=0)[None]
        inds = mx.array(slots)[None, :, None]
        value = switch_forward(xb, inds, mini, pool.qparams)
        mx.async_eval(value)
        outputs.append(value)
        selections.append(sel)
        pool.sweep_experts += len(ids)
        # Existing resident rows need no placement; don't rewrite a pool
        # while another resident batch is reading its current slots.
        if not cached:
            for e in ids:
                if e in warm_ids:
                    pool.adopt(e, rows[e])
    for i in np.argsort(counts, kind="stable"):
        e = int(uniq[i])
        if e in warm_ids and e in pool.id2slot:
            pool.id2slot.move_to_end(e)
    value = mx.concatenate(outputs, axis=1)[0, :, 0]
    pairs = np.concatenate(selections)
    inverse = np.empty_like(pairs)
    inverse[pairs] = np.arange(pairs.size)
    value = mx.take(value, mx.array(inverse.astype(np.uint32)), axis=0)
    value = value.reshape(b, t, k, -1)
    mx.eval(value, *(pool.pool[p][q] for p in PROJS for q in PARTS))
    return value
