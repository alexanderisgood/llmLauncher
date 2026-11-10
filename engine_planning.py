"""Native engine plans, private materialization and immediate launch proof.

The structural plan contains one already validated route. Frozen policies and
named runtime/artifact ports supply exact live facts; no controller, process
manager, installation map or global namespace is imported. Native settings
remain canonicalized by launch_contract, and builders recheck current artifacts.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, fields
import os
from pathlib import Path
import re
import secrets
import stat
import sys
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol

import kolibri_runtime
import rec_runtime
import rapidmlx_runtime
import launch_contract
from runtime_identity import OpenExecutableRevision
import slotstream_runtime
import splash_runtime
import strata_runtime
import whallm_runtime


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return value


def _private_bearer_basename_valid(value: Any) -> bool:
    return bool(
        isinstance(value, str) and 1 <= len(value) <= 128 and value not in {".", ".."}
        and not any(character in value for character in ("/", "\\", "\0"))
        and not any(ord(character) < 32 for character in value)
    )


class _FrozenPolicy:
    def __post_init__(self) -> None:
        for item in fields(self):
            object.__setattr__(self, item.name, _freeze(getattr(self, item.name)))


@dataclass(frozen=True)
class OmlxPolicy(_FrozenPolicy):
    expert_offload_version: str
    high_memory_ceiling_gib: float
    high_memory_soft_threshold: float
    high_memory_hard_threshold: float
    ane_sequence_length: int
    recommended_dflash_runtime: str


@dataclass(frozen=True)
class MtplxPolicy(_FrozenPolicy):
    dense_geometry: Mapping[str, int]
    candidate_route: str
    minimum_operator_context: int
    compiled_verify_fence: int
    baseline_environment: Mapping[str, str]
    candidate_environment: Mapping[str, str]


@dataclass(frozen=True)
class UzuPolicy(_FrozenPolicy):
    model_id: str
    model_commit: str
    toolchain_version: str
    boundary_contract_id: str
    context_windows: tuple[int, ...]
    process_memory_ceiling_bytes: int
    sandbox_executable: Path
    network_sandbox_profile: str
    api_key_filename: str
    private_bearer_filenames: tuple[str, ...]


@dataclass(frozen=True)
class LlamaCppPolicy(_FrozenPolicy):
    context: int
    memory_ceiling_bytes: int
    memory_ceiling_gib: float
    whallm_conflict_label: str
    runtime_directory: Path
    server_path: Path
    runtime_file_manifest: tuple[tuple[str, str, str], ...]
    model_file_manifest: tuple[tuple[str, int, str], ...]
    acquisition_marker: str
    reasoning_budget_message: str
    api_key_filename: str
    private_bearer_filenames: tuple[str, ...]


@dataclass(frozen=True)
class WhallmPolicy(_FrozenPolicy):
    model_id: str
    endpoint: str
    context_windows: tuple[int, ...]


PRIVATE_ENGINE_BEARER_FILES = MappingProxyType({
    "omlx": ("omlx/settings.json",), "mtplx": ("mtplx-api-key",),
    "kolibri": ("kolibri.json",), "freetoken": ("freetoken-bridge.json",),
    "whallm": ("whallm-bridge.json",),
    "rec": ("rec-data/rec/config/api-key",),
})


@dataclass(frozen=True)
class EnginePolicy(_FrozenPolicy):
    launch: launch_contract.LaunchPolicy
    thinking_budgets: Mapping[str, int]
    omlx: OmlxPolicy
    mtplx: MtplxPolicy
    uzu: UzuPolicy
    llamacpp: LlamaCppPolicy
    whallm: WhallmPolicy
    private_engine_bearer_files: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: PRIVATE_ENGINE_BEARER_FILES,
    )


class PreparationPlan(Protocol):
    backend: str
    client: str
    model: dict[str, Any]
    context: int
    output: int
    reasoning: str
    options: dict[str, Any]
    warnings: list[str]
    runtime_binary: str | None
    purpose: str
    project: str
    chat: dict[str, Any]


class EnginePlan(PreparationPlan, Protocol):
    run_id: str
    port: int
    run_dir: Path | None
    engine_argv: list[str]
    engine_env: dict[str, str]
    client_env: dict[str, str]
    secrets: dict[str, Any]


@dataclass(frozen=True)
class PlanningPaths:
    app_directory: Callable[[], Path]
    state_directory: Callable[[], Path]
    openai_bridge: Callable[[], Path]


@dataclass(frozen=True)
class RuntimeServices:
    selected_binary: Callable[[str], str | None]
    required_binary: Callable[[str], str]
    command_version: Callable[[str | None], str]
    omlx_plan_runtime_version: Callable[[PreparationPlan], str]
    omlx_runtime_python: Callable[[str], str | None]
    omlx_qwen_kernel_status: Callable[[str | None], dict[str, Any]]
    semantic_version_key: Callable[[str], tuple[int, ...]]
    exact_omlx_version: Callable[[str, str], bool]
    recommended_dflash_runtime: Callable[[str], bool]
    safe_int: Callable[[Any, int, int, int], int]


@dataclass(frozen=True)
class ModelServices:
    artifact_fingerprint: Callable[[Path, dict[str, Any]], str]
    weight_completeness: Callable[[Path, dict[str, Any]], tuple[bool, str, int]]
    normalized_model_type: Callable[[Any], str]
    qwen_ple_record: Callable[[dict[str, Any]], bool]
    strong_path_identity: Callable[[Path], tuple[Any, ...]]
    preserved_thinking_template: Callable[[str], str | None]


@dataclass(frozen=True)
class MemoryServices:
    physical_memory_bytes: Callable[[], int]
    wired_limit_bytes: Callable[[], int | None]
    resource_snapshot: Callable[[], dict[str, Any]]
    public_resource: Callable[[dict[str, Any]], dict[str, Any]]
    launch_estimate: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]]
    ane_memory_readiness: Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class OmlxChecks:
    dflash_capability_valid: Callable[[dict[str, Any], dict[str, Any]], bool]
    ane_record_valid: Callable[[Any, str, str], bool]
    cpu_sharing_profile: Callable[[Path], dict[str, Any]]
    expert_offload_options: Callable[[dict[str, Any], dict[str, Any]], tuple[float, int] | None]
    ple_profile: Callable[..., dict[str, Any]]
    expert_offload_profile: Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class MtplxChecks:
    operator_route: Callable[[PreparationPlan, dict[str, Any]], str]
    long_context_contract: Callable[..., dict[str, Any] | None]
    capability_matches: Callable[[Any, dict[str, Any]], bool]


@dataclass(frozen=True)
class UzuChecks:
    runtime_contract: Callable[..., dict[str, Any]]
    listener_protection_ready: Callable[[dict[str, Any]], bool]
    model_cache_contract: Callable[[], dict[str, Any] | None]
    ensure_offline_catalog: Callable[[dict[str, Any]], Any]
    validated_offline_catalog: Callable[[dict[str, Any]], str]
    open_executable: Callable[[Any], OpenExecutableRevision]
    confirm_open_executable: Callable[[OpenExecutableRevision], None]


@dataclass(frozen=True)
class LlamaCppChecks:
    runtime_contract: Callable[[str | None], dict[str, Any]]
    artifact_contract: Callable[[Path], dict[str, Any]]
    qualified_session_capacity: Callable[..., tuple[Any, Any, dict[str, Any]]]


@dataclass(frozen=True)
class FreeTokenChecks:
    connection: Callable[[], dict[str, Any]]
    validate_native_contract: Callable[..., dict[str, Any]]
    inspect_native_model: Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class WhallmChecks:
    qualification_conflict: Callable[[], dict[str, Any]]
    probe_endpoint: Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class PlanningIO:
    read_json: Callable[[Path], dict[str, Any]]
    atomic_json: Callable[[Path, dict[str, Any]], None]
    token_urlsafe: Callable[[int], str]
    token_hex: Callable[[int], str]
    slug: Callable[[str, int], str]


ENGINE_BUILD_METHODS = MappingProxyType({
    "omlx": "build_omlx", "lmstudio": "build_lmstudio", "mtplx": "build_mtplx",
    "uzu": "build_uzu", "freetoken": "build_freetoken", "swiftlm": "build_swiftlm",
    "mference": "build_mference", "whallm": "build_whallm", "slotstream": "build_slotstream",
    "splash": "build_splash", "strata": "build_strata", "rec": "build_rec", "kolibri": "build_kolibri", "llamacpp": "build_llamacpp",
    "rapidmlx": "build_rapidmlx",
})


@dataclass
class UzuExecutableLaunch:
    """The immediate Uzu command plus its retained, verified executable fd."""

    opened: OpenExecutableRevision
    argv: list[str]
    pass_fds: tuple[int, ...]
    executes_from_fd: bool

    def close(self) -> None:
        self.opened.close()

class EnginePlanner:
    def __init__(self, policy: EnginePolicy, paths: PlanningPaths,
                 runtime: RuntimeServices, models: ModelServices, memory: MemoryServices,
                 omlx: OmlxChecks, mtplx: MtplxChecks, uzu: UzuChecks,
                 llamacpp: LlamaCppChecks, freetoken: FreeTokenChecks,
                 whallm: WhallmChecks, io: PlanningIO) -> None:
        self.policy, self.paths = policy, paths
        self.runtime, self.models, self.memory = runtime, models, memory
        self.omlx, self.mtplx, self.uzu = omlx, mtplx, uzu
        self.llamacpp, self.freetoken, self.whallm, self.io = llamacpp, freetoken, whallm, io
        self.builders = MappingProxyType({
            backend: getattr(self, name) for backend, name in ENGINE_BUILD_METHODS.items()
        })

    def expert_offload_options(self, model: dict[str, Any], options: dict[str, Any]) -> tuple[float, int] | None:
        return self.omlx.expert_offload_options(model, options)

    def validated_profile_options(self, backend: str, model: dict[str, Any], capability: dict[str, Any], value: Any) -> dict[str, Any]:
        return launch_contract.validated_profile_options(
            backend, model, capability, value, policy=self.policy.launch, offload_checks=self,
        )

    def validated_freetoken_options(self, capability: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
        return launch_contract.validated_freetoken_options(capability, options, policy=self.policy.launch)

    def validate_runtime_context(self, backend: str, context: int) -> None:
        launch_contract.validate_runtime_context(backend, context, policy=self.policy.launch)

    def lmstudio_mtp_controls(self, options: dict[str, Any], capability: dict[str, Any]) -> dict[str, Any]:
        return launch_contract.lmstudio_mtp_controls(options, capability, policy=self.policy.launch)


    def build_engine_plan(self, plan: EnginePlan) -> None:
        assert plan.run_dir
        builder = self.builders.get(plan.backend)
        if builder is None:
            raise ValueError("Unknown inference-engine adapter.")
        cap = plan.model.get("backends", {}).get(plan.backend)
        if not isinstance(cap, dict):
            raise ValueError("The selected model has no capability record for this engine adapter.")
        plan.run_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        details = plan.run_dir.lstat()
        if (
            plan.run_dir.is_symlink()
            or not stat.S_ISDIR(details.st_mode)
            or details.st_uid != os.geteuid()
        ):
            raise ValueError("The private run folder is not an owner-controlled directory.")
        os.chmod(plan.run_dir, 0o700)
        builder(plan, cap)


    def _prepare_omlx_engine(self, plan: EnginePlan, cap: dict[str, Any]) -> dict[str, Any]:
        """Validate exact current oMLX state without files, keys, ports or processes."""
        acceleration = str(plan.options.get("acceleration", "auto"))
        if acceleration not in {"auto", "off", "mtp", "dflash"}:
            raise ValueError("Invalid oMLX acceleration mode.")
        if acceleration == "mtp" and not cap.get("mtp"):
            raise ValueError(cap.get("mtpReason") or "MTP is not verified for this model in oMLX.")
        if acceleration == "dflash" and not self.omlx.dflash_capability_valid(plan.model, cap):
            raise ValueError(cap.get("dflashReason") or "DFlash is not verified for this model.")
        kv = str(plan.options.get("kv", "off"))
        if kv not in {"off", "q8", "q6", "q4"}:
            raise ValueError("Invalid oMLX KV mode.")
        if acceleration == "dflash" and kv != "off":
            if str(plan.options.get("dflashVerify", "adaptive")) not in {"adaptive", "dflash"}:
                raise ValueError("Quantized KV requires Adaptive or Fixed DFlash. DDTree needs full precision.")
            if self.runtime.semantic_version_key(self.runtime.omlx_plan_runtime_version(plan)) != self.runtime.semantic_version_key("0.6.4"):
                raise ValueError("Quantized DFlash KV requires the launcher's oMLX 0.6.4 adapter.")
        if kv != "off":
            if acceleration == "dflash":
                plan.warnings.append(
                    f"DFlash target KV uses {kv.upper()} affine quantization with reusable prefixes. Quantization can change numerical output; ordinary oMLX fallback uses TurboQuant."
                )
            else:
                plan.warnings.append("TurboQuant KV can change numerical output; the optimiser never enables it for you.")
        ane_prefill = str(plan.options.get("anePrefill", "off"))
        if ane_prefill not in {"off", "tuned"}:
            raise ValueError("ANE prefill must be Off or a measured local recommendation.")
        ane_record = cap.get("aneTuning")
        ane_tuned = ane_prefill == "tuned"
        ane_cpu_enabled = False
        if ane_tuned:
            scanned_runtime = str(cap.get("runtimeVersion") or "")
            current_runtime = self.runtime.command_version(self.runtime.selected_binary("omlx"))
            kernel = self.runtime.omlx_qwen_kernel_status(self.runtime.selected_binary("omlx"))
            if not kernel.get("ready"):
                raise ValueError(str(
                    kernel.get("reason")
                    or "The selected oMLX installation has no verified native Qwen kernel."
                ))
            if current_runtime != scanned_runtime or not self.omlx.ane_record_valid(
                ane_record,
                str(cap.get("benchmarkModelFingerprint") or ""),
                scanned_runtime,
            ):
                raise ValueError(cap.get("aneReason") or "No trusted ANE tuning result matches this checkpoint, runtime, and Mac.")
            recommendation = ane_record["recommendation"]
            ane_cpu_enabled = recommendation.get("cpu_enabled") is True
            if ane_cpu_enabled:
                try:
                    model_path = Path(str(plan.model["path"])).resolve(strict=True)
                except (KeyError, OSError, RuntimeError) as error:
                    raise ValueError("The FP16 checkpoint moved after tuning. Rescan models before launch.") from error
                config = self.io.read_json(model_path / "config.json")
                cpu_profile = self.omlx.cpu_sharing_profile(model_path)
                ready, _status, weight_bytes = self.models.weight_completeness(model_path, config)
                cpu_memory = self.memory.ane_memory_readiness(
                    weight_bytes, self.memory.physical_memory_bytes(), cpu_assist=True,
                )
                if not ready:
                    raise ValueError("The FP16 checkpoint is no longer complete.")
                if not cpu_profile.get("eligible"):
                    raise ValueError(str(cpu_profile.get("reason") or "The FP16 tensor profile is no longer eligible."))
                if not cpu_memory.get("ready"):
                    raise ValueError(str(cpu_memory.get("reason") or "CPU sharing no longer has enough capacity."))
                if cpu_profile.get("profileFingerprint") != ane_record.get("cpuProfileFingerprint"):
                    raise ValueError("The FP16 tensor profile no longer matches the measured CPU-sharing result.")
        if ane_tuned and acceleration == "dflash":
            raise ValueError("DFlash 2 and tuned ANE prefill cannot share this oMLX engine. Choose one acceleration path.")
        if acceleration == "dflash":
            depth = self.runtime.safe_int(
                plan.options.get("depth"),
                int(cap.get("dflashBlockSize") or 8),
                1,
                int(cap.get("dflashMaxBlockSize") or cap.get("depthMax") or 8),
            )
        elif acceleration == "mtp":
            depth = self.runtime.safe_int(
                plan.options.get("depth"),
                int(cap.get("depth") or 1),
                1,
                int(cap.get("depthMax") or 8),
            )
        else:
            depth = 1
        burst = str(plan.options.get("burst", "balanced"))
        if burst not in {"off", "light", "balanced", "aggressive"}:
            raise ValueError("Invalid burst mode.")
        qwen4_flash = self.models.qwen_ple_record(plan.model)
        offload_options = self.omlx.expert_offload_options(plan.model, plan.options)
        if offload_options:
            if acceleration not in {"off", "auto"} or kv != "off" or ane_tuned:
                raise ValueError("oMLX expert offload requires MTP, DFlash and ANE prefill off, with full-precision QSA cache.")
            if not self.runtime.exact_omlx_version(self.runtime.omlx_plan_runtime_version(plan), self.policy.omlx.expert_offload_version):
                raise ValueError("Select the verified oMLX 0.7.0.dev2 runtime for expert SSD offload.")
            acceleration = "off"
            plan.options.update(acceleration="off", depth=1, memoryGuard="high",
                                expertResidentPercent=offload_options[0] * 100,
                                omlxMemoryGB=offload_options[1] / 1_000_000_000)
        memory_guard = str(plan.options.get("memoryGuard", "balanced"))
        if memory_guard not in {"balanced", "high"}:
            raise ValueError("Invalid oMLX memory mode.")
        if memory_guard == "high" and not qwen4_flash:
            raise ValueError(
                "High-memory mode is reserved for a verified Qwen3.8 Flash PLE mmap checkpoint."
            )
        if qwen4_flash and memory_guard != "high":
            raise ValueError(
                "Verified Qwen PLE mmap routes require High memory mode."
            )
        if qwen4_flash:
            if kv != "off":
                raise ValueError("Quantised KV is not qualified for the Qwen4 QSA cache; use full precision.")
            try:
                qwen4_path = Path(str(plan.model["path"])).resolve(strict=True)
            except (KeyError, OSError, RuntimeError) as error:
                raise ValueError("The Qwen4 checkpoint moved after scanning. Rescan models before launch.") from error
            qwen4_config = self.io.read_json(qwen4_path / "config.json")
            qwen4_ready, _qwen4_status, _qwen4_bytes = self.models.weight_completeness(qwen4_path, qwen4_config)
            live_qwen4_ple = self.omlx.ple_profile(
                qwen4_path, qwen4_config, qwen4_ready, self.runtime.command_version(self.runtime.selected_binary("omlx")),
            )
            scanned_qwen4_ple = plan.model.get("qwen4Ple")
            if (
                live_qwen4_ple.get("supported") is not True
                or not isinstance(scanned_qwen4_ple, dict)
                or any(
                    live_qwen4_ple.get(key) != scanned_qwen4_ple.get(key)
                    for key in (
                        "storage", "storageSource", "checkpointBytes", "pleBytes",
                        "rawResidentBytes", "residentBytes", "inventorySchema",
                        "inventoryFingerprint", "sourceFingerprint",
                        "configFingerprint", "indexFingerprint", "index",
                        "shardCount", "tensorCount", "pleLayerCount",
                        "pleShardCount", "pleTensorCount", "pleLayouts",
                    )
                )
            ):
                raise ValueError("The verified Qwen4 PLE mmap contract changed after scanning. Rescan models before launch.")
        if offload_options:
            live_experts = self.omlx.expert_offload_profile(qwen4_path, qwen4_config, live_qwen4_ple, self.runtime.omlx_plan_runtime_version(plan))
            if live_experts != plan.model.get("omlxExpertOffload"):
                raise ValueError("The expert checkpoint changed. Rescan models before launch.")
        chat_template_kwargs: dict[str, Any] = {}
        # The private relay strips client reasoning overrides. Keep engine values
        # as defaults so its native Pi summary requests can disable thinking.
        # Forcing these keys in oMLX silently overrides that recovery policy and
        # spends the entire summary allowance on the normal task thinking budget.
        forced_ct_kwargs: list[str] = []
        thinking_budget_enabled = False
        thinking_budget_tokens: int | None = None
        if plan.reasoning == "off":
            chat_template_kwargs["enable_thinking"] = False
        elif plan.reasoning != "auto":
            supported_efforts = list(plan.model.get("templateReasoningEfforts") or [])
            if plan.reasoning not in supported_efforts:
                raise ValueError("This model template does not expose the selected reasoning effort in oMLX.")
            chat_template_kwargs.update({"enable_thinking": True, "reasoning_effort": plan.reasoning})
            thinking_budget_enabled = True
            qualification_budget = plan.options.get("_qualificationThinkingBudgetTokens")
            if isinstance(qualification_budget, bool) or not isinstance(qualification_budget, int):
                qualification_budget = None
            thinking_budget_tokens = min(
                self.policy.thinking_budgets[plan.reasoning],
                max(1, plan.output // 2),
                qualification_budget if qualification_budget is not None else plan.output,
            )
            if thinking_budget_tokens < self.policy.thinking_budgets[plan.reasoning]:
                if qualification_budget is not None:
                    plan.warnings.append(
                        "Route qualification bounds thinking below each measured sample ceiling so a final answer has reserved space; the saved response limit is unchanged."
                    )
                else:
                    plan.warnings.append("The selected response ceiling is too small for the full reasoning budget; half is reserved for the answer/tool call.")
        if acceleration == "dflash":
            draft_quant = str(plan.options.get("dflashDraftQuant", "native"))
            verify_mode = str(plan.options.get("dflashVerify", "adaptive"))
            if draft_quant not in {"native", "q2", "q4", "q8"}:
                raise ValueError("DFlash draft precision must be native, Q8, Q4, or Q2.")
            if verify_mode not in {"adaptive", "dflash", "ddtree"}:
                raise ValueError("DFlash verification must be adaptive, DFlash, or DDTree.")
        adapter_python = None
        if ((plan.purpose == "session" or kv != "off") and acceleration == "dflash"
                and self.runtime.semantic_version_key(self.runtime.omlx_plan_runtime_version(plan)) == self.runtime.semantic_version_key("0.6.4")):
            adapter_python = self.runtime.omlx_runtime_python(plan.runtime_binary or self.runtime.required_binary("omlx"))
            if not adapter_python:
                raise ValueError("The oMLX DFlash session adapter needs its runtime Python.")
        return {
            "acceleration": acceleration,
            "kv": kv,
            "ane_prefill": ane_prefill,
            "ane_record": ane_record,
            "ane_tuned": ane_tuned,
            "ane_cpu_enabled": ane_cpu_enabled,
            "depth": depth,
            "burst": burst,
            "qwen4_flash": qwen4_flash,
            "offload_options": offload_options,
            "memory_guard": memory_guard,
            "chat_template_kwargs": chat_template_kwargs,
            "forced_ct_kwargs": forced_ct_kwargs,
            "thinking_budget_enabled": thinking_budget_enabled,
            "thinking_budget_tokens": thinking_budget_tokens,
            "adapter_python": adapter_python,
        }


    def build_omlx(self, plan: EnginePlan, cap: dict[str, Any]) -> None:
        base = plan.run_dir / "omlx"
        catalog = base / "models"
        served = self.io.slug(plan.model["name"], 38)
        link = catalog / served
        prepared = self._prepare_omlx_engine(plan, cap)
        acceleration = prepared["acceleration"]
        kv = prepared["kv"]
        ane_prefill = prepared["ane_prefill"]
        ane_record = prepared["ane_record"]
        ane_tuned = prepared["ane_tuned"]
        ane_cpu_enabled = prepared["ane_cpu_enabled"]
        depth = prepared["depth"]
        burst = prepared["burst"]
        qwen4_flash = prepared["qwen4_flash"]
        offload_options = prepared["offload_options"]
        memory_guard = prepared["memory_guard"]
        chat_template_kwargs = prepared["chat_template_kwargs"]
        forced_ct_kwargs = prepared["forced_ct_kwargs"]
        thinking_budget_enabled = prepared["thinking_budget_enabled"]
        thinking_budget_tokens = prepared["thinking_budget_tokens"]
        adapter_python = prepared["adapter_python"]
        catalog.mkdir(parents=True, exist_ok=True)
        if not link.exists():
            link.symlink_to(plan.model["path"], target_is_directory=True)
        api_key = self.io.token_urlsafe(24)
        secret_key = self.io.token_hex(32)
        benchmark_mode = plan.purpose in {"benchmark", "runtime-promotion", "route-check"}
        tuner_mode = plan.purpose == "ane-tune"
        isolated_measurement = benchmark_mode or tuner_mode
        if isolated_measurement:
            # Measurements talk to the engine directly rather than the Hub relay.
            forced_ct_kwargs = list(chat_template_kwargs)
        chunked_ane_prefill = tuner_mode or ane_tuned
        memory_settings = {
            "prefill_memory_guard": True,
            "memory_guard_tier": "custom" if memory_guard == "high" else "balanced",
            "memory_guard_custom_ceiling_gb": (
                offload_options[1] / 1024**3 if offload_options else
                self.policy.omlx.high_memory_ceiling_gib if memory_guard == "high" else 0.0
            ),
            "soft_threshold": (
                self.policy.omlx.high_memory_soft_threshold
                if memory_guard == "high" else 0.85
            ),
            "hard_threshold": (
                self.policy.omlx.high_memory_hard_threshold
                if memory_guard == "high" else 0.95
            ),
            "prefill_safe_zone_ratio": 0.8,
            "prefill_min_chunk_tokens": 32,
        }
        settings = {
            "version": "1.0",
            "server": {"host": "127.0.0.1", "port": plan.port, "log_level": "info", "cors_origins": [], "server_aliases": ["localhost", "127.0.0.1"], "sse_keepalive_mode": "chunk", "auto_start_on_launch": False, "burst_decode_mode": burst, "preserve_mid_system_cache": not isolated_measurement},
            "model": {"model_dirs": [str(catalog)], "model_dir": str(catalog), "model_fallback": False, "hide_helper_models": False},
            "memory": memory_settings,
            "scheduler": {"max_concurrent_requests": 1, "embedding_batch_size": 8, "chunked_prefill": chunked_ane_prefill, "prefill_step_size": self.policy.omlx.ane_sequence_length, "prefill_priority": "speed" if chunked_ane_prefill else "context"},
            "cache": {"enabled": not isolated_measurement, "hot_cache_only": False, "ssd_cache_dir": str(self.paths.state_directory() / "cache" / "omlx"), "ssd_cache_max_size": "40GB", "hot_cache_max_size": "0", "initial_cache_blocks": 256},
            "auth": {"api_key": api_key, "secret_key": secret_key, "skip_api_key_verification": False, "sub_keys": []},
            # These are only context/output fallbacks. Per-model sampler defaults
            # below come from generation_config.json, while explicit request
            # parameters still win because force_sampling remains false.
            "sampling": {"max_context_window": plan.context, "max_context_window_policy": plan.context, "max_tokens": plan.output},
            "logging": {"log_dir": str(plan.run_dir / "logs"), "retention_days": 7},
        }
        self.io.atomic_json(base / "settings.json", settings)
        per_model_settings = {
            "max_context_window": plan.context,
            "max_tokens": plan.output,
            **dict(plan.model.get("defaultSampling") or {}),
            "force_sampling": False,
            "chat_template_kwargs": chat_template_kwargs or None,
            "forced_ct_kwargs": forced_ct_kwargs,
            "preserve_thinking": plan.reasoning != "off",
            "thinking_budget_enabled": thinking_budget_enabled,
            "thinking_budget_tokens": thinking_budget_tokens,
            # Flash-Next's PLE is the large N-gram table. Pin mmap mode instead of
            # relying on macOS swap or on oMLX's last-minute admission fallback.
            "qwen4_ple_ssd_offload": qwen4_flash,
            "moe_expert_offload_enabled": bool(offload_options),
            "moe_expert_offload_resident_fraction": offload_options[0] if offload_options else 0.25,
            "vlm_mtp_enabled": False if offload_options else acceleration == "mtp",
            "turboquant_kv_enabled": kv != "off",
            "turboquant_kv_bits": {"q8": 8, "q6": 6, "q4": 4}.get(kv, 4),
            "turboquant_skip_last": True,
            "mtp_enabled": acceleration == "mtp",
            "mtp_num_draft_tokens": depth if acceleration == "mtp" else None,
            "dflash_enabled": acceleration == "dflash",
            "trust_remote_code": False,
            "is_default": True,
        }
        if qwen4_flash:
            plan.warnings.append(
                "Qwen3.8 Flash-Next keeps its PLE N-gram table SSD-backed through oMLX mmap; the launcher does not treat macOS swap as model offload."
            )
        if offload_options:
            plan.warnings.append(f"Expert SSD offload keeps {offload_options[0]:.1%} of experts per layer in RAM, within a {offload_options[1] / 1e9:g} GB process ceiling; all routed experts remain available. MTP is off.")
        elif memory_guard == "high":
            plan.warnings.append(
                "Qwen high-memory mode uses a 45 GiB oMLX process ceiling. Sessions separately checks the selected context, current memory headroom, and temporary Apple GPU wired-memory limit."
            )
        if ane_tuned:
            recommendation = ane_record["recommendation"]
            per_model_settings.update({
                "qwen35_ane_prefill_enabled": True,
                "qwen35_ane_prefill_sequence_length": self.policy.omlx.ane_sequence_length,
                "qwen35_ane_prefill_fraction": float(recommendation["mlp_fraction"]),
                "qwen35_ane_prefill_dual_ane": True,
                "qwen35_ane_prefill_gdn": bool(recommendation.get("gdn_enabled")),
                "qwen35_ane_prefill_gdn_fraction": recommendation.get("gdn_fraction"),
                "qwen35_ane_prefill_cpu_enabled": ane_cpu_enabled,
                "qwen35_ane_prefill_cpu_fraction": float(recommendation.get("cpu_fraction") or 0.0) if ane_cpu_enabled else 0.0,
                "qwen35_ane_prefill_cpu_down_fraction": float(recommendation.get("cpu_down_fraction") or 0.0) if ane_cpu_enabled else 0.0,
                "qwen35_ane_prefill_cpu_gdn_fraction": float(recommendation.get("cpu_gdn_fraction") or 0.0) if ane_cpu_enabled else 0.0,
                "qwen35_ane_prefill_cpu_threads": int(recommendation.get("cpu_threads") or 8) if ane_cpu_enabled else 8,
                "qwen35_ane_prefill_cpu_shared_resource": bool(recommendation.get("cpu_shared_resource")) if ane_cpu_enabled else False,
            })
            plan.warnings.append(
                "ANE prefill is an explicit experimental opt-in: oMLX requantises the ANE slice to INT8, so this path is approximate even though local execution and speed were measured."
            )
            if ane_cpu_enabled:
                plan.warnings.append(
                    "The measured split also uses CPU sharing from this exact all-FP16 checkpoint clone; the launcher rechecked its tensor profile and 16 GiB capacity reserve before launch."
                )
        if acceleration == "dflash":
            draft_quant = str(plan.options.get("dflashDraftQuant", "native"))
            verify_mode = str(plan.options.get("dflashVerify", "adaptive"))
            if draft_quant not in {"native", "q2", "q4", "q8"}:
                raise ValueError("DFlash draft precision must be native, Q8, Q4, or Q2.")
            if verify_mode not in {"adaptive", "dflash", "ddtree"}:
                raise ValueError("DFlash verification must be adaptive, DFlash, or DDTree.")
            quant_bits = int(draft_quant[1:]) if draft_quant.startswith("q") else None
            per_model_settings.update({
                "dflash_draft_model": str(Path(str(cap["dflashDraftPath"])).resolve()),
                "dflash_draft_quant_enabled": quant_bits is not None,
                "dflash_draft_quant_weight_bits": quant_bits,
                "dflash_draft_quant_activation_bits": 16 if quant_bits is not None else None,
                "dflash_draft_quant_group_size": 64 if quant_bits is not None else None,
                "dflash_draft_sink_size": 0,
                "dflash_block_size": depth,
                "dflash_verify_mode": verify_mode,
            })
            if plan.purpose == "session" and plan.client in {"pi", "omp"}:
                # Keep one reusable conversation prefix. Native generation snapshots
                # adopt resident arrays; the live memory guard still owns admission.
                per_model_settings["dflash_in_memory_cache_max_entries"] = 1
                snapshot_estimate = self.memory.launch_estimate(
                    {"backend": "omlx", "context": plan.context, "options": plan.options},
                    plan.model, {},
                )
                # A full 128K Qwen prefix has 8 GiB of FP16 KV before recurrent
                # state and hidden features. The upstream 8 GiB logical cache cap
                # would evict it even when native physical admission permits it.
                # This limit retains one snapshot; it neither allocates memory nor
                # changes the process/Metal ceiling or prefill admission checks.
                per_model_settings["dflash_in_memory_cache_max_bytes"] = max(
                    8 * 1024**3,
                    int(snapshot_estimate["kvCacheBytes"]) + 1024**3
                    if snapshot_estimate["geometryReady"] else 0,
                )
            if quant_bits is not None:
                plan.warnings.append(
                    "Draft quantisation saves memory but can change DFlash acceptance and speed; target verification still owns the output."
                )
            if not self.runtime.recommended_dflash_runtime(str(cap.get("dflashRuntimeVersion") or "")):
                plan.warnings.append(
                    f"This runtime has first-generation DFlash 2 support; {self.policy.omlx.recommended_dflash_runtime} or later is recommended."
                )
            elif "rc" in str(cap.get("dflashRuntimeVersion") or "").lower():
                plan.warnings.append("DFlash 2 is running through an oMLX release candidate; keep AR/MTP available as a fallback.")
        model_settings = {
            "version": 1,
            "models": {
                served: per_model_settings,
            },
        }
        self.io.atomic_json(base / "model_settings.json", model_settings)
        plan.model["servedId"] = served
        plan.secrets["apiKey"] = api_key
        omlx_binary = plan.runtime_binary or self.runtime.required_binary("omlx")
        plan.engine_argv = [omlx_binary, "serve", "--base-path", str(base), "--model-dir", str(catalog), "--host", "127.0.0.1", "--port", str(plan.port), "--max-concurrent-requests", "1"]
        plan.engine_env = {"OMLX_BASE_PATH": str(base), "OMLX_API_KEY": api_key}
        # Keep the installed runtime immutable. Only normal DFlash sessions on
        # this audited API version use the local streaming/admission adapter.
        if ((plan.purpose == "session" or kv != "off") and acceleration == "dflash"
                and self.runtime.semantic_version_key(self.runtime.omlx_plan_runtime_version(plan)) == self.runtime.semantic_version_key("0.6.4")):
            python = adapter_python
            plan.engine_argv[:1] = [python, str(self.paths.app_directory() / "omlx_hub_runtime.py")]
            plan.engine_env.update({
                "LLM_LAUNCHER_OMLX_CONTEXT": str(plan.context),
                "LLM_LAUNCHER_OMLX_PREVIEW": str(plan.run_dir / "tool-preview.json"),
                "LLM_LAUNCHER_DFLASH_KV": kv,
            })
            plan.secrets["omlxNativeContextGuard"] = True


    def build_lmstudio(self, plan: EnginePlan, cap: dict[str, Any]) -> None:
        acceleration = str(plan.options.get("acceleration", "auto"))
        mtp_controls = {
            "depth": 1,
            "mtpMinTokens": self.policy.launch.lmstudio_mtp_min_tokens,
            "mtpMinContinueProbability": self.policy.launch.lmstudio_mtp_probability,
        }
        if acceleration not in {"auto", "off", "mtp"}:
            raise ValueError("Invalid LM Studio acceleration mode.")
        if acceleration == "mtp" and not cap.get("mtp"):
            raise ValueError(cap.get("mtpReason") or "MTP is not verified for this LM Studio model.")
        if acceleration == "mtp":
            mtp_controls = self.lmstudio_mtp_controls(plan.options, cap)
            plan.options.update(mtp_controls)
        gpu = str(plan.options.get("gpu", "max"))
        if gpu not in {"max", "off"}:
            raise ValueError("GPU offload must be max or off.")
        parallel = self.runtime.safe_int(plan.options.get("parallel"), 1, 1, 16)
        served = f"llm-launcher-{plan.run_id[:8]}"
        argv = [self.runtime.required_binary("lms"), "load", plan.model["lmKey"], "-y", "--identifier", served, "--context-length", str(plan.context), "--gpu", gpu, "--parallel", str(parallel)]
        if acceleration == "mtp":
            argv.extend([
                "--speculative-draft-mtp",
                "--speculative-draft-max-tokens", str(mtp_controls["depth"]),
                "--speculative-draft-min-tokens", str(mtp_controls["mtpMinTokens"]),
                "--speculative-draft-min-continue-probability",
                f"{mtp_controls['mtpMinContinueProbability']:.2f}",
            ])
        elif acceleration == "off":
            argv.append("--no-speculative-draft-mtp")
        plan.model["servedId"] = served
        plan.engine_argv = argv
        plan.engine_env = {}
        plan.warnings.append("LM Studio is a shared service. Stop unloads only this launcher's model and leaves your LM Studio server running.")


    def _mtplx_hub_memory_python(self, plan: EnginePlan, cap: dict[str, Any]) -> Path | None:
        """Apply the reviewed 48 GiB Mac policy to dense Qwen 27B sessions."""
        if plan.purpose in {"benchmark", "route-check"}:
            return
        version = str(cap.get("runtimeVersion") or "").strip()
        if not re.fullmatch(r"(?:mtplx\s+)?2\.11\.2(?:\s+\(2\.11\.2\))?", version, re.I):
            return
        config = self.io.read_json(Path(plan.model["path"]) / "config.json")
        text_config = config.get("text_config", config)
        if not isinstance(text_config, dict):
            return
        if (
            self.models.normalized_model_type(config.get("model_type")) not in {"qwen3_5", "qwen3_8"}
            or any(text_config.get(key) != value for key, value in self.policy.mtplx.dense_geometry.items())
            or any(self.runtime.safe_int(text_config.get(key), 0, 0, 1_000_000) > 1 for key in ("num_experts", "num_local_experts", "n_routed_experts"))
            or self.memory.physical_memory_bytes() != 48 * 1024**3
        ):
            return
        python = self.runtime.omlx_runtime_python(self.runtime.required_binary("mtplx"))
        if python is None:
            raise ValueError("The MTPLX runtime Python is missing; repair the runtime before launching.")
        return Path(python)


    def configure_mtplx_hub_memory(self, plan: EnginePlan, cap: dict[str, Any]) -> None:
        """Materialize the reviewed memory adapter after its read-only check."""
        python = self._mtplx_hub_memory_python(plan, cap)
        if python is None:
            return
        plan.engine_argv[:1] = [str(python), str(self.paths.app_directory() / "mtplx_hub_runtime.py")]
        plan.engine_env.update({
            "MTPLX_MEMORY_LIMIT_BYTES": str(40 * 1024**3),
            # One 128K target+MTP snapshot fits without the old 8 GiB switch to
            # live-ref-only storage. A bounded total bank prevents accumulation.
            "MTPLX_SESSION_BANK_PER_SESSION_BYTES": str(12 * 1024**3),
            # Auto keeps the engine's pressure-sensitive ceiling active; the
            # adapter additionally clamps the bank's absolute maximum to 12 GiB.
            "MTPLX_SESSION_BANK_MAX_BYTES": "auto",
            "MTPLX_PREFILL_ADMISSION_SHED": "1",
            "MTPLX_MEMORY_PRESSURE_GUARD": "1",
        })
        plan.options["mtplxMemoryPolicy"] = "hub-prefill-1"


    def _mtplx_baseline_required(self, plan: EnginePlan, cap: dict[str, Any], operator_route: str,
            acceleration: str, profile: str) -> bool:
        """Revalidate the exact inverse-baseline receipt before key/template IO."""
        if operator_route == self.policy.mtplx.candidate_route:
            return False
        elif (
            plan.purpose == "benchmark"
            and plan.context >= self.policy.mtplx.minimum_operator_context
            and acceleration == "mtp"
            and profile == "turbo"
        ):
            receipt = self.mtplx.long_context_contract(
                plan.model, cap,
                runtime_version=str(cap.get("runtimeVersion") or ""),
            )
            advertised = cap.get("longContext2111")
            baseline_binding = plan.options.get("_mtplxOperatorBaselineContractId")
            direct_contract_test = bool(
                isinstance(advertised, dict) and "environment" in advertised
            )
            baseline_capable = bool(
                isinstance(advertised, dict)
                and (advertised.get("ready") is True or direct_contract_test)
            )
            if baseline_capable:
                baseline_verified = bool(
                    receipt is not None
                    and self.mtplx.capability_matches(advertised, receipt)
                    and (
                        direct_contract_test
                        or (
                            isinstance(baseline_binding, str)
                            and secrets.compare_digest(
                                baseline_binding, str(receipt["contractId"]),
                            )
                        )
                    )
                )
                if not baseline_verified:
                    raise ValueError(
                        "The MTPLX 2.11.1 inverse baseline lost its exact receipt before launch. "
                        "Nothing was measured; rescan models and retry Calibration."
                    )
                return True
        return False


    def build_mtplx(self, plan: EnginePlan, cap: dict[str, Any]) -> None:
        acceleration = str(plan.options.get("acceleration", "auto"))
        profile = str(plan.options.get("profile", cap.get("profile", "sustained")))
        depth = self.runtime.safe_int(plan.options.get("depth"), int(cap.get("depth", 3)), 1, 8)
        operator_route = self.mtplx.operator_route(plan, cap)
        plan.options["mtplxOperatorRoute"] = operator_route
        if acceleration not in {"auto", "off", "mtp"}:
            raise ValueError("Invalid MTPLX acceleration mode.")
        if acceleration == "mtp" and not cap.get("mtp"):
            raise ValueError(cap.get("mtpReason") or "MTP is not verified by this artifact.")
        if acceleration == "mtp":
            depth = self.runtime.safe_int(depth, 1, 1, int(cap.get("depthMax") or 1))
        if profile not in {"stable", "performance-cold", "sustained", "turbo", "exact"}:
            raise ValueError("Invalid MTPLX profile.")
        kv = str(plan.options.get("kv", "off"))
        if kv not in {"off", "q8", "q4"}:
            raise ValueError("Invalid MTPLX KV mode.")
        if kv != "off":
            plan.warnings.append("Paged KV quantisation can change numerical output and may disable fast paths; the optimiser preserves your selected value.")
        fan = str(plan.options.get("fan", "smart"))
        if fan not in {"default", "smart", "max"}:
            raise ValueError("Invalid fan mode.")
        inverse_baseline = self._mtplx_baseline_required(plan, cap, operator_route, acceleration, profile)
        self._mtplx_hub_memory_python(plan, cap)
        reasoning_mode = "off" if plan.reasoning == "off" else ("auto" if plan.reasoning == "auto" else "on")
        reasoning_effort = plan.reasoning if plan.reasoning in self.policy.thinking_budgets else "auto"
        served = f"llm-launcher-{plan.run_id[:8]}"
        key_file = plan.run_dir / "mtplx-api-key"
        key_file.write_text(self.io.token_urlsafe(32) + "\n", encoding="utf-8")
        key_file.chmod(0o600)
        argv = [
            self.runtime.required_binary("mtplx"), "serve", "--yes", "--model", plan.model["path"],
            "--model-id", served, "--profile", profile, "--host", "127.0.0.1",
            "--port", str(plan.port), "--context-window", str(plan.context),
            "--max-tokens", str(plan.output), "--paged-kv-quantization", kv,
            "--scheduler-mode", "serial", "--batching-preset", "latency",
            "--ssd-session-cache", "off" if plan.purpose in {"benchmark", "route-check"} else "on", "--fan-mode", fan,
            "--reasoning", reasoning_mode, "--reasoning-effort", reasoning_effort,
            "--preserve-thinking", "auto",
            "--api-key-file", str(key_file),
        ]
        if acceleration == "mtp":
            argv.extend(["--mtp", "--load-mtp", "--generation-mode", "mtp", "--depth", str(depth)])
        elif acceleration == "off":
            argv.extend(["--no-mtp", "--no-load-mtp", "--generation-mode", "ar"])
        else:
            argv.extend(["--generation-mode", "auto"])
        reasoning_template = self.models.preserved_thinking_template(plan.model["path"])
        if reasoning_template is not None:
            template_path = plan.run_dir / "qwopus-preserved-thinking.jinja"
            template_path.write_text(reasoning_template, encoding="utf-8")
            argv.extend(["--chat-template-profile", "tokenizer", "--chat-template-path", str(template_path)])
            argv.extend(["--tool-prompt-mode", "native"])
            plan.options["reasoningHistory"] = "scoped"
        plan.model["servedId"] = served
        plan.secrets["apiKey"] = key_file.read_text(encoding="utf-8").strip()
        plan.engine_argv = argv
        # MTPLX 2.8.x otherwise compacts historical coding-agent tool results very
        # aggressively. Keep ordinary source reads intact while still allowing
        # genuinely large results to compact, and disable the old coercive
        # read-only convergence contracts. These are server-side context policies;
        # they do not reduce reasoning, context, sampling quality, or model size.
        plan.engine_env = {
            "MTPLX_TOOL_RESULT_COMPACT_THRESHOLD_CHARS": "32768",
            "MTPLX_ACTIVE_TOOL_RESULT_COMPACT_THRESHOLD_CHARS": "32768",
            "MTPLX_ACTIVE_READ_INSPECTION_COMPACT_THRESHOLD_CHARS": "32768",
            "MTPLX_ACTIVE_READ_COMPACT_HEAD_LINES": "4096",
            "MTPLX_ACTIVE_READ_COMPACT_TAIL_LINES": "0",
            "MTPLX_ACTIVE_READ_COMPACT_MAX_LINES": "4096",
            "MTPLX_PI_CONVERGENCE_AFTER_TOOLS": "0",
            "MTPLX_READ_ONLY_INSPECTION_FORCE_ANSWER_AFTER_TOOLS": "0",
            # Never inherit an explicit overcommit from a parent shell. The user
            # previously approved only launcher-admitted memory plans, and MTPLX
            # 2.11.1 otherwise accepts MTPLX_ALLOW_SWAP=1 as an operator override.
            "MTPLX_ALLOW_SWAP": "0",
            # Keep these measured-dark experiments off so an inherited shell
            # setting cannot opt a normal route into an unqualified execution lane.
            "MTPLX_ASYNC_AR": "0",
            "MTPLX_FUSED_MOE_VERIFY": "0",
        }
        if plan.context > self.policy.mtplx.compiled_verify_fence:
            # The turbo profile fences the compiled verify step at 32,768 tokens, so
            # every speculative verify above that ran the eager path. A 17 Sep 2026
            # local A/B on this Mac at a 112,881-token prompt (profiles unchanged,
            # paged KV q8, depth 3) took decode from 4.56 to 10.05 tok/s with a
            # byte-identical greedy continuation once the fence covered the window.
            # Evidence: bench/results/20260917-175916-27b-mtplx-cv131k.json.
            plan.engine_env["MTPLX_COMPILED_VERIFY_MAX_CONTEXT"] = str(plan.context)
        if operator_route == self.policy.mtplx.candidate_route:
            plan.engine_env.update(self.policy.mtplx.candidate_environment)
        elif inverse_baseline:
            plan.engine_env.update(self.policy.mtplx.baseline_environment)
        if reasoning_effort in self.policy.thinking_budgets:
            effective_budget = min(self.policy.thinking_budgets[reasoning_effort], max(1, plan.output // 2))
            plan.engine_env["MTPLX_THINKING_BUDGET"] = str(effective_budget)
            if effective_budget < self.policy.thinking_budgets[reasoning_effort]:
                plan.warnings.append("The selected response ceiling is too small for the full reasoning budget; half is reserved for the answer/tool call.")
        self.configure_mtplx_hub_memory(plan, cap)


    def _uzu_engine_argv(self, 
        plan: EnginePlan, binary: Path, api_key_file: Path,
    ) -> list[str]:
        return [
            str(self.policy.uzu.sandbox_executable),
            "-p", self.policy.uzu.network_sandbox_profile,
            str(binary),
            "server",
            "--model", self.policy.uzu.model_id,
            "--host", "127.0.0.1",
            "--port", str(plan.port),
            "--api-key-file", str(api_key_file),
            "--context-limit", str(plan.context),
            "--max-output-tokens", str(plan.output),
            "--prefix-cache",
        ]


    def _validated_uzu_route(self, 
        plan: EnginePlan, cap: dict[str, Any], *, verify_argv: bool = False,
        opened_revision: OpenExecutableRevision | None = None,
    ) -> tuple[Path, dict[str, Any], dict[str, Any], tuple[Any, ...]]:
        """Rebind launch to the exact model receipts and safe runtime bytes."""
        if plan.model.get("uzuNative") is not True:
            raise ValueError("This model is not a pinned Uzu-native artifact.")
        binary_value = plan.runtime_binary or self.runtime.selected_binary("mirai")
        runtime = self.uzu.runtime_contract(binary_value, opened_revision=opened_revision)
        if runtime.get("ready") is not True:
            raise ValueError(str(runtime.get("reason") or "A verified memory-safe Uzu runtime is required."))
        if any(runtime.get(field) is not True for field in (
            "binaryIdentityPinned", "nativeBearerAuthentication", "oneUseApiKeyFile",
            "nativeContextLimit", "nativeOutputLimit", "boundedContextReady",
        )) or runtime.get("nativeBoundaryContractId") != self.policy.uzu.boundary_contract_id:
            raise ValueError(
                "The selected Uzu binary does not match the launcher's native auth/context/output contract."
            )
        if not self.uzu.listener_protection_ready(runtime):
            raise ValueError(
                "Direct access to Uzu's raw loopback listener is not protected; "
                "the bounded launcher relay cannot be trusted."
            )
        try:
            binary = (
                opened_revision.path
                if opened_revision is not None else
                Path(str(binary_value)).expanduser().resolve(strict=True)
            )
            model_path = Path(str(plan.model.get("path") or "")).expanduser().resolve(strict=True)
        except OSError as error:
            raise ValueError("The Uzu executable or model cache moved after the model scan.") from error
        cache = self.uzu.model_cache_contract()
        if cache is None or cache.get("ready") is not True:
            raise ValueError(str((cache or {}).get("reason") or "The pinned Uzu model is incomplete."))
        try:
            current_model_path = Path(str(cache["path"])).resolve(strict=True)
        except OSError as error:
            raise ValueError("The pinned Uzu model cache moved after validation.") from error
        scanned_fingerprint = str(cap.get("benchmarkModelFingerprint") or "")
        current_fingerprint = str(cache.get("fingerprint") or "")
        if (
            model_path != current_model_path
            or not scanned_fingerprint
            or not current_fingerprint
            or not secrets.compare_digest(scanned_fingerprint, current_fingerprint)
            or cap.get("modelRegistryId") != self.policy.uzu.model_id
            or cap.get("modelCommit") != self.policy.uzu.model_commit
            or cap.get("modelToolchainVersion") != self.policy.uzu.toolchain_version
        ):
            raise ValueError("The pinned Uzu model files or catalog receipt changed. Rescan models.")
        runtime_sha = str(runtime.get("binary", {}).get("sha256") or "")
        scanned_runtime = cap.get("runtimeIdentity")
        scanned_system = cap.get("qualificationSystemContract")
        if (
            not isinstance(scanned_runtime, dict)
            or not isinstance(scanned_system, dict)
            or scanned_runtime.get("nativeBoundaryContractId") != self.policy.uzu.boundary_contract_id
            or scanned_runtime.get("nativeBearerAuthentication") is not True
            or scanned_runtime.get("oneUseApiKeyFile") is not True
            or scanned_runtime.get("nativeContextLimit") is not True
            or scanned_runtime.get("nativeOutputLimit") is not True
            or scanned_runtime.get("binaryIdentityPinned") is not True
            or scanned_runtime.get("networkSandbox") is not True
            or scanned_runtime.get("memorySafetyBlocked") is not False
            or not secrets.compare_digest(
                str(scanned_runtime.get("binary", {}).get("sha256") or ""), runtime_sha,
            )
            or scanned_runtime.get("binary", {}).get("size")
            != runtime.get("binary", {}).get("size")
            or scanned_runtime.get("upstreamCommit") != runtime.get("upstreamCommit")
            or scanned_runtime.get("sourcePatchSha256") != runtime.get("sourcePatchSha256")
            or scanned_system.get("rawListenerProtected") is not True
            or scanned_system.get("nativeBoundaryContractId") != self.policy.uzu.boundary_contract_id
            or scanned_system.get("nativeBearerAuthentication") is not True
            or scanned_system.get("oneUseApiKeyFile") is not True
            or scanned_system.get("nativeContextLimit") is not True
            or scanned_system.get("nativeOutputLimit") is not True
        ):
            raise ValueError("The hardened Uzu runtime contract changed after the model scan. Rescan models.")
        if plan.context not in self.policy.uzu.context_windows:
            choices = ", ".join(f"{value:,}" for value in self.policy.uzu.context_windows)
            raise ValueError(f"The first Uzu qualification permits only these bounded contexts: {choices}.")
        options = self.validated_profile_options("uzu", plan.model, cap, plan.options)
        key_identity: tuple[Any, ...] | None = None
        offline_catalog_identity: str | None = None
        if verify_argv:
            offline_catalog_identity = self.uzu.validated_offline_catalog(cache)
            api_key_file = self._validated_uzu_api_key_file(plan)
            expected = self._uzu_engine_argv(plan, binary, api_key_file)
            if (
                plan.engine_argv != expected
                or plan.engine_env
                or any(key.startswith("DYLD_") for key in plan.engine_env)
            ):
                raise ValueError("The fixed local-only Uzu launch contract changed after validation.")
            key_identity = self.models.strong_path_identity(api_key_file)
        return binary, runtime, cache, (
            runtime_sha,
            current_fingerprint,
            key_identity,
            str(runtime.get("binary", {}).get("id") or ""),
            offline_catalog_identity,
        )


    def build_uzu(self, plan: EnginePlan, cap: dict[str, Any]) -> None:
        binary, _runtime, _cache, _identities = self._validated_uzu_route(plan, cap)
        self.uzu.ensure_offline_catalog(_cache)
        options = self.validated_profile_options("uzu", plan.model, cap, plan.options)
        plan.options.update(options)
        plan.model["servedId"] = self.policy.uzu.model_id
        api_key_file, _api_key = self._create_plan_api_key_file(
            plan, backend="uzu", filename=self.policy.uzu.api_key_filename, label="Uzu",
        )
        plan.engine_argv = self._uzu_engine_argv(plan, binary, api_key_file)
        plan.engine_env = {}
        plan.warnings.extend([
            "Uzu owns the bundled DFlash draft and Weaver verification tree; the launcher does not replace them with an AR label or expose unsafe speculative overrides.",
            "The Uzu process is wrapped in a macOS sandbox that denies every outbound connection, including telemetry and automatic downloads; only loopback serving remains available.",
            f"The raw server requires a one-use bearer key and natively enforces this run's {plan.context:,}-token context and {plan.output:,}-token output ceilings; the relay adds defense in depth and the engine has a {self.policy.uzu.process_memory_ceiling_bytes / 1024**3:.0f} GiB process-group safety ceiling.",
        ])


    def validate_uzu_launch_boundary(self, plan: EnginePlan) -> tuple[Any, ...]:
        cap = plan.model.get("backends", {}).get("uzu")
        if not isinstance(cap, dict):
            raise ValueError("The Uzu launch capability is missing. Rescan models.")
        _binary, _runtime, _cache, identities = self._validated_uzu_route(
            plan, cap, verify_argv=True,
        )
        return identities


    def confirm_uzu_launch_identities(self, plan: EnginePlan, expected: tuple[Any, ...]) -> None:
        current = self.validate_uzu_launch_boundary(plan)
        if not expected or current != expected:
            raise ValueError("The Uzu executable or model receipts changed before launch.")


    def _uzu_inherited_executable_path(self, opened: OpenExecutableRevision) -> str | None:
        """Return an executable fd path only when the host exposes one as executable.

        macOS currently exposes `/dev/fd/N` without execute permission, so its
        `sandbox-exec` rejects that path.  Keeping this feature check here permits
        a descriptor-exec handoff on a host that genuinely supports it without
        claiming that current macOS has `fexecve`/`execveat` semantics.
        """
        candidate = Path("/dev/fd") / str(opened.fd)
        try:
            candidate_details = candidate.stat()
            descriptor_details = os.fstat(opened.fd)
        except OSError:
            return None
        if (
            candidate_details.st_ino != descriptor_details.st_ino
            or candidate_details.st_size != descriptor_details.st_size
            or candidate_details.st_mtime_ns != descriptor_details.st_mtime_ns
            or not os.access(candidate, os.X_OK)
        ):
            return None
        return str(candidate)


    def prepare_uzu_executable_launch(self, 
        plan: EnginePlan, expected: tuple[Any, ...],
    ) -> UzuExecutableLaunch:
        """Retain the authoritative Uzu runtime fd through immediate process spawn.

        This pins the launcher-managed executable only. The separately validated
        model-cache receipts remain path based and are not represented as fd-pinned
        by this handoff.
        """
        binary_value = plan.runtime_binary or self.runtime.selected_binary("mirai")
        opened = self.uzu.open_executable(binary_value)
        try:
            cap = plan.model.get("backends", {}).get("uzu")
            if not isinstance(cap, dict):
                raise ValueError("The Uzu launch capability is missing. Rescan models.")
            _binary, _runtime, _cache, current = self._validated_uzu_route(
                plan, cap, verify_argv=True, opened_revision=opened,
            )
            if not expected or current != expected:
                raise ValueError("The Uzu executable or model receipts changed before launch.")
            self.uzu.confirm_open_executable(opened)
            argv = list(plan.engine_argv)
            executable_path = self._uzu_inherited_executable_path(opened)
            if executable_path is None:
                # Current macOS cannot exec /dev/fd/N. The owner-only path is
                # checked against this retained inode immediately before and after
                # Popen; this narrows but cannot eliminate a malicious same-user
                # rename race. Do not describe this fallback as race-free.
                return UzuExecutableLaunch(opened, argv, (), False)
            if len(argv) < 4 or argv[3] != str(opened.path):
                raise ValueError("The fixed Uzu executable position changed before launch.")
            argv[3] = executable_path
            return UzuExecutableLaunch(opened, argv, (opened.fd,), True)
        except Exception:
            opened.close()
            raise


    def _verified_ssd_model_path(self, plan: EnginePlan, cap: dict[str, Any]) -> Path:
        """Rebind an SSD route to the exact scanned artifact before starting a server."""
        try:
            model_path = Path(str(plan.model.get("path") or "")).expanduser().resolve(strict=True)
            scanned_path = Path(str(cap.get("modelPath") or "")).expanduser().resolve(strict=True)
        except OSError as error:
            raise ValueError("The SSD-streamed model moved after the model scan. Rescan models.") from error
        if model_path != scanned_path or not model_path.is_dir():
            raise ValueError("The SSD-streamed model changed after the model scan. Rescan models.")
        if cap.get("runnable") is not True or cap.get("ssdStreaming") is not True:
            raise ValueError(str(cap.get("reason") or "This model is not accepted by the selected SSD runtime."))
        config = self.io.read_json(model_path / "config.json")
        if model_path.name.endswith(".gturbo"):
            config = {
                **self.io.read_json(model_path / "tokenizer" / "config.json"),
                **self.io.read_json(model_path / "manifest.json"),
            }
        artifact_fingerprint = self.models.artifact_fingerprint(model_path, config)
        if (
            not artifact_fingerprint
            or not secrets.compare_digest(
                artifact_fingerprint, str(cap.get("artifactFingerprint") or ""),
            )
        ):
            raise ValueError("The SSD-streamed model files changed after the model scan. Rescan models.")
        return model_path


    def build_swiftlm(self, plan: EnginePlan, cap: dict[str, Any]) -> None:
        model_path = self._verified_ssd_model_path(plan, cap)
        options = self.validated_profile_options("swiftlm", plan.model, cap, plan.options)
        plan.options.update(options)
        served = f"llm-launcher-{self.io.slug(plan.model['name'], 34)}-{plan.run_id[:8]}"
        binary = plan.runtime_binary or self.runtime.selected_binary("swiftlm")
        if not binary:
            raise ValueError("SwiftLM is not installed.")
        plan.engine_argv = [
            binary,
            "--model", str(model_path),
            "--host", "127.0.0.1",
            "--port", str(plan.port),
            "--max-tokens", str(plan.output),
            "--prefill-size", str(options["prefillSize"]),
            "--stream-experts",
        ]
        native_top_k = int(options["nativeExpertTopK"])
        plan.engine_env = (
            {"SWIFTLM_TOP_K": str(native_top_k)} if native_top_k > 0 else {}
        )
        plan.model["servedId"] = served
        plan.warnings.extend([
            "SwiftLM will stream routed MoE experts from SSD. Cold turns include disk reads; warm turns can reuse the operating-system file cache.",
            "The launcher keeps native expert routing and disables speculative decoding so the SSD comparison does not trade model fidelity for speed.",
        ])


    def build_mference(self, plan: EnginePlan, cap: dict[str, Any]) -> None:
        model_path = self._verified_ssd_model_path(plan, cap)
        if not model_path.name.endswith(".gturbo"):
            raise ValueError("Mference requires a verified .gturbo model bundle.")
        self.validate_runtime_context("mference", plan.context)
        options = self.validated_profile_options("mference", plan.model, cap, plan.options)
        plan.options.update(options)
        served = f"llm-launcher-{self.io.slug(plan.model['name'], 34)}-{plan.run_id[:8]}"
        binary = plan.runtime_binary or self.runtime.selected_binary("mference")
        if not binary:
            raise ValueError("Mference is not installed.")
        argv = [
            binary,
            "--model", str(model_path),
            "--model-id", served,
            "--port", str(plan.port),
            "--max-context", str(plan.context),
            "--queue-limit", str(options["queueLimit"]),
        ]
        if options["promptCacheMode"] == "off":
            argv.extend(["--prompt-cache-mode", "off"])
        plan.model["servedId"] = served
        plan.engine_argv = argv
        plan.engine_env = {}
        plan.warnings.extend([
            "Mference will stream routed experts from this verified .gturbo bundle. Cold and warm SSD performance can differ materially.",
            "The launcher keeps the bundle's pinned model-native routing and excludes speculative decoding from this calibration lane.",
        ])


    def build_slotstream(self, plan: EnginePlan, cap: dict[str, Any]) -> None:
        if cap.get("runnable") is not True or not plan.model.get("slotstream"):
            raise ValueError("Choose the complete pinned Slotstream model.")
        install = slotstream_runtime.inspect_install(plan.runtime_binary or self.runtime.selected_binary("slotstream"), plan.model.get("path"))
        if install != plan.model["slotstream"] or not install["ready"]:
            raise ValueError("Slotstream's runtime or model changed. Rescan before launching.")
        options = self.validated_profile_options("slotstream", plan.model, cap, plan.options)
        plan.options.update(options)
        if options["kv"] == "q8":
            selected = plan.model.get("slotstreamQ8")
            if not selected:
                raise ValueError("Install the qualified Q8 Slotstream runtime, then rescan.")
            install = slotstream_runtime.inspect_install(selected["binary"], plan.model.get("path"))
            if install != selected:
                raise ValueError("The Q8 runtime changed. Rescan before launching.")
            plan.runtime_binary = install["binary"]
            plan.model["slotstream"] = install
        memory_plan = slotstream_runtime.doctor(install, plan.context, options)
        plan.options["_slotstreamMemoryPlan"] = memory_plan
        if options["memoryMode"] == "auto":
            plan.warnings.append(f"Automatic memory sizing keeps the selected {plan.context:,}-token context and MTP setting, using up to {options['memoryGB']} GB. The current native plan targets {memory_plan.get('target_gb', 0):.1f} GB; it rechecks available memory before loading.")
        native_argv = [install["binary"], "serve", "--port", str(plan.port),
                       *slotstream_runtime.planning_arguments(install, plan.context, options)]
        assert plan.run_dir
        config_path = plan.run_dir / "slotstream.json"
        self.io.atomic_json(config_path, {"install": install, "argv": native_argv, "depth": options["depth"]})
        plan.engine_argv = [sys.executable, "-I", "-S", "-B", str(self.paths.app_directory() / "slotstream_runtime.py"), str(config_path)]
        plan.engine_env = {"SLOTSTREAM_DRAFT_DEPTH": str(options["depth"])}
        if options["kv"] == "q8":
            # Measured 17-18 Sep 2026 on this Mac at a 112,881-token prompt with
            # Q8 KV, MTP depth 2, the 36 GB ceiling and the corrected tap sidecar
            # present in both arms: these engine-validated read-path switches took
            # cold prefill from 90.4 to 124.7 tok/s and decode from 8.62 to
            # 10.74 tok/s. Deterministic greedy probes are byte-identical with and
            # without the set. Evidence: bench/notes/flash-next.md and
            # bench/notes/RESULTS.md.
            # 4,096-token prefill passes measured better than the planner's 2,048
            # at this window (prefill 124.7 -> 128.6 tok/s and decode 10.74 ->
            # 11.26 tok/s at the auto-sized pool, 11.88 tok/s at a pinned 19 GB
            # pool), even though the larger pass costs ~2.6 GB of the process
            # budget. The same set goes to slotstream_runtime.doctor, so the
            # capacity check plans against the ledger the launch will use.
            plan.engine_env.update(slotstream_runtime.Q8_OPTIMIZATION_ENV)
        plan.model["servedId"] = slotstream_runtime.MODEL_ID
        # The native loopback server ignores auth; the shared relay still requires
        # a valid opaque upstream header in addition to its enforced surface key.
        plan.secrets["apiKey"] = self.io.token_urlsafe(32)
        plan.warnings.append("Slotstream verifies the pinned weights at startup and streams all experts and n-grams from SSD. Long first prompts can take several minutes; subsequent turns reuse the prefix cache.")


    def build_kolibri(self, plan: EnginePlan, cap: dict[str, Any]) -> None:
        runtime = kolibri_runtime.inspect_runtime(self.runtime.selected_binary("kolibri"))
        model = kolibri_runtime.inspect_model(Path(plan.model["path"]))
        if not runtime or not model or model != plan.model.get("kolibri") or runtime != cap.get("runtimeIdentity"):
            raise ValueError("Kolibri's model or runtime changed. Rescan before launching.")
        options = self.validated_profile_options("kolibri", plan.model, cap, plan.options)
        plan.options.update(options)
        memory = kolibri_runtime.memory_plan(model, plan.context, options, kolibri_runtime.current_resource())
        if not memory["ready"]:
            raise ValueError("Free memory before loading Kolibri or lower its fixed memory ceiling.")
        plan.options["_kolibriMemoryPlan"] = memory
        plan.secrets["apiKey"] = self.io.token_urlsafe(32)
        assert plan.run_dir
        config_path = plan.run_dir / "kolibri.json"
        self.io.atomic_json(config_path, {"runtime": runtime, "model": model, "options": options,
                                  "context": plan.context, "output": plan.output,
                                  "reasoning": plan.reasoning, "port": plan.port,
                                  "apiKey": plan.secrets["apiKey"]})
        plan.engine_argv = [sys.executable, "-I", "-S", "-B", str(self.paths.app_directory() / "kolibri_runtime.py"), str(config_path)]
        plan.engine_env = {}
        plan.model["servedId"] = kolibri_runtime.MODEL_ID
        plan.warnings.append(
            f"Kolibri keeps its full Q6 weights on SSD. Automatic sizing currently plans {memory['expertCacheBytes'] / 1024**3:.1f} GiB "
            f"of expert cache ({memory['residentExpertsPerLayer']}/384 experts per layer), and rechecks available memory before loading."
        )


    def build_rapidmlx(self, plan: EnginePlan, cap: dict[str, Any]) -> None:
        runtime, model = rapidmlx_runtime.validate_route(
            plan.runtime_binary or self.runtime.selected_binary("rapidmlx"), plan.model, cap, plan.context, plan.output,
        )
        plan.options.update(self.validated_profile_options("rapidmlx", plan.model, cap, plan.options))
        key = self.io.token_urlsafe(32)
        served = f"launcher-rapidmlx-{plan.run_id[:8]}"
        plan.engine_argv = rapidmlx_runtime.server_arguments(
            runtime, model, port=plan.port, served_id=served, context=plan.context, output=plan.output, reasoning=plan.reasoning,
            sampling=plan.model.get("defaultSampling"),
            options=plan.options,
        )
        plan.engine_env = rapidmlx_runtime.server_environment(key, plan.output)
        plan.secrets["apiKey"] = key
        plan.model["servedId"] = served
        decoding = "native MTP with adaptive draft depth" if "--speculative-config" in plan.engine_argv else "standard decoding"
        plan.warnings.append(f"Rapid MLX reuses the selected local MLX weights with full-precision KV and {decoding}. Models are not downloaded by the server; it starts only for this launcher session.")

    def build_rec(self, plan: EnginePlan, cap: dict[str, Any]) -> None:
        if cap.get("runnable") is not True or not plan.model.get("rec"):
            raise ValueError("Choose the complete official Flint INT4 model for Rec.")
        install = rec_runtime.inspect_install(plan.runtime_binary or self.runtime.selected_binary("rec"))
        model = rec_runtime.inspect_model(plan.model["path"])
        if not install or not install.get("ready") or not model or model["identity"] != plan.model["rec"].get("identity"):
            raise ValueError("Rec or Flint changed after scanning. Rescan before launching.")
        if plan.reasoning != "auto":
            raise ValueError("Flint uses native reasoning automatically; choose Auto.")
        plan.options.update(self.validated_profile_options("rec", plan.model, cap, plan.options))
        assert plan.run_dir
        key = self.io.token_hex(32)
        plan.engine_argv, plan.engine_env = rec_runtime.prepare_run(
            install, model, plan.run_dir, plan.context, plan.port, key, output=plan.output,
        )
        plan.model["servedId"] = rec_runtime.MODEL_ID
        plan.secrets["apiKey"] = key
        plan.warnings.append("Rec serves one generation at a time with native reasoning and function tools. The selected response limit is enforced by the launcher's session relay.")


    def build_strata(self, plan: EnginePlan, cap: dict[str, Any]) -> None:
        if cap.get("runnable") is not True or not plan.model.get("strata"):
            raise ValueError(strata_runtime.PREPARATION_REASON)
        install, model = strata_runtime.validate_route(
            plan.runtime_binary or self.runtime.selected_binary("strata"), plan.model, plan.context, plan.output)
        plan.options.update(self.validated_profile_options("strata", plan.model, cap, plan.options))
        assert plan.run_dir
        config = plan.run_dir / "strata.json"
        self.io.atomic_json(config, {"install": install, "model": model, "context": plan.context,
                                     "output": plan.output, "port": plan.port})
        plan.secrets["apiKey"] = self.io.token_urlsafe(32)
        plan.engine_env = {"LLM_STRATA_API_KEY": plan.secrets["apiKey"]}
        plan.engine_argv = [sys.executable, "-I", "-S", "-B", str(self.paths.app_directory() / "strata_runtime.py"), str(config)]
        plan.model["servedId"] = strata_runtime.MODEL_ID
        plan.warnings.append("Strata reads the existing Q4 GGUF shards and original BF16 table directly. Experts stream from SSD; the engine sizes its cache for available memory. This initial route uses standard decoding without an external draft model.")

    def build_splash(self, plan: EnginePlan, cap: dict[str, Any]) -> None:
        """Launch one compatible Splash model on a launcher-owned loopback port.

        The Homebrew CLI hardcodes 127.0.0.1:8000, which other launcher engines own;
        this drives the engine's own server.py with the planned port. The launch
        re-verifies the release hashes and model metadata before loading.
        """
        if cap.get("runnable") is not True or not plan.model.get("splash"):
            raise ValueError("Choose a compatible installed model for Splash.")
        pack = plan.model["splash"]
        options = self.validated_profile_options("splash", plan.model, cap, plan.options)
        plan.options.update(options)
        dspine = options["acceleration"] == "dspine"
        install, current = splash_runtime.require_route(
            plan.runtime_binary or self.runtime.selected_binary("splash"), pack, plan.context, options,
        )
        memory_config = {}
        if dspine or pack.get("ssdStreaming") is True:
            resource = self.memory.public_resource(self.memory.resource_snapshot())
            estimate = self.memory.launch_estimate(
                {"backend": "splash", "context": plan.context, "options": options},
                plan.model, resource,
            )
            if dspine:
                headroom = int(resource.get("headroomBytes") or 0)
                if resource.get("memoryAvailable") is not True or headroom < int(estimate["requiredHeadroomBytes"]):
                    raise ValueError("Current headroom cannot cover the DSpine draft, full target context and macOS reserve.")
                memory_config["maxMemory"] = str(headroom - estimate["osReserveBytes"] - estimate["companionBytes"])
            elif (resource.get("memoryAvailable") is not True
                    or estimate.get("nativeMemoryBudgetReady") is not True
                    or int(resource.get("headroomBytes") or 0) < int(estimate["requiredHeadroomBytes"])):
                raise ValueError("Free memory before loading Splash; current headroom cannot cover its streaming budget and protected reserves.")
            else:
                memory_config["maxMemory"] = str(int(estimate["nativeMemoryBudgetBytes"]))
        assert plan.run_dir
        config_path = plan.run_dir / "splash.json"
        self.io.atomic_json(config_path, {
            "install": install, "pack": current,
            "drafts": pack.get("draftCandidates") or [],
            "modelsRoot": str(self.paths.state_directory() / ("splash-dspine-models" if dspine else "splash-models")),
            "context": plan.context, "output": plan.output,
            "port": plan.port, "servedId": pack["id"],
            **({"acceleration": "dspine"} if dspine else {}),
            **memory_config,
        })
        plan.engine_argv = [sys.executable, "-I", "-S", "-B", str(self.paths.app_directory() / "splash_runtime.py"), str(config_path)]
        plan.model["servedId"] = pack["id"]
        plan.secrets["apiKey"] = self.io.token_urlsafe(32)
        plan.engine_env = {"SPLASH_API_KEY": plan.secrets["apiKey"]}
        if dspine:
            draft = "Q4 draft backbone and BF16 refinement" if plan.context == splash_runtime.DSPINE_CONTEXT else "BF16 draft"
            plan.warnings.append(
                f"Splash DSpine uses the {draft} with greedy sampling and {plan.context:,} context tokens. "
                "Matching turns can reuse a resident target prefix and rebuild the draft's trailing 8K context."
            )
        else:
            plan.warnings.append(
                f"Splash uses {plan.model.get('quantization') or 'the selected quantization'} with a matching DFlash2 draft "
                f"and {plan.context:,} context tokens. Local weights are reused without conversion. "
                "The first launch downloads the draft if it is missing; later turns reuse the prefix cache."
            )


    def build_whallm(self, plan: EnginePlan, cap: dict[str, Any]) -> None:
        """Launch the pinned local install, or bridge an independently running Whallm."""
        if plan.model.get("nativeWhallm"):
            if cap.get("nativeWhallm") is not True or cap.get("runnable") is not True:
                raise ValueError("This model is not a verified native Whallm route. Rescan models.")
            install = whallm_runtime.inspect_install(self.runtime.selected_binary("whallm"), plan.model.get("path"))
            if install != plan.model["nativeWhallm"]:
                raise ValueError("Whallm's runtime or model changed. Rescan before launching.")
            conflict = self.whallm.qualification_conflict()
            if conflict:
                raise ValueError("A separate Whallm model is already active. Use its existing shared route or unload it first.")
            if plan.reasoning == "off":
                raise ValueError("Thinking stays enabled on the native Whallm route.")
            plan.reasoning = "medium" if plan.reasoning == "auto" else plan.reasoning
            plan.options.update(self.validated_profile_options("whallm", plan.model, cap, plan.options))
            config = whallm_runtime.launch_config(
                install, port=plan.port, context=plan.context, output=plan.output,
                cache_directory=self.paths.state_directory() / "whallm-cache" / whallm_runtime.VERSION / install["artifactIdentity"][:16] / str(plan.context),
            )
            config_path = plan.run_dir / "whallm-owned.json"
            self.io.atomic_json(config_path, config)
            plan.options["_whallmConfig"] = config
            plan.model["servedId"] = self.policy.whallm.model_id
            plan.secrets["apiKey"] = self.io.token_urlsafe(32)
            plan.engine_argv = [install["python"], "-I", "-S", "-B", str(self.paths.app_directory() / "whallm_runtime.py"), str(config_path)]
            plan.engine_env = {"DEEPSEEK_API_KEY": plan.secrets["apiKey"],
                               "WHALLM_ANE_BRIDGE": str(Path(install["app"]) / "Contents/Frameworks/libWhallmANE.dylib")}
            plan.warnings.extend([
                "LLM Launcher owns this Whallm process and unloads it when the session ends.",
                "Full 512-expert Qwen uses SSD streaming with a fixed 40 GiB memory ceiling and 16K working context.",
                "This 48 GiB Mac remains below Whallm's published 64 GiB support floor; the full model is separate from a pruned REAP checkpoint.",
            ])
            return
        if (
            plan.model.get("sharedServer") is not True
            or plan.model.get("remoteModelId") != self.policy.whallm.model_id
            or cap.get("runnable") is not True
            or cap.get("sharedServer") is not True
        ):
            raise ValueError("This is not the live pinned Whallm Qwen3.8 Flash-Next route. Rescan models.")
        if plan.context not in self.policy.whallm.context_windows:
            choices = ", ".join(f"{value:,}" for value in self.policy.whallm.context_windows)
            raise ValueError(f"Whallm's measured Qwen route uses one of these contexts: {choices}.")
        live = self.whallm.probe_endpoint()
        if live.get("model") != self.policy.whallm.model_id:
            raise ValueError("Whallm stopped serving its pinned Qwen model. Start it and rescan models.")
        if not self.paths.openai_bridge().is_file():
            raise ValueError("The launcher's private OpenAI bridge is missing.")
        options = self.validated_profile_options("whallm", plan.model, cap, plan.options)
        plan.options.update(options)
        local_key = self.io.token_urlsafe(32)
        bridge_config = plan.run_dir / "whallm-bridge.json"
        self.io.atomic_json(bridge_config, {
            "version": 1,
            "listenPort": plan.port,
            "clientKey": local_key,
            "endpoint": self.policy.whallm.endpoint,
            "upstreamKey": "",
            "upstreamLabel": "Whallm",
            "servedModel": self.policy.whallm.model_id,
        })
        plan.model["servedId"] = self.policy.whallm.model_id
        plan.secrets["apiKey"] = local_key
        plan.engine_argv = [sys.executable, str(self.paths.openai_bridge()), str(bridge_config)]
        plan.engine_env = {}
        plan.warnings.extend([
            "Whallm owns the full 512-expert model and its SSD cache. Stop closes only this launcher's private route; use Whallm to unload the model.",
            "Whallm publishes a 64 GiB support floor. Its current M5 Pro measurements reached 22.75 GiB of MLX active memory through 16K input, so this 48 GiB Mac is exposed as an experimental—not guaranteed—route.",
            "The Whallm checkpoint is a separate MXFP4 install and is never compared as equivalent to a pruned REAP checkpoint.",
        ])


    def _llamacpp_launch_file_identities(self, model_path: Path) -> tuple[tuple[Any, ...], ...]:
        """Snapshot every receipt, runtime, and model path used by this route."""
        paths = [
            self.policy.llamacpp.runtime_directory,
            self.policy.llamacpp.server_path,
            model_path.parent / self.policy.llamacpp.acquisition_marker,
        ]
        for load_name, target_name, _expected_digest in self.policy.llamacpp.runtime_file_manifest:
            paths.extend((self.policy.llamacpp.runtime_directory / load_name, self.policy.llamacpp.runtime_directory / target_name))
        paths.extend(
            model_path / Path(relative).name
            for relative, _size, _checksum in self.policy.llamacpp.model_file_manifest
        )
        unique = sorted({str(item.expanduser()) for item in paths})
        return tuple(self.models.strong_path_identity(Path(item)) for item in unique)


    def _validated_llamacpp_route(self, 
        plan: EnginePlan, cap: dict[str, Any],
    ) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any], tuple[tuple[Any, ...], ...]]:
        """Revalidate the exact managed runtime and immutable AtomicChat artifact."""
        binary = self.runtime.selected_binary("llamacpp")
        if plan.context != self.policy.llamacpp.context:
            raise ValueError(
                f"The initial llama.cpp SSD-PLE qualification is fixed at {self.policy.llamacpp.context:,} context tokens."
            )
        options = self.validated_profile_options("llamacpp", plan.model, cap, plan.options)
        try:
            model_path = Path(str(plan.model.get("path") or "")).expanduser().resolve(strict=True)
            before = self._llamacpp_launch_file_identities(model_path)
        except OSError as error:
            raise ValueError("The audited llama.cpp runtime or AtomicChat GGUF folder moved after the model scan.") from error
        runtime = self.llamacpp.runtime_contract(binary)
        if runtime.get("ready") is not True:
            raise ValueError(str(runtime.get("reason") or "The audited llama.cpp runtime is not ready."))
        if str(cap.get("runtimeVersion") or "") != str(runtime.get("version") or ""):
            raise ValueError("The llama.cpp runtime changed after the model scan. Rescan models before launch.")
        artifact = self.llamacpp.artifact_contract(model_path)
        if artifact.get("ready") is not True:
            raise ValueError(str(artifact.get("reason") or "The AtomicChat receipt is no longer valid."))
        if (
            cap.get("llamacppPle") is not True
            or cap.get("currentProcessVerified") is not True
            or not isinstance(cap.get("verificationGeneration"), int)
            or cap.get("verificationGeneration") <= 0
            or cap.get("verificationGeneration") != artifact.get("verificationGeneration")
            or cap.get("receiptFingerprint") != artifact.get("receiptFingerprint")
            or cap.get("firstShard") != artifact.get("firstShard")
            or cap.get("modelPath") != str(model_path)
            or cap.get("benchmarkModelFingerprint")
            != self.models.artifact_fingerprint(model_path, self.io.read_json(model_path / "config.json"))
        ):
            raise ValueError("The AtomicChat GGUF or acquisition receipt changed after the scan. Rescan models.")
        wired_limit = self.memory.wired_limit_bytes()
        if wired_limit != self.policy.llamacpp.memory_ceiling_bytes:
            raise ValueError(
                f"This exact route requires the temporary Metal wired-memory limit to be exactly "
                f"{self.policy.llamacpp.memory_ceiling_gib:.0f} GiB; it cannot be bypassed or raised."
            )
        whallm_conflict = self.whallm.qualification_conflict()
        if whallm_conflict:
            raise ValueError(
                f"{self.policy.llamacpp.whallm_conflict_label}. {whallm_conflict['detail']}"
            )
        self._validate_llamacpp_qualified_session_boundary(plan)
        try:
            after = self._llamacpp_launch_file_identities(model_path)
        except OSError as error:
            raise ValueError("The audited llama.cpp runtime or AtomicChat GGUF changed during validation.") from error
        if before != after:
            raise ValueError("The audited llama.cpp runtime or AtomicChat GGUF changed during validation.")
        return str(binary), runtime, artifact, options, after


    def _llamacpp_engine_argv(self, 
        plan: EnginePlan, binary: str, artifact: dict[str, Any], served: str,
        api_key_file: Path,
    ) -> list[str]:
        return [
            binary,
            "--model", str(artifact["firstShard"]),
            "-ngl", "99",
            "-c", str(self.policy.llamacpp.context),
            "--parallel", "1",
            "--load-mode", "mmap",
            "--lazy-mode", "on",
            "-fit", "off",
            "--jinja",
            "-fa", "on",
            "--reasoning", "on",
            "--reasoning-format", "deepseek",
            "--reasoning-preserve",
            "--reasoning-budget-message", self.policy.llamacpp.reasoning_budget_message,
            "--spec-type", "none",
            "--cache-type-k", "f16",
            "--cache-type-v", "f16",
            "--host", "127.0.0.1",
            "--port", str(plan.port),
            "--alias", served,
            "--api-key-file", str(api_key_file),
        ]


    def _llamacpp_api_key_file(self, plan: EnginePlan) -> Path:
        if plan.run_dir is None:
            raise ValueError("The private llama.cpp run folder is missing.")
        return plan.run_dir / self.policy.llamacpp.api_key_filename


    def _uzu_api_key_file(self, plan: EnginePlan) -> Path:
        if plan.run_dir is None:
            raise ValueError("The private Uzu run folder is missing.")
        return plan.run_dir / self.policy.uzu.api_key_filename


    def _plan_private_bearer_file_names(self, plan: EnginePlan) -> tuple[str, ...]:
        proxy_names = ("session-proxy.json", "codex-proxy.json", "omp-settings.json")
        if plan.backend == "llamacpp":
            return self.policy.llamacpp.private_bearer_filenames
        if plan.backend == "uzu":
            return self.policy.uzu.private_bearer_filenames
        return (*proxy_names, *self.policy.private_engine_bearer_files.get(plan.backend, ()))

    def _unlink_private_bearer(self, run_dir: Path, relative_name: str) -> None:
        """Unlink one fixed credential through owner-controlled directory fds.

        A replaced final symlink is removed itself. Parent symlinks are rejected,
        including the nested oMLX settings directory, so cleanup cannot traverse
        outside the authorized run when a directory name changes concurrently.
        """
        parts = Path(relative_name).parts
        if not parts or Path(relative_name).is_absolute() or any(part in {"", ".", ".."} for part in parts):
            raise OSError("unsafe private bearer name")
        no_follow = getattr(os, "O_NOFOLLOW", None)
        directory_flag = getattr(os, "O_DIRECTORY", None)
        if no_follow is None or directory_flag is None:
            raise OSError("safe private bearer traversal is unavailable")
        flags = os.O_RDONLY | no_follow | directory_flag
        descriptor = None
        try:
            named = run_dir.lstat()
            descriptor = os.open(run_dir, flags)
            opened = os.fstat(descriptor)
            if (not stat.S_ISDIR(opened.st_mode) or opened.st_uid != os.geteuid()
                    or opened.st_dev != named.st_dev or opened.st_ino != named.st_ino):
                raise OSError("unsafe private run directory")
            for part in parts[:-1]:
                child = os.open(part, flags, dir_fd=descriptor)
                try:
                    details = os.fstat(child)
                    if not stat.S_ISDIR(details.st_mode) or details.st_uid != os.geteuid():
                        raise OSError("unsafe private bearer parent")
                except Exception:
                    os.close(child)
                    raise
                os.close(descriptor)
                descriptor = child
            details = os.stat(parts[-1], dir_fd=descriptor, follow_symlinks=False)
            if stat.S_ISDIR(details.st_mode) or details.st_uid != os.geteuid():
                return
            os.unlink(parts[-1], dir_fd=descriptor)
        finally:
            if descriptor is not None:
                os.close(descriptor)


    def dispose_plan_secrets(self, plan: EnginePlan) -> None:
        """Remove fixed bearer files and forget in-memory keys for one plan.

        Uzu and llama.cpp both create their server credential during planning so
        the exact argv can be validated before exec.  Previews, rejected admission,
        startup failure, and normal Stop all use this idempotent backend-neutral
        cleanup path. Fixed private files stay inside the run directory; Rec
        also removes its verified short path alias for the native control socket.
        """
        run_dir = plan.run_dir
        try:
            if run_dir is None:
                raise OSError("missing run directory")
            directory = run_dir.lstat()
            if (
                run_dir.is_symlink()
                or not stat.S_ISDIR(directory.st_mode)
                or directory.st_uid != os.geteuid()
            ):
                raise OSError("unsafe run directory")
            for name in self._plan_private_bearer_file_names(plan):
                try:
                    self._unlink_private_bearer(run_dir, name)
                except FileNotFoundError:
                    continue
                except OSError:
                    continue
            if plan.backend == "rec":
                rec_runtime.cleanup_run_alias(run_dir)
        except OSError:
            pass
        for key in ("apiKey", "clientApiKey", "proxyControlKey"):
            plan.secrets.pop(key, None)
        for key in ("OMLX_API_KEY", "SPLASH_API_KEY", "DEEPSEEK_API_KEY"):
            plan.engine_env.pop(key, None)
        for key in ("LLM_LAUNCHER_PI_PROVIDER", "LLM_LAUNCHER_OMP_PROVIDER",
                    "LLM_LAUNCHER_CODEX_API_KEY", "OPENCODE_CONFIG_CONTENT"):
            plan.client_env.pop(key, None)


    def dispose_llamacpp_plan_bearers(self, plan: EnginePlan) -> None:
        """Compatibility wrapper for callers that still use the old name."""
        self.dispose_plan_secrets(plan)


    def _validated_plan_api_key_file(self, 
        plan: EnginePlan, *, backend: str, filename: str, label: str,
    ) -> Path:
        """Bind a live credential to one owner-only regular file in this run."""
        if plan.backend != backend:
            raise ValueError(f"The private {label} API-key file belongs to another backend.")
        if not _private_bearer_basename_valid(filename):
            raise ValueError(f"The private {label} API-key filename is invalid.")
        run_dir = plan.run_dir
        if run_dir is None:
            raise ValueError(f"The private {label} run folder is missing.")
        key_file = run_dir / filename
        expected = str(plan.secrets.get("apiKey") or "")
        descriptor: int | None = None
        try:
            run_details = run_dir.lstat()
            details = key_file.lstat()
            resolved_run_dir = run_dir.resolve(strict=True)
            resolved_key_file = key_file.resolve(strict=True)
            if (
                run_dir.is_symlink()
                or not stat.S_ISDIR(run_details.st_mode)
                or run_details.st_uid != os.geteuid()
                or key_file.is_symlink()
                or not stat.S_ISREG(details.st_mode)
                or details.st_uid != os.geteuid()
                or details.st_nlink != 1
                or stat.S_IMODE(details.st_mode) != 0o600
                or not 1 <= details.st_size <= 1_024
                or resolved_key_file.parent != resolved_run_dir
                or resolved_key_file != resolved_run_dir / filename
            ):
                raise ValueError(f"The private {label} API-key file changed before launch.")
            flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(key_file, flags)
            opened = os.fstat(descriptor)
            if (
                opened.st_dev != details.st_dev
                or opened.st_ino != details.st_ino
                or opened.st_nlink != 1
                or stat.S_IMODE(opened.st_mode) != 0o600
                or opened.st_uid != os.geteuid()
            ):
                raise ValueError(f"The private {label} API-key file changed before launch.")
            raw = os.read(descriptor, 1_025)
            after = os.fstat(descriptor)
            if (
                after.st_dev != opened.st_dev
                or after.st_ino != opened.st_ino
                or after.st_size != opened.st_size
                or after.st_mtime_ns != opened.st_mtime_ns
                or after.st_ctime_ns != opened.st_ctime_ns
            ):
                raise ValueError(f"The private {label} API-key file changed before launch.")
            value = raw.decode("utf-8")
        except (OSError, UnicodeError) as error:
            raise ValueError(f"The private {label} API-key file is missing or unreadable.") from error
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        if (
            not expected
            or len(expected) > 512
            or "\0" in expected
            or not secrets.compare_digest(value, expected + "\n")
        ):
            raise ValueError(f"The private {label} API-key file changed before launch.")
        return key_file


    def _create_plan_api_key_file(self, 
        plan: EnginePlan, *, backend: str, filename: str, label: str,
    ) -> tuple[Path, str]:
        """Create one exclusive owner-only credential inside the fixed run folder."""
        if plan.backend != backend or plan.run_dir is None:
            raise ValueError(f"The private {label} run folder is missing.")
        if not _private_bearer_basename_valid(filename):
            raise ValueError(f"The private {label} API-key filename is invalid.")
        run_dir = plan.run_dir
        key_file = run_dir / filename
        api_key = self.io.token_urlsafe(32)
        directory_fd: int | None = None
        descriptor: int | None = None
        created_identity: tuple[int, int] | None = None
        try:
            directory_flags = os.O_RDONLY
            if hasattr(os, "O_DIRECTORY"):
                directory_flags |= os.O_DIRECTORY
            if hasattr(os, "O_NOFOLLOW"):
                directory_flags |= os.O_NOFOLLOW
            directory_fd = os.open(run_dir, directory_flags)
            directory = os.fstat(directory_fd)
            if (
                not stat.S_ISDIR(directory.st_mode)
                or directory.st_uid != os.geteuid()
                or stat.S_IMODE(directory.st_mode) != 0o700
            ):
                raise OSError("unsafe run directory")
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(filename, flags, 0o600, dir_fd=directory_fd)
            created = os.fstat(descriptor)
            created_identity = (created.st_dev, created.st_ino)
            os.fchmod(descriptor, 0o600)
            encoded = (api_key + "\n").encode("utf-8")
            written = 0
            while written < len(encoded):
                chunk_size = os.write(descriptor, encoded[written:])
                if chunk_size <= 0:
                    raise OSError("short write while creating private API key")
                written += chunk_size
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            os.fsync(directory_fd)
            plan.secrets["apiKey"] = api_key
            self._validated_plan_api_key_file(
                plan, backend=backend, filename=filename, label=label,
            )
            return key_file, api_key
        except (OSError, ValueError) as error:
            plan.secrets.pop("apiKey", None)
            if created_identity is not None and directory_fd is not None:
                try:
                    current = os.stat(filename, dir_fd=directory_fd, follow_symlinks=False)
                    if (current.st_dev, current.st_ino) == created_identity and current.st_uid == os.geteuid():
                        os.unlink(filename, dir_fd=directory_fd)
                except OSError:
                    pass
            raise ValueError(f"Could not create the private {label} API-key file.") from error
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            if directory_fd is not None:
                try:
                    os.close(directory_fd)
                except OSError:
                    pass


    def _validated_llamacpp_api_key_file(self, plan: EnginePlan) -> Path:
        return self._validated_plan_api_key_file(
            plan, backend="llamacpp", filename=self.policy.llamacpp.api_key_filename,
            label="llama.cpp",
        )


    def _validated_uzu_api_key_file(self, plan: EnginePlan) -> Path:
        return self._validated_plan_api_key_file(
            plan, backend="uzu", filename=self.policy.uzu.api_key_filename, label="Uzu",
        )


    def _validate_llamacpp_qualified_session_boundary(self, plan: EnginePlan) -> None:
        """Rebind a normal load to its measured peak and current macOS headroom."""
        if plan.purpose not in {"session", "route-check"}:
            return
        resource = self.memory.public_resource(self.memory.resource_snapshot())
        record, metrics, estimate = self.llamacpp.qualified_session_capacity(
            {
                "backend": plan.backend, "client": plan.client,
                "modelId": plan.model.get("id"), "context": plan.context,
                "output": plan.output, "reasoning": plan.reasoning,
                "options": copy.deepcopy(plan.options),
                "chat": copy.deepcopy(plan.chat),
            },
            plan.model, resource,
        )
        headroom = resource.get("headroomBytes")
        if record is None or metrics is None:
            raise ValueError(
                "The exact llama.cpp qualification receipt became stale before launch. "
                "Run the bounded route qualification again."
            )
        if (
            resource.get("memoryAvailable") is not True
            or not isinstance(headroom, int) or isinstance(headroom, bool)
            or headroom < int(estimate["requiredHeadroomBytes"])
        ):
            raise ValueError(
                "Current unified-memory headroom no longer covers the exact measured llama.cpp "
                "process-group peak plus the protected 4 GiB macOS reserve."
            )


    def validate_llamacpp_launch_boundary(self, 
        plan: EnginePlan,
    ) -> tuple[tuple[Any, ...], ...]:
        """Fail closed at exec if the planned runtime, artifact, or argv changed."""
        capabilities = plan.model.get("backends")
        cap = capabilities.get("llamacpp") if isinstance(capabilities, dict) else None
        if not isinstance(cap, dict):
            raise ValueError("The llama.cpp launch capability is missing. Rescan models.")
        binary, _runtime, artifact, options, identities = self._validated_llamacpp_route(plan, cap)
        served = str(plan.model.get("servedId") or "")
        api_key = str(plan.secrets.get("apiKey") or "")
        if not served or not api_key:
            raise ValueError("The private llama.cpp route credentials are missing.")
        key_file = self._validated_llamacpp_api_key_file(plan)
        expected_argv = self._llamacpp_engine_argv(plan, binary, artifact, served, key_file)
        if plan.engine_argv != expected_argv:
            raise ValueError("The fixed llama.cpp launch command changed after validation.")
        if plan.engine_env or any(key.startswith("DYLD_") for key in plan.engine_env):
            raise ValueError("The fixed llama.cpp launch environment changed after validation.")
        if any(plan.options.get(key) != value for key, value in options.items()):
            raise ValueError("The fixed llama.cpp launch options changed after validation.")
        return (*identities, self.models.strong_path_identity(key_file))


    def confirm_llamacpp_launch_identities(self, 
        plan: EnginePlan, expected: tuple[tuple[Any, ...], ...],
    ) -> None:
        """Close the validation-to-exec window with one final strong stat snapshot."""
        try:
            model_path = Path(str(plan.model.get("path") or "")).expanduser().resolve(strict=True)
            current = self._llamacpp_launch_file_identities(model_path)
            key_file = self._validated_llamacpp_api_key_file(plan)
            key_identity = self.models.strong_path_identity(key_file)
        except OSError as error:
            raise ValueError("The audited llama.cpp runtime or AtomicChat GGUF changed before launch.") from error
        if not expected or current != expected[:-1] or key_identity != expected[-1]:
            raise ValueError("The audited llama.cpp runtime or AtomicChat GGUF changed before launch.")
        whallm_conflict = self.whallm.qualification_conflict()
        if whallm_conflict:
            raise ValueError(
                f"{self.policy.llamacpp.whallm_conflict_label}. {whallm_conflict['detail']}"
            )
        if self.memory.wired_limit_bytes() != self.policy.llamacpp.memory_ceiling_bytes:
            raise ValueError(
                f"The Metal wired-memory limit changed before launch; it must still equal exactly "
                f"{self.policy.llamacpp.memory_ceiling_gib:.0f} GiB."
            )
        self._validate_llamacpp_qualified_session_boundary(plan)


    def build_llamacpp(self, plan: EnginePlan, cap: dict[str, Any]) -> None:
        """Build the one receipt-bound, no-MTP AtomicChat SSD-PLE route."""
        binary, _runtime, artifact, options, _identities = self._validated_llamacpp_route(plan, cap)
        plan.options.update(options)
        served = f"llm-launcher-atomic-ple-{plan.run_id[:8]}"
        api_key = self.io.token_urlsafe(32)
        key_file = self._llamacpp_api_key_file(plan)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        created_identity = None
        descriptor = None
        try:
            descriptor = os.open(key_file, flags, 0o600)
            created = os.fstat(descriptor)
            created_identity = (created.st_dev, created.st_ino)
            handle = os.fdopen(descriptor, "w", encoding="utf-8")
            descriptor = None  # the file object now owns this descriptor
            with handle:
                handle.write(api_key + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(key_file, 0o600)
        except OSError as error:
            if created_identity is not None:
                try:
                    current = key_file.lstat()
                    if (current.st_dev, current.st_ino) == created_identity and current.st_uid == os.geteuid():
                        key_file.unlink()
                except OSError:
                    pass
            raise ValueError("Could not create the private llama.cpp API-key file.") from error
        finally:
            if descriptor is not None:
                os.close(descriptor)
        plan.model["servedId"] = served
        plan.secrets["apiKey"] = api_key
        plan.engine_argv = self._llamacpp_engine_argv(plan, binary, artifact, served, key_file)
        plan.engine_env = {}
        plan.warnings.extend([
            "This exact AD-3.84 quant keeps only its isolated PLE table in read-only SSD mmap; ordinary model weights are not SSD streamed.",
            "The route is fixed to 8K context, full-precision KV, one request lane, no MTP, and an exact 44 GiB Metal ceiling for initial qualification.",
            "The launcher relay caps automatic reasoning at the qualified 384-token budget while preserving final-answer space; a stricter smaller client budget is preserved.",
            "AD-3.84 is an aggressive low-bit quality tradeoff. Do not treat the publisher's M5 Max speed as a measurement for this Mac.",
        ])


    def build_remote_freetoken(self, plan: EnginePlan, cap: dict[str, Any]) -> None:
        """Own only a private bridge; the configured FreeToken server owns model memory."""
        connection = self.freetoken.connection()
        if not connection:
            raise ValueError("Connect and verify a FreeToken server before launching this route.")
        if plan.model.get("remoteConnectionId") != connection.get("id"):
            raise ValueError("The FreeToken connection changed after this model was selected. Rescan models.")
        remote_model = str(plan.model.get("remoteModelId") or "")
        if not remote_model or remote_model not in connection.get("models", []):
            raise ValueError("The selected model is no longer advertised by the FreeToken server. Reconnect it.")
        if cap.get("runnable") is not True or cap.get("connectionId") != connection.get("id"):
            raise ValueError("The FreeToken model capability record is stale. Rescan models.")
        if not self.paths.openai_bridge().is_file():
            raise ValueError("The launcher's FreeToken bridge is missing.")
        local_key = self.io.token_urlsafe(32)
        bridge_config = plan.run_dir / "freetoken-bridge.json"
        self.io.atomic_json(bridge_config, {
            "version": 1,
            "listenPort": plan.port,
            "clientKey": local_key,
            "endpoint": connection["endpoint"],
            "upstreamKey": connection.get("apiKey", ""),
            "servedModel": remote_model,
        })
        plan.model["servedId"] = remote_model
        plan.secrets["apiKey"] = local_key
        plan.engine_argv = [sys.executable, str(self.paths.openai_bridge()), str(bridge_config)]
        plan.engine_env = {}
        plan.options.update({
            "acceleration": "off", "depth": 1, "kv": "off",
            "_remoteConnectionId": connection["id"],
        })
        transport = "encrypted HTTPS" if str(connection["endpoint"]).startswith("https://") else "plain HTTP"
        plan.warnings.append(
            f"FreeToken stays loaded on its configured server. Stop closes only this launcher's private bridge; remote model ownership is unchanged. Transport to that server uses {transport}."
        )


    def build_native_freetoken(self, plan: EnginePlan, cap: dict[str, Any]) -> None:
        """Start one launcher-owned, loopback-only native MLX/Metal FreeToken server."""
        if plan.model.get("nativeFreetoken") is not True or cap.get("native") is not True:
            raise ValueError("This model has no native FreeToken capability receipt.")
        if plan.client != "chat":
            raise ValueError(
                "The native FreeToken milestone currently supports built-in Chat only; "
                "tools and the Responses API remain fail-closed."
            )
        binary = self.runtime.selected_binary("freetoken_native")
        if not binary:
            raise ValueError("The native Apple-Silicon FreeToken port is not installed.")
        try:
            binary_path = Path(binary).expanduser().resolve(strict=True)
            scanned_binary = Path(str(cap.get("nativeBinary") or "")).expanduser().resolve(strict=True)
            model_path = Path(str(plan.model.get("path") or "")).expanduser().resolve(strict=True)
        except OSError as error:
            raise ValueError("The native FreeToken executable or checkpoint moved after the model scan.") from error
        if binary_path != scanned_binary or not os.access(binary_path, os.X_OK):
            raise ValueError("The native FreeToken executable changed after the model scan. Rescan models.")
        config = self.io.read_json(model_path / "config.json")
        fingerprint = self.models.artifact_fingerprint(model_path, config)
        if not fingerprint or fingerprint != cap.get("benchmarkModelFingerprint"):
            raise ValueError("The native FreeToken checkpoint changed after inspection. Rescan models.")
        inspected = self.freetoken.validate_native_contract(
            cap.get("nativeContract"), model_path,
        )
        if inspected.get("supported") is not True or inspected.get("startup", {}).get("default_allowed") is not True:
            raise ValueError(str(cap.get("reason") or "Native FreeToken preflight no longer permits this checkpoint."))
        current = self.freetoken.inspect_native_model(
            model_path,
            int(cap.get("nativeMaxContext") or plan.model.get("nativeContext") or plan.context),
            fingerprint,
            force=True,
        )
        if (
            current.get("supported") is not True
            or current.get("startup", {}).get("default_allowed") is not True
            or current.get("runtime", {}).get("freetoken_version")
            != inspected.get("runtime", {}).get("freetoken_version")
            or current.get("qualification") != inspected.get("qualification")
        ):
            raise ValueError("Native FreeToken capability evidence changed after the scan. Rescan models.")
        qualification_policy = inspected["qualification"]["launcher"]
        experimental_consent = plan.options.get("experimentalQualificationConsent") is True
        options = self.validated_freetoken_options(cap, plan.options)
        plan.options.pop("experimentalQualificationConsent", None)
        plan.options.update(options)
        if qualification_policy.get("readiness") == "experimental_synthetic_only":
            plan.options["_freetokenExperimentalConsent"] = experimental_consent
        served = f"llm-launcher-{self.io.slug(plan.model['name'], 34)}-{plan.run_id[:8]}"
        argv = [
            str(binary_path), "macos-serve",
            "--model", str(model_path),
            "--served-model-name", served,
            "--host", "127.0.0.1",
            "--port", str(plan.port),
            "--max-batch-size", str(options["maxBatchSize"]),
        ]
        if options["expertCacheSize"] is not None:
            argv.extend(["--expert-cache-size", str(options["expertCacheSize"])])
        if options["prefixCacheEntries"] > 0:
            argv.extend(["--prefix-cache-entries", str(options["prefixCacheEntries"])])
        plan.model["servedId"] = served
        plan.engine_argv = argv
        plan.engine_env = {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
        }
        plan.options["_freetokenRoute"] = "native"
        if qualification_policy.get("readiness") == "experimental_synthetic_only":
            plan.warnings.append(
                "Experimental FreeToken run explicitly approved: only the tiny synthetic path has completed end-to-end verification; "
                "this real checkpoint is not qualified, and the launcher does not recommend downloading a large model for this path."
            )
        else:
            plan.warnings.append(
                "FreeToken supplied runtime-owned end-to-end serve and token-generation evidence for this exact real checkpoint."
            )
        plan.warnings.append(
            "Native FreeToken runs locally through MLX/Metal and is owned by this launcher. "
            "Stop unloads this exact server; network model downloads, custom sampling, tools, and Responses remain disabled."
        )


    def build_freetoken(self, plan: EnginePlan, cap: dict[str, Any]) -> None:
        if plan.model.get("remote") is True:
            self.build_remote_freetoken(plan, cap)
            return
        self.build_native_freetoken(plan, cap)


    def validate_live_native_freetoken(self, plan: EnginePlan, value: Any) -> dict[str, Any]:
        """Bind live /health to the exact native launch settings and checkpoint."""
        try:
            model_path = Path(str(plan.model.get("path") or "")).expanduser().resolve(strict=True)
            contract = self.freetoken.validate_native_contract(value, model_path, live=True)
        except (OSError, ValueError) as error:
            raise RuntimeError(f"Native FreeToken health verification failed: {error}") from error
        service = contract["service"]
        enabled = service["enabled"]
        expected_batch = int(plan.options.get("maxBatchSize") or 1)
        expected_prefix = int(plan.options.get("prefixCacheEntries") or 0) > 0
        expected_experts = plan.options.get("expertCacheSize") is not None
        scanned_qualification = (
            plan.model.get("backends", {}).get("freetoken", {})
            .get("nativeContract", {}).get("qualification")
        )
        if (
            contract.get("supported") is not True
            or contract.get("qualification") != scanned_qualification
            or contract.get("model", {}).get("id") != plan.model.get("servedId")
            or service.get("served_model_id") != plan.model.get("servedId")
            or service.get("working_set_override_used") is not False
            or service.get("max_batch_size") != expected_batch
            or enabled.get("continuous_batching") is not (expected_batch > 1)
            or enabled.get("prefix_cache") is not expected_prefix
            or enabled.get("expert_placement") is not expected_experts
        ):
            raise RuntimeError(
                "Native FreeToken health does not match the launcher-owned process settings."
            )
        return contract
