"use strict";

const assert = require("node:assert/strict");
const routes = require("../route_preferences.js");

assert.deepEqual(routes.normaliseRoute({backend:" OMLX ", modelId:" model-a ", client:" CHAT "}), {
  backend:"omlx", modelId:"model-a", client:"chat",
});
assert.equal(routes.normaliseRoute({backend:"unknown", modelId:"model-a", client:"chat"}), null);
assert.equal(routes.normaliseRoute({backend:"omlx", modelId:"", client:"chat"}), null);
assert.equal(routes.normaliseRoute({backend:"omlx", modelId:"model-a", client:"browser"}), null);
assert.equal(routes.normaliseRoute({backend:"omlx", modelId:"x".repeat(routes.MAX_MODEL_ID + 1), client:"chat"}), null);
assert.deepEqual(routes.normaliseRoute({backend:"whallm", modelId:"qwen-full", client:"chat"}), {
  backend:"whallm", modelId:"qwen-full", client:"chat",
});
assert.deepEqual(routes.normaliseRoute({backend:"llamacpp", modelId:"qwen-flash-next-ple", client:"chat"}), {
  backend:"llamacpp", modelId:"qwen-flash-next-ple", client:"chat",
});

const values = new Map();
const storage = {
  getItem:key => values.get(key) || null,
  setItem:(key, value) => values.set(key, value),
};
assert.equal(routes.readRoute(storage), null);
assert.deepEqual(routes.writeRoute(storage, {
  backend:"omlx", modelId:"model-a", client:"chat", project:"/private/work", reasoning:"high",
}), {
  route:{backend:"omlx", modelId:"model-a", client:"chat"}, stored:true,
});
assert.deepEqual(JSON.parse(values.get(routes.STORAGE_KEY)), {
  version:1, backend:"omlx", modelId:"model-a", client:"chat",
});
assert.deepEqual(routes.readRoute(storage), {backend:"omlx", modelId:"model-a", client:"chat"});
values.set(routes.STORAGE_KEY, "not json");
assert.equal(routes.readRoute(storage), null);
values.set(routes.STORAGE_KEY, JSON.stringify({version:2, backend:"omlx", modelId:"model-a", client:"chat"}));
assert.equal(routes.readRoute(storage), null);

const blockedStorage = {
  getItem() { throw new Error("blocked"); },
  setItem() { throw new Error("blocked"); },
};
assert.equal(routes.readRoute(blockedStorage), null);
assert.deepEqual(routes.writeRoute(blockedStorage, {backend:"mtplx", modelId:"model-b", client:"pi"}), {
  route:{backend:"mtplx", modelId:"model-b", client:"pi"}, stored:false,
});

const available = [
  {backend:"mtplx", modelId:"model-fast", client:"opencode"},
  {backend:"mtplx", modelId:"model-fast", client:"chat"},
  {backend:"omlx", modelId:"model-a", client:"chat"},
];
assert.deepEqual(routes.selectInitialRoute({
  preference:{backend:"omlx", modelId:"model-a", client:"chat"},
  current:{backend:"mtplx", modelId:"model-fast", client:"pi"},
  routes:available,
}), {backend:"omlx", modelId:"model-a", client:"chat", source:"remembered"});
assert.deepEqual(routes.selectInitialRoute({
  preference:{backend:"lmstudio", modelId:"missing", client:"pi"},
  current:{backend:"mtplx", modelId:"model-fast", client:"pi"},
  routes:available,
}), {backend:"mtplx", modelId:"model-fast", client:"opencode", source:"current-fallback"});
assert.deepEqual(routes.selectInitialRoute({
  preference:{backend:"lmstudio", modelId:"missing", client:"pi"},
  current:{backend:"mtplx", modelId:"missing", client:"pi"},
  routes:[{backend:"omlx", modelId:"model-a", client:"chat"}],
}), {backend:"omlx", modelId:"model-a", client:"chat", source:"available"});
assert.equal(routes.selectInitialRoute({routes:[]}), null);
assert.equal(routes.availableRoutes([available[0], available[0], {bad:true}]).length, 1);
assert.equal(routes.isRouteAvailable(available[1], available), true);
assert.equal(routes.isRouteAvailable({backend:"mtplx", modelId:"model-fast", client:"pi"}, available), false);

