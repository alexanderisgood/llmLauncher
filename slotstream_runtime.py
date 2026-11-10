"""Audited Slotstream adapter. Scanning never loads tensors or downloads files.

The owned runner hashes every model file before loading. Scan-time identities
bind the reviewed inventory to launch without reading 105 GB on every refresh.
"""
from __future__ import annotations

import copy
import functools
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

VERSION = "0.2.17"
MODEL_ID = "qwen3.8-flash-next:4bit"
MODEL_DIR = "qwen38-flash-next-mlx-4bit"
CONTEXTS = (16_384, 32_768, 65_536, 131_072, 262_144)
# The whole-process ceiling the native auto planner may size its expert pool
# against. Measured on 17 Sep 2026 (M5 Pro, 48 GB, Q8.2 fork, 112,881-token
# prompt, depth 2): a 30 GB ceiling buys a 12.9 GB pool and 7.03 decode tok/s,
# while 36 GB (≈70% of physical RAM) buys a 19.0 GB pool, a 90.1% expert hit
# rate and 9.68 decode tok/s (+38%); prefill is unchanged. The engine still
# sizes down to live reclaimable memory and the launcher's capacity check
# fails closed when the plan does not fit.
DEFAULT_MEMORY_GB = 36
RUNTIME_HASHES = {
    "slotstream": "1d761999c461c19237f4efa84947265c6253890ea57824ca62b7e2892e8f32aa",
    "mlx.metallib": "198488eb61359e953580a9c4530400feee1a06dd2f28a930a6ffa58aec66a597",
}
Q8_VERSION = "0.2.20-q8.1"
Q8_BINARY = Path.home() / ".slotstream/releases/llm-launcher-0.2.20-q8.1/slotstream"
Q8_MANIFEST_PATH = Path(__file__).with_name("runtime-patches") / "slotstream-q8" / "manifest.json"

# Engine-validated read-path switches that the launcher enables for Q8
# launches. They are passed to the running server *and* to the doctor, so the
# capacity check plans against the same memory ledger the launch will use
# (the 4,096-token prefill pass costs ~2.6 GB of the process budget).
Q8_OPTIMIZATION_ENV = {
    "SLOTSTREAM_PREFILL_CHUNK": "4096",
    "SLOTSTREAM_OPT_READ_SCOPE": "8192",
    "SLOTSTREAM_OPT_LAYER_WORKSPACE": "1",
    "SLOTSTREAM_OPT_COMPACT_STATE": "1",
    "SLOTSTREAM_OPT_COMPACT_MTP": "1",
    "SLOTSTREAM_OPT_INDEXER_TILES": "1",
    "SLOTSTREAM_OPT_PLE_TILES": "1",
    "SLOTSTREAM_OPT_RESIDENT_OVERLAP": "1",
    # Launch-reduction set measured 18 Sep 2026 at 112,881 tokens: prefill
    # 127.7 -> 132.3 tok/s with an unchanged 11.84 decode and byte-identical
    # greedy output. Individual contributions not yet bisected.
    "SLOTSTREAM_OPT_COMPILED_NORM": "1",
    "SLOTSTREAM_OPT_GDN_RECORD": "1",
    "SLOTSTREAM_OPT_SLOT_WORDS": "1",
    "SLOTSTREAM_OPT_WORKSPACE_PIECES": "1",
    # MoE workspace tile size. The engine's default spends 256 tokens of
    # workspace per tile, i.e. 32 serialised tiles (each ending in its own
    # eval) per layer per read scope at a 4,096-token prefill pass; 4,096
    # leaves two. Measured 19 Sep 2026 at 112,881 tokens, paired same-session
    # arms on the pinned 0.2.20-q8.1 binary: prefill 133.7 -> 167.4 and
    # 168.9 tok/s (+25-26%), decode 11.07 -> 11.16/11.34 tok/s (flat), greedy
    # byte-identical (`dcb56fb102e8…`) and drafting unchanged at 130/250
    # accepted. Evidence: bench/results/20260918-234936-flash-tile-4096.json,
    # bench/results/20260919-000134-flash-tile-4096-rep2.json.
    "SLOTSTREAM_OPT_WORKSPACE_TILE": "4096",
}


def q8_hashes() -> dict[str, str]:
    data = json.loads(Q8_MANIFEST_PATH.read_text())
    if data.get("qualified") is not True or data.get("version") != Q8_VERSION:
        raise ValueError("The Q8 runtime has not passed its qualification checks.")
    hashes = data["runtimeHashes"]
    if set(hashes) != {"slotstream", "mlx.metallib"}:
        raise ValueError("Invalid Q8 runtime identity.")
    return hashes


