"use strict";
const launchSources=require("./helpers/launch_sources.js");

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const app = launchSources.controllerSource;
const start = app.indexOf("function runtimeKvLabel(");
const end = app.indexOf("function setRuntimeKvValue(", start);
assert.ok(start >= 0 && end > start);
const elements = {
  omlxKvLabel: {textContent: ""}, omlxKvHint: {textContent: ""},
  omlxEffectiveKv: {hidden:true},
  accelerationSelect: {value: "dflash"}, omlxKv: {value: "q6", options:["off","q4","q6","q8"].map(value=>({value}))},
  dflashVerifySelect: {value: "ddtree"},
};
const ctx = vm.createContext({$: id => elements[id],state:{backend:"omlx"},selectedModel:()=>({})});
launchSources.runInContext(app.slice(start, end), ctx);
for (const verifier of ["adaptive", "dflash", "ddtree"]) {
  for (const kv of ["off", "q4", "q6", "q8"]) {
    const options = Object.freeze({acceleration:"dflash", dflashVerify:verifier, kv});
    const name = kv === "off" ? "Full" : kv.toUpperCase();
    const expected = kv === "off" ? "Full" : verifier === "ddtree"
      ? `${name} · incompatible with DDTree` : `${name} (DFlash)`;
    assert.equal(ctx.runtimeKvLabel("omlx", options), expected);
    assert.equal(ctx.runtimeKvLabel("mtplx", options), name);
    elements.dflashVerifySelect.value = verifier;
    elements.omlxKv.value = kv;
    elements.accelerationSelect.value = "dflash";
    ctx.updateOmlxKvControl();
    assert.equal(elements.omlxKv.hidden, false);
    assert.equal(elements.omlxKvLabel.textContent, "KV cache");
    assert.equal(elements.omlxKv.value, kv);
    assert.match(elements.omlxKvHint.textContent, verifier === "ddtree"
      ? /DDTree requires full precision/ : /retain prefix reuse/);
    assert.equal(elements.omlxEffectiveKv.hidden, kv === "off");
    if (kv !== "off") assert.match(elements.omlxEffectiveKv.textContent,
      verifier === "ddtree" ? /Choose Adaptive or Fixed/ : new RegExp(`DFlash cache: ${name}`));
    elements.accelerationSelect.value = "off";
    ctx.updateOmlxKvControl();
    assert.equal(elements.omlxEffectiveKv.hidden, true);
    assert.equal(elements.omlxKv.value, kv);
  }
}
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const kvValueStart = app.indexOf("function runtimeKvValue(");
const kvValueContext = vm.createContext({state:{backend:"kolibri"},
  $:id=>({value:{kolibriKv:"q4",slotstreamKv:"q8",omlxKv:"q6",mtplxKv:"off"}[id]})});
launchSources.runInContext(app.slice(kvValueStart,start),kvValueContext);
assert.equal(kvValueContext.runtimeKvValue(),"q4","Kolibri evidence must use the selected KV precision");
assert.equal(kvValueContext.runtimeKvValue("slotstream"),"q8");
assert.equal(kvValueContext.runtimeKvValue("omlx"),"q6");
assert.equal(kvValueContext.runtimeKvValue("splash"),"off");
assert.match(html, /id="omlxKvHint"/);
assert.match(app, /kvLabel:runtimeKvLabel/);
assert.match(fs.readFileSync(require.resolve("../saved_launches.js"),"utf8"), /const kv = kvLabel\(request.backend, options\)/);
console.log("DFlash KV controls preserve Q4/Q6/Q8 selection and explain DDTree incompatibility.");

ctx.selectedModel=()=>({omlxExpertOffload:{supported:true}});
ctx.updateOmlxKvControl();
assert.ok(elements.omlxKv.options.filter(o=>o.value!=="off").every(o=>o.disabled));
assert.match(elements.omlxKvHint.textContent,/full-precision QSA/);
ctx.selectedModel=()=>({});
ctx.updateOmlxKvControl();
assert.ok(elements.omlxKv.options.every(o=>!o.disabled));