assert.deepEqual(routes.reconcileRuntimeLimits({
  context:131072, output:16384, contextWindows:[4096, 8192, 16384],
}), {
  context:16384, output:15360, contextChanged:true, outputChanged:true, promptBudget:1024,
});
assert.deepEqual(routes.reconcileRuntimeLimits({
  context:16384, output:16384, contextWindows:[4096, 8192, 16384],
}), {
  context:16384, output:15360, contextChanged:false, outputChanged:true, promptBudget:1024,
});
assert.deepEqual(routes.reconcileRuntimeLimits({
  context:16384, output:8192, contextWindows:[16384, 4096, 8192, 8192],
}), {
  context:16384, output:8192, contextChanged:false, outputChanged:false, promptBudget:8192,
});
assert.deepEqual(routes.reconcileRuntimeLimits({
  context:4096, output:128, contextWindows:[4096],
}), {
  context:4096, output:128, contextChanged:false, outputChanged:false, promptBudget:3968,
});

console.log("Safe visible-route persistence and installed-route fallback passed.");

assert.deepEqual(routes.reconcileRuntimeLimits({
  context:131072, output:16384, contextWindows:[16384], outputMaximum:4096,
}), {
  context:16384, output:4096, contextChanged:true, outputChanged:true, promptBudget:12288,
});
assert.deepEqual(routes.reconcileRuntimeLimits({
  context:16384, output:2048, contextWindows:[16384], outputMaximum:4096,
}), {
  context:16384, output:2048, contextChanged:false, outputChanged:false, promptBudget:14336,
});

const savedRoute = {backend:"mtplx", modelId:"model-fast", client:"chat"};
assert.equal(routes.writeSetup(storage, savedRoute, {
  contextInput:"65536", outputInput:"16384", reasoningSelect:"auto",
  fanSelect:"default", profileSelect:"turbo", mtplxKv:"off",
  systemPrompt:"private instructions", projectPath:"/private/work", apiKey:"secret",
  experimentalConsent:"true", temperatureInput:true,
}), true);
const setup = routes.readSetup(storage, savedRoute);
assert.deepEqual(setup.controls, {
  contextInput:"65536", outputInput:"16384", reasoningSelect:"auto",
  profileSelect:"turbo", fanSelect:"default", mtplxKv:"off",
});
assert.doesNotMatch(values.get(routes.MODEL_SETTINGS_KEY), /private|secret|Consent/);
assert.equal(routes.readSetup(storage, {...savedRoute, modelId:"other"}), null);
assert.equal(routes.readSetup(storage, {...savedRoute, backend:"omlx"}), null);
assert.deepEqual(routes.readSetup(storage, {...savedRoute, client:"pi"}), setup);
assert.equal(routes.writeSetup(blockedStorage, savedRoute, setup.controls), false);
assert.equal(routes.readSetup(blockedStorage, savedRoute), null);
values.set(routes.MODEL_SETTINGS_KEY, JSON.stringify({...setup, version:3}));
assert.equal(routes.readSetup(storage, savedRoute), null);
values.set(routes.SETUP_STORAGE_KEY, "x".repeat(8193));
assert.equal(routes.readSetup(storage, savedRoute), null);
console.log("Exact-route context, sampling and runtime controls persist without prompts, credentials or approvals.");

const strataRoute = {backend:"strata", modelId:"strata-qwen-flash-next", client:"omp"};
assert.equal(routes.writeRoute(storage, strataRoute).stored, true);
assert.equal(routes.writeSetup(storage, strataRoute, {contextInput:"262144", outputInput:"65536"}), true);
assert.deepEqual(routes.readRoute(storage), strataRoute);
assert.deepEqual(routes.selectInitialRoute({preference:routes.readRoute(storage), routes:[...available,strataRoute]}),
  {...strataRoute,source:"remembered"});
assert.deepEqual(routes.readSetup(storage, strataRoute).controls, {contextInput:"262144",outputInput:"65536"});
assert.deepEqual(routes.reconcileRuntimeLimits({context:262144,output:65536,contextWindows:[16384,32768,65536,131072,262144],outputMaximum:261120}),
  {context:262144,output:65536,contextChanged:false,outputChanged:false,promptBudget:196608});
console.log("Strata context and response settings survive route persistence.");
const legacyRoute = {...savedRoute, modelId:"legacy-model"};
values.set(routes.SETUP_STORAGE_KEY, JSON.stringify({version:1, route:legacyRoute, controls:{outputInput:"4567"}}));
const secondEngine = {...strataRoute, backend:"splash"};
assert.equal(routes.writeSetup(storage, secondEngine, {contextInput:"131072", outputInput:"12000"}), true);
assert.equal(routes.readSetup(storage, strataRoute).controls.outputInput, "65536");
assert.equal(routes.readSetup(storage, secondEngine).controls.outputInput, "12000");
assert.equal(routes.readSetup(storage, legacyRoute).controls.outputInput, "4567");
console.log("Settings stay separate by model and runtime, with legacy settings still readable.");
