"""Opt-in pinned real OMP RPC qualification against a synthetic local server.

LLM_LAUNCHER_OMP_RPC_LIVE=1 python3 -m unittest discover -s tests -p test_omp_rpc_installed_integration.py
No model/GPU, downloads, user projects, global config writes or real AI endpoints.
Optional LLM_LAUNCHER_OMP_RPC_REPORT saves sanitized protocol metadata only.
"""
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest

import omp_runtime
import omp_protocol


PINNED_BINARY = Path("/private/tmp/llm-launcher-omp-test/omp")
PINNED_SHA256 = "ab52491643e21b270682691b1319f1161fe2a2658ae4e9a4e3958b1aeb12dcf4"

# Exercise native preparation rejection before admission without contacting a
# model. These intentionally broken extension results exist only in the private
# fixture: ordinary input passes through unchanged. Attachment preparation is
# inside session.prompt's tracked promise; text access is before it exists.
REJECTION_EXTENSION = r'''
export default function fixtureRejections(pi) {
  pi.on("input", event => {
    if (event.text === "NATIVE_PREFLIGHT_REJECT") {
      const images = new Array(1);
      Object.defineProperty(images, 0, {get() { throw new Error("FIXTURE_NATIVE_PREFLIGHT_REJECTION"); }});
      return {images};
    }
    if (event.text === "NATIVE_SETUP_REJECT") {
      return {get text() { throw new Error("FIXTURE_NATIVE_SETUP_REJECTION"); }};
    }
  });
}
'''


class _Peer:
    """Bounded JSONL reader; continue draining stdout through process exit."""
    def __init__(self, process):
        self.process = process
        self.frames = []
        self.condition = threading.Condition()
        self.write_lock = threading.Lock()
        self.transport_lock = threading.Lock()
        self.transport = omp_protocol.Adapter()
        self.adapted = []
        self.negotiation_id = None
        self.error = None
        self.stderr = bytearray()
        self.pending = None
        self.counter = 0
        self.reader = threading.Thread(target=self.read, daemon=True)
        self.errors_reader = threading.Thread(target=self.read_errors, daemon=True)
        self.reader.start(); self.errors_reader.start()

    def read_errors(self):
        while chunk := self.process.stderr.read(4096):
            self.stderr.extend(chunk)
            if len(self.stderr) > 64 * 1024:
                del self.stderr[:-64 * 1024]

    def decode(self, frame):
        if frame.get("type") != "rpc_chunk":
            if self.pending:
                raise AssertionError("Native RPC v2 chunks were interrupted")
            return frame
        identifier, index, count, length = (frame.get(field) for field in ("chunkId", "index", "count", "byteLength"))
        if (not isinstance(identifier, str) or not 1 <= len(identifier) <= 128
                or any(type(value) is not int for value in (index, count, length))
                or not 2 <= count <= 256 or not 0 <= index < count or not 1024 * 1024 <= length <= 64 * 1024**2):
            raise AssertionError("Native RPC v2 chunk metadata exceeded its advertised limits")
        chunk = base64.b64decode(frame["data"], validate=True)
        if not chunk or len(chunk) > 256 * 1024:
            raise AssertionError("Native RPC chunk size is invalid")
        if self.pending is None:
            if index != 0:
                raise AssertionError("Native RPC sequence did not start at zero")
            self.pending = {"id": identifier, "count": count, "length": length, "index": 0, "bytes": bytearray()}
        pending = self.pending
        if (identifier, count, length, index) != (pending["id"], pending["count"], pending["length"], pending["index"]):
            raise AssertionError("Native RPC chunks were interleaved or changed identity")
        pending["bytes"].extend(chunk); pending["index"] += 1
        if len(pending["bytes"]) > length:
            raise AssertionError("Native RPC reassembly exceeded its declared byte count")
        if pending["index"] < count:
            return None
        if len(pending["bytes"]) != length:
            raise AssertionError("Native RPC reassembly length differs")
        self.pending = None
        return json.loads(pending["bytes"].decode("utf-8"))

    def read(self):
        try:
            while line := self.process.stdout.readline(1024 * 1024 + 1):
                if len(line) > 1024 * 1024 or not line.endswith(b"\n"):
                    raise AssertionError("Native RPC physical frame exceeded its limit or lost its newline")
                if not line.strip():
                    continue
                with self.transport_lock:
                    translated = self.transport.receive_line(line)
                    self.adapted.extend(translated.events)
                for command in translated.commands:
                    if command["type"] == "negotiate_protocol":
                        self.negotiation_id = command["id"]
                    self.send_payload(command)
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise AssertionError("Native RPC frame was not an object")
                frame = self.decode(value)
                if frame is not None:
                    with self.condition:
                        self.frames.append(frame)
                        self.condition.notify_all()
            if self.pending:
                raise AssertionError("Native RPC process ended with incomplete v2 chunks")
        except Exception as error:
            self.error = error
        finally:
            with self.condition:
                self.condition.notify_all()

    def wait(self, predicate, timeout=20):
        deadline = time.monotonic() + timeout
        with self.condition:
            while True:
                for frame in self.frames:
                    if predicate(frame):
                        return frame
                if self.error:
                    raise self.error
                if self.process.poll() is not None:
                    raise AssertionError("Pinned OMP exited before the expected RPC frame: " + self.stderr.decode(errors="replace")[-2000:])
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AssertionError("Pinned OMP did not produce the expected RPC frame: " + self.stderr.decode(errors="replace")[-2000:])
                self.condition.wait(min(.1, remaining))

    def send(self, command, *, identifier=None, **fields):
        self.counter += 1
        identifier = identifier or f"native-rpc-{self.counter}"
        payload = {"id": identifier, "type": command, **fields}
        self.send_payload(payload)
        return identifier

    def send_payload(self, payload):
        with self.write_lock:
            with self.transport_lock:
                wire = self.transport.encode_command(payload)
            self.process.stdin.write(wire); self.process.stdin.flush()

    def command(self, command, **fields):
        identifier = self.send(command, **fields)
        response = self.wait(lambda frame: frame.get("type") == "response" and frame.get("id") == identifier)
        if response.get("command") != command or response.get("success") is not True:
            raise AssertionError(f"Native RPC {command} failed: {response.get('error')}")
        return response


