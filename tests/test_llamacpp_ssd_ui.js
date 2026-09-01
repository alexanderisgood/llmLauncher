"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const index = fs.readFileSync(path.join(root, "index.html"), "utf8");
const styles = fs.readFileSync(path.join(root, "styles.css"), "utf8");

const primaryStart = index.indexOf('id="backendChoices"');
const ssdStart = index.indexOf('id="ssdRuntimeDisclosure"');
const ssdEnd = index.indexOf("</details>", ssdStart);
assert.ok(primaryStart >= 0 && ssdStart > primaryStart && ssdEnd > ssdStart);
assert.doesNotMatch(index.slice(primaryStart, ssdStart), /data-backend="llamacpp"/);
const ssdMarkup = index.slice(ssdStart, ssdEnd);
assert.match(ssdMarkup, /<strong>Huge models on SSD<\/strong><small>Model-specific routes<\/small>/);
assert.match(ssdMarkup, /data-backend="llamacpp"[^>]*hidden disabled/);
assert.match(ssdMarkup, /<strong>llama\.cpp · SSD PLE<\/strong><small>Pinned Flash-Next · 8K<\/small>/);
assert.match(index, /id="llamacppControls"[^]*Qualified Qwen3\.8 Flash-Next route[^]*fixed 8K contract[^]*not a generic SSD-streaming mode/);
assert.match(styles, /\.ssd-runtime-choices \.ssd-ple-choice\{grid-column:1\/-1/);

const visibleStart = app.indexOf("function uiEngineVisible");
const visibleEnd = app.indexOf("\nfunction uiRequestVisible", visibleStart);
assert.ok(visibleStart >= 0 && visibleEnd > visibleStart);
const visibleContext = {
  state: {adapters: {engines: []}},
  uiFeatureEnabled: () => false,
};
vm.createContext(visibleContext);
vm.runInContext(app.slice(visibleStart, visibleEnd), visibleContext);
assert.equal(visibleContext.uiEngineVisible("llamacpp"), false);
visibleContext.state.adapters.engines.push({id: "llamacpp", label: "llama.cpp · SSD PLE"});
assert.equal(visibleContext.uiEngineVisible("llamacpp"), true);

const modelStart = app.indexOf("function llamaCppPleCapabilityQualified");
const modelEnd = app.indexOf("\nfunction clientName", modelStart);
assert.ok(modelStart >= 0 && modelEnd > modelStart);
const modelContext = {state: {models: []}};
vm.createContext(modelContext);
vm.runInContext(app.slice(modelStart, modelEnd), modelContext);
modelContext.state.models = [{
  ready: true,
  backends: {llamacpp: {runnable: true, contextWindows: [4096]}},
}];
assert.equal(modelContext.llamaCppPleModel(), null);
modelContext.state.models[0].backends.llamacpp.contextWindows = [4096, 8192];
assert.equal(modelContext.llamaCppPleModel(), null);
const qualified = {
  id: "qwen-flash-next-ple",
  ready: true,
  backends: {llamacpp: {
    runnable: true,
    llamacppPle: true,
    atomicPle: {ready: true},
    receiptFingerprint: "a".repeat(64),
    contextWindows: [8192],
  }},
};
modelContext.state.models.push(qualified);
assert.equal(modelContext.llamaCppPleModel().id, qualified.id);
qualified.backends.llamacpp.receiptFingerprint = "not-a-receipt";
assert.equal(modelContext.llamaCppPleModel(), null);
qualified.backends.llamacpp.receiptFingerprint = "a".repeat(64);
qualified.backends.llamacpp.runnable = false;
assert.equal(modelContext.llamaCppPleModel(), null);

assert.match(app, /if \(\["whallm", "llamacpp"\]\.includes\(state\.backend\)\) \{\s*return \{acceleration:"off", depth:1, kv:"off"\};/);
assert.match(app, /const qualifiedPle = button\.dataset\.backend !== "llamacpp" \|\| Boolean\(llamaCppPleModel\(\)\)/);
assert.match(app, /filter\(backend => backend !== "llamacpp"\)/);
assert.match(app, /if \(backend === "llamacpp"\) return \[\{\s*id:"ar", label:"SSD PLE", available:llamaCppPleCapabilityQualified\(cap\)/);
assert.match(app, /if \(backend === "llamacpp" && !llamaCppPleQualified\(model\)\) continue/);
assert.match(app, /state\.backend !== "llamacpp" \|\| llamaCppPleQualified\(model\)/);
assert.match(app, /capability\?\.llamacppPle === true[^]*capability\?\.atomicPle\?\.ready === true[^]*\^\[0-9a-f\]\{64\}\$\/\.test\(capability\.receiptFingerprint\)/);
assert.match(app, /llamacpp:"llama\.cpp · SSD PLE"/);

console.log("Dedicated, controller-qualified llama.cpp SSD PLE UI passed.");
