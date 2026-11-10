import fs from 'node:fs';
import assert from 'node:assert/strict';
import install, {reasoningRepetition,recoveredReasoningContext,cleanCompactionReasoning} from '../pi-workflow.js';
import {LEGACY_REASONING_MARKER, createContextRecovery, reasoningDigitRun, exhaustedThinkingOnly} from '../pi_context_recovery.js';
const motif=fs.readFileSync(new URL('./fixtures/pi-reasoning/audio-loop.txt',import.meta.url),'utf8').trim();
const loop=(motif+'\n\n').repeat(24);
assert.equal(reasoningRepetition(loop),true,'The observed alternating short-paragraph loop must be recognized');
assert.equal(reasoningRepetition(motif),false,'A single discussion is legitimate thinking');
assert.equal(reasoningRepetition('```js\n'+loop+'\n```'),false,'Quoted code is excluded');
const distinct=Array.from({length:30},(_,i)=>motif.split('\n\n').map(p=>p+` Measurement ${i}: value ${i*17}.`).join('\n\n')).join('\n\n');
assert.equal(reasoningRepetition(distinct),false,'Changing observations are not a verbatim cycle');
const kolibriShortLoop = Array(80).fill("We'll use the read tool to read the current directory? No.").join('\n\n');
assert.equal(reasoningRepetition(kolibriShortLoop),true,'Repeated short Kolibri reasoning must not escape the fallback guard');
assert.equal(reasoningRepetition('```text\n'+kolibriShortLoop+'\n```'),false,'Quoted short repetitions are excluded');
const kolibriAborted = {role:'assistant',stopReason:'aborted',content:[{type:'thinking',thinking:kolibriShortLoop}]};
assert.deepEqual(recoveredReasoningContext([kolibriAborted]),[], 'An aborted thinking-only loop must not be replayed on resume');
assert.equal(kolibriAborted.content[0].thinking,kolibriShortLoop,'The original saved reasoning stays intact');
const healthyLead = Array.from({length:50},(_,i)=>`Observation ${i}: Compare the measured rendering result with sample ${i*17} before choosing the next implementation step.`).join('\n\n');
const lateKolibriLoop = healthyLead + '\n\n```js\n' + 'const distinctSource = 1;\n'.repeat(80) + '\n```\n\n'
  + Array(35).fill("We'll use the read tool to read the current directory? No.").join('\n\n');
assert.equal(reasoningRepetition(lateKolibriLoop),true,'Useful planning before a short repeated tail must not conceal the loop');
assert.equal(reasoningRepetition(healthyLead),false,'Long useful planning stays intact');
const call={type:'toolCall',id:'real-read',name:'read',arguments:{path:'fixture.js'}};
const original={role:'assistant',content:[{type:'thinking',thinking:loop},call]};
const result={role:'toolResult',toolCallId:'real-read',content:[{type:'text',text:'Observed source'}]};
const cleaned=recoveredReasoningContext([original,result]);
assert.deepEqual(cleaned[0].content,[call]);assert.equal(cleaned[1],result);
assert.equal(original.content[0].thinking,loop,'Saved transcript remains intact');
const echo={role:'assistant',timestamp:72,content:[
  {type:'thinking',thinking:'\n'+LEGACY_REASONING_MARKER+'\n'},
  {type:'text',text:LEGACY_REASONING_MARKER},call]};
const quoted={role:'user',content:[{type:'text',text:LEGACY_REASONING_MARKER}]};
const normal={role:'assistant',content:[{type:'thinking',thinking:'Compare the two observed results.'},{type:'text',text:'Verified answer.'}]};
assert.deepEqual(recoveredReasoningContext([echo,result,quoted,normal]),[
  {...echo,content:[call]},result,quoted,normal]);
assert.equal(echo.content.length,3,'Saved echoes remain intact');
assert.deepEqual(recoveredReasoningContext([{...echo,content:echo.content.slice(0,2)}]),[],
  'A synthetic-only assistant turn must not teach another empty answer');
