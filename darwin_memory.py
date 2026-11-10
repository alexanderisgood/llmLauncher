"""Darwin physical-page capacity, separate from memorystatus pressure percent.

On macOS the memorystatus percentage includes active/inactive anonymous pages,
whose reuse can require compression or swap. It must not be multiplied by RAM
size to promise physical capacity for a new model. This helper reads public
Mach page counters without launching a process and retains no sample cache.

The exported free counter and the file-backed counter both include speculative
pages. Reclaimable capacity therefore uses free minus speculative, plus
file-backed and volatile purgeable pages. This is a physical reclaim estimate;
file-backed pages may still require writeback and all observations can change.

ABI references: Darwin mach/vm_statistics.h and mach/host_info.h REV1 layout;
Apple XNU osfmk/kern/host.c and osfmk/vm/vm_page.h.
"""
from __future__ import annotations

import ctypes
import math
import sys
from typing import Any, Callable


HOST_VM_INFO64 = 4
HOST_VM_INFO64_REV1_COUNT = 38
MEMORY_SEMANTICS_VERSION = 2
PHYSICAL_MEMORY_SOURCE = "host_statistics64"


class _DarwinVMStatistics64Rev1(ctypes.Structure):
    """Complete public REV1 prefix; an external-only prefix returns REV0."""
    _fields_ = [
        *[(name, ctypes.c_uint32) for name in (
            "free_count", "active_count", "inactive_count", "wire_count",
        )],
        *[(name, ctypes.c_uint64) for name in (
            "zero_fill_count", "reactivations", "pageins", "pageouts",
            "faults", "cow_faults", "lookups", "hits", "purges",
        )],
        ("purgeable_count", ctypes.c_uint32),
        ("speculative_count", ctypes.c_uint32),
        *[(name, ctypes.c_uint64) for name in (
            "decompressions", "compressions", "swapins", "swapouts",
        )],
        *[(name, ctypes.c_uint32) for name in (
            "compressor_page_count", "throttled_count",
            "external_page_count", "internal_page_count",
        )],
        ("total_uncompressed_pages_in_compressor", ctypes.c_uint64),
    ]


def _abi_ready() -> bool:
    """Fail before any foreign call if Python's native alignment differs."""
    return bool(
        ctypes.sizeof(ctypes.c_int32) == 4
        and ctypes.sizeof(ctypes.c_uint32) == 4
        and ctypes.sizeof(ctypes.c_size_t) == 8
        and ctypes.sizeof(_DarwinVMStatistics64Rev1) == 152
        and _DarwinVMStatistics64Rev1.purgeable_count.offset == 88
        and _DarwinVMStatistics64Rev1.speculative_count.offset == 92
        and _DarwinVMStatistics64Rev1.external_page_count.offset == 136
        and _DarwinVMStatistics64Rev1.internal_page_count.offset == 140
        and _DarwinVMStatistics64Rev1.total_uncompressed_pages_in_compressor.offset == 144
    )


def _task_self(libc: Any) -> int:
    return int(ctypes.c_uint32.in_dll(libc, "mach_task_self_").value)


def native_vm_statistics() -> dict[str, int] | None:
    """Read current REV1 counters, rejecting unavailable/truncated native data.

    Call the kernel on every observation. XNU may internally rate-limit Mach
    statistics to its short sampling window; this module adds no further TTL.
    Lifetime compression/swap counters are descriptive, not current free RAM.
    """
    if sys.platform != "darwin" or not _abi_ready():
        return None
    try:
        libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        host_self = libc.mach_host_self
        host_self.argtypes = []
        host_self.restype = ctypes.c_uint32
        page_size_reader = libc.host_page_size
        page_size_reader.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_size_t)]
        page_size_reader.restype = ctypes.c_int
        stats_reader = libc.host_statistics64
        stats_reader.argtypes = [
            ctypes.c_uint32, ctypes.c_int,
            ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_uint32),
        ]
        stats_reader.restype = ctypes.c_int
        release_port = libc.mach_port_deallocate
        release_port.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        release_port.restype = ctypes.c_int
        task = _task_self(libc)
        if not task:
            return None
        host = host_self()
        if not host:
            return None
        try:
            page_size = ctypes.c_size_t(0)
            if page_size_reader(host, ctypes.byref(page_size)) != 0:
                return None
            if page_size.value not in {4096, 16384}:
                return None
            count = ctypes.c_uint32(HOST_VM_INFO64_REV1_COUNT)
            value = _DarwinVMStatistics64Rev1()
            if stats_reader(
                host, HOST_VM_INFO64,
                ctypes.cast(ctypes.byref(value), ctypes.POINTER(ctypes.c_int32)),
                ctypes.byref(count),
            ) != 0 or count.value != HOST_VM_INFO64_REV1_COUNT:
                return None
            return {
                "pageSizeBytes": int(page_size.value),
                **{name: int(getattr(value, name)) for name, _type in value._fields_},
            }
        finally:
            # mach_host_self acquires a send right on every call. Release it
            # even when page-size/statistics validation failed.
            release_port(task, host)
    except (AttributeError, OSError, TypeError, ValueError, OverflowError, ctypes.ArgumentError):
        return None


