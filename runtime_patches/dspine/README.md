# DSpine on Splash 1.6.0

This local experiment pairs the official Tencent BF16 DSpine drafter with
the installed Qwen3.8-27B MLX 4-bit checkpoint. Splash evaluates the target
and decides which proposals to commit. An on-demand MLX child process reads
the target's embedding and output head directly from their shards and
receives five BF16 hidden-state taps over a private Unix socket.

The experiment serves one greedy text request at a time with up to 262,144
tokens across the prompt and answer. Splash keeps the full target context,
verifies DSpine proposals and applies its native thinking budget and tool
grammar. DSpine uses its trailing 8,192-token attention window at absolute
positions within the prompt. Splash can reuse a matching resident target
prefix and rebuild the trailing draft context for a follow-up. The
DSpine model assembly contains the text target and tokenizer. Its warmup
exercises target verification with synthetic proposals. The MLX child
proposes tokens for live requests.

## Run from Local LLM Launcher

Rescan models, select **Splash** and **Qwen3.8-27B-4bit · Splash**, then open
**Runtime settings → Acceleration** and choose **DSpine · Experimental**.
Choose Chat or oh-my-pi, a context window up to **256K** and a reasoning
level before launch. The context includes instructions, tool definitions,
history and the response. At 256K the sidecar converts the draft backbone
to Q4 in memory, keeps the refinement bridge in BF16, and reads the target
embedding and BF16 refinement tables by row from file-backed mappings.
Smaller windows use the original BF16 draft. The launcher reserves the
sidecar's running memory and Splash's native macOS allowance, then caps
Splash to the remaining budget. The native planner checks the full context
at load time. Stopping the session releases both workers.
The launcher package in `bench/runtimes/splash-1.6.0-llm-launcher-dspine-r3`
uses the 1.6.0 release libraries with the patched host and assembly validator.
The original checkpoint files are reused in place.

## Run the standalone comparison

From the launcher directory:

```sh
bench/runtimes/dspine-27b-experimental/release/python/bin/python3 \
  runtime_patches/dspine/run_splash_27b.py --max-tokens 96 \
  --prompt "Explain how a Tetris ghost piece finds its landing row."
```

Use `--drafter compare` to run the same tokenized prompt through DFlash2 and
DSpine sequentially and report native decode speed, accepted tokens and
output token parity. The standalone comparison uses the earlier host and a
2,048-token window. The runner stops the engine and sidecar on exit.

## Local verification

On the M5 Pro, with the installed 4-bit target, the same Game of Life prompt
and 96 greedy completion tokens:

| Drafter | Decode tokens/s | Accepted proposals | Output compared with DFlash2 |
| --- | ---: | ---: | --- |
| Splash DFlash2 | 62.5 | 73 / 154 | Reference |
| DSpine BF16 | 32.1 | 71 / 168 | All 96 tokens matched |
| DSpine with an in-memory Q4 backbone | 35.5 | 70 / 182 | All 96 tokens matched |

The Q4 trial quantized the draft backbone in memory while retaining the BF16
bridge and the same target. This is a single prompt comparison. In a
separate MLX diagnostic, the batched target and token-at-a-time target
rounded two near-tied logits differently even with rollback disabled.
The BF16 Splash runner also answered a separate 1,119-token inventory
prompt with the correct final row number.

## Build inputs

| Input | Pin |
| --- | --- |
| [Splash 1.6.0](https://github.com/incoai/splash/releases/tag/1.6.0) | `9124ff2ce1e6d19dab6bb0f2aa94b214b1271ce2` |
| Splash macOS arm64 release archive SHA-256 | `da3aef0a581491b0eb4c1168bda07f520e5ca8368764abff426d95ac1c77e5c4` |
| [Tencent DSpine MLX source](https://github.com/Tencent/DSpine/tree/6450af726375cb3c6bac4de95d98ebc8df99fbd4) | `6450af726375cb3c6bac4de95d98ebc8df99fbd4` |
| [Tencent 27B BF16 draft](https://huggingface.co/tencent/Qwen3.8-27B-DSpine-b16) | `ea909c0f5fab8865f9e14600334f55f7ce47308f` |
| Draft `model.safetensors` SHA-256 | `ac90f1df842ea66b23e4224f3e86624add547526f689ffe9e9c6b7a5937116b1` |

The ignored runtime directory `bench/runtimes/dspine-27b-experimental`
contains the pinned Splash checkout in `splash`, the official release in
`release`, the pinned DSpine checkout in `tencent` and the verified draft
`config.json` and `model.safetensors` in `weights`. To rebuild from clean
copies, apply the patches to their respective checkouts, then link the host
against the matching release Metal libraries.

```sh
runtime="$PWD/bench/runtimes/dspine-27b-experimental"
splash_source="$PWD/bench/runtimes/splash-1.6.0-source"
patch -d "$runtime/tencent" -p1 < runtime_patches/dspine/draft-27b.patch
patch -d "$splash_source" -p1 < runtime_patches/dspine/splash-1.6.0.patch
mkdir -p "$splash_source/build"
cp -p "$runtime/release/engine/"*.metallib "$splash_source/build/"
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  make -C "$splash_source" -o build/splash.metallib \
  -o build/host-step.metallib PRODUCTION_AIRS= build/splash
```

Copy the built host and patched `install/assembly.py` into the launcher
runtime package with the matching Metal libraries. The launcher's
`prepare-dspine` source helper creates the text-only assembly on demand.
The sidecar uses the existing MLX 0.32.2 Python environment. The standalone
comparison accepts `--mlx-python` to point to another compatible interpreter.
