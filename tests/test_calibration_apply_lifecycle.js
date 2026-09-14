"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const CalibrationDecision = require("../calibration_decision.js");

function sourceBetween(startMarker, endMarker) {
  const start = app.indexOf(startMarker);
  const end = app.indexOf(endMarker, start + startMarker.length);
  assert.ok(start >= 0, `missing production marker: ${startMarker}`);
  assert.ok(end > start, `missing production end marker: ${endMarker}`);
  return app.slice(start, end);
}

class FakeClassList {
  constructor() { this.values = new Set(); }
  add(...names) { names.forEach(name => this.values.add(name)); }
  remove(...names) { names.forEach(name => this.values.delete(name)); }
  contains(name) { return this.values.has(name); }
  toggle(name, force) {
    const enabled = force === undefined ? !this.values.has(name) : Boolean(force);
    if (enabled) this.values.add(name); else this.values.delete(name);
    return enabled;
  }
}

class FakeElement {
  constructor(id) {
    this.id = id;
    this.classList = new FakeClassList();
    this.dataset = {};
    this.style = {};
    this.attributes = {};
    this.options = [];
    this.value = "";
    this.textContent = "";
    this.innerHTML = "";
    this.className = "";
    this.title = "";
    this.disabled = false;
    this.checked = false;
    this.open = false;
    this.closeCount = 0;
    this.strong = {textContent:""};
    this.progressContainer = {classList:new FakeClassList()};
  }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  querySelector(selector) { return selector === "strong" ? this.strong : null; }
  closest() { return this.progressContainer; }
  close() { this.open = false; this.closeCount += 1; }
}

const elements = new Map();
const element = id => {
  if (!elements.has(id)) elements.set(id, new FakeElement(id));
  return elements.get(id);
};

const binding = {
  scope:"engine",
  suite:"agentic",
  preference:"throughput",
  shootoutId:"shootout-42",
  recordIds:{omlx:"omlx-record-42", lmstudio:"lmstudio-record-42"},
};
const returnedBinding = {
  scope:"engine",
  suite:"agentic",
  preference:"throughput",
  shootoutId:"shootout-42-returned",
  recordIds:{omlx:"omlx-record-returned", lmstudio:"lmstudio-record-returned"},
};
const routeBinding = {
  scope:"route",
  suite:"agentic",
  preference:"throughput",
  recordId:"route-record-42",
};
const returnedRouteBinding = {
  scope:"route",
  suite:"agentic",
  preference:"throughput",
  recordId:"route-record-42-returned",
};
const comparedEngines = [
  {
    backend:"omlx", label:"oMLX", mode:"dflash2",
    testedModes:["ar", "dflash2"], settingsLabel:"DFlash 2",
    routeSettingsLabel:"DFlash block 8 · dflash · q4",
    settingsSearch:{
      version:1, kind:"omlx-dflash2", label:"DFlash 2 settings",
      strategy:"bounded", selectedSetupLabel:"DFlash block 8 · dflash · q4",
      testedSetupCount:7, maximumSetupCount:12,
      testedCandidateCount:5, maximumCandidateCount:10,
      referenceSetupCount:2,
      axes:["DFlash block size", "verification mode", "draft precision"],
    },
    display:"19.7 tok/s", decodeTokensPerSecond:19.7,
  },
  {
    backend:"lmstudio", label:"LM Studio", mode:"mtp",
    testedModes:["ar", "mtp"], settingsLabel:"MTP",
    routeSettingsLabel:"MTP D3 · min 1 · cutoff 0.25",
    settingsSearch:{
      version:1, kind:"lmstudio-mtp", label:"MTP settings",
      strategy:"bounded", selectedSetupLabel:"MTP D3 · min 1 · cutoff 0.25",
      testedSetupCount:5, maximumSetupCount:11,
      testedCandidateCount:4, maximumCandidateCount:10,
      referenceSetupCount:1,
      axes:["MTP draft depth", "minimum draft tokens", "continuation cutoff"],
    },
    display:"17.1 tok/s", decodeTokensPerSecond:17.1,
  },
];
const completedProfile = {
  backend:"omlx", label:"oMLX", preference:"throughput",
  evidenceTier:"cross-engine-local-benchmark",
  trustedWinner:true, engineChanged:true,
  recommendation:"oMLX won the matching agentic comparison.",
  comparedEngines,
  evidenceBinding:JSON.parse(JSON.stringify(binding)),
};
const completedResult = {
  id:"shootout-42", kind:"engine-shootout", suite:"agentic",
  selectedPreference:"throughput", matrixWorkloadComparable:true,
  persistence:{saved:true},
  profiles:{throughput:completedProfile},
  decision:{...completedProfile, evidenceBinding:undefined},
  engines:comparedEngines,
};
const performanceReceipt = {
  state:"trusted-engine", fresh:true, backend:"omlx",
  evidenceBinding:JSON.parse(JSON.stringify(binding)),
};

