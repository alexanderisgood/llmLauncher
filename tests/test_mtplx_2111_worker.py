from __future__ import annotations
from tests.memory_fixtures import physical_snapshot, physical_telemetry

import copy
import importlib.util
import math
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "llm_launcher_mtplx_2111_worker_tests", ROOT / "launcher.py",
)
assert SPEC and SPEC.loader
launcher = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = launcher
SPEC.loader.exec_module(launcher)


class MTPLX2111WorkerTests(unittest.TestCase):
    """Model-free end-to-end checks for the fixed MTPLX operator sweep."""

    MACHINE = "mtplx-2111-worker-test-mac"
    RUNTIME = "mtplx 2.11.1 (2.11.1)"
    DEFAULT = launcher.MTPLX_LONG_CONTEXT_DEFAULT_ROUTE
    CANDIDATE = launcher.MTPLX_LONG_CONTEXT_2111_ROUTE

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="mtplx-2111-worker-")
        self.root = Path(self.temp.name)
        self.model_path = self.root / "Qwen3.8-27B-MLX-6bit"
        self.model_path.mkdir(parents=True)
        self.config = {
            "model_type": "qwen3_5",
            "text_config": {
                "model_type": "qwen3_5_text",
                "num_hidden_layers": 64,
                "vocab_size": 248_320,
                "hidden_size": 5_120,
                "intermediate_size": 17_408,
            },
        }
        launcher.atomic_json(self.model_path / "config.json", self.config)
        fingerprint = launcher.model_artifact_fingerprint(
            self.model_path, self.config,
        )
        capability = {
            "runnable": True,
            "reason": "Verified test route",
            "runtimeVersion": self.RUNTIME,
            "benchmarkModelFingerprint": fingerprint,
            "mtp": True,
            "mtpReason": "Verified integrated MTP tensors",
            "kv": True,
            "profile": "turbo",
            "depth": 3,
            "depthMax": 3,
            "contextMaximum": 262_144,
            "contextWindows": [65_536, 131_072, 262_144],
            "agentReasoning": ["auto"],
            "implicitSamplingDefaultsVerified": True,
            "customSampling": True,
            "localBenchmarks": [],
        }
        self.model = {
            "id": "qwen38-dense-27b-worker",
            "name": "Qwen3.8-27B-MLX-6bit",
            "path": str(self.model_path),
            "artifact": str(self.model_path),
            "format": "mlx",
            "architecture": "Qwen3_8ForConditionalGeneration",
            "modelType": "qwen3_8",
            "parameterCount": 27_000_000_000,
            "mixtureOfExperts": False,
            "nativeContext": 262_144,
            "quantization": "6-bit",
            "ready": True,
            "defaultSampling": {
                "temperature": 1.0,
                "top_p": 0.95,
                "top_k": 20,
            },
            "backends": {"mtplx": capability},
        }
        receipt = launcher.mtplx_long_context_2111_contract(
            self.model, capability, runtime_version=self.RUNTIME,
        )
        self.assertIsInstance(receipt, dict)
        self.receipt = receipt
        capability["longContext2111"] = launcher._mtplx_long_context_capability(
            receipt, self.RUNTIME,
        )
        self.options = {
            "acceleration": "auto",
            "depth": 3,
            "kv": "off",
            "profile": "turbo",
            "mtplxOperatorRoute": self.DEFAULT,
            "fan": "default",
        }
        self.job = self._job()

    def tearDown(self) -> None:
        self.temp.cleanup()

    @property
    def capability(self) -> dict:
        return self.model["backends"]["mtplx"]

    def _job(self) -> dict:
        sampling = launcher.build_sampling_contract(
            "model", model_defaults=self.model["defaultSampling"],
        ).as_dict()
        evidence = launcher.optimizer_evidence(
            self.model, 65_536, 1_024, "chat", "auto", "off",
            {"sampling": "model"}, sampling,
        )
        launcher.add_benchmark_engine_evidence(
            evidence, self.model, self.options, ["mtplx"],
        )
        job = {
            "id": "mtplx-2111-worker-record",
            "backend": "mtplx",
            "client": "chat",
            "modelId": self.model["id"],
            "model": copy.deepcopy(self.model),
            "project": str(self.root),
            "context": 65_536,
            "output": 1_024,
            "reasoning": "auto",
            "options": copy.deepcopy(self.options),
            "chat": {"systemPrompt": "", "sampling": "model"},
            "samplingContract": sampling,
            "suiteName": "agentic",
            "suite": copy.deepcopy(launcher.BENCHMARK_SUITES["agentic"]),
            "workloadKind": "agentic",
            "modes": ["ar", "mtp"],
            "evidence": evidence,
            "modelFingerprint": self.capability["benchmarkModelFingerprint"],
            "runtimeVersion": self.RUNTIME,
            "pairFingerprint": None,
            "ssdStreaming": False,
            "ssdComparisonIdentity": "",
            "speedSampling": {
                "temperature": 1.0, "top_p": 0.95, "top_k": 20,
            },
            "shootoutId": "mtplx-2111-shootout",
            "shootoutExecutionOrder": ["mtplx"],
            "shootoutOrderIndex": 0,
            "shootoutOrderStrategy": "single-engine",
        }
        launcher.prepare_calibration_tuning_plan(job)
        self.assertEqual(
            job["suiteName"], launcher.MTPLX_LONG_CONTEXT_64K_SUITE,
        )
        return job

    @staticmethod
    def _agentic_metrics() -> dict:
        return {
            "coldTTFTSeconds": 0.2,
            "warmPrefixTTFTSeconds": 0.2,
            "prefixReuseFactor": 1.0,
            "toolIngestTTFTSeconds": 0.2,
            "steadyTurnTTFTSeconds": 0.2,
            "toolReuseFactor": 1.0,
            "warmCachedPromptTokens": None,
            "steadyCachedPromptTokens": None,
            "warmCacheHitRate": None,
            "steadyCacheHitRate": None,
            "cacheTelemetryAvailable": False,
        }

    def _result(
        self,
        *,
        speeds: list[float],
        quality: str = "a",
        route: str | None = None,
    ) -> dict:
        self.assertEqual(len(speeds), len(launcher.ROUTE_QUALIFICATION_SCENARIOS))
        samples = []
        for index, (scenario, speed) in enumerate(zip(
            launcher.ROUTE_QUALIFICATION_SCENARIOS, speeds,
        )):
            prompt_tokens = 61_440 if scenario in {"toolIngest", "steadyTurn"} else 49_152
            total_seconds = round(63.0 / speed + 0.2, 6)
            samples.append({
                "scenario": scenario,
                "scenarioLabel": scenario,
                "cacheExpected": index > 0,
                "targetPromptTokens": prompt_tokens,
                "repetition": 1,
                "promptTokens": prompt_tokens,
                "completionTokens": 64,
                "requestedMaxTokens": 256,
                "authoritativeUsage": True,
                "ttftSeconds": 0.2,
                "totalSeconds": total_seconds,
                "decodeTokensPerSecond": speed,
                "endToEndTokensPerSecond": round(
                    64.0 / total_seconds, 6,
                ),
                "outputHash": f"sample-{index}",
            })
        settings = (
            {} if route is None else
            {"depth": 3, "mtplxOperatorRoute": route}
        )
        return {
            "label": "AR" if route is None else "MTP",
            "settings": settings,
            "qualityHash": quality * 64,
            "qualityCompletionTokens": 64,
            "medianTTFT": round(0.2, 4),
            "medianDecodeTokensPerSecond": round(
                float(sorted(speeds)[len(speeds) // 2]), 3,
            ),
            "medianEndToEndTokensPerSecond": round(float(sorted(
                sample["endToEndTokensPerSecond"] for sample in samples
            )[len(samples) // 2]), 3),
            "agenticMetrics": self._agentic_metrics(),
            "samples": samples,
        }

    def _manager(self) -> launcher.BenchmarkManager:
        run = mock.Mock(plan=None, llamacpp_safety_violation=None,
                        codex_proxy_port=None, session_proxy_port=None)
        run.lock = threading.RLock()
        run.lifecycle_lock = threading.Lock()
        run.cancel_event = threading.Event()
        manager = launcher.BenchmarkManager(run)
        manager.cancel_event = threading.Event()
        manager.state = {
            "phase": "queued",
            "message": "queued",
            "progress": 0.0,
            "job": {"kind": "engine-shootout"},
            "modes": {},
            "result": None,
            "events": [],
            "engines": {
                "mtplx": {
                    "backend": "mtplx",
                    "label": launcher.BACKEND_LABELS["mtplx"],
                    "phase": "queued",
                    "modes": {},
                    "record": None,
                },
            },
        }
        return manager

    def test_live_system_reserve_checks_debounce_and_reject_unreadable_memory(self):
        healthy = physical_snapshot({"memoryAvailable": True, "totalBytes": 48 * 1024**3, "freePercent": 25.0})
        low = physical_snapshot({**healthy, "freePercent": 9.0})
        counters = {}
        check = lambda sample: launcher.benchmark_system_memory_violation(sample, counters, "MTPLX test")
        self.assertIsNone(check(low))
        self.assertIsNone(check(healthy))
        self.assertIsNone(check(low))
        self.assertIn("protected macOS reserve", check(low))
        for invalid in ({}, physical_snapshot({**healthy, "freePercent": float("nan")}),
                        physical_snapshot({**healthy, "freePercent": True}), {**healthy, "totalBytes": True}):
            counters.clear()
            self.assertIsNone(check(invalid))
            self.assertIsNone(check(invalid))
            self.assertIn("unreadable", check(invalid))
        counters.clear()
        self.assertIsNone(check(physical_snapshot({**healthy, "freePercent": 10.0})))
        self.assertIsNone(check(physical_snapshot({**healthy, "freePercent": 10.0})))
        small = physical_snapshot({**healthy, "totalBytes": 16 * 1024**3, "freePercent": 20.0})
        self.assertIsNone(check(small))
        self.assertIn("protected macOS reserve", check(small))

    def test_long_context_live_memory_failure_stops_ar_and_mtp_without_saving(self):
        for mode, interrupted in (("ar", False), ("mtp", False), ("ar", True), ("mtp", True)):
            with self.subTest(mode=mode, interrupted=interrupted):
                job = self._job()
                launcher.prepare_calibration_tuning_plan(job)
                if interrupted:
                    # Timing continuity applies to ordinary benchmarks too,
                    # not only the strict long-context qualification route.
                    job["suiteName"] = "agentic"
                manager = self._manager()
                manager.run_manager.llamacpp_safety_violation = None
                manager.run_manager.process.poll.return_value = None
                manager.run_manager.process.pid = 12345
                sampler = mock.Mock(violation=None)
                sampler.stop.return_value = {}
                callback = None

                def make_sampler(**kwargs):
                    nonlocal callback
                    callback = kwargs["invariant_callback"]
                    return sampler

                def loading(_plan):
                    if interrupted:
                        callback({"timingDiscontinuity": "The Mac slept during measurement."})
                        return
                    low = physical_snapshot({"memoryAvailable": True, "totalBytes": 48 * 1024**3, "freePercent": 8.0})
                    callback(low)
                    callback(low)

                plan = mock.Mock(port=1234, client_port=1235)
                def accept(p):
                    manager.run_manager.plan = p
                    manager.run_manager.cancel_event = threading.Event()
                manager.run_manager.start.side_effect = accept
                with (
                    mock.patch.object(manager, "_mode_payload", return_value={}),
                    mock.patch.object(launcher, "normalized_request", return_value=plan),
                    mock.patch.object(launcher, "require_live_model_load_admission", return_value={}),
                    mock.patch.object(launcher, "BenchmarkTelemetrySampler", side_effect=make_sampler),
                    mock.patch.object(manager, "_wait_for_engine", side_effect=loading),
                    mock.patch.object(launcher.threading, "Thread") as stopping,
                    mock.patch.object(launcher.os, "getpgid", return_value=12345),
                    mock.patch.object(launcher, "benchmark_clean_unload_evidence", return_value={}),
                    mock.patch.object(launcher, "run_benchmark_completion") as completion,
                ):
                    with self.assertRaisesRegex(launcher.QualificationSafetyFailure,
                                                "Mac slept" if interrupted else "protected macOS reserve"):
                        manager._measure_mode(job, [self.model], mode, 0, 18)
                completion.assert_not_called()
                stopping.assert_called_once_with(target=manager.owner.stop,
                                                kwargs={"expected_plan":plan}, daemon=True)
                manager.run_manager.stop.assert_called_once_with(expected_plan=plan,
                    expected_cancel_event=manager.run_manager.cancel_event)
                self.assertIsNone(manager.state["result"])
                self.assertIsNone(manager.active_plan)

    def test_candidate_memory_admission_allows_measurement_not_unqualified_launch(self):
        request = self._manager()._mode_payload(self.job, "mtp")
        request["options"]["mtplxOperatorRoute"] = self.CANDIDATE
        # Caller-supplied flags are not authority to bypass a normal launch.
        request["allow_unmeasured_mtplx_operator"] = True
        request["purpose"] = "benchmark"
        resource = physical_snapshot({"memoryAvailable": True, "totalBytes": 48 * 1024**3,
                    "freePercent": 80.0})
        estimate = {"geometryReady": True, "estimatedWorkingSetBytes": 28 * 1024**3,
                    "requiredHeadroomBytes": 33 * 1024**3}
        with (
            mock.patch.dict(launcher.BINARIES, {"mtplx": "/test/mtplx"}),
            mock.patch.object(launcher, "_revalidated_mtplx_long_context_receipt", return_value=self.receipt) as binding,
            mock.patch.object(launcher.resource_admission.ResourceAdmission,
                              "launch_memory_estimate", return_value=estimate) as capacity,
        ):
            with self.assertRaisesRegex(ValueError, "matching completed Calibration"):
                launcher.session_memory_admission(
                    request, [self.model], launcher.public_session_resource(resource),
                    {"phase":"idle"}, {"active":False},
                )
            for purpose in ("session-set", "route-check", "runtime-promotion"):
                with self.subTest(purpose=purpose), self.assertRaisesRegex(ValueError, "matching completed Calibration"):
                    launcher.require_live_model_load_admission(
                        request, [self.model], purpose=purpose, resource_snapshot=resource,
                        hub={"phase":"idle"}, operation={"active":False},
                    )
            admission = launcher.require_live_model_load_admission(
                request, [self.model], purpose="benchmark", resource_snapshot=resource,
                hub={"phase":"idle"}, operation={"active":False},
            )
            self.assertEqual(admission["decision"], "ready")
            self.assertEqual(admission["request"]["options"]["mtplxOperatorRoute"], self.CANDIDATE)
            self.assertEqual(capacity.call_args.args[0]["options"]["mtplxOperatorRoute"], self.CANDIDATE)
            binding.assert_called()
            with self.assertRaisesRegex(RuntimeError, "Capacity changed"):
                launcher.require_live_model_load_admission(
                    request, [self.model], purpose="benchmark",
                    resource_snapshot=physical_snapshot({**resource, "freePercent":10.0}),
                    hub={"phase":"idle"}, operation={"active":False},
                )
            binding.return_value = None
            with self.assertRaisesRegex(ValueError, "receipt changed"):
                launcher.require_live_model_load_admission(
                    request, [self.model], purpose="benchmark", resource_snapshot=resource,
                    hub={"phase":"idle"}, operation={"active":False},
                )

    def _run_worker(
        self,
        *,
        ar_speeds: list[float] | None = None,
        default_speeds: list[float],
        candidate_speeds: list[float],
        candidate_quality: str = "a",
        default_quality: str = "a",
        finalizer=None,
        commit_order: list[str] | None = None,
        current_engine: bool = False,
    ) -> tuple[launcher.BenchmarkManager, dict, list[tuple]]:
        manager = self._manager()
        measured = {
            None: self._result(
                speeds=ar_speeds if ar_speeds is not None else [80.0] * 4,
            ),
            self.DEFAULT: self._result(
                speeds=default_speeds, quality=default_quality, route=self.DEFAULT,
            ),
            self.CANDIDATE: self._result(
                speeds=candidate_speeds,
                quality=candidate_quality,
                route=self.CANDIDATE,
            ),
        }
        calls: list[tuple] = []

        def measure(job, _models, mode, completed, _total, gate, **kwargs):
            route = job.get("_benchmarkMtplxOperatorRoute") if mode == "mtp" else None
            payload_options = manager._mode_payload(job, mode)["options"]
            calls.append((
                mode, route, kwargs.get("display_label"), kwargs.get("state_key"),
                copy.deepcopy(payload_options),
            ))
            result = copy.deepcopy(measured[route])
            result["resourceTelemetry"] = physical_telemetry({
                "version": 1,
                "sampleCount": 3,
                "memoryAvailable": True,
                "totalMemoryBytes": 64 * 1024**3,
                "baselineHeadroomPercent": 50.0,
                "peakPressureDeltaBytes": 3 * 1024**3,
                "minimumHeadroomPercent": 45.0,
                "thermalAvailable": True,
                "thermalStartValue": 0,
                "thermalStart": "nominal",
                "thermalWorstValue": 0,
                "thermalWorst": "nominal",
                "lowPowerMode": False,
            })
            result["resourceCooldown"] = {
                key: copy.deepcopy(value)
                for key, value in gate.items()
                if key != "_initialSnapshot"
            }
            return result, completed + 6

        reference = {"memoryAvailable": True, "freePercent": 50.0}
        gates = [
            {
                "version": 1, "status": "reference-ready",
                "reference": reference, "observed": reference,
            },
            {
                "version": 1, "status": "ready",
                "reference": reference, "observed": reference,
            },
            {
                "version": 1, "status": "ready",
                "reference": reference, "observed": reference,
            },
        ]
        shootout = {
            "id": "mtplx-2111-shootout",
            "jobs": [copy.deepcopy(self.job)],
        }
        saved_records: list[dict] = []

        def save(records):
            if commit_order is not None:
                commit_order.append("saved")
            saved_records.extend(copy.deepcopy(records))

        if finalizer is None:
            finalizer = lambda _shootout, _records, _models: {  # noqa: E731
                "recommendation": "MTPLX test matrix complete",
            }
        with (
            mock.patch.object(
                manager, "_wait_for_resource_baseline", side_effect=gates,
            ),
            mock.patch.object(manager, "_measure_mode", side_effect=measure),
            mock.patch.object(manager, "_build_shootout_result", side_effect=finalizer),
            mock.patch.object(launcher, "hardware_fingerprint", return_value=self.MACHINE),
            mock.patch.object(launcher, "save_benchmark_records", side_effect=save),
        ):
            if current_engine:
                job = copy.deepcopy(self.job)
                for key in list(job):
                    if key.startswith("shootout"):
                        del job[key]
                manager._worker(job, [self.model])
            else:
                manager._shootout_worker(shootout, [self.model])
        self.assertLessEqual(len(saved_records), 1)
        return manager, (saved_records[0] if saved_records else {}), calls

    def test_configured_16k_reply_ceiling_does_not_overflow_256_token_measurements(self):
        self.job["output"] = 16384
        self.job["evidence"]["output"] = 16384
        manager, record, _ = self._run_worker(
            default_speeds=[100.0] * 4, candidate_speeds=[120.0] * 4,
            current_engine=True,
        )
        self.assertEqual(manager.state["phase"], "completed")
        self.assertEqual(record["outputMax"], 16384)
        sample = record["modes"]["mtp"]["samples"][2]
        self.assertEqual(sample["requestedMaxTokens"], 256)
        self.assertGreater(sample["promptTokens"] + record["outputMax"], 65536)
        self.assertLess(sample["promptTokens"] + sample["requestedMaxTokens"], 65536)

    def test_current_engine_worker_runs_all_three_operator_routes_and_saves(self):
        manager, record, calls = self._run_worker(
            default_speeds=[100.0] * 4, candidate_speeds=[120.0] * 4,
            current_engine=True,
        )
        self.assertEqual(manager.state["phase"], "completed")
        self.assertEqual([call[1] for call in calls], [None, self.DEFAULT, self.CANDIDATE])
        self.assertEqual(record["kind"], "mtplx-long-context-operator-tuning")
        self.assertTrue(record["mtplxOperatorSweep"]["candidateAccepted"])
        self.assertEqual(manager.state["result"], record)
        self.assertFalse(record.get("shootoutId"))
        self.assertEqual(record["selectionPreference"], "throughput")
        mislabeled = copy.deepcopy(record)
        mislabeled["selectionPreference"] = "fastest"
        self.assertTrue(launcher.benchmark_record_matches_selection_preference(mislabeled, "throughput"))
        self.assertFalse(launcher.benchmark_record_matches_selection_preference(mislabeled, "fastest"))
        self.assertTrue(launcher.mtplx_operator_sweep_verified(
            self.capability, mislabeled, mislabeled["modeSettings"]))
        for changes in ({"shootoutId":"matrix"}, {"kind":"ordinary"},
                        {"suite":"quick"}, {"selectionMetric":"end-to-end-tokens-per-second"}):
            self.assertFalse(launcher.benchmark_record_matches_selection_preference(
                {**mislabeled, **changes}, "throughput"))
        old = copy.deepcopy(mislabeled)
        old["mtplxOperatorSweep"]["version"] = 4
        self.assertFalse(launcher.benchmark_record_matches_selection_preference(old, "throughput"))

    def test_operator_measurement_requires_exact_actual_request_allowance(self):
        _, record, _ = self._run_worker(
            default_speeds=[100.0] * 4, candidate_speeds=[120.0] * 4,
            current_engine=True,
        )
        measurement = record["mtplxOperatorSweep"]["arMeasurement"]
        self.assertIsNotNone(launcher._mtplx_operator_measurement_verified(measurement))
        for value in (None, True, 0, 255, 257, 16384, "256", 256.0):
            with self.subTest(requested=value):
                altered = copy.deepcopy(measurement)
                if value is None:
                    altered["samples"][2].pop("requestedMaxTokens")
                else:
                    altered["samples"][2]["requestedMaxTokens"] = value
                self.assertIsNone(launcher._mtplx_operator_measurement_verified(altered))
        altered = copy.deepcopy(measurement)
        altered["samples"][2]["completionTokens"] = 257
        self.assertIsNone(launcher._mtplx_operator_measurement_verified(altered))

    def test_current_engine_worker_rejects_candidate_with_different_output(self):
        manager, record, calls = self._run_worker(
            default_speeds=[100.0] * 4, candidate_speeds=[120.0] * 4,
            candidate_quality="b", current_engine=True,
        )
        self.assertEqual(manager.state["phase"], "completed")
        self.assertEqual(len(calls), 3)
        self.assertFalse(record["mtplxOperatorSweep"]["candidateAccepted"])
        self.assertEqual(record["mtplxOperatorSweep"]["selectedRoute"], self.DEFAULT)

    def test_faster_mismatching_mtp_is_explained_as_parity_failure_not_speed_failure(self):
        manager, record, _ = self._run_worker(
            ar_speeds=[10.0] * 4, default_speeds=[21.0] * 4,
            candidate_speeds=[25.0] * 4, default_quality="b", candidate_quality="c",
            current_engine=True,
        )
        self.assertEqual(manager.state["phase"], "completed")
        self.assertEqual(record["winner"], "ar")
        self.assertIn("did not exactly match", record["recommendation"])
        self.assertNotIn("did not beat AR", record["recommendation"])

    def test_current_engine_start_prepares_and_discloses_only_eligible_turbo_sweep(self):
        for profile in ("turbo", "sustained"):
            with self.subTest(profile=profile):
                job = copy.deepcopy(self.job)
                job.pop("calibrationTuningPlan", None)
                job["suiteName"] = "agentic"
                job["suite"] = copy.deepcopy(launcher.BENCHMARK_SUITES["agentic"])
                job["options"]["profile"] = profile
                manager = self._manager()
                manager.state["phase"] = "idle"
                manager.run_manager.snapshot.return_value = {"phase": "idle"}
                with (
                    mock.patch.object(launcher, "validated_benchmark_request", return_value=job),
                    mock.patch.object(launcher.threading, "Thread") as thread,
                ):
                    public = manager.start({"scope": "current"}, [self.model])
                queued = thread.call_args.kwargs["args"][0]
                self.assertEqual(queued["options"]["profile"], profile)
                self.assertEqual(queued["options"]["fan"], self.options["fan"])
                if profile == "turbo":
                    self.assertEqual(public["measurementRouteCount"], 3)
                    self.assertEqual(len(public["measurementRoutes"]), 3)
                    self.assertEqual(public["suite"], launcher.MTPLX_LONG_CONTEXT_64K_SUITE)
                else:
                    self.assertNotIn("calibrationTuningPlan", queued)
                    self.assertEqual(public["suite"], "agentic")

    def _generic_cross_engine_fixture(
        self, *, fan: str = "default", omlx_speed: float = 90.0,
        mtplx_speed: float = 70.0,
    ) -> tuple[dict, dict]:
        model = copy.deepcopy(self.model)
        model["backends"]["omlx"] = {
            "runnable": True,
            "reason": "Verified model-free oMLX route",
            "runtimeVersion": "omlx test runtime",
            "benchmarkModelFingerprint": self.capability[
                "benchmarkModelFingerprint"
            ],
            "mtp": True,
            "mtpReason": "Verified model-free MTP tensors",
            "dflash": False,
            "kv": True,
            "depth": 3,
            "depthMax": 3,
            "agentReasoning": ["auto"],
            "implicitSamplingDefaultsVerified": True,
            "customSampling": True,
            "localBenchmarks": [],
        }
        payload = {
            "backend": "omlx",
            "client": "chat",
            "modelId": model["id"],
            "project": str(self.root),
            "context": 16_384,
            "output": 1_024,
            "reasoning": "auto",
            "options": {
                "acceleration": "auto",
                "depth": 3,
                "kv": "off",
                "burst": "balanced",
                "anePrefill": "off",
                "memoryGuard": "balanced",
                "profile": "turbo",
                "fan": fan,
                "mtplxOperatorRoute": self.DEFAULT,
            },
            "chat": {"systemPrompt": "", "sampling": "model"},
            "enginePreference": "throughput",
        }
        sampling = launcher.build_sampling_contract(
            "model", model_defaults=model["defaultSampling"],
        ).as_dict()
        evidence = launcher.optimizer_evidence(
            model, payload["context"], payload["output"], "chat", "auto",
            "off", payload["chat"], sampling,
        )
        launcher.add_benchmark_engine_evidence(
            evidence, model, payload["options"], ["omlx", "mtplx"],
        )

        def measured(speed: float, label: str, settings: dict) -> dict:
            samples = []
            for target in (512, 2_048):
                total = round(63.0 / speed + 0.2, 6)
                samples.append({
                    "targetPromptTokens": target,
                    "repetition": 1,
                    "promptTokens": target,
                    "completionTokens": 64,
                    "authoritativeUsage": True,
                    "ttftSeconds": 0.2,
                    "totalSeconds": total,
                    "decodeTokensPerSecond": speed,
                    "endToEndTokensPerSecond": round(64.0 / total, 6),
                })
            return {
                "label": label,
                "settings": copy.deepcopy(settings),
                "qualityHash": "a" * 64,
                "qualityCompletionTokens": 64,
                "medianTTFT": 0.2,
                "medianDecodeTokensPerSecond": speed,
                "medianEndToEndTokensPerSecond": round(
                    sum(
                        sample["endToEndTokensPerSecond"]
                        for sample in samples
                    ) / len(samples),
                    3,
                ),
                "samples": samples,
            }

        records: dict[str, dict] = {}
        with mock.patch.object(
            launcher, "hardware_fingerprint", return_value=self.MACHINE,
        ):
            for backend, speed in (
                ("omlx", omlx_speed), ("mtplx", mtplx_speed),
            ):
                job_evidence = copy.deepcopy(evidence)
                job_evidence["engineSettings"] = copy.deepcopy(
                    evidence["engineSettingsByBackend"][backend]
                )
                job = {
                    "id": f"profile-{fan}-{backend}-record",
                    "backend": backend,
                    "client": "chat",
                    "modelId": model["id"],
                    "model": copy.deepcopy(model),
                    "context": payload["context"],
                    "output": payload["output"],
                    "reasoning": "auto",
                    "options": copy.deepcopy(payload["options"]),
                    "suiteName": "quick",
                    "suite": copy.deepcopy(launcher.BENCHMARK_SUITES["quick"]),
                    "workloadKind": "throughput",
                    "enginePreference": payload["enginePreference"],
                    "modes": ["ar", "mtp"],
                    "evidence": job_evidence,
                    "modelFingerprint": model["backends"][backend][
                        "benchmarkModelFingerprint"
                    ],
                    "runtimeVersion": model["backends"][backend][
                        "runtimeVersion"
                    ],
                    "pairFingerprint": None,
                    "ssdStreaming": False,
                    "ssdComparisonIdentity": "",
                    "shootoutId": f"profile-{fan}-shootout",
                    "shootoutExecutionOrder": ["omlx", "mtplx"],
                    "shootoutOrderIndex": 0 if backend == "omlx" else 1,
                    "shootoutOrderStrategy": "alternating",
                }
                records[backend] = launcher.BenchmarkManager(
                    mock.Mock(),
                )._build_record(
                    job,
                    {
                        "ar": measured(50.0, "AR", {}),
                        "mtp": measured(speed, "MTP", {"depth": 3}),
                    },
                )
        for backend, record in records.items():
            capability = model["backends"][backend]
            capability["localBenchmark"] = copy.deepcopy(record)
            capability["localBenchmarks"] = [copy.deepcopy(record)]
        return model, payload

    def test_routes_run_once_in_exact_ar_default_candidate_order(self) -> None:
        routes = launcher.benchmark_job_measurement_routes(self.job)
        self.assertEqual(
            [(item["mode"], item.get("operatorRoute")) for item in routes],
            [("ar", None), ("mtp", self.DEFAULT), ("mtp", self.CANDIDATE)],
        )

        manager, record, calls = self._run_worker(
            default_speeds=[100.0] * 4,
            candidate_speeds=[104.0] * 4,
        )
        self.assertEqual(manager.snapshot()["phase"], "completed")
        self.assertTrue(record)
        self.assertEqual(
            [(mode, route) for mode, route, *_rest in calls],
            [("ar", None), ("mtp", self.DEFAULT), ("mtp", self.CANDIDATE)],
        )
        self.assertEqual([item[3] for item in calls], [
            "ar", "mtp-default", "mtp-long-context-2111",
        ])
        self.assertEqual(calls[0][4]["mtplxOperatorRoute"], self.DEFAULT)
        self.assertEqual(calls[1][4]["mtplxOperatorRoute"], self.DEFAULT)
        self.assertEqual(calls[2][4]["mtplxOperatorRoute"], self.CANDIDATE)

    def test_candidate_requires_exact_parity_and_both_three_percent_gates(self) -> None:
        cases = (
            ("accepted", [104.0] * 4, "a", "a", self.CANDIDATE, True),
            ("wrong output", [120.0] * 4, "b", "a", self.DEFAULT, False),
            ("wrong default output", [120.0] * 4, "a", "b", self.DEFAULT, False),
            ("worst below floor", [102.0, 110.0, 110.0, 110.0], "a", "a", self.DEFAULT, False),
            ("rounding cannot promote below floor", [102.999] * 4, "a", "a", self.DEFAULT, False),
            ("median below floor", [102.0] * 4, "a", "a", self.DEFAULT, False),
        )
        for label, candidate_speeds, candidate_quality, default_quality, expected, accepted in cases:
            with self.subTest(label=label):
                manager, record, _calls = self._run_worker(
                    default_speeds=[100.0] * 4,
                    candidate_speeds=candidate_speeds,
                    candidate_quality=candidate_quality,
                    default_quality=default_quality,
                )
                self.assertEqual(manager.snapshot()["phase"], "completed")
                sweep = record["mtplxOperatorSweep"]
                self.assertEqual(sweep["selectedRoute"], expected)
                self.assertIs(sweep["candidateAccepted"], accepted)
                self.assertEqual(
                    record["modeSettings"]["mtp"]["mtplxOperatorRoute"], expected,
                )

    def test_final_ar_gate_uses_raw_speedup_before_rounding(self) -> None:
        manager, record, _calls = self._run_worker(
            ar_speeds=[100.0] * 4,
            default_speeds=[102.999] * 4,
            candidate_speeds=[102.999] * 4,
        )

        self.assertEqual(manager.snapshot()["phase"], "completed")
        self.assertEqual(
            record["mtplxOperatorSweep"]["selectedRoute"], self.DEFAULT,
        )
        self.assertFalse(record["mtplxOperatorSweep"]["candidateAccepted"])
        self.assertEqual(record["modes"]["mtp"]["medianSpeedupVsAR"], 1.03)
        self.assertEqual(record["modes"]["mtp"]["worstCaseSpeedupVsAR"], 1.03)
        self.assertEqual(record["winner"], "ar")
        self.assertEqual(record["settings"], {})
        self.assertEqual(record["winnerSpeedup"], 1.0)
        self.assertEqual(record["worstCaseSpeedup"], 1.0)
        with mock.patch.object(
            launcher, "hardware_fingerprint", return_value=self.MACHINE,
        ):
            self.assertTrue(launcher._local_benchmark_record_verified(
                self.capability, record, self.job["evidence"],
            ))

    def test_ar_winner_rejects_tampered_route_decision_inputs(self) -> None:
        manager, record, _calls = self._run_worker(
            ar_speeds=[100.0] * 4,
            default_speeds=[90.0] * 4,
            candidate_speeds=[91.0] * 4,
        )
        self.assertEqual(manager.snapshot()["phase"], "completed")
        self.assertEqual(record["winner"], "ar")

        changed_median = copy.deepcopy(record)
        changed_median["modes"]["ar"]["medianDecodeTokensPerSecond"] = 125.0
        changed_ar_total = copy.deepcopy(record)
        changed_ar_total["modes"]["ar"]["samples"][0]["totalSeconds"] = 999.0
        changed_mtp_total = copy.deepcopy(record)
        changed_mtp_total["modes"]["mtp"]["samples"][0]["totalSeconds"] = 999.0
        changed_ar_ttft = copy.deepcopy(record)
        changed_ar_ttft["modes"]["ar"]["samples"][0]["ttftSeconds"] = 999.0
        changed_mtp_pressure = copy.deepcopy(record)
        changed_mtp_pressure["modes"]["mtp"]["resourceTelemetry"][
            "peakPressureDeltaBytes"
        ] += 1
        changed_candidate_cooldown = copy.deepcopy(record)
        candidate = next(
            item
            for item in changed_candidate_cooldown["mtplxOperatorSweep"][
                "candidates"
            ]
            if item["route"] == self.CANDIDATE
        )
        candidate["resourceCooldownStatus"] = "timeout"

        with mock.patch.object(
            launcher, "hardware_fingerprint", return_value=self.MACHINE,
        ):
            self.assertTrue(launcher._local_benchmark_record_verified(
                self.capability, record, self.job["evidence"],
            ))
            for label, tampered in (
                ("AR median generation TPS", changed_median),
                ("AR sample total seconds", changed_ar_total),
                ("selected MTP sample total seconds", changed_mtp_total),
                ("AR sample time to first token", changed_ar_ttft),
                ("selected MTP peak pressure delta", changed_mtp_pressure),
                ("candidate cooldown status", changed_candidate_cooldown),
            ):
                with self.subTest(label=label):
                    self.assertFalse(
                        launcher._local_benchmark_record_verified(
                            self.capability, tampered, self.job["evidence"],
                        ),
                        f"tampered {label} was accepted as reusable local evidence",
                    )

    def test_ar_winner_rejects_forged_winner_and_selected_settings(self) -> None:
        manager, record, _calls = self._run_worker(
            ar_speeds=[100.0] * 4,
            default_speeds=[90.0] * 4,
            candidate_speeds=[91.0] * 4,
        )
        self.assertEqual(manager.snapshot()["phase"], "completed")
        self.assertEqual(record["winner"], "ar")

        forged_winner = copy.deepcopy(record)
        forged_winner.update({
            "winner": "mtp",
            "winnerSpeedup": 1.5,
            "worstCaseSpeedup": 1.5,
            "endToEndSpeedup": 1.5,
            "settings": copy.deepcopy(record["modeSettings"]["mtp"]),
        })
        forged_selected_settings = copy.deepcopy(record)
        forged_selected_settings["mtplxOperatorSweep"]["selectedSettings"] = {
            "depth": 3,
            "mtplxOperatorRoute": self.CANDIDATE,
        }

        with mock.patch.object(
            launcher, "hardware_fingerprint", return_value=self.MACHINE,
        ):
            self.assertTrue(launcher._local_benchmark_record_verified(
                self.capability, record, self.job["evidence"],
            ))
            for label, tampered in (
                ("top-level winner", forged_winner),
                ("selected settings", forged_selected_settings),
            ):
                with self.subTest(label=label):
                    self.assertFalse(
                        launcher._local_benchmark_record_verified(
                            self.capability, tampered, self.job["evidence"],
                        ),
                        f"forged {label} was accepted as reusable local evidence",
                    )

    def test_record_verifies_and_fastest_reuses_route_without_recalibration(self) -> None:
        manager, record, _calls = self._run_worker(
            default_speeds=[100.0] * 4,
            candidate_speeds=[104.0] * 4,
        )
        self.assertEqual(manager.snapshot()["phase"], "completed")
        with mock.patch.object(
            launcher, "hardware_fingerprint", return_value=self.MACHINE,
        ):
            self.assertTrue(launcher._local_benchmark_record_verified(
                self.capability, record, self.job["evidence"],
            ))

            reusable = copy.deepcopy(self.capability)
            reusable.update({
                "localBenchmark": copy.deepcopy(record),
                "localBenchmarks": [copy.deepcopy(record)],
                "preferredAcceleration": "mtp",
                "preferredAccelerationSource": "local-benchmark",
            })
            optimized = launcher.fastest_safe_options(
                "mtplx", reusable, self.options, self.job["evidence"],
            )
        self.assertEqual(optimized["evidenceTier"], "local-benchmark")
        self.assertEqual(optimized["options"]["acceleration"], "mtp")
        self.assertEqual(
            optimized["options"]["mtplxOperatorRoute"], self.CANDIDATE,
        )

        applied_model = copy.deepcopy(self.model)
        applied_model["backends"]["mtplx"] = reusable
        payload = {
            "backend": "mtplx",
            "client": "chat",
            "modelId": applied_model["id"],
            "project": str(self.root),
            "context": 65_536,
            "output": 1_024,
            "reasoning": "auto",
            "options": copy.deepcopy(self.options),
            "chat": {"systemPrompt": "", "sampling": "model"},
            "enginePreference": "throughput",
        }
        with (
            mock.patch.dict(launcher.BINARIES, {"mtplx": "/usr/bin/true"}, clear=True),
            mock.patch.object(launcher, "hardware_fingerprint", return_value=self.MACHINE),
        ):
            applied = launcher.best_engine_request(payload, [applied_model])
        self.assertEqual(applied["options"]["mtplxOperatorRoute"], self.CANDIDATE)
        self.assertEqual(applied["engineNextAction"]["id"], "keep-current")
        self.assertFalse(applied["engineNextAction"]["requiresCalibration"])

    def test_fastest_does_not_offer_an_expired_operator_candidate(self) -> None:
        manager, record, _calls = self._run_worker(
            default_speeds=[100.0] * 4,
            candidate_speeds=[104.0] * 4,
        )
        self.assertEqual(manager.snapshot()["phase"], "completed")
        expired = copy.deepcopy(record)
        expired["createdAt"] = "2000-01-01T00:00:00Z"
        capability = copy.deepcopy(self.capability)
        capability.update({
            "localBenchmark": copy.deepcopy(expired),
            "localBenchmarks": [copy.deepcopy(expired)],
            "preferredAcceleration": "mtp",
            "preferredAccelerationSource": "local-benchmark",
        })

        with mock.patch.object(
            launcher, "hardware_fingerprint", return_value=self.MACHINE,
        ):
            optimized = launcher.fastest_safe_options(
                "mtplx", capability, self.options, self.job["evidence"],
            )

        self.assertNotEqual(optimized["evidenceTier"], "local-benchmark")
        self.assertEqual(
            optimized["options"]["mtplxOperatorRoute"], self.DEFAULT,
        )

    def test_candidate_route_requires_fresh_matching_operator_evidence_for_use(self) -> None:
        manager, record, _calls = self._run_worker(
            default_speeds=[100.0] * 4,
            candidate_speeds=[104.0] * 4,
        )
        self.assertEqual(manager.snapshot()["phase"], "completed")
        self.assertTrue(record["mtplxOperatorSweep"]["candidateAccepted"])
        self.assertEqual(
            record["mtplxOperatorSweep"]["selectedRoute"], self.CANDIDATE,
        )

        def payload() -> dict:
            return {
                "backend": "mtplx",
                "client": "chat",
                "modelId": self.model["id"],
                "project": str(self.root),
                "context": 65_536,
                "output": 1_024,
                "reasoning": "auto",
                "mode": "custom",
                "options": {
                    **copy.deepcopy(self.options),
                    "acceleration": "mtp",
                    "profile": "turbo",
                    "fan": "default",
                    "mtplxOperatorRoute": self.CANDIDATE,
                },
                "chat": {"systemPrompt": "", "sampling": "model"},
            }

        def model_with(candidate_record: dict | None) -> dict:
            model = copy.deepcopy(self.model)
            capability = model["backends"]["mtplx"]
            capability["agentReasoning"] = ["auto", "off"]
            capability["localBenchmark"] = copy.deepcopy(candidate_record)
            capability["localBenchmarks"] = (
                [copy.deepcopy(candidate_record)]
                if isinstance(candidate_record, dict) else []
            )
            return model

        def normalize(
            request: dict, model: dict, purpose: str,
        ) -> launcher.LaunchPlan:
            return launcher.normalized_request(request, [model], purpose=purpose)

        no_record = model_with(None)
        matching = model_with(record)
        stale_record = copy.deepcopy(record)
        stale_record["createdAt"] = "2000-01-01T00:00:00Z"
        tampered_record = copy.deepcopy(record)
        tampered_record["modes"]["mtp"]["samples"][0]["totalSeconds"] = 999.0

        with (
            mock.patch.dict(
                launcher.BINARIES, {"mtplx": "/usr/bin/true"}, clear=True,
            ),
            mock.patch.object(launcher, "free_port", return_value=18_080),
            mock.patch.object(
                launcher, "_revalidated_mtplx_long_context_receipt",
                return_value=copy.deepcopy(self.receipt),
            ),
            mock.patch.object(launcher, "build_engine_plan"),
            mock.patch.object(launcher, "build_client_plan"),
            mock.patch.object(
                launcher, "hardware_fingerprint", return_value=self.MACHINE,
            ),
        ):
            benchmark_plan = normalize(payload(), no_record, "benchmark")
            self.assertEqual(
                benchmark_plan.options["mtplxOperatorRoute"], self.CANDIDATE,
            )
            self.assertEqual(
                benchmark_plan.options["_mtplxOperatorContractId"],
                self.receipt["contractId"],
            )

            for purpose in ("session", "route-check"):
                with self.subTest(missing_evidence=purpose), self.assertRaises(
                    ValueError,
                ):
                    normalize(payload(), no_record, purpose)

            session_plan = normalize(payload(), matching, "session")
            self.assertEqual(
                session_plan.options["mtplxOperatorRoute"], self.CANDIDATE,
            )
            self.assertEqual(
                session_plan.options["_mtplxOperatorContractId"],
                self.receipt["contractId"],
            )

            invalid_cases: list[tuple[str, dict, dict]] = [
                ("stale evidence", payload(), model_with(stale_record)),
                ("tampered evidence", payload(), model_with(tampered_record)),
            ]
            wrong_context = payload()
            wrong_context["context"] = 131_072
            invalid_cases.append(("wrong context", wrong_context, matching))
            wrong_reasoning = payload()
            wrong_reasoning["reasoning"] = "off"
            invalid_cases.append(("wrong reasoning", wrong_reasoning, matching))
            wrong_fan = payload()
            wrong_fan["options"]["fan"] = "max"
            invalid_cases.append(("wrong fan", wrong_fan, matching))

            for label, request, model in invalid_cases:
                with self.subTest(label=label), self.assertRaises(ValueError):
                    normalize(request, model, "session")

    def test_candidate_profile_cannot_disable_mtp_even_with_depth_one_evidence(self) -> None:
        manager, record, _calls = self._run_worker(
            default_speeds=[100.0] * 4,
            candidate_speeds=[104.0] * 4,
        )
        self.assertEqual(manager.snapshot()["phase"], "completed")
        self.assertEqual(record["winner"], "mtp")

        depth_one = copy.deepcopy(record)
        depth_one["settings"]["depth"] = 1
        depth_one["modeSettings"]["mtp"]["depth"] = 1
        depth_one["mtplxOperatorSweep"]["fixedMtpDepth"] = 1
        depth_one["mtplxOperatorSweep"]["selectedSettings"]["depth"] = 1
        for candidate in depth_one["mtplxOperatorSweep"]["candidates"]:
            candidate["settings"]["depth"] = 1

        model = copy.deepcopy(self.model)
        capability = model["backends"]["mtplx"]
        capability["depth"] = 1
        capability["localBenchmark"] = copy.deepcopy(depth_one)
        capability["localBenchmarks"] = [copy.deepcopy(depth_one)]
        request = {
            "backend": "mtplx",
            "client": "chat",
            "modelId": model["id"],
            "project": str(self.root),
            "context": 65_536,
            "output": 1_024,
            "reasoning": "auto",
            "mode": "custom",
            "options": {
                **copy.deepcopy(self.options),
                "acceleration": "off",
                "depth": 1,
                "mtplxOperatorRoute": self.CANDIDATE,
            },
            "chat": {"systemPrompt": "", "sampling": "model"},
        }
        evidence = launcher.optimizer_evidence(
            model, 65_536, 1_024, "chat", "auto", "off",
            request["chat"], self.job["samplingContract"],
        )
        launcher.add_benchmark_engine_evidence(
            evidence, model, request["options"], ["mtplx"],
        )

        with (
            mock.patch.dict(
                launcher.BINARIES, {"mtplx": "/usr/bin/true"}, clear=True,
            ),
            mock.patch.object(
                launcher, "hardware_fingerprint", return_value=self.MACHINE,
            ),
        ):
            self.assertTrue(launcher._local_benchmark_record_verified(
                capability, depth_one, evidence,
            ))
            with self.assertRaisesRegex(
                ValueError, "matching completed Calibration|requires MTP",
            ):
                launcher.validated_launch_profile_request(request, [model])

    def test_cross_engine_apply_normalizes_source_acceleration_for_target(self) -> None:
        model = copy.deepcopy(self.model)
        model["backends"]["omlx"] = {
            "runnable": True,
            "reason": "Verified model-free oMLX route",
            "runtimeVersion": "omlx test runtime",
            "benchmarkModelFingerprint": self.capability[
                "benchmarkModelFingerprint"
            ],
            "mtp": False,
            "mtpReason": "This fixture intentionally has no oMLX MTP route",
            "dflash": True,
            "dflashReason": "Verified model-free DFlash route",
            "kv": True,
            "depth": 1,
            "depthMax": 4,
            "agentReasoning": ["auto"],
            "implicitSamplingDefaultsVerified": True,
            "customSampling": True,
            "localBenchmarks": [],
        }

        def payload(backend: str, acceleration: str) -> dict:
            return {
                "backend": backend,
                "client": "chat",
                "modelId": model["id"],
                "project": str(self.root),
                "context": 65_536,
                "output": 1_024,
                "reasoning": "auto",
                "options": {
                    "acceleration": acceleration,
                    "depth": 3,
                    "kv": "off",
                    "profile": "turbo",
                    "fan": "default",
                    "mtplxOperatorRoute": self.DEFAULT,
                },
                "chat": {"systemPrompt": "", "sampling": "model"},
            }

        cases = (
            ("oMLX DFlash to MTPLX", "omlx", "dflash", "mtplx", "mtp"),
            ("MTPLX MTP to oMLX", "mtplx", "mtp", "omlx", "off"),
        )
        with mock.patch.dict(
            launcher.BINARIES,
            {"omlx": "/usr/bin/true", "mtplx": "/usr/bin/true"},
            clear=True,
        ):
            for label, source, source_acceleration, target, expected in cases:
                with self.subTest(label=label):
                    result = launcher._optimizer_with_forced_record(
                        payload(source, source_acceleration),
                        [model], model, target,
                        {"backend": target, "winner": "ar"},
                        {},
                    )
                    self.assertEqual(result["backend"], target)
                    self.assertEqual(result["options"]["acceleration"], expected)

    def test_generic_shootout_ar_resource_timeout_aborts_atomically(self) -> None:
        manager = self._manager()
        job = copy.deepcopy(self.job)
        job.pop("calibrationTuningPlan", None)
        job["suiteName"] = "quick"
        job["suite"] = copy.deepcopy(launcher.BENCHMARK_SUITES["quick"])
        job["workloadKind"] = str(job["suite"]["kind"])
        job["modes"] = ["ar"]
        shootout = {"id": "generic-timeout", "jobs": [job]}
        timeout = {
            "version": 1,
            "status": "timeout",
            "conditionDetail": "memory pressure remained above the reference",
        }

        with (
            mock.patch.object(
                manager, "_wait_for_resource_baseline", return_value=timeout,
            ),
            mock.patch.object(manager, "_measure_mode") as measure,
            mock.patch.object(manager, "_build_shootout_result") as finalize,
            mock.patch.object(launcher, "save_benchmark_records") as save,
        ):
            manager._shootout_worker(shootout, [self.model])

        status = manager.snapshot()
        self.assertEqual(status["phase"], "failed")
        self.assertIn("resource cooldown expired", status["message"])
        measure.assert_not_called()
        finalize.assert_not_called()
        save.assert_not_called()

    def test_capability_match_rejects_non_stable_2111_versions(self) -> None:
        advertised = copy.deepcopy(self.capability["longContext2111"])
        self.assertTrue(
            launcher._mtplx_long_context_capability_matches(
                advertised, self.receipt,
            ),
        )
        for version in (
            "2.11.1-beta", "2.11.1-dev1", "2.11.1+local",
            "mtplx 2.11.1-beta", "mtplx 2.11.1+local",
        ):
            candidate = copy.deepcopy(advertised)
            candidate["runtimeVersion"] = version
            with self.subTest(version=version):
                self.assertFalse(
                    launcher._mtplx_long_context_capability_matches(
                        candidate, self.receipt,
                    ),
                )

    def test_measured_profile_persists_and_revalidates_engine_binding(self) -> None:
        request = {
            "backend": "mtplx",
            "client": "chat",
            "modelId": self.model["id"],
            "project": str(self.root),
            "context": 65_536,
            "output": 1_024,
            "reasoning": "auto",
            "mode": "custom",
            "options": copy.deepcopy(self.options),
            "chat": {"systemPrompt": "", "sampling": "model"},
        }
        binding = {
            "scope": "engine",
            "suite": "quick",
            "preference": "throughput",
            "shootoutId": "profile-shootout",
            "recordIds": {
                "omlx": "profile-omlx-record",
                "mtplx": "profile-mtplx-record",
            },
        }
        ready_result = {
            "backend": "mtplx",
            "engineChanged": False,
            "engineEvidenceTier": "cross-engine-local-benchmark",
            "engineEvidenceLabel": "Highest generation TPS · locally measured",
            "engineRationale": ["The saved complete matrix still matches."],
            "engineEvidenceBinding": copy.deepcopy(binding),
            "engineNextAction": {
                "id": "keep-current",
                "requiresCalibration": False,
                "reason": "The saved complete matrix still matches.",
            },
        }
        seen_requests: list[dict] = []

        def revalidate(value: dict, _models: list[dict]) -> dict:
            seen_requests.append(copy.deepcopy(value))
            if value.get("evidenceBinding") != binding:
                raise ValueError("The saved engine comparison is stale.")
            return copy.deepcopy(ready_result)

        with (
            mock.patch.object(launcher, "STATE_DIR", self.root),
            mock.patch.dict(
                launcher.BINARIES, {"mtplx": "/usr/bin/true"}, clear=True,
            ),
            mock.patch.object(
                launcher, "best_engine_request", side_effect=revalidate,
            ),
        ):
            inventory = launcher.save_launch_profile({
                "name": "Measured long-context route",
                "enginePolicy": "measured",
                "enginePreference": "throughput",
                "evidenceBinding": copy.deepcopy(binding),
                "request": request,
            }, [self.model])

            profile = inventory["profiles"][0]
            self.assertTrue(profile["ready"])
            self.assertEqual(profile["evidenceBinding"], binding)
            self.assertTrue(profile["resolution"]["trustedWinner"])
            self.assertGreaterEqual(len(seen_requests), 2)
            self.assertTrue(all(
                value.get("evidenceBinding") == binding
                for value in seen_requests
            ))
            stored = launcher.read_json(launcher.launch_profile_store_path())
            self.assertEqual(
                stored["profiles"][0]["evidenceBinding"], binding,
            )

            stale = copy.deepcopy(stored)
            stale["profiles"][0]["evidenceBinding"]["recordIds"][
                "omlx"
            ] = "stale-omlx-record"
            launcher.atomic_json(launcher.launch_profile_store_path(), stale)
            stale_inventory = launcher.launch_profile_inventory([self.model])
            self.assertFalse(stale_inventory["profiles"][0]["ready"])
            self.assertIn("stale", stale_inventory["profiles"][0]["reason"])

            tampered = copy.deepcopy(stored)
            tampered["profiles"][0]["evidenceBinding"]["recordIds"] = []
            launcher.atomic_json(launcher.launch_profile_store_path(), tampered)
            tampered_inventory = launcher.launch_profile_inventory([self.model])
            self.assertFalse(tampered_inventory["profiles"][0]["ready"])
            self.assertIn("invalid", tampered_inventory["profiles"][0]["reason"])

            launcher.atomic_json(launcher.launch_profile_store_path(), stored)
            calibration_result = copy.deepcopy(ready_result)
            calibration_result["engineNextAction"] = {
                "id": "calibrate",
                "requiresCalibration": True,
                "reason": "Run Calibration again before applying this profile.",
            }
            with mock.patch.object(
                launcher, "best_engine_request",
                return_value=calibration_result,
            ):
                calibration_inventory = launcher.launch_profile_inventory(
                    [self.model],
                )
            calibration_profile = calibration_inventory["profiles"][0]
            self.assertFalse(calibration_profile["ready"])
            self.assertIn("Run Calibration", calibration_profile["reason"])
            self.assertNotIn("evidenceBinding", calibration_profile)

    def test_invalid_profile_binding_survives_unrelated_profile_save(self) -> None:
        request = {
            "backend": "mtplx",
            "client": "chat",
            "modelId": self.model["id"],
            "project": str(self.root),
            "context": 65_536,
            "output": 1_024,
            "reasoning": "auto",
            "mode": "custom",
            "options": copy.deepcopy(self.options),
            "chat": {"systemPrompt": "", "sampling": "model"},
        }
        corrupt_profile = {
            "id": "00000000-0000-4000-8000-000000000001",
            "name": "Corrupt measured profile",
            "createdAt": "2026-09-04T10:00:00+00:00",
            "updatedAt": "2026-09-04T10:00:00+00:00",
            "enginePolicy": "measured",
            "enginePreference": "throughput",
            "modelName": self.model["name"],
            "request": copy.deepcopy(request),
            "evidenceBinding": {
                "scope": "engine",
                "suite": "quick",
                "preference": "throughput",
                "shootoutId": "corrupt-shootout",
                "recordIds": [],
            },
        }

        with (
            mock.patch.object(launcher, "STATE_DIR", self.root),
            mock.patch.dict(
                launcher.BINARIES, {"mtplx": "/usr/bin/true"}, clear=True,
            ),
            mock.patch.object(launcher, "best_engine_request") as select_engine,
        ):
            launcher.atomic_json(launcher.launch_profile_store_path(), {
                "version": launcher.LAUNCH_PROFILE_STORE_VERSION,
                "profiles": [corrupt_profile],
            })
            before = launcher.launch_profile_inventory([self.model])
            self.assertFalse(before["profiles"][0]["ready"])
            self.assertIn("invalid", before["profiles"][0]["reason"])

            after_save = launcher.save_launch_profile({
                "name": "Unrelated fixed profile",
                "enginePolicy": "fixed",
                "enginePreference": "throughput",
                "request": request,
            }, [self.model])
            original = next(
                item for item in after_save["profiles"]
                if item["name"] == "Corrupt measured profile"
            )
            self.assertFalse(original["ready"])
            self.assertIn("invalid", original["reason"])

            persisted = launcher.read_json(
                launcher.launch_profile_store_path(),
            )
            original_record = next(
                item for item in persisted["profiles"]
                if item["name"] == "Corrupt measured profile"
            )
            self.assertIs(
                original_record.get("_evidenceBindingInvalid"), True,
            )

            after_reload = launcher.launch_profile_inventory([self.model])
            original = next(
                item for item in after_reload["profiles"]
                if item["name"] == "Corrupt measured profile"
            )
            self.assertFalse(original["ready"])
            self.assertNotIn("evidenceBinding", original)
            select_engine.assert_not_called()

    def test_bound_omlx_profile_preserves_non_smart_calibration_cooling(self) -> None:
        with (
            mock.patch.dict(
                launcher.BINARIES,
                {"omlx": "/usr/bin/true", "mtplx": "/usr/bin/true"},
                clear=True,
            ),
            mock.patch.object(
                launcher, "hardware_fingerprint", return_value=self.MACHINE,
            ),
        ):
            for fan in ("default", "max"):
                with self.subTest(fan=fan):
                    model, payload = self._generic_cross_engine_fixture(fan=fan)
                    selected = launcher.best_engine_request(payload, [model])
                    self.assertEqual(selected["backend"], "omlx")
                    binding = copy.deepcopy(
                        selected["engineEvidenceBinding"],
                    )
                    bound_payload = copy.deepcopy(payload)
                    bound_payload["evidenceBinding"] = copy.deepcopy(binding)
                    reapplied = launcher.best_engine_request(
                        bound_payload, [model],
                    )
                    self.assertEqual(reapplied["backend"], "omlx")

                    state = self.root / f"profile-cooling-{fan}"
                    with mock.patch.object(launcher, "STATE_DIR", state):
                        inventory = launcher.save_launch_profile({
                            "name": f"Measured {fan} cooling",
                            "enginePolicy": "measured",
                            "enginePreference": "throughput",
                            "evidenceBinding": binding,
                            "request": payload,
                        }, [model])
                        profile = inventory["profiles"][0]
                        self.assertTrue(profile["ready"])
                        self.assertEqual(profile["evidenceBinding"], binding)

                        reloaded = launcher.launch_profile_inventory([model])[
                            "profiles"
                        ][0]
                        self.assertTrue(reloaded["ready"])
                        self.assertEqual(reloaded["evidenceBinding"], binding)

    def test_measured_profile_missing_persisted_binding_fails_closed(self) -> None:
        model, payload = self._generic_cross_engine_fixture()
        with (
            mock.patch.object(
                launcher, "STATE_DIR", self.root / "missing-profile-binding",
            ),
            mock.patch.dict(
                launcher.BINARIES,
                {"omlx": "/usr/bin/true", "mtplx": "/usr/bin/true"},
                clear=True,
            ),
            mock.patch.object(
                launcher, "hardware_fingerprint", return_value=self.MACHINE,
            ),
        ):
            selected = launcher.best_engine_request(payload, [model])
            binding = copy.deepcopy(selected["engineEvidenceBinding"])
            inventory = launcher.save_launch_profile({
                "name": "Measured engine route",
                "enginePolicy": "measured",
                "enginePreference": "throughput",
                "evidenceBinding": binding,
                "request": payload,
            }, [model])
            self.assertTrue(inventory["profiles"][0]["ready"])

            stored = launcher.read_json(launcher.launch_profile_store_path())
            stored["profiles"][0].pop("evidenceBinding")
            launcher.atomic_json(launcher.launch_profile_store_path(), stored)

            reloaded = launcher.launch_profile_inventory([model])["profiles"][0]
            self.assertFalse(reloaded["ready"])
            self.assertNotIn("evidenceBinding", reloaded)
            self.assertIn("Run Calibration", reloaded["reason"])

    def test_route_bound_measured_profile_saves_replays_and_expires(self) -> None:
        model, source_payload = self._generic_cross_engine_fixture()
        route_record = copy.deepcopy(
            model["backends"]["mtplx"]["localBenchmark"],
        )
        route_record.update({"id": "profile-route-record"})
        route_record.pop("shootoutId", None)
        route_record.pop("shootoutExecutionOrder", None)
        route_record.pop("shootoutOrderIndex", None)
        route_record.pop("shootoutOrderStrategy", None)
        capability = model["backends"]["mtplx"]
        capability["localBenchmark"] = copy.deepcopy(route_record)
        capability["localBenchmarks"] = [copy.deepcopy(route_record)]
        request = {
            **copy.deepcopy(source_payload),
            "backend": "mtplx",
            "options": {
                "acceleration": "auto",
                "depth": 3,
                "kv": "off",
                "profile": "turbo",
                "fan": "default",
                "mtplxOperatorRoute": self.DEFAULT,
            },
        }
        binding = {
            "scope": "route",
            "suite": "quick",
            "preference": "throughput",
            "recordId": route_record["id"],
        }
        bound_request = copy.deepcopy(request)
        bound_request["evidenceBinding"] = copy.deepcopy(binding)

        with (
            mock.patch.object(
                launcher, "STATE_DIR", self.root / "route-profile",
            ),
            mock.patch.dict(
                launcher.BINARIES,
                {"omlx": "/usr/bin/true", "mtplx": "/usr/bin/true"},
                clear=True,
            ),
            mock.patch.object(
                launcher, "hardware_fingerprint", return_value=self.MACHINE,
            ),
        ):
            preflight = launcher.optimal_request(bound_request, [model])
            self.assertEqual(preflight["evidenceBinding"], binding)

            inventory = launcher.save_launch_profile({
                "name": "Qualified local route",
                "enginePolicy": "measured",
                "enginePreference": "throughput",
                "evidenceBinding": copy.deepcopy(binding),
                "request": request,
            }, [model])
            profile = inventory["profiles"][0]
            self.assertTrue(profile["ready"])
            self.assertEqual(profile["evidenceBinding"], binding)
            stored = launcher.read_json(launcher.launch_profile_store_path())
            self.assertEqual(stored["profiles"][0]["evidenceBinding"], binding)

            reloaded = launcher.launch_profile_inventory([model])["profiles"][0]
            self.assertTrue(reloaded["ready"])
            self.assertEqual(reloaded["evidenceBinding"], binding)

            expired_model = copy.deepcopy(model)
            expired = copy.deepcopy(route_record)
            expired["createdAt"] = "2000-01-01T00:00:00Z"
            expired_capability = expired_model["backends"]["mtplx"]
            expired_capability["localBenchmark"] = copy.deepcopy(expired)
            expired_capability["localBenchmarks"] = [copy.deepcopy(expired)]
            expired_profile = launcher.launch_profile_inventory(
                [expired_model],
            )["profiles"][0]
            self.assertFalse(expired_profile["ready"])
            self.assertNotIn("evidenceBinding", expired_profile)

    def test_future_and_expired_cross_engine_records_cannot_select_or_apply(self) -> None:
        model = copy.deepcopy(self.model)
        model["backends"]["omlx"] = {
            "runnable": True,
            "reason": "Verified model-free oMLX route",
            "runtimeVersion": "omlx test runtime",
            "benchmarkModelFingerprint": self.capability[
                "benchmarkModelFingerprint"
            ],
            "mtp": True,
            "mtpReason": "Verified model-free MTP tensors",
            "dflash": False,
            "kv": True,
            "depth": 3,
            "depthMax": 3,
            "agentReasoning": ["auto"],
            "implicitSamplingDefaultsVerified": True,
            "customSampling": True,
            "localBenchmarks": [],
        }
        payload = {
            "backend": "omlx",
            "client": "chat",
            "modelId": model["id"],
            "project": str(self.root),
            "context": 16_384,
            "output": 1_024,
            "reasoning": "auto",
            "options": {
                "acceleration": "auto",
                "depth": 3,
                "kv": "off",
                "burst": "balanced",
                "anePrefill": "off",
                "memoryGuard": "balanced",
                "profile": "turbo",
                "fan": "default",
                "mtplxOperatorRoute": self.DEFAULT,
            },
            "chat": {"systemPrompt": "", "sampling": "model"},
            "enginePreference": "throughput",
        }
        sampling = launcher.build_sampling_contract(
            "model", model_defaults=model["defaultSampling"],
        ).as_dict()
        evidence = launcher.optimizer_evidence(
            model, payload["context"], payload["output"], "chat", "auto",
            "off", payload["chat"], sampling,
        )
        launcher.add_benchmark_engine_evidence(
            evidence, model, payload["options"], ["omlx", "mtplx"],
        )

        def measured(speed: float, label: str, settings: dict) -> dict:
            samples = []
            for target in (512, 2_048):
                total = round(63.0 / speed + 0.2, 6)
                samples.append({
                    "targetPromptTokens": target,
                    "repetition": 1,
                    "promptTokens": target,
                    "completionTokens": 64,
                    "authoritativeUsage": True,
                    "ttftSeconds": 0.2,
                    "totalSeconds": total,
                    "decodeTokensPerSecond": speed,
                    "endToEndTokensPerSecond": round(64.0 / total, 6),
                })
            return {
                "label": label,
                "settings": copy.deepcopy(settings),
                "qualityHash": "a" * 64,
                "qualityCompletionTokens": 64,
                "medianTTFT": 0.2,
                "medianDecodeTokensPerSecond": speed,
                "medianEndToEndTokensPerSecond": round(
                    sum(sample["endToEndTokensPerSecond"] for sample in samples)
                    / len(samples), 3,
                ),
                "samples": samples,
            }

        records: dict[str, dict] = {}
        with mock.patch.object(
            launcher, "hardware_fingerprint", return_value=self.MACHINE,
        ):
            for backend, speed in (("omlx", 70.0), ("mtplx", 90.0)):
                job_evidence = copy.deepcopy(evidence)
                job_evidence["engineSettings"] = copy.deepcopy(
                    evidence["engineSettingsByBackend"][backend]
                )
                job = {
                    "id": f"fresh-{backend}-record",
                    "backend": backend,
                    "client": "chat",
                    "modelId": model["id"],
                    "model": copy.deepcopy(model),
                    "context": payload["context"],
                    "output": payload["output"],
                    "reasoning": "auto",
                    "options": copy.deepcopy(payload["options"]),
                    "suiteName": "quick",
                    "suite": copy.deepcopy(launcher.BENCHMARK_SUITES["quick"]),
                    "workloadKind": "throughput",
                    "enginePreference": payload["enginePreference"],
                    "modes": ["ar", "mtp"],
                    "evidence": job_evidence,
                    "modelFingerprint": model["backends"][backend][
                        "benchmarkModelFingerprint"
                    ],
                    "runtimeVersion": model["backends"][backend][
                        "runtimeVersion"
                    ],
                    "pairFingerprint": None,
                    "ssdStreaming": False,
                    "ssdComparisonIdentity": "",
                    "shootoutId": "fresh-cross-engine-shootout",
                    "shootoutExecutionOrder": ["omlx", "mtplx"],
                    "shootoutOrderIndex": 0 if backend == "omlx" else 1,
                    "shootoutOrderStrategy": "alternating",
                }
                manager = launcher.BenchmarkManager(mock.Mock())
                records[backend] = manager._build_record(job, {
                    "ar": measured(50.0, "AR", {}),
                    "mtp": measured(speed, "MTP", {"depth": 3}),
                })

        fresh_model = copy.deepcopy(model)
        for backend, record in records.items():
            capability = fresh_model["backends"][backend]
            capability["localBenchmark"] = copy.deepcopy(record)
            capability["localBenchmarks"] = [copy.deepcopy(record)]

        with (
            mock.patch.dict(
                launcher.BINARIES,
                {"omlx": "/usr/bin/true", "mtplx": "/usr/bin/true"},
                clear=True,
            ),
            mock.patch.object(
                launcher, "hardware_fingerprint", return_value=self.MACHINE,
            ),
        ):
            fresh = launcher.best_engine_request(payload, [fresh_model])
            self.assertEqual(fresh["backend"], "mtplx")
            self.assertEqual(
                fresh["engineEvidenceTier"], "cross-engine-local-benchmark",
            )
            self.assertEqual(fresh["engineNextAction"]["id"], "apply")
            binding = copy.deepcopy(fresh["engineEvidenceBinding"])

            for label, created_at in (
                ("future", "2999-01-01T00:00:00Z"),
                ("expired", "2000-01-01T00:00:00Z"),
            ):
                aged_model = copy.deepcopy(fresh_model)
                for backend in records:
                    capability = aged_model["backends"][backend]
                    capability["localBenchmark"]["createdAt"] = created_at
                    capability["localBenchmarks"][0]["createdAt"] = created_at
                with self.subTest(label=label):
                    unbound = launcher.best_engine_request(
                        payload, [aged_model],
                    )
                    self.assertEqual(unbound["backend"], "omlx")
                    self.assertTrue(
                        unbound["engineNextAction"]["requiresCalibration"],
                    )
                    self.assertNotIn("engineEvidenceBinding", unbound)

                    bound_payload = copy.deepcopy(payload)
                    bound_payload["evidenceBinding"] = binding
                    with self.assertRaises(ValueError):
                        launcher.best_engine_request(
                            bound_payload, [aged_model],
                        )

    def test_matrix_is_saved_only_after_complete_verified_finalization(self) -> None:
        order: list[str] = []

        def finalizer(_shootout, records, _models):
            order.append("finalized")
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["kind"], "mtplx-long-context-operator-tuning")
            return {"recommendation": "complete"}

        successful, record, _calls = self._run_worker(
            default_speeds=[100.0] * 4,
            candidate_speeds=[104.0] * 4,
            finalizer=finalizer,
            commit_order=order,
        )
        self.assertEqual(successful.snapshot()["phase"], "completed")
        self.assertTrue(record)
        self.assertEqual(order, ["finalized", "saved"])

        failed = self._manager()
        gates = [
            {"status": "reference-ready", "reference": {}},
            {"status": "ready", "reference": {}},
            {"status": "ready", "reference": {}},
        ]
        call_count = 0

        def incomplete(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                raise RuntimeError("candidate load failed")
            route = None if call_count == 1 else self.DEFAULT
            result = self._result(
                speeds=[80.0] * 4 if route is None else [100.0] * 4,
                route=route,
            )
            return result, call_count * 6

        with (
            mock.patch.object(failed, "_wait_for_resource_baseline", side_effect=gates),
            mock.patch.object(failed, "_measure_mode", side_effect=incomplete),
            mock.patch.object(failed, "_build_shootout_result") as finalize,
            mock.patch.object(launcher, "hardware_fingerprint", return_value=self.MACHINE),
            mock.patch.object(launcher, "save_benchmark_records") as save,
        ):
            failed._shootout_worker(
                {"id": "failed", "jobs": [copy.deepcopy(self.job)]}, [self.model],
            )
        self.assertEqual(failed.snapshot()["phase"], "failed")
        finalize.assert_not_called()
        save.assert_not_called()

        finalization_failed = self._manager()
        with (
            mock.patch.object(
                finalization_failed, "_wait_for_resource_baseline", side_effect=gates,
            ),
            mock.patch.object(
                finalization_failed, "_measure_mode",
                side_effect=[
                    (self._result(speeds=[80.0] * 4), 6),
                    (self._result(speeds=[100.0] * 4, route=self.DEFAULT), 12),
                    (self._result(speeds=[104.0] * 4, route=self.CANDIDATE), 18),
                ],
            ),
            mock.patch.object(
                finalization_failed, "_build_shootout_result",
                side_effect=RuntimeError("finalization failed"),
            ),
            mock.patch.object(launcher, "hardware_fingerprint", return_value=self.MACHINE),
            mock.patch.object(launcher, "save_benchmark_records") as save,
        ):
            finalization_failed._shootout_worker(
                {"id": "finalization-failed", "jobs": [copy.deepcopy(self.job)]},
                [self.model],
            )
        self.assertEqual(finalization_failed.snapshot()["phase"], "failed")
        save.assert_not_called()

    def test_long_context_plan_normalizes_turbo_and_rebinds_engine_evidence(self) -> None:
        sustained = copy.deepcopy(self.job)
        sustained.pop("calibrationTuningPlan", None)
        sustained["suiteName"] = "agentic"
        sustained["suite"] = copy.deepcopy(launcher.BENCHMARK_SUITES["agentic"])
        sustained["options"]["profile"] = "sustained"
        sustained["evidence"]["engineSettings"]["profile"] = "sustained"

        launcher.prepare_calibration_tuning_plan(sustained)

        self.assertEqual(
            sustained["calibrationTuningPlan"]["strategy"],
            "isolated-long-context-operator-comparison",
        )
        self.assertEqual(sustained["options"]["profile"], "turbo")
        self.assertEqual(
            sustained["evidence"]["engineSettings"],
            {"profile": "turbo", "fan": "default"},
        )

    def test_sustained_shootout_finalizes_applies_and_reuses_turbo_result(self) -> None:
        model = copy.deepcopy(self.model)
        model["backends"]["mtplx"]["profile"] = "sustained"
        model_fingerprint = model["backends"]["mtplx"][
            "benchmarkModelFingerprint"
        ]
        model["backends"]["omlx"] = {
            "runnable": True,
            "reason": "Verified model-free oMLX comparison route",
            "runtimeVersion": "omlx test runtime",
            "benchmarkModelFingerprint": model_fingerprint,
            "mtp": False,
            "mtpReason": "No paired MTP artifact in this fixture",
            "dflash": False,
            "dflashReason": "No paired DFlash artifact in this fixture",
            "kv": True,
            "agentReasoning": ["auto"],
            "codexReasoning": ["auto"],
            "implicitSamplingDefaultsVerified": True,
            "customSampling": True,
            "localBenchmarks": [],
        }
        payload = {
            "backend": "mtplx",
            "client": "chat",
            "modelId": model["id"],
            "project": str(self.root),
            "context": 65_536,
            "output": 1_024,
            "reasoning": "auto",
            "options": {
                **copy.deepcopy(self.options),
                "profile": "sustained",
            },
            "chat": {"systemPrompt": "", "sampling": "model"},
            "suite": "agentic",
            "scope": "engines",
            "enginePreference": "throughput",
        }
        saved_records: list[dict] = []

        def resource_gate(
            _label: str, _backend: str,
            reference: dict | None = None,
        ) -> dict:
            baseline = {
                "memoryAvailable": True,
                "freePercent": 50.0,
            }
            return {
                "version": 1,
                "status": "reference-ready" if reference is None else "ready",
                "reference": copy.deepcopy(reference or baseline),
                "observed": copy.deepcopy(reference or baseline),
                "_initialSnapshot": {},
            }

        def measured(
            job: dict, _models: list[dict], mode: str, completed: int,
            _total: int, gate: dict, **_kwargs,
        ) -> tuple[dict, int]:
            backend = str(job["backend"])
            operator_route = (
                str(job.get("_benchmarkMtplxOperatorRoute") or "")
                if backend == "mtplx" and mode == "mtp" else None
            )
            if backend == "omlx":
                result = self._result(speeds=[70.0] * 4)
                pressure = 2 * 1024**3
            elif operator_route == self.DEFAULT:
                result = self._result(
                    speeds=[110.0] * 4, route=self.DEFAULT,
                )
                pressure = 3 * 1024**3
            elif operator_route == self.CANDIDATE:
                result = self._result(
                    speeds=[115.0] * 4, route=self.CANDIDATE,
                )
                pressure = 3 * 1024**3
            else:
                result = self._result(speeds=[90.0] * 4)
                pressure = 3 * 1024**3
            result["resourceTelemetry"] = physical_telemetry({
                "version": 1,
                "sampleCount": 3,
                "memoryAvailable": True,
                "totalMemoryBytes": 64 * 1024**3,
                "baselineHeadroomPercent": 50.0,
                "peakPressureDeltaBytes": pressure,
                "minimumHeadroomPercent": 45.0,
                "thermalAvailable": True,
                "thermalStartValue": 0,
                "thermalStart": "nominal",
                "thermalWorstValue": 0,
                "thermalWorst": "nominal",
                "lowPowerMode": False,
            })
            result["resourceCooldown"] = {
                key: copy.deepcopy(value)
                for key, value in gate.items()
                if key != "_initialSnapshot"
            }
            return result, completed + 6

        with mock.patch.dict(
            launcher.BINARIES,
            {"mtplx": "/usr/bin/true", "omlx": "/usr/bin/true"},
            clear=True,
        ), mock.patch.object(
            launcher, "hardware_fingerprint", return_value=self.MACHINE,
        ):
            shootout = launcher.validated_engine_shootout_request(
                payload, [model],
            )
            self.assertEqual(payload["options"]["profile"], "sustained")
            self.assertEqual(
                shootout["request"]["options"]["profile"], "turbo",
            )
            mtplx_job = next(
                job for job in shootout["jobs"]
                if job["backend"] == "mtplx"
            )
            self.assertEqual(mtplx_job["options"]["profile"], "turbo")
            self.assertEqual(
                mtplx_job["evidence"]["engineSettings"],
                {"profile": "turbo", "fan": "default"},
            )
            self.assertEqual(
                launcher.benchmark_engine_settings(
                    "mtplx", shootout["request"]["options"],
                ),
                mtplx_job["evidence"]["engineSettings"],
            )

            manager = self._manager()
            manager.state["engines"] = {
                job["backend"]: {
                    "backend": job["backend"],
                    "label": launcher.BACKEND_LABELS[job["backend"]],
                    "phase": "queued",
                    "modes": {},
                    "record": None,
                }
                for job in shootout["jobs"]
            }
            with mock.patch.object(
                manager, "_wait_for_resource_baseline",
                side_effect=resource_gate,
            ), mock.patch.object(
                manager, "_measure_mode", side_effect=measured,
            ), mock.patch.object(
                launcher, "save_benchmark_records",
                side_effect=lambda records: saved_records.extend(
                    copy.deepcopy(records)
                ),
            ):
                manager._shootout_worker(shootout, [model])

            status = manager.snapshot()
            self.assertEqual(status["phase"], "completed", status)
            self.assertEqual(len(saved_records), 2)
            self.assertTrue(status["result"]["matrixQualityPassed"])
            self.assertEqual(status["result"]["recommendedBackend"], "mtplx")
            self.assertIsInstance(
                status["result"].get("evidenceBinding"), dict,
                status["result"],
            )
            saved_mtplx = next(
                record for record in saved_records
                if record["backend"] == "mtplx"
            )
            self.assertEqual(
                saved_mtplx["engineSettings"],
                {"profile": "turbo", "fan": "default"},
            )
            self.assertEqual(
                saved_mtplx["mtplxOperatorSweep"]["selectedRoute"],
                self.CANDIDATE,
            )

            enriched = manager._models_with_shootout_records(
                [model], model["id"], saved_records,
            )
            apply_request = copy.deepcopy(shootout["request"])
            apply_request["evidenceBinding"] = copy.deepcopy(
                status["result"]["evidenceBinding"]
            )
            applied = launcher.best_engine_request(apply_request, enriched)
            self.assertEqual(applied["backend"], "mtplx")
            self.assertEqual(applied["options"]["profile"], "turbo")
            self.assertEqual(
                applied["options"]["mtplxOperatorRoute"], self.CANDIDATE,
            )
            self.assertEqual(applied["engineNextAction"]["id"], "apply")
            self.assertFalse(
                applied["engineNextAction"]["requiresCalibration"],
            )

            fastest_request = copy.deepcopy(shootout["request"])
            fastest_request["backend"] = applied["backend"]
            fastest_request["options"] = copy.deepcopy(applied["options"])
            fastest = launcher.best_engine_request(
                fastest_request, enriched,
            )
            self.assertEqual(fastest["backend"], "mtplx")
            self.assertEqual(fastest["options"]["profile"], "turbo")
            self.assertEqual(
                fastest["options"]["mtplxOperatorRoute"], self.CANDIDATE,
            )
            self.assertEqual(
                fastest["engineNextAction"]["id"], "keep-current",
            )
            self.assertFalse(
                fastest["engineNextAction"]["requiresCalibration"],
            )

    def test_tampered_contract_environment_and_measured_result_fail_closed(self) -> None:
        _manager, record, _calls = self._run_worker(
            default_speeds=[100.0] * 4,
            candidate_speeds=[104.0] * 4,
        )
        tampered = []

        wrong_contract = copy.deepcopy(record)
        wrong_contract["mtplxOperatorSweep"]["contract"]["environment"][
            "MTPLX_CONTEXT_COPY"
        ] = "1"
        tampered.append(("contract", wrong_contract))

        wrong_environment = copy.deepcopy(record)
        wrong_environment["mtplxOperatorSweep"]["candidateEnvironment"][
            "MTPLX_CONTEXT_COPY"
        ] = "1"
        tampered.append(("environment", wrong_environment))

        wrong_result = copy.deepcopy(record)
        wrong_result["modes"]["mtp"]["samples"][0][
            "decodeTokensPerSecond"
        ] = 1.0
        tampered.append(("measured result", wrong_result))

        forged_speedup = copy.deepcopy(record)
        candidate = next(
            item for item in forged_speedup["mtplxOperatorSweep"]["candidates"]
            if item["route"] == self.CANDIDATE
        )
        candidate["medianSpeedupVsDefault"] = 50.0
        tampered.append(("candidate metric", forged_speedup))

        wrong_selected_settings = copy.deepcopy(record)
        wrong_selected_settings["mtplxOperatorSweep"]["selectedSettings"] = {
            "depth": 3, "mtplxOperatorRoute": self.DEFAULT,
        }
        tampered.append(("selected settings", wrong_selected_settings))

        old_word_count_workload = copy.deepcopy(record)
        old_word_count_workload["mtplxOperatorSweep"]["version"] = 2
        tampered.append(("old unbudgeted corpus", old_word_count_workload))

        old_unbound_request_limit = copy.deepcopy(record)
        old_unbound_request_limit["mtplxOperatorSweep"]["version"] = 3
        tampered.append(("old unbound request allowance", old_unbound_request_limit))

        old_stochastic_probe = copy.deepcopy(record)
        old_stochastic_probe["mtplxOperatorSweep"]["version"] = 4
        tampered.append(("old stochastic correctness probe", old_stochastic_probe))

        with mock.patch.object(
            launcher, "hardware_fingerprint", return_value=self.MACHINE,
        ):
            for label, value in tampered:
                with self.subTest(label=label):
                    self.assertFalse(
                        launcher._local_benchmark_record_verified(
                            self.capability, value, self.job["evidence"],
                        ),
                        f"tampered {label} was accepted as reusable local evidence",
                    )


if __name__ == "__main__":
    unittest.main()
