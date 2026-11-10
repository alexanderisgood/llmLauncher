"""No-model checks for the post-refactor full-launcher proof path."""
import copy
import json
import math
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest import mock
from bench import launcher_agents_route as route

class RoutePreparationTests(unittest.TestCase):
    def test_exact_prior_contracts_are_retained_and_lower_ceiling_is_explicit(self):
        model={"id":"original"};project=Path("/generated/project")
        first=route.request_for("kolibri",model,project);other=route.request_for("splash",model,project)
        self.assertEqual((first["context"],first["output"],first["reasoning"]),(8192,1024,"off"))
        self.assertEqual(first["options"],route.KOLIBRI_OPTIONS)
        self.assertEqual((other["context"],other["output"],other["reasoning"]),(16384,1024,"off"))
        self.assertEqual(other["options"],{})
        smaller=route.request_for("kolibri",model,project,memory_gb=8)
        self.assertEqual(first["options"]["memoryGB"],12)
        self.assertEqual(smaller["options"]["memoryGB"],8)

    def guard(self,physical,launchable=True,decision="ready"):
        admission={"launchable":launchable,"decision":decision,"requiresAcknowledgement":False,
                   "estimate":{"requiredHeadroomBytes":20_000_000_000,"osReserveBytes":5_000_000_000}}
        with mock.patch.object(route.launcher,"apple_resource_snapshot",return_value={"freePercent":99,"reclaimableMemorySource":"host_statistics64"}),mock.patch.object(route.launcher,"public_session_resource",return_value={}),mock.patch.object(route.launcher,"session_memory_admission",return_value=admission),mock.patch.object(route.darwin_memory,"snapshot_reclaimable_bytes",return_value=physical):
            return route.admission({}, {})

    def test_physical_capacity_pressure_and_launcher_decision_remain_separate(self):
        self.assertFalse(self.guard(20_000_000_000)["ready"])
        self.assertFalse(self.guard(None)["ready"])
        self.assertFalse(self.guard(40_000_000_000,False,"pressure")["ready"])
        self.assertTrue(self.guard(22_147_483_648)["ready"])
        self.assertEqual(self.guard(1)["requiredPhysicalBytes"],20_000_000_000+route.AGENT_RESERVE)

    def test_private_agent_keeps_provider_hooks_rpc_and_never_overrides_home(self):
        with tempfile.TemporaryDirectory() as folder:
            plan=SimpleNamespace(run_dir=Path(folder),client="pi",client_env={"LLM_LAUNCHER_PI_PROVIDER":"private"},
                                 client_argv=["/generated/pi","--extension","/generated/pi-provider.js","--mode","rpc"])
            route.private_agent(plan)
            self.assertEqual(plan.client_argv[:5],["/generated/pi","--extension","/generated/pi-provider.js","--mode","rpc"])
            self.assertIn("--tools",plan.client_argv)
            self.assertNotIn("HOME",plan.client_env)
            self.assertEqual(plan.client_env["LLM_LAUNCHER_PI_PROVIDER"],"private")
            self.assertTrue(plan.client_env["PI_CODING_AGENT_DIR"].startswith(folder))

    def test_plan_receipt_exposes_exact_controls_without_bearer(self):
        provider={"apiKey":"SECRET_NEVER_REPORT","transportModel":route.kolibri_runtime.MODEL_ID,"model":{"id":"exact-model","maxTokens":1024,"contextWindow":8192,"reasoning":False}}
        plan=SimpleNamespace(client="pi",backend="kolibri",agent_host="console",context=8192,output=1024,reasoning="off",
             options={"kv":"off"},client_env={"LLM_LAUNCHER_PI_PROVIDER":json.dumps(provider)},client_argv=["pi","--mode","rpc"])
        receipt=route.plan_receipt(plan)
        self.assertEqual(receipt["providerOutput"],1024);self.assertEqual(receipt["providerContext"],8192)
        self.assertTrue(receipt["authenticationConfigured"]);self.assertTrue(receipt["rpcConfigured"])
        self.assertNotIn("SECRET_NEVER_REPORT",json.dumps(receipt))
        plan.client="omp";plan.client_env={"LLM_LAUNCHER_OMP_PROVIDER":json.dumps({"apiKey":"SECRET_NEVER_REPORT","models":[{**provider["model"],"id":route.kolibri_runtime.MODEL_ID}]})}
        self.assertEqual(route.plan_receipt(plan)["providerOutput"],1024)
        plan.client_env["LLM_LAUNCHER_OMP_PROVIDER"]=json.dumps({"models":[{**provider["model"],"maxTokens":512}]})
        with self.assertRaisesRegex(AssertionError,"differs"):route.plan_receipt(plan)

    def test_metrics_require_authoritative_finite_count_duration_and_basis(self):
        row={"result":"completed","runtimeStatsSource":"kolibri-native-stats","runtimeDecodeTokenCount":10,
             "runtimeGenerationSeconds":2,"runtimeTokensPerSecond":5,"completionTokens":10,"promptTokens":40,
             "runtimeThroughputBasis":"request-native-generation"}
        self.assertEqual(route.metric_receipt(row,"kolibri")["runtimeTokensPerSecond"],5)
        for field,value in [("runtimeStatsSource","relay-clock"),("runtimeTokensPerSecond",math.inf),("runtimeTokensPerSecond",8),
                            ("runtimeGenerationSeconds",True),("runtimeDecodeTokenCount",True),("completionTokens",11)]:
            with self.subTest(field=field,value=value),self.assertRaises(AssertionError):route.metric_receipt({**row,field:value},"kolibri")
        splash={**row,"runtimeStatsSource":"splash-native-stats","runtimeDecodeTokenCount":4,"runtimeGenerationSeconds":2,
                "runtimeTokensPerSecond":2,"runtimeFirstBatchTokens":6,"runtimeThroughputBasis":"request-lifecycle-excluding-first-native-batch"}
        self.assertEqual(route.metric_receipt(splash,"splash")["runtimeDecodeTokenCount"],4)
        with self.assertRaisesRegex(AssertionError,"batches differ"):route.metric_receipt({**splash,"runtimeFirstBatchTokens":7},"splash")
        with self.assertRaisesRegex(AssertionError,"basis"):route.metric_receipt({**row,"runtimeThroughputBasis":"engine-whole-run"},"kolibri")

    def test_actual_native_read_execution_is_required_even_when_file_is_correct(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/"proof.txt").write_text("MARKER")
            console=SimpleNamespace(plan=SimpleNamespace(run_id="surface"));proof=route.ToolEvidence()
            for name in ("write","read"):
                proof.record(console,{"type":"tool_execution_end","toolName":name,"isError":False,"result":{"content":[{"text":"MARKER"}]}})
            proof.record(console,{"type":"message_end","message":{"role":"assistant","stopReason":"stop","content":[{"text":"MARKER"}]}})
            self.assertTrue(proof.verify("surface","MARKER",root)["actualWriteRead"])
            proof.rows["surface"]["tools"][1]["result"]={"content":[{"text":"different"}]}
            with self.assertRaisesRegex(AssertionError,"read did not return"):proof.verify("surface","MARKER",root)

    def test_stale_epoch_never_captures_replacement_processes(self):
        plan=object();old=threading.Event();new=threading.Event()
        manager=SimpleNamespace(lifecycle_lock=threading.Lock(),lock=threading.Lock(),plan=plan,cancel_event=new,
            process=SimpleNamespace(pid=123),proxy_process=None,aux_process=None,agent_consoles={})
        safety=route.RouteSafety(manager,plan,"fingerprint");safety.epoch=old;safety.capture()
        self.assertEqual(safety.groups,set());self.assertEqual(safety.handles,[])

    def test_blocked_guard_cannot_start_run_manager(self):
        with mock.patch.object(route.launcher,"RunManager") as manager,self.assertRaisesRegex(RuntimeError,"physical admission"):
            route.execute(SimpleNamespace(),{}, {},Path("/generated"),{"ready":False},None)
        manager.assert_not_called()

if __name__=="__main__":unittest.main()
