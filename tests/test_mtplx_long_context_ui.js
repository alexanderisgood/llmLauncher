"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");

// Exercise the actual current-engine disclosure before the unrelated engine strip.
{
  const start = app.indexOf("function renderBenchmarkSetup() {");
  const end = app.indexOf('  $("benchmarkEngineStrip").innerHTML', start);
  const fields = Object.fromEntries([
    "benchmarkSuiteSelect", "contextInput", "profileSelect", "benchmarkStartLabel",
    "benchmarkRoute", "benchmarkModes", "benchmarkSuiteHelp",
  ].map(id => [id, {value:"", textContent:"", innerHTML:""}]));
  fields.benchmarkSuiteSelect.value = "agentic";
  fields.contextInput.value = "65536";
  fields.profileSelect.value = "turbo";
  const context = {
    state:{backend:"mtplx", client:"chat"},
    $:id => fields[id],
    selectedModel:() => ({name:"verified 27B", backends:{mtplx:{}}}),
    benchmarkCandidates:() => [{available:true, label:"AR"}, {available:true, label:"MTP"}],
    engineShootoutRoutes:() => [], mtplxLongContextCapabilityExact:() => true,
    backendName:value => value, clientName:value => value, esc:value => value,
  };
  vm.createContext(context);
  vm.runInContext(app.slice(start, end) + "\n}", context);
  context.renderBenchmarkSetup();
  assert.match(fields.benchmarkStartLabel.textContent, /3 setups/);
  assert.match(fields.benchmarkModes.innerHTML, /MTP · 2.11 long-context/);
  assert.match(fields.benchmarkSuiteHelp.textContent, /18 generated requests/);
  fields.profileSelect.value = "sustained";
  context.renderBenchmarkSetup();
  assert.doesNotMatch(fields.benchmarkModes.innerHTML, /2.11 long-context/);
  assert.doesNotMatch(fields.benchmarkSuiteHelp.textContent, /near-64K/);
  fields.profileSelect.value = "turbo";
  fields.contextInput.value = "32768";
  context.renderBenchmarkSetup();
  assert.doesNotMatch(fields.benchmarkStartLabel.textContent, /3 setups/);
}

function sourceBetween(startMarker, endMarker) {
  const start = app.indexOf(startMarker);
  const end = app.indexOf(endMarker, start + startMarker.length);
  assert.ok(start >= 0, `missing production marker: ${startMarker}`);
  assert.ok(end > start, `missing production end marker: ${endMarker}`);
  return app.slice(start, end);
}

const option = value => ({value, disabled:false, hidden:false});
const controls = {
  accelerationSelect:{value:"mtp"},
  depthInput:{value:"3"},
  profileSelect:{value:"turbo"},
  mtplxOperatorRouteSelect:{
    value:"default",
    options:[option("default"), option("dense-27b-long-context-2111")],
  },
  mtplxOperatorRouteHelp:{textContent:""},
  contextInput:{value:"65536"},
  outputInput:{value:"1024"},
  reasoningSelect:{value:"auto"},
  samplingMode:{value:"model"},
  temperatureInput:{value:"1"},
  topPInput:{value:"0.95"},
  topKInput:{value:"20"},
  presencePenaltyInput:{value:"0"},
  frequencyPenaltyInput:{value:"0"},
  repetitionPenaltyInput:{value:"1"},
  seedInput:{value:""},
  mtplxKv:{value:"off", options:[option("off"), option("q8"), option("q4")]},
  omlxKv:{value:"off", options:[option("off")]},
  fanSelect:{value:"smart"},
  burstSelect:{value:"balanced"},
  dflashVerifySelect:{value:"adaptive"},
  dflashDraftQuantSelect:{value:"native"},
  anePrefillSelect:{value:"off"},
  memoryGuardSelect:{value:"balanced"},
  gpuSelect:{value:"max"},
  parallelInput:{value:"1"},
  mtpMinTokensInput:{value:"0"},
  mtpMinContinueProbabilityInput:{value:"0"},
};
const $ = id => controls[id] || null;

function exactModel() {
  const fingerprint = "a".repeat(64);
  const value = {
    id:"qwen-27b", ready:true,
    defaultSampling:{temperature:1, top_p:0.95, top_k:20},
    backends:{mtplx:{
      runnable:true, mtp:true,
      runtimeVersion:"mtplx 2.11.1 (2.11.1)",
      benchmarkModelFingerprint:fingerprint,
      longContext2111:{
        contractVersion:1,
        ready:true,
        routeId:"dense-27b-long-context-2111",
        contractId:"mtplx-2111-contract-test",
        minimumContext:65536,
        requiredProfile:"turbo",
        requiredAcceleration:"mtp",
        runtimeVersion:"2.11.1",
        reason:"Exact runtime route is ready.",
      },
    }},
  };
  value.backends.mtplx.localBenchmarks = [exactRecord(value)];
  value.backends.mtplx.localBenchmark = value.backends.mtplx.localBenchmarks[0];
  return value;
}

