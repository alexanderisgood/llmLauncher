import fs from 'node:fs';
import assert from 'node:assert/strict';
const source=fs.readFileSync(new URL('../pi-workflow.js',import.meta.url),'utf8');
const {default:install,malformedToolAnswer}=await import('../pi-workflow.js');
const events=new Map(), messages=[];
install({on:(k,v)=>events.set(k,v),sendMessage:(...args)=>messages.push(args),getActiveTools:()=>['bash','read']});
const before=events.get('before_agent_start')({systemPrompt:'Original instructions'});
assert.match(before.systemPrompt,/Original instructions/);
assert.match(before.systemPrompt,/real entry point/);
function call(id,name,args={}) {events.get('tool_execution_start')({toolCallId:id,toolName:name,args});events.get('tool_execution_end')({toolCallId:id,isError:false});}
function inspectionFixture(request) {
  const hooks=new Map(), notices=[];
  let executions=0, aborts=0;
  install({on:(name,hook)=>hooks.set(name,hook),sendMessage:(...args)=>notices.push(args),
    getActiveTools:()=>['bash','read','web_search']});
  hooks.get('input')({source:'rpc',text:request});
  hooks.get('before_agent_start')({systemPrompt:''});
  return {notices, get executions(){return executions;}, get aborts(){return aborts;},
    run(name,input,text) {
      const decision=hooks.get('tool_call')({toolName:name,input},{abort:()=>aborts++});
      if(decision?.block) return decision;
      const toolCallId=++executions;
      hooks.get('tool_execution_start')({toolCallId,toolName:name,args:input});
      hooks.get('tool_execution_end')({toolCallId,isError:false,result:{content:[{type:'text',text}]}});
      return decision;
    },
  };
}
{
  const f=inspectionFixture('Improve the renderer using the existing implementation.');
  // The observed false positive followed reads of different renderer sections.
  for(let i=0;i<36;i++) {
    const args=i%2 ? {command:`cd /tmp/project && grep -n 'field${i}|method${i}' game.js | head -40`}
      : {path:'game.js',offset:100+i*80,limit:80};
    assert.equal(f.run(i%2 ? 'bash' : 'read',args,`New renderer section ${i}`),undefined);
  }
  assert.equal(f.executions,36);
  assert.equal(f.aborts,0);
  assert.deepEqual(f.notices,[], 'Distinct source inspections must not add a count-based steering turn');
}
{
  const f=inspectionFixture('Investigate the changing build output.');
  for(let i=0;i<16;i++) assert.equal(f.run('read',{path:'build.log'},`Build advanced to stage ${i}`),undefined);
  assert.equal(f.executions,16);
  assert.deepEqual(f.notices,[], 'Repeated call arguments with changing results are new evidence');
}
{
  const f=inspectionFixture('Research the API and review the code. Do not edit files.');
  for(let i=0;i<16;i++) {
    assert.equal(f.run('web_search',{query:`API specification section ${i}`},`Specification evidence ${i}`),undefined);
    assert.equal(f.run('read',{path:`module-${i}.js`},`Relevant implementation ${i}`),undefined);
  }
  assert.equal(f.executions,32);
  assert.deepEqual(f.notices,[], 'Read-only research must not be steered toward editing or explaining its read count');
}
{
  const f=inspectionFixture('Monitor the build log.');
  for(let i=0;i<16;i++) assert.equal(f.run('read',{path:'build.log'},'Build still running'),undefined);
  assert.equal(f.executions,16);
  assert.equal(f.aborts,0);
  assert.deepEqual(f.notices,[], 'Explicit monitoring permits unchanged results without progress nudges');
}
{
  const f=inspectionFixture('Implement and validate the fix.');
  for(let i=0;i<16;i++) {
    f.run('read',{path:`scenario-${i}.js`},`Scenario ${i}`);
    f.run('bash',{command:'cd /tmp/project && node test.js'},`Verified scenario ${i}`);
  }
  assert.equal(f.executions,32);
  assert.deepEqual(f.notices,[], 'Successful checks must not depend on a shell-prefix classifier');
}
{
  const f=inspectionFixture('Investigate the renderer.');
  for(let i=0;i<3;i++) assert.equal(f.run('read',{path:'game.js'},'Unchanged source'),undefined);
  assert.equal(f.run('read',{path:'game.js'},'Unchanged source')?.block,true);
  assert.equal(f.executions,3, 'The fourth identical call must be blocked before execution');
  assert.equal(f.aborts,1);
  assert.equal(f.notices.length,1);
  assert.equal(f.notices[0][0].customType,'launcher-loop-stop');
  assert.equal(f.notices[0][1].triggerTurn,false, 'A confirmed duplicate loop must not automatically retry');
}
console.log('Useful inspections do not trigger steering; identical-result loop protection remains active');
const broken={role:'assistant',stopReason:'stop',content:[{type:'text',text:'{"name": "bash",\n\ntail -30 game_test.js\n'}]};
assert.equal(malformedToolAnswer(broken,['bash']),true);
for (const msg of [
  {...broken,stopReason:'aborted'}, {...broken,stopReason:'error'}, {...broken,stopReason:'length'},
  {...broken,content:[...broken.content,{type:'toolCall',name:'bash'}]},
  {...broken,content:[{type:'text',text:'Example: '+broken.content[0].text}]},
  {...broken,content:[{type:'text',text:'```json\n'+broken.content[0].text+'```'}]},
]) assert.equal(malformedToolAnswer(msg,['bash']),false);
assert.equal(malformedToolAnswer(broken,['read']),false);
const printedCall = {...broken,content:[{type:'text',text:'{"name":"bash","arguments":{"command":"ls"}}'}]};
assert.equal(malformedToolAnswer(printedCall,['bash']),true, 'Valid JSON printed in a final answer never executed');
const truncatedEdit = (await import('node:fs')).readFileSync(new URL('./fixtures/pi-reasoning/truncated-edit-final.txt', import.meta.url),'utf8');
assert.throws(()=>JSON.parse(truncatedEdit));
assert.equal(malformedToolAnswer({...broken,content:truncatedEdit},['edit']),true,'The actual missing-brace edit must be recognized');
assert.equal(malformedToolAnswer({...broken,content:'{"arguments":{"command":"ls"},"name":"bash"}'},['bash']),true);
for (const text of ['{"name":"bash"}', '{"name":"bash","arguments":null}',
 '{"name":"bash","arguments":{},"description":"example data"}',
 'Example: {"name":"bash","arguments":{}}', '```json\n{"name":"bash","arguments":{}}\n```']) {
 assert.equal(malformedToolAnswer({...broken,content:[{type:'text',text}]},['bash']),false);
}
const {requestsLiteralToolOutput} = await import('../pi-workflow.js');
for (const text of ['Fix config.json and continue.', 'Repair the JSON parser.',
 'The launcher repaired processor_config.json; continue implementation.']) {
 assert.equal(requestsLiteralToolOutput(text),false);
}
for (const text of ['Show an example of invalid JSON', 'Return only JSON', 'Explain the tool syntax', 'Repeat this verbatim']) {
 assert.equal(requestsLiteralToolOutput(text),true);
}
events.get('input')({source:'rpc',text:'replace'});
const base=messages.length;
for(let i=0;i<5;i++) {
  events.get('before_agent_start')({systemPrompt:''});
  events.get('message_end')({message:broken});
}
assert.equal(messages.length-base,3,'two retries and one terminal warning; no retry loop');
assert.deepEqual(messages[base][1],{deliverAs:'steer',triggerTurn:true});
assert.equal(messages[base+2][1].triggerTurn,false);
events.get('input')({source:'extension',text:'continue'});
events.get('message_end')({message:broken});
assert.equal(messages.length-base,3,'extension continuation cannot reset the retry cap');
events.get('input')({source:'rpc',text:'Show an example of invalid JSON'});
events.get('message_end')({message:broken});
assert.equal(messages.length-base,3,'literal examples must not trigger recovery');
events.get('input')({source:'rpc',text:'try the replacement again'});
events.get('message_end')({message:broken});
assert.equal(messages.length-base,4,'a real new request can retry');
console.log('Malformed-tool recovery, safe exclusions and retry bounds passed');
{
 const handlers=new Map(), retries=[];
 install({on:(name,handler)=>handlers.set(name,handler),sendMessage:(...args)=>retries.push(args),getActiveTools:()=>['bash']});
 handlers.get('input')({source:'rpc',text:'Fix config.json and continue the task.'});
 handlers.get('message_end')({message:printedCall});
 assert.equal(retries.length,1);
 assert.equal(retries[0][1].triggerTurn,true);
 assert.match(retries[0][0].content,/did not execute/);
 handlers.get('input')({source:'rpc',text:'Return only JSON'});
 handlers.get('message_end')({message:printedCall});
 assert.equal(retries.length,1,'An explicitly requested literal JSON response remains an answer');
}
// Separate malformed episodes within one long task used to exhaust a single
// lifetime counter, even when recovery executed real tools in between.
const episodeEvents=new Map(), episodeMessages=[];
install({on:(k,v)=>episodeEvents.set(k,v),sendMessage:(...args)=>episodeMessages.push(args),getActiveTools:()=>['bash']});
episodeEvents.get('input')({source:'rpc',text:'Complete the task'});
function episodeResult(id,isError=false,withResult=true) {
 episodeEvents.get('tool_execution_start')({toolCallId:id,toolName:'bash',args:{command:'fixture '+id}});
 episodeEvents.get('tool_execution_end')({toolCallId:id,isError,
  ...(withResult?{result:{content:[{type:'text',text:'result '+id}]}}:{})});
}
for(let i=0;i<6;i++) {
 episodeEvents.get('message_end')({message:broken});
 assert.equal(episodeMessages.at(-1)[1].triggerTurn,true,'Successful recovery must allow a later independent retry');
 episodeResult(i);
 episodeEvents.get('before_agent_start')({systemPrompt:''});
 episodeEvents.get('session_compact')();
 episodeEvents.get('input')({source:'extension',text:'Continue'});
}
episodeEvents.get('message_end')({message:broken});
assert.equal(episodeMessages.length,7);
assert.match(episodeMessages.at(-1)[0].content,/six tool-format retries/);
assert.equal(episodeMessages.at(-1)[1].triggerTurn,false,'Successful calls must not bypass the total ceiling');
episodeEvents.get('message_end')({message:broken});
assert.equal(episodeMessages.length,7,'Terminal warning appears once');
episodeEvents.get('input')({source:'rpc',text:'Try again'});
episodeEvents.get('message_end')({message:broken});
episodeResult('failed',true);
episodeEvents.get('message_end')({message:broken});
episodeResult('missing',false,false);
episodeEvents.get('message_end')({message:broken});
assert.match(episodeMessages.at(-1)[0].content,/two attempts without a successful tool result/);
assert.equal(episodeMessages.at(-1)[1].triggerTurn,false);
console.log('Independent format recovery episodes, failed-result handling and prompt-wide ceiling passed');
const {recoveredToolContext,toolRecoveryGuidance}=await import('../pi-workflow.js');
const recovery={role:'custom',customType:'launcher-tool-format-recovery',content:'Retry'};
const terminal={role:'custom',customType:'launcher-tool-format-error',content:'Stopped'};
const valid={...broken,stopReason:'toolUse',content:[{type:'toolCall',name:'read',arguments:{path:'a'}}]};
const result={role:'toolResult',content:[{type:'text',text:'Confirmed result'}]};
const failedHistory=[valid,result,broken,recovery,terminal,broken];
const originalHistory=JSON.stringify(failedHistory);
const healed=recoveredToolContext(failedHistory,['bash','read']);
assert.equal(JSON.stringify(failedHistory),originalHistory,'Saved entries must never be mutated');
assert.equal(healed[0],valid);assert.equal(healed[1],result);
assert.match(healed[2].content[0].text,/No tool ran/);
assert.match(healed[5].content[0].text,/No tool ran/);
assert.equal(recoveredToolContext([broken],['bash'])[0],broken,'Unflagged examples stay intact');
assert.equal(recoveredToolContext([recovery,{role:'user',content:'Show syntax'},broken],['bash'])[2],broken,
 'Do not cross a user message when identifying failed retries');
