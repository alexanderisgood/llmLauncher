"""Isolated UI fixture: real installed Pi and controller handlers, no model.

Run only as a child of test_pi_hub_browser.js. All agent configuration and
session files live in its disposable directory; no user tools or credentials.
"""
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import launcher
import omlx_hub_runtime


def main():
    if os.environ.get("LLM_LAUNCHER_PI_HUB_BROWSER") != "1":
        raise SystemExit("Explicit browser integration flag required")
    binary = shutil.which("pi")
    if not binary:
        raise SystemExit("Installed Pi required")
    stop = threading.Event()
    release = threading.Event()
    requests = []
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    class Responder(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert self.path == "/v1/chat/completions"
            assert not body.get("tools"), "Fixture must never expose tools"
            content = [m["content"] for m in body["messages"] if m["role"] == "user"][-1]
            prompt = content if isinstance(content, str) else "".join(p.get("text", "") for p in content)
            requests.append(prompt)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True

            def chunk(delta, finish=None):
                data = {"id":"browser-fixture", "object":"chat.completion.chunk",
                    "created":1, "model":"hub-fixture",
                    "choices":[{"index":0, "delta":delta, "finish_reason":finish}]}
                if finish:
                    data["usage"] = {"prompt_tokens":1200, "completion_tokens":200,
                        "total_tokens":1400, "prompt_tokens_details":{"cached_tokens":400}}
                self.wfile.write(("data: " + json.dumps(data) + "\n\n").encode())
                self.wfile.flush()

            try:
                if prompt == "prefill":
                    request = {"id":"prefill-fixture", "surfaceId":plan.run_id,
                        "state":"running", "startedAt":datetime.now(timezone.utc).isoformat(),
                        "firstOutputSeconds":None, "runSeconds":0,
                        "liveTelemetry":{"source":"omlx-activity", "phase":"prefill", "metricKind":"prefill"}}
                    manager._session_proxy_api = lambda *args, **kwargs: {
                        "active":[request] if request["state"] == "running" else [],
                        "activeCount":int(request["state"] == "running"), "queuedCount":0,
                        "recent":[] if request["state"] == "running" else [request],
                        "state":"busy" if request["state"] == "running" else "idle"}
                    time.sleep(12)
                    request.update(firstOutputSeconds=12, promptProcessing={
                        "source":"omlx-dflash-prefill", "tokensPerSecond":320.5,
                        "processedTokens":641,"cachedTokens":40000})
                    request["liveTelemetry"].update(phase="decode", metricKind="decode")
                    chunk({"reasoning_content":"Prefill finished; generating now."})
                    time.sleep(8)
                    request["state"] = "completed"
                chunk({"role":"assistant", "reasoning_content":"Generated reasoning for " + prompt + "."})
                if prompt == "scroll":
                    # Follow through long thinking, a tall live tool card, its
                    # automatic collapse, and another round of thinking.
                    first = body["messages"][-1]["role"] == "user"
                    for i in range(550):
                        if stop.is_set(): return
                        chunk({"reasoning_content":f"\n{'Before tool' if first else 'After tool'} thinking line {i:03d}."})
                        time.sleep(.035)
                    if first:
                        chunk({"tool_calls":[{"index":0,"id":"scroll-tool","type":"function","function":{
                            "name":"write","arguments":json.dumps({"path":"fixture.txt","content":"Generated code line\n" * 500})}}]})
                        time.sleep(3)
                        chunk({}, "tool_calls")
                        self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()
                        return
                elif prompt == "long":
                    # Cross the real 512-event delivery-journal bound, while
                    # keeping the visible conversation comfortably within its cap.
                    for i in range(600):
                        if stop.is_set():
                            return
                        chunk({"content":f"Line {i:03d}: generated browser scroll fixture.\n"})
                        time.sleep(0.012)
                    release.wait(30)
                elif prompt == "buffered" and body["messages"][-1]["role"] == "user":
                    writer = omlx_hub_runtime.PreviewWriter(root / "tool-preview.json", "chatcmpl-12345678")
                    original_activity = manager._session_proxy_api
                    plan.secrets["omlxNativeContextGuard"] = True
                    manager._session_proxy_api = lambda *args, **kwargs: {"active":[{
                        "surfaceId":plan.run_id,"runtimeResponseId":"chatcmpl-12345678"}],
                        "activeCount":1,"queuedCount":0,"recent":[],"state":"busy"}
                    try:
                        writer.feed('<tool_call><function=write><parameter=path>example.py</parameter><parameter=content>def greet():\n    return "Live buffered code"')
                        time.sleep(20)
                        chunk({"tool_calls":[{"index":0,"id":"fixture-buffered","type":"function", "function":{"name":"write","arguments":json.dumps({"path":"example.py","content":"def greet():\n    return \"Live buffered code\""})}}]})
                        chunk({}, "tool_calls")
                    finally:
                        writer.clear()
                        plan.secrets.pop("omlxNativeContextGuard", None)
                        manager._session_proxy_api = original_activity
                elif prompt == "code" and body["messages"][-1]["role"] == "user":
                    # No tools are registered, so this exercises Pi's real tool
                    # stream and safe unknown-tool result without writing files.
                    chunk({"tool_calls":[{"index":0,"id":"fixture-write","type":"function",
                        "function":{"name":"write","arguments":""}}]})
                    arguments = json.dumps({"path":"example.py","content":"def greet():\n    return 'Hello from live code'\n"})
                    for part in (arguments[:45], arguments[45:]):
                        chunk({"tool_calls":[{"index":0,"function":{"arguments":part}}]})
                        time.sleep(8)
                    chunk({}, "tool_calls")
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                    return
                elif prompt == "hold":
                    for _ in range(300):
                        if stop.wait(0.1):
                            return
                        chunk({"reasoning_content":" Still reasoning."})
                chunk({"content":f"Final answer for {prompt}."})
                chunk({}, "stop")
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

    responder = ThreadingHTTPServer(("127.0.0.1", 0), Responder)
    responder_thread = threading.Thread(target=responder.serve_forever, daemon=True)
    responder_thread.start()
    manager = launcher.RunManager()
    console = None
    ui = None
    with tempfile.TemporaryDirectory(prefix="pi-hub-browser-") as folder:
        root = Path(folder)
        project, config = root / "project", root / "config"
        project.mkdir()
        config.mkdir()
        # This process owns its own module globals and never binds port 18080.
        launcher.STATE_DIR = root / "state"
        launcher.MANAGER = manager
        plan = launcher.LaunchPlan(run_id="pi-browser-fixture", backend="omlx", client="pi",
            model={"name":"Generated Hub fixture", "id":"hub-fixture", "backends":{}},
            project=str(project), context=8192, output=4096, reasoning="high",
            port=responder.server_port, mode="ar", options={}, agent_host="console")
        try:
            with mock.patch.dict(launcher.BINARIES, {"pi":binary}), mock.patch.object(launcher, "pi_browser_test_module", return_value=None):
                launcher.build_pi_client(plan, launcher.ClientRoute("launcher-fixture", "hub-fixture",
                    f"http://127.0.0.1:{responder.server_port}/v1", "generated-fixture-key"))
            plan.client_argv.extend(["--no-session", "--no-tools", "--no-extensions", "--no-skills",
                "--no-prompt-templates", "--no-themes", "--no-context-files", "--no-approve",
                "--offline", "--system-prompt", "Generated browser fixture only."])
            plan.client_env.update({"PI_CODING_AGENT_DIR":str(config),
                "PI_CODING_AGENT_SESSION_DIR":str(root / "sessions"), "PI_OFFLINE":"1", "PI_TELEMETRY":"0"})
            speed = Path.home() / ".pi/agent/npm/node_modules/pi-token-speed/index.ts"
            if speed.exists():
                plan.client_argv.extend(["--extension", str(speed)])
            plan.run_dir = root
            manager.plan = plan
            manager.state = {"phase":"running", "message":"Generated browser fixture",
                "run":plan.public(), "events":[]}
            manager.attachments[plan.run_id] = launcher.SurfaceAttachment(
                owner_run_id=plan.run_id, plan=plan, primary=True)
            with mock.patch.dict(os.environ, {"PATH":os.environ["PATH"]}, clear=True):
                console = manager._launch_agent_console(plan, manager.cancel_event)

            class FixtureHandler(launcher.Handler):
                def do_GET(self):
                    fixtures = {
                        "/api/bootstrap":{"version":launcher.VERSION, "controllerSourceCurrent":True,
                            "token":self.server.csrf_token, "binaries":{}, "adapters":[], "roots":[]},
                        "/api/models":{"models":[]},
                        "/api/profiles":{"profiles":[]},
                        "/api/session-sets":{"sessionSets":[]},
                        "/api/chat/history":{"threads":[]},
                        "/api/runtime/promotion/status":{"runtimePromotion":{"phase":"idle"}},
                        "/api/session-sets/status":{"sessionSet":{"phase":"idle"}},
                        "/api/acquisition/status":{"acquisition":{"phase":"idle"}, "roots":[]},
                        "/fixture/status":{"requests":requests, "piRunning":console.process.poll() is None,
                            "timelineRevision":console.rpc_timeline_revision,
                            "journalBaseRevision":console.public().get("timelineBaseRevision"),
                            "journalLimit":launcher.PI_RPC_TIMELINE_MAX_EVENTS},
                    }
                    if self.path in fixtures:
                        return self.json_response(fixtures[self.path])
                    if self.path.startswith('/api/') and self.path != '/api/status':
                        return self.json_response({"phase":"idle"})
                    return super().do_GET()

                def do_POST(self):
                    if self.headers.get("X-Launcher-Token") != self.server.csrf_token:
                        return self.send_error(403)
                    if self.path == "/fixture/release":
                        self.rfile.read(int(self.headers.get("Content-Length", "0")))
                        release.set()
                        return self.json_response({"ok":True})
                    if self.path == "/api/chat/turn/recover":
                        self.rfile.read(int(self.headers.get("Content-Length", "0")))
                        return self.json_response({"recovered":False, "discarded":False, "threads":[]})
                    if self.path not in {"/api/agent-console/read", "/api/agent-console/input",
                                         "/api/agent-console/resize", "/api/agent-console/stop"}:
                        return self.send_error(403, "Fixture permits only its owned console")
                    return super().do_POST()

            ui = launcher.ControllerHTTPServer(("127.0.0.1", 0), FixtureHandler)
            ui.csrf_token = secrets.token_urlsafe(32)
            threading.Thread(target=ui.serve_forever, daemon=True).start()
            print(json.dumps({"base":f"http://127.0.0.1:{ui.server_port}"}), flush=True)
            stop.wait(180)
        finally:
            stop.set()
            release.set()
            if console is not None:
                manager._stop_agent_console_process(console)
            if ui is not None:
                ui.shutdown()
                ui.server_close()
            responder.shutdown()
            responder.server_close()
            responder_thread.join(timeout=3)
            launcher.dispose_plan_secrets(plan)
            if console is not None and console.process.poll() is None:
                raise RuntimeError("Fixture Pi did not exit")


if __name__ == "__main__":
    main()
