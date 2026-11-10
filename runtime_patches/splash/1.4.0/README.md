# Splash 1.4.0: original BF16 PLE rows

Upstream 1.4.0 advertises BF16 embedding support, but its host image planner
uses the projection format's 256-element blocks to size raw embedding rows.
Flash-Next's original PLE has 160 BF16 values per row, so integer division
produces a zero-byte row and startup fails with `unexpected size for
per_layer_token_embd.weight`. The embedding kernels already use one BF16 value
per block; no shader or model-weight change is needed.

`bf16-embedding-rows.patch` separates raw BF16/F16 embedding row extents from
projection packing. It updates the image planner, streamed-table planner,
weight-image validation and embedding dispatch validation. Quantized formats
keep their existing block rules. All Q4 main tensors and original BF16 PLE
payload bytes remain unchanged.

The isolated runtime is
`bench/runtimes/splash-1.4.0-llm-launcher-bf16-r1`. Its `launcher-patch.json`
matches the tracked `bf16-embedding-rows.json`; its `release.json` describes the
new binary, while the official runtime remains intact. The manifest pins the
source archive, patch, four changed sources, executable and unchanged official
metallibs. The executable was rebuilt using command-line tools and SDK 27.0,
with macOS 26.4 as its deployment target. No Metal kernel was rebuilt or changed.

The CPU check parses a tiny GGUF through the production native loader and
confirms a 160-column BF16 row occupies 320 bytes. Static checks preserve F16
raw rows and the existing Q4/projection layouts. It does not load a model or
start Metal inference. Actual startup qualification is recorded separately.

Rebuild from the source archive pinned in the manifest, apply the patch, and
place the official 1.4.0 `splash.metallib` and `host-step.metallib` in `build/`:

```sh
make -j 4 -o build/splash.metallib -o build/host-step.metallib build/splash
```
