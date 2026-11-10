"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const {harness} = require("./helpers/launch_workspace_harness.js");
const {harness:benchmarkHarness} = require("./helpers/benchmark_workspace_harness.js");
const routes = require("../route_preferences.js");
const home = require("../launcher_home.js");
const workspace = require("../launch_workspace.js");

const html = fs.readFileSync(path.join(__dirname, "../index.html"), "utf8");
assert.match(html, /data-backend="rapidmlx"/);
assert.ok(html.indexOf('data-backend="rapidmlx"') < html.indexOf('id="ssdRuntimeDisclosure"'));
assert.ok(workspace.nodeIds.includes("rapidmlxControls"));
assert.match(home.engineGuidance("rapidmlx"), /Auto.*native MTP.*AR/);
assert.doesNotMatch(home.engineGuidance("rapidmlx"), /verified|faster|tok\/s|×/i);
assert.equal(home.measurementView(null, "rapidmlx").speed, "Not measured");

const supported = Object.fromEntries(["chat", "pi", "omp", "opencode"].map(client => [client, {supported:true}]));
supported.codex = {supported:false, reason:"Responses support has not been advertised"};
const capability = {runnable:true, mtp:true, dflash:false, kv:false, depth:3, depthMax:4,
  depthChoices:[1,2,3,4], preferredAcceleration:"auto",
  contextWindows:[8192,16384,32768,65536], contextMaximum:32768, outputMaximum:8192,
  agentReasoning:["auto","off"], codexReasoning:["auto"], clientSupport:supported};
const h = harness({registry:{clientSupport:()=>({rapidmlx:supported})}});
h.model.backends.rapidmlx = capability;
h.runtimes.rapidmlx = {installed:true};
h.groups.registry.adapters().engines.push({id:"rapidmlx", binaryKey:"rapidmlx", label:"Rapid MLX", installed:true});
h.nodes.accelerationSelect.options = ["auto", "mtp", "dflash", "off"].map(value => ({value, disabled:false}));
h.nodes.accelerationSelect.querySelector = selector => h.nodes.accelerationSelect.options.find(option => selector.includes(`"${option.value}"`));
h.controller.initialize();
h.controller.useModelInventory([h.model]);
h.controller.setBackend("rapidmlx");
h.nodes.accelerationSelect.value = "dflash";
h.nodes.depthInput.value = "8";
h.controller.updateBackend();
assert.equal(h.nodes.rapidmlxControls.classList.contains("hidden"), false);
assert.equal(h.nodes.recControls.classList.contains("hidden"), true);
assert.equal(h.nodes.sharedRuntimeControls.classList.contains("hidden"), false);
assert.deepEqual(h.controller.gatherOptions(), {acceleration:"auto", depth:3, kv:"off"});
assert.equal(h.nodes.depthInput.disabled, true);
assert.equal(h.nodes.rapidmlxDepthSelect.disabled, false);
assert.equal(h.nodes.depthInput.max, "4");
assert.equal(h.nodes.rapidmlxDepthSelect.value, "3");
assert.match(h.nodes.rapidmlxDepthSelect.innerHTML, /3 · native default/);
assert.deepEqual(h.nodes.accelerationSelect.options.filter(option => !option.disabled).map(option => option.value), ["auto", "mtp", "off"]);
assert.equal(h.controller.setRuntimeKvValue("rapidmlx", "off"), true);
assert.equal(h.controller.setRuntimeKvValue("rapidmlx", "q8"), false);

// The native route's maximum constrains both typed values and the menu.
assert.equal(Number(h.nodes.contextInput.max), 32768);
assert.match(h.nodes.contextSelect.innerHTML, /32768/);
assert.doesNotMatch(h.nodes.contextSelect.innerHTML, /65536/);
h.nodes.contextInput.value = "65536";
assert.match(h.controller.limitError(), /Rapid MLX supports at most 32,768/);
h.nodes.contextInput.value = "16384";
assert.equal(h.controller.limitError(), "");

