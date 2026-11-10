"""Bounded semantic Agent Console: transcript, replay, prompt outcomes and queues.

Process ownership, native wire decoding and command scheduling belong to the
controller. This domain receives only a frozen per-console policy and two queue
IO callbacks. It never imports the launcher or reads its global configuration.
"""
from __future__ import annotations

import base64
import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets
import threading
import time
from typing import Any, Callable, Protocol

from agent_console_transport import ConsoleTransport


@dataclass(frozen=True)
class ConsolePolicy:
    console_version: int = 3
    max_buffer: int = 2 * 1024 * 1024
    max_read: int = 128 * 1024
    structured_protocols: frozenset[str] = frozenset({"pi-rpc", "omp-rpc"})
    max_queued_messages: int = 32
    max_queued_bytes: int = 512 * 1024
    max_interactions: int = 8
    timeline_version: int = 1
    max_events: int = 512
    max_replay_items: int = 512
    max_text_bytes: int = 512 * 1024
    max_event_text_bytes: int = 64 * 1024
    max_tracked_items: int = 256
    snapshot_interval: int = 64
    max_transient_text_items: int = 64
    max_json_line_bytes: int = 2 * 1024 * 1024
    history_max_json_line_bytes: int = 16 * 1024 * 1024
    timeline_kinds: frozenset[str] = frozenset({
        "user", "thinking", "answer", "toolCall", "toolResult", "notice", "error", "queue", "summary",
    })

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if name in {"structured_protocols", "timeline_kinds"}:
                if not isinstance(value, frozenset) or any(not isinstance(item, str) or not item for item in value):
                    raise ValueError(f"Console policy {name} must be an immutable set of names")
            elif type(value) is not int or value < 1:
                raise ValueError(f"Console policy {name} must be a positive integer")


DEFAULT_POLICY = ConsolePolicy()


@dataclass(frozen=True)
class QueueIO:
    read: Callable[[Path], dict[str, Any]]
    write: Callable[[Path, Any], None]

    def __post_init__(self) -> None:
        if not callable(self.read) or not callable(self.write):
            raise TypeError("Console queue storage requires explicit read and write callbacks")


def _unconfigured_write(path: Path, value: Any) -> None:
    raise OSError("Agent Console queue storage was not configured")


UNCONFIGURED_QUEUE_IO = QueueIO(read=lambda path: {}, write=_unconfigured_write)


class PlanView(Protocol):
    run_id: str
    client: str
    model: dict[str, Any]
    backend: str
    project: str


class ProcessStatus(Protocol):
    pid: int
    def poll(self) -> int | None: ...


class ProtocolAdapter(Protocol):
    @property
    def can_input(self) -> bool: ...


@dataclass
class AgentConsole:
    """One launcher-owned PTY with a bounded, session-memory-only output buffer."""

    owner_run_id: str
    plan: PlanView
    process: ProcessStatus
    master_fd: int
    cols: int
    rows: int
    state: str = "running"
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    ended_at: str | None = None
    exit_code: int | None = None
    detail: str = "Agent is running in Hub Console."
    base_offset: int = 0
    last_output_at: str | None = None
    output: bytearray = field(default_factory=bytearray, repr=False)
    protocol: str = "terminal"
    transport: ConsoleTransport | None = field(default=None, repr=False)
    omp_adapter: ProtocolAdapter | None = field(default=None, repr=False)
    rpc_failure: str = ""
    rpc_line_buffer: bytearray = field(default_factory=bytearray, repr=False)
    rpc_discarding_oversize_line: bool = False
    rpc_streaming: bool = False
    rpc_prompt_inflight: bool = False
    rpc_pending_messages: int = 0
    rpc_external_pending_messages: int = 0
    rpc_follow_up_queue: list[str] = field(default_factory=list, repr=False)
    rpc_external_queue: list[dict[str, str]] = field(default_factory=list, repr=False)
    rpc_queue_directory: Path | None = field(default=None, repr=False)
    rpc_queue_session: str = field(default="", repr=False)
    rpc_conversation_revision: int = 0
    rpc_queue_saved: str = field(default="", repr=False)
    rpc_queue_identity: str = field(default="", repr=False)
    rpc_queue_token: str = field(default="", repr=False)
    rpc_queue_save_error: str = ""
    rpc_interactions: list[dict[str, Any]] = field(default_factory=list, repr=False)
    rpc_statuses: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)
    rpc_commands: list[dict[str, str]] = field(default_factory=list, repr=False)
    rpc_command_ids: dict[str, str] = field(default_factory=dict, repr=False)
    rpc_resume_session_path: str = field(default="", repr=False)
    rpc_steer_ids: dict[str, str] = field(default_factory=dict, repr=False)
    rpc_compacting: bool = False
    rpc_section: str = ""
    rpc_history_loaded: bool = False
    rpc_last_queue_count: int = -1
    rpc_prompt_id: str = ""
    rpc_prompt_acknowledged: bool = False
    rpc_local_command: bool = False
    rpc_prompt_result_status: str = ""
    rpc_queued_prompt_message: str = field(default="", repr=False)
    rpc_queue_paused: bool = False
    rpc_queue_advance_allowed: bool = False
    rpc_settle_revision: int = 0
    rpc_last_state_probe_at: float = 0.0
    rpc_message_blocks: dict[str, str] = field(default_factory=dict, repr=False)
    rpc_tool_argument_deltas: dict[str, str] = field(default_factory=dict, repr=False)
    rpc_last_assistant: dict[str, Any] = field(default_factory=dict, repr=False)
    rpc_loop_stop_reason: str = ""
    rpc_tool_format_error: str = ""
    rpc_prompt_started: float | None = None
    rpc_prompt_usage: dict[str, int] = field(default_factory=dict, repr=False)
    rpc_prompt_usage_last_message: str = ""
    rpc_timeline_events: list[dict[str, Any]] = field(default_factory=list, repr=False)
    rpc_timeline_items: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict, repr=False)
    rpc_timeline_item_text_bytes: int = 0
    rpc_timeline_revision: int = 0
    rpc_timeline_text_bytes: int = 0
    rpc_timeline_turn: int = 0
    rpc_timeline_user_message: int = 0
    rpc_timeline_assistant_message: int = 0
    rpc_timeline_tool: int = 0
    rpc_timeline_current_message_id: str = ""
    rpc_timeline_skip_current_message: bool = False
    rpc_timeline_message_blocks: dict[str, str] = field(default_factory=dict, repr=False)
    rpc_timeline_delta_counts: dict[str, int] = field(default_factory=dict, repr=False)
    rpc_timeline_seen_message_ids: set[str] = field(default_factory=set, repr=False)
    rpc_timeline_live_fingerprints: set[str] = field(default_factory=set, repr=False)
    rpc_timeline_active_tools: dict[str, str] = field(default_factory=dict, repr=False)
    rpc_timeline_tool_text: dict[str, str] = field(default_factory=dict, repr=False)
    rpc_timeline_tool_status: dict[str, str] = field(default_factory=dict, repr=False)
    rpc_timeline_last_queue_text: str = ""
    rpc_timeline_omitted_items: set[str] = field(default_factory=set, repr=False)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    policy: ConsolePolicy = field(default=DEFAULT_POLICY, repr=False)
    queue_io: QueueIO = field(default=UNCONFIGURED_QUEUE_IO, repr=False)
    surface_label: str | None = None

    @property
    def structured(self) -> bool:
        return self.protocol in self.policy.structured_protocols

    @property
    def agent_label(self) -> str:
        return "oh-my-pi" if self.protocol == "omp-rpc" else "Pi"

    @property
    def rpc_ready(self) -> bool:
        return self.protocol != "omp-rpc" or bool(self.omp_adapter and self.omp_adapter.can_input)

    def append(self, value: bytes) -> None:
        if not value:
            return
        with self.lock:
            self.output.extend(value)
            self.last_output_at = datetime.now(timezone.utc).isoformat()
            overflow = len(self.output) - self.policy.max_buffer
            if overflow > 0:
                del self.output[:overflow]
                self.base_offset += overflow

    def append_timeline(
        self, kind: str, text: Any, *, title: Any = "", item_id: Any = "",
        operation: str = "",
        created_at: str | None = None,
    ) -> dict[str, Any] | None:
        """Append one safe typed event and evict only complete older events."""
        if not self.structured or kind not in self.policy.timeline_kinds:
            return None
        safe_text = safe_agent_timeline_text(
            text, self.policy.max_event_text_bytes,
        )
        safe_title = safe_agent_timeline_text(title, 500).strip()
        safe_item_id = re.sub(
            r"[^A-Za-z0-9:._-]+", "-",
            safe_agent_timeline_text(item_id, 200),
        ).strip("-")
        safe_operation = operation if operation in {"append", "replace"} else ""
        if (
            not safe_text and not safe_title
            and not (safe_item_id and safe_operation == "replace")
        ):
            return None
        with self.lock:
            self.rpc_timeline_revision += 1
            event: dict[str, Any] = {
                "revision": self.rpc_timeline_revision,
                "kind": kind,
                "text": safe_text,
                "createdAt": created_at if created_at is not None else datetime.now(timezone.utc).isoformat(),
            }
            if safe_title:
                event["title"] = safe_title
            if safe_item_id:
                event["itemId"] = safe_item_id
                if safe_operation:
                    event["operation"] = safe_operation
            event_bytes = timeline_event_text_bytes(event)
            # The token journal is a delivery buffer, not the conversation.
            # Keep a separately bounded materialized view so a busy stream
            # cannot erase completed tools/answers from a missed-poll replay.
            mutable = bool(safe_item_id and safe_operation)
            item_key = ("item", safe_item_id) if mutable else ("revision", str(self.rpc_timeline_revision))
            previous = self.rpc_timeline_items.get(item_key)
            item = copy.deepcopy(event)
            if previous is not None:
                item["createdAt"] = previous.get("createdAt", item["createdAt"])
                self.rpc_timeline_item_text_bytes -= timeline_event_text_bytes(previous)
                if safe_operation == "append":
                    item["text"] = str(previous.get("text") or "") + safe_text
                if not safe_title and previous.get("title"):
                    item["title"] = previous["title"]
            item["text"], item["title"] = pi_rpc_timeline_recent_text(
                item["text"], str(item.get("title") or ""),
             policy=self.policy)
            if mutable:
                item["operation"] = "replace"
            self.rpc_timeline_items[item_key] = item
            self.rpc_timeline_item_text_bytes += timeline_event_text_bytes(item)
            while self.rpc_timeline_items and (
                len(self.rpc_timeline_items) > self.policy.max_replay_items
                or self.rpc_timeline_item_text_bytes > self.policy.max_text_bytes
            ):
                oldest_key = next(iter(self.rpc_timeline_items))
                removed_item = self.rpc_timeline_items.pop(oldest_key)
                self.rpc_timeline_item_text_bytes -= timeline_event_text_bytes(removed_item)
            self.rpc_timeline_events.append(event)
            self.rpc_timeline_text_bytes += event_bytes
            while self.rpc_timeline_events and (
                len(self.rpc_timeline_events) > self.policy.max_events
                or self.rpc_timeline_text_bytes > self.policy.max_text_bytes
            ):
                removed = self.rpc_timeline_events.pop(0)
                self.rpc_timeline_text_bytes -= timeline_event_text_bytes(removed)
            return copy.deepcopy(event)

    def timeline_slice(self, revision: Any) -> dict[str, Any]:
        """Deliver journal deltas, or a bounded conversation snapshot on reset."""
        invalid = False
        if revision is None:
            requested = 0
        else:
            try:
                if isinstance(revision, bool):
                    raise ValueError
                requested = int(revision)
                if requested < 0:
                    raise ValueError
            except (TypeError, ValueError):
                requested = 0
                invalid = True
        with self.lock:
            latest = self.rpc_timeline_revision
            base = (
                int(self.rpc_timeline_events[0]["revision"])
                if self.rpc_timeline_events else latest + 1
            )
            reset = invalid or requested < base - 1 or requested > latest
            if reset:
                events = copy.deepcopy(list(self.rpc_timeline_items.values()))
                # Snapshot order follows first appearance, not last update.
                # Rebase only this reset envelope so an old item updated late
                # cannot make the browser discard later chronological items.
                base = latest - len(events) + 1
                for index, event in enumerate(events):
                    event["revision"] = base + index
            else:
                events = copy.deepcopy([event for event in self.rpc_timeline_events
                    if int(event["revision"]) > requested])
            return {
                "timelineVersion": self.policy.timeline_version,
                "timelineBaseRevision": base,
                "timelineRevision": latest,
                "nextTimelineRevision": latest,
                "timelineReset": reset,
                "timelineEvents": events,
            }

    def output_slice(self, offset: Any, timeline_revision: Any = None,
                     *, timeline_version: Any = None) -> dict[str, Any]:
        try:
            requested = int(offset)
        except (TypeError, ValueError):
            requested = self.base_offset
        with self.lock:
            end = self.base_offset + len(self.output)
            # Only omit terminal bytes when the client explicitly understands
            # this semantic format. Old clients and version mismatches keep raw
            # replay, and the retained server buffer is never discarded here.
            semantic_only = (self.structured
                and type(timeline_version) is int
                and timeline_version == self.policy.timeline_version)
            reset = requested < self.base_offset or requested > end
            start = self.base_offset if reset else requested
            relative = start - self.base_offset
            chunk = b"" if semantic_only else bytes(self.output[relative:relative + self.policy.max_read])
            next_offset = end if semantic_only else start + len(chunk)
            result = {
                "version": self.policy.console_version,
                "ownerRunId": self.owner_run_id,
                "surfaceId": self.plan.run_id,
                "startedAt": self.started_at,
                "baseOffset": self.base_offset,
                "bufferBaseOffset": self.base_offset,
                "nextOffset": next_offset,
                "bufferEnd": end,
                "outputRevision": end,
                "reset": reset,
                "data": "" if semantic_only else base64.b64encode(chunk).decode("ascii"),
                "terminalOmitted": semantic_only,
                "state": self.state,
                "exitCode": self.exit_code,
                "lastOutputAt": self.last_output_at,
                "detail": self.detail,
                "protocol": self.protocol,
                "canInput": self.state == "running" and self.process.poll() is None and self.rpc_ready and not self.rpc_failure,
                "conversationId": self.conversation_id(),
                "conversationRevision": self.rpc_conversation_revision,
                "streaming": self.rpc_streaming,
                "pendingMessages": self.rpc_pending_messages,
                "queuePaused": self.rpc_queue_paused,
                "queuedMessages": pi_rpc_visible_queue(self),
                "queueEditingAvailable": True,
                "queueSaveError": self.rpc_queue_save_error,
                "interactions": copy.deepcopy(self.rpc_interactions),
                "extensionStatuses": copy.deepcopy(self.rpc_statuses),
                "commands": copy.deepcopy(self.rpc_commands),
                "compacting": self.rpc_compacting,
            }
            if self.structured:
                result.update(self.timeline_slice(timeline_revision))
            return result

    def conversation_id(self) -> str:
        # Pi conversations survive engine/run IDs. Publish an opaque identity
        # for tab-local draft recovery, never the session's filesystem path.
        if not self.structured or not self.rpc_queue_session:
            return ""
        parts = [str(self.plan.project), self.rpc_queue_session]
        if self.protocol == "omp-rpc":
            parts.insert(0, self.protocol)
        identity = json.dumps(parts, separators=(",", ":"))
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    def public(self) -> dict[str, Any]:
        with self.lock:
            result = {
                "version": self.policy.console_version,
                "conversationId": self.conversation_id(),
                "conversationRevision": self.rpc_conversation_revision,
                "id": self.plan.run_id,
                "surfaceId": self.plan.run_id,
                "ownerRunId": self.owner_run_id,
                "client": self.plan.client,
                "surface": (self.surface_label if self.surface_label is not None else self.plan.client),
                "model": self.plan.model["name"],
                "backend": self.plan.backend,
                "project": self.plan.project,
                "state": self.state,
                "detail": self.detail,
                "pid": self.process.pid if self.process.poll() is None else None,
                "startedAt": self.started_at,
                "endedAt": self.ended_at,
                "exitCode": self.exit_code,
                "cols": self.cols,
                "rows": self.rows,
                "bufferBytes": len(self.output),
                "droppedBytes": self.base_offset,
                "bufferBaseOffset": self.base_offset,
                "bufferEnd": self.base_offset + len(self.output),
                "nextOffset": self.base_offset + len(self.output),
                "outputRevision": self.base_offset + len(self.output),
                "lastOutputAt": self.last_output_at,
                "hasOutput": bool(self.output),
                "protocol": self.protocol,
                "streaming": self.rpc_streaming,
                "pendingMessages": self.rpc_pending_messages,
                "queuePaused": self.rpc_queue_paused,
                "queuedMessages": pi_rpc_visible_queue(self),
                "queueEditingAvailable": True,
                "queueSaveError": self.rpc_queue_save_error,
                "interactions": copy.deepcopy(self.rpc_interactions),
                "persistent": False,
                "commands": copy.deepcopy(self.rpc_commands),
                "canInput": self.state == "running" and self.process.poll() is None and self.rpc_ready and not self.rpc_failure,
                "canStop": self.state in {"starting", "running", "stopping"} and self.process.poll() is None,
                "canRestart": self.state in {"exited", "stopped", "failed"} or self.process.poll() is not None,
                "supportsQueue": self.structured,
                "supportsSteering": self.structured,
                "supportsDirectKeys": not self.structured,
            }
            if self.structured:
                result.update({
                    "timelineVersion": self.policy.timeline_version,
                    "timelineBaseRevision": (
                        int(self.rpc_timeline_events[0]["revision"])
                        if self.rpc_timeline_events else self.rpc_timeline_revision + 1
                    ),
                    "timelineRevision": self.rpc_timeline_revision,
                })
            return result


