"""Bounded OMP v18.6.3 stdout framing and explicit Pi-semantic adaptation.

Contract: https://github.com/can1357/oh-my-pi/blob/v18.6.3/docs/rpc.md
Reference: rpc-frame.ts, rpc-prompt-results.ts and rpc-session-settle.ts at
that tag. OMP stdin is ordinary JSONL in both versions; rpc_chunk is stdout
only. This module owns neither processes, model routes nor Console UI state.

One Adapter belongs to one process. Call receive_line with complete physical
lines (including newline), send its commands through encode_command, and pass
its events to the semantic consumer in order. Prompt-result/local-completion
controls are explicit: they must not become invented assistant messages.
ProtocolError invalidates the adapter; discard it with its owned connection.
"""
from __future__ import annotations

import base64
from collections import deque
from dataclasses import dataclass, field
import json
import math
from typing import Any, Iterator


MAX_RPC_FRAME_BYTES = 1024 * 1024
MAX_RPC_REASSEMBLED_BYTES = 64 * 1024 * 1024
RPC_CHUNK_PAYLOAD_BYTES = 256 * 1024
DEFAULT_COMMAND_BYTES = 64 * 1024
MAX_COMMAND_OUTPUT_BYTES = 64 * 1024
MAX_PENDING_COMMANDS = 256
MAX_PENDING_PROMPTS = 32
_CONTROL_RESPONSES = frozenset({"extension_ui_response", "host_tool_result", "host_tool_update", "host_uri_result"})


class ProtocolError(ValueError):
    """Invalid/incompatible wire data; the connection must no longer be used."""


@dataclass
class Result:
    events: list[dict[str, Any]] = field(default_factory=list)
    commands: list[dict[str, Any]] = field(default_factory=list)


def _integer(value: Any) -> bool:
    return type(value) is int and abs(value) <= (1 << 53) - 1


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ProtocolError("Duplicate RPC object key")
        value[key] = item
    return value


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ProtocolError("Non-finite RPC number")
    return parsed


def _load(data: bytes) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8", errors="strict"), object_pairs_hook=_pairs, parse_float=_finite_float,
                           parse_constant=lambda _: (_ for _ in ()).throw(ProtocolError("Non-finite RPC number")))
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ProtocolError("Invalid RPC UTF-8/JSON frame") from error
    if not isinstance(value, dict):
        raise ProtocolError("RPC frame must be an object")
    return value


def _serialize(value: dict[str, Any], maximum: int) -> bytes:
    """Incremental byte bound avoids first allocating an oversized JSON copy."""
    if not isinstance(value, dict) or not _integer(maximum) or maximum < 2:
        raise ProtocolError("Invalid RPC command or byte limit")
    buffer = bytearray()
    try:
        for piece in json.JSONEncoder(ensure_ascii=False, allow_nan=False, separators=(",", ":")).iterencode(value):
            if len(buffer) + len(piece) + 1 > maximum:
                raise ProtocolError("RPC command exceeds the transport limit")
            encoded = piece.encode("utf-8", errors="strict")
            if len(buffer) + len(encoded) + 1 > maximum:
                raise ProtocolError("RPC command exceeds the transport limit")
            buffer.extend(encoded)
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise ProtocolError("Invalid or oversized RPC command") from error
    return bytes(buffer)


