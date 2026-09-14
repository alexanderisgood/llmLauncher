"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const app = fs.readFileSync(path.join(__dirname, "../app.js"), "utf8");
function between(start, end) {
  const from = app.indexOf(start), to = app.indexOf(end, from + start.length);
  assert.ok(from >= 0 && to > from);
  return app.slice(from, to);
}
const elements = {
  reasoningSelect:{value:"auto"}, contextInput:{value:"65536"}, outputInput:{value:"16384"},
  benchmarkResults:{innerHTML:""},
  benchmarkDialog:{open:true, close() {this.open = false;}},
};
const result = {
  id:"measured-setup", scope:"local", suite:"mtplx-dense-27b-long-context-64k",
  backend:"mtplx", modelId:"model", client:"chat", reasoning:"auto", qualityPassed:true,
  contextMin:65536, contextMax:65536, outputMax:16384,
  winner:"mtp", recommendation:"Use MTP", modes:{},
};
const state = {backend:"mtplx", client:"chat", benchmarkStatus:{phase:"completed", result}};
const calls = [], notices = [];
let applySucceeds = true;
const ctx = vm.createContext({
  state, $:id => elements[id], selectedModel:() => ({id:"model"}),
  benchmarkDisplayedStatus:() => state.benchmarkStatus,
  esc:String, benchmarkWinnerLabel:String,
  finiteMetric:value => typeof value === "number" && Number.isFinite(value) ? value : null,
  showNotice:(...args) => notices.push(args),
  applyOptimal:async (...args) => {calls.push(args); return applySucceeds;},
});
vm.runInContext(
  between("function copiedEvidenceBinding(", "function clearActiveEvidenceBinding(")
  + between("function benchmarkRouteApplyBinding(", "function renderBenchmarkStatus("), ctx,
);

(async () => {
  ctx.renderBenchmarkResults(state.benchmarkStatus);
  assert.match(elements.benchmarkResults.innerHTML, /data-apply-benchmark-route>Use measured settings/);
  const operatorStatus = {...state.benchmarkStatus, result:{...result,
    kind:"mtplx-long-context-operator-tuning", mtplxOperatorSweep:{
      arMeasurement:{medianDecodeTokensPerSecond:12,
        samples:[{decodeTokensPerSecond:11.5}, {decodeTokensPerSecond:12.5}]},
      selectedRoute:"dense-27b-long-context-2111",
      candidates:[
        {route:"default", medianGenerationTokensPerSecond:24, worstGenerationTokensPerSecond:23, qualityMatchesAR:true},
        {route:"dense-27b-long-context-2111", medianGenerationTokensPerSecond:31, worstGenerationTokensPerSecond:30, qualityMatchesAR:true},
      ],
    },
  }};
  assert.ok(ctx.benchmarkRouteApplyBinding(operatorStatus));
  ctx.renderBenchmarkResults(operatorStatus);
  assert.equal((elements.benchmarkResults.innerHTML.match(/<article/g) || []).length, 3);
  assert.match(elements.benchmarkResults.innerHTML, /Default MTP/);
  assert.match(elements.benchmarkResults.innerHTML, /Long-context MTP/);
  assert.equal((elements.benchmarkResults.innerHTML.match(/Slowest turn/g) || []).length, 3);
  assert.match(elements.benchmarkResults.innerHTML, /11\.5 tok\/s/);
  assert.match(elements.benchmarkResults.innerHTML, /data-apply-benchmark-route/);
  const tied = {...operatorStatus.result, mtplxOperatorSweep:{
    ...operatorStatus.result.mtplxOperatorSweep, selectedRoute:"default", candidates:[{
      route:"dense-27b-long-context-2111", qualityMatchesAR:true,
      resourceComparable:true, medianSpeedupVsDefault:1.0137,
    }],
  }};
  assert.match(ctx.benchmarkResultRecommendation(tied), /only 1\.4% faster/);
  assert.match(ctx.benchmarkResultRecommendation(tied), /practical tie/);
  ctx.renderBenchmarkResults({...operatorStatus, result:{...operatorStatus.result,
    winner:"ar", mtplxOperatorSweep:{...operatorStatus.result.mtplxOperatorSweep,
      selectedRoute:"default", candidates:[{route:"default", qualityMatchesAR:false,
        medianGenerationTokensPerSecond:24, worstGenerationTokensPerSecond:23}]}}});
  assert.match(elements.benchmarkResults.innerHTML, /output did not exactly match/);
  assert.doesNotMatch(elements.benchmarkResults.innerHTML, /Use MTP/);
  for (const change of [{phase:"running"}, {phase:"failed"}, {phase:"cancelled"}]) {
    const status = {...state.benchmarkStatus, ...change};
    assert.equal(ctx.benchmarkRouteApplyBinding(status), null);
    ctx.renderBenchmarkResults(status);
    assert.doesNotMatch(elements.benchmarkResults.innerHTML, /data-apply-benchmark-route/);
  }
  for (const change of [
    {id:""}, {qualityPassed:false}, {modelId:"different"}, {backend:"omlx"},
    {client:"pi"}, {reasoning:"high"}, {contextMin:32768}, {contextMax:131072},
    {outputMax:1024}, {scope:"cloud"}, {kind:"route-qualification"},
  ]) assert.equal(ctx.benchmarkRouteApplyBinding({...state.benchmarkStatus, result:{...result, ...change}}), null);

  assert.equal(await ctx.applyBenchmarkRouteResult(), true);
  assert.deepEqual(JSON.parse(JSON.stringify(calls.pop())), ["current", "throughput", false,
    {scope:"route", suite:result.suite, preference:"throughput", recordId:result.id}]);
  assert.equal(elements.benchmarkDialog.open, false);
  elements.benchmarkDialog.open = true;
  applySucceeds = false;
  assert.equal(await ctx.applyBenchmarkRouteResult(), false);
  assert.equal(elements.benchmarkDialog.open, true, "Keep errors visible; never reopen calibration automatically");
  calls.length = 0;
  state.benchmarkStatus.phase = "failed";
  assert.equal(await ctx.applyBenchmarkRouteResult(), false);
  assert.equal(calls.length, 0);
  assert.equal(notices.length, 1);
  console.log("Current-engine results apply their exact saved binding without starting another test.");
})().catch(error => {console.error(error); process.exitCode = 1;});
