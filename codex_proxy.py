#!/usr/bin/env python3
"""Private Responses pass-through for exact Codex launch contracts."""

from __future__ import annotations

import http.client
import hmac
import json
import os
import re
import stat
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from responses_bridge import BridgeRequest, ChatStreamBridge, translate_responses_request


MAX_BODY = 128 * 1024 * 1024
MAX_RESPONSE_GUARD_BUFFER = 16 * 1024 * 1024
SUPPORTED_BACKENDS = {
    "omlx", "lmstudio", "mtplx", "freetoken", "swiftlm", "mference", "whallm",
}
HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}
EFFORT_ORDER = ("auto", "off", "minimal", "low", "medium", "high", "xhigh", "max")
THINKING_BUDGETS = {"minimal": 1_024, "low": 2_048, "medium": 4_096, "high": 8_192, "xhigh": 16_384}


def fail(message: str) -> None:
    print(f"LLM Launcher Codex guard: {message}", file=sys.stderr)
    raise SystemExit(2)


def load_config(path: Path) -> dict[str, Any]:
    state_root = (Path.home() / "Library" / "Application Support" / "LLM Launcher" / "runs").resolve()
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
    for key in ("listenPort", "upstreamPort", "outputLimit"):
        if not isinstance(value.get(key), int):
            fail(f"invalid {key}")
    if not 1_024 <= value["listenPort"] <= 65_535 or not 1_024 <= value["upstreamPort"] <= 65_535:
        fail("invalid port")
    if not 1_024 <= value["outputLimit"] <= 2_000_000:
        fail("invalid response limit")
    if value.get("backend") not in SUPPORTED_BACKENDS:
        fail("unsupported Responses backend")
    if value.get("reasoning") not in EFFORT_ORDER:
        fail("invalid reasoning effort")
    if not all(isinstance(value.get(key), str) and value[key] for key in ("clientKey", "upstreamKey", "servedModel")):
        fail("invalid API key")
    return value


