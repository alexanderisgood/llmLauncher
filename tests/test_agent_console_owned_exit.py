"""An exited console leader cannot leave owned inherited-fd workers behind."""
import json
import os
from pathlib import Path
import pty
import sys
import tempfile
import time
import unittest
from unittest import mock

import launcher
import omp_protocol
from agent_console_transport import ConsoleTransport


FIXTURE = r'''
import json, pathlib, subprocess, sys
root = pathlib.Path(sys.argv[1])
worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], stdin=subprocess.DEVNULL)
(root / "worker-pid").write_text(str(worker.pid))
def emit(value): print(json.dumps(value),flush=True)
def response(command,data=None): emit({"type":"response","id":command["id"],"command":command["type"],"success":True,"data":data or {}})
emit({"type":"ready","protocolVersion":1,"supportedProtocolVersions":[1,2],"maxFrameBytes":1048576,"maxReassembledFrameBytes":67108864})
for line in sys.stdin:
    command = json.loads(line)
    kind = command["type"]
    if kind == "negotiate_protocol": response(command,{"protocolVersion":2})
    elif kind == "get_state": response(command,{"isStreaming":False,"isCompacting":False,"isSettled":True,"hasPendingAsyncWork":False,"queuedMessageCount":0,"queuedMessages":{"steering":[],"followUp":[]}})
    elif kind == "get_messages": response(command,{"messages":[]})
    elif kind == "get_available_commands": response(command,{"commands":[]})
    elif kind == "prompt":
        response(command)
        emit({"type":"agent_start"})
        emit({"type":"message_start","messageId":"fixture-answer","message":{"role":"assistant","content":[]}})
        emit({"type":"message_end","messageId":"fixture-answer","message":{"role":"assistant","content":[{"type":"text","text":"DRAINED_BEFORE_EXIT"}],"stopReason":"stop"}})
        emit({"type":"agent_end","messages":[],"yielded":True,"isTerminal":True})
        emit({"type":"prompt_result","id":command["id"],"agentInvoked":True,"status":"completed","sessionSettled":True})
        emit({"type":"session_settled"})
        sys.exit(0)
    else: response(command)
'''


