import fs from 'node:fs';
import assert from 'node:assert/strict';
import install, {reasoningRepetition,recoveredReasoningContext,cleanCompactionReasoning} from '../pi-workflow.js';
import {LEGACY_REASONING_MARKER, createContextRecovery} from '../pi_context_recovery.js';
const motif=fs.readFileSync(new URL('./fixtures/pi-reasoning/audio-loop.txt',import.meta.url),'utf8').trim();
const loop=(motif+'\n\n').repeat(24);
assert.equal(reasoningRepetition(loop),true,'The observed alternating short-paragraph loop must be recognized');
assert.equal(reasoningRepetition(motif),false,'A single discussion is legitimate thinking');
assert.equal(reasoningRepetition('```js\n'+loop+'\n```'),false,'Quoted code is excluded');
const distinct=Array.from({length:30},(_,i)=>motif.split('\n\n').map(p=>p+` Measurement ${i}: value ${i*17}.`).join('\n\n')).join('\n\n');
assert.equal(reasoningRepetition(distinct),false,'Changing observations are not a verbatim cycle');
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
