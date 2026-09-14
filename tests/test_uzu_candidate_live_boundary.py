"""Explicit opt-in, isolated real-model recovery test; never part of normal CI.

Requires the exact candidate, its own successful 64K receipt, full hardware
access, and exclusive ownership of the normal controller lock. Not a benchmark.
"""
from __future__ import annotations

import importlib.util
from dataclasses import replace
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import uuid
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PATCH_ROOT = ROOT / "runtime_patches/uzu/0.5.23"


@contextmanager
def termination_runs_cleanup():
    def interrupt(_number, _frame):
        raise KeyboardInterrupt("Stop requested during isolated live boundary check")

    previous = {number: signal.getsignal(number) for number in (signal.SIGTERM, signal.SIGHUP)}
    try:
        for number in previous:
            signal.signal(number, interrupt)
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


@contextmanager
def private_session_files():
    previous_mask = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(previous_mask)


def read_streamed_tool_message(lines):
    """Reassemble the actual tool request for a generated-data-only round trip."""
    message = {"role": "assistant", "content": "", "reasoning_content": ""}
    calls = {}
    finish = None
    done = False
    size = 0
    for line in lines:
        size += len(line)
        if size > 2 * 1024**2:
            raise ValueError("Tool probe exceeded its bounded response size")
        if not line.startswith(b"data:"):
            continue
        raw = line[5:].strip()
        if raw == b"[DONE]":
            done = True
            break
        event = json.loads(raw)
        if event.get("error"):
            raise ValueError("Tool probe returned a runtime error")
        for choice in event.get("choices", []):
            if choice.get("index") != 0:
                raise ValueError("Unexpected tool probe choice")
            delta = choice.get("delta") or {}
            if finish and any(delta.get(key) for key in ("content", "reasoning_content", "tool_calls")):
                raise ValueError("Output continued after the tool terminal event")
            for key in ("content", "reasoning_content"):
                if delta.get(key):
                    message[key] += delta[key]
            for fragment in delta.get("tool_calls", []):
                index = fragment.get("index")
                if isinstance(index, bool) or not isinstance(index, int) or index < 0:
                    raise ValueError("Tool call has no valid stream index")
                call = calls.setdefault(index, {"id": "", "type": "function",
                    "function": {"name": "", "arguments": ""}})
                if fragment.get("type", "function") != "function":
                    raise ValueError("Unsupported tool call type")
                if fragment.get("id"):
                    if call["id"] and call["id"] != fragment["id"]:
                        raise ValueError("Tool call identity changed during streaming")
                    call["id"] = fragment["id"]
                for key in ("name", "arguments"):
                    call["function"][key] += (fragment.get("function") or {}).get(key, "")
            if choice.get("finish_reason"):
                if finish and finish != choice["finish_reason"]:
                    raise ValueError("Conflicting tool terminal events")
                finish = choice["finish_reason"]
    if not done or finish != "tool_calls" or not calls:
        raise ValueError("Tool stream did not finish with complete tool calls")
    message["tool_calls"] = [calls[index] for index in sorted(calls)]
    for call in message["tool_calls"]:
        if not call["id"] or not call["function"]["name"]:
            raise ValueError("Tool stream omitted its name or call ID")
        if not isinstance(json.loads(call["function"]["arguments"]), dict):
            raise ValueError("Tool arguments are not an object")
    return message


class UzuCandidateLiveHarnessTests(unittest.TestCase):
    def test_tool_stream_reassembles_fragments_and_rejects_truncation(self):
        def event(delta, finish=None):
            return b"data: " + json.dumps({"choices": [{"index": 0,
                "delta": delta, "finish_reason": finish}]}).encode() + b"\n"
        lines = [event({"reasoning_content": "Read the generated fixture."}),
            event({"tool_calls": [{"index": 0, "id": "call_1", "type": "function",
                "function": {"name": "fixture_lookup", "arguments": '{"key":'}}]}),
            event({"tool_calls": [{"index": 0, "function": {"arguments": '"alpha"}'}}]}),
            event({}, "tool_calls"), b"data: [DONE]\n"]
        message = read_streamed_tool_message(lines)
        self.assertEqual(message["tool_calls"][0]["id"], "call_1")
        self.assertEqual(json.loads(message["tool_calls"][0]["function"]["arguments"]), {"key": "alpha"})
        self.assertTrue(message["reasoning_content"])
        for invalid in (lines[:-1], lines[:3] + lines[-1:],
                        lines[:3] + [event({}, "length"), lines[-1]],
                        lines[:-1] + [event({"content": "late"}), lines[-1]]):
            with self.assertRaises(ValueError):
                read_streamed_tool_message(invalid)

    def test_termination_unwinds_cleanup_and_restores_handlers_without_a_model(self):
        original = {number: signal.getsignal(number) for number in (signal.SIGTERM, signal.SIGHUP)}
        cleanup = []
        with self.assertRaises(KeyboardInterrupt):
            with termination_runs_cleanup():
                try:
                    # Invoke the handler directly; do not signal any process.
                    signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
                finally:
                    cleanup.append(True)
        self.assertEqual(cleanup, [True])
        self.assertEqual({number: signal.getsignal(number) for number in original}, original)