const apiCalls = [];
const receiptSchedules = [];
const notices = [];
let uiAdmission = {
  known:true, actionReady:true, launchable:true,
  decision:"ready", label:"Ready", detail:"This route fits safely.",
};
const state = {
  backend:"omlx",
  client:"chat",
  runPhase:"idle",
  setupPhase:"idle",
  benchmarkPhase:"idle",
  benchmarkStatus:{phase:"idle"},
  calibrationJobId:"shootout-42",
  calibrationCompletionId:"",
  calibrationLoading:false,
  calibrationStarting:false,
  calibrationApplying:false,
  profileBusy:false,
  applyingOptimal:false,
  optimizationGeneration:0,
  optimalSignature:"",
  optimalLabel:"",
  activeEvidenceBinding:null,
  activeEvidenceSignature:"",
  performanceReceipt,
  profiles:[],
  calibrationPlan:{
    action:"measure", ready:true, routeQualification:false,
    contractId:"agentic-contract-42",
    model:{id:"model-42", name:"Qwen test model"},
    clientLabel:"Pi",
    preference:"throughput", preferenceLabel:"Highest generation TPS",
    suite:{id:"agentic", label:"Agentic Route Lab"},
    request:{
      backend:"omlx", modelId:"model-42", client:"chat",
      context:32768, output:4096, reasoning:"auto",
      options:{kv:"off"},
    },
    reasoningContract:{normalized:false},
    calibrationCooling:"default",
    calibrationCoolingLabel:"System controlled",
    eligibleEngineCount:2,
    countsAreMaximum:true,
    modelReloadCount:23,
    measuredRequestCount:92,
    routeCount:23,
    resourceCooldownMaxSecondsPerRoute:30,
    engines:comparedEngines.map(engine => ({
      backend:engine.backend, label:engine.label, eligible:true,
      measurementRouteCount:engine.backend === "omlx" ? 12 : 11,
      settingsSearch:engine.backend === "omlx" ? {
        version:1, kind:"omlx-dflash2", label:"DFlash 2 settings",
        strategy:"bounded", maximumSetupCount:12,
        maximumCandidateCount:10, referenceSetupCount:2,
        axes:["DFlash block size", "verification mode", "draft precision"],
      } : {
        version:1, kind:"lmstudio-mtp", label:"MTP settings",
        strategy:"bounded", maximumSetupCount:11,
        maximumCandidateCount:10, referenceSetupCount:1,
        axes:["MTP draft depth", "minimum draft tokens", "continuation cutoff"],
      },
      modeDetail:`${engine.label} exact route`, modes:[{label:"AR"}],
    })),
    evidence:{},
    suggestedProfileName:"Agentic winner",
  },
};

element("calibrationPreferenceSelect").value = "throughput";
element("calibrationSuiteSelect").value = "agentic";
element("calibrationCoolingSelect").value = "default";
element("calibrationStartButton").classList.add("calibration-run-action", "primary");
element("calibrationApplyButton").classList.add("secondary");
element("reasoningSelect").value = "auto";
element("reasoningSelect").options = [{value:"auto", disabled:false}];
element("fanSelect").value = "default";
element("fanSelect").options = [{value:"default", disabled:false}];
element("contextInput").value = "32768";
element("outputInput").value = "4096";
element("calibrationDialog").open = true;

