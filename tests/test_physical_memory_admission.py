from __future__ import annotations

from copy import deepcopy
import unittest
import itertools
from unittest import mock

import darwin_memory
import launcher
import resource_telemetry
from tests.memory_fixtures import physical_snapshot, physical_telemetry


GIB = 1024**3


def raw_sample(capacity_bytes=18 * GIB, pressure=84):
    return {
        "totalBytes": 48 * GIB, "memoryAvailable": True,
        "freePercent": pressure, "memorySource": "memorystatus_get_level",
        "memorySemanticsVersion": 2, "physicalMemoryAvailable": True,
        "reclaimableBytes": capacity_bytes, "reclaimableMemorySource": "host_statistics64",
        "thermalAvailable": True, "thermalState": 0, "lowPowerMode": False,
    }


def memory_summary():
    return physical_telemetry({
        "version": 1, "memoryAvailable": True, "totalMemoryBytes": 48 * GIB,
        "baselineHeadroomPercent": 50., "minimumHeadroomPercent": 25.,
        "peakPressureDeltaBytes": 12 * GIB,
        "thermalAvailable": True, "thermalStartValue": 0, "thermalWorstValue": 1,
    })


def record(telemetry):
    return {
        "comparisonContractVersion": launcher.BENCHMARK_COMPARISON_CONTRACT_VERSION,
        "qualityFingerprint": "a" * 64, "qualityCompletionTokens": 32,
        "winner": "ar", "backend": "omlx", "modelFingerprint": "b" * 64,
        "modes": {"ar": {
            "samples": [{"totalSeconds": 1.2, "ttftSeconds": .2,
                         "completionTokens": 64, "promptTokens": 128,
                         "decodeTokensPerSecond": 64., "decodeTimingValid": True,
                         "targetPromptTokens": 128, "repetition": 1}],
            "medianDecodeTokensPerSecond": 64., "resourceTelemetry": telemetry,
        }},
    }


