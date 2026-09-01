"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const index = fs.readFileSync(path.join(root, "index.html"), "utf8");

assert.match(app, /plan\.routeQualification\) request\.scope = "qualification"/);
assert.match(app, /"Route Qualification"/);
assert.match(app, /"Qualify route"/);
assert.match(app, /"Route qualification result"/);
assert.match(app, /local-route-qualification/);
assert.match(app, /Authoritative usage, generation TPS, time to first output/);
assert.match(app, /actionId:"measure-qualification"/);
assert.match(app, /action === "measure-qualification"\) return openCalibrationAssistant/);
assert.match(app, /const qwenPleQualification = state\.backend === "omlx"/);
assert.match(app, /memoryGuard:\s*"memoryGuardSelect"/);
assert.match(app, /memoryGuardSelect"\)\.addEventListener\("change", \(\) => \{\s*\/\/[^]*?if \(!state\.applyingOptimal\) \{\s*cancelOptimization\("Memory mode changed; reapply to refresh the benchmark match\."\);/);
assert.match(app, /"Prepare safe test"/);
assert.match(app, /dataset\.action = canPrepare \? "prepare" : "measure"/);
assert.match(app, /async function prepareQwenRouteQualification\(\)/);
assert.match(app, /preparation\.doesNotChangeMacOS !== true/);
assert.match(app, /macOS was not changed/);
assert.match(app, /dataset\.action === "prepare"/);
assert.match(app, /CalibrationDecision\.receiptSuite\(\s*state\.client,\s*state\.backend === "omlx" && selectedModel\(\)\?\.qwen4Ple\?\.supported === true/);
assert.match(app, /actionId:qwenPleQualification \? "measure-qualification" : "rerun-lab"/);
assert.match(app, /actionId:qwenPleQualification\s*\? "measure-qualification"/);
assert.match(app, /calibrationBenchmarkActive\(\)\s*\|\| state\.calibrationLoading/);
assert.match(app, /state\.calibrationLoading = true;\s*state\.calibrationPlan = null;\s*\$\("calibrationStatus"\)/);
assert.match(app, /state\.calibrationStarting = true/);
assert.match(app, /\|\| state\.calibrationStarting/);
assert.match(index, /id="calibrationDialogSubtitle"/);
assert.match(index, /id="calibrationPreferenceLabel"/);
assert.match(index, /class="field amber optimizable"[^>]*><span>48 GB memory mode/);

console.log("Qwen PLE single-route qualification has distinct, non-shootout UI semantics.");