const selected = {id:"model-42", ready:true};
const context = {
  state,
  CalibrationDecision,
  enginePreferenceLabels:{throughput:"highest generation TPS"},
  optimizerControls:{},
  $:element,
  selectedModel:() => selected,
  controllerRouteQualificationBackend:() => "",
  calibrationQualificationProfile:() => ({backend:"", llama:false, uzu:false}),
  currentSessionAdmission:() => uiAdmission,
  sessionAdmissionDecision:admission => admission || {
    known:false, actionReady:false, decision:"unknown",
    label:"Capacity unavailable", detail:"Refresh capacity.",
  },
  sessionAdmissionBlockerCopy:admission => admission.actionReady
    ? "" : "This setup is too large for this Mac. Reduce context or choose another runtime.",
  routeQualificationContractExact:() => true,
  uiEngineVisible:() => true,
  acquisitionIsActive:() => false,
  routeCheckIsActive:() => false,
  aneWorkIsActive:() => false,
  calibrationStateBadge:(id, label, status) => {
    element(id).textContent = label;
    element(id).dataset.status = status;
  },
  calibrationAlternativeMarkup:() => "",
  calibrationRoutePreview:() => "oMLX: AR + DFlash 2 · LM Studio: AR + MTP",
  calibrationParityRejectionNote:() => "",
  routeQualificationFactsMarkup:() => "",
  backendName:value => ({omlx:"oMLX", lmstudio:"LM Studio"})[value] || value,
  benchmarkWinnerLabel:value => ({ar:"AR", dflash2:"DFlash 2", mtp:"MTP"})[value] || value,
  finiteMetric:value => Number.isFinite(Number(value)) ? Number(value) : null,
  formatNumber:value => Number(value).toLocaleString("en-US"),
  exactContextTier:value => `${value} tokens`,
  esc:value => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;"),
  closeOptimizerMenu:() => {},
  protectedSnapshot:() => "protected-contract",
  optimizerValueSnapshot:() => ({}),
  setOptimizerInteractionLocked:() => {},
  setOptimizationState:() => {},
  refreshLaunchability:() => {},
  persistVisibleRoute:() => true,
  rememberAppliedProfile:() => {},
  gatherOptions:() => ({kv:"off"}),
  runtimeKvValue:() => "off",
  gatherGenerationSettings:() => ({sampling:"model"}),
  gatherChatSettings:() => ({showThinking:true}),
  api:async (endpoint, options = {}) => {
    apiCalls.push({endpoint, request:options.body ? JSON.parse(options.body) : null});
    if (endpoint === "/api/optimal-engine") return {optimization:{
        modelId:"model-42", backend:"omlx", options:{kv:"off"},
        changedKeys:[], appliedKeys:[],
        engineEvidenceLabel:"Measured oMLX winner",
        evidenceLabel:"Measured oMLX winner",
        engineRationale:["Matching completed evidence."],
        rationale:["Matching completed evidence."],
        engineEvidenceBinding:JSON.parse(JSON.stringify(returnedBinding)),
      }};
    if (endpoint === "/api/optimal") return {optimization:{
        modelId:"model-42", backend:"omlx", options:{kv:"off"},
        changedKeys:[], appliedKeys:[],
        evidenceLabel:"Qualified local route",
        rationale:["Matching completed route evidence."],
        evidenceBinding:JSON.parse(JSON.stringify(returnedRouteBinding)),
      }};
    if (endpoint === "/api/profiles/save") return {profiles:[]};
    if (endpoint === "/api/profiles") return {profiles:state.profiles};
    throw new Error(`unexpected endpoint ${endpoint}`);
  },
  setRuntimeKvValue:() => true,
  speedSignature:() => "applied-speed-signature",
  clearOptimizerAnimationClasses:() => {},
  restoreOptimizerValues:() => {},
  updateBackend:() => {},
  schedulePerformanceReceipt:force => receiptSchedules.push(force),
  openCalibrationAssistant:async () => { throw new Error("completed evidence reopened Calibration"); },
  renderCalibration:() => {},
  showNotice:(message, error = false) => notices.push({message, error}),
  gather:() => ({}),
  useProfileInventory:data => { state.profiles = data.profiles || []; },
  profileRunBlocked:() => false,
  profileSettingsBlockReason:() => "",
  profileLaunchBlockReason:() => "",
  renderProfileEditBanner:() => {},
  updateProfilePolicyControls:() => {},
  requestAnimationFrame:() => {},
  applyProfileRequest:() => {},
  setProfileStatus:() => {},
  freeTokenExperimentalConsentRequired:() => false,
  setQuickStartEditor:() => {},
  renderProfiles:() => {},
  Event,
  console,
};