assert.match(toolRecoveryGuidance({model:{name:'qwopus3.8-mxfp4'}}),/<tool_call>/);
assert.doesNotMatch(toolRecoveryGuidance({model:{name:'Other model'}}),/<tool_call>/);
console.log('Failed-tool context cleanup preserves saved history, confirmed results and unflagged examples');
let aborted=0;
const action={toolName:'bash',input:{command:'copy-and-check'}};
function completeSame(id,text='verified') {
  events.get('tool_execution_start')({toolCallId:id,toolName:action.toolName,args:action.input});
  events.get('tool_execution_end')({toolCallId:id,isError:false,result:{content:[{type:'text',text}]}});
}
events.get('input')({source:'rpc',text:'Apply the replacement'});
for(let i=0;i<3;i++) {
  assert.equal(events.get('tool_call')(action,{abort:()=>aborted++}),undefined);
  completeSame(i);
}
assert.equal(events.get('tool_call')(action,{abort:()=>aborted++}).block,true);
assert.equal(aborted,1);
assert.equal(messages.at(-1)[1].triggerTurn,false);
events.get('input')({source:'rpc',text:'Try again'});
for(let i=0;i<5;i++) completeSame(i,'changing result '+i);
assert.equal(events.get('tool_call')(action,{abort:()=>aborted++}),undefined);
events.get('input')({source:'rpc',text:'Monitor the build'});
for(let i=0;i<5;i++) completeSame(i);
assert.equal(events.get('tool_call')(action,{abort:()=>aborted++}),undefined);
console.log('Identical-action loop stop, changed results and explicit monitoring passed');
// Identical native failures are observations too: repeating one must not erase
// the existing consecutive-result limit or disguise failures as successes.
{
  const hooks = new Map(), notices = [];
  let stops = 0;
  install({on:(name,hook)=>hooks.set(name,hook),sendMessage:(...args)=>notices.push(args),getActiveTools:()=>['bash','edit']});
  const check = (input=action.input) => hooks.get('tool_call')({toolName:'bash',input},{abort:()=>stops++});
  const complete = (id, {input=action.input, name='bash', isError=true, text='SyntaxError: Unexpected token', missing=false}={}) => {
    hooks.get('tool_execution_start')({toolCallId:id,toolName:name,args:input});
    const result = {content:[{type:'text',text}]};
    hooks.get('tool_execution_end')({toolCallId:id,isError,...(missing ? {} : {result})});
    assert.deepEqual(result.content,[{type:'text',text}], 'Preserve the actual native failure text');
  };
  const fresh = () => hooks.get('input')({source:'rpc',text:'Repair the implementation'});
  fresh();
  for (let i=0; i<3; i++) { assert.equal(check(),undefined); complete(i); }
  assert.equal(check()?.block,true,'A fourth identical failing call must be blocked');
  assert.equal(stops,1);
  assert.match(notices.at(-1)[0].content,/three identical failures/);
  assert.doesNotMatch(notices.at(-1)[0].content,/successful/);
  assert.equal(notices.at(-1)[1].triggerTurn,false);
  fresh();
  for (let i=0; i<3; i++) complete(i);
  assert.equal(check({command:'corrected-check'}),undefined,'Changed input is a new attempt');
  complete('changed-input',{input:{command:'corrected-check'}});
  assert.equal(check(),undefined,'An intervening different call resets the streak');
  fresh();
  for (let i=0; i<5; i++) complete(i,{text:`Failure at a different stage ${i}`});
  assert.equal(check(),undefined,'Changed failure results are new evidence');
  fresh();
  for (let i=0; i<3; i++) complete(i);
  complete('repair',{name:'edit',input:{path:'fixture.js',oldText:'bad',newText:'fixed'},isError:false,text:'Edited fixture.js'});
  assert.equal(check(),undefined,'An intervening corrective edit permits another check');
  fresh();
  complete(1); complete(2); complete(3,{isError:false});
  assert.equal(check(),undefined,'Equal text with different failure status is not an identical result');
  fresh();
  complete(1); complete(2); complete(3,{missing:true}); complete(4);
  assert.equal(check(),undefined,'A missing result cannot establish a repeated failure');
  hooks.get('input')({source:'rpc',text:'Monitor this operation'});
  for (let i=0; i<5; i++) complete(i);
  assert.equal(check(),undefined,'The existing explicit monitoring exemption is preserved');
}
console.log('Identical native failure limit, unchanged error evidence and corrective-action resets passed');
const {unfinishedActionAnswer}=await import('../pi-workflow.js');
const promise={role:'assistant',stopReason:'stop',content:[{type:'text',text:'Now I understand the requirements. Let me implement the fixes:\n\n'}]};
assert.equal(unfinishedActionAnswer(promise),true);
for(const text of ['Implemented the fixes and all tests pass.','If you approve, I will implement the fixes.',
  'I could write the implementation.','```\nLet me implement the fixes:\n```','Here is the implementation: {}'])
 assert.equal(unfinishedActionAnswer({...promise,content:text}),false);