def transform_response_request(body: bytes, config: dict[str, Any]) -> bytes:
    """Set the exact output cap and translate the launcher's effort vocabulary."""
    value = json.loads(body)
    if not isinstance(value, dict):
        raise ValueError("Responses request must be a JSON object")
    if value.get("model") != config.get("servedModel"):
        raise ValueError("Responses request targets a different model")
    output_limit = int(config["outputLimit"])
    requested_limit = value.get("max_output_tokens")
    if requested_limit is None:
        value["max_output_tokens"] = output_limit
    elif isinstance(requested_limit, bool) or not isinstance(requested_limit, int) or requested_limit <= 0:
        raise ValueError("Invalid max_output_tokens")
    else:
        value["max_output_tokens"] = min(requested_limit, output_limit)
    effective_output_limit = int(value["max_output_tokens"])
    effort = str(config["reasoning"])
    if effort == "auto":
        # A user's global Codex setting (for example `ultra`) is otherwise
        # inherited into this one-off local route. "Model default" means the
        # local model/runtime chooses. Remove only the inherited effort while
        # retaining unrelated Responses controls such as summary style.
        reasoning = value.get("reasoning")
        if isinstance(reasoning, dict):
            reasoning.pop("effort", None)
            if reasoning:
                value["reasoning"] = reasoning
            else:
                value.pop("reasoning", None)
        else:
            value.pop("reasoning", None)
        value.pop("thinking_budget", None)
    else:
        reasoning = value.get("reasoning")
        if not isinstance(reasoning, dict):
            reasoning = {}
        # The launcher calls the no-reasoning choice ``off``. Responses APIs,
        # including Whallm's route, call the same wire value ``none``.
        reasoning["effort"] = "none" if effort == "off" else effort
        value["reasoning"] = reasoning
        if effort == "off":
            value.pop("thinking_budget", None)
    if config["backend"] == "omlx" and effort != "auto":
        supported = list(config.get("templateReasoningEfforts") or [])
        if effort not in supported or effort not in THINKING_BUDGETS:
            raise ValueError("The oMLX model template does not support this reasoning effort")
        if effective_output_limit < 2:
            raise ValueError("max_output_tokens is too small for explicit reasoning")
        # Codex may request less than the UI cap. At small ceilings, reserve
        # at least half for the answer/tool call; at normal ceilings retain
        # the selected effort budget without ever exceeding the total cap.
        value["thinking_budget"] = min(THINKING_BUDGETS[effort], effective_output_limit // 2)
        kwargs = value.get("chat_template_kwargs")
        if not isinstance(kwargs, dict):
            kwargs = {}
        kwargs["enable_thinking"] = True
        kwargs["reasoning_effort"] = effort
        value["chat_template_kwargs"] = kwargs
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _response_record(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    nested = value.get("response")
    if isinstance(nested, dict):
        return nested
    if value.get("object") == "response" or "usage" in value:
        return value
    return None


def correct_completed_response_at_limit(value: Any, output_limit: int) -> bool:
    """Relabel a falsely completed Responses result at its exact token cap."""
    if not isinstance(value, dict):
        return False
    response = _response_record(value)
    if response is None:
        return False
    event_completed = value.get("type") == "response.completed"
    if not event_completed and response.get("status") != "completed":
        return False
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return False
    output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
    if (
        isinstance(output_tokens, bool) or not isinstance(output_tokens, int)
        or output_tokens < int(output_limit)
    ):
        return False
    if event_completed:
        value["type"] = "response.incomplete"
    response["status"] = "incomplete"
    response["incomplete_details"] = {"reason": "max_output_tokens"}
    return True


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _output_item_signals(item: Any) -> tuple[bool, bool]:
    """Return whether an output item contains reasoning and usable final output."""
    if not isinstance(item, dict):
        return False, False
    item_type = str(item.get("type") or "")
    reasoning = item_type == "reasoning"
    final_output = item_type.endswith("_call")
    if item_type == "message":
        content = item.get("content")
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                part_type = str(part.get("type") or "")
                if part_type.endswith("_call"):
                    final_output = True
                if part_type in {"output_text", "text"} and _nonempty_text(part.get("text")):
                    final_output = True
                if part_type == "refusal" and (
                    _nonempty_text(part.get("refusal")) or _nonempty_text(part.get("text"))
                ):
                    final_output = True
    return reasoning, final_output


def response_output_signals(value: Any) -> tuple[bool, bool]:
    """Inspect one Responses event/result without retaining its private text."""
    if not isinstance(value, dict):
        return False, False
    event_type = str(value.get("type") or "")
    reasoning = event_type.startswith("response.reasoning")
    final_output = False
    if event_type.startswith("response.output_text"):
        final_output = _nonempty_text(value.get("delta")) or _nonempty_text(value.get("text"))
    elif event_type.startswith("response.refusal"):
        final_output = _nonempty_text(value.get("delta")) or _nonempty_text(value.get("refusal"))
    elif "_call" in event_type:
        final_output = True

    item_reasoning, item_final = _output_item_signals(value.get("item"))
    reasoning = reasoning or item_reasoning
    final_output = final_output or item_final
    response = _response_record(value)
    if response is not None:
        output = response.get("output")
        if isinstance(output, list):
            for item in output:
                item_reasoning, item_final = _output_item_signals(item)
                reasoning = reasoning or item_reasoning
                final_output = final_output or item_final
    return reasoning, final_output


def fail_completed_reasoning_only_response(
    value: Any, *, saw_reasoning: bool = False, saw_final_output: bool = False,
) -> bool:
    """Reject a terminal success that contains thought but no answer or tool call."""
    if not isinstance(value, dict):
        return False
    response = _response_record(value)
    if response is None:
        return False
    event_completed = value.get("type") == "response.completed"
    if not event_completed and response.get("status") != "completed":
        return False
    local_reasoning, local_final = response_output_signals(value)
    if not (saw_reasoning or local_reasoning) or saw_final_output or local_final:
        return False
    if event_completed:
        value["type"] = "response.failed"
    response["status"] = "failed"
    response.pop("incomplete_details", None)
    response["error"] = {
        "code": "reasoning_without_final_output",
        "message": "The local model stopped after reasoning without an answer or tool call.",
    }
    return True


class ResponsesLimitGuard:
    """Hold only the terminal Responses event long enough to verify its usage.

    oMLX-compatible servers can emit ``response.completed`` after consuming the
    complete ``max_output_tokens`` budget. Codex then settles the turn instead
    of offering continuation. Earlier output streams immediately; only the
    terminal event (or one bounded non-stream JSON response) is inspected.
    """

    def __init__(self, output_limit: int, streaming: bool) -> None:
        self.output_limit = max(1, int(output_limit))
        self.streaming = bool(streaming)
        self.pending = bytearray()
        self.terminal = bytearray()
        self.terminal_started = False
        self.disabled = False
        self.saw_reasoning = False
        self.saw_final_output = False

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
        if not payload or payload == b"[DONE]" or len(payload) > MAX_RESPONSE_GUARD_BUFFER:
            return None
        try:
            value = json.loads(payload)
        except (ValueError, UnicodeError, TypeError):
            return None
        return value if isinstance(value, dict) else None

    @classmethod
    def _is_completed_event(cls, event: bytes) -> bool:
        value = cls._event_value(event)
        if value is None:
            return False
        response = _response_record(value)
        return bool(
            value.get("type") == "response.completed"
            or (response is not None and response.get("status") == "completed")
        )

    def _observe_event(self, event: bytes) -> None:
        value = self._event_value(event)
        reasoning, final_output = response_output_signals(value)
        self.saw_reasoning = self.saw_reasoning or reasoning
        self.saw_final_output = self.saw_final_output or final_output

    def _correct_event(self, event: bytes) -> bytes:
        value = self._event_value(event)
        if value is None:
            return event
        corrected = correct_completed_response_at_limit(value, self.output_limit)
        if not corrected:
            corrected = fail_completed_reasoning_only_response(
                value,
                saw_reasoning=self.saw_reasoning,
                saw_final_output=self.saw_final_output,
            )
        if not corrected:
            return event
        response = _response_record(value) or {}
        event_kind = str(value.get("type") or "")
        if not event_kind:
            event_kind = {
                "failed": "response.failed",
                "incomplete": "response.incomplete",
            }.get(str(response.get("status") or ""), "response.completed")
            value["type"] = event_kind
        newline = b"\r\n" if b"\r\n" in event else b"\n"
        output = []
        data_written = False
        for line in event.splitlines():
            if line.startswith(b"event:"):
                output.append(f"event: {event_kind}".encode("utf-8"))
            elif line.startswith(b"data:"):
                if not data_written:
                    output.append(
                        b"data: " + json.dumps(
                            value, ensure_ascii=False, separators=(",", ":"),
                        ).encode("utf-8")
                    )
                    data_written = True
            else:
                output.append(line)
        return newline.join(output) + newline + newline

    def feed(self, chunk: bytes) -> bytes:
        if not chunk:
            return b""
        if self.disabled:
            return chunk
        if not self.streaming:
            if len(self.pending) + len(chunk) > MAX_RESPONSE_GUARD_BUFFER:
                released = bytes(self.pending) + chunk
                self.pending.clear()
                self.disabled = True
                return released
            self.pending.extend(chunk)
            return b""
        if self.terminal_started:
            if len(self.terminal) + len(chunk) > MAX_RESPONSE_GUARD_BUFFER:
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
            self._observe_event(event)
            if self._is_completed_event(event):
                self.terminal_started = True
                self.terminal.extend(event)
                self.terminal.extend(self.pending)
                self.pending.clear()
                break
            released.extend(event)
        if not self.terminal_started and len(self.pending) > MAX_RESPONSE_GUARD_BUFFER:
            released.extend(self.pending)
            self.pending.clear()
            self.disabled = True
        return bytes(released)

    def finish(self) -> bytes:
        if self.disabled:
            return b""
        if not self.streaming:
            payload = bytes(self.pending)
            self.pending.clear()
            try:
                value = json.loads(payload)
            except (ValueError, UnicodeError, TypeError):
                return payload
            corrected = correct_completed_response_at_limit(value, self.output_limit)
            if not corrected:
                corrected = fail_completed_reasoning_only_response(value)
            if corrected:
                return json.dumps(
                    value, ensure_ascii=False, separators=(",", ":"),
                ).encode("utf-8")
            return payload
        if not self.terminal_started:
            released = bytes(self.pending)
            self.pending.clear()
            return released
        self.terminal.extend(self.pending)
        self.pending.clear()
        source = bytearray(self.terminal)
        self.terminal.clear()
        output = bytearray()
        while source:
            event = self._split_event(source)
            if event is None:
                output.extend(source)
                break
            output.extend(self._correct_event(event))
        return bytes(output)


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "LLMLauncherCodexGuard/1"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def send_json_error(self, status: HTTPStatus, message: str) -> None:
        body = json.dumps({"error": {"message": message, "type": "llm_launcher_proxy_error"}}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def allowed_path(self) -> bool:
        return bool(re.fullmatch(
            r"/v1/(?:models|responses(?:/[A-Za-z0-9][A-Za-z0-9._:-]{0,255}){0,3})(?:\?[^#]*)?",
            self.path,
        ))

    def authorised(self) -> bool:
        expected = self.server.config["clientKey"]  # type: ignore[attr-defined]
        return hmac.compare_digest(self.headers.get("Authorization", ""), f"Bearer {expected}")

    def do_GET(self) -> None:
        if self.path == "/health":
            body = b'{"status":"ok"}'
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.forward()

    def do_POST(self) -> None:
        self.forward()

    def do_DELETE(self) -> None:
        self.forward()

    def forward(self) -> None:
        config = self.server.config  # type: ignore[attr-defined]
        if not self.allowed_path():
            self.send_json_error(HTTPStatus.NOT_FOUND, "Unsupported local API path")
            return
        if not self.authorised():
            self.send_json_error(HTTPStatus.UNAUTHORIZED, "Invalid launcher session key")
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
        if config["backend"] == "mtplx" and base_path.startswith("/v1/responses") and base_path != "/v1/responses":
            self.send_json_error(
                HTTPStatus.NOT_IMPLEMENTED,
                "MTPLX does not expose Responses compaction or stored-response routes. Codex remote compaction is disabled for this session.",
            )
            return
        if self.command == "POST" and base_path == "/v1/responses":
            try:
                body = transform_response_request(body, config)
                request_output_limit = int(json.loads(body)["max_output_tokens"])
                if config["backend"] == "mtplx":
                    bridge_request = translate_responses_request(body, config)
                    body = bridge_request.body
                    upstream_path = "/v1/chat/completions"
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                self.send_json_error(HTTPStatus.BAD_REQUEST, str(error) or "Invalid Responses request")
                return
        headers = {
            key: value for key, value in self.headers.items()
            if key.lower() not in HOP_HEADERS | {"authorization", "host", "content-length", "accept-encoding"}
        }
        headers["Authorization"] = f"Bearer {config['upstreamKey']}"
        headers["Accept-Encoding"] = "identity"
        if body:
            headers["Content-Length"] = str(len(body))
        headers["Connection"] = "close"
        connection = http.client.HTTPConnection("127.0.0.1", config["upstreamPort"], timeout=900)
        response_started = False
        try:
            connection.request(self.command, upstream_path, body=body or None, headers=headers)
            upstream = connection.getresponse()
            if bridge_request is not None and 200 <= upstream.status < 300:
                bridge = ChatStreamBridge(bridge_request)
                content_type = (upstream.getheader("Content-Type") or "").lower()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Connection", "close")
                self.end_headers()
                response_started = True
                self.wfile.write(bridge.start())
                self.wfile.flush()
                if "text/event-stream" in content_type:
                    while True:
                        chunk = upstream.read1(16 * 1024)
                        if not chunk:
                            break
                        translated = bridge.feed(chunk)
                        if translated:
                            self.wfile.write(translated)
                            self.wfile.flush()
                    translated = bridge.finish()
                else:
                    payload = upstream.read(MAX_BODY + 1)
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
            upstream_content_type = upstream.getheader("Content-Type") or ""
            limit_guard = (
                ResponsesLimitGuard(
                    request_output_limit,
                    upstream_content_type.lower().startswith("text/event-stream"),
                )
                if request_output_limit is not None and 200 <= upstream.status < 300
                else None
            )
            response_started = True
            self.send_response(upstream.status, upstream.reason)
            for key, value in upstream.getheaders():
                if key.lower() not in HOP_HEADERS and not (
                    limit_guard is not None and key.lower() == "content-length"
                ):
                    self.send_header(key, value)
            self.send_header("Connection", "close")
            self.end_headers()
            while True:
                chunk = upstream.read1(16 * 1024)
                if not chunk:
                    break
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
            pass
        except (OSError, http.client.HTTPException) as error:
            # Once upstream headers have started, a second HTTP status would
            # corrupt the stream. Closing the connection is the only valid
            # signal at that point; before headers, return a normal 502.
            if not response_started and not self.wfile.closed:
                try:
                    self.send_json_error(HTTPStatus.BAD_GATEWAY, f"Local model server error: {error}")
                except OSError:
                    pass
        finally:
            connection.close()
            self.close_connection = True


def main() -> None:
    if len(sys.argv) != 2:
        fail("expected one private configuration file")
    config = load_config(Path(sys.argv[1]))
    server = ThreadingHTTPServer(("127.0.0.1", config["listenPort"]), ProxyHandler)
    server.daemon_threads = True
    server.config = config  # type: ignore[attr-defined]
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