vm.createContext(context);
vm.runInContext(sourceBetween(
  "function engineShootoutApplyBinding(",
  "\nfunction renderEngineShootoutResults",
), context);
vm.runInContext(sourceBetween(
  "function optimizerEvidenceContractSignature(",
  "\nfunction optimizerValueSnapshot",
), context);
vm.runInContext(sourceBetween(
  "function markOptimizerCustom(",
  "\nfunction cancelOptimization",
), context);
vm.runInContext(sourceBetween(
  "async function applyOptimal(",
  "\nasync function prepareVerifiedQuickLaunch",
), context);
vm.runInContext(sourceBetween(
  "function calibrationBenchmarkActive(",
  "\nfunction calibrationQualificationProfile",
), context);
vm.runInContext(sourceBetween(
  "function completedCalibrationDecision(",
  "\nfunction calibrationParityRejectionNote",
), context);
vm.runInContext(sourceBetween(
  "function renderCalibrationPlan(",
  "\nfunction renderCalibrationBenchmark",
), context);
vm.runInContext(sourceBetween(
  "function calibrationRouteEvidenceApplyReady(",
  "\nasync function applyCalibrationResult",
), context);
vm.runInContext(sourceBetween(
  "async function applyCalibrationResult(",
  "\nfunction sessionDecisionClass",
), context);
vm.runInContext(sourceBetween(
  "function measuredProfileEvidenceBinding(",
  "\nfunction requestUsesExperimentalFreeToken",
), context);
vm.runInContext(sourceBetween(
  "async function applySavedProfile(",
  "\nasync function saveCurrentProfile",
), context);

