# oMLX 0.7 preview

Runtime Manager offers the official **0.7.0.dev2** wheel as the Preview track.
Stable 0.6.4 and earlier managed installations remain available for rollback.
The preview installs separately; selecting **Use for new sessions** changes the
executable for subsequent oMLX sessions. Slotstream and its Q8 runtime remain independent.

## Full Flash with expert SSD offload

Dev2 adds [upstream MoE expert offload](https://github.com/jundot/omlx/blob/v0.7.0.dev2/docs/MoE_Expert_Offload.md).
The launcher exposes the existing full Qwen3.8 Flash-Next Q4 pack as
**Qwen3.8 Flash-Next · oMLX · SSD experts** after verifying its safetensors headers
and selecting the qualified dev2 runtime. It reuses the existing model files.
Both routed experts and PLE/ngram tables can be read from SSD; routing retains
access to every original expert.

Engine tuning exposes **Experts kept in RAM** (12.5–75%, default 25%) and a separate
**Maximum process RAM (GB)** (default 41 GB, decimal). The ceiling is a limit, not an instruction
to allocate that much immediately. Expert share controls the resident cache;
context, cache growth, workspace and protected macOS headroom also need memory.
Capacity checks use the selected share, ceiling and current machine headroom.
The Metal device's reported working-set limit is used when no explicit wired
limit is configured; the launcher does not change that system limit.

**MTP and DFlash cannot be combined with this release's expert offload.** Both
upstream settings validation and model loading reject that combination. The
launcher disables those choices for this route. The separate Slotstream Q8 cache
patch is not an oMLX QSA-cache implementation; oMLX Flash uses its supported
full-precision cache. Larger context selections remain available when capacity
permits, but are not all qualified by the local smoke test.

Dev2 also includes upstream Flash decode, QSA, hyper-connection and PLE optimizations.
Individual fast paths depend on checkpoint layout; the installed pack falls back
to canonical hyper-connection normalization. Installation does not establish a
speed improvement over Slotstream.

## Pinned installation

- Release: <https://github.com/jundot/omlx/releases/tag/v0.7.0.dev2>
- Commit: `b390b31e0c6831225fed0f24d278eb1db7fcb68b`
- Artifact: `omlx-0.7.0.dev2-cp311-cp311-macosx_15_0_universal2.whl`
- SHA-256: `fd0104efc037b4a9f84ecd9f9a7489f30c51f3ea041f95552a2249e0966bb178`
- Audited CPython 3.11 wheel; MLX 0.32.2 and four full-commit Git dependencies.
- Dependencies are staged, hashed, installed offline and recorded in a local
  manifest. Package/CLI version, dependency and native Qwen-kernel checks must pass.

Numbered development versions have distinct identities and sort before release
candidates/final releases. Dev1 and older RC provenance is retained. Stable-only
DFlash adapters are not applied to the preview's different upstream API.

## Local validation, 15 September 2026

On the 48 GiB M5 Pro, the managed installer verified the official dev2 artifact
and 109 staged dependency artifacts. Both the upstream header checker and launcher
validator accepted the installed full Q4 pack. The pack contains 32,000,153,600
bytes of PLE tables and 67,947,724,800 bytes of routed expert tensors; these are
accounted separately so SSD savings are applied once.

The actual full Flash model loaded with expert and PLE offload, 25% expert RAM
share, a 41 GB ceiling, 16K context and speculation disabled. It returned the
expected arithmetic response through authenticated Hub Chat. Native loaded model
allocation was about 19.79 GB; memory grows with other engine allocations and
context. This is an integration smoke test, not a sustained throughput benchmark.

Hub metrics now recognize native oMLX generation duration, decode speed and time
to first token. Prompt-processing speed is reported from native timing on uncached
requests. Cached requests are not assigned misleading prefill speed from a timing
that includes reused prompt tokens.

A second launch passed at 32K context with the same 25% share and 41 GB ceiling.
A 109-token counting response completed correctly at 3.32 native decode tokens/s;
its uncached 29-token prompt took 13.26 seconds (2.19 tokens/s). This small sample
is slow and does not justify replacing Slotstream on performance grounds. A 37.5%
share was rejected by the live headroom check with other apps open.

A forced `record_number` tool call returned valid arguments with the expected value
133. The model selector and expert RAM controls were also exercised in the browser.
Launcher tests passed (306 tests, 10 skips); oMLX tests passed (62 tests, six skips),
with relevant JavaScript UI and native-metric checks passing.
