"""Pinned Strata Metal runtime and prepared Flash-Next model routes.

Discovery never prepares or copies a model. The Mac engine needs a verified
Metal split-GGUF patch; its BF16 PLE is read from the original separate shard.
"""
from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import flash_vision

VERSION = "0.1.56"
MODEL_ID = "qwen3.8-flash-next-ud-q4_k_xl-bf16-ple"
MODELS = Path.home() / "Library/Application Support/LLM Launcher/strata-models"
# The Mac guide's 32K quality measurements are not an engine limit. Strata
# accepts the model's full 262,144-token window; these are launcher presets.
NATIVE_CONTEXT = 262_144
CONTEXTS = (16_384, 32_768, 65_536, 131_072, NATIVE_CONTEXT)
DEFAULT_CONTEXT = 16_384
DEFAULT_OUTPUT = 4_096
# Prompt and response share the context. The native server has no separate
# 16K output cap; request validation reserves at least 1,024 prompt tokens.
OUTPUT_MAXIMUM = NATIVE_CONTEXT - 1_024
ENGINE_SHA256 = "3e7facb8e88b58dc1f7efca561c22a5967de3cd18e4f694a72467f568f6e27a0"
COMPONENT_SHA256 = "f9fa7ff08df9b696480fb23dbd47e9990e45d48aa732b15a563b091887212177"
CONTROL_SHA256 = "212c86cdcccfc3ab530687b98b01893804762931da28aa97827ebc7cd11e2afa"
SPLIT_ENGINE_SHA256 = "3c64d1a1b2a5774eb5fe3f16b2c185d3d277061154e82d255ca67b228768a660"
SPLIT_MANIFEST_SHA256 = "695d40924ea1ba7bd97eeca641054d416646efefaf21bab11059d0f6e66a22db"
SAMPLING_FIELDS = ("temperature", "top_p", "top_k", "presence_penalty", "frequency_penalty", "repetition_penalty", "seed")
PREPARATION_REASON = "Strata needs the verified local support pack and complete original Q4/BF16 GGUF shards. Rescan after preparing the support pack; no merged weight copy is required."


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def file_identity(path: Path) -> dict:
    s = path.stat()
    return {"path": str(path.resolve()), "size": s.st_size, "device": s.st_dev,
            "inode": s.st_ino, "mtime_ns": s.st_mtime_ns, "ctime_ns": s.st_ctime_ns}


def inspect_install(binary: str | Path | None) -> dict | None:
    if not binary:
        return None
    try:
        binary = Path(binary).resolve(strict=True)
        root = binary.parent.parent
        component = root / "engine/engine-component.json"
        manifest = json.loads(component.read_text())
        patch_file = root / "launcher-patch.json"
        split = patch_file.is_file() and digest(patch_file) == SPLIT_MANIFEST_SHA256
        expected_binary = SPLIT_ENGINE_SHA256 if split else ENGINE_SHA256
        ready = (binary == root / "engine/strata" and manifest.get("version") == VERSION
                 and manifest.get("backend") == "metal" and digest(component) == COMPONENT_SHA256
                 and digest(binary) == expected_binary)
        for item in manifest["files"]:
            p = root / "engine" / item["path"]
            p.resolve().relative_to((root / "engine").resolve())
            ready = ready and (split and item["path"] == "strata" or p.stat().st_size == item["bytes"]) and digest(p) == (expected_binary if item["path"] == "strata" else item["sha256"])
        python, server = root / "python/bin/python3", root / "serve/server.py"
        ready = ready and os.access(python, os.X_OK) and server.is_file()
        control = json.loads((root / "launcher-control.json").read_text())
        ready = ready and control["version"] == VERSION and digest(root / "launcher-control.json") == CONTROL_SHA256
        for name, checksum in control["files"].items():
            p = root / name
            p.resolve().relative_to(root)
            ready = ready and digest(p) == checksum
        identity = hashlib.sha256(json.dumps([manifest, control, expected_binary], sort_keys=True).encode()).hexdigest()
        return {"version": VERSION, "ready": bool(ready), "identity": identity,
                "root": str(root), "engineBinary": str(binary), "supportsSplitGguf": split, "python": str(python),
                "server": str(server), "runtimeVersion": f"Strata {VERSION} · Metal"}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def inspect_model(root: str | Path) -> dict | None:
    try:
        root = Path(root).resolve(strict=True)
        record = json.loads((root / "launcher-model.json").read_text())
        if record.get("schemaVersion") != 1 or record.get("id") != MODEL_ID:
            return None
        sources = record["sourceFiles"]
        source_ok = len(sources) == 4 and all(file_identity(Path(x["path"])) == x for x in sources)
        prepared = record.get("nativeTensorsVerified") is True and bool(record.get("artifacts"))
        artifacts_ok = prepared and all(file_identity(Path(x["path"])) == x for x in record["artifacts"])
        ready = source_ok and artifacts_ok
        record.update(path=str(root), ready=bool(ready), reason=("Verified native Q4 weights and original BF16 PLE" if ready else PREPARATION_REASON))
        record['vision'] = flash_vision.inspect_model(root)
        record["identity"] = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
        return record
    except (OSError, ValueError, KeyError, TypeError):
        return None


