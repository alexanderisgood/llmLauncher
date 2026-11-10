"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const timeline = require("../pi_timeline.js");

const app = fs.readFileSync(path.resolve(__dirname, "..", "app.js"), "utf8") + "\n" + fs.readFileSync(require.resolve("../agent_console_workspace.js"), "utf8");
const view = fs.readFileSync(path.resolve(__dirname, "..", "pi_timeline_view.js"), "utf8");

const empty = timeline.emptyTimeline();
const noisyEvents = [
  {revision:1, kind:"thinking", itemId:"thought", operation:"replace", text:"Visible reasoning"},
  ...Array.from({length:1000}, (_, index) => ({
    revision:index + 2, kind:"notice", title:"Pi notice", text:"setStatus",
    itemId:`interaction:${index}`, operation:"replace",
  })),
  {revision:1002, kind:"answer", text:"Answer"},
  {revision:1003, kind:"notice", title:"Pi notice", text:"Response limit reached.", itemId:"interaction:warning"},
];
const cleaned = timeline.applyTimelineEnvelope(empty, {
  timelineVersion:1, timelineReset:true, timelineBaseRevision:1,
  timelineRevision:1003, nextTimelineRevision:1003, timelineEvents:noisyEvents,
});
assert.deepEqual(cleaned.state.items.map(item => item.kind), ["thinking", "answer", "notice"]);
assert.equal(cleaned.state.revision, 1003, "filtered updates must still advance the read cursor");
assert.doesNotMatch(timeline.timelinePlainText(cleaned.state), /setStatus/);
assert.equal(timeline.thinkingIsOpen("thought", new Map()), true);
assert.equal(timeline.thinkingIsOpen("thought", new Map([["thought", false]])), false);
assert.equal(timeline.thinkingIsOpen("thought", new Map([["thought", true]])), true);
assert.match(view, /PiTimelineCore\.thinkingIsOpen\(item.key, expanded\)/);
assert.deepEqual(empty, {
  version:1, baseRevision:0, revision:0, availableRevision:0, items:[],
});

const first = timeline.applyTimelineEnvelope(empty, {
  timelineVersion:1,
  timelineBaseRevision:1,
  timelineRevision:5,
  nextTimelineRevision:5,
  timelineReset:false,
  timelineEvents:[
    {revision:1, kind:"user", text:"Inspect <script> literally"},
    {revision:2, kind:"thinking", itemId:"turn-1-thinking", operation:"append", text:"Check "},
    {revision:3, kind:"thinking", itemId:"turn-1-thinking", operation:"append", text:"the route."},
    {revision:4, kind:"toolCall", itemId:"tool-1", operation:"replace", title:"Read file", text:"README.md"},
    {revision:5, kind:"answer", itemId:"turn-1-answer", operation:"replace", text:"Done."},
  ],
});
assert.equal(first.supported, true);
assert.equal(first.accepted, 5);
assert.equal(first.state.revision, 5);
assert.equal(first.state.items.length, 4);
assert.equal(first.state.items[1].text, "Check the route.");
assert.equal(first.state.items[0].text, "Inspect <script> literally");

const duplicate = timeline.applyTimelineEnvelope(first.state, {
  timelineVersion:1,
  timelineBaseRevision:1,
  timelineRevision:5,
  nextTimelineRevision:5,
  timelineReset:false,
  timelineEvents:[{revision:5, kind:"answer", itemId:"turn-1-answer", operation:"append", text:" duplicated"}],
});
assert.equal(duplicate.changed, false);
assert.equal(duplicate.state, first.state, "Idle polls reuse their immutable state");
assert.equal(duplicate.state.items.at(-1).text, "Done.");

const next = timeline.applyTimelineEnvelope(first.state, {
  timelineVersion:1,
  timelineBaseRevision:1,
  timelineRevision:7,
  nextTimelineRevision:7,
  timelineReset:false,
  timelineEvents:[
    {revision:6, kind:"answer", itemId:"turn-1-answer", operation:"replace", text:"Finished safely."},
    {revision:7, kind:"notice", text:"Ready"},
  ],
});
assert.equal(next.state.items.at(-2).text, "Finished safely.");
assert.equal(next.state.items.at(-1).kind, "notice");
assert.equal(next.state.items[0], first.state.items[0], "Unchanged history is shared");
assert.equal(first.state.items.at(-1).text, "Done.", "Later deltas cannot mutate earlier state");
assert.throws(() => { next.state.items[0].text = "mutated"; }, TypeError);

const reset = timeline.applyTimelineEnvelope(next.state, {
  timelineVersion:1,
  timelineBaseRevision:20,
  timelineRevision:21,
  nextTimelineRevision:21,
  timelineReset:true,
  timelineEvents:[
    {revision:20, kind:"queue", itemId:"queue", operation:"replace", text:"1 follow-up queued"},
    {revision:21, kind:"error", text:"Stopped"},
  ],
});
assert.equal(reset.reset, true);
assert.deepEqual(reset.state.items.map(item => item.kind), ["queue", "error"]);
assert.equal(reset.state.revision, 21);

