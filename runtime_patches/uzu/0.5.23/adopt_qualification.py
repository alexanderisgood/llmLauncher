"""Adopt this host's exact candidate receipts without rewriting their identity.

Default is read-only. --apply requires the normal controller to be stopped,
backs up its existing history, and merges only the two verified local results.
It neither installs a runtime nor loads a model.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

PATCH_ROOT = Path(__file__).resolve().parent
ROOT = PATCH_ROOT.parents[2]
RECORDS = {
    "7cd4a040-9ab7-433d-b301-ac44bf4dd8b3": 65536,
    "8811a1ac-230b-4208-9b35-0b8ec202b3f2": 131072,
}


def verified_records(app, source: Path):
    from candidate_qualification import BINARY_SHA256, BINARY_SIZE, PATCH_CHAIN_SHA256, TAG, request
    if (app.UZU_RUNTIME_RELEASE_BINARY_SHA256, app.UZU_RUNTIME_RELEASE_BINARY_SIZE,
        app.UZU_RUNTIME_SOURCE_PATCH_SHA256, app.UZU_RUNTIME_TAG) != (
        BINARY_SHA256, BINARY_SIZE, PATCH_CHAIN_SHA256, TAG,
    ):
        raise ValueError("Normal launcher is not pinned to the exact qualified candidate")
    if app.uzu_runtime_contract(str(app.UZU_RUNTIME_PATH)).get("ready") is not True:
        raise ValueError("The exact candidate is not safely installed at the normal runtime path")
    document = json.loads(source.read_text())
    selected = [copy.deepcopy(record) for record in document["records"] if record.get("id") in RECORDS]
    if len(selected) != len(RECORDS) or {record["id"] for record in selected} != set(RECORDS):
        raise ValueError("The two exact measured receipts are missing or duplicated")
    fingerprint = app.hardware_fingerprint()
    models = app.uzu_model_records(selected, fingerprint)
    for record in selected:
        context = RECORDS[record["id"]]
        if record.get("hardwareFingerprint") != fingerprint or record.get("contextMin") != context:
            raise ValueError("Receipt does not match this hardware and measured context")
        plan = app.calibration_plan(request(context), models)
        if plan.get("action") != "apply-existing" or plan.get("evidence", {}).get("qualified") is not True:
            raise ValueError(f"Normal launcher rejected the saved {context}-token qualification")
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(PATCH_ROOT))
    import launcher as app
    from candidate_qualification import STATE, exclusive_controller_lock
    source = STATE / "benchmarks.json"
    selected = verified_records(app, source)
    if not args.apply:
        print(json.dumps({"ready": True, "recordIds": [record["id"] for record in selected]}))
        return
    with exclusive_controller_lock(app.controller_instance_path()):
        selected = verified_records(app, source)
        previous = app.load_benchmark_records()
        original_by_id = {record["id"]: record for record in previous}
        for record in selected:
            existing = original_by_id.get(record["id"])
            if existing is not None and existing != record:
                raise ValueError("An existing receipt with the same ID differs; nothing was overwritten")
        backup = None
        if any(record["id"] not in original_by_id for record in selected):
            snapshot = {"version": app.BENCHMARK_STORE_VERSION, "records": previous}
            snapshot_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()[:16]
            backup = app.STATE_DIR / f"benchmarks-before-uzu-prefill-{snapshot_hash}.json"
            if backup.exists():
                if app.read_json(backup) != snapshot:
                    raise ValueError("History backup path already contains different data")
            else:
                app.atomic_json(backup, snapshot)
            app.save_benchmark_records(selected)
        saved = {record["id"]: record for record in app.load_benchmark_records()}
        if any(saved.get(record["id"]) != record for record in selected):
            raise RuntimeError("Adopted receipts failed exact post-save comparison")
        retained = all(saved.get(key) == value for key, value in original_by_id.items())
        print(json.dumps({"adopted": list(RECORDS), "originalHistoryRetained": retained,
                          "backup": str(backup) if backup else None}, indent=2))


if __name__ == "__main__":
    main()
