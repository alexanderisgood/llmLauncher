"""Controller/PTY lifecycle regressions for the explicit OMP dialect.

The tiny child emits pinned native event shapes; no models or external tools.
Real executable qualification is separately opt-in.
"""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

import launcher


FIXTURE = r'''
import json, pathlib, sys, threading, time
root = pathlib.Path(sys.argv[1])
lock = threading.Lock()
pending = None
async_work = False
current_session = root / "current.jsonl"
resume_pending = None
def emit(value):
    with lock:
        print(json.dumps(value, ensure_ascii=False, separators=(",", ":")), flush=True)
def reply(cmd, data=None):
    emit({"type":"response", "id":cmd["id"], "command":cmd["type"], "success":True, "data":data or {}})
def finish(identifier, text, *, async_pending=False, status="completed"):
    global pending, async_work
    emit({"type":"message_start", "messageId":identifier, "message":{"role":"assistant", "content":[]}})
    emit({"type":"message_update", "messageId":identifier, "assistantMessageEvent":{"type":"text_delta", "contentIndex":0, "delta":text}})
    emit({"type":"message_end", "messageId":identifier, "message":{"role":"assistant", "content":[{"type":"text", "text":text}], "stopReason":"aborted" if status=="aborted" else "stop"}})
    async_work = async_pending
    emit({"type":"agent_end", "messages":[], "isTerminal":True, "yielded":True, "awaitingAsyncWork":async_pending})
    emit({"type":"prompt_result", "id":identifier, "agentInvoked":True, "status":status, "sessionSettled":not async_pending})
    pending = None
    if not async_pending:
        emit({"type":"session_settled"})
def release():
    global async_work
    while not (root / "release").exists(): time.sleep(.01)
    async_work = False
    emit({"type":"session_settled"})
def complete_resume(identifier):
    global resume_pending
    while (root / "hold-picker").exists() and not (root / "select-picker").exists(): time.sleep(.01)
    emit({"type":"extension_ui_request","method":"setStatus","statusKey":"launcher.resumeSession","statusText":json.dumps({"sessionPath":str(root / "saved.jsonl")})})
    resume_pending = None
    emit({"type":"prompt_result","id":identifier,"agentInvoked":False,"status":"completed","sessionSettled":True})
emit({"type":"ready", "protocolVersion":1, "supportedProtocolVersions":[1,2], "maxFrameBytes":1048576, "maxReassembledFrameBytes":67108864})
for line in sys.stdin:
    cmd = json.loads(line)
    with (root / "commands.jsonl").open("a") as handle: handle.write(json.dumps(cmd) + "\n")
    kind = cmd["type"]
    if kind == "negotiate_protocol": reply(cmd, {"protocolVersion":2})
    elif kind == "get_state": reply(cmd, {"isStreaming":pending is not None or resume_pending is not None, "isCompacting":False, "isSettled":pending is None and resume_pending is None and not async_work, "hasPendingAsyncWork":async_work, "queuedMessageCount":0, "queuedMessages":{"steering":[], "followUp":[]}, **({"sessionFile":str(current_session)} if current_session.exists() else {})})
    elif kind == "get_messages": reply(cmd, {"messages":[{"role":"assistant","content":[{"type":"text","text":"Saved answer"}],"stopReason":"stop"}] if current_session.name=="saved.jsonl" else []})
    elif kind == "get_available_commands": reply(cmd, {"commands":[{"name":"status", "source":"builtin", "description":"Local status"},{"name":"resume", "source":"extension", "description":"Resume a saved conversation"}]})
    elif kind == "switch_session":
        if (root / "reject-resume").exists():
            emit({"type":"response","id":cmd["id"],"command":kind,"success":False,"error":"Generated switch failure"})
        else:
            cancelled = (root / "cancel-resume").exists()
            if not cancelled: current_session = pathlib.Path(cmd["sessionPath"])
            reply(cmd,{"cancelled":cancelled})
    elif kind == "prompt":
        if cmd["message"] == "/resume":
            resume_pending = cmd["id"]
            reply(cmd)  # Admission ACK precedes the asynchronous picker.
            threading.Thread(target=complete_resume,args=(cmd["id"],),daemon=True).start()
            continue
        if cmd["message"] in {"tracked-reject", "outer-reject"}:
            emit({"type":"response", "id":cmd["id"], "command":"prompt", "success":False, "error":"Generated preflight failure"})
            if cmd["message"] == "tracked-reject":
                reply(cmd)
                emit({"type":"prompt_result", "id":cmd["id"], "agentInvoked":False, "status":"error", "sessionSettled":True,
                      "error":{"message":"Generated preflight failure", "retryable":False}})
            continue
        if cmd["message"] == "/status":
            reply(cmd, {"agentInvoked":False})
            continue
        reply(cmd)
        pending = cmd["id"]
        emit({"type":"agent_start"})
        if cmd["message"] == "async":
            finish(cmd["id"], "First answer", async_pending=True)
            threading.Thread(target=release, daemon=True).start()
        elif cmd["message"] != "hold": finish(cmd["id"], cmd["message"])
    elif kind == "abort":
        if pending: finish(pending, "Partial answer", status="aborted")
        reply(cmd)
    else: reply(cmd)
'''


class OMPConsoleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="omp-controller-fixture-")
        self.root = Path(self.temporary.name)
        script = self.root / "agent.py"
        script.write_text(FIXTURE)
        self.plan = launcher.LaunchPlan(run_id="omp-controller-fixture", backend="splash", client="omp",
            model={"id":"fixture", "name":"Generated model", "backends":{}},
            project=str(self.root), context=8192, output=512, reasoning="off", port=18987,
            mode="ar", options={}, agent_host="console")
        self.plan.client_argv = [sys.executable, str(script), str(self.root), "--mode", "rpc"]
        self.manager = launcher.RunManager()
        self.manager.plan = self.plan
        self.manager.state = {"phase":"running", "run":self.plan.public(), "events":[]}
        self.manager.attachments[self.plan.run_id] = launcher.SurfaceAttachment(
            owner_run_id=self.plan.run_id, plan=self.plan, primary=True)
        self.payload = {"ownerRunId":self.plan.run_id, "surfaceId":self.plan.run_id}
        with mock.patch.dict(launcher.BINARIES, {"omp":sys.executable}), mock.patch.object(launcher, "command_version", return_value="omp/18.6.3"):
            self.console = self.manager._launch_agent_console(self.plan, self.manager.cancel_event)
        self.wait_for(lambda: self.console.rpc_ready or self.console.rpc_failure)
        self.assertFalse(self.console.rpc_failure)
        self.assertTrue(self.console.rpc_ready)

    def tearDown(self):
        if hasattr(self, "console"):
            self.manager._stop_agent_console_process(self.console)
            self.wait_for(lambda: self.console.master_fd < 0)
        self.temporary.cleanup()

    def wait_for(self, predicate, seconds=4):
        deadline = time.monotonic() + seconds
        while not predicate() and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(predicate(), self.console.rpc_failure if hasattr(self, "console") else "Fixture timed out")

    def send(self, message):
        return self.manager.write_agent_console({**self.payload, "command":"prompt", "message":message})

    def commands(self):
        return [json.loads(line) for line in (self.root / "commands.jsonl").read_text().splitlines()]

    def test_async_yield_does_not_advance_follow_up_until_native_settlement(self):
        self.send("async")
        self.wait_for(lambda: b"First answer" in self.console.output)
        self.send("queued follow-up")
        self.send("second follow-up")
        self.manager.read_agent_console(self.payload)
        self.wait_for(lambda: any(command["type"] == "get_state" and command["id"].startswith("launcher-state-") for command in self.commands()))
        time.sleep(.06)
        self.assertTrue(self.console.rpc_streaming)
        self.assertEqual([c["message"] for c in self.commands() if c["type"] == "prompt"], ["async"])
        (self.root / "release").touch()
        self.wait_for(lambda: b"second follow-up" in self.console.output and not self.console.rpc_prompt_inflight)
        self.assertEqual([c["message"] for c in self.commands() if c["type"] == "prompt"], ["async", "queued follow-up", "second follow-up"])
        self.assertFalse(self.console.rpc_queue_paused)
        self.assertFalse(self.console.rpc_failure)
        public = self.manager.read_agent_console({**self.payload, "timelineVersion":1})
        self.assertEqual(public["protocol"], "omp-rpc")
        self.assertTrue(public["terminalOmitted"])
        self.assertTrue(any(item["kind"] == "answer" and item["text"] == "First answer" for item in public["timelineEvents"]))

    def prepare_resume(self):
        self.wait_for(lambda: any(c["name"] == "resume" for c in self.console.rpc_commands))
        for name in ("current.jsonl", "saved.jsonl"):
            (self.root / name).write_text("{}\n")
        self.console.rpc_queue_directory = self.root / "queues"
        self.console.rpc_queue_session = str(self.root / "current.jsonl")
        self.plan.client_env["LLM_LAUNCHER_OMP_PROVIDER"] = json.dumps({
            "id":"launcher-current-local", "models":[{"id":"selected-local-model"}]})
        self.console.append_timeline("answer", "Old conversation answer", item_id="old-answer")

    def test_resume_uses_native_switch_with_current_model_and_keeps_old_queue_scoped(self):
        self.prepare_resume()
        (self.root / "hold-picker").touch()
        self.console.rpc_follow_up_queue.append("Belongs to old conversation")
        old_path = launcher.pi_rpc_queue_path(self.console)
        self.send("/resume")
        self.manager._write_pi_rpc_command(self.console,{"id":"picker-probe","type":"get_state"})
        self.wait_for(lambda: self.console.rpc_streaming)
        self.assertTrue(self.console.rpc_command_ids, "An admission ACK must not close the picker")
        (self.root / "select-picker").touch()
        self.wait_for(lambda: self.console.rpc_queue_session == str(self.root / "saved.jsonl")
                      and self.console.rpc_history_loaded and not self.console.rpc_command_ids)
        switch = next(c for c in self.commands() if c["type"] == "switch_session")
        self.assertEqual((switch["provider"],switch["modelId"]), ("launcher-current-local","selected-local-model"))
        self.assertEqual(switch["sessionPath"],str(self.root / "saved.jsonl"))
        self.assertEqual(json.loads(old_path.read_text())["messages"], ["Belongs to old conversation"])
        self.assertEqual(self.console.rpc_follow_up_queue, [])
        items = list(self.console.rpc_timeline_items.values())
        self.assertTrue(any(i["text"] == "Saved answer" for i in items))
        self.assertFalse(any(i["text"] == "Old conversation answer" for i in items))
        self.assertEqual([c["message"] for c in self.commands() if c["type"] == "prompt"], ["/resume"])
        self.assertFalse(self.console.rpc_failure)

    def test_cancelled_or_failed_resume_retains_current_history(self):
        self.prepare_resume()
        (self.root / "cancel-resume").touch()
        self.send("/resume")
        self.wait_for(lambda: any(c["type"] == "switch_session" for c in self.commands())
                      and not self.console.rpc_command_ids)
        self.assertEqual(self.console.rpc_queue_session,str(self.root / "current.jsonl"))
        self.assertTrue(any(i["text"] == "Old conversation answer" for i in self.console.rpc_timeline_items.values()))
        (self.root / "cancel-resume").unlink()
        (self.root / "reject-resume").touch()
        self.send("/resume")
        self.wait_for(lambda: sum(c["type"] == "switch_session" for c in self.commands()) == 2
                      and not self.console.rpc_command_ids)
        self.assertTrue(any(i["text"] == "Generated switch failure" for i in self.console.rpc_timeline_items.values()))
        self.assertTrue(any(i["text"] == "Old conversation answer" for i in self.console.rpc_timeline_items.values()))
        self.assertFalse(self.console.rpc_failure)

    def test_resume_does_not_switch_from_unrelated_status_or_while_agent_is_busy(self):
        self.prepare_resume()
        self.console.rpc_statuses["launcher.resumeSession"] = {"text":json.dumps({"sessionPath":str(self.root / "saved.jsonl")})}
        self.manager._consume_agent_rpc_event(self.console,{"type":"response","id":"unrelated","command":"prompt","success":True})
        self.assertFalse(any(c["type"] == "switch_session" for c in self.commands()))
        self.send("hold")
        self.wait_for(lambda: self.console.rpc_prompt_acknowledged)
        with self.assertRaisesRegex(ValueError,"finish"):
            self.send("/resume")

    def test_resume_refuses_switch_when_old_queued_messages_cannot_be_saved(self):
        self.prepare_resume()
        self.console.rpc_follow_up_queue.append("Do not move this message to a different conversation")
        self.console.queue_io = launcher.agent_console_rpc.QueueIO(
            read=lambda _path: {}, write=mock.Mock(side_effect=OSError("Generated disk failure")))
        self.send("/resume")
        self.wait_for(lambda: any(i.get("title") == "Could not resume conversation"
                                 for i in self.console.rpc_timeline_items.values()))
        self.assertFalse(any(c["type"] == "switch_session" for c in self.commands()))
        self.assertEqual(self.console.rpc_queue_session,str(self.root / "current.jsonl"))
        self.assertEqual(len(self.console.rpc_follow_up_queue),1)
        self.assertTrue(any(i["text"] == "Old conversation answer" for i in self.console.rpc_timeline_items.values()))

    def test_explicit_resume_queue_sends_the_retained_head_once_and_drains_in_order(self):
        self.console.rpc_follow_up_queue.extend(["saved first message","saved second message"])
        self.console.rpc_queue_paused = True
        self.manager.write_agent_console({**self.payload,"command":"resume_queue"})
        self.wait_for(lambda: b"saved second message" in self.console.output and not self.console.rpc_prompt_inflight)
        self.assertEqual([c["message"] for c in self.commands() if c["type"] == "prompt"],
                         ["saved first message","saved second message"])
        self.assertEqual(self.console.rpc_follow_up_queue,[])
        self.assertFalse(self.console.rpc_queue_paused)
        self.assertFalse(self.console.rpc_failure)

    def test_explicit_resume_queue_cannot_interrupt_a_running_turn(self):
        self.send("hold")
        self.wait_for(lambda: self.console.rpc_prompt_acknowledged)
        self.send("Keep this queued")
        with self.assertRaisesRegex(ValueError,"finish"):
            self.manager.write_agent_console({**self.payload,"command":"resume_queue"})
        self.assertEqual(self.console.rpc_follow_up_queue,["Keep this queued"])

    def test_abort_preserves_and_pauses_follow_up(self):
        self.send("hold")
        self.wait_for(lambda: self.console.rpc_prompt_acknowledged)
        self.send("must stay queued")
        self.manager.write_agent_console({**self.payload, "command":"abort"})
        self.wait_for(lambda: not self.console.rpc_prompt_inflight)
        self.assertEqual(self.console.rpc_follow_up_queue, ["must stay queued"])
        self.assertTrue(self.console.rpc_queue_paused)
        self.assertEqual([c["message"] for c in self.commands() if c["type"] == "prompt"], ["hold"])

    def test_local_command_finishes_without_fabricated_answer_or_incomplete_notice(self):
        self.wait_for(lambda: bool(self.console.rpc_commands))
        self.send("/status")
        self.wait_for(lambda: not self.console.rpc_prompt_inflight)
        self.assertFalse(self.console.rpc_streaming)
        self.assertFalse(self.console.rpc_last_assistant)
        self.assertNotIn(b"without visible output", self.console.output)
        self.assertFalse(any(item["kind"] == "answer" for item in self.console.rpc_timeline_items.values()))

    def test_bad_frame_closes_only_the_owned_console_and_keeps_partial_output(self):
        self.send("hold")
        self.wait_for(lambda: self.console.rpc_prompt_acknowledged)
        self.console.append(b"Retained partial output")
        self.console.rpc_follow_up_queue.append("retained input")
        self.manager._consume_pi_rpc_line(self.console, b'{"type":"rpc_chunk","index":7}')
        self.wait_for(lambda: self.console.process.poll() is not None)
        self.assertTrue(self.console.rpc_failure)
        self.assertTrue(self.console.rpc_queue_paused)
        self.assertIn(b"Retained partial output", self.console.output)
        self.assertIs(self.manager.plan, self.plan)
        self.assertEqual(self.manager.state["phase"], "running")
        self.assertFalse(self.console.public()["canInput"])

    def test_late_admission_error_waits_for_native_outcome_before_pausing(self):
        self.send("hold")
        self.wait_for(lambda: self.console.rpc_prompt_acknowledged)
        self.send("kept follow-up")
        identifier = self.console.rpc_prompt_id
        self.manager._consume_agent_rpc_event(self.console, {"type":"response", "command":"prompt",
            "id":identifier, "success":False, "error":"Generated late failure", "ompAwaitingPromptResult":True})
        self.assertTrue(self.console.rpc_prompt_inflight)
        self.assertTrue(self.console.rpc_streaming)
        self.manager._consume_agent_rpc_event(self.console, {"type":"launcher_prompt_result",
            "id":identifier, "status":"error", "agentInvoked":False, "sessionSettled":True,
            "error":{"message":"Generated late failure"}})
        self.assertTrue(self.console.rpc_prompt_inflight)
        self.manager._consume_agent_rpc_event(self.console, {"type":"agent_settled"})
        self.assertFalse(self.console.rpc_prompt_inflight)
        self.assertTrue(self.console.rpc_queue_paused)
        self.assertEqual(self.console.rpc_follow_up_queue, ["kept follow-up"])

    def test_rejected_transport_write_rolls_back_unadmitted_prompt(self):
        transport = self.manager._agent_console_transport(self.console)
        with mock.patch.object(transport, "send", side_effect=ValueError("Generated full buffer")):
            with self.assertRaisesRegex(ValueError, "full buffer"):
                self.send("retry after full buffer")
        self.assertFalse(self.console.rpc_prompt_inflight)
        self.assertFalse(self.console.omp_adapter.active_prompt_id)
        self.assertFalse(self.console.omp_adapter.busy)
        self.send("retry after full buffer")
        self.wait_for(lambda: b"retry after full buffer" in self.console.output and not self.console.rpc_prompt_inflight)
        self.assertFalse(self.console.rpc_failure)

    def test_tracked_preflight_failure_before_ack_keeps_console_usable_and_queue_paused(self):
        self.console.rpc_follow_up_queue.append("Keep follow-up")
        self.send("tracked-reject")
        self.wait_for(lambda: not self.console.rpc_prompt_inflight)
        self.assertFalse(self.console.rpc_failure)
        self.assertTrue(self.console.public()["canInput"])
        self.assertTrue(self.console.rpc_queue_paused)
        self.assertEqual(self.console.rpc_follow_up_queue, ["Keep follow-up"])
        self.assertEqual([c["message"] for c in self.commands() if c["type"] == "prompt"], ["tracked-reject"])
        self.assertTrue(any(item["kind"] == "error" and "preflight" in item["text"]
                            for item in self.console.rpc_timeline_items.values()))
        self.send("Recovery request")
        self.wait_for(lambda: b"Recovery request" in self.console.output)
        self.assertFalse(self.console.rpc_failure)

    def test_setup_only_rejection_uses_fresh_native_state_without_timeout_or_agent_activity(self):
        self.console.rpc_follow_up_queue.append("Keep follow-up")
        self.send("outer-reject")
        self.wait_for(lambda: not self.console.rpc_prompt_inflight)
        self.assertFalse(self.console.rpc_failure)
        self.assertFalse(self.console.omp_adapter.busy)
        self.assertTrue(self.console.rpc_queue_paused)
        self.assertEqual(self.console.rpc_follow_up_queue, ["Keep follow-up"])
        self.assertFalse(any(item["kind"] == "answer" for item in self.console.rpc_timeline_items.values()))
        commands = self.commands()
        prompt_position = next(index for index, command in enumerate(commands) if command["type"] == "prompt")
        self.assertTrue(any(command["type"] == "get_state" for command in commands[prompt_position + 1:]))
        self.assertEqual(self.console.rpc_settle_revision, 1)


if __name__ == "__main__":
    unittest.main()
