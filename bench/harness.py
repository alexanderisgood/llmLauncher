"""Shared long-context benchmark harness for local inference engines.

Every measurement in this directory goes through :class:`BenchLock` so only
one model is resident on the 48 GiB host at a time, and through the engine's
own OpenAI-compatible streaming endpoint so only runtime-reported token counts
are used as evidence.

Design rules:

* One cold, uncached prefill per measured request. Warm requests reuse the
  prefix cache and are reported separately.
* Greedy sampling, fixed seed, fixed prompt file -> identical work per run.
* Both client-side timing and native engine telemetry are recorded; the
  native numbers win in reports when the engine publishes them.
"""
from __future__ import annotations

import contextlib
import dataclasses
import fcntl
import json
import os
import pathlib
import random
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from response_metrics import ResponseMetrics
from sse_framing import ResponseOutcome
import generation_metrics

HOME = pathlib.Path.home()
BENCH_DIR = pathlib.Path(__file__).resolve().parent
RESULTS_DIR = BENCH_DIR / "results"
PROMPTS_DIR = BENCH_DIR / "prompts"
RUNS_DIR = BENCH_DIR / "runs"
LOCK_PATH = pathlib.Path("/tmp/llm-launcher-bench.lock")

MTPLX_BIN = HOME / "Library/Application Support/MTPLX/runtime-venv/bin/mtplx"
MTPLX_WHEEL = pathlib.Path("/Applications/MTPLX.app/Contents/Resources/Runtime/mtplx-2.11.1-py3-none-any.whl")
OMLX_MANAGED_DIR = HOME / "Library/Application Support/LLM Launcher/runtimes"
OMLX_DEFAULT_BIN = OMLX_MANAGED_DIR / "omlx-0.7.0.dev2/bin/omlx"
SLOTSTREAM_BIN = HOME / ".slotstream/releases/llm-launcher-0.2.17/slotstream"
# Keep the harness on the runtime the launcher actually ships for Q8. The
# 0.2.17-q8.2 pin predated the 0.2.20-q8.1 rebase and silently measured an
# obsolete engine in every arm that did not pass --binary explicitly (the
# 19 Sep workspace-tile arms had to be run twice because of it).
SLOTSTREAM_Q8_BIN = HOME / ".slotstream/releases/llm-launcher-0.2.20-q8.1/slotstream"
LLAMACPP_BIN = (
    HOME / "Library/Application Support/LLM Launcher/runtimes/llama.cpp-b10740/llama-server"
)

MODEL_PATHS = {
    "mtplx-27b-speed": HOME / ".lmstudio/models/Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed",
    "mtplx-27b-quality": HOME / ".mtplx/models/Youssofal--Qwen3.8-27B-MTPLX-Optimized-Quality",
    "mlx-27b-6bit": HOME / ".lmstudio/models/lmstudio-community/Qwen3.8-27B-MLX-6bit",
    "flash-next-4bit": HOME / ".slotstream/models/qwen38-flash-next-mlx-4bit",
    "qwen35-moe-q6": (
        HOME / ".lmstudio/models/Qwen/Qwen3.8-35B-A3B-GGUF/Qwen3.8-35B-A3B-Q6_K.gguf"
    ),
}

DEFAULT_PORT = 18765


# --------------------------------------------------------------------------
# machine-wide serialization
# --------------------------------------------------------------------------


class BenchLock:
    """Advisory lock so benchmark agents never load two models at once."""

    def __init__(self, purpose: str = "", wait_seconds: float = 3600.0):
        self.purpose = purpose
        self.wait_seconds = wait_seconds
        self.handle = None

    def __enter__(self) -> "BenchLock":
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.handle = LOCK_PATH.open("a+")
        deadline = time.monotonic() + self.wait_seconds
        while True:
            try:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise TimeoutError(
                        f"model lock is held; waited {self.wait_seconds:.0f}s "
                        f"for {self.purpose!r}"
                    )
                time.sleep(5.0)
        holder = self.handle.read().strip()
        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(f"{os.getpid()} {self.purpose} {time.strftime('%H:%M:%S')}\n")
        self.handle.flush()
        if holder:
            print(f"[bench] lock acquired (previous holder: {holder})", flush=True)
        return self

    def __exit__(self, *exc) -> None:
        if self.handle is not None:
            self.handle.seek(0)
            self.handle.truncate()
            self.handle.write("")
            self.handle.flush()
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
            self.handle = None