class FrameDecoder:
    """Strict, noninterleaved OMP v2 reassembly, bounded by native ceilings."""
    def __init__(self) -> None:
        self.failed = False
        self.last_was_chunk = False
        self._pending: tuple[str, int, int] | None = None
        self._next_index = 0
        self._bytes = bytearray()

    def invalidate(self) -> None:
        self.failed = True
        self._pending = None
        self._bytes.clear()

    def receive_line(self, line: bytes) -> dict[str, Any] | None:
        if self.failed:
            raise ProtocolError("RPC decoder has been invalidated")
        try:
            if not isinstance(line, bytes) or len(line) > MAX_RPC_FRAME_BYTES:
                raise ProtocolError("RPC physical frame exceeds the transport limit")
            if not line.endswith(b"\n") or b"\n" in line[:-1] or b"\r" in line[:-2]:
                raise ProtocolError("RPC physical frame must be one complete JSONL line")
            value = _load(line[:-1])
            self.last_was_chunk = value.get("type") == "rpc_chunk"
            if value.get("type") != "rpc_chunk":
                if self._pending is not None:
                    raise ProtocolError("RPC chunk sequence interrupted")
                return value
            chunk_id, index, count, length, data = (value.get(key) for key in
                                                   ("chunkId", "index", "count", "byteLength", "data"))
            if (not isinstance(chunk_id, str) or not 0 < len(chunk_id) <= 128
                    or not _integer(index) or not _integer(count) or not _integer(length)
                    or not 2 <= count <= math.ceil(MAX_RPC_REASSEMBLED_BYTES / RPC_CHUNK_PAYLOAD_BYTES)
                    or not 0 <= index < count or not MAX_RPC_FRAME_BYTES <= length <= MAX_RPC_REASSEMBLED_BYTES):
                raise ProtocolError("Invalid RPC chunk metadata")
            if not isinstance(data, str) or not data or len(data) > 4 * math.ceil(RPC_CHUNK_PAYLOAD_BYTES / 3):
                raise ProtocolError("Invalid RPC chunk data")
            try:
                decoded = base64.b64decode(data, validate=True)
            except (ValueError, UnicodeError) as error:
                raise ProtocolError("Invalid RPC chunk base64") from error
            if base64.b64encode(decoded).decode("ascii") != data or len(decoded) > RPC_CHUNK_PAYLOAD_BYTES:
                raise ProtocolError("Invalid RPC chunk data")
            header = (chunk_id, count, length)
            if self._pending is None:
                if index != 0:
                    raise ProtocolError("RPC chunk sequence must start at zero")
                self._pending = header
                self._next_index = 0
            if self._pending != header or index != self._next_index:
                raise ProtocolError("RPC chunk sequence is inconsistent")
            if len(self._bytes) + len(decoded) > length:
                raise ProtocolError("RPC chunk exceeds its declared byte length")
            self._bytes.extend(decoded)
            self._next_index += 1
            if self._next_index < count:
                return None
            if len(self._bytes) != length:
                raise ProtocolError("RPC chunk byte length does not match")
            # json.loads accepts bytearray, but strict UTF-8 must be checked before
            # JSON's more permissive byte encoding detection.
            result = _load(self._bytes)
            self._bytes.clear()
            self._pending = None
            if result.get("type") == "rpc_chunk":
                raise ProtocolError("Nested RPC chunk frames are invalid")
            return result
        except ProtocolError:
            self.invalidate()
            raise

    def finish(self) -> None:
        if self.failed or self._pending is not None:
            self.invalidate()
            raise ProtocolError("RPC stream ended before a complete logical frame")


def encode_output_frames(value: dict[str, Any], *, protocol_version: int = 2,
                         chunk_id: str = "rpc-fixture") -> Iterator[bytes]:
    """Bounded native stdout framing for fixtures; never use for process stdin.

    Does not implement native v1 elision or agent_end transcript compaction.
    Oversized values fail explicitly, preserving a lossless fixture contract.
    """
    if type(protocol_version) is not int or protocol_version not in (1, 2):
        raise ProtocolError("Unsupported RPC protocol version")
    data = _serialize(value, MAX_RPC_REASSEMBLED_BYTES + 1 if protocol_version == 2 else MAX_RPC_FRAME_BYTES)
    if len(data) + 1 <= MAX_RPC_FRAME_BYTES:
        yield data + b"\n"
        return
    if not isinstance(chunk_id, str) or not 0 < len(chunk_id) <= 128:
        raise ProtocolError("Invalid RPC chunk id")
    count = math.ceil(len(data) / RPC_CHUNK_PAYLOAD_BYTES)
    for index in range(count):
        frame = {"type": "rpc_chunk", "chunkId": chunk_id, "index": index,
                 "count": count, "byteLength": len(data),
                 "data": base64.b64encode(data[index * RPC_CHUNK_PAYLOAD_BYTES:
                                               (index + 1) * RPC_CHUNK_PAYLOAD_BYTES]).decode("ascii")}
        yield _serialize(frame, MAX_RPC_FRAME_BYTES) + b"\n"


