#!/usr/bin/env python3
"""Controlled current-launcher Pi/OMP tool qualification; default is preparation.

Preparation reads installed artifacts and validates private plans, never starts
an engine. Execution requires explicit --execute-authorized after source freeze;
all model processes are created by the normal RunManager start path, and the
second agent is attached to that same loaded model through its normal relay.
No runtime selection, installation, user agent settings or foreign shutdown.
"""
from __future__ import annotations
import argparse
import contextlib
import copy
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import socket
import sys
import tempfile
import threading
import time
from unittest import mock
import urllib.request
import urllib.error

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import launcher
import kolibri_runtime
import splash_runtime
import darwin_memory
from bench.harness import BenchLock
from bench.splash_agents_live import Safety
from bench.kolibri_model_ab import allow_verified_idle

AGENT_RESERVE=2*1024**3
KOLIBRI_OPTIONS={"acceleration":"off","depth":1,"kv":"off","memoryGB":12,
                 "memoryMode":"fixed","prefillSize":64,"promptCacheGB":1}


def artifact_model(backend,binary,path):
    if backend=="kolibri":
        runtime=kolibri_runtime.inspect_runtime(binary);info=kolibri_runtime.inspect_model(path)
        if not runtime or not info:raise ValueError("Fresh complete Kolibri Q6/runtime qualification failed")
        model={"id":"launcher-proof-kolibri-q6","name":"Kolibri-1 Q6","path":info["path"],"size":info["weightBytes"],
               "format":"mlx","ready":True,"kolibri":info,"backends":{"kolibri":kolibri_runtime.capability(info,runtime)}}
        return model,runtime,info["identity"]
    install=splash_runtime.inspect_install(binary);pack=splash_runtime.inspect_pack(path)
    if not install or not install["ready"] or not pack:raise ValueError("Fresh Splash release/pack qualification failed")
    model=splash_runtime.model_record(install,pack,[("splash","Splash")],launcher.physical_memory_bytes())
    return model,{key:install[key] for key in ("version","release","engineBinary","python","server","ready")},pack["identity"]


def request_for(backend,model,project,client="pi",memory_gb=12):
    options=copy.deepcopy(KOLIBRI_OPTIONS) if backend=="kolibri" else {}
    if backend=="kolibri":options["memoryGB"]=memory_gb
    return {"backend":backend,"client":client,"agentHost":"console","modelId":model["id"],"project":str(project),
            "context":8192 if backend=="kolibri" else 16384,"output":1024,"reasoning":"off","mode":"custom","options":options,
            "generation":{"sampling":"custom","temperature":0,"topP":1,"topK":0,"seed":42} if backend=="kolibri" else {"sampling":"model"}}


def admission(request,model):
    snapshot=launcher.apple_resource_snapshot();resource=launcher.public_session_resource(snapshot)
    decision=launcher.session_memory_admission(request,[model],resource,{"phase":"idle"},{"active":False})
    physical=darwin_memory.snapshot_reclaimable_bytes(snapshot)
    estimate=decision.get("estimate") or {}
    required=int(estimate.get("requiredHeadroomBytes") or 0)+AGENT_RESERVE
    ready=(decision.get("launchable") is True and decision.get("decision")=="ready"
           and decision.get("requiresAcknowledgement") is False and physical is not None and physical>=required and required>AGENT_RESERVE)
    return {"ready":ready,"launcherAdmission":decision,"physicalReclaimableBytes":physical,"requiredPhysicalBytes":required,
            "agentCompanionReserveBytes":AGENT_RESERVE,"physicalSource":snapshot.get("reclaimableMemorySource"),
            "pressureFreePercent":snapshot.get("freePercent"),"thermal":snapshot.get("thermalLabel"),
            "protectedOSReserveBytes":estimate.get("osReserveBytes")}


@contextlib.contextmanager
def private_paths(root,binaries):
    state=root/"state";state.mkdir();(state/"runs").mkdir();(state/"logs").mkdir()
    with mock.patch.multiple(launcher,STATE_DIR=state,RUNS_DIR=state/"runs",LOGS_DIR=state/"logs"),mock.patch.dict(launcher.BINARIES,binaries),mock.patch.dict(os.environ,{
        "PI_CODING_AGENT_DIR":str(root/"agent-default"),"XDG_DATA_HOME":str(root/"data-default"),"PI_OFFLINE":"1","PI_TELEMETRY":"0"}):
        yield


