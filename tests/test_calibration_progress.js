"use strict";
const benchmarkSources = require("./helpers/benchmark_sources.js");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = benchmarkSources.controllerSource;
const start = source.indexOf("function renderCalibrationBenchmark(");
const end = source.indexOf("\nfunction renderCalibration()", start);
assert.ok(start >= 0 && end > start);
const fields = new Map();
function field(id) {
  if (!fields.has(id)) fields.set(id, {
    textContent:"", style:{}, classList:{toggle() {}},
    parentElement:{attributes:{}, setAttribute(key, value) {this.attributes[key] = value;}},
  });
  return fields.get(id);
}
const context = {
  state:{calibrationLoading:false, calibrationPlan:{action:"apply-existing", ready:true}},
  $:field, finiteMetric:() => null,
  calibrationBenchmarkActive:status => status.phase === "running",
  calibrationOwnsBenchmark:status => status.owned === true,
};
vm.createContext(context);
benchmarkSources.runInContext(source.slice(start, end), context);
context.renderCalibrationBenchmark({phase:"idle"});
assert.equal(field("calibrationPercent").textContent, "100%");
assert.equal(field("calibrationProgressBar").style.width, "100%");
assert.equal(field("calibrationProgressBar").parentElement.attributes["aria-valuenow"], "100");
assert.equal(field("calibrationPhase").textContent, "Ready to use");

context.renderCalibrationBenchmark({phase:"running", owned:true, progress:0.25});
assert.equal(field("calibrationPercent").textContent, "25%", "An active retest keeps real progress");
context.renderCalibrationBenchmark({phase:"failed", owned:true, progress:0.5});
assert.equal(field("calibrationPercent").textContent, "50%", "Failed retests must not look complete");
context.state.calibrationPlan = {action:"measure", ready:true};
context.renderCalibrationBenchmark({phase:"idle"});
assert.equal(field("calibrationPercent").textContent, "0%");
context.state.calibrationPlan = {action:"apply-existing", ready:true};
context.state.calibrationLoading = true;
context.renderCalibrationBenchmark({phase:"idle"});
assert.equal(field("calibrationPercent").textContent, "0%", "An unverified loading state stays distinct");
console.log("Saved calibration progress is complete; active, failed and unmeasured runs retain truthful progress.");