const rapidRoutes = h.controller.visibleRouteCatalog().filter(route => route.backend === "rapidmlx");
assert.deepEqual(rapidRoutes.map(route => route.client).sort(), ["chat", "omp", "opencode", "pi"]);
for (const route of rapidRoutes) {
  assert.deepEqual(routes.normaliseRoute(route), route);
  assert.deepEqual(routes.selectInitialRoute({preference:route, routes:[route]}), {...route, source:"remembered"});
}
// Codex enters only after explicit capability support, rather than its install alone.
h.model.backends.rapidmlx.clientSupport = {...supported, codex:{supported:true}};
h.controller.useModelInventory([h.model]);
assert.equal(h.controller.visibleRouteCatalog().some(route => route.backend === "rapidmlx" && route.client === "codex"), true);

const profile = {backend:"rapidmlx", client:"omp", modelId:h.model.id, project:"/generated/project",
  context:16384, output:1024, reasoning:"auto", agentHost:"terminal", generation:{sampling:"model"},
  options:{acceleration:"mtp", depth:2, kv:"off"}};
h.controller.applyProfileRequest(profile);
assert.deepEqual(h.controller.gatherOptions(), profile.options);
assert.equal(h.controller.view().client, "omp");
assert.throws(() => h.controller.applyProfileRequest({...profile, options:{...profile.options, depth:5}}), /saved MTP draft depth is no longer supported/);
h.controller.applyProfileRequest({...profile, options:{...profile.options, depth:4}});
assert.equal(h.controller.gatherOptions().depth, 4);
h.model.backends.rapidmlx.mtp = false;
h.controller.useModelInventory([h.model]);
h.controller.modelChanged();
assert.equal(h.nodes.accelerationSelect.options.find(option => option.value === "mtp").disabled, true);
assert.throws(() => h.controller.applyProfileRequest({...profile, options:{...profile.options, depth:1}}), /saved acceleration route is no longer available/);
h.nodes.accelerationSelect.value = "mtp";
assert.match(h.controller.accelerationSelectionError(), /MTP is unavailable/);
h.nodes.accelerationSelect.value = "dflash";
assert.match(h.controller.accelerationSelectionError(), /supports Auto, AR or MTP/);

// Flash-Next uses its own native default and restricted depths, without an
// origin/name lock or a claim that its GGUF artifact can run through MLX.
const flash = structuredClone(h.model);
flash.id = "shared-flash-mlx";
flash.name = "Qwen3.8 Flash-Next MLX";
flash.origins = ["Existing shared model folder"];
flash.backends.rapidmlx = {...capability, mtp:true, depth:1, depthMax:2, depthChoices:[1,2], preferredAcceleration:"auto"};
h.controller.useModelInventory([flash]);
h.nodes.modelSelect.options = [{value:flash.id}];
h.nodes.modelSelect.value = flash.id;
h.controller.renderModelOptions();
assert.match(h.nodes.modelSelect.innerHTML, /shared-flash-mlx/);
assert.deepEqual(h.controller.gatherOptions(), {acceleration:"auto", depth:1, kv:"off"});
assert.doesNotMatch(h.nodes.rapidmlxDepthSelect.innerHTML, /value="3"/);
h.nodes.rapidmlxDepthSelect.value = "2";
h.nodes.rapidmlxDepthSelect.dispatch("change");
assert.equal(h.controller.gatherOptions().depth, 2);
h.nodes.accelerationSelect.value = "off";
h.controller.updateAccelerationState();
assert.equal(h.nodes.rapidmlxDepthSelect.disabled, true);
h.nodes.accelerationSelect.value = "auto";
h.controller.updateAccelerationState();
assert.equal(h.nodes.rapidmlxDepthSelect.disabled, false);
assert.equal(h.controller.gatherOptions().depth, 2, "An explicit supported depth survives Auto/Off toggling");
const fixed = structuredClone(flash);
fixed.id = "native-fixed-pair";
fixed.backends.rapidmlx = {...flash.backends.rapidmlx, depth:2, depthMax:2, depthChoices:[2], preferredAcceleration:"mtp"};
h.controller.useModelInventory([fixed]);
h.nodes.modelSelect.options = [{value:fixed.id}];
h.nodes.modelSelect.value = fixed.id;
h.controller.renderModelOptions();
assert.deepEqual(h.controller.gatherOptions(), {acceleration:"mtp", depth:2, kv:"off"});
assert.match(h.nodes.rapidmlxDepthSelect.innerHTML, /value="2"/);
assert.doesNotMatch(h.nodes.rapidmlxDepthSelect.innerHTML, /value="1"/);
const sparse = structuredClone(fixed);
sparse.id = "native-sparse-depths";
sparse.backends.rapidmlx.depth = 3;
sparse.backends.rapidmlx.depthChoices = [1,3,6];
delete sparse.backends.rapidmlx.depthMax;
h.controller.useModelInventory([sparse]);
h.nodes.modelSelect.options = [{value:sparse.id}];
h.nodes.modelSelect.value = sparse.id;
h.controller.renderModelOptions();
assert.equal(h.controller.gatherOptions().depth, 3);
assert.match(h.nodes.rapidmlxDepthSelect.innerHTML, /value="6"/);
assert.doesNotMatch(h.nodes.rapidmlxDepthSelect.innerHTML, /value="4"/);
assert.match(html, /Rapid MLX uses MLX safetensors; GGUF files/);

