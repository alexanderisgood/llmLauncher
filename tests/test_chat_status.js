"use strict";

const assert = require("assert");
const core = require("../chat_status.js");

const piEstimate = {value:"12.5 tok/s · Pi live", state:"live", title:"Pi token estimate"};
const measuredRequest = {state:"running", liveTelemetry:{source:"mtplx-flight", phase:"decode", tokensPerSecond:26.8}};
assert.equal(core.agentGenerationSpeed(measuredRequest, null, piEstimate, null).value, "26.8 tok/s · engine");
assert.equal(core.agentGenerationSpeed({state:"running"}, null, piEstimate, null).value, "12.5 tok/s · Pi estimate");
assert.equal(core.agentGenerationSpeed(null, {decodeTokensPerSecond:30}, piEstimate, null).value, "30.0 tok/s · last");
assert.equal(core.agentGenerationSpeed({state:"running", liveTelemetry:{source:"omlx-activity", metricKind:"prefill", tokensPerSecond:400}},
  {decodeTokensPerSecond:25}, piEstimate, null).value, "25.0 tok/s · last");
assert.equal(core.agentGenerationSpeed({state:"running", liveTelemetry:{phase:"prefill"}}, null, piEstimate, null).value, "Waiting…");

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
  value:"Awaiting token count", state:"measuring",
  title:"This engine has not reported token usage for the current request yet. Speed appears when that count arrives.",
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
assert.equal(summary.speed.value, "99.0 tok/s · last", "a queued request labels historical TPS explicitly");
assert.deepEqual(summary.lane, {value:"Queue #2", state:"queued"});

summary = core.activitySummary({
  engineResident:true,
  active:[{surfaceId:"pi", state:"running", firstOutputSeconds:1.2}],
  recent:[{surfaceId:"other", decodeTokensPerSecond:99}, {surfaceId:"pi", decodeTokensPerSecond:40.37}],
}, "pi");
assert.equal(summary.speed.value, "40.4 tok/s · last");
assert.match(summary.speed.title, /Last completed model request/);
assert.doesNotMatch(summary.speed.title, /Chat/);
summary = core.activitySummary({active:[{surfaceId:"pi", state:"running", liveTelemetry:{
  source:"omlx-activity", phase:"prefill", metricKind:"prefill", tokensPerSecond:1200,
}}]}, "pi");
assert.equal(summary.speed.value, "1200.0 tok/s prefill", "prefill must not be labeled generation speed");
assert.equal(core.requestPhase({state:"running"}), "Preparing prompt…");
assert.equal(core.requestPhase({state:"running", firstOutputSeconds:0}), "Generating…");
assert.equal(core.requestPhase({state:"running", liveTelemetry:{source:"omlx-activity", phase:"prefill"}}), "Prefilling · reading context…");
assert.equal(core.requestPhase({state:"running", liveTelemetry:{source:"unknown", phase:"prefill"}}), "Preparing prompt…");
assert.equal(core.requestPhase({state:"running", liveTelemetry:{source:"mtplx-flight", phase:"decode", reasoningCharacters:12}}), "Thinking…");
assert.equal(core.requestPhase({state:"completed"}), "");
assert.equal(core.requestPhase(null), "", "transient activity disappears when the request finishes");

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

const promptLast = {usageReported:true, promptTokens:2000, completionTokens:500, firstOutputSeconds:2};
assert.equal(core.promptProcessingSummary(null, promptLast).value, 'Not reported');
assert.match(core.promptProcessingSummary(null, promptLast).title, /cached context/);
assert.equal(core.promptProcessingSummary(null, {...promptLast, firstOutputSeconds:0}).state, 'unknown');
assert.equal(core.promptProcessingSummary(null, {...promptLast, usageReported:false}).state, 'unknown');
assert.equal(core.promptProcessingSummary({state:'running',liveTelemetry:{source:'omlx-activity',metricKind:'prefill',tokensPerSecond:1234}}, promptLast).value, '1234.0 tok/s');
assert.equal(core.promptProcessingSummary({state:'running',liveTelemetry:{source:'omlx-activity',metricKind:'decode',tokensPerSecond:60}}, promptLast).value, 'Waiting…');
const piContext = tokens => ({extensionStatuses:{'launcher.context':{text:JSON.stringify({source:'pi-context-estimate', tokens, contextWindow:10000})}}});
assert.equal(core.agentContextSummary(piContext(2500),10000,null,promptLast).value,'~25.0%');
assert.equal(core.agentContextSummary(piContext(9000),10000).state,'busy');
assert.equal(core.agentContextSummary(piContext(null),10000,null,promptLast).value,'Recalculating…', 'Do not reuse pre-compaction or summarisation usage');
assert.equal(core.agentContextSummary({...piContext(2500),compacting:true},10000).value,'Compacting…');
assert.equal(core.agentContextSummary({},10000,null,promptLast).value,'25.0% · last', 'Context includes output, not only prompt tokens');
assert.equal(core.agentContextSummary({},0,null,promptLast).state,'unknown');
console.log('Hub prompt throughput and compaction-aware context percentage passed');