class AgentConsoleOwnedExitTests(unittest.TestCase):
    def wait_for(self, predicate, timeout=5):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(predicate())

    def test_idle_read_is_not_eof_and_closed_transport_is_eof(self):
        master, slave = pty.openpty()
        transport = ConsoleTransport(master)
        try:
            self.assertIsNone(transport.read(idle_timeout=.01))
            transport.close()
            self.assertEqual(transport.read(idle_timeout=.01), b"")
        finally:
            transport.close(); os.close(slave)

    def test_exited_leader_output_drains_then_its_inherited_fd_worker_stops(self):
        self.verify_inherited_worker_cleanup(FIXTURE)

    def test_clean_stdout_eof_still_stops_child_holding_only_stderr(self):
        self.verify_inherited_worker_cleanup(FIXTURE.replace(
            "stdin=subprocess.DEVNULL)", "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)"))

    def verify_inherited_worker_cleanup(self, source):
        with tempfile.TemporaryDirectory(prefix="owned-agent-exit-") as temporary:
            root = Path(temporary)
            script = root / "agent.py"; script.write_text(source)
            plan = launcher.LaunchPlan(run_id="owned-exit-fixture", backend="splash", client="omp",
                model={"id":"fixture", "name":"Generated", "backends":{}}, project=str(root),
                context=8192, output=512, reasoning="off", port=18987, mode="ar", options={}, agent_host="console")
            plan.client_argv = [sys.executable, str(script), str(root), "--mode", "rpc"]
            manager = launcher.RunManager(); manager.plan = plan
            manager.state = {"phase":"running", "run":plan.public(), "events":[]}
            manager.attachments[plan.run_id] = launcher.SurfaceAttachment(owner_run_id=plan.run_id, plan=plan, primary=True)
            console = None
            try:
                with mock.patch.dict(launcher.BINARIES, {"omp":sys.executable}), \
                        mock.patch.object(launcher, "command_version", return_value="omp/18.6.3"):
                    console = manager._launch_agent_console(plan, manager.cancel_event)
                self.wait_for(lambda: console.rpc_ready)
                manager.write_agent_console({"ownerRunId":plan.run_id,"surfaceId":plan.run_id,
                    "command":"prompt","message":"exit the fixture leader"})
                self.wait_for(lambda: console.process.poll() is not None)
                self.wait_for(lambda: console.master_fd < 0 and console.state == "exited")
                self.assertIn(b"DRAINED_BEFORE_EXIT", console.output)
                self.assertFalse(console.rpc_failure)
                self.assertTrue(console.public()["canRestart"])
                self.assertIs(manager.plan, plan)
                self.assertEqual(manager.state["phase"], "running", "The shared model owner remains active")
                worker = int((root / "worker-pid").read_text())
                def gone():
                    try:
                        os.kill(worker, 0)
                    except ProcessLookupError:
                        return True
                    return False
                self.wait_for(gone)
            finally:
                if console is not None:
                    # Only the fresh fixture's owned session group is touched.
                    manager._terminate_process(console.process, 1)
                    manager._close_agent_console_fd(console)

    def test_stop_closes_open_resources_even_when_leader_already_exited(self):
        master, slave = pty.openpty()
        plan = launcher.LaunchPlan(run_id="stopped-exit-fixture", backend="splash", client="omp",
            model={"name":"Generated"}, project="/private/tmp", context=8192, output=512,
            reasoning="off", port=18987, mode="ar", options={}, agent_host="console")
        process = mock.Mock(returncode=0); process.poll.return_value = 0
        console = launcher.AgentConsole(owner_run_id=plan.run_id, plan=plan, process=process,
            master_fd=master, cols=100, rows=30, transport=ConsoleTransport(master), protocol="omp-rpc")
        manager = launcher.RunManager(); manager.agent_consoles[plan.run_id] = console
        try:
            with mock.patch.object(manager, "_terminate_process") as terminate:
                manager._stop_agent_console_process(console)
            terminate.assert_called_once_with(process, 5)
            self.assertEqual(console.master_fd, -1)
            self.assertEqual(console.state, "stopped")
            self.assertEqual(console.exit_code, 0)
        finally:
            manager._close_agent_console_fd(console); os.close(slave)

    def test_multiple_bad_records_preserve_first_protocol_failure_and_cleanup_once(self):
        master, slave = pty.openpty()
        plan = launcher.LaunchPlan(run_id="failed-frame-fixture", backend="splash", client="omp",
            model={"name":"Generated"}, project="/private/tmp", context=8192, output=512,
            reasoning="off", port=18987, mode="ar", options={}, agent_host="console")
        process = mock.Mock(); process.poll.return_value = None
        console = launcher.AgentConsole(owner_run_id=plan.run_id, plan=plan, process=process,
            master_fd=master, cols=100, rows=30, transport=ConsoleTransport(master),
            protocol="omp-rpc", omp_adapter=omp_protocol.Adapter())
        manager = launcher.RunManager()
        try:
            with mock.patch.object(manager, "_terminate_process") as terminate:
                manager._consume_pi_rpc_line(console, b"invalid JSON")
                original_error = console.rpc_failure
                revision = console.rpc_timeline_revision
                manager._consume_pi_rpc_line(console, b"{}")
            self.assertTrue(original_error)
            self.assertEqual(console.rpc_failure, original_error)
            self.assertEqual(console.rpc_timeline_revision, revision)
            terminate.assert_called_once_with(process, 3)
            self.assertEqual(console.master_fd, -1)
        finally:
            manager._close_agent_console_fd(console); os.close(slave)

    def test_noisy_inherited_fd_worker_cannot_hide_its_exited_leader(self):
        with tempfile.TemporaryDirectory(prefix="noisy-agent-exit-") as temporary:
            root = Path(temporary)
            script = root / "agent.py"
            worker_source = "import time\nwhile True:\n print('owned-worker-output',flush=True)\n time.sleep(.005)"
            script.write_text("import pathlib,subprocess,sys,time\n"
                f"worker=subprocess.Popen([sys.executable,'-c',{worker_source!r}],stdin=subprocess.DEVNULL)\n"
                "pathlib.Path(sys.argv[1],'worker-pid').write_text(str(worker.pid))\n"
                "time.sleep(.1)\nprint('NOISY_LEADER_FINAL',flush=True)\n")
            plan = launcher.LaunchPlan(run_id="noisy-exit-fixture", backend="splash", client="opencode",
                model={"name":"Generated"}, project=str(root), context=8192, output=512,
                reasoning="off", port=18987, mode="ar", options={}, agent_host="console")
            plan.client_argv = [sys.executable, str(script), str(root)]
            manager = launcher.RunManager(); manager.plan = plan
            manager.state = {"phase":"running", "run":plan.public(), "events":[]}
            console = None
            try:
                with mock.patch.dict(launcher.BINARIES, {"opencode":sys.executable}):
                    console = manager._launch_agent_console(plan, manager.cancel_event)
                self.wait_for(lambda: console.master_fd < 0 and console.state == "exited")
                self.assertIn(b"NOISY_LEADER_FINAL", console.output)
                self.assertIn(b"owned-worker-output", console.output)
                self.assertTrue(console.public()["canRestart"])
                worker = int((root / "worker-pid").read_text())
                def gone():
                    try:
                        os.kill(worker, 0)
                    except ProcessLookupError:
                        return True
                    return False
                self.wait_for(gone)
            finally:
                if console is not None:
                    manager._terminate_process(console.process, 1)
                    manager._close_agent_console_fd(console)

    def test_live_leader_closing_pty_then_hanging_is_finalized_and_restartable(self):
        with tempfile.TemporaryDirectory(prefix="closed-agent-stream-") as temporary:
            root = Path(temporary)
            script = root / "agent.py"
            script.write_text("import os,time\n"
                "print('LEADER_CLOSED_STREAM_FINAL',flush=True)\n"
                "os.close(0);os.close(1);os.close(2)\n"
                "time.sleep(60)\n")
            plan = launcher.LaunchPlan(run_id="closed-stream-fixture", backend="splash", client="opencode",
                model={"name":"Generated"}, project=str(root), context=8192, output=512,
                reasoning="off", port=18987, mode="ar", options={}, agent_host="console")
            plan.client_argv = [sys.executable, str(script)]
            manager = launcher.RunManager(); manager.plan = plan
            manager.state = {"phase":"running", "run":plan.public(), "events":[]}
            console = None
            try:
                with mock.patch.dict(launcher.BINARIES, {"opencode":sys.executable}), \
                        mock.patch.object(manager, "_terminate_process", wraps=manager._terminate_process) as terminate:
                    console = manager._launch_agent_console(plan, manager.cancel_event)
                    self.wait_for(lambda: console.master_fd < 0 and console.state == "failed")
                    terminate.assert_called_once_with(console.process, 3)
                self.assertIsNotNone(console.process.poll())
                self.assertIn(b"LEADER_CLOSED_STREAM_FINAL", console.output)
                self.assertTrue(console.public()["canRestart"])
                self.assertEqual(manager.state["phase"], "running")
            finally:
                if console is not None:
                    manager._terminate_process(console.process, 1)
                    manager._close_agent_console_fd(console)

    def test_unterminated_pi_record_is_drained_but_unfinished_omp_frame_fails(self):
        for client in ("pi", "omp"):
            with self.subTest(client=client), tempfile.TemporaryDirectory(prefix="agent-final-record-") as temporary:
                root = Path(temporary)
                script = root / "agent.py"
                prefix = ("print(" + repr(json.dumps({"type":"ready", "protocolVersion":1,
                    "supportedProtocolVersions":[1,2], "maxFrameBytes":1048576,
                    "maxReassembledFrameBytes":67108864})) + ", flush=True)\n") if client == "omp" else ""
                final = '{"type":"message_end",' if client == "omp" else json.dumps({"type":"message_end",
                    "message":{"role":"assistant","content":[{"type":"text","text":"PI_FINAL_RECORD"}],"stopReason":"stop"}})
                script.write_text("import subprocess,sys,time\n"
                    "subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],stdin=subprocess.DEVNULL)\n"
                    "time.sleep(.1)\n" + prefix + f"sys.stdout.write({final!r});sys.stdout.flush()\n")
                plan = launcher.LaunchPlan(run_id=f"final-record-{client}", backend="splash", client=client,
                    model={"name":"Generated", "backends":{}}, project=str(root), context=8192,
                    output=512, reasoning="off", port=18987, mode="ar", options={}, agent_host="console")
                plan.client_argv = [sys.executable, str(script), "--mode", "rpc"]
                manager = launcher.RunManager(); manager.plan = plan
                manager.state = {"phase":"running", "run":plan.public(), "events":[]}
                console = None
                try:
                    with mock.patch.dict(launcher.BINARIES, {client:sys.executable}), \
                            mock.patch.object(launcher, "command_version", return_value="omp/18.6.3"):
                        console = manager._launch_agent_console(plan, manager.cancel_event)
                    self.wait_for(lambda: console.master_fd < 0 and console.state in {"exited", "failed", "stopped"})
                    if client == "pi":
                        self.assertIn(b"PI_FINAL_RECORD", console.output)
                        self.assertFalse(console.rpc_failure)
                    else:
                        self.assertIn("ended inside an RPC frame", console.rpc_failure)
                        self.assertEqual(console.state, "failed")
                finally:
                    if console is not None:
                        manager._terminate_process(console.process, 1)
                        manager._close_agent_console_fd(console)


if __name__ == "__main__":
    unittest.main()
