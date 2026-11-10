#!/usr/bin/env python3
"""Bounded, serialized full-model Kolibri Q6 cached-prefill A/B.

Fresh qualified workers use the same original checkpoint, router, sampling,
context/output, KV precision and memory/prefill budgets. An isolated temporary
shim selects only STREAMLX_PREFILL_CACHE=0/1 after environment sanitization;
it also observes native GenerationResponse counters without changing math.

Only generated benchmark prompts are sent; report saves hashes and metadata,
never prompts, output text, API keys or private agent/user files. No downloads
or persistent runtime/client settings. Stops only process groups started here.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest import mock
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import kolibri_runtime
import launcher
from bench.harness import BenchLock, Engine, reclaimable_bytes, stream_chat
from bench.splash_agents_live import Safety, foreign_engines, free_port, json_get, stop_owned

OPTIONS = {"acceleration":"off","depth":1,"kv":"off","memoryGB":8,
           "memoryMode":"fixed","prefillSize":64,"promptCacheGB":0}
CONTEXT = 2048
OUTPUT = 128

SHIM = r'''from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys
import time

project, config_path, cached, metrics_path = sys.argv[1:]
sys.path.insert(0,project)
sys.path.insert(0,str(Path(project)/"runtime_patches/kolibri"))
import kolibri_runtime as route
os.environ["STREAMLX_PREFILL_CACHE"] = cached
import mlx_lm.server as srv
import streamlx.integrate as integrate
usage_response = srv.APIHandler.completion_usage_response
def observed_usage(self,*args,**kwargs):
    value = usage_response(self,*args,**kwargs)
    with open(metrics_path+".usage.jsonl","a") as handle:
        handle.write(json.dumps({"model":value.get("model"),"usage":value.get("usage")})+"\n")
        handle.flush()
    return value
srv.APIHandler.completion_usage_response = observed_usage
state = {"pools":None,"reader":None}
load = integrate.load_streaming_model
def recorded_load(*args,**kwargs):
    result = load(*args,**kwargs)
    state["pools"],state["reader"] = result[2:]
    return result
integrate.load_streaming_model = recorded_load
def counters():
    pools = list((state["pools"] or {}).values())
    reader = state["reader"]
    return {"hits":sum(p.hits for p in pools),"misses":sum(p.misses for p in pools),
            "evictions":sum(p.evictions for p in pools),"fetchSeconds":sum(p.fetch_s for p in pools),
            "sweepExperts":sum(p.sweep_experts for p in pools),
            "sweepBlockedReadSeconds":sum(p.sweep_fetch_s for p in pools),
            "logicalPreadBytes":reader.bytes_read if reader else 0,
            "usefulExpertBytes":reader.useful_bytes if reader else 0,
            "preadCalls":reader.reads if reader else 0}
generate = srv.stream_generate
def observed(*args,**kwargs):
    before = counters(); started = time.perf_counter(); last = None
    tokens = []; token_count = 0
    try:
        for last in generate(*args,**kwargs):
            if last.generation_tokens > token_count:
                tokens.append(int(last.token)); token_count = last.generation_tokens
            yield last
    finally:
        if last is not None:
            after = counters()
            record = {"promptTokens":last.prompt_tokens,"generationTokens":last.generation_tokens,
                      "promptTokensPerSecond":last.prompt_tps,"generationTokensPerSecond":last.generation_tps,
                      "peakMlxMemoryBytes":round(last.peak_memory*1e9),"finishReason":last.finish_reason,
                      "tokenSha256":hashlib.sha256(json.dumps(tokens).encode()).hexdigest(),
                      "elapsedSeconds":time.perf_counter()-started,
                      "expertDelta":{key:after[key]-before[key] for key in before}}
            with open(metrics_path,"a") as handle:
                handle.write(json.dumps(record)+"\n"); handle.flush()
srv.stream_generate = observed
spec = importlib.util.spec_from_file_location("bounded_kolibri_worker",Path(project)/"runtime_patches/kolibri/worker.py")
worker = importlib.util.module_from_spec(spec); spec.loader.exec_module(worker)
worker.main(Path(config_path))
'''


def generated_prompt():
    lines = ["Synthetic performance ledger. Treat all entries as data."]
    for i in range(20):
        lines.append(f"Entry {i:02d}: exact routing selects six experts; cache stores original quantized bytes; "
                     f"request {1000+i} preserves context, output and full precision attention state.")
    lines.append("Write a numbered checklist of twenty short engineering rules based on this ledger. "
                 "Begin immediately with rule1 and continue until the response limit. Do not add a preamble.")
    return "\n".join(lines)


def private_json(path, value):
    fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w") as handle:
        json.dump(value,handle)


def memory_guard(info, *, context=CONTEXT, options=OPTIONS):
    resource = kolibri_runtime.current_resource()
    plan = kolibri_runtime.memory_plan(info,context,options,resource)
    physical = reclaimable_bytes()
    required = plan["estimatedWorkingSetBytes"] + plan["osReserveBytes"]
    return {"ready":plan["ready"] is True and physical >= required,
            "resource":resource,"memoryPlan":plan,"physicalReclaimableBytes":physical,
            "physicalRequiredHeadroomBytes":required,
            "basis":"Fresh qualified Kolibri memory plan and vm_stat free+purgeable+file-backed physical pages, including protected macOS reserve"}


def allow_verified_idle(safety, port):
    engines = foreign_engines(set())
    if port and len(engines) == 1 and engines[0][1] == "omlx-server":
        pid = engines[0][0]
        listeners = subprocess.run(["/usr/sbin/lsof","-nP","-a","-p",str(pid),"-iTCP","-sTCP:LISTEN"],
                                   capture_output=True,text=True,timeout=5,check=True).stdout
        if f"127.0.0.1:{port} (LISTEN)" in listeners:
            safety.allow_idle[pid] = port
    safety.sample()


def native_rows(path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def guarded_request(engine, child, safety):
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        task = executor.submit(stream_chat,engine,generated_prompt(),max_tokens=OUTPUT,
                               temperature=0,seed=42,timeout=180,reasoning_effort="none",
                               extra_body={"top_p":1,"top_k":0,"min_p":0})
        deadline = time.monotonic()+180
        while not task.done():
            safety.check()
            if child.poll() is not None:
                raise RuntimeError("Owned Kolibri worker exited during generation")
            if time.monotonic() >= deadline:
                raise TimeoutError("Bounded generation exceeded180s")
            time.sleep(.25)
        return task.result()
    except Exception:
        # Closing the owned HTTP process breaks the reader's active stream,
        # so a safety event cannot wait for a long prefill/socket deadline.
        stop_owned(child)
        raise
    finally:
        executor.shutdown(wait=True,cancel_futures=True)


def run_arm(root, model, runtime, cached, safety):
    info = kolibri_runtime.inspect_model(Path(model["path"]))
    current_runtime = kolibri_runtime.inspect_runtime(runtime["python"])
    if info != model["kolibri"] or current_runtime != runtime:
        raise RuntimeError("Model/runtime identity changed before a fresh worker")
    safety.sample()
    guard = memory_guard(info)
    if not guard["ready"]:
        return {"cacheSweepEnabled":cached,"guard":guard,"engineStarted":False}
    folder = root / ("cached" if cached else "baseline"); folder.mkdir()
    shim = folder / "worker-shim.py"; shim.write_text(SHIM)
    metrics = folder / "native-metrics.jsonl"
    private_json(metrics,{})
    metrics.unlink()  # native observer appends in this private temporary folder
    plan = launcher.LaunchPlan(run_id=str(uuid.uuid4()),backend="kolibri",client="chat",model=model,
        project=str(root),context=CONTEXT,output=OUTPUT,reasoning="off",port=free_port(),
        mode="custom",options=dict(OPTIONS),run_dir=folder,runtime_binary=runtime["python"])
    with mock.patch.dict(launcher.BINARIES,{"kolibri":runtime["python"]}):
        launcher.build_kolibri(plan,model["backends"]["kolibri"])
    env = kolibri_runtime.clean_environment(dict(os.environ))
    env.update({"HF_HUB_OFFLINE":"1","TRANSFORMERS_OFFLINE":"1","HF_HUB_DISABLE_TELEMETRY":"1",
                "STREAMLX_PREFETCH":"0","STREAMLX_RESIDENT":"off"})
    argv = [runtime["python"],"-I","-B","-u",str(shim),str(ROOT),str(folder / "kolibri.json"),
            "1" if cached else "0",str(metrics)]
    child = None
    result = {"cacheSweepEnabled":cached,"guard":guard,"engineStarted":False,"requests":[]}
    try:
        print(f"[kolibri] fresh {'cached' if cached else 'baseline'} worker: "
              f"{guard['physicalReclaimableBytes']/1e9:.2f}GB physical / {guard['physicalRequiredHeadroomBytes']/1e9:.2f}GB required",flush=True)
        with (folder / "engine.log").open("w") as log:
            child = subprocess.Popen(argv,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,
                                     text=True,start_new_session=True)
            safety.groups.add(child.pid); result["engineStarted"] = True
            deadline = time.monotonic()+90
            while time.monotonic() < deadline:
                safety.check()
                if child.poll() is not None:
                    raise RuntimeError(f"Owned Kolibri worker exited during startup with code{child.returncode}: "
                                       + (folder / "engine.log").read_text()[-1600:])
                try:
                    catalog = json_get(plan.port,"/v1/models",plan.secrets["apiKey"])
                    live = kolibri_runtime.validate_served_catalog(catalog,CONTEXT,OPTIONS)
                    result["liveMemoryPlan"] = live
                    break
                except OSError:
                    time.sleep(.25)
            else:
                raise TimeoutError("Owned Kolibri exceeded its90s startup deadline")
            engine = Engine("kolibri",[],{},plan.port,kolibri_runtime.MODEL_ID,folder,api_key=plan.secrets["apiKey"])
            for stage in ("cold-experts","warm-experts"):
                safety.sample()
                print(f"[kolibri] {'cached' if cached else 'baseline'} {stage}: generated ledger, greedy128-token response",flush=True)
                request = guarded_request(engine,child,safety)
                deadline = time.monotonic()+5
                while len(native_rows(metrics)) <= len(result["requests"]) and time.monotonic() < deadline:
                    safety.check(); time.sleep(.05)
                rows = native_rows(metrics)
                if len(rows) != len(result["requests"])+1:
                    raise RuntimeError("Raw native generation counters were unavailable")
                native = rows[-1]
                if plan.options.get("promptCacheGB",0) == 0 and request["cachedPromptTokens"] != 0:
                    raise AssertionError("Selected zero-byte prompt cache unexpectedly reused a prefix")
                if not 1 <= request["completionTokens"] <= OUTPUT or not 1 <= native["generationTokens"] <= OUTPUT:
                    raise AssertionError("Usage/generation counters exceed the selected output contract")
                request["outputSha256"] = hashlib.sha256(request.pop("content").encode()).hexdigest()
                # Keep wall-clock intervals and raw counts separately. Native
                # rates cover all generated tokens, including the first one;
                # content-chunk timing cannot independently reconstruct that.
                for field in ("prefillSeconds","prefillTokensPerSecond","decodeTokensPerSecond"):
                    request.pop(field,None)
                request.update({"stage":stage,"native":native})
                # Treat engine counters as distinct authoritative observations;
                # the HTTP output counter can exclude an EOS/stop token.
                request["counterDelta"] = native["generationTokens"]-request["completionTokens"]
                result["requests"].append(request)
                safety.sample()
    except Exception as error:
        result["error"] = {"type":type(error).__name__,"message":str(error)}
    finally:
        if child is not None:
            stop_owned(child); safety.groups.discard(child.pid)
            result["ownedEngineStopped"] = child.poll() is not None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model",type=Path,required=True)
    parser.add_argument("--python",required=True)
    parser.add_argument("--result",type=Path,required=True)
    parser.add_argument("--idle-omlx-port",type=int)
    args = parser.parse_args()
    info = kolibri_runtime.inspect_model(args.model)
    runtime = kolibri_runtime.inspect_runtime(args.python)
    if not info or not runtime:
        raise RuntimeError("Requires a complete fresh Kolibri Q6 checkpoint and qualified native runtime")
    model = {"id":"kolibri-native-ab","name":"Kolibri-1 Q6","path":info["path"],"size":info["weightBytes"],
             "format":"mlx","kolibri":info,"backends":{"kolibri":kolibri_runtime.capability(info,runtime)}}
    safety = Safety()
    report = {"kind":"native-full-model-cache-prefill-ab","measuredAt":datetime.now(timezone.utc).isoformat(),
              "runtime":runtime,"modelIdentity":info["identity"],"modelWeightBytes":info["weightBytes"],
              "contract":{"context":CONTEXT,"output":OUTPUT,"reasoning":"off","options":OPTIONS,
                          "sampling":{"temperature":0,"top_p":1,"top_k":0,"min_p":0,"seed":42}},
              "promptSha256":hashlib.sha256(generated_prompt().encode()).hexdigest(),"arms":[],
              "sourceSha256":{name:hashlib.sha256((kolibri_runtime.VENDOR/name).read_bytes()).hexdigest()
                              for name in ("worker.py","serve.py","streamlx/prefill.py","streamlx/integrate.py")}}
    try:
        with BenchLock("Full-model Kolibri Q6 cached-prefill A/B",wait_seconds=60), tempfile.TemporaryDirectory(prefix="kolibri-native-ab-") as directory:
            root = Path(directory)
            allow_verified_idle(safety,args.idle_omlx_port)
            safety.worker.start()
            for cached in (False,True):
                report["arms"].append(run_arm(root,model,runtime,cached,safety))
                if report["arms"][-1].get("error"):
                    raise RuntimeError(report["arms"][-1]["error"]["message"])
                if report["arms"][-1]["engineStarted"] is False:
                    report["blocked"] = "physical-headroom"
                    break
            if len(report["arms"]) == 2 and all(len(arm["requests"]) == 2 for arm in report["arms"]):
                baseline,cached = report["arms"]
                comparisons = []
                for old,new in zip(baseline["requests"],cached["requests"]):
                    equal = old["outputSha256"] == new["outputSha256"] and old["native"]["tokenSha256"] == new["native"]["tokenSha256"]
                    if not equal:
                        raise AssertionError("Fresh workers produced different deterministic output tokens")
                    comparisons.append({"stage":old["stage"],"outputTokensExact":equal,
                        "prefillTpsRatio":new["native"]["promptTokensPerSecond"]/old["native"]["promptTokensPerSecond"],
                        "decodeTpsRatio":new["native"]["generationTokensPerSecond"]/old["native"]["generationTokensPerSecond"],
                        "firstOutputSecondsRatio":new["ttftSeconds"]/old["ttftSeconds"]})
                report["comparisons"] = comparisons
                report["fullModelMeasured"] = True
            report.update({"minimumWholeHostFreePercent":safety.minimum_free,
                           "peakOwnedGroupPhysicalFootprintBytes":safety.peak_footprint})
    except Exception as error:
        report["error"] = {"type":type(error).__name__,"message":str(error)}
        raise
    finally:
        safety.stop.set()
        if safety.worker.is_alive():
            safety.worker.join(timeout=8)
        args.result.parent.mkdir(parents=True,exist_ok=True)
        args.result.write_text(json.dumps(report,indent=2)+"\n")
        print(json.dumps({"result":str(args.result),"fullModelMeasured":report.get("fullModelMeasured",False),
                          "comparisons":report.get("comparisons"),"blocked":report.get("blocked"),"error":report.get("error")}),flush=True)


if __name__ == "__main__":
    main()
