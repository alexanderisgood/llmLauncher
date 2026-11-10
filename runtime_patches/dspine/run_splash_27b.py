"""Run one short, greedy Qwen3.8-27B request in the isolated Splash build."""

import argparse
import json
import os
import select
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parents[1] / "bench/runtimes/dspine-27b-experimental"
MLX_PYTHON = (
    Path.home() / "Library/Application Support/LLM Launcher/runtimes/omlx-0.7.0.dev2/bin/python"
)
CONTEXT = 2048


@contextmanager
def child(command, **kwargs):
    with subprocess.Popen(command, **kwargs) as process:
        try:
            yield process
        finally:
            if process.stdin is not None:
                process.stdin.close()
            elif process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def wait_for_sidecar(sidecar, path, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if sidecar.poll() is not None:
            raise RuntimeError(f"DSpine sidecar exited with status {sidecar.returncode}")
        if path.exists() and path.stat().st_mode & 0o777 == 0o600:
            return
        time.sleep(0.05)
    raise TimeoutError("DSpine sidecar did not become ready")


def events(process, wire, timeout=300):
    parser = wire.FrameParser()
    fd = process.stdout.fileno()
    deadline = time.monotonic() + timeout
    while select.select([fd], [], [], max(0, deadline - time.monotonic()))[0]:
        chunk = os.read(fd, 65536)
        if not chunk:
            raise RuntimeError(f"Splash stopped before completing the request ({process.poll()})")
        offset = 0
        while offset < len(chunk):
            step = parser.consume(memoryview(chunk)[offset:])
            if step.issue:
                raise RuntimeError(step.issue.describe())
            offset += step.consumed_bytes
            if step.frame:
                yield wire.decode_frame(step.frame)
    raise TimeoutError("Splash did not complete the request before the timeout")


def generate(args, wire, prompt, env, engine_log):
    command = [
        str(args.runtime / "splash/build/splash"), "serve-native", str(args.runtime / "model"),
        str(CONTEXT), "auto", "0", "--persistent-cache", "off",
        "--idle-release", "off", "--idle-sleep", "allow", "--ane", "off",
    ]
    if args.verify_all:
        command += ["--verify-rows", "all"]
    with child(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=engine_log, env=env,
    ) as engine:
        tokens = []
        for event in events(engine, wire):
            if isinstance(event, wire.ReadyEvent):
                remaining_us = 120_000_000
                frame = wire.RequestFrame(
                    request_id=1, priority=wire.RequestPriority.FOREGROUND,
                    absolute_deadline_unix_micros=time.time_ns() // 1000 + remaining_us,
                    remaining_deadline_micros=remaining_us,
                    logical_max_output_tokens=args.max_tokens, prompt_tokens=tuple(prompt),
                    sampling=wire.SamplingParameters(), seed=0,
                    constraint=wire.ConstraintMode.NONE, image_spans=(), image_pixels=b"",
                    score_tokens=(), generation_prompt_tokens=0,
                    flags=wire.RequestFlag(0), cache_salt=0,
                )
                engine.stdin.write(wire.serialize_message(frame))
                engine.stdin.flush()
            elif isinstance(event, (wire.StartFailedEvent, wire.ErrorEvent)):
                raise RuntimeError(event.message.decode("utf-8", errors="replace"))
            elif isinstance(event, wire.TokensEvent):
                if event.sequence_offset != len(tokens):
                    raise RuntimeError("Splash returned a non-contiguous token sequence")
                tokens.extend(event.tokens)
            elif isinstance(event, wire.DoneEvent):
                if event.reason == wire.FinishReason.CANCELLED or not tokens:
                    raise RuntimeError("Splash ended without a successful completion")
                return tokens, {
                    "prompt_tokens": event.prompt_tokens,
                    "tokens": len(tokens),
                    "prefill_seconds": event.prefill_micros / 1e6,
                    "decode_seconds": event.decode_micros / 1e6,
                    "decode_tps": 1e6 * len(tokens) / max(1, event.decode_micros),
                    "drafted": event.drafted_tokens,
                    "accepted": event.accepted_draft_tokens,
                    "draft_cycles": event.draft_cycles,
                }


def run(args, wire, prompt, drafter):
    env = dict(os.environ)
    env.pop("SPLASH_EXPERIMENTAL_DSPINE_SOCKET", None)
    with tempfile.TemporaryDirectory(prefix="splash-dspine-", dir="/private/tmp") as scratch:
        folder = Path(scratch)
        engine_log = folder / "engine.log"
        sidecar_log = folder / "sidecar.log"
        try:
            with engine_log.open("w") as log:
                if drafter == "dflash2":
                    return generate(args, wire, prompt, env, log)
                path = folder / "d.sock"
                env["SPLASH_EXPERIMENTAL_DSPINE_SOCKET"] = str(path)
                command = [
                    str(args.mlx_python), "-u", str(HERE / "splash_sidecar.py"),
                    "--socket", str(path), "--target", str(args.target),
                    "--draft", str(args.runtime / "weights"),
                ]
                sidecar_env = dict(env, PYTHONPATH=str(args.runtime / "tencent/dspine_mlx"))
                with sidecar_log.open("w") as side_log, child(
                    command, stdout=side_log, stderr=subprocess.STDOUT, env=sidecar_env,
                ) as sidecar:
                    wait_for_sidecar(sidecar, path)
                    return generate(args, wire, prompt, env, log)
        except (OSError, RuntimeError, wire.ProtocolError) as error:
            for path in (engine_log, sidecar_log):
                if path.is_file():
                    print(path.read_text()[-5000:], file=sys.stderr)
            raise SystemExit(f"{drafter}: {error}") from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=RUNTIME)
    parser.add_argument("--mlx-python", type=Path, default=MLX_PYTHON)
    parser.add_argument("--drafter", choices=("dspine", "dflash2", "compare"), default="dspine")
    parser.add_argument("--verify-all", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=96)
    parser.add_argument("--prompt", default="Write a Python implementation of Conway's Game of Life with comments.")
    args = parser.parse_args()
    args.runtime = args.runtime.resolve()
    record = json.loads((args.runtime / "model/model.json").read_text())
    args.target = Path(record["sources"]["target"]["repo"])
    if not args.target.is_absolute() or not args.target.is_dir():
        parser.error("Prepare the Splash model from the local MLX checkpoint")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    sys.path.insert(0, str(args.runtime / "release"))
    from server import protocol as wire
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.target, local_files_only=True)
    prompt = tokenizer.apply_chat_template(
        [{"role": "user", "content": args.prompt}],
        tokenize=True, return_dict=False, add_generation_prompt=True, enable_thinking=False,
    )
    if not 0 < args.max_tokens <= CONTEXT - len(prompt):
        parser.error("Prompt plus output must fit within 2048 tokens")
    drafters = ("dflash2", "dspine") if args.drafter == "compare" else (args.drafter,)
    outputs = {}
    for drafter in drafters:
        tokens, stats = run(args, wire, prompt, drafter)
        outputs[drafter] = tokens
        print(json.dumps({drafter: stats}), flush=True)
    if len(outputs) > 1:
        stock, dspine = outputs["dflash2"], outputs["dspine"]
        first_difference = next(
            (i for i, pair in enumerate(zip(stock, dspine)) if pair[0] != pair[1]),
            None if len(stock) == len(dspine) else min(len(stock), len(dspine)),
        )
        print(json.dumps({"identical_tokens": stock == dspine, "first_difference": first_difference}))
    else:
        print(tokenizer.decode(tokens, skip_special_tokens=True))


if __name__ == "__main__":
    def stop(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130) from None
