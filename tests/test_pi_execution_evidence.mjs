import fs from 'node:fs';
import assert from 'node:assert/strict';
const source=fs.readFileSync(new URL('../pi-workflow.js',import.meta.url),'utf8');
const {default:install,executionEvidence}=await import('../pi-workflow.js');
const pair=(id,output,name='bash')=>[
 {type:'message',message:{role:'assistant',content:[{type:'toolCall',id,name,arguments:{command:'node check.js'}}]}},
 {type:'message',message:{role:'toolResult',toolCallId:id,isError:false,content:[{type:'text',text:output}]}}
];
const branch=[...pair('a','6 passed, 1 FAILED'),...pair('b','6 passed, 1 FAILED'),...pair('c','7 passed')];
const records=executionEvidence(branch);
assert.equal(records.length,2);
assert.equal(records[0].outputTail,'6 passed, 1 FAILED');
assert.equal(records[0].toolError,false,'transport success must not become a test pass');
assert.equal(records[1].outputTail,'7 passed');
assert.equal(executionEvidence(pair('read','noise','read')).length,0);
const large=Array.from({length:30},(_,i)=>pair(String(i),'x'.repeat(3000)+i)).flat();
assert.equal(executionEvidence(large).length,8);
assert.ok(JSON.stringify(executionEvidence(large)).length<9000);
const events=new Map(),sent=[];
install({on:(k,v)=>events.set(k,v),sendMessage:(...args)=>sent.push(args),getActiveTools:()=>['bash']});
events.get('session_compact')({}, {sessionManager:{getBranch:()=>branch}});
assert.equal(sent.length,1);
assert.equal(sent[0][0].display,false);
assert.equal(sent[0][1].triggerTurn,false,'memory must not start an unsolicited turn');
assert.match(sent[0][0].content,/1 FAILED/);
const saved={type:'custom_message',...sent[0][0]};
assert.deepEqual(executionEvidence([saved]),records,'survives another compaction or restart');
console.log('Execution evidence preserves exact failed and changed outcomes with bounded context.');
