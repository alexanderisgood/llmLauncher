"""Rec/Flint discovery and private foreground serving without importing MLX.

The official CLI verifies its embedded runtime and pinned model payloads. This
adapter inspects metadata/headers only, reuses those installed weights, and
isolates the server's authentication and lifecycle from other Rec sessions.
"""
from __future__ import annotations

import copy
import functools
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
from typing import Any

# ``-I`` deliberately excludes the script directory. Add only this trusted
# application directory so the isolated launch wrapper can read local headers.
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import tensor_inventory

VERSION = "0.1.0"
CLI_SHA256 = "22f08e8505e5ace84475c23eefffd116b4b201ad7e796aaea76d223f0e3862de"
CLI_BYTES = 276_603_858
SOURCE_COMMIT = "e53663b262af4cb1ca498e596ca8b1a2d79e0800"
MODEL_REPO = "RecursiveSI/flint-int4"
MODEL_REVISION = "3b93f9053b530488405ae9fca51d4900d6ce21f0"
MODEL_CACHE_KEY = "fdc85248ad77a0fa9fbf0abda8b1525bea8ee74c11ada2ec95eb66113353d677"
MODEL_ID = "flint"
CONTEXTS = (8_192, 16_384, 32_768, 65_536, 131_072, 262_144)
CONTEXT_MAXIMUM = 262_144
DEFAULT_CONTEXT = 32_768
DEFAULT_OUTPUT = 8_192
OUTPUT_MAXIMUM = CONTEXT_MAXIMUM - 1_024
MINIMUM_MEMORY_BYTES = 48 * 1024**3
SUPPORTED_CHIPS = ("Apple M4 Pro", "Apple M5 Pro", "Apple M5 Max")
RUNTIME_RESERVE_BYTES = 2 * 1024**3
RUN_ALIAS_PARENT = Path("/tmp") / f"llmr-{os.getuid()}"
SAMPLING_FIELDS = ["temperature", "top_p", "top_k", "presence_penalty", "seed"]
DEFAULT_SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20,
                    "presence_penalty": 0.0, "frequency_penalty": 0.0, "repetition_penalty": 1.0}
MODEL_FILES = (
    ("chat_template.jinja", 2328, "7940f4ffa3275c36caa4a582f845aaad79da11018b3961e8fbcad6ae29733466"),
    ("config.json", 3082, "80f577a984db1bd40dfff88457b611d4c13e807704a945616be27f28809eed21"),
    ("generation_config.json", 202, "a499c71895e008abd572558a5ad5904feaed92cf2a3b6e2cb0e9cabf03b96ed3"),
    ("model-00000.safetensors", 4745746152, "1a362742a0136c95ed751e2c56d83e63d4ed9ac674984b23b368f105d16cfe7a"),
    ("model-00001.safetensors", 4682022280, "12979140fa019042ff5cdec4c0237cc87db13b56428ce7fe093dd9d33893ea32"),
    ("model-00002.safetensors", 4682022280, "01805c6b882fdec008b0184ec68e7516102205b521e63ca5126f9d52b9aed87b"),
    ("model-00003.safetensors", 4682022280, "9380ed032d90e0ff566d49672faf292f354b3b0e7320820c150eeed8c75e9d42"),
    ("model-00004.safetensors", 3777099608, "c1ba12d2c2a80feb5e554554a01cfde2b71c2638e27fc0ee597b4121399eff99"),
    ("special_tokens_map.json", 20192, "be37b302338dda189bc70bfbe902d8faebeb5986d60c1342713439eefc4ca182"),
    ("tokenizer.json", 10879128, "a263cce0b7e2b03f7ee07ce809783ef4b47f160c3f268a4ea1524f638da45b68"),
    ("tokenizer_config.json", 30439, "159ac88217e90ffd0a4a294726048bb302829e82e1958dc85bb203aa79138fbf"),
    ("flint-int4.json", 1206, "319822f10e32a5916b57e23c7f05f9e92b24d02b3a136d02a3846b5edab78109"),
)


def _json(path: Path, maximum: int = 4 * 1024**2) -> dict[str, Any]:
    if not 2 <= path.stat().st_size <= maximum:
        raise ValueError("Rec metadata is oversized or incomplete")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Rec metadata must be an object")
    return value


