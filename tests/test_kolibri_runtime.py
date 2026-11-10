"""Memory admission and route boundaries, without loading a real model."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest import mock

import kolibri_runtime as route
import launcher
import darwin_memory
import resource_telemetry


GIB = 1024**3
MODEL = {
    "path": "/fixture/kolibri", "identity": "fixture-model", "weightBytes": 63517990178,
    "trunkBytes": 2176069120, "expertBytes": 61341696000, "slotBytes": 159744000,
    "expertCount": 384, "topK": 6, "layers": 50, "fullAttentionLayers": 10,
    "slidingAttentionLayers": 40, "slidingWindow": 513, "kvBytesPerTokenPerLayer": 2048,
}
RESOURCE = {"memoryAvailable": True, "totalMemoryBytes": 48*GIB,
            "headroomBytes": int(48*GIB*.80), "metalRecommendedWorkingSetBytes": 40200896512}
RUNTIME = {"python": "/fixture/python", "version": route.VERSION, "identity": "fixture-runtime", "ready": True}


class MemoryTests(unittest.TestCase):
    def test_worker_uses_physical_capacity_even_when_pressure_looks_healthy(self):
        sample={"totalBytes":48*GIB,"memoryAvailable":True,"freePercent":90,
                "memorySemanticsVersion":2,"physicalMemoryAvailable":True,
                "reclaimableBytes":18*GIB,"reclaimableMemorySource":"host_statistics64"}
        with mock.patch.object(resource_telemetry,"apple_memory_pressure_state",return_value=sample), \
                mock.patch.object(route.subprocess,"run",side_effect=AssertionError("spawned memory helper")):
            resource=route.current_resource(40*GIB)
        self.assertEqual(resource["headroomBytes"],18*GIB)
        self.assertEqual(resource["memorySource"],"host_statistics64")
        self.assertEqual(resource["metalRecommendedWorkingSetBytes"],40*GIB)
        plan=route.memory_plan(MODEL,8192,{},resource)
        self.assertTrue(plan["ready"])
        self.assertLessEqual(plan["requiredHeadroomBytes"],18*GIB)

    def test_worker_does_not_fall_back_to_pressure_for_missing_physical_capacity(self):
        with mock.patch.object(resource_telemetry,"apple_memory_pressure_state",return_value={
                "totalBytes":48*GIB,"memoryAvailable":True,"freePercent":99}):
            with self.assertRaisesRegex(ValueError,"physical memory headroom"):
                route.current_resource()

    def test_isolated_worker_rejects_memory_module_from_an_unexpected_location(self):
        from types import SimpleNamespace
        with mock.patch.dict(sys.modules,{"darwin_memory":SimpleNamespace(__file__="/private/tmp/unrelated-memory.py")}):
            with self.assertRaisesRegex(ValueError,"unexpected source"):
                route.current_resource()

    def test_auto_uses_most_available_memory_with_all_reserves(self):
        plan = route.memory_plan(MODEL,8192,{},RESOURCE)
        self.assertTrue(plan["ready"])
        self.assertGreater(plan["expertCacheBytes"], 27*GIB)
        self.assertGreater(plan["residentWeightBytes"],32_000_000_000)
        self.assertLessEqual(plan["requiredHeadroomBytes"],RESOURCE["headroomBytes"])
        self.assertGreater(plan["requiredHeadroomBytes"] + MODEL["slotBytes"],RESOURCE["headroomBytes"])
        self.assertGreater(plan["runtimeReserveBytes"],3*GIB)

    def test_pressure_shrinks_experts_and_preserves_context(self):
        low = {**RESOURCE,"headroomBytes":24*GIB}
        roomy = route.memory_plan(MODEL,8192,{},RESOURCE)
        plan = route.memory_plan(MODEL,8192,{},low)
        self.assertTrue(plan["ready"])
        self.assertLess(plan["expertCacheBytes"],roomy["expertCacheBytes"])
        self.assertEqual(plan["contextTokens"],8192)
        self.assertEqual(plan["kvCacheBytes"],roomy["kvCacheBytes"])

    def test_metal_limit_bounds_expert_allocation(self):
        plan=route.memory_plan(MODEL,8192,{}, {**RESOURCE,"metalRecommendedWorkingSetBytes":26*GIB})
        self.assertTrue(plan["ready"])
        self.assertLessEqual(plan["estimatedWorkingSetBytes"],26*GIB)

    def test_larger_mac_can_cache_all_experts(self):
        resource={"memoryAvailable":True,"totalMemoryBytes":128*GIB,"headroomBytes":100*GIB,
                  "metalRecommendedWorkingSetBytes":96*GIB}
        plan=route.memory_plan(MODEL,8192,{"memoryGB":96},resource)
        self.assertTrue(plan["ready"])
        self.assertEqual(plan["residentExpertsPerLayer"],384)
        self.assertAlmostEqual(plan["residentWeightFraction"],1,places=4)

    def test_fixed_budget_cannot_silently_shrink_under_pressure(self):
        plan=route.memory_plan(MODEL,8192,{"memoryMode":"fixed","memoryGB":40},RESOURCE)
        self.assertFalse(plan["ready"])

    def test_no_headroom_and_unknown_memory_are_blocked(self):
        for resource in ({}, {**RESOURCE,"memoryAvailable":False}, {**RESOURCE,"headroomBytes":6*GIB}):
            with self.subTest(resource=resource):
                self.assertFalse(route.memory_plan(MODEL,8192,{},resource)["ready"])

    def test_contract_rejects_unqualified_context_and_invalid_ceiling(self):
        for context, options in [(524288,{}),(8192,{"memoryGB":True}),(8192,{"memoryGB":7}),(8192,{"memoryMode":"unbounded"}),
                                 (8192,{"kv":"q3"}), (8192,{"prefillSize":255}), (8192,{"promptCacheGB":9})]:
            with self.subTest(context=context,options=options), self.assertRaises(ValueError):
                route.memory_plan(MODEL,context,options,RESOURCE)

    def test_native_256k_and_all_cache_precisions_fit_with_small_prefill(self):
        for kv in route.KV_CHOICES:
            with self.subTest(kv=kv):
                plan = route.memory_plan(MODEL,262144,{"kv":kv,"prefillSize":64},RESOURCE)
                self.assertTrue(plan["ready"])
                self.assertEqual(plan["contextTokens"],262144)
                self.assertGreaterEqual(plan["residentExpertsPerLayer"],6)
                self.assertLessEqual(plan["requiredHeadroomBytes"],RESOURCE["headroomBytes"])

    def test_quantized_cache_counts_packing_metadata_and_keeps_sliding_bf16(self):
        baseline = route.memory_plan(MODEL,262144,{"prefillSize":64},RESOURCE)
        for kv, bytes_per_token in (("q8",1088),("q6",832),("q4",576)):
            with self.subTest(kv=kv):
                plan = route.memory_plan(MODEL,262144,{"kv":kv,"prefillSize":64},RESOURCE)
                self.assertEqual(plan["fullAttentionKvBytes"],bytes_per_token*262144*10)
                self.assertEqual(plan["slidingAttentionKvBytes"],baseline["slidingAttentionKvBytes"])
                self.assertEqual(plan["quantizedKvLayers"],10)
                self.assertEqual(plan["fullPrecisionKvLayers"],40)
                self.assertLess(plan["kvCacheBytes"],baseline["kvCacheBytes"])

    def test_prefill_and_retained_cache_reduce_experts_without_lowering_context(self):
        small = route.memory_plan(MODEL,131072,{"kv":"q8","prefillSize":64,"promptCacheGB":1},RESOURCE)
        big = route.memory_plan(MODEL,131072,{"kv":"q8","prefillSize":256,"promptCacheGB":4},RESOURCE)
        self.assertTrue(big["ready"])
        self.assertLess(big["residentExpertsPerLayer"],small["residentExpertsPerLayer"])
        self.assertEqual(big["contextTokens"],131072)
        self.assertEqual(big["promptCacheBytes"],4*GIB)
        self.assertGreater(big["attentionWorkspaceBytes"],small["attentionWorkspaceBytes"])
        impossible = route.memory_plan(MODEL,262144,{"kv":"q4","prefillSize":2048},RESOURCE)
        self.assertFalse(impossible["ready"])


class BoundaryTests(unittest.TestCase):
    def body(self, **changes):
        return {"model":route.MODEL_ID,"messages":[{"role":"user","content":"synthetic request"}],"max_tokens":512,**changes}

    def test_reasoning_and_response_ceiling_are_locked(self):
        body=route.checked_chat_body(self.body(),8192,1024,"off")
        self.assertEqual(body["chat_template_kwargs"],{"reasoning_effort":"none"})
        for changes in ({"reasoning_effort":"high"},{"max_tokens":1025},{"max_completion_tokens":False},{"chat_template_kwargs":{"reasoning_effort":"high"}}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                route.checked_chat_body(self.body(**changes),8192,1024,"off")

    def test_unknown_model_images_and_tools_fail_closed(self):
        for changes in ({"model":"unrelated"},{"tools":[{"type":"function"}]},
                        {"messages":[{"role":"user","content":[{"type":"image_url"}]}]}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                route.checked_chat_body(self.body(**changes),8192,1024,"off")

    def test_live_catalog_must_confirm_exact_context_and_memory(self):
        memory=route.memory_plan(MODEL,8192,{},RESOURCE)
        catalog={"data":[{"id":route.MODEL_ID,"max_context_length":8192}],"kolibri":memory}
        self.assertEqual(route.validate_served_catalog(catalog,8192),memory)
        with self.assertRaises(ValueError):
            route.validate_served_catalog(catalog,4096)
        del catalog["kolibri"]
        with self.assertRaises(ValueError):
            route.validate_served_catalog(catalog,8192)

    def test_live_catalog_locks_quantization_prefill_and_retained_cache(self):
        options = {"kv":"q6","prefillSize":64,"promptCacheGB":4}
        memory = route.memory_plan(MODEL,262144,options,RESOURCE)
        catalog = {"data":[{"id":route.MODEL_ID,"max_context_length":262144}],"kolibri":memory}
        self.assertEqual(route.validate_served_catalog(catalog,262144,options),memory)
        for changed in ({"kv":"off"},{"prefillSize":256},{"promptCacheGB":1}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                route.validate_served_catalog(catalog,262144,{**options,**changed})

    def test_requests_cannot_override_launched_kv_precision(self):
        for field in ("kv_bits","kv_group_size","quantized_kv_start"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                route.checked_chat_body(self.body(**{field:4}),8192,1024,"off")

    def test_runtime_source_changes_invalidate_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            python=root/"runtime/bin/python"; python.parent.mkdir(parents=True)
            python.write_text("fixture"); python.chmod(0o700)
            packages=root/"runtime/lib/python3.11/site-packages"
            for name,version in route.RUNTIME_VERSIONS.items():
                metadata=packages/f"{name}-{version}.dist-info/METADATA"
                metadata.parent.mkdir(parents=True); metadata.write_text(f"Version: {version}\n")
            server=packages/"mlx_lm/server.py"; server.parent.mkdir(); server.write_text("fixture")
            vendor=root/"vendor"; vendor.mkdir(); worker=vendor/"worker.py"; worker.write_text("reviewed")
            (vendor/"provenance.json").write_text(json.dumps({"sha256":{"worker.py":hashlib.sha256(worker.read_bytes()).hexdigest()}}))
            with mock.patch.object(route,"VENDOR",vendor),mock.patch.object(route.platform,"system",return_value="Darwin"),mock.patch.object(route.platform,"machine",return_value="arm64"):
                self.assertTrue(route.inspect_runtime(str(python))["ready"])
                worker.write_text("changed")
                self.assertIsNone(route.inspect_runtime(str(python)))

    def test_inherited_memory_and_execution_overrides_are_removed(self):
        env={"MLX_MEMORY_LIMIT":"999","STREAMLX_RESIDENT":"auto","PYTHONPATH":"unreviewed",
             "DYLD_INSERT_LIBRARIES":"unexpected","PATH":"normal"}
        self.assertEqual(route.clean_environment(env),{"PATH":"normal"})


class LauncherTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); self.root=Path(tmp.name)
        cap=route.capability(MODEL,RUNTIME)
        self.model={"id":"fixture-model","path":MODEL["path"],"name":"Kolibri Q6",
                    "modelType":"kolibri1","ready":True,"size":MODEL["weightBytes"],"nativeContext":262144,
                    "defaultOutput":route.DEFAULT_OUTPUT,"outputMaximum":route.OUTPUT_MAXIMUM,"defaultSampling":{"temperature":1,"top_p":.97,"top_k":128},
                    "kolibri":MODEL,"backends":{"kolibri":cap}}
        self.request={"backend":"kolibri","client":"chat","modelId":self.model["id"],"project":str(self.root),
                      "context":8192,"output":1024,"reasoning":"off","options":{"memoryMode":"auto","memoryGB":40}}

    def test_registry_and_agent_compatibility(self):
        launcher.validate_adapter_registries()
        self.assertTrue(launcher.resolved_client_support("kolibri","chat",self.model["backends"]["kolibri"])["supported"])
        self.assertTrue(launcher.resolved_client_support("kolibri","pi",self.model["backends"]["kolibri"])["supported"])
        for client in ("opencode","codex"):
            self.assertFalse(launcher.resolved_client_support("kolibri",client,self.model["backends"]["kolibri"])["supported"])

    def test_plan_preserves_settings_and_uses_owned_private_auth(self):
        with mock.patch.dict(launcher.BINARIES,{"kolibri":"/fixture/python"}), \
             mock.patch.object(launcher,"RUNS_DIR",self.root/"runs"), \
             mock.patch.object(launcher,"free_port",side_effect=[18091,18092]), \
             mock.patch.object(route,"inspect_runtime",return_value=RUNTIME), \
             mock.patch.object(route,"inspect_model",return_value=MODEL), \
             mock.patch.object(route,"current_resource",return_value=RESOURCE):
            plan=launcher.normalized_request(self.request,[self.model])
        config= json.loads(Path(plan.engine_argv[-1]).read_text())
        self.assertEqual((config["context"],config["output"],config["reasoning"]),(8192,1024,"off"))
        self.assertGreater(plan.options["_kolibriMemoryPlan"]["expertCacheBytes"],27*GIB)
        self.assertEqual(config["apiKey"],plan.secrets["apiKey"])
        self.assertNotEqual(plan.secrets["apiKey"],plan.secrets["clientApiKey"])
        self.assertNotIn(config["apiKey"],json.dumps(plan.public()))
        self.assertEqual(Path(plan.engine_argv[-1]).stat().st_mode & 0o777,0o600)

    def test_model_changes_after_scan_block_launch(self):
        changed={**MODEL,"identity":"changed"}
        with mock.patch.dict(launcher.BINARIES,{"kolibri":"/fixture/python"}), \
             mock.patch.object(launcher,"RUNS_DIR",self.root/"runs"), \
             mock.patch.object(launcher,"free_port",side_effect=[18091,18092]), \
             mock.patch.object(route,"inspect_runtime",return_value=RUNTIME), \
             mock.patch.object(route,"inspect_model",return_value=changed),self.assertRaisesRegex(ValueError,"changed"):
            launcher.normalized_request(self.request,[self.model])

    def test_large_context_response_and_kv_options_reach_worker(self):
        request = {**self.request,"context":262144,"output":65536,
                   "options":{"kv":"q6","prefillSize":64,"promptCacheGB":4,"memoryGB":40}}
        with mock.patch.dict(launcher.BINARIES,{"kolibri":"/fixture/python"}), \
             mock.patch.object(launcher,"RUNS_DIR",self.root/"runs"), \
             mock.patch.object(launcher,"free_port",side_effect=[18091,18092]), \
             mock.patch.object(route,"inspect_runtime",return_value=RUNTIME), \
             mock.patch.object(route,"inspect_model",return_value=MODEL), \
             mock.patch.object(route,"current_resource",return_value=RESOURCE):
            plan = launcher.normalized_request(request,[self.model])
        config = json.loads(Path(plan.engine_argv[-1]).read_text())
        self.assertEqual((config["context"],config["output"]),(262144,65536))
        self.assertEqual(config["options"]["kv"],"q6")
        self.assertEqual(config["options"]["prefillSize"],64)
        self.assertEqual(config["options"]["promptCacheGB"],4)
        self.assertEqual(plan.options["_kolibriMemoryPlan"]["quantizedKvLayers"],10)

    def test_optimizer_keeps_requested_kv_and_workspace_settings(self):
        request = {**self.request,"context":131072,"output":16384,
                   "options":{"kv":"q6","prefillSize":64,"promptCacheGB":4,"memoryGB":40}}
        preset = launcher.fastest_safe_options("kolibri",self.model["backends"]["kolibri"],request["options"])
        for key in ("kv","prefillSize","promptCacheGB"):
            self.assertEqual(preset["options"][key],request["options"][key])

    def test_admission_accounts_for_ssd_weights_without_requiring_full_model_ram(self):
        with mock.patch.dict(launcher.BINARIES,{"kolibri":"/fixture/python"}):
            result=launcher.session_memory_admission(self.request,[self.model],RESOURCE,{"phase":"idle"},{"active":False})
        self.assertTrue(result["launchable"])
        estimate=result["estimate"]
        self.assertEqual(estimate["ssdWeightBytes"],MODEL["weightBytes"])
        self.assertLess(estimate["estimatedWorkingSetBytes"],MODEL["weightBytes"])


if __name__ == "__main__":
    unittest.main()
