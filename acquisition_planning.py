"""Complete public model acquisition and setup previews with explicit live ports.

Queries remain anonymous, plans bind exact revisions/files/licenses/destinations,
and verification retains current regular-file and checksum authority. Importing
this module starts no operation and performs no filesystem or network work.
"""
from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable
import copy
import hashlib
import json
import locale
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import owned_cli_capture

@dataclass(frozen=True)
class AcquisitionDescriptor:
    id: str
    label: str
    kind: str
    binary_key: str | None
    protocol: str
    built_in: bool

@dataclass(frozen=True)
class _FrozenMapping(Mapping[Any, Any]):
    _values: Mapping[Any, Any]
    def __getitem__(self, key): return self._values[key]
    def __iter__(self): return iter(self._values)
    def __len__(self): return len(self._values)
    def __deepcopy__(self,memo): return {k:copy.deepcopy(v,memo) for k,v in self._values.items()}

def _freeze(value):
    if isinstance(value, Mapping):return _FrozenMapping(MappingProxyType({k:_freeze(v) for k,v in value.items()}))
    if isinstance(value,(tuple,list)):return tuple(_freeze(v) for v in value)
    if isinstance(value,(set,frozenset)):return frozenset(value)
    return value

@dataclass(frozen=True)
class AcquisitionPolicy:
    dflash2_draft_bytes: int
    dflash2_draft_repo: str
    dflash2_draft_revision: str
    dflash2_draft_size_label: str
    dflash2_draft_url: str
    dflash2_minimum_runtime: str
    dflash2_recommended_runtime: str
    dflash2_release_url: str
    engine_adapters: Mapping[str, AcquisitionDescriptor]
    llamacpp_atomic_file_manifest: tuple[Any, ...]
    llamacpp_atomic_repo: str
    llamacpp_atomic_revision: str
    llamacpp_atomic_total_bytes: int
    llamacpp_atomic_variant: str
    llamacpp_atomic_variant_id: str
    model_acquisition_download_reserve_bytes: int
    model_acquisition_marker: str
    model_acquisition_max_files: int
    model_acquisition_max_remote_bytes: int
    model_acquisition_memory_reserve_bytes: int
    model_acquisition_plan_ttl_seconds: int
    model_acquisition_schema_version: int
    model_acquisition_search_limit: int
    setup_download_reserve_bytes: int
    _acquisition_metadata_names: frozenset[str]

    def __post_init__(self):
        for field in fields(self):object.__setattr__(self,field.name,_freeze(getattr(self,field.name)))

@dataclass(frozen=True)
class AcquisitionServices:
    binary: Callable[[str], str | None]
    descriptor_public: Callable[[str], dict[str, Any]]
    now: Callable[[Any], datetime]
    cancelled: type[Exception]
    prime_regular_file_sha256_cache: Callable[..., Any]
    regular_file_sha256_identity: Callable[..., Any]
    display_size: Callable[..., Any]
    physical_memory_bytes: Callable[..., Any]
    read_json: Callable[..., Any]
    safetensors_inventory: Callable[..., Any]
    weight_completeness: Callable[..., Any]


def directory_size(path: Path) -> int:
    """Measure regular files without following user-controlled symlink trees."""
    total = 0
    try:
        if not path.exists() or not path.is_dir():
            return 0
        for root, directories, files in os.walk(path, followlinks=False):
            directories[:] = [
                name for name in directories
                if not (Path(root) / name).is_symlink()
            ]
            for name in files:
                item = Path(root) / name
                try:
                    if not item.is_symlink() and item.is_file():
                        total += item.stat().st_size
                except OSError:
                    continue
    except OSError:
        return total
    return total


def disk_free_for(path: Path) -> int:
    """Return free bytes on the volume that will hold a not-yet-created path."""
    anchor = path.expanduser()
    while not anchor.exists() and anchor != anchor.parent:
        anchor = anchor.parent
    try:
        return int(shutil.disk_usage(anchor).free)
    except OSError:
        return 0


def default_dflash2_download_root() -> Path:
    """Keep launcher-managed downloads in oMLX's conventional model tree."""
    return Path.home() / ".omlx" / "models"


def _hf_public_environment() -> dict[str, str]:
    """Use the Hub anonymously; browser payloads never receive or supply tokens."""
    environment = dict(os.environ)
    environment.pop("HF_TOKEN", None)
    environment.pop("HUGGING_FACE_HUB_TOKEN", None)
    environment["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    environment["HF_HUB_DISABLE_TELEMETRY"] = "1"
    return environment


def validated_hf_repo_id(value: Any) -> str:
    repo_id = str(value or "").strip()
    if (
        len(repo_id) > 194
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}/[A-Za-z0-9][A-Za-z0-9._-]{0,95}", repo_id)
        or ".." in repo_id
    ):
        raise ValueError("Enter a model repository as owner/name.")
    return repo_id


def validated_hf_revision(value: Any) -> str:
    revision = str(value or "").strip()
    if not revision:
        return ""
    if (
        len(revision) > 160 or ".." in revision or "//" in revision
        or revision.startswith("/") or revision.endswith("/")
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", revision)
    ):
        raise ValueError("The revision must be a branch, tag, or commit name without traversal segments.")
    return revision


def _hub_license(tags: list[str], card_data: Any = None) -> str:
    tagged = next((item.split(":", 1)[1] for item in tags if item.startswith("license:") and ":" in item), "")
    if tagged:
        return tagged[:80]
    if isinstance(card_data, dict) and isinstance(card_data.get("license"), str):
        return str(card_data["license"])[:80]
    return "Not declared"


