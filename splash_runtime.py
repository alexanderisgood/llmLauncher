"""Splash runtime discovery and launch planning for packs and local sources.

Splash 1.5 loads GGUFs (including split Flash-Next targets) and supported MLX
checkpoints. Its native validators identify compatibility;
filenames are labels, never evidence. Older releases retain their pack path.
"""
from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import pathlib
import platform
import re
import signal
import stat
import subprocess
import tempfile
import time
from typing import Any

HOME = pathlib.Path.home()
ROOT = pathlib.Path("/opt/homebrew/opt/splash")
LIBEXEC = ROOT / "libexec"
ENGINE = LIBEXEC / "engine" / "splash"
SERVER = LIBEXEC / "server" / "server.py"
PYTHON = LIBEXEC / "python" / "bin" / "python3"
RELEASE = LIBEXEC / "release.json"
MODELS = HOME / "Library/Application Support/Splash/models"

VERSION = "1.5.0"
UPSTREAM_MINIMUM = (1, 2, 1)
SOURCE_HELPER = pathlib.Path(__file__).with_name("splash_sources.py")
CONTEXTS = (16_384, 32_768, 65_536, 131_072, 262_144)
CONTEXT_MAXIMUM = 262_144
DEFAULT_CONTEXT = 131_072
DEFAULT_OUTPUT = 8_192
# Splash's 32K --max-new-tokens default is not an engine output ceiling.
# Its frontend validates prompt + requested output against the context window.
OUTPUT_MAXIMUM = CONTEXT_MAXIMUM - 1_024
QUEUE_DEFAULT = 32
MINIMUM_MACOS = (26, 4)
MINIMUM_MEMORY_BYTES = 36 * 1024**3

# Measured from the engine's own memory plan at 128K on 19 Sep 2026: a KV page
# covers 32 tokens and costs 1,064,960 bytes, i.e. ~32.5 KiB per token. The
# engine keeps far more virtual KV than one context (reusable cache state), but
# this is the per-context figure a launch estimate needs.
KV_BYTES_PER_TOKEN = 1_064_960 // 32
RUNTIME_RESERVE_BYTES = 2 * 1024**3
REASONING = ["auto", "off", "low", "medium", "xhigh"]
OWNER_REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
SPLIT_GGUF = re.compile(r"-([0-9]{5})-of-([0-9]{5})\.gguf$")
NATIVE_SERVER_BOOTSTRAP = (
    "import sys; sys.path.insert(0, sys.argv.pop(1)); "
    "from server.server import main; main()"
)
BF16_ROW_PATCH = "bf16-embedding-rows-r1"
BF16_ROW_ENGINE_SHA256 = "2256e056b279f111329ad91fd320e49d3693d2ba475781fb53fb2274444e094c"
BF16_ROW_METALLIB_SHA256 = "e30124e8bceba1a9de7afe75cf1a10439bcfa5c1b777490c829ba4da0d0cd1cd"
M5_PRO_DECODE_PATCH = "m5-pro-decode-r1"
M5_PRO_DECODE_ENGINE_SHA256 = "8abf9ac43ce9f8521317a61d40411f6bf51430e72d806ce369e67e61ee88f844"
M5_PRO_DECODE_METALLIB_SHA256 = "703016c3a3e6f07b1772463c75781b0b67f3e92219a8c7f497e07f794f0d6d3c"
DSPINE_PATCH = "dspine-27b-r3"
DSPINE_CONTEXTS = (2_048, *CONTEXTS)
DSPINE_CONTEXT = DSPINE_CONTEXTS[-1]
DSPINE_OUTPUT = 4096
DSPINE_SAMPLING = {
    "sampling": "custom", "temperature": 0, "topP": 1, "topK": 0,
    "presencePenalty": 0, "frequencyPenalty": 0, "repetitionPenalty": 1, "seed": None,
}
DSPINE_ENGINE_SHA256 = "e01a1da83f3695caab002632c622f5d45d3f82f6e3b0b62d7fbfbaf13d9a5595"
DSPINE_DRAFT_SHA256 = "ac90f1df842ea66b23e4224f3e86624add547526f689ffe9e9c6b7a5937116b1"
DSPINE_DRAFT_BYTES = 4_051_831_880
DSPINE_CONFIG_SHA256 = "c2aa9e3ff22766ea7df0fa5b5f5f7d2035ae722671c6b7eb58b65578705e6815"
DSPINE_MEMORY_BYTES = 8 * 1024**3
# The compact sidecar peaks higher while converting the draft, before
# Splash starts. This reserve covers the measured running sidecar.
DSPINE_COMPACT_MEMORY_BYTES = 13 * 1024**3 // 4
DSPINE_HOME = SOURCE_HELPER.parent / "bench/runtimes/dspine-27b-experimental"
DSPINE_ENGINE = DSPINE_HOME.parent / "splash-1.6.0-llm-launcher-dspine-r3/engine/splash"
DSPINE_SIDECAR = SOURCE_HELPER.parent / "runtime_patches/dspine/splash_sidecar.py"
DSPINE_PYTHON = HOME / "Library/Application Support/LLM Launcher/runtimes/omlx-0.7.0.dev2/bin/python"