def private_agent(plan):
    root=plan.run_dir/"agent-private";root.mkdir(parents=True,exist_ok=True)
    plan.client_env.update({"PI_CODING_AGENT_DIR":str(root/"agent"),"PI_CODING_AGENT_SESSION_DIR":str(root/"sessions"),
        "XDG_DATA_HOME":str(root/"data"),"PI_OFFLINE":"1","PI_TELEMETRY":"0"})
    flags=["--no-extensions","--no-skills","--tools","read,write","--system-prompt",
           "Verify the exact small generated file task, then stop. Use only read and write."]
    flags+=(["--no-prompt-templates","--no-themes","--no-context-files","--no-approve","--offline"] if plan.client=="pi"
            else ["--no-rules","--no-title","--no-lsp","--no-prewalk","--no-pty"])
    # Keep all normal provider/context/workflow extensions and the RPC dialect.
    plan.client_argv.extend(flags)


def plan_receipt(plan):
    provider=json.loads(plan.client_env["LLM_LAUNCHER_PI_PROVIDER"] if plan.client=="pi" else plan.client_env["LLM_LAUNCHER_OMP_PROVIDER"])
    models=provider.get("models")
    contract=provider.get("model") if plan.client=="pi" else models[0] if isinstance(models,list) and len(models)==1 else None
    if not isinstance(contract,dict) or contract.get("contextWindow")!=plan.context or contract.get("maxTokens")!=plan.output or not contract.get("id"):
        raise AssertionError("Native provider model/context/output differs from the normalized launch plan")
    if plan.reasoning=="off" and contract.get("reasoning") is not False:raise AssertionError("Native provider re-enabled thinking")
    served=provider.get("transportModel") if plan.client=="pi" else contract["id"]
    expected=kolibri_runtime.MODEL_ID if plan.backend=="kolibri" else plan.model["splash"]["id"]
    if served!=expected:raise AssertionError("Native provider changed the exact served model")
    return {"backend":plan.backend,"client":plan.client,"host":plan.agent_host,"context":plan.context,"output":plan.output,
            "reasoning":plan.reasoning,"options":{key:value for key,value in plan.options.items() if not key.startswith("_")},
            "providerModel":contract.get("id"),"servedModel":served,"providerContext":contract.get("contextWindow"),"providerOutput":contract.get("maxTokens"),
            "providerThinking":contract.get("reasoning"),"authenticationConfigured":bool(provider.get("apiKey")),
            "rpcConfigured":any(plan.client_argv[i:i+2]==["--mode","rpc"] for i in range(len(plan.client_argv)-1)),
            "privateRunFiles":True,"normalizedRequest":True}


def metric_receipt(record,backend):
    source=f"{backend}-native-stats";count=record.get("runtimeDecodeTokenCount");seconds=record.get("runtimeGenerationSeconds");tps=record.get("runtimeTokensPerSecond")
    if record.get("runtimeStatsSource")!=source or record.get("result")!="completed":raise AssertionError("Completed authoritative native generation metadata is missing")
    if type(count) is not int or count<0 or not isinstance(seconds,(int,float)) or isinstance(seconds,bool) or not math.isfinite(seconds) or seconds<0:
        raise AssertionError("Native count/duration are malformed")
    if count>0 and (seconds<=0 or not isinstance(tps,(int,float)) or isinstance(tps,bool) or not math.isfinite(tps) or not math.isclose(count/seconds,tps,rel_tol=1e-5)):
        raise AssertionError("Native TPS does not rederive from its declared count/duration")
    for field in ("promptTokens","completionTokens"):
        if type(record.get(field)) is not int or record[field]<0:raise AssertionError("Exact raw HTTP usage is unavailable")
    if backend=="kolibri" and count!=record["completionTokens"]:raise AssertionError("Kolibri native count differs from raw HTTP completion usage")
    if backend=="splash":
        first=record.get("runtimeFirstBatchTokens")
        if type(first) is not int or first<0 or first+count!=record["completionTokens"]:raise AssertionError("Splash native batches differ from raw HTTP completion usage")
    expected="request-native-generation" if backend=="kolibri" else "request-lifecycle-excluding-first-native-batch"
    if record.get("runtimeThroughputBasis")!=expected:raise AssertionError("Native throughput basis is missing or unexpected")
    if count==0 and tps is not None:raise AssertionError("An empty native decode interval cannot have a TPS")
    return {key:record.get(key) for key in ("promptTokens","completionTokens","firstOutputSeconds","runSeconds","runtimeStatsSource",
        "runtimeDecodeTokenCount","runtimeGenerationSeconds","runtimeTokensPerSecond","runtimeThroughputBasis","runtimeFirstBatchTokens","promptProcessing","result")}


