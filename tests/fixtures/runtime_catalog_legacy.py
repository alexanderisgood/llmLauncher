"""Frozen original runtime preview algorithms. Test oracle; never production imported."""
from __future__ import annotations
import copy, hashlib, json, math, os, platform, plistlib, re, secrets, stat, statistics, subprocess, sys, time, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import launcher as current
RUNTIME_CANDIDATE_SPECS = current.RUNTIME_CANDIDATE_SPECS
RUNTIME_APP_SPECS = current.RUNTIME_APP_SPECS
RUNTIME_PREFERENCES_VERSION = current.RUNTIME_PREFERENCES_VERSION
LLAMACPP_RUNTIME_TAG = current.LLAMACPP_RUNTIME_TAG
RUNTIME_RELEASE_CATALOG = current.RUNTIME_RELEASE_CATALOG
RUNTIME_RELEASE_CATALOG_AUDITED_AT = current.RUNTIME_RELEASE_CATALOG_AUDITED_AT
RUNTIME_RELEASE_CATALOG_VERSION = current.RUNTIME_RELEASE_CATALOG_VERSION
RUNTIME_UPDATE_CATALOG = current.RUNTIME_UPDATE_CATALOG
RUNTIME_UPDATE_ARCHIVE = current.RUNTIME_UPDATE_ARCHIVE
RUNTIME_UPDATE_CATALOG_AUDITED_AT = current.RUNTIME_UPDATE_CATALOG_AUDITED_AT
RUNTIME_UPDATE_MANIFEST = current.RUNTIME_UPDATE_MANIFEST
RUNTIME_UPDATE_SCHEMA_VERSION = current.RUNTIME_UPDATE_SCHEMA_VERSION
RUNTIME_UPDATE_ESTIMATED_INSTALL_BYTES = current.RUNTIME_UPDATE_ESTIMATED_INSTALL_BYTES
RUNTIME_UPDATE_DISK_RESERVE_BYTES = current.RUNTIME_UPDATE_DISK_RESERVE_BYTES
DFLASH2_MINIMUM_RUNTIME = current.DFLASH2_MINIMUM_RUNTIME
DFLASH2_RECOMMENDED_RUNTIME = current.DFLASH2_RECOMMENDED_RUNTIME
ANE_TUNER_MINIMUM_RUNTIME = current.ANE_TUNER_MINIMUM_RUNTIME
MTPLX_AGENT_RECOMMENDED_RUNTIME = current.MTPLX_AGENT_RECOMMENDED_RUNTIME
OMLX_INSTALL_URL = current.OMLX_INSTALL_URL
OMLX_INSTALL_DOCS_URL = current.OMLX_INSTALL_DOCS_URL
LMSTUDIO_UPDATE_DOCS_URL = current.LMSTUDIO_UPDATE_DOCS_URL
LMSTUDIO_RUNTIME_DOCS_URL = current.LMSTUDIO_RUNTIME_DOCS_URL
MTPLX_INSTALL_DOCS_URL = current.MTPLX_INSTALL_DOCS_URL
SSD_STREAMING_RUNTIME_URLS = current.SSD_STREAMING_RUNTIME_URLS
UZU_RUNTIME_TAG = current.UZU_RUNTIME_TAG
UZU_RUNTIME_UPSTREAM_TAG = current.UZU_RUNTIME_UPSTREAM_TAG
UZU_RUNTIME_UPSTREAM_COMMIT = current.UZU_RUNTIME_UPSTREAM_COMMIT
UZU_RUNTIME_SOURCE_PATCH_SHA256 = current.UZU_RUNTIME_SOURCE_PATCH_SHA256
UZU_RUNTIME_RELEASE_URL = current.UZU_RUNTIME_RELEASE_URL
UZU_MODEL_PAGE_URL = current.UZU_MODEL_PAGE_URL
RUNTIME_PROMOTION_SCHEMA_VERSION = current.RUNTIME_PROMOTION_SCHEMA_VERSION
RUNTIME_PROMOTION_MAX_AGE_DAYS = current.RUNTIME_PROMOTION_MAX_AGE_DAYS
BENCHMARK_MINIMUM_SPEEDUP = current.BENCHMARK_MINIMUM_SPEEDUP
BENCHMARK_MEMORY_MEANINGFUL_BYTES = current.BENCHMARK_MEMORY_MEANINGFUL_BYTES
BENCHMARK_COMPARISON_CONTRACT_VERSION = current.BENCHMARK_COMPARISON_CONTRACT_VERSION
MANAGED_RUNTIMES_DIR = current.MANAGED_RUNTIMES_DIR
LLAMACPP_SERVER_PATH = current.LLAMACPP_SERVER_PATH
BINARIES = current.BINARIES
_RUNTIME_KERNEL_CACHE = {}

def executable(*args, **kwargs):
    return current.executable(*args, **kwargs)

def command_version(*args, **kwargs):
    return current.command_version(*args, **kwargs)

def _lmstudio_cache_document(*args, **kwargs):
    return current._lmstudio_cache_document(*args, **kwargs)

def lmstudio_mtp_load_supported(*args, **kwargs):
    return current.lmstudio_mtp_load_supported(*args, **kwargs)

def lmstudio_assistant_drafter_load_supported(*args, **kwargs):
    return current.lmstudio_assistant_drafter_load_supported(*args, **kwargs)

def lmstudio_assistant_drafter_runtime_contract(*args, **kwargs):
    return current.lmstudio_assistant_drafter_runtime_contract(*args, **kwargs)

def llamacpp_runtime_contract(*args, **kwargs):
    return current.llamacpp_runtime_contract(*args, **kwargs)

def uzu_runtime_contract(*args, **kwargs):
    return current.uzu_runtime_contract(*args, **kwargs)

def uzu_listener_protection_ready(*args, **kwargs):
    return current.uzu_listener_protection_ready(*args, **kwargs)

def runtime_executable_revision(*args, **kwargs):
    return current.runtime_executable_revision(*args, **kwargs)

def read_json(*args, **kwargs):
    return current.read_json(*args, **kwargs)

def disk_free_for(*args, **kwargs):
    return current.disk_free_for(*args, **kwargs)

def display_size(*args, **kwargs):
    return current.display_size(*args, **kwargs)

def validated_benchmark_request(*args, **kwargs):
    return current.validated_benchmark_request(*args, **kwargs)

def hardware_fingerprint(*args, **kwargs):
    return current.hardware_fingerprint(*args, **kwargs)

def load_runtime_promotion_records(*args, **kwargs):
    return current.load_runtime_promotion_records(*args, **kwargs)

def benchmark_measurement_count(*args, **kwargs):
    return current.benchmark_measurement_count(*args, **kwargs)

def sampling_record_evidence(*args, **kwargs):
    return current.sampling_record_evidence(*args, **kwargs)

def cross_engine_benchmark_measurement(*args, **kwargs):
    return current.cross_engine_benchmark_measurement(*args, **kwargs)

def route_qualification_memory_admission(*args, **kwargs):
    return current.route_qualification_memory_admission(*args, **kwargs)

def strict_model_load_admission_ready(*args, **kwargs):
    return current.strict_model_load_admission_ready(*args, **kwargs)

def launcher_managed_runtime_specs(runtime: str) -> tuple[tuple[str, str, str], ...]:
    """Discover isolated, versioned runtimes installed for this launcher."""
    if runtime == "llamacpp":
        return ((
            "launcher-managed", str(LLAMACPP_SERVER_PATH),
            f"Launcher-managed llama.cpp {LLAMACPP_RUNTIME_TAG}",
        ),)
    if runtime != "omlx":
        return ()
    try:
        paths = sorted(
            MANAGED_RUNTIMES_DIR.glob("omlx-*/bin/omlx"),
            key=lambda item: item.parent.parent.name.lower(),
        )
    except OSError:
        return ()
    result: list[tuple[str, str, str]] = []
    for path in paths:
        version = path.parent.parent.name.removeprefix("omlx-")
        label = f"Launcher-managed {version}" if version else "Launcher-managed oMLX"
        result.append(("launcher-managed", str(path), label))
    return tuple(result)

def runtime_candidates(runtime: str) -> list[dict[str, str]]:
    """Return known installed runtime entry points, deduplicated by target."""
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    specs = (
        *RUNTIME_CANDIDATE_SPECS.get(runtime, ()),
        *launcher_managed_runtime_specs(runtime),
    )
    for channel, requested, label in specs:
        path = executable([requested])
        if not path:
            continue
        try:
            resolved = str(Path(path).expanduser().resolve(strict=True))
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        candidate_id = hashlib.sha256(
            f"{runtime}\0{resolved}".encode("utf-8", "replace")
        ).hexdigest()[:16]
        candidates.append({
            "id": candidate_id,
            "runtime": runtime,
            "path": str(Path(path).expanduser()),
            "resolvedPath": resolved,
            "channel": channel,
            "channelLabel": label,
        })
    return candidates

def lmstudio_backend_preference(path: Path | None = None) -> dict[str, Any]:
    """Read the one engine pack LM Studio selected for GGUF models."""
    source = path or (
        Path.home() / ".lmstudio" / ".internal" / "backend-preferences-v1.json"
    )
    value, identity = _lmstudio_cache_document(source)
    if not isinstance(value, list) or len(value) > 32:
        return {"ready": False, "reason": "LM Studio has no valid GGUF engine preference."}
    matches = [
        item for item in value
        if isinstance(item, dict) and item.get("model_format") == "gguf"
    ]
    if len(matches) != 1:
        return {"ready": False, "reason": "LM Studio's selected GGUF engine is ambiguous."}
    selected = matches[0]
    name = selected.get("name")
    version = selected.get("version")
    if (
        not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,180}", name)
        or not isinstance(version, str) or semantic_version_key(version) == (-1, -1, -1, -1)
    ):
        return {"ready": False, "reason": "LM Studio's selected GGUF engine is invalid."}
    return {
        "ready": True, "name": name, "version": version,
        "sourceFingerprint": identity.get("sha256"),
    }

def lmstudio_runtime_identity(
    cli_version: str, app_version: str | None,
    packs: list[dict[str, str]],
) -> str:
    """Bind benchmark evidence to the app and every installed MLX pack."""
    mlx_packs = sorted(
        {
            f"{str(item.get('name') or '')}@{str(item.get('version') or 'Unknown')}"
            for item in packs if item.get("kind") == "MLX" and item.get("name")
        },
    )
    pack_contract = "\n".join(mlx_packs)
    pack_digest = hashlib.sha256(pack_contract.encode("utf-8")).hexdigest()[:12] if pack_contract else "none"
    versions = ",".join(sorted({item.rsplit("@", 1)[-1] for item in mlx_packs})) or "missing"
    return (
        f"{str(cli_version or 'CLI unknown')[:100]} · app {app_version or 'unknown'} "
        f"· MLX {versions} · packs {pack_digest}"
    )[:320]

