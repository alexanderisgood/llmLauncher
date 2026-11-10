"""Complete benchmark, tuning, qualification and runtime-comparison jobs.

Owns execution order, admission orchestration, result staging, status and
cancellation. Explicit ports supply plans, live resource/inference operations,
artifact verification and persistence. Import performs no engine operations.
"""
from __future__ import annotations
import copy
from dataclasses import dataclass, fields
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import secrets
import statistics
import threading
import time
from typing import Any, Callable, Mapping, Protocol
import uuid
import benchmark_evidence
import generation_metrics


class BenchmarkCancelled(RuntimeError): pass
class ResourceCooldownTimeout(RuntimeError): pass
class QualificationSafetyFailure(RuntimeError): pass


@dataclass(frozen=True)
class BenchmarkErrors:
    cancelled: type[Exception] = BenchmarkCancelled
    cooldown: type[Exception] = ResourceCooldownTimeout
    safety: type[Exception] = QualificationSafetyFailure


class BenchmarkPlan(Protocol):
    backend: str
    options: dict[str, Any]
    port: int
    client_port: int | None


@dataclass(frozen=True)
class RunOwnerPort:
    """Only this manager's exact accepted plan lifetime may be accessed.

    stop requires expected_plan. Process/ports/safety include final receipts
    after unloading, but never expose or stop a replacement owner.
    """
    snapshot: Callable[[], dict[str, Any]]
    start: Callable[[BenchmarkPlan], None]
    stop: Callable[..., None]
    owns_plan: Callable[[BenchmarkPlan], bool]
    process_for: Callable[[BenchmarkPlan], Any]
    ports_for: Callable[[BenchmarkPlan], tuple[int, ...]]
    safety_violation: Callable[[BenchmarkPlan | None], str | None]


class TelemetrySampler(Protocol):
    violation: str | None
    def start(self, initial_sample: dict[str, Any] | None = None) -> None: ...
    def stop(self) -> dict[str, Any]: ...


