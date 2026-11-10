"""Exact local performance selection, ranking and measurement-history presentation.

Importing the domain performs no I/O. Frozen policy is separate from individual
live validation/evidence/resource ports; saved measurements never replace current
artifact, runtime, capacity or contract checks.
"""
from __future__ import annotations
from dataclasses import dataclass, fields
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Callable
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import statistics
import darwin_memory
import generation_metrics
import kolibri_runtime
import slotstream_runtime
from sampling_contract import SamplingContractError

@dataclass(frozen=True)
class SelectionDescriptor:
    id: str
    label: str
    binary_key: str | None
    built_in: bool

@dataclass(frozen=True)
class _FrozenMapping(Mapping[str, Any]):
    _values: Mapping[Any, Any]
    def __getitem__(self, key: str) -> Any: return self._values[key]
    def __iter__(self): return iter(self._values)
    def __len__(self) -> int: return len(self._values)
    def __deepcopy__(self, memo): return {k:copy.deepcopy(v,memo) for k,v in self._values.items()}

def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _FrozenMapping(MappingProxyType({k:_freeze(v) for k,v in value.items()}))
    if isinstance(value, (tuple,list)): return tuple(_freeze(v) for v in value)
    if isinstance(value, (set,frozenset)): return frozenset(value)
    return value

@dataclass(frozen=True)
class SelectionPolicy:
    backend_labels: Mapping[Any, Any]
    benchmark_comparison_contract_version: int
    benchmark_history_fresh_days: int
    benchmark_history_visible_runs: int
    benchmark_max_history_per_route: int
    benchmark_max_records: int
    benchmark_memory_meaningful_bytes: int
    benchmark_minimum_speedup: float
    benchmark_reasoning_policy_all_engines: str
    benchmark_reasoning_policy_exact: str
    benchmark_suites: Mapping[Any, Any]
    client_adapters: Mapping[str, SelectionDescriptor]
    dflash2_draft_bytes: int
    dflash_kv_comparison_reason: str
    engine_adapters: Mapping[str, SelectionDescriptor]
    engine_preference_labels: Mapping[Any, Any]
    mtplx_long_context_2111_route: str
    mtplx_long_context_64k_suite: str
    mtplx_long_context_default_route: str
    omlx_dflash_tuned_ane_exclusion_detail: str
    optimizer_keys: Mapping[Any, Any]
    sampling_contract_schema_version: int
    sampling_evidence_schema_version: int
    ssd_streaming_backends: tuple[Any, ...]
    ssd_streaming_prefill_sizes: tuple[Any, ...]
    thermal_state_labels: Mapping[Any, Any]
    uzu_pi_benchmark_limitation: str

    def __post_init__(self) -> None:
        for item in fields(self):
            object.__setattr__(self,item.name,_freeze(getattr(self,item.name)))

@dataclass(frozen=True)
class SelectionContracts:
    llamacpp_route_qualification_capability: Callable[..., Any]
    require_omp_console_support: Callable[..., Any]
    build_sampling_contract: Callable[..., Any]
    canonicalize_sampling: Callable[..., Any]
    chat_settings_from_sampling_contract: Callable[..., Any]
    load_sampling_contract: Callable[..., Any]
    normalized_ssd_comparison_request: Callable[..., Any]
    resolved_client_support: Callable[..., Any]
    route_host_support: Callable[..., Any]
    route_qualification_spec: Callable[..., Any]
    sampling_contract_from_settings: Callable[..., Any]
    sampling_fingerprint: Callable[..., Any]
    validate_chat_capability: Callable[..., Any]
    validate_runtime_context: Callable[..., Any]
    validate_sampling_capability: Callable[..., Any]
    validated_chat_settings: Callable[..., Any]
    validated_cross_engine_profile_options: Callable[..., Any]
    validated_launch_profile_request: Callable[..., Any]
    validated_limits: Callable[..., Any]
    validated_profile_options: Callable[..., Any]
    validated_sampling_contract: Callable[..., Any]

@dataclass(frozen=True)
class SelectionEvidence:
    local_benchmark_record_verified: Callable[..., Any]
    uzu_qualified_session_record: Callable[..., Any]
    benchmark_engine_settings: Callable[..., Any]
    benchmark_engine_settings_match: Callable[..., Any]
    benchmark_integrity_issue: Callable[..., Any]
    benchmark_probe_integrity_issue: Callable[..., Any]
    benchmark_record_output_contract_verified: Callable[..., Any]
    benchmark_runtime_integrity_issue: Callable[..., Any]
    dflash2_benchmark_verified: Callable[..., Any]
    load_benchmark_records: Callable[..., Any]
    public_benchmark_settings_search_result: Callable[..., Any]
    public_route_qualification_result: Callable[..., Any]
    route_performance_evidence: Callable[..., Any]
    verified_local_benchmark: Callable[..., Any]
    verified_route_qualification: Callable[..., Any]

@dataclass(frozen=True)
class SelectionLive:
    binary: Callable[[str], str | None]
    descriptor_public: Callable[[str], dict[str, Any]]
    mode_label: Callable[[dict[str, Any]], str]
    now: Callable[[Any], datetime]
    apple_resource_snapshot: Callable[..., Any]
    dflash2_capability_valid: Callable[..., Any]
    dflash_quantized_fallback: Callable[..., Any]
    display_size: Callable[..., Any]
    hardware_fingerprint: Callable[..., Any]
    is_qwen4_exp_record: Callable[..., Any]
    lmstudio_mtp_controls: Callable[..., Any]
    public_session_resource: Callable[..., Any]
    safe_int: Callable[..., Any]
    session_memory_admission: Callable[..., Any]
    ssd_profile_candidate_backends: Callable[..., Any]




def cross_engine_workload_compatibility(
    group: list[dict[str, Any]],
) -> dict[str, Any]:
    """Separate a real workload mismatch from harmless backend output drift."""
    if len(group) < 2:
        return {
            "comparable": False, "exactOutputMatch": False,
            "warning": "At least two completed engine measurements are required.",
        }
    if len({str(item.get("signature") or "") for item in group}) != 1:
        return {
            "comparable": False, "exactOutputMatch": False,
            "warning": "The engines did not run the same generated input schedule.",
        }

    def bounded(values: list[int], *, minimum: int, ratio: float) -> bool:
        if not values or any(value <= 0 for value in values):
            return False
        limit = max(minimum, math.ceil(max(values) * ratio))
        return max(values) - min(values) <= limit

    quality_tokens = [int(item["qualityCompletionTokens"]) for item in group]
    if not bounded(quality_tokens, minimum=2, ratio=0.02):
        return {
            "comparable": False, "exactOutputMatch": False,
            "warning": (
                "The deterministic probe produced materially different response lengths "
                "across engines, so their timings are not comparable."
            ),
        }

    observed = [item.get("observedSampleTokens") for item in group]
    if any(not isinstance(samples, list) or not samples for samples in observed):
        return {
            "comparable": False, "exactOutputMatch": False,
            "warning": "One engine returned incomplete token accounting for the measured workload.",
        }
    assert all(isinstance(samples, list) for samples in observed)
    sample_count = len(observed[0])
    if any(len(samples) != sample_count for samples in observed):
        return {
            "comparable": False, "exactOutputMatch": False,
            "warning": "The engines completed different numbers of generated workload stages.",
        }
    for index in range(sample_count):
        prompt_tokens = [int(samples[index]["promptTokens"]) for samples in observed]
        completion_tokens = [int(samples[index]["completionTokens"]) for samples in observed]
        if not bounded(prompt_tokens, minimum=64, ratio=0.01):
            return {
                "comparable": False, "exactOutputMatch": False,
                "warning": (
                    "The engines tokenised a generated prompt too differently for a fair "
                    "performance comparison."
                ),
            }
        if not bounded(completion_tokens, minimum=2, ratio=0.02):
            return {
                "comparable": False, "exactOutputMatch": False,
                "warning": (
                    "The engines generated materially different amounts of measured output, "
                    "so their complete-workload times are not comparable."
                ),
            }

    quality_contracts = {
        (item.get("qualityFingerprint"), item.get("qualityCompletionTokens"))
        for item in group
    }
    exact_output = len(quality_contracts) == 1
    return {
        "comparable": True,
        "exactOutputMatch": exact_output,
        "warning": "" if exact_output else (
            "Generated wording varied slightly across engines. The result remains usable: "
            "the model, generated inputs and settings matched, and token counts stayed within "
            "the comparison tolerance."
        ),
    }


def _speed_ranked_entries(group: list[dict[str, Any]]) -> list[dict[str, Any]]:
    higher_is_better = bool(group[0]["higherIsBetter"])
    return sorted(
        group, key=lambda item: float(item["score"]), reverse=higher_is_better,
    )


def _speed_lead(winner: dict[str, Any], runner_up: dict[str, Any]) -> float:
    if winner.get("higherIsBetter"):
        return float(winner["score"]) / max(float(runner_up["score"]), 0.000_001)
    return float(runner_up["score"]) / max(float(winner["score"]), 0.000_001)


def route_qualification_engine_reason(backend: str) -> str:
    """Describe the one route being qualified without exposing its internal lane id."""
    if backend == "uzu":
        return (
            "Runs the exact fixed DFlash + Weaver route with packaged reasoning and "
            "requires both reasoning and final-answer output."
        )
    return (
        "Runs the exact PLE mmap AR route with explicit reasoning and requires both "
        "reasoning and final-answer output."
    )


def model_acceleration_family(model: dict[str, Any]) -> str:
    """Return a conservative name family used only to suggest explicit model alternatives."""
    name = str(model.get("name") or "").strip().lower()
    if not name:
        return ""
    family = re.split(r"-(?:mtplx|mlx)(?:-|$)", name, maxsplit=1)[0]
    return re.sub(r"[^a-z0-9.]+", "-", family).strip("-")


