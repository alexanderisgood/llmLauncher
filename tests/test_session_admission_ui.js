"use strict";
const benchmarkSources = require("./helpers/benchmark_sources.js");

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const app = benchmarkSources.controllerSource;

function sourceBetween(startMarker, endMarker) {
  const start = app.indexOf(startMarker);
  const end = app.indexOf(endMarker, start + startMarker.length);
  assert.ok(start >= 0, `missing production marker: ${startMarker}`);
  assert.ok(end > start, `missing production end marker: ${endMarker}`);
  return app.slice(start, end);
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((accept, decline) => {
    resolve = accept;
    reject = decline;
  });
  return {promise, resolve, reject};
}

async function run() {
  let visibleRequest = {
    backend:"omlx", modelId:"large-model", client:"chat",
    context:131072, output:4096, reasoning:"auto", options:{kv:"q8"},
  };
  const scheduled = new Map();
  const backgroundLoads = [];
  let timerSequence = 0;
  const helperState = {
    sessionDashboard:null, sessionLoading:false,
    sessionAdmissionSignature:"", sessionLastLoadedAt:0,
    sessionAdmissionPendingSignature:"", sessionAdmissionError:"",
    sessionAdmissionErrorSignature:"", sessionAdmissionErrorAt:0,
    sessionAdmissionTimer:null, sessionAcknowledgementId:"",
  };
  const helperContext = {
    state:helperState,
    gather:() => visibleRequest,
    currentWarmRoutePlan:() => null,
    loadSessionDashboard:async options => { backgroundLoads.push(options); },
    refreshLaunchability:() => {},
    showNotice:() => {},
    setTimeout:(callback, delay) => {
      const id = ++timerSequence;
      scheduled.set(id, {callback, delay});
      return id;
    },
    clearTimeout:id => scheduled.delete(id),
  };
  vm.createContext(helperContext);
  benchmarkSources.runInContext(sourceBetween(
    "const SESSION_ADMISSION_REFRESH_MS",
    "\nfunction clearWarmRoutePlan",
  ), helperContext);

  let admission = helperContext.currentSessionAdmission();
  assert.equal(admission.actionReady, false, "unknown capacity fails closed");
  assert.equal(admission.decision, "checking");
  assert.match(helperContext.sessionAdmissionBlockerCopy(admission), /Checking this route fits safely/);

  const signature = helperContext.visibleSessionAdmissionSignature();
  helperState.sessionDashboard = {admission:{
    launchable:false, requiresAcknowledgement:false,
    decision:"configuration", label:"Context exceeds safe capacity",
    detail:"The selected model and KV cache exceed physical memory.",
  }};
  helperState.sessionAdmissionSignature = signature;
  helperState.sessionLastLoadedAt = Date.now();
  admission = helperContext.currentSessionAdmission();
  assert.equal(admission.actionReady, false);
  assert.match(
    helperContext.sessionAdmissionBlockerCopy(admission),
    /too large for this Mac/i,
  );
  helperState.sessionDashboard.admission.label = "Choose Qwen high-memory mode";
  assert.match(
    helperContext.sessionAdmissionBlockerCopy(
      helperContext.currentSessionAdmission(),
    ),
    /Choose High memory in Runtime controls/,
  );
  helperState.sessionDashboard.admission = {
    launchable:false, decision:"pressure", label:"Free memory before loading Splash",
    detail:"39.9 GiB needed. 29.8 GiB is available, including reclaimable cache.",
  };
  assert.match(helperContext.sessionAdmissionBlockerCopy(), /29.8 GiB is available, including reclaimable cache/);

  helperState.sessionDashboard = {admission:{
    launchable:true, requiresAcknowledgement:false,
    decision:"ready", label:"Ready", detail:"Safe capacity is available.",
  }};
  helperState.sessionLastLoadedAt = 1_000;
  assert.equal(
    helperContext.currentSessionAdmission(17_000).actionReady,
    false,
    "an admission older than the freshness window fails closed",
  );
  helperState.sessionLastLoadedAt = Date.now();
  assert.equal(helperContext.currentSessionAdmission().actionReady, true);

  helperState.sessionDashboard = {admission:{
    launchable:true, requiresAcknowledgement:true, contractId:"review-42",
    decision:"review", label:"Review memory", detail:"Review this estimate once.",
  }};
  helperState.sessionAcknowledgementId = "";
  assert.equal(helperContext.currentSessionAdmission().actionReady, false);
  helperState.sessionAcknowledgementId = "review-42";
  assert.equal(helperContext.currentSessionAdmission().actionReady, true);

  const jitNotices = [];
  helperContext.showNotice = message => jitNotices.push(message);
  helperContext.loadSessionDashboard = async () => null;
  helperState.sessionLoading = true;
  helperState.sessionAdmissionPendingSignature = signature;
  assert.equal(
    await helperContext.requireFreshSessionAdmission(),
    false,
    "a superseded or failed just-in-time check cannot reuse an older ready admission",
  );
  assert.match(jitNotices.at(-1), /Checking this route fits safely/);
  helperState.sessionLoading = false;
  helperState.sessionAdmissionPendingSignature = "";

  helperState.sessionDashboard = {admission:{
    launchable:true, requiresAcknowledgement:false,
    decision:"ready", label:"Ready", detail:"Safe capacity is available.",
  }};
  helperState.sessionAcknowledgementId = "";
  helperState.sessionLastLoadedAt = Date.now();
  helperContext.loadSessionDashboard = async options => { backgroundLoads.push(options); };
  scheduled.clear();
  helperContext.scheduleSessionAdmissionPlan();
  assert.equal(scheduled.size, 0, "a fresh admission does not schedule another refresh");

  helperState.sessionLastLoadedAt = Date.now() - 6_000;
  helperContext.scheduleSessionAdmissionPlan();
  assert.equal(scheduled.size, 1);
  const refreshTimer = [...scheduled.values()][0];
  assert.equal(refreshTimer.delay, 180, "background refreshes are debounced");
  refreshTimer.callback();
  await Promise.resolve();
  assert.equal(backgroundLoads.length, 1);
  assert.equal(backgroundLoads[0].force, true);

  helperState.sessionAdmissionError = "capacity refresh failed";
  helperState.sessionAdmissionErrorSignature = signature;
  helperState.sessionAdmissionErrorAt = Date.now();
  admission = helperContext.currentSessionAdmission();
  assert.equal(admission.actionReady, false, "a failed exact refresh invalidates the cached admission");
  assert.equal(admission.decision, "error");
  helperState.sessionAdmissionTimer = null;
  scheduled.clear();
  helperContext.scheduleSessionAdmissionPlan();
  assert.equal(scheduled.size, 0, "a failed refresh backs off instead of creating a retry loop");

  helperState.sessionDashboard = null;
  helperState.sessionAdmissionSignature = "";
  helperState.sessionLastLoadedAt = 0;
  helperState.sessionAdmissionError = "";
  helperState.sessionAdmissionErrorSignature = "";
  helperState.sessionAdmissionErrorAt = 0;
  helperState.sessionAdmissionTimer = null;
  scheduled.clear();
  helperContext.scheduleSessionAdmissionPlan();
  assert.equal([...scheduled.values()][0].delay, 180, "an unknown route is also debounced");

  helperState.sessionAdmissionTimer = null;
  scheduled.clear();
  helperState.sessionLoading = true;
  helperState.sessionAdmissionPendingSignature = signature;
  helperContext.scheduleSessionAdmissionPlan();
  assert.equal(scheduled.size, 0, "the same admission request is coalesced while pending");

  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {textContent:"", className:""});
    return elements.get(id);
  };
  let currentRequest = {backend:"omlx", modelId:"model-a", context:32768};
  const calls = [];
  const staleState = {
    sessionDashboard:null, sessionLoading:false, sessionGeneration:0,
    sessionAcknowledgementId:"", sessionAdmissionSignature:"",
    sessionLastLoadedAt:0, sessionAdmissionPendingSignature:"",
    sessionAdmissionError:"", sessionAdmissionErrorSignature:"",
    sessionAdmissionErrorAt:0, runStatus:null,
    warmRoutePlan:null, warmRouteSignature:"",
  };
  const staleContext = {
    state:staleState,
    $:element,
    visibleSessionAdmissionRequest:() => currentRequest,
    visibleSessionAdmissionSignature:request => JSON.stringify(request || currentRequest),
    renderSessionDashboard:() => {},
    refreshLaunchability:() => {},
    loadSessionAttachmentPlan:async () => {},
    warmRouteRequestSignature:request => JSON.stringify(request),
    api:async (_endpoint, options) => {
      const gate = deferred();
      calls.push({request:JSON.parse(options.body), gate});
      return gate.promise;
    },
  };
  vm.createContext(staleContext);
  benchmarkSources.runInContext(sourceBetween(
    "async function loadSessionDashboard(",
    "\nasync function openSessionDashboard",
  ), staleContext);

  const first = staleContext.loadSessionDashboard({force:true});
  currentRequest = {backend:"omlx", modelId:"model-b", context:65536};
  const second = staleContext.loadSessionDashboard({force:true});
  calls[0].gate.resolve({sessions:{admission:{marker:"stale", launchable:true}}});
  await first;
  assert.equal(staleState.sessionDashboard, null, "an older in-flight response is ignored");
  calls[1].gate.resolve({sessions:{admission:{marker:"current", launchable:false}}});
  await second;
  assert.equal(staleState.sessionDashboard.admission.marker, "current");
  assert.equal(staleState.sessionAdmissionSignature, JSON.stringify(currentRequest));

  staleState.sessionAdmissionError = "previous exact refresh failed";
  staleState.sessionAdmissionErrorSignature = JSON.stringify(currentRequest);
  staleState.sessionAdmissionErrorAt = Date.now();
  const recovery = staleContext.loadSessionDashboard({force:true});
  assert.equal(
    staleState.sessionAdmissionError,
    "previous exact refresh failed",
    "a failed admission stays fail-closed while its retry is pending",
  );
  calls[2].gate.resolve({sessions:{admission:{marker:"recovered", launchable:true}}});
  await recovery;
  assert.equal(staleState.sessionAdmissionError, "");
  assert.equal(staleState.sessionDashboard.admission.marker, "recovered");

  const third = staleContext.loadSessionDashboard({force:true});
  currentRequest = {backend:"omlx", modelId:"model-c", context:131072};
  calls[3].gate.reject(new Error("stale capacity failure"));
  await third;
  assert.notEqual(staleState.sessionAdmissionError, "stale capacity failure");
  assert.notEqual(staleState.sessionAdmissionErrorSignature, JSON.stringify(currentRequest));

  assert.match(app, /const coldLaunchable = Boolean\(coldControlsReady && !state\.launchPreparing\)/);
  assert.match(app, /\$\("previewButton"\)\.disabled = !coldControlsReady/);
  assert.match(app, /\$\("optimizerMenuButton"\)\.disabled = !coldControlsReady/);
  assert.match(app, /\$\("optimizerVerifiedLaunch"\)\.disabled = !coldControlsReady/);
  assert.match(app, /routeCheckStartButton"\)\.disabled = !\(canStart && plan\?\.contractId && admission\.actionReady\)/);
  assert.match(app, /routeCheckLaunchButton"\)\.disabled = !receiptReady \|\| state\.verifiedLaunchBusy \|\| !admission\.actionReady/);
  assert.match(app, /if \(!warm && launchOptions\.admissionChecked !== true && !await requireFreshSessionAdmission\(\)\) return false/);
  assert.match(app, /const canMeasure = \["measure", "apply-existing"\]\.includes\(plan\.action\)[^]*?&& measurementAdmission\.actionReady/);
  assert.match(app, /plan = await loadCalibrationPlan\(false\)[^]*?const admission = calibrationMeasurementAdmission/);

  console.log("session admission UI tests passed");
}

run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
