# Flint through Rec

Select **Rec**, **Recursive Flint INT4**, and Pi, oh-my-pi, OpenCode or built-in
Chat in the launcher. Rec serves Chat Completions; the launcher does not enable
Codex for this route because its Responses API adapter is not available.

This integration uses the official [Rec engine](https://github.com/recursive-oss/rec)
and [RecursiveSI/flint-int4 weights](https://huggingface.co/RecursiveSI/flint-int4).
Rec 0.1.0 supports Apple M4 Pro, M5 Pro and M5 Max with at least 48 GB unified
memory. Upstream asks for about 30 GB free disk. The INT4 checkpoint occupies
about 22.6 GB; projections and experts use group-64 affine INT4 and embeddings
use INT8. The model runs in unified memory.

[Flint](https://huggingface.co/RecursiveSI/flint) has 39.8B total parameters,
about 2.5B active per token, and supports text, reasoning and function tools.
Its 262,144-token context includes both prompt and output. A smaller selected
context can reduce cache memory. The context limit does not establish uniform
quality at every length.

Reasoning is always on in Rec. Thinking consumes the same maximum-response
budget as the answer. The launcher therefore offers **Model default** rather
than effort levels or a reasoning-off switch. The model's recommended sampling
is temperature 1.0, top-p 0.95 and top-k 20. Custom temperature, top-p, top-k,
presence penalty and seed are supported; frequency and repetition penalties
must stay neutral. Tool selection supports automatic tools or no tools.

The launcher starts its own foreground Rec server with a private local API key
and the selected context. Rec is designed for one generation at a time. Start
the route from the launcher so it can manage that server's lifetime and connect
the chosen assistant. Rescan after installation or model download completes.

No local throughput or agent-task benchmark is claimed by this integration.
Saved measurements appear only after measuring the exact local setup.
