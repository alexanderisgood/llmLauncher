from __future__ import annotations

from copy import deepcopy
import ctypes
from types import SimpleNamespace
import unittest
from unittest import mock

import darwin_memory


def sample() -> dict:
    return {
        "pageSizeBytes": 16384, "free_count": 200, "speculative_count": 100,
        "purgeable_count": 300, "external_page_count": 400,
        "internal_page_count": 2000, "compressor_page_count": 500,
        "wire_count": 200,
        "swapins": 2**40, "swapouts": 2**40,
        "total_uncompressed_pages_in_compressor": 2**40,
    }


class NativeFunction:
    def __init__(self, operation):
        self.operation = operation
        self.calls = []
        self.argtypes = None
        self.restype = None

    def __call__(self, *arguments):
        self.calls.append(arguments)
        return self.operation(*arguments)


def fake_library(*, page_size=16384, count=38, statistics_result=0, page_size_result=0):
    def page_reader(host, pointer):
        ctypes.cast(pointer, ctypes.POINTER(ctypes.c_size_t)).contents.value = page_size
        return page_size_result

    def statistics_reader(host, flavor, pointer, count_pointer):
        requested = ctypes.cast(count_pointer, ctypes.POINTER(ctypes.c_uint32))
        if requested.contents.value != 38:
            raise AssertionError("REV1 must request the complete 38-word prefix")
        value = ctypes.cast(pointer, ctypes.POINTER(darwin_memory._DarwinVMStatistics64Rev1)).contents
        for name, number in sample().items():
            if hasattr(value, name):
                setattr(value, name, number)
        requested.contents.value = count
        return statistics_result

    return SimpleNamespace(
        mach_host_self=NativeFunction(lambda: 42),
        host_page_size=NativeFunction(page_reader),
        host_statistics64=NativeFunction(statistics_reader),
        mach_port_deallocate=NativeFunction(lambda task, host: 0),
    )


