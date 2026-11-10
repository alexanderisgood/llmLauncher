"use strict";
const launchSources=require("./helpers/launch_sources.js");

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = launchSources.controllerSource;
const start = source.indexOf("function renderLaunchMemoryEstimate(");
const end = source.indexOf("\nfunction updateLaunchHome(", start);
const element = {dataset:{}};
const state = {
  sessionAdmissionSignature:"current",
  sessionDashboard:{admission:{estimate:{
    estimatedWorkingSetBytes:34.3 * 1024 ** 3,
    osReserveBytes:8 * 1024 ** 3,
    geometryReady:true,
  }}},
};
const context = vm.createContext({state, $:()=>element});
launchSources.runInContext(source.slice(start,end),context);
const render = admission => context.renderLaunchMemoryEstimate(admission);
render({known:true,signature:"current",decision:"ready"});
assert.equal(element.textContent,"Est. peak ~34.3 GiB");
assert.match(element.title,/Excludes macOS/);
assert.match(element.title,/8.0 GiB is reserved separately/);
render({known:false,signature:"new-settings",decision:"checking",pending:true});
assert.equal(element.textContent,"Checking memory…","Do not display the previous route's estimate while checking new settings");
render({known:true,signature:"old-settings",decision:"ready"});
assert.equal(element.textContent,"Memory estimate unavailable");
render({known:true,warm:true,decision:"ready"});
assert.equal(element.textContent,"Reusing engine");
state.sessionDashboard.admission.estimate.geometryReady = false;
render({known:true,signature:"current",decision:"unknown"});
assert.equal(element.textContent,"Memory estimate unavailable");
state.sessionDashboard.admission.estimate.geometryReady = true;
render({known:true,signature:"current",decision:"pressure"});
assert.equal(element.dataset.pressure,"true");
state.sessionDashboard.admission.estimate.remoteEngine = true;
render({known:true,signature:"current",decision:"ready"});
assert.equal(element.textContent,"Model managed by server");
console.log("Launch memory estimate: matching settings, stale plans, warm reuse and unavailable geometry passed.");
