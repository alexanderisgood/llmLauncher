"""Complete model discovery, current artifact records and library doctor.

Frozen registry/model policies and named live ports provide external facts.
CatalogState owns only model inspection receipts and current-process artifact
verification; persisted presentation snapshots never confer launch authority.
The controller retains presentation caching and mutation/launch orchestration.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, fields
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import subprocess
import threading
from types import MappingProxyType
from typing import Any, Callable, Mapping
import urllib.parse

import kolibri_runtime
import rec_runtime
import rapidmlx_runtime
import slotstream_runtime
import splash_runtime
import strata_runtime
import whallm_runtime
import runtime_identity
import runtime_probes
from sampling_contract import SUPPORTED_SAMPLING_FIELDS, SamplingContractError, canonicalize_sampling


class _FrozenList(list):
    def _readonly(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("Catalog policy sequences are immutable")
    __setitem__ = __delitem__ = append = clear = extend = insert = pop = remove = reverse = sort = __iadd__ = __imul__ = _readonly
    def __deepcopy__(self, memo: dict[int, Any]) -> _FrozenList:
        return self


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return _FrozenList(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return value


class _FrozenPolicy:
    def __post_init__(self) -> None:
        for item in fields(self):
            object.__setattr__(self, item.name, _freeze(getattr(self, item.name)))


@dataclass(frozen=True)
class CatalogDescriptor:
    id: str
    label: str
    kind: str
    binary_key: str | None
    protocol: str
    built_in: bool = False

    def public(self, selected_binary: Callable[[str], str | None]) -> dict[str, Any]:
        return {
            "id": self.id, "label": self.label, "kind": self.kind,
            "binaryKey": self.binary_key, "protocol": self.protocol,
            "builtIn": self.built_in,
            "installed": self.built_in or bool(self.binary_key and selected_binary(self.binary_key)),
        }


@dataclass
class CatalogState:
    atomic_lock: Any = field(default_factory=threading.RLock)
    atomic_current_process_proofs: dict[str, dict[str, Any]] = field(default_factory=dict)
    atomic_verification_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    atomic_verification_threads: dict[str, threading.Thread] = field(default_factory=dict)
    atomic_verification_generation: int = 0
    native_inspection_lock: Any = field(default_factory=threading.Lock)
    native_inspection_cache: dict[str, tuple[int, str]] = field(default_factory=dict)
    mtplx_inspection_cache: dict[tuple[Any, ...], tuple[int, str]] = field(default_factory=dict)


@dataclass(frozen=True)
class CatalogPaths:
    state_directory: Callable[[], Path]
    acquisition_roots: Callable[[], list[dict[str, Any]]]
    uzu_cache_root: Callable[[], Path]
    uzu_registry_path: Callable[[], Path]
    uzu_resolved_models_path: Callable[[], Path]


@dataclass(frozen=True)
class CatalogValues:
    deep_get: Callable[..., Any]
    safe_int: Callable[[Any, int, int, int], int]
    slug: Callable[..., str]
    display_size: Callable[[int], str]
    qwen_ple_config: Callable[[dict[str, Any]], bool]
    semantic_version_key: Callable[[str], tuple[int, ...]]


@dataclass(frozen=True)
class CatalogRuntimes:
    selected_binary: Callable[[str], str | None]
    command_version: Callable[[str | None], str]
    lmstudio_runtime_packs: Callable[[], list[dict[str, Any]]]
    app_status: Callable[[str], dict[str, Any]]
    plist_version: Callable[[Path], str]
    lmstudio_mtp_load_supported: Callable[[str | None], bool]
    lmstudio_assistant_drafter_load_supported: Callable[[str | None], bool]
    lmstudio_backend_preference: Callable[[], dict[str, Any]]
    lmstudio_runtime_identity: Callable[..., str]
    omlx_supports_dflash2: Callable[[str], bool]
    omlx_recommended_dflash_runtime: Callable[[str], bool]
    omlx_version_at_least: Callable[[str, str], bool]
    omlx_kernel_status: Callable[[str | None], dict[str, Any]]
    llamacpp_runtime_contract: Callable[[str | None], dict[str, Any]]
    uzu_runtime_contract: Callable[[str | None], dict[str, Any]]
    uzu_listener_protection_ready: Callable[[dict[str, Any]], bool]
    native_freetoken_host_supported: Callable[[], bool]
    physical_memory_bytes: Callable[[], int]


@dataclass(frozen=True)
class CatalogArtifacts:
    cached_regular_file_sha256_matches: Callable[[Path, str], bool]
    safetensors_inventory: Callable[..., tuple[bool, dict[str, Any], list[dict[str, Any]]]]
    qwen_ple_profile: Callable[..., dict[str, Any]]
    qwen_expert_offload_profile: Callable[..., dict[str, Any]]
    atomic_shard_relative: Callable[[int], str]


@dataclass(frozen=True)
class CatalogEvidence:
    load_benchmarks: Callable[[], list[dict[str, Any]]]
    load_ane_records: Callable[[], list[dict[str, Any]]]
    hardware_fingerprint: Callable[[], str]
    matching_benchmarks: Callable[..., list[dict[str, Any]]]
    latest_by_identity: Callable[[list[dict[str, Any]]], list[dict[str, Any]]]
    matching_ane_record: Callable[..., dict[str, Any] | None]
    verified_ane_record: Callable[..., bool]
    route_performance: Callable[..., dict[str, Any]]
    public_mode_label: Callable[[str, str], str]


@dataclass(frozen=True)
class CatalogSurfaces:
    resolved_support: Callable[[str, str, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class CatalogConnections:
    freetoken_connection: Callable[[], dict[str, Any]]
    whallm_endpoint: Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class CatalogIO:
    read_json: Callable[[Path], dict[str, Any]]
    atomic_json: Callable[..., None]
    run_catalog_cli: Callable[..., subprocess.CompletedProcess]
    token_hex: Callable[[int], str]


@dataclass(frozen=True)
class GeneralCatalogPolicy(_FrozenPolicy):
    default_context: int
    max_json: Any
    model_library_schema_version: int
    model_acquisition_schema_version: int
    model_acquisition_marker: str
    route_evidence_schema_version: int
    omlx_qwen4_qsa_allocation_step_tokens: int


@dataclass(frozen=True)
class SsdCatalogPolicy(_FrozenPolicy):
    ssd_artifact_backends: frozenset[str]
    ssd_streaming_backends: frozenset[str]
    ssd_streaming_contract_version: int
    ssd_streaming_min_weight_ratio: float
    mference_context_windows: tuple[Any, ...]
    mference_known_flags: frozenset[str]
    mference_streaming_arch_signatures: Mapping[str, Any]


@dataclass(frozen=True)
class DflashCatalogPolicy(_FrozenPolicy):
    dflash2_draft_repo: str
    dflash2_draft_size_label: str
    dflash2_draft_url: str
    dflash2_minimum_runtime: str
    dflash2_recommended_runtime: str
    dflash2_release_url: str
    dflash2_target_geometry: Mapping[str, Any]


@dataclass(frozen=True)
class AneCatalogPolicy(_FrozenPolicy):
    ane_cpu_tuner_reserve_bytes: int
    ane_fp16_clone_source_url: str
    ane_tuner_minimum_runtime: str
    ane_tuner_minimum_speedup_percent: float
    ane_tuner_release_url: str
    ane_tuner_repeats: int
    ane_tuner_reserve_bytes: int
    ane_tuner_sequence_length: int


@dataclass(frozen=True)
class AtomicCatalogPolicy(_FrozenPolicy):
    atomic_presentation_snapshot_max_bytes: int
    atomic_presentation_snapshot_schema_version: int
    llamacpp_atomic_file_manifest: tuple[Any, ...]
    llamacpp_atomic_repo: str
    llamacpp_atomic_revision: str
    llamacpp_atomic_shards: int
    llamacpp_atomic_total_bytes: int
    llamacpp_atomic_variant: str
    llamacpp_atomic_variant_id: str
    llamacpp_ple_context: int
    llamacpp_ple_memory_ceiling_bytes: int


@dataclass(frozen=True)
class LmstudioCatalogPolicy(_FrozenPolicy):
    lmstudio_assistant_drafter_families: frozenset[str]
    lmstudio_mtp_min_continue_probability_default: float
    lmstudio_mtp_min_tokens_default: Any
    lmstudio_assistant_drafter_minimum_app: str
    lmstudio_assistant_drafter_minimum_llama_pack: str
    lmstudio_assistant_drafter_release_url: str


@dataclass(frozen=True)
class MtplxCatalogPolicy(_FrozenPolicy):
    mtplx_long_context_2111_contract_version: int
    mtplx_long_context_2111_route: Any
    mtplx_long_context_baseline_env: Mapping[str, Any]
    mtplx_long_context_candidate_env: Mapping[str, Any]
    mtplx_long_context_dense_geometry: Mapping[str, Any]
    mtplx_long_context_minimum: int


@dataclass(frozen=True)
class FreetokenCatalogPolicy(_FrozenPolicy):
    freetoken_native_api_version: str
    freetoken_native_inspection_max_response: Any
    freetoken_native_qualification_schema_version: int
    freetoken_native_real_checkpoint_test_kind: Any
    freetoken_native_schema_name: str
    freetoken_native_schema_version: int
    freetoken_native_synthetic_coverage: tuple[Any, ...]
    freetoken_native_synthetic_evidence_id: str


@dataclass(frozen=True)
class UzuCatalogPolicy(_FrozenPolicy):
    session_os_reserve_fraction: float
    session_os_reserve_min_bytes: int
    uzu_model_commit: Any
    uzu_model_file_manifest: tuple[Any, ...]
    uzu_model_file_sha256: Any
    uzu_model_manifest_max_bytes: int
    uzu_model_manifest_max_files: int
    uzu_model_registry_id: str
    uzu_model_registry_max_bytes: int
    uzu_model_registry_max_entries: int
    uzu_model_registry_operational_contract: Mapping[str, Any]
    uzu_model_repository: str
    uzu_model_toolchain_version: Any
    uzu_safe_context_windows: tuple[Any, ...]
    uzu_sandbox_profile_sha256: Any


@dataclass(frozen=True)
class WhallmCatalogPolicy(_FrozenPolicy):
    whallm_context_windows: tuple[Any, ...]
    whallm_model_bytes: int
    whallm_model_id: str
    whallm_support_floor_bytes: int


@dataclass(frozen=True)
class CatalogPolicy(_FrozenPolicy):
    engines: Mapping[str, CatalogDescriptor]
    surfaces: Mapping[str, CatalogDescriptor]
    backend_labels: Mapping[str, str]
    general: GeneralCatalogPolicy
    ssd: SsdCatalogPolicy
    dflash: DflashCatalogPolicy
    ane: AneCatalogPolicy
    atomic: AtomicCatalogPolicy
    lmstudio: LmstudioCatalogPolicy
    mtplx: MtplxCatalogPolicy
    freetoken: FreetokenCatalogPolicy
    uzu: UzuCatalogPolicy
    whallm: WhallmCatalogPolicy


def model_memory_geometry(
    config: dict[str, Any], *, qwen_ple_config: Callable[[dict[str, Any]], bool],
    qsa_allocation_step_tokens: int,
) -> dict[str, Any]:
        """Extract the bounded attention geometry needed for a full-context KV estimate."""
        text = config.get("text_config") if isinstance(config.get("text_config"), dict) else config

        def positive(*keys: str) -> int | None:
            for key in keys:
                value = text.get(key) if isinstance(text, dict) else None
                if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                    return value
            return None

        layers = positive("num_hidden_layers", "n_layer", "num_layers")
        attention_heads = positive("num_attention_heads", "n_head", "attention_heads")
        kv_heads = positive("num_key_value_heads", "n_kv_head", "kv_heads") or attention_heads
        hidden = positive("hidden_size", "n_embd", "d_model")
        head_dim = positive("head_dim")
        if head_dim is None and hidden and attention_heads and hidden % attention_heads == 0:
            head_dim = hidden // attention_heads

        layer_types = text.get("layer_types") if isinstance(text, dict) else None
        if (
            isinstance(layer_types, list) and layers
            and len(layer_types) == layers
            and all(isinstance(item, str) for item in layer_types)
        ):
            full_attention_layers = sum(
                1 for item in layer_types if "linear" not in item.casefold()
            )
            layer_source = "layer-types"
        else:
            interval = positive("full_attention_interval")
            if layers and interval:
                full_attention_layers = max(1, layers // interval)
                layer_source = "full-attention-interval"
            else:
                full_attention_layers = layers
                layer_source = "all-layers-conservative"

        ready = bool(
            layers and full_attention_layers and kv_heads and head_dim
            and 0 < int(full_attention_layers) <= int(layers)
        )
        geometry = {
            "ready": ready,
            "layers": layers,
            "fullAttentionLayers": int(full_attention_layers) if full_attention_layers else None,
            "kvHeads": kv_heads,
            "headDimension": head_dim,
            "layerSource": layer_source,
        }
        if ready and qwen_ple_config(config):
            indexer_head_dim = positive("indexer_head_dim")
            rope = text.get("rope_parameters") if isinstance(text.get("rope_parameters"), dict) else {}
            sections = rope.get("mrope_section") if isinstance(rope, dict) else None
            position_channels = (
                len(sections)
                if isinstance(sections, list) and sections
                and all(isinstance(value, int) and not isinstance(value, bool) and value > 0 for value in sections)
                else 1
            )
            raw_compress_ratio = text.get("indexer_compress_ratio", 4)
            indexer_compress_ratio = (
                int(raw_compress_ratio)
                if isinstance(raw_compress_ratio, int)
                and not isinstance(raw_compress_ratio, bool)
                and 0 < raw_compress_ratio <= qsa_allocation_step_tokens
                and qsa_allocation_step_tokens % raw_compress_ratio == 0
                and (int(indexer_head_dim or 0) * 2) % raw_compress_ratio == 0
                else None
            )
            if indexer_head_dim and indexer_compress_ratio:
                raw_qsa_bytes = int(indexer_head_dim) * 2 + position_channels * 8
                pooled_index_bytes = int(indexer_head_dim) * 2
                pooled_qsa_bytes = pooled_index_bytes // indexer_compress_ratio
                kv_bytes = 2 * int(kv_heads) * int(head_dim) * 2
                geometry.update({
                    "qwen4Qsa": True,
                    "indexerHeadDimension": int(indexer_head_dim),
                    "indexerCompressRatio": indexer_compress_ratio,
                    "positionChannels": position_channels,
                    "qsaAllocationStepTokens": qsa_allocation_step_tokens,
                    "rawIndexBytesPerTokenPerLayer": raw_qsa_bytes,
                    "pooledIndexBytesPerBlockPerLayer": pooled_index_bytes,
                    "pooledIndexBytesPerTokenPerLayer": pooled_qsa_bytes,
                    # Keep the legacy field as the complete per-token QSA
                    # auxiliary allocation so older UI consumers become safer.
                    "fixedIndexBytesPerTokenPerLayer": raw_qsa_bytes + pooled_qsa_bytes,
                    "fullBytesPerToken": int(full_attention_layers) * (
                        kv_bytes + raw_qsa_bytes + pooled_qsa_bytes
                    ),
                })
        return geometry


class ModelCatalog:
    def __init__(self, policy: CatalogPolicy, state: CatalogState, paths: CatalogPaths,
                 values: CatalogValues, runtime: CatalogRuntimes, artifacts: CatalogArtifacts,
                 evidence: CatalogEvidence, surfaces: CatalogSurfaces,
                 connections: CatalogConnections, io: CatalogIO) -> None:
        self.policy, self.state, self.paths, self.values = policy, state, paths, values
        self.runtime, self.artifacts, self.evidence = runtime, artifacts, evidence
        self.surfaces, self.connections, self.io = surfaces, connections, io

    def _native_inspection_source_identity(self, binary: str, model_path: Path) -> tuple[Any, ...] | None:
        """Bind raw probe reuse to current executable/link and metadata inputs.

        Receipt validation is rerun on every use. No model weights are read:
        existing shared identity helpers observe regular targets, named links,
        directory entries and the headers/configuration the inspector consumes.
        """
        executable = runtime_probes.executable_identity(binary)
        if executable is None:
            return None
        try:
            named_root = model_path.expanduser()
            root = named_root.resolve(strict=True)
            named_details, target_details = named_root.lstat(), root.stat()
            if not stat.S_ISDIR(target_details.st_mode):
                return None
            candidates = {
                root / name for name in (
                    "config.json", "generation_config.json", "model.safetensors.index.json",
                    "tokenizer_config.json", "tokenizer.json", "mtplx_runtime.json",
                    "mtp.safetensors", "model-mtp.safetensors", "mtp/weights.safetensors",
                )
            }
            candidates.update(root.glob("*.safetensors"))
            candidates.update(root.glob("*.gguf"))
            candidates.add(self.mtplx_sidecar_path(root, self.io.read_json(root / "config.json")))
            files = tuple((str(path), runtime_probes.executable_identity(str(path)))
                for path in sorted(candidates, key=str))
            return (executable, str(named_root.absolute()),
                runtime_identity.executable_stat_identity(named_details),
                runtime_identity.executable_stat_identity(target_details), files)
        except (OSError, ValueError, RuntimeError):
            return None


    def model_memory_geometry(self, config: dict[str, Any]) -> dict[str, Any]:
        return model_memory_geometry(config, qwen_ple_config=self.values.qwen_ple_config,
            qsa_allocation_step_tokens=self.policy.general.omlx_qwen4_qsa_allocation_step_tokens)


    def _lmstudio_cache_document(self, path: Path) -> tuple[Any, dict[str, Any]]:
        """Read one bounded, stable LM Studio cache file without following a link."""
        try:
            before = path.lstat()
            if (
                path.is_symlink() or not stat.S_ISREG(before.st_mode)
                or not 0 < before.st_size <= self.policy.general.max_json
            ):
                return None, {}
            raw = path.read_bytes()
            after = path.lstat()
            identity = (
                before.st_dev, before.st_ino, before.st_size,
                before.st_mtime_ns, before.st_ctime_ns,
            )
            if identity != (
                after.st_dev, after.st_ino, after.st_size,
                after.st_mtime_ns, after.st_ctime_ns,
            ):
                return None, {}
            value = json.loads(raw)
        except (OSError, ValueError, UnicodeError):
            return None, {}
        return value, {
            "size": int(before.st_size),
            "modifiedNs": int(before.st_mtime_ns),
            "changedNs": int(before.st_ctime_ns),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }


    def lmstudio_assistant_drafter_runtime_contract(self, 
        cli_path: str | None,
        cli_version: str,
        app: dict[str, Any],
        packs: list[dict[str, Any]],
        preference: dict[str, Any],
    ) -> dict[str, Any]:
        """Prove the app, selected llama.cpp pack, and CLI can attach a drafter."""
        app_version = str(app.get("version") or "") if isinstance(app, dict) else ""
        app_ready = bool(
            isinstance(app, dict) and app.get("available") is True
            and app.get("bundleId") == "ai.elementlabs.lmstudio"
            and self.values.semantic_version_key(app_version)
            >= self.values.semantic_version_key(self.policy.lmstudio.lmstudio_assistant_drafter_minimum_app)
        )
        cli_ready = self.runtime.lmstudio_assistant_drafter_load_supported(cli_path)
        selected_pack = next((
            item for item in packs
            if (
                isinstance(item, dict) and preference.get("ready") is True
                and item.get("kind") == "llama.cpp"
                and item.get("engineName") == preference.get("name")
                and item.get("version") == preference.get("version")
            )
        ), None)
        pack_ready = bool(
            isinstance(selected_pack, dict)
            and selected_pack.get("manifestContractVerified") is True
            and isinstance(selected_pack.get("contractFingerprint"), str)
            and re.fullmatch(
                r"[0-9a-f]{64}", str(selected_pack.get("contractFingerprint")),
            ) is not None
            and isinstance(preference.get("sourceFingerprint"), str)
            and re.fullmatch(
                r"[0-9a-f]{64}", str(preference.get("sourceFingerprint")),
            ) is not None
            and self.values.semantic_version_key(str(selected_pack.get("version") or ""))
            >= self.values.semantic_version_key(self.policy.lmstudio.lmstudio_assistant_drafter_minimum_llama_pack)
        )
        ready = bool(app_ready and cli_ready and pack_ready)
        if not app_ready:
            reason = (
                f"LM Studio {self.policy.lmstudio.lmstudio_assistant_drafter_minimum_app}+ is required for "
                "DFlash, DSpark, and MTP assistant drafters."
            )
        elif preference.get("ready") is not True:
            reason = str(preference.get("reason") or "LM Studio has no selected GGUF engine pack.")
        elif selected_pack is None:
            reason = "LM Studio's selected GGUF engine pack is not installed."
        elif not pack_ready:
            reason = (
                f"The selected GGUF pack must be a complete llama.cpp "
                f"{self.policy.lmstudio.lmstudio_assistant_drafter_minimum_llama_pack}+ engine."
            )
        elif not cli_ready:
            reason = "The selected LM Studio CLI does not expose the complete assistant-drafter load contract."
        else:
            reason = "Compatible LM Studio app, selected llama.cpp pack, and CLI flags are installed."
        identity = {
            "schema": 1,
            "cliVersion": str(cli_version or "")[:100],
            "appVersion": app_version,
            "selectedPack": {
                "name": preference.get("name"), "version": preference.get("version"),
                "contractFingerprint": (
                    selected_pack.get("contractFingerprint")
                    if isinstance(selected_pack, dict) else None
                ),
            },
            "preferenceFingerprint": preference.get("sourceFingerprint"),
            "cliContract": cli_ready,
        }
        return {
            "ready": ready,
            "appReady": app_ready,
            "appVersion": app_version or None,
            "minimumAppVersion": self.policy.lmstudio.lmstudio_assistant_drafter_minimum_app,
            "cliReady": cli_ready,
            "packReady": pack_ready,
            "selectedPackName": preference.get("name"),
            "selectedPackVersion": preference.get("version"),
            "minimumPackVersion": self.policy.lmstudio.lmstudio_assistant_drafter_minimum_llama_pack,
            "runtimeFingerprint": hashlib.sha256(json.dumps(
                identity, sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")).hexdigest() if ready else None,
            "releaseUrl": self.policy.lmstudio.lmstudio_assistant_drafter_release_url,
            "reason": reason,
        }


    def _lmstudio_vocabulary_contract(self, value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        token_count = value.get("tokenCount")
        start = value.get("startTokenId")
        maximum_difference = value.get("maxVocabSizeDifference")
        hashes = value.get("prefixHashes")
        if (
            not isinstance(token_count, int) or isinstance(token_count, bool)
            or not 1 <= token_count <= 2_000_000
            or not isinstance(start, int) or isinstance(start, bool)
            or not 0 <= start < token_count
            or not isinstance(maximum_difference, int) or isinstance(maximum_difference, bool)
            or not 0 <= maximum_difference <= 4_096
            or not isinstance(hashes, list) or not 1 <= len(hashes) <= 4_097
        ):
            return None
        expected_start = max(start + 1, token_count - maximum_difference)
        expected_ends = list(range(expected_start, token_count + 1))
        normalized: list[dict[str, Any]] = []
        for item in hashes:
            end = item.get("endTokenIdExclusive") if isinstance(item, dict) else None
            digest = item.get("hash") if isinstance(item, dict) else None
            if (
                not isinstance(end, int) or isinstance(end, bool)
                or not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            ):
                return None
            normalized.append({"endTokenIdExclusive": end, "hash": digest})
        if [item["endTokenIdExclusive"] for item in normalized] != expected_ends:
            return None
        return {
            "tokenCount": token_count,
            "startTokenId": start,
            "maxVocabSizeDifference": maximum_difference,
            "prefixHashes": normalized,
        }


    def _lmstudio_vocabulary_pair(self, 
        target: dict[str, Any], draft: dict[str, Any],
    ) -> dict[str, Any] | None:
        if target["startTokenId"] != draft["startTokenId"]:
            return None
        difference = abs(int(target["tokenCount"]) - int(draft["tokenCount"]))
        if difference > min(
            int(target["maxVocabSizeDifference"]),
            int(draft["maxVocabSizeDifference"]),
        ):
            return None
        common_end = min(int(target["tokenCount"]), int(draft["tokenCount"]))
        target_hashes = {
            int(item["endTokenIdExclusive"]): str(item["hash"])
            for item in target["prefixHashes"]
        }
        draft_hashes = {
            int(item["endTokenIdExclusive"]): str(item["hash"])
            for item in draft["prefixHashes"]
        }
        if target_hashes.get(common_end) != draft_hashes.get(common_end) or common_end not in target_hashes:
            return None
        evidence = {
            "commonPrefixTokens": common_end,
            "targetTokenCount": int(target["tokenCount"]),
            "draftTokenCount": int(draft["tokenCount"]),
            "commonPrefixHash": target_hashes[common_end],
        }
        return {
            **evidence,
            "fingerprint": hashlib.sha256(json.dumps(
                evidence, sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")).hexdigest(),
        }


    def _lmstudio_assistant_family(self, architecture: Any) -> str | None:
        if not isinstance(architecture, str) or not 0 < len(architecture) <= 160:
            return None
        normalized = architecture.casefold().replace("-", "_")
        for family, pattern in (
            ("dspark", r"(?:^|_)dspark(?:_|$)"),
            ("dflash", r"(?:^|_)dflash(?:2)?(?:_|$)"),
            ("mtp", r"(?:^|_)mtp(?:_|$)"),
        ):
            if re.search(pattern, normalized):
                return family
        return None


    def lmstudio_gguf_catalog(self, 
        index_path: Path | None = None, catalog_root: Path | None = None,
    ) -> dict[str, Any]:
        """Return exact registered GGUF artifacts with LM Studio's vocabulary receipts."""
        root = (catalog_root or (Path.home() / ".lmstudio" / "models")).expanduser().absolute()
        try:
            root_details = root.lstat()
            resolved_root = root.resolve(strict=True)
            if root.is_symlink() or not stat.S_ISDIR(root_details.st_mode):
                raise OSError("unsafe catalog root")
        except (OSError, RuntimeError):
            return {"entries": [], "sourceFingerprint": None}
        source = index_path or (
            Path.home() / ".lmstudio" / ".internal" / "model-index-cache.json"
        )
        value, source_identity = self._lmstudio_cache_document(source)
        models = value.get("models") if isinstance(value, dict) else None
        if not isinstance(models, list) or len(models) > 4_096:
            return {"entries": [], "sourceFingerprint": None}
        entries: list[dict[str, Any]] = []
        for item in models:
            if (
                not isinstance(item, dict) or item.get("format") != "gguf"
                or item.get("domain") != "llm"
            ):
                continue
            load_key = item.get("defaultIdentifier")
            indexed_id = item.get("indexedModelIdentifier")
            folder_value = item.get("concreteModelDirAbsolutePath")
            if not all(
                isinstance(candidate, str) and 0 < len(candidate) <= 512
                and "\0" not in candidate and "\n" not in candidate
                for candidate in (load_key, indexed_id, folder_value)
            ):
                continue
            folder = Path(str(folder_value)).expanduser().absolute()
            try:
                folder_details = folder.lstat()
                resolved_folder = folder.resolve(strict=True)
                resolved_folder.relative_to(resolved_root)
                if folder.is_symlink() or not stat.S_ISDIR(folder_details.st_mode):
                    raise OSError("unsafe model directory")
            except (OSError, RuntimeError, ValueError):
                continue
            files = item.get("selfFiles")
            if not isinstance(files, list) or not 1 <= len(files) <= 128:
                continue
            artifact_identities: list[dict[str, Any]] = []
            valid_files = True
            for file_value in files:
                filename = file_value.get("filename") if isinstance(file_value, dict) else None
                absolute = file_value.get("absPath") if isinstance(file_value, dict) else None
                expected_size = file_value.get("sizeBytes") if isinstance(file_value, dict) else None
                if (
                    not isinstance(filename, str) or Path(filename).name != filename
                    or not filename.lower().endswith(".gguf")
                    or not isinstance(absolute, str)
                    or not isinstance(expected_size, int) or isinstance(expected_size, bool)
                    or expected_size <= 1_000_000
                ):
                    valid_files = False
                    break
                artifact = folder / filename
                try:
                    supplied = Path(absolute).expanduser().resolve(strict=True)
                    resolved = artifact.resolve(strict=True)
                    details = artifact.lstat()
                except (OSError, RuntimeError):
                    valid_files = False
                    break
                if (
                    supplied != resolved or artifact.is_symlink()
                    or not stat.S_ISREG(details.st_mode) or details.st_size != expected_size
                ):
                    valid_files = False
                    break
                artifact_identities.append({
                    "name": filename, "path": str(resolved),
                    "device": int(details.st_dev), "inode": int(details.st_ino),
                    "size": int(details.st_size), "modifiedNs": int(details.st_mtime_ns),
                    "changedNs": int(details.st_ctime_ns),
                })
            metadata = item.get("metadata")
            gguf = metadata.get("gguf") if isinstance(metadata, dict) else None
            vocabulary = self._lmstudio_vocabulary_contract(
                gguf.get("draftSpeculationVocab") if isinstance(gguf, dict) else None
            )
            architecture = gguf.get("arch") if isinstance(gguf, dict) else None
            declared_size = item.get("sizeBytes")
            if (
                not valid_files or not artifact_identities or vocabulary is None
                or not isinstance(architecture, str) or not architecture
                or not isinstance(declared_size, int) or isinstance(declared_size, bool)
                or declared_size != sum(entry["size"] for entry in artifact_identities)
                or int(source_identity.get("modifiedNs") or 0)
                < max(entry["changedNs"] for entry in artifact_identities)
            ):
                continue
            identity = {
                "loadKey": load_key, "indexedIdentifier": indexed_id,
                "directory": str(resolved_folder), "architecture": architecture,
                "vocabulary": vocabulary, "artifacts": artifact_identities,
                "catalogFingerprint": source_identity.get("sha256"),
            }
            entries.append({
                **identity,
                "assistantFamily": self._lmstudio_assistant_family(architecture),
                "artifactFingerprint": hashlib.sha256(json.dumps(
                    identity, sort_keys=True, separators=(",", ":"),
                ).encode("utf-8")).hexdigest(),
            })
        return {
            "entries": entries[:512],
            "sourceFingerprint": source_identity.get("sha256"),
        }


    def lmstudio_draft_compatibility_receipts(self, 
        path: Path | None = None,
    ) -> dict[str, Any]:
        """Read LM Studio's explicit target-to-drafter compatibility decisions."""
        source = path or (
            Path.home() / ".lmstudio" / ".internal"
            / "draft-model-compatibility-cache.json"
        )
        value, identity = self._lmstudio_cache_document(source)
        document = value.get("json") if isinstance(value, dict) else None
        raw_map = document.get("map") if isinstance(document, dict) else None
        meta = value.get("meta") if isinstance(value, dict) else None
        meta_values = meta.get("values") if isinstance(meta, dict) else None
        if (
            not isinstance(raw_map, list) or len(raw_map) > 4_096
            or not isinstance(meta_values, dict) or meta_values.get("map") != ["map"]
        ):
            return {"pairs": [], "sourceFingerprint": None, "modifiedNs": 0}
        pairs: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for row in raw_map:
            if not isinstance(row, list) or len(row) != 2:
                continue
            target, engine_values = row
            if not isinstance(target, str) or not 0 < len(target) <= 512:
                continue
            if not isinstance(engine_values, list) or len(engine_values) > 32:
                continue
            for engine in engine_values:
                if not isinstance(engine, dict) or engine.get("engineType") != "llama.cpp":
                    continue
                oldest = engine.get("oldestEngineVersion")
                compatible = engine.get("compatibleDraftModelIdentifiers")
                if (
                    not isinstance(oldest, str)
                    or self.values.semantic_version_key(oldest) == (-1, -1, -1, -1)
                    or not isinstance(compatible, list) or len(compatible) > 512
                ):
                    continue
                for draft in compatible:
                    key = (target, draft) if isinstance(draft, str) else (target, "")
                    if (
                        not isinstance(draft, str) or not 0 < len(draft) <= 512
                        or key in seen
                    ):
                        continue
                    seen.add(key)
                    pairs.append({
                        "target": target, "draft": draft,
                        "oldestEngineVersion": oldest,
                    })
        return {
            "pairs": pairs[:2_048],
            "sourceFingerprint": identity.get("sha256"),
            "modifiedNs": int(identity.get("modifiedNs") or 0),
        }


    def lmstudio_assistant_drafter_readiness(self, 
        target_path: Path,
        catalog: dict[str, Any],
        receipts: dict[str, Any],
        runtime: dict[str, Any],
    ) -> dict[str, Any]:
        """Discover exact assistant pairs without making them selectable or preferred."""
        try:
            resolved_target = str(target_path.resolve(strict=True))
        except (OSError, RuntimeError):
            resolved_target = ""
        entries = catalog.get("entries") if isinstance(catalog, dict) else None
        entries = entries if isinstance(entries, list) else []
        target_matches = [
            item for item in entries
            if isinstance(item, dict) and item.get("directory") == resolved_target
            and item.get("assistantFamily") is None
        ]
        target = target_matches[0] if len(target_matches) == 1 else None
        pair_receipts = receipts.get("pairs") if isinstance(receipts, dict) else None
        pair_receipts = pair_receipts if isinstance(pair_receipts, list) else []
        candidates: list[dict[str, Any]] = []
        if target is not None:
            for receipt in pair_receipts:
                if (
                    not isinstance(receipt, dict)
                    or receipt.get("target") != target.get("indexedIdentifier")
                ):
                    continue
                draft_matches = [
                    item for item in entries
                    if isinstance(item, dict)
                    and item.get("indexedIdentifier") == receipt.get("draft")
                    and item.get("assistantFamily") in self.policy.lmstudio.lmstudio_assistant_drafter_families
                ]
                if len(draft_matches) != 1:
                    continue
                draft = draft_matches[0]
                vocabulary = self._lmstudio_vocabulary_pair(
                    target["vocabulary"], draft["vocabulary"],
                )
                artifact_changed = max(
                    item["changedNs"]
                    for model in (target, draft) for item in model["artifacts"]
                )
                oldest = str(receipt.get("oldestEngineVersion") or "")
                if (
                    vocabulary is None
                    or int(receipts.get("modifiedNs") or 0) < artifact_changed
                    or self.values.semantic_version_key(str(runtime.get("selectedPackVersion") or ""))
                    < self.values.semantic_version_key(oldest)
                ):
                    continue
                identity = {
                    "schema": 1,
                    "targetFingerprint": target["artifactFingerprint"],
                    "draftFingerprint": draft["artifactFingerprint"],
                    "vocabularyFingerprint": vocabulary["fingerprint"],
                    "compatibilityFingerprint": receipts.get("sourceFingerprint"),
                    "oldestEngineVersion": oldest,
                    "runtimeFingerprint": runtime.get("runtimeFingerprint"),
                }
                candidates.append({
                    "family": str(draft["assistantFamily"]),
                    "draftModelKey": str(draft["loadKey"]),
                    "draftIndexedIdentifier": str(draft["indexedIdentifier"]),
                    "draftPath": str(draft["directory"]),
                    "vocabulary": vocabulary,
                    "pairFingerprint": hashlib.sha256(json.dumps(
                        identity, sort_keys=True, separators=(",", ":"),
                    ).encode("utf-8")).hexdigest(),
                    "selectable": False,
                    "benchmarkEligible": False,
                    "automaticEligible": False,
                })
        candidates.sort(key=lambda item: (
            item["family"], item["draftIndexedIdentifier"].casefold(),
        ))
        pair_ready = bool(candidates)
        foundation_ready = bool(pair_ready and runtime.get("ready") is True)
        if target is None:
            reason = "Assistant drafters require one exact LM Studio-registered GGUF target with current vocabulary metadata."
        elif not pair_ready:
            reason = "No current LM Studio compatibility receipt and direct vocabulary hash prove an installed assistant pair."
        elif runtime.get("ready") is not True:
            reason = str(runtime.get("reason") or "LM Studio's assistant-drafter runtime contract is not ready.")
        else:
            reason = (
                "Exact assistant pair discovered. Selection and benchmarking remain disabled until "
                "the launcher can verify LM Studio's applied load receipt after each fresh load."
            )
        return {
            "foundationReady": foundation_ready,
            "pairReady": pair_ready,
            "runtimeReady": runtime.get("ready") is True,
            "targetModelKey": str(target.get("loadKey")) if target is not None else None,
            "targetIndexedIdentifier": (
                str(target.get("indexedIdentifier")) if target is not None else None
            ),
            "targetArtifactFingerprint": (
                str(target.get("artifactFingerprint")) if target is not None else None
            ),
            "selectable": False,
            "benchmarkEligible": False,
            "automaticEligible": False,
            "receiptRequired": True,
            "candidates": candidates[:16],
            "runtime": copy.deepcopy(runtime),
            "reason": reason,
        }


    def model_roots(self) -> list[tuple[str, Path]]:
        roots: list[tuple[str, Path]] = [
            ("LM Studio", Path.home() / ".lmstudio" / "models"),
            ("MTPLX", Path.home() / ".mtplx" / "models"),
            ("oMLX", Path.home() / ".omlx" / "models"),
            ("Documents", Path.home() / "Documents" / "models"),
            ("Documents", Path.home() / "Documents" / "Models"),
            ("Hugging Face", Path.home() / ".cache" / "huggingface" / "hub"),
            ("Mference", Path.home() / "Library" / "Application Support" / "Mference"),
            ("Mference", Path.home() / ".mference" / "models"),
        ]
        omlx_settings = self.io.read_json(Path.home() / ".omlx" / "settings.json")
        configured = self.values.deep_get(omlx_settings, ("model", "model_dirs"))
        if isinstance(configured, list):
            for item in configured:
                if isinstance(item, str) and item.strip():
                    roots.append(("oMLX configured", Path(item).expanduser()))
        unique: list[tuple[str, Path]] = []
        seen: set[str] = set()
        for label, path in roots:
            key = str(path.expanduser().absolute())
            if key not in seen:
                seen.add(key)
                unique.append((label, path.expanduser()))
        return unique


    def _physical_directory_identity(self, path: Path) -> tuple[int, int] | None:
        """Identify one directory independently of aliases and path spelling.

        APFS commonly preserves the spelling supplied to ``realpath`` even when
        two case variants address the same directory.  A resolved-path string is
        therefore not an authoritative dedupe key on the Mac.  The device/inode
        pair is, and using the directory identity (rather than any weight-file
        identity) keeps separate model folders separate even if they hard-link a
        payload.
        """
        try:
            details = path.stat()
        except OSError:
            return None
        if not stat.S_ISDIR(details.st_mode):
            return None
        return int(details.st_dev), int(details.st_ino)


    def _preferred_scan_root_spellings(self, 
        roots: list[tuple[str, Path]],
    ) -> dict[tuple[int, int], Path]:
        """Choose a stable spelling for each physical model-library root.

        Launcher acquisition destinations come first so a model downloaded to
        ``Documents/models`` keeps that configured path and consequently keeps
        its model id and artifact fingerprint.  Other roots retain their existing
        scan order.  Origin labels are intentionally merged later, at candidate
        level, rather than being discarded here.
        """
        preferred: dict[tuple[int, int], Path] = {}
        candidates: list[Path] = []
        for item in self.paths.acquisition_roots():
            value = item.get("path") if isinstance(item, dict) else None
            if isinstance(value, str) and value:
                candidates.append(Path(value).expanduser())
        candidates.extend(path.expanduser() for _label, path in roots)
        for path in candidates:
            identity = self._physical_directory_identity(path)
            if identity is not None:
                preferred.setdefault(identity, path)
        return preferred


    def _preferred_physical_candidate_path(self, 
        candidate: Path,
        scanned_root: Path,
        preferred_root: Path | None,
        identity: tuple[int, int],
    ) -> Path | None:
        """Resolve a candidate through the preferred alias when it is identical."""
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            return None
        if preferred_root is None:
            return resolved
        try:
            relative = candidate.relative_to(scanned_root)
            preferred = (preferred_root / relative).resolve(strict=True)
        except (OSError, ValueError):
            return resolved
        return preferred if self._physical_directory_identity(preferred) == identity else resolved


    def candidate_dirs(self, root: Path, max_depth: int = 4) -> list[Path]:
        found: list[Path] = []
        if not root.exists():
            return found

        def visit(path: Path, depth: int) -> None:
            try:
                entries = list(os.scandir(path))
            except OSError:
                return
            names = {entry.name for entry in entries}
            if (
                path.name.endswith(".gturbo") and "manifest.json" in names
                and "verified-install.json" in names
            ):
                found.append(path)
                return
            has_config = "config.json" in names
            has_gguf = any(name.lower().endswith(".gguf") for name in names)
            if has_config or has_gguf:
                found.append(path)
                return
            if depth >= max_depth:
                return
            for entry in entries:
                if entry.name.startswith(".") or entry.name in {"blobs", "refs"}:
                    continue
                try:
                    if entry.is_dir(follow_symlinks=True):
                        visit(Path(entry.path), depth + 1)
                except OSError:
                    continue

        visit(root, 0)
        return found


    def _bounded_regular_json(self, path: Path) -> tuple[dict[str, Any], bytes, str | None]:
        """Read one bounded metadata object without trusting links or special files."""
        try:
            details = path.lstat()
            if path.is_symlink() or not stat.S_ISREG(details.st_mode):
                return {}, b"", f"{path.name} must be a regular file"
            if not 0 < details.st_size <= self.policy.general.max_json:
                return {}, b"", f"{path.name} exceeds the supported metadata size"
            data = path.read_bytes()
            value = json.loads(data)
        except (OSError, ValueError, UnicodeError):
            return {}, b"", f"{path.name} is not valid JSON"
        if not isinstance(value, dict):
            return {}, b"", f"{path.name} must contain a JSON object"
        return value, data, None


    def mference_bundle_validation(self, path: Path) -> tuple[bool, str, int]:
        """Mirror Mference's cheap receipt checks without hashing multi-GB payloads."""
        if not path.name.endswith(".gturbo"):
            return False, "Mference requires a .gturbo bundle.", 0
        try:
            root = path.resolve(strict=True)
        except OSError:
            return False, "The Mference bundle is missing or unreadable.", 0
        if not root.is_dir():
            return False, "The Mference bundle is not a directory.", 0

        manifest, manifest_data, manifest_error = self._bounded_regular_json(root / "manifest.json")
        receipt, receipt_data, receipt_error = self._bounded_regular_json(root / "verified-install.json")
        if manifest_error or receipt_error:
            return False, manifest_error or receipt_error or "Invalid Mference metadata.", 0
        if manifest.get("magic") != "GTURBO" or manifest.get("versionMajor") != 1:
            return False, "The Mference manifest has an unsupported format.", 0
        flags = manifest.get("flags")
        if not isinstance(flags, dict) or any(key not in self.policy.ssd.mference_known_flags for key in flags):
            return False, "The Mference manifest contains unsupported runtime flags.", 0
        if flags.get("streamingPresent") is not True or flags.get("turboQuantKV") is True:
            return False, "The Mference bundle does not declare a supported SSD-streaming layout.", 0

        arch = manifest.get("arch")
        if not isinstance(arch, dict):
            return False, "The Mference manifest is missing its architecture contract.", 0
        family = arch.get("family") or "gemma4"
        signature = self.policy.ssd.mference_streaming_arch_signatures.get(family) if isinstance(family, str) else None
        if not signature:
            return False, "This .gturbo architecture is not pinned by the installed Mference contract.", 0
        for key in ("hiddenSize", "vocabSize", "numLayers", "numExperts", "topKExperts"):
            value = arch.get(key)
            if isinstance(value, bool) or value != signature[key]:
                return False, f"The .gturbo {family} architecture does not match Mference's pinned {key}.", 0
        if manifest.get("numLayers") != signature["numLayers"]:
            return False, "The Mference manifest layer count conflicts with its architecture.", 0
        if manifest.get("expertsPerLayer") != signature["numExperts"]:
            return False, "The Mference manifest expert count conflicts with its architecture.", 0
        expert_stride = manifest.get("expertStride")
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        if (
            isinstance(expert_stride, bool) or not isinstance(expert_stride, int)
            or expert_stride <= 0 or expert_stride % page_size
        ):
            return False, "The Mference expert stride is not page aligned.", 0
        mask = arch.get("fullAttentionLayerMask")
        if not isinstance(mask, list) or len(mask) != signature["numLayers"]:
            return False, "The Mference attention layout does not match its layer count.", 0
        if not isinstance(manifest.get("quant"), dict) or not manifest["quant"]:
            return False, "The Mference production manifest is missing quantization metadata.", 0

        files = manifest.get("files")
        receipt_files = receipt.get("files")
        if not isinstance(files, dict) or not 3 <= len(files) <= 4_096:
            return False, "The Mference manifest has an invalid payload file set.", 0
        if not isinstance(receipt_files, dict):
            return False, "The Mference receipt has an invalid payload file set.", 0
        manifest_hash = hashlib.sha256(manifest_data).hexdigest()
        if receipt.get("schemaVersion") != 1:
            return False, "The Mference receipt schema is unsupported.", 0
        if not isinstance(receipt.get("modelDirectoryPath"), str) or receipt["modelDirectoryPath"] != str(root):
            return False, "The Mference receipt belongs to a different bundle location.", 0
        if not isinstance(receipt.get("manifestSha256"), str) or not secrets.compare_digest(
            receipt["manifestSha256"].casefold(), manifest_hash,
        ):
            return False, "The Mference receipt does not match manifest.json.", 0
        expected_receipt_files = set(files) | {"manifest.json"}
        if set(receipt_files) != expected_receipt_files:
            return False, "The Mference receipt file set does not match its manifest.", 0
        manifest_receipt = receipt_files.get("manifest.json")
        if not isinstance(manifest_receipt, dict) or manifest_receipt.get("size") != len(manifest_data):
            return False, "The Mference receipt has the wrong manifest size.", 0
        if not isinstance(manifest_receipt.get("sha256"), str) or not secrets.compare_digest(
            manifest_receipt["sha256"].casefold(), manifest_hash,
        ):
            return False, "The Mference receipt has the wrong manifest hash.", 0

        layer_indices: set[int] = set()
        payload_total = 0
        for relative, entry in files.items():
            if (
                not isinstance(relative, str) or not relative or len(relative) > 512
                or relative.startswith(("/", "\\")) or "\\" in relative or "\0" in relative
            ):
                return False, "The Mference manifest contains an unsafe payload path.", 0
            parts = relative.split("/")
            if any(part in {"", ".", ".."} for part in parts):
                return False, "The Mference manifest contains an unsafe payload path.", 0
            if relative in {"manifest.json", "verified-install.json"}:
                return False, "The Mference manifest incorrectly includes its own metadata.", 0
            if not isinstance(entry, dict) or not isinstance(receipt_files.get(relative), dict):
                return False, f"The Mference metadata for {relative} is invalid.", 0
            declared_size = entry.get("size")
            declared_hash = entry.get("sha256")
            receipt_entry = receipt_files[relative]
            if (
                isinstance(declared_size, bool) or not isinstance(declared_size, int) or declared_size < 0
                or not isinstance(declared_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", declared_hash)
                or receipt_entry.get("size") != declared_size
                or not isinstance(receipt_entry.get("sha256"), str)
                or not secrets.compare_digest(receipt_entry["sha256"].casefold(), declared_hash.casefold())
            ):
                return False, f"The Mference receipt does not match {relative}.", 0
            candidate = root.joinpath(*parts)
            try:
                cursor = root
                for part in parts:
                    cursor /= part
                    if cursor.is_symlink():
                        return False, f"The Mference payload {relative} may not use symbolic links.", 0
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(root)
                details = candidate.lstat()
            except (OSError, ValueError):
                return False, f"The Mference payload {relative} is missing or unsafe.", 0
            if not stat.S_ISREG(details.st_mode) or details.st_size != declared_size:
                return False, f"The Mference payload size does not match {relative}.", 0
            payload_total += details.st_size
            match = re.fullmatch(r"packed_experts/layer_(\d+)\.bin", relative)
            if match:
                layer_indices.add(int(match.group(1)))

        for required in ("model_weights.bin", "packed_experts/layout.json"):
            entry = files.get(required)
            if not isinstance(entry, dict) or not isinstance(entry.get("size"), int) or entry["size"] <= 0:
                return False, f"The Mference manifest is missing a usable {required}.", 0
        first_layer = signature["firstExpertLayer"]
        expected_layers = set(range(first_layer, signature["numLayers"]))
        if layer_indices != expected_layers:
            return False, "The Mference bundle is missing one or more pinned expert-layer payloads.", 0
        for index in expected_layers:
            entry = files.get(f"packed_experts/layer_{index:02d}.bin") or files.get(
                f"packed_experts/layer_{index}.bin"
            )
            if not isinstance(entry, dict) or not isinstance(entry.get("size"), int) or entry["size"] <= 0:
                return False, "The Mference bundle contains an empty expert-layer payload.", 0

        total = payload_total + len(manifest_data) + len(receipt_data)
        return True, f"Verified Mference {family} receipt and SSD-streaming payload layout.", total


    def _llamacpp_atomic_base(self) -> dict[str, Any]:
        return {
            "ready": False,
            "repoId": self.policy.atomic.llamacpp_atomic_repo,
            "pinnedRevision": self.policy.atomic.llamacpp_atomic_revision,
            "variantId": self.policy.atomic.llamacpp_atomic_variant_id,
            "variant": self.policy.atomic.llamacpp_atomic_variant,
            "shardCount": self.policy.atomic.llamacpp_atomic_shards,
            "weightBytes": self.policy.atomic.llamacpp_atomic_total_bytes,
            "context": self.policy.atomic.llamacpp_ple_context,
            "firstShard": None,
            "receiptFingerprint": None,
            "verificationState": "unverified",
            "currentProcessVerified": False,
            "verifiedShards": 0,
            "totalShards": self.policy.atomic.llamacpp_atomic_shards,
            "presentationSnapshot": False,
        }


    def _atomic_file_identity(self, path: Path, expected_checksum: str) -> dict[str, Any] | None:
        """Describe one current shard without treating metadata as a hash proof."""
        try:
            requested = path.expanduser()
            details = requested.lstat()
            resolved = requested.resolve(strict=True)
        except OSError:
            return None
        if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode):
            return None
        birthtime = getattr(details, "st_birthtime", 0.0)
        return {
            "path": str(requested),
            "resolvedPath": str(resolved),
            "device": int(details.st_dev),
            "inode": int(details.st_ino),
            "mode": int(details.st_mode),
            "size": int(details.st_size),
            "mtimeNs": int(details.st_mtime_ns),
            "ctimeNs": int(details.st_ctime_ns),
            "birthtimeNs": int(float(birthtime) * 1_000_000_000),
            "expectedSha256": str(expected_checksum).casefold(),
        }


    def _llamacpp_atomic_structural_contract(self, path: Path) -> dict[str, Any]:
        """Validate receipt, exact file set, and identities without hashing payloads."""
        base = self._llamacpp_atomic_base()
        try:
            root = path.expanduser().resolve(strict=True)
        except OSError:
            return {**base, "reason": "The AtomicChat GGUF folder is missing or unreadable."}
        if not root.is_dir() or root.name != self.policy.atomic.llamacpp_atomic_variant:
            return {**base, "reason": "This is not the exact allowlisted AtomicChat AD-3.84 folder."}
        marker_path = root.parent / self.policy.general.model_acquisition_marker
        marker, marker_data, marker_error = self._bounded_regular_json(marker_path)
        if marker_error:
            return {
                **base,
                "reason": "The exact AtomicChat route requires its verified launcher acquisition receipt.",
            }
        verification = marker.get("verification") if isinstance(marker.get("verification"), dict) else {}
        if (
            marker.get("schemaVersion") != self.policy.general.model_acquisition_schema_version
            or marker.get("repoId") != self.policy.atomic.llamacpp_atomic_repo
            or marker.get("pinnedRevision") != self.policy.atomic.llamacpp_atomic_revision
            or marker.get("variantId") != self.policy.atomic.llamacpp_atomic_variant_id
            or marker.get("format") != "gguf"
            or marker.get("status") != "verified"
            or verification.get("verified") is not True
            or verification.get("format") != "gguf"
            or verification.get("checkedFiles") != self.policy.atomic.llamacpp_atomic_shards
            or verification.get("weightBytes") != self.policy.atomic.llamacpp_atomic_total_bytes
        ):
            return {**base, "reason": "The AtomicChat acquisition receipt is stale or does not match the pinned route."}
        declared = marker.get("files") if isinstance(marker.get("files"), list) else []
        if len(declared) != self.policy.atomic.llamacpp_atomic_shards:
            return {**base, "reason": "The AtomicChat receipt must cover all 28 GGUF shards and nothing else."}
        by_path: dict[str, dict[str, Any]] = {}
        for item in declared:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                return {**base, "reason": "The AtomicChat receipt contains an invalid shard record."}
            relative = item["path"]
            if relative in by_path:
                return {**base, "reason": "The AtomicChat receipt contains a duplicate shard record."}
            by_path[relative] = item

        normalized: list[dict[str, Any]] = []
        file_identities: list[dict[str, Any]] = []
        actual_names: set[str] = set()
        for index, (relative, expected_size, expected_checksum) in enumerate(
            self.policy.atomic.llamacpp_atomic_file_manifest, 1,
        ):
            item = by_path.get(relative)
            size = item.get("size") if isinstance(item, dict) else None
            checksum = str(item.get("sha256") or "") if isinstance(item, dict) else ""
            if size != expected_size or checksum != expected_checksum:
                return {
                    **base,
                    "reason": (
                        f"The acquisition receipt for shard {index} does not match the "
                        "launcher's immutable pinned source manifest."
                    ),
                }
            candidate = root / Path(relative).name
            try:
                details = candidate.lstat()
                candidate.resolve(strict=True).relative_to(root)
                with open(candidate, "rb") as handle:
                    magic = handle.read(4)
            except (OSError, ValueError):
                return {**base, "reason": f"AtomicChat shard {index} is missing or unsafe."}
            if (
                candidate.is_symlink() or not stat.S_ISREG(details.st_mode)
                or details.st_size != expected_size or magic != b"GGUF"
            ):
                return {**base, "reason": f"AtomicChat shard {index} changed after verification."}
            file_identity = self._atomic_file_identity(candidate, expected_checksum)
            if file_identity is None:
                return {**base, "reason": f"AtomicChat shard {index} is missing or unsafe."}
            actual_names.add(candidate.name)
            file_identities.append(file_identity)
            normalized.append({
                "path": relative, "size": expected_size, "sha256": expected_checksum,
            })
        try:
            gguf_names = {item.name for item in root.iterdir() if item.is_file() and item.suffix.lower() == ".gguf"}
        except OSError:
            return {**base, "reason": "The AtomicChat GGUF folder became unreadable."}
        if gguf_names != actual_names or sum(int(item["size"]) for item in normalized) != self.policy.atomic.llamacpp_atomic_total_bytes:
            return {**base, "reason": "The AtomicChat folder does not contain the exact pinned 28-shard set."}
        identity = {
            "schemaVersion": self.policy.general.model_acquisition_schema_version,
            "repoId": self.policy.atomic.llamacpp_atomic_repo,
            "pinnedRevision": self.policy.atomic.llamacpp_atomic_revision,
            "variantId": self.policy.atomic.llamacpp_atomic_variant_id,
            "files": normalized,
        }
        fingerprint = hashlib.sha256(json.dumps(
            identity, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        marker_identity = self._atomic_file_identity(
            marker_path, hashlib.sha256(marker_data).hexdigest(),
        )
        if marker_identity is None:
            return {**base, "reason": "The AtomicChat acquisition receipt became unsafe."}
        presentation = {
            "schemaVersion": self.policy.atomic.atomic_presentation_snapshot_schema_version,
            "kind": "atomicchat-llamacpp-presentation",
            "modelPath": str(root),
            "manifestFingerprint": fingerprint,
            "receiptFingerprint": fingerprint,
            "marker": marker_identity,
            "files": file_identities,
        }
        identity_key = hashlib.sha256(json.dumps(
            presentation, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        return {
            **base,
            "reason": "Exact pinned AtomicChat receipt and 28-shard structure found; SHA-256 verification is required in this controller process.",
            "firstShard": str(root / Path(self.artifacts.atomic_shard_relative(1)).name),
            "receiptFingerprint": fingerprint,
            "files": normalized,
            "_structurallyReady": True,
            "_root": str(root),
            "_identityKey": identity_key,
            "_presentation": presentation,
        }


    def _atomic_public_contract(self, contract: dict[str, Any]) -> dict[str, Any]:
        return {
            key: copy.deepcopy(value)
            for key, value in contract.items()
            if not str(key).startswith("_")
        }


    def _register_atomic_current_process_proof(self, 
        structural: dict[str, Any], contract: dict[str, Any],
    ) -> int:
        path = str(structural.get("_root") or "")
        identity_key = str(structural.get("_identityKey") or "")
        if not path or not identity_key:
            return 0
        with self.state.atomic_lock:
            self.state.atomic_verification_generation += 1
            generation = self.state.atomic_verification_generation
            self.state.atomic_current_process_proofs[path] = {
                "identityKey": identity_key,
                "generation": generation,
                "contract": self._atomic_public_contract(contract),
            }
        return generation


    def _atomic_current_process_contract(self, 
        structural: dict[str, Any],
    ) -> dict[str, Any] | None:
        path = str(structural.get("_root") or "")
        identity_key = str(structural.get("_identityKey") or "")
        with self.state.atomic_lock:
            proof = copy.deepcopy(self.state.atomic_current_process_proofs.get(path))
            if proof and proof.get("identityKey") != identity_key:
                self.state.atomic_current_process_proofs.pop(path, None)
                proof = None
        if not isinstance(proof, dict):
            return None
        contract = proof.get("contract")
        if not isinstance(contract, dict) or contract.get("ready") is not True:
            return None
        return {
            **self._atomic_public_contract(structural),
            **copy.deepcopy(contract),
            "ready": True,
            "verificationState": "verified",
            "currentProcessVerified": True,
            "verificationGeneration": int(proof.get("generation") or 0),
            "verifiedShards": self.policy.atomic.llamacpp_atomic_shards,
            "totalShards": self.policy.atomic.llamacpp_atomic_shards,
        }


    def llamacpp_atomic_artifact_contract(self, 
        path: Path, *, progress: Any = None,
    ) -> dict[str, Any]:
        """Hash and bind the exact 28-shard quant in the current process."""
        structural = self._llamacpp_atomic_structural_contract(path)
        if structural.get("_structurallyReady") is not True:
            return self._atomic_public_contract(structural)
        current = self._atomic_current_process_contract(structural)
        if current is not None:
            return current
        initial_identity = str(structural["_identityKey"])
        root = Path(str(structural["_root"]))
        for index, (relative, _expected_size, expected_checksum) in enumerate(
            self.policy.atomic.llamacpp_atomic_file_manifest, 1,
        ):
            candidate = root / Path(relative).name
            if not self.artifacts.cached_regular_file_sha256_matches(candidate, expected_checksum):
                return {
                    **self._atomic_public_contract(structural),
                    "reason": f"AtomicChat shard {index} no longer matches its verified SHA-256 checksum.",
                    "verificationState": "failed",
                    "verifiedShards": index - 1,
                }
            if callable(progress):
                try:
                    progress(index, self.policy.atomic.llamacpp_atomic_shards)
                except Exception:
                    pass
        final = self._llamacpp_atomic_structural_contract(root)
        if (
            final.get("_structurallyReady") is not True
            or final.get("_identityKey") != initial_identity
        ):
            return {
                **self._atomic_public_contract(final),
                "ready": False,
                "reason": "The AtomicChat GGUF or receipt changed during SHA-256 verification.",
                "verificationState": "failed",
            }
        verified = {
            **self._atomic_public_contract(final),
            "ready": True,
            "reason": "Exact pinned AtomicChat 28-shard receipt verified for SSD-only PLE mmap in this controller process.",
            "verificationState": "verified",
            "currentProcessVerified": True,
            "verifiedShards": self.policy.atomic.llamacpp_atomic_shards,
            "totalShards": self.policy.atomic.llamacpp_atomic_shards,
        }
        generation = self._register_atomic_current_process_proof(final, verified)
        verified["verificationGeneration"] = generation
        with self.state.atomic_lock:
            proof = self.state.atomic_current_process_proofs.get(str(final["_root"]))
            if isinstance(proof, dict):
                proof["contract"] = copy.deepcopy(verified)
        return verified


    def atomic_presentation_snapshot_path(self) -> Path:
        """Resolve lazily so tests and portable state directories remain isolated."""
        return self.paths.state_directory() / "verification" / "atomicchat-llamacpp-presentation.json"


    def _strict_atomic_snapshot_payload(self, value: Any) -> bool:
        if not isinstance(value, dict) or set(value) != {
            "schemaVersion", "kind", "modelPath", "manifestFingerprint",
            "receiptFingerprint", "marker", "files",
        }:
            return False
        if type(value.get("schemaVersion")) is not int:
            return False
        if any(type(value.get(key)) is not str for key in (
            "kind", "modelPath", "manifestFingerprint", "receiptFingerprint",
        )):
            return False
        identity_keys = {
            "path", "resolvedPath", "device", "inode", "mode", "size",
            "mtimeNs", "ctimeNs", "birthtimeNs", "expectedSha256",
        }

        def valid_identity(item: Any) -> bool:
            return bool(
                isinstance(item, dict)
                and set(item) == identity_keys
                and type(item.get("path")) is str
                and type(item.get("resolvedPath")) is str
                and type(item.get("expectedSha256")) is str
                and re.fullmatch(r"[0-9a-f]{64}", item["expectedSha256"]) is not None
                and all(type(item.get(key)) is int for key in (
                    "device", "inode", "mode", "size", "mtimeNs", "ctimeNs", "birthtimeNs",
                ))
            )

        files = value.get("files")
        return bool(
            valid_identity(value.get("marker"))
            and isinstance(files, list)
            and len(files) == self.policy.atomic.llamacpp_atomic_shards
            and all(valid_identity(item) for item in files)
        )


    def _load_atomic_presentation_snapshot(self, 
        structural: dict[str, Any],
    ) -> bool:
        expected = structural.get("_presentation")
        if not self._strict_atomic_snapshot_payload(expected):
            return False
        path = self.atomic_presentation_snapshot_path()
        try:
            directory = path.parent.lstat()
            details = path.lstat()
            if (
                path.parent.is_symlink() or not stat.S_ISDIR(directory.st_mode)
                or directory.st_uid != os.geteuid() or directory.st_mode & 0o077
                or path.is_symlink() or not stat.S_ISREG(details.st_mode)
                or details.st_uid != os.geteuid() or details.st_mode & 0o077
                or not 0 < details.st_size <= self.policy.atomic.atomic_presentation_snapshot_max_bytes
            ):
                return False
            raw = path.read_bytes()
            value = json.loads(raw)
        except (OSError, ValueError, UnicodeError):
            return False
        return self._strict_atomic_snapshot_payload(value) and value == expected


    def _write_atomic_presentation_snapshot(self, structural: dict[str, Any]) -> bool:
        payload = structural.get("_presentation")
        if not self._strict_atomic_snapshot_payload(payload):
            return False
        path = self.atomic_presentation_snapshot_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            directory = path.parent.lstat()
            if (
                path.parent.is_symlink() or not stat.S_ISDIR(directory.st_mode)
                or directory.st_uid != os.geteuid()
            ):
                return False
            os.chmod(path.parent, 0o700)
            self.io.atomic_json(path, payload, mode=0o600)
            return True
        except OSError:
            return False


    def _atomic_verification_status(self, path: str) -> dict[str, Any]:
        with self.state.atomic_lock:
            state = copy.deepcopy(self.state.atomic_verification_states.get(path) or {})
        return state


    def _start_atomic_background_verification(self, 
        structural: dict[str, Any],
    ) -> dict[str, Any]:
        path = str(structural.get("_root") or "")
        identity_key = str(structural.get("_identityKey") or "")
        if not path or not identity_key:
            return {}
        with self.state.atomic_lock:
            thread = self.state.atomic_verification_threads.get(path)
            state = self.state.atomic_verification_states.get(path)
            if thread is not None and thread.is_alive():
                return copy.deepcopy(state or {})
            if isinstance(state, dict) and state.get("identityKey") == identity_key:
                if state.get("phase") in {"verified", "failed"} and state.get("retryable") is not True:
                    return copy.deepcopy(state)
            job_id = self.io.token_hex(12)
            state = {
                "phase": "checking",
                "identityKey": identity_key,
                "jobId": job_id,
                "verifiedShards": 0,
                "totalShards": self.policy.atomic.llamacpp_atomic_shards,
                "reason": "Checking the exact pinned shards in the background.",
            }
            self.state.atomic_verification_states[path] = state

            def worker() -> None:
                def report(completed: int, total: int) -> None:
                    with self.state.atomic_lock:
                        current = self.state.atomic_verification_states.get(path)
                        if not isinstance(current, dict) or current.get("jobId") != job_id:
                            return
                        current["verifiedShards"] = max(0, min(int(completed), self.policy.atomic.llamacpp_atomic_shards))
                        current["totalShards"] = self.policy.atomic.llamacpp_atomic_shards

                try:
                    result = self.llamacpp_atomic_artifact_contract(Path(path), progress=report)
                    final_structural = self._llamacpp_atomic_structural_contract(Path(path))
                    proof = self._atomic_current_process_contract(final_structural)
                    succeeded = bool(
                        result.get("ready") is True
                        and proof is not None
                        and final_structural.get("_identityKey") == identity_key
                    )
                    snapshot_saved = (
                        self._write_atomic_presentation_snapshot(final_structural)
                        if succeeded else False
                    )
                except Exception as error:
                    result = {
                        "ready": False,
                        "reason": f"Background SHA-256 verification failed safely: {error}",
                    }
                    succeeded = False
                    snapshot_saved = False
                with self.state.atomic_lock:
                    current = self.state.atomic_verification_states.get(path)
                    if not isinstance(current, dict) or current.get("jobId") != job_id:
                        return
                    current.update({
                        "phase": "verified" if succeeded else "failed",
                        "verifiedShards": self.policy.atomic.llamacpp_atomic_shards if succeeded else int(
                            result.get("verifiedShards") or current.get("verifiedShards") or 0
                        ),
                        "totalShards": self.policy.atomic.llamacpp_atomic_shards,
                        "snapshotSaved": snapshot_saved,
                        "reason": (
                            "Current-process SHA-256 verification completed."
                            if succeeded else str(result.get("reason") or "SHA-256 verification failed.")
                        ),
                    })

            try:
                thread = threading.Thread(
                    target=worker, name="llm-launcher-atomic-verifier", daemon=True,
                )
                self.state.atomic_verification_threads[path] = thread
                thread.start()
            except Exception as error:
                current = self.state.atomic_verification_states.get(path)
                if isinstance(current, dict) and current.get("jobId") == job_id:
                    if self.state.atomic_verification_threads.get(path) is thread:
                        self.state.atomic_verification_threads.pop(path, None)
                    current.update({
                        "phase": "failed", "retryable": True,
                        "verifiedShards": 0, "snapshotSaved": False,
                        "reason": "Background SHA-256 verifier could not start; rescan to retry: " + str(error)[:400],
                    })
                return copy.deepcopy(self.state.atomic_verification_states.get(path) or {})
            return copy.deepcopy(state)


    def llamacpp_atomic_scan_contract(self, path: Path) -> dict[str, Any]:
        """Start current-process verification without blocking catalog discovery."""
        structural = self._llamacpp_atomic_structural_contract(path)
        if structural.get("_structurallyReady") is not True:
            return self._atomic_public_contract(structural)
        current = self._atomic_current_process_contract(structural)
        if current is not None:
            return current
        snapshot = self._load_atomic_presentation_snapshot(structural)
        state = self._start_atomic_background_verification(structural)
        current = self._atomic_current_process_contract(structural)
        if current is not None:
            return current
        phase = str(state.get("phase") or "checking")
        completed = max(0, min(
            int(state.get("verifiedShards") or 0), self.policy.atomic.llamacpp_atomic_shards,
        ))
        if phase == "failed":
            reason = str(state.get("reason") or "Background SHA-256 verification failed.")
        else:
            phase = "checking"
            reason = f"Verifying exact pinned shards in this controller process ({completed}/{self.policy.atomic.llamacpp_atomic_shards})."
        return {
            **self._atomic_public_contract(structural),
            "ready": False,
            "reason": reason,
            "verificationState": phase,
            "currentProcessVerified": False,
            "verifiedShards": completed,
            "totalShards": self.policy.atomic.llamacpp_atomic_shards,
            "presentationSnapshot": snapshot,
        }


    def weight_completeness(self, 
        path: Path, config: dict[str, Any], *, ignore_acquisition_marker: bool = False,
    ) -> tuple[bool, str, int]:
        if path.name.endswith(".gturbo"):
            ready, reason, total = self.mference_bundle_validation(path)
            return ready, "Ready" if ready else reason, total
        try:
            files = [p for p in path.iterdir() if p.is_file()]
        except OSError:
            return False, "Unreadable", 0
        partial = [p for p in files if p.name.endswith((".part", ".partial", ".download", ".incomplete"))]
        total = sum(p.stat().st_size for p in files if p.suffix in {".safetensors", ".gguf", ".part"})
        if partial:
            return False, f"Downloading ({len(partial)} partial file{'s' if len(partial) != 1 else ''})", total
        marker_path = path / self.policy.general.model_acquisition_marker
        if marker_path.is_file() and not ignore_acquisition_marker:
            marker = self.io.read_json(marker_path)
            marker_status = str(marker.get("status") or "").casefold()
            verification = marker.get("verification") if isinstance(marker.get("verification"), dict) else {}
            if marker_status != "verified" or verification.get("verified") is not True:
                label = {
                    "downloading": "Downloading",
                    "verifying": "Verifying",
                    "partial": "Partial download",
                    "failed": "Download failed",
                }.get(marker_status, "Unverified acquisition")
                return False, label, total
            declared = marker.get("files") if isinstance(marker.get("files"), list) else []
            if not declared:
                return False, "Invalid acquisition receipt", total
            for item in declared:
                relative = item.get("path") if isinstance(item, dict) else None
                expected_size = item.get("size") if isinstance(item, dict) else None
                if (
                    not isinstance(relative, str)
                    or not isinstance(expected_size, int) or isinstance(expected_size, bool) or expected_size < 0
                ):
                    return False, "Invalid acquisition receipt", total
                parts = Path(relative).parts
                if Path(relative).is_absolute() or not parts or any(part in {"", ".", ".."} for part in parts):
                    return False, "Invalid acquisition receipt", total
                candidate = path / relative
                try:
                    candidate.resolve(strict=True).relative_to(path.resolve(strict=True))
                    stat_result = candidate.stat()
                except (OSError, ValueError):
                    return False, "Verified acquisition file missing", total
                if candidate.is_symlink() or not candidate.is_file() or stat_result.st_size != expected_size:
                    return False, "Verified acquisition file changed", total
        ggufs = [p for p in files if p.suffix.lower() == ".gguf" and p.stat().st_size > 1_000_000]
        if ggufs:
            return True, "Ready", sum(p.stat().st_size for p in ggufs)
        index = self.io.read_json(path / "model.safetensors.index.json")
        weight_map = index.get("weight_map")
        if isinstance(weight_map, dict) and weight_map:
            required = {str(v) for v in weight_map.values() if isinstance(v, str)}
            missing = [name for name in required if not (path / name).is_file() or (path / name).stat().st_size == 0]
            if missing:
                return False, f"Incomplete ({len(missing)} weight shard{'s' if len(missing) != 1 else ''} missing)", total
            return True, "Ready", total
        weights = [p for p in files if p.suffix == ".safetensors" and p.name != "mtp.safetensors" and p.stat().st_size > 0]
        numbered: dict[int, int] = {}
        denominators: set[int] = set()
        for weight in weights:
            match = re.fullmatch(r"model-(\d{5})-of-(\d{5})\.safetensors", weight.name)
            if not match:
                continue
            index_number, denominator = int(match.group(1)), int(match.group(2))
            numbered[index_number] = denominator
            denominators.add(denominator)
        if numbered:
            if len(denominators) != 1:
                return False, "Incomplete (inconsistent weight shard count)", total
            expected = next(iter(denominators))
            missing_count = len(set(range(1, expected + 1)) - set(numbered))
            if missing_count:
                return False, f"Incomplete ({missing_count} weight shards missing)", total
            return False, "Incomplete (safetensors index missing)", total
        if weights:
            return True, "Ready", sum(p.stat().st_size for p in weights)
        return False, "Incomplete (no model weights)", total


    def _positive_config_integer(self, config: dict[str, Any], *keys: str) -> int | None:
        text = config.get("text_config") if isinstance(config.get("text_config"), dict) else config
        for source in (text, config):
            if not isinstance(source, dict):
                continue
            for key in keys:
                value = source.get(key)
                if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                    return value
        return None


    def _ssd_source_contract(self, path: Path, config: dict[str, Any]) -> dict[str, Any]:
        """Find a format-independent source receipt without guessing from a display name."""
        documents = [config]
        if path.name.endswith(".gturbo"):
            documents.extend([
                self.io.read_json(path / "manifest.json"),
                self.io.read_json(path / "verified-install.json"),
            ])
        candidates: list[tuple[str, str]] = []

        def visit(value: Any, prefix: str = "") -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    child_prefix = f"{prefix}.{key}" if prefix else str(key)
                    visit(child, child_prefix)
            elif isinstance(value, list):
                for index, child in enumerate(value[:2_048]):
                    visit(child, f"{prefix}[{index}]")
            elif isinstance(value, str) and 0 < len(value) <= 1_024:
                candidates.append((prefix.casefold(), value.strip()))

        for document in documents:
            visit(document)
        source_ids = [
            value for key, value in candidates
            if (
                key.endswith(("source_model", "source_model_id", "source_repo", "source_repository", "_name_or_path"))
                or ("source" in key and key.endswith(("model", "model_id", "repo", "repository")))
                or key.endswith("sourcerepoid")
            )
            and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.@-]+", value)
        ]
        revisions = [
            value.casefold() for key, value in candidates
            if "source" in key and any(marker in key for marker in ("revision", "commit"))
            and re.fullmatch(r"[0-9a-fA-F]{40}", value)
        ]
        index_digests = [
            value.casefold() for key, value in candidates
            if "source" in key and "index" in key and any(marker in key for marker in ("sha", "digest", "hash"))
            and re.fullmatch(r"[0-9a-fA-F]{64}", value)
        ]
        source_id = source_ids[0].casefold() if source_ids else None
        proof_kind = "revision" if revisions else "source-index" if index_digests else None
        proof = revisions[0] if revisions else index_digests[0] if index_digests else None
        comparison_identity = None
        if source_id and proof_kind and proof:
            comparison_identity = hashlib.sha256(
                f"ssd-source-v1\0{source_id}\0{proof_kind}\0{proof}".encode("utf-8")
            ).hexdigest()
        return {
            "sourceModel": source_id,
            "proofKind": proof_kind,
            "proof": proof,
            "comparisonIdentity": comparison_identity,
            "verifiedForCrossFormatComparison": comparison_identity is not None,
        }


    def ssd_streaming_model_profile(self, 
        path: Path, config: dict[str, Any], weight_bytes: int, installed_memory: int,
    ) -> dict[str, Any]:
        """Describe oversized-MoE eligibility without claiming unsupported runtime support."""
        identity = " ".join(filter(None, (
            path.name,
            str(config.get("model_type") or ""),
            str(self.values.deep_get(config, ("text_config", "model_type")) or ""),
            " ".join(str(item) for item in (config.get("architectures") or []) if isinstance(item, str)),
        ))).casefold()
        expert_count = self._positive_config_integer(
            config, "num_experts", "num_local_experts", "n_routed_experts", "moe_num_experts",
        )
        native_top_k = self._positive_config_integer(
            config, "num_experts_per_tok", "num_experts_per_token", "num_selected_experts", "moe_top_k",
        )
        bundle = path.name.endswith(".gturbo")
        moe = bool(expert_count and expert_count > 1) or bundle or any(
            marker in identity for marker in ("moe", "a3b", "a4b", "a10b", "a12b", "flash-next")
        )
        qwen38_flash = bool(
            ("qwen3.8" in identity or "qwen3_8" in identity)
            and ("flash" in identity or "next" in identity)
        )
        ratio = (
            float(weight_bytes) / float(installed_memory)
            if weight_bytes > 0 and installed_memory > 0 else None
        )
        oversized = bool(ratio is not None and ratio >= self.policy.ssd.ssd_streaming_min_weight_ratio)
        # Qwen4-Exp keeps only its indexed PLE N-gram tensors on SSD. That is a
        # separate, exact mmap contract and must never enter the generic expert-
        # streaming lane used by SwiftLM/Mference.
        ple_architecture = self.values.qwen_ple_config(config)
        candidate = bool(moe and weight_bytes > 0 and not ple_architecture)
        recommended = bool(candidate and oversized)
        if ple_architecture:
            reason = "Qwen4 PLE mmap is checked separately from SSD expert streaming."
        elif not moe:
            reason = "SSD expert streaming is reserved for Mixture-of-Experts checkpoints."
        elif not weight_bytes:
            reason = "Finish the model download before SSD-streaming admission can be checked."
        elif oversized:
            reason = "The checkpoint is an MoE whose weights exceed the launcher's safe in-memory threshold."
        else:
            reason = "This MoE currently fits below the safe in-memory threshold; SSD streaming remains optional."
        source_contract = self._ssd_source_contract(path, config)
        return {
            "version": self.policy.ssd.ssd_streaming_contract_version,
            "candidate": candidate,
            "recommended": recommended,
            "moe": moe,
            "oversized": oversized,
            "qwen38FlashNext": qwen38_flash,
            "qwen4PleExcluded": ple_architecture,
            "expertCount": expert_count,
            "nativeExpertTopK": native_top_k,
            "weightBytes": weight_bytes,
            "installedMemoryBytes": installed_memory,
            "weightToMemoryRatio": round(ratio, 4) if ratio is not None else None,
            "format": "gturbo" if bundle else "mlx",
            "reason": reason,
            "sourceContract": source_contract,
            "comparisonIdentity": source_contract["comparisonIdentity"],
            "crossFormatComparisonReady": source_contract["verifiedForCrossFormatComparison"],
            "calibration": {
                "suite": "agentic",
                # Whallm owns a separately downloaded pinned checkpoint. It cannot
                # consume or be paired with these source-folder artifacts.
                "engines": list(self.policy.ssd.ssd_artifact_backends),
                "freshProcessPerEngine": True,
                "coldAndWarmStages": True,
                "nativeExpertRoutingRequired": True,
                "metrics": ["generationTps", "ttft", "peakMemory", "thermalState", "prefixReuse"],
            },
        }


    def ssd_profile_candidate_backends(self, profile: Any) -> tuple[str, ...]:
        """Return only the runtimes that can consume this exact SSD artifact."""
        calibration = profile.get("calibration") if isinstance(profile, dict) else None
        declared = calibration.get("engines") if isinstance(calibration, dict) else None
        result = tuple(
            engine for engine in declared or ()
            if isinstance(engine, str) and engine in self.policy.ssd.ssd_streaming_backends
        )
        return result or self.policy.ssd.ssd_artifact_backends


    def swiftlm_model_supported(self, path: Path, config: dict[str, Any], profile: dict[str, Any]) -> tuple[bool, str]:
        identity = " ".join((
            path.name,
            str(config.get("model_type") or ""),
            str(self.values.deep_get(config, ("text_config", "model_type")) or ""),
        )).casefold()
        if profile.get("qwen38FlashNext"):
            return False, "Qwen3.8 Flash-Next is not yet listed in SwiftLM's accepted model families."
        supported = any(marker in identity for marker in (
            "qwen3.5", "qwen3_5", "qwen3.6", "qwen3_6", "qwen3-next", "qwen3_next", "qwen3next",
            "gemma-4", "gemma4",
            "deepseek_v3", "deepseek-v3", "deepseek_v4", "deepseek-v5",
        ))
        return (
            (True, "SwiftLM supports this MLX MoE family with native SSD expert streaming.")
            if supported else
            (False, "SwiftLM has not listed this exact MoE architecture as supported.")
        )


    def mference_model_supported(self, path: Path, profile: dict[str, Any]) -> tuple[bool, str]:
        if profile.get("qwen38FlashNext"):
            return False, "Qwen3.8 Flash-Next has not passed Mference's pinned-family acceptance gate."
        if path.name.endswith(".gturbo"):
            ready, reason, _ = self.mference_bundle_validation(path)
            return ready, reason
        return False, "Mference requires its verified pinned .gturbo repack of this model."


    def dflash2_draft_shape(self, config: dict[str, Any]) -> dict[str, Any] | None:
        """Return the verified structural contract of an official-style DFlash 2 draft."""
        architectures = config.get("architectures")
        dflash = config.get("dflash_config")
        if not isinstance(architectures, list) or "DFlash2DraftModel" not in architectures or not isinstance(dflash, dict):
            return None
        integer_fields = {
            key: config.get(key)
            for key in (
                "hidden_size", "intermediate_size", "vocab_size", "num_hidden_layers",
                "num_target_layers", "num_attention_heads", "num_key_value_heads", "head_dim",
                "max_position_embeddings",
            )
        }
        if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in integer_fields.values()):
            return None
        nested_fields = {
            key: dflash.get(key)
            for key in ("conv_kernel_size", "conv_group_size", "selector_rank", "selector_top_k")
        }
        if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in nested_fields.values()):
            return None
        if integer_fields["hidden_size"] % nested_fields["conv_group_size"] != 0:
            return None
        if nested_fields["selector_top_k"] > integer_fields["vocab_size"]:
            return None
        target_layer_ids = dflash.get("target_layer_ids")
        configured_block = config.get("block_size")
        if configured_block is None:
            configured_block = dflash.get("block_size")
        layer_types = config.get("layer_types")
        rope_theta = self.values.deep_get(config, ("rope_theta",), ("rope_parameters", "rope_theta"))
        rms_norm_eps = config.get("rms_norm_eps")
        attention_bias = config.get("attention_bias", False)
        if (
            not isinstance(config.get("model_type"), str) or not config.get("model_type")
            or not isinstance(config.get("tie_word_embeddings"), bool)
            or not isinstance(attention_bias, bool)
            or not isinstance(rms_norm_eps, (int, float)) or isinstance(rms_norm_eps, bool) or rms_norm_eps <= 0
            or not isinstance(rope_theta, (int, float)) or isinstance(rope_theta, bool) or rope_theta <= 0
            or not isinstance(layer_types, list)
            or len(layer_types) != integer_fields["num_hidden_layers"]
            or any(value not in {"full_attention", "sliding_attention"} for value in layer_types)
            or not isinstance(configured_block, int)
            or isinstance(configured_block, bool)
            or not 1 <= configured_block <= 64
        ):
            return None
        if "sliding_attention" in layer_types:
            sliding_window = config.get("sliding_window")
            if not isinstance(sliding_window, int) or isinstance(sliding_window, bool) or sliding_window <= 0:
                return None
        if target_layer_ids is None:
            target_layer_ids = []
        elif (
            not isinstance(target_layer_ids, list)
            or not target_layer_ids
            or any(not isinstance(value, int) or isinstance(value, bool) for value in target_layer_ids)
            or target_layer_ids != sorted(set(target_layer_ids))
            or target_layer_ids[0] < 0
            or target_layer_ids[-1] >= integer_fields["num_target_layers"]
        ):
            return None
        mask_token_id = dflash.get("mask_token_id")
        if mask_token_id is not None and (
            not isinstance(mask_token_id, int) or isinstance(mask_token_id, bool)
            or not 0 <= mask_token_id < integer_fields["vocab_size"]
        ):
            return None
        input_scale = dflash.get("input_embedding_scale")
        if input_scale is not None and (
            not isinstance(input_scale, (int, float)) or isinstance(input_scale, bool) or input_scale <= 0
        ):
            return None
        return {
            **integer_fields,
            **nested_fields,
            "target_layer_ids": target_layer_ids,
            "block_size": configured_block,
            "attention_bias": attention_bias,
        }


    def dflash2_expected_tensor_shapes(self, config: dict[str, Any]) -> dict[str, list[int]]:
        shape = self.dflash2_draft_shape(config)
        if not shape:
            return {}
        hidden = int(shape["hidden_size"])
        intermediate = int(shape["intermediate_size"])
        layers = int(shape["num_hidden_layers"])
        attention_heads = int(shape["num_attention_heads"])
        kv_heads = int(shape["num_key_value_heads"])
        head_dim = int(shape["head_dim"])
        conv_kernel = int(shape["conv_kernel_size"])
        conv_groups = int(shape["conv_group_size"])
        selector_rank = int(shape["selector_rank"])
        selected_target_layers = len(shape["target_layer_ids"]) if shape["target_layer_ids"] else layers
        expected = {
            "candidate_selector.hidden_projection.weight": [selector_rank, hidden],
            "fc.weight": [hidden, selected_target_layers * hidden],
            "hidden_norm.weight": [hidden],
            "norm.weight": [hidden],
        }
        for index in range(layers):
            prefix = f"layers.{index}"
            expected.update({
                f"{prefix}.input_layernorm.weight": [hidden],
                f"{prefix}.post_attention_layernorm.weight": [hidden],
                f"{prefix}.self_attn.q_proj.weight": [attention_heads * head_dim, hidden],
                f"{prefix}.self_attn.k_proj.weight": [kv_heads * head_dim, hidden],
                f"{prefix}.self_attn.v_proj.weight": [kv_heads * head_dim, hidden],
                f"{prefix}.self_attn.o_proj.weight": [hidden, attention_heads * head_dim],
                f"{prefix}.self_attn.q_norm.weight": [head_dim],
                f"{prefix}.self_attn.k_norm.weight": [head_dim],
                f"{prefix}.mlp.gate_proj.weight": [intermediate, hidden],
                f"{prefix}.mlp.up_proj.weight": [intermediate, hidden],
                f"{prefix}.mlp.down_proj.weight": [hidden, intermediate],
                f"{prefix}.attention_conv.base_kernel": [2, conv_kernel, hidden],
                f"{prefix}.attention_conv.kernel_projection.weight": [
                    2 * conv_kernel * (hidden // conv_groups), hidden,
                ],
                f"{prefix}.mlp_conv.base_kernel": [2, conv_kernel, hidden],
                f"{prefix}.mlp_conv.kernel_projection.weight": [
                    2 * conv_kernel * (hidden // conv_groups), hidden,
                ],
            })
            if shape["attention_bias"]:
                expected.update({
                    f"{prefix}.self_attn.q_proj.bias": [attention_heads * head_dim],
                    f"{prefix}.self_attn.k_proj.bias": [kv_heads * head_dim],
                    f"{prefix}.self_attn.v_proj.bias": [kv_heads * head_dim],
                    f"{prefix}.self_attn.o_proj.bias": [hidden],
                })
        return expected


    def required_dflash2_tensors(self, config: dict[str, Any]) -> set[str]:
        return set(self.dflash2_expected_tensor_shapes(config))


    def is_dflash2_draft(self, path: Path, config: dict[str, Any]) -> bool:
        del path  # The checkpoint contract, not its folder name, identifies a draft.
        # Weight validation is deliberately performed separately during scanning and
        # immediately before launch so incomplete helper checkpoints remain hidden.
        return bool(self.required_dflash2_tensors(config))


    def dflash2_draft_complete(self, path: Path, config: dict[str, Any]) -> bool:
        if not self.is_dflash2_draft(path, config):
            return False
        if config.get("quantization") is not None or config.get("quantization_config") is not None:
            return False  # A quantized draft needs a separately verified tensor schema.
        valid, tensors, _manifest = self.artifacts.safetensors_inventory(path)
        expected_shapes = self.dflash2_expected_tensor_shapes(config)
        required = set(expected_shapes)
        shape = self.dflash2_draft_shape(config)
        if not valid or not required or not shape or not required.issubset(tensors):
            return False
        predecessor_names = [name for name in (
            "candidate_selector.predecessor_codebook.weight",
            "candidate_selector.predecessor_codebook",
        ) if name in tensors]
        successor_names = [name for name in (
            "candidate_selector.successor_codebook.weight",
            "candidate_selector.successor_codebook",
        ) if name in tensors]
        if len(predecessor_names) != 1 or len(successor_names) != 1:
            return False
        predecessor = predecessor_names[0]
        successor = successor_names[0]
        if set(tensors) != required | {predecessor, successor}:
            return False
        hidden_size = int(shape["hidden_size"])
        selector_rank = int(shape["selector_rank"])
        vocab_size = int(shape["vocab_size"])
        floating_dtypes = {"F16", "BF16", "F32", "F64"}
        if any(tensors[name].get("dtype") not in floating_dtypes for name in required | {predecessor, successor}):
            return False
        if tensors[predecessor].get("shape") != [vocab_size, selector_rank]:
            return False
        if tensors[successor].get("shape") != [vocab_size, selector_rank]:
            return False
        if any(tensors[name].get("shape") != expected for name, expected in expected_shapes.items()):
            return False
        return True


    def dflash2_target_profile(self, target_path: Path, target_config: dict[str, Any]) -> dict[str, Any] | None:
        """Identify the exact published Qwen3.8-27B target contract without loading weights."""
        target_name = str(target_path).lower()
        if not re.search(r"qwen3[._-]?8[^/]*27b", target_name) or "ornith" in target_name:
            return None
        target_text = (
            target_config.get("text_config")
            if isinstance(target_config.get("text_config"), dict)
            else target_config
        )
        target_type = target_text.get("model_type")
        if target_type not in {"qwen3_5_text", "qwen3_8", "qwen3_8_text"}:
            return None
        geometry = {
            "num_target_layers": target_text.get("num_hidden_layers"),
            "vocab_size": target_text.get("vocab_size"),
            "hidden_size": target_text.get("hidden_size"),
            "intermediate_size": target_text.get("intermediate_size"),
        }
        if geometry != self.policy.dflash.dflash2_target_geometry:
            return None
        return {
            "draftRepo": self.policy.dflash.dflash2_draft_repo,
            "draftUrl": self.policy.dflash.dflash2_draft_url,
            "draftSizeLabel": self.policy.dflash.dflash2_draft_size_label,
            "geometry": dict(geometry),
        }


    def matching_dflash2_draft(self, 
        target_path: Path,
        target_config: dict[str, Any],
        drafts: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Pair only the exact Qwen3.8-27B target geometry advertised by a draft."""
        target_profile = self.dflash2_target_profile(target_path, target_config)
        if not target_profile:
            return None
        target_geometry = target_profile["geometry"]
        for draft in drafts:
            draft_path = Path(str(draft.get("path", "")))
            if not re.search(r"qwen3[._-]?8[^/]*27b[^/]*dflash2", str(draft_path).lower()):
                continue
            config = draft.get("config")
            if not isinstance(config, dict):
                continue
            shape = self.dflash2_draft_shape(config)
            if shape and all(shape.get(key) == value for key, value in target_geometry.items()):
                return draft
        return None


    def dflash2_pair_fingerprint(self, 
        target_path: Path,
        target_config: dict[str, Any],
        draft_path: Path,
        draft_config: dict[str, Any],
    ) -> str:
        def manifest(path: Path, config: dict[str, Any]) -> dict[str, Any]:
            index = self.io.read_json(path / "model.safetensors.index.json")
            _valid, _tensors, safetensors = self.artifacts.safetensors_inventory(path)
            try:
                weights = sorted(
                    (
                        item.name,
                        item.stat().st_dev,
                        item.stat().st_size,
                        item.stat().st_mtime_ns,
                        item.stat().st_ino,
                        os.readlink(item) if item.is_symlink() else None,
                    )
                    for item in path.iterdir()
                    if item.is_file() and item.suffix in {".safetensors", ".gguf"}
                )
            except OSError:
                weights = []
            return {"config": config, "index": index, "weights": weights, "safetensors": safetensors}

        identity = {
            "target": str(target_path.resolve()),
            "draft": str(draft_path.resolve()),
            "target_layers": self.values.deep_get(target_config, ("text_config", "num_hidden_layers"), ("num_hidden_layers",)),
            "target_vocab": self.values.deep_get(target_config, ("text_config", "vocab_size"), ("vocab_size",)),
            "draft_shape": self.dflash2_draft_shape(draft_config),
            "target_manifest": manifest(target_path, target_config),
            "draft_manifest": manifest(draft_path, draft_config),
        }
        encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


    def model_artifact_fingerprint(self, path: Path, config: dict[str, Any]) -> str:
        """Fingerprint model identity without hashing multi-gigabyte weight payloads."""
        try:
            real = path.resolve(strict=True)
            weights = []
            candidates = [
                item for item in real.iterdir()
                if item.is_file() and item.suffix in {".safetensors", ".gguf"}
            ]
            nested_mtp = self.mtplx_sidecar_path(real, config)
            if nested_mtp.is_file() and nested_mtp not in candidates:
                candidates.append(nested_mtp)
            if real.name.endswith(".gturbo"):
                candidates.extend(
                    item for item in (
                        real / "model_weights.bin",
                        real / "manifest.json",
                        real / "verified-install.json",
                        real / "packed_experts" / "layout.json",
                    )
                    if item.is_file()
                )
                candidates.extend(
                    item for item in (real / "packed_experts").glob("layer_*.bin")
                    if item.is_file()
                )
            for item in sorted(set(candidates), key=lambda value: str(value.relative_to(real))):
                details = item.stat()
                weights.append({
                    "name": str(item.relative_to(real)),
                    "device": details.st_dev,
                    "inode": details.st_ino,
                    "size": details.st_size,
                    "modified": details.st_mtime_ns,
                    "link": os.readlink(item) if item.is_symlink() else None,
                })
        except OSError:
            return ""
        identity = {
            "path": str(real),
            "config": config,
            "index": self.io.read_json(real / "model.safetensors.index.json"),
            "mferenceManifest": self.io.read_json(real / "manifest.json") if real.name.endswith(".gturbo") else {},
            "mferenceReceipt": self.io.read_json(real / "verified-install.json") if real.name.endswith(".gturbo") else {},
            "weights": weights,
        }
        encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


    def ane_quantization_profile(self, config: dict[str, Any]) -> dict[str, Any]:
        """Fail-closed structural check for the dense Qwen ANE patch."""
        model_type = str(self.values.deep_get(config, ("text_config", "model_type"), ("model_type",)) or "").lower()
        architectures = config.get("architectures") or self.values.deep_get(config, ("text_config", "architectures")) or []
        architecture_text = " ".join(str(item).lower() for item in architectures if isinstance(item, str))
        dense_qwen = (
            model_type.startswith(("qwen3_5", "qwen3_6", "qwen3_8"))
            and "moe" not in model_type
            and "moe" not in architecture_text
        )
        quant = self.values.deep_get(config, ("quantization",), ("quantization_config",))
        if not isinstance(quant, dict):
            quant = {}
        mode = str(quant.get("mode") or "").lower()
        bits = quant.get("bits")
        group_size = quant.get("group_size")
        valid_number = lambda value: isinstance(value, int) and not isinstance(value, bool)
        unsupported_overrides: list[str] = []
        for name, override in quant.items():
            if not isinstance(name, str) or not isinstance(override, dict) or ".mlp." not in name:
                continue
            if not any(part in name for part in ("gate_proj", "up_proj", "down_proj")):
                continue
            override_mode = str(override.get("mode") or mode).lower()
            override_bits = override.get("bits", bits)
            override_group = override.get("group_size", group_size)
            if (
                override_mode != "affine"
                or not valid_number(override_bits) or override_bits not in {2, 4, 5, 6, 8}
                or not valid_number(override_group) or override_group not in {64, 128}
            ):
                unsupported_overrides.append(name)
        compatible = bool(
            dense_qwen
            and mode == "affine"
            and valid_number(bits) and bits in {4, 5, 6, 8}
            and valid_number(group_size) and group_size in {64, 128}
            and not unsupported_overrides
        )
        if not dense_qwen:
            reason = "ANE prefill currently supports dense Qwen3.5/3.6/3.8 checkpoints only."
        elif mode != "affine":
            reason = "The ANE path requires affine MLX quantisation."
        elif not valid_number(bits) or bits not in {4, 5, 6, 8}:
            reason = "The checkpoint's default weight precision is not supported by the ANE path."
        elif not valid_number(group_size) or group_size not in {64, 128}:
            reason = f"The checkpoint uses group size {group_size or 'unknown'}; ANE requires group size 64 or 128."
        elif unsupported_overrides:
            reason = "At least one MLP override uses an unsupported ANE quantisation layout."
        else:
            reason = f"Dense Qwen affine {bits}-bit / group-size {group_size} layout is structurally eligible."
        return {
            "compatible": compatible,
            "reason": reason,
            "modelType": model_type or "unknown",
            "mode": mode or "unknown",
            "bits": bits if valid_number(bits) else None,
            "groupSize": group_size if valid_number(group_size) else None,
            "unsupportedOverrideCount": len(unsupported_overrides),
        }


    def ane_cpu_sharing_profile(self, path: Path) -> dict[str, Any]:
        """Prove that a checkpoint is the separate FP16 clone required upstream."""
        valid, tensors, _manifest = self.artifacts.safetensors_inventory(path)
        default = {
            "eligible": False,
            "reason": "A complete safetensors inventory is required before CPU sharing can be offered.",
            "floatDtypes": [],
            "floatingTensorCount": 0,
            "gateUpScalePairs": 0,
            "downProjectionEligible": False,
            "gdnEligible": False,
            "profileFingerprint": "",
        }
        if not valid or not tensors:
            return default

        floating_dtypes = {"F16", "BF16", "F32", "F64"}
        floating = {
            name: metadata for name, metadata in tensors.items()
            if metadata.get("dtype") in floating_dtypes
        }

        def projection_prefixes(suffix: str) -> set[str]:
            return {name[:-len(suffix)] for name in tensors if name.endswith(suffix)}

        gate = projection_prefixes(".mlp.gate_proj.scales")
        up = projection_prefixes(".mlp.up_proj.scales")
        down = projection_prefixes(".mlp.down_proj.scales")
        gdn = projection_prefixes(".linear_attn.in_proj_qkv.scales")
        paired_gate_up = bool(gate and gate == up)
        all_float16 = bool(floating) and all(
            metadata.get("dtype") == "F16" for metadata in floating.values()
        )
        fingerprint_payload = [
            {
                "name": name,
                "dtype": metadata.get("dtype"),
                "shape": metadata.get("shape"),
                "shard": metadata.get("shard"),
            }
            for name, metadata in sorted(tensors.items())
        ]
        profile_fingerprint = hashlib.sha256(json.dumps(
            fingerprint_payload, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        seen_dtypes = sorted({str(metadata.get("dtype")) for metadata in floating.values()})
        eligible = bool(paired_gate_up and all_float16)
        if not floating:
            reason = "No floating checkpoint tensors were found, so the required FP16 clone cannot be proved."
        elif not paired_gate_up:
            reason = "The checkpoint does not contain a complete matching set of MLP gate/up scale tensors."
        elif not all_float16:
            listed = ", ".join(seen_dtypes) or "unknown"
            reason = (
                f"CPU sharing requires a separate all-FP16 checkpoint clone; this checkpoint contains {listed} floating tensors."
            )
        else:
            reason = (
                f"All {len(floating):,} floating tensors and {len(gate):,} MLP gate/up scale pairs are FP16."
            )
        return {
            "eligible": eligible,
            "reason": reason,
            "floatDtypes": seen_dtypes,
            "floatingTensorCount": len(floating),
            "gateUpScalePairs": len(gate) if paired_gate_up else 0,
            "downProjectionEligible": bool(eligible and down == gate),
            "gdnEligible": bool(eligible and gdn),
            "profileFingerprint": profile_fingerprint,
        }


    def ane_memory_readiness(self, 
        weight_bytes: int, total_bytes: int, cpu_assist: bool = False,
    ) -> dict[str, Any]:
        weight_bytes = max(0, int(weight_bytes or 0))
        total_bytes = max(0, int(total_bytes or 0))
        reserve = self.policy.ane.ane_cpu_tuner_reserve_bytes if cpu_assist else self.policy.ane.ane_tuner_reserve_bytes
        required = weight_bytes + reserve
        ready = bool(weight_bytes > 0 and total_bytes >= required)
        return {
            "ready": ready,
            "totalBytes": total_bytes,
            "modelBytes": weight_bytes,
            "reserveBytes": reserve,
            "requiredBytes": required,
            "headroomBytes": max(0, total_bytes - weight_bytes),
            "cpuAssist": bool(cpu_assist),
            "reason": (
                f"Installed memory leaves at least {self.values.display_size(reserve)} beyond the checkpoint weights."
                if ready else
                f"{'CPU candidate tuning' if cpu_assist else 'Tuning'} needs checkpoint weights plus a conservative {self.values.display_size(reserve)} reserve."
            ),
        }


    def ane_fp16_clone_source_profile(self, 
        model_path: Path, config: dict[str, Any], weight_bytes: int,
    ) -> dict[str, Any]:
        """Classify a read-only BF16 checkpoint for the tagged upstream clone path."""
        quantization = self.ane_quantization_profile(config)
        cpu_profile = self.ane_cpu_sharing_profile(model_path)
        dtypes = set(cpu_profile.get("floatDtypes") or [])
        convertible_dtypes = bool(dtypes and "BF16" in dtypes and dtypes.issubset({"BF16", "F16"}))
        eligible = bool(
            weight_bytes > 0
            and quantization.get("compatible")
            and not cpu_profile.get("eligible")
            and convertible_dtypes
            and int(cpu_profile.get("gateUpScalePairs") or 0) > 0
        )
        if not quantization.get("compatible"):
            reason = str(quantization.get("reason") or "The checkpoint is not eligible for ANE prefill.")
        elif cpu_profile.get("eligible"):
            reason = "This checkpoint is already an all-FP16 CPU-sharing clone."
        elif not dtypes:
            reason = "The checkpoint's floating tensor types could not be proved."
        elif not convertible_dtypes:
            reason = (
                "The tagged clone path accepts BF16/F16 floating tensors only; "
                f"this checkpoint contains {', '.join(sorted(dtypes))}."
            )
        elif int(cpu_profile.get("gateUpScalePairs") or 0) <= 0:
            reason = "No complete matching MLP gate/up scale pairs were found."
        else:
            reason = "Ready to prepare a separate FP16 clone without modifying the source checkpoint."
        return {
            "eligible": eligible,
            "reason": reason,
            "floatDtypes": sorted(dtypes),
            "sourceTensorFingerprint": str(cpu_profile.get("profileFingerprint") or ""),
            "gateUpScalePairs": int(cpu_profile.get("gateUpScalePairs") or 0),
        }


    def route_host_support(self, 
        model: dict[str, Any], backend: str, capability: dict[str, Any], *,
        runtime_installed: bool, artifact_compatible: bool,
    ) -> dict[str, Any]:
        """Classify host support independently from any performance measurement."""
        profile = model.get("ssdStreaming") if isinstance(model.get("ssdStreaming"), dict) else {}
        installed_memory = profile.get("installedMemoryBytes")
        host_memory = (
            int(installed_memory)
            if isinstance(installed_memory, int) and not isinstance(installed_memory, bool)
            and installed_memory > 0 else None
        )
        runnable = bool(runtime_installed and artifact_compatible)
        support_floor = self.policy.whallm.whallm_support_floor_bytes if backend == "whallm" else None

        if not runnable:
            if not runtime_installed:
                detail = f"{self.policy.backend_labels.get(backend, backend or 'This runtime')} is not installed on this host."
            else:
                detail = str(
                    capability.get("reason")
                    or model.get("status")
                    or "This artifact is not compatible with the installed runtime."
                )
            state = "unavailable"
            label = "Unavailable on this host"
        else:
            qualification = (
                capability.get("nativeContract", {}).get("qualification", {}).get("launcher", {})
                if backend == "freetoken" else {}
            )
            synthetic_only = str(qualification.get("readiness") or "") == "experimental_synthetic_only"
            whallm_below_floor = bool(
                backend == "whallm" and host_memory is not None
                and host_memory < self.policy.whallm.whallm_support_floor_bytes
            )
            if synthetic_only:
                state = "experimental"
                label = "Experimental on this host"
                detail = "Only the synthetic native FreeToken qualification is complete; a real checkpoint is not yet qualified."
            elif whallm_below_floor:
                state = "experimental"
                label = f"Experimental on {host_memory / 1024**3:.0f} GiB"
                detail = (
                    f"Whallm publishes a {self.policy.whallm.whallm_support_floor_bytes / 1024**3:.0f} GiB unified-memory "
                    "support floor. Its live route can be inspected here, but this smaller host is not "
                    "an upstream-supported configuration."
                )
            else:
                state = "supported"
                label = "Supported on this host"
                detail = "The installed runtime and scanned artifact expose a compatible local route."

        return {
            "version": self.policy.general.route_evidence_schema_version,
            "state": state,
            "tier": state,
            "label": label,
            "detail": detail,
            "hostMemoryBytes": host_memory,
            "supportFloorBytes": support_floor,
        }


    def checkpoint_has_mtp_weights(self, path: Path, config: dict[str, Any]) -> bool:
        """Conservatively detect persisted MTP tensors without loading weights."""
        prefixes = ["mtp.", "language_model.mtp.", "model.mtp.", "model.language_model.mtp."]
        configs = (config, config.get("text_config") if isinstance(config.get("text_config"), dict) else {})
        try:
            nextn = max(int(item.get("num_nextn_predict_layers", 0) or 0) for item in configs)
            main = max(int(item.get("num_hidden_layers", 0) or 0) for item in configs)
        except (TypeError, ValueError):
            nextn, main = 0, 0
        if nextn > 0 and main > 0:
            for index in range(nextn):
                prefixes.extend([
                    f"model.layers.{main + index}.",
                    f"language_model.model.layers.{main + index}.",
                    f"model.language_model.layers.{main + index}.",
                ])

        index = self.io.read_json(path / "model.safetensors.index.json")
        weight_map = index.get("weight_map")
        if isinstance(weight_map, dict) and weight_map:
            return any(str(key).startswith(tuple(prefixes)) for key in weight_map)

        # Unsharded safetensors keep a JSON key table at the start of the file.
        # Read only that metadata header, never the tensor payload.
        for shard in sorted(path.glob("*.safetensors")):
            if shard.name == "mtp.safetensors":
                continue
            try:
                with open(shard, "rb") as handle:
                    length = int.from_bytes(handle.read(8), "little")
                    if not 2 <= length <= 64 * 1024 * 1024:
                        continue
                    header = json.loads(handle.read(length))
                if isinstance(header, dict) and any(str(key).startswith(tuple(prefixes)) for key in header if key != "__metadata__"):
                    return True
            except (OSError, ValueError, UnicodeError):
                continue
        return False


    def template_reasoning_efforts(self, path: Path) -> list[str]:
        """Return only reasoning-effort literals advertised by this template."""
        template = ""
        file_path = path / "chat_template.jinja"
        try:
            if file_path.is_file() and file_path.stat().st_size <= 2 * 1024 * 1024:
                template = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
        if not template:
            tokenizer = self.io.read_json(path / "tokenizer_config.json")
            candidate = tokenizer.get("chat_template")
            if isinstance(candidate, str) and len(candidate) <= 2 * 1024 * 1024:
                template = candidate
        if "reasoning_effort" not in template:
            return []
        return [level for level in ("minimal", "low", "medium", "high", "xhigh") if re.search(rf"['\"]{level}['\"]", template)]


    def model_default_sampling(self, path: Path) -> dict[str, int | float]:
        """Read bounded generation defaults without inventing a sampler."""
        source = self.io.read_json(path / "generation_config.json")
        result: dict[str, int | float] = {}
        for key in SUPPORTED_SAMPLING_FIELDS:
            if key not in source:
                continue
            try:
                result.update(canonicalize_sampling({key: source[key]}))
            except SamplingContractError:
                # Model metadata is descriptive, not a user request. Preserve the
                # prior bounded-reader behavior by omitting malformed defaults.
                continue
        return result


    def validate_native_freetoken_qualification(self, 
        value: Any, contract: dict[str, Any], model_path: Path, *, live: bool = False,
    ) -> dict[str, Any]:
        """Validate runtime-owned maturity evidence and bind real claims to this receipt."""
        if not isinstance(value, dict):
            raise ValueError("Native FreeToken omitted its checkpoint qualification evidence.")
        if value.get("schema_version") != self.policy.freetoken.freetoken_native_qualification_schema_version:
            raise ValueError("Native FreeToken returned an unsupported qualification schema.")
        if value.get("synthetic_path_verified") is not True:
            raise ValueError("Native FreeToken did not verify its bounded synthetic path.")
        if not isinstance(value.get("real_checkpoint_verified"), bool) or not isinstance(
            value.get("inspected_checkpoint_qualified"), bool
        ):
            raise ValueError("Native FreeToken returned ambiguous checkpoint qualification flags.")
        if value["inspected_checkpoint_qualified"] is not value["real_checkpoint_verified"]:
            raise ValueError("Native FreeToken contradicted its checkpoint qualification state.")

        evidence = value.get("evidence")
        launcher_policy = value.get("launcher")
        if not isinstance(evidence, dict) or not isinstance(launcher_policy, dict):
            raise ValueError("Native FreeToken returned incomplete qualification evidence.")
        synthetic = evidence.get("synthetic")
        if (
            not isinstance(synthetic, dict)
            or synthetic.get("evidence_id") != self.policy.freetoken.freetoken_native_synthetic_evidence_id
            or synthetic.get("kind") != "tiny_synthetic_checkpoint_end_to_end"
            or synthetic.get("real_weights") is not False
            or synthetic.get("coverage") != list(self.policy.freetoken.freetoken_native_synthetic_coverage)
        ):
            raise ValueError("Native FreeToken's synthetic qualification receipt is invalid.")
        if not isinstance(launcher_policy.get("large_download_recommended"), bool):
            raise ValueError("Native FreeToken returned an ambiguous model-acquisition policy.")

        if value["real_checkpoint_verified"] is False:
            if not (
                value.get("maturity") == "synthetic_path_verified"
                and value.get("qualified_checkpoint") is None
                and evidence.get("real_checkpoint") is None
                and launcher_policy.get("readiness") == "experimental_synthetic_only"
                and launcher_policy.get("setup_mode") == "existing_local_checkpoint_only"
                and launcher_policy.get("large_download_recommended") is False
            ):
                raise ValueError("Native FreeToken's synthetic-only qualification policy is inconsistent.")
            return copy.deepcopy(value)

        qualified = value.get("qualified_checkpoint")
        real_evidence = evidence.get("real_checkpoint")
        if not isinstance(qualified, dict) or not isinstance(real_evidence, dict):
            raise ValueError("Native FreeToken's real-checkpoint qualification is incomplete.")
        if not (
            value.get("maturity") == "real_checkpoint_verified"
            and launcher_policy.get("readiness") == "qualified_real_checkpoint"
            and launcher_policy.get("setup_mode") == "exact_qualified_checkpoint_only"
            and launcher_policy.get("large_download_recommended") is False
        ):
            raise ValueError("Native FreeToken's real-checkpoint launcher policy is invalid.")
        for key in ("qualification_id", "model_id", "revision", "resolved_path", "architecture"):
            if not isinstance(qualified.get(key), str) or not qualified[key]:
                raise ValueError("Native FreeToken's qualified checkpoint identity is incomplete.")
        weight_bytes = qualified.get("weight_bytes")
        if not isinstance(weight_bytes, int) or isinstance(weight_bytes, bool) or weight_bytes <= 0:
            raise ValueError("Native FreeToken's qualified checkpoint size is invalid.")
        if not isinstance(qualified.get("quantization_method"), str):
            raise ValueError("Native FreeToken's qualified checkpoint quantization is invalid.")
        fingerprint = qualified.get("checkpoint_fingerprint")
        fingerprint_value = fingerprint.get("value") if isinstance(fingerprint, dict) else None
        if not (
            isinstance(fingerprint, dict)
            and fingerprint.get("algorithm") == "sha256"
            and isinstance(fingerprint_value, str)
            and len(fingerprint_value) == 64
            and all(character in "0123456789abcdef" for character in fingerprint_value)
        ):
            raise ValueError("Native FreeToken's qualified checkpoint fingerprint is invalid.")
        try:
            qualified_path = Path(qualified["resolved_path"]).expanduser().resolve(strict=True)
            expected_path = model_path.expanduser().resolve(strict=True)
        except (OSError, RuntimeError, ValueError) as error:
            raise ValueError("Native FreeToken's qualified checkpoint path could not be revalidated.") from error
        model = contract["model"]
        sizing = contract["sizing"]
        quantization = model.get("quantization")
        if (
            qualified_path != expected_path
            or (not live and qualified.get("model_id") != model.get("id"))
            or qualified.get("architecture") != model.get("architecture")
            or weight_bytes != sizing.get("weight_bytes")
            or not isinstance(quantization, dict)
            or qualified.get("quantization_method") != quantization.get("method")
        ):
            raise ValueError("Native FreeToken's real-checkpoint evidence describes a different checkpoint.")
        runtime = contract["runtime"]
        if not (
            real_evidence.get("evidence_id") == qualified["qualification_id"]
            and real_evidence.get("kind") == self.policy.freetoken.freetoken_native_real_checkpoint_test_kind
            and real_evidence.get("real_weights") is True
            and real_evidence.get("server_started") is True
            and real_evidence.get("token_generation_succeeded") is True
            and isinstance(real_evidence.get("tested_at"), str)
            and bool(real_evidence["tested_at"])
            and real_evidence.get("runtime_version") == runtime.get("freetoken_version")
            and real_evidence.get("native_port_api_version") == runtime.get("native_port_api_version")
        ):
            raise ValueError("Native FreeToken's real-checkpoint serve-and-generation evidence is invalid.")
        return copy.deepcopy(value)


    def validate_native_freetoken_contract(self, 
        value: Any, model_path: Path, *, live: bool = False,
    ) -> dict[str, Any]:
        """Validate the port's versioned capability receipt without guessing support."""
        if not isinstance(value, dict):
            raise ValueError("Native FreeToken returned no capability document.")
        if (
            value.get("schema_version") != self.policy.freetoken.freetoken_native_schema_version
            or value.get("schema_name") != self.policy.freetoken.freetoken_native_schema_name
            or value.get("backend") != "mlx-metal"
        ):
            raise ValueError("Native FreeToken returned an unsupported capability schema.")
        required_objects = (
            "runtime", "device", "model", "checkpoint", "sizing",
            "working_set", "startup", "qualification", "support", "constraints", "security",
        )
        if any(not isinstance(value.get(key), dict) for key in required_objects):
            raise ValueError("Native FreeToken returned an incomplete capability document.")
        runtime = value["runtime"]
        if (
            runtime.get("native_port_api_version") != self.policy.freetoken.freetoken_native_api_version
            or runtime.get("backend") != "mlx-metal"
            or not isinstance(runtime.get("freetoken_version"), str)
            or not runtime["freetoken_version"]
        ):
            raise ValueError("Native FreeToken's launcher API contract is incompatible.")
        supported = value.get("supported")
        if not isinstance(supported, bool):
            raise ValueError("Native FreeToken did not make a fail-closed support decision.")
        support = value["support"]
        support_keys = {
            "chat_completions", "completions", "streaming", "sampling",
            "tools", "responses", "continuous_batching", "prefix_cache",
            "expert_placement",
        }
        if any(not isinstance(support.get(key), bool) for key in support_keys):
            raise ValueError("Native FreeToken returned ambiguous API support flags.")
        security = value["security"]
        if (
            security.get("local_files_only") is not True
            or security.get("network_downloads") is not False
            or security.get("trust_remote_code") is not False
        ):
            raise ValueError("Native FreeToken did not preserve the local-only checkpoint policy.")
        constraints = value["constraints"]
        if (
            constraints.get("decoding") != "greedy_only"
            or constraints.get("supported_model_type") != "qwen3_moe"
            or constraints.get("one_prompt_per_request") is not True
            or constraints.get("continuous_batching_with_prefix_cache") is not False
        ):
            raise ValueError("Native FreeToken returned an unknown execution contract.")
        self.validate_native_freetoken_qualification(
            value["qualification"], value, model_path, live=live,
        )
        model = value["model"]
        try:
            reported_path = Path(str(model.get("path") or "")).expanduser().resolve(strict=False)
            expected_path = model_path.expanduser().resolve(strict=True)
        except (OSError, RuntimeError, ValueError) as error:
            raise ValueError("The native FreeToken checkpoint path could not be revalidated.") from error
        if reported_path != expected_path or model.get("local") is not True:
            raise ValueError("Native FreeToken inspected a different checkpoint path.")
        if supported:
            if value.get("rejection") is not None:
                raise ValueError("Native FreeToken contradicted its support decision.")
            if (
                model.get("model_type") != "qwen3_moe"
                or support.get("chat_completions") is not True
                or support.get("completions") is not True
                or support.get("streaming") is not True
                or support.get("sampling") is not False
                or support.get("tools") is not False
                or support.get("responses") is not False
            ):
                raise ValueError("Native FreeToken advertised an unsupported model or API surface.")
        else:
            rejection = value.get("rejection")
            if (
                not isinstance(rejection, dict)
                or not isinstance(rejection.get("code"), str)
                or not rejection.get("code")
                or not isinstance(rejection.get("message"), str)
                or not rejection.get("message")
            ):
                raise ValueError("Native FreeToken rejected the checkpoint without a reason.")
        service = value.get("service")
        if live:
            if not isinstance(service, dict) or not isinstance(service.get("enabled"), dict):
                raise ValueError("Native FreeToken health omitted its live service contract.")
            enabled = service["enabled"]
            if any(not isinstance(enabled.get(key), bool) for key in support_keys):
                raise ValueError("Native FreeToken health returned ambiguous enabled features.")
            if supported and (
                value.get("status") != "ok"
                or service.get("status") != "ready"
                or enabled.get("chat_completions") is not True
                or enabled.get("streaming") is not True
                or enabled.get("sampling") is not False
                or enabled.get("tools") is not False
                or enabled.get("responses") is not False
            ):
                raise ValueError("Native FreeToken health did not preserve the inspected API contract.")
        elif service is not None:
            raise ValueError("Native FreeToken inspection unexpectedly described a running service.")
        return copy.deepcopy(value)


    def inspect_native_freetoken_model(self, 
        model_path: Path, context_tokens: int, model_fingerprint: str, *,
        force: bool = False,
    ) -> dict[str, Any]:
        """Run the port's header-only local inspection and cache the exact receipt."""
        binary = self.runtime.selected_binary("freetoken_native")
        if not binary or not self.runtime.native_freetoken_host_supported():
            raise ValueError("The native Apple-Silicon FreeToken port is not installed.")
        try:
            binary_path = Path(binary).expanduser().resolve(strict=True)
            model_path = model_path.expanduser().resolve(strict=True)
            binary_stat = binary_path.stat()
        except OSError as error:
            raise ValueError("The native FreeToken executable or checkpoint moved after discovery.") from error
        if not model_path.is_dir() or not binary_path.is_file() or not os.access(binary_path, os.X_OK):
            raise ValueError("The native FreeToken executable or checkpoint is unavailable.")
        source_identity = self._native_inspection_source_identity(str(binary), model_path)
        cache_key = hashlib.sha256(json.dumps({
            "binary": str(binary_path),
            "sourceIdentity": source_identity,
            "model": str(model_path),
            "fingerprint": model_fingerprint,
            "context": context_tokens,
            "schema": self.policy.freetoken.freetoken_native_schema_version,
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        if not force and source_identity is not None:
            with self.state.native_inspection_lock:
                cached = self.state.native_inspection_cache.get(cache_key)
            if isinstance(cached, tuple) and len(cached) == 2:
                if self._native_inspection_source_identity(str(binary), model_path) != source_identity:
                    raise ValueError("Native FreeToken's executable or checkpoint changed during inspection.")
                return self._validated_native_freetoken_probe(cached[0], cached[1], model_path)
        env = os.environ.copy()
        env.update({
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
        })
        try:
            result = self.io.run_catalog_cli(
                [
                    str(binary_path), "macos-inspect", "--model", str(model_path),
                    "--context-tokens", str(context_tokens), "--json",
                ],
                cwd=str(model_path), env=env, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=30, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError(f"Native FreeToken inspection could not finish: {error}") from error
        if self._native_inspection_source_identity(str(binary), model_path) != source_identity:
            raise ValueError("Native FreeToken's executable or checkpoint changed during inspection.")
        contract = self._validated_native_freetoken_probe(result.returncode, result.stdout, model_path)
        if source_identity is not None:
            with self.state.native_inspection_lock:
                if len(self.state.native_inspection_cache) >= 64:
                    self.state.native_inspection_cache.pop(
                        next(iter(self.state.native_inspection_cache)), None,
                    )
                # Strings and integers are immutable observations. A current
                # support/qualification decision is recomputed from them.
                self.state.native_inspection_cache[cache_key] = (int(result.returncode), result.stdout)
        return contract

    def _validated_native_freetoken_probe(self, returncode: int, stdout: str, model_path: Path) -> dict[str, Any]:
        encoded = stdout.encode("utf-8", "replace")
        if not encoded or len(encoded) > self.policy.freetoken.freetoken_native_inspection_max_response:
            raise ValueError("Native FreeToken returned an empty or oversized inspection receipt.")
        try:
            value = json.loads(stdout)
        except (ValueError, UnicodeError) as error:
            raise ValueError("Native FreeToken inspection did not return valid JSON.") from error
        contract = self.validate_native_freetoken_contract(value, model_path)
        if returncode == 0 and contract.get("supported") is not True:
            raise ValueError("Native FreeToken exited successfully after rejecting the checkpoint.")
        if returncode != 0 and contract.get("supported") is not False:
            raise ValueError("Native FreeToken failed without a fail-closed rejection receipt.")
        return contract


    def mtplx_sidecar_path(self, path: Path, config: dict[str, Any]) -> Path:
        declared = self.values.deep_get(config, ("mlx_lm_extra_tensors", "mtp_file"))
        if isinstance(declared, str) and declared:
            candidate = (path / declared).resolve()
            if candidate.is_relative_to(path.resolve()):
                return candidate
            return path / "__invalid_mtp_path__"
        for name in ("mtp.safetensors", "mtp/weights.safetensors", "model-mtp.safetensors"):
            if (path / name).is_file():
                return path / name
        return path / "mtp.safetensors"


    def _mtplx_native_mtp_inspection(self, binary: str, path: str, fingerprint: str,
                                 binary_mtime: int) -> bool:
        """Native artifact compatibility, deliberately not a speed qualification."""
        source_identity = self._native_inspection_source_identity(binary, Path(path))
        key = (source_identity, str(Path(path).absolute()), fingerprint, binary_mtime)
        cached = None
        if source_identity is not None:
            with self.state.native_inspection_lock:
                cached = self.state.mtplx_inspection_cache.get(key)
        try:
            if cached is None:
                result = self.io.run_catalog_cli(
                    [binary, "inspect", "--model", path, "--json"],
                    env={**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"},
                    capture_output=True, text=True, timeout=20, check=False,
                )
                observed = (int(result.returncode), result.stdout)
            else:
                observed = cached
            if self._native_inspection_source_identity(binary, Path(path)) != source_identity:
                return False
            if not isinstance(observed[1], str) or not 0 < len(observed[1].encode("utf-8")) <= self.policy.general.max_json:
                return False
            receipt = json.loads(observed[1])
            if not isinstance(receipt, dict) or not isinstance(receipt.get("mtp"), dict) or not isinstance(receipt.get("compatibility"), dict):
                return False
            compatible = bool(
                observed[0] == 0
                and Path(receipt.get("model_dir", "")).resolve() == Path(path).resolve()
                and receipt.get("mtp_supported") == "yes"
                and receipt.get("unverified_model") is False
                and receipt.get("mtp", {}).get("passes_tensor_gate") is True
                and receipt.get("compatibility", {}).get("can_run") is True
            )
            if source_identity is not None and cached is None:
                with self.state.native_inspection_lock:
                    if len(self.state.mtplx_inspection_cache) >= 64:
                        self.state.mtplx_inspection_cache.pop(next(iter(self.state.mtplx_inspection_cache)), None)
                    self.state.mtplx_inspection_cache[key] = observed
            return compatible
        except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
            return False


    def native_mtplx_mtp_ready(self, path: Path, config: dict[str, Any]) -> bool:
        binary = self.runtime.selected_binary("mtplx")
        if not binary or not self.mtplx_sidecar_path(path, config).is_file():
            return False
        try:
            sidecar = self.mtplx_sidecar_path(path, config).stat()
            fingerprint = self.model_artifact_fingerprint(path, config)
            return self._mtplx_native_mtp_inspection(
                str(binary), str(path.resolve()),
                f"{fingerprint}:{sidecar.st_size}:{sidecar.st_mtime_ns}:"
                + json.dumps(self.io.read_json(path / "mtplx_runtime.json"), sort_keys=True),
                Path(binary).stat().st_mtime_ns,
            )
        except OSError:
            return False


    def verified_mtplx_runtime(self, path: Path, runtime: dict[str, Any], config: dict[str, Any]) -> bool:
        """Require a complete, internally consistent MTPLX MTP audit stamp."""
        sidecar = path / "mtp.safetensors"
        try:
            size = sidecar.stat().st_size
            if not sidecar.is_file() or size <= 16:
                return False
            with open(sidecar, "rb") as handle:
                header_length = int.from_bytes(handle.read(8), "little")
                if not 2 <= header_length <= 16 * 1024 * 1024 or size <= 8 + header_length:
                    return False
                header = json.loads(handle.read(header_length))
        except OSError:
            return False
        except (ValueError, UnicodeError):
            return False
        if not isinstance(header, dict):
            return False
        tensors = {key: value for key, value in header.items() if key != "__metadata__"}
        if not tensors or not all(str(key).startswith("mtp.") and isinstance(value, dict) for key, value in tensors.items()):
            return False
        payload_size = size - 8 - header_length
        for value in tensors.values():
            offsets = value.get("data_offsets")
            if (
                not isinstance(offsets, list) or len(offsets) != 2
                or not all(isinstance(item, int) and not isinstance(item, bool) for item in offsets)
                or not 0 <= offsets[0] < offsets[1] <= payload_size
            ):
                return False
        contract = runtime.get("mtp_contract")
        evidence = runtime.get("speed_evidence")
        if not isinstance(contract, dict) or not isinstance(evidence, dict):
            return False
        if config.get("mtplx_mtp_contract") != contract:
            return False
        audit = config.get("mtplx_mtp_payload_audit")
        if not isinstance(audit, dict) or audit.get("passed") is not True or audit.get("problems") != []:
            return False
        try:
            tensor_count = int(audit.get("tensor_count"))
            payload_count = int(audit.get("payload_tensor_count"))
            nonzero_count = int(audit.get("nonzero_payload_tensor_count"))
        except (TypeError, ValueError):
            return False
        if tensor_count != len(tensors) or not 0 < payload_count == nonzero_count <= tensor_count:
            return False
        if audit.get("zero_payload_sample") not in ([], None) or audit.get("zero_scale_sample") not in ([], None):
            return False
        required_contract = {
            "base_hidden_variant", "concat_order", "hidden_variant",
            "mtp_position_mode", "mtp_quant_group_size", "mtp_quant_mode",
        }
        if not required_contract.issubset(contract) or not all(contract.get(key) not in {None, ""} for key in required_contract):
            return False
        try:
            maximum = int(runtime.get("mtp_depth_max"))
            default = int(runtime.get("mtp_depth_default"))
        except (TypeError, ValueError):
            return False
        if not 1 <= default <= maximum <= 8:
            return False
        if runtime.get("recommended_profile") not in {"stable", "performance-cold", "sustained", "turbo", "exact"}:
            return False
        if not isinstance(runtime.get("arch_id"), str) or not runtime.get("arch_id"):
            return False
        if evidence.get("verdict") != "mtp_depth_wins":
            return False
        if evidence.get("failure_reasons") or evidence.get("quality_rejected"):
            return False
        rows = evidence.get("forge_verify_rows")
        if not isinstance(rows, list):
            return False
        winner = next(
            (
                row for row in rows
                if isinstance(row, dict) and row.get("depth") == default
            ),
            None,
        )
        try:
            hit_count = int(winner.get("hit_token_budget_count") or 0) if isinstance(winner, dict) else -1
        except (TypeError, ValueError):
            return False
        multiplier = winner.get("multiplier_vs_ar") if isinstance(winner, dict) else None
        if (
            not isinstance(winner, dict)
            or winner.get("quality_passed") is not True
            or winner.get("hit_token_budget") is not False
            or hit_count != 0
            or isinstance(multiplier, bool)
            or not isinstance(multiplier, (int, float))
            or float(multiplier) <= 1.0
        ):
            return False
        return True


    def _normalized_model_type(self, value: Any) -> str:
        return str(value or "").strip().replace("-", "_").casefold()


    def mtplx_exact_2111_runtime(self, version_text: Any) -> bool:
        """Accept only the audited stable 2.11.1 CLI identity.

        The generic semantic parser intentionally tolerates suffixes for release
        ordering. That is too broad for a route which enables an exact reviewed set
        of operator switches, so prerelease, development and local-build suffixes
        fail closed here.
        """
        value = re.sub(r"\s+", " ", str(version_text or "").strip())
        return bool(re.fullmatch(
            r"(?:mtplx\s+)?2\.11\.1(?:\s+\(2\.11\.1\))?",
            value,
            re.IGNORECASE,
        ))


    def mtplx_long_context_2111_contract(self, 
        model: dict[str, Any], capability: dict[str, Any],
        runtime_version: str | None = None,
    ) -> dict[str, Any] | None:
        """Mint the immutable receipt for MTPLX's audited dense-27B operators."""
        if not isinstance(model, dict) or not isinstance(capability, dict):
            return None
        version = str(runtime_version or capability.get("runtimeVersion") or "")[:160]
        if not self.mtplx_exact_2111_runtime(version):
            return None
        if (
            model.get("ready") is not True
            or str(model.get("format") or "") != "mlx"
            or capability.get("mtp") is not True
        ):
            return None
        try:
            model_path = Path(str(model.get("path") or "")).expanduser().resolve(strict=True)
        except OSError:
            return None
        if not model_path.is_dir():
            return None
        config = self.io.read_json(model_path / "config.json")
        if not config:
            return None
        text = config.get("text_config")
        text_config = text if isinstance(text, dict) else config
        root_type = self._normalized_model_type(config.get("model_type"))
        text_type = self._normalized_model_type(text_config.get("model_type"))
        if (
            root_type not in {"qwen3_5", "qwen3_8"}
            or text_type not in {"qwen3_5_text", "qwen3_8"}
        ):
            return None
        identity_text = " ".join(str(model.get(key) or "") for key in (
            "name", "architecture", "modelType", "rootModelType", "textModelType",
        )).casefold()
        if (
            "ornith" in identity_text
            or "flash" in identity_text
            or "moe" in identity_text
            or model.get("mixtureOfExperts") is True
            or any(
                isinstance(text_config.get(key), int)
                and not isinstance(text_config.get(key), bool)
                and int(text_config[key]) > 1
                for key in ("num_experts", "num_local_experts", "n_routed_experts")
            )
        ):
            return None
        geometry = {
            key: text_config.get(key)
            for key in self.policy.mtplx.mtplx_long_context_dense_geometry
        }
        if geometry != self.policy.mtplx.mtplx_long_context_dense_geometry:
            return None
        context_maximum = capability.get("contextMaximum", model.get("nativeContext"))
        if (
            isinstance(context_maximum, bool)
            or not isinstance(context_maximum, int)
            or context_maximum < self.policy.mtplx.mtplx_long_context_minimum
        ):
            return None
        scanned_fingerprint = str(capability.get("benchmarkModelFingerprint") or "")
        current_fingerprint = self.model_artifact_fingerprint(model_path, config)
        if (
            re.fullmatch(r"[0-9a-f]{64}", scanned_fingerprint) is None
            or re.fullmatch(r"[0-9a-f]{64}", current_fingerprint) is None
            or not secrets.compare_digest(scanned_fingerprint, current_fingerprint)
        ):
            return None
        receipt: dict[str, Any] = {
            "version": self.policy.mtplx.mtplx_long_context_2111_contract_version,
            "backend": "mtplx",
            "route": self.policy.mtplx.mtplx_long_context_2111_route,
            "runtimeVersion": version,
            "modelFingerprint": current_fingerprint,
            "modelPath": str(model_path),
            "modelType": text_type,
            "geometry": geometry,
            "minimumContext": self.policy.mtplx.mtplx_long_context_minimum,
            "requiredProfile": "turbo",
            "requiredAcceleration": "mtp",
            "environment": dict(self.policy.mtplx.mtplx_long_context_candidate_env),
            "baselineEnvironment": dict(self.policy.mtplx.mtplx_long_context_baseline_env),
            "allowSwap": "0",
            "growthReserve": "absent",
        }
        receipt["contractId"] = hashlib.sha256(json.dumps(
            receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")).hexdigest()
        return receipt


    def _mtplx_long_context_capability(self, 
        receipt: dict[str, Any] | None, runtime_version: str,
    ) -> dict[str, Any]:
        ready = isinstance(receipt, dict)
        return {
            "contractVersion": self.policy.mtplx.mtplx_long_context_2111_contract_version,
            "ready": ready,
            "routeId": self.policy.mtplx.mtplx_long_context_2111_route,
            "contractId": str(receipt.get("contractId")) if ready else None,
            "minimumContext": self.policy.mtplx.mtplx_long_context_minimum,
            "requiredProfile": "turbo",
            "requiredAcceleration": "mtp",
            "runtimeVersion": (
                "2.11.1"
                if self.mtplx_exact_2111_runtime(runtime_version)
                else str(runtime_version or "")[:160]
            ),
            "reason": (
                "Ready for an isolated 64K local comparison of the audited MTPLX 2.11.1 dense-27B operators."
                if ready else
                "Requires the exact MTPLX 2.11.1 runtime, verified MTP weights, and the complete non-Ornith Qwen dense-27B geometry."
            ),
        }


    def _mtplx_long_context_capability_matches(self, 
        value: Any, receipt: dict[str, Any],
    ) -> bool:
        if not isinstance(value, dict):
            return False
        receipt_id = receipt.get("contractId")
        unsigned_receipt = copy.deepcopy(receipt)
        unsigned_receipt.pop("contractId", None)
        expected_receipt_id = hashlib.sha256(json.dumps(
            unsigned_receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")).hexdigest()
        if (
            not isinstance(receipt_id, str)
            or not secrets.compare_digest(receipt_id, expected_receipt_id)
            or receipt.get("version") != self.policy.mtplx.mtplx_long_context_2111_contract_version
            or receipt.get("backend") != "mtplx"
            or receipt.get("route") != self.policy.mtplx.mtplx_long_context_2111_route
            or not self.mtplx_exact_2111_runtime(receipt.get("runtimeVersion"))
            or receipt.get("geometry") != self.policy.mtplx.mtplx_long_context_dense_geometry
            or receipt.get("environment") != self.policy.mtplx.mtplx_long_context_candidate_env
            or receipt.get("baselineEnvironment") != self.policy.mtplx.mtplx_long_context_baseline_env
            or receipt.get("allowSwap") != "0"
            or receipt.get("growthReserve") != "absent"
        ):
            return False
        # Direct model-free contract tests use the full receipt. Scanner output
        # exposes only the compact public capability schema.
        route = value.get("routeId", value.get("route"))
        version = value.get("contractVersion", value.get("version"))
        ready = value.get("ready", True)
        contract_id = value.get("contractId")
        return bool(
            ready is True
            and version == self.policy.mtplx.mtplx_long_context_2111_contract_version
            and route == self.policy.mtplx.mtplx_long_context_2111_route
            and isinstance(contract_id, str)
            and secrets.compare_digest(contract_id, receipt_id)
            and self.mtplx_exact_2111_runtime(value.get("runtimeVersion"))
            and self.values.semantic_version_key(str(value.get("runtimeVersion") or ""))
            == self.values.semantic_version_key(str(receipt["runtimeVersion"]))
            and value.get("minimumContext") == self.policy.mtplx.mtplx_long_context_minimum
            and value.get("requiredProfile") == "turbo"
            and value.get("requiredAcceleration") == "mtp"
            and (
                "environment" not in value
                or value.get("environment") == self.policy.mtplx.mtplx_long_context_candidate_env
            )
            and (
                "baselineEnvironment" not in value
                or value.get("baselineEnvironment") == self.policy.mtplx.mtplx_long_context_baseline_env
            )
        )


    def lmstudio_model_load_key_index(self, 
        index_path: Path | None = None,
        catalog_root: Path | None = None,
    ) -> dict[str, str]:
        """Map resolved LM Studio model folders to canonical CLI load keys.

        LM Studio's current MLX catalog can expose a default identifier such as
        ``qwen3.8-27b-mlx@6bit`` while retaining a case-preserved Hub folder name.
        The CLI lookup is not guaranteed to accept that folder spelling. Reading
        this local index is side-effect free; malformed or out-of-catalog entries
        are ignored and scanning retains its portable lowercase fallback.
        """
        root = (catalog_root or (Path.home() / ".lmstudio" / "models")).expanduser()
        source = index_path or (Path.home() / ".lmstudio" / ".internal" / "model-index-cache.json")
        raw = self.io.read_json(source)
        models = raw.get("models") if isinstance(raw, dict) else None
        if not isinstance(models, list):
            return {}
        try:
            resolved_root = root.resolve(strict=False)
        except (OSError, RuntimeError):
            return {}
        result: dict[str, str] = {}
        for item in models:
            if not isinstance(item, dict):
                continue
            identifier = item.get("defaultIdentifier")
            folder = item.get("concreteModelDirAbsolutePath")
            if (
                not isinstance(identifier, str)
                or not 0 < len(identifier) <= 512
                or any(ord(char) < 32 for char in identifier)
                or not isinstance(folder, str)
                or not folder
            ):
                continue
            try:
                catalog_path = Path(folder).expanduser()
                catalog_path.relative_to(root)
                resolved_path = catalog_path.resolve(strict=False)
                resolved_path.relative_to(resolved_root)
            except (OSError, RuntimeError, ValueError):
                # A normal in-catalog symlink may resolve outside the catalog. It
                # is still owned by this exact indexed catalog entry, so retain the
                # resolved alias only after the unresolved path passed containment.
                try:
                    catalog_path.relative_to(root)
                    resolved_path = catalog_path.resolve(strict=False)
                except (OSError, RuntimeError, ValueError):
                    continue
            result[str(resolved_path)] = identifier
        return result


    def _uzu_registry_operational_contract(self, entry: Any) -> dict[str, Any]:
        """Extract only registry fields that can change model/runtime interpretation."""
        if not isinstance(entry, dict):
            return {}
        encoding = entry.get("encoding")
        family = entry.get("family")
        family_vendor = family.get("vendor") if isinstance(family, dict) else None
        properties = entry.get("properties")
        quantization = entry.get("quantization")
        quantization_vendor = (
            quantization.get("vendor") if isinstance(quantization, dict) else None
        )
        registry = entry.get("registry")
        specializations = entry.get("specializations")
        return {
            "encoding": {
                "name": encoding.get("name"), "type": encoding.get("type"),
            } if isinstance(encoding, dict) else None,
            "family": {
                "id": family.get("id"),
                "vendor": family_vendor.get("id") if isinstance(family_vendor, dict) else None,
            } if isinstance(family, dict) else None,
            "properties": {
                "id": properties.get("id"), "size": properties.get("size"),
                "version": properties.get("version"),
            } if isinstance(properties, dict) else None,
            "quantization": {
                "bits_per_weight": quantization.get("bits_per_weight"),
                "id": quantization.get("id"), "method": quantization.get("method"),
                "vendor": (
                    quantization_vendor.get("id")
                    if isinstance(quantization_vendor, dict) else None
                ),
            } if isinstance(quantization, dict) else None,
            "registry": registry.get("id") if isinstance(registry, dict) else None,
            "specializations": copy.deepcopy(specializations),
        }


    def _uzu_registry_entry(self) -> tuple[dict[str, Any] | None, str | None]:
        """Read only the pinned Mirai catalog entry from a bounded local registry."""
        path = self.paths.uzu_registry_path().expanduser()
        try:
            details = path.lstat()
            if path.is_symlink() or not stat.S_ISREG(details.st_mode):
                return None, "Mirai's local registry must be a regular file."
            if not 0 < details.st_size <= self.policy.uzu.uzu_model_registry_max_bytes:
                return None, "Mirai's local registry exceeds the launcher's metadata limit."
            value = json.loads(path.read_bytes())
        except (OSError, ValueError, UnicodeError):
            return None, "Mirai's local registry is missing or invalid."
        if not isinstance(value, list) or len(value) > self.policy.uzu.uzu_model_registry_max_entries:
            return None, "Mirai's local registry has an unsupported shape."
        matches = [
            item for item in value
            if isinstance(item, dict) and item.get("id") == self.policy.uzu.uzu_model_registry_id
        ]
        if len(matches) != 1:
            return None, "The pinned Qwen3.6 Uzu entry is missing or duplicated in Mirai's registry."
        entry = matches[0]
        accessibility = entry.get("accessibility")
        reference = accessibility.get("reference") if isinstance(accessibility, dict) else None
        repository = reference.get("repository") if isinstance(reference, dict) else None
        backends = entry.get("backends")
        uzu_backends = [
            item for item in backends
            if isinstance(item, dict) and item.get("id") == "uzu"
        ] if isinstance(backends, list) else []
        uzu_backend = uzu_backends[0] if len(uzu_backends) == 1 else None
        if (
            not isinstance(accessibility, dict)
            or accessibility.get("type") != "local"
            or not isinstance(reference, dict)
            or reference.get("type") != "mirai"
            or reference.get("toolchain_version") != self.policy.uzu.uzu_model_toolchain_version
            or not isinstance(repository, dict)
            or repository.get("identifier") != self.policy.uzu.uzu_model_repository
            or repository.get("commit_hash") != self.policy.uzu.uzu_model_commit
            or repository.get("paths") is not None
            or not isinstance(backends, list)
            or len(backends) != 1
            or not isinstance(uzu_backend, dict)
            or uzu_backend.get("version") != self.policy.uzu.uzu_model_toolchain_version
        ):
            return None, "The installed Mirai catalog entry no longer matches the pinned Uzu model contract."
        if self._uzu_registry_operational_contract(entry) != self.policy.uzu.uzu_model_registry_operational_contract:
            return None, (
                "The installed Mirai catalog changed the pinned model's encoding, "
                "quantization, family, size, registry, or chat specialization."
            )
        files = reference.get("files")
        if not isinstance(files, list) or not 0 < len(files) <= self.policy.uzu.uzu_model_manifest_max_files:
            return None, "The pinned Mirai model manifest has an unsupported file list."
        expected = {
            name: {"size": size, "crc": crc}
            for name, size, crc in self.policy.uzu.uzu_model_file_manifest
        }
        observed: dict[str, dict[str, Any]] = {}
        total = 0
        for item in files:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                return None, "The pinned Mirai model manifest contains invalid file metadata."
            name = item["name"]
            relative = PurePosixPath(name)
            if relative.is_absolute() or not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
                return None, "The pinned Mirai model manifest contains an unsafe file path."
            size = item.get("size")
            hashes = item.get("hashes")
            crc_values = [
                value.get("value") for value in hashes
                if isinstance(value, dict) and value.get("method") == "crc32c"
            ] if isinstance(hashes, list) else []
            url = str(item.get("url") or "")
            if (
                name in observed
                or isinstance(size, bool) or not isinstance(size, int) or size <= 0
                or len(crc_values) != 1 or not isinstance(crc_values[0], str)
                or not url.startswith("https://assets.trymirai.com/")
            ):
                return None, "The pinned Mirai model manifest contains invalid size, hash, or source metadata."
            total += size
            observed[name] = {"size": size, "crc": crc_values[0]}
        if observed != expected or total > self.policy.uzu.uzu_model_manifest_max_bytes:
            return None, "The installed Mirai manifest differs from the launcher's pinned Qwen3.6 file set."
        return copy.deepcopy(entry), None


    def _uzu_offline_catalog(self, cache: dict[str, Any]) -> dict[str, Any]:
        """Adapt the verified legacy entry to Uzu 0.5.23's local-only v2 catalog.

        Filesystem sources bypass the native downloader. The launcher still checks
        every original receipt and pinned SHA-256 before permitting this path.
        """
        if cache.get("ready") is not True or not isinstance(cache.get("registryEntry"), dict):
            raise ValueError("Verified Uzu model metadata is required for offline startup.")
        model = copy.deepcopy(cache["registryEntry"])
        model["accessibility"] = {
            "type": "on_device",
            "source": {"type": "filesystem", "path": str(Path(cache["path"]).resolve(strict=True))},
        }
        return {"version": 2, "models": [{"model": model, "files": None}]}


    def _validated_uzu_offline_catalog(self, cache: dict[str, Any]) -> str:
        path = self.paths.uzu_resolved_models_path().expanduser()
        try:
            details = path.lstat()
            parent = path.parent.lstat()
            if (
                path.is_symlink() or not stat.S_ISREG(details.st_mode)
                or details.st_uid != os.getuid() or details.st_mode & 0o022
                or path.parent.is_symlink() or not stat.S_ISDIR(parent.st_mode)
                or parent.st_uid != os.getuid() or parent.st_mode & 0o022
                or not 0 < details.st_size <= self.policy.uzu.uzu_model_registry_max_bytes
            ):
                raise ValueError("unsafe catalog")
            payload = path.read_bytes()
            if json.loads(payload) != self._uzu_offline_catalog(cache):
                raise ValueError("different catalog")
        except (OSError, ValueError, UnicodeError) as error:
            raise ValueError(
                "Uzu's offline catalog is missing or differs from the verified local model. "
                "Existing catalog data has not been overwritten."
            ) from error
        return hashlib.sha256(payload).hexdigest()


    def _ensure_uzu_offline_catalog(self, cache: dict[str, Any]) -> None:
        """Create missing metadata during explicit launch only; never replace a catalog."""
        payload = json.dumps(self._uzu_offline_catalog(cache), sort_keys=True).encode("utf-8")
        path = self.paths.uzu_resolved_models_path().expanduser()
        parent = path.parent.lstat()
        if (
            path.parent.is_symlink() or not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != os.getuid() or parent.st_mode & 0o022
        ):
            raise ValueError("Uzu's offline catalog directory is unsafe.")
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            self._validated_uzu_offline_catalog(cache)
            return
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        self._validated_uzu_offline_catalog(cache)


    def _uzu_model_cache_contract(self) -> dict[str, Any] | None:
        """Validate Mirai's receipts and pinned file bytes without loading model code."""
        model_root = self.paths.uzu_cache_root().expanduser()
        model_identifier_path = model_root / self.policy.uzu.uzu_model_registry_id.replace(":", "-")
        model_path = model_identifier_path / self.policy.uzu.uzu_model_toolchain_version
        try:
            if not model_path.exists():
                return None
            root_details = model_root.lstat()
            identifier_details = model_identifier_path.lstat()
            model_details = model_path.lstat()
            if (
                model_root.is_symlink() or model_identifier_path.is_symlink() or model_path.is_symlink()
                or not stat.S_ISDIR(root_details.st_mode)
                or not stat.S_ISDIR(identifier_details.st_mode)
                or not stat.S_ISDIR(model_details.st_mode)
            ):
                return {
                    "present": True, "ready": False, "path": str(model_path),
                    "reason": "The Mirai model cache must use ordinary local directories.",
                }
            resolved_root = model_root.resolve(strict=True)
            resolved_model = model_path.resolve(strict=True)
            resolved_model.relative_to(resolved_root)
        except (OSError, ValueError):
            return {
                "present": True, "ready": False, "path": str(model_path),
                "reason": "The Mirai model cache moved outside its expected local directory.",
            }

        entry, registry_error = self._uzu_registry_entry()
        if registry_error:
            return {
                "present": True, "ready": False, "path": str(resolved_model),
                "reason": registry_error,
            }

        completed_bytes = 0
        total_bytes = sum(size for _name, size, _crc in self.policy.uzu.uzu_model_file_manifest)
        file_identity: list[dict[str, Any]] = []
        problems: list[str] = []
        for name, expected_size, expected_crc in self.policy.uzu.uzu_model_file_manifest:
            relative = PurePosixPath(name)
            file_path = resolved_model.joinpath(*relative.parts)
            receipt_path = Path(str(file_path) + ".crc")
            try:
                resolved_file = file_path.resolve(strict=False)
                resolved_receipt = receipt_path.resolve(strict=False)
                resolved_file.relative_to(resolved_model)
                resolved_receipt.relative_to(resolved_model)
                parent = resolved_model
                for part in relative.parts[:-1]:
                    parent = parent / part
                    parent_details = parent.lstat()
                    if parent.is_symlink() or not stat.S_ISDIR(parent_details.st_mode):
                        raise OSError("unsafe model subdirectory")
                details = file_path.lstat()
                if file_path.is_symlink() or not stat.S_ISREG(details.st_mode):
                    raise OSError("not a regular file")
                if details.st_size != expected_size:
                    problems.append(f"{name} has an unexpected size")
                    continue
                receipt_details = receipt_path.lstat()
                if (
                    receipt_path.is_symlink() or not stat.S_ISREG(receipt_details.st_mode)
                    or not 0 < receipt_details.st_size <= 4_096
                ):
                    raise OSError("invalid receipt")
                receipt = json.loads(receipt_path.read_bytes())
                if (
                    not isinstance(receipt, dict)
                    or receipt.get("version") != 1
                    or receipt.get("file_size") != expected_size
                    or receipt.get("crc") != expected_crc
                ):
                    problems.append(f"{name} has an invalid completion receipt")
                    continue
                expected_sha256 = self.policy.uzu.uzu_model_file_sha256.get(name)
                if (
                    not isinstance(expected_sha256, str)
                    or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
                    or not self.artifacts.cached_regular_file_sha256_matches(file_path, expected_sha256)
                ):
                    problems.append(f"{name} failed its pinned SHA-256 check")
                    continue
                completed_bytes += expected_size
                file_identity.append({
                    "name": name,
                    "size": expected_size,
                    "crc32c": expected_crc,
                    "sha256": expected_sha256,
                    "device": int(details.st_dev),
                    "inode": int(details.st_ino),
                    "modified": int(details.st_mtime_ns),
                    "changed": int(details.st_ctime_ns),
                })
            except (OSError, ValueError, UnicodeError):
                partial = file_path.with_suffix(".part")
                try:
                    partial_details = partial.lstat()
                    if not partial.is_symlink() and stat.S_ISREG(partial_details.st_mode):
                        completed_bytes += min(expected_size, max(0, int(partial_details.st_size)))
                except OSError:
                    pass
                problems.append(f"{name} is incomplete")

        active_markers: list[str] = []
        try:
            for root, directories, filenames in os.walk(resolved_model, followlinks=False):
                directories[:] = [
                    name for name in directories
                    if not (Path(root) / name).is_symlink()
                ]
                for filename in filenames:
                    if filename.endswith((".part", ".lock")):
                        active_markers.append(str((Path(root) / filename).relative_to(resolved_model)))
        except OSError:
            problems.append("the model cache cannot be inspected completely")
        if active_markers:
            problems.append("the Mirai downloader is still writing this model")

        ready = not problems and completed_bytes == total_bytes
        config: dict[str, Any] = {}
        if ready:
            try:
                config_value = json.loads((resolved_model / "config.json").read_bytes())
                if not isinstance(config_value, dict):
                    raise ValueError("config must be an object")
                config = config_value
            except (OSError, ValueError, UnicodeError):
                ready = False
                problems.append("config.json is invalid")

        manifest_identity = {
            "schema": 2,
            "registryId": self.policy.uzu.uzu_model_registry_id,
            "repository": self.policy.uzu.uzu_model_repository,
            "commit": self.policy.uzu.uzu_model_commit,
            "toolchain": self.policy.uzu.uzu_model_toolchain_version,
            "registryOperationalContract": self._uzu_registry_operational_contract(entry),
            "files": file_identity if ready else [],
        }
        fingerprint = (
            hashlib.sha256(json.dumps(
                manifest_identity, sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")).hexdigest()
            if ready else ""
        )
        progress = min(100.0, max(0.0, completed_bytes * 100.0 / total_bytes))
        reason = (
            "Pinned Mirai catalog files passed receipt and SHA-256 verification."
            if ready else
            ("Downloading Qwen3.6 Uzu files" if active_markers else problems[0])
        )
        return {
            "present": True,
            "ready": ready,
            "path": str(resolved_model),
            "reason": reason,
            "problems": problems[:16],
            "activeMarkers": active_markers[:16],
            "completedBytes": completed_bytes,
            "totalBytes": total_bytes,
            "progressPercent": round(progress, 1),
            "fingerprint": fingerprint,
            "manifestIdentity": manifest_identity,
            "registryEntry": entry,
            "config": config,
        }


    def _uzu_model_geometry(self, config: dict[str, Any]) -> tuple[dict[str, Any], int]:
        decoder = config.get("decoder_config") if isinstance(config, dict) else None
        transformer = decoder.get("transformer_config") if isinstance(decoder, dict) else None
        layers = transformer.get("layer_configs") if isinstance(transformer, dict) else None
        if not isinstance(layers, list) or not layers or len(layers) > 512:
            return {"ready": False, "layerSource": "uzu-config-invalid"}, 0
        attention: list[dict[str, Any]] = []
        native_context = 0
        for layer in layers:
            if not isinstance(layer, dict):
                return {"ready": False, "layerSource": "uzu-config-invalid"}, 0
            mixer = layer.get("mixer_config")
            if not isinstance(mixer, dict):
                return {"ready": False, "layerSource": "uzu-config-invalid"}, 0
            if mixer.get("type") == "AttentionConfig":
                attention.append(mixer)
                rope = layer.get("rope_config")
                value = rope.get("max_sequence_length") if isinstance(rope, dict) else None
                if isinstance(value, int) and not isinstance(value, bool):
                    native_context = max(native_context, value)
        if not attention:
            return {"ready": False, "layerSource": "uzu-config-invalid"}, native_context
        first = attention[0]
        kv_heads = first.get("num_groups")
        head_dim = first.get("head_dim")
        attention_heads = first.get("num_heads")
        consistent = all(
            item.get("num_groups") == kv_heads
            and item.get("head_dim") == head_dim
            and item.get("num_heads") == attention_heads
            for item in attention
        )
        ready = bool(
            consistent
            and isinstance(kv_heads, int) and not isinstance(kv_heads, bool) and kv_heads > 0
            and isinstance(head_dim, int) and not isinstance(head_dim, bool) and head_dim > 0
            and isinstance(attention_heads, int) and not isinstance(attention_heads, bool) and attention_heads > 0
        )
        return {
            "ready": ready,
            "layers": len(layers),
            "fullAttentionLayers": len(attention),
            "attentionHeads": attention_heads if ready else None,
            "kvHeads": kv_heads if ready else None,
            "headDimension": head_dim if ready else None,
            "layerSource": "uzu-layer-configs",
        }, native_context


    def uzu_model_records(self, 
        benchmark_records: list[dict[str, Any]], machine_fingerprint: str | None = None,
    ) -> list[dict[str, Any]]:
        """Expose only locally present, receipt-complete Uzu catalog artifacts."""
        cache = self._uzu_model_cache_contract()
        if cache is None:
            return []
        runtime = self.runtime.uzu_runtime_contract(self.runtime.selected_binary("mirai"))
        model_ready = cache.get("ready") is True
        runtime_ready = runtime.get("ready") is True
        config = cache.get("config") if isinstance(cache.get("config"), dict) else {}
        geometry, architecture_context = self._uzu_model_geometry(config)
        generation = config.get("generation_config") if isinstance(config, dict) else None
        generation = generation if isinstance(generation, dict) else {}
        default_sampling: dict[str, int | float] = {}
        for key in SUPPORTED_SAMPLING_FIELDS:
            if key not in generation:
                continue
            try:
                default_sampling.update(canonicalize_sampling({key: generation[key]}))
            except SamplingContractError:
                continue
        listener_protected = self.runtime.uzu_listener_protection_ready(runtime)
        qualification_system_contract = {
            "osReserveBytes": max(
                self.policy.uzu.session_os_reserve_min_bytes,
                round(self.runtime.physical_memory_bytes() * self.policy.uzu.session_os_reserve_fraction),
            ),
            "sandboxProfileSha256": self.policy.uzu.uzu_sandbox_profile_sha256,
            "rawListenerProtected": listener_protected,
            "nativeBoundaryContractId": runtime.get("nativeBoundaryContractId"),
            "nativeBearerAuthentication": runtime.get("nativeBearerAuthentication") is True,
            "oneUseApiKeyFile": runtime.get("oneUseApiKeyFile") is True,
            "nativeContextLimit": runtime.get("nativeContextLimit") is True,
            "nativeOutputLimit": runtime.get("nativeOutputLimit") is True,
        }
        fingerprint = str(cache.get("fingerprint") or "")
        runtime_version = self.runtime.command_version(self.runtime.selected_binary("mirai"))
        runnable = bool(
            model_ready and runtime_ready and listener_protected
            and geometry.get("ready") is True
        )
        if not model_ready:
            route_reason = str(cache.get("reason") or "The Uzu model download is incomplete.")
        elif not runtime_ready:
            route_reason = str(runtime.get("reason") or "A verified memory-safe Uzu runtime is required.")
        elif not listener_protected:
            route_reason = (
                "The hardened Uzu raw-listener authentication boundary is unavailable."
            )
        elif geometry.get("ready") is not True:
            route_reason = "The Uzu config does not expose a complete bounded attention geometry."
        else:
            route_reason = "Pinned local Qwen3.6 target and bundled DFlash draft are ready for Uzu Weaver decoding."
        uzu_capability: dict[str, Any] = {
            "runnable": runnable,
            "reason": route_reason,
            "mtp": False,
            "mtpReason": "Uzu owns its bundled DFlash draft and Weaver verification tree; no MTP toggle is exposed.",
            "dflash": False,
            "dflashVersion": None,
            "dflashReason": "DFlash + Weaver is fixed inside this Uzu artifact rather than exposed as a launcher toggle.",
            "runtimeManagedAcceleration": "DFlash + Weaver",
            "runtimeManagedAccelerationReady": runnable,
            "preferredAcceleration": "off",
            "fallbackAcceleration": "off",
            "depth": 1,
            "depthMax": 1,
            "kv": False,
            # This first qualified launcher route requires the packaged reasoning
            # path. Keep the lower-level relay's disabled spelling available for a
            # future separately qualified contract, but do not advertise it here.
            "agentReasoning": ["auto"],
            "codexReasoning": ["auto"],
            # The current Uzu server accepts only a subset of the launcher's
            # sampling contract and silently ignores seed and penalty controls.
            # Expose model defaults rather than pretending all visible controls
            # can be preserved end to end.
            "customSampling": False,
            "implicitSamplingDefaultsVerified": True,
            "samplingReason": (
                "This Uzu server can preserve the packaged model defaults, but not "
                "the launcher's complete custom sampling contract."
            ),
            "contextWindows": list(self.policy.uzu.uzu_safe_context_windows),
            "contextMaximum": max(self.policy.uzu.uzu_safe_context_windows),
            "runtimeVersion": runtime_version,
            "runtimeIdentity": copy.deepcopy(runtime),
            "qualificationSystemContract": qualification_system_contract,
            "modelRegistryId": self.policy.uzu.uzu_model_registry_id,
            "modelRepository": self.policy.uzu.uzu_model_repository,
            "modelCommit": self.policy.uzu.uzu_model_commit,
            "modelToolchainVersion": self.policy.uzu.uzu_model_toolchain_version,
            "modelCacheContract": {
                key: copy.deepcopy(cache.get(key))
                for key in (
                    "ready", "path", "reason", "problems", "completedBytes",
                    "totalBytes", "progressPercent", "fingerprint", "manifestIdentity",
                )
            },
            "benchmarkModelFingerprint": fingerprint,
            "localBenchmark": None,
            "localBenchmarks": [],
            "benchmarkHistoryCount": 0,
        }
        if model_ready and fingerprint:
            history = self.evidence.matching_benchmarks(
                benchmark_records, "uzu", fingerprint, runtime_version,
                uzu_capability, machine_fingerprint or None,
            )
            benchmarks = self.evidence.latest_by_identity(history)
            uzu_capability["localBenchmarks"] = benchmarks
            uzu_capability["benchmarkHistoryCount"] = len(history)
            if benchmarks:
                uzu_capability["localBenchmark"] = benchmarks[-1]
                uzu_capability["preferredAccelerationSource"] = "local-benchmark"

        uzu_capability["piTransportVersion"] = self.runtime.command_version(self.runtime.selected_binary("pi")) if runnable else None
        uzu_capability["clientSupport"] = {"pi": self.surfaces.resolved_support("uzu", "pi", uzu_capability)}

        unavailable: dict[str, dict[str, Any]] = {}
        for backend_id, descriptor in self.policy.engines.items():
            if backend_id == "uzu":
                unavailable[backend_id] = uzu_capability
                continue
            unavailable[backend_id] = {
                "runnable": False,
                "reason": f"This is a Mirai/Uzu-native artifact, not a {descriptor.label} model folder.",
                "mtp": False, "mtpReason": "No equivalent artifact is asserted.",
                "dflash": False, "dflashVersion": None,
                "dflashReason": "No equivalent artifact is asserted.",
                "kv": False, "preferredAcceleration": "off", "fallbackAcceleration": "off",
                "depth": 1, "depthMax": 1,
                "agentReasoning": ["auto"], "codexReasoning": ["auto"],
                "runtimeVersion": "Not applicable",
                "benchmarkModelFingerprint": fingerprint,
                "localBenchmark": None, "localBenchmarks": [], "benchmarkHistoryCount": 0,
            }

        total_weights = sum(
            size for name, size, _crc in self.policy.uzu.uzu_model_file_manifest
            if name.endswith("model.safetensors")
        )
        progress = float(cache.get("progressPercent") or 0.0)
        if model_ready and not runtime_ready:
            status = "Downloaded · safe Uzu update required"
        elif model_ready:
            status = "Ready"
        elif cache.get("activeMarkers"):
            status = f"Downloading · {progress:.1f}%"
        else:
            status = str(cache.get("reason") or "Incomplete")
        model_id = "uzu-" + hashlib.sha256(
            self.policy.uzu.uzu_model_registry_id.encode("utf-8")
        ).hexdigest()[:24]
        return [{
            "id": model_id,
            "name": "Qwen3.6 27B · Uzu DFlash + Weaver",
            "path": str(cache.get("path") or ""),
            "artifact": str(cache.get("path") or ""),
            "origins": ["Mirai local catalog"],
            "format": "Uzu · Mirai-M",
            "architecture": "Qwen3.6 27B · hybrid DeltaNet/attention",
            "modelType": "qwen3.6-uzu",
            "rootModelType": "qwen3.6-uzu",
            "textModelType": "qwen3.6-uzu",
            # Preserve the architecture's advertised capacity in the catalog while
            # keeping the independently enforced first-run choices in
            # capability.contextWindows.  Conflating those two values makes a
            # safety cap look like a limitation of the model itself.
            "nativeContext": architecture_context or 262_144,
            "architectureNativeContext": architecture_context or 262_144,
            "contextWindows": list(self.policy.uzu.uzu_safe_context_windows),
            "quantization": "Mirai-M 4-bit",
            "size": total_weights,
            "sizeLabel": self.values.display_size(total_weights),
            "memoryGeometry": geometry,
            "mtpSidecarSize": 0,
            "ready": model_ready,
            "status": status,
            "mtp": {"declared": False, "integrated": False, "sidecar": False},
            "templateReasoningEfforts": [],
            "defaultSampling": default_sampling,
            "lmKey": self.policy.uzu.uzu_model_registry_id,
            "uzuNative": True,
            "uzuModelCache": copy.deepcopy(uzu_capability["modelCacheContract"]),
            "backends": unavailable,
        }]


    def scan_models(self) -> list[dict[str, Any]]:
        records: dict[str, dict[str, Any]] = {}
        roots = self.model_roots()
        preferred_root_spellings = self._preferred_scan_root_spellings(roots)
        lmstudio_load_keys = self.lmstudio_model_load_key_index()
        benchmark_records = self.evidence.load_benchmarks()
        ane_tuning_records = self.evidence.load_ane_records()
        machine_fingerprint = self.evidence.hardware_fingerprint() if benchmark_records or ane_tuning_records else ""
        installed_memory = self.runtime.physical_memory_bytes()
        for uzu_model in self.uzu_model_records(
            benchmark_records, machine_fingerprint or None,
        ):
            records[f"uzu:{uzu_model['id']}"] = uzu_model
        discovered: dict[tuple[int, int], dict[str, Any]] = {}
        for origin, root in roots:
            scanned_root = root.expanduser().absolute()
            root_identity = self._physical_directory_identity(scanned_root)
            preferred_root = preferred_root_spellings.get(root_identity) if root_identity else None
            for candidate in self.candidate_dirs(scanned_root):
                candidate_identity = self._physical_directory_identity(candidate)
                if candidate_identity is None:
                    continue
                real = self._preferred_physical_candidate_path(
                    candidate, scanned_root, preferred_root, candidate_identity,
                )
                if real is None:
                    continue
                item = discovered.setdefault(
                    candidate_identity, {"path": real, "origins": []},
                )
                if origin not in item["origins"]:
                    item["origins"].append(origin)

        slotstream_install = slotstream_runtime.discover(self.runtime.selected_binary("slotstream"))
        if slotstream_install and slotstream_install.get("ready"):
            shared_path = Path(slotstream_install["modelPath"]).resolve()
            identity = self._physical_directory_identity(shared_path)
            if identity is not None:
                discovered.setdefault(identity, {"path": shared_path, "origins": ["Slotstream shared checkpoint"]})

        omlx_version = self.runtime.command_version(self.runtime.selected_binary("omlx"))
        lmstudio_cli_version = self.runtime.command_version(self.runtime.selected_binary("lms"))
        lmstudio_packs = self.runtime.lmstudio_runtime_packs()
        lmstudio_app = self.runtime.app_status("lms")
        lmstudio_app_version = self.runtime.plist_version(Path("/Applications/LM Studio.app/Contents/Info.plist"))
        lmstudio_version = self.runtime.lmstudio_runtime_identity(
            lmstudio_cli_version, lmstudio_app_version, lmstudio_packs,
        )
        lmstudio_mtp_runtime = self.runtime.lmstudio_mtp_load_supported(self.runtime.selected_binary("lms"))
        lmstudio_assistant_runtime = self.lmstudio_assistant_drafter_runtime_contract(
            self.runtime.selected_binary("lms"), lmstudio_cli_version, lmstudio_app,
            lmstudio_packs, self.runtime.lmstudio_backend_preference(),
        )
        lmstudio_gguf_models = self.lmstudio_gguf_catalog()
        lmstudio_draft_receipts = self.lmstudio_draft_compatibility_receipts()
        mtplx_version = self.runtime.command_version(self.runtime.selected_binary("mtplx"))
        swiftlm_version = self.runtime.command_version(self.runtime.selected_binary("swiftlm"))
        mference_version = self.runtime.command_version(self.runtime.selected_binary("mference"))
        whallm_version = self.runtime.command_version(self.runtime.selected_binary("whallm"))
        llamacpp_runtime = self.runtime.llamacpp_runtime_contract(self.runtime.selected_binary("llamacpp"))
        llamacpp_version = str(llamacpp_runtime.get("version") or "Not installed")
        freetoken_native_binary = self.runtime.selected_binary("freetoken_native")
        freetoken_native_version = self.runtime.command_version(freetoken_native_binary)
        dflash2_runtime = self.runtime.omlx_supports_dflash2(omlx_version)
        dflash2_runtime_recommended = self.runtime.omlx_recommended_dflash_runtime(omlx_version)
        ane_runtime_version_ready = self.runtime.omlx_version_at_least(
            omlx_version, self.policy.ane.ane_tuner_minimum_runtime,
        )
        ane_kernel = self.runtime.omlx_kernel_status(self.runtime.selected_binary("omlx"))
        ane_runtime_ready = bool(
            ane_runtime_version_ready and ane_kernel.get("ready")
        )
        dflash2_candidates: list[dict[str, Any]] = []
        dflash2_drafts: list[dict[str, Any]] = []
        for item in discovered.values():
            real = item["path"]
            config = self.io.read_json(real / "config.json")
            if real.name.endswith(".gturbo"):
                manifest = self.io.read_json(real / "manifest.json")
                tokenizer_config = self.io.read_json(real / "tokenizer" / "config.json")
                config = {**tokenizer_config, **manifest}
            if not self.is_dflash2_draft(real, config):
                continue
            ready, status, size = self.weight_completeness(real, config)
            complete = ready and self.dflash2_draft_complete(real, config)
            candidate = {
                "path": str(real), "config": config, "complete": complete,
                "status": "Ready" if complete else status, "size": size,
            }
            dflash2_candidates.append(candidate)
            if complete:
                dflash2_drafts.append(candidate)

        for item in discovered.values():
            if not isinstance(item, dict):
                continue
            real = item["path"]
            key = str(real)
            config = self.io.read_json(real / "config.json")
            if real.name.endswith(".gturbo"):
                # Mference bundles keep their pinned model contract in the bundle
                # manifest rather than a Hugging Face-style root config.  Use the
                # same merged view for admission, fingerprinting, and launch-time
                # revalidation so a scan cannot approve one artifact and later
                # reject the unchanged bundle as stale.
                config = {
                    **self.io.read_json(real / "tokenizer" / "config.json"),
                    **self.io.read_json(real / "manifest.json"),
                }
            # Draft checkpoints are helpers, never standalone target models.
            if self.is_dflash2_draft(real, config):
                continue
            ready, status, weight_bytes = self.weight_completeness(real, config)
            atomic_named_variant = real.name == self.policy.atomic.llamacpp_atomic_variant
            atomic_ple = (
                self.llamacpp_atomic_scan_contract(real)
                if atomic_named_variant else {
                    "ready": False,
                    "reason": "The dedicated llama.cpp route requires the exact pinned AtomicChat GGUF split.",
                }
            )
            if atomic_named_variant:
                # A single >1 MB GGUF is normally a complete standalone model, but
                # this allowlisted variant is an exact 28-shard split.  Bind its
                # library readiness to the parent acquisition receipt so an
                # interrupted nested download is never advertised as Ready.
                ready = atomic_ple.get("ready") is True
                status = (
                    "Ready" if ready else
                    str(atomic_ple.get("reason") or "The pinned 28-shard split is incomplete.")
                )
                if ready:
                    weight_bytes = int(atomic_ple["weightBytes"])
            ggufs = sorted(real.glob("*.gguf"))
            model_tensors = [
                tensor for tensor in real.glob("*.safetensors")
                if tensor.name != "mtp.safetensors" and tensor.stat().st_size > 0
            ]
            fmt = (
                "mference"
                if real.name.endswith(".gturbo") else
                "gguf" if ggufs and not model_tensors else "mlx"
            )
            artifact = ggufs[0] if fmt == "gguf" else real
            context = self.values.deep_get(
                config,
                ("text_config", "max_position_embeddings"),
                ("max_position_embeddings",),
                ("model_max_length",),
            )
            try:
                context = int(context)
                if not 1_024 <= context <= 2_000_000:
                    context = None
            except (TypeError, ValueError):
                context = None
            root_model_type = str(config.get("model_type") or "unknown")
            text_model_type = str(self.values.deep_get(config, ("text_config", "model_type")) or "unknown")
            model_type = text_model_type if text_model_type != "unknown" else root_model_type
            architectures = config.get("architectures") or self.values.deep_get(config, ("text_config", "architectures")) or []
            architecture = str(architectures[0]) if isinstance(architectures, list) and architectures else model_type
            quant = self.values.deep_get(config, ("quantization", "bits"), ("quantization_config", "bits"))
            quantization = f"{quant}-bit" if isinstance(quant, (int, float)) else "From artifact"
            atomic_ple_ready = bool(
                atomic_ple.get("ready") is True
                and atomic_ple.get("currentProcessVerified") is True
                and isinstance(atomic_ple.get("verificationGeneration"), int)
                and atomic_ple.get("verificationGeneration") > 0
            )
            if atomic_ple_ready:
                context = self.policy.atomic.llamacpp_ple_context
                root_model_type = "qwen4exp"
                text_model_type = "qwen4exp"
                model_type = "qwen4exp"
                architecture = "Qwen3.8-Flash-Next · Qwen4Exp"
                quantization = "AD-3.84bpw · IQ4_XS-M64 · SSD-only PLE"
            qwen4_ple = self.artifacts.qwen_ple_profile(real, config, ready and fmt == "mlx", omlx_version)
            expert_offload = self.artifacts.qwen_expert_offload_profile(real, config, qwen4_ple, omlx_version)
            ssd_profile = self.ssd_streaming_model_profile(
                real, config, weight_bytes, installed_memory,
            )
            swiftlm_family_ready, swiftlm_family_reason = self.swiftlm_model_supported(
                real, config, ssd_profile,
            )
            mference_family_ready, mference_family_reason = self.mference_model_supported(
                real, ssd_profile,
            )
            ane_profile = self.ane_quantization_profile(config)
            ane_memory = self.ane_memory_readiness(weight_bytes, installed_memory)
            ane_cpu_profile = self.ane_cpu_sharing_profile(real)
            ane_clone_profile = self.ane_fp16_clone_source_profile(real, config, weight_bytes)
            ane_cpu_memory = self.ane_memory_readiness(weight_bytes, installed_memory, cpu_assist=True)
            ane_ready_to_tune = bool(
                ready and fmt == "mlx" and ane_profile["compatible"]
                and ane_runtime_ready and ane_memory["ready"]
            )
            if not ready or fmt != "mlx":
                ane_reason = "ANE tuning requires a complete MLX checkpoint."
            elif not ane_profile["compatible"]:
                ane_reason = str(ane_profile["reason"])
            elif not ane_runtime_version_ready:
                ane_reason = f"Update {omlx_version} to oMLX {self.policy.ane.ane_tuner_minimum_runtime} or newer before tuning ANE prefill."
            elif not ane_kernel.get("ready"):
                ane_reason = str(
                    ane_kernel.get("reason")
                    or "The selected oMLX installation has no verified native Qwen kernel."
                )
            elif not ane_memory["ready"]:
                ane_reason = str(ane_memory["reason"])
            else:
                ane_reason = "Ready for a temporary GPU baseline and ANE/GPU split measurement."
            ane_cpu_available = bool(
                ane_ready_to_tune
                and ane_cpu_profile["eligible"]
                and ane_cpu_memory["ready"]
            )
            if not ane_cpu_profile["eligible"]:
                ane_cpu_reason = str(ane_cpu_profile["reason"])
            elif not ane_cpu_memory["ready"]:
                ane_cpu_reason = str(ane_cpu_memory["reason"])
            elif not ane_ready_to_tune:
                ane_cpu_reason = "Resolve the standard ANE Tuner checks before adding CPU candidates."
            else:
                ane_cpu_reason = "This separate FP16 clone can include measured CPU-sharing candidates."
            ane_readiness = {
                "ready": ane_ready_to_tune,
                "modelCompatible": bool(ane_profile["compatible"]),
                "modelReason": ane_profile["reason"],
                "quantizationMode": ane_profile["mode"],
                "bits": ane_profile["bits"],
                "groupSize": ane_profile["groupSize"],
                "runtimeReady": ane_runtime_ready,
                "runtimeVersionReady": ane_runtime_version_ready,
                "runtimeDetected": omlx_version,
                "minimumRuntime": self.policy.ane.ane_tuner_minimum_runtime,
                "kernelReady": bool(ane_kernel.get("ready")),
                "kernelState": str(ane_kernel.get("state") or "unverified"),
                "kernelReason": str(ane_kernel.get("reason") or "Native Qwen kernel not verified."),
                "releaseUrl": self.policy.ane.ane_tuner_release_url,
                "memoryReady": bool(ane_memory["ready"]),
                "memory": ane_memory,
                "cpuMemoryReady": bool(ane_cpu_memory["ready"]),
                "cpuMemory": ane_cpu_memory,
                "sequenceLength": self.policy.ane.ane_tuner_sequence_length,
                "repeats": self.policy.ane.ane_tuner_repeats,
                "minimumSpeedupPercent": self.policy.ane.ane_tuner_minimum_speedup_percent,
                "cpuSharingEligible": bool(ane_cpu_profile["eligible"]),
                "cpuSharingAvailable": ane_cpu_available,
                "cpuSharingReason": ane_cpu_reason,
                "cpuFloatDtypes": ane_cpu_profile["floatDtypes"],
                "cpuFloatingTensorCount": ane_cpu_profile["floatingTensorCount"],
                "cpuGateUpScalePairs": ane_cpu_profile["gateUpScalePairs"],
                "cpuDownProjectionEligible": bool(ane_cpu_profile["downProjectionEligible"]),
                "cpuGdnEligible": bool(ane_cpu_profile["gdnEligible"]),
                "cpuProfileFingerprint": ane_cpu_profile["profileFingerprint"],
                "cpuCloneEligible": bool(ane_clone_profile["eligible"]),
                "cpuCloneReason": ane_clone_profile["reason"],
                "cpuCloneSourceUrl": self.policy.ane.ane_fp16_clone_source_url,
                "experimental": True,
                "approximate": True,
                "reason": ane_reason,
            }
            mtp_layers = self.values.deep_get(config, ("text_config", "mtp_num_hidden_layers"), ("mtp_num_hidden_layers",))
            mtp_declared = isinstance(mtp_layers, int) and mtp_layers > 0
            integrated_mtp = mtp_declared and self.checkpoint_has_mtp_weights(real, config)
            sidecar_path = self.mtplx_sidecar_path(real, config)
            sidecar_mtp = sidecar_path.is_file()
            try:
                mtp_sidecar_bytes = sidecar_path.stat().st_size if sidecar_mtp else 0
            except OSError:
                mtp_sidecar_bytes = 0
            runtime = self.io.read_json(real / "mtplx_runtime.json")
            reasoning_efforts = self.template_reasoning_efforts(real)
            default_sampling = self.model_default_sampling(real)
            if atomic_ple_ready:
                # These are the publisher's thinking-mode defaults embedded in the
                # pinned GGUF chat template. Keep the first qualification on model
                # defaults instead of inventing an engine-side sampler.
                reasoning_efforts = ["low", "medium", "xhigh"]
                default_sampling = {"temperature": 1.0, "top_p": 0.95, "top_k": 20}
            lm_reasoning_efforts = [level for level in reasoning_efforts if level in {"low", "medium", "high"}]
            mtplx_verified = self.verified_mtplx_runtime(real, runtime, config)
            mtplx_native_ready = mtplx_verified or bool(
                ready and fmt == "mlx" and runtime and self.native_mtplx_mtp_ready(real, config)
            )
            mtp_depth = runtime.get("mtp_depth_default") if isinstance(runtime.get("mtp_depth_default"), int) else 3
            mtp_depth_max = self.values.safe_int(runtime.get("mtp_depth_max"), 3, 1, 8) if mtplx_native_ready else 1
            # `lms load` resolves LM Studio's canonical/default identifier,
            # not necessarily the case-preserved catalog path. Recent MLX entries
            # may also use `model@6bit` aliases that a folder name cannot recreate.
            canonical_lm_key = lmstudio_load_keys.get(str(real))
            if canonical_lm_key:
                lm_key = canonical_lm_key
                lm_catalogued = True
            else:
                try:
                    lm_relative = real.relative_to(Path.home() / ".lmstudio" / "models")
                except ValueError:
                    lm_key = str(artifact)
                    lm_catalogued = False
                else:
                    derived_lm_key = "/".join(lm_relative.parts[:2]) if len(lm_relative.parts) >= 2 else lm_relative.name
                    lm_key = derived_lm_key.lower()
                    lm_catalogued = True
            lmstudio_assistant_drafter = self.lmstudio_assistant_drafter_readiness(
                real, lmstudio_gguf_models, lmstudio_draft_receipts,
                lmstudio_assistant_runtime,
            )
            qwen4_architecture = self.values.qwen_ple_config(config)
            omlx_artifact_ready = bool(
                ready and fmt == "mlx"
                and (not qwen4_architecture or qwen4_ple.get("supported") is True)
            )
            omlx_mtp = bool(
                omlx_artifact_ready and integrated_mtp and not sidecar_mtp
                and model_type.startswith(("qwen3_5", "qwen3_6", "deepseek_v4", "qwen4_exp"))
            )
            lmstudio_mtp_artifact = bool(
                ready and lm_catalogued and sidecar_mtp and mtplx_verified
            )
            lmstudio_mtp = bool(lmstudio_mtp_runtime and lmstudio_mtp_artifact)
            dflash2_profile = (
                self.dflash2_target_profile(real, config)
                if ready and fmt == "mlx" and not qwen4_architecture else None
            )
            dflash2_candidate = self.matching_dflash2_draft(real, config, dflash2_candidates) if dflash2_profile else None
            dflash2_complete_draft = self.matching_dflash2_draft(real, config, dflash2_drafts) if dflash2_profile else None
            dflash2_draft = dflash2_complete_draft if dflash2_runtime else None
            dflash2_ready = dflash2_draft is not None
            dflash2_pair_id = None
            dflash2_shape = None
            if dflash2_draft:
                dflash2_shape = self.dflash2_draft_shape(dflash2_draft["config"])
                dflash2_pair_id = self.dflash2_pair_fingerprint(
                    real,
                    config,
                    Path(str(dflash2_draft["path"])),
                    dflash2_draft["config"],
                )
            dflash2_default_block = int(dflash2_shape["block_size"]) if dflash2_shape else None
            if dflash2_ready:
                dflash2_reason = "Compatible local DFlash 2 draft detected; choose it manually or add a matching local benchmark before the optimiser selects it."
            elif not dflash2_profile:
                dflash2_reason = "No published DFlash 2 draft matches this target model's family and geometry."
            elif not dflash2_runtime and not dflash2_complete_draft:
                dflash2_reason = (
                    f"Target matches {self.policy.dflash.dflash2_draft_repo}; update oMLX {omlx_version} to "
                    f"{self.policy.dflash.dflash2_recommended_runtime} and download the {self.policy.dflash.dflash2_draft_size_label} draft."
                )
            elif not dflash2_runtime:
                dflash2_reason = (
                    f"Matching draft is installed; update oMLX {omlx_version} to "
                    f"{self.policy.dflash.dflash2_recommended_runtime} to enable DFlash 2."
                )
            elif dflash2_candidate and not dflash2_candidate.get("complete"):
                dflash2_reason = "The matching DFlash 2 draft is present but its weight download is incomplete or invalid."
            elif not dflash2_complete_draft:
                dflash2_reason = (
                    f"Runtime is ready; download the matching {self.policy.dflash.dflash2_draft_size_label} "
                    f"{self.policy.dflash.dflash2_draft_repo} draft."
                )
            else:
                dflash2_reason = "Installed DFlash 2 drafts do not match this target model's family, layer count, and vocabulary."
            dflash2_readiness = {
                "targetCompatible": bool(dflash2_profile),
                "targetReason": (
                    f"Exact {self.policy.dflash.dflash2_draft_repo} geometry match"
                    if dflash2_profile else "No published matching draft"
                ),
                "runtimeReady": dflash2_runtime,
                "runtimeRecommended": dflash2_runtime_recommended,
                "runtimeDetected": omlx_version,
                "minimumRuntime": self.policy.dflash.dflash2_minimum_runtime,
                "recommendedRuntime": self.policy.dflash.dflash2_recommended_runtime,
                "releaseUrl": self.policy.dflash.dflash2_release_url,
                "draftInstalled": dflash2_complete_draft is not None,
                "draftDetected": dflash2_candidate is not None,
                "draftComplete": bool(dflash2_candidate and dflash2_candidate.get("complete")),
                "draftPath": str(dflash2_candidate.get("path")) if dflash2_candidate else None,
                "draftStatus": (
                    str(dflash2_candidate.get("status") or "Detected")
                    if dflash2_candidate else "Not installed"
                ),
                "draftRepo": self.policy.dflash.dflash2_draft_repo,
                "draftUrl": self.policy.dflash.dflash2_draft_url,
                "draftSizeLabel": self.policy.dflash.dflash2_draft_size_label,
                "ready": dflash2_ready,
            }
            backend = {
                "omlx": {
                    "runnable": omlx_artifact_ready,
                    "reason": (
                        "Ready for oMLX with read-only PLE N-gram SSD mmap"
                        if qwen4_ple.get("supported") is True else
                        str(qwen4_ple.get("reason"))
                        if qwen4_architecture else
                        "Ready for oMLX" if ready and fmt == "mlx" else
                        "oMLX requires a complete MLX artifact"
                    ),
                    "qwen4Ple": copy.deepcopy(qwen4_ple),
                    "mtp": omlx_mtp,
                    "mtpReason": "Native integrated MTP tensors detected" if omlx_mtp else ("Config advertises MTP, but this conversion contains no MTP tensors" if mtp_declared and not sidecar_mtp else "No verified oMLX-native MTP tensors"),
                    "dflash": dflash2_ready,
                    "dflashVersion": "2" if dflash2_ready else None,
                    "dflashReason": dflash2_reason,
                    "dflashDraftPath": dflash2_draft.get("path") if dflash2_draft else None,
                    "dflashDraftSize": int(dflash2_draft.get("size") or 0) if dflash2_draft else 0,
                    "dflashBlockSize": dflash2_default_block if dflash2_ready else None,
                    "dflashMaxBlockSize": int(dflash2_shape["block_size"]) if dflash2_shape else None,
                    "dflashPairFingerprint": dflash2_pair_id,
                    "dflashRuntimeVersion": omlx_version,
                    "dflashBenchmark": None,
                    "dflashBenchmarkVerified": False,
                    "dflashPreferred": False,
                    "dflashReadiness": dflash2_readiness,
                    "anePrefill": False,
                    "aneReason": ane_reason,
                    "aneReadiness": ane_readiness,
                    "aneTuning": None,
                    "aneTuningVerified": False,
                    "preferredAcceleration": "mtp" if omlx_mtp else "off",
                    "depth": dflash2_default_block if dflash2_ready else 1,
                    "depthMax": int(dflash2_shape["block_size"]) if dflash2_shape else (3 if omlx_mtp and qwen4_architecture else 8 if omlx_mtp else 1),
                    # Qwen4 QSA carries unquantised index keys and MRoPE positions.
                    # Keep TurboQuant fail-closed until this exact route is measured.
                    "kv": not qwen4_architecture,
                    "agentReasoning": ["auto", "off", *reasoning_efforts],
                    "codexReasoning": ["auto", *reasoning_efforts],
                },
                "lmstudio": {
                        "runnable": ready and lm_catalogued and not qwen4_architecture and not atomic_ple_ready,
                        "reason": (
                            "This exact AtomicChat split is admitted only through the pinned llama.cpp SSD-PLE route."
                            if atomic_ple_ready else
                            "LM Studio has no verified external Qwen4 PLE mmap route."
                            if qwen4_architecture else
                            "LM Studio catalog model" if lm_catalogued else
                            "Detected external GGUF; register/import it in LM Studio first"
                            if ready and fmt == "gguf" else "Not registered with LM Studio"
                        ),
                        "mtp": lmstudio_mtp,
                        "mtpReason": (
                            "Selected LM Studio CLI exposes load-time Draft MTP and the sidecar pairing/audit is valid; benchmark this route before the optimiser prefers it."
                            if lmstudio_mtp else
                            "The selected LM Studio CLI does not expose the complete load-time Draft MTP flag contract."
                            if lmstudio_mtp_artifact and not lmstudio_mtp_runtime else
                            "MTP sidecar is present but its pairing/audit is not verified."
                            if sidecar_mtp else "No MTP sidecar found."
                        ),
                        "mtpRuntimeVerified": lmstudio_mtp_runtime,
                        "assistantDrafter": lmstudio_assistant_drafter,
                        "preferredAcceleration": "off",
                        "dflash": False,
                        "dflashVersion": None,
                        "dflashReason": f"{lmstudio_cli_version} does not expose a verified DFlash 2 loading route.",
                        "kv": False,
                        # LM Studio's Chat Completions compatibility route does
                        # not expose a reasoning control. Codex uses Responses,
                        # where only levels advertised by both the model template
                        # and LM Studio's public API vocabulary are offered.
                        "agentReasoning": ["auto"],
                        "codexReasoning": ["auto", *lm_reasoning_efforts],
                        "depth": mtp_depth,
                        "depthMax": mtp_depth_max if lmstudio_mtp else 1,
                        "mtpMinTokens": self.policy.lmstudio.lmstudio_mtp_min_tokens_default,
                        "mtpMinContinueProbability": self.policy.lmstudio.lmstudio_mtp_min_continue_probability_default,
                },
                "mtplx": {
                        "runnable": ready and fmt == "mlx" and not qwen4_architecture,
                        "reason": (
                            "MTPLX has no verified external Qwen4 PLE mmap route."
                            if qwen4_architecture else
                            "MLX artifact; MTPLX validates again before loading"
                            if ready and fmt == "mlx" else
                            "MTPLX requires a complete compatible MLX artifact"
                        ),
                        "mtp": mtplx_native_ready,
                        "mtpReason": (
                            "Verified MTPLX runtime contract"
                            if mtplx_native_ready else
                            "No matching MTP weights have been verified by MTPLX."
                        ),
                        "dflash": False,
                        "dflashVersion": None,
                        "dflashReason": f"{mtplx_version} serves native MTP or AR; DFlash 2 is not a serving mode.",
                        "kv": True,
                        "profile": runtime.get("recommended_profile") if isinstance(runtime.get("recommended_profile"), str) else "sustained",
                        "depth": mtp_depth,
                        "depthMax": mtp_depth_max,
                        "agentReasoning": ["auto", "off", "low", "medium", "high", "xhigh"],
                        "codexReasoning": ["auto", "low", "medium", "high", "xhigh"],
                },
                "freetoken": {
                        "runnable": False,
                        "reason": (
                            "The native FreeToken port currently accepts only complete Qwen3-MoE MLX checkpoints."
                            if freetoken_native_binary else
                            "Install the native Apple-Silicon port or connect a FreeToken server."
                        ),
                        "mtp": False,
                        "mtpReason": "Native FreeToken owns expert execution; speculative MTP is not exposed.",
                        "dflash": False,
                        "dflashVersion": None,
                        "dflashReason": "DFlash 2 is not a FreeToken serving mode.",
                        "kv": False,
                        "preferredAcceleration": "off",
                        "depth": 1,
                        "depthMax": 1,
                        "agentReasoning": ["auto"],
                        "codexReasoning": ["auto"],
                        "customSampling": False,
                        "samplingReason": "The native FreeToken milestone currently uses greedy decoding only.",
                },
                "swiftlm": {
                        "runnable": bool(
                            ready and fmt == "mlx" and ssd_profile["moe"]
                            and swiftlm_family_ready
                        ),
                        "reason": (
                            swiftlm_family_reason
                            if ready and fmt == "mlx" and ssd_profile["moe"] else
                            "SwiftLM SSD streaming requires a complete MLX Mixture-of-Experts checkpoint."
                        ),
                        "mtp": False,
                        "mtpReason": "MTP is deliberately disabled for SSD-streamed MoEs because verification multiplies expert I/O fan-out.",
                        "dflash": False,
                        "dflashVersion": None,
                        "dflashReason": "DFlash is outside the exact SSD-streaming calibration contract.",
                        "kv": False,
                        "preferredAcceleration": "off",
                        "depth": 1,
                        "depthMax": 1,
                        "agentReasoning": ["auto", "off"],
                        "codexReasoning": ["auto"],
                        "ssdStreaming": True,
                        "ssdProfile": copy.deepcopy(ssd_profile),
                        "modelPath": str(real),
                        "nativeExpertTopK": int(ssd_profile.get("nativeExpertTopK") or 0),
                        "prefillSize": 512,
                        "exactExpertRouting": True,
                },
                "mference": {
                        "runnable": bool(ready and fmt == "mference" and mference_family_ready),
                        "reason": mference_family_reason,
                        "mtp": False,
                        "mtpReason": "Mference uses model-native expert execution; no speculative route is included in SSD calibration.",
                        "dflash": False,
                        "dflashVersion": None,
                        "dflashReason": "DFlash is outside Mference's pinned model contract.",
                        "kv": False,
                        "preferredAcceleration": "off",
                        "depth": 1,
                        "depthMax": 1,
                        "agentReasoning": ["auto"],
                        "codexReasoning": ["auto"],
                        "ssdStreaming": True,
                        "ssdProfile": copy.deepcopy(ssd_profile),
                        "modelPath": str(real),
                        "promptCacheMode": "on",
                        "queueLimit": 4,
                        "contextWindows": list(self.policy.ssd.mference_context_windows),
                        "contextMaximum": max(self.policy.ssd.mference_context_windows),
                        "exactExpertRouting": True,
                },
                "whallm": {
                        "runnable": False,
                        "reason": (
                            "Whallm uses its own pinned 125 GB Qwen3.8 Flash-Next MXFP4 install; "
                            "it cannot consume this scanned model folder. Start Whallm's server "
                            "and rescan to use its advertised model."
                            if ssd_profile.get("qwen38FlashNext") else
                            "Whallm currently accepts only its pinned Qwen3.8 Flash-Next checkpoint."
                        ),
                        "mtp": False,
                        "mtpReason": (
                            "Whallm's optional Qwen MTP prototype is confined to its own pinned install "
                            "and is not an acceleration mode for this scanned model folder."
                        ),
                        "dflash": False,
                        "dflashVersion": None,
                        "dflashReason": "DFlash is not a Whallm serving mode.",
                        "kv": False,
                        "preferredAcceleration": "off",
                        "depth": 1,
                        "depthMax": 1,
                        "agentReasoning": ["auto", "off", "low", "medium", "high", "xhigh", "max"],
                        "codexReasoning": ["auto", "off", "low", "medium", "high", "xhigh", "max"],
                        "ssdStreaming": True,
                        "ssdProfile": copy.deepcopy(ssd_profile),
                        "exactExpertRouting": True,
                },
                "llamacpp": {
                        "runnable": bool(atomic_ple_ready and llamacpp_runtime.get("ready") is True),
                        "reason": (
                            str(llamacpp_runtime.get("reason") or "The pinned llama.cpp runtime is not ready.")
                            if atomic_ple_ready else str(atomic_ple.get("reason") or "This GGUF is not allowlisted.")
                        ),
                        "mtp": False,
                        "mtpReason": "MTP and draft-model speculation are disabled for the initial SSD-PLE qualification.",
                        "dflash": False,
                        "dflashVersion": None,
                        "dflashReason": "DFlash is a different serving route and is not mixed into this qualification.",
                        "kv": False,
                        "preferredAcceleration": "off",
                        "depth": 1,
                        "depthMax": 1,
                        "agentReasoning": ["auto"],
                        "codexReasoning": ["auto"],
                        "contextWindows": [self.policy.atomic.llamacpp_ple_context],
                        "contextMaximum": self.policy.atomic.llamacpp_ple_context,
                        "atomicPle": copy.deepcopy(atomic_ple),
                        "llamacppPle": atomic_ple_ready,
                        "verificationState": atomic_ple.get("verificationState"),
                        "currentProcessVerified": atomic_ple.get("currentProcessVerified") is True,
                        "verificationGeneration": atomic_ple.get("verificationGeneration"),
                        "verifiedShards": int(atomic_ple.get("verifiedShards") or 0),
                        "totalShards": int(
                            atomic_ple.get("totalShards") or self.policy.atomic.llamacpp_atomic_shards
                        ),
                        "presentationSnapshot": atomic_ple.get("presentationSnapshot") is True,
                        "receiptFingerprint": atomic_ple.get("receiptFingerprint"),
                        "modelPath": str(real),
                        "firstShard": atomic_ple.get("firstShard"),
                        "memoryCeilingBytes": self.policy.atomic.llamacpp_ple_memory_ceiling_bytes,
                        "exactExpertRouting": True,
                },
            }
            model_fingerprint = self.model_artifact_fingerprint(real, config) if ready else ""
            freetoken_capability = backend["freetoken"]
            if freetoken_native_binary and ready and fmt == "mlx":
                if model_type != "qwen3_moe":
                    freetoken_capability["reason"] = (
                        f"Native FreeToken schema {self.policy.freetoken.freetoken_native_schema_version} supports model_type=qwen3_moe; "
                        f"this checkpoint reports {model_type}."
                    )
                else:
                    try:
                        native_contract = self.inspect_native_freetoken_model(
                            real, int(context or self.policy.general.default_context), model_fingerprint,
                        )
                        rejection = native_contract.get("rejection")
                        supported_contract = native_contract.get("supported") is True
                        startup_allowed = native_contract.get("startup", {}).get("default_allowed") is True
                        qualification = native_contract["qualification"]
                        qualification_policy = qualification["launcher"]
                        real_checkpoint_verified = (
                            qualification.get("real_checkpoint_verified") is True
                            and qualification.get("inspected_checkpoint_qualified") is True
                            and qualification_policy.get("readiness") == "qualified_real_checkpoint"
                        )
                        experimental_checkpoint = (
                            qualification_policy.get("readiness") == "experimental_synthetic_only"
                        )
                        if supported_contract and startup_allowed:
                            native_reason = (
                                "Native FreeToken qualified this exact real checkpoint with an end-to-end serve and token-generation receipt."
                                if real_checkpoint_verified else
                                "This existing local checkpoint passed format and memory preflight, but the port has only tiny-synthetic end-to-end verification. An explicit experimental-run approval is required."
                            )
                        elif supported_contract:
                            working = native_contract.get("working_set", {})
                            needed = native_contract.get("sizing", {}).get("weights_plus_kv_bytes")
                            budget = working.get("budget_after_headroom_bytes")
                            native_reason = (
                                "Native FreeToken supports this checkpoint, but its maximum-context working-set preflight "
                                f"needs {self.values.display_size(int(needed)) if isinstance(needed, int) else 'more memory'} against "
                                f"a {self.values.display_size(int(budget)) if isinstance(budget, int) else 'smaller'} safe budget. "
                                "The launcher will not apply the unsafe override automatically."
                            )
                        else:
                            native_reason = str(
                                rejection.get("message")
                                if isinstance(rejection, dict) else
                                "Native FreeToken rejected this checkpoint."
                            )[:600]
                        max_context = native_contract.get("model", {}).get("max_context_tokens")
                        expert_count = self.values.deep_get(
                            config, ("text_config", "num_experts"),
                            ("text_config", "num_local_experts"),
                            ("num_experts",), ("num_local_experts",),
                        )
                        freetoken_capability.update({
                            "runnable": bool(supported_contract and startup_allowed),
                            "reason": native_reason,
                            "native": True,
                            "nativeContract": native_contract,
                            "nativeBinary": str(Path(freetoken_native_binary).expanduser().resolve()),
                            "nativeApiVersion": self.policy.freetoken.freetoken_native_api_version,
                            "qualificationReadiness": qualification_policy.get("readiness"),
                            "realCheckpointVerified": real_checkpoint_verified,
                            "experimentalQualification": experimental_checkpoint,
                            "largeDownloadRecommended": qualification_policy.get("large_download_recommended") is True,
                            "nativeExpertCount": (
                                int(expert_count)
                                if isinstance(expert_count, int) and not isinstance(expert_count, bool)
                                and expert_count > 0 else None
                            ),
                            "nativeMaxContext": (
                                int(max_context)
                                if isinstance(max_context, int) and not isinstance(max_context, bool)
                                else context
                            ),
                            "clientSupport": {
                                "chat": {
                                    "supported": native_contract.get("support", {}).get("chat_completions") is True,
                                    "reason": (
                                        "Native streaming Chat Completions on an exactly qualified real checkpoint; greedy decoding in the current port milestone."
                                        if real_checkpoint_verified else
                                        "Native streaming Chat Completions; this checkpoint remains an explicit synthetic-only experimental run."
                                    ),
                                },
                                "pi": {
                                    "supported": False,
                                    "reason": "Native FreeToken does not expose tool calling yet, so Pi is blocked fail-closed.",
                                },
                                "omp": {
                                    "supported": False,
                                    "reason": "Native FreeToken does not expose tool calling yet, so oh-my-pi is blocked fail-closed.",
                                },
                                "opencode": {
                                    "supported": False,
                                    "reason": "Native FreeToken does not expose tool calling yet, so OpenCode is blocked fail-closed.",
                                },
                                "codex": {
                                    "supported": False,
                                    "reason": "Native FreeToken does not expose the Responses API yet, so Codex is blocked fail-closed.",
                                },
                            },
                        })
                    except ValueError as error:
                        freetoken_capability["reason"] = str(error)[:600]
            ane_record = self.evidence.matching_ane_record(
                ane_tuning_records, model_fingerprint, omlx_version,
                machine_fingerprint or None,
            ) if ane_tuning_records and model_fingerprint else None
            ane_verified = self.evidence.verified_ane_record(
                ane_record, model_fingerprint, omlx_version,
                machine_fingerprint or None,
            ) if ane_record else False
            omlx_capability = backend["omlx"]
            omlx_capability["aneTuning"] = ane_record
            omlx_capability["aneTuningVerified"] = ane_verified
            omlx_capability["anePrefill"] = ane_verified
            omlx_capability["aneReadiness"]["tuned"] = ane_verified
            omlx_capability["aneReadiness"]["latestResultAccepted"] = bool(ane_record and ane_record.get("accepted"))
            if ane_verified:
                speedup = float(ane_record["recommendation"]["speedup_percent"])
                omlx_capability["aneReason"] = (
                    f"A local ANE execution trace proved a {speedup:.1f}% prefill gain for this exact checkpoint/runtime/Mac."
                )
            runtime_versions = {
                "omlx": omlx_version,
                "lmstudio": lmstudio_version,
                "mtplx": mtplx_version,
                "freetoken": freetoken_native_version,
                "swiftlm": swiftlm_version,
                "mference": mference_version,
                "whallm": whallm_version,
                "llamacpp": llamacpp_version,
            }
            mtplx_scan_model = {
                "name": real.name,
                "path": str(real),
                "format": fmt,
                "architecture": architecture,
                "modelType": model_type,
                "rootModelType": root_model_type,
                "textModelType": text_model_type,
                "nativeContext": context,
                "ready": ready,
            }
            mtplx_scan_capability = {
                **backend["mtplx"],
                "runtimeVersion": mtplx_version,
                "benchmarkModelFingerprint": model_fingerprint,
            }
            mtplx_long_context_receipt = self.mtplx_long_context_2111_contract(
                mtplx_scan_model, mtplx_scan_capability,
                runtime_version=mtplx_version,
            )
            backend["mtplx"]["longContext2111"] = self._mtplx_long_context_capability(
                mtplx_long_context_receipt, mtplx_version,
            )
            for backend_name, capability in backend.items():
                runtime_version = runtime_versions[backend_name]
                capability["runtimeVersion"] = runtime_version
                capability["benchmarkModelFingerprint"] = model_fingerprint
                # These local routes consume the same verified model artifact from
                # which ``defaultSampling`` was read. Model mode may therefore
                # leave protocol-specific fields implicit when a client API cannot
                # spell every artifact default. Custom mode never receives this
                # exception.
                capability["implicitSamplingDefaultsVerified"] = bool(
                    ready and capability.get("runnable") is True
                )
                if backend_name in self.policy.ssd.ssd_streaming_backends:
                    capability["artifactFingerprint"] = model_fingerprint
                    capability["comparisonIdentity"] = ssd_profile.get("comparisonIdentity")
                capability["localBenchmark"] = None
                capability["localBenchmarks"] = []
                capability["fallbackAcceleration"] = capability.get("preferredAcceleration")
                benchmark_history = self.evidence.matching_benchmarks(
                    benchmark_records, backend_name, model_fingerprint,
                    runtime_version, capability, machine_fingerprint or None,
                )
                capability["benchmarkHistoryCount"] = len(benchmark_history)
                benchmarks = self.evidence.latest_by_identity(benchmark_history)
                capability["localBenchmarks"] = benchmarks
                benchmark = benchmarks[-1] if benchmarks else None
                if not benchmark:
                    continue
                capability["localBenchmark"] = benchmark
                capability["preferredAccelerationSource"] = "local-benchmark"
                winner = benchmark.get("winner")
                if winner == "dflash2" and capability.get("dflash"):
                    capability["preferredAcceleration"] = "dflash"
                    capability["dflashBenchmark"] = copy.deepcopy(benchmark)
                    capability["dflashBenchmarkVerified"] = benchmark.get("qualityPassed") is True
                    capability["dflashPreferred"] = True
                elif winner == "mtp" and capability.get("mtp"):
                    capability["preferredAcceleration"] = "mtp"
                    # A catalog scan knows only artifact/runtime/Mac identity. It
                    # must not copy request-specific tuning coordinates into the
                    # artifact capability before context, reasoning, sampling, KV,
                    # and engine controls have been verified. ``fastest_safe_options``
                    # applies those coordinates later from an exact matching record.
                elif winner == "ar":
                    capability["preferredAcceleration"] = "off"

            if expert_offload.get("supported"):
                backend["omlx"].update({
                    "expertOffload": True, "experimental": True,
                    "mtp": False, "dflash": False, "depth": 1, "depthMax": 1,
                    "preferredAcceleration": "off", "fallbackAcceleration": "off", "anePrefill": False,
                    "reason": expert_offload["reason"], "mtpReason": "oMLX expert offload requires MTP to be off.",
                })
            shared_slotstream = bool(slotstream_install and str(real) == str(Path(slotstream_install["modelPath"]).resolve()))
            if shared_slotstream:
                backend["omlx"]["runnable"] = bool(omlx_artifact_ready and expert_offload.get("supported"))
                if not backend["omlx"]["runnable"]:
                    backend["omlx"]["reason"] = expert_offload["reason"]
            records[key] = {
                "id": self.values.slug(key),
                "name": "Qwen3.8 Flash-Next · MLX 4-bit" if shared_slotstream else real.name,
                "path": str(real),
                "artifact": str(artifact),
                "origins": list(item["origins"]),
                "format": fmt,
                "architecture": architecture,
                "modelType": model_type,
                "rootModelType": root_model_type,
                "textModelType": text_model_type,
                "nativeContext": context,
                "quantization": quantization,
                "size": weight_bytes,
                "sizeLabel": self.values.display_size(weight_bytes),
                "memoryGeometry": self.model_memory_geometry(config),
                "qwen4Ple": copy.deepcopy(qwen4_ple),
                "omlxExpertOffload": copy.deepcopy(expert_offload),
                "mtpSidecarSize": mtp_sidecar_bytes,
                "ready": ready,
                "status": status,
                "mtp": {"declared": mtp_declared, "integrated": integrated_mtp, "sidecar": sidecar_mtp},
                "templateReasoningEfforts": reasoning_efforts,
                "defaultSampling": default_sampling,
                "lmKey": lm_key,
                "nativeFreetoken": freetoken_capability.get("native") is True,
                "ssdStreaming": ssd_profile,
                "atomicPle": copy.deepcopy(atomic_ple),
                "verificationState": atomic_ple.get("verificationState") if atomic_named_variant else None,
                "currentProcessVerified": atomic_ple.get("currentProcessVerified") is True,
                "verificationProgress": {
                    "completed": int(atomic_ple.get("verifiedShards") or 0),
                    "total": int(atomic_ple.get("totalShards") or self.policy.atomic.llamacpp_atomic_shards),
                } if atomic_named_variant else None,
                "backends": backend,
            }
        # A verified Mference repack and its ordinary MLX source are separate
        # folders. Link only receipts that prove the same pinned source revision
        # or source index; display-name similarity is never enough.
        ssd_groups: dict[str, list[dict[str, Any]]] = {}
        for record in records.values():
            profile = record.get("ssdStreaming")
            identity = str(profile.get("comparisonIdentity") or "") if isinstance(profile, dict) else ""
            if identity:
                ssd_groups.setdefault(identity, []).append(record)
        for identity, group in ssd_groups.items():
            route_sources: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
            for source_record in group:
                for backend_name in self.policy.ssd.ssd_artifact_backends:
                    capability = source_record.get("backends", {}).get(backend_name, {})
                    if capability.get("runnable") is True:
                        route_sources.setdefault(backend_name, (source_record, capability))
            if len(route_sources) < 2:
                continue
            for target_record in group:
                for backend_name, (source_record, source_capability) in route_sources.items():
                    target_capability = target_record.get("backends", {}).get(backend_name, {})
                    if target_capability.get("runnable") is True:
                        continue
                    paired = copy.deepcopy(source_capability)
                    paired.update({
                        "pairedArtifact": True,
                        "pairedArtifactName": str(source_record.get("name") or "SSD model bundle"),
                        "pairedArtifactModelId": str(source_record.get("id") or ""),
                        "comparisonIdentity": identity,
                        "reason": (
                            f"Uses the verified equivalent {source_record.get('name')} artifact for "
                            f"{self.policy.backend_labels[backend_name]}."
                        ),
                    })
                    target_record["backends"][backend_name] = paired
                target_record["ssdStreaming"]["pairedCalibrationReady"] = True
                target_record["ssdStreaming"]["pairedEngines"] = list(self.policy.ssd.ssd_artifact_backends)
        freetoken = self.connections.freetoken_connection()
        if freetoken:
            endpoint_label = urllib.parse.urlsplit(str(freetoken["endpoint"])).netloc
            runtime_label = str(freetoken.get("server") or "FreeToken remote API")
            for remote_model_id in freetoken["models"]:
                remote_fingerprint = hashlib.sha256(json.dumps({
                    "engine": "freetoken",
                    "connection": freetoken["id"],
                    "model": remote_model_id,
                    "context": freetoken["context"],
                }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
                remote_backends: dict[str, dict[str, Any]] = {}
                for engine_id, descriptor in self.policy.engines.items():
                    if engine_id == "freetoken":
                        remote_backends[engine_id] = {
                            "runnable": True,
                            "reason": f"Advertised live by the configured FreeToken server at {endpoint_label}.",
                            "mtp": False,
                            "mtpReason": "FreeToken automatically selects fused, offload, CPU, or hybrid MoE execution on its server.",
                            "dflash": False,
                            "dflashVersion": None,
                            "dflashReason": "DFlash 2 is not a FreeToken serving mode.",
                            "kv": False,
                            "preferredAcceleration": "off",
                            "fallbackAcceleration": "off",
                            "depth": 1,
                            "depthMax": 1,
                            "agentReasoning": ["auto"],
                            "codexReasoning": ["auto"],
                            "runtimeVersion": runtime_label,
                            "benchmarkModelFingerprint": remote_fingerprint,
                            "localBenchmark": None,
                            "localBenchmarks": [],
                            "benchmarkHistoryCount": 0,
                            "remote": True,
                            "connectionId": freetoken["id"],
                        }
                    else:
                        remote_backends[engine_id] = {
                            "runnable": False,
                            "reason": f"This model is advertised by FreeToken at {endpoint_label}, not present as a verified local {descriptor.label} artifact.",
                            "mtp": False,
                            "mtpReason": "No equivalent local artifact was asserted.",
                            "dflash": False,
                            "dflashVersion": None,
                            "dflashReason": "No equivalent local artifact was asserted.",
                            "kv": False,
                            "preferredAcceleration": "off",
                            "fallbackAcceleration": "off",
                            "depth": 1,
                            "depthMax": 1,
                            "agentReasoning": ["auto"],
                            "codexReasoning": ["auto"],
                            "runtimeVersion": "Not applicable",
                            "benchmarkModelFingerprint": remote_fingerprint,
                            "localBenchmark": None,
                            "localBenchmarks": [],
                            "benchmarkHistoryCount": 0,
                        }
                record_key = f"freetoken:{freetoken['id']}:{remote_model_id}"
                records[record_key] = {
                    "id": "freetoken-" + hashlib.sha256(record_key.encode("utf-8", "replace")).hexdigest()[:24],
                    "name": remote_model_id,
                    "path": "FreeToken remote endpoint",
                    "artifact": f"freetoken:{remote_fingerprint[:24]}",
                    "origins": [f"FreeToken · {endpoint_label}"],
                    "format": "remote api",
                    "architecture": "Server managed",
                    "modelType": "freetoken-remote",
                    "nativeContext": int(freetoken["context"]),
                    "quantization": "Server managed",
                    "size": 0,
                    "sizeLabel": "Remote",
                    "memoryGeometry": {"ready": False, "remote": True},
                    "mtpSidecarSize": 0,
                    "ready": True,
                    "status": "Connected",
                    "mtp": {"declared": False, "integrated": False, "sidecar": False},
                    "templateReasoningEfforts": [],
                    "defaultSampling": {},
                    "lmKey": remote_model_id,
                    "remote": True,
                    "remoteConnectionId": freetoken["id"],
                    "remoteModelId": remote_model_id,
                    "backends": remote_backends,
                }
        whallm = self.connections.whallm_endpoint()
        if whallm:
            source_revision = "bcd9f01ddc9cff2316eb84281bebcd5b058bddce"
            comparison_identity = hashlib.sha256(
                f"ssd-source-v1\0qwen/qwen3.8-flash-next-fp8\0revision\0{source_revision}".encode("utf-8")
            ).hexdigest()
            model_fingerprint = hashlib.sha256(json.dumps({
                "engine": "whallm", "version": whallm_version,
                "model": self.policy.whallm.whallm_model_id, "revision": source_revision,
            }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            ssd_profile = {
                "version": self.policy.ssd.ssd_streaming_contract_version,
                "candidate": True, "recommended": True, "moe": True,
                "oversized": True, "qwen38FlashNext": True,
                "expertCount": 512, "nativeExpertTopK": 10,
                "weightBytes": self.policy.whallm.whallm_model_bytes,
                "installedMemoryBytes": installed_memory,
                "weightToMemoryRatio": round(self.policy.whallm.whallm_model_bytes / installed_memory, 4) if installed_memory else None,
                "format": "whallm-mxfp4", "reason": (
                    "Whallm advertises its pinned full 512-expert Qwen3.8 Flash-Next model on loopback. "
                    "This 48 GiB Mac is experimental because Whallm publishes a 64 GiB support floor."
                ),
                "sourceContract": {
                    "sourceModel": "qwen/qwen3.8-flash-next-fp8",
                    "proofKind": "revision", "proof": source_revision,
                    "comparisonIdentity": comparison_identity,
                    "verifiedForCrossFormatComparison": True,
                },
                "comparisonIdentity": comparison_identity,
                "crossFormatComparisonReady": True,
                "calibration": {
                    "suite": "agentic", "engines": ["whallm"],
                    "freshProcessPerEngine": False, "coldAndWarmStages": True,
                    "nativeExpertRoutingRequired": True,
                    "metrics": ["generationTps", "ttft", "peakMemory", "thermalState", "prefixReuse"],
                },
            }
            remote_backends: dict[str, dict[str, Any]] = {}
            for engine_id, descriptor in self.policy.engines.items():
                if engine_id == "whallm":
                    remote_backends[engine_id] = {
                        "runnable": True,
                        "reason": (
                            "Live Whallm 1.1.x loopback route · full 512 experts · experimental on 48 GiB. "
                            "Public M5 Pro measurements cover up to 16,384 input tokens."
                        ),
                        "mtp": False, "mtpReason": (
                            "Whallm 1.1.4 exposes an optional default-off MTP prototype, but its "
                            "published formal total-time and tail-latency gates did not accept it. "
                            "The launcher keeps it unavailable until an exact local route qualification exists."
                        ),
                        "dflash": False, "dflashVersion": None,
                        "dflashReason": "DFlash is not a Whallm serving mode.",
                        "kv": False, "preferredAcceleration": "off", "fallbackAcceleration": "off",
                        "depth": 1, "depthMax": 1,
                        "agentReasoning": ["auto", "off", "low", "medium", "high", "xhigh", "max"],
                        "codexReasoning": ["auto", "off", "low", "medium", "high", "xhigh", "max"],
                        "runtimeVersion": whallm_version,
                        "benchmarkModelFingerprint": model_fingerprint,
                        "localBenchmark": None, "localBenchmarks": [], "benchmarkHistoryCount": 0,
                        "ssdStreaming": True, "ssdProfile": copy.deepcopy(ssd_profile),
                        "comparisonIdentity": comparison_identity,
                        "exactExpertRouting": True, "remote": False, "sharedServer": True,
                        "contextWindows": list(self.policy.whallm.whallm_context_windows),
                        "contextMaximum": max(self.policy.whallm.whallm_context_windows),
                        "customSampling": False,
                        "samplingReason": (
                            "Whallm's public Qwen API does not expose every custom launcher sampling field; "
                            "use the model's thinking or chat defaults."
                        ),
                    }
                else:
                    remote_backends[engine_id] = {
                        "runnable": False,
                        "reason": f"This model is owned by Whallm's pinned install, not a {descriptor.label} model folder.",
                        "mtp": False, "mtpReason": "No equivalent local artifact was asserted.",
                        "dflash": False, "dflashVersion": None,
                        "dflashReason": "No equivalent local artifact was asserted.",
                        "kv": False, "preferredAcceleration": "off", "fallbackAcceleration": "off",
                        "depth": 1, "depthMax": 1,
                        "agentReasoning": ["auto"], "codexReasoning": ["auto"],
                        "runtimeVersion": "Not applicable",
                        "benchmarkModelFingerprint": model_fingerprint,
                        "localBenchmark": None, "localBenchmarks": [], "benchmarkHistoryCount": 0,
                    }
            record_key = f"whallm:{self.policy.whallm.whallm_model_id}:{source_revision}"
            records[record_key] = {
                "id": "whallm-" + model_fingerprint[:24],
                "name": "Qwen3.8 Flash-Next · Whallm full experts",
                "path": "Whallm shared loopback server",
                "artifact": f"whallm:{source_revision[:24]}",
                "origins": ["Whallm · 127.0.0.1:11434"],
                "format": "Whallm MXFP4 + SSD", "architecture": "Qwen4Exp · 512 experts",
                "modelType": "whallm-qwen38-flash-next",
                "nativeContext": max(self.policy.whallm.whallm_context_windows),
                "quantization": "MXFP4 experts · FP8 n-gram",
                "size": self.policy.whallm.whallm_model_bytes, "sizeLabel": self.values.display_size(self.policy.whallm.whallm_model_bytes),
                "memoryGeometry": {"ready": False, "sharedServer": True},
                "mtpSidecarSize": 0, "ready": True, "status": "Connected",
                "mtp": {"declared": False, "integrated": False, "sidecar": False},
                "templateReasoningEfforts": ["low", "medium", "xhigh"],
                "defaultSampling": {}, "lmKey": self.policy.whallm.whallm_model_id,
                "sharedServer": True, "remote": False,
                "remoteModelId": self.policy.whallm.whallm_model_id,
                "ssdStreaming": ssd_profile, "backends": remote_backends,
            }
        if not whallm:
            native_whallm = whallm_runtime.discover(self.runtime.selected_binary("whallm"))
            if native_whallm:
                native_record = whallm_runtime.model_record(
                    native_whallm,
                    [(engine_id, descriptor.label) for engine_id, descriptor in self.policy.engines.items()],
                    installed_memory,
                )
                records[native_record["id"]] = native_record
        slotstream_install = slotstream_runtime.discover(self.runtime.selected_binary("slotstream"))
        if slotstream_install:
            slotstream_record = slotstream_runtime.model_record(
                slotstream_install, [(key, value.label) for key, value in self.policy.engines.items()], installed_memory,
            )
            slot_cap = slotstream_record["backends"]["slotstream"]
            slot_history = self.evidence.matching_benchmarks(
                benchmark_records, "slotstream", slot_cap["benchmarkModelFingerprint"],
                slot_cap["runtimeVersion"], slot_cap, machine_fingerprint or None,
            )
            slot_cap["benchmarkHistoryCount"] = len(slot_history)
            slot_cap["localBenchmarks"] = self.evidence.latest_by_identity(slot_history)
            if slot_cap["localBenchmarks"]:
                slot_cap["localBenchmark"] = slot_cap["localBenchmarks"][-1]
                slot_cap["preferredAccelerationSource"] = "local-benchmark"
                slot_cap["preferredAcceleration"] = "mtp" if slot_cap["localBenchmark"].get("winner") == "mtp" else "off"
            records[slotstream_record["id"]] = slotstream_record
        splash_install = splash_runtime.inspect_install(self.runtime.selected_binary("splash"))
        if splash_install:
            splash_sources = splash_runtime.inspect_sources(
                splash_install,
                splash_runtime.source_candidates([
                    *(item["path"] for item in discovered.values()),
                    *splash_runtime.installed_source_roots(),
                ], install=splash_install),
            )
            for splash_pack in [*(splash_install.get("packs") or ()), *splash_sources]:
                splash_record = splash_runtime.model_record(
                    splash_install, splash_pack,
                    [(key, value.label) for key, value in self.policy.engines.items()],
                    installed_memory,
                )
                splash_record["splash"]["draftCandidates"] = [draft["path"] for draft in dflash2_drafts]
                splash_cap = splash_record["backends"]["splash"]
                splash_history = self.evidence.matching_benchmarks(
                    benchmark_records, "splash", splash_cap["benchmarkModelFingerprint"],
                    splash_cap["runtimeVersion"], splash_cap, machine_fingerprint or None,
                )
                splash_cap["benchmarkHistoryCount"] = len(splash_history)
                splash_cap["localBenchmarks"] = self.evidence.latest_by_identity(splash_history)
                if splash_cap["localBenchmarks"]:
                    splash_cap["localBenchmark"] = splash_cap["localBenchmarks"][-1]
                records[splash_record["id"]] = splash_record
        strata_install = strata_runtime.inspect_install(self.runtime.selected_binary("strata"))
        if strata_install:
            for strata_model in strata_runtime.discover_models():
                strata_record = strata_runtime.model_record(
                    strata_install, strata_model, [(key, value.label) for key, value in self.policy.engines.items()], installed_memory)
                records[strata_record["id"]] = strata_record
        rec_install = rec_runtime.inspect_install(self.runtime.selected_binary("rec"))
        if rec_install:
            for rec_root in rec_runtime.installed_model_roots(rec_install):
                rec_model = rec_runtime.inspect_model(rec_root)
                if rec_model:
                    rec_record = rec_runtime.model_record(
                        rec_install, rec_model,
                        [(key, value.label) for key, value in self.policy.engines.items()], installed_memory,
                    )
                    records[rec_record["id"]] = rec_record
        rapidmlx_install = rapidmlx_runtime.inspect_runtime(self.runtime.selected_binary("rapidmlx"))
        kolibri_install = kolibri_runtime.inspect_runtime(self.runtime.selected_binary("kolibri"))
        for scanned_model in records.values():
            rapid_cap = rapidmlx_runtime.capability(scanned_model, rapidmlx_install)
            rapid_history = self.evidence.matching_benchmarks(
                benchmark_records, "rapidmlx", rapid_cap.get("benchmarkModelFingerprint"),
                rapid_cap["runtimeVersion"], rapid_cap, machine_fingerprint or None,
            ) if rapid_cap.get("runnable") else []
            rapid_cap["benchmarkHistoryCount"] = len(rapid_history)
            rapid_cap["localBenchmarks"] = self.evidence.latest_by_identity(rapid_history)
            if rapid_cap["localBenchmarks"]:
                rapid_cap["localBenchmark"] = rapid_cap["localBenchmarks"][-1]
            scanned_model.setdefault("backends", {})["rapidmlx"] = rapid_cap
            if scanned_model.get("rec") and rapid_cap.get("runnable"):
                scanned_model["name"] = "Flint INT4"
            kolibri_model = (
                kolibri_runtime.inspect_model(Path(scanned_model["path"]))
                if scanned_model.get("modelType") == "kolibri1" else None
            )
            scanned_model.setdefault("backends", {})["kolibri"] = kolibri_runtime.capability(kolibri_model, kolibri_install)
            if kolibri_model:
                scanned_model["kolibri"] = kolibri_model
                scanned_model["defaultOutput"] = kolibri_runtime.DEFAULT_OUTPUT
                scanned_model["outputMaximum"] = kolibri_runtime.OUTPUT_MAXIMUM
                scanned_model["defaultSampling"] = {"temperature": 1.0, "top_p": 0.97, "top_k": 128}
                for other, other_cap in scanned_model["backends"].items():
                    if other != "kolibri" and not (other == "rapidmlx" and other_cap.get("runnable") is True):
                        other_cap["runnable"] = False
                        other_cap["reason"] = "Use Kolibri SSD to run this Q6 checkpoint with bounded expert offloading."
            capabilities = scanned_model.get("backends")
            if not isinstance(capabilities, dict):
                continue
            for backend_name, capability in capabilities.items():
                if not isinstance(capability, dict):
                    continue
                descriptor = self.policy.engines.get(backend_name)
                installed = bool(descriptor and descriptor.public(self.runtime.selected_binary).get("installed") is True)
                compatible = bool(
                    scanned_model.get("ready") is True
                    and capability.get("runnable") is True
                )
                capability["performanceEvidence"] = self.evidence.route_performance(
                    scanned_model, backend_name, capability,
                )
                capability["hostSupport"] = self.route_host_support(
                    scanned_model, backend_name, capability,
                    runtime_installed=installed,
                    artifact_compatible=compatible,
                )

        result = list(records.values())
        result.sort(key=lambda item: (not item["ready"], item["name"].lower()))
        return result


    def model_library_inventory(self, models: list[dict[str, Any]]) -> dict[str, Any]:
        """Build a read-only compatibility report from the canonical model scan.

        This deliberately performs no launches, downloads, model loads, or state
        writes. Compatibility remains derived from the same adapter registry,
        support matrix, and scanner capabilities used by launch validation.
        """
        engine_descriptors = {
            engine_id: descriptor.public(self.runtime.selected_binary)
            for engine_id, descriptor in self.policy.engines.items()
        }
        surface_descriptors = {
            surface_id: descriptor.public(self.runtime.selected_binary)
            for surface_id, descriptor in self.policy.surfaces.items()
        }
        reports: list[dict[str, Any]] = []

        for source in models:
            model = source if isinstance(source, dict) else {}
            model_ready = model.get("ready") is True
            remote_model = model.get("remote") is True
            backend_capabilities = model.get("backends")
            if not isinstance(backend_capabilities, dict):
                backend_capabilities = {}
            engine_reports: list[dict[str, Any]] = []
            launchable_routes = 0
            launchable_engines = 0
            accelerator_count = 0
            evidence_count = 0

            for engine_id, descriptor in self.policy.engines.items():
                public_engine = engine_descriptors[engine_id]
                capability = backend_capabilities.get(engine_id)
                if not isinstance(capability, dict):
                    capability = {}
                runtime_installed = public_engine["installed"] is True
                artifact_compatible = model_ready and capability.get("runnable") is True
                runnable = runtime_installed and artifact_compatible
                qualification_policy = (
                    capability.get("nativeContract", {}).get("qualification", {}).get("launcher", {})
                    if engine_id == "freetoken" else {}
                )
                qualification_readiness = str(qualification_policy.get("readiness") or "")
                performance_evidence = self.evidence.route_performance(
                    model, engine_id, capability,
                )
                host_support = self.route_host_support(
                    model, engine_id, capability,
                    runtime_installed=runtime_installed,
                    artifact_compatible=artifact_compatible,
                )
                experimental = host_support["state"] == "experimental"
                if runnable:
                    launchable_engines += 1

                if not runtime_installed:
                    engine_status = "runtime-missing"
                    engine_reason = f"{descriptor.label} is not installed."
                elif not artifact_compatible:
                    engine_status = "incompatible"
                    engine_reason = str(
                        capability.get("reason")
                        or model.get("status")
                        or f"This artifact is not compatible with {descriptor.label}."
                    )
                else:
                    engine_status = "experimental" if experimental else "ready"
                    engine_reason = str(capability.get("reason") or "Ready")

                fixed_uzu_route = bool(
                    engine_id == "uzu"
                    and capability.get("runtimeManagedAcceleration") == "DFlash + Weaver"
                )
                modes = [{
                    "id": "ar",
                    "label": self.evidence.public_mode_label(engine_id, "ar"),
                    "kind": "fixed-route" if fixed_uzu_route else "baseline",
                    "available": artifact_compatible,
                    "detail": (
                        "Runtime-managed bundled DFlash draft and Weaver verification tree"
                        if fixed_uzu_route else "Standard autoregressive decoding"
                    ),
                }]
                if model.get("uzuNative") is True and engine_id != "uzu":
                    modes = []
                if fixed_uzu_route and artifact_compatible:
                    accelerator_count += 1
                if capability.get("mtp") is True:
                    modes.append({
                        "id": "mtp", "label": "MTP", "kind": "accelerator",
                        "available": artifact_compatible,
                        "detail": str(capability.get("mtpReason") or "Verified MTP route"),
                    })
                    accelerator_count += 1
                if engine_id == "omlx" and capability.get("dflash") is True:
                    modes.append({
                        "id": "dflash2", "label": "DFlash 2", "kind": "accelerator",
                        "available": artifact_compatible,
                        "detail": str(capability.get("dflashReason") or "Exact DFlash 2 pair"),
                    })
                    accelerator_count += 1
                if engine_id == "omlx" and capability.get("anePrefill") is True:
                    modes.append({
                        "id": "ane-prefill", "label": "ANE prefill", "kind": "accelerator",
                        "available": artifact_compatible,
                        "detail": str(capability.get("aneReason") or "Locally verified ANE prefill split"),
                    })
                    accelerator_count += 1

                surface_reports: list[dict[str, Any]] = []
                for surface_id, surface_descriptor in self.policy.surfaces.items():
                    public_surface = surface_descriptors[surface_id]
                    surface_installed = public_surface["installed"] is True
                    matrix = self.surfaces.resolved_support(engine_id, surface_id, capability)
                    matrix_supported = matrix.get("supported") is True
                    reasoning_key = "codexReasoning" if surface_id == "codex" else "agentReasoning"
                    reasoning = capability.get(reasoning_key)
                    reasoning_ready = isinstance(reasoning, list) and bool(reasoning)
                    supported = bool(
                        runnable and surface_installed and matrix_supported and reasoning_ready
                    )
                    if supported:
                        launchable_routes += 1
                        route_reason = str(matrix.get("reason") or "Compatible")
                    elif not runtime_installed:
                        route_reason = f"Install {descriptor.label} first."
                    elif not artifact_compatible:
                        route_reason = engine_reason
                    elif not surface_installed:
                        route_reason = f"{surface_descriptor.label} is not installed."
                    elif not matrix_supported:
                        route_reason = str(matrix.get("reason") or "This protocol route is unsupported.")
                    elif not reasoning_ready:
                        route_reason = "No enforceable reasoning mode is advertised for this route."
                    else:
                        route_reason = "This route is unavailable."
                    surface_reports.append({
                        "id": surface_id,
                        "label": surface_descriptor.label,
                        "installed": surface_installed,
                        "builtIn": public_surface["builtIn"],
                        "protocol": surface_descriptor.protocol,
                        "supported": supported,
                        "reason": route_reason,
                        "reasoning": list(reasoning) if isinstance(reasoning, list) else [],
                    })

                history_count = capability.get("benchmarkHistoryCount")
                if not isinstance(history_count, int) or isinstance(history_count, bool) or history_count < 0:
                    history_count = 0
                benchmark = capability.get("localBenchmark")
                if not isinstance(benchmark, dict):
                    benchmark = None
                if benchmark and history_count == 0:
                    history_count = 1
                evidence_count += history_count
                evidence = {
                    "savedRuns": history_count,
                    "latest": None if not benchmark else {
                        "winner": str(benchmark.get("winner") or ""),
                        "winnerLabel": self.evidence.public_mode_label(
                            engine_id, str(benchmark.get("winner") or "ar")
                        ),
                        "suite": str(benchmark.get("suite") or ""),
                        "createdAt": str(benchmark.get("createdAt") or ""),
                        "recommendation": str(benchmark.get("recommendation") or ""),
                        "qualityPassed": benchmark.get("qualityPassed") is True,
                    },
                }
                engine_reports.append({
                    "id": engine_id,
                    "label": descriptor.label,
                    "protocol": descriptor.protocol,
                    "runtimeInstalled": runtime_installed,
                    "artifactCompatible": artifact_compatible,
                    "runnable": runnable,
                    "experimental": experimental,
                    "status": engine_status,
                    "reason": engine_reason,
                    "runtimeVersion": str(capability.get("runtimeVersion") or ""),
                    "performanceEvidence": performance_evidence,
                    "hostSupport": host_support,
                    "qualification": {
                        "readiness": qualification_readiness,
                        "realCheckpointVerified": capability.get("realCheckpointVerified") is True,
                        "largeDownloadRecommended": qualification_policy.get("large_download_recommended") is True,
                    } if engine_id == "freetoken" and capability.get("native") is True else None,
                    "modes": modes,
                    "surfaces": surface_reports,
                    "evidence": evidence,
                })

            checks = [{
                "id": "artifact",
                "label": "Served model" if remote_model else "Artifact completeness",
                "state": "pass" if model_ready else "blocked",
                "detail": (
                    "Advertised by the connected FreeToken server during model discovery."
                    if remote_model and model_ready else
                    str(model.get("status") or ("Ready" if model_ready else "Incomplete artifact"))
                ),
            }, {
                "id": "engines",
                "label": "Connected engine" if remote_model else "Installed engines",
                "state": "pass" if launchable_engines else "blocked",
                "detail": (
                    f"{launchable_engines} connected engine route is available."
                    if remote_model and launchable_engines else
                    "The connected FreeToken route is unavailable."
                    if remote_model else
                    f"{launchable_engines} installed engine{'s' if launchable_engines != 1 else ''} can load this artifact."
                    if launchable_engines else "No installed engine can load this artifact."
                ),
            }, {
                "id": "surfaces",
                "label": "Launchable work surfaces",
                "state": "pass" if launchable_routes else "blocked",
                "detail": (
                    f"{launchable_routes} engine/surface route{'s' if launchable_routes != 1 else ''} are ready."
                    if launchable_routes else "No installed engine and work-surface route is ready."
                ),
            }]
            if remote_model:
                checks.append({
                    "id": "performance", "label": "Performance reporting",
                    "state": "pass",
                    "detail": "Live TPS is reported for this connected route; remote-host and network time stay out of Mac-only Benchmark Lab.",
                })
            elif accelerator_count == 0:
                checks.append({
                    "id": "acceleration", "label": "Acceleration evidence",
                    "state": "advisory",
                    "detail": (
                        "The fixed DFlash + Weaver route is not currently runnable."
                        if model.get("uzuNative") is True else
                        "No verified speculative accelerator is available; standard AR remains valid."
                    ),
                })
            elif evidence_count == 0:
                checks.append({
                    "id": "acceleration", "label": "Acceleration evidence",
                    "state": "advisory",
                    "detail": f"{accelerator_count} accelerator route{'s' if accelerator_count != 1 else ''} are available, but none has matching saved benchmark evidence.",
                })
            else:
                checks.append({
                    "id": "acceleration", "label": "Acceleration evidence",
                    "state": "pass",
                    "detail": f"{evidence_count} matching saved benchmark run{'s' if evidence_count != 1 else ''} cover available local routes.",
                })

            if any(check["state"] == "blocked" for check in checks):
                doctor_state = "blocked"
                if not model_ready:
                    headline = "Finish or repair this artifact before launch."
                    next_action = "Rescan after every required weight shard is present."
                elif not launchable_engines:
                    headline = "No installed engine can load this model yet."
                    next_action = "Review the engine reasons below, then install or select a compatible runtime."
                else:
                    headline = "The model loads, but no complete work-surface route is ready."
                    next_action = "Install a compatible agent launcher or use the built-in Chat route where supported."
            elif any(check["state"] == "advisory" for check in checks):
                doctor_state = "attention"
                headline = "Usable now, with an optimisation advisory."
                next_action = (
                    "Run Benchmark Lab before preferring an accelerator automatically."
                    if accelerator_count else
                    "Use the fixed DFlash + Weaver route after its runtime checks pass."
                    if model.get("uzuNative") is True else
                    "Use standard AR; no speculative speedup is claimed for this artifact."
                )
            else:
                doctor_state = "ready"
                headline = (
                    "Ready on the connected FreeToken route."
                    if remote_model else "Ready across installed local routes."
                )
                next_action = (
                    "Choose FreeToken below to put this served model into the launcher without starting it. Reconnect to refresh the server's model list."
                    if remote_model else
                    "Choose an engine below to put this model into the launcher without starting it."
                )

            reports.append({
                "id": str(model.get("id") or ""),
                "name": str(model.get("name") or "Unnamed model"),
                "path": str(model.get("path") or ""),
                "artifact": str(model.get("artifact") or ""),
                "origins": [str(item) for item in (model.get("origins") or [])],
                "format": str(model.get("format") or "unknown"),
                "architecture": str(model.get("architecture") or "unknown"),
                "modelType": str(model.get("modelType") or "unknown"),
                "nativeContext": model.get("nativeContext") if isinstance(model.get("nativeContext"), int) else None,
                "quantization": str(model.get("quantization") or "Unknown"),
                "size": model.get("size") if isinstance(model.get("size"), int) else 0,
                "sizeLabel": str(model.get("sizeLabel") or self.values.display_size(model.get("size") or 0)),
                "ready": model_ready,
                "status": str(model.get("status") or "Unknown"),
                "engines": engine_reports,
                "counts": {
                    "launchableEngines": launchable_engines,
                    "launchableRoutes": launchable_routes,
                    "accelerators": accelerator_count,
                    "evidenceRuns": evidence_count,
                },
                "doctor": {
                    "state": doctor_state,
                    "headline": headline,
                    "nextAction": next_action,
                    "checks": checks,
                },
            })

        summary = {
            "models": len(reports),
            "ready": sum(item["doctor"]["state"] == "ready" for item in reports),
            "attention": sum(item["doctor"]["state"] == "attention" for item in reports),
            "blocked": sum(item["doctor"]["state"] == "blocked" for item in reports),
            "launchableRoutes": sum(item["counts"]["launchableRoutes"] for item in reports),
        }
        return {
            "schemaVersion": self.policy.general.model_library_schema_version,
            "readOnly": True,
            "summary": summary,
            "models": reports,
            "engines": list(engine_descriptors.values()),
            "workSurfaces": list(surface_descriptors.values()),
        }