MANIFEST = json.loads(Path(__file__).with_name("slotstream_manifest.json").read_text())
FILES = MANIFEST["files"]
REASONING = ["auto", "off", "minimal", "low", "medium", "high", "xhigh", "max"]


def default_model_path() -> Path:
    return Path.home() / ".slotstream/models" / MODEL_DIR


def identity(path: Path) -> tuple[Any, ...]:
    s = path.stat()
    return (str(path.resolve()), s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024**2), b""):
            h.update(chunk)
    return h.hexdigest()


@functools.lru_cache(maxsize=8)
def _verify_runtime(identities: tuple[tuple[Any, ...], ...], expected: tuple[tuple[str, str], ...] = ()) -> str:
    hashes = dict(expected) if expected else RUNTIME_HASHES
    for name, item in zip(hashes, identities):
        if digest(Path(item[0])) != hashes[name]:
            raise ValueError(f"Slotstream {VERSION}: {name} differs from the audited release. Reinstall the pinned macOS 26 release.")
    return hashlib.sha256(json.dumps(identities).encode()).hexdigest()


def runtime_identity(binary: str | None) -> str:
    if not binary:
        raise ValueError(f"Install Slotstream {VERSION} to use this route.")
    path = Path(binary).expanduser().resolve(strict=True)
    if path.name != "slotstream" or not os.access(path, os.X_OK):
        raise ValueError("Slotstream's executable is missing or not executable.")
    hashes = q8_hashes() if path == Q8_BINARY.resolve() else RUNTIME_HASHES
    items = tuple(identity(path.parent / name) for name in hashes)
    result = _verify_runtime(items, tuple(hashes.items()))
    if items != tuple(identity(path.parent / name) for name in hashes):
        raise ValueError("Slotstream changed during verification. Rescan the runtime.")
    return result


def inspect_install(binary: str | None, model_path: str | Path | None = None) -> dict[str, Any]:
    runtime = runtime_identity(binary)
    root = Path(model_path or default_model_path()).expanduser().resolve()
    identities = []
    missing = []
    present_bytes = 0
    mtp = False
    for row in FILES:
        path = root / row["path"]
        if not path.is_file() or path.is_symlink() or path.stat().st_size != row["size"]:
            missing.append(row["path"])
            continue
        # Templates/configuration are cheap to check and define model behaviour.
        if not row["path"].endswith(".safetensors") and digest(path) != row["sha256"]:
            missing.append(row["path"])
            continue
        identities.append(identity(path))
        present_bytes += row["size"]
        if row["path"] == "mtp.safetensors":
            mtp = True
    required_missing = [name for name in missing if name != "mtp.safetensors"]
    artifact = hashlib.sha256(json.dumps(identities).encode()).hexdigest()
    return {"binary": str(Path(str(binary)).resolve()), "runtimeVersion": Q8_VERSION if Path(str(binary)).resolve() == Q8_BINARY.resolve() else VERSION,
            "runtimeIdentity": runtime, "modelPath": str(root),
            "artifactIdentity": artifact, "weightBytes": sum(r["size"] for r in FILES),
            "presentBytes": present_bytes, "completeFiles": len(identities), "totalFiles": len(FILES), "missing": missing,
            "ready": not required_missing, "mtp": mtp}


def discover_q8(model_path: str | Path | None = None) -> dict[str, Any] | None:
    try:
        install = inspect_install(str(Q8_BINARY), model_path)
        return install if install["ready"] else None
    except (OSError, ValueError, TypeError, KeyError):
        return None


def discover(binary: str | None) -> dict[str, Any] | None:
    try:
        return inspect_install(binary)
    except (OSError, ValueError, TypeError):
        return None


def clean_environment(env: dict[str, str]) -> dict[str, str]:
    # Experiment flags can change routing, memory, or speculation semantics.
    return {key: value for key, value in env.items()
            if not key.startswith(("SLOTSTREAM_", "DYLD_", "MLX_"))}


def planning_arguments(install: dict[str, Any], context: int, options: dict[str, Any]) -> list[str]:
    selected_q8 = options.get("kv", "off") == "q8"
    if selected_q8 != (install.get("runtimeVersion") == Q8_VERSION):
        raise ValueError("Selected KV precision does not match the verified Slotstream runtime.")
    if context not in CONTEXTS:
        raise ValueError("Choose a supported Slotstream context window.")
    args = ["--model", install["modelPath"], "--max-context", str(context),
            "--mtp", "on" if options["acceleration"] == "mtp" else "off",
            "--vision", "off"]
    if options.get("memoryMode", "auto") == "auto":
        # Native auto sizes the expert cache to currently reclaimable memory.
        # Bound its RAM share by the user's whole-process ceiling as well.
        ram = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
        percent = min(100.0, options["memoryGB"] * 1_000_000_000 / ram * 100)
        args.extend(["--max-ram-percent", f"{percent:.6f}"])
    else:
        args.extend(["--memory-gb", str(options["memoryGB"])])
    return args