def safe_agent_transcript_text(value: Any, limit: int = 64 * 1024) -> str:
    """Make model/tool text printable without allowing it to redraw the host UI."""
    text = str(value or "")[:limit].replace("\r\n", "\n").replace("\r", "\n")
    cleaned: list[str] = []
    for character in text:
        if character == "\n":
            cleaned.append("\r\n")
        elif character == "\t" or character >= " ":
            cleaned.append(character)
        elif character == "\x1b":
            cleaned.append("␛")
        else:
            cleaned.append("�")
    return "".join(cleaned)


def safe_agent_ui_text(value: Any, limit: int) -> str:
    """Bound agent-owned dialog copy without passing terminal controls to the UI."""
    return safe_agent_transcript_text(value, limit).replace("\r\n", "\n").strip()


_TIMELINE_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def safe_agent_timeline_text(
    value: Any, limit: int = DEFAULT_POLICY.max_event_text_bytes,
) -> str:
    """Return bounded plain text for JSON UI events, without ANSI/control bytes."""
    raw = str(value or "")[:max(0, limit)].replace("\r\n", "\n").replace("\r", "\n")
    # Ordinary streamed text needs no per-character Python work. Only actual
    # controls invoke the replacement, preserving tabs/newlines and visible ESC.
    cleaned = _TIMELINE_CONTROL_CHARACTERS.sub(
        lambda match: "␛" if match[0] == "\x1b" else "�", raw,
    )
    encoded = cleaned.encode("utf-8")
    if len(encoded) <= max(0, limit):
        return cleaned
    return encoded[:max(0, limit)].decode("utf-8", errors="ignore")


def timeline_event_text_bytes(event: dict[str, Any]) -> int:
    """Count the user-visible text retained by one complete timeline event."""
    return sum(
        len(str(event.get(field) or "").encode("utf-8"))
        for field in ("text", "title")
    )


def pi_rpc_timeline_recent_text(value: Any, title: str = "", *, policy: ConsolePolicy = DEFAULT_POLICY) -> tuple[str, str]:
    """Retain the newest safe UTF-8 text, with a visible bounded-view label."""
    limit = policy.max_event_text_bytes
    raw = str(value or "")
    # At most `limit` Unicode characters can fit in `limit` UTF-8 bytes.
    cleaned = safe_agent_timeline_text(raw[-limit:], limit * 4)
    encoded = cleaned.encode("utf-8")
    omitted = len(raw) > limit or len(encoded) > limit
    recent = encoded[-limit:].decode("utf-8", errors="ignore")
    if omitted and "Earlier text omitted" not in title:
        title = f"{title} · Earlier text omitted" if title else "Earlier text omitted"
    return recent, title


def pi_rpc_remember_timeline_value(values: set[str], value: str, *, policy: ConsolePolicy = DEFAULT_POLICY) -> None:
    values.add(value)
    while len(values) > policy.max_tracked_items:
        values.pop()


def pi_rpc_bound_timeline_mapping(values: dict[str, Any], *, policy: ConsolePolicy = DEFAULT_POLICY) -> None:
    while len(values) > policy.max_tracked_items:
        del values[next(iter(values))]


