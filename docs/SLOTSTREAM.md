# Slotstream Qwen3.8 Flash-Next

The launcher supports the audited **Slotstream 0.2.17 macOS 26 arm64 release** and its pinned `qwen3.8-flash-next:4bit` model. It keeps all 512 experts and native top-10 routing, streams experts and n-grams from SSD, and uses the separately pinned MTP head. The model needs **105,264,463,248 bytes** including MTP and is separate from Whallm's model format.

Choose **Slotstream** in the engine menu, then its Qwen model. For a 48 GiB M5 Pro, start with **65,536 context**, **8,192 maximum response**, **MTP depth 2**, **automatic memory sizing with a 30 GB ceiling**, and **medium reasoning**. These are starting settings, not a claim of measured maximum speed. Run the launcher's AR/MTP benchmark on the intended context and workload before promoting a speed result.

The initial integration supports Pi, OpenCode and built-in Chat through the authenticated session relay. Codex is unavailable because this runtime does not implement Responses. Text-only operation and native sampling defaults are intentional for this initial route; images and custom sampling are not advertised. Context choices are 16K, 32K, 64K, 128K and 256K. Each must pass native memory planning, and long first prompts can take minutes. A selectable window is not proof of locally measured capacity or throughput.

## Installation and discovery

The runtime is discovered at `~/.slotstream/bin/slotstream`, with `mlx.metallib` beside its resolved executable. The launcher checks both files against the audited macOS 26 release hashes. Updated or alternate builds require a new adapter audit; it does not silently accept an arbitrary executable with the same version string.

