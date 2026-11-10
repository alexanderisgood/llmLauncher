#!/usr/bin/env python3
"""Serve the Qwen3.8-35B-A3B Q6_K GGUF in its measured-fastest configuration.

Measured on an M5 Pro 48 GB, 18 September 2026, 112,881-token prompt, Q8 KV:
392.1 prefill / 32.5 decode tok/s with `--load-mode mlock`, versus 358.5 /
31.5 with the default mmap — byte-identical greedy output. The launcher's
LM Studio route cannot express `mlock`, so this helper starts the
launcher-managed llama.cpp server directly with the tuned flags.

It binds loopback only, prints the OpenAI base URL, and stops the server on
Ctrl-C or SIGTERM. It never downloads anything.
"""
from __future__ import annotations

import argparse
import pathlib
import signal
import subprocess
import sys

HOME = pathlib.Path.home()
SERVER = (
    HOME
    / "Library/Application Support/LLM Launcher/runtimes/llama.cpp-b10740/llama-server"
)
MODEL = (
    HOME
    / ".lmstudio/models/Qwen/Qwen3.8-35B-A3B-GGUF/Qwen3.8-35B-A3B-Q6_K.gguf"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=pathlib.Path, default=MODEL)
    parser.add_argument("--context", type=int, default=131072)
    parser.add_argument("--port", type=int, default=18765)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--batch", type=int, default=2048)
    parser.add_argument("--ubatch", type=int, default=2048)
    parser.add_argument("--kv", default="q8_0", help="cache type for K and V")
    parser.add_argument(
        "--load-mode", default="mlock", choices=("auto", "mlock", "mmap", "none"),
        help="mlock measured +9.4%% prefill; it pins the 27 GB of weights",
    )
    parser.add_argument("--no-flash-attn", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not SERVER.is_file():
        raise SystemExit(f"launcher-managed llama-server not found: {SERVER}")
    if not args.model.is_file():
        raise SystemExit(f"model not found: {args.model}")
    argv = [
        str(SERVER),
        "-m", str(args.model),
        "-c", str(args.context),
        "-ctk", args.kv,
        "-ctv", args.kv,
        "-fa", "off" if args.no_flash_attn else "on",
        "-ngl", "999",
        "-b", str(args.batch),
        "-ub", str(args.ubatch),
        "--load-mode", args.load_mode,
        "--host", args.host,
        "--port", str(args.port),
        "--jinja",
        "--no-webui",
    ]
    print(" ".join(argv), flush=True)
    if args.dry_run:
        return 0

    def interrupted(signum, _frame):
        raise SystemExit(128 + signum)

    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    process = None
    try:
        process = subprocess.Popen(argv, start_new_session=True)
        return process.wait()
    finally:
        # Repeated stop signals must not interrupt child cleanup.
        for sig in previous:
            signal.signal(sig, signal.SIG_IGN)
        try:
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
