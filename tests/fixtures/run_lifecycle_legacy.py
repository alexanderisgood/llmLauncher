"""Frozen complete pre-extraction RunManager; test-only controller imports."""
from __future__ import annotations
import copy
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
import fcntl
import hashlib
from http import HTTPStatus
import json
import math
import os
from pathlib import Path
import pty
import re
import secrets
import shlex
import signal
import statistics
import struct
import subprocess
import sys
import termios
import threading
import time
from types import MappingProxyType
import tty
from typing import Any, Callable, Mapping, Protocol
import urllib.error
import urllib.request
import uuid
from agent_console_transport import ConsoleTransport
import agent_console_rpc
import darwin_memory
import kolibri_runtime
import omp_protocol
import slotstream_runtime
import splash_runtime
import whallm_runtime
import whallm_telemetry

from launcher import (
    AGENT_CONSOLE_COLS,
    AGENT_CONSOLE_MAX_INPUT,
    AGENT_CONSOLE_ROWS,
    APP_DIR,
    AgentConsole,
    BACKEND_LABELS,
    BINARIES,
    CACHE_OBSERVATION_MAX,
    CACHE_OBSERVATORY_VERSION,
    CLIENT_ADAPTERS,
    CLIENT_LABELS,
    CONTROLLER_QUITTING,
    FREETOKEN_NATIVE_INSPECTION_MAX_RESPONSE,
    LLAMACPP_PLE_MEMORY_CEILING_BYTES,
    LLAMACPP_QWEN_REASONING_BUDGET_MESSAGE,
    LaunchCancelled,
    LaunchPlan,
    MTPLX_LONG_CONTEXT_OPERATOR_ENV_KEYS,
    PI_RPC_MAX_QUEUED_BYTES,
    PI_RPC_MAX_QUEUED_MESSAGES,
    PI_RPC_STATE_PROBE_SECONDS,
    REQUEST_ACTIVITY_VERSION,
    SESSION_IDLE_TIMEOUT_CHOICES,
    SESSION_OS_RESERVE_FRACTION,
    SESSION_OS_RESERVE_MIN_BYTES,
    SSD_STREAMING_BACKENDS,
    STATE_DIR,
    STRUCTURED_AGENT_PROTOCOLS,
    SURFACE_ATTACHMENT_MAX,
    SURFACE_ATTACHMENT_VERSION,
    SurfaceAttachment,
    UZU_PROCESS_MEMORY_CEILING_BYTES,
    WARM_ROUTE_VERSION,
    WHALLM_MODEL_ID,
    _SessionActivityTarget,
    _chat_resume_contract_for_plan,
    _confirm_open_uzu_executable,
    _environment_without_dyld,
    _require_omp_console_support,
    _uzu_api_key_file,
    apple_iogpu_wired_limit_bytes,
    apple_memory_pressure_state,
    atomic_json,
    build_chat_completion_request,
    build_client_plan,
    chat_settings_from_sampling_contract,
    confirm_llamacpp_launch_identities,
    darwin_process_group_physical_footprint,
    deep_get,
    dispose_plan_secrets,
    mtplx_flight_activity,
    mtplx_prompt_activity,
    omlx_activity_activity,
    omlx_prompt_activity,
    pi_model_identity,
    pi_rpc_accept_queued_prompt,
    pi_rpc_event_output,
    pi_rpc_heading,
    pi_rpc_line_limit,
    pi_rpc_queue_path,
    pi_rpc_record_queue,
    pi_rpc_unexpected_eof_output,
    pi_rpc_visible_queue,
    prepare_uzu_executable_launch,
    resolved_client_support,
    safe_agent_transcript_text,
    safe_agent_ui_text,
    sampling_contract_from_settings,
    sampling_route_enforcement,
    save_chat_history,
    save_chat_turn_checkpoint,
    selected_pi_binary,
    session_cache_policy,
    session_request_lanes,
    uzu_prompt_activity,
    validate_chat_capability,
    validate_live_native_freetoken,
    validate_llamacpp_launch_boundary,
    validate_sampling_capability,
    validate_uzu_launch_boundary,
    validated_agent_session_file,
    validated_chat_settings,
    validated_launch_profile_request,
    validated_profile_options,
    validated_sampling_contract,
    whallm_qualification_conflict,
)

