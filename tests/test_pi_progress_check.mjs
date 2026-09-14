import assert from 'node:assert/strict';
import test from 'node:test';
import install, {createInspectionProgressCheck} from '../pi-workflow.js';

const plain = value => JSON.parse(JSON.stringify(value));
const read = (index, turn, overrides = {}) => ({
  toolName:'read', input:{path:'game.js', offset:100 + index * 80, limit:80},
  content:[{type:'text', text:`Renderer section ${index}`}], isError:false, turn,
  ...overrides,
});
function cycle(detector, length = 2, firstTurn = 1) {
  const results = [];
  for (let round = 0; round < 3; round++) {
    for (let index = 0; index < length; index++) results.push(detector.observe(read(index, firstTurn + round)));
  }
  return results;
}

test('Only three completed unchanged cycles of two to four actions produce evidence', () => {
  for (const length of [2, 3, 4]) {
    const detector = createInspectionProgressCheck();
    const results = cycle(detector, length);
    assert.ok(results.slice(0, -1).every(value => value === undefined));
    const evidence = results.at(-1);
    assert.equal(evidence.cycles, 3);
    assert.equal(evidence.actions.length, length);
    assert.deepEqual(evidence.actions.map(action => action.input),
      Array.from({length}, (_, index) => read(index, 1).input));
    for (const action of evidence.actions) {
      assert.equal(action.tool, 'read');
      assert.match(action.resultHash, /^[a-f0-9]{64}$/);
    }
  }
});

test('New sections, changed results and a single repeated action do not trigger', () => {
  for (const scenario of ['new-sections', 'changing-results', 'single-action']) {
    const detector = createInspectionProgressCheck();
    for (let index = 0; index < 36; index++) {
      const event = read(scenario === 'new-sections' ? index : scenario === 'single-action' ? 0 : index % 2, index + 1);
      if (scenario === 'changing-results') event.content[0].text += `, revision ${index}`;
      assert.equal(detector.observe(event), undefined, scenario);
    }
  }
});

test('Different native inspection tools remain distinct and cycles longer than four stay out of scope', () => {
  const detector = createInspectionProgressCheck();
  const tools = ['read', 'grep', 'find', 'ls'];
  let evidence;
  for (let round = 0; round < 3; round++) {
    for (const toolName of tools) evidence = detector.observe(read(0, round + 1, {toolName}));
  }
  assert.deepEqual(evidence.actions.map(action => action.tool), tools);
  const longer = createInspectionProgressCheck();
  for (let index = 0; index < 30; index++) {
    assert.equal(longer.observe(read(index % 5, 1 + Math.floor(index / 5))), undefined);
  }
});

test('Cycles must follow observed results across separate assistant turns', () => {
  for (const turns of [[1, 1, 1, 1, 1, 1], [1, 2, 2, 3, 3, 4]]) {
    const detector = createInspectionProgressCheck();
    turns.forEach((turn, index) => {
      assert.equal(detector.observe(read(index % 2, turn)), undefined,
        'One batch or overlapping batches do not prove the model reread a completed cycle');
    });
  }
});

test('Unsupported work and unavailable evidence break the sequence instead of being ignored', () => {
  const interrupted = [
    {toolName:'bash', input:{command:'cd /tmp/project && node test.js'}},
    {toolName:'browser_check', input:{action:'inspect'}},
    {toolName:'browser_check', input:{action:'open', url:'http://localhost:3000'}},
    {toolName:'write', input:{path:'game.js', content:'updated'}},
    {toolName:'edit', input:{path:'game.js', oldText:'before', newText:'after'}},
    {toolName:'web_search', input:{query:'renderer reference'}},
    {isError:true},
    {isError:undefined},
    {content:undefined},
    {content:[]},
    {content:[{type:'image', data:'image-data', mimeType:'image/png'}]},
    {content:[{type:'text', text:'x'.repeat(128 * 1024 + 1)}]},
    {input:{path:'x'.repeat(2049)}},
    {turn:undefined},
  ];
  for (const interruption of interrupted) {
    const detector = createInspectionProgressCheck();
    for (let index = 0; index < 4; index++) assert.equal(detector.observe(read(index % 2, 1 + Math.floor(index / 2))), undefined);
    assert.equal(detector.observe(read(9, 3, interruption)), undefined);
    assert.equal(detector.observe(read(0, 4)), undefined);
    assert.equal(detector.observe(read(1, 4)), undefined, JSON.stringify(interruption).slice(0, 120));
  }
});