const malformed = timeline.applyTimelineEnvelope(reset.state, {
  timelineVersion:1,
  timelineBaseRevision:20,
  timelineRevision:24,
  nextTimelineRevision:24,
  timelineReset:false,
  timelineEvents:[
    {revision:22, kind:"unknown", text:"ignored"},
    {revision:23, kind:"answer", text:42},
    {revision:24, kind:"answer", text:"Accepted"},
  ],
});
assert.equal(malformed.accepted, 1);
assert.equal(malformed.state.revision, 24);
assert.equal(malformed.state.items.at(-1).text, "Accepted");

const stale = timeline.applyTimelineEnvelope(malformed.state, {
  timelineVersion:1, timelineRevision:2, nextTimelineRevision:2, timelineEvents:[],
});
assert.equal(stale.stale, true);
assert.strictEqual(stale.state, malformed.state);
assert.strictEqual(
  timeline.applyTimelineEnvelope(malformed.state, {timelineVersion:99}).state,
  malformed.state,
);

assert.match(timeline.timelinePlainText(first.state), /You\nInspect <script> literally/);
assert.match(timeline.timelinePlainText(first.state), /Thinking\nCheck the route\./);
assert.equal(timeline.isNearBottom({scrollHeight:1000, scrollTop:700, clientHeight:250}), true);
assert.equal(timeline.isNearBottom({scrollHeight:1000, scrollTop:400, clientHeight:250}), false);
assert.equal(timeline.restoredScrollTop(413, false, 1400), 413);
assert.equal(timeline.restoredScrollTop(413, true, 1400), 1400);
assert.equal(
  timeline.followTailAfterScroll(true, 700, 680, true, "up"),
  false,
  "an upward gesture detaches even inside the near-bottom threshold",
);
assert.equal(timeline.followTailAfterScroll(false, 680, 720, false, "down"), false);
assert.equal(timeline.followTailAfterScroll(false, 720, 750, true, "down"), true);
assert.equal(timeline.followTailAfterScroll(true, 700, 700, false), true);
assert.equal(timeline.followTailAfterScroll(true, 700, 320, false), true,
  "card collapse and reflow cannot turn off following without a user gesture");
assert.equal(timeline.followTailAfterScroll(false, 700, 320, true), false,
  "layout shrink cannot pull a reader back into following");
assert.equal(timeline.followTailAfterScroll(true, 700, 620, false, "scrollbar"), false);
assert.equal(timeline.followTailAfterScroll(false, 620, 750, true, "scrollbar"), true);
assert.equal(timeline.anchoredScrollTop(413, 12, 37), 438);
assert.equal(timeline.anchoredScrollTop(413, NaN, 37), 413);
assert.match(app, /function handleAgentPiTimelineScroll\(\)/);
assert.match(app, /recordAgentPiScrollIntent\(event\.deltaY < 0 \? "up" : "down"\)/);
assert.match(view, /agentPiTimelineScrollAnchor\(viewport, timeline\)/);
assert.match(app, /view\.piNewOutput = true/);

assert.equal(timeline.truncateUtf8("🙂🙂", 5), "🙂");
assert.equal(timeline.truncateUtf8("🙂🙂", 5, true), "🙂");

const longDeltas = Array.from({length:24}, (_, index) => ({
  revision:index + 1,
  kind:"answer",
  itemId:"long-answer",
  operation:"append",
  text:`part-${String(index).padStart(2, "0")}:` + "🙂".repeat(1024),
}));
const boundedStream = timeline.applyTimelineEnvelope(timeline.emptyTimeline(), {
  timelineVersion:1,
  timelineBaseRevision:1,
  timelineRevision:longDeltas.length,
  nextTimelineRevision:longDeltas.length,
  timelineReset:true,
  timelineEvents:longDeltas,
});
assert.equal(boundedStream.state.items.length, 1);
assert.ok(
  timeline.itemTextBytes(boundedStream.state.items[0]) <= timeline.MAX_ITEM_TEXT_BYTES,
  "one mutable stream must remain within the per-item UTF-8 byte cap",
);
assert.match(boundedStream.state.items[0].text, /part-23:/);
assert.doesNotThrow(() => new TextDecoder("utf-8", {fatal:true}).decode(
  new TextEncoder().encode(boundedStream.state.items[0].text),
));

const authoritative = timeline.applyTimelineEnvelope(boundedStream.state, {
  timelineVersion:1,
  timelineBaseRevision:1,
  timelineRevision:25,
  nextTimelineRevision:25,
  timelineReset:false,
  timelineEvents:[{
    revision:25, kind:"answer", itemId:"long-answer", operation:"replace",
    text:"Authoritative final answer",
  }],
});
assert.equal(authoritative.state.items[0].text, "Authoritative final answer");

