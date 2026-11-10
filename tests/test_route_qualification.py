"""Exact route correctness, timing, physical reserve and current trust proof."""
from __future__ import annotations

import dataclasses
import copy
import json
import unittest

import launcher
from tests.helpers.benchmark_planning_fixture import DomainFixture, ROOT, qualification_model
from tests.test_benchmark_planning import verify_complete_bodies, verify_import


class RouteQualificationSourceTests(unittest.TestCase):
    def test_all14_complete_bodies_and_signatures_match_frozen(self):
        verify_complete_bodies(self, DomainFixture("route_qualification"), "RouteQualification")

    def test_import_starts_no_io_process_or_controller(self):
        verify_import(self, "route_qualification")

    def test_policy_and_scenario_lists_are_detached(self):
        fixture = DomainFixture("route_qualification")
        self.assertEqual(fixture.policy.input_values(), fixture.raw_policy_values)
        with self.assertRaises(dataclasses.FrozenInstanceError): fixture.policy.uzu_process_memory_ceiling_bytes = 1
        with self.assertRaises(TypeError): fixture.policy.route_qualification_scenarios.append("fake")
        with self.assertRaises(TypeError): fixture.policy.route_qualification_uzu_suites_by_context[8192] = "fake"


class RouteQualificationDecisionTests(unittest.TestCase):
    def records(self):
        return json.loads((ROOT / "tests/fixtures/route_qualification_records.json").read_text())

    def compare(self, fixture, name, *args, **kwargs):
        before = fixture.original[name](*copy.deepcopy(args), **copy.deepcopy(kwargs))
        current = fixture.method(name)(*copy.deepcopy(args), **copy.deepcopy(kwargs))
        self.assertEqual(current, before)
        return current

    def test_all15_complete_valid_original_contract_records_match(self):
        fixture = DomainFixture("route_qualification")
        records = self.records()
        self.assertEqual(records["fixtureSha256"], fixture.metadata["fixtureSha256"])
        self.assertEqual(len(records["cases"]), 15)
        for case in records["cases"]:
            record, spec = case["record"], case["spec"]
            with self.subTest(backend=record["backend"], context=record["contextMin"],
                              output=record.get("configuredOutputLimit")):
                current = self.compare(fixture, "route_qualification_metrics", record, spec)
                self.assertEqual(current, case["metrics"])
                self.assertEqual(current["completionTokens"], sum(
                    sample["completionTokens"] for sample in record["modes"]["ar"]["samples"]))
                self.assertEqual(current["promptTokens"], sum(
                    sample["promptTokens"] for sample in record["modes"]["ar"]["samples"]))
                model = qualification_model(record)
                described = self.compare(fixture, "route_qualification_spec", model,
                                         record["backend"], record["contextMin"])
                self.assertEqual(described, spec)
                self.compare(fixture, "public_route_qualification_result", model, record)

    def test_malformed_samples_cannot_create_authoritative_tokens_timing_or_completion(self):
        fixture = DomainFixture("route_qualification")
        mutations = [
            ("promptTokens", True), ("promptTokens", 0),
            ("completionTokens", True), ("completionTokens", 0),
            ("decodeTokensPerSecond", float("nan")), ("decodeTokensPerSecond", float("inf")),
            ("decodeTokensPerSecond", 0), ("ttftSeconds", float("nan")),
            ("ttftSeconds", 0), ("totalSeconds", 0),
            ("finishReason", "length"), ("terminalState", "aborted"),
            ("terminalComplete", False), ("responseLimitReached", True),
        ]
        for case in self.records()["cases"]:
            for field, value in mutations:
                record = copy.deepcopy(case["record"])
                record["modes"]["ar"]["samples"][0][field] = value
                with self.subTest(backend=record["backend"], field=field, value=repr(value)):
                    self.assertIsNone(self.compare(fixture, "route_qualification_metrics", record, case["spec"]))

    def test_quality_original_precision_runtime_and_unload_proofs_never_weaken(self):
        fixture = DomainFixture("route_qualification")
        mutations = [
            ("correctnessContract", "exact", False),
            ("correctnessContract", "authoritativeUsage", False),
            ("correctnessContract", "observedAnswerSha256", "0" * 64),
            ("unloadEvidence", "clean", False),
            ("unloadEvidence", "processGroupExited", False),
            ("unloadEvidence", "portsClosed", False),
            ("unloadEvidence", "closedPorts", []),
        ]
        for case in self.records()["cases"]:
            if case["record"]["backend"] not in {"llamacpp", "uzu"}:
                continue
            for section, field, value in mutations:
                record = copy.deepcopy(case["record"])
                record[section][field] = value
                with self.subTest(backend=record["backend"], section=section, field=field):
                    self.assertIsNone(self.compare(fixture, "route_qualification_metrics", record, case["spec"]))
            if case["record"]["backend"] == "uzu":
                for field, value in (("kvStateDataType", "q8"), ("runtimeBinarySha256", "0" * 64),
                                     ("nativeContextLimitTokens", 8192), ("nativeMaxOutputTokens", 256),
                                     ("memoryCeilingBytes", 100 * 1024**3), ("osReserveBytes", 0)):
                    record = copy.deepcopy(case["record"])
                    record["qualificationContract"][field] = value
                    self.assertIsNone(self.compare(fixture, "route_qualification_metrics", record, case["spec"]))

    def test_physical_reserve_and_128k_prompt_exercise_remain_strict(self):
        fixture = DomainFixture("route_qualification")
        for case in self.records()["cases"]:
            if case["record"]["backend"] != "uzu":
                continue
            for field, value in (("memorySemanticsVersion", 1), ("memorySource", "memory_pressure -Q"),
                                 ("memorySampleCount", 7), ("minimumHeadroomBytes", 1),
                                 ("peakProcessGroupPhysicalFootprintBytes", launcher.UZU_PROCESS_MEMORY_CEILING_BYTES),
                                 ("samplingComplete", False)):
                record = copy.deepcopy(case["record"])
                record["modes"]["ar"]["resourceTelemetry"][field] = value
                with self.subTest(context=record["contextMin"], field=field):
                    self.assertIsNone(self.compare(fixture, "route_qualification_metrics", record, case["spec"]))
            if case["record"]["contextMin"] >= 65536:
                for scenario in launcher.UZU_QUALIFICATION_NEAR_TIER_SCENARIOS:
                    record = copy.deepcopy(case["record"])
                    sample = next(sample for sample in record["modes"]["ar"]["samples"] if sample["scenario"] == scenario)
                    sample["authoritativeUsage"] = False
                    self.assertIsNone(self.compare(fixture, "route_qualification_metrics", record, case["spec"]))
                    sample["authoritativeUsage"] = True
                    sample["promptTokens"] = 1024
                    self.assertIsNone(self.compare(fixture, "route_qualification_metrics", record, case["spec"]))

    def test_saved_receipts_recheck_live_trust_freshness_and_current_capability(self):
        flags = {"trusted": True, "fresh": True}
        calls = {"trusted": 0, "fresh": 0}
        def trusted(*args): calls["trusted"] += 1; return flags["trusted"]
        def fresh(*args): calls["fresh"] += 1; return flags["fresh"]
        fixture = DomainFixture("route_qualification", callbacks={
            "_local_benchmark_record_verified": trusted,
            "route_qualification_record_is_fresh": fresh,
        })
        for case in self.records()["cases"]:
            record = case["record"]
            if record.get("qualification") is None:
                continue
            model = qualification_model(record)
            evidence = {"context": record["contextMin"]}
            flags.update(trusted=True, fresh=True)
            selected = self.compare(fixture, "verified_route_qualification", model, record["backend"], evidence)
            self.assertEqual(selected, record)
            flags["trusted"] = False
            self.assertIsNone(self.compare(fixture, "verified_route_qualification", model, record["backend"], evidence))
            flags.update(trusted=True, fresh=False)
            self.assertIsNone(self.compare(fixture, "verified_route_qualification", model, record["backend"], evidence))
            flags.update(trusted=True, fresh=True)
            model["backends"][record["backend"]]["runnable"] = False
            self.assertIsNone(self.compare(fixture, "verified_route_qualification", model, record["backend"], evidence))
        self.assertGreater(calls["trusted"], 0)
        self.assertGreater(calls["fresh"], 0)

    def test_contract_budgets_resample_memory_and_preserve_selected_limits(self):
        memory = [48 * 1024**3]
        fixture = DomainFixture("route_qualification", callbacks={
            "physical_memory_bytes": lambda: memory[0],
        })
        for case in self.records()["cases"]:
            record = case["record"]
            if record["backend"] != "uzu": continue
            model = qualification_model(record)
            request = {"context": record["contextMin"], "output": record["configuredOutputLimit"],
                       "reasoning": "auto", "client": "chat"}
            contract = self.compare(fixture, "build_route_qualification_contract", case["spec"], request,
                                    model["backends"]["uzu"])
            self.assertEqual(contract["nativeContextLimitTokens"], request["context"])
            self.assertEqual(contract["nativeMaxOutputTokens"], request["output"])
            self.assertEqual(contract["kvStateDataType"], "BF16")
            memory[0] = 96 * 1024**3
            changed = self.compare(fixture, "build_route_qualification_contract", case["spec"], request,
                                   model["backends"]["uzu"])
            self.assertGreater(changed["osReserveBytes"], contract["osReserveBytes"])
            memory[0] = 48 * 1024**3
            job = {"backend": "uzu", "output": request["output"], "suite": {}}
            before = copy.deepcopy(job)
            fixture.original["apply_route_qualification_budget"](before)
            fixture.current.apply_route_qualification_budget(job)
            self.assertEqual(job, before)
            self.assertEqual(job["output"], request["output"])


if __name__ == "__main__": unittest.main()
