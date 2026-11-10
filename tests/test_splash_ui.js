"use strict";
const benchmarkSources = require("./helpers/benchmark_sources.js");
// Pins the launcher UI surface for the first-class Splash engine: the engine
// button, its control panel, the option plumbing and the fixed-value helpers.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..");
const app = benchmarkSources.controllerSource;
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");

// Engine selector and per-engine controls exist.
assert.match(html, /data-backend="splash"/);
assert.match(html, /id="splashControls"/);
assert.match(app, /\$\("splashControls"\)\.classList\.toggle\("hidden", state\.backend !== "splash"\)/);
assert.match(app, /splash:"Splash · local models \+ DFlash2"/);

// The route catalog and option plumbing know the engine.
assert.match(app, /"whallm", "slotstream", "splash", "strata", "llamacpp", "kolibri"\]\)/);
assert.match(app, /splash: \[\],\n  strata: \[\],\n  rec: \[\],\n  llamacpp: \[\],/);
assert.match(app, /slotstream:model\.backends\?\.slotstream\?\.kvChoices \|\| \["off"\], splash:\["off"\]/);
assert.match(html, /id="splashAccelerationSelect"[^>]*>.*value="dspine"/);
assert.match(app, /\["lmstudio", "uzu", "freetoken", "swiftlm", "mference", "whallm", "splash", "strata", "rec", "llamacpp"\]\.includes\(backend\)/);
assert.match(app, /splash:"Splash", strata:"Strata", rec:"Rec", llamacpp:"llama\.cpp · SSD PLE"/);

// The engine status explains source support when no compatible model is present.
assert.match(app, /state\.backend === "splash"[\s\S]{0,400}Install Splash 1\.5\.0/);
assert.match(html, /Flash-Next requires GGUF/);
assert.match(html, /split GGUFs and Q2_0 are supported/);
assert.match(html, /GGUF quantizations, including Q6_K/);
assert.match(html, /MLX checkpoints must be affine 4-bit/);

const {reconcileRuntimeLimits} = require('../route_preferences.js');
for (const output of [65536, 131072]) {
  assert.equal(reconcileRuntimeLimits({context:262144, output,
    contextWindows:[16384,32768,65536,131072,262144], outputMaximum:261120}).output, output);
}
assert.match(app, /Splash thinking has an enforced token ceiling/);

const {harness} = require("./helpers/launch_workspace_harness.js");
const h = harness();
h.model.nativeContext = 262144;
h.model.backends.splash = {...h.model.backends.splash, dspine:true, dspineContext:262144,
  dspineContexts:[2048, 16384, 32768, 65536, 131072, 262144], dspineOutput:4096};
h.nodes.contextInput.dispatchEvent = event => h.nodes.contextInput.dispatch(event.type);
const select = h.nodes.splashAccelerationSelect;
select.value = "off";
select.options = ["off", "dspine"].map(value => ({value}));
select.querySelector = selector => select.options.find(option => selector.includes(`"${option.value}"`));
h.controller.initialize();
h.controller.useModelInventory([h.model]);
h.controller.setBackend("splash");
h.controller.updateBackend();
h.nodes.outputInput.value = "4096";
assert.equal(select.options[1].disabled, false);
select.value = "dspine";
select.dispatch("change");
h.nodes.contextSelect.value = "262144";
h.nodes.contextSelect.dispatch("change");
h.nodes.reasoningSelect.value = "low";
const omp = h.collections.clientButtons.find(button => button.dataset.client === "omp");
assert.equal(omp.disabled, false);
omp.dispatch("click");
const request = h.controller.gather("custom", false);
assert.equal(request.options.acceleration, "dspine");
assert.equal(request.context, 262144);
assert.equal(request.output, 4096);
assert.equal(request.reasoning, "low");
assert.equal(request.client, "omp");
assert.equal(request.generation.temperature, 0);
assert.equal(h.controller.limitError(), "");
select.value = "off";
select.dispatch("change");
assert.equal(h.controller.gatherOptions().acceleration, "off");
assert.equal(h.nodes.contextInput.value, "16384");
assert.equal(h.nodes.outputInput.value, "4096");
h.model.backends.splash.dspine = false;
h.controller.useModelInventory([h.model]);
h.controller.modelChanged();
assert.equal(select.options[1].disabled, true);

console.log("Splash UI wiring passed");
