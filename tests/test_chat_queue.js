"use strict";

const assert = require("node:assert/strict");
const queue = require("../chat_queue.js");

assert.deepEqual(queue.normaliseEnvelope({version:99, queues:{unsafe:{items:[]}}}), queue.emptyEnvelope());

let envelope = queue.emptyEnvelope();
envelope = queue.writeQueue(envelope, "surface:one:new:a", [
  {id:"queued-1", content:"first waiting message"},
  {id:"queued-2", content:"second waiting message"},
], 100);
assert.deepEqual(queue.readQueue(envelope, "surface:one:new:a"), [
  {id:"queued-1", content:"first waiting message"},
  {id:"queued-2", content:"second waiting message"},
]);

envelope = queue.moveQueue(envelope, "surface:one:new:a", "surface:one:history:123", 200);
assert.deepEqual(queue.readQueue(envelope, "surface:one:new:a"), []);
assert.equal(queue.readQueue(envelope, "surface:one:history:123")[0].content, "first waiting message");
envelope = queue.removeQueue(envelope, "surface:one:history:123");
assert.deepEqual(queue.readQueue(envelope, "surface:one:history:123"), []);

const limits = {
  maximumQueues:2,
  maximumMessages:2,
  maximumMessageCharacters:5,
  maximumQueueCharacters:8,
  maximumTotalCharacters:8,
  maximumKeyCharacters:64,
};
envelope = queue.writeQueue(queue.emptyEnvelope(), "one", [{id:"one", content:"12345"}], 1, limits);
envelope = queue.writeQueue(envelope, "two", [{id:"two", content:"abc"}], 2, limits);
envelope = queue.writeQueue(envelope, "three", [{id:"three", content:"XY"}], 3, limits);
assert.deepEqual(queue.readQueue(envelope, "one", limits), []);
assert.equal(queue.readQueue(envelope, "two", limits)[0].content, "abc");
assert.equal(queue.readQueue(envelope, "three", limits)[0].content, "XY");

const malformed = queue.normaliseEnvelope({
  version:1,
  queues:{
    safe:{updatedAt:5, items:[
      {id:"same", content:"ok"},
      {id:"same", content:"yes", hiddenState:"sent"},
      {id:"bad", content:"\u0000secret"},
      {id:"object", content:{private:true}},
    ]},
    "bad\nkey":{updatedAt:6, items:[{id:"bad", content:"no"}]},
  },
});
assert.deepEqual(Object.keys(malformed.queues), ["safe"]);
assert.deepEqual(malformed.queues.safe.items, [
  {id:"same", content:"ok"},
  {id:"same-1", content:"yes"},
]);

console.log("Tab-local paused Chat queue bounds and migration core passed.");