class PhysicalMemoryAdmissionTests(unittest.TestCase):
    def test_owned_engine_live_reserve_uses_physical_bytes_not_healthy_pressure(self):
        for sample,minimum_reads in ((raw_sample(3*GIB,pressure=99),2),
                ({"totalBytes":48*GIB,"memoryAvailable":True,"freePercent":99},3)):
            with self.subTest(sample=sample):
                manager=launcher.RunManager()
                plan=mock.Mock(model={})
                process=mock.Mock(pid=4321)
                process.poll.side_effect=[None]*16+[0]
                cancel=mock.Mock()
                stopped=[False]
                cancel.is_set.side_effect=lambda:stopped[0]
                cancel.set.side_effect=lambda:stopped.__setitem__(0,True)
                cancel.wait.return_value=False
                manager.plan,manager.process=plan,process
                manager.state={"phase":"running","message":"Running","events":[]}
                with mock.patch.object(launcher.os,"getpgid",return_value=4321), \
                        mock.patch.object(launcher,"darwin_process_group_physical_footprint",return_value={
                            "processGroupFootprintAvailable":True,"processGroupMemberCount":1,
                            "processGroupPhysicalFootprintBytes":6*GIB,
                            "processGroupLifetimePeakPhysicalFootprintBytes":6*GIB}), \
                        mock.patch.object(launcher,"apple_memory_pressure_state",return_value=sample) as read, \
                        mock.patch.object(launcher.time,"monotonic",side_effect=itertools.count()), \
                        mock.patch.object(manager,"_terminate_process") as terminate, \
                        mock.patch.object(manager,"_stop_owned") as cleanup:
                    manager._guard_owned_memory(plan,process,cancel,"Kolibri",12*GIB)
                self.assertTrue(stopped[0])
                self.assertGreaterEqual(read.call_count,minimum_reads)
                terminate.assert_called_once()
                cleanup.assert_called_once_with(plan)
                self.assertIn("physical memory",manager.state["message"])

    def test_public_capacity_uses_native_bytes_and_keeps_pressure_separate(self) -> None:
        public = launcher.public_session_resource(raw_sample())
        self.assertTrue(public["memoryAvailable"])
        self.assertEqual(public["headroomBytes"], 18 * GIB)
        self.assertEqual(public["headroomPercent"], 37.5)
        self.assertEqual(public["memorySource"], "host_statistics64")
        self.assertEqual(public["pressureFreePercent"], 84)
        self.assertEqual(public["pressureSource"], "memorystatus_get_level")
        self.assertEqual(public["memorySemanticsVersion"], 2)

    def test_pressure_only_or_unavailable_physical_sample_cannot_approve_capacity(self) -> None:
        for sample in [
            {"totalBytes": 48 * GIB, "memoryAvailable": True, "freePercent": 99},
            {**raw_sample(), "physicalMemoryAvailable": False},
            {**raw_sample(), "memorySemanticsVersion": 1},
            {**raw_sample(), "reclaimableBytes": True},
            {**raw_sample(), "reclaimableMemorySource": "memory_pressure -Q"},
        ]:
            with self.subTest(sample=sample):
                public = launcher.public_session_resource(sample)
                self.assertFalse(public["memoryAvailable"])
                self.assertIsNone(public["headroomBytes"])
                self.assertIsNone(public["headroomPercent"])

    def test_pressure_cannot_mask_low_physical_os_reserve(self) -> None:
        counters = {}
        low = raw_sample(3 * GIB, pressure=99)
        self.assertIsNone(launcher.benchmark_system_memory_violation(low, counters, "test"))
        self.assertIn("protected macOS reserve", launcher.benchmark_system_memory_violation(low, counters, "test"))
        counters.clear()
        sufficient = raw_sample(8 * GIB, pressure=1)
        self.assertIsNone(launcher.benchmark_system_memory_violation(sufficient, counters, "test"))
        self.assertIsNone(launcher.benchmark_system_memory_violation(sufficient, counters, "test"))

    def test_resource_cooldown_uses_exact_physical_bytes_and_rejects_legacy_semantics(self) -> None:
        before = launcher.benchmark_resource_condition(raw_sample())
        after = launcher.benchmark_resource_condition(raw_sample(18 * GIB + 1, pressure=99))
        comparison = launcher.compare_benchmark_resource_condition(before, after)
        self.assertEqual(comparison["memoryDeltaBytes"], 1)
        legacy = {**before, "memorySemanticsVersion": 1, "memorySource": "memory_pressure -Q"}
        self.assertFalse(launcher.compare_benchmark_resource_condition(legacy, after)["memoryWithinTolerance"])

    def test_raw_telemetry_reads_physical_and_pressure_with_the_same_installed_total_once(self) -> None:
        total_reader = mock.Mock(return_value=48 * GIB)
        physical = mock.Mock(return_value={"memorySemanticsVersion": 2, "physicalMemoryAvailable": True,
                                           "reclaimableBytes": 18 * GIB,
                                           "reclaimableMemorySource": "host_statistics64"})
        with mock.patch.object(resource_telemetry, "native_memory_free_percent", return_value=84), mock.patch.object(resource_telemetry.darwin_memory, "physical_reclaimable_state", physical):
            snapshot = resource_telemetry.apple_memory_pressure_state(total_reader)
        total_reader.assert_called_once_with()
        physical.assert_called_once_with(48 * GIB)
        self.assertEqual(snapshot["freePercent"], 84)
        self.assertEqual(snapshot["reclaimableBytes"], 18 * GIB)

    def test_sampler_records_physical_minimum_and_pressure_as_distinct_signals(self) -> None:
        sampler = launcher.BenchmarkTelemetrySampler()
        sampler.samples = [raw_sample(18 * GIB, pressure=80)]
        with mock.patch.object(launcher, "apple_resource_snapshot", return_value=raw_sample(12 * GIB, pressure=79)):
            summary = sampler.stop()
        self.assertEqual(summary["version"], 2)
        self.assertEqual(summary["minimumHeadroomBytes"], 12 * GIB)
        self.assertEqual(summary["minimumHeadroomPercent"], 25)
        self.assertEqual(summary["peakReclaimableDeltaBytes"], 6 * GIB)
        self.assertEqual(summary["minimumPressureFreePercent"], 79)
        self.assertEqual(summary["peakPressureDeltaPercent"], 1)

    def test_legacy_speed_and_thermal_remain_readable_without_becoming_capacity_proof(self) -> None:
        telemetry = memory_summary()
        legacy = {**telemetry, "version": 1, "memorySemanticsVersion": 1, "memorySource": "memory_pressure -Q"}
        measurement = launcher.cross_engine_benchmark_measurement(record(legacy))
        self.assertEqual(measurement["decodeTokensPerSecond"], 64)
        self.assertEqual(measurement["thermalWorstValue"], 1)
        self.assertIsNone(measurement["baselineHeadroomBytes"])
        self.assertIsNone(measurement["peakPressureDeltaBytes"])
        self.assertIsNone(darwin_memory.telemetry_capacity_metrics(legacy))

    def test_new_physical_summary_is_recognized_and_mixed_memory_comparison_fails(self) -> None:
        physical = launcher.cross_engine_benchmark_measurement(record(memory_summary()))
        self.assertEqual(physical["peakPressureDeltaBytes"], 12 * GIB)
        self.assertEqual(physical["baselineHeadroomBytes"], 24 * GIB)
        self.assertEqual(physical["memorySemanticsVersion"], 2)
        legacy_summary = {**memory_summary(), "version": 1, "memorySource": "memory_pressure -Q"}
        legacy = launcher.cross_engine_benchmark_measurement(record(legacy_summary))
        group = [{**physical, "backend": "omlx"}, {**legacy, "backend": "mtplx"}]
        decision = launcher.rank_cross_engine_profile(group, "memory")
        self.assertFalse(decision["available"])
        self.assertIn("mtplx", decision["missing"])
        self.assertTrue(launcher.rank_cross_engine_profile(group, "throughput")["available"])

    def test_inconsistent_or_unversioned_capacity_summary_fails_closed(self) -> None:
        valid = memory_summary()
        changes = [
            {"memorySemanticsVersion": None}, {"minimumHeadroomBytes": 49 * GIB},
            {"minimumHeadroomPercent": 84}, {"baselineHeadroomBytes": True},
            {"peakReclaimableDeltaBytes": 1},
        ]
        for change in changes:
            with self.subTest(change=change):
                self.assertIsNone(darwin_memory.telemetry_capacity_metrics({**valid, **change}))


if __name__ == "__main__":
    unittest.main()
