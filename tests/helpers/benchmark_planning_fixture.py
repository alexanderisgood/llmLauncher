"""Named synthetic/fresh authority ports; no controller namespace enters a domain."""
from __future__ import annotations

import copy
from contextlib import ExitStack, contextmanager
from datetime import datetime
import hashlib
import importlib
import json
import math
from pathlib import Path
import re
import secrets
from types import SimpleNamespace
import uuid
from unittest import mock

import launcher
import darwin_memory
import statistics
from sampling_contract import SamplingContractError, load_sampling_contract

ROOT = Path(__file__).resolve().parents[2]


class DomainFixture:
    def __init__(self, module_name, *, root=launcher, callbacks=None, constants=None):
        self.module = importlib.import_module(module_name)
        self.fixture = ROOT / "tests/fixtures" / (module_name + "_legacy.py")
        self.metadata = json.loads(self.fixture.with_suffix(".json").read_text())
        self.callbacks = dict(callbacks or {})
        self.constants = dict(constants or {})
        values = {}
        for name in self.metadata["constants"]:
            value = copy.deepcopy(self.constants.get(name, getattr(root, name)))
            if name in {"CLIENT_ADAPTERS", "ENGINE_ADAPTERS"}:
                value = {key: self.module.PlanningDescriptor(
                    item.id, item.label, item.binary_key, getattr(item, "built_in", False),
                    getattr(item, "protocol", "")) for key, item in value.items()}
            values[name.lower()] = value
        groups = {}
        for name, (group, field) in self.metadata["callbacks"].items():
            groups.setdefault(group, {})[field] = self.callback(root, name)
        if self.metadata["dynamicAttributes"]:
            groups["live"] = {"binary": lambda key: self.callbacks.get(
                "binary", lambda current: root.BINARIES.get(current))(key)}
            groups["live"]["engine_public"] = lambda key: self.callbacks.get(
                "engine_public", lambda current: root.ENGINE_ADAPTERS[current].public())(key)
        ports = {group: getattr(self.module, group.title() + "Ports")(**fields)
                 for group, fields in groups.items()}
        policy_type = (self.module.PlanningPolicy if module_name == "benchmark_planning"
                       else self.module.QualificationPolicy)
        owner = (self.module.BenchmarkPlanning if module_name == "benchmark_planning"
                 else self.module.RouteQualification)
        self.raw_policy_values = copy.deepcopy(values)
        self.policy = policy_type(**values)
        self.current = owner(self.policy, **ports)
        namespace = {
            "Any": object, "LaunchPlan": root.LaunchPlan, "Path": Path,
            "datetime": datetime, "copy": copy, "hashlib": hashlib, "json": json,
            "math": math, "re": re, "secrets": secrets, "statistics": statistics,
            "uuid": uuid, "darwin_memory": darwin_memory,
            "SamplingContractError": SamplingContractError,
            "load_sampling_contract": load_sampling_contract,
            **{name: copy.deepcopy(self.constants.get(name, getattr(root, name)))
               for name in self.metadata["constants"]},
            **{name: self.callback(root, name) for name in self.metadata["callbacks"]},
        }
        if self.metadata["dynamicAttributes"]:
            namespace["BINARIES"] = BinaryLookup(lambda key: self.callbacks.get(
                "binary", lambda current: root.BINARIES.get(current))(key))
        body = self.fixture.read_text().split("\n\n", 1)[1]
        assert hashlib.sha256(body.encode()).hexdigest() == self.metadata["fixtureSha256"]
        exec(compile(self.fixture.read_text(), str(self.fixture), "exec"), namespace)
        self.original = namespace
        if module_name == "benchmark_planning":
            before = '"clientLabel": {"pi": "Pi", "opencode": "OpenCode", "codex": "Codex", "chat": "Chat"}'
            after = '"clientLabel": {"pi": "Pi", "omp": "oh-my-pi", "opencode": "OpenCode", "codex": "Codex", "chat": "Chat"}'
            frozen = self.fixture.read_text()
            assert frozen.count(before) == 1
            repaired = dict(namespace)
            exec(compile(frozen.replace(before, after), str(self.fixture) + "-label-repair", "exec"), repaired)
            self.repaired_original = repaired
        else:
            self.repaired_original = self.original

    def callback(self, root, name):
        return lambda *args, **kwargs: self.callbacks.get(name, getattr(root, name))(*args, **kwargs)

    def method(self, name):
        if name in self.metadata["pureFunctions"]:
            return getattr(self.module, name)
        return getattr(self.current, name)


class BinaryLookup:
    def __init__(self, callback): self.callback = callback
    def get(self, name): return self.callback(name)


def generated_model(project):
    return {
        "id": "generated-model", "name": "Generated exact fixture", "ready": True,
        "path": str(project), "nativeContext": 262144, "defaultOutput": 1024,
        "defaultSampling": {"temperature": 1.0, "top_p": 0.95, "top_k": 20},
        "templateReasoningEfforts": ["low", "medium", "high"],
        "backends": {backend: {
            "runnable": True, "mtp": backend in {"omlx", "mtplx", "lmstudio"},
            "dflash": False, "kv": backend in {"omlx", "mtplx", "kolibri"},
            "depth": 1, "depthMax": 3, "agentReasoning": ["auto", "off", "medium"],
            "codexReasoning": ["auto", "medium"], "customSampling": True,
            "implicitSamplingDefaultsVerified": True,
            "benchmarkModelFingerprint": "a" * 64,
            "runtimeVersion": "generated-" + backend, "comparisonIdentity": "b" * 64,
        } for backend in launcher.ENGINE_ADAPTERS},
    }


