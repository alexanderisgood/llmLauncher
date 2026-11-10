# Inco Splash on this Mac

The launcher supports [Splash 1.4.0](https://github.com/incoai/splash/releases/tag/1.4.0),
released 20 October 2026, including Qwen3.8 Flash-Next GGUF, Qwen 27B and
35B-A3B with matching DFlash2 drafts.

## Local models in the launcher

Select Splash and rescan. Splash's native metadata checks decide which
checkpoints are compatible. Each GGUF quantization appears separately;
a complete split GGUF appears once, using its first shard. Discovery preserves
Hugging Face snapshot shard filenames and verifies identities of every shard.
Flash-Next requires GGUF; its MLX checkpoints are not supported by Splash.
Compatible 27B and 35B MLX affine Q4/group-64 models remain selectable.

The launcher prefers its verified `bench/runtimes/splash-1.4.0` installation,
with older runtime choices retained. The official macOS archive SHA256 is
`4c0f032a5392a6c559f081a0052278fbc0ea5abee2d16b820a015cc9b1826a2d`.
It also verifies the installed engine and Metal library against `release.json`.
Splash 1.3.1 and newer no longer load legacy Splash packs; rescan original
GGUF or MLX checkpoints instead.

Every current launch calls Splash's public `install.local.prepare_local_model()`
to prepare or refresh linked metadata without copying or requantizing weights.
Compatible local drafts are reused. Only a missing matching DFlash2 draft
is downloaded; Flash-Next uses `incoai/Qwen3.8-Flash-Next-DFlash2`.
The native server starts on a private loopback port without the removed
`--tokenizer` argument or the older frontend patch.

For MoE models the launcher uses current reclaimable memory up to Splash's
native Metal ceiling, keeping the native host reserve (2 GiB on this Mac).
There is no fixed 32 GiB ceiling or duplicate runtime reserve.
The exact budget reaches `--max-memory`. Full SSD model size is not counted
as resident RAM. Splash plans expert and PLE streaming, context, and eligible
KV spill together, and refuses an infeasible context or insufficient SSD
capacity before loading. The launcher retains the native context choices
16K/32K/64K/128K/256K; this integration does not enable static YaRN.

The relay and built-in requests use the native `thinking_token_budget`:
low 1,024, medium 4,096, xhigh/default 32,768, each at most half the response
allowance. A client's smaller budget is respected; an unlimited budget cannot
remove the route ceiling. Checkpoint requests use thinking off. Older runtimes
retain the qualified `splash_reasoning.py` adapter.

## Q4 main weights with the original BF16 PLE table

The selected Flash-Next configuration keeps Bartowski Q4_K_M main tensors
unchanged and replaces only `per_layer_token_embd.weight` with the original
BF16 table. The table is 102.4 GB on SSD; the combined target is about
186.8 GB, plus its matching DFlash2 draft.

`tools/prepare_splash_flash_bf16.py` downloads the pinned BF16 table, waits
for the pinned Q4 source and draft downloads, verifies their checksums, and
builds a native five-part GGUF. Independent APFS clones keep the large
payloads shared while headers change. Every main tensor must match its
source digest. Splash's own loader then validates the combined model and
prepares its local assembly; redundant source weights are removed only after
that succeeds. Progress and completion are recorded in
`bench/results/20261021-splash-flash-q4-bf16-setup.json`.

The launcher displays the table's actual precision separately, for example
`Q4_K · BF16 PLE`. Merely selecting a Q4 model does not imply its PLE is BF16.
Streaming preserves the stored table's values and avoids loading the whole
table into RAM. Task accuracy and speed still require a paired workload test.

The launcher prefers a separately pinned 1.4.0 build with the
[BF16 embedding-row fix](../runtime_patches/splash/1.4.0/README.md).
Official 1.4.0 incorrectly sizes Flash-Next's 160-column BF16 rows as
256-element projection blocks and fails during loading. The host-only fix
retains the official shaders and every original model-weight byte.
Splash 1.4 scans installed 6-bit MLX 27B checkpoints as well as GGUFs;
its native loader decides which quantized configurations are compatible.

The measurements below describe older 27B Q4 packs. They do not establish
Flash-Next Q4_K_M performance or the speed of the new runtime.

## Native agent timing verified on 6 October 2026

Pi and oh-my-pi passed actual write/read/final-answer tasks with the installed
Splash 1.2.1 27B Q4 pack, 16K context, 1K maximum response and reasoning off.
Their exact tool history, local authorization and request settings were checked.
One combined run stopped protectively when physical headroom fell below the
unchanged macOS reserve; a fresh oh-my-pi run passed above that reserve. That
failed attempt remains in the evidence rather than being counted as success.

Per-request generation TPS now uses Splash's native final timings paired with
final usage by response ID and model. Decode excludes the whole first native
speculative batch, whose timing clock begins after that batch. If a short answer
fits entirely in that batch, generation TPS is unavailable. First visible output
and total request time remain separate; buffered delivery and server-wide
aggregate rates cannot become per-request GPU speed.

Evidence: [Pi and protected combined run](../bench/results/20261006-splash-agents-native-verified.json),
[successful oh-my-pi run](../bench/results/20261006-splash-omp-native.json),
[native timing source contract](../bench/notes/20261006-splash-native-stats.md).

## Requirements and install

Apple M3 or newer, macOS 26.4 or newer, 36 GB+ unified memory (48 GB
recommended), Homebrew:

```sh
brew install incoai/tap/splash
splash serve --model bartowski/Qwen3.8-Flash-Next-GGUF:Q4_K_M
```

The launcher drives Splash's native frontend on a free loopback port so other
engine services can keep using port 8000. The standalone helper below is for
an older installed runtime and its legacy 27B Q4 pack, on port 8010:

```sh
python3 tools/run_splash_128k.py            # serves on 127.0.0.1:8010, Ctrl-C stops
python3 tools/run_splash_128k.py --check    # verify install + package, no launch
```

The helper checks the release hashes, executable dependencies, qualified
frontend and declared artifact paths/sizes. It uses the launcher's native
thinking-budget adapter. `--output` controls the response allowance (8,192 by
default); `--context` must be one of the supported context windows.
Requests require an API key: the helper uses `SPLASH_API_KEY` when supplied,
otherwise it generates one. On readiness it prints the path to a private key
file for configuring clients; that file is removed when the host stops.

The package is `incoai/Qwen3.8-27B-Splash` (17.4 GB): a repacked
`mlx-community/Qwen3.8-27B-4bit` target (4-bit, group 64) plus
`incoai/Qwen3.8-27B-DFlash2` as the draft, plus a vision tower. It lands in
`~/Library/Application Support/Splash/models/<owner>/<repo>`.

## Measured on this machine (M5 Pro 20-core GPU, 48 GB, 19 September 2026)

Standing 112,881-token prompt unless noted, 256 greedy tokens, reasoning off:

| Metric | Splash | MTPLX 4-bit (previous best) | Original launcher baseline |
| --- | ---: | ---: | ---: |
| Cold prefill | **324.5 / 337.9** | 315.7 | 245.1 |
| Decode | **25.30 / 25.33** | 19.30 | 4.56 |
| Cached-prefix TTFT (112,864 tokens reused) | **0.390 s** | — | — |

Decode by workload and setting (draft acceptance dominates):

| Scenario | Decode |
| --- | ---: |
| 128K prompt, reasoning off | 25.3 |
| 128K prompt, reasoning on (Splash's default) | 36.6 |
| 84K real-code prompt | 43.2 |
| 33K real-code prompt | 56.9 |
| 4 concurrent streams, 33K code, cached prefix | **114.6 aggregate** |
| 4 concurrent streams @128K, cached prefix | 45.2 aggregate |

Prefill scales flatter than anything else measured here: 463 tok/s at 1K, 422 at
33K, 370 at 84K, 338 at 113K. Against the launcher's original 128K baseline the
27B therefore runs **1.38× prefill and 5.5× decode**; against the previous best
route it is +7% prefill and +31% decode.

## Notes and caveats

### Follow-up turns: the number that matters for agent work

On a 112,881-token context, measured 19 September 2026:

| Route | Second-turn (same prefix) |
| --- | --- |
| **Splash** | **0.390 s to first token** (112,864 of 112,881 tokens reused) |
| MTPLX, warm request | **439 s** — `cachedPromptTokens: 0`; its session-bank entry is evicted at this context (`bank_entries_evicted: 1, bank_bytes_after: 0`), so every turn re-prefills the whole prompt |
| MTPLX Q8, warm request | 438 s, `cachedPromptTokens: 0` |

For a multi-turn agent the engine choice therefore matters far more than the
cold-prefill table suggests: Splash costs ~0.4 s per turn where MTPLX costs
~7.3 minutes, roughly a thousand-fold difference on the same context. Keep the
prefix stable and point agents at one Splash server.

* `--max-memory 44G` measured no better than `auto` (307.5 / 24.7 against
  324.5-337.9 / 25.3), so keep the engine's own memory plan.
* Speculative decoding verifies against the served 4-bit pack; this does not
  establish equivalence to higher-precision model weights. Greedy text
  differs from the MTPLX pack's reference wording because it is a different
  4-bit artifact.
* Concurrency is the biggest lever for agentic work: four simultaneous streams
  roughly double aggregate decode at short context, and at 128K each stream
  falls to ~11.6 tok/s while the aggregate rises to 45.2.
* The installed runtime uses a binary plus precompiled `splash.metallib`.
  The [upstream project](https://github.com/incoai/splash) publishes source;
  this launcher uses the verified release rather than rebuilding kernels.
* Measurement path: `python3 bench/run.py --engine splash …` (see
  `bench/harness.py::make_splash`), which is what produced every number above.
  Full analysis: `bench/notes/splash-engine.md`.

## Historical legacy-pack integration

Splash is wired into the launcher as its own engine like oMLX or Slotstream:

* `splash_runtime.py` discovers the Homebrew install
  (`/opt/homebrew/opt/splash/libexec`), verifies the release hashes from
  `libexec/release.json`, scans packs under
  `~/Library/Application Support/Splash/models/<owner>/<repo>` (each must carry
  a readable `manifest.json` plus `target/`, `draft/` and `tokenizer/`), and
  describes one model record per pack.
* `launcher.py` registers the adapter (`Splash`), the engine button and controls
  in the UI, the fixed context windows (16K/32K/64K/128K/256K), the memory
  estimate (packed weights + ~32.5 KiB per context token of paged KV + a 2 GiB
  reserve) and a launch path that starts `server.py` on a launcher-allocated
  loopback port — the Homebrew CLI's hardcoded 8000 is never touched, so the
  launcher's oMLX server keeps running.
* The launch re-verifies the engine release and the pack manifest identity
  before the engine loads, and the health check validates that `/v1/models`
  advertises the pack id; a changed install or pack fails closed with a rescan
  request.
* Reasoning levels `off`, `low`, `medium` and `xhigh` are pinned per route the
  same way as the other engines; sampling stays engine-owned (temperature,
  `top_p`, `top_k` pass through, penalties must remain zero). Pi and OpenCode
  use the Chat Completions surface; Codex is listed as unsupported until the
  launcher's live Responses contract check runs.

Verified end to end on 19 Sep 2026: the launcher wrapper started the engine
from the real pack at 128K on port 18790, `/v1/models` returned
`incoai/Qwen3.8-27B-Splash`, a chat completion answered correctly, and the
engine stopped cleanly with the run.

### Tool schemas (Pi and OpenCode)

Splash compiles every tool's `parameters` into an llguidance grammar and
refuses a fixed set of keywords when they sit at the schema **root** —
`$ref`, `$dynamicRef`, `allOf`, `anyOf`, `oneOf`, `not`, `if`, `then`, `else`,
`dependentRequired`, `dependentSchemas`, `enum`, `const`, `minProperties`,
`maxProperties` and `patternProperties` (see its `server/tool_schema.py`).
Nested uses are fine, and the root must describe a JSON object.

Pi's `browser_check` declares its per-action requirements with a top-level
`anyOf`, which a per-property grammar cannot represent, so the engine answered
every Pi turn with
`400 unsupported top-level tool schema keyword(s): anyOf`. The relay now
relaxes exactly those root keywords on the `splash` route before forwarding
(`splash_runtime.compatible_tool_schema` / `relax_tool_schemas`), keeps every
nested keyword — the model still sees the full property shapes, enums and
per-property descriptions — and logs one notice per relaxed request. The
refinement is not lost with it: `browser_check` validates its own arguments
(`validateArguments`), so an inconsistent action/field combination still fails
loudly and Pi feeds the error back to the model. Other engines keep the
complete schema because the relaxation is scoped to this backend.

Verified 19 Sep 2026 against the installed engine: its own compiler rejects
the unmodified schema with that exact message and compiles the relaxed one
(`tests/test_splash_tool_schemas.py`), and the real captured Pi request —
9 tools, `browser_check` carrying the top-level `anyOf` — returned `HTTP 200`
through a live relay pointed at the running engine instead of the previous
`400`.

### Response allowance and runaway reasoning

The server's `--max-new-tokens=32768` is a default, not an engine ceiling.
The launcher now permits larger responses within the selected context, leaving
at least 1,024 tokens for the prompt. Actual rendered instructions, tools and
history must also fit: Splash checks prompt plus response allowance with its
tokenizer. The selected output is carried through the wrapper, Pi and relay;
the native request deadline grows with the allowance so responses above 32K
are not cut short by the server's default 30-minute deadline. This is a maximum,
not a requirement to generate that many tokens.

The 19 September Pi fractal run passed tool execution, then exhausted all
32,768 output tokens in thinking. Its final reasoning contained 23,997
consecutive digits while inventing decimal places for a fractal coordinate.
Raising Max response does not fix that generation failure. The Pi guard now
stops an uninterrupted run of at least 4,096 digits in unfenced reasoning,
alongside its existing repeated-paragraph detection. Ordinary precision,
numeric tables, code fences, final-answer text and tool results are unaffected.
Damaged thinking is omitted from subsequent model requests and compaction;
the saved original conversation is retained. Send “continue” to retry from
the last confirmed result; compaction is not required (native Pi may refuse
to compact a short conversation). A stopped turn is not replayed automatically.

The subsequent fractal request spent all 65,536 output tokens in changing,
circular arithmetic reasoning over 40 minutes. No verbatim paragraphs repeated,
so text-pattern detection alone was insufficient.

For older runtimes, the launcher runs the native frontend through `splash_reasoning.py`.
It enforces thinking ceilings of 1,024 tokens (low), 4,096 (medium), and 32,768
(xhigh/model default), further bounded to half Max response. At the
boundary, the token mask permits only the real `</think>` token. The same
generation then continues with the answer or tool grammar, keeping the
remaining response allowance. A small reserve inside the ceiling lets an
unfinished UTF-8 character complete before closing. Natural early completion
is unaffected. Speculative mask simulations do not advance committed counts,
and each request owns its budget. No response rewriting, second model request,
tool replay, or global sampling change is involved. Homebrew files and model
weights remain untouched; the adapter checks the qualified frontend hashes
and refuses incompatible changes before the engine starts.

Pi also omits length-ended thinking-only attempts from future requests and
checkpoints. It preserves the original transcript, actual answers, successful
thinking, and tool calls/results. Recovery notices no longer recommend raising
the output cap for a thinking-only failure.

Pi now advertises Splash's actual low/medium/xhigh levels, keeping its displayed
level aligned with the pinned relay setting. Native Pi checkpoint requests use
thinking off and at most 4K output tokens, with the launcher's bounded summary
retry, so recovering a failed turn cannot consume a task-sized reasoning budget.

The installed Splash thinking defaults (temperature 1.0, top_p 0.95, top_k 20)
match [Qwen's model guidance](https://huggingface.co/Qwen/Qwen3.8-27B#api-usage).
This prevents an entire response allowance being spent on hidden reasoning;
it does not guarantee correct model reasoning or establish whether the initial
degeneration was caused by weights, quantisation or inference. As of 19 September
2026, Splash's official catalog lists only 4-bit Qwen3.8-27B and Qwen3.6-35B-A3B
packs. Ordinary Q6 MLX/GGUF files cannot load in Splash's specialized pack format.
See the [supported packs](https://github.com/incoai/splash#models).

Verified against the installed Pi and running Splash: three requests with
`max_tokens=65536` and xhigh reasoning passed the full tool schemas, executed a
write/read round trip in an isolated temporary project, and returned a normal
final answer (`tests/test_splash_pi_live.py`). This verifies the larger allowance
and agent transport, not the quality or completion of a 65K-token answer.

The budget adapter additionally passed real tokenizer/llguidance tests for
speculative boundaries, required tools, JSON and split Unicode. Three concurrent
native requests with test ceilings of 32/64/96 tokens closed thinking after
24/56/88 tokens (the internal closing reserve) and produced streaming text,
valid JSON and a valid tool call in 3.7 seconds. The 32K boundary is also tested
without spending 32K GPU tokens. A temporary-copy fractal diagnostic hit its
4K medium ceiling, then wrote and ran numerical experiments; it continued
making tool calls until the six-minute test deadline, so it is not recorded
as a completed task-quality evaluation. No changes were made to the real
fractal project. A deliberately conflicting required-tool/plain-answer probe
also demonstrated that limiting thinking does not guarantee instruction
following in the subsequent visible output.

For current Splash, download the original GGUF (all shards of one variant)
or a compatible MLX checkpoint, then rescan. For example:

```sh
hf download bartowski/Qwen3.8-Flash-Next-GGUF --include 'Qwen3.8-Flash-Next-Q4_K_M/*' --local-dir ~/.lmstudio/models/bartowski/Qwen3.8-Flash-Next-GGUF
```

Q4_K_M is about 119.6 GB on SSD; it streams within the launcher's native
memory budget. The matching DFlash2 draft is separate. Installing a legacy
`*-Splash` package does not make it loadable in 1.4.0.