const nativePrompt = {...promptLast,promptProcessing:{source:'uzu-native-stats', tokensPerSecond:215.7,processedTokens:269,cachedTokens:68273}};
assert.equal(core.promptProcessingSummary(null,nativePrompt).value,'215.7 tok/s · last');
assert.match(core.promptProcessingSummary(null,nativePrompt).title,/cached tokens are excluded/);

const processingNow = Date.parse('2026-09-05T21:00:12Z');
const processingRequest = {state:'running', startedAt:'2026-09-05T21:00:00Z', firstOutputSeconds:null};
assert.equal(core.promptProcessingClock(processingRequest, processingNow), '0:12');
assert.equal(core.promptProcessingClock({...processingRequest, state:'queued'}, processingNow), null);
assert.equal(core.promptProcessingClock({...processingRequest, firstOutputSeconds:0}, processingNow), null);
assert.equal(core.promptProcessingClock({...processingRequest, liveTelemetry:{phase:'decode'}}, processingNow), null);
assert.equal(core.promptProcessingClock({...processingRequest, startedAt:'invalid'}, processingNow), null);
assert.equal(core.promptProcessingClock({...processingRequest, startedAt:'2026-09-05T21:00:10Z'}, processingNow), '0:02');
const nativePrefill = core.promptProcessingSummary({state:'running', promptProcessing:{source:'omlx-dflash-prefill', tokensPerSecond:320.5, processedTokens:641, cachedTokens:39000}}, null);
assert.equal(nativePrefill.value, '320.5 tok/s');
assert.match(nativePrefill.title, /39,000 cached tokens are excluded/);
const tokenBudget = core.agentContextSummary({extensionStatuses:{'launcher.context':{text:JSON.stringify({source:'pi-context-estimate',tokens:40000,contextWindow:131072})}}}, 131072);
assert.equal(tokenBudget.usedTokens,40000);
assert.equal(tokenBudget.totalTokens,131072);
assert.equal(tokenBudget.remainingTokens,91072);
const exceededBudget = core.agentContextSummary({},100,{liveTelemetry:{source:'omlx-activity',contextTokens:120}});
assert.equal(exceededBudget.remainingTokens,0);
assert.equal(core.agentContextSummary({compacting:true},100).remainingTokens,undefined);

const mtplxPrefill = {source:'mtplx-prefill',tokensPerSecond:500,processedTokens:1000,cachedTokens:8000,partial:true};
assert.equal(core.promptProcessingSummary({promptProcessing:mtplxPrefill}, null).value, '500.0 tok/s');
assert.match(core.promptProcessingSummary({promptProcessing:mtplxPrefill}, null).title, /MTPLX.*Latest observed prefill sample/);
assert.equal(core.promptProcessingSummary(null,{promptProcessing:{...mtplxPrefill,partial:false}}).value, '500.0 tok/s · last');

const whallmPrefill = {state:'running', liveTelemetry:{source:'whallm-native-stats',phase:'prefill'}};
const whallmComplete = {state:'completed', runtimeStatsSource:'whallm-native-stats',runtimeTokensPerSecond:10,
  decodeTokensPerSecond:100, promptProcessing:{source:'whallm-prefill',tokensPerSecond:400,processedTokens:2000,cachedTokens:8000}};
