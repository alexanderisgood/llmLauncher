"""Synthetic LaunchAgent/PID proofs: never unload or signal a real service."""
from dataclasses import replace
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import launcher_shutdown
import service_shutdown as shutdown


class ServiceShutdownTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="launcher-service-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.agents = self.root / "LaunchAgents"; self.agents.mkdir(mode=0o755)
        self.binary = self.root / "bin/omlx"; self.binary.parent.mkdir()
        self.binary.write_text("synthetic executable; never run\n"); self.binary.chmod(0o755)
        self.label = "homebrew.mxcl.omlx"
        self.path = self.agents / (self.label + ".plist")
        self.config = {"Label": self.label, "ProgramArguments": [str(self.binary), "serve"], "KeepAlive": True}
        self.write_config()
        self.loaded_args = tuple(self.config["ProgramArguments"])
        self.loaded_program = self.loaded_args[0]
        self.loaded_path = self.path
        self.original = launcher_shutdown.LocalProcess(os.getuid(), 7182, 1,
            "Tue Oct 6 11:00:00 2026", "omlx-server")
        self.processes = {self.original.pid: self.original}
        self.job_pid = self.original.pid
        self.registered = True
        self.calls = []
        self.list_count = 0
        self.print_count = 0
        self.before_list = None
        self.before_print = None
        self.on_bootout = None
        self.bootout_code = 0
        self.kill = mock.patch.object(shutdown.os, "kill")
        self.kill_mock = self.kill.start(); self.addCleanup(self.kill.stop)

    def write_config(self):
        self.path.write_bytes(plistlib.dumps(self.config))
        self.path.chmod(0o644)

    def predicate(self, process):
        return launcher_shutdown.process_label(process, {"omlx": str(self.binary)}, self.root / "app")

    def snapshot(self):
        return dict(self.processes)

    def runner(self, argv, **_kwargs):
        self.calls.append(tuple(argv))
        if argv == ["/bin/launchctl", "list"]:
            self.list_count += 1
            if self.before_list:
                self.before_list(self.list_count)
            row = f"{self.job_pid if self.job_pid is not None else '-'}\t-9\t{self.label}\n" if self.registered else ""
            return SimpleNamespace(returncode=0, stdout="PID\tStatus\tLabel\n" + row, stderr="")
        target = f"gui/{os.getuid()}/{self.label}"
        if argv == ["/bin/launchctl", "print", target]:
            self.print_count += 1
            if self.before_print:
                self.before_print(self.print_count)
            if not self.registered:
                return SimpleNamespace(returncode=113, stdout="", stderr="not registered")
            args = "".join(f"\t\t{arg}\n" for arg in self.loaded_args)
            pid = f"\tpid = {self.job_pid}\n" if self.job_pid is not None else ""
            output = (f"{target} = {{\n\tactive count = 1\n\tpath = {self.loaded_path}\n"
                f"\ttype = LaunchAgent\n\tprogram = {self.loaded_program}\n\targuments = {{\n{args}\t}}\n"
                f"{pid}\tenvironment = {{\n\t\tpid = 999\n\t\tprogram = /unrelated\n\t}}\n"
                "\tresource = {\n\t\ttype = resource\n\t}\n}\n")
            return SimpleNamespace(returncode=0, stdout=output, stderr="")
        if argv == ["/bin/launchctl", "bootout", target]:
            if self.on_bootout:
                self.on_bootout()
            elif self.bootout_code == 0:
                self.registered = False
                self.processes.pop(self.original.pid, None)
            return SimpleNamespace(returncode=self.bootout_code, stdout="", stderr="synthetic error")
        self.fail(f"Unexpected service command: {argv}")

    def stop(self, **kwargs):
        result = shutdown.stop_engine_services(process_label=self.predicate, process_snapshot=self.snapshot,
            launch_agents=self.agents, timeout=0, runner=self.runner, **kwargs)
        self.kill_mock.assert_not_called()
        return result

    def bootouts(self):
        return [call for call in self.calls if len(call) > 1 and call[1] == "bootout"]

    def test_renamed_keepalive_engine_is_unloaded_by_exact_proven_job(self):
        self.assertIsNone(self.predicate(self.original), "The process title alone must not identify this engine")
        result = self.stop()
        self.assertEqual(self.bootouts(), [("/bin/launchctl", "bootout", f"gui/{os.getuid()}/{self.label}")])
        self.assertEqual(result["servicesStopped"], 1)
        self.assertEqual(result["processesStopped"], 1)
        self.assertEqual(result["errors"], [])
        self.assertFalse(self.registered)
        self.assertEqual(result["_processReceipts"], {self.original.pid: self.original})
        self.assertEqual(result["_survivingProcesses"], {})

    def test_inactive_registered_engine_is_also_unloaded(self):
        self.job_pid = None; self.processes.clear()
        result = self.stop()
        self.assertEqual(result["servicesStopped"], 1)
        self.assertEqual(result["processesStopped"], 0)
        self.assertEqual(result["errors"], [])

    def test_rapidmlx_exact_serve_service_is_recognized_without_label_matching(self):
        self.config["ProgramArguments"] = [str(self.binary), "serve", "/models/local"]
        self.write_config()
        self.loaded_args = tuple(self.config["ProgramArguments"])
        with mock.patch.object(self, "predicate", side_effect=lambda process:
                launcher_shutdown.process_label(process, {"rapidmlx":str(self.binary)}, self.root / "app")):
            result = self.stop()
        self.assertEqual(result["servicesStopped"], 1)
        self.assertEqual(self.bootouts(), [("/bin/launchctl", "bootout", f"gui/{os.getuid()}/{self.label}")])
        self.assertEqual(result["errors"], [])

    def test_modified_config_before_bootout_is_not_mutated(self):
        def replace_config(count):
            if count == 2:
                self.config["ProgramArguments"] = ["/usr/bin/python3", "unrelated.py"]
                self.write_config()
        self.before_list = replace_config
        result = self.stop()
        self.assertFalse(self.bootouts())
        self.assertTrue(any("configuration changed" in error for error in result["errors"]))
        self.assertEqual(result["_processReceipts"], {})

    def test_replaced_inode_with_identical_config_invalidates_receipt(self):
        def replace_inode(count):
            if count == 2:
                self.path.rename(self.path.with_suffix(".old"))
                self.write_config()
        self.before_list = replace_inode
        result = self.stop()
        self.assertFalse(self.bootouts())
        self.assertTrue(result["errors"])

    def test_loaded_job_with_different_program_is_not_stopped(self):
        self.loaded_program = "/usr/bin/python3"
        self.loaded_args = ("/usr/bin/python3", "unrelated.py")
        result = self.stop()
        self.assertFalse(self.bootouts())
        self.assertTrue(any("does not match" in error for error in result["errors"]))

    def test_loaded_job_with_different_source_path_is_not_stopped(self):
        self.loaded_path = self.agents / "other.plist"
        result = self.stop()
        self.assertFalse(self.bootouts())
        self.assertTrue(result["errors"])

    def test_loaded_config_change_at_final_validation_prevents_bootout(self):
        def alter_loaded(count):
            if count == 2:
                self.loaded_args = (str(self.binary), "--help")
        self.before_print = alter_loaded
        result = self.stop()
        self.assertFalse(self.bootouts())
        self.assertTrue(result["errors"])

    def test_pid_reuse_before_bootout_does_not_stop_new_process(self):
        def reuse_pid(count):
            if count == 2:
                self.processes[self.original.pid] = replace(self.original, started="Tue Oct 6 12:00:00 2026")
        self.before_list = reuse_pid
        result = self.stop()
        self.assertFalse(self.bootouts())
        self.assertEqual(result["_processReceipts"], {})
        self.assertTrue(any("process changed" in error for error in result["errors"]))

    def test_foreign_user_process_is_not_stopped(self):
        self.processes[self.original.pid] = replace(self.original, uid=os.getuid() + 1)
        result = self.stop()
        self.assertFalse(self.bootouts())
        self.assertEqual(result["servicesStopped"], 0)

    def test_arbitrary_shell_policy_is_not_an_engine_service(self):
        self.config["Program"] = "/bin/sh"
        self.config["ProgramArguments"] = [str(self.binary), "-c", str(self.binary) + " serve"]
        self.write_config()
        result = self.stop()
        self.assertFalse(self.bootouts())
        self.assertEqual(result["services"], [])

    def test_label_prefix_alone_does_not_stop_an_unrelated_job(self):
        self.config["ProgramArguments"] = ["/usr/bin/python3", "unrelated.py"]
        self.write_config()
        result = self.stop()
        self.assertFalse(self.bootouts())
        self.assertEqual(result["errors"], [])

    def test_readable_644_config_is_allowed_but_writable_or_symlink_config_is_not(self):
        for mode in (0o664, 0o666):
            with self.subTest(mode=mode):
                self.path.chmod(mode)
                result = self.stop()
                self.assertFalse(self.bootouts())
                self.assertEqual(result["services"], [])
        self.path.chmod(0o644)
        original = self.path.with_suffix(".original")
        self.path.rename(original); self.path.symlink_to(original)
        result = self.stop()
        self.assertFalse(self.bootouts())
        self.assertEqual(result["services"], [])

    def test_unsafe_label_and_oversized_file_are_never_service_targets(self):
        self.config["Label"] = "other/job"
        self.write_config()
        self.assertEqual(self.stop()["services"], [])
        self.path.write_bytes(b"x" * (shutdown.MAX_PLIST_BYTES + 1))
        self.assertEqual(self.stop()["services"], [])
        self.assertFalse(self.bootouts())

    def test_positive_bootout_exit_is_an_error_and_original_survivor_is_returned(self):
        self.bootout_code = 5
        result = self.stop()
        self.assertEqual(result["servicesStopped"], 0)
        self.assertEqual(result["processesStopped"], 0)
        self.assertTrue(any("exit 5" in error for error in result["errors"]))
        self.assertTrue(any("remains registered" in error for error in result["errors"]))
        self.assertEqual(result["_survivingProcesses"], {self.original.pid: self.original})

    def test_unregistered_job_with_surviving_original_process_is_honest(self):
        self.on_bootout = lambda: setattr(self, "registered", False)
        result = self.stop()
        self.assertEqual(result["servicesStopped"], 0)
        self.assertTrue(result["services"][0]["unregistered"])
        self.assertFalse(result["services"][0]["processStopped"])
        self.assertTrue(any("remains running" in error for error in result["errors"]))
        self.assertEqual(result["_survivingProcesses"], {self.original.pid: self.original})

    def test_pid_reuse_after_unload_counts_original_gone_without_trusting_replacement(self):
        def unload_and_reuse():
            self.registered = False
            self.processes[self.original.pid] = replace(self.original, started="Tue Oct 6 12:00:00 2026")
        self.on_bootout = unload_and_reuse
        result = self.stop()
        self.assertEqual(result["servicesStopped"], 1)
        self.assertEqual(result["processesStopped"], 1)
        self.assertEqual(result["_survivingProcesses"], {})
        self.assertEqual(result["errors"], [])

    def test_orphaned_workers_retain_birth_bound_receipts_for_final_sweep(self):
        worker = replace(self.original, pid=7183, parent=self.original.pid,
                         command="python3 multiprocessing_worker.py")
        unrelated = replace(worker, pid=7184, parent=1)
        self.processes.update({worker.pid: worker, unrelated.pid: unrelated})
        def remove_parent_only():
            self.registered = False
            self.processes.pop(self.original.pid)
            self.processes[worker.pid] = replace(worker, parent=1)
        self.on_bootout = remove_parent_only
        result = self.stop()
        self.assertEqual(result["servicesStopped"], 1)
        self.assertEqual(result["_processReceipts"], {self.original.pid: self.original, worker.pid: worker})
        self.assertEqual(result["_survivingProcesses"], {worker.pid: worker})
        self.assertEqual(result["services"][0]["descendantPids"], [worker.pid])
        self.assertNotIn(unrelated.pid, result["_processReceipts"])

    def test_unload_timeout_retains_receipt_for_safe_final_sweep(self):
        actual_runner = self.runner
        def timeout_bootout(argv, **kwargs):
            if argv[1] == "bootout":
                self.calls.append(tuple(argv))
                raise subprocess.TimeoutExpired(argv, 5)
            return actual_runner(argv, **kwargs)
        with mock.patch.object(self, "runner", side_effect=timeout_bootout):
            result = self.stop()
        self.assertTrue(result["errors"])
        self.assertEqual(result["_survivingProcesses"], {self.original.pid: self.original})

    def test_duplicate_launchagent_labels_fail_closed(self):
        second = self.agents / "duplicate.plist"
        second.write_bytes(self.path.read_bytes()); second.chmod(0o644)
        result = self.stop()
        self.assertFalse(self.bootouts())
        self.assertEqual(result["services"], [])

    def test_ambiguous_loaded_print_is_not_used_as_identity(self):
        actual_runner = self.runner
        def ambiguous(argv, **kwargs):
            result = actual_runner(argv, **kwargs)
            if argv[1] == "print":
                result.stdout = result.stdout.replace("\tprogram = ", "\tprogram = /unrelated\n\tprogram = ")
            return result
        with mock.patch.object(self, "runner", side_effect=ambiguous):
            result = self.stop()
        self.assertFalse(self.bootouts())
        self.assertTrue(result["errors"])


if __name__ == "__main__":
    unittest.main()
