# Third-party notices

LLM Launcher is licensed under Apache-2.0. It integrates with separately installed applications and includes one adapted utility that requires explicit attribution.

## Adapted source

`ane_fp16_clone.py` is derived from `tools/clone_mlx_model_fp16.py` in [oMLX v0.6.3rc2](https://github.com/jundot/omlx/blob/v0.6.3rc2/tools/clone_mlx_model_fp16.py). oMLX is licensed under [Apache-2.0](https://github.com/jundot/omlx). The launcher version adds stricter source validation, symlink rejection, staging rules, structured progress, and caller-owned promotion checks.

## External applications and libraries

The repository can interoperate with oMLX, LM Studio, MTPLX, FreeToken, Pi, OpenCode, Codex, Hugging Face tooling, MLX, and safetensors. Except for source explicitly present in this repository, those projects, applications, libraries, model weights, names, and trademarks are not bundled and remain subject to their own licences and terms.

References to third-party products describe compatibility and do not imply endorsement or affiliation.
