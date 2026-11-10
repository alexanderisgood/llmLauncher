"""Complete job-domain equivalence with generated measurements and owned children.

No model, GPU workload, actual benchmark result store, install or preference is
used. Sleeping Python fixture groups exercise only ownership and cleanup.
"""
import ast
import copy
from contextlib import ExitStack
from dataclasses import FrozenInstanceError, fields, replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock

import benchmark_evidence
import benchmark_jobs as jobs
import launcher


fixture = Path(__file__).parent / "fixtures/benchmark_jobs_legacy.py"
spec = importlib.util.spec_from_file_location("legacy_benchmark_jobs", fixture)
legacy = importlib.util.module_from_spec(spec); spec.loader.exec_module(legacy)


def normalize(value):
    if isinstance(value, dict):
        return {key:("<time>" if key in {"time", "createdAt", "savedAt", "expiresAt", "promotedAt"}
                     else normalize(item)) for key,item in value.items()}
    if isinstance(value, (tuple,list)):
        return [normalize(item) for item in value]
    return value


class FakeOwner:
    def __init__(self):
        self.plan = self.process = None
        self.llamacpp_safety_violation = None
        self.codex_proxy_port = self.session_proxy_port = None
        self.phase = "idle"
        self.accepted = []; self.stopped = []
        self.receipts = {}
        self.reject = False
        self.lock = threading.RLock()
        self.lifecycle_lock = threading.Lock()
        self.cancel_event = threading.Event()

    def snapshot(self):
        return {"phase":self.phase, "message":"Generated owner"}

    def start(self, plan):
        if self.reject or self.plan is not None:
            raise ValueError("Generated other owner won admission")
        process = subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
        self.plan, self.process, self.phase = plan, process, "running"
        self.cancel_event = threading.Event()
        self.accepted.append((plan,process))
        self.receipts[id(plan)] = {"plan":plan,"process":process,"safety":None}

    def stop(self, expected_plan=None, expected_cancel_event=None):
        with self.lock:
            if expected_cancel_event is not None and self.cancel_event is not expected_cancel_event:
                return
            self._stop_owned(expected_plan)

    def _stop_owned(self, expected_plan=None):
        if expected_plan is not None and self.plan is not expected_plan:
            return
        if self.plan is None:
            return
        plan, process = self.plan, self.process
        self.receipts[id(plan)]["safety"] = self.llamacpp_safety_violation
        self.stopped.append((plan,expected_plan))
        try:
            os.killpg(process.pid,signal.SIGTERM); process.wait(timeout=2)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL); process.wait(timeout=2)
        self.plan = self.process = None; self.phase = "idle"

    def port(self):
        def process(plan):
            receipt = self.receipts.get(id(plan))
            return receipt["process"] if receipt and receipt["plan"] is plan and self.plan in (None,plan) else None
        def safety(plan):
            if plan is None:
                plan = self.accepted[-1][0] if self.accepted else None
            receipt = self.receipts.get(id(plan))
            if not receipt or receipt["plan"] is not plan or self.plan not in (None,plan):
                return None
            return self.llamacpp_safety_violation if self.plan is plan else receipt["safety"]
        return jobs.RunOwnerPort(self.snapshot,self.start,self.stop,lambda plan:self.plan is plan,
            process,lambda plan:tuple(port for port in (plan.port,plan.client_port) if isinstance(port,int)),safety)

    def close(self):
        self.stop()
        for _plan,process in self.accepted:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGTERM); process.wait(timeout=2)


class FakeTelemetry:
    def __init__(self, *, process_provider, invariant_callback):
        self.process_provider, self.invariant = process_provider, invariant_callback
        self.violation = None

    def start(self, _initial=None):
        pass

    def tick(self, value):
        try:
            self.invariant(value)
        except Exception as error:
            self.violation = str(error); raise

    def stop(self):
        return {"physicalFootprintAvailable":True,"synthetic":True,"peakPhysicalFootprintBytes":1}


