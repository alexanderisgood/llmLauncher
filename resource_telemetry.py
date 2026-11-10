"""Native host resource readings, isolated from controller and model lifecycle.

Live pressure, thermal, wired-limit and process-footprint readings are never cached:
safety guards must see the kernel's current state. Installed memory can be queried
without creating a helper process through sysctlbyname.
"""
from __future__ import annotations

import ctypes
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable
import darwin_memory


def native_sysctl_bytes(name: bytes, maximum_bytes: int = 4096) -> bytes | None:
    """Read a bounded Darwin sysctl without starting a subprocess."""
    if sys.platform != "darwin":
        return None
    try:
        libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        call = libc.sysctlbyname
        call.argtypes = [
            ctypes.c_char_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
            ctypes.c_void_p, ctypes.c_size_t,
        ]
        call.restype = ctypes.c_int
        size = ctypes.c_size_t(0)
        if call(name, None, ctypes.byref(size), None, 0) != 0:
            return None
        if not 0 < size.value <= maximum_bytes:
            return None
        buffer = ctypes.create_string_buffer(size.value)
        if call(name, buffer, ctypes.byref(size), None, 0) != 0:
            return None
        if not 0 < size.value <= len(buffer):
            return None
        return buffer.raw[:size.value]
    except (AttributeError, OSError, TypeError, ValueError, OverflowError, ctypes.ArgumentError):
        return None


def native_sysctl_text(name: str) -> str | None:
    value = native_sysctl_bytes(name.encode("ascii"), 256)
    if value is None:
        return None
    if name == "hw.memsize":
        return str(int.from_bytes(value, sys.byteorder)) if len(value) in {4, 8} else None
    try:
        return value.rstrip(b"\0").decode("utf-8")[:200]
    except UnicodeError:
        return None


def physical_memory_bytes() -> int:
    """Return installed memory without treating a blocked sysctl as success."""
    native = native_sysctl_bytes(b"hw.memsize", 8)
    if native is not None and len(native) in {4, 8}:
        value = int.from_bytes(native, sys.byteorder)
        if value > 0:
            return value
    try:
        result = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "hw.memsize"], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=2, check=False,
        )
        value = int(result.stdout.strip())
        if result.returncode == 0 and value > 0:
            return value
    except (OSError, TypeError, ValueError, subprocess.TimeoutExpired):
        pass
    try:
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        pages = int(os.sysconf("SC_PHYS_PAGES"))
        return page_size * pages if page_size > 0 and pages > 0 else 0
    except (OSError, TypeError, ValueError):
        return 0


def apple_process_resource_state(thermal_labels: dict[int, str]) -> dict[str, Any]:
    """Read public NSProcessInfo thermal and low-power state without a helper process."""
    if sys.platform != "darwin":
        return {
            "thermalAvailable": False, "thermalState": None,
            "thermalLabel": "unavailable", "lowPowerMode": None,
        }
    try:
        ctypes.CDLL("/System/Library/Frameworks/Foundation.framework/Foundation")
        objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        message = objc.objc_msgSend
        message.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        message.restype = ctypes.c_void_p
        process_info = message(
            objc.objc_getClass(b"NSProcessInfo"),
            objc.sel_registerName(b"processInfo"),
        )
        if not process_info:
            raise RuntimeError("NSProcessInfo is unavailable.")
        message.restype = ctypes.c_long
        thermal = int(message(process_info, objc.sel_registerName(b"thermalState")))
        if thermal not in thermal_labels:
            raise RuntimeError("NSProcessInfo returned an unknown thermal state.")
        message.restype = ctypes.c_bool
        low_power = bool(message(
            process_info, objc.sel_registerName(b"isLowPowerModeEnabled"),
        ))
        return {
            "thermalAvailable": True, "thermalState": thermal,
            "thermalLabel": thermal_labels[thermal],
            "lowPowerMode": low_power,
        }
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return {
            "thermalAvailable": False, "thermalState": None,
            "thermalLabel": "unavailable", "lowPowerMode": None,
        }


def native_memory_free_percent() -> int | None:
    """Read the same kernel counter used by memory_pressure, without a helper.

    Apple's memorystatus_get_level copies the current memorystatus_level into
    a uint32_t. Read it every time; never cache memory-safety observations.
    """
    if sys.platform != "darwin":
        return None
    try:
        libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        call = libc.memorystatus_get_level
        call.argtypes = [ctypes.POINTER(ctypes.c_uint32)]
        call.restype = ctypes.c_int
        value = ctypes.c_uint32(0)
        if call(ctypes.byref(value)) != 0 or not 0 <= value.value <= 100:
            return None
        return int(value.value)
    except (AttributeError, OSError, TypeError, ValueError, OverflowError, ctypes.ArgumentError):
        return None


