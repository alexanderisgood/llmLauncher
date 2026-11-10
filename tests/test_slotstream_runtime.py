"""Slotstream launch and contract regression tests; no model is loaded."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import launcher
import session_proxy
import slotstream_runtime as native


class SlotstreamTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="slotstream-test-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.binary = self.root / "slotstream"
        self.binary.write_bytes(b"test-executable")
        self.binary.chmod(0o755)
        (self.root / "mlx.metallib").write_bytes(b"test-metal")
        hashes = {name: native.digest(self.root / name) for name in native.RUNTIME_HASHES}
        self.model_path = self.root / "model"
        self.model_path.mkdir()
        files = []
        for name in ("config.json", "tokenizer.json", "model-00001.safetensors", "mtp.safetensors"):
            data = b"{}" if name.endswith("json") else b"fixture-weight"
            (self.model_path / name).write_bytes(data)
            files.append({"path":name, "size":len(data), "sha256":hashlib.sha256(data).hexdigest(), "optional":name.startswith("mtp")})
        for patch in (mock.patch.object(native, "RUNTIME_HASHES", hashes), mock.patch.object(native, "FILES", files), mock.patch.object(native, "discover_q8", return_value=None)):
            patch.start(); self.addCleanup(patch.stop)
        native._verify_runtime.cache_clear()
        self.install = native.inspect_install(str(self.binary), self.model_path)
        self.model = native.model_record(self.install, [(k,v.label) for k,v in launcher.ENGINE_ADAPTERS.items()], 48*1024**3)
        self.cap = self.model["backends"]["slotstream"]

    def request(self, **changes):
        return {"backend":"slotstream", "client":"chat", "modelId":self.model["id"],
                "project":str(self.root), "context":65536, "output":8192, "reasoning":"medium",
                "options":{"acceleration":"mtp", "depth":2, "memoryGB":34, "memoryMode":"fixed", "kv":"off"}, **changes}

    def build(self, **changes):
        with mock.patch.dict(launcher.BINARIES, {"slotstream":str(self.binary)}), \
             mock.patch.object(launcher, "RUNS_DIR", self.root / "runs"), \
             mock.patch.object(launcher, "STATE_DIR", self.root / "state"), \
             mock.patch.object(native, "doctor", return_value={"mtp":True}), \
             mock.patch.object(launcher, "free_port", side_effect=[18091,18092]):
            return launcher.normalized_request(self.request(**changes), [self.model])

    def test_registry_and_capabilities(self):
        launcher.validate_adapter_registries()
        self.assertEqual(set(self.model["backends"]), set(launcher.ENGINE_ADAPTERS))
        self.assertTrue(self.cap["mtp"])
        self.assertEqual(self.cap["contextWindows"], list(native.CONTEXTS))
        for name, cap in self.model["backends"].items():
            self.assertEqual(cap["runnable"], name == "slotstream")
        for client in ("chat", "pi", "opencode"):
            self.assertTrue(launcher.resolved_client_support("slotstream", client, self.cap)["supported"])
        self.assertFalse(launcher.resolved_client_support("slotstream", "codex", self.cap)["supported"])

    def test_incomplete_and_corrupted_metadata_never_ready(self):
        (self.model_path / "config.json").write_bytes(b"[]")
        self.assertFalse(native.inspect_install(str(self.binary), self.model_path)["ready"])
        (self.model_path / "config.json").write_bytes(b"{}")
        (self.model_path / "model-00001.safetensors").unlink()
        self.assertFalse(native.inspect_install(str(self.binary), self.model_path)["ready"])

    def test_missing_head_allows_ar_but_cannot_enable_mtp(self):
        (self.model_path / "mtp.safetensors").unlink()
        installed = native.inspect_install(str(self.binary), self.model_path)
        self.assertTrue(installed["ready"])
        self.assertFalse(installed["mtp"])
        cap = {**self.cap, "mtp":False}
        with self.assertRaisesRegex(ValueError, "MTP head"):
            launcher.validated_profile_options("slotstream", self.model, cap, {"acceleration":"mtp"})
        auto = launcher.validated_profile_options("slotstream", self.model, cap, {})
        self.assertEqual(auto["acceleration"], "off")

    def test_runtime_replacement_invalidates_cached_hash(self):
        self.binary.write_bytes(b"bad!-executable")
        with self.assertRaisesRegex(ValueError, "audited release"):
            native.inspect_install(str(self.binary), self.model_path)

    def test_weight_replacement_invalidates_evidence_and_launch(self):
        (self.model_path / "model-00001.safetensors").write_bytes(b"changed-weight")
        new = native.inspect_install(str(self.binary), self.model_path)
        self.assertNotEqual(new["artifactIdentity"], self.install["artifactIdentity"])
        with self.assertRaisesRegex(ValueError, "changed"):
            self.build()

    def test_symlinked_model_file_rejected(self):
        path = self.model_path / "tokenizer.json"
        path.unlink(); path.symlink_to(self.model_path / "config.json")
        self.assertFalse(native.inspect_install(str(self.binary), self.model_path)["ready"])

    def test_explicit_launch_keeps_context_mtp_depth_memory_and_private_port(self):
        plan = self.build()
        argv = json.loads(Path(plan.engine_argv[-1]).read_text())["argv"]
        for key, value in (("--max-context","65536"),("--mtp","on"),("--memory-gb","34"),("--vision","off")):
            self.assertEqual(argv[argv.index(key)+1], value)
        self.assertEqual(argv[:2], [str(self.binary.resolve()), "serve"])
        self.assertEqual(plan.engine_env, {"SLOTSTREAM_DRAFT_DEPTH":"2"})
        self.assertEqual(plan.output,8192)
        self.assertEqual(plan.model["servedId"],native.MODEL_ID)
        self.assertNotEqual(plan.port,plan.client_port)
        self.assertTrue(plan.secrets["clientApiKey"])
        self.assertTrue(session_proxy._valid_secret(plan.secrets.get("apiKey")))
        self.assertEqual(plan.reasoning,"medium")
        off = self.build(options={"acceleration":"off", "memoryGB":28, "memoryMode":"fixed"})
        off_argv = json.loads(Path(off.engine_argv[-1]).read_text())["argv"]
        self.assertEqual(off_argv[off_argv.index("--mtp")+1],"off")

    def test_options_fail_closed_and_auto_is_explicit(self):
        options = launcher.validated_profile_options("slotstream",self.model,self.cap,{})
        self.assertEqual((options["acceleration"],options["depth"],options["memoryGB"]),("mtp",2,36))
        self.assertEqual(launcher.validated_profile_options("slotstream",self.model,self.cap,{"acceleration":"auto","depth":3})["depth"],2)
        for bad in ({"acceleration":"dflash"},{"depth":17,"acceleration":"mtp"},{"memoryGB":11},{"memoryGB":True},{"kv":"q4"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                launcher.validated_profile_options("slotstream",self.model,self.cap,bad)
        with self.assertRaises(ValueError): self.build(context=48000)
        with self.assertRaises(ValueError): self.build(output=65536)
        with self.assertRaises(ValueError): self.build(client="codex")

    def test_memory_budget_above_36_survives_validation_and_launch(self):
        for budget in (40, 48, 64, 128):
            with self.subTest(budget=budget):
                request = self.request(options={"acceleration":"mtp", "depth":2,
                                               "memoryGB":budget, "memoryMode":"fixed"})
                plan = self.build(options=request["options"])
                self.assertEqual(plan.options["memoryGB"], budget)
                argv = json.loads(Path(plan.engine_argv[-1]).read_text())["argv"]
                self.assertEqual(argv[argv.index("--memory-gb")+1], str(budget))
                estimate = launcher.launch_memory_estimate(request, self.model,
                    {"totalMemoryBytes":192*1024**3, "headroomBytes":160*1024**3})
                self.assertEqual(estimate["estimatedWorkingSetBytes"], budget*1_000_000_000)
        for value in (11, True, 36.5, "invalid", float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                launcher.validated_profile_options("slotstream", self.model, self.cap, {"memoryGB":value})

    def test_memory_admission_uses_process_budget_not_ssd_weight_size(self):
        resource={"memoryAvailable":True,"totalMemoryBytes":48*1024**3,"headroomBytes":42*1024**3}
        with mock.patch.dict(launcher.BINARIES,{"slotstream":str(self.binary)}):
            good=launcher.session_memory_admission(self.request(),[self.model],resource,{"phase":"idle"},{})
            bad=launcher.session_memory_admission(self.request(),[self.model],{**resource,"headroomBytes":20*1024**3},{"phase":"idle"},{})
        self.assertTrue(good["launchable"],good)
        self.assertEqual(good["estimate"]["estimatedWorkingSetBytes"],34_000_000_000)
        self.assertFalse(bad["launchable"])

    def test_doctor_refusal_and_mtp_downgrade_rejected(self):
        options=launcher.validated_profile_options("slotstream",self.model,self.cap,{})
        valid={"source":"auto","mtp":True,"vision":False,"max_context_tokens":65536,
               "memory_ledger":{"expected_peak_bytes":29_000_000_000}}
        for result in (subprocess.CompletedProcess([],2,json.dumps({"error":{"message":"insufficient memory"}}),""),
                       subprocess.CompletedProcess([],0,json.dumps({**valid,"mtp":False}),"")):
            with mock.patch.object(subprocess,"run",return_value=result),self.assertRaises(ValueError):
                native.doctor(self.install,65536,options)
        with mock.patch.object(subprocess,"run",return_value=subprocess.CompletedProcess([],0,json.dumps(valid),"")) as run:
            self.assertEqual(native.doctor(self.install,65536,options),valid)
            self.assertIn("--json",run.call_args.args[0])

    def test_doctor_plans_with_the_q8_optimization_environment(self):
        """The capacity check must see the 4,096-token prefill pass and the
        read-path switches, or it promises an expert pool the launch cannot
        keep (18.9 GB planned vs 16.1 GB delivered)."""
        options = {"acceleration":"mtp", "depth":2, "memoryGB":34, "memoryMode":"fixed", "kv":"q8"}
        valid = {"source":"--memory-gb","mtp":True,"vision":False,"max_context_tokens":65536,
                 "kv_cache_bits":8,"kv_cache_group_size":64,
                 "memory_ledger":{"expected_peak_bytes":29_000_000_000}}
        q8_install = {**self.install, "runtimeVersion": native.Q8_VERSION}
        with mock.patch.object(subprocess,"run",return_value=subprocess.CompletedProcess([],0,json.dumps(valid),"")) as run:
            native.doctor(q8_install, 65536, {**options, "kv": "q8"})
        env = run.call_args.kwargs["env"]
        self.assertEqual(env["SLOTSTREAM_PREFILL_CHUNK"], "4096")
        self.assertEqual(env["SLOTSTREAM_OPT_READ_SCOPE"], "8192")
        self.assertEqual(env["SLOTSTREAM_OPT_RESIDENT_OVERLAP"], "1")
        self.assertEqual(env["SLOTSTREAM_OPT_WORKSPACE_TILE"], "4096")
        self.assertEqual(env["SLOTSTREAM_DRAFT_DEPTH"], str(options["depth"]))
        # Full-precision launches keep the planner's own defaults.
        with mock.patch.object(subprocess,"run",return_value=subprocess.CompletedProcess([],0,json.dumps(valid),"")) as run:
            native.doctor(self.install, 65536, {**options, "kv": "off"})
        self.assertNotIn("SLOTSTREAM_PREFILL_CHUNK", run.call_args.kwargs["env"])

    def test_large_response_uses_selected_context_not_a_32k_cap(self):
        plan = self.build(context=131072, output=100000)
        self.assertEqual((plan.context, plan.output), (131072, 100000))
        with self.assertRaises(ValueError):
            self.build(context=131072, output=131000)

    def test_automatic_memory_uses_native_sizing_with_user_ceiling(self):
        options = {"acceleration":"mtp", "depth":2, "memoryGB":30, "memoryMode":"auto"}
        with mock.patch.object(os, "sysconf", side_effect=[3_000_000, 16384]):
            args = native.planning_arguments(self.install, 131072, options)
        self.assertNotIn("--memory-gb", args)
        self.assertAlmostEqual(float(args[args.index("--max-ram-percent")+1]), 30e9/(3e6*16384)*100, places=5)
        self.assertEqual(args[args.index("--max-context")+1], "131072")
        self.assertEqual(args[args.index("--mtp")+1], "on")
        resource = {"memoryAvailable":True, "totalMemoryBytes":48*1024**3, "headroomBytes":24*1024**3}
        with mock.patch.dict(launcher.BINARIES, {"slotstream":str(self.binary)}):
            admission = launcher.session_memory_admission(self.request(options=options), [self.model], resource, {"phase":"idle"}, {})
        self.assertTrue(admission["launchable"], admission)
        self.assertLess(admission["estimate"]["estimatedWorkingSetBytes"],30e9)

    def test_ready_server_must_advertise_the_exact_selected_context(self):
        row={"id":native.MODEL_ID,"owned_by":"slotstream","context_window":65536,"context_length":65536,
             "context_policy":{"configured_window":65536,"allocation_available":True}}
        native.validate_served_catalog({"data":[row]},65536)
        for bad in ({**row,"context_window":16384},{**row,"owned_by":"other"},
                    {**row,"context_policy":{"configured_window":65536,"allocation_available":False}}):
            with self.assertRaises(RuntimeError):native.validate_served_catalog({"data":[bad]},65536)

    def test_environment_cannot_inherit_experiments(self):
        self.assertEqual(native.clean_environment({"PATH":"/bin","SLOTSTREAM_DRAFT_DEPTH":"16","SLOTSTREAM_EXPERT_LOOKAHEAD":"1","MLX_DEVICE":"cpu","DYLD_INSERT_LIBRARIES":"evil"}),{"PATH":"/bin"})

    def test_chat_and_agent_reasoning_contract_agree(self):
        for effort in native.REASONING:
            with self.subTest(effort=effort):
                body={"messages":[{"role":"user","content":"hello"}],"model":native.MODEL_ID,
                      "reasoning_effort":"high","think":True,"max_tokens":9000}
                local=launcher.apply_chat_reasoning_contract(copy.deepcopy(body),"slotstream",effort)
                config={"backend":"slotstream","reasoning":effort,"outputLimit":8192,"servedModel":native.MODEL_ID}
                proxied=json.loads(session_proxy.transform_chat_request(json.dumps(body).encode(),config))
                self.assertEqual(proxied.get("reasoning_effort"),local.get("reasoning_effort"))
                self.assertNotIn("think",proxied)
                self.assertEqual(proxied["max_tokens"],8192)

    def test_greedy_benchmark_probe_uses_only_supported_native_fields(self):
        plan = self.build()
        request = launcher.build_benchmark_completion_request(
            plan, "Reply with the number 42.", 128,
            launcher.BENCHMARK_PROBE_CONTRACT["sampling"], greedy_probe=True,
        )
        body = json.loads(request.data)
        for key, value in launcher.BENCHMARK_PROBE_CONTRACT["sampling"].items():
            self.assertEqual(body[key], value)
        self.assertNotIn("frequency_penalty", body)
        self.assertNotIn("repetition_penalty", body)
        self.assertEqual(body["reasoning_effort"], "medium")

    def test_startup_verifies_weights_before_exec_and_stops_on_failure(self):
        plan = self.build()
        with mock.patch.object(subprocess,"run",return_value=subprocess.CompletedProcess([],0)), \
             mock.patch.object(os,"execve") as execute:
            native.run_verified(Path(plan.engine_argv[-1]))
            execute.assert_called_once()
            self.assertEqual(execute.call_args.args[1][1], "serve")
            self.assertEqual(execute.call_args.args[2]["SLOTSTREAM_DRAFT_DEPTH"], "2")
        with mock.patch.object(subprocess,"run",side_effect=subprocess.CalledProcessError(1,[])), \
             mock.patch.object(os,"execve") as execute, self.assertRaises(subprocess.CalledProcessError):
            native.run_verified(Path(plan.engine_argv[-1]))
        execute.assert_not_called()

    def test_q8_requires_a_qualified_separate_install(self):
        with self.assertRaisesRegex(ValueError, "KV precision"):
            launcher.validated_profile_options("slotstream", self.model, self.cap, {"kv":"q8"})
        q8_dir = self.root / "q8"
        q8_dir.mkdir()
        binary = q8_dir / "slotstream"
        binary.write_bytes(b"q8-engine"); binary.chmod(0o755)
        (q8_dir / "mlx.metallib").write_bytes(b"q8-metal")
        hashes = {name:native.digest(q8_dir / name) for name in native.RUNTIME_HASHES}
        manifest = self.root / "q8-manifest.json"
        manifest.write_text(json.dumps({"version":native.Q8_VERSION,"qualified":True,"runtimeHashes":hashes}))
        with mock.patch.object(native, "Q8_BINARY", binary), mock.patch.object(native, "Q8_MANIFEST_PATH", manifest):
            q8 = native.inspect_install(str(binary), self.model_path)
            self.assertEqual(q8["runtimeVersion"], native.Q8_VERSION)
            self.model["slotstreamQ8"] = q8
            self.cap["kv"] = True
            plan = self.build(options={"kv":"q8", "acceleration":"mtp", "depth":2,"memoryGB":34})
            config = json.loads(Path(plan.engine_argv[-1]).read_text())
            self.assertEqual(config["install"], q8)
            self.assertEqual(config["argv"][0], str(binary.resolve()))
            self.assertEqual(plan.runtime_binary, str(binary.resolve()))
            self.assertEqual(plan.model["slotstream"], q8)
            self.assertEqual(plan.options["kv"], "q8")
            self.assertEqual(plan.public()["runtimeVersion"], native.Q8_VERSION)
            self.assertEqual(plan.context, 65536)
            # The measured read-path switches ride on every Q8 launch.
            self.assertEqual(plan.engine_env["SLOTSTREAM_OPT_READ_SCOPE"], "8192")
            self.assertEqual(plan.engine_env["SLOTSTREAM_PREFILL_CHUNK"], "4096")
            self.assertEqual(plan.engine_env["SLOTSTREAM_OPT_RESIDENT_OVERLAP"], "1")
            self.assertEqual(plan.engine_env["SLOTSTREAM_OPT_LAYER_WORKSPACE"], "1")
            self.assertEqual(plan.engine_env["SLOTSTREAM_OPT_COMPACT_STATE"], "1")
            self.assertEqual(plan.engine_env["SLOTSTREAM_OPT_COMPACT_MTP"], "1")
            self.assertEqual(plan.engine_env["SLOTSTREAM_OPT_INDEXER_TILES"], "1")
            self.assertEqual(plan.engine_env["SLOTSTREAM_OPT_PLE_TILES"], "1")
            self.assertEqual(plan.engine_env["SLOTSTREAM_OPT_WORKSPACE_TILE"], "4096")
            self.assertEqual(plan.engine_env["SLOTSTREAM_DRAFT_DEPTH"], "2")
            with self.assertRaisesRegex(ValueError, "does not match"):
                native.planning_arguments(self.install, 65536, plan.options)
            with self.assertRaisesRegex(ValueError, "does not match"):
                native.planning_arguments(q8, 65536, {**plan.options,"kv":"off"})
            manifest.write_text(json.dumps({"version":native.Q8_VERSION,"qualified":False,"runtimeHashes":hashes}))
            with self.assertRaisesRegex(ValueError, "qualification"):
                native.inspect_install(str(binary), self.model_path)

    def test_q8_catalog_must_confirm_bits_and_group_size(self):
        row={"id":native.MODEL_ID,"owned_by":"slotstream","context_window":65536,"context_length":65536,
             "context_policy":{"configured_window":65536,"allocation_available":True}}
        with self.assertRaisesRegex(RuntimeError,"Q8"):
            native.validate_served_catalog({"data":[row]},65536,"q8")
        q8={**row,"kv_cache_bits":8,"kv_cache_group_size":64}
        native.validate_served_catalog({"data":[q8]},65536,"q8")
        with self.assertRaisesRegex(RuntimeError,"full-precision"):
            native.validate_served_catalog({"data":[q8]},65536,"off")

    def test_scan_is_read_only_and_exposes_partial_download(self):
        with mock.patch.dict(launcher.BINARIES,{name:None for name in launcher.BINARIES},clear=True), \
             mock.patch.object(launcher,"model_roots",return_value=[]), \
             mock.patch.object(native,"discover",return_value={**self.install,"ready":False,"missing":["model-00001.safetensors"]}), \
             mock.patch.object(launcher,"probe_whallm_endpoint",return_value={}), \
             mock.patch.object(launcher,"load_freetoken_connection",return_value={}), \
             mock.patch.object(native,"doctor") as doctor:
            models=launcher.scan_models()
        found=next(x for x in models if x.get("slotstream"))
        self.assertFalse(found["ready"])
        doctor.assert_not_called()


if __name__ == "__main__":
    unittest.main()
