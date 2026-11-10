# Long-context benchmark harness

One shared harness for the 128K / Q8-KV optimisation work. Every model is
launched and measured through `bench/run.py` so evidence is comparable.

## Ground rules

1. **One model at a time.** `bench/run.py` takes an exclusive `flock` on
   `/tmp/llm-launcher-bench.lock`, refuses to start when another engine is
   already resident, and waits for ≥20 GB reclaimable memory first (raise it
   with `--min-headroom-gb` for the 41 GB Slotstream runs). If you
   drive an engine by hand, wrap it in `harness.BenchLock`.
2. **Same prompt for every run.** Prompt text is cached in `bench/prompts/`.
   Never edit a prompt file that earlier results used; use a new
   `--prompt-name` instead.

   `bench/prompts/ledger-120000.txt` is the standing A/B prompt. Counted with
   the three installed Qwen tokenizers it is **112,826 tokens** (4.788
   chars/token) inside a 131,072-token window — quote that actual number in
   reports rather than "120K". Raise `--prompt-tokens` if a true 128K-token
   prompt is needed; never change the standing file.
3. **Runtime-reported token counts only.** `usage` fields and native engine
   telemetry decide throughput. Client wall-clock is secondary.
4. **Quality contract.** No weight, expert-count, routing, or quantisation
   changes. A perf change must reproduce the baseline greedy output
   (temperature 0, fixed seed) for the standard probes, or the delta has to be
   justified as numerically exact in the engine's own terms.
5. **Evidence.** Every run writes `bench/results/<stamp>-<label>.json`.
   Write findings, commands, versions and limitations to `bench/notes/<topic>.md`.
   Unmeasured claims stay out of the notes.
6. **Heavy builds** (`swift build`, `pip install`, model rebuilds) run with
   `nice -n 10` and at most 2 workers, and only while no model is loaded.

## Reference configurations

| Target | Command |
| --- | --- |
| Qwen3.8-27B, MTPLX, Q8 KV, 128K window | `python3 bench/run.py --engine mtplx --model mtplx-27b-speed --kv q8 --context 131072 --prompt-tokens 120000 --gen-tokens 256 --profile turbo --depth 3 --label 27b-baseline` |
| Qwen3.8-27B, oMLX 0.7.0.dev2, TurboQuant Q8 | `python3 bench/run.py --engine omlx --model mlx-27b-6bit --kv q8 --context 131072 --prompt-tokens 120000 --gen-tokens 256 --memory-gb 41 --label 27b-omlx-baseline` |
| Qwen3.8 Flash-Next, Slotstream Q8.2, 128K | `python3 bench/run.py --engine slotstream --model flash-next-4bit --kv q8 --context 131072 --prompt-tokens 120000 --gen-tokens 256 --memory-gb 41 --depth 2 --label flash-baseline` |

## Model aliases

`mtplx-27b-speed`, `mtplx-27b-quality`, `mlx-27b-6bit`, `flash-next-4bit`
and `qwen35-moe-q6` (the user's new 35B-A3B Q6_K GGUF, hard-linked into
`~/.lmstudio/models/Qwen/Qwen3.8-35B-A3B-GGUF/`) — see `MODEL_PATHS` in
`harness.py`.

## Engines

| `--engine` | Runtime | Notes |
| --- | --- | --- |
| `mtplx` | MTPLX app venv (`--binary` overrides, e.g. `bench/runtimes/mtplx-2.11.3/bin/mtplx`) | `--profile`, `--depth`, `--kv` (paged KV quantisation), `--extra-env` for the `MTPLX_*` surface |
| `omlx` | launcher-managed oMLX 0.7.0.dev2 | writes `settings.json` + `model_settings.json`; TurboQuant KV via `--kv` |
| `slotstream` | pinned 0.2.17 or the Q8 fork | `--memory-gb`, `--depth`, `--mtp` |
| `llamacpp` | launcher-managed llama.cpp b10740 | `--batch/--ubatch/--flash-attn`, `--extra-arg` for anything else |

## Current standings (standing `ledger2` prompt, 112,881 tokens if not noted)

