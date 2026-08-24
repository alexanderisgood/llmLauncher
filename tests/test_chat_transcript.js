"use strict";

const assert = require("node:assert/strict");
const transcript = require("../chat_transcript.js");

assert.equal(transcript.normaliseQuery("  Prefix\n  REUSE  "), "prefix reuse");
assert.equal(transcript.normaliseQuery("x".repeat(200)).length, transcript.MAX_QUERY_CHARACTERS);
assert.equal(transcript.normaliseQuery("Cafe\u0301"), "café");

const messages = [
  {id:"u1", role:"user", content:"Explain prefix reuse."},
  {id:"a1", role:"assistant", content:"The final answer.", reasoning:"Check the prefix cache."},
  {id:"u2", role:"user", content:"Now compare engines."},
  {id:"a2", role:"assistant", content:"MTPLX wins this measured route."},
  {id:"a3", role:"assistant", content:"Continuation of that answer."},
];

assert.deepEqual(
  transcript.searchMessages(messages, "PREFIX").map(match => ({id:match.id, fields:[...match.fields]})),
  [
    {id:"u1", fields:["content"]},
    {id:"a1", fields:["reasoning"]},
  ],
);
assert.deepEqual(transcript.searchMessages(messages, "missing"), []);
assert.deepEqual(
  transcript.turnLandmarks(messages).map(item => [item.id, item.label, item.turn]),
  [
    ["u1", "Turn 1", 1],
    ["a1", "Reply 1", 1],
    ["u2", "Turn 2", 2],
    ["a2", "Reply 2", 2],
    ["a3", "Reply 2", 2],
  ],
);

assert.equal(transcript.nextMatchIndex(-1, 1, 3), 0);
assert.equal(transcript.nextMatchIndex(0, -1, 3), 2);
assert.equal(transcript.nextMatchIndex(2, 1, 3), 0);
assert.equal(transcript.nextMatchIndex(2, 1, 0), -1);

const many = Array.from({length:700}, (_, index) => ({
  id:`m${index}`, role:index % 2 ? "assistant" : "user", content:"bounded result",
}));
assert.equal(transcript.searchMessages(many, "bounded").length, transcript.MAX_RESULTS);
assert.equal(transcript.turnLandmarks(many).length, transcript.MAX_MESSAGES);
assert.equal(messages[0].content, "Explain prefix reuse.");

console.log("Bounded current-transcript search, turn landmarks, and navigation passed.");
