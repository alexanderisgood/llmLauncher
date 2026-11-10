'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const Workspace=require('../benchmark_workspace.js'),{harness}=require('./helpers/benchmark_workspace_harness.js');
const frozen=require('./fixtures/benchmark_workspace_legacy.json');
// Full original sources and the explicit port-rewrite projections are frozen
// together; the production test has no temporary parser/tooling dependency.
(async()=>{
 const h=harness(),c=h.controller,source=fs.readFileSync(path.join(__dirname,'../benchmark_workspace.js'),'utf8');
 assert.equal(frozen.functionCount,65);assert.equal(frozen.handlerCount,23);
 const app=fs.readFileSync(path.join(__dirname,'../app.js'),'utf8');
 for(const key of frozen.privateStateKeys)assert.equal(app.includes(`state.${key}`),false,`Owned ${key} has no outside read/write`);
 for(const method of frozen.functions)assert.ok(app.includes(`return benchmarkWorkspace.${method.name}(...args);`),`Public ${method.name} delegates to the full component`);
 assert.ok(app.includes('benchmarkWorkspace.initialize();'));assert.match(fs.readFileSync(path.join(__dirname,'../index.html'),'utf8'),/<script src="benchmark_workspace.js" defer><\/script>/);
 const markup=require('./fixtures/benchmark_workspace_markup.json'),repairs=require('./fixtures/benchmark_workspace_repairs.json');
 const approvedRepairs=new Set(['renderBenchmarkHistory','loadBenchmarkHistory','renderCalibration','renderBenchmarkStatus','loadCalibrationPlan','startCalibration','applyCalibrationResult','reviewBenchmarkResult','startBenchmark','stopBenchmark']);
 for(const repair of repairs)assert.ok(approvedRepairs.has(repair.method),'Only evidenced error/history display repairs may alter frozen behavior');
 for(const method of frozen.functions){
  let expected=method.portSource;
  for(const patch of markup.filter(x=>x.method===method.name)){
   const parts=patch.before.match(/^(\$\("[^"\n]+"\))\.innerHTML = ([\s\S]*);$/);assert.ok(parts);
   assert.equal(patch.after,`setMarkup(${parts[1]}, ${parts[2]});`,'Reuse preserves every original markup expression');
   assert.ok(expected.includes(patch.before));expected=expected.replace(patch.before,patch.after);
  }
  const repair=repairs.find(x=>x.method===method.name);
  if(repair){const lines=expected.split('\n');for(const patch of [...repair.patches].reverse()){
   assert.deepEqual(lines.slice(patch.start,patch.end),patch.before,'Approved repair starts from the frozen source');lines.splice(patch.start,patch.end-patch.start,...patch.after);
  }expected=lines.join('\n')}
  assert.ok(source.includes(expected),`Full original ${method.name} behavior survives only explicit ports/markup reuse/evidenced display repairs`);
 }
 for(const handler of frozen.handlers)assert.ok(source.includes(handler.replace('void applyOptimal("engine", preference, false, evidenceBinding);','void evidence.applyOptimal("engine", preference, false, evidenceBinding);').replace('    showNotice("That measured result has no exact apply reference. Refresh it before applying.", true);','    effects.showNotice("That measured result has no exact apply reference. Refresh it before applying.", true);')),'All complete original handlers preserved');
 assert.equal(Object.isFrozen(c),true);assert.equal('state' in c,false);assert.equal('plan' in c.view(),false);
 for(const id of ['accelerationSelect','burstSelect','anePrefillSelect','memoryGuardSelect','calibrationContractState','calibrationEngineState','calibrationEvidenceState'])assert.ok(Workspace.nodeIds.includes(id),'Dynamic control IDs are explicitly injected');
 c.initialize();c.initialize();assert.equal(h.polls.length,1);assert.equal(h.nodes.calibrationApplyButton.listenerCount('click'),1);
 const detachedPlan=await c.loadCalibrationPlan();detachedPlan.model.name='Corrupted';assert.equal(c.view().hasPlan,true);assert.match(h.nodes.calibrationContract.textContent,/exact model|Generated model/);
 assert.equal(h.nodes.calibrationStartButton.disabled,false);
 // Admission refresh and exact request matching happen before the only start endpoint.
 h.request.context=16384;await c.startCalibration();assert.equal(h.requests.filter(x=>x.method==='start').length,1);
 assert.equal(h.requests.find(x=>x.method==='start').body.context,16384);
 assert.equal(c.status().phase,'queued');assert.equal(c.view().calibrationStarting,false);
 await c.stopCalibration();assert.equal(h.requests.filter(x=>x.method==='stop').length,1);
 // Detached public status cannot change owned jobs.
 const status=c.status();status.phase='corrupted';assert.equal(c.status().phase,'idle');
 const shown=c.benchmarkDisplayedStatus();shown.phase='corrupted';assert.equal(c.benchmarkDisplayedStatus().phase,'idle');
 // A plan response from a superseded request cannot enable a different contract.
 let resolveOld,resolveNew;
 const stale=harness({network:{plan:()=>new Promise(resolve=>{if(!resolveOld)resolveOld=resolve;else resolveNew=resolve})}});
 const old=stale.controller.loadCalibrationPlan();stale.request.context=32768;const fresh=stale.controller.loadCalibrationPlan();
 resolveNew({plan:{...stale.plan,request:{...stale.plan.request,context:32768}}});await fresh;
 resolveOld({plan:{...stale.plan,request:{...stale.plan.request,context:8192}}});await old;
 assert.match(stale.nodes.calibrationContract.textContent,/32,768/);assert.equal(stale.controller.view().loading,false);
 // Explicit Apply passes the immutable record reference to root's commit port.
 const apply=harness();apply.plan.action='apply-existing';apply.plan.evidence={trusted:true,evidenceBinding:apply.binding};
 await apply.controller.loadCalibrationPlan();await apply.controller.applyCalibrationResult(false);
 assert.deepEqual(apply.applies,[['engine','throughput',false,apply.binding]]);assert.equal(apply.controller.view().calibrationApplying,false);
 // A profile-save error retains an already applied route; an apply error rolls
 // back only the temporary controls and never saves a profile.
 let applySucceeds=false;
 const failure=harness({evidence:{applyOptimal:async()=>applySucceeds},network:{saveProfile:async()=>{throw Error('Generated save failure')}}});
 failure.plan.action='apply-existing';failure.plan.evidence={evidenceBinding:failure.binding};failure.plan.request.context=16384;
 failure.plan.reasoningContract={normalized:true,measured:'off'};failure.plan.calibrationCooling='smart';failure.nodes.calibrationProfileName.value='Generated';
 await failure.controller.loadCalibrationPlan();failure.nodes.calibrationProfileName.value='Generated';failure.nodes.calibrationDialog.open=true;
 await failure.controller.applyCalibrationResult(true);assert.equal(failure.nodes.contextInput.value,'8192');assert.equal(failure.nodes.reasoningSelect.value,'auto');assert.equal(failure.nodes.fanSelect.value,'default');
 assert.equal(failure.requests.filter(x=>x.method==='saveProfile').length,0);
 applySucceeds=true;await failure.controller.applyCalibrationResult(true);assert.equal(failure.nodes.contextInput.value,'16384');assert.equal(failure.nodes.reasoningSelect.value,'off');assert.equal(failure.nodes.fanSelect.value,'smart');
 assert.equal(failure.requests.filter(x=>x.method==='saveProfile').length,1);assert.equal(failure.controller.view().calibrationApplying,false);assert.match(failure.nodes.calibrationStatus.textContent,/Generated save failure/);
 // Native qualification contracts remain checked rather than substituting a
 // convenient backend, context or model.
 assert.equal(c.llamaQualificationContractExact({routeQualification:true,backend:'llamacpp'}),false);
 assert.equal(c.uzuQualificationContractExact({routeQualification:true,backend:'uzu'}),false);
 const historyCache=harness();await historyCache.controller.loadBenchmarkHistory(true);const writes=historyCache.nodes.benchmarkHistoryRuns.markupWrites;
 historyCache.controller.renderBenchmarkHistory();assert.equal(historyCache.nodes.benchmarkHistoryRuns.markupWrites,writes,'Unchanged saved history keeps existing DOM');
 let refreshFails=false;
 const retained=harness({network:{history:async()=>{if(refreshFails)throw Error('Generated refresh failure');return{history:structuredClone(historyCache.history)}}}});
 retained.history.currentRouteRuns=[{id:'generated-record',suite:'agentic',createdAt:'2026-10-07',winnerLabel:'MTP',display:'Generated'}];
 await retained.controller.loadBenchmarkHistory(true);refreshFails=true;await retained.controller.loadBenchmarkHistory(true);
 assert.equal(retained.controller.view().hasHistory,true);assert.match(retained.nodes.benchmarkHistoryFreshness.textContent,/Last loaded history is shown/);assert.equal(retained.nodes.benchmarkHistoryRetry.classList.contains('hidden'),false);
 retained.request.context=32768;await retained.controller.loadBenchmarkHistory(true);assert.equal(retained.controller.view().hasHistory,false);assert.equal(retained.nodes.benchmarkHistoryRuns.innerHTML,'','Changed-contract failure never leaves another contract visible');
 refreshFails=false;await retained.controller.loadBenchmarkHistory(true);assert.equal(retained.controller.view().historyError,'');assert.equal(retained.nodes.benchmarkHistoryRetry.classList.contains('hidden'),true);
 // Qwen preparation uses explicit settings ports even though the reviewed
 // preparation has its own local settings object; no callback is shadowed.
 const prepared=harness();prepared.plan.qualificationPreparation={kind:'qwen-ple-safe-qualification-v1',applicable:true,resolvesVisibleSettings:true,doesNotChangeMacOS:true,modelId:prepared.model.id,
  settings:{backend:'omlx',context:32768,output:1024,reasoning:'auto',calibrationCooling:'smart',options:{kv:'off',depth:3,acceleration:'off',burst:'balanced',anePrefill:'off',memoryGuard:'high'}}};
 for(const[id,value]of [['accelerationSelect','off'],['burstSelect','balanced'],['anePrefillSelect','off'],['memoryGuardSelect','high']])prepared.nodes[id].options=[{value}];
 await prepared.controller.loadCalibrationPlan();await prepared.controller.prepareQwenRouteQualification();assert.equal(prepared.nodes.contextInput.value,'32768');assert.equal(prepared.nodes.calibrationCoolingSelect.value,'smart');assert.equal(prepared.requests.some(x=>x.method==='start'),false);
 console.log('Complete Benchmark/Calibration standalone source, private state, exact Apply, admission, cancellation and stale replies passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
