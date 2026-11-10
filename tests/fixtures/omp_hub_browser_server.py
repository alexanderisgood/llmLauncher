"""Owned real OMP/RunManager/HTTP fixture with generated SSE, never a model."""
from __future__ import annotations
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import signal
import sys
import tempfile
import threading
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import launcher

EXPECTED_SHA = "ab52491643e21b270682691b1319f1161fe2a2658ae4e9a4e3958b1aeb12dcf4"


def main():
    if os.environ.get("LLM_LAUNCHER_OMP_HUB_BROWSER") != "1":
        raise SystemExit("Explicit OMP browser integration flag required")
    binary = Path(os.environ["LLM_LAUNCHER_OMP_BINARY"]).resolve()
    with binary.open("rb") as handle:
        if hashlib.file_digest(handle,"sha256").hexdigest() != EXPECTED_SHA:
            raise SystemExit("Fixture requires the verified OMP18.6.3 executable")
    # This child owns its module globals; qualification is still checked by the
    # real builder and again immediately before the real process is spawned.
    launcher.BINARIES["omp"] = str(binary)
    stop,release = threading.Event(),threading.Event()
    requests,contracts = [],[]
    signal.signal(signal.SIGTERM,lambda *_:stop.set())
    signal.signal(signal.SIGINT,lambda *_:stop.set())
    class Responder(BaseHTTPRequestHandler):
        def log_message(self,*_): pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert self.path == "/v1/chat/completions" and not body.get("tools")
            assert self.headers.get("Authorization") == "Bearer generated-fixture-key"
            assert body.get("model") == "hub-fixture"
            message = [item["content"] for item in body["messages"] if item["role"] == "user"][-1]
            prompt = message if isinstance(message,str) else "".join(item.get("text","") for item in message)
            # OMP prepends its native date/project reminder to a first message.
            # Keep the generated responder's scenario names independent of that
            # private temporary path; production transport is left untouched.
            if prompt.startswith("<system-reminder>"):
                prompt = prompt.split("</system-reminder>",1)[1]
            requests.append(prompt)
            contracts.append({"model":body.get("model"),"output":body.get("max_tokens"),
                "roles":[item["role"] for item in body["messages"]],
                "reasoningReplay":any("Generated OMP reasoning for first." in str(item.get("reasoning_content",""))
                    for item in body["messages"] if item["role"] == "assistant")})
            self.send_response(200); self.send_header("Content-Type","text/event-stream")
            self.send_header("Connection","close"); self.end_headers(); self.close_connection = True
            def chunk(delta,finish=None):
                data = {"id":"generated-omp-browser","object":"chat.completion.chunk","created":1,"model":"hub-fixture",
                        "choices":[{"index":0,"delta":delta,"finish_reason":finish}]}
                if finish:
                    data["usage"] = {"prompt_tokens":100,"completion_tokens":30,"total_tokens":130}
                self.wfile.write(("data: "+json.dumps(data)+"\n\n").encode()); self.wfile.flush()
            try:
                chunk({"role":"assistant","reasoning_content":"Generated OMP reasoning for "+prompt+"."})
                if prompt in {"hold","queue-hold"}:
                    while not stop.wait(.08) and (prompt == "hold" or not release.is_set()):
                        chunk({"reasoning_content":" Still thinking."})
                chunk({"content":"Final answer for "+prompt+". <script>inert fixture</script>"})
                chunk({},"stop"); self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()
            except (BrokenPipeError,ConnectionResetError): pass
    responder = ThreadingHTTPServer(("127.0.0.1",0),Responder)
    thread = threading.Thread(target=responder.serve_forever,daemon=True); thread.start()
    manager = launcher.RunManager(); console = ui = None
    with tempfile.TemporaryDirectory(prefix="omp-hub-browser-") as folder:
        root = Path(folder); project = root/"project"; project.mkdir()
        (root/"agent").mkdir(); (root/"data/omp").mkdir(parents=True)
        launcher.STATE_DIR = root/"state"; launcher.MANAGER = manager
        plan = launcher.LaunchPlan(run_id="omp-browser-fixture",backend="omlx",client="omp",
            model={"name":"Generated OMP Hub fixture","id":"hub-fixture", "backends":{
                "omlx":{"agentReasoning":["off","high"]}}},
            project=str(project),context=8192,output=1024,reasoning="high",port=responder.server_port,
            mode="ar",options={},agent_host="console",run_dir=root)
        try:
            with mock.patch.dict(launcher.BINARIES,{"omp":str(binary)}):
                launcher.build_omp_client(plan,launcher.ClientRoute("launcher-fixture","hub-fixture",
                    f"http://127.0.0.1:{responder.server_port}/v1","generated-fixture-key"))
            plan.client_argv += ["--session-dir",str(root/"sessions"),"--no-tools","--no-extensions","--no-skills","--no-rules",
                "--no-title","--no-lsp","--no-prewalk","--no-pty","--system-prompt","Generated browser fixture only."]
            plan.client_env.update({"PI_CODING_AGENT_DIR":str(root/"agent"),"XDG_DATA_HOME":str(root/"data"),
                                   "PI_OFFLINE":"1","PI_TELEMETRY":"0"})
            manager.plan = plan; manager.state = {"phase":"running","message":"Generated OMP browser fixture",
                                                 "run":plan.public(),"events":[]}
            manager.attachments[plan.run_id] = launcher.SurfaceAttachment(owner_run_id=plan.run_id,plan=plan,primary=True)
            with mock.patch.dict(os.environ,{"PATH":os.environ["PATH"]},clear=True):
                console = manager._launch_agent_console(plan,manager.cancel_event)
            class FixtureHandler(launcher.Handler):
                def do_GET(self):
                    fixtures = {"/api/bootstrap":{"version":launcher.VERSION,"controllerSourceCurrent":True,
                        "token":self.server.csrf_token,"binaries":{"omp":{"installed":True,
                            "version":"omp/18.6.3","consoleSupported":True,"consoleProtocol":"omp-rpc"}},
                        "adapters":[],"roots":[]},
                        "/api/models":{"models":[]},"/api/profiles":{"profiles":[]},"/api/session-sets":{"sessionSets":[]},
                        "/api/chat/history":{"threads":[]},"/api/runtime/promotion/status":{"runtimePromotion":{"phase":"idle"}},
                        "/api/session-sets/status":{"sessionSet":{"phase":"idle"}},"/api/acquisition/status":{"acquisition":{"phase":"idle"},"roots":[]},
                        "/fixture/status":{"requests":requests,"contracts":contracts,
                            "ompRunning":console.process.poll() is None,"console":console.public()}}
                    if self.path in fixtures: return self.json_response(fixtures[self.path])
                    if self.path.startswith("/api/") and self.path != "/api/status": return self.json_response({"phase":"idle"})
                    return super().do_GET()
                def do_POST(self):
                    if self.headers.get("X-Launcher-Token") != self.server.csrf_token: return self.send_error(403)
                    if self.path == "/fixture/release":
                        self.rfile.read(int(self.headers.get("Content-Length","0"))); release.set()
                        return self.json_response({"ok":True})
                    if self.path == "/api/chat/turn/recover":
                        self.rfile.read(int(self.headers.get("Content-Length","0")))
                        return self.json_response({"recovered":False,"discarded":False,"threads":[]})
                    if self.path not in {"/api/agent-console/read","/api/agent-console/input","/api/agent-console/resize","/api/agent-console/stop"}:
                        return self.send_error(403,"Fixture permits only its owned console")
                    return super().do_POST()
            ui = launcher.ControllerHTTPServer(("127.0.0.1",0),FixtureHandler); ui.csrf_token = secrets.token_urlsafe(32)
            threading.Thread(target=ui.serve_forever,daemon=True).start()
            print(json.dumps({"base":f"http://127.0.0.1:{ui.server_port}"}),flush=True)
            stop.wait(150)
        finally:
            stop.set(); release.set()
            if console is not None: manager._stop_agent_console_process(console)
            if ui is not None: ui.shutdown(); ui.server_close()
            responder.shutdown(); responder.server_close(); thread.join(timeout=3)
            launcher.dispose_plan_secrets(plan)
            if console is not None and console.process.poll() is None: raise RuntimeError("Owned OMP fixture did not exit")


if __name__ == "__main__": main()
