"""Pinned, launcher-owned Whallm route. Importing this module never imports MLX."""
from __future__ import annotations

import argparse
import copy
import functools
import hashlib
import json
import os
import plistlib
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

VERSION = "1.1.4"
TEAM_ID = "Y366CJ66L6"
APP_CDHASH = "daa028934745e1ef84d8db8ca20f352d741315f9"
MODEL_ID = "Qwen/Qwen3.8-Flash-Next-FP8"
SERVED_ID = "qwen3.8-flash-next-fp8"
MODEL_REVISION = "bcd9f01ddc9cff2316eb84281bebcd5b058bddce"
MANIFEST_SHA256 = "3f4cb52a88335591cfb8233778eb56396e9d2756c153485e4dcfb0a12daed0ce"
CONTEXTS = (16_384,)
OUTPUT = 4_096
SLOTS = 4_096
MEMORY_GIB = 40
MEMORY_BYTES = MEMORY_GIB * 1024**3
PROMPT_CACHE_GIB = 2
WORKING_SET_BYTES = 26 * 1024**3
_RUNTIME_FILES = (
    "Contents/Info.plist", "Contents/_CodeSignature/CodeResources",
    "Contents/MacOS/dsv4-app", "Contents/MacOS/python3",
    "Contents/Frameworks/libWhallmANE.dylib",
    "Contents/Resources/runtime/deepseek_v4_ssd/server.py",
    "Contents/Resources/runtime/deepseek_v4_ssd/generation.py",
    "Contents/Resources/runtime/deepseek_v4_ssd/model.py",
    "Contents/Resources/runtime/deepseek_v4_ssd/manifest.py",
)


