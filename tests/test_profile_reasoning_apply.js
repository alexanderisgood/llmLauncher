"use strict";
const launchSources=require("./helpers/launch_sources.js");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const app = launchSources.controllerSource;
const html = fs.readFileSync(path.join(__dirname, "../index.html"), "utf8");
function between(start, end) {
  const from = app.indexOf(start), to = app.indexOf(end, from + start.length);
  assert.ok(from >= 0 && to > from);
  return app.slice(from, to);
}

// Browser option values follow their text unless the value attribute is explicit.
class Option {
  constructor(text, value = null, selected = false) {
    this.textContent = text;
    this.explicitValue = value;
    this.selected = selected;
    this.disabled = false;
  }
  get value() { return this.explicitValue ?? this.textContent; }
  set value(value) { this.explicitValue = String(value); }
}
class Select {
  constructor(options) { this.options = options; }
  get value() { return this.options.find(option => option.selected)?.value || ""; }
  set value(value) {
    for (const option of this.options) option.selected = option.value === String(value);
  }
}
const reasoningMarkup = html.match(/<select id="reasoningSelect">([\s\S]*?)<\/select>/)[1];
const reasoningOptions = [...reasoningMarkup.matchAll(/<option([^>]*)>([^<]*)<\/option>/g)]
  .map(([, attributes, text]) => new Option(text, attributes.match(/\bvalue="([^"]*)"/)?.[1], /\bselected\b/.test(attributes)));
const makeSelect = (...values) => new Select(values.map(value => new Option(value, value)));
const elements = {
  reasoningSelect:new Select(reasoningOptions),
  modelSelect:makeSelect("flash", "qwen-27b-6bit"),
  agentHostSelect:makeSelect("terminal", "hub"),
  accelerationSelect:makeSelect("auto", "off", "dflash"),
  samplingMode:makeSelect("model", "custom"),
  outputInput:{value:"4096"}, contextInput:{value:"16384"},
};
const controls = id => elements[id] ||= {value:""};
const models = [
  {id:"flash", backends:{whallm:{agentReasoning:["auto"]}}},
  {id:"qwen-27b-6bit", backends:{
    mtplx:{agentReasoning:["auto", "off", "medium", "high"]},
    omlx:{agentReasoning:["auto", "off", "medium", "high"], codexReasoning:["auto"]},
  }},
];
const state = {backend:"whallm", client:"pi"};
const persisted = [];
elements.modelSelect.value = "flash";
const ctx = vm.createContext({
  state, $:controls,
  selectedModel:() => models.find(model => model.id === elements.modelSelect.value),
  formatNumber:value => Number(value).toLocaleString("en-US"),
  updateContextChoices() {}, uiRequestVisible:() => true,
  cancelOptimization() {}, setRangeVisual() {}, updateChatSamplingControls() {},
  setRuntimeKvValue(_backend, value) { controls("kvFixture").value = value; return true; },
  updateAccelerationState() {}, setOptimizationState() {},
  updateOmlxKvControl() {},
  MTPLX_OPERATOR_ROUTE_DEFAULT:"default",
  updateBackend() {
    elements.modelSelect.options = models.filter(model => model.backends[state.backend])
      .map(model => new Option(model.id, model.id));
    elements.modelSelect.value = elements.modelSelect.options[0]?.value;
    ctx.modelChanged();
  },
  // Model selection refreshes and saves defaults before full profile restoration.
  modelChanged() { ctx.refreshLaunchability(); ctx.persistVisibleRoute(); },
  persistVisibleRoute() {
    persisted.push({backend:state.backend, client:state.client, modelId:elements.modelSelect.value,
      project:controls("projectPath").value, context:Number(elements.contextInput.value),
      output:Number(elements.outputInput.value), reasoning:elements.reasoningSelect.value,
      agentHost:elements.agentHostSelect.value,
      options:{acceleration:elements.accelerationSelect.value, kv:controls("kvFixture").value},
      generation:{sampling:elements.samplingMode.value}});
    return true;
  },
});
launchSources.runInContext(
  between("function reasoningChoices(", "function adapterDescriptor(")
  + between("function refreshLaunchability()", '  collections.backendButtons.forEach') + "}\n"
  + between("function setProfileSelect(", "async function applySavedProfile("), ctx,
);
const profile = {
  backend:"omlx", client:"pi", modelId:"qwen-27b-6bit", project:"/tmp/profile-fixture",
  context:32768, output:4096, reasoning:"medium", agentHost:"hub",
  options:{acceleration:"dflash", kv:"off"}, generation:{sampling:"model"},
};

ctx.refreshLaunchability();
assert.equal(elements.reasoningSelect.value, "auto");
assert.equal(reasoningOptions.find(option => option.value === "medium").disabled, true);
ctx.applyProfileRequest(profile);
assert.equal(elements.reasoningSelect.value, "medium", "Whallm → oMLX restores supported thinking");
assert.equal(reasoningOptions.find(option => option.value === "medium").disabled, false);
assert.equal(persisted[0].reasoning, "auto", "Model selection initially persists its default reasoning");
assert.deepEqual(persisted.at(-1), profile, "The final persistence must replace defaults with the restored profile");

state.backend = "mtplx";
ctx.refreshLaunchability();
assert.equal(elements.reasoningSelect.value, "medium", "A budget label must not change the submitted reasoning value");
assert.match(reasoningOptions.find(option => option.value === "medium").textContent, /2,048 thinking tokens/);
elements.outputInput.value = "16384";
ctx.refreshLaunchability();
assert.equal(elements.reasoningSelect.value, "medium");
assert.match(reasoningOptions.find(option => option.value === "medium").textContent, /4,096 thinking tokens/);
state.backend = "whallm";
ctx.updateBackend();
assert.equal(elements.reasoningSelect.value, "auto");
ctx.applyProfileRequest(profile);
assert.equal(elements.reasoningSelect.value, "medium", "MTPLX → Whallm → saved oMLX profile keeps canonical values");
assert.equal(reasoningOptions.find(option => option.value === "medium").textContent, "medium");
assert.deepEqual(persisted.at(-1), profile, "Returning from another engine persists canonical reasoning and all restored fields");
assert.deepEqual(reasoningOptions.map(option => option.value), ["auto", "off", "minimal", "low", "medium", "high", "xhigh"]);
assert.throws(() => ctx.applyProfileRequest({...profile, reasoning:"xhigh"}), /saved reasoning level is no longer available/);
assert.throws(() => ctx.applyProfileRequest({...profile, client:"codex"}), /saved reasoning level is no longer available/);
assert.throws(() => ctx.applyProfileRequest({...profile, backend:"whallm", modelId:"flash"}), /saved reasoning level is no longer available/);
console.log("Saved thinking profiles survive engine changes and budget labels; unsupported levels still reject.");
