#!/usr/bin/env python3
"""Private, metadata-only request relay for one launcher-owned model session.

Every launcher-created work surface receives a distinct bearer key.  The relay
uses those keys to label requests, admits generation work through the exact
number of configured engine lanes, and exposes a separate controller-only
status/cancellation API.  Prompt, response, reasoning, tool, and project data
are never copied into the activity registry.
"""

from __future__ import annotations

import hmac
import http.client
import json
import math
import os
import re
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from codex_proxy import (
    OMLX_CONTEXT_MAX,
    OMLX_CONTEXT_MIN,
    MUTATED_REPRESENTATION_HEADERS,
    PrivateConfigError,
    REASONING_OVERRIDE_FIELDS,
    ResponsesLimitGuard,
    bound_omlx_request_to_context,
    consume_private_config,
    enforce_sampling_contract,
    transform_response_request,
    validate_omlx_context_is_self_contained,
    validated_sampling_policy,
)
from responses_bridge import BridgeRequest, ChatStreamBridge, translate_responses_request
from relay_transport import InterruptibleHTTPConnection
from sse_framing import EventScanner, pop_event


VERSION = 2
MAX_BODY = 128 * 1024 * 1024
MAX_CONTROL_BODY = 64 * 1024
MAX_RECENT = 32
MAX_QUEUE = 64
MAX_METRICS_BUFFER = 1024 * 1024
MAX_LIMIT_GUARD_BUFFER = 256 * 1024
MIN_TPS_COMPLETION_TOKENS = 16
MIN_TPS_SECONDS = 0.25
CLIENTS = {"chat", "pi", "opencode", "codex"}
CLIENT_LABELS = {"chat": "Chat", "pi": "Pi", "opencode": "OpenCode", "codex": "Codex"}
SUPPORTED_BACKENDS = {
    "omlx", "lmstudio", "mtplx", "freetoken", "swiftlm", "mference", "whallm",
    "llamacpp", "uzu",
}
UZU_CONTEXT_WINDOWS = frozenset({16_384, 32_768, 65_536, 131_072})
CHAT_REASONING_LEVELS = frozenset({
    "auto", "off", "minimal", "low", "medium", "high", "xhigh", "max",
})
LLAMACPP_QWEN_REASONING_BUDGET_MESSAGE = (
    "\n\n Considering the limited time by the user, "
    "I have to give the solution based on the thinking directly now."
)
HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "trailers", "transfer-encoding", "upgrade",
}


def mtplx_launcher_request(body: bytes, headers: dict[str, str]) -> tuple[bytes, dict[str, str]]:
    """The authenticated relay owns sampling; MTPLX owns the engine route.

    A `pi` managed-client hint makes MTPLX ignore even explicit sampler values.
    Identify the actual policy owner after the relay validates those values.
    Keep session/cache affinity, but never allow a client to change the loaded
    route's acceleration or draft depth when enabling request controls.
    """
    value = json.loads(body)
    for field in ("generation_mode", "depth", "mtp_depth", "speculative_depth",
                  "draft_block_size", "gemma_draft_block_size"):
        value.pop(field, None)
    recovery_header = "x-llm-launcher-mtplx-recovery"
    recovered_session = next((val for key, val in headers.items()
                              if key.lower() == recovery_header), None)
    if recovered_session is not None and (
        len(recovered_session) > 256
        or not re.fullmatch(r"[A-Za-z0-9._:-]+:recovery:[0-9a-f]{24}", recovered_session)
    ):
        raise ValueError("Invalid repaired MTPLX session identity")
    stripped = {"x-mtplx-client", "x-mtplx-allow-client-controls", recovery_header}
    if recovered_session is not None:
        stripped.add("x-mtplx-session-id")
    result = {key: val for key, val in headers.items() if key.lower() not in stripped}
    if recovered_session is not None:
        # Apply after every client hook: a global Pi extension may reset the
        # public session ID to one whose committed cache still contains a loop.
        result["x-mtplx-session-id"] = recovered_session
    result.update({"x-mtplx-client": "llm-launcher", "x-mtplx-allow-client-controls": "true"})
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode(), result


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fail(message: str) -> None:
    print(f"LLM Launcher session relay: {message}", file=sys.stderr)
    raise SystemExit(2)


def _valid_secret(value: Any) -> bool:
    return isinstance(value, str) and 16 <= len(value) <= 512 and "\0" not in value