def _identity(path: Path) -> tuple[Any, ...]:
    info = path.stat()
    return (str(path.resolve()), info.st_dev, info.st_ino, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def verify_signature(app: Path) -> None:
    """Require the exact audited signed app, including its sealed Python sources."""
    result = subprocess.run(
        ["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)],
        capture_output=True, text=True, timeout=60, check=False,
    )
    if result.returncode:
        raise ValueError("Whallm's app signature could not be verified. Reinstall the signed 1.1.4 release.")
    result = subprocess.run(
        ["/usr/bin/codesign", "-d", "--verbose=4", str(app)],
        capture_output=True, text=True, timeout=10, check=False,
    )
    identity = dict(line.split("=", 1) for line in (result.stdout + result.stderr).splitlines() if "=" in line)
    if (result.returncode or identity.get("TeamIdentifier") != TEAM_ID
            or identity.get("CDHash") != APP_CDHASH
            or identity.get("Identifier") != "com.deepseekv4ssd.app"):
        raise ValueError("Whallm's signed runtime identity differs from the audited 1.1.4 release.")


@functools.lru_cache(maxsize=4)
def _cached_signature(app: str, identities: tuple[tuple[Any, ...], ...]) -> None:
    verify_signature(Path(app))


def inspect_install(binary: str | None, model_path: str | Path | None = None, *, fresh: bool = False) -> dict[str, Any]:
    """Read pinned metadata and stat all weights; never hash/load 125 GB of tensors."""
    if not binary:
        raise ValueError("Whallm 1.1.4 is not installed.")
    executable = Path(binary).expanduser().resolve(strict=True)
    app = executable.parent.parent.parent
    if executable.name != "dsv4-app" or app.name != "Whallm.app":
        raise ValueError("Choose the signed Whallm 1.1.4 app runtime.")
    with (app / "Contents/Info.plist").open("rb") as handle:
        info = plistlib.load(handle)
    if info.get("CFBundleShortVersionString") != VERSION or info.get("CFBundleIdentifier") != "com.deepseekv4ssd.app":
        raise ValueError("Native Whallm requires the audited 1.1.4 app.")
    runtime_files = tuple(_identity(app / name) for name in _RUNTIME_FILES)
    if fresh:
        verify_signature(app)
    else:
        _cached_signature(str(app), runtime_files)
    python = app / "Contents/MacOS/python3"
    if not os.access(python, os.X_OK):
        raise ValueError("Whallm's bundled Python executable is missing.")
    root = Path(model_path or Path.home() / ".dsmodel/qwen3.8-flash-next.dsv4").expanduser().resolve(strict=True)
    manifest_path = root / "manifest.json"
    if manifest_path.stat().st_size > 1024**2:
        raise ValueError("Whallm's installed manifest is oversized.")
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Whallm's installed model does not match the pinned full-expert manifest.")
    manifest = json.loads(raw)
    expected = {"modelID": MODEL_ID, "revision": MODEL_REVISION, "formatVersion": 2,
                "modelKind": "qwen3.8-flash-next", "expertCount": 512,
                "selectedExpertCount": 10, "layerCount": 48, "expertBlobSize": 2_611_200}
    if any(manifest.get(key) != value for key, value in expected.items()) or manifest.get("mtp"):
        raise ValueError("Whallm's manifest does not describe the pinned 48-layer, 512-expert Qwen model.")
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != 57:
        raise ValueError("Whallm's installed model file inventory is incomplete.")
    names: set[str] = set()
    size = 0
    file_identities = []
    for entry in files:
        name, expected_size = entry.get("path"), entry.get("size")
        if not isinstance(name, str) or name in names or not isinstance(expected_size, int) or expected_size < 1:
            raise ValueError("Whallm's installed file inventory is invalid.")
        names.add(name)
        target = (root / name).resolve(strict=True)
        if root not in target.parents or not target.is_file() or target.stat().st_size != expected_size:
            raise ValueError(f"Whallm's installed file is missing, unsafe, or incomplete: {name}")
        file_identities.append(_identity(target))
        size += expected_size
    required = {"common.bin", "ngram.bin", "config.json", "generation_config.json"}
    required.update(f"experts/layer_{layer:02d}.bin" for layer in range(48))
    if not required.issubset(names):
        raise ValueError("Whallm's full-expert install is incomplete.")
    runtime_fingerprint = hashlib.sha256(json.dumps(runtime_files, separators=(",", ":")).encode()).hexdigest()
    artifact_fingerprint = hashlib.sha256(json.dumps(file_identities, separators=(",", ":")).encode()).hexdigest()
    return {"app": str(app), "binary": str(executable), "python": str(python),
            "runtimePath": str(app / "Contents/Resources/runtime"),
            "sitePackages": str(app / "Contents/Resources/python/site-packages"),
            "runtimeVersion": f"Whallm {VERSION}", "runtimeIdentity": runtime_fingerprint,
            "modelPath": str(root), "manifestSHA256": MANIFEST_SHA256,
            "artifactIdentity": artifact_fingerprint,
            "weightBytes": size, "commonBytes": next(entry["size"] for entry in files if entry["path"] == "common.bin")}


def discover(binary: str | None) -> dict[str, Any] | None:
    try:
        return inspect_install(binary)
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        return None


def model_record(install: dict[str, Any], engines: list[tuple[str, str]], installed_memory: int) -> dict[str, Any]:
    comparison = hashlib.sha256(f"ssd-source-v1\0{MODEL_ID.lower()}\0revision\0{MODEL_REVISION}".encode()).hexdigest()
    fingerprint = hashlib.sha256(f"{MANIFEST_SHA256}\0{install['artifactIdentity']}\0{install['runtimeIdentity']}\0native-v1".encode()).hexdigest()
    profile = {
        "version": 1, "candidate": True, "recommended": True, "moe": True,
        "oversized": True, "qwen38FlashNext": True, "expertCount": 512, "nativeExpertTopK": 10,
        "weightBytes": install["weightBytes"], "installedMemoryBytes": installed_memory,
        "weightToMemoryRatio": round(install["weightBytes"] / installed_memory, 4) if installed_memory else None,
        "format": "whallm-mxfp4", "reason": "Installed full-expert model; launched and unloaded by LLM Launcher.",
        "sourceContract": {"sourceModel": MODEL_ID.lower(), "proofKind": "revision", "proof": MODEL_REVISION,
                           "comparisonIdentity": comparison, "verifiedForCrossFormatComparison": True},
        "comparisonIdentity": comparison, "crossFormatComparisonReady": True,
        "calibration": {"suite": "agentic", "engines": ["whallm"], "freshProcessPerEngine": True,
                        "coldAndWarmStages": True, "nativeExpertRoutingRequired": True,
                        "metrics": ["generationTps", "ttft", "peakMemory", "thermalState", "prefixReuse"]},
    }
    backends = {}
    for engine, label in engines:
        native = engine == "whallm"
        cap = {"runnable": native, "reason": "Full Qwen experts · automatic local launch · 16K context" if native else f"This pinned install cannot run in {label}.",
               "mtp": False, "mtpReason": "This installed model has no verified MTP sidecar.",
               "dflash": False, "dflashVersion": None, "dflashReason": "Whallm uses its native full-expert route.",
               "kv": False, "preferredAcceleration": "off", "fallbackAcceleration": "off", "depth": 1, "depthMax": 1,
               "agentReasoning": ["auto", "low", "medium", "high", "xhigh", "max"] if native else ["auto"],
               "codexReasoning": ["auto", "low", "medium", "high", "xhigh", "max"] if native else ["auto"],
               "runtimeVersion": install["runtimeVersion"] if native else "Not applicable",
               "benchmarkModelFingerprint": fingerprint, "localBenchmark": None, "localBenchmarks": [], "benchmarkHistoryCount": 0}
        if native:
            cap.update({"ssdStreaming": True, "ssdProfile": copy.deepcopy(profile), "comparisonIdentity": comparison,
                        "exactExpertRouting": True, "remote": False, "sharedServer": False, "nativeWhallm": True,
                        "contextWindows": list(CONTEXTS), "contextMaximum": max(CONTEXTS), "outputMaximum": OUTPUT,
                        "customSampling": False, "samplingReason": "Use the native model's thinking defaults.",
                        "clientSupport": {"codex": {"supported": False,
                            "reason": "Use Pi for this native route. Whallm's Responses tool streaming and completion status need a separate Codex qualification."}},
                        "memoryCeilingBytes": MEMORY_BYTES, "whallmSlots": SLOTS})
        backends[engine] = cap
    return {"id": "whallm-native-" + MANIFEST_SHA256[:24], "name": "Qwen3.8 Flash-Next · Whallm full experts",
            "path": install["modelPath"], "artifact": "whallm:" + MANIFEST_SHA256[:24],
            "origins": ["Whallm · installed locally"], "format": "Whallm MXFP4 + SSD",
            "architecture": "Qwen4Exp · 512 experts", "modelType": "whallm-qwen38-flash-next",
            "nativeContext": max(CONTEXTS), "architectureNativeContext": 262_144, "defaultOutput": OUTPUT, "outputMaximum": OUTPUT,
            "defaultReasoning": "medium", "quantization": "MXFP4 experts · FP8 n-gram",
            "size": install["weightBytes"], "sizeLabel": f"{install['weightBytes'] / 1024**3:.1f} GiB",
            "memoryGeometry": {"ready": True, "nativeWhallm": True}, "mtpSidecarSize": 0,
            "ready": True, "status": "Installed", "mtp": {"declared": False, "integrated": False, "sidecar": False},
            "templateReasoningEfforts": ["low", "medium", "xhigh"], "defaultSampling": {},
            "lmKey": SERVED_ID, "remoteModelId": SERVED_ID, "sharedServer": False, "remote": False,
            "nativeWhallm": copy.deepcopy(install), "ssdStreaming": profile, "backends": backends}


def launch_config(install: dict[str, Any], *, port: int, context: int, output: int, cache_directory: Path) -> dict[str, Any]:
    if context not in CONTEXTS or not 256 <= output <= OUTPUT or output >= context:
        raise ValueError("This native Whallm route requires 16K context and at most 4K response tokens.")
    if not 1024 <= port <= 65535 or port == 11434:
        raise ValueError("Native Whallm requires a private launcher port.")
    return {"version": 1, "install": copy.deepcopy(install), "port": port,
            "context": context, "output": output, "slots": SLOTS,
            "memoryGiB": MEMORY_GIB, "promptCacheGiB": PROMPT_CACHE_GIB,
            "cacheDirectory": str(cache_directory.resolve())}


def validate_config(config: dict[str, Any]) -> None:
    if (config.get("version") != 1 or config.get("context") not in CONTEXTS
            or config.get("slots") != SLOTS or config.get("memoryGiB") != MEMORY_GIB
            or config.get("promptCacheGiB") != PROMPT_CACHE_GIB):
        raise ValueError("Native Whallm's fixed execution and memory contract changed.")
    launch_config(config["install"], port=config["port"], context=config["context"],
                  output=config["output"], cache_directory=Path(config["cacheDirectory"]))


def runtime_argv(config: dict[str, Any]) -> list[str]:
    validate_config(config)
    return ["whallm-owned", "--model", config["install"]["modelPath"], "--host", "127.0.0.1",
            "--port", str(config["port"]), "--public-model", SERVED_ID,
            "--slots", str(SLOTS), "--read-workers", "4", "--prefetch-read-workers", "2",
            "--memory-limit-gib", str(MEMORY_GIB), "--prompt-cache-memory-gib", str(PROMPT_CACHE_GIB),
            "--prompt-cache-entries", "2", "--ane-prefill-ratio", "0.25",
            "--prompt-cache-directory", config["cacheDirectory"], "--default-max-tokens", str(config["output"])]


def matched_cached_tokens(metrics: dict[str, Any], prompt: int, completion: int) -> int | None:
    values = [metrics.get(key) for key in ("runtime_prompt_tokens", "runtime_generation_tokens", "prompt_cache_reused_tokens")]
    if (any(not isinstance(value, int) or isinstance(value, bool) for value in values)
            or values[0] != prompt or values[1] != completion or not 0 <= values[2] <= prompt):
        return None
    return values[2]


def install_native_contract(server: Any, installed_model: Any, config: dict[str, Any], runtime_type: Any) -> None:
    """Bound native context and enrich native usage; leave generation/parsing intact."""
    open_model = installed_model.open
    selected = Path(config["install"]["modelPath"]).resolve()

    def bounded_open(cls: Any, path: Any) -> Any:
        if Path(path).expanduser().resolve() != selected:
            raise ValueError("This launcher process owns only its selected Whallm model.")
        return replace(open_model(path), maximum_context=config["context"])

    installed_model.open = classmethod(bounded_open)
    original_stream = runtime_type.stream

    def bounded_stream(self: Any, prompt: str, options: Any) -> Any:
        # Validate eagerly, before the native handler sends SSE headers or
        # allocates a KV cache. Native stream() is otherwise a lazy generator.
        prompt_tokens = len(self._encode_prompt(prompt))
        if prompt_tokens >= config["context"]:
            raise server.APIError("Prompt exceeds this launcher's context limit; compact the conversation.",
                                  status=400, code="context_length_exceeded", param="messages")
        return original_stream(self, prompt, replace(options, max_tokens=min(options.max_tokens, config["output"], config["context"] - prompt_tokens)))

    runtime_type.stream = bounded_stream
    original_validated_pieces = server.OpenAIHandler._validated_response_pieces

    def validated_pieces(self: Any, runtime: Any, prompt: str, *args: Any, **kwargs: Any) -> Any:
        # Required-tool Responses adds another lazy iterator around stream().
        # Reject its oversized initial prompt before that handler sends HTTP 200.
        if len(runtime._encode_prompt(prompt)) >= config["context"]:
            raise server.APIError("Prompt exceeds this launcher's context limit; compact the conversation.",
                                  status=400, code="context_length_exceeded", param="messages")
        return original_validated_pieces(self, runtime, prompt, *args, **kwargs)

    server.OpenAIHandler._validated_response_pieces = validated_pieces
    original_options = server._options

    def options(*args: Any, **kwargs: Any) -> Any:
        value = original_options(*args, **kwargs)
        return replace(value, max_tokens=min(value.max_tokens, config["output"]))

    server._options = options

    def fixed_configuration(self: Any, value: Any) -> None:
        raise server.APIError("This runtime configuration is owned by LLM Launcher.", param="configuration")

    server.ModelManager._configure = fixed_configuration
    original_catalog = server.ModelManager.codex_models

    def codex_models(self: Any) -> Any:
        records = original_catalog(self)
        for record in records:
            record["context_window"] = config["context"]
            record["max_context_window"] = config["context"]
        return records

    server.ModelManager.codex_models = codex_models
    active = threading.local()
    for name in ("_chat", "_responses", "_completion"):
        original = getattr(server.OpenAIHandler, name)

        def handler(self: Any, payload: Any, model: Any, _original: Any = original) -> Any:
            active.runtime = model.runtime
            try:
                return _original(self, payload, model)
            finally:
                active.runtime = None

        setattr(server.OpenAIHandler, name, handler)
    for name, details_key in (("_usage", "prompt_tokens_details"), ("_response_usage", "input_tokens_details")):
        original_usage = getattr(server, name)

        def usage(prompt: int, completion: int, _original: Any = original_usage, _details: str = details_key) -> dict[str, Any]:
            result = _original(prompt, completion)
            runtime = getattr(active, "runtime", None)
            if runtime is not None:
                cached = matched_cached_tokens(runtime.metrics.snapshot(), prompt, completion)
                if cached is not None:
                    result[_details] = {**result.get(_details, {}), "cached_tokens": cached}
            return result

        setattr(server, name, usage)
    original_reasoning = server._reasoning_settings

    def reasoning(payload: dict[str, Any], *, responses_api: bool = False, qwen: bool = False) -> Any:
        if qwen:
            payload = copy.deepcopy(payload)
            if responses_api and payload.get("reasoning") is not None and not isinstance(payload["reasoning"], dict):
                return original_reasoning(payload, responses_api=responses_api, qwen=qwen)
            effort = (payload.get("reasoning") or {}).get("effort") if responses_api else payload.get("reasoning_effort")
            if effort == "none" or payload.get("thinking_mode") == "chat":
                raise server.APIError("Thinking stays enabled on this launcher route.", param="reasoning_effort")
            if not effort:
                if responses_api:
                    payload["reasoning"] = {**(payload.get("reasoning") or {}), "effort": "medium"}
                else:
                    payload["reasoning_effort"] = "medium"
            payload["thinking_mode"] = "thinking"
        return original_reasoning(payload, responses_api=responses_api, qwen=qwen)

    server._reasoning_settings = reasoning


def ready_status(value: Any, config: dict[str, Any]) -> bool:
    if not isinstance(value, dict) or value.get("loaded_model") != SERVED_ID or value.get("loading_model"):
        return False
    runtime = value.get("runtime") or {}
    contract = value.get("launcher_contract") or {}
    return (value.get("model_path") == config["install"]["modelPath"]
            and runtime.get("slots") == SLOTS and runtime.get("read_workers") == 4
            and runtime.get("prompt_cache_memory_gib") == PROMPT_CACHE_GIB
            and runtime.get("ane_prefill_ratio") == 0.25 and runtime.get("mtp_enabled") is False
            and contract == {"context": config["context"], "output": config["output"], "memoryGiB": MEMORY_GIB,
                             "manifestSHA256": MANIFEST_SHA256, "runtimeIdentity": config["install"]["runtimeIdentity"]})


def wait_ready(config: dict[str, Any], key: str, cancelled: threading.Event,
               alive: Callable[[], bool], *, timeout: float = 900) -> None:
    """Start one native load, then require actual residency and the owned contract."""
    deadline = time.monotonic() + timeout
    endpoint = f"http://127.0.0.1:{config['port']}"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    load_started = False
    load_done = threading.Event()
    load_errors: list[str] = []

    def load() -> None:
        request = urllib.request.Request(endpoint + "/api/models/load",
            data=json.dumps({"model": SERVED_ID}).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=max(1, deadline - time.monotonic())) as response:
                if response.status != 200:
                    raise ValueError("Whallm rejected the selected model load.")
                response.read(256 * 1024 + 1)
        except (OSError, ValueError, urllib.error.URLError) as error:
            load_errors.append(str(error))
        finally:
            load_done.set()

    while time.monotonic() < deadline:
        if cancelled.is_set():
            raise InterruptedError("Whallm launch cancelled.")
        if not alive():
            raise RuntimeError("Whallm exited while loading the selected model.")
        if load_done.is_set() and load_errors:
            raise RuntimeError("Whallm could not load the selected model: " + load_errors[0][:500])
        try:
            request = urllib.request.Request(endpoint + "/api/status", headers=headers)
            with urllib.request.urlopen(request, timeout=2) as response:
                data = response.read(256 * 1024 + 1)
            if len(data) > 256 * 1024:
                raise ValueError("Whallm status is oversized.")
            value = json.loads(data)
            if ready_status(value, config):
                return
            if not load_started:
                threading.Thread(target=load, daemon=True).start()
                load_started = True
            elif load_done.is_set():
                raise RuntimeError("Whallm loaded a model that does not match the launcher's bounded route.")
        except (OSError, ValueError, urllib.error.URLError):
            pass
        cancelled.wait(0.2)
    raise RuntimeError("Timed out loading Whallm's selected model.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Launcher-owned Whallm runtime")
    parser.add_argument("config")
    args = parser.parse_args()
    path = Path(args.config)
    if path.stat().st_size > 32 * 1024:
        raise ValueError("Whallm launch configuration is oversized.")
    config = json.loads(path.read_text())
    validate_config(config)
    expected = config["install"]
    actual = inspect_install(expected["binary"], expected["modelPath"], fresh=True)
    if actual != expected:
        raise ValueError("Whallm's runtime or model changed after launch planning. Rescan and retry.")
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise ValueError("Whallm's private API key is missing.")
    # -I -S keeps Homebrew sitecustomize and project modules out of this child.
    sys.path[:0] = [actual["runtimePath"], actual["sitePackages"]]
    os.environ["WHALLM_ANE_BRIDGE"] = str(Path(actual["app"]) / "Contents/Frameworks/libWhallmANE.dylib")
    from deepseek_v4_ssd import server
    from deepseek_v4_ssd.manifest import InstalledModel
    from deepseek_v4_ssd.generation import ModelRuntime
    install_native_contract(server, InstalledModel, config, ModelRuntime)
    original_status = server.OpenAIHandler._status

    def status(self: Any) -> dict[str, Any]:
        return {**original_status(self), "launcher_contract": {
            "context": config["context"], "output": config["output"], "memoryGiB": MEMORY_GIB,
            "manifestSHA256": MANIFEST_SHA256, "runtimeIdentity": actual["runtimeIdentity"]}}

    server.OpenAIHandler._status = status
    sys.argv = runtime_argv(config)
    server.main()


if __name__ == "__main__":
    main()
