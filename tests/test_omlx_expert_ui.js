'use strict';
const launchSources=require("./helpers/launch_sources.js");
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = launchSources.controllerSource;
const start = source.indexOf('function gatherOptions()');
const end = source.indexOf('function gatherGenerationSettings()',start);
const elements = new Proxy({omlxExpertResidentPercent:{value:'37.5'},omlxMemoryGB:{value:'41'},
  memoryGuardSelect:{value:'balanced'},accelerationSelect:{value:'off'}}, {
  get:(object,key)=>object[key] || {value:'1'}
});
let model = {omlxExpertOffload:{supported:true}};
const context = vm.createContext({state:{backend:'omlx'},$:id=>elements[id],selectedModel:()=>model,runtimeKvValue:()=> 'off'});
launchSources.runInContext(source.slice(start,end),context);
let options = context.gatherOptions();
assert.equal(options.expertResidentPercent,37.5);
assert.equal(options.omlxMemoryGB,41);
assert.equal(options.memoryGuard,'high');
assert.equal(options.acceleration,'off');
model = {};
options = context.gatherOptions();
assert.equal(options.memoryGuard,'balanced');
assert.equal(Object.hasOwn(options,'expertResidentPercent'),false);
assert.equal(Object.hasOwn(options,'omlxMemoryGB'),false);
console.log('oMLX offload controls preserve the chosen share and ceiling without affecting other models');
