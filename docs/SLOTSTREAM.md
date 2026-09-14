# Slotstream Qwen3.8 Flash-Next

The launcher supports the audited **Slotstream 0.2.17 macOS 26 arm64 release** and its pinned `qwen3.8-flash-next:4bit` model. It keeps all 512 experts and native top-10 routing, streams experts and n-grams from SSD, and uses the separately pinned MTP head. The model needs **105,264,463,248 bytes** including MTP and is separate from Whallm's model format.

Choose **Slotstream** in the engine menu, then its Qwen model. For a 48 GiB M5 Pro, start with **65,536 context**, **8,192 maximum response**, **MTP depth 2**, **30 GB process memory**, and **medium reasoning**. These are starting settings, not a claim of measured maximum speed. Run the launcher's AR/MTP benchmark on the intended context and workload before promoting a speed result.

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

The explicit total-process memory budget includes expert cache, context, retained prefix and MTP. Admission protects an additional macOS reserve, `doctor --json` must honour the selected context/MTP/budget before launch, and an owned-process guard stops the model if memory exceeds the budget by more than 2 GiB. No global memory or Metal settings are changed.

Speed evidence is bound to exact model files, runtime files, hardware, context, output, reasoning, sampling, memory budget and MTP depth. This quantisation has its own comparison identity; it cannot inherit a Whallm result or become a cross-format winner based on a matching model name.

## Local validation

On 14 September 2026, the 48 GiB M5 Pro passed a live session check with 65,536 configured context, MTP depth 2, medium reasoning and a 30 GB process budget. The native catalog reported the exact window, the authenticated relay rejected an unauthenticated request, and streamed text plus a function-call/result round trip completed successfully. Stop unloaded the engine and relay. All 25 model files passed pinned SHA-256 verification before loading.

The 34 GB budget was refused by the native planner with the applications then open; 30 GB passed. These short prompts do not qualify full-window capacity or establish whether MTP is faster than AR on a particular workload.