class EvidencePort(Protocol):

    def mtplx_mtp_depth_candidates(self, capability: dict[str, Any]) -> list[int]:
        ...

    def _positive_finite_number(self, value: Any) -> bool:
        ...

    def _mtplx_operator_measurement_evidence(self, result: dict[str, Any]) -> dict[str, Any]:
        ...

    def dflash2_tuning_controls(self, options: dict[str, Any], capability: dict[str, Any]) -> dict[str, Any]:
        ...

    def deterministic_tuning_best_candidate(self, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
        ...

    def benchmark_route_selection_metric(self, job: dict[str, Any]) -> str:
        ...

    def tuning_speed_fields(self, selection_metric: str) -> tuple[str, str]:
        ...

    def sampling_record_evidence(self, evidence: dict[str, Any]) -> dict[str, Any]:
        ...

    def select_engine_settings_sweep_candidate(self, candidates: list[dict[str, Any]], preference: str) -> dict[str, Any] | None:
        ...

    def engine_settings_candidate_evidence(self, candidate: dict[str, Any], record: dict[str, Any], reference: dict[str, Any], preference: str) -> dict[str, Any]:
        ...

    def _local_benchmark_record_verified(self, capability: dict[str, Any], benchmark: dict[str, Any], evidence: dict[str, Any] | None=None) -> bool:
        ...


@dataclass(frozen=True)
class BenchmarkPolicy:
    backend_labels: Any
    benchmark_comparison_contract_version: Any
    benchmark_cooldown_max_seconds: Any
    benchmark_cooldown_memory_tolerance_bytes: Any
    benchmark_cooldown_sample_seconds: Any
    benchmark_cooldown_stable_samples: Any
    benchmark_dflash_tuner_max_candidates: Any
    benchmark_dflash_tuner_version: Any
    benchmark_minimum_speedup: Any
    benchmark_mtp_tuner_max_candidates: Any
    benchmark_mtp_tuner_version: Any
    benchmark_probe_contract: Any
    engine_preference_labels: Any
    llamacpp_ple_memory_ceiling_bytes: Any
    llamacpp_qualification_correctness_expected: Any
    llamacpp_qualification_reasoning_boundary_id: Any
    llamacpp_qwen_reasoning_budget_message: Any
    mtplx_long_context_2111_route: Any
    mtplx_long_context_2111_sweep_version: Any
    mtplx_long_context_64k_suite: Any
    mtplx_long_context_baseline_env: Any
    mtplx_long_context_candidate_env: Any
    mtplx_long_context_default_route: Any
    mtplx_long_context_minimum: Any
    mtplx_long_context_minimum_prompt: Any
    mtplx_mtp_depth_sweep_max_candidates: Any
    mtplx_mtp_depth_sweep_version: Any
    route_qualification_version: Any
    uzu_process_memory_ceiling_bytes: Any
    uzu_qualification_correctness_expected: Any
    engine_ready_timeout_seconds: float = 930.0
    engine_poll_seconds: float = 0.2
    event_limit: int = 100

    def __post_init__(self) -> None:
        for item in fields(self):
            object.__setattr__(self, item.name, benchmark_evidence._freeze(getattr(self, item.name)))


@dataclass(frozen=True)
class PromotionPolicy:
    plan_ttl_seconds: float


@dataclass(frozen=True)
class PlanningServices:
    _mtplx_long_context_suite_requested: Callable[..., Any]
    active_launcher_operation: Callable[..., Any]
    add_benchmark_engine_evidence: Callable[..., Any]
    benchmark_job_maximum_route_count: Callable[..., Any]
    benchmark_job_measurement_routes: Callable[..., Any]
    benchmark_job_public_modes: Callable[..., Any]
    benchmark_measurement_count: Callable[..., Any]
    best_engine_request: Callable[..., Any]
    normalized_request: Callable[..., Any]
    dispose_plan_secrets: Callable[..., Any]
    prepare_calibration_tuning_plan: Callable[..., Any]
    prepare_engine_settings_sweep: Callable[..., Any]
    require_live_model_load_admission: Callable[..., Any]
    route_qualification_admission_ready: Callable[..., Any]
    route_qualification_memory_admission: Callable[..., Any]
    validated_benchmark_request: Callable[..., Any]
    validated_dflash2_tuning_request: Callable[..., Any]
    validated_engine_shootout_request: Callable[..., Any]
    validated_lmstudio_mtp_tuning_request: Callable[..., Any]
    validated_optimizer_evidence_binding: Callable[..., Any]
    validated_route_qualification_request: Callable[..., Any]


@dataclass(frozen=True)
class WorkloadServices:
    benchmark_agentic_cases: Callable[..., Any]
    benchmark_prompt: Callable[..., Any]
    run_benchmark_completion: Callable[..., Any]
    run_route_check_request: Callable[..., Any]
    uzu_conversation_case: Callable[..., Any]
    validate_uzu_qualification_sample: Callable[..., Any]


@dataclass(frozen=True)
class ResourceServices:
    apple_resource_snapshot: Callable[..., Any]
    benchmark_resource_condition: Callable[..., Any]
    compare_benchmark_resource_condition: Callable[..., Any]
    benchmark_system_memory_violation: Callable[..., Any]
    hardware_fingerprint: Callable[..., Any]
    telemetry_sampler: Callable[..., TelemetrySampler]
    clean_unload: Callable[[BenchmarkPlan, Any, int | None, list[int]], dict[str, Any]]


@dataclass(frozen=True)
class ControlsServices:
    _ordered_unique: Callable[..., Any]
    bounded_integer: Callable[..., Any]
    safe_int: Callable[..., Any]
    dflash2_tuning_candidate_key: Callable[..., Any]
    lmstudio_mtp_controls: Callable[..., Any]
    lmstudio_mtp_tuning_candidate_key: Callable[..., Any]


@dataclass(frozen=True)
class PresentationServices:
    benchmark_acceleration_reason: Callable[..., Any]
    benchmark_engine_settings_label: Callable[..., Any]
    benchmark_mode_summary: Callable[..., Any]
    benchmark_public_mode_label: Callable[..., Any]
    benchmark_route_settings_label: Callable[..., Any]
    public_benchmark_settings_search_result: Callable[..., Any]
    public_route_qualification_result: Callable[..., Any]
    cross_engine_benchmark_measurement: Callable[..., Any]
    cross_engine_workload_compatibility: Callable[..., Any]
    route_qualification_metrics: Callable[..., Any]
    route_qualification_sample_tokens: Callable[..., Any]
    summarize_agentic_samples: Callable[..., Any]


@dataclass(frozen=True)
class StoreServices:
    save_benchmark_record: Callable[..., Any]
    save_benchmark_records: Callable[..., Any]


@dataclass(frozen=True)
class BenchmarkServices:
    planning: PlanningServices
    workload: WorkloadServices
    resource: ResourceServices
    controls: ControlsServices
    presentation: PresentationServices
    store: StoreServices


@dataclass(frozen=True)
class PromotionServices:
    _benchmark_created_at: Callable[..., Any]
    build_runtime_promotion_plan: Callable[..., Any]
    build_runtime_promotion_result: Callable[..., Any]
    runtime_promotion_public_plan: Callable[..., Any]
    runtime_candidate_details: Callable[..., Any]
    runtime_executable_revision: Callable[..., Any]
    managed_runtime_verification: Callable[..., Any]
    load_runtime_promotion_records: Callable[..., Any]
    save_runtime_promotion_record: Callable[..., Any]
    select_runtime_candidate: Callable[..., Any]
    selected_runtime: Callable[[], str | None]


def _mutable_policy_copy(value: Any) -> Any:
    """Public records get detached JSON containers, never frozen policy views."""
    if isinstance(value, Mapping):
        return {key: _mutable_policy_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_mutable_policy_copy(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_mutable_policy_copy(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return type(value)(_mutable_policy_copy(item) for item in value)
    return copy.deepcopy(value)


class BenchmarkManager:
    ACTIVE_PHASES = {"queued", "cooldown", "starting", "running", "stopping"}

    def __init__(self, owner: RunOwnerPort, policy: BenchmarkPolicy, services: BenchmarkServices, evidence: EvidencePort, errors: BenchmarkErrors = BenchmarkErrors()) -> None:
        self.owner = owner
        self.policy = policy
        self.services = services
        self.evidence = evidence
        self.errors = errors
        self.lock = threading.RLock()
        self.cancel_event = threading.Event()
        self.qualification_safety_violation: str | None = None
        self.thread: threading.Thread | None = None
        self.active_plan: BenchmarkPlan | None = None
        self.state: dict[str, Any] = {
            "phase": "idle", "message": "No benchmark is running.",
            "progress": 0.0, "job": None, "modes": {}, "result": None, "events": [],
        }

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return json.loads(json.dumps(self.state))

    def is_active(self) -> bool:
        with self.lock:
            return self.state.get("phase") in self.ACTIVE_PHASES or bool(self.thread and self.thread.is_alive())

    def _event(self, message: str, level: str = "info") -> None:
        with self.lock:
            self.state["message"] = message
            self.state["events"] = (
                self.state.get("events", [])
                + [{"time": time.strftime("%H:%M:%S"), "level": level, "message": message}]
            )[-self.policy.event_limit:]

    def _start_thread(self, thread: threading.Thread) -> None:
        """A refused worker cannot leave an admitted job permanently queued."""
        try:
            thread.start()
        except Exception as error:
            self.thread = None
            self.state["phase"] = "failed"
            self._event(str(error), "error")
            raise

    def start(self, payload: dict[str, Any], models: list[dict[str, Any]]) -> dict[str, Any]:
        scope = str(payload.get("scope") or "current")
        if scope not in {"current", "engines", "qualification", "mtp-tune", "dflash-tune"}:
            raise ValueError("Unknown Benchmark Lab scope.")
        shootout = self.services.planning.validated_engine_shootout_request(payload, models) if scope == "engines" else None
        qualification = (
            self.services.planning.validated_route_qualification_request(payload, models)
            if scope == "qualification" else None
        )
        tuning_job = None
        if scope == "mtp-tune":
            tuning_job = self.services.planning.validated_lmstudio_mtp_tuning_request(payload, models)
        elif scope == "dflash-tune":
            tuning_job = self.services.planning.validated_dflash2_tuning_request(payload, models)
        job = None if shootout or qualification or tuning_job else self.services.planning.validated_benchmark_request(payload, models)
        if (
            job is not None and job["backend"] == "mtplx"
            and job.get("options", {}).get("profile") == "turbo"
            and self.services.planning._mtplx_long_context_suite_requested(
                job["model"], job["context"], job["suiteName"],
            )
        ):
            # Current-engine Agentic runs must exercise the same audited
            # operators as Calibration, without starting other engines or
            # silently changing a user's Sustained profile to Turbo.
            self.services.planning.prepare_calibration_tuning_plan(job)
        if self.owner.snapshot().get("phase") != "idle":
            raise ValueError("Stop the active launcher run before starting Benchmark Lab.")
        if qualification:
            hub = self.owner.snapshot()
            admission = self.services.planning.route_qualification_memory_admission(
                qualification["request"], models, hub=hub,
                operation=self.services.planning.active_launcher_operation(hub),
            )
            if not self.services.planning.route_qualification_admission_ready(admission):
                raise ValueError(
                    f"{admission.get('label') or 'Qwen route is not loadable'}: "
                    f"{admission.get('detail') or 'refresh capacity before qualification.'}"
                )
            qualification["memoryAdmission"] = admission
        with self.lock:
            if self.is_active():
                raise ValueError("A benchmark is already running.")
            self.cancel_event = threading.Event()
            self.qualification_safety_violation = None
            if shootout:
                public_job = {
                    "id": shootout["id"], "kind": shootout["kind"],
                    "client": shootout["client"], "modelId": shootout["modelId"],
                    "model": shootout["model"], "suite": shootout["suite"],
                    "suiteLabel": shootout["suiteLabel"],
                    "workloadKind": shootout["workloadKind"],
                    "enginePreference": shootout["enginePreference"],
                    "enginePreferenceLabel": self.policy.engine_preference_labels[shootout["enginePreference"]],
                    "ssdStreaming": shootout.get("ssdStreaming") is True,
                    "ssdContract": copy.deepcopy(shootout.get("ssdContract")),
                    "reasoningContract": copy.deepcopy(shootout["reasoningContract"]),
                    "executionOrder": list(shootout["executionOrder"]),
                    "orderStrategy": shootout["orderStrategy"],
                    "resourceCooldown": {
                        "version": 1,
                        "maxWaitSeconds": self.policy.benchmark_cooldown_max_seconds,
                        "stableSamplesRequired": self.policy.benchmark_cooldown_stable_samples,
                        "memoryToleranceBytes": self.policy.benchmark_cooldown_memory_tolerance_bytes,
                    },
                    "engines": [
                        {
                            "backend": item["backend"],
                            "label": self.policy.backend_labels[item["backend"]],
                            "modes": self.services.planning.benchmark_job_public_modes(item),
                            "measurementRouteCount": self.services.planning.benchmark_job_maximum_route_count(item),
                        }
                        for item in shootout["jobs"]
                    ],
                    "excludedEngines": shootout["excludedEngines"],
                }
                engine_state = {
                    item["backend"]: {
                        "backend": item["backend"],
                        "label": self.policy.backend_labels[item["backend"]],
                        "phase": "queued", "modes": {}, "record": None,
                    }
                    for item in shootout["jobs"]
                }
                self.state = {
                    "phase": "queued",
                    "message": (
                        "Engine Shootout accepted. Preparing "
                        f"{self.policy.backend_labels[shootout['executionOrder'][0]]} first in this rotated run…"
                    ),
                    "progress": 0.0, "job": public_job, "modes": {},
                    "engines": engine_state, "result": None, "events": [],
                }
                thread = threading.Thread(
                    target=self._shootout_worker, args=(shootout, models), daemon=True,
                )
                self.thread = thread
                self._start_thread(thread)
                return copy.deepcopy(public_job)
            if qualification:
                qualification_job = qualification["job"]
                qualification_backend = str(qualification_job["backend"])
                route_spec = qualification["routeSpec"]
                public_job = {
                    "id": qualification["id"], "kind": qualification["kind"],
                    "client": qualification["client"], "modelId": qualification["modelId"],
                    "model": qualification["model"], "suite": qualification["suite"],
                    "suiteLabel": qualification["suiteLabel"],
                    "workloadKind": qualification["workloadKind"],
                    "enginePreference": qualification["enginePreference"],
                    "enginePreferenceLabel": self.policy.engine_preference_labels[qualification["enginePreference"]],
                    "reasoningContract": copy.deepcopy(qualification["reasoningContract"]),
                    "routeQualification": True,
                    "qualificationContract": copy.deepcopy(qualification["qualificationContract"]),
                    "reasoningBudget": {
                        "sampleMaxTokens": int(qualification_job["suite"]["maxTokens"]),
                        "thinkingMaxTokens": int(qualification_job["qualificationThinkingBudgetTokens"]),
                        "answerReserveTokens": int(qualification_job["qualificationAnswerReserveTokens"]),
                        "visibleResponseLimit": int(qualification_job["output"]),
                    },
                    "memoryAdmission": copy.deepcopy(qualification.get("memoryAdmission")),
                    "executionOrder": [qualification_backend],
                    "engines": [{
                        "backend": qualification_backend, "label": self.policy.backend_labels[qualification_backend],
                        "modes": self.services.planning.benchmark_job_public_modes(qualification_job),
                        "measurementRouteCount": 1,
                    }],
                    "excludedEngines": copy.deepcopy(qualification["excludedEngines"]),
                    "resourceCooldown": {
                        "version": 1,
                        "maxWaitSeconds": self.policy.benchmark_cooldown_max_seconds,
                        "stableSamplesRequired": self.policy.benchmark_cooldown_stable_samples,
                        "memoryToleranceBytes": self.policy.benchmark_cooldown_memory_tolerance_bytes,
                    },
                }
                self.state = {
                    "phase": "queued",
                    "message": f"Route qualification accepted. Preparing the exact {route_spec['routeLabel']}…",
                    "progress": 0.0, "job": public_job, "modes": {},
                    "engines": {
                        qualification_backend: {
                            "backend": qualification_backend, "label": self.policy.backend_labels[qualification_backend],
                            "phase": "queued", "modes": {}, "record": None,
                        },
                    },
                    "result": None, "events": [],
                }
                thread = threading.Thread(
                    target=self._qualification_worker,
                    args=(qualification, models), daemon=True,
                )
                self.thread = thread
                self._start_thread(thread)
                return copy.deepcopy(public_job)
            if tuning_job:
                dflash_tuning = tuning_job["kind"] == "omlx-dflash2-tuning"
                public_job = {
                    "id": tuning_job["id"], "kind": tuning_job["kind"],
                    "backend": tuning_job["backend"], "client": tuning_job["client"],
                    "modelId": tuning_job["modelId"], "model": tuning_job["model"]["name"],
                    "suite": tuning_job["suiteName"],
                    "suiteLabel": tuning_job["suite"]["label"],
                    "workloadKind": tuning_job["workloadKind"],
                    "promptTokens": tuning_job["suite"]["promptTokens"],
                    "maxTokens": tuning_job["suite"]["maxTokens"],
                    "modes": list(tuning_job["modes"]),
                    "tuningPlan": copy.deepcopy(tuning_job["tuningPlan"]),
                }
                self.state = {
                    "phase": "queued",
                    "message": (
                        "DFlash 2 tuning accepted. Preparing the AR reference route…"
                        if dflash_tuning else
                        "MTP tuning accepted. Preparing the AR reference route…"
                    ),
                    "progress": 0.0, "job": public_job, "modes": {}, "engines": {},
                    "result": None, "events": [], "tuning": {"candidates": []},
                }
                thread = threading.Thread(
                    target=(
                        self._dflash_tuning_worker if dflash_tuning
                        else self._mtp_tuning_worker
                    ),
                    args=(tuning_job, models), daemon=True,
                )
                self.thread = thread
                self._start_thread(thread)
                return copy.deepcopy(public_job)
            assert job is not None
            public_job = {
                "id": job["id"], "backend": job["backend"], "client": job["client"],
                "modelId": job["modelId"], "model": job["model"]["name"],
                "suite": job["suiteName"], "suiteLabel": job["suite"]["label"],
                "workloadKind": job["workloadKind"],
                "promptTokens": job["suite"]["promptTokens"],
                "maxTokens": job["suite"]["maxTokens"], "modes": job["modes"],
            }
            if isinstance(job.get("calibrationTuningPlan"), dict):
                public_job["measurementRoutes"] = self.services.planning.benchmark_job_measurement_routes(job)
                public_job["measurementRouteCount"] = self.services.planning.benchmark_job_maximum_route_count(job)
                public_job["calibrationTuningPlan"] = copy.deepcopy(job["calibrationTuningPlan"])
            self.state = {
                "phase": "queued", "message": "Benchmark accepted. Preparing the first route…",
                "progress": 0.0, "job": public_job, "modes": {}, "engines": {},
                "result": None, "events": [],
            }
            thread = threading.Thread(target=self._worker, args=(job, models), daemon=True)
            self.thread = thread
            self._start_thread(thread)
            return copy.deepcopy(public_job)

    def cancel(self, expected_job_id: str | None = None) -> None:
        with self.lock:
            job = self.state.get("job")
            if expected_job_id is not None and (
                not isinstance(job, dict) or job.get("id") != expected_job_id
            ):
                raise ValueError("The capacity test changed; no other job was stopped.")
            # A worker can still be unwinding its final Python frames after it
            # has atomically published a completed/failed result.  Do not turn
            # that terminal UI state back into "stopping" merely because the
            # thread has not returned yet.
            if self.state.get("phase") not in self.ACTIVE_PHASES:
                return
            self.state["phase"] = "stopping"
            self.state["message"] = "Stopping Benchmark Lab…"
            self.cancel_event.set()
            plan = self.active_plan
        if plan is not None and self.owner.owns_plan(plan):
            self.owner.stop(expected_plan=plan)

    @staticmethod
    def _resource_condition_text(condition: dict[str, Any]) -> str:
        parts: list[str] = []
        if condition.get("thermalAvailable") is True:
            parts.append(f"thermal {condition.get('thermalState')}")
        if condition.get("memoryAvailable") is True:
            parts.append(f"memory headroom {float(condition.get('headroomPercent') or 0):.0f}%")
        if isinstance(condition.get("lowPowerMode"), bool):
            parts.append("Low Power Mode on" if condition["lowPowerMode"] else "Low Power Mode off")
        return " · ".join(parts) or "resource signals unavailable"

    def _resource_comparison_text(self, 
        reference: dict[str, Any], observed: dict[str, Any], readiness: dict[str, Any],
    ) -> str:
        """Describe a route start against the fixed shootout reference."""
        parts: list[str] = []
        delta = readiness.get("memoryDeltaBytes")
        if isinstance(delta, int) and not isinstance(delta, bool):
            if delta == 0:
                parts.append("memory headroom matched the fixed reference")
            else:
                direction = "more" if delta > 0 else "less"
                parts.append(
                    f"memory headroom {abs(delta) / 1024**3:.2f} GiB {direction} than the "
                    f"fixed reference ({self.policy.benchmark_cooldown_memory_tolerance_bytes / 1024**3:.1f} GiB allowed)"
                )
        elif reference.get("memoryAvailable") is True:
            parts.append("memory headroom could not be compared with the fixed reference")
        if (
            reference.get("thermalAvailable") is True
            and observed.get("thermalAvailable") is True
        ):
            parts.append(
                f"thermal {observed.get('thermalState')} vs fixed reference "
                f"{reference.get('thermalState')}"
            )
        elif reference.get("thermalAvailable") is True:
            parts.append("thermal state unavailable against the fixed reference")
        if (
            isinstance(reference.get("lowPowerMode"), bool)
            and isinstance(observed.get("lowPowerMode"), bool)
        ):
            observed_power = "on" if observed["lowPowerMode"] else "off"
            reference_power = "on" if reference["lowPowerMode"] else "off"
            parts.append(
                f"Low Power Mode {observed_power} vs fixed reference {reference_power}"
            )
        elif isinstance(reference.get("lowPowerMode"), bool):
            parts.append("Low Power Mode unavailable against the fixed reference")
        return " · ".join(parts) or "resource comparison signals unavailable"

    def _wait_for_resource_baseline(
        self, route_label: str, backend: str,
        reference: dict[str, Any] | None = None, *,
        max_seconds: float | None = None, sample_seconds: float | None = None,
    ) -> dict[str, Any]:
        """Wait for a stable, comparable route start without making the run unbounded."""
        maximum = self.policy.benchmark_cooldown_max_seconds if max_seconds is None else max(0.0, float(max_seconds))
        interval = self.policy.benchmark_cooldown_sample_seconds if sample_seconds is None else max(0.001, float(sample_seconds))
        started = time.monotonic()
        deadline = started + maximum
        samples = 0
        stable_samples = 0
        improved_samples = 0
        previous: dict[str, Any] | None = None
        raw: dict[str, Any] = {}
        observed: dict[str, Any] = {}
        readiness: dict[str, Any] = {"available": False, "ready": False}
        with self.lock:
            self.state["phase"] = "cooldown"
            engine = self.state.get("engines", {}).get(backend)
            if isinstance(engine, dict):
                engine["phase"] = "cooldown"
        self._event(
            f"Stabilising the Mac before {route_label}; Stop remains available during the bounded wait."
        )
        status = "timeout"
        while True:
            if self.cancel_event.is_set():
                raise self.errors.cancelled("Engine Shootout cancelled during resource cooldown.")
            try:
                raw = self.services.resource.apple_resource_snapshot()
            except Exception:  # noqa: BLE001 - optional signals must not break a benchmark
                raw = {
                    "memoryAvailable": False, "freePercent": None,
                    "thermalAvailable": False, "thermalState": None,
                    "thermalLabel": "unavailable", "lowPowerMode": None,
                    "capturedAt": time.monotonic(),
                }
            observed = self.services.resource.benchmark_resource_condition(raw)
            samples += 1
            if not (
                observed.get("memoryAvailable") is True
                or observed.get("thermalAvailable") is True
                or isinstance(observed.get("lowPowerMode"), bool)
            ):
                status = "unavailable"
                readiness = {"available": False, "ready": False}
                break
            if reference is None:
                nominal = (
                    observed.get("thermalAvailable") is not True
                    or observed.get("thermalStateValue") == 0
                )
                if previous is None:
                    stable_samples = 1 if nominal else 0
                    readiness = {"available": True, "ready": False}
                else:
                    readiness = self.services.resource.compare_benchmark_resource_condition(
                        previous, observed, stability=True,
                    )
                    if nominal and readiness["ready"]:
                        stable_samples += 1
                    else:
                        stable_samples = 1 if nominal else 0
                if stable_samples >= self.policy.benchmark_cooldown_stable_samples:
                    status = "reference-ready"
                    break
            else:
                readiness = self.services.resource.compare_benchmark_resource_condition(reference, observed)
                improved = bool(
                    readiness.get("thermalImproved") or readiness.get("memoryImproved")
                )
                improved_comparable = bool(
                    readiness.get("memoryWithinTolerance") is not False
                    and (
                        readiness.get("thermalMatches") is not False
                        or readiness.get("thermalImproved") is True
                    )
                    and readiness.get("lowPowerModeMatches") is not False
                )
                if improved and improved_comparable:
                    improved_samples += 1
                else:
                    improved_samples = 0
                if readiness["ready"]:
                    stable_samples += 1
                else:
                    stable_samples = 0
                if improved_samples >= self.policy.benchmark_cooldown_stable_samples:
                    status = "condition-improved"
                    break
                if stable_samples >= self.policy.benchmark_cooldown_stable_samples:
                    status = "ready"
                    break
            elapsed = max(0.0, time.monotonic() - started)
            if time.monotonic() >= deadline:
                status = "timeout"
                break
            with self.lock:
                condition = (
                    self._resource_comparison_text(reference, observed, readiness)
                    if reference is not None else
                    self._resource_condition_text(observed)
                )
                self.state["message"] = (
                    f"Stabilising before {route_label} · {condition} · "
                    f"{min(maximum, elapsed):.0f}/{maximum:.0f}s"
                )
            previous = observed
            wait_for = min(interval, max(0.0, deadline - time.monotonic()))
            if self.cancel_event.wait(wait_for):
                raise self.errors.cancelled("Engine Shootout cancelled during resource cooldown.")
        waited = round(max(0.0, time.monotonic() - started), 3)
        baseline = copy.deepcopy(reference if reference is not None else observed)
        condition_detail = (
            self._resource_comparison_text(baseline, observed, readiness)
            if reference is not None else
            self._resource_condition_text(observed)
        )
        gate = {
            "version": 1,
            "status": status,
            "waitedSeconds": waited,
            "sampleCount": samples,
            "stableSamplesRequired": self.policy.benchmark_cooldown_stable_samples,
            "maxWaitSeconds": maximum,
            "memoryToleranceBytes": self.policy.benchmark_cooldown_memory_tolerance_bytes,
            "reference": baseline,
            "observed": copy.deepcopy(observed),
            "readiness": copy.deepcopy(readiness),
            "conditionDetail": condition_detail,
            "_initialSnapshot": copy.deepcopy(raw),
        }
        if status in {"reference-ready", "ready"}:
            self._event(f"Comparable resource baseline ready for {route_label} after {waited:.1f}s.")
        elif status == "unavailable":
            self._event(
                f"Resource cooldown signals were unavailable before {route_label}; measurement will continue without that gate.",
                "warning",
            )
        elif status == "condition-improved":
            self._event(
                f"The Mac's resource conditions improved before {route_label}; the higher-headroom start was recorded and the shared resource gate passed.",
            )
        else:
            self._event(
                f"Resource cooldown reached its {maximum:.0f}s limit before {route_label}; "
                f"{condition_detail}. Measurement will continue and final evidence checks "
                "will fail closed if starts differ.",
                "warning",
            )
        return gate

    def _wait_for_engine(self, plan: BenchmarkPlan) -> None:
        deadline = time.monotonic() + self.policy.engine_ready_timeout_seconds
        while time.monotonic() < deadline:
            safety_failure = (
                self.qualification_safety_violation
                or self.owner.safety_violation(plan)
            )
            if safety_failure:
                raise self.errors.safety(safety_failure)
            if self.cancel_event.wait(self.policy.engine_poll_seconds):
                raise self.errors.cancelled("Benchmark cancelled.")
            status = self.owner.snapshot()
            if status.get("phase") == "running" and self.owner.owns_plan(plan):
                return
            if status.get("phase") == "failed":
                raise RuntimeError(str(status.get("message") or "The benchmark engine failed to start."))
        raise RuntimeError("Benchmark Lab timed out while loading the model.")

    @staticmethod
    def _mode_label(mode: str) -> str:
        return {"ar": "AR", "mtp": "MTP", "dflash2": "DFlash 2"}.get(mode, mode)

    def _mode_settings(self, 
        job: dict[str, Any], mode: str, options: dict[str, Any],
    ) -> dict[str, Any]:
        """Return the complete load-time tuning identity for one measured mode."""
        if mode == "ar":
            return {}
        if mode == "dflash2":
            capability = job["model"]["backends"]["omlx"]
            return self.evidence.dflash2_tuning_controls(options, capability)
        capability = job["model"]["backends"][job["backend"]]
        if job["backend"] == "lmstudio":
            return self.services.controls.lmstudio_mtp_controls(options, capability)
        settings = {
            "depth": self.services.controls.bounded_integer(
                options.get("depth"), int(capability.get("depth") or 1),
                1, int(capability.get("depthMax") or 1), "MTP draft depth",
            )
        }
        tuning = job.get("calibrationTuningPlan")
        if (
            job["backend"] == "mtplx"
            and isinstance(tuning, dict)
            and tuning.get("strategy")
            == "isolated-long-context-operator-comparison"
        ):
            route = str(
                options.get("mtplxOperatorRoute")
                or self.policy.mtplx_long_context_default_route
            )
            if route not in {
                self.policy.mtplx_long_context_default_route,
                self.policy.mtplx_long_context_2111_route,
            }:
                raise ValueError("Unknown MTPLX operator benchmark route.")
            settings["mtplxOperatorRoute"] = route
        return settings

    def _mode_payload(self, job: dict[str, Any], mode: str) -> dict[str, Any]:
        options = copy.deepcopy(job["options"])
        options["acceleration"] = {"ar": "off", "mtp": "mtp", "dflash2": "dflash"}[mode]
        if mode == "dflash2":
            capability = job["model"]["backends"]["omlx"]
            forced = job.get("_benchmarkDflashSettings")
            if isinstance(forced, dict):
                controls = self.evidence.dflash2_tuning_controls(forced, capability)
                options.update({
                    "depth": controls["blockSize"],
                    "dflashDraftQuant": controls["draftQuant"],
                    "dflashVerify": controls["verifyMode"],
                })
            else:
                requested_depth = None if job.get("shootoutId") else options.get("depth")
                options["depth"] = self.services.controls.safe_int(
                    requested_depth, int(capability.get("dflashBlockSize") or 8),
                    1, int(capability.get("dflashMaxBlockSize") or 8),
                )
                options.setdefault("dflashDraftQuant", "native")
                options.setdefault("dflashVerify", "adaptive")
        elif mode == "mtp":
            capability = job["model"]["backends"][job["backend"]]
            if job["backend"] == "lmstudio":
                forced = job.get("_benchmarkMtpSettings")
                requested = (
                    forced if isinstance(forced, dict)
                    else {} if job.get("shootoutId") else options
                )
                options.update(self.services.controls.lmstudio_mtp_controls(requested, capability))
            else:
                forced_depth = job.get("_benchmarkMtpDepth")
                requested_depth = (
                    forced_depth
                    if isinstance(forced_depth, int) and not isinstance(forced_depth, bool)
                    else None if job.get("shootoutId") else options.get("depth")
                )
                options["depth"] = self.services.controls.safe_int(
                    requested_depth, int(capability.get("depth") or 1),
                    1, int(capability.get("depthMax") or 1),
                )
                if job["backend"] == "mtplx":
                    forced_route = job.get("_benchmarkMtplxOperatorRoute")
                    if forced_route is not None:
                        options["mtplxOperatorRoute"] = str(forced_route)
        payload = {
            "backend": job["backend"], "client": "chat", "modelId": job["modelId"],
            "project": job["project"], "context": job["context"], "output": job["output"],
            "reasoning": job["reasoning"], "mode": "custom", "options": options,
            "chat": job["chat"],
        }
        if job.get("routeQualification") is True:
            options["_qualificationThinkingBudgetTokens"] = int(
                job["qualificationThinkingBudgetTokens"]
            )
            options["_qualificationAnswerReserveTokens"] = int(
                job["qualificationAnswerReserveTokens"]
            )
        return payload

    def _update_progress(
        self, completed: int, total: int, message: str,
        live_metric: dict[str, Any] | None = None,
    ) -> None:
        with self.lock:
            self.state["progress"] = round(completed / max(1, total), 4)
            if live_metric is not None:
                self.state["liveMetric"] = copy.deepcopy(live_metric)
        self._event(message)

    def _measure_mode(
        self, job: dict[str, Any], models: list[dict[str, Any]], mode: str,
        completed: int, total: int, resource_gate: dict[str, Any] | None = None,
        *, display_label: str | None = None, state_key: str | None = None,
    ) -> tuple[dict[str, Any], int]:
        label = display_label or self._mode_label(mode)
        if (
            job["backend"] in {"llamacpp", "uzu"}
            and job.get("routeQualification") is not True
        ):
            raise RuntimeError(
                f"The {self.policy.backend_labels[job['backend']]} route can load for Benchmark Lab only "
                "through its dedicated qualification."
            )
        shootout = bool(job.get("shootoutId"))
        grouped = shootout or job.get("routeQualification") is True
        route_label = (
            f"{self.policy.backend_labels[job['backend']]} · {label}" if grouped else label
        )
        with self.lock:
            self.state["phase"] = "starting"
            self.state["liveMetric"] = None
            if grouped and job["backend"] in self.state.get("engines", {}):
                self.state["engines"][job["backend"]]["phase"] = "starting"
        self._event(f"Loading {route_label} for a cache-isolated benchmark pass…")
        promotion = bool(job.get("runtimePromotionId"))
        mode_payload = self._mode_payload(job, mode)
        plan = self.services.planning.normalized_request(
            mode_payload, models,
            purpose="runtime-promotion" if promotion else "benchmark",
            runtime_binary=str(job.get("_runtimeBinary")) if promotion else None,
        )
        admission_purpose = (
            "route-qualification"
            if job.get("routeQualification") is True else
            "runtime-promotion" if promotion else "benchmark"
        )
        try:
            admission = self.services.planning.require_live_model_load_admission(
                mode_payload, models, purpose=admission_purpose,
                hub=self.owner.snapshot(),
            )
        except BaseException:
            self.services.planning.dispose_plan_secrets(plan)
            raise
        with self.lock:
            if isinstance(self.state.get("job"), dict):
                self.state["job"]["memoryAdmission"] = copy.deepcopy(admission)
        strict_llama = bool(
            job.get("routeQualification") is True and job["backend"] == "llamacpp"
        )
        strict_uzu = bool(
            job.get("routeQualification") is True and job["backend"] == "uzu"
        )
        core_engine_memory_guard = job["backend"] in {"omlx", "lmstudio", "mtplx"}
        uzu_memory_samples = {"missing": 0, "low": 0}
        core_memory_samples = {"missing": 0, "low": 0}

        def live_invariant(value: dict[str, Any]) -> None:
            def abort(message: str) -> None:
                with self.lock:
                    self.qualification_safety_violation = message
                threading.Thread(
                    target=self.owner.stop, kwargs={"expected_plan": plan}, daemon=True,
                ).start()
                raise self.errors.safety(message)

            if value.get("timingDiscontinuity"):
                abort(str(value["timingDiscontinuity"]))
            if core_engine_memory_guard:
                # LM Studio's model belongs to its desktop service; its CLI may
                # have exited or there may be no child PID yet during loading.
                # Whole-Mac protection must follow the owned run, not a child.
                if self.owner.owns_plan(plan):
                    reason = self.services.resource.benchmark_system_memory_violation(
                        value, core_memory_samples,
                        f"the {self.policy.backend_labels[job['backend']]} benchmark",
                    )
                    if reason:
                        abort(reason)
                return
            process = self.owner.process_for(plan)
            if not (strict_llama or strict_uzu) or process is None or process.poll() is not None:
                return
            if strict_llama and value.get("metalWiredLimitBytes") != self.policy.llamacpp_ple_memory_ceiling_bytes:
                abort("The 44 GiB Metal wired-memory limit changed during qualification.")
            if strict_uzu:
                reason = self.services.resource.benchmark_system_memory_violation(value, uzu_memory_samples, "Uzu qualification")
                if reason:
                    abort(reason)
            footprint = value.get("processGroupPhysicalFootprintBytes")
            lifetime_peak = value.get("processGroupLifetimePeakPhysicalFootprintBytes")
            if (
                value.get("processFootprintAvailable") is not True
                or
                value.get("processGroupFootprintAvailable") is not True
                or not isinstance(value.get("processGroupMemberCount"), int)
                or isinstance(value.get("processGroupMemberCount"), bool)
                or int(value.get("processGroupMemberCount")) < 1
                or (strict_llama and value.get("processGroupMemberCount") != 1)
                or not isinstance(footprint, int) or isinstance(footprint, bool)
                or not isinstance(lifetime_peak, int) or isinstance(lifetime_peak, bool)
            ):
                abort("The owned process-group physical footprint became unreadable during qualification.")
            ceiling = (
                self.policy.llamacpp_ple_memory_ceiling_bytes
                if strict_llama else self.policy.uzu_process_memory_ceiling_bytes
            )
            if max(footprint, lifetime_peak) >= ceiling:
                abort(
                    f"The owned process group reached the strict {ceiling / 1024**3:.0f} GiB "
                    "qualification ceiling."
                )

        try:
            telemetry = self.services.resource.telemetry_sampler(
                process_provider=lambda: self.owner.process_for(plan),
                invariant_callback=live_invariant,
            )
        except BaseException:
            self.services.planning.dispose_plan_secrets(plan)
            raise

        def measured_completion(*args: Any, **kwargs: Any) -> dict[str, Any]:
            try:
                measured = self.services.workload.run_benchmark_completion(*args, **kwargs)
            except Exception as error:
                safety_failure = (
                    self.qualification_safety_violation
                    or self.owner.safety_violation(plan)
                    or telemetry.violation
                )
                if safety_failure:
                    raise self.errors.safety(safety_failure) from error
                raise
            safety_failure = (
                self.qualification_safety_violation
                or self.owner.safety_violation(plan)
                or telemetry.violation
            )
            if safety_failure:
                raise self.errors.safety(safety_failure)
            return measured
        generation_required = bool(
            job.get("routeQualification") is True
            or self.evidence.benchmark_route_selection_metric(job) == "generation-tokens-per-second"
        )

        def validate_measurement(sample: dict[str, Any]) -> None:
            if sample.get("responseOutcome") not in {None, "completed", "truncated"}:
                raise RuntimeError("Incomplete or invalid benchmark response")
            if not self.evidence._positive_finite_number(sample.get("endToEndTokensPerSecond")):
                raise RuntimeError("No authoritative end-to-end timing measurement")
            if generation_required and generation_metrics.sample_generation_tps(sample, str(job["backend"])) is None:
                raise RuntimeError(sample.get("timingInvalidReason") or "No valid native generation measurement for this goal")

        def generation_note(sample: dict[str, Any]) -> str:
            speed = generation_metrics.sample_generation_tps(sample, str(job["backend"]))
            return f"{speed:.1f} generation tok/s" if speed is not None else "generation timing not available"

        gate = copy.deepcopy(resource_gate) if isinstance(resource_gate, dict) else None
        initial_sample = gate.pop("_initialSnapshot", None) if gate else None
        try:
            telemetry.start(initial_sample if isinstance(initial_sample, dict) else None)
        except BaseException:
            try:
                telemetry.stop()
            finally:
                self.services.planning.dispose_plan_secrets(plan)
            raise
        with self.lock:
            self.active_plan = plan
        result: dict[str, Any] | None = None
        tool_contract: dict[str, Any] | None = None
        conversation: list[dict[str, str]] = []
        captured_reply: list[dict[str, str]] = []
        run_manager_accepted_plan = False
        try:
            self.owner.start(plan)
            run_manager_accepted_plan = True
            self._wait_for_engine(plan)
            with self.lock:
                self.state["phase"] = "running"
                if grouped and job["backend"] in self.state.get("engines", {}):
                    self.state["engines"][job["backend"]]["phase"] = "running"
            measured_completion(
                plan, self.services.workload.benchmark_prompt(128, 11_000 + job["modes"].index(mode)), 32,
                {"temperature": 0.0, "top_p": 1.0, "top_k": 0, "seed": 17},
                self.cancel_event,
                greedy_probe=plan.backend != "uzu",
            )
            completed += 1
            self._update_progress(completed, total, f"{route_label} warm-up complete.")
            llama_qualification = bool(
                job.get("routeQualification") is True and job["backend"] == "llamacpp"
            )
            uzu_qualification = bool(
                job.get("routeQualification") is True and job["backend"] == "uzu"
            )
            reliability_qualification = llama_qualification or uzu_qualification
            correctness_prompt: str | list[dict[str, str]] = (
                [
                    {
                        "role": "system",
                        "content": (
                            "This is a generated local reliability check. Calculate silently, then "
                            "return only the requested nonce and integer with no punctuation or explanation."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Compute (37 * 19) + 39. Reply exactly as "
                            + ("RQ-8K-<integer>." if llama_qualification else "RQ-UZU-<integer>.")
                        ),
                    },
                ]
                if reliability_qualification else self.services.workload.benchmark_prompt(256, 71_771)
            )
            quality = measured_completion(
                plan, correctness_prompt,
                self.services.presentation.route_qualification_sample_tokens(plan.backend, int(job["output"])) if reliability_qualification else 64,
                {"temperature": 0.0, "top_p": 1.0, "top_k": 0, "seed": 17},
                self.cancel_event,
                correctness_expected=(
                    self.policy.llamacpp_qualification_correctness_expected
                    if llama_qualification else
                    self.policy.uzu_qualification_correctness_expected
                    if uzu_qualification else None
                ),
                reasoning_budget_tokens=(0 if llama_qualification else None),
                greedy_probe=not uzu_qualification,
            )
            if llama_qualification:
                boundary = quality.get("correctnessContract")
                if not (
                    isinstance(boundary, dict)
                    and boundary.get("reasoningBoundaryContractId")
                    == self.policy.llamacpp_qualification_reasoning_boundary_id
                    and boundary.get("reasoningBudgetTokensRequested") == 0
                    and boundary.get("reasoningBudgetMessageSha256")
                    == hashlib.sha256(
                        self.policy.llamacpp_qwen_reasoning_budget_message.encode("utf-8")
                    ).hexdigest()
                    and boundary.get("reasoningBoundaryClean") is True
                    and boundary.get("reasoningTagLeakDetected") is False
                    and boundary.get("transitionMessageLeakDetected") is False
                ):
                    raise RuntimeError(
                        "The forced Qwen reasoning boundary leaked into the visible answer; "
                        "the route was not qualified."
                    )
            completed += 1
            correctness_label = "Model-default" if uzu_qualification else "Greedy"
            self._update_progress(completed, total, f"{route_label}: {correctness_label} correctness probe complete.")
            samples: list[dict[str, Any]] = []
            if job["workloadKind"] == "agentic":
                for case in self.services.workload.benchmark_agentic_cases(
                    job["suite"],
                    require_complete_answer=job.get("routeQualification") is True,
                ):
                    if uzu_qualification:
                        case = self.services.workload.uzu_conversation_case(
                            case, conversation, samples[-1] if samples else None,
                            int(job["context"]), int(job["suite"]["maxTokens"]),
                        )
                    captured_reply.clear()
                    request_tokens = int(case.get("maxTokens", job["suite"]["maxTokens"]))
                    self._update_progress(
                        completed, total,
                        f"{route_label}: running {case['label']} "
                        f"(target {int(case['targetPromptTokens']):,} prompt tokens). "
                        f"Up to {request_tokens:,} output tokens. TPS updates when this turn completes.",
                    )
                    sample = measured_completion(
                        plan, case["messages"],
                        request_tokens, job["speedSampling"], self.cancel_event,
                        **({"reply_observer": captured_reply.append} if uzu_qualification else {}),
                    )
                    sample.update({
                        "scenario": case["scenario"], "scenarioLabel": case["label"],
                        "cacheExpected": case["cacheExpected"],
                        "targetPromptTokens": case["targetPromptTokens"], "repetition": 1,
                    })
                    if uzu_qualification:
                        self.services.workload.validate_uzu_qualification_sample(sample, case, request_tokens)
                        if len(captured_reply) != 1:
                            raise RuntimeError("Uzu's completed reply could not be retained for the next turn.")
                        conversation[:] = [*case["messages"], captured_reply.pop()]
                    if (
                        job.get("suiteName") == self.policy.mtplx_long_context_64k_suite
                        and case["scenario"] in {"toolIngest", "steadyTurn"}
                        and (
                            sample.get("authoritativeUsage") is not True
                            or int(sample.get("promptTokens") or 0)
                            < self.policy.mtplx_long_context_minimum_prompt
                            or int(sample.get("promptTokens") or 0)
                            + int(job["suite"]["maxTokens"]) > int(job["context"])
                        )
                    ):
                        raise RuntimeError(
                            "The MTPLX long-context route did not return authoritative "
                            "near-64K prompt usage within the selected context."
                        )
                    qualification_context = job.get("qualificationContract", {}).get(
                        "exactContext"
                    )
                    if (
                        job.get("routeQualification") is True
                        and isinstance(qualification_context, int)
                        and not isinstance(qualification_context, bool)
                        and int(sample["promptTokens"]) + request_tokens
                        > qualification_context
                    ):
                        raise RuntimeError(
                            "The authoritative prompt usage plus bounded answer reserve exceeded "
                            "the exact qualified context."
                        )
                    validate_measurement(sample)
                    samples.append(sample)
                    completed += 1
                    cached = sample.get("cachedPromptTokens")
                    cache_note = (
                        f" · {int(cached):,} cached prompt tokens"
                        if cached is not None else " · cache telemetry not reported"
                    )
                    first_output_note = f"{sample['ttftSeconds']:.2f}s" if self.evidence._positive_finite_number(sample.get("ttftSeconds")) else "not separately measured"
                    self._update_progress(
                        completed, total,
                        f"{route_label}: {case['label']} reached first output in "
                        f"{first_output_note} · {generation_note(sample)}{cache_note}.",
                        {
                            "backend": job["backend"], "backendLabel": self.policy.backend_labels[job["backend"]],
                            "mode": mode, "modeLabel": label, "stageLabel": case["label"],
                            "decodeTokensPerSecond": sample["decodeTokensPerSecond"],
                            "endToEndTokensPerSecond": sample["endToEndTokensPerSecond"],
                        },
                    )
            else:
                for prompt_index, target in enumerate(job["suite"]["promptTokens"]):
                    for repetition in range(int(job["suite"]["repetitions"])):
                        sample = measured_completion(
                            plan,
                            self.services.workload.benchmark_prompt(int(target), 90_000 + prompt_index * 101 + repetition),
                            int(job["suite"]["maxTokens"]), job["speedSampling"], self.cancel_event,
                        )
                        sample.update({"targetPromptTokens": int(target), "repetition": repetition + 1})
                        validate_measurement(sample)
                        samples.append(sample)
                        completed += 1
                        self._update_progress(
                            completed, total,
                            f"{route_label}: measured {sample['promptTokens']:,} prompt tokens at "
                            f"{generation_note(sample)} · "
                            f"{sample['endToEndTokensPerSecond']:.1f} end-to-end tok/s.",
                            {
                                "backend": job["backend"], "backendLabel": self.policy.backend_labels[job["backend"]],
                                "mode": mode, "modeLabel": label,
                                "stageLabel": f"{sample['promptTokens']:,} prompt tokens",
                                "decodeTokensPerSecond": sample["decodeTokensPerSecond"],
                                "endToEndTokensPerSecond": sample["endToEndTokensPerSecond"],
                            },
                        )
            qualification_contract = job.get("qualificationContract")
            safety_failure = (
                self.qualification_safety_violation
                or self.owner.safety_violation(plan)
                or telemetry.violation
            )
            if safety_failure:
                raise self.errors.safety(safety_failure)
            if (
                isinstance(qualification_contract, dict)
                and qualification_contract.get("toolProbeRequired") is True
            ):
                probe = self.services.workload.run_route_check_request(
                    plan, self.cancel_event, tool_probe=True,
                )
                tool_contract = {
                    "protocol": probe.get("protocol"),
                    "toolContractValid": probe.get("toolContractValid") is True,
                    "toolCallCount": probe.get("toolCallCount"),
                    "toolNameSeen": probe.get("toolNameSeen") is True,
                    "terminalComplete": probe.get("terminalComplete") is True,
                    "thinkingBudgetTokensRequested": probe.get("thinkingBudgetTokensRequested"),
                    "reasoningBudgetMessageSha256": probe.get("reasoningBudgetMessageSha256"),
                    "toolContractDetail": str(probe.get("toolContractDetail") or "")[:400],
                }
                if not (
                    tool_contract["toolContractValid"] is True
                    and tool_contract["toolCallCount"] == 1
                    and tool_contract["toolNameSeen"] is True
                    and tool_contract["terminalComplete"] is True
                    and tool_contract["thinkingBudgetTokensRequested"] == 32
                    and tool_contract["reasoningBudgetMessageSha256"]
                    == hashlib.sha256(
                        self.policy.llamacpp_qwen_reasoning_budget_message.encode("utf-8")
                    ).hexdigest()
                ):
                    raise RuntimeError(
                        "The same loaded route did not produce the one exact Jinja tool call required for qualification."
                    )
                completed += 1
                self._update_progress(
                    completed, total,
                    f"{route_label}: Jinja tool-call contract verified on the same loaded route.",
                )
            result = {
                "label": label,
                "settings": self._mode_settings(job, mode, plan.options),
                "qualityHash": quality["outputHash"],
                "qualityCompletionTokens": quality["completionTokens"],
                "correctnessContract": copy.deepcopy(quality.get("correctnessContract")),
                "medianTTFT": round(statistics.median(item["ttftSeconds"] for item in samples), 4) if all(self.evidence._positive_finite_number(item.get("ttftSeconds")) for item in samples) else None,
                "medianDecodeTokensPerSecond": generation_metrics.median_generation_tps(samples, str(job["backend"])),
                "medianEndToEndTokensPerSecond": round(statistics.median(item["endToEndTokensPerSecond"] for item in samples), 3),
                "samples": samples,
                "resourceTelemetry": {},
            }
            if tool_contract is not None:
                result["toolContract"] = tool_contract
            if gate is not None:
                result["resourceCooldown"] = gate
            if job["workloadKind"] == "agentic" and all(self.evidence._positive_finite_number(item.get("ttftSeconds")) for item in samples):
                result["agenticMetrics"] = self.services.presentation.summarize_agentic_samples(samples)
            with self.lock:
                if grouped and job["backend"] in self.state.get("engines", {}):
                    self.state["engines"][job["backend"]]["modes"][state_key or mode] = copy.deepcopy(result)
                else:
                    self.state["modes"][state_key or mode] = copy.deepcopy(result)
            return result, completed
        finally:
            conversation.clear()
            captured_reply.clear()
            resource_telemetry: dict[str, Any] = {}
            try:
                resource_telemetry = telemetry.stop()
            finally:
                owned_process = self.owner.process_for(plan)
                try:
                    owned_pgid = os.getpgid(owned_process.pid) if owned_process is not None else None
                except (OSError, ProcessLookupError):
                    owned_pgid = None
                known_ports = list(self.owner.ports_for(plan))
                if run_manager_accepted_plan or self.owner.owns_plan(plan):
                    self.owner.stop(expected_plan=plan)
                    unload = self.services.resource.clean_unload(
                        plan, owned_process, owned_pgid, known_ports,
                    )
                else:
                    # RunManager rejected this plan before taking ownership (for
                    # example, a concurrent launch won the final race). Never stop
                    # that other run, and never leave this plan's bearer file.
                    self.services.planning.dispose_plan_secrets(plan)
                    unload = {}
                if result is not None:
                    result["resourceTelemetry"] = resource_telemetry
                    result["unloadEvidence"] = unload
                with self.lock:
                    if result is not None and benchmark_evidence.unload_receipt_issue(unload, str(job["backend"])) is not None:
                        # Keep failed isolation receipts reviewable in status.
                        if grouped and job["backend"] in self.state.get("engines", {}):
                            self.state["engines"][job["backend"]]["modes"][state_key or mode] = copy.deepcopy(result)
                        else:
                            self.state["modes"][state_key or mode] = copy.deepcopy(result)
                    if self.active_plan is plan:
                        self.active_plan = None
                safety_failure = (
                    self.qualification_safety_violation
                    or self.owner.safety_violation(plan)
                    or telemetry.violation
                )
                if safety_failure:
                    raise self.errors.safety(safety_failure)
                if run_manager_accepted_plan:
                    unload_issue = benchmark_evidence.unload_receipt_issue(unload, str(job["backend"]))
                    if unload_issue is not None:
                        if self.cancel_event.is_set():
                            raise self.errors.cancelled("The benchmark was cancelled before its route unloaded cleanly.")
                        raise RuntimeError(f"The accepted benchmark route did not unload cleanly: {unload_issue} No result was saved and no next route was loaded.")

    def _build_record(self, job: dict[str, Any], results: dict[str, dict[str, Any]]) -> dict[str, Any]:
        baseline = results["ar"]
        baseline_samples = baseline["samples"]
        quality_hash = baseline["qualityHash"]
        selection_metric = self.evidence.benchmark_route_selection_metric(job)
        generation_tps_selection = (
            selection_metric == "generation-tokens-per-second"
        )
        speed_field = (
            "decodeTokensPerSecond"
            if generation_tps_selection else "endToEndTokensPerSecond"
        )
        speedups: dict[str, dict[str, float]] = {"ar": {"median": 1.0, "worst": 1.0}}
        raw_speedups: dict[str, dict[str, float]] = {
            "ar": {"median": 1.0, "worst": 1.0},
        }
        public_modes: dict[str, Any] = {}
        mode_settings: dict[str, dict[str, Any]] = {}
        for mode, result in results.items():
            measured_settings = result.get("settings")
            if isinstance(measured_settings, dict):
                mode_settings[mode] = copy.deepcopy(measured_settings)
            else:
                payload = self._mode_payload(job, mode)
                mode_settings[mode] = self._mode_settings(job, mode, payload["options"])
            public = copy.deepcopy(result)
            public["qualityMatchesAR"] = bool(
                result["qualityHash"] == quality_hash
                and result["qualityCompletionTokens"] == baseline["qualityCompletionTokens"]
            )
            public.pop("qualityHash", None)
            public.pop("settings", None)
            public_modes[mode] = public
            if mode == "ar":
                continue
            ratios = [
                sample[speed_field] / max(base[speed_field], 0.000_001)
                for sample, base in zip(result["samples"], baseline_samples)
            ]
            raw_speedups[mode] = {
                "median": statistics.median(ratios),
                "worst": min(ratios),
            }
            speedups[mode] = {
                "median": round(raw_speedups[mode]["median"], 4),
                "worst": round(raw_speedups[mode]["worst"], 4),
            }
            public_modes[mode]["medianSpeedupVsAR"] = speedups[mode]["median"]
            public_modes[mode]["worstCaseSpeedupVsAR"] = speedups[mode]["worst"]
        eligible = [
            mode for mode in job["modes"] if mode != "ar"
            and results[mode]["qualityHash"] == quality_hash
            and results[mode]["qualityCompletionTokens"] == baseline["qualityCompletionTokens"]
            and raw_speedups[mode]["median"] >= self.policy.benchmark_minimum_speedup
            and raw_speedups[mode]["worst"] >= self.policy.benchmark_minimum_speedup
        ]
        winner = max(eligible, key=lambda mode: raw_speedups[mode]["median"]) if eligible else "ar"
        winner_speedup = speedups[winner]["median"]
        worst_case = speedups[winner]["worst"]
        settings = copy.deepcopy(mode_settings[winner])
        all_samples = [sample for result in results.values() for sample in result["samples"]]
        quality_passed = bool(
            winner == "ar"
            or (
                results[winner]["qualityHash"] == quality_hash
                and results[winner]["qualityCompletionTokens"] == baseline["qualityCompletionTokens"]
            )
        )
        bounded_route_qualification = bool(
            job.get("routeQualification") is True
            and job.get("backend") in {"llamacpp", "uzu"}
        )
        measured_output_limit = (
            int(job["suite"]["maxTokens"])
            if bounded_route_qualification else int(job["output"])
        )
        measured_output_minimum = measured_output_limit
        if bounded_route_qualification and job["backend"] == "uzu":
            measured_output_minimum = min(int(item["requestedMaxTokens"]) for item in all_samples)
            measured_output_limit = max(int(item["requestedMaxTokens"]) for item in all_samples)
        record = {
            "id": job["id"], "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "scope": "local", "backend": job["backend"], "modelId": job["modelId"],
            "modelName": job["model"]["name"], "modelFingerprint": job["modelFingerprint"],
            "runtimeVersion": job["runtimeVersion"], "hardwareFingerprint": self.services.resource.hardware_fingerprint(),
            "suite": job["suiteName"], "workloadKind": job["workloadKind"],
            "scenarioContract": list(job["suite"].get("scenarios") or []),
            "client": (
                "any"
                if job.get("routeQualification") is True and job["backend"] == "llamacpp"
                else job["client"]
            ),
            "reasoning": job["reasoning"],
            "targetKV": job["evidence"]["kv"], "samplingFingerprint": job["evidence"]["samplingFingerprint"],
            **self.evidence.sampling_record_evidence(job["evidence"]),
            "contextMin": job["context"], "contextMax": job["context"],
            "outputMin": measured_output_minimum, "outputMax": measured_output_limit,
            "promptTokensMin": min(item["promptTokens"] for item in all_samples),
            "promptTokensMax": max(item["promptTokens"] for item in all_samples),
            "comparedModes": list(job["modes"]), "modes": public_modes,
            "comparisonContractVersion": self.policy.benchmark_comparison_contract_version,
            "engineSettings": copy.deepcopy(job.get("evidence", {}).get("engineSettings") or {}),
            "modeSettings": mode_settings,
            "qualityFingerprint": quality_hash,
            "qualityCompletionTokens": baseline["qualityCompletionTokens"],
            "baselinePassed": True, "qualityPassed": quality_passed,
            "allQualityPassed": all(
                result["qualityHash"] == quality_hash
                and result["qualityCompletionTokens"] == baseline["qualityCompletionTokens"]
                for result in results.values()
            ),
            "winner": winner, "winnerSpeedup": winner_speedup,
            "worstCaseSpeedup": worst_case, "endToEndSpeedup": winner_speedup,
            "settings": settings, "pairFingerprint": job.get("pairFingerprint"),
            "ssdStreaming": job.get("ssdStreaming") is True,
            "ssdComparisonIdentity": str(job.get("ssdComparisonIdentity") or ""),
            "shootoutId": job.get("shootoutId"),
            "shootoutExecutionOrder": copy.deepcopy(job.get("shootoutExecutionOrder")),
            "shootoutOrderIndex": job.get("shootoutOrderIndex"),
            "shootoutOrderStrategy": job.get("shootoutOrderStrategy"),
            "minimumSpeedup": self.policy.benchmark_minimum_speedup,
            "selectionMetric": (
                selection_metric
            ),
            "selectionPreference": str(job.get("enginePreference") or "fastest"),
            "recommendation": (
                f"Use {self._mode_label(winner)}: it cleared correctness and the "
                f"{self.policy.benchmark_minimum_speedup:.2f}× noise floor"
                + (
                    " across cold, shared-prefix, tool-result, and warm follow-up turns."
                    if job["workloadKind"] == "agentic" else "."
                )
                if winner != "ar" else
                (
                    "Keep AR: no verified acceleration route beat it across every agentic stage by the noise floor."
                    if job["workloadKind"] == "agentic" else
                    "Keep AR: no verified acceleration route beat it across every measured prompt by the noise floor."
                )
            ),
        }
        # Produced only by the corrected worker: correctness/warmup requests use
        # greedy_probe=True, while timed workloads keep the user's sampling.
        if job["backend"] in {"omlx", "lmstudio", "mtplx"}:
            record["probeContract"] = _mutable_policy_copy(self.policy.benchmark_probe_contract)
        if bounded_route_qualification:
            record.update({
                "configuredOutputLimit": int(job["output"]),
                "measuredRequestMaxTokens": measured_output_limit,
            })
        if job.get("routeQualification") is True:
            record.update({
                "kind": "route-qualification",
                "qualificationVersion": self.policy.route_qualification_version,
                "qualificationContract": copy.deepcopy(job.get("qualificationContract")),
                "toolContract": copy.deepcopy(baseline.get("toolContract")),
                "correctnessContract": copy.deepcopy(baseline.get("correctnessContract")),
                "unloadEvidence": copy.deepcopy(baseline.get("unloadEvidence")),
            })
            metrics = self.services.presentation.route_qualification_metrics(record)
            if metrics is None:
                raise RuntimeError(
                    "Route qualification did not return complete authoritative usage, TPS, and TTFT telemetry."
                )
            reasoning_enabled = bool(
                job.get("qualificationReasoningContract", {}).get("reasoningEnabled") is True
            )
            reasoning_observed = metrics["reasoningTurns"] == metrics["sampleCount"]
            answer_observed = metrics["answerTurns"] == metrics["sampleCount"]
            if not reasoning_enabled or not reasoning_observed or not answer_observed:
                raise RuntimeError(
                    "Route qualification requires every measured turn to expose separate reasoning and a final answer; nothing was saved."
                )
            record["qualification"] = {
                "reasoningEnabled": True,
                "reasoningObserved": True,
                "answerObserved": True,
                "reasoningBoundaryVerified": (
                    metrics.get("reasoningBoundaryVerified") is True
                    if job["backend"] == "llamacpp" else None
                ),
                "terminalCompletionObserved": True,
                "authoritativeUsage": True,
                "metrics": metrics,
            }
            route_label = str(
                job.get("qualificationContract", {}).get("id") or job["backend"]
            )
            record["recommendation"] = (
                f"The exact {route_label} route qualified at "
                f"{float(metrics['medianDecodeTokensPerSecond']):.1f} generation tok/s "
                f"with {float(metrics['medianTTFTSeconds']):.2f}s median time to first output. "
                f"All {int(metrics['sampleCount'])} bounded agentic turns exposed separate "
                "reasoning and a final answer."
                + (
                    " The zero-budget Qwen handoff stayed out of visible content."
                    if metrics.get("reasoningBoundaryVerified") is True else ""
                )
            )
        return record

    def _mtp_tuning_candidate_summary(self, 
        baseline: dict[str, Any], result: dict[str, Any], stage: str,
        resource_status: str,
        selection_metric: str = "end-to-end-tokens-per-second",
    ) -> dict[str, Any]:
        """Compare one exact MTP load with the single AR reference route."""
        baseline_samples = baseline.get("samples")
        samples = result.get("samples")
        if (
            not isinstance(baseline_samples, list) or not baseline_samples
            or not isinstance(samples, list) or len(samples) != len(baseline_samples)
        ):
            raise RuntimeError("An MTP candidate returned an incomplete benchmark sample set.")
        sample_field, _aggregate_field = self.evidence.tuning_speed_fields(selection_metric)
        ratios: list[float] = []
        for sample, reference in zip(samples, baseline_samples):
            try:
                measured = float(sample[sample_field])
                baseline_speed = float(reference[sample_field])
            except (KeyError, TypeError, ValueError) as error:
                raise RuntimeError("An MTP candidate returned invalid speed telemetry.") from error
            if (
                not math.isfinite(measured) or measured <= 0
                or not math.isfinite(baseline_speed) or baseline_speed <= 0
            ):
                raise RuntimeError("An MTP candidate returned non-positive speed telemetry.")
            ratios.append(measured / baseline_speed)
        settings = copy.deepcopy(result.get("settings"))
        if not isinstance(settings, dict):
            raise RuntimeError("An MTP candidate did not report its exact load settings.")
        return {
            "key": self.services.controls.lmstudio_mtp_tuning_candidate_key(settings),
            "stage": stage,
            "settings": settings,
            "qualityMatchesAR": bool(
                result.get("qualityHash") == baseline.get("qualityHash")
                and result.get("qualityCompletionTokens")
                == baseline.get("qualityCompletionTokens")
            ),
            "resourceComparable": True,
            "resourceCooldownStatus": resource_status,
            "selectionMetric": selection_metric,
            "medianSpeedupVsAR": round(statistics.median(ratios), 4),
            "worstCaseSpeedupVsAR": round(min(ratios), 4),
            "medianDecodeTokensPerSecond": round(
                float(result["medianDecodeTokensPerSecond"]), 3,
            ) if self.evidence._positive_finite_number(result.get("medianDecodeTokensPerSecond")) else None,
            "medianEndToEndTokensPerSecond": round(
                float(result.get("medianEndToEndTokensPerSecond") or 0), 3,
            ),
            "selected": False,
            "_result": result,
        }

    def _mtplx_depth_candidate_summary(self, 
        baseline: dict[str, Any], result: dict[str, Any], depth: int,
        resource_status: str,
        selection_metric: str = "end-to-end-tokens-per-second",
    ) -> dict[str, Any]:
        """Compare one exact MTPLX depth with the engine's single AR reference."""
        baseline_samples = baseline.get("samples")
        samples = result.get("samples")
        settings = result.get("settings")
        if (
            not isinstance(baseline_samples, list) or not baseline_samples
            or not isinstance(samples, list) or len(samples) != len(baseline_samples)
            or settings != {"depth": depth}
        ):
            raise RuntimeError(
                f"MTPLX D{depth} did not return the complete requested measurement contract."
            )
        sample_field, _aggregate_field = self.evidence.tuning_speed_fields(selection_metric)
        ratios: list[float] = []
        for sample, reference in zip(samples, baseline_samples):
            try:
                measured = float(sample[sample_field])
                baseline_speed = float(reference[sample_field])
            except (KeyError, TypeError, ValueError) as error:
                raise RuntimeError(f"MTPLX D{depth} returned invalid speed telemetry.") from error
            if (
                not math.isfinite(measured) or measured <= 0
                or not math.isfinite(baseline_speed) or baseline_speed <= 0
            ):
                raise RuntimeError(f"MTPLX D{depth} returned non-positive speed telemetry.")
            ratios.append(measured / baseline_speed)
        resource_comparable = resource_status in {
            "reference-ready", "ready", "condition-improved", "unavailable",
        }
        return {
            "depth": depth, "settings": {"depth": depth},
            "qualityMatchesAR": bool(
                result.get("qualityHash") == baseline.get("qualityHash")
                and result.get("qualityCompletionTokens")
                == baseline.get("qualityCompletionTokens")
            ),
            "resourceComparable": resource_comparable,
            "resourceCooldownStatus": resource_status,
            "selectionMetric": selection_metric,
            "medianSpeedupVsAR": round(statistics.median(ratios), 4),
            "worstCaseSpeedupVsAR": round(min(ratios), 4),
            "medianDecodeTokensPerSecond": round(
                float(result["medianDecodeTokensPerSecond"]), 3,
            ) if self.evidence._positive_finite_number(result.get("medianDecodeTokensPerSecond")) else None,
            "medianEndToEndTokensPerSecond": round(
                float(result.get("medianEndToEndTokensPerSecond") or 0), 3,
            ),
            "selected": False, "_result": result,
        }

    def _mtplx_operator_candidate_summaries(self, 
        ar: dict[str, Any], default: dict[str, Any], candidate: dict[str, Any],
        default_resource_status: str, candidate_resource_status: str,
    ) -> list[dict[str, Any]]:
        """Compare the two fixed MTP operator routes by generation TPS."""
        ar_samples = ar.get("samples")
        default_samples = default.get("samples")
        candidate_samples = candidate.get("samples")
        if (
            not isinstance(ar_samples, list) or not ar_samples
            or not isinstance(default_samples, list)
            or not isinstance(candidate_samples, list)
            or len(default_samples) != len(ar_samples)
            or len(candidate_samples) != len(default_samples)
        ):
            raise RuntimeError(
                "MTPLX long-context operator routes returned an incomplete sample set."
            )
        default_settings = default.get("settings")
        candidate_settings = candidate.get("settings")
        if (
            not isinstance(default_settings, dict)
            or default_settings.get("mtplxOperatorRoute")
            != self.policy.mtplx_long_context_default_route
            or not isinstance(candidate_settings, dict)
            or candidate_settings.get("mtplxOperatorRoute")
            != self.policy.mtplx_long_context_2111_route
            or default_settings.get("depth") != candidate_settings.get("depth")
        ):
            raise RuntimeError(
                "MTPLX long-context operator routes did not preserve the fixed MTP depth."
            )

        def speeds(result_samples: list[dict[str, Any]]) -> list[float]:
            values: list[float] = []
            for sample in result_samples:
                value = sample.get("decodeTokensPerSecond") if isinstance(sample, dict) else None
                if not self.evidence._positive_finite_number(value):
                    raise RuntimeError(
                        "MTPLX long-context operator comparison returned invalid generation TPS."
                    )
                values.append(float(value))
            return values

        default_speeds = speeds(default_samples)
        candidate_speeds = speeds(candidate_samples)
        default_median = statistics.median(default_speeds)
        candidate_median = statistics.median(candidate_speeds)
        default_worst = min(default_speeds)
        candidate_worst = min(candidate_speeds)
        candidate_median_speedup_raw = candidate_median / max(default_median, 0.000_001)
        candidate_worst_speedup_raw = candidate_worst / max(default_worst, 0.000_001)
        quality_default_ar = bool(
            default.get("qualityHash") == ar.get("qualityHash")
            and default.get("qualityCompletionTokens")
            == ar.get("qualityCompletionTokens")
        )
        quality_candidate_ar = bool(
            candidate.get("qualityHash") == ar.get("qualityHash")
            and candidate.get("qualityCompletionTokens")
            == ar.get("qualityCompletionTokens")
        )
        quality_candidate_default = bool(
            candidate.get("qualityHash") == default.get("qualityHash")
            and candidate.get("qualityCompletionTokens")
            == default.get("qualityCompletionTokens")
        )
        resource_comparable = bool(
            default_resource_status in {"ready", "condition-improved"}
            and candidate_resource_status in {"ready", "condition-improved"}
        )
        shared = {
            "resourceComparable": resource_comparable,
            "medianSpeedupVsDefault": 1.0,
            "worstCaseSpeedupVsDefault": 1.0,
            "selected": False,
        }
        return [
            {
                **shared,
                "route": self.policy.mtplx_long_context_default_route,
                "settings": copy.deepcopy(default_settings),
                "qualityMatchesAR": quality_default_ar,
                "qualityMatchesDefault": True,
                "resourceCooldownStatus": default_resource_status,
                "medianGenerationTokensPerSecond": round(default_median, 3),
                "worstGenerationTokensPerSecond": round(default_worst, 3),
                "_result": default,
            },
            {
                **shared,
                "route": self.policy.mtplx_long_context_2111_route,
                "settings": copy.deepcopy(candidate_settings),
                "qualityMatchesAR": quality_candidate_ar,
                "qualityMatchesDefault": quality_candidate_default,
                "resourceCooldownStatus": candidate_resource_status,
                "medianSpeedupVsDefault": round(
                    candidate_median_speedup_raw, 4,
                ),
                "worstCaseSpeedupVsDefault": round(
                    candidate_worst_speedup_raw, 4,
                ),
                # Winner selection must never use the rounded display values: a
                # true +2.999% result otherwise appears to clear the +3% gate.
                "_medianSpeedupVsDefaultRaw": candidate_median_speedup_raw,
                "_worstCaseSpeedupVsDefaultRaw": candidate_worst_speedup_raw,
                "medianGenerationTokensPerSecond": round(candidate_median, 3),
                "worstGenerationTokensPerSecond": round(candidate_worst, 3),
                "_result": candidate,
            },
        ]

    def _best_tuning_candidate(self, 
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        best = self.evidence.deterministic_tuning_best_candidate(candidates)
        if best is None:
            raise RuntimeError("Tuning produced no complete candidates.")
        return best

    @staticmethod
    def _tuning_gate_reference(
        gate: dict[str, Any], route_label: str,
    ) -> tuple[dict[str, Any] | None, str]:
        status = str(gate.get("status") or "")
        if status == "reference-ready":
            reference = gate.get("reference")
            if not isinstance(reference, dict):
                raise RuntimeError("The tuner could not capture its AR resource reference.")
            return copy.deepcopy(reference), "ready"
        if status == "unavailable":
            return None, "unavailable"
        raise RuntimeError(
            f"{route_label} did not reach a stable resource baseline ({status or 'unknown'}). "
            "Nothing was saved; retry when the Mac is idle."
        )

    def _mtp_tuning_worker(
        self, job: dict[str, Any], models: list[dict[str, Any]],
    ) -> None:
        """Run a bounded coordinate search and commit only one complete v3 result."""
        plan = job["tuningPlan"]
        capability = job["model"]["backends"]["lmstudio"]
        steps_per_route = int(plan["stepsPerRoute"])
        total = int(plan["maximumModelLoads"]) * steps_per_route
        completed = 0
        candidates: list[dict[str, Any]] = []
        candidate_by_key: dict[str, dict[str, Any]] = {}

        def publish_candidates(selected_key: str | None = None) -> None:
            public = []
            for candidate in candidates:
                item = {key: copy.deepcopy(value) for key, value in candidate.items() if key != "_result"}
                item["selected"] = bool(selected_key and item["key"] == selected_key)
                public.append(item)
            with self.lock:
                self.state["tuning"] = {
                    "candidates": public,
                    "selectedCandidateKey": selected_key,
                    "maximumCandidates": self.policy.benchmark_mtp_tuner_max_candidates,
                }

        try:
            baseline_gate = self._wait_for_resource_baseline(
                "LM Studio · AR tuning baseline", "lmstudio",
            )
            resource_reference, expected_candidate_status = self._tuning_gate_reference(
                baseline_gate, "The AR reference route",
            )
            baseline, completed = self._measure_mode(
                job, models, "ar", completed, total, baseline_gate,
                display_label="AR tuning baseline", state_key="ar",
            )

            def measure_candidate(settings: dict[str, Any], stage: str) -> dict[str, Any] | None:
                nonlocal completed
                normalized = self.services.controls.lmstudio_mtp_controls(settings, capability)
                key = self.services.controls.lmstudio_mtp_tuning_candidate_key(normalized)
                if key in candidate_by_key:
                    return candidate_by_key[key]
                if len(candidates) >= self.policy.benchmark_mtp_tuner_max_candidates:
                    return None
                if self.cancel_event.is_set():
                    raise self.errors.cancelled("MTP tuning cancelled.")
                label = (
                    f"MTP · max {normalized['depth']} · min {normalized['mtpMinTokens']} · "
                    f"cutoff {normalized['mtpMinContinueProbability']:.2f}"
                )
                gate = self._wait_for_resource_baseline(
                    f"LM Studio · {label}", "lmstudio", resource_reference,
                )
                status = str(gate.get("status") or "")
                if status != expected_candidate_status:
                    raise RuntimeError(
                        f"{label} started under non-comparable Mac conditions ({status or 'unknown'}; "
                        f"expected {expected_candidate_status}). Nothing was saved; retry when the Mac is idle."
                    )
                candidate_job = copy.deepcopy(job)
                candidate_job["options"].update(normalized)
                candidate_job["modes"] = ["ar", "mtp"]
                result, completed = self._measure_mode(
                    candidate_job, models, "mtp", completed, total, gate,
                    display_label=label, state_key=f"mtp-{key}",
                )
                summary = self._mtp_tuning_candidate_summary(
                    baseline, result, stage, status,
                    self.evidence.benchmark_route_selection_metric(job),
                )
                if summary["key"] != key:
                    raise RuntimeError("LM Studio loaded different MTP settings than the tuner requested.")
                candidates.append(summary)
                candidate_by_key[key] = summary
                publish_candidates(self._best_tuning_candidate(candidates)["key"])
                return summary

            anchor = copy.deepcopy(plan["anchor"])
            for depth in plan["depthCandidates"]:
                settings = copy.deepcopy(anchor)
                settings["depth"] = int(depth)
                settings["mtpMinTokens"] = min(int(settings["mtpMinTokens"]), int(depth))
                measure_candidate(settings, "depth")

            best = self._best_tuning_candidate(candidates)
            cutoff_anchor = copy.deepcopy(best["settings"])
            cutoff_values = self.services.controls._ordered_unique([
                cutoff_anchor["mtpMinContinueProbability"],
                *plan["cutoffCandidates"],
            ])
            for cutoff in cutoff_values:
                settings = copy.deepcopy(cutoff_anchor)
                settings["mtpMinContinueProbability"] = cutoff
                measure_candidate(settings, "cutoff")

            best = self._best_tuning_candidate(candidates)
            minimum_anchor = copy.deepcopy(best["settings"])
            minimum_values = self.services.controls._ordered_unique([
                minimum_anchor["mtpMinTokens"], 0, 1, minimum_anchor["depth"],
            ])
            for minimum in minimum_values:
                settings = copy.deepcopy(minimum_anchor)
                settings["mtpMinTokens"] = max(
                    0, min(int(settings["depth"]), int(minimum)),
                )
                measure_candidate(settings, "minimum")

            if self.cancel_event.is_set():
                raise self.errors.cancelled("MTP tuning cancelled before its result was committed.")
            best = self._best_tuning_candidate(candidates)
            best["selected"] = True
            publish_candidates(best["key"])
            final_job = copy.deepcopy(job)
            final_job["modes"] = ["ar", "mtp"]
            final_job["options"].update(best["settings"])
            record = self._build_record(
                final_job, {"ar": baseline, "mtp": best["_result"]},
            )
            public_candidates = [
                {key: copy.deepcopy(value) for key, value in candidate.items() if key != "_result"}
                for candidate in candidates
            ]
            record["kind"] = "lmstudio-mtp-tuning"
            record["tuningSweep"] = {
                "version": self.policy.benchmark_mtp_tuner_version,
                "strategy": "bounded-coordinate-search",
                "selectionMetric": str(plan["selectionMetric"]),
                "complete": True,
                "resourceComparable": True,
                "optionalSearchComplete": True,
                "optionalSearchStop": None,
                "baselineResourceStatus": str(baseline_gate.get("status") or ""),
                "candidateCount": len(public_candidates),
                "maximumCandidates": self.policy.benchmark_mtp_tuner_max_candidates,
                "selectedCandidateKey": best["key"],
                "selectedSettings": copy.deepcopy(best["settings"]),
                "candidates": public_candidates,
            }
            settings = best["settings"]
            if record["winner"] == "mtp":
                record["recommendation"] = (
                    f"Use LM Studio MTP with max {settings['depth']}, min "
                    f"{settings['mtpMinTokens']}, and cutoff "
                    f"{settings['mtpMinContinueProbability']:.2f}: this exact load cleared "
                    f"greedy parity and the {self.policy.benchmark_minimum_speedup:.2f}× median/worst-case "
                    f"noise floor across {len(candidates)} bounded candidates."
                )
            else:
                record["recommendation"] = (
                    f"Keep AR: none of {len(candidates)} bounded LM Studio MTP candidates "
                    f"cleared exact greedy parity and the {self.policy.benchmark_minimum_speedup:.2f}× "
                    "median/worst-case noise floor."
                )
            if not self.evidence._local_benchmark_record_verified(capability, record, job["evidence"]):
                raise RuntimeError("The completed MTP tuning sweep failed its evidence contract.")
            with self.lock:
                if self.cancel_event.is_set():
                    raise self.errors.cancelled("The job was cancelled before its evidence commit.")
                self.services.store.save_benchmark_record(record)
                self.state["phase"] = "completed"
                self.state["progress"] = 1.0
                self.state["result"] = copy.deepcopy(record)
            self._event(record["recommendation"])
        except self.errors.cancelled:
            with self.lock:
                self.state["phase"] = "cancelled"
            self._event(
                "MTP tuning cancelled. No partial sweep was trusted or saved.", "warning",
            )
        except Exception as error:  # noqa: BLE001
            if self.cancel_event.is_set():
                with self.lock:
                    self.state["phase"] = "cancelled"
                self._event(
                    "MTP tuning cancelled. No partial sweep was trusted or saved.", "warning",
                )
            else:
                with self.lock:
                    self.state["phase"] = "failed"
                self._event(f"MTP tuning stopped before saving: {error}", "error")
        finally:
            if self.active_plan is not None:
                self.owner.stop(expected_plan=self.active_plan)
            with self.lock:
                self.active_plan = None
                if self.thread is threading.current_thread():
                    self.thread = None

    def _dflash_tuning_candidate_summary(self, 
        baseline: dict[str, Any], result: dict[str, Any], stage: str,
        resource_status: str,
        selection_metric: str = "end-to-end-tokens-per-second",
    ) -> dict[str, Any]:
        """Compare one exact DFlash load with the single AR reference route."""
        baseline_samples = baseline.get("samples")
        samples = result.get("samples")
        if (
            not isinstance(baseline_samples, list) or not baseline_samples
            or not isinstance(samples, list) or len(samples) != len(baseline_samples)
        ):
            raise RuntimeError("A DFlash candidate returned an incomplete benchmark sample set.")
        sample_field, _aggregate_field = self.evidence.tuning_speed_fields(selection_metric)
        ratios: list[float] = []
        for sample, reference in zip(samples, baseline_samples):
            try:
                measured = float(sample[sample_field])
                baseline_speed = float(reference[sample_field])
            except (KeyError, TypeError, ValueError) as error:
                raise RuntimeError("A DFlash candidate returned invalid speed telemetry.") from error
            if (
                not math.isfinite(measured) or measured <= 0
                or not math.isfinite(baseline_speed) or baseline_speed <= 0
            ):
                raise RuntimeError("A DFlash candidate returned non-positive speed telemetry.")
            ratios.append(measured / baseline_speed)
        settings = copy.deepcopy(result.get("settings"))
        if not isinstance(settings, dict):
            raise RuntimeError("A DFlash candidate did not report its exact load settings.")
        return {
            "key": self.services.controls.dflash2_tuning_candidate_key(settings),
            "stage": stage,
            "settings": settings,
            "qualityMatchesAR": bool(
                result.get("qualityHash") == baseline.get("qualityHash")
                and result.get("qualityCompletionTokens")
                == baseline.get("qualityCompletionTokens")
            ),
            "resourceComparable": True,
            "resourceCooldownStatus": resource_status,
            "selectionMetric": selection_metric,
            "medianSpeedupVsAR": round(statistics.median(ratios), 4),
            "worstCaseSpeedupVsAR": round(min(ratios), 4),
            "medianDecodeTokensPerSecond": round(
                float(result["medianDecodeTokensPerSecond"]), 3,
            ) if self.evidence._positive_finite_number(result.get("medianDecodeTokensPerSecond")) else None,
            "medianEndToEndTokensPerSecond": round(
                float(result.get("medianEndToEndTokensPerSecond") or 0), 3,
            ),
            "selected": False,
            "_result": result,
        }

    def _dflash_tuning_worker(
        self, job: dict[str, Any], models: list[dict[str, Any]],
    ) -> None:
        """Tune DFlash coordinates and commit only a complete exact-pair result."""
        plan = job["tuningPlan"]
        capability = job["model"]["backends"]["omlx"]
        steps_per_route = int(plan["stepsPerRoute"])
        total = int(plan["maximumModelLoads"]) * steps_per_route
        completed = 0
        candidates: list[dict[str, Any]] = []
        candidate_by_key: dict[str, dict[str, Any]] = {}

        def publish_candidates(selected_key: str | None = None) -> None:
            public = []
            for candidate in candidates:
                item = {
                    key: copy.deepcopy(value)
                    for key, value in candidate.items() if key != "_result"
                }
                item["selected"] = bool(selected_key and item["key"] == selected_key)
                public.append(item)
            with self.lock:
                self.state["tuning"] = {
                    "candidates": public,
                    "selectedCandidateKey": selected_key,
                    "maximumCandidates": self.policy.benchmark_dflash_tuner_max_candidates,
                }

        try:
            baseline_gate = self._wait_for_resource_baseline(
                "oMLX · AR tuning baseline", "omlx",
            )
            resource_reference, expected_candidate_status = self._tuning_gate_reference(
                baseline_gate, "The AR reference route",
            )
            baseline, completed = self._measure_mode(
                job, models, "ar", completed, total, baseline_gate,
                display_label="AR tuning baseline", state_key="ar",
            )
            final_results: dict[str, dict[str, Any]] = {"ar": baseline}

            if "mtp" in plan["baselineModes"]:
                mtp_gate = self._wait_for_resource_baseline(
                    "oMLX · native MTP comparison", "omlx", resource_reference,
                )
                mtp_status = str(mtp_gate.get("status") or "")
                if mtp_status != expected_candidate_status:
                    raise RuntimeError(
                        "Native MTP started under non-comparable Mac conditions "
                        f"({mtp_status or 'unknown'}; expected {expected_candidate_status}). "
                        "Nothing was saved; retry when the Mac is idle."
                    )
                mtp_result, completed = self._measure_mode(
                    job, models, "mtp", completed, total, mtp_gate,
                    display_label="Native MTP comparison", state_key="mtp",
                )
                final_results["mtp"] = mtp_result

            def measure_candidate(
                settings: dict[str, Any], stage: str,
            ) -> dict[str, Any] | None:
                nonlocal completed
                normalized = self.evidence.dflash2_tuning_controls(settings, capability)
                key = self.services.controls.dflash2_tuning_candidate_key(normalized)
                if key in candidate_by_key:
                    return candidate_by_key[key]
                if len(candidates) >= self.policy.benchmark_dflash_tuner_max_candidates:
                    return None
                if self.cancel_event.is_set():
                    raise self.errors.cancelled("DFlash tuning cancelled.")
                label = (
                    f"DFlash · block {normalized['blockSize']} · "
                    f"{normalized['verifyMode']} · {normalized['draftQuant']}"
                )
                gate = self._wait_for_resource_baseline(
                    f"oMLX · {label}", "omlx", resource_reference,
                )
                status = str(gate.get("status") or "")
                if status != expected_candidate_status:
                    raise RuntimeError(
                        f"{label} started under non-comparable Mac conditions "
                        f"({status or 'unknown'}; expected {expected_candidate_status}). "
                        "Nothing was saved; retry when the Mac is idle."
                    )
                candidate_job = copy.deepcopy(job)
                candidate_job["options"].update({
                    "depth": normalized["blockSize"],
                    "dflashVerify": normalized["verifyMode"],
                    "dflashDraftQuant": normalized["draftQuant"],
                })
                result, completed = self._measure_mode(
                    candidate_job, models, "dflash2", completed, total, gate,
                    display_label=label, state_key=f"dflash2-{key}",
                )
                summary = self._dflash_tuning_candidate_summary(
                    baseline, result, stage, status,
                    self.evidence.benchmark_route_selection_metric(job),
                )
                if summary["key"] != key:
                    raise RuntimeError(
                        "oMLX loaded different DFlash settings than the tuner requested."
                    )
                candidates.append(summary)
                candidate_by_key[key] = summary
                publish_candidates(self._best_tuning_candidate(candidates)["key"])
                return summary

            anchor = copy.deepcopy(plan["anchor"])
            for block_size in plan["blockCandidates"]:
                settings = copy.deepcopy(anchor)
                settings["blockSize"] = int(block_size)
                measure_candidate(settings, "block")

            best = self._best_tuning_candidate(candidates)
            verifier_anchor = copy.deepcopy(best["settings"])
            verifier_values = self.services.controls._ordered_unique([
                verifier_anchor["verifyMode"], *plan["verifyCandidates"],
            ])
            for verify_mode in verifier_values:
                settings = copy.deepcopy(verifier_anchor)
                settings["verifyMode"] = str(verify_mode)
                measure_candidate(settings, "verifier")

            best = self._best_tuning_candidate(candidates)
            quant_anchor = copy.deepcopy(best["settings"])
            quant_values = self.services.controls._ordered_unique([
                quant_anchor["draftQuant"], *plan["quantCandidates"],
            ])
            for draft_quant in quant_values:
                settings = copy.deepcopy(quant_anchor)
                settings["draftQuant"] = str(draft_quant)
                measure_candidate(settings, "quantization")

            if self.cancel_event.is_set():
                raise self.errors.cancelled("DFlash tuning cancelled before its result was committed.")
            best = self._best_tuning_candidate(candidates)
            best["selected"] = True
            publish_candidates(best["key"])
            final_job = copy.deepcopy(job)
            final_job["options"].update({
                "depth": best["settings"]["blockSize"],
                "dflashVerify": best["settings"]["verifyMode"],
                "dflashDraftQuant": best["settings"]["draftQuant"],
            })
            final_results["dflash2"] = best["_result"]
            record = self._build_record(final_job, final_results)
            public_candidates = [
                {
                    key: copy.deepcopy(value)
                    for key, value in candidate.items() if key != "_result"
                }
                for candidate in candidates
            ]
            record["kind"] = "omlx-dflash2-tuning"
            record["tuningSweep"] = {
                "version": self.policy.benchmark_dflash_tuner_version,
                "strategy": "bounded-coordinate-search",
                "selectionMetric": str(plan["selectionMetric"]),
                "searchedAxes": ["blockSize", "verifyMode", "draftQuant"],
                "baselineModes": list(plan["baselineModes"]),
                "complete": True,
                "resourceComparable": True,
                "optionalSearchComplete": True,
                "optionalSearchStop": None,
                "baselineResourceStatus": str(baseline_gate.get("status") or ""),
                "candidateCount": len(public_candidates),
                "maximumCandidates": self.policy.benchmark_dflash_tuner_max_candidates,
                "selectedCandidateKey": best["key"],
                "selectedSettings": copy.deepcopy(best["settings"]),
                "candidates": public_candidates,
            }
            settings = best["settings"]
            if record["winner"] == "dflash2":
                record["recommendation"] = (
                    f"Use DFlash 2 with block {settings['blockSize']}, "
                    f"{settings['verifyMode']} verification, and {settings['draftQuant']} "
                    f"draft precision: this exact load cleared greedy parity and the "
                    f"{self.policy.benchmark_minimum_speedup:.2f}× median/worst-case noise floor "
                    f"across {len(candidates)} bounded candidates."
                )
            elif record["winner"] == "mtp":
                record["recommendation"] = (
                    f"Use native MTP: it remained faster than AR and the best of "
                    f"{len(candidates)} correctness-gated DFlash candidates."
                )
            else:
                record["recommendation"] = (
                    f"Keep AR: none of {len(candidates)} bounded DFlash candidates"
                    + (
                        " or native MTP"
                        if "mtp" in plan["baselineModes"] else ""
                    )
                    + f" cleared exact greedy parity and the {self.policy.benchmark_minimum_speedup:.2f}× "
                    "median/worst-case noise floor."
                )
            if not self.evidence._local_benchmark_record_verified(capability, record, job["evidence"]):
                raise RuntimeError("The completed DFlash tuning sweep failed its evidence contract.")
            with self.lock:
                if self.cancel_event.is_set():
                    raise self.errors.cancelled("The job was cancelled before its evidence commit.")
                self.services.store.save_benchmark_record(record)
                self.state["phase"] = "completed"
                self.state["progress"] = 1.0
                self.state["result"] = copy.deepcopy(record)
            self._event(record["recommendation"])
        except self.errors.cancelled:
            with self.lock:
                self.state["phase"] = "cancelled"
            self._event(
                "DFlash tuning cancelled. No partial sweep was trusted or saved.",
                "warning",
            )
        except Exception as error:  # noqa: BLE001
            if self.cancel_event.is_set():
                with self.lock:
                    self.state["phase"] = "cancelled"
                self._event(
                    "DFlash tuning cancelled. No partial sweep was trusted or saved.",
                    "warning",
                )
            else:
                with self.lock:
                    self.state["phase"] = "failed"
                self._event(f"DFlash tuning stopped before saving: {error}", "error")
        finally:
            if self.active_plan is not None:
                self.owner.stop(expected_plan=self.active_plan)
            with self.lock:
                self.active_plan = None
                if self.thread is threading.current_thread():
                    self.thread = None

    def _models_with_shootout_records(self, 
        models: list[dict[str, Any]], model_id: str, records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        enriched = copy.deepcopy(models)
        model = next((item for item in enriched if item.get("id") == model_id), None)
        if not model:
            raise RuntimeError("The shootout model disappeared before its result could be evaluated.")
        for record in records:
            backend = str(record["backend"])
            capability = model.get("backends", {}).get(backend)
            if not isinstance(capability, dict):
                raise RuntimeError(f"{self.policy.backend_labels.get(backend, backend)} capability disappeared.")
            existing = capability.get("localBenchmarks")
            history = [item for item in existing if isinstance(item, dict)] if isinstance(existing, list) else []
            history = [item for item in history if item.get("id") != record.get("id")]
            history.append(copy.deepcopy(record))
            capability["localBenchmarks"] = history
            capability["localBenchmark"] = copy.deepcopy(record)
        return enriched

    def _build_shootout_result(
        self, shootout: dict[str, Any], records: list[dict[str, Any]],
        models: list[dict[str, Any]],
    ) -> dict[str, Any]:
        measurements: list[dict[str, Any]] = []
        for record in records:
            measurement = self.services.presentation.cross_engine_benchmark_measurement(record)
            if measurement:
                measurements.append({
                    "backend": record["backend"], "record": record, **measurement,
                })
        workload_comparison = self.services.presentation.cross_engine_workload_compatibility(measurements)
        matrix_quality_passed = workload_comparison.get("comparable") is True
        reference_quality = (
            (records[0].get("qualityFingerprint"), records[0].get("qualityCompletionTokens"))
            if records else (None, None)
        )
        engines: list[dict[str, Any]] = []
        for record in records:
            measurement = self.services.presentation.cross_engine_benchmark_measurement(record)
            quality_matches = (
                record.get("qualityFingerprint"), record.get("qualityCompletionTokens")
            ) == reference_quality
            engines.append({
                "backend": record["backend"],
                "label": self.policy.backend_labels[record["backend"]],
                "mode": record["winner"],
                "modeLabel": self.services.presentation.benchmark_public_mode_label(
                    str(record["backend"]), str(record["winner"])
                ),
                "testedModes": copy.deepcopy(record.get("comparedModes") or ["ar"]),
                "modeDetail": self.services.presentation.benchmark_mode_summary(
                    next(
                        item for item in models
                        if item.get("id") == shootout["modelId"]
                    ),
                    str(record["backend"]),
                    record.get("comparedModes") or ["ar"],
                    record.get("engineSettings"),
                    kv=str(record.get("targetKV") or "off"),
                ),
                "accelerationReason": self.services.presentation.benchmark_acceleration_reason(
                    next(
                        item for item in models
                        if item.get("id") == shootout["modelId"]
                    ),
                    str(record["backend"]),
                    record.get("comparedModes") or ["ar"],
                    kv=str(record.get("targetKV") or "off"),
                ),
                "settingsLabel": self.services.presentation.benchmark_engine_settings_label(
                    str(record["backend"]), record.get("engineSettings"),
                ),
                "routeSettingsLabel": self.services.presentation.benchmark_route_settings_label(
                    str(record["backend"]), record.get("winner"),
                    record.get("settings"),
                ),
                "settingsSearch": self.services.presentation.public_benchmark_settings_search_result(record),
                "score": round(float(measurement["score"]), 4) if measurement else None,
                "metric": measurement["metric"] if measurement else None,
                "display": measurement["display"] if measurement else "Not comparable",
                "firstTokenSeconds": measurement.get("firstTokenSeconds") if measurement else None,
                "decodeTokensPerSecond": measurement.get("decodeTokensPerSecond") if measurement else None,
                "peakPressureDeltaBytes": measurement.get("peakPressureDeltaBytes") if measurement else None,
                "baselineHeadroomPercent": measurement.get("baselineHeadroomPercent") if measurement else None,
                "minimumHeadroomPercent": measurement.get("minimumHeadroomPercent") if measurement else None,
                "totalMemoryBytes": measurement.get("totalMemoryBytes") if measurement else None,
                "thermalStart": measurement.get("thermalStart") if measurement else "unavailable",
                "thermalStartValue": measurement.get("thermalStartValue") if measurement else None,
                "thermalWorst": measurement.get("thermalWorst") if measurement else "unavailable",
                "thermalWorstValue": measurement.get("thermalWorstValue") if measurement else None,
                "lowPowerMode": measurement.get("lowPowerMode") if measurement else None,
                "resourceCooldownStatus": measurement.get("resourceCooldownStatus") if measurement else None,
                "qualityMatchesMatrix": quality_matches,
                "recordId": record["id"],
                "runtimeVersion": record["runtimeVersion"],
            })
        enriched = self._models_with_shootout_records(
            models, shootout["modelId"], records,
        )
        profiles: dict[str, dict[str, Any]] = {}
        expected_record_ids = {
            str(record["backend"]): str(record["id"])
            for record in records
        }
        for preference, preference_label in self.policy.engine_preference_labels.items():
            request = copy.deepcopy(shootout["request"])
            request["enginePreference"] = preference
            decision = self.services.planning.best_engine_request(request, enriched)
            tier = str(decision.get("engineEvidenceTier") or "")
            trusted = tier == "cross-engine-local-benchmark" and matrix_quality_passed
            apply_ready = bool(
                matrix_quality_passed
                and tier in {
                    "cross-engine-local-benchmark",
                    "cross-engine-leading-band",
                    "cross-engine-noise-floor",
                }
            )
            raw_binding = decision.get("engineEvidenceBinding")
            binding: dict[str, Any] | None = None
            if raw_binding is not None:
                binding = self.services.planning.validated_optimizer_evidence_binding({
                    "evidenceBinding": raw_binding,
                })
                expected_binding = {
                    "scope": "engine",
                    "suite": str(shootout["suite"]),
                    "preference": preference,
                    "shootoutId": str(shootout["id"]),
                    "recordIds": expected_record_ids,
                }
                if binding != expected_binding:
                    raise RuntimeError(
                        "The completed Engine Shootout produced an inconsistent apply reference."
                    )
            if apply_ready and binding is None:
                raise RuntimeError(
                    "The completed Engine Shootout produced no immutable apply reference."
                )
            if not matrix_quality_passed:
                recommendation = str(workload_comparison.get("warning") or (
                    "The completed engine routes did not perform comparable amounts of work."
                ))
            else:
                recommendation = " ".join(str(item) for item in decision.get("engineRationale") or [])
            profiles[preference] = {
                "preference": preference, "preferenceLabel": preference_label,
                "backend": decision.get("backend"),
                "label": self.policy.backend_labels.get(str(decision.get("backend")), str(decision.get("backend"))),
                "engineChanged": bool(decision.get("engineChanged")),
                "evidenceTier": tier,
                "evidenceLabel": decision.get("engineEvidenceLabel"),
                "comparedEngines": copy.deepcopy(decision.get("comparedEngines") or []),
                "missingEngines": copy.deepcopy(decision.get("missingEngines") or []),
                "rationale": copy.deepcopy(decision.get("engineRationale") or []),
                "leadingBackends": copy.deepcopy(decision.get("leadingBackends") or []),
                "currentInLeadingBand": decision.get("currentInLeadingBand") is True,
                "trustedWinner": trusted, "recommendation": recommendation,
                "exactOutputMatch": workload_comparison.get("exactOutputMatch") is True,
                "outputWarning": str(workload_comparison.get("warning") or ""),
                **({"evidenceBinding": copy.deepcopy(binding)} if apply_ready else {}),
            }
        selected_preference = str(shootout["request"].get("enginePreference") or "throughput")
        public_decision = profiles.get(selected_preference) or profiles["throughput"]
        return {
            "id": shootout["id"], "kind": "engine-shootout",
            "modelId": shootout["modelId"], "model": shootout["model"],
            "suite": shootout["suite"], "workloadKind": shootout["workloadKind"],
            "engines": engines, "matrixQualityPassed": matrix_quality_passed,
            "matrixWorkloadComparable": matrix_quality_passed,
            "exactOutputMatch": workload_comparison.get("exactOutputMatch") is True,
            "outputWarning": str(workload_comparison.get("warning") or ""),
            "reasoningContract": copy.deepcopy(shootout["reasoningContract"]),
            "profiles": profiles, "selectedPreference": selected_preference,
            "executionOrder": list(shootout["executionOrder"]),
            "orderStrategy": shootout["orderStrategy"],
            "resourceCooldown": {
                "version": 1,
                "maxWaitSeconds": self.policy.benchmark_cooldown_max_seconds,
                "stableSamplesRequired": self.policy.benchmark_cooldown_stable_samples,
                "memoryToleranceBytes": self.policy.benchmark_cooldown_memory_tolerance_bytes,
            },
            "trustedWinner": public_decision["trustedWinner"],
            "recommendedBackend": public_decision["backend"],
            "decision": copy.deepcopy(public_decision),
            "recommendation": public_decision["recommendation"],
            **(
                {"evidenceBinding": copy.deepcopy(public_decision["evidenceBinding"])}
                if isinstance(public_decision.get("evidenceBinding"), dict) else {}
            ),
        }

    def _shootout_tuning_gate(
        self, route_label: str, backend: str,
        resource_reference: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        """Require a stable cross-engine start and carry one shared reference forward."""
        gate = self._wait_for_resource_baseline(
            route_label, backend, resource_reference,
        )
        status = str(gate.get("status") or "")
        reference = resource_reference
        if status == "timeout":
            condition = str(
                gate.get("conditionDetail")
                or "the observed memory, thermal, or power condition did not match"
            )
            raise self.errors.cooldown(
                f"{route_label} did not return to comparable Mac conditions "
                f"before the bounded resource cooldown expired: {condition}."
            )
        if reference is None:
            if status in {"reference-ready", "ready"}:
                candidate = gate.get("reference")
                if not isinstance(candidate, dict):
                    raise RuntimeError(
                        f"{route_label} did not publish its resource reference."
                    )
                reference = copy.deepcopy(candidate)
            elif status != "unavailable":
                raise RuntimeError(
                    f"{route_label} did not reach a stable Mac-condition baseline "
                    f"({status or 'unknown'}). Nothing was saved; retry when the Mac is idle."
                )
        elif status not in {"ready", "condition-improved", "reference-ready"}:
            raise RuntimeError(
                f"{route_label} started under non-comparable Mac conditions "
                f"({status or 'unknown'}). Nothing was saved; retry when the Mac is idle."
            )
        return gate, reference

    def _shootout_settings_search(
        self, job: dict[str, Any], models: list[dict[str, Any]],
        completed: int, total: int, resource_reference: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], int, dict[str, Any] | None]:
        plan = job.get("engineSettingsSweep")
        if not isinstance(plan, dict):
            return self._shootout_one_engine(job, models, completed, total, resource_reference)
        expected_job = copy.deepcopy(job)
        expected_job.pop("engineSettingsSweep", None)
        self.services.planning.prepare_engine_settings_sweep(expected_job)
        if expected_job.get("engineSettingsSweep") != plan:
            raise RuntimeError("The runtime settings plan changed; review Calibration again before testing.")
        backend = str(job["backend"])
        base_job = copy.deepcopy(job)
        base_job.pop("engineSettingsSweep", None)
        candidates = plan["candidates"]
        ar_results: dict[str, Any] = {}
        ar_records: dict[str, Any] = {}
        preference = str(plan["selectionPreference"])

        def candidate_job(candidate: dict[str, Any]) -> dict[str, Any]:
            value = copy.deepcopy(base_job)
            value["options"].update(copy.deepcopy(candidate["settings"]))
            self.services.planning.add_benchmark_engine_evidence(value["evidence"], value["model"], value["options"], [backend])
            return value

        def measure(value: dict[str, Any], mode: str, label: str) -> dict[str, Any]:
            nonlocal completed, resource_reference
            if self.cancel_event.is_set():
                raise self.errors.cancelled("Calibration cancelled during settings search.")
            gate, resource_reference = self._shootout_tuning_gate(label, backend, resource_reference)
            result, completed = self._measure_mode(
                value, models, mode, completed, total, gate,
                display_label=label, state_key=mode,
            )
            result["resourceCooldown"] = {
                key: copy.deepcopy(value) for key, value in gate.items()
                if not key.startswith("_")
            }
            return result

        for index, candidate in enumerate(candidates):
            value = candidate_job(candidate)
            label = f"{candidate['label']} · AR · preset {index + 1}/{len(candidates)}"
            result = measure(value, "ar", label)
            ar_results[candidate["key"]] = result
            value["modes"] = ["ar"]
            ar_records[candidate["key"]] = self._build_record(value, {"ar": result})
        reference = ar_records[candidates[0]["key"]]
        provisional_rows = [
            self.evidence.engine_settings_candidate_evidence(candidate, ar_records[candidate["key"]], reference, preference)
            for candidate in candidates
        ]
        provisional = self.evidence.select_engine_settings_sweep_candidate(provisional_rows, preference)
        if provisional is None:
            raise RuntimeError("No runtime preset completed a comparable AR workload.")
        chosen = next(candidate for candidate in candidates if candidate["key"] == provisional["key"])
        tuned_job = candidate_job(chosen)
        tuned_job["_premeasuredAR"] = ar_results[chosen["key"]]
        tuned_record, completed, resource_reference = self._shootout_one_engine(
            tuned_job, models, completed, total, resource_reference,
        )
        measured_records = {chosen["key"]: tuned_record}
        for index, candidate in enumerate(candidates):
            if candidate["key"] == chosen["key"]:
                continue
            value = candidate_job(candidate)
            results = {"ar": ar_results[candidate["key"]]}
            for mode in value["modes"]:
                if mode == "ar":
                    continue
                settings = tuned_record["modeSettings"][mode]
                if mode == "dflash2":
                    value["_benchmarkDflashSettings"] = copy.deepcopy(settings)
                elif backend == "lmstudio":
                    value["_benchmarkMtpSettings"] = copy.deepcopy(settings)
                else:
                    value["_benchmarkMtpDepth"] = settings["depth"]
                label = f"{candidate['label']} · {self.services.presentation.benchmark_public_mode_label(backend, mode)} · preset {index + 1}/{len(candidates)}"
                results[mode] = measure(value, mode, label)
            measured_records[candidate["key"]] = self._build_record(value, results)
        rows = [
            self.evidence.engine_settings_candidate_evidence(candidate, measured_records[candidate["key"]], reference, preference)
            for candidate in candidates
        ]
        best = self.evidence.select_engine_settings_sweep_candidate(rows, preference)
        if best is None:
            raise RuntimeError("No runtime preset passed the final route comparison.")
        record = copy.deepcopy(measured_records[best["key"]])
        record["engineSettingsSweep"] = {
            **copy.deepcopy(plan),
            "complete": True,
            "candidateCount": len(candidates),
            "selectedCandidateKey": best["key"],
            "selectedEngineSettings": copy.deepcopy(record["engineSettings"]),
            "tuningReferenceKey": chosen["key"],
            "records": measured_records,
        }
        if not self.evidence._local_benchmark_record_verified(
            job["model"]["backends"][backend], record, job["evidence"],
        ):
            raise RuntimeError("The completed runtime settings search failed its evidence audit.")
        return record, completed, resource_reference

    def _publish_shootout_tuning(
        self, backend: str, kind: str, candidates: list[dict[str, Any]],
        selected_key: str | None, maximum: int,
    ) -> None:
        public = []
        for candidate in candidates:
            item = {
                key: copy.deepcopy(value)
                for key, value in candidate.items() if key != "_result"
            }
            item["selected"] = bool(selected_key and item.get("key") == selected_key)
            public.append(item)
        with self.lock:
            engine = self.state.get("engines", {}).get(backend)
            if isinstance(engine, dict):
                engine["tuning"] = {
                    "kind": kind, "candidates": public,
                    "selectedCandidateKey": selected_key,
                    "maximumCandidates": maximum,
                }

    def _shootout_lmstudio_tuning(
        self, job: dict[str, Any], models: list[dict[str, Any]],
        completed: int, total: int,
        resource_reference: dict[str, Any] | None,
        premeasured_baseline: dict[str, Any] | None = None,
        premeasured_gate: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], int, dict[str, Any] | None]:
        """Return one complete LM Studio record after its bounded MTP search."""
        plan = job["calibrationTuningPlan"]
        capability = job["model"]["backends"]["lmstudio"]
        maximum_candidates = int(
            plan.get("maximumMtpCandidates") or self.policy.benchmark_mtp_tuner_max_candidates
        )
        candidates: list[dict[str, Any]] = []
        candidate_by_key: dict[str, dict[str, Any]] = {}
        optional_search_stop: dict[str, Any] | None = None
        if premeasured_baseline is None:
            baseline_gate, resource_reference = self._shootout_tuning_gate(
                "LM Studio · AR tuning baseline", "lmstudio", resource_reference,
            )
            baseline, completed = self._measure_mode(
                job, models, "ar", completed, total, baseline_gate,
                display_label="AR tuning baseline", state_key="ar",
            )
        else:
            if not isinstance(premeasured_gate, dict):
                raise RuntimeError("LM Studio settings search lost its AR resource receipt.")
            baseline = premeasured_baseline
            baseline_gate = premeasured_gate

        def measure_candidate(
            settings: dict[str, Any], stage: str,
        ) -> dict[str, Any] | None:
            nonlocal completed, resource_reference
            normalized = self.services.controls.lmstudio_mtp_controls(settings, capability)
            key = self.services.controls.lmstudio_mtp_tuning_candidate_key(normalized)
            if key in candidate_by_key:
                return candidate_by_key[key]
            if len(candidates) >= maximum_candidates:
                return None
            if self.cancel_event.is_set():
                raise self.errors.cancelled("Engine Shootout cancelled during LM Studio tuning.")
            label = (
                f"MTP · max {normalized['depth']} · min {normalized['mtpMinTokens']} · "
                f"cutoff {normalized['mtpMinContinueProbability']:.2f}"
            )
            gate, resource_reference = self._shootout_tuning_gate(
                f"LM Studio · {label}", "lmstudio", resource_reference,
            )
            candidate_job = copy.deepcopy(job)
            candidate_job["_benchmarkMtpSettings"] = copy.deepcopy(normalized)
            result, completed = self._measure_mode(
                candidate_job, models, "mtp", completed, total, gate,
                display_label=label, state_key=f"mtp-{key}",
            )
            summary = self._mtp_tuning_candidate_summary(
                baseline, result, stage, str(gate.get("status") or ""),
                self.evidence.benchmark_route_selection_metric(job),
            )
            if summary["key"] != key:
                raise RuntimeError(
                    "LM Studio loaded different MTP settings than Calibration requested."
                )
            candidates.append(summary)
            candidate_by_key[key] = summary
            leading = self._best_tuning_candidate(candidates)
            self._publish_shootout_tuning(
                "lmstudio", "lmstudio-mtp", candidates, leading["key"],
                maximum_candidates,
            )
            return summary

        def measure_optional_candidate(
            settings: dict[str, Any], stage: str,
        ) -> bool:
            """Stop only optional refinement when its comparable-start wait expires."""
            nonlocal optional_search_stop
            try:
                measured = measure_candidate(settings, stage)
                if measured is None:
                    optional_search_stop = {
                        "reason": "candidate-budget", "stage": stage,
                        "completedCandidateCount": len(candidates),
                    }
                    return False
            except self.errors.cooldown:
                optional_search_stop = {
                    "reason": "resource-cooldown-timeout",
                    "stage": stage,
                    "completedCandidateCount": len(candidates),
                }
                self._event(
                    "LM Studio's optional cutoff/minimum refinement reached its resource "
                    "cooldown limit after every required depth was measured. Calibration "
                    "will keep the fastest completed comparable candidate.",
                    "warning",
                )
                return False
            return True

        anchor = copy.deepcopy(plan["anchor"])
        for depth in plan["depthCandidates"]:
            settings = copy.deepcopy(anchor)
            settings["depth"] = int(depth)
            settings["mtpMinTokens"] = min(
                int(settings["mtpMinTokens"]), int(depth),
            )
            measure_candidate(settings, "depth")
        best = self._best_tuning_candidate(candidates)
        cutoff_anchor = copy.deepcopy(best["settings"])
        for cutoff in self.services.controls._ordered_unique([
            cutoff_anchor["mtpMinContinueProbability"], *plan["cutoffCandidates"],
        ]):
            settings = copy.deepcopy(cutoff_anchor)
            settings["mtpMinContinueProbability"] = cutoff
            if not measure_optional_candidate(settings, "cutoff"):
                break
        best = self._best_tuning_candidate(candidates)
        minimum_anchor = copy.deepcopy(best["settings"])
        if optional_search_stop is None:
            for minimum in self.services.controls._ordered_unique([
                minimum_anchor["mtpMinTokens"], 0, 1, minimum_anchor["depth"],
            ]):
                settings = copy.deepcopy(minimum_anchor)
                settings["mtpMinTokens"] = max(
                    0, min(int(settings["depth"]), int(minimum)),
                )
                if not measure_optional_candidate(settings, "minimum"):
                    break
        if self.cancel_event.is_set():
            raise self.errors.cancelled("Engine Shootout cancelled before LM Studio tuning was committed.")
        best = self._best_tuning_candidate(candidates)
        best["selected"] = True
        self._publish_shootout_tuning(
            "lmstudio", "lmstudio-mtp", candidates, best["key"],
            maximum_candidates,
        )
        inner_results = {"ar": baseline, "mtp": best["_result"]}
        record = self._build_record(job, inner_results)
        public_candidates = [
            {
                key: copy.deepcopy(value)
                for key, value in candidate.items() if key != "_result"
            }
            for candidate in candidates
        ]
        record["kind"] = "lmstudio-mtp-tuning"
        record["tuningSweep"] = {
            "version": self.policy.benchmark_mtp_tuner_version,
            "strategy": "bounded-coordinate-search",
            "selectionMetric": str(plan["selectionMetric"]),
            "complete": True, "resourceComparable": True,
            "optionalSearchComplete": optional_search_stop is None,
            "optionalSearchStop": copy.deepcopy(optional_search_stop),
            "baselineResourceStatus": str(baseline_gate.get("status") or ""),
            "candidateCount": len(public_candidates),
            "maximumCandidates": maximum_candidates,
            "selectedCandidateKey": best["key"],
            "selectedSettings": copy.deepcopy(best["settings"]),
            "candidates": public_candidates,
        }
        settings = best["settings"]
        record["recommendation"] = (
            (
                f"Use LM Studio MTP D{settings['depth']} with min "
                f"{settings['mtpMinTokens']} and cutoff "
                f"{settings['mtpMinContinueProbability']:.2f}: it was the fastest "
                f"correctness-clearing load across {len(candidates)} bounded candidates."
            )
            if record["winner"] == "mtp" else
            f"Keep AR: none of {len(candidates)} bounded LM Studio MTP candidates "
            "cleared exact parity and the speed noise floor."
        )
        if optional_search_stop is not None:
            record["recommendation"] += (
                " Optional cutoff/minimum refinement stopped at the resource cooldown "
                "limit after every required draft depth was compared; this result uses "
                "the fastest completed comparable candidate."
            )
        if not self.evidence._local_benchmark_record_verified(capability, record, job["evidence"]):
            raise RuntimeError("The completed LM Studio Calibration sweep failed its evidence contract.")
        return record, completed, resource_reference

    def _shootout_dflash_tuning(
        self, job: dict[str, Any], models: list[dict[str, Any]],
        completed: int, total: int,
        resource_reference: dict[str, Any] | None,
        premeasured_baseline: dict[str, Any] | None = None,
        premeasured_gate: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], int, dict[str, Any] | None]:
        """Return one complete oMLX record after its bounded DFlash search."""
        plan = job["calibrationTuningPlan"]
        capability = job["model"]["backends"]["omlx"]
        maximum_candidates = int(
            plan.get("maximumDflashCandidates") or self.policy.benchmark_dflash_tuner_max_candidates
        )
        candidates: list[dict[str, Any]] = []
        candidate_by_key: dict[str, dict[str, Any]] = {}
        optional_search_stop: dict[str, Any] | None = None
        if premeasured_baseline is None:
            baseline_gate, resource_reference = self._shootout_tuning_gate(
                "oMLX · AR tuning baseline", "omlx", resource_reference,
            )
            baseline, completed = self._measure_mode(
                job, models, "ar", completed, total, baseline_gate,
                display_label="AR tuning baseline", state_key="ar",
            )
        else:
            if not isinstance(premeasured_gate, dict):
                raise RuntimeError("oMLX settings search lost its AR resource receipt.")
            baseline = premeasured_baseline
            baseline_gate = premeasured_gate
        final_results: dict[str, dict[str, Any]] = {"ar": baseline}
        if "mtp" in plan["baselineModes"]:
            mtp_gate, resource_reference = self._shootout_tuning_gate(
                "oMLX · native MTP comparison", "omlx", resource_reference,
            )
            mtp_result, completed = self._measure_mode(
                job, models, "mtp", completed, total, mtp_gate,
                display_label="Native MTP comparison", state_key="mtp",
            )
            final_results["mtp"] = mtp_result

        def measure_candidate(
            settings: dict[str, Any], stage: str,
        ) -> dict[str, Any] | None:
            nonlocal completed, resource_reference
            normalized = self.evidence.dflash2_tuning_controls(settings, capability)
            key = self.services.controls.dflash2_tuning_candidate_key(normalized)
            if key in candidate_by_key:
                return candidate_by_key[key]
            if len(candidates) >= maximum_candidates:
                return None
            if self.cancel_event.is_set():
                raise self.errors.cancelled("Engine Shootout cancelled during DFlash tuning.")
            label = (
                f"DFlash · block {normalized['blockSize']} · "
                f"{normalized['verifyMode']} · {normalized['draftQuant']}"
            )
            gate, resource_reference = self._shootout_tuning_gate(
                f"oMLX · {label}", "omlx", resource_reference,
            )
            candidate_job = copy.deepcopy(job)
            candidate_job["_benchmarkDflashSettings"] = copy.deepcopy(normalized)
            result, completed = self._measure_mode(
                candidate_job, models, "dflash2", completed, total, gate,
                display_label=label, state_key=f"dflash2-{key}",
            )
            summary = self._dflash_tuning_candidate_summary(
                baseline, result, stage, str(gate.get("status") or ""),
                self.evidence.benchmark_route_selection_metric(job),
            )
            if summary["key"] != key:
                raise RuntimeError(
                    "oMLX loaded different DFlash settings than Calibration requested."
                )
            candidates.append(summary)
            candidate_by_key[key] = summary
            leading = self._best_tuning_candidate(candidates)
            self._publish_shootout_tuning(
                "omlx", "omlx-dflash2", candidates, leading["key"],
                maximum_candidates,
            )
            return summary

        def measure_optional_candidate(
            settings: dict[str, Any], stage: str,
        ) -> bool:
            """Stop only optional refinement when its comparable-start wait expires."""
            nonlocal optional_search_stop
            try:
                measured = measure_candidate(settings, stage)
                if measured is None:
                    optional_search_stop = {
                        "reason": "candidate-budget", "stage": stage,
                        "completedCandidateCount": len(candidates),
                    }
                    return False
            except self.errors.cooldown:
                optional_search_stop = {
                    "reason": "resource-cooldown-timeout",
                    "stage": stage,
                    "completedCandidateCount": len(candidates),
                }
                self._event(
                    "oMLX's optional verifier/quantization refinement reached its resource "
                    "cooldown limit after every required DFlash block size was measured. "
                    "Calibration will keep the fastest completed comparable candidate.",
                    "warning",
                )
                return False
            return True

        anchor = copy.deepcopy(plan["anchor"])
        for block_size in plan["blockCandidates"]:
            settings = copy.deepcopy(anchor)
            settings["blockSize"] = int(block_size)
            measure_candidate(settings, "block")
        best = self._best_tuning_candidate(candidates)
        verifier_anchor = copy.deepcopy(best["settings"])
        for verify_mode in self.services.controls._ordered_unique([
            verifier_anchor["verifyMode"], *plan["verifyCandidates"],
        ]):
            settings = copy.deepcopy(verifier_anchor)
            settings["verifyMode"] = str(verify_mode)
            if not measure_optional_candidate(settings, "verifier"):
                break
        best = self._best_tuning_candidate(candidates)
        quant_anchor = copy.deepcopy(best["settings"])
        if optional_search_stop is None:
            for draft_quant in self.services.controls._ordered_unique([
                quant_anchor["draftQuant"], *plan["quantCandidates"],
            ]):
                settings = copy.deepcopy(quant_anchor)
                settings["draftQuant"] = str(draft_quant)
                if not measure_optional_candidate(settings, "quantization"):
                    break
        if self.cancel_event.is_set():
            raise self.errors.cancelled("Engine Shootout cancelled before DFlash tuning was committed.")
        best = self._best_tuning_candidate(candidates)
        best["selected"] = True
        self._publish_shootout_tuning(
            "omlx", "omlx-dflash2", candidates, best["key"],
            maximum_candidates,
        )
        final_results["dflash2"] = best["_result"]
        record = self._build_record(job, final_results)
        public_candidates = [
            {
                key: copy.deepcopy(value)
                for key, value in candidate.items() if key != "_result"
            }
            for candidate in candidates
        ]
        record["kind"] = "omlx-dflash2-tuning"
        record["tuningSweep"] = {
            "version": self.policy.benchmark_dflash_tuner_version,
            "strategy": "bounded-coordinate-search",
            "selectionMetric": str(plan["selectionMetric"]),
            "searchedAxes": ["blockSize", "verifyMode", "draftQuant"],
            "baselineModes": list(plan["baselineModes"]),
            "complete": True, "resourceComparable": True,
            "optionalSearchComplete": optional_search_stop is None,
            "optionalSearchStop": copy.deepcopy(optional_search_stop),
            "baselineResourceStatus": str(baseline_gate.get("status") or ""),
            "candidateCount": len(public_candidates),
            "maximumCandidates": maximum_candidates,
            "selectedCandidateKey": best["key"],
            "selectedSettings": copy.deepcopy(best["settings"]),
            "candidates": public_candidates,
        }
        settings = best["settings"]
        if record["winner"] == "dflash2":
            record["recommendation"] = (
                f"Use DFlash block {settings['blockSize']} with "
                f"{settings['verifyMode']} verification and {settings['draftQuant']} "
                f"draft precision: it was the fastest correctness-clearing load across "
                f"{len(candidates)} bounded candidates."
            )
        elif record["winner"] == "mtp":
            record["recommendation"] = (
                f"Use native MTP: it beat AR and the best of {len(candidates)} "
                "correctness-gated DFlash candidates."
            )
        else:
            record["recommendation"] = (
                f"Keep AR: none of {len(candidates)} bounded DFlash candidates"
                + (" or native MTP" if "mtp" in plan["baselineModes"] else "")
                + " cleared exact parity and the speed noise floor."
            )
        if optional_search_stop is not None:
            record["recommendation"] += (
                " Optional verifier/quantization refinement stopped at the resource "
                "cooldown limit after every required DFlash block size was compared; "
                "this result uses the fastest completed comparable candidate."
            )
        if not self.evidence._local_benchmark_record_verified(capability, record, job["evidence"]):
            raise RuntimeError("The completed DFlash Calibration sweep failed its evidence contract.")
        return record, completed, resource_reference

    def _build_qualification_result(
        self, qualification: dict[str, Any], record: dict[str, Any],
        models: list[dict[str, Any]],
    ) -> dict[str, Any]:
        model = next(
            item for item in models if item.get("id") == qualification["modelId"]
        )
        preference = str(qualification.get("enginePreference") or "throughput")
        backend = str(record["backend"])
        route = self.services.presentation.public_route_qualification_result(model, record, preference)
        metrics = record["qualification"]["metrics"]
        rationale = str(record["recommendation"])
        binding = {
            "scope": "route", "suite": str(record.get("suite") or qualification["suite"]),
            "preference": preference, "recordId": str(record["id"]),
        }
        decision = {
            "preference": preference,
            "preferenceLabel": self.policy.engine_preference_labels[preference],
            "backend": backend, "label": self.policy.backend_labels[backend],
            "backendLabel": self.policy.backend_labels[backend],
            "engineChanged": False,
            "evidenceTier": "local-route-qualification",
            "evidenceLabel": f"Qualified {self.policy.backend_labels[backend]} route",
            "qualified": True, "trusted": True, "trustedWinner": False,
            "comparedEngines": [], "qualifiedRoutes": [route],
            "missingEngines": [], "rationale": [rationale],
            "recommendation": rationale,
            "leadingBackends": [], "currentInLeadingBand": True,
            "routeQualification": True, "evidenceBinding": copy.deepcopy(binding),
        }
        return {
            "id": qualification["id"], "kind": "route-qualification",
            "routeQualification": True,
            "qualificationVersion": self.policy.route_qualification_version,
            "modelId": qualification["modelId"], "model": qualification["model"],
            "suite": qualification["suite"],
            "workloadKind": qualification["workloadKind"],
            "reasoningContract": copy.deepcopy(qualification["reasoningContract"]),
            "qualificationContract": copy.deepcopy(record.get("qualificationContract")),
            "qualified": True, "qualifiedBackend": backend,
            "qualifiedRoutes": [route], "engines": [route],
            "authoritativeUsage": {
                "promptTokens": metrics["promptTokens"],
                "completionTokens": metrics["completionTokens"],
            },
            "evidenceBinding": binding,
            "decision": decision, "recommendation": rationale,
        }

    def _qualification_worker(
        self, qualification: dict[str, Any], models: list[dict[str, Any]],
    ) -> None:
        job = qualification["job"]
        backend = str(job["backend"])
        spec = qualification["routeSpec"]
        total = (
            2 + self.services.planning.benchmark_measurement_count(job["suite"])
            + int(spec.get("toolProbeRequired") is True)
        )
        try:
            gate = self._wait_for_resource_baseline(
                f"{spec['routeLabel']} qualification", backend,
            )
            admission = self.services.planning.route_qualification_memory_admission(
                qualification["request"], models,
                hub=self.owner.snapshot(),
                operation={
                    "active": False, "kind": "benchmark", "phase": "running",
                    "detail": "This route qualification owns the next model load.",
                },
            )
            if not self.services.planning.route_qualification_admission_ready(admission):
                raise RuntimeError(
                    "Capacity changed before the qualified model load. "
                    f"{admission.get('label') or 'The route is blocked'}: "
                    f"{admission.get('detail') or 'refresh capacity and try again.'}"
                )
            with self.lock:
                if isinstance(self.state.get("job"), dict):
                    self.state["job"]["memoryAdmission"] = copy.deepcopy(admission)
            result, _completed = self._measure_mode(
                job, models, "ar", 0, total, gate,
                display_label=str(spec["modeLabel"]), state_key="ar",
            )
            if self.cancel_event.is_set():
                raise self.errors.cancelled("Route qualification cancelled before its result was saved.")
            record = self._build_record(job, {"ar": result})
            qualification_model = next(
                (
                    item for item in models
                    if item.get("id") == qualification.get("modelId")
                ),
                None,
            )
            capability = (
                qualification_model.get("backends", {}).get(backend)
                if isinstance(qualification_model, dict) else None
            )
            if (
                not isinstance(capability, dict)
                or not self.evidence._local_benchmark_record_verified(
                    capability, record, job["evidence"],
                )
            ):
                raise RuntimeError(
                    "The completed route failed its immutable local-evidence audit; "
                    "no qualification result was trusted or saved."
                )
            public_result = self._build_qualification_result(
                qualification, record, models,
            )
            with self.lock:
                # Cancellation and the persistence/publication boundary share
                # this lock.  Stop therefore wins before saving, or observes
                # one already-completed result; it can never publish
                # "stopping" between those two outcomes.
                if self.cancel_event.is_set():
                    raise self.errors.cancelled(
                        "Route qualification cancelled before its result was saved."
                    )
                self.services.store.save_benchmark_record(record)
                public_result["persistence"] = {
                    "saved": True, "scope": "local", "recordCount": 1,
                    "savedAt": datetime.now(timezone.utc).isoformat(),
                }
                self.state["phase"] = "completed"
                self.state["progress"] = 1.0
                self.state["result"] = copy.deepcopy(public_result)
                engine = self.state.get("engines", {}).get(backend)
                if isinstance(engine, dict):
                    engine["phase"] = "completed"
                    engine["record"] = {
                        "qualifiedRoute": "ar", "qualifiedRouteLabel": str(spec["modeLabel"]),
                        "recommendation": record["recommendation"],
                    }
            self._event(record["recommendation"])
        except self.errors.safety as error:
            with self.lock:
                self.state["phase"] = "failed"
                engine = self.state.get("engines", {}).get(backend)
                if isinstance(engine, dict):
                    engine["phase"] = "failed"
            self._event(str(error), "error")
        except self.errors.cancelled:
            with self.lock:
                self.state["phase"] = "cancelled"
                engine = self.state.get("engines", {}).get(backend)
                if isinstance(engine, dict):
                    engine["phase"] = "cancelled"
            self._event(
                "Route qualification cancelled. No partial result was trusted or saved.",
                "warning",
            )
        except Exception as error:  # noqa: BLE001
            safety_failure = (
                self.qualification_safety_violation
                or self.owner.safety_violation(self.active_plan)
            )
            if safety_failure:
                with self.lock:
                    self.state["phase"] = "failed"
                    engine = self.state.get("engines", {}).get(backend)
                    if isinstance(engine, dict):
                        engine["phase"] = "failed"
                self._event(safety_failure, "error")
            elif self.cancel_event.is_set():
                with self.lock:
                    self.state["phase"] = "cancelled"
                    engine = self.state.get("engines", {}).get(backend)
                    if isinstance(engine, dict):
                        engine["phase"] = "cancelled"
                self._event(
                    "Route qualification cancelled. No partial result was trusted or saved.",
                    "warning",
                )
            else:
                with self.lock:
                    self.state["phase"] = "failed"
                    engine = self.state.get("engines", {}).get(backend)
                    if isinstance(engine, dict):
                        engine["phase"] = "failed"
                self._event(
                    f"Route qualification stopped before saving its result: {error}",
                    "error",
                )
        finally:
            if self.active_plan is not None:
                self.owner.stop(expected_plan=self.active_plan)
            with self.lock:
                self.active_plan = None
                if self.thread is threading.current_thread():
                    self.thread = None

    def _shootout_one_engine(
        self, job: dict[str, Any], models: list[dict[str, Any]],
        completed: int, total: int, resource_reference: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], int, dict[str, Any] | None]:
        tuning_plan = job.get("calibrationTuningPlan")
        if (
            isinstance(tuning_plan, dict)
            and job["backend"] in {"lmstudio", "omlx"}
        ):
            if job["backend"] == "lmstudio":
                record, completed, resource_reference = self._shootout_lmstudio_tuning(
                    job, models, completed, total, resource_reference,
                    premeasured_baseline=job.get("_premeasuredAR"),
                    premeasured_gate=(job.get("_premeasuredAR") or {}).get("resourceCooldown"),
                )
            elif job["backend"] == "omlx":
                record, completed, resource_reference = self._shootout_dflash_tuning(
                    job, models, completed, total, resource_reference,
                    premeasured_baseline=job.get("_premeasuredAR"),
                    premeasured_gate=(job.get("_premeasuredAR") or {}).get("resourceCooldown"),
                )
            else:
                raise RuntimeError("Calibration created an unsupported adaptive engine plan.")
            return record, completed, resource_reference
        long_operator_plan = bool(
            isinstance(tuning_plan, dict)
            and job["backend"] == "mtplx"
            and tuning_plan.get("strategy")
            == "isolated-long-context-operator-comparison"
        )
        if isinstance(tuning_plan, dict) and not long_operator_plan:
            raise RuntimeError(
                "Calibration created an unsupported adaptive engine plan."
            )
        results: dict[str, dict[str, Any]] = {}
        mtplx_depth_candidates: list[dict[str, Any]] = []
        mtplx_operator_results: dict[str, dict[str, Any]] = {}
        mtplx_operator_resource_status: dict[str, str] = {}
        for route in self.services.planning.benchmark_job_measurement_routes(job):
            if self.cancel_event.is_set():
                raise self.errors.cancelled("Engine Shootout cancelled.")
            mode = str(route["mode"])
            if mode == "ar" and isinstance(job.get("_premeasuredAR"), dict):
                results["ar"] = job["_premeasuredAR"]
                continue
            route_label = f"{self.policy.backend_labels[job['backend']]} · {route['label']}"
            gate, resource_reference = self._shootout_tuning_gate(
                route_label, str(job["backend"]), resource_reference,
            )
            candidate_job = job
            route_settings = route.get("settings")
            if (
                job["backend"] == "mtplx" and mode == "mtp"
                and isinstance(route_settings, dict)
                and isinstance(route_settings.get("depth"), int)
            ):
                candidate_job = copy.deepcopy(job)
                candidate_job["_benchmarkMtpDepth"] = int(route_settings["depth"])
                if long_operator_plan:
                    operator_route = str(route.get("operatorRoute") or "")
                    if operator_route not in {
                        self.policy.mtplx_long_context_default_route,
                        self.policy.mtplx_long_context_2111_route,
                    }:
                        raise RuntimeError(
                            "Calibration created an unknown MTPLX operator route."
                        )
                    candidate_job["_benchmarkMtplxOperatorRoute"] = operator_route
            result, completed = self._measure_mode(
                candidate_job, models, mode, completed, total, gate,
                display_label=str(route["label"]),
                state_key=str(route["stateKey"]),
            )
            if long_operator_plan and mode == "mtp":
                operator_route = str(route["operatorRoute"])
                mtplx_operator_results[operator_route] = result
                mtplx_operator_resource_status[operator_route] = str(
                    gate.get("status") or ""
                )
                continue
            if candidate_job is not job:
                if "ar" not in results:
                    raise RuntimeError(
                        "MTPLX depth tuning started before its AR correctness reference."
                    )
                mtplx_depth_candidates.append(
                    self._mtplx_depth_candidate_summary(
                        results["ar"], result,
                        int(route_settings["depth"]),
                        str(gate.get("status") or ""),
                        self.evidence.benchmark_route_selection_metric(job),
                    )
                )
                with self.lock:
                    engine = self.state.get("engines", {}).get("mtplx")
                    if isinstance(engine, dict):
                        engine["depthSweep"] = [
                            {
                                key: copy.deepcopy(value)
                                for key, value in candidate.items()
                                if key != "_result"
                            }
                            for candidate in mtplx_depth_candidates
                        ]
                continue
            results[mode] = result
        mtplx_operator_candidates: list[dict[str, Any]] = []
        if long_operator_plan:
            baseline_result = mtplx_operator_results.get(
                self.policy.mtplx_long_context_default_route
            )
            candidate_result = mtplx_operator_results.get(
                self.policy.mtplx_long_context_2111_route
            )
            if (
                "ar" not in results
                or not isinstance(baseline_result, dict)
                or not isinstance(candidate_result, dict)
            ):
                raise RuntimeError(
                    "MTPLX long-context operator calibration returned an incomplete route matrix."
                )
            mtplx_operator_candidates = self._mtplx_operator_candidate_summaries(
                results["ar"], baseline_result, candidate_result,
                mtplx_operator_resource_status.get(
                    self.policy.mtplx_long_context_default_route, "",
                ),
                mtplx_operator_resource_status.get(
                    self.policy.mtplx_long_context_2111_route, "",
                ),
            )
            if not all(
                item.get("resourceComparable") is True
                for item in mtplx_operator_candidates
            ):
                raise RuntimeError(
                    "MTPLX operator routes did not start under comparable Mac conditions. "
                    "Nothing was saved; retry when the Mac is idle."
                )
            by_route = {
                str(item["route"]): item
                for item in mtplx_operator_candidates
            }
            measured_candidate = by_route[self.policy.mtplx_long_context_2111_route]
            candidate_accepted = bool(
                measured_candidate["qualityMatchesAR"] is True
                and measured_candidate["qualityMatchesDefault"] is True
                and float(measured_candidate["_medianSpeedupVsDefaultRaw"])
                >= self.policy.benchmark_minimum_speedup
                and float(measured_candidate["_worstCaseSpeedupVsDefaultRaw"])
                >= self.policy.benchmark_minimum_speedup
            )
            selected_route = (
                self.policy.mtplx_long_context_2111_route
                if candidate_accepted else self.policy.mtplx_long_context_default_route
            )
            selected_operator = by_route[selected_route]
            selected_operator["selected"] = True
            results["mtp"] = selected_operator["_result"]
        if mtplx_depth_candidates:
            if not all(
                candidate.get("resourceComparable") is True
                for candidate in mtplx_depth_candidates
            ):
                raise RuntimeError(
                    "MTPLX depth candidates did not start under comparable Mac conditions. "
                    "Nothing was saved; retry when the Mac is idle."
                )
            best_depth = self._best_tuning_candidate(mtplx_depth_candidates)
            best_depth["selected"] = True
            results["mtp"] = best_depth["_result"]
        record = self._build_record(job, results)
        if mtplx_operator_candidates:
            plan = job["calibrationTuningPlan"]
            public_candidates = [
                {
                    key: copy.deepcopy(value)
                    for key, value in item.items()
                    if not key.startswith("_")
                }
                for item in mtplx_operator_candidates
            ]
            selected = next(
                item for item in public_candidates
                if item["selected"] is True
            )
            measured_candidate = next(
                item for item in public_candidates
                if item["route"] == self.policy.mtplx_long_context_2111_route
            )
            record.update({
                "kind": "mtplx-long-context-operator-tuning",
                "selectionPreference": "throughput",
                "modelPath": str(plan["contract"]["modelPath"]),
                "mtplxOperatorSweep": {
                    "version": self.policy.mtplx_long_context_2111_sweep_version,
                    "strategy": "isolated-long-context-operator-comparison",
                    "complete": True,
                    "resourceComparable": True,
                    "suiteName": self.policy.mtplx_long_context_64k_suite,
                    "requiredContext": self.policy.mtplx_long_context_minimum,
                    "contractId": str(plan["contractId"]),
                    "contract": copy.deepcopy(plan["contract"]),
                    "baselineRoute": self.policy.mtplx_long_context_default_route,
                    "candidateRoute": self.policy.mtplx_long_context_2111_route,
                    "baselineEnvironment": _mutable_policy_copy(
                        self.policy.mtplx_long_context_baseline_env
                    ),
                    "candidateEnvironment": _mutable_policy_copy(
                        self.policy.mtplx_long_context_candidate_env
                    ),
                    "selectionMetric": "generation-tokens-per-second",
                    "minimumMedianSpeedup": self.policy.benchmark_minimum_speedup,
                    "minimumWorstSpeedup": self.policy.benchmark_minimum_speedup,
                    "qualificationContract": copy.deepcopy(
                        plan["qualificationContract"]
                    ),
                    "fixedMtpDepth": int(plan["fixedMtpDepth"]),
                    "candidateAccepted": bool(
                        measured_candidate["selected"] is True
                    ),
                    "selectedRoute": str(selected["route"]),
                    "selectedSettings": copy.deepcopy(selected["settings"]),
                    "arMeasurement": self.evidence._mtplx_operator_measurement_evidence(
                        results["ar"],
                    ),
                    "routeMeasurements": {
                        self.policy.mtplx_long_context_default_route:
                            self.evidence._mtplx_operator_measurement_evidence(
                                baseline_result,
                            ),
                        self.policy.mtplx_long_context_2111_route:
                            self.evidence._mtplx_operator_measurement_evidence(
                                candidate_result,
                            ),
                    },
                    "candidates": public_candidates,
                },
            })
            if record["winner"] == "mtp":
                if selected["route"] == self.policy.mtplx_long_context_2111_route:
                    record["recommendation"] = (
                        "Use MTPLX's measured 2.11.1 long-context MTP route: "
                        "it preserved exact greedy output and cleared the 3% median "
                        "and worst-generation-TPS gates over the isolated default route, "
                        "then beat AR by the same noise floor."
                    )
                else:
                    record["recommendation"] = (
                        "Use MTPLX's default MTP route: the 2.11.1 long-context "
                        "operator candidate did not clear every promotion gate, and "
                        "the default route still beat AR by generation TPS."
                    )
            elif selected.get("qualityMatchesAR") is not True:
                record["recommendation"] = (
                    "Keep MTPLX AR: the tested MTP output did not exactly match the greedy "
                    "reference. Its measured speed is shown, but it is not eligible for "
                    "automatic selection."
                )
            else:
                record["recommendation"] = (
                    "Keep MTPLX AR: the selected correctness-preserving MTP operator "
                    "route did not beat AR across both median and worst generation TPS "
                    "by the 3% noise floor."
                )
            capability = job["model"]["backends"]["mtplx"]
            if not self.evidence._local_benchmark_record_verified(
                capability, record, job["evidence"],
            ):
                raise RuntimeError(
                    "The completed MTPLX long-context operator sweep failed its "
                    "immutable evidence contract."
                )
        if mtplx_depth_candidates:
            public_candidates = [
                {
                    key: copy.deepcopy(value)
                    for key, value in candidate.items()
                    if key != "_result"
                }
                for candidate in mtplx_depth_candidates
            ]
            selected = next(
                candidate for candidate in public_candidates
                if candidate["selected"] is True
            )
            record["mtpDepthSweep"] = {
                "version": self.policy.mtplx_mtp_depth_sweep_version,
                "strategy": "exhaustive-verified-depths",
                "selectionMetric": self.evidence.benchmark_route_selection_metric(job),
                "complete": True,
                "resourceComparable": True,
                "depthCandidates": self.evidence.mtplx_mtp_depth_candidates(
                    job["model"]["backends"]["mtplx"],
                ),
                "candidateCount": len(public_candidates),
                "maximumCandidates": self.policy.mtplx_mtp_depth_sweep_max_candidates,
                "selectedDepth": selected["depth"],
                "selectedSettings": copy.deepcopy(selected["settings"]),
                "candidates": public_candidates,
            }
            if record["winner"] == "mtp":
                record["recommendation"] = (
                    f"Use MTP D{selected['depth']}: it was the fastest verified MTPLX "
                    f"depth and cleared exact AR parity plus the "
                    f"{self.policy.benchmark_minimum_speedup:.2f}× median/worst-case noise floor."
                )
            else:
                record["recommendation"] = (
                    f"Keep AR: none of the {len(public_candidates)} verified MTPLX "
                    "depths cleared exact parity and the speed noise floor."
                )
        return record, completed, resource_reference

    def _shootout_worker(
        self, shootout: dict[str, Any], models: list[dict[str, Any]],
    ) -> None:
        jobs = shootout["jobs"]
        total = sum(
            (2 + self.services.planning.benchmark_measurement_count(job["suite"]))
            * self.services.planning.benchmark_job_maximum_route_count(job)
            for job in jobs
        )
        completed = 0
        records: list[dict[str, Any]] = []
        resource_reference: dict[str, Any] | None = None
        try:
            for job in jobs:
                if self.cancel_event.is_set():
                    raise self.errors.cancelled("Engine Shootout cancelled.")
                record, completed, resource_reference = self._shootout_settings_search(
                    job, models, completed, total, resource_reference,
                )
                records.append(record)
                with self.lock:
                    engine = self.state.get("engines", {}).get(job["backend"])
                    if isinstance(engine, dict):
                        engine["phase"] = "measured"
                        engine["record"] = {
                            "winner": record["winner"],
                            "winnerLabel": self._mode_label(str(record["winner"])),
                            "recommendation": record["recommendation"],
                        }
                self._event(
                    f"{self.policy.backend_labels[job['backend']]} complete; its result is staged until every engine finishes."
                )
            if self.cancel_event.is_set():
                raise self.errors.cancelled("Engine Shootout cancelled before its matrix was committed.")
            result = self._build_shootout_result(shootout, records, models)
            with self.lock:
                if self.cancel_event.is_set():
                    raise self.errors.cancelled("The job was cancelled before its evidence commit.")
                self.services.store.save_benchmark_records(records)
                result["persistence"] = {
                    "saved": True,
                    "scope": "local",
                    "recordCount": len(records),
                    "savedAt": datetime.now(timezone.utc).isoformat(),
                    **(
                        {"evidenceBinding": copy.deepcopy(result["evidenceBinding"])}
                        if isinstance(result.get("evidenceBinding"), dict) else {}
                    ),
                }
                self.state["phase"] = "completed"
                self.state["progress"] = 1.0
                self.state["result"] = copy.deepcopy(result)
                for engine in self.state.get("engines", {}).values():
                    if isinstance(engine, dict):
                        engine["phase"] = "completed"
            self._event(result["recommendation"])
        except self.errors.cancelled:
            with self.lock:
                self.state["phase"] = "cancelled"
            self._event(
                "Engine Shootout cancelled. No partial engine matrix was trusted or saved.",
                "warning",
            )
        except Exception as error:  # noqa: BLE001
            if self.cancel_event.is_set():
                with self.lock:
                    self.state["phase"] = "cancelled"
                self._event(
                    "Engine Shootout cancelled. No partial engine matrix was trusted or saved.",
                    "warning",
                )
            else:
                with self.lock:
                    self.state["phase"] = "failed"
                self._event(
                    f"Engine Shootout stopped before saving its matrix: {error}", "error",
                )
        finally:
            if self.active_plan is not None:
                self.owner.stop(expected_plan=self.active_plan)
            with self.lock:
                self.active_plan = None
                if self.thread is threading.current_thread():
                    self.thread = None

    def _worker(self, job: dict[str, Any], models: list[dict[str, Any]]) -> None:
        steps_per_mode = 2 + self.services.planning.benchmark_measurement_count(job["suite"])
        operator_sweep = bool(
            job["backend"] == "mtplx"
            and isinstance(job.get("calibrationTuningPlan"), dict)
            and job["calibrationTuningPlan"].get("strategy")
            == "isolated-long-context-operator-comparison"
        )
        total = steps_per_mode * (
            self.services.planning.benchmark_job_maximum_route_count(job) if operator_sweep else len(job["modes"])
        )
        completed = 0
        results: dict[str, dict[str, Any]] = {}
        try:
            if operator_sweep:
                record, completed, _reference = self._shootout_one_engine(
                    job, models, completed, total, None,
                )
            else:
                for mode in job["modes"]:
                    if self.cancel_event.is_set():
                        raise self.errors.cancelled("Benchmark cancelled.")
                    result, completed = self._measure_mode(job, models, mode, completed, total)
                    results[mode] = result
                record = self._build_record(job, results)
            with self.lock:
                if self.cancel_event.is_set():
                    raise self.errors.cancelled("The job was cancelled before its evidence commit.")
                self.services.store.save_benchmark_record(record)
                self.state["phase"] = "completed"
                self.state["progress"] = 1.0
                self.state["result"] = copy.deepcopy(record)
            self._event(record["recommendation"])
        except self.errors.cancelled:
            with self.lock:
                self.state["phase"] = "cancelled"
            self._event("Benchmark cancelled. No partial result was trusted or saved.", "warning")
        except Exception as error:  # noqa: BLE001
            if self.cancel_event.is_set():
                with self.lock:
                    self.state["phase"] = "cancelled"
                self._event("Benchmark cancelled. No partial result was trusted or saved.", "warning")
            else:
                with self.lock:
                    self.state["phase"] = "failed"
                self._event(str(error), "error")
        finally:
            if self.active_plan is not None:
                self.owner.stop(expected_plan=self.active_plan)
            with self.lock:
                self.active_plan = None
                if self.thread is threading.current_thread():
                    self.thread = None

class RuntimePromotionManager(BenchmarkManager):
    """Measure two exact oMLX copies and gate a separate explicit selection change."""

    def __init__(self, owner: RunOwnerPort, policy: BenchmarkPolicy, services: BenchmarkServices, evidence: EvidencePort, promotion_policy: PromotionPolicy, promotion: PromotionServices, errors: BenchmarkErrors = BenchmarkErrors()) -> None:
        super().__init__(owner, policy, services, evidence, errors)
        self.promotion_policy = promotion_policy
        self.promotion = promotion
        self.plans: dict[str, dict[str, Any]] = {}
        self.state = {
            "phase": "idle", "message": "No runtime comparison is running.",
            "progress": 0.0, "plan": None, "modes": {}, "runtimes": {},
            "result": None, "events": [],
        }

    def _prune(self) -> None:
        now = time.time()
        self.plans = {
            plan_id: entry for plan_id, entry in self.plans.items()
            if float(entry.get("expires", 0)) > now
        }

    def inspect(
        self, payload: dict[str, Any], models: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if self.is_active():
            raise ValueError("Wait for the active runtime comparison before replacing its plan.")
        plan = self.promotion.build_runtime_promotion_plan(payload, models)
        expires = time.time() + self.promotion_policy.plan_ttl_seconds
        plan["expiresAt"] = datetime.fromtimestamp(expires, timezone.utc).isoformat()
        with self.lock:
            if self.is_active():
                raise ValueError("Wait for the active runtime comparison before replacing its plan.")
            self._prune()
            self.plans[plan["id"]] = {
                "expires": expires,
                "request": copy.deepcopy(payload),
                "plan": copy.deepcopy(plan),
            }
        return self.promotion.runtime_promotion_public_plan(plan)

    def _validated_start_plan(
        self, payload: dict[str, Any], models: list[dict[str, Any]],
    ) -> dict[str, Any]:
        plan_id = str(payload.get("planId") or "")
        with self.lock:
            self._prune()
            entry = copy.deepcopy(self.plans.get(plan_id))
        if not entry:
            raise ValueError("The runtime comparison plan expired or changed. Review it again.")
        current = self.promotion.build_runtime_promotion_plan(entry["request"], models)
        if current.get("id") != plan_id:
            raise ValueError("A runtime, model, executable revision, or comparison condition changed. Review a fresh plan.")
        if payload.get("reviewed") is not True:
            raise ValueError("Review the exact runtimes, model, workload, and promotion guards first.")
        if not secrets.compare_digest(
            str(payload.get("confirmation") or ""), str(current.get("confirmation") or ""),
        ):
            raise ValueError("Confirm the exact runtime comparison before loading either model route.")
        if current.get("canStart") is not True:
            admission = current.get("memoryAdmission")
            raise ValueError(
                f"{admission.get('label') if isinstance(admission, dict) else 'Mac capacity is not ready'}: "
                f"{admission.get('detail') if isinstance(admission, dict) else 'refresh capacity before comparing runtimes.'}"
            )
        return current

    def start(
        self, payload: dict[str, Any], models: list[dict[str, Any]],
    ) -> dict[str, Any]:
        plan = self._validated_start_plan(payload, models)
        if self.owner.snapshot().get("phase") != "idle":
            raise ValueError("Stop the active launcher run before comparing runtime versions.")
        with self.lock:
            if self.is_active():
                raise ValueError("A runtime comparison is already running.")
            self.cancel_event = threading.Event()
            public_plan = self.promotion.runtime_promotion_public_plan(plan)
            runtime_state = {
                role: {
                    "role": role, "phase": "queued",
                    "version": plan[role]["version"], "result": None,
                }
                for role in ("selected", "candidate")
            }
            self.state = {
                "phase": "queued",
                "message": f"Runtime comparison approved. Preparing {plan['executionOrder'][0]} copy first…",
                "progress": 0.0, "plan": public_plan, "modes": {},
                "runtimes": runtime_state, "result": None, "events": [],
            }
            thread = threading.Thread(
                target=self._worker, args=(copy.deepcopy(plan), copy.deepcopy(models)),
                daemon=True,
            )
            self.thread = thread
            self._start_thread(thread)
        return public_plan

    def cancel(self) -> None:
        with self.lock:
            if self.state.get("phase") not in self.ACTIVE_PHASES:
                return
            self.state["phase"] = "stopping"
            self.state["message"] = "Stopping the runtime comparison; the selected copy will not change…"
            self.cancel_event.set()
            plan = self.active_plan
        if plan is not None and self.owner.owns_plan(plan):
            self.owner.stop(expected_plan=plan)

    def _worker(self, plan: dict[str, Any], models: list[dict[str, Any]]) -> None:
        job_template = plan["_job"]
        steps_per_runtime = 2 + self.services.planning.benchmark_measurement_count(job_template["suite"])
        total = steps_per_runtime * 2
        completed = 0
        results: dict[str, dict[str, Any]] = {}
        resource_reference: dict[str, Any] | None = None
        selected_before = self.promotion.selected_runtime()
        try:
            for role in plan["executionOrder"]:
                if self.cancel_event.is_set():
                    raise self.errors.cancelled("Runtime comparison cancelled.")
                runtime = plan[role]
                revision = self.promotion.runtime_executable_revision(runtime["path"])
                if revision.get("id") != runtime.get("revision", {}).get("id"):
                    raise RuntimeError(f"The {role} runtime executable changed before measurement.")
                if role == "candidate" and not self.promotion.managed_runtime_verification(runtime["path"]).get("verified"):
                    raise RuntimeError("The candidate's official wheel provenance changed before measurement.")
                with self.lock:
                    self.state["runtimes"][role]["phase"] = "cooldown"
                route_label = f"{role.capitalize()} · oMLX {runtime['version']}"
                gate = self._wait_for_resource_baseline(
                    route_label, "omlx", resource_reference,
                )
                if resource_reference is None and gate.get("status") != "unavailable":
                    resource_reference = copy.deepcopy(gate.get("reference"))
                job = copy.deepcopy(job_template)
                job.update({
                    "id": str(uuid.uuid4()),
                    "runtimePromotionId": plan["id"],
                    "runtimePromotionRole": role,
                    "runtimeVersion": runtime["version"],
                    "_runtimeBinary": runtime["resolvedPath"],
                    "_runtimeRevision": copy.deepcopy(runtime["revision"]),
                    "modes": ["ar"],
                })
                with self.lock:
                    self.state["runtimes"][role]["phase"] = "starting"
                result, completed = self._measure_mode(
                    job, models, "ar", completed, total, gate,
                    display_label=route_label, state_key=role,
                )
                results[role] = result
                with self.lock:
                    self.state["runtimes"][role]["phase"] = "measured"
                    self.state["runtimes"][role]["result"] = {
                        "medianEndToEndTokensPerSecond": result.get("medianEndToEndTokensPerSecond"),
                        "medianTTFT": result.get("medianTTFT"),
                    }
                self._event(f"{route_label} complete and stopped; its evidence is staged until both copies finish.")
            if self.cancel_event.is_set():
                raise self.errors.cancelled("Runtime comparison cancelled before evidence was committed.")
            if self.promotion.selected_runtime() != selected_before:
                raise RuntimeError("The selected oMLX preference changed during measurement; no result was trusted.")
            result = self.promotion.build_runtime_promotion_result(plan, results)
            with self.lock:
                if self.cancel_event.is_set():
                    raise self.errors.cancelled("The job was cancelled before its evidence commit.")
                self.promotion.save_runtime_promotion_record(result)
                self.state["phase"] = "completed"
                self.state["progress"] = 1.0
                self.state["result"] = copy.deepcopy(result)
                for runtime in self.state.get("runtimes", {}).values():
                    runtime["phase"] = "completed"
            self._event(result["recommendation"])
        except self.errors.cancelled:
            with self.lock:
                self.state["phase"] = "cancelled"
            self._event(
                "Runtime comparison cancelled. No partial evidence was saved and the selected runtime was unchanged.",
                "warning",
            )
        except Exception as error:  # noqa: BLE001
            if self.cancel_event.is_set():
                with self.lock:
                    self.state["phase"] = "cancelled"
                self._event(
                    "Runtime comparison cancelled. No partial evidence was saved and the selected runtime was unchanged.",
                    "warning",
                )
            else:
                with self.lock:
                    self.state["phase"] = "failed"
                self._event(
                    f"Runtime comparison stopped. No partial evidence was saved: {error}",
                    "error",
                )
        finally:
            if self.active_plan is not None:
                self.owner.stop(expected_plan=self.active_plan)
            with self.lock:
                self.active_plan = None
                if self.thread is threading.current_thread():
                    self.thread = None

    def promote(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.is_active():
            raise ValueError("Wait for the runtime comparison to finish before promoting its result.")
        record_id = str(payload.get("resultId") or "")
        record = next(
            (item for item in self.promotion.load_runtime_promotion_records() if item.get("id") == record_id),
            None,
        )
        if not record or record.get("canPromote") is not True:
            raise ValueError("That result is unavailable or did not clear every promotion guard.")
        expected = str(record.get("confirmation") or "")
        if not secrets.compare_digest(str(payload.get("confirmation") or ""), expected):
            raise ValueError("Confirm the exact measured runtime candidate before promoting it.")
        valid_until = self.promotion._benchmark_created_at(record.get("validUntil"))
        if valid_until is None or datetime.now(timezone.utc) > valid_until:
            raise ValueError("That runtime comparison is older than the promotion window. Measure it again.")
        if record.get("hardwareFingerprint") != self.services.resource.hardware_fingerprint():
            raise ValueError("The Mac or macOS identity changed after measurement. Measure again.")

        details = self.promotion.runtime_candidate_details("omlx")
        selected = next((item for item in details if item.get("selected") is True), None)
        candidate = next(
            (item for item in details if item.get("id") == record.get("candidate", {}).get("id")),
            None,
        )
        if not selected or selected.get("id") != record.get("selected", {}).get("id"):
            raise ValueError("The selected rollback runtime changed after measurement. Measure the current pair again.")
        if not candidate:
            raise ValueError("The measured candidate is no longer installed.")
        if not self.promotion.managed_runtime_verification(candidate["path"]).get("verified"):
            raise ValueError("The measured candidate no longer has verified official provenance.")
        for role, current in (("selected", selected), ("candidate", candidate)):
            revision = self.promotion.runtime_executable_revision(current["path"])
            if revision.get("id") != record.get(role, {}).get("revision", {}).get("id"):
                raise ValueError(f"The measured {role} executable changed. Run a fresh comparison.")

        inventory = self.promotion.select_runtime_candidate({
            "runtime": "omlx", "candidateId": candidate["id"],
            "confirmation": f"select:{candidate['id']}",
        })
        promoted = copy.deepcopy(record)
        promoted["selectionChanged"] = True
        promoted["promotedAt"] = datetime.now(timezone.utc).isoformat()
        self.promotion.save_runtime_promotion_record(promoted)
        with self.lock:
            current_result = self.state.get("result")
            if isinstance(current_result, dict) and current_result.get("id") == record_id:
                self.state["result"] = copy.deepcopy(promoted)
        self._event(
            f"oMLX {candidate.get('version')} is now selected for new sessions. The previous copy remains installed for rollback."
        )
        return {"result": promoted, "runtimeManager": inventory}
