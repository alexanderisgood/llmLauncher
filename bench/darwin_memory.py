#!/usr/bin/env python3
"""Read-only Darwin page-accounting and native telemetry evidence.

Reports pressure separately from physical reclaimable capacity and measures
native observation overhead. No model is loaded, stopped, or reconfigured.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import darwin_memory
import resource_telemetry


def run(repeats: int) -> dict:
    if sys.platform != "darwin":
        raise RuntimeError("This evidence requires a Darwin host")
    total = resource_telemetry.physical_memory_bytes()
    pressure = resource_telemetry.apple_memory_pressure_state()
    native = darwin_memory.physical_reclaimable_state(total)
    if not native["physicalMemoryAvailable"]:
        raise RuntimeError("Native physical-page counters are unavailable")
    start = time.perf_counter()
    cli = subprocess.run(["/usr/bin/vm_stat"], check=True, capture_output=True, text=True, timeout=3)
    cli_ms = (time.perf_counter() - start) * 1000
    page_size = int(re.search(r"page size of (\d+) bytes", cli.stdout).group(1))
    fields = {}
    for label in ["Pages free", "Pages purgeable", "File-backed pages", "Pages speculative"]:
        matched = re.search(rf"^{re.escape(label)}:\s+(\d+)\.", cli.stdout, re.MULTILINE)
        if not matched:
            raise RuntimeError(f"vm_stat omitted {label}")
        fields[label] = int(matched.group(1))
    cli_reclaimable = (fields["Pages free"] + fields["Pages purgeable"] + fields["File-backed pages"]) * page_size
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        value = darwin_memory.physical_reclaimable_state(total)
        samples.append((time.perf_counter() - start) * 1000)
        if not value["physicalMemoryAvailable"]:
            raise RuntimeError("Native physical-page read failed during measurement")
    return {
        "version": 1, "measuredAt": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "python": platform.python_version(),
        "scope": "Read-only Darwin memory accounting and observation overhead; no inference measured",
        "engineInferenceMeasured": False, "abiReady": darwin_memory._abi_ready(),
        "rev1IntegerCount": darwin_memory.HOST_VM_INFO64_REV1_COUNT,
        "nativePressure": pressure,
        "formerPressureDerivedCapacityBytes": round(total * pressure["freePercent"] / 100),
        "physicalReclaimable": native,
        "vmStatReference": {"pageSizeBytes": page_size, "pages": fields, "reclaimableBytes": cli_reclaimable},
        "sequentialObservationDifferenceBytes": cli_reclaimable - native["reclaimableBytes"],
        "nativeMedianReadMs": round(statistics.median(samples), 6),
        "nativeP95ReadMs": round(sorted(samples)[max(0, int(len(samples) * .95) - 1)], 6),
        "vmStatSingleReadMs": round(cli_ms, 6), "nativeRepeats": repeats,
        "kernelSamplingNote": "host_statistics64 may return XNU's short rate-limited sample; no userspace sample cache added",
        "sources": [
            "https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/vm/vm_page.h",
            "https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/kern/host.c",
            "https://github.com/apple-oss-distributions/xnu/blob/main/doc/vm/memorystatus_notify.md",
            "https://github.com/apple-oss-distributions/system_cmds/blob/main/memory_pressure/memory_pressure.c",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=50)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeat count must be positive")
    encoded = json.dumps(run(args.repeats), indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
