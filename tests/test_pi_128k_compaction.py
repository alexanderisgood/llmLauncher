"""Installed Pi at 128K; generated local usage, no model or real project work."""
import contextlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

import launcher


@unittest.skipUnless(os.environ.get("LLM_LAUNCHER_PI_INTEGRATION") == "1", "Opt-in installed Pi")
class Pi128KCompaction(unittest.TestCase):
    def test_27b_uses_selected_128k_window_then_native_reserve(self):
        normal, summaries = [], []

        class Responder(BaseHTTPRequestHandler):
            def log_message(self, *_): pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                summary = "context summarization assistant" in str(body["messages"][0]["content"])
                (summaries if summary else normal).append(body)
                total = 8000 if summary else [70000, 114000, 115000, 3000][min(len(normal)-1, 3)]
                text = "Summary: preserve verified evidence and file references." if summary else "Completed the next step."
                event = {"id":"128k-fixture", "model":"fixture", "choices":[
                    {"index":0, "delta":{"content":text}, "finish_reason":None},
                ]}
                self.close_connection = True
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                self.wfile.write(("data: "+json.dumps(event)+"\n\n").encode())
                event["choices"] = [{"index":0, "delta":{}, "finish_reason":"stop"}]
                event["usage"] = {"prompt_tokens":total-100, "completion_tokens":100, "total_tokens":total}
                self.wfile.write(("data: "+json.dumps(event)+"\n\ndata: [DONE]\n\n").encode())

        server = ThreadingHTTPServer(("127.0.0.1", 0), Responder)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        manager = launcher.RunManager()
        try:
            with tempfile.TemporaryDirectory(prefix="pi-128k-context-") as directory, contextlib.ExitStack() as cleanup:
                root = Path(directory)
                config = root / "config"
                config.mkdir()
                saved_settings = json.dumps({"compaction":{
                    "enabled":True, "reserveTokens":16384, "keepRecentTokens":20000,
                }})
                (config / "settings.json").write_text(saved_settings)
                session = root / "seed.jsonl"
                entries = [{"type":"session", "version":3, "id":"context-128k",
                    "timestamp":"2026-01-01T00:00:00Z", "cwd":str(root)}]
                parent = None
                # Supply enough real history for Pi's native cut-point algorithm;
                # reported token usage, not character length, controls admission.
                for index in range(24):
                    for role, content in [("user", f"Perform step {index}"),
                                          ("assistant", "Evidence and file references.\n" * 150)]:
                        identifier = f"{index}-{role}"
                        message = {"role":role, "content":[{"type":"text", "text":content}], "timestamp":index*1000}
                        if role == "assistant":
                            message.update(provider="launcher-fixture", model="fixture", api="openai-completions", stopReason="stop",
                                usage={"input":69900, "output":100, "cacheRead":0, "cacheWrite":0, "totalTokens":70000,
                                       "cost":{"input":0, "output":0, "cacheRead":0, "cacheWrite":0, "total":0}})
                        entries.append({"type":"message", "id":identifier, "parentId":parent,
                            "timestamp":"2026-01-01T00:00:00Z", "message":message})
                        parent = identifier
                session.write_text("".join(json.dumps(entry)+"\n" for entry in entries))
                plan = launcher.LaunchPlan(run_id="context-128k", backend="omlx", client="pi",
                    model={"name":"Qwen3.8-27B-MLX-6bit fixture", "id":"fixture", "backends":{}},
                    project=str(root), context=131072, output=16384, reasoning="medium",
                    port=server.server_port, mode="ar", options={}, agent_host="console", pi_session_file=str(session))
                with mock.patch.dict(launcher.BINARIES, {"pi":shutil.which("pi")}):
                    launcher.build_pi_client(plan, launcher.ClientRoute(
                        "launcher-fixture", "fixture", f"http://127.0.0.1:{server.server_port}/v1", "test-key"))
                provider = json.loads(plan.client_env["LLM_LAUNCHER_PI_PROVIDER"])
                self.assertEqual(provider["model"]["contextWindow"], 131072)
                self.assertTrue(provider["memoryCompaction"])
                self.assertIn("27B", provider["model"]["name"])
                plan.client_argv.extend(["--no-tools", "--no-extensions", "--no-skills", "--no-prompt-templates",
                    "--no-themes", "--no-context-files", "--no-approve", "--offline", "--system-prompt", "Local fixture only."])
                probe = root / "compaction-probe.js"
                cuts = root / "compaction-settings.jsonl"
                probe.write_text("""import {appendFileSync} from 'node:fs';
export default pi => pi.on('session_before_compact', event => {
  appendFileSync(process.env.FIXTURE_COMPACTION_SETTINGS,
    JSON.stringify(event.preparation.settings)+'\\n');
});
""")
                plan.client_argv.extend(["--extension", str(probe)])
                plan.client_env.update(PI_CODING_AGENT_DIR=str(config), PI_CODING_AGENT_SESSION_DIR=str(root/"sessions"),
                                       PI_OFFLINE="1", PI_TELEMETRY="0", FIXTURE_COMPACTION_SETTINGS=str(cuts))
                manager.plan = plan
                manager.state = {"phase":"running", "run":plan.public(), "events":[]}
                manager.attachments[plan.run_id] = launcher.SurfaceAttachment(owner_run_id=plan.run_id, plan=plan, primary=True)
                with mock.patch.dict(os.environ, {"PATH":os.environ["PATH"]}, clear=True):
                    console = manager._launch_agent_console(plan, manager.cancel_event)
                cleanup.callback(manager._stop_agent_console_process, console)
                for turn in range(4):
                    manager.write_agent_console({"ownerRunId":plan.run_id, "surfaceId":plan.run_id,
                        "command":"prompt", "message":f"Continue step {turn}"})
                    deadline = time.monotonic()+25
                    while time.monotonic() < deadline:
                        if len(normal) >= turn+1 and not console.rpc_streaming and not console.rpc_prompt_inflight and not console.rpc_compacting:
                            break
                        time.sleep(.025)
                    else:
                        self.fail(bytes(console.output).decode(errors="replace")[-4000:])
                    if turn < 2:
                        self.assertFalse(summaries, "70K and 114K usage must fit below the selected 128K window's 16K reserve")
                self.assertEqual(len(normal), 4)
                compactions = [json.loads(line) for line in session.read_text().splitlines() if json.loads(line).get("type") == "compaction"]
                self.assertEqual(len(compactions), 1, "Usage above 114688 must compact once and leave room to continue")
                observed_settings = [json.loads(line) for line in cuts.read_text().splitlines()]
                self.assertTrue(observed_settings)
                for settings in observed_settings:
                    self.assertEqual(131072-settings["reserveTokens"], 114688)
                    self.assertEqual(settings["keepRecentTokens"], 8000)
                self.assertTrue(summaries)
                self.assertTrue(all(0 < body["max_tokens"] <= 13107 for body in summaries),
                                "Native summary allowance must stay within 80% of the 16K reserve")
                self.assertEqual((config/"settings.json").read_text(), saved_settings)
                self.assertEqual(json.loads(console.rpc_statuses["launcher.context"]["text"])["tokens"], 3000)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
