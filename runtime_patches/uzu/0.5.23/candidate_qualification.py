"""Isolated developer qualification of the exact pinned bounded-prefill build.

Default: print a no-load calibration plan. --run requires exclusive ownership of
the normal controller lock (stop the normal controller first), and uses the
unchanged launcher benchmark worker/guards with a separate evidence directory.
No downloads, production runtime replacement, or receipt copying are performed.
"""
from __future__ import annotations

import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import signal
import stat
import sys
import time

PATCH_ROOT = Path(__file__).resolve().parent
ROOT = PATCH_ROOT.parents[2]
STATE = ROOT / "build" / "uzu-prefill-candidate"
TAG = "0.5.23-llm-launcher.prefill-experiment.1"
BINARY_SHA256 = "efe7fc98a8e063c30103a27badb4f308b8cb782708134a7805178f9e16caa0ce"
BINARY_SIZE = 65_079_520
# SHA-256 of the three patch files concatenated in verifier.PATCHES order.
PATCH_CHAIN_SHA256 = "680e2d72f0ba7a63fc822543022c6a1fc9b2895276fb7252a8049219de58692f"
MODEL_ID = "uzu-58a4a2b149eddad1e821e795"


def configure_candidate(app):
    """Change only this imported process; never the production module on disk."""
    old_state = app.STATE_DIR
    for name, value in list(vars(app).items()):
        if name.isupper() and isinstance(value, Path) and value.is_relative_to(old_state):
            setattr(app, name, STATE / value.relative_to(old_state))
    app.UZU_RUNTIME_TAG = TAG
    app.UZU_RUNTIME_DIR = app.MANAGED_RUNTIMES_DIR / f"uzu-{TAG}"
    app.UZU_RUNTIME_PATH = app.UZU_RUNTIME_DIR / "mirai"
    app.UZU_RUNTIME_RELEASE_BINARY_SHA256 = BINARY_SHA256
    app.UZU_RUNTIME_RELEASE_BINARY_SIZE = BINARY_SIZE
    app.UZU_RUNTIME_SOURCE_PATCH_SHA256 = PATCH_CHAIN_SHA256
    app.RUNTIME_CANDIDATE_SPECS = {
        **app.RUNTIME_CANDIDATE_SPECS,
        "mirai": (("launcher-managed", str(app.UZU_RUNTIME_PATH), "Unqualified prefill experiment"),),
    }
    app.BINARIES = {**app.BINARIES, "mirai": str(app.UZU_RUNTIME_PATH)}
    # Do not import the baseline's identity or its cached admission conclusions.
    app._VERIFIED_FILE_SHA256_CACHE.clear()
    return old_state / "controller-instance.lock"


def exclusive_controller_lock(path: Path):
    """Never truncate the normal controller's metadata, or stop its process."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1:
            raise ValueError("Normal controller lock is not a single owner-owned regular file")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Stop the normal launcher controller before running the isolated qualification") from error
        return os.fdopen(fd, "r")
    except BaseException:
        os.close(fd)
        raise


def request(context: int) -> dict:
    if context not in (65536, 131072):
        raise ValueError("Candidate qualification accepts only the existing 64K/128K tiers")
    return {
        "backend": "uzu", "client": "chat", "modelId": MODEL_ID,
        "project": str(ROOT), "context": context, "output": 16384,
        "reasoning": "auto", "mode": "custom",
        "options": {"acceleration": "off", "depth": 1, "kv": "off"},
        "chat": {"sampling": "model"}, "generation": {"sampling": "model"},
        "calibrationCooling": "default", "scope": "qualification",
        "enginePreference": "throughput",
    }


def run_qualification(app, payload, models):
    def stop(_signal=None, _frame=None):
        app.BENCHMARK.cancel()
        app.MANAGER.stop()

    for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(number, stop)
    try:
        app.BENCHMARK.start(payload, models)
        previous = None
        deadline = time.monotonic() + 3600
        while app.BENCHMARK.is_active():
            snapshot = app.BENCHMARK.snapshot()
            update = {key: snapshot.get(key) for key in ("phase", "progress", "message")}
            if update != previous:
                print(json.dumps(update), flush=True)
                previous = update
            if time.monotonic() > deadline:
                stop()
                raise TimeoutError("Candidate qualification exceeded its one-hour bound")
            time.sleep(1)
        final = app.BENCHMARK.snapshot()
        print(json.dumps(final, indent=2), flush=True)
        return 0 if final.get("phase") == "completed" else 1
    finally:
        stop()
        worker = app.BENCHMARK.thread
        if worker is not None:
            worker.join(timeout=30)
        if app.MANAGER.snapshot().get("phase") != "idle":
            raise RuntimeError("Candidate did not confirm clean unload; inspect its private run log")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--context", type=int, choices=(65536, 131072), default=65536)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(PATCH_ROOT))
    from verify_candidate_source import verify
    verify(args.source)
    spec = importlib.util.spec_from_file_location("uzu_candidate_launcher", ROOT / "launcher.py")
    app = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = app
    spec.loader.exec_module(app)
    production_lock = configure_candidate(app)
    contract = app.uzu_runtime_contract(str(app.UZU_RUNTIME_PATH))
    if contract.get("ready") is not True:
        raise RuntimeError(f"Pinned candidate is not staged safely: {contract}")
    payload = request(args.context)
    models = app.uzu_model_records(app.load_benchmark_records())
    plan = app.calibration_plan(payload, models)
    if not args.run:
        print(json.dumps(plan, indent=2))
        return 0
    with exclusive_controller_lock(production_lock):
        # Revalidate capacity in BenchmarkManager.start after taking ownership.
        # No old receipt is copied; 128K still requires this candidate's own 64K.
        for directory in (app.STATE_DIR, app.RUNS_DIR, app.LOGS_DIR):
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        return run_qualification(app, payload, models)


if __name__ == "__main__":
    raise SystemExit(main())
