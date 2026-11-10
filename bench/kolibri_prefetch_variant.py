"""Unqualified, process-local exact-routing Kolibri prefetch experiments.

Predictions choose original rows to read early. They never replace actual
router indices or any tensor bytes. Raw prefetch buffers are bounded by exact
coalesced span bytes, including gaps, and by outstanding/retained futures.
No queued task or completed result bypasses those limits. This module is not
used by the launcher or qualified engine worker.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading

PROJS = ("gate_proj","up_proj","down_proj")
PARTS = ("weight","scales","biases")


class PrefetchBudget:
    def __init__(self, max_outstanding=2, max_bytes=64*1024**2, workers=1):
        if type(max_outstanding) is not int or max_outstanding < 1 or type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("Use positive bounded prefetch limits")
        self.max_outstanding,self.max_bytes = max_outstanding,max_bytes
        self._executor = ThreadPoolExecutor(max_workers=workers,thread_name_prefix="kolibri-bench-pf")
        self._lock = threading.Lock()
        self._pending = {}
        self._bytes = 0
        self._closed = False
        self.stats = {"submitted":0,"skippedBound":0,"discarded":0,"used":0,"failed":0,
                      "peakOutstanding":0,"peakReservedBytes":0}

    @staticmethod
    def span_bytes(reader,triples,ids):
        requests = []
        for expert in ids:
            for projection in PROJS:
                for part in PARTS:
                    path,offset,count = triples[projection][part].expert_range(expert)
                    requests.append(((expert,projection,part),path,offset,count))
        return sum(span[2] for span in reader._plan(requests))

    def submit(self,fn,*args,cost):
        if type(cost) is not int or cost < 1:
            raise ValueError("Reserve the exact positive coalesced read size")
        token = object()
        with self._lock:
            if self._closed or len(self._pending) >= self.max_outstanding or self._bytes+cost > self.max_bytes:
                self.stats["skippedBound"] += 1
                return None
            entry = {"cost":cost,"future":None,"discard":False}
            self._pending[token] = entry; self._bytes += cost
            self.stats["submitted"] += 1
            self.stats["peakOutstanding"] = max(self.stats["peakOutstanding"],len(self._pending))
            self.stats["peakReservedBytes"] = max(self.stats["peakReservedBytes"],self._bytes)
        try:
            future = self._executor.submit(fn,*args)
        except Exception:
            with self._lock:
                self._drop(token); self.stats["failed"] += 1
            raise
        with self._lock:
            entry["future"] = future
        future.add_done_callback(lambda value:self._done(token,value))
        return future

    def _drop(self,token):
        entry = self._pending.pop(token,None)
        if entry is not None:
            self._bytes -= entry["cost"]

    def _done(self,token,future):
        with self._lock:
            entry = self._pending.get(token)
            if entry is not None and not future.cancelled() and future.exception() is not None:
                self.stats["failed"] += 1
            if entry is not None and entry["discard"]:
                self._drop(token)

    def release(self,future,*,used=False):
        if future is None:
            return
        with self._lock:
            found = next(((token,entry) for token,entry in self._pending.items()
                          if entry["future"] is future),None)
            if found is None:
                return
            token,entry = found
            if entry["discard"]:
                return
            entry["discard"] = True
            self.stats["used" if used else "discarded"] += 1
            if future.done():
                self._drop(token)
                return
        # A running read retains its reservation until its done callback.
        # Queued unused work can be cancelled; the callback releases it.
        future.cancel()

    def snapshot(self):
        with self._lock:
            return {**self.stats,"outstanding":len(self._pending),"reservedBytes":self._bytes,
                    "maxOutstanding":self.max_outstanding,"maxBytes":self.max_bytes}

    def close(self):
        with self._lock:
            self._closed = True
            futures = [entry["future"] for entry in self._pending.values() if entry["future"] is not None]
        for future in futures:
            self.release(future)
        self._executor.shutdown(wait=True,cancel_futures=True)
        with self._lock:
            for token in list(self._pending):
                self._drop(token)


def install(variant,*,max_outstanding=2,max_bytes=64*1024**2):
    """Modify only this isolated benchmark process before model construction."""
    if variant not in {"qualified","no-overlap","prefetch","bias-prefetch"}:
        raise ValueError("Unknown unqualified prefetch experiment")
    import mlx.core as mx
    import mlx.nn as nn
    from streamlx import integrate,pool as pool_module
    if variant == "qualified":
        return None
    if variant == "no-overlap":
        integrate.StreamingSwitchGLU._overlapped = lambda self,x,indices:None
        return None
    budget = PrefetchBudget(max_outstanding,max_bytes)
    previous_absorb = pool_module.StreamingSwitchMLP.prefetch_absorb

    def start(self,pred,unused_executor):
        previous,self._pf = self._pf,None
        if previous is not None:
            budget.release(previous[2])
        rank = {expert:i for i,expert in enumerate(pred)}
        launch = [expert for expert in pred if expert not in self.id2slot and rank[expert] < self._PF_TOPM]
        future = None
        if launch:
            cost = budget.span_bytes(self.reader,self.triples_loc,launch)
            future = budget.submit(self.reader.read_experts_raw,self.triples_loc,launch,cost=cost)
        if future is None:
            launch = []
        else:
            self.pf_launched += len(launch)
            for expert in launch:
                self.pf_rank.setdefault(rank[expert],[0,0])[0] += 1
        self._pf = (set(pred),launch,future,rank)

    def absorb(self,wanted):
        pending = self._pf
        before = self.pf_used
        try:
            return previous_absorb(self,wanted)
        finally:
            if pending is not None:
                budget.release(pending[2],used=self.pf_used > before)

    pool_module.StreamingSwitchMLP.prefetch_start = start
    pool_module.StreamingSwitchMLP.prefetch_absorb = absorb
    # MLX0.32 cannot export BF16 scores through NumPy's buffer protocol.
    # A lossless BF16->FP32 score conversion changes only prefetch ranking
    # transport, never the actual router or any model tensor precision.
    previous_predict = integrate.StreamingSwitchGLU._pf_pred_lazy
    def exported_prediction(self,x,k):
        value = previous_predict(self,x,k)
        return (value[0],value[1].astype(mx.float32)) if value is not None else None
    integrate.StreamingSwitchGLU._pf_pred_lazy = exported_prediction
    if variant == "bias-prefetch":
        original_load = integrate.load_streaming_model
        def loaded(*args,**kwargs):
            result = original_load(*args,**kwargs)
            model = result[0]
            for layer in model.layers:
                wrapper = getattr(getattr(layer,"mlp",None),"switch_mlp",None)
                link = getattr(wrapper,"_pf_next",None)
                if link is not None:
                    target = model.layers[link[0].layer].mlp
                    wrapper._bench_prediction_bias = target.expert_bias
            return result
        integrate.load_streaming_model = loaded
        def predict(self,x,k):
            link = self._pf_next
            if link is None:
                return None
            target,gate,current_norm,next_norm = link
            if target.pf_agree_tot >= 512 and target.prefetch_agreement() < .55:
                return None
            try:
                ratio = getattr(self,"_bench_prediction_ratio",None)
                if ratio is None:
                    ratio = next_norm.astype(mx.float32)/current_norm.astype(mx.float32)
                    self._bench_prediction_ratio = ratio
                approximate_input = x.astype(mx.float32)*ratio
                if isinstance(gate,nn.QuantizedLinear):
                    logits = gate(approximate_input.astype(x.dtype)).astype(mx.float32)
                else:
                    logits = approximate_input @ gate.weight.astype(mx.float32).T
                logits = logits + self._bench_prediction_bias
                indices = mx.argpartition(-logits,kth=k-1,axis=-1)[...,:k]
                return indices,mx.take_along_axis(logits,indices,axis=-1)
            except Exception:
                self._pf_next = None
                return None
        integrate.StreamingSwitchGLU._pf_pred_lazy = predict
    return budget
