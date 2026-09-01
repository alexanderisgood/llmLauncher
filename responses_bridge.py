#!/usr/bin/env python3
"""Fail-closed OpenAI Responses to Chat Completions bridge for MTPLX.

Codex speaks the Responses API while MTPLX currently exposes Chat Completions.
This module translates only the request and stream shapes that can be preserved
without guessing. Unsupported inputs fail before a model request is sent.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any


_NAME = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_FRAME_END = re.compile(br"\r?\n\r?\n")
_BENIGN_RESPONSE_FIELDS = {
    "client_metadata", "include", "metadata", "prompt_cache_key", "reasoning",
    "service_tier", "store", "truncation",
}
_LIMIT_REASONS = {"length", "max_tokens", "max_completion_tokens", "max_output_tokens"}


@dataclass(frozen=True)
class ToolTarget:
    namespace: str | None
    name: str


@dataclass(frozen=True)
class BridgeRequest:
    body: bytes
    by_wire_name: dict[str, ToolTarget]
    by_target: dict[tuple[str | None, str], str]
    model: str
    output_limit: int


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _valid_name(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise ValueError(f"invalid {label}")
    return value


def _wire_name(namespace: str, name: str, index: int, reserved: set[str]) -> str:
    readable = re.sub(r"[^A-Za-z0-9_-]+", "_", f"llmns_{namespace}__{name}")
    digest = hashlib.sha256(f"{namespace}\0{name}".encode("utf-8")).hexdigest()[:10]
    candidate = readable if len(readable) <= 64 else f"{readable[:53]}_{digest}"
    if candidate in reserved:
        candidate = f"llmns_{index:03d}_{digest}"
    if candidate in reserved or not _NAME.fullmatch(candidate):
        raise ValueError("namespace tool names cannot be mapped without collision")
    return candidate


def _function_tool(tool: dict[str, Any], wire_name: str, namespace: str | None) -> dict[str, Any]:
    original = _valid_name(tool.get("name"), "function tool name")
    parameters = tool.get("parameters", {"type": "object", "properties": {}})
    if not isinstance(parameters, dict):
        raise ValueError(f"function tool {original} has invalid parameters")
    description = tool.get("description")
    if description is not None and not isinstance(description, str):
        raise ValueError(f"function tool {original} has an invalid description")
    if namespace:
        prefix = f"Codex namespace `{namespace}`, tool `{original}`."
        description = f"{prefix} {description or ''}".strip()
    function: dict[str, Any] = {"name": wire_name, "parameters": parameters}
    if description:
        function["description"] = description
    if isinstance(tool.get("strict"), bool):
        function["strict"] = tool["strict"]
    return {"type": "function", "function": function}


def _translate_tools(
    tools: Any,
) -> tuple[list[dict[str, Any]], dict[str, ToolTarget], dict[tuple[str | None, str], str]]:
    if tools is None:
        return [], {}, {}
    if not isinstance(tools, list):
        raise ValueError("Responses tools must be a list")
    top_level_names = {
        _valid_name(tool.get("name"), "function tool name")
        for tool in tools if isinstance(tool, dict) and tool.get("type") == "function"
    }
    translated: list[dict[str, Any]] = []
    by_wire: dict[str, ToolTarget] = {}
    by_target: dict[tuple[str | None, str], str] = {}
    reserved = {name for name in top_level_names if len(name) <= 64}
    function_index = 0
    namespace_index = 0
    for tool in tools:
        if not isinstance(tool, dict):
            raise ValueError("Responses tool entries must be objects")
        tool_type = tool.get("type")
        if tool_type == "function":
            name = _valid_name(tool.get("name"), "function tool name")
            target = ToolTarget(None, name)
            if (None, name) in by_target:
                raise ValueError(f"duplicate function tool name: {name}")
            wire = name if len(name) <= 64 else _wire_name("functions", name, function_index, reserved)
            function_index += 1
            if wire in by_wire:
                raise ValueError(f"function tool wire-name collision: {wire}")
            reserved.add(wire)
            translated.append(_function_tool(tool, wire, None))
            by_wire[wire] = target
            by_target[(None, name)] = wire
            continue
        if tool_type != "namespace":
            raise ValueError(f"MTPLX cannot preserve Responses tool type: {tool_type or 'missing'}")
        namespace = _valid_name(tool.get("name"), "tool namespace")
        children = tool.get("tools")
        if not isinstance(children, list) or not children:
            raise ValueError(f"tool namespace {namespace} has no function tools")
        for child in children:
            if not isinstance(child, dict) or child.get("type") != "function":
                child_type = child.get("type") if isinstance(child, dict) else "invalid"
                raise ValueError(
                    f"MTPLX cannot preserve {child_type} inside tool namespace {namespace}"
                )
            name = _valid_name(child.get("name"), "namespace function name")
            target_key = (namespace, name)
            if target_key in by_target:
                raise ValueError(f"duplicate namespace function: {namespace}.{name}")
            wire = _wire_name(namespace, name, namespace_index, reserved)
            namespace_index += 1
            reserved.add(wire)
            translated.append(_function_tool(child, wire, namespace))
            by_wire[wire] = ToolTarget(namespace, name)
            by_target[target_key] = wire
    if len(translated) > 256:
        raise ValueError("MTPLX Codex bridge supports at most 256 expanded function tools")
    return translated, by_wire, by_target


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        raise ValueError("Responses message content must be text or a content list")
    parts: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            raise ValueError("Responses content entries must be objects")
        part_type = part.get("type")
        if part_type not in {"input_text", "output_text", "text"}:
            raise ValueError(f"MTPLX Codex bridge cannot preserve content type: {part_type}")
        text = part.get("text")
        if not isinstance(text, str):
            raise ValueError("Responses text content is invalid")
        parts.append(text)
    return "\n\n".join(parts)


def _output_text(output: Any) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, dict) and isinstance(output.get("content"), str):
        return str(output["content"])
    if isinstance(output, (dict, list)):
        return json.dumps(output, ensure_ascii=False, separators=(",", ":"))
    if output is None:
        return ""
    return str(output)


def _reasoning_text(item: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("summary", "content"):
        value = item.get(key)
        if isinstance(value, list):
            for part in value:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    parts.append(str(part["text"]))
    return "\n".join(parts)


def _lookup_wire(
    item: dict[str, Any], by_target: dict[tuple[str | None, str], str],
) -> str:
    name = _valid_name(item.get("name"), "function call name")
    namespace = item.get("namespace")
    if namespace is not None:
        namespace = _valid_name(namespace, "function call namespace")
    wire = by_target.get((namespace, name))
    if wire is None:
        raise ValueError(f"function call does not match a declared tool: {namespace or 'functions'}.{name}")
    return wire


def _translate_input(
    value: Any, by_target: dict[tuple[str | None, str], str], instructions: Any,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    if instructions is not None:
        if not isinstance(instructions, str):
            raise ValueError("Responses instructions must be text")
        if instructions:
            messages.append({"role": "system", "content": instructions})
    if isinstance(value, str):
        messages.append({"role": "user", "content": value})
        return messages
    if not isinstance(value, list):
        raise ValueError("Responses input must be text or an item list")

    assistant_seen = False
    pending_content: list[str] = []
    pending_reasoning: list[str] = []
    pending_calls: list[dict[str, Any]] = []

    def flush_assistant() -> None:
        nonlocal assistant_seen
        if not assistant_seen and not pending_calls and not pending_reasoning:
            return
        message: dict[str, Any] = {
            "role": "assistant",
            "content": "\n\n".join(pending_content) if pending_content else None,
        }
        if pending_reasoning:
            message["reasoning_content"] = "\n".join(pending_reasoning)
        if pending_calls:
            message["tool_calls"] = list(pending_calls)
        messages.append(message)
        assistant_seen = False
        pending_content.clear()
        pending_reasoning.clear()
        pending_calls.clear()

    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Responses input entries must be objects")
        item_type = item.get("type")
        if item_type == "message":
            role = item.get("role")
            if role == "developer":
                role = "system"
            if role not in {"system", "user", "assistant"}:
                raise ValueError(f"MTPLX Codex bridge cannot preserve message role: {role}")
            content = _content_text(item.get("content"))
            if role == "assistant":
                assistant_seen = True
                pending_content.append(content)
            else:
                flush_assistant()
                messages.append({"role": role, "content": content})
        elif item_type == "reasoning":
            text = _reasoning_text(item)
            if text:
                assistant_seen = True
                pending_reasoning.append(text)
        elif item_type == "function_call":
            call_id = item.get("call_id")
            arguments = item.get("arguments")
            if not isinstance(call_id, str) or not call_id or not isinstance(arguments, str):
                raise ValueError("Responses function call is invalid")
            assistant_seen = True
            pending_calls.append({
                "id": call_id,
                "type": "function",
                "function": {"name": _lookup_wire(item, by_target), "arguments": arguments},
            })
        elif item_type == "function_call_output":
            flush_assistant()
            call_id = item.get("call_id")
            if not isinstance(call_id, str) or not call_id:
                raise ValueError("Responses function output has no call id")
            messages.append({
                "role": "tool", "tool_call_id": call_id,
                "content": _output_text(item.get("output")),
            })
        else:
            raise ValueError(f"MTPLX Codex bridge cannot preserve input item type: {item_type}")
    flush_assistant()
    if not messages:
        raise ValueError("Responses input contains no translatable messages")
    return messages


def translate_responses_request(body: bytes, config: dict[str, Any]) -> BridgeRequest:
    """Translate one already-bounded Responses request into Chat Completions."""
    value = json.loads(body)
    if not isinstance(value, dict):
        raise ValueError("Responses request must be an object")
    model = value.get("model")
    if not isinstance(model, str) or model != config.get("servedModel"):
        raise ValueError("Responses request targets a different model")
    if value.get("stream") is not True:
        raise ValueError("MTPLX Codex bridge requires streaming Responses requests")
    if value.get("previous_response_id") not in {None, ""}:
        raise ValueError("MTPLX Codex bridge cannot preserve previous_response_id")
    if not isinstance(value.get("max_output_tokens"), int) or isinstance(value.get("max_output_tokens"), bool):
        raise ValueError("Responses request has no valid output limit")

    tools, by_wire, by_target = _translate_tools(value.get("tools"))
    messages = _translate_input(value.get("input"), by_target, value.get("instructions"))
    translated: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
        "max_tokens": int(value["max_output_tokens"]),
    }
    if tools:
        translated["tools"] = tools
        choice = value.get("tool_choice", "auto")
        if isinstance(choice, str) and choice in {"auto", "none", "required"}:
            translated["tool_choice"] = choice
        elif isinstance(choice, dict) and choice.get("type") == "function":
            wire = _lookup_wire(choice, by_target)
            translated["tool_choice"] = {"type": "function", "function": {"name": wire}}
        else:
            raise ValueError("MTPLX Codex bridge cannot preserve this tool_choice")
        parallel = value.get("parallel_tool_calls")
        if parallel is not None:
            if not isinstance(parallel, bool):
                raise ValueError("parallel_tool_calls must be boolean")
            translated["parallel_tool_calls"] = parallel
    elif value.get("tool_choice") not in {None, "none", "auto"}:
        raise ValueError("tool_choice requires declared function tools")

    for key in ("temperature", "top_p"):
        setting = value.get(key)
        if setting is not None:
            if isinstance(setting, bool) or not isinstance(setting, (int, float)):
                raise ValueError(f"invalid {key}")
            translated[key] = setting
    if value.get("seed") is not None:
        if isinstance(value["seed"], bool) or not isinstance(value["seed"], int):
            raise ValueError("invalid seed")
        translated["seed"] = value["seed"]

    handled = {
        "model", "input", "instructions", "stream", "max_output_tokens", "tools",
        "tool_choice", "parallel_tool_calls", "previous_response_id", "temperature",
        "top_p", "seed",
    } | _BENIGN_RESPONSE_FIELDS
    unsupported = sorted(key for key, setting in value.items() if key not in handled and setting is not None)
    if unsupported:
        raise ValueError(f"MTPLX Codex bridge cannot preserve Responses fields: {', '.join(unsupported)}")
    return BridgeRequest(
        _json_bytes(translated), by_wire, by_target, model,
        int(value["max_output_tokens"]),
    )


class ChatStreamBridge:
    """Incrementally turn a Chat Completions SSE stream into Responses SSE."""

    def __init__(self, request: BridgeRequest) -> None:
        self.request = request
        self.response_id = f"resp_llm_{uuid.uuid4().hex}"
        self.buffer = bytearray()
        self.started = False
        self.finished = False
        self.failed = False
        self.text = ""
        self.reasoning = ""
        self.text_item_id = f"msg_llm_{uuid.uuid4().hex}"
        self.reasoning_item_id = f"rs_llm_{uuid.uuid4().hex}"
        self.text_index: int | None = None
        self.reasoning_index: int | None = None
        self.next_output_index = 0
        self.tool_calls: dict[int, dict[str, str]] = {}
        self.finish_reason: str | None = None
        self.usage: dict[str, int] = {}

    @staticmethod
    def _event(kind: str, **payload: Any) -> bytes:
        value = {"type": kind, **payload}
        return f"event: {kind}\ndata: {json.dumps(value, ensure_ascii=False, separators=(',', ':'))}\n\n".encode("utf-8")

    def start(self) -> bytes:
        if self.started:
            return b""
        self.started = True
        return self._event("response.created", response={
            "id": self.response_id, "object": "response", "status": "in_progress",
            "model": self.request.model,
        })

    def _ensure_text(self) -> bytes:
        if self.text_index is not None:
            return b""
        self.text_index = self.next_output_index
        self.next_output_index += 1
        return b"".join((
            self._event("response.output_item.added", output_index=self.text_index, item={
                "id": self.text_item_id, "type": "message", "role": "assistant",
                "status": "in_progress", "content": [],
            }),
            self._event("response.content_part.added", item_id=self.text_item_id,
                        output_index=self.text_index, content_index=0,
                        part={"type": "output_text", "text": "", "annotations": []}),
        ))

    def _ensure_reasoning(self) -> bytes:
        if self.reasoning_index is not None:
            return b""
        self.reasoning_index = self.next_output_index
        self.next_output_index += 1
        return self._event("response.output_item.added", output_index=self.reasoning_index, item={
            "id": self.reasoning_item_id, "type": "reasoning", "status": "in_progress",
            "summary": [],
        })

    def _fail(self, message: str) -> bytes:
        if self.finished:
            return b""
        self.failed = self.finished = True
        return self._event("response.failed", response={
            "id": self.response_id, "status": "failed",
            "error": {"code": "llm_launcher_bridge_error", "message": message},
        })

    def failure(self, message: str) -> bytes:
        """Terminate an already-started translated stream with a Responses error."""
        return self.start() + self._fail(message)

    def _chat_chunk(self, value: Any) -> bytes:
        if not isinstance(value, dict):
            return self._fail("MTPLX returned a non-object stream chunk")
        output = bytearray()
        usage = value.get("usage")
        if isinstance(usage, dict):
            for source, target in (
                ("prompt_tokens", "input_tokens"),
                ("completion_tokens", "output_tokens"),
                ("total_tokens", "total_tokens"),
            ):
                token_count = usage.get(source)
                if isinstance(token_count, int) and not isinstance(token_count, bool) and token_count >= 0:
                    self.usage[target] = token_count
        choices = value.get("choices")
        if not isinstance(choices, list):
            return bytes(output)
        for choice in choices:
            if not isinstance(choice, dict) or choice.get("index", 0) != 0:
                return self._fail("MTPLX returned an unsupported multi-choice response")
            delta = choice.get("delta")
            if delta is None and isinstance(choice.get("message"), dict):
                delta = choice["message"]
            if not isinstance(delta, dict):
                delta = {}
            reasoning_delta = next(
                (delta[key] for key in ("reasoning_content", "reasoning", "thinking")
                 if isinstance(delta.get(key), str)),
                "",
            )
            if reasoning_delta:
                output.extend(self._ensure_reasoning())
                self.reasoning += reasoning_delta
                output.extend(self._event(
                    "response.reasoning_summary_text.delta", item_id=self.reasoning_item_id,
                    output_index=self.reasoning_index, summary_index=0, delta=reasoning_delta,
                ))
            content = delta.get("content")
            if isinstance(content, str) and content:
                output.extend(self._ensure_text())
                self.text += content
                output.extend(self._event(
                    "response.output_text.delta", item_id=self.text_item_id,
                    output_index=self.text_index, content_index=0, delta=content, logprobs=[],
                ))
            tool_deltas = delta.get("tool_calls")
            if isinstance(tool_deltas, list):
                for tool_delta in tool_deltas:
                    if not isinstance(tool_delta, dict):
                        return self._fail("MTPLX returned an invalid tool-call delta")
                    index = tool_delta.get("index", 0)
                    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
                        return self._fail("MTPLX returned an invalid tool-call index")
                    current = self.tool_calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
                    if isinstance(tool_delta.get("id"), str):
                        current["id"] = str(tool_delta["id"])
                    function = tool_delta.get("function")
                    if isinstance(function, dict):
                        if isinstance(function.get("name"), str):
                            current["name"] += str(function["name"])
                        if isinstance(function.get("arguments"), str):
                            current["arguments"] += str(function["arguments"])
            finish = choice.get("finish_reason")
            if isinstance(finish, str):
                self.finish_reason = finish
        return bytes(output)

    def _frame(self, frame: bytes) -> bytes:
        data_lines = []
        for line in frame.replace(b"\r\n", b"\n").split(b"\n"):
            if line.startswith(b"data:"):
                data_lines.append(line[5:].lstrip())
        if not data_lines:
            return b""
        payload = b"\n".join(data_lines)
        if payload.strip() == b"[DONE]":
            return self.finish()
        try:
            value = json.loads(payload)
        except (ValueError, UnicodeError):
            return self._fail("MTPLX returned malformed streaming JSON")
        return self._chat_chunk(value)

    def feed(self, chunk: bytes) -> bytes:
        if self.finished or not chunk:
            return b""
        output = bytearray(self.start())
        self.buffer.extend(chunk)
        while True:
            match = _FRAME_END.search(self.buffer)
            if match is None:
                break
            frame = bytes(self.buffer[:match.start()])
            del self.buffer[:match.end()]
            output.extend(self._frame(frame))
        return bytes(output)

    def feed_completion(self, value: Any) -> bytes:
        if self.finished:
            return b""
        output = bytearray(self.start())
        output.extend(self._chat_chunk(value))
        output.extend(self.finish())
        return bytes(output)

    def _usage(self) -> dict[str, Any]:
        input_tokens = int(self.usage.get("input_tokens", 0))
        output_tokens = int(self.usage.get("output_tokens", 0))
        total_tokens = int(self.usage.get("total_tokens", input_tokens + output_tokens))
        return {
            "input_tokens": input_tokens, "input_tokens_details": None,
            "output_tokens": output_tokens, "output_tokens_details": None,
            "total_tokens": total_tokens,
        }

    def finish(self) -> bytes:
        if self.finished:
            return b""
        output = bytearray(self.start())
        if self.buffer:
            output.extend(self._frame(bytes(self.buffer)))
            self.buffer.clear()
            if self.finished:
                return bytes(output)

        if self.reasoning_index is not None:
            output.extend(self._event(
                "response.reasoning_summary_text.done", item_id=self.reasoning_item_id,
                output_index=self.reasoning_index, summary_index=0, text=self.reasoning,
            ))
            output.extend(self._event("response.output_item.done", output_index=self.reasoning_index, item={
                "id": self.reasoning_item_id, "type": "reasoning", "status": "completed",
                "summary": [{"type": "summary_text", "text": self.reasoning}],
            }))
        if self.text_index is not None:
            output.extend(self._event(
                "response.output_text.done", item_id=self.text_item_id,
                output_index=self.text_index, content_index=0, text=self.text, logprobs=[],
            ))
            output.extend(self._event(
                "response.content_part.done", item_id=self.text_item_id,
                output_index=self.text_index, content_index=0,
                part={"type": "output_text", "text": self.text, "annotations": []},
            ))
            output.extend(self._event("response.output_item.done", output_index=self.text_index, item={
                "id": self.text_item_id, "type": "message", "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": self.text, "annotations": []}],
            }))
        for index in sorted(self.tool_calls):
            call = self.tool_calls[index]
            target = self.request.by_wire_name.get(call["name"])
            if target is None:
                output.extend(self._fail(f"MTPLX called an undeclared bridge tool: {call['name']}"))
                return bytes(output)
            output_index = self.next_output_index
            self.next_output_index += 1
            call_id = call["id"] or f"call_llm_{uuid.uuid4().hex}"
            item: dict[str, Any] = {
                "id": f"fc_llm_{uuid.uuid4().hex}", "type": "function_call",
                "status": "completed", "call_id": call_id, "name": target.name,
                "arguments": call["arguments"],
            }
            if target.namespace:
                item["namespace"] = target.namespace
            output.extend(self._event("response.output_item.done", output_index=output_index, item=item))

        self.finished = True
        response = {"id": self.response_id, "model": self.request.model, "usage": self._usage()}
        stopped_at_ceiling = (
            self.finish_reason == "stop"
            and int(self.usage.get("output_tokens", 0)) >= self.request.output_limit
        )
        if self.finish_reason in _LIMIT_REASONS or stopped_at_ceiling:
            response.update({
                "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
            })
            output.extend(self._event("response.incomplete", response=response))
        elif self.finish_reason == "content_filter":
            response.update({
                "status": "failed",
                "error": {"code": "content_filter", "message": "MTPLX stopped the response"},
            })
            output.extend(self._event("response.failed", response=response))
        elif self.reasoning.strip() and not self.text.strip() and not self.tool_calls:
            response.update({
                "status": "failed",
                "error": {
                    "code": "reasoning_without_final_output",
                    "message": "MTPLX stopped after reasoning without an answer or tool call.",
                },
            })
            output.extend(self._event("response.failed", response=response))
        else:
            response["status"] = "completed"
            output.extend(self._event("response.completed", response=response))
        return bytes(output)
