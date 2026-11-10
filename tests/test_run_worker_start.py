"""A failed worker publication owns no engine, agent or lasting bearer files."""
from contextlib import ExitStack
from pathlib import Path
import copy
import tempfile
import threading
import unittest
from unittest import mock

import launcher


class RunWorkerStartTests(unittest.TestCase):
    def test_prepared_job_start_failures_release_publications_without_stopping_other_work(self):
        with tempfile.TemporaryDirectory(prefix="launcher-job-start-") as directory:
            root = Path(directory)
            run = mock.Mock()
            run.snapshot.return_value = {"phase": "idle"}
            run.plan = None
            run.lock = threading.RLock()
            run.lifecycle_lock = threading.RLock()
            run.cancel_event = threading.Event()
            run.attachments = {}
            run.state = {"phase": "idle"}
            for kind in ("route", "ane", "clone", "session-set"):
                with self.subTest(kind=kind):
                    plan = launcher.LaunchPlan("generated-job", "mtplx", "pi", {"name": "Generated model"},
                        directory, 8192, 1024, "off", 18789, "custom", {}, run_dir=root,
                        secrets={"clientApiKey": "generated-private-key"})
                    bearer = root / "session-proxy.json"
                    bearer.write_text("generated private configuration")
                    if kind == "route":
                        job = launcher.RouteCheckManager(run)
                        report = {"ready": True, "contractId": "generated-contract", "request": {}, "checks": [],
                                  "identity": {"id": "generated-identity", "runtimeVersion": "generated"}}
                        patches = [mock.patch.object(job.planner, "route_check_plan", return_value=report),
                                   mock.patch.object(launcher, "normalized_request", return_value=plan)]
                        payload = {"confirmation": "generated-contract"}
                    elif kind == "ane":
                        job = launcher.ANETunerManager(run)
                        patches = [mock.patch.object(launcher, "validated_ane_tuning_request", return_value=({}, plan, {"id": "generated-tuning"}))]
                        payload = {}
                    elif kind == "clone":
                        job = launcher.ANEFP16CloneManager(run)
                        reviewed = {"ready": True, "modelId": "generated-model", "planId": "generated-plan",
                                    "confirmation": "generated-clone", "expiresAtEpoch": 2_000_000_000,
                                    "contractId": "generated-contract"}
                        job.current_plan = copy.deepcopy(reviewed)
                        patches = [mock.patch.object(job.planner, "build_ane_fp16_clone_plan", return_value=({}, reviewed))]
                        payload = {"approved": True, "planId": reviewed["planId"], "confirmation": reviewed["confirmation"]}
                    else:
                        job = launcher.SessionSetRunner(run)
                        report = {"ready": True, "confirmation": "generated-set", "mode": "reuse", "ownerRunId": "resident-owner",
                                  "_record": {"id": "generated-set", "name": "Generated set"},
                                  "_restartSurfaceIds": ["generated-surface"], "_missingRequests": [], "surfaceCount": 1}
                        run.plan = copy.copy(plan)
                        run.plan.run_id = report["ownerRunId"]
                        run.state = {"phase": "running"}
                        patches = [mock.patch.object(job.planner, "build_session_set_open_plan", return_value=report)]
                        payload = {"confirmation": "generated-set"}
                    with ExitStack() as stack:
                        for patch in patches:
                            stack.enter_context(patch)
                        stack.enter_context(mock.patch.object(threading.Thread, "start", side_effect=RuntimeError("generated job-start failure")))
                        stack.enter_context(mock.patch.object(launcher.subprocess, "Popen", side_effect=AssertionError("No process may start")))
                        with self.assertRaisesRegex(RuntimeError, "generated job-start failure"):
                            job.start(payload, [])
                    self.assertEqual(job.state["phase"], "failed")
                    self.assertIsNone(job.thread)
                    self.assertFalse(job.is_active())
                    job.cancel()
                    self.assertEqual(job.state["phase"], "failed")
                    run.start.assert_not_called()
                    run.stop.assert_not_called()
                    if kind in {"route", "ane"}:
                        self.assertIsNone(job.active_plan)
                        self.assertFalse(bearer.exists())
                        self.assertEqual(plan.secrets, {})

    def test_stop_from_an_old_epoch_preserves_a_restart_of_the_same_plan(self):
        with tempfile.TemporaryDirectory(prefix="launcher-worker-epoch-") as directory:
            plan = launcher.LaunchPlan("generated-epoch", "mtplx", "pi", {"name": "Generated model"},
                directory, 8192, 1024, "off", 18789, "custom", {})
            manager = launcher.RunManager()
            def accept(_plan, _cancel):
                with manager.lock:
                    manager.state["phase"] = "running"
            with mock.patch.object(manager, "_worker", side_effect=accept), \
                    mock.patch.object(manager, "_stop_owned") as cleanup:
                manager.start(plan)
                manager.worker_thread.join(2)
                old_epoch = manager.cancel_event
                manager.stop(expected_plan=plan, expected_cancel_event=old_epoch)
                self.assertEqual(manager.state["phase"], "idle")
                manager.start(plan)
                manager.worker_thread.join(2)
                replacement_epoch = manager.cancel_event
                self.assertIsNot(replacement_epoch, old_epoch)
                cleanup.reset_mock()

                manager.stop(expected_plan=plan, expected_cancel_event=old_epoch)
                cleanup.assert_not_called()
                self.assertIs(manager.plan, plan)
                self.assertEqual(manager.state["phase"], "running")
                self.assertFalse(replacement_epoch.is_set())

                manager.stop(expected_plan=plan, expected_cancel_event=replacement_epoch)
                cleanup.assert_called_once_with(plan)
                self.assertEqual(manager.state["phase"], "idle")

    def test_failed_thread_start_releases_plan_and_bearers_and_stop_is_safe(self):
        with tempfile.TemporaryDirectory(prefix="launcher-worker-start-") as directory:
            root = Path(directory)
            plan = launcher.LaunchPlan("generated-run", "mtplx", "pi", {"name": "Generated model"},
                str(root), 8192, 1024, "off", 18789, "custom", {}, run_dir=root,
                secrets={"apiKey": "generated-key", "clientApiKey": "generated-client-key",
                         "proxyControlKey": "generated-control-key"})
            bearer = root / "session-proxy.json"
            bearer.write_text("generated private configuration")
            manager = launcher.RunManager()
            with mock.patch.object(threading.Thread, "start", side_effect=RuntimeError("generated start failure")), \
                    mock.patch.object(launcher.subprocess, "Popen", side_effect=AssertionError("No model may start")), \
                    mock.patch.object(manager, "_terminate_process", side_effect=AssertionError("No process may be signalled")):
                with self.assertRaisesRegex(RuntimeError, "generated start failure"):
                    manager.start(plan)
                self.assertEqual(manager.state["phase"], "failed")
                self.assertIsNone(manager.plan)
                self.assertIsNone(manager.worker_thread)
                self.assertIsNone(manager.started_at)
                self.assertEqual(manager.attachments, {})
                self.assertTrue(manager.cleanup_complete.is_set())
                self.assertEqual(plan.secrets, {})
                self.assertFalse(bearer.exists())
                manager.stop()
                self.assertEqual(manager.state["phase"], "idle")

            retried = threading.Event()
            def accept(_plan, _cancel):
                with manager.lock:
                    manager.state["phase"] = "running"
                retried.set()
            with mock.patch.object(manager, "_worker", side_effect=accept):
                manager.start(plan)
                self.assertTrue(retried.wait(2))
                manager.worker_thread.join(2)
            self.assertIs(manager.plan, plan)
            self.assertEqual(manager.state["phase"], "running")


if __name__ == "__main__":
    unittest.main()