def discover_models(root: Path | None = None) -> list[dict]:
    return [model for p in sorted((root or MODELS).glob("*/launcher-model.json"))
            if (model := inspect_model(p.parent)) is not None]


def model_record(install: dict, model: dict, engines: list[tuple[str, str]], installed_memory: int) -> dict:
    host = platform.machine() == "arm64" and installed_memory >= 36 * 1024**3
    ready = install["ready"] and model["ready"] and host and (not model.get("requiresSplitGguf") or install.get("supportsSplitGguf"))
    reason = model["reason"] if not model["ready"] else ("Strata Metal needs an Apple Silicon Mac with at least 36 GiB RAM." if not host else "Strata Metal · Q4 experts streamed from SSD · original BF16 PLE")
    if not install["ready"]:
        reason = "Strata's runtime files failed verification; reinstall the pinned runtime."
    if model.get("requiresSplitGguf") and not install.get("supportsSplitGguf"):
        reason = "Select the launcher Strata build with split-GGUF support to use these existing files."
    backends = {}
    for engine, label in engines:
        native = engine == "strata"
        backends[engine] = {"runnable": bool(native and ready), "reason": reason if native else f"This prepared entry uses Strata; select the original model for {label}.",
            "modelPath": model["path"], "mtp": False, "dflash": False, "kv": False, "kvChoices": ["off"],
            "preferredAcceleration": "off", "fallbackAcceleration": "off", "depth": 1, "depthMax": 1,
            "agentReasoning": ["auto", "off", "low", "medium", "high"], "codexReasoning": ["auto"],
            "runtimeVersion": install["runtimeVersion"] if native else "Not applicable",
            "benchmarkModelFingerprint": model["identity"], "runtimeIdentity": install["identity"],
            "localBenchmark": None, "localBenchmarks": [], "benchmarkHistoryCount": 0,
            "customSampling": native, "samplingFields": list(SAMPLING_FIELDS) if native else [],
            "implicitSamplingDefaultsVerified": False, "contextWindows": list(CONTEXTS),
            "contextMaximum": NATIVE_CONTEXT, "outputMaximum": OUTPUT_MAXIMUM,
            "installedMemoryBytes": installed_memory}
        if native:
            backends[engine]['input'] = ['text', 'image'] if model.get('vision') else ['text']
            backends[engine]['vision'] = copy.deepcopy(model.get('vision'))
    size = int(model["weightBytes"]) + int(model["pleBytes"])
    return {"id": "strata-" + MODEL_ID, "name": "Qwen3.8 Flash-Next · Q4 · Strata",
        "path": model["path"], "artifact": "strata:" + model["identity"][:24], "origins": ["Strata · Unsloth"],
        "format": "GGUF", "architecture": "qwen4exp", "modelType": "strata-flash-next",
        "nativeContext": NATIVE_CONTEXT, "defaultContext": DEFAULT_CONTEXT, "defaultOutput": DEFAULT_OUTPUT,
        "outputMaximum": OUTPUT_MAXIMUM, "defaultReasoning": "auto", "quantization": "UD-Q4_K_XL · BF16 PLE",
        "size": size, "sizeLabel": f"{size / 1024**3:.1f} GiB", "mtpSidecarSize": 0,
        "ready": bool(ready), "status": reason, "mtp": {"declared": False, "integrated": False, "sidecar": False},
        "templateReasoningEfforts": [], "defaultSampling": {"temperature": 0.6, "top_p": 0.95, "top_k": 20},
        "lmKey": MODEL_ID, "remoteModelId": MODEL_ID, "sharedServer": False, "remote": False,
        "strata": copy.deepcopy(model), "backends": backends}