def doctor(install: dict[str, Any], context: int, options: dict[str, Any]) -> dict[str, Any]:
    """Use the native planner's complete context/prefix/MTP memory ledger."""
    env = clean_environment(dict(os.environ))
    env["SLOTSTREAM_DRAFT_DEPTH"] = str(options["depth"])
    if options.get("kv") == "q8":
        env.update(Q8_OPTIMIZATION_ENV)
    result = subprocess.run([install["binary"], "doctor", *planning_arguments(install, context, options), "--json"],
                            env=env, capture_output=True, text=True, timeout=30, check=False)
    try:
        data = json.loads(result.stdout)
    except (ValueError, TypeError) as error:
        raise ValueError("Slotstream could not produce a valid memory plan.") from error
    if result.returncode or data.get("error"):
        reason = (data.get("error") or {}).get("message") or result.stderr.strip()
        raise ValueError(f"Slotstream cannot fit the selected settings right now: {reason}")
    if (data.get("max_context_tokens") != context
            or data.get("mtp") is not (options["acceleration"] == "mtp")
            or data.get("source") != ("auto" if options.get("memoryMode", "auto") == "auto" else "--memory-gb")
            or data.get("vision") is not False):
        raise ValueError("Slotstream's memory plan does not honour the selected context and MTP settings.")
    if options.get("kv", "off") == "q8" and (data.get("kv_cache_bits") != 8 or data.get("kv_cache_group_size") != 64):
        raise ValueError("Slotstream did not confirm Q8 KV cache in its memory plan.")
    ledger = data.get("memory_ledger", {})
    peak = ledger.get("expected_peak_bytes")
    if type(peak) is not int or peak <= 0 or peak > options["memoryGB"] * 1_000_000_000:
        raise ValueError("Slotstream's memory ledger exceeds the selected process budget.")
    return data


def validate_served_catalog(data: dict[str, Any], context: int, kv: str = "off") -> None:
    models = data.get("data")
    if not isinstance(models, list) or len(models) != 1:
        raise RuntimeError("Slotstream returned an unexpected model catalog.")
    model = models[0]
    if kv == "q8" and (model.get("kv_cache_bits") != 8 or model.get("kv_cache_group_size") != 64):
        raise RuntimeError("Slotstream is not serving the selected Q8 KV cache.")
    if kv == "off" and model.get("kv_cache_bits", 16) != 16:
        raise RuntimeError("Slotstream is not serving full-precision KV cache.")
    policy = model.get("context_policy") or {}
    if (model.get("id") != MODEL_ID or model.get("owned_by") != "slotstream"
            or model.get("context_window") != context or model.get("context_length") != context
            or policy.get("configured_window") != context or policy.get("allocation_available") is not True):
        raise RuntimeError("Slotstream is not serving the selected model and context with available memory.")


