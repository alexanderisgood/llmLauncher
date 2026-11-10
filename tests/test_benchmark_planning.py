"""Complete planning bodies and generated exact route decisions."""
from __future__ import annotations

import ast
import copy
import dataclasses
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import benchmark_planning
import launcher
from tests.helpers.benchmark_planning_fixture import (
    DomainFixture, ROOT, generated_model, planning_environment, outcome, normalize,
)


class Projection(ast.NodeTransformer):
    def __init__(self, metadata): self.metadata = metadata
    def visit_Call(self, node):
        if ast.unparse(node) == "self.live.engine_public(backend)":
            return ast.copy_location(ast.parse("ENGINE_ADAPTERS[backend].public()", mode="eval").body, node)
        return self.generic_visit(node)
    def visit_Attribute(self, node):
        text = ast.unparse(node)
        for name in self.metadata["constants"]:
            if text == "self.policy." + name.lower():
                return ast.copy_location(ast.Name(name, ast.Load()), node)
        for name, (group, field) in self.metadata["callbacks"].items():
            if text == "self." + group + "." + field:
                return ast.copy_location(ast.Name(name, ast.Load()), node)
        if text == "self.live.binary":
            return ast.copy_location(ast.Attribute(ast.Name("BINARIES", ast.Load()), "get", ast.Load()), node)
        if isinstance(node.value, ast.Name) and node.value.id == "self" and node.attr in self.metadata["functions"]:
            return ast.copy_location(ast.Name(node.attr, ast.Load()), node)
        return self.generic_visit(node)