@unittest.skipUnless(
    os.environ.get("LLM_LAUNCHER_UZU_LIVE_CANDIDATE") == "1"
    and os.environ.get("LLM_LAUNCHER_UZU_SOURCE"),
    "requires explicit real-model candidate test and exclusive idle controller",
)
class UzuCandidateLiveBoundaryTests(unittest.TestCase):
    def assert_installed_pi_hub(self, app, owner):
        """Use the real provider/RPC/Hub path with only one generated-data tool.

        This deliberately does not relax production Uzu client admission. The
        live model and relay are already normally admitted as qualified Chat;
        a test-only Pi attachment probes compatibility before enabling it.
        """
        binary = shutil.which("pi")
        self.assertIsNotNone(binary)
        console = None
        with tempfile.TemporaryDirectory(prefix="uzu-pi-tool-check-") as directory:
            root = Path(directory)
            project, config = root / "project", root / "config"
            project.mkdir(); config.mkdir()
            plan = replace(owner, run_id=str(uuid.uuid4()), client="pi", agent_host="console",
                           project=str(project), client_argv=[], client_env={})
            with mock.patch.dict(app.BINARIES, {"pi":binary}):
                app.build_pi_client(plan, app.ClientRoute("launcher-uzu-fixture", app.UZU_MODEL_REGISTRY_ID,
                    f"http://127.0.0.1:{owner.client_port}/v1", owner.secrets["clientApiKey"]))
                plan.client_argv.extend([
                    "--no-session", "--tools", "fixture_lookup", "--no-extensions", "--no-skills",
                    "--no-prompt-templates", "--no-themes", "--no-context-files", "--no-approve", "--offline",
                    "--extension", str(ROOT / "tests/fixtures/pi-generated-tool.js"),
                    "--system-prompt", "Use only the generated fixture tool. Do not access files or run commands.",
                ])
                plan.client_env.update({"PI_CODING_AGENT_DIR":str(config),
                    "PI_CODING_AGENT_SESSION_DIR":str(root / "sessions"), "PI_OFFLINE":"1", "PI_TELEMETRY":"0"})
                attachment = app.SurfaceAttachment(owner_run_id=owner.run_id, plan=plan, primary=False)
                try:
                    with mock.patch.dict(os.environ, {"PATH":os.environ["PATH"]}, clear=True):
                        console = app.MANAGER._launch_agent_console(plan, app.MANAGER.cancel_event,
                            owner_plan=owner, attachment=attachment)
                    app.MANAGER.write_agent_console({"ownerRunId":owner.run_id,"surfaceId":plan.run_id,
                        "command":"prompt", "message":"Call fixture_lookup once with key alpha. Read the returned JSON object's value field. Reply only with that string, without quotes, JSON, or any other answer text."})
                    deadline = time.monotonic() + 120
                    while time.monotonic() < deadline:
                        snapshot = console.output_slice(0)
                        results = [event for event in snapshot["timelineEvents"] if event["kind"] == "toolResult"]
                        answers = [event for event in snapshot["timelineEvents"] if event["kind"] == "answer"
                                   and event.get("operation") == "replace"]
                        if answers and not console.rpc_streaming and not console.rpc_prompt_inflight:
                            break
                        self.assertIsNone(console.process.poll(), "Pi exited before completing its tool turn")
                        self.assertFalse(console.rpc_queue_paused, "Pi paused on an error: " + bytes(console.output).decode(errors="replace")[-3000:])
                        time.sleep(0.1)
                    else:
                        self.fail("Real Pi tool turn did not finish: " + bytes(console.output).decode(errors="replace")[-4000:])
                    # RPC history and live finalisation may replace the same
                    # tool item. Distinct generated values expose real repeated
                    # executions; the browser reducer below must yield one item.
                    values = {json.loads(event["text"])["value"] for event in results}
                    self.assertEqual(len(values),1, "Expected one generated tool execution, not repeated calls")
                    value = next(iter(values))
                    self.assertTrue(value.startswith("fixture-"))
                    self.assertEqual(answers[-1]["text"].strip(),value)
                    self.assertTrue(any(event["kind"] == "thinking" for event in snapshot["timelineEvents"]))
                    # Apply the real browser-side reconciliation to the actual
                    # installed Pi events, not a generated envelope fixture.
                    replay = subprocess.run([shutil.which("node"), "-e",
                        "const fs=require('fs'),t=require('./pi_timeline.js');"
                        "const e=JSON.parse(fs.readFileSync(0,'utf8'));"
                        "const s=t.applyTimelineEnvelope(t.emptyTimeline(),e).state;"
                        "const r=s.items.filter(x=>x.kind==='toolResult');"
                        "const a=s.items.filter(x=>x.kind==='answer').at(-1);"
                        "if(r.length!==1||a.text.trim()!==JSON.parse(r[0].text).value)process.exit(1);"],
                        input=json.dumps(snapshot),text=True,capture_output=True,cwd=ROOT,timeout=10)
                    self.assertEqual(replay.returncode,0,replay.stderr)
                    print("Installed Pi completed a real tool turn through the launcher relay; Hub thinking, tool result and final answer survived reconciliation.",flush=True)
                finally:
                    if console is not None:
                        app.MANAGER._stop_agent_console_process(console)

    def test_native_rejection_and_stream_interruption_allow_a_complete_next_turn(self):
        sys.path.insert(0, str(ROOT))
        sys.path.insert(0, str(PATCH_ROOT))
        import candidate_qualification as candidate
        from verify_candidate_source import verify

        verify(Path(os.environ["LLM_LAUNCHER_UZU_SOURCE"]))
        spec = importlib.util.spec_from_file_location("uzu_candidate_boundary_app", ROOT / "launcher.py")
        app = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = app
        spec.loader.exec_module(app)
        lock_path = candidate.configure_candidate(app)
        with candidate.exclusive_controller_lock(lock_path), termination_runs_cleanup(), private_session_files():
            # The real session relay intentionally accepts configs only below
            # the normal private runs root. Use one fresh UUID-owned run there,
            # not a weaker relay or a configurable trust root. Benchmark
            # receipts, runtime identity, and all other state remain isolated.
            app.RUNS_DIR = lock_path.parent / "runs"
            models = app.uzu_model_records(app.load_benchmark_records())
            payload = candidate.request(65536)
            calibration = app.calibration_plan(payload, models)
            self.assertEqual(calibration.get("action"), "apply-existing", "Qualify this candidate at 64K first")
            # Use normal session admission, not the qualification-only bypass of
            # the no-receipt state. The ordinary live Uzu guard remains active.
            dashboard = app.session_dashboard_plan(payload, models)
            admission = dashboard.get("admission", {})
            self.assertTrue(app.strict_model_load_admission_ready(admission), admission)
            app.require_session_launch_admission(payload, admission)
            plan = app.normalized_request(payload, models, purpose="session")
            try:
                app.MANAGER.start(plan)
                deadline = time.monotonic() + 120
                while app.MANAGER.snapshot().get("phase") != "running":
                    status = app.MANAGER.snapshot()
                    self.assertNotIn(status.get("phase"), {"idle", "failed", "error"}, status.get("message"))
                    self.assertLess(time.monotonic(), deadline, "Candidate session startup timed out")
                    time.sleep(0.25)
                print("Uzu ready: exact qualified 64K session, ordinary memory guard active.", flush=True)

                base = f"http://127.0.0.1:{plan.port}/v1"

                def send(body=None, *, authenticate=True, path="/chat/completions", relay=False):
                    headers = {"Content-Type": "application/json"}
                    if authenticate:
                        key = "clientApiKey" if relay else "apiKey"
                        headers["Authorization"] = f"Bearer {plan.secrets[key]}"
                    endpoint = f"http://127.0.0.1:{plan.client_port}/v1" if relay else base
                    request = urllib.request.Request(
                        endpoint + path, data=None if body is None else json.dumps(body).encode(), headers=headers,
                    )
                    return urllib.request.urlopen(request, timeout=90)

                def reject(body=None, *, authenticate=True, path="/chat/completions", code=400):
                    try:
                        with send(body, authenticate=authenticate, path=path) as response:
                            response.read(4096)
                    except urllib.error.HTTPError as error:
                        with error:
                            self.assertEqual(error.code, code)
                            return error.read(16000).decode()
                    self.fail("Native server unexpectedly accepted an invalid request")

                reject(authenticate=False, path="/models", code=401)
                body = {
                    "model": app.UZU_MODEL_REGISTRY_ID,
                    "messages": [{"role": "user", "content": "What is 41 + 1? Give the result."}],
                    "max_tokens": 4096, "stream": False,
                }
                reject({**body, "max_tokens": 0})
                reject({**body, "max_completion_tokens": 0})
                # Native policy clamps oversized positive limits; it does not
                # reject them. Exercise the stricter of both aliases without
                # generating a wasteful 16K-token response just to hit the cap.
                with send({**body, "max_tokens": 8, "max_completion_tokens": 16385}) as response:
                    limited = json.load(response)
                self.assertEqual(limited["choices"][0].get("finish_reason"), "length")
                self.assertEqual(limited.get("usage", {}).get("completion_tokens"), 8)
                overflow = {**body, "messages": [{"role": "user", "content": "hello " * 70000}]}
                self.assertIn("context", reject(overflow).lower())
                print("Native authentication and request-limit checks passed.", flush=True)

                def assert_complete_recovery(*, relay=False):
                    with send(body, relay=relay) as response:
                        result = json.load(response)
                    choice = result["choices"][0]
                    self.assertEqual(choice.get("finish_reason"), "stop")
                    message = choice["message"]
                    self.assertIn("42", message.get("content", ""))
                    self.assertTrue(message.get("reasoning_content"), "Separate reasoning is required")
                    self.assertGreater(result.get("usage", {}).get("completion_tokens", 0), 0)

                assert_complete_recovery()
                long_turn = {
                    **body, "stream": True,
                    "messages": [{"role": "user", "content": "Count from 1 to 2000, writing every number separately."}],
                }
                interrupted = False
                with send(long_turn) as response:
                    for raw_line in response:
                        if not raw_line.startswith(b"data:"):
                            continue
                        event_text = raw_line[5:].strip()
                        if event_text == b"[DONE]":
                            break
                        event = json.loads(event_text)
                        for choice in event.get("choices", []):
                            delta = choice.get("delta", {})
                            if delta.get("reasoning_content") or delta.get("content"):
                                self.assertIsNone(choice.get("finish_reason"))
                                interrupted = True
                                break
                        if interrupted:
                            break  # Close the stream while generation is active.
                self.assertTrue(interrupted, "No active generated stream was observed")
                assert_complete_recovery()
                # Also cross the unchanged, normally configured app relay; a
                # native-only pass must not stand in for a working chat route.
                assert_complete_recovery(relay=True)
                print("Interrupted-stream recovery passed natively and through the launcher relay.", flush=True)

                # No tools are executed: only this one fixed, generated fixture
                # is returned. The second turn must use a nonce created AFTER
                # the call, so merely emitting plausible tool syntax cannot pass.
                for relay in (False, True):
                    with self.subTest(tool_round_trip_via_relay=relay):
                        prompt = {"role": "user", "content": (
                            "Call fixture_lookup once with key alpha. Read the returned JSON object's "
                            "value field. Reply only with that string, without quotes, JSON, or any other answer text."
                        )}
                        tools = [{"type": "function", "function": {
                            "name": "fixture_lookup", "description": "Read a synthetic test value.",
                            "parameters": {"type": "object", "properties": {
                                "key": {"type": "string", "enum": ["alpha"]}},
                                "required": ["key"], "additionalProperties": False}}}]
                        request = {**body, "messages": [prompt], "tools": tools,
                            "tool_choice": "auto", "stream": True}
                        with send(request, relay=relay) as response:
                            assistant = read_streamed_tool_message(response)
                        self.assertEqual(len(assistant["tool_calls"]), 1)
                        call = assistant["tool_calls"][0]
                        self.assertEqual(call["function"]["name"], "fixture_lookup")
                        self.assertEqual(json.loads(call["function"]["arguments"]), {"key": "alpha"})
                        nonce = "fixture-" + uuid.uuid4().hex
                        tool_result = {"role": "tool", "tool_call_id": call["id"],
                            "name": "fixture_lookup", "content": json.dumps({"value": nonce})}
                        with send({**request, "stream": False,
                                   "messages": [prompt, assistant, tool_result]}, relay=relay) as response:
                            final = json.load(response)["choices"][0]
                        self.assertEqual(final["finish_reason"], "stop")
                        self.assertFalse(final["message"].get("tool_calls"))
                        self.assertEqual(final["message"]["content"].strip(), nonce)
                        print(f"Generated tool round trip passed via {'launcher relay' if relay else 'native server'}.", flush=True)
                if os.environ.get("LLM_LAUNCHER_UZU_PI_LIVE") == "1":
                    self.assert_installed_pi_hub(app, plan)
            finally:
                app.MANAGER.stop()
                app.dispose_plan_secrets(plan)
                self.assertEqual(app.MANAGER.snapshot().get("phase"), "idle")
                process = app.MANAGER.process
                self.assertTrue(process is None or process.poll() is not None)
                print("Uzu test-owned process stopped cleanly.", flush=True)


if __name__ == "__main__":
    unittest.main()
