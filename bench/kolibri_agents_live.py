#!/usr/bin/env python3
"""Opt-in full Kolibri -> installed Pi/oh-my-pi native tool verification.

Use only generated write/read markers and private temporary projects/configs.
The selected route remains8192context/1024output/BF16KV/8–12GBfixedceiling/
64-token prefill/1GiB retained prompt cache. A shared model lock, fresh native
qualification, physical memory+agent+macOS reserves and live monitoring bound
the run. Stops only process groups started here; no downloads/global settings.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from unittest import mock
import uuid
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import kolibri_runtime
import darwin_memory
import launcher
import session_proxy
from bench.harness import BenchLock
from bench.kolibri_model_ab import SHIM, allow_verified_idle, native_rows
from bench.splash_agents_live import Safety, free_port, json_get, stop_owned

CONTEXT = 8192
OUTPUT = 1024
OPTIONS = {"acceleration":"off","depth":1,"kv":"off","memoryGB":12,
           "memoryMode":"fixed","prefillSize":64,"promptCacheGB":1}


class PhysicalSafety(Safety):
    def __init__(self):
        super().__init__()
        self.minimum_reclaimable = None
        self.protected_reserve = None

    def sample(self):
        super().sample()
        total = launcher.physical_memory_bytes()
        physical = darwin_memory.physical_reclaimable_state(total)
        if physical.get("physicalMemoryAvailable") is not True:
            raise RuntimeError("Fresh native physical reclaimable memory is unavailable")
        available = physical["reclaimableBytes"]
        reserve = max(launcher.SESSION_OS_RESERVE_MIN_BYTES,round(total*launcher.SESSION_OS_RESERVE_FRACTION))
        self.minimum_reclaimable = min(self.minimum_reclaimable if self.minimum_reclaimable is not None else available,available)
        self.protected_reserve = reserve
        if available < reserve:
            raise RuntimeError("Native physical reclaimable capacity fell below the protected macOS reserve")


def executable_identity(binary):
    path = Path(binary)
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle,"sha256").hexdigest()
    return {"path":str(path.resolve()),"sha256":digest}


def memory_guard(info, options):
    resource = kolibri_runtime.current_resource()
    plan = kolibri_runtime.memory_plan(info,CONTEXT,options,resource)
    physical = darwin_memory.physical_reclaimable_state(launcher.physical_memory_bytes())
    agent_reserve = 2*1024**3
    required = plan["estimatedWorkingSetBytes"]+plan["osReserveBytes"]+agent_reserve
    ready = bool(plan["ready"] is True and physical.get("physicalMemoryAvailable") is True
                 and physical["reclaimableBytes"] >= required)
    return {"ready":ready,"resource":resource,"memoryPlan":plan,"physical":physical,
            "physicalRequiredHeadroomBytes":required,"agentCompanionReserveBytes":agent_reserve}


def run_client(plan, binary, root, safety):
    project = root / "project"; project.mkdir()
    (root / "agent").mkdir()
    (root / "data/omp").mkdir(parents=True)
    marker = f"KOLIBRI_{plan.client.upper()}_VERIFIED_7193"
    prompt = (f"Use write to create proof.txt containing exactly {marker}. "
              "Then use read on proof.txt to verify it. Finally reply with that marker. "
              "Do not use other tools or files. This needs only a brief check.")
    env = {"PATH":os.environ["PATH"],"TMPDIR":str(root),"PI_CODING_AGENT_DIR":str(root / "agent"),
           "PI_CODING_AGENT_SESSION_DIR":str(root / "sessions"),"XDG_DATA_HOME":str(root / "data"),
           "PI_OFFLINE":"1","PI_TELEMETRY":"0",**plan.client_env}
    flags = ["--no-extensions","--no-skills","--tools","read,write","--system-prompt",
             "You are verifying a local tool transport. Follow the exact small task and stop."]
    if plan.client == "pi":
        flags += ["--no-prompt-templates","--no-themes","--no-context-files","--no-approve","--offline"]
    else:
        flags += ["--no-rules","--no-title","--no-lsp","--no-prewalk","--no-pty"]
    argv = [binary,*flags,*plan.client_argv[1:],"--mode","json","--print","--no-session",prompt]
    child = subprocess.Popen(argv,cwd=project,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                             start_new_session=True)
    safety.groups.add(child.pid)
    try:
        deadline = time.monotonic()+180
        while time.monotonic() < deadline:
            safety.check()
            try:
                stdout,stderr = child.communicate(timeout=1)
                break
            except subprocess.TimeoutExpired:
                continue
        else:
            raise TimeoutError(f"{plan.client} exceeded its180s native tool-check deadline")
        if child.returncode != 0:
            raise RuntimeError(f"{plan.client} failed with code{child.returncode}: {stderr[-1600:]}")
        if not (project / "proof.txt").is_file() or (project / "proof.txt").read_text().strip() != marker:
            raise AssertionError(f"{plan.client} did not complete the actual write/read task")
        events = [json.loads(line) for line in stdout.splitlines() if line.startswith("{")]
        tools = [event for event in events if event.get("type") == "tool_execution_end"]
        successful = [event for event in tools if event.get("isError") is False]
        executed_names = {event.get("toolName") for event in successful}
        read_verified = any(event.get("toolName") == "read" and marker in json.dumps(event.get("result"))
                            for event in successful)
        if not {"read","write"}.issubset(executed_names) or not read_verified:
            raise AssertionError(f"{plan.client} did not execute a successful write and read returning the actual marker")
        finals = [event["message"] for event in events if event.get("type") == "message_end" and
                  event.get("message",{}).get("role") == "assistant"]
        if not finals or finals[-1].get("stopReason") != "stop" or marker not in json.dumps(finals[-1].get("content")):
            raise AssertionError(f"{plan.client} did not finish with the verified marker")
        return {"toolFileVerified":True,"finalAnswerVerified":True,"executedWriteReadVerified":True,
                "readResultMarkerVerified":True,"successfulToolExecutions":len(successful)}
    finally:
        stop_owned(child); safety.groups.discard(child.pid)


def verify_agent(client,binary,model,port,key,root,safety):
    root.mkdir()
    run_id = str(uuid.uuid4())
    contract = launcher.build_sampling_contract("custom",custom={"temperature":0,"top_p":1,"top_k":0,"seed":42}).as_dict()
    enforcement = launcher.sampling_route_enforcement("kolibri",client,model["backends"]["kolibri"],contract)
    client_key = secrets.token_urlsafe(32)
    requests = []
    relay = session_proxy.RelayHTTPServer(("127.0.0.1",0),session_proxy.ProxyHandler)
    relay.config = {"listenPort":relay.server_port,"upstreamPort":port,"upstreamKey":key,
                    "controlKey":secrets.token_urlsafe(32),"backend":"kolibri","servedModel":kolibri_runtime.MODEL_ID,
                    "reasoning":"off","outputLimit":OUTPUT}
    relay.registry = session_proxy.SurfaceRegistry([{"id":run_id,"client":client,"key":client_key,
                       "samplingContract":contract,"samplingEnforcement":enforcement}])
    relay.scheduler = session_proxy.RequestScheduler(1)
    worker = threading.Thread(target=relay.serve_forever,daemon=True); worker.start()
    plan = launcher.LaunchPlan(run_id=run_id,backend="kolibri",client=client,model=model,project=str(root / "project"),
        context=CONTEXT,output=OUTPUT,reasoning="off",port=port,mode="custom",options=dict(OPTIONS),run_dir=root,
        sampling_contract=contract,sampling_enforcement=enforcement)
    try:
        with mock.patch.dict(launcher.BINARIES,{client:binary}):
            builder = launcher.build_pi_client if client == "pi" else launcher.build_omp_client
            builder(plan,launcher.ClientRoute("kolibri-live",kolibri_runtime.MODEL_ID,
                    f"http://127.0.0.1:{relay.server_port}/v1",client_key))
        relay.config["servedModelAliases"] = [launcher.pi_model_identity(plan)[1]]
        transform = session_proxy.transform_chat_request
        def record(body,config,surface=None):
            data = transform(body,config,surface)
            requests.append(json.loads(data)); return data
        started = time.monotonic()
        with mock.patch.object(session_proxy,"transform_chat_request",record):
            result = run_client(plan,binary,root,safety)
        if len(requests) < (3 if client == "pi" else 2):
            raise AssertionError(f"{client} omitted write/read/final rounds")
        if any(request.get("model") != kolibri_runtime.MODEL_ID or request.get("max_tokens") != OUTPUT or
               request.get("reasoning_effort") != "none" or request.get("temperature") != 0 for request in requests):
            raise AssertionError(f"{client} changed the exact route/output/reasoning/sampling contract")
        tool_calls = [tool["function"]["name"] for message in requests[-1]["messages"] if message.get("role") == "assistant"
                      for tool in message.get("tool_calls",[])]
        if not {"read","write"}.issubset(tool_calls) or not any(m.get("role") == "tool" for m in requests[-1]["messages"]):
            raise AssertionError(f"{client} dropped actual tool-call history")
        metrics = relay.scheduler.snapshot(relay.registry.public())["recent"]
        if len(metrics) != len(requests) or any(item.get("result") != "completed" for item in metrics):
            raise AssertionError(f"{client} did not record all completed model requests")
        return {"client":client,"requests":len(requests),"nativeTools":["read","write"],**result,
                "historyVerified":True,"exactRouteOutputReasoningSamplingVerified":True,
                "authenticatedSurfaceVerified":True,"elapsedSeconds":time.monotonic()-started,
                "metrics":[{field:item.get(field) for field in ("promptTokens","completionTokens","runSeconds",
                    "firstOutputSeconds","generationSeconds","decodeTokensPerSecond","observedStatsSource",
                    "runtimeTokensPerSecond","runtimeStatsSource","result","statusCode")} for item in reversed(metrics)]}
    finally:
        relay.shutdown(); relay.server_close(); worker.join(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model",type=Path,required=True)
    for name in ("python","pi","omp"):
        parser.add_argument(f"--{name}",required=True)
    parser.add_argument("--result",type=Path,required=True)
    parser.add_argument("--idle-omlx-port",type=int)
    args = parser.parse_args()
    # Validate exact client controls before allocating an owned model.
    launcher.build_sampling_contract("custom",custom={"temperature":0,"top_p":1,"top_k":0,"seed":42})
    info = kolibri_runtime.inspect_model(args.model); runtime = kolibri_runtime.inspect_runtime(args.python)
    if not info or not runtime:
        raise RuntimeError("Requires fresh complete Kolibri Q6 checkpoint and qualified native runtime")
    model = {"id":"kolibri-native-tools","name":"Kolibri-1 Q6","path":info["path"],"size":info["weightBytes"],
             "format":"mlx","kolibri":info,"backends":{"kolibri":kolibri_runtime.capability(info,runtime)}}
    safety = PhysicalSafety(); child = None
    report = {"kind":"native-Kolibri-Pi-OMP-tools","runtime":runtime,"modelIdentity":info["identity"],
              "measuredAt":datetime.now(timezone.utc).isoformat(),
              "agentExecutables":{client:executable_identity(binary)
                    for client,binary in (("pi",args.pi),("omp",args.omp))},
              "providerSourceSha256":{name:hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                      for name in ("pi-provider.js","omp-provider.mjs")},
              "contract":{"context":CONTEXT,"output":OUTPUT,"reasoning":"off","options":dict(OPTIONS)},"agents":[]}
    try:
        with BenchLock("Kolibri real Pi/OMP bounded native tools",wait_seconds=60), tempfile.TemporaryDirectory(prefix="kolibri-native-tools-") as directory:
            root = Path(directory)
            allow_verified_idle(safety,args.idle_omlx_port)
            guard = memory_guard(info,OPTIONS)
            if not guard["ready"]:
                OPTIONS["memoryGB"] = 8
                report["contract"]["options"] = dict(OPTIONS)
                guard = memory_guard(info,OPTIONS)
            report["guard"] = guard
            if not guard["ready"]:
                report["blocked"] = "physical-headroom"; return
            safety.worker.start()
            run = root / "engine"; run.mkdir()
            shim = run / "worker-shim.py"; shim.write_text(SHIM)
            metrics = run / "native-metrics.jsonl"
            plan = launcher.LaunchPlan(run_id=str(uuid.uuid4()),backend="kolibri",client="chat",model=model,
                project=str(root),context=CONTEXT,output=OUTPUT,reasoning="off",port=free_port(),mode="custom",
                options=dict(OPTIONS),run_dir=run,runtime_binary=runtime["python"])
            with mock.patch.dict(launcher.BINARIES,{"kolibri":runtime["python"]}):
                launcher.build_kolibri(plan,model["backends"]["kolibri"])
            env = kolibri_runtime.clean_environment(dict(os.environ))
            env.update({"HF_HUB_OFFLINE":"1","TRANSFORMERS_OFFLINE":"1","HF_HUB_DISABLE_TELEMETRY":"1",
                        "STREAMLX_PREFETCH":"0","STREAMLX_RESIDENT":"off"})
            argv = [runtime["python"],"-I","-B","-u",str(shim),str(ROOT),str(run / "kolibri.json"),"1",str(metrics)]
            with (run / "engine.log").open("w") as log:
                child = subprocess.Popen(argv,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,text=True,start_new_session=True)
                safety.groups.add(child.pid); report["engineStarted"] = True
                deadline = time.monotonic()+90
                while time.monotonic() < deadline:
                    safety.check()
                    if child.poll() is not None:
                        raise RuntimeError("Owned Kolibri worker exited during startup")
                    try:
                        catalog = json_get(plan.port,"/v1/models",plan.secrets["apiKey"])
                        report["liveMemoryPlan"] = kolibri_runtime.validate_served_catalog(catalog,CONTEXT,OPTIONS)
                        break
                    except OSError:
                        time.sleep(.25)
                else:
                    raise TimeoutError("Owned Kolibri worker exceeded90s startup limit")
                try:
                    json_get(plan.port,"/v1/models")
                except urllib.error.HTTPError as error:
                    if error.code != 401:
                        raise AssertionError("Unauthenticated model endpoint returned an unexpected status") from error
                    report["engineAuthenticationEnforced"] = True
                else:
                    raise AssertionError("Owned Kolibri accepted an unauthenticated catalog request")
                for client,binary in (("pi",args.pi),("omp",args.omp)):
                    safety.sample()
                    print(f"[kolibri] actual {client} write/read/final verification",flush=True)
                    native_start = len(native_rows(metrics))
                    try:
                        agent = verify_agent(client,binary,model,plan.port,plan.secrets["apiKey"],root / client,safety)
                        native_for_agent = native_rows(metrics)[native_start:]
                        if len(native_for_agent) != agent["requests"]:
                            raise AssertionError("Direct native observer did not cover every agent request")
                        for relay_metric,direct in zip(agent["metrics"],native_for_agent):
                            if (relay_metric.get("runtimeStatsSource") != "kolibri-native-stats"
                                    or not isinstance(relay_metric.get("runtimeTokensPerSecond"),(int,float))
                                    or not math.isclose(relay_metric["runtimeTokensPerSecond"],direct["generationTokensPerSecond"],rel_tol=1e-6)
                                    or relay_metric.get("completionTokens") != direct["generationTokens"]):
                                raise AssertionError("Relay native TPS/counts disagreed with the direct generation observer")
                        agent["nativeRatesAndCountsMatchRelay"] = True
                        report["agents"].append(agent)
                    finally:
                        # Retain primitive counters even if a later client
                        # fails; temporary tool/config files are still removed.
                        report["nativeRequests"] = native_rows(metrics)
                        report["rawUsage"] = native_rows(Path(str(metrics)+".usage.jsonl"))
                report["nativeRequests"] = native_rows(metrics)
                report["rawUsage"] = native_rows(Path(str(metrics)+".usage.jsonl"))
                if len(report["rawUsage"]) != sum(agent["requests"] for agent in report["agents"]):
                    raise AssertionError("Raw native usage did not cover all agent model requests")
                report["prefixReuseObserved"] = any(
                    (row.get("usage",{}).get("prompt_tokens_details") or {}).get("cached_tokens",0) > 0
                    for row in report["rawUsage"])
    except Exception as error:
        report["error"] = {"type":type(error).__name__,"message":str(error)}
        raise
    finally:
        if child is not None:
            stop_owned(child); safety.groups.discard(child.pid)
            report["ownedEngineStopped"] = child.poll() is not None
        safety.stop.set()
        if safety.worker.is_alive():
            safety.worker.join(timeout=8)
        report.update({"minimumPressureFreePercent":safety.minimum_free,
                       "minimumPhysicalReclaimableBytes":safety.minimum_reclaimable,
                       "protectedMacOsReserveBytes":safety.protected_reserve,
                       "peakOwnedGroupPhysicalFootprintBytes":safety.peak_footprint})
        args.result.parent.mkdir(parents=True,exist_ok=True)
        args.result.write_text(json.dumps(report,indent=2)+"\n")
        print(json.dumps({"result":str(args.result),"agents":[(row["client"],row["requests"]) for row in report["agents"]],
                          "blocked":report.get("blocked"),"error":report.get("error")}),flush=True)


if __name__ == "__main__":
    main()