test('Exact arguments and full content are compared without trimming or truncation', () => {
  for (const changedField of ['input', 'content']) {
    const detector = createInspectionProgressCheck();
    for (let round = 0; round < 3; round++) {
      for (let index = 0; index < 2; index++) {
        const event = read(index, round + 1);
        if (changedField === 'input') event.input.path += ' '.repeat(round);
        else event.content[0].text = 'Identical prefix '.repeat(3000) + `tail ${index}, revision ${round}`;
        assert.equal(detector.observe(event), undefined, changedField);
      }
    }
  }
});

test('Lifecycle resets clear evidence but only a genuine new input renews the reminder cap', () => {
  const detector = createInspectionProgressCheck();
  assert.ok(cycle(detector).at(-1));
  detector.commit();
  detector.reset();
  assert.ok(cycle(detector, 2, 4).every(value => value === undefined));
  detector.newInput();
  assert.ok(cycle(detector, 2, 7).at(-1));
  const partial = createInspectionProgressCheck();
  for (let index = 0; index < 4; index++) partial.observe(read(index % 2, 1 + Math.floor(index / 2)));
  partial.reset();
  assert.equal(partial.observe(read(0, 3)), undefined);
  assert.equal(partial.observe(read(1, 3)), undefined);
});

test('A discarded candidate does not consume the one-per-input reminder allowance', () => {
  const detector = createInspectionProgressCheck();
  assert.ok(cycle(detector).at(-1));
  detector.reset();
  assert.ok(cycle(detector, 2, 4).at(-1));
  detector.commit();
  assert.ok(cycle(detector, 2, 7).every(value => value === undefined));
});

function nativeFixture(request = 'Investigate the renderer.') {
  const hooks = new Map(), notices = [], transcript = [];
  const toolSources = new Map(['read', 'edit', 'bash'].map(name => [name, 'builtin']));
  let callId = 0, aborts = 0;
  let assistant;
  const ctx = {abort:() => aborts++, sessionManager:{getBranch:() => []}};
  install({on:(name, handler) => hooks.set(name, handler),
    sendMessage:(...args) => notices.push(args), getActiveTools:() => ['read', 'edit', 'bash'],
    getAllTools:() => [...toolSources].map(([name, source]) => ({name, sourceInfo:{source}}))});
  const input = (text = request, source = 'rpc') => hooks.get('input')({source, text}, ctx);
  input();
  hooks.get('before_agent_start')({systemPrompt:''}, ctx);
  return {hooks, notices, ctx, input, transcript, toolSources, get aborts() { return aborts; },
    beginTurn() {
      assistant = {role:'assistant', content:[], stopReason:'toolUse'};
      transcript.push(assistant);
      hooks.get('message_start')({message:assistant}, ctx);
    },
    endTurn() { hooks.get('turn_end')({message:assistant}, ctx); },
    run(index, overrides = {}) {
      const event = read(index, 1, overrides);
      const args = event.input;
      const result = {content:event.content};
      const original = plain({args, result});
      const decision = hooks.get('tool_call')({toolName:event.toolName, input:args}, ctx);
      assert.equal(decision, undefined);
      if (event.toolName === 'bash' && toolSources.get('bash') === 'builtin' && original.args.timeout === undefined) original.args.timeout = 120;
      const toolCallId = `native-call-${++callId}`;
      assistant.content.push({type:'toolCall', id:toolCallId, name:event.toolName, arguments:args});
      hooks.get('tool_execution_start')({toolCallId, toolName:event.toolName, args}, ctx);
      hooks.get('tool_execution_end')({toolCallId, isError:event.isError, result}, ctx);
      transcript.push({role:'toolResult', toolCallId, toolName:event.toolName, isError:event.isError,
        content:event.content});
      assert.deepEqual({args, result}, original, 'The original tool observations remain intact');
    },
  };
}
function runNativeCycle(f) {
  for (let round = 0; round < 3; round++) {
    f.beginTurn();
    f.run(0);
    f.run(1);
    f.endTurn();
  }
}