def _valid_surface(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("surface is not an object")
    surface_id = str(value.get("id") or "")
    client = str(value.get("client") or "")
    key = value.get("key")
    try:
        parsed = str(uuid.UUID(surface_id))
    except (ValueError, AttributeError) as error:
        raise ValueError("invalid surface id") from error
    if parsed != surface_id.lower() or client not in CLIENTS or not _valid_secret(key):
        raise ValueError("invalid surface registration")
    protocol = "responses" if client == "codex" else "chat-completions"
    contract, enforcement = validated_sampling_policy(
        value.get("samplingContract"), value.get("samplingEnforcement"), protocol,
    )
    return {
        "id": parsed,
        "client": client,
        "key": str(key),
        "samplingContract": contract,
        "samplingEnforcement": enforcement,
    }


def load_config(path: Path) -> dict[str, Any]:
    state_root = (
        Path.home() / "Library" / "Application Support" / "LLM Launcher" / "runs"
    )
    try:
        payload = consume_private_config(path, state_root)
    except PrivateConfigError:
        fail("private configuration could not be safely consumed")
    try:
        value = json.loads(payload)
    except (ValueError, UnicodeError):
        fail("configuration data is invalid")
    if not isinstance(value, dict):
        fail("configuration is not an object")
    for key in ("listenPort", "upstreamPort", "lanes", "outputLimit"):
        if isinstance(value.get(key), bool) or not isinstance(value.get(key), int):
            fail(f"invalid {key}")
    if not 1_024 <= value["listenPort"] <= 65_535 or not 1_024 <= value["upstreamPort"] <= 65_535:
        fail("invalid port")
    if value["listenPort"] == value["upstreamPort"]:
        fail("relay and engine ports must differ")
    if not 1 <= value["lanes"] <= 16 or not 256 <= value["outputLimit"] <= 2_000_000:
        fail("invalid scheduler or output limit")
    if value.get("backend") not in SUPPORTED_BACKENDS:
        fail("unsupported backend")
    if value.get("backend") == "llamacpp":
        if value.get("reasoningBudgetMessage") != LLAMACPP_QWEN_REASONING_BUDGET_MESSAGE:
            fail("invalid llama.cpp reasoning boundary message")
    elif value.get("reasoningBudgetMessage") not in {None, ""}:
        fail("unexpected reasoning boundary message")
    if value.get("reasoning") not in CHAT_REASONING_LEVELS:
        fail("invalid reasoning effort")
    if value.get("backend") == "uzu":
        if value.get("reasoning") not in {"auto", "off"}:
            fail("Uzu Qwen3.6 reasoning must be auto or off")
        if value.get("contextLimit") not in UZU_CONTEXT_WINDOWS:
            fail("invalid Uzu context limit")
    elif value.get("backend") == "omlx":
        context_limit = value.get("contextLimit")
        if (
            isinstance(context_limit, bool) or not isinstance(context_limit, int)
            or not OMLX_CONTEXT_MIN <= context_limit <= OMLX_CONTEXT_MAX
        ):
            fail("invalid oMLX context limit")
    elif value.get("contextLimit") not in {None, 0}:
        fail("unexpected context limit")
    if not all(_valid_secret(value.get(key)) for key in ("controlKey", "upstreamKey")):
        fail("invalid relay secret")
    if not isinstance(value.get("servedModel"), str) or not value["servedModel"]:
        fail("invalid served model")
    aliases = value.get("servedModelAliases", [])
    if (not isinstance(aliases, list) or len(aliases) > 1
            or any(not isinstance(alias, str) or not re.fullmatch(r"local-[0-9a-f]{24}", alias)
                   for alias in aliases)):
        fail("invalid served model aliases")
    surfaces = value.get("surfaces")
    if not isinstance(surfaces, list) or len(surfaces) != 1:
        fail("one primary surface is required")
    try:
        value["surfaces"] = [_valid_surface(surfaces[0])]
    except ValueError as error:
        fail(str(error))
    return value


class SurfaceRegistry:
    def __init__(self, surfaces: list[dict[str, Any]]) -> None:
        self.lock = threading.RLock()
        self.by_id: dict[str, dict[str, Any]] = {}
        for surface in surfaces:
            self.register(surface)

    def register(self, value: Any) -> dict[str, Any]:
        surface = _valid_surface(value)
        with self.lock:
            for current in self.by_id.values():
                if current["key"] == surface["key"] and current["id"] != surface["id"]:
                    raise ValueError("surface key is already registered")
            self.by_id[surface["id"]] = surface
        return dict(surface)

    def unregister(self, surface_id: Any) -> dict[str, Any] | None:
        value = str(surface_id or "")
        with self.lock:
            surface = self.by_id.pop(value, None)
            return dict(surface) if surface else None

    def authenticate(self, authorization: str) -> dict[str, Any] | None:
        if not authorization.startswith("Bearer "):
            return None
        supplied = authorization[7:]
        with self.lock:
            for surface in self.by_id.values():
                if hmac.compare_digest(supplied, surface["key"]):
                    return dict(surface)
        return None

    def public(self) -> list[dict[str, str]]:
        with self.lock:
            return [
                {
                    "id": item["id"],
                    "client": item["client"],
                    "surface": CLIENT_LABELS[item["client"]],
                }
                for item in self.by_id.values()
            ]


class RequestScheduler:
    """Fair FCFS admission with bounded, text-free request metadata."""

    def __init__(self, lanes: int, max_queue: int = MAX_QUEUE) -> None:
        self.lanes = max(1, min(16, int(lanes)))
        self.max_queue = max(1, min(128, int(max_queue)))
        self.condition = threading.Condition(threading.RLock())
        self.records: dict[str, dict[str, Any]] = {}
        self.queue: list[str] = []
        self.active: set[str] = set()
        self.recent: list[dict[str, Any]] = []
        self.started_at = utc_now()
        self.last_activity_at = self.started_at
        self.last_activity_monotonic = time.monotonic()

    def begin(self, surface: dict[str, str], protocol: str) -> str:
        with self.condition:
            if len(self.queue) >= self.max_queue:
                raise OverflowError("The private session request queue is full.")
            request_id = str(uuid.uuid4())
            now = time.monotonic()
            self.records[request_id] = {
                "id": request_id,
                "surfaceId": surface["id"],
                "client": surface["client"],
                "surface": CLIENT_LABELS[surface["client"]],
                "protocol": protocol,
                "state": "queued",
                "queuedAt": utc_now(),
                "queuedMonotonic": now,
                "startedAt": None,
                "startedMonotonic": None,
                "firstByteAt": None,
                "firstByteMonotonic": None,
                "firstOutputAt": None,
                "firstOutputMonotonic": None,
                "endedAt": None,
                "endedMonotonic": None,
                "statusCode": None,
                "bytesRelayed": 0,
                "promptTokens": None,
                "completionTokens": None,
                "runtimeTokensPerSecond": None,
                "runtimeTimeToFirstTokenSeconds": None,
                "runtimeGenerationSeconds": None,
                "totalDraftTokens": None,
                "acceptedDraftTokens": None,
                "speculativeAcceptancePercent": None,
                "result": None,
                "cancel": threading.Event(),
                "connection": None,
            }
            self.queue.append(request_id)
            self.last_activity_at = utc_now()
            self.last_activity_monotonic = now
            self.condition.notify_all()
            return request_id

    def await_turn(self, request_id: str) -> bool:
        with self.condition:
            while True:
                record = self.records.get(request_id)
                if record is None:
                    return False
                if record["cancel"].is_set():
                    self._finish_locked(record, "cancelled")
                    return False
                if self.queue and self.queue[0] == request_id and len(self.active) < self.lanes:
                    self.queue.pop(0)
                    self.active.add(request_id)
                    record["state"] = "running"
                    record["startedAt"] = utc_now()
                    record["startedMonotonic"] = time.monotonic()
                    self.condition.notify_all()
                    return True
                self.condition.wait(0.25)

    def set_connection(self, request_id: str, connection: InterruptibleHTTPConnection) -> None:
        cancel_now = False
        with self.condition:
            record = self.records.get(request_id)
            if record is None or record["cancel"].is_set():
                cancel_now = True
            else:
                record["connection"] = connection
        if cancel_now:
            connection.cancel()

    def first_byte(self, request_id: str) -> None:
        with self.condition:
            record = self.records.get(request_id)
            if record is not None and record["firstByteMonotonic"] is None:
                record["firstByteAt"] = utc_now()
                record["firstByteMonotonic"] = time.monotonic()

    def first_output(self, request_id: str) -> None:
        with self.condition:
            record = self.records.get(request_id)
            if record is not None and record["firstOutputMonotonic"] is None:
                record["firstOutputAt"] = utc_now()
                record["firstOutputMonotonic"] = time.monotonic()

    def set_usage(
        self, request_id: str, prompt_tokens: int | None, completion_tokens: int | None,
    ) -> None:
        def valid(value: int | None) -> int | None:
            return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None

        with self.condition:
            record = self.records.get(request_id)
            if record is not None:
                record["promptTokens"] = valid(prompt_tokens)
                record["completionTokens"] = valid(completion_tokens)

    def set_runtime_stats(self, request_id: str, value: dict[str, Any]) -> None:
        """Attach allowlisted numeric facts and Uzu's opaque log correlation tag."""
        bounds = {
            "runtimeTokensPerSecond": 1_000_000.0,
            "runtimeTimeToFirstTokenSeconds": 86_400.0,
            "runtimeGenerationSeconds": 86_400.0,
            "totalDraftTokens": 2_000_000_000,
            "acceptedDraftTokens": 2_000_000_000,
            "speculativeAcceptancePercent": 100.0,
        }
        with self.condition:
            record = self.records.get(request_id)
            if record is None:
                return
            tag = value.get("uzuRequestTag")
            if isinstance(tag, str) and re.fullmatch(r"[0-9a-f]{8}", tag):
                record["uzuRequestTag"] = tag
            response_id = value.get("runtimeResponseId")
            if isinstance(response_id, str) and re.fullmatch(r"chatcmpl-[0-9a-f]{8,32}", response_id):
                record["runtimeResponseId"] = response_id
            for key, maximum in bounds.items():
                candidate = value.get(key)
                integer_field = key in {"totalDraftTokens", "acceptedDraftTokens"}
                if (
                    isinstance(candidate, (int, float))
                    and not isinstance(candidate, bool)
                    and (not integer_field or isinstance(candidate, int))
                    and math.isfinite(float(candidate))
                    and 0 <= float(candidate) <= maximum
                ):
                    record[key] = candidate

    def add_bytes(self, request_id: str, count: int) -> None:
        with self.condition:
            record = self.records.get(request_id)
            if record is not None:
                record["bytesRelayed"] += max(0, int(count))

    def cancelled(self, request_id: str) -> bool:
        with self.condition:
            record = self.records.get(request_id)
            return bool(record and record["cancel"].is_set())

    def cancel(self, request_id: Any) -> bool:
        connection: InterruptibleHTTPConnection | None = None
        with self.condition:
            record = self.records.get(str(request_id or ""))
            if record is None:
                return False
            record["cancel"].set()
            record["state"] = "cancelling"
            connection = record.get("connection")
            self.condition.notify_all()
        if connection is not None:
            connection.cancel()
        return True

    def cancel_surface(self, surface_id: Any) -> int:
        with self.condition:
            ids = [
                item["id"] for item in self.records.values()
                if item["surfaceId"] == str(surface_id or "")
            ]
        return sum(1 for request_id in ids if self.cancel(request_id))

    def finish(self, request_id: str, result: str, status_code: int | None = None) -> None:
        with self.condition:
            record = self.records.get(request_id)
            if record is None:
                return
            record["statusCode"] = status_code
            self._finish_locked(record, result)

    def _finish_locked(self, record: dict[str, Any], result: str) -> None:
        request_id = record["id"]
        if request_id not in self.records:
            return
        if request_id in self.queue:
            self.queue.remove(request_id)
        self.active.discard(request_id)
        now = time.monotonic()
        record["state"] = "cancelled" if result == "cancelled" else "completed"
        record["result"] = result
        record["endedAt"] = utc_now()
        record["endedMonotonic"] = now
        record["connection"] = None
        self.recent = (self.recent + [self._public_locked(record)])[-MAX_RECENT:]
        del self.records[request_id]
        self.last_activity_at = record["endedAt"]
        self.last_activity_monotonic = now
        self.condition.notify_all()

    @staticmethod
    def _seconds(value: float | None) -> float | None:
        return round(max(0.0, value), 3) if value is not None else None

    def _public_locked(self, record: dict[str, Any]) -> dict[str, Any]:
        now = record.get("endedMonotonic") or time.monotonic()
        queued = float(record["queuedMonotonic"])
        started = record.get("startedMonotonic")
        first = record.get("firstByteMonotonic")
        first_output = record.get("firstOutputMonotonic")
        position = self.queue.index(record["id"]) + 1 if record["id"] in self.queue else None
        run_seconds = (now - started) if started is not None else None
        generation_seconds = (
            now - first_output
            if first_output is not None and now >= first_output else None
        )
        prompt_tokens = record.get("promptTokens")
        completion_tokens = record.get("completionTokens")
        usage_reported = isinstance(prompt_tokens, int) and isinstance(completion_tokens, int)
        enough_output_for_tps = bool(
            usage_reported and completion_tokens >= MIN_TPS_COMPLETION_TOKENS
        )
        end_to_end_sample_qualified = bool(
            enough_output_for_tps and run_seconds is not None
            and run_seconds >= MIN_TPS_SECONDS
        )
        decode_sample_qualified = bool(
            enough_output_for_tps and generation_seconds is not None
            and generation_seconds >= MIN_TPS_SECONDS
        )
        end_to_end_tps = (
            completion_tokens / run_seconds
            if end_to_end_sample_qualified else None
        )
        decode_tps = (
            (completion_tokens - 1) / generation_seconds
            if decode_sample_qualified else None
        )
        runtime_fields = {
            key: record.get(key) for key in (
                "runtimeTokensPerSecond", "runtimeTimeToFirstTokenSeconds",
                "runtimeGenerationSeconds", "totalDraftTokens", "acceptedDraftTokens",
                "speculativeAcceptancePercent",
            )
        }
        runtime_stats_reported = any(value is not None for value in runtime_fields.values())
        return {
            "id": record["id"],
            "surfaceId": record["surfaceId"],
            "client": record["client"],
            "surface": record["surface"],
            "protocol": record["protocol"],
            "state": record["state"],
            "queuePosition": position,
            "queuedAt": record["queuedAt"],
            "startedAt": record["startedAt"],
            "firstByteAt": record["firstByteAt"],
            "firstOutputAt": record["firstOutputAt"],
            "endedAt": record["endedAt"],
            "waitSeconds": self._seconds((started or now) - queued),
            "firstByteSeconds": self._seconds(first - started) if first is not None and started is not None else None,
            "firstOutputSeconds": self._seconds(first_output - started) if first_output is not None and started is not None else None,
            "runSeconds": self._seconds(run_seconds),
            "generationSeconds": self._seconds(generation_seconds),
            "bytesRelayed": int(record["bytesRelayed"]),
            "usageReported": usage_reported,
            "promptTokens": prompt_tokens if usage_reported else None,
            "completionTokens": completion_tokens if usage_reported else None,
            "tpsSampleQualified": end_to_end_sample_qualified or decode_sample_qualified,
            "tpsSampleMinimumTokens": MIN_TPS_COMPLETION_TOKENS,
            "endToEndTokensPerSecond": round(end_to_end_tps, 2) if end_to_end_tps is not None else None,
            "decodeTokensPerSecond": round(decode_tps, 2) if decode_tps is not None else None,
            "runtimeStatsSource": "lmstudio-response-stats" if runtime_stats_reported else None,
            "uzuRequestTag": record.get("uzuRequestTag"),
            "runtimeResponseId": record.get("runtimeResponseId"),
            **runtime_fields,
            "statusCode": record["statusCode"],
            "result": record["result"],
            "canCancel": record["state"] in {"queued", "running", "cancelling"},
        }

    def snapshot(self, surfaces: list[dict[str, str]]) -> dict[str, Any]:
        with self.condition:
            active = [
                self._public_locked(self.records[item])
                for item in self.active if item in self.records
            ]
            active.sort(key=lambda item: str(item.get("startedAt") or ""))
            queued = [
                self._public_locked(self.records[item])
                for item in self.queue if item in self.records
            ]
            idle = not active and not queued
            return {
                "version": VERSION,
                "state": "idle" if idle else "busy",
                "lanes": self.lanes,
                "activeCount": len(active),
                "queuedCount": len(queued),
                "active": active,
                "queued": queued,
                "recent": list(reversed(self.recent[-12:])),
                "surfaces": surfaces,
                "startedAt": self.started_at,
                "lastActivityAt": self.last_activity_at,
                "idleSeconds": self._seconds(time.monotonic() - self.last_activity_monotonic) if idle else 0.0,
                "coverage": {
                    "allLauncherSurfaces": True,
                    "externalEngineClients": False,
                    "detail": (
                        "Every Chat, Pi, OpenCode, and Codex surface created by this session uses "
                        "the private relay. Clients that independently know the engine port remain outside it."
                    ),
                },
                "privacy": {
                    "storesPromptText": False,
                    "storesResponseText": False,
                    "storesReasoningText": False,
                    "storesToolData": False,
                    "storesProjectData": False,
                    "persistent": False,
                    "maximumRecentRequests": MAX_RECENT,
                    "readsUsageMetadata": True,
                    "readsRuntimePerformanceMetadata": True,
                    "estimatesTokens": False,
                },
            }


class ResponseMetrics:
    """Extract only bounded timing and runtime usage metadata from a relayed response."""

    def __init__(self, protocol: str, content_type: str, backend: str = "") -> None:
        self.protocol = protocol
        self.backend = backend
        self.streaming = content_type.lower().startswith("text/event-stream")
        self.buffer = bytearray()
        self.complete = bytearray()
        self.overflowed = False
        self.discarding_line = False
        self.output_seen = False
        self.prompt_tokens: int | None = None
        self.completion_tokens: int | None = None
        self.runtime_stats: dict[str, int | float | str] = {}

    @staticmethod
    def _token(value: Any) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None

    def _usage(self, value: Any) -> None:
        if not isinstance(value, dict):
            return
        usage = value.get("usage")
        response = value.get("response")
        if not isinstance(usage, dict) and isinstance(response, dict):
            usage = response.get("usage")
        if not isinstance(usage, dict):
            return
        prompt = self._token(usage.get("prompt_tokens"))
        if prompt is None:
            prompt = self._token(usage.get("input_tokens"))
        completion = self._token(usage.get("completion_tokens"))
        if completion is None:
            completion = self._token(usage.get("output_tokens"))
        if prompt is not None and completion is not None:
            self.prompt_tokens = prompt
            self.completion_tokens = completion

    @staticmethod
    def _number(value: Any, maximum: float, *, positive: bool = False) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        parsed = float(value)
        if not math.isfinite(parsed) or parsed < 0 or parsed > maximum:
            return None
        if positive and parsed <= 0:
            return None
        return parsed

    @staticmethod
    def _integer(value: Any, maximum: int = 2_000_000_000) -> int | None:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
            return None
        return value

    def _performance(self, value: Any) -> None:
        """Read documented LM Studio numeric stats without retaining response data."""
        if self.backend != "lmstudio" or not isinstance(value, dict):
            return
        containers = [value]
        for key in ("response", "result"):
            nested = value.get(key)
            if isinstance(nested, dict):
                containers.append(nested)
        stats = next(
            (container.get("stats") for container in containers
             if isinstance(container.get("stats"), dict)),
            None,
        )
        if not isinstance(stats, dict):
            return
        tps = self._number(stats.get("tokens_per_second"), 1_000_000, positive=True)
        ttft = self._number(
            stats.get("time_to_first_token_seconds", stats.get("time_to_first_token")),
            86_400,
        )
        generation = self._number(
            stats.get("generation_time_seconds", stats.get("generation_time")),
            86_400,
        )
        total_draft = self._integer(stats.get("total_draft_tokens_count"))
        accepted_draft = self._integer(stats.get("accepted_draft_tokens_count"))
        if tps is not None:
            self.runtime_stats["runtimeTokensPerSecond"] = round(tps, 4)
        if ttft is not None:
            self.runtime_stats["runtimeTimeToFirstTokenSeconds"] = round(ttft, 6)
        if generation is not None:
            self.runtime_stats["runtimeGenerationSeconds"] = round(generation, 6)
        if (
            total_draft is not None and accepted_draft is not None
            and total_draft > 0 and accepted_draft <= total_draft
        ):
            self.runtime_stats["totalDraftTokens"] = total_draft
            self.runtime_stats["acceptedDraftTokens"] = accepted_draft
            self.runtime_stats["speculativeAcceptancePercent"] = round(
                accepted_draft / total_draft * 100, 1,
            )

    @staticmethod
    def _nonempty(value: Any) -> bool:
        if isinstance(value, str):
            return bool(value)
        if isinstance(value, list):
            return bool(value)
        if isinstance(value, dict):
            return bool(value)
        return value is not None

    def _inspect(self, value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        if self.backend in {"omlx", "mtplx"}:
            identifier = value.get("id")
            if isinstance(identifier, str) and re.fullmatch(r"chatcmpl-[0-9a-f]{8,32}", identifier):
                self.runtime_stats["runtimeResponseId"] = identifier
        if self.backend == "uzu":
            identifier = value.get("id")
            if isinstance(identifier, str) and re.fullmatch(r"chatcmpl-[0-9a-f]{32}", identifier):
                self.runtime_stats["uzuRequestTag"] = identifier[9:17]
        self._usage(value)
        self._performance(value)
        emitted = False
        if self.protocol == "chat-completions":
            for choice in value.get("choices") or []:
                if not isinstance(choice, dict):
                    continue
                delta = choice.get("delta")
                message = choice.get("message")
                for container in (delta, message, choice):
                    if not isinstance(container, dict):
                        continue
                    if any(self._nonempty(container.get(key)) for key in (
                        "content", "reasoning", "reasoning_content", "thinking", "tool_calls", "text",
                    )):
                        emitted = True
                        break
                if emitted:
                    break
        else:
            event_type = str(value.get("type") or "")
            emitted = bool(
                event_type.endswith(".delta")
                and any(self._nonempty(value.get(key)) for key in (
                    "delta", "text", "arguments", "content",
                ))
            )
        if emitted:
            self.output_seen = True
        return emitted

    def _line(self, line: bytes) -> bool:
        stripped = line.strip()
        if not stripped.startswith(b"data:"):
            return False
        payload = stripped[5:].strip()
        if not payload or payload == b"[DONE]" or len(payload) > MAX_METRICS_BUFFER:
            return False
        try:
            return self._inspect(json.loads(payload))
        except (ValueError, UnicodeError, TypeError):
            return False

    def feed(self, chunk: bytes) -> bool:
        emitted = False
        if self.streaming:
            start = 0
            while start < len(chunk):
                newline = chunk.find(b"\n", start)
                end = len(chunk) if newline < 0 else newline
                if self.discarding_line:
                    # An oversized line may span many reads. Its suffix is
                    # still part of that line, never a new metrics event.
                    self.discarding_line = newline < 0
                elif len(self.buffer) + end - start > MAX_METRICS_BUFFER:
                    self.buffer.clear()
                    self.overflowed = True
                    self.discarding_line = newline < 0
                elif newline < 0:
                    self.buffer.extend(chunk[start:end])
                elif self.buffer:
                    self.buffer.extend(chunk[start:end])
                    emitted = self._line(self.buffer) or emitted
                    self.buffer.clear()
                else:
                    emitted = self._line(chunk[start:end]) or emitted
                start = end + 1
        elif not self.overflowed:
            if len(self.complete) + len(chunk) <= MAX_METRICS_BUFFER:
                self.complete.extend(chunk)
            else:
                self.complete.clear()
                self.overflowed = True
        return emitted

    def finish(self) -> bool:
        emitted = False
        if self.streaming and self.buffer:
            emitted = self._line(bytes(self.buffer))
            self.buffer.clear()
        elif not self.streaming and not self.overflowed and self.complete:
            try:
                emitted = self._inspect(json.loads(self.complete))
            except (ValueError, UnicodeError, TypeError):
                pass
            self.complete.clear()
        return emitted

    def public_usage(self) -> tuple[int | None, int | None]:
        return self.prompt_tokens, self.completion_tokens

    def public_runtime_stats(self) -> dict[str, int | float | str]:
        return dict(self.runtime_stats)


class ChatCompletionLimitGuard:
    """Correct a falsely normal Chat Completions result at the output ceiling.

    Some local servers have reported ``finish_reason=stop`` after emitting exactly
    ``max_tokens``.  Agent clients then treat a reasoning-only, budget-exhausted
    turn as complete.  The relay holds only the small terminal SSE tail until its
    authoritative usage event arrives and relabels that boundary as ``length``.
    Prompt, reasoning, and response text are never retained by this guard.
    """

    def __init__(self, output_limit: int, streaming: bool = True, *, mtplx_memory_recovery: bool = False) -> None:
        self.output_limit = max(1, int(output_limit))
        self.streaming = streaming
        self.mtplx_memory_recovery = mtplx_memory_recovery
        self.memory_refused = False
        # A non-stream completion contains the generated text and terminal
        # usage in one JSON document, so the small SSE-tail allowance is not
        # sufficient.  The handler caps and buffers that document before
        # sending response headers; keep the guard's bound identical.
        self.buffer_limit = MAX_LIMIT_GUARD_BUFFER if streaming else MAX_BODY
        self.pending = bytearray()
        self._event_scanner = EventScanner()
        self.passthrough_event = False
        self.terminal = bytearray()
        self.terminal_started = False
        self.disabled = False

    _split_event = staticmethod(pop_event)

    @staticmethod
    def _event_value(event: bytes) -> dict[str, Any] | None:
        payload_lines = []
        for line in event.splitlines():
            if line.startswith(b"data:"):
                payload_lines.append(line[5:].lstrip())
        payload = b"\n".join(payload_lines).strip()
        if not payload or payload == b"[DONE]" or len(payload) > MAX_METRICS_BUFFER:
            return None
        try:
            value = json.loads(payload)
        except (ValueError, UnicodeError, TypeError):
            return None
        return value if isinstance(value, dict) else None

    @classmethod
    def _has_terminal_stop(cls, event: bytes) -> bool:
        value = cls._event_value(event)
        if value is None:
            return False
        for choice in value.get("choices") or []:
            if not isinstance(choice, dict):
                continue
            reason = choice.get("finish_reason", choice.get("finishReason"))
            if reason is not None:
                return True
        return False

    @classmethod
    def _completion_tokens(cls, tail: bytes) -> int | None:
        buffer = bytearray(tail)
        events: list[bytes] = []
        while buffer:
            event = cls._split_event(buffer)
            if event is None:
                events.append(bytes(buffer))
                break
            events.append(event)
        completion: int | None = None
        for event in events:
            value = cls._event_value(event)
            if value is None:
                continue
            usage = value.get("usage")
            if not isinstance(usage, dict):
                continue
            candidate = usage.get("completion_tokens", usage.get("output_tokens"))
            if isinstance(candidate, int) and not isinstance(candidate, bool) and candidate >= 0:
                completion = candidate
        return completion

    @staticmethod
    def _mark_length(tail: bytes) -> bytes:
        return re.sub(
            rb'("finish_reason"\s*:\s*)"stop"', rb'\1"length"', tail,
        )

    def feed(self, chunk: bytes) -> bytes:
        if not chunk:
            return b""
        if self.disabled:
            return chunk
        if not self.streaming:
            if len(self.pending) + len(chunk) > self.buffer_limit:
                released = bytes(self.pending) + chunk
                self.pending.clear()
                self.disabled = True
                return released
            self.pending.extend(chunk)
            return b""
        if self.terminal_started:
            if len(self.terminal) + len(chunk) > self.buffer_limit:
                released = bytes(self.terminal) + chunk
                self.terminal.clear()
                self.disabled = True
                return released
            self.terminal.extend(chunk)
            return b""

        self.pending.extend(chunk)
        released = bytearray()
        while True:
            event = self._event_scanner.pop(self.pending)
            if event is None:
                break
            if self.passthrough_event:
                # Finish forwarding the oversized event before inspecting the
                # next one. A JSON-looking suffix is not a separate event.
                released.extend(event)
                self.passthrough_event = False
                continue
            if self.mtplx_memory_recovery:
                normalized = normalize_mtplx_compactable_event(event)
                self.memory_refused |= normalized != event
                event = normalized
            if self._has_terminal_stop(event):
                self.terminal_started = True
                self.terminal.extend(event)
                self.terminal.extend(self.pending)
                self.pending.clear()
                break
            released.extend(event)
        if not self.terminal_started and (self.passthrough_event or len(self.pending) > self.buffer_limit):
            # Forward large tool/content events without disabling correction for
            # later usage or memory errors. Keep only enough bytes to recognize
            # either SSE separator (LF LF or CRLF CRLF) across read boundaries.
            self.passthrough_event = True
            released.extend(self._event_scanner.forward_prefix(self.pending))
        return bytes(released)

    def finish_completion(self, payload: bytes | bytearray) -> bytes | bytearray:
        """Correct an already bounded complete response without copying it into pending."""
        try:
            value = json.loads(payload)
        except (ValueError, UnicodeError, TypeError):
            return payload
        usage = value.get("usage") if isinstance(value, dict) else None
        completion = usage.get("completion_tokens", usage.get("output_tokens")) \
            if isinstance(usage, dict) else None
        choices = value.get("choices") if isinstance(value, dict) else None
        if (
            isinstance(completion, int) and not isinstance(completion, bool)
            and completion >= self.output_limit
            and isinstance(choices, list) and len(choices) == 1
        ):
            changed = False
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                if choice.get("finish_reason") == "stop":
                    choice["finish_reason"] = "length"
                    changed = True
                if choice.get("finishReason") == "stop":
                    choice["finishReason"] = "length"
                    changed = True
            if changed:
                return json.dumps(
                    value, separators=(",", ":"), ensure_ascii=False,
                ).encode("utf-8")
        return payload

    def finish(self) -> bytes:
        self._event_scanner.reset()
        if self.disabled:
            return b""
        if not self.streaming:
            payload = bytes(self.pending)
            self.pending.clear()
            return self.finish_completion(payload)
        if not self.terminal_started:
            released = bytes(self.pending)
            self.pending.clear()
            return released
        self.terminal.extend(self.pending)
        self.pending.clear()
        tail = bytes(self.terminal)
        self.terminal.clear()
        completion = self._completion_tokens(tail)
        if completion is not None and completion >= self.output_limit:
            return self._mark_length(tail)
        return tail


PI_SUMMARIZATION_SYSTEM_PROMPT = (
    "You are a context summarization assistant. Your task is to read a conversation "
    "between a user and an AI assistant, then produce a structured summary following "
    "the exact format specified.\n\nDo NOT continue the conversation. Do NOT respond "
    "to any questions in the conversation. ONLY output the structured summary."
)


def transform_chat_request(
    body: bytes, config: dict[str, Any], surface: dict[str, Any] | None = None,
) -> bytes:
    value = json.loads(body)
    allowed_models = [config.get("servedModel"), *config.get("servedModelAliases", [])]
    if not isinstance(value, dict) or value.get("model") not in allowed_models:
        raise ValueError("chat request targets a different model")
    # Pi's native summarizer bypasses before_provider_request. Resolve the
    # same-artifact stable identity at the authenticated relay as well.
    value["model"] = config["servedModel"]
    backend = str(config.get("backend") or "")
    if backend == "omlx":
        validate_omlx_context_is_self_contained(value)
    sampling_source = surface if surface is not None else config
    contract_document = sampling_source.get("samplingContract")
    enforcement = sampling_source.get("samplingEnforcement")
    if contract_document is not None or enforcement is not None:
        if contract_document is None or enforcement is None:
            raise ValueError("sampling contract is incomplete")
        contract_document, enforcement = validated_sampling_policy(
            contract_document, enforcement, "chat-completions",
        )
        value = enforce_sampling_contract(
            value, contract_document, enforcement, "chat-completions",
        )
    # Unit-level callers and older in-memory diagnostics predate the explicit
    # field; a real proxy configuration is still validated strictly at load.
    reasoning = config.get("reasoning", "auto")
    if reasoning not in CHAT_REASONING_LEVELS:
        raise ValueError("invalid reasoning effort")
    llama_client_budgets = {
        key: value.get(key)
        for key in ("reasoning_budget_tokens", "thinking_budget_tokens")
        if key in value
    } if backend == "llamacpp" else {}
    for key in REASONING_OVERRIDE_FIELDS:
        value.pop(key, None)
    if backend == "whallm" and reasoning != "auto":
        if reasoning == "off":
            value.update({"thinking_mode": "chat", "reasoning_effort": "none"})
        else:
            value.update({"thinking_mode": "thinking", "reasoning_effort": reasoning})
    elif backend == "uzu":
        if reasoning not in {"auto", "off"}:
            raise ValueError("Uzu Qwen3.6 reasoning must be auto or off")
        unexpected_sampling = {
            "temperature", "top_p", "top_k", "min_p", "seed",
            "presence_penalty", "frequency_penalty", "repetition_penalty",
        }.intersection(value)
        if unexpected_sampling:
            raise ValueError(
                "This Uzu route is pinned to the packaged model sampling defaults."
            )
        # Qwen3.6 exposes a toggle through Uzu. All named non-disabled levels
        # normalize to Default, so send the one canonical request control.
        value["reasoning_effort"] = "disabled" if reasoning == "off" else "default"
    limit = int(config["outputLimit"])
    requested_limits: list[int] = []
    for key in ("max_tokens", "max_completion_tokens"):
        candidate = value.get(key)
        if candidate is None:
            continue
        if isinstance(candidate, bool) or not isinstance(candidate, int) or candidate <= 0:
            raise ValueError(f"invalid {key}")
        requested_limits.append(candidate)
    effective_limit = min([limit, *requested_limits])
    if backend == "uzu":
        # Uzu implements the newer Chat Completions spelling. Keep exactly one
        # upstream field so two client aliases can never disagree.
        value["max_completion_tokens"] = effective_limit
        value.pop("max_tokens", None)
    else:
        # oMLX, LM Studio, MTPLX and the SSD/native runtimes accept max_tokens.
        # Modern clients may send max_completion_tokens instead (or alongside
        # it), so preserve the strictest visible ceiling and collapse aliases.
        value["max_tokens"] = effective_limit
        value.pop("max_completion_tokens", None)
    if backend == "llamacpp":
        effective = int(value["max_tokens"])
        reserve = 128 if effective >= 512 else max(1, effective // 4)
        maximum_thinking = min(384, max(0, effective - reserve))
        client_budgets: list[int] = []
        for key in ("reasoning_budget_tokens", "thinking_budget_tokens"):
            client_budget = llama_client_budgets.get(key)
            if client_budget is None or client_budget == -1:
                continue
            if (
                isinstance(client_budget, bool) or not isinstance(client_budget, int)
                or client_budget < 0
            ):
                raise ValueError(f"invalid {key}")
            client_budgets.append(client_budget)
        value["reasoning_budget_tokens"] = min(
            [maximum_thinking, *client_budgets]
        )
        value["reasoning_budget_message"] = LLAMACPP_QWEN_REASONING_BUDGET_MESSAGE
        value.pop("thinking_budget_tokens", None)
    if backend == "uzu":
        context_limit = config.get("contextLimit")
        if context_limit not in UZU_CONTEXT_WINDOWS:
            raise ValueError("invalid Uzu context limit")
        messages = value.get("messages")
        if not isinstance(messages, list):
            raise ValueError("invalid Uzu messages")
        # The pinned native runtime counts the rendered prompt with its real
        # tokenizer and reserves the complete response allowance before decode.
        # JSON bytes are NOT tokens: a byte guard rejects ordinary code/history
        # far below the selected context and prevents Pi's own compaction.
    # Native Pi summaries are housekeeping, not a new reasoning turn. Keep
    # them bounded so recovery cannot consume its own remaining KV headroom.
    if backend in {"omlx", "mtplx"} and (surface or {}).get("client") == "pi":
        messages = value.get("messages")
        first = messages[0] if isinstance(messages, list) and messages else {}
        if (
            isinstance(first, dict) and first.get("role") == "system"
            and first.get("content") == PI_SUMMARIZATION_SYSTEM_PROMPT
        ):
            value["max_tokens"] = min(int(value.get("max_tokens") or 4096), 4096)
            value["chat_template_kwargs"] = {"enable_thinking": False}
            if backend == "mtplx":
                value.update({"enable_thinking": False, "reasoning_effort": "none"})
    if value.get("stream") is True:
        stream_options = value.get("stream_options")
        if stream_options is None:
            stream_options = {}
        if not isinstance(stream_options, dict):
            raise ValueError("invalid stream_options")
        value["stream_options"] = {**stream_options, "include_usage": True}
        if backend == "uzu":
            # Uzu always emits terminal usage and ignores stream_options.
            value.pop("stream_options", None)
    messages = value.get("messages")
    prompt_items = len(messages) if isinstance(messages, list) else 0
    return bound_omlx_request_to_context(
        value, config, "max_tokens", prompt_items=prompt_items,
    )


def normalize_uzu_context_error(payload: bytes) -> bytes:
    """Keep native overflow recognisable when an SDK retains only error.message."""
    try:
        value = json.loads(payload)
        error = value.get("error") if isinstance(value, dict) else None
        if isinstance(error, dict) and error.get("code") == "context_length_exceeded":
            error["message"] = "context_length_exceeded: " + str(error.get("message") or "The request exceeds the context window.")
            return json.dumps(value, ensure_ascii=False).encode("utf-8")
    except (ValueError, UnicodeError):
        pass
    return payload


def normalize_omlx_compactable_error(payload: bytes) -> bytes:
    """Let Pi reduce history after the native prompt-memory admission guard.

    Pi's SDK drops structured error codes, so the compaction trigger must
    survive in error.message. Preserve the native code and memory diagnostics;
    unrelated allocation/runtime failures must not become compaction retries.
    """
    try:
        value = json.loads(payload)
        error = value.get("error") if isinstance(value, dict) else None
        if (isinstance(error, dict)
                and error.get("code") == "prefill_memory_exceeded"):
            message = str(error.get("message") or "The prompt exceeds available processing memory.")
            if not message.startswith("context_length_exceeded:"):
                error["message"] = (
                    "context_length_exceeded: Compact the conversation to reduce prompt-processing memory. "
                    + message
                )
            return json.dumps(value, ensure_ascii=False).encode("utf-8")
    except (ValueError, UnicodeError):
        pass
    return payload


def normalize_mtplx_compactable_error(payload: bytes) -> bytes:
    """Recognise admission refusal, never a failed allocation during generation."""
    try:
        value = json.loads(payload)
        error = value.get("error") if isinstance(value, dict) else None
        if not isinstance(error, dict) or error.get("code") != "insufficient_memory":
            return payload
        message = str(error.get("message") or "")
        if not (message.startswith("insufficient memory: this prompt projects ")
                and "refused before prefill" in message):
            return payload
        # Pi recognises the context marker after its SDK discards error codes.
        # The second marker selects the existing bounded retention policy.
        error["message"] = "context_length_exceeded: prefill_memory_exceeded: " + message
        return json.dumps(value, ensure_ascii=False).encode("utf-8")
    except (ValueError, UnicodeError):
        return payload


def normalize_mtplx_compactable_event(event: bytes) -> bytes:
    data = b"\n".join(line[5:].lstrip() for line in event.splitlines() if line.startswith(b"data:"))
    normalized = normalize_mtplx_compactable_error(data)
    if normalized == data:
        return event
    output = []
    written = False
    for line in event.splitlines(keepends=True):
        if line.startswith(b"data:"):
            if not written:
                ending = b"\r\n" if line.endswith(b"\r\n") else b"\n" if line.endswith(b"\n") else b""
                output.append(b"data: " + normalized + ending)
                written = True
        else:
            output.append(line)
    return b"".join(output)


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "LLMLauncherSessionRelay/2"

    def log_message(self, format: str, *args: Any) -> None:
        return

    @property
    def config(self) -> dict[str, Any]:
        return self.server.config  # type: ignore[attr-defined]

    @property
    def scheduler(self) -> RequestScheduler:
        return self.server.scheduler  # type: ignore[attr-defined]

    @property
    def registry(self) -> SurfaceRegistry:
        return self.server.registry  # type: ignore[attr-defined]

    def send_json(self, status: HTTPStatus, value: Any) -> None:
        body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def send_json_error(self, status: HTTPStatus, message: str) -> None:
        self.send_json(status, {"error": {"message": message, "type": "llm_launcher_relay_error"}})

    def control_authorised(self) -> bool:
        expected = f"Bearer {self.config['controlKey']}"
        return hmac.compare_digest(self.headers.get("Authorization", ""), expected)

    def read_json(self, maximum: int) -> dict[str, Any]:
        if self.headers.get("Content-Encoding", "identity").lower() not in {"", "identity"}:
            raise ValueError("compressed request bodies are unsupported")
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("chunked request bodies are unsupported")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("invalid request length") from error
        if not 0 <= length <= maximum:
            raise ValueError("request is too large")
        value = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(value, dict):
            raise ValueError("request body must be an object")
        return value

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if self.path == "/__launcher/status":
            if not self.control_authorised():
                self.send_json_error(HTTPStatus.UNAUTHORIZED, "Invalid controller key")
                return
            status = self.scheduler.snapshot(self.registry.public())
            if self.config.get("backend") == "llamacpp":
                status["reasoningReservePolicy"] = {
                    "version": 1,
                    "finalAnswerReserveTokens": 128,
                    "smallRequestReserve": "25%",
                    "maximumAutomaticThinkingTokens": 384,
                    "preservesStricterClientBudget": True,
                }
            self.send_json(HTTPStatus.OK, status)
            return
        self.forward()

    def do_POST(self) -> None:
        if self.path == "/__launcher/surfaces":
            self.update_surfaces()
            return
        if self.path == "/__launcher/cancel":
            self.cancel_request()
            return
        self.forward()

    def do_DELETE(self) -> None:
        self.forward()

    def update_surfaces(self) -> None:
        if not self.control_authorised():
            self.send_json_error(HTTPStatus.UNAUTHORIZED, "Invalid controller key")
            return
        try:
            payload = self.read_json(MAX_CONTROL_BODY)
            action = str(payload.get("action") or "")
            if action == "register":
                surface = self.registry.register(payload.get("surface"))
                self.send_json(HTTPStatus.OK, {
                    "ok": True,
                    "surface": {"id": surface["id"], "client": surface["client"], "surface": CLIENT_LABELS[surface["client"]]},
                })
                return
            if action == "unregister":
                surface_id = str(payload.get("surfaceId") or "")
                removed = self.registry.unregister(surface_id)
                cancelled = self.scheduler.cancel_surface(surface_id) if removed else 0
                self.send_json(HTTPStatus.OK, {"ok": True, "removed": bool(removed), "cancelled": cancelled})
                return
            if action == "cancel":
                surface_id = str(payload.get("surfaceId") or "")
                known = any(
                    surface["id"] == surface_id
                    for surface in self.registry.public()
                )
                if not known:
                    raise ValueError("unknown surface")
                cancelled = self.scheduler.cancel_surface(surface_id)
                self.send_json(HTTPStatus.ACCEPTED, {
                    "ok": True, "surfaceId": surface_id,
                    "cancelled": cancelled,
                })
                return
            raise ValueError("unknown surface action")
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json_error(HTTPStatus.BAD_REQUEST, str(error))

    def cancel_request(self) -> None:
        if not self.control_authorised():
            self.send_json_error(HTTPStatus.UNAUTHORIZED, "Invalid controller key")
            return
        try:
            payload = self.read_json(MAX_CONTROL_BODY)
            request_id = str(uuid.UUID(str(payload.get("requestId") or "")))
        except (ValueError, AttributeError, json.JSONDecodeError):
            self.send_json_error(HTTPStatus.BAD_REQUEST, "Invalid request id")
            return
        if not self.scheduler.cancel(request_id):
            self.send_json_error(HTTPStatus.NOT_FOUND, "Request is no longer active or queued")
            return
        self.send_json(HTTPStatus.ACCEPTED, {"ok": True, "requestId": request_id})

    @staticmethod
    def allowed_path(path: str) -> bool:
        return bool(re.fullmatch(
            r"/v1/(?:models|chat/completions|responses(?:/[A-Za-z0-9][A-Za-z0-9._:-]{0,255}){0,3})(?:\?[^#]*)?", path,
        ))

    def forward(self) -> None:
        if not self.allowed_path(self.path):
            self.send_json_error(HTTPStatus.NOT_FOUND, "Unsupported local API path")
            return
        surface = self.registry.authenticate(self.headers.get("Authorization", ""))
        if surface is None:
            self.send_json_error(HTTPStatus.UNAUTHORIZED, "Invalid launcher surface key")
            return
        if self.headers.get("Content-Encoding", "identity").lower() not in {"", "identity"}:
            self.send_json_error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Compressed request bodies are unsupported")
            return
        if self.headers.get("Transfer-Encoding"):
            self.send_json_error(HTTPStatus.BAD_REQUEST, "Chunked request bodies are unsupported")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json_error(HTTPStatus.BAD_REQUEST, "Invalid request length")
            return
        if not 0 <= length <= MAX_BODY:
            self.send_json_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request is too large")
            return
        body = self.rfile.read(length) if length else b""
        base_path = self.path.split("?", 1)[0]
        bridge_request: BridgeRequest | None = None
        request_output_limit: int | None = None
        upstream_path = self.path
        if (
            self.config["backend"] == "mtplx"
            and base_path.startswith("/v1/responses")
            and base_path != "/v1/responses"
        ):
            self.send_json_error(
                HTTPStatus.NOT_IMPLEMENTED,
                "MTPLX does not expose Responses compaction or stored-response routes. Codex remote compaction is disabled for this session.",
            )
            return
        generation = self.command == "POST" and base_path in {"/v1/chat/completions", "/v1/responses"}
        if generation:
            try:
                if base_path == "/v1/responses":
                    body = transform_response_request(body, self.config, surface)
                    request_output_limit = int(json.loads(body)["max_output_tokens"])
                    protocol = "responses"
                    if self.config["backend"] == "mtplx":
                        bridge_request = translate_responses_request(body, self.config)
                        body = bridge_request.body
                        upstream_path = "/v1/chat/completions"
                else:
                    body = transform_chat_request(body, self.config, surface)
                    protocol = "chat-completions"
                    transformed = json.loads(body)
                    limit_field = (
                        "max_completion_tokens"
                        if self.config["backend"] == "uzu" else
                        "max_tokens"
                    )
                    request_output_limit = int(transformed[limit_field])
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                self.send_json_error(
                    HTTPStatus.BAD_REQUEST,
                    str(error) or "Invalid bounded generation request",
                )
                return
        else:
            protocol = "control"

        request_id: str | None = None
        if generation:
            try:
                request_id = self.scheduler.begin(surface, protocol)
            except OverflowError as error:
                self.send_json_error(HTTPStatus.TOO_MANY_REQUESTS, str(error))
                return
            if not self.scheduler.await_turn(request_id):
                self.send_json_error(HTTPStatus.CONFLICT, "Request was cancelled while queued")
                return

        headers = {
            key: value for key, value in self.headers.items()
            if key.lower() not in HOP_HEADERS | MUTATED_REPRESENTATION_HEADERS
            | {"authorization", "host", "accept-encoding"}
        }
        headers["Authorization"] = f"Bearer {self.config['upstreamKey']}"
        headers["Accept-Encoding"] = "identity"
        if generation and self.config["backend"] == "mtplx":
            body, headers = mtplx_launcher_request(body, headers)
        if body:
            headers["Content-Length"] = str(len(body))
        headers["Connection"] = "close"
        connection = InterruptibleHTTPConnection(
            "127.0.0.1", self.config["upstreamPort"], timeout=900,
            downstream=self.connection,
        )
        # A connected client that stops consuming output must not occupy an
        # engine lane forever. This is a write timeout, not a prefill deadline.
        self.connection.settimeout(30)
        if request_id:
            self.scheduler.set_connection(request_id, connection)
        response_started = False
        status_code: int | None = None
        result = "completed"
        metrics: ResponseMetrics | None = None
        runtime_identity_sent = False
        try:
            if request_id and self.scheduler.cancelled(request_id):
                raise ConnectionAbortedError("request cancelled")
            connection.request(self.command, upstream_path, body=body or None, headers=headers)
            upstream = connection.getresponse()
            status_code = upstream.status
            if upstream.status >= 400:
                result = "upstream-error"
            upstream_content_type = upstream.getheader("Content-Type") or ""
            is_event_stream = upstream_content_type.lower().startswith("text/event-stream")
            limit_guard: ChatCompletionLimitGuard | ResponsesLimitGuard | None = None
            if request_output_limit is not None and 200 <= upstream.status < 300:
                if protocol == "responses" and bridge_request is None:
                    limit_guard = ResponsesLimitGuard(request_output_limit, is_event_stream)
                elif protocol == "chat-completions":
                    limit_guard = ChatCompletionLimitGuard(
                        request_output_limit, is_event_stream,
                        mtplx_memory_recovery=self.config["backend"] == "mtplx",
                    )
            if request_id:
                metrics = ResponseMetrics(
                    "chat-completions" if bridge_request is not None else protocol,
                    upstream_content_type,
                    self.config["backend"],
                )
            buffered_chat_completion: bytes | bytearray | None = None
            normalized_error = False
            if ((self.config["backend"] in {"uzu", "omlx"} and upstream.status == 400)
                    or (self.config["backend"] == "mtplx" and upstream.status == 507)):
                payload = upstream.read(MAX_BODY + 1)
                if len(payload) > MAX_BODY:
                    raise OSError("Local model server returned an oversized error")
                buffered_chat_completion = (
                    normalize_uzu_context_error(payload) if self.config["backend"] == "uzu"
                    else normalize_mtplx_compactable_error(payload) if self.config["backend"] == "mtplx"
                    else normalize_omlx_compactable_error(payload)
                )
                normalized_error = True
            if (
                isinstance(limit_guard, ChatCompletionLimitGuard)
                and not is_event_stream
            ):
                payload = bytearray()
                while len(payload) <= MAX_BODY:
                    chunk = upstream.read1(16 * 1024)
                    if not chunk:
                        break
                    payload.extend(chunk)
                    if request_id:
                        self.scheduler.first_byte(request_id)
                        self.scheduler.add_bytes(request_id, len(chunk))
                        if metrics is not None and metrics.feed(chunk):
                            self.scheduler.first_output(request_id)
                if len(payload) > MAX_BODY:
                    result = "upstream-error"
                    status_code = int(HTTPStatus.BAD_GATEWAY)
                    response_started = True
                    self.send_json_error(
                        HTTPStatus.BAD_GATEWAY,
                        "Local model server returned an oversized non-stream completion",
                    )
                    return
                buffered_chat_completion = limit_guard.finish_completion(payload)
                del payload
            if bridge_request is not None and 200 <= upstream.status < 300:
                bridge = ChatStreamBridge(bridge_request)
                content_type = (upstream.getheader("Content-Type") or "").lower()
                response_started = True
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Connection", "close")
                if request_id:
                    self.send_header("X-LLM-Launcher-Request-Id", request_id)
                self.end_headers()
                self.wfile.write(bridge.start())
                self.wfile.flush()
                if "text/event-stream" in content_type:
                    while True:
                        chunk = upstream.read1(16 * 1024)
                        if not chunk:
                            break
                        if request_id:
                            self.scheduler.first_byte(request_id)
                            self.scheduler.add_bytes(request_id, len(chunk))
                            if metrics is not None and metrics.feed(chunk):
                                self.scheduler.first_output(request_id)
                        translated = bridge.feed(chunk)
                        if translated:
                            self.wfile.write(translated)
                            self.wfile.flush()
                    translated = bridge.finish()
                else:
                    payload = upstream.read(MAX_BODY + 1)
                    if request_id:
                        self.scheduler.first_byte(request_id)
                        self.scheduler.add_bytes(request_id, len(payload))
                        if metrics is not None and metrics.feed(payload):
                            self.scheduler.first_output(request_id)
                    if len(payload) > MAX_BODY:
                        translated = bridge.failure("MTPLX returned an oversized completion")
                    else:
                        try:
                            translated = bridge.feed_completion(json.loads(payload))
                        except (ValueError, UnicodeError, TypeError):
                            translated = bridge.failure("MTPLX returned invalid completion JSON")
                if translated:
                    self.wfile.write(translated)
                    self.wfile.flush()
                return
            response_started = True
            self.send_response(upstream.status, upstream.reason)
            for key, value in upstream.getheaders():
                if key.lower() not in HOP_HEADERS and not (
                    (limit_guard is not None or normalized_error)
                    and key.lower() in MUTATED_REPRESENTATION_HEADERS
                ):
                    self.send_header(key, value)
            self.send_header("Connection", "close")
            if request_id:
                self.send_header("X-LLM-Launcher-Request-Id", request_id)
            self.end_headers()
            if buffered_chat_completion is not None:
                if buffered_chat_completion:
                    self.wfile.write(buffered_chat_completion)
                    self.wfile.flush()
            else:
                while True:
                    chunk = upstream.read1(16 * 1024)
                    if not chunk:
                        break
                    if request_id:
                        self.scheduler.first_byte(request_id)
                        self.scheduler.add_bytes(request_id, len(chunk))
                        if metrics is not None and metrics.feed(chunk):
                            self.scheduler.first_output(request_id)
                    relayed = limit_guard.feed(chunk) if limit_guard is not None else chunk
                    if isinstance(limit_guard, ChatCompletionLimitGuard) and limit_guard.memory_refused:
                        result = "upstream-error"
                        status_code = 507
                    # Publish correlation metadata as soon as the first SSE
                    # frame arrives. Waiting until EOF hides buffered tool
                    # previews for the entire request.
                    if request_id and metrics is not None and not runtime_identity_sent:
                        response_id = metrics.runtime_stats.get("runtimeResponseId")
                        if response_id:
                            self.scheduler.set_runtime_stats(request_id, {"runtimeResponseId": response_id})
                            runtime_identity_sent = True
                    if relayed:
                        self.wfile.write(relayed)
                        self.wfile.flush()
                if limit_guard is not None:
                    terminal = limit_guard.finish()
                    if terminal:
                        self.wfile.write(terminal)
                        self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            result = (
                "cancelled" if request_id and self.scheduler.cancelled(request_id)
                else "client-disconnected"
            )
        except (ConnectionAbortedError, OSError, http.client.HTTPException) as error:
            cancelled = bool(request_id and self.scheduler.cancelled(request_id))
            result = "cancelled" if cancelled else "upstream-error"
            if not response_started and not self.wfile.closed:
                try:
                    self.send_json_error(
                        HTTPStatus.CONFLICT if cancelled else HTTPStatus.BAD_GATEWAY,
                        "Request cancelled" if cancelled else f"Local model server error: {error}",
                    )
                except OSError:
                    pass
        finally:
            connection.close()
            if request_id:
                if self.scheduler.cancelled(request_id):
                    result = "cancelled"
                if metrics is not None:
                    if metrics.finish():
                        self.scheduler.first_output(request_id)
                    self.scheduler.set_usage(request_id, *metrics.public_usage())
                    self.scheduler.set_runtime_stats(request_id, metrics.public_runtime_stats())
                self.scheduler.finish(request_id, result, status_code)
            self.close_connection = True


def main() -> None:
    if len(sys.argv) != 2:
        fail("expected one private configuration file")
    config = load_config(Path(sys.argv[1]))
    server = ThreadingHTTPServer(("127.0.0.1", config["listenPort"]), ProxyHandler)
    server.daemon_threads = True
    server.config = config  # type: ignore[attr-defined]
    server.registry = SurfaceRegistry(config["surfaces"])  # type: ignore[attr-defined]
    server.scheduler = RequestScheduler(config["lanes"])  # type: ignore[attr-defined]
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
