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

console.log("Authoritative Chat response-limit detection passed.");
