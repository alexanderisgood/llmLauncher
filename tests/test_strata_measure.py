"""Reject misleading Strata rates, stale requests and side-effectful previews."""
from copy import deepcopy
from contextlib import redirect_stdout, nullcontext
import hashlib
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

from bench import strata_measure as measure


class StrataTimingTests(unittest.TestCase):
    def setUp(self):
        self.sample = {"promptTokens": 1000, "completionTokens": 135,
                       "observedDecodeTokensPerSecond": 9000,
                       "decodeTokensPerSecond": 9000,
                       "engineTimings": {"predicted_n": 135, "predicted_ms": 2000,
                                         "predicted_per_second": 60, "prompt_n": 900,
                                         "cache_n": 100, "prompt_ms": 3000}}
        self.before = {"totals": {"requests": 4}}
        self.after = {"totals": {"requests": 5}, "live": {"state": "idle"},
                      "requests": [{"prompt_tokens": 1000, "output_tokens": 135,
                                    "engine_generated": 120, "prompt_read": 900, "reused": 100,
                                    "decode_ms": 2000, "prompt_ms": 3000}]}

    def test_uses_native_count_instead_of_server_added_output_or_network_burst(self):
        got = measure.bind_strata_timing(self.sample, self.before, self.after)
        self.assertEqual(got["nativeDecodeTokensPerSecond"], 60)
        self.assertEqual(got["generationProof"]["decodeTokenCount"], 120)
        self.assertEqual(got["completionTokens"], 135)
        self.assertEqual(got["nativePrefillTokensPerSecond"], 300)
        self.assertEqual(got["observedDecodeTokensPerSecond"], 9000)
        self.assertEqual(self.sample["decodeTokensPerSecond"], 9000)

    def test_rejects_stale_extra_or_inflight_requests(self):
        for count, state in ((4, "idle"), (6, "idle"), (5, "generating")):
            after = deepcopy(self.after)
            after["totals"]["requests"], after["live"]["state"] = count, state
            with self.subTest(count=count, state=state), self.assertRaises(ValueError):
                measure.bind_strata_timing(self.sample, self.before, after)

    def test_rejects_changed_usage_or_native_clock(self):
        for key, value in (("prompt_tokens", 999), ("output_tokens", 134),
                           ("engine_generated", 119), ("prompt_read", 899),
                           ("decode_ms", 1900), ("prompt_ms", 2900)):
            after = deepcopy(self.after)
            after["requests"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                measure.bind_strata_timing(self.sample, self.before, after)

    def test_rejects_missing_nonfinite_or_boolean_native_values(self):
        for field in ("engine_generated", "decode_ms", "prompt_ms"):
            for value in (None, True, float("nan"), 0):
                after = deepcopy(self.after)
                after["requests"][0][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    measure.bind_strata_timing(self.sample, self.before, after)

    def test_requires_matching_response_timing(self):
        for change in ({"engineTimings": None}, {"engineTimings": {}}):
            sample = {**self.sample, **change}
            with self.assertRaises(ValueError):
                measure.bind_strata_timing(sample, self.before, self.after)

    def test_complete_cache_hit_is_not_credited_as_prefill_work(self):
        sample, after = deepcopy(self.sample), deepcopy(self.after)
        sample["engineTimings"].update(prompt_n=0, cache_n=1000, prompt_ms=0)
        after["requests"][0].update(prompt_read=0, reused=1000, prompt_ms=0)
        got = measure.bind_strata_timing(sample, self.before, after)
        self.assertNotIn("nativePrefillTokensPerSecond", got)


class StrataPlanTests(unittest.TestCase):
    def test_served_context_must_come_from_loaded_native_model(self):
        for context in (32768, 131072):
            catalog = {"object": "list", "data": [{"id": "flash-next", "meta": {"n_ctx": context},
                                                   "status": {"value": "loaded"}}]}
            measure.validate_strata_catalog(catalog, "flash-next", context)

    def test_rejects_wrong_missing_ambiguous_or_unloaded_served_context(self):
        model = {"id": "flash-next", "meta": {"n_ctx": 32768}, "status": {"value": "loaded"}}
        cases = [None, {}, {"data": "unavailable"}, {"data": []}, {"data": [model, model]}]
        for replacement in ({"id": "another-model"}, {"meta": {}}, {"meta": {"n_ctx": 131072}},
                            {"meta": {"n_ctx": "32768"}}, {"meta": {"n_ctx": True}},
                            {"status": {"value": "unloaded"}}, {"status": None}):
            cases.append({"data": [{**model, **replacement}]})
        for catalog in cases:
            with self.subTest(catalog=catalog), self.assertRaisesRegex(ValueError, "Strata served"):
                measure.validate_strata_catalog(catalog, "flash-next", 32768)

    def test_long_only_preview_plans_one_fresh_quality_engine(self):
        output = io.StringIO()
        with redirect_stdout(output), patch.object(measure, "verify_slotstream_weights") as verify:
            self.assertEqual(measure.main(["--engine", "slotstream", "--context", "32768",
                                           "--long-quality-only", "--dry-run"]), 0)
        preview = json.loads(output.getvalue())
        self.assertEqual((preview["phase"], preview["expectedEngineStarts"]), ("long-quality", 1))
        verify.assert_not_called()

    def test_fresh_runner_imports_controller_native_memory_helper(self):
        result = subprocess.run([sys.executable, "-c", "from bench import strata_measure as s; "
                                 "print(s.darwin_memory.__file__); "
                                 "assert callable(s.darwin_memory.physical_reclaimable_state)"],
                                cwd=measure.ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout.strip()).resolve(), measure.ROOT / "darwin_memory.py")

    def test_slotstream_preview_uses_requested_port_without_loading_weights(self):
        output = io.StringIO()
        with redirect_stdout(output), patch.object(measure, "verify_slotstream_weights") as verify:
            self.assertEqual(measure.main(["--engine", "slotstream", "--context", "32768",
                                           "--port", "18666", "--dry-run"]), 0)
        command = json.loads(output.getvalue())["command"]
        self.assertEqual(command[command.index("--port") + 1], "18666")
        verify.assert_not_called()

    def test_review_keeps_original_config_and_creates_no_private_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            exe = root / "strata"
            exe.touch()
            original = {"backend": "metal", "model_name": "qwen3.8-flash-next-ud-q4_k_xl",
                        "exe": str(exe), "args": ["--max-context", "32768", "--pack", "unchanged"],
                        "env": {"STRATA_METAL_STREAM": "1", "STRATA_ROUTE_TAIL_SKIP": "7", "STRATA_PREFILL_CPU_SHARE": "auto"},
                        "mcp_servers": [{"command": "unused"}], "parallel": 4, "host": "0.0.0.0"}
            config = root / "original.json"
            config.write_text(json.dumps(original))
            work = root / "private-run"
            engine = measure.make_strata(config, 131072, 18765, work)
            planned = engine.extra["_privateConfig"]
            self.assertFalse(work.exists())
            self.assertEqual(json.loads(config.read_text()), original)
            self.assertEqual(planned["args"], ["--max-context", "131072", "--pack", "unchanged"])
            self.assertEqual(planned["host"], "127.0.0.1")
            self.assertEqual(planned["parallel"], 1)
            self.assertEqual(planned["env"], {"STRATA_METAL_STREAM": "1", "STRATA_ROUTE_TAIL_SKIP": "0", "STRATA_PREFILL_CPU_SHARE": "0"})
            self.assertNotIn("mcp_servers", planned)
            self.assertNotIn(engine.api_key, " ".join(engine.argv))

    def test_rejects_lower_precision_substitution_and_duplicate_context(self):
        with self.assertRaises(ValueError):
            measure.replace_option(["--max-context", "32768", "--max-context=65536"], "--max-context", 131072)
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "lower-precision.json"
            config.write_text(json.dumps({"backend": "metal", "model_name": "qwen3.8-flash-next-q2_0"}))
            with self.assertRaisesRegex(ValueError, "Q4"):
                measure.make_strata(config, 32768, 18765, Path(directory) / "run")

    def test_failed_private_file_creation_does_not_remove_preexisting_file(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            path = work / "strata.json"
            path.write_text("preserve existing data")
            engine = SimpleNamespace(work_dir=work, extra={"_privateConfig": {}, "_privateConfigPath": path})
            with self.assertRaises(FileExistsError):
                measure.start_clean(engine)
            measure.dispose_private_config(engine)
            self.assertEqual(path.read_text(), "preserve existing data")

    def test_failed_process_start_disposes_only_created_private_file(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            path = work / "strata.json"
            engine = SimpleNamespace(work_dir=work, extra={"_privateConfig": {}, "_privateConfigPath": path},
                                     argv=["missing-executable"], env={})
            with patch.object(measure.subprocess, "Popen", side_effect=OSError("generated start failure")):
                with self.assertRaises(OSError):
                    measure.start_clean(engine)
            self.assertTrue(path.exists())
            measure.dispose_private_config(engine)
            self.assertFalse(path.exists())

    def test_unstarted_resource_monitor_can_be_cleaned_after_thread_failure(self):
        guard = measure.ResourceGuard(SimpleNamespace(pid=123), 100, 10)
        guard.stop()


class WeightVerificationTests(unittest.TestCase):
    def test_detects_same_length_weight_corruption_and_preserves_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.safetensors"
            path.write_bytes(b"changed!")
            install = {"ready": True, "mtp": True, "missing": [], "modelPath": directory}
            row = {"path": path.name, "size": 8, "sha256": hashlib.sha256(b"original").hexdigest()}
            engine = SimpleNamespace(argv=["fixture"], extra={"model": directory})
            with patch.object(measure.slotstream_runtime, "inspect_install", return_value=install), \
                 patch.object(measure.slotstream_runtime, "FILES", [row]), \
                 patch.object(measure, "SLOTSTREAM_EXTRA_FILES", []), redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError, "checksum"):
                    measure.verify_slotstream_weights(engine)
            self.assertEqual(path.read_bytes(), b"changed!")

    def test_repetitions_require_identity_bound_to_verified_weights(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.safetensors"
            path.write_bytes(b"original")
            install = {"ready": True, "mtp": True, "missing": [], "modelPath": directory,
                       "artifactIdentity": "original-artifact", "runtimeIdentity": "pinned-runtime"}
            row = {"path": path.name, "size": 8, "sha256": hashlib.sha256(b"original").hexdigest()}
            sidecar = Path(directory) / "sidecar.safetensors"
            sidecar.write_bytes(b"sidecar")
            extra = {"path": sidecar.name, "size": 7, "sha256": hashlib.sha256(b"sidecar").hexdigest()}
            engine = SimpleNamespace(argv=["fixture"], extra={"model": directory})
            with patch.object(measure.slotstream_runtime, "inspect_install", return_value=install), \
                 patch.object(measure.slotstream_runtime, "FILES", [row]), \
                 patch.object(measure, "SLOTSTREAM_EXTRA_FILES", [extra]), redirect_stdout(io.StringIO()):
                proof = measure.verify_slotstream_weights(engine)
                with patch.object(measure.slotstream_runtime, "digest", side_effect=AssertionError("unnecessary reread")):
                    self.assertIs(measure.verify_slotstream_weights(engine, proof), proof)
                for key in ("artifactIdentity", "runtimeIdentity"):
                    with self.subTest(key=key), patch.object(measure.slotstream_runtime, "inspect_install",
                                                           return_value={**install, key: "changed"}):
                        with self.assertRaisesRegex(ValueError, "changed"):
                            measure.verify_slotstream_weights(engine, proof)
                sidecar.write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "sidecar changed"):
                    measure.verify_slotstream_weights(engine, proof)


class ResourceGuardTests(unittest.TestCase):
    def guard(self, poll):
        guard = measure.ResourceGuard(SimpleNamespace(pid=123, poll=poll), 100, 10)
        guard.done = SimpleNamespace(wait=Mock(return_value=False))
        return guard

    def test_finished_process_is_not_queried_or_signalled(self):
        guard = self.guard(Mock(return_value=0))
        with patch.object(measure.darwin_memory, "physical_reclaimable_state") as memory, \
             patch.object(measure.os, "killpg") as signal_group:
            guard._watch()
        memory.assert_not_called()
        signal_group.assert_not_called()
        self.assertIsNone(guard.failure)

    def test_process_exiting_during_sample_is_not_a_telemetry_failure(self):
        guard = self.guard(Mock(side_effect=[None, 0]))
        with patch.object(measure.resource_telemetry, "physical_memory_bytes", return_value=100), \
             patch.object(measure.darwin_memory, "physical_reclaimable_state", return_value={"physicalMemoryAvailable": True, "reclaimableBytes": 50}), \
             patch.object(measure.resource_telemetry, "darwin_process_group_physical_footprint", return_value={"processGroupFootprintAvailable": False}), \
             patch.object(measure.resource_telemetry, "apple_process_resource_state", return_value={}), \
             patch.object(measure.os, "killpg") as signal_group:
            guard._watch()
        signal_group.assert_not_called()
        self.assertIsNone(guard.failure)

    def test_denied_stop_preserves_safety_failure_without_crashing_monitor(self):
        guard = self.guard(Mock(return_value=None))
        with patch.object(measure.resource_telemetry, "physical_memory_bytes", return_value=100), \
             patch.object(measure.darwin_memory, "physical_reclaimable_state", return_value={"physicalMemoryAvailable": True, "reclaimableBytes": 1}), \
             patch.object(measure.resource_telemetry, "darwin_process_group_physical_footprint", return_value={"processGroupFootprintAvailable": True, "processGroupPhysicalFootprintBytes": 20}), \
             patch.object(measure.resource_telemetry, "apple_process_resource_state", return_value={}), \
             patch.object(measure.os, "killpg", side_effect=PermissionError("fixture denied stop")):
            guard._watch()
        self.assertIn("memory reserve", guard.failure)
        self.assertIn("PermissionError", guard.failure)


class StrataInstalledFileTests(unittest.TestCase):
    """Use small stand-ins for a trusted installation receipt, then change its actual files."""
    def setUp(self):
        from bench import strata_stream_repack as preparation
        self.preparation = preparation
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.model, self.pack, runtime = root / "model", root / "pack", root / "runtime"
        self.model.mkdir()
        self.pack.mkdir()
        self.exe = runtime / "build-metal/strata"
        for path in [self.exe, runtime / "metal/kernels/fixture.metal", runtime / "serve/server.py",
                     runtime / "tools/strata_tokenizer.py", runtime / "third_party/llama.cpp/ggml/src/ggml-common.h",
                     runtime / "data/expert-profile.bin"]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture runtime bytes")
        for name in ["dense.bin", "index.txt", "native_experts.txt", "tokenizer/vocab.json", "tokenizer/chat_template.jinja"]:
            path = self.pack / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture pack bytes")

        def row(path, relative=False):
            return {"path": str(path.relative_to(self.pack)) if relative else str(path),
                    "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

        outputs = {}
        for key in ["native", "ple"]:
            path = self.model / f"{key}.gguf"
            path.write_bytes((key + " fixture bytes").encode())
            outputs[key] = row(path)
        self.prepared = {"status": "verified", "sourceRevision": preparation.REVISION,
                         "sources": preparation.SOURCES, "planSha256": "fixture-layout", "outputs": outputs,
                         "sourceProofs": {str(i): {"sha256": s["sha256"]} for i, s in enumerate(preparation.SOURCES)}}
        self.prepared_path = self.model / "verified-model.json"
        self.prepared_path.write_text(json.dumps(self.prepared))
        self.state_path = self.model / "stream-state.json"
        self.state_path.write_text(json.dumps({"stage": "complete", "planSha256": "fixture-layout"}))
        self.install = {"schemaVersion": 1, "status": "verified", "workDirectory": str(self.model),
                        "packDirectory": str(self.pack), "runtimeDirectory": str(runtime),
                        "runtimeFiles": [row(p) for p in measure.strata_runtime_files(runtime, self.exe)],
                        "preparedManifestSha256": hashlib.sha256(self.prepared_path.read_bytes()).hexdigest(),
                        "nativeOutputs": outputs, "expertIdentity": {"layers": 48, "expertsPerLayer": 512},
                        "packFiles": [row(p, True) for p in sorted(self.pack.rglob("*")) if p.is_file()]}
        self.manifest = root / "installed.json"
        self.manifest.write_text(json.dumps(self.install))
        self.engine = SimpleNamespace(extra={"_privateConfig": {"exe": str(self.exe), "args": [
            "--pack", str(self.pack), "--native", str(self.model / "native.gguf"),
            "--ple-gguf", str(self.model / "ple.gguf")]}})

    def tearDown(self):
        self.temp.cleanup()

    def test_native_host_pack_and_runtime_kernel_changes_are_detected(self):
        with redirect_stdout(io.StringIO()):
            proof = measure.verify_strata_weights(self.engine, self.manifest)
            self.assertIs(measure.verify_strata_weights(self.engine, self.manifest, proof), proof)
            for path in [self.model / "native.gguf", self.pack / "dense.bin",
                         self.exe.parent.parent / "metal/kernels/fixture.metal",
                         self.exe.parent.parent / "data/expert-profile.bin"]:
                original = path.read_bytes()
                path.write_bytes(bytes(value ^ 1 for value in original))
                with self.subTest(path=path), self.assertRaisesRegex(ValueError, "checksum"):
                    measure.verify_strata_weights(self.engine, self.manifest)
                with self.assertRaisesRegex(ValueError, "changed after verification"):
                    measure.verify_strata_weights(self.engine, self.manifest, proof)
                path.write_bytes(original)

    def test_incomplete_preparation_and_missing_source_proof_cannot_load(self):
        self.state_path.write_text(json.dumps({"stage": "downloading", "planSha256": "fixture-layout"}))
        with self.assertRaisesRegex(ValueError, "incomplete"):
            measure.verify_strata_weights(self.engine, self.manifest)
        self.state_path.write_text(json.dumps({"stage": "complete", "planSha256": "fixture-layout"}))
        self.prepared["sourceProofs"]["0"]["sha256"] = "missing proof"
        self.prepared_path.write_text(json.dumps(self.prepared))
        self.install["preparedManifestSha256"] = hashlib.sha256(self.prepared_path.read_bytes()).hexdigest()
        self.manifest.write_text(json.dumps(self.install))
        with self.assertRaisesRegex(ValueError, "pinned source verification"):
            measure.verify_strata_weights(self.engine, self.manifest)

    def test_unregistered_expert_pack_file_cannot_silently_change_loading(self):
        (self.pack / "experts.bin").write_bytes(b"unexpected alternative expert data")
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            measure.verify_strata_weights(self.engine, self.manifest)


class QualityContractTests(unittest.TestCase):
    def run_quality_fixture(self, *, wrong_answer=False, guard_failure=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompts = root / "bench/prompts"
            prompts.mkdir(parents=True)
            reference = "fixture ledger entry\n" * 100
            (prompts / measure.PROMPTS[32768]).write_text(reference)
            engines, requests = [], []
            answers = {"arithmetic": "405" if wrong_answer else "403", "json-tool": '{"status":"ready","count":3}',
                       "code": "def bounded_add(a, b, limit):\n    return min(a+b, limit)", "recall": "lattice"}

            def build(**options):
                engine = SimpleNamespace(argv=[sys.executable], env={}, extra={}, model_id="fixture",
                                         process=SimpleNamespace(pid=123), work_dir=options["work_dir"],
                                         wait_ready=Mock(), stop=Mock())
                engines.append(engine)
                return engine

            def request(engine, prompt, _tokens):
                requests.append((engine, prompt))
                content = "fixture continuation"
                for probe in measure.quality.PROBES:
                    if prompt == probe["prompt"]:
                        content = answers[probe["id"]]
                        break
                else:
                    if prompt != reference:
                        expected = measure.long_quality_prompt(reference)[1]
                        content = json.dumps({**expected, "arithmetic": 405} if wrong_answer else expected)
                return {"content": content, "cachedPromptTokens": 0,
                        "nativePrefillTokensPerSecond": 240, "nativeDecodeTokensPerSecond": 11}

            guard = SimpleNamespace(thread=SimpleNamespace(start=Mock()), stop=Mock(), failure=guard_failure, samples=[])
            with patch.object(measure, "ROOT", root), \
                 patch.object(measure.harness, "make_slotstream", side_effect=build), \
                 patch.object(measure.harness, "bench_run", side_effect=lambda *a, **k: nullcontext()), \
                 patch.object(measure, "verify_slotstream_weights", return_value={"install": {"fixture": True}}), \
                 patch.object(measure.slotstream_runtime, "doctor", return_value={"fixture": True}), \
                 patch.object(measure, "served_catalog", return_value={"fixture": True}), \
                 patch.object(measure.slotstream_runtime, "validate_served_catalog"), \
                 patch.object(measure.time, "sleep"), \
                 patch.object(measure, "start_clean"), patch.object(measure, "ResourceGuard", return_value=guard), \
                 patch.object(measure, "measured_chat", side_effect=request), redirect_stdout(io.StringIO()):
                options = ["--engine", "slotstream", "--context", "32768", "--reps", "2"]
                if guard_failure:
                    with self.assertRaisesRegex(RuntimeError, guard_failure):
                        measure.main(options)
                else:
                    self.assertEqual(measure.main(options), 2 if wrong_answer else 0)
            for engine in engines:
                engine.stop.assert_called_once()
            report = json.loads(next((root / "bench/results").glob("*.json")).read_text())
            return engines, requests, report

    def test_long_quality_probe_gets_its_own_fresh_engine(self):
        engines, requests, report = self.run_quality_fixture()
        self.assertEqual(len(engines), 3)
        self.assertEqual([sum(engine is e for e, _ in requests) for engine in engines], [5, 5, 1])
        self.assertIn("Independent audit fact", requests[-1][1])
        self.assertEqual(report["status"], "measured")
        self.assertEqual(len(report["measurements"]), 2)
        self.assertEqual(len(report["quality"]), 9)
        self.assertTrue(report["qualityPassed"])
        self.assertEqual([r["phase"] for r in report["runs"]], ["baseline", "baseline", "long-quality"])

    def test_wrong_answers_complete_all_samples_but_cannot_pass_quality(self):
        engines, requests, report = self.run_quality_fixture(wrong_answer=True)
        self.assertEqual(len(engines), 3)
        self.assertEqual(len(requests), 11)
        self.assertEqual(len(report["measurements"]), 2)
        self.assertEqual(report["status"], "failed-quality")
        self.assertFalse(report["qualityPassed"])
        self.assertEqual(report["qualitySummary"], {"passed": 6, "failed": 3, "total": 9, "complete": True})
        self.assertEqual([r["content"] for r in report["quality"] if r["probeId"] == "arithmetic"], ["405", "405"])
        self.assertEqual([r["passed"] for r in report["quality"]][-1], False)

    def test_resource_failure_still_aborts_remaining_workers_after_wrong_answer(self):
        engines, requests, report = self.run_quality_fixture(wrong_answer=True, guard_failure="Protected macOS reserve reached")
        self.assertEqual(len(engines), 1)
        self.assertEqual(len(requests), 5)
        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["qualityPassed"])
        self.assertIn("Protected macOS reserve reached", report["error"])
        self.assertEqual(len(report["quality"]), 4)

    def test_long_prompt_is_shared_deterministic_and_scored_without_changing_reference(self):
        original = "original ledger entry\n" * 1000
        prompt, expected, positions = measure.long_quality_prompt(original)
        self.assertEqual((prompt, expected, positions), measure.long_quality_prompt(original))
        self.assertEqual(original, "original ledger entry\n" * 1000)
        self.assertEqual(sorted(positions), ["early", "late", "middle"])
        self.assertTrue(measure.score_probe("long-recall", json.dumps(expected), expected))
        changed = {**expected, "middle": "invented"}
        self.assertFalse(measure.score_probe("long-recall", json.dumps(changed), expected))

    def test_scores_semantics_of_bounded_function_without_executing_model_code(self):
        self.assertTrue(measure.score_probe("code", "def bounded_add(a, b, limit):\n    return min(a+b, limit)"))
        self.assertTrue(measure.score_probe("code", "def bounded_add(a, b, limit):\n    return a+b if a+b < limit else limit"))
        self.assertFalse(measure.score_probe("code", "def bounded_add(a, b, limit):\n    return a+b"))
        self.assertFalse(measure.score_probe("code", "def bounded_add(a, b, limit):\n    return __import__('os').system('unexpected')"))
        self.assertTrue(measure.score_probe("arithmetic", "403"))
        self.assertTrue(measure.score_probe("arithmetic", "403.0"))
        self.assertFalse(measure.score_probe("arithmetic", "402"))
        self.assertFalse(measure.score_probe("arithmetic", "NaN"))


class StrataWireTests(unittest.TestCase):
    def test_real_loopback_stream_binds_native_count_and_preserves_exact_sampling(self):
        observed = []
        state = {"requests": 4}
        row = {"prompt_tokens": 1000, "output_tokens": 135, "engine_generated": 120,
               "prompt_read": 1000, "reused": 0, "decode_ms": 2000, "prompt_ms": 3000}
        timing = {"predicted_n": 135, "predicted_ms": 2000, "predicted_per_second": 60,
                  "prompt_n": 1000, "cache_n": 0, "prompt_ms": 3000}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                observed.append((self.path, self.headers.get("Authorization")))
                body = json.dumps({"totals": state, "live": {"state": "idle"}, "requests": [row]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                observed.append((self.path, self.headers.get("Authorization")))
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                observed.append(request)
                frames = [
                    {"choices": [{"delta": {"content": "hello"}}]},
                    {"choices": [{"delta": {"content": " world"}}]},
                    {"choices": [{"delta": {}, "finish_reason": "length"}],
                     "usage": {"prompt_tokens": 1000, "completion_tokens": 135, "total_tokens": 1135,
                               "prompt_tokens_details": {"cached_tokens": 0}}, "timings": timing},
                ]
                body = b"".join(b"data: " + json.dumps(frame).encode() + b"\n\n" for frame in frames) + b"data: [DONE]\n\n"
                state["requests"] += 1
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            engine = SimpleNamespace(name="strata", port=server.server_address[1], model_id="exact-model",
                                     api_key="fixture-private-bearer", extra={"backend": "strata"})
            result = measure.measured_chat(engine, "shared prompt", 135)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.assertEqual(result["content"], "hello world")
        self.assertEqual(result["nativeDecodeTokensPerSecond"], 60)
        self.assertAlmostEqual(result["nativePrefillTokensPerSecond"], 1000 / 3)
        request = next(value for value in observed if isinstance(value, dict))
        self.assertEqual({key: request[key] for key in ("temperature", "top_p", "top_k", "seed", "reasoning_effort")},
                         {"temperature": 0, "top_p": 1, "top_k": 0, "seed": 42, "reasoning_effort": "none"})
        self.assertTrue(all(value[1] == "Bearer fixture-private-bearer" for value in observed if isinstance(value, tuple)))


if __name__ == "__main__":
    unittest.main()
