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
const ssdEnd = index.indexOf("</details>", ssdStart);
assert.ok(primaryStart >= 0 && ssdStart > primaryStart && ssdEnd > ssdStart);
assert.doesNotMatch(index.slice(primaryStart, ssdStart), /data-backend="llamacpp"/);
const ssdMarkup = index.slice(ssdStart, ssdEnd);
assert.match(ssdMarkup, /<strong>Huge models on SSD<\/strong><small>Model-specific routes<\/small>/);
assert.match(ssdMarkup, /data-backend="llamacpp"[^>]*hidden disabled/);
assert.match(ssdMarkup, /<strong>llama\.cpp · SSD PLE<\/strong><small>Pinned Flash-Next · 8K<\/small>/);
assert.match(index, /id="llamacppControls"[^]*Qualified Qwen3\.8 Flash-Next route[^]*fixed 8K contract[^]*not a generic SSD-streaming mode/);
assert.match(styles, /\.ssd-runtime-choices \.ssd-ple-choice\{grid-column:1\/-1/);

const visibleStart = app.indexOf("function uiEngineVisible");
const visibleEnd = app.indexOf("\nfunction uiRequestVisible", visibleStart);
assert.ok(visibleStart >= 0 && visibleEnd > visibleStart);
const visibleContext = {
  state: {adapters: {engines: []}},
  uiFeatureEnabled: () => false,
};
vm.createContext(visibleContext);
vm.runInContext(app.slice(visibleStart, visibleEnd), visibleContext);
assert.equal(visibleContext.uiEngineVisible("llamacpp"), false);
visibleContext.state.adapters.engines.push({id: "llamacpp", label: "llama.cpp · SSD PLE"});
assert.equal(visibleContext.uiEngineVisible("llamacpp"), true);

const modelStart = app.indexOf("function llamaCppPleCapabilityQualified");
const modelEnd = app.indexOf("\nfunction clientName", modelStart);
assert.ok(modelStart >= 0 && modelEnd > modelStart);
const modelContext = {state: {models: []}};
vm.createContext(modelContext);
vm.runInContext(app.slice(modelStart, modelEnd), modelContext);
assert.equal(modelContext.controllerRouteQualificationBackend({
  routeQualification: false, request: {backend: "llamacpp"},
}), "");
assert.equal(modelContext.controllerRouteQualificationBackend({
  routeQualification: true, request: {backend: "llamacpp"},
}), "llamacpp");
modelContext.state.models = [{
  ready: true,
  backends: {llamacpp: {runnable: true, contextWindows: [4096]}},
}];
assert.equal(modelContext.llamaCppPleModel(), null);
modelContext.state.models[0].backends.llamacpp.contextWindows = [4096, 8192];
assert.equal(modelContext.llamaCppPleModel(), null);
const qualified = {
  id: "qwen-flash-next-ple",
  ready: true,
  backends: {llamacpp: {
    runnable: true,
    llamacppPle: true,
    currentProcessVerified: true,
    verificationGeneration: 7,
    atomicPle: {
      ready: true, currentProcessVerified: true, verificationGeneration: 7,
    },
    receiptFingerprint: "a".repeat(64),
    runtimeVersion: "llama.cpp b10740 qualification runtime",
    contextWindows: [8192],
    memoryCeilingBytes: 44 * 1024 ** 3,
  }},
};
modelContext.state.models.push(qualified);
assert.equal(modelContext.llamaCppPleModel().id, qualified.id);
qualified.backends.llamacpp.receiptFingerprint = "not-a-receipt";
assert.equal(modelContext.llamaCppPleModel(), null);
qualified.backends.llamacpp.receiptFingerprint = "a".repeat(64);
qualified.backends.llamacpp.runnable = false;
assert.equal(modelContext.llamaCppPleModel(), null);

qualified.backends.llamacpp.runnable = true;
qualified.backends.llamacpp.currentProcessVerified = false;
assert.equal(modelContext.llamaCppPleModel(), null);
qualified.backends.llamacpp.currentProcessVerified = true;
const checking = {
  id: "qwen-flash-next-checking",
  ready: false,
  verificationState: "checking",
  backends: {llamacpp: {
    runnable: false, verificationState: "checking", currentProcessVerified: false,
  }},
};
modelContext.state.models.push(checking);
assert.equal(modelContext.llamaCppPleCheckingModel().id, checking.id);
modelContext.state.backend = "llamacpp";
modelContext.selectedModel = () => qualified;
assert.equal(modelContext.selectedRouteQualificationBackend(), "llamacpp");
assert.equal(modelContext.performanceReceiptQualificationBackend({
  routeQualification: true, qualifiedBackend: "llamacpp",
}), "llamacpp");

const reasoningStart = app.indexOf("function reasoningChoices");
const reasoningEnd = app.indexOf("\nfunction adapterDescriptor", reasoningStart);
const reasoningSelect = {value: "medium"};
const reasoningContext = {
  state: {backend: "llamacpp", client: "pi"},
  selectedModel: () => ({backends: {llamacpp: {agentReasoning: ["auto"]}}}),
  $: id => { assert.equal(id, "reasoningSelect"); return reasoningSelect; },
};
vm.createContext(reasoningContext);
vm.runInContext(app.slice(reasoningStart, reasoningEnd), reasoningContext);
assert.equal(reasoningContext.normalizeReasoningSelection(), "auto");
assert.equal(reasoningSelect.value, "auto");
assert.match(app, /function refreshLaunchability\(\) \{[^]*normalizeReasoningSelection\(\);/);
assert.match(app, /exact route · fixed[^]*route-level receipt can be reused by compatible work surfaces/);
assert.match(app, /Pinned Qwen3\.8 Flash-Next route ready · fixed 8K context/);
assert.match(app, /No pinned verified artifact route is available/);
assert.doesNotMatch(app, /Qualified pinned (?:Qwen3\.8 )?Flash-Next route/);

const exactContractStart = app.indexOf("function llamaQualificationContractExact");
const exactContractEnd = app.indexOf("\nfunction firstQualificationMetric", exactContractStart);
assert.ok(exactContractStart >= 0 && exactContractEnd > exactContractStart);
vm.runInContext(app.slice(exactContractStart, exactContractEnd), modelContext);
const exactPlan = {
  routeQualification: true,
  model: {id: qualified.id},
  request: {
    backend: "llamacpp", modelId: qualified.id, context: 8192,
    output: 4096, reasoning: "auto",
  },
  routeSpec: {
    id: "atomicchat-llamacpp-ssd-ple-8k-v1",
    version: 1,
    scope: "route",
    clientAgnostic: true,
    backend: "llamacpp",
    suite: "route-qualification-8k",
    context: 8192,
    reasoningPolicy: "runtime-fixed-on",
    toolProbeRequired: true,
    memoryProofRequired: true,
    memoryCeilingBytes: 44 * 1024 ** 3,
  },
  qualificationContract: {
    id: "atomicchat-llamacpp-ssd-ple-8k-v1",
    version: 1,
    scope: "route",
    clientAgnostic: true,
    backend: "llamacpp",
    exactContext: 8192,
    configuredOutputLimit: 4096,
    measuredRequestMaxTokens: 512,
    scenarioContract: ["cold", "warmPrefix", "toolIngest", "steadyTurn"],
    sampleMaxTokens: 512,
    answerReserveTokens: 128,
    thinkingBudgetTokens: 384,
    minimumDecodeTokensPerSecond: 15,
    minimumCompletionTokens: 128,
    reasoningBoundaryContractId: "atomicchat-budget-zero-boundary-v1",
    reasoningBudgetMessageSha256: "04dbe3b430e5be6b5f2f130343e8a0b55872538b1ca53c775e7d8afd9b4acb5a",
    reasoningPolicy: "runtime-fixed-on",
    toolProbeRequired: true,
    memoryProofRequired: true,
    memoryCeilingBytes: 44 * 1024 ** 3,
    receiptFingerprint: "a".repeat(64),
    runtimeVersion: "llama.cpp b10740 qualification runtime",
  },
  reasoningContract: {
    policy: "runtime-fixed-reasoning-on",
    runtimeControlled: true, reasoningEnabled: true, measured: "auto",
  },
};
assert.equal(modelContext.llamaQualificationContractExact(exactPlan), true);
const clonePlan = () => JSON.parse(JSON.stringify(exactPlan));
const contractMutations = [
  ["missing qualification contract", plan => { delete plan.qualificationContract; }],
  ["wrong contract id", plan => { plan.qualificationContract.id = "wrong"; }],
  ["wrong contract version", plan => { plan.qualificationContract.version = 2; }],
  ["wrong contract backend", plan => { plan.qualificationContract.backend = "omlx"; }],
  ["wrong contract scope", plan => { plan.qualificationContract.scope = "engine"; }],
  ["client-specific contract", plan => { plan.qualificationContract.clientAgnostic = false; }],
  ["wrong exact context", plan => { plan.qualificationContract.exactContext = 4096; }],
  ["missing configured output limit", plan => { delete plan.qualificationContract.configuredOutputLimit; }],
  ["wrong configured output limit", plan => { plan.qualificationContract.configuredOutputLimit = 2048; }],
  ["wrong visible output limit", plan => { plan.request.output = 2048; }],
  ["missing measured request maximum", plan => { delete plan.qualificationContract.measuredRequestMaxTokens; }],
  ["wrong measured request maximum", plan => { plan.qualificationContract.measuredRequestMaxTokens = 511; }],
  ["reordered scenarios", plan => { plan.qualificationContract.scenarioContract.reverse(); }],
  ["wrong sample limit", plan => { plan.qualificationContract.sampleMaxTokens = 511; }],
  ["wrong answer reserve", plan => { plan.qualificationContract.answerReserveTokens = 127; }],
  ["missing thinking budget", plan => { delete plan.qualificationContract.thinkingBudgetTokens; }],
  ["wrong thinking budget", plan => { plan.qualificationContract.thinkingBudgetTokens = 383; }],
  ["missing minimum TPS", plan => { delete plan.qualificationContract.minimumDecodeTokensPerSecond; }],
  ["wrong minimum TPS", plan => { plan.qualificationContract.minimumDecodeTokensPerSecond = 14.9; }],
  ["wrong minimum completion", plan => { plan.qualificationContract.minimumCompletionTokens = 127; }],
  ["missing reasoning boundary contract", plan => { delete plan.qualificationContract.reasoningBoundaryContractId; }],
  ["wrong reasoning boundary contract", plan => { plan.qualificationContract.reasoningBoundaryContractId = "wrong"; }],
  ["missing reasoning budget message hash", plan => { delete plan.qualificationContract.reasoningBudgetMessageSha256; }],
  ["short reasoning budget message hash", plan => { plan.qualificationContract.reasoningBudgetMessageSha256 = "b".repeat(63); }],
  ["non-hex reasoning budget message hash", plan => { plan.qualificationContract.reasoningBudgetMessageSha256 = "g".repeat(64); }],
  ["different valid reasoning budget message hash", plan => { plan.qualificationContract.reasoningBudgetMessageSha256 = "b".repeat(64); }],
  ["wrong reasoning policy", plan => { plan.qualificationContract.reasoningPolicy = "selectable"; }],
  ["missing tool probe", plan => { plan.qualificationContract.toolProbeRequired = false; }],
  ["missing memory proof", plan => { plan.qualificationContract.memoryProofRequired = false; }],
  ["wrong contract memory ceiling", plan => { plan.qualificationContract.memoryCeilingBytes += 1; }],
  ["missing receipt", plan => { delete plan.qualificationContract.receiptFingerprint; }],
  ["wrong receipt", plan => { plan.qualificationContract.receiptFingerprint = "b".repeat(64); }],
  ["missing runtime", plan => { delete plan.qualificationContract.runtimeVersion; }],
  ["wrong runtime", plan => { plan.qualificationContract.runtimeVersion = "different runtime"; }],
  ["missing route spec", plan => { delete plan.routeSpec; }],
  ["wrong route id", plan => { plan.routeSpec.id = "wrong"; }],
  ["wrong route version", plan => { plan.routeSpec.version = 2; }],
  ["wrong route scope", plan => { plan.routeSpec.scope = "engine"; }],
  ["client-specific route", plan => { plan.routeSpec.clientAgnostic = false; }],
  ["wrong route backend", plan => { plan.routeSpec.backend = "omlx"; }],
  ["wrong route suite", plan => { plan.routeSpec.suite = "agentic"; }],
  ["wrong route context", plan => { plan.routeSpec.context = 4096; }],
  ["wrong request model", plan => { plan.request.modelId = "another-model"; }],
  ["wrong route reasoning policy", plan => { plan.routeSpec.reasoningPolicy = "selectable"; }],
  ["missing route tool probe", plan => { plan.routeSpec.toolProbeRequired = false; }],
  ["missing route memory proof", plan => { plan.routeSpec.memoryProofRequired = false; }],
  ["wrong route memory ceiling", plan => { plan.routeSpec.memoryCeilingBytes += 1; }],
  ["wrong visible context", plan => { plan.request.context = 4096; }],
  ["wrong visible reasoning", plan => { plan.request.reasoning = "medium"; }],
  ["wrong reasoning contract", plan => { plan.reasoningContract.policy = "selectable"; }],
];
for (const [label, mutate] of contractMutations) {
  const candidate = clonePlan();
  mutate(candidate);
  assert.equal(modelContext.llamaQualificationContractExact(candidate), false, label);
}
qualified.backends.llamacpp.memoryCeilingBytes += 1;
assert.equal(modelContext.llamaQualificationContractExact(exactPlan), false, "capability ceiling");
qualified.backends.llamacpp.memoryCeilingBytes = 44 * 1024 ** 3;
qualified.backends.llamacpp.runtimeVersion = "different runtime";
assert.equal(modelContext.llamaQualificationContractExact(exactPlan), false, "capability runtime");
qualified.backends.llamacpp.runtimeVersion = "llama.cpp b10740 qualification runtime";

assert.match(app, /if \(\["whallm", "llamacpp"\]\.includes\(state\.backend\)\) \{\s*return \{acceleration:"off", depth:1, kv:"off"\};/);
assert.match(app, /const verifyingPle = button\.dataset\.backend === "llamacpp"[^]*const qualifiedPle = button\.dataset\.backend !== "llamacpp"[^]*Boolean\(llamaCppPleModel\(\)\) \|\| verifyingPle/);
assert.match(app, /filter\(backend => backend !== "llamacpp"\)/);
assert.match(app, /if \(backend === "llamacpp"\) return \[\{\s*id:"ar", label:"SSD PLE", available:llamaCppPleCapabilityQualified\(cap\)/);
assert.match(app, /if \(backend === "llamacpp" && !llamaCppPleQualified\(model\)\) continue/);
assert.match(app, /state\.backend !== "llamacpp" \|\| llamaCppPleQualified\(model\)/);
assert.match(app, /capability\?\.llamacppPle === true[^]*capability\?\.atomicPle\?\.ready === true[^]*capability\?\.currentProcessVerified === true[^]*capability\?\.atomicPle\?\.currentProcessVerified === true[^]*\^\[0-9a-f\]\{64\}\$\/\.test\(capability\.receiptFingerprint\)/);
assert.match(app, /modelVerificationTimer: null, modelVerificationLoading: false/);
assert.match(app, /model\.verificationState === "checking"[^]*setTimeout\(\(\) => \{ void loadModels\(false\); \}, 700\)/);
assert.match(app, /Verifying the pinned artifact in this controller[^]*verificationProgress\?\.completed/);
assert.match(app, /const modelReady = Boolean\([^]*state\.backend !== "llamacpp" \|\| llamaCppPleQualified\(model\)/);
assert.match(app, /llamacpp:"llama\.cpp · SSD PLE"/);
assert.match(app, /LLAMACPP_PLE_QUALIFICATION_CONTEXT = 8192/);
assert.match(app, /LLAMACPP_PLE_QUALIFICATION_MEMORY_LIMIT_BYTES = 44 \* 1024 \*\* 3/);
assert.match(app, /LLAMACPP_PLE_QUALIFICATION_SUITE = "route-qualification-8k"/);
assert.match(app, /qualificationBackend === "llamacpp"[^]*return LLAMACPP_PLE_QUALIFICATION_SUITE/);
assert.match(app, /suite === LLAMACPP_PLE_QUALIFICATION_SUITE \? "agentic" : suite/);
assert.match(app, /fixed 8K under the exact 44 GiB ceiling/);
assert.match(app, /Reasoning is runtime-controlled and stays on/);
assert.match(app, /Last completed turn · \$\{liveTps\.toFixed\(1\)\} tok\/s/);
assert.match(app, /Peak memory · \$\{esc\(peak\)\}/);
assert.match(app, /Reasoning \+ final answer/);
assert.match(app, /Correctness check/);
assert.match(app, /Jinja tool check/);
assert.match(app, /Clean unload/);
assert.match(app, /Slowest turn · \$\{esc\(minimumTps\)\} · target ≥\$\{LLAMACPP_PLE_QUALIFICATION_MINIMUM_TPS\}/);
assert.match(app, /Apply qualified route/);
assert.match(app, /memoryBlocker\.estimate\?\.requiredMetalWiredLimitBytes[^]*memoryBlocker\.estimate\?\.memoryCeilingBytes/);
assert.match(app, /measurementAction = "Recheck limit"/);
assert.match(app, /memoryBlocker\.decision === "runtime-conflict"/);
assert.match(app, /measurementAction = "Recheck Whallm"/);
assert.match(app, /Unload or close Whallm, then recheck · the launcher will not stop it/);
assert.match(app, /sudo \/usr\/sbin\/sysctl -w iogpu\.wired_limit_mb=45056/);
assert.match(app, /\["recheck-limit", "recheck-conflict"\]\.includes\(\$\("calibrationStartButton"\)\.dataset\.action\)/);
assert.match(app, /route\.scope === "route"/);
assert.match(app, /route\.clientAgnostic === true/);
assert.match(app, /routeEvidenceQualified = !routeQualification \|\| shownEvidence\.qualified === true/);
assert.match(app, /qualificationContractExact \? "Locked" : "Contract mismatch"/);
assert.match(app, /plan\.ready && qualificationContractExact/);
assert.match(app, /completedCalibrationEvidenceBinding\(result, decision\)/);

console.log("Dedicated, controller-qualified llama.cpp SSD PLE UI passed.");
