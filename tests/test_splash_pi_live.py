"""Opt-in installed Pi -> launcher relay -> already-running Splash smoke test.

LLM_LAUNCHER_SPLASH_LIVE_PORT=18080 python3 -m unittest discover -s tests -p test_splash_pi_live.py
Uses only temporary project/config files; does not start or stop the engine.
"""
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest import mock
import uuid

import launcher
import session_proxy
import splash_runtime


@unittest.skipUnless(os.environ.get("LLM_LAUNCHER_SPLASH_LIVE_PORT"), "Opt-in running Splash and installed Pi")
class SplashPiLive(unittest.TestCase):
    def test_large_allowance_tool_round_trip(self):
        upstream_port = int(os.environ["LLM_LAUNCHER_SPLASH_LIVE_PORT"])
        model_id = "incoai/Qwen3.8-27B-Splash"
        requests = []
        transform = session_proxy.transform_chat_request

        def record(body, config, surface=None):
            result = transform(body, config, surface)
            requests.append(json.loads(result))
            return result

        contract = launcher.build_sampling_contract("model").as_dict()
        capability = {"agentReasoning": splash_runtime.REASONING, "customSampling": True}
        enforcement = launcher.sampling_route_enforcement("splash", "pi", capability, contract)
        key = secrets.token_urlsafe(32)
        run_id = str(uuid.uuid4())
        relay = session_proxy.RelayHTTPServer(("127.0.0.1", 0), session_proxy.ProxyHandler)
        relay.config = {"listenPort": relay.server_port, "upstreamPort": upstream_port,
                        "upstreamKey": os.environ.get("LLM_LAUNCHER_SPLASH_LIVE_KEY", key),
                        "controlKey": secrets.token_urlsafe(32), "backend": "splash",
                        "servedModel": model_id, "reasoning": "xhigh", "outputLimit": 65_536}
        relay.registry = session_proxy.SurfaceRegistry([
            {"id": run_id, "client": "pi", "key": key,
             "samplingContract": contract, "samplingEnforcement": enforcement},
        ])
        relay.scheduler = session_proxy.RequestScheduler(1)
        worker = threading.Thread(target=relay.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory(prefix="splash-pi-live-") as directory, \
                    mock.patch.object(session_proxy, "transform_chat_request", record):
                root = Path(directory)
                project = root / "project"
                project.mkdir()
                config = root / "config"
                config.mkdir()
                plan = launcher.LaunchPlan(
                    run_id=run_id, backend="splash", client="pi", project=str(project),
                    model={"id": "splash-live", "name": "Qwen3.8-27B · Splash", "backends": {"splash": capability}},
                    context=131_072, output=65_536, reasoning="xhigh", port=upstream_port,
                    mode="custom", options={}, agent_host="terminal", run_dir=root,
                )
                with mock.patch.dict(launcher.BINARIES, {"pi": shutil.which("pi")}):
                    launcher.build_pi_client(plan, launcher.ClientRoute(
                        "splash-live", model_id, f"http://127.0.0.1:{relay.server_port}/v1", key,
                    ))
                relay.config["servedModelAliases"] = [launcher.pi_model_identity(plan)[1]]
                argv = plan.client_argv + [
                    "--mode", "json", "--print", "--no-session",
                    "--no-extensions", "--no-skills", "--no-prompt-templates", "--no-themes",
                    "--no-context-files", "--no-approve", "--offline", "--system-prompt",
                    "You are verifying a local tool transport. Follow the exact small task and stop.",
                    "Use write to create proof.txt containing exactly SPLASH_PI_VERIFIED_7182. "
                    "Then use read on proof.txt to verify it. Finally reply with that marker. "
                    "Do not use other tools or files. This needs only a brief check.",
                ]
                env = {"PATH": os.environ["PATH"], "HOME": str(root), **plan.client_env,
                       "PI_CODING_AGENT_DIR": str(config), "PI_CODING_AGENT_SESSION_DIR": str(root / "sessions"),
                       "PI_OFFLINE": "1", "PI_TELEMETRY": "0"}
                result = subprocess.run(argv, cwd=project, env=env, text=True, capture_output=True, timeout=180)
                self.assertEqual(result.returncode, 0, result.stderr[-3000:] + result.stdout[-3000:])
                self.assertEqual((project / "proof.txt").read_text().strip(), "SPLASH_PI_VERIFIED_7182")
                self.assertGreaterEqual(len(requests), 3, "Write, read and final answer must cross the relay")
                self.assertTrue(all(r["max_tokens"] == 65_536 for r in requests))
                self.assertTrue(all(r["reasoning_effort"] == "xhigh" for r in requests))
                tools = [t["function"] for t in requests[0].get("tools", [])]
                self.assertIn("browser_check", [t["name"] for t in tools], "Exercise the real browser schema")
                self.assertTrue(all("anyOf" not in t.get("parameters", {}) for t in tools))
                messages = requests[-1]["messages"]
                self.assertTrue(any(m["role"] == "assistant" and m.get("tool_calls") for m in messages))
                self.assertTrue(any(m["role"] == "tool" and "SPLASH_PI_VERIFIED_7182" in str(m.get("content")) for m in messages))
                events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
                final = [e["message"] for e in events if e.get("type") == "message_end" and e.get("message", {}).get("role") == "assistant"][-1]
                self.assertEqual(final["stopReason"], "stop")
                self.assertIn("SPLASH_PI_VERIFIED_7182", " ".join(b.get("text", "") for b in final["content"]))
                print(f"Live Splash + Pi: {len(requests)} requests at 65,536 max_tokens; write/read/final verified.")
        finally:
            relay.shutdown()
            relay.server_close()
            worker.join(5)


if __name__ == "__main__":
    unittest.main()