# Splash compiles every tool's parameters into an llguidance grammar and
# refuses a fixed set of keywords when they sit at the schema *root* (see the
# engine's ``server/tool_schema.py``); nested uses are kept. Clients express
# cross-field refinements with a top-level ``anyOf`` - Pi's browser_check does
# - and a per-property grammar cannot represent those, so the relay forwards
# the base object schema and lets the tool's own argument validation decide.
UNSUPPORTED_TOOL_ROOT_KEYWORDS = frozenset({
    "$ref", "$dynamicRef", "allOf", "anyOf", "oneOf", "not", "if", "then",
    "else", "dependentRequired", "dependentSchemas", "enum", "const",
    "minProperties", "maxProperties", "patternProperties",
})


def compatible_tool_schema(parameters: Any) -> tuple[dict[str, Any], list[str]]:
    """Return ``parameters`` restricted to the schemas Splash can compile.

    Only the schema root is touched: every nested keyword survives so the
    model still sees the full property shapes. Returns the schema to forward
    and the root keywords that had to be dropped.
    """
    if not isinstance(parameters, dict):
        return {}, ["parameters"] if parameters is not None else []
    schema = {key: value for key, value in parameters.items() if key not in UNSUPPORTED_TOOL_ROOT_KEYWORDS}
    dropped = sorted(key for key in parameters if key in UNSUPPORTED_TOOL_ROOT_KEYWORDS)
    if schema.get("type") not in (None, "object"):
        # The engine requires a top-level JSON object for tool arguments.
        schema.pop("type", None)
        dropped.append("type")
    properties = schema.get("properties")
    if properties is None:
        properties = {}
    elif not isinstance(properties, dict):
        schema["properties"] = properties = {}
        dropped.append("properties")
    required = schema.get("required")
    if required is not None:
        kept: list[str] = []
        if isinstance(required, list):
            for name in required:
                if isinstance(name, str) and name in properties and name not in kept:
                    kept.append(name)
        if kept != required:
            # The engine refuses required names without declared properties.
            dropped.append("required")
        if kept:
            schema["required"] = kept
        else:
            schema.pop("required", None)
    return schema, sorted(set(dropped))


def relax_tool_schemas(request: dict[str, Any]) -> tuple[int, tuple[str, ...]]:
    """Rewrite a Chat Completions ``tools`` list in place for the engine.

    Returns the number of relaxed tool schemas and the root keywords dropped.
    """
    tools = request.get("tools")
    if not isinstance(tools, list):
        return 0, ()
    relaxed = 0
    keywords: set[str] = set()
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        function = tool.get("function")
        holder = function if isinstance(function, dict) else tool
        parameters = holder.get("parameters")
        if not isinstance(parameters, dict):
            continue
        schema, dropped = compatible_tool_schema(parameters)
        if not dropped:
            continue
        holder["parameters"] = schema
        relaxed += 1
        keywords.update(dropped)
    return relaxed, tuple(sorted(keywords))


def bound_thinking_budget(request: dict[str, Any], effort: str | None = None) -> None:
    """Apply the route ceiling to Splash's native per-request thinking budget.

    Older frontends ignore the native field and retain their qualified adapter.
    Both budget spellings may lower the route ceiling; neither can disable it.
    """
    from splash_reasoning import thinking_budget

    output = request.get("max_tokens", DEFAULT_OUTPUT)
    if type(output) is not int or output < 0:
        raise ValueError("Splash max_tokens must be a non-negative integer")
    ceiling = thinking_budget(effort or request.get("reasoning_effort"), output)
    for key in ("thinking_token_budget", "thinking_budget_tokens"):
        value = request.get(key)
        if value is None or key == "thinking_token_budget" and value == -1 and type(value) is int:
            continue
        if type(value) is not int or value < 0:
            raise ValueError(f"{key} must be a non-negative integer")
        ceiling = min(ceiling, value)
    request["thinking_token_budget"] = ceiling
    if "thinking_budget_tokens" in request:
        request["thinking_budget_tokens"] = ceiling


