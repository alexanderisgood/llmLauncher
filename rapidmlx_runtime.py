"""Passive Rapid MLX discovery and launcher-owned local text serving.

Catalog reads never import MLX, load weights, start a service, or download a
model. The foreground server reuses an existing checkpoint and private key.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
from typing import Any

import rapidmlx_mtp

VERSION = "0.16.9"
SOURCE_COMMIT = "7b3d9527df3d54c27bb5ed7beca5203e3a445abf"
WHEEL_SHA256 = "9ee9bd5c96c70b2f4577e2500d2c5811a8f521666ec4f7a6ac192b19d33bb8be"
SOURCE_URL = "https://github.com/raullenchai/Rapid-MLX"
CONTEXTS = (8_192, 16_384, 32_768, 65_536, 131_072, 262_144, 524_288, 1_048_576)
SAMPLING_FIELDS = ["temperature", "top_p", "top_k", "presence_penalty", "frequency_penalty", "repetition_penalty", "seed"]


def _identity(path: Path) -> tuple[Any, ...]:
    value = path.stat()
    if not stat.S_ISREG(value.st_mode):
        raise ValueError("Rapid MLX requires regular runtime and model files")
    return (str(path.resolve()), value.st_dev, value.st_ino, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns)


def _json(path: Path) -> dict[str, Any]:
    if not 2 <= path.stat().st_size <= 8 * 1024**2:
        raise ValueError("Rapid MLX model metadata is incomplete or oversized")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Rapid MLX metadata must be an object")
    return value


def inspect_runtime(binary: str | Path | None = None) -> dict[str, Any] | None:
    if not binary:
        return None
    try:
        executable = Path(binary).expanduser().resolve(strict=True)
        if not os.access(executable, os.X_OK):
            return None
        prefix = executable.parent.parent
        sites = list(prefix.glob("lib/python*/site-packages"))
        # Homebrew can retain a small bin wrapper in front of libexec.
        sites.extend(prefix.glob("libexec/lib/python*/site-packages"))
        package = next((site / "rapid_mlx" for site in sites if (site / "rapid_mlx/cli_parser.py").is_file()), None)
        if package is None:
            return None
        metadata = next(package.parent.glob("rapid_mlx-*.dist-info/METADATA"), None)
        if metadata is None:
            return None
        match = re.search(r"^Version: ([^\r\n]+)$", metadata.read_text(encoding="utf-8"), re.MULTILINE)
        version = match.group(1).strip() if match else "unknown"
        python_root = package.parent.parent.parent.parent
        python = next((python_root / "bin" / name for name in ("python", "python3")
                       if (python_root / "bin" / name).is_file()), None)
        model_files = sorted((package.parent / "mlx_lm/models").glob("*.py"))
        vendor_files = sorted((package / "models").glob("*.py"))
        model_types = sorted({path.stem for path in (*model_files, *vendor_files) if not path.stem.startswith("_")})
        tracked = [executable, metadata, package / "cli_parser.py", package / "server.py", *model_files, *vendor_files]
        stamps = [_identity(path) for path in tracked]
        identity = hashlib.sha256(json.dumps(stamps).encode()).hexdigest()
        ready = version == VERSION and python is not None and os.access(python, os.X_OK) and bool(model_files)
        return {"binary": str(executable), "python": str(python) if python else None,
                "version": version, "ready": ready, "identity": identity, "modelTypes": model_types,
                "reason": f"Rapid MLX {version} local runtime" if ready else f"Install Rapid MLX {VERSION} in an isolated Python environment"}
    except (OSError, ValueError, StopIteration):
        return None


def inspect_model(path: str | Path) -> dict[str, Any] | None:
    try:
        root = Path(path).expanduser().resolve(strict=True)
        config = _json(root / "config.json")
        text = config.get("text_config") if isinstance(config.get("text_config"), dict) else config
        if config.get("model_file") or text.get("model_file"):
            return None  # Native model code overrides need a separate adapter.
        model_type = str(config.get("model_type") or text.get("model_type") or "")
        index_path = root / "model.safetensors.index.json"
        weight_map = None
        if index_path.is_file():
            weight_map = _json(index_path).get("weight_map", {})
            names = set(weight_map.values())
            if (not names or len(names) > 1_024 or any(not isinstance(name, str)
                    or Path(name).is_absolute() or ".." in Path(name).parts for name in names)):
                return None
            # MLX loads the native glob, not just the index's weight_map. Do
            # not let an unindexed shard replace tensors after cataloging.
            if names != {path.name for path in root.glob("model*.safetensors")}:
                return None
            weights = [root / name for name in sorted(names)]
        else:
            weights = sorted(root.glob("model*.safetensors"))
        if not weights or len(weights) > 1_024:
            return None
        # A safetensors header is at least eight bytes. The catalog separately
        # verifies tensor/header completeness; launch rebinds these identities.
        if any(path.stat().st_size <= 8 or not path.is_file() for path in weights):
            return None
        tokenizers = [root / name for name in ("tokenizer.json", "tokenizer.model") if (root / name).is_file()]
        if not tokenizers:
            return None
        files = [root / "config.json", *tokenizers, *weights]
        files.extend(root / name for name in ("tokenizer_config.json", "generation_config.json", "chat_template.jinja", "model.safetensors.index.json") if (root / name).is_file())
        mtp = rapidmlx_mtp.inspect_mtp(root, config, weight_map)
        files.extend(Path(path) for path in mtp.get("files", []))
        native = int(text.get("max_position_embeddings") or config.get("max_position_embeddings") or 32_768)
        stamps = [_identity(path) for path in files]
        sidecar_files = {Path(path) for path in mtp.get("files", []) if str(path).endswith(".safetensors")} - set(weights)
        return {"path": str(root), "modelType": model_type, "nativeContext": native, "mtp": mtp,
                "weightBytes": sum(path.stat().st_size for path in weights),
                "mtpSidecarBytes": sum(path.stat().st_size for path in sidecar_files),
                "identity": hashlib.sha256(json.dumps(stamps).encode()).hexdigest()}
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def capability(record: dict[str, Any], runtime: dict[str, Any] | None) -> dict[str, Any]:
    # Origin/engine labels are presentation metadata. Inspect the actual local
    # checkpoint, including a compatible copy discovered by another adapter.
    eligible = record.get("ready") is True and Path(str(record.get("path") or "")).is_dir()
    model = inspect_model(record["path"]) if eligible else None
    supported = bool(model and runtime and model["modelType"] in runtime.get("modelTypes", []))
    host = platform.system() == "Darwin" and platform.machine() == "arm64"
    ready = supported and host and runtime.get("ready") is True
    maximum = model["nativeContext"] if model else int(record.get("nativeContext") or 32_768)
    mtp = (model or {}).get("mtp") or {}
    has_mtp = bool(ready and mtp.get("supported") is True)
    reason = ("Install Rapid MLX to run local MLX checkpoints" if not runtime else
              str(runtime.get("reason")) if not runtime.get("ready") else
              "Rapid MLX requires Apple silicon" if not host else
              "This copy is GGUF. Rapid MLX needs an MLX safetensors copy of the same model" if not model and "gguf" in str(record.get("format") or "").lower() else
              "Choose a complete local MLX checkpoint supported by this Rapid MLX runtime" if not supported else
              "Ready for Rapid MLX · local text, reasoning and function tools")
    return {"runnable": bool(ready), "reason": reason, "modelPath": (model or {}).get("path"),
            "runtimeIdentity": runtime, "modelIdentity": (model or {}).get("identity"),
            "nativeWeightBytes": (model or {}).get("weightBytes"), "mtpSidecarBytes": (model or {}).get("mtpSidecarBytes", 0),
            "nativeContext": maximum,
            "runtimeVersion": f"Rapid MLX {runtime['version']}" if runtime else "Not installed",
            "benchmarkModelFingerprint": (model or {}).get("identity"),
            "mtp": has_mtp, "mtpReason": mtp.get("reason") or "No native MTP head is installed for this checkpoint",
            "dflash": False, "kv": False, "kvChoices": ["off"], "preferredAcceleration": "mtp" if has_mtp else "off",
            "fallbackAcceleration": "mtp" if has_mtp else "off", "depth": int(mtp.get("depth") or 1) if has_mtp else 1,
            "depthMax": int(mtp.get("depthMax") or 1) if has_mtp else 1,
            "depthChoices": mtp.get("depthChoices") if has_mtp else [1],
            "agentReasoning": ["auto", "off"], "codexReasoning": ["auto", "off"],
            "contextWindows": [value for value in CONTEXTS if value <= maximum], "contextMaximum": maximum,
            "outputMaximum": maximum - 1_024, "customSampling": True, "samplingFields": list(SAMPLING_FIELDS),
            # Native Responses carries four sampler fields. The other three
            # model defaults are fixed on the server command at every launch.
            "implicitSamplingDefaultsVerified": bool(ready), "localBenchmark": None, "localBenchmarks": [], "benchmarkHistoryCount": 0}


def validate_route(binary: str | None, record: dict[str, Any], cap: dict[str, Any], context: int, output: int) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime = inspect_runtime(binary)
    model = inspect_model(record["path"])
    if (not runtime or not runtime.get("ready") or runtime != cap.get("runtimeIdentity")
            or not model or model.get("identity") != cap.get("modelIdentity") or cap.get("runnable") is not True):
        raise ValueError("Rapid MLX or its model changed after scanning. Rescan before launching.")
    if type(context) is not int or not 1_024 <= context <= min(model["nativeContext"], int(cap.get("contextMaximum") or 0)):
        raise ValueError("Choose a Rapid MLX context within the model's native window")
    if type(output) is not int or not 256 <= output <= context - 1_024:
        raise ValueError("Rapid MLX Max response must leave at least 1,024 tokens for the prompt")
    return runtime, model


def server_arguments(runtime: dict[str, Any], model: dict[str, Any], *, port: int, served_id: str, context: int, output: int, reasoning: str, sampling: dict[str, Any] | None = None, options: dict[str, Any] | None = None) -> list[str]:
    if type(port) is not int or not 1 <= port <= 65_535:
        raise ValueError("Rapid MLX needs a private local port")
    if reasoning not in {"auto", "off"}:
        raise ValueError("Choose Auto or Off for Rapid MLX reasoning")
    argv = [runtime["binary"], "serve", model["path"], "--host", "127.0.0.1", "--port", str(port),
            "--served-model-name", served_id, "--context-length", str(context), "--max-tokens", str(output),
            "--disable-model-downloads", "--disable-disk-caches", "--max-num-seqs", "1",
            "--max-concurrent-requests", "1", "--kv-cache-dtype", "bf16", "--text-only"]
    mtp = model.get("mtp") or {}
    acceleration = str((options or {}).get("acceleration") or "auto")
    if acceleration == "mtp" or (acceleration == "auto" and mtp.get("supported") is True):
        if mtp.get("supported") is not True:
            raise ValueError(mtp.get("reason") or "This Rapid MLX checkpoint has no native MTP head")
        depth = int((options or {}).get("depth") or mtp.get("depth") or 1)
        if depth not in (mtp.get("depthChoices") or range(1, int(mtp.get("depthMax") or 1) + 1)):
            raise ValueError("Choose a supported Rapid MLX MTP depth")
        argv.extend(["--speculative-config", json.dumps({"method": "mtp", "model": mtp["sidecarPath"],
            "num_speculative_tokens": depth, "disable_auto_k": False}, separators=(",", ":"))])
    else:
        argv.append("--no-spec-decode")
    for name, neutral in (("presence_penalty", 0.0), ("frequency_penalty", 0.0), ("repetition_penalty", 1.0)):
        argv.extend(["--default-" + name.replace("_", "-"), str((sampling or {}).get(name, neutral))])
    if reasoning == "off":
        argv.append("--no-thinking")
    return argv


def clean_environment(environment: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in environment.items()
            if not key.startswith(("DYLD_", "RAPID_MLX_")) and key not in {"PYTHONPATH", "PYTHONHOME"}}


def server_environment(api_key: str, output: int) -> dict[str, str]:
    return {"RAPID_MLX_API_KEY": api_key, "RAPID_MLX_MAX_GENERATION_TOKENS": str(output),
            "RAPID_MLX_TELEMETRY": "0", "RAPID_MLX_DISABLE_VERSION_CHECK": "1", "RAPID_MLX_NO_BANNER": "1",
            "HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1", "TRANSFORMERS_OFFLINE": "1"}


def validate_ready(health: Any, catalog: Any, served_id: str) -> None:
    if not isinstance(health, dict) or health.get("ready") is not True or health.get("model_loaded") is not True:
        raise ValueError("Rapid MLX is still loading or warming its kernels")
    if not isinstance(catalog, dict) or served_id not in [item.get("id") for item in catalog.get("data", []) if isinstance(item, dict)]:
        raise ValueError("Rapid MLX did not publish the selected model")
