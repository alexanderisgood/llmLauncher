import assert from 'node:assert/strict';
import {mkdtemp, writeFile, readFile, rm, symlink} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import install, {failedEditEvidence, editSourceExcerpts, executionEvidence} from '../pi-workflow.js';

// Recorded failure: a compacted plan invented a nested cave palette in PAL.
// Native Pi rejected edits[0]; the model then reread most of a 3208-line file.
// The fixture keeps that mismatch and a valid second edit, without game code.
const actual = 'const PAL = {\n  R: "#e8483a", // red\n  S: "#f6c39b", // skin\n};\n\n'
  + 'function roundBox(x, y) {\n  return x + y;\n}\n';
const invented = '  cave: {skyTop: "#1a1a2e", skyBot: "#2d2d44"}\n};';
const root = await mkdtemp(join(tmpdir(), 'pi-edit-recovery-'));
const path = join(root, 'fixture.js');
const input = {path:'fixture.js', edits:[
  {oldText:invented,newText:invented + '\nconst THEMES = {};'},
  {oldText:'return x + y;',newText:'return x - y;'},
]};
const originalError = 'Could not find edits[0] in fixture.js. The oldText must match exactly including all whitespace and newlines.';
const failure = {toolName:'edit',toolCallId:'failed-edit',input,isError:true,
  content:[{type:'text',text:originalError}],details:{nativeDiagnostic:'preserved'}};