def digest(path: pathlib.Path, *, cache: bool = True) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        if not cache and hasattr(fcntl, "F_NOCACHE"):
            try:
                fcntl.fcntl(handle.fileno(), fcntl.F_NOCACHE, 1)
            except OSError:
                pass  # Filesystems without this hint still need a verified digest.
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def read_json(path: pathlib.Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def release_at_least(install: dict[str, Any], minimum: tuple[int, ...]) -> bool:
    match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?(?:$|[-+])", str(install.get("version") or ""))
    parts = tuple(int(part or 0) for part in match.groups()) if match else ()
    return parts >= minimum


def upstream_supported(install: dict[str, Any]) -> bool:
    return release_at_least(install, UPSTREAM_MINIMUM)


def native_supported(install: dict[str, Any]) -> bool:
    return release_at_least(install, (1, 4, 0))


def release_identity(release: pathlib.Path | None = None) -> dict[str, Any] | None:
    """Declared version plus on-disk hash verification for the engine binary."""
    document = read_json(release or RELEASE)
    if not isinstance(document, dict):
        return None
    version = str(document.get("version") or "")
    binary_hash = str(document.get("binary_sha256") or "")
    metallib_hash = str(document.get("metallib_sha256") or "")
    if not version or not binary_hash or not metallib_hash:
        return None
    binary = (release.parent / "engine" / "splash") if release else ENGINE
    metallib = (release.parent / "engine" / "splash.metallib") if release else ENGINE.with_suffix(".metallib")
    try:
        binary_ok = digest(binary) == binary_hash
        metallib_ok = digest(metallib) == metallib_hash
    except OSError:
        return None
    patch = document.get("launcher_patch")
    if patch:
        expected = {
            ("1.4.0", BF16_ROW_PATCH): (BF16_ROW_ENGINE_SHA256, BF16_ROW_METALLIB_SHA256),
            ("1.5.0", BF16_ROW_PATCH): ("bebba98543e33f40505fa3b12377f95e249435223a5875546a57b1210f8a52ec", "0279664b0a60a571878d25e9595815b31b64aaaca0da80cf85aa7715d8d02c76"),
            ("1.6.0", M5_PRO_DECODE_PATCH): (M5_PRO_DECODE_ENGINE_SHA256, M5_PRO_DECODE_METALLIB_SHA256),
            ("1.6.0", DSPINE_PATCH): (DSPINE_ENGINE_SHA256, M5_PRO_DECODE_METALLIB_SHA256),
        }.get((version, str(patch)))
        binary_ok = bool(binary_ok and expected and binary_hash == expected[0])
        metallib_ok = bool(metallib_ok and expected and metallib_hash == expected[1])
    return {
        "version": version,
        "binarySha256": binary_hash,
        "metallibSha256": metallib_hash,
        "binaryVerified": binary_ok,
        "metallibVerified": metallib_ok,
        **({"launcherPatch": patch} if patch else {}),
    }


def inspect_pack(root: pathlib.Path) -> dict[str, Any] | None:
    """Fail-closed description of one Splash pack (no engine launch)."""
    manifest = read_json(root / "manifest.json")
    if not isinstance(manifest, dict):
        return None
    if manifest.get("schema_version") not in (None, 3, 4):
        # Community Q8 packs require a separate fork; native GGUF Q8 is valid.
        return None
    model = str(manifest.get("model") or "").strip()
    geometry = manifest.get("execution_geometry")
    artifacts = manifest.get("artifacts")
    if not model or not isinstance(geometry, dict) or not isinstance(artifacts, list) or not artifacts:
        return None
    for name in ("target", "draft", "tokenizer"):
        if not (root / name).is_dir():
            return None
    bytes_by_root: dict[str, int] = {}
    for record in artifacts:
        if not isinstance(record, dict):
            return None
        path = str(record.get("path") or "")
        size = record.get("size")
        if not path or type(size) is not int or size <= 0:
            return None
        relative = pathlib.PurePosixPath(path)
        if relative.is_absolute() or ".." in relative.parts:
            return None
        try:
            artifact = (root / path).resolve(strict=True)
            artifact.relative_to(root.resolve())
            if not artifact.is_file() or artifact.stat().st_size != size:
                return None
        except (OSError, ValueError):
            return None
        head = path.split("/", 1)[0]
        bytes_by_root[head] = bytes_by_root.get(head, 0) + size
    if any(not bytes_by_root.get(name) for name in ("target", "draft", "tokenizer")):
        return None
    pack_id = f"{root.parent.name}/{root.name}"
    return {
        "kind": "pack",
        "id": pack_id,
        "name": model,
        "path": str(root),
        "artifactSetSha256": str(manifest.get("artifact_set_sha256") or ""),
        "geometry": copy.deepcopy(geometry),
        "weightBytes": bytes_by_root.get("target", 0) + bytes_by_root.get("draft", 0) + bytes_by_root.get("vision", 0),
        "targetBytes": bytes_by_root.get("target", 0),
        "draftBytes": bytes_by_root.get("draft", 0),
        "visionBytes": bytes_by_root.get("vision", 0),
        "tokenizerBytes": bytes_by_root.get("tokenizer", 0),
        "identity": hashlib.sha256(json.dumps(
            [pack_id, manifest],
            sort_keys=True,
        ).encode()).hexdigest(),
    }


def discover_packs(models: pathlib.Path | None = None) -> list[dict[str, Any]]:
    base = models or MODELS
    packs: list[dict[str, Any]] = []
    if not base.is_dir():
        return packs
    for owner in sorted(path for path in base.iterdir() if path.is_dir()):
        for repo in sorted(path for path in owner.iterdir() if path.is_dir()):
            description = inspect_pack(repo)
            if description and OWNER_REPO.match(description["id"]):
                packs.append(description)
    return packs


def inspect_install(binary: str | pathlib.Path | None = None, *, libexec: pathlib.Path | None = None) -> dict[str, Any] | None:
    """Stable, verifiable description of the engine install (like Slotstream's)."""
    if libexec is not None:
        base = pathlib.Path(libexec)
    elif binary is not None:
        candidate = pathlib.Path(binary)
        base = candidate.parent.parent if candidate.parent.name == "engine" else candidate.parent
    else:
        base = LIBEXEC
    release = release_identity(base / "release.json")
    engine = pathlib.Path(binary) if binary else base / "engine" / "splash"
    server = base / "server" / "server.py"
    python = base / "python" / "bin" / "python3"
    if (release is None or not engine.is_file() or not server.is_file() or not python.is_file()
            or not os.access(engine, os.X_OK) or not os.access(python, os.X_OK)):
        return None
    packs = [] if release_at_least(release, (1, 3, 1)) else discover_packs()
    return {
        "version": release["version"],
        "release": release,
        "libexec": str(base),
        "engineBinary": str(engine),
        "server": str(server),
        "python": str(python),
        "runtimeVersion": f"Splash {release['version']}",
        "ready": bool(release["binaryVerified"] and release["metallibVerified"]),
        "packs": packs,
        "upstreamSupported": upstream_supported({"version": release["version"]}),
    }


def dspine_target(pack: dict[str, Any]) -> bool:
    return (
        pack.get("kind") == "source"
        and pack.get("family") == "Qwen3.8-27B"
        and pack.get("format") == "mlx-affine"
        and pack.get("quantization") == "4-bit affine · group 64"
    )


def inspect_dspine_install(pack: dict[str, Any]) -> dict[str, Any] | None:
    if not dspine_target(pack):
        return None
    weights = DSPINE_HOME / "weights"
    try:
        if (
            (weights / "model.safetensors").stat().st_size != DSPINE_DRAFT_BYTES
            or digest(weights / "config.json") != DSPINE_CONFIG_SHA256
            or not DSPINE_SIDECAR.is_file() or not os.access(DSPINE_PYTHON, os.X_OK)
            or not (DSPINE_HOME / "tencent/dspine_mlx/dspine_mlx/model.py").is_file()
        ):
            return None
    except OSError:
        return None
    install = inspect_install(DSPINE_ENGINE)
    if install and install["ready"] and install["release"].get("launcherPatch") == DSPINE_PATCH:
        return install
    return None


def dspine_target_bytes(install: dict[str, Any], pack: dict[str, Any]) -> int:
    """Read the target's native allocation plan without assembling or loading weights."""
    source = pathlib.Path(pack["path"])
    try:
        with tempfile.TemporaryDirectory(prefix="launcher-dspine-size-") as directory:
            root = pathlib.Path(directory)
            (root / "config.json").symlink_to(source / "config.json")
            (root / "target").mkdir()
            for shard in source.glob("*.safetensors"):
                (root / "target" / shard.name).symlink_to(shard)
            (root / "model.json").write_text(json.dumps({
                "version": 1, "model": pack["id"], "target_format": "mlx-affine",
                "vision_format": "none", "external_draft": "dspine",
            }), encoding="utf-8")
            result = subprocess.run(
                [str(install["engineBinary"]), "dspine-model-size", str(root)],
                capture_output=True, text=True, timeout=5, check=True,
                env=clean_environment(dict(os.environ)),
            )
        size = json.loads(result.stdout).get("target_weights_bytes")
        return size if type(size) is int and 0 < size <= int(pack["targetBytes"]) else 0
    except (OSError, ValueError, KeyError, AttributeError, subprocess.SubprocessError):
        return 0


def installed_source_roots(models: pathlib.Path | None = None) -> list[pathlib.Path]:
    """Original checkpoints linked by modern Splash installations."""
    roots = []
    for manifest in sorted((models or MODELS).glob("*/*/model.json")):
        record = read_json(manifest)
        if not isinstance(record, dict) or not isinstance(record.get("files"), dict):
            continue
        if record.get("target_format") == "gguf":
            roots.extend(pathlib.Path(entry["path"]) for name, entry in record["files"].items()
                         if name.startswith("target/") and name.endswith(".gguf")
                         and isinstance(entry, dict) and isinstance(entry.get("path"), str))
        elif record.get("target_format") == "mlx-affine":
            entry = record["files"].get("config.json") or {}
            if isinstance(entry, dict) and isinstance(entry.get("path"), str):
                roots.append(pathlib.Path(entry["path"]).parent)
    return roots


def source_candidates(roots: list[pathlib.Path], install: dict[str, Any] | None = None) -> list[str]:
    """GGUF variants and MLX candidates for the selected release's own checks."""
    candidates: list[str] = []
    seen: set[tuple[int, int]] = set()
    modern_mlx = release_at_least(install or {}, (1, 4, 0))
    for root in roots:
        try:
            paths = [root] if root.is_file() and root.suffix == ".gguf" else sorted(root.glob("*.gguf"))
            config = read_json(root / "config.json") or {}
            quant = (config.get("quantization") or (config.get("quantization_config") if modern_mlx else None)
                     if isinstance(config, dict) else None)
            if (isinstance(quant, dict) and (modern_mlx or (
                    quant.get("bits") == 4 and quant.get("group_size") == 64
                    and quant.get("mode", "affine") == "affine"))):
                paths.append(root)
        except OSError:
            continue
        for path in paths:
            split = SPLIT_GGUF.search(path.name)
            if (path.name.lower().startswith(("mmproj", "mtp-", "mtp_"))
                    or split and int(split.group(1)) != 1):
                continue
            try:
                stat = path.stat()
                key = (stat.st_dev, stat.st_ino)
                if key not in seen:
                    seen.add(key)
                    # Keep shard leaf names beside their siblings in Hub
                    # snapshots, whose symlinks target opaque blob filenames.
                    candidates.append(str(path.parent.resolve() / path.name))
            except OSError:
                continue
    return candidates


def inspect_sources(install: dict[str, Any], paths: list[str]) -> list[dict[str, Any]]:
    """Use this release's loader without loading weights or contacting the Hub."""
    if not paths or not install.get("ready") or not upstream_supported(install):
        return []
    try:
        result = subprocess.run(
            [str(install["python"]), "-I", "-B", str(SOURCE_HELPER), str(install["libexec"]), "inspect"],
            input=json.dumps({"paths": paths}), text=True, capture_output=True,
            timeout=90, env=clean_environment(dict(os.environ)),
        )
        if result.returncode:
            return []
        records = json.loads(result.stdout)
        return [item["source"] for item in records if isinstance(item, dict) and isinstance(item.get("source"), dict)]
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []


def inspect_model(install: dict[str, Any], model: dict[str, Any]) -> dict[str, Any] | None:
    if model.get("kind", "pack") == "pack":
        if release_at_least(install, (1, 3, 1)):
            return None
        return inspect_pack(pathlib.Path(model["path"]))
    sources = inspect_sources(install, [model["path"]])
    return sources[0] if sources else None


def host_support() -> tuple[bool, str]:
    version = platform.mac_ver()[0]
    parts = tuple(int(part) for part in version.split(".")[:2] if part.isdigit()) if version else ()
    if len(parts) >= 2 and parts < MINIMUM_MACOS:
        return False, f"Splash requires macOS {MINIMUM_MACOS[0]}.{MINIMUM_MACOS[1]} or newer; this Mac runs {version}."
    machine = platform.machine()
    if machine != "arm64":
        return False, f"Splash requires Apple silicon; this host reports {machine}."
    return True, f"Splash {VERSION} supports this host."


def install_identity(install: dict[str, Any]) -> str:
    """Stable identity of the engine install, independent of the pack catalog."""
    return hashlib.sha256(json.dumps({
        "version": install.get("version"),
        "release": install.get("release"),
        "engineBinary": install.get("engineBinary"),
        "server": install.get("server"),
        "python": install.get("python"),
    }, sort_keys=True).encode()).hexdigest()


def memory_estimate(pack: dict[str, Any], context: int, *, acceleration: str = "off") -> dict[str, Any]:
    """Conservative working-set estimate for one pack at one context."""
    weights = int(pack.get("weightBytes") or 0)
    if pack.get("ssdStreaming") is True:
        # A catalog placeholder; launch admission replaces this with the
        # current host headroom and the native Metal ceiling.
        budget = MINIMUM_MEMORY_BYTES
        return {
            "version": 1, "modelBytes": 0, "ssdWeightBytes": weights,
            "kvCacheBytes": 0, "kvPrecision": "native · included in memory budget",
            "runtimeReserveBytes": 0,
            "nativeMemoryBudgetBytes": budget,
            "estimatedWorkingSetBytes": budget,
            "contextTokens": int(context), "parallelLanes": 4,
            "ssdStreaming": True, "geometryReady": True,
            "geometry": {"ready": True, "splash": True},
            "basis": "Native memory budget shared by weights, context and expert/PLE caches, "
                     "with runtime allocations charged inside the native budget. SSD weight bytes are not fully resident RAM. "
                     "Launch sizing uses current headroom and the native Metal ceiling, without a fixed 32 GiB cap; Splash checks cache floors, "
                     "the selected context and SSD capacity before loading. This is a budget, "
                     "not a measured process peak.",
        }
    source = pack.get("kind") == "source"
    dspine = acceleration == "dspine"
    reserve = RUNTIME_RESERVE_BYTES
    compact = dspine and context == DSPINE_CONTEXT
    draft = (DSPINE_COMPACT_MEMORY_BYTES if compact else DSPINE_MEMORY_BYTES) if dspine else 0
    if dspine:
        weights = int(pack.get("dspineTargetBytes") or pack.get("targetBytes") or weights)
    kv_per_token = (int(pack["layers"]) // 4 * int(pack["kvHeads"]) * int(pack["headDim"]) * 2 * 65 // 64
                    if source else KV_BYTES_PER_TOKEN)
    kv = max(0, int(context)) * kv_per_token
    working = weights + kv + reserve + draft
    return {
        "version": 1,
        "modelBytes": weights,
        **({"companionBytes": draft, "companionLabels": ["Compact DSpine draft" if compact else "BF16 DSpine draft"]} if dspine else {}),
        "kvCacheBytes": kv,
        "kvPrecision": "engine-owned paged INT8 KV",
        "runtimeReserveBytes": reserve,
        "estimatedWorkingSetBytes": working,
        "contextTokens": int(context),
        "parallelLanes": 1 if dspine else 4,
        "geometryReady": True,
        "geometry": {"ready": True, "splash": True},
        "basis": (
            ("Text target bytes and DSpine sidecar; " if dspine else
             "Local target bytes plus a conservative DFlash2 allowance; " if source else
             "Packed target+draft+vision bytes from manifest.json plus ") +
            f"{kv_per_token} bytes/token of paged INT8 KV from "
            "the model's attention geometry (or the measured legacy plan), "
            "plus a 2 GiB runtime reserve. Splash's native planner "
            "rechecks the selected context before loading." +
            (f" Includes {draft / 1024**3:g} GiB for the running DSpine draft and its workspace." if dspine else "")
        ),
    }


def doctor(install: dict[str, Any], context: int, options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate one launch request and return the plan the launcher records."""
    options = options or {}
    if options.get("acceleration") == "dspine":
        if context not in DSPINE_CONTEXTS or install["release"].get("launcherPatch") != DSPINE_PATCH:
            raise ValueError("DSpine needs its verified Splash build and a supported context window up to 256K.")
    elif context not in CONTEXTS:
        raise ValueError("Splash supports fixed context windows: " + ", ".join(f"{value:,}" for value in CONTEXTS) + ".")
    if install.get("ready") is not True:
        raise ValueError("The Splash install failed its release hash check. Reinstall with Homebrew.")
    packs = install.get("packs") or []
    return {
        "version": str(install.get("version") or VERSION),
        "context": context,
        "packs": len(packs),
        "engineBinary": install.get("engineBinary"),
        "release": install.get("release"),
        "options": dict(options),
    }


def require_route(binary, pack, context, options):
    if options.get("acceleration") == "dspine":
        install = inspect_dspine_install(pack)
        if not install:
            raise ValueError("DSpine's verified runtime or local draft files are unavailable. Rescan models.")
    else:
        install = inspect_install(binary)
    if install is None or install.get("ready") is not True:
        raise ValueError("The Splash install failed its release hash check. Reinstall with Homebrew.")
    current = inspect_model(install, pack)
    if current is None or current.get("identity") != pack.get("identity"):
        raise ValueError("The Splash model changed after the last scan. Rescan models before launching.")
    doctor(install, context, options)
    return install, current


def planning_arguments(install: dict[str, Any], pack: dict[str, Any], context: int, *, port: int, host: str = "127.0.0.1", served_id: str | None = None, output: int = DEFAULT_OUTPUT, max_memory: str = "auto", model_root: str | None = None, acceleration: str = "off") -> list[str]:
    """Exact argv for the engine server (pure so tests can pin it)."""
    root = pathlib.Path(model_root or pack["path"])
    model_id = served_id or pack["id"]
    if not OWNER_REPO.match(model_id):
        raise ValueError(f"Splash needs an owner/repo model id; got {model_id!r}.")
    if isinstance(output, bool) or not isinstance(output, int) or not 256 <= output <= min(OUTPUT_MAXIMUM, context - 1_024):
        raise ValueError("Splash Max response must leave at least 1,024 context tokens for the prompt.")
    modern = upstream_supported(install)
    native = native_supported(install)
    dspine = acceleration == "dspine"
    if pack.get("kind", "pack") == "pack" and release_at_least(install, (1, 3, 1)):
        raise ValueError("Splash 1.3.1 and newer require the original GGUF or MLX checkpoint; rescan models.")
    if pack.get("kind") == "source" and not modern:
        raise ValueError("Update Splash to 1.2.1 to load local GGUF and MLX models.")
    return [
        *([str(install["python"]), "-I", "-B", "-u", "-c", NATIVE_SERVER_BOOTSTRAP, str(install["libexec"])]
          if native else [str(install["python"]), "-u", str(pathlib.Path(__file__).with_name("splash_reasoning.py")), str(install["server"])]),
        *([str(root)] if modern else [str(root / "target"), str(root / "draft")]),
        *([] if native else ["--tokenizer", str(root / "tokenizer")]),
        "--model", model_id,
        "--binary", str(install["engineBinary"]),
        "--max-context", str(context),
        "--max-memory", max_memory,
        *(["--thinking-token-budget", str(min(32_768, output // 2))] if native else []),
        *(["--disable-ane", "--max-cache-disk", "0"] if dspine else []),
        *([] if modern else ["--max-new-tokens", str(output)]),
        # The native default is a 30-minute total request deadline. Give long
        # responses room at 10 tok/s plus that preparation/prefill allowance;
        # this is timeout headroom, not a promised generation speed.
        "--request-timeout", str(1_800 + (output + 9) // 10),
        "--queue-size", str(1 if dspine else QUEUE_DEFAULT),
        "--host", host,
        "--port", str(port),
        "--no-webui",
    ]


def clean_environment(env: dict[str, str]) -> dict[str, str]:
    """Strip launcher-injected knobs; the engine takes only its own argv."""
    cleaned = dict(env)
    for key in list(cleaned):
        if key.startswith(("SPLASH_", "MLX_", "MTPLX_", "SLOTSTREAM_")) and key != "SPLASH_API_KEY":
            cleaned.pop(key, None)
    return cleaned


def validate_served_catalog(data: Any, served_id: str) -> None:
    models = data.get("data") if isinstance(data, dict) else None
    if not isinstance(models, list):
        raise ValueError("Splash /v1/models did not return a model list.")
    identifiers = {item.get("id") for item in models if isinstance(item, dict)}
    if served_id not in identifiers:
        raise ValueError(f"Splash is not serving {served_id!r}.")


def model_record(install: dict[str, Any], pack: dict[str, Any], engines: list[tuple[str, str]], installed_memory: int) -> dict[str, Any]:
    """Launcher model record for a compatible local checkpoint or pack."""
    source = pack.get("kind") == "source"
    if source:
        pack = {**pack, "weightBytes": pack["targetBytes"] + int(pack.get("visionBytes") or 0) + (2 if pack["hiddenSize"] == 5120 else 1) * 1024**3,
                "ssdStreaming": bool(native_supported(install) and (pack.get("expertCount") or "Flash-Next" in pack["family"] or "35B" in pack["family"])),
                "geometry": {"maximum_batch_width": 4}, "artifactSetSha256": ""}
    label = f"{pack['name']} · Splash"
    fingerprint = hashlib.sha256(json.dumps(
        [VERSION, pack["identity"], install.get("release")], sort_keys=True,
    ).encode()).hexdigest()
    runtime_version = f"Splash {install.get('version') or VERSION}"
    support, support_reason = host_support()
    ready = bool(install.get("ready") and support and (not source or upstream_supported(install)))
    quantization = pack["quantization"] if source else "4-bit group 64 target (engine-packed)"
    if source and pack.get("plePrecision") not in (None, "unknown"):
        quantization += f" · {pack['plePrecision']} PLE"
    reason = (support_reason if not support else
              "Update Splash to 1.2.1 for local GGUF and MLX models." if source and not upstream_supported(install) else
              f"{runtime_version} · {quantization} target + matching DFlash2 draft.")
    backends: dict[str, Any] = {}
    for engine, engine_label in engines:
        native = engine == "splash"
        backends[engine] = {
            "runnable": native and ready,
            "reason": reason if native else f"Select the original local model entry to use {engine_label}; this entry is the Splash route.",
            "mtp": False,
            "mtpReason": "Splash decodes with its packaged DFlash 2 draft instead of an MTP head.",
            "dflash": native and ready,
            "dflashReason": "Splash pairs the matching DFlash2 draft; the target verifies its proposals.",
            "kv": False,
            "kvChoices": ["off"],
            "preferredAcceleration": "off",
            "fallbackAcceleration": "off",
            "depth": 1,
            "depthMax": 1,
            "agentReasoning": REASONING if native else ["auto"],
            "codexReasoning": ["auto"],
            "runtimeVersion": runtime_version if native else "Not applicable",
            "benchmarkModelFingerprint": fingerprint,
            "localBenchmark": None,
            "localBenchmarks": [],
            "benchmarkHistoryCount": 0,
            "implicitSamplingDefaultsVerified": False,
            "customSampling": True,
            "samplingFields": (["temperature", "top_p", "top_k", "presence_penalty", "frequency_penalty", "repetition_penalty", "seed"]
                               if upstream_supported(install) else ["temperature", "top_p", "top_k", "seed"]),
            "samplingReason": ("Splash accepts sampling controls and seed per request." if upstream_supported(install) else
                "Splash accepts temperature, top_p and top_k (1-32) per request; "
                "presence/frequency/min_p penalties must stay zero and seed is ignored."
            ),
        }
        if native:
            estimate = memory_estimate(pack, DEFAULT_CONTEXT)
            backends[engine].update({
                "modelPath": pack["path"],
                "contextWindows": list(CONTEXTS),
                "contextMaximum": CONTEXT_MAXIMUM,
                "outputMaximum": OUTPUT_MAXIMUM,
                "memoryEstimate": estimate,
                "installedMemoryBytes": installed_memory,
                "input": ['text', 'image'] if pack.get('visionFormat') not in (None, 'none') else ['text'],
                "vision": copy.deepcopy(pack.get('vision')),
            })
            if dspine_target(pack):
                dspine_install = inspect_dspine_install(pack) if ready else None
                if dspine_install:
                    pack["dspineTargetBytes"] = dspine_target_bytes(dspine_install, pack)
                available = dspine_install is not None
                backends[engine].update({
                    "dspine": available,
                    "dspineContext": DSPINE_CONTEXT,
                    "dspineContexts": list(DSPINE_CONTEXTS),
                    "dspineOutput": DSPINE_OUTPUT,
                    "dspineReason": (
                        "Experimental DSpine supports greedy Chat and oh-my-pi with up to 256K context."
                        if available else "The local DSpine runtime or draft files are unavailable."
                    ),
                })
    return {
        "id": "splash-" + re.sub(r"[^a-z0-9]+", "-", pack["id"].lower()).strip("-")
              + "-" + hashlib.sha256(pack["id"].encode()).hexdigest()[:12],
        "name": label,
        "path": pack["path"],
        "artifact": f"splash:{pack['artifactSetSha256'][:24] or pack['identity'][:24]}",
        "origins": ["Splash · " + pack["id"]],
        "format": ("GGUF" if pack.get("format") == "gguf" else "MLX") if source else "Splash packed Q4 + DFlash 2 draft",
        "architecture": pack.get("family") or pack["name"],
        "modelType": ("splash-qwen38-flash-next" if "Flash-Next" in (pack.get("family") or pack["name"]) else
                      "splash-qwen35-moe" if "35B" in (pack.get("family") or pack["name"]) else "splash-qwen38-27b"),
        "nativeContext": pack.get("nativeContext") or CONTEXT_MAXIMUM,
        "defaultContext": DEFAULT_CONTEXT,
        "defaultOutput": DEFAULT_OUTPUT,
        "outputMaximum": OUTPUT_MAXIMUM,
        "defaultReasoning": "medium",
        "quantization": quantization,
        "size": pack["weightBytes"],
        "sizeLabel": f"{pack['weightBytes'] / 1024**3:.1f} GiB",
        "memoryGeometry": {"ready": True, "splash": True},
        "mtpSidecarSize": 0,
        "ready": ready,
        "status": "Installed · Splash headers checked" if source else "Installed · release hashes checked" if install.get("ready") else "Splash install failed its hash check",
        "mtp": {"declared": False, "integrated": False, "sidecar": False},
        "templateReasoningEfforts": ["low", "medium", "xhigh"],
        "defaultSampling": {},
        "lmKey": pack["id"],
        "remoteModelId": pack["id"],
        "sharedServer": False,
        "remote": False,
        "splash": copy.deepcopy(pack),
        "backends": backends,
    }


def run_with_dspine(argv: list[str], env: dict[str, str], target: pathlib.Path, *, compact: bool = False) -> None:
    """Own both workers for the lifetime of the launcher session."""
    stopping = False

    def request_stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    def stop(process):
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    previous = {sig: signal.signal(sig, request_stop) for sig in (signal.SIGTERM, signal.SIGINT)}
    frontend = sidecar = None
    try:
        with tempfile.TemporaryDirectory(prefix="llm-dspine-", dir="/tmp") as private_dir:
            path = pathlib.Path(private_dir) / "draft.sock"
            draft_env = dict(env, PYTHONPATH=str(DSPINE_HOME / "tencent/dspine_mlx"))
            draft_env.pop("SPLASH_API_KEY", None)
            try:
                sidecar = subprocess.Popen([
                    str(DSPINE_PYTHON), "-B", "-s", "-u", str(DSPINE_SIDECAR),
                    "--socket", str(path), "--target", str(target),
                    "--draft", str(DSPINE_HOME / "weights"), "--parent-pid", str(os.getpid()),
                    *(["--compact"] if compact else []),
                ], env=draft_env, stdin=subprocess.DEVNULL)
                deadline = time.monotonic() + 90
                while not stopping:
                    if sidecar.poll() is not None:
                        raise ValueError(f"DSpine drafter exited at startup ({sidecar.returncode}).")
                    if path.exists() and stat.S_IMODE(path.stat().st_mode) == 0o600:
                        break
                    if time.monotonic() >= deadline:
                        raise TimeoutError("DSpine drafter did not become ready.")
                    time.sleep(0.05)
                if stopping:
                    return
                frontend = subprocess.Popen(argv, env=dict(
                    env, SPLASH_EXPERIMENTAL_DSPINE_SOCKET=str(path), SPLASH_APP_PID=str(os.getpid()),
                ), stdin=subprocess.DEVNULL)
                while not stopping:
                    status = frontend.poll()
                    if status is not None:
                        if status:
                            raise SystemExit(status)
                        return
                    if sidecar.poll() is not None:
                        raise ValueError(f"DSpine drafter exited during the session ({sidecar.returncode}).")
                    time.sleep(0.1)
            finally:
                try:
                    stop(frontend)
                finally:
                    stop(sidecar)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def run_verified(config_path: pathlib.Path) -> None:
    """Re-verify the install, then replace this process with the engine server."""
    config = read_json(config_path)
    if not isinstance(config, dict):
        raise ValueError("Splash launch config could not be read.")
    install = config["install"]
    dspine = config.get("acceleration") == "dspine"
    current = inspect_install(install["engineBinary"])
    if current is None or install_identity(current) != install_identity(install) or not install.get("ready"):
        raise ValueError("Splash changed before startup. Rescan before launching.")
    pack = inspect_model(current, config["pack"])
    if pack is None or pack["identity"] != config["pack"]["identity"]:
        raise ValueError("Splash model changed before startup. Rescan before launching.")
    model_root = None
    if dspine:
        doctor(current, int(config["context"]), {"acceleration": "dspine"})
        draft = DSPINE_HOME / "weights/model.safetensors"
        # Stream the startup verification without filling the file cache.
        if inspect_dspine_install(pack) != current or digest(draft, cache=False) != DSPINE_DRAFT_SHA256:
            raise ValueError("DSpine's local runtime or draft changed before startup. Rescan models.")
    if pack.get("kind") == "source":
        process = subprocess.run(
            [str(install["python"]), "-I", "-B", str(SOURCE_HELPER), str(install["libexec"]),
             "prepare-dspine" if dspine else "prepare"],
            input=json.dumps({"source": pack, "destination": str(config.get("modelsRoot") or config_path.parent / "splash-models"),
                              "drafts": config.get("drafts", [])}),
            text=True, stdout=subprocess.PIPE, env=clean_environment(dict(os.environ)),
        )
        if process.returncode:
            raise ValueError("Splash could not prepare this local model and its matching draft.")
        model_root = json.loads(process.stdout.splitlines()[-1])["root"]
    argv = planning_arguments(
        install, config["pack"], int(config["context"]),
        port=int(config["port"]), served_id=config.get("servedId"),
        output=config.get("output", DEFAULT_OUTPUT),
        max_memory=str(config.get("maxMemory") or "auto"),
        model_root=model_root,
        acceleration="dspine" if dspine else "off",
    )
    env = clean_environment(dict(os.environ))
    if dspine:
        run_with_dspine(argv, env, pathlib.Path(pack["path"]), compact=int(config["context"]) == DSPINE_CONTEXT)
        return
    if (
        current["release"].get("launcherPatch") == M5_PRO_DECODE_PATCH
        and pack.get("family") == "Qwen3.8-27B"
        and pack.get("format") == "mlx-affine"
    ):
        env["SPLASH_EXPERIMENTAL_PROMPT_LOOKUP"] = "fixed16"
    os.execve(argv[0], argv, env)


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 2:
        run_verified(pathlib.Path(sys.argv[1]))
    else:
        print(json.dumps({
            "install": inspect_install(),
            "packs": [{"id": pack["id"], "bytes": pack["weightBytes"]} for pack in discover_packs()],
        }, indent=2))
