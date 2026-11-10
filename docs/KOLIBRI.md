# Kolibri Q6 with SSD expert offloading

Choose **Kolibri SSD**, the complete **Kolibri-1-MLX-6bit** checkpoint, and
**Chat**, **Pi** or **oh-my-pi**. Context choices run from **2K to the checkpoint's native 256K**:
2K, 4K, 8K, 16K, 32K, 64K, 128K and 256K. Maximum response can reach
**65,536 tokens**, while leaving at least 1,024 tokens for the prompt.
For long conversations, start with **Q8 KV**, a **64-token prefill chunk**,
automatic memory sizing and reasoning off. Pi uses the same selected context,
maximum response, KV precision, prefill and expert-cache settings as Chat.

## Using Pi

Select **Kolibri SSD → Kolibri-1-MLX-6bit → Pi**, choose your project and launch
in Hub Console or a terminal. The provider is scoped to that launcher session;
the launcher does not change global Pi settings. Reasoning choices are **off,
low, medium and high**.

The checkpoint's native `json_tools` parser converts `<tool_call>` blocks into
OpenAI function-tool responses. Pi receives tool-call IDs, executes its tools
in the selected project, and sends the results and assistant reasoning back
through the native Kolibri chat template. Requests support text strings and
text content blocks, including assistant turns containing only tool calls.
Tool schemas are preserved. Tool selection is automatic; `tool_choice: none`
omits the tool definitions, while forced/required selection is rejected.

The context guard counts the rendered tool definitions, tool history and
reasoning using Kolibri's actual tokenizer before generation. Context overflow
returns `context_length_exceeded` so Pi can trigger its native compaction.
Pi's native summary requests use reasoning off and at most 4,096 response
tokens, with one shorter retry for an incomplete summary. Original transcripts
remain saved. Images are not supported by this route.

The initial Pi integration was implemented without a live Pi test, as requested.
Both Pi and oh-my-pi subsequently passed real tool/history checks on 6 October,
as described below. These short tasks do not establish arbitrary long-task
quality or full-window capacity.

## Performance and agent verification on 6 October 2026

The qualified **Kolibri SSD 8** worker reuses original resident Q6 experts
during prefill and reports native generation timing. In one controlled original
checkpoint comparison, identical 739-token prompts and 128-token outputs showed
24.8% higher cold prefill throughput and 18.8% higher warm prefill throughput. Output token/text
hashes and final expert-cache order matched. Decode varied in both directions;
this establishes a prefill improvement, not a general decode-TPS improvement.

Real Pi and oh-my-pi tasks then executed temporary-file write/read tools and
returned final answers on the exact 8K context, 1K maximum-response,
reasoning-off, BF16 KV, 64-token prefill, 1 GiB retained prompt-cache and 12 GB
process-ceiling contract. Follow-up prompts reused their native cached prefix.
Minimum physical memory available for loading was 17.23 GB, above the unchanged
5.15 GB macOS reserve. All test-owned workers stopped.

The interface uses count-validated native `mlx-lm` generation seconds and rates.
Socket-delivery speed is excluded because this server can buffer output during
generation. Native decode observations of 9.21, 10.43 and 14.2 tok/s belong
to those exact requests; they are not a universal model-speed promise.

Evidence: [prefill comparison](../bench/results/20261006-kolibri-model-ab.json),
[real agent checks](../bench/results/20261006-kolibri-agents-native.json).
Fetch-only decode prediction was also tested and rejected because it did not
improve consistently; the qualified worker retains no router lookahead.

