"use strict";
// Synthetic transcript only. No model, browser, network, or user files.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const {performance} = require("node:perf_hooks");
const source = path.resolve(process.argv[2] || path.join(__dirname, "../pi_timeline.js"));
let encodedBytes = 0;
class MeasuredEncoder extends TextEncoder {
  encode(value) {
    const result = super.encode(value);
    encodedBytes += result.byteLength;
    return result;
  }
}
const context = vm.createContext({TextEncoder:MeasuredEncoder, TextDecoder, module:{exports:{}}});
vm.runInContext(fs.readFileSync(source, "utf8"), context);
const core = context.module.exports;
function seed() {
  return core.applyTimelineEnvelope(core.emptyTimeline(), {
    timelineVersion:1, timelineReset:true, timelineBaseRevision:1,
    timelineRevision:400, nextTimelineRevision:400,
    timelineEvents:Array.from({length:400}, (_, index) => ({
      revision:index + 1, kind:"answer", itemId:`item-${index}`, operation:"replace",
      text:"Measured synthetic history. ".repeat(42), title:"Pi",
      createdAt:"2026-09-07T00:00:00.000Z",
    })),
  }).state;
}
const results = {};
for (const scenario of ["idle", "streaming"]) {
  let state = seed();
  const startBytes = encodedBytes, start = performance.now();
  for (let i = 0; i < 200; i++) {
    const revision = 400 + (scenario === "streaming" ? i + 1 : 0);
    state = core.applyTimelineEnvelope(state, {
      timelineVersion:1, timelineReset:false, timelineBaseRevision:1,
      timelineRevision:revision, nextTimelineRevision:revision,
      timelineEvents:scenario === "idle" ? [] : [{
        revision, kind:"answer", itemId:"item-399", operation:"append", text:" next",
      }],
    }).state;
  }
  results[scenario] = {
    updates:200, milliseconds:Math.round((performance.now() - start) * 100) / 100,
    encodedBytes:encodedBytes - startBytes, retainedItems:state.items.length,
  };
}
console.log(JSON.stringify(results, null, 2));
