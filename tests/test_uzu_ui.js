"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const index = fs.readFileSync(path.join(root, "index.html"), "utf8");
const styles = fs.readFileSync(path.join(root, "styles.css"), "utf8");

const primaryStart = index.indexOf('id="backendChoices"');
const ssdStart = index.indexOf('id="ssdRuntimeDisclosure"');
assert.ok(primaryStart >= 0 && ssdStart > primaryStart);
const primaryMarkup = index.slice(primaryStart, ssdStart);
assert.match(primaryMarkup, /data-backend="uzu"[^>]*aria-pressed="false"/);
assert.match(primaryMarkup, /choice-icon uzu[^]*<strong>Uzu · Mirai<\/strong><small>DFlash \+ Weaver · Chat first<\/small>/);

const controlsStart = index.indexOf('id="uzuControls"');
const controlsEnd = index.indexOf('id="freetokenControls"', controlsStart);
assert.ok(controlsStart >= 0 && controlsEnd > controlsStart);
const controlsMarkup = index.slice(controlsStart, controlsEnd);
assert.match(controlsMarkup, /id="uzuAccelerationLabel">DFlash \+ Weaver<\/strong>/);
assert.match(controlsMarkup, /managed by Uzu/);
assert.match(controlsMarkup, /id="uzuRouteSummary"[^>]*role="note"[^>]*aria-label="Uzu route limits"/);
assert.match(controlsMarkup, /<strong>BF16 KV<\/strong><small>Runtime fixed · no Q8\/Q4<\/small>/);
assert.match(controlsMarkup, /<strong>Chat only<\/strong><small>Initial qualification<\/small>/);
assert.doesNotMatch(controlsMarkup, /<(?:select|input)\b/);

