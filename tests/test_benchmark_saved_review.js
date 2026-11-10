"use strict";
const benchmarkSources = require("./helpers/benchmark_sources.js");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = benchmarkSources.controllerSource;
const start = source.indexOf("function benchmarkDisplayedStatus(");
const end = source.indexOf("function performanceReceiptSuite(", start);
let request = {modelId:"model", context:65536, output:16384, suite:"agentic"};
const state = {benchmarkStatus:{phase:"idle"}, benchmarkReview:null};
const record = {id:"saved", suite:"mtplx-dense-27b-long-context-64k", winner:"mtp"};
let resolveRequest, posted, renders = 0, scrolled = 0;
const errors = [];
const ctx = vm.createContext({state,
  benchmarkHistoryRequest:() => ({...request}), benchmarkHistoryRequestKey:JSON.stringify,
  calibrationBenchmarkActive:() => ["running","queued"].includes(state.benchmarkStatus.phase),
  api:async (url, options) => {
    assert.equal(url, "/api/benchmark/history");
    posted = JSON.parse(options.body);
    return new Promise(resolve => {resolveRequest = resolve;});
  },
  renderBenchmarkStatus:() => {renders++;},
  $:() => ({scrollIntoView:() => {scrolled++;}}),
  showNotice:message => errors.push(message),
});
benchmarkSources.runInContext(source.slice(start,end), ctx);
const suiteContext = vm.createContext({
  selectedModel:() => ({}), mtplxLongContextCapabilityExact:() => true,
  MTPLX_LONG_CONTEXT_SUITE:record.suite,
});
benchmarkSources.runInContext(source.slice(source.indexOf("function performanceReceiptSuiteOrder("),
  source.indexOf("function performanceReceiptNeedsFallback(")), suiteContext);
assert.deepEqual(Array.from(suiteContext.performanceReceiptSuiteOrder({
  suite:"standard", backend:"mtplx", client:"chat", context:65536, options:{profile:"turbo"},
})), ["standard",record.suite,"agentic","thorough","quick"]);
assert.ok(!suiteContext.performanceReceiptSuiteOrder({
  suite:"standard", backend:"mtplx", client:"chat", context:32768, options:{profile:"turbo"},
}).includes(record.suite));
(async () => {
  const review = ctx.reviewBenchmarkResult(record.id, record.suite);
  assert.equal(posted.reviewRecordId, record.id);
  assert.equal(posted.suite, record.suite);
  resolveRequest({history:{reviewResult:record}});
  await review;
  assert.equal(ctx.benchmarkDisplayedStatus().result.id, record.id);
  assert.equal(ctx.benchmarkDisplayedStatus().savedReview, true);
  assert.equal(state.benchmarkStatus.phase, "idle", "Review never forges an active/completed job");
  assert.equal(renders,1); assert.equal(scrolled,1);
  assert.equal(ctx.benchmarkDisplayedStatus({phase:"idle"}).result.id, record.id, "Idle polls retain review");
  const saved = state.benchmarkReview;
  request.context = 32768;
  assert.equal(ctx.benchmarkDisplayedStatus().phase, "idle");
  assert.equal(state.benchmarkReview, null, "Changed settings invalidate review");
  request.context = 65536;
  state.benchmarkReview = saved;
  assert.equal(ctx.benchmarkDisplayedStatus({phase:"running",job:{id:"new"}}).phase,"running");
  assert.equal(state.benchmarkReview,null, "Live work always replaces history review");
  state.benchmarkReview = saved;
  ctx.benchmarkDisplayedStatus({phase:"completed",job:{id:"new"}});
  assert.equal(state.benchmarkReview,null, "New terminal jobs replace history review too");
  const stale = ctx.reviewBenchmarkResult(record.id, record.suite);
  request.context = 32768;
  resolveRequest({history:{reviewResult:record}});
  await stale;
  assert.equal(state.benchmarkReview,null, "Ignore response after visible settings change");
  assert.deepEqual(errors,[]);
  console.log("Saved benchmark review survives idle polling without replacing live job state.");
})().catch(error => {console.error(error); process.exitCode=1;});