def bounded_utf8_prefix(value: str, limit: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= max(0, limit):
        return value
    return encoded[:max(0, limit)].decode("utf-8", errors="ignore")


def pi_rpc_store_bounded_text(
    values: dict[str, str], key: str, value: str, *,
    total_bytes: int, max_items: int = DEFAULT_POLICY.max_transient_text_items,
) -> str:
    """Keep one newest text value while bounding the whole transient mapping."""
    bounded = bounded_utf8_prefix(value, total_bytes)
    values.pop(key, None)
    values[key] = bounded
    while len(values) > max(1, max_items):
        del values[next(iter(values))]
    retained_bytes = sum(len(item.encode("utf-8")) for item in values.values())
    while retained_bytes > total_bytes and len(values) > 1:
        oldest = next(iter(values))
        retained_bytes -= len(values[oldest].encode("utf-8"))
        del values[oldest]
    if retained_bytes > total_bytes:
        values[key] = bounded_utf8_prefix(values.get(key, ""), total_bytes)
    return values.get(key, "")


def pi_rpc_current_assistant_prefix(console: AgentConsole) -> str:
    return (
        console.rpc_timeline_current_message_id
        or f"live:{console.rpc_timeline_turn}:assistant:"
        f"{max(1, console.rpc_timeline_assistant_message)}"
    )


def pi_rpc_append_timeline_delta(
    console: AgentConsole, kind: str, value: Any, *,
    title: str, item_id: str,
) -> None:
    """Append one byte-capped delta or a reconstructable periodic snapshot."""
    current = console.rpc_timeline_message_blocks.get(item_id, "")
    delta, delta_title = pi_rpc_timeline_recent_text(value, title, policy=console.policy)
    if not delta:
        return
    recent, recent_title = pi_rpc_timeline_recent_text(current + delta, title, policy=console.policy)
    if delta_title != title:
        recent_title = delta_title
    if recent_title != title:
        pi_rpc_remember_timeline_value(console.rpc_timeline_omitted_items, item_id, policy=console.policy)
    elif item_id in console.rpc_timeline_omitted_items:
        recent_title = f"{title} · Earlier text omitted" if title else "Earlier text omitted"
    updated = pi_rpc_store_bounded_text(
        console.rpc_timeline_message_blocks, item_id, recent,
        total_bytes=console.policy.max_text_bytes,
     max_items=console.policy.max_transient_text_items)
    count = console.rpc_timeline_delta_counts.get(item_id, 0) + 1
    console.rpc_timeline_delta_counts[item_id] = count
    pi_rpc_bound_timeline_mapping(console.rpc_timeline_delta_counts, policy=console.policy)
    interval = max(
        1,
        min(
            console.policy.snapshot_interval,
            max(1, console.policy.max_events // 4),
        ),
    )
    snapshot = count == 1 or count % interval == 0
    console.append_timeline(
        kind, updated if snapshot else delta, title=recent_title, item_id=item_id,
        operation="replace" if snapshot else "append",
    )


def pi_rpc_reconcile_final_block(streamed: str, final: str) -> str:
    """Keep a complete streamed block when Pi's closing snapshot is empty or truncated."""
    if not streamed:
        return final
    if not final or (len(final) < len(streamed) and streamed.startswith(final)):
        return streamed
    return final


def pi_rpc_interaction(event: Any) -> dict[str, Any] | None:
    """Return the small, explicit subset of Pi RPC extension UI that Hub can answer."""
    if not isinstance(event, dict):
        return None
    method = str(event.get("method") or "")
    if method not in {"select", "confirm", "input", "editor"}:
        return None
    request_id = str(event.get("id") or "")
    if not request_id or len(request_id) > 160 or any(ord(char) < 32 for char in request_id):
        return None
    interaction: dict[str, Any] = {
        "id": request_id,
        "method": method,
        "title": safe_agent_ui_text(event.get("title") or "Pi needs input", 500),
    }
    if method == "select":
        interaction["options"] = [
            safe_agent_ui_text(item, 500)
            for item in (event.get("options") if isinstance(event.get("options"), list) else [])[:100]
        ]
        interaction["options"] = [item for item in interaction["options"] if item]
    elif method == "confirm":
        interaction["message"] = safe_agent_ui_text(event.get("message"), 4_000)
    elif method == "input":
        interaction["placeholder"] = safe_agent_ui_text(event.get("placeholder"), 500)
    elif method == "editor":
        interaction["prefill"] = safe_agent_ui_text(event.get("prefill"), 32_000)
    return interaction


def pi_rpc_message_text(message: Any, *, include_thinking: bool = True) -> list[tuple[str, str]]:
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    if isinstance(content, str):
        return [("text", safe_agent_transcript_text(content))]
    blocks: list[tuple[str, str]] = []
    if not isinstance(content, list):
        return blocks
    for block in content:
        if not isinstance(block, dict):
            continue
        kind = str(block.get("type") or "")
        if kind == "text":
            blocks.append(("text", safe_agent_transcript_text(block.get("text"))))
        elif kind == "thinking" and include_thinking:
            blocks.append(("thinking", safe_agent_transcript_text(block.get("thinking"))))
        elif kind == "toolCall":
            name = safe_agent_transcript_text(block.get("name") or "tool", 160)
            arguments = block.get("arguments")
            try:
                detail = json.dumps(arguments, ensure_ascii=False, separators=(",", ":"))
            except (TypeError, ValueError):
                detail = str(arguments or "")
            blocks.append(("tool", f"{name} {safe_agent_transcript_text(detail, 8_192)}".rstrip()))
    return blocks


def pi_rpc_timeline_fingerprint(
    role: str, kind: str, text: str, title: str = "",
) -> str:
    return hashlib.sha256(json.dumps(
        [role, kind, text, title], ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def pi_rpc_timeline_message_key(message: Any, fallback: str) -> tuple[str, bool]:
    raw_identifier = ""
    if isinstance(message, dict):
        raw_identifier = str(message.get("id") or message.get("messageId") or "")
    if raw_identifier:
        digest = hashlib.sha256(raw_identifier.encode("utf-8")).hexdigest()[:24]
        return f"message:{digest}", True
    return fallback, False


def pi_rpc_timeline_message_parts(
    message: Any,
    *, policy: ConsolePolicy = DEFAULT_POLICY,
) -> list[tuple[str, str, str, int]]:
    """Extract typed, plain-text blocks without borrowing terminal formatting."""
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    if isinstance(content, str):
        text, title = pi_rpc_timeline_recent_text(content, policy=policy)
        return [(
            "answer", text, title, 0,
        )]
    if not isinstance(content, list):
        return []
    parts: list[tuple[str, str, str, int]] = []
    for index, block in enumerate(content):
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "")
        if block_type == "text":
            text, title = pi_rpc_timeline_recent_text(block.get("text"), policy=policy)
            parts.append((
                "answer", text, title, index,
            ))
        elif block_type == "thinking":
            text, title = pi_rpc_timeline_recent_text(block.get("thinking"), "Thinking", policy=policy)
            parts.append((
                "thinking", text, title, index,
            ))
        elif block_type == "toolCall":
            title = safe_agent_timeline_text(block.get("name") or "Tool", 160).strip()
            try:
                arguments = json.dumps(
                    block.get("arguments"), ensure_ascii=False, indent=2,
                )
            except (TypeError, ValueError):
                arguments = str(block.get("arguments") or "")
            parts.append((
                "toolCall", safe_agent_timeline_text(arguments), title or "Tool", index,
            ))
    return parts


def pi_rpc_custom_notice(console: AgentConsole, message: dict[str, Any], *, live: bool = False) -> bytes:
    """Render Pi's explicitly visible extension messages as notices, never tools."""
    if message.get("role") != "custom" or message.get("display") is not True:
        return b""
    titles = {
        "launcher-tool-format-recovery": "Retrying tool call",
        "launcher-tool-format-error": "Tool call failed",
        "launcher-progress-check": "Progress check",
        "launcher-loop-stop": "Repetition paused",
    }
    title = titles.get(message.get("customType"), "Pi extension")
    text = "\n".join(text for kind, text, _title, _index
                     in pi_rpc_timeline_message_parts(message, policy=console.policy) if kind == "answer" and text)
    if not text:
        return b""
    if live and console.rpc_streaming and message.get("customType") == "launcher-loop-stop":
        console.rpc_loop_stop_reason = text
        # New Pi defers extension messages until tool results are settled.
        # Reconcile only the latest aborted result in this prompt.
        for item in reversed(list(console.rpc_timeline_items.values())):
            if item.get("kind") == "user":
                break
            if item.get("kind") != "toolResult":
                continue
            if str(item.get("title", "")).startswith("Failed · ") and re.fullmatch(
                r"(?:Operation )?abort(?:ed)?[.!]?", str(item.get("text", "")).strip(), re.I,
            ):
                evidence_id = item["itemId"]
                console.append_timeline("toolResult", item["text"],
                    title=item["title"].replace("Failed · ", "Stopped · ", 1),
                    item_id=evidence_id, operation="replace")
                call_id = evidence_id.removesuffix(":result")
                call = console.rpc_timeline_items.get(("item", call_id))
                if call:
                    console.rpc_timeline_tool_status[call_id] = "Stopped"
                    console.append_timeline("toolCall", call.get("text", ""),
                        title=call.get("title", "").replace("Failed · ", "Stopped · ", 1),
                        item_id=call_id, operation="replace")
            break
    if live and console.rpc_streaming and message.get("customType") == "launcher-tool-format-error":
        console.rpc_tool_format_error = text
        console.rpc_queue_advance_allowed = False
    identity = hashlib.sha256(json.dumps(
        [message.get("timestamp"), message.get("customType"), text],
        ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()[:24]
    key = f"custom:{identity}"
    if key in console.rpc_timeline_seen_message_ids:
        return b""
    pi_rpc_remember_timeline_value(console.rpc_timeline_seen_message_ids, key, policy=console.policy)
    console.append_timeline("notice", text, title=title, item_id=key,
                            operation="replace", created_at=pi_rpc_message_timestamp(message))
    return f"\r\n{title.upper()}\r\n{safe_agent_transcript_text(text)}\r\n".encode("utf-8")


def pi_rpc_add_prompt_usage(totals: dict[str, int], message: dict[str, Any]) -> None:
    """Pi input excludes cache reads/writes; include each exactly once."""
    totals["requests"] = totals.get("requests", 0) + 1
    content = message.get("content")
    totals["tools"] = totals.get("tools", 0) + sum(
        isinstance(block, dict) and block.get("type") == "toolCall"
        for block in (content if isinstance(content, list) else [])
    )
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return
    values = [usage.get("input"), usage.get("output"),
              usage.get("cacheRead", 0), usage.get("cacheWrite", 0)]
    if not all(type(value) is int and 0 <= value <= 10**12 for value in values):
        return
    # Pi initializes usage to zero even when the provider never reports it.
    if not any(values):
        return
    incoming, outgoing, cached, written = values
    totals["reported"] = totals.get("reported", 0) + 1
    totals["input"] = totals.get("input", 0) + incoming + cached + written
    totals["output"] = totals.get("output", 0) + outgoing
    totals["cached"] = totals.get("cached", 0) + cached


def pi_rpc_prompt_summary(totals: dict[str, int], elapsed: float | None = None) -> str:
    parts = []
    if elapsed is not None:
        seconds = max(0, round(elapsed))
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        parts.append(f"{hours}h {minutes}m" if hours else
                     f"{minutes}m {seconds}s" if minutes else f"{seconds}s")
    if totals.get("reported"):
        incoming, outgoing = totals.get("input", 0), totals.get("output", 0)
        qualifier = " reported" if totals["reported"] < totals["requests"] else " total"
        parts.extend([f"{incoming + outgoing:,}{qualifier} tokens",
                      f"{incoming:,} input", f"{outgoing:,} output"])
        if totals.get("cached"):
            parts.append(f"{totals['cached']:,} cached")
        if totals["reported"] < totals["requests"]:
            parts.append("some usage unavailable")
    else:
        parts.append("Token usage unavailable")
    if totals.get("tools"):
        count = totals["tools"]
        parts.append(f"{count:,} tool call{'s' if count != 1 else ''}")
    return " · ".join(parts)


def pi_rpc_saved_history(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Display the selected saved branch, including messages before compaction.

    get_messages is the model's compacted context, not a transcript. Pi owns
    branch selection; follow the leaf from get_entries rather than mixing in
    messages from abandoned branches. Nothing here is sent back to the model.
    """
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise ValueError("Pi did not return saved conversation entries.")
    by_id = {entry.get("id"): entry for entry in entries
             if isinstance(entry, dict) and isinstance(entry.get("id"), str)}
    branch, seen = [], set()
    current = data.get("leafId")
    while current is not None:
        if not isinstance(current, str) or current in seen or current not in by_id:
            raise ValueError("Pi returned an incomplete conversation branch.")
        seen.add(current)
        entry = by_id[current]
        branch.append(entry)
        current = entry.get("parentId")
    messages = []
    for entry in reversed(branch):
        if entry.get("type") == "message" and isinstance(entry.get("message"), dict):
            messages.append({**entry["message"], "id": entry["id"],
                             "timestamp": entry["message"].get("timestamp", entry.get("timestamp"))})
        elif entry.get("type") == "custom_message":
            messages.append({**entry, "role": "custom"})
        elif entry.get("type") in {"compaction", "branch_summary"}:
            messages.append({"role": "compactionSummary", "id": entry["id"],
                             "timestamp": entry.get("timestamp")})
    return messages


def pi_rpc_line_limit(prefix: bytes, *, policy: ConsolePolicy = DEFAULT_POLICY) -> int:
    # Saved sessions can exceed an ordinary stream event, but remain bounded.
    if re.search(rb'"command"\s*:\s*"get_entries"', prefix[:512]):
        return policy.history_max_json_line_bytes
    return policy.max_json_line_bytes


def pi_rpc_record_history(console: AgentConsole, messages: Any) -> None:
    """Seed the typed journal once, skipping live messages already seen by identity/content."""
    if not isinstance(messages, list):
        return
    retained = messages[-200:]
    start_index = max(0, len(messages) - len(retained))
    prompt_usage: dict[str, int] | None = None
    for relative_index, message in enumerate(retained):
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "")
        if role == "custom":
            pi_rpc_custom_notice(console, message)
            continue
        if role == "user":
            prompt_usage = {}
        elif role in {"compactionSummary", "branchSummary"}:
            prompt_usage = None
            key, _ = pi_rpc_timeline_message_key(message, f"history:{start_index + relative_index}")
            console.append_timeline(
                "notice", "Earlier messages were summarized for the model. The saved transcript is retained.",
                title="Context compacted", item_id=f"{key}:compaction", operation="replace",
                created_at=pi_rpc_message_timestamp(message),
            )
        if role not in {"user", "assistant", "toolResult"}:
            continue
        message_key, explicit_id = pi_rpc_timeline_message_key(
            message, f"history:{start_index + relative_index}",
        )
        if explicit_id and message_key in console.rpc_timeline_seen_message_ids:
            prompt_usage = None
            continue
        parts = pi_rpc_timeline_message_parts(message, policy=console.policy)
        for part_kind, text, title, block_index in parts:
            if role == "user":
                kind = "user"
                title = "You"
            elif role == "toolResult":
                kind = "toolResult"
                title = safe_agent_timeline_text(
                    message.get("toolName") or title or "Tool result", 160,
                ).strip()
            else:
                kind = part_kind
            if not text and kind != "toolCall":
                continue
            fingerprint = pi_rpc_timeline_fingerprint(role, kind, text, title)
            if fingerprint in console.rpc_timeline_live_fingerprints:
                prompt_usage = None
                continue
            console.append_timeline(
                kind, text, title=title,
                item_id=f"{message_key}:{kind}:{block_index}", operation="replace",
                created_at=pi_rpc_message_timestamp(message),
            )
        if explicit_id:
            pi_rpc_remember_timeline_value(
                console.rpc_timeline_seen_message_ids, message_key,
             policy=console.policy)
        if role == "assistant" and prompt_usage is not None:
            pi_rpc_add_prompt_usage(prompt_usage, message)
            if message.get("stopReason") == "stop":
                # Pi may persist the terminal extension notice immediately
                # before or after the malformed assistant response.
                format_failed = any(
                    0 <= neighbor < len(retained)
                    and isinstance(retained[neighbor], dict)
                    and retained[neighbor].get("role") == "custom"
                    and retained[neighbor].get("customType") == "launcher-tool-format-error"
                    for neighbor in (relative_index - 1, relative_index + 1)
                )
                console.append_timeline(
                    "summary", pi_rpc_prompt_summary(prompt_usage),
                    title="Tool call failed" if format_failed else "Complete",
                    item_id=f"{message_key}:summary", operation="replace",
                    created_at=pi_rpc_message_timestamp(message),
                )
                prompt_usage = None


def pi_rpc_message_timestamp(message: dict[str, Any]) -> str:
    value = message.get("timestamp")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()
        except (ValueError, OverflowError, OSError):
            pass
    return ""


def pi_rpc_visible_queue(console: AgentConsole) -> list[dict[str, Any]]:
    identity = json.dumps([console.rpc_queue_session, console.rpc_follow_up_queue])
    if identity != console.rpc_queue_identity:
        console.rpc_queue_identity = identity
        console.rpc_queue_token = secrets.token_hex(16)
    return [{"message": message, "kind": "followUp",
             "id": f"{console.rpc_queue_token}:{index}",
             "editable": not (index == 0 and bool(console.rpc_queued_prompt_message))}
            for index, message in enumerate(console.rpc_follow_up_queue)] + copy.deepcopy(console.rpc_external_queue)


def pi_rpc_queue_path(console: AgentConsole) -> Path | None:
    if console.rpc_queue_directory is None or not console.rpc_queue_session:
        return None
    identity = str(console.plan.project) + "\n" + console.rpc_queue_session
    return console.rpc_queue_directory / (hashlib.sha256(identity.encode()).hexdigest() + ".json")


def pi_rpc_save_queue(console: AgentConsole) -> None:
    """Persist changes, not every status poll. Restored queues always start paused."""
    with console.lock:
        pi_rpc_visible_queue(console)
        path = pi_rpc_queue_path(console)
        if path is None:
            return
        record = {"version": 1, "sessionFile": console.rpc_queue_session,
                  "project": str(console.plan.project),
                  "messages": list(console.rpc_follow_up_queue)}
        fingerprint = hashlib.sha256(json.dumps(record, ensure_ascii=False).encode()).hexdigest()
        if fingerprint == console.rpc_queue_saved:
            return
        if not record["messages"] and not path.exists():
            console.rpc_queue_saved = fingerprint
            return
        try:
            console.queue_io.write(path, record)
        except OSError:
            console.rpc_queue_save_error = "Queued messages are visible here, but could not be saved to disk. Keep this launcher open."
        else:
            console.rpc_queue_saved = fingerprint
            console.rpc_queue_save_error = ""


def pi_rpc_bind_queue(console: AgentConsole, session_file: Any) -> None:
    if console.rpc_queue_directory is None or not isinstance(session_file, str) or not session_file:
        return
    if session_file == console.rpc_queue_session:
        return
    # A session switch must not silently send the old conversation's follow-ups.
    if console.rpc_queue_session:
        pi_rpc_save_queue(console)
        if console.rpc_queue_save_error:
            console.rpc_queue_paused = True
            console.rpc_queue_advance_allowed = False
            return
        console.rpc_follow_up_queue.clear()
    console.rpc_queue_session = session_file
    console.rpc_conversation_revision += 1
    console.rpc_queue_saved = ""
    path = pi_rpc_queue_path(console)
    saved = console.queue_io.read(path) if path else {}
    messages = saved.get("messages")
    if (saved.get("version") == 1 and saved.get("sessionFile") == session_file
            and saved.get("project") == str(console.plan.project)
            and isinstance(messages, list) and len(messages) <= console.policy.max_queued_messages
            and all(isinstance(item, str) and item.strip() for item in messages)
            and sum(len(item.encode("utf-8")) for item in messages) <= console.policy.max_queued_bytes):
        console.rpc_follow_up_queue = messages + console.rpc_follow_up_queue
    if console.rpc_follow_up_queue:
        console.rpc_queue_paused = True
        console.rpc_queue_advance_allowed = False
    pi_rpc_save_queue(console)


def pi_rpc_record_queue(console: AgentConsole, text: str, *, title: str = "Queue") -> None:
    pi_rpc_save_queue(console)
    safe_text = safe_agent_timeline_text(text)
    if not safe_text or safe_text == console.rpc_timeline_last_queue_text:
        return
    console.rpc_timeline_last_queue_text = safe_text
    console.append_timeline(
        "queue", safe_text, title=title, item_id="pi:queue", operation="replace",
    )


def pi_rpc_partial_tool_arguments(raw: str) -> Any:
    """Decode streamed string arguments even before their closing quote arrives.

    Pi 0.84 RPC deliberately removes `partial` snapshots, leaving JSON deltas.
    Complete objects use the standard decoder; incomplete common code-tool
    strings retain literal newlines and safely wait for split escape sequences.
    """
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        pass
    result: dict[str, str] = {}
    for match in re.finditer(r'(?<!\\)"(path|file_path|content|oldText|newText|command)"\s*:\s*"', raw):
        value = raw[match.end() - 1:]
        try:
            result[match.group(1)] = json.JSONDecoder().raw_decode(value)[0]
        except ValueError:
            # A trailing partial JSON escape needs its next delta before display.
            for trim in range(min(6, len(value))):
                candidate = value[:len(value) - trim] if trim else value
                try:
                    result[match.group(1)] = json.loads(candidate + '"')
                    break
                except ValueError:
                    continue
    return result or {"input": raw}


def pi_rpc_timeline_tool_key(
    console: AgentConsole, event: Any, *, fallback: str = "", new_call: bool = False,
) -> str:
    raw_identifier = ""
    tool_name = ""
    if isinstance(event, dict):
        tool = event.get("toolCall") if isinstance(event.get("toolCall"), dict) else {}
        raw_identifier = str(
            event.get("toolCallId") or event.get("id")
            or tool.get("id") or tool.get("toolCallId") or ""
        )
        tool_name = str(event.get("toolName") or tool.get("name") or "")
    map_keys: list[str] = []
    if raw_identifier:
        digest = hashlib.sha256(raw_identifier.encode("utf-8")).hexdigest()[:20]
        map_keys.append(f"id:{digest}")
        existing = console.rpc_timeline_active_tools.get(map_keys[0])
        if existing:
            return existing
    if tool_name:
        name_digest = hashlib.sha256(tool_name.encode("utf-8")).hexdigest()[:20]
        name_key = f"name:{name_digest}"
        map_keys.append(name_key)
        if not new_call:
            existing = console.rpc_timeline_active_tools.get(name_key)
            if existing:
                return existing
    if fallback:
        item_id = fallback
    else:
        console.rpc_timeline_tool += 1
        item_id = f"live:{console.rpc_timeline_turn}:tool:{console.rpc_timeline_tool}"
    for map_key in map_keys:
        console.rpc_timeline_active_tools[map_key] = item_id
    if map_keys:
        pi_rpc_bound_timeline_mapping(console.rpc_timeline_active_tools, policy=console.policy)
    return item_id


def pi_rpc_heading(label: str, colour: str) -> bytes:
    return f"\r\n\x1b[1;{colour}m{label}\x1b[0m\r\n".encode("utf-8")


def pi_rpc_render_history(messages: Any) -> bytes:
    if not isinstance(messages, list) or not messages:
        return b""
    output = bytearray()
    output.extend(pi_rpc_heading("SESSION HISTORY", "38;5;75"))
    for message in messages[-200:]:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "")
        if role == "user":
            output.extend(pi_rpc_heading("YOU", "38;5;75"))
        elif role == "assistant":
            pass
        elif role == "toolResult":
            output.extend(pi_rpc_heading(
                f"TOOL RESULT · {safe_agent_transcript_text(message.get('toolName') or 'tool', 160)}",
                "38;5;214",
            ))
        else:
            continue
        for kind, text in pi_rpc_message_text(message):
            if not text:
                continue
            if role == "assistant" and kind == "thinking":
                output.extend(pi_rpc_heading("THINKING", "38;5;141"))
                output.extend(f"\x1b[2;38;5;183m{text}\x1b[0m".encode("utf-8"))
            elif role == "assistant" and kind == "text":
                output.extend(pi_rpc_heading("RESPONSE", "38;5;84"))
                output.extend(text.encode("utf-8"))
            elif kind == "tool":
                output.extend(pi_rpc_heading("TOOL", "38;5;214"))
                output.extend(text.encode("utf-8"))
            else:
                output.extend(text.encode("utf-8"))
    output.extend(pi_rpc_heading("LIVE", "38;5;75"))
    return bytes(output)


def pi_rpc_settled_output(console: AgentConsole, *, local_command: bool = False) -> bytes:
    """Finish one Pi turn and make the queue decision in exactly one place."""
    output = bytearray()
    local_command = local_command or console.rpc_local_command
    console.rpc_local_command = False

    def section(name: str, label: str, colour: str) -> None:
        if console.rpc_section != name:
            output.extend(pi_rpc_heading(label, colour))
            console.rpc_section = name

    console.rpc_streaming = False
    console.rpc_compacting = False
    for item in list(console.rpc_timeline_items.values()):
        if item.get("kind") in {"toolCall", "toolResult"} and re.match(r"^(Writing|Running) · ", item.get("title", "")):
            console.append_timeline(
                item["kind"], item.get("text", ""),
                title=re.sub(r"^(Writing|Running)", "Stopped", item["title"]),
                item_id=item.get("itemId", ""), operation="replace",
            )
    console.rpc_prompt_inflight = False
    console.rpc_prompt_id = ""
    console.rpc_prompt_acknowledged = False
    console.rpc_queued_prompt_message = ""
    if not console.rpc_command_ids:
        console.rpc_interactions.clear()
    last = console.rpc_last_assistant
    terminal_state = "clean" if local_command else str(last.get("terminalState") or "unexpected-eof")
    if console.rpc_prompt_result_status in {"error", "aborted"}:
        terminal_state = "failed" if console.rpc_prompt_result_status == "error" else "aborted"
        console.rpc_queue_advance_allowed = False
    console.rpc_prompt_result_status = ""
    if (console.rpc_loop_stop_reason and terminal_state in {"aborted", "failed"}
            and (last.get("stopReason") == "aborted"
                 or re.search(r"\babort(?:ed)?\b", str(last.get("errorMessage") or ""), re.I))):
        terminal_state = "paused"
        last["terminalState"] = terminal_state
    if console.rpc_tool_format_error and terminal_state == "clean":
        terminal_state = "tool-format-failed"
        last["terminalState"] = terminal_state
        console.rpc_queue_advance_allowed = False
    console.rpc_queue_paused = bool(
        console.rpc_follow_up_queue and not console.rpc_queue_advance_allowed
    )
    if console.rpc_prompt_started is not None:
        title = {"clean": "Complete", "failed": "Failed", "aborted": "Stopped", "paused": "Repetition paused",
                 "limited": "Response limit", "tool-format-failed": "Tool call failed"}.get(terminal_state, "Incomplete")
        if terminal_state == "clean" and not last.get("textCharacters"):
            title = "Incomplete"
        console.append_timeline(
            "summary", pi_rpc_prompt_summary(
                console.rpc_prompt_usage, time.monotonic() - console.rpc_prompt_started,
            ), title=title,
            item_id=f"live:{console.rpc_timeline_turn}:summary", operation="replace",
        )
        console.rpc_prompt_started = None
        console.rpc_prompt_usage.clear()
        console.rpc_prompt_usage_last_message = ""
    if (
        not local_command and terminal_state == "clean"
        and last.get("textCharacters", 0) == 0
        and last.get("toolCalls", 0) == 0
    ):
        notice_text = (
            f"{console.agent_label} finished the turn without a final response. Send continue to resume the task."
            if last.get("thinkingCharacters", 0) > 0 else
            f"{console.agent_label} finished the turn without visible output. Retry the message."
        )
        section("incomplete", "NO FINAL ANSWER", "38;5;214")
        output.extend(notice_text.encode("utf-8"))
        console.append_timeline(
            "notice", notice_text, title="No final answer",
            item_id=f"live:{console.rpc_timeline_turn}:settled", operation="replace",
        )
    elif terminal_state == "unexpected-eof":
        notice_text = (
            f"{console.agent_label} became idle without reporting a clean terminal result. "
            "Any partial output was preserved."
        )
        section("incomplete", "TURN INCOMPLETE", "38;5;214")
        output.extend(
            f"{console.agent_label} became idle without reporting a clean terminal result. Any partial output above was preserved.".encode("utf-8")
        )
        console.append_timeline(
            "notice", notice_text, title="Turn incomplete",
            item_id=f"live:{console.rpc_timeline_turn}:settled", operation="replace",
        )
    if console.rpc_queue_paused:
        section("queue-paused", "QUEUE PAUSED", "38;5;214")
        output.extend(
            b"Queued follow-ups were kept in place because the previous turn did not finish cleanly. "
            b"Send continue to finish the response, or clear the queue."
        )
        pi_rpc_record_queue(
            console,
            "Queued follow-ups were kept because the previous turn did not finish cleanly.",
            title="Queue paused",
        )
    console.rpc_last_assistant = {}
    console.rpc_message_blocks.clear()
    console.rpc_timeline_message_blocks.clear()
    console.rpc_timeline_delta_counts.clear()
    console.rpc_timeline_current_message_id = ""
    console.rpc_timeline_skip_current_message = False
    console.rpc_settle_revision += 1
    return bytes(output)


def pi_rpc_unexpected_eof_output(console: AgentConsole) -> bytes:
    """Fail one active Pi turn closed when its RPC process ends mid-response."""
    if not (console.rpc_streaming or console.rpc_prompt_inflight):
        return b""
    console.rpc_queue_advance_allowed = False
    console.rpc_queue_paused = bool(console.rpc_follow_up_queue)
    output = bytearray(pi_rpc_heading(f"{console.agent_label.upper()} SESSION ENDED", "38;5;203"))
    output.extend(
        (f"The {console.agent_label} process ended before the active turn reported a clean completion. "
         "Any partial thinking, response, and tool output above was preserved.").encode("utf-8")
    )
    console.append_timeline(
        "error",
        f"The {console.agent_label} process ended before the active turn reported a clean completion. "
        "Any partial thinking, response, and tool output was preserved.",
        title=f"{console.agent_label} session ended",
        item_id=f"live:{console.rpc_timeline_turn}:session-ended", operation="replace",
    )
    if console.rpc_queue_paused:
        output.extend(pi_rpc_heading("QUEUE PAUSED", "38;5;214"))
        output.extend(
            b"Queued follow-ups were kept in place and were not sent against the incomplete turn."
        )
        pi_rpc_record_queue(
            console,
            "Queued follow-ups were kept and were not sent against the incomplete turn.",
            title="Queue paused",
        )
    return bytes(output)


def pi_rpc_accept_queued_prompt(console: AgentConsole) -> None:
    """Commit a launcher-queued prompt once Pi proves it accepted the write."""
    message = console.rpc_queued_prompt_message
    accepted = bool(
        message and console.rpc_follow_up_queue
        and console.rpc_follow_up_queue[0] == message
    )
    if accepted:
        console.rpc_follow_up_queue.pop(0)
    console.rpc_queued_prompt_message = ""
    console.rpc_pending_messages = (
        len(console.rpc_follow_up_queue) + console.rpc_external_pending_messages
    )
    if accepted:
        count = console.rpc_pending_messages
        pi_rpc_record_queue(
            console,
            f"{count} message{'s' if count != 1 else ''} waiting"
            if count else "No queued messages",
        )


def pi_rpc_event_output(console: AgentConsole, event: Any) -> bytes:
    """Translate Pi's structured RPC events into a stable append-only transcript."""
    if not isinstance(event, dict):
        return b""
    event_type = str(event.get("type") or "")
    output = bytearray()

    if event_type in {
        "agent_start", "message_start", "message_update", "message_end",
        "tool_execution_start", "tool_execution_update", "tool_execution_end",
    }:
        pi_rpc_accept_queued_prompt(console)

    def section(name: str, label: str, colour: str) -> None:
        if console.rpc_section != name:
            output.extend(pi_rpc_heading(label, colour))
            console.rpc_section = name

    if event_type == "response":
        command = str(event.get("command") or "")
        if command == "compact":
            console.rpc_compacting = False
        response_id = str(event.get("id") or "")
        if command in {"steer", "prompt"} and response_id in console.rpc_steer_ids:
            message = console.rpc_steer_ids.pop(response_id)
            if event.get("success") and not console.rpc_prompt_id:
                console.rpc_prompt_acknowledged = True
            console.append_timeline(
                "notice" if event.get("success") else "error",
                message if event.get("success") else f"{event.get('error') or 'Steering failed'}\n\nUnsent steering: {message}",
                title="Steering accepted · next agent step or new turn" if event.get("success") else "Steering failed",
                item_id=response_id, operation="replace",
            )
            return b""
        if event.get("success") is False:
            error_text = safe_agent_transcript_text(
                event.get("error") or f"{command} failed",
            )
            section("error", f"{console.agent_label.upper()} ERROR", "38;5;203")
            output.extend(error_text.encode("utf-8"))
            console.append_timeline(
                "error", event.get("error") or f"{command} failed",
                title=f"{console.agent_label} error",
                item_id=f"live:{console.rpc_timeline_turn}:error:{command or 'response'}",
                operation="replace",
            )
            if command == "prompt" and (
                not response_id or not console.rpc_prompt_id
                or response_id == console.rpc_prompt_id
            ) and event.get("ompAwaitingPromptResult") is not True:
                queued_message = console.rpc_queued_prompt_message
                if queued_message and (
                    not console.rpc_follow_up_queue
                    or console.rpc_follow_up_queue[0] != queued_message
                ):
                    console.rpc_follow_up_queue.insert(0, queued_message)
                console.rpc_queue_advance_allowed = False
                console.rpc_last_assistant = {
                    "thinkingCharacters": 0,
                    "textCharacters": 0,
                    "toolCalls": 0,
                    "stopReason": "error",
                    "terminalState": "failed",
                    "errorMessage": error_text,
                }
                # Pi emits no agent_settled after rejecting a prompt command.
                # Settle it here so queued follow-ups become visibly paused.
                output.extend(pi_rpc_settled_output(console))
        elif command == "prompt" and (
            not response_id or not console.rpc_prompt_id
            or response_id == console.rpc_prompt_id
        ):
            pi_rpc_accept_queued_prompt(console)
            console.rpc_prompt_acknowledged = True
        elif command == "get_commands":
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            console.rpc_commands = [
                {"name": safe_agent_ui_text(item.get("name"), 160),
                 "description": safe_agent_ui_text(item.get("description"), 500),
                 "source": safe_agent_ui_text(item.get("source"), 32)}
                for item in (data.get("commands") or [])[:500]
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            ]
        elif command in {"get_entries", "get_messages"} and not console.rpc_history_loaded:
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            try:
                messages = pi_rpc_saved_history(data) if command == "get_entries" else data.get("messages")
            except ValueError as error:
                console.append_timeline("error", str(error), title="History unavailable")
                return bytes(output)
            pi_rpc_record_history(console, messages)
            output.extend(pi_rpc_render_history(messages))
            console.rpc_history_loaded = True
            console.rpc_timeline_live_fingerprints.clear()
            console.rpc_section = ""
        elif command == "get_state":
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            pi_rpc_bind_queue(console, data.get("sessionFile"))
            try:
                external_pending = max(0, min(1_000, int(data.get("pendingMessageCount") or 0)))
            except (TypeError, ValueError):
                external_pending = 0
            console.rpc_external_pending_messages = external_pending
            if not external_pending:
                console.rpc_external_queue.clear()
            console.rpc_pending_messages = len(console.rpc_follow_up_queue) + external_pending
            pi_rpc_record_queue(
                console,
                f"{console.rpc_pending_messages} message"
                f"{'s' if console.rpc_pending_messages != 1 else ''} waiting"
                if console.rpc_pending_messages else "No queued messages",
            )
            measured_streaming = data.get("isStreaming") is True
            console.rpc_compacting = data.get("isCompacting") is True
            if console.rpc_compacting:
                pass  # Pi can be compacting while its normal stream is idle.
            elif measured_streaming:
                console.rpc_streaming = True
                console.rpc_prompt_inflight = True
            elif not console.rpc_prompt_inflight or console.rpc_prompt_acknowledged:
                # The state reply is authoritative once Pi accepted the prompt.
                # This repairs a missed agent_settled event without racing prompt
                # preflight, which is not acknowledged until it succeeds.
                was_active = console.rpc_streaming or console.rpc_prompt_inflight
                if was_active:
                    output.extend(pi_rpc_settled_output(console))
                else:
                    console.rpc_streaming = False
                    console.rpc_prompt_inflight = False
                    console.rpc_prompt_id = ""
                    console.rpc_prompt_acknowledged = False
                    if not console.rpc_command_ids:
                        console.rpc_interactions.clear()
        return bytes(output)

    if event_type == "agent_start":
        # Automatic recovery can start another agent loop inside this prompt.
        # Keep its usage and clock until Pi confirms the whole prompt settled.
        if console.rpc_prompt_started is None:
            console.rpc_prompt_started = time.monotonic()
            console.rpc_prompt_usage.clear()
            console.rpc_prompt_usage_last_message = ""
        console.rpc_statuses.pop("tokenSpeed", None)
        console.rpc_timeline_turn += 1
        console.rpc_timeline_user_message = 0
        console.rpc_timeline_omitted_items.clear()
        console.rpc_timeline_assistant_message = 0
        console.rpc_timeline_tool = 0
        console.rpc_timeline_current_message_id = ""
        console.rpc_timeline_skip_current_message = False
        console.rpc_timeline_message_blocks.clear()
        console.rpc_timeline_delta_counts.clear()
        console.rpc_timeline_active_tools.clear()
        console.rpc_timeline_tool_text.clear()
        console.rpc_timeline_tool_status.clear()
        console.rpc_prompt_inflight = True
        console.rpc_streaming = True
        console.rpc_queue_paused = False
        console.rpc_queue_advance_allowed = False
        console.rpc_last_assistant.clear()
        console.rpc_loop_stop_reason = ""
        console.rpc_tool_format_error = ""
        return b""
    if event_type == "extension_error":
        console.append_timeline("error", event.get("error") or f"{console.agent_label} extension failed", title=f"{console.agent_label} command error")
        return pi_rpc_heading(f"{console.agent_label.upper()} COMMAND ERROR", "38;5;203") + safe_agent_transcript_text(event.get("error")).encode("utf-8")
    if event_type == "agent_end":
        console.rpc_section = ""
        if event.get("willRetry") is True:
            console.rpc_streaming = True
            console.rpc_prompt_inflight = True
            console.append_timeline(
                "notice", f"{console.agent_label} is retrying the current turn.",
                title="Retrying",
                item_id=f"live:{console.rpc_timeline_turn}:retry", operation="replace",
            )
        return b""
    if event_type == "agent_settled":
        return pi_rpc_settled_output(console)
    if event_type == "queue_update":
        steering = event.get("steering") if isinstance(event.get("steering"), list) else []
        follow_up = event.get("followUp") if isinstance(event.get("followUp"), list) else []
        console.rpc_external_queue = [
            {"message": item, "kind": kind}
            for kind, messages in (("steer", steering), ("followUp", follow_up))
            for item in messages[:console.policy.max_queued_messages] if isinstance(item, str)
        ]
        count = len(steering) + len(follow_up)
        console.rpc_external_pending_messages = count
        console.rpc_pending_messages = len(console.rpc_follow_up_queue) + count
        total_count = console.rpc_pending_messages
        pi_rpc_record_queue(
            console,
            f"{total_count} message{'s' if total_count != 1 else ''} waiting"
            if total_count else "No queued messages",
        )
        if total_count and total_count != console.rpc_last_queue_count:
            section("queue", "QUEUED", "38;5;214")
            output.extend(
                f"{total_count} message{'s' if total_count != 1 else ''} waiting".encode("utf-8")
            )
        console.rpc_last_queue_count = total_count
        return bytes(output)
    if event_type == "message_start":
        message = event.get("message")
        if isinstance(message, dict) and message.get("role") == "user":
            console.rpc_timeline_user_message += 1
            message_key, explicit_id = pi_rpc_timeline_message_key(
                message, f"live:{console.rpc_timeline_turn}:user:{console.rpc_timeline_user_message}",
            )
            skip_message = explicit_id and message_key in console.rpc_timeline_seen_message_ids
            if explicit_id:
                pi_rpc_remember_timeline_value(
                    console.rpc_timeline_seen_message_ids, message_key,
                 policy=console.policy)
            if not skip_message:
                for _part_kind, text, _title, block_index in pi_rpc_timeline_message_parts(message, policy=console.policy):
                    if not text:
                        continue
                    console.append_timeline(
                        "user", text, title="You",
                        item_id=f"{message_key}:user:{block_index}", operation="replace",
                    )
                    if not console.rpc_history_loaded:
                        pi_rpc_remember_timeline_value(
                            console.rpc_timeline_live_fingerprints,
                            pi_rpc_timeline_fingerprint("user", "user", text, "You"),
                         policy=console.policy)
            section("user", "YOU", "38;5;75")
            for _kind, text in pi_rpc_message_text(message, include_thinking=False):
                output.extend(text.encode("utf-8"))
        elif isinstance(message, dict) and message.get("role") == "assistant":
            console.rpc_timeline_assistant_message += 1
            assistant_fallback = (
                f"live:{console.rpc_timeline_turn}:assistant:"
                f"{console.rpc_timeline_assistant_message}"
            )
            message_key, explicit_id = pi_rpc_timeline_message_key(
                message, assistant_fallback,
            )
            console.rpc_timeline_current_message_id = message_key
            console.rpc_timeline_skip_current_message = bool(
                explicit_id and message_key in console.rpc_timeline_seen_message_ids
            )
            if explicit_id:
                pi_rpc_remember_timeline_value(
                    console.rpc_timeline_seen_message_ids, message_key,
                 policy=console.policy)
            console.rpc_message_blocks.clear()
            console.rpc_tool_argument_deltas.clear()
            console.rpc_timeline_message_blocks.clear()
            console.rpc_timeline_delta_counts.clear()
            console.rpc_last_assistant.clear()
            console.rpc_queue_advance_allowed = False
        return bytes(output)
    if event_type == "message_update":
        update = event.get("assistantMessageEvent")
        if not isinstance(update, dict):
            return b""
        update_type = str(update.get("type") or "")
        if update_type.startswith("thinking_"):
            section("thinking", "THINKING", "38;5;141")
            if update_type == "thinking_delta":
                text = safe_agent_transcript_text(update.get("delta"))
                try:
                    content_index = max(0, min(4_096, int(update.get("contentIndex") or 0)))
                except (TypeError, ValueError):
                    content_index = 0
                key = f"thinking:{content_index}"
                pi_rpc_store_bounded_text(
                    console.rpc_message_blocks, key,
                    console.rpc_message_blocks.get(key, "") + text,
                    total_bytes=console.policy.max_buffer,
                 max_items=console.policy.max_transient_text_items)
                timeline_key = (
                    f"{pi_rpc_current_assistant_prefix(console)}"
                    f":thinking:{content_index}"
                )
                if not console.rpc_timeline_skip_current_message:
                    pi_rpc_append_timeline_delta(
                        console, "thinking", update.get("delta"),
                        title="Thinking", item_id=timeline_key,
                    )
                output.extend(f"\x1b[2;38;5;183m{text}\x1b[0m".encode("utf-8"))
        elif update_type.startswith("text_"):
            section("response", "RESPONSE", "38;5;84")
            if update_type == "text_delta":
                text = safe_agent_transcript_text(update.get("delta"))
                try:
                    content_index = max(0, min(4_096, int(update.get("contentIndex") or 0)))
                except (TypeError, ValueError):
                    content_index = 0
                key = f"text:{content_index}"
                pi_rpc_store_bounded_text(
                    console.rpc_message_blocks, key,
                    console.rpc_message_blocks.get(key, "") + text,
                    total_bytes=console.policy.max_buffer,
                 max_items=console.policy.max_transient_text_items)
                timeline_key = (
                    f"{pi_rpc_current_assistant_prefix(console)}"
                    f":answer:{content_index}"
                )
                if not console.rpc_timeline_skip_current_message:
                    pi_rpc_append_timeline_delta(
                        console, "answer", update.get("delta"),
                        title="", item_id=timeline_key,
                    )
                output.extend(text.encode("utf-8"))
        elif update_type in {"toolcall_start", "toolcall_delta", "toolcall_end"}:
            try:
                content_index = max(0, min(4_096, int(update.get("contentIndex") or 0)))
            except (TypeError, ValueError):
                content_index = 0
            partial = update.get("partial")
            blocks = partial.get("content") if isinstance(partial, dict) else None
            tool = update.get("toolCall")
            if not isinstance(tool, dict):
                tool = blocks[content_index] if isinstance(blocks, list) and content_index < len(blocks) else {}
                if not tool:
                    key = str(content_index)
                    raw = console.rpc_tool_argument_deltas.get(key, "")
                    if update_type == "toolcall_delta":
                        raw += str(update.get("delta") or "")
                        pi_rpc_store_bounded_text(console.rpc_tool_argument_deltas, key, raw,
                                                  total_bytes=console.policy.max_buffer, max_items=console.policy.max_transient_text_items)
                    tool = {"arguments": pi_rpc_partial_tool_arguments(raw)}
            if not isinstance(tool, dict):
                return b""
            section(
                "tool", f"TOOL · {safe_agent_transcript_text(tool.get('name') or 'tool', 160)}",
                "38;5;214",
            )
            try:
                arguments = json.dumps(tool.get("arguments"), ensure_ascii=False, indent=2)
            except (TypeError, ValueError):
                arguments = str(tool.get("arguments") or "")
            if not console.rpc_timeline_skip_current_message:
                try:
                    content_index = max(0, min(4_096, int(update.get("contentIndex") or 0)))
                except (TypeError, ValueError):
                    content_index = 0
                tool_item_id = pi_rpc_timeline_tool_key(
                    console, {"toolCall": tool},
                    fallback=(
                        f"{pi_rpc_current_assistant_prefix(console)}"
                        f":toolCall:{content_index}"
                    ),
                    new_call=True,
                )
                timeline_arguments = safe_agent_timeline_text(
                    arguments, console.policy.max_event_text_bytes,
                )
                pi_rpc_store_bounded_text(
                    console.rpc_timeline_tool_text, tool_item_id,
                    timeline_arguments,
                    total_bytes=console.policy.max_text_bytes,
                 max_items=console.policy.max_transient_text_items)
                console.append_timeline(
                    "toolCall", timeline_arguments,
                    title=f"Writing · {tool.get('name') or 'Tool'}",
                    item_id=tool_item_id,
                    operation="replace",
                )
            if update_type == "toolcall_end":
                output.extend(safe_agent_transcript_text(arguments, 16_384).encode("utf-8"))
        return bytes(output)
    if event_type == "message_end":
        message = event.get("message")
        if isinstance(message, dict) and message.get("role") == "custom":
            return pi_rpc_custom_notice(console, message, live=True)
        if not isinstance(message, dict) or message.get("role") != "assistant":
            return b""
        usage_key = pi_rpc_current_assistant_prefix(console)
        if (console.rpc_prompt_started is not None
                and usage_key != console.rpc_prompt_usage_last_message):
            pi_rpc_add_prompt_usage(console.rpc_prompt_usage, message)
            console.rpc_prompt_usage_last_message = usage_key
        raw_content = message.get("content")
        if isinstance(raw_content, str):
            content = [{"type": "text", "text": raw_content}]
        elif isinstance(raw_content, list):
            content = raw_content
        else:
            content = []
        indexed_content = list(enumerate(content))
        final_indexes = {
            index for index, block in indexed_content if isinstance(block, dict)
        }
        # A closing snapshot can omit a block entirely even though its deltas
        # were delivered. Reconcile those orphaned blocks before clearing the
        # live accumulators so the structured Hub timeline cannot lose output.
        for block_key, streamed in console.rpc_message_blocks.items():
            kind, separator, raw_index = block_key.partition(":")
            if not separator or kind not in {"thinking", "text"}:
                continue
            try:
                index = max(0, min(4_096, int(raw_index)))
            except (TypeError, ValueError):
                continue
            if index in final_indexes:
                continue
            indexed_content.append((index, {
                "type": kind,
                "thinking" if kind == "thinking" else "text": streamed,
            }))
            final_indexes.add(index)
        indexed_content.sort(key=lambda item: item[0])

        thinking_characters = 0
        text_characters = 0
        tool_calls = 0
        for index, block in indexed_content:
            if not isinstance(block, dict):
                continue
            kind = str(block.get("type") or "")
            if kind == "thinking":
                final = pi_rpc_reconcile_final_block(
                    console.rpc_message_blocks.get(f"thinking:{index}", ""),
                    safe_agent_transcript_text(block.get("thinking"), console.policy.max_buffer),
                )
                timeline_kind = "thinking"
                timeline_final, timeline_title = pi_rpc_timeline_recent_text(final, "Thinking", policy=console.policy)
                thinking_characters += len(final)
                label, colour = "RECOVERED THINKING", "38;5;141"
            elif kind == "text":
                final = pi_rpc_reconcile_final_block(
                    console.rpc_message_blocks.get(f"text:{index}", ""),
                    safe_agent_transcript_text(block.get("text"), console.policy.max_buffer),
                )
                timeline_kind = "answer"
                timeline_final, timeline_title = pi_rpc_timeline_recent_text(final, policy=console.policy)
                text_characters += len(final)
                label, colour = "RECOVERED RESPONSE", "38;5;84"
            elif kind == "toolCall":
                tool_calls += 1
                try:
                    tool_arguments = json.dumps(
                        block.get("arguments"), ensure_ascii=False, indent=2,
                    )
                except (TypeError, ValueError):
                    tool_arguments = str(block.get("arguments") or "")
                timeline_tool_arguments = safe_agent_timeline_text(
                    tool_arguments, console.policy.max_event_text_bytes,
                )
                tool_item_id = pi_rpc_timeline_tool_key(
                    console, {"toolCall": block},
                    fallback=(
                        f"{pi_rpc_current_assistant_prefix(console)}"
                        f":toolCall:{index}"
                    ),
                )
                pi_rpc_store_bounded_text(
                    console.rpc_timeline_tool_text, tool_item_id,
                    timeline_tool_arguments,
                    total_bytes=console.policy.max_text_bytes,
                 max_items=console.policy.max_transient_text_items)
                tool_title = safe_agent_timeline_text(
                    block.get("name") or "Tool", 160,
                ).strip() or "Tool"
                tool_status = console.rpc_timeline_tool_status.get(tool_item_id, "")
                console.append_timeline(
                    "toolCall", timeline_tool_arguments,
                    title=f"{tool_status} · {tool_title}" if tool_status else tool_title,
                    item_id=tool_item_id,
                    operation="replace",
                )
                if not console.rpc_history_loaded:
                    pi_rpc_remember_timeline_value(
                        console.rpc_timeline_live_fingerprints,
                        pi_rpc_timeline_fingerprint(
                            "assistant", "toolCall", timeline_tool_arguments,
                            safe_agent_timeline_text(
                                block.get("name") or "Tool", 160,
                            ).strip(),
                        ),
                     policy=console.policy)
                continue
            else:
                continue
            timeline_key = (
                f"{pi_rpc_current_assistant_prefix(console)}"
                f":{timeline_kind}:{index}"
            )
            console.append_timeline(
                timeline_kind, timeline_final, title=timeline_title,
                item_id=timeline_key, operation="replace",
            )
            if timeline_final:
                if not console.rpc_history_loaded:
                    pi_rpc_remember_timeline_value(
                        console.rpc_timeline_live_fingerprints,
                        pi_rpc_timeline_fingerprint(
                            "assistant", timeline_kind, timeline_final, timeline_title,
                        ),
                     policy=console.policy)
            if not final:
                continue
            seen = console.rpc_message_blocks.get(f"{kind}:{index}", "")
            if final == seen:
                continue
            if seen and final.startswith(seen):
                section(kind, "THINKING" if kind == "thinking" else "RESPONSE", colour)
                suffix = final[len(seen):]
                output.extend(
                    f"\x1b[2;38;5;183m{suffix}\x1b[0m".encode("utf-8")
                    if kind == "thinking" else suffix.encode("utf-8")
                )
            else:
                section(f"recovered-{kind}", label, colour)
                output.extend(
                    f"\x1b[2;38;5;183m{final}\x1b[0m".encode("utf-8")
                    if kind == "thinking" else final.encode("utf-8")
                )
        stop_reason = safe_agent_ui_text(message.get("stopReason"), 80)
        normalized_stop_reason = stop_reason.strip().casefold().replace("-", "_").replace(" ", "_")
        terminal_state = {
            "stop": "clean",
            "length": "limited",
            "error": "failed",
            "aborted": "aborted",
        }.get(normalized_stop_reason, "unexpected-eof")
        error_message = safe_agent_transcript_text(message.get("errorMessage"), 2_000)
        if (console.rpc_loop_stop_reason and terminal_state in {"failed", "aborted"}
                and (terminal_state == "aborted" or re.search(r"\babort(?:ed)?\b", error_message, re.I))):
            terminal_state = "paused"
        console.rpc_last_assistant = {
            "thinkingCharacters": thinking_characters,
            "textCharacters": text_characters,
            "toolCalls": tool_calls,
            "stopReason": stop_reason,
            "terminalState": terminal_state,
            "errorMessage": error_message,
        }
        console.rpc_queue_advance_allowed = bool(
            (text_characters > 0 or tool_calls > 0) and terminal_state == "clean"
        )
        console.rpc_message_blocks.clear()
        console.rpc_timeline_message_blocks.clear()
        if terminal_state == "limited":
            section("limit", "RESPONSE LIMIT REACHED", "38;5;214")
            output.extend(
                b"The model used the complete response allowance. Send continue to resume this task, "
                b"or raise Max response before the next hard task."
            )
            console.append_timeline(
                "notice",
                "The model used the complete response allowance. Send continue to resume this task, "
                "or raise Max response before the next hard task.",
                title="Response limit reached",
                item_id=f"live:{console.rpc_timeline_turn}:limit", operation="replace",
            )
        elif terminal_state == "failed":
            section("error", f"{console.agent_label.upper()} ERROR", "38;5;203")
            output.extend((
                error_message
                or f"{console.agent_label} reported that the model turn failed before a clean completion."
            ).encode("utf-8"))
            console.append_timeline(
                "error",
                message.get("errorMessage")
                or f"{console.agent_label} reported that the model turn failed before a clean completion.",
                title=f"{console.agent_label} error",
                item_id=f"live:{console.rpc_timeline_turn}:turn-error", operation="replace",
            )
        elif terminal_state == "aborted":
            section("aborted", "RESPONSE ABORTED", "38;5;214")
            output.extend((
                error_message
                or f"{console.agent_label} reported that the model turn was aborted before a clean completion."
            ).encode("utf-8"))
            console.append_timeline(
                "notice",
                message.get("errorMessage")
                or f"{console.agent_label} reported that the model turn was aborted before a clean completion.",
                title="Response aborted",
                item_id=f"live:{console.rpc_timeline_turn}:aborted", operation="replace",
            )
        return bytes(output)
    if event_type == "tool_execution_start":
        tool_name = event.get("toolName") or "tool"
        tool_item_id = pi_rpc_timeline_tool_key(console, event)
        console.rpc_timeline_tool_status[tool_item_id] = "Running"
        pi_rpc_bound_timeline_mapping(console.rpc_timeline_tool_status, policy=console.policy)
        section(
            "tool-running",
            f"RUNNING · {safe_agent_transcript_text(tool_name, 160)}",
            "38;5;214",
        )
        console.append_timeline(
            "toolCall",
            console.rpc_timeline_tool_text.get(tool_item_id) or "Running",
            title=f"Running · {tool_name}",
            item_id=tool_item_id, operation="replace",
        )
        return bytes(output)
    if event_type == "tool_execution_update":
        tool_item_id = pi_rpc_timeline_tool_key(console, event)
        result = event.get("partialResult")
        if isinstance(result, dict):
            text = "\n".join(text for _kind, text, _title, _index in
                             pi_rpc_timeline_message_parts({"content": result.get("content")}, policy=console.policy) if text)
            console.append_timeline(
                "toolResult", text, title=f"Running · {event.get('toolName') or 'tool'}",
                item_id=f"{tool_item_id}:result", operation="replace",
            )
        return b""
    if event_type == "tool_execution_end":
        tool_name = event.get("toolName") or "tool"
        tool_item_id = pi_rpc_timeline_tool_key(console, event)
        tool_status = "Failed" if event.get("isError") is True else "Completed"
        console.rpc_timeline_tool_status[tool_item_id] = tool_status
        pi_rpc_bound_timeline_mapping(console.rpc_timeline_tool_status, policy=console.policy)
        label = "TOOL FAILED" if event.get("isError") is True else "TOOL RESULT"
        colour = "38;5;203" if event.get("isError") is True else "38;5;109"
        section(
            "tool-result",
            f"{label} · {safe_agent_transcript_text(tool_name, 160)}",
            colour,
        )
        result = event.get("result")
        timeline_result: list[str] = []
        if isinstance(result, dict):
            for _kind, text in pi_rpc_message_text(
                {"content": result.get("content")}, include_thinking=False,
            ):
                output.extend(text.encode("utf-8"))
            timeline_result.extend(
                text for _kind, text, _title, _index
                in pi_rpc_timeline_message_parts({"content": result.get("content")}, policy=console.policy)
                if text
            )
        elif result is not None:
            timeline_result.append(safe_agent_timeline_text(result))
        result_text = "\n".join(timeline_result).strip()
        guard_aborted = bool(event.get("isError") is True and (
            (console.rpc_loop_stop_reason and re.search(r"\babort(?:ed)?\b", result_text, re.I))
            # Pi 0.85 returns the extension's block reason before delivering
            # its deferred notice, rather than returning an abort error.
            or result_text.startswith("Paused: the model requested the same tool again after three identical successful results.")
        ))
        if guard_aborted:
            tool_status = "Stopped"
            console.rpc_timeline_tool_status[tool_item_id] = tool_status
        console.append_timeline(
            "toolCall",
            console.rpc_timeline_tool_text.get(tool_item_id) or tool_status,
            title=f"{tool_status} · {tool_name}",
            item_id=tool_item_id, operation="replace",
        )
        console.append_timeline(
            "toolResult",
            result_text or ("Failed" if event.get("isError") is True else "Completed"),
            title=f"{'Stopped' if guard_aborted else 'Failed' if event.get('isError') is True else 'Result'} · {tool_name}",
            item_id=f"{tool_item_id}:result",
            operation="replace",
        )
        if result_text and not console.rpc_history_loaded:
            pi_rpc_remember_timeline_value(
                console.rpc_timeline_live_fingerprints,
                pi_rpc_timeline_fingerprint(
                    "toolResult", "toolResult", result_text,
                    safe_agent_timeline_text(tool_name, 160).strip(),
                ),
             policy=console.policy)
        return bytes(output)
    if event_type == "compaction_start":
        console.rpc_compacting = True
        # A recoverable overflow is progress once Pi starts compacting.
        if event.get("reason") == "overflow":
            error_key = f"live:{console.rpc_timeline_turn}:turn-error"
            console.append_timeline("error", "", item_id=error_key, operation="replace")
        section("status", "COMPACTING CONTEXT", "38;5;75")
        console.append_timeline(
            "notice", f"{console.agent_label} is compacting the conversation context.",
            title="Compacting context",
            item_id=f"live:{console.rpc_timeline_turn}:compaction", operation="replace",
        )
        return bytes(output)
    if event_type == "compaction_end":
        console.rpc_compacting = False
        failed = event.get("errorMessage")
        aborted = event.get("aborted") is True
        console.append_timeline(
            "error" if failed else "notice",
            failed or ("Context compaction cancelled." if aborted else
                       "Context compacted. Continuing…" if event.get("willRetry") else
                       "Context compaction finished."),
            title="Compaction failed" if failed else "Compaction cancelled" if aborted else "Context ready",
            item_id=f"live:{console.rpc_timeline_turn}:compaction", operation="replace",
        )
        return bytes(output)
    if event_type == "auto_retry_start":
        section("status", "RETRYING", "38;5;214")
        output.extend(safe_agent_transcript_text(event.get("errorMessage"), 2_000).encode("utf-8"))
        console.append_timeline(
            "notice", event.get("errorMessage") or f"{console.agent_label} is retrying the current turn.",
            title="Retrying",
            item_id=f"live:{console.rpc_timeline_turn}:retry", operation="replace",
        )
        return bytes(output)
    if event_type == "auto_retry_end":
        console.append_timeline(
            "notice", f"{console.agent_label} finished the retry attempt.",
            title="Retry finished",
            item_id=f"live:{console.rpc_timeline_turn}:retry", operation="replace",
        )
        return bytes(output)
    if event_type == "extension_ui_request":
        # These are fire-and-forget TUI presentation updates, often emitted
        # once per token. They are neither notifications nor input requests.
        # Recording them fills the bounded journal and evicts real thinking.
        if event.get("method") == "setStatus":
            key = safe_agent_ui_text(event.get("statusKey"), 128)
            if key:
                raw = event.get("statusText")
                if raw is None or raw == "":
                    console.rpc_statuses.pop(key, None)
                else:
                    # Pi themes emit ANSI colour. Keep plain status text outside
                    # the transcript, replacing each extension's previous value.
                    limit = 24000 if key == "launcher.customUI" else 2048
                    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(raw)[:limit * 4])
                    console.rpc_statuses[key] = {
                        "text": safe_agent_ui_text(text, limit).replace("\u200b", ""),
                        "updatedAt": datetime.now(timezone.utc).isoformat(),
                    }
                    while len(console.rpc_statuses) > 32:
                        del console.rpc_statuses[next(iter(console.rpc_statuses))]
            return b""
        if event.get("method") in {"setWidget", "setTitle", "set_editor_text"}:
            return b""
        interaction = pi_rpc_interaction(event)
        if interaction is not None and interaction["title"] == "__launcher_custom_ui__":
            console.rpc_interactions = [item for item in console.rpc_interactions
                if item.get("title") != "__launcher_custom_ui__"]
            console.rpc_interactions.append(interaction)
            return b""
        section(
            "action" if interaction is not None else "notice",
            f"{console.agent_label.upper()} NEEDS INPUT" if interaction is not None else f"{console.agent_label.upper()} NOTICE",
            "38;5;214",
        )
        title = event.get("title") or event.get("message") or event.get("method") or "Extension request"
        output.extend(safe_agent_transcript_text(title, 2_000).encode("utf-8"))
        console.append_timeline(
            "notice", title,
            title=f"{console.agent_label} needs input" if interaction is not None else f"{console.agent_label} notice",
            item_id=(
                f"interaction:{hashlib.sha256(str(event.get('id') or '').encode('utf-8')).hexdigest()[:20]}"
                if event.get("id") else f"live:{console.rpc_timeline_turn}:interaction"
            ),
            operation="replace",
        )
        if interaction is not None:
            console.rpc_interactions = [
                item for item in console.rpc_interactions
                if item.get("id") != interaction["id"]
            ]
            console.rpc_interactions.append(interaction)
            if len(console.rpc_interactions) > console.policy.max_interactions:
                del console.rpc_interactions[:-console.policy.max_interactions]
    return bytes(output)
