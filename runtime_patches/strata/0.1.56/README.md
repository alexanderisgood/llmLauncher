# Strata 0.1.56: split GGUF SSD streaming

Based on the exact released Metal engine commit, with an opt-in host-side patch.
`STRATA_METAL_SPLIT_GGUF=1` loads the first shard's metadata, validates every
sibling, retains each tensor's physical file location and directs the existing
SSD reads to that file. Resident whole-file GPU wrapping is refused for splits.
The default single-file loader and all Metal shaders are unchanged.

No merged GGUF or copied expert/table payload is required. The ordinary Strata
support pack is about 1.4 GiB; its small projection conversions are recorded in
`conversions.json`. The expert quantization and BF16 PLE payload stay unchanged.

Validation: all 1,224 actual tensor shapes/types/offsets, 3,672 actual production
SSD reads compared with original files, malformed/missing shard rejection,
real generation and a tool-call/result round trip. Use the upstream Mac arguments,
including `--expert-cache 64 --prefill auto --spec 2`; this cache is separate from
the Metal SSD arena. No performance superiority claim is made.

Rebuild with the pinned source/ggml commits and Metal C++ headers, apply the patch,
then build the `strata` target of the `metal/` CMake project. The installed patched
runtime keeps the official kernel resources alongside `engine/strata`.