def parsed_omlx_version(version_text: str) -> tuple[int, int, int, int] | None:
    """Parse stable, RC and numbered development releases without conflating them."""
    match = re.search(
        r"(?<![\d.])(\d+)\.(\d+)\.(\d+)(?:rc(\d+)|\.dev(\d+))?(?=$|[^A-Za-z0-9.])",
        version_text,
        re.IGNORECASE,
    )
    if not match:
        return None
    release_candidate = match.group(4)
    development = match.group(5)
    # Preserve RC ordering while placing numbered development builds before RCs.
    stage = (-1_000_000 + int(development) if development is not None else
             1_000_000 if release_candidate is None else int(release_candidate))
    return tuple(int(match.group(index)) for index in (1, 2, 3)) + (stage,)

def omlx_version_at_least(version_text: str, minimum: str) -> bool:
    current = parsed_omlx_version(version_text)
    required = parsed_omlx_version(minimum)
    return current is not None and required is not None and current >= required

def omlx_supports_dflash2(version_text: str) -> bool:
    """DFlash 2 first appears in the official 0.6.3rc1 release."""
    return omlx_version_at_least(version_text, DFLASH2_MINIMUM_RUNTIME)

def omlx_has_recommended_dflash2_runtime(version_text: str) -> bool:
    """0.6.4 is the current audited stable DFlash/Lightning-MTP build."""
    return omlx_version_at_least(version_text, DFLASH2_RECOMMENDED_RUNTIME)

def plist_version(path: Path) -> str | None:
    try:
        with open(path, "rb") as handle:
            value = plistlib.load(handle).get("CFBundleShortVersionString")
    except (OSError, ValueError, plistlib.InvalidFileException):
        return None
    return str(value)[:80] if value is not None else None

def runtime_app_status(runtime: str) -> dict[str, Any]:
    """Identify one explicitly supported macOS app without starting it."""
    spec = RUNTIME_APP_SPECS.get(runtime)
    if not spec:
        return {"available": False, "runtime": runtime}
    label = str(spec["label"])
    allowed_bundle_ids = set(spec["bundleIds"])
    for requested in spec["paths"]:
        bundle = Path(str(requested)).expanduser()
        try:
            resolved = bundle.resolve(strict=True)
            if not resolved.is_dir() or resolved.suffix != ".app":
                continue
            with open(resolved / "Contents" / "Info.plist", "rb") as handle:
                metadata = plistlib.load(handle)
        except (OSError, ValueError, plistlib.InvalidFileException):
            continue
        bundle_id = metadata.get("CFBundleIdentifier")
        executable_name = metadata.get("CFBundleExecutable")
        if (
            bundle_id not in allowed_bundle_ids
            or not isinstance(executable_name, str)
            or not executable_name
            or len(executable_name) > 160
            or "/" in executable_name
            or "\0" in executable_name
        ):
            continue
        executable_path = resolved / "Contents" / "MacOS" / executable_name
        if not executable_path.is_file() or not os.access(executable_path, os.X_OK):
            continue
        version = metadata.get("CFBundleShortVersionString")
        return {
            "available": True,
            "runtime": runtime,
            "label": label,
            "path": str(bundle),
            "resolvedPath": str(resolved),
            "bundleId": str(bundle_id),
            "version": str(version)[:80] if version is not None else "Installed",
        }
    return {
        "available": False,
        "runtime": runtime,
        "label": label,
    }

def semantic_version_key(text: str) -> tuple[int, int, int, int]:
    return parsed_omlx_version(text) or (-1, -1, -1, -1)

def runtime_release_key(runtime: str, text: str) -> tuple[int, int, int, int]:
    """Parse the audited version scheme used by one runtime, or fail closed."""
    if runtime == "swiftlm":
        match = re.search(r"(?<![A-Za-z0-9])b(\d+)(?!\d)", text, re.IGNORECASE)
        return (int(match.group(1)), 0, 0, 1_000_000) if match else (-1, -1, -1, -1)
    return semantic_version_key(text)

def audited_runtime_release(runtime: str, installed_version: str | None) -> dict[str, Any]:
    """Compare one local runtime with the launcher's last audited official release."""
    release = copy.deepcopy(RUNTIME_RELEASE_CATALOG.get(runtime) or {})
    if not release:
        raise ValueError("No audited release catalog exists for this runtime.")
    installed = str(installed_version or "").strip()[:160]
    preview = RUNTIME_UPDATE_CATALOG["preview"]
    if runtime == "omlx" and _exact_omlx_version(installed, preview["version"]):
        release.update({
            **{key: copy.deepcopy(preview[key]) for key in (
                "version", "channel", "releasedAt", "releaseUrl", "summary", "commit",
            )},
            "displayVersion": preview["version"],
            "highlights": [
                {"value": "Preview", "label": "release channel"},
                {"value": "Flash-Next", "label": "decode and prefill optimizations"},
                {"value": "Expert SSD", "label": "configurable resident expert cache"},
            ],
            "workflow": ["Select the installed preview in Engine versions to try it; the stable copy remains available."],
        })
    current_key = runtime_release_key(runtime, installed)
    release_key = runtime_release_key(runtime, str(release.get("version") or ""))
    if not installed:
        state = "not-installed"
        label = "Not installed"
        detail = f"Audited upstream release {release['displayVersion']} is available."
    elif current_key == (-1, -1, -1, -1):
        state = "unknown-local-version"
        label = "Review version"
        detail = (
            f"The selected version could not be compared with audited release "
            f"{release['displayVersion']}."
        )
    elif current_key < release_key:
        state = "update-available"
        label = "Update available"
        detail = (
            f"Audited upstream release {release['displayVersion']} is newer than "
            f"the selected {installed}."
        )
    elif current_key > release_key:
        state = "newer-unreviewed"
        label = "Newer than catalog"
        detail = (
            f"The selected {installed} is newer than audited release "
            f"{release['displayVersion']}; no current-release claim is made."
        )
    else:
        state = "current"
        label = "Audited current"
        detail = f"The selected runtime matches audited release {release['displayVersion']}."
    active_advisory = next((
        copy.deepcopy(item)
        for item in release.get("advisories", [])
        if isinstance(item, dict)
        and current_key != (-1, -1, -1, -1)
        and current_key == runtime_release_key(
            runtime, str(item.get("affectedVersion") or ""),
        )
    ), None)
    release.update({
        "schemaVersion": RUNTIME_RELEASE_CATALOG_VERSION,
        "auditedAt": (RUNTIME_UPDATE_CATALOG_AUDITED_AT
                      if runtime == "omlx" and release.get("channel") == "preview"
                      else RUNTIME_RELEASE_CATALOG_AUDITED_AT),
        "installedVersion": installed or None,
        "state": state, "label": label, "detail": detail,
        "updateAvailable": state == "update-available",
        "catalogCurrent": state == "current",
        "activeAdvisory": active_advisory,
        "needsReview": state != "current" or active_advisory is not None,
    })
    return release

def launch_runtime_advisory(backend: str, model: dict[str, Any]) -> dict[str, Any] | None:
    """Expose a bounded route warning only when an installed runtime has a known session risk."""
    capability = model.get("backends", {}).get(backend, {})
    runtime_version = str(capability.get("runtimeVersion") or "")[:160]
    version_match = re.search(r"(?<![\d.])\d+\.\d+\.\d+(?:rc\d+)?", runtime_version, re.IGNORECASE)
    version_label = version_match.group(0) if version_match else runtime_version
    if (
        backend == "mtplx"
        and semantic_version_key(runtime_version) < semantic_version_key(MTPLX_AGENT_RECOMMENDED_RUNTIME)
        and semantic_version_key(runtime_version) != (-1, -1, -1, -1)
    ):
        return {
            "id": "mtplx-long-agent-update",
            "level": "warning",
            "title": "Update MTPLX for safer long agent runs",
            "detail": (
                f"MTPLX {version_label} is selected. Upstream {MTPLX_AGENT_RECOMMENDED_RUNTIME} "
                "includes hardware-gated 27B attention plus warm-turn, postcommit, "
                "session-bank and memory fixes. Open Tools → Runtimes before relying on a hard Pi, "
                "OpenCode, or Codex task."
            ),
            "releaseUrl": RUNTIME_RELEASE_CATALOG["mtplx"]["releaseUrl"],
        }
    return None

def omlx_kernel_artifacts(binary: str | None) -> list[Path]:
    """Find the native Qwen kernel extension without importing Metal."""
    if not binary:
        return []
    try:
        original = Path(binary).expanduser().resolve(strict=True)
    except OSError:
        return []
    patterns: list[Path] = []
    # Homebrew/source virtual environments resolve to .../bin/omlx.
    environment = original.parent.parent
    patterns.extend(environment.glob(
        "lib/python*/site-packages/omlx/custom_kernels/qwen35_prefill/_ext*.so"
    ))
    # The signed app puts the package either directly in Resources or in a
    # venvstacks framework layer. Keep the walk inside this one known bundle.
    parts = original.parts
    app_index = next((index for index, part in enumerate(parts) if part.endswith(".app")), None)
    if app_index is not None:
        app = Path(*parts[:app_index + 1])
        resources = app / "Contents" / "Resources"
        if resources.is_dir():
            patterns.extend(resources.glob(
                "**/omlx/custom_kernels/qwen35_prefill/_ext*.so"
            ))
    unique: dict[str, Path] = {}
    for item in patterns:
        try:
            if item.is_file():
                unique[str(item.resolve(strict=True))] = item
        except OSError:
            continue
    return list(unique.values())

def omlx_runtime_python(binary: str | None) -> str | None:
    if not binary:
        return None
    try:
        original = Path(binary).expanduser().resolve(strict=True)
    except OSError:
        return None
    candidates = [original.parent / "python", original.parent / "python3"]
    parts = original.parts
    app_index = next((index for index, part in enumerate(parts) if part.endswith(".app")), None)
    if app_index is not None:
        app = Path(*parts[:app_index + 1])
        candidates.extend([
            app / "Contents" / "Resources" / "Python" / "cpython-3.11" / "bin" / "python3",
            app / "Contents" / "Resources" / "Python" / "cpython-3.12" / "bin" / "python3",
        ])
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None