def model_record(install: dict[str, Any], engines: list[tuple[str, str]], installed_memory: int) -> dict[str, Any]:
    ready, mtp = install["ready"], install["mtp"]
    q8 = discover_q8(install["modelPath"])
    fingerprint = hashlib.sha256(json.dumps([VERSION, MANIFEST, install["artifactIdentity"], install["runtimeIdentity"], (q8 or {}).get("runtimeIdentity")], sort_keys=True).encode()).hexdigest()
    # A distinct quantisation/repack identity; do not claim Whallm equivalence.
    comparison = hashlib.sha256(f"slotstream-pinned-v1:{MANIFEST['revision']}".encode()).hexdigest()
    reason = ("Full 512 experts · SSD n-grams · native MTP available" if mtp else "Full 512 experts · SSD n-grams · MTP head not installed") if ready else f"Download incomplete: {len(install['missing'])} files missing or invalid. Resume Slotstream pull."
    profile = {"version": 1, "candidate": True, "recommended": True, "moe": True,
               "oversized": True, "qwen38FlashNext": True, "expertCount": 512, "nativeExpertTopK": 10,
               "weightBytes": install["weightBytes"], "installedMemoryBytes": installed_memory,
               "format": "slotstream-mlx-4bit", "reason": reason,
               "comparisonIdentity": comparison, "crossFormatComparisonReady": False,
               "calibration": {"suite": "agentic", "engines": ["slotstream"], "freshProcessPerEngine": True,
                               "coldAndWarmStages": True, "nativeExpertRoutingRequired": True}}
    backends = {}
    for engine, label in engines:
        native = engine == "slotstream"
        backends[engine] = {"runnable": native and ready, "reason": reason if native else f"Use Slotstream for this pinned artifact; it is not qualified in {label}.",
            "mtp": native and ready and mtp, "mtpReason": "Pinned MTP head; selected drafts are verified by the target model." if mtp else "Download the pinned mtp.safetensors head to enable MTP.",
            "dflash": False, "kv": native and q8 is not None, "kvChoices": ["off", "q8"] if native and q8 else ["off"], "preferredAcceleration": "mtp" if mtp else "off",
            "fallbackAcceleration": "mtp" if mtp else "off", "depth": 2 if mtp else 1, "depthMax": 4 if mtp else 1,
            "agentReasoning": REASONING if native else ["auto"], "codexReasoning": ["auto"],
            "runtimeVersion": VERSION if native else "Not applicable", "benchmarkModelFingerprint": fingerprint,
            "localBenchmark": None, "localBenchmarks": [], "benchmarkHistoryCount": 0,
            "implicitSamplingDefaultsVerified": native and ready,
            "customSampling": False, "samplingReason": "This initial Slotstream route uses its pinned native sampling defaults.",
        }
        if native:
            backends[engine].update({"ssdStreaming": True, "ssdProfile": copy.deepcopy(profile),
                "comparisonIdentity": comparison, "exactExpertRouting": True, "modelPath": install["modelPath"],
                "contextWindows": list(CONTEXTS), "contextMaximum": max(CONTEXTS), "outputMaximum": max(CONTEXTS) - 1024})
    return {"id": "slotstream-qwen38-4bit", "name": "Qwen3.8 Flash-Next · Slotstream · full experts" + (" + MTP" if mtp else ""),
            "path": install["modelPath"], "artifact": "slotstream:" + MANIFEST["revision"],
            "origins": ["Slotstream · installed locally"], "format": "Slotstream MLX 4-bit + SSD",
            "architecture": "Qwen4Exp · 512 experts", "modelType": "slotstream-qwen38-flash-next",
            "nativeContext": max(CONTEXTS), "defaultContext": 65_536, "defaultOutput": 8_192, "outputMaximum": max(CONTEXTS) - 1024,
            "defaultReasoning": "medium", "quantization": "4-bit · full experts · SSD n-grams",
            "size": install["weightBytes"], "sizeLabel": f"{install['weightBytes'] / 1024**3:.1f} GiB",
            "memoryGeometry": {"ready": True, "slotstream": True}, "mtpSidecarSize": 1_470_955_171 if mtp else 0,
            "ready": ready, "status": "Installed · hashes checked at startup" if ready else "Download incomplete",
            "mtp": {"declared": mtp, "integrated": False, "sidecar": mtp},
            "templateReasoningEfforts": ["low", "medium", "xhigh"], "defaultSampling": {},
            "lmKey": MODEL_ID, "remoteModelId": MODEL_ID, "sharedServer": False, "remote": False,
            "slotstream": copy.deepcopy(install), "slotstreamQ8": copy.deepcopy(q8), "ssdStreaming": profile, "backends": backends}


def run_verified(config_path: Path) -> None:
    """Verify in the cancellable owned process, then replace it with the engine.

    Upstream skips pinned hash verification when --model is an explicit path.
    Keep that path deterministic and perform its pinned pull --verify ourselves.
    """
    config = json.loads(config_path.read_text())
    install = config["install"]
    if inspect_install(install["binary"], install["modelPath"]) != install or not install["ready"]:
        raise ValueError("Slotstream changed before startup. Rescan before launching.")
    env = clean_environment(dict(os.environ))
    env["SLOTSTREAM_DRAFT_DEPTH"] = str(config["depth"])
    print("Verifying all pinned Slotstream weights before loading…", flush=True)
    subprocess.run([install["binary"], "pull", "--verify", "--dir", install["modelPath"]],
                   env=env, check=True)
    if inspect_install(install["binary"], install["modelPath"]) != install:
        raise ValueError("Slotstream files changed during verification. Rescan before launching.")
    argv = config["argv"]
    if argv[:2] != [install["binary"], "serve"]:
        raise ValueError("Invalid Slotstream server command.")
    os.execve(install["binary"], argv, env)


if __name__ == "__main__":
    import sys
    try:
        if len(sys.argv) != 2:
            raise ValueError("Expected the launcher-owned Slotstream configuration path.")
        run_verified(Path(sys.argv[1]))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f"Slotstream startup refused: {error}", file=sys.stderr, flush=True)
        sys.exit(1)
