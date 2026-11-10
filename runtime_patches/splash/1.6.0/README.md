# Splash 1.6.0 on the 20-core M5 Pro

Select **Launcher Splash 1.6.0 · M5 Pro decode** under Splash in Runtime
Manager, then rescan the models. The launcher verifies the engine and Metal
library hashes before use. This build links to the existing model weights
and runs through Splash's normal chat and tool APIs.

The M16 projection policy selects an existing Metal kernel for eligible
4.5-bit storage layouts on the 20-core M5 Pro. The guarded lookup path
matches a 16-token suffix against the request history and skips the DFlash2
draft when every matching span supplies the same seven continuation tokens.
Splash still verifies them with the target. The launcher enables lookup for
Qwen3.8-27B MLX. Sampling, grammar, thinking budgets, and incompatible
state or batching use DFlash2. When the Neural Engine is available, a request
that may have used its prefill split or restored earlier state also uses
DFlash2.

## Local measurements

On this M5 Pro with the existing 4-bit target and DFlash2 checkpoint, the M16
kernel policy improved decode by **1.8–2.9%** on four matched requests
against Splash 1.6.0. Output tokens and draft acceptance matched on all four.

The combined build completed three independently specified SQL, TOML and
JavaScript edits **5.8% sooner in aggregate** than the installed Splash 1.5.0
build in an A–B–B–A comparison. Decode was **6.1–11.7% faster** and each
complete output matched token for token. Both arms used GPU-only prefill for
that comparison. A non-copy control diverged across releases with zero
lookup hits, so its speed is excluded. Within 1.6.0, enabling lookup
preserved all four token sequences and a separate seeded sampled request.
[Measurements](../../../bench/results/20261108-splash-m5-pro-decode.json)

The installed build also passed a normal launcher smoke test with the
Neural Engine configured. It skipped 38 draft cycles on a 422-token edit
and used the ordinary draft path on a forced tool call and a 1,763-token
prefill.

## Build

The build uses Splash 1.6.0's official Metal libraries and a host executable
compiled with Apple clang 21.0.0 (`clang-2100.4.1.1`), macOS SDK 27.0 and
deployment target 26.4.

| Input | Pin |
| --- | --- |
| [Splash 1.6.0](https://github.com/incoai/splash/releases/tag/1.6.0) | `9124ff2ce1e6d19dab6bb0f2aa94b214b1271ce2` |
| Official macOS archive SHA-256 | `da3aef0a581491b0eb4c1168bda07f520e5ca8368764abff426d95ac1c77e5c4` |
| [Lookup source](https://github.com/incoai/splash/pull/672) | `5f8271f41a5c24f886d9669eaaff5ad77c602d20` |
| Lookup source archive SHA-256 | `4d3a4fb0c975100a581542f711eb6ac644f6588f4d62463de06452bfe2c80334` |
| [M16 kernel policy](https://github.com/incoai/splash/pull/653) | `93f71e74db4c8fd8eb18a6b692bee475cb8f2102` |
| Installed engine SHA-256 | `8abf9ac43ce9f8521317a61d40411f6bf51430e72d806ce369e67e61ee88f844` |
| Installed `splash.metallib` SHA-256 | `703016c3a3e6f07b1772463c75781b0b67f3e92219a8c7f497e07f794f0d6d3c` |
| Installed `host-step.metallib` SHA-256 | `9f94af73a1a7ab440d381268281989cb80698b3921ebec95772e2b889fc54ffb` |

Apply `m5-pro-m16.patch` and `prompt-lookup-serve.patch` to the pinned
lookup source. Place the two official Metal libraries in its `build/`
directory, then link the host:

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  make -j 4 -o build/splash.metallib -o build/host-step.metallib \
  PRODUCTION_AIRS= build/splash
```

The installed runtime lives in
`bench/runtimes/splash-1.6.0-llm-launcher-m5-pro-r1`.