def omlx_qwen_kernel_status(binary: str | None) -> dict[str, Any]:
    """Require both a native artifact and the upstream runtime self-check."""
    artifacts = omlx_kernel_artifacts(binary)
    if not artifacts:
        return {
            "ready": False,
            "state": "missing",
            "artifactCount": 0,
            "reason": "The selected oMLX installation has no native Qwen prefill kernel.",
        }
    try:
        resolved = str(Path(str(binary)).expanduser().resolve(strict=True))
        signature = max(item.stat().st_mtime_ns for item in artifacts)
    except OSError:
        return {
            "ready": False, "state": "unverified", "artifactCount": len(artifacts),
            "reason": "The Qwen kernel files could not be revalidated.",
        }
    cache_key = (resolved, signature)
    cached = _RUNTIME_KERNEL_CACHE.get(cache_key)
    if cached is not None:
        return copy.deepcopy(cached)
    python = omlx_runtime_python(binary)
    if not python:
        result = {
            "ready": False, "state": "unverified", "artifactCount": len(artifacts),
            "reason": "Native Qwen kernel files exist, but the matching runtime Python was not found.",
        }
        _RUNTIME_KERNEL_CACHE[cache_key] = result
        return copy.deepcopy(result)
    probe = (
        "import json\n"
        "from omlx.custom_kernels import native_kernel_status\n"
        "value = native_kernel_status().get('qwen35_prefill', {})\n"
        "print('__LLM_LAUNCHER_KERNEL__' + json.dumps(value, default=str))\n"
    )
    try:
        completed = subprocess.run(
            [python, "-c", probe], text=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=8, check=False,
        )
        marker = next(
            (line.split("__LLM_LAUNCHER_KERNEL__", 1)[1] for line in completed.stdout.splitlines()
             if "__LLM_LAUNCHER_KERNEL__" in line),
            "",
        )
        value = json.loads(marker) if marker else {}
    except (OSError, subprocess.TimeoutExpired, ValueError, json.JSONDecodeError):
        value = {}
    available = isinstance(value, dict) and value.get("available") is True
    import_error = str(value.get("import_error") or "")[:240] if isinstance(value, dict) else ""
    result = {
        "ready": available,
        "state": "ready" if available else "failed",
        "artifactCount": len(artifacts),
        "reason": (
            "The upstream native-kernel self-check passed for Qwen prefill."
            if available else
            "Native Qwen kernel files exist, but the upstream self-check did not pass."
            + (f" {import_error}" if import_error else "")
        ),
    }
    _RUNTIME_KERNEL_CACHE[cache_key] = result
    return copy.deepcopy(result)

def metal_toolchain_status() -> dict[str, Any]:
    xcrun = executable(["/usr/bin/xcrun", "xcrun"])
    if not xcrun:
        return {"ready": False, "reason": "Apple's xcrun developer tool is unavailable."}
    try:
        completed = subprocess.run(
            [xcrun, "-f", "metal"], text=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=4, check=False,
        )
        path = completed.stdout.strip().splitlines()[0] if completed.returncode == 0 and completed.stdout.strip() else ""
    except (OSError, subprocess.TimeoutExpired):
        path = ""
    return {
        "ready": bool(path),
        "path": path or None,
        "reason": (
            "The full Metal compiler is available for an advanced Homebrew source build."
            if path else
            "The full Metal compiler is missing; Command Line Tools alone cannot build oMLX's native Qwen kernels."
        ),
    }

def _exact_omlx_version(version_text: str, expected: str) -> bool:
    current = parsed_omlx_version(version_text)
    wanted = parsed_omlx_version(expected)
    return current is not None and wanted is not None and current == wanted

def runtime_update_python() -> dict[str, Any]:
    """Find a real CPython 3.11 interpreter for the audited universal wheel."""
    candidates: list[str] = []
    selected = BINARIES.get("omlx")
    selected_python = omlx_runtime_python(selected)
    if selected_python:
        candidates.append(selected_python)
    candidates.extend([
        "/opt/homebrew/opt/python@3.11/bin/python3.11",
        "/opt/homebrew/bin/python3.11",
        "/usr/local/bin/python3.11",
        "python3.11",
    ])
    seen: set[str] = set()
    for requested in candidates:
        path = executable([requested])
        if not path:
            continue
        try:
            resolved = str(Path(path).expanduser().resolve(strict=True))
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            completed = subprocess.run(
                [resolved, "-c", "import platform,sys; print(platform.python_version()); print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=4, check=False,
            )
            lines = completed.stdout.strip().splitlines()
            return_code = completed.returncode
        except (OSError, subprocess.TimeoutExpired):
            lines = []
            return_code = -1
        if return_code == 0 and len(lines) >= 2 and lines[1] == "3.11":
            return {"ready": True, "path": resolved, "version": lines[0]}
    return {
        "ready": False, "path": None, "version": None,
        "reason": "Python 3.11 is required for the audited oMLX wheel and was not found.",
    }

def _runtime_update_release(channel: Any) -> dict[str, Any]:
    key = str(channel or "")
    release = RUNTIME_UPDATE_CATALOG.get(key)
    if not release:
        raise ValueError("Choose the audited stable or preview oMLX track.")
    return copy.deepcopy(release)

def _runtime_update_target(release: dict[str, Any]) -> Path:
    version = str(release["version"])
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:rc\d+|\.dev\d+)?", version):
        raise ValueError("The audited runtime catalog contains an invalid version.")
    return MANAGED_RUNTIMES_DIR.expanduser() / f"omlx-{version}"

def _runtime_update_direct_hash(target: Path, version: str) -> str:
    try:
        matches = list(target.glob(
            f"lib/python3.11/site-packages/omlx-{version}.dist-info/direct_url.json"
        ))
    except OSError:
        return ""
    if len(matches) != 1:
        return ""
    value = read_json(matches[0])
    archive = value.get("archive_info")
    hashes = archive.get("hashes") if isinstance(archive, dict) else None
    digest = str(hashes.get("sha256") or "").lower() if isinstance(hashes, dict) else ""
    return digest if re.fullmatch(r"[0-9a-f]{64}", digest) else ""

def managed_runtime_verification(binary: str | None) -> dict[str, Any]:
    """Report whether a launcher-owned runtime traces to an audited official wheel."""
    if not binary:
        return {"verified": False, "state": "not-managed", "detail": "No executable."}
    try:
        resolved = Path(binary).expanduser().resolve(strict=True)
        target = resolved.parent.parent
        managed_root = MANAGED_RUNTIMES_DIR.expanduser().resolve(strict=False)
    except OSError:
        return {"verified": False, "state": "unavailable", "detail": "The runtime path could not be revalidated."}
    if resolved.name != "omlx" or target.parent.resolve(strict=False) != managed_root:
        return {"verified": False, "state": "not-managed", "detail": "This copy is managed by another installer."}
    release = next(
        (copy.deepcopy(item) for item in (*RUNTIME_UPDATE_CATALOG.values(), *RUNTIME_UPDATE_ARCHIVE.values())
         if target.name == f"omlx-{item['version']}"),
        None,
    )
    if not release:
        return {
            "verified": False, "state": "unknown-release",
            "detail": "This launcher-managed version is not in the audited release catalog.",
        }
    manifest = read_json(target / RUNTIME_UPDATE_MANIFEST)
    manifest_hash = str(manifest.get("artifactSha256") or "").lower()
    direct_hash = _runtime_update_direct_hash(target, str(release["version"]))
    expected = str(release["sha256"])
    provenance_matched = (
        secrets.compare_digest(manifest_hash, expected)
        or secrets.compare_digest(direct_hash, expected)
    )
    final_path_works = _exact_omlx_version(
        command_version(str(resolved)), str(release["version"]),
    )
    verified = provenance_matched and final_path_works
    return {
        "verified": verified,
        "state": (
            "verified" if verified else
            "final-path-failed" if provenance_matched else
            "unverified-provenance"
        ),
        "channel": release["channel"], "version": release["version"],
        "artifactSha256": expected if verified else None,
        "manifest": bool(manifest),
        "detail": (
            "Official release-wheel checksum provenance verified."
            if verified else
            "Official checksum provenance exists, but the final installed command failed its exact version check."
            if provenance_matched else
            "The executable works, but its source checksum cannot be matched to the audited official wheel."
        ),
    }