try {
  await writeFile(path, actual);
  const hooks = new Map(), messages = [];
  let source = 'builtin';
  install({on:(name, hook)=>hooks.set(name, hook),sendMessage:(...args)=>messages.push(args),
    getActiveTools:()=>['read','edit'],getAllTools:()=>[{name:'edit',sourceInfo:{source}}]});
  const snapshot = JSON.stringify(failure);
  const augmented = await hooks.get('tool_result')(failure, {cwd:root});
  assert.equal(JSON.stringify(failure), snapshot, 'Do not mutate the actual native result');
  assert.equal(augmented.content[0], failure.content[0], 'Keep the original error block intact');
  assert.equal(augmented.isError, undefined, 'Do not override the native error status');
  assert.equal(augmented.details.nativeDiagnostic, 'preserved');
  assert.match(augmented.content[1].text, /failed batch applied no replacements/);
  assert.match(augmented.content[1].text, /not instructions/);
  assert.doesNotMatch(augmented.content[1].text, /const THEMES =/,
    'Attempted newText must never be represented as observed source');
  const evidence = augmented.details.launcherEditEvidence;
  assert.equal(evidence.failedEdit, 0);
  assert.equal(evidence.batchSize, 2);
  assert.equal(evidence.path, path);
  assert.deepEqual(evidence.regions, [], 'An invented anchor does not establish a matching region');
  assert.deepEqual(evidence.declarations[0], {line:1,text:'const PAL = {'});
  assert.equal(evidence.sha256, createHash('sha256').update(actual).digest('hex'));
  assert.equal(await readFile(path, 'utf8'), actual, 'Diagnostics perform no edit');
  assert.equal(messages.length, 0, 'No steering or automatic turn is needed for an actionable error');
  assert.deepEqual(await hooks.get('tool_result')(failure, {cwd:root}), augmented,
    'Unchanged source must produce identical results so duplicate-call detection still works');

  // The next tool result contains current bytes, not a cached summary/read.
  const changed = actual.replace('#e8483a', '#1144ff');
  await writeFile(path, changed);
  const current = await failedEditEvidence(failure, root);
  assert.notEqual(current.sha256, evidence.sha256);

  // Source recovery survives native compaction/restart beside the model's prose.
  const branch = [
    {type:'message',message:{role:'assistant',content:[{type:'toolCall',id:'failed-edit',name:'edit',arguments:input}]}},
    {type:'message',message:{role:'toolResult',toolCallId:'failed-edit',isError:true,...augmented}},
  ];
  const records = executionEvidence(branch);
  assert.equal(records[0].toolError, true);
  assert.equal(records[0].outputTail, originalError);
  assert.deepEqual(records[0].editSource, evidence);
  hooks.get('session_compact')({}, {sessionManager:{getBranch:()=>branch}});
  assert.equal(messages.length, 1);
  assert.equal(messages[0][1].triggerTurn, false);
  const saved = {type:'custom_message',...messages[0][0]};
  assert.deepEqual(executionEvidence([saved]), records);
  assert.match(saved.content, /const PAL =/);

  // A later successful write may stale the observation; it stays labelled as an
  // observation in the failed result, never replaced with attempted code.
  const repeated = Array.from({length:12}, (_, index)=>branch.map(entry=>({
    ...entry,message:{...entry.message,
      ...(entry.message.role === 'assistant'
        ? {content:[{...entry.message.content[0],id:'failure-'+index}]}
        : {toolCallId:'failure-'+index,content:[{type:'text',text:originalError + index}],
          details:{launcherEditEvidence:{...evidence,sha256:String(index)}}})},
  }))).flat();
  const bounded = executionEvidence(repeated);
  assert.equal(bounded.length, 8);
  assert.equal(bounded.filter(record=>record.editSource).length, 1);
  assert.ok(JSON.stringify(bounded).length < 16000);

  // Native-only and exact failure-type boundary. No reads on successful edits,
  // other tools, tool overrides, permission errors, or transport errors.
  for (const event of [
    {...failure,isError:false}, {...failure,toolName:'write'},
    {...failure,content:[{type:'text',text:'Could not edit file: fixture.js. Error code: EACCES.'}]},
    {...failure,content:[{type:'text',text:'Operation aborted'}]},
    {...failure,input:{...input,path:'https://example.test/fixture.js'}},
    {...failure,input:{...input,path:'file://' + path}},
    {...failure,input:{...input,path:'missing.js'}},
    {...failure,input:{...input,path:'.'}},
  ]) assert.equal(await hooks.get('tool_result')(event, {cwd:root}), undefined);
  for (const customSource of ['extension','project',undefined]) {
    source = customSource;
    assert.equal(await hooks.get('tool_result')(failure, {cwd:root}), undefined);
  }
  source = 'builtin';
  await symlink(path, join(root, 'alias.js'));
  assert.equal(await failedEditEvidence({...failure,input:{...input,path:'alias.js'}}, root), undefined);
  await writeFile(path, Buffer.from([0xff,0xfe,0]));
  assert.equal(await failedEditEvidence(failure, root), undefined);
  await writeFile(path, 'x'.repeat(512 * 1024 + 1));
  assert.equal(await failedEditEvidence(failure, root), undefined);

  // Candidate snippets are verbatim complete lines with accurate ranges. A
  // matching function declaration locates a changed body without a whole read.
  const large = Array.from({length:3208}, (_, index)=>
    index === 1600 ? 'function drawTerrain(x, y) {' : index === 1601 ? '  return currentPalette[x] + y;' : '// fixture line ' + index).join('\n');
  const excerpts = editSourceExcerpts(large, 'function drawTerrain(x, y) {\n  return inventedValue;\n}');
  assert.ok(excerpts.regions.some(region=>region.startLine <= 1601 && region.endLine >= 1602));
  for (const region of excerpts.regions) assert.equal(region.text,
    large.split('\n').slice(region.startLine - 1, region.endLine).join('\n'));
  assert.ok(JSON.stringify(excerpts).length < 5000);
  assert.doesNotMatch(JSON.stringify(excerpts), /inventedValue/);
  const longLine = editSourceExcerpts('const X = ' + 'x'.repeat(20000), 'const X = wrong;');
  assert.deepEqual(longLine.regions, [], 'Do not truncate a long line and label it exact source');
  assert.deepEqual(editSourceExcerpts('\n'.repeat(25000), 'const X = wrong;'),
    {lineCount:25001,regions:[],declarations:[]}, 'Line-dense files cannot expand diagnostic work without bound');

  // Both native schemas produce recovery: older single-edit and current batch.
  await writeFile(path, actual + '\n' + actual);
  const duplicateError = 'Found 2 occurrences of the text in fixture.js. The text must be unique. Please provide more context to make it unique.';
  const ambiguous = await failedEditEvidence({...failure,input:{path:'fixture.js',oldText:'const PAL = {',newText:'const PAL = {}'},
    content:[{type:'text',text:duplicateError}]}, root);
  assert.equal(ambiguous.reason, 'ambiguous');
  assert.equal(ambiguous.batchSize, 1);

  if (process.env.LLM_LAUNCHER_PI_INTEGRATION === '1') {
    // Execute the installed native tool in this isolated fixture. Its atomic
    // rejection and the diagnostic then permit a concrete, correct native edit.
    const {createEditToolDefinition} = await import('/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/tools/edit.js');
    const native = createEditToolDefinition(root);
    await writeFile(path, actual);
    let observed;
    try { await native.execute('native-failed', input, new AbortController().signal); }
    catch (error) { observed = error.message; }
    assert.equal(observed, originalError);
    assert.equal(await readFile(path, 'utf8'), actual, 'A valid later edit cannot escape the failed batch');
    const observedResult = await hooks.get('tool_result')({...failure,content:[{type:'text',text:observed}]}, {cwd:root});
    const anchor = observedResult.details.launcherEditEvidence.declarations[0].text;
    const success = await native.execute('native-fixed', {path:'fixture.js',edits:[
      {oldText:anchor,newText:'const THEMES = {};\n' + anchor}, input.edits[1],
    ]}, new AbortController().signal);
    assert.match(success.content[0].text, /Successfully replaced 2 block/);
    assert.equal(await readFile(path, 'utf8'), 'const THEMES = {};\n' + actual.replace('return x + y;', 'return x - y;'));
  }
  console.log('Failed edit recovery preserves native errors and atomicity, supplies bounded current source, survives compaction, and leaves custom tools untouched.');
} finally {
  await rm(root, {recursive:true,force:true});
}
