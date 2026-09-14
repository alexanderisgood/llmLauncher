"""Opt-in real Pi/Hub test; generated loopback responses, no model or tools.

Run with LLM_LAUNCHER_PI_INTEGRATION=1 python3 -m unittest discover
    -s tests -p test_pi_installed_integration.py
"""
import contextlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import launcher


@unittest.skipUnless(os.environ.get("LLM_LAUNCHER_PI_INTEGRATION") == "1",
                     "Opt-in installed Pi integration")
class InstalledPiIntegration(unittest.TestCase):
    def test_stream_queue_abort_and_retained_transcript(self):
        binary = shutil.which("pi")
        self.assertIsNotNone(binary, "Install Pi before enabling this integration test")
        requests = []
        first_received = threading.Event()
        release_first = threading.Event()
        hold_received = threading.Event()
        release_hold = threading.Event()
        fault_received = threading.Event()
        release_fault = threading.Event()

        class Responder(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                users = [m for m in body["messages"] if m["role"] == "user"]
                content = users[-1]["content"]
                prompt = content if isinstance(content, str) else "".join(
                    part.get("text", "") for part in content)
                requests.append((self.path, self.headers.get("Authorization"), body, prompt))
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True

                def chunk(delta, finish=None):
                    data = {"id": "fixture", "object": "chat.completion.chunk",
                            "created": 1, "model": "hub-fixture",
                            "choices": [{"index": 0, "delta": delta,
                                         "finish_reason": finish}]}
                    self.wfile.write(("data: " + json.dumps(data) + "\n\n").encode())
                    self.wfile.flush()

                try:
                    chunk({"role": "assistant", "reasoning_content": "Fixture thinking."})
                    if prompt == "first":
                        first_received.set()
                        release_first.wait(20)
                    elif prompt == "hold":
                        hold_received.set()
                        release_hold.wait(20)
                    elif prompt in {"limit", "eof"}:
                        fault_received.set()
                        release_fault.wait(20)
                        if prompt == "eof":
                            chunk({"content": "Partial answer before disconnection."})
                            return
                        chunk({}, "length")
                        self.wfile.write(b"data: [DONE]\n\n")
                        self.wfile.flush()
                        return
                    elif prompt == "long":
                        for index in range(24):
                            chunk({"content": f"part-{index:02d}:" + "🙂" * 1024})
                    chunk({"content": f"Final answer for {prompt}."})
                    chunk({}, "stop")
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Responder)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        manager = launcher.RunManager()
        console = None
        try:
            with tempfile.TemporaryDirectory(prefix="launcher-pi-fixture-") as folder, \
                    contextlib.ExitStack() as cleanup:
                root = Path(folder)
                project = root / "project"
                config = root / "config"
                project.mkdir()
                config.mkdir()
                plan = launcher.LaunchPlan(
                    run_id="installed-pi-fixture", backend="omlx", client="pi",
                    model={"name": "Hub fixture", "id": "hub-fixture", "backends": {}},
                    project=str(project), context=8192, output=512, reasoning="high",
                    port=server.server_port, mode="ar", options={}, agent_host="console",
                )
                with mock.patch.dict(launcher.BINARIES, {"pi": binary}):
                    launcher.build_pi_client(plan, launcher.ClientRoute(
                        "launcher-fixture", "hub-fixture",
                        f"http://127.0.0.1:{server.server_port}/v1", "test-local-key"))
                    plan.client_argv.extend([
                        "--no-session", "--no-tools", "--no-extensions", "--no-skills",
                        "--no-prompt-templates", "--no-themes", "--no-context-files",
                        "--no-approve", "--offline", "--system-prompt", "Local fixture only.",
                    ])
                    plan.client_env.update({
                        "PI_CODING_AGENT_DIR": str(config),
                        "PI_CODING_AGENT_SESSION_DIR": str(root / "sessions"),
                        "PI_OFFLINE": "1", "PI_TELEMETRY": "0",
                    })
                    manager.plan = plan
                    manager.state = {"phase": "running", "message": "Fixture",
                                     "run": plan.public(), "events": []}
                    manager.attachments[plan.run_id] = launcher.SurfaceAttachment(
                        owner_run_id=plan.run_id, plan=plan, primary=True)
                    # Never pass cloud credentials or load the user's agent configuration.
                    with mock.patch.dict(os.environ, {"PATH": os.environ["PATH"]}, clear=True):
                        console = manager._launch_agent_console(plan, manager.cancel_event)
                    cleanup.callback(manager._stop_agent_console_process, console)

                def transcript():
                    return bytes(console.output).decode("utf-8", errors="replace")

                def wait_for(predicate):
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline:
                        if predicate():
                            return
                        if console.process.poll() is not None:
                            break
                        time.sleep(0.02)
                    self.fail("Pi fixture did not reach expected state:\n" + transcript()[-6000:])

                def send(command, message=""):
                    return manager.write_agent_console({
                        "ownerRunId": plan.run_id, "surfaceId": plan.run_id,
                        "command": command, "message": message})

                send("prompt", "first")
                wait_for(first_received.is_set)
                wait_for(lambda: "Fixture thinking." in transcript())
                self.assertEqual(send("prompt", "queued")["pendingMessages"], 1)
                release_first.set()
                wait_for(lambda: "Final answer for queued." in transcript()
                         and not console.rpc_streaming and not console.rpc_prompt_inflight)
                self.assertIn("THINKING", transcript())
                self.assertIn("RESPONSE", transcript())
                prior_assistant = next(m for m in requests[1][2]["messages"] if m["role"] == "assistant")
                self.assertEqual(prior_assistant.get("reasoning_content"), "Fixture thinking.",
                                 "Pi must carry thinking into a subsequent user prompt")
                send("prompt", "hold")
                wait_for(hold_received.is_set)
                self.assertEqual(send("prompt", "must-not-run")["pendingMessages"], 1)
                send("abort")
                wait_for(lambda: not console.rpc_streaming and not console.rpc_prompt_inflight)
                self.assertTrue(console.rpc_queue_paused)
                send("clear_queue")
                release_hold.set()
                send("prompt", "after-stop")
                wait_for(lambda: "Final answer for after-stop." in transcript()
                         and not console.rpc_streaming and not console.rpc_prompt_inflight)
                snapshot = json.dumps(console.output_slice(0))
                self.assertIn("Final answer for first.", snapshot)
                self.assertIn("Final answer for queued.", snapshot)
                self.assertIn("Final answer for after-stop.", snapshot)
                for fault, notice in [("limit", "Response limit reached"),
                                      ("eof", "Pi error")]:
                    fault_received.clear()
                    release_fault.clear()
                    send("prompt", fault)
                    wait_for(fault_received.is_set)
                    self.assertEqual(send("prompt", "must-not-run")["pendingMessages"], 1)
                    release_fault.set()
                    wait_for(lambda: not console.rpc_streaming and not console.rpc_prompt_inflight)
                    self.assertTrue(console.rpc_queue_paused, fault + " must pause follow-ups")
                    self.assertIn(notice, json.dumps(console.output_slice(0)))
                    self.assertIn("Final answer for first.", json.dumps(console.output_slice(0)))
                    send("clear_queue")
                self.assertEqual([item[3] for item in requests],
                                 ["first", "queued", "hold", "after-stop", "limit"]
                                 + ["eof"] * sum(item[3] == "eof" for item in requests))
                self.assertGreaterEqual(sum(item[3] == "eof" for item in requests), 1)
                # Real PTY delivery: multi-kilobyte Unicode JSON must survive
                # while another turn is streaming, for both delivery modes.
                hold_received.clear()
                release_hold.clear()
                send("prompt", "hold")
                wait_for(hold_received.is_set)
                queued_text = "queued-large:" + "line £🙂\n" * 180
                steered_text = "steered-large:" + "change £🙂\n" * 180
                send("prompt", queued_text)
                send("steer", steered_text)
                release_hold.set()
                wait_for(lambda: any(item[3] == queued_text for item in requests)
                         and not console.rpc_streaming and not console.rpc_prompt_inflight)
                self.assertEqual(sum(item[3] == queued_text for item in requests), 1)
                self.assertEqual(sum(item[3] == steered_text for item in requests), 1)
                self.assertLess(next(i for i,x in enumerate(requests) if x[3] == steered_text),
                                next(i for i,x in enumerate(requests) if x[3] == queued_text))
                # Simulate the browser/backend observing busy just as Pi ends.
                # Native prompt(streamingBehavior=steer) must start a new turn
                # here, rather than strand the message in Pi's steering queue.
                console.rpc_streaming = True
                send("steer", "steer-after-finish")
                wait_for(lambda: any(item[3] == "steer-after-finish" for item in requests)
                         and not console.rpc_streaming and not console.rpc_prompt_inflight)
                send("prompt", "long")
                wait_for(lambda: "Final answer for long." in transcript()
                         and not console.rpc_streaming and not console.rpc_prompt_inflight)
                snapshot = console.output_slice(0)
                final_answers = [event for event in snapshot["timelineEvents"]
                                 if event["kind"] == "answer" and event.get("operation") == "replace"]
                self.assertTrue(final_answers[-1]["text"].endswith("Final answer for long."))
                self.assertIn("Earlier text omitted", final_answers[-1]["title"])
                self.assertIn("part-23:", final_answers[-1]["text"])
                self.assertNotIn("�", final_answers[-1]["text"])
                # Exercise the actual browser-side reconciliation with the real
                # Pi event envelope, including its per-item and total caps.
                node = shutil.which("node")
                self.assertIsNotNone(node, "Node is required for Hub timeline verification")
                replay = subprocess.run([
                    node, "-e",
                    "const fs=require('fs');const t=require('./pi_timeline.js');"
                    "const e=JSON.parse(fs.readFileSync(0,'utf8'));"
                    "const s=t.applyTimelineEnvelope(t.emptyTimeline(),e).state;"
                    "const a=s.items.filter(i=>i.kind==='answer').at(-1);"
                    "if(!a.text.endsWith('Final answer for long.') || "
                    "!a.title.includes('Earlier text omitted'))process.exit(1);",
                ], input=json.dumps(snapshot), text=True, capture_output=True,
                    cwd=launcher.APP_DIR, timeout=10)
                self.assertEqual(replay.returncode, 0, replay.stderr)
                for path, auth, body, _prompt in requests:
                    self.assertEqual(path, "/v1/chat/completions")
                    self.assertEqual(auth, "Bearer test-local-key")
                    # Native compaction bypasses before_provider_request;
                    # the production relay accepts this stable model alias.
                    self.assertIn(body["model"], {"hub-fixture", launcher.pi_model_identity(plan)[1]})
                    self.assertFalse(body.get("tools"))
        finally:
            release_first.set()
            release_hold.set()
            release_fault.set()
            if console is not None:
                manager._stop_agent_console_process(console)
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)