assert.equal(core.requestTps(whallmComplete).primary, 10, 'native end-to-end decode supersedes transport timing');
assert.match(core.requestTps(whallmComplete).label, /Whallm.*including cache evaluation/);
assert.equal(core.requestPhase(whallmPrefill), 'Prefilling · reading context…');
assert.equal(core.agentGenerationSpeed(whallmPrefill,whallmComplete,{state:'live',value:'100 tok/s Pi live'},{}).value,'Waiting…');
assert.equal(core.promptProcessingSummary(whallmPrefill,whallmComplete).value,'Waiting…', 'last request speed is hidden while the new prompt is processing');
assert.equal(core.promptProcessingSummary(null,whallmComplete).value,'400.0 tok/s · last');
assert.match(core.promptProcessingSummary(null,whallmComplete).title,/Whallm.*2,000 new prompt tokens; 8,000 cached tokens are excluded/);
assert.equal(core.agentContextSummary({},16384,{liveTelemetry:{source:'whallm-native-stats',contextTokens:8192}}).usedTokens,8192);
console.log('Whallm native prompt/decode attribution and fresh-prefill display passed');

const slotstreamPrompt = {promptProcessing:{source:'slotstream-native-stats',tokensPerSecond:200,processedTokens:100,cachedTokens:3900}};
assert.equal(core.promptProcessingSummary(slotstreamPrompt,null).value,'200.0 tok/s');
assert.match(core.promptProcessingSummary(null,slotstreamPrompt).title,/Slotstream.*3,900 cached tokens are excluded/);
assert.match(core.requestTps({runtimeStatsSource:'slotstream-native-stats',runtimeTokensPerSecond:16}).label,/Slotstream native decode/);
assert.match(core.promptProcessingSummary(slotstreamPrompt,null).title,/excludes decode and cached tokens/);

const omlxNative = {runtimeStatsSource:'omlx-native-stats',runtimeTokensPerSecond:2.6,
  promptProcessing:{source:'omlx-native-stats',tokensPerSecond:1.4,processedTokens:28,cachedTokens:0}};
assert.equal(core.requestTps(omlxNative).primary,2.6);
assert.match(core.requestTps(omlxNative).label,/oMLX native decode/);

const kolibriNative = {runtimeStatsSource:'kolibri-native-stats',runtimeTokensPerSecond:8.6,
  decodeTokensPerSecond:24.08,promptProcessing:{source:'kolibri-native-stats',
    tokensPerSecond:31.38,processedTokens:1121,cachedTokens:0}};
assert.equal(core.requestTps(kolibriNative).primary,8.6,'native tool generation timing supersedes buffered relay timing');
assert.match(core.requestTps(kolibriNative).label,/Kolibri native decode/);
assert.match(core.promptProcessingSummary(null,kolibriNative).title,/Kolibri/);
const splashNative={backend:'splash',runtimeStatsSource:'splash-native-stats',runtimeTokensPerSecond:78,
  decodeTokensPerSecond:120,endToEndTokensPerSecond:40,promptProcessing:{source:'splash-native-stats',
    tokensPerSecond:453,processedTokens:500,cachedTokens:0,basis:'request-start-to-first-native-token'}};
assert.equal(core.requestTps(splashNative).primary,78);
assert.match(core.requestTps(splashNative).label,/first native batch excluded/);
assert.match(core.promptProcessingSummary(null,splashNative).title,/request preparation/);
const firstBatchOnly={...splashNative,runtimeTokensPerSecond:null};
assert.equal(core.requestTps(firstBatchOnly).primaryKind,'end-to-end');
assert.equal(core.requestTps(firstBatchOnly).primary,40);
const wait={value:'Waiting…',state:'unknown',title:'Awaiting native timing'};
assert.deepEqual(core.agentGenerationSpeed({backend:'splash',state:'running'},null,
  {value:'120 tok/s Pi live',state:'live'},wait),wait,'unproven Pi estimates cannot replace native-only decode');
assert.equal(core.promptProcessingSummary(null,omlxNative).value,'1.4 tok/s · last');
assert.match(core.promptProcessingSummary(null,omlxNative).title,/oMLX.*28 new prompt tokens/);