assert.equal(unfinishedActionAnswer({...promise,stopReason:'error'}),false);
assert.equal(unfinishedActionAnswer({...promise,content:[...promise.content,{type:'toolCall',name:'write'}]}),false);
events.get('input')({source:'rpc',text:'Repair the implementation'});
const actionBase=messages.length;
events.get('message_end')({message:promise});
assert.equal(messages.length,actionBase,'Only recover after the agent has actually started tool work');
call('action-read','read',{path:'a'});
for(let i=0;i<4;i++) {
 events.get('before_agent_start')({systemPrompt:''});
 events.get('input')({source:'extension',text:'Continue'});
 events.get('message_end')({message:promise});
}
assert.equal(messages.length,actionBase+1,'Only one premature-stop recovery, even across automatic turns');
assert.match(messages.at(-1)[0].content,/Action recovery/);
for(const text of ['Give me a plan only','Do not implement it','Show an example']) {
 events.get('input')({source:'rpc',text});call('plan-read','read',{path:'a'});
 events.get('message_end')({message:promise});
}
assert.equal(messages.length,actionBase+1,'Planning and example requests do not trigger actions');
console.log('Premature action preamble recovery and safe retry cap passed');
for(const text of ['{"name": "run_tests>\n','{"name": "run_tests','{"name": "run_tests"'])
 assert.equal(malformedToolAnswer({...broken,content:text},['run_tests']),true);
