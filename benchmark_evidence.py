"""Exact saved-benchmark evidence, tuning replay and route eligibility.

The verifier owns comparison semantics. The controller supplies a frozen
policy and individual live artifact/runtime/qualification callbacks; there is
no controller import, namespace injection, process ownership or model launch.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, fields
import json
import math
from pathlib import Path
import re
import secrets
import statistics
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

import generation_metrics
from sampling_contract import (
    SAMPLING_CONTRACT_SCHEMA_VERSION, SamplingContractError,
    load_sampling_contract, sampling_fingerprint,
)


class _FrozenList(list):
    """Preserve list comparison/JSON semantics without writable policy aliases."""
    def _readonly(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("Benchmark policy sequences are immutable")
    __setitem__ = __delitem__ = append = clear = extend = insert = pop = remove = reverse = sort = __iadd__ = __imul__ = _readonly
    def __deepcopy__(self, memo: dict[int, Any]) -> _FrozenList:
        return self


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return _FrozenList(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


def _closed_unload_ports_verified(receipt: dict[str, Any], *, allow_empty: bool) -> bool:
    checked = receipt.get("checkedPorts")
    closed = receipt.get("closedPorts")
    # The complete valid TCP port space bounds decoding work without inventing
    # a backend-specific number of listeners. The producer uses sorted unique
    # ports, and every one must have been observed closed.
    if (
        not isinstance(checked, list) or not int(not allow_empty) <= len(checked) <= 65_535
        or not isinstance(closed, list) or len(closed) != len(checked)
        or any(type(port) is not int or not 1 <= port <= 65_535 for port in checked)
        or any(type(port) is not int or not 1 <= port <= 65_535 for port in closed)
    ):
        return False
    return checked == sorted(set(checked)) and closed == checked


def unload_receipt_issue(receipt: Any, backend: str) -> str | None:
    """Validate fresh or historical explicit cleanup proof without doing I/O.

    Historical callers retain compatibility by not invoking this helper for an
    absent receipt. A shared LM Studio model has a separate, versioned ownership
    contract: its launcher model unloads, while the unowned server stays open.
    An engine name alone never changes the owned-process cleanup requirements.
    """
    if not isinstance(receipt, dict):
        return "The route-unload receipt is not a dictionary."
    shared_model = receipt.get("kind") == "shared-lmstudio-model-v1"
    if "kind" in receipt and not shared_model:
        return "The route-unload receipt has an unsupported ownership contract."
    if shared_model:
        if backend != "lmstudio":
            return "The shared-model unload receipt does not match the measured engine."
        flags = ("clean", "managerIdle", "modelUnloaded", "sharedServerRetained", "ownedPortsClosed")
        if any(key in receipt for key in ("processExited", "processGroupExited", "portsClosed")):
            return "The shared-model unload receipt mixes model and process ownership claims."
        identifier = receipt.get("modelIdentifier")
        port = receipt.get("sharedServerPort")
        if (
            not isinstance(identifier, str)
            or re.fullmatch(r"llm-launcher-[0-9a-f]{8}", identifier) is None
            or type(port) is not int or not 1 <= port <= 65_535
        ):
            return "The shared-model unload receipt has an invalid model or server identity."
    else:
        flags = ("clean", "processExited", "processGroupExited", "managerIdle", "portsClosed")
    if any(receipt.get(key) is not True for key in flags):
        return "The route-unload receipt does not prove every cleanup condition."
    if not _closed_unload_ports_verified(receipt, allow_empty=shared_model):
        return "The route-unload receipt has invalid or unclosed owned listeners."
    if shared_model and receipt["sharedServerPort"] in receipt["checkedPorts"]:
        return "The shared-model unload receipt claims the retained server listener was closed."
    return None


@dataclass(frozen=True)
class EvidencePolicy:
    benchmark_comparison_contract_version: int
    benchmark_dflash_tuner_draft_quants: tuple[str, ...]
    benchmark_dflash_tuner_max_candidates: int
    benchmark_dflash_tuner_read_versions: frozenset[int]
    benchmark_dflash_tuner_verify_modes: tuple[str, ...]
    benchmark_engine_setting_keys: Mapping[str, tuple[str, ...]]
    benchmark_memory_meaningful_bytes: int
    benchmark_minimum_speedup: float
    benchmark_mtp_tuner_cutoffs: tuple[float, ...]
    benchmark_mtp_tuner_max_candidates: int
    benchmark_mtp_tuner_read_versions: frozenset[int]
    benchmark_probe_contract: Mapping[str, Any]
    benchmark_suites: Mapping[str, Mapping[str, Any]]
    dflash2_upstream_performance_evidence: Mapping[str, Any]
    engine_settings_sweep_max_generated_requests: int
    engine_settings_sweep_max_model_loads: int
    engine_settings_sweep_version: int
    llamacpp_ple_memory_ceiling_bytes: int
    mtplx_long_context_2111_route: str
    mtplx_long_context_2111_sweep_version: int
    mtplx_long_context_64k_suite: str
    mtplx_long_context_baseline_env: Mapping[str, str]
    mtplx_long_context_candidate_env: Mapping[str, str]
    mtplx_long_context_default_route: str
    mtplx_long_context_minimum: int
    mtplx_long_context_minimum_prompt: int
    mtplx_long_context_target_prompt: int
    mtplx_mtp_depth_sweep_max_candidates: int
    mtplx_mtp_depth_sweep_version: int
    mtplx_operator_measurement_result_keys: tuple[str, ...]
    mtplx_operator_measurement_sample_keys: tuple[str, ...]
    omlx_expert_resident_percentages: tuple[float, ...]
    route_evidence_schema_version: int
    route_qualification_agentic_suites: frozenset[str]
    route_qualification_scenarios: Sequence[str]
    sampling_evidence_schema_version: int
    sampling_record_evidence_keys: tuple[str, ...]
    ssd_streaming_backends: tuple[str, ...]
    ssd_streaming_prefill_sizes: tuple[int, ...]
    uzu_model_commit: str
    uzu_model_page_url: str
    uzu_model_registry_id: str
    uzu_model_toolchain_version: str
    uzu_sandbox_profile_sha256: str
    uzu_upstream_hardware: str
    uzu_upstream_output_tps: float
    whallm_benchmark_url: str

    def __post_init__(self) -> None:
        for name in (
            'benchmark_comparison_contract_version',
            'benchmark_dflash_tuner_max_candidates',
            'benchmark_memory_meaningful_bytes',
            'benchmark_mtp_tuner_max_candidates',
            'engine_settings_sweep_max_generated_requests',
            'engine_settings_sweep_max_model_loads',
            'engine_settings_sweep_version',
            'llamacpp_ple_memory_ceiling_bytes',
            'mtplx_long_context_2111_sweep_version',
            'mtplx_long_context_minimum',
            'mtplx_long_context_minimum_prompt',
            'mtplx_long_context_target_prompt',
            'mtplx_mtp_depth_sweep_max_candidates',
            'mtplx_mtp_depth_sweep_version',
            'route_evidence_schema_version',
            'sampling_evidence_schema_version',
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"Benchmark policy {name} must be a positive integer")
        if (type(self.benchmark_minimum_speedup) not in (int, float)
                or not math.isfinite(self.benchmark_minimum_speedup)
                or self.benchmark_minimum_speedup < 1):
            raise ValueError("Benchmark speedup policy must be finite and at least one")
        if (type(self.uzu_upstream_output_tps) not in (int, float)
                or not math.isfinite(self.uzu_upstream_output_tps)
                or self.uzu_upstream_output_tps <= 0):
            raise ValueError("Upstream output rate must be finite and positive")
        for item in fields(self):
            object.__setattr__(self, item.name, _freeze(getattr(self, item.name)))


@dataclass(frozen=True)
class EvidenceServices:
    _engine_settings_candidate_key: Callable[..., Any]
    _mtplx_long_context_capability_matches: Callable[..., Any]
    _ordered_unique: Callable[..., Any]
    bounded_integer: Callable[..., Any]
    cross_engine_benchmark_measurement: Callable[..., Any]
    dflash2_draft_complete: Callable[..., Any]
    dflash2_draft_shape: Callable[..., Any]
    dflash2_pair_fingerprint: Callable[..., Any]
    dflash2_tuning_block_sizes: Callable[..., Any]
    dflash2_tuning_candidate_key: Callable[..., Any]
    hardware_fingerprint: Callable[..., Any]
    lmstudio_mtp_controls: Callable[..., Any]
    lmstudio_mtp_tuning_candidate_key: Callable[..., Any]
    lmstudio_mtp_tuning_depths: Callable[..., Any]
    matching_dflash2_draft: Callable[..., Any]
    mtplx_long_context_2111_contract: Callable[..., Any]
    omlx_supports_dflash2: Callable[..., Any]
    physical_memory_bytes: Callable[..., Any]
    read_json: Callable[..., Any]
    route_qualification_metrics: Callable[..., Any]
    route_qualification_record_is_fresh: Callable[..., Any]
    route_qualification_sample_tokens: Callable[..., Any]
    semantic_version_key: Callable[..., Any]
    summarize_agentic_samples: Callable[..., Any]
    uzu_listener_protection_ready: Callable[..., Any]
    uzu_qualification_memory_ceiling_supported: Callable[..., Any]
    weight_completeness: Callable[..., Any]
    runtime_version: Callable[[str], str]


class EvidenceVerifier:
    def __init__(self, policy: EvidencePolicy, services: EvidenceServices) -> None:
        self.policy = policy
        self.services = services

    def benchmark_engine_settings(self, backend: str, options: dict[str, Any] | None) -> dict[str, Any]:
        """Return the fixed, engine-owned controls that shaped one measurement."""
        source = options if isinstance(options, dict) else {}
        return {
            key: copy.deepcopy(source[key])
            for key in self.policy.benchmark_engine_setting_keys.get(backend, ())
            if key in source
        }

    def benchmark_runtime_integrity_issue(self, record: dict[str, Any]) -> str | None:
        """Reject only evidence covered by a reviewed upstream runtime disclosure."""
        if str(record.get("backend") or "") != "mtplx":
            return None
        runtime_key = self.services.semantic_version_key(str(record.get("runtimeVersion") or ""))
        if runtime_key[:3] != (2, 9, 0):
            return None
        settings = record.get("engineSettings")
        profile = str(settings.get("profile") or "") if isinstance(settings, dict) else ""
        if profile and profile != "turbo":
            return None
        return (
            "MTPLX 2.9.0 did not apply its complete Turbo fast path. Update to 2.9.1 and "
            "repeat this route; a legacy 2.9.0 record without a captured profile is treated as affected."
        )

    def benchmark_probe_integrity_issue(self, record: dict[str, Any]) -> str | None:
        """Older core-engine probes could inherit the workload's sampling instead.

        Operator v5 was introduced with the corrected wire request. Its full sweep
        still has to pass the normal verifier; this exception supplies no speed or
        correctness proof by itself. Uzu has a separate packaged-sampler contract.
        """
        if record.get("backend") not in {"omlx", "lmstudio", "mtplx"}:
            return None
        if record.get("probeContract") == self.policy.benchmark_probe_contract:
            return None
        sweep = record.get("mtplxOperatorSweep")
        if (
            "probeContract" not in record
            and record.get("backend") == "mtplx"
            and record.get("kind") == "mtplx-long-context-operator-tuning"
            and isinstance(sweep, dict)
            and type(sweep.get("version")) is int
            and sweep["version"] == 5
        ):
            return None
        return (
            "This saved run does not verify the corrected correctness-test sampling contract. "
            "Its measurements remain in history, but re-test this route before using "
            "it to choose settings automatically."
        )

    def benchmark_integrity_issue(self, record: dict[str, Any]) -> str | None:
        known = self.benchmark_runtime_integrity_issue(record) or self.benchmark_probe_integrity_issue(record)
        if known:
            return known
        backend = str(record.get("backend") or "")
        modes = record.get("modes")
        if isinstance(modes, dict) and any(
            isinstance(mode, dict) and "unloadEvidence" in mode
            and unload_receipt_issue(mode["unloadEvidence"], backend) is not None
            for mode in modes.values()
        ):
            return (
                "This saved run contains a failed or invalid route-unload receipt. "
                "Its measurements remain in history, but repeat the route before "
                "using it to choose settings automatically."
            )
        if backend in generation_metrics.BUFFERED_GENERATION_BACKENDS and (
            record.get("selectionPreference") == "throughput"
            or record.get("selectionMetric") == "generation-tokens-per-second"
        ):
            modes = record.get("modes")
            if not isinstance(modes, dict) or not modes or any(
                not isinstance(mode, dict) or not isinstance(mode.get("samples"), list)
                or generation_metrics.median_generation_tps(mode["samples"], backend) is None
                for mode in modes.values()
            ):
                return "This saved generation comparison used delivery timing without native request proof. Its end-to-end measurements remain historical; repeat the route before selecting it for generation TPS."
        return None

    def benchmark_record_identity(self, record: dict[str, Any]) -> tuple[Any, ...]:
        """Identify one repeatable, goal-bound route without collapsing its history."""
        qualification_output_contract = (
            record.get("configuredOutputLimit"),
            record.get("measuredRequestMaxTokens"),
        ) if (
            record.get("kind") == "route-qualification"
            and record.get("backend") in {"llamacpp", "uzu"}
        ) else (None, None)
        return (
            record.get("backend"), record.get("modelFingerprint"),
            record.get("ssdComparisonIdentity"),
            record.get("runtimeVersion"), record.get("hardwareFingerprint"),
            record.get("client"), record.get("reasoning"), record.get("targetKV"),
            record.get("samplingFingerprint"), record.get("contextMin"), record.get("contextMax"),
            record.get("outputMin"), record.get("outputMax"), record.get("suite"),
            record.get("selectionPreference"),
            json.dumps(record.get("engineSettings") or {}, sort_keys=True, separators=(",", ":")),
            json.dumps(record.get("scenarioContract") or [], sort_keys=True, separators=(",", ":")),
            *qualification_output_contract,
        )

    def latest_benchmark_records_by_identity(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep model payloads compact while the full history remains server-side."""
        latest: dict[tuple[Any, ...], dict[str, Any]] = {}
        for record in sorted(records, key=lambda item: str(item.get("createdAt") or "")):
            latest[self.benchmark_record_identity(record)] = record
        return [
            copy.deepcopy(item)
            for item in sorted(latest.values(), key=lambda value: str(value.get("createdAt") or ""))
        ]

    def matching_benchmark_records(self,
        records: list[dict[str, Any]], backend: str, model_fingerprint: str,
        runtime_version: str, capability: dict[str, Any], machine: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return evidence produced for this exact artifact/runtime/Mac."""
        if not model_fingerprint or not runtime_version:
            return []
        machine = machine or self.services.hardware_fingerprint()
        matches = [
            record for record in records
            if record.get("scope") == "local"
            and record.get("backend") == backend
            and record.get("modelFingerprint") == model_fingerprint
            and record.get("runtimeVersion") == runtime_version
            and record.get("hardwareFingerprint") == machine
            and self.benchmark_integrity_issue(record) is None
            and (
                backend not in self.policy.ssd_streaming_backends
                or (
                    record.get("ssdStreaming") is True
                    and record.get("ssdComparisonIdentity") == capability.get("comparisonIdentity")
                )
            )
            and (
                "dflash2" not in (record.get("comparedModes") or [])
                or record.get("pairFingerprint") == capability.get("dflashPairFingerprint")
            )
        ]
        return [copy.deepcopy(item) for item in sorted(matches, key=lambda item: str(item.get("createdAt") or ""))]

    def matching_benchmark_record(self,
        records: list[dict[str, Any]], backend: str, model_fingerprint: str,
        runtime_version: str, capability: dict[str, Any], machine: str | None = None,
    ) -> dict[str, Any] | None:
        matches = self.matching_benchmark_records(
            records, backend, model_fingerprint, runtime_version, capability, machine,
        )
        return matches[-1] if matches else None

    def dflash2_capability_valid(self, model: dict[str, Any], capability: dict[str, Any]) -> bool:
        """Revalidate a scanned DFlash 2 pairing immediately before use."""
        if capability.get("dflash") is not True or capability.get("dflashVersion") != "2":
            return False
        runtime_version = str(capability.get("dflashRuntimeVersion") or "")
        current_runtime = self.services.runtime_version("omlx")
        if (
            not self.services.omlx_supports_dflash2(runtime_version)
            or not self.services.omlx_supports_dflash2(current_runtime)
            or not secrets.compare_digest(runtime_version, current_runtime)
        ):
            return False
        try:
            target_path = Path(str(model["path"])).resolve(strict=True)
            draft_path = Path(str(capability["dflashDraftPath"])).resolve(strict=True)
        except (KeyError, OSError, RuntimeError):
            return False
        target_config = self.services.read_json(target_path / "config.json")
        draft_config = self.services.read_json(draft_path / "config.json")
        ready, _status, _size = self.services.weight_completeness(draft_path, draft_config)
        if not ready or not self.services.dflash2_draft_complete(draft_path, draft_config):
            return False
        pair = self.services.matching_dflash2_draft(target_path, target_config, [{"path": str(draft_path), "config": draft_config}])
        if not pair:
            return False
        expected = self.services.dflash2_pair_fingerprint(target_path, target_config, draft_path, draft_config)
        if not secrets.compare_digest(str(capability.get("dflashPairFingerprint") or ""), expected):
            return False
        block = capability.get("dflashBlockSize")
        maximum = capability.get("dflashMaxBlockSize")
        draft_shape = self.services.dflash2_draft_shape(draft_config)
        if not draft_shape:
            return False
        return bool(
            isinstance(block, int) and not isinstance(block, bool)
            and isinstance(maximum, int) and not isinstance(maximum, bool)
            and 1 <= block <= maximum <= int(draft_shape["block_size"])
        )

    def dflash2_benchmark_verified(self,
        capability: dict[str, Any],
        evidence: dict[str, Any] | None = None,
        benchmark: dict[str, Any] | None = None,
    ) -> bool:
        """Accept only a structured local result tied to this exact pair/runtime."""
        benchmark = benchmark or capability.get("dflashBenchmark")
        if not isinstance(benchmark, dict):
            return False
        if benchmark.get("targetKV") != "off":
            # AR's quantised cache and DFlash's full-precision cache are not the
            # same target contract, even when their nominal selector values match.
            return False
        try:
            speedup = float(benchmark.get("endToEndSpeedup"))
        except (TypeError, ValueError):
            return False
        context = (evidence or {}).get("context")
        if not isinstance(context, int) or isinstance(context, bool):
            return False
        context_min = benchmark.get("contextMin")
        context_max = benchmark.get("contextMax")
        if not isinstance(context_min, int) or not isinstance(context_max, int) or not context_min <= context <= context_max:
            return False
        benchmark_client = benchmark.get("client")
        if benchmark_client not in {None, "any", (evidence or {}).get("client")}:
            return False
        output = (evidence or {}).get("output")
        output_min = benchmark.get("outputMin")
        output_max = benchmark.get("outputMax")
        if (
            not isinstance(output, int) or isinstance(output, bool)
            or not isinstance(output_min, int) or not isinstance(output_max, int)
            or not output_min <= output <= output_max
        ):
            return False
        benchmark_reasoning = benchmark.get("reasoning")
        if benchmark_reasoning not in {"any", (evidence or {}).get("reasoning")}:
            return False
        if benchmark.get("targetKV") != (evidence or {}).get("kv"):
            return False
        if benchmark.get("samplingFingerprint") != (evidence or {}).get("samplingFingerprint"):
            return False
        settings = benchmark.get("settings")
        if not self.dflash2_benchmark_settings_verified(capability, settings):
            return False
        compared_modes = benchmark.get("comparedModes")
        required_modes = {"ar", "dflash2"}
        if capability.get("mtp") is True:
            required_modes.add("mtp")
        if not isinstance(compared_modes, list) or not required_modes.issubset({str(value) for value in compared_modes}):
            return False
        return bool(
            benchmark.get("scope") == "local"
            and benchmark.get("winner") == "dflash2"
            and benchmark.get("qualityPassed") is True
            and speedup > 1.0
            and benchmark.get("pairFingerprint") == capability.get("dflashPairFingerprint")
            and benchmark.get("runtimeVersion") == capability.get("dflashRuntimeVersion")
        )

    def _agentic_benchmark_contract_verified(self,
        benchmark: dict[str, Any], required_modes: set[str],
    ) -> bool:
        workload = benchmark.get("workloadKind")
        if workload in {None, "throughput"}:
            return True
        if (
            workload != "agentic"
            or benchmark.get("suite") not in self.policy.route_qualification_agentic_suites
            or benchmark.get("scenarioContract")
            != self.policy.route_qualification_scenarios
        ):
            return False
        modes = benchmark.get("modes")
        if not isinstance(modes, dict):
            return False
        expected = self.policy.route_qualification_scenarios
        numeric_metrics = {
            "coldTTFTSeconds", "warmPrefixTTFTSeconds", "prefixReuseFactor",
            "toolIngestTTFTSeconds", "steadyTurnTTFTSeconds", "toolReuseFactor",
        }
        for mode in required_modes:
            result = modes.get(mode)
            if not isinstance(result, dict):
                return False
            samples = result.get("samples")
            metrics = result.get("agenticMetrics")
            if (
                not isinstance(samples, list) or len(samples) != len(expected)
                or [sample.get("scenario") for sample in samples if isinstance(sample, dict)] != expected
                or not isinstance(metrics, dict)
                or metrics.get("cacheTelemetryAvailable") not in {True, False}
            ):
                return False
            for key in numeric_metrics:
                value = metrics.get(key)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) <= 0:
                    return False
        return True

    def mtp_benchmark_settings_verified(self,
        backend: str, capability: dict[str, Any], settings: Any,
    ) -> bool:
        """Validate the complete tuning identity for one measured MTP route."""
        if not isinstance(settings, dict):
            return False
        if backend == "lmstudio":
            if set(settings) != {
                "depth", "mtpMinTokens", "mtpMinContinueProbability",
            }:
                return False
            try:
                return self.services.lmstudio_mtp_controls(settings, capability) == settings
            except (TypeError, ValueError):
                return False
        allowed_keys = {"depth"}
        if backend == "mtplx" and "mtplxOperatorRoute" in settings:
            allowed_keys.add("mtplxOperatorRoute")
            if settings.get("mtplxOperatorRoute") not in {
                self.policy.mtplx_long_context_default_route,
                self.policy.mtplx_long_context_2111_route,
            }:
                return False
        return bool(
            set(settings) == allowed_keys
            and isinstance(settings.get("depth"), int)
            and not isinstance(settings.get("depth"), bool)
            and 1 <= settings["depth"] <= int(capability.get("depthMax") or 1)
        )

    def mtplx_mtp_depth_candidates(self, capability: dict[str, Any]) -> list[int]:
        """Return every verified MTPLX draft depth, with the artifact default first."""
        maximum = self.services.bounded_integer(
            capability.get("depthMax"), 1, 1,
            self.policy.mtplx_mtp_depth_sweep_max_candidates, "MTPLX MTP maximum depth",
        )
        default = self.services.bounded_integer(
            capability.get("depth"), maximum, 1, maximum, "MTPLX MTP default depth",
        )
        return self.services._ordered_unique([default, *range(1, maximum + 1)])

    def mtplx_mtp_depth_sweep_verified(self,
        capability: dict[str, Any], benchmark: dict[str, Any], mode_settings: Any,
    ) -> bool:
        """Require a complete, untampered D1…Dmax search before trusting its winner."""
        sweep = benchmark.get("mtpDepthSweep")
        if not isinstance(sweep, dict):
            return False
        try:
            expected_depths = self.mtplx_mtp_depth_candidates(capability)
        except (TypeError, ValueError):
            return False
        selected_settings = mode_settings.get("mtp") if isinstance(mode_settings, dict) else None
        candidates = sweep.get("candidates")
        if (
            sweep.get("version") != self.policy.mtplx_mtp_depth_sweep_version
            or sweep.get("strategy") != "exhaustive-verified-depths"
            or sweep.get("selectionMetric") != benchmark.get("selectionMetric")
            or sweep.get("selectionMetric") not in {
                "generation-tokens-per-second", "end-to-end-tokens-per-second",
            }
            or sweep.get("complete") is not True
            or sweep.get("resourceComparable") is not True
            or sweep.get("depthCandidates") != expected_depths
            or sweep.get("candidateCount") != len(expected_depths)
            or sweep.get("maximumCandidates") != self.policy.mtplx_mtp_depth_sweep_max_candidates
            or sweep.get("selectedSettings") != selected_settings
            or not isinstance(candidates, list)
            or len(candidates) != len(expected_depths)
        ):
            return False
        seen: set[int] = set()
        selected = 0
        for candidate in candidates:
            if not isinstance(candidate, dict):
                return False
            depth = candidate.get("depth")
            settings = candidate.get("settings")
            if (
                isinstance(depth, bool) or not isinstance(depth, int)
                or depth in seen or depth not in expected_depths
                or settings != {"depth": depth}
                or candidate.get("selectionMetric") != sweep.get("selectionMetric")
                or candidate.get("qualityMatchesAR") not in {True, False}
                or candidate.get("resourceComparable") is not True
                or candidate.get("selected") not in {True, False}
            ):
                return False
            seen.add(depth)
            for metric in (
                "medianSpeedupVsAR", "worstCaseSpeedupVsAR",
                "medianDecodeTokensPerSecond",
                "medianEndToEndTokensPerSecond",
            ):
                value = candidate.get(metric)
                if (
                    isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(float(value)) or float(value) <= 0
                ):
                    return False
            if candidate.get("selected") is True:
                selected += 1
                if settings != selected_settings or depth != sweep.get("selectedDepth"):
                    return False
        return seen == set(expected_depths) and selected == 1

    def _positive_finite_number(self, value: Any) -> bool:
        return bool(
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and math.isfinite(float(value))
            and float(value) > 0
        )

    def _mtplx_operator_measurement_evidence(self,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Project the raw route facts needed to re-derive an operator winner.

        The selected route is also stored in ``modes.mtp`` for the normal result
        UI, but the unselected route would otherwise survive only as duplicated
        summary numbers. Retaining this small, text-free projection lets record
        verification recompute both candidates instead of trusting those numbers.
        """
        raw_samples = result.get("samples")
        samples = raw_samples if isinstance(raw_samples, list) else []
        return {
            "qualityHash": result.get("qualityHash"),
            "qualityCompletionTokens": result.get("qualityCompletionTokens"),
            **{
                key: copy.deepcopy(result.get(key))
                for key in self.policy.mtplx_operator_measurement_result_keys
            },
            "samples": [
                {
                    key: copy.deepcopy(sample.get(key))
                    for key in self.policy.mtplx_operator_measurement_sample_keys
                }
                for sample in samples if isinstance(sample, dict)
            ],
        }

    def _mtplx_operator_measurement_verified(self,
        measurement: Any,
    ) -> dict[str, Any] | None:
        """Recompute every timing aggregate consumed by route and engine ranking."""
        expected_keys = {
            "qualityHash", "qualityCompletionTokens", "samples",
            *self.policy.mtplx_operator_measurement_result_keys,
        }
        if not isinstance(measurement, dict) or set(measurement) != expected_keys:
            return None
        quality_hash = measurement.get("qualityHash")
        quality_tokens = measurement.get("qualityCompletionTokens")
        samples = measurement.get("samples")
        if (
            not isinstance(quality_hash, str)
            or re.fullmatch(r"[0-9a-f]{64}", quality_hash) is None
            or isinstance(quality_tokens, bool)
            or not isinstance(quality_tokens, int)
            or quality_tokens <= 0
            or not isinstance(samples, list)
            or len(samples) != len(self.policy.route_qualification_scenarios)
        ):
            return None
        decode: list[float] = []
        end_to_end: list[float] = []
        ttft: list[float] = []
        for index, sample in enumerate(samples):
            if not isinstance(sample, dict) or set(sample) != set(
                self.policy.mtplx_operator_measurement_sample_keys
            ):
                return None
            prompt = sample.get("promptTokens")
            target = sample.get("targetPromptTokens")
            completion = sample.get("completionTokens")
            requested = sample.get("requestedMaxTokens")
            first = sample.get("ttftSeconds")
            total = sample.get("totalSeconds")
            decode_tps = sample.get("decodeTokensPerSecond")
            end_to_end_tps = sample.get("endToEndTokensPerSecond")
            cached = sample.get("cachedPromptTokens")
            cache_rate = sample.get("cacheHitRate")
            if (
                sample.get("scenario") != self.policy.route_qualification_scenarios[index]
                or sample.get("authoritativeUsage") is not True
                or isinstance(prompt, bool) or not isinstance(prompt, int) or prompt <= 0
                or isinstance(target, bool) or not isinstance(target, int) or target <= 0
                or isinstance(completion, bool) or not isinstance(completion, int) or completion <= 0
                or isinstance(requested, bool) or not isinstance(requested, int)
                or requested != self.policy.benchmark_suites[self.policy.mtplx_long_context_64k_suite]["maxTokens"]
                or completion > requested
                or not self._positive_finite_number(first)
                or not self._positive_finite_number(total)
                or float(total) <= float(first)
                or not self._positive_finite_number(decode_tps)
                or not self._positive_finite_number(end_to_end_tps)
                or (
                    cached is not None
                    and (
                        isinstance(cached, bool) or not isinstance(cached, int)
                        or cached < 0 or cached > prompt
                    )
                )
                or (
                    cache_rate is not None
                    and (
                        isinstance(cache_rate, bool)
                        or not isinstance(cache_rate, (int, float))
                        or not math.isfinite(float(cache_rate))
                        or not 0 <= float(cache_rate) <= 1
                    )
                )
            ):
                return None
            expected_decode = round(
                max(1, completion - 1)
                / max(0.000_001, float(total) - float(first)),
                4,
            )
            expected_end_to_end = round(completion / float(total), 4)
            if (
                abs(float(decode_tps) - expected_decode)
                > max(0.01, float(decode_tps) * 0.001)
                or abs(float(end_to_end_tps) - expected_end_to_end)
                > max(0.01, float(end_to_end_tps) * 0.001)
            ):
                return None
            decode.append(float(decode_tps))
            end_to_end.append(float(end_to_end_tps))
            ttft.append(float(first))
        expected_aggregates = {
            "medianTTFT": round(statistics.median(ttft), 4),
            "medianDecodeTokensPerSecond": round(statistics.median(decode), 3),
            "medianEndToEndTokensPerSecond": round(statistics.median(end_to_end), 3),
        }
        if any(
            not self._positive_finite_number(measurement.get(key))
            or float(measurement[key]) != expected
            for key, expected in expected_aggregates.items()
        ):
            return None
        agentic_metrics = measurement.get("agenticMetrics")
        if (
            not isinstance(agentic_metrics, dict)
            or agentic_metrics != self.services.summarize_agentic_samples(samples)
        ):
            return None
        resource = measurement.get("resourceTelemetry")
        cooldown = measurement.get("resourceCooldown")
        if not isinstance(resource, dict):
            return None
        if not isinstance(cooldown, dict):
            return None
        return {
            "qualityHash": quality_hash,
            "qualityCompletionTokens": quality_tokens,
            "samples": samples,
            "median": statistics.median(decode),
            "worst": min(decode),
        }

    def _mtplx_operator_public_measurement_matches(self,
        result: Any, measurement: dict[str, Any],
    ) -> bool:
        if not isinstance(result, dict):
            return False
        if any(
            result.get(key) != measurement.get(key)
            for key in self.policy.mtplx_operator_measurement_result_keys
        ):
            return False
        return bool(
            self._mtplx_operator_measurement_evidence({"samples": result.get("samples")})["samples"]
            == measurement.get("samples")
        )

    def _mtplx_long_context_usage_verified(self,
        benchmark: dict[str, Any], required_modes: set[str],
    ) -> bool:
        if (
            benchmark.get("suite") != self.policy.mtplx_long_context_64k_suite
            or benchmark.get("workloadKind") != "agentic"
            or benchmark.get("scenarioContract") != self.policy.route_qualification_scenarios
            or not isinstance(benchmark.get("contextMin"), int)
            or benchmark["contextMin"] < self.policy.mtplx_long_context_minimum
        ):
            return False
        modes = benchmark.get("modes")
        if not isinstance(modes, dict):
            return False
        for mode in required_modes:
            result = modes.get(mode)
            samples = result.get("samples") if isinstance(result, dict) else None
            if not isinstance(samples, list):
                return False
            near_tier = [
                sample for sample in samples
                if isinstance(sample, dict)
                and sample.get("scenario") in {"toolIngest", "steadyTurn"}
            ]
            if len(near_tier) != 2 or any(
                sample.get("authoritativeUsage") is not True
                or sample.get("targetPromptTokens") != self.policy.mtplx_long_context_target_prompt
                or isinstance(sample.get("promptTokens"), bool)
                or not isinstance(sample.get("promptTokens"), int)
                or int(sample["promptTokens"]) < self.policy.mtplx_long_context_minimum_prompt
                or isinstance(sample.get("requestedMaxTokens"), bool)
                or not isinstance(sample.get("requestedMaxTokens"), int)
                or sample["requestedMaxTokens"] != self.policy.benchmark_suites[self.policy.mtplx_long_context_64k_suite]["maxTokens"]
                or sample["requestedMaxTokens"] > int(benchmark.get("outputMax") or 0)
                or int(sample["promptTokens"]) + sample["requestedMaxTokens"]
                > int(benchmark.get("contextMax") or 0)
                for sample in near_tier
            ):
                return False
        return True

    def mtplx_operator_sweep_verified(self,
        capability: dict[str, Any], benchmark: dict[str, Any], mode_settings: Any,
    ) -> bool:
        """Verify the immutable default-vs-2.11.1 long-context operator sweep."""
        sweep = benchmark.get("mtplxOperatorSweep")
        if not isinstance(sweep, dict) or not isinstance(mode_settings, dict):
            return False
        receipt = self.services.mtplx_long_context_2111_contract(
            {
                **(
                    benchmark.get("modelContract")
                    if isinstance(benchmark.get("modelContract"), dict) else {}
                ),
                "name": benchmark.get("modelName"),
                "path": capability.get("modelPath") or benchmark.get("modelPath"),
                "format": "mlx",
                "ready": True,
                "nativeContext": capability.get("contextMaximum") or benchmark.get("contextMax"),
            },
            capability,
            runtime_version=str(benchmark.get("runtimeVersion") or ""),
        )
        # Scanner capabilities do not retain a model path, so the record embeds
        # the exact receipt used for the measurement and we compare it with the
        # compact scan-time contract instead of manufacturing a new path.
        stored_contract = sweep.get("contract")
        if not isinstance(stored_contract, dict):
            return False
        advertised = capability.get("longContext2111")
        if not self.services._mtplx_long_context_capability_matches(advertised, stored_contract):
            return False
        expected_qualification = {
            "suiteName": self.policy.mtplx_long_context_64k_suite,
            "generatedPromptsOnly": True,
            "authoritativeUsageRequired": True,
            "minimumPromptTokens": self.policy.mtplx_long_context_minimum_prompt,
            "targetPromptTokens": self.policy.mtplx_long_context_target_prompt,
        }
        candidates = sweep.get("candidates")
        route_measurements = sweep.get("routeMeasurements")
        selected_settings = mode_settings.get("mtp")
        fixed_depth = sweep.get("fixedMtpDepth")
        stored_fingerprint = str(stored_contract.get("modelFingerprint") or "")
        capability_fingerprint = str(
            capability.get("benchmarkModelFingerprint") or ""
        )
        if (
            receipt is None
            or receipt != stored_contract
            or re.fullmatch(r"[0-9a-f]{64}", stored_fingerprint) is None
            or not secrets.compare_digest(
                stored_fingerprint, capability_fingerprint,
            )
            or not secrets.compare_digest(
                stored_fingerprint, str(benchmark.get("modelFingerprint") or ""),
            )
            or stored_contract.get("modelPath") != benchmark.get("modelPath")
            or stored_contract.get("runtimeVersion") != benchmark.get("runtimeVersion")
            or sweep.get("version") != self.policy.mtplx_long_context_2111_sweep_version
            or sweep.get("strategy") != "isolated-long-context-operator-comparison"
            or sweep.get("complete") is not True
            or sweep.get("resourceComparable") is not True
            or sweep.get("suiteName") != self.policy.mtplx_long_context_64k_suite
            or sweep.get("requiredContext") != self.policy.mtplx_long_context_minimum
            or sweep.get("contractId") != stored_contract.get("contractId")
            or sweep.get("baselineRoute") != self.policy.mtplx_long_context_default_route
            or sweep.get("candidateRoute") != self.policy.mtplx_long_context_2111_route
            or sweep.get("baselineEnvironment") != self.policy.mtplx_long_context_baseline_env
            or sweep.get("candidateEnvironment") != self.policy.mtplx_long_context_candidate_env
            or sweep.get("selectionMetric") != "generation-tokens-per-second"
            or sweep.get("minimumMedianSpeedup") != self.policy.benchmark_minimum_speedup
            or sweep.get("minimumWorstSpeedup") != self.policy.benchmark_minimum_speedup
            or sweep.get("qualificationContract") != expected_qualification
            or isinstance(fixed_depth, bool) or not isinstance(fixed_depth, int)
            or not 1 <= fixed_depth <= int(capability.get("depthMax") or 1)
            or not isinstance(candidates, list) or len(candidates) != 2
            or not isinstance(route_measurements, dict)
            or set(route_measurements) != {
                self.policy.mtplx_long_context_default_route,
                self.policy.mtplx_long_context_2111_route,
            }
            or not isinstance(selected_settings, dict)
            or selected_settings.get("depth") != fixed_depth
            or selected_settings.get("mtplxOperatorRoute") != sweep.get("selectedRoute")
        ):
            return False
        by_route: dict[str, dict[str, Any]] = {}
        derived: dict[str, dict[str, Any]] = {}
        selected_count = 0
        for candidate in candidates:
            if not isinstance(candidate, dict):
                return False
            route = candidate.get("route")
            if route in by_route or route not in {
                self.policy.mtplx_long_context_default_route,
                self.policy.mtplx_long_context_2111_route,
            }:
                return False
            expected_settings = {
                "depth": fixed_depth, "mtplxOperatorRoute": route,
            }
            if (
                candidate.get("settings") != expected_settings
                or candidate.get("qualityMatchesAR") not in {True, False}
                or candidate.get("qualityMatchesDefault") not in {True, False}
                or candidate.get("resourceComparable") is not True
                or candidate.get("resourceCooldownStatus") not in {
                    "ready", "condition-improved",
                }
                or candidate.get("selected") not in {True, False}
                or any(not self._positive_finite_number(candidate.get(key)) for key in (
                    "medianGenerationTokensPerSecond",
                    "worstGenerationTokensPerSecond",
                    "medianSpeedupVsDefault",
                    "worstCaseSpeedupVsDefault",
                ))
            ):
                return False
            if candidate["selected"] is True:
                selected_count += 1
            by_route[str(route)] = candidate
            measurement = route_measurements.get(route)
            verified_measurement = self._mtplx_operator_measurement_verified(measurement)
            if verified_measurement is None:
                return False
            if measurement["resourceCooldown"].get("status") != candidate.get(
                "resourceCooldownStatus"
            ):
                return False
            measurement_samples = verified_measurement["samples"]
            speeds: list[float] = []
            for index, sample in enumerate(measurement_samples):
                if not isinstance(sample, dict):
                    return False
                scenario = self.policy.route_qualification_scenarios[index]
                prompt_tokens = sample.get("promptTokens")
                target_prompt = sample.get("targetPromptTokens")
                sample_completion = sample.get("completionTokens")
                speed = sample.get("decodeTokensPerSecond")
                if (
                    sample.get("scenario") != scenario
                    or isinstance(prompt_tokens, bool)
                    or not isinstance(prompt_tokens, int)
                    or prompt_tokens <= 0
                    or isinstance(target_prompt, bool)
                    or not isinstance(target_prompt, int)
                    or target_prompt <= 0
                    or isinstance(sample_completion, bool)
                    or not isinstance(sample_completion, int)
                    or sample_completion <= 0
                    or sample.get("authoritativeUsage") is not True
                    or not self._positive_finite_number(speed)
                ):
                    return False
                if scenario in {"toolIngest", "steadyTurn"} and (
                    target_prompt != self.policy.mtplx_long_context_target_prompt
                    or prompt_tokens < self.policy.mtplx_long_context_minimum_prompt
                    or sample["requestedMaxTokens"] > int(benchmark.get("outputMax") or 0)
                    or prompt_tokens + sample["requestedMaxTokens"]
                    > int(benchmark.get("contextMax") or 0)
                ):
                    return False
                speeds.append(float(speed))
            derived[str(route)] = {
                "qualityHash": verified_measurement["qualityHash"],
                "qualityCompletionTokens": verified_measurement["qualityCompletionTokens"],
                "samples": measurement_samples,
                "median": verified_measurement["median"],
                "worst": verified_measurement["worst"],
            }
        baseline = by_route.get(self.policy.mtplx_long_context_default_route)
        candidate = by_route.get(self.policy.mtplx_long_context_2111_route)
        baseline_measurement = derived.get(self.policy.mtplx_long_context_default_route)
        candidate_measurement = derived.get(self.policy.mtplx_long_context_2111_route)
        if (
            baseline is None or candidate is None
            or baseline_measurement is None or candidate_measurement is None
        ):
            return False
        baseline_quality_hash = str(benchmark.get("qualityFingerprint") or "")
        baseline_completion_tokens = benchmark.get("qualityCompletionTokens")
        quality_default_ar = bool(
            baseline_measurement["qualityHash"] == baseline_quality_hash
            and baseline_measurement["qualityCompletionTokens"]
            == baseline_completion_tokens
        )
        quality_candidate_ar = bool(
            candidate_measurement["qualityHash"] == baseline_quality_hash
            and candidate_measurement["qualityCompletionTokens"]
            == baseline_completion_tokens
        )
        quality_candidate_default = bool(
            candidate_measurement["qualityHash"]
            == baseline_measurement["qualityHash"]
            and candidate_measurement["qualityCompletionTokens"]
            == baseline_measurement["qualityCompletionTokens"]
        )
        candidate_median_speedup_raw = (
            float(candidate_measurement["median"])
            / max(float(baseline_measurement["median"]), 0.000_001)
        )
        candidate_worst_speedup_raw = (
            float(candidate_measurement["worst"])
            / max(float(baseline_measurement["worst"]), 0.000_001)
        )
        expected_candidate_median_speedup = round(candidate_median_speedup_raw, 4)
        expected_candidate_worst_speedup = round(candidate_worst_speedup_raw, 4)
        if (
            baseline.get("qualityMatchesAR") is not quality_default_ar
            or baseline.get("qualityMatchesDefault") is not True
            or float(baseline.get("medianGenerationTokensPerSecond"))
            != round(float(baseline_measurement["median"]), 3)
            or float(baseline.get("worstGenerationTokensPerSecond"))
            != round(float(baseline_measurement["worst"]), 3)
            or float(baseline.get("medianSpeedupVsDefault")) != 1.0
            or float(baseline.get("worstCaseSpeedupVsDefault")) != 1.0
            or candidate.get("qualityMatchesAR") is not quality_candidate_ar
            or candidate.get("qualityMatchesDefault") is not quality_candidate_default
            or float(candidate.get("medianGenerationTokensPerSecond"))
            != round(float(candidate_measurement["median"]), 3)
            or float(candidate.get("worstGenerationTokensPerSecond"))
            != round(float(candidate_measurement["worst"]), 3)
            or float(candidate.get("medianSpeedupVsDefault"))
            != expected_candidate_median_speedup
            or float(candidate.get("worstCaseSpeedupVsDefault"))
            != expected_candidate_worst_speedup
        ):
            return False
        accepted = bool(
            quality_candidate_ar
            and quality_candidate_default
            and candidate_median_speedup_raw >= self.policy.benchmark_minimum_speedup
            and candidate_worst_speedup_raw >= self.policy.benchmark_minimum_speedup
        )
        expected_selected = (
            self.policy.mtplx_long_context_2111_route
            if accepted else self.policy.mtplx_long_context_default_route
        )
        selected_measurement = derived.get(expected_selected)
        public_modes = benchmark.get("modes")
        public_ar = public_modes.get("ar") if isinstance(public_modes, dict) else None
        public_mtp = public_modes.get("mtp") if isinstance(public_modes, dict) else None
        public_ar_samples = public_ar.get("samples") if isinstance(public_ar, dict) else None
        public_samples = public_mtp.get("samples") if isinstance(public_mtp, dict) else None
        raw_ar = sweep.get("arMeasurement")
        verified_ar = self._mtplx_operator_measurement_verified(raw_ar)
        if (
            selected_measurement is None
            or verified_ar is None
            or raw_ar["resourceCooldown"].get("status") not in {
                "reference-ready", "ready", "condition-improved",
            }
            or not self._mtplx_operator_public_measurement_matches(public_ar, raw_ar)
            or not self._mtplx_operator_public_measurement_matches(
                public_mtp, route_measurements[expected_selected],
            )
            or not isinstance(public_ar_samples, list)
            or len(public_ar_samples) != len(self.policy.route_qualification_scenarios)
            or not isinstance(public_samples, list)
            or self._mtplx_operator_measurement_evidence({"samples": public_samples})["samples"]
            != selected_measurement["samples"]
            or not self._positive_finite_number(public_mtp.get("medianDecodeTokensPerSecond"))
            or float(public_mtp["medianDecodeTokensPerSecond"])
            != round(float(selected_measurement["median"]), 3)
            or public_mtp.get("qualityMatchesAR")
            is not bool(
                selected_measurement["qualityHash"] == baseline_quality_hash
                and selected_measurement["qualityCompletionTokens"]
                == baseline_completion_tokens
            )
            or public_ar.get("qualityMatchesAR") is not True
        ):
            return False
        selected_ar_ratios: list[float] = []
        for index, (ar_sample, mtp_sample) in enumerate(zip(
            public_ar_samples, selected_measurement["samples"],
        )):
            if (
                not isinstance(ar_sample, dict)
                or ar_sample.get("scenario") != self.policy.route_qualification_scenarios[index]
                or not self._positive_finite_number(ar_sample.get("decodeTokensPerSecond"))
                or not self._positive_finite_number(mtp_sample.get("decodeTokensPerSecond"))
            ):
                return False
            selected_ar_ratios.append(
                float(mtp_sample["decodeTokensPerSecond"])
                / max(float(ar_sample["decodeTokensPerSecond"]), 0.000_001)
            )
        selected_quality_ar = bool(
            selected_measurement["qualityHash"] == baseline_quality_hash
            and selected_measurement["qualityCompletionTokens"]
            == baseline_completion_tokens
        )
        selected_ar_median_raw = statistics.median(selected_ar_ratios)
        selected_ar_worst_raw = min(selected_ar_ratios)
        expected_mtp_wins = bool(
            selected_quality_ar
            and selected_ar_median_raw >= self.policy.benchmark_minimum_speedup
            and selected_ar_worst_raw >= self.policy.benchmark_minimum_speedup
        )
        expected_winner = "mtp" if expected_mtp_wins else "ar"
        expected_winner_median = (
            round(selected_ar_median_raw, 4) if expected_mtp_wins else 1.0
        )
        expected_winner_worst = (
            round(selected_ar_worst_raw, 4) if expected_mtp_wins else 1.0
        )
        if (
            verified_ar["qualityHash"] != baseline_quality_hash
            or verified_ar["qualityCompletionTokens"] != baseline_completion_tokens
        ):
            return False
        if (
            public_mtp.get("qualityMatchesAR") is not selected_quality_ar
            or public_mtp.get("medianSpeedupVsAR")
            != round(selected_ar_median_raw, 4)
            or public_mtp.get("worstCaseSpeedupVsAR")
            != round(selected_ar_worst_raw, 4)
            or benchmark.get("selectionMetric") != "generation-tokens-per-second"
            or benchmark.get("minimumSpeedup") != self.policy.benchmark_minimum_speedup
            or benchmark.get("winner") != expected_winner
            or not self._positive_finite_number(benchmark.get("winnerSpeedup"))
            or float(benchmark["winnerSpeedup"]) != expected_winner_median
            or not self._positive_finite_number(benchmark.get("worstCaseSpeedup"))
            or float(benchmark["worstCaseSpeedup"]) != expected_winner_worst
            or not self._positive_finite_number(benchmark.get("endToEndSpeedup"))
            or float(benchmark["endToEndSpeedup"]) != expected_winner_median
            or benchmark.get("qualityPassed") is not True
            or benchmark.get("settings") != mode_settings.get(expected_winner)
        ):
            return False
        return bool(
            selected_count == 1
            and sweep.get("candidateAccepted") is accepted
            and sweep.get("selectedRoute") == expected_selected
            and by_route[expected_selected]["selected"] is True
            and sweep.get("selectedSettings") == selected_settings
            and selected_settings == by_route[expected_selected]["settings"]
            and self._mtplx_long_context_usage_verified(benchmark, {"ar", "mtp"})
        )

    def dflash2_tuning_controls(self,
        options: dict[str, Any], capability: dict[str, Any],
    ) -> dict[str, Any]:
        """Normalize the complete DFlash load identity against the scanned draft."""
        block_size = self.services.bounded_integer(
            options.get("blockSize", options.get("depth")),
            int(capability.get("dflashBlockSize") or 1),
            1,
            int(capability.get("dflashMaxBlockSize") or 1),
            "DFlash block size",
        )
        draft_quant = str(
            options.get("draftQuant", options.get("dflashDraftQuant", "native"))
        )
        verify_mode = str(
            options.get("verifyMode", options.get("dflashVerify", "adaptive"))
        )
        if draft_quant not in set(self.policy.benchmark_dflash_tuner_draft_quants):
            raise ValueError("DFlash draft precision must be native, Q8, Q4, or Q2.")
        if verify_mode not in set(self.policy.benchmark_dflash_tuner_verify_modes):
            raise ValueError("DFlash verification must be adaptive, DFlash, or DDTree.")
        return {
            "blockSize": block_size,
            "draftQuant": draft_quant,
            "verifyMode": verify_mode,
        }

    def dflash2_benchmark_settings_verified(self,
        capability: dict[str, Any], settings: Any,
    ) -> bool:
        if not isinstance(settings, dict) or set(settings) != {
            "blockSize", "draftQuant", "verifyMode",
        }:
            return False
        try:
            return self.dflash2_tuning_controls(settings, capability) == settings
        except (TypeError, ValueError):
            return False

    def optional_tuning_search_metadata_verified(self,
        sweep: dict[str, Any], candidates: list[dict[str, Any]],
        optional_stages: tuple[str, ...], *, replay_complete: bool,
        replay_next_stage: str | None,
    ) -> bool:
        """Bind optional-search metadata to its exact deterministic replay."""
        has_complete = "optionalSearchComplete" in sweep
        has_stop = "optionalSearchStop" in sweep
        if sweep.get("version") == 1 and not has_complete and not has_stop:
            # Version 1 predated explicit optional-search receipts.  Its missing
            # metadata is safe only when the candidate sequence itself proves that
            # the complete historical search ran.
            return replay_complete and replay_next_stage is None
        complete = sweep.get("optionalSearchComplete")
        stop = sweep.get("optionalSearchStop")
        if complete is True:
            return bool(
                stop is None
                and replay_complete
                and replay_next_stage is None
            )
        if complete is not False or not isinstance(stop, dict):
            return False
        if not (
            set(stop) == {"reason", "stage", "completedCandidateCount"}
            and stop.get("reason") in {"resource-cooldown-timeout", "candidate-budget"}
            and stop.get("stage") in optional_stages
            and isinstance(stop.get("completedCandidateCount"), int)
            and not isinstance(stop.get("completedCandidateCount"), bool)
            and stop.get("completedCandidateCount") == len(candidates)
        ):
            return False
        if (
            stop.get("reason") == "candidate-budget"
            and stop.get("completedCandidateCount") != sweep.get("maximumCandidates")
        ):
            return False
        return bool(
            not replay_complete
            and replay_next_stage is not None
            and stop.get("stage") == replay_next_stage
        )

    def benchmark_tuner_read_version_supported(self,
        value: Any, supported_versions: frozenset[int],
    ) -> bool:
        """Accept compatible stored schemas only; their full current structure is checked separately."""
        return bool(
            isinstance(value, int) and not isinstance(value, bool)
            and value in supported_versions
        )

    def deterministic_tuning_best_candidate(self,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Return the candidate selected by the tuner's deterministic score policy."""
        if not candidates:
            return None

        def score(candidate: dict[str, Any]) -> tuple[int, int, float, float]:
            quality = candidate.get("qualityMatchesAR") is True
            clears_floor = bool(
                quality
                and float(candidate["medianSpeedupVsAR"]) >= self.policy.benchmark_minimum_speedup
                and float(candidate["worstCaseSpeedupVsAR"]) >= self.policy.benchmark_minimum_speedup
            )
            return (
                int(quality), int(clears_floor),
                float(candidate["medianSpeedupVsAR"]),
                float(candidate["worstCaseSpeedupVsAR"]),
            )

        return max(candidates, key=score)

    def benchmark_route_selection_metric(self, job: dict[str, Any]) -> str:
        """Return the speed metric that an engine-owned route search must honour.

        Cross-engine calibration offers separate goals for sustained generation
        throughput and complete-workload time.  The old tuner always ranked its
        MTP/DFlash coordinates by end-to-end throughput, even when the surrounding
        shootout was explicitly asking for generation TPS.  Keep standalone tuner
        jobs on their historical total-workload default, but bind Calibration's
        throughput goal (and the dedicated MTPLX long-context operator contract)
        to decode/generation TPS.
        """
        tuning = job.get("calibrationTuningPlan")
        if (
            isinstance(tuning, dict)
            and tuning.get("strategy")
            == "isolated-long-context-operator-comparison"
        ):
            return "generation-tokens-per-second"
        return (
            "generation-tokens-per-second"
            if str(job.get("enginePreference") or "") == "throughput"
            else "end-to-end-tokens-per-second"
        )

    def tuning_speed_fields(self, selection_metric: str) -> tuple[str, str]:
        """Map a public tuning metric to its per-sample and aggregate fields."""
        if selection_metric == "generation-tokens-per-second":
            return "decodeTokensPerSecond", "medianDecodeTokensPerSecond"
        if selection_metric == "end-to-end-tokens-per-second":
            return "endToEndTokensPerSecond", "medianEndToEndTokensPerSecond"
        raise ValueError("Unsupported tuning selection metric.")

    def replay_lmstudio_optional_search(self,
        capability: dict[str, Any], candidates: list[dict[str, Any]], required_count: int,
    ) -> tuple[bool, bool, str | None]:
        """Replay the LM optional coordinates and identify an exact stopped prefix."""
        cursor = required_count
        seen = {str(candidate["key"]) for candidate in candidates[:required_count]}

        def consume(settings: dict[str, Any], stage: str) -> str:
            nonlocal cursor
            try:
                normalized = self.services.lmstudio_mtp_controls(settings, capability)
                key = self.services.lmstudio_mtp_tuning_candidate_key(normalized)
            except (KeyError, TypeError, ValueError):
                return "invalid"
            if key in seen or len(seen) >= self.policy.benchmark_mtp_tuner_max_candidates:
                return "skipped"
            if cursor >= len(candidates):
                return "missing"
            candidate = candidates[cursor]
            if (
                candidate.get("stage") != stage
                or candidate.get("key") != key
                or candidate.get("settings") != normalized
            ):
                return "invalid"
            seen.add(key)
            cursor += 1
            return "consumed"

        best = self.deterministic_tuning_best_candidate(candidates[:cursor])
        if best is None:
            return False, False, None
        cutoff_anchor = copy.deepcopy(best["settings"])
        for cutoff in self.services._ordered_unique([
            cutoff_anchor["mtpMinContinueProbability"],
            *self.policy.benchmark_mtp_tuner_cutoffs,
        ]):
            settings = copy.deepcopy(cutoff_anchor)
            settings["mtpMinContinueProbability"] = cutoff
            outcome = consume(settings, "cutoff")
            if outcome == "invalid":
                return False, False, None
            if outcome == "missing":
                return True, False, "cutoff"

        best = self.deterministic_tuning_best_candidate(candidates[:cursor])
        if best is None:
            return False, False, None
        minimum_anchor = copy.deepcopy(best["settings"])
        for minimum in self.services._ordered_unique([
            minimum_anchor["mtpMinTokens"], 0, 1, minimum_anchor["depth"],
        ]):
            settings = copy.deepcopy(minimum_anchor)
            settings["mtpMinTokens"] = max(
                0, min(int(settings["depth"]), int(minimum)),
            )
            outcome = consume(settings, "minimum")
            if outcome == "invalid":
                return False, False, None
            if outcome == "missing":
                return True, False, "minimum"
        if cursor != len(candidates):
            return False, False, None
        return True, True, None

    def replay_dflash_optional_search(self,
        capability: dict[str, Any], candidates: list[dict[str, Any]], required_count: int,
    ) -> tuple[bool, bool, str | None]:
        """Replay the DFlash optional coordinates and identify an exact stopped prefix."""
        cursor = required_count
        seen = {str(candidate["key"]) for candidate in candidates[:required_count]}

        def consume(settings: dict[str, Any], stage: str) -> str:
            nonlocal cursor
            try:
                normalized = self.dflash2_tuning_controls(settings, capability)
                key = self.services.dflash2_tuning_candidate_key(normalized)
            except (KeyError, TypeError, ValueError):
                return "invalid"
            if key in seen or len(seen) >= self.policy.benchmark_dflash_tuner_max_candidates:
                return "skipped"
            if cursor >= len(candidates):
                return "missing"
            candidate = candidates[cursor]
            if (
                candidate.get("stage") != stage
                or candidate.get("key") != key
                or candidate.get("settings") != normalized
            ):
                return "invalid"
            seen.add(key)
            cursor += 1
            return "consumed"

        best = self.deterministic_tuning_best_candidate(candidates[:cursor])
        if best is None:
            return False, False, None
        verifier_anchor = copy.deepcopy(best["settings"])
        for verify_mode in self.services._ordered_unique([
            verifier_anchor["verifyMode"], *self.policy.benchmark_dflash_tuner_verify_modes,
        ]):
            settings = copy.deepcopy(verifier_anchor)
            settings["verifyMode"] = str(verify_mode)
            outcome = consume(settings, "verifier")
            if outcome == "invalid":
                return False, False, None
            if outcome == "missing":
                return True, False, "verifier"

        best = self.deterministic_tuning_best_candidate(candidates[:cursor])
        if best is None:
            return False, False, None
        quant_anchor = copy.deepcopy(best["settings"])
        for draft_quant in self.services._ordered_unique([
            quant_anchor["draftQuant"], *self.policy.benchmark_dflash_tuner_draft_quants,
        ]):
            settings = copy.deepcopy(quant_anchor)
            settings["draftQuant"] = str(draft_quant)
            outcome = consume(settings, "quantization")
            if outcome == "invalid":
                return False, False, None
            if outcome == "missing":
                return True, False, "quantization"
        if cursor != len(candidates):
            return False, False, None
        return True, True, None

    def tuning_selected_candidate_matches_mode(self,
        benchmark: dict[str, Any], mode: str, candidate: dict[str, Any],
    ) -> bool:
        """Bind a tuning decision to the exact measured mode stored in the receipt."""
        modes = benchmark.get("modes")
        mode_settings = benchmark.get("modeSettings")
        measured = modes.get(mode) if isinstance(modes, dict) else None
        settings = mode_settings.get(mode) if isinstance(mode_settings, dict) else None
        if not isinstance(measured, dict) or not isinstance(settings, dict):
            return False
        return bool(
            candidate.get("settings") == settings
            and candidate.get("qualityMatchesAR") == measured.get("qualityMatchesAR")
            and candidate.get("medianSpeedupVsAR") == measured.get("medianSpeedupVsAR")
            and candidate.get("worstCaseSpeedupVsAR") == measured.get("worstCaseSpeedupVsAR")
            and (
                "medianDecodeTokensPerSecond" not in candidate
                or candidate.get("medianDecodeTokensPerSecond")
                == measured.get("medianDecodeTokensPerSecond")
            )
            and candidate.get("medianEndToEndTokensPerSecond")
            == measured.get("medianEndToEndTokensPerSecond")
        )

    def tuning_selection_contract_verified(self,
        benchmark: dict[str, Any], sweep: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> bool:
        """Reject old route searches as proof for a metric they never optimised."""
        metric = benchmark.get("selectionMetric")
        if metric not in {
            "generation-tokens-per-second", "end-to-end-tokens-per-second",
        }:
            return False
        version = sweep.get("version")
        if version in {1, 2}:
            # Historical adaptive searches always used end-to-end throughput.
            return bool(
                metric == "end-to-end-tokens-per-second"
                and sweep.get("selectionMetric") in {None, metric}
                and all(
                    candidate.get("selectionMetric") in {None, metric}
                    for candidate in candidates
                )
            )
        if version != 3 or sweep.get("selectionMetric") != metric:
            return False
        return all(
            candidate.get("selectionMetric") == metric
            and self._positive_finite_number(
                candidate.get("medianDecodeTokensPerSecond")
            )
            and self._positive_finite_number(
                candidate.get("medianEndToEndTokensPerSecond")
            )
            for candidate in candidates
        )

    def lmstudio_mtp_tuning_sweep_verified(self,
        capability: dict[str, Any], benchmark: dict[str, Any], mode_settings: Any,
    ) -> bool:
        sweep = benchmark.get("tuningSweep")
        expected_maximum = self.policy.benchmark_mtp_tuner_max_candidates
        if isinstance(expected_maximum, bool) or not isinstance(expected_maximum, int):
            return False
        if (
            benchmark.get("kind") != "lmstudio-mtp-tuning"
            or not isinstance(sweep, dict)
            or not self.benchmark_tuner_read_version_supported(
                sweep.get("version"), self.policy.benchmark_mtp_tuner_read_versions,
            )
            or sweep.get("strategy") != "bounded-coordinate-search"
            or sweep.get("complete") is not True
            or sweep.get("resourceComparable") is not True
            or sweep.get("maximumCandidates") != expected_maximum
            or not isinstance(mode_settings, dict)
            or not self.mtp_benchmark_settings_verified(
                "lmstudio", capability, mode_settings.get("mtp"),
            )
            or sweep.get("selectedSettings") != mode_settings.get("mtp")
        ):
            return False
        candidates = sweep.get("candidates")
        count = sweep.get("candidateCount")
        if (
            not isinstance(candidates, list)
            or isinstance(count, bool) or not isinstance(count, int)
            or count != len(candidates)
            or not 1 <= count <= int(expected_maximum)
            or not self.tuning_selection_contract_verified(
                benchmark, sweep, candidates,
            )
        ):
            return False
        seen: set[str] = set()
        seen_settings: set[tuple[int, int, float]] = set()
        selected = 0
        selected_candidate: dict[str, Any] | None = None
        for candidate in candidates:
            if not isinstance(candidate, dict):
                return False
            key = candidate.get("key")
            settings = candidate.get("settings")
            if (
                not isinstance(key, str) or not key or key in seen
                or candidate.get("stage") not in {"depth", "cutoff", "minimum"}
                or candidate.get("qualityMatchesAR") not in {True, False}
                or candidate.get("resourceComparable") is not True
                or candidate.get("selected") not in {True, False}
                or not self.mtp_benchmark_settings_verified("lmstudio", capability, settings)
                or key != self.services.lmstudio_mtp_tuning_candidate_key(settings)
            ):
                return False
            seen.add(key)
            settings_key = (
                settings["depth"], settings["mtpMinTokens"],
                settings["mtpMinContinueProbability"],
            )
            if settings_key in seen_settings:
                return False
            seen_settings.add(settings_key)
            for metric in (
                "medianSpeedupVsAR", "worstCaseSpeedupVsAR",
                "medianEndToEndTokensPerSecond",
            ):
                value = candidate.get(metric)
                if (
                    isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(float(value)) or float(value) <= 0
                ):
                    return False
            if candidate.get("selected") is True:
                selected += 1
                selected_candidate = candidate
                if key != sweep.get("selectedCandidateKey") or settings != sweep.get("selectedSettings"):
                    return False
        best = self.deterministic_tuning_best_candidate(candidates)
        if (
            selected != 1 or selected_candidate is None or best is None
            or best.get("key") != selected_candidate.get("key")
            or best.get("settings") != selected_candidate.get("settings")
            or not self.tuning_selected_candidate_matches_mode(
                benchmark, "mtp", selected_candidate,
            )
            or candidates[0].get("stage") != "depth"
        ):
            return False
        anchor = copy.deepcopy(candidates[0]["settings"])
        try:
            required_depths = self.services.lmstudio_mtp_tuning_depths(
                capability, int(anchor["depth"]),
            )
            required_settings = []
            for depth in required_depths:
                settings = copy.deepcopy(anchor)
                settings["depth"] = int(depth)
                settings["mtpMinTokens"] = min(
                    int(settings["mtpMinTokens"]), int(depth),
                )
                required_settings.append(self.services.lmstudio_mtp_controls(settings, capability))
        except (KeyError, TypeError, ValueError):
            return False
        if (
            len(candidates) < len(required_settings)
            or any(
                candidate.get("stage") != "depth"
                or candidate.get("settings") != expected
                for candidate, expected in zip(candidates, required_settings)
            )
            or any(candidate.get("stage") == "depth" for candidate in candidates[len(required_settings):])
        ):
            return False
        stage_order = {"depth": 0, "cutoff": 1, "minimum": 2}
        if [stage_order[item["stage"]] for item in candidates] != sorted(
            stage_order[item["stage"]] for item in candidates
        ):
            return False
        replay_valid, replay_complete, replay_next_stage = (
            self.replay_lmstudio_optional_search(
                capability, candidates, len(required_settings),
            )
        )
        if not replay_valid:
            return False
        if sweep.get("version") == 1 and not replay_complete:
            return False
        if not self.optional_tuning_search_metadata_verified(
            sweep, candidates, ("cutoff", "minimum"),
            replay_complete=replay_complete,
            replay_next_stage=replay_next_stage,
        ):
            return False
        stop = sweep.get("optionalSearchStop")
        return not (
            isinstance(stop, dict)
            and stop.get("stage") == "cutoff"
            and any(candidate.get("stage") == "minimum" for candidate in candidates)
        )

    def dflash2_tuning_sweep_verified(self,
        capability: dict[str, Any], benchmark: dict[str, Any], mode_settings: Any,
    ) -> bool:
        """Verify a complete, bounded DFlash search before it can guide launches."""
        sweep = benchmark.get("tuningSweep")
        expected_maximum = self.policy.benchmark_dflash_tuner_max_candidates
        if isinstance(expected_maximum, bool) or not isinstance(expected_maximum, int):
            return False
        baseline_modes = ["ar"] + (["mtp"] if capability.get("mtp") is True else [])
        if (
            benchmark.get("kind") != "omlx-dflash2-tuning"
            or not isinstance(sweep, dict)
            or not self.benchmark_tuner_read_version_supported(
                sweep.get("version"), self.policy.benchmark_dflash_tuner_read_versions,
            )
            or sweep.get("strategy") != "bounded-coordinate-search"
            or sweep.get("searchedAxes") != ["blockSize", "verifyMode", "draftQuant"]
            or sweep.get("baselineModes") != baseline_modes
            or sweep.get("complete") is not True
            or sweep.get("resourceComparable") is not True
            or sweep.get("maximumCandidates") != expected_maximum
            or not isinstance(mode_settings, dict)
            or not self.dflash2_benchmark_settings_verified(
                capability, mode_settings.get("dflash2"),
            )
            or sweep.get("selectedSettings") != mode_settings.get("dflash2")
        ):
            return False
        candidates = sweep.get("candidates")
        count = sweep.get("candidateCount")
        if (
            not isinstance(candidates, list)
            or isinstance(count, bool) or not isinstance(count, int)
            or count != len(candidates)
            or not 1 <= count <= int(expected_maximum)
            or not self.tuning_selection_contract_verified(
                benchmark, sweep, candidates,
            )
        ):
            return False
        seen: set[str] = set()
        seen_settings: set[tuple[int, str, str]] = set()
        selected = 0
        selected_candidate: dict[str, Any] | None = None
        for candidate in candidates:
            if not isinstance(candidate, dict):
                return False
            key = candidate.get("key")
            settings = candidate.get("settings")
            if (
                not isinstance(key, str) or not key or key in seen
                or candidate.get("stage") not in {"block", "verifier", "quantization"}
                or candidate.get("qualityMatchesAR") not in {True, False}
                or candidate.get("resourceComparable") is not True
                or candidate.get("selected") not in {True, False}
                or not self.dflash2_benchmark_settings_verified(capability, settings)
                or key != self.services.dflash2_tuning_candidate_key(settings)
            ):
                return False
            seen.add(key)
            settings_key = (
                settings["blockSize"], settings["draftQuant"], settings["verifyMode"],
            )
            if settings_key in seen_settings:
                return False
            seen_settings.add(settings_key)
            for metric in (
                "medianSpeedupVsAR", "worstCaseSpeedupVsAR",
                "medianEndToEndTokensPerSecond",
            ):
                value = candidate.get(metric)
                if (
                    isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(float(value)) or float(value) <= 0
                ):
                    return False
            if candidate.get("selected") is True:
                selected += 1
                selected_candidate = candidate
                if (
                    key != sweep.get("selectedCandidateKey")
                    or settings != sweep.get("selectedSettings")
                ):
                    return False
        best = self.deterministic_tuning_best_candidate(candidates)
        if (
            selected != 1 or selected_candidate is None or best is None
            or best.get("key") != selected_candidate.get("key")
            or best.get("settings") != selected_candidate.get("settings")
            or not self.tuning_selected_candidate_matches_mode(
                benchmark, "dflash2", selected_candidate,
            )
            or candidates[0].get("stage") != "block"
        ):
            return False
        anchor = copy.deepcopy(candidates[0]["settings"])
        try:
            required_blocks = self.services.dflash2_tuning_block_sizes(
                capability, int(anchor["blockSize"]),
            )
            required_settings = []
            for block_size in required_blocks:
                settings = copy.deepcopy(anchor)
                settings["blockSize"] = int(block_size)
                required_settings.append(self.dflash2_tuning_controls(settings, capability))
        except (KeyError, TypeError, ValueError):
            return False
        if (
            len(candidates) < len(required_settings)
            or any(
                candidate.get("stage") != "block"
                or candidate.get("settings") != expected
                for candidate, expected in zip(candidates, required_settings)
            )
            or any(candidate.get("stage") == "block" for candidate in candidates[len(required_settings):])
        ):
            return False
        stage_order = {"block": 0, "verifier": 1, "quantization": 2}
        if [stage_order[item["stage"]] for item in candidates] != sorted(
            stage_order[item["stage"]] for item in candidates
        ):
            return False
        replay_valid, replay_complete, replay_next_stage = (
            self.replay_dflash_optional_search(
                capability, candidates, len(required_settings),
            )
        )
        if not replay_valid:
            return False
        if sweep.get("version") == 1 and not replay_complete:
            return False
        if not self.optional_tuning_search_metadata_verified(
            sweep, candidates, ("verifier", "quantization"),
            replay_complete=replay_complete,
            replay_next_stage=replay_next_stage,
        ):
            return False
        stop = sweep.get("optionalSearchStop")
        return not (
            isinstance(stop, dict)
            and stop.get("stage") == "verifier"
            and any(candidate.get("stage") == "quantization" for candidate in candidates)
        )

    def benchmark_record_output_contract_verified(self,
        benchmark: dict[str, Any], configured_output: Any,
    ) -> bool:
        """Keep the selected ceiling distinct from what a bounded probe measured."""
        if isinstance(configured_output, bool) or not isinstance(configured_output, int):
            return False
        output_min = benchmark.get("outputMin")
        output_max = benchmark.get("outputMax")
        if (
            isinstance(output_min, bool) or not isinstance(output_min, int)
            or isinstance(output_max, bool) or not isinstance(output_max, int)
        ):
            return False
        if (
            benchmark.get("kind") == "route-qualification"
            and benchmark.get("backend") in {"llamacpp", "uzu"}
        ):
            if benchmark["backend"] == "uzu":
                return bool(
                    configured_output == benchmark.get("configuredOutputLimit")
                    and self.services.route_qualification_metrics(benchmark) is not None
                )
            contract = benchmark.get("qualificationContract")
            sample_tokens = self.services.route_qualification_sample_tokens(benchmark["backend"])
            return bool(
                configured_output == benchmark.get("configuredOutputLimit")
                and benchmark.get("measuredRequestMaxTokens")
                == sample_tokens
                and output_min == sample_tokens
                and output_max == sample_tokens
                and isinstance(contract, dict)
                and contract.get("configuredOutputLimit") == configured_output
                and contract.get("measuredRequestMaxTokens")
                == sample_tokens
            )
        return output_min <= configured_output <= output_max

    def sampling_record_evidence(self, evidence: dict[str, Any]) -> dict[str, Any]:
        """Copy only the strict sampling proof saved beside a benchmark result."""
        return {
            key: copy.deepcopy(evidence.get(key))
            for key in self.policy.sampling_record_evidence_keys
        }

    def sampling_record_evidence_verified(self,
        benchmark: dict[str, Any], evidence: dict[str, Any],
    ) -> bool:
        """Verify a launcher-controlled document rather than trusting a hash label."""
        if (
            evidence.get("samplingEvidenceVersion") != self.policy.sampling_evidence_schema_version
            or benchmark.get("samplingEvidenceVersion") != self.policy.sampling_evidence_schema_version
            or evidence.get("samplingControlled") is not True
            or benchmark.get("samplingControlled") is not True
            or evidence.get("samplingContractVersion") != SAMPLING_CONTRACT_SCHEMA_VERSION
            or benchmark.get("samplingContractVersion") != SAMPLING_CONTRACT_SCHEMA_VERSION
        ):
            return False
        try:
            expected = load_sampling_contract(evidence.get("samplingContract"))
            measured = load_sampling_contract(benchmark.get("samplingContract"))
        except (SamplingContractError, TypeError):
            return False
        expected_fingerprint = sampling_fingerprint(expected)
        measured_fingerprint = sampling_fingerprint(measured)
        return bool(
            expected.as_dict() == measured.as_dict()
            and secrets.compare_digest(expected_fingerprint, measured_fingerprint)
            and isinstance(evidence.get("samplingContractFingerprint"), str)
            and secrets.compare_digest(
                expected_fingerprint, evidence["samplingContractFingerprint"],
            )
            and isinstance(benchmark.get("samplingContractFingerprint"), str)
            and secrets.compare_digest(
                measured_fingerprint, benchmark["samplingContractFingerprint"],
            )
        )

    def engine_settings_sweep_record_contract(self, record: dict[str, Any]) -> dict[str, Any]:
        context = record.get("contextMin")
        output = record.get("outputMin")
        if (
            isinstance(context, bool) or not isinstance(context, int)
            or isinstance(output, bool) or not isinstance(output, int)
            or context <= 0 or output <= 0
        ):
            raise ValueError("The settings-search record has invalid workload limits.")
        return {
            "backend": str(record.get("backend") or ""),
            "modelFingerprint": str(record.get("modelFingerprint") or ""),
            "runtimeVersion": str(record.get("runtimeVersion") or ""),
            "hardwareFingerprint": str(record.get("hardwareFingerprint") or ""),
            "suite": str(record.get("suite") or ""),
            "client": str(record.get("client") or ""),
            "reasoning": str(record.get("reasoning") or ""),
            "targetKV": str(record.get("targetKV") or "off"),
            "samplingFingerprint": str(record.get("samplingFingerprint") or ""),
            "context": context,
            "output": output,
            "selectionPreference": str(record.get("selectionPreference") or "throughput"),
        }

    def select_engine_settings_sweep_candidate(self,
        candidates: list[dict[str, Any]], preference: str,
    ) -> dict[str, Any] | None:
        """Replay the deterministic incumbent-preserving settings decision."""
        def finite_nonnegative(value: Any) -> bool:
            return bool(
                not isinstance(value, bool)
                and isinstance(value, (int, float))
                and math.isfinite(float(value))
                and float(value) >= 0
            )

        usable = [
            candidate for candidate in candidates
            if candidate.get("qualityMatchesReference") is True
            and candidate.get("resourceComparable") is True
            and finite_nonnegative(candidate.get("preferenceValue"))
            and finite_nonnegative(candidate.get("worstPreferenceValue"))
        ]
        if not usable:
            return None
        incumbent = usable[0]
        higher = incumbent.get("higherIsBetter") is True
        if any(candidate.get("higherIsBetter") is not higher for candidate in usable):
            return None
        best = (
            max(usable, key=lambda item: (
                float(item["preferenceValue"]), float(item["worstPreferenceValue"]),
            ))
            if higher else
            min(usable, key=lambda item: (
                float(item["preferenceValue"]), float(item["worstPreferenceValue"]),
            ))
        )
        if best is incumbent:
            return incumbent
        current = float(incumbent["preferenceValue"])
        measured = float(best["preferenceValue"])
        current_worst = float(incumbent["worstPreferenceValue"])
        measured_worst = float(best["worstPreferenceValue"])
        if preference == "memory":
            return best if current - measured >= self.policy.benchmark_memory_meaningful_bytes else incumbent
        if preference == "thermal":
            return best if measured < current else incumbent
        median_gain = (
            measured / max(current, 0.000_001)
            if higher else current / max(measured, 0.000_001)
        )
        worst_gain = (
            measured_worst / max(current_worst, 0.000_001)
            if higher else current_worst / max(measured_worst, 0.000_001)
        )
        return (
            best
            if median_gain >= self.policy.benchmark_minimum_speedup
            and worst_gain >= self.policy.benchmark_minimum_speedup
            else incumbent
        )

    def _engine_settings_sweep_settings_valid(self,
        backend: str, settings: Any, capability: dict[str, Any],
    ) -> bool:
        if not isinstance(settings, dict):
            return False
        expected = set(self.policy.benchmark_engine_setting_keys.get(backend, ()))
        if backend == "omlx" and not capability.get("expertOffload"):
            expected -= {"expertResidentPercent", "omlxMemoryGB"}
        if backend == "omlx" and settings.get("pleStorage") == "mmap":
            expected.add("pleStorage")
        if set(settings) != expected:
            return False
        try:
            if backend == "omlx":
                return bool(
                    settings.get("burst") in {"off", "light", "balanced", "aggressive"}
                    and settings.get("anePrefill") in {"off", "tuned"}
                    and settings.get("memoryGuard") in {"balanced", "high"}
                    and settings.get("pleStorage") in {None, "mmap"}
                    and (not capability.get("expertOffload") or (
                        settings.get("expertResidentPercent") in self.policy.omlx_expert_resident_percentages
                        and type(settings.get("omlxMemoryGB")) in (int, float)
                        and 12 <= settings["omlxMemoryGB"] <= self.services.physical_memory_bytes() / 1e9
                    ))
                )
            if backend == "lmstudio":
                return bool(settings.get("gpu") in {"max", "off"} and settings.get("parallel") == 1)
            if backend == "mtplx":
                return bool(
                    settings.get("profile") in {
                        "stable", "performance-cold", "sustained", "turbo", "exact",
                    }
                    and settings.get("fan") in {"default", "smart", "max"}
                )
            if backend == "swiftlm":
                return bool(
                    settings.get("prefillSize") in self.policy.ssd_streaming_prefill_sizes
                    and settings.get("nativeExpertTopK")
                    == max(0, int(capability.get("nativeExpertTopK") or 0))
                    and settings.get("ssdCacheState") == "natural-cold-to-warm"
                )
            if backend == "mference":
                return bool(
                    settings.get("promptCacheMode") in {"on", "off"}
                    and settings.get("queueLimit") == 1
                    and settings.get("ssdCacheState") == "natural-cold-to-warm"
                )
        except (TypeError, ValueError):
            return False
        return False

    def engine_settings_candidate_evidence(self,
        candidate: dict[str, Any], record: dict[str, Any],
        reference: dict[str, Any], preference: str,
    ) -> dict[str, Any]:
        """Derive selection inputs from measured samples, never from display scores."""
        measured = self.services.cross_engine_benchmark_measurement(record)
        if measured is None:
            raise ValueError("A settings candidate has incomplete measurement data.")
        mode = record["modes"][record["winner"]]
        samples = mode["samples"]
        if preference in {"memory", "thermal"}:
            key = "peakPressureDeltaBytes" if preference == "memory" else "thermalWorstValue"
            value = measured.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ValueError("This settings goal requires available resource telemetry.")
            worst = value
        else:
            key = {"throughput": "decodeTokensPerSecond", "responsive": "ttftSeconds"}.get(
                preference, "totalSeconds",
            )
            values = [generation_metrics.sample_generation_tps(sample, str(record.get("backend") or ""))
                      if preference == "throughput" else sample.get(key) for sample in samples]
            if not all(self._positive_finite_number(value) for value in values):
                raise ValueError("A settings candidate has invalid timing samples.")
            value = sum(values) if preference == "fastest" else statistics.median(values)
            worst = min(values) if preference == "throughput" else max(values)
        return {
            **copy.deepcopy(candidate),
            "qualityMatchesReference": (
                record["qualityFingerprint"] == reference["qualityFingerprint"]
                and record["qualityCompletionTokens"] == reference["qualityCompletionTokens"]
            ),
            "resourceComparable": all(
                item.get("resourceCooldown", {}).get("status") in {
                    "reference-ready", "ready", "condition-improved", "unavailable",
                }
                for item in record["modes"].values()
            ),
            "higherIsBetter": preference == "throughput",
            "preferenceValue": value, "worstPreferenceValue": worst,
        }

    def benchmark_engine_settings_match(self,
        benchmark: dict[str, Any], expected: Any,
    ) -> bool:
        """A saved search may replace searched controls; safety controls must still match."""
        measured = benchmark.get("engineSettings")
        if not isinstance(expected, dict) or not isinstance(measured, dict):
            return False
        sweep = benchmark.get("engineSettingsSweep")
        if not isinstance(sweep, dict):
            return measured == expected
        axes = sweep.get("searchedAxes")
        if not isinstance(axes, list) or not all(isinstance(axis, str) for axis in axes):
            return False
        # This helper only matches requests. The full verifier separately proves
        # the complete search, exact candidate records, and selected winner.
        ignored = set(axes)
        return (
            {key: value for key, value in measured.items() if key not in ignored}
            == {key: value for key, value in expected.items() if key not in ignored}
        )

    def engine_settings_sweep_receipt_verified(self,
        capability: dict[str, Any], benchmark: dict[str, Any],
    ) -> bool:
        try:
            sweep = benchmark.get("engineSettingsSweep")
            if not isinstance(sweep, dict) or sweep.get("complete") is not True:
                return False
            backend = str(benchmark["backend"])
            candidates = sweep["candidates"]
            records = sweep["records"]
            if (
                sweep.get("version") != self.policy.engine_settings_sweep_version
                or sweep.get("strategy") != "staged-runtime-and-route-search"
                or sweep.get("backend") != backend
                or sweep.get("globalCartesianSearch") is not False
                or sweep.get("contract") != self.engine_settings_sweep_record_contract(benchmark)
                or sweep.get("selectionPreference") != benchmark.get("selectionPreference")
                or not isinstance(candidates, list) or not 1 <= len(candidates) <= 5
                or not isinstance(records, dict) or len(records) != len(candidates)
                or sweep.get("candidateCount") != len(candidates)
            ):
                return False
            modes = benchmark["comparedModes"]
            reference_key = sweep["tuningReferenceKey"]
            reference = records[reference_key]
            if not isinstance(reference, dict):
                return False
            setting_values = []
            rows = []
            for candidate in candidates:
                settings = candidate["settings"]
                key = candidate["key"]
                if (
                    not self._engine_settings_sweep_settings_valid(backend, settings, capability)
                    or key != self.services._engine_settings_candidate_key(backend, settings)
                ):
                    return False
                setting_values.append(settings)
                nested = records[key]
                if (
                    not isinstance(nested, dict) or "engineSettingsSweep" in nested
                    or nested.get("engineSettings") != settings
                    or self.engine_settings_sweep_record_contract(nested)
                    != self.engine_settings_sweep_record_contract(benchmark)
                    or nested.get("comparedModes") != modes
                    or nested.get("modeSettings") != reference.get("modeSettings")
                    or nested.get("scenarioContract") != benchmark.get("scenarioContract")
                ):
                    return False
                evidence = {
                    **self.sampling_record_evidence(benchmark),
                    "samplingFingerprint": benchmark["samplingFingerprint"],
                    "context": benchmark["contextMin"], "output": benchmark["outputMin"],
                    "client": benchmark["client"], "reasoning": benchmark["reasoning"],
                    "kv": benchmark["targetKV"],
                    "engineSettings": settings,
                }
                if not self._local_benchmark_record_verified(capability, nested, evidence):
                    return False
                rows.append(self.engine_settings_candidate_evidence(
                    candidate, nested, records[candidates[0]["key"]], sweep["selectionPreference"],
                ))
            if len({candidate["key"] for candidate in candidates}) != len(candidates):
                return False
            axis = {"omlx": "burst", "lmstudio": "gpu", "mtplx": "profile",
                    "swiftlm": "prefillSize", "mference": "promptCacheMode"}[backend]
            values = {
                "omlx": ["off", "light", "balanced", "aggressive"],
                "lmstudio": ["max", "off"], "swiftlm": list(self.policy.ssd_streaming_prefill_sizes),
                "mference": ["on", "off"],
            }
            if backend == "mtplx":
                values[backend] = (
                    ["stable", "sustained", "exact"]
                    if sweep["selectionPreference"] in {"memory", "thermal"} else
                    ["performance-cold", "turbo", "sustained"]
                    if sweep["selectionPreference"] == "responsive" else
                    ["turbo", "sustained", "performance-cold"]
                )
            fixed_axis = (
                backend == "mtplx" and benchmark["suite"] == self.policy.mtplx_long_context_64k_suite
                or backend == "mference" and benchmark["workloadKind"] != "agentic"
            )
            expected_values = (
                [setting_values[0][axis]] if fixed_axis else
                self.services._ordered_unique([setting_values[0][axis], *values[backend]])
            )
            if (
                [settings[axis] for settings in setting_values] != expected_values
                or sweep.get("searchedAxes") != ([] if fixed_axis else [axis])
                or any(
                    {k: v for k, v in settings.items() if k != axis}
                    != {k: v for k, v in setting_values[0].items() if k != axis}
                    for settings in setting_values
                )
            ):
                return False
            if backend == "lmstudio" and "mtp" in modes:
                base = 1 + self.policy.benchmark_mtp_tuner_max_candidates
                if reference.get("kind") != "lmstudio-mtp-tuning":
                    return False
            elif backend == "omlx" and "dflash2" in modes:
                base = len(modes) - 1 + self.policy.benchmark_dflash_tuner_max_candidates
                if reference.get("kind") != "omlx-dflash2-tuning":
                    return False
            elif backend == "mtplx" and "mtp" in modes:
                base = 3 if fixed_axis else 1 + len(self.mtplx_mtp_depth_candidates(capability))
                if not fixed_axis and "mtpDepthSweep" not in reference:
                    return False
            else:
                base = len(modes)
            maximum = base + (len(candidates) - 1) * len(modes)
            steps = 2 + len(reference["modes"]["ar"]["samples"])
            counts = {
                "candidateCount": len(candidates), "maximumEngineSettingLoads": len(candidates),
                "baseRouteLoads": base, "maximumModelLoads": maximum,
                "stepsPerLoad": steps, "maximumGeneratedRequests": maximum * steps,
            }
            if any(type(sweep.get(key)) is not int or sweep[key] != value for key, value in counts.items()):
                return False
            best = self.select_engine_settings_sweep_candidate(rows, sweep["selectionPreference"])
            selected = sweep["selectedCandidateKey"]
            without_sweep = {key: value for key, value in benchmark.items() if key != "engineSettingsSweep"}
            return bool(
                maximum <= self.policy.engine_settings_sweep_max_model_loads
                and maximum * steps <= self.policy.engine_settings_sweep_max_generated_requests
                and best is not None and best["key"] == selected
                and sweep["selectedEngineSettings"] == benchmark["engineSettings"]
                and without_sweep == records[selected]
            )
        except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
            return False

    def _local_benchmark_record_verified(self,
        capability: dict[str, Any], benchmark: dict[str, Any],
        evidence: dict[str, Any] | None = None,
    ) -> bool:
        if not isinstance(benchmark, dict):
            return False
        backend = str(benchmark.get("backend") or "")
        if (
            backend == "omlx" and benchmark.get("targetKV") != "off"
            and (
                benchmark.get("winner") == "dflash2"
                or (
                    isinstance(benchmark.get("comparedModes"), list)
                    and "dflash2" in benchmark["comparedModes"]
                )
            )
        ):
            return False
        ssd_identity = benchmark.get("ssdComparisonIdentity")
        if backend in self.policy.ssd_streaming_backends:
            capability_identity = capability.get("comparisonIdentity")
            if (
                capability.get("ssdStreaming") is not True
                or benchmark.get("ssdStreaming") is not True
                or not isinstance(ssd_identity, str)
                or re.fullmatch(r"[0-9a-f]{64}", ssd_identity) is None
                or not isinstance(capability_identity, str)
                or not secrets.compare_digest(ssd_identity, capability_identity)
            ):
                return False
        elif benchmark.get("ssdStreaming") is True or ssd_identity not in {None, ""}:
            return False
        if (
            benchmark.get("scope") != "local"
            or benchmark.get("modelFingerprint") != capability.get("benchmarkModelFingerprint")
            or benchmark.get("runtimeVersion") != capability.get("runtimeVersion")
            or benchmark.get("hardwareFingerprint") != self.services.hardware_fingerprint()
            or benchmark.get("baselinePassed") is not True
            or self.benchmark_integrity_issue(benchmark) is not None
        ):
            return False
        context = (evidence or {}).get("context")
        output = (evidence or {}).get("output")
        if (
            not isinstance(context, int) or isinstance(context, bool)
            or not isinstance(output, int) or isinstance(output, bool)
            or not isinstance(benchmark.get("contextMin"), int)
            or not isinstance(benchmark.get("contextMax"), int)
            or not benchmark["contextMin"] <= context <= benchmark["contextMax"]
            or not self.benchmark_record_output_contract_verified(benchmark, output)
        ):
            return False
        if benchmark.get("client") not in {None, "any", (evidence or {}).get("client")}:
            return False
        if benchmark.get("reasoning") not in {"any", (evidence or {}).get("reasoning")}:
            return False
        if benchmark.get("targetKV") != (evidence or {}).get("kv"):
            return False
        if benchmark.get("samplingFingerprint") != (evidence or {}).get("samplingFingerprint"):
            return False
        evidence_value = evidence or {}
        strict_sampling_record = any(
            key in benchmark for key in self.policy.sampling_record_evidence_keys
        )
        if (
            evidence_value.get("client") != "chat" or strict_sampling_record
        ) and not self.sampling_record_evidence_verified(benchmark, evidence_value):
            # Agent records have never been safe to reuse without relay-owned
            # sampling. Legacy records therefore fail closed; legacy Chat records
            # retain their compatibility fingerprint path.
            return False
        compared = benchmark.get("comparedModes")
        if not isinstance(compared, list):
            return False
        compared_modes = {str(item) for item in compared}
        required = {"ar"}
        if capability.get("mtp") is True:
            required.add("mtp")
        contract_version = benchmark.get("comparisonContractVersion")
        measured_engine_settings = benchmark.get("engineSettings")
        expected_by_backend = (evidence or {}).get("engineSettingsByBackend")
        expected_engine_settings = (
            expected_by_backend.get(backend)
            if isinstance(expected_by_backend, dict) else
            (evidence or {}).get("engineSettings")
        )
        if (
            benchmark.get("engineSettingsSweep") is not None
            and not self.engine_settings_sweep_receipt_verified(capability, benchmark)
        ):
            return False
        dflash_locked_by_tuned_ane = bool(
            backend == "omlx"
            and contract_version == self.policy.benchmark_comparison_contract_version
            and isinstance(measured_engine_settings, dict)
            and measured_engine_settings.get("anePrefill") == "tuned"
            and isinstance(expected_engine_settings, dict)
            and expected_engine_settings.get("anePrefill") == "tuned"
        )
        if (
            capability.get("dflash") is True and not dflash_locked_by_tuned_ane
            and (backend != "omlx" or benchmark.get("targetKV") == "off")
        ):
            required.add("dflash2")
        if not required.issubset(compared_modes):
            return False
        modes = benchmark.get("modes")
        if not isinstance(modes, dict) or not required.issubset(modes):
            return False
        if not self._agentic_benchmark_contract_verified(benchmark, required):
            return False
        winner = benchmark.get("winner")
        if winner not in compared_modes or winner not in {"ar", "mtp", "dflash2"}:
            return False
        mode_settings = benchmark.get("modeSettings")
        if backend == "lmstudio" and capability.get("mtp") is True:
            if contract_version not in {3, self.policy.benchmark_comparison_contract_version}:
                return False
        if contract_version in {3, self.policy.benchmark_comparison_contract_version}:
            if (
                not isinstance(mode_settings, dict)
                or set(mode_settings) != compared_modes
                or mode_settings.get("ar") != {}
                or benchmark.get("settings") != mode_settings.get(winner)
            ):
                return False
            if "mtp" in compared_modes and not self.mtp_benchmark_settings_verified(
                backend, capability, mode_settings.get("mtp"),
            ):
                return False
        if contract_version == self.policy.benchmark_comparison_contract_version:
            if (
                not isinstance(expected_engine_settings, dict)
                or not self.benchmark_engine_settings_match(benchmark, expected_engine_settings)
            ):
                return False
        if benchmark.get("kind") == "lmstudio-mtp-tuning" and not self.lmstudio_mtp_tuning_sweep_verified(
            capability, benchmark, mode_settings,
        ):
            return False
        if "mtpDepthSweep" in benchmark and (
            backend != "mtplx"
            or not self.mtplx_mtp_depth_sweep_verified(capability, benchmark, mode_settings)
        ):
            return False
        operator_settings_present = bool(
            isinstance(mode_settings, dict)
            and any(
                isinstance(value, dict) and "mtplxOperatorRoute" in value
                for value in mode_settings.values()
            )
        )
        operator_evidence_present = bool(
            benchmark.get("kind") == "mtplx-long-context-operator-tuning"
            or "mtplxOperatorSweep" in benchmark
            or operator_settings_present
        )
        # The near-64K suite is shared by every engine in the same shootout. Its
        # presence alone must not make an oMLX/LM Studio peer masquerade as an MTPLX
        # operator record. Conversely, any actual operator marker on another backend
        # is invalid, while MTPLX must carry the full immutable sweep for this suite.
        if backend != "mtplx" and operator_evidence_present:
            return False
        long_operator_record = bool(
            backend == "mtplx"
            and (
                benchmark.get("suite") == self.policy.mtplx_long_context_64k_suite
                or operator_evidence_present
            )
        )
        if long_operator_record and (
            "mtpDepthSweep" in benchmark
            or not self.mtplx_operator_sweep_verified(
                capability, benchmark, mode_settings,
            )
        ):
            return False
        if benchmark.get("kind") == "omlx-dflash2-tuning" and not self.dflash2_tuning_sweep_verified(
            capability, benchmark, mode_settings,
        ):
            return False
        if benchmark.get("kind") == "route-qualification":
            metrics = self.services.route_qualification_metrics(benchmark)
            qualification = benchmark.get("qualification")
            contract = benchmark.get("qualificationContract")
            if (
                metrics is None or not isinstance(qualification, dict)
                or qualification.get("metrics") != metrics
                or qualification.get("reasoningEnabled") is not True
                or qualification.get("reasoningObserved") is not True
                or qualification.get("answerObserved") is not True
                or (
                    backend == "llamacpp"
                    and qualification.get("reasoningBoundaryVerified") is not True
                )
                or qualification.get("terminalCompletionObserved") is not True
                or qualification.get("authoritativeUsage") is not True
                or (not isinstance(contract, dict) and backend != "omlx")
            ):
                return False
            if backend == "llamacpp" and (
                capability.get("llamacppPle") is not True
                or capability.get("currentProcessVerified") is not True
                or not isinstance(capability.get("verificationGeneration"), int)
                or capability.get("verificationGeneration") <= 0
                or capability.get("atomicPle", {}).get("ready") is not True
                or capability.get("atomicPle", {}).get("currentProcessVerified") is not True
                or capability.get("atomicPle", {}).get("verificationGeneration")
                != capability.get("verificationGeneration")
                or contract.get("receiptFingerprint") != capability.get("receiptFingerprint")
                or contract.get("runtimeVersion") != capability.get("runtimeVersion")
                or contract.get("memoryCeilingBytes") != self.policy.llamacpp_ple_memory_ceiling_bytes
            ):
                return False
            if backend == "uzu":
                runtime_identity = capability.get("runtimeIdentity")
                runtime_binary = (
                    runtime_identity.get("binary")
                    if isinstance(runtime_identity, dict) else None
                )
                if (
                    capability.get("runnable") is not True
                    or capability.get("runtimeManagedAcceleration") != "DFlash + Weaver"
                    or capability.get("modelRegistryId") != self.policy.uzu_model_registry_id
                    or capability.get("modelCommit") != self.policy.uzu_model_commit
                    or capability.get("modelToolchainVersion") != self.policy.uzu_model_toolchain_version
                    or not isinstance(contract, dict)
                    or contract.get("receiptFingerprint")
                    != capability.get("benchmarkModelFingerprint")
                    or contract.get("modelFingerprint")
                    != capability.get("benchmarkModelFingerprint")
                    or contract.get("runtimeVersion") != capability.get("runtimeVersion")
                    or not isinstance(runtime_binary, dict)
                    or contract.get("runtimeBinarySha256") != runtime_binary.get("sha256")
                    or contract.get("runtimeBinarySize") != runtime_binary.get("size")
                    or contract.get("runtimeUpstreamCommit")
                    != runtime_identity.get("upstreamCommit")
                    or contract.get("runtimeSourcePatchSha256")
                    != runtime_identity.get("sourcePatchSha256")
                    or contract.get("sandboxProfileSha256") != self.policy.uzu_sandbox_profile_sha256
                    or contract.get("rawListenerProtected") is not True
                    or contract.get("nativeBoundaryContractId")
                    != runtime_identity.get("nativeBoundaryContractId")
                    or contract.get("nativeBearerAuthentication") is not True
                    or contract.get("oneUseApiKeyFile") is not True
                    or runtime_identity.get("binaryIdentityPinned") is not True
                    or runtime_identity.get("nativeBearerAuthentication") is not True
                    or runtime_identity.get("oneUseApiKeyFile") is not True
                    or runtime_identity.get("nativeContextLimit") is not True
                    or runtime_identity.get("nativeOutputLimit") is not True
                    or not self.services.uzu_listener_protection_ready(runtime_identity)
                    or not self.services.uzu_qualification_memory_ceiling_supported(contract.get("memoryCeilingBytes"))
                ):
                    return False
        if winner == "ar":
            return True
        try:
            winner_speedup = float(benchmark.get("winnerSpeedup"))
            worst_case = float(benchmark.get("worstCaseSpeedup"))
        except (TypeError, ValueError):
            return False
        if (
            benchmark.get("qualityPassed") is not True
            or winner_speedup < self.policy.benchmark_minimum_speedup
            or worst_case < self.policy.benchmark_minimum_speedup
        ):
            return False
        settings = benchmark.get("settings")
        if winner == "mtp":
            return self.mtp_benchmark_settings_verified(backend, capability, settings)
        return bool(
            benchmark.get("pairFingerprint") == capability.get("dflashPairFingerprint")
            and self.dflash2_benchmark_settings_verified(capability, settings)
        )

    def verified_local_benchmark(self,
        capability: dict[str, Any], evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        candidates = capability.get("localBenchmarks")
        records = [item for item in candidates if isinstance(item, dict)] if isinstance(candidates, list) else []
        latest = capability.get("localBenchmark")
        if isinstance(latest, dict) and latest not in records:
            records.append(latest)
        matches = [
            record for record in records
            if self.services.route_qualification_record_is_fresh(record)
            and self._local_benchmark_record_verified(capability, record, evidence)
        ]
        if not matches:
            return None
        client = str((evidence or {}).get("client") or "")
        agent_client = client in {"pi", "omp", "opencode", "codex"}

        def preference(record: dict[str, Any]) -> tuple[int, int, str]:
            workload = str(record.get("workloadKind") or "throughput")
            workload_match = int((workload == "agentic") == agent_client)
            suite_strength = {
                "quick": 1, "standard": 2, "thorough": 3, "agentic": 4,
                self.policy.mtplx_long_context_64k_suite: 5,
            }.get(str(record.get("suite") or ""), 0)
            return workload_match, suite_strength, str(record.get("createdAt") or "")

        return copy.deepcopy(max(matches, key=preference))

    def local_benchmark_verified(self,
        capability: dict[str, Any], evidence: dict[str, Any] | None = None,
    ) -> bool:
        """Validate locally measured acceleration evidence for the active contract."""
        return self.verified_local_benchmark(capability, evidence) is not None

    def route_performance_evidence(self,
        model: dict[str, Any], backend: str, capability: dict[str, Any],
        exact_evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Classify speed evidence without turning upstream results into local trust."""
        local = self.verified_local_benchmark(capability, exact_evidence)
        if local is not None:
            recommendation = str(local.get("recommendation") or "").strip()
            return {
                "version": self.policy.route_evidence_schema_version,
                "tier": "verified-this-mac",
                "label": "Verified on this Mac",
                "detail": recommendation or (
                    "A matching local benchmark is bound to this model artifact, runtime, "
                    "Mac, and measured request contract."
                ),
                "source": "local-benchmark",
                "sourceUrl": None,
                "sourceHardware": "This Mac",
                "recordId": str(local.get("id") or "") or None,
                "createdAt": str(local.get("createdAt") or "") or None,
                "automaticEligible": True,
            }

        exact_dflash_pair = bool(
            backend == "omlx"
            and capability.get("dflash") is True
            and capability.get("dflashVersion") == "2"
            and capability.get("dflashDraftPath")
            and capability.get("dflashPairFingerprint")
            and capability.get("dflashRuntimeVersion")
        )
        if exact_dflash_pair:
            return {
                "version": self.policy.route_evidence_schema_version,
                "tier": "upstream-measured",
                "label": "Upstream measured",
                "detail": str(self.policy.dflash2_upstream_performance_evidence["detail"]),
                "source": str(self.policy.dflash2_upstream_performance_evidence["source"]),
                "sourceUrl": str(self.policy.dflash2_upstream_performance_evidence["sourceUrl"]),
                "sourceHardware": str(self.policy.dflash2_upstream_performance_evidence["sourceHardware"]),
                "recordId": None,
                "createdAt": None,
                "automaticEligible": False,
            }

        if backend == "uzu" and capability.get("modelRegistryId") == self.policy.uzu_model_registry_id:
            return {
                "version": self.policy.route_evidence_schema_version,
                "tier": "upstream-measured",
                "label": "Upstream measured",
                "detail": (
                    f"Mirai reports {self.policy.uzu_upstream_output_tps:.0f} output tok/s for this Uzu "
                    f"DFlash + Weaver artifact on {self.policy.uzu_upstream_hardware}. That is not a "
                    "measurement for this 48 GB Mac and cannot select the fastest route automatically."
                ),
                "source": "mirai-upstream",
                "sourceUrl": self.policy.uzu_model_page_url,
                "sourceHardware": self.policy.uzu_upstream_hardware,
                "recordId": None,
                "createdAt": None,
                "automaticEligible": False,
            }

        if backend == "whallm" and (
            model.get("sharedServer") is True or capability.get("sharedServer") is True
        ):
            return {
                "version": self.policy.route_evidence_schema_version,
                "tier": "upstream-measured",
                "label": "Upstream measured",
                "detail": (
                    "Whallm reports 9.7–10.4 generation tok/s on its tested M5 Pro "
                    "Qwen3.8 Flash-Next route through 16K input. This is not a local result."
                ),
                "source": "whallm-upstream",
                "sourceUrl": self.policy.whallm_benchmark_url,
                "sourceHardware": "Apple M5 Pro",
                "recordId": None,
                "createdAt": None,
                "automaticEligible": False,
            }

        return {
            "version": self.policy.route_evidence_schema_version,
            "tier": "unmeasured",
            "label": "Not measured on this Mac",
            "detail": (
                "No exact local benchmark is available for this model, runtime, Mac, and request contract."
            ),
            "source": "none",
            "sourceUrl": None,
            "sourceHardware": None,
            "recordId": None,
            "createdAt": None,
            "automaticEligible": False,
        }