class DarwinMemoryTests(unittest.TestCase):
    def read_native(self, library):
        with mock.patch.object(darwin_memory.sys, "platform", "darwin"), mock.patch.object(darwin_memory.ctypes, "CDLL", return_value=library), mock.patch.object(darwin_memory, "_task_self", return_value=7):
            return darwin_memory.native_vm_statistics()

    def test_complete_rev1_abi_matches_sdk_and_bounds_the_foreign_write(self) -> None:
        self.assertTrue(darwin_memory._abi_ready())
        library = fake_library()
        result = self.read_native(library)
        self.assertIsNotNone(result)
        self.assertEqual(result["external_page_count"], 400)
        self.assertEqual(result["swapouts"], 2**40)
        self.assertEqual(library.host_statistics64.calls[0][:2], (42, 4))
        self.assertEqual(library.host_statistics64.argtypes[-1], ctypes.POINTER(ctypes.c_uint32))
        self.assertEqual(library.mach_port_deallocate.calls, [(7, 42)])

    def test_truncated_and_oversized_returned_native_counts_fail_closed(self) -> None:
        for returned_count in [0, 24, 37, 39, 2**32 - 1]:
            with self.subTest(count=returned_count):
                library = fake_library(count=returned_count)
                self.assertIsNone(self.read_native(library))
                self.assertEqual(library.mach_port_deallocate.calls, [(7, 42)])

    def test_native_failure_and_unknown_page_size_release_the_host_right(self) -> None:
        for options in [{"statistics_result": 5}, {"page_size_result": 5}, {"page_size": 0}, {"page_size": 8192}]:
            with self.subTest(options=options):
                library = fake_library(**options)
                self.assertIsNone(self.read_native(library))
                self.assertEqual(library.mach_port_deallocate.calls, [(7, 42)])

    def test_unsupported_platform_or_native_abi_performs_no_foreign_call(self) -> None:
        with mock.patch.object(darwin_memory.sys, "platform", "linux"), mock.patch.object(darwin_memory.ctypes, "CDLL") as loader:
            self.assertIsNone(darwin_memory.native_vm_statistics())
        loader.assert_not_called()
        with mock.patch.object(darwin_memory.sys, "platform", "darwin"), mock.patch.object(darwin_memory, "_abi_ready", return_value=False), mock.patch.object(darwin_memory.ctypes, "CDLL") as loader:
            self.assertIsNone(darwin_memory.native_vm_statistics())
        loader.assert_not_called()

    def test_reclaimable_capacity_counts_speculative_once_and_excludes_ordinary_anonymous_pages(self) -> None:
        value = darwin_memory.physical_reclaimable_state(16384 * 10_000, lambda: sample())
        self.assertTrue(value["physicalMemoryAvailable"])
        self.assertEqual(value["freeBytes"], 100 * 16384)
        self.assertEqual(value["fileBackedBytes"], 400 * 16384)
        self.assertEqual(value["purgeableBytes"], 300 * 16384)
        self.assertEqual(value["reclaimableBytes"], 800 * 16384)
        self.assertEqual(value["reclaimablePercent"], 8)
        self.assertEqual(value["reclaimableMemorySource"], "host_statistics64")
        self.assertEqual(value["anonymousBytes"], 2000 * 16384)
        self.assertEqual(value["compressedPhysicalBytes"], 500 * 16384)

    def test_reclaimable_capacity_does_not_convert_pressure_percentage_to_ram(self) -> None:
        ordinary = sample()
        excessive_pressure_projection = {**ordinary, "freePercent": 84, "active_count": 5000, "inactive_count": 3000}
        total = 16384 * 10_000
        self.assertEqual(
            darwin_memory.physical_reclaimable_state(total, lambda: ordinary),
            darwin_memory.physical_reclaimable_state(total, lambda: excessive_pressure_projection),
        )

    def test_every_capacity_observation_reads_the_current_counters(self) -> None:
        first = sample()
        second = {**first, "free_count": first["free_count"] + 100}
        reader = mock.Mock(side_effect=[first, second])
        before = darwin_memory.physical_reclaimable_state(16384 * 10_000, reader)
        after = darwin_memory.physical_reclaimable_state(16384 * 10_000, reader)
        self.assertEqual(reader.call_count, 2)
        self.assertEqual(after["reclaimableBytes"] - before["reclaimableBytes"], 100 * 16384)

    def test_unreadable_counter_never_falls_back_to_pressure_or_total_memory(self) -> None:
        for value in [None, {}, {"freePercent": 99}, {**sample(), "free_count": True}, {**sample(), "pageSizeBytes": 16384.0}]:
            with self.subTest(value=value):
                actual = darwin_memory.physical_reclaimable_state(16384 * 10_000, lambda: value)
                self.assertFalse(actual["physicalMemoryAvailable"])
                self.assertIsNone(actual["reclaimableBytes"])
                self.assertIsNone(actual["reclaimablePercent"])

    def test_impossible_counts_and_overlapping_speculative_accounting_fail_closed(self) -> None:
        changes = [
            {"free_count": 50}, {"external_page_count": 50},
            {"purgeable_count": -1}, {"internal_page_count": 10_001},
            {"free_count": 8000, "external_page_count": 3000},
        ]
        for change in changes:
            value = {**sample(), **change}
            with self.subTest(change=change):
                actual = darwin_memory.physical_reclaimable_state(16384 * 10_000, lambda: value)
                self.assertFalse(actual["physicalMemoryAvailable"])

    def test_4k_pages_zero_capacity_and_reader_errors_are_handled(self) -> None:
        value = deepcopy(sample())
        value["pageSizeBytes"] = 4096
        actual = darwin_memory.physical_reclaimable_state(4096 * 10_000, lambda: value)
        self.assertEqual(actual["reclaimableBytes"], 800 * 4096)
        zero = {**value, **{name: 0 for name in (
            "free_count", "speculative_count", "purgeable_count", "external_page_count",
            "internal_page_count", "compressor_page_count", "wire_count",
        )}}
        actual = darwin_memory.physical_reclaimable_state(4096 * 10_000, lambda: zero)
        self.assertTrue(actual["physicalMemoryAvailable"])
        self.assertEqual(actual["reclaimableBytes"], 0)
        self.assertFalse(darwin_memory.physical_reclaimable_state(0, lambda: zero)["physicalMemoryAvailable"])
        with mock.patch.object(darwin_memory, "native_vm_statistics", side_effect=OSError):
            self.assertFalse(darwin_memory.physical_reclaimable_state(4096, darwin_memory.native_vm_statistics)["physicalMemoryAvailable"])


if __name__ == "__main__":
    unittest.main()
