# Hardened Uzu 0.5.23 server patch

The [bounded-prefill build](EXPERIMENTAL_PREFILL.md) is now installed and admitted
by the normal launcher on the qualification host. Its exact local 64K and 128K
receipts were adopted unchanged, with existing history backed up and retained.
The build is not publicly distributed. Isolated-browser Apply/reopen and Launch
readiness passed, as did backend receipt validation and real-model relay recovery.
Starting a real chat through the browser remains a separate pending check.

Current build: `0.5.23-llm-launcher.prefill-experiment.1`, 65,079,520 bytes,
binary SHA-256 `efe7fc98a8e063c30103a27badb4f308b8cb782708134a7805178f9e16caa0ce`.
Apply `llm-launcher-hardening.patch`, `experimental-bounded-prefill.patch`, then
`experimental-quiet-build.patch` to the pinned upstream revision. The SHA-256 of
their bytes concatenated in that order is
`680e2d72f0ba7a63fc822543022c6a1fc9b2895276fb7252a8049219de58692f`.
See the linked build record for compiler flags and measurements. The original
hardening patch and historical `.2` build record below are preserved separately.

Offline startup also requires the launcher's catalog adapter. Uzu 0.5.23 reads
`~/.cache/mirai/resolved-models.json` (schema 2), not the older `registry.json`.
During explicit launch, the controller may create this file only when absent,
after validating all original model receipts and pinned SHA-256 values. Its
single filesystem-source entry preserves the verified model metadata and points
to the existing model directory; `files: null` disables native download tasks.
The exact catalog is checked again at exec, and an existing different catalog
is rejected without overwriting it. Native `list-models` succeeded with outbound
networking denied on the qualification Mac. This is a startup check, not a
successful long-context inference qualification.

This directory contains the launcher-owned source patch for the experimental resident Uzu route. It is intentionally pinned to one upstream revision:

- Upstream repository: <https://github.com/trymirai/uzu>
- Upstream tag: `0.5.23`
- Upstream commit: `115609b6ef7ce5a94fc761bf395780f032b09f9b`
- Patch SHA-256: `6caceb71adad8a609dec32e2c6eaf5bd72f0b7240564eeb9ead5c67bc53ab124`
- Upstream-declared Rust MSRV: `1.98.0`

The patch must not be applied to another Uzu revision. The launcher must identify the resulting binary by an exact SHA-256 before admitting it; a matching version string alone is not sufficient.

## What the patch changes

The stock Uzu server exposes an unauthenticated raw loopback listener and does not accept a native context or response ceiling. This patch:

- restricts the server to a loopback address;
- requires a one-use API-key file in an owner-controlled `0700` directory;
- accepts only an owner-owned, single-link, non-symlink `0600` key file, consumes it before model discovery or allocation, and rejects replacement or hard-link races;
- requires Bearer authentication on both model-list and chat-completion routes, including their `/v1` aliases;
- configures the model session with a native context limit;
- renders and tokenizes the complete canonical prompt with the same model tokenizer and chat template as inference for an early rejection, then authoritatively reserves the response against the live cached-token state plus exact new suffix immediately before generation;
- commits prompt history, encoded input, and cache state only after token preflight succeeds, so a rejected overflow cannot poison a later turn;
- reports an interrupted generation as `cancelled` rather than misrepresenting it as a normal `stop` completion;
- enforces a mandatory response-token ceiling across both OpenAI limit aliases; and
- caps request bodies at 16 MiB.

The launcher's authenticated relay and conservative request estimate remain defense-in-depth controls. They are not substitutes for these native checks.

## Review and test the patch

From a clean clone of Uzu:

```sh
git checkout 115609b6ef7ce5a94fc761bf395780f032b09f9b
git apply --check /absolute/path/to/llm-launcher-hardening.patch
git apply /absolute/path/to/llm-launcher-hardening.patch
cargo fmt --all -- --check
cargo test --release -p nagare --locked --offline --ignore-rust-version -- --test-threads=1
cargo test -p cli --no-default-features --features backend-cpu --locked --offline --ignore-rust-version -- --test-threads=1
```

The CPU-feature test build exercises the server contract without loading or running a model. Any executable admitted by the launcher still needs its own exact-hash build record and launcher-side boundary tests before the Uzu card may be enabled.

At the time this patch was captured, all 8 stateful Nagare regression tests and all 74 CPU-only CLI tests passed with no model load. This includes rollback after a rejected overflow followed by a successful replacement turn, and cancellation-finish-reason coverage. A clean `git apply --check` against the pinned upstream commit also passed. The launcher tests verify the checked-in patch digest and its boundary contract, but the full native apply/build/test sequence above is not yet reproduced in public CI.

## Historical local build record — superseded by bounded prefill

Launcher build `0.5.23-llm-launcher.2` was produced locally from the upstream commit and patch named above. The successful release build used Homebrew `rustc 1.97.1` and `cargo 1.97.1`, despite upstream declaring Rust 1.98.0, with the following explicit build environment and flags:

```sh
export TOOLCHAINS=com.apple.dt.toolchain.Metal.32023.883
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
/opt/homebrew/bin/cargo build --release -p cli --locked --offline --ignore-rust-version -j2
```

- Installed launcher path: `~/Library/Application Support/LLM Launcher/runtimes/uzu-0.5.23-llm-launcher.2/mirai`
- Architecture: `arm64`
- Binary size: `65,104,480` bytes
- Binary SHA-256: `d90089131806aeb7a388058bb3f5f5e386aa40847ad24910a574ebf82a8c438e`
- Installed directory mode: `0700`
- Installed binary mode: `0500`
- Code-signing state: ad-hoc linker signature only; not Developer ID signed and not notarized

This SHA-256 identifies the previous locally qualified binary, which remains
installed untouched but is no longer the normal admission identity. The source
patches do not promise byte-for-byte reproduction: compiler, dependencies,
Xcode/Metal toolchain, SDK, linker and other build inputs would require exact
independent pins. Current admission checks the bounded-prefill build's exact
installed path, size and SHA-256 rather than trusting its version string.

## Licence

Uzu is MIT-licensed. Its notice is preserved in [LICENSE.UZU](LICENSE.UZU). Model weights are separate downloads and are not included here.
