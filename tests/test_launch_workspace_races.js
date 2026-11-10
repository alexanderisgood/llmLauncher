'use strict';
const assert=require('node:assert/strict'),{harness}=require('./helpers/launch_workspace_harness.js');
const run=(owner,activity)=>({phase:'running',run:{runId:owner,client:'pi'},activity,events:[]});
(async()=>{
 const replies=[];const h=harness({network:{sessionIdlePolicy:()=>new Promise((resolve,reject)=>{replies.push({resolve,reject})})}}),c=h.controller;
 await c.loadModels();h.session.hub.session={runId:'owner-A'};await c.loadSessionDashboard();c.renderRun(run('owner-A',structuredClone(h.activity)));
 h.nodes.sessionIdleTimeout.value='5';const a=c.setSessionIdlePolicy();assert.equal(h.requests.find(x=>x.method==='sessionIdlePolicy').body.timeoutMinutes,5);assert.equal(h.nodes.sessionIdleTimeout.value,'5','A pending choice remains visible');
 c.renderRun(run('owner-B',{...structuredClone(h.activity),detail:'Current B activity'}));h.nodes.sessionIdleTimeout.options.push({value:'10'});h.nodes.sessionIdleTimeout.value='10';const b=c.setSessionIdlePolicy();assert.equal(h.requests.filter(x=>x.method==='sessionIdlePolicy').at(-1).body.ownerRunId,'owner-B','A cached dashboard cannot route policy changes to the retired owner');
 replies[0].resolve({activity:{...structuredClone(h.activity),detail:'Retired A activity'}});await a;assert.equal(c.activity().detail,'Current B activity');assert.equal(h.nodes.sessionIdleTimeout.value,'10','A retired finally cannot clear the latest pending choice');assert.equal(h.nodes.sessionIdleTimeout.disabled,true);
 replies[1].resolve({activity:{...structuredClone(h.activity),detail:'Accepted B activity',idlePolicy:{...h.activity.idlePolicy,timeoutMinutes:10}}});await b;assert.equal(c.activity().detail,'Accepted B activity');assert.equal(h.nodes.sessionIdleTimeout.value,'10');assert.equal(h.nodes.sessionIdleTimeout.disabled,false);
 // A failed same-owner change rolls back to the last reported server policy.
 h.nodes.sessionIdleTimeout.value='5';const failed=c.setSessionIdlePolicy();replies[2].reject(Error('Generated policy failure'));await failed;assert.equal(h.nodes.sessionIdleTimeout.value,'10');assert.match(h.notices.at(-1)[0],/Generated policy failure/);
 for(const mutation of ['launch','stop']){
  let resolveStatus,reads=0;const fixture=harness({network:{status:()=>++reads===1?new Promise(resolve=>{resolveStatus=resolve}):Promise.resolve({phase:'idle',events:[]})}}),workspace=fixture.controller;
  workspace.initialize();await workspace.loadModels();await workspace.loadSessionDashboard();
  if(mutation==='stop')workspace.renderRun(run('prior-owner',structuredClone(fixture.activity)));
  const old=workspace.pollStatus();if(mutation==='launch')await workspace.launch(null,{admissionChecked:true});else await workspace.stopRun();
  const current=workspace.runState();resolveStatus(mutation==='launch'?{phase:'idle',events:[]}:run('prior-owner',structuredClone(fixture.activity)));await old;
  assert.deepEqual(workspace.runState(),current,`${mutation}: status captured before acceptance cannot replace current state`);
 }
 const rows=harness(),activity={...structuredClone(rows.activity),active:[{id:'generated-request',state:'running',client:'pi',surface:'Pi',surfaceId:'generated-surface',runSeconds:1,canCancel:true}]};rows.controller.renderRequestActivity(activity);const writes=rows.nodes.sessionActivityList.markupWrites;for(let i=0;i<30;i++)rows.controller.renderRequestActivity(activity);assert.equal(rows.nodes.sessionActivityList.markupWrites,writes,'Unchanged request rows keep their DOM');
 activity.active[0].runSeconds=2;rows.controller.renderRequestActivity(activity);assert.equal(rows.nodes.sessionActivityList.markupWrites,writes+1,'New displayed telemetry still renders');
 console.log('Launch/Stop status epochs, pending policy selection, retired owner/late-finally isolation, failed policy rollback and unchanged-row reuse passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