async function run() {
  const initialPlan = state.calibrationPlan;
  element("calibrationStartButton").title = "Previous model needs High memory";
  element("calibrationStartButton").dataset.admission = "blocked";
  state.calibrationPlan = null;
  state.calibrationLoading = true;
  context.renderCalibrationPlan();
  assert.equal(element("calibrationStartButton").title, "");
  assert.equal(element("calibrationStartButton").dataset.admission, "checking");
  assert.equal(element("calibrationStartButton").disabled, true);
  state.calibrationPlan = initialPlan;
  state.calibrationLoading = false;
  const benchmarkApplyBinding = context.engineShootoutApplyBinding(
    completedResult, completedProfile, "throughput",
  );
  assert.deepEqual(JSON.parse(JSON.stringify(benchmarkApplyBinding)), binding);
  assert.notEqual(benchmarkApplyBinding, completedProfile.evidenceBinding);
  benchmarkApplyBinding.recordIds.omlx = "mutated-copy";
  assert.equal(completedProfile.evidenceBinding.recordIds.omlx, binding.recordIds.omlx);
  assert.equal(
    context.engineShootoutApplyBinding(completedResult, completedProfile, "fastest"),
    null,
  );
  assert.match(
    app,
    /void applyOptimal\("engine", preference, false, evidenceBinding\)/,
  );

  context.renderCalibrationPlan();
  assert.equal(element("calibrationStartButton").strong.textContent, "Test engines + settings");
  assert.match(element("calibrationEngineCards").innerHTML, /Up to 12 setups/);
  assert.match(element("calibrationEngineCards").innerHTML, /Settings search · DFlash 2 settings/);
  assert.match(element("calibrationStartLabel").textContent, /up to 23 setups/i);
  assert.equal(element("calibrationStartButton").classList.contains("calibration-run-action"), true);
  assert.equal(element("calibrationStartButton").classList.contains("primary"), true);
  assert.equal(element("calibrationStartButton").classList.contains("secondary"), false);
  assert.equal(element("calibrationApplyButton").disabled, true);
  assert.equal(element("calibrationApplyButton").classList.contains("primary"), false);
  assert.equal(element("calibrationApplyButton").classList.contains("secondary"), true);
  assert.equal(element("calibrationResults").classList.contains("hidden"), true);

  const measurementPlan = JSON.parse(JSON.stringify(state.calibrationPlan));
  const unsavedResult = JSON.parse(JSON.stringify(completedResult));
  unsavedResult.persistence = {saved:false};
  state.benchmarkPhase = "completed";
  state.benchmarkStatus = {
    phase:"completed", progress:1,
    job:{id:"shootout-42"}, result:unsavedResult,
  };
  context.renderCalibrationPlan();
  assert.equal(state.calibrationPlan.action, "measure");
  assert.equal(element("calibrationApplyButton").disabled, true);
  assert.equal(element("calibrationStartButton").strong.textContent, "Test engines + settings");
  assert.equal(element("calibrationResults").classList.contains("hidden"), true);

  const malformedBindingResult = JSON.parse(JSON.stringify(completedResult));
  malformedBindingResult.profiles.throughput.evidenceBinding = {
    scope:"engine", suite:"agentic", preference:"throughput",
    shootoutId:"shootout-42", recordIds:{omlx:"only-one-record"},
  };
  state.benchmarkStatus = {
    phase:"completed", progress:1,
    job:{id:"shootout-42"}, result:malformedBindingResult,
  };
  context.renderCalibrationPlan();
  assert.equal(state.calibrationPlan.action, "measure");
  assert.equal(element("calibrationApplyButton").disabled, true);
  assert.equal(element("calibrationResults").classList.contains("hidden"), true);

  const mismatchedShootoutResult = JSON.parse(JSON.stringify(completedResult));
  mismatchedShootoutResult.profiles.throughput.evidenceBinding.shootoutId = "another-shootout";
  state.benchmarkStatus = {
    phase:"completed", progress:1,
    job:{id:"shootout-42"}, result:mismatchedShootoutResult,
  };
  context.renderCalibrationPlan();
  assert.equal(state.calibrationPlan.action, "measure");
  assert.equal(element("calibrationApplyButton").disabled, true);

  const qualifiedResult = {
    id:"qualification-42", kind:"route-qualification", suite:"agentic",
    matrixWorkloadComparable:true, persistence:{saved:true},
    decision:{
      backend:"omlx", evidenceTier:"local-route-qualification",
      evidenceBinding:JSON.parse(JSON.stringify(routeBinding)),
    },
  };
  state.calibrationJobId = "qualification-42";
  assert.ok(context.completedCalibrationDecision({
    phase:"completed", job:{id:"qualification-42"}, result:qualifiedResult,
  }), "a saved route qualification with a usable route binding remains promotable");
  state.calibrationJobId = "shootout-42";
  state.calibrationPlan = measurementPlan;

  state.benchmarkPhase = "completed";
  state.benchmarkStatus = {
    phase:"completed", progress:1,
    job:{id:"shootout-42"}, result:completedResult,
  };
  context.renderCalibrationPlan();

  assert.equal(state.calibrationPlan.action, "apply-existing");
  assert.deepEqual(
    JSON.parse(JSON.stringify(state.calibrationPlan.evidence.evidenceBinding)),
    binding,
  );
  assert.notEqual(state.calibrationPlan.evidence.evidenceBinding, binding);
  assert.notEqual(
    state.calibrationPlan.evidence.evidenceBinding,
    completedResult.profiles.throughput.evidenceBinding,
  );
  completedResult.profiles.throughput.evidenceBinding.recordIds.omlx = "poisoned-after-render";
  assert.deepEqual(
    JSON.parse(JSON.stringify(state.calibrationPlan.evidence.evidenceBinding)),
    binding,
  );
  assert.equal(element("calibrationResults").classList.contains("hidden"), false);
  assert.match(element("calibrationResults").innerHTML, /Measured engine results/);
  assert.match(element("calibrationResults").innerHTML, /oMLX/);
  assert.match(element("calibrationResults").innerHTML, /Generation 19\.7 tok\/s/);
  assert.match(element("calibrationResults").innerHTML, /Selected: DFlash block 8 · dflash · q4/);
  assert.match(element("calibrationResults").innerHTML, /Tested 7\/12 setups/);
  assert.match(element("calibrationResults").innerHTML, /5\/10 DFlash 2 settings candidates/);
  assert.match(element("calibrationResults").innerHTML, /axes: DFlash block size, verification mode, draft precision/);
  assert.equal(element("calibrationApplyButton").disabled, false);
  assert.equal(element("calibrationApplyButton").textContent, "Apply result · oMLX");
  assert.equal(element("calibrationStartButton").strong.textContent, "Retest engines + settings");
  assert.equal(element("calibrationStartButton").disabled, false);
  assert.equal(element("calibrationStartButton").classList.contains("calibration-run-action"), true);
  assert.equal(element("calibrationStartButton").classList.contains("primary"), false);
  assert.equal(element("calibrationStartButton").classList.contains("secondary"), true);
  assert.equal(element("calibrationApplyButton").classList.contains("primary"), true);
  assert.equal(element("calibrationApplyButton").classList.contains("secondary"), false);

  uiAdmission = {
    known:true, actionReady:false, launchable:false,
    decision:"configuration", label:"Context exceeds safe capacity",
    detail:"The selected model and context do not fit safely.",
  };
  context.renderCalibrationPlan();
  assert.equal(element("calibrationStartButton").disabled, true, "retest stays fail-closed");
  assert.match(element("calibrationStartLabel").textContent, /too large for this Mac/i);
  assert.equal(element("calibrationApplyButton").disabled, false, "saved result remains usable");
  uiAdmission = {
    known:true, actionReady:true, launchable:true,
    decision:"ready", label:"Ready", detail:"This route fits safely.",
  };
  context.renderCalibrationPlan();

  state.calibrationPlan.reasoningContract = {
    normalized:true, original:"medium", measured:"auto",
  };
  element("reasoningSelect").options = [
    {value:"auto", disabled:false}, {value:"medium", disabled:false},
  ];
  element("reasoningSelect").value = "medium";
  context.renderCalibrationPlan();
  assert.equal(
    element("calibrationApplyButton").textContent,
    "Apply result · oMLX + model default",
  );

  const applicableEvidence = state.calibrationPlan.evidence;
  state.calibrationPlan.evidence = {
    ...applicableEvidence,
    evidenceBinding:{scope:"engine", suite:"agentic", preference:"throughput"},
  };
  const callsBeforeMalformedApply = apiCalls.length;
  await context.applyCalibrationResult(false);
  assert.equal(apiCalls.length, callsBeforeMalformedApply);
  assert.match(element("calibrationStatus").textContent, /no usable exact apply reference/i);
  state.calibrationPlan.evidence = applicableEvidence;

  const resultBeforeApply = state.benchmarkStatus.result;
  const receiptBeforeApply = state.performanceReceipt;
  await context.applyOptimizerMenuChoice("engine", "throughput");

  assert.equal(apiCalls.length, 1);
  assert.equal(apiCalls[0].endpoint, "/api/optimal-engine");
  assert.equal(apiCalls.filter(call => call.endpoint === "/api/benchmark/start").length, 0);
  assert.deepEqual(apiCalls[0].request.evidenceBinding, binding);
  assert.equal(apiCalls[0].request.enginePreference, "throughput");
  assert.equal(element("reasoningSelect").value, "auto");
  assert.equal(element("calibrationDialog").open, false);
  assert.equal(element("calibrationDialog").closeCount, 1);
  assert.equal(state.benchmarkStatus.result, resultBeforeApply);
  assert.equal(state.performanceReceipt, receiptBeforeApply);
  assert.deepEqual(state.performanceReceipt.evidenceBinding, binding);
  assert.equal(state.calibrationPlan.action, "apply-existing");
  assert.deepEqual(
    JSON.parse(JSON.stringify(state.calibrationPlan.evidence.evidenceBinding)),
    binding,
  );
  assert.deepEqual(
    JSON.parse(JSON.stringify(state.activeEvidenceBinding)), returnedBinding,
  );
  assert.notEqual(state.activeEvidenceBinding, returnedBinding);
  assert.ok(state.activeEvidenceSignature);
  assert.deepEqual(receiptSchedules, [true]);
  assert.equal(notices.some(notice => notice.error), false);

  const repeated = await context.applyOptimal("engine", "throughput", false);
  assert.equal(repeated, true);
  const repeatedApply = apiCalls.filter(call => call.endpoint === "/api/optimal-engine").at(-1);
  assert.deepEqual(repeatedApply.request.evidenceBinding, returnedBinding);

  element("calibrationProfileName").value = "Measured winner";
  element("calibrationDialog").open = true;
  await context.applyCalibrationResult(true);
  const saved = apiCalls.filter(call => call.endpoint === "/api/profiles/save").at(-1);
  assert.ok(saved, "calibration Apply + save should write a measured profile");
  assert.equal(saved.request.enginePolicy, "measured");
  assert.deepEqual(saved.request.evidenceBinding, returnedBinding);

  const measuredProfile = {
    id:"profile-42", name:"Measured winner", ready:true,
    enginePolicy:"measured", enginePreference:"throughput",
    evidenceBinding:JSON.parse(JSON.stringify(returnedBinding)),
    resolution:{backend:"omlx", detail:"Measured route ready."},
    request:{backend:"omlx", modelId:"model-42"},
  };
  const missingBinding = {...measuredProfile, evidenceBinding:undefined};
  const calibrationRequired = {
    ...missingBinding, ready:false,
    reason:"Run Calibration again before applying this measured profile.",
  };
  assert.equal(context.profileUiReady(missingBinding), false);
  assert.match(context.profileUiReason(missingBinding), /Calibration/);
  assert.equal(context.profileUiReady(calibrationRequired), false);
  assert.equal(context.profileUiReason(calibrationRequired), calibrationRequired.reason);
  assert.equal(context.profileUiReady(measuredProfile), true);
  assert.match(app, /const ready = profileUiReady\(profile\)/);

  state.profiles = [measuredProfile];
  await context.applySavedProfile(measuredProfile.id, false);
  const profileApply = apiCalls.filter(call => call.endpoint === "/api/optimal-engine").at(-1);
  assert.deepEqual(profileApply.request.evidenceBinding, returnedBinding);
  assert.equal(state.profileBusy, false);

  const appliedContext = element("contextInput").value;
  element("contextInput").value = String(Number(appliedContext) + 1);
  assert.equal(context.activeEvidenceBindingFor("engine", "throughput"), null);
  element("contextInput").value = appliedContext;

  const previousSpeedSignature = context.speedSignature;
  state.optimalSignature = "previous-speed";
  context.speedSignature = () => "edited-speed";
  context.markOptimizerCustom();
  assert.equal(state.activeEvidenceBinding, null);
  assert.equal(state.activeEvidenceSignature, "");
  context.speedSignature = previousSpeedSignature;

  state.calibrationPlan = {
    ...state.calibrationPlan,
    action:"apply-existing",
    routeQualification:true,
    evidence:{qualified:true, evidenceBinding:JSON.parse(JSON.stringify(routeBinding))},
  };
  element("calibrationProfileName").value = "Qualified route";
  element("calibrationDialog").open = true;
  await context.applyCalibrationResult(true);
  const savedRoute = apiCalls.filter(call => call.endpoint === "/api/profiles/save").at(-1);
  assert.deepEqual(savedRoute.request.evidenceBinding, returnedRouteBinding);
  assert.deepEqual(
    JSON.parse(JSON.stringify(state.activeEvidenceBinding)), returnedRouteBinding,
  );

  const routeProfile = {
    ...measuredProfile,
    id:"profile-route-42", name:"Qualified route",
    evidenceBinding:JSON.parse(JSON.stringify(returnedRouteBinding)),
    resolution:{backend:"omlx", detail:"Qualified route ready."},
  };
  assert.equal(context.profileUiReady(routeProfile), true);
  assert.deepEqual(
    JSON.parse(JSON.stringify(context.measuredProfileEvidenceBinding(routeProfile))),
    returnedRouteBinding,
  );
  state.profiles = [routeProfile];
  await context.applySavedProfile(routeProfile.id, false);
  const routeProfileApply = apiCalls.filter(call => call.endpoint === "/api/optimal").at(-1);
  assert.deepEqual(routeProfileApply.request.evidenceBinding, returnedRouteBinding);
  assert.equal(Object.hasOwn(routeProfileApply.request, "enginePreference"), false);

  const samplingHandler = sourceBetween(
    '$("samplingMode").addEventListener("change"',
    '\n$("systemPrompt").addEventListener',
  );
  assert.match(samplingHandler, /cancelOptimization\("Sampling changed/);
  assert.match(app, /"mtplxOperatorRouteSelect", "fanSelect"\]\.includes\(id\)/);

  assert.deepEqual(receiptSchedules, [true, true, true, true, true, true]);

  console.log("Completed Calibration bindings remain reusable through Apply and saved measured profiles.");
}

run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
