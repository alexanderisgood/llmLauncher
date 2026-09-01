"use strict";

const assert = require("node:assert/strict");
const decisions = require("../calibration_decision.js");

assert.equal(decisions.summary({backendLabel:"oMLX", trusted:true}), "oMLX is fastest");
assert.equal(
  decisions.summary({backendLabel:"oMLX", qualified:true, evidenceTier:"local-route-qualification"}),
  "oMLX route qualified",
);
assert.equal(
  decisions.summary({backendLabel:"oMLX", engineChanged:true}),
  "Leading engines tied — use oMLX",
);
assert.equal(
  decisions.summary({backendLabel:"MTPLX", engineChanged:false}),
  "No clear winner — keep MTPLX",
);
assert.equal(decisions.applyLabel({backendLabel:"oMLX"}), "Apply result · oMLX");
assert.equal(
  decisions.applyLabel({backendLabel:"oMLX", qualified:true, tier:"local-route-qualification"}),
  "Use qualified route · oMLX",
);

const tiedSwitch = {backend:"omlx", engineChanged:true};
assert.equal(decisions.resultBadge(tiedSwitch, {backend:"omlx", leading:true}, 0), "Recommended");
assert.equal(decisions.resultBadge(tiedSwitch, {backend:"lmstudio", leading:true}, 1), "Tied leader");
assert.equal(decisions.resultBadge(tiedSwitch, {backend:"mtplx", leading:false}, 2), "#3");
assert.equal(
  decisions.resultBadge({backend:"mtplx", engineChanged:false}, {backend:"mtplx", leading:true}, 2),
  "Kept · within 3%",
);
assert.equal(
  decisions.resultBadge(
    {backend:"omlx", qualified:true, evidenceTier:"local-route-qualification"},
    {backend:"omlx"}, 0,
  ),
  "Qualified",
);
assert.equal(decisions.receiptSuite("chat", false), "standard");
assert.equal(decisions.receiptSuite("chat", true), "agentic");
assert.equal(decisions.receiptSuite("pi", false), "agentic");

console.log("Calibration result labels distinguish winners, tied leaders, and applied routes.");