@contextmanager
def planning_environment():
    with ExitStack() as stack:
        binaries = {key: "/generated/" + key for key in launcher.BINARIES}
        binaries.update({item.binary_key: "/generated/" + item.binary_key
                         for item in [*launcher.CLIENT_ADAPTERS.values(), *launcher.ENGINE_ADAPTERS.values()]
                         if item.binary_key})
        stack.enter_context(mock.patch.dict(launcher.BINARIES, binaries))
        stack.enter_context(mock.patch.object(launcher, "command_version", return_value="generated-runtime"))
        stack.enter_context(mock.patch.object(launcher, "hardware_fingerprint", return_value="generated-hardware"))
        stack.enter_context(mock.patch.object(launcher, "physical_memory_bytes", return_value=48 * 1024**3))
        stack.enter_context(mock.patch.object(uuid, "uuid4", return_value=uuid.UUID("11111111-1111-4111-8111-111111111111")))
        for owner, name in ((launcher, "free_port"), (launcher, "atomic_json"),
                            (launcher.subprocess, "Popen")):
            stack.enter_context(mock.patch.object(owner, name, side_effect=AssertionError("read-only planning performed external work")))
        yield


def outcome(callback, *args, **kwargs):
    try:
        return {"value": callback(*copy.deepcopy(args), **copy.deepcopy(kwargs))}
    except (ValueError, RuntimeError, KeyError) as error:
        return {"errorType": type(error).__name__, "error": str(error)}


def normalize(value, project):
    return json.loads(json.dumps(value, ensure_ascii=False).replace(str(project), "PROJECT"))


def qualification_model(record):
    backend = record["backend"]
    model = {"id": record.get("modelId", "generated-qualified"), "name": "Generated qualified original artifact",
             "ready": True, "path": "/generated/original-model", "backends": {}}
    capability = {"runnable": True, "mtp": False, "dflash": False,
                  "localBenchmark": copy.deepcopy(record), "localBenchmarks": [copy.deepcopy(record)],
                  "benchmarkModelFingerprint": record.get("modelFingerprint"),
                  "runtimeVersion": record.get("runtimeVersion"), "agentReasoning": ["auto"],
                  "codexReasoning": ["auto"]}
    model["backends"][backend] = capability
    if backend == "omlx":
        model["modelType"] = "qwen4_exp_text"
        model["qwen4Ple"] = {"supported": True, "storage": "mmap"}
    if backend == "uzu":
        model["uzuNative"] = True
        capability["runtimeManagedAcceleration"] = "DFlash + Weaver"
        contract = record["qualificationContract"]
        capability.update({"modelRegistryId": contract["modelRegistryId"],
                           "modelCommit": contract["modelCommit"],
                           "modelToolchainVersion": contract["modelToolchainVersion"]})
        capability["runtimeIdentity"] = {
            "ready": True, "binaryIdentityPinned": True,
            "binary": {"sha256": contract["runtimeBinarySha256"], "size": contract["runtimeBinarySize"]},
            "upstreamCommit": contract["runtimeUpstreamCommit"],
            "sourcePatchSha256": contract["runtimeSourcePatchSha256"],
            "networkSandbox": True, "memorySafetyBlocked": False,
            "rawListenerAuthenticated": True, "rawListenerIsolated": False,
            "listenerIsolationBlocked": False, "boundedContextReady": True,
            "nativeBoundaryContractId": contract["nativeBoundaryContractId"],
            "nativeBearerAuthentication": True, "oneUseApiKeyFile": True,
            "nativeContextLimit": True, "nativeOutputLimit": True,
        }
        capability["qualificationSystemContract"] = {
            "rawListenerProtected": True, "nativeBoundaryContractId": contract["nativeBoundaryContractId"],
            "nativeBearerAuthentication": True, "oneUseApiKeyFile": True,
            "nativeContextLimit": True, "nativeOutputLimit": True,
            "osReserveBytes": contract["osReserveBytes"], "sandboxProfileSha256": contract["sandboxProfileSha256"],
        }
    if backend == "llamacpp":
        contract = record["qualificationContract"]
        receipt = contract["receiptFingerprint"]
        atomic = {"ready": True, "currentProcessVerified": True, "verificationGeneration": 7,
                  "repoId": launcher.LLAMACPP_ATOMIC_REPO,
                  "pinnedRevision": launcher.LLAMACPP_ATOMIC_REVISION,
                  "variantId": launcher.LLAMACPP_ATOMIC_VARIANT_ID,
                  "variant": launcher.LLAMACPP_ATOMIC_VARIANT,
                  "shardCount": launcher.LLAMACPP_ATOMIC_SHARDS,
                  "weightBytes": launcher.LLAMACPP_ATOMIC_TOTAL_BYTES,
                  "context": launcher.LLAMACPP_PLE_CONTEXT,
                  "receiptFingerprint": receipt, "firstShard": "/generated/original-model/first.gguf"}
        capability.update({"llamacppPle": True, "currentProcessVerified": True,
                           "verificationGeneration": 7, "receiptFingerprint": receipt,
                           "contextWindows": [launcher.LLAMACPP_PLE_CONTEXT],
                           "contextMaximum": launcher.LLAMACPP_PLE_CONTEXT,
                           "memoryCeilingBytes": launcher.LLAMACPP_PLE_MEMORY_CEILING_BYTES,
                           "firstShard": atomic["firstShard"], "modelPath": model["path"],
                           "atomicPle": copy.deepcopy(atomic)})
        model["atomicPle"] = copy.deepcopy(atomic)
    return model