def _stat(path: Path) -> dict[str, Any]:
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("Rec files must be regular files")
    return {"path": str(path.resolve()), "size": info.st_size, "device": info.st_dev,
            "inode": info.st_ino, "mtime_ns": info.st_mtime_ns, "ctime_ns": info.st_ctime_ns}


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024**2), b""):
            digest.update(block)
    return digest.hexdigest()


@functools.lru_cache(maxsize=8)
def _binary_hash(path: str, identity: tuple[Any, ...]) -> str:
    # Every caller supplies fresh inode/size/mtime/ctime before reusing a hash.
    return _digest(Path(path))


def data_root() -> Path:
    configured = Path(os.environ.get("XDG_DATA_HOME") or "")
    base = configured if configured.is_absolute() else Path.home() / ".local/share"
    return base / "rec"


def inspect_install(binary: str | Path | None = None, *, data_dir: str | Path | None = None) -> dict[str, Any] | None:
    candidate = Path(binary or Path.home() / ".local/bin/rec").expanduser()
    try:
        candidate = candidate.resolve(strict=True)
        identity = _stat(candidate)
        if not os.access(candidate, os.X_OK):
            return None
        sha = _binary_hash(str(candidate), tuple(identity.values()))
        # Catch changes during a first hash too, before caching a ready claim.
        if _stat(candidate) != identity:
            return None
    except (OSError, ValueError):
        return None
    ready = identity["size"] == CLI_BYTES and sha == CLI_SHA256
    root = Path(data_dir).expanduser().absolute() if data_dir is not None else data_root()
    record = {"version": VERSION if ready else "unverified", "ready": ready,
        "engineBinary": str(candidate), "binary": str(candidate), "binarySha256": sha,
        "binaryStat": identity, "dataRoot": str(root), "runtimeVersion": f"Rec {VERSION}" if ready else "Unverified Rec",
        "sourceCommit": SOURCE_COMMIT,
        "reason": "Official Rec release hash verified" if ready else "Choose the installed official Rec 0.1.0 release"}
    record["identity"] = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
    return record


def installed_model_roots(install: dict[str, Any]) -> list[Path]:
    root = Path(install["dataRoot"]) / "models" / MODEL_CACHE_KEY
    return [root] if root.is_dir() else []


