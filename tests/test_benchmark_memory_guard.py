"""Core-engine calibration protects whole-Mac memory, even without a child PID."""
import copy
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

import launcher


class BenchmarkMemoryGuardTests(unittest.TestCase):
    HEALTHY = {"memoryAvailable":True, "totalBytes":48 * 1024**3, "freePercent":60.0}
    LOW = {**HEALTHY, "freePercent":8.0}

    def exercise(self, backend, mode, samples, stage, process_state):
        run = mock.Mock(plan=None, process=None, llamacpp_safety_violation=None,
                        codex_proxy_port=None, session_proxy_port=None)
        if process_state != "absent":
            run.process = mock.Mock(pid=12345)
            run.process.poll.return_value = None if process_state == "running" else 0
        plan = SimpleNamespace(backend=backend, port=1234, client_port=1235)
        run.start.side_effect = lambda p: setattr(run, "plan", p)
        manager = launcher.BenchmarkManager(run)
        manager.state = {"phase":"queued", "job":{}, "modes":{}, "result":None, "events":[]}
        job = {"backend":backend, "suiteName":"quick", "modes":["ar",mode] if mode != "ar" else ["ar"]}
        callback = None
        sampler = mock.Mock(violation=None)
        sampler.stop.return_value = {}

        def telemetry(**kwargs):
            nonlocal callback
            callback = kwargs["invariant_callback"]
            return sampler

        def emit():
            for sample in samples:
                callback(copy.deepcopy(sample))

        def loading(_plan):
            if stage == "loading":
                emit()
            else:
                callback(self.HEALTHY)

        with (
            mock.patch.object(manager, "_mode_payload", return_value={}),
            mock.patch.object(launcher, "normalized_request", return_value=plan),
            mock.patch.object(launcher, "require_live_model_load_admission", return_value={}),
            mock.patch.object(launcher, "BenchmarkTelemetrySampler", side_effect=telemetry),
            mock.patch.object(manager, "_wait_for_engine", side_effect=loading),
            mock.patch.object(launcher.threading, "Thread") as stop_thread,
            mock.patch.object(launcher.os, "getpgid", return_value=12345),
            mock.patch.object(launcher, "benchmark_clean_unload_evidence", return_value={}),
            mock.patch.object(launcher, "run_benchmark_completion", side_effect=lambda *a, **kw: emit()) as completion,
            mock.patch.object(launcher, "save_benchmark_record") as save,
        ):
            with self.assertRaises(launcher.QualificationSafetyFailure) as raised:
                manager._measure_mode(job, [], mode, 0, 6)
            stop_thread.assert_called_once_with(target=run.stop, kwargs={"expected_plan":plan}, daemon=True)
            run.stop.assert_called_once_with(expected_plan=plan)
            save.assert_not_called()
            self.assertEqual(completion.call_count, int(stage == "request"))
        self.assertIsNone(manager.state["result"])
        self.assertIsNone(manager.active_plan)
        return str(raised.exception)

    def test_every_core_mode_stops_on_low_or_unreadable_memory(self):
        for backend, modes in {"omlx":["ar","dflash2"], "lmstudio":["ar","mtp"], "mtplx":["ar","mtp"]}.items():
            for mode in modes:
                for stage in ("loading", "request"):
                    for process in ("absent", "running", "exited"):
                        for samples, reason in (([self.LOW,self.LOW], "protected macOS reserve"),
                                                ([{}, {}, {}], "unreadable")):
                            with self.subTest(backend=backend,mode=mode,stage=stage,process=process,reason=reason):
                                self.assertIn(reason, self.exercise(backend,mode,samples,stage,process))

    def test_transient_low_and_unavailable_readings_recover_before_real_violation(self):
        # No stop until the final consecutive pair, not the earlier isolated dip
        # or one missing observation. All samples run through the real worker.
        self.assertIn("protected macOS reserve", self.exercise("lmstudio", "mtp",
            [self.LOW,self.HEALTHY,{},self.HEALTHY,self.LOW,self.LOW], "loading", "absent"))

    def test_delayed_safety_stop_cannot_stop_a_replacement_run(self):
        manager = launcher.RunManager()
        old, current = object(), object()
        manager.plan = current
        manager.state["phase"] = "running"
        cancel = manager.cancel_event
        with mock.patch.object(manager, "_stop_owned") as cleanup:
            manager.stop(expected_plan=old)
        cleanup.assert_not_called()
        self.assertIs(manager.plan, current)
        self.assertEqual(manager.state["phase"], "running")
        self.assertFalse(cancel.is_set())


if __name__ == "__main__":
    unittest.main()