class RunManager:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.lifecycle_lock = threading.Lock()
        self.stop_lock = threading.Lock()
        self.surface_lock = threading.Lock()
        self.engine_telemetry_lock = threading.Lock()
        self.mtplx_prefill_observations = {}
        self.whallm_telemetry_observations = {}
        self.state: dict[str, Any] = {"phase": "idle", "message": "Ready", "run": None, "events": []}
        self.process: subprocess.Popen[str] | None = None
        self.proxy_process: subprocess.Popen[str] | None = None
        self.aux_process: subprocess.Popen[str] | None = None
        self.worker_thread: threading.Thread | None = None
        self.monitor_thread: threading.Thread | None = None
        self.llamacpp_guard_thread: threading.Thread | None = None
        self.llamacpp_safety_violation: str | None = None
        self.cancel_event = threading.Event()
        self.cleanup_started = False
        self.cleanup_complete = threading.Event()
        self.cleanup_complete.set()
        self.lm_loaded_id: str | None = None
        self.plan: LaunchPlan | None = None
        self.started_at: str | None = None
        self.attachments: dict[str, SurfaceAttachment] = {}
        self.agent_consoles: dict[str, AgentConsole] = {}
        self.codex_proxy_port: int | None = None
        self.codex_proxy_key: str | None = None
        self.session_proxy_port: int | None = None
        self.session_proxy_control_key: str | None = None
        self.idle_timeout_minutes = 0
        self.idle_policy_set_at = time.time()
        self.cache_observations: list[dict[str, Any]] = []

    def event(self, message: str, level: str = "info") -> None:
        with self.lock:
            self.state["message"] = message
            self.state["events"] = (self.state.get("events", []) + [{"time": time.strftime("%H:%M:%S"), "level": level, "message": message}])[-80:]

    def _cache_observatory_unlocked(self) -> dict[str, Any]:
        plan = self.plan
        phase = str(self.state.get("phase") or "idle")
        resident = bool(plan is not None and plan.purpose == "session" and phase == "running")
        observations = copy.deepcopy(self.cache_observations) if resident else []
        completed = [item for item in observations if item.get("completed") is True]
        usage_rows = [item for item in observations if item.get("usageReported") is True]
        telemetry_rows = [
            item for item in usage_rows if item.get("cacheTelemetryReported") is True
        ]
        hit_rows = [item for item in telemetry_rows if int(item.get("cachedPromptTokens") or 0) > 0]
        miss_rows = [item for item in telemetry_rows if int(item.get("cachedPromptTokens") or 0) == 0]
        prompt_tokens = sum(int(item.get("promptTokens") or 0) for item in usage_rows)
        telemetry_prompt_tokens = sum(int(item.get("promptTokens") or 0) for item in telemetry_rows)
        cached_tokens = sum(int(item.get("cachedPromptTokens") or 0) for item in telemetry_rows)

        def median_ttft(rows: list[dict[str, Any]]) -> float | None:
            values = [
                float(item["ttftSeconds"])
                for item in rows
                if isinstance(item.get("ttftSeconds"), (int, float))
                and not isinstance(item.get("ttftSeconds"), bool)
            ]
            return round(float(statistics.median(values)), 6) if values else None

        if not resident:
            state = "idle"
            label = "No resident model"
            detail = "Start a normal model session to observe cache reports from built-in Chat."
        elif hit_rows:
            state = "confirmed-reuse"
            label = "Prefix reuse confirmed"
            detail = "At least one observed Chat turn reported cached prompt tokens."
        elif telemetry_rows:
            state = "reported-no-reuse"
            label = "No reuse reported yet"
            detail = "The runtime reported cache telemetry, but no observed turn contained cached prompt tokens."
        elif observations:
            state = "telemetry-unavailable"
            label = "Cache report unavailable"
            detail = "Observed Chat turns did not include cache-token telemetry; timing is not treated as proof."
        else:
            state = "warming"
            label = "Engine ready"
            detail = "The session route is ready. Send a Chat turn to see whether this runtime reports prefix reuse."

        return {
            "version": CACHE_OBSERVATORY_VERSION,
            "state": state,
            "label": label,
            "detail": detail,
            "engineResident": resident,
            "policy": session_cache_policy(plan if resident else None),
            "observationCount": len(observations),
            "completedTurns": len(completed),
            "usageReportedTurns": len(usage_rows),
            "cacheTelemetryReportedTurns": len(telemetry_rows),
            "confirmedHitTurns": len(hit_rows),
            "reportedNoReuseTurns": len(miss_rows),
            "reportedPromptTokens": prompt_tokens,
            "reportedCachedPromptTokens": cached_tokens,
            "reportedTokenReuseRate": (
                round(cached_tokens / telemetry_prompt_tokens, 6)
                if telemetry_prompt_tokens > 0 else None
            ),
            "reportedTurnHitRate": (
                round(len(hit_rows) / len(telemetry_rows), 6)
                if telemetry_rows else None
            ),
            "medianHitTtftSeconds": median_ttft(hit_rows),
            "medianMissTtftSeconds": median_ttft(miss_rows),
            "lastObservation": observations[-1] if observations else None,
            "coverage": {
                "surface": "built-in-chat",
                "detail": (
                    "Per-turn observations cover built-in Chat requests relayed by this controller. "
                    "Pi, OpenCode, and Codex share the resident engine/cache, but their direct agent "
                    "traffic is not labelled as observed."
                ),
                "timingProvesCacheHit": False,
            },
            "privacy": {
                "sessionScoped": True,
                "persistent": False,
                "maximumObservations": CACHE_OBSERVATION_MAX,
                "storesPromptText": False,
                "storesResponseText": False,
                "storesReasoningText": False,
                "storesProjectData": False,
                "storesCredentials": False,
            },
        }

    def cache_observatory(self) -> dict[str, Any]:
        with self.lock:
            return json.loads(json.dumps(self._cache_observatory_unlocked()))

    def record_chat_cache_observation(
        self, context: Any, observation: Any,
    ) -> None:
        """Retain one bounded numeric Chat observation for the current session only."""
        if not isinstance(context, dict) or not isinstance(observation, dict):
            return

        def safe_seconds(value: Any) -> float | None:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None
            parsed = float(value)
            return round(parsed, 6) if math.isfinite(parsed) and 0 <= parsed <= 86_400 else None

        def safe_tokens(value: Any) -> int | None:
            if isinstance(value, bool):
                return None
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                return None
            return parsed if 0 <= parsed <= 2_000_000_000 else None

        with self.lock:
            owner = self.plan
            if (
                owner is None or owner.purpose != "session"
                or self.state.get("phase") != "running"
                or str(context.get("ownerRunId") or "") != owner.run_id
            ):
                return
            attachment_id = str(context.get("attachmentId") or "")
            attachment = self.attachments.get(attachment_id)
            if attachment is None and not (
                attachment_id == owner.run_id and owner.client == "chat"
            ):
                return
            prompt_tokens = safe_tokens(observation.get("promptTokens"))
            completion_tokens = safe_tokens(observation.get("completionTokens"))
            cached_tokens = safe_tokens(observation.get("cachedPromptTokens"))
            usage_reported = prompt_tokens is not None and completion_tokens is not None
            telemetry_reported = bool(
                usage_reported
                and observation.get("cacheTelemetryReported") is True
                and cached_tokens is not None
            )
            if telemetry_reported:
                cached_tokens = min(int(prompt_tokens), int(cached_tokens))
            else:
                cached_tokens = None
            item = {
                "observedAt": datetime.now(timezone.utc).isoformat(),
                "surface": "Chat",
                "completed": observation.get("completed") is True,
                "interrupted": observation.get("interrupted") is True,
                "outputObserved": observation.get("outputObserved") is True,
                "usageReported": usage_reported,
                "cacheTelemetryReported": telemetry_reported,
                "promptTokens": prompt_tokens if usage_reported else None,
                "completionTokens": completion_tokens if usage_reported else None,
                "cachedPromptTokens": cached_tokens,
                "ttftSeconds": safe_seconds(observation.get("ttftSeconds")),
                "totalSeconds": safe_seconds(observation.get("totalSeconds")),
            }
            self.cache_observations = (
                self.cache_observations + [item]
            )[-CACHE_OBSERVATION_MAX:]

    def _request_activity_fallback(
        self, state: str, detail: str, *, resident: bool, lanes: int,
    ) -> dict[str, Any]:
        return {
            "version": REQUEST_ACTIVITY_VERSION,
            "state": state,
            "detail": detail,
            "engineResident": resident,
            "lanes": lanes,
            "activeCount": 0,
            "queuedCount": 0,
            "active": [],
            "queued": [],
            "recent": [],
            "surfaces": [],
            "lastActivityAt": None,
            "idleSeconds": None,
            "coverage": {
                "allLauncherSurfaces": False,
                "externalEngineClients": False,
                "detail": (
                    "Activity becomes authoritative when the private session relay is ready. "
                    "Independent clients that know the engine port are never guessed."
                ),
            },
            "privacy": {
                "storesPromptText": False,
                "storesResponseText": False,
                "storesReasoningText": False,
                "storesToolData": False,
                "storesProjectData": False,
                "persistent": False,
                "maximumRecentRequests": 32,
                "readsUsageMetadata": False,
                "estimatesTokens": False,
            },
        }

    def _activity_target_unlocked(self) -> _SessionActivityTarget:
        return _SessionActivityTarget(
            self.plan, self.plan.run_id if self.plan is not None else None,
            self.session_proxy_port, self.session_proxy_control_key,
            str(self.state.get("phase") or "idle"),
        )

    def _activity_target_matches_unlocked(self, target: _SessionActivityTarget) -> bool:
        return (
            target.owner is self.plan
            and target.run_id == (self.plan.run_id if self.plan is not None else None)
            and target.port == self.session_proxy_port
            and target.control_key == self.session_proxy_control_key
            and target.phase == str(self.state.get("phase") or "idle")
        )

    def _session_proxy_api(
        self, method: str, path: str, payload: dict[str, Any] | None = None,
        *, timeout: float = 1.0, _target: _SessionActivityTarget | None = None,
    ) -> dict[str, Any]:
        with self.lock:
            target = _target if _target is not None else self._activity_target_unlocked()
            if not self._activity_target_matches_unlocked(target):
                raise ValueError("The active model route changed. Refresh Sessions and try again.")
        owner, port, control_key, phase = target.owner, target.port, target.control_key, target.phase
        if (
            owner is None or owner.purpose != "session"
            or phase not in {"starting", "running", "stopping"}
            or not port or not control_key
        ):
            raise ValueError("The private session relay is not ready.")
        data = None
        headers = {"Authorization": f"Bearer {control_key}"}
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}", data=data, method=method, headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                value = json.loads(response.read(1_000_000))
        except urllib.error.HTTPError as error:
            try:
                value = json.loads(error.read(64_000))
                detail = deep_get(value, ("error", "message"), ("message",))
            except (OSError, ValueError, UnicodeError):
                detail = None
            raise ValueError(str(detail or f"Session relay returned HTTP {error.code}.")) from error
        except (OSError, ValueError, urllib.error.URLError) as error:
            raise ValueError(f"Could not reach the private session relay: {error}") from error
        if not isinstance(value, dict):
            raise ValueError("The private session relay returned an invalid response.")
        with self.lock:
            if not self._activity_target_matches_unlocked(target):
                raise ValueError("The active model route changed. Refresh Sessions and try again.")
        return value

    def request_activity(
        self, *, include_engine_telemetry: bool = True,
        _target: _SessionActivityTarget | None = None,
    ) -> dict[str, Any]:
        """Return relay evidence and idle policy, optionally enriched for the Hub."""
        with self.lock:
            target = _target if _target is not None else self._activity_target_unlocked()
            if not self._activity_target_matches_unlocked(target):
                return self._current_activity_unlocked(target, {})
        owner, phase = target.owner, target.phase
        resident = bool(owner is not None and owner.purpose == "session" and phase == "running")
        lanes = session_request_lanes(owner if owner and owner.purpose == "session" else None)
        if owner is None or owner.purpose != "session" or phase == "idle":
            activity = self._request_activity_fallback(
                "idle", "Start a normal model session to observe shared request activity.",
                resident=False, lanes=0,
            )
        else:
            try:
                activity = self._session_proxy_api("GET", "/__launcher/status", timeout=0.8, _target=target)
                activity["engineResident"] = resident
                activity["detail"] = (
                    f"{int(activity.get('lanes') or lanes)} engine-matched request lane"
                    f"{'s' if int(activity.get('lanes') or lanes) != 1 else ''}; "
                    "queued work is admitted first-come, first-served."
                )
            except ValueError as error:
                activity = self._request_activity_fallback(
                    "starting" if phase in {"preflight", "starting"} else "unavailable",
                    str(error), resident=resident, lanes=lanes,
                )
        if include_engine_telemetry and owner is not None and owner.purpose == "session":
            with self.engine_telemetry_lock:
                with self.lock:
                    if not self._activity_target_matches_unlocked(target):
                        return self._current_activity_unlocked(target, {})
                if owner.backend == "mtplx":
                    activity = mtplx_flight_activity(owner, activity)
                    activity = mtplx_prompt_activity(owner, activity, self.mtplx_prefill_observations)
                elif owner.backend == "omlx":
                    activity = omlx_activity_activity(owner, activity)
                    activity = omlx_prompt_activity(owner, activity)
                elif owner.backend == "uzu":
                    activity = uzu_prompt_activity(owner, activity)
                elif owner.backend == "whallm" and phase == "running" and owner.model.get("nativeWhallm"):
                    activity = whallm_telemetry.request_activity(owner, activity, self.whallm_telemetry_observations)

        with self.lock:
            return json.loads(json.dumps(self._current_activity_unlocked(target, activity)))

    def _current_activity_unlocked(
        self, target: _SessionActivityTarget, activity: dict[str, Any],
    ) -> dict[str, Any]:
        """Drop evidence from a replaced route at the same boundary that reads state."""
        if not self._activity_target_matches_unlocked(target):
            target = self._activity_target_unlocked()
            owner = target.owner
            session = owner is not None and owner.purpose == "session"
            activity = self._request_activity_fallback(
                "idle" if not session or target.phase == "idle" else
                "starting" if target.phase in {"preflight", "starting"} else "unavailable",
                "The model route changed during this update. Fresh activity will appear on the next update.",
                resident=session and target.phase == "running",
                lanes=session_request_lanes(owner) if session else 0,
            )
        owner = target.owner
        timeout_minutes = self.idle_timeout_minutes
        policy_set_at = self.idle_policy_set_at
        active = int(activity.get("activeCount") or 0)
        queued = int(activity.get("queuedCount") or 0)
        raw_idle = activity.get("idleSeconds")
        idle_seconds = (
            max(0.0, float(raw_idle))
            if isinstance(raw_idle, (int, float)) and not isinstance(raw_idle, bool)
            else None
        )
        enabled_elapsed = max(0.0, time.time() - policy_set_at)
        effective_idle = min(idle_seconds, enabled_elapsed) if idle_seconds is not None else None
        remaining = (
            max(0.0, timeout_minutes * 60 - effective_idle)
            if timeout_minutes and effective_idle is not None and not active and not queued
            else None
        )
        idle_eligible = bool(
            activity.get("coverage", {}).get("allLauncherSurfaces")
            and owner is not None and owner.backend != "lmstudio"
        )
        if timeout_minutes and idle_eligible:
            idle_detail = (
                f"Close the private launcher route after {timeout_minutes} minutes with no relayed request; "
                "the FreeToken server and model keep running. The countdown pauses while work is active or queued."
                if owner is not None and owner.backend == "freetoken"
                and owner.model.get("remote") is True else
                f"Auto-unload after {timeout_minutes} minutes with no relayed request. "
                "The countdown pauses while work is active or queued."
            )
        elif owner is not None and owner.backend == "lmstudio":
            idle_detail = (
                "Auto-unload is unavailable for this LM Studio route because its shared, "
                "unauthenticated loopback server may receive requests outside the relay."
            )
        else:
            idle_detail = "Keep the model loaded until you stop it."
        activity["idlePolicy"] = {
            "enabled": timeout_minutes > 0,
            "timeoutMinutes": timeout_minutes,
            "allowedMinutes": sorted(SESSION_IDLE_TIMEOUT_CHOICES),
            "remainingSeconds": round(remaining, 3) if remaining is not None else None,
            "eligible": idle_eligible,
            "detail": idle_detail,
        }
        return activity

    def register_session_surface(self, owner: LaunchPlan, plan: LaunchPlan) -> None:
        if (
            owner.purpose != "session" or not plan.secrets.get("clientApiKey")
            or not isinstance(plan.sampling_contract, dict)
            or not isinstance(plan.sampling_enforcement, dict)
        ):
            raise ValueError("The attached surface has no private relay contract.")
        self._session_proxy_api("POST", "/__launcher/surfaces", {
            "action": "register",
            "surface": {
                "id": plan.run_id,
                "client": plan.client,
                "key": plan.secrets["clientApiKey"],
                "samplingContract": copy.deepcopy(plan.sampling_contract),
                "samplingEnforcement": copy.deepcopy(plan.sampling_enforcement),
            },
        }, timeout=2.0)

    def unregister_session_surface(self, surface_id: str) -> None:
        try:
            self._session_proxy_api("POST", "/__launcher/surfaces", {
                "action": "unregister", "surfaceId": surface_id,
            }, timeout=2.0)
        except ValueError:
            # Detaching a local Chat still removes controller ownership if the
            # relay is already stopping; the whole relay will close shortly.
            pass

    def cancel_session_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            owner = self.plan
            if (
                owner is None or owner.purpose != "session"
                or self.state.get("phase") != "running"
                or str(payload.get("ownerRunId") or "") != owner.run_id
            ):
                raise ValueError("The active model route changed. Refresh Sessions and try again.")
        try:
            request_id = str(uuid.UUID(str(payload.get("requestId") or "")))
        except (ValueError, AttributeError) as error:
            raise ValueError("Choose an active or queued request to cancel.") from error
        self._session_proxy_api("POST", "/__launcher/cancel", {
            "requestId": request_id,
        }, timeout=2.0)
        return self.request_activity()

    def cancel_chat_generation(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Cancel queued/running work for one exact built-in Chat surface."""
        chat_plan = self._chat_plan_for_payload(payload)
        surface_id = chat_plan.run_id
        cancelled = 0
        # Stop can be pressed immediately after dispatch. Give the relay a
        # brief chance to register the request before a zero count is treated
        # as an already-settled turn.
        for attempt in range(5):
            result = self._session_proxy_api("POST", "/__launcher/surfaces", {
                "action": "cancel", "surfaceId": surface_id,
            }, timeout=2.0)
            cancelled = max(cancelled, int(result.get("cancelled") or 0))
            if cancelled or attempt == 4:
                break
            time.sleep(0.02)
        return {"surfaceId": surface_id, "cancelled": cancelled}

    def set_idle_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            owner = self.plan
            if (
                owner is None or owner.purpose != "session"
                or self.state.get("phase") != "running"
                or str(payload.get("ownerRunId") or "") != owner.run_id
            ):
                raise ValueError("The active model route changed. Refresh Sessions and try again.")
        value = payload.get("timeoutMinutes")
        if isinstance(value, bool):
            raise ValueError("Choose a supported idle timeout.")
        try:
            minutes = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError("Choose a supported idle timeout.") from error
        if minutes not in SESSION_IDLE_TIMEOUT_CHOICES:
            raise ValueError("Choose Off, 5, 15, 30, 60, or 120 minutes.")
        if minutes and owner.backend == "lmstudio":
            raise ValueError(
                "Idle auto-unload is disabled for LM Studio because its shared loopback server "
                "may have direct clients the launcher cannot observe."
            )
        with self.lock:
            if self.plan is not owner or self.state.get("phase") != "running":
                raise ValueError("The active model route changed. Refresh Sessions and try again.")
            self.idle_timeout_minutes = minutes
            self.idle_policy_set_at = time.time()
        if owner.backend == "freetoken" and owner.model.get("remote") is True:
            self.event(
                f"Idle auto-close set to {minutes} minutes; it will not stop the FreeToken server or model."
                if minutes else "Idle auto-close disabled; the connected route stays open until stopped."
            )
        else:
            self.event(
                f"Idle auto-unload set to {minutes} minutes."
                if minutes else "Idle auto-unload disabled; the model stays loaded until stopped."
            )
        return self.request_activity()

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            target = self._activity_target_unlocked()
        activity = self.request_activity(_target=target)
        with self.lock:
            snapshot = copy.deepcopy(self.state)
            snapshot["attachments"] = [
                attachment.public() for attachment in self.attachments.values()
            ]
            snapshot["agentConsoles"] = [
                console.public() for console in self.agent_consoles.values()
            ]
            snapshot["cache"] = self._cache_observatory_unlocked()
            snapshot["activity"] = self._current_activity_unlocked(target, activity)
            return json.loads(json.dumps(snapshot))

    def hub_snapshot(self) -> dict[str, Any]:
        """Describe only this launcher's owned route and handoff components."""
        with self.lock:
            target = self._activity_target_unlocked()
        activity = self.request_activity(_target=target)
        with self.lock:
            phase = str(self.state.get("phase") or "idle")
            plan = self.plan
            active = phase in {"preflight", "starting", "running", "stopping"}
            components: list[dict[str, Any]] = []
            attachments = list(self.attachments.values())
            consoles = {
                surface_id: console.public()
                for surface_id, console in self.agent_consoles.items()
            }
            if not attachments and plan is not None:
                # Keep diagnostics useful for tests and a controller restored
                # around an already-created plan, before start() seeds the
                # authoritative attachment registry.
                attachments = [SurfaceAttachment(
                    owner_run_id=plan.run_id,
                    plan=plan,
                    primary=True,
                    status=(
                        "ready" if plan.client == "chat" else
                        "running" if plan.agent_host == "console" else "handoff"
                    ) if phase == "running" else phase,
                    detail=(
                        "Built-in Chat is ready."
                        if plan.client == "chat" else
                        "Agent is running in Hub Console."
                        if plan.agent_host == "console" else "Terminal handoff opened."
                    ),
                    attached_at=self.started_at or datetime.now(timezone.utc).isoformat(),
                )]

            def process_component(kind: str, label: str, process: subprocess.Popen[str] | None) -> None:
                if process is None:
                    return
                running = process.poll() is None
                components.append({
                    "kind": kind, "label": label, "owned": True,
                    "running": running, "pid": process.pid if running else None,
                })

            if plan is not None:
                if plan.backend == "lmstudio":
                    components.append({
                        "kind": "engine", "label": "LM Studio shared model slot",
                        "owned": "model-only", "running": active,
                        "pid": None,
                    })
                else:
                    process_component("engine", f"{BACKEND_LABELS[plan.backend]} engine", self.process)
                process_component("loader", "Runtime loader", self.aux_process)
                process_component(
                    "relay" if plan.purpose == "session" else "guard",
                    "Private session request relay" if plan.purpose == "session" else "Codex response guard",
                    self.proxy_process,
                )
                for attachment in attachments:
                    public_attachment = attachment.public()
                    console = consoles.get(attachment.plan.run_id)
                    components.append({
                        "kind": "surface",
                        "label": (
                            "Built-in Chat"
                            if attachment.plan.client == "chat" else
                            f"{public_attachment['surface']} Hub Console"
                            if attachment.plan.agent_host == "console" else
                            f"{public_attachment['surface']} Terminal handoff"
                        ) + (" · primary" if attachment.primary else " · attached"),
                        "owned": attachment.plan.client == "chat" or attachment.plan.agent_host == "console",
                        "running": bool(
                            active and attachment.status != "unavailable"
                            and (console is None or console.get("state") == "running")
                        ),
                        "pid": console.get("pid") if console else None,
                        "attachmentId": attachment.plan.run_id,
                        "primary": attachment.primary,
                        "status": attachment.status,
                    })
            public_plan = plan.public() if plan is not None else None
            return {
                "phase": phase,
                "message": str(self.state.get("message") or "Ready"),
                "active": active,
                "activeSessionCount": int(bool(
                    active and plan is not None and plan.purpose == "session"
                )),
                "activeSurfaceCount": (
                    len(attachments)
                    if active and plan is not None and plan.purpose == "session" else 0
                ),
                "startedAt": self.started_at,
                "session": public_plan if plan is not None and plan.purpose == "session" else None,
                "internalRun": public_plan if plan is not None and plan.purpose != "session" else None,
                "components": components,
                "attachments": [
                    attachment.public() for attachment in attachments
                    if plan is not None and plan.purpose == "session"
                ],
                "agentConsoles": list(consoles.values()) if plan is not None and plan.purpose == "session" else [],
                "cache": self._cache_observatory_unlocked(),
                "activity": self._current_activity_unlocked(target, activity),
                "ownedProcessCount": sum(
                    1 for item in components if item.get("owned") is True and item.get("pid")
                ),
            }

    def _chat_plan_for_payload(self, payload: dict[str, Any]) -> LaunchPlan:
        """Resolve one browser-owned Chat surface without exposing its route secrets."""
        with self.lock:
            owner = self.plan
            if self.state.get("phase") != "running" or not owner:
                raise ValueError("The model is not ready for chat yet.")
            if owner.purpose != "session":
                raise ValueError("This internal model run is reserved for a launcher measurement.")
            if str(payload.get("runId") or "") != owner.run_id:
                raise ValueError("This chat belongs to an older run. Start a new chat with the active model.")
            attachment_id = str(payload.get("attachmentId") or owner.run_id)
            attachment = self.attachments.get(attachment_id)
            if attachment is None and attachment_id == owner.run_id and owner.client == "chat":
                # Supports a directly constructed manager in diagnostics and
                # preserves the original primary-Chat request contract.
                chat_plan = owner
            elif attachment is None:
                raise ValueError("This attached chat is no longer active. Open another chat from Sessions.")
            else:
                if attachment.owner_run_id != owner.run_id:
                    raise ValueError("This attached chat belongs to an older model route.")
                if attachment.status != "ready":
                    raise ValueError("This attached chat is not ready.")
                chat_plan = attachment.plan
            if chat_plan.client != "chat":
                raise ValueError("The selected work surface is not a built-in chat session.")
            return chat_plan

    def chat_request(self, payload: dict[str, Any]) -> urllib.request.Request:
        """Bind a browser chat turn to one exact surface on the active route."""
        with self.lock:
            chat_plan = self._chat_plan_for_payload(payload)
            request = build_chat_completion_request(chat_plan, payload)
            request._launcher_cache_context = {  # type: ignore[attr-defined]
                "ownerRunId": str(payload.get("runId") or ""),
                "attachmentId": str(payload.get("attachmentId") or chat_plan.run_id),
            }
            return request

    def save_chat_history(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Save visible transcript content with a route contract derived only from the live plan."""
        resume_contract: dict[str, Any] | None = None
        if payload.get("runId") not in (None, ""):
            chat_plan = self._chat_plan_for_payload(payload)
            resume_contract = _chat_resume_contract_for_plan(chat_plan)
        return save_chat_history(payload, resume_contract=resume_contract)

    def _chat_settings_snapshot_unlocked(self, plan: LaunchPlan) -> dict[str, Any]:
        owner = self.plan
        if owner is None:
            raise ValueError("The active Chat route is no longer available.")
        capability = plan.model.get("backends", {}).get(plan.backend, {})
        return {
            "version": 1,
            "runId": owner.run_id,
            "attachmentId": plan.run_id,
            "chat": copy.deepcopy(plan.chat),
            "contract": {
                "backend": plan.backend,
                "backendLabel": BACKEND_LABELS.get(plan.backend, plan.backend),
                "model": str(plan.model.get("name") or "Local model"),
                "context": plan.context,
                "output": plan.output,
                "reasoning": plan.reasoning,
                "customSampling": capability.get("customSampling") is not False,
                "samplingReason": str(capability.get("samplingReason") or ""),
            },
            "appliesTo": "next-request",
            "reloadsModel": False,
        }

    def chat_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return only the selected Chat surface's active request controls."""
        with self.lock:
            plan = self._chat_plan_for_payload(payload)
            return self._chat_settings_snapshot_unlocked(plan)

    def update_chat_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Atomically replace request-level Chat controls for future turns."""
        with self.lock:
            plan = self._chat_plan_for_payload(payload)
            updated = validated_chat_settings(
                plan.model, {"chat": payload.get("chat")}, "chat",
            )
            capability = plan.model.get("backends", {}).get(plan.backend, {})
            validate_chat_capability(capability, updated, "chat")
            sampling_contract = sampling_contract_from_settings(plan.model, updated)
            validate_sampling_capability(capability, sampling_contract)
            sampling_enforcement = sampling_route_enforcement(
                plan.backend, "chat", capability, sampling_contract,
            )
            assert sampling_enforcement is not None
            updated = chat_settings_from_sampling_contract(
                sampling_contract,
                system_prompt=str(updated.get("systemPrompt") or ""),
            )
            if (
                self.session_proxy_port and self.session_proxy_control_key
                and self.proxy_process is not None
                and self.proxy_process.poll() is None
            ):
                self._session_proxy_api("POST", "/__launcher/surfaces", {
                    "action": "register",
                    "surface": {
                        "id": plan.run_id,
                        "client": plan.client,
                        "key": plan.secrets.get("clientApiKey"),
                        "samplingContract": sampling_contract,
                        "samplingEnforcement": sampling_enforcement,
                    },
                }, timeout=2.0)
            plan.chat = updated
            plan.sampling_contract = sampling_contract
            plan.sampling_enforcement = sampling_enforcement
            if plan is self.plan:
                self.state["run"] = plan.public()
            result = self._chat_settings_snapshot_unlocked(plan)
        self.event(
            "Built-in Chat controls updated for the next request; the model route was not reloaded."
        )
        return result

    def chat_checkpoint(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Bind a visible turn journal entry to the same exact active Chat route."""
        chat_plan = self._chat_plan_for_payload(payload)
        scoped = copy.deepcopy(payload)
        scoped["metadata"] = {
            "model": str(chat_plan.model.get("name") or "Local model"),
            "backend": chat_plan.backend,
            "context": chat_plan.context,
            "output": chat_plan.output,
            "reasoning": chat_plan.reasoning,
            **({
                key: copy.deepcopy(payload["metadata"][key])
                for key in (
                    "branchParentId", "branchParentTitle", "branchPoint", "branchKind",
                ) if isinstance(payload.get("metadata"), dict) and key in payload["metadata"]
            }),
        }
        return save_chat_turn_checkpoint(
            scoped, resume_contract=_chat_resume_contract_for_plan(chat_plan),
        )

    def _validated_attachment_target(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate a surface without allocating a port or creating files."""
        with self.lock:
            owner = self.plan
            phase = str(self.state.get("phase") or "idle")
            if phase != "running" or owner is None or owner.purpose != "session":
                raise ValueError("Start a normal model session before attaching another work surface.")
            if str(payload.get("ownerRunId") or "") != owner.run_id:
                raise ValueError("The active model route changed. Refresh Sessions and try again.")
            if len(self.attachments) >= SURFACE_ATTACHMENT_MAX:
                raise ValueError(
                    f"This model route already has {SURFACE_ATTACHMENT_MAX} work surfaces. "
                    "End an attached Chat or stop the route before adding another."
                )
            cancel_event = self.cancel_event
            relay_running = bool(
                self.proxy_process is not None
                and self.proxy_process.poll() is None
                and self.session_proxy_port
                and self.session_proxy_control_key
            )
            owner_model = copy.deepcopy(owner.model)

        client = str(payload.get("client") or "")
        if not relay_running:
            raise ValueError(
                "The private shared-request relay is unavailable. Stop this route before opening another surface."
            )
        if client not in CLIENT_ADAPTERS:
            raise ValueError("Choose Pi, OpenCode, Codex, or Chat to attach.")
        client_adapter = CLIENT_ADAPTERS[client]
        if not client_adapter.built_in and not BINARIES.get(client_adapter.binary_key or ""):
            raise ValueError(f"{client} is not installed.")
        capability = owner_model.get("backends", {}).get(owner.backend, {})
        support = resolved_client_support(owner.backend, client, capability)
        if not support.get("supported"):
            raise ValueError(str(support.get("reason") or "This work surface is not compatible with the loaded engine."))
        reasoning_key = "codexReasoning" if client == "codex" else "agentReasoning"
        allowed_reasoning = list(capability.get(reasoning_key) or ["auto"])
        if owner.reasoning not in allowed_reasoning:
            choices = ", ".join("model default" if item == "auto" else item for item in allowed_reasoning)
            raise ValueError(
                f"The loaded {owner.reasoning} reasoning contract cannot be preserved for {client}; "
                f"this route allows {choices}."
            )
        if client == "codex" and owner.output < 1_024:
            raise ValueError("Codex local-model sessions need a response limit of at least 1,024 tokens.")

        raw_project = payload.get("project") or owner.project
        if not isinstance(raw_project, str) or "\x00" in raw_project:
            raise ValueError("Project folder does not exist.")
        project = str(Path(raw_project).expanduser().resolve())
        if not Path(project).is_dir():
            raise ValueError("Project folder does not exist.")
        chat = validated_chat_settings(owner_model, {"chat": payload.get("chat")}, client)
        validate_chat_capability(capability, chat, client)
        sampling_contract = validated_sampling_contract(
            owner_model, payload, client, chat,
        )
        assert sampling_contract is not None
        validate_sampling_capability(capability, sampling_contract)
        sampling_enforcement = sampling_route_enforcement(
            owner.backend, client, capability, sampling_contract,
        )
        assert sampling_enforcement is not None
        if client == "chat":
            chat = chat_settings_from_sampling_contract(
                sampling_contract,
                system_prompt=str(chat.get("systemPrompt") or ""),
            )
        if client == "chat":
            agent_host = "launcher"
        else:
            agent_host = str(payload.get("agentHost") or "terminal")
            if agent_host not in {"console", "terminal"}:
                raise ValueError("Choose Hub Console or Terminal for this agent.")
            _require_omp_console_support(client, agent_host)
        lanes = session_request_lanes(owner)
        return {
            "owner": owner,
            "cancelEvent": cancel_event,
            "client": client,
            "project": project,
            "chat": chat,
            "samplingContract": sampling_contract,
            "samplingEnforcement": sampling_enforcement,
            "agentHost": agent_host,
            "relayRunning": relay_running,
            "requestLanes": lanes,
        }

    def attachment_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Describe a zero-weight-reload surface attachment without side effects."""
        target = self._validated_attachment_target(payload)
        owner: LaunchPlan = target["owner"]
        client = str(target["client"])
        surface = CLIENT_LABELS[client]
        lanes = int(target["requestLanes"])
        agent_host = str(target["agentHost"])
        console = client != "chat" and agent_host == "console"
        queue_detail = (
            "The loaded engine has one request lane, so simultaneous surfaces queue instead of duplicating model memory."
            if lanes == 1 else
            f"The loaded LM Studio route has {lanes} request lanes; excess simultaneous requests queue."
        )
        return {
            "version": SURFACE_ATTACHMENT_VERSION,
            "ready": True,
            "ownerRunId": owner.run_id,
            "client": client,
            "surface": surface,
            "project": str(target["project"]),
            "contract": {
                "backend": owner.backend,
                "backendLabel": BACKEND_LABELS[owner.backend],
                "model": owner.model["name"],
                "context": owner.context,
                "output": owner.output,
                "reasoning": owner.reasoning,
                "modelPort": owner.port,
                "options": {
                    key: value for key, value in owner.options.items() if not key.startswith("_")
                },
            },
            "action": {
                "kind": "chat" if client == "chat" else ("hub-console" if console else "terminal-handoff"),
                "label": (
                    "Open attached Chat" if client == "chat" else
                    f"Open {surface} in Hub Console" if console else
                    f"Open {surface} in Terminal"
                ),
                "opensTerminal": client != "chat" and not console,
                "opensHubConsole": console,
                "usesSessionRelay": True,
                "loadsWeights": False,
                "startsEngine": False,
            },
            "detail": (
                f"{surface} will reuse the loaded {BACKEND_LABELS[owner.backend]} model and exact "
                f"{owner.context:,}-context / {owner.output:,}-response / {owner.reasoning}-reasoning contract. "
                + queue_detail
            ),
            "privacy": {
                "startsRuntime": False,
                "loadsWeights": False,
                "allocatesPort": False,
                "createsRunFiles": False,
                "opensTerminal": False,
                "opensHubConsole": False,
                "usesProjectData": False,
            },
        }

    @staticmethod
    def _warm_model_fingerprint(model: dict[str, Any], backend: str) -> str:
        capability = model.get("backends", {}).get(backend, {})
        fingerprint = str(capability.get("benchmarkModelFingerprint") or "")
        if fingerprint:
            return fingerprint
        identity = {
            "id": str(model.get("id") or ""),
            "artifact": str(model.get("artifact") or model.get("path") or ""),
            "size": int(model.get("size") or 0),
            "format": str(model.get("format") or ""),
            "architecture": str(model.get("architecture") or ""),
            "quantization": str(model.get("quantization") or ""),
        }
        return hashlib.sha256(json.dumps(
            identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")).hexdigest()

    @staticmethod
    def public_warm_route(plan: dict[str, Any]) -> dict[str, Any]:
        return {
            key: copy.deepcopy(value)
            for key, value in plan.items() if not key.startswith("_")
        }

    def warm_route_plan(
        self, payload: dict[str, Any], models: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Prove whether visible controls can reuse the exact resident engine."""
        request = validated_launch_profile_request(payload, models)
        requested_model = next(item for item in models if item.get("id") == request["modelId"])
        with self.lock:
            owner = self.plan
            phase = str(self.state.get("phase") or "idle")
            if owner is None or owner.purpose != "session" or phase != "running":
                return {
                    "version": WARM_ROUTE_VERSION,
                    "state": "no-active-route",
                    "ready": False,
                    "canAttach": False,
                    "ownerRunId": None,
                    "contractId": None,
                    "confirmation": None,
                    "engineResident": False,
                    "prefixReuseGuaranteed": False,
                    "differences": [],
                    "detail": "No normal launcher-owned model route is ready to reuse.",
                    "privacy": {
                        "planningStartsRuntime": False,
                        "planningLoadsWeights": False,
                        "planningAllocatesPort": False,
                        "planningCreatesRunFiles": False,
                        "planningOpensTerminal": False,
                        "usesProjectData": False,
                    },
                }
            owner_id = owner.run_id
            owner_backend = owner.backend
            owner_model = copy.deepcopy(owner.model)
            owner_context = owner.context
            owner_output = owner.output
            owner_reasoning = owner.reasoning
            owner_options_raw = {
                key: copy.deepcopy(value)
                for key, value in owner.options.items() if not key.startswith("_")
            }

        differences: list[dict[str, Any]] = []

        def difference(field: str, label: str, loaded: Any, requested: Any) -> None:
            differences.append({
                "field": field, "label": label,
                "loaded": copy.deepcopy(loaded), "requested": copy.deepcopy(requested),
            })

        if owner_backend != request["backend"]:
            difference(
                "backend", "Engine",
                BACKEND_LABELS.get(owner_backend, owner_backend),
                BACKEND_LABELS.get(str(request["backend"]), str(request["backend"])),
            )
        if str(owner_model.get("id") or "") != request["modelId"]:
            difference(
                "model", "Model",
                str(owner_model.get("name") or owner_model.get("id") or "Loaded model"),
                str(requested_model.get("name") or request["modelId"]),
            )
        elif owner_backend == request["backend"] and self._warm_model_fingerprint(
            owner_model, owner_backend,
        ) != self._warm_model_fingerprint(requested_model, owner_backend):
            difference("modelFingerprint", "Checkpoint files", "loaded revision", "current revision")
        if owner_context != request["context"]:
            difference("context", "Context", owner_context, request["context"])
        if owner_output != request["output"]:
            difference("output", "Response limit", owner_output, request["output"])
        if owner_reasoning != request["reasoning"]:
            difference("reasoning", "Reasoning", owner_reasoning, request["reasoning"])

        if owner_backend == request["backend"] and not any(
            item["field"] in {"model", "modelFingerprint"} for item in differences
        ):
            owner_capability = owner_model.get("backends", {}).get(owner_backend, {})
            try:
                owner_options = validated_profile_options(
                    owner_backend, owner_model, owner_capability, owner_options_raw,
                )
            except ValueError:
                owner_options = owner_options_raw
            if owner_options != request["options"]:
                option_keys = sorted(set(owner_options) | set(request["options"]))
                for key in option_keys:
                    if owner_options.get(key) != request["options"].get(key):
                        difference(
                            f"options.{key}", key,
                            owner_options.get(key), request["options"].get(key),
                        )

        attachment_request = {
            "ownerRunId": owner_id,
            "client": request["client"],
            "project": request["project"],
            "chat": copy.deepcopy(request.get("chat")),
            "generation": copy.deepcopy(request.get("generation")),
            "agentHost": request.get("agentHost", "launcher" if request["client"] == "chat" else "terminal"),
        }
        target: dict[str, Any] | None = None
        surface_error = ""
        if not differences:
            try:
                target = self._validated_attachment_target(attachment_request)
            except (LaunchCancelled, ValueError) as error:
                surface_error = str(error)

        can_attach = not differences and target is not None and not surface_error
        surface = CLIENT_LABELS.get(str(request["client"]), str(request["client"]))
        console = request["client"] != "chat" and request.get("agentHost") == "console"
        contract_value = {
            "version": WARM_ROUTE_VERSION,
            "ownerRunId": owner_id,
            "request": request,
            "loaded": {
                "backend": owner_backend,
                "modelId": str(owner_model.get("id") or ""),
                "modelFingerprint": self._warm_model_fingerprint(owner_model, owner_backend),
                "context": owner_context,
                "output": owner_output,
                "reasoning": owner_reasoning,
                "options": owner_options_raw,
            },
        }
        contract_id = hashlib.sha256(json.dumps(
            contract_value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")).hexdigest()[:24] if can_attach else None
        confirmation = f"warm:{contract_id}" if contract_id else None
        if can_attach:
            state = "exact"
            detail = (
                f"{surface} can use the resident {BACKEND_LABELS[owner_backend]} model with "
                "these exact engine, model, context, response, reasoning, and speed controls. "
                "No model weights reload; prefix reuse remains a per-turn runtime report."
            )
        elif surface_error:
            state = "surface-unavailable"
            detail = surface_error
        else:
            state = "route-mismatch"
            labels = ", ".join(str(item["label"]) for item in differences[:4])
            detail = (
                f"The loaded route differs in {labels or 'its engine contract'}. "
                "Stop it before loading the visible route."
            )
        return {
            "version": WARM_ROUTE_VERSION,
            "state": state,
            "ready": can_attach,
            "canAttach": can_attach,
            "ownerRunId": owner_id,
            "contractId": contract_id,
            "confirmation": confirmation,
            "engineResident": True,
            "prefixReuseGuaranteed": False,
            "surface": surface,
            "client": request["client"],
            "loadedRoute": {
                "backend": owner_backend,
                "backendLabel": BACKEND_LABELS[owner_backend],
                "model": str(owner_model.get("name") or owner_model.get("id") or "Loaded model"),
                "context": owner_context,
                "output": owner_output,
                "reasoning": owner_reasoning,
            },
            "requestedRoute": {
                "backend": request["backend"],
                "backendLabel": BACKEND_LABELS[request["backend"]],
                "model": str(requested_model.get("name") or request["modelId"]),
                "context": request["context"],
                "output": request["output"],
                "reasoning": request["reasoning"],
            },
            "differences": differences,
            "action": {
                "kind": "chat" if request["client"] == "chat" else ("hub-console" if console else "terminal-handoff"),
                "label": (
                    "Open warm chat" if request["client"] == "chat" else
                    f"Open {surface} in Hub Console" if console else f"Open {surface} in Terminal"
                ),
                "opensTerminal": request["client"] != "chat" and not console,
                "opensHubConsole": console,
                "loadsWeights": False,
                "startsEngine": False,
            } if can_attach else None,
            "detail": detail,
            "privacy": {
                "planningStartsRuntime": False,
                "planningLoadsWeights": False,
                "planningAllocatesPort": False,
                "planningCreatesRunFiles": False,
                "planningOpensTerminal": False,
                "planningOpensHubConsole": False,
                "usesProjectData": False,
            },
            "_attachmentRequest": attachment_request if can_attach else None,
        }

    def warm_attach(
        self, payload: dict[str, Any], models: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Revalidate and attach a visible exact-match route without another model load."""
        warm = self.warm_route_plan(payload, models)
        if warm.get("canAttach") is not True or not isinstance(warm.get("_attachmentRequest"), dict):
            raise ValueError(str(warm.get("detail") or "The resident route no longer matches."))
        expected = str(warm.get("confirmation") or "")
        supplied = str(payload.get("warmRouteConfirmation") or "")
        if not expected or not secrets.compare_digest(supplied, expected):
            raise ValueError("The warm-route contract changed. Recheck the visible settings and try again.")
        attachment = self.attach_surface(warm["_attachmentRequest"])
        return {
            "attachment": attachment,
            "warmRoute": self.public_warm_route(warm),
        }

    @staticmethod
    def _build_attachment_launch_plan(
        target: dict[str, Any], attachment_id: str,
        client_port: int, client_api_key: str,
    ) -> LaunchPlan:
        """Create only a per-surface overlay for an already-loaded engine."""
        owner: LaunchPlan = target["owner"]
        assert owner.run_dir
        plan = LaunchPlan(
            run_id=attachment_id,
            backend=owner.backend,
            client=str(target["client"]),
            model=copy.deepcopy(owner.model),
            project=str(target["project"]),
            context=owner.context,
            output=owner.output,
            reasoning=owner.reasoning,
            port=owner.port,
            mode=owner.mode,
            options=copy.deepcopy(owner.options),
            purpose="session",
            chat=copy.deepcopy(target["chat"]),
            sampling_contract=copy.deepcopy(target["samplingContract"]),
            sampling_enforcement=copy.deepcopy(target["samplingEnforcement"]),
            agent_host=str(target["agentHost"]),
            client_port=client_port,
            secrets={
                "apiKey": str(owner.secrets.get("apiKey") or "local"),
                "clientApiKey": client_api_key,
            },
            run_dir=owner.run_dir / "attachments" / attachment_id,
        )
        plan.run_dir.mkdir(parents=True, exist_ok=True)
        build_client_plan(plan)
        plan.warnings.append(
            "This work surface reuses the launcher-owned engine and private request relay; "
            "it does not start a runtime or load model weights."
        )
        return plan

    def attach_surface(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Attach Chat or hand off an agent while retaining one model allocation."""
        with self.surface_lock:
            target = self._validated_attachment_target(payload)
            owner: LaunchPlan = target["owner"]
            cancel_event: threading.Event = target["cancelEvent"]
            client = str(target["client"])
            attachment_id = str(uuid.uuid4())
            client_port = int(owner.client_port or 0)
            if not client_port:
                raise ValueError("The active session has no private request relay.")
            client_api_key = secrets.token_urlsafe(32)

            attachment_plan = self._build_attachment_launch_plan(
                target, attachment_id, client_port, client_api_key,
            )
            registered = False
            try:
                self.register_session_surface(owner, attachment_plan)
                registered = True
                if client == "codex":
                    # The resident model may have been launched through a
                    # Chat-Completions surface. Prove the upstream Responses
                    # route and reasoning contract before opening Terminal;
                    # normal traffic then uses this surface's private relay key.
                    self._verify_lmstudio_reasoning(attachment_plan)
                    self._verify_client_api(attachment_plan)

                attachment = SurfaceAttachment(
                    owner_run_id=owner.run_id,
                    plan=attachment_plan,
                    primary=False,
                    status=(
                        "ready" if client == "chat" else
                        "starting" if attachment_plan.agent_host == "console" else "handoff"
                    ),
                    detail=(
                        "Built-in Chat is ready on the existing model allocation and shared request relay."
                        if client == "chat" else (
                        "Opening a launcher-owned Hub Console on the shared request relay."
                        if attachment_plan.agent_host == "console" else
                        "Terminal handoff opened through the shared request relay; close that Terminal "
                        "to end the agent while leaving the model loaded."
                        )
                    ),
                )
                if client == "chat":
                    with self.lifecycle_lock:
                        with self.lock:
                            if (
                                self.plan is not owner
                                or self.cancel_event is not cancel_event
                                or cancel_event.is_set()
                                or self.state.get("phase") != "running"
                            ):
                                raise LaunchCancelled("The active model route changed before Chat could attach.")
                            self.attachments[attachment_id] = attachment
                else:
                    self._launch_client(
                        attachment_plan,
                        cancel_event,
                        owner_plan=owner,
                        attachment=attachment,
                    )
            except Exception:
                if registered:
                    self.unregister_session_surface(attachment_id)
                raise
            self.event(
                f"{attachment.public()['surface']} attached through the shared request relay without reloading weights."
            )
            return attachment.public()

    def detach_surface(self, payload: dict[str, Any]) -> dict[str, Any]:
        """End a launcher-owned secondary Chat without stopping the engine."""
        with self.surface_lock:
            attachment_id = str(payload.get("attachmentId") or "")
            owner_run_id = str(payload.get("ownerRunId") or "")
            with self.lifecycle_lock:
                with self.lock:
                    owner = self.plan
                    if (
                        owner is None or owner.purpose != "session"
                        or owner.run_id != owner_run_id
                        or self.state.get("phase") != "running"
                    ):
                        raise ValueError("The active model route changed. Refresh Sessions and try again.")
                    attachment = self.attachments.get(attachment_id)
                    if attachment is None or attachment.owner_run_id != owner.run_id:
                        raise ValueError("That attached work surface is no longer active.")
                    if attachment.primary:
                        raise ValueError("Stop the launcher-owned route to end its primary work surface.")
                    if attachment.plan.client != "chat":
                        if attachment.plan.agent_host == "console":
                            raise ValueError(
                                "Use Stop agent for this launcher-owned Hub Console; "
                                "the shared model will remain loaded."
                            )
                        raise ValueError(
                            "This agent belongs to its Terminal handoff. Close that Terminal; "
                            "the launcher will keep the shared model loaded."
                        )
                    public_attachment = attachment.public()
                    del self.attachments[attachment_id]
            self.unregister_session_surface(attachment_id)
            self.event("Attached Chat ended; the shared model remains loaded for other work surfaces.")
            return public_attachment

    def start(self, plan: LaunchPlan) -> None:
        with self.lock:
            if CONTROLLER_QUITTING.is_set():
                raise LaunchCancelled("LLM Launcher is quitting.")
            if (
                self.state["phase"] in {"preflight", "starting", "running", "stopping"}
                or (self.worker_thread and self.worker_thread.is_alive())
                or (self.monitor_thread and self.monitor_thread.is_alive())
                or (self.llamacpp_guard_thread and self.llamacpp_guard_thread.is_alive())
            ):
                raise ValueError("Another launcher run is active. Stop it first.")
            plan.secrets.pop("omlxAdminSessionCookie", None)
            self.plan = plan
            self.started_at = datetime.now(timezone.utc).isoformat()
            self.lm_loaded_id = None
            self.codex_proxy_port = None
            self.codex_proxy_key = None
            self.session_proxy_port = None
            self.session_proxy_control_key = None
            self.idle_timeout_minutes = 0
            self.idle_policy_set_at = time.time()
            self.attachments = {}
            self.agent_consoles = {}
            self.cache_observations = []
            self.llamacpp_safety_violation = None
            if plan.purpose == "session":
                self.attachments[plan.run_id] = SurfaceAttachment(
                    owner_run_id=plan.run_id,
                    plan=plan,
                    primary=True,
                    status="starting",
                    detail=(
                        "Opening the connected FreeToken route."
                        if plan.backend == "freetoken" and plan.model.get("remote") is True else
                        "Loading native FreeToken through MLX/Metal."
                        if plan.backend == "freetoken" else
                        "Loading the shared model route."
                    ),
                    attached_at=self.started_at,
                )
            self.cancel_event = threading.Event()
            self.cleanup_started = False
            self.cleanup_complete = threading.Event()
            self.state = {"phase": "preflight", "message": "Checking the launch plan…", "run": plan.public(), "events": []}
            # Record and start atomically with respect to Stop/another Start.
            # The worker's first lock acquisition simply waits for this block.
            thread = threading.Thread(target=self._worker, args=(plan, self.cancel_event), daemon=True)
            self.worker_thread = thread
            try:
                thread.start()
            except Exception:
                self.worker_thread = None
                self.cancel_event.set()
                self.cleanup_started = True
                self.cleanup_complete.set()
                self.plan = None
                self.started_at = None
                self.attachments = {}
                self.agent_consoles = {}
                self.state["phase"] = "failed"
                self.state["run"] = None
                self.event("The launch worker could not start. Try the launch again.", "error")
                dispose_plan_secrets(plan)
                raise

    @staticmethod
    def _check_cancelled(cancel_event: threading.Event) -> None:
        if cancel_event.is_set():
            raise LaunchCancelled("Launch cancelled.")

    @staticmethod
    def _terminate_process(process: subprocess.Popen[str] | None, timeout: float) -> None:
        if not process:
            return
        leader_running = process.poll() is None
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except OSError:
            return
        try:
            if leader_running:
                process.wait(timeout=timeout)
                os.killpg(process.pid, 0)
                raise subprocess.TimeoutExpired(process.args, timeout)
            else:
                # The session leader can exit before descendants. Give its
                # process group a brief graceful window, then close the group.
                time.sleep(min(timeout, 0.25))
                os.killpg(process.pid, 0)
                raise subprocess.TimeoutExpired(process.args, timeout)
        except (OSError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
            if leader_running:
                try:
                    process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    pass

    def _publish_owned_process(
        self,
        attribute: str,
        process: subprocess.Popen[str],
        plan: LaunchPlan,
        cancel_event: threading.Event,
    ) -> None:
        """Publish a child only while its exact run still owns the manager."""
        accepted = False
        with self.lifecycle_lock:
            with self.lock:
                if self.plan is plan and self.cancel_event is cancel_event and not cancel_event.is_set():
                    setattr(self, attribute, process)
                    accepted = True
        if not accepted:
            self._terminate_process(process, 5)
            raise LaunchCancelled("Launch cancelled.")

    def _clear_owned_process(self, attribute: str, process: subprocess.Popen[str]) -> None:
        with self.lifecycle_lock:
            if getattr(self, attribute) is process:
                setattr(self, attribute, None)

    def _worker(self, plan: LaunchPlan, cancel_event: threading.Event) -> None:
        assert plan.run_dir
        try:
            self._check_cancelled(cancel_event)
            self.event(
                "Opening a private bridge to the connected FreeToken server…"
                if plan.backend == "freetoken" and plan.model.get("remote") is True else
                "Opening a private bridge to the running Whallm model…"
                if plan.backend == "whallm" and plan.model.get("sharedServer") is True else
                "Starting native FreeToken on this Mac…"
                if plan.backend == "freetoken" else
                "Starting the model engine…"
            )
            with self.lock:
                self.state["phase"] = "starting"
            log_path = plan.run_dir / "engine.log"
            env = os.environ.copy()
            if plan.backend == "mtplx":
                # MTPLX operator experiments must be selected only by the
                # launcher-owned plan. Never inherit shell-level memory or
                # execution-lane overrides across the child boundary.
                for key in (
                    *MTPLX_LONG_CONTEXT_OPERATOR_ENV_KEYS,
                    "MTPLX_COMPILED_VERIFY_MAX_CONTEXT",
                    "MTPLX_COMPILED_VERIFY_GROWTH_RESERVE",
                    "MTPLX_NAX_FLASH_ROUTE",
                ):
                    env.pop(key, None)
            if plan.backend == "slotstream":
                env = slotstream_runtime.clean_environment(env)
                if slotstream_runtime.inspect_install(plan.runtime_binary or BINARIES.get("slotstream"), plan.model.get("path")) != plan.model.get("slotstream"):
                    raise ValueError("Slotstream changed after planning. Rescan before launching.")
            if plan.backend == "kolibri":
                env = kolibri_runtime.clean_environment(env)
            if plan.backend == "splash":
                env = splash_runtime.clean_environment(env)
                live_install = splash_runtime.inspect_install(plan.runtime_binary or BINARIES.get("splash"))
                if live_install is None or live_install.get("ready") is not True:
                    raise ValueError("Splash changed after planning. Rescan before launching.")
            env.update(plan.engine_env)
            if plan.backend in {"llamacpp", "uzu"} or plan.model.get("nativeWhallm"):
                env = _environment_without_dyld(env)
            # Reserve the agent-facing route before an expensive model load.
            # No client can reach it until its selected work surface opens
            # after the upstream API passes verification.
            delayed_ssd_proxy = bool(
                plan.purpose == "session" and plan.backend in SSD_STREAMING_BACKENDS
            )
            if plan.purpose == "session" and not delayed_ssd_proxy:
                self._start_session_proxy(plan, log_path, cancel_event)
            elif plan.client == "codex":
                self._start_codex_proxy(plan, log_path, cancel_event)
            llamacpp_identities: tuple[tuple[Any, ...], ...] | None = None
            uzu_identities: tuple[Any, ...] | None = None
            if plan.backend == "llamacpp":
                # This is deliberately after any proxy setup and immediately
                # before the process boundary: never rely only on scan/build
                # time provenance for an executable or an 80 GB artifact.
                llamacpp_identities = validate_llamacpp_launch_boundary(plan)
                env = _environment_without_dyld(env)
            elif plan.backend == "uzu":
                uzu_identities = validate_uzu_launch_boundary(plan)
                env = _environment_without_dyld(env)
            if plan.backend == "lmstudio":
                self._start_lmstudio(plan, log_path, env, cancel_event)
            else:
                # Popen duplicates this descriptor for the child. Closing the
                # controller's copy prevents one descriptor leaking per run.
                with open(log_path, "a", encoding="utf-8") as log_handle:
                    uzu_launch: UzuExecutableLaunch | None = None
                    process: subprocess.Popen[str] | None = None
                    if plan.backend == "llamacpp":
                        assert llamacpp_identities is not None
                        confirm_llamacpp_launch_identities(plan, llamacpp_identities)
                        env = _environment_without_dyld(env)
                    elif plan.backend == "uzu":
                        assert uzu_identities is not None
                        uzu_launch = prepare_uzu_executable_launch(plan, uzu_identities)
                        env = _environment_without_dyld(env)
                    argv = uzu_launch.argv if uzu_launch is not None else plan.engine_argv
                    popen_extra: dict[str, Any] = {}
                    if uzu_launch is not None and uzu_launch.pass_fds:
                        popen_extra["pass_fds"] = uzu_launch.pass_fds
                    try:
                        process = subprocess.Popen(
                            argv, cwd=plan.project, env=env, text=True,
                            stdout=log_handle, stderr=subprocess.STDOUT,
                            start_new_session=True, **popen_extra,
                        )
                        if uzu_launch is not None and not uzu_launch.executes_from_fd:
                            try:
                                _confirm_open_uzu_executable(uzu_launch.opened)
                            except ValueError:
                                # The child may have crossed the path boundary
                                # before the post-spawn check. Stop it before it
                                # can be published as the launcher-owned route.
                                self._terminate_process(process, 5)
                                raise
                    finally:
                        if uzu_launch is not None:
                            uzu_launch.close()
                    assert process is not None
                    self._publish_owned_process("process", process, plan, cancel_event)
                    if plan.backend == "llamacpp":
                        guard = threading.Thread(
                            target=self._guard_llamacpp_memory,
                            args=(plan, process, cancel_event), daemon=True,
                        )
                        self.llamacpp_guard_thread = guard
                        guard.start()
                    elif plan.backend == "uzu":
                        guard = threading.Thread(
                            target=self._guard_uzu_memory,
                            args=(plan, process, cancel_event), daemon=True,
                        )
                        self.llamacpp_guard_thread = guard
                        guard.start()
                    elif plan.backend == "slotstream":
                        guard = threading.Thread(
                            target=self._guard_owned_memory,
                            args=(plan, process, cancel_event, "Slotstream", int(plan.options["memoryGB"]) * 1_000_000_000 + 2 * 1024**3), daemon=True,
                        )
                        self.llamacpp_guard_thread = guard
                        guard.start()
                    elif plan.model.get("nativeWhallm"):
                        guard = threading.Thread(
                            target=self._guard_owned_memory,
                            args=(plan, process, cancel_event, "Whallm", whallm_runtime.MEMORY_BYTES), daemon=True,
                        )
                        self.llamacpp_guard_thread = guard
                        guard.start()
            self._check_cancelled(cancel_event)
            self._wait_ready(plan, cancel_event)
            self._check_cancelled(cancel_event)
            if delayed_ssd_proxy:
                # These servers advertise a runtime-owned model ID. Discover
                # it from their single-model API before freezing the relay.
                self._start_session_proxy(plan, log_path, cancel_event)
                self._check_cancelled(cancel_event)
            self._verify_lmstudio_reasoning(plan)
            self._verify_client_api(plan)
            self._check_cancelled(cancel_event)
            if plan.purpose == "benchmark":
                self.event("Benchmark engine is ready.")
            elif plan.purpose == "route-check":
                self.event(
                    "Connected FreeToken route is ready for protocol checks."
                    if plan.backend == "freetoken" and plan.model.get("remote") is True else
                    "Native FreeToken route is ready for protocol checks."
                    if plan.backend == "freetoken" else
                    "Temporary route is ready for protocol checks."
                )
            elif plan.purpose == "ane-tune":
                self.event("Private oMLX engine is ready for ANE tuning.")
            elif plan.client == "chat":
                self.event(
                    "Connected model route is ready. Preparing the built-in chat…"
                    if plan.backend == "freetoken" and plan.model.get("remote") is True else
                    "Whallm's shared model route is ready. Preparing the built-in chat…"
                    if plan.backend == "whallm" and plan.model.get("sharedServer") is True else
                    "Native FreeToken is ready. Preparing the built-in chat…"
                    if plan.backend == "freetoken" else
                    "Model is ready. Preparing the built-in chat…"
                )
            else:
                self.event(
                    "Connected model route is ready. Opening the coding agent in Hub Console…"
                    if plan.backend == "freetoken" and plan.agent_host == "console" else
                    "Connected model route is ready. Opening the coding agent in a background Terminal…"
                    if plan.backend == "freetoken" else
                    "Whallm's shared model route is ready. Opening the coding agent in Hub Console…"
                    if plan.backend == "whallm" and plan.model.get("sharedServer") is True and plan.agent_host == "console" else
                    "Whallm's shared model route is ready. Opening the coding agent in a background Terminal…"
                    if plan.backend == "whallm" and plan.model.get("sharedServer") is True else
                    "Model is ready. Opening the coding agent in Hub Console…"
                    if plan.agent_host == "console" else
                    "Model is ready. Opening the coding agent in a background Terminal…"
                )
                self._launch_client(plan, cancel_event)
            self._check_cancelled(cancel_event)
            with self.lock:
                self.state["phase"] = "running"
                primary = self.attachments.get(plan.run_id)
                if primary is not None:
                    if plan.client == "chat":
                        primary.status = "ready"
                        primary.detail = (
                            "Built-in Chat is ready on the connected FreeToken model."
                            if plan.backend == "freetoken" and plan.model.get("remote") is True else
                            "Built-in Chat is ready on Whallm's shared model."
                            if plan.backend == "whallm" and plan.model.get("sharedServer") is True else
                            "Built-in Chat is ready on launcher-owned native FreeToken."
                            if plan.backend == "freetoken" else
                            "Built-in Chat is ready on the loaded model."
                        )
                    elif plan.agent_host == "console":
                        console = self.agent_consoles.get(plan.run_id)
                        primary.status = console.state if console is not None else "failed"
                        primary.detail = console.detail if console is not None else "Hub Console did not start."
                    else:
                        primary.status = "handoff"
                        primary.detail = "Terminal handoff opened; the launcher continues to own the model route."
                monitor = threading.Thread(
                    target=self._monitor_run, args=(plan, cancel_event), daemon=True,
                )
                self.monitor_thread = monitor
                monitor.start()
            if plan.purpose == "benchmark":
                self.event("Benchmark engine is ready for controlled requests.")
            elif plan.purpose == "route-check":
                self.event("Route Check owns this temporary model until its synthetic probes finish.")
            elif plan.purpose == "ane-tune":
                self.event("ANE Tuner owns this private engine until its measurements finish.")
            elif plan.client == "chat":
                self.event("Chat is ready in the launcher.")
            elif plan.agent_host == "console":
                self.event("Running. The coding agent is ready in Hub Console.")
            else:
                self.event("Running. The Terminal was opened without taking focus.")
        except LaunchCancelled:
            self._stop_owned(plan)
        except Exception as error:  # noqa: BLE001
            with self.lock:
                if self.plan is plan and not cancel_event.is_set():
                    self.state["phase"] = "failed"
            if not cancel_event.is_set():
                self.event(str(error), "error")
            self._stop_owned(plan)
        finally:
            with self.lock:
                if self.worker_thread is threading.current_thread():
                    self.worker_thread = None

    def _run_owned_command(
        self,
        argv: list[str],
        plan: LaunchPlan,
        env: dict[str, str],
        log_handle: Any,
        cancel_event: threading.Event,
        timeout: float,
    ) -> int:
        process = subprocess.Popen(
            argv, cwd=plan.project, env=env, text=True,
            stdout=log_handle, stderr=subprocess.STDOUT, start_new_session=True,
        )
        deadline = time.time() + timeout
        try:
            self._publish_owned_process("aux_process", process, plan, cancel_event)
            while process.poll() is None:
                if cancel_event.wait(0.15):
                    raise LaunchCancelled("Launch cancelled.")
                if time.time() >= deadline:
                    raise subprocess.TimeoutExpired(argv, timeout)
            return int(process.returncode or 0)
        finally:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except OSError:
                        pass
            self._clear_owned_process("aux_process", process)

    def _start_lmstudio(self, plan: LaunchPlan, log_path: Path, env: dict[str, str], cancel_event: threading.Event) -> None:
        with open(log_path, "a", encoding="utf-8") as log_handle:
            if not plan.options.get("_sharedServerWasRunning"):
                returncode = self._run_owned_command(
                    [BINARIES["lms"], "server", "start", "--port", str(plan.port), "--bind", "127.0.0.1"],
                    plan, env, log_handle, cancel_event, 60,
                )
                if returncode != 0:
                    raise RuntimeError("LM Studio server did not start. Open the run log for details.")
            self._check_cancelled(cancel_event)
            # The identifier is unique to this run and known before the shared
            # server begins loading. Recording it now lets Stop issue an unload
            # even if the CLI is cancelled after dispatching the load request.
            with self.lifecycle_lock:
                with self.lock:
                    if self.plan is not plan or self.cancel_event is not cancel_event or cancel_event.is_set():
                        raise LaunchCancelled("Launch cancelled.")
                    self.lm_loaded_id = plan.model["servedId"]
            returncode = self._run_owned_command(plan.engine_argv, plan, env, log_handle, cancel_event, 900)
            if returncode != 0:
                log_handle.flush()
                detail = ""
                try:
                    with open(log_path, "rb") as failure_log:
                        failure_log.seek(max(0, log_path.stat().st_size - 16_384))
                        detail = failure_log.read(16_384).decode("utf-8", errors="replace")
                except OSError:
                    pass
                if "Model not found" in detail or "No model found that matches model key" in detail:
                    raise RuntimeError(
                        "LM Studio no longer recognises the selected model in its local catalog. "
                        "Open LM Studio once, then Rescan models and retry calibration."
                    )
                raise RuntimeError("LM Studio could not load the selected model. Open the run log for details.")

    def _wait_ready(self, plan: LaunchPlan, cancel_event: threading.Event) -> None:
        if plan.backend == "whallm" and plan.model.get("nativeWhallm"):
            self.event("Loading the full Qwen model from SSD…")
            whallm_runtime.wait_ready(
                plan.options["_whallmConfig"], plan.secrets["apiKey"], cancel_event,
                lambda: self.process is not None and self.process.poll() is None,
            )
            plan.model["servedId"] = WHALLM_MODEL_ID
            return
        deadline = time.time() + 900
        headers = {"Authorization": f"Bearer {plan.secrets.get('apiKey', 'local')}"}
        last_error = ""
        while time.time() < deadline:
            self._check_cancelled(cancel_event)
            if self.process and self.process.poll() is not None:
                raise RuntimeError(f"{plan.backend} exited during startup (code {self.process.returncode}).")
            try:
                request = urllib.request.Request(f"http://127.0.0.1:{plan.port}/v1/models", headers=headers)
                with urllib.request.urlopen(request, timeout=3) as response:
                    data = json.loads(response.read(2_000_000))
                ids = [str(item.get("id")) for item in data.get("data", []) if isinstance(item, dict)]
                if plan.backend in SSD_STREAMING_BACKENDS and plan.backend != "slotstream" and len(ids) == 1 and ids[0]:
                    plan.model["servedId"] = ids[0]
                    return
                if plan.model["servedId"] in ids:
                    if plan.backend == "slotstream":
                        slotstream_runtime.validate_served_catalog(data, plan.context, plan.options.get("kv", "off"))
                    if plan.backend == "kolibri":
                        plan.options["_kolibriMemoryPlan"] = kolibri_runtime.validate_served_catalog(data, plan.context, plan.options)
                    if plan.backend == "splash":
                        splash_runtime.validate_served_catalog(data, str(plan.model["servedId"]))
                    if plan.backend == "uzu":
                        self._verify_uzu_native_security(plan)
                    if plan.backend == "freetoken" and plan.model.get("nativeFreetoken") is True:
                        health_request = urllib.request.Request(
                            f"http://127.0.0.1:{plan.port}/health", headers=headers,
                        )
                        with urllib.request.urlopen(health_request, timeout=3) as response:
                            raw_health = response.read(FREETOKEN_NATIVE_INSPECTION_MAX_RESPONSE + 1)
                        if len(raw_health) > FREETOKEN_NATIVE_INSPECTION_MAX_RESPONSE:
                            raise RuntimeError("Native FreeToken health response is oversized.")
                        try:
                            health = json.loads(raw_health)
                        except (ValueError, UnicodeError) as error:
                            raise RuntimeError("Native FreeToken health response is invalid JSON.") from error
                        validate_live_native_freetoken(plan, health)
                    return
                last_error = "Server is up, but the selected model is not listed yet."
            except (OSError, ValueError, urllib.error.URLError) as error:
                last_error = str(error)
            cancel_event.wait(1.5)
        raise RuntimeError(f"Timed out waiting for the model. {last_error}".strip())

    @staticmethod
    def _verify_uzu_native_security(plan: LaunchPlan) -> None:
        """Prove the live raw listener consumed its key and rejects bypasses."""
        key_file = _uzu_api_key_file(plan)
        try:
            key_file.lstat()
        except FileNotFoundError:
            pass
        except OSError as error:
            raise RuntimeError("The Uzu one-use API-key file could not be rechecked.") from error
        else:
            raise RuntimeError(
                "The hardened Uzu server did not consume its one-use API-key file before readiness."
            )
        wrong_key = secrets.token_urlsafe(32)
        if secrets.compare_digest(wrong_key, str(plan.secrets.get("apiKey") or "")):
            wrong_key += "-wrong"
        for path in ("/models", "/v1/models"):
            probes = (
                urllib.request.Request(f"http://127.0.0.1:{plan.port}{path}"),
                urllib.request.Request(
                    f"http://127.0.0.1:{plan.port}{path}",
                    headers={"Authorization": f"Bearer {wrong_key}"},
                ),
            )
            for request in probes:
                try:
                    with urllib.request.urlopen(request, timeout=2) as response:
                        response.read(4_096)
                except urllib.error.HTTPError as error:
                    status = error.code
                    error.close()
                    if status == HTTPStatus.UNAUTHORIZED:
                        continue
                    raise RuntimeError(
                        "The hardened Uzu raw listener returned an unexpected auth status."
                    ) from error
                except (OSError, urllib.error.URLError) as error:
                    raise RuntimeError(
                        "The hardened Uzu raw-listener auth boundary could not be verified."
                    ) from error
                raise RuntimeError(
                    "The hardened Uzu raw listener accepted a request without its exact bearer key."
                )

    def _guard_llamacpp_memory(
        self, plan: LaunchPlan, process: subprocess.Popen[str],
        cancel_event: threading.Event,
    ) -> None:
        """Enforce the exact cap and owned-group ceiling from Popen through unload."""
        last_whallm_check = 0.0
        try:
            while not cancel_event.is_set() and process.poll() is None:
                wired = apple_iogpu_wired_limit_bytes()
                reason = ""
                if wired != LLAMACPP_PLE_MEMORY_CEILING_BYTES:
                    reason = "The 44 GiB Metal wired-memory limit changed; the llama.cpp route was stopped."
                else:
                    try:
                        pgid = os.getpgid(process.pid)
                    except (OSError, ProcessLookupError):
                        pgid = 0
                    group = darwin_process_group_physical_footprint(pgid)
                    current = group.get("processGroupPhysicalFootprintBytes")
                    peak = group.get("processGroupLifetimePeakPhysicalFootprintBytes")
                    if (
                        group.get("processGroupFootprintAvailable") is not True
                        or group.get("processGroupMemberCount") != 1
                        or not isinstance(current, int) or isinstance(current, bool)
                        or not isinstance(peak, int) or isinstance(peak, bool)
                    ):
                        reason = "The llama.cpp process-group memory proof became incomplete; the route was stopped."
                    elif max(current, peak) >= LLAMACPP_PLE_MEMORY_CEILING_BYTES:
                        reason = "The llama.cpp process group reached the strict 44 GiB ceiling and was stopped."
                now = time.monotonic()
                if not reason and now - last_whallm_check >= 1.0:
                    last_whallm_check = now
                    if whallm_qualification_conflict(timeout=0.25):
                        reason = (
                            "Whallm became active while the llama.cpp route was loaded; "
                            "the route was stopped before combined memory residency became unsafe."
                        )
                if not reason:
                    if cancel_event.wait(0.25):
                        return
                    continue
                with self.lock:
                    if self.plan is not plan or self.process is not process:
                        return
                    self.state["phase"] = "failed"
                    self.state["message"] = reason
                    self.state["events"] = (
                        self.state.get("events", [])
                        + [{"time": time.strftime("%H:%M:%S"), "level": "error", "message": reason}]
                    )[-80:]
                    self.llamacpp_safety_violation = reason
                cancel_event.set()
                self._stop_owned(plan)
                return
        finally:
            with self.lock:
                if self.llamacpp_guard_thread is threading.current_thread():
                    self.llamacpp_guard_thread = None

    def _guard_uzu_memory(
        self, plan: LaunchPlan, process: subprocess.Popen[str],
        cancel_event: threading.Event,
    ) -> None:
        self._guard_owned_memory(plan, process, cancel_event, "Uzu", UZU_PROCESS_MEMORY_CEILING_BYTES)

    def _guard_owned_memory(
        self, plan: LaunchPlan, process: subprocess.Popen[str],
        cancel_event: threading.Event, label: str, ceiling: int,
    ) -> None:
        """Keep the bounded native process and the protected macOS reserve intact."""
        missing_samples = 0
        missing_system_samples = 0
        low_system_samples = 0
        last_system_check = -math.inf

        def fail(reason: str) -> None:
            with self.lock:
                if self.plan is not plan or self.process is not process:
                    return
                self.state["phase"] = "failed"
                self.state["message"] = reason
                self.state["events"] = (
                    self.state.get("events", [])
                    + [{"time": time.strftime("%H:%M:%S"), "level": "error", "message": reason}]
                )[-80:]
                self.llamacpp_safety_violation = reason
            cancel_event.set()
            # Stop the allocating engine before waiting for agent/relay cleanup.
            self._terminate_process(process, 0.25)
            self._stop_owned(plan)

        try:
            while not cancel_event.is_set() and process.poll() is None:
                try:
                    pgid = os.getpgid(process.pid)
                except (OSError, ProcessLookupError):
                    pgid = 0
                group = darwin_process_group_physical_footprint(pgid)
                current = group.get("processGroupPhysicalFootprintBytes")
                peak = group.get("processGroupLifetimePeakPhysicalFootprintBytes")
                complete = bool(
                    group.get("processGroupFootprintAvailable") is True
                    and isinstance(current, int) and not isinstance(current, bool)
                    and isinstance(peak, int) and not isinstance(peak, bool)
                    and int(group.get("processGroupMemberCount") or 0) >= 1
                )
                reason = ""
                if complete:
                    missing_samples = 0
                    if max(int(current), int(peak)) >= ceiling:
                        reason = (
                            f"{label} reached the launcher's {ceiling / 1024**3:.0f} GiB "
                            "process-group safety ceiling and was stopped before macOS lost its reserve."
                        )
                else:
                    missing_samples += 1
                    if missing_samples >= 12:
                        reason = (
                            f"{label} process-group memory could not be verified continuously, so the route was stopped fail-closed."
                        )
                now = time.monotonic()
                if not reason and now - last_system_check >= 1.0:
                    last_system_check = now
                    memory = apple_memory_pressure_state()
                    total = memory.get("totalBytes")
                    headroom = darwin_memory.snapshot_reclaimable_bytes(memory)
                    if headroom is not None:
                        missing_system_samples = 0
                        reserve = max(
                            SESSION_OS_RESERVE_MIN_BYTES,
                            round(int(total) * SESSION_OS_RESERVE_FRACTION),
                        )
                        low_system_samples = low_system_samples + 1 if headroom < reserve else 0
                        if low_system_samples >= 2:
                            reason = (
                                "System-wide physical memory left less than the protected macOS "
                                f"reserve, so {label} was stopped before the computer became unresponsive."
                            )
                    else:
                        missing_system_samples += 1
                        low_system_samples = 0
                        if missing_system_samples >= 3:
                            reason = (
                                "System-wide physical memory could not be verified continuously, "
                                f"so {label} was stopped fail-closed."
                            )
                    if not reason and plan.model.get("nativeWhallm") and whallm_qualification_conflict(timeout=0.25):
                        reason = "A separate Whallm model became active; the launcher-owned copy was stopped to protect memory."
                if not reason:
                    if cancel_event.wait(0.25):
                        return
                    continue
                fail(reason)
                return
        except Exception:
            fail(f"{label}'s memory watchdog failed; its owned process was stopped to protect the macOS reserve.")
        finally:
            with self.lock:
                if self.llamacpp_guard_thread is threading.current_thread():
                    self.llamacpp_guard_thread = None

    def _monitor_run(self, plan: LaunchPlan, cancel_event: threading.Event) -> None:
        """Notice an unexpected engine/proxy/model loss and clean up once."""
        missing_responses = 0
        unreachable_since: float | None = None
        degraded_reported = False
        last_health_check = 0.0
        headers = {"Authorization": f"Bearer {plan.secrets.get('apiKey', 'local')}"}
        try:
            while not cancel_event.wait(0.25 if plan.backend == "llamacpp" else 3.0):
                reason = ""
                llama_safety_reason = False
                if plan.backend != "lmstudio" and self.process and self.process.poll() is not None:
                    reason = f"{plan.backend} exited unexpectedly (code {self.process.returncode})."
                elif self.proxy_process and self.proxy_process.poll() is not None:
                    reason = (
                        "The private shared-request relay exited unexpectedly."
                        if plan.purpose == "session" else
                        "The Codex compatibility guard exited unexpectedly."
                    )
                if (not reason and (plan.backend in {"uzu", "slotstream"} or plan.model.get("nativeWhallm"))
                        and self.process is not None
                        and (self.llamacpp_guard_thread is None or not self.llamacpp_guard_thread.is_alive())):
                    reason = "The owned memory watchdog stopped unexpectedly; the model was stopped to protect memory."
                    llama_safety_reason = True
                if not reason and plan.backend == "llamacpp" and self.process is not None:
                    wired = apple_iogpu_wired_limit_bytes()
                    if wired != LLAMACPP_PLE_MEMORY_CEILING_BYTES:
                        reason = "The 44 GiB Metal wired-memory limit changed; the llama.cpp route was stopped."
                    else:
                        try:
                            pgid = os.getpgid(self.process.pid)
                        except (OSError, ProcessLookupError):
                            pgid = 0
                        group = darwin_process_group_physical_footprint(pgid)
                        group_current = group.get("processGroupPhysicalFootprintBytes")
                        group_peak = group.get("processGroupLifetimePeakPhysicalFootprintBytes")
                        if (
                            group.get("processGroupFootprintAvailable") is not True
                            or group.get("processGroupMemberCount") != 1
                            or not isinstance(group_current, int) or isinstance(group_current, bool)
                            or not isinstance(group_peak, int) or isinstance(group_peak, bool)
                        ):
                            reason = "The llama.cpp process-group memory proof became incomplete; the route was stopped."
                        elif max(group_current, group_peak) >= LLAMACPP_PLE_MEMORY_CEILING_BYTES:
                            reason = "The llama.cpp process group reached the strict 44 GiB ceiling and was stopped."
                    llama_safety_reason = bool(reason)
                now_monotonic = time.monotonic()
                if (
                    not reason and plan.backend == "llamacpp"
                    and now_monotonic - last_health_check < 3.0
                ):
                    continue
                last_health_check = now_monotonic
                with self.lock:
                    check_idle = self.plan is plan and self.idle_timeout_minutes > 0
                if not reason and plan.purpose == "session" and check_idle:
                    # Auto-unload uses the relay's request coverage and idle clock.
                    # Native token counters are only needed by the visible Hub.
                    activity = self.request_activity(include_engine_telemetry=False)
                    idle_policy = activity.get("idlePolicy") or {}
                    if (
                        idle_policy.get("enabled") is True
                        and idle_policy.get("eligible") is True
                        and int(activity.get("activeCount") or 0) == 0
                        and int(activity.get("queuedCount") or 0) == 0
                        and isinstance(idle_policy.get("remainingSeconds"), (int, float))
                        and float(idle_policy["remainingSeconds"]) <= 0
                    ):
                        self.event(
                            "Idle timeout reached; closing the private FreeToken route. The remote server and model will keep running."
                            if plan.backend == "freetoken" and plan.model.get("remote") is True else
                            "Idle timeout reached; unloading the launcher-owned model route."
                        )
                        threading.Thread(target=self.stop, daemon=True).start()
                        return
                if reason:
                    pass
                elif plan.purpose == "ane-tune":
                    # The upstream tuner intentionally unloads and reloads its
                    # temporary engine. Process ownership is the health signal;
                    # a transiently absent model ID is expected here.
                    missing_responses = 0
                    unreachable_since = None
                else:
                    try:
                        request = urllib.request.Request(
                            f"http://127.0.0.1:{plan.port}/v1/models", headers=headers,
                        )
                        with urllib.request.urlopen(request, timeout=2) as response:
                            data = json.loads(response.read(2_000_000))
                        ids = [str(item.get("id")) for item in data.get("data", []) if isinstance(item, dict)]
                        if plan.model.get("servedId") not in ids:
                            missing_responses += 1
                            if missing_responses >= 3:
                                reason = "The model API confirmed that the selected model is no longer served."
                        else:
                            missing_responses = 0
                        unreachable_since = None
                        if degraded_reported:
                            self.event("Model API health checks recovered.")
                            degraded_reported = False
                    except (OSError, ValueError, urllib.error.URLError):
                        # A serial local runtime may not answer management
                        # routes during a long generation. Never kill a live
                        # model merely because a health request timed out.
                        missing_responses = 0
                        if unreachable_since is None:
                            unreachable_since = time.monotonic()
                        if not degraded_reported and time.monotonic() - unreachable_since >= 120:
                            self.event(
                                "Model API health checks are delayed, but the owned process is still running.",
                                "warning",
                            )
                            degraded_reported = True
                if not reason:
                    continue
                with self.lock:
                    if self.plan is not plan or self.state.get("phase") != "running" or cancel_event.is_set():
                        return
                    self.state["phase"] = "failed"
                    self.state["message"] = reason
                    self.state["events"] = (
                        self.state.get("events", [])
                        + [{"time": time.strftime("%H:%M:%S"), "level": "error", "message": reason}]
                    )[-80:]
                    if llama_safety_reason:
                        self.llamacpp_safety_violation = reason
                cancel_event.set()
                if llama_safety_reason:
                    self._terminate_process(self.process, 0.25)
                self._stop_owned(plan)
                return
        finally:
            with self.lock:
                if self.monitor_thread is threading.current_thread():
                    self.monitor_thread = None

    def _launch_client(
        self,
        plan: LaunchPlan,
        cancel_event: threading.Event,
        owner_plan: LaunchPlan | None = None,
        attachment: SurfaceAttachment | None = None,
    ) -> None:
        if plan.agent_host == "console":
            self._launch_agent_console(
                plan, cancel_event, owner_plan=owner_plan, attachment=attachment,
            )
            return
        self._launch_terminal_client(
            plan, cancel_event, owner_plan=owner_plan, attachment=attachment,
        )

    def _launch_terminal_client(
        self,
        plan: LaunchPlan,
        cancel_event: threading.Event,
        owner_plan: LaunchPlan | None = None,
        attachment: SurfaceAttachment | None = None,
    ) -> None:
        assert plan.run_dir
        if CONTROLLER_QUITTING.is_set():
            raise LaunchCancelled("LLM Launcher is quitting.")
        owner = owner_plan or plan
        client_plan = {
            "cwd": plan.project,
            "argv": plan.client_argv,
            "env": plan.client_env,
            "clientName": plan.client,
            "allowedExecutable": plan.client_argv[0],
        }
        plan_file = plan.run_dir / "client-plan.json"
        atomic_json(plan_file, client_plan)
        script = plan.run_dir / "Open Coding Agent.command"
        script.write_text(
            "#!/bin/zsh\nexec /usr/bin/python3 " + shlex.quote(str(APP_DIR / "client_runner.py")) + " " + shlex.quote(str(plan_file)) + "\n",
            encoding="utf-8",
        )
        script.chmod(0o700)
        # Linearise the final user-visible launch with Stop. If Stop commits
        # cancellation first, no Terminal opens; if this commits first, the
        # Terminal was opened before the Stop request took ownership.
        with self.lifecycle_lock:
            with self.lock:
                if (CONTROLLER_QUITTING.is_set() or self.plan is not owner
                        or self.cancel_event is not cancel_event or cancel_event.is_set()):
                    raise LaunchCancelled("Launch cancelled.")
            subprocess.run(["/usr/bin/open", "-g", "-a", "Terminal", str(script)], timeout=15, check=True)
            if attachment is not None:
                with self.lock:
                    if self.plan is not owner or self.cancel_event is not cancel_event or cancel_event.is_set():
                        raise LaunchCancelled("Launch cancelled.")
                    self.attachments[attachment.plan.run_id] = attachment

    @staticmethod
    def _set_agent_console_size(fd: int, cols: int, rows: int) -> None:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    @staticmethod
    def _close_agent_console_fd(console: AgentConsole) -> None:
        with console.lock:
            fd = console.master_fd
            console.master_fd = -1
            if console.transport is not None:
                console.transport.close()
                return
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass

    @staticmethod
    def _agent_console_transport(console: AgentConsole) -> ConsoleTransport:
        with console.lock:
            if console.master_fd < 0:
                raise ValueError("That agent console has ended.")
            if console.transport is None:
                console.transport = ConsoleTransport(console.master_fd)
            return console.transport

    def _launch_agent_console(
        self,
        plan: LaunchPlan,
        cancel_event: threading.Event,
        owner_plan: LaunchPlan | None = None,
        attachment: SurfaceAttachment | None = None,
    ) -> AgentConsole:
        owner = owner_plan or plan
        if plan.client not in {"pi", "omp", "opencode", "codex"} or not plan.client_argv:
            raise ValueError("Hub Console can run only Pi, oh-my-pi, OpenCode, or Codex.")
        executable_path = plan.client_argv[0]
        expected_executable = selected_pi_binary(plan) if plan.client == "pi" else BINARIES.get(plan.client)
        if (
            not isinstance(executable_path, str) or not os.path.isabs(executable_path)
            or not os.access(executable_path, os.X_OK)
            or executable_path != expected_executable
        ):
            raise ValueError("The selected agent executable changed before Hub Console opened.")
        _require_omp_console_support(plan.client, plan.agent_host)
        if not Path(plan.project).is_dir():
            raise ValueError("The project folder disappeared before Hub Console opened.")

        protocol = (
            f"{plan.client}-rpc"
            if plan.client in {"pi", "omp"} and any(
                plan.client_argv[index:index + 2] == ["--mode", "rpc"]
                for index in range(len(plan.client_argv) - 1)
            ) else "terminal"
        )
        cols, rows = 100, 30
        master_fd, slave_fd = pty.openpty()
        process: subprocess.Popen[Any] | None = None
        try:
            self._set_agent_console_size(slave_fd, cols, rows)
            if protocol in STRUCTURED_AGENT_PROTOCOLS:
                # RPC is a byte stream, not interactive terminal input. Canonical
                # mode silently truncates long JSON lines (notably on macOS).
                tty.setraw(slave_fd, termios.TCSANOW)
            env = os.environ.copy()
            env.update(plan.client_env)
            env.update({
                "TERM": "xterm-256color",
                "COLORTERM": "truecolor",
                "LLM_LAUNCHER_AGENT_HOST": "console",
            })
            process = subprocess.Popen(
                plan.client_argv,
                cwd=plan.project,
                env=env,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=subprocess.PIPE if protocol == "omp-rpc" else slave_fd,
                start_new_session=True,
                close_fds=True,
            )
        except Exception:
            try:
                os.close(master_fd)
            except OSError:
                pass
            raise
        finally:
            try:
                os.close(slave_fd)
            except OSError:
                pass

        console = AgentConsole(
            owner_run_id=owner.run_id,
            plan=plan,
            process=process,
            master_fd=master_fd,
            cols=cols,
            rows=rows,
            protocol=protocol,
            detail="Connecting to oh-my-pi Hub Console…" if protocol == "omp-rpc" else "Agent is running in Hub Console.",
            omp_adapter=omp_protocol.Adapter() if protocol == "omp-rpc" else None,
            rpc_queue_directory=STATE_DIR / ("omp-queues" if protocol == "omp-rpc" else "pi-queues") if protocol in STRUCTURED_AGENT_PROTOCOLS else None,
        )
        accepted = False
        with self.lifecycle_lock:
            with self.lock:
                if (
                    self.plan is owner
                    and self.cancel_event is cancel_event
                    and not cancel_event.is_set()
                    and self.state.get("phase") in {"starting", "running"}
                ):
                    current = self.agent_consoles.get(plan.run_id)
                    if current is None or current.process.poll() is not None:
                        self.agent_consoles[plan.run_id] = console
                        target_attachment = attachment or self.attachments.get(plan.run_id)
                        if target_attachment is not None:
                            target_attachment.status = "running"
                            target_attachment.detail = (
                                "Agent is running in the launcher-owned Hub Console. "
                                "Stopping it leaves the shared model loaded."
                            )
                            self.attachments[plan.run_id] = target_attachment
                        accepted = True
        if not accepted:
            self._terminate_process(process, 3)
            self._close_agent_console_fd(console)
            raise LaunchCancelled("The active model route changed before Hub Console opened.")
        reader = threading.Thread(
            target=self._read_agent_console, args=(console,), daemon=True,
            name=f"agent-console-{plan.run_id[:8]}",
        )
        reader.start()
        if protocol == "omp-rpc":
            threading.Thread(target=self._read_agent_console_diagnostics,
                args=(console,), daemon=True, name=f"agent-diagnostics-{plan.run_id[:8]}").start()
        if protocol in STRUCTURED_AGENT_PROTOCOLS:
            console.append_timeline(
                "notice",
                "Stable transcript ready. Thinking, responses, tools, and queued messages stay visible.",
                title=f"{console.agent_label} Hub", item_id=f"{plan.client}:hub", operation="replace",
            )
            console.append(
                pi_rpc_heading(f"{console.agent_label.upper()} HUB", "38;5;75")
                + b"Stable transcript ready. Thinking, responses, tools, and queued messages stay visible.\r\n"
            )
            if protocol == "pi-rpc":
                self._initialize_agent_rpc(console)
        return console

    def _initialize_agent_rpc(self, console: AgentConsole) -> None:
        for command_id, command_type in (("launcher-history", "get_entries"),
                ("launcher-state", "get_state"), ("launcher-commands", "get_commands")):
            self._write_pi_rpc_command(console, {"id": command_id, "type": command_type})

    def _read_agent_console_diagnostics(self, console: AgentConsole) -> None:
        """Drain native stderr separately so diagnostics cannot corrupt RPC frames."""
        pipe = console.process.stderr
        if pipe is None:
            return
        try:
            while True:
                value = pipe.read(4_096)
                if not value:
                    return
                text = safe_agent_transcript_text(value.decode("utf-8", errors="replace"), 4_096)
                console.append_timeline("notice", text, title=f"{console.agent_label} diagnostics")
        finally:
            pipe.close()

    def _fail_omp_console_protocol(self, console: AgentConsole, error: Any) -> None:
        """Keep partial output and queued input when native framing loses proof."""
        message = safe_agent_ui_text(error, 2_000) or "oh-my-pi sent an incompatible RPC event."
        with console.lock:
            if console.rpc_failure:
                return
            if console.omp_adapter:
                console.omp_adapter.invalidate()
            console.rpc_failure = message
            console.rpc_queue_advance_allowed = False
            console.rpc_queue_paused = bool(console.rpc_follow_up_queue)
            console.append_timeline("error", message, title="oh-my-pi connection failed")
        # This console owns only the coding agent. Its model server remains loaded.
        self._terminate_process(console.process, 3)
        self._close_agent_console_fd(console)

    def _consume_pi_rpc_line(self, console: AgentConsole, line: bytes) -> None:
        """Decode the explicit native dialect before shared transcript rendering."""
        line = line.rstrip(b"\r")
        if not line:
            return
        if console.omp_adapter is not None:
            try:
                with console.lock:
                    result = console.omp_adapter.receive_line(line + b"\n")
                    for command in result.commands:
                        self._write_pi_rpc_command(console, command)
                    if any(command.get("type") == "negotiate_protocol" for command in result.commands):
                        self._initialize_agent_rpc(console)
                        self._write_pi_rpc_command(console, {
                            "id": "launcher-event-filter", "type": "set_event_filter",
                            "events": None, "messageUpdates": "delta",
                        })
                    if console.omp_adapter.can_input and not console.rpc_failure:
                        console.detail = "Agent is running in Hub Console."
                for event in result.events:
                    self._consume_agent_rpc_event(console, event)
            except (ValueError, UnicodeError) as error:
                self._fail_omp_console_protocol(console, error)
            return
        try:
            event = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            unsafe_line = line.decode("utf-8", errors="replace")
            console.append_timeline(
                "error", unsafe_line, title="Invalid Pi event",
                item_id=f"pi:invalid-event:{console.rpc_timeline_revision + 1}",
                operation="replace",
            )
            console.append(
                pi_rpc_heading("PI NOTICE", "38;5;214")
                + safe_agent_transcript_text(unsafe_line, 4_000).encode("utf-8")
            )
            return
        self._consume_agent_rpc_event(console, event)

    def _consume_agent_rpc_event(self, console: AgentConsole, event: Any) -> None:
        if not isinstance(event, dict):
            return
        with console.lock:
            control = str(event.get("type") or "")
            if control == "launcher_command_output":
                console.append_timeline("notice", event.get("text"), title=event.get("title") or "Command output")
                return
            if control in {"launcher_prompt_result", "launcher_local_prompt_complete"}:
                if not console.rpc_prompt_id or event.get("id") != console.rpc_prompt_id:
                    return
                console.rpc_prompt_acknowledged = True
                if control == "launcher_prompt_result":
                    console.rpc_prompt_result_status = str(event.get("status") or "")
                    if console.rpc_prompt_result_status in {"error", "aborted"}:
                        console.rpc_queue_advance_allowed = False
                        console.rpc_queue_paused = bool(console.rpc_follow_up_queue)
                        if event.get("error"):
                            error = event["error"]
                            console.append_timeline("error", error.get("message") if isinstance(error, dict) else error, title="oh-my-pi turn failed")
                    return
                pi_rpc_accept_queued_prompt(console)
                console.rpc_local_command = True
                console.rpc_queue_advance_allowed = True
                if event.get("sessionSettled") is not True:
                    return
                event = {"type": "agent_settled"}
            command_name = console.rpc_command_ids.pop(str(event.get("id") or ""), None) if event.get("type") == "response" else None
            if command_name is not None:
                if event.get("success") is False:
                    console.append_timeline("error", event.get("error") or "Command failed", title=f"/{command_name}")
                console.rpc_interactions.clear()
                console.rpc_statuses.pop("launcher.customUI", None)
                if console.rpc_statuses.pop("launcher.historyChanged", None) is not None:
                    console.rpc_history_loaded = False
                    console.rpc_timeline_items.clear()
                    console.rpc_timeline_item_text_bytes = 0
                    console.rpc_timeline_events.clear()
                    console.rpc_timeline_seen_message_ids.clear()
                    console.rpc_timeline_live_fingerprints.clear()
                    console.rpc_timeline_text_bytes = 0
                    console.rpc_timeline_revision += 1  # Invalidate browser history even when the new session is empty.
                    self._write_pi_rpc_command(console, {"id": "launcher-history", "type": "get_entries"})
                self._write_pi_rpc_command(console, {"id": "launcher-commands", "type": "get_commands"})
                return
            settle_revision = console.rpc_settle_revision
            rendered = pi_rpc_event_output(console, event)
            turn_settled = console.rpc_settle_revision != settle_revision
        console.append(rendered)
        if not turn_settled:
            return
        with console.lock:
            if console.rpc_queue_paused:
                console.rpc_pending_messages = (
                    len(console.rpc_follow_up_queue)
                    + console.rpc_external_pending_messages
                )
                return
            next_message = (
                console.rpc_follow_up_queue[0]
                if console.rpc_follow_up_queue else None
            )
            if next_message is not None:
                prompt_id = f"launcher-prompt-{secrets.token_hex(8)}"
                console.rpc_prompt_inflight = True
                console.rpc_streaming = True
                console.rpc_prompt_id = prompt_id
                console.rpc_prompt_acknowledged = False
                console.rpc_queued_prompt_message = next_message
                console.rpc_queue_paused = False
                console.rpc_queue_advance_allowed = False
        if next_message is None:
            return
        pi_rpc_record_queue(
            console,
            f"Starting a queued message; {console.rpc_pending_messages} message"
            f"{'s' if console.rpc_pending_messages != 1 else ''} retained until Pi accepts it.",
            title="Starting queued message",
        )
        console.append(pi_rpc_heading("STARTING QUEUED MESSAGE", "38;5;214"))
        try:
            self._write_pi_rpc_command(console, {
                "id": prompt_id, "type": "prompt", "message": next_message,
                "streamingBehavior": "followUp",
            })
            with console.lock:
                # Keep the head queued until Pi explicitly accepts the prompt.
                # A successful OS write alone cannot prove that Pi parsed it.
                console.rpc_pending_messages = (
                    len(console.rpc_follow_up_queue)
                    + console.rpc_external_pending_messages
                )
        except ValueError as error:
            with console.lock:
                if console.rpc_prompt_id == prompt_id:
                    console.rpc_prompt_inflight = False
                    console.rpc_streaming = False
                    console.rpc_prompt_id = ""
                    console.rpc_prompt_acknowledged = False
                    console.rpc_queued_prompt_message = ""
                console.rpc_queue_advance_allowed = False
                console.rpc_queue_paused = bool(console.rpc_follow_up_queue)
                console.rpc_pending_messages = (
                    len(console.rpc_follow_up_queue)
                    + console.rpc_external_pending_messages
                )
                console.append_timeline(
                    "error", error, title=f"{console.agent_label} input failed",
                    item_id=f"live:{console.rpc_timeline_turn}:queue-write-error",
                    operation="replace",
                )
                if console.rpc_queue_paused:
                    pi_rpc_record_queue(
                        console,
                        "The queued message was not sent and remains available to retry.",
                        title="Queue paused",
                    )
            console.append(
                pi_rpc_heading(f"{console.agent_label.upper()} ERROR", "38;5;203")
                + safe_agent_transcript_text(error, 2_000).encode("utf-8")
                + (
                    pi_rpc_heading("QUEUE PAUSED", "38;5;214")
                    + b"The queued message was not sent and remains available to retry."
                    if console.rpc_queue_paused else b""
                )
            )

    def _record_oversize_pi_rpc_line(self, console: AgentConsole) -> None:
        """Report and forget one JSONL record that crossed the hard input cap."""
        if console.omp_adapter is not None:
            self._fail_omp_console_protocol(console, "oh-my-pi exceeded its negotiated RPC frame limit. Partial output was kept.")
            return
        message = (
            "Pi sent an RPC event larger than the local safety limit. "
            "The event was discarded and reading resumes at the next JSON line."
        )
        console.append_timeline(
            "error", message, title="Oversized Pi event",
            item_id=f"pi:oversized-event:{console.rpc_timeline_revision + 1}",
            operation="replace",
        )
        console.append(
            pi_rpc_heading("PI NOTICE", "38;5;214")
            + message.encode("utf-8")
        )

    def _read_agent_console(self, console: AgentConsole) -> None:
        leader_group_cleaned = False
        try:
            with console.lock:
                if console.master_fd < 0:
                    return
                transport = self._agent_console_transport(console)
            while True:
                try:
                    value = transport.read(idle_timeout=0.2)
                except OSError:
                    break
                if value is None:
                    if console.process.poll() is not None:
                        # Drain all ready output before declaring EOF. An
                        # inherited PTY/stderr held by a surviving child must
                        # not leave an exited agent looking permanently live.
                        if not leader_group_cleaned:
                            self._terminate_process(console.process, 3)
                            leader_group_cleaned = True
                        break
                    continue
                if not value:
                    break
                if console.process.poll() is not None and not leader_group_cleaned:
                    # A descendant can keep output permanently readable. Stop
                    # the retained group once its leader exits, then keep
                    # draining buffered output through normal EOF handling.
                    self._terminate_process(console.process, 3)
                    leader_group_cleaned = True
                if not console.structured:
                    console.append(value)
                    continue
                with console.lock:
                    pending = value
                    records: list[bytes | None] = []
                    while pending:
                        if console.rpc_discarding_oversize_line:
                            newline = pending.find(b"\n")
                            if newline < 0:
                                break
                            pending = pending[newline + 1:]
                            console.rpc_discarding_oversize_line = False
                            continue
                        newline = pending.find(b"\n")
                        if newline < 0:
                            if (
                                len(console.rpc_line_buffer) + len(pending)
                                > (console.omp_adapter.physical_line_limit - 1 if console.omp_adapter else pi_rpc_line_limit(bytes(console.rpc_line_buffer[:512]) + pending[:512]))
                            ):
                                console.rpc_line_buffer.clear()
                                console.rpc_discarding_oversize_line = True
                                records.append(None)
                            else:
                                console.rpc_line_buffer.extend(pending)
                            break
                        segment = pending[:newline]
                        pending = pending[newline + 1:]
                        if (
                            len(console.rpc_line_buffer) + len(segment)
                            > (console.omp_adapter.physical_line_limit - 1 if console.omp_adapter else pi_rpc_line_limit(bytes(console.rpc_line_buffer[:512]) + segment[:512]))
                        ):
                            console.rpc_line_buffer.clear()
                            records.append(None)
                            continue
                        console.rpc_line_buffer.extend(segment)
                        records.append(bytes(console.rpc_line_buffer))
                        console.rpc_line_buffer.clear()
                for record in records:
                    if record is None:
                        self._record_oversize_pi_rpc_line(console)
                    else:
                        self._consume_pi_rpc_line(console, record)
        finally:
            if console.structured:
                with console.lock:
                    final_line = bytes(console.rpc_line_buffer)
                    console.rpc_line_buffer.clear()
                    console.rpc_discarding_oversize_line = False
                if final_line:
                    if console.omp_adapter:
                        self._fail_omp_console_protocol(console, "oh-my-pi ended inside an RPC frame. Partial output was kept.")
                    else:
                        self._consume_pi_rpc_line(console, final_line)
                if console.omp_adapter and not console.rpc_failure:
                    try:
                        console.omp_adapter.decoder.finish()
                    except ValueError as error:
                        self._fail_omp_console_protocol(console, error)
            try:
                exit_code = console.process.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                exit_code = console.process.poll()
            if (not leader_group_cleaned and console.state != "stopping"
                    and not console.rpc_failure):
                # EOF can race leader exit, a child may retain only stderr, or
                # the leader may close its stream and hang. After bounded drain
                # and wait, finalize only this agent's retained group as well.
                self._terminate_process(console.process, 3)
                leader_group_cleaned = True
                if exit_code is None:
                    exit_code = console.process.poll()
            self._close_agent_console_fd(console)
            unexpected_rpc_eof = False
            unexpected_rpc_output = b""
            with console.lock:
                if console.structured and console.state != "stopping":
                    unexpected_rpc_eof = bool(
                        console.rpc_streaming or console.rpc_prompt_inflight
                    )
                    if unexpected_rpc_eof:
                        unexpected_rpc_output = pi_rpc_unexpected_eof_output(console)
                console.rpc_streaming = False
                console.rpc_prompt_inflight = False
                console.rpc_prompt_id = ""
                console.rpc_prompt_acknowledged = False
                console.rpc_queued_prompt_message = ""
                console.rpc_interactions.clear()
                console.exit_code = int(exit_code) if exit_code is not None else None
                console.ended_at = datetime.now(timezone.utc).isoformat()
                if console.rpc_failure:
                    console.state = "failed"
                    console.detail = f"{console.rpc_failure} The shared model remains loaded."
                elif console.state == "stopping":
                    console.state = "stopped"
                    console.detail = "Agent stopped. The shared model remains loaded."
                else:
                    console.state = "exited" if console.exit_code == 0 else "failed"
                    if unexpected_rpc_eof:
                        console.detail = (
                            "Pi ended before the active response reported a clean completion. "
                            "Partial output was preserved and queued follow-ups were not sent."
                        )
                    else:
                        console.detail = (
                            "Agent exited normally. The shared model remains loaded."
                            if console.exit_code == 0 else
                            f"Agent exited with status {console.exit_code}. The shared model remains loaded."
                        )
                    if console.exit_code not in {None, 0} and not unexpected_rpc_eof:
                        console.append_timeline(
                            "error",
                            f"Pi exited with status {console.exit_code}. The shared model remains loaded.",
                            title="Pi exited",
                            item_id=f"live:{console.rpc_timeline_turn}:process-exit",
                            operation="replace",
                        )
            console.append(unexpected_rpc_output)
            with self.lock:
                if self.agent_consoles.get(console.plan.run_id) is console:
                    attachment = self.attachments.get(console.plan.run_id)
                    if attachment is not None:
                        attachment.status = console.state
                        attachment.detail = console.detail

    def _agent_console_for_payload(self, payload: dict[str, Any]) -> AgentConsole:
        owner_run_id = str(payload.get("ownerRunId") or "")
        surface_id = str(payload.get("surfaceId") or payload.get("attachmentId") or "")
        with self.lock:
            owner = self.plan
            console = self.agent_consoles.get(surface_id)
            if (
                owner is None or owner.purpose != "session"
                or owner.run_id != owner_run_id
                or self.state.get("phase") not in {"starting", "running", "stopping"}
                or console is None or console.owner_run_id != owner.run_id
            ):
                raise ValueError("That Hub Console no longer belongs to the active model route.")
            return console

    def read_agent_console(self, payload: dict[str, Any]) -> dict[str, Any]:
        console = self._agent_console_for_payload(payload)
        if console.structured:
            now = time.monotonic()
            with console.lock:
                should_probe = (
                    console.state == "running" and console.process.poll() is None
                    and console.master_fd >= 0
                    and now - console.rpc_last_state_probe_at >= PI_RPC_STATE_PROBE_SECONDS
                )
                if should_probe:
                    console.rpc_last_state_probe_at = now
            if should_probe:
                try:
                    self._write_pi_rpc_command(console, {
                        "id": f"launcher-state-{secrets.token_hex(6)}",
                        "type": "get_state",
                    })
                except ValueError:
                    pass
        result = console.output_slice(
            payload.get("offset"), payload.get("timelineRevision"),
            timeline_version=payload.get("timelineVersion"),
        )
        result["toolPreview"] = None
        owner = self.plan
        if (owner and owner.run_dir and owner.secrets.get("omlxNativeContextGuard")
                and console.rpc_streaming and not console.rpc_compacting):
            try:
                preview_path = owner.run_dir / "tool-preview.json"
                if preview_path.stat().st_size <= 400_000:
                    preview = json.loads(preview_path.read_text())
                    activity = self._session_proxy_api("GET", "/__launcher/status", timeout=0.8)
                    active = activity.get("active", [])
                    if (isinstance(preview, dict)
                            and isinstance(preview.get("updatedAt"), (int, float))
                            and 0 <= time.time() - preview["updatedAt"] < 5
                            and isinstance(preview.get("title"), str)
                            and isinstance(preview.get("text"), str)
                            and any(item.get("surfaceId") == console.plan.run_id
                                    and item.get("runtimeResponseId") == preview.get("responseId")
                                    and item.get("runtimeResponseId") for item in active)):
                        result["toolPreview"] = preview
            except (OSError, ValueError, TypeError):
                pass
        return result

    def write_agent_console(self, payload: dict[str, Any]) -> dict[str, Any]:
        console = self._agent_console_for_payload(payload)
        if console.structured:
            return self._write_pi_rpc_console(console, payload)
        value = payload.get("data")
        if not isinstance(value, str):
            raise ValueError("Hub Console input must be text or terminal control keys.")
        encoded = value.encode("utf-8")
        if not encoded or len(encoded) > AGENT_CONSOLE_MAX_INPUT:
            raise ValueError("Hub Console input must be between 1 byte and 64 KB.")
        try:
            with console.lock:
                if console.state != "running" or console.process.poll() is not None or console.master_fd < 0:
                    raise ValueError("That agent is no longer accepting input.")
                self._agent_console_transport(console).send(encoded)
        except OSError as error:
            raise ValueError(f"Could not send input to the agent: {error}") from error
        return console.public()

    @staticmethod
    def _write_pi_rpc_command(console: AgentConsole, command: dict[str, Any]) -> None:
        try:
            with console.lock:
                if (
                    console.state != "running" or console.process.poll() is not None
                    or console.master_fd < 0
                ):
                    raise ValueError("That agent is no longer accepting input.")
                encoded = (console.omp_adapter.encode_command(command, max_bytes=AGENT_CONSOLE_MAX_INPUT)
                    if console.omp_adapter else
                    (json.dumps(command, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
                if len(encoded) > AGENT_CONSOLE_MAX_INPUT:
                    raise ValueError(f"{console.agent_label} Hub input must be at most 64 KB.")
                try:
                    RunManager._agent_console_transport(console).send(
                        encoded,
                        # Each OMP state command has a correlated proof ID. Do
                        # not register a command that coalescing never sends.
                        coalesce_key="state" if command.get("type") == "get_state" and not console.omp_adapter else None,
                    )
                except (ValueError, OSError):
                    if console.omp_adapter:
                        console.omp_adapter.discard_command(str(command.get("id") or ""))
                    raise
        except OSError as error:
            raise ValueError(f"Could not send input to {console.agent_label}: {error}") from error

    def _write_pi_rpc_console(
        self, console: AgentConsole, payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not console.rpc_ready or console.rpc_failure:
            raise ValueError("oh-my-pi Hub Console has not verified its native protocol. Wait for it to connect or open the agent in Terminal.")
        command = str(payload.get("command") or "")
        if not command:
            legacy = payload.get("data")
            if not isinstance(legacy, str):
                raise ValueError(f"{console.agent_label} Hub input must be a message or control action.")
            if legacy == "\x03":
                command = "abort"
            elif legacy == "\x1b":
                command = "clear_queue"
            else:
                command = "prompt"
                payload = {**payload, "message": legacy.rstrip("\r\n")}
        if command == "prompt":
            message = payload.get("message")
            if not isinstance(message, str) or not message.strip():
                raise ValueError(f"Enter a message for {console.agent_label}.")
            if len(json.dumps(message, ensure_ascii=False).encode("utf-8")) - 2 > AGENT_CONSOLE_MAX_INPUT - 256:
                raise ValueError(f"{console.agent_label} Hub messages must be smaller than 64 KB.")
            if message.strip() == "/":
                raise ValueError("Choose a command from the list below the message box.")
            slash = re.match(r"^/([A-Za-z][\w:-]*)(?:\s|$)", message.strip())
            if slash:
                name = slash.group(1)
                with console.lock:
                    entry = next((item for item in console.rpc_commands if item["name"] == name), None)
                    if entry is None:
                        raise ValueError(f"/{name} is not available in this {console.agent_label} session. Type / to see available commands.")
                    if entry.get("source") == "extension":
                        if console.rpc_command_ids:
                            raise ValueError(f"Finish or cancel the current {console.agent_label} command first.")
                        command_id = f"launcher-slash-{secrets.token_hex(8)}"
                        console.rpc_command_ids[command_id] = name
                        try:
                            arguments = message.strip()[slash.end():].lstrip()
                            self._write_pi_rpc_command(console, {"id": command_id, "type": "prompt", "message": f"/{name}" + (f" {arguments}" if arguments else "")})
                        except ValueError:
                            console.rpc_command_ids.pop(command_id, None)
                            raise
                        return console.public()
            prompt_id = f"launcher-prompt-{secrets.token_hex(8)}"
            with console.lock:
                if console.rpc_compacting and not console.rpc_prompt_inflight:
                    raise ValueError("Wait for context compaction to finish before sending a message.")
                is_busy = console.rpc_streaming or console.rpc_prompt_inflight or console.rpc_compacting
                if is_busy:
                    queued_bytes = sum(
                        len(item.encode("utf-8")) for item in console.rpc_follow_up_queue
                    )
                    if len(console.rpc_follow_up_queue) >= PI_RPC_MAX_QUEUED_MESSAGES:
                        raise ValueError(f"{console.agent_label} Hub can queue at most 32 follow-up messages.")
                    if queued_bytes + len(message.encode("utf-8")) > PI_RPC_MAX_QUEUED_BYTES:
                        raise ValueError(f"{console.agent_label} Hub's follow-up queue has reached its 512 KB memory limit.")
                    console.rpc_follow_up_queue.append(message)
                    console.rpc_pending_messages = (
                        len(console.rpc_follow_up_queue)
                        + console.rpc_external_pending_messages
                    )
                    pending = console.rpc_pending_messages
                else:
                    console.rpc_prompt_inflight = True
                    console.rpc_streaming = True
                    console.rpc_prompt_id = prompt_id
                    console.rpc_prompt_acknowledged = False
                    console.rpc_queued_prompt_message = ""
                    console.rpc_queue_paused = False
                    console.rpc_queue_advance_allowed = False
                    pending = 0
            if is_busy:
                pi_rpc_record_queue(
                    console,
                    f"{pending} follow-up message{'s' if pending != 1 else ''} waiting",
                )
                console.append(
                    pi_rpc_heading("QUEUED", "38;5;214")
                    + f"{pending} follow-up message{'s' if pending != 1 else ''} waiting".encode("utf-8")
                )
                return console.public()
            rpc_command = {
                "id": prompt_id,
                "type": "prompt",
                "message": message,
                "streamingBehavior": "followUp",
            }
        elif command == "steer":
            message = payload.get("message")
            if not isinstance(message, str) or not message.strip():
                raise ValueError(f"Enter steering instructions for {console.agent_label}.")
            if len(json.dumps(message, ensure_ascii=False).encode("utf-8")) - 2 > AGENT_CONSOLE_MAX_INPUT - 256:
                raise ValueError(f"{console.agent_label} Hub messages must be smaller than 64 KB.")
            if message.lstrip().startswith("/"):
                raise ValueError("Use Send for slash commands; Steer accepts instructions for the current task.")
            with console.lock:
                if not (console.rpc_streaming or console.rpc_prompt_inflight) or console.rpc_compacting:
                    raise ValueError(f"{console.agent_label} is not currently responding. Use Send to start a new prompt.")
                if console.rpc_external_pending_messages + len(console.rpc_steer_ids) >= PI_RPC_MAX_QUEUED_MESSAGES:
                    raise ValueError(f"{console.agent_label} has too many pending steering messages. Wait for it to read them.")
                request_id = f"launcher-steer-{secrets.token_hex(8)}"
                console.rpc_steer_ids[request_id] = message
                try:
                    self._write_pi_rpc_command(console, {"id":request_id, "type":"prompt", "streamingBehavior":"steer", "message":message})
                except ValueError:
                    console.rpc_steer_ids.pop(request_id, None)
                    raise
            return console.public()
        elif command == "compact":
            with console.lock:
                if console.rpc_streaming or console.rpc_prompt_inflight or console.rpc_compacting:
                    raise ValueError(f"Wait for {console.agent_label} to finish before compacting context.")
                console.rpc_compacting = True
            rpc_command = {"id": f"launcher-compact-{secrets.token_hex(6)}", "type": "compact"}
        elif command == "extension_response":
            request_id = str(payload.get("requestId") or "")
            with console.lock:
                interaction = next((
                    copy.deepcopy(item) for item in console.rpc_interactions
                    if item.get("id") == request_id
                ), None)
            if interaction is None:
                raise ValueError(f"That {console.agent_label} request is no longer waiting for an answer.")
            method = interaction["method"]
            rpc_command = {"type": "extension_ui_response", "id": request_id}
            response_label = "Cancelled"
            if payload.get("cancelled") is True:
                rpc_command["cancelled"] = True
            elif method == "confirm":
                if not isinstance(payload.get("confirmed"), bool):
                    raise ValueError(f"Choose Yes, No, or Cancel for {console.agent_label}.")
                rpc_command["confirmed"] = payload["confirmed"]
                response_label = "Yes" if payload["confirmed"] else "No"
            else:
                value = payload.get("value")
                if not isinstance(value, str):
                    raise ValueError(f"Enter a response for {console.agent_label}.")
                if method == "select" and value not in interaction.get("options", []):
                    raise ValueError(f"Choose one of {console.agent_label}'s listed options.")
                if len(value.encode("utf-8")) > AGENT_CONSOLE_MAX_INPUT - 256:
                    raise ValueError(f"{console.agent_label} dialog responses must be smaller than 64 KB.")
                rpc_command["value"] = value
                response_label = value or "Empty response"
            self._write_pi_rpc_command(console, rpc_command)
            with console.lock:
                console.rpc_interactions = [
                    item for item in console.rpc_interactions
                    if item.get("id") != request_id
                ]
            if interaction.get("title") == "__launcher_custom_ui__":
                return console.public()
            console.append(
                pi_rpc_heading(f"{console.agent_label.upper()} INPUT SENT", "38;5;109")
                + safe_agent_transcript_text(response_label, 2_000).encode("utf-8")
            )
            console.append_timeline(
                "notice", response_label, title="Input sent",
                item_id=f"interaction:{hashlib.sha256(request_id.encode('utf-8')).hexdigest()[:20]}",
                operation="replace",
            )
            return console.public()
        elif command == "abort":
            rpc_command = {
                "id": f"launcher-abort-{secrets.token_hex(6)}", "type": "abort",
            }
        elif command in {"edit_queued_message", "delete_queued_message"}:
            with console.lock:
                entries = pi_rpc_visible_queue(console)
                index = next((i for i, item in enumerate(entries)
                              if item.get("id") == payload.get("queueId") and item.get("id")), None)
                if index is None or not entries[index].get("editable"):
                    raise ValueError("That queued message changed or is already being sent. Refresh the queue and try again.")
                messages = list(console.rpc_follow_up_queue)
                if command == "edit_queued_message":
                    message = payload.get("message")
                    if not isinstance(message, str) or not message.strip():
                        raise ValueError(f"Enter a message for {console.agent_label}.")
                    if len(json.dumps(message, ensure_ascii=False).encode("utf-8")) - 2 > AGENT_CONSOLE_MAX_INPUT - 256:
                        raise ValueError(f"{console.agent_label} Hub messages must be smaller than 64 KB.")
                    messages[index] = message
                    if sum(len(item.encode("utf-8")) for item in messages) > PI_RPC_MAX_QUEUED_BYTES:
                        raise ValueError(f"{console.agent_label} Hub's follow-up queue has reached its 512 KB memory limit.")
                else:
                    messages.pop(index)
                path = pi_rpc_queue_path(console)
                if path is None:
                    raise ValueError(f"Wait for {console.agent_label} to open its saved session before changing the queue.")
                record = {"version": 1, "sessionFile": console.rpc_queue_session,
                          "project": str(console.plan.project), "messages": messages}
                try:
                    atomic_json(path, record)
                except OSError as error:
                    raise ValueError("Could not save the queue change. Your original message is still queued.") from error
                console.rpc_follow_up_queue = messages
                console.rpc_queue_saved = hashlib.sha256(json.dumps(record, ensure_ascii=False).encode()).hexdigest()
                console.rpc_queue_save_error = ""
                console.rpc_pending_messages = len(messages) + console.rpc_external_pending_messages
                pi_rpc_record_queue(console, "Queued message updated" if command == "edit_queued_message" else "Queued message deleted")
            return console.public()
        elif command == "clear_queue":
            with console.lock:
                cleared = len(console.rpc_follow_up_queue)
                console.rpc_follow_up_queue.clear()
                console.rpc_queued_prompt_message = ""
                console.rpc_pending_messages = console.rpc_external_pending_messages
                console.rpc_queue_paused = False
                pi_rpc_record_queue(
                    console,
                    f"{console.rpc_pending_messages} external message"
                    f"{'s' if console.rpc_pending_messages != 1 else ''} still waiting"
                    if console.rpc_pending_messages else "Queue cleared",
                )
            console.append(
                pi_rpc_heading("QUEUE CLEARED", "38;5;109")
                + f"Removed {cleared} launcher-queued follow-up message{'s' if cleared != 1 else ''}.".encode("utf-8")
            )
            return console.public()
        else:
            raise ValueError(f"Unknown {console.agent_label} Hub action.")
        try:
            self._write_pi_rpc_command(console, rpc_command)
        except ValueError:
            if command == "compact":
                console.rpc_compacting = False
            if command == "prompt":
                with console.lock:
                    if console.rpc_prompt_id == rpc_command["id"]:
                        console.rpc_prompt_inflight = False
                        console.rpc_streaming = False
                        console.rpc_prompt_id = ""
                        console.rpc_prompt_acknowledged = False
                        console.rpc_queued_prompt_message = ""
                    console.rpc_queue_advance_allowed = False
                    console.rpc_queue_paused = bool(console.rpc_follow_up_queue)
                    console.rpc_pending_messages = (
                        len(console.rpc_follow_up_queue)
                        + console.rpc_external_pending_messages
                    )
                    console.append_timeline(
                        "error", f"The message could not be sent to {console.agent_label}.",
                        title=f"{console.agent_label} input failed",
                        item_id=f"live:{console.rpc_timeline_turn}:prompt-write-error",
                        operation="replace",
                    )
            raise
        if command == "abort":
            console.append_timeline(
                "notice", f"Stopping the current {console.agent_label} response.",
                title="Stopping response",
                item_id=f"live:{console.rpc_timeline_turn}:abort", operation="replace",
            )
        return console.public()

    def resize_agent_console(self, payload: dict[str, Any]) -> dict[str, Any]:
        console = self._agent_console_for_payload(payload)
        try:
            cols = int(payload.get("cols"))
            rows = int(payload.get("rows"))
        except (TypeError, ValueError) as error:
            raise ValueError("Choose a valid Hub Console size.") from error
        if not AGENT_CONSOLE_COLS[0] <= cols <= AGENT_CONSOLE_COLS[1] or not AGENT_CONSOLE_ROWS[0] <= rows <= AGENT_CONSOLE_ROWS[1]:
            raise ValueError("Hub Console supports 40–240 columns and 12–100 rows.")
        with console.lock:
            if console.master_fd < 0:
                raise ValueError("That agent console has ended.")
            self._set_agent_console_size(console.master_fd, cols, rows)
            console.cols = cols
            console.rows = rows
        return console.public()

    def _stop_agent_console_process(self, console: AgentConsole) -> None:
        with console.lock:
            if console.process.poll() is not None and console.master_fd < 0:
                return
            console.state = "stopping"
            console.detail = "Stopping the agent while keeping the model loaded…"
        self._terminate_process(console.process, 5)
        self._close_agent_console_fd(console)
        with console.lock:
            if console.state == "stopping" and console.process.poll() is not None:
                console.state = "stopped"
                console.exit_code = console.process.returncode
                console.ended_at = console.ended_at or datetime.now(timezone.utc).isoformat()
                console.detail = "Agent stopped. The shared model remains loaded."
        with self.lock:
            if self.agent_consoles.get(console.plan.run_id) is console:
                attachment = self.attachments.get(console.plan.run_id)
                if attachment is not None:
                    attachment.status = console.state
                    attachment.detail = console.detail

    def stop_agent_console(self, payload: dict[str, Any]) -> dict[str, Any]:
        console = self._agent_console_for_payload(payload)
        self._stop_agent_console_process(console)
        self.event(
            f"{CLIENT_LABELS.get(console.plan.client, console.plan.client)} stopped; the shared model stays loaded."
        )
        return console.public()

    def restart_agent_console(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.surface_lock:
            old = self._agent_console_for_payload(payload)
            if old.process.poll() is None or old.state in {"starting", "running", "stopping"}:
                raise ValueError("Stop this agent before restarting it.")
            with self.lock:
                owner = self.plan
                cancel_event = self.cancel_event
                attachment = self.attachments.get(old.plan.run_id)
                if owner is None or attachment is None:
                    raise ValueError("That Hub Console no longer belongs to the active model route.")
                attachment.status = "starting"
                attachment.detail = "Restarting the agent in Hub Console…"
            if old.structured and old.rpc_queue_session:
                session = validated_agent_session_file(old.rpc_queue_session, old.plan.project, old.agent_label)
                if old.plan.client == "pi":
                    old.plan.pi_session_file = session
                argv = old.plan.client_argv
                if "--session" in argv:
                    argv[argv.index("--session") + 1] = session
                else:
                    argv.extend(["--session", session])
            console = self._launch_agent_console(
                old.plan, cancel_event, owner_plan=owner, attachment=attachment,
            )
        self.event(f"{CLIENT_LABELS.get(old.plan.client, old.plan.client)} restarted in Hub Console.")
        return console.public()

    def _start_session_proxy(
        self, plan: LaunchPlan, log_path: Path, cancel_event: threading.Event,
    ) -> None:
        """Start the authenticated relay shared by every normal work surface."""
        assert plan.run_dir and plan.client_port
        client_key = str(plan.secrets.get("clientApiKey") or "")
        control_key = str(plan.secrets.get("proxyControlKey") or "")
        if not client_key or not control_key:
            raise RuntimeError("The normal session has no private relay keys.")
        config_path = plan.run_dir / "session-proxy.json"
        atomic_json(config_path, {
            "listenPort": plan.client_port,
            "upstreamPort": plan.port,
            "upstreamKey": plan.secrets.get("apiKey", "local"),
            "controlKey": control_key,
            "lanes": session_request_lanes(plan),
            "outputLimit": plan.output,
            "omlxNativeContextGuard": plan.secrets.get("omlxNativeContextGuard") is True,
            "contextLimit": (
                plan.context if plan.backend in {"omlx", "uzu"} else None
            ),
            "reasoning": plan.reasoning,
            "backend": plan.backend,
            "reasoningBudgetMessage": (
                LLAMACPP_QWEN_REASONING_BUDGET_MESSAGE
                if plan.backend == "llamacpp" else None
            ),
            "servedModel": plan.model["servedId"],
            "servedModelAliases": [pi_model_identity(plan)[1]],
            "templateReasoningEfforts": plan.model.get("templateReasoningEfforts", []),
            "surfaces": [{
                "id": plan.run_id,
                "client": plan.client,
                "key": client_key,
                "samplingContract": copy.deepcopy(plan.sampling_contract),
                "samplingEnforcement": copy.deepcopy(plan.sampling_enforcement),
            }],
        })
        proxy: subprocess.Popen[str] | None = None
        try:
            with open(log_path, "a", encoding="utf-8") as log_handle:
                proxy = subprocess.Popen(
                    [sys.executable, str(APP_DIR / "session_proxy.py"), str(config_path)],
                    cwd=plan.project, text=True, stdout=log_handle, stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                self._publish_owned_process("proxy_process", proxy, plan, cancel_event)
            deadline = time.time() + 12
            while time.time() < deadline:
                self._check_cancelled(cancel_event)
                if proxy.poll() is not None:
                    raise RuntimeError("The private session relay exited during startup.")
                request = urllib.request.Request(
                    f"http://127.0.0.1:{plan.client_port}/__launcher/status",
                    headers={"Authorization": f"Bearer {control_key}"},
                )
                try:
                    with urllib.request.urlopen(request, timeout=1) as response:
                        status = json.loads(response.read(1_000_000))
                    if response.status == 200 and status.get("version") == REQUEST_ACTIVITY_VERSION:
                        with self.lifecycle_lock:
                            with self.lock:
                                if (
                                    self.plan is not plan
                                    or self.cancel_event is not cancel_event
                                    or cancel_event.is_set()
                                ):
                                    raise LaunchCancelled("Launch cancelled.")
                                self.session_proxy_port = plan.client_port
                                self.session_proxy_control_key = control_key
                        return
                except (OSError, ValueError, urllib.error.URLError):
                    cancel_event.wait(0.15)
            raise RuntimeError("Timed out starting the private session relay.")
        except Exception:
            if proxy is not None:
                self._clear_owned_process("proxy_process", proxy)
                self._terminate_process(proxy, 5)
            raise

    def _start_codex_proxy(
        self,
        plan: LaunchPlan,
        log_path: Path,
        cancel_event: threading.Event,
        owner_plan: LaunchPlan | None = None,
    ) -> None:
        """Start the private Responses pass-through that enforces the output contract."""
        assert plan.run_dir and plan.client_port
        owner = owner_plan or plan
        proxy_key = plan.client_env["LLM_LAUNCHER_CODEX_API_KEY"]
        config_path = plan.run_dir / "codex-proxy.json"
        atomic_json(config_path, {
            "listenPort": plan.client_port,
            "upstreamPort": plan.port,
            "upstreamKey": plan.secrets.get("apiKey", "local"),
            "clientKey": proxy_key,
            "outputLimit": plan.output,
            "contextLimit": plan.context if plan.backend == "omlx" else None,
            "reasoning": plan.reasoning,
            "backend": plan.backend,
            "servedModel": plan.model["servedId"],
            "templateReasoningEfforts": plan.model.get("templateReasoningEfforts", []),
            "samplingContract": copy.deepcopy(plan.sampling_contract),
            "samplingEnforcement": copy.deepcopy(plan.sampling_enforcement),
        })
        proxy: subprocess.Popen[str] | None = None
        try:
            with open(log_path, "a", encoding="utf-8") as log_handle:
                proxy = subprocess.Popen(
                    [sys.executable, str(APP_DIR / "codex_proxy.py"), str(config_path)],
                    cwd=plan.project, text=True, stdout=log_handle, stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                self._publish_owned_process("proxy_process", proxy, owner, cancel_event)
            deadline = time.time() + 12
            while time.time() < deadline:
                self._check_cancelled(cancel_event)
                if proxy.poll() is not None:
                    raise RuntimeError("The Codex compatibility guard exited during startup.")
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{plan.client_port}/health", timeout=1) as response:
                        if response.status == 200:
                            with self.lifecycle_lock:
                                with self.lock:
                                    if (
                                        self.plan is not owner
                                        or self.cancel_event is not cancel_event
                                        or cancel_event.is_set()
                                    ):
                                        raise LaunchCancelled("Launch cancelled.")
                                    self.codex_proxy_port = plan.client_port
                                    self.codex_proxy_key = proxy_key
                            return
                except OSError:
                    cancel_event.wait(0.15)
            raise RuntimeError("Timed out starting the Codex compatibility guard.")
        except Exception:
            if proxy is not None:
                self._clear_owned_process("proxy_process", proxy)
                self._terminate_process(proxy, 5)
            raise

    def _verify_lmstudio_reasoning(self, plan: LaunchPlan) -> None:
        """Confirm a non-default Codex effort against LM Studio's live model metadata."""
        if plan.backend != "lmstudio" or plan.client != "codex" or plan.reasoning == "auto":
            return
        request = urllib.request.Request(f"http://127.0.0.1:{plan.port}/api/v1/models")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                data = json.loads(response.read(4_000_000))
        except (OSError, ValueError, urllib.error.URLError) as error:
            raise RuntimeError(f"Could not verify LM Studio reasoning support: {error}") from error
        models = data.get("models") if isinstance(data, dict) else None
        record = next(
            (
                item for item in models or []
                if isinstance(item, dict)
                and (
                    item.get("key") == plan.model.get("lmKey")
                    or item.get("selected_variant") == plan.model.get("lmKey")
                    or any(
                        isinstance(instance, dict) and instance.get("id") == plan.model.get("servedId")
                        for instance in item.get("loaded_instances", [])
                    )
                )
            ),
            None,
        )
        reasoning = deep_get(record or {}, ("capabilities", "reasoning"))
        allowed = reasoning.get("allowed_options") if isinstance(reasoning, dict) else None
        if not isinstance(allowed, list) or plan.reasoning not in allowed:
            choices = ", ".join(str(item) for item in allowed or []) or "model default only"
            raise RuntimeError(
                f"LM Studio does not advertise {plan.reasoning} reasoning for this loaded model (available: {choices})."
            )

    def _verify_client_api(self, plan: LaunchPlan) -> None:
        """Fail before opening Codex when its native or bridged protocol is absent."""
        if plan.client != "codex":
            return
        body = b"{}"  # Deliberately invalid: a real route validates; a missing route returns 404/405.
        bridged = plan.backend == "mtplx"
        request = urllib.request.Request(
            f"http://127.0.0.1:{plan.port}/v1/{'chat/completions' if bridged else 'responses'}",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {plan.secrets.get('apiKey', 'local')}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                response.read(4_096)
        except urllib.error.HTTPError as error:
            if error.code in {400, 422}:
                return
            if error.code in {404, 405}:
                raise RuntimeError(
                    "MTPLX does not expose the Chat Completions route required by the launcher Codex bridge."
                    if bridged else
                    "This runtime does not expose the Responses API required by Codex."
                ) from error
            raise RuntimeError(f"Codex API preflight failed with HTTP {error.code}.") from error
        except (OSError, urllib.error.URLError) as error:
            raise RuntimeError(f"Codex API preflight failed: {error}") from error

    def stop(self, *, expected_plan: LaunchPlan | None = None,
             expected_cancel_event: threading.Event | None = None) -> None:
        # Capture the generation before waiting. A duplicate Stop request that
        # queued behind an earlier one must never stop a newer run.
        with self.lock:
            if expected_plan is not None and self.plan is not expected_plan:
                return
            if expected_cancel_event is not None and self.cancel_event is not expected_cancel_event:
                return
            target_plan = self.plan
            target_cancel = self.cancel_event
        with self.stop_lock:
            with self.lifecycle_lock:
                with self.lock:
                    if self.plan is not target_plan or self.cancel_event is not target_cancel:
                        return
                    worker = self.worker_thread
                    monitor = self.monitor_thread
                    guard = self.llamacpp_guard_thread
                    if (
                        self.state["phase"] == "idle"
                        and not (worker and worker.is_alive())
                        and not (monitor and monitor.is_alive())
                        and not (guard and guard.is_alive())
                    ):
                        return
                    self.state["phase"] = "stopping"
                    target_cancel.set()
                    self.state["message"] = "Stopping launcher-owned processes…"
                    self.state["events"] = (
                        self.state.get("events", [])
                        + [{"time": time.strftime("%H:%M:%S"), "level": "info", "message": self.state["message"]}]
                    )[-80:]
            if target_plan is not None:
                self._stop_owned(target_plan)
            if worker and worker is not threading.current_thread():
                worker.join(timeout=20)
            if monitor and monitor is not threading.current_thread():
                monitor.join(timeout=8)
            if guard and guard is not threading.current_thread():
                guard.join(timeout=8)
            with self.lock:
                if self.plan is not target_plan or self.cancel_event is not target_cancel:
                    return
                if (
                    (worker and worker.is_alive()) or (monitor and monitor.is_alive())
                    or (guard and guard.is_alive())
                ):
                    self.state["phase"] = "failed"
                    self.state["message"] = "A launcher worker did not stop cleanly; no new run will start until it exits."
                    return
                message = (
                    "Stopped. Private FreeToken bridge closed; the remote server and model were left untouched."
                    if target_plan is not None and target_plan.backend == "freetoken"
                    and target_plan.model.get("remote") is True else
                    "Stopped. Launcher-owned native FreeToken was unloaded."
                    if target_plan is not None and target_plan.backend == "freetoken" else
                    "Stopped. Private Whallm routes closed; Whallm's server and loaded model were left untouched."
                    if target_plan is not None and target_plan.backend == "whallm"
                    and target_plan.model.get("sharedServer") is True else
                    "Stopped. Shared LM Studio service was left alone."
                    if target_plan is not None and target_plan.backend == "lmstudio" else
                    "Stopped. The launcher-owned model route was closed."
                )
                self.state["phase"] = "idle"
                self.state["message"] = message
                self.state["run"] = None
                self.state["events"] = (
                    self.state.get("events", [])
                    + [{"time": time.strftime("%H:%M:%S"), "level": "info", "message": message}]
                )[-80:]
                if target_plan is not None:
                    target_plan.secrets.pop("omlxAdminSessionCookie", None)
                self.plan = None
                self.started_at = None
                self.attachments = {}
                self.agent_consoles = {}
                self.cache_observations = []
                self.codex_proxy_port = None
                self.codex_proxy_key = None
                self.session_proxy_port = None
                self.session_proxy_control_key = None
                self.idle_timeout_minutes = 0
                self.idle_policy_set_at = time.time()

    def _stop_owned(self, plan: LaunchPlan) -> None:
        # Exactly one caller owns cleanup for a run. Worker, monitor, and HTTP
        # Stop paths may all converge here concurrently.
        with self.lock:
            if self.plan is not plan:
                return
            complete = self.cleanup_complete
            if self.cleanup_started:
                owns_cleanup = False
            else:
                self.cleanup_started = True
                self.cancel_event.set()
                owns_cleanup = True
        if not owns_cleanup:
            complete.wait(timeout=75)
            return

        try:
            # Remove published references atomically. A child created just
            # before Stop will either be captured here, or its publication
            # gate will observe cancellation and terminate the local process.
            with self.lifecycle_lock:
                if self.plan is not plan:
                    return
                proxy = self.proxy_process
                auxiliary = self.aux_process
                engine = self.process
                consoles = list(self.agent_consoles.values())
                self.proxy_process = None
                self.aux_process = None
                self.process = None
                self.agent_consoles = {}
                self.codex_proxy_port = None
                self.codex_proxy_key = None
                self.session_proxy_port = None
                self.session_proxy_control_key = None
                target_id = self.lm_loaded_id or plan.model.get("servedId")
                self.lm_loaded_id = None

            # Stop launcher-owned agent processes before closing their private
            # request route and unloading the model. Terminal handoffs remain
            # deliberately outside launcher process ownership.
            for console in consoles:
                self._stop_agent_console_process(console)
            self._terminate_process(proxy, 5)
            self._terminate_process(auxiliary, 5)
            if plan.backend == "lmstudio" and BINARIES.get("lms"):
                # A cancelled `lms load` may already have reached the shared
                # server even though its CLI has not exited. Unload once now,
                # then keep retrying this run's unique identifier in the
                # background. This never stops the shared LM Studio service or
                # touches models belonging to another run.
                if isinstance(target_id, str) and target_id.startswith("llm-launcher-"):
                    self._unload_lmstudio_id(target_id)
                    self._schedule_lmstudio_cleanup(target_id)
            self._terminate_process(engine, 12)
        finally:
            # Proxy and engine processes are already terminated above, so
            # owner-only configs and one-use engine keys can be removed
            # without racing a live bearer reader.
            dispose_plan_secrets(plan)
            complete.set()

    @staticmethod
    def _unload_lmstudio_id(target_id: str) -> None:
        lms = BINARIES.get("lms")
        if not lms:
            return
        try:
            subprocess.run(
                [lms, "unload", target_id], timeout=10, check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass

    def _schedule_lmstudio_cleanup(self, target_id: str) -> None:
        """Detach exact-ID retries for the full 15-minute load horizon."""
        lms = BINARIES.get("lms")
        if not lms:
            return
        cleanup_dir = STATE_DIR / "cleanup"
        cleanup_dir.mkdir(parents=True, exist_ok=True)
        config_path = cleanup_dir / f"{target_id}.json"
        atomic_json(config_path, {
            "identifier": target_id,
            "lms": lms,
            # `lms load` is bounded at 900 seconds. The final two exact-ID
            # retries happen after that horizon and survive controller exit.
            "deadlines": [2, 10, 30, 60, 120, 240, 480, 720, 930, 1020],
        })
        try:
            subprocess.Popen(
                [sys.executable, str(APP_DIR / "lmstudio_cleanup.py"), str(config_path)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True, close_fds=True,
            )
        except OSError:
            # The immediate unload above has still run. Leave the private
            # config in place so the failure is visible for troubleshooting.
            pass
