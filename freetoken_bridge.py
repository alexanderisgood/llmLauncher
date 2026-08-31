#!/usr/bin/env python3
"""Private loopback bridge to one launcher-approved OpenAI-compatible server."""

from __future__ import annotations

import hmac
import http.client
import json
import os
import re
import ssl
import stat
import sys
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


VERSION = "1.0"
MAX_BODY = 128 * 1024 * 1024
MAX_MODELS_BODY = 4 * 1024 * 1024
HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}


def fail(message: str) -> None:
    print(f"LLM Launcher private bridge: {message}", file=sys.stderr)
    raise SystemExit(2)


def _private_config_path(path: Path) -> Path:
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
    return resolved


def load_config(path: Path) -> dict[str, Any]:
    resolved = _private_config_path(path)
    try:
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as error:
        fail(f"cannot read configuration: {error}")
    if not isinstance(value, dict):
        fail("configuration is not an object")
    listen_port = value.get("listenPort")
    if isinstance(listen_port, bool) or not isinstance(listen_port, int) or not 1_024 <= listen_port <= 65_535:
        fail("invalid listen port")
    for key in ("clientKey", "endpoint", "servedModel"):
        if not isinstance(value.get(key), str) or not value[key] or "\0" in value[key]:
            fail(f"invalid {key}")
    if not 16 <= len(value["clientKey"]) <= 512 or len(value["servedModel"]) > 512:
        fail("invalid bridge identity")
    upstream_key = value.get("upstreamKey", "")
    if not isinstance(upstream_key, str) or len(upstream_key) > 4_096 or "\0" in upstream_key:
        fail("invalid upstream key")
    upstream_label = value.get("upstreamLabel", "FreeToken")
    if (
        not isinstance(upstream_label, str) or not upstream_label
        or len(upstream_label) > 40 or not re.fullmatch(r"[A-Za-z0-9 ._-]+", upstream_label)
    ):
        fail("invalid upstream label")
    parsed = urllib.parse.urlsplit(value["endpoint"])
    if (
        parsed.scheme not in {"http", "https"} or not parsed.hostname
        or parsed.username is not None or parsed.password is not None
        or parsed.query or parsed.fragment or parsed.path not in {"", "/"}
    ):
        fail("invalid upstream endpoint")
    value["upstreamKey"] = upstream_key
    value["upstreamLabel"] = upstream_label
    value["parsedEndpoint"] = parsed
    return value


class BridgeHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "LLMLauncherFreeTokenBridge/1"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def send_json_error(self, status: HTTPStatus, message: str) -> None:
        if getattr(self, "_response_started", False):
            return
        body = json.dumps({
            "error": {"message": message, "type": "llm_launcher_freetoken_bridge_error"},
        }, separators=(",", ":")).encode("utf-8")
        self._response_started = True
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def authorised(self) -> bool:
        expected = self.server.config["clientKey"]  # type: ignore[attr-defined]
        return hmac.compare_digest(
            self.headers.get("Authorization", ""), f"Bearer {expected}",
        )

    def allowed_path(self) -> bool:
        return bool(re.fullmatch(
            r"/v1/(?:models|chat/completions|responses(?:/[A-Za-z0-9][A-Za-z0-9._:-]{0,255}){0,3})(?:\?[^#]*)?",
            self.path,
        ))

    def do_GET(self) -> None:
        if self.path == "/health":
            body = json.dumps({
                "status": "ok",
                "upstream": self.server.config["upstreamLabel"],  # type: ignore[attr-defined]
            }, separators=(",", ":")).encode("utf-8")
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

    def _request_body(self) -> bytes:
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("Chunked request bodies are unsupported")
        if self.headers.get("Content-Encoding", "identity").lower() not in {"", "identity"}:
            raise ValueError("Compressed request bodies are unsupported")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid request length") from error
        if not 0 <= length <= MAX_BODY:
            raise ValueError("Request body is too large")
        return self.rfile.read(length) if length else b""

    def _validate_model_contract(self, body: bytes) -> None:
        if not body or self.command not in {"POST", "PUT", "PATCH"}:
            return
        path = self.path.split("?", 1)[0]
        if path not in {"/v1/chat/completions", "/v1/responses"}:
            return
        try:
            value = json.loads(body)
        except (ValueError, UnicodeError) as error:
            raise ValueError("Request body must be valid JSON") from error
        if not isinstance(value, dict) or value.get("model") != self.server.config["servedModel"]:  # type: ignore[attr-defined]
            label = self.server.config.get("upstreamLabel", "FreeToken")  # type: ignore[attr-defined]
            raise ValueError(f"Request targets a different {label} model")

    def _connection(self) -> http.client.HTTPConnection:
        parsed = self.server.config["parsedEndpoint"]  # type: ignore[attr-defined]
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if parsed.scheme == "https":
            return http.client.HTTPSConnection(
                parsed.hostname, port, timeout=900,
                context=ssl.create_default_context(),
            )
        return http.client.HTTPConnection(parsed.hostname, port, timeout=900)

    def _request_headers(self, body: bytes) -> dict[str, str]:
        headers: dict[str, str] = {}
        for key, value in self.headers.items():
            lowered = key.lower()
            if lowered in HOP_HEADERS or lowered in {"host", "authorization", "content-length"}:
                continue
            headers[key] = value
        upstream_key = self.server.config["upstreamKey"]  # type: ignore[attr-defined]
        if upstream_key:
            headers["Authorization"] = f"Bearer {upstream_key}"
        if body:
            headers["Content-Length"] = str(len(body))
        return headers

    def _send_models(self, response: http.client.HTTPResponse) -> None:
        body = response.read(MAX_MODELS_BODY + 1)
        if len(body) > MAX_MODELS_BODY:
            raise ValueError("Upstream model catalog is too large")
        try:
            value = json.loads(body)
        except (ValueError, UnicodeError) as error:
            raise ValueError("Upstream returned an invalid model catalog") from error
        data = value.get("data") if isinstance(value, dict) else None
        served = self.server.config["servedModel"]  # type: ignore[attr-defined]
        matches = [
            item for item in data or []
            if isinstance(item, dict) and str(item.get("id") or "") == served
        ]
        if not matches:
            raise ValueError("The configured upstream model is no longer served")
        filtered = json.dumps({"object": "list", "data": matches}, separators=(",", ":")).encode("utf-8")
        self._response_started = True
        self.send_response(response.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(filtered)))
        self.send_header("X-FreeToken-Bridge", VERSION)
        self.end_headers()
        self.wfile.write(filtered)

    def _send_stream(self, response: http.client.HTTPResponse) -> None:
        self._response_started = True
        self.send_response(response.status)
        for key, value in response.getheaders():
            lowered = key.lower()
            if lowered in HOP_HEADERS or lowered in {"content-length", "server", "date"}:
                continue
            self.send_header(key, value)
        self.send_header("X-FreeToken-Bridge", VERSION)
        self.end_headers()
        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            self.wfile.write(chunk)
            self.wfile.flush()

    def forward(self) -> None:
        if not self.allowed_path():
            self.send_json_error(HTTPStatus.NOT_FOUND, "Unsupported private API path")
            return
        if not self.authorised():
            self.send_json_error(HTTPStatus.UNAUTHORIZED, "Invalid launcher route key")
            return
        connection: http.client.HTTPConnection | None = None
        try:
            body = self._request_body()
            self._validate_model_contract(body)
            connection = self._connection()
            connection.request(
                self.command, self.path, body=body or None,
                headers=self._request_headers(body),
            )
            response = connection.getresponse()
            if self.command == "GET" and self.path.split("?", 1)[0] == "/v1/models" and response.status < 400:
                self._send_models(response)
            else:
                self._send_stream(response)
        except (OSError, http.client.HTTPException, ValueError) as error:
            if not self.wfile.closed and not getattr(self, "_response_started", False):
                try:
                    self.send_json_error(HTTPStatus.BAD_GATEWAY, str(error))
                except (BrokenPipeError, ConnectionResetError):
                    pass
        finally:
            if connection is not None:
                connection.close()


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "--version":
        print(f"FreeToken remote bridge {VERSION}")
        return
    if len(sys.argv) != 2:
        fail("usage: freetoken_bridge.py CONFIG")
    config = load_config(Path(sys.argv[1]))
    server = ThreadingHTTPServer(("127.0.0.1", config["listenPort"]), BridgeHandler)
    server.daemon_threads = True
    server.config = config  # type: ignore[attr-defined]
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
