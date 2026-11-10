"""Synthetic capacity computation/wiring timing; never starts an engine or agent.

Run from the repository root with Python. Results describe CPU microseconds per
call only; they do not measure inference TPS or change resource admission.
"""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import statistics
import sys
import timeit
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import launcher
import resource_admission
from tests.helpers.resource_admission_harness import Fixture, model, request, snapshot


def median_microseconds(callback, count=10_000):
    return statistics.median(timeit.repeat(callback, number=count, repeat=7)) * 1_000_000 / count


def measure():
    fixture = Fixture()
    physical = fixture.domain.public_session_resource(snapshot())
    arguments = (request("omlx"), model("omlx"), physical)
    original_estimate = fixture.legacy["launch_memory_estimate"](*arguments)
    assert fixture.domain.launch_memory_estimate(*arguments) == original_estimate
    with ExitStack() as stack:
        for name, callback in fixture.ports.items():
            stack.enter_context(mock.patch.object(launcher, name, new=callback))
        stack.enter_context(mock.patch.object(launcher.kolibri_runtime, "memory_plan", new=fixture.kolibri))
        stack.enter_context(mock.patch.object(launcher.splash_runtime, "memory_estimate", new=fixture.splash))
        stack.enter_context(mock.patch.object(launcher, "MANAGER", SimpleNamespace(hub_snapshot=fixture.read_hub)))
        stack.enter_context(mock.patch.object(launcher, "_RESOURCE_ADMISSION", None))
        stack.enter_context(mock.patch.object(launcher, "_RESOURCE_ADMISSION_INPUTS", None))
        wiring = launcher._resource_admission_service()
        assert launcher.launch_memory_estimate(*arguments) == original_estimate
        assert launcher._resource_admission_service() is wiring

        def reconstruct():
            launcher._RESOURCE_ADMISSION_INPUTS = None
            return launcher._resource_admission_service()

        cached = median_microseconds(launcher._resource_admission_service)
        forced = median_microseconds(reconstruct, count=1000)
        timings = {
            "denseEstimateLegacy": median_microseconds(lambda: fixture.legacy["launch_memory_estimate"](*arguments)),
            "denseEstimateDomain": median_microseconds(lambda: fixture.domain.launch_memory_estimate(*arguments)),
            "denseEstimateRootFacade": median_microseconds(lambda: launcher.launch_memory_estimate(*arguments)),
            "immutableWiringCached": cached,
            "immutableWiringForcedReconstruction": forced,
            "statelessKvLegacy": median_microseconds(lambda: fixture.legacy["effective_kv_precision"]("omlx", {})),
            "statelessKvRootFacade": median_microseconds(lambda: launcher.effective_kv_precision("omlx", {})),
        }
    return {
        "version": 1,
        "scope": "synthetic CPU computation and immutable dependency wiring only",
        "units": "median microseconds per call across seven repetitions",
        "inferenceMeasured": False,
        "eligibilityCached": False,
        "syntheticEstimateIdentical": True,
        "timings": timings,
        "sourceSha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                         for name in ("launcher.py", "resource_admission.py",
                                      "tests/fixtures/resource_admission_legacy.py")},
    }


if __name__ == "__main__":
    print(json.dumps(measure(), indent=2, sort_keys=True))