assert.match(index, /id="modelLibraryEngineFilter"[^]*<option value="uzu">Uzu · Mirai<\/option>/);
assert.match(index, /id="clientChoices"[^>]*aria-describedby="compatibilityLine"/);
assert.match(app, /\["omlx", "lmstudio", "mtplx", "uzu", "freetoken"/);
assert.match(app, /\["uzu", "whallm", "llamacpp"\]\.includes\(state\.backend\)[^]*acceleration:"off", depth:1, kv:"off"/);
assert.match(app, /\["uzu", "freetoken", "swiftlm", "mference", "whallm", "llamacpp"\]\.includes\(state\.backend\)/);
assert.match(app, /mirai:"Uzu · Mirai"/);
assert.match(app, /route-qualification-uzu-16k/);
assert.match(app, /route-qualification-uzu-32k/);
assert.match(app, /Chat only for initial qualification/);
assert.match(app, /BF16 KV · runtime fixed/);
assert.match(app, /Slowest turn/);
assert.match(app, /Correctness/);
assert.match(app, /Clean unload/);
assert.match(app, /calibrationCoolingSelect\"\)\.value = plan\.calibrationCooling \|\| \"default\"/);
assert.match(app, /calibrationCoolingSelect\"\)\.disabled = controlsLocked \|\| coolingLocked/);
assert.match(styles, /\.choice-icon\.uzu,\.runtime-icon\.uzu,\.runtime-icon\.mirai\{/);
assert.match(styles, /\.choice\{[^}]*min-height:46px/);
assert.match(styles, /\.choice>span:not\(\.choice-icon\)\{min-width:0\}/);
assert.match(styles, /\.uzu-route-summary\{[^}]*grid-template-columns:repeat\(2,minmax\(0,1fr\)\)/);
assert.match(styles, /:root\[data-detail="focused"\] #backendChoices\{grid-template-columns:repeat\(4,minmax\(0,1fr\)\)\}/);
assert.match(styles, /@media\(max-width:720px\)\{:root\[data-detail="focused"\] #backendChoices\{grid-template-columns:1fr\}\}/);

const descriptorStart = app.indexOf("function adapterDescriptor");
const nameEnd = app.indexOf("\nfunction routeCapabilityPresentation", descriptorStart);
assert.ok(descriptorStart >= 0 && nameEnd > descriptorStart);
const nameContext = {state: {adapters: {engines: []}}};
vm.createContext(nameContext);
vm.runInContext(app.slice(descriptorStart, nameEnd), nameContext);
assert.equal(nameContext.backendName("uzu"), "Uzu · Mirai");
assert.equal(nameContext.backendMark("uzu"), "U");
assert.equal(nameContext.backendBinaryKey("uzu"), "mirai");
nameContext.state.adapters.engines.push({
  id: "uzu", label: "Inventory Uzu", binaryKey: "inventory-mirai",
});
assert.equal(nameContext.backendName("uzu"), "Inventory Uzu");
assert.equal(nameContext.backendBinaryKey("uzu"), "inventory-mirai");

const candidatesStart = app.indexOf("function benchmarkCandidates");
const candidatesEnd = app.indexOf("\nfunction engineShootoutRoutes", candidatesStart);
assert.ok(candidatesStart >= 0 && candidatesEnd > candidatesStart);
const candidateContext = {
  state: {backend: "uzu"},
  llamaCppPleCapabilityQualified: () => false,
};
vm.createContext(candidateContext);
vm.runInContext(app.slice(candidatesStart, candidatesEnd), candidateContext);
assert.deepEqual(
  JSON.parse(JSON.stringify(candidateContext.benchmarkCandidates({
    runnable: true, runtimeManagedAcceleration: "DFlash + Weaver",
  }, "uzu"))),
  [{id: "ar", label: "DFlash + Weaver", available: true}],
);

const contextLabelStart = app.indexOf("function compactNativeContext");
const contextLabelEnd = app.indexOf("\nconst rangeOutputIds", contextLabelStart);
assert.ok(contextLabelStart >= 0 && contextLabelEnd > contextLabelStart);
const contextLabelContext = {
  formatNumber: value => Number(value).toLocaleString("en-US"),
  UZU_QUALIFICATION_CONTEXTS: [16_384, 32_768],
};
vm.createContext(contextLabelContext);
vm.runInContext(app.slice(contextLabelStart, contextLabelEnd), contextLabelContext);
assert.equal(
  contextLabelContext.modelContextLabel({
    modelType: "qwen3.6-uzu", nativeContext: 262_144,
  }),
  "262K native · qualify 16K or 32K",
);
assert.equal(
  contextLabelContext.modelContextLabel({
    nativeContext: 262_144,
    engines: [{id: "uzu", artifactCompatible: true}],
  }),
  "262K native · qualify 16K or 32K",
  "the Model Library recognizes Uzu from its engine report too",
);

const selectedBackendStart = app.indexOf("function selectedRouteQualificationBackend");
const selectedBackendEnd = app.indexOf("\nfunction performanceReceiptQualificationBackend", selectedBackendStart);
assert.ok(selectedBackendStart >= 0 && selectedBackendEnd > selectedBackendStart);
const selectedBackendModel = {
  ready: true,
  uzuNative: true,
  backends: {uzu: {runnable: true, runtimeManagedAcceleration: "DFlash + Weaver"}},
};
const selectedBackendContext = {
  state: {backend: "uzu"},
  selectedModel: () => selectedBackendModel,
  llamaCppPleQualified: () => false,
};
vm.createContext(selectedBackendContext);
vm.runInContext(app.slice(selectedBackendStart, selectedBackendEnd), selectedBackendContext);
assert.equal(selectedBackendContext.selectedRouteQualificationBackend(), "uzu");
selectedBackendModel.backends.uzu.runnable = false;
assert.equal(selectedBackendContext.selectedRouteQualificationBackend(), "");
selectedBackendModel.backends.uzu.runnable = true;

let qualificationContextTokens = 16_384;
const receiptSuiteStart = app.indexOf("function performanceReceiptSuite()");
const receiptSuiteEnd = app.indexOf("\nfunction performanceReceiptSuiteOrder", receiptSuiteStart);
assert.ok(receiptSuiteStart >= 0 && receiptSuiteEnd > receiptSuiteStart);
const receiptSuiteContext = {
  state: {client: "chat"},
  selectedRouteQualificationBackend: () => "uzu",
  $: () => ({value: String(qualificationContextTokens)}),
  uzuQualificationSuite: value => ({
    16_384: "route-qualification-uzu-16k",
    32_768: "route-qualification-uzu-32k",
  })[Number(value)] || "",
  isUzuQualificationSuite: suite => [
    "route-qualification-uzu-16k", "route-qualification-uzu-32k",
  ].includes(suite),
  LLAMACPP_PLE_QUALIFICATION_SUITE: "route-qualification-8k",
  CalibrationDecision: {receiptSuite: () => "standard"},
};
vm.createContext(receiptSuiteContext);
vm.runInContext(app.slice(receiptSuiteStart, receiptSuiteEnd), receiptSuiteContext);
assert.equal(receiptSuiteContext.performanceReceiptSuite(), "route-qualification-uzu-16k");
assert.equal(
  receiptSuiteContext.calibrationSuiteControlValue("route-qualification-uzu-16k"),
  "agentic",
);
qualificationContextTokens = 32_768;
assert.equal(receiptSuiteContext.performanceReceiptSuite(), "route-qualification-uzu-32k");
assert.equal(
  receiptSuiteContext.calibrationSuiteControlValue("route-qualification-uzu-32k"),
  "agentic",
);
qualificationContextTokens = 24_576;
assert.throws(
  () => receiptSuiteContext.performanceReceiptSuite(),
  /exact 16K or 32K context tier/,
);

const qualificationProfileStart = app.indexOf("function calibrationQualificationProfile");
const qualificationProfileEnd = app.indexOf("\nfunction llamaQualificationContractExact", qualificationProfileStart);
assert.ok(qualificationProfileStart >= 0 && qualificationProfileEnd > qualificationProfileStart);
const qualificationProfileContext = {
  state: {calibrationPlan: null},
  controllerRouteQualificationBackend: () => "uzu",
};
vm.createContext(qualificationProfileContext);
vm.runInContext(app.slice(qualificationProfileStart, qualificationProfileEnd), qualificationProfileContext);
const qualificationProfile = qualificationProfileContext.calibrationQualificationProfile({});
assert.equal(qualificationProfile.uzu, true);
assert.equal(qualificationProfile.routeLabel, "Uzu DFlash + Weaver");
assert.match(qualificationProfile.subtitle, /exact context on built-in Chat/);
assert.match(qualificationProfile.startMessage, /fixed DFlash \+ Weaver route/);
assert.doesNotMatch(qualificationProfile.startMessage, /oMLX|AR/);

const fingerprint = "a".repeat(64);
const runtimeSha = "b".repeat(64);
const sandboxSha = "c".repeat(64);
const systemReserveBytes = 5 * 1024 ** 3;
const uzuModel = {
  id: "uzu-qualified",
  ready: true,
  uzuNative: true,
  backends: {uzu: {
    runnable: true,
    runtimeManagedAcceleration: "DFlash + Weaver",
    contextWindows: [16_384, 32_768],
    contextMaximum: 32_768,
    benchmarkModelFingerprint: fingerprint,
    runtimeVersion: "Uzu 0.5.23",
    runtimeIdentity: {
      ready: true,
      networkSandbox: true,
      memorySafetyBlocked: false,
      rawListenerAuthenticated: true,
      rawListenerIsolated: false,
      listenerIsolationBlocked: false,
      binary: {sha256: runtimeSha},
    },
    qualificationSystemContract: {
      osReserveBytes: systemReserveBytes,
      sandboxProfileSha256: sandboxSha,
      rawListenerProtected: true,
    },
    modelRegistryId: "alibaba:qwen3.6:27b:mirai:mirai-m:4",
    modelCommit: "d".repeat(40),
    modelToolchainVersion: "0.15.0",
  }},
};
const uzuQualificationSuite = context => ({
  16_384: "route-qualification-uzu-16k",
  32_768: "route-qualification-uzu-32k",
})[Number(context)] || "";
const uzuQualificationContractId = context => ({
  16_384: "qwen36-uzu-dflash-weaver-16k-v1",
  32_768: "qwen36-uzu-dflash-weaver-32k-v1",
})[Number(context)] || "";
const scenarios = ["cold", "warmPrefix", "toolIngest", "steadyTurn"];
const contractContext = {
  state: {calibrationPlan: null},
  controllerRouteQualificationBackend: plan => (
    plan.routeQualification === true && plan.request?.backend === "uzu" ? "uzu" : ""
  ),
  selectedModel: () => uzuModel,
  uzuQualificationSuite,
  uzuQualificationContractId,
  UZU_QUALIFICATION_CONTEXTS: [16_384, 32_768],
  UZU_QUALIFICATION_SCENARIOS: scenarios,
  UZU_QUALIFICATION_MEMORY_LIMIT_BYTES: 36 * 1024 ** 3,
  UZU_QUALIFICATION_OS_RESERVE_MINIMUM_BYTES: 4 * 1024 ** 3,
  UZU_QUALIFICATION_CONTRACT_VERSION: 1,
  UZU_QUALIFICATION_SAMPLE_MAX_TOKENS: 512,
  UZU_QUALIFICATION_ANSWER_RESERVE_TOKENS: 128,
  UZU_QUALIFICATION_MINIMUM_TPS: 15,
  UZU_QUALIFICATION_MINIMUM_COMPLETION_TOKENS: 128,
};
const contractStart = app.indexOf("function uzuQualificationContractExact");
const contractEnd = app.indexOf("\nfunction routeQualificationContractExact", contractStart);
assert.ok(contractStart >= 0 && contractEnd > contractStart);
vm.createContext(contractContext);
vm.runInContext(app.slice(contractStart, contractEnd), contractContext);

function exactUzuPlan(context) {
  const suite = uzuQualificationSuite(context);
  const id = uzuQualificationContractId(context);
  return {
    routeQualification: true,
    model: {id: uzuModel.id},
    request: {
      modelId: uzuModel.id,
      backend: "uzu",
      client: "chat",
      context,
      output: 1_024,
      reasoning: "auto",
      options: {acceleration: "off", depth: 1, kv: "off"},
    },
    suite: {id: suite},
    qualificationContract: {
      id,
      version: 1,
      scope: "route",
      clientAgnostic: false,
      client: "chat",
      backend: "uzu",
      exactContext: context,
      configuredOutputLimit: 1_024,
      measuredRequestMaxTokens: 512,
      scenarioContract: [...scenarios],
      sampleMaxTokens: 512,
      answerReserveTokens: 128,
      thinkingBudgetTokens: null,
      minimumDecodeTokensPerSecond: 15,
      minimumCompletionTokens: 128,
      reasoningPolicy: "runtime-default-on",
      toolProbeRequired: false,
      memoryProofRequired: true,
      memoryCeilingBytes: 36 * 1024 ** 3,
      fixedAcceleration: "DFlash + Weaver",
      kvStateDataType: "BF16",
      prefixCache: true,
      osReservePolicy: "max-4gib-or-10-percent-total-v1",
      osReserveMinimumBytes: 4 * 1024 ** 3,
      osReserveBytes: systemReserveBytes,
      receiptFingerprint: fingerprint,
      modelFingerprint: fingerprint,
      modelRegistryId: uzuModel.backends.uzu.modelRegistryId,
      modelCommit: uzuModel.backends.uzu.modelCommit,
      modelToolchainVersion: uzuModel.backends.uzu.modelToolchainVersion,
      runtimeBinarySha256: runtimeSha,
      sandboxProfileSha256: sandboxSha,
      rawListenerProtected: true,
      runtimeVersion: uzuModel.backends.uzu.runtimeVersion,
    },
    routeSpec: {
      id,
      version: 1,
      scope: "route",
      clientAgnostic: false,
      client: "chat",
      backend: "uzu",
      mode: "ar",
      modeLabel: "Fixed DFlash + Weaver",
      suite,
      context,
      reasoningPolicy: "runtime-default-on",
      toolProbeRequired: false,
      memoryProofRequired: true,
      memoryCeilingBytes: 36 * 1024 ** 3,
    },
    reasoningContract: {
      runtimeControlled: true,
      reasoningEnabled: true,
      policy: "runtime-default-reasoning-on",
      requested: "auto",
      measured: "auto",
    },
  };
}

for (const context of [16_384, 32_768]) {
  assert.equal(
    contractContext.uzuQualificationContractExact(exactUzuPlan(context)),
    true,
    `the exact ${context / 1024}K controller contract is accepted`,
  );
}
for (const [label, mutate] of [
  ["suite", plan => { plan.suite.id = "route-qualification-uzu-32k"; }],
  ["surface", plan => { plan.request.client = "pi"; }],
  ["reasoning", plan => { plan.request.reasoning = "off"; }],
  ["visible KV", plan => { plan.request.options.kv = "q8"; }],
  ["BF16 receipt", plan => { plan.qualificationContract.kvStateDataType = "Q8"; }],
  ["system reserve", plan => { plan.qualificationContract.osReserveBytes += 1; }],
  ["sandbox receipt", plan => { plan.qualificationContract.sandboxProfileSha256 = "e".repeat(64); }],
  ["raw listener receipt", plan => { plan.qualificationContract.rawListenerProtected = false; }],
  ["fixed mode", plan => { plan.routeSpec.modeLabel = "DFlash + Weaver"; }],
]) {
  const candidate = exactUzuPlan(16_384);
  mutate(candidate);
  assert.equal(contractContext.uzuQualificationContractExact(candidate), false, label);
}
uzuModel.backends.uzu.runtimeIdentity.listenerIsolationBlocked = true;
assert.equal(
  contractContext.uzuQualificationContractExact(exactUzuPlan(16_384)),
  false,
  "an exposed raw Uzu listener rejects the otherwise exact controller contract",
);
uzuModel.backends.uzu.runtimeIdentity.listenerIsolationBlocked = false;

const applyGuardStart = app.indexOf("function calibrationRouteEvidenceApplyReady");
const applyGuardEnd = app.indexOf("\nasync function applyCalibrationResult", applyGuardStart);
assert.ok(applyGuardStart >= 0 && applyGuardEnd > applyGuardStart);
const applyGuardContext = {
  state: {calibrationPlan: null},
  calibrationQualificationProfile: () => ({uzu: true, llama: false}),
  uzuQualificationContractExact: plan => contractContext.uzuQualificationContractExact(plan),
  llamaQualificationContractExact: () => false,
};
vm.createContext(applyGuardContext);
vm.runInContext(app.slice(applyGuardStart, applyGuardEnd), applyGuardContext);
const qualifiedPlan = exactUzuPlan(16_384);
qualifiedPlan.evidence = {
  qualified: true,
  evidenceBinding: {scope: "route", suite: qualifiedPlan.suite.id, recordId: "uzu-16k"},
};
assert.equal(applyGuardContext.calibrationRouteEvidenceApplyReady(qualifiedPlan), true);
delete qualifiedPlan.evidence.evidenceBinding;
assert.equal(
  applyGuardContext.calibrationRouteEvidenceApplyReady(qualifiedPlan),
  false,
  "a completed qualification without its immutable handoff cannot be applied",
);

const resultMetricStart = app.indexOf("function firstQualificationMetric");
const resultMetricEnd = app.indexOf("\nfunction updateCalibrationHelp", resultMetricStart);
assert.ok(resultMetricStart >= 0 && resultMetricEnd > resultMetricStart);
const resultMetricContext = {
  finiteMetric: value => Number.isFinite(Number(value)) ? Number(value) : null,
  esc: value => String(value ?? ""),
  UZU_QUALIFICATION_MEMORY_LIMIT_BYTES: 36 * 1024 ** 3,
  UZU_QUALIFICATION_MINIMUM_TPS: 15,
};
vm.createContext(resultMetricContext);
vm.runInContext(app.slice(resultMetricStart, resultMetricEnd), resultMetricContext);
const resultMarkup = resultMetricContext.routeQualificationFactsMarkup({
  decodeTokensPerSecond: 25.4,
  minimumDecodeTokensPerSecond: 16.1,
  firstTokenSeconds: 0.45,
  peakMemoryBytes: 20 * 1024 ** 3,
  reasoningObserved: true,
  answerObserved: true,
  correctnessVerified: true,
  cleanUnloadVerified: true,
}, {}, "uzu");
assert.match(resultMarkup, /Generation TPS · 25\.4 tok\/s/);
assert.match(resultMarkup, /Slowest turn · 16\.1 tok\/s · target ≥15/);
assert.match(resultMarkup, /BF16 KV · runtime fixed/);
assert.match(resultMarkup, /Peak memory · 20\.0 GiB \/ 36 GiB/);
assert.match(resultMarkup, /Reasoning \+ final answer · Passed/);
assert.match(resultMarkup, /Correctness · Passed/);
assert.match(resultMarkup, /Clean unload · Passed/);
assert.doesNotMatch(resultMarkup, /\bAR\b|Q8|Q4/);

const coolingHelpStart = app.indexOf("function updateCalibrationHelp");
const coolingHelpEnd = app.indexOf("\nfunction calibrationPlanRequest", coolingHelpStart);
assert.ok(coolingHelpStart >= 0 && coolingHelpEnd > coolingHelpStart);
const coolingElements = {
  calibrationSuiteSelect: {value: "agentic"},
  calibrationPreferenceSelect: {value: "throughput"},
  calibrationCoolingSelect: {value: "max"},
  calibrationSuiteHelp: {textContent: ""},
  calibrationPreferenceHelp: {textContent: ""},
  calibrationCoolingHelp: {textContent: ""},
};
const coolingHelpContext = {
  state: {calibrationPlan: {
    routeQualification: true,
    calibrationCoolingLocked: true,
    calibrationCoolingReason: "Uzu does not expose fan control; macOS controls cooling for this fixed route.",
  }},
  $: id => coolingElements[id],
  calibrationQualificationProfile: () => ({uzu: true, llama: false}),
};
vm.createContext(coolingHelpContext);
vm.runInContext(app.slice(coolingHelpStart, coolingHelpEnd), coolingHelpContext);
coolingHelpContext.updateCalibrationHelp();
assert.match(coolingElements.calibrationCoolingHelp.textContent, /Uzu does not expose fan control/);
assert.match(coolingElements.calibrationCoolingHelp.textContent, /macOS control/);
assert.doesNotMatch(coolingElements.calibrationCoolingHelp.textContent, /Maximum fans/);
assert.match(app, /const coolingLocked = plan\?\.calibrationCoolingLocked === true;/);

const libraryModeStart = app.indexOf("function modelLibraryEngineModes");
const libraryModeEnd = app.indexOf("\nfunction visibleModelLibraryOverview", libraryModeStart);
assert.ok(libraryModeStart >= 0 && libraryModeEnd > libraryModeStart);
const libraryModeContext = {isUzuModel: () => true};
vm.createContext(libraryModeContext);
vm.runInContext(app.slice(libraryModeStart, libraryModeEnd), libraryModeContext);
assert.deepEqual(
  JSON.parse(JSON.stringify(libraryModeContext.modelLibraryEngineModes(uzuModel, {
    id: "uzu", runnable: true, modes: [{id: "ar", label: "AR", available: true}],
  }))),
  [{
    id: "dflash-weaver",
    label: "DFlash + Weaver",
    available: true,
    detail: "Fixed runtime-managed acceleration with the bundled draft and Weaver tree",
  }],
);
const libraryChecks = libraryModeContext.modelLibraryChecks({
  doctor: {checks: [{id: "acceleration", label: "No accelerator", detail: "AR only"}]},
});
assert.equal(libraryChecks[0].label, "Fixed acceleration");
assert.match(libraryChecks[0].detail, /DFlash \+ Weaver/);
assert.doesNotMatch(libraryChecks[0].detail, /AR only/);

console.log("Uzu UI checks passed");
