"""Opt-in real oh-my-pi tool/reasoning check against a synthetic local server.

Set LLM_LAUNCHER_OMP_BINARY to an installed omp executable. No model loads,
downloads, user projects, persistent configuration or real AI endpoints.
"""
import json
import os
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import omp_runtime


@unittest.skipUnless(os.environ.get("LLM_LAUNCHER_OMP_BINARY"), "Opt-in real oh-my-pi integration")
class InstalledOMPTests(unittest.TestCase):
    def test_real_tools_reasoning_history_and_exact_model_limits(self):
        requests = []

        class Responder(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append({"path":self.path, "authorization":self.headers.get("Authorization"), "body":body})
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True

                def chunk(delta, finish=None, usage=None):
                    data = {"id":"omp-fixture", "object":"chat.completion.chunk", "created":1,
                            "model":"qwen-fixture", "choices":[{"index":0,"delta":delta,"finish_reason":finish}]}
                    if usage is not None:
                        data["usage"] = usage
                    self.wfile.write(("data: " + json.dumps(data) + "\n\n").encode())
                    self.wfile.flush()

                has_result = any(message.get("role") == "tool" for message in body["messages"])
                chunk({"role":"assistant","reasoning_content":"Synthetic reasoning to preserve."})
                if has_result:
                    chunk({"content":"FIXTURE_OK"})
                    chunk({}, "stop", {"prompt_tokens":80,"completion_tokens":12,"total_tokens":92})
                else:
                    chunk({"tool_calls":[{"index":0,"id":"fixture-read","type":"function",
                           "function":{"name":"read","arguments":'{"path":"fixture'}}]})
                    chunk({"tool_calls":[{"index":0,"function":{"arguments":'.txt"}'}}]})
                    chunk({}, "tool_calls", {"prompt_tokens":40,"completion_tokens":10,"total_tokens":50})
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()

        server = ThreadingHTTPServer(("127.0.0.1",0),Responder)
        worker = threading.Thread(target=server.serve_forever,daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory(prefix="launcher-omp-fixture-") as tmp:
                root = Path(tmp)
                project = root / "project"; project.mkdir()
                (project / "fixture.txt").write_text("SYNTHETIC_SENTINEL\n")
                (root / "agent").mkdir()
                (root / "data/omp").mkdir(parents=True)
                plan = SimpleNamespace(agent_host="terminal", run_dir=root, run_id="omp-native-fixture",
                    backend="splash", model={"name":"Synthetic Qwen", "backends":{"splash":{
                        "agentReasoning":["off","low","medium","high"]}}},
                    context=8192,output=512,reasoning="low",client_env={},warnings=[])
                omp_runtime.build_client(plan, SimpleNamespace(served="qwen-fixture",
                    base_url=f"http://127.0.0.1:{server.server_address[1]}/v1",api_key="fixture-only"),
                    binary=os.environ["LLM_LAUNCHER_OMP_BINARY"],
                    app_dir=Path(__file__).resolve().parents[1],
                    provider="launcher-splash-fixture",inputs=["text"])
                env = {"PATH":os.environ["PATH"], "TMPDIR":str(root),
                       "PI_CODING_AGENT_DIR":str(root / "agent"), "XDG_DATA_HOME":str(root / "data"),
                       "PI_SMOL_MODEL":"unavailable-cloud/conflicting-small-model",
                       "PI_SLOW_MODEL":"unavailable-cloud/conflicting-large-model",
                       "PI_PLAN_MODEL":"unavailable-cloud/conflicting-plan-model",
                       **plan.client_env}
                result = subprocess.run([
                    os.environ["LLM_LAUNCHER_OMP_BINARY"], "--no-extensions", "--no-skills", "--no-rules",
                    "--no-title", "--no-session", "--no-lsp", "--no-prewalk", "--no-pty",
                    *plan.client_argv[1:], "--tools","read", "--mode","json", "--print",
                    "Read fixture.txt using the read tool, then respond FIXTURE_OK.",
                ], cwd=project,env=env,capture_output=True,text=True,timeout=60)
                self.assertEqual(result.returncode,0,result.stderr[-4000:])
                self.assertIn("FIXTURE_OK",result.stdout)
                self.assertEqual(len(requests),2, str([(r["path"],len(r["body"]["messages"])) for r in requests]))
                for request in requests:
                    self.assertEqual(request["path"],"/v1/chat/completions")
                    self.assertEqual(request["authorization"],"Bearer fixture-only")
                    self.assertEqual(request["body"]["model"],"qwen-fixture")
                    self.assertEqual(request["body"]["max_tokens"],512)
                    self.assertNotIn("store",request["body"])
                    self.assertNotIn("reasoning_effort",request["body"])
                assistant = next(m for m in requests[1]["body"]["messages"] if m["role"] == "assistant")
                self.assertEqual(assistant["reasoning_content"],"Synthetic reasoning to preserve.")
                self.assertEqual(assistant["tool_calls"][0]["id"],"fixture-read")
                self.assertIn("SYNTHETIC_SENTINEL",json.dumps(requests[1]["body"]["messages"]))
        finally:
            server.shutdown(); server.server_close(); worker.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
