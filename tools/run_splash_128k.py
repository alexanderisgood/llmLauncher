#!/usr/bin/env python3
"""Serve Inco's Splash engine (Qwen3.8-27B-Splash) on a free port at 128K.

Why this helper exists: the `splash` CLI hardcodes 127.0.0.1:8000 and refuses to
start when another service owns it — on this Mac the launcher's oMLX server
listens there — while the engine's own `server.py` accepts `--port`. This
script drives that server directly, so Splash runs alongside everything else.

Measured on this M5 Pro (48 GB), 19 September 2026, Splash 1.0 with
`incoai/Qwen3.8-27B-Splash` (17.4 GB), standing 112,881-token prompt:

    cold prefill   324.5 / 337.9 tok/s      (two runs)
    decode         25.3 tok/s (reasoning off), 36.6 tok/s (reasoning medium)
    cached prefix  first token in 390 ms on the same 112,881-token context
    4 concurrent   at 33K: 114.6 tok/s aggregate; at 128K: 45.2 tok/s
    code workloads 56.9 tok/s at 33K, 43.2 at 84K

It binds loopback only, prints the OpenAI base URL, and stops the engine on
Ctrl-C or SIGTERM. It never downloads anything: run
`splash serve --model incoai/Qwen3.8-27B-Splash` once (or `hf download`) to
fetch the pack first.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import secrets
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import splash_runtime
from splash_reasoning import verify_frontend

HOME = pathlib.Path.home()
LIBEXEC = pathlib.Path("/opt/homebrew/opt/splash/libexec")
MODELS = HOME / "Library/Application Support/Splash/models"
DEFAULT_MODEL = "incoai/Qwen3.8-27B-Splash"
DEFAULT_PORT = 8010


def model_root(model: str, models: pathlib.Path | None = None) -> pathlib.Path:
    """Directory holding a Splash package (target/, draft/, tokenizer/)."""
    if not splash_runtime.OWNER_REPO.fullmatch(model):
        raise ValueError("Splash model must be an owner/repo identifier")
    return (models or MODELS) / model


def pack_ready(root: pathlib.Path) -> tuple[bool, str]:
    """Fail-closed check that the package is installed and complete enough."""
    pack = splash_runtime.inspect_pack(root)
    if pack is None:
        return False, "invalid manifest.json or missing/incomplete target, draft or tokenizer artifacts"
    return True, "manifest artifact paths and sizes checked"


def build_argv(
    model: str = DEFAULT_MODEL,
    *,
    port: int = DEFAULT_PORT,
    context: int = 131072,
    max_memory: str = "auto",
    libexec: pathlib.Path | None = None,
    models: pathlib.Path | None = None,
    output: int = splash_runtime.DEFAULT_OUTPUT,
) -> list[str]:
    """Exact argv for the engine server (kept pure so tests can assert it)."""
    root = libexec or LIBEXEC
    pack = model_root(model, models)
    return splash_runtime.planning_arguments(
        {"python": str(root / "python/bin/python3"), "server": str(root / "server/server.py"),
         "engineBinary": str(root / "engine/splash")},
        {"path": str(pack), "id": model}, context, port=port,
        output=output, max_memory=str(max_memory),
    )


def free_port(preferred: int, *, tries: int = 20) -> int:
    """First free loopback port at or after ``preferred``."""
    for candidate in range(preferred, preferred + tries):
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", candidate))
            except OSError:
                continue
            return candidate
    raise SystemExit(f"no free loopback port in {preferred}..{preferred + tries - 1}")


def wait_ready(port: int, process: subprocess.Popen, timeout: float, api_key: str = "", model: str = DEFAULT_MODEL) -> dict:
    url = f"http://127.0.0.1:{port}/v1/models"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise SystemExit(f"Splash exited with {process.returncode}")
        try:
            request = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
            with urllib.request.urlopen(request, timeout=3) as response:
                catalog = json.load(response)
                splash_runtime.validate_served_catalog(catalog, model)
                return catalog
        except (OSError, urllib.error.URLError, ValueError):
            time.sleep(1.0)
    raise SystemExit("Splash did not become ready in time")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--context", type=int, default=131072)
    parser.add_argument("--output", type=int, default=splash_runtime.DEFAULT_OUTPUT)
    parser.add_argument("--max-memory", default="auto")
    parser.add_argument("--ready-timeout", type=float, default=300.0)
    parser.add_argument("--print-argv", action="store_true")
    parser.add_argument("--check", action="store_true",
                        help="validate the install and package, then exit")
    args = parser.parse_args(argv)

    install = splash_runtime.inspect_install(libexec=LIBEXEC)
    if not install or not install.get("ready"):
        print("Splash install is incomplete or failed its release hash check.", file=sys.stderr)
        return 2
    try:
        verify_frontend(LIBEXEC / "server")
        splash_runtime.doctor(install, args.context)
        ready, detail = pack_ready(model_root(args.model))
        command = build_argv(args.model, port=args.port, context=args.context,
                             max_memory=args.max_memory, output=args.output)
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    if not ready:
        print(f"Splash package {args.model} is not ready: {detail}\n"
              f"Download it with: splash serve --model {args.model} "
              "(stop that server afterwards) or: hf download "
              f"{args.model} --local-dir '{model_root(args.model)}'", file=sys.stderr)
        return 2
    if args.check:
        print(f"Splash ready: {args.model} ({detail})")
        return 0

    if args.print_argv:
        print(shlex.join(command))
        return 0
    port = free_port(args.port)
    command = build_argv(args.model, port=port, context=args.context,
                         max_memory=args.max_memory, output=args.output)
    print(f"Starting Splash · {args.model} · context {args.context} · "
          f"http://127.0.0.1:{port}", flush=True)
    credentials = tempfile.TemporaryDirectory(prefix="splash-host-")
    key_path = pathlib.Path(credentials.name) / "api-key"
    api_key = os.environ.get("SPLASH_API_KEY") or secrets.token_urlsafe(32)
    with open(key_path, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as handle:
        handle.write(api_key)
    env = splash_runtime.clean_environment(dict(os.environ))
    env["SPLASH_API_KEY"] = api_key
    process = None

    def stop(*_signal: object) -> None:
        raise SystemExit(128 + int(_signal[0]))
    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        process = subprocess.Popen(command, start_new_session=True, env=env)
        catalog = wait_ready(port, process, args.ready_timeout, api_key, args.model)
        served = (catalog.get("data") or [{}])[0].get("id", args.model)
        print(f"Ready · {served}\n"
              f"  OpenAI base URL: http://127.0.0.1:{port}/v1\n"
              f"  API key file: {key_path} (removed when the host stops)\n"
              "  Measured here: 324-338 tok/s cold prefill, 25.3 tok/s decode "
              "(36.6 with reasoning on),\n"
              "                 390 ms cached TTFT at 128K, 45 tok/s aggregate "
              "with 4 concurrent streams.\n"
              "Ctrl-C stops the engine.", flush=True)
        while process.poll() is None:
            time.sleep(1.0)
    finally:
        for sig in previous:
            signal.signal(sig, signal.SIG_IGN)
        try:
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        finally:
            credentials.cleanup()
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
