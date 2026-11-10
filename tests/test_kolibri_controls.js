"use strict";
const launchSources=require("./helpers/launch_sources.js");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const preferences = require("../route_preferences.js");
const app = launchSources.controllerSource;
const start = app.indexOf("function setRuntimeKvValue(");
const end = app.indexOf("function gatherOptions(",start);
const gatherEnd = app.indexOf('  if (state.backend === "freetoken")',end);
const controls = {
  kolibriKv:{value:"off",options:["off","q8","q6","q4"].map(value=>({value}))},
  kolibriMemoryGB:{value:"40"},kolibriMemoryMode:{value:"auto"},
  kolibriPrefillSelect:{value:"64"},kolibriPromptCacheGB:{value:"4"},
};
const context = vm.createContext({$:id=>controls[id],state:{backend:"kolibri"}});
launchSources.runInContext(app.slice(start,end)+app.slice(end,gatherEnd)+"}",context);
for (const kv of ["off","q8","q6","q4"]) {
  assert.equal(context.setRuntimeKvValue("kolibri",kv),true);
  const options = JSON.parse(JSON.stringify(context.gatherOptions()));
  assert.deepEqual(options,{acceleration:"off",depth:1,kv,memoryGB:40,memoryMode:"auto",prefillSize:64,promptCacheGB:4});
}
assert.equal(context.setRuntimeKvValue("kolibri","q3"),false);

const data = new Map();
const storage = {getItem:key=>data.get(key),setItem:(key,value)=>data.set(key,value)};
const route = {backend:"kolibri",client:"chat",modelId:"kolibri-q6"};
assert.equal(preferences.writeRoute(storage,route).stored,true);
assert.deepEqual(preferences.readRoute(storage),route);
const values = Object.fromEntries(Object.entries(controls).map(([key,control])=>[key,control.value]));
assert.equal(preferences.writeSetup(storage,route,values),true);
assert.deepEqual(preferences.readSetup(storage,route).controls,values);
assert.deepEqual(preferences.reconcileRuntimeLimits({context:262144,output:65536,
  contextWindows:[2048,4096,8192,16384,32768,65536,131072,262144],outputMaximum:65536}),
  {context:262144,output:65536,contextChanged:false,outputChanged:false,promptBudget:196608});

// Numeric cache-budget edits must persist before blur or page reload.
for (const control of Object.values(controls)) {
  control.events = {};
  control.addEventListener = (event,fn)=>{control.events[event]=fn;};
}
for (const name of ["cancelOptimization","refreshLaunchability","scheduleBenchmarkHistory","schedulePerformanceReceipt"]) {
  context[name] = ()=>{};
}
context.persistVisibleRoute = ()=>preferences.writeSetup(storage,route,
  Object.fromEntries(Object.entries(controls).map(([key,control])=>[key,control.value])));
const eventsStart = app.indexOf('for (const id of ["kolibriKv",');
const eventsEnd = app.indexOf('\n$("slotstreamKv").addEventListener',eventsStart);
assert.ok(eventsStart>=0 && eventsEnd>eventsStart);
launchSources.runInContext(app.slice(eventsStart,eventsEnd),context);
controls.kolibriPromptCacheGB.value="1";
context.persistVisibleRoute();
controls.kolibriPromptCacheGB.value="4";
controls.kolibriPromptCacheGB.events.input();
assert.equal(preferences.readSetup(storage,route).controls.kolibriPromptCacheGB,"4");
console.log("Kolibri KV, prefill and prompt-cache selections reach launch options and survive reload.");