const oversizedItems = Array.from({length:9}, (_, index) => ({
  revision:index + 1,
  kind:"notice",
  text:String(index).repeat(timeline.MAX_ITEM_TEXT_BYTES),
}));
const totalBounded = timeline.applyTimelineEnvelope(timeline.emptyTimeline(), {
  timelineVersion:1,
  timelineBaseRevision:1,
  timelineRevision:oversizedItems.length,
  nextTimelineRevision:oversizedItems.length,
  timelineReset:true,
  timelineEvents:oversizedItems,
});
assert.equal(totalBounded.state.items.length, 8);
assert.equal(totalBounded.state.items[0].revision, 2);
assert.ok(
  totalBounded.state.items.reduce((total, item) => total + timeline.itemTextBytes(item), 0)
    <= timeline.MAX_TOTAL_TEXT_BYTES,
  "materialized timeline text must remain inside the total UTF-8 byte cap",
);

const manyItems = Array.from({length:timeline.MAX_ITEMS + 8}, (_, index) => ({
  revision:index + 1, kind:"notice", text:`event ${index + 1}`,
}));
const countBounded = timeline.applyTimelineEnvelope(timeline.emptyTimeline(), {
  timelineVersion:1,
  timelineBaseRevision:1,
  timelineRevision:manyItems.length,
  nextTimelineRevision:manyItems.length,
  timelineReset:true,
  timelineEvents:manyItems,
});
assert.equal(countBounded.state.items.length, timeline.MAX_ITEMS);
assert.equal(countBounded.state.items[0].revision, 9);

// An unexpectedly oversized delta batch must not build an unbounded client
// materialized view before the normal history bound is applied. The newest
// history and revision cursor remain recoverable after compaction.
const oversizedBatch = Array.from({length:timeline.MAX_ITEMS * 8}, (_, index) => ({
  revision:index + 1, kind:"notice", text:`batch event ${index + 1}`,
}));
const compactedBatch = timeline.applyTimelineEnvelope(timeline.emptyTimeline(), {
  timelineVersion:1,
  timelineBaseRevision:1,
  timelineRevision:oversizedBatch.length,
  nextTimelineRevision:oversizedBatch.length,
  timelineReset:true,
  timelineEvents:oversizedBatch,
});
assert.equal(compactedBatch.state.items.length, timeline.MAX_ITEMS);
assert.equal(compactedBatch.state.items.at(-1).revision, oversizedBatch.length);
assert.equal(compactedBatch.state.revision, oversizedBatch.length);
assert.ok(
  compactedBatch.state.items.reduce((total, item) => total + timeline.itemTextBytes(item), 0)
    <= timeline.MAX_TOTAL_TEXT_BYTES,
  "oversized delta batches retain only bounded materialized text",
);

assert.equal(timeline.timelineAvailableRevision({revision:7, availableRevision:8}, {
  timelineRevision:12,
}), 12);
assert.equal(timeline.timelineAvailableRevision({revision:14}, {timelineRevision:12}), 14);
assert.equal(timeline.shouldUseTimeline("pi-rpc", false), false);
assert.equal(timeline.shouldUseTimeline("pi-rpc", true), true);
assert.equal(timeline.shouldUseTimeline("terminal", true), false);
assert.equal(timeline.shouldRenderTimeline(false, {supported:true, changed:false}), true);
assert.equal(timeline.shouldRenderTimeline(true, {supported:true, changed:false}), false);
assert.equal(timeline.shouldRenderTimeline(true, {supported:true, changed:true}), true);
assert.equal(timeline.shouldRenderTimeline(true, {supported:false, changed:true}), false);

console.log("Pi semantic timeline reconciliation, replay, and scroll policy passed.");

const receipt = timeline.applyTimelineEnvelope(timeline.emptyTimeline(), {
  timelineVersion:1, timelineReset:true, timelineBaseRevision:1,
  timelineRevision:2, nextTimelineRevision:2,
  timelineEvents:[
    {revision:1, kind:"answer", text:"Level finished."},
    {revision:2, kind:"summary", itemId:"prompt:summary", operation:"replace",
      title:"Complete", text:"1m 5s · 1,100 total tokens · 1,050 input · 50 output"},
  ],
});
assert.equal(receipt.state.items.at(-1).kind, "summary");
assert.match(timeline.timelinePlainText(receipt.state), /Complete\n1m 5s · 1,100 total tokens/);

// Streaming updates and snapshot reloads retain a message's original time.
const firstTime = '2026-09-06T14:02:03.000Z';
const timed = timeline.applyTimelineEnvelope(timeline.emptyTimeline(), {
  timelineVersion:1, nextTimelineRevision:2, timelineEvents:[
    {revision:1, kind:'answer', itemId:'timed', operation:'replace', text:'Hello', createdAt:firstTime},
    {revision:2, kind:'answer', itemId:'timed', operation:'append', text:' there', createdAt:'2026-09-06T14:03:00Z'},
  ],
});
assert.equal(timed.state.items[0].createdAt, firstTime);
assert.equal(timed.state.items[0].text, 'Hello there');
const replayed = timeline.applyTimelineEnvelope(timed.state, {
  timelineVersion:1, timelineReset:true, nextTimelineRevision:3,
  timelineEvents:[{revision:3, kind:'answer', itemId:'timed', operation:'replace', text:'Hello there', createdAt:firstTime}],
});
assert.equal(replayed.state.items[0].createdAt, firstTime);
assert.equal(cleaned.state.items[0].createdAt, '', 'old undated events must not receive invented dates');