- [Pinned release](https://github.com/carloslfu/slotstream/releases/tag/v0.2.17)
- Archive: `slotstream-arm64.tar.gz`
- Archive SHA-256: `66eb2ae95b325e75280d675fcf2afb3d61ef27db5500dea462faadef457b6042`
- [Pinned upstream model manifest](https://github.com/carloslfu/slotstream/blob/d25dffff1f3f56e70ddb9f11b82e7dc1b843f041/Sources/Slotstream/PinnedModel.swift)

After installing that release, download or resume the separate model:

```sh
"$HOME/.slotstream/bin/slotstream" pull qwen3.8-flash-next:4bit \
  --dir "$HOME/.slotstream/models/qwen38-flash-next-mlx-4bit"
```

The pull verifies each file and resumes interrupted downloads. The launcher displays completed-file counts and refreshes the selected Slotstream route during setup. It never downloads weights during a scan. A missing MTP head permits AR only; explicitly selecting MTP fails if the head is unavailable.

## Launch contract

The launcher owns a cancellable verification process. It runs `pull --verify` against the explicit model directory, rechecks all file identities, then replaces that process with `slotstream serve`. This matters because upstream's automatic pinned-file check is skipped for an explicit `--model` path. The native server remains in the launcher's owned process group; Stop terminates that group and its private session relay.

The selected MTP mode is resolved to `on` or `off`, never an upstream `auto` that can silently disable MTP under pressure. Draft depth is explicit. Shell-level `SLOTSTREAM_*`, `MLX_*`, and `DYLD_*` overrides are removed before native planning and loading. Prefix caching stays enabled and native expert routing is fixed.

Authentication covers the launcher relay, not Slotstream's separate native loopback listener. The pinned 0.2.17 binary ignores bearer tokens on that listener, so another local process can bypass relay policy by calling it directly. Closing this gap requires native token enforcement or a permission-protected native socket, followed by a new runtime audit and hash pin. A second proxy cannot secure an already reachable native listener. This integration must not be described as authenticating every local endpoint.

The explicit total-process memory budget includes expert cache, context, retained prefix and MTP. Admission protects an additional macOS reserve, `doctor --json` must honour the selected context/MTP/budget before launch, and an owned-process guard stops the model if memory exceeds the budget by more than 2 GiB. No global memory or Metal settings are changed.

Speed evidence is bound to exact model files, runtime files, hardware, context, output, reasoning, sampling, memory budget and MTP depth. This quantisation has its own comparison identity; it cannot inherit a Whallm result or become a cross-format winner based on a matching model name.

## Local validation

On 14 September 2026, the 48 GiB M5 Pro passed a live session check with 65,536 configured context, MTP depth 2, medium reasoning and a 30 GB process budget. The native catalog reported the exact window, the authenticated relay rejected an unauthenticated request, and streamed text plus a function-call/result round trip completed successfully. Stop unloaded the engine and relay. All 25 model files passed pinned SHA-256 verification before loading.

The 34 GB budget was refused by the native planner with the applications then open; 30 GB passed. These short prompts do not qualify full-window capacity or establish whether MTP is faster than AR on a particular workload.

Automatic sizing uses Slotstream’s native available-memory planner, bounded by the selected process ceiling. It reduces the resident expert cache when other apps hold RAM and preserves the exact context and MTP request. Fixed mode remains available for controlled comparisons. The 32K response cap was a launcher restriction, not an engine limit; responses can use the selected context minus at least 1,024 tokens reserved for instructions and history.

After the automatic-sizing fix, a normal launcher Chat session on the same Mac started with 131,072 context, a 100,000-token response limit, medium reasoning and MTP depth 2. Startup verified all 25 files, planned 25.6 GB total with a 6.5 GB expert cache, and enabled native elastic cache resizing. A browser-driven short request completed with `READY` (19 prompt and 42 output tokens reported). This verifies startup and a real reply with those settings, not generation of 100,000 tokens or a full-window performance benchmark.

## Q8 KV cache

The local `0.2.20-q8.1` fork is available through **KV cache precision → Q8**.
It rebases the Q8 cache patch onto upstream v0.2.20 (`6e25b00`). With the Q8
runtime the launcher now also enables the engine's validated read-path
switches (`SLOTSTREAM_OPT_READ_SCOPE=8192`, layer workspace, compact state and
MTP rows, indexer and PLE tiles, resident overlap) and defaults the process
ceiling to 36 GB so the native auto planner may keep a larger expert pool.
The set also raises the MoE workspace tile to `SLOTSTREAM_OPT_WORKSPACE_TILE=4096`
(the engine default of 256 serialises 32 tiles per layer per read scope at a
4,096-token prefill pass, each ending in its own `eval`). A paired
same-session A/B on 19 September 2026 measured prefill **133.7 → 167.4 tok/s**
and a repeat with the full 256-token probe **168.9 tok/s** at an unchanged
11.1-11.3 decode, with the greedy continuation byte-identical to the recorded
reference and drafting unchanged (130 of 250 drafts accepted).
A paired 112,881-token measurement on 17-18 September 2026 toggled the whole
set at once: prefill 90.4 → 124.7 tok/s and decode 8.62 → 10.74 tok/s, with
byte-identical deterministic probes and the corrected tap sidecar present in
both arms. The individual contributions within the set are not separated by
that pair.
It uses the same full-expert Q4 weights, with Q8 main and MTP attention caches.
The original BF16 KV runtime remains selectable as **Full precision**.
Q8 is selected explicitly and preserved by optimisation; changing it applies
on the next launch. The launcher verifies separate runtime hashes and requires
both the planner and live catalog to confirm eight-bit KV with group size 64.

Packed KV storage is 46.875% smaller, including scales and biases. The planner
charges the smaller persistent cache, all six replacement buffers, and the
prefill reconstruction workspace. It can spend the remaining budget on experts.
At a 24 GB budget and 128K context in the local test, it allocated 3,114 expert
slots (8.6 GB) versus 1,778 (4.9 GB) with BF16 KV. Both answered the same
6,541-token retrieval task correctly with MTP enabled. This is a functional
comparison, not sufficient evidence of a repeatable whole-model speedup.

Validation includes 54 native Swift/Metal checks, 3,827 full-model prefix-fork
assertions, and the native MTP determinism/rollback/reuse check. The installed
binary's MTP test peaked at 9.23 GB inside a 12 GB budget. Tensor tests cover
128K cache length; a full 128K model prompt and 256K Q8 operation are not
qualified by those tests. The custom split-key kernel benefits sparse masks;
its dense attention timing is not consistently faster than MLX quantized
matmul. Lower cache precision can change generated output.

Source patch, rebuild instructions, pinned hashes and raw evidence are in
[`runtime-patches/slotstream-q8`](../runtime-patches/slotstream-q8/README.md).

The Q8 route also passed the launcher-owned startup check at 128K context,
MTP depth 2 and a 30 GB ceiling: all pinned files were verified before loading,
the live catalog acknowledged Q8, an unauthenticated relay request was refused,
and streamed text plus a function-call/result round trip completed. The
installed Pi provider integration test passed separately with synthetic replies.

### Q8 performance reporting and memory ceilings

The local Q8 runtime reports newly processed prompt tokens and their native
prefill time separately from cached tokens. With streaming usage enabled, that
measurement reaches Hub as soon as prefill finishes, before generated output.
The final response supplies native decode timing, draft acceptance, allocated
expert-cache bytes and expert-cache hit rate. These are numeric-only metadata;
no prompt text or token IDs are retained for telemetry. The original full-
precision binary does not expose this additional OpenAI timing metadata.

Automatic memory is a ceiling, not a promise to fill that amount of RAM. The
native planner also applies current reclaimable memory, a safety allowance and
the Metal working-set limit. Within the resulting target it reserves resident
weights, the expert pool, active context growth, retained conversations, MTP
and temporary prefill allocations. Activity Monitor shows current process
memory, which can be substantially lower than these future capacity reserves.
The expert-cache size shown in request details is an allocation, not the total
model weight size or proof that every allocated slot contains a useful expert.
