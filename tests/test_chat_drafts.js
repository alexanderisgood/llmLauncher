"use strict";

const assert = require("node:assert/strict");
const drafts = require("../chat_drafts.js");

assert.deepEqual(drafts.normaliseEnvelope({version:99, drafts:{unsafe:{text:"no"}}}), drafts.emptyEnvelope());

let envelope = drafts.emptyEnvelope();
envelope = drafts.writeDraft(envelope, "surface:one:new:a", "unfinished message", 100);
assert.equal(drafts.readDraft(envelope, "surface:one:new:a"), "unfinished message");
assert.equal(envelope.activeKey, "surface:one:new:a");

envelope = drafts.moveDraft(envelope, "surface:one:new:a", "surface:one:history:123");
assert.equal(drafts.readDraft(envelope, "surface:one:new:a"), "");
assert.equal(drafts.readDraft(envelope, "surface:one:history:123"), "unfinished message");
assert.equal(envelope.activeKey, "surface:one:history:123");

envelope = drafts.removeDraft(envelope, "surface:one:history:123");
assert.equal(drafts.readDraft(envelope, "surface:one:history:123"), "");
assert.equal(envelope.activeKey, "");

const limits = {
  maximumDrafts:2,
  maximumDraftCharacters:5,
  maximumTotalCharacters:8,
  maximumKeyCharacters:64,
};
envelope = drafts.writeDraft(drafts.emptyEnvelope(), "one", "123456", 1, limits);
envelope = drafts.writeDraft(envelope, "two", "abc", 2, limits);
envelope = drafts.writeDraft(envelope, "three", "XYZ", 3, limits);
assert.equal(drafts.readDraft(envelope, "one", limits), "");
assert.equal(drafts.readDraft(envelope, "two", limits), "abc");
assert.equal(drafts.readDraft(envelope, "three", limits), "XYZ");
assert.equal(Object.keys(envelope.drafts).length, 2);

const malformed = drafts.normaliseEnvelope({
  version:1,
  activeKey:"safe",
  drafts:{
    safe:{text:"ok", updatedAt:2},
    "bad\nkey":{text:"no", updatedAt:3},
    object:{text:{secret:true}, updatedAt:4},
  },
});
assert.deepEqual(Object.keys(malformed.drafts), ["safe"]);
assert.equal(malformed.activeKey, "safe");

console.log("Tab-local Chat draft bounds and migration core passed.");
