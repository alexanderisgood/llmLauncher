"""Opt-in real-model Pi launch through normal admission and RunManager.start.

Only generated tool data is exposed: no project files, shell tools, user Pi
extensions, sessions, credentials, or network providers. Never runs in CI.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from test_uzu_candidate_live_boundary import private_session_files, termination_runs_cleanup

ROOT = Path(__file__).resolve().parents[1]
PATCH_ROOT = ROOT / "runtime_patches/uzu/0.5.23"


@unittest.skipUnless(os.environ.get("LLM_LAUNCHER_UZU_PI_PRIMARY_LIVE") == "1",
                     "requires explicit real-model test and exclusive idle controller")
class UzuPiPrimaryLiveTests(unittest.TestCase):
    def test_normal_primary_pi_launch_tool_turn_and_followup(self):
        sys.path.insert(0, str(PATCH_ROOT))
        import candidate_qualification as candidate

        spec = importlib.util.spec_from_file_location("uzu_pi_primary_app", ROOT / "launcher.py")
        app = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = app
        spec.loader.exec_module(app)
        # Production runtime, model and saved receipts, not candidate overrides.
        lock_path = app.STATE_DIR / "controller-instance.lock"
        binary = shutil.which("pi")
        self.assertIsNotNone(binary)
        with candidate.exclusive_controller_lock(lock_path), termination_runs_cleanup(), \
             private_session_files(), tempfile.TemporaryDirectory(prefix="uzu-pi-primary-") as directory:
            root = Path(directory)
            project, config = root / "project", root / "config"
            project.mkdir()
            config.mkdir()
            models = app.uzu_model_records(app.load_benchmark_records())
            payload = {**candidate.request(65536), "client": "pi", "agentHost": "console",
                       "project": str(project)}
            dashboard = app.session_dashboard_plan(payload, models)
            admission = dashboard.get("admission", {})
            self.assertTrue(app.strict_model_load_admission_ready(admission), admission)
            app.require_session_launch_admission(payload, admission)
            plan = app.normalized_request(payload, models, purpose="session")
            self.assertEqual(plan.client, "pi")
            self.assertEqual(plan.agent_host, "console")
            self.assertEqual(plan.context, 65536)
            plan.client_argv.extend([
                "--no-session", "--tools", "fixture_lookup", "--no-extensions", "--no-skills",
                "--no-prompt-templates", "--no-themes", "--no-context-files", "--no-approve", "--offline",
                "--extension", str(ROOT / "tests/fixtures/pi-generated-tool.js"),
                "--system-prompt", "Use only the generated fixture tool. Do not access files or run commands.",
            ])
            plan.client_env.update({"PI_CODING_AGENT_DIR": str(config),
                "PI_CODING_AGENT_SESSION_DIR": str(root / "sessions"),
                "PI_OFFLINE": "1", "PI_TELEMETRY": "0"})
            console = None
            try:
                # The asynchronous worker inherits only PATH. Exact runtime,
                # private provider and isolated Pi config come from the plan.
                with mock.patch.dict(os.environ, {"PATH": os.environ["PATH"]}, clear=True):
                    app.MANAGER.start(plan)
                    deadline = time.monotonic() + 120
                    while app.MANAGER.snapshot().get("phase") != "running":
                        status = app.MANAGER.snapshot()
                        self.assertNotIn(status.get("phase"), {"idle", "failed", "error"}, status.get("message"))
                        self.assertLess(time.monotonic(), deadline, "Normal Pi launch timed out")
                        time.sleep(0.25)
                console = app.MANAGER.agent_consoles.get(plan.run_id)
                self.assertIsNotNone(console, "Normal startup did not open primary Hub Console")
                self.assertTrue(app.MANAGER.attachments[plan.run_id].primary)
                print("Normal Uzu → Pi primary Hub launch passed exact 64K admission; live memory guard active.", flush=True)

                def turn(message, previous_answers=0):
                    app.MANAGER.write_agent_console({"ownerRunId": plan.run_id, "surfaceId": plan.run_id,
                        "command": "prompt", "message": message})
                    deadline = time.monotonic() + 120
                    while time.monotonic() < deadline:
                        snapshot = console.output_slice(0)
                        reduced = subprocess.run([shutil.which("node"), "-e",
                            "const fs=require('fs'),t=require('./pi_timeline.js');"
                            "const s=t.applyTimelineEnvelope(t.emptyTimeline(),JSON.parse(fs.readFileSync(0,'utf8'))).state;"
                            "process.stdout.write(JSON.stringify(s.items));"],
                            input=json.dumps(snapshot), text=True, capture_output=True, cwd=ROOT, timeout=10)
                        self.assertEqual(reduced.returncode, 0, reduced.stderr)
                        items = json.loads(reduced.stdout)
                        answers = [item for item in items if item["kind"] == "answer"]
                        if len(answers) > previous_answers and not console.rpc_streaming and not console.rpc_prompt_inflight:
                            return items, answers
                        self.assertIsNone(console.process.poll(), "Pi exited during a turn")
                        self.assertFalse(console.rpc_queue_paused, "Pi paused on a provider or protocol error")
                        self.assertEqual(app.MANAGER.snapshot().get("phase"), "running")
                        time.sleep(0.5)
                    self.fail("Normal Pi turn did not finish within its bound")

                items, answers = turn("Call fixture_lookup once with key alpha. Read the returned JSON object's value field. Reply only with that string, without quotes, JSON, or any other answer text.")
                results = [item for item in items if item["kind"] == "toolResult"]
                self.assertEqual(len(results), 1)
                value = json.loads(results[0]["text"])["value"]
                self.assertTrue(value.startswith("fixture-"))
                self.assertEqual(answers[-1]["text"].strip(), value)
                self.assertTrue(any(item["kind"] == "thinking" for item in items))
                print("Primary Pi tool call, returned value, reasoning and final answer passed the real Hub reducer.", flush=True)
                items, followup = turn("Without calling tools again, repeat the exact fixture value from the previous turn. Output only that string.", len(answers))
                self.assertEqual(followup[-1]["text"].strip(), value)
                self.assertEqual(len([item for item in items if item["kind"] == "toolResult"]), 1)
                self.assertTrue(any(item.get("text", "").strip() == value for item in items if item["kind"] == "answer"))
                print("Follow-up retained the tool result and previous answer; no repeated tool execution.", flush=True)
            finally:
                app.MANAGER.stop()
                app.dispose_plan_secrets(plan)
                self.assertEqual(app.MANAGER.snapshot().get("phase"), "idle")
                if console is not None:
                    self.assertIsNotNone(console.process.poll(), "Primary Pi did not stop")
                self.assertTrue(app.MANAGER.process is None or app.MANAGER.process.poll() is not None)
                print("Normal primary Pi and Uzu stopped cleanly.", flush=True)


if __name__ == "__main__":
    unittest.main()
