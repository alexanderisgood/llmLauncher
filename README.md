# LLM Launcher

[![Tests](https://github.com/alexanderisgood/llmLauncher/actions/workflows/tests.yml/badge.svg)](https://github.com/alexanderisgood/llmLauncher/actions/workflows/tests.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](CHANGELOG.md)

LLM Launcher is a macOS hub for selecting a local model, choosing the best compatible inference engine, and opening that route in **Pi**, **OpenCode**, **Codex**, or a built-in streaming **Chat**.

Its primary in-memory engines are **oMLX**, **LM Studio**, and **MTPLX**. Oversized Mixture-of-Experts models can also use optional **SwiftLM** or **Mference** SSD-streaming routes when the exact runtime, model family, and source identity pass the launcher's compatibility checks. Instead of treating every OpenAI-compatible server as identical, it keeps model format, reasoning support, context, sampling, accelerator settings, agent protocol, and locally measured performance in one visible contract.

> **Alpha software:** this is an early public release for macOS and Apple Silicon enthusiasts. It is not signed or notarized yet, runtime interfaces may change, and you should review a route before trusting it with important work.

## What it does

- Finds compatible local models across supported model folders.
- Launches one model into Pi, OpenCode, Codex, or local Chat without rewriting those tools' permanent configuration.
- Preserves context, output, reasoning, sampling, and KV-cache choices across the complete route.
- Measures like-for-like engine and accelerator performance before claiming a fastest option.
- Exposes a separate **Huge models on SSD** lane for supported MoEs, with source-bound SwiftLM/Mference calibration rather than comparing unrelated repacks by filename.
- Keeps cooling user-owned: optimisation and Calibration use automatic cooling by default and never select maximum fans without an explicit choice.
- Supports streaming thinking, message queues, history, branching, TPS, warm-route reuse, and resumable local Chat.
- Gives Pi a stable in-launcher transcript with restored session messages, separate thinking/response/tool lanes, queued follow-ups, and abort/clear-queue controls; external Terminal remains available for Pi's full TUI.
- Includes a polished light **Frost** appearance plus Focused progressive disclosure for a calmer Mac-style interface; the Hub Console remains a black terminal workspace in every appearance.
- Keeps generated routes on authenticated loopback addresses and stops only launcher-owned processes.
- Provides profiles, Session Sets, model acquisition, runtime inspection, route checks, and capacity controls.

The experimental FreeToken integration remains implemented and tested but is hidden behind an off-by-default UI feature flag while the native route matures.

## Requirements

- macOS; the primary target is Apple Silicon.
- Python 3.10 or newer.
- At least one primary engine installed: [oMLX](https://github.com/jundot/omlx), [LM Studio](https://lmstudio.ai/), or [MTPLX](https://github.com/youssofal/MTPLX).
- Optional: [SwiftLM](https://github.com/SharpAI/SwiftLM) or [Mference](https://github.com/NeelM0906/Mference) for a compatible oversized-MoE SSD-streaming route. Mference requires its verified model-specific `.gturbo` repack.
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
2. Select oMLX, LM Studio, or MTPLX. For a supported MoE whose weights do not fit safely in memory, open **Huge models on SSD** and select SwiftLM or Mference.
3. Select Pi, OpenCode, Codex, or Chat.
4. Review context, maximum response, reasoning, and engine controls.
5. Choose **Launch** or **Start chat**.

Nothing is uploaded by the launcher. Model downloads happen only after a separate pinned-revision review and explicit approval.

## Oversized MoEs on SSD

The SSD lane is deliberately separate from the three normal runtime cards. SwiftLM streams experts from a supported MLX checkpoint, including its released Qwen3-Next family; Mference runs a model-specific `.gturbo` repack only after its bounded manifest and install receipt agree with Mference's pinned architecture and complete payload layout. The launcher preserves the model's native expert top-k, disables speculative decoding on this I/O-bound path, and exposes only controls that each runtime can enforce.

When both routes are installed, Calibration can compare them only after their artifacts prove the same immutable source revision. Mference exposes fixed context windows up to 128,000 tokens, so an SSD comparison visibly locks and applies the largest common supported window rather than silently measuring a different contract. It measures first-turn and warm-prefix generation TPS, time to first output, memory pressure, and thermal state in fresh processes. It observes the natural macOS file cache instead of claiming a privileged cold-cache purge.

[Qwen3.8-Flash-Next](https://github.com/QwenLM/Qwen3.8-Flash-Next) is detected as an SSD-streaming candidate, but currently remains blocked because neither upstream runtime lists that new architecture as supported. Detection is not treated as proof that the weights can be executed.

## Known alpha limitations

- There is no packaged `.app`, code signing, notarization, or automatic launcher updater yet.
- The interface and saved-data formats may evolve before a stable release.
- Runtime support is deliberately strict; a nominally OpenAI-compatible route can remain unavailable if its model, reasoning, tools, or Responses contract cannot be preserved.
- SSD streaming is model-family specific. A large MoE remains unavailable until its exact SwiftLM or Mference architecture path is verified; Qwen3.8-Flash-Next is currently detected but intentionally not launchable through either route.
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
