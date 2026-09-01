"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const index = fs.readFileSync(path.join(root, "index.html"), "utf8");

assert.match(app, /plan\.routeQualification\) request\.scope = "qualification"/);
assert.match(app, /"Route Qualification"/);
assert.match(app, /"Qualify route"/);
assert.match(app, /"Route qualification result"/);
assert.match(app, /local-route-qualification/);
assert.match(app, /Authoritative usage, generation TPS, time to first output/);
assert.match(app, /actionId:"measure-qualification"/);
assert.match(app, /action === "measure-qualification"\) return openCalibrationAssistant/);
assert.match(app, /const qwenPleQualification = state\.backend === "omlx"/);
assert.match(app, /memoryGuard:\s*"memoryGuardSelect"/);
assert.match(app, /memoryGuardSelect"\)\.addEventListener\("change", \(\) => \{\s*\/\/[^]*?if \(!state\.applyingOptimal\) \{\s*cancelOptimization\("Memory mode changed; reapply to refresh the benchmark match\."\);/);
assert.match(app, /"Prepare safe test"/);
assert.match(app, /dataset\.action = canPrepare \? "prepare" : "measure"/);
assert.match(app, /async function prepareQwenRouteQualification\(\)/);
assert.match(app, /preparation\.doesNotChangeMacOS !== true/);
assert.match(app, /macOS was not changed/);
assert.match(app, /dataset\.action === "prepare"/);
assert.match(app, /CalibrationDecision\.receiptSuite\(\s*state\.client,\s*state\.backend === "omlx" && selectedModel\(\)\?\.qwen4Ple\?\.supported === true/);
assert.match(app, /actionId:qwenPleQualification \? "measure-qualification" : "rerun-lab"/);
assert.match(app, /actionId:qwenPleQualification\s*\? "measure-qualification"/);
assert.match(app, /calibrationBenchmarkActive\(\)\s*\|\| state\.calibrationLoading/);
assert.match(app, /state\.calibrationLoading = true;\s*state\.calibrationPlan = null;\s*\$\("calibrationStatus"\)/);
assert.match(app, /state\.calibrationStarting = true/);
assert.match(app, /\|\| state\.calibrationStarting/);
assert.match(index, /id="calibrationDialogSubtitle"/);
assert.match(index, /id="calibrationPreferenceLabel"/);
assert.match(index, /class="field amber optimizable"[^>]*><span>48 GB memory mode/);

const routePresentationStart = app.indexOf("function routeCapabilityPresentation");
const routePresentationEnd = app.indexOf("\nfunction benchmarkCandidates", routePresentationStart);
assert.ok(routePresentationStart >= 0 && routePresentationEnd > routePresentationStart);
const routeContext = {};
vm.createContext(routeContext);
vm.runInContext(app.slice(routePresentationStart, routePresentationEnd), routeContext);
const scanOnlyFlashRoute = routeContext.routeCapabilityPresentation({
  runnable: true,
  hostSupport: {state: "supported", detail: "Supported by the installed runtime."},
  performanceEvidence: {
    tier: "upstream-measured", automaticEligible: false,
    detail: "Measured elsewhere, not against this exact request.",
  },
}, {backend: "omlx", modelName: "Qwen3.8 Flash-Next", modelReady: true});
assert.equal(scanOnlyFlashRoute.available, true);
assert.equal(scanOnlyFlashRoute.attention, false);
assert.equal(scanOnlyFlashRoute.label, "Supported");
assert.doesNotMatch(scanOnlyFlashRoute.label, /qualification|upstream/i);
assert.match(scanOnlyFlashRoute.detail, /Supported by the installed runtime/);

const alternativeStart = app.indexOf("function calibrationAlternativeMarkup");
const alternativeEnd = app.indexOf("\nfunction renderCalibrationPlan", alternativeStart);
assert.ok(alternativeStart >= 0 && alternativeEnd > alternativeStart);
const context = {
  backendName: () => "oMLX",
  esc: value => String(value ?? ""),
};
vm.createContext(context);
vm.runInContext(app.slice(alternativeStart, alternativeEnd), context);
const baseAlternative = {
  differentModel: true,
  intelligenceContractChanged: true,
  requiresExplicitSelection: true,
  modelId: "qwen38-27b-dflash",
  modelName: "Qwen3.8-27B-DFlash2",
  backend: "omlx",
  hostSupport: {state: "supported", label: "Supported on this host"},
  capacity: {launchable: true},
  modes: ["DFlash 2"],
};
const verifiedMarkup = context.calibrationAlternativeMarkup({
  modelAlternatives: [{
    ...baseAlternative,
    performanceEvidence: {tier: "verified-this-mac", label: "Verified on this Mac"},
  }],
}, false);
assert.match(verifiedMarkup, /matching DFlash result is verified on this Mac/);
assert.doesNotMatch(verifiedMarkup, /It is not verified here/);
const upstreamMarkup = context.calibrationAlternativeMarkup({
  modelAlternatives: [{
    ...baseAlternative,
    performanceEvidence: {tier: "upstream-measured", label: "Upstream measured"},
  }],
}, false);
assert.match(upstreamMarkup, /It is not verified here or selected automatically/);

const parityStart = app.indexOf("function calibrationParityRejectionNote");
const parityEnd = app.indexOf("\nfunction calibrationRoutePreview", parityStart);
assert.ok(parityStart >= 0 && parityEnd > parityStart);
vm.runInContext(app.slice(parityStart, parityEnd), context);
const parityNote = context.calibrationParityRejectionNote({
  backend: "omlx",
  tuningSweep: {candidates: [{
    qualityMatchesAR: false,
    medianSpeedupVsAR: 1.42,
    medianEndToEndTokensPerSecond: 987.6,
  }]},
});
assert.match(parityNote, /faster raw DFlash 2 candidate was excluded/);
assert.match(parityNote, /failing greedy output parity with AR/);
assert.match(parityNote, /TPS is not trusted or used here/);
assert.doesNotMatch(parityNote, /987|tok\/s/);
assert.equal(context.calibrationParityRejectionNote({
  backend: "omlx",
  tuningSweep: {candidates: [{
    qualityMatchesAR: false,
    medianSpeedupVsAR: 0.98,
  }]},
}), "");
assert.match(app, /const parityRejectionNote = calibrationParityRejectionNote\(engine\)/);

const receiptHelpersStart = app.indexOf("function performanceReceiptSuiteOrder");
const receiptHelpersEnd = app.indexOf("\nfunction performanceReceiptRequest", receiptHelpersStart);
assert.ok(receiptHelpersStart >= 0 && receiptHelpersEnd > receiptHelpersStart);
vm.runInContext(app.slice(receiptHelpersStart, receiptHelpersEnd), context);
assert.deepEqual(
  Array.from(context.performanceReceiptSuiteOrder({client: "chat", suite: "standard"})),
  ["standard", "agentic", "thorough", "quick"],
);
assert.deepEqual(
  Array.from(context.performanceReceiptSuiteOrder({client: "pi", suite: "agentic"})),
  ["agentic", "standard", "thorough", "quick"],
);
assert.deepEqual(
  Array.from(context.performanceReceiptSuiteOrder({client: "chat", suite: "agentic"}, true)),
  ["agentic"],
);
assert.equal(context.performanceReceiptNeedsFallback({state: "missing"}), true);
assert.equal(context.performanceReceiptNeedsFallback({state: "incomplete"}), true);
assert.equal(context.performanceReceiptNeedsFallback({state: "tie"}), false);
assert.equal(context.performanceReceiptNeedsFallback({state: "trusted-engine"}), false);
assert.equal(context.performanceReceiptSuiteLabel({suite: "agentic"}), "Agentic Route Lab");
assert.equal(context.performanceReceiptSuiteLabel({
  suite: "standard", suiteLabel: "Returned Standard Label",
}), "Returned Standard Label");

const receiptViewStart = app.indexOf("function performanceReceiptView");
const receiptViewEnd = app.indexOf("\nfunction renderPerformanceReceipt", receiptViewStart);
assert.ok(receiptViewStart >= 0 && receiptViewEnd > receiptViewStart);
context.state = {backend: "lmstudio"};
context.activeDetail = () => "focused";
context.selectedModel = () => null;
context.uiEngineVisible = () => true;
context.finiteMetric = value => Number.isFinite(Number(value)) ? Number(value) : null;
context.formatNumber = value => String(value);
context.performanceReceiptAge = () => "measured today";
context.benchmarkCandidates = () => [];
vm.runInContext(app.slice(receiptViewStart, receiptViewEnd), context);
const alternateSuiteView = context.performanceReceiptView({
  state: "trusted-engine", fresh: true, suite: "agentic",
  suiteLabel: "Agentic Route Lab", backendLabel: "oMLX",
  modeLabel: "DFlash 2", workloadDisplay: "Coding agent · four turns",
});
assert.match(alternateSuiteView.detail, /Agentic Route Lab/);
assert.doesNotMatch(alternateSuiteView.detail, /Standard/);

const receiptLoaderStart = app.indexOf("async function loadPerformanceReceipt");
const receiptLoaderEnd = app.indexOf("\nfunction schedulePerformanceReceipt", receiptLoaderStart);
assert.ok(receiptLoaderStart >= 0 && receiptLoaderEnd > receiptLoaderStart);
context.state = {
  performanceReceiptGeneration: 0,
  performanceReceiptKey: "",
  performanceReceiptLoading: false,
  performanceReceiptError: "",
  performanceReceipt: null,
};
context.renderPerformanceReceipt = () => {};
context.selectedModel = () => null;
vm.runInContext(app.slice(receiptLoaderStart, receiptLoaderEnd), context);

async function testReceiptFallback() {
  const requestedSuites = [];
  context.api = async (_path, options) => {
    const request = JSON.parse(options.body);
    requestedSuites.push(request.suite);
    return {history: {receipt: request.suite === "agentic"
      ? {state: "trusted-engine", suite: "agentic", suiteLabel: "Agentic Route Lab"}
      : {state: "missing", suite: request.suite, suiteLabel: "Standard"}}};
  };
  await context.loadPerformanceReceipt(false, {
    key: "chat-standard-contract",
    request: {backend: "lmstudio", client: "chat", suite: "standard"},
  });
  assert.deepEqual(requestedSuites, ["standard", "agentic"]);
  assert.equal(context.state.performanceReceipt.state, "trusted-engine");
  assert.equal(context.state.performanceReceipt.suite, "agentic");

  requestedSuites.length = 0;
  context.state.performanceReceipt = null;
  context.state.performanceReceiptKey = "";
  context.api = async (_path, options) => {
    const request = JSON.parse(options.body);
    requestedSuites.push(request.suite);
    return {history: {receipt: {
      state: "tie", suite: request.suite, suiteLabel: "Standard",
    }}};
  };
  await context.loadPerformanceReceipt(false, {
    key: "complete-preferred-contract",
    request: {backend: "lmstudio", client: "chat", suite: "standard"},
  });
  assert.deepEqual(requestedSuites, ["standard"]);
  assert.equal(context.state.performanceReceipt.state, "tie");
  assert.equal(context.state.performanceReceipt.suite, "standard");

  requestedSuites.length = 0;
  context.state.performanceReceipt = null;
  context.state.performanceReceiptKey = "";
  context.api = async (_path, options) => {
    const request = JSON.parse(options.body);
    requestedSuites.push(request.suite);
    return {history: {receipt: {
      state: "incomplete", suite: request.suite, suiteLabel: request.suite,
    }}};
  };
  await context.loadPerformanceReceipt(false, {
    key: "all-partial-contract",
    request: {backend: "lmstudio", client: "chat", suite: "standard"},
  });
  assert.deepEqual(requestedSuites, ["standard", "agentic", "thorough", "quick"]);
  assert.equal(context.state.performanceReceipt.state, "incomplete");
  assert.equal(context.state.performanceReceipt.suite, "standard");

  const activateStart = app.indexOf("async function activatePerformanceReceipt");
  const activateEnd = app.indexOf("\nfunction benchmarkSuiteChanged", activateStart);
  assert.ok(activateStart >= 0 && activateEnd > activateStart);
  vm.runInContext(app.slice(activateStart, activateEnd), context);
  const applyCalls = [];
  const binding = {
    scope: "engine", suite: "agentic", preference: "throughput",
    shootoutId: "saved-shootout", recordIds: {omlx: "record-omlx", mtplx: "record-mtplx"},
  };
  context.state.performanceReceipt = {evidenceBinding: binding};
  context.$ = () => ({disabled: false, dataset: {action: "apply-engine"}});
  context.applyOptimal = async (...args) => { applyCalls.push(args); return true; };
  await context.activatePerformanceReceipt();
  assert.deepEqual(Array.from(applyCalls[0].slice(0, 3)), ["engine", "throughput", false]);
  assert.deepEqual(JSON.parse(JSON.stringify(applyCalls[0][3])), binding);
}

testReceiptFallback().then(() => {
  console.log("Qwen route qualification and exact-suite receipt fallback UI semantics passed.");
}).catch(error => {
  console.error(error);
  process.exitCode = 1;
});
