# Rapid MLX

Select **Rapid MLX** in the launcher's engine menu to run a complete local MLX
checkpoint. The adapter supports built-in Chat, Pi, oh-my-pi, OpenCode and
Codex. The engine starts only when a session launches and stops with that
session; it has no login service or automatic restart policy.

The adapter targets [Rapid-MLX 0.16.9](https://github.com/raullenchai/Rapid-MLX/releases/tag/v0.16.9),
commit `7b3d9527df3d54c27bb5ed7beca5203e3a445abf`. Install the official
`rapid-mlx==0.16.9` package in an isolated Python environment. The launcher
recognises its managed `runtimes/rapidmlx-0.16.9` environment, the official
`~/.rapid-mlx` environment, Homebrew and local command installations when their
package metadata can be inspected. An unsupported version remains visible in
the runtime manager with an explanation.

Existing model weights are reused without conversion or another download.
Flint INT4 can use the same files already installed for Rec. Qwen3.8 27B and
other supported MLX checkpoints appear when their complete weights are in a
configured model library. Checkpoints are shared by any engine that actually
supports their architecture and files, regardless of which engine discovered
them. Rapid needs safetensors; a GGUF-only copy or a Splash `.bin` pack needs a
compatible MLX copy before Rapid can load it.

**Auto** uses native MTP when a trained local head is present; **Off** uses
standard decoding. **MTP** lets you choose the maximum draft depth and keeps
Rapid's adaptive per-round depth enabled. The Qwen3.8 27B validated checkpoint
defaults to depth 3. Flash Next supports depths 1 and 2, with 1 as its default.
Other supported families expose depths 1–6 as launcher tuning choices; 6 is a
UI limit rather than an upstream engine limit. The optimistic MTP option is
not enabled. Flint lacks an MTP head and uses standard decoding.

KV stays BF16. DFlash and quantized KV controls remain unavailable in this
adapter. Context and response choices
are checked against the model's native window and current memory headroom.
The native server enforces the selected context window and generation ceiling;
the session relay also enforces its response limit. A session becomes ready
only after `/health/ready` confirms loading and warmup, and the authenticated
model catalog contains the selected served model.

Flash Next MLX support is exposed when its complete checkpoint is installed.
This does not make it fit in 48 GB: Rapid's published Flash alias requires at
least 128 GB, and its experts remain resident. PLE-only NVMe offload is not
full expert streaming. The existing Splash GGUF Q4/BF16 PLE checkpoint cannot
be passed to Rapid or converted automatically by this adapter.

The listener binds to `127.0.0.1` with a private per-session API key. Telemetry,
update checks, inference-time model downloads and disk prompt caches are
disabled. The running session can still reuse its in-memory prefix cache.
No permanent coding-agent settings are changed.

Codex uses native stateless Responses requests with complete conversation
history. Its four native sampling fields are temperature, top-p, top-k and
seed. Model-default presence, frequency and repetition penalties are pinned
on the server at startup; custom penalties that the Responses API cannot
represent are rejected before launch. Chat-based clients can use all seven
advertised sampling fields.

Verification covers passive discovery, complete-model checks, changed-file
rejection, launch planning, local authentication, readiness, proxy requests,
UI controls and Stop/Quit recognition with synthetic fixtures. The installed
CLI parser accepts the generated server arguments. This is not a measured
model-performance or long-context qualification; no large inference test was
run during setup.

On October 26, a normal launcher session loaded the existing Flint INT4 at 8K
context with a 256-token response ceiling, returned `OK` to a short prompt,
and unloaded cleanly. MTP discovery and configuration were checked using local
header fixtures and the installed native parser; MTP inference was not run
because no compatible trained-head checkpoint is currently installed.
