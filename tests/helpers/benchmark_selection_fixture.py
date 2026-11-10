"""Generated comparison wiring; production never receives a controller namespace."""
import copy
import hashlib
import json
from pathlib import Path

import benchmark_selection as domain

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "benchmark_selection_legacy.py"
METADATA = json.loads(FIXTURE.with_suffix(".json").read_text())


def planner(root):
    policy_values = {}
    for name in METADATA["constants"]:
        value = getattr(root, name)
        if name in {"ENGINE_ADAPTERS", "CLIENT_ADAPTERS"}:
            value = {key: domain.SelectionDescriptor(item.id, item.label, item.binary_key,
                     getattr(item, "built_in", False)) for key, item in value.items()}
        policy_values[name.lower()] = copy.deepcopy(value)

    def callback(name):
        return lambda *args, **kwargs: getattr(root, name)(*args, **kwargs)

    groups = {name: {} for name in ("contracts", "evidence", "live")}
    for name, group in METADATA["functionGroups"].items():
        groups[group][name.lstrip("_")] = callback(name)
    groups["live"].update(binary=lambda key: root.BINARIES.get(key),
        descriptor_public=lambda key: root.ENGINE_ADAPTERS[key].public(),
        mode_label=lambda route: root.BenchmarkManager._mode_label(route),
        now=lambda zone: root.datetime.now(zone))
    return domain.BenchmarkSelection(domain.SelectionPolicy(**policy_values),
        domain.SelectionContracts(**groups["contracts"]),
        domain.SelectionEvidence(**groups["evidence"]), domain.SelectionLive(**groups["live"]))


def original(root):
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == METADATA["fixtureSha256"]
    namespace = vars(root).copy()
    exec(compile(raw, str(FIXTURE), "exec"), namespace)
    return namespace


def method(instance, name):
    return getattr(domain, name) if name in METADATA["pureFunctions"] else getattr(instance, name)
