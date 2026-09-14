"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../app.js"), "utf8");
const html = fs.readFileSync(path.join(__dirname, "../index.html"), "utf8");
const start = source.indexOf("function renderBenchmarkLiveTps(");
const end = source.indexOf("function renderBenchmarkStatus(", start);
assert.ok(start >= 0 && end > start);
assert.match(html, /id="benchmarkLiveTps"/);
assert.match(source.slice(end, source.indexOf("async function", end)), /renderBenchmarkLiveTps\(status\)/);
const field = {textContent:"", title:"", hidden:true,
  classList:{toggle(_name, hidden) {field.hidden = hidden;}}};
const context = vm.createContext({$:() => field,
  finiteMetric:value => typeof value === "number" && Number.isFinite(value) ? value : null});
vm.runInContext(source.slice(start, end), context);
const liveMetric = {decodeTokensPerSecond:24.25, backendLabel:"MTPLX", modeLabel:"Default MTP", stageLabel:"Cold turn"};
for (const phase of ["queued", "cooldown", "starting", "running", "stopping"]) {
  context.renderBenchmarkLiveTps({phase, liveMetric});
  assert.equal(field.hidden, false);
  assert.equal(field.textContent, "Last completed turn · 24.3 tok/s");
  assert.equal(field.title, "MTPLX · Default MTP · Cold turn");
}
context.renderBenchmarkLiveTps({phase:"running", liveMetric:null});
assert.equal(field.textContent, "Measuring…", "A newly loaded route must not inherit another route's TPS");
for (const phase of ["completed", "failed", "cancelled", "idle"]) {
  context.renderBenchmarkLiveTps({phase, liveMetric});
  assert.equal(field.hidden, true);
  assert.equal(field.textContent, "");
  assert.equal(field.title, "");
}
console.log("Benchmark Lab retains accurately labelled last-turn TPS between requests and clears it across routes.");
