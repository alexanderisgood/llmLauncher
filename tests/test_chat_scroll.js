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

assert.deepEqual(
  scroll.normaliseMetrics({scrollHeight:"900", clientHeight:"300", scrollTop:"Infinity"}),
  {scrollHeight:900, clientHeight:300, scrollTop:0, maximumTop:600},
);

console.log("Streaming Chat scroll-follow and restoration core passed.");
