"""Explicit synthetic physical-memory samples for admission/benchmark fixtures.

Production never converts memorystatus percentages into capacity. These test
builders deliberately specify simulated physical page capacity separately from
the pressure field; the equal percentages in older scenarios are test inputs.
"""
from __future__ import annotations

import math
from typing import Any


def physical_snapshot(values: dict[str, Any]) -> dict[str, Any]:
    result = dict(values)
    total = values.get("totalBytes")
    simulated_capacity_percent = values.get("freePercent")
    ready = bool(
        values.get("memoryAvailable") is True
        and isinstance(total, int) and not isinstance(total, bool) and total > 0
        and isinstance(simulated_capacity_percent, (int, float)) and not isinstance(simulated_capacity_percent, bool)
        and math.isfinite(float(simulated_capacity_percent)) and 0 <= float(simulated_capacity_percent) <= 100
    )
    result.update({
        "memorySemanticsVersion": 2, "physicalMemoryAvailable": ready,
        "reclaimableMemorySource": "host_statistics64" if ready else None,
        "reclaimableBytes": round(total * float(simulated_capacity_percent) / 100) if ready else None,
    })
    return result


def physical_telemetry(values: dict[str, Any]) -> dict[str, Any]:
    result = dict(values)
    total = values.get("totalMemoryBytes")
    baseline = values.get("baselineHeadroomPercent")
    minimum = values.get("minimumHeadroomPercent")
    delta = values.get("peakPressureDeltaBytes")
    baseline_bytes = round(total * baseline / 100)
    minimum_bytes = baseline_bytes - delta if isinstance(delta, int) else round(total * minimum / 100)
    result.update({
        "version": 2, "memorySemanticsVersion": 2,
        "memorySource": "host_statistics64",
        "baselineHeadroomBytes": baseline_bytes, "minimumHeadroomBytes": minimum_bytes,
        "minimumHeadroomPercent": minimum_bytes * 100 / total,
        "peakReclaimableDeltaBytes": max(0, baseline_bytes - minimum_bytes),
    })
    return result
