"use strict";

const assert = require("node:assert/strict");
const scroll = require("../chat_scroll.js");

assert.equal(scroll.nearBottom({scrollHeight:1000, clientHeight:400, scrollTop:600}), true);
assert.equal(scroll.nearBottom({scrollHeight:1000, clientHeight:400, scrollTop:540}), true);
assert.equal(scroll.nearBottom({scrollHeight:1000, clientHeight:400, scrollTop:500}), false);
assert.equal(scroll.nearBottom({scrollHeight:300, clientHeight:400, scrollTop:0}), true);

assert.equal(scroll.restoredTop({scrollHeight:1400, clientHeight:400}, 275), 275);
assert.equal(scroll.restoredTop({scrollHeight:500, clientHeight:400}, 275), 100);
assert.equal(scroll.restoredTop({scrollHeight:500, clientHeight:400}, -20), 0);

const scrolledUpReasoning = scroll.captureScroll({
  scrollHeight:1000, clientHeight:360, scrollTop:180,
});
assert.deepEqual(scrolledUpReasoning, {scrollTop:180, follow:false});
assert.equal(
  scroll.restoredCapturedTop(
    {scrollHeight:1400, clientHeight:360, scrollTop:0}, scrolledUpReasoning,
  ),
  180,
  "a streamed reasoning redraw must preserve the reader's inner scroll position",
);

const followedReasoning = scroll.captureScroll({
  scrollHeight:1000, clientHeight:360, scrollTop:640,
});
assert.deepEqual(followedReasoning, {scrollTop:640, follow:true});
assert.equal(
  scroll.restoredCapturedTop(
    {scrollHeight:1400, clientHeight:360, scrollTop:0}, followedReasoning,
  ),
  1040,
  "a reasoning panel already at its tail must follow newly streamed thinking",
);
assert.equal(
  scroll.restoredCapturedTop(
    {scrollHeight:900, clientHeight:360, scrollTop:0}, null, true,
  ),
  540,
  "a new live reasoning panel starts at its latest output",
);

assert.equal(scroll.renderAction({
  shouldFollow:true,
  capturedRenderRevision:7,
  currentRenderRevision:8,
}), "stale");
assert.equal(scroll.renderAction({
  shouldFollow:true,
  capturedInteractionRevision:3,
  currentInteractionRevision:4,
}), "preserve-user");
assert.equal(scroll.renderAction({
  forceBottom:true,
  shouldFollow:false,
  capturedInteractionRevision:3,
  currentInteractionRevision:4,
}), "follow");
assert.equal(scroll.renderAction({shouldFollow:true}), "follow");
assert.equal(scroll.renderAction({shouldFollow:false}), "restore");

assert.equal(
  scroll.queuedTurnShouldFollow(true, {
    scrollHeight:1000, clientHeight:400, scrollTop:600,
  }),
  true,
  "an auto-started queued turn may follow only when the reader is still at the tail",
);
assert.equal(
  scroll.queuedTurnShouldFollow(false, {
    scrollHeight:1000, clientHeight:400, scrollTop:600,
  }),
  false,
  "an explicit scroll-up intent survives the transition to the next queued turn",
);
assert.equal(
  scroll.queuedTurnShouldFollow(true, {
    scrollHeight:1000, clientHeight:400, scrollTop:420,
  }),
  false,
  "a reader above the follow threshold is not yanked to the next queued answer",
);

assert.deepEqual(
  scroll.normaliseMetrics({scrollHeight:"900", clientHeight:"300", scrollTop:"Infinity"}),
  {scrollHeight:900, clientHeight:300, scrollTop:0, maximumTop:600},
);

console.log("Streaming Chat scroll-follow and restoration core passed.");