| Target | Engine / config | Prefill | Decode |
| --- | --- | ---: | ---: |
| Qwen3.8-27B | MTPLX 2.11.2 stock q8 (baseline) | 244.7 | 4.56 |
| Qwen3.8-27B | MTPLX 2.11.2 + `MTPLX_COMPILED_VERIFY_MAX_CONTEXT=131072` | 271.2 | **10.05** |
| Qwen3.8-27B | MTPLX 2.11.2 f16 KV (diagnostic, out of contract) | 280.2 | 17.11 |
| Qwen3.8-27B | oMLX 0.7.0.dev2 q8, 30.9K prompt | 301.8 | 7.84 |
| Qwen3.8-35B-A3B | llama.cpp b10740 q8, `-b 2048 -ub 2048` | 358.4 | 31.7 |

Every number above has a result file in `bench/results/` and a note in
`bench/notes/`.

## Useful forms

```sh
# print the exact engine command without loading anything
python3 bench/run.py --engine mtplx --dry-run

# measure a warm prefix-cached follow-up instead of a cold prefill
python3 bench/run.py --engine slotstream --warm --label flash-warm

# leave the engine running for manual poking, then attach later
python3 bench/run.py --engine mtplx --keep-alive --label probe
python3 bench/run.py --engine mtplx --attach --port 18765 --label probe-followup
```

## What 50% faster means here

Both numbers must reach ≥1.5× of the matching baseline at a 120K-token cold
prompt with Q8 KV enabled:

* prefill tokens/s for the uncached prompt, and
* decode tokens/s for the 256-token greedy continuation.

The target is measured against the current launcher default route for each
model, on this Mac (M5 Pro, 48 GB), with the same prompt file.

## Kolibri decode scheduling experiments, 6 October 2026

Keep the qualified Kolibri SSD 8 path. Fetch-only next-layer prediction and
disabling the current GPU/read overlap preserved the original Q6 output
tokens, but neither improved decode consistently. No experiment was promoted
and the runtime's no-router-lookahead contract remains unchanged.

The controlled comparison used six fresh workers in the order
bias-aware prefetch / qualified / no overlap / no overlap / qualified /
bias-aware prefetch, with no concurrent tests. Every worker used 12 GB fixed
process memory, 8K context, 128 output tokens, BF16 KV, 64-token prefill,
1 GiB retained prompt cache, greedy sampling and the same generated 739-token
prompt. Each worker measured a cold request and a follow-up with 738 cached
prompt tokens. Candidate timings were paired with the nearest qualified
worker. Thermal state stayed nominal and low-power mode stayed off.

| Candidate | Median paired decode change | Worst paired decode change | Decision |
| --- | ---: | ---: | --- |
| GPU/read overlap disabled | +8.3% | -3.7% | Reject |
| Bias-aware fetch-only prefetch | +10.5% | -0.3% | Reject |

The median gains reflect an earlier slow baseline. Against the later adjacent
baseline, bias-aware prefetch was essentially flat: 10.207 versus 10.239 tok/s
cold and 10.299 versus 10.271 tok/s warm. It also increased warm logical
reads from 46.1 to 63.7 GB. Logical pread bytes include OS page-cache hits;
they do not measure physical SSD traffic. Generic prefetch had already
regressed cold decode by 12% in the exploratory batch and used only 25% of
its prefetched experts.

The original generic prefetch path also has an unbounded submission queue and
cannot export BF16 prediction scores through the qualified MLX NumPy buffer
protocol. The isolated experiments added a lossless FP32 score export and
limited all running, queued and retained raw-read futures to two and 64 MiB
of exact coalesced span bytes. Tiny fixtures matched stock Q6 logits and
actual routing over 97 forward passes for every variant. Full-model output
token and text hashes matched; buffers returned to zero; all owned workers
stopped. Minimum physical reclaimable memory was 19.02 GB, above the protected
5.15 GB macOS reserve.

Evidence: [controlled comparison](results/20261006-kolibri-prefetch-controlled.json)
and [exploratory comparison](results/20261006-kolibri-prefetch-experiment.json).
Reproduce with `bench/kolibri_prefetch_ab.py`; its variants are private,
unqualified benchmark shims, never launcher settings. Require improved median
and worst-case paired decode rates before considering a production change.