assert.equal(malformedToolAnswer({...broken,content:'{"name":"run_tests"}'},['run_tests']),false);
assert.equal(malformedToolAnswer({...broken,content:'{"name":"run_tests_extra>\n'},['run_tests']),false);
console.log('Truncated tool-name recovery respects the exact active tool set');
events.get('input')({source:'rpc',text:'Repair the implementation. Do not change tests.'});
call('protected-tests','read',{path:'a'});
const protectedBase=messages.length;
events.get('message_end')({message:promise});
assert.equal(messages.length,protectedBase+1,'Protecting tests does not prohibit the requested implementation');
const {reasoningRepetition,recoveredReasoningContext}=await import('../pi-workflow.js');
const paragraph='The scheduler should select the oldest waiting job before looking at newer arrivals. However the observed execution order contradicts that expectation, so we need to inspect the recorded timestamps and test the queue directly rather than assume the priority calculation is correct. The worker might be using an outdated snapshot of the pending jobs.';
const loop=(paragraph+'\n\n').repeat(12);
assert.equal(reasoningRepetition(loop),true);
assert.equal(reasoningRepetition(paragraph),false);
assert.equal(reasoningRepetition('same token '.repeat(10000)),false,'Short token runs are outside this conservative prose guard');
assert.equal(reasoningRepetition('```text\n'+loop+'```'),false,'Fenced material is not a reasoning loop');
const unique=Array.from({length:40},(_,i)=>`Case ${i}: ${paragraph} The measured delay is ${i*13} milliseconds.`).join('\n\n');
assert.equal(reasoningRepetition(unique),false,'Repeated structure with changing results is progress');
const loopingMessage={role:'assistant',stopReason:'toolUse',content:[{type:'thinking',thinking:loop},...valid.content]};
const cleanReasoning=recoveredReasoningContext([loopingMessage,result]);
assert.equal(loopingMessage.content[0].thinking,loop,'Do not mutate saved reasoning');
assert.equal(cleanReasoning[0].content[0],valid.content[0],'Keep real tool calls and their IDs');
assert.equal(cleanReasoning[1],result);
assert.deepEqual(cleanReasoning[0].content,valid.content,'Do not insert a synthetic assistant answer');
events.get('message_start')({message:{role:'assistant'}});
const loopBase=messages.length;let streamAborts=0;
for(let length=512;length<=loop.length;length+=512)events.get('message_update')({message:{role:'assistant',content:[{type:'thinking',thinking:loop.slice(0,length)}]}},{abort:()=>streamAborts++});
assert.equal(streamAborts,1,'Stop once while streaming, before message_end');
assert.equal(messages.length,loopBase+1);assert.equal(messages.at(-1)[0].customType,'launcher-loop-stop');
assert.equal(messages.at(-1)[1].triggerTurn,false,'No automatic retry into the same reasoning loop');
events.get('message_start')({message:{role:'assistant'}});
events.get('message_update')({message:{role:'assistant',content:[{type:'text',text:loop}]}},{abort:()=>streamAborts++});
assert.equal(streamAborts,1,'Requested repetitive answer text is not reasoning');
console.log('Streaming prose-loop interruption, bounded detection and saved-context cleanup passed');
const restoredBranch=[{type:'message',message:{role:'user',content:'Investigate'}},{type:'message',message:loopingMessage}];
let restoreBase=messages.length;
events.get('session_start')({}, {sessionManager:{getBranch:()=>restoredBranch}});
assert.equal(messages.length,restoreBase+1,'A saved unfinished loop gets a compaction marker after restart');
assert.equal(messages.at(-1)[0].customType,'launcher-loop-stop');
for(const suffix of [[{type:'custom_message',customType:'launcher-loop-stop'}],[{type:'message',message:{role:'user',content:'New task'}}],[{type:'compaction'}]]) {
 events.get('session_start')({}, {sessionManager:{getBranch:()=>[...restoredBranch,...suffix]}});
}
assert.equal(messages.length,restoreBase+1,'Do not repeat notices or cross a user/compaction boundary');
const {cleanCompactionReasoning}=await import('../pi-workflow.js');
const bookkeeping={read:new Set(['a']),edited:new Set(['b'])};
const preparation={messagesToSummarize:[loopingMessage,result],turnPrefixMessages:[loopingMessage],fileOps:bookkeeping,firstKeptEntryId:'native-cut'};
cleanCompactionReasoning(preparation);
assert.deepEqual(preparation.messagesToSummarize[0].content,valid.content);
assert.equal(preparation.messagesToSummarize[1],result);
assert.equal(preparation.fileOps,bookkeeping);assert.equal(preparation.firstKeptEntryId,'native-cut');
assert.equal(loopingMessage.content[0].thinking,loop);
console.log('Native summary input cleanup preserves file bookkeeping and original entries');
