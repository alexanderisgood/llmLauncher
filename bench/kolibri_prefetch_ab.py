#!/usr/bin/env python3
"""Unqualified full-model original-Q6 decode scheduling experiments.

Fresh workers keep identical8192context/128output/BF16KV/12GBfixedceiling/
64-token prefill/1GiB retained-prefix budget, greedy sampling and generated
prompt. Variants change only private in-process fetch scheduling/prediction.
Actual router indices and original tensor bytes are mandatory; token hashes
must match. This experiment never enables a launcher setting or changes the
qualified No-router-lookahead provenance. Shared BenchLock/physical guards
and64MiB/two-future read bounds protect the host. Stops owned groups only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import statistics

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import kolibri_runtime
from bench.harness import BenchLock
from bench import kolibri_model_ab as core
from bench.kolibri_agents_live import PhysicalSafety

CONTEXT = 8192
OPTIONS = {"acceleration":"off","depth":1,"kv":"off","memoryGB":12,
           "memoryMode":"fixed","prefillSize":64,"promptCacheGB":1}
EXTRA_RAW_RESERVE = 64*1024**2
BASE_SHIM = core.SHIM


def shim(variant):
    source = BASE_SHIM.replace('os.environ["STREAMLX_PREFILL_CACHE"] = cached',
        'os.environ["STREAMLX_PREFILL_CACHE"] = cached\n'
        + 'os.environ["STREAMLX_PREFETCH"] = '+repr("1" if variant in {"prefetch","bias-prefetch"} else "0")+'\n'
        + 'from bench.kolibri_prefetch_variant import install as install_variant\n'
        + '_bench_prefetch_budget = install_variant('+repr(variant)+')')
    source = source.replace('generate = srv.stream_generate',r'''original_counters = counters
def counters():
    result = original_counters()
    pools = list((state["pools"] or {}).values())
    for field in ("pf_calls","pf_launched","pf_used","pf_agree_hit","pf_agree_tot"):
        result[field] = sum(getattr(pool,field) for pool in pools)
    return result
generate = srv.stream_generate''')
    source = source.replace('with open(metrics_path,"a") as handle:',
        'if _bench_prefetch_budget is not None:\n'
        + '                record["prefetchBudget"] = _bench_prefetch_budget.snapshot()\n'
        + '            with open(metrics_path,"a") as handle:')
    compile(source,"isolated-prefetch-shim","exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model",type=Path,required=True)
    parser.add_argument("--python",required=True)
    parser.add_argument("--result",type=Path,required=True)
    parser.add_argument("--idle-omlx-port",type=int)
    parser.add_argument("--variants",nargs="+",default=["qualified","no-overlap","prefetch","bias-prefetch"],
                        choices=["qualified","no-overlap","prefetch","bias-prefetch"])
    args = parser.parse_args()
    if "qualified" not in args.variants:
        parser.error("Include qualified baselines in the controlled order")
    info,runtime = kolibri_runtime.inspect_model(args.model),kolibri_runtime.inspect_runtime(args.python)
    if not info or not runtime:
        raise RuntimeError("Requires a fresh complete Kolibri Q6 checkpoint and qualified base runtime")
    model = {"id":"kolibri-prefetch-experiment","name":"Kolibri-1 Q6","path":info["path"],"size":info["weightBytes"],
             "format":"mlx","kolibri":info,"backends":{"kolibri":kolibri_runtime.capability(info,runtime)}}
    safety = PhysicalSafety()
    report = {"kind":"unqualified-native-fetch-scheduling-experiment","productionPromoted":False,
              "measuredAt":datetime.now(timezone.utc).isoformat(),"baseRuntime":runtime,"modelIdentity":info["identity"],
              "contract":{"context":CONTEXT,"output":128,"reasoning":"off","options":OPTIONS,
                          "sampling":{"temperature":0,"top_p":1,"top_k":0,"min_p":0,"seed":42}},
              "prefetchBounds":{"maxOutstandingIncludingRetained":2,"maxRawSpanBytes":EXTRA_RAW_RESERVE},
              "sourceSha256":{"variantModule":hashlib.sha256((ROOT / "bench/kolibri_prefetch_variant.py").read_bytes()).hexdigest()},
              "promptSha256":hashlib.sha256(core.generated_prompt().encode()).hexdigest(),"arms":[]}
    original_guard = core.memory_guard
    core.CONTEXT = CONTEXT; core.OUTPUT = 128; core.OPTIONS.update(OPTIONS)
    def guard(info):
        value = original_guard(info,context=CONTEXT,options=OPTIONS)
        total = value["resource"]["totalMemoryBytes"]
        import darwin_memory
        physical = darwin_memory.physical_reclaimable_state(total)
        value["physical"] = physical
        value["physicalReclaimableBytes"] = physical.get("reclaimableBytes")
        value["physicalRequiredHeadroomBytes"] += EXTRA_RAW_RESERVE
        value["ready"] = bool(value["memoryPlan"]["ready"] and physical.get("physicalMemoryAvailable") is True
                              and physical["reclaimableBytes"] >= value["physicalRequiredHeadroomBytes"])
        value["basis"] = "Native host_statistics64 physical reclaimable capacity +protectedmacOSreserve +64MiBboundedrawprefetch"
        return value
    core.memory_guard = guard
    try:
        with BenchLock("Kolibri unqualified bounded fetch-scheduling variants",wait_seconds=60), tempfile.TemporaryDirectory(prefix="kolibri-prefetch-ab-") as directory:
            root = Path(directory)
            core.allow_verified_idle(safety,args.idle_omlx_port); safety.worker.start()
            for arm_index,variant in enumerate(args.variants):
                folder = root / f"{arm_index:02d}-{variant}"; folder.mkdir()
                core.SHIM = shim(variant)
                print(f"[experiment] {variant}; originalQ6/alltruerouterexperts; boundedprocess/rawbuffers",flush=True)
                load_before = list(os.getloadavg())
                thermal_before = core.launcher.apple_process_resource_state()
                arm = core.run_arm(folder,model,runtime,True,safety)
                arm.update({"variant":variant,"productionQualified":variant == "qualified",
                            "shimSha256":hashlib.sha256(core.SHIM.encode()).hexdigest(),
                            "loadBefore":load_before,"loadAfter":list(os.getloadavg()),
                            "thermalBefore":thermal_before,"thermalAfter":core.launcher.apple_process_resource_state()})
                report["arms"].append(arm)
                if arm.get("error"):
                    raise RuntimeError(arm["error"]["message"])
                if not arm["engineStarted"]:
                    report["blocked"] = "physical-headroom"; break
            baselines = [(i,arm) for i,arm in enumerate(report["arms"]) if arm["variant"] == "qualified" and len(arm["requests"]) == 2]
            if not baselines:
                raise RuntimeError("No completed qualified baseline for controlled comparisons")
            for arm_index,arm in enumerate(report["arms"]):
                if arm["variant"] != "qualified" and len(arm["requests"]) == 2:
                    reference_index,baseline = min(baselines,key=lambda pair:abs(pair[0]-arm_index))
                    arm["baselineReferenceIndex"] = reference_index
                    comparisons = []
                    for old,new in zip(baseline["requests"],arm["requests"]):
                        equal = old["outputSha256"] == new["outputSha256"] and old["native"]["tokenSha256"] == new["native"]["tokenSha256"]
                        if not equal:
                            raise AssertionError(f"{arm['variant']} changed deterministic true model output tokens")
                        comparisons.append({"stage":old["stage"],"exactTokens":True,
                            "generationTpsRatio":new["native"]["generationTokensPerSecond"]/old["native"]["generationTokensPerSecond"],
                            "ttftRatio":new["ttftSeconds"]/old["ttftSeconds"],
                            "nativePrefillTpsRatio":new["native"]["promptTokensPerSecond"]/old["native"]["promptTokensPerSecond"]})
                    arm["comparisons"] = comparisons
            summary = {}
            for variant in set(args.variants):
                arms = [arm for arm in report["arms"] if arm["variant"] == variant and len(arm["requests"]) == 2]
                ratios = [point["generationTpsRatio"] for arm in arms for point in arm.get("comparisons",[])]
                summary[variant] = {"workers":len(arms),"nativeGenerationTps":[point["native"]["generationTokensPerSecond"]
                                      for arm in arms for point in arm["requests"]],
                                    "medianPairedGenerationRatio":statistics.median(ratios) if ratios else None,
                                    "worstPairedGenerationRatio":min(ratios) if ratios else None}
            report["summary"] = summary
            report.update({"minimumPhysicalReclaimableBytes":safety.minimum_reclaimable,
                           "protectedMacOsReserveBytes":safety.protected_reserve,
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
        print(json.dumps({"result":str(args.result),"variants":[row["variant"] for row in report["arms"]],
                          "blocked":report.get("blocked"),"error":report.get("error")}),flush=True)


if __name__ == "__main__":
    main()