test('The real hooks emit one non-triggering evidence notice without modifying results', () => {
  const f = nativeFixture();
  runNativeCycle(f);
  assert.equal(f.aborts, 0);
  assert.equal(f.notices.length, 1);
  const [message, options] = f.notices[0];
  assert.equal(message.customType, 'launcher-progress-check');
  assert.equal(message.display, true);
  assert.equal(message.details.cycles, 3);
  assert.equal(message.details.actions.length, 2);
  assert.match(message.content, /unchanged|identical|same/i);
  assert.deepEqual(options, {triggerTurn:false}, 'The notice must not steer, follow up or force a turn');
  for (const boundary of ['before_agent_start', 'agent_end', 'session_compact']) {
    f.hooks.get(boundary)({systemPrompt:''}, f.ctx);
    f.input('Automatic continuation', 'extension');
    runNativeCycle(f);
    assert.equal(f.notices.length, 1, `${boundary} cannot renew the per-input cap`);
  }
  f.input('Investigate again.');
  runNativeCycle(f);
  assert.equal(f.notices.length, 2);
});

test('The real hooks exempt monitoring and duplicate calls within one assistant message', () => {
  const monitor = nativeFixture('Monitor the renderer snapshots.');
  runNativeCycle(monitor);
  assert.deepEqual(monitor.notices, []);
  const batch = nativeFixture();
  batch.beginTurn();
  for (let index = 0; index < 12; index++) batch.run(index % 2);
  batch.endTurn();
  assert.deepEqual(batch.notices, []);
});

test('Each native lifecycle boundary discards partial cycle evidence', () => {
  for (const boundary of ['before_agent_start', 'agent_end', 'session_compact', 'session_start']) {
    const f = nativeFixture();
    for (let round = 0; round < 2; round++) { f.beginTurn(); f.run(0); f.run(1); f.endTurn(); }
    f.hooks.get(boundary)({systemPrompt:''}, f.ctx);
    f.beginTurn(); f.run(0); f.run(1); f.endTurn();
    assert.deepEqual(f.notices, [], boundary);
  }
});

test('Later work in the triggering batch cancels the candidate without consuming the cap', () => {
  for (const laterWork of [
    {toolName:'edit', input:{path:'game.js', oldText:'before', newText:'after'}},
    {toolName:'bash', input:{command:'node test.js'}},
    {},
  ]) {
    const f = nativeFixture();
    for (let round = 0; round < 2; round++) { f.beginTurn(); f.run(0); f.run(1); f.endTurn(); }
    f.beginTurn(); f.run(0); f.run(1);
    assert.deepEqual(f.notices, [], 'A complete cycle is still only a candidate before the batch ends');
    f.run(9, laterWork);
    f.endTurn();
    assert.deepEqual(f.notices, [], 'A later edit, executable check or new observation cancels the stale reminder');
    runNativeCycle(f);
    assert.equal(f.notices.length, 1, 'Cancelling the candidate must leave the genuine-input allowance available');
    assert.equal(f.notices[0][1].triggerTurn, false);
  }
});

test('An overridden or unknown-provenance read is not treated as a native inspection', () => {
  for (const source of ['extension', undefined]) {
    const f = nativeFixture();
    f.toolSources.set('read', source);
    runNativeCycle(f);
    assert.deepEqual(f.notices, []);
  }
  const f = nativeFixture();
  for (let round = 0; round < 2; round++) { f.beginTurn(); f.run(0); f.run(1); f.endTurn(); }
  f.toolSources.set('read', 'extension');
  f.beginTurn(); f.run(9); f.endTurn();
  f.toolSources.set('read', 'builtin');
  f.beginTurn(); f.run(0); f.run(1); f.endTurn();
  assert.deepEqual(f.notices, [], 'An intervening custom read also breaks partial native evidence');
});

