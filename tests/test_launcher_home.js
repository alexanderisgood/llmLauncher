"use strict";

const assert = require("node:assert/strict");
const home = require("../launcher_home.js");
const presenter = require("../ui_presenter.js");
const routes = require("../route_preferences.js");
const metrics = require("../request_metrics.js");
const fs = require("node:fs");
const vm = require("node:vm");

const models = [{id:"qwen", name:"Qwen Q6", quantization:"Q6_K"}, {id:"other", name:"Other Q4"}];
assert.deepEqual(home.filterModels(models, "other", "qwen"), {models, count:1, filtering:true});
assert.equal(home.filterModels(models, "missing", "qwen").models[0].id, "qwen", "Search must preserve the selected model");
assert.deepEqual(home.filterModels(models, "qwen q6", ""), {models:[models[0]], count:1, filtering:true});
const records = [
  {...models[0], format:"MLX", artifact:"/fixture/qwen"},
  {id:"qwen-splash", name:"Qwen Q6 · Splash", format:"mlx", splash:{path:"/fixture/qwen"}},
  {id:"qwen-other", name:"Qwen Q6", format:"mlx", artifact:"/fixture/other-weights"},
];
const groups = home.modelRouteGroups(records, [
  {backend:"omlx", modelId:"qwen", client:"omp"}, {backend:"splash", modelId:"qwen-splash", client:"omp"},
  {backend:"omlx", modelId:"qwen-other", client:"omp"},
], String);
assert.equal(groups.length,2,"Only matching original artifacts share a picker entry");
assert.deepEqual(groups[0].engines,["omlx","splash"]);

const receipt = {backend:"splash", state:"trusted-route", fresh:true, decodeTokensPerSecond:31.25, firstTokenSeconds:0.39};
assert.equal(home.measurementView(receipt,"splash").speed,"31.3 tok/s");
assert.equal(home.measurementView(receipt,"kolibri").speed,"Not measured", "An engine comparison winner must not become another engine's TPS");
for (const changes of [{fresh:false}, {contextAdjustment:{measured:16384}}, {reasoningContract:{normalized:true}}]) {
  assert.equal(home.measurementView({...receipt,...changes},"splash").speed,"Not measured");
}
assert.equal(home.measurementView({...receipt,decodeTokensPerSecond:"31"},"splash").speed,"Not reported");
assert.equal(home.measurementView(receipt,"splash",{loading:true}).speed,"Checking…", "Do not keep stale TPS during contract lookup");

const select = {value:"console", options:[{value:"console", hidden:false, disabled:false}, {value:"terminal"}]};
home.syncAgentHost(select,"omp");
assert.equal(select.value,"terminal");
assert.equal(select.options[0].disabled,true);
home.syncAgentHost(select,"pi");
assert.equal(select.options[0].disabled,false);
for (const backend of ["splash","slotstream","kolibri"]) {
  assert.equal(routes.normaliseRoute({backend, modelId:"qwen", client:"omp"}).client,"omp");
}

let writes = 0, replacements = 0;
const elements = new Map();
function element(id) {
  if (!elements.has(id)) {
    const node = {dataset:{}, classList:{contains:()=>false}, querySelectorAll:()=>[], getAttribute(name) {return this[name];},
      setAttribute(name,value) {writes++; this[name]=value;}, replaceChildren() {replacements++;}};
    for (const property of ["textContent","value","title","inert"]) {
      let value = property === "value" ? "" : undefined;
      Object.defineProperty(node,property,{get:()=>value, set:next=>{value=next; writes++;}});
    }
    elements.set(id,node);
  }
  return elements.get(id);
}
const state = {backend:"splash",client:"omp",performanceReceipt:receipt,performanceReceiptLoading:false};
element("contextInput").value="131072";
element("outputInput").value="16384";
element("reasoningSelect").value="auto";
const controller = home.createController({
  $:element, state, presenter,
  document:{body:{dataset:{}}, createElement:()=>({}),
    querySelectorAll:()=>[{dataset:{backend:"splash"}, disabled:false, hidden:false}]},
  backendName:()=>"Splash", clientName:()=>"oh-my-pi", protectedSnapshot:()=>"contract",
  formatNumber:String, exactContextTier:()=>"128K", gatherOptions:()=>({}), runtimeKvLabel:()=>"Full precision",
  currentWarmRoutePlan:()=>null, clientAvailability:()=>({available:true}), selectedModel:()=>models[0], esc:String,
});
controller.update({decision:"ready"},groups);
writes=0;
for (let i=0;i<500;i++) controller.update({decision:"ready"},groups);
assert.equal(writes,0,"Stable status refreshes must not rewrite home text, select values or input state");
assert.equal(replacements,1,"Native option serialization must not force a rebuild every poll");
element("homeRouteEngine").textContent="Changed by another view";
controller.update({decision:"ready"},groups);
assert.equal(element("homeRouteEngine").textContent,"Splash","Presenter must repair real DOM changes, not rely on stale caches");

assert.equal(metrics.phaseLabel({state:"running",liveTelemetry:{source:"omlx-activity",phase:"prefill"}},()=>"Generating"),"Reading context");
assert.equal(metrics.liveTelemetry({state:"queued",liveTelemetry:{source:"mtplx-flight",tokensPerSecond:90}}),null);
assert.equal(metrics.liveTelemetry({state:"running",liveTelemetry:{source:"unknown",tokensPerSecond:90}}),null);
// Browser serialization expands/normalizes character references. Slash-menu
// polls must retain the same buttons and keyboard focus through that difference.
const source = fs.readFileSync(require.resolve("../agent_console_workspace.js"),"utf8");
const commandStart = source.indexOf("function renderAgentConsoleCommands(");
const commandEnd = source.indexOf("\nconst piMenuKeys",commandStart);
let commandWrites=0, commandMarkup="";
const commandPanel={dataset:{},hidden:false,get innerHTML(){return commandMarkup.replace(/&#39;/g,"'");},
  set innerHTML(value){commandMarkup=value;commandWrites++;}};
const commandMeta={protocol:"pi-rpc",commands:[{name:"review",description:"Review 'this' change"}]};
const commandContext=vm.createContext({UiPresenter:presenter,AgentConsoleInputCore:require("../agent_console_input.js"),currentAgentConsoleView:()=>({meta:commandMeta}),
  $:id=>id==="agentConsoleCommands"?commandPanel:{value:"/re"},
  esc:value=>String(value).replace(/'/g,"&#39;")});
vm.runInContext(source.slice(commandStart,commandEnd),commandContext);
for(let i=0;i<500;i++)commandContext.renderAgentConsoleCommands(commandMeta);
assert.equal(commandWrites,1,"Stable slash-command polls must retain their existing buttons and focus");
commandMeta.commands[0].description="Updated description";
commandContext.renderAgentConsoleCommands(commandMeta);
assert.equal(commandWrites,2,"Changed command metadata must still update the menu");
console.log("Launcher home: selection-safe search, exact measured TPS, OMP terminal hosts, 500 unchanged renders and telemetry source checks passed.");
