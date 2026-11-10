# Local Slotstream Q8 KV runtime

This is a separate local fork of Slotstream 0.2.17 at commit
`d25dffff1f3f56e70ddb9f11b82e7dc1b843f041`. The full-precision runtime and
105 GB model pack stay in place. Q8 changes attention cache storage, not the
Q4 model weights, expert count, routing, n-gram storage, or GDN recurrent state.

The launcher selects the separately pinned executable only when **KV cache
precision → Q8** is selected. Both startup planning and the running model's
catalog must acknowledge Q8. `manifest.json` must mark the exact binary as
qualified; arbitrary locally rebuilt binaries are not silently trusted.

## Implementation

- Main and MTP caches pack eight-bit affine values into UInt32 arrays, with
  one BF16 scale and bias per group of 64 channels. All six allocations count
  toward live-state and growth budgets.
- Prefix forks share packed values and metadata using independent MLX array
  contexts. Rollback trims the logical offset and subsequent writes replace
  rejected rows; it does not replay accepted tokens.
- Decode/MTP attention reads packed values directly in a two-stage Metal
  kernel. Sparse-invisible keys are skipped before payload reads. Partial
  softmax statistics and accumulation use FP32.
- Prefill reconstructs one attention layer at a time and retains the existing
  selected-attention/bounded-prefill path. Its temporary BF16 buffers are
  explicitly priced before dispatch. The empirical BF16 fixed footprint and
  Hermes reserve remain conservative allowances.
- The cache layout uses 1,088 bytes per attention layer/token for K and V,
  versus 2,048 BF16 bytes: 46.875% less KV storage, including quantization
  metadata. The unchanged 256-byte indexer row makes combined main
  KV/indexer storage 16,128 bytes/token across twelve layers. Recurrent state,
  pooled indexer storage, MTP and stepped spare capacity are separately charged.

The small tensor timing fixture compares fused Q8, direct MLX quantized
matmul, and reconstruction followed by SDPA in interleaved rounds. It does
not establish whole-model speed or quality. A configured 128K window is not
proof of full-window model qualification. See the final qualification evidence
beside this file for actual coverage and limitations.

## Rebuilding

Check available memory and stop other model processes before model tests.
Two build workers limit compiler memory on the shared 48 GiB machine:

```sh
python3 runtime-patches/slotstream-q8/build.py \
  --source-dir /tmp/slotstream-q8-rebuild \
  --metallib "$HOME/.slotstream/releases/llm-launcher-0.2.17/mlx.metallib"
```

The script checks out the exact upstream commit, applies `q8.patch`, uses the
pinned metallib, and builds/runs the tensor checks. It does not install or
approve a new binary. Re-run native MTP/prefix and application checks before
updating its hash and qualification manifest. Compiler/build paths can change
the resulting binary hash even when the source patch is identical.

Upstream Slotstream is MIT licensed; see `UPSTREAM-LICENSE`. The MLX
quantized-attention API reference is
[MLX-LM's attention implementation](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/models/base.py).

## 0.2.20-q8.1 (17 September 2026)

The Q8 KV patch rebased onto upstream v0.2.20 (`6e25b00`; `Sources/` there is
byte-identical to tag `v0.2.20`). Rebase diff:
`q8-0.2.20.patch`, version string `0.2.20-q8.1`. Every added and removed line
in the 18 patched files is identical to `q8.patch` except `Version.swift`, so
the Q8 arithmetic is unchanged; `ContextMemory.swift` is untouched by upstream
0.2.17→0.2.20, so the six Q8 allocations keep their accounting. Details and the
two traps below: `bench/notes/q8-rebase-verification.md`.

```sh
git clone https://github.com/carloslfu/slotstream.git /tmp/slotstream-q8-rebase
cd /tmp/slotstream-q8-rebase && git checkout --detach 6e25b00
git apply runtime-patches/slotstream-q8/q8-0.2.20.patch
mkdir -p Tools/lib && cp "$HOME/.slotstream/releases/llm-launcher-0.2.17/mlx.metallib" Tools/lib/mlx-0.31.1.metallib
nice -n 10 make build SLOTSTREAM_BUILD_JOBS=2 \
  DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer TOOLCHAINS=Metal
.build/release/slotstream-checks --tier t1 --filter q8-cache      # 45 assertions
```

Installed as `~/.slotstream/releases/llm-launcher-0.2.20-q8.1/` — binary
sha256 `3197a638ab7a14d6fb7c17f9bfc6b286e343f9ff0657f01627e8c960d53e8f44`,
metallib `198488eb…` (the same digest the official 0.2.20 release archive
ships, and the Makefile's pinned 0.31.1 metallib).

Host requirement: Xcode's `metal` driver refuses to run without the **Metal
Toolchain** component. `xcodebuild -downloadComponent MetalToolchain` then
`ln -sfn /Volumes/MetalToolchainCryptex/Metal.xctoolchain
~/Library/Developer/Toolchains/Metal.xctoolchain` makes it available to
SwiftPM with `TOOLCHAINS=Metal DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer`.

### Traps when upstream moves (keep these in mind on the next rebase)

1. Upstream's experimental `attention-readout`, `boundary-readout` and
   `attention-readout-corrected` lookahead taps call `QSAAttention.readout` /
   `GDNLayer.readout`, which read `cache.keys`/`cache.values` as floating-point
   rows. In this fork those two arrays hold packed UInt32 words, so those taps
   are **not Q8-safe** (wrong forecast at best). The default `boundary` tap,
   the `attention`/`attention-corrected` taps the shipped sidecar selects, and
   `attention-shared` touch no cache and are safe.
2. `PersistentPrefixSave`/`Restore` (the 0.2.18 `--prefix-cache-dir` on-disk
   prefix cache) persist only `kv.keys`/`kv.values`, not the four Q8
   scale/bias tensors, so a Q8 restore would be corrupt. Keep that tier off
   until the format carries the metadata.

## Q8.2 telemetry and local tuning

Q8.2 preserves Q8.1 inference arithmetic and memory policy. It adds a numeric
`slotstream_metrics` object to OpenAI responses. Streaming clients requesting
`include_usage` receive a `prefilled` event before generated output and a
`completed` measurement alongside final usage. Cache reuse is excluded from
processed-token throughput. Expert-pool metadata uses the engine's synchronized
snapshot. The earlier cache/MTP/prefix evidence remains attributed to Q8.1 in
`qualification/q8.1-manifest.json`; Q8.2-specific evidence is under
`qualification/performance-2026-09-14/`.

Three interleaved paired coding samples at a matched 32 GB target and 128K
configured context favored two MTP drafts over three: median 13.93 vs 12.78
native decode tokens/sec. Each process warmed up for 128 output tokens before
its 384-token sample, with greedy sampling and seed 42. All three pairs favored
two drafts; sampled paging counters did not change during measured requests.
These are short prompts, not a full-window or universal speed qualification.

A separate operational check used the user's 41 GB automatic ceiling. Two
and three drafts measured 13.80 and 13.56 tok/s respectively, but changing
available memory gave them different expert-pool allocations. That single
pair cannot establish a significant speedup. The local Pi session uses two
drafts based on the matched samples while retaining the user's 41 GB ceiling,
128K context and Q8 cache. Upstream defaults and general launcher defaults
remain unchanged. On restoration the native automatic plan selected a 38.2 GB
process target and a 21.1 GB expert pool; these are allocation budgets, not
resident-memory or throughput guarantees. See `restored-session.json` in the
performance evidence directory.