test('Context delivery inserts the notice once after its confirmed result, preserving the saved transcript', () => {
  const f = nativeFixture();
  runNativeCycle(f);
  const notice = f.notices[0][0];
  f.beginTurn(); f.run(9); f.endTurn();
  const original = JSON.stringify(f.transcript);
  const anchor = f.transcript.findIndex(message => message.role === 'toolResult'
    && message.toolCallId === notice.details.afterToolCallId);
  const enriched = f.hooks.get('context')({messages:f.transcript}, f.ctx).messages;
  assert.equal(JSON.stringify(f.transcript), original);
  assert.equal(enriched.length, f.transcript.length + 1);
  assert.deepEqual(enriched[anchor + 1], notice);
  assert.deepEqual(enriched[anchor + 2], f.transcript[anchor + 1],
    'The note stays at the confirmed result instead of following newer actions');
  const repeated = f.hooks.get('context')({messages:enriched}, f.ctx).messages;
  assert.deepEqual(repeated, enriched, 'A persisted or already inserted notice must not be duplicated');
  assert.equal(f.notices.length, 1, 'Context recovery does not emit or schedule another message');
});

test('Parallel results anchor the notice after native batch order, not the last operation to finish', () => {
  const f = nativeFixture();
  let orderedResults;
  for (let round = 0; round < 3; round++) {
    f.beginTurn();
    const assistant = f.transcript.at(-1);
    orderedResults = [0, 1].map(index => {
      const event = read(index, round + 1);
      const toolCallId = `parallel-${round}-${index}`;
      assistant.content.push({type:'toolCall', id:toolCallId, name:'read', arguments:event.input});
      assert.equal(f.hooks.get('tool_call')({toolName:'read', input:event.input}, f.ctx), undefined);
      f.hooks.get('tool_execution_start')({toolCallId, toolName:'read', args:event.input}, f.ctx);
      return {role:'toolResult', toolCallId, toolName:'read', content:event.content, isError:false};
    });
    // Native parallel execution completes B first and A last, then appends
    // results in the assistant's original A/B call order via Promise.all.
    for (const result of [...orderedResults].reverse()) {
      f.hooks.get('tool_execution_end')({toolCallId:result.toolCallId,
        toolName:'read', isError:false, result:{content:result.content}}, f.ctx);
    }
    f.transcript.push(...orderedResults);
    f.hooks.get('turn_end')({message:assistant, toolResults:orderedResults}, f.ctx);
  }
  assert.equal(f.notices.length, 1);
  const notice = f.notices[0][0];
  assert.equal(notice.details.afterToolCallId, orderedResults.at(-1).toolCallId);
  const enriched = f.hooks.get('context')({messages:f.transcript}, f.ctx).messages;
  assert.deepEqual(enriched.slice(-3), [...orderedResults, notice],
    'The custom notice must follow the whole native tool-result batch');
  assert.deepEqual(f.notices[0][1], {triggerTurn:false});
});

test('Context delivery skips absent anchors and clears stale notices at real-input and compaction boundaries', () => {
  for (const boundary of ['missing-anchor', 'input', 'session_compact', 'session_start']) {
    const f = nativeFixture();
    runNativeCycle(f);
    let messages = f.transcript;
    if (boundary === 'missing-anchor') messages = [{role:'user', content:'A compacted handover without the old tool result.'}];
    else if (boundary === 'input') f.input('A different request.');
    else f.hooks.get(boundary)({}, f.ctx);
    const original = JSON.stringify(messages);
    const result = f.hooks.get('context')({messages}, f.ctx).messages;
    assert.equal(JSON.stringify(messages), original);
    assert.deepEqual(result, messages, boundary);
  }
});