class Harness:
    def __init__(self, root, *, frozen=False, promotion=False):
        self.root = root; self.frozen = frozen
        self.owner = FakeOwner(); self.saved = []; self.promotion_saved = []
        self.requests = []; self.normalized = []; self.disposed = []
        self.telemetry = []
        self.metric_invalid = False; self.guard_failure = False
        self.selected = "generated-selected-copy"; self.selected_calls = []
        self.revision = "generated-revision"; self.provenance = True
        self.model = {"id":"generated-model", "name":"Generated model", "path":str(root),
            "backends":{"omlx":{"depth":2,"depthMax":3,"mtp":True}}}
        self.job = {"id":"generated-benchmark", "backend":"omlx", "client":"chat", "modelId":self.model["id"],
            "model":copy.deepcopy(self.model), "project":str(root), "context":8192,"output":128,"reasoning":"off",
            "options":{"acceleration":"off","kv":"off","depth":2}, "chat":{"sampling":"model","systemPrompt":""},
            "suiteName":"quick", "suite":{"label":"Generated workload","promptTokens":[32],"maxTokens":8,"repetitions":1},
            "modes":["ar","mtp"],"workloadKind":"throughput","modelFingerprint":"a"*64,
            "runtimeVersion":"generated-runtime", "speedSampling":{"temperature":.6,"top_p":.9,"top_k":20,"seed":17},
            "evidence":{"context":8192,"output":128,"client":"chat","reasoning":"off","kv":"off",
                        "samplingFingerprint":"generated-sampling","engineSettings":{}}}
        self.overrides = {
            "validated_benchmark_request":lambda *_args,**_kwargs:copy.deepcopy(self.job),
            "normalized_request":self.plan,
            "require_live_model_load_admission":lambda *_args,**_kwargs:{"decision":"allow","launchable":True},
            "dispose_plan_secrets":lambda plan:self.disposed.append(plan),
            "run_benchmark_completion":self.complete,
            "hardware_fingerprint":lambda:"generated-mac",
            "benchmark_system_memory_violation":lambda value,*_args:"Generated physical reserve failure" if value.get("syntheticViolation") else None,
            "save_benchmark_record":lambda record:self.saved.append(copy.deepcopy(record)),
            "save_benchmark_records":lambda records:self.saved.extend(copy.deepcopy(records)),
            "load_runtime_promotion_records":lambda:copy.deepcopy(self.promotion_saved),
            "save_runtime_promotion_record":lambda record:self.promotion_saved.append(copy.deepcopy(record)),
            "build_runtime_promotion_plan":lambda *_args,**_kwargs:self.promotion_plan(),
            "build_runtime_promotion_result":lambda plan,results:{"id":"generated-result","recommendation":"Generated comparison complete",
                "measurements":copy.deepcopy(results),"selectionChanged":False,"canPromote":True},
            "runtime_executable_revision":lambda _path:{"id":self.revision},
            "managed_runtime_verification":lambda _path:{"verified":self.provenance},
            "runtime_candidate_details":lambda _runtime:[{"id":"selected","path":"generated-selected","selected":True},
                {"id":"candidate","path":"generated-candidate","selected":False,"version":"generated-candidate-version"}],
            "select_runtime_candidate":self.select,
        }
        self.errors = jobs.BenchmarkErrors(launcher.LaunchCancelled,launcher.BenchmarkResourceCooldownTimeout,launcher.QualificationSafetyFailure)
        self.policy = jobs.BenchmarkPolicy(**{item.name:getattr(launcher,item.name.upper()) for item in fields(jobs.BenchmarkPolicy)
            if item.name not in {"engine_ready_timeout_seconds","engine_poll_seconds","event_limit"}},
            engine_ready_timeout_seconds=.5,engine_poll_seconds=.001)
        self.services = self.services_from(launcher)
        self.evidence = launcher._benchmark_evidence_verifier()
        self.stack = ExitStack()
        if frozen:
            self.stack.enter_context(mock.patch.multiple(legacy, **self.overrides,
                BenchmarkTelemetrySampler=self.sampler,
                benchmark_clean_unload_evidence=lambda _owner,process,pgid,ports:self.unload(None,process,pgid,ports),
                BINARIES={"omlx":self.selected}))
            self.manager = (legacy.RuntimePromotionManager if promotion else legacy.BenchmarkManager)(self.owner)
        elif promotion:
            services = jobs.PromotionServices(**{item.name:(lambda:self.selected) if item.name=="selected_runtime"
                else self.overrides.get(item.name,getattr(launcher,item.name)) for item in fields(jobs.PromotionServices)})
            self.manager = jobs.RuntimePromotionManager(self.owner.port(),self.policy,self.services,self.evidence,
                jobs.PromotionPolicy(launcher.RUNTIME_PROMOTION_PLAN_TTL_SECONDS),services,self.errors)
        else:
            self.manager = jobs.BenchmarkManager(self.owner.port(),self.policy,self.services,self.evidence,self.errors)

    def services_from(self, namespace):
        groups = {}
        for item in fields(jobs.BenchmarkServices):
            cls = getattr(jobs,item.name.capitalize()+"Services")
            arguments = {}
            for service in fields(cls):
                if service.name == "telemetry_sampler": arguments[service.name] = self.sampler
                elif service.name == "clean_unload": arguments[service.name] = self.unload
                else: arguments[service.name] = self.overrides.get(service.name,getattr(namespace,service.name))
            groups[item.name] = cls(**arguments)
        return jobs.BenchmarkServices(**groups)

    def sampler(self, **kwargs):
        sampler = FakeTelemetry(**kwargs); self.telemetry.append(sampler); return sampler

    def unload(self, _plan,process,_pgid,_ports):
        ports=sorted(set(_ports)) or [18987]
        return {"clean":process is not None and process.poll() is not None,
                "processExited":True,"processGroupExited":True,"managerIdle":self.owner.plan is None,
                "portsClosed":True,"checkedPorts":ports,"closedPorts":ports}

    def plan(self,payload,_models,**kwargs):
        plan = SimpleNamespace(backend=payload["backend"],options=copy.deepcopy(payload["options"]),
            port=18987,client_port=None,context=payload["context"],output=payload["output"],reasoning=payload["reasoning"])
        self.normalized.append((plan,copy.deepcopy(payload),kwargs)); return plan

    def complete(self,plan,prompt,max_tokens,sampling,cancel,**kwargs):
        self.requests.append({"plan":plan,"maxTokens":max_tokens,"sampling":copy.deepcopy(sampling),"kwargs":kwargs})
        self.telemetry[-1].tick({"syntheticViolation":self.guard_failure})
        if cancel.is_set(): raise launcher.LaunchCancelled("Generated cancellation")
        speed = 10 if plan.options.get("acceleration")=="off" else 12
        return {"outputHash":"b"*64,"completionTokens":max_tokens,"promptTokens":32,"requestedMaxTokens":max_tokens,
            "ttftSeconds":.1,"decodeTokensPerSecond":speed,"endToEndTokensPerSecond":speed*.9,
            "totalSeconds":max_tokens/(speed*.9),"authoritativeUsage":True,
            "responseOutcome":"invalid" if self.metric_invalid else "completed"}

    def promotion_plan(self):
        runtime=lambda role:{"path":"generated-"+role,"resolvedPath":"generated-"+role,"version":role,
                             "revision":{"id":"generated-revision"}}
        return {"id":"generated-promotion", "confirmation":"generated-confirmation","canStart":True,
                "executionOrder":["selected","candidate"],"selected":runtime("selected"),"candidate":runtime("candidate"),
                "_job":copy.deepcopy(self.job)}

    def select(self,payload):
        self.selected_calls.append(copy.deepcopy(payload)); return {"generated":True}

    def wait(self):
        deadline=time.monotonic()+5
        while self.manager.is_active() and time.monotonic()<deadline:time.sleep(.01)
        if self.manager.is_active():raise AssertionError("Generated job did not finish")
        return self.manager.snapshot()

    def close(self):
        try:
            self.manager.cancel()
            if self.manager.thread is not None:self.manager.thread.join(3)
            self.owner.close()
        finally:self.stack.close()


