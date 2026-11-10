'use strict';
const assert=require('node:assert/strict'),{harness}=require('./helpers/benchmark_workspace_harness.js');
(async()=>{
 for(const kind of ['benchmark','calibration']){
  let resolveStatus;const h=harness({network:{status:()=>new Promise(resolve=>{resolveStatus=resolve})}}),c=h.controller;
  c.initialize();if(kind==='calibration')await c.loadCalibrationPlan();
  const flight=c.pollBenchmarkStatus();await(kind==='calibration'?c.startCalibration():c.startBenchmark());
  const accepted=c.status().job.id;resolveStatus({phase:'idle'});await flight;
  assert.equal(c.view().phase,'queued',`${kind}: a pre-admission status cannot retire the accepted job`);assert.equal(c.status().job.id,accepted);
 }
 let oldStatus,count=0;
 const stopped=harness({network:{status:()=>++count===1?new Promise(resolve=>{oldStatus=resolve}):Promise.resolve({phase:'cancelled'})}});
 stopped.controller.initialize();const flight=stopped.controller.pollBenchmarkStatus();await stopped.controller.stopBenchmark();oldStatus({phase:'running',job:{id:'obsolete'}});await flight;
 assert.equal(stopped.controller.status().phase,'cancelled','An accepted Stop fences older status reads too');
 for(const method of ['loadCalibrationPlan','loadBenchmarkHistory']){
  let invalid=false,resolveReply,h;
  h=harness({settings:{gather:()=>{if(invalid)throw Error('Generated invalid controls');return structuredClone(h.request)}},
   network:{[method==='loadCalibrationPlan'?'plan':'history']:()=>new Promise(resolve=>{resolveReply=resolve})}});
  const pending=h.controller[method](true);invalid=true;await h.controller[method](true);
  resolveReply(method==='loadCalibrationPlan'?{plan:structuredClone(h.plan)}:{history:structuredClone(h.history)});await pending;
  assert.equal(method==='loadCalibrationPlan'?h.controller.view().hasPlan:h.controller.view().hasHistory,false,'Invalid current controls retire a previous valid read');
  if(method==='loadCalibrationPlan')assert.equal(h.nodes.calibrationStartButton.disabled,true);
 }
 let refreshReply,historyReads=0,cached;
 cached=harness({network:{history:()=>++historyReads===1?Promise.resolve({history:structuredClone(cached.history)}):new Promise(resolve=>{refreshReply=resolve})}});
 await cached.controller.loadBenchmarkHistory(true);const pendingRefresh=cached.controller.loadBenchmarkHistory(true);await cached.controller.loadBenchmarkHistory(false);
 refreshReply({history:structuredClone(cached.history)});await pendingRefresh;assert.equal(cached.controller.view().historyLoading,false,'A newer cache-hit read retires its pending refresh without stranding loading');assert.equal(cached.nodes.benchmarkHistoryRetry.disabled,false);
 const replies=[];const reviewed=harness({network:{history:()=>new Promise((resolve,reject)=>{replies.push({resolve,reject})})}}),reply=id=>({history:{reviewResult:{id,scope:'local',modes:{}}}});
 const a=reviewed.controller.reviewBenchmarkResult('record-A','agentic'),b=reviewed.controller.reviewBenchmarkResult('record-B','agentic');
 replies[1].resolve(reply('record-B'));await b;replies[0].resolve(reply('record-A'));await a;
 assert.equal(reviewed.controller.benchmarkDisplayedStatus().result.id,'record-B','The latest selected saved result wins');
 const old=reviewed.controller.reviewBenchmarkResult('record-C','agentic'),latest=reviewed.controller.reviewBenchmarkResult('record-D','agentic');
 replies[3].resolve(reply('record-D'));await latest;replies[2].reject(Error('Obsolete review failure'));await old;
 assert.equal(reviewed.controller.benchmarkDisplayedStatus().result.id,'record-D');assert.equal(reviewed.notices.length,0,'An obsolete review error cannot cover a newer result');
 for(const action of ['start','stop']){
  let fail=true;const h=harness({network:{[action]:async()=>{if(fail)throw Error('Generated action failure '+ 'x'.repeat(4096));return action==='start'?{benchmark:{id:'retry-job'}}:{ok:true}}}}),c=h.controller;
  await c[action==='start'?'startBenchmark':'stopBenchmark']();assert.ok(h.nodes.benchmarkStatus.textContent.length<=2048);
  c.renderBenchmarkStatus({phase:'idle'});assert.match(h.nodes.benchmarkStatus.textContent,/Generated action failure/);
  fail=false;await c[action==='start'?'startBenchmark':'stopBenchmark']();assert.equal(c.view().benchmarkError,'');
  c.renderBenchmarkStatus({phase:'idle'});assert.doesNotMatch(h.nodes.benchmarkStatus.textContent,/Generated action failure/);
 }
 console.log('Benchmark mutation epochs, invalid-input read retirement, latest-review selection and persistent bounded action errors passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