function exactRecord(model, overrides = {}) {
  const settings = {depth:3, mtplxOperatorRoute:"dense-27b-long-context-2111"};
  const samplingContract = {
    schemaVersion:1, controlled:true, mode:"model",
    values:{temperature:1, top_p:0.95, top_k:20},
  };
  const candidate = {
    route:"dense-27b-long-context-2111", settings:{...settings},
    selected:true, qualityMatchesAR:true, qualityMatchesDefault:true,
    resourceComparable:true, resourceCooldownStatus:"ready",
  };
  return {
    id:"mtplx-record-2111", createdAt:new Date().toISOString(),
    scope:"local", backend:"mtplx", kind:"mtplx-long-context-operator-tuning",
    suite:"mtplx-dense-27b-long-context-64k", workloadKind:"agentic",
    selectionMetric:"generation-tokens-per-second",
    baselinePassed:true, qualityPassed:true, winner:"mtp",
    runtimeVersion:model.backends.mtplx.runtimeVersion,
    modelFingerprint:model.backends.mtplx.benchmarkModelFingerprint,
    contextMin:65536, contextMax:65536, outputMin:1024, outputMax:1024,
    client:"chat", reasoning:"auto", targetKV:"off",
    samplingFingerprint:"b".repeat(64),
    samplingEvidenceVersion:1, samplingControlled:true,
    samplingContractVersion:1, samplingContract,
    samplingContractFingerprint:"c".repeat(64),
    engineSettings:{profile:"turbo", fan:"smart"},
    settings:{...settings}, modeSettings:{mtp:{...settings}},
    mtplxOperatorSweep:{
      version:5, strategy:"isolated-long-context-operator-comparison",
      complete:true, resourceComparable:true,
      suiteName:"mtplx-dense-27b-long-context-64k", requiredContext:65536,
      contractId:model.backends.mtplx.longContext2111.contractId,
      baselineRoute:"default", candidateRoute:"dense-27b-long-context-2111",
      candidateAccepted:true, selectedRoute:"dense-27b-long-context-2111",
      selectedSettings:{...settings}, candidates:[candidate],
    },
    ...overrides,
  };
}

let model = exactModel();
const optimizationStateChanges = [];
const state = {
  backend:"mtplx", client:"chat", applyingOptimal:false,
  optimalSignature:"", optimalLabel:"",
  activeEvidenceBinding:null, activeEvidenceSignature:"",
};
const context = {
  state, $, selectedModel:() => model, console,
  clearActiveEvidenceBinding:() => {
    state.activeEvidenceBinding = null;
    state.activeEvidenceSignature = "";
  },
  setOptimizationState:(...args) => optimizationStateChanges.push(args),
};
vm.createContext(context);
vm.runInContext(sourceBetween(
  "const MTPLX_OPERATOR_ROUTE_DEFAULT",
  "\nconst optimizerControls",
), context);

assert.equal(context.mtplxLongContextCapabilityExact(model), true);
assert.equal(context.mtplxLongContextRouteEligible(model, {
  backend:"mtplx", acceleration:"mtp", profile:"turbo", context:65536,
}), true);
const exactValues = {
  backend:"mtplx", acceleration:"mtp", profile:"turbo",
  context:65536, output:1024, depth:3, fan:"smart",
  client:"chat", reasoning:"auto", kv:"off",
};
assert.equal(context.mtplxLongContextRecordMatches(
  model.backends.mtplx.localBenchmark, model, exactValues,
), true);
for (const values of [
  {backend:"omlx", acceleration:"mtp", profile:"turbo", context:65536},
  {backend:"mtplx", acceleration:"off", profile:"turbo", context:65536},
  {backend:"mtplx", acceleration:"mtp", profile:"sustained", context:65536},
  {backend:"mtplx", acceleration:"mtp", profile:"turbo", context:65535},
]) assert.equal(context.mtplxLongContextRouteEligible(model, values), false);

for (const mutate of [
  route => { route.ready = "true"; },
  route => { route.contractVersion = 2; },
  route => { route.routeId = "lookalike-route"; },
  route => { route.contractId = ""; },
  route => { route.minimumContext = 32768; },
  route => { route.requiredProfile = "sustained"; },
  route => { route.requiredAcceleration = "auto"; },
  route => { route.runtimeVersion = "2.11.0"; },
]) {
  const stale = exactModel();
  mutate(stale.backends.mtplx.longContext2111);
  assert.equal(context.mtplxLongContextCapabilityExact(stale), false);
}
for (const runtimeVersion of [
  "2.11.1-beta", "2.11.1-dev1", "2.11.1+local", "2.11.2",
]) {
  const stale = exactModel();
  stale.backends.mtplx.runtimeVersion = runtimeVersion;
  assert.equal(context.mtplxLongContextCapabilityExact(stale), false);
}

