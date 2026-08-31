# LLM Launcher

[![Tests](https://github.com/alexanderisgood/llmLauncher/actions/workflows/tests.yml/badge.svg)](https://github.com/alexanderisgood/llmLauncher/actions/workflows/tests.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](CHANGELOG.md)

LLM Launcher is a macOS hub for selecting a local model, choosing the best compatible inference engine, and opening that route in **Pi**, **OpenCode**, **Codex**, or a built-in streaming **Chat**.

Its primary in-memory engines are **oMLX**, **LM Studio**, and **MTPLX**. Oversized Mixture-of-Experts models can also use optional **SwiftLM** or **Mference** source-bound SSD routes, or the separate **Whallm** full-expert Qwen3.8 Flash-Next server. Instead of treating every OpenAI-compatible server as identical, it keeps model format, reasoning support, context, sampling, accelerator settings, agent protocol, and locally measured performance in one visible contract.

> **Alpha software:** this is an early public release for macOS and Apple Silicon enthusiasts. It is not signed or notarized yet, runtime interfaces may change, and you should review a route before trusting it with important work.

## What it does

- Finds compatible local models across supported model folders.
- Launches one model into Pi, OpenCode, Codex, or local Chat without rewriting those tools' permanent configuration.
- Preserves context, output, reasoning, sampling, and KV-cache choices across the complete route.
- Measures like-for-like engine and accelerator performance before claiming a fastest option.
- Defaults every automatic engine decision to correctness-verified **generation TPS**, including older profiles and API requests that do not carry a goal; total workload, first response, memory, and thermal rankings remain explicit alternatives.
- Exposes a separate **Huge models on SSD** lane for supported MoEs, with source-bound SwiftLM/Mference calibration and an isolated Whallm full-expert route rather than comparing unrelated or pruned checkpoints by filename.
- Keeps cooling user-owned: optimisation and Calibration use automatic cooling by default and never select maximum fans without an explicit choice.
- Supports streaming thinking, message queues, history, branching, TPS, warm-route reuse, and resumable local Chat.
- Gives Pi a stable in-launcher transcript with restored session messages, separate thinking/response/tool lanes, queued follow-ups, abort/clear-queue controls, and answerable extension prompts; authoritative final-message repair and response-limit continuation cues prevent a long reasoning turn from silently disappearing. Codex Responses routes likewise turn a falsely completed exact-ceiling result into the protocol's continuable incomplete state in both Hub Console and external Terminal. External Terminal remains available for Pi's full TUI.
- Includes a polished light **Frost** appearance plus Focused progressive disclosure for a calmer Mac-style interface; the Hub Console remains a black terminal workspace in every appearance.
- Keeps generated routes on authenticated loopback addresses and stops only launcher-owned processes.
- Provides profiles, Session Sets, model acquisition, runtime inspection, route checks, and capacity controls.

Runtime Manager uses a reviewable release snapshot rather than an unchecked “latest” query. The snapshot audited on 31 August 2026 covers [oMLX 0.6.4](https://github.com/jundot/omlx/releases/tag/v0.6.4), [LM Studio 0.4.23 Build 1](https://lmstudio.ai/changelog/lmstudio/lmstudio-v0.4.23), [MTPLX 2.10.1](https://github.com/youssofal/MTPLX/releases/tag/v2.10.1), optional [SwiftLM b709](https://github.com/SharpAI/SwiftLM/releases/tag/b709), and experimental [Whallm 1.1.2](https://github.com/yanun0323/Whallm/releases/tag/v1.1.2). A newer release is only a candidate: it does not replace a selected runtime or inherit old speed evidence.

The experimental FreeToken integration remains implemented and tested but is hidden behind an off-by-default UI feature flag while the native route matures.

## Requirements

- macOS; the primary target is Apple Silicon.
- Python 3.10 or newer.
- At least one primary engine installed: [oMLX](https://github.com/jundot/omlx), [LM Studio](https://lmstudio.ai/), or [MTPLX](https://github.com/youssofal/MTPLX).
- Optional: [SwiftLM](https://github.com/SharpAI/SwiftLM) or [Mference](https://github.com/NeelM0906/Mference) for compatible oversized-MoE artifacts. Mference requires its verified model-specific `.gturbo` repack.
- Optional and experimental: [Whallm](https://github.com/yanun0323/Whallm) for its own pinned full-512-expert Qwen3.8 Flash-Next download. Whallm publishes a 64 GB unified-memory floor even though its M5 Pro measurements stay below 19 GiB through 16K input.
- Pi, OpenCode, or Codex only if you want to launch that agent. Built-in Chat needs no separate agent.
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
2. Select oMLX, LM Studio, or MTPLX. For a supported MoE whose weights do not fit safely in memory, open **Huge models on SSD** and select SwiftLM, Mference, or a live Whallm Qwen route.
3. Select Pi, OpenCode, Codex, or Chat.
4. Review context, maximum response, reasoning, and engine controls.
5. Choose **Launch** or **Start chat**.

Nothing is uploaded by the launcher. Model downloads happen only after a separate pinned-revision review and explicit approval.

## Oversized MoEs on SSD

The SSD lane is deliberately separate from the three normal runtime cards. SwiftLM streams experts from a supported MLX checkpoint, including its released Qwen3-Next family; Mference runs a model-specific `.gturbo` repack only after its bounded manifest and install receipt agree with Mference's pinned architecture and complete payload layout. The launcher preserves the model's native expert top-k, disables speculative decoding on this I/O-bound path, and exposes only controls that each runtime can enforce.

When both routes are installed, Calibration can compare them only after their artifacts prove the same immutable source revision. Mference exposes fixed context windows up to 128,000 tokens, so an SSD comparison visibly locks and applies the largest common supported window rather than silently measuring a different contract. It measures first-turn and warm-prefix generation TPS, time to first output, memory pressure, and thermal state in fresh processes. It observes the natural macOS file cache instead of claiming a privileged cold-cache purge.

[Qwen3.8-Flash-Next](https://github.com/QwenLM/Qwen3.8-Flash-Next) now has two materially different public 48 GB-class routes. [Whallm](https://github.com/yanun0323/Whallm/blob/master/docs/QWEN.md) installs its own roughly 125 GB MXFP4 checkpoint, preserves all 512 experts, and streams them from SSD; its published [M5 Pro benchmark](https://github.com/yanun0323/Whallm/blob/master/BENCHMARK.md) reports roughly 7.8–9.3 generation tok/s and 15–19 GiB peak memory, while the project still lists 64 GB unified memory as its support floor. The launcher therefore exposes 48 GB as experimental only after Whallm is already serving the exact pinned model ID.

The alternative [REAP-288 oMLX checkpoint](https://huggingface.co/sh0wie/Qwen3.8-Flash-Next-REAP-288-MLX-4bit) reports about 39 GB resident memory with its n-gram table streamed by oMLX 0.6.4, but it retains 288 of 512 experts and reports a small HumanEval loss. It is a different model artifact and is never calibrated as equivalent to Whallm's full-expert checkpoint. The tweet-demonstrated full-expert pMLX path is not integrated because no public, reproducible release is available.

## Known alpha limitations

- There is no packaged `.app`, code signing, notarization, or automatic launcher updater yet.
- The interface and saved-data formats may evolve before a stable release.
- Runtime support is deliberately strict; a nominally OpenAI-compatible route can remain unavailable if its model, reasoning, tools, or Responses contract cannot be preserved.
- SSD streaming is model-family specific. A large MoE remains unavailable until its exact runtime/artifact contract is verified. Whallm cannot consume an existing MLX folder, while SwiftLM and Mference still do not accept Qwen3.8 Flash-Next.
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
