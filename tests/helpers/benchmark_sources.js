'use strict';
// Relocation compatibility for older generated VM fixtures. Regions come from
// the actual independent component; flat fixture hooks are adapted to its named
// ports. Full component/private-state behavior is tested separately.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const launchSources=require('./launch_sources.js');
const root=path.resolve(__dirname,'../..'),app=launchSources.controllerSource,workspace=fs.readFileSync(path.join(root,'benchmark_workspace.js'),'utf8');
const fixture=require('../fixtures/benchmark_workspace_legacy.json');
function functionSource(name){
 const marker=new RegExp(`(?:async )?function ${name}\\(`),match=marker.exec(workspace);if(!match)throw Error(`Missing component function ${name}`);
 const next=/\n(?:async )?function |\n  function initialize\(/g;next.lastIndex=match.index+match[0].length;const end=next.exec(workspace);
 if(!end)throw Error(`Missing component boundary ${name}`);return workspace.slice(match.index,end.index).trimEnd();
}
let controllerSource=app;
for(const method of fixture.functions){
 const marker=new RegExp(`(?:async )?function ${method.name}\\(\\.\\.\\.args\\) \\{ return benchmarkWorkspace\\.${method.name}\\(\\.\\.\\.args\\); \\}`);
 if(!marker.test(controllerSource))throw Error(`Missing controller facade ${method.name}`);
 controllerSource=controllerSource.replace(marker,()=>functionSource(method.name));
}
// The live factory is outside any function under test and intentionally cannot
// be created from a legacy VM's partial DOM. The real browser proves that glue.
const factoryStart=controllerSource.indexOf('\nconst benchmarkWorkspace = LLMBenchmarkWorkspace.createController('),factoryEnd=controllerSource.indexOf('\nasync function applyOptimizerMenuChoice(',factoryStart);
if(factoryStart>=0&&factoryEnd>factoryStart)controllerSource=controllerSource.slice(0,factoryStart)+controllerSource.slice(factoryEnd);
const handlersStart=workspace.indexOf('$("openBenchmarkButton").addEventListener');
const handlersEnd=workspace.indexOf('  }\n  const methods=',handlersStart);
if(handlersStart<0||handlersEnd<0)throw Error('Missing actual component handlers');
controllerSource+='\n'+workspace.slice(handlersStart,handlersEnd);
function connectScope(context){
 launchSources.connectScope(context);
 for(const[group,names]of Object.entries(fixture.callbacks)){
  const port=group==='settings'?'settingsPort':group==='receipt'?'receiptPort':group;
  if(context[port])continue;const service={};
  for(const name of names.split(' '))service[name]=(...args)=>{if(typeof context[name]!=='function')throw Error(`Missing generated fixture port ${name}`);return context[name](...args)};
  context[port]=service;
 }
 context.capabilities.runtimeInstalled??=key=>context.state?.binaries?.[key]?.installed===true;
 context.settingsPort.snapshot??=()=>({backend:context.state?.backend,client:context.state?.client,optimalLabel:context.state?.optimalLabel});
 context.settingsPort.selectBackend??=backend=>{context.state.backend=backend;context.updateBackend(true)};
 context.settingsPort.resetSessionAcknowledgement??=()=>{context.state.sessionAcknowledgementId=''};
 context.operations.profileBusy??=()=>context.profilesManager?.isBusy()||false;
 context.operations.snapshot??=()=>({runPhase:context.state?.runPhase,setupPhase:context.state?.setupPhase});
 context.receiptPort.current??=()=>context.state?.performanceReceipt;
 context.policy??={};for(const key of fixture.policyKeys)if(!Object.hasOwn(context.policy,key))Object.defineProperty(context.policy,key,{configurable:true,enumerable:true,get:()=>context[key]??fixture.policyValues[key]});
 context.calibrationError??='';context.benchmarkError??='';context.statusEpoch??=0;context.reviewGeneration??=0;
 context.setMarkup??=(node,markup)=>{if(node.innerHTML!==markup)node.innerHTML=markup};
 context.benchmarkWorkspace??={view:()=>({phase:context.state?.benchmarkPhase,calibrationStarting:context.state?.calibrationStarting,calibrationApplying:context.state?.calibrationApplying,message:context.state?.benchmarkStatus?.message}),status:()=>context.state?.benchmarkStatus};
}
function runInContext(code,context,options){connectScope(context);return vm.runInContext(code,context,options)}
module.exports={app,workspace,controllerSource,functionSource,connectScope,runInContext};