const withoutEvidence = exactModel();
withoutEvidence.backends.mtplx.localBenchmark = null;
withoutEvidence.backends.mtplx.localBenchmarks = [];
model = withoutEvidence;
context.updateMtplxLongContextControl();
const measuredOption = controls.mtplxOperatorRouteSelect.options[1];
assert.equal(measuredOption.disabled, true);
assert.equal(measuredOption.hidden, true);
assert.match(controls.mtplxOperatorRouteHelp.textContent, /Run Calibration once/);

model = exactModel();

context.updateMtplxLongContextControl();
assert.equal(measuredOption.disabled, false);
assert.equal(measuredOption.hidden, false);
assert.match(controls.mtplxOperatorRouteHelp.textContent, /Measured 2\.11\.1 route ready/);

for (const [label, mutate] of [
  ["future evidence", record => { record.createdAt = new Date(Date.now() + 60_000).toISOString(); }],
  ["expired evidence", record => { record.createdAt = new Date(Date.now() - 31 * 86_400_000).toISOString(); }],
  ["non-local evidence", record => { record.scope = "artifact"; }],
  ["wrong runtime", record => { record.runtimeVersion = "mtplx 2.11.1-beta"; }],
  ["wrong client", record => { record.client = "pi"; }],
  ["wrong reasoning", record => { record.reasoning = "high"; }],
  ["wrong KV", record => { record.targetKV = "q8"; }],
  ["wrong sampling", record => { record.samplingContract.values.top_p = 0.9; }],
  ["wrong fan", record => { record.engineSettings.fan = "default"; }],
  ["candidate rejected", record => { record.mtplxOperatorSweep.candidateAccepted = false; }],
  ["default selected", record => { record.mtplxOperatorSweep.selectedRoute = "default"; }],
  ["candidate not selected", record => { record.mtplxOperatorSweep.candidates[0].selected = false; }],
]) {
  const stale = exactModel();
  const record = structuredClone(stale.backends.mtplx.localBenchmark);
  mutate(record);
  stale.backends.mtplx.localBenchmark = record;
  stale.backends.mtplx.localBenchmarks = [record];
  assert.equal(
    context.mtplxLongContextRecordMatches(record, stale, exactValues), false,
    label,
  );
}

controls.mtplxOperatorRouteSelect.value = "dense-27b-long-context-2111";
state.optimalSignature = "measured-signature";
state.optimalLabel = "MTP D3 · 2.11.1 long-context";
state.activeEvidenceBinding = {scope:"engine"};
state.activeEvidenceSignature = "active";
controls.contextInput.value = "32768";
context.updateMtplxLongContextControl();
assert.equal(controls.mtplxOperatorRouteSelect.value, "default");
assert.equal(measuredOption.disabled, true);
assert.equal(measuredOption.hidden, true);
assert.equal(state.optimalSignature, "");
assert.equal(state.optimalLabel, "");
assert.equal(state.activeEvidenceBinding, null);
assert.equal(state.activeEvidenceSignature, "");
assert.deepEqual(
  optimizationStateChanges.at(-1),
  ["custom", "Custom", "The measured 2.11.1 long-context route is no longer available for this setup."],
);
controls.mtplxOperatorRouteSelect.value = "dense-27b-long-context-2111";
state.applyingOptimal = true;
state.optimalSignature = "in-flight-signature";
state.optimalLabel = "Applying…";
context.updateMtplxLongContextControl();
assert.equal(controls.mtplxOperatorRouteSelect.value, "default");
assert.equal(state.optimalSignature, "in-flight-signature");
assert.equal(state.optimalLabel, "Applying…");
state.applyingOptimal = false;
state.optimalSignature = "";
state.optimalLabel = "";
controls.contextInput.value = "65536";

const measuredResult = {
  backend:"mtplx",
  options:{
    acceleration:"mtp", profile:"turbo", depth:3,
    fan:"smart", kv:"off",
    mtplxOperatorRoute:"dense-27b-long-context-2111",
  },
  evidenceTier:"local-benchmark",
};
assert.equal(context.mtplxOperatorRouteFromOptimization(
  measuredResult, false, model, 65536,
), "dense-27b-long-context-2111");
assert.equal(context.mtplxOperatorRouteFromOptimization(
  {...measuredResult, evidenceTier:"artifact-benchmark"}, false, model, 65536,
), "default");
assert.equal(context.mtplxOperatorRouteFromOptimization(
  {...measuredResult, options:{...measuredResult.options, mtplxOperatorRoute:undefined}},
  false, model, 65536,
), "default");

