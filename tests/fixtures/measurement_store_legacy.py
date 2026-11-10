from __future__ import annotations

def ane_tuning_store_path() -> Path:
    return STATE_DIR / "ane-tuning.json"

def load_ane_tuning_records() -> list[dict[str, Any]]:
    store = read_json(ane_tuning_store_path())
    if store.get("version") != ANE_TUNER_STORE_VERSION:
        return []
    records = store.get("records")
    if not isinstance(records, list):
        return []
    return [copy.deepcopy(item) for item in records if isinstance(item, dict)][-ANE_TUNER_MAX_RECORDS:]

def save_ane_tuning_record(record: dict[str, Any]) -> None:
    required = {
        "id", "createdAt", "scope", "modelFingerprint", "runtimeVersion",
        "hardwareFingerprint", "sequenceLength", "recommendation", "status",
    }
    if not required.issubset(record):
        raise ValueError("ANE tuning evidence is incomplete and was not saved.")
    identity = (
        record.get("modelFingerprint"), record.get("runtimeVersion"),
        record.get("hardwareFingerprint"), record.get("sequenceLength"),
    )
    records = [
        item for item in load_ane_tuning_records()
        if (
            item.get("modelFingerprint"), item.get("runtimeVersion"),
            item.get("hardwareFingerprint"), item.get("sequenceLength"),
        ) != identity
    ]
    records.append(copy.deepcopy(record))
    atomic_json(ane_tuning_store_path(), {
        "version": ANE_TUNER_STORE_VERSION,
        "records": records[-ANE_TUNER_MAX_RECORDS:],
    })

def benchmark_store_path() -> Path:
    return STATE_DIR / "benchmarks.json"

def load_benchmark_records() -> list[dict[str, Any]]:
    store = read_json(benchmark_store_path())
    if store.get("version") != BENCHMARK_STORE_VERSION:
        return []
    records = store.get("records")
    if not isinstance(records, list):
        return []
    return [copy.deepcopy(item) for item in records if isinstance(item, dict)][-BENCHMARK_MAX_RECORDS:]

def save_benchmark_records(new_records: list[dict[str, Any]]) -> None:
    """Atomically append bounded evidence without losing like-for-like history."""
    required = {
        "id", "createdAt", "scope", "backend", "modelFingerprint",
        "runtimeVersion", "hardwareFingerprint", "winner", "comparedModes",
    }
    if not new_records:
        raise ValueError("No benchmark evidence was supplied.")
    if any(not isinstance(record, dict) or not required.issubset(record) for record in new_records):
        raise ValueError("Benchmark evidence is incomplete and was not saved.")
    for record in new_records:
        backend = str(record.get("backend") or "")
        identity = record.get("ssdComparisonIdentity")
        if backend in SSD_STREAMING_BACKENDS:
            if (
                record.get("ssdStreaming") is not True
                or not isinstance(identity, str)
                or re.fullmatch(r"[0-9a-f]{64}", identity) is None
            ):
                raise ValueError("SSD benchmark evidence is missing its verified source identity.")
        elif record.get("ssdStreaming") is True or identity not in {None, ""}:
            raise ValueError("Non-SSD benchmark evidence contains an SSD source identity.")
    new_ids = {str(record.get("id") or "") for record in new_records}
    new_shootout_routes = {
        (str(record.get("shootoutId") or ""), str(record.get("backend") or ""))
        for record in new_records if record.get("shootoutId")
    }
    records = [
        item for item in load_benchmark_records()
        if str(item.get("id") or "") not in new_ids
        and (
            not item.get("shootoutId")
            or (str(item.get("shootoutId")), str(item.get("backend") or "")) not in new_shootout_routes
        )
    ]
    records.extend(copy.deepcopy(new_records))
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in records:
        groups.setdefault(benchmark_record_identity(record), []).append(record)
    retained: list[dict[str, Any]] = []
    for group in groups.values():
        retained.extend(sorted(
            group, key=lambda item: (str(item.get("createdAt") or ""), str(item.get("id") or "")),
        )[-BENCHMARK_MAX_HISTORY_PER_ROUTE:])
    retained.sort(key=lambda item: (str(item.get("createdAt") or ""), str(item.get("id") or "")))
    atomic_json(benchmark_store_path(), {
        "version": BENCHMARK_STORE_VERSION,
        "records": retained[-BENCHMARK_MAX_RECORDS:],
    })

def save_benchmark_record(record: dict[str, Any]) -> None:
    """Atomically append one bounded historical measurement."""
    save_benchmark_records([record])

def runtime_promotion_store_path() -> Path:
    return STATE_DIR / RUNTIME_PROMOTION_STORE

def load_runtime_promotion_records() -> list[dict[str, Any]]:
    store = read_json(runtime_promotion_store_path())
    if store.get("version") != RUNTIME_PROMOTION_SCHEMA_VERSION:
        return []
    records = store.get("records")
    if not isinstance(records, list):
        return []
    return [copy.deepcopy(item) for item in records if isinstance(item, dict)][-RUNTIME_PROMOTION_MAX_RECORDS:]

def save_runtime_promotion_record(record: dict[str, Any]) -> None:
    required = {
        "id", "createdAt", "contractId", "planId", "modelFingerprint",
        "hardwareFingerprint", "selected", "candidate", "executionOrder",
        "qualityMatched", "resourceComparable", "canPromote", "measurements",
    }
    if not required.issubset(record):
        raise ValueError("Runtime promotion evidence is incomplete and was not saved.")
    with RUNTIME_PROMOTION_LOCK:
        records = [
            item for item in load_runtime_promotion_records()
            if str(item.get("id") or "") != str(record.get("id") or "")
        ]
        records.append(copy.deepcopy(record))
        atomic_json(runtime_promotion_store_path(), {
            "version": RUNTIME_PROMOTION_SCHEMA_VERSION,
            "records": records[-RUNTIME_PROMOTION_MAX_RECORDS:],
        })
