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
assert.match(app, /function controllerRouteQualificationBackend\(plan = \{\}\)/);
assert.match(app, /const routeQualification = Boolean\(qualificationBackend\)/);
assert.match(app, /Boolean\(selectedRouteQualificationBackend\(\)\)/);
assert.match(app, /LLAMACPP_PLE_QUALIFICATION_SUITE = "route-qualification-8k"/);
assert.match(app, /memoryGuard:\s*"memoryGuardSelect"/);
assert.match(app, /memoryGuardSelect"\)\.addEventListener\("change", \(\) => \{\s*\/\/[^]*?if \(!state\.applyingOptimal\) \{\s*cancelOptimization\("Memory mode changed; reapply to refresh the benchmark match\."\);/);
assert.match(app, /"Prepare safe test"/);
assert.match(app, /dataset\.action = canPrepare[^]*\? "prepare" : canRecheckSystemSetting \? "recheck-limit" : canRecheckRuntimeConflict \? "recheck-conflict" : "measure"/);
assert.match(app, /memoryBlocker\.decision === "runtime-conflict"/);
assert.match(app, /"Recheck Whallm"/);
assert.match(app, /async function prepareQwenRouteQualification\(\)/);
assert.match(app, /preparation\.doesNotChangeMacOS !== true/);
assert.match(app, /macOS was not changed/);
assert.match(app, /dataset\.action === "prepare"/);
assert.match(app, /function calibrationRouteEvidenceApplyReady/);
assert.match(app, /if \(qualificationBackend === "llamacpp"\) \{\s*return LLAMACPP_PLE_QUALIFICATION_SUITE/);
assert.match(app, /CalibrationDecision\.receiptSuite\(\s*state\.client,\s*qualificationBackend === "omlx"/);
assert.match(app, /actionId:routeQualification \? "measure-qualification" : "rerun-lab"/);
assert.match(app, /actionId:routeQualification\s*\? "measure-qualification"/);
assert.match(app, /calibrationBenchmarkActive\(\)\s*\|\| state\.calibrationLoading/);

const applyGuardStart = app.indexOf("function calibrationRouteEvidenceApplyReady");
const applyGuardEnd = app.indexOf("\nasync function applyCalibrationResult", applyGuardStart);
assert.ok(applyGuardStart >= 0 && applyGuardEnd > applyGuardStart);
const applyGuardContext = {
  state: {calibrationPlan: null},
  calibrationQualificationProfile: plan => ({llama: plan.request?.backend === "llamacpp"}),
  llamaQualificationContractExact: plan => plan.exactLlamaContract === true,
};
vm.createContext(applyGuardContext);
vm.runInContext(app.slice(applyGuardStart, applyGuardEnd), applyGuardContext);
const routeBinding = {scope: "route", recordId: "qualified-route"};
assert.equal(applyGuardContext.calibrationRouteEvidenceApplyReady({
  routeQualification: true,
  request: {backend: "omlx"},
  evidence: {qualified: true, evidenceBinding: routeBinding},
}), true, "legacy oMLX apply-existing remains allowed");
assert.equal(applyGuardContext.calibrationRouteEvidenceApplyReady({
  routeQualification: true,
  request: {backend: "llamacpp"},
  exactLlamaContract: false,
  evidence: {qualified: true, evidenceBinding: routeBinding},
}), false, "llama.cpp still requires the exact contract");
assert.equal(applyGuardContext.calibrationRouteEvidenceApplyReady({
  routeQualification: true,
  request: {backend: "omlx"},
  evidence: {qualified: false, evidenceBinding: routeBinding},
}), false, "all routes still require qualified evidence");
assert.equal(applyGuardContext.calibrationRouteEvidenceApplyReady({
  routeQualification: true,
  request: {backend: "omlx"},
  evidence: {qualified: true},
}), false, "all routes still require an immutable binding");
assert.match(app, /state\.calibrationLoading = true;\s*state\.calibrationPlan = null;\s*\$\("calibrationStatus"\)/);
assert.match(app, /state\.calibrationStarting = true/);
assert.match(app, /\|\| state\.calibrationStarting/);
assert.match(index, /id="calibrationDialogSubtitle"/);
assert.match(index, /id="calibrationPreferenceLabel"/);
assert.match(index, /class="field amber optimizable"[^>]*><span>48 GB memory mode/);
assert.match(app, /"Measuring…"\s*:\s*`Last completed turn · \$\{liveTps\.toFixed\(1\)\} tok\/s`/);
assert.match(app, /"Apply qualified route"/);
assert.match(app, /function completedCalibrationEvidenceBinding/);
assert.match(app, /\.\.\.\(evidenceBinding \? \{evidenceBinding\} : \{\}\)/);

const qualificationHelperStart = app.indexOf("const LLAMACPP_PLE_QUALIFICATION_CONTEXT");
const qualificationHelperEnd = app.indexOf("\nfunction clientName", qualificationHelperStart);
assert.ok(qualificationHelperStart >= 0 && qualificationHelperEnd > qualificationHelperStart);
const qualificationContext = {
  state: {backend: "llamacpp"},
  selectedModel: () => ({id: "atomic-ple"}),
  llamaCppPleQualified: () => true,
};
vm.createContext(qualificationContext);
vm.runInContext(app.slice(qualificationHelperStart, qualificationHelperEnd), qualificationContext);
assert.equal(qualificationContext.controllerRouteQualificationBackend({
  routeQualification: false,
  request: {backend: "llamacpp"},
}), "");
assert.equal(qualificationContext.controllerRouteQualificationBackend({
  routeQualification: true,
  request: {backend: "llamacpp"},
}), "llamacpp");
assert.equal(qualificationContext.controllerRouteQualificationBackend({
  routeQualification: true,
  engines: [{backend: "llamacpp", eligible: true}],
}), "llamacpp");
assert.equal(qualificationContext.selectedRouteQualificationBackend(), "llamacpp");
assert.equal(qualificationContext.performanceReceiptQualificationBackend({
  kind: "route-qualification", qualifiedBackend: "llamacpp",
}), "llamacpp");
assert.equal(qualificationContext.performanceReceiptQualificationBackend({
  state: "trusted-route", scope: "route", backend: "omlx",
}), "");
assert.equal(qualificationContext.performanceReceiptQualificationBackend({
  kind: "route-qualification",
}), "");
assert.equal(qualificationContext.performanceReceiptQualificationBackend({
  kind: "route-qualification", qualifiedBackend: "llamacpp", backend: "omlx",
}), "");

const suiteHelperStart = app.indexOf("function performanceReceiptSuite()");
const suiteHelperEnd = app.indexOf("\nfunction performanceReceiptRequest()", suiteHelperStart);
assert.ok(suiteHelperStart >= 0 && suiteHelperEnd > suiteHelperStart);
qualificationContext.CalibrationDecision = {
  receiptSuite: (client, routeQualification) => routeQualification
    ? "agentic" : client === "chat" ? "standard" : "agentic",
};
qualificationContext.state.client = "chat";
vm.runInContext(app.slice(suiteHelperStart, suiteHelperEnd), qualificationContext);
assert.equal(qualificationContext.performanceReceiptSuite(), "route-qualification-8k");
assert.equal(
  qualificationContext.calibrationSuiteControlValue("route-qualification-8k"),
  "agentic",
);
qualificationContext.state.backend = "omlx";
qualificationContext.selectedModel = () => ({qwen4Ple: {supported: true}});
assert.equal(qualificationContext.performanceReceiptSuite(), "agentic");
qualificationContext.state.backend = "lmstudio";
qualificationContext.selectedModel = () => ({ready: true});
assert.equal(qualificationContext.performanceReceiptSuite(), "standard");

const resultMetricStart = app.indexOf("function firstQualificationMetric");
const resultMetricEnd = app.indexOf("\nfunction updateCalibrationHelp", resultMetricStart);
assert.ok(resultMetricStart >= 0 && resultMetricEnd > resultMetricStart);
const resultMetricContext = {
  finiteMetric: value => Number.isFinite(Number(value)) ? Number(value) : null,
  formatBytes: value => `${(Number(value) / (1024 ** 3)).toFixed(1)} GiB`,
  esc: value => String(value ?? ""),
  LLAMACPP_PLE_QUALIFICATION_MEMORY_LIMIT_BYTES: 44 * 1024 ** 3,
  LLAMACPP_PLE_QUALIFICATION_MINIMUM_TPS: 15,
};
vm.createContext(resultMetricContext);
vm.runInContext(app.slice(resultMetricStart, resultMetricEnd), resultMetricContext);
const qualificationMarkup = resultMetricContext.routeQualificationFactsMarkup({
  decodeTokensPerSecond: 18.75,
  minimumDecodeTokensPerSecond: 15.25,
  firstTokenSeconds: 2.125,
  peakMemoryBytes: 41 * 1024 ** 3,
  reasoningTurns: 4,
  answerTurns: 4,
  sampleCount: 4,
  correctnessVerified: true,
  reasoningBoundaryVerified: true,
  toolContractVerified: true,
  cleanUnloadVerified: true,
}, {}, "llamacpp");
assert.match(qualificationMarkup, /Generation TPS · 18\.8 tok\/s/);
assert.match(qualificationMarkup, /Slowest turn · 15\.3 tok\/s · target ≥15/);
assert.match(qualificationMarkup, /TTFT · 2\.13s/);
assert.match(qualificationMarkup, /Peak memory · 41\.0 GiB \/ 44 GiB/);
assert.match(qualificationMarkup, /Reasoning \+ final answer · Passed/);
assert.match(qualificationMarkup, /Clean forced handoff · Passed/);
assert.match(qualificationMarkup, /Correctness check · Passed/);
assert.match(qualificationMarkup, /Jinja tool check · Passed/);
assert.match(qualificationMarkup, /Clean unload · Passed/);

const bindingHelperStart = app.indexOf("function completedCalibrationEvidenceBinding");
const bindingHelperEnd = app.indexOf("\nfunction promoteCompletedCalibrationResult", bindingHelperStart);
assert.ok(bindingHelperStart >= 0 && bindingHelperEnd > bindingHelperStart);
vm.runInContext(app.slice(bindingHelperStart, bindingHelperEnd), resultMetricContext);
const immutableBinding = {scope: "route", suite: "route-qualification-8k", preference: "throughput", recordId: "route-record"};
const copiedBinding = resultMetricContext.completedCalibrationEvidenceBinding({
  evidenceBinding: immutableBinding,
}, {});
assert.deepEqual(JSON.parse(JSON.stringify(copiedBinding)), immutableBinding);
assert.notEqual(copiedBinding, immutableBinding);

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
  LLAMACPP_PLE_QUALIFICATION_SUITE: "route-qualification-8k",
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
context.selectedRouteQualificationBackend = () => "omlx";
context.performanceReceiptQualificationBackend = receipt => (
  receipt?.kind === "route-qualification" ? String(receipt.qualifiedBackend || receipt.backend || "") : ""
);
vm.runInContext(app.slice(receiptViewStart, receiptViewEnd), context);
const alternateSuiteView = context.performanceReceiptView({
  state: "trusted-engine", fresh: true, suite: "agentic",
  suiteLabel: "Agentic Route Lab", backendLabel: "oMLX",
  modeLabel: "DFlash 2", workloadDisplay: "Coding agent · four turns",
});
assert.match(alternateSuiteView.detail, /Agentic Route Lab/);
assert.doesNotMatch(alternateSuiteView.detail, /Standard/);
const ordinaryOmlxRouteView = context.performanceReceiptView({
  state: "trusted-route", scope: "route", fresh: true, suite: "agentic",
  backend: "omlx", backendLabel: "oMLX", modeLabel: "AR",
  workloadDisplay: "Coding agent · four turns",
});
assert.match(ordinaryOmlxRouteView.title, /Measured route/);
assert.doesNotMatch(ordinaryOmlxRouteView.title, /Qualified/);
assert.equal(ordinaryOmlxRouteView.actionId, "apply-route");
const qualifiedLlamaView = context.performanceReceiptView({
  state: "trusted-route", scope: "route", fresh: true, suite: "agentic",
  kind: "route-qualification", routeQualification: true,
  qualifiedBackend: "llamacpp",
  backend: "llamacpp", backendLabel: "llama.cpp · SSD PLE",
  modeLabel: "SSD PLE · exact 8K", workloadDisplay: "Four bounded turns",
});
assert.match(qualifiedLlamaView.title, /Qualified route/);
assert.doesNotMatch(qualifiedLlamaView.title, /Best|winner/i);
assert.equal(qualifiedLlamaView.actionId, "apply-route");
context.selectedRouteQualificationBackend = () => "llamacpp";
const incompleteLlamaView = context.performanceReceiptView({
  state: "incomplete", suite: "agentic",
  eligibleBackends: [{backend: "omlx"}, {backend: "mtplx"}, {backend: "llamacpp"}],
});
assert.match(incompleteLlamaView.title, /route qualification/i);
assert.doesNotMatch(incompleteLlamaView.title, /engine comparison/i);
assert.equal(incompleteLlamaView.actionId, "measure-qualification");

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
context.selectedRouteQualificationBackend = () => "";
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

  requestedSuites.length = 0;
  context.state.performanceReceipt = null;
  context.state.performanceReceiptKey = "";
  context.selectedRouteQualificationBackend = () => "llamacpp";
  const persistedBinding = {
    scope: "route", suite: "route-qualification-8k",
    preference: "throughput", recordId: "persisted-llama-route",
  };
  context.api = async (_path, options) => {
    const request = JSON.parse(options.body);
    requestedSuites.push(request.suite);
    return {history: {receipt: {
      state: "trusted-route", fresh: true,
      suite: "route-qualification-8k",
      suiteLabel: "SSD PLE Route Qualification",
      backend: "llamacpp", evidenceBinding: persistedBinding,
    }}};
  };
  await context.loadPerformanceReceipt(false, {
    key: "llamacpp-route-qualification-reload",
    request: {
      backend: "llamacpp", client: "chat",
      suite: "route-qualification-8k",
    },
  });
  assert.deepEqual(requestedSuites, ["route-qualification-8k"]);
  assert.equal(context.state.performanceReceipt.state, "trusted-route");
  assert.equal(context.state.performanceReceipt.suite, "route-qualification-8k");
  assert.deepEqual(
    JSON.parse(JSON.stringify(context.state.performanceReceipt.evidenceBinding)),
    persistedBinding,
  );

  for (const client of ["chat", "pi", "opencode"]) {
    requestedSuites.length = 0;
    context.state.performanceReceipt = null;
    context.state.performanceReceiptKey = "";
    await context.loadPerformanceReceipt(false, {
      key: `llamacpp-route-${client}`,
      request: {backend: "llamacpp", client, suite: "route-qualification-8k"},
    });
    assert.deepEqual(requestedSuites, ["route-qualification-8k"], `${client} exact suite`);
    assert.deepEqual(
      JSON.parse(JSON.stringify(context.state.performanceReceipt.evidenceBinding)),
      persistedBinding,
      `${client} immutable route binding`,
    );
  }

  requestedSuites.length = 0;
  context.state.performanceReceipt = null;
  context.state.performanceReceiptKey = "";
  context.api = async (_path, options) => {
    const request = JSON.parse(options.body);
    requestedSuites.push(request.suite);
    return {history: {receipt: {
      state: "incomplete", suite: request.suite,
      reason: "sampling-contract-mismatch",
    }}};
  };
  await context.loadPerformanceReceipt(false, {
    key: "llamacpp-custom-sampling",
    request: {
      backend: "llamacpp", client: "chat", suite: "route-qualification-8k",
      temperature: 0.7,
    },
  });
  assert.deepEqual(requestedSuites, ["route-qualification-8k"]);
  assert.equal(context.state.performanceReceipt.state, "incomplete");
  assert.equal(context.state.performanceReceipt.reason, "sampling-contract-mismatch");

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

  for (const client of ["chat", "pi", "opencode"]) {
    context.state.client = client;
    context.state.performanceReceipt = {evidenceBinding: persistedBinding};
    context.$ = () => ({disabled: false, dataset: {action: "apply-route"}});
    await context.activatePerformanceReceipt();
    const call = applyCalls.at(-1);
    assert.deepEqual(Array.from(call.slice(0, 3)), ["current", "throughput", false], `${client} route apply`);
    assert.deepEqual(JSON.parse(JSON.stringify(call[3])), persistedBinding, `${client} apply binding`);
  }
}

testReceiptFallback().then(() => {
  console.log("Qwen route qualification and exact-suite receipt fallback UI semantics passed.");
}).catch(error => {
  console.error(error);
  process.exitCode = 1;
});