def build_runtime_update_plan(channel: Any) -> dict[str, Any]:
    """Build a side-effect-free, immutable plan for one audited oMLX release."""
    release = _runtime_update_release(channel)
    target = _runtime_update_target(release)
    root = MANAGED_RUNTIMES_DIR.expanduser()
    root_resolved = root.resolve(strict=False)
    target_exists = target.exists() or target.is_symlink()
    target_symlink = target.is_symlink()
    target_safe = not root.is_symlink() and not target_symlink
    try:
        if target_exists and target.resolve(strict=True).parent != root_resolved:
            target_safe = False
    except OSError:
        target_safe = False

    binary = target / "bin" / "omlx"
    installed_version = command_version(str(binary)) if binary.is_file() and os.access(binary, os.X_OK) else ""
    exact_installed = bool(installed_version and _exact_omlx_version(installed_version, str(release["version"])))
    provenance = managed_runtime_verification(str(binary)) if exact_installed else {
        "verified": False, "state": "not-installed", "detail": "No exact installed copy was found.",
    }
    if target_exists and exact_installed:
        action = "verify"
    elif target_exists:
        action = "blocked"
    else:
        action = "install"

    python = runtime_update_python()
    curl = executable(["/usr/bin/curl", "curl"])
    git = executable(["/usr/bin/git", "git"])
    free_bytes = disk_free_for(root)
    required_bytes = 0 if action == "verify" else (
        RUNTIME_UPDATE_ESTIMATED_INSTALL_BYTES + RUNTIME_UPDATE_DISK_RESERVE_BYTES
    )
    selected = BINARIES.get("omlx")
    try:
        selected_resolved = str(Path(selected).expanduser().resolve(strict=True)) if selected else ""
        target_resolved = str(binary.resolve(strict=True)) if exact_installed else ""
    except OSError:
        selected_resolved = target_resolved = ""
    selected_now = bool(target_resolved and selected_resolved == target_resolved)

    host_ready = sys.platform == "darwin" and platform.machine().lower() in {"arm64", "aarch64"}
    checks = [
        {
            "label": "Audited official artifact", "state": "pass",
            "detail": f"{release['fileName']} · SHA-256 {str(release['sha256'])[:16]}… · tag {release['tag']} at {str(release['commit'])[:12]}",
        },
        {
            "label": "Supported host", "state": "pass" if host_ready else "blocked",
            "detail": "Apple Silicon macOS detected." if host_ready else "This audited wheel is only for Apple Silicon macOS.",
        },
        {
            "label": "Isolated destination", "state": "pass" if target_safe and action != "blocked" else "blocked",
            "detail": (
                f"Verify the existing versioned copy at {target}."
                if action == "verify" else
                f"Create {target}; no existing runtime will be replaced."
                if action == "install" else
                "The versioned destination already exists but is not the exact expected runtime; it will not be overwritten."
            ),
        },
        {
            "label": "Python 3.11", "state": "pass" if python.get("ready") else "blocked",
            "detail": f"{python.get('version')} at {python.get('path')}" if python.get("ready") else str(python.get("reason")),
        },
        {
            "label": "Download tool", "state": "pass" if action == "verify" or curl else "blocked",
            "detail": "No download is needed for local verification." if action == "verify" else (f"HTTPS download with {curl}." if curl else "curl is required for a resumable HTTPS download."),
        },
        {
            "label": "Pinned source dependencies", "state": "pass" if action == "verify" or git else "blocked",
            "detail": (
                "No dependency build is needed for local verification."
                if action == "verify" else
                f"{len(release.get('directSources') or [])} audited GitHub dependencies are fixed to full commits and staged with {git}."
                if git else
                "Git is required to stage the full-commit source dependencies declared by the official wheel."
            ),
        },
        {
            "label": "Disk reserve", "state": "pass" if action == "verify" or free_bytes >= required_bytes else "blocked",
            "detail": (
                "Verification creates only a small owner-only manifest."
                if action == "verify" else
                f"{free_bytes / 1024**3:.1f} GiB free; requires about {required_bytes / 1024**3:.1f} GiB including a 4 GiB reserve."
            ),
        },
    ]
    if action == "verify":
        checks.append({
            "label": "Installed provenance",
            "state": "pass" if provenance.get("verified") else "blocked",
            "detail": str(provenance.get("detail") or "Installed provenance is unavailable."),
        })
    can_start = action in {"install", "verify"} and all(item["state"] != "blocked" for item in checks)
    identity = {
        "schema": RUNTIME_UPDATE_SCHEMA_VERSION, "channel": release["channel"],
        "version": release["version"], "commit": release["commit"],
        "sha256": release["sha256"], "action": action, "target": str(target),
        "targetExists": target_exists, "installedVersion": installed_version,
        "provenance": provenance.get("state"), "python": python.get("path"),
        "git": git, "directSources": release.get("directSources"),
    }
    plan_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()
    confirmation = f"runtime:{action}:omlx:{release['channel']}:{release['version']}:{release['sha256']}"
    return {
        "schemaVersion": RUNTIME_UPDATE_SCHEMA_VERSION, "id": plan_id,
        "runtime": "omlx", "action": action, "canStart": can_start,
        "confirmation": confirmation,
        "release": release,
        "destination": {
            "path": str(target), "exists": target_exists,
            "installedVersion": installed_version or None,
            "selected": selected_now, "provenance": provenance,
        },
        "installer": {
            "python": python, "curl": curl, "git": git,
            "directSources": copy.deepcopy(release.get("directSources") or []),
            "dependencyPolicy": "The official oMLX wheel is checksum-pinned. Its four disclosed GitHub dependencies must match audited full commits; other dependencies must arrive as binary wheels. Everything is staged into a private wheelhouse, hashed, installed offline, and recorded in the manifest.",
        },
        "disk": {"freeBytes": free_bytes, "requiredBytes": required_bytes},
        "checks": checks,
        "steps": (
            ["Revalidate installed checksum provenance", "Run dependency and version smoke tests", "Write an owner-only verification manifest"]
            if action == "verify" else
            ["Resume the exact official wheel download", "Verify its published SHA-256 and dependency metadata", "Create a new isolated environment", "Stage binary wheels and four full-commit source builds", "Hash the complete private wheelhouse", "Install that wheelhouse offline", "Run preliminary dependency, version, and native-kernel smoke tests", "Rebase generated launchers and atomically promote the isolated copy", "Repeat every smoke test from the final path before recording trust"]
        ),
        "rollback": {
            "automaticSelection": False,
            "selectedPath": selected,
            "detail": "The currently selected executable remains untouched. Rollback is the existing ‘Use for new sessions’ choice on any verified installed copy.",
        },
        "review": {
            "networkOnStart": action == "install",
            "networkDetail": "Official GitHub wheel, four audited full-commit GitHub sources, and public dependency wheels." if action == "install" else "No network request.",
            "startsServer": False, "startsModel": False,
            "replacesExisting": False, "autoSelects": False,
            "catalogAuditedAt": RUNTIME_UPDATE_CATALOG_AUDITED_AT,
        },
    }

def runtime_update_overview() -> dict[str, Any]:
    releases = []
    for channel in ("stable", "preview"):
        plan = build_runtime_update_plan(channel)
        releases.append({
            "channel": channel, "label": plan["release"]["label"],
            "version": plan["release"]["version"],
            "preview": plan["release"]["preview"],
            "summary": plan["release"]["summary"],
            "releaseUrl": plan["release"]["releaseUrl"],
            "releasedAt": plan["release"]["releasedAt"],
            "action": plan["action"], "canPlan": plan["action"] != "blocked",
            "installed": plan["destination"]["exists"],
            "selected": plan["destination"]["selected"],
            "verified": bool(plan["destination"]["provenance"].get("verified")),
        })
    return {
        "schemaVersion": RUNTIME_UPDATE_SCHEMA_VERSION,
        "catalogAuditedAt": RUNTIME_UPDATE_CATALOG_AUDITED_AT, "networkChecked": False,
        "releases": releases,
        "ownership": {
            "omlx": "Launcher-managed side-by-side install",
            "lmstudio": "Vendor app and runtime-pack updater",
            "mtplx": "Vendor app-managed engine updater",
        },
    }

