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
assert.match(app, /CalibrationDecision\.receiptSuite\(\s*state\.client,\s*state\.backend === "omlx" && selectedModel\(\)\?\.qwen4Ple\?\.supported === true/);
assert.match(app, /actionId:qwenPleQualification \? "measure-qualification" : "rerun-lab"/);
assert.match(app, /actionId:qwenPleQualification\s*\? "measure-qualification"/);
assert.match(app, /calibrationBenchmarkActive\(\)\s*\|\| state\.calibrationLoading/);
assert.match(app, /state\.calibrationLoading = true;\s*state\.calibrationPlan = null;\s*\$\("calibrationStatus"\)/);
assert.match(app, /state\.calibrationStarting = true/);
assert.match(app, /\|\| state\.calibrationStarting/);
assert.match(index, /id="calibrationDialogSubtitle"/);
assert.match(index, /id="calibrationPreferenceLabel"/);

console.log("Qwen PLE single-route qualification has distinct, non-shootout UI semantics.");
