#!/usr/bin/env python3
"""Run one long-context measurement against a local engine.

Typical invocations:

* Cold 120K-token prefill plus 256-token decode on MTPLX with Q8 KV:
  ``python3 bench/run.py --engine mtplx --model mtplx-27b-speed --label 27b-baseline``
* Flash-Next through the Q8 Slotstream runtime:
  ``python3 bench/run.py --engine slotstream --model flash-next-4bit --label flash-baseline``
* Measure an already-running engine instead of launching one:
  ``python3 bench/run.py --engine mtplx --attach --port 18765 --label manual``
"""
from __future__ import annotations

import argparse
import contextlib
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness  # noqa: E402


def parse_key_values(items: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"expected KEY=VALUE, got {item!r}")
        key, value = item.split("=", 1)
        values[key] = value
    return values


def build_engine(args: argparse.Namespace) -> harness.Engine:
    extras = tuple(args.extra_arg or ())
    env = parse_key_values(args.extra_env or [])
    per_model = json.loads(args.per_model_json) if args.per_model_json else None
    default_models = {
        "mtplx": "mtplx-27b-speed",
        "omlx": "mlx-27b-6bit",
        "slotstream": "flash-next-4bit",
        "llamacpp": "qwen35-moe-q6",
        "splash": "incoai/Qwen3.8-27B-Splash",
    }
    model = args.model or default_models[args.engine]
    if args.engine == "mtplx":
        return harness.make_mtplx(
            model,
            port=args.port,
            context=args.context,
            kv=args.kv,
            profile=args.profile,
            depth=args.depth,
            generation=args.generation,
            reasoning=args.reasoning,
            max_tokens=args.max_response,
            extra_args=extras,
            extra_env=env,
            binary=args.binary or harness.MTPLX_BIN,
        )
    if args.engine == "omlx":
        return harness.make_omlx(
            model,
            port=args.port,
            context=args.context,
            kv=args.kv,
            memory_guard_gb=args.memory_gb,
            max_tokens=args.max_response,
            per_model=per_model,
            extra_settings=json.loads(args.settings_json) if args.settings_json else None,
            binary=args.binary or harness.OMLX_DEFAULT_BIN,
        )
    if args.engine == "slotstream":
        return harness.make_slotstream(
            model,
            port=args.port,
            context=args.context,
            kv=args.kv,
            memory_gb=args.memory_gb,
            draft_depth=args.depth,
            mtp=args.mtp,
            extra_args=extras,
            extra_env=env,
            binary=args.binary,
            memory_auto=args.memory_auto,
            max_ram_percent=args.max_ram_percent,
        )
    if args.engine == "llamacpp":
        return harness.make_llamacpp(
            model,
            port=args.port,
            context=args.context,
            kv=args.kv,
            batch=args.batch,
            ubatch=args.ubatch,
            flash_attn=args.flash_attn,
            extra_args=extras,
            extra_env=env,
            binary=args.binary or harness.LLAMACPP_BIN,
        )
    if args.engine == "splash":
        return harness.make_splash(
            model,
            port=args.port,
            context=args.context,
            max_memory=f"{args.memory_gb:.0f}G" if args.memory_gb else "auto",
            pack_root=args.splash_pack,
            extra_args=extras,
            extra_env=env,
        )
    raise SystemExit(f"unknown engine {args.engine!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--engine", choices=("mtplx", "omlx", "slotstream", "llamacpp", "splash"),
        required=True,
    )
    parser.add_argument(
        "--model",
        default=None,
        help="model alias (mtplx-27b-speed, mlx-27b-6bit, flash-next-4bit) or directory",
    )
    parser.add_argument("--kv", default="q8", choices=("off", "q8", "q6", "q4"))
    parser.add_argument("--context", type=int, default=131072)
    parser.add_argument("--prompt-tokens", type=int, default=120000)
    parser.add_argument("--gen-tokens", type=int, default=256)
    parser.add_argument("--max-response", type=int, default=4096)
    parser.add_argument("--prompt-name", default="ledger2")
    parser.add_argument("--chars-per-token", type=float, default=4.5)
    parser.add_argument("--profile", default="turbo")
    parser.add_argument("--generation", default="mtp", choices=("mtp", "ar", "auto"))
    parser.add_argument("--reasoning", default="off", choices=("off", "auto", "on"))
    parser.add_argument(
        "--depth",
        type=int,
        default=None,
        help="MTP draft depth; default 3 for MTPLX, 2 for Slotstream",
    )
    parser.add_argument("--mtp", default="on", choices=("on", "off", "auto"))
    parser.add_argument("--memory-gb", type=float, default=41.0)
    parser.add_argument(
        "--memory-auto",
        action="store_true",
        help="slotstream: native auto sizing (the launcher default) instead of --memory-gb",
    )
    parser.add_argument(
        "--max-ram-percent",
        type=float,
        default=None,
        help="slotstream --memory-auto ceiling; defaults to --memory-gb as a share of RAM",
    )
    parser.add_argument("--batch", type=int, default=2048, help="llama.cpp logical batch")
    parser.add_argument("--ubatch", type=int, default=512, help="llama.cpp physical batch")
    parser.add_argument("--flash-attn", default="on", choices=("on", "off", "auto"))
    parser.add_argument(
        "--min-headroom-gb",
        type=float,
        default=20.0,
        help="reclaimable memory required before a model may load (default 20)",
    )
    parser.add_argument("--port", type=int, default=harness.DEFAULT_PORT)
    parser.add_argument("--binary", help="override the engine executable path")
    parser.add_argument("--label", default="run")
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--warm", action="store_true", help="measure a warm (prefix-cached) request instead of cold")
    parser.add_argument("--keep-alive", action="store_true", help="leave the engine running after the measurement")
    parser.add_argument("--attach", action="store_true", help="use an already-running engine")
    parser.add_argument("--no-lock", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--extra-arg", action="append")
    parser.add_argument("--extra-env", action="append")
    parser.add_argument("--per-model-json")
    parser.add_argument("--settings-json")
    parser.add_argument(
        "--splash-pack",
        help="Splash: model root for a derived pack (its own manifest.json)",
    )
    args = parser.parse_args()
    if args.depth is None:
        args.depth = 2 if args.engine == "slotstream" else 3

    prompt_path = harness.prompt_file(
        args.prompt_name, args.prompt_tokens, args.chars_per_token,
    )
    engine = build_engine(args)
    # MTPLX maps request-level "none" to its lowest thinking level, so omit the
    # field and let the server's --reasoning flag decide.
    request_effort = None if args.engine == "mtplx" else "none"
    print(
        f"[bench] prompt {prompt_path.name}: {prompt_path.stat().st_size} chars "
        f"~{prompt_path.stat().st_size / args.chars_per_token:.0f} tokens",
        flush=True,
    )

    if args.dry_run:
        print(engine.command_line())
        print("env:", json.dumps(engine.env, indent=2))
        return 0

    lock = (
        contextlib.nullcontext()
        if args.no_lock
        else harness.bench_run(
            f"{args.label} {args.engine}", minimum_headroom_gb=args.min_headroom_gb,
        )
    )
    payload: dict = {
        "label": args.label,
        "engine": args.engine,
        "startedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "config": vars(args),
        "command": engine.command_line(),
        "environment": engine.env,
        "promptFile": str(prompt_path),
        "measurements": [],
    }
    with lock:
        if args.attach:
            if args.model and args.model not in harness.MODEL_PATHS:
                engine.model_id = args.model
            try:
                engine.wait_ready()
            except Exception as error:  # noqa: BLE001
                print(f"[bench] attach failed: {error}", file=sys.stderr)
                return 2
            prompt = prompt_path.read_text(encoding="utf-8")
            for _ in range(args.reps):
                payload["measurements"].append(
                    harness.stream_chat(
                        engine, prompt, max_tokens=args.gen_tokens,
                        reasoning_effort=request_effort,
                    )
                )
        else:
            for rep in range(args.reps):
                # A second request inside one process would hit the prefix
                # cache, so every cold rep gets a fresh engine (--warm keeps
                # the deliberate in-process warm-up request instead).
                engine.start()
                try:
                    engine.wait_ready()
                    measurement = harness.measure(
                        engine, prompt_path, max_tokens=args.gen_tokens,
                        warm=args.warm, reasoning_effort=request_effort,
                    )
                    if args.engine == "splash":
                        measurement["nativeMetrics"] = harness.splash_status(engine)
                    payload["measurements"].append(measurement)
                finally:
                    if not (rep == args.reps - 1 and args.keep_alive):
                        engine.stop()

    for measurement in payload["measurements"]:
        print(json.dumps({
            "promptTokens": measurement.get("promptTokens"),
            "completionTokens": measurement.get("completionTokens"),
            "cachedPromptTokens": measurement.get("cachedPromptTokens"),
            "prefillTokensPerSecond": measurement.get("prefillTokensPerSecond"),
            "nativePrefillTokensPerSecond": measurement.get("nativePrefillTokensPerSecond"),
            "decodeTokensPerSecond": measurement.get("decodeTokensPerSecond"),
            "generationTimingSource": measurement.get("decodeTimingSource"),
            "generationTimingBasis": measurement.get("decodeTimingBasis"),
            "endToEndTokensPerSecond": measurement.get("endToEndTokensPerSecond"),
            "nativeDecodeTokensPerSecond": measurement.get("nativeDecodeTokensPerSecond"),
            "ttftSeconds": measurement.get("ttftSeconds"),
            "totalSeconds": measurement.get("totalSeconds"),
        }, indent=2))
    path = harness.write_result(args.label, payload)
    print(f"[bench] wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