class ToolEvidence:
    def __init__(self):self.rows={};self.lock=threading.Lock()
    def record(self,console,event):
        key=console.plan.run_id
        with self.lock:
            row=self.rows.setdefault(key,{"tools":[],"answers":[],"roles":[]})
            if event.get("type")=="tool_execution_end":row["tools"].append(copy.deepcopy(event))
            if event.get("type")=="message_end":row["answers"].append(copy.deepcopy(event.get("message") or {}))
            if event.get("type")=="response" and event.get("command")=="get_messages":
                messages=(event.get("data") or {}).get("messages",[]);row["roles"]=[message.get("role") for message in messages]
    def verify(self,surface,marker,project):
        with self.lock:row=copy.deepcopy(self.rows.get(surface,{"tools":[],"answers":[],"roles":[]}))
        succeeded=[event for event in row["tools"] if event.get("isError") is False]
        if not {"write","read"}.issubset({event.get("toolName") for event in succeeded}):raise AssertionError("Actual successful write/read execution was not observed")
        if not any(event.get("toolName")=="read" and marker in json.dumps(event.get("result")) for event in succeeded):raise AssertionError("Native read did not return the generated marker")
        path=project/"proof.txt"
        if not path.is_file() or path.read_text().strip()!=marker:raise AssertionError("Generated proof file does not match")
        answers=[message for message in row["answers"] if message.get("role")=="assistant"]
        if not answers or answers[-1].get("stopReason")!="stop" or marker not in json.dumps(answers[-1].get("content")):raise AssertionError("Native final answer is missing")
        return {"actualWriteRead":True,"nativeReadMarker":True,"fileVerified":True,"finalMarker":True,
                "successfulToolExecutions":len(succeeded),"nativeHistoryRoles":row["roles"]}


class RouteSafety(Safety):
    def __init__(self,manager,plan,fingerprint):
        super().__init__();self.manager=manager;self.plan=plan;self.epoch=None;self.fingerprint=fingerprint;self.handles=[]
    def capture(self):
        with self.manager.lifecycle_lock,self.manager.lock:
            if self.manager.plan is not self.plan or (self.epoch is not None and self.manager.cancel_event is not self.epoch):return
            for process in [self.manager.process,self.manager.proxy_process,self.manager.aux_process,*[console.process for console in self.manager.agent_consoles.values()]]:
                if process and process not in self.handles:self.handles.append(process);self.groups.add(process.pid)
    def sample(self):
        self.capture()
        if launcher.controller_source_fingerprint()!=self.fingerprint:raise RuntimeError("Controller source changed during qualification")
        super().sample()


def wait_until(predicate,seconds,safety):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        safety.check()
        result=predicate()
        if result:return result
        time.sleep(.2)
    raise TimeoutError("Owned launcher verification phase exceeded its bounded deadline")