const recovery=createContextRecovery();
assert.equal(recovery.sessionId('pi-session'),'pi-session');
recovery.recover([echo,result]);
const repairedSession=recovery.sessionId('pi-session');
assert.match(repairedSession,/^pi-session:recovery:[0-9a-f]{24}$/);
recovery.recover(JSON.parse(JSON.stringify([echo,result,normal])));
assert.equal(recovery.sessionId('pi-session'),repairedSession,'Healthy continuations reuse the repaired cache');
recovery.recover([echo,result,{...echo,timestamp:73}]);
assert.notEqual(recovery.sessionId('pi-session'),repairedSession,'New damaged history cannot inherit the old committed reasoning');
recovery.reset();
assert.equal(recovery.sessionId('other-session'),'other-session');
const hooks=new Map();let aborts=0;const notices=[];
install({on:(n,f)=>hooks.set(n,f),getActiveTools:()=>['read'],sendMessage:(...v)=>notices.push(v)});
const sent=hooks.get('context')({messages:[original,result]});
assert.deepEqual(sent.messages,cleaned,'Clean the actual next model request, not just the visible transcript');
const headers={'x-mtplx-client':'pi'};
const headerContext={sessionManager:{getSessionId:()=> 'pi-session'}};
hooks.get('before_provider_headers')({headers},headerContext);
const privateRecovery=headers['x-llm-launcher-mtplx-recovery'];
assert.match(privateRecovery,/^pi-session:recovery:[0-9a-f]{24}$/);
headers['x-mtplx-session-id']='pi-session'; // Installed global Pi extension runs last.
assert.equal(headers['x-llm-launcher-mtplx-recovery'],privateRecovery);
hooks.get('session_start')({}, {sessionManager:{getBranch:()=>[
  {type:'message',message:quoted}, {type:'message',message:echo},
]}});
assert.equal(notices.at(-1)[0].customType,'launcher-loop-stop',
  'A saved synthetic echo must enable the same native compaction recovery as a long loop');
hooks.get('before_provider_headers')({headers},headerContext);
assert.equal(headers['x-llm-launcher-mtplx-recovery'],undefined,'New sessions cannot inherit recovery affinity');
const noticeCount=notices.length;
hooks.get('session_start')({}, {sessionManager:{getBranch:()=>[
  {type:'message',message:echo}, {type:'compaction'}, {type:'message',message:normal},
]}});
assert.equal(notices.length,noticeCount,'Already compacted damage must not pause a healthy session');
const prep={messagesToSummarize:[original,result],turnPrefixMessages:[original]};cleanCompactionReasoning(prep);
assert.deepEqual(prep.messagesToSummarize,cleaned);
hooks.get('message_start')({message:{role:'assistant'}});
let firstAbort=0;
for(let n=512;n<loop.length;n+=512){hooks.get('message_update')({message:{role:'assistant',content:[{type:'thinking',thinking:loop.slice(0,n)}]}},{abort:()=>{aborts++;firstAbort=n;}});}
assert.equal(aborts,1);assert.ok(firstAbort<8000,'Catch this cycle well before the 16K-token budget');
assert.equal(notices.at(-1)[1].triggerTurn,false);
console.log('Observed Qwopus feedback regression passed; first stop at',firstAbort,'characters');