@unittest.skipUnless(os.environ.get("LLM_LAUNCHER_OMP_RPC_LIVE") == "1", "Opt-in pinned real OMP RPC")
class InstalledOMPRPCTests(unittest.TestCase):
    def test_native_console_resume_picker_uses_saved_metadata_without_inference(self):
        binary = Path(os.environ.get("LLM_LAUNCHER_OMP_BINARY", str(PINNED_BINARY))).resolve()
        if not binary.is_file():
            self.skipTest("The pinned verified OMP executable is unavailable")
        with binary.open("rb") as handle:
            self.assertEqual(hashlib.file_digest(handle, "sha256").hexdigest(), PINNED_SHA256)
        report = {"binarySha256": PINNED_SHA256, "usesModel": False, "globalConfigWrites": False}
        process = peer = None
        try:
            with tempfile.TemporaryDirectory(prefix="launcher-omp-resume-fixture-") as temporary:
                root = Path(temporary).resolve()
                project = root / "project"; project.mkdir()
                sessions = root / "sessions"; sessions.mkdir()
                (root / "home").mkdir(); (root / "agent").mkdir()
                for directory in ("data", "state", "cache"):
                    (root / directory / "omp").mkdir(parents=True)
                provider = "launcher-splash-resume-fixture"
                timestamp = "2026-10-21T15:42:00.000Z"
                def saved_session(name):
                    path = sessions / f"{name}.jsonl"
                    values = [
                        {"type": "session", "version": 3, "id": name, "timestamp": timestamp,
                         "cwd": str(project), "title": f"Saved {name} conversation"},
                        {"type": "message", "id": "fixture-user", "parentId": None, "timestamp": timestamp,
                         "message": {"role": "user", "content": [{"type": "text", "text": "Saved fixture request"}],
                                     "timestamp": 1792597320000}},
                        {"type": "message", "id": "fixture-answer", "parentId": "fixture-user", "timestamp": timestamp,
                         "message": {"role": "assistant", "content": [{"type": "text", "text": "Saved fixture answer"}],
                                     "api": "openai-completions", "provider": provider, "model": "qwen-resume-fixture",
                                     "stopReason": "stop", "timestamp": 1792597320000,
                                     "usage": {"input": 1, "output": 1, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 2,
                                               "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "total": 0}}}},
                    ]
                    path.write_text("".join(json.dumps(value) + "\n" for value in values))
                    return path
                current = saved_session("current")
                target = saved_session("target")
                plan = SimpleNamespace(agent_host="terminal", run_dir=root, run_id="omp-resume-fixture",
                    backend="splash", model={"name": "Synthetic resume fixture", "backends": {"splash": {
                        "agentReasoning": ["off"]}}}, context=8192, output=512, reasoning="off", client_env={}, warnings=[])
                omp_runtime.build_client(plan, SimpleNamespace(served="qwen-resume-fixture",
                    base_url="http://127.0.0.1:9/v1", api_key="resume-fixture-only"),
                    binary=str(binary), app_dir=Path(__file__).resolve().parents[1], provider=provider, inputs=["text"])
                env = {"PATH": os.environ["PATH"], "HOME": str(root / "home"), "TMPDIR": str(root),
                       "PI_CODING_AGENT_DIR": str(root / "agent"), "XDG_DATA_HOME": str(root / "data"),
                       "XDG_STATE_HOME": str(root / "state"), "XDG_CACHE_HOME": str(root / "cache"),
                       "LLM_LAUNCHER_AGENT_HOST": "console", **plan.client_env}
                argv = [str(binary), "--no-extensions", "--no-skills", "--no-rules", "--no-title", "--no-lsp",
                        "--no-prewalk", "--no-pty", *plan.client_argv[1:], "--tools", "read", "--mode", "rpc",
                        "--session-dir", str(sessions), "--session", str(current)]
                process = subprocess.Popen(argv, cwd=project, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, start_new_session=True)
                peer = _Peer(process)
                peer.wait(lambda frame: frame.get("type") == "ready")
                peer.wait(lambda frame: frame.get("command") == "negotiate_protocol" and frame.get("success") is True)
                state = peer.command("get_state")
                self.assertEqual(Path(state["data"]["sessionFile"]), current)
                commands = peer.command("get_available_commands")["data"]["commands"]
                resume = next(command for command in commands if command["name"] == "resume")
                self.assertEqual(resume["source"], "extension")
                resume_start = len(peer.frames)
                identifier = peer.send("prompt", message="/resume")
                selector = peer.wait(lambda frame: frame.get("type") == "extension_ui_request" and frame.get("method") == "select")
                self.assertEqual(len(selector["options"]), 1)
                self.assertIn("Saved target conversation", selector["options"][0])
                peer.send_payload({"type": "extension_ui_response", "id": selector["id"], "value": selector["options"][0]})
                selected = peer.wait(lambda frame: frame.get("type") == "extension_ui_request" and
                    frame.get("method") == "setStatus" and frame.get("statusKey") == "launcher.resumeSession" and
                    isinstance(frame.get("statusText"), str))
                self.assertEqual(json.loads(selected["statusText"]), {"sessionPath": str(target)})
                response = peer.wait(lambda frame: frame.get("type") == "response" and frame.get("id") == identifier)
                self.assertTrue(response["success"])
                result = peer.wait(lambda frame: frame.get("type") == "prompt_result" and frame.get("id") == identifier)
                self.assertFalse(result["agentInvoked"])
                self.assertEqual(result["status"], "completed")
                self.assertTrue(result["sessionSettled"])
                self.assertTrue(peer.command("get_state")["data"]["isSettled"])
                # A second, cancelled picker must clear the prior pending choice.
                start = len(peer.frames)
                cancel_id = peer.send("prompt", message="/resume")
                peer.wait(lambda frame: frame in peer.frames[start:] and frame.get("type") == "extension_ui_request" and
                    frame.get("method") == "setStatus" and frame.get("statusKey") == "launcher.resumeSession" and
                    "statusText" not in frame)
                cancelled_selector = peer.wait(lambda frame: frame in peer.frames[start:] and
                    frame.get("type") == "extension_ui_request" and frame.get("method") == "select")
                peer.send_payload({"type": "extension_ui_response", "id": cancelled_selector["id"], "cancelled": True})
                cancelled_response = peer.wait(lambda frame: frame.get("type") == "response" and frame.get("id") == cancel_id)
                self.assertTrue(cancelled_response["success"])
                cancelled_result = peer.wait(lambda frame: frame.get("type") == "prompt_result" and frame.get("id") == cancel_id)
                self.assertFalse(cancelled_result["agentInvoked"])
                self.assertEqual(cancelled_result["status"], "completed")
                self.assertFalse(any(frame.get("type") == "agent_start" for frame in peer.frames))
                self.assertFalse(any(frame.get("type") == "extension_error" for frame in peer.frames))
                self.assertEqual(sum(frame.get("statusKey") == "launcher.resumeSession" and
                    isinstance(frame.get("statusText"), str) for frame in peer.frames), 1)
                report.update({"resumeCommand": resume, "nativeSessionManagerImport": True,
                    "selection": {"method": selector["method"], "optionCount": len(selector["options"])},
                    "selectionStatusShape": sorted(selected), "selectionPayloadKeys": sorted(json.loads(selected["statusText"])),
                    "selectionMatchesListedFixture": True, "currentSessionOmitted": True,
                    "localCommandResponse": {key: response[key] for key in ("type", "command", "success", "data") if key in response},
                    "localCommandResult": {key: result[key] for key in ("type", "status", "agentInvoked", "sessionSettled")},
                    "selectionFrameOrder": [frame.get("method", frame["type"])
                        for frame in peer.frames[resume_start:start]
                        if frame.get("id") == identifier or frame.get("method") in {"setStatus", "select"}],
                    "cancelClearsPreviousSelection": True, "agentStarted": False})
                process.stdin.close(); process.wait(timeout=15)
                peer.reader.join(3); peer.errors_reader.join(3)
                self.assertEqual(process.returncode, 0, peer.stderr.decode(errors="replace")[-2000:])
                self.assertIsNone(peer.error)
                report.update({"cleanStdinEofExit": True, "success": True})
        finally:
            if error := sys.exc_info()[1]:
                report.update({"success": False, "errorType": type(error).__name__})
            if process is not None and process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM); process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
                except ProcessLookupError:
                    pass
            if peer is not None:
                peer.reader.join(3); peer.errors_reader.join(3)
            if process is not None:
                for pipe in (process.stdin, process.stdout, process.stderr):
                    if pipe is not None and not pipe.closed:
                        pipe.close()
            if destination := os.environ.get("LLM_LAUNCHER_OMP_RESUME_REPORT"):
                Path(destination).write_text(json.dumps(report, indent=2) + "\n")

    def test_native_rpc_v2_tools_history_second_prompt_abort_and_local_slash(self):
        binary = Path(os.environ.get("LLM_LAUNCHER_OMP_BINARY", str(PINNED_BINARY)))
        if not binary.is_file():
            self.skipTest("The pinned verified OMP executable is unavailable")
        with binary.open("rb") as handle:
            self.assertEqual(hashlib.file_digest(handle, "sha256").hexdigest(), PINNED_SHA256)
        requests = []
        hold_received = threading.Event(); release_hold = threading.Event()
        report = {"binarySha256": PINNED_SHA256, "usesModel": False, "globalConfigWrites": False}

        class Responder(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append({"path": self.path, "authorization": self.headers.get("Authorization"), "body": body})
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Connection", "close"); self.end_headers()
                self.close_connection = True
                def chunk(delta, finish=None, usage=None):
                    value = {"id": "rpc-fixture", "object": "chat.completion.chunk", "created": 1,
                             "model": "qwen-rpc-fixture", "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
                    if usage:
                        value["usage"] = usage
                    self.wfile.write(("data: " + json.dumps(value) + "\n\n").encode()); self.wfile.flush()
                latest_user = next(message for message in reversed(body["messages"]) if message["role"] == "user")
                text = json.dumps(latest_user.get("content"))
                chunk({"role": "assistant"})
                if "RPC_ABORT_HOLD" in text:
                    hold_received.set()
                    chunk({"reasoning_content": "Synthetic waiting reasoning."})
                    try:
                        while not release_hold.wait(.05):
                            self.wfile.write(b": fixture heartbeat\n\n"); self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        return
                    return
                second = "SECOND_RPC_CHECK" in text
                has_tool = any(message.get("role") == "tool" for message in body["messages"])
                thinking = "Second synthetic reasoning." if second else "Synthetic reasoning to preserve."
                chunk({"reasoning_content": thinking})
                if second or has_tool:
                    chunk({"content": "SECOND_RPC_OK" if second else "FIRST_RPC_OK"})
                    chunk({}, "stop", {"prompt_tokens": 80, "completion_tokens": 12, "total_tokens": 92})
                else:
                    chunk({"tool_calls": [{"index": 0, "id": "rpc-fixture-read", "type": "function",
                           "function": {"name": "read", "arguments": '{"path":"fixture'}}]})
                    chunk({"tool_calls": [{"index": 0, "function": {"arguments": '.txt"}'}}]})
                    chunk({}, "tool_calls", {"prompt_tokens": 40, "completion_tokens": 10, "total_tokens": 50})
                self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()

        server = ThreadingHTTPServer(("127.0.0.1", 0), Responder); server.daemon_threads = True
        server_thread = threading.Thread(target=server.serve_forever, daemon=True); server_thread.start()
        process = None; peer = None
        rejected_id = setup_id = None
        try:
            with tempfile.TemporaryDirectory(prefix="launcher-omp-rpc-fixture-") as temporary:
                root = Path(temporary).resolve()
                project = root / "project"; project.mkdir()
                (project / "fixture.txt").write_text("SYNTHETIC_RPC_SENTINEL\n")
                rejection_extension = root / "fixture-rejections.mjs"
                rejection_extension.write_text(REJECTION_EXTENSION)
                (root / "agent").mkdir(); (root / "data/omp").mkdir(parents=True)
                provider = "launcher-splash-rpc-fixture"
                plan = SimpleNamespace(agent_host="terminal", run_dir=root, run_id="omp-rpc-fixture",
                    backend="splash", model={"name": "Synthetic RPC Qwen", "backends": {"splash": {
                        "agentReasoning": ["off", "low", "medium", "high"]}}},
                    context=8192, output=512, reasoning="low", client_env={}, warnings=[])
                omp_runtime.build_client(plan, SimpleNamespace(served="qwen-rpc-fixture",
                    base_url=f"http://127.0.0.1:{server.server_address[1]}/v1", api_key="rpc-fixture-only"),
                    binary=str(binary), app_dir=Path(__file__).resolve().parents[1], provider=provider, inputs=["text"])
                env = {"PATH": os.environ["PATH"], "TMPDIR": str(root), "PI_CODING_AGENT_DIR": str(root / "agent"),
                       "XDG_DATA_HOME": str(root / "data"), "PI_SMOL_MODEL": "unavailable-cloud/conflicting-small",
                       "PI_SLOW_MODEL": "unavailable-cloud/conflicting-large", "PI_PLAN_MODEL": "unavailable-cloud/conflicting-plan",
                       **plan.client_env}
                argv = [str(binary), "--no-extensions", "--no-skills", "--no-rules", "--no-title", "--no-session",
                        "--no-lsp", "--no-prewalk", "--no-pty", "--no-ui", *plan.client_argv[1:],
                        "--extension", str(rejection_extension),
                        "--tools", "read", "--mode", "rpc"]
                process = subprocess.Popen(argv, cwd=project, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, start_new_session=True)
                peer = _Peer(process)
                ready = peer.wait(lambda frame: frame.get("type") == "ready")
                self.assertEqual(ready["protocolVersion"], 1)
                self.assertIn(2, ready["supportedProtocolVersions"])
                self.assertEqual(ready["maxFrameBytes"], 1024 * 1024)
                self.assertEqual(ready["maxReassembledFrameBytes"], 64 * 1024**2)
                negotiated = peer.wait(lambda frame: frame.get("type") == "response" and
                    frame.get("command") == "negotiate_protocol" and frame.get("id") == peer.negotiation_id)
                self.assertTrue(negotiated["success"])
                self.assertEqual(negotiated["data"]["protocolVersion"], 2)
                report.update({"ready": ready, "negotiateResponse": negotiated})
                commands = peer.command("get_available_commands")
                self.assertIsInstance(commands["data"]["commands"], list)
                messages = peer.command("get_messages")
                self.assertEqual(messages["data"]["messages"], [])
                state = peer.command("get_state")
                data = state["data"]
                self.assertEqual(data["model"]["provider"], provider)
                self.assertEqual(data["model"]["id"], "qwen-rpc-fixture")
                self.assertEqual(data["model"]["contextWindow"], 8192)
                self.assertEqual(data["model"]["maxTokens"], 512)
                self.assertEqual(data["thinkingLevel"], "low")
                self.assertTrue(data["isSettled"]); self.assertFalse(data["hasPendingAsyncWork"])
                self.assertTrue(peer.transport.can_input)
                report.update({"initialState": {key: data[key] for key in ("thinkingLevel", "isStreaming", "isCompacting", "isSettled", "hasPendingAsyncWork", "queuedMessageCount", "messageCount")},
                    "model": {key: data["model"][key] for key in ("id", "provider", "contextWindow", "maxTokens")},
                    "availableCommandNames": [command["name"] for command in commands["data"]["commands"]]})
                report["nativeStateResponse"] = {key: state[key] for key in ("id", "type", "command", "success")}
                report["nativeStateResponse"]["data"] = {**report["initialState"], "model": report["model"],
                    "queuedMessages": data["queuedMessages"], "steeringMode": data["steeringMode"],
                    "followUpMode": data["followUpMode"]}
                event_filter = peer.command("set_event_filter", events=None, messageUpdates="delta")
                self.assertIsNone(event_filter["data"]["events"])
                self.assertEqual(event_filter["data"]["messageUpdates"], "delta")
                report["eventFilterResponse"] = event_filter
                rejection_start = len(peer.frames)
                rejected_id = peer.send("prompt", message="NATIVE_PREFLIGHT_REJECT")
                rejected_result = peer.wait(lambda frame: frame.get("type") == "prompt_result" and frame.get("id") == rejected_id)
                self.assertEqual(rejected_result["status"], "error")
                self.assertFalse(rejected_result["agentInvoked"])
                self.assertTrue(rejected_result["sessionSettled"])
                self.assertEqual(rejected_result["error"]["message"], "FIXTURE_NATIVE_PREFLIGHT_REJECTION")
                rejected_frames = [frame for frame in peer.frames[rejection_start:] if frame.get("id") == rejected_id]
                self.assertEqual([frame["type"] for frame in rejected_frames], ["response", "response", "prompt_result"])
                self.assertEqual([frame.get("success") for frame in rejected_frames[:2]], [False, True])
                self.assertFalse(any(frame.get("type") == "agent_start" for frame in peer.frames[rejection_start:]))
                self.assertFalse(requests, "Native preparation rejection must not reach a model")
                self.assertFalse(peer.transport.busy, "Correlated rejection must not leave the adapter busy")
                self.assertTrue(peer.transport.can_input)
                rejection_controls = [frame for frame in peer.adapted if frame.get("id") == rejected_id]
                self.assertTrue(rejection_controls[0].get("ompAwaitingPromptResult"),
                    "The first failure must retain the prompt until the authoritative result")
                self.assertFalse(any(frame.get("type") == "agent_settled" for frame in rejection_controls[:-1]),
                    "The initial failure must not prematurely release a follow-up")
                setup_start = len(peer.frames)
                setup_id = peer.send("prompt", message="NATIVE_SETUP_REJECT")
                setup_error = peer.wait(lambda frame: frame.get("type") == "response" and frame.get("id") == setup_id)
                self.assertFalse(setup_error["success"])
                self.assertEqual(setup_error["error"], "FIXTURE_NATIVE_SETUP_REJECTION")
                setup_state = peer.command("get_state")
                self.assertTrue(setup_state["data"]["isSettled"])
                self.assertFalse(setup_state["data"]["hasPendingAsyncWork"])
                self.assertFalse(peer.transport.busy, "Ordered settled state must reconcile an outer setup rejection")
                self.assertTrue(peer.transport.can_input)
                self.assertFalse(any(frame.get("type") == "prompt_result" and frame.get("id") == setup_id
                    for frame in peer.frames[setup_start:]))
                self.assertFalse(requests)
                report["nativePreflightRejection"] = [{key: frame[key] for key in
                    ("type", "id", "command", "success", "error", "status", "agentInvoked", "sessionSettled") if key in frame}
                    for frame in rejected_frames]
                report["nativeSetupRejection"] = setup_error
                report["setupReconciledByOrderedState"] = True
                first = peer.command("prompt", message="Read fixture.txt using the read tool, then respond FIRST_RPC_OK.")
                first_result = peer.wait(lambda frame: frame.get("type") == "prompt_result" and frame.get("id") == first["id"])
                self.assertEqual(first_result["status"], "completed"); self.assertTrue(first_result["agentInvoked"])
                self.assertTrue(first_result["sessionSettled"])
                report["firstPromptResult"] = first_result
                after_read = peer.command("get_messages")
                history = after_read["data"]["messages"]
                self.assertIn("SYNTHETIC_RPC_SENTINEL", json.dumps(history))
                self.assertIn("FIRST_RPC_OK", json.dumps(history))
                self.assertTrue(any(message.get("role") == "toolResult" for message in history))
                self.assertTrue(any(frame.get("type") == "tool_execution_start" and frame.get("toolName") == "read" for frame in peer.frames))
                second = peer.command("prompt", message="SECOND_RPC_CHECK: respond SECOND_RPC_OK.")
                second_result = peer.wait(lambda frame: frame.get("type") == "prompt_result" and frame.get("id") == second["id"])
                self.assertEqual(second_result["status"], "completed")
                report["secondPromptResult"] = second_result
                self.assertIn("SECOND_RPC_OK", json.dumps(peer.command("get_messages")["data"]["messages"]))
                hold = peer.command("prompt", message="RPC_ABORT_HOLD: wait for cancellation.")
                self.assertTrue(hold_received.wait(10))
                during = peer.command("get_state")
                self.assertTrue(during["data"]["isStreaming"]); self.assertFalse(during["data"]["isSettled"])
                aborted = peer.command("abort")
                hold_result = peer.wait(lambda frame: frame.get("type") == "prompt_result" and frame.get("id") == hold["id"])
                self.assertEqual(hold_result["status"], "aborted")
                self.assertTrue(hold_result["sessionSettled"])
                report["abortedPromptResult"] = hold_result
                settled = peer.command("get_state")
                self.assertTrue(settled["data"]["isSettled"]); self.assertFalse(settled["data"]["isStreaming"])
                count = len(requests)
                self.assertIn("stats", report["availableCommandNames"])
                local = peer.command("prompt", message="/stats")
                if (local.get("data") or {}).get("agentInvoked") is False:
                    local_result = None
                else:
                    local_result = peer.wait(lambda frame: frame.get("type") == "prompt_result" and frame.get("id") == local["id"])
                    self.assertFalse(local_result["agentInvoked"])
                self.assertEqual(len(requests), count, "The native local slash command must not call any model")
                self.assertEqual(len(requests), 4)
                for request in requests:
                    self.assertEqual(request["path"], "/v1/chat/completions")
                    self.assertEqual(request["authorization"], "Bearer rpc-fixture-only")
                    self.assertEqual(request["body"]["model"], "qwen-rpc-fixture")
                    self.assertEqual(request["body"]["max_tokens"], 512)
                    self.assertNotIn("store", request["body"])
                    self.assertNotIn("reasoning_effort", request["body"])
                assistant = next(message for message in requests[1]["body"]["messages"] if message["role"] == "assistant")
                self.assertEqual(assistant["reasoning_content"], "Synthetic reasoning to preserve.")
                self.assertIn("SYNTHETIC_RPC_SENTINEL", json.dumps(requests[1]["body"]["messages"]))
                self.assertTrue(any(message.get("reasoning_content") == "Synthetic reasoning to preserve."
                                    for message in requests[2]["body"]["messages"] if message["role"] == "assistant"))
                updates = [frame for frame in peer.frames if frame.get("type") == "message_update"]
                self.assertTrue(updates, "The actual agent must emit projected deltas")
                for frame in updates:
                    self.assertEqual(set(frame["message"]), {"role"})
                    self.assertNotIn("partial", frame["assistantMessageEvent"])
                    self.assertIsInstance(frame["messageId"], str)
                self.assertTrue(any((frame.get("assistantMessageEvent") or {}).get("type") == "thinking_delta" for frame in updates))
                self.assertTrue(any((frame.get("assistantMessageEvent") or {}).get("type") == "text_delta" for frame in updates))
                report.update({"ready": ready, "negotiateResponse": negotiated, "availableCommandCount": len(commands["data"]["commands"]),
                    "initialState": {key: data[key] for key in ("thinkingLevel", "isStreaming", "isCompacting", "isSettled", "hasPendingAsyncWork", "queuedMessageCount", "messageCount")},
                    "model": {key: data["model"][key] for key in ("id", "provider", "contextWindow", "maxTokens")},
                    "firstPromptResult": first_result, "secondPromptResult": second_result, "abortedPromptResult": hold_result,
                    "localSlashResponse": local, "localSlashResult": local_result,
                    "authenticatedExactRequests": len(requests), "actualReadVerified": True, "reasoningReplayVerified": True,
                    "secondPromptVerified": True, "abortVerified": True,
                    "rejectionRecoveryVerified": True,
                    "adapterQualified": peer.transport.can_input,
                    "adapterPromptResults": [{key: frame.get(key) for key in ("type", "id", "status", "agentInvoked", "sessionSettled", "sessionBusy")}
                        for frame in peer.adapted if frame.get("type") == "launcher_prompt_result"],
                    "adapterSessionSettlementObserved": any(frame.get("type") == "agent_settled" for frame in peer.adapted),
                    "deltaProjectionVerified": True,
                    "nativeDeltaSubtypes": sorted({frame["assistantMessageEvent"]["type"] for frame in updates}),
                    "nativeEventShapes": {kind: sorted(next(frame for frame in peer.frames if frame.get("type") == kind))
                        for kind in ("message_start", "message_update", "message_end", "tool_execution_start", "tool_execution_end", "session_settled")
                        if any(frame.get("type") == kind for frame in peer.frames)},
                    "nativeQueueStateShape": sorted(settled["data"]["queuedMessages"]),
                    "nativeHistoryRoles": sorted({message["role"] for message in history}),
                    "localBuiltin": "stats",
                    "messageEventHasId": any(frame.get("type") == "message_end" and isinstance(frame.get("messageId"), str) for frame in peer.frames)})
                process.stdin.close()
                process.wait(timeout=15)
                peer.reader.join(3); peer.errors_reader.join(3)
                self.assertEqual(process.returncode, 0, peer.stderr.decode(errors="replace")[-2000:])
                self.assertIsNone(peer.error)
                report["cleanStdinEofExit"] = True
                report["success"] = True
        finally:
            if error := sys.exc_info()[1]:
                report["success"] = False
                report["errorType"] = type(error).__name__
            release_hold.set()
            if process is not None and process.poll() is None:
                # The fixture owns this fresh session/process group only.
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
                except ProcessLookupError:
                    pass
            if peer is not None:
                peer.reader.join(3); peer.errors_reader.join(3)
                report["rejectionFrameTrace"] = [{key: frame[key] for key in
                    ("type", "id", "command", "success", "error", "status", "agentInvoked", "sessionSettled") if key in frame}
                    for frame in peer.frames if frame.get("id") in {rejected_id, setup_id} and frame.get("id") is not None]
                report["syntheticRequestCount"] = len(requests)
                report["adapterBusyAtExit"] = peer.transport.busy
                report["adapterQualifiedAtExit"] = peer.transport.can_input
                if peer.error is not None:
                    report["adapterOrFrameError"] = f"{type(peer.error).__name__}: {peer.error}"
            if process is not None:
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream is not None and not stream.closed:
                        stream.close()
            server.shutdown(); server.server_close(); server_thread.join(3)
            report["ownedAgentStopped"] = process is not None and process.poll() is not None
            if path := os.environ.get("LLM_LAUNCHER_OMP_RPC_REPORT"):
                destination = Path(path); destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