class BenchmarkPlanningSourceTests(unittest.TestCase):
    def test_all47_complete_bodies_and_signatures_match_frozen(self):
        fixture = DomainFixture("benchmark_planning")
        self.assertEqual(fixture.policy.input_values(), fixture.raw_policy_values)
        verify_complete_bodies(self, fixture, "BenchmarkPlanning")

    def test_import_starts_no_io_process_or_controller(self):
        verify_import(self, "benchmark_planning")

    def test_policy_is_detached_and_binary_validation_callback_stays_live(self):
        fixture = DomainFixture("benchmark_planning")
        with self.assertRaises(dataclasses.FrozenInstanceError): fixture.policy.benchmark_minimum_speedup = 0
        with self.assertRaises(TypeError): fixture.policy.backend_labels["omlx"] = "changed"
        with self.assertRaises(TypeError): fixture.policy.benchmark_suites["quick"]["promptTokens"].append(1)
        detached = copy.deepcopy(fixture.policy.benchmark_suites)
        detached["quick"]["promptTokens"].append(1)
        self.assertNotEqual(fixture.policy.benchmark_suites["quick"]["promptTokens"], detached["quick"]["promptTokens"])
        for value in ("/generated/first", "/generated/second", None):
            fixture.callbacks["binary"] = lambda key, selected=value: selected
            self.assertEqual(fixture.current.live.binary("omlx"), value)
        fixture.callbacks["validated_limits"] = lambda *args: (8192, 1024)
        self.assertEqual(fixture.current.contracts.validated_limits({}, {}), (8192, 1024))
        fixture.callbacks["validated_limits"] = lambda *args: (65536, 4096)
        self.assertEqual(fixture.current.contracts.validated_limits({}, {}), (65536, 4096))

    def test_root_facades_keep_all_signatures_and_direct_helpers_without_wiring(self):
        for name, factory in (("benchmark_planning", "_benchmark_planning"),
                              ("route_qualification", "_route_qualification_service")):
            fixture = DomainFixture(name)
            self.assertIn(ROOT / (name + ".py"), launcher.CONTROLLER_SOURCE_PATHS)
            for function in fixture.metadata["functions"]:
                with self.subTest(domain=name, function=function):
                    signature = lambda value: [(item.name, item.kind, item.default)
                                               for item in inspect.signature(value).parameters.values()]
                    self.assertEqual(signature(getattr(launcher, function)), signature(fixture.original[function]))
                    if function in fixture.metadata["pureFunctions"]:
                        node = ast.parse(inspect.getsource(getattr(launcher, function))).body[0]
                        result = node.body[-1]
                        self.assertIsInstance(result, ast.Return)
                        self.assertEqual(ast.unparse(result.value.func), name + "." + function)
            with mock.patch.object(launcher, factory, side_effect=AssertionError("pure helper constructed wiring")):
                if name == "benchmark_planning":
                    self.assertEqual(launcher.benchmark_measurement_count({"promptTokens": [1, 2], "repetitions": 3}), 6)
                else:
                    self.assertTrue(launcher.qwen_ple_route_qualification_reasoning_contract(
                        {"reasoning": "auto", "client": "omp"},
                        {"backends": {"omlx": {"agentReasoning": ["medium"]}}})["reasoningEnabled"])

    def test_root_reuses_only_static_wiring_and_live_ports_rebind_after_creation(self):
        planning = launcher._benchmark_planning()
        qualification = launcher._route_qualification_service()
        self.assertIs(launcher._benchmark_planning(), planning)
        self.assertIs(launcher._route_qualification_service(), qualification)
        with mock.patch.dict(launcher.BINARIES, {"omlx": "/generated/live-install"}), \
                mock.patch.object(launcher, "hardware_fingerprint", return_value="generated-current-hardware"), \
                mock.patch.object(launcher, "physical_memory_bytes", return_value=96 * 1024**3), \
                mock.patch.object(launcher, "route_qualification_record_is_fresh", return_value=False):
            self.assertIs(launcher._benchmark_planning(), planning)
            self.assertIs(launcher._route_qualification_service(), qualification)
            self.assertEqual(planning.live.binary("omlx"), "/generated/live-install")
            self.assertTrue(planning.live.engine_public("omlx")["installed"])
            self.assertEqual(planning.artifacts.hardware_fingerprint(), "generated-current-hardware")
            self.assertEqual(qualification.resources.physical_memory_bytes(), 96 * 1024**3)
            self.assertFalse(qualification.evidence.route_qualification_record_is_fresh({}))
        old = planning.policy.backend_labels["omlx"]
        with mock.patch.dict(launcher.BACKEND_LABELS, {"omlx": "Generated changed label"}):
            changed = launcher._benchmark_planning()
            changed_qualification = launcher._route_qualification_service()
            self.assertIsNot(changed, planning)
            self.assertIsNot(changed_qualification, qualification)
            self.assertEqual(changed.policy.backend_labels["omlx"], "Generated changed label")
            self.assertEqual(planning.policy.backend_labels["omlx"], old)
            self.assertIs(launcher._benchmark_planning(), changed)
            self.assertIs(launcher._route_qualification_service(), changed_qualification)
        self.assertEqual(launcher._benchmark_planning().policy.backend_labels["omlx"], old)


