"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const start = app.indexOf("function runtimeKvLabel(");
const end = app.indexOf("function setRuntimeKvValue(", start);
assert.ok(start >= 0 && end > start);
const elements = {
  omlxKvLabel: {textContent: ""}, omlxKvHint: {textContent: ""},
  omlxEffectiveKv: {hidden:true},
  accelerationSelect: {value: "dflash"}, omlxKv: {value: "q6"},
  dflashVerifySelect: {value: "ddtree"},
};
const ctx = vm.createContext({$: id => elements[id]});
vm.runInContext(app.slice(start, end), ctx);
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
assert.match(html, /id="omlxKvHint"/);
assert.match(app, /const kv = runtimeKvLabel\(request.backend, options\)/);
console.log("DFlash KV controls preserve Q4/Q6/Q8 selection and explain DDTree incompatibility.");
