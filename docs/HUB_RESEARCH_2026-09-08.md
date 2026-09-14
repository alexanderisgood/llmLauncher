# Community reports checked against the current launcher

Reviewed on 8 September 2026 after the user requested Reddit and X searches.
Community measurements are leads, not replacements for tests on this device.

## Findings that match the symptoms

| Report | What it establishes | Applicability here |
| --- | --- | --- |
| [Reddit: Qwen3.8 on an M5 Pro with 48 GB](https://www.reddit.com/r/oMLX/comments/1w5ns18/qwen3827b_on_my_m5_pro_i_want_to_use_omlx_but/) | The author measured real tool-heavy decode falling from 8.8 to 4.4 tokens/s as prompts grew from roughly 38K to 52K. | Similar memory class and symptom, but Q4/native MTP/oMLX 0.6.3rc2. It does not prove a fix or rank our DFlash2/Q6 route. |
| [DFlash2 file-writing slowdown report](https://huggingface.co/incoai/Qwen3.8-27B-DFlash2-GGUF/discussions/3) and [actual fix](https://github.com/HermiG/llama.cpp/commit/fe3e373e3f6e3ea56f19e5a7c10abe5b4b13777a) | A full-vocabulary grammar scan made llama.cpp's stochastic verifier expensive during tool calls. Switching to its lazy verifier while grammar is active fixed that path. | Real fix, different implementation. Installed MLX probability filtering/rejection sampling has no corresponding grammar scan; tool parsing happens after decoding. Do not transplant the GGUF patch. |
| [oMLX cache issue #3182](https://github.com/jundot/omlx/issues/3182) and [memory estimation issue #2865](https://github.com/jundot/omlx/issues/2865) | Other users report lost warm prefixes and large memory projections on long requests. | Different runtime/settings. Our actual rejected-snapshot calculations and native allocation tests establish the local cause more directly. |
| [Simon Willison's Qwen3.8 tests](https://simonwillison.net/2026/Aug/16/qwen-38-27b/) | First-person tests show excessive planning and scope expansion, while Pi can still complete useful coding work. | Supports testing lower reasoning effort, with thinking enabled. It does not show that lowering effort always preserves quality. |

## Guidance and fixes already accounted for

- [Qwen's own model card](https://huggingface.co/Qwen/Qwen3.8-27B) supports
  low/medium/xhigh effort and preserving historical reasoning for continuity
  and prefix reuse. It also warns that reducing effort can increase retries.
  Preservation is already enabled. The 2,048-token/low trial is a trial, not a
  proven universal replacement for medium.
- [Official DFlash MLX guidance](https://github.com/z-lab/dflash) recommends
  block sizes of five or less for quantized weights. Our size four already
  complies. Re-enabling DFlash is not a new optimization.
- [Native DFlash v0.1.10](https://github.com/bstnxbt/dflash-mlx/releases/tag/v0.1.10)
  documents resident-array adoption and consumed-snapshot release. That matches
  the allocation ownership used by the launcher's corrected guard.
- [oMLX fix #3285](https://github.com/jundot/omlx/pull/3285) addresses shared
  DFlash/MTP patch contamination that could cause repetition. Installed 0.6.4
  includes it. The separately reported [SDPA256 integration issue](https://github.com/jundot/omlx/issues/3241)
  is already covered by the launcher's engine-owned integration.

## Qwopus claims have material limits

The [author's model card](https://huggingface.co/Jackrong/Qwopus3.8-27B-Flash-GGUF/blob/main/README.md)
acknowledges a Python indentation defect, with a
[cross-runtime reproduction report](https://huggingface.co/Jackrong/Qwopus3.8-27B-Flash/discussions/1).
The advertised 13/14 agent result used Q5 GGUF, MTP, Q8 KV, an RTX 5090 and
thinking disabled. It is not evidence of equivalent reliability with thinking
enabled in Pi on this Mac. One reported task passed tests but continued working
until its deadline. The current standard Qwen 6-bit trial avoids assuming a
fine-tune automatically fixes the harness or model behavior.

The three older X URLs in the conversation could not be opened directly.
Indexed X excerpts were used only to locate primary documentation; the exact
Benjamin Marie and Oluwaphilemon posts could not be verified. No unverified
social-media patch was installed.