@dataclass
class _Prompt:
    command: str
    acknowledged: bool = False
    failed_response: dict[str, Any] | None = None


_EQUIVALENT_EVENTS = frozenset({
    "message_start", "message_update", "message_end", "tool_execution_start",
    "tool_execution_update", "tool_execution_end", "tool_stream_update",
    "auto_compaction_start", "auto_compaction_end", "auto_retry_start", "auto_retry_end",
    "extension_ui_request", "extension_error", "queue_update", "turn_start", "turn_end",
})


class Adapter:
    """One connection's framing, qualification and correlated prompt lifecycle.

    can_input means the wire contract is qualified, independent of busy; the
    controller owns whether a busy prompt is queued. busy is conservative until
    an explicit native settlement and every admitted prompt result are known.
    """
    physical_line_limit = MAX_RPC_FRAME_BYTES

    def __init__(self, *, negotiate_v2: bool = True) -> None:
        self.decoder = FrameDecoder()
        self.protocol_version = 1
        self._negotiate_v2 = negotiate_v2
        self._ready = False
        self._qualified_state = False
        self._negotiation_id = ""
        self._counter = 0
        self._commands: dict[str, tuple[str, str]] = {}
        self._prompts: dict[str, _Prompt] = {}
        self._state_failure_barriers: dict[str, frozenset[str]] = {}
        # get_state can overtake ACK, even when encoded after its error. Keep
        # bounded correlation after quiet-state reconciliation so valid late
        # failure controls are consumed without reopening a settled UI turn.
        self._retired_failures: dict[str, _Prompt] = {}
        self._completed: deque[str] = deque(maxlen=128)
        self._settled = False
        self._streaming = False
        self._compacting = False
        self._async_work = False
        self._queued = 0
        self._activity_pending_settle = False
        self._settlement_deferred = False

    @property
    def can_input(self) -> bool:
        return (not self.decoder.failed and self._ready and self._qualified_state
                and (self.protocol_version == 2 or not self._negotiate_v2))

    @property
    def busy(self) -> bool:
        return bool(self._prompts or not self._settled or self._streaming
                    or self._compacting or self._async_work or self._queued)

    @property
    def active_prompt_id(self) -> str:
        return next(iter(self._prompts), "")

    def invalidate(self) -> None:
        self.decoder.invalidate()
        self._qualified_state = False

    def discard_command(self, identifier: str) -> bool:
        """Undo registration of an unsent command; never cancel admitted work.

        The controller calls this under its send/receive lock only when its
        transport rejected enqueue. A partial/failed OS write requires closing
        and invalidating instead, because the peer might have received it.
        """
        ticket = self._prompts.get(identifier)
        if identifier not in self._commands or (ticket is not None and ticket.acknowledged):
            return False
        del self._commands[identifier]
        self._prompts.pop(identifier, None)
        self._state_failure_barriers.pop(identifier, None)
        return True

    def _id(self) -> str:
        self._counter += 1
        return f"launcher-omp-{self._counter}"

    def encode_command(self, command: dict[str, Any], max_bytes: int = DEFAULT_COMMAND_BYTES) -> bytes:
        """Translate and register a command atomically after its byte validation.

        The caller must invalidate/close after a failed write; this registration
        intentionally precedes sending so a fast response cannot race its ID.
        """
        if self.decoder.failed:
            raise ProtocolError("OMP connection has been invalidated")
        if not isinstance(command, dict) or not isinstance(command.get("type"), str):
            raise ProtocolError("RPC command must have a type")
        value = dict(command)
        semantic_type = value["type"]
        value["type"] = {"get_commands": "get_available_commands", "get_entries": "get_messages"}.get(semantic_type, semantic_type)
        native_type = value["type"]
        control = native_type in _CONTROL_RESPONSES
        if control and "id" not in value:
            raise ProtocolError("OMP side-channel response requires its native request id")
        identifier = value["id"] if "id" in value else self._id()
        if not isinstance(identifier, str) or not 0 < len(identifier) <= 256:
            raise ProtocolError("RPC command id must be a bounded nonempty string")
        if not control and (identifier in self._commands or identifier in self._prompts or identifier in self._completed):
            raise ProtocolError("RPC command id was already used")
        value["id"] = identifier
        prompt = native_type in {"prompt", "abort_and_prompt"}
        if prompt and not self.can_input:
            raise ProtocolError("OMP has not qualified its native session lifecycle")
        if not control and (len(self._commands) >= MAX_PENDING_COMMANDS or (prompt and len(self._prompts) >= MAX_PENDING_PROMPTS)):
            raise ProtocolError("Too many pending OMP commands")
        if not _integer(max_bytes) or max_bytes < 2:
            raise ProtocolError("Invalid RPC command byte limit")
        payload = _serialize(value, min(max_bytes, MAX_RPC_FRAME_BYTES)) + b"\n"
        if control:
            return payload
        self._commands[identifier] = (native_type, semantic_type)
        if native_type == "get_state":
            # Only a command encoded after observing a failure may reconcile
            # it. A previously in-flight state response is not a causal proof.
            self._state_failure_barriers[identifier] = frozenset(
                key for key, ticket in self._prompts.items() if ticket.failed_response is not None
            )
        if prompt:
            self._prompts[identifier] = _Prompt(native_type)
        return payload

    def receive_line(self, line: bytes) -> Result:
        try:
            value = self.decoder.receive_line(line)
            if self.decoder.last_was_chunk and self.protocol_version != 2:
                raise ProtocolError("OMP sent chunked output before protocol v2 negotiation")
            if value is None:
                return Result()
            if value.get("type") == "rpc_chunk":
                raise ProtocolError("Nested RPC chunk frame")
            return self._receive(value)
        except ProtocolError:
            self.invalidate()
            raise

    def _receive(self, value: dict[str, Any]) -> Result:
        kind = value.get("type")
        if not isinstance(kind, str) or not kind:
            raise ProtocolError("RPC event must have a type")
        if kind == "ready":
            if (self._ready or value.get("protocolVersion") != 1
                    or value.get("supportedProtocolVersions") != [1, 2]
                    or any(type(version) is not int for version in value.get("supportedProtocolVersions", []))
                    or type(value.get("protocolVersion")) is not int
                    or value.get("maxFrameBytes") != MAX_RPC_FRAME_BYTES
                    or value.get("maxReassembledFrameBytes") != MAX_RPC_REASSEMBLED_BYTES):
                raise ProtocolError("Unsupported OMP ready protocol contract")
            self._ready = True
            commands = []
            if self._negotiate_v2:
                self._negotiation_id = self._id()
                commands.append({"id": self._negotiation_id, "type": "negotiate_protocol", "protocolVersion": 2})
            return Result(commands=commands)
        if not self._ready:
            # Startup command metadata may precede ready; it proves no lifecycle.
            if kind == "available_commands_update":
                return Result(events=[self._command_catalog(value)])
            raise ProtocolError("OMP emitted an event before its ready contract")
        if kind == "response":
            return self._response(value)
        if kind == "prompt_result":
            return self._prompt_result(value)
        if kind == "session_settled":
            was_active = self.busy or self._activity_pending_settle
            self._settled = True
            self._streaming = self._compacting = self._async_work = False
            self._queued = 0
            self._settlement_deferred = bool(self._prompts)
            if was_active and not self.busy:
                self._activity_pending_settle = False
                return Result(events=[{"type": "agent_settled"}])
            return Result()
        if kind == "agent_start":
            self._settled = False
            self._streaming = True
            self._activity_pending_settle = True
            self._settlement_deferred = False
            return Result(events=[value])
        if kind == "agent_end":
            self._streaming = False
            self._settled = False
            if value.get("awaitingAsyncWork") is True:
                self._async_work = True
            # Native isTerminal/yielded are deliberately NOT settlement proof.
            return Result(events=[value])
        if kind == "available_commands_update":
            return Result(events=[self._command_catalog(value)])
        if kind == "rpc_frame_error":
            raise ProtocolError("OMP could not deliver a complete RPC event")
        if kind == "command_output":
            text = value.get("text")
            if not isinstance(text, str):
                raise ProtocolError("OMP command output must contain text")
            prefix = text[:MAX_COMMAND_OUTPUT_BYTES].encode("utf-8", errors="replace")
            output = prefix[:MAX_COMMAND_OUTPUT_BYTES].decode("utf-8", errors="ignore")
            return Result(events=[{"type": "launcher_command_output", "title": "Command output", "text": output,
                                   "truncated": len(text) > len(output)}])
        if kind == "notice":
            if value.get("level") not in ("info", "warning", "error") or not isinstance(value.get("message"), str):
                raise ProtocolError("Invalid OMP notice")
            return Result(events=[{"type": "extension_ui_request", "method": "notify",
                                   "message": value["message"], "notifyType": value["level"]}])
        if kind == "queue_update":
            self._check_queue(value)
            self._queued = len(value["steering"]) + len(value["followUp"])
            if self._queued:
                self._settled = False
        if kind == "auto_compaction_start":
            self._compacting = True
            self._settled = False
        elif kind == "auto_compaction_end":
            self._compacting = False
        if kind in _EQUIVALENT_EVENTS:
            if kind.startswith("auto_compaction_"):
                value = {**value, "type": kind.removeprefix("auto_")}
            if kind.startswith("message_"):
                message = value.get("message")
                identifier = value.get("messageId")
                if not isinstance(identifier, str) or not identifier:
                    raise ProtocolError("OMP message event lacks its native message identity")
                if not isinstance(message, dict):
                    if kind == "message_update" and "message" not in value:
                        return Result(events=[value])
                    raise ProtocolError("OMP message event lacks its native message")
                # The shared semantic renderer reads identity from the message;
                # OMP's stable identity lives on the enclosing frame instead.
                value = {**value, "message": {**message, "messageId": identifier}}
            return Result(events=[value])
        # Other OMP-native side channels are not silently reinterpreted as Pi.
        return Result()

    @staticmethod
    def _check_queue(value: dict[str, Any]) -> None:
        if any(not isinstance(value.get(key), list) or any(not isinstance(item, str) for item in value[key])
               for key in ("steering", "followUp")):
            raise ProtocolError("Invalid OMP queue snapshot")

    @staticmethod
    def _command_catalog(value: dict[str, Any]) -> dict[str, Any]:
        commands = value.get("commands")
        if not isinstance(commands, list) or any(not isinstance(item, dict) or not isinstance(item.get("name"), str)
                                               or not isinstance(item.get("source"), str)
                                               or ("description" in item and not isinstance(item["description"], str))
                                               for item in commands):
            raise ProtocolError("Invalid OMP command catalog")
        # Only the three common display fields are equivalent. Rich OMP fields
        # and sourceInfo are not claimed to be Pi command wire contracts.
        return {"type": "response", "command": "get_commands", "success": True,
                "data": {"commands": [{key: item[key] for key in ("name", "source", "description") if key in item}
                                      for item in commands]}}

    def _response(self, value: dict[str, Any]) -> Result:
        identifier, native_type = value.get("id"), value.get("command")
        if not isinstance(native_type, str) or type(value.get("success")) is not bool:
            raise ProtocolError("Invalid OMP command response")
        registration = self._commands.get(identifier) if isinstance(identifier, str) else None
        ticket = self._prompts.get(identifier) if isinstance(identifier, str) else None
        if registration is None:
            retired = self._retired_failures.get(identifier) if isinstance(identifier, str) else None
            if retired is not None:
                if native_type != retired.command or not value["success"] or retired.acknowledged:
                    raise ProtocolError("Invalid late OMP failure acknowledgement")
                retired.acknowledged = True
                return Result()
            # A post-admission failure emits a second same-ID error response.
            if ticket is None or not ticket.acknowledged or native_type != ticket.command or value["success"]:
                raise ProtocolError("Uncorrelated OMP command response")
        elif registration[0] != native_type:
            raise ProtocolError("OMP response command does not match its id")
        else:
            # A tracked rejection can precede its success ACK. The native
            # watcher never rejects its admission promise, and still owes ACK
            # plus prompt_result after onError emitted this failure response.
            if ticket is None or value["success"] or ticket.acknowledged:
                del self._commands[identifier]
        barrier_ids = self._state_failure_barriers.pop(identifier, frozenset()) if native_type == "get_state" else frozenset()
        if native_type == "negotiate_protocol":
            if (identifier != self._negotiation_id or not value["success"]
                    or not isinstance(value.get("data"), dict) or value["data"].get("protocolVersion") != 2
                    or type(value["data"].get("protocolVersion")) is not int):
                raise ProtocolError("OMP protocol v2 negotiation failed")
            self.protocol_version = 2
            return Result()
        event = dict(value)
        if native_type == "get_available_commands" and value["success"]:
            data = value.get("data")
            if not isinstance(data, dict):
                raise ProtocolError("Invalid OMP command catalog response")
            event = self._command_catalog(data)
            event["id"] = identifier
        elif native_type == "get_available_commands":
            event["command"] = "get_commands"
        elif native_type == "get_state" and value["success"]:
            event = self._state_response(value)
            reconciled: list[dict[str, Any]] = []
            data = value["data"]
            if data["isSettled"] and not data["isCompacting"]:
                for failed_id in barrier_ids:
                    pending = self._prompts.get(failed_id)
                    if pending is None or pending.acknowledged or pending.failed_response is None:
                        continue
                    del self._prompts[failed_id]
                    self._commands.pop(failed_id, None)
                    self._completed.append(failed_id)
                    self._retired_failures[failed_id] = pending
                    while len(self._retired_failures) > 128:
                        del self._retired_failures[next(iter(self._retired_failures))]
                    # This is the actual failure response, now finalized by
                    # native quiescence. No assistant or prompt result is made up.
                    reconciled.append({**pending.failed_response, "command": "prompt",
                                       "ompPromptResponse": True, "ompAwaitingPromptResult": False})
                event["data"]["isStreaming"] = self.busy
                if not self.busy:
                    self._activity_pending_settle = False
                    self._settlement_deferred = False
            queued = value["data"].get("queuedMessages")
            if queued is not None:
                if not isinstance(queued, dict):
                    raise ProtocolError("Invalid OMP state queue snapshot")
                self._check_queue(queued)
                return Result(events=[*reconciled, {"type": "queue_update", "steering": queued["steering"],
                                       "followUp": queued["followUp"]}, event])
            return Result(events=[*reconciled, event])
        elif native_type in {"prompt", "abort_and_prompt"}:
            if ticket is None:
                raise ProtocolError("Uncorrelated OMP prompt admission")
            event["command"] = "prompt"
            event["ompPromptResponse"] = True
            if not value["success"]:
                if ticket.failed_response is not None:
                    raise ProtocolError("Duplicate OMP prompt error response")
                error_text = value.get("error")
                if not isinstance(error_text, str):
                    raise ProtocolError("OMP prompt error response must contain text")
                retained = error_text[:MAX_COMMAND_OUTPUT_BYTES].encode("utf-8", errors="replace")
                ticket.failed_response = {"type": "response", "id": identifier, "command": native_type,
                                          "success": False,
                                          "error": retained[:MAX_COMMAND_OUTPUT_BYTES].decode("utf-8", errors="ignore")}
                event["ompAwaitingPromptResult"] = True
                if not ticket.acknowledged:
                    return Result(events=[event], commands=[{"id": self._id(), "type": "get_state"}])
            else:
                if ticket.acknowledged:
                    raise ProtocolError("Duplicate OMP prompt admission")
                ticket.acknowledged = True
                data = value.get("data")
                if isinstance(data, dict) and "agentInvoked" in data and type(data["agentInvoked"]) is not bool:
                    raise ProtocolError("Invalid OMP local prompt admission")
                if isinstance(data, dict) and data.get("agentInvoked") is False:
                    if ticket.failed_response is not None:
                        raise ProtocolError("OMP failed prompt cannot complete as a successful local command")
                    del self._prompts[identifier]
                    self._completed.append(identifier)
                    if not self.busy:
                        self._activity_pending_settle = False
                        self._settlement_deferred = False
                    return Result(events=[event, {"type": "launcher_local_prompt_complete", "id": identifier,
                                                 "agentInvoked": False, "sessionSettled": not self.busy}])
        return Result(events=[event])

    def _state_response(self, value: dict[str, Any]) -> dict[str, Any]:
        data = value.get("data")
        if (not isinstance(data, dict)
                or any(type(data.get(key)) is not bool for key in
                       ("isStreaming", "isCompacting", "isSettled", "hasPendingAsyncWork"))
                or not _integer(data.get("queuedMessageCount")) or data["queuedMessageCount"] < 0):
            raise ProtocolError("OMP state lacks the required settlement/async lifecycle contract")
        if data["isSettled"] and (data["isStreaming"] or data["hasPendingAsyncWork"]
                                  or data["queuedMessageCount"]):
            raise ProtocolError("OMP state claims settlement while work remains")
        self._qualified_state = True
        self._settled = data["isSettled"]
        self._streaming, self._compacting, self._async_work = (data[key] for key in
                                                            ("isStreaming", "isCompacting", "hasPendingAsyncWork"))
        self._queued = data["queuedMessageCount"]
        adapted = dict(data)
        adapted["ompIsStreaming"] = data["isStreaming"]
        adapted["isStreaming"] = self.busy
        adapted["pendingMessageCount"] = data["queuedMessageCount"]
        if not self.busy:
            self._activity_pending_settle = False
            self._settlement_deferred = False
        return {**value, "data": adapted}

    def _prompt_result(self, value: dict[str, Any]) -> Result:
        identifier = value.get("id")
        ticket = self._prompts.get(identifier) if isinstance(identifier, str) else None
        retired = self._retired_failures.get(identifier) if isinstance(identifier, str) else None
        if ticket is None and retired is not None:
            if not retired.acknowledged or value.get("status") != "error" or value.get("agentInvoked") is not False:
                raise ProtocolError("Invalid late OMP failure result")
            self._validate_prompt_result(value)
            del self._retired_failures[identifier]
            return Result()
        if ticket is None or not ticket.acknowledged:
            raise ProtocolError("Uncorrelated OMP prompt result or result before admission")
        self._validate_prompt_result(value)
        if ticket.failed_response is not None and (value["status"] != "error" or value["agentInvoked"] is not False):
            raise ProtocolError("OMP prompt error response does not match its failed result")
        del self._prompts[identifier]
        self._completed.append(identifier)
        self._settled = value["sessionSettled"]
        if self._settled:
            self._streaming = self._compacting = self._async_work = False
            self._queued = 0
        event = {**value, "type": "launcher_prompt_result", "sessionBusy": self.busy}
        if not value["agentInvoked"] and value["status"] == "completed":
            # abort_and_prompt acknowledges before asynchronous dispatch; its
            # local-only completion therefore arrives as a result, rather than
            # the synchronous prompt admission's data.agentInvoked:false.
            if not self.busy:
                self._settlement_deferred = False
                self._activity_pending_settle = False
            return Result(events=[event, {"type": "launcher_local_prompt_complete", "id": identifier,
                                         "agentInvoked": False, "sessionSettled": not self.busy}])
        if not self.busy and self._settlement_deferred:
            self._settlement_deferred = False
            self._activity_pending_settle = False
            return Result(events=[event, {"type": "agent_settled"}])
        # Rejections/aborts before agent_start have no native settlement watcher
        # activity. An explicit state proof settles their failed/aborted UI turn.
        commands = ([{"id": self._id(), "type": "get_state"}]
                    if not self.busy and not self._activity_pending_settle else [])
        return Result(events=[event], commands=commands)

    @staticmethod
    def _validate_prompt_result(value: dict[str, Any]) -> None:
        if (value.get("status") not in ("completed", "aborted", "error")
                or type(value.get("agentInvoked")) is not bool or type(value.get("sessionSettled")) is not bool):
            raise ProtocolError("Invalid OMP prompt result")
        if value["status"] == "error":
            error = value.get("error")
            if not isinstance(error, dict) or not isinstance(error.get("message"), str) or type(error.get("retryable")) is not bool:
                raise ProtocolError("Invalid OMP prompt error")
            if (any(key in error and not isinstance(error[key], str) for key in ("provider", "model"))
                    or ("httpStatus" in error and not _integer(error["httpStatus"]))):
                raise ProtocolError("Invalid OMP prompt error metadata")
