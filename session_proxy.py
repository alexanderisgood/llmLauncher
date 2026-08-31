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
import stat
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from codex_proxy import ResponsesLimitGuard, transform_response_request
from responses_bridge import BridgeRequest, ChatStreamBridge, translate_responses_request


VERSION = 2
MAX_BODY = 128 * 1024 * 1024
MAX_CONTROL_BODY = 64 * 1024
MAX_RECENT = 32
MAX_QUEUE = 64
MAX_METRICS_BUFFER = 1024 * 1024
MAX_LIMIT_GUARD_BUFFER = 256 * 1024
CLIENTS = {"chat", "pi", "opencode", "codex"}
CLIENT_LABELS = {"chat": "Chat", "pi": "Pi", "opencode": "OpenCode", "codex": "Codex"}
HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fail(message: str) -> None:
    print(f"LLM Launcher session relay: {message}", file=sys.stderr)
    raise SystemExit(2)


def _valid_secret(value: Any) -> bool:
    return isinstance(value, str) and 16 <= len(value) <= 512 and "\0" not in value


def _valid_surface(value: Any) -> dict[str, str]:
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
    return {"id": parsed, "client": client, "key": str(key)}


def load_config(path: Path) -> dict[str, Any]:
    state_root = (
        Path.home() / "Library" / "Application Support" / "LLM Launcher" / "runs"
    ).resolve()
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(state_root)
    except ValueError:
        fail("configuration is outside the launcher state folder")
    info = resolved.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        fail("configuration permissions are not private")
    try:
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as error:
        fail(f"cannot read configuration: {error}")
    if not isinstance(value, dict):
        fail("configuration is not an object")
    for key in ("listenPort", "upstreamPort", "lanes", "outputLimit"):
        if isinstance(value.get(key), bool) or not isinstance(value.get(key), int):
            fail(f"invalid {key}")
    if not 1_024 <= value["listenPort"] <= 65_535 or not 1_024 <= value["upstreamPort"] <= 65_535:
        fail("invalid port")
    if value["listenPort"] == value["upstreamPort"]:
        fail("relay and engine ports must differ")
    if not 1 <= value["lanes"] <= 16 or not 1_024 <= value["outputLimit"] <= 2_000_000:
        fail("invalid scheduler or output limit")
    if value.get("backend") not in {"omlx", "lmstudio", "mtplx", "freetoken"}:
        fail("unsupported backend")
    if not all(_valid_secret(value.get(key)) for key in ("controlKey", "upstreamKey")):
        fail("invalid relay secret")
    if not isinstance(value.get("servedModel"), str) or not value["servedModel"]:
        fail("invalid served model")
    surfaces = value.get("surfaces")
    if not isinstance(surfaces, list) or len(surfaces) != 1:
        fail("one primary surface is required")
    try:
        value["surfaces"] = [_valid_surface(surfaces[0])]
    except ValueError as error:
        fail(str(error))
    return value