def _valid_hub_file_path(value: Any) -> str | None:
    path = str(value or "")
    parts = path.split("/")
    if (
        not path or len(path) > 512 or path.startswith("/")
        or any(part in {"", ".", ".."} for part in parts)
        or "\x00" in path or "\\" in path
    ):
        return None
    return path


def model_acquisition_roots() -> list[dict[str, Any]]:
    roots = [
        ("lmstudio", "LM Studio catalog", Path.home() / ".lmstudio" / "models"),
        ("omlx", "oMLX models", Path.home() / ".omlx" / "models"),
        ("mtplx", "MTPLX models", Path.home() / ".mtplx" / "models"),
        ("documents", "Documents models", Path.home() / "Documents" / "models"),
    ]
    return [{"id": item, "label": label, "path": str(path.expanduser().resolve(strict=False))} for item, label, path in roots]


class AcquisitionPlanning:
    def __init__(self, policy: AcquisitionPolicy, services: AcquisitionServices):
        self.policy, self.services = policy, services

    def build_dflash2_setup_plan(self, 
        model: dict[str, Any], download_root: Path | None = None,
    ) -> dict[str, Any]:
        """Describe exact local changes without making any of them."""
        capability = model.get("backends", {}).get("omlx", {})
        readiness = capability.get("dflashReadiness")
        if not isinstance(readiness, dict) or readiness.get("targetCompatible") is not True:
            raise ValueError("This model has no published, geometry-matched DFlash 2 setup path.")

        configured_root = (download_root or default_dflash2_download_root()).expanduser()
        detected_path = readiness.get("draftPath")
        if isinstance(detected_path, str) and detected_path.strip():
            destination = Path(detected_path).expanduser()
        else:
            destination = configured_root / "z-lab" / "Qwen3.8-27B-DFlash2"
        destination = destination.resolve(strict=False)
        existing_bytes = directory_size(destination)
        remaining_bytes = max(0, self.policy.dflash2_draft_bytes - existing_bytes)
        free_bytes = disk_free_for(destination)
        admission_bytes = remaining_bytes + self.policy.setup_download_reserve_bytes
        draft_complete = bool(readiness.get("draftInstalled") and readiness.get("draftComplete"))
        runtime_ready = bool(readiness.get("runtimeReady"))
        runtime_recommended = bool(readiness.get("runtimeRecommended"))
        downloader = self.services.binary("hf")
        disk_ready = free_bytes >= admission_bytes if not draft_complete else True
        can_download = bool(not draft_complete and downloader and disk_ready)
        plan_identity = {
            "model": model.get("id"), "destination": str(destination),
            "revision": self.policy.dflash2_draft_revision,
            "runtime": readiness.get("runtimeDetected"),
        }
        plan_id = hashlib.sha256(
            json.dumps(plan_identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:20]
        steps_remaining = int(not runtime_ready) + int(not draft_complete)
        return {
            "id": plan_id,
            "kind": "dflash2",
            "ready": bool(runtime_ready and draft_complete),
            "stepsRemaining": steps_remaining,
            "target": {
                "modelId": model.get("id"), "name": model.get("name"),
                "path": model.get("path"), "compatible": True,
                "detail": readiness.get("targetReason"),
            },
            "runtime": {
                "detected": readiness.get("runtimeDetected") or "Not installed",
                "minimum": self.policy.dflash2_minimum_runtime,
                "recommended": self.policy.dflash2_recommended_runtime,
                "supported": runtime_ready,
                "recommendedBuild": runtime_recommended,
                "channel": "release-candidate",
                "automatic": False,
                "releaseUrl": self.policy.dflash2_release_url,
                "detail": (
                    "The installed runtime has the recommended DFlash 2 fixes."
                    if runtime_recommended else
                    f"A supported runtime is installed; {self.policy.dflash2_recommended_runtime} is the current audited preview."
                    if runtime_ready else
                    "Upgrade through the official oMLX release flow. The launcher will not replace a runtime automatically."
                ),
            },
            "draft": {
                "repo": self.policy.dflash2_draft_repo,
                "url": self.policy.dflash2_draft_url,
                "revision": self.policy.dflash2_draft_revision,
                "sizeBytes": self.policy.dflash2_draft_bytes,
                "sizeLabel": self.policy.dflash2_draft_size_label,
                "destination": str(destination),
                "detected": bool(readiness.get("draftDetected")),
                "complete": draft_complete,
                "status": readiness.get("draftStatus") or "Not installed",
                "existingBytes": existing_bytes,
                "remainingBytes": 0 if draft_complete else remaining_bytes,
                "freeBytes": free_bytes,
                "admissionBytes": 0 if draft_complete else admission_bytes,
                "diskReady": disk_ready,
                "downloaderReady": bool(downloader),
                "downloaderPath": downloader,
                "canDownload": can_download,
                "detail": (
                    "The complete pinned draft is already installed."
                    if draft_complete else
                    "The launcher can resume or start this pinned public download. Existing files are preserved."
                    if can_download else
                    "The bundled Hugging Face downloader is unavailable. Open the model page to install it manually."
                    if not downloader else
                    f"Free at least {self.services.display_size(admission_bytes - free_bytes)} more disk space before downloading."
                ),
            },
            "verification": {
                "automatic": True,
                "checks": [
                    "Pinned repository revision",
                    "Complete safetensors header and byte ranges",
                    "DFlash 2 tensor names and exact shapes",
                    "Target layer, vocabulary and hidden-size pairing",
                    "Fresh local Benchmark Lab result before automatic selection",
                ],
            },
            "safety": {
                "requiresExplicitConsent": True,
                "downloadOnly": True,
                "preservesPartialFiles": True,
                "changesRuntime": False,
                "changesAgentConfig": False,
                "changesModelWeights": False,
            },
        }


    def validated_setup_request(self, 
        payload: dict[str, Any], models: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        model_id = str(payload.get("modelId") or "")
        model = next((item for item in models if item.get("id") == model_id), None)
        if not model:
            raise ValueError("The selected setup target is no longer in the scanned catalog. Refresh models.")
        return model, self.build_dflash2_setup_plan(model)


    def build_dflash2_download_argv(self, plan: dict[str, Any]) -> list[str]:
        """Build a fixed-identity, argv-safe public Hub download command."""
        draft = plan.get("draft") if isinstance(plan.get("draft"), dict) else {}
        downloader = self.services.binary("hf")
        if not downloader or draft.get("repo") != self.policy.dflash2_draft_repo:
            raise ValueError("The pinned DFlash 2 downloader is unavailable.")
        if draft.get("revision") != self.policy.dflash2_draft_revision:
            raise ValueError("The DFlash 2 revision changed; refresh the setup plan.")
        destination = str(draft.get("destination") or "")
        if not destination or "\x00" in destination or not os.path.isabs(destination):
            raise ValueError("The DFlash 2 destination is invalid.")
        return [
            downloader, "download", self.policy.dflash2_draft_repo,
            "--revision", self.policy.dflash2_draft_revision,
            "--local-dir", destination,
            "--include", "*.json",
            "--include", "*.safetensors",
            "--include", "README.md",
            "--format", "quiet",
        ]


    def run_hf_json(self, arguments: list[str], timeout: float = 30.0) -> Any:
        """Run one bounded, anonymous, read-only Hub CLI query and parse JSON."""
        downloader = self.services.binary("hf")
        if not downloader:
            raise ValueError("The launcher-managed Hugging Face client is unavailable.")
        if not arguments or any(not isinstance(item, str) or "\x00" in item for item in arguments):
            raise ValueError("The Hugging Face request is invalid.")
        try:
            result = owned_cli_capture.capture_owned_cli(
                [downloader, *arguments], timeout=timeout,
                max_bytes=32 * 1024**2, environment=_hf_public_environment(),
            )
        except owned_cli_capture.CaptureLimitError as error:
            raise ValueError("The Hub returned more metadata than the launcher can inspect safely.") from error
        except owned_cli_capture.CaptureOwnershipError as error:
            raise ValueError("The public Hugging Face metadata request could not finish safely.") from error
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError("The public Hugging Face metadata request did not complete.") from error
        encoding = "utf-8" if sys.flags.utf8_mode else locale.getpreferredencoding(False)
        output = (result.stdout or b"").decode(encoding).replace("\r\n", "\n").replace("\r", "\n")
        if len(output) > 8 * 1024 * 1024:
            raise ValueError("The Hub returned more metadata than the launcher can inspect safely.")
        if result.returncode != 0:
            detail = " ".join(output.strip().split())[-600:]
            if "gated" in detail.lower() or "401" in detail or "403" in detail:
                raise ValueError("This repository needs gated or private Hub access; the public acquisition path cannot use saved account tokens.")
            if "not found" in detail.lower() or "404" in detail:
                raise ValueError("The public model repository or requested revision was not found.")
            raise ValueError(f"Hugging Face rejected the metadata request.{f' {detail}' if detail else ''}")
        try:
            return json.loads(output)
        except json.JSONDecodeError as error:
            raise ValueError("The installed Hugging Face client returned invalid metadata.") from error


    def model_acquisition_search(self, query: Any) -> dict[str, Any]:
        """Search public text-generation repositories without using saved Hub auth."""
        normalized = " ".join(str(query or "").split())
        if not 2 <= len(normalized) <= 100 or any(ord(char) < 32 for char in normalized):
            raise ValueError("Enter between 2 and 100 visible characters to search the public Hub.")
        raw = self.run_hf_json([
            "models", "list", "--search", normalized,
            "--pipeline-tag", "text-generation",
            "--limit", str(self.policy.model_acquisition_search_limit),
            "--sort", "downloads",
            "--expand", "sha,gated,private,disabled,tags,downloads,likes,lastModified",
            "--format", "json", "--no-truncate",
        ])
        if not isinstance(raw, list):
            raise ValueError("The Hub returned an invalid model search result.")
        results: list[dict[str, Any]] = []
        for item in raw[:self.policy.model_acquisition_search_limit]:
            if not isinstance(item, dict):
                continue
            try:
                repo_id = validated_hf_repo_id(item.get("id"))
            except ValueError:
                continue
            tags = [str(tag)[:120] for tag in item.get("tags", []) if isinstance(tag, str)][:80]
            formats = []
            if "mlx" in tags:
                formats.append("MLX")
            if "gguf" in tags:
                formats.append("GGUF")
            quantization = next(
                (tag.upper() for tag in tags if re.fullmatch(r"(?:[2-8]-bit|q\d(?:_[a-z0-9]+)?)", tag.lower())),
                "Inspect files",
            )
            blocked = bool(item.get("gated") or item.get("private") or item.get("disabled"))
            results.append({
                "id": repo_id,
                "url": f"https://huggingface.co/{repo_id}",
                "revision": str(item.get("sha") or "")[:64],
                "gated": bool(item.get("gated")),
                "private": bool(item.get("private")),
                "disabled": bool(item.get("disabled")),
                "inspectable": not blocked,
                "license": _hub_license(tags),
                "formats": formats,
                "quantization": quantization,
                "downloads": int(item.get("downloads") or 0),
                "likes": int(item.get("likes") or 0),
                "lastModified": str(item.get("last_modified") or ""),
                "draftOnly": "draft-model" in tags,
                "tags": tags[:12],
            })
        return {
            "schemaVersion": self.policy.model_acquisition_schema_version,
            "query": normalized,
            "publicAnonymous": True,
            "results": results,
        }


    def fetch_model_acquisition_snapshot(self, repo_value: Any, revision_value: Any = "") -> dict[str, Any]:
        """Resolve one moving Hub name to an immutable public repository snapshot."""
        repo_id = validated_hf_repo_id(repo_value)
        requested_revision = validated_hf_revision(revision_value)
        info_args = [
            "models", "info", repo_id,
            "--expand", "sha,gated,private,disabled,usedStorage,tags,downloads,likes,lastModified,cardData",
            "--format", "json", "--no-truncate",
        ]
        if requested_revision:
            info_args[3:3] = ["--revision", requested_revision]
        info = self.run_hf_json(info_args)
        if not isinstance(info, dict):
            raise ValueError("The Hub returned invalid repository metadata.")
        canonical_id = validated_hf_repo_id(info.get("id") or repo_id)
        pinned_revision = str(info.get("sha") or "").lower()
        if not re.fullmatch(r"[0-9a-f]{40,64}", pinned_revision):
            raise ValueError("The Hub did not return an immutable commit for this repository.")
        tree = self.run_hf_json([
            "models", "list", canonical_id, "-R", "--revision", pinned_revision,
            "--format", "json", "--no-truncate",
        ], timeout=45.0)
        if not isinstance(tree, list):
            raise ValueError("The Hub returned an invalid pinned file inventory.")
        files: list[dict[str, Any]] = []
        for raw in tree:
            if not isinstance(raw, dict) or not isinstance(raw.get("size"), int):
                continue
            path = _valid_hub_file_path(raw.get("path"))
            size = int(raw.get("size") or 0)
            if not path or size < 0 or size > self.policy.model_acquisition_max_remote_bytes:
                continue
            security = raw.get("security") if isinstance(raw.get("security"), dict) else {}
            lfs = raw.get("lfs") if isinstance(raw.get("lfs"), dict) else {}
            checksum = str(lfs.get("sha256") or "").lower()
            files.append({
                "path": path,
                "size": size,
                "sha256": checksum if re.fullmatch(r"[0-9a-f]{64}", checksum) else "",
                "securitySafe": security.get("safe") if isinstance(security.get("safe"), bool) else None,
                "securityStatus": str(security.get("status") or "unreported")[:40],
            })
        if not files:
            raise ValueError("This repository has no downloadable files in its pinned snapshot.")
        tags = [str(tag)[:120] for tag in info.get("tags", []) if isinstance(tag, str)][:100]
        used_storage = info.get("used_storage")
        if not isinstance(used_storage, int) or isinstance(used_storage, bool) or used_storage < 0:
            used_storage = sum(item["size"] for item in files)
        return {
            "repoId": canonical_id,
            "url": f"https://huggingface.co/{canonical_id}",
            "requestedRevision": requested_revision or "default branch",
            "pinnedRevision": pinned_revision,
            "gated": bool(info.get("gated")),
            "private": bool(info.get("private")),
            "disabled": bool(info.get("disabled")),
            "downloads": int(info.get("downloads") or 0),
            "likes": int(info.get("likes") or 0),
            "lastModified": str(info.get("last_modified") or ""),
            "license": _hub_license(tags, info.get("card_data")),
            "tags": tags,
            "usedStorage": int(used_storage),
            "draftOnly": "draft-model" in tags,
            "customCode": "custom_code" in tags or any("/" not in item["path"] and item["path"].endswith(".py") for item in files),
            "files": files,
        }


    def _acquisition_metadata_files(self, files: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {**item, "role": "metadata"}
            for item in files
            if "/" not in item["path"]
            and item["path"] in self.policy._acquisition_metadata_names
            and item["size"] <= 64 * 1024**2
        ]


    def llamacpp_atomic_shard_relative(self, index: int) -> str:
        if not 1 <= index <= len(self.policy.llamacpp_atomic_file_manifest):
            raise ValueError("AtomicChat shard index is outside the immutable manifest.")
        return self.policy.llamacpp_atomic_file_manifest[index - 1][0]


    def _llamacpp_atomic_acquisition_variant(self, 
        snapshot: dict[str, Any], files: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Select only the pinned AtomicChat AD-3.84 split; no sibling quant is eligible."""
        if (
            snapshot.get("repoId") != self.policy.llamacpp_atomic_repo
            or snapshot.get("pinnedRevision") != self.policy.llamacpp_atomic_revision
        ):
            return None
        by_path = {
            str(item.get("path") or ""): item
            for item in files if isinstance(item, dict)
        }
        selected: list[dict[str, Any]] = []
        for relative, expected_size, expected_checksum in self.policy.llamacpp_atomic_file_manifest:
            item = by_path.get(relative)
            if (
                not isinstance(item, dict)
                or item.get("size") != expected_size
                or item.get("sha256") != expected_checksum
            ):
                return None
            selected.append({**item, "role": "weight"})
        total = sum(int(item["size"]) for item in selected)
        if total != self.policy.llamacpp_atomic_total_bytes:
            return None
        return {
            "id": self.policy.llamacpp_atomic_variant_id,
            "label": f"{self.policy.llamacpp_atomic_variant} · SSD-only PLE",
            "format": "gguf",
            "route": "llamacpp-atomic-ssd-ple",
            "files": selected,
            "fileCount": len(selected),
            "weightBytes": total,
            "sizeBytes": total,
        }


    def model_acquisition_variants(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        """Return exact safe file sets; never download every GGUF quantisation at once."""
        files = [item for item in snapshot.get("files", []) if isinstance(item, dict)]
        metadata = self._acquisition_metadata_files(files)
        tags = snapshot.get("tags") if isinstance(snapshot.get("tags"), list) else []
        variants: list[dict[str, Any]] = []
        atomic_variant = self._llamacpp_atomic_acquisition_variant(snapshot, files)
        if atomic_variant is not None:
            variants.append(atomic_variant)
        if "mlx" in tags:
            weights = [
                {**item, "role": "weight"}
                for item in files
                if "/" not in item["path"] and re.fullmatch(
                    r"(?:model(?:-\d{5}-of-\d{5})?|mtp)\.safetensors",
                    item["path"], re.IGNORECASE,
                )
            ]
            if any(item["path"] == "config.json" for item in metadata) and any(
                item["path"].lower().startswith("model") for item in weights
            ):
                selection = [*metadata, *weights]
                variants.append({
                    "id": "mlx-snapshot", "label": "Complete MLX checkpoint",
                    "format": "mlx", "files": selection,
                    "fileCount": len(selection),
                    "weightBytes": sum(item["size"] for item in weights),
                    "sizeBytes": sum(item["size"] for item in selection),
                })

        ggufs = [item for item in files if "/" not in item["path"] and item["path"].lower().endswith(".gguf")]
        shard_groups: dict[str, dict[str, Any]] = {}
        singles: list[dict[str, Any]] = []
        for item in ggufs:
            match = re.fullmatch(r"(.+)-(\d{5})-of-(\d{5})\.gguf", item["path"], re.IGNORECASE)
            if not match:
                singles.append(item)
                continue
            key = match.group(1)
            group = shard_groups.setdefault(key, {"total": int(match.group(3)), "files": []})
            if group["total"] == int(match.group(3)):
                group["files"].append(item)
        gguf_sets: list[tuple[str, list[dict[str, Any]]]] = [
            (item["path"][:-5], [item]) for item in singles
        ]
        for name, group in shard_groups.items():
            ordered = sorted(group["files"], key=lambda item: item["path"])
            if len(ordered) == group["total"]:
                gguf_sets.append((name, ordered))
        for name, weights_raw in sorted(gguf_sets, key=lambda item: sum(file["size"] for file in item[1]))[:24]:
            weights = [{**item, "role": "weight"} for item in weights_raw]
            selection = [*metadata, *weights]
            variant_id = f"gguf-{hashlib.sha256(name.encode('utf-8')).hexdigest()[:12]}"
            variants.append({
                "id": variant_id, "label": name, "format": "gguf",
                "files": selection, "fileCount": len(selection),
                "weightBytes": sum(item["size"] for item in weights),
                "sizeBytes": sum(item["size"] for item in selection),
            })
        return [
            variant for variant in variants
            if 0 < variant["fileCount"] <= self.policy.model_acquisition_max_files
            and 0 < variant["sizeBytes"] <= self.policy.model_acquisition_max_remote_bytes
        ]


    def _acquisition_safe_child(self, destination: Path, relative: str) -> Path:
        valid = _valid_hub_file_path(relative)
        if not valid:
            raise ValueError("The pinned repository contains an invalid file path.")
        candidate = (destination / valid).resolve(strict=False)
        try:
            candidate.relative_to(destination.resolve(strict=False))
        except ValueError as error:
            raise ValueError("A pinned repository file escapes the selected destination.") from error
        return candidate


    def _acquisition_present_bytes(self, destination: Path, files: list[dict[str, Any]]) -> int:
        total = 0
        for item in files:
            path = self._acquisition_safe_child(destination, str(item["path"]))
            try:
                if path.is_file() and not path.is_symlink():
                    total += min(int(item["size"]), int(path.stat().st_size))
            except OSError:
                continue
        return total


    def build_model_acquisition_plan(self, 
        snapshot: dict[str, Any], destination_kind: Any = "lmstudio",
        variant_value: Any = "",
    ) -> dict[str, Any]:
        """Build one immutable, side-effect-free download plan from pinned metadata."""
        roots = {item["id"]: item for item in model_acquisition_roots()}
        kind = str(destination_kind or "lmstudio")
        if kind not in roots:
            raise ValueError("Choose one of the launcher’s known model folders.")
        variants = self.model_acquisition_variants(snapshot)
        requested_variant = str(variant_value or "")
        variant = next((item for item in variants if item["id"] == requested_variant), None)
        if variant is None and len(variants) == 1 and not requested_variant:
            variant = variants[0]
        if requested_variant and variant is None:
            raise ValueError("The selected model-file variant is no longer in the pinned repository.")

        repo_id = validated_hf_repo_id(snapshot.get("repoId"))
        pinned = str(snapshot.get("pinnedRevision") or "")
        if not re.fullmatch(r"[0-9a-f]{40,64}", pinned):
            raise ValueError("The acquisition snapshot is not pinned to an immutable commit.")
        owner, name = repo_id.split("/", 1)
        root = Path(roots[kind]["path"])
        destination = (root / owner / name).resolve(strict=False)
        try:
            destination.relative_to(root.resolve(strict=False))
        except ValueError as error:
            raise ValueError("The model destination escapes its known model folder.") from error
        marker_path = destination / self.policy.model_acquisition_marker
        marker = self.services.read_json(marker_path)
        marker_match = bool(
            marker.get("schemaVersion") == self.policy.model_acquisition_schema_version
            and marker.get("repoId") == repo_id
            and marker.get("pinnedRevision") == pinned
            and variant is not None
            and marker.get("variantId") == variant["id"]
        )
        collision = destination.is_symlink()
        if destination.exists() and not marker_match and not collision:
            try:
                collision = any(item.name not in {".cache", self.policy.model_acquisition_marker} for item in destination.iterdir())
            except OSError:
                collision = True
        selected_files = copy.deepcopy(variant["files"]) if variant else []
        existing_bytes = self._acquisition_present_bytes(destination, selected_files) if selected_files else 0
        selection_bytes = int(variant["sizeBytes"]) if variant else 0
        remaining_bytes = max(0, selection_bytes - existing_bytes)
        free_bytes = disk_free_for(destination)
        admission_bytes = remaining_bytes + self.policy.model_acquisition_download_reserve_bytes
        disk_ready = free_bytes >= admission_bytes if variant else False
        physical_bytes = self.services.physical_memory_bytes()
        estimated_memory = (int(variant["weightBytes"]) + self.policy.model_acquisition_memory_reserve_bytes) if variant else 0
        memory_state = "unknown" if physical_bytes <= 0 or not variant else "fits" if estimated_memory <= physical_bytes else "tight"
        tags = snapshot.get("tags") if isinstance(snapshot.get("tags"), list) else []
        public_access = not bool(snapshot.get("gated") or snapshot.get("private") or snapshot.get("disabled"))
        security_statuses = [
            str(item.get("securityStatus") or "unreported").strip().lower().replace("-", "_")
            for item in selected_files
        ]
        explicitly_unsafe = any(
            item.get("securitySafe") is False
            and any(marker in status for marker in ("unsafe", "infected", "malicious", "virus"))
            for item, status in zip(selected_files, security_statuses, strict=True)
        )
        security_complete = bool(variant) and all(item.get("securitySafe") is True for item in selected_files)
        security_clear = bool(variant) and not explicitly_unsafe
        standard_artifact = not bool(snapshot.get("draftOnly") or snapshot.get("customCode"))
        downloader_ready = bool(self.services.binary("hf"))
        complete_by_size = bool(variant and remaining_bytes == 0 and marker_match)
        blocked = bool(
            not public_access or not variant or not security_clear or not standard_artifact
            or collision or not disk_ready or not downloader_ready
        )
        plan_identity = {
            "schemaVersion": self.policy.model_acquisition_schema_version,
            "repoId": repo_id, "pinnedRevision": pinned,
            "destination": str(destination),
            "variantId": variant["id"] if variant else "",
        }
        plan_id = hashlib.sha256(json.dumps(
            plan_identity, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()[:24]

        expected_engines: list[dict[str, Any]] = []
        selected_format = str(variant.get("format") or "") if variant else ""
        dedicated_llamacpp_ple = bool(
            variant
            and repo_id == self.policy.llamacpp_atomic_repo
            and pinned == self.policy.llamacpp_atomic_revision
            and variant.get("id") == self.policy.llamacpp_atomic_variant_id
        )
        for engine_id, descriptor in self.policy.engine_adapters.items():
            installed = self.services.descriptor_public(descriptor.id)["installed"] is True
            if dedicated_llamacpp_ple:
                compatible = engine_id == "llamacpp"
                detail = (
                    "Exact pinned AtomicChat AD-3.84 split for the launcher-owned llama.cpp SSD-PLE route."
                    if compatible else
                    "This exact low-memory PLE acquisition is qualified only through the dedicated llama.cpp route."
                )
            elif selected_format == "mlx":
                compatible = engine_id in {"omlx", "mtplx"} or (engine_id == "lmstudio" and kind == "lmstudio")
                detail = (
                    "Expected MLX candidate; the post-download scanner still validates this checkpoint."
                    if engine_id in {"omlx", "mtplx"} else
                    "Downloaded into LM Studio’s catalog; its local runtime still validates the checkpoint."
                    if kind == "lmstudio" else
                    "LM Studio requires this artifact to be imported into its catalog first."
                )
            elif selected_format == "gguf":
                compatible = engine_id == "lmstudio" and kind == "lmstudio"
                detail = (
                    "Downloaded into LM Studio’s catalog; LM Studio performs the final GGUF validation."
                    if compatible else "This launcher route does not load GGUF directly."
                )
            else:
                compatible = False
                detail = "Choose a supported file variant first."
            expected_engines.append({
                "id": engine_id, "label": descriptor.label,
                "installed": installed, "expectedCompatible": compatible,
                "expectedReady": bool(installed and compatible), "detail": detail,
            })

        checks = [{
            "id": "access", "label": "Public repository access",
            "state": "pass" if public_access else "blocked",
            "detail": "Anonymous metadata and download access are available." if public_access else "Gated, private, or disabled repositories are not downloaded by this public path.",
        }, {
            "id": "artifact", "label": "Standard local artifact",
            "state": "pass" if standard_artifact and variant else "blocked",
            "detail": (
                f"{variant['label']} selects {variant['fileCount']} exact files."
                if variant and standard_artifact else
                "Draft-only and custom-code repositories are not installed as standalone chat targets."
                if not standard_artifact else "Choose one exact MLX or GGUF file set."
            ),
        }, {
            "id": "security", "label": "Selected file scan",
            "state": "pass" if security_complete else "advisory" if security_clear else "blocked",
            "detail": (
                "Every selected file currently has a safe Hub scan result."
                if security_complete else
                "No selected file is explicitly marked unsafe; at least one Hub scan is pending, unavailable, or unreported. Only standard non-code files are selected, and post-download verification still applies."
                if security_clear else
                "At least one selected file is explicitly marked unsafe by the Hub, or no exact file set is selected."
            ),
        }, {
            "id": "destination", "label": "Owned destination",
            "state": "pass" if not collision else "blocked",
            "detail": "The destination is new or has a matching launcher resume marker." if not collision else "The destination already contains files not owned by this acquisition plan.",
        }, {
            "id": "disk", "label": "Disk admission",
            "state": "pass" if disk_ready else "blocked",
            "detail": (
                f"{self.services.display_size(free_bytes)} free; {self.services.display_size(admission_bytes)} required including reserve."
                if variant else "Choose an exact file set before checking disk admission."
            ),
        }, {
            "id": "memory", "label": "Conservative memory fit",
            "state": "pass" if memory_state == "fits" else "advisory",
            "detail": (
                f"Weights plus an {self.services.display_size(self.policy.model_acquisition_memory_reserve_bytes)} runtime reserve fit within {self.services.display_size(physical_bytes)} physical memory."
                if memory_state == "fits" else
                f"The conservative {self.services.display_size(estimated_memory)} estimate exceeds {self.services.display_size(physical_bytes)} physical memory; smaller context/offload may still work."
                if memory_state == "tight" else "Physical-memory capacity could not be read; download size is not a loadability guarantee."
            ),
        }]
        return {
            "schemaVersion": self.policy.model_acquisition_schema_version,
            "id": plan_id,
            "expiresAt": (self.services.now(timezone.utc) + timedelta(seconds=self.policy.model_acquisition_plan_ttl_seconds)).isoformat(),
            "repo": {
                "id": repo_id, "url": str(snapshot.get("url") or f"https://huggingface.co/{repo_id}"),
                "requestedRevision": str(snapshot.get("requestedRevision") or "default branch"),
                "pinnedRevision": pinned, "license": str(snapshot.get("license") or "Not declared"),
                "gated": bool(snapshot.get("gated")), "private": bool(snapshot.get("private")),
                "downloads": int(snapshot.get("downloads") or 0), "likes": int(snapshot.get("likes") or 0),
                "lastModified": str(snapshot.get("lastModified") or ""), "tags": list(tags[:16]),
            },
            "variants": [{key: value for key, value in item.items() if key != "files"} for item in variants],
            "selection": None if not variant else {
                "id": variant["id"], "label": variant["label"], "format": variant["format"],
                "fileCount": variant["fileCount"], "sizeBytes": variant["sizeBytes"],
                "weightBytes": variant["weightBytes"], "files": selected_files,
            },
            "variantRequired": variant is None and len(variants) > 1,
            "destination": {
                "kind": kind, "label": roots[kind]["label"], "root": roots[kind]["path"],
                "path": str(destination), "markerPath": str(marker_path),
                "markerMatch": marker_match, "collision": collision,
                "existingBytes": existing_bytes, "remainingBytes": remaining_bytes,
                "freeBytes": free_bytes, "admissionBytes": admission_bytes,
                "diskReady": disk_ready, "completeBySize": complete_by_size,
            },
            "memory": {
                "state": memory_state, "physicalBytes": physical_bytes,
                "estimatedMinimumBytes": estimated_memory,
                "detail": next(check["detail"] for check in checks if check["id"] == "memory"),
            },
            "expectedEngines": expected_engines,
            "checks": checks,
            "canStart": not blocked,
            "action": "verify" if complete_by_size else "download",
            "actionLabel": "Verify existing pinned files" if complete_by_size else "Download pinned files",
            "confirmation": f"{repo_id}@{pinned}",
            "safety": {
                "publicAnonymous": True, "requiresExplicitConsent": True,
                "requiresLicenseReview": True, "pinnedRevision": True,
                "exactFileList": True, "preservesPartialFiles": True,
                "hubSecurityScanComplete": security_complete,
                "explicitUnsafeFile": explicitly_unsafe,
                "deletesFiles": False, "runsDownloadedCode": False,
                "startsRuntime": False, "changesAgentConfig": False,
            },
        }


    def build_model_acquisition_download_argv(self, plan: dict[str, Any]) -> list[str]:
        downloader = self.services.binary("hf")
        repo = plan.get("repo") if isinstance(plan.get("repo"), dict) else {}
        selection = plan.get("selection") if isinstance(plan.get("selection"), dict) else {}
        destination = plan.get("destination") if isinstance(plan.get("destination"), dict) else {}
        repo_id = validated_hf_repo_id(repo.get("id"))
        revision = str(repo.get("pinnedRevision") or "")
        if not downloader or not re.fullmatch(r"[0-9a-f]{40,64}", revision):
            raise ValueError("The pinned public downloader is unavailable.")
        destination_path = Path(str(destination.get("path") or ""))
        roots = [Path(item["path"]).resolve(strict=False) for item in model_acquisition_roots()]
        resolved = destination_path.resolve(strict=False)
        if not destination_path.is_absolute() or not any(
            resolved == root or root in resolved.parents for root in roots
        ):
            raise ValueError("The acquisition destination is outside the known model folders.")
        files = selection.get("files") if isinstance(selection.get("files"), list) else []
        names = [str(item.get("path") or "") for item in files if isinstance(item, dict)]
        if not names or len(names) > self.policy.model_acquisition_max_files or any(_valid_hub_file_path(name) != name for name in names):
            raise ValueError("The pinned acquisition file list is invalid.")
        return [
            downloader, "download", repo_id, *names,
            "--revision", revision, "--local-dir", str(resolved),
            "--max-workers", "4", "--format", "quiet",
        ]


    def verify_model_acquisition(self, 
        plan: dict[str, Any], cancel_event: threading.Event | None = None,
        progress: Any = None,
    ) -> dict[str, Any]:
        """Verify exact sizes/checksums and the selected local artifact format."""
        selection = plan.get("selection") if isinstance(plan.get("selection"), dict) else {}
        destination_info = plan.get("destination") if isinstance(plan.get("destination"), dict) else {}
        destination = Path(str(destination_info.get("path") or "")).resolve(strict=True)
        files = selection.get("files") if isinstance(selection.get("files"), list) else []
        weights = [item for item in files if isinstance(item, dict) and item.get("role") == "weight"]
        if not files or not weights:
            raise ValueError("The pinned acquisition has no verifiable weight files.")
        checked = 0
        total_hash_bytes = sum(int(item.get("size") or 0) for item in weights if item.get("sha256"))
        hashed = 0
        verified_hashes: list[tuple[Path, str, os.stat_result]] = []
        for item in files:
            if cancel_event and cancel_event.is_set():
                raise self.services.cancelled("Model acquisition verification cancelled.")
            path = self._acquisition_safe_child(destination, str(item.get("path") or ""))
            try:
                stat_result = path.stat()
            except OSError as error:
                raise ValueError(f"The pinned file {item.get('path')} is missing.") from error
            if path.is_symlink() or not path.is_file() or stat_result.st_size != int(item.get("size") or -1):
                raise ValueError(f"The pinned file {item.get('path')} has the wrong size or type.")
            checksum = str(item.get("sha256") or "")
            if checksum:
                digest = hashlib.sha256()
                with open(path, "rb") as handle:
                    while True:
                        if cancel_event and cancel_event.is_set():
                            raise self.services.cancelled("Model acquisition verification cancelled.")
                        chunk = handle.read(4 * 1024**2)
                        if not chunk:
                            break
                        digest.update(chunk)
                        hashed += len(chunk)
                        if callable(progress) and total_hash_bytes:
                            progress(min(1.0, hashed / total_hash_bytes))
                if not secrets.compare_digest(digest.hexdigest(), checksum):
                    raise ValueError(f"The SHA-256 checksum for {item.get('path')} does not match the pinned Hub manifest.")
                current = self.services.regular_file_sha256_identity(path, checksum)
                fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
                if current is None or any(
                    getattr(current[1], field) != getattr(stat_result, field)
                    for field in fields
                ):
                    raise ValueError(
                        f"The pinned file {item.get('path')} changed while its checksum was being verified."
                    )
                verified_hashes.append((path, checksum, current[1]))
            checked += 1
        selected_format = str(selection.get("format") or "")
        if selected_format == "mlx":
            config = self.services.read_json(destination / "config.json")
            ready, status, weight_bytes = self.services.weight_completeness(
                destination, config, ignore_acquisition_marker=True,
            )
            tensor_ready, tensors, manifest = self.services.safetensors_inventory(destination)
            if not ready or not tensor_ready:
                raise ValueError(f"The MLX checkpoint failed structural validation ({status}).")
            detail = f"Verified {len(tensors)} safetensors entries across {len(manifest)} shard files."
        elif selected_format == "gguf":
            for item in weights:
                path = self._acquisition_safe_child(destination, str(item["path"]))
                try:
                    with open(path, "rb") as handle:
                        if handle.read(4) != b"GGUF":
                            raise ValueError(f"{item['path']} is not a GGUF file.")
                except OSError as error:
                    raise ValueError(f"Could not validate {item['path']}.") from error
            weight_bytes = sum(int(item["size"]) for item in weights)
            detail = f"Verified {len(weights)} GGUF weight file{'s' if len(weights) != 1 else ''}."
        else:
            raise ValueError("The acquisition format is not supported.")
        for path, checksum, verified_details in verified_hashes:
            if not self.services.prime_regular_file_sha256_cache(path, checksum, verified_details):
                raise ValueError(
                    f"The pinned file {path.name} changed after its checksum was verified."
                )
        return {
            "verified": True, "format": selected_format,
            "checkedFiles": checked, "weightBytes": weight_bytes,
            "detail": detail,
        }