const data = new Map();
const storage = {getItem:key=>data.get(key), setItem:(key,value)=>data.set(key,value)};
const route = {backend:"rapidmlx", client:"omp", modelId:h.model.id};
assert.equal(routes.writeSetup(storage, route, {accelerationSelect:"mtp", depthInput:"3", contextInput:"16384"}), true);
assert.equal(routes.readSetup(storage, route).controls.accelerationSelect, "mtp");
assert.equal(routes.readSetup(storage, route).controls.depthInput, "3");

// Comparison helpers accept the new backend without inventing a speed result.
const b = benchmarkHarness();
b.model.backends.rapidmlx = {...capability, mtp:true};
const comparison = b.controller.engineShootoutRoutes().find(item => item.backend === "rapidmlx");
assert.equal(comparison.eligible, true);
assert.deepEqual(comparison.modes.map(mode => mode.id), ["ar", "mtp"]);
b.model.ssdStreaming = {recommended:true, calibration:{engines:["kolibri"]}};
assert.equal(b.controller.engineShootoutRoutes().some(item => item.backend === "rapidmlx" && item.eligible), true,
  "A runnable compatible model is not hidden by another engine's SSD recommendation");
b.request.options.kv = "q8";
assert.match(b.controller.engineShootoutRoutes().find(item => item.backend === "rapidmlx").reason, /KV precision/);
assert.equal(h.requests.length, 0, "Control changes do not start a model or send server requests");

const app = fs.readFileSync(path.join(__dirname, "../app.js"), "utf8");
const functionSource = name => {
  const start = app.indexOf(`function ${name}(`);
  const end = app.indexOf("\nfunction ", start + 1);
  assert.ok(start >= 0 && end > start);
  return app.slice(start, end);
};
const labels = vm.createContext({formatNumber:value=>Number(value).toLocaleString("en-US"),
  isUzuModel:()=>false, adapterDescriptor:()=>null});
vm.runInContext(["modelContextLabel", "backendName", "backendMark", "backendBinaryKey", "profileBackendLabel", "routeCapabilityPresentation"].map(functionSource).join("\n"), labels);
assert.equal(labels.modelContextLabel({nativeContext:65536}, capability, "rapidmlx"), "65,536 native · 32,768 runtime cap");
assert.equal(labels.backendName("rapidmlx"), "Rapid MLX");
assert.equal(labels.profileBackendLabel("rapidmlx"), "Rapid MLX");
assert.equal(labels.backendMark("rapidmlx"), "RM");
assert.equal(labels.backendBinaryKey("rapidmlx"), "rapidmlx");
assert.equal(labels.routeCapabilityPresentation(flash.backends.rapidmlx,
  {backend:"rapidmlx", modelName:flash.name, modelReady:true}).available, true);
assert.equal(labels.routeCapabilityPresentation({...flash.backends.rapidmlx, runnable:false},
  {backend:"rapidmlx", modelName:flash.name, modelReady:true}).available, false);

console.log("Rapid MLX selection, capability controls, limits, profiles and route eligibility passed without startup.");