// Splash generated an unbroken invented fractal coordinate until all 32K
// output tokens were spent. Use deterministic synthetic digits, not the saved
// user conversation, and exercise streaming, resume, and compaction cleanup.
let seed = 1729;
const digits = Array.from({length: 12000}, () => {
  seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
  return String(seed % 10);
}).join('');
const numeric = 'Choose a useful fractal coordinate: -0.' + digits;
assert.equal(reasoningDigitRun(numeric), true);
assert.equal(reasoningRepetition(numeric), false, 'This regression is not a repeated paragraph');
for (const healthy of [digits.slice(0, 4095), '```text\n' + digits + '\n```',
  digits.match(/.{1,16}/g).join('\n'), distinct]) {
  assert.equal(reasoningDigitRun(healthy), false, 'Normal precision, code, tables and prose are unaffected');
}
const damaged = {...original, content:[{type:'thinking', thinking:numeric}, call]};
const finalDigits = {role:'assistant',content:[{type:'text',text:numeric}]};
const userDigits = {role:'user',content:[{type:'text',text:numeric}]};
assert.deepEqual(recoveredReasoningContext([damaged,result,finalDigits,userDigits]),[
  {...damaged,content:[call]},result,finalDigits,userDigits,
]);
assert.equal(damaged.content[0].thinking, numeric, 'Saved reasoning stays intact');
const numericPrep = {messagesToSummarize:[damaged,result],turnPrefixMessages:[damaged]};
cleanCompactionReasoning(numericPrep);
assert.deepEqual(numericPrep.turnPrefixMessages[0].content, [call]);
hooks.get('message_start')({message:{role:'assistant'}});
let numericAborts = 0, stoppedAt = 0;
for (let n=512; n<numeric.length; n+=512) {
  hooks.get('message_update')({message:{role:'assistant',content:[{type:'thinking',thinking:numeric.slice(0,n)}]}},
    {abort:()=>{numericAborts++;stoppedAt=n;}});
}
assert.equal(numericAborts, 1);
assert.ok(stoppedAt < 5000, 'Stop the digit stream well before 32K output tokens');
assert.match(notices.at(-1)[0].content, /unbroken stream of digits/);
assert.match(notices.at(-1)[0].content, /Send “continue”/);
assert.equal(notices.at(-1)[1].triggerTurn, false, 'No automatic task replay');
hooks.get('session_start')({}, {sessionManager:{getBranch:()=>[
  {type:'message',message:{role:'user',content:'Create a fractal viewer'}},
  {type:'message',message:damaged},
]}});
assert.equal(notices.at(-1)[0].customType, 'launcher-loop-stop');
assert.equal(notices.at(-1)[0].details.recovery, 'numeric-retry');
const retryNotice = notices.at(-1)[0];
const beforeReload = notices.length;
hooks.get('session_start')({}, {sessionManager:{getBranch:()=>[
  {type:'message',message:{role:'user',content:'Create a fractal viewer'}},
  {type:'message',message:damaged}, {type:'custom_message',...retryNotice},
]}});
assert.equal(notices.length, beforeReload, 'A reload must not duplicate the direct-retry notice');
console.log('Splash numeric runaway stops at', stoppedAt, 'characters; retry and compaction omit damaged thinking.');

// Semantic looping changes its wording, so phrase matching cannot qualify it.
// A terminal thinking-only length stop is objective evidence of a failed turn.
const exhausted = {role:'assistant', stopReason:'length', content:[
  {type:'thinking', thinking:distinct}, {type:'text', text:' '},
]};
assert.equal(exhaustedThinkingOnly(exhausted), true);
assert.deepEqual(recoveredReasoningContext([normal, exhausted, result]), [normal, result]);
assert.equal(exhausted.content.length, 2, 'The failed transcript stays saved');
for (const healthy of [{...exhausted, stopReason:'stop'},
  {...exhausted, content:[...exhausted.content, call]},
  {...exhausted, content:[...exhausted.content, {type:'text', text:'Partial answer'}]}]) {
  assert.equal(exhaustedThinkingOnly(healthy), false);
  assert.deepEqual(recoveredReasoningContext([healthy]), [healthy]);
}
const lengthPrep = {messagesToSummarize:[normal, exhausted], turnPrefixMessages:[exhausted]};
cleanCompactionReasoning(lengthPrep);
assert.deepEqual(lengthPrep, {messagesToSummarize:[normal], turnPrefixMessages:[]});
