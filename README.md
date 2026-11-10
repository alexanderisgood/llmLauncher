# LLM Launcher

[![Tests](https://github.com/alexanderisgood/llmLauncher/actions/workflows/tests.yml/badge.svg)](https://github.com/alexanderisgood/llmLauncher/actions/workflows/tests.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](CHANGELOG.md)

LLM Launcher is a macOS hub for selecting a local model, choosing the best compatible inference engine, and opening that route in **Pi**, **oh-my-pi**, **OpenCode**, **Codex**, or a built-in streaming **Chat**.

**New in 1.67.0-alpha.1:** a compact Pi Hub, editable queues and steering,
live tool previews, clearer prompt/decode/context statistics, and version-gated
DFlash Q4/Q6/Q8 KV support with memory-pressure recovery. See the
[release notes](CHANGELOG.md) for scope and remaining limitations.

The current refactor adds a searchable launch screen, clearer readiness and
saved speed results, an oh-my-pi adapter, and **Quit** in the top bar
and Console menu. Streaming, resource monitoring, runtime probes and screen
updates now avoid repeated work. CPU measurements are recorded separately from
model generation TPS; see [performance boundaries](ARCHITECTURE.md#performance-boundaries).

Its primary in-memory engines are **oMLX**, **LM Studio**, and **MTPLX**. The source also contains a developer-machine-only experimental **Mirai/Uzu** adapter for the exact [`trymirai/Qwen3.6-27B-M`](https://huggingface.co/trymirai/Qwen3.6-27B-M) target plus its bundled DFlash draft and Weaver proposal tree; this is Qwen3.6, not Qwen3.8 Flash. Its exact hardened executable is installed only on the qualification Mac and is not distributed by this repository, so a fresh public clone cannot enable that route. Oversized Mixture-of-Experts models can also use source-bound **SwiftLM** or **Mference** routes, Whallm's full-expert runtime, or one receipt-bound **llama.cpp** SSD-PLE route for the exact pinned AtomicChat Qwen3.8 Flash-Next AD-3.84 GGUF. The Uzu route is resident and its speculative acceleration is fixed and runtime-managed, while the llama.cpp route maps only its isolated PLE table from SSD; neither is a generic out-of-core fallback. Instead of treating every OpenAI-compatible server as identical, the launcher keeps model format, reasoning support, context, sampling, accelerator settings, agent protocol, and locally measured performance in one visible contract.

> **Alpha software:** this is an early public release for macOS and Apple Silicon enthusiasts. It is not signed or notarized yet, runtime interfaces may change, and you should review a route before trusting it with important work.

## Kolibri Q6 on SSD

**Kolibri SSD** runs the complete Q6 MLX checkpoint in built-in Chat, Pi and
oh-my-pi, including function tools and reasoning history. Automatic
memory sizing keeps the largest expert cache that fits current headroom, the
selected process ceiling and Metal, with separate context and macOS reserves.
Context now reaches the checkpoint's native 256K, with Q8/Q6/Q4 KV cache,
configurable prefill chunks and retained prompt-cache budgets.
See [Kolibri setup and memory sizing](docs/KOLIBRI.md).

## Slotstream Qwen3.8 Flash-Next

The pinned Slotstream 0.2.17 adapter adds full-expert SSD streaming, native MTP,
longer context choices and checked process-memory budgets. See the
[Slotstream setup and execution contract](docs/SLOTSTREAM.md).

## Launching a model

**Rapid MLX** reuses installed local MLX checkpoints in Chat and coding agents,
including the Flint INT4 files already installed for Rec. Its isolated runtime
starts only when you launch a session. See [Rapid MLX setup and controls](docs/RAPID_MLX.md).

**Recursive Flint INT4** runs through the official **Rec** engine in Chat, Pi,
oh-my-pi or OpenCode, with native reasoning and function tools. Select **Rec**
after installing its runtime and weights. See [Flint setup and controls](docs/FLINT.md).

Choose an installed engine and model, select Chat or a coding agent, and press
**Launch**. Model, memory, and client-connection checks run automatically.
A required capacity qualification runs from the same button, shows progress,
and continues into the selected session only after a matching successful
result is saved and current capacity passes again. Uzu/Pi uses the verified
Chat capacity contract; a missing 128K prerequisite is tested at 64K first.
First-use capacity checks can take several minutes and can be cancelled.
Saved qualifications are reused only while they match the selected settings.
For Uzu session capacity, changing only Max response reuses the saved check
when both ceilings allow the same bounded probe budget and the new ceiling
fits within the unchanged context. The receipt still binds the exact model,
runtime, context, reasoning, sampling, hardware, and memory guards. This proves
context capacity, not performance or completion of a full-length response;
cross-engine calibration continues to require its exact output settings.

**Choose fastest engine**, directly below the model selector, applies a matching
saved cross-engine calibration or opens calibration when comparison is needed.
It compares compatible engines for the same model and selected settings; it
does not substitute a different checkpoint.

**Settings** holds context, response limit, reasoning and the agent window.
**Engine tuning & diagnostics** keeps sampling, runtime controls and optional
performance tools collapsed underneath. Uzu context sizes use a dropdown.
The top bar contains **Sessions**, **Models** and **Advanced**; Advanced holds
saved launches, chat history, calibration, engines and appearance. Optional
diagnostics are not prerequisites for launching. Required memory acknowledgement
appears inline with Launch; failed checks never change the model or settings.

**oh-my-pi** opens in Hub Console with the verified 18.6.3 release, or in
Terminal. Other versions keep the Terminal option until their console protocol
is verified. Its selected model, helper roles, context,
response allowance and reasoning use a private session configuration. Install
`omp` separately; the launcher does not rewrite its permanent settings. The
adapter has passed real native reasoning/tools, history, queued follow-ups,
abort and local-command checks against generated local data. Pi and oh-my-pi
also passed actual Splash and Kolibri tool tasks. Each engine's model and capacity checks still apply;
Uzu and the native FreeToken milestone remain unavailable for oh-my-pi.

**Quit** stops launcher jobs and agents, unloads LM Studio through its local
CLI, stops recognised local engine servers (including independently started
ones), and closes the launcher. The dialog displays any shutdown errors. Process
matching uses exact installed paths and verified process identities. **Stop**
continues to stop the selected launcher session.
Quit also unloads verified user LaunchAgent services so their automatic restart
policy cannot immediately bring a model server back.

The Hub uses one compact bar for model identity, decode speed, prompt speed,
context and activity. **Home** and **Return to Pi** switch views without stopping
the task. Copy, compaction, queue cleanup and session actions live in **•••**;
steering and queueing remain beside the message field while Pi responds.

Kolibri's controlled prefill comparison improved 19–25% with identical output
tokens. Native generation timing now remains separate from buffered network
delivery, prompt processing and total request time in live status and saved
benchmarks. See [Kolibri measurements](docs/KOLIBRI.md#performance-and-agent-verification-on-6-october-2026)
and [Splash timing](docs/SPLASH.md#native-agent-timing-verified-on-6-october-2026).

When Playwright is already installed, Pi also receives a private `browser_check`
tool for short page checks. It owns a headless Chromium session, keeps page state
between calls, and closes on cancellation, timeout or session exit. It does not
attach to the user's browser or install packages. Browser-specific and visual
claims still need the corresponding verification.

## What it does

- Finds compatible local models across supported model folders.
- Recognizes the separate Mirai cache and presents Uzu as a resident runtime with fixed DFlash-plus-Weaver acceleration, without misclassifying its custom artifact as a generic MLX model.
- Launches one model into Pi, oh-my-pi, OpenCode, Codex, or local Chat without rewriting those tools' permanent configuration.
- Preserves context, output, reasoning, sampling, and KV-cache choices across the complete route.
- Separates host compatibility from speed evidence. **Verified on this Mac** means an exact local model/runtime/Mac/request match and is the only tier eligible for automatic fastest-route selection; **Upstream measured** is reference-only, while **Not measured on this Mac** remains untrusted. Host support is reported independently as **Supported**, **Experimental**, or **Unavailable**.
- When Qwen3.8 Flash-Next is selected, Calibration may expose one installed Qwen3.8-27B DFlash 2 route as an explicit different-model alternative. It is offered only when the exact target/draft pair and unchanged visible context, output, reasoning, KV, and Chat contract pass fresh validation; it changes the model, architecture, and intelligence contract and is never selected automatically.
- Discovers LM Studio's separate DFlash, DSpark, and MTP assistant-drafter foundation only from a validated LM Studio 0.4.22+ app bundle, its selected complete llama.cpp 2.29.1+ pack, and LM Studio's current exact GGUF compatibility and vocabulary receipts. Discovery alone does not make that route selectable, benchmarkable, or automatic; those actions remain disabled until the launcher can verify the applied target/draft pair after every fresh load.
- Defaults every automatic engine decision to correctness-verified **generation TPS**, including older profiles and API requests that do not carry a goal; total workload, first response, memory, and thermal rankings remain explicit alternatives.
- For an exact dense Qwen 27B artifact on MTPLX 2.11.1 at 64K or more, Calibration can isolate the normal MTP path from the release's long-context operator recipe. It promotes that recipe only after generated near-64K prompts preserve exact output and beat the default route by at least 3% in both median and worst-case generation TPS under comparable Mac conditions.
- To test only that MTPLX upgrade, select **Turbo**, at least **64K context**, then **Benchmark Lab → Agentic → Current engine only**. It discloses three isolated setups (AR, default MTP, long-context MTP) and 18 generated requests before starting. This does not load other engines or change your cooling setting; a result is a current-engine recommendation, not proof of the fastest engine overall.
- Exposes a separate **Huge models on SSD** lane for supported MoEs, with source-bound SwiftLM/Mference calibration, an isolated Whallm full-expert route, and one exact receipt-bound llama.cpp SSD-PLE route rather than comparing unrelated or pruned checkpoints by filename.
- Treats **Qualified route** as a separate single-route proof: it may enable that exact route, but it is not a cross-engine winner or a claim that the engine is fastest.
- Keeps cooling user-owned: optimisation and Calibration use automatic cooling by default and never select maximum fans without an explicit choice.
- Supports streaming thinking, message queues, history, branching, TPS, warm-route reuse, and resumable local Chat.
- Gives Pi a stable, bounded in-launcher conversation timeline with restored session messages, separate thinking/answer/tool/status cards, queued follow-ups, unread tabs, fixed-position scrolling during generation, abort/clear-queue controls, and answerable extension prompts. Periodic and authoritative-final snapshots make refresh replay independent of expired token chunks, while response-limit continuation cues prevent a long reasoning turn from silently disappearing. Codex Responses routes likewise turn a falsely completed exact-ceiling result into the protocol's continuable incomplete state in both Hub Console and external Terminal. External Terminal remains available for Pi's full TUI.
- Includes a polished light **Frost** appearance plus Focused progressive disclosure for a calmer Mac-style interface; the Hub Console remains a black terminal workspace in every appearance.
- Keeps generated routes on authenticated loopback addresses. Stop cleans up launcher-owned processes; the explicit Quit action also stops recognised local engine services.
- Provides profiles, Session Sets, model acquisition, runtime inspection, route checks, and capacity controls.
- Opens installed LM Studio, MTPLX, and Whallm apps directly from Runtime Manager after revalidating their exact macOS bundles; opening an app remains distinct from loading a model.

Runtime Manager uses a reviewable release snapshot rather than an unchecked “latest” query. The snapshot updated on 7 September 2026 covers [oMLX 0.6.4](https://github.com/jundot/omlx/releases/tag/v0.6.4), [LM Studio 0.4.23 Build 1](https://lmstudio.ai/changelog/lmstudio/lmstudio-v0.4.23), [MTPLX 2.11.2](https://github.com/youssofal/MTPLX/releases/tag/v2.11.2) at official release commit [`21be78b3f51820eecef020e5e4855c0715eaf9a5`](https://github.com/youssofal/MTPLX/commit/21be78b3f51820eecef020e5e4855c0715eaf9a5), optional [SwiftLM b709](https://github.com/SharpAI/SwiftLM/releases/tag/b709), and experimental [Whallm 1.1.4](https://github.com/yanun0323/Whallm/releases/tag/v1.1.4). MTPLX remains vendor-owned: the launcher keeps swap overcommit off and never enables its context-specific operator recipe globally. An exact dense-27B, MTPLX 2.11.1, verified-MTP, Turbo, 64K-or-larger route can instead run a user-triggered isolated comparison; only its matching immutable local result can be applied or reused. The release's dense-27B, Flash-Next, and agent-session results are upstream M5 Max measurements, not evidence for this Mac. The exact AtomicChat SSD-PLE route independently pins launcher-managed llama.cpp b10740. The experimental Uzu route pins launcher build `0.5.23-llm-launcher.prefill-experiment.1` to upstream commit `115609b6ef7ce5a94fc761bf395780f032b09f9b`, the included three-patch chain `680e2d72f0ba7a63fc822543022c6a1fc9b2895276fb7252a8049219de58692f`, and binary `efe7fc98a8e063c30103a27badb4f308b8cb782708134a7805178f9e16caa0ce`. This local build is ad-hoc signed only—not Developer ID signed or notarized—and is admitted by exact source, patch, binary, model, sandbox, and qualification evidence rather than a signing claim.

The oMLX Preview track was separately audited on 15 September 2026 and now offers **0.7.0.dev2** with Flash-Next expert and PLE SSD offload, adjustable expert RAM share and a separate RAM ceiling. See [installation and model-fit details](docs/OMLX_PREVIEW.md).

The experimental FreeToken integration remains implemented and tested but is hidden behind an off-by-default UI feature flag while the native route matures.

## Requirements

- macOS; the primary target is Apple Silicon.
- Python 3.10 or newer.
- At least one primary engine installed: [oMLX](https://github.com/jundot/omlx), [LM Studio](https://lmstudio.ai/), or [MTPLX](https://github.com/youssofal/MTPLX).
- Developer qualification host only: the exact launcher-hardened Uzu `0.5.23-llm-launcher.prefill-experiment.1` build with the separately downloaded [`trymirai/Qwen3.6-27B-M`](https://huggingface.co/trymirai/Qwen3.6-27B-M) package. The executable is not bundled or offered as a public download, the local build is not byte-reproducible, and stock Uzu builds are not substituted by version number alone.
- Optional: [SwiftLM](https://github.com/SharpAI/SwiftLM) or [Mference](https://github.com/NeelM0906/Mference) for compatible oversized-MoE artifacts. Mference requires its verified model-specific `.gturbo` repack.
- Optional and experimental: [Whallm](https://github.com/yanun0323/Whallm) for its own pinned full-512-expert Qwen3.8 Flash-Next download. Whallm publishes a 64 GiB unified-memory floor; its current M5 Pro measurements reach 22.75 GiB of MLX active memory through 16K input.
- Optional and experimental: the exact pinned 28-shard AtomicChat Qwen3.8 Flash-Next AD-3.84 GGUF and launcher-managed llama.cpp b10740 for the receipt-bound 8K SSD-PLE route.
- Pi, oh-my-pi, OpenCode, or Codex only if you want to launch that agent. Built-in Chat needs no separate agent.
- Local model weights compatible with the selected engine. Models and commercial runtimes are not bundled.

## Quick start

```bash
git clone https://github.com/alexanderisgood/llmLauncher.git
cd llmLauncher
./Start\ LLM\ Launcher.command
```

The launcher selects an available Python 3.10+ interpreter, starts an owner-only controller on `127.0.0.1`, and opens the interface. Opening the command again safely reuses the existing controller.

On first use:

1. Choose **Models** to inspect detected artifacts and engine compatibility.
2. Select oMLX, LM Studio, or MTPLX. The developer-only Mirai/Uzu card is a separate resident route and remains unavailable in a public clone; on the qualification host it also stays unavailable until its displayed safety gates pass. For a supported MoE whose weights do not fit safely in memory, open **Huge models on SSD** and select SwiftLM, Mference, or a live Whallm Qwen route. The exact AtomicChat llama.cpp option becomes available for ordinary launch only after current-process model verification and its local route qualification succeed.
3. Select Pi, oh-my-pi, OpenCode, Codex, or Chat.
4. Review context, maximum response, reasoning, and engine controls.
5. Choose **Launch** or **Start chat**.

Nothing is uploaded by the launcher. Model downloads happen only after a separate pinned-revision review and explicit approval.

## Resident Mirai/Uzu route

Uzu qualification permits up to 8,192 output tokens per measured response, capped by the selected response limit and the remaining context. It preserves model-default reasoning without a forced reasoning/answer split, a prompt-framing margin, and a reserve for the final follow-up. Each request's allowance and the measured minimum/maximum are saved and verified separately from the configured launch ceiling. Corpus sizing is checked against the pinned tokenizer, while the runtime's authoritative usage still proves the actual context exercised. The shorter 512-token SSD-PLE qualification remains unchanged.

Uzu's four measured turns extend one real conversation. Exact generated reasoning and answers are retained only in memory for the next request, then discarded; saved results contain numeric measurements and output hashes, not generated text. Added synthetic tool padding adapts to prior authoritative token usage, preserving the context reserve. The conversation policy is part of the receipt, so older canned-reply tests cannot authorize this route. Cache reuse is reported only from runtime usage, not inferred from a shared prompt or a faster response.

The developer-machine-only experimental Uzu adapter is deliberately narrow. Its exact hardened executable is not bundled or published, so the route is unavailable from a fresh public clone. On the qualification host it recognizes only the exact [`trymirai/Qwen3.6-27B-M`](https://huggingface.co/trymirai/Qwen3.6-27B-M) package: a Mirai-M 4-bit Qwen3.6 27B target with its packaged DFlash drafter and Weaver proposal-tree data. It is not Qwen3.8 Flash, is not part of the SSD-streaming lane, and is not compared as plain autoregressive inference. DFlash plus Weaver is one fixed, runtime-managed acceleration route; the launcher reports its measured generation TPS but does not expose invented draft-depth or verifier controls.

The model weights are not included in this repository. They must be downloaded separately into Mirai's own cache, and discovery admits only a complete registry-bound package whose files also match the launcher's pinned SHA-256 values; a downloader receipt alone is not launch authority. The hardened server binds to loopback inside the launcher's outbound-network-denied sandbox and requires a random API key from an owner-only, one-use file. It consumes and removes that file before engine construction or model loading, so the raw listener and launcher relay share the same authentication boundary without putting the secret in process arguments.

The architecture advertises 262K context, while [Qwen's own model guidance](https://huggingface.co/Qwen/Qwen3.6-27B) recommends at least 128K when reducing context for constrained hardware. On this 48 GB Mac the launcher therefore exposes exact, separately proven 16K, 32K, 64K, and 128K tiers, but not an unproven native-262K option. The interface reports the 128K guarded cap separately from native capacity, and a receipt for one tier can never authorize another. Uzu's Metal attention state is sparse: the 262K virtual capacity is not all resident at startup, while the pinned geometry puts target-plus-draft BF16 KV at about 1.1 GiB at 16K, 2.2 GiB at 32K, 4.3 GiB at 64K, 8.6 GiB at 128K, and roughly 17 GiB at the native limit, plus weights and transient state. Long-context admission also reserves another 1 GiB at 64K or 2 GiB at 128K for prefill and requires a 2 GiB margin below the live process ceiling. The current runtime has no supported Q8/Q4 KV control; its 4-bit label describes weights, not the cache. The hardened build applies context and output ceilings inside Uzu itself. Immediately before generation it reserves the configured output against the live token sequence—including an actually reused cached prefix—so a relay estimate or prefix-cache re-tokenisation mismatch cannot bypass the native limit. A 38 GiB process-group ceiling and a separate whole-Mac headroom monitor remain independent stops if either the route or another application threatens the protected macOS reserve.

Capacity qualification uses built-in Chat with **Model default** reasoning only. Before ordinary inference can start, the exact context tier must complete a version-5 generated-data qualification that binds the hardened runtime identity and safety contract and verifies separate reasoning and answer output, authoritative usage, at least 15 generation tok/s on every measured turn, arithmetic correctness, continuous process and system-memory telemetry, and a clean unload. At 64K and 128K, the last two probes must authoritatively exercise at least 90% of the selected window. A 128K qualification is staged behind a fresh matching 64K receipt whose measured peak plus projected context growth and the protected 2 GiB margin still fit strictly below the 38 GiB live ceiling. Older version-1 through version-4 Uzu receipts are intentionally rejected. Uzu streams reasoning separately from answer text, but named low/high effort levels all collapse to the same model-default mode. Although the server protocol can encode **Thinking off**, the launcher does not advertise that path until its no-reasoning behavior has a separate honest qualification contract; an unavailable setting must not send users back through an impossible calibration loop. Pi 0.84.2 is enabled on the exact locally verified Uzu/model build: normal primary Hub startup, a streamed tool call, a retained follow-up, separate thinking, and clean shutdown passed at 64K. Pi reuses matching Chat capacity evidence, not its speed ranking; Pi agent-performance calibration and long coding-task verification remain unfinished. OpenCode remains gated pending its own integration verification; Codex remains unavailable because this server does not expose the Responses API. Uzu does not report native timing, so displayed TPS must be derived from its authoritative final token usage and the launcher's relay timing.

Mirai's published [approximately 105 output tok/s result](https://x.com/dimashvets/status/2095533685147582923) used an M5 Max with 128 GB unified memory. It is useful upstream context, not evidence for this Mac and never makes the route an automatic fastest choice; only a completed matching local qualification can do that.

## Oversized MoEs on SSD

The SSD lane is deliberately separate from the three normal runtime cards. SwiftLM streams experts from a supported MLX checkpoint, including its released Qwen3-Next family; Mference runs a model-specific `.gturbo` repack only after its bounded manifest and install receipt agree with Mference's pinned architecture and complete payload layout. The launcher preserves the model's native expert top-k, disables speculative decoding on this I/O-bound path, and exposes only controls that each runtime can enforce.

When both routes are installed, Calibration can compare them only after their artifacts prove the same immutable source revision. Mference exposes fixed context windows up to 128,000 tokens, so an SSD comparison visibly locks and applies the largest common supported window rather than silently measuring a different contract. It measures first-turn and warm-prefix generation TPS, time to first output, memory pressure, and thermal state in fresh processes. It observes the natural macOS file cache instead of claiming a privileged cold-cache purge.

A separate experimental llama.cpp route admits only the pinned 28-shard AtomicChat AD-3.84 split and the launcher-managed llama.cpp b10740 runtime. It is fixed to 8K context, one request lane, full-precision f16 KV, runtime-controlled reasoning, Jinja tools, and no speculative decoding. A prior owner-only identity snapshot can make catalog discovery responsive, but every controller process must still complete full SHA-256 verification before qualification or launch; the snapshot never grants authority.

Its single-route qualification requires the Metal wired-memory limit to equal exactly 44 GiB (`45056` MiB), at least 4 GiB of macOS headroom, and no loaded or loading Whallm model. The launcher changes none of those conditions. Four generated agentic requests are capped at 512 output tokens and must each return at least 128 tokens at 15 generation tok/s or better, with separate reasoning and a final answer; correctness, one exact Jinja tool call, owned-process-group memory, continuous limit and Whallm isolation, and clean unload are also checked. Ordinary qualified launches then require current headroom to cover that measured process-group peak plus the protected 4 GiB macOS reserve, and they continue checking Whallm for the lifetime of the route. Longer configured responses remain explicitly unmeasured. A saved receipt is reusable only for the matching model, runtime, and settings contract across Pi, OpenCode, and Chat; Codex is unavailable on this Chat-Completions-only route. This qualification proves only the exact route, not a fastest cross-engine result.

[Qwen3.8-Flash-Next](https://github.com/QwenLM/Qwen3.8-Flash-Next) now has several materially different routes rather than one interchangeable artifact. [Whallm](https://github.com/yanun0323/Whallm/blob/master/docs/QWEN.md) installs its own roughly 125.3 GB converted package with MXFP4 routed experts and FP8 N-gram storage, preserves all 512 experts, and streams them from SSD; its current published [M5 Pro benchmark](https://github.com/yanun0323/Whallm/blob/master/BENCHMARK.md) reports 9.7–10.4 generation tok/s and 20.92–22.75 GiB of peak MLX active memory from 1K through 16K input. That metric is not process RSS or a minimum-memory claim, and the project still lists 64 GiB unified memory as its support floor, so 48 GiB remains outside its published support floor. The launcher can now discover the exact installed signed Whallm 1.1.4 model and start its own bounded 16K process, while retaining support for an existing external server. On this 48 GiB M5 Pro, short thinking/cache/tool checks passed with 4,096 expert slots and a 23.89 GiB peak process footprint; see the [device measurements and limits](docs/FLASH_DEVICE_TUNING.md). Whallm 1.1.4 also ships a default-off MTP prototype, but its published formal gates did not accept that path for total-time and tail-latency performance; the launcher therefore does not label or auto-select Whallm MTP without a future exact local qualification.

The alternative [REAP-288 oMLX checkpoint](https://huggingface.co/sh0wie/Qwen3.8-Flash-Next-REAP-288-MLX-4bit) publisher reports about 39 GB resident memory with its 51B N-gram/PLE table streamed by oMLX 0.6.4, but it retains 288 of 512 experts. Its card reports 91.5% versus 93.9% on one 164-problem HumanEval run and warns that other domains may degrade more and vision is untested. The launcher requires the new `qwen4_exp` architecture, verifies the indexed PLE layout, and explicitly pins read-only PLE `mmap`; core QSA/GDN layers and pruned experts remain resident, so this is selective SSD row access rather than macOS swap. It is a different model artifact and is never calibrated as equivalent to Whallm's full-expert checkpoint. No public exact 48 GB M4 Max benchmark yet proves the 15 tok/s target, and the tweet-demonstrated pMLX path remains unintegrated because its serving code is not public. mlx-vlm 0.7.0rc0 is tracked only as an experimental future comparison engine until it passes the same local qualification.

On this 48 GiB qualification host, an actual 8,224-token oMLX Flash-Next prefill reached 41.25 GiB resident and requested a 0.57 GiB minimum transient allocation. That exceeds oMLX's 95% safety cap under a 44 GiB Metal limit (41.8 GiB), so the launcher now reserves 1 GiB of transient workspace, blocks this long-context contract at 44 GiB, and requires a 45 GiB Metal wired-memory limit. High-memory mode also exposes a 45 GiB oMLX process ceiling. This is a fail-closed capacity guard for that separate oMLX long-context contract, not a universal model-memory or speed claim and not the fixed-8K llama.cpp route's 44 GiB qualification.

## Known alpha limitations

- There is no packaged `.app`, code signing, notarization, or automatic launcher updater yet.
- The interface and saved-data formats may evolve before a stable release.
- Runtime support is deliberately strict; a nominally OpenAI-compatible route can remain unavailable if its model, reasoning, tools, or Responses contract cannot be preserved.
- Mirai/Uzu is currently a developer-machine-only route because the exact hardened `0.5.23-llm-launcher.prefill-experiment.1` executable is neither bundled nor published and its local build is not byte-reproducible. On the qualification host, inference still accepts only that exact build, the exact verified model, launcher sandbox, one-use API key boundary, and a matching version-5 qualification receipt. Older version-1 through version-4 receipts are deliberately invalid. Built-in Chat is the first surface; Pi/OpenCode tools and Codex Responses remain unavailable.
- SSD streaming is model-family specific. A large MoE remains unavailable until its exact runtime/artifact contract is verified. Whallm cannot consume an existing MLX folder, while SwiftLM and Mference still do not accept Qwen3.8 Flash-Next. The initial llama.cpp SSD-PLE route is model-, quantisation-, runtime-, and 8K-contract specific; it has no bundled performance claim and remains **Not measured on this Mac** until local qualification succeeds.
- FreeToken is temporarily hidden from the interface. Existing implementation and saved records are retained.
- Hardware recommendations are evidence-bound to the measured Mac, model fingerprint, runtime, and workload; they are not universal benchmark claims.

## Documentation

- [Full user manual](manual.html)
- [Detailed feature and safety reference](docs/REFERENCE.md)
- [Architecture and adapter contract](ARCHITECTURE.md)
- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)
- [Changelog](CHANGELOG.md)

## Development

The core launcher uses the Python standard library. The JavaScript suite uses Node.js 24+ for its native erasable-TypeScript support. Some optional runtime operations use libraries already installed with the selected engine.

```bash
node --check app.js
python3 -m unittest discover -s tests -p 'test_*.py'
for test in tests/test_*.js; do node "$test"; done
```

## Privacy and security

LLM Launcher is local-first, but coding agents can read and change files within the folders you give them. Treat model files, external runtimes, and agent extensions as code-adjacent inputs and install them only from sources you trust. Please report suspected security issues privately using the process in [SECURITY.md](SECURITY.md).

## Licence

Apache-2.0. See [LICENSE](LICENSE). Third-party applications and model weights keep their own licences and are not redistributed by this repository.

Built by Alexander Thomson with OpenAI Codex.