ENGINE_PROCESS_NAMES = ("slotstream", "mtplx", "omlx", "llama-server", "Uzu", "uzu")


def foreign_engine_processes() -> list[str]:
    found: list[str] = []
    for name in ENGINE_PROCESS_NAMES:
        result = subprocess.run(["pgrep", "-x", name], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            found.append(f"{name}:{result.stdout.split()[0]}")
    return found


def reclaimable_bytes() -> int:
    text = subprocess.check_output(["vm_stat"], text=True)
    values = {k: int(v) for k, v in re.findall(r"^([^:]+):\s+(\d+)\.", text, re.M)}
    page = 16384
    return sum(
        values.get(key, 0)
        for key in ("Pages free", "Pages purgeable", "File-backed pages")
    ) * page


def wait_for_headroom(minimum_gb: float = 20.0, timeout: float = 900.0) -> int:
    deadline = time.monotonic() + timeout
    while True:
        available = reclaimable_bytes()
        if available >= minimum_gb * 1_000_000_000:
            return available
        if time.monotonic() > deadline:
            raise RuntimeError(
                f"only {available / 1e9:.1f} GB reclaimable; {minimum_gb:.0f} GB required"
            )
        print(f"[bench] waiting for headroom: {available / 1e9:.1f} GB", flush=True)
        time.sleep(10.0)


# --------------------------------------------------------------------------
# deterministic prompt material
# --------------------------------------------------------------------------

_VOCAB = (
    "cache prefix scheduler attention tensor kernel channel expert router decode "
    "prefill latency throughput memory quantisation window block layer head "
    "session ledger commit rollback snapshot stream buffer index shard group "
    "queue worker request token sample verify draft accept reject retry limit "
    "table column range offset stride vector matrix softmax normalise residual "
    "gradient embedding position rotary packing affine symmetric greedy seed "
    "temperature nucleus budget threshold manifest receipt evidence baseline "
    "promotion regression thermal ceiling reserve headroom admission reclaim"
).split()

_TASKS = (
    "Summarise the subsystem invariant in one sentence.",
    "List the failure mode and the guard that prevents it.",
    "Rewrite the routine with the same behaviour and fewer allocations.",
    "Name the counter that proves the optimisation did not change semantics.",
    "State the rollback path if the change regresses long-context decode.",
)

CLOSING_INSTRUCTION = (
    "\nEND OF LEDGER\n\n"
    "Task: without any preamble, write 140 numbered engineering rules that a "
    "reviewer could apply to the ledger above. One rule per line, 6 to 14 "
    "words each, numbered from 1 upward, and keep going to the end.\n"
)


def build_prompt(target_tokens: int, seed: int = 20260917, chars_per_token: float = 4.5) -> str:
    """Deterministic pseudo-corpus sized to ~target_tokens on Qwen tokenizers."""
    rng = random.Random(seed)
    target_chars = int(target_tokens * chars_per_token)
    parts: list[str] = [
        f"# Long-context engineering ledger (benchmark seed {seed})\n",
        "Treat every entry below as reference data. Do not summarise yet.\n\n",
    ]
    size = sum(len(p) for p in parts)
    entry = 0
    while size < target_chars:
        entry += 1
        words = " ".join(rng.choice(_VOCAB) for _ in range(rng.randint(28, 46)))
        task = rng.choice(_TASKS)
        block = (
            f"## entry {entry:06d}\n"
            f"fact: {words}.\n"
            f"task: {task}\n"
            f"counter: {rng.randint(10**8, 10**9)} delta {rng.randint(-999, 999)}\n\n"
        )
        parts.append(block)
        size += len(block)
    parts.append(CLOSING_INSTRUCTION)
    return "".join(parts)


def prompt_file(name: str, target_tokens: int, chars_per_token: float = 4.5) -> pathlib.Path:
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    path = PROMPTS_DIR / f"{name}-{target_tokens}.txt"
    if not path.exists():
        path.write_text(
            build_prompt(target_tokens, chars_per_token=chars_per_token),
            encoding="utf-8",
        )
    return path


# --------------------------------------------------------------------------
# engine processes
# --------------------------------------------------------------------------


@dataclasses.dataclass
class Engine:
    name: str
    argv: list[str]
    env: dict[str, str]
    port: int
    model_id: str
    work_dir: pathlib.Path
    api_key: str = ""
    ready_timeout: float = 900.0
    start_timeout_grace: float = 0.0
    process: subprocess.Popen | None = None
    log_path: pathlib.Path | None = None
    extra: dict = dataclasses.field(default_factory=dict)

    def command_line(self) -> str:
        return " ".join(self.argv)

    def start(self) -> None:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.work_dir / "engine.log"
        log = self.log_path.open("ab")
        env = os.environ.copy()
        env.update(self.env)
        print(f"[bench] start {self.name}: {self.command_line()}", flush=True)
        self.process = subprocess.Popen(
            self.argv,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    def wait_ready(self) -> None:
        assert self.process is not None
        started = time.monotonic()
        deadline = started + self.ready_timeout
        url = f"http://127.0.0.1:{self.port}/v1/models"
        while True:
            if self.process.poll() is not None:
                tail = ""
                if self.log_path and self.log_path.exists():
                    tail = self.log_path.read_text(errors="replace")[-2000:]
                raise RuntimeError(
                    f"{self.name} exited with {self.process.returncode}\n{tail}"
                )
            try:
                request = urllib.request.Request(url)
                if self.api_key:
                    request.add_header("Authorization", f"Bearer {self.api_key}")
                with urllib.request.urlopen(request, timeout=3) as response:
                    json.load(response)
                print(
                    f"[bench] {self.name} ready after {time.monotonic() - started:.0f}s",
                    flush=True,
                )
                return
            except (OSError, urllib.error.URLError, json.JSONDecodeError):
                pass
            if time.monotonic() > deadline:
                raise TimeoutError(f"{self.name} did not become ready in {self.ready_timeout:.0f}s")
            time.sleep(2.0)

    def stop(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                self.process.wait(timeout=45)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                self.process.wait(timeout=30)
        self.process = None
        print(f"[bench] {self.name} stopped", flush=True)

    def __enter__(self) -> "Engine":
        self.start()
        self.wait_ready()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()


def _model_path(model: str | pathlib.Path) -> pathlib.Path:
    if str(model) in MODEL_PATHS:
        return MODEL_PATHS[str(model)]
    path = pathlib.Path(model).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"model path not found: {path}")
    return path


def make_mtplx(
    model: str | pathlib.Path,
    *,
    port: int = DEFAULT_PORT,
    context: int = 131072,
    kv: str = "q8",
    profile: str = "turbo",
    depth: int = 3,
    generation: str = "mtp",
    reasoning: str = "off",
    max_tokens: int = 4096,
    extra_args: tuple[str, ...] = (),
    extra_env: dict[str, str] | None = None,
    work_dir: pathlib.Path | None = None,
    binary: pathlib.Path | str = MTPLX_BIN,
) -> Engine:
    path = _model_path(model)
    argv = [
        str(binary), "serve", "--yes", "--no-auth",
        "--model", str(path),
        "--model-id", "bench",
        "--profile", profile,
        "--host", "127.0.0.1", "--port", str(port),
        "--context-window", str(context),
        "--max-tokens", str(max_tokens),
        "--paged-kv-quantization", kv,
        "--scheduler-mode", "serial",
        "--batching-preset", "latency",
        "--ssd-session-cache", "off",
        "--fan-mode", "smart",
        "--reasoning", reasoning,
        *extra_args,
    ]
    if generation == "mtp":
        argv += ["--mtp", "--load-mtp", "--generation-mode", "mtp", "--depth", str(depth)]
    elif generation == "ar":
        argv += ["--no-mtp", "--no-load-mtp", "--generation-mode", "ar"]
    else:
        argv += ["--generation-mode", "auto"]
    env = {
        "MTPLX_ALLOW_SWAP": "0",
        "MTPLX_ASYNC_AR": "0",
        "MTPLX_FUSED_MOE_VERIFY": "0",
    }
    env.update(extra_env or {})
    return Engine(
        name=f"mtplx-{profile}-{kv}",
        argv=argv,
        env=env,
        port=port,
        model_id="bench",
        work_dir=work_dir or (RUNS_DIR / f"mtplx-{time.strftime('%H%M%S')}"),
        ready_timeout=1200.0,
        extra={"model": str(path), "context": context, "kv": kv, "depth": depth, "profile": profile},
    )


SPLASH_ROOT = pathlib.Path("/opt/homebrew/opt/splash/libexec")
SPLASH_MODELS = HOME / "Library/Application Support/Splash/models"


def make_splash(
    model: str = "incoai/Qwen3.8-27B-Splash",
    *,
    port: int = DEFAULT_PORT,
    context: int = 131072,
    max_memory: str = "auto",
    extra_args: tuple[str, ...] = (),
    extra_env: dict[str, str] | None = None,
    binary: pathlib.Path | str | None = None,
    root: pathlib.Path | str | None = None,
    pack_root: pathlib.Path | str | None = None,
    work_dir: pathlib.Path | None = None,
) -> Engine:
    """Launch Inco's Splash engine directly on a free port.

    ``splash serve`` hardcodes 127.0.0.1:8000 (and refuses to start if the
    user's oMLX server owns it), while the underlying ``server.py`` accepts
    ``--port``; the harness therefore drives the server itself and leaves any
    other local service untouched. The model pack lives under
    ``~/Library/Application Support/Splash/models/<repo id>`` (release layout).
    ``pack_root`` points the engine at a derived pack (its own ``manifest.json``
    plus ``target/``/``draft/``/``tokenizer/`` entries) so geometry experiments
    do not touch the installed release.
    """
    libexec = pathlib.Path(root or SPLASH_ROOT)
    model_root = pathlib.Path(pack_root) if pack_root else (SPLASH_MODELS / model)
    if not (model_root / "manifest.json").exists():
        raise FileNotFoundError(f"Splash pack not installed: {model_root}")
    work = work_dir or (RUNS_DIR / f"splash-{time.strftime('%H%M%S')}")
    argv = [
        str(libexec / "python" / "bin" / "python3"), "-u",
        str(libexec / "server" / "server.py"),
        str(model_root / "target"), str(model_root / "draft"),
        "--tokenizer", str(model_root / "tokenizer"),
        "--model", model,
        "--binary", str(binary or (libexec / "engine" / "splash")),
        "--max-memory", str(max_memory),
        "--max-context", str(context),
        "--port", str(port),
        "--no-webui",
        *extra_args,
    ]
    env = {"PYTHONUNBUFFERED": "1", "TRANSFORMERS_VERBOSITY": "error"}
    env.update(extra_env or {})
    return Engine(
        name="splash",
        argv=argv,
        env=env,
        port=port,
        model_id=model,
        work_dir=work,
        extra={"model": model, "context": context, "maxMemory": max_memory},
    )


# Prometheus lines worth keeping in a result file: scheduler batching, draft
# acceptance and cache reuse are what explain a Splash delta (or its absence).
SPLASH_METRIC_PREFIXES = (
    "splash_scheduler_",
    "splash_draft_acceptance_ratio",
    "splash_accepted_draft_tokens_total",
    "splash_drafted_tokens_total",
    "splash_cache_",
    "splash_kv_pages_",
    "splash_requests_",
)


def splash_status(engine: Engine) -> dict:
    """Best-effort native status/metrics snapshot for a running Splash engine."""

    def get(path: str) -> str:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{engine.port}{path}", timeout=15,
        ) as response:
            return response.read().decode("utf-8", "replace")

    snapshot: dict = {}
    try:
        snapshot["status"] = json.loads(get("/status"))
    except Exception as error:  # noqa: BLE001 - diagnostics only
        snapshot["statusError"] = str(error)
    try:
        text = get("/metrics")
        snapshot["metrics"] = [
            line for line in text.splitlines()
            if line.startswith(SPLASH_METRIC_PREFIXES)
        ]
    except Exception as error:  # noqa: BLE001 - diagnostics only
        snapshot["metricsError"] = str(error)
    return snapshot


def make_omlx(
    model: str | pathlib.Path,
    *,
    port: int = DEFAULT_PORT,
    context: int = 131072,
    kv: str = "q8",
    memory_guard_gb: float = 41.0,
    max_tokens: int = 4096,
    per_model: dict | None = None,
    extra_settings: dict | None = None,
    work_dir: pathlib.Path | None = None,
    binary: pathlib.Path | str = OMLX_DEFAULT_BIN,
) -> Engine:
    path = _model_path(model)
    work = work_dir or (RUNS_DIR / f"omlx-{time.strftime('%H%M%S')}")
    base = work / "omlx"
    catalog = base / "models"
    catalog.mkdir(parents=True, exist_ok=True)
    served = "bench"
    link = catalog / served
    if not link.exists():
        link.symlink_to(path, target_is_directory=True)
    settings = {
        "version": "1.0",
        "server": {"host": "127.0.0.1", "port": port, "log_level": "info", "auto_start_on_launch": False},
        "model": {"model_dirs": [str(catalog)], "model_dir": str(catalog), "model_fallback": False, "hide_helper_models": False},
        # oMLX reads only memory_guard_tier / memory_guard_custom_ceiling_gb
        # (omlx/settings.py MemorySettings.from_dict). The plain guard_mode /
        # guard_gb keys are ignored, which silently left every run on the
        # dynamic balanced ceiling.
        "memory": {
            "memory_guard_tier": "custom" if memory_guard_gb else "balanced",
            "memory_guard_custom_ceiling_gb": float(memory_guard_gb or 0),
        },
        "scheduler": {"max_concurrent_requests": 1, "embedding_batch_size": 8, "chunked_prefill": False, "prefill_priority": "context"},
        "cache": {"enabled": False, "ssd_cache_dir": str(work / "cache"), "ssd_cache_max_size": "40GB", "hot_cache_max_size": "0", "initial_cache_blocks": 256},
        "sampling": {"max_context_window": context, "max_context_window_policy": context, "max_tokens": max_tokens},
        "logging": {"log_dir": str(work / "logs"), "retention_days": 3},
    }
    if extra_settings:
        for section, values in extra_settings.items():
            settings.setdefault(section, {}).update(values)
    (base / "settings.json").write_text(json.dumps(settings, indent=2), encoding="utf-8")
    model_settings = {
        "version": 1,
        "models": {
            served: {
                "max_context_window": context,
                "max_tokens": max_tokens,
                "force_sampling": False,
                "preserve_thinking": False,
                "turboquant_kv_enabled": kv != "off",
                "turboquant_kv_bits": {"q8": 8, "q6": 6, "q4": 4}.get(kv, 4),
                "turboquant_skip_last": True,
                "mtp_enabled": False,
                "dflash_enabled": False,
                "trust_remote_code": False,
                "is_default": True,
                **(per_model or {}),
            }
        },
    }
    (base / "model_settings.json").write_text(json.dumps(model_settings, indent=2), encoding="utf-8")
    argv = [
        str(binary), "serve",
        "--base-path", str(base),
        "--model-dir", str(catalog),
        "--host", "127.0.0.1", "--port", str(port),
        "--max-concurrent-requests", "1",
    ]
    return Engine(
        name=f"omlx-{kv}",
        argv=argv,
        env={"OMLX_BASE_PATH": str(base)},
        port=port,
        model_id=served,
        work_dir=work,
        ready_timeout=1800.0,
        extra={"model": str(path), "context": context, "kv": kv},
    )


def make_slotstream(
    model: str | pathlib.Path = "flash-next-4bit",
    *,
    port: int = DEFAULT_PORT,
    context: int = 131072,
    kv: str = "q8",
    memory_gb: float = 41.0,
    draft_depth: int = 2,
    mtp: str = "on",
    extra_args: tuple[str, ...] = (),
    extra_env: dict[str, str] | None = None,
    work_dir: pathlib.Path | None = None,
    binary: pathlib.Path | str | None = None,
    memory_auto: bool = False,
    max_ram_percent: float | None = None,
) -> Engine:
    path = _model_path(model)
    if binary is None:
        binary = SLOTSTREAM_Q8_BIN if kv == "q8" else SLOTSTREAM_BIN
    if memory_auto:
        if max_ram_percent is None:
            # Mirror slotstream_runtime.planning_arguments: the launcher's
            # default route bounds native auto sizing by the whole-process
            # ceiling expressed as a share of physical RAM.
            total_ram = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
            max_ram_percent = min(100.0, memory_gb * 1_000_000_000 / total_ram * 100)
        memory_args = ["--max-ram-percent", f"{max_ram_percent:.6f}"]
    else:
        memory_args = ["--memory-gb", str(memory_gb)]
    argv = [
        str(binary), "serve",
        "--model", str(path),
        "--port", str(port),
        *memory_args,
        "--max-context", str(context),
        "--mtp", mtp,
        "--vision", "off",
        *extra_args,
    ]
    env = {"SLOTSTREAM_DRAFT_DEPTH": str(draft_depth)}
    if kv == "q8":
        # Measure the route the launcher ships, not a bare engine launch: the
        # 4,096-token prefill pass, the twelve read-path switches and the
        # 4,096-token MoE workspace tile are part of that route.
        try:
            import sys as _sys
            _root = str(BENCH_DIR.parent)
            if _root not in _sys.path:
                _sys.path.insert(0, _root)
            import slotstream_runtime as _slotstream_runtime
            env.update(_slotstream_runtime.Q8_OPTIMIZATION_ENV)
        except Exception:
            pass  # a bare launch is still a valid (if slower) measurement
    env.update(extra_env or {})
    return Engine(
        name=f"slotstream-{kv}",
        argv=argv,
        env=env,
        port=port,
        model_id="qwen3.8-flash-next:4bit",
        work_dir=work_dir or (RUNS_DIR / f"slotstream-{time.strftime('%H%M%S')}"),
        ready_timeout=2400.0,
        extra={
            "model": str(path), "context": context, "kv": kv,
            "draftDepth": draft_depth, "memoryAuto": memory_auto,
        },
    )


def make_llamacpp(
    model: str | pathlib.Path,
    *,
    port: int = DEFAULT_PORT,
    context: int = 131072,
    kv: str = "q8",
    batch: int = 2048,
    ubatch: int = 512,
    gpu_layers: int = 999,
    flash_attn: str = "on",
    threads: int | None = None,
    alias: str = "bench",
    extra_args: tuple[str, ...] = (),
    extra_env: dict[str, str] | None = None,
    work_dir: pathlib.Path | None = None,
    binary: pathlib.Path | str = LLAMACPP_BIN,
) -> Engine:
    path = _model_path(model)
    cache_type = {"q8": "q8_0", "q4": "q4_0", "off": "f16"}.get(kv, kv)
    argv = [
        str(binary),
        "-m", str(path),
        "-c", str(context),
        "-ctk", cache_type,
        "-ctv", cache_type,
        "-fa", flash_attn,
        "-ngl", str(gpu_layers),
        "-b", str(batch),
        "-ub", str(ubatch),
        "--host", "127.0.0.1",
        "--port", str(port),
        "--jinja",
        "--no-webui",
        "-a", alias,
        *extra_args,
    ]
    if threads:
        argv += ["-t", str(threads)]
    env = {"LLAMA_ARG_NO_WEBUI": "1"}
    env.update(extra_env or {})
    return Engine(
        name=f"llamacpp-{kv}",
        argv=argv,
        env=env,
        port=port,
        model_id=alias,
        work_dir=work_dir or (RUNS_DIR / f"llamacpp-{time.strftime('%H%M%S')}"),
        ready_timeout=1800.0,
        extra={"model": str(path), "context": context, "kv": kv, "batch": batch, "ubatch": ubatch},
    )


# --------------------------------------------------------------------------
# measurement
# --------------------------------------------------------------------------


def stream_chat(
    engine: Engine,
    prompt: str,
    *,
    max_tokens: int = 256,
    temperature: float = 0.0,
    seed: int = 42,
    timeout: float = 7200.0,
    reasoning_effort: str | None = "none",
    extra_body: dict | None = None,
) -> dict:
    body = {
        "model": engine.model_id,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": temperature,
        "seed": seed,
        "max_tokens": max_tokens,
    }
    if reasoning_effort is not None:
        body["reasoning_effort"] = reasoning_effort
    if extra_body:
        body.update(extra_body)
    request = urllib.request.Request(
        f"http://127.0.0.1:{engine.port}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    if engine.api_key:
        request.add_header("Authorization", f"Bearer {engine.api_key}")

    started = time.monotonic()
    first_output: float | None = None
    last_output: float | None = None
    usage: dict | None = None
    timings: dict | None = None
    metrics: list[dict] = []
    content: list[str] = []
    backend = str(engine.extra.get("backend") or engine.name.split("-", 1)[0])
    metadata = ResponseMetrics("chat-completions", "text/event-stream", backend=backend)
    outcome = ResponseOutcome("chat-completions", True)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw in response:
            if not raw.startswith(b"data: "):
                continue
            payload = raw[6:].strip()
            if payload == b"[DONE]":
                break
            event = json.loads(payload)
            emitted_output = metadata.observe_payload(event)
            outcome.inspect(event)
            if "error" in event:
                raise RuntimeError(json.dumps(event["error"]))
            if isinstance(event.get("usage"), dict):
                usage = event["usage"]
            if isinstance(event.get("timings"), dict):
                timings = event["timings"]
            if isinstance(event.get("slotstream_metrics"), dict):
                metrics.append(
                    {"at": time.monotonic() - started, **event["slotstream_metrics"]}
                )
            if emitted_output:
                now = time.monotonic()
                if first_output is None:
                    first_output = now - started
                last_output = now - started
            for choice in event.get("choices", []):
                delta = choice.get("delta") or {}
                piece = (delta.get("content") or "") + (delta.get("reasoning_content") or "")
                if piece:
                    content.append(piece)

    total = time.monotonic() - started
    prompt_tokens = ResponseMetrics._integer((usage or {}).get("prompt_tokens"))
    completion_tokens = ResponseMetrics._integer((usage or {}).get("completion_tokens"))
    details = (usage or {}).get("prompt_tokens_details")
    cached_tokens = ResponseMetrics._integer(details.get("cached_tokens")) if isinstance(details, dict) else None
    if prompt_tokens is None or completion_tokens is None or prompt_tokens < 1 or completion_tokens < 1:
        raise RuntimeError("Benchmark needs authoritative integer token usage; no text/chunk estimates are used")
    if cached_tokens is not None and cached_tokens > prompt_tokens:
        raise RuntimeError("Benchmark cache counters exceed the prompt usage")
    if outcome.result not in {"completed", "truncated"}:
        raise RuntimeError("Benchmark response did not finish with a valid terminal event")
    native = generation_metrics.native_generation_proof(backend, completion_tokens, metadata.public_runtime_stats())
    observed_decode = (
        (completion_tokens - 1) / (last_output - first_output)
        if first_output is not None and last_output is not None and last_output - first_output >= .001
        else None
    )
    selected_decode = native["tokensPerSecond"] if native is not None else observed_decode
    if backend in generation_metrics.BUFFERED_GENERATION_BACKENDS and native is None:
        selected_decode = None
    prompt_processing = metadata.public_runtime_stats().get("promptProcessing")
    result = {
        "promptTokens": prompt_tokens,
        "completionTokens": completion_tokens,
        "cachedPromptTokens": cached_tokens,
        "ttftSeconds": first_output,
        "totalSeconds": total,
        "prefillSeconds": prompt_processing.get("elapsedSeconds") if isinstance(prompt_processing, dict) else None,
        "prefillTokensPerSecond": prompt_processing.get("tokensPerSecond") if isinstance(prompt_processing, dict) else None,
        "decodeSeconds": (
            (last_output - first_output)
            if first_output is not None and last_output is not None
            else None
        ),
        "decodeTokensPerSecond": selected_decode,
        "generationTokensPerSecond": selected_decode,
        "decodeTimingValid": selected_decode is not None,
        "authoritativeUsage": True,
        "responseOutcome": outcome.result,
        "transport": "sse",
        "endToEndTokensPerSecond": completion_tokens / total if total > 0 else None,
        "observedDecodeTokensPerSecond": observed_decode,
        "decodeTimingSource": native["source"] if native is not None else "engine-usage-and-relay-clock" if selected_decode is not None else None,
        "decodeTimingBasis": native["basis"] if native is not None else "client output-event interval estimate" if selected_decode is not None else None,
        "generationProof": native,
        "engineMetrics": metrics,
        "usage": usage,
        "content": "".join(content),
    }
    # Only request-bound metadata validated for this backend is native proof.
    # TTFT divided into prompt tokens includes queue/first-generation work and
    # is deliberately not presented as prefill speed.
    usage = usage or {}
    if native is not None:
        result["nativeDecodeTokensPerSecond"] = native["tokensPerSecond"]
        result["nativeThroughputBasis"] = native["basis"]
    runtime_stats = metadata.public_runtime_stats()
    if runtime_stats.get("runtimeTimeToFirstTokenSeconds") is not None:
        result["nativeTimeToFirstToken"] = runtime_stats["runtimeTimeToFirstTokenSeconds"]
    if isinstance(prompt_processing, dict):
        result["nativePrefillTokensPerSecond"] = prompt_processing["tokensPerSecond"]
        result["nativePrefillBasis"] = prompt_processing.get("basis", "runtime-reported-processed-prompt-timing")
    # llama.cpp publishes per-request timings on the final stream chunk.
    if timings:
        result["engineTimings"] = timings
        predicted = ResponseMetrics._integer(timings.get("predicted_n"))
        elapsed_ms = ResponseMetrics._number(timings.get("predicted_ms"), 604800000, positive=True)
        if backend == "llamacpp" and predicted == completion_tokens and elapsed_ms is not None:
            result["nativeDecodeTokensPerSecond"] = predicted * 1000 / elapsed_ms
            result["decodeTokensPerSecond"] = result["nativeDecodeTokensPerSecond"]
            result["generationTokensPerSecond"] = result["nativeDecodeTokensPerSecond"]
            result["decodeTimingSource"] = "llamacpp-response-timings"
            result["decodeTimingBasis"] = "runtime-reported-request-generation"
            result["nativeThroughputBasis"] = "runtime-reported-request-generation"
        processed = ResponseMetrics._integer(timings.get("prompt_n"))
        prompt_ms = ResponseMetrics._number(timings.get("prompt_ms"), 604800000, positive=True)
        if (backend == "llamacpp" and processed is not None and 0 < processed <= prompt_tokens
                and prompt_ms is not None and (cached_tokens is None or processed + cached_tokens == prompt_tokens)):
            rate = processed * 1000 / prompt_ms
            if rate <= 10_000_000:
                result["nativePrefillTokensPerSecond"] = rate
                result["nativePrefillBasis"] = "runtime-reported-processed-prompt-timing"
    return result


def _native_metrics(metrics: list[dict]) -> dict | None:
    if not metrics:
        return None
    completed = metrics[-1]
    decode_seconds = float(completed.get("decode_seconds") or 0)
    decode_tokens = float(completed.get("decode_tokens") or 0)
    processed = float(completed.get("processed_tokens") or 0)
    prefill_seconds = float(completed.get("prefill_seconds") or 0)
    out = dict(completed)
    if decode_seconds > 0 and decode_tokens > 0:
        out["decode_tokens_per_second"] = decode_tokens / decode_seconds
    if prefill_seconds > 0 and processed > 0:
        out["processed_tokens_per_second"] = processed / prefill_seconds
    return out


def measure(
    engine: Engine,
    prompt_path: pathlib.Path,
    *,
    max_tokens: int = 256,
    warm: bool = False,
    reasoning_effort: str | None = "none",
) -> dict:
    prompt = prompt_path.read_text(encoding="utf-8")
    if warm:
        stream_chat(engine, prompt, max_tokens=8, reasoning_effort=reasoning_effort)
    return stream_chat(
        engine, prompt, max_tokens=max_tokens, reasoning_effort=reasoning_effort,
    )


def write_result(label: str, payload: dict) -> pathlib.Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = RESULTS_DIR / f"{stamp}-{label}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    index = RESULTS_DIR / "index.json"
    entries = json.loads(index.read_text()) if index.exists() else []
    entries.append({"label": label, "file": path.name, "at": stamp})
    index.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return path


@contextlib.contextmanager
def bench_run(purpose: str, minimum_headroom_gb: float = 20.0):
    with BenchLock(purpose):
        foreign = foreign_engine_processes()
        if foreign:
            raise RuntimeError(f"engine processes already running: {foreign}")
        wait_for_headroom(minimum_headroom_gb)
        yield