def _sysctl(name: str) -> str:
    try:
        result = subprocess.run(["/usr/sbin/sysctl", "-n", name], capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def host_support(installed_memory: int | None = None, *, chip: str | None = None) -> tuple[bool, str]:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        return False, "Rec requires an Apple silicon Mac"
    detected = _sysctl("machdep.cpu.brand_string") if chip is None else chip
    if detected not in SUPPORTED_CHIPS:
        return False, f"Rec supports Apple M4 Pro, M5 Pro and M5 Max; detected {detected or 'an unknown chip'}"
    if installed_memory is None:
        raw = _sysctl("hw.memsize")
        installed_memory = int(raw) if raw.isdigit() else 0
    if installed_memory < MINIMUM_MEMORY_BYTES:
        return False, "Rec requires at least 48 GiB of installed unified memory"
    return True, f"Rec supports {detected} with {installed_memory / 1024**3:.0f} GiB unified memory"


def inspect_model(path: str | Path) -> dict[str, Any] | None:
    """Check pinned file sizes, small metadata hashes and safetensors headers.

    No weight payload is read here. Rec verifies complete pinned SHA256s using
    its own fresh identity-bound download receipt before it loads the model.
    """
    root = Path(path).expanduser()
    try:
        root = root.resolve(strict=True)
        files = []
        for name, size, sha in MODEL_FILES:
            source = root / name
            if source.is_symlink():
                return None  # The native downloader requires regular leaf files.
            identity = _stat(source)
            if identity["size"] != size:
                return None
            if not name.endswith(".safetensors") and _digest(source) != sha:
                return None
            files.append({**identity, "name": name, "sha256": sha})
        config = _json(root / "config.json")
        quant = config.get("quantization") or {}
        export = config.get("mlx_export") or {}
        if (config.get("model_type") != "flint" or quant.get("bits") != 4 or quant.get("group_size") != 64
                or export.get("bits") != 4 or export.get("routed_expert_bits") != 4 or export.get("embedding_bits") != 8
                or config.get("max_position_embeddings") != CONTEXT_MAXIMUM):
            return None
        complete, tensors, headers = tensor_inventory.safetensors_inventory(root)
        if not complete or not tensors:
            return None
        expected_shards = {name for name, _, _ in MODEL_FILES if name.endswith(".safetensors")}
        if {entry["name"] for entry in headers} != expected_shards:
            return None
        # Do not approve a source that changed during the header walk.
        for item in files:
            current = _stat(root / item["name"])
            if current != {key: item[key] for key in current}:
                return None
        layers = config.get("layer_types") or []
        if len(layers) != config.get("num_hidden_layers") or any(kind not in {"full_attention", "sliding_attention"} for kind in layers):
            return None
        geometry = {"fullAttentionLayers": layers.count("full_attention"),
            "slidingAttentionLayers": layers.count("sliding_attention"),
            "slidingWindow": int(config["sliding_window"]), "kvHeads": int(config["num_key_value_heads"]),
            "headDimension": int(config["head_dim"]), "ready": True, "rec": True}
        verified = _json(root / "verified.json") if (root / "verified.json").is_file() else {}
        payload_verified = all(isinstance(verified.get(item["name"]), dict) and all(
            verified[item["name"]].get(key) == item[key] for key in
            ("sha256", "size", "device", "inode", "mtime_ns", "ctime_ns")) for item in files)
        weight_bytes = sum(item["size"] for item in files if item["name"].endswith(".safetensors"))
        model_identity = hashlib.sha256(json.dumps([MODEL_REVISION, files, headers], sort_keys=True).encode()).hexdigest()
        return {"path": str(root), "id": MODEL_ID, "name": "Flint INT4", "identity": model_identity,
            "revision": MODEL_REVISION, "repo": MODEL_REPO, "weightBytes": weight_bytes,
            "files": files, "headers": headers, "config": config, "geometry": geometry,
            "nativeContext": CONTEXT_MAXIMUM, "payloadVerified": payload_verified,
            "quantization": "INT4 group 64 projections and experts · INT8 embeddings"}
    except (OSError, ValueError, TypeError, KeyError):
        return None


def memory_estimate(model: dict[str, Any], context: int) -> dict[str, Any]:
    geometry = model.get("geometry") or {}
    if type(context) is not int or not 256 <= context <= CONTEXT_MAXIMUM:
        raise ValueError("Rec context must be between 256 and 262,144 tokens")
    weights = int(model["weightBytes"])
    kv_scalar_bytes = 2  # Conservative BF16 envelope, including native INT8 KV.
    per_layer = int(geometry["kvHeads"]) * int(geometry["headDimension"]) * 2 * kv_scalar_bytes
    kv = per_layer * (int(geometry["fullAttentionLayers"]) * context
        + int(geometry["slidingAttentionLayers"]) * min(context, int(geometry["slidingWindow"])))
    return {"version": 1, "modelBytes": weights, "ssdWeightBytes": 0,
        "kvCacheBytes": kv, "kvPrecision": "BF16 envelope for engine-owned KV", "kvScalarBytes": kv_scalar_bytes,
        "runtimeReserveBytes": RUNTIME_RESERVE_BYTES, "estimatedWorkingSetBytes": weights + kv + RUNTIME_RESERVE_BYTES,
        "contextTokens": context, "parallelLanes": 1, "geometryReady": True,
        "geometry": copy.deepcopy(geometry),
        "basis": "Installed INT4 projections/experts and INT8 embeddings, plus a conservative BF16 KV envelope for full-attention layers and 513-token sliding windows, and a 2 GiB runtime reserve. Rec owns the native KV layout and single-session scheduler; this is an estimate, not a measured peak."}


def model_record(install: dict[str, Any], model: dict[str, Any], engines: list[tuple[str, str]], installed_memory: int) -> dict[str, Any]:
    supported, host_reason = host_support(installed_memory)
    ready = install.get("ready") is True and supported
    runtime_version = f"Rec {install.get('version') or VERSION}"
    fingerprint = hashlib.sha256(json.dumps([install["identity"], model["identity"]]).encode()).hexdigest()
    reason = host_reason if not supported else f"{runtime_version} · official Flint INT4 with native reasoning and function tools"
    backends = {}
    for engine, label in engines:
        native = engine == "rec"
        backends[engine] = {"runnable": native and ready,
            "reason": reason if native else f"This entry uses Rec; select the original checkpoint to use {label}",
            "modelPath": model["path"], "mtp": False, "mtpReason": "Rec owns decoding; no MTP control is exposed",
            "dflash": False, "kv": False, "kvChoices": ["off"], "preferredAcceleration": "off", "fallbackAcceleration": "off",
            "depth": 1, "depthMax": 1, "agentReasoning": ["auto"], "codexReasoning": ["auto"],
            "runtimeVersion": runtime_version if native else "Not applicable", "benchmarkModelFingerprint": fingerprint,
            "localBenchmark": None, "localBenchmarks": [], "benchmarkHistoryCount": 0,
            "implicitSamplingDefaultsVerified": False, "customSampling": native,
            "samplingFields": list(SAMPLING_FIELDS) if native else [],
            "samplingReason": "Rec accepts temperature, top_p, top_k, presence_penalty and seed. Frequency/min_p stay zero and repetition_penalty stays one.",
            "contextWindows": list(CONTEXTS), "contextMaximum": CONTEXT_MAXIMUM, "outputMaximum": OUTPUT_MAXIMUM,
            "memoryEstimate": memory_estimate(model, DEFAULT_CONTEXT), "installedMemoryBytes": installed_memory}
    return {"id": "rec-flint-int4", "name": "Flint INT4 · Rec", "path": model["path"],
        "artifact": "rec:" + model["identity"][:24], "origins": ["Rec · " + MODEL_REPO],
        "format": "MLX INT4 / INT8", "architecture": "FlintForCausalLM", "modelType": "rec-flint",
        "nativeContext": CONTEXT_MAXIMUM, "defaultContext": DEFAULT_CONTEXT, "defaultOutput": DEFAULT_OUTPUT,
        "outputMaximum": OUTPUT_MAXIMUM, "defaultReasoning": "auto", "quantization": model["quantization"],
        "size": model["weightBytes"], "sizeLabel": f"{model['weightBytes'] / 1024**3:.1f} GiB",
        "memoryGeometry": copy.deepcopy(model["geometry"]), "mtpSidecarSize": 0, "ready": ready,
        "status": "Installed · Rec payload verified" if model.get("payloadVerified") else "Installed · headers checked",
        "mtp": {"declared": False, "integrated": False, "sidecar": False}, "templateReasoningEfforts": [],
        "defaultSampling": dict(DEFAULT_SAMPLING), "lmKey": MODEL_ID, "remoteModelId": MODEL_ID,
        "sharedServer": False, "remote": False, "rec": copy.deepcopy(model), "backends": backends}


def planning_arguments(install: dict[str, Any], model: dict[str, Any], context: int, *, port: int, output: int = DEFAULT_OUTPUT) -> list[str]:
    if install.get("ready") is not True:
        raise ValueError("Rec's installed executable failed its official release hash check")
    if type(context) is not int or not 256 <= context <= CONTEXT_MAXIMUM:
        raise ValueError("Rec context must be between 256 and 262,144 tokens")
    if type(output) is not int or not 1 <= output <= min(OUTPUT_MAXIMUM, context - 1024):
        raise ValueError("Rec Max response must leave at least 1,024 context tokens for the prompt")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Rec needs a valid launcher-owned loopback port")
    return [str(install["engineBinary"]), "serve", MODEL_ID, "--context", str(context), "--port", str(port)]


def _write_private(path: Path, value: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(value)


def _run_alias(run_dir: Path) -> Path:
    return RUN_ALIAS_PARENT / hashlib.sha256(str(run_dir).encode()).hexdigest()[:24]


def _check_alias_parent(*, create: bool = False) -> None:
    if create:
        try:
            RUN_ALIAS_PARENT.mkdir(mode=0o700)
        except FileExistsError:
            pass
    details = RUN_ALIAS_PARENT.lstat()
    if (not stat.S_ISDIR(details.st_mode) or details.st_uid != os.getuid()
            or stat.S_IMODE(details.st_mode) != 0o700):
        raise ValueError("Rec's short-path directory must be a private owned directory")


def _checked_run_alias(run_dir: Path, *, require_target: bool = True) -> Path:
    _check_alias_parent()
    alias = _run_alias(run_dir)
    details = alias.lstat()
    target = run_dir / "rec-data"
    if (not stat.S_ISLNK(details.st_mode) or details.st_uid != os.getuid()
            or os.readlink(alias) != str(target)
            or (require_target and alias.resolve(strict=True) != target)):
        raise ValueError("Rec's short private data link changed before startup")
    return alias


def cleanup_run_alias(run_dir: str | Path) -> bool:
    """Unlink only this run's owned short alias, preserving every real file."""
    try:
        directory = Path(run_dir).resolve()
        alias = _checked_run_alias(directory, require_target=False)
        alias.unlink()
        return True
    except (OSError, ValueError):
        return False


def prepare_run(install: dict[str, Any], model: dict[str, Any], run_dir: str | Path,
                context: int, port: int, api_key: str, *, output: int = DEFAULT_OUTPUT) -> tuple[list[str], dict[str, str]]:
    planning_arguments(install, model, context, port=port, output=output)
    if not isinstance(api_key, str) or re.fullmatch(r"[0-9a-f]{64}", api_key) is None:
        raise ValueError("Rec requires a private 32-byte hexadecimal API key")
    run_dir = Path(run_dir).resolve(strict=True)
    if not run_dir.is_dir():
        raise ValueError("Rec needs an existing private launch directory")
    xdg = run_dir / "rec-data"
    private_root = xdg / "rec"
    config_root = private_root / "config"
    models = private_root / "models"
    for directory in (xdg, private_root, config_root, models, private_root / "state"):
        directory.mkdir(mode=0o700, exist_ok=False)
    _write_private(config_root / "api-key", api_key + "\n")
    (models / MODEL_CACHE_KEY).symlink_to(Path(model["path"]).resolve(strict=True), target_is_directory=True)
    # Reuse a previously extracted official native runtime when available. The
    # CLI independently verifies every embedded runtime file before starting.
    shared_runtime = Path(install["dataRoot"]) / "runtimes"
    if shared_runtime.is_dir():
        (private_root / "runtimes").symlink_to(shared_runtime.resolve(), target_is_directory=True)
    # Darwin's Unix socket path is limited to 104 bytes. Rec places its
    # control.sock under XDG_DATA_HOME, so keep native paths short while all
    # actual files (including the bearer key) stay in the launcher's run folder.
    _check_alias_parent(create=True)
    alias = _run_alias(run_dir)
    alias.symlink_to(xdg, target_is_directory=True)
    _checked_run_alias(run_dir)
    config = {"install": install, "model": model, "context": context, "output": output,
        "port": port, "xdgDataHome": str(alias), "apiKeyFile": str(config_root / "api-key")}
    config_path = run_dir / "rec.json"
    try:
        _write_private(config_path, json.dumps(config, separators=(",", ":")))
    except BaseException:
        cleanup_run_alias(run_dir)
        raise
    argv = [sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()), str(config_path)]
    return argv, {"XDG_DATA_HOME": str(alias), "HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}


def validate_served_catalog(value: Any, served_id: str = MODEL_ID) -> None:
    if not isinstance(value, dict) or not isinstance(value.get("data"), list) or not any(
            isinstance(model, dict) and model.get("id") == served_id for model in value["data"]):
        raise ValueError("Rec is not advertising the selected Flint model")


def run_verified(config_path: str | Path) -> None:
    path = Path(config_path).resolve(strict=True)
    config = _json(path, 16 * 1024**2)
    install = config["install"]
    current = inspect_install(install["engineBinary"], data_dir=install["dataRoot"])
    if not current or not current["ready"] or current["identity"] != install["identity"]:
        raise ValueError("Rec changed before startup; rescan before launching")
    model = inspect_model(config["model"]["path"])
    if model is None or model["identity"] != config["model"]["identity"]:
        raise ValueError("Flint changed before startup; rescan before launching")
    xdg = path.parent / "rec-data"
    alias = _checked_run_alias(path.parent)
    if str(alias) != config["xdgDataHome"]:
        raise ValueError("Rec private data path changed before startup")
    link = xdg / "rec/models" / MODEL_CACHE_KEY
    if not link.is_symlink() or link.resolve(strict=True) != Path(model["path"]).resolve(strict=True):
        raise ValueError("Rec's private model link changed before startup")
    key_file = xdg / "rec/config/api-key"
    if str(key_file) != config["apiKeyFile"] or key_file.is_symlink() or stat.S_IMODE(key_file.stat().st_mode) != 0o600:
        raise ValueError("Rec's private API key file changed before startup")
    if re.fullmatch(r"[0-9a-f]{64}\n?", key_file.read_text()) is None:
        raise ValueError("Rec's private API key is invalid")
    argv = planning_arguments(current, model, config["context"], port=config["port"], output=config["output"])
    environment = dict(os.environ)
    environment.update(XDG_DATA_HOME=str(alias), HF_HUB_OFFLINE="1", TOKENIZERS_PARALLELISM="false")
    os.execve(argv[0], argv, environment)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Expected one private Rec launch config")
    run_verified(sys.argv[1])
