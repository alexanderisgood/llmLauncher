import assert from 'node:assert/strict';
import {compactionRecoveryStream} from '../pi_context_recovery.js';

const context = {systemPrompt: 'native-summary-system', messages: [{role: 'user', content: [{type: 'text', text: '<conversation>USER_GOAL CHECKPOINT_7182 /project/app.js</conversation>'}]}]};
const model = {reasoning: true};
const usage = {input: 100, output: 400, cacheRead: 30, cacheWrite: 0, totalTokens: 530, cost: {input: 0, output: 0, total: 0}};
const response = (stopReason = 'stop', text = 'Complete checkpoint') => ({stopReason, content: [{type: 'text', text}], usage});
const run = (responses, extraOptions = {}) => {
  const requests = [];
  let retries = 0;
  const stream = compactionRecoveryStream(async (m, c, o) => {
    requests.push({model: m, context: c, options: o});
    return {result: async () => responses.shift()};
  }, () => retries++);
  return {requests, retries: () => retries, result: stream(model, context, {maxTokens: 13107, reasoning: 'medium', cacheRetention: 'none', ...extraOptions}).result()};
};

const saved = JSON.stringify(context);
{
  const test = run([response()]);
  assert.equal((await test.result).stopReason, 'stop');
  assert.equal(test.requests.length, 1);
  assert.equal(test.requests[0].options.maxTokens, 4096);
  assert.equal(test.requests[0].options.reasoning, 'medium');
  assert.equal(test.requests[0].context.systemPrompt, context.systemPrompt);
  assert.equal(JSON.stringify(context), saved, 'Original prompt is not mutated');
}
for (const initial of [response('length', 'PARTIAL_MUST_NOT_ENTER_CHECKPOINT'), response('stop', ' ')]) {
  const test = run([initial, response()]);
  const final = await test.result;
  assert.equal(test.requests.length, 2);
  assert.equal(test.retries(), 1);
  assert.equal(final.usage.input, 200);
  assert.equal(final.usage.output, 800);
  assert.equal(final.usage.cacheRead, 60);
  assert.equal(final.usage.totalTokens, 1060);
  assert.equal(final.content[0].text, 'Complete checkpoint');
  for (const request of test.requests) {
    assert.equal(request.options.maxTokens, 4096);
    const text = JSON.stringify(request.context);
    assert.ok(text.includes('USER_GOAL CHECKPOINT_7182 /project/app.js'));
    assert.ok(!text.includes('PARTIAL_MUST_NOT_ENTER_CHECKPOINT'));
  }
  assert.ok(JSON.stringify(test.requests[1].context).includes('at most 500 words'));
}
{
  const test = run([response('length'), response('length')]);
  assert.equal((await test.result).stopReason, 'length', 'Native Pi must reject a second truncated summary');
  assert.equal(test.requests.length, 2);
}
{
  const test = run([response('stop', ''), response('stop', '')]);
  await assert.rejects(test.result, /no summary after one shorter retry/);
  assert.equal(test.requests.length, 2);
}
for (const stop of ['error']) {
  const test = run([response(stop)]);
  assert.equal((await test.result).stopReason, stop);
  assert.equal(test.requests.length, 1, 'Other native failure cases are not hidden or retried here');
}
for (const invalid of [response('toolUse'), {...response(), content: [{type: 'toolCall', name: 'read', arguments: {path: '/tmp/file'}}]}]) {
  const test = run([invalid]);
  await assert.rejects(test.result, /attempted a tool call/);
  assert.equal(test.requests.length, 1, 'A summary cannot run tools or become an empty checkpoint');
}
{
  const abort = new AbortController(); abort.abort();
  const test = run([], {signal: abort.signal});
  await assert.rejects(test.result, /cancelled/);
  assert.equal(test.requests.length, 0);
}
{
  const abort = new AbortController(); let calls = 0;
  const stream = compactionRecoveryStream(() => ({result: async () => { calls++; abort.abort(); return response('length'); }}));
  await assert.rejects(stream(model, context, {maxTokens: 512, signal: abort.signal}).result(), /cancelled/);
  assert.equal(calls, 1, 'Cancellation between attempts cannot trigger another request');
}
{
  const test = run([response()], {maxTokens: 512});
  await test.result;
  assert.equal(test.requests[0].options.maxTokens, 512);
  assert.ok(JSON.stringify(test.requests[0].context).includes('at most 112 words'));
}
{
  let calls = 0, notices = 0;
  const stream = compactionRecoveryStream(() => ({result: async () => {
    calls++;
    return response(calls === 2 ? 'error' : 'length');
  }}), () => notices++);
  const options = {maxTokens: 4096};
  assert.equal((await stream(model, context, options).result()).stopReason, 'error');
  // Simulate native retryAssistantCall retrying that transient error.
  assert.equal((await stream(model, context, options).result()).stopReason, 'length');
  assert.equal(calls, 3, 'Native transport retry cannot replenish the shorter-summary retry');
  assert.equal(notices, 1);
}
console.log('Compaction preserves the native source, bounds output, retries once, counts wasted usage, and respects cancellation.');
