"""Complete runtime update lifecycle with private fake commands/artifacts."""
import copy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
import zipfile

import runtime_update_jobs as jobs


class RuntimeUpdateJobTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="runtime-update-domain-")
        self.root = Path(self.temporary.name)
        self.managed = self.root/"runtimes"
        self.updates = self.root/"updates"
        self.selected = "/generated/selected/bin/omlx"
        self.release = {"version":"0.7.0.dev2", "channel":"preview", "tag":"fixture-tag",
            "commit":"a"*40, "sha256":"b"*64, "url":"https://fixture.invalid/omlx.whl",
            "fileName":"omlx-fixture.whl", "directSources":[], "sizeLabel":"generated wheel"}
        self.target = self.managed/"omlx-0.7.0.dev2"
        self.plan = {"id":"c"*64, "action":"verify", "release":self.release,
            "confirmation":"fixture-confirmation", "canStart":True, "checks":[],
            "destination":{"path":str(self.target), "selected":False},
            "installer":{"python":{"path":sys.executable}, "dependencyPolicy":"fixture-only"}}
        self.writes = []
        def write(path, value):
            self.writes.append(copy.deepcopy(value))
            path.write_text(json.dumps(value))
        self.services = jobs.RuntimeUpdateServices(
            build_plan=lambda _channel:copy.deepcopy(self.plan), launcher_idle=lambda:True,
            benchmark_active=lambda:False, selected_binary=lambda:self.selected,
            exact_version=lambda a,b:a==b, managed_verification=lambda _path:{"verified":True},
            kernel_status=lambda _path:{"ready":True}, invalidate_kernel_cache=lambda:None,
            candidates=lambda:[{"id":"generated-candidate", "path":str(self.target/"bin/omlx")}],
            write_json=write, patch_inspect=lambda _path:(None,None,{"applied":True}),
            patch_apply=lambda _path:None)
        self.policy = jobs.RuntimeUpdatePolicy(60, 1, "provenance.json")
        self.paths = jobs.RuntimeUpdatePaths(lambda:self.managed, lambda:self.updates)
        self.manager = jobs.RuntimeUpdateManager(self.policy,self.paths,self.services)

    def tearDown(self):
        if self.manager.process is not None:
            self.manager._retire_process(self.manager.process)
        if self.manager.thread and self.manager.thread.is_alive():
            self.manager.cancel(); self.manager.thread.join(3)
        self.temporary.cleanup()

    def test_smoke_capture_drains_large_output_without_pipe_deadlock_and_is_bounded(self):
        code, text = self.manager._run_capture([
            sys.executable, "-c", "import sys;sys.stdout.write('x'*1500000+'END_SENTINEL');sys.stdout.flush()"],timeout=4)
        self.assertEqual(code,0)
        self.assertEqual(len(text.encode()),self.policy.capture_tail_bytes)
        self.assertTrue(text.endswith("END_SENTINEL"))
        self.assertIsNone(self.manager.process)

    def test_capture_timeout_and_cancel_retire_only_owned_process(self):
        with self.assertRaisesRegex(RuntimeError,"timed out"):
            self.manager._run_capture([sys.executable,"-c","import time;time.sleep(10)"],timeout=.15)
        self.assertIsNone(self.manager.process)
        errors=[]
        def capture():
            try:self.manager._run_capture([sys.executable,"-c","import time;time.sleep(10)"],timeout=10)
            except Exception as error:errors.append(error)
        self.manager.state["phase"]="smoke-testing"
        worker=threading.Thread(target=capture);self.manager.thread=worker;worker.start()
        deadline=time.monotonic()+3
        while self.manager.process is None and time.monotonic()<deadline:time.sleep(.01)
        process=self.manager.process;self.assertIsNotNone(process)
        self.manager.cancel();worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertIsInstance(errors[0],jobs.RuntimeUpdateCancelled)
        self.assertIsNotNone(process.poll())

    def test_capture_retires_stdout_holding_child_after_leader_exit(self):
        child_receipt = self.root / "stdout-child.pid"
        child_code = "import time;print('CHILD_READY',flush=True);time.sleep(30)"
        leader_code = (
            "import subprocess,sys,time;"
            "from pathlib import Path;"
            f"p=subprocess.Popen([sys.executable,'-c',{child_code!r}]);"
            f"Path({str(child_receipt)!r}).write_text(str(p.pid));"
            "time.sleep(.15);print('LEADER_DONE',flush=True)"
        )
        started = time.monotonic()
        code, output = self.manager._run_capture([sys.executable, "-c", leader_code], timeout=4)
        self.assertEqual(code, 0)
        self.assertIn("CHILD_READY", output)
        self.assertIn("LEADER_DONE", output)
        self.assertLess(time.monotonic() - started, 4)
        self.assertIsNone(self.manager.process)
        child_pid = int(child_receipt.read_text())
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(.02)
        else:
            self.fail("The generated smoke-test child survived group retirement")

    def test_cancel_before_process_publication_closes_spawned_group(self):
        process=subprocess.Popen([sys.executable,"-c","import time;time.sleep(10)"],start_new_session=True)
        try:
            self.manager.cancel_event.set()
            with self.assertRaises(jobs.RuntimeUpdateCancelled):self.manager._publish_process(process)
            self.assertIsNotNone(process.poll())
            self.assertIsNone(self.manager.process)
        finally:
            if process.poll() is None:process.kill()
            process.wait()

    def test_output_reader_start_failure_retires_the_spawned_command(self):
        spawned = []
        actual_popen = subprocess.Popen
        def spawn(*args, **kwargs):
            process = actual_popen(*args, **kwargs)
            spawned.append(process)
            return process
        with mock.patch.object(jobs.subprocess, "Popen", side_effect=spawn), \
                mock.patch.object(threading.Thread, "start", side_effect=RuntimeError("generated reader-start failure")):
            with self.assertRaisesRegex(RuntimeError, "generated reader-start failure"):
                self.manager._run_capture([sys.executable, "-c", "import time;time.sleep(30)"])
        self.assertEqual(len(spawned), 1)
        self.assertIsNotNone(spawned[0].poll())
        self.assertTrue(spawned[0].stdout.closed)
        self.assertIsNone(self.manager.process)

    def test_inspection_finishing_after_job_begins_cannot_replace_reviewed_plan(self):
        entered,release=threading.Event(),threading.Event();errors=[]
        def build(_channel):entered.set();release.wait(3);return copy.deepcopy(self.plan)
        self.manager.services=replace(self.services,build_plan=build)
        def inspect():
            try:self.manager.inspect({"channel":"preview"})
            except Exception as error:errors.append(error)
        worker=threading.Thread(target=inspect);worker.start()
        try:
            self.assertTrue(entered.wait(2));self.manager.state["phase"]="queued"
            release.set();worker.join(3)
            self.assertIsInstance(errors[0],ValueError)
            self.assertFalse(self.manager.plans)
        finally:release.set();worker.join(3);self.manager.state["phase"]="idle"

    def test_worker_start_failure_is_terminal_and_the_reviewed_operation_can_retry(self):
        self.manager.inspect({"channel": "preview"})
        payload = {"planId": self.plan["id"], "reviewed": True,
                   "confirmation": self.plan["confirmation"]}
        with mock.patch.object(threading.Thread, "start", side_effect=RuntimeError("generated thread-start failure")):
            with self.assertRaisesRegex(RuntimeError, "generated thread-start failure"):
                self.manager.start(payload)
        self.assertEqual(self.manager.state["phase"], "failed")
        self.assertIsNone(self.manager.thread)
        self.assertFalse(self.manager.is_active())
        self.manager.cancel()
        self.assertEqual(self.manager.state["phase"], "failed")
        self.assertFalse(self.managed.exists())
        self.assertFalse(self.updates.exists())
        self.assertFalse(self.writes)

        finished = threading.Event()
        def complete(_plan):
            with self.manager.lock:
                self.manager.state["phase"] = "completed"
                self.manager.thread = None
            finished.set()
        with mock.patch.object(self.manager, "_worker", side_effect=complete):
            self.assertEqual(self.manager.start(payload)["id"], self.plan["id"])
            self.assertTrue(finished.wait(2))
        self.assertEqual(self.manager.state["phase"], "completed")
        self.assertFalse(self.manager.is_active())

    def prepare_verification(self):
        self.target.mkdir(parents=True)
        self.manager.state["plan"]=copy.deepcopy(self.plan)
        self.manager.state["phase"]="queued"
        self.manager._smoke_runtime=mock.Mock(return_value={"version":"fixture", "modelLoaded":False})
        self.manager._dependency_inventory=mock.Mock(return_value=[])

    def test_cancel_during_smoke_cannot_commit_trusted_manifest(self):
        self.prepare_verification()
        def smoke(*_args):self.manager.cancel();return {"version":"fixture"}
        self.manager._smoke_runtime=mock.Mock(side_effect=smoke)
        self.manager._worker(copy.deepcopy(self.plan))
        self.assertEqual(self.manager.state["phase"],"cancelled")
        self.assertFalse(self.writes)
        self.assertFalse((self.target/self.policy.manifest_name).exists())
        self.assertEqual(self.selected,"/generated/selected/bin/omlx")

    def test_success_commit_cannot_be_reopened_by_late_cancel(self):
        self.prepare_verification()
        original=self.manager._event
        def event(message,level="info"):
            original(message,level)
            if "successfully" in message:self.manager.cancel()
        self.manager._event=event
        self.manager._worker(copy.deepcopy(self.plan))
        self.assertEqual(self.manager.state["phase"],"completed")
        self.assertEqual(len(self.writes),1)
        self.assertTrue(self.manager.state["result"]["verified"])
        self.assertFalse(self.manager.state["result"]["selectionChanged"])

    def test_cancelled_worker_creates_no_staging_or_log_directories(self):
        self.manager.cancel_event.set()
        self.manager._worker(copy.deepcopy(self.plan))
        self.assertEqual(self.manager.state["phase"],"cancelled")
        self.assertFalse(self.managed.exists())
        self.assertFalse(self.updates.exists())

    def test_failed_final_path_smoke_removes_only_new_unselected_copy(self):
        plan=copy.deepcopy(self.plan);plan["action"]="install"
        artifact=self.root/"fixture.whl";artifact.write_bytes(b"generated fixture")
        self.manager.state["plan"]=copy.deepcopy(plan)
        self.manager._download=mock.Mock(return_value=artifact)
        self.manager._audit_official_wheel=mock.Mock(return_value={"baseDirectSourcesMatched":True})
        def create_environment(argv,*_args):
            if argv[1:3]==["-m","venv"]:
                bin_dir=Path(argv[3])/"bin";bin_dir.mkdir(parents=True)
                for name in ("python","omlx","pip"):
                    (bin_dir/name).write_text("generated command")
        self.manager._run_logged=mock.Mock(side_effect=create_environment)
        self.manager._wheelhouse_inventory=mock.Mock(return_value=([{"sha256":"fixture"}],[artifact]))
        self.manager._rebase_staged_environment=mock.Mock(return_value=["omlx","pip"])
        self.manager._smoke_runtime=mock.Mock(side_effect=[{"version":"fixture"},RuntimeError("Final-path check rejected")])
        self.manager._worker(plan)
        self.assertEqual(self.manager.state["phase"],"failed")
        self.assertIn("Final-path",self.manager.state["message"])
        self.assertFalse(self.target.exists())
        self.assertFalse(self.writes)
        self.assertEqual(self.selected,"/generated/selected/bin/omlx")
        self.assertFalse(list(self.managed.glob(".omlx-*.installing-*")))

    def test_staging_collision_preserves_the_preexisting_directory(self):
        plan = copy.deepcopy(self.plan)
        plan["action"] = "install"
        collision = self.managed / f".omlx-{self.release['version']}.installing-{'d' * 10}"
        collision.mkdir(parents=True)
        sentinel = collision / "preexisting.txt"
        sentinel.write_text("unowned staged data")
        artifact = self.root / "fixture.whl"
        artifact.write_bytes(b"generated fixture")
        self.manager._download = mock.Mock(return_value=artifact)
        self.manager._audit_official_wheel = mock.Mock(return_value={})
        self.manager._run_logged = mock.Mock(side_effect=AssertionError("Collision must reject before installation"))
        with mock.patch.object(jobs.uuid, "uuid4", return_value=mock.Mock(hex="d" * 32)):
            self.manager._worker(plan)
        self.assertEqual(self.manager.state["phase"], "failed")
        self.assertIn("collision", self.manager.state["message"])
        self.assertEqual(sentinel.read_text(), "unowned staged data")
        self.assertFalse(self.target.exists())
        self.assertFalse(self.writes)

    def test_legacy_snapshot_manifest_audit_and_environment_are_equal(self):
        text=Path(__file__).with_name("fixtures").joinpath("runtime_update_legacy.py").read_text()
        digest=Path(__file__).with_name("fixtures").joinpath("runtime_update_legacy.json")
        self.assertEqual(hashlib.sha256(text[:-1].encode()).hexdigest(),
            json.loads(digest.read_text())["sourceSha256"])
        namespace={"RunManager":object,"BenchmarkManager":object,"Any":object,"Path":Path,
            "copy":copy,"json":json,"threading":threading,"time":time,"datetime":datetime,"timezone":timezone,
            "subprocess":subprocess,"secrets":secrets,"re":__import__("re"),"os":os,"hashlib":hashlib,"zipfile":zipfile,
            "RUNTIME_UPDATE_SCHEMA_VERSION":self.policy.schema_version,"BINARIES":{"omlx":self.selected}}
        exec(compile("from __future__ import annotations\n"+text,"legacy-runtime-update","exec"),namespace)
        legacy=namespace["RuntimeUpdateManager"](mock.Mock(),mock.Mock())
        self.assertEqual(legacy.snapshot(),self.manager.snapshot())
        a=legacy._manifest(self.plan,{"modelLoaded":False},[],source_audit={},dependency_artifacts=[])
        b=self.manager._manifest(self.plan,{"modelLoaded":False},[],source_audit={},dependency_artifacts=[])
        a.pop("installedAt");b.pop("installedAt");self.assertEqual(a,b)
        self.assertEqual(legacy._pip_environment(),self.manager._pip_environment())
        artifact=self.root/"fixture.whl"
        with zipfile.ZipFile(artifact,"w") as archive:
            archive.writestr("omlx-0.7.0.dev2.dist-info/METADATA","Metadata-Version: 2.4\nName: omlx\nVersion: 0.7.0.dev2\n")
        self.assertEqual(legacy._audit_official_wheel(artifact,self.release),self.manager._audit_official_wheel(artifact,self.release))


if __name__=="__main__":unittest.main()