def prove_agent(manager,surface,backend,project,evidence,safety):
    base={"ownerRunId":manager.plan.run_id,"surfaceId":surface,"offset":0,"timelineRevision":0,"timelineVersion":1}
    def ready():
        try:data=manager.read_agent_console(base)["console"]
        except ValueError:return None
        return data if data.get("canInput") is True else None
    console=wait_until(ready,45,safety)
    marker="LAUNCHER_"+secrets.token_hex(8).upper()
    manager.write_agent_console({**base,"command":"prompt","message":f"Use write to create proof.txt containing exactly {marker}. Use read on proof.txt to verify it. Finally reply with that marker. Use only these two tools and that file."})
    def settled():
        data=manager.read_agent_console(base)["console"]
        with evidence.lock:answers=copy.deepcopy(evidence.rows.get(surface,{}).get("answers",[]))
        return data if data.get("canInput") is True and data.get("streaming") is False and any(marker in json.dumps(event) for event in answers) else None
    wait_until(settled,240,safety)
    # Native history is independently read through the already-qualified owned RPC channel.
    with manager.lock:target=manager.agent_consoles[surface]
    manager._write_pi_rpc_command(target,{"id":"launcher-proof-history","type":"get_messages"})
    wait_until(lambda:evidence.rows.get(surface,{}).get("roles"),10,safety)
    proof=evidence.verify(surface,marker,project)
    if "assistant" not in proof["nativeHistoryRoles"] or not any(role in {"tool","toolResult"} for role in proof["nativeHistoryRoles"]):raise AssertionError("Actual native tool/assistant history was not retained")
    activity=manager._session_proxy_api("GET","/__launcher/status",timeout=3)
    metrics=[record for record in activity.get("recent",[]) if record.get("surfaceId")==surface]
    if len(metrics)<2:raise AssertionError("The real tool task did not issue complete model rounds")
    return {**proof,"requests":len(metrics),"metrics":[metric_receipt(record,backend) for record in reversed(metrics)]}


