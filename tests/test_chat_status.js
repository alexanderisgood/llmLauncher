"use strict";

const assert = require("assert");
const core = require("../chat_status.js");

assert.equal(core.requestTps({}), null);
assert.equal(core.requestTps({runSeconds:1.2}), null, "timing must not become TPS");
assert.equal(core.requestTps({decodeTokensPerSecond:-1}), null, "negative TPS is invalid");
assert.equal(core.requestTps({decodeTokensPerSecond:"42"}), null, "coerced text is not authoritative TPS");
assert.deepEqual(core.requestTps({decodeTokensPerSecond:42, endToEndTokensPerSecond:30}), {
  decode:42, endToEnd:30, primary:42, primaryKind:"decode",
  compact:"42.0 decode · 30.0 end-to-end",
  label:"42.0 tok/s decode · 30.0 tok/s end-to-end",
});
assert.deepEqual(core.requestTps({
  runtimeStatsSource:"lmstudio-response-stats", runtimeTokensPerSecond:51.4371,
  decodeTokensPerSecond:49, endToEndTokensPerSecond:35,
}), {
  decode:49, endToEnd:35, runtime:51.4371,
  primary:51.4371, primaryKind:"runtime",
  compact:"51.4 tok/s engine",
  label:"51.4 tok/s · LM Studio reported",
});
assert.equal(core.requestTps({
  runtimeStatsSource:"unknown", runtimeTokensPerSecond:99,
}), null, "unidentified runtime stats must fail closed");
assert.deepEqual(core.requestTps({
  state:"running", liveTelemetry:{source:"mtplx-flight", tokensPerSecond:45.25},
}), {
  decode:null, endToEnd:null, primary:45.25, primaryKind:"live",
  compact:"45.3 tok/s live",
  label:"45.3 tok/s live · MTPLX flight telemetry",
});
assert.deepEqual(core.requestTps({
  state:"running", liveTelemetry:{
    source:"omlx-activity", metricKind:"decode", tokensPerSecond:52,
  },
}), {
  decode:null, endToEnd:null, primary:52, primaryKind:"live",
  compact:"52.0 tok/s live",
  label:"52.0 tok/s live · oMLX activity telemetry",
});
assert.deepEqual(core.requestTps({
  state:"running", liveTelemetry:{
    source:"omlx-activity", metricKind:"prefill", tokensPerSecond:1200,
  },
}), {
  decode:null, endToEnd:null, primary:1200, primaryKind:"live-prefill",
  compact:"1200.0 tok/s prefill",
  label:"1200.0 tok/s live prefill · oMLX activity telemetry",
});
assert.equal(core.requestTps({
  state:"running", liveTelemetry:{source:"unknown", tokensPerSecond:99},
}), null, "unknown live telemetry must fail closed");
assert.equal(core.requestTps({
  state:"queued", liveTelemetry:{source:"mtplx-flight", tokensPerSecond:99},
}), null, "queued telemetry must never look live");

let summary = core.activitySummary({
  engineResident:true,
  active:[{surfaceId:"chat-1", state:"running"}],
  queued:[], recent:[],
}, "chat-1");
assert.deepEqual(summary.speed, {
  value:"Measuring…", state:"measuring",
  title:"TPS is waiting for authoritative runtime usage.",
});
assert.deepEqual(summary.lane, {value:"Generating", state:"running"});

summary = core.activitySummary({
  engineResident:true,
  active:[{surfaceId:"chat-1", state:"running", liveTelemetry:{source:"mtplx-flight", tokensPerSecond:45.25}}],
  queued:[], recent:[],
}, "chat-1");
assert.equal(summary.speed.value, "45.3 tok/s");
assert.equal(summary.speed.state, "measured");
assert.match(summary.speed.title, /MTPLX flight telemetry/);

