import fs from 'node:fs';
import assert from 'node:assert/strict';
const source=fs.readFileSync(new URL('../pi-context-policy.js',import.meta.url),'utf8');
const {prepareLoopCompaction}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const entries=[{type:'message',message:{role:'user'}},{type:'custom_message',customType:'launcher-loop-stop'},{type:'message',message:{role:'assistant',stopReason:'error'}}];
const make=(branchEntries=entries,reason='manual')=>({reason,branchEntries,preparation:{settings:{keepRecentTokens:20000}}});
const event=make();
assert.equal(prepareLoopCompaction(event,(branch,settings)=>{
 assert.equal(branch,entries);assert.equal(settings.keepRecentTokens,0);return {firstKeptEntryId:'native-cut'};
}),true);
assert.equal(event.preparation.firstKeptEntryId,'native-cut');
for(const e of [make([], 'manual'),make(entries,'threshold'),make([...entries,{type:'message',message:{role:'user'}}]),make([...entries,{type:'compaction'}])])
 assert.equal(prepareLoopCompaction(e,()=>{throw Error('Healthy work must keep normal retention')}),false);
if(process.env.LLM_LAUNCHER_PI_INTEGRATION==='1') {
 const {prepareCompaction}=await import('/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/compaction/compaction.js');
 const branch=[];
 const add=(type,extra)=>branch.push({type,...extra,id:String(branch.length),parentId:branch.length?String(branch.length-1):null,timestamp:'2026-01-01T00:00:00Z'});
 add('message',{message:{role:'user',content:'Repair the fixture',timestamp:0}});
 for(let i=0;i<4;i++) {
  add('message',{message:{role:'assistant',content:[{type:'thinking',thinking:'REPEATED_THOUGHT_9182 '.repeat(40)},{type:'toolCall',id:'call'+i,name:'read',arguments:{path:'fixture.js'}}],stopReason:'toolUse',timestamp:i+1}});
  add('message',{message:{role:'toolResult',toolCallId:'call'+i,toolName:'read',content:[{type:'text',text:'Confirmed file output'}],isError:false,timestamp:i+1}});
 }
 add('custom_message',{customType:'launcher-loop-stop',content:'Repeated action paused',display:true});
 add('message',{message:{role:'assistant',content:[],stopReason:'aborted',errorMessage:'Aborted',timestamp:8}});
 const test=make(branch);test.preparation.settings={enabled:true,reserveTokens:4096,keepRecentTokens:20000};
 assert.equal(prepareLoopCompaction(test,prepareCompaction),true);
 const retained=branch.slice(branch.findIndex(e=>e.id===test.preparation.firstKeptEntryId));
 assert.ok(!JSON.stringify(retained).includes('REPEATED_THOUGHT_9182'));
 assert.ok(JSON.stringify(test.preparation.messagesToSummarize).includes('Repair the fixture'));
 assert.ok(JSON.stringify(test.preparation.messagesToSummarize).includes('Confirmed file output'));
}
console.log('Loop compaction uses native bookkeeping and excludes the stale reasoning tail');