const boundResult = {
  ...measuredResult,
  evidenceTier:"cross-engine-local-benchmark",
  engineEvidenceTier:"cross-engine-local-benchmark",
  settingsEvidenceTier:"local-benchmark",
  enginePreference:"throughput",
  engineEvidenceBinding:{
    scope:"engine", suite:"agentic", preference:"throughput",
    shootoutId:"shootout-2111",
    recordIds:{omlx:"record-omlx", mtplx:"record-mtplx"},
  },
};
assert.equal(context.mtplxOperatorRouteFromOptimization(
  boundResult, true, model, 65536,
), "dense-27b-long-context-2111");
const noiseFloorResult = {
  ...boundResult,
  evidenceTier:"cross-engine-noise-floor",
  engineEvidenceTier:"cross-engine-noise-floor",
};
assert.equal(context.mtplxOperatorRouteFromOptimization(
  noiseFloorResult, true, model, 65536,
), "dense-27b-long-context-2111");
for (const tampered of [
  {...boundResult, settingsEvidenceTier:"artifact-benchmark"},
  {...noiseFloorResult, settingsEvidenceTier:undefined},
  {...boundResult, engineEvidenceTier:"incomplete-cross-engine-matrix"},
  {...boundResult, engineEvidenceBinding:{...boundResult.engineEvidenceBinding, shootoutId:""}},
  {...boundResult, engineEvidenceBinding:{...boundResult.engineEvidenceBinding, preference:"fastest"}},
  {...boundResult, engineEvidenceBinding:{...boundResult.engineEvidenceBinding, recordIds:{omlx:"record-omlx"}}},
]) assert.equal(context.mtplxOperatorRouteFromOptimization(
  tampered, true, model, 65536,
), "default");

const staleModel = exactModel();
staleModel.backends.mtplx.longContext2111.contractId = "";
assert.equal(context.mtplxOperatorRouteFromOptimization(
  measuredResult, false, staleModel, 65536,
), "default");

assert.equal(context.savedMtplxOperatorRoute({}), "default");
assert.equal(context.savedMtplxOperatorRoute({
  mtplxOperatorRoute:"dense-27b-long-context-2111",
}), "dense-27b-long-context-2111");
assert.throws(
  () => context.savedMtplxOperatorRoute({mtplxOperatorRoute:"tampered-route"}),
  /no longer supported/,
);
assert.equal(context.mtplxOperatorRouteLabel(measuredResult.options), "MTP D3 · 2.11.1 long-context");

vm.runInContext(sourceBetween(
  "function runtimeKvValue(",
  "\nfunction gatherGenerationSettings",
), context);
controls.mtplxOperatorRouteSelect.value = "dense-27b-long-context-2111";
assert.equal(context.gatherOptions().mtplxOperatorRoute, "dense-27b-long-context-2111");
state.backend = "omlx";
assert.equal(Object.hasOwn(context.gatherOptions(), "mtplxOperatorRoute"), false);
state.backend = "mtplx";

const controlStart = html.indexOf('<label class="field optimizable" data-opt-key="mtplxOperatorRoute">');
const controlEnd = html.indexOf("</label>", controlStart);
assert.ok(controlStart >= 0 && controlEnd > controlStart);
const controlMarkup = html.slice(controlStart, controlEnd);
const rowStart = html.lastIndexOf('<div class="mtplx-long-context-row">', controlStart);
assert.ok(rowStart >= 0 && rowStart < controlStart, "long-context control should use a full-width block row");
assert.match(controlMarkup, />Long-context execution</);
assert.match(controlMarkup, />Runtime default</);
assert.match(controlMarkup, />Measured 2\.11\.1 route</);
assert.match(controlMarkup, /aria-describedby="mtplxOperatorRouteHelp"/);
assert.match(controlMarkup, /id="mtplxOperatorRouteHelp" aria-live="polite"/);
assert.doesNotMatch(controlMarkup, /MTPLX_[A-Z_]+/);
assert.match(app, /mtplxOperatorRoute:\s*"mtplxOperatorRouteSelect"/);
assert.match(app, /mtplx:\s*\["acceleration",\s*"depth",\s*"profile",\s*"mtplxOperatorRoute",\s*"fan"\]/);
assert.match(app, /"mtplxOperatorRouteSelect", savedMtplxOperatorRoute\(options\)/);
assert.match(app, /mtplxOperatorRouteFromOptimization\(\s*result, engineSelection, model/);
const profileApplySource = sourceBetween(
  "function applyProfileRequest(",
  "\nasync function applySavedProfile",
);
assert.ok(
  profileApplySource.indexOf('setProfileSelect("samplingMode"')
    < profileApplySource.indexOf("updateMtplxLongContextControl()"),
  "saved sampling must be restored before the measured route is enabled",
);

console.log("MTPLX 2.11.1 long-context UI gating, evidence checks, and profile persistence passed.");