class SurfaceRegistry:
    def __init__(self, surfaces: list[dict[str, str]]) -> None:
        self.lock = threading.RLock()
        self.by_id: dict[str, dict[str, str]] = {}
        for surface in surfaces:
            self.register(surface)

    def register(self, value: Any) -> dict[str, str]:
        surface = _valid_surface(value)
        with self.lock:
            for current in self.by_id.values():
                if current["key"] == surface["key"] and current["id"] != surface["id"]:
                    raise ValueError("surface key is already registered")
            self.by_id[surface["id"]] = surface
        return dict(surface)

    def unregister(self, surface_id: Any) -> dict[str, str] | None:
        value = str(surface_id or "")
        with self.lock:
            surface = self.by_id.pop(value, None)
            return dict(surface) if surface else None

    def authenticate(self, authorization: str) -> dict[str, str] | None:
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

    def set_connection(self, request_id: str, connection: http.client.HTTPConnection) -> None:
        close_now = False
        with self.condition:
            record = self.records.get(request_id)
            if record is None or record["cancel"].is_set():
                close_now = True
            else:
                record["connection"] = connection
        if close_now:
            connection.close()

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
        """Attach only allowlisted numeric engine facts to one relay request."""
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
        connection: http.client.HTTPConnection | None = None
        with self.condition:
            record = self.records.get(str(request_id or ""))
            if record is None:
                return False
            record["cancel"].set()
            record["state"] = "cancelling"
            connection = record.get("connection")
            self.condition.notify_all()
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass
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
        end_to_end_tps = (
            completion_tokens / run_seconds
            if usage_reported and run_seconds is not None and run_seconds > 0 else None
        )
        decode_tps = (
            (completion_tokens - 1) / generation_seconds
            if usage_reported and completion_tokens > 1
            and generation_seconds is not None and generation_seconds > 0 else None
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
            "endToEndTokensPerSecond": round(end_to_end_tps, 2) if end_to_end_tps is not None else None,
            "decodeTokensPerSecond": round(decode_tps, 2) if decode_tps is not None else None,
            "runtimeStatsSource": "lmstudio-response-stats" if runtime_stats_reported else None,
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
        self.output_seen = False
        self.prompt_tokens: int | None = None
        self.completion_tokens: int | None = None
        self.runtime_stats: dict[str, int | float] = {}

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
                        "content", "reasoning", "reasoning_content", "tool_calls", "text",
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
            self.buffer.extend(chunk)
            if len(self.buffer) > MAX_METRICS_BUFFER:
                newline = self.buffer.rfind(b"\n")
                if newline < 0:
                    self.buffer.clear()
                else:
                    del self.buffer[:newline + 1]
                self.overflowed = True
            while b"\n" in self.buffer:
                line, _, remainder = self.buffer.partition(b"\n")
                self.buffer = bytearray(remainder)
                emitted = self._line(line) or emitted
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

    def public_runtime_stats(self) -> dict[str, int | float]:
        return dict(self.runtime_stats)


class ChatCompletionLimitGuard:
    """Correct a falsely normal terminal SSE event at the exact output ceiling.

    Some local servers have reported ``finish_reason=stop`` after emitting exactly
    ``max_tokens``.  Agent clients then treat a reasoning-only, budget-exhausted
    turn as complete.  The relay holds only the small terminal SSE tail until its
    authoritative usage event arrives and relabels that boundary as ``length``.
    Prompt, reasoning, and response text are never retained by this guard.
    """

    def __init__(self, output_limit: int) -> None:
        self.output_limit = max(1, int(output_limit))
        self.pending = bytearray()
        self.terminal = bytearray()
        self.terminal_started = False
        self.disabled = False

    @staticmethod
    def _split_event(buffer: bytearray) -> bytes | None:
        endings = []
        for separator in (b"\n\n", b"\r\n\r\n"):
            index = buffer.find(separator)
            if index >= 0:
                endings.append((index + len(separator), index))
        if not endings:
            return None
        end, _index = min(endings, key=lambda item: item[1])
        event = bytes(buffer[:end])
        del buffer[:end]
        return event

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
        if self.terminal_started:
            if len(self.terminal) + len(chunk) > MAX_LIMIT_GUARD_BUFFER:
                released = bytes(self.terminal) + chunk
                self.terminal.clear()
                self.disabled = True
                return released
            self.terminal.extend(chunk)
            return b""

        self.pending.extend(chunk)
        released = bytearray()
        while True:
            event = self._split_event(self.pending)
            if event is None:
                break
            if self._has_terminal_stop(event):
                self.terminal_started = True
                self.terminal.extend(event)
                self.terminal.extend(self.pending)
                self.pending.clear()
                break
            released.extend(event)
        if not self.terminal_started and len(self.pending) > MAX_LIMIT_GUARD_BUFFER:
            released.extend(self.pending)
            self.pending.clear()
            self.disabled = True
        return bytes(released)

    def finish(self) -> bytes:
        if self.disabled:
            return b""
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


def transform_chat_request(body: bytes, config: dict[str, Any]) -> bytes:
    value = json.loads(body)
    if not isinstance(value, dict) or value.get("model") != config.get("servedModel"):
        raise ValueError("chat request targets a different model")
    limit = int(config["outputLimit"])
    requested = value.get("max_tokens")
    if requested is None:
        value["max_tokens"] = limit
    elif isinstance(requested, bool) or not isinstance(requested, int) or requested <= 0:
        raise ValueError("invalid max_tokens")
    else:
        value["max_tokens"] = min(requested, limit)
    if value.get("stream") is True:
        stream_options = value.get("stream_options")
        if stream_options is None:
            stream_options = {}
        if not isinstance(stream_options, dict):
            raise ValueError("invalid stream_options")
        value["stream_options"] = {**stream_options, "include_usage": True}
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


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
            self.send_json(HTTPStatus.OK, self.scheduler.snapshot(self.registry.public()))
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
                    body = transform_response_request(body, self.config)
                    request_output_limit = int(json.loads(body)["max_output_tokens"])
                    protocol = "responses"
                    if self.config["backend"] == "mtplx":
                        bridge_request = translate_responses_request(body, self.config)
                        body = bridge_request.body
                        upstream_path = "/v1/chat/completions"
                else:
                    body = transform_chat_request(body, self.config)
                    protocol = "chat-completions"
                    request_output_limit = int(json.loads(body)["max_tokens"])
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
            if key.lower() not in HOP_HEADERS | {"authorization", "host", "content-length", "accept-encoding"}
        }
        headers["Authorization"] = f"Bearer {self.config['upstreamKey']}"
        headers["Accept-Encoding"] = "identity"
        if body:
            headers["Content-Length"] = str(len(body))
        headers["Connection"] = "close"
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.config["upstreamPort"], timeout=900,
        )
        if request_id:
            self.scheduler.set_connection(request_id, connection)
        response_started = False
        status_code: int | None = None
        result = "completed"
        metrics: ResponseMetrics | None = None
        try:
            if request_id and self.scheduler.cancelled(request_id):
                raise ConnectionAbortedError("request cancelled")
            connection.request(self.command, upstream_path, body=body or None, headers=headers)
            upstream = connection.getresponse()
            status_code = upstream.status
            upstream_content_type = upstream.getheader("Content-Type") or ""
            is_event_stream = upstream_content_type.lower().startswith("text/event-stream")
            limit_guard: ChatCompletionLimitGuard | ResponsesLimitGuard | None = None
            if request_output_limit is not None and 200 <= upstream.status < 300:
                if protocol == "responses" and bridge_request is None:
                    limit_guard = ResponsesLimitGuard(request_output_limit, is_event_stream)
                elif protocol == "chat-completions" and is_event_stream:
                    limit_guard = ChatCompletionLimitGuard(request_output_limit)
            if request_id:
                metrics = ResponseMetrics(
                    "chat-completions" if bridge_request is not None else protocol,
                    upstream_content_type,
                    self.config["backend"],
                )
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
                    limit_guard is not None and key.lower() == "content-length"
                ):
                    self.send_header(key, value)
            self.send_header("Connection", "close")
            if request_id:
                self.send_header("X-LLM-Launcher-Request-Id", request_id)
            self.end_headers()
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
                if relayed:
                    self.wfile.write(relayed)
                    self.wfile.flush()
            if limit_guard is not None:
                terminal = limit_guard.finish()
                if terminal:
                    self.wfile.write(terminal)
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            result = "client-disconnected"
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