def _benchmark_created_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class BenchmarkSelection:
    def __init__(self, policy: SelectionPolicy, contracts: SelectionContracts,
                 evidence: SelectionEvidence, live: SelectionLive):
        self.policy, self.contracts = policy, contracts
        self.evidence, self.live = evidence, live

    def fastest_safe_options(self, 
        backend: str,
        capability: dict[str, Any],
        current_options: dict[str, Any] | None,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return the best evidence-backed, quality-preserving visible controls.

        This deliberately owns only performance controls. Model choice, weight and
        KV precision, context, response ceiling, reasoning, sampling, prompts, and
        tools are outside the transform. DFlash is selected only when a future
        scanner has both verified the exact pairing and supplied benchmark evidence
        that names it as the preferred route.
        """
        if backend not in self.policy.optimizer_keys:
            raise ValueError("Choose a supported runtime.")
        options = dict(current_options or {})
        before = dict(options)
        rationale: list[str] = []

        if self.live.dflash_quantized_fallback(backend, options):
            # Switching this explicit route to AR/MTP would change the primary
            # cache from full precision to the selected quantised fallback.
            return {
                "options": options, "changedKeys": [], "appliedKeys": [],
                "preservedKeys": [
                    "model", "quantisation", "context", "output", "reasoning",
                    "sampling", "prompts", "tools", "kv", "fan",
                ],
                "evidenceTier": "manual-route",
                "evidenceLabel": "Manual DFlash route preserved",
                "rationale": [self.policy.dflash_kv_comparison_reason],
                "dflashStatus": self.policy.dflash_kv_comparison_reason,
            }

        if backend == "uzu":
            options.update({"acceleration": "off", "depth": 1, "kv": "off"})
            local_benchmark = self.evidence.verified_local_benchmark(capability, evidence)
            local_verified = local_benchmark is not None
            return {
                "options": options,
                "changedKeys": [],
                "appliedKeys": [],
                "preservedKeys": [
                    "model", "quantisation", "context", "output", "reasoning",
                    "sampling", "prompts", "tools",
                ],
                "evidenceTier": (
                    "local-benchmark" if local_verified else "pinned-uzu-speculative-route"
                ),
                "evidenceLabel": (
                    "Locally measured Uzu route" if local_verified else
                    "Pinned Uzu DFlash + Weaver route"
                ),
                "rationale": [
                    "Use the artifact's bundled DFlash draft and runtime-managed Weaver verification tree.",
                    "Keep prefix caching enabled while preserving model, reasoning, sampling, and full-precision KV semantics.",
                ],
                "dflashStatus": "DFlash + Weaver is fixed and owned by this Uzu artifact.",
            }

        preferred = capability.get("preferredAcceleration")
        local_benchmark = self.evidence.verified_local_benchmark(capability, evidence)
        local_verified = local_benchmark is not None
        if capability.get("preferredAccelerationSource") == "local-benchmark":
            if local_verified:
                winner = local_benchmark.get("winner")
                preferred = {"ar": "off", "mtp": "mtp", "dflash2": "dflash"}.get(winner)
            else:
                preferred = capability.get("fallbackAcceleration")
        if preferred == "dflash":
            dflash_ready = (
                str(options.get("kv") or "off") == "off"
                and capability.get("dflash") is True
                and capability.get("dflashVersion") == "2"
                and capability.get("dflashPreferred") is True
                and capability.get("dflashBenchmarkVerified") is True
                and bool(capability.get("dflashDraftPath"))
                and bool(capability.get("dflashPairFingerprint"))
                and bool(capability.get("dflashRuntimeVersion"))
                and local_verified
                and self.evidence.dflash2_benchmark_verified(capability, evidence, local_benchmark)
            )
            if not dflash_ready:
                preferred = None
        if preferred == "mtp" and capability.get("mtp") is not True:
            preferred = None
        if preferred not in {"mtp", "dflash", "off"}:
            preferred = "mtp" if capability.get("mtp") is True else "off"

        options["acceleration"] = preferred
        if preferred == "dflash":
            rationale.append("A complete DFlash 2 pairing won the matching local benchmark.")
        elif preferred == "mtp":
            rationale.append("Use the model's validated speculative path while preserving the target distribution.")
        else:
            if capability.get("mtp") is True or capability.get("dflash") is True:
                rationale.append(
                    "Keep autoregressive decoding because no matching local benchmark currently proves a speculative winner."
                )
            else:
                rationale.append("Use autoregressive decoding because no speculative path is verified for this artifact.")

        evidence_tier = "local-benchmark" if local_verified else "safe-runtime-recommendation"
        evidence_label = "Locally benchmarked speed preset" if local_verified else "Safe runtime recommendation"
        measured_engine_settings = (
            local_benchmark.get("engineSettings")
            if local_verified and isinstance(local_benchmark.get("engineSettings"), dict)
            else {}
        )
        if backend == "omlx":
            options["burst"] = str(measured_engine_settings.get("burst") or "aggressive")
            qwen_ple = capability.get("qwen4Ple")
            measured_memory_guard = str(measured_engine_settings.get("memoryGuard") or "")
            if isinstance(qwen_ple, dict) and qwen_ple.get("supported") is True:
                options["memoryGuard"] = "high"
                rationale.append(
                    "Use the dedicated Qwen PLE High memory guard required by this mmap route."
                )
            elif measured_memory_guard in {"balanced", "high"}:
                options["memoryGuard"] = measured_memory_guard
            measured_ane_prefill = str(measured_engine_settings.get("anePrefill") or "")
            options["anePrefill"] = (
                measured_ane_prefill
                if local_verified and measured_ane_prefill in {"off", "tuned"}
                else "off"
            )
            if preferred in {"mtp", "dflash"}:
                options["depth"] = self.live.safe_int(
                    capability.get("depth"), 1, 1, int(capability.get("depthMax") or 8)
                )
            if preferred == "dflash":
                benchmark_settings = local_benchmark["settings"]
                options["depth"] = int(benchmark_settings["blockSize"])
                options["dflashDraftQuant"] = str(benchmark_settings["draftQuant"])
                options["dflashVerify"] = str(benchmark_settings["verifyMode"])
            rationale.append("Use oMLX's throughput-oriented stream batching; target tokens remain unchanged.")
            rationale.append(
                "Reuse the exact locally measured ANE prefill setting."
                if options["anePrefill"] == "tuned" else
                "Keep approximate ANE prefill off unless a matching local result measured it."
            )
            if preferred == "dflash":
                evidence_tier = "local-benchmark"
                evidence_label = "Locally benchmarked speed preset"
            elif preferred == "mtp" and local_verified:
                benchmark_settings = local_benchmark.get("settings") or {}
                options["depth"] = int(benchmark_settings.get("depth") or options.get("depth") or 1)
        elif backend == "lmstudio":
            options["gpu"] = str(measured_engine_settings.get("gpu") or "max")
            options["parallel"] = self.live.safe_int(
                measured_engine_settings.get("parallel"), 1, 1, 16,
            )
            if preferred == "mtp":
                measured_settings = (
                    local_benchmark.get("settings")
                    if local_verified and local_benchmark.get("winner") == "mtp"
                    else None
                )
                controls = self.live.lmstudio_mtp_controls(
                    measured_settings if isinstance(measured_settings, dict) else {},
                    capability,
                )
                options.update(controls)
            rationale.append("Use full GPU offload and one request lane for a single coding agent.")
            if preferred == "mtp":
                if local_verified and local_benchmark.get("winner") == "mtp":
                    rationale.append(
                        "Reuse the exact locally measured MTP draft size, minimum, and probability cutoff."
                    )
                else:
                    evidence_tier = "artifact-validated"
                    evidence_label = "Artifact-backed speed recommendation"
                    rationale.append(
                        "Keep LM Studio's conservative MTP minimum and probability defaults until this route is benchmarked."
                    )
        elif backend == "mtplx":
            options["mtplxOperatorRoute"] = self.policy.mtplx_long_context_default_route
            options["profile"] = str(
                measured_engine_settings.get("profile")
                or capability.get("profile") or "sustained"
            )
            # Cooling is a user-owned safety control. A speed preset may tune the
            # runtime profile, but must never promote an ordinary route to forced
            # maximum fans. Exact benchmark matching already includes fan policy,
            # so maximum-cooling evidence cannot be reused for this normal route.
            selected_fan = str(before.get("fan") or "smart")
            options["fan"] = selected_fan if selected_fan in {"default", "smart", "max"} else "smart"
            if preferred == "mtp":
                measured_settings = (
                    local_benchmark.get("settings")
                    if local_verified and local_benchmark.get("winner") == "mtp"
                    else None
                )
                options["depth"] = self.live.safe_int(
                    measured_settings.get("depth") if isinstance(measured_settings, dict) else capability.get("depth"),
                    int(capability.get("depth") or 1),
                    1, int(capability.get("depthMax") or 1),
                )
                measured_operator_route = (
                    str(measured_settings.get("mtplxOperatorRoute") or "")
                    if isinstance(measured_settings, dict) else ""
                )
                operator_sweep = (
                    local_benchmark.get("mtplxOperatorSweep")
                    if isinstance(local_benchmark, dict) else None
                )
                if (
                    measured_operator_route == self.policy.mtplx_long_context_2111_route
                    and isinstance(operator_sweep, dict)
                    and operator_sweep.get("candidateAccepted") is True
                    and operator_sweep.get("selectedRoute")
                    == self.policy.mtplx_long_context_2111_route
                ):
                    options["mtplxOperatorRoute"] = self.policy.mtplx_long_context_2111_route
                    rationale.append(
                        "Reuse the exact locally measured MTPLX 2.11.1 long-context operator route."
                    )
                if not local_verified:
                    evidence_tier = "artifact-benchmark"
                    evidence_label = "Artifact-backed speed preset"
                else:
                    rationale.append("Reuse the exact MTPLX draft depth that won the matching local measurement.")
            rationale.append(
                "Reuse the measured MTPLX profile while preserving your visible cooling choice."
                if measured_engine_settings else
                "Use the artifact's validated MTPLX profile and keep cooling on your visible choice."
            )
        elif backend == "freetoken":
            options.update({"acceleration": "off", "depth": 1, "kv": "off"})
            if capability.get("native") is True:
                options.update({
                    "maxBatchSize": 1,
                    "expertCacheSize": None,
                    "prefixCacheEntries": 0,
                })
                evidence_tier = "native-safe-default"
                evidence_label = "Native FreeToken safe default"
                rationale.extend([
                    "Use one active sequence for the lowest single-chat scheduling overhead.",
                    "Keep resident Metal experts and prefix caching at the port defaults until matching local measurements justify another placement.",
                ])
            else:
                evidence_tier = "remote-runtime-managed"
                evidence_label = "FreeToken server-managed route"
                rationale.append(
                    "Keep execution policy on the connected FreeToken server; preserve the visible request contract without inventing a remote tuning result."
                )
        elif backend == "swiftlm":
            native_top_k = max(0, int(capability.get("nativeExpertTopK") or 0))
            options.update({
                "acceleration": "off", "depth": 1, "kv": "off",
                "prefillSize": self.live.safe_int(
                    measured_engine_settings.get("prefillSize"),
                    int(capability.get("prefillSize") or 512),
                    min(self.policy.ssd_streaming_prefill_sizes), max(self.policy.ssd_streaming_prefill_sizes),
                ),
                "nativeExpertTopK": native_top_k,
            })
            evidence_tier = "local-benchmark" if local_verified else "exact-ssd-streaming-default"
            evidence_label = "Locally measured SSD-streaming preset" if local_verified else "Exact SSD-streaming default"
            rationale.extend([
                "Stream routed experts from SSD while keeping the checkpoint's native expert count per token.",
                "Keep speculative decoding off so draft verification cannot multiply SSD expert reads.",
            ])
        elif backend == "mference":
            options.update({
                "acceleration": "off", "depth": 1, "kv": "off",
                "promptCacheMode": str(measured_engine_settings.get("promptCacheMode") or "on"),
                "queueLimit": self.live.safe_int(
                    measured_engine_settings.get("queueLimit"),
                    int(capability.get("queueLimit") or 4), 1, 32,
                ),
            })
            evidence_tier = "local-benchmark" if local_verified else "verified-gturbo-default"
            evidence_label = "Locally measured SSD-streaming preset" if local_verified else "Verified .gturbo default"
            rationale.extend([
                "Use the verified .gturbo expert layout and one model-native routed-expert path.",
                "Keep the prompt cache enabled for repeated agent prefixes without changing generated tokens.",
            ])
        elif backend == "slotstream":
            measured_depth = (local_benchmark.get("settings") or {}).get("depth") if local_verified else None
            options.update({"acceleration": preferred,
                            "depth": int(measured_depth or capability.get("depth") or 2) if preferred == "mtp" else 1,
                            "kv": str(options.get("kv") or "off"), "memoryGB": int(measured_engine_settings.get("memoryGB") or options.get("memoryGB") or slotstream_runtime.DEFAULT_MEMORY_GB),
                            "memoryMode": str(measured_engine_settings.get("memoryMode") or options.get("memoryMode") or "auto")})
            evidence_tier = "local-benchmark" if local_verified else "pinned-runtime-default"
            evidence_label = "Locally measured Slotstream route" if local_verified else "Slotstream starting preset · not locally benchmarked"
            rationale.append("Keep all 512 experts and native routing, with an explicit MTP choice and a checked process memory budget.")
        elif backend == "kolibri":
            options.update({"acceleration": "off", "depth": 1})
            options.setdefault("kv", "off")
            options.setdefault("memoryGB", kolibri_runtime.DEFAULT_MEMORY_GB)
            options.setdefault("memoryMode", "auto")
            options.setdefault("prefillSize", kolibri_runtime.DEFAULT_PREFILL)
            options.setdefault("promptCacheGB", kolibri_runtime.DEFAULT_PROMPT_CACHE_GB)
            evidence_tier = "runtime-default"
            evidence_label = "Kolibri SSD starting settings · not a speed benchmark"
            rationale.append("Keep the full Q6 weights and native top-6 routing; spend available memory on expert caching within the selected ceiling.")
        elif backend == "splash":
            options.update({"acceleration": "off", "depth": 1, "kv": "off"})
            evidence_tier = "engine-owned-model"
            evidence_label = "Splash route · engine-owned speed"
            rationale.extend([
                "Keep the selected target quantization and matching DFlash2 draft; Splash manages speculative decoding.",
                "Keep the engine's paged KV plan so speculative verification stays exact.",
            ])
        elif backend == "whallm":
            options.update({"acceleration": "off", "depth": 1, "kv": "off"})
            evidence_tier = "shared-pinned-ssd-route"
            evidence_label = "Whallm full-expert route"
            rationale.extend([
                "Keep Whallm's pinned full 512-expert MXFP4 execution contract unchanged.",
                "Use the running shared server directly; this launcher does not invent an accelerator or compare it with a pruned checkpoint.",
            ])
        elif backend == "llamacpp":
            options.update({"acceleration": "off", "depth": 1, "kv": "off"})
            evidence_tier = "pinned-ssd-ple-route"
            evidence_label = "Pinned llama.cpp SSD-PLE route"
            rationale.extend([
                "Keep the isolated PLE tensor in read-only SSD mmap through the exact audited runtime.",
                "Keep MTP, CPU-MoE, tensor overrides, and quantized KV disabled for the initial qualification.",
            ])

        changed = [
            key for key in self.policy.optimizer_keys[backend]
            if key in options and before.get(key) != options.get(key)
        ]
        applied = [
            key for key in self.policy.optimizer_keys[backend]
            if key in options
            and not (key == "depth" and preferred == "off")
            and not (
                key in {"mtpMinTokens", "mtpMinContinueProbability"}
                and preferred != "mtp"
            )
            and not (key in {"dflashVerify", "dflashDraftQuant"} and preferred != "dflash")
        ]
        return {
            "options": options,
            "changedKeys": changed,
            "appliedKeys": applied,
            "preservedKeys": [
                "model", "quantisation", "context", "output", "reasoning",
                "sampling", "prompts", "tools", "kv", "fan",
            ],
            "evidenceTier": evidence_tier,
            "evidenceLabel": evidence_label,
            "rationale": rationale,
            "dflashStatus": capability.get("dflashReason") or "No verified DFlash 2 pairing.",
        }


    def optimizer_evidence(self, 
        model: dict[str, Any], context: int, output: int, client: str, reasoning: str, kv: str,
        chat: dict[str, Any] | None = None,
        sampling_contract_document: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if sampling_contract_document is None and client == "chat":
            if chat and chat.get("sampling") in {"model", "custom"}:
                sampling_contract_document = self.contracts.sampling_contract_from_settings(model, chat)
            else:
                sampling_contract_document = self.contracts.build_sampling_contract(
                    "model", model_defaults=model.get("defaultSampling"),
                ).as_dict()
        contract = None
        if sampling_contract_document is not None:
            try:
                contract = self.contracts.load_sampling_contract(sampling_contract_document)
            except SamplingContractError as error:
                raise ValueError(str(error)) from error
        sampling = (
            contract.values if contract is not None else
            self.contracts.canonicalize_sampling(
                model.get("defaultSampling")
                if isinstance(model.get("defaultSampling"), dict) else {}
            )
        )
        compatibility_fingerprint = hashlib.sha256(json.dumps(
            sampling,
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        return {
            "context": context,
            "output": output,
            "client": client or "any",
            "reasoning": reasoning or "auto",
            "kv": kv or "off",
            "samplingFingerprint": compatibility_fingerprint,
            "samplingEvidenceVersion": self.policy.sampling_evidence_schema_version,
            "samplingControlled": contract is not None,
            "samplingContractVersion": (
                self.policy.sampling_contract_schema_version if contract is not None else None
            ),
            "samplingContract": contract.as_dict() if contract is not None else None,
            "samplingContractFingerprint": (
                self.contracts.sampling_fingerprint(contract) if contract is not None else None
            ),
        }


    def add_benchmark_engine_evidence(self, 
        evidence: dict[str, Any], model: dict[str, Any], raw_options: dict[str, Any] | None,
        backends: list[str],
    ) -> dict[str, Any]:
        """Bind fixed engine controls without mixing them into the shared prompt contract."""
        by_backend: dict[str, dict[str, Any]] = {}
        cross_engine = len(backends) > 1
        for backend in backends:
            capability = model.get("backends", {}).get(backend, {})
            canonical = (
                self.contracts.validated_cross_engine_profile_options(
                    backend, model, capability, raw_options,
                )
                if cross_engine else
                self.contracts.validated_profile_options(backend, model, capability, raw_options)
            )
            settings = self.evidence.benchmark_engine_settings(backend, canonical)
            if backend == "omlx" and self.live.is_qwen4_exp_record(model):
                settings["pleStorage"] = "mmap"
            by_backend[backend] = settings
        evidence["engineSettingsByBackend"] = by_backend
        if len(backends) == 1:
            evidence["engineSettings"] = copy.deepcopy(by_backend[backends[0]])
        return evidence


    def validated_optimizer_evidence_binding(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Validate an optional UI receipt binding without trusting display metadata."""
        raw = payload.get("evidenceBinding")
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise ValueError("The saved performance result reference is invalid. Refresh it before applying.")
        scope = str(raw.get("scope") or "")
        if scope not in {"engine", "route"}:
            raise ValueError("The saved performance result has an unsupported scope. Refresh it before applying.")
        suite = str(raw.get("suite") or "")
        if suite not in self.policy.benchmark_suites:
            raise ValueError("The saved performance result no longer names a supported workload suite.")
        preference = str(raw.get("preference") or "throughput")
        if preference not in self.policy.engine_preference_labels:
            raise ValueError("The saved performance result no longer names a supported decision goal.")

        def identifier(key: str) -> str:
            value = str(raw.get(key) or "")
            if value and (len(value) > 128 or re.fullmatch(r"[A-Za-z0-9._:-]+", value) is None):
                raise ValueError("The saved performance result reference is invalid. Refresh it before applying.")
            return value

        shootout_id = identifier("shootoutId")
        record_id = identifier("recordId")
        raw_record_ids = raw.get("recordIds")
        record_ids: dict[str, str] = {}
        if raw_record_ids is not None:
            if not isinstance(raw_record_ids, dict):
                raise ValueError("The saved engine comparison reference is invalid. Refresh it before applying.")
            for backend, value in raw_record_ids.items():
                if backend not in self.policy.engine_adapters or not isinstance(value, str):
                    raise ValueError("The saved engine comparison reference is invalid. Refresh it before applying.")
                if not value or len(value) > 128 or re.fullmatch(r"[A-Za-z0-9._:-]+", value) is None:
                    raise ValueError("The saved engine comparison reference is invalid. Refresh it before applying.")
                record_ids[str(backend)] = value
        if scope == "route" and not record_id:
            raise ValueError("The saved route result has no exact record reference. Refresh it before applying.")
        if scope == "route" and (shootout_id or record_ids):
            raise ValueError("The saved route result reference is inconsistent. Refresh it before applying.")
        if scope == "engine" and record_id:
            raise ValueError("The saved engine comparison reference is inconsistent. Refresh it before applying.")
        if scope == "engine" and (not shootout_id or not record_ids):
            raise ValueError(
                "The saved engine comparison has no exact shootout and record references. "
                "Refresh it before applying."
            )
        result: dict[str, Any] = {
            "scope": scope, "suite": suite, "preference": preference,
        }
        if shootout_id:
            result["shootoutId"] = shootout_id
        if record_id:
            result["recordId"] = record_id
        if record_ids:
            result["recordIds"] = record_ids
        return result


    def optimizer_bound_engine_settings(self, 
        model: dict[str, Any], eligible_backends: list[str], binding: dict[str, Any],
        raw_options: dict[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:
        """Resolve engine-owned controls from one exact bound shootout.

        Engine settings are deliberately outside the shared comparison contract. A
        completed tuner may therefore have measured a different valid engine profile
        from the one still visible in the UI (for example MTPLX Turbo after starting
        Calibration from Sustained).  The immutable record IDs are the authority for
        those engine-owned controls; model, context, reasoning, sampling, limits and
        KV precision continue to come from the current request and are verified later.
        """
        if binding.get("scope") != "engine":
            raise ValueError("A route result cannot supply cross-engine settings.")
        record_ids = binding.get("recordIds")
        if (
            not isinstance(record_ids, dict)
            or set(record_ids) != set(eligible_backends)
            or len(set(record_ids.values())) != len(record_ids)
        ):
            raise ValueError(
                "That saved engine comparison no longer names every compatible engine. "
                "Refresh performance evidence before applying it."
            )
        shootout_id = str(binding.get("shootoutId") or "")
        suite = str(binding.get("suite") or "")
        resolved: dict[str, dict[str, Any]] = {}
        for backend in eligible_backends:
            capability = model.get("backends", {}).get(backend)
            if not isinstance(capability, dict):
                raise ValueError(
                    "That saved engine comparison references a route that is no longer available."
                )
            records = capability.get("localBenchmarks")
            candidates = [
                item for item in records if isinstance(item, dict)
            ] if isinstance(records, list) else []
            latest = capability.get("localBenchmark")
            if isinstance(latest, dict) and latest not in candidates:
                candidates.append(latest)
            matches = [
                record for record in candidates
                if str(record.get("id") or "") == str(record_ids[backend])
                and str(record.get("backend") or "") == backend
                and str(record.get("shootoutId") or "") == shootout_id
                and str(record.get("suite") or "") == suite
            ]
            if len(matches) != 1:
                raise ValueError(
                    "That saved engine comparison is stale or incomplete. "
                    "Refresh performance evidence before applying it."
                )
            stored = matches[0].get("engineSettings")
            if not isinstance(stored, dict):
                raise ValueError(
                    "That saved engine comparison has no validated engine controls. "
                    "Refresh performance evidence before applying it."
                )
            visible_options = self.contracts.validated_cross_engine_profile_options(
                backend, model, capability, raw_options,
            )
            visible_settings = self.evidence.benchmark_engine_settings(backend, visible_options)
            if (
                backend == "mtplx"
                and stored.get("fan") != visible_settings.get("fan")
            ):
                raise ValueError(
                    "That saved engine comparison used a different cooling setting. "
                    "Restore its measured cooling choice or rerun Calibration."
                )
            if backend == "omlx" and any(
                stored.get(key) != visible_settings.get(key)
                for key in ("anePrefill", "memoryGuard")
            ):
                raise ValueError(
                    "That saved engine comparison used different fixed oMLX settings "
                    "(ANE prefill or memory guard). Restore those settings or rerun Calibration."
                )
            option_source = copy.deepcopy(raw_options or {})
            option_source.update(copy.deepcopy(stored))
            canonical = self.contracts.validated_cross_engine_profile_options(
                backend, model, capability, option_source,
            )
            expected = self.evidence.benchmark_engine_settings(backend, canonical)
            if stored != expected:
                raise ValueError(
                    "That saved engine comparison contains invalid engine controls. "
                    "Refresh performance evidence before applying it."
                )
            resolved[backend] = copy.deepcopy(expected)
        return resolved


    def route_qualification_record_is_fresh(self, 
        record: dict[str, Any], now: datetime | None = None,
    ) -> bool:
        """Keep stale single-route receipts from driving Apply/Best decisions."""
        created = _benchmark_created_at(record.get("createdAt"))
        if created is None:
            return False
        current = (now or self.live.now(timezone.utc)).astimezone(timezone.utc)
        if created > current:
            return False
        age_days = max(0.0, (current - created).total_seconds() / 86_400)
        return age_days <= self.policy.benchmark_history_fresh_days


    def optimizer_evidence_bound_route_record(self, 
        capability: dict[str, Any], backend: str, binding: dict[str, Any],
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve exactly one still-valid route record named by a displayed receipt."""
        records = capability.get("localBenchmarks")
        candidates = [item for item in records if isinstance(item, dict)] if isinstance(records, list) else []
        latest = capability.get("localBenchmark")
        if isinstance(latest, dict) and latest not in candidates:
            candidates.append(latest)
        matches = [
            record for record in candidates
            if str(record.get("id") or "") == binding["recordId"]
            and str(record.get("suite") or "") == binding["suite"]
            and str(record.get("backend") or "") == backend
            and not record.get("shootoutId")
            and self.route_qualification_record_is_fresh(record)
            and self.evidence.local_benchmark_record_verified(capability, record, evidence)
        ]
        if len(matches) != 1:
            raise ValueError(
                "That saved route measurement is stale or no longer matches the visible contract. "
                "Refresh performance evidence before applying it."
            )
        return copy.deepcopy(matches[0])


    def optimal_request(self, payload: dict[str, Any], models: list[dict[str, Any]]) -> dict[str, Any]:
        """Resolve an optimizer result without allocating a port or creating a run."""
        binding = self.validated_optimizer_evidence_binding(payload)
        if binding is not None and binding["scope"] != "route":
            raise ValueError("An engine comparison cannot be applied as a current-route result.")
        backend = str(payload.get("backend", ""))
        if backend not in self.policy.engine_adapters or backend not in self.policy.optimizer_keys:
            raise ValueError("Choose a compatible installed runtime, including Kolibri SSD.")
        client = str(payload.get("client", ""))
        if client not in self.policy.client_adapters:
            raise ValueError("Choose Pi, oh-my-pi, OpenCode, Codex, or Chat.")
        if client == "chat":
            agent_host = "launcher"
        else:
            agent_host = str(payload.get("agentHost") or "terminal")
            if agent_host not in {"console", "terminal"}:
                raise ValueError("Choose Hub Console or Terminal for this agent.")
            self.contracts.require_omp_console_support(client, agent_host)
        engine_adapter = self.policy.engine_adapters[backend]
        client_adapter = self.policy.client_adapters[client]
        if not self.live.binary(engine_adapter.binary_key or ""):
            raise ValueError(f"{backend} is not installed.")
        if not client_adapter.built_in and not self.live.binary(client_adapter.binary_key or ""):
            raise ValueError(f"{client} is not installed.")
        model_id = str(payload.get("modelId", ""))
        model = next((item for item in models if item.get("id") == model_id), None)
        if not model:
            raise ValueError("The selected model is no longer in the scanned catalog. Refresh models.")
        capability = model.get("backends", {}).get(backend, {})
        client_support = self.contracts.resolved_client_support(backend, client, capability)
        if not client_support["supported"]:
            raise ValueError(str(client_support["reason"]))
        if not capability.get("runnable"):
            raise ValueError(str(capability.get("reason") or "This model cannot run in the selected runtime."))
        options = copy.deepcopy(
            payload.get("options") if isinstance(payload.get("options"), dict) else {}
        )
        context, output = self.contracts.validated_limits(model, payload)
        self.contracts.validate_runtime_context(backend, context)
        chat = self.contracts.validated_chat_settings(model, payload, client)
        self.contracts.validate_chat_capability(capability, chat, client)
        sampling_contract = self.contracts.validated_sampling_contract(
            model, payload, client, chat,
        )
        assert sampling_contract is not None
        if client == "chat":
            chat = self.contracts.chat_settings_from_sampling_contract(
                sampling_contract,
                system_prompt=str(chat.get("systemPrompt") or ""),
            )
        self.contracts.validate_sampling_capability(capability, sampling_contract)
        reasoning = str(payload.get("reasoning", "auto"))
        if model.get("nativeWhallm") and reasoning == "auto":
            reasoning = "medium"
        if reasoning not in {"off", "minimal", "low", "medium", "high", "xhigh", "max", "auto"}:
            raise ValueError("Unknown reasoning level.")
        reasoning_key = "codexReasoning" if client == "codex" else "agentReasoning"
        allowed_reasoning = list(capability.get(reasoning_key) or ["auto"])
        if reasoning not in allowed_reasoning:
            choices = ", ".join("model default" if item == "auto" else item for item in allowed_reasoning)
            raise ValueError(f"This model/runtime route can enforce only these reasoning choices: {choices}.")
        evidence = self.optimizer_evidence(
            model, context, output, client, reasoning, str(options.get("kv") or "off"), chat,
            sampling_contract,
        )
        self.add_benchmark_engine_evidence(evidence, model, options, [backend])
        optimizer_capability = copy.deepcopy(capability)
        if backend == "omlx" and self.live.is_qwen4_exp_record(model):
            optimizer_capability["qwen4Ple"] = copy.deepcopy(model.get("qwen4Ple"))
        if binding is not None:
            record = self.optimizer_evidence_bound_route_record(
                capability, backend, binding, evidence,
            )
            optimizer_capability["localBenchmark"] = copy.deepcopy(record)
            optimizer_capability["localBenchmarks"] = [copy.deepcopy(record)]
            optimizer_capability["preferredAccelerationSource"] = "local-benchmark"
            optimizer_capability["preferredAcceleration"] = {
                "ar": "off", "mtp": "mtp", "dflash2": "dflash",
            }.get(str(record.get("winner") or ""), "off")
            if record.get("winner") == "dflash2":
                optimizer_capability["dflashPreferred"] = True
                optimizer_capability["dflashBenchmarkVerified"] = True
                optimizer_capability["dflashBenchmark"] = copy.deepcopy(record)
        result = self.fastest_safe_options(backend, optimizer_capability, options, evidence)
        result.update({"backend": backend, "modelId": model_id, "model": model.get("name")})
        if binding is not None:
            result["evidenceBinding"] = copy.deepcopy(binding)
        return result


    def optimizer_backend_eligibility(self, 
        model: dict[str, Any], backend: str, client: str, reasoning: str, kv: str,
        chat: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """Check whether an engine can preserve the visible request contract."""
        capability = model.get("backends", {}).get(backend, {})
        adapter = self.policy.engine_adapters.get(backend)
        if not adapter or not self.live.binary(adapter.binary_key or ""):
            return False, f"{self.policy.backend_labels.get(backend, backend or 'Engine')} is not installed."
        if backend == "llamacpp" and self.contracts.llamacpp_route_qualification_capability(model) is None:
            return False, (
                "The pinned llama.cpp route must finish SHA-256 verification in this "
                "controller before it can be optimised."
            )
        if not model.get("ready") or not capability.get("runnable"):
            return False, str(capability.get("reason") or "The model is not runnable in this engine.")
        support = self.contracts.resolved_client_support(backend, client, capability)
        if support.get("supported") is not True:
            return False, str(support.get("reason") or "This work surface is not supported.")
        if (
            client == "chat" and isinstance(chat, dict)
            and chat.get("sampling") == "custom"
            and capability.get("customSampling") is False
        ):
            return False, str(
                capability.get("samplingReason")
                or "This engine cannot preserve custom sampling."
            )
        reasoning_key = "codexReasoning" if client == "codex" else "agentReasoning"
        allowed_reasoning = list(capability.get(reasoning_key) or ["auto"])
        if reasoning not in allowed_reasoning:
            if backend == "lmstudio" and allowed_reasoning == ["auto"]:
                requested = "model default" if reasoning == "auto" else reasoning
                return False, (
                    "LM Studio can use the model's own reasoning on this route, but it cannot "
                    f"select {requested}; it exposes model-default reasoning only."
                )
            return False, "This engine cannot preserve the selected reasoning level."
        allowed_kv = {
            "omlx": {"off", "q8", "q6", "q4"},
            "lmstudio": {"off"},
            "mtplx": {"off", "q8", "q4"},
            "uzu": {"off"},
            "freetoken": {"off"},
            "swiftlm": {"off"},
            "mference": {"off"},
            "whallm": {"off"},
            "slotstream": {"off", "q8"},
            "splash": {"off"},
            "kolibri": set(kolibri_runtime.KV_CHOICES),
            "llamacpp": {"off"},
        }[backend]
        if kv not in allowed_kv or (kv != "off" and capability.get("kv") is not True):
            return False, "This engine cannot preserve the selected KV precision."
        return True, "Compatible with the full visible request contract."


    def benchmark_backend_eligibility(self, 
        model: dict[str, Any], backend: str, client: str, reasoning: str, kv: str,
        chat: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """Check the common benchmark route without describing model-default reasoning as absent."""
        if backend == "uzu" and client == "pi":
            return False, self.policy.uzu_pi_benchmark_limitation
        allowed, reason = self.optimizer_backend_eligibility(
            model, backend, client, reasoning, kv, chat,
        )
        if not allowed:
            return allowed, reason
        capability = model.get("backends", {}).get(backend, {})
        benchmark_reasoning = list(capability.get("agentReasoning") or ["auto"])
        if reasoning in benchmark_reasoning:
            return True, "Compatible with the complete benchmark contract."
        requested = "model default" if reasoning == "auto" else reasoning
        if backend == "lmstudio" and benchmark_reasoning == ["auto"]:
            return False, (
                "LM Studio can use the model's own reasoning, but its Chat Completions "
                f"benchmark route cannot select {requested}; it exposes model-default reasoning only."
            )
        choices = ", ".join(
            "model default" if item == "auto" else str(item)
            for item in benchmark_reasoning
        )
        return False, (
            f"This engine's common benchmark route cannot select {requested}; "
            f"available choices: {choices}."
        )


    def benchmark_reasoning_contract(self, 
        payload: dict[str, Any], model: dict[str, Any], *,
        policy: str | None = None,
    ) -> dict[str, Any]:
        """Resolve one honest common reasoning setting for a cross-engine measurement."""
        requested = str(payload.get("reasoning") or "auto")
        selected_policy = str(
            policy or payload.get("reasoningPolicy") or self.policy.benchmark_reasoning_policy_exact
        )
        if selected_policy not in {
            self.policy.benchmark_reasoning_policy_exact,
            self.policy.benchmark_reasoning_policy_all_engines,
        }:
            raise ValueError("Choose an exact or all-engine benchmark reasoning policy.")
        contract = {
            "policy": selected_policy,
            "requested": requested,
            "measured": requested,
            "normalized": False,
            "normalizedFor": [],
            "normalizedForLabels": [],
            "label": "Model default" if requested == "auto" else requested,
            "detail": "The selected reasoning setting is preserved across every measured engine.",
            "changesVisibleSettingWhenApplied": False,
        }
        if selected_policy != self.policy.benchmark_reasoning_policy_all_engines or requested == "auto":
            return contract

        client = str(payload.get("client") or "")
        options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
        kv = str(options.get("kv") or "off")
        chat = payload.get("chat") if isinstance(payload.get("chat"), dict) else None
        normalized_for: list[str] = []
        for backend in self.policy.engine_adapters:
            if backend == "freetoken":
                continue
            requested_allowed, _ = self.benchmark_backend_eligibility(
                model, backend, client, requested, kv, chat,
            )
            default_allowed, _ = self.benchmark_backend_eligibility(
                model, backend, client, "auto", kv, chat,
            )
            capability = model.get("backends", {}).get(backend, {})
            benchmark_choices = list(capability.get("agentReasoning") or ["auto"])
            if not requested_allowed and default_allowed and benchmark_choices == ["auto"]:
                normalized_for.append(backend)
        if not normalized_for:
            return contract

        labels = [self.policy.backend_labels[backend] for backend in normalized_for]
        contract.update({
            "measured": "auto",
            "normalized": True,
            "normalizedFor": normalized_for,
            "normalizedForLabels": labels,
            "label": "Model default",
            "detail": (
                f"Reasoning is normalised from {requested} to model default for every measured "
                f"engine so {', '.join(labels)} can join one like-for-like comparison."
            ),
            "changesVisibleSettingWhenApplied": True,
        })
        return contract


    def cross_engine_benchmark_measurement(self, 
        record: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Return a score plus the generated-input contract used across engines.

        Exact generated text is deliberately not part of the cross-engine grouping
        key. Backends can differ by one terminal token or make a numerically valid
        greedy branch while still running the same model and generated workload.
        Observed token counts remain available for the bounded comparability check
        below; runtime promotion keeps its stricter byte-for-byte parity gate.
        """
        quality_fingerprint = record.get("qualityFingerprint")
        quality_tokens = record.get("qualityCompletionTokens")
        ssd_identity = record.get("ssdComparisonIdentity")
        is_ssd_measurement = record.get("ssdStreaming") is True
        if (
            record.get("comparisonContractVersion") not in {2, 3, self.policy.benchmark_comparison_contract_version}
            or not isinstance(quality_fingerprint, str)
            or re.fullmatch(r"[0-9a-f]{64}", quality_fingerprint) is None
            or isinstance(quality_tokens, bool)
            or not isinstance(quality_tokens, int)
            or quality_tokens <= 0
        ):
            return None
        if is_ssd_measurement:
            if (
                str(record.get("backend") or "") not in self.policy.ssd_streaming_backends
                or not isinstance(ssd_identity, str)
                or re.fullmatch(r"[0-9a-f]{64}", ssd_identity) is None
            ):
                return None
        elif ssd_identity not in {None, ""}:
            return None
        winner = str(record.get("winner") or "")
        modes = record.get("modes")
        result = modes.get(winner) if isinstance(modes, dict) else None
        samples = result.get("samples") if isinstance(result, dict) else None
        if not isinstance(samples, list) or not samples:
            return None
        workload = str(record.get("workloadKind") or "throughput")
        sample_contract: list[dict[str, Any]] = []
        observed_sample_tokens: list[dict[str, Any]] = []
        total_seconds = 0.0
        completion_tokens = 0
        first_token_seconds: list[float] = []
        for sample in samples:
            if not isinstance(sample, dict):
                return None
            seconds = sample.get("totalSeconds")
            ttft = sample.get("ttftSeconds")
            prompt_tokens = sample.get("promptTokens")
            generated = sample.get("completionTokens")
            if (
                isinstance(seconds, bool) or not isinstance(seconds, (int, float))
                or not math.isfinite(float(seconds)) or float(seconds) <= 0
                or isinstance(prompt_tokens, bool) or not isinstance(prompt_tokens, int)
                or prompt_tokens <= 0
                or isinstance(generated, bool) or not isinstance(generated, int)
                or generated <= 0
                or (ttft is not None and (
                    isinstance(ttft, bool) or not isinstance(ttft, (int, float))
                    or not math.isfinite(float(ttft)) or float(ttft) <= 0
                ))
            ):
                return None
            total_seconds += float(seconds)
            completion_tokens += generated
            if ttft is not None:
                first_token_seconds.append(float(ttft))
            base = {"targetPromptTokens": sample.get("targetPromptTokens")}
            if workload == "agentic":
                base["scenario"] = sample.get("scenario")
            else:
                base["repetition"] = sample.get("repetition")
            sample_contract.append(base)
            observed_sample_tokens.append({
                **base,
                "promptTokens": prompt_tokens,
                "completionTokens": generated,
            })
        if workload == "agentic":
            score = total_seconds
            metric = "agentic-total-seconds"
            display = f"{score:.2f}s staged total"
            higher_is_better = False
        else:
            score = completion_tokens / total_seconds
            metric = "aggregate-end-to-end-tokens-per-second"
            display = f"{score:.1f} output tok/s"
            higher_is_better = True
        contract = {
            "modelContractKind": "ssd-source" if is_ssd_measurement else "artifact",
            "modelContract": ssd_identity if is_ssd_measurement else record.get("modelFingerprint"),
            "hardwareFingerprint": record.get("hardwareFingerprint"),
            "suite": record.get("suite"),
            "workloadKind": workload,
            "scenarioContract": record.get("scenarioContract"),
            "client": record.get("client"),
            "reasoning": record.get("reasoning"),
            "targetKV": record.get("targetKV"),
            "samplingFingerprint": record.get("samplingFingerprint"),
            "contextMin": record.get("contextMin"),
            "contextMax": record.get("contextMax"),
            "outputMin": record.get("outputMin"),
            "outputMax": record.get("outputMax"),
            "samples": sample_contract,
        }
        signature = hashlib.sha256(json.dumps(
            contract, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        resource = result.get("resourceTelemetry")
        memory_delta: int | None = None
        baseline_headroom: float | None = None
        baseline_headroom_bytes: int | None = None
        minimum_headroom: float | None = None
        total_memory: int | None = None
        thermal_start: int | None = None
        thermal_worst: int | None = None
        thermal_label = "unavailable"
        if isinstance(resource, dict) and resource.get("version") in {1, 2}:
            physical = darwin_memory.telemetry_capacity_metrics(resource)
            thermal = resource.get("thermalWorstValue")
            start = resource.get("thermalStartValue")
            if physical is not None:
                memory_delta = physical["deltaBytes"]
                baseline_headroom = physical["baselinePercent"]
                minimum_headroom = physical["minimumPercent"]
                total_memory = physical["totalBytes"]
                baseline_headroom_bytes = physical["baselineBytes"]
            if (
                resource.get("thermalAvailable") is True
                and isinstance(thermal, int) and not isinstance(thermal, bool)
                and thermal in self.policy.thermal_state_labels
                and isinstance(start, int) and not isinstance(start, bool)
                and start in self.policy.thermal_state_labels
            ):
                thermal_start = start
                thermal_worst = thermal
                thermal_label = self.policy.thermal_state_labels[thermal]
        return {
            "signature": signature, "score": score, "metric": metric,
            "display": display, "higherIsBetter": higher_is_better,
            "qualityFingerprint": quality_fingerprint,
            "qualityCompletionTokens": quality_tokens,
            "observedSampleTokens": observed_sample_tokens,
            "firstTokenSeconds": round(statistics.median(first_token_seconds), 4) if len(first_token_seconds) == len(samples) else None,
            "decodeTokensPerSecond": generation_metrics.median_generation_tps(samples, str(record.get("backend") or "")),
            "peakPressureDeltaBytes": memory_delta,
            "memorySemanticsVersion": darwin_memory.MEMORY_SEMANTICS_VERSION if memory_delta is not None else None,
            "baselineHeadroomPercent": baseline_headroom,
            "baselineHeadroomBytes": baseline_headroom_bytes,
            "minimumHeadroomPercent": minimum_headroom,
            "totalMemoryBytes": total_memory,
            "thermalStartValue": thermal_start,
            "thermalStart": self.policy.thermal_state_labels.get(thermal_start, "unavailable"),
            "thermalWorstValue": thermal_worst,
            "thermalWorst": thermal_label,
            "lowPowerMode": resource.get("lowPowerMode") if isinstance(resource, dict) else None,
            "resourceCooldownStatus": (
                result.get("resourceCooldown", {}).get("status")
                if isinstance(result.get("resourceCooldown"), dict) else None
            ),
        }


    def benchmark_record_matches_selection_preference(self, 
        record: dict[str, Any], preference: str,
    ) -> bool:
        """Do not reuse a newly measured route for a goal it did not optimise.

        Records created before the selection contract was stored remain readable;
        new records are bound to the Calibration goal that chose their internal
        acceleration route and engine-owned settings.
        """
        measured = record.get("selectionPreference")
        # Early v5 standalone operator runs dropped enginePreference when building
        # the job, despite the fixed operator contract ranking generation TPS.
        # Interpret that known label error without rewriting saved measurements.
        # This is only a goal match; callers still require the full record verifier.
        if (measured == "fastest" and record.get("scope") == "local"
                and record.get("backend") == "mtplx" and not record.get("shootoutId")
                and record.get("kind") == "mtplx-long-context-operator-tuning"
                and record.get("suite") == self.policy.mtplx_long_context_64k_suite
                and record.get("selectionMetric") == "generation-tokens-per-second"
                and isinstance(record.get("mtplxOperatorSweep"), dict)
                and record["mtplxOperatorSweep"].get("version") == 5):
            measured = "throughput"
        return measured is None or measured == preference


    def verified_cross_engine_entries(self, 
        model: dict[str, Any], eligible_backends: list[str], evidence: dict[str, Any],
        preference: str | None = None,
    ) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for backend in eligible_backends:
            capability = model.get("backends", {}).get(backend, {})
            records = capability.get("localBenchmarks")
            candidates = [item for item in records if isinstance(item, dict)] if isinstance(records, list) else []
            latest = capability.get("localBenchmark")
            if isinstance(latest, dict) and latest not in candidates:
                candidates.append(latest)
            for record in candidates:
                if (
                    not self.route_qualification_record_is_fresh(record)
                    or not self.evidence.local_benchmark_record_verified(capability, record, evidence)
                    or (
                        preference is not None
                        and not self.benchmark_record_matches_selection_preference(
                            record, preference,
                        )
                    )
                ):
                    continue
                measurement = self.cross_engine_benchmark_measurement(record)
                if not measurement:
                    continue
                entries.append({
                    "backend": backend, "record": copy.deepcopy(record), **measurement,
                })
        return entries


    def _cross_engine_group_rank(self, 
        group: list[dict[str, Any]], client: str,
    ) -> tuple[int, int, str]:
        record = group[0]["record"]
        workload = str(record.get("workloadKind") or "throughput")
        agent_client = client in {"pi", "omp", "opencode", "codex"}
        workload_match = int((workload == "agentic") == agent_client)
        strength = {
            "quick": 1, "standard": 2, "thorough": 3, "agentic": 4,
            self.policy.mtplx_long_context_64k_suite: 5,
        }.get(
            str(record.get("suite") or ""), 0,
        )
        oldest_latest = min(str(item["record"].get("createdAt") or "") for item in group)
        return workload_match, strength, oldest_latest


    def rank_cross_engine_profile(self, 
        group: list[dict[str, Any]], preference: str,
    ) -> dict[str, Any]:
        """Rank one complete matrix using only profile-specific measured evidence."""
        if preference not in self.policy.engine_preference_labels:
            raise ValueError(
                "Choose Highest generation TPS, Fastest total, Fastest first response, "
                "Lowest memory use, or Best thermal stability."
            )
        speed_ranked = _speed_ranked_entries(group)
        if preference == "memory" and any(
            item.get("memorySemanticsVersion") != darwin_memory.MEMORY_SEMANTICS_VERSION
            for item in group
        ):
            return {
                "available": False,
                "missing": [str(item["backend"]) for item in group
                            if item.get("memorySemanticsVersion") != darwin_memory.MEMORY_SEMANTICS_VERSION],
                "preference": preference,
                "reason": "A physical-capacity comparison needs current native page measurements for every engine; historical pressure percentages cannot supply that proof.",
            }
        thermal_starts = [
            int(item["thermalStartValue"]) for item in group
            if isinstance(item.get("thermalStartValue"), int)
            and not isinstance(item.get("thermalStartValue"), bool)
            and int(item["thermalStartValue"]) in self.policy.thermal_state_labels
        ]
        if len(thermal_starts) == len(group) and len(set(thermal_starts)) != 1:
            starts = ", ".join(
                f"{self.policy.backend_labels[item['backend']]} {item.get('thermalStart', 'unavailable')}"
                for item in group
            )
            return {
                "available": False, "missing": [], "preference": preference,
                "conditionMismatch": True,
                "reason": (
                    "The engines did not start from the same public macOS thermal state "
                    f"({starts}), so the measured {self.policy.engine_preference_labels[preference].lower()} winner would be biased. "
                    "Run a fresh shootout after the Mac settles."
                ),
            }
        low_power_states = [item.get("lowPowerMode") for item in group if isinstance(item.get("lowPowerMode"), bool)]
        if len(low_power_states) == len(group) and len(set(low_power_states)) != 1:
            return {
                "available": False, "missing": [], "preference": preference,
                "conditionMismatch": True,
                "reason": (
                    "Low Power Mode changed during the Engine Shootout, so its routes are not comparable. "
                    "Choose one power mode and run the shootout again."
                ),
            }
        baseline_bytes = [
            int(item["baselineHeadroomBytes"]) for item in group
            if isinstance(item.get("baselineHeadroomBytes"), int)
            and not isinstance(item.get("baselineHeadroomBytes"), bool)
            and int(item["baselineHeadroomBytes"]) >= 0
        ]
        cooldown_statuses = [str(item.get("resourceCooldownStatus") or "") for item in group]
        shootout_ids = {
            str(item.get("record", {}).get("shootoutId") or "")
            for item in group if isinstance(item.get("record"), dict)
        }
        shared_gate_passed = bool(
            len(cooldown_statuses) == len(group)
            and all(
                status in {"ready", "reference-ready", "condition-improved"}
                for status in cooldown_statuses
            )
            and len(shootout_ids) == 1 and "" not in shootout_ids
        )
        if (
            len(baseline_bytes) == len(group)
            and max(baseline_bytes) - min(baseline_bytes) > self.policy.benchmark_memory_meaningful_bytes
            and not shared_gate_passed
        ):
            starts = ", ".join(
                f"{self.policy.backend_labels[item['backend']]} {float(item.get('baselineHeadroomPercent') or 0):.0f}%"
                for item in group
            )
            return {
                "available": False, "missing": [], "preference": preference,
                "conditionMismatch": True,
                "reason": (
                    "The routes began more than "
                    f"{self.live.display_size(self.policy.benchmark_memory_meaningful_bytes)} apart in unified-memory headroom "
                    f"({starts}), so the measured {self.policy.engine_preference_labels[preference].lower()} winner would be biased. "
                    "Run a fresh shootout after memory pressure settles."
                ),
            }
        missing: list[str] = []
        metric = ""
        displays: dict[str, str] = {}
        leading_backends: list[str] = []
        if preference == "throughput":
            missing = [
                str(item["backend"]) for item in group
                if not isinstance(item.get("decodeTokensPerSecond"), (int, float))
                or isinstance(item.get("decodeTokensPerSecond"), bool)
                or not math.isfinite(float(item["decodeTokensPerSecond"]))
                or float(item["decodeTokensPerSecond"]) <= 0
            ]
            if missing:
                return {"available": False, "missing": missing, "preference": preference}
            ranked = sorted(
                group, key=lambda item: float(item["decodeTokensPerSecond"]), reverse=True,
            )
            winner, runner_up = ranked[0], ranked[1]
            lead = float(winner["decodeTokensPerSecond"]) / max(
                float(runner_up["decodeTokensPerSecond"]), 0.000_001,
            )
            trusted = lead >= self.policy.benchmark_minimum_speedup
            leading_backends = [
                str(item["backend"]) for item in ranked
                if float(winner["decodeTokensPerSecond"]) / max(
                    float(item["decodeTokensPerSecond"]), 0.000_001,
                ) < self.policy.benchmark_minimum_speedup
            ]
            metric = "median-decode-tokens-per-second"
            displays = {
                item["backend"]: f"{float(item['decodeTokensPerSecond']):.1f} tok/s generation"
                for item in ranked
            }
            winner_reason = (
                f"{self.policy.backend_labels[winner['backend']]} generated tokens {(lead - 1) * 100:.1f}% faster "
                "than the next engine's correctness-verified safe route."
            )
            tie_reason = (
                f"{self.policy.backend_labels[winner['backend']]} led generation TPS by only {(lead - 1) * 100:.1f}%, "
                f"below the {int((self.policy.benchmark_minimum_speedup - 1) * 100)}% switch threshold."
            )
        elif preference == "fastest":
            ranked = speed_ranked
            winner, runner_up = ranked[0], ranked[1]
            lead = _speed_lead(winner, runner_up)
            trusted = lead >= self.policy.benchmark_minimum_speedup
            leading_backends = [
                str(item["backend"]) for item in ranked
                if _speed_lead(winner, item) < self.policy.benchmark_minimum_speedup
            ]
            metric = str(winner["metric"])
            displays = {item["backend"]: str(item["display"]) for item in ranked}
            winner_reason = (
                f"{self.policy.backend_labels[winner['backend']]} led total workload performance by {(lead - 1) * 100:.1f}% over the next engine."
            )
            tie_reason = (
                f"{self.policy.backend_labels[winner['backend']]} led by only {(lead - 1) * 100:.1f}%, below the "
                f"{int((self.policy.benchmark_minimum_speedup - 1) * 100)}% switch threshold."
            )
        elif preference == "responsive":
            missing = [
                str(item["backend"]) for item in group
                if not isinstance(item.get("firstTokenSeconds"), (int, float))
                or isinstance(item.get("firstTokenSeconds"), bool)
                or float(item["firstTokenSeconds"]) <= 0
            ]
            if missing:
                return {"available": False, "missing": missing, "preference": preference}
            ranked = sorted(group, key=lambda item: float(item["firstTokenSeconds"]))
            winner, runner_up = ranked[0], ranked[1]
            lead = float(runner_up["firstTokenSeconds"]) / max(float(winner["firstTokenSeconds"]), 0.000_001)
            trusted = lead >= self.policy.benchmark_minimum_speedup
            leading_backends = [
                str(item["backend"]) for item in ranked
                if float(item["firstTokenSeconds"]) / max(
                    float(winner["firstTokenSeconds"]), 0.000_001,
                ) < self.policy.benchmark_minimum_speedup
            ]
            metric = "median-first-token-seconds"
            displays = {
                item["backend"]: f"{float(item['firstTokenSeconds']):.2f}s median first token"
                for item in ranked
            }
            winner_reason = (
                f"{self.policy.backend_labels[winner['backend']]} reached the first output {(lead - 1) * 100:.1f}% sooner than the next engine."
            )
            tie_reason = (
                f"{self.policy.backend_labels[winner['backend']]} reached first output only {(lead - 1) * 100:.1f}% sooner, below the "
                f"{int((self.policy.benchmark_minimum_speedup - 1) * 100)}% switch threshold."
            )
        elif preference == "memory":
            missing = [
                str(item["backend"]) for item in group
                if not isinstance(item.get("peakPressureDeltaBytes"), int)
                or isinstance(item.get("peakPressureDeltaBytes"), bool)
                or int(item["peakPressureDeltaBytes"]) < 0
            ]
            if missing:
                return {"available": False, "missing": missing, "preference": preference}
            ranked = sorted(
                group,
                key=lambda item: (
                    int(item["peakPressureDeltaBytes"]),
                    -float(item.get("minimumHeadroomPercent") or 0),
                ),
            )
            winner, runner_up = ranked[0], ranked[1]
            saved = int(runner_up["peakPressureDeltaBytes"]) - int(winner["peakPressureDeltaBytes"])
            trusted = saved >= self.policy.benchmark_memory_meaningful_bytes
            leading_backends = [
                str(item["backend"]) for item in ranked
                if int(item["peakPressureDeltaBytes"]) - int(winner["peakPressureDeltaBytes"])
                < self.policy.benchmark_memory_meaningful_bytes
            ]
            metric = "peak-system-memory-pressure-delta-bytes"
            displays = {
                item["backend"]: (
                    f"{self.live.display_size(int(item['peakPressureDeltaBytes']))} peak pressure delta · "
                    f"{float(item.get('minimumHeadroomPercent') or 0):.0f}% minimum headroom"
                )
                for item in ranked
            }
            winner_reason = (
                f"{self.policy.backend_labels[winner['backend']]} added {self.live.display_size(saved)} less peak unified-memory pressure than the next engine."
            )
            tie_reason = (
                f"The smallest measured memory-pressure difference was {self.live.display_size(max(0, saved))}, below the "
                f"{self.live.display_size(self.policy.benchmark_memory_meaningful_bytes)} switch threshold."
            )
        else:
            missing = [
                str(item["backend"]) for item in group
                if (
                    not isinstance(item.get("thermalStartValue"), int)
                    or isinstance(item.get("thermalStartValue"), bool)
                    or int(item["thermalStartValue"]) not in self.policy.thermal_state_labels
                    or not isinstance(item.get("thermalWorstValue"), int)
                    or isinstance(item.get("thermalWorstValue"), bool)
                    or int(item["thermalWorstValue"]) not in self.policy.thermal_state_labels
                )
            ]
            if missing:
                return {"available": False, "missing": missing, "preference": preference}
            starting_states = {int(item["thermalStartValue"]) for item in group}
            if len(starting_states) != 1:
                starts = ", ".join(
                    f"{self.policy.backend_labels[item['backend']]} {self.policy.thermal_state_labels[int(item['thermalStartValue'])]}"
                    for item in group
                )
                return {
                    "available": False, "missing": [], "preference": preference,
                    "conditionMismatch": True,
                    "reason": (
                        "The engines did not start from the same public macOS thermal state "
                        f"({starts}), so a thermal winner would be biased. Run a fresh shootout after the Mac settles."
                    ),
                }
            speed_position = {item["backend"]: index for index, item in enumerate(speed_ranked)}
            ranked = sorted(
                group,
                key=lambda item: (int(item["thermalWorstValue"]), speed_position[item["backend"]]),
            )
            winner, runner_up = ranked[0], ranked[1]
            winner_thermal = int(winner["thermalWorstValue"])
            runner_thermal = int(runner_up["thermalWorstValue"])
            lead = _speed_lead(winner, runner_up)
            thermal_advantage = runner_thermal > winner_thermal
            trusted = thermal_advantage or lead >= self.policy.benchmark_minimum_speedup
            leading_backends = [
                str(item["backend"]) for item in ranked
                if int(item["thermalWorstValue"]) == winner_thermal
                and _speed_lead(winner, item) < self.policy.benchmark_minimum_speedup
            ]
            metric = "worst-system-thermal-state-then-total-performance"
            displays = {
                item["backend"]: f"{self.policy.thermal_state_labels[int(item['thermalWorstValue'])]} worst state · {item['display']}"
                for item in ranked
            }
            if thermal_advantage:
                winner_reason = (
                    f"{self.policy.backend_labels[winner['backend']]} stayed {self.policy.thermal_state_labels[winner_thermal]} while the next engine reached "
                    f"{self.policy.thermal_state_labels[runner_thermal]}."
                )
                tie_reason = ""
            else:
                winner_reason = (
                    f"The leading engines shared the same {self.policy.thermal_state_labels[winner_thermal]} thermal state; "
                    f"{self.policy.backend_labels[winner['backend']]} was {(lead - 1) * 100:.1f}% faster."
                )
                tie_reason = (
                    f"The leading engines shared the same {self.policy.thermal_state_labels[winner_thermal]} thermal state and their "
                    f"performance differed by only {(lead - 1) * 100:.1f}%."
                )
        return {
            "available": True, "preference": preference,
            "label": self.policy.engine_preference_labels[preference],
            "ranked": ranked, "winner": winner, "runnerUp": runner_up,
            "trusted": trusted, "metric": metric, "displays": displays,
            "winnerReason": winner_reason, "tieReason": tie_reason,
            "leadingBackends": leading_backends,
        }


    def _optimizer_with_forced_record(self, 
        payload: dict[str, Any], models: list[dict[str, Any]], model: dict[str, Any],
        backend: str, record: dict[str, Any], evidence: dict[str, Any],
    ) -> dict[str, Any]:
        target_payload = copy.deepcopy(payload)
        target_payload["backend"] = backend
        source_backend = str(payload.get("backend") or "")
        source_options = copy.deepcopy(
            target_payload.get("options")
            if isinstance(target_payload.get("options"), dict) else {}
        )
        # Acceleration is owned by the target engine. A cross-engine decision can
        # start from an explicit route such as oMLX DFlash or MTPLX MTP, neither of
        # which is a valid input for every peer. Validate the target from its
        # neutral route, then let the verified record choose its measured route.
        target_options = copy.deepcopy(source_options)
        if source_backend != backend:
            target_options["acceleration"] = (
                "auto" if backend in {"omlx", "lmstudio", "mtplx"} else "off"
            )
        target_payload["options"] = target_options
        # The caller has already resolved and validated the exact record. Avoid
        # recursively treating an engine-shootout binding as a current-route receipt.
        target_payload.pop("evidenceBinding", None)
        # Run the normal validator first so an engine switch never bypasses its
        # client, reasoning, model, limit, or installation checks.
        validated = self.optimal_request(target_payload, models)
        capability = copy.deepcopy(model["backends"][backend])
        if backend == "omlx" and self.live.is_qwen4_exp_record(model):
            capability["qwen4Ple"] = copy.deepcopy(model.get("qwen4Ple"))
        capability["localBenchmark"] = copy.deepcopy(record)
        capability["localBenchmarks"] = [copy.deepcopy(record)]
        capability["preferredAccelerationSource"] = "local-benchmark"
        capability["preferredAcceleration"] = {
            "ar": "off", "mtp": "mtp", "dflash2": "dflash",
        }.get(str(record.get("winner") or ""), "off")
        if record.get("winner") == "dflash2":
            capability["dflashPreferred"] = True
            capability["dflashBenchmarkVerified"] = True
            capability["dflashBenchmark"] = copy.deepcopy(record)
        # On a same-engine reuse, compare the measured result with the real visible
        # controls so an already-applied route remains a no-op. On an engine switch,
        # compare with the neutral target route because the source engine's route
        # vocabulary is not meaningful in the destination engine.
        options = source_options if source_backend == backend else target_options
        result = self.fastest_safe_options(backend, capability, options, evidence)
        result.update({
            "backend": backend, "modelId": validated["modelId"],
            "model": validated.get("model"),
        })
        return result


    def engine_selection_next_action(self, 
        action: str, preference: str, backend: str, client: str, reason: str,
        missing_engines: list[dict[str, Any]] | None = None,
        recommended_suite: str | None = None,
    ) -> dict[str, Any]:
        """Return a stable UI handoff without performing the suggested action."""
        if action not in {"apply", "keep-current", "calibrate"}:
            raise ValueError("Unsupported engine-selection next action.")
        labels = {
            "apply": f"Apply {self.policy.backend_labels[backend]}",
            "keep-current": f"Keep {self.policy.backend_labels[backend]}",
            "calibrate": "Test engines + settings",
        }
        return {
            "id": action,
            "label": labels[action],
            "preference": preference,
            "preferenceLabel": self.policy.engine_preference_labels[preference],
            "backend": backend,
            "backendLabel": self.policy.backend_labels[backend],
            "reason": reason,
            "requiresCalibration": action == "calibrate",
            "requiresConsent": False,
            "requiresReview": action == "calibrate",
            "recommendedSuite": recommended_suite or (
                "standard" if client == "chat" else "agentic"
            ),
            "missingEngines": copy.deepcopy(missing_engines or []),
        }


    def benchmark_public_mode_label(self, backend: str, mode: Any) -> str:
        """Name an internal measurement lane without mislabelling fixed routes."""
        route = str(mode or "ar")
        if backend == "uzu" and route == "ar":
            return "Fixed DFlash + Weaver"
        return self.live.mode_label(route)


    def benchmark_mode_summary(self, 
        model: dict[str, Any], backend: str, modes: list[Any] | tuple[Any, ...],
        engine_settings: dict[str, Any] | None = None, *, kv: str = "off",
    ) -> str:
        """Explain which verified routes an exact model artifact can actually compare."""
        capability = model.get("backends", {}).get(backend, {})
        tested = [str(mode) for mode in modes if str(mode) in {"ar", "mtp", "dflash2"}]
        if backend == "uzu":
            return (
                "Measures Uzu's one fixed DFlash + Weaver route with its bundled draft and prefix cache. "
                "The internal speculative controls stay runtime-owned so calibration measures the real published path."
            )
        if backend in self.policy.ssd_streaming_backends:
            return (
                "Runs exact native expert routing through SSD streaming. The fresh-process first turn, "
                "shared-prefix turn, tool ingestion, and warm follow-up are measured separately; "
                "the OS file cache is observed, not forcibly purged."
            )
        labels = [self.live.mode_label(mode) for mode in tested]
        accelerators = labels[1:] if tested[:1] == ["ar"] else [
            label for mode, label in zip(tested, labels) if mode != "ar"
        ]
        dflash_exclusion = ""
        if backend == "omlx" and capability.get("dflash") is True and "dflash2" not in tested:
            if kv != "off":
                dflash_exclusion = f"DFlash affine KV and ordinary oMLX TurboQuant are not an equivalent {kv.upper()} comparison."
            elif isinstance(engine_settings, dict) and engine_settings.get("anePrefill") == "tuned":
                dflash_exclusion = self.policy.omlx_dflash_tuned_ane_exclusion_detail
        if accelerators:
            detail = (
                f"Tests {' + '.join(labels)} for this selected model artifact; "
                + (
                    "the fastest correctness-verified tested route wins."
                    if dflash_exclusion else
                    "the fastest correctness-verified route wins."
                )
            )
            return f"{detail} {dflash_exclusion}".strip()
        reason = str(capability.get("mtpReason") or "No verified matching acceleration weights were found.")
        if backend == "omlx" and capability.get("dflash") is not True:
            dflash_reason = str(capability.get("dflashReason") or "")
            if dflash_reason and dflash_reason != reason:
                reason = f"{reason} {dflash_reason}"
        if reason and reason[-1] not in ".!?":
            reason += "."
        return f"AR only for this selected model artifact. {reason} {dflash_exclusion}".strip()


    def benchmark_acceleration_reason(self, 
        model: dict[str, Any], backend: str, modes: list[Any] | tuple[Any, ...],
        *, kv: str = "off",
    ) -> str:
        """Return a compact, truthful reason when an engine can measure only AR."""
        tested = {str(mode) for mode in modes}
        if backend == "uzu":
            return "Runtime-managed DFlash + Weaver with bundled draft and prefix cache"
        if tested.intersection({"mtp", "dflash2"}):
            return ""
        capability = model.get("backends", {}).get(backend, {})
        mtp_reason = str(capability.get("mtpReason") or "").strip().rstrip(".")
        if backend == "lmstudio" and "sidecar" in mtp_reason.lower():
            return "This model has no MTP sidecar"
        if backend == "mtplx" and "mtp" in mtp_reason.lower():
            return "This model has no verified MTPLX MTP weights"
        if backend == "omlx":
            if capability.get("dflash") is True and kv != "off":
                return f"DFlash excluded to preserve {kv.upper()} KV"
            return "This model has no verified oMLX accelerator"
        if backend == "slotstream":
            return mtp_reason or "The pinned MTP head is not installed"
        if backend == "splash":
            # Splash always decodes with its packaged DFlash 2 draft; there is no
            # separate AR-only mode to caveat.
            return ""
        if backend in self.policy.ssd_streaming_backends:
            return "Exact SSD streaming uses native expert routing; speculative decoding is excluded"
        return mtp_reason or "This model has no verified accelerator"


    def benchmark_engine_settings_label(self, backend: str, settings: Any) -> str:
        """Describe the fixed engine-owned controls used beside each acceleration route."""
        values = settings if isinstance(settings, dict) else {}
        if backend == "omlx":
            burst = str(values.get("burst") or "balanced")
            parts = [f"{burst.replace('-', ' ').title()} burst"]
            if values.get("pleStorage") == "mmap":
                parts.insert(0, "PLE mmap")
                parts.append(
                    "45 GiB high-memory guard"
                    if values.get("memoryGuard") == "high"
                    else "balanced memory guard"
                )
            if values.get("anePrefill") == "tuned":
                parts.append("measured ANE prefill")
            return " · ".join(parts)
        if backend == "lmstudio":
            gpu = "Full GPU" if values.get("gpu", "max") == "max" else "CPU only"
            lanes = max(1, self.live.safe_int(values.get("parallel"), 1, 1, 16))
            return f"{gpu} · {lanes} request lane{'s' if lanes != 1 else ''}"
        if backend == "mtplx":
            profile = str(values.get("profile") or "sustained").replace("-", " ").title()
            cooling = {
                "default": "system cooling", "smart": "automatic cooling", "max": "maximum fans",
            }.get(str(values.get("fan") or "smart"), "automatic cooling")
            return f"{profile} profile · {cooling}"
        if backend == "swiftlm":
            prefill = self.live.safe_int(values.get("prefillSize"), 512, 128, 2_048)
            top_k = max(0, self.live.safe_int(values.get("nativeExpertTopK"), 0, 0, 4_096))
            routing = f"native top-{top_k}" if top_k else "native expert routing"
            return f"SSD expert streaming · {prefill:,} prefill · {routing}"
        if backend == "mference":
            cache = "prompt cache" if str(values.get("promptCacheMode") or "on") == "on" else "no prompt cache"
            queue = self.live.safe_int(values.get("queueLimit"), 4, 1, 32)
            return f"Verified .gturbo streaming · {cache} · queue {queue}"
        if backend == "slotstream":
            return f"Full 512-expert SSD stream · {values.get('memoryGB', slotstream_runtime.DEFAULT_MEMORY_GB)} GB process budget · prefix cache"
        if backend == "kolibri":
            return (f"Full Q6 · SSD expert cache · "
                    f"{values.get('memoryGB', kolibri_runtime.DEFAULT_MEMORY_GB)} GB process ceiling · "
                    f"{values.get('prefillSize', kolibri_runtime.DEFAULT_PREFILL)} token prefill · "
                    f"{values.get('promptCacheGB', kolibri_runtime.DEFAULT_PROMPT_CACHE_GB)} GiB prompt cache")
        if backend == "splash":
            return "Selected target quantization · DFlash2 draft · engine-owned memory plan"
        if backend == "whallm":
            return "Full 512-expert SSD stream · Whallm-owned MXFP4"
        if backend == "uzu":
            return "Bundled DFlash draft · Weaver tree verification · prefix cache"
        return ""


    def benchmark_route_settings_label(self, 
        backend: str, mode: Any, settings: Any,
    ) -> str:
        """Describe the exact winning accelerator controls without exposing raw JSON."""
        route = str(mode or "ar")
        values = settings if isinstance(settings, dict) else {}
        if backend == "uzu" and route == "ar":
            return "Fixed DFlash + Weaver"
        if route == "mtp":
            depth = values.get("depth")
            if isinstance(depth, int) and not isinstance(depth, bool):
                operator_route = values.get("mtplxOperatorRoute")
                if backend == "mtplx" and operator_route == self.policy.mtplx_long_context_2111_route:
                    return f"MTP D{depth} · 2.11 long-context"
                if backend == "mtplx" and operator_route == self.policy.mtplx_long_context_default_route:
                    return f"MTP D{depth} · 2.11 default"
                if backend == "lmstudio":
                    minimum = values.get("mtpMinTokens")
                    cutoff = values.get("mtpMinContinueProbability")
                    if (
                        isinstance(minimum, int) and not isinstance(minimum, bool)
                        and isinstance(cutoff, (int, float)) and not isinstance(cutoff, bool)
                    ):
                        return f"MTP D{depth} · min {minimum} · cutoff {float(cutoff):.2f}"
                return f"MTP depth D{depth}"
        if route == "dflash2":
            block = values.get("blockSize")
            verify = values.get("verifyMode")
            quant = values.get("draftQuant")
            if isinstance(block, int) and not isinstance(block, bool):
                extras = [str(value) for value in (verify, quant) if value]
                return f"DFlash block {block}" + (f" · {' · '.join(extras)}" if extras else "")
        return "AR"


    def accelerated_model_alternatives(self, 
        selected: dict[str, Any], backend: str, models: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Suggest installed accelerated siblings without ever substituting one silently."""
        family = model_acceleration_family(selected)
        if not family:
            return []
        selected_id = str(selected.get("id") or "")
        architecture = str(selected.get("architecture") or "")
        model_type = str(selected.get("modelType") or "")
        candidates: list[dict[str, Any]] = []
        for candidate in models:
            capability = candidate.get("backends", {}).get(backend, {})
            if (
                str(candidate.get("id") or "") == selected_id
                or candidate.get("ready") is not True
                or capability.get("runnable") is not True
                or model_acceleration_family(candidate) != family
                or str(candidate.get("architecture") or "") != architecture
                or str(candidate.get("modelType") or "") != model_type
            ):
                continue
            modes = []
            if capability.get("mtp") is True:
                modes.append("MTP")
            if backend == "omlx" and capability.get("dflash") is True:
                modes.append("DFlash 2")
            if not modes:
                continue
            candidates.append({
                "id": str(candidate.get("id") or ""),
                "name": str(candidate.get("name") or "Installed accelerated model"),
                "quantization": str(candidate.get("quantization") or "Unknown"),
                "sizeLabel": str(candidate.get("sizeLabel") or ""),
                "modes": modes,
                "differentArtifact": True,
            })
        candidates.sort(key=lambda item: (
            0 if "optimized-speed" in item["name"].lower() else 1,
            item["name"].lower(),
        ))
        return candidates[:2]


    def qwen_flash_next_model_alternatives(self, 
        selected: dict[str, Any], visible_request: dict[str, Any],
        models: list[dict[str, Any]], *,
        resource_snapshot: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Offer an explicit smaller-model DFlash route without changing selection."""
        if not self.live.is_qwen4_exp_record(selected):
            return []
        identity = " ".join(str(selected.get(key) or "") for key in (
            "name", "path", "architecture", "modelType",
        )).casefold()
        ssd_profile = (
            selected.get("ssdStreaming")
            if isinstance(selected.get("ssdStreaming"), dict) else {}
        )
        if (
            ssd_profile.get("qwen38FlashNext") is not True
            and not re.search(r"qwen3[._-]?8.*flash[._-]?next", identity)
        ):
            return []

        client = str(visible_request.get("client") or "")
        reasoning = str(visible_request.get("reasoning") or "auto")
        visible_options = (
            copy.deepcopy(visible_request.get("options"))
            if isinstance(visible_request.get("options"), dict) else {}
        )
        kv = str(visible_options.get("kv") or "off")
        chat = (
            copy.deepcopy(visible_request.get("chat"))
            if isinstance(visible_request.get("chat"), dict) else {}
        )
        snapshot = (
            copy.deepcopy(resource_snapshot)
            if isinstance(resource_snapshot, dict) else self.live.apple_resource_snapshot()
        )
        resource = self.live.public_session_resource(snapshot)
        candidates: list[dict[str, Any]] = []

        for source in models:
            candidate = source if isinstance(source, dict) else {}
            candidate_id = str(candidate.get("id") or "")
            candidate_identity = " ".join(str(candidate.get(key) or "") for key in (
                "name", "path", "architecture", "modelType",
            )).casefold()
            candidate_backends = (
                candidate.get("backends")
                if isinstance(candidate.get("backends"), dict) else {}
            )
            capability = candidate_backends.get("omlx", {})
            if not isinstance(capability, dict):
                continue
            readiness = (
                capability.get("dflashReadiness")
                if isinstance(capability.get("dflashReadiness"), dict) else {}
            )
            exact_pair = bool(
                candidate_id
                and candidate_id != str(selected.get("id") or "")
                and re.search(r"qwen3[._-]?8[^/]*27b", candidate_identity)
                and "flash-next" not in candidate_identity
                and "flash_next" not in candidate_identity
                and "ornith" not in candidate_identity
                and candidate.get("ready") is True
                and capability.get("runnable") is True
                and capability.get("dflash") is True
                and capability.get("dflashVersion") == "2"
                and capability.get("dflashDraftPath")
                and capability.get("dflashPairFingerprint")
                and capability.get("dflashRuntimeVersion")
                and readiness.get("runtimeRecommended") is True
                and readiness.get("targetCompatible") is not False
                and readiness.get("draftComplete") is not False
            )
            if not exact_pair:
                continue
            # The scan is only a snapshot. Revalidate the target, draft tensors,
            # runtime identity, and pair fingerprint before advertising an explicit
            # different-model route from a freshly opened calibration plan.
            if not self.live.dflash2_capability_valid(candidate, capability):
                continue
            allowed, _reason = self.optimizer_backend_eligibility(
                candidate, "omlx", client, reasoning, kv, chat,
            )
            if not allowed:
                continue

            candidate_models = copy.deepcopy(models)
            candidate_copy = next(
                item for item in candidate_models
                if str(item.get("id") or "") == candidate_id
            )
            candidate_capability = candidate_copy["backends"]["omlx"]
            draft_size = candidate_capability.get("dflashDraftSize")
            if (
                not isinstance(draft_size, int) or isinstance(draft_size, bool)
                or draft_size <= 0
            ):
                candidate_capability["dflashDraftSize"] = self.policy.dflash2_draft_bytes
            block_size = capability.get("dflashBlockSize")
            if not isinstance(block_size, int) or isinstance(block_size, bool) or block_size < 1:
                block_size = 1
            candidate_options = copy.deepcopy(visible_options)
            candidate_options.update({
                "acceleration": "dflash",
                "depth": block_size,
                "anePrefill": "off",
                "memoryGuard": "balanced",
            })
            candidate_payload = copy.deepcopy(visible_request)
            candidate_payload.update({
                "backend": "omlx",
                "modelId": candidate_id,
                "options": candidate_options,
            })
            try:
                candidate_request = self.contracts.validated_launch_profile_request(
                    candidate_payload, candidate_models,
                )
                admission = self.live.session_memory_admission(
                    candidate_request, candidate_models, resource,
                    {"phase": "idle", "message": ""}, {"active": False},
                )
            except (KeyError, StopIteration, TypeError, ValueError):
                continue
            if (
                admission.get("launchable") is not True
                or admission.get("decision") != "ready"
                or admission.get("requiresAcknowledgement") is not False
            ):
                continue
            estimate = admission.get("estimate") if isinstance(admission.get("estimate"), dict) else {}
            required = estimate.get("requiredHeadroomBytes")
            total = resource.get("totalMemoryBytes")
            if (
                isinstance(required, int) and not isinstance(required, bool)
                and isinstance(total, int) and not isinstance(total, bool)
                and total > 0 and required > total
            ):
                continue

            exact_evidence = self.optimizer_evidence(
                candidate, int(candidate_request["context"]), int(candidate_request["output"]),
                client, reasoning, kv,
                candidate_request.get("chat")
                if isinstance(candidate_request.get("chat"), dict) else None,
                self.contracts.validated_sampling_contract(
                    candidate, candidate_request, client,
                    candidate_request.get("chat")
                    if isinstance(candidate_request.get("chat"), dict) else None,
                ),
            )
            self.add_benchmark_engine_evidence(
                exact_evidence, candidate, candidate_request["options"], ["omlx"],
            )
            local = self.evidence.verified_local_benchmark(capability, exact_evidence)
            evidence_capability = capability
            if local is None or local.get("winner") != "dflash2":
                evidence_capability = copy.deepcopy(capability)
                evidence_capability["localBenchmark"] = None
                evidence_capability["localBenchmarks"] = []
            performance = self.evidence.route_performance_evidence(
                candidate, "omlx", evidence_capability, exact_evidence,
            )
            host_support = self.contracts.route_host_support(
                candidate, "omlx", capability,
                runtime_installed=True, artifact_compatible=True,
            )
            if isinstance(total, int) and not isinstance(total, bool) and total > 0:
                host_support["hostMemoryBytes"] = total
            capacity = {
                key: copy.deepcopy(admission.get(key))
                for key in (
                    "decision", "label", "detail", "launchable",
                    "requiresAcknowledgement", "projectedHeadroomBytes",
                )
            }
            capacity["estimate"] = copy.deepcopy(estimate)
            capacity["sizeLabel"] = str(candidate.get("sizeLabel") or "")
            capacity["quantization"] = str(candidate.get("quantization") or "Unknown")
            candidates.append({
                "kind": "explicit-different-model",
                "label": "Fast 48 GB candidate",
                "modelId": candidate_id,
                "modelName": str(candidate.get("name") or candidate_id),
                "name": str(candidate.get("name") or candidate_id),
                "backend": "omlx",
                "backendLabel": self.policy.backend_labels["omlx"],
                "modes": ["DFlash 2"],
                "quantization": str(candidate.get("quantization") or "Unknown"),
                "sizeLabel": str(candidate.get("sizeLabel") or ""),
                "differentArtifact": True,
                "differentModel": True,
                "differentArchitecture": True,
                "intelligenceContractChanged": True,
                "requiresExplicitSelection": True,
                "automaticEligible": False,
                "performanceEvidence": performance,
                "hostSupport": host_support,
                "preservedContract": {
                    "client": client,
                    "context": int(candidate_request["context"]),
                    "output": int(candidate_request["output"]),
                    "reasoning": reasoning,
                    "kv": kv,
                    "chat": copy.deepcopy(candidate_request.get("chat") or {}),
                },
                "capacity": capacity,
            })

        candidates.sort(key=lambda item: (
            0 if item["performanceEvidence"]["tier"] == "verified-this-mac" else 1,
            0 if "optimized-speed" in item["modelName"].casefold() else 1,
            int(item["capacity"].get("estimate", {}).get("requiredHeadroomBytes") or 2**63),
            item["modelName"].casefold(),
        ))
        return candidates[:1]


    def best_engine_request(self, payload: dict[str, Any], models: list[dict[str, Any]]) -> dict[str, Any]:
        """Choose an engine only when a complete, like-for-like local matrix proves it."""
        binding = self.validated_optimizer_evidence_binding(payload)
        if binding is not None and binding["scope"] != "engine":
            raise ValueError("A saved route result cannot be applied as an engine comparison.")
        base_payload = copy.deepcopy(payload)
        base_payload.pop("evidenceBinding", None)
        current = self.optimal_request(base_payload, models)
        preference = str(payload.get("enginePreference") or "throughput")
        if preference not in self.policy.engine_preference_labels:
            raise ValueError("Choose a supported measured engine preference.")
        if binding is not None and binding["preference"] != preference:
            raise ValueError(
                "That saved engine result used a different decision goal. Refresh it before applying."
            )
        current_backend = str(current["backend"])
        if self.live.dflash_quantized_fallback(current_backend, base_payload.get("options") or {}):
            if binding is not None:
                raise ValueError(self.policy.dflash_kv_comparison_reason)
            current.update({
                "engineChanged": False, "engineEvidenceTier": "manual-route",
                "engineEvidenceLabel": "Manual DFlash route preserved",
                "comparedEngines": [], "qualifiedRoutes": [], "missingEngines": [],
                "engineRationale": [self.policy.dflash_kv_comparison_reason],
                "enginePreference": preference,
                "engineNextAction": self.engine_selection_next_action(
                    "keep-current", preference, current_backend,
                    str(payload.get("client") or ""), self.policy.dflash_kv_comparison_reason,
                ),
            })
            return current
        model_id = str(current["modelId"])
        model = next(item for item in models if item.get("id") == model_id)
        client = str(payload.get("client") or "")
        reasoning = str(payload.get("reasoning") or "auto")
        options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
        kv = str(options.get("kv") or "off")
        context, output = self.contracts.validated_limits(model, payload)
        chat = self.contracts.validated_chat_settings(model, payload, client)
        sampling_contract = self.contracts.validated_sampling_contract(model, payload, client, chat)
        assert sampling_contract is not None
        evidence = self.optimizer_evidence(
            model, context, output, client, reasoning, kv, chat, sampling_contract,
        )

        if current_backend == "uzu" and client == "pi" and binding is None:
            capacity = self.evidence.uzu_qualified_session_record({
                **payload, "context": context, "output": output, "reasoning": reasoning,
                "options": options, "chat": chat,
            }, model)
            if capacity is not None:
                detail = (
                    "Keep the fixed Uzu DFlash + Weaver route. Its exact context capacity is qualified "
                    "and the pinned Pi transport is verified; no Pi speed ranking is claimed."
                )
                current.update({
                    "engineChanged": False, "engineEvidenceTier": "local-capacity-only",
                    "engineEvidenceLabel": "Pi ready · model capacity qualified",
                    "comparedEngines": [], "qualifiedRoutes": [], "missingEngines": [],
                    "engineRationale": [detail], "enginePreference": preference,
                    "engineNextAction": self.engine_selection_next_action(
                        "keep-current", preference, current_backend, client, detail,
                    ),
                    "evidenceTier": "local-capacity-only",
                    "evidenceLabel": "Pi ready · model capacity qualified",
                })
                return current

        eligible: list[str] = []
        excluded: list[dict[str, str]] = []
        ssd_profile = model.get("ssdStreaming") if isinstance(model.get("ssdStreaming"), dict) else {}
        selected_spec = self.contracts.route_qualification_spec(model, current_backend, context)
        candidate_backends = (
            (current_backend,) if selected_spec is not None else
            self.live.ssd_profile_candidate_backends(ssd_profile)
            if ssd_profile.get("recommended") is True else tuple(self.policy.engine_adapters)
        )
        for backend in candidate_backends:
            allowed, reason = self.optimizer_backend_eligibility(
                model, backend, client, reasoning, kv, chat,
            )
            if allowed:
                eligible.append(backend)
            else:
                excluded.append({"backend": backend, "label": self.policy.backend_labels[backend], "reason": reason})

        self.add_benchmark_engine_evidence(evidence, model, options, eligible)
        if binding is not None:
            # A bound Apply action names the exact completed records. Let those
            # records supply only their engine-owned controls before the normal
            # verifier checks the complete shared request contract. This prevents a
            # tuned Turbo result being discarded merely because the pre-calibration
            # UI still shows Sustained, without allowing the binding to alter model,
            # reasoning, sampling, context, output, or KV precision.
            evidence["engineSettingsByBackend"] = self.optimizer_bound_engine_settings(
                model, eligible, binding, options,
            )
        entries = self.verified_cross_engine_entries(
            model, eligible, evidence, preference=preference,
        )
        if binding is not None:
            bound_suite = str(binding["suite"])
            bound_shootout = str(binding.get("shootoutId") or "")
            bound_record_ids = binding.get("recordIds") or {}
            entries = [
                entry for entry in entries
                if str(entry.get("record", {}).get("suite") or "") == bound_suite
                and (
                    not bound_shootout
                    or str(entry.get("record", {}).get("shootoutId") or "") == bound_shootout
                )
                and (
                    not bound_record_ids
                    or str(entry.get("record", {}).get("id") or "")
                    == str(bound_record_ids.get(str(entry.get("backend") or "")) or "")
                )
            ]
        groups: dict[str, dict[str, dict[str, Any]]] = {}
        for entry in entries:
            shootout_id = str(entry.get("record", {}).get("shootoutId") or "")
            group_key = (
                f"{entry['signature']}\x00{shootout_id}"
                if shootout_id else str(entry["signature"])
            )
            group = groups.setdefault(group_key, {})
            backend = entry["backend"]
            existing = group.get(backend)
            if not existing or str(entry["record"].get("createdAt") or "") > str(existing["record"].get("createdAt") or ""):
                group[backend] = entry
        complete = [
            list(group.values()) for group in groups.values()
            if set(group) == set(eligible) and len(group) >= 2
        ]
        engine_meta = {
            "requested": True, "originalBackend": current_backend,
            "preference": preference, "preferenceLabel": self.policy.engine_preference_labels[preference],
            "eligibleBackends": [
                {"backend": backend, "label": self.policy.backend_labels[backend]} for backend in eligible
            ],
            "excludedBackends": excluded,
        }
        if eligible == [current_backend]:
            if binding is not None:
                raise ValueError(
                    "That saved engine comparison no longer has two compatible engines. "
                    "Refresh performance evidence before applying it."
                )
            qualification = self.evidence.verified_route_qualification(
                model, current_backend, evidence,
            )
            if qualification is not None:
                qualified_route = self.evidence.public_route_qualification_result(
                    model, qualification, preference,
                )
                metrics = qualification["qualification"]["metrics"]
                reason = (
                    f"The exact {selected_spec['routeLabel'] if selected_spec else self.policy.backend_labels[current_backend]} is locally qualified at "
                    f"{float(metrics['medianDecodeTokensPerSecond']):.1f} generation tok/s "
                    f"with {float(metrics['medianTTFTSeconds']):.2f}s median time to first output; "
                    "separate reasoning and final-answer output were both observed."
                )
                result = self._optimizer_with_forced_record(
                    payload, models, model, current_backend, qualification, evidence,
                )
                result.update({
                    "engineChanged": False,
                    "engineEvidenceTier": "local-route-qualification",
                    "engineEvidenceLabel": f"Qualified {self.policy.backend_labels[current_backend]} route",
                    "comparedEngines": [], "qualifiedRoutes": [qualified_route],
                    "missingEngines": [], "engineRationale": [reason],
                    "engineDecision": {
                        **engine_meta, "routeQualification": True,
                        "evidenceBinding": {
                            "scope": "route", "suite": str(qualification.get("suite") or "agentic"),
                            "preference": preference, "recordId": str(qualification.get("id") or ""),
                        },
                    },
                    "engineEvidenceBinding": {
                        "scope": "route", "suite": str(qualification.get("suite") or "agentic"),
                        "preference": preference, "recordId": str(qualification.get("id") or ""),
                    },
                    "enginePreference": preference,
                    "engineNextAction": self.engine_selection_next_action(
                        "keep-current", preference, current_backend, client, reason,
                        recommended_suite=(
                            str(selected_spec["suite"]) if selected_spec else None
                        ),
                    ),
                    "settingsEvidenceTier": result.get("evidenceTier"),
                    "settingsEvidenceLabel": result.get("evidenceLabel"),
                    "evidenceTier": "local-route-qualification",
                    "evidenceLabel": f"Qualified {self.policy.backend_labels[current_backend]} route",
                })
                result["rationale"] = result["engineRationale"] + list(result.get("rationale") or [])
                return result
            route_spec = self.contracts.route_qualification_spec(model, current_backend, context)
            route_qualification_needed = route_spec is not None
            reason = (
                f"{route_spec['routeLabel']} is the only honest route for this exact checkpoint. "
                "Run one bounded route qualification to measure authoritative generation TPS, "
                "time to first output, usage, reasoning, final-answer reliability, tools, memory, and unload."
                if route_spec else
                f"{self.policy.backend_labels[current_backend]} is the only installed route that can run this exact "
                "model and work contract; there is no honest cross-engine calibration to perform."
            )
            current.update({
                "engineChanged": False,
                "engineEvidenceTier": (
                    "single-route-qualification-needed"
                    if route_qualification_needed else "single-compatible-engine"
                ),
                "engineEvidenceLabel": (
                    "Route qualification needed"
                    if route_qualification_needed else "Only compatible engine"
                ),
                "comparedEngines": [],
                "missingEngines": [],
                "engineRationale": [reason],
                "engineDecision": {**engine_meta, "routeQualification": route_qualification_needed},
                "engineNextAction": self.engine_selection_next_action(
                    "calibrate" if route_qualification_needed else "keep-current",
                    preference, current_backend, client, reason,
                    recommended_suite=(
                        str(route_spec["suite"]) if route_spec else None
                    ),
                ),
            })
            current["rationale"] = current["engineRationale"] + list(current.get("rationale") or [])
            return current
        if not complete:
            if binding is not None:
                raise ValueError(
                    "That saved engine comparison is stale or no longer matches every compatible engine. "
                    "Refresh performance evidence before applying it."
                )
            largest = max(groups.values(), key=len, default={})
            measured = sorted(largest)
            missing = [backend for backend in eligible if backend not in largest]
            missing_public = [
                {"backend": backend, "label": self.policy.backend_labels[backend]}
                for backend in missing
            ]
            missing_reason = (
                "No like-for-like cross-engine winner is available yet. "
                + (
                    "Run the same Benchmark Lab contract in "
                    + ", ".join(self.policy.backend_labels[item] for item in missing)
                    + "."
                    if missing else
                    "At least two compatible engines need the same Benchmark Lab contract."
                )
            )
            current.update({
                "engineChanged": False,
                "engineEvidenceTier": "incomplete-cross-engine-matrix",
                "engineEvidenceLabel": "Current engine kept",
                "comparedEngines": [
                    {"backend": backend, "label": self.policy.backend_labels[backend]}
                    for backend in measured
                ],
                "missingEngines": missing_public,
                "engineRationale": [
                    missing_reason,
                    "The current engine was kept; open Calibration to review the exact measurement before changing settings.",
                ],
                "engineDecision": engine_meta,
                "engineNextAction": self.engine_selection_next_action(
                    "calibrate", preference, current_backend, client,
                    missing_reason, missing_public,
                ),
            })
            current["rationale"] = current["engineRationale"] + list(current.get("rationale") or [])
            return current

        comparable_complete = [
            (group, cross_engine_workload_compatibility(group))
            for group in complete
        ]
        usable_complete = [
            (group, quality) for group, quality in comparable_complete
            if quality.get("comparable") is True
        ]
        if not usable_complete:
            if binding is not None:
                raise ValueError(
                    "That saved engine comparison no longer passes output and workload parity. "
                    "Refresh performance evidence before applying it."
                )
            newest_group, quality = max(
                comparable_complete, key=lambda item: self._cross_engine_group_rank(item[0], client),
            )
            mismatch_reason = str(
                quality.get("warning")
                or "The completed engine measurements did not perform comparable amounts of work."
            )
            current.update({
                "engineChanged": False,
                "engineEvidenceTier": "cross-engine-workload-mismatch",
                "engineEvidenceLabel": "Completed results need review",
                "comparedEngines": [
                    {"backend": item["backend"], "label": self.policy.backend_labels[item["backend"]]}
                    for item in newest_group
                ],
                "missingEngines": [],
                "engineRationale": [
                    mismatch_reason,
                    "The completed measurements were kept, but no automatic engine switch was made.",
                ],
                "engineDecision": {**engine_meta, "workloadComparison": copy.deepcopy(quality)},
                "enginePreference": preference,
                "engineNextAction": self.engine_selection_next_action(
                    "calibrate", preference, current_backend, client, mismatch_reason,
                ),
            })
            current["rationale"] = current["engineRationale"] + list(current.get("rationale") or [])
            return current

        chosen_group, workload_comparison = max(
            usable_complete, key=lambda item: self._cross_engine_group_rank(item[0], client),
        )
        selected_suites = {
            str(item.get("record", {}).get("suite") or "") for item in chosen_group
        }
        if len(selected_suites) != 1 or "" in selected_suites:
            raise RuntimeError("The selected engine comparison has no single workload suite.")
        selected_shootouts = {
            str(item.get("record", {}).get("shootoutId") or "") for item in chosen_group
        }
        selected_suite = next(iter(selected_suites))
        selected_shootout = (
            next(iter(selected_shootouts))
            if len(selected_shootouts) == 1 and "" not in selected_shootouts else ""
        )
        selected_binding: dict[str, Any] | None = None
        if selected_shootout:
            selected_record_ids = {
                str(item["backend"]): str(item.get("record", {}).get("id") or "")
                for item in chosen_group
            }
            if (
                set(selected_record_ids) == set(eligible)
                and all(selected_record_ids.values())
                and len(set(selected_record_ids.values())) == len(selected_record_ids)
            ):
                selected_binding = {
                    "scope": "engine", "suite": selected_suite, "preference": preference,
                    "shootoutId": selected_shootout,
                    "recordIds": selected_record_ids,
                }
        if binding is not None and (
            selected_binding is None or binding != selected_binding
        ):
            raise ValueError(
                "That saved engine comparison changed while it was being applied. "
                "Refresh performance evidence and try again."
            )
        if selected_binding is not None:
            engine_meta["evidenceBinding"] = copy.deepcopy(selected_binding)
        engine_meta["workloadComparison"] = copy.deepcopy(workload_comparison)
        profile = self.rank_cross_engine_profile(chosen_group, preference)
        ranked = profile.get("ranked") if profile.get("available") else _speed_ranked_entries(chosen_group)
        leading_backends = [str(item) for item in profile.get("leadingBackends") or []]
        leading_backend_set = set(leading_backends)
        compared = [
            {
                "backend": item["backend"], "label": self.policy.backend_labels[item["backend"]],
                "leading": str(item["backend"]) in leading_backend_set,
                "mode": str(item["record"].get("winner") or "ar"),
                "testedModes": copy.deepcopy(item["record"].get("comparedModes") or ["ar"]),
                "modeDetail": self.benchmark_mode_summary(
                    model, item["backend"], item["record"].get("comparedModes") or ["ar"],
                    item["record"].get("engineSettings"),
                    kv=str(item["record"].get("targetKV") or "off"),
                ),
                "accelerationReason": self.benchmark_acceleration_reason(
                    model, item["backend"], item["record"].get("comparedModes") or ["ar"],
                    kv=str(item["record"].get("targetKV") or "off"),
                ),
                "settingsLabel": self.benchmark_engine_settings_label(
                    item["backend"], item["record"].get("engineSettings"),
                ),
                "routeSettingsLabel": self.benchmark_route_settings_label(
                    item["backend"], item["record"].get("winner"),
                    item["record"].get("settings"),
                ),
                "settingsSearch": self.evidence.public_benchmark_settings_search_result(
                    item["record"],
                ),
                "score": round(float(item["score"]), 4),
                "metric": item["metric"], "display": item["display"],
                "firstTokenSeconds": item.get("firstTokenSeconds"),
                "decodeTokensPerSecond": item.get("decodeTokensPerSecond"),
                "peakPressureDeltaBytes": item.get("peakPressureDeltaBytes"),
                "baselineHeadroomPercent": item.get("baselineHeadroomPercent"),
                "minimumHeadroomPercent": item.get("minimumHeadroomPercent"),
                "totalMemoryBytes": item.get("totalMemoryBytes"),
                "thermalWorst": item.get("thermalWorst"),
                "thermalWorstValue": item.get("thermalWorstValue"),
                "thermalStart": item.get("thermalStart"),
                "thermalStartValue": item.get("thermalStartValue"),
                "lowPowerMode": item.get("lowPowerMode"),
                "resourceCooldownStatus": item.get("resourceCooldownStatus"),
                "profileDisplay": (profile.get("displays") or {}).get(item["backend"]),
                "suite": str(item["record"].get("suite") or ""),
                "createdAt": str(item["record"].get("createdAt") or ""),
            }
            for item in ranked
        ]
        if not profile.get("available"):
            if binding is not None:
                raise ValueError(
                    "That saved engine comparison no longer contains the selected metric. "
                    "Refresh performance evidence before applying it."
                )
            missing_profile = [str(item) for item in profile.get("missing") or []]
            missing_public = [
                {
                    "backend": backend, "label": self.policy.backend_labels[backend],
                    "reason": "This matching record lacks the selected resource metric.",
                }
                for backend in missing_profile
            ]
            profile_reason = str(profile.get("reason") or (
                f"{self.policy.engine_preference_labels[preference]} needs the same measured metric from every compatible engine."
            ))
            current.update({
                "engineChanged": False,
                "engineEvidenceTier": "cross-engine-profile-incomplete",
                "engineEvidenceLabel": f"{self.policy.engine_preference_labels[preference]} evidence unavailable",
                "comparedEngines": compared,
                "missingEngines": missing_public,
                "engineRationale": [
                    profile_reason,
                    (
                        "Run a new Engine Shootout after the Mac settles; open Calibration to review the exact measurement before changing settings."
                        if profile.get("conditionMismatch") else
                        "Run one new Engine Shootout; open Calibration to review the exact measurement before changing settings."
                    ),
                ],
                "engineDecision": engine_meta,
                **({"engineEvidenceBinding": copy.deepcopy(selected_binding)} if selected_binding else {}),
                "enginePreference": preference,
                "engineNextAction": self.engine_selection_next_action(
                    "calibrate", preference, current_backend, client,
                    profile_reason, missing_public,
                ),
            })
            current["rationale"] = current["engineRationale"] + list(current.get("rationale") or [])
            return current
        winner = profile["winner"]
        profile_trusted = bool(profile.get("trusted"))
        current_in_leading_band = current_backend in leading_backend_set
        engine_meta.update({
            "leadingBackends": list(leading_backends),
            "currentInLeadingBand": current_in_leading_band,
        })
        if not profile_trusted and current_in_leading_band:
            current_entry = next(
                item for item in chosen_group
                if str(item["backend"]) == current_backend
            )
            current = self._optimizer_with_forced_record(
                payload, models, model, current_backend,
                current_entry["record"], evidence,
            )
            tie_reason = str(profile.get("tieReason") or "The measured difference did not clear the switch threshold.")
            rationale = [
                tie_reason,
                "The current engine is inside the measured leading group, so it was kept to avoid switching on measurement noise.",
            ]
            if workload_comparison.get("warning"):
                rationale.append(str(workload_comparison["warning"]))
            current.update({
                "engineChanged": False,
                "engineEvidenceTier": "cross-engine-noise-floor",
                "engineEvidenceLabel": f"{self.policy.engine_preference_labels[preference]} tied · current kept",
                "comparedEngines": compared, "missingEngines": [],
                "engineRationale": rationale,
                "engineDecision": engine_meta,
                **({"engineEvidenceBinding": copy.deepcopy(selected_binding)} if selected_binding else {}),
                "enginePreference": preference,
                "enginePreferenceMetric": profile["metric"],
                "leadingBackends": list(leading_backends),
                "currentInLeadingBand": True,
                "engineNextAction": self.engine_selection_next_action(
                    "keep-current", preference, current_backend, client, tie_reason,
                ),
                "settingsEvidenceTier": current.get("evidenceTier"),
                "settingsEvidenceLabel": current.get("evidenceLabel"),
                "evidenceTier": "cross-engine-noise-floor",
                "evidenceLabel": f"{self.policy.engine_preference_labels[preference]} tied · current kept",
            })
            current["rationale"] = current["engineRationale"] + list(current.get("rationale") or [])
            return current

        winning_backend = str(winner["backend"])
        result = self._optimizer_with_forced_record(
            payload, models, model, winning_backend, winner["record"], evidence,
        )
        if profile_trusted:
            winner_rationale = [
                str(profile["winnerReason"]),
                "The comparison preserved this model, Mac, workload, context, response limit, reasoning, sampling, and KV precision.",
            ]
            evidence_tier = "cross-engine-local-benchmark"
            evidence_label = f"{self.policy.engine_preference_labels[preference]} · locally measured"
        else:
            tie_reason = str(profile.get("tieReason") or "The leading engines finished inside the switch threshold.")
            winner_rationale = [
                tie_reason,
                (
                    f"{self.policy.backend_labels[current_backend]} was outside the measured leading group, so "
                    f"{self.policy.backend_labels[winning_backend]} was selected from the tied leaders instead of preserving a slower route."
                ),
                "The comparison preserved this model, Mac, workload, context, response limit, reasoning, sampling, and KV precision.",
            ]
            evidence_tier = "cross-engine-leading-band"
            evidence_label = f"{self.policy.engine_preference_labels[preference]} · leading group"
        if workload_comparison.get("warning"):
            winner_rationale.append(str(workload_comparison["warning"]))
        next_action = (
            "apply"
            if winning_backend != current_backend or bool(result.get("changedKeys"))
            else "keep-current"
        )
        result.update({
            "engineChanged": winning_backend != current_backend,
            "originalBackend": current_backend,
            "engineEvidenceTier": evidence_tier,
            "engineEvidenceLabel": evidence_label,
            "comparedEngines": compared, "missingEngines": [],
            "engineRationale": winner_rationale,
            "engineOutputWarning": str(workload_comparison.get("warning") or ""),
            "exactOutputMatch": workload_comparison.get("exactOutputMatch") is True,
            "engineDecision": engine_meta,
            **({"engineEvidenceBinding": copy.deepcopy(selected_binding)} if selected_binding else {}),
            "enginePreference": preference,
            "enginePreferenceMetric": profile["metric"],
            "leadingBackends": list(leading_backends),
            "currentInLeadingBand": current_in_leading_band,
            "engineNextAction": self.engine_selection_next_action(
                next_action, preference, winning_backend, client, str(winner_rationale[0]),
            ),
            "settingsEvidenceTier": result.get("evidenceTier"),
            "settingsEvidenceLabel": result.get("evidenceLabel"),
            "evidenceTier": evidence_tier,
            "evidenceLabel": evidence_label,
        })
        result["rationale"] = result["engineRationale"] + list(result.get("rationale") or [])
        return result


    def _benchmark_history_value(self, 
        measurement: dict[str, Any], preference: str,
    ) -> tuple[float | None, str, bool]:
        if preference == "throughput":
            value = measurement.get("decodeTokensPerSecond")
            return (
                (float(value), f"{float(value):.1f} tok/s generation", False)
                if isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(float(value)) and float(value) > 0
                else (None, "Unavailable", False)
            )
        if preference == "fastest":
            return float(measurement["score"]), str(measurement["display"]), not bool(measurement["higherIsBetter"])
        if preference == "responsive":
            value = measurement.get("firstTokenSeconds")
            return (float(value), f"{float(value):.2f}s first output", True) if isinstance(value, (int, float)) else (None, "Unavailable", True)
        if preference == "memory":
            value = measurement.get("peakPressureDeltaBytes")
            return (float(value), f"{self.live.display_size(int(value))} pressure delta", True) if isinstance(value, int) and not isinstance(value, bool) else (None, "Unavailable", True)
        value = measurement.get("thermalWorstValue")
        return (
            float(value), f"{self.policy.thermal_state_labels[int(value)]} worst state", True
        ) if isinstance(value, int) and not isinstance(value, bool) and value in self.policy.thermal_state_labels else (None, "Unavailable", True)


    def benchmark_history_request(self, 
        payload: dict[str, Any], models: list[dict[str, Any]],
        records: list[dict[str, Any]] | None = None, now: datetime | None = None,
    ) -> dict[str, Any]:
        """Summarise repeat measurements for the exact visible contract without promoting stale data."""
        model_id = str(payload.get("modelId") or "")
        model = next((item for item in models if item.get("id") == model_id), None)
        if not model:
            raise ValueError("The selected model is no longer in the scanned catalog. Refresh models.")
        reasoning_contract = self.benchmark_reasoning_contract(payload, model)
        comparison_payload = copy.deepcopy(payload)
        comparison_payload["reasoning"] = reasoning_contract["measured"]
        comparison_payload, context_adjustment = self.contracts.normalized_ssd_comparison_request(
            comparison_payload, model,
        )
        current = self.optimal_request(comparison_payload, models)
        backend = str(payload.get("backend") or current["backend"])
        client = str(payload.get("client") or "")
        reasoning = str(comparison_payload.get("reasoning") or "auto")
        options = comparison_payload.get("options") if isinstance(comparison_payload.get("options"), dict) else {}
        kv = str(options.get("kv") or "off")
        context, output = self.contracts.validated_limits(model, comparison_payload)
        chat = self.contracts.validated_chat_settings(model, comparison_payload, client)
        sampling_contract = self.contracts.validated_sampling_contract(
            model, comparison_payload, client, chat,
        )
        assert sampling_contract is not None
        evidence = self.optimizer_evidence(
            model, context, output, client, reasoning, kv, chat, sampling_contract,
        )
        suite_name = str(payload.get("suite") or "agentic")
        suite = self.policy.benchmark_suites.get(suite_name)
        if not suite:
            raise ValueError("Choose a Quick, Standard, Thorough, or Agentic Route Lab suite.")
        preference = str(payload.get("enginePreference") or "throughput")
        if preference not in self.policy.engine_preference_labels:
            raise ValueError("Choose a supported benchmark history goal.")
        eligible: list[str] = []
        ssd_profile = model.get("ssdStreaming") if isinstance(model.get("ssdStreaming"), dict) else {}
        ssd_lane = ssd_profile.get("recommended") is True
        candidate_backends = self.live.ssd_profile_candidate_backends(ssd_profile) if ssd_lane else tuple(self.policy.engine_adapters)
        for candidate in candidate_backends:
            allowed, _reason = self.benchmark_backend_eligibility(
                model, candidate, client, reasoning, kv, chat,
            )
            if allowed:
                eligible.append(candidate)
        self.add_benchmark_engine_evidence(evidence, model, options, eligible)
        machine = self.live.hardware_fingerprint()
        source_records = [
            copy.deepcopy(item) for item in (records if records is not None else self.evidence.load_benchmark_records())
            if isinstance(item, dict)
        ]
        scenario_contract = list(suite.get("scenarios") or [])

        def exact(record: dict[str, Any]) -> bool:
            record_backend = str(record.get("backend") or "")
            capability = model.get("backends", {}).get(record_backend, {})
            return bool(
                record.get("scope") == "local"
                and record_backend in model.get("backends", {})
                and record.get("modelFingerprint") == capability.get("benchmarkModelFingerprint")
                and record.get("runtimeVersion") == capability.get("runtimeVersion")
                and record.get("hardwareFingerprint") == machine
                and self.evidence.benchmark_integrity_issue(record) is None
                and (
                    not ssd_lane
                    or (
                        record_backend in self.policy.ssd_streaming_backends
                        and record.get("ssdStreaming") is True
                        and record.get("ssdComparisonIdentity") == capability.get("comparisonIdentity")
                    )
                )
                and (
                    record.get("comparisonContractVersion") != self.policy.benchmark_comparison_contract_version
                    or self.evidence.benchmark_engine_settings_match(
                        record, evidence.get("engineSettingsByBackend", {}).get(record_backend),
                    )
                )
                and record.get("client") in {None, "any", client}
                and record.get("reasoning") in {"any", reasoning}
                and record.get("targetKV") == evidence["kv"]
                and record.get("samplingFingerprint") == evidence["samplingFingerprint"]
                and isinstance(record.get("contextMin"), int)
                and isinstance(record.get("contextMax"), int)
                and record["contextMin"] <= context <= record["contextMax"]
                and self.evidence.benchmark_record_output_contract_verified(record, output)
                and record.get("suite") == suite_name
                and isinstance(record.get("scenarioContract", []), list)
                and (record.get("scenarioContract") or []) == scenario_contract
                and self.benchmark_record_matches_selection_preference(record, preference)
                # History may describe only evidence that could also drive Apply.
                # Reuse the complete local-record verifier here so a structurally
                # matching but failed or tampered shootout never becomes a receipt.
                and self.evidence.local_benchmark_record_verified(capability, record, evidence)
            )

        exact_records = [record for record in source_records if exact(record)]
        exact_record_ids = {id(record) for record in exact_records}
        shootout_groups: dict[str, dict[str, dict[str, Any]]] = {}
        for record in exact_records:
            shootout_id = str(record.get("shootoutId") or "")
            if not shootout_id:
                continue
            by_backend = shootout_groups.setdefault(shootout_id, {})
            record_backend = str(record.get("backend") or "")
            previous = by_backend.get(record_backend)
            if previous is None or str(record.get("createdAt") or "") > str(previous.get("createdAt") or ""):
                by_backend[record_backend] = record

        evaluated: list[dict[str, Any]] = []
        for shootout_id, by_backend in shootout_groups.items():
            comparable_records = {
                candidate: record for candidate, record in by_backend.items()
                if candidate in eligible
            }
            entries: list[dict[str, Any]] = []
            for candidate, record in comparable_records.items():
                measurement = self.cross_engine_benchmark_measurement(record)
                if measurement:
                    entries.append({"backend": candidate, "record": record, **measurement})
            complete = set(comparable_records) == set(eligible) and len(entries) == len(eligible) and len(entries) >= 2
            signatures_match = complete and len({str(item["signature"]) for item in entries}) == 1
            workload_comparison = (
                cross_engine_workload_compatibility(entries)
                if signatures_match else {
                    "comparable": False, "exactOutputMatch": False,
                    "warning": "The engines did not run the same generated input schedule.",
                }
            )
            profile: dict[str, Any] | None = (
                self.rank_cross_engine_profile(entries, preference)
                if workload_comparison.get("comparable") is True else None
            )
            if not complete:
                status = "incomplete"
                summary = "This run does not contain every engine compatible with the current contract."
            elif workload_comparison.get("comparable") is not True:
                status = "workload-mismatch"
                summary = str(workload_comparison.get("warning") or "The measured workloads were not comparable.")
            elif not profile or not profile.get("available"):
                status = "conditions-mismatched"
                summary = str((profile or {}).get("reason") or "The selected metric is incomplete for this run.")
            elif not profile.get("trusted"):
                status = "tie"
                summary = str(profile.get("tieReason") or "The result stayed inside the measurement noise floor.")
            else:
                status = "trusted"
                summary = str(profile["winnerReason"])
                if workload_comparison.get("warning"):
                    summary += " " + str(workload_comparison["warning"])
            execution_order = next(
                (
                    list(record.get("shootoutExecutionOrder") or [])
                    for record in by_backend.values()
                    if isinstance(record.get("shootoutExecutionOrder"), list)
                ),
                list(by_backend),
            )
            measurement_map = {item["backend"]: item for item in entries}
            engine_rows: list[dict[str, Any]] = []
            for candidate in execution_order:
                item = measurement_map.get(str(candidate))
                if not item:
                    continue
                value, value_display, lower_is_better = self._benchmark_history_value(item, preference)
                engine_rows.append({
                    "backend": item["backend"], "label": self.policy.backend_labels[item["backend"]],
                    "recordId": str(item["record"].get("id") or ""),
                    "mode": str(item["record"].get("winner") or "ar"),
                    "modeLabel": self.benchmark_public_mode_label(
                        str(item["backend"]), str(item["record"].get("winner") or "ar")
                    ),
                    "value": value, "valueDisplay": value_display,
                    "lowerIsBetter": lower_is_better,
                    "workloadDisplay": item["display"],
                    "routeSettingsLabel": self.benchmark_route_settings_label(
                        str(item["backend"]), item["record"].get("winner"),
                        item["record"].get("settings"),
                    ),
                    "settingsSearch": self.evidence.public_benchmark_settings_search_result(
                        item["record"],
                    ),
                    "firstTokenSeconds": item.get("firstTokenSeconds"),
                    "decodeTokensPerSecond": item.get("decodeTokensPerSecond"),
                    "peakPressureDeltaBytes": item.get("peakPressureDeltaBytes"),
                    "thermalWorst": item.get("thermalWorst"),
                    "profileDisplay": (profile.get("displays") or {}).get(item["backend"]) if profile else None,
                })
            created_at = max((str(record.get("createdAt") or "") for record in comparable_records.values()), default="")
            leading_backends = [
                str(item) for item in (profile or {}).get("leadingBackends") or []
            ]
            recommended_backend = str((profile or {}).get("winner", {}).get("backend") or "")
            evaluated.append({
                "id": shootout_id, "createdAt": created_at,
                "status": status, "summary": summary,
                "trustedWinner": status == "trusted",
                "winnerBackend": profile["winner"]["backend"] if status == "trusted" and profile else None,
                "winnerLabel": self.policy.backend_labels[profile["winner"]["backend"]] if status == "trusted" and profile else None,
                "leadingBackends": leading_backends,
                "recommendedBackend": recommended_backend or None,
                "recommendedLabel": self.policy.backend_labels.get(recommended_backend) if recommended_backend else None,
                "metric": profile.get("metric") if profile else None,
                "engines": engine_rows,
                "exactOutputMatch": workload_comparison.get("exactOutputMatch") is True,
                "outputWarning": str(workload_comparison.get("warning") or ""),
                "_profileAvailable": bool(profile and profile.get("available")),
            })
        evaluated.sort(key=lambda item: str(item.get("createdAt") or ""), reverse=True)

        series: list[dict[str, Any]] = []
        comparable_runs = [item for item in reversed(evaluated) if item.get("_profileAvailable")]
        for candidate in eligible:
            points: list[dict[str, Any]] = []
            lower_is_better = True
            for run in comparable_runs:
                engine = next((item for item in run["engines"] if item["backend"] == candidate), None)
                if not engine or not isinstance(engine.get("value"), (int, float)):
                    continue
                lower_is_better = bool(engine["lowerIsBetter"])
                points.append({
                    "createdAt": run["createdAt"], "value": engine["value"],
                    "display": engine["valueDisplay"], "runStatus": run["status"],
                })
            if not points:
                continue
            improvement: float | None = None
            if len(points) >= 2 and preference != "thermal":
                previous_value = float(points[-2]["value"])
                latest_value = float(points[-1]["value"])
                if abs(previous_value) > 0.000_001:
                    improvement = (
                        (previous_value - latest_value) / abs(previous_value) * 100
                        if lower_is_better else
                        (latest_value - previous_value) / abs(previous_value) * 100
                    )
            series.append({
                "backend": candidate, "label": self.policy.backend_labels[candidate],
                "lowerIsBetter": lower_is_better,
                "points": points[-self.policy.benchmark_history_visible_runs:],
                "improvementPercent": round(improvement, 2) if improvement is not None else None,
            })

        current_route_runs: list[dict[str, Any]] = []
        for record in sorted(exact_records, key=lambda item: str(item.get("createdAt") or ""), reverse=True):
            if record.get("shootoutId") or record.get("backend") != backend:
                continue
            capability = model.get("backends", {}).get(backend, {})
            if not self.evidence.local_benchmark_record_verified(capability, record, evidence):
                continue
            measurement = self.cross_engine_benchmark_measurement(record)
            if not measurement:
                continue
            route_summary = {
                "id": record.get("id"), "createdAt": record.get("createdAt"),
                "suite": record.get("suite"),
                "backend": backend, "backendLabel": self.policy.backend_labels[backend],
                "winner": record.get("winner"),
                "winnerLabel": self.benchmark_public_mode_label(
                    backend, str(record.get("winner") or "ar")
                ),
                "display": measurement["display"],
                "routeSettingsLabel": self.benchmark_route_settings_label(
                    backend, record.get("winner"), record.get("settings"),
                ),
                "settingsSearch": self.evidence.public_benchmark_settings_search_result(record),
                "firstTokenSeconds": measurement.get("firstTokenSeconds"),
                "decodeTokensPerSecond": measurement.get("decodeTokensPerSecond"),
                "peakPressureDeltaBytes": measurement.get("peakPressureDeltaBytes"),
                "thermalWorst": measurement.get("thermalWorst"),
                "recommendation": record.get("recommendation"),
            }
            if record.get("kind") == "route-qualification":
                route_summary.update({
                    "kind": "route-qualification",
                    "routeQualification": True,
                    "qualifiedBackend": backend,
                })
            current_route_runs.append(route_summary)
            if len(current_route_runs) >= 4:
                break

        # Review comes from verified, saved evidence, never the in-memory job or a
        # caller-supplied result. Applying still revalidates the exact record ID.
        review_result = None
        if "reviewRecordId" in payload:
            review_id = payload["reviewRecordId"]
            if not isinstance(review_id, str) or not review_id or len(review_id) > 128:
                raise ValueError("Choose a saved benchmark result to review.")
            review_result = next((copy.deepcopy(record) for record in exact_records
                                  if record.get("id") == review_id
                                  and record.get("backend") == backend
                                  and not record.get("shootoutId")), None)
            if review_result is None:
                raise ValueError("That saved result no longer matches the selected model and settings.")

        current_fingerprints = {
            str(capability.get("benchmarkModelFingerprint") or "")
            for capability in model.get("backends", {}).values() if isinstance(capability, dict)
        } - {""}
        related = [
            record for record in source_records
            if record.get("modelId") == model_id
            or record.get("modelName") == model.get("name")
            or str(record.get("modelFingerprint") or "") in current_fingerprints
        ]
        other_reasons: dict[str, int] = {}
        for record in related:
            if id(record) in exact_record_ids:
                continue
            record_backend = str(record.get("backend") or "")
            capability = model.get("backends", {}).get(record_backend, {})
            integrity_issue = self.evidence.benchmark_runtime_integrity_issue(record)
            expected_settings = evidence.get("engineSettingsByBackend", {}).get(record_backend)
            if integrity_issue:
                reason = "Runtime profile re-test required"
            elif self.evidence.benchmark_probe_integrity_issue(record):
                reason = "Correctness sampling re-test required"
            elif record.get("modelFingerprint") != capability.get("benchmarkModelFingerprint"):
                reason = "Model artifact changed"
            elif record.get("hardwareFingerprint") != machine:
                reason = "Mac or macOS changed"
            elif record.get("runtimeVersion") != capability.get("runtimeVersion"):
                reason = "Runtime changed"
            elif (
                record.get("comparisonContractVersion") == self.policy.benchmark_comparison_contract_version
                and record.get("engineSettings") != expected_settings
            ):
                reason = "Engine controls changed"
            elif record.get("suite") != suite_name:
                reason = "Different workload suite"
            else:
                reason = "Different visible contract"
            other_reasons[reason] = other_reasons.get(reason, 0) + 1

        current_time = (now or self.live.now(timezone.utc)).astimezone(timezone.utc)
        latest_time = max(
            (_benchmark_created_at(record.get("createdAt")) for record in exact_records),
            default=None,
            key=lambda item: item or datetime.min.replace(tzinfo=timezone.utc),
        )
        latest_is_future = bool(latest_time is not None and latest_time > current_time)
        age_days = (
            (current_time - latest_time).total_seconds() / 86_400
            if latest_time is not None and not latest_is_future else None
        )
        if latest_time is None:
            freshness = "missing"
            freshness_message = (
                "No saved run matches every visible contract field."
                + (" Other local evidence is retained below but cannot drive Apply fastest safe settings." if other_reasons else "")
            )
        elif latest_is_future:
            freshness = "older"
            freshness_message = (
                "The newest exact run is dated in the future. Rerun before relying on this evidence."
            )
        elif age_days is not None and age_days > self.policy.benchmark_history_fresh_days:
            freshness = "older"
            freshness_message = (
                f"The newest exact run is {age_days:.0f} days old. Its fingerprints still match, but rerun to confirm current system conditions."
            )
        else:
            freshness = "current"
            freshness_message = "Saved runs match this model, runtime, Mac, workload, engine controls, reasoning, sampling, limits, and KV contract."

        latest_shootout = evaluated[0] if evaluated else None
        receipt: dict[str, Any]
        if latest_shootout and latest_shootout.get("status") == "trusted":
            winner_backend = str(latest_shootout.get("winnerBackend") or "")
            winner_engine = next(
                (
                    item for item in latest_shootout.get("engines", [])
                    if item.get("backend") == winner_backend
                ),
                {},
            )
            receipt = {
                "state": "trusted-engine", "scope": "engine",
                "shootoutId": latest_shootout.get("id"),
                "recordIds": {
                    str(item.get("backend") or ""): str(item.get("recordId") or "")
                    for item in latest_shootout.get("engines", [])
                },
                "backend": winner_backend,
                "backendLabel": self.policy.backend_labels.get(winner_backend, winner_backend),
                "mode": winner_engine.get("mode"),
                "modeLabel": winner_engine.get("modeLabel"),
                "routeSettingsLabel": winner_engine.get("routeSettingsLabel"),
                "settingsSearch": copy.deepcopy(winner_engine.get("settingsSearch")),
                "workloadDisplay": winner_engine.get("workloadDisplay"),
                "firstTokenSeconds": winner_engine.get("firstTokenSeconds"),
                "decodeTokensPerSecond": winner_engine.get("decodeTokensPerSecond"),
                "createdAt": latest_shootout.get("createdAt"),
                "summary": latest_shootout.get("summary"),
            }
        elif latest_shootout and latest_shootout.get("status") == "tie":
            leading_backends = [
                str(item) for item in latest_shootout.get("leadingBackends") or []
            ]
            recommended_backend = str(latest_shootout.get("recommendedBackend") or "")
            receipt = {
                "state": "tie", "scope": "engine",
                "shootoutId": latest_shootout.get("id"),
                "recordIds": {
                    str(item.get("backend") or ""): str(item.get("recordId") or "")
                    for item in latest_shootout.get("engines", [])
                },
                "createdAt": latest_shootout.get("createdAt"),
                "summary": latest_shootout.get("summary"),
                "currentBackend": backend,
                "currentBackendLabel": self.policy.backend_labels.get(backend, backend),
                "currentInLeadingBand": backend in set(leading_backends),
                "leadingBackends": [
                    {"backend": item, "label": self.policy.backend_labels.get(item, item)}
                    for item in leading_backends
                ],
                "recommendedBackend": recommended_backend or None,
                "recommendedLabel": self.policy.backend_labels.get(recommended_backend, recommended_backend),
            }
        elif current_route_runs:
            route = current_route_runs[0]
            receipt = {
                "state": "trusted-route", "scope": "route",
                "recordId": route.get("id"),
                "backend": route.get("backend"),
                "backendLabel": route.get("backendLabel"),
                "mode": route.get("winner"),
                "modeLabel": route.get("winnerLabel"),
                "routeSettingsLabel": route.get("routeSettingsLabel"),
                "settingsSearch": copy.deepcopy(route.get("settingsSearch")),
                "workloadDisplay": route.get("display"),
                "firstTokenSeconds": route.get("firstTokenSeconds"),
                "decodeTokensPerSecond": route.get("decodeTokensPerSecond"),
                "createdAt": route.get("createdAt"),
                "summary": route.get("recommendation"),
            }
            if route.get("kind") == "route-qualification":
                receipt.update({
                    "kind": "route-qualification",
                    "routeQualification": True,
                    "qualifiedBackend": route.get("qualifiedBackend"),
                })
        elif latest_shootout:
            receipt = {
                "state": "incomplete", "scope": "engine",
                "createdAt": latest_shootout.get("createdAt"),
                "summary": latest_shootout.get("summary"),
            }
        else:
            receipt = {
                "state": "missing", "scope": "engine" if len(eligible) >= 2 else "route",
                "createdAt": None,
                "summary": (
                    "No saved run matches this intelligence, sampling, limits, KV, workload, runtime, model, and Mac contract."
                ),
            }
        receipt_time = _benchmark_created_at(receipt.get("createdAt"))
        receipt_is_future = bool(receipt_time is not None and receipt_time > current_time)
        receipt_age_days = (
            (current_time - receipt_time).total_seconds() / 86_400
            if receipt_time is not None and not receipt_is_future else None
        )
        receipt["ageDays"] = round(receipt_age_days, 2) if receipt_age_days is not None else None
        receipt["fresh"] = bool(
            receipt_time is not None
            and not receipt_is_future
            and receipt_age_days is not None
            and receipt_age_days <= self.policy.benchmark_history_fresh_days
        )
        receipt["suite"] = suite_name
        receipt["suiteLabel"] = suite["label"]
        receipt["contextAdjustment"] = copy.deepcopy(context_adjustment)
        receipt["eligibleBackends"] = [
            {"backend": item, "label": self.policy.backend_labels[item]} for item in eligible
        ]
        receipt["reasoningContract"] = copy.deepcopy(reasoning_contract)
        if receipt.get("state") in {"trusted-engine", "tie"}:
            shootout_id = str(receipt.get("shootoutId") or "")
            record_ids = receipt.get("recordIds") if isinstance(receipt.get("recordIds"), dict) else {}
            if shootout_id and record_ids and all(record_ids.values()):
                receipt["evidenceBinding"] = {
                    "scope": "engine", "suite": suite_name, "preference": preference,
                    "shootoutId": shootout_id, "recordIds": copy.deepcopy(record_ids),
                }
        elif receipt.get("state") == "trusted-route" and receipt.get("recordId"):
            receipt["evidenceBinding"] = {
                "scope": "route", "suite": suite_name, "preference": preference,
                "recordId": str(receipt["recordId"]),
            }
        receipt_backend = str(receipt.get("backend") or backend)
        receipt_capability = model.get("backends", {}).get(receipt_backend, {})
        receipt_descriptor = self.policy.engine_adapters.get(receipt_backend)
        receipt_runtime_installed = bool(
                    receipt_descriptor and self.live.descriptor_public(receipt_descriptor.id).get("installed") is True
        )
        receipt["performanceEvidence"] = self.evidence.route_performance_evidence(
            model, receipt_backend, receipt_capability, evidence,
        )
        receipt["hostSupport"] = self.contracts.route_host_support(
            model, receipt_backend, receipt_capability,
            runtime_installed=receipt_runtime_installed,
            artifact_compatible=bool(
                model.get("ready") is True
                and receipt_capability.get("runnable") is True
            ),
        )

        public_runs = []
        for run in evaluated[:self.policy.benchmark_history_visible_runs]:
            public = {key: copy.deepcopy(value) for key, value in run.items() if not key.startswith("_")}
            public_runs.append(public)
        return {
            "version": 1,
            "preference": preference,
            "preferenceLabel": self.policy.engine_preference_labels[preference],
            "contract": {
                "modelId": model_id, "model": model.get("name"),
                "client": client, "suite": suite_name, "suiteLabel": suite["label"],
                "context": context, "output": output, "reasoning": reasoning, "kv": kv,
                "reasoningContract": copy.deepcopy(reasoning_contract),
                "contextAdjustment": copy.deepcopy(context_adjustment),
                "eligibleBackends": [
                    {"backend": item, "label": self.policy.backend_labels[item]} for item in eligible
                ],
            },
            "freshness": freshness,
            "freshnessMessage": freshness_message,
            "latestExactCreatedAt": latest_time.isoformat().replace("+00:00", "Z") if latest_time else None,
            "latestExactAgeDays": round(age_days, 2) if age_days is not None else None,
            "exactRecordCount": len(exact_records),
            "shootoutCount": len(evaluated),
            "runs": public_runs,
            "series": series,
            "currentRouteRuns": current_route_runs,
            "reviewResult": review_result,
            "receipt": receipt,
            "otherEvidence": {
                "count": sum(other_reasons.values()),
                "reasons": [
                    {"label": label, "count": count}
                    for label, count in sorted(other_reasons.items())
                ],
            },
            "retention": {
                "perRoute": self.policy.benchmark_max_history_per_route,
                "totalRecords": self.policy.benchmark_max_records,
            },
            "canRerunShootout": len(eligible) >= 2,
        }