def execute(plan,model,binaries,root,guard,idle_port):
    if not guard["ready"]:raise RuntimeError("Current launcher/physical admission blocks this exact route")
    if not launcher.controller_source_is_current():raise RuntimeError("Controller process is stale")
    manager=launcher.RunManager();safety=RouteSafety(manager,plan,launcher.controller_source_fingerprint());evidence=ToolEvidence()
    delegate=launcher.pi_rpc_event_output
    def observer(console,event):evidence.record(console,event);return delegate(console,event)
    original_builder=launcher.build_client_plan
    def client_builder(value):original_builder(value);private_agent(value)
    report={"agents":[],"singleModelWarmAttachment":False,"sourceFingerprint":safety.fingerprint}
    owned_cleanup=None
    try:
        allow_verified_idle(safety,idle_port);safety.sample()
        with mock.patch.object(launcher,"pi_rpc_event_output",observer),mock.patch.object(launcher,"build_client_plan",client_builder):
            manager.start(plan);safety.epoch=manager.cancel_event;owned_cleanup=manager.cleanup_complete;safety.worker.start()
            def running():
                state=manager.snapshot()
                if state.get("phase")=="failed":raise RuntimeError("The normal launcher failed startup: "+str(state.get("message") or "unknown")[:400])
                return state.get("phase")=="running"
            wait_until(running,120,safety)
            if manager.plan is not plan or manager.cancel_event is not safety.epoch:raise RuntimeError("Accepted launcher epoch changed")
            for port in (plan.port,plan.client_port):
                try:urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models",timeout=3)
                except urllib.error.HTTPError as error:
                    if error.code!=401:raise AssertionError("Owned endpoint returned an unexpected unauthenticated status")
                else:raise AssertionError("Owned endpoint accepted an unauthenticated model request")
            report["engineAndRelayAuthenticationEnforced"]=True
            report["agents"].append({"client":"pi",**prove_agent(manager,plan.run_id,plan.backend,Path(plan.project),evidence,safety)})
            project=root/"omp-project";project.mkdir()
            attachment=manager.attachment_plan({"ownerRunId":plan.run_id,"client":"omp","agentHost":"console","project":str(project),"generation":request_for(plan.backend,model,project,"omp")["generation"]})
            if attachment["action"]["loadsWeights"] is not False or attachment["action"]["startsEngine"] is not False:raise AssertionError("Warm attachment would duplicate model ownership")
            engine=manager.process
            result=manager.attach_surface({"ownerRunId":plan.run_id,"client":"omp","agentHost":"console","project":str(project),"generation":request_for(plan.backend,model,project,"omp")["generation"]})
            if manager.process is not engine:raise AssertionError("Warm attachment replaced the engine")
            report["singleModelWarmAttachment"]=True
            report["agents"].append({"client":"omp",**prove_agent(manager,result["attachment"]["id"],plan.backend,project,evidence,safety)})
            safety.sample();safety.check()
    finally:
        safety.stop.set()
        if safety.worker.ident is not None:safety.worker.join(timeout=3)
        safety.capture()
        if safety.epoch is not None:manager.stop(expected_plan=plan,expected_cancel_event=safety.epoch)
        if safety.epoch is not None and not owned_cleanup.wait(30):raise RuntimeError("Owned launcher cleanup did not complete")
        if any(process.poll() is None for process in safety.handles):raise RuntimeError("An owned process remained alive")
        for process in safety.handles:
            try:os.killpg(process.pid,0)
            except ProcessLookupError:continue
            raise RuntimeError("An owned process group remained after cleanup")
        report["cleanup"]={"ownedProcessesExited":True,"ownedGroupsExited":True,"managerIdle":manager.snapshot().get("phase")=="idle","foreignServicesUntouched":True}
        report["memory"]={"minimumPhysicalReclaimableBytes":safety.minimum_reclaimable,"protectedOSReserveBytes":safety.protected_reserve,"peakOwnedGroupPhysicalFootprintBytes":safety.peak_footprint}
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--backend",choices=["kolibri","splash"],required=True)
    parser.add_argument("--model",type=Path,required=True);parser.add_argument("--engine",required=True);parser.add_argument("--pi",required=True);parser.add_argument("--omp",required=True)
    parser.add_argument("--result",type=Path,required=True);parser.add_argument("--memory-gb",type=int,choices=[8,12],default=12);parser.add_argument("--idle-omlx-port",type=int)
    parser.add_argument("--execute-authorized",action="store_true");args=parser.parse_args()
    binaries={args.backend:args.engine,"pi":args.pi,"omp":args.omp}
    report={"kind":"current-launcher-agent-route-proof","phase":"preparation","modelStarted":False,"measuredAt":datetime.now(timezone.utc).isoformat(),
        "sourceFingerprint":launcher.controller_source_fingerprint(),"harnessSha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "artifactPath":str(args.model.resolve()),"entryPath":["normalized_request","RunManager.start","session_proxy","inference_requests","native-agent-rpc"]}
    with tempfile.TemporaryDirectory(prefix="launcher-final-route-") as folder:
        root=Path(folder);project=root/"pi-project";project.mkdir()
        with private_paths(root,binaries):
            report["agentExecutables"]={name:{"path":str(Path(binaries[name]).resolve()),"version":launcher.command_version(binaries[name]),
                  "sha256":hashlib.sha256(Path(binaries[name]).resolve().read_bytes()).hexdigest()} for name in ("pi","omp")}
            model,runtime,identity=artifact_model(args.backend,args.engine,args.model)
            request=request_for(args.backend,model,project,memory_gb=args.memory_gb);guard=admission(request,model)
            omp_request={**copy.deepcopy(request),"client":"omp"};omp_guard=admission(omp_request,model)
            launcher._require_omp_console_support("omp","console")
            guard["ready"]=guard["ready"] and omp_guard["ready"]
            report.update(runtime=runtime,modelIdentity=identity,request={**request,"project":"generated-private-project"},guard=guard,ompGuard=omp_guard)
            launcher_ready=all(item["launcherAdmission"].get("launchable") is True and item["launcherAdmission"].get("decision")=="ready"
                               and item["launcherAdmission"].get("requiresAcknowledgement") is False for item in (guard,omp_guard))
            if launcher_ready:
                # Plan materialization writes only disposable private files. The
                # independent physical + companion guard still gates all Start.
                plan=launcher.normalized_request(request,[model]);private_agent(plan)
                try:
                    report["plan"]=plan_receipt(plan)
                    omp_plan=launcher.normalized_request(omp_request,[model])
                    try:report["ompPlan"]=plan_receipt(omp_plan)
                    finally:launcher.dispose_plan_secrets(omp_plan)
                    if args.execute_authorized:
                        if not guard["ready"]:raise RuntimeError("The independent physical + agent reserve blocks execution of this exact prepared plan")
                        with BenchLock("current normalized launcher real Pi/OMP tool qualification",wait_seconds=60):
                            guard=admission(request,model)
                            report["executionGuard"]=guard
                            report.update(execute(plan,model,binaries,root,guard,args.idle_omlx_port));report["phase"]="completed";report["modelStarted"]=True
                finally:launcher.dispose_plan_secrets(plan)
            if not guard["ready"]:report["blocked"]="Exact launcher admission or physical reserve does not fit; settings were not changed."
    args.result.parent.mkdir(parents=True,exist_ok=True);args.result.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"phase":report["phase"],"ready":report["guard"]["ready"],"modelStarted":report["modelStarted"],"result":str(args.result)}))

if __name__=="__main__":main()
