import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,rm,mkdir,symlink} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createDeliveryProgressCheck,projectSourceFingerprint,implementationRequest,applyBashDeadline} from '../pi_delivery_progress.js';

const execFileAsync=promisify(execFile);

test('Only implementation requests opt in; research and no-edits requests stay out',()=>{
  for(const text of ['Research asset formats','Review this code','Watch the build','Fix proposal, do not change anything']) assert.equal(implementationRequest(text),false,text);
  for(const text of ['Build a file watcher','Implement a file watcher']) assert.equal(implementationRequest(text),true,text);
  assert.equal(implementationRequest('Recreate World 1 in the browser'),true);
});
test('No notice from time alone, tools alone, changed files, or missing observations; one notice per input',async()=>{
  let now=0, hash='a'; const d=createDeliveryProgressCheck({now:()=>now,snapshot:async()=>hash?{hash,files:4}:null});
  d.reset(true);await d.observe('/project');
  now=16*60000;assert.equal(await d.observe('/project',11),undefined);
  now+=60000;assert.deepEqual(await d.observe('/project',1),{minutes:17,completedTools:12,sourceFiles:4});
  now+=900000;assert.equal(await d.observe('/project',30),undefined);
  d.reset(true);await d.observe('/project');now+=900000;hash='b';assert.equal(await d.observe('/project',40),undefined);
  now+=900000;hash=null;assert.equal(await d.observe('/project',40),undefined);
  d.reset(false);hash='c';now+=900000;assert.equal(await d.observe('/project',40),undefined);
});
test('Source fingerprints detect shell edits and new files, ignore asset downloads and scratch files',async()=>{
 const root=await mkdtemp(join(tmpdir(),'delivery-'));
 try{
  await writeFile(join(root,'game.js'),'v1');const a=await projectSourceFingerprint(root);
  await mkdir(join(root,'assets'));await writeFile(join(root,'assets','sprite.png'),'asset');assert.deepEqual(await projectSourceFingerprint(root),a);
  await writeFile(join(root,'game.js'),'v2');const b=await projectSourceFingerprint(root);assert.notEqual(a.hash,b.hash);
  await writeFile(join(root,'index.html'),'new');assert.equal((await projectSourceFingerprint(root)).files,2);
 }finally{await rm(root,{recursive:true,force:true});}
});

test('Source fingerprints do not follow symlinks or block on FIFO entries', {skip:process.platform==='win32'}, async()=>{
 const root=await mkdtemp(join(tmpdir(),'delivery-special-'));
 const outside=await mkdtemp(join(tmpdir(),'delivery-outside-'));
 try{
  await writeFile(join(root,'game.js'),'source');
  await writeFile(join(outside,'external.js'),'outside-v1');
  await symlink(join(outside,'external.js'),join(root,'linked.js'));
  const before=await projectSourceFingerprint(root);
  await writeFile(join(outside,'external.js'),'outside-v2');
  assert.deepEqual(await projectSourceFingerprint(root),before);

  const fifo=join(root,'pipe.js');
  await execFileAsync('mkfifo',[fifo]);
  const result=await Promise.race([
   projectSourceFingerprint(root),
   new Promise((_,reject)=>setTimeout(()=>reject(new Error('FIFO fingerprint blocked')),500)),
  ]);
  assert.deepEqual(result,before);
 }finally{
  await rm(root,{recursive:true,force:true});
  await rm(outside,{recursive:true,force:true});
 }
});
test('Only native bash receives default; explicit long deadlines and other tools remain unchanged',()=>{
 const event={toolName:'bash',input:{command:'python script.py'}};applyBashDeadline(event,true);assert.equal(event.input.timeout,120);
 for(const builtin of [false,true]){const e={toolName:'bash',input:{command:'build',timeout:900}};applyBashDeadline(e,builtin);assert.equal(e.input.timeout,900);}
 const custom={toolName:'bash',input:{command:'custom'}};applyBashDeadline(custom,false);assert.equal(custom.input.timeout,undefined);
});

test('Workflow inserts one project-stall observation into the next normal context after shell/scratch work',async()=>{
 const {default:install}=await import('../pi-workflow.js');
 const root=await mkdtemp(join(tmpdir(),'delivery-hooks-'));
 let time=0;const realNow=Date.now;const hooks=new Map(),notices=[];
 try {
  await writeFile(join(root,'game.js'),'unchanged');
  Date.now=()=>time;
  install({on:(name,fn)=>hooks.set(name,fn),getActiveTools:()=>['bash','write'],getAllTools:()=>[{name:'bash',sourceInfo:{source:'builtin'}}],sendMessage:(...args)=>notices.push(args)});
  Date.now=realNow;
  const ctx={cwd:root};hooks.get('input')({source:'rpc',text:'Implement the game renderer'},ctx);
  const run=async i=>{
   const id=`call-${i}`;
   hooks.get('tool_execution_start')({toolCallId:id,toolName:'bash',args:{command:`inspect-${i}`}});
   hooks.get('tool_execution_end')({toolCallId:id,isError:false,result:{content:[{type:'text',text:`new observation ${i}`}]}});
   await hooks.get('turn_end')({toolResults:[{toolCallId:id}]},ctx);
  };
  await run(0);for(let i=1;i<=12;i++){time=i*80000;await run(i);}
  assert.equal(notices.length,1);assert.equal(notices[0][1].triggerTurn,false);
  assert.match(notices[0][0].content,/12 tools completed/);
  const result=hooks.get('context')({messages:[{role:'toolResult',toolCallId:'call-12',content:[]}]}).messages;
  assert.equal(result.length,2);assert.match(result[1].content,/no source change/i);
 }finally{Date.now=realNow;await rm(root,{recursive:true,force:true});}
});

test('Continue preserves implementation intent without overriding an explicit read-only request',async()=>{
 let time=0;const d=createDeliveryProgressCheck({now:()=>time,snapshot:async()=>({hash:'same',files:1})});
 d.reset(true);d.reset(implementationRequest('ok continue'));await d.observe('/p');time=900000;assert.ok(await d.observe('/p',12));
 d.reset(false);d.reset(implementationRequest('resume'));await d.observe('/p');time+=900000;assert.equal(await d.observe('/p',12),undefined);
 });

test('Reset invalidates an in-flight observation and unknown snapshots fail open',async()=>{
 let now=0, resolveSnapshot;
 const d=createDeliveryProgressCheck({now:()=>now,snapshot:()=>new Promise(resolve=>{resolveSnapshot=resolve;})});
 d.reset(true);
 const pending=d.observe('/p',12);
 d.reset(false);
 resolveSnapshot({hash:'same',files:1});
 assert.equal(await pending,undefined);

 const throwing=createDeliveryProgressCheck({now:()=>now,snapshot:async()=>{throw new Error('unreadable');}});
 throwing.reset(true);
 await assert.doesNotReject(() => throwing.observe('/p',12));
 now=900000;
 assert.equal(await throwing.observe('/p',12),undefined);
});
