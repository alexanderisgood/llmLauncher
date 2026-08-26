"use strict";

const assert = require("node:assert/strict");
const decisions = require("../calibration_decision.js");

assert.equal(decisions.summary({backendLabel:"oMLX", trusted:true}), "oMLX is fastest");
assert.equal(
  decisions.summary({backendLabel:"oMLX", engineChanged:true}),
  "Leading engines tied — use oMLX",
);
assert.equal(
  decisions.summary({backendLabel:"MTPLX", engineChanged:false}),
  "No clear winner — keep MTPLX",
);
assert.equal(decisions.applyLabel({backendLabel:"oMLX"}), "Apply result · oMLX");

const tiedSwitch = {backend:"omlx", engineChanged:true};
assert.equal(decisions.resultBadge(tiedSwitch, {backend:"omlx", leading:true}, 0), "Recommended");
assert.equal(decisions.resultBadge(tiedSwitch, {backend:"lmstudio", leading:true}, 1), "Tied leader");
assert.equal(decisions.resultBadge(tiedSwitch, {backend:"mtplx", leading:false}, 2), "#3");
assert.equal(
  decisions.resultBadge({backend:"mtplx", engineChanged:false}, {backend:"mtplx", leading:true}, 2),
  "Kept · within 3%",
);

console.log("Calibration result labels distinguish winners, tied leaders, and applied routes.");
