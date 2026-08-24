"use strict";

const assert = require("node:assert/strict");
const tabs = require("../agent_console_tabs.js");

const surfaces = ["run-one", "run-two"];
assert.equal(tabs.normalizeRecovery(null, "owner-one", surfaces).valid, false);
assert.equal(tabs.normalizeRecovery({version:99, ownerRunId:"owner-one"}, "owner-one", surfaces).valid, false);
assert.equal(tabs.normalizeRecovery({version:1, ownerRunId:"other"}, "owner-one", surfaces).valid, false);

const built = tabs.buildRecovery(
  "owner-one", "run-two", true,
  {"run-one":12, "run-two":34, output:"private terminal text"},
  ["run-one", "run-two", "run-two", "../unsafe"],
);
assert.deepEqual(built, {
  version:1,
  ownerRunId:"owner-one",
  activeSurfaceId:"run-two",
  visible:true,
  seen:{"run-one":12, "run-two":34},
});
assert.doesNotMatch(JSON.stringify(built), /private terminal text|output/);

const recovered = tabs.normalizeRecovery({
  ...built,
  seen:{"run-one":12, "run-two":"41", unknown:999, privateText:"do not restore"},
  terminalOutput:"must be ignored",
}, "owner-one", surfaces);
assert.deepEqual(recovered, {
  version:1,
  valid:true,
  ownerRunId:"owner-one",
  activeSurfaceId:"run-two",
  visible:true,
  seen:{"run-one":12, "run-two":41},
});
assert.doesNotMatch(JSON.stringify(recovered), /must be ignored|do not restore/);

assert.deepEqual(tabs.allowedSurfaceIds(["valid-one", "bad/id", "valid-one", "valid-two"]), ["valid-one", "valid-two"]);
assert.equal(tabs.safeOffset(true), 0);
assert.equal(tabs.safeOffset(-1), 0);

const matches = tabs.findMatches("Alpha beta ALPHA alpha", "alpha");
assert.deepEqual(matches.ranges, [{start:0, end:5}, {start:11, end:16}, {start:17, end:22}]);
assert.equal(matches.truncated, false);
const capped = tabs.findMatches("x x x", "x", 2);
assert.equal(capped.ranges.length, 2);
assert.equal(capped.truncated, true);
assert.equal(tabs.nextMatchIndex(-1, 3, 1), 0);
assert.equal(tabs.nextMatchIndex(0, 3, -1), 2);
assert.equal(tabs.nextMatchIndex(2, 3, 1), 0);
assert.equal(tabs.nextMatchIndex(2, 0, 1), -1);

assert.equal(tabs.tabPresentation({
  consoleRecord:{state:"running", bufferEnd:50}, seenEnd:10,
  activity:{state:"queued", queuePosition:2}, active:false,
}).label, "Queue #2");
assert.equal(tabs.tabPresentation({
  consoleRecord:{state:"running", bufferEnd:50}, seenEnd:10,
  activity:{state:"running"}, active:false,
}).label, "Generating");
const unread = tabs.tabPresentation({
  consoleRecord:{state:"running", bufferEnd:50}, seenEnd:10, active:false,
});
assert.equal(unread.label, "New output");
assert.equal(unread.unreadBytes, 40);
assert.equal(tabs.tabPresentation({
  consoleRecord:{state:"running", bufferEnd:50}, seenEnd:10, active:true,
}).label, "Ready");
assert.equal(tabs.tabPresentation({consoleRecord:{state:"failed"}}).tone, "failed");

console.log("Agent Console tab recovery, unread state, and bounded search core passed.");