def apple_memory_pressure_state(
    memory_reader: Callable[[], int] = physical_memory_bytes,
) -> dict[str, Any]:
    """Read pressure and physical capacity as separate uncached observations."""
    installed_total = memory_reader()

    def observed(pressure: dict[str, Any]) -> dict[str, Any]:
        return {
            **pressure,
            **darwin_memory.physical_reclaimable_state(installed_total),
        }

    free_native = native_memory_free_percent()
    if isinstance(free_native, int) and not isinstance(free_native, bool) and 0 <= free_native <= 100:
        total = installed_total
        if isinstance(total, int) and not isinstance(total, bool) and total > 0:
            return observed({
                "memoryAvailable": True, "totalBytes": total,
                "freePercent": float(free_native),
                "memorySource": "memorystatus_get_level",
            })
    command = Path("/usr/bin/memory_pressure")
    if sys.platform != "darwin" or not command.is_file():
        return observed({
            "memoryAvailable": False, "totalBytes": installed_total,
            "freePercent": None,
        })
    try:
        result = subprocess.run(
            [str(command), "-Q"], text=True, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=2, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return observed({
            "memoryAvailable": False, "totalBytes": installed_total,
            "freePercent": None,
        })
    free_match = re.search(
        r"memory free percentage:\s*(\d+(?:\.\d+)?)%", result.stdout, re.IGNORECASE,
    )
    try:
        total = installed_total
        free = float(free_match.group(1)) if free_match else None
    except (TypeError, ValueError):
        total, free = installed_total, None
    ready = bool(
        result.returncode == 0 and total > 0 and free is not None
        and math.isfinite(free) and 0 <= free <= 100
    )
    return observed({
        "memoryAvailable": ready, "totalBytes": total,
        "freePercent": round(free, 3) if ready and free is not None else None,
        "memorySource": "memory_pressure -Q" if ready else None,
    })


def _apple_iogpu_wired_limit_mib_native() -> int | None:
    """Read the native signed sysctl value, or ``None`` when unavailable.

    ``iogpu.wired_limit_mb`` has appeared as both a 32-bit and a 64-bit native
    integer. Ask the kernel for the width first and accept only those two
    layouts. This avoids spawning ``sysctl`` in the quarter-second safety
    monitor, where process creation can time out while a very large model is
    faulting pages and falsely look like a changed limit.
    """
    try:
        libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        call = libc.sysctlbyname
        call.argtypes = [
            ctypes.c_char_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
            ctypes.c_void_p, ctypes.c_size_t,
        ]
        call.restype = ctypes.c_int
        native_size = ctypes.c_size_t(0)
        name = b"iogpu.wired_limit_mb"
        if call(name, None, ctypes.byref(native_size), None, 0) != 0:
            return None
        widths = {
            ctypes.sizeof(ctypes.c_int32): ctypes.c_int32,
            ctypes.sizeof(ctypes.c_int64): ctypes.c_int64,
        }
        value_type = widths.get(int(native_size.value))
        if value_type is None:
            return None
        expected_size = int(native_size.value)
        value = value_type()
        if call(name, ctypes.byref(value), ctypes.byref(native_size), None, 0) != 0:
            return None
        if int(native_size.value) != expected_size:
            return None
        return int(value.value)
    except (
        AttributeError, OSError, TypeError, ValueError, OverflowError,
        ctypes.ArgumentError,
    ):
        return None


def _apple_iogpu_wired_limit_mib_command() -> int | None:
    """Conservative compatibility fallback for an unavailable native call."""
    try:
        result = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "iogpu.wired_limit_mb"], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=2, check=False,
        )
        raw = result.stdout.strip()
        if result.returncode != 0 or re.fullmatch(r"[0-9]+", raw) is None:
            return None
        return int(raw)
    except (OSError, TypeError, ValueError, subprocess.TimeoutExpired):
        return None


def apple_iogpu_wired_limit_bytes(
    maximum_mib: int,
    native_reader: Callable[[], int | None] = _apple_iogpu_wired_limit_mib_native,
    command_reader: Callable[[], int | None] = _apple_iogpu_wired_limit_mib_command,
) -> int:
    """Return a bounded explicitly raised Apple GPU wired limit, or zero."""
    if sys.platform != "darwin":
        return 0
    value_mib = native_reader()
    if value_mib is None:
        value_mib = command_reader()
    if (
        isinstance(value_mib, bool) or not isinstance(value_mib, int)
        or not 0 < value_mib <= maximum_mib
    ):
        return 0
    return value_mib * 1024**2