class BenchmarkPlanningDecisionTests(unittest.TestCase):
    def test_all528_complete_frozen_pi_omp_route_and_calibration_cases(self):
        stored = json.loads((ROOT / "tests/fixtures/benchmark_planning_records.json").read_text())
        self.assertEqual(len(stored["cases"]), 528)
        with tempfile.TemporaryDirectory(prefix="benchmark-planning-proof-") as project, planning_environment():
            fixture = DomainFixture("benchmark_planning")
            self.assertEqual(stored["fixtureSha256"], fixture.metadata["fixtureSha256"])
            for case in stored["cases"]:
                request = json.loads(json.dumps(case["request"]).replace("PROJECT", project))
                model = generated_model(project)
                if case.get("modelVariant") == "dense-three-engine":
                    model["backends"] = {name: value for name, value in model["backends"].items()
                                         if name in {"omlx", "mtplx", "lmstudio"}}
                if "defaultSampling" in case:
                    model["defaultSampling"] = copy.deepcopy(case["defaultSampling"])
                with self.subTest(method=case["method"], backend=request["backend"],
                                  client=request["client"], context=request["context"],
                                  kv=request["options"]["kv"]):
                    current = outcome(fixture.method(case["method"]), request, [model], **case["kwargs"])
                    before = outcome(fixture.original[case["method"]], request, [model], **case["kwargs"])
                    self.assertEqual(normalize(before, project), case.get("legacyExpected", case["expected"]))
                    self.assertEqual(normalize(current, project), case["expected"])
                    if "value" in current and case["method"] == "validated_benchmark_request":
                        job = current["value"]
                        self.assertEqual((job["context"], job["output"], job["client"]),
                                         (request["context"], request["output"], request["client"]))
                        self.assertEqual(job["evidence"]["kv"], request["options"]["kv"])
                        self.assertEqual(job["speedSampling"], model["defaultSampling"])

    def test_omp_label_repair_retains_complete_original_plan_and_readonly_guards(self):
        with tempfile.TemporaryDirectory(prefix="benchmark-omp-label-") as project, planning_environment():
            fixture = DomainFixture("benchmark_planning")
            model = generated_model(project)
            model["backends"] = {key: value for key, value in model["backends"].items()
                                 if key in {"omlx", "mtplx", "lmstudio"}}
            for client, label in (("pi", "Pi"), ("omp", "oh-my-pi")):
                request = {"backend": "mtplx", "client": client, "agentHost": "terminal",
                           "modelId": model["id"], "project": project, "context": 16384,
                           "output": 1024, "reasoning": "auto", "suite": "agentic",
                           "mode": "custom", "options": {"acceleration": "off", "depth": 1, "kv": "off"}}
                before = outcome(fixture.original["calibration_plan"], request, [model])
                expected = fixture.repaired_original["calibration_plan"](copy.deepcopy(request), [copy.deepcopy(model)])
                current = fixture.current.calibration_plan(copy.deepcopy(request), [copy.deepcopy(model)])
                self.assertEqual(current, expected)
                self.assertEqual(launcher.calibration_plan(copy.deepcopy(request), [copy.deepcopy(model)]), expected)
                self.assertEqual(current["clientLabel"], label)
                self.assertTrue(current["ready"])
                self.assertEqual(current["action"], "measure")
                self.assertEqual(current["eligibleEngineCount"], 3)
                self.assertEqual(current["request"]["output"], 1024)
                self.assertEqual(current["request"]["context"], 16384)
                self.assertFalse(current["privacy"]["usesProjectData"])
                if client == "omp":
                    self.assertEqual(before, {"errorType": "KeyError", "error": "'omp'"})
                else:
                    self.assertEqual(before["value"], current)

    def test_generated_corpora_agent_prefixes_and_128k_conversation_contracts_are_exact(self):
        fixture = DomainFixture("benchmark_planning")
        for budget in (1, 1024, 8192, 65536, 131072):
            for name in ("benchmark_words", "qwen_token_budgeted_words", "uzu_qualification_words", "benchmark_prompt"):
                current = fixture.method(name)(budget, 183211)
                original = fixture.original[name](budget, 183211)
                self.assertTrue(current == original, name + " complete generated corpus differs")
        for suite_name in ("agentic", *launcher.ROUTE_QUALIFICATION_UZU_SUITES_BY_CONTEXT.values()):
            suite = copy.deepcopy(launcher.BENCHMARK_SUITES[suite_name])
            for complete in (False, True):
                current = fixture.current.benchmark_agentic_cases(suite, require_complete_answer=complete)
                original = fixture.original["benchmark_agentic_cases"](suite, require_complete_answer=complete)
                self.assertTrue(current == original, "Full prefix/tool/turn workload differs")
                self.assertEqual(fixture.module.benchmark_measurement_count(suite), len(current))
                if suite.get("uzuTokenBudgetedCorpus") is True:
                    for context in launcher.UZU_SAFE_CONTEXT_WINDOWS:
                        history = []
                        previous = None
                        for case in current:
                            before = outcome(fixture.original["uzu_conversation_case"], case, history,
                                             previous, context, 8192)
                            after = outcome(fixture.current.uzu_conversation_case, case, history,
                                            previous, context, 8192)
                            self.assertTrue(before == after, "Complete continuing conversation differs")
                            if "value" in after:
                                result = after["value"]
                                previous = {"promptTokens": result["targetPromptTokens"], "completionTokens": 256}
                                history = [*result["messages"], {"role": "assistant", "content": "Generated completed response"}]

    def test_tuning_sweeps_keep_all_bounds_preset_fidelity_and_disclosures(self):
        with tempfile.TemporaryDirectory(prefix="benchmark-tuning-proof-") as project, planning_environment():
            fixture = DomainFixture("benchmark_planning")
            model = generated_model(project)
            model["backends"]["lmstudio"]["mtpRuntimeVerified"] = True
            model["backends"]["omlx"].update({"dflashMaxBlockSize": 24, "dflashDefaultBlockSize": 16})
            for backend in ("omlx", "lmstudio", "mtplx", "swiftlm", "mference"):
                request = {"backend": backend, "client": "pi", "modelId": model["id"],
                           "project": project, "context": 16384, "output": 1024,
                           "reasoning": "auto", "suite": "agentic", "mode": "custom",
                           "options": {"acceleration": "off", "depth": 1, "kv": "off"}}
                job = fixture.current.validated_benchmark_request(request, [model], allow_baseline_only=True)
                before, current = copy.deepcopy(job), copy.deepcopy(job)
                for name in ("prepare_calibration_tuning_plan", "prepare_engine_settings_sweep"):
                    fixture.original[name](before)
                    fixture.method(name)(current)
                    self.assertEqual(current, before)
                for name in ("benchmark_job_measurement_routes", "benchmark_job_maximum_route_count",
                             "benchmark_job_public_modes", "public_benchmark_settings_search_plan",
                             "engine_settings_sweep_contract"):
                    self.assertEqual(fixture.method(name)(current), fixture.original[name](before))
                fixture.current.validate_engine_settings_sweep_budget([current])
                if "engineSettingsSweep" in current:
                    self.assertLessEqual(current["engineSettingsSweep"]["maximumModelLoads"],
                                         launcher.ENGINE_SETTINGS_SWEEP_MAX_MODEL_LOADS)
                    self.assertEqual(current["output"], request["output"])
                    self.assertEqual(current["evidence"]["kv"], "off")
            base = copy.deepcopy(job)
            base.update({"backend": "omlx", "modes": ["ar", "dflash2"], "options": {}})
            self.assertEqual(fixture.current.dflash2_tuning_plan(base), fixture.original["dflash2_tuning_plan"](base))
            limited = fixture.current.dflash2_tuning_plan(base)
            self.assertTrue(limited["resourceGatePerCandidate"])
            self.assertTrue(limited["greedyParityPerCandidate"])
            self.assertLessEqual(len(limited["blockCandidates"]), 5)

    def test_shootout_and_tuning_request_entries_preserve_complete_jobs_and_fresh_pairs(self):
        with tempfile.TemporaryDirectory(prefix="benchmark-request-entries-") as project, planning_environment():
            fixture = DomainFixture("benchmark_planning")
            model = generated_model(project)
            model["backends"] = {key: value for key, value in model["backends"].items()
                                 if key in {"omlx", "mtplx", "lmstudio"}}
            model["backends"]["lmstudio"]["mtpRuntimeVerified"] = True
            payload = {"backend": "mtplx", "client": "pi", "agentHost": "terminal",
                       "modelId": model["id"], "project": project, "context": 16384,
                       "output": 1024, "reasoning": "auto", "suite": "agentic",
                       "mode": "custom", "options": {"acceleration": "off", "depth": 1, "kv": "off"}}
            for client in ("pi", "omp"):
                payload["client"] = client
                before = fixture.original["validated_engine_shootout_request"](copy.deepcopy(payload), [copy.deepcopy(model)])
                current = fixture.current.validated_engine_shootout_request(copy.deepcopy(payload), [copy.deepcopy(model)])
                self.assertEqual(current, before)
                self.assertEqual(len(current["jobs"]), 3)
                self.assertTrue(all((job["client"], job["context"], job["output"]) ==
                                    (client, 16384, 1024) for job in current["jobs"]))
            payload.update(backend="lmstudio", client="pi")
            self.assertEqual(fixture.current.validated_lmstudio_mtp_tuning_request(payload, [model]),
                             fixture.original["validated_lmstudio_mtp_tuning_request"](payload, [model]))
            model["backends"]["lmstudio"]["mtpRuntimeVerified"] = False
            self.assertEqual(outcome(fixture.current.validated_lmstudio_mtp_tuning_request, payload, [model]),
                             outcome(fixture.original["validated_lmstudio_mtp_tuning_request"], payload, [model]))
            flags = {"pair": True}
            fixture.callbacks.update({"omlx_has_recommended_dflash2_runtime": lambda *_: True,
                                      "dflash2_capability_valid": lambda *_: flags["pair"]})
            model["backends"]["omlx"].update({"dflash": True, "dflashVersion": "2",
                "dflashRuntimeVersion": "generated-runtime", "dflashMaxBlockSize": 24,
                "dflashDefaultBlockSize": 16})
            payload["backend"] = "omlx"
            before = fixture.original["validated_dflash2_tuning_request"](payload, [model])
            current = fixture.current.validated_dflash2_tuning_request(payload, [model])
            self.assertEqual(current, before)
            self.assertEqual(current["kind"], "omlx-dflash2-tuning")
            flags["pair"] = False
            rejected = outcome(fixture.current.validated_dflash2_tuning_request, payload, [model])
            self.assertEqual(rejected, outcome(fixture.original["validated_dflash2_tuning_request"], payload, [model]))
            self.assertIn("pair changed", rejected["error"])

    def test_ane_request_keeps_existing_materializer_and_rechecks_artifact_identity(self):
        with tempfile.TemporaryDirectory(prefix="ane-planning-request-") as project, planning_environment():
            model = generated_model(project)
            model["backends"]["omlx"].update({"aneReadiness": {"ready": True},
                                              "runtimeVersion": "generated-runtime"})
            flags = {"fingerprint": "a" * 64}
            materialized = []
            def materializer(payload, models, **kwargs):
                materialized.append((copy.deepcopy(payload), copy.deepcopy(kwargs)))
                return {"opaqueExistingPlan": copy.deepcopy(payload), **copy.deepcopy(kwargs)}
            fixture = DomainFixture("benchmark_planning", callbacks={
                "omlx_version_at_least": lambda *_: True,
                "omlx_qwen_kernel_status": lambda *_: {"ready": True},
                "read_json": lambda *_: {"generated": "config"},
                "ane_quantization_profile": lambda *_: {"compatible": True},
                "ane_cpu_sharing_profile": lambda *_: {"eligible": False},
                "weight_completeness": lambda *_: (True, "ready", 1024),
                "ane_memory_readiness": lambda *args, **kwargs: {"ready": True, "reserveBytes": 1024},
                "model_artifact_fingerprint": lambda *_: flags["fingerprint"],
                "normalized_request": materializer,
            })
            payload = {"modelId": model["id"], "project": project, "cpuAssist": False}
            before = fixture.original["validated_ane_tuning_request"](payload, [model])
            current = fixture.current.validated_ane_tuning_request(payload, [model])
            self.assertEqual(current, before)
            self.assertEqual(materialized[0], materialized[1])
            self.assertEqual(materialized[1][1], {"purpose": "ane-tune"})
            self.assertEqual((materialized[1][0]["context"], materialized[1][0]["output"]), (8192, 256))
            self.assertEqual(materialized[1][0]["options"]["kv"], "off")
            flags["fingerprint"] = "b" * 64
            rejected = outcome(fixture.current.validated_ane_tuning_request, payload, [model])
            self.assertEqual(rejected, outcome(fixture.original["validated_ane_tuning_request"], payload, [model]))
            self.assertIn("checkpoint changed", rejected["error"])
            self.assertEqual(len(materialized), 2, "Changed artifacts must fail before plan materialization")

    def test_native_qualification_request_preserves_tiers_output_and_original_sampling(self):
        from tests.helpers.benchmark_planning_fixture import qualification_model
        records = json.loads((ROOT / "tests/fixtures/route_qualification_records.json").read_text())["cases"]
        with tempfile.TemporaryDirectory(prefix="qualification-request-entry-") as project, planning_environment():
            fixture = DomainFixture("benchmark_planning")
            for case in records:
                record = case["record"]
                if record["backend"] != "uzu" or record["configuredOutputLimit"] != 4096: continue
                model = qualification_model(record)
                model.update(path=project, nativeContext=262144,
                             defaultSampling={"temperature": 0.6, "top_p": 0.95})
                model["backends"]["uzu"].update(customSampling=False, implicitSamplingDefaultsVerified=True)
                payload = {"scope": "qualification", "backend": "uzu", "client": "chat",
                           "modelId": model["id"], "project": project, "context": record["contextMin"],
                           "output": 4096, "reasoning": "auto", "mode": "custom",
                           "options": {"acceleration": "off", "depth": 1, "kv": "off"},
                           "chat": {"systemPrompt": "", "sampling": "model"}}
                before = fixture.original["validated_route_qualification_request"](copy.deepcopy(payload), [copy.deepcopy(model)])
                current = fixture.current.validated_route_qualification_request(copy.deepcopy(payload), [copy.deepcopy(model)])
                self.assertEqual(current, before)
                self.assertEqual(current["job"]["context"], payload["context"])
                self.assertEqual(current["job"]["output"], 4096)
                self.assertEqual(current["job"]["speedSampling"], model["defaultSampling"])
                self.assertEqual(current["qualificationContract"]["kvStateDataType"], "BF16")


