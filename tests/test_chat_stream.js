"use strict";

const assert = require("node:assert/strict");
const stream = require("../chat_stream.js");

assert.equal(stream.responseLimitReason({choices:[{finish_reason:"length"}]}), "length");
assert.equal(stream.responseLimitReason({choices:[{finishReason:"max_tokens"}]}), "max_tokens");
assert.equal(stream.responseLimitReason({finish_reason:"max-completion-tokens"}), "max_completion_tokens");
assert.equal(stream.responseLimitReason({stopReason:"token limit"}), "token_limit");
assert.equal(
  stream.responseLimitReason({
    type:"response.incomplete",
    response:{incomplete_details:{reason:"max_output_tokens"}},
  }),
  "max_output_tokens",
);
assert.equal(
  stream.responseLimitReason({status:"incomplete", incomplete_details:{reason:"max_output_tokens"}}),
  "max_output_tokens",
);
assert.equal(
  stream.responseLimitReason({response:{incompleteDetails:{reason:"maxOutputTokens"}}}),
  "",
);
assert.equal(
  stream.responseLimitReason({response:{incompleteDetails:{reason:"max-output-tokens"}}}),
  "max_output_tokens",
);

for (const event of [
  {choices:[{finish_reason:"stop"}]},
  {choices:[{finish_reason:"tool_calls"}]},
  {choices:[{finish_reason:"content_filter"}]},
  {type:"response.incomplete", response:{status:"incomplete"}},
  {incomplete_details:{reason:"server_error"}},
  {},
  [],
  null,
  "finish_reason: length",
]) {
  assert.equal(stream.responseLimitReason(event), "");
  assert.equal(stream.responseLimitReached(event), false);
}

assert.equal(stream.responseLimitReached({incompleteDetails:{reason:"max tokens"}}), true);

assert.deepEqual(stream.partitionContent([
  {type:"thinking", thinking:"inspect "},
  {type:"reasoning_text", text:"route "},
  {type:"text", text:"Ready."},
]), {text:"Ready.", reasoning:"inspect route "});
assert.deepEqual(
  stream.eventParts({choices:[{delta:{thinking:"reason ", content:[
    {type:"thinking", thinking:"inside "},
    {type:"text", text:"answer"},
  ]}}]}),
  {text:"answer", reasoning:"inside reason "},
);
assert.deepEqual(
  stream.eventParts({type:"content_block_delta", delta:{type:"thinking_delta", thinking:"working"}}),
  {text:"", reasoning:"working"},
);
assert.deepEqual(
  stream.eventParts({type:"response.reasoning_summary_text.delta", delta:"summary"}),
  {text:"", reasoning:"summary"},
);
assert.equal(stream.hasFinalAnswer({content:"\n"}), false);
assert.equal(stream.hasFinalAnswer({content:"done", reasoning:"work"}), true);
assert.equal(stream.messageContextCharacters({role:"user", content:"hello", reasoning:"ignored"}), 5);
assert.equal(stream.messageContextCharacters({role:"assistant", content:"done", reasoning:"think"}), 9);
assert.equal(stream.messageContextCharacters({role:"assistant", content:"done", reasoning_content:"think"}), 9);
assert.equal(
  stream.incompleteAnswerKind({role:"assistant", content:"", reasoning:"work", interrupted:true}),
  "reasoning-only",
);
assert.equal(
  stream.incompleteAnswerKind({role:"assistant", content:"partial", truncated:true}),
  "truncated",
);
assert.equal(
  stream.incompleteAnswerKind({
    role:"assistant", content:"Chat error: offline", exclude:true, stopped:true,
  }),
  "failed",
);
assert.equal(
  stream.incompleteAnswerKind({
    role:"assistant", content:"partial answer", interrupted:true, exclude:true, stopped:true,
  }),
  "interrupted",
);
assert.equal(
  stream.incompleteAnswerKind({
    role:"assistant", content:"", reasoning:"", interrupted:true, exclude:true, stopped:true,
  }),
  "interrupted",
);
assert.equal(
  stream.incompleteRecoveryOperation({
    role:"assistant", content:"", reasoning:"work", interrupted:true, continuation:true,
  }),
  "continue",
);
assert.equal(
  stream.incompleteRecoveryOperation({
    role:"assistant", content:"", reasoning:"work", interrupted:true, continuation:false,
  }),
  "message",
);
assert.equal(
  stream.incompleteRecoveryOperation({
    role:"assistant", content:"Chat error", exclude:true, stopped:true, continuation:true,
  }),
  "continue",
);
assert.equal(
  stream.pausedQueueRecoveryAction(
    "retry", {role:"assistant", content:"", reasoning:"work", interrupted:true}, true,
  ),
  true,
);
assert.equal(
  stream.pausedQueueRecoveryAction(
    "continue", {role:"assistant", content:"partial", truncated:true}, true,
  ),
  true,
);
assert.equal(
  stream.pausedQueueRecoveryAction(
    "continue", {role:"assistant", content:"partial", truncated:true}, false,
  ),
  false,
);
assert.equal(
  stream.pausedQueueRecoveryAction(
    "retry", {role:"assistant", content:"Chat error", exclude:true, stopped:true}, true,
  ),
  true,
);
assert.equal(
  stream.pausedQueueRecoveryAction(
    "retry", {role:"assistant", content:"partial", interrupted:true, exclude:true, stopped:true}, true,
  ),
  true,
);
assert.equal(stream.shouldDrainQueue("complete"), true);
assert.equal(stream.shouldDrainQueue("stopped"), false);
assert.equal(stream.shouldDrainQueue("reasoning-only"), false);
assert.equal(stream.shouldDrainQueue("truncated"), false);
assert.equal(stream.shouldDrainQueue("failed"), false);
assert.equal(
  stream.blocksIncompleteTailRecovery({role:"assistant", content:"Chat error: offline", exclude:true, stopped:true}),
  true,
);
assert.equal(
  stream.blocksIncompleteTailRecovery({role:"assistant", content:"", reasoning:"again", exclude:true, stopped:true, interrupted:true}),
  true,
);
assert.equal(
  stream.blocksIncompleteTailRecovery({role:"assistant", content:"partial", truncated:true}),
  true,
);

const sseEvents = [];
const sse = stream.createSseDataParser(data => sseEvents.push(JSON.parse(data)));
sse.push(": heartbeat\r\nevent: message\r\ndata: {\r");
sse.push("\ndata: \"choices\":[{\"delta\":{\"thinking\":\"plan\",\"content\":\"done\"}}]\r\n");
sse.push("data: }\r\n\r\ndata: [DONE]\r\n\r\n");
sse.finish();
assert.equal(sse.sawData(), true);
assert.equal(sseEvents.length, 1);
assert.deepEqual(stream.eventParts(sseEvents[0]), {text:"done", reasoning:"plan"});

const finalEvent = [];
const unterminated = stream.createSseDataParser(data => finalEvent.push(JSON.parse(data)));
unterminated.push('data: {"choices":[{"delta":{"content":"tail"}}]}');
unterminated.finish();
assert.equal(finalEvent[0].choices[0].delta.content, "tail");

const looseEvents = [];
const loose = stream.createSseDataParser(data => looseEvents.push(JSON.parse(data)));
loose.push('data: {"choices":[{"delta":{"content":"one"}}]}\n');
loose.push('data: {"choices":[{"delta":{"content":"two"}}]}\ndata: [DONE]\n');
loose.finish();
assert.equal(looseEvents.length, 2);
assert.equal(looseEvents[1].choices[0].delta.content, "two");

console.log("Authoritative Chat response-limit detection passed.");
