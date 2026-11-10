"""Quit uses synthetic process identities; these tests never signal real AI."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import client_runner
import launcher_shutdown as shutdown


def process(pid=300, parent=1, command="/opt/test/omlx serve", started="Tue Oct 6 14:00:00 2026"):
    return shutdown.LocalProcess(os.getuid(), pid, parent, started, command)


class SelectionTests(unittest.TestCase):
    def test_multiple_terminal_instances_keep_independent_birth_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            run=root/"run"
            run.mkdir()
            records={301:process(301,command="first renamed agent"),302:process(302,command="second renamed agent")}
            for pid in records:
                with mock.patch.object(shutdown.os,"getpid",return_value=pid), \
                        mock.patch.object(shutdown,"process_snapshot",return_value=records):
                    shutdown.register_terminal_agent(run,"omp")
            receipts=list((run/"agent-processes").glob("*.json"))
            self.assertEqual(len(receipts),2)
            self.assertTrue(all(path.stat().st_mode&0o077==0 for path in receipts))
            self.assertEqual(set(shutdown.terminal_agent_receipts(root,records)),{301,302})
            reused={**records,302:process(302,started="new birth",command="unrelated")}
            self.assertEqual(set(shutdown.terminal_agent_receipts(root,reused)),{301})
    def test_exact_server_names_do_not_match_status_or_unrelated_python(self):
        app = Path("/private/tmp/launcher-test")
        binaries = {"omlx": "/opt/test/omlx", "mtplx": "/opt/test/mtplx"}
        snapshot = {p.pid: p for p in [
            process(300), process(301, 300, "python worker.py"),
            process(302, 301, "python tool.py"), process(303, 1, "/opt/test/omlx status"),
            process(304, 1, "/opt/test/omlx-backup serve"),
            process(305, 1, "python unrelated_mlx_task.py"),
            process(306, 1, "/opt/test/mtplx serve"),
        ]}
        self.assertEqual(set(shutdown.select_processes(snapshot, binaries, app)), {300, 301, 302, 306})

    def test_exact_installed_scripts_are_found_behind_node_and_bun(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            cli = root / "cli.mjs"
            cli.write_text("// fixture")
            binary = root / "omp"
            binary.symlink_to(cli)
            for interpreter in ("/opt/test/node", "/opt/test/bun"):
                command = f"{interpreter} {cli} --extension {root / 'omp-provider.mjs'}"
                self.assertEqual(shutdown.process_label(process(command=command), {"omp": str(binary)}, root), "omp")
                unrelated = f"{interpreter} {cli} --extension {root / 'omp-provider.mjs'}.backup"
                self.assertIsNone(shutdown.process_label(process(command=unrelated), {"omp": str(binary)}, root))
            self.assertIsNone(shutdown._command_tail(f"bun {cli}.backup --help", str(binary)))

    def test_reparenting_preserves_identity_but_pid_reuse_does_not(self):
        original = process(301, 300, "python worker.py")
        self.assertTrue(original.same_identity(process(301, 1, "python worker.py")))
        self.assertFalse(original.same_identity(process(301, 1, "python worker.py", "later start")))

    def test_isolated_wrappers_and_exact_splash_frontend_and_native_children_match(self):
        app = Path("/private/tmp/launcher-test")
        binaries = {"splash": "/opt/test/splash/libexec/engine/splash"}
        for script in ("splash_runtime.py", "kolibri_runtime.py", "slotstream_runtime.py", "whallm_runtime.py"):
            command = f"/opt/test/python3 -I -S -B {app / script} /private/tmp/config.json"
            self.assertIsNotNone(shutdown.process_label(process(command=command), binaries, app))
        for flags in ("-I -B -u", "-ISBu", "-u"):
            command = f"python3 {flags} /opt/test/splash/libexec/server/server.py target draft --port 18000"
            self.assertEqual(shutdown.process_label(process(command=command), binaries, app), "splash")
        native = process(command="/opt/test/splash/libexec/engine/splash serve-native target draft 16384 auto")
        self.assertEqual(shutdown.process_label(native, binaries, app), "splash")
        self.assertIsNone(shutdown.process_label(process(command="python3 -c /opt/test/splash/libexec/server/server.py"), binaries, app))
        self.assertIsNone(shutdown.process_label(process(command="python3 -m unrelated /opt/test/splash/libexec/server/server.py"), binaries, app))
        self.assertIsNone(shutdown.process_label(process(command="python3 -u /other/install/server/server.py"), binaries, app))

    def test_known_dedicated_servers_require_their_real_server_arguments(self):
        app = Path("/private/tmp/launcher-test")
        for key, binary in (("swiftlm", "/opt/test/SwiftLM"), ("mference", "/opt/test/MferenceServer")):
            self.assertEqual(shutdown.process_label(process(command=f"{binary} --model weights --port 18000"), {key: binary}, app), key)
            self.assertIsNone(shutdown.process_label(process(command=f"{binary} --help"), {key: binary}, app))
            self.assertIsNone(shutdown.process_label(process(command=f"{binary} --model weights --port malformed"), {key: binary}, app))

    def test_rapidmlx_requires_exact_installed_cli_and_serve_action(self):
        app = Path("/private/tmp/launcher-test")
        binary = "/opt/test/rapid-mlx"
        binaries = {"rapidmlx": binary}
        for command in (f"{binary} serve /models/local --port 18000",
                        f"/opt/test/python3 {binary} serve /models/local",
                        f"/opt/test/python3 -I -B {binary} serve /models/local"):
            self.assertEqual(shutdown.process_label(process(command=command), binaries, app), "rapidmlx")
        for command in (f"{binary} status", f"{binary} start", f"{binary} server",
                        f"{binary} api-server", f"{binary} --version", f"{binary}-backup serve model",
                        f"/other/rapid-mlx serve model", f"python3 -m rapid_mlx serve {binary}",
                        f"python3 -c 'print(\"{binary} serve\")'"):
            self.assertIsNone(shutdown.process_label(process(command=command), binaries, app), command)

    def test_receipts_find_primary_and_attached_agents_after_title_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = {}
            for pid, relative in ((301, "run/agent-process.json"),
                                  (302, "run/attachments/surface/agent-process.json")):
                path = root / relative
                path.parent.mkdir(parents=True)
                record = process(pid, command="oh-my-pi renamed title")
                path.write_text(json.dumps({"pid": pid, "started": record.started, "client": "omp"}))
                path.chmod(0o600)
                snapshot[pid] = record
            self.assertEqual(set(shutdown.terminal_agent_receipts(root, snapshot)), {301, 302})
            reused = process(302, command="unrelated", started="different start")
            self.assertEqual(set(shutdown.terminal_agent_receipts(root, {301: snapshot[301], 302: reused})), {301})

    def test_receipts_reject_public_files_symlinks_and_nonregular_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = {301: process(301, command="renamed")}
            receipt = root / "run/agent-process.json"
            receipt.parent.mkdir()
            receipt.write_text(json.dumps({"pid": 301, "started": snapshot[301].started, "client": "omp"}))
            receipt.chmod(0o644)
            self.assertEqual(shutdown.terminal_agent_receipts(root, snapshot), {})
            target = root / "private-receipt.json"
            receipt.rename(target)
            target.chmod(0o600)
            receipt.symlink_to(target)
            self.assertEqual(shutdown.terminal_agent_receipts(root, snapshot), {})
            receipt.unlink()
            os.mkfifo(receipt, 0o600)
            self.assertEqual(shutdown.terminal_agent_receipts(root, snapshot), {})


class StopTests(unittest.TestCase):
    def setUp(self):
        self.kill_patcher = mock.patch.object(shutdown.os, "kill")
        self.kill = self.kill_patcher.start()
        self.addCleanup(self.kill_patcher.stop)

    def test_children_are_signalled_after_reparenting_and_count_only_verified_exits(self):
        current = {300: process(), 301: process(301, 300, "python worker.py")}

        def send(pid, sig):
            if pid == 300:
                current.pop(pid, None)
                current[301] = process(301, 1, "python worker.py")
            else:
                current.pop(pid, None)

        self.kill.side_effect = send
        with mock.patch.object(shutdown, "process_snapshot", side_effect=lambda: dict(current)), \
                mock.patch.object(shutdown.time, "sleep"):
            result = shutdown.stop_local_servers({"omlx": "/opt/test/omlx"}, Path("/private/tmp/app"), grace=0)
        self.assertEqual(result, {"processesStopped": 2, "errors": []})
        self.assertIn(mock.call(301, signal.SIGTERM), self.kill.call_args_list)

    def test_reused_pid_is_never_killed(self):
        original, reused = process(), process(command="unrelated editor", started="different start")
        with mock.patch.object(shutdown, "process_snapshot", side_effect=[{300: original}, {300: reused}, {300: reused}, {300: reused}]), \
                mock.patch.object(shutdown.time, "sleep"):
            result = shutdown.stop_local_servers({"omlx": "/opt/test/omlx"}, Path("/private/tmp/app"), grace=0)
        self.kill.assert_not_called()
        self.assertEqual(result["processesStopped"], 1)

    def test_verified_renamed_service_worker_survives_reparenting_and_is_stopped(self):
        original=process(301,300,"python generic_worker.py")
        current={301:process(301,1,"renamed worker")}
        def send(pid,_sig):
            current.pop(pid,None)
        self.kill.side_effect=send
        with mock.patch.object(shutdown,"process_snapshot",side_effect=lambda:dict(current)), \
                mock.patch.object(shutdown.time,"sleep"):
            result=shutdown.stop_local_servers({},Path("/private/tmp/app"),grace=0,
                                               verified_processes={301:original})
        self.assertEqual(result,{"processesStopped":1,"errors":[]})
        self.kill.assert_called_once_with(301,signal.SIGTERM)

    def test_verified_service_receipt_does_not_authorize_a_reused_pid(self):
        original=process(301,command="omlx-server")
        current={301:process(301,command="unrelated",started="later start")}
        with mock.patch.object(shutdown,"process_snapshot",return_value=current):
            result=shutdown.stop_local_servers({},Path("/private/tmp/app"),grace=0,
                                               verified_processes={301:original})
        self.assertEqual(result,{"processesStopped":0,"errors":[]})
        self.kill.assert_not_called()

    def test_retitled_server_rechecks_kernel_birth_before_each_signal(self):
        target=process(301,command="omlx-server")
        current={301:target}
        receipt=SimpleNamespace(environment=object(),revalidate=mock.Mock(return_value=False))
        with mock.patch.object(shutdown,"process_snapshot",return_value=current), \
                mock.patch.object(shutdown.time,"sleep"):
            result=shutdown.stop_local_servers({},Path("/private/tmp/app"),grace=0,
                verified_processes={301:target},native_receipts={301:receipt})
        self.kill.assert_not_called()
        self.assertEqual(receipt.revalidate.call_count,2)
        self.assertEqual(result["processesStopped"],0)
        self.assertTrue(result["errors"])

    def test_same_interpreter_handoff_cannot_authorize_unrelated_python(self):
        original=process(301,command="omlx-server")
        current={301:process(301,command="python unrelated_script.py")}
        receipt=SimpleNamespace(environment=object(),revalidate=mock.Mock(return_value=True))
        with mock.patch.object(shutdown,"process_snapshot",return_value=current), \
                mock.patch.object(shutdown.time,"sleep"):
            result=shutdown.stop_local_servers({},Path("/private/tmp/app"),grace=0,
                verified_processes={301:original},native_receipts={301:receipt})
        self.kill.assert_not_called()
        self.assertEqual(result["processesStopped"],0)
        self.assertTrue(result["errors"])

    def test_signal_delivery_is_not_reported_as_an_exit(self):
        current = {300: process()}
        with mock.patch.object(shutdown, "process_snapshot", return_value=current), \
                mock.patch.object(shutdown.time, "sleep"):
            result = shutdown.stop_local_servers({"omlx": "/opt/test/omlx"}, Path("/private/tmp/app"), grace=0)
        self.assertEqual(result["processesStopped"], 0)
        self.assertTrue(result["errors"])
        self.assertEqual(self.kill.call_args_list, [mock.call(300, signal.SIGTERM), mock.call(300, signal.SIGKILL)])

    def test_changed_title_is_not_falsely_counted_as_an_exited_agent(self):
        original = process()
        renamed = process(command="changed title")
        with mock.patch.object(shutdown, "process_snapshot", side_effect=[{300: original}, {300: renamed}, {300: renamed}, {300: renamed}]), \
                mock.patch.object(shutdown.time, "sleep"):
            result = shutdown.stop_local_servers({"omlx": "/opt/test/omlx"}, Path("/private/tmp/app"), grace=0)
        self.kill.assert_not_called()
        self.assertEqual(result["processesStopped"], 0)
        self.assertIn("changed its title", result["errors"][0])

    def test_private_agent_receipt_allows_safe_stop_despite_title_changes(self):
        original = process(command="omp initial title")
        renamed = process(command="omp working on task")
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory)
            receipt = runs / "run/attachments/agent/agent-process.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_text(json.dumps({"pid": original.pid, "started": original.started, "client": "omp"}))
            receipt.chmod(0o600)
            with mock.patch.object(shutdown, "process_snapshot", side_effect=[{300: original}, {300: renamed}, {}, {}]), \
                    mock.patch.object(shutdown.time, "sleep"):
                result = shutdown.stop_local_servers({}, Path("/private/tmp/app"), runs_dir=runs, grace=0)
        self.assertEqual(result, {"processesStopped": 1, "errors": []})
        self.kill.assert_called_once_with(300, signal.SIGTERM)

    def test_worker_starting_during_the_grace_window_is_found_and_stopped(self):
        current = {300: process()}
        clock = [0.0]

        def send(pid, sig):
            if pid == 300 and sig == signal.SIGTERM:
                current[301] = process(301, 300, "python late_worker.py")
            else:
                current.pop(pid, None)

        self.kill.side_effect = send
        with mock.patch.object(shutdown, "process_snapshot", side_effect=lambda: dict(current)), \
                mock.patch.object(shutdown.time, "monotonic", side_effect=lambda: clock[0]), \
                mock.patch.object(shutdown.time, "sleep", side_effect=lambda _delay: clock.__setitem__(0, clock[0] + 1)):
            result = shutdown.stop_local_servers({"omlx": "/opt/test/omlx"}, Path("/private/tmp/app"), grace=1)
        self.assertEqual(result, {"processesStopped": 2, "errors": []})
        self.assertIn(mock.call(301, signal.SIGTERM), self.kill.call_args_list)

    def test_positive_lmstudio_failure_is_reported_and_stop_is_still_attempted(self):
        with mock.patch.object(shutdown, "lmstudio_service_running", return_value=True), \
                mock.patch.object(shutdown.subprocess, "run", side_effect=[SimpleNamespace(returncode=2), SimpleNamespace(returncode=0)]) as run:
            errors = shutdown.stop_lmstudio("/opt/test/lms")
        self.assertEqual(len(errors), 1)
        self.assertIn("model unload", errors[0])
        self.assertEqual([call.args[0] for call in run.call_args_list],
                         [["/opt/test/lms", "unload", "--all"], ["/opt/test/lms", "server", "stop"]])

    def test_closed_lmstudio_is_never_woken_by_shutdown_or_status(self):
        import launcher
        with mock.patch.object(shutdown, "process_snapshot", return_value={}), \
                mock.patch.object(shutdown.subprocess, "run", side_effect=AssertionError("An idle LM Studio CLI was started")):
            self.assertEqual(shutdown.stop_lmstudio("/opt/test/lms"), [])
            self.assertEqual(launcher.lmstudio_server_status(), (False, 1234))

    def test_lmstudio_presence_requires_the_app_or_native_daemon(self):
        for command, expected in (
            ("/Applications/LM Studio.app/Contents/MacOS/LM Studio --run-as-service", True),
            ("/opt/local/llmster --port 1234", True),
            ("python unrelated.py LM Studio", False),
            ("/opt/local/llmster-backup", False),
        ):
            with self.subTest(command=command), mock.patch.object(shutdown, "process_snapshot", return_value={300:process(command=command)}):
                self.assertEqual(shutdown.lmstudio_service_running(), expected)


class MarkerTests(unittest.TestCase):
    def setUp(self):
        patcher=mock.patch.object(shutdown,"retitled_servers_for_quit",return_value={
            "_processReceipts":{},"_nativeReceipts":{},"errors":[]})
        patcher.start()
        self.addCleanup(patcher.stop)
    def test_persisted_marker_blocks_old_handoffs_but_allows_new_plans(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = root / "client-plan.json"
            plan.write_text("{}")
            old = plan.stat()
            self.assertFalse(shutdown.terminal_plan_cancelled(root, old))
            shutdown.mark_quit(root)
            marker = root / shutdown.QUIT_MARKER
            os.utime(marker, ns=(old.st_mtime_ns + 10, old.st_mtime_ns + 10))
            self.assertTrue(shutdown.terminal_plan_cancelled(root, old))
            os.utime(plan, ns=(old.st_mtime_ns + 20, old.st_mtime_ns + 20))
            self.assertFalse(shutdown.terminal_plan_cancelled(root, plan.stat()))
            self.assertEqual(marker.stat().st_mode & 0o777, 0o600)

    def test_marker_rejects_symlink_public_file_and_fifo(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.write_text("untouched")
            target.chmod(0o600)
            marker = root / shutdown.QUIT_MARKER
            marker.symlink_to(target)
            for operation in (lambda: shutdown.mark_quit(root), lambda: shutdown.terminal_plan_cancelled(root, target.stat())):
                with self.assertRaises(OSError):
                    operation()
            self.assertEqual(target.read_text(), "untouched")
            marker.unlink()
            marker.write_text("public")
            marker.chmod(0o644)
            with self.assertRaises(OSError):
                shutdown.mark_quit(root)
            self.assertEqual(marker.read_text(), "public")
            marker.unlink()
            os.mkfifo(marker, 0o600)
            with self.assertRaises(OSError):
                shutdown.terminal_plan_cancelled(root, target.stat())

    def test_quit_marker_is_written_before_cleanup_and_normal_exit_does_not_write_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            callback = mock.Mock()
            coordinator = shutdown.ShutdownCoordinator([callback], binaries={}, app_dir=root,
                                                       runs_dir=root, shutdown_server=mock.Mock())
            with mock.patch.object(shutdown.threading, "Thread"):
                coordinator.request(all_local=True)
                coordinator.request(all_local=True)
            self.assertTrue((root / shutdown.QUIT_MARKER).is_file())
            callback.assert_not_called()
            (root / shutdown.QUIT_MARKER).unlink()
            normal = shutdown.ShutdownCoordinator([callback], binaries={}, app_dir=root,
                                                  runs_dir=root, shutdown_server=mock.Mock())
            with mock.patch.object(shutdown.threading, "Thread"):
                normal.request()
            self.assertFalse((root / shutdown.QUIT_MARKER).exists())

    def test_failed_callback_does_not_prevent_other_cleanup_or_listener_shutdown(self):
        last, listener = mock.Mock(), mock.Mock()
        coordinator = shutdown.ShutdownCoordinator([mock.Mock(side_effect=RuntimeError), last],
                                                   binaries={}, app_dir=Path("/private/tmp/app"), shutdown_server=listener)
        with mock.patch.object(shutdown.time, "sleep"), \
                mock.patch.object(shutdown, "stop_engine_services", return_value={
                    "servicesStopped": 0, "processesStopped": 0, "errors": [], "_processReceipts": {}}), \
                mock.patch.object(shutdown, "stop_lmstudio", return_value=[]), \
                mock.patch.object(shutdown, "stop_local_servers", return_value={"processesStopped": 2, "errors": []}):
            coordinator._run(True)
        last.assert_called_once()
        listener.assert_called_once()
        self.assertTrue(coordinator.snapshot()["complete"])
        self.assertEqual(coordinator.snapshot()["processesStopped"], 2)
        self.assertTrue(coordinator.snapshot()["errors"])

    def test_plan_published_during_cancellation_is_invalidated_before_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory)
            plan = runs / "client-plan.json"

            def admitted_attachment():
                plan.write_text("{}")
                first = (runs / shutdown.QUIT_MARKER).stat().st_mtime_ns
                os.utime(plan, ns=(first + 1, first + 1))
                self.assertFalse(shutdown.terminal_plan_cancelled(runs, plan.stat()))

            def inventory(*_args, **_kwargs):
                self.assertTrue(shutdown.terminal_plan_cancelled(runs, plan.stat()))
                return {"processesStopped": 0, "errors": []}

            coordinator = shutdown.ShutdownCoordinator([admitted_attachment], binaries={}, app_dir=runs,
                                                       runs_dir=runs, shutdown_server=mock.Mock())
            with mock.patch.object(shutdown.threading, "Thread"):
                coordinator.request(all_local=True)
            os.utime(runs / shutdown.QUIT_MARKER, ns=(100, 100))
            with mock.patch.object(shutdown.time, "sleep"), \
                    mock.patch.object(shutdown, "stop_engine_services", return_value={
                        "servicesStopped": 0, "processesStopped": 0, "errors": [], "_processReceipts": {}}), \
                    mock.patch.object(shutdown, "stop_lmstudio", return_value=[]), \
                    mock.patch.object(shutdown, "stop_local_servers", side_effect=inventory):
                coordinator._run(True)
            self.assertEqual(coordinator.snapshot()["errors"], [])

    def test_verified_service_receipts_reach_final_sweep_without_public_exposure(self):
        target = process(301,command="omlx-server renamed")
        receipts = {301:target}
        coordinator = shutdown.ShutdownCoordinator([],binaries={},app_dir=Path("/private/tmp/app"),
                                                    shutdown_server=mock.Mock())
        with mock.patch.object(shutdown.time,"sleep"), \
                mock.patch.object(shutdown,"stop_engine_services",return_value={
                    "servicesStopped":1,"processesStopped":1,"errors":[],"_processReceipts":receipts}), \
                mock.patch.object(shutdown,"stop_lmstudio",return_value=[]), \
                mock.patch.object(shutdown,"stop_local_servers",return_value={"processesStopped":1,"errors":[]}) as sweep:
            coordinator._run(True)
        self.assertEqual(sweep.call_args.kwargs["verified_processes"],receipts)
        self.assertEqual(coordinator.snapshot()["processesStopped"],2)
        self.assertEqual(coordinator.snapshot()["servicesStopped"],1)
        self.assertNotIn("_processReceipts",coordinator.snapshot())


class RunnerTests(unittest.TestCase):
    def fixture(self, directory):
        home = Path(directory)
        runs = home / "Library/Application Support/LLM Launcher/runs"
        run = runs / "run"
        run.mkdir(parents=True, mode=0o700)
        runs.chmod(0o700)
        binary = home / "omp"
        binary.write_text("fixture only")
        binary.chmod(0o700)
        plan = run / "client-plan.json"
        plan.write_text(json.dumps({"argv": [str(binary)], "allowedExecutable": str(binary),
                                    "clientName": "omp", "cwd": str(home), "env": {}}))
        plan.chmod(0o600)
        return home, runs, plan

    def test_marker_before_runner_prevents_agent_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            home, runs, plan = self.fixture(directory)
            shutdown.mark_quit(runs)
            marker = runs / shutdown.QUIT_MARKER
            stamp = plan.stat().st_mtime_ns + 1
            os.utime(marker, ns=(stamp, stamp))
            with mock.patch.object(client_runner.Path, "home", return_value=home), \
                    mock.patch.object(client_runner.sys, "argv", ["client_runner.py", str(plan)]), \
                    mock.patch.object(client_runner.os, "execve") as execute, \
                    mock.patch.object(shutdown, "register_terminal_agent"):
                with self.assertRaises(SystemExit):
                    client_runner.main()
                execute.assert_not_called()

    def test_marker_during_receipt_registration_prevents_exec(self):
        with tempfile.TemporaryDirectory() as directory:
            home, runs, plan = self.fixture(directory)

            def register(*_args):
                shutdown.mark_quit(runs)
                stamp = plan.stat().st_mtime_ns + 1
                os.utime(runs / shutdown.QUIT_MARKER, ns=(stamp, stamp))

            with mock.patch.object(client_runner.Path, "home", return_value=home), \
                    mock.patch.object(client_runner.sys, "argv", ["client_runner.py", str(plan)]), \
                    mock.patch.object(client_runner.os, "chdir"), \
                    mock.patch.object(client_runner.os, "execve") as execute, \
                    mock.patch.object(shutdown, "register_terminal_agent", side_effect=register):
                with self.assertRaises(SystemExit):
                    client_runner.main()
                execute.assert_not_called()

    def test_new_plan_after_quit_and_unavailable_inspection_remain_usable(self):
        with tempfile.TemporaryDirectory() as directory:
            home, runs, plan = self.fixture(directory)
            shutdown.mark_quit(runs)
            stamp = (runs / shutdown.QUIT_MARKER).stat().st_mtime_ns + 1
            os.utime(plan, ns=(stamp, stamp))
            with mock.patch.object(client_runner.Path, "home", return_value=home), \
                    mock.patch.object(client_runner.sys, "argv", ["client_runner.py", str(plan)]), \
                    mock.patch.object(client_runner.os, "chdir"), \
                    mock.patch.object(client_runner.os, "execve") as execute, \
                    mock.patch.object(shutdown, "register_terminal_agent", side_effect=subprocess.TimeoutExpired("ps", 5)):
                client_runner.main()
                execute.assert_called_once()


if __name__ == "__main__":
    unittest.main()
