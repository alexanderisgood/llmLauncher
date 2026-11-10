"""Private frozen acquisition oracle and individually named comparison ports."""
import copy
import hashlib
import json
from pathlib import Path

import acquisition_planning as domain

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures' / 'acquisition_planning_legacy.py'
METADATA = json.loads(FIXTURE.with_suffix('.json').read_text())


def planner(root):
    values = {}
    for name in METADATA['constants']:
        value = getattr(root, name)
        if name == 'ENGINE_ADAPTERS':
            value = {key: domain.AcquisitionDescriptor(item.id, item.label, item.kind,
                     item.binary_key, item.protocol, item.built_in) for key, item in value.items()}
        values[name.lower()] = copy.deepcopy(value)
    def callback(name):
        return lambda *args, **kwargs: getattr(root, name)(*args, **kwargs)
    callbacks = {name.lstrip('_'): callback(name) for name in METADATA['ports']}
    callbacks.update(binary=lambda key: root.BINARIES.get(key),
        descriptor_public=lambda key: root.ENGINE_ADAPTERS[key].public(),
        now=lambda zone: root.datetime.now(zone), cancelled=root.LaunchCancelled)
    return domain.AcquisitionPlanning(domain.AcquisitionPolicy(**values), domain.AcquisitionServices(**callbacks))


def original(root):
    source = FIXTURE.read_bytes()
    assert hashlib.sha256(source).hexdigest() == METADATA['fixtureSha256']
    namespace = vars(root).copy()
    exec(compile(source, str(FIXTURE), 'exec'), namespace)
    return namespace


def method(owner, name):
    return getattr(domain, name) if name in METADATA['pureFunctions'] else getattr(owner, name)
