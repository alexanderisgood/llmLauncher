"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const launch = require("./helpers/launch_sources.js");
const routes = require("../route_preferences.js");
const home = require("../launcher_home.js");
const root = path.join(__dirname, "..");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const workspace = require("../launch_workspace.js");

// Rec is a resident model choice, outside the SSD-only selector group.
assert.match(html, /data-backend="rec"/);
assert.ok(html.indexOf('data-backend="rec"') < html.indexOf('id="ssdRuntimeDisclosure"'));
assert.match(html, /id="recControls"/);
assert.ok(workspace.nodeIds.includes("recControls"));
assert.match(home.engineGuidance("rec"), /Flint INT4.*reasoning and function tools/);

// A saved Rec route survives normalization and restores without changing model.
for (const client of ["pi", "omp", "opencode", "chat"]) {
  const route = {backend:"rec", modelId:"RecursiveSI/flint-int4", client};
  assert.deepEqual(routes.normaliseRoute(route), route);
  assert.deepEqual(routes.selectInitialRoute({preference:route, routes:[route]}), {...route, source:"remembered"});
}

// Hidden shared controls must never leak another engine's acceleration or KV.
const context = vm.createContext({state:{backend:"rec"}});
vm.runInContext([
  launch.functionSource("gatherOptions"),
  launch.functionSource("setRuntimeKvValue"),
  launch.functionSource("accelerationSelectionError"),
].join("\n"), context);
assert.deepEqual(JSON.parse(JSON.stringify(context.gatherOptions())), {acceleration:"off", depth:1, kv:"off"});
assert.equal(context.setRuntimeKvValue("rec", "off"), true);
assert.equal(context.setRuntimeKvValue("rec", "q4"), false);
assert.equal(context.accelerationSelectionError({}), "");

// Reasoning choices come from the native capability, without invented efforts.
const reasoning = vm.createContext({state:{backend:"rec", client:"pi"},
  selectedModel:()=>({backends:{rec:{agentReasoning:["auto"]}}})});
vm.runInContext(launch.functionSource("reasoningChoices"), reasoning);
assert.deepEqual(Array.from(reasoning.reasoningChoices()), ["auto"]);

// A prior route's penalties remain visible and editable until explicitly reset.
const values = {samplingMode:"custom", temperatureInput:"1", topPInput:"0.95", topKInput:"20",
  presencePenaltyInput:"0", frequencyPenaltyInput:"0.4", repetitionPenaltyInput:"1.1", seedInput:"", systemPrompt:""};
const nodes = Object.fromEntries(Object.entries(values).map(([id, value])=>[id, {value, disabled:false,
  classList:{toggle() {}}, querySelector:()=>({disabled:false})}]));
for (const id of ["chatSettings", "samplingHelp", "chatSamplingAdvancedSummary"]) nodes[id]={classList:{toggle() {}}};
const sampling = vm.createContext({state:{backend:"rec", client:"pi"}, $:id=>nodes[id],
  collections:{chatSamplers:[]}, selectedModel:()=>({backends:{rec:{customSampling:true}}})});
vm.runInContext(launch.functionSource("chatSettingsError") + "\n" + launch.functionSource("updateChatSamplingControls"), sampling);
sampling.updateChatSamplingControls();
assert.equal(nodes.frequencyPenaltyInput.value, "0.4");
assert.equal(nodes.frequencyPenaltyInput.disabled, false);
assert.match(sampling.chatSettingsError(), /frequency penalty 0/);
nodes.frequencyPenaltyInput.value="0";
assert.match(sampling.chatSettingsError(), /repetition penalty 1/);
nodes.repetitionPenaltyInput.value="1";
sampling.updateChatSamplingControls();
assert.equal(nodes.frequencyPenaltyInput.disabled, true);
assert.equal(nodes.repetitionPenaltyInput.disabled, true);
assert.equal(sampling.chatSettingsError(), "");
sampling.state.backend="omlx";
sampling.updateChatSamplingControls();
assert.equal(nodes.frequencyPenaltyInput.disabled, false);
assert.equal(nodes.repetitionPenaltyInput.disabled, false);

console.log("Rec selector, saved routes and native control defaults passed");
