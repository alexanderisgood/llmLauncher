"""No-model safety proofs for the opt-in full Kolibri benchmark harness."""
from __future__ import annotations

from pathlib import Path
import threading
import types
import unittest
from unittest import mock

from bench import kolibri_model_ab as bench


class NativeBenchmarkSafetyTests(unittest.TestCase):
    def test_physical_guard_can_reject_an_optimistic_pressure_plan(self):
        plan = {"ready":True,"estimatedWorkingSetBytes":8_000_000_000,"osReserveBytes":5_000_000_000}
        with mock.patch.object(bench.kolibri_runtime,"current_resource",return_value={"headroomBytes":40_000_000_000}), \
             mock.patch.object(bench.kolibri_runtime,"memory_plan",return_value=plan), \
             mock.patch.object(bench,"reclaimable_bytes",return_value=12_000_000_000):
            guard = bench.memory_guard({})
        self.assertFalse(guard["ready"])
        self.assertEqual(guard["physicalRequiredHeadroomBytes"],13_000_000_000)
        self.assertEqual(guard["physicalReclaimableBytes"],12_000_000_000)

    def test_failed_fresh_guard_never_creates_an_engine(self):
        info,runtime = {"path":"/fixture/model"},{"python":"/fixture/python"}
        model = {"path":"/fixture/model","kolibri":info}
        safety = types.SimpleNamespace(sample=mock.Mock())
        guard = {"ready":False,"physicalReclaimableBytes":1}
        with mock.patch.object(bench.kolibri_runtime,"inspect_model",return_value=info), \
             mock.patch.object(bench.kolibri_runtime,"inspect_runtime",return_value=runtime), \
             mock.patch.object(bench,"memory_guard",return_value=guard), \
             mock.patch.object(bench.subprocess,"Popen") as launch:
            result = bench.run_arm(Path("/fixture/never-created"),model,runtime,True,safety)
        self.assertFalse(result["engineStarted"])
        self.assertIs(result["guard"],guard)
        launch.assert_not_called()

    def test_runtime_identity_change_blocks_before_allocating_or_connecting(self):
        info,runtime = {"path":"/fixture/model"},{"python":"/fixture/python","identity":"old"}
        model = {"path":"/fixture/model","kolibri":info}
        safety = types.SimpleNamespace(sample=mock.Mock())
        with mock.patch.object(bench.kolibri_runtime,"inspect_model",return_value=info), \
             mock.patch.object(bench.kolibri_runtime,"inspect_runtime",return_value={**runtime,"identity":"new"}), \
             mock.patch.object(bench.subprocess,"Popen") as launch:
            with self.assertRaisesRegex(RuntimeError,"identity changed"):
                bench.run_arm(Path("/fixture/never-created"),model,runtime,True,safety)
        launch.assert_not_called(); safety.sample.assert_not_called()

    def test_safety_failure_stops_only_owned_group_and_releases_active_reader(self):
        release = threading.Event()
        child = types.SimpleNamespace(poll=lambda:None)
        safety = types.SimpleNamespace(check=mock.Mock(side_effect=RuntimeError("protected reserve")))
        def blocked_request(*args,**kwargs):
            release.wait(5)
            return {}
        with mock.patch.object(bench,"stream_chat",side_effect=blocked_request), \
             mock.patch.object(bench,"stop_owned",side_effect=lambda process:release.set()) as stop:
            with self.assertRaisesRegex(RuntimeError,"protected reserve"):
                bench.guarded_request(object(),child,safety)
        stop.assert_called_once_with(child)
        self.assertTrue(release.is_set())


if __name__ == "__main__":
    unittest.main()