def physical_reclaimable_state(
    total_memory_bytes: int,
    reader: Callable[[], dict[str, int] | None] = native_vm_statistics,
) -> dict[str, Any]:
    """Expose bounded physical capacity without interpreting pressure as bytes."""
    unavailable = {
        "memorySemanticsVersion": MEMORY_SEMANTICS_VERSION,
        "physicalMemoryAvailable": False,
        "reclaimableBytes": None, "reclaimablePercent": None,
        "reclaimableMemorySource": None,
    }
    if (
        isinstance(total_memory_bytes, bool) or not isinstance(total_memory_bytes, int)
        or total_memory_bytes <= 0
    ):
        return unavailable
    try:
        sample = reader()
    except (OSError, TypeError, ValueError, OverflowError):
        return unavailable
    if not isinstance(sample, dict):
        return unavailable
    names = (
        "free_count", "speculative_count", "purgeable_count",
        "external_page_count", "internal_page_count",
        "compressor_page_count", "wire_count",
    )
    page_size = sample.get("pageSizeBytes")
    if not isinstance(page_size, int) or isinstance(page_size, bool) or page_size not in {4096, 16384}:
        return unavailable
    total_pages = total_memory_bytes // page_size
    if any(
        not isinstance(sample.get(name), int) or isinstance(sample.get(name), bool)
        or not 0 <= sample[name] <= total_pages
        for name in names
    ):
        return unavailable
    # speculative pages are already included in both exported counters.
    free = sample["free_count"] - sample["speculative_count"]
    if free < 0 or sample["speculative_count"] > sample["external_page_count"]:
        return unavailable
    reclaimable = (free + sample["purgeable_count"] + sample["external_page_count"]) * page_size
    if not 0 <= reclaimable <= total_memory_bytes:
        return unavailable
    return {
        "memorySemanticsVersion": MEMORY_SEMANTICS_VERSION,
        "physicalMemoryAvailable": True,
        "reclaimableBytes": reclaimable,
        "reclaimablePercent": round(reclaimable * 100 / total_memory_bytes, 3),
        "reclaimableMemorySource": PHYSICAL_MEMORY_SOURCE,
        "pageSizeBytes": page_size,
        "freeBytes": free * page_size,
        "purgeableBytes": sample["purgeable_count"] * page_size,
        "fileBackedBytes": sample["external_page_count"] * page_size,
        "speculativeBytes": sample["speculative_count"] * page_size,
        "anonymousBytes": sample["internal_page_count"] * page_size,
        "compressedPhysicalBytes": sample["compressor_page_count"] * page_size,
        "wiredBytes": sample["wire_count"] * page_size,
    }


def snapshot_reclaimable_bytes(snapshot: dict[str, Any]) -> int | None:
    """Validate physical capacity explicitly; pressure-only snapshots cannot pass."""
    total = snapshot.get("totalBytes")
    value = snapshot.get("reclaimableBytes")
    if (
        snapshot.get("memorySemanticsVersion") != MEMORY_SEMANTICS_VERSION
        or snapshot.get("physicalMemoryAvailable") is not True
        or snapshot.get("reclaimableMemorySource") != PHYSICAL_MEMORY_SOURCE
        or not isinstance(total, int) or isinstance(total, bool) or total <= 0
        or not isinstance(value, int) or isinstance(value, bool)
        or not 0 <= value <= total
    ):
        return None
    return value


def telemetry_capacity_metrics(telemetry: dict[str, Any]) -> dict[str, Any] | None:
    """Read a versioned physical-capacity summary; legacy pressure is descriptive."""
    if (
        telemetry.get("version") != 2
        or telemetry.get("memorySemanticsVersion") != MEMORY_SEMANTICS_VERSION
        or telemetry.get("memoryAvailable") is not True
        or telemetry.get("memorySource") != PHYSICAL_MEMORY_SOURCE
    ):
        return None
    total = telemetry.get("totalMemoryBytes")
    baseline = telemetry.get("baselineHeadroomBytes")
    minimum = telemetry.get("minimumHeadroomBytes")
    delta = telemetry.get("peakReclaimableDeltaBytes")
    if (
        not isinstance(total, int) or isinstance(total, bool) or total <= 0
        or any(not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= total
               for value in (baseline, minimum, delta))
        or delta != max(0, baseline - minimum)
    ):
        return None
    reported_baseline = telemetry.get("baselineHeadroomPercent")
    reported_minimum = telemetry.get("minimumHeadroomPercent")
    if any(
        not isinstance(value, (int, float)) or isinstance(value, bool)
        or not math.isfinite(float(value)) or not 0 <= float(value) <= 100
        for value in (reported_baseline, reported_minimum)
    ) or (
        abs(float(reported_baseline) - baseline * 100 / total) > .001
        or abs(float(reported_minimum) - minimum * 100 / total) > .001
    ):
        return None
    return {
        "totalBytes": total, "baselineBytes": baseline, "minimumBytes": minimum,
        "baselinePercent": baseline * 100 / total,
        "minimumPercent": minimum * 100 / total, "deltaBytes": delta,
        "memorySemanticsVersion": MEMORY_SEMANTICS_VERSION,
    }