def verify_complete_bodies(test, fixture, owner_name):
    old = {node.name: node for node in ast.parse(fixture.fixture.read_text()).body if isinstance(node, ast.FunctionDef)}
    parsed = ast.parse(Path(fixture.module.__file__).read_text())
    current = {node.name: node for node in parsed.body if isinstance(node, ast.FunctionDef)}
    owner = next(node for node in parsed.body if isinstance(node, ast.ClassDef) and node.name == owner_name)
    current.update({node.name: node for node in owner.body if isinstance(node, ast.FunctionDef)})
    test.assertEqual(set(old), set(fixture.metadata["functions"]))
    for name in fixture.metadata["functions"]:
        with test.subTest(function=name):
            before = ast.Module(body=copy.deepcopy(old[name].body), type_ignores=[])
            after = Projection(fixture.metadata).visit(ast.Module(body=copy.deepcopy(current[name].body), type_ignores=[]))
            if name == "calibration_plan":
                labels = [node for node in ast.walk(after) if isinstance(node, ast.Dict)
                          and any(isinstance(key, ast.Constant) and key.value == "pi"
                                  for key in node.keys)
                          and any(isinstance(key, ast.Constant) and key.value == "omp"
                                  for key in node.keys)]
                test.assertEqual(len(labels), 1)
                index = next(index for index, key in enumerate(labels[0].keys)
                             if isinstance(key, ast.Constant) and key.value == "omp")
                test.assertEqual(ast.literal_eval(labels[0].values[index]), "oh-my-pi")
                del labels[0].keys[index]
                del labels[0].values[index]
            for body in (before.body, after.body):
                if isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                    body[0].value.value = inspect.cleandoc(body[0].value.value)
            test.assertEqual(ast.dump(before, include_attributes=False), ast.dump(after, include_attributes=False))
            arguments = lambda signature: [(value.name, value.kind, value.default) for value in signature.parameters.values()]
            test.assertEqual(arguments(inspect.signature(fixture.original[name])), arguments(inspect.signature(fixture.method(name))))


def verify_import(test, name):
    code = '''
import builtins,pathlib,subprocess,sys,urllib.request
sys.path.insert(0,sys.argv[1]);original=builtins.__import__
def guarded(name,*args,**kwargs):
 if name=='launcher':raise AssertionError('controller import')
 return original(name,*args,**kwargs)
def forbidden(*args,**kwargs):raise AssertionError('import side effect')
builtins.__import__=guarded;subprocess.Popen=forbidden;urllib.request.urlopen=forbidden
pathlib.Path.write_text=forbidden;pathlib.Path.write_bytes=forbidden
__import__(sys.argv[2]);assert 'launcher' not in sys.modules
'''
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(ROOT), name], capture_output=True, text=True, timeout=5)
    test.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__": unittest.main()