def validate_route(binary: str | None, model: dict, context: int, output: int) -> tuple[dict, dict]:
    install = inspect_install(binary)
    current = inspect_model(model["path"])
    if not install or not install["ready"]:
        raise ValueError("Strata's pinned runtime failed verification. Rescan after reinstalling.")
    if not current or not current["ready"]:
        raise ValueError(PREPARATION_REASON)
    if current.get("requiresSplitGguf") and not install.get("supportsSplitGguf"):
        raise ValueError("Select the verified Strata split-GGUF build for these model files")
    if current["identity"] != model.get("strata", model).get("identity"):
        raise ValueError("Strata's model changed after scanning; rescan before launching.")
    if type(context) is not int or context not in CONTEXTS:
        choices = ", ".join(f"{value // 1024}K" for value in CONTEXTS)
        raise ValueError(f"Choose a Strata context preset: {choices}.")
    if type(output) is not int or not 1 <= output <= min(OUTPUT_MAXIMUM, context - 1024):
        raise ValueError("Strata's response limit must leave 1,024 tokens for the prompt.")
    return install, current


def server_config(install: dict, model: dict, *, context: int, port: int, api_key: str, log: Path) -> dict:
    if type(port) is not int or not 1 <= port <= 65535 or not api_key:
        raise ValueError("Strata needs a private API key and valid loopback port")
    config = {"exe": install["engineBinary"], "cwd": install["root"],
        "args": ["--pack", model["pack"], "--native", model["native"], "--ple-gguf", model["ple"],
                 "--expert-cache", "64", "--expert-profile", str(Path(install["root"]) / "engine/metal/data/expert-profile.bin"),
                 "--mmap-experts", "--max-context", str(context), "--prefill", "auto", "--spec", "2", "--suffix-draft", "0"],
        "tokenizer": str(Path(model["pack"]) / "tokenizer"), "model_name": MODEL_ID,
        "host": "127.0.0.1", "port": port, "backend": "metal", "parallel": 1,
        "api_key": api_key, "log": str(log), "fit_max_tokens": False,
        "env": {"STRATA_METAL_STREAM": "1", "STRATA_METAL_SPLIT_GGUF": "1"}, "open_browser": False}
    if model.get('vision'):
        reader = str(Path(install['root']) / 'engine/strata-vision')
        config['vision'] = {'exe': reader, 'cpu_exe': reader, 'gpu': True,
                            'mmproj': model['vision']['projector'], 'model': model['native'],
                            'max_tokens': 1024}
    return config


def run_verified(path: str) -> None:
    cfg_path = Path(path).resolve(strict=True)
    cfg = json.loads(cfg_path.read_text())
    install, model = validate_route(cfg["install"]["engineBinary"], cfg["model"], cfg["context"], cfg["output"])
    if install["identity"] != cfg["install"]["identity"]:
        raise ValueError("Strata changed before startup; rescan")
    run = server_config(install, model, context=cfg["context"], port=cfg["port"],
                        api_key=os.environ["LLM_STRATA_API_KEY"], log=cfg_path.with_suffix(".engine.log"))
    server_path = cfg_path.with_suffix(".server.json")
    fd = os.open(server_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(run, f)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "DYLD_", "STRATA_")) and k != "LLM_STRATA_API_KEY"}
    env.update(PYTHONNOUSERSITE="1", HF_HUB_OFFLINE="1", TOKENIZERS_PARALLELISM="false")
    argv = [install["python"], "-I", "-B", install["server"], "--engine", "strata", "--config", str(server_path), "--host", "127.0.0.1", "--port", str(cfg["port"])]
    os.execve(argv[0], argv, env)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Expected one private Strata launch config")
    run_verified(sys.argv[1])
