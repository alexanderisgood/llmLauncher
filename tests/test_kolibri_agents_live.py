"""No-model physical admission checks for real-agent Kolibri verification."""
from __future__ import annotations

import unittest
from unittest import mock

from bench import kolibri_agents_live as bench


class AgentBenchmarkPhysicalTests(unittest.TestCase):
    def test_agent_guard_reserves_client_and_os_beyond_engine_working_set(self):
        plan = {"ready":True,"estimatedWorkingSetBytes":12_000_000_000,"osReserveBytes":5_000_000_000}
        with mock.patch.object(bench.kolibri_runtime,"current_resource",return_value={"headroomBytes":45_000_000_000}), \
             mock.patch.object(bench.kolibri_runtime,"memory_plan",return_value=plan), \
             mock.patch.object(bench.launcher,"physical_memory_bytes",return_value=48*1024**3), \
             mock.patch.object(bench.darwin_memory,"physical_reclaimable_state",return_value={
                 "physicalMemoryAvailable":True,"reclaimableBytes":18_000_000_000}):
            guard = bench.memory_guard({},bench.OPTIONS)
        self.assertFalse(guard["ready"])
        self.assertEqual(guard["physicalRequiredHeadroomBytes"],17_000_000_000+2*1024**3)

    def test_unknown_physical_capacity_blocks_even_with_ready_route(self):
        plan = {"ready":True,"estimatedWorkingSetBytes":8_000_000_000,"osReserveBytes":5_000_000_000}
        with mock.patch.object(bench.kolibri_runtime,"current_resource",return_value={}), \
             mock.patch.object(bench.kolibri_runtime,"memory_plan",return_value=plan), \
             mock.patch.object(bench.launcher,"physical_memory_bytes",return_value=48*1024**3), \
             mock.patch.object(bench.darwin_memory,"physical_reclaimable_state",return_value={"physicalMemoryAvailable":False}):
            self.assertFalse(bench.memory_guard({},bench.OPTIONS)["ready"])

    def test_live_monitor_tracks_actual_bytes_and_rejects_reserve_breach(self):
        safety = bench.PhysicalSafety()
        total = 48*1024**3
        with mock.patch.object(bench.Safety,"sample"), \
             mock.patch.object(bench.launcher,"physical_memory_bytes",return_value=total), \
             mock.patch.object(bench.darwin_memory,"physical_reclaimable_state",side_effect=[
                 {"physicalMemoryAvailable":True,"reclaimableBytes":20_000_000_000},
                 {"physicalMemoryAvailable":True,"reclaimableBytes":1_000_000_000}]):
            safety.sample()
            with self.assertRaisesRegex(RuntimeError,"protected macOS reserve"):
                safety.sample()
        self.assertEqual(safety.minimum_reclaimable,1_000_000_000)
        self.assertEqual(safety.protected_reserve,max(bench.launcher.SESSION_OS_RESERVE_MIN_BYTES,
                                                   round(total*bench.launcher.SESSION_OS_RESERVE_FRACTION)))

    def test_invalid_client_contract_blocks_before_model_inspection(self):
        argv = ["kolibri_agents_live.py","--model","/fixture/model","--python","/fixture/python",
                "--pi","/fixture/pi","--omp","/fixture/omp","--result","/fixture/report"]
        with mock.patch.object(bench.sys,"argv",argv), \
             mock.patch.object(bench.launcher,"build_sampling_contract",side_effect=ValueError("invalid sampling")), \
             mock.patch.object(bench.kolibri_runtime,"inspect_model") as inspect:
            with self.assertRaisesRegex(ValueError,"invalid sampling"):
                bench.main()
        inspect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