def _lmstudio_llamacpp_pack_contract(
    pack: Path, declared_version: str,
) -> dict[str, Any]:
    """Verify the installed files LM Studio declares for one llama.cpp pack."""
    blocked = {"manifestContractVerified": False, "contractFingerprint": None}
    try:
        pack_details = pack.lstat()
        resolved_pack = pack.resolve(strict=True)
        if pack.is_symlink() or not stat.S_ISDIR(pack_details.st_mode):
            return blocked
    except (OSError, RuntimeError):
        return blocked
    manifest, manifest_identity = _lmstudio_cache_document(
        resolved_pack / "backend-manifest.json",
    )
    inventory, inventory_identity = _lmstudio_cache_document(
        resolved_pack / "engine-protocol-server-artifacts.json",
    )
    protocol = manifest.get("engine_protocol_server") if isinstance(manifest, dict) else None
    files = inventory.get("files") if isinstance(inventory, dict) else None
    target_libraries = manifest.get("target_libraries") if isinstance(manifest, dict) else None
    engine_name = manifest.get("name") if isinstance(manifest, dict) else None
    executable_value = (
        protocol.get("executable_relative_path") if isinstance(protocol, dict) else None
    )
    if (
        not isinstance(manifest, dict)
        or manifest.get("engine") != "llama.cpp"
        or manifest.get("extension_type") != "engine"
        or manifest.get("version") != declared_version
        or not isinstance(manifest.get("supported_model_formats"), list)
        or not 1 <= len(manifest.get("supported_model_formats", [])) <= 32
        or not all(
            isinstance(value, str)
            for value in manifest.get("supported_model_formats", [])
        )
        or "gguf" not in manifest.get("supported_model_formats", [])
        or not isinstance(engine_name, str)
        or not 0 < len(engine_name) <= 180
        or pack.name != f"{engine_name}-{declared_version}"
        or not isinstance(protocol, dict)
        or protocol.get("runtime_kind") != "llama-server"
        or not isinstance(executable_value, str)
        or not isinstance(inventory, dict)
        or inventory.get("schema_version") != 1
        or inventory.get("runtime_kind") != "llama-server"
        or inventory.get("executable_relative_path") != executable_value
        or not isinstance(files, list) or not 1 <= len(files) <= 128
        or not isinstance(target_libraries, list) or not 1 <= len(target_libraries) <= 64
    ):
        return blocked

    identities: list[dict[str, Any]] = []
    seen: set[str] = set()

    def admit_file(relative_value: Any, executable: bool) -> bool:
        if (
            not isinstance(relative_value, str)
            or not 0 < len(relative_value) <= 320
            or "\\" in relative_value or "\0" in relative_value
        ):
            return False
        relative = PurePosixPath(relative_value)
        if (
            relative.is_absolute() or not relative.parts
            or any(part in {"", ".", ".."} for part in relative.parts)
            or relative_value in seen
        ):
            return False
        candidate = resolved_pack.joinpath(*relative.parts)
        try:
            details = candidate.lstat()
            if stat.S_ISLNK(details.st_mode):
                link_value = os.readlink(candidate)
                link = PurePosixPath(link_value)
                if link.is_absolute() or any(part in {"", ".", ".."} for part in link.parts):
                    return False
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(resolved_pack)
                target_details = resolved.stat()
                if not stat.S_ISREG(target_details.st_mode):
                    return False
            elif stat.S_ISREG(details.st_mode):
                resolved = candidate
                target_details = details
            else:
                return False
            if executable and not os.access(resolved, os.X_OK):
                return False
        except (OSError, RuntimeError, ValueError):
            return False
        seen.add(relative_value)
        identities.append({
            "path": relative_value,
            "device": int(details.st_dev), "inode": int(details.st_ino),
            "size": int(details.st_size), "modifiedNs": int(details.st_mtime_ns),
            "changedNs": int(details.st_ctime_ns),
            "resolvedDevice": int(target_details.st_dev),
            "resolvedInode": int(target_details.st_ino),
            "resolvedSize": int(target_details.st_size),
            "executable": executable,
        })
        return True

    for file_entry in files:
        if (
            not isinstance(file_entry, dict)
            or not isinstance(file_entry.get("executable"), bool)
            or not admit_file(
                file_entry.get("relative_path"), bool(file_entry.get("executable")),
            )
        ):
            return blocked
    if executable_value not in seen:
        return blocked
    for library in target_libraries:
        library_name = library.get("name") if isinstance(library, dict) else None
        if library_name in seen:
            continue
        if not admit_file(library_name, False):
            return blocked

    _manifest_after, manifest_after = _lmstudio_cache_document(
        resolved_pack / "backend-manifest.json",
    )
    _inventory_after, inventory_after = _lmstudio_cache_document(
        resolved_pack / "engine-protocol-server-artifacts.json",
    )
    if manifest_after != manifest_identity or inventory_after != inventory_identity:
        return blocked
    identity = {
        "schema": 1,
        "pack": str(resolved_pack),
        "name": engine_name,
        "version": declared_version,
        "manifestFingerprint": manifest_identity.get("sha256"),
        "inventoryFingerprint": inventory_identity.get("sha256"),
        "files": sorted(identities, key=lambda item: item["path"]),
    }
    return {
        "manifestContractVerified": True,
        "engineName": engine_name,
        "contractFingerprint": hashlib.sha256(json.dumps(
            identity, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest(),
    }

def lmstudio_runtime_packs(root: Path | None = None) -> list[dict[str, Any]]:
    root = root or (Path.home() / ".lmstudio" / "extensions" / "backends")
    result: list[dict[str, Any]] = []
    try:
        root_details = root.lstat()
        if root.is_symlink() or not stat.S_ISDIR(root_details.st_mode):
            return result
        entries = sorted(root.iterdir(), key=lambda item: item.name.lower())
    except OSError:
        return result
    for item in entries[:128]:
        try:
            details = item.lstat()
        except OSError:
            continue
        if item.is_symlink() or not stat.S_ISDIR(details.st_mode) or item.name == "vendor":
            continue
        kind = "MLX" if item.name.startswith("mlx-") else "llama.cpp" if item.name.startswith("llama.cpp-") else "Other"
        version = re.search(r"-(\d+\.\d+\.\d+)$", item.name)
        record: dict[str, Any] = {
            "name": item.name[:180],
            "kind": kind,
            "version": version.group(1) if version else "Unknown",
        }
        if kind == "llama.cpp" and version:
            record.update(_lmstudio_llamacpp_pack_contract(item, version.group(1)))
        result.append(record)
    return result[:32]

def runtime_candidate_details(runtime: str) -> list[dict[str, Any]]:
    selected_path = BINARIES.get(runtime)
    try:
        selected_resolved = str(Path(selected_path).resolve(strict=True)) if selected_path else ""
    except OSError:
        selected_resolved = ""
    result: list[dict[str, Any]] = []
    for candidate in runtime_candidates(runtime):
        llamacpp_contract = (
            llamacpp_runtime_contract(candidate["path"])
            if runtime == "llamacpp" else None
        )
        uzu_contract = (
            uzu_runtime_contract(candidate["path"])
            if runtime == "mirai" else None
        )
        version = (
            str(llamacpp_contract["version"])
            if isinstance(llamacpp_contract, dict) and llamacpp_contract.get("ready") is True else
            "Installed (unverified managed runtime)"
            if runtime == "llamacpp" else
            str(uzu_contract["version"])
            if (
                isinstance(uzu_contract, dict)
                and uzu_contract.get("binaryIdentityPinned") is True
            ) else
            "Installed (unverified managed runtime)"
            if runtime == "mirai" else
            command_version(candidate["path"])
        )
        detail: dict[str, Any] = {
            **candidate,
            "version": version,
            "selected": candidate["resolvedPath"] == selected_resolved,
        }
        if runtime == "omlx":
            kernel = omlx_qwen_kernel_status(candidate["path"])
            detail["kernel"] = kernel
            detail["managedVerification"] = managed_runtime_verification(candidate["path"])
            detail["dflashReady"] = omlx_supports_dflash2(version)
            detail["recommendedDflashBuild"] = omlx_has_recommended_dflash2_runtime(version)
            detail["aneReady"] = bool(
                omlx_version_at_least(version, ANE_TUNER_MINIMUM_RUNTIME)
                and kernel.get("ready")
            )
        elif runtime == "lms":
            detail["mtpLoadReady"] = lmstudio_mtp_load_supported(candidate["path"])
            detail["assistantDrafterCliReady"] = (
                lmstudio_assistant_drafter_load_supported(candidate["path"])
            )
        elif runtime == "llamacpp":
            detail["pleContract"] = llamacpp_contract
        elif runtime == "mirai":
            detail["uzuContract"] = uzu_contract
        result.append(detail)
    return result

def runtime_inventory() -> dict[str, Any]:
    """Describe selected runtimes and safe next actions without using the network."""
    omlx_candidates = runtime_candidate_details("omlx")
    omlx_selected = next((item for item in omlx_candidates if item["selected"]), None)
    omlx_best = max(
        omlx_candidates,
        key=lambda item: (
            bool(item.get("aneReady")), bool(item.get("recommendedDflashBuild")),
            semantic_version_key(str(item.get("version") or "")),
        ),
        default=None,
    )
    if omlx_best:
        omlx_best["recommended"] = True
    for item in omlx_candidates:
        item.setdefault("recommended", False)
    omlx_release = audited_runtime_release(
        "omlx", str((omlx_selected or {}).get("version") or ""),
    )
    metal = metal_toolchain_status()
    if not omlx_selected:
        omlx_level, omlx_headline = "blocked", "oMLX is not installed."
    elif omlx_selected.get("aneReady"):
        omlx_level, omlx_headline = "ready", "Selected oMLX can run DFlash 2 and the guarded ANE tuner."
    elif omlx_selected.get("dflashReady"):
        omlx_level = "advisory"
        omlx_headline = (
            f"Selected oMLX supports DFlash 2; audited {omlx_release['displayVersion']} is available."
            if omlx_release["updateAvailable"] else
            "DFlash 2 is available, but the native Qwen kernel is not verified for ANE."
        )
    else:
        omlx_level, omlx_headline = "advisory", "Core oMLX is runnable; DFlash 2 and ANE still need a newer verified installation."
    if omlx_selected and omlx_level == "ready" and omlx_release["needsReview"]:
        omlx_level = "advisory"
        omlx_headline = omlx_release["detail"]

    lms_candidates = runtime_candidate_details("lms")
    lms_selected = next((item for item in lms_candidates if item["selected"]), None)
    lms_app = runtime_app_status("lms")
    lms_app_version = plist_version(Path("/Applications/LM Studio.app/Contents/Info.plist"))
    packs = lmstudio_runtime_packs()
    lms_preference = lmstudio_backend_preference()
    lms_assistant_runtime = lmstudio_assistant_drafter_runtime_contract(
        BINARIES.get("lms"),
        str((lms_selected or {}).get("version") or "Not installed"),
        lms_app, packs, lms_preference,
    )
    mlx_packs = [item for item in packs if item["kind"] == "MLX"]
    lms_mtp_ready = bool(lms_selected and lms_selected.get("mtpLoadReady"))
    lms_level = (
        "ready" if lms_selected and mlx_packs and lms_mtp_ready else
        "advisory" if lms_selected else "blocked"
    )
    lms_identity = lmstudio_runtime_identity(
        str((lms_selected or {}).get("version") or "Not installed"),
        lms_app_version, packs,
    )
    lms_release = audited_runtime_release(
        "lms", lms_app_version or str((lms_selected or {}).get("version") or ""),
    )
    if lms_selected and lms_level == "ready" and lms_release["needsReview"]:
        lms_level = "advisory"

    mtplx_candidates = runtime_candidate_details("mtplx")
    mtplx_selected = next((item for item in mtplx_candidates if item["selected"]), None)
    mtplx_best = max(
        mtplx_candidates,
        key=lambda item: semantic_version_key(str(item.get("version") or "")),
        default=None,
    )
    if mtplx_best:
        mtplx_best["recommended"] = True
    for item in mtplx_candidates:
        item.setdefault("recommended", False)
    mtplx_app_version = plist_version(Path("/Applications/MTPLX.app/Contents/Info.plist"))
    mtplx_shadowed = [item for item in mtplx_candidates if not item["selected"]]
    mtplx_release = audited_runtime_release(
        "mtplx", str((mtplx_selected or {}).get("version") or ""),
    )
    mtplx_level = (
        "blocked" if not mtplx_selected else
        "advisory" if mtplx_selected is not mtplx_best or mtplx_release["needsReview"] else
        "ready"
    )
    mtplx_headline = (
        f"MTPLX {mtplx_release['displayVersion']} is available; the selected app engine is older."
        if mtplx_release["updateAvailable"] else
        "The selected MTPLX engine matches the audited upstream release."
        if mtplx_level == "ready" else
        "A newer installed MTPLX candidate is available; switching remains explicit."
        if mtplx_selected is not None and mtplx_selected is not mtplx_best else
        "The selected MTPLX engine is newer than or cannot be matched to the audited catalog."
        if mtplx_selected else
        "MTPLX is not installed."
    )

    agents = []
    for key, label in (("pi", "Pi"), ("opencode", "OpenCode"), ("codex", "Codex")):
        path = BINARIES.get(key)
        agents.append({
            "id": key, "label": label, "installed": bool(path),
            "path": path, "version": command_version(path),
        })

    runtimes = [
        {
            "id": "omlx", "label": "oMLX", "level": omlx_level,
            "headline": omlx_headline, "selected": omlx_selected,
            "candidates": omlx_candidates, "toolchain": metal,
            "release": omlx_release,
            "checks": [
                {"label": "Core server", "ready": bool(omlx_selected), "detail": str(omlx_selected.get("version") if omlx_selected else "Not installed")},
                {"label": "Audited upstream release", "ready": omlx_release["catalogCurrent"], "advisory": bool(omlx_selected), "detail": omlx_release["detail"]},
                {
                    "label": "DFlash 2 runtime",
                    "ready": bool(omlx_selected and omlx_selected.get("dflashReady")),
                    "advisory": bool(
                        omlx_selected and omlx_selected.get("dflashReady")
                        and not omlx_selected.get("recommendedDflashBuild")
                    ),
                    "detail": (
                        f"Supported by the selected build; audited {DFLASH2_RECOMMENDED_RUNTIME} is available."
                        if omlx_selected and omlx_selected.get("dflashReady")
                        and not omlx_selected.get("recommendedDflashBuild") else
                        "Selected build matches the current audited DFlash preview."
                        if omlx_selected and omlx_selected.get("recommendedDflashBuild") else
                        f"Requires {DFLASH2_MINIMUM_RUNTIME} or newer."
                    ),
                },
                {"label": "Native Qwen kernel", "ready": bool(omlx_selected and omlx_selected.get("kernel", {}).get("ready")), "detail": str((omlx_selected or {}).get("kernel", {}).get("reason") or "No selected runtime.")},
            ],
            "update": {
                "mode": "manual-review", "automatic": False,
                "headline": "Prefer the signed app for precompiled kernels; keep the current CLI until its replacement verifies.",
                "detail": (
                    "The official macOS app ships precompiled native kernels. "
                    "The documented Homebrew custom-kernel path tracks HEAD and needs full Xcode."
                ),
                "primaryUrl": OMLX_INSTALL_URL,
                "primaryLabel": f"Open official oMLX {omlx_release['displayVersion']} release",
                "docsUrl": OMLX_INSTALL_DOCS_URL,
                "developerCommand": "brew install omlx --HEAD --with-custom-kernel",
                "developerCommandReady": bool(metal.get("ready")),
                "release": omlx_release,
                "rollback": "Nothing switches automatically. The current executable remains selected until you choose another verified installed candidate.",
            },
        },
        {
            "id": "lms", "label": "LM Studio", "level": lms_level,
            "headline": (
                f"LM Studio {lms_app_version or 'app'}, load-time MTP, and {len(mlx_packs)} local MLX runtime variant{'s' if len(mlx_packs) != 1 else ''} are ready."
                if lms_selected and mlx_packs and lms_mtp_ready else
                "LM Studio is installed, but the selected CLI does not expose the complete load-time MTP contract."
                if lms_selected else "LM Studio CLI is not installed."
            ),
            "selected": lms_selected, "candidates": lms_candidates,
            "appVersion": lms_app_version, "runtimePacks": packs,
            "benchmarkIdentity": lms_identity, "release": lms_release,
            "app": lms_app,
            "assistantDrafterRuntime": lms_assistant_runtime,
            "checks": [
                {"label": "Desktop app", "ready": bool(lms_app_version), "detail": lms_app_version or "Not detected"},
                {"label": "Audited upstream release", "ready": lms_release["catalogCurrent"], "advisory": bool(lms_selected), "detail": lms_release["detail"]},
                {"label": "Launcher CLI", "ready": bool(lms_selected), "detail": str(lms_selected.get("version") if lms_selected else "Not installed")},
                {"label": "MLX engine packs", "ready": bool(mlx_packs), "detail": ", ".join(item["version"] for item in mlx_packs) or "No local MLX pack detected"},
                {"label": "Load-time MTP", "ready": lms_mtp_ready, "detail": "Selected CLI advertises MTP enable, disable, and draft-depth flags." if lms_mtp_ready else "Selected CLI is missing one or more required Draft MTP load flags."},
                {
                    "label": "Assistant drafter discovery",
                    "ready": lms_assistant_runtime["ready"],
                    "detail": lms_assistant_runtime["reason"],
                },
                {"label": "Benchmark identity", "ready": bool(lms_selected and mlx_packs), "detail": lms_identity},
            ],
            "update": {
                "mode": "in-app", "automatic": False,
                "headline": "Use LM Studio's built-in app and runtime updaters.",
                "detail": "App releases and inference runtime packs update independently; the launcher does not wake LM Studio or download a pack while inspecting them.",
                "primaryUrl": LMSTUDIO_UPDATE_DOCS_URL,
                "primaryLabel": "Open official update guidance",
                "docsUrl": LMSTUDIO_RUNTIME_DOCS_URL,
                "release": lms_release,
                "rollback": "LM Studio keeps runtime packs separate, so selecting or updating a pack does not rewrite this launcher's settings.",
            },
        },
        {
            "id": "mtplx", "label": "MTPLX", "level": mtplx_level,
            "headline": mtplx_headline, "selected": mtplx_selected,
            "candidates": mtplx_candidates, "appVersion": mtplx_app_version,
            "shadowedCount": len(mtplx_shadowed), "release": mtplx_release,
            "app": runtime_app_status("mtplx"),
            "checks": [
                {"label": "Selected engine", "ready": bool(mtplx_selected), "detail": str(mtplx_selected.get("version") if mtplx_selected else "Not installed")},
                {"label": "Desktop app", "ready": bool(mtplx_app_version), "detail": mtplx_app_version or "Not detected"},
                {"label": "Audited upstream release", "ready": mtplx_release["catalogCurrent"], "advisory": bool(mtplx_selected), "detail": mtplx_release["detail"]},
                {"label": "Duplicate paths", "ready": len(mtplx_shadowed) == 0, "advisory": len(mtplx_shadowed) > 0, "detail": f"{len(mtplx_shadowed)} other installed candidate{'s' if len(mtplx_shadowed) != 1 else ''}; only the selected path launches."},
            ],
            "update": {
                "mode": "in-app", "automatic": False,
                "headline": (
                    f"MTPLX {mtplx_release['displayVersion']} is the audited agent and decode update."
                    if mtplx_release["updateAvailable"] else
                    "Prefer the app-managed engine and inspect duplicate CLI installs separately."
                ),
                "detail": (
                    "Upstream 2.11.2 gates the 27B flash verifier to supported M5 hardware "
                    "and fixes deep-session and later-conversation cache reuse. "
                    "Preserve valid older evidence as history, keep "
                    "swap overcommit and context-specific operator tuning disabled, then measure "
                    "2.11.2 locally before calling it faster on this Mac."
                    if mtplx_release["updateAvailable"] else
                    "The MTPLX app refreshes its managed engine; a Homebrew or user CLI can remain at a different version without affecting the selected path."
                ),
                "primaryUrl": mtplx_release["releaseUrl"],
                "primaryLabel": f"Open MTPLX {mtplx_release['displayVersion']} release",
                "docsUrl": MTPLX_INSTALL_DOCS_URL,
                "release": mtplx_release,
                "rollback": (
                    "The vendor app updater replaces its app-managed engine. Existing results stay version-bound; measurements from an older runtime cannot drive fastest-route choices."
                    if mtplx_release["updateAvailable"] else
                    "Switching candidates changes only which installed executable new launcher sessions use. It never uninstalls the other copy."
                ),
            },
        },
    ]
    uzu_candidates = runtime_candidate_details("mirai")
    uzu_selected = next((item for item in uzu_candidates if item["selected"]), None)
    uzu_contract = (
        copy.deepcopy(uzu_selected.get("uzuContract"))
        if isinstance(uzu_selected, dict) and isinstance(uzu_selected.get("uzuContract"), dict)
        else uzu_runtime_contract(BINARIES.get("mirai"))
    )
    uzu_ready = uzu_contract.get("ready") is True
    runtimes.append({
        "id": "mirai",
        "label": "Uzu · Mirai",
        "level": "ready" if uzu_ready else "blocked",
        "headline": (
            "The pinned Uzu runtime is ready for local-only DFlash + Weaver inference."
            if uzu_ready else
            str(uzu_contract.get("reason") or "A verified memory-safe Uzu runtime is required.")
        ),
        "selected": uzu_selected,
        "candidates": uzu_candidates,
        "release": None,
        "checks": [
            {
                "label": "Exact hardened bytes",
                "ready": uzu_contract.get("binaryIdentityPinned") is True,
                "detail": (
                    f"{command_version(BINARIES.get('mirai'))} · SHA-256 "
                    f"{str(uzu_contract.get('expectedBinarySha256') or '')[:12]}… · "
                    "signing status is not used as launch authority"
                ),
            },
            {
                "label": "Pinned source hardening",
                "ready": bool(
                    uzu_contract.get("memorySafetyBlocked") is False
                    and uzu_contract.get("upstreamCommit") == UZU_RUNTIME_UPSTREAM_COMMIT
                    and uzu_contract.get("sourcePatchSha256") == UZU_RUNTIME_SOURCE_PATCH_SHA256
                ),
                "detail": (
                    f"Uzu {UZU_RUNTIME_UPSTREAM_TAG} commit {UZU_RUNTIME_UPSTREAM_COMMIT[:12]}… "
                    "plus the reviewed launcher patch."
                ),
            },
            {
                "label": "Native private boundary",
                "ready": bool(
                    uzu_contract.get("boundedContextReady") is True
                    and uzu_contract.get("nativeBearerAuthentication") is True
                    and uzu_contract.get("oneUseApiKeyFile") is True
                    and uzu_contract.get("nativeContextLimit") is True
                    and uzu_contract.get("nativeOutputLimit") is True
                    and uzu_listener_protection_ready(uzu_contract)
                ),
                "detail": (
                    "The raw listener requires a one-use bearer key and enforces each "
                    "run's context and output ceilings itself."
                    if uzu_listener_protection_ready(uzu_contract) else
                    "The hardened raw-listener boundary is not available."
                ),
            },
            {
                "label": "Outbound isolation",
                "ready": uzu_contract.get("networkSandbox") is True,
                "detail": "The launcher still denies outbound network access around inference.",
            },
        ],
        "update": {
            "mode": "manual-review", "automatic": False,
            "headline": f"Hardened Uzu {UZU_RUNTIME_TAG} is an exact local build.",
            "detail": (
                "Only the fixed launcher-managed path and SHA-256 are accepted. The launcher "
                "does not infer trust from a version string or make a Developer ID/notarization claim."
            ),
            "primaryUrl": UZU_RUNTIME_RELEASE_URL,
            "primaryLabel": f"Open upstream Uzu {UZU_RUNTIME_UPSTREAM_TAG}",
            "docsUrl": UZU_MODEL_PAGE_URL,
            "release": None,
            "rollback": "The hardened binary stays isolated in its versioned launcher directory and is never placed on PATH.",
        },
    })
    for runtime_id, label, minimum, detail in (
        (
            "slotstream", "Slotstream", "Audited 0.2.17 · macOS 26 · Apple Silicon",
            "Full Qwen experts and n-grams streamed from SSD, explicit MTP, and context memory planning.",
        ),
        (
            "splash", "Splash", "Splash 1.2.1 · GGUF / MLX Q4 · macOS 26.4 · Apple silicon M3+ · 36 GB+",
            "Qwen 27B and 35B-A3B execution with local GGUF / MLX Q4 weights and a matching DFlash2 draft.",
        ),
        (
            "swiftlm", "SwiftLM", "macOS 14 · Apple Silicon",
            "Streams routed experts from ordinary MLX MoE checkpoints with native expert routing preserved.",
        ),
        (
            "mference", "Mference", "macOS 15 · Apple Silicon",
            "Runs only pinned, verified .gturbo bundles with model-specific Metal kernels.",
        ),
        (
            "whallm", "Whallm", "macOS 15 · Apple Silicon · 64 GiB published floor",
            "Owns one pinned Qwen3.8 Flash-Next install and streams all 512 routed experts from SSD; 48 GiB is experimental.",
        ),
    ):
        candidates = runtime_candidate_details(runtime_id)
        selected = next((item for item in candidates if item["selected"]), None)
        installed_runtime = selected is not None
        release = (
            audited_runtime_release(
                runtime_id, str((selected or {}).get("version") or ""),
            )
            if runtime_id in RUNTIME_RELEASE_CATALOG else None
        )
        runtime_level = (
            "blocked" if not installed_runtime else
            "advisory" if release and release.get("needsReview") else
            "ready"
        )
        checks = [
            {
                "label": "SSD-streaming server",
                "ready": installed_runtime,
                "detail": str(selected.get("version") if selected else "Not installed"),
            },
            {
                "label": "Exact model contract",
                "ready": installed_runtime,
                "detail": detail,
            },
            {"label": "Platform", "ready": True, "detail": minimum},
        ]
        if release:
            checks.insert(1, {
                "label": "Audited upstream release",
                "ready": bool(release.get("catalogCurrent")),
                "advisory": installed_runtime,
                "detail": str(release.get("detail") or ""),
            })
        runtimes.append({
            "id": runtime_id,
            "label": label,
            "level": runtime_level,
            "headline": (
                f"{label} {release['displayVersion']} is available; the selected copy needs review."
                if installed_runtime and release and release.get("updateAvailable") else
                f"{label} is ready for accepted SSD-streamed models."
                if installed_runtime else
                f"{label} is optional and not installed."
            ),
            "selected": selected,
            "candidates": candidates,
            "release": release,
            "checks": checks,
            "app": runtime_app_status(runtime_id),
            "update": {
                "mode": "manual-review", "automatic": False,
                "headline": (
                    f"Install or update to audited {label} {release['displayVersion']}."
                    if release else f"Install and update {label} from its upstream source."
                ),
                "detail": "The launcher never downloads runtimes or very large model weights while inspecting this optional lane.",
                "primaryUrl": str((release or {}).get("releaseUrl") or SSD_STREAMING_RUNTIME_URLS[runtime_id]),
                "primaryLabel": (
                    f"Open {label} {release['displayVersion']} release"
                    if release else f"Open {label} source"
                ),
                "docsUrl": SSD_STREAMING_RUNTIME_URLS[runtime_id],
                "release": release,
                "rollback": "Runtime selection changes only the executable used for new sessions; model files are not rewritten.",
            },
        })
    installed = sum(bool(runtime.get("selected")) for runtime in runtimes)
    advisories = sum(runtime["level"] != "ready" for runtime in runtimes)
    if installed == len(runtimes) and advisories:
        summary_message = "All runtimes are installed; one or more advanced checks still need review."
    elif installed == len(runtimes):
        summary_message = "All selected runtimes passed their local checks."
    else:
        summary_message = f"{installed} of {len(runtimes)} runtimes are installed; missing engines remain optional."
    return {
        "version": RUNTIME_PREFERENCES_VERSION,
        "checkedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "networkChecked": False,
        "releaseCatalog": {
            "schemaVersion": RUNTIME_RELEASE_CATALOG_VERSION,
            "auditedAt": RUNTIME_RELEASE_CATALOG_AUDITED_AT,
            "networkChecked": False,
        },
        "summary": {
            "installed": installed,
            "total": len(runtimes), "advisories": advisories,
            "message": summary_message,
        },
        "runtimes": runtimes,
        "agents": agents,
        "safety": {
            "changesNothingOnOpen": True,
            "usesNetwork": False,
            "startsApplications": False,
            "startsApplicationsOnExplicitRequest": True,
            "selectionOnly": True,
        },
    }

def runtime_promotion_public_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in plan.items() if not key.startswith("_")
    }

def _runtime_promotion_candidate(
    candidate: dict[str, Any], revision: dict[str, Any], role: str,
) -> dict[str, Any]:
    provenance = candidate.get("managedVerification")
    return {
        "role": role,
        "id": str(candidate["id"]),
        "label": str(candidate.get("channelLabel") or "Installed oMLX"),
        "version": str(candidate.get("version") or "Unreported"),
        "path": str(candidate["path"]),
        "resolvedPath": str(candidate["resolvedPath"]),
        "revision": copy.deepcopy(revision),
        "officialVerified": bool(isinstance(provenance, dict) and provenance.get("verified")),
        "artifactSha256": (
            str(provenance.get("artifactSha256") or "")
            if isinstance(provenance, dict) else ""
        ),
    }

def build_runtime_promotion_plan(
    payload: dict[str, Any], models: list[dict[str, Any]], *,
    resource_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an exact, read-only A/B contract for two installed oMLX copies."""
    candidate_id = str(payload.get("candidateId") or "")
    details = runtime_candidate_details("omlx")
    selected = next((item for item in details if item.get("selected") is True), None)
    candidate = next((item for item in details if item.get("id") == candidate_id), None)
    if not selected:
        raise ValueError("Select an installed oMLX copy before planning a runtime comparison.")
    if not candidate:
        raise ValueError("That oMLX comparison candidate changed. Refresh Runtime Manager.")
    if candidate.get("id") == selected.get("id"):
        raise ValueError("Choose a different installed oMLX copy to compare with the selected runtime.")
    provenance = candidate.get("managedVerification")
    if not isinstance(provenance, dict) or provenance.get("verified") is not True:
        raise ValueError(
            "Runtime Promotion measures only a launcher-managed candidate whose official wheel checksum is verified."
        )

    selected_revision = runtime_executable_revision(selected["path"])
    candidate_revision = runtime_executable_revision(candidate["path"])
    request = copy.deepcopy(payload)
    request["backend"] = "omlx"
    request.pop("scope", None)
    options = copy.deepcopy(request.get("options") if isinstance(request.get("options"), dict) else {})
    options.update({
        "acceleration": "off", "kv": "off", "anePrefill": "off",
        "burst": "balanced",
    })
    request["options"] = options
    job = validated_benchmark_request(request, models, allow_baseline_only=True)
    job["modes"] = ["ar"]
    job["options"] = options
    job["pairFingerprint"] = None
    admission_request = {
        "backend": "omlx", "client": "chat", "modelId": job["modelId"],
        "project": job["project"], "context": job["context"],
        "output": job["output"], "reasoning": job["reasoning"],
        "mode": "custom", "options": copy.deepcopy(job["options"]),
        "chat": copy.deepcopy(job["chat"]),
    }
    memory_admission = route_qualification_memory_admission(
        admission_request, models, resource_snapshot=resource_snapshot,
    )
    capacity_ready = strict_model_load_admission_ready(memory_admission)
    model_fingerprint = str(job.get("modelFingerprint") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", model_fingerprint):
        raise ValueError("The selected model has no stable benchmark fingerprint for runtime promotion.")

    selected_public = _runtime_promotion_candidate(selected, selected_revision, "selected")
    candidate_public = _runtime_promotion_candidate(candidate, candidate_revision, "candidate")
    contract_value = {
        "schema": RUNTIME_PROMOTION_SCHEMA_VERSION,
        "selected": {"id": selected_public["id"], "revision": selected_revision["id"], "version": selected_public["version"]},
        "candidate": {"id": candidate_public["id"], "revision": candidate_revision["id"], "version": candidate_public["version"], "artifact": candidate_public["artifactSha256"]},
        "modelId": job["modelId"], "modelFingerprint": model_fingerprint,
        "hardwareFingerprint": hardware_fingerprint(),
        "suite": job["suiteName"], "workloadKind": job["workloadKind"],
        "context": job["context"], "output": job["output"],
        "client": job["client"], "reasoning": job["reasoning"],
        "samplingFingerprint": job["evidence"]["samplingFingerprint"],
        "targetKV": "off", "acceleration": "ar", "anePrefill": "off",
    }
    contract_id = hashlib.sha256(json.dumps(
        contract_value, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    prior = [
        item for item in load_runtime_promotion_records()
        if item.get("contractId") == contract_id
        and isinstance(item.get("executionOrder"), list)
    ]
    if prior:
        previous_order = list(max(
            prior, key=lambda item: str(item.get("createdAt") or ""),
        )["executionOrder"])
        execution_roles = ["candidate", "selected"] if previous_order[:1] == ["selected"] else ["selected", "candidate"]
        order_strategy = "alternate-after-matching-run"
    else:
        execution_roles = ["selected", "candidate"]
        order_strategy = "selected-reference-first"
    plan_identity = {**contract_value, "contractId": contract_id, "executionOrder": execution_roles}
    plan_id = hashlib.sha256(json.dumps(
        plan_identity, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    steps_per_runtime = 2 + benchmark_measurement_count(job["suite"])
    checks = [
        {
            "label": "Different installed copies", "state": "pass",
            "detail": f"{selected_public['version']} remains selected while {candidate_public['version']} is measured separately.",
        },
        {
            "label": "Official candidate provenance", "state": "pass",
            "detail": f"Candidate wheel SHA-256 {candidate_public['artifactSha256'][:16]}… matched the audited catalog.",
        },
        {
            "label": "Exact executable revisions", "state": "pass",
            "detail": f"Selected {selected_revision['id']} · candidate {candidate_revision['id']}.",
        },
        {
            "label": "Same model artifact", "state": "pass",
            "detail": f"{job['model']['name']} · fingerprint {model_fingerprint[:16]}…",
        },
        {
            "label": "Controlled route", "state": "pass",
            "detail": "Both copies use AR, full-precision KV, no ANE tuning, the same reasoning and sampling contract, and fresh cache-isolated loads.",
        },
        {
            "label": "Live Mac capacity",
            "state": "pass" if capacity_ready else "block",
            "detail": (
                "Current unified-memory headroom passed the strict automated-load gate."
                if capacity_ready else
                f"{memory_admission.get('label') or 'Capacity is not ready'}: "
                f"{memory_admission.get('detail') or 'refresh capacity before comparing runtimes.'}"
            ),
        },
    ]
    return {
        "schemaVersion": RUNTIME_PROMOTION_SCHEMA_VERSION,
        "id": plan_id, "contractId": contract_id,
        "canStart": capacity_ready,
        "confirmation": f"runtime-promotion:{plan_id}",
        "memoryAdmission": copy.deepcopy(memory_admission),
        "selected": selected_public, "candidate": candidate_public,
        "model": {
            "id": job["modelId"], "name": job["model"]["name"],
            "fingerprint": model_fingerprint,
        },
        "workload": {
            "suite": job["suiteName"], "label": job["suite"]["label"],
            "kind": job["workloadKind"], "context": job["context"],
            "output": job["output"], "client": job["client"],
            "reasoning": job["reasoning"], "modelLoads": 2,
            "requestsPerRuntime": steps_per_runtime,
            "generatedRequests": steps_per_runtime * 2,
        },
        "executionOrder": execution_roles,
        "orderStrategy": order_strategy,
        "checks": checks,
        "thresholds": {
            "minimumMedianSpeedup": BENCHMARK_MINIMUM_SPEEDUP,
            "minimumWorstCaseSpeedup": BENCHMARK_MINIMUM_SPEEDUP,
            "maximumMemoryRegressionBytes": BENCHMARK_MEMORY_MEANINGFUL_BYTES,
            "allowsThermalRegression": False,
            "maximumEvidenceAgeDays": RUNTIME_PROMOTION_MAX_AGE_DAYS,
        },
        "steps": [
            "Revalidate both executable revisions and the candidate's official provenance",
            "Wait for a stable public memory and thermal baseline",
            f"Load {execution_roles[0]} runtime in cache-isolated AR mode",
            "Run warm-up, greedy correctness, and generated workload requests",
            "Stop it completely and restore comparable Mac conditions",
            f"Load {execution_roles[1]} runtime with the identical contract",
            "Require matching output, token counts, resource starts, and no material regression",
            "Save complete evidence without changing the selected runtime",
        ],
        "rollback": {
            "selectedCandidateId": selected_public["id"],
            "detail": "Measurement never edits runtime preferences. A trusted result still needs a separate Promote click; the current copy remains an installed one-click rollback.",
        },
        "privacy": {
            "usesNetwork": False, "usesProjectData": False,
            "usesGeneratedPromptsOnly": True, "storesGeneratedText": False,
            "autoPromotes": False, "selectionChangesDuringMeasurement": False,
        },
        "_job": job,
        "_contract": contract_value,
        "_request": copy.deepcopy(payload),
    }

def _runtime_promotion_measurement(
    job: dict[str, Any], result: dict[str, Any],
) -> dict[str, Any]:
    record = {
        "comparisonContractVersion": BENCHMARK_COMPARISON_CONTRACT_VERSION,
        "modelFingerprint": job["modelFingerprint"],
        "hardwareFingerprint": hardware_fingerprint(),
        "suite": job["suiteName"], "workloadKind": job["workloadKind"],
        "scenarioContract": list(job["suite"].get("scenarios") or []),
        "client": job["client"], "reasoning": job["reasoning"],
        "targetKV": "off", "samplingFingerprint": job["evidence"]["samplingFingerprint"],
        **sampling_record_evidence(job["evidence"]),
        "contextMin": job["context"], "contextMax": job["context"],
        "outputMin": job["output"], "outputMax": job["output"],
        "qualityFingerprint": result.get("qualityHash"),
        "qualityCompletionTokens": result.get("qualityCompletionTokens"),
        "winner": "ar", "modes": {"ar": result},
    }
    measured = cross_engine_benchmark_measurement(record)
    if measured is None:
        raise RuntimeError("A runtime returned incomplete benchmark evidence.")
    return measured

def build_runtime_promotion_result(
    plan: dict[str, Any], results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if set(results) != {"selected", "candidate"}:
        raise RuntimeError("Runtime promotion did not complete both exact routes.")
    job = plan["_job"]
    selected_result = results["selected"]
    candidate_result = results["candidate"]
    selected_measurement = _runtime_promotion_measurement(job, selected_result)
    candidate_measurement = _runtime_promotion_measurement(job, candidate_result)
    quality_matched = bool(
        selected_result.get("qualityHash") == candidate_result.get("qualityHash")
        and selected_result.get("qualityCompletionTokens")
        == candidate_result.get("qualityCompletionTokens")
        and selected_measurement["signature"] == candidate_measurement["signature"]
        and selected_measurement["observedSampleTokens"]
        == candidate_measurement["observedSampleTokens"]
    )

    selected_samples = selected_result.get("samples")
    candidate_samples = candidate_result.get("samples")
    if (
        not isinstance(selected_samples, list) or not selected_samples
        or not isinstance(candidate_samples, list)
        or len(selected_samples) != len(candidate_samples)
    ):
        raise RuntimeError("Runtime promotion returned a mismatched sample set.")
    ratios: list[float] = []
    for baseline, target in zip(selected_samples, candidate_samples):
        if job["workloadKind"] == "agentic":
            baseline_value = float(baseline.get("totalSeconds") or 0)
            target_value = float(target.get("totalSeconds") or 0)
            ratio = baseline_value / max(target_value, 0.000_001)
        else:
            baseline_value = float(baseline.get("endToEndTokensPerSecond") or 0)
            target_value = float(target.get("endToEndTokensPerSecond") or 0)
            ratio = target_value / max(baseline_value, 0.000_001)
        if not math.isfinite(ratio) or ratio <= 0 or baseline_value <= 0 or target_value <= 0:
            raise RuntimeError("Runtime promotion returned non-positive speed telemetry.")
        ratios.append(ratio)
    median_speedup = statistics.median(ratios)
    worst_speedup = min(ratios)

    cooldown_statuses = {
        role: str(result.get("resourceCooldown", {}).get("status") or "")
        for role, result in results.items()
    }
    resource_complete = all(
        isinstance(measurement.get("baselineHeadroomBytes"), int)
        and isinstance(measurement.get("peakPressureDeltaBytes"), int)
        and isinstance(measurement.get("thermalStartValue"), int)
        and isinstance(measurement.get("thermalWorstValue"), int)
        and isinstance(measurement.get("lowPowerMode"), bool)
        for measurement in (selected_measurement, candidate_measurement)
    )
    starts_comparable = bool(
        resource_complete
        and selected_measurement["thermalStartValue"] == candidate_measurement["thermalStartValue"]
        and selected_measurement["lowPowerMode"] == candidate_measurement["lowPowerMode"]
        and abs(
            int(selected_measurement["baselineHeadroomBytes"])
            - int(candidate_measurement["baselineHeadroomBytes"])
        ) <= BENCHMARK_MEMORY_MEANINGFUL_BYTES
        and sorted(cooldown_statuses.values()) == ["ready", "reference-ready"]
    )
    memory_regression = (
        int(candidate_measurement["peakPressureDeltaBytes"])
        - int(selected_measurement["peakPressureDeltaBytes"])
        if resource_complete else None
    )
    thermal_regression = bool(
        resource_complete
        and int(candidate_measurement["thermalWorstValue"])
        > int(selected_measurement["thermalWorstValue"])
    )
    resource_guard_passed = bool(
        starts_comparable
        and memory_regression is not None
        and memory_regression <= BENCHMARK_MEMORY_MEANINGFUL_BYTES
        and not thermal_regression
    )
    speed_passed = bool(
        median_speedup >= BENCHMARK_MINIMUM_SPEEDUP
        and worst_speedup >= BENCHMARK_MINIMUM_SPEEDUP
    )
    can_promote = quality_matched and resource_guard_passed and speed_passed
    checks = [
        {
            "label": "Greedy output parity", "state": "pass" if quality_matched else "blocked",
            "detail": "Output fingerprint and authoritative token count matched." if quality_matched else "The runtimes produced different deterministic output or token counts.",
        },
        {
            "label": "Comparable Mac conditions", "state": "pass" if starts_comparable else "blocked",
            "detail": "Both routes began from matching public memory, thermal, and power-mode conditions." if starts_comparable else "Public memory, thermal, power-mode, or cooldown evidence was missing or mismatched.",
        },
        {
            "label": "Median and worst-case speed", "state": "pass" if speed_passed else "advisory",
            "detail": f"Candidate median {(median_speedup - 1) * 100:+.1f}% · worst case {(worst_speedup - 1) * 100:+.1f}% · requires +{(BENCHMARK_MINIMUM_SPEEDUP - 1) * 100:.0f}% in both.",
        },
        {
            "label": "Memory regression guard",
            "state": "pass" if resource_complete and memory_regression is not None and memory_regression <= BENCHMARK_MEMORY_MEANINGFUL_BYTES else "blocked",
            "detail": (
                "Candidate peak pressure matched the selected runtime."
                if memory_regression == 0 else
                f"Candidate peak pressure changed by {display_size(abs(memory_regression))} "
                f"{'more' if memory_regression > 0 else 'less'} than selected."
                if memory_regression is not None else "Comparable memory telemetry was unavailable."
            ),
        },
        {
            "label": "Thermal regression guard", "state": "blocked" if thermal_regression else "pass" if resource_complete else "blocked",
            "detail": (
                f"Selected {selected_measurement['thermalWorst']} · candidate {candidate_measurement['thermalWorst']}."
                if resource_complete else "Comparable public thermal telemetry was unavailable."
            ),
        },
    ]
    if can_promote:
        recommendation = (
            f"Promote oMLX {plan['candidate']['version']}: it matched deterministic output, "
            f"was {(median_speedup - 1) * 100:.1f}% faster at the median and cleared every resource guard."
        )
    elif not quality_matched:
        recommendation = "Keep the selected runtime: deterministic output changed, so speed cannot justify promotion."
    elif not resource_guard_passed:
        recommendation = "Keep the selected runtime: resource evidence was incomplete, mismatched, or regressed."
    else:
        recommendation = (
            f"Keep the selected runtime: the candidate's median {(median_speedup - 1) * 100:+.1f}% and "
            f"worst-case {(worst_speedup - 1) * 100:+.1f}% results did not both clear the 3% switch threshold."
        )
    record_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    public_measurements = {
        "selected": {
            key: copy.deepcopy(value) for key, value in selected_measurement.items()
            if key != "signature"
        },
        "candidate": {
            key: copy.deepcopy(value) for key, value in candidate_measurement.items()
            if key != "signature"
        },
    }
    return {
        "schemaVersion": RUNTIME_PROMOTION_SCHEMA_VERSION,
        "id": record_id, "planId": plan["id"], "contractId": plan["contractId"],
        "createdAt": created_at.isoformat(),
        "validUntil": (created_at + timedelta(days=RUNTIME_PROMOTION_MAX_AGE_DAYS)).isoformat(),
        "hardwareFingerprint": hardware_fingerprint(),
        "model": copy.deepcopy(plan["model"]), "modelFingerprint": plan["model"]["fingerprint"],
        "workload": copy.deepcopy(plan["workload"]),
        "selected": copy.deepcopy(plan["selected"]),
        "candidate": copy.deepcopy(plan["candidate"]),
        "executionOrder": list(plan["executionOrder"]),
        "qualityMatched": quality_matched,
        "resourceComparable": starts_comparable,
        "resourceGuardPassed": resource_guard_passed,
        "speedPassed": speed_passed,
        "medianSpeedup": round(median_speedup, 4),
        "worstCaseSpeedup": round(worst_speedup, 4),
        "memoryRegressionBytes": memory_regression,
        "thermalRegression": thermal_regression,
        "cooldownStatuses": cooldown_statuses,
        "measurements": public_measurements,
        "checks": checks, "canPromote": can_promote,
        "confirmation": f"promote-runtime:{record_id}:{plan['candidate']['id']}",
        "recommendation": recommendation,
        "selectionChanged": False, "promotedAt": None,
        "privacy": {"storedGeneratedText": False, "storedPrompts": False},
    }