class _DarwinRusageInfoV4(ctypes.Structure):
    """Public Darwin rusage_info_v4 layout through its lifetime footprint counters."""
    _fields_ = [
        ("ri_uuid", ctypes.c_uint8 * 16),
        *[(name, ctypes.c_uint64) for name in (
            "ri_user_time", "ri_system_time", "ri_pkg_idle_wkups",
            "ri_interrupt_wkups", "ri_pageins", "ri_wired_size",
            "ri_resident_size", "ri_phys_footprint", "ri_proc_start_abstime",
            "ri_proc_exit_abstime", "ri_child_user_time", "ri_child_system_time",
            "ri_child_pkg_idle_wkups", "ri_child_interrupt_wkups",
            "ri_child_pageins", "ri_child_elapsed_abstime", "ri_diskio_bytesread",
            "ri_diskio_byteswritten", "ri_cpu_time_qos_default",
            "ri_cpu_time_qos_maintenance", "ri_cpu_time_qos_background",
            "ri_cpu_time_qos_utility", "ri_cpu_time_qos_legacy",
            "ri_cpu_time_qos_user_initiated", "ri_cpu_time_qos_user_interactive",
            "ri_billed_system_time", "ri_serviced_system_time", "ri_logical_writes",
            "ri_lifetime_max_phys_footprint", "ri_instructions", "ri_cycles",
            "ri_billed_energy", "ri_serviced_energy",
            "ri_interval_max_phys_footprint", "ri_runnable_time", "ri_flags",
        )],
    ]


def darwin_process_physical_footprint(pid: int) -> dict[str, Any]:
    """Read an owned process's kernel-accounted footprint; never substitute RSS."""
    if sys.platform != "darwin" or isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return {
            "processFootprintAvailable": False, "processFootprintSource": None,
            "processPhysicalFootprintBytes": None,
            "processLifetimePeakPhysicalFootprintBytes": None,
        }
    try:
        libc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        call = libc.proc_pid_rusage
        call.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
        call.restype = ctypes.c_int
        value = _DarwinRusageInfoV4()
        if call(pid, 4, ctypes.byref(value)) != 0:
            raise OSError(ctypes.get_errno(), "proc_pid_rusage failed")
        current = int(value.ri_phys_footprint)
        lifetime = int(value.ri_lifetime_max_phys_footprint)
        if current <= 0 or lifetime <= 0:
            raise ValueError("Darwin returned invalid physical-footprint counters.")
        # Kernel current/peak counters can be observed between peak updates
        # during allocation. Current is itself a proven lower bound on peak;
        # taking the larger value preserves the ceiling without discarding a
        # valid sample. Failed calls and zero counters still fail closed.
        lifetime = max(current, lifetime)
        return {
            "processFootprintAvailable": True,
            "processFootprintSource": "proc_pid_rusage RUSAGE_INFO_V4",
            "processPhysicalFootprintBytes": current,
            "processLifetimePeakPhysicalFootprintBytes": lifetime,
        }
    except (AttributeError, OSError, TypeError, ValueError):
        return {
            "processFootprintAvailable": False, "processFootprintSource": None,
            "processPhysicalFootprintBytes": None,
            "processLifetimePeakPhysicalFootprintBytes": None,
        }


def darwin_all_process_ids() -> list[int] | None:
    """Enumerate Darwin processes through libproc without trusting parsed command output."""
    if sys.platform != "darwin":
        return None
    try:
        libc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        call = libc.proc_listallpids
        call.argtypes = [ctypes.c_void_p, ctypes.c_int]
        call.restype = ctypes.c_int
        capacity = max(64, int(call(None, 0)) + 64)
        for _attempt in range(3):
            buffer = (ctypes.c_int * capacity)()
            count = int(call(buffer, ctypes.sizeof(buffer)))
            if count < 0:
                raise OSError(ctypes.get_errno(), "proc_listallpids failed")
            if count < capacity:
                return sorted({int(buffer[index]) for index in range(count) if int(buffer[index]) > 0})
            capacity *= 2
    except (AttributeError, OSError, TypeError, ValueError):
        return None
    return None


def darwin_process_group_physical_footprint(
    pgid: int,
    enumerate_pids: Callable[[], list[int] | None] = darwin_all_process_ids,
    read_footprint: Callable[[int], dict[str, Any]] = darwin_process_physical_footprint,
) -> dict[str, Any]:
    """Sum kernel physical footprints for every live member of an owned process group."""
    if sys.platform != "darwin" or not isinstance(pgid, int) or isinstance(pgid, bool) or pgid <= 0:
        return {"processGroupFootprintAvailable": False, "processGroupMemberCount": 0}
    all_pids = enumerate_pids()
    if all_pids is None:
        return {"processGroupFootprintAvailable": False, "processGroupMemberCount": 0}
    pids: list[int] = []
    for pid in all_pids:
        try:
            if os.getpgid(pid) == pgid:
                pids.append(pid)
        except (OSError, ProcessLookupError):
            continue
    readings = [read_footprint(pid) for pid in pids]
    if not pids or any(item.get("processFootprintAvailable") is not True for item in readings):
        return {
            "processGroupFootprintAvailable": False,
            "processGroupMemberCount": len(pids),
        }
    return {
        "processGroupFootprintAvailable": True,
        "processGroupMemberCount": len(pids),
        "processGroupPhysicalFootprintBytes": sum(
            int(item["processPhysicalFootprintBytes"]) for item in readings
        ),
        "processGroupLifetimePeakPhysicalFootprintBytes": sum(
            int(item["processLifetimePeakPhysicalFootprintBytes"]) for item in readings
        ),
    }
