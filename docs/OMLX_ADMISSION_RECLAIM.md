# DFlash admission cleanup before compaction

The September 11–12 OrcaRouter 6-bit run logged 17 prefill admission refusals and one model-load memory refusal. Most prefill projections exceeded the launcher headroom limit by a small amount. The same run logged several GiB of unused Metal allocator buffers released during generation. These observations motivate reclaiming unused buffers before a refusal, but do not prove that every overnight rejection was avoidable.

`omlx_admission.py` wraps the audited oMLX 0.6.4 / dflash-mlx 0.1.10+omlx.7 preflight methods. Only a native `PrefillMemoryExceededError` on a loaded, inactive, primary DFlash engine starts recovery. It releases unused allocator buffers on oMLX's MLX executor, refreshes the guard's active-memory sample, and runs the original admission check once more. Model weights, live KV, snapshots, context settings, thinking and memory ceilings remain unchanged. Cloned prefix KV is still charged in full. Genuine overflow reaches normal Pi compaction.

The executor callback revalidates engine/guard identity and activity before acting. Cancellation while queued prevents late cleanup. Cleanup failure preserves the original typed refusal; lower limits discovered during cleanup remain authoritative. Fitting requests skip cleanup entirely. No model request is replayed.

Validation includes executor ownership, a true overflow, unchanged limits, dynamic limit reduction, cancellation, engine replacement and cleanup failure; existing headroom/pressure tests also pass. Import validation against the installed runtime loads no model. A long-running real-model comparison is still needed to establish the number of avoided refusals and net speed improvement. This does not address the distinct model-load memory refusal.

## DFlash cache precision and launcher estimates

The audited oMLX 0.6.4 adapter does not pass `quantize_kv_cache` to DFlash. Its primary target cache therefore stays full precision; TurboQuant Q4/Q6/Q8 settings configure only the BatchedEngine fallback. The native prefill guard already charges full-precision cache. It must not be relaxed using the selector's advertised quantisation savings.

Launcher capacity estimates and DFlash snapshot retention now use the same effective precision policy. At 131,072 tokens, the 27B model's 16 full-attention layers, four KV heads and 256-dimensional heads require 8 GiB of full-precision KV, rather than the 3.25 GiB previously estimated for a Q6 selection. This is full-context capacity, not a measurement of current residency. The existing control and saved profile display distinguish the DFlash primary cache from its quantised fallback.

Automatic comparisons exclude DFlash when quantised KV is selected. Older oMLX measurements comparing quantised AR/MTP with full-precision DFlash remain in history but cannot choose a winner automatically. An explicit DFlash route with a quantised fallback is preserved, including its settings; it cannot silently become quantised AR through optimisation. Full-precision comparisons remain supported. Regression coverage exercises estimates, admission, unchanged fallback settings, evidence rejection and selection in both directions without model inference.