class BenchmarkJobTests(unittest.TestCase):
    def fixture(self,**kwargs):
        temp=tempfile.TemporaryDirectory(prefix="generated-benchmark-job-")
        h=Harness(Path(temp.name),**kwargs)
        self.addCleanup(temp.cleanup);self.addCleanup(h.close);return h

    def test_standalone_boundary_and_frozen_baseline_and_policy(self):
        self.assertNotIn("import launcher",Path(jobs.__file__).read_text())
        self.assertNotIn("self.run_manager",Path(jobs.__file__).read_text())
        meta=json.loads(fixture.with_suffix(".json").read_text())
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(),meta["fixtureSha256"])
        h=self.fixture()
        with self.assertRaises(FrozenInstanceError):h.policy.benchmark_minimum_speedup=0
        with self.assertRaises(TypeError):h.policy.benchmark_probe_contract["version"]=0
        with self.assertRaises(FrozenInstanceError):h.services.store.save_benchmark_record=lambda _:None
        self.assertTrue(issubclass(launcher.RuntimePromotionManager,launcher.BenchmarkManager))

    def test_all_execution_logic_matches_frozen_source_after_explicit_port_rewrites(self):
        old_classes={n.name:n for n in ast.parse(fixture.read_text()).body if isinstance(n,ast.ClassDef)}
        new_classes={n.name:n for n in ast.parse(Path(jobs.__file__).read_text()).body if isinstance(n,ast.ClassDef)}
        class Unwrap(ast.NodeTransformer):
            def __init__(self, original, name):
                self.original,self.name=original,name
            def visit_Expr(self,node):
                if isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):return None
                return self.generic_visit(node)
            def visit_Name(self,node):
                if node.id=="BenchmarkPlan":return ast.Name(id="LaunchPlan",ctx=node.ctx)
                return node
            def visit_Assign(self,node):
                if self.name=="cancel" and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=="job":return None
                if len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=="known_ports":
                    return copy.deepcopy(next(n for n in ast.walk(self.original) if isinstance(n,ast.Assign)
                        and any(isinstance(target,ast.Name) and target.id=="known_ports" for target in n.targets)))
                return self.generic_visit(node)
            def visit_AnnAssign(self,node):
                if self.name=="_measure_mode" and isinstance(node.target,ast.Name) and node.target.id=="resource_telemetry":return None
                return self.generic_visit(node)
            def visit_Try(self,node):
                if self.name=="_measure_mode" and len(node.body)==1:
                    single=node.body[0]
                    if isinstance(single,ast.Assign) and any(isinstance(t,ast.Name) and t.id in {"telemetry","resource_telemetry"} for t in single.targets):
                        return [value for value in [self.visit(single),*(self.visit(n) for n in node.finalbody)] if value is not None]
                    if (isinstance(single,ast.Expr) and isinstance(single.value,ast.Call)
                            and isinstance(single.value.func,ast.Attribute) and single.value.func.attr=="start"
                            and isinstance(single.value.func.value,ast.Name) and single.value.func.value.id=="telemetry"):
                        return self.visit(single)
                return self.generic_visit(node)
            def visit_If(self,node):
                if self.name=="_measure_mode" and isinstance(node.test,ast.Name) and node.test.id=="run_manager_accepted_plan":
                    return None
                if self.name=="cancel":
                    original_ifs=[n for n in ast.walk(self.original) if isinstance(n,ast.If)]
                    if (isinstance(node.test,ast.BoolOp) and any(isinstance(n,ast.Name) and n.id=="expected_job_id" for n in ast.walk(node.test))):
                        node.test=copy.deepcopy(original_ifs[0].test)
                    elif (isinstance(node.test,ast.Compare) and any(isinstance(n,ast.Attribute) and n.attr=="ACTIVE_PHASES" for n in ast.walk(node.test))
                          and any(isinstance(n.test,ast.UnaryOp) for n in original_ifs)):
                        node.test=copy.deepcopy(next(n.test for n in original_ifs if isinstance(n.test,ast.UnaryOp)))
                return self.generic_visit(node)
            def visit_With(self,node):
                if self.name=="_measure_mode" and len(node.body)==2 and isinstance(node.body[0],ast.If) and any(
                        isinstance(n,ast.Name) and n.id=="result" for n in ast.walk(node.body[0].test)):
                    node.body=node.body[1:]
                if self.name=="inspect" and node.body and isinstance(node.body[0],ast.If):
                    node.body=node.body[1:]
                if (self.name in {"_worker","_mtp_tuning_worker","_dflash_tuning_worker","_shootout_worker"}
                        and node.body and isinstance(node.body[0],ast.If)
                        and isinstance(node.body[0].test,ast.Call)
                        and isinstance(node.body[0].test.func,ast.Attribute) and node.body[0].test.func.attr=="is_set"):
                    body=node.body[1:]
                    publish=next(i for i,n in enumerate(body) if isinstance(n,ast.Assign)
                        and any(isinstance(target,ast.Subscript) and isinstance(target.value,ast.Attribute)
                            and target.value.attr=="state" for target in n.targets))
                    previous=body[:publish]
                    node.body=body[publish:]
                    return [*(self.visit(n) for n in previous),self.generic_visit(node)]
                return self.generic_visit(node)
            def visit_Call(self,node):
                if isinstance(node.func,ast.Attribute) and node.func.attr=="_start_thread":
                    return ast.Call(func=ast.Attribute(value=node.args[0],attr="start",ctx=ast.Load()),args=[],keywords=[])
                if isinstance(node.func,ast.Name) and node.func.id=="_mutable_policy_copy":
                    node.func=ast.Attribute(value=ast.Name(id="copy",ctx=ast.Load()),attr="deepcopy",ctx=ast.Load())
                f=node.func
                if isinstance(f,ast.Attribute) and isinstance(f.value,ast.Attribute) and isinstance(f.value.value,ast.Name) and f.value.value.id=="self":
                    if f.value.attr=="owner":
                        manager=ast.Attribute(value=ast.Name(id="self",ctx=ast.Load()),attr="run_manager",ctx=ast.Load())
                        if f.attr=="owns_plan":return ast.Compare(left=ast.Attribute(value=manager,attr="plan",ctx=ast.Load()),ops=[ast.Is()],comparators=node.args)
                        if f.attr=="process_for":return ast.Attribute(value=manager,attr="process",ctx=ast.Load())
                        if f.attr=="safety_violation":return ast.Attribute(value=manager,attr="llamacpp_safety_violation",ctx=ast.Load())
                        if f.attr=="stop" and self.name!="_measure_mode":node.keywords=[]
                    elif f.value.attr=="promotion" and f.attr=="selected_runtime":
                        return ast.Call(func=ast.Attribute(value=ast.Name(id="BINARIES",ctx=ast.Load()),attr="get",ctx=ast.Load()),args=[ast.Constant("omlx")],keywords=[])
                if isinstance(f,ast.Attribute) and f.attr=="clean_unload":
                    node.func=ast.Name(id="benchmark_clean_unload_evidence",ctx=ast.Load())
                    node.args[0]=ast.Attribute(value=ast.Name(id="self",ctx=ast.Load()),attr="run_manager",ctx=ast.Load())
                return self.generic_visit(node)
            def visit_Attribute(self,node):
                value=node.value
                if isinstance(value,ast.Attribute) and isinstance(value.value,ast.Name) and value.value.id=="self":
                    if value.attr=="policy":
                        fixed={"engine_ready_timeout_seconds":930,"engine_poll_seconds":.2,"event_limit":100}
                        return ast.Constant(fixed[node.attr]) if node.attr in fixed else ast.Name(id=node.attr.upper(),ctx=node.ctx)
                    if value.attr=="promotion_policy":return ast.Name(id="RUNTIME_PROMOTION_PLAN_TTL_SECONDS",ctx=node.ctx)
                    if value.attr in {"evidence","promotion"}:return ast.Name(id=node.attr,ctx=node.ctx)
                    if value.attr=="errors":return ast.Name(id={"cancelled":"LaunchCancelled","cooldown":"BenchmarkResourceCooldownTimeout","safety":"QualificationSafetyFailure"}[node.attr],ctx=node.ctx)
                    if value.attr=="owner":return ast.Attribute(value=ast.Attribute(value=ast.Name(id="self",ctx=ast.Load()),attr="run_manager",ctx=ast.Load()),attr=node.attr,ctx=node.ctx)
                if isinstance(value,ast.Attribute) and isinstance(value.value,ast.Attribute) and isinstance(value.value.value,ast.Name) and value.value.value.id=="self" and value.value.attr=="services":
                    return ast.Name(id="BenchmarkTelemetrySampler" if node.attr=="telemetry_sampler" else node.attr,ctx=node.ctx)
                return self.generic_visit(node)
        checked=0
        for name in ("BenchmarkManager","RuntimePromotionManager"):
            before={n.name:n for n in old_classes[name].body if isinstance(n,ast.FunctionDef)}
            after={n.name:n for n in new_classes[name].body if isinstance(n,ast.FunctionDef) and n.name!="_start_thread"}
            self.assertEqual(set(before),set(after))
            for method,old in before.items():
                if method=="__init__":continue
                new=copy.deepcopy(after[method])
                if any(isinstance(d,ast.Name) and d.id=="staticmethod" for d in old.decorator_list):
                    if new.args.args and new.args.args[0].arg=="self":new.args.args=new.args.args[1:]
                    new.decorator_list=copy.deepcopy(old.decorator_list)
                expected=Unwrap(old,method).visit(copy.deepcopy(old))
                actual=Unwrap(old,method).visit(new)
                with self.subTest(manager=name,method=method):
                    self.assertEqual(ast.dump(actual,include_attributes=False),ast.dump(expected,include_attributes=False))
                checked+=1
        self.assertEqual(checked,42)

    def test_real_owned_fixture_measurements_match_baseline_and_reload_every_mode(self):
        states=[]
        for frozen in (True,False):
            h=self.fixture(frozen=frozen)
            h.manager.start({},[h.model]);state=h.wait()
            self.assertEqual(state["phase"],"completed",state.get("message"))
            self.assertEqual(len(h.saved),1)
            self.assertEqual(len(h.owner.accepted),2)
            self.assertEqual(len({process.pid for _plan,process in h.owner.accepted}),2)
            self.assertTrue(all(process.poll() is not None for _plan,process in h.owner.accepted))
            self.assertEqual([request["maxTokens"] for request in h.requests],[32,64,8,32,64,8])
            self.assertTrue(all(request["kwargs"].get("greedy_probe") is True for request in h.requests if request["maxTokens"] in {32,64}))
            self.assertEqual([payload["context"] for _plan,payload,_kwargs in h.normalized],[8192,8192])
            self.assertEqual([payload["output"] for _plan,payload,_kwargs in h.normalized],[128,128])
            self.assertEqual([payload["options"]["kv"] for _plan,payload,_kwargs in h.normalized],["off","off"])
            self.assertEqual([request["sampling"] for request in h.requests if request["maxTokens"]==8],[h.job["speedSampling"]]*2)
            json.dumps(h.saved,allow_nan=False)
            states.append(normalize({"state":state,"records":h.saved}))
            if not frozen:self.assertTrue(all(expected is plan for plan,expected in h.owner.stopped))
            h.close()
        self.assertEqual(states[0],states[1])

    def test_admission_changed_before_load_disposes_only_unowned_plan(self):
        h=self.fixture()
        h.manager.services=replace(h.services,planning=replace(h.services.planning,
            require_live_model_load_admission=mock.Mock(side_effect=RuntimeError("Generated capacity changed"))))
        with self.assertRaisesRegex(RuntimeError,"capacity changed"):
            h.manager._measure_mode(h.job,[h.model],"ar",0,3)
        self.assertEqual(h.owner.accepted,[])
        self.assertEqual(h.disposed,[h.normalized[0][0]])

    def test_rejected_owner_cannot_stop_foreign_plan_and_disposes_its_bearer(self):
        h=self.fixture();foreign=SimpleNamespace(port=18001,client_port=None)
        h.owner.plan=foreign;h.owner.phase="running";h.owner.reject=True
        with self.assertRaisesRegex(ValueError,"other owner"):
            h.manager._measure_mode(h.job,[h.model],"ar",0,3)
        self.assertIs(h.owner.plan,foreign)
        self.assertEqual(h.owner.stopped,[])
        self.assertEqual(h.disposed,[h.normalized[0][0]])
        h.owner.plan=None;h.owner.phase="idle"

    def test_live_guard_and_invalid_response_discard_all_results_and_stop_owned_group(self):
        for field in ("metric_invalid","guard_failure"):
            with self.subTest(field=field):
                h=self.fixture();setattr(h,field,True)
                h.manager.start({},[h.model]);state=h.wait()
                self.assertEqual(state["phase"],"failed")
                self.assertEqual(h.saved,[])
                self.assertIsNone(h.owner.plan)
                self.assertTrue(all(process.poll() is not None for _plan,process in h.owner.accepted))

    def test_generation_goal_refuses_generic_delivery_timing_for_splash(self):
        h=self.fixture();h.job.update({"backend":"splash","enginePreference":"throughput","modes":["ar"]})
        h.job["model"]["backends"]["splash"]={}
        h.manager.start({},[h.model]);state=h.wait()
        self.assertEqual(state["phase"],"failed")
        self.assertIn("generation",state["message"])
        self.assertEqual(h.saved,[])

    def test_capacity_job_identity_cannot_cancel_replacement_or_terminal_job(self):
        h=self.fixture();h.manager.state={"phase":"running","job":{"id":"current"}}
        with self.assertRaisesRegex(ValueError,"no other job"):
            h.manager.cancel(expected_job_id="older")
        self.assertFalse(h.manager.cancel_event.is_set())
        h.manager.state["phase"]="completed"
        h.manager.cancel(expected_job_id="current")
        self.assertEqual(h.manager.state["phase"],"completed")
        h.manager.state={"phase":"idle","job":None}
        with self.assertRaisesRegex(ValueError,"no other job"):
            h.manager.cancel(expected_job_id="older")

    def test_cancel_during_final_record_build_saves_nothing_and_keeps_groups_stopped(self):
        h=self.fixture();entered,release=threading.Event(),threading.Event()
        original=h.manager._build_record
        def build(*args):
            entered.set();release.wait(3);return original(*args)
        try:
            with mock.patch.object(h.manager,"_build_record",side_effect=build):
                h.manager.start({},[h.model]);self.assertTrue(entered.wait(2))
                h.manager.cancel();release.set();state=h.wait()
            self.assertEqual(state["phase"],"cancelled")
            self.assertEqual(h.saved,[])
            self.assertTrue(all(process.poll() is not None for _plan,process in h.owner.accepted))
        finally:release.set()

    def test_commit_wins_before_cancel_and_terminal_teardown_does_not_reopen(self):
        h=self.fixture();entered,release=threading.Event(),threading.Event()
        def save(record):
            entered.set();release.wait(3);h.saved.append(copy.deepcopy(record))
        h.manager.services=replace(h.services,store=replace(h.services.store,save_benchmark_record=save))
        stopped=threading.Event()
        def cancel():h.manager.cancel();stopped.set()
        cancel_thread=threading.Thread(target=cancel)
        try:
            h.manager.start({},[h.model]);self.assertTrue(entered.wait(2));cancel_thread.start()
            self.assertFalse(stopped.wait(.05),"Cancellation must not split a committed save/publication")
            release.set();cancel_thread.join(2);state=h.wait()
            self.assertEqual(state["phase"],"completed")
            self.assertFalse(h.manager.cancel_event.is_set())
            self.assertEqual(len(h.saved),1)
        finally:release.set();cancel_thread.join(3)

    def test_cancellation_during_owned_measurement_stops_only_that_route(self):
        h=self.fixture();entered,release=threading.Event(),threading.Event()
        original=h.complete
        def complete(*args,**kwargs):
            entered.set();release.wait(3);return original(*args,**kwargs)
        h.manager.services=replace(h.services,workload=replace(h.services.workload,run_benchmark_completion=complete))
        try:
            h.manager.start({},[h.model]);self.assertTrue(entered.wait(2))
            h.manager.cancel(expected_job_id=h.job["id"]);release.set()
            self.assertEqual(h.wait()["phase"],"cancelled")
            self.assertEqual(h.saved,[])
            self.assertTrue(all(expected is plan for plan,expected in h.owner.stopped))
            self.assertTrue(all(process.poll() is not None for _plan,process in h.owner.accepted))
        finally:release.set()

    def test_embedded_policy_receipts_remain_detached_serializable_data(self):
        h=self.fixture();h.manager.start({},[h.model]);self.assertEqual(h.wait()["phase"],"completed")
        h.saved[0]["probeContract"]["syntheticMutation"]=True
        self.assertNotIn("syntheticMutation",h.policy.benchmark_probe_contract)
        json.dumps(h.manager.snapshot(),allow_nan=False)

    def test_telemetry_setup_failure_disposes_private_unowned_plan(self):
        for stage in ("construct","start"):
            with self.subTest(stage=stage):
                h=self.fixture()
                if stage=="construct":factory=mock.Mock(side_effect=RuntimeError("Generated telemetry setup failed"))
                else:
                    monitor=mock.Mock(violation=None)
                    monitor.start.side_effect=RuntimeError("Generated telemetry setup failed")
                    monitor.stop.return_value={}
                    factory=mock.Mock(return_value=monitor)
                h.manager.services=replace(h.services,resource=replace(h.services.resource,telemetry_sampler=factory))
                with self.assertRaisesRegex(RuntimeError,"telemetry setup failed"):
                    h.manager._measure_mode(h.job,[h.model],"ar",0,3)
                self.assertEqual(h.disposed,[h.normalized[0][0]])
                self.assertEqual(h.owner.accepted,[])
                if stage=="start":monitor.stop.assert_called_once()

    def test_telemetry_summary_failure_still_stops_exact_owned_group(self):
        h=self.fixture()
        original=h.sampler
        def factory(**kwargs):
            monitor=original(**kwargs)
            monitor.stop=mock.Mock(side_effect=RuntimeError("Generated summary failure"))
            return monitor
        h.manager.services=replace(h.services,resource=replace(h.services.resource,telemetry_sampler=factory))
        with self.assertRaisesRegex(RuntimeError,"summary failure"):
            h.manager._measure_mode(h.job,[h.model],"ar",0,3)
        self.assertIsNone(h.owner.plan)
        self.assertIsNone(h.manager.active_plan)
        self.assertTrue(all(process.poll() is not None for _plan,process in h.owner.accepted))
        self.assertTrue(all(expected is plan for plan,expected in h.owner.stopped))

    def test_post_unload_safety_receipt_keeps_the_run_failure_visible(self):
        h=self.fixture();original=h.owner.stop
        def stop(expected_plan=None):
            h.owner.llamacpp_safety_violation="Generated accepted-run safety failure"
            original(expected_plan)
        h.manager.owner=replace(h.manager.owner,stop=stop)
        with self.assertRaisesRegex(launcher.QualificationSafetyFailure,"accepted-run safety"):
            h.manager._measure_mode(h.job,[h.model],"ar",0,3)
        self.assertIsNone(h.owner.plan)
        self.assertTrue(all(process.poll() is not None for _plan,process in h.owner.accepted))

    def test_failed_owned_unload_is_visible_and_never_saves_or_starts_next_route(self):
        for grouped in (False,True):
            with self.subTest(grouped=grouped):
                h=self.fixture()
                h.manager.services=replace(h.services,resource=replace(h.services.resource,
                    clean_unload=lambda *_args:{"clean":False,"processExited":True,"processGroupExited":False,
                        "managerIdle":True,"portsClosed":False,"checkedPorts":[18987],"closedPorts":[]}))
                if grouped:
                    h.job["shootoutId"]="generated-shootout"
                    h.manager.state={"phase":"queued","job":{},"modes":{},"engines":{"omlx":{"modes":{}}},"events":[]}
                    with self.assertRaisesRegex(RuntimeError,"did not unload cleanly"):
                        h.manager._measure_mode(h.job,[h.model],"ar",0,3)
                    state=h.manager.snapshot();receipt=state["engines"]["omlx"]["modes"]["ar"]["unloadEvidence"]
                else:
                    h.manager.start({},[h.model]);state=h.wait()
                    self.assertEqual(state["phase"],"failed")
                    receipt=state["modes"]["ar"]["unloadEvidence"]
                self.assertFalse(receipt["clean"])
                self.assertFalse(receipt["processGroupExited"])
                self.assertFalse(receipt["portsClosed"])
                self.assertEqual(len(h.owner.accepted),1)
                self.assertEqual(h.saved,[])
                self.assertTrue(all(process.poll() is not None for _plan,process in h.owner.accepted))

    def test_failed_unload_does_not_replace_accepted_run_safety_reason(self):
        h=self.fixture();original=h.owner.stop
        def stop(expected_plan=None):
            h.owner.llamacpp_safety_violation="Generated native safety violation"
            original(expected_plan)
        h.manager.owner=replace(h.manager.owner,stop=stop)
        h.manager.services=replace(h.services,resource=replace(h.services.resource,clean_unload=lambda *_args:{"clean":False}))
        with self.assertRaisesRegex(launcher.QualificationSafetyFailure,"native safety violation"):
            h.manager._measure_mode(h.job,[h.model],"ar",0,3)

    def test_shared_lmstudio_model_unload_uses_audited_receipt_without_process_claims(self):
        for complete in (True,False):
            with self.subTest(complete=complete):
                h=self.fixture();h.job.update({"backend":"lmstudio","modes":["ar"]})
                h.job["model"]["backends"]["lmstudio"]={}
                def start(plan):
                    h.owner.plan=plan;h.owner.phase="running";h.owner.cancel_event=threading.Event()
                def stop(expected_plan=None):
                    if h.owner.plan is expected_plan:h.owner.plan=None;h.owner.phase="idle"
                h.manager.owner=replace(h.manager.owner,start=start,stop=stop,
                    process_for=lambda _plan:None,ports_for=lambda _plan:(),safety_violation=lambda _plan:None)
                receipt={"kind":"shared-lmstudio-model-v1","clean":complete,"managerIdle":True,
                    "modelUnloaded":complete,"sharedServerRetained":True,"ownedPortsClosed":True,
                    "modelIdentifier":"llm-launcher-1234abcd","sharedServerPort":18987,
                    "checkedPorts":[],"closedPorts":[]}
                h.manager.services=replace(h.services,resource=replace(h.services.resource,
                    clean_unload=lambda *_args:copy.deepcopy(receipt)))
                h.manager.start({},[h.model]);state=h.wait()
                self.assertEqual(state["phase"],"completed" if complete else "failed")
                self.assertEqual(len(h.saved),1 if complete else 0)
                self.assertEqual(h.owner.accepted,[],"The shared server has no fixture-owned engine process")
                if not complete:self.assertEqual(state["modes"]["ar"]["unloadEvidence"],receipt)

    def test_promotion_terminal_cancel_and_result_build_cancel_do_not_publish(self):
        h=self.fixture(promotion=True)
        h.manager.state["phase"]="completed";h.manager.thread=mock.Mock();h.manager.thread.is_alive.return_value=True
        h.manager.cancel();self.assertEqual(h.manager.state["phase"],"completed")
        self.assertFalse(h.manager.cancel_event.is_set());h.manager.thread=None
        h.manager.state={"phase":"queued","plan":{},"modes":{},"runtimes":{
            role:{"phase":"queued"} for role in ("selected","candidate")},"events":[],"result":None}
        entered,release=threading.Event(),threading.Event()
        original=h.manager.promotion.build_runtime_promotion_result
        def build(*args):entered.set();release.wait(3);return original(*args)
        h.manager.promotion=replace(h.manager.promotion,build_runtime_promotion_result=build)
        thread=threading.Thread(target=h.manager._worker,args=(h.promotion_plan(),[h.model]))
        try:
            with mock.patch.object(h.manager,"_measure_mode",return_value=({"medianEndToEndTokensPerSecond":10,"medianTTFT":.1},3)), \
                    mock.patch.object(h.manager,"_wait_for_resource_baseline",return_value={"status":"unavailable"}):
                h.manager.thread=thread;thread.start();self.assertTrue(entered.wait(2))
                h.manager.cancel();release.set();thread.join(3)
            self.assertEqual(h.manager.snapshot()["phase"],"cancelled")
            self.assertEqual(h.promotion_saved,[])
            self.assertEqual(h.selected_calls,[])
        finally:release.set();thread.join(3)

    def test_promotion_rechecks_revision_provenance_selected_copy_and_expiry(self):
        for changed in ("revision","provenance","selected"):
            with self.subTest(changed=changed):
                h=self.fixture(promotion=True)
                h.manager.state={"phase":"queued","plan":{},"modes":{},"runtimes":{
                    role:{"phase":"queued"} for role in ("selected","candidate")},"events":[],"result":None}
                def measure(*_args,**_kwargs):
                    if changed=="revision":h.revision="changed-revision"
                    elif changed=="provenance":h.provenance=False
                    else:h.selected="changed-selection"
                    return {"medianEndToEndTokensPerSecond":10,"medianTTFT":.1},3
                with mock.patch.object(h.manager,"_measure_mode",side_effect=measure), \
                        mock.patch.object(h.manager,"_wait_for_resource_baseline",return_value={"status":"unavailable"}):
                    h.manager._worker(h.promotion_plan(),[h.model])
                self.assertEqual(h.manager.snapshot()["phase"],"failed")
                self.assertEqual(h.promotion_saved,[])
                self.assertEqual(h.selected_calls,[])
        h=self.fixture(promotion=True)
        with mock.patch.object(time,"time",return_value=100):
            reviewed=h.manager.inspect({},[h.model])
        with mock.patch.object(time,"time",return_value=100+h.manager.promotion_policy.plan_ttl_seconds+1), \
                self.assertRaisesRegex(ValueError,"expired or changed"):
            h.manager.start({"planId":reviewed["id"],"reviewed":True,"confirmation":reviewed["confirmation"]},[h.model])
        self.assertEqual(h.owner.accepted,[])

    def test_explicit_promotion_preserves_rollback_and_revalidates_every_receipt(self):
        h=self.fixture(promotion=True)
        record={"id":"generated-promotion-result","canPromote":True,"confirmation":"generated-promote",
            "validUntil":"2999-01-01T00:00:00+00:00","hardwareFingerprint":"generated-mac",
            "selected":{"id":"selected","revision":{"id":h.revision}},
            "candidate":{"id":"candidate","revision":{"id":h.revision}}}
        h.promotion_saved.append(record)
        with self.assertRaisesRegex(ValueError,"Confirm the exact"):
            h.manager.promote({"resultId":record["id"],"confirmation":"wrong"})
        self.assertEqual(h.selected_calls,[])
        h.provenance=False
        with self.assertRaisesRegex(ValueError,"provenance"):
            h.manager.promote({"resultId":record["id"],"confirmation":record["confirmation"]})
        self.assertEqual(h.selected_calls,[])
        h.provenance=True
        promoted=h.manager.promote({"resultId":record["id"],"confirmation":record["confirmation"]})
        self.assertEqual(h.selected_calls,[{"runtime":"omlx","candidateId":"candidate","confirmation":"select:candidate"}])
        self.assertTrue(promoted["result"]["selectionChanged"])
        self.assertEqual(promoted["result"]["selected"],record["selected"])

    def test_late_promotion_inspect_cannot_replace_active_job_plan(self):
        h=self.fixture(promotion=True);entered,release=threading.Event(),threading.Event()
        original=h.manager.promotion.build_runtime_promotion_plan
        def build(*args):entered.set();release.wait(3);return original(*args)
        h.manager.promotion=replace(h.manager.promotion,build_runtime_promotion_plan=build)
        failures=[]
        def inspect():
            try:h.manager.inspect({},[h.model])
            except Exception as error:failures.append(error)
        thread=threading.Thread(target=inspect)
        try:
            thread.start();self.assertTrue(entered.wait(2))
            with h.manager.lock:h.manager.state["phase"]="running"
            release.set();thread.join(3)
            self.assertEqual(len(failures),1)
            self.assertIn("active runtime comparison",str(failures[0]))
            self.assertEqual(h.manager.plans,{})
        finally:
            release.set();thread.join(3);h.manager.state["phase"]="idle"

    def test_worker_bootstrap_failure_is_terminal_and_reviewed_retry_is_allowed(self):
        for promotion in (False,True):
            with self.subTest(promotion=promotion):
                h=self.fixture(promotion=promotion)
                payload={}
                if promotion:
                    plan=h.manager.inspect({},[h.model])
                    payload={"planId":plan["id"],"reviewed":True,"confirmation":plan["confirmation"]}
                with mock.patch.object(threading.Thread,"start",side_effect=RuntimeError("Generated thread start refusal")), \
                        self.assertRaisesRegex(RuntimeError,"thread start refusal"):
                    h.manager.start(payload,[h.model])
                self.assertEqual(h.manager.snapshot()["phase"],"failed")
                self.assertIn("thread start refusal",h.manager.snapshot()["message"])
                self.assertIsNone(h.manager.thread)
                self.assertFalse(h.manager.is_active())
                self.assertEqual(h.owner.accepted,[])
                h.manager.cancel()
                if promotion:
                    with mock.patch.object(h.manager,"_measure_mode",return_value=({"medianEndToEndTokensPerSecond":10,"medianTTFT":.1},3)), \
                            mock.patch.object(h.manager,"_wait_for_resource_baseline",return_value={"status":"unavailable"}):
                        h.manager.start(payload,[h.model]);self.assertEqual(h.wait()["phase"],"completed")
                else:
                    h.manager.start(payload,[h.model]);self.assertEqual(h.wait()["phase"],"completed")

    def test_integrated_controller_facade_matches_frozen_complete_job(self):
        results=[]
        for frozen in (True,False):
            h=self.fixture(frozen=frozen)
            if not frozen:h.manager=launcher.BenchmarkManager(h.owner)
            with mock.patch.multiple(launcher,**h.overrides,
                    BenchmarkTelemetrySampler=h.sampler,
                    benchmark_clean_unload_evidence=lambda _owner,process,pgid,ports,**_kwargs:h.unload(None,process,pgid,ports)):
                h.manager.start({},[h.model]);state=h.wait()
            self.assertEqual(state["phase"],"completed",state.get("message"))
            self.assertTrue(all(process.poll() is not None for _plan,process in h.owner.accepted))
            results.append(normalize({"state":state,"records":h.saved}))
            h.close()
        self.assertEqual(results[0],results[1])

    def test_controller_owner_binding_never_exposes_replacement_and_keeps_final_receipt(self):
        h=self.fixture();binding=launcher._BenchmarkRunOwner(h.owner);port=binding.port()
        plan=SimpleNamespace(port=18987,client_port=None)
        port.start(plan);owned=port.process_for(plan)
        self.assertIs(owned,h.owner.process)
        self.assertTrue(port.owns_plan(plan))
        h.owner.llamacpp_safety_violation="Generated final accepted-run failure"
        port.stop(expected_plan=plan)
        self.assertIsNotNone(owned.poll())
        self.assertIs(port.process_for(plan),owned)
        self.assertEqual(port.safety_violation(None),"Generated final accepted-run failure")
        foreign=SimpleNamespace(port=18988,client_port=None)
        h.owner.start(foreign)
        h.owner.llamacpp_safety_violation="Different run's failure"
        self.assertFalse(port.owns_plan(plan))
        self.assertIs(port.process_for(plan),owned)
        self.assertIsNone(port.process_for(foreign))
        self.assertEqual(port.safety_violation(None),"Generated final accepted-run failure")
        port.stop(expected_plan=plan)
        self.assertIs(h.owner.plan,foreign)
        self.assertIsNone(h.owner.process.poll())

    def test_stale_owner_cannot_stop_same_plan_object_restarted_with_new_epoch(self):
        h=self.fixture();port=launcher._BenchmarkRunOwner(h.owner).port()
        plan=SimpleNamespace(port=18987,client_port=None)
        port.start(plan);port.stop(expected_plan=plan)
        h.owner.start(plan);replacement=h.owner.process
        self.assertFalse(port.owns_plan(plan))
        port.stop(expected_plan=plan)
        self.assertIs(h.owner.plan,plan)
        self.assertIsNone(replacement.poll())

    def test_owner_admission_registration_holds_state_lock_before_foreign_start(self):
        h=self.fixture();port=launcher._BenchmarkRunOwner(h.owner).port()
        plan=SimpleNamespace(port=18987,client_port=None)
        entered,release,foreign_attempted=threading.Event(),threading.Event(),threading.Event()
        original=h.owner.start;errors=[]
        def wrapped(target):entered.set();release.wait(3);original(target)
        def owned():
            try:port.start(plan)
            except Exception as error:errors.append(error)
        foreign_errors=[]
        def foreign():
            foreign_attempted.set()
            with h.owner.lock:
                try:original(plan)
                except Exception as error:foreign_errors.append(error)
        owned_thread=threading.Thread(target=owned);foreign_thread=threading.Thread(target=foreign)
        try:
            with mock.patch.object(h.owner,"start",side_effect=wrapped):
                owned_thread.start();self.assertTrue(entered.wait(2));foreign_thread.start()
                self.assertTrue(foreign_attempted.wait(2))
                self.assertEqual(h.owner.accepted,[])
                release.set();owned_thread.join(3);foreign_thread.join(3)
            self.assertEqual(errors,[])
            self.assertEqual(len(foreign_errors),1)
            self.assertTrue(port.owns_plan(plan))
            self.assertEqual(len(h.owner.accepted),1)
            port.stop(expected_plan=plan)
        finally:
            release.set();owned_thread.join(3)
            if foreign_thread.ident is not None:foreign_thread.join(3)

    def test_promotion_worker_matches_baseline_without_selecting_and_drops_partial_pair(self):
        for fails in (False,True):
            states=[]
            for frozen in (True,False):
                h=self.fixture(frozen=frozen,promotion=True)
                h.manager.state={"phase":"queued","plan":{},"modes":{},"runtimes":{
                    role:{"phase":"queued"} for role in ("selected","candidate")},"events":[],"result":None}
                count=0
                def measure(job,_models,_mode,completed,_total,_gate,**_kwargs):
                    nonlocal count
                    count+=1
                    if fails and count==2:raise RuntimeError("Generated second copy failed")
                    return {"medianEndToEndTokensPerSecond":10,"medianTTFT":.1},completed+3
                with mock.patch.object(h.manager,"_measure_mode",side_effect=measure), \
                        mock.patch.object(h.manager,"_wait_for_resource_baseline",return_value={"status":"unavailable"}):
                    h.manager._worker(h.promotion_plan(),[h.model])
                state=h.manager.snapshot()
                self.assertEqual(state["phase"],"failed" if fails else "completed")
                self.assertEqual(len(h.promotion_saved),0 if fails else 1)
                self.assertEqual(h.selected_calls,[])
                states.append(normalize({"state":state,"records":h.promotion_saved}))
                h.close()
            self.assertEqual(states[0],states[1])


if __name__=="__main__":unittest.main()