summary = core.activitySummary({
  engineResident:true, active:[], queued:[],
  recent:[{surfaceId:"chat-1", decodeTokensPerSecond:37.25}],
}, "chat-1");
assert.equal(summary.speed.value, "37.3 tok/s");
assert.equal(summary.speed.state, "measured");
assert.deepEqual(summary.lane, {value:"Idle", state:"idle"});

summary = core.activitySummary({
  engineResident:true, active:[], queued:[],
  recent:[{
    surfaceId:"chat-1", usageReported:true, completionTokens:3,
    tpsSampleQualified:false, tpsSampleMinimumTokens:16,
    decodeTokensPerSecond:null, endToEndTokensPerSecond:null,
  }],
}, "chat-1");
assert.deepEqual(summary.speed, {
  value:"Too short", state:"unknown",
  title:"The last reply had 3 output tokens; at least 16 are required for stable TPS.",
});

summary = core.activitySummary({
  engineResident:true, active:[], queued:[],
  recent:[
    {surfaceId:"other-1", decodeTokensPerSecond:80},
    {surfaceId:"other-2", decodeTokensPerSecond:79},
    {surfaceId:"other-3", decodeTokensPerSecond:78},
    {surfaceId:"chat-1", decodeTokensPerSecond:36},
  ],
}, "chat-1");
assert.equal(summary.speed.value, "36.0 tok/s", "a selected surface keeps its bounded last measurement");

summary = core.activitySummary({
  engineResident:true, active:[],
  queued:[{surfaceId:"chat-1", state:"queued", queuePosition:2}],
  recent:[{surfaceId:"chat-1", decodeTokensPerSecond:99}],
}, "chat-1");
assert.equal(summary.speed.value, "Not reported", "a queued request must not look like live TPS");
assert.deepEqual(summary.lane, {value:"Queue #2", state:"queued"});

assert.deepEqual(core.cacheSummary({
  state:"confirmed-reuse", engineResident:true,
  lastObservation:{cacheTelemetryReported:true, promptTokens:1000, cachedPromptTokens:375},
}), {value:"38% reused", state:"confirmed-reuse"});
assert.deepEqual(core.cacheSummary({
  state:"reported-no-reuse", engineResident:true,
  lastObservation:{cacheTelemetryReported:true, promptTokens:1000, cachedPromptTokens:0},
}), {value:"No reuse", state:"reported-no-reuse"});
assert.deepEqual(core.cacheSummary({
  state:"telemetry-unavailable", engineResident:true,
  lastObservation:{ttftSeconds:0.2},
}), {value:"Not reported", state:"telemetry-unavailable"}, "lower latency is not cache evidence");
assert.deepEqual(core.cacheSummary({
  state:"telemetry-unavailable", engineResident:true,
  lastObservation:{cacheTelemetryReported:true, promptTokens:1000, cachedPromptTokens:"375"},
}), {value:"Not reported", state:"telemetry-unavailable"}, "coerced cache counters are not evidence");
assert.deepEqual(core.cacheSummary({
  state:"confirmed-reuse", engineResident:true,
  lastObservation:{cacheTelemetryReported:true, promptTokens:1000, cachedPromptTokens:1200},
}), {value:"100% reused", state:"confirmed-reuse"}, "malformed over-reporting stays bounded");

summary = core.contextSummary({promptTokens:849}, 1000);
assert.equal(summary.warning, false);
assert(Math.abs(summary.percent - 84.9) < 1e-9);
assert.deepEqual(core.contextSummary({promptTokens:850}, 1000), {
  warning:true, percent:85, label:"Context 85%",
});
assert.equal(core.contextSummary({promptTokens:990}, 1000, true).warning, false);
assert.equal(core.contextSummary({promptTokens:990}, 0).percent, null);
assert.equal(core.contextSummary({promptTokens:-1}, 1000).percent, null);
assert.equal(core.contextSummary({promptTokens:990}, "1000").percent, null);

console.log("Authoritative compact Chat status summaries passed.");