For additional loop detection, [Pi Loop Police](https://pi.dev/packages/pi-loop-police?type=extension)
is an optional Pi package. Version 1.14.1 detects short repeated thinking,
semantic paragraph loops, output loops and repeated tool calls. It loads on
the next Pi launch or extension reload. To avoid blocking legitimate paging
through source files, set `REREAD_WINDOW=0`; the other stream and tool guards
remain enabled. External notification/log hooks are optional and disabled by
default. The launcher also removes repeated short thinking from resumed model
context without editing the saved transcript.

## KV cache and prompt settings

**Full precision, Q8, Q6 and Q4** are available. Quantization applies from the
first token to all **10 full-attention layers**, using group size 64. The
**40 sliding-attention layers keep their native BF16 rotating caches**: the
installed mlx-lm version does not implement rotating-cache quantization.
Their 513-token windows remain bounded at every selected context length.
The checkpoint weights always remain Q6; KV precision is a separate setting.
Lower KV precision can change output, so Q8 is the conservative starting choice.

The launcher adapts cache construction inside its own worker and corrects
mlx-lm 0.31.3's Q6 packed-buffer width (128 values need 24 uint32s). The pinned
publisher architecture and LM Studio's installed libraries remain unchanged.
The route planner, saved profiles, optimizer and live readiness check preserve
the selected KV precision.

**Prefill chunk** defaults to **64**, and supports 64, 128, 256, 512, 1,024 and 2,048 tokens. Larger chunks
need more temporary attention memory, especially with quantized KV at long
context. Smaller chunks can leave more room for resident expert weights.
At 256K with quantized KV, the attention workspace reserve alone is 24 GiB
with a 256-token chunk, versus 6 GiB with 64. The smaller default lets the
planner assign the freed budget to resident Q6 experts, reducing SSD traffic.
Larger chunks can improve prompt batching when that extra workspace fits;
they remain selectable and saved explicit choices are preserved.
**Retained prompt cache** supports 0–8 GiB; 0 disables retention. Long prefixes
need a larger retention budget to benefit from reuse. This budget is separate
from the active conversation's KV cache and included in the process ceiling.
An earlier prefill snapshot preserves reuse when the assistant's generation
suffix differs from its next-turn history. Snapshot keys include any already
cached prefix, so reused state always matches its full token position.

The model remains in its existing MLX model folder. Its 13 shards contain
63,517,990,178 bytes. No weights are copied into the launcher repository.
The reviewed Kolibri implementation and streamlx read the original Q6 tensors
and preserve all 384 experts in each of 50 layers with native top-6 routing.

## Memory sizing

**Automatic** is the default, with a **40 GB maximum process memory** ceiling.
This is a ceiling, not a request to allocate all 40 GB regardless of other apps.
The planner spends the remaining admissible budget on the largest whole number
of resident expert slots per layer after reserving the complete trunk,
the complete selected-context KV at the chosen precision, the configured
retained prompt cache (default 1 GiB), 256 MiB MLX buffer cache, and a 2 GiB
base runtime allowance plus prefill workspace. Quantized attention materializes
scores, so its workspace reserve grows with context and chunk size. Quantizing
KV therefore does not guarantee a larger expert cache or faster execution.
The planner separately protects at least 4 GiB
or 10% of installed memory for macOS, whichever is larger.

Current macOS headroom and Metal's recommended working set also bound the
allocation. The worker rechecks them immediately before loading. Less available
memory reduces the expert cache while preserving the selected context and
reasoning settings. Fixed mode rejects a ceiling that cannot fit. A larger Mac
may cache all experts. Expert slots fill as they are used and retain recently
used weights; a configured cache capacity does not prove every slot already
contains a useful expert.

Each launch reports its rechecked allocation in its private run folder.
These are allocation estimates, not a benchmark or measured peak. If a large
context and prefill chunk cannot fit even six expert slots per layer, the
launcher rejects that combination; reduce the chunk or retention budget.

Only per-process MLX memory/cache/wired limits are set. No global GPU or macOS
memory settings are changed. Stop terminates the launcher's own engine and
relay and releases the cache.

## Runtime and protocol

The adapter discovers the already installed MLX 0.32.0 and mlx-lm 0.31.3
libraries from LM Studio's local runtime. It registers the pinned Kolibri class
inside the child process; app-managed libraries and checkpoint bytes remain
unchanged. Source identities and model file identities are rechecked at the
launch boundary. Scanning reads metadata and tensor headers without loading
the weights or accessing the network.

The native server binds to 127.0.0.1 and requires its own random key from an
owner-only configuration file. The existing launcher relay enforces the
separate Chat or Pi surface key. The server locks the model, KV precision,
prefill settings, normal-turn reasoning, response ceiling and
prompt-plus-response context. It permits Pi's bounded summaries to disable
reasoning, accepts native function tools and text tool results, rejects images,
and uses offline tokenization. Planning never starts inference.

Pinned upstream sources and local adaptations are recorded in
[`runtime_patches/kolibri/provenance.json`](../runtime_patches/kolibri/provenance.json):

- [Kolibri Q6 checkpoint](https://huggingface.co/audreyt/Kolibri-1-MLX-6bit)
- [Pinned Kolibri MLX implementation](https://github.com/here-be-dragons-ai/mlx-lm/blob/5bc45adb8733f9af29c1c03e9ea947d155328b75/mlx_lm/models/kolibri1.py)
- [Pinned streamlx source](https://github.com/srcterm/streamlx/tree/146507b59293058b3a1cecc43f47947b25012297)

This is a separate Kolibri SSD route; it does not change Slotstream's
Qwen-specific engine or reuse its speed evidence.

## Extended-route verification on 5 October 2026

The real Q6 checkpoint passed three streamed Chat turns with **256K configured
context, 64K maximum response, Q8 KV, a 64-token prefill chunk and 4 GiB prompt
retention**. It recalled a reference word and returned the correct consecutive
arithmetic results. The prompts contained 758, 795 and 832 tokens; follow-up
turns reused **576 and 640 cached tokens**. The server confirmed all 10 Q8
full-attention layers and 40 full-precision sliding layers. The temporary
session stopped successfully and released its memory. This verifies the
configured route and hybrid prefix reuse; **a full 256K prompt was not tested**.

Native MLX checks exercise Q8, Q6 and Q4 on a small model across prefill,
decode, 513-token rotation and cache copying, including corrected Q6 buffer
packing and absolute snapshot keys after prefix reuse. All 23 Kolibri unit
checks and 69 JavaScript test files pass. The broader launcher checks retain
the same two previously recorded optimizer failures. Public evidence is in
[`long_context_validation.json`](../runtime_patches/kolibri/long_context_validation.json).

## Initial-route verification on 4 October 2026

The normal launcher-owned Chat route passed a real streamed arithmetic check
with the 8K/1K/reasoning-off contract and automatic 40 GB ceiling. The final
allocation kept 189 expert slots per layer: a 28.12 GiB expert cache and
32.37 GB of resident weight capacity. Native peak MLX memory was 33.03 GB.
The raw native endpoint rejected an unauthenticated request, and Stop returned
the launcher to idle and closed the engine listener. This short reply verifies
operation; it does not benchmark speed or exercise the full 8K context.

All 16 new memory/route checks pass. The full Python suite ran 907 checks:
831 passed, 74 skipped, and two existing optimizer/shootout failures reproduced
against the source captured before this integration. All 68 JavaScript tests
pass after updating the engine-list expectation. The public numeric evidence
is in [`validation.json`](../runtime_patches/kolibri/validation.json).
