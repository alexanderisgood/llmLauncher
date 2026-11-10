'use strict';
// Older partial-VM fixtures keep their explicit hooks. All workflow bodies are
// selected from the current production module, with its named ports adapted to
// those generated hooks; full privacy/ownership is exercised by component tests.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),root=path.resolve(__dirname,'../..');
const app=fs.readFileSync(path.join(root,'app.js'),'utf8'),workspace=fs.readFileSync(path.join(root,'launch_workspace.js'),'utf8'),fixture=require('../fixtures/launch_workspace_legacy.json');
function functionSource(name){const match=new RegExp(`(?:async )?function ${name}\\(`).exec(workspace);if(!match)throw Error(`Missing actual Launch function ${name}`);const next=/\n(?:async )?function |\n  const launchHome=|\n  function initialize\(/g;next.lastIndex=match.index+match[0].length;const end=next.exec(workspace);if(!end)throw Error(`Missing Launch boundary ${name}`);return workspace.slice(match.index,end.index).trimEnd()}
let controllerSource=app;
for(const method of fixture.methods){const marker=new RegExp(`(?:async )?function ${method.name}\\(\\.\\.\\.args\\) \\{ return launchWorkspace\\.${method.name}\\(\\.\\.\\.args\\); \\}`);if(!marker.test(controllerSource))throw Error(`Missing Launch facade ${method.name}`);controllerSource=controllerSource.replace(marker,()=>functionSource(method.name));}
const begin=controllerSource.indexOf('\nconst launchWorkspace = LLMLaunchWorkspace.createController('),end=controllerSource.indexOf('\nconst chatResumeReview =',begin);if(begin>=0&&end>begin)controllerSource=controllerSource.slice(0,begin)+controllerSource.slice(end);
const handlersStart=workspace.indexOf('collections.backendButtons.forEach(button => button.addEventListener'),handlersEnd=workspace.indexOf('  }\n  const methods=',handlersStart);if(handlersStart<0||handlersEnd<0)throw Error('Missing Launch handlers');controllerSource+='\n'+workspace.slice(handlersStart,handlersEnd);
function connectScope(ctx){
 for(const[group,names]of Object.entries(fixture.callbackGroups)){
  const port=group+'Port';ctx[port]??={};for(const name of names.split(' '))ctx[port][name]??=(...args)=>{if(typeof ctx[name]!=='function')throw Error(`Missing generated Launch port ${name}`);return ctx[name](...args)};
 }
 ctx.registryPort.binaries??=()=>ctx.state?.binaries||{};ctx.registryPort.adapters??=()=>ctx.state?.adapters||{};ctx.registryPort.clientSupport??=()=>ctx.state?.clientSupport||{};
 ctx.registryPort.useRuntimes??=value=>{ctx.state.binaries=value};ctx.registryPort.useAdapters??=value=>{ctx.state.adapters=value};
 ctx.jobsPort.snapshot??=()=>ctx.state||{};ctx.jobsPort.updateRuntimeControls??=()=>ctx.runtimeManager?.updateControls();
 ctx.savedPort.isBusy??=()=>ctx.profilesManager?.isBusy()||false;ctx.savedPort.shortcutsLoaded??=()=>ctx.profilesManager?.shortcutsLoaded()||false;
 ctx.assetsPort.invalidateLibrary??=()=>ctx.modelAssets?.invalidateLibrary();ctx.assetsPort.activity??=()=>ctx.modelAssets?.activity()||{phase:'idle'};
 ctx.surfacesPort.chatView??=()=>ctx.chatWorkspace?.view()||{surfaceId:ctx.state?.chatRunId,ownerRunId:ctx.state?.chatOwnerRunId,generating:Boolean(ctx.state?.chatAbort)};
 ctx.surfacesPort.initializePrimaryChat??=(...args)=>ctx.chatWorkspace?.initializePrimary(...args);ctx.surfacesPort.abortChatResponse??=()=>ctx.chatWorkspace?.abortResponse();
 ctx.surfacesPort.hasPendingChatReview??=()=>ctx.chatResumeReview?.hasPending()||false;ctx.surfacesPort.chatReviewStopped??=message=>ctx.chatResumeReview?.stopped(message);
 ctx.benchmarkPort.view??=()=>ctx.benchmarkWorkspace?.view()||{phase:ctx.state?.benchmarkPhase,calibrationApplying:ctx.state?.calibrationApplying,calibrationStarting:ctx.state?.calibrationStarting};
 ctx.preflightPort.setIntent??=value=>{ctx.state.routeCheckIntent=value};
 ctx.platform??={};for(const name of ['setTimeout','clearTimeout','requestAnimationFrame','Event'])ctx.platform[name]??=ctx[name]||globalThis[name];ctx.platform.storage??=()=>ctx.themeStorage?.();ctx.platform.confirm??=(...args)=>ctx.window?.confirm(...args);ctx.platform.activeElement??=()=>ctx.document?.activeElement;
 ctx.collections??={};for(const[selector,name]of Object.entries({'.chat-sampler':'chatSamplers','.session-attach-sampler':'sessionSamplers','[data-backend]':'backendButtons','[data-client]':'clientButtons','[data-optimizer-scope]':'optimizerButtons'}))ctx.collections[name]??=Array.from(ctx.document?.querySelectorAll?.(selector)||[]);ctx.collections.optimizerControls??=Array.from(ctx.document?.querySelectorAll?.('.optimizable')||[]);
 ctx.nodes??={configScroll:ctx.document?.querySelector?.('.config-scroll')};ctx.policy??={};for(const[key,value]of Object.entries(fixture.policyValues))if(!Object.hasOwn(ctx.policy,key))Object.defineProperty(ctx.policy,key,{configurable:true,enumerable:true,get:()=>ctx[key]??value});
 ctx.launchHome??={update(){},renderOverview(){}};ctx.runEpoch??=0;ctx.idlePolicyGeneration??=0;ctx.pendingIdlePolicy??=null;
 ctx.currentPolicyOwner??=()=>ctx.state?.runStatus?.run?.runId||ctx.state?.sessionDashboard?.hub?.session?.runId||null;ctx.retireIdlePolicy??=()=>{ctx.idlePolicyGeneration++;ctx.pendingIdlePolicy=null;if(ctx.state)ctx.state.idlePolicyBusy=false};ctx.setMarkup??=(node,markup)=>{if(node.innerHTML!==markup)node.innerHTML=markup};
 ctx.launchWorkspace??={view:()=>({backend:ctx.state?.backend,client:ctx.state?.client,phase:ctx.state?.runPhase,applyingOptimal:ctx.state?.applyingOptimal,launchPreparing:ctx.state?.launchPreparing,optimalLabel:ctx.state?.optimalLabel}),catalog:()=>ctx.state?.models,selectedModel:()=>ctx.state?.selected,runState:()=>ctx.state?.runStatus,sessionState:()=>ctx.state?.sessionDashboard,activity:()=>ctx.state?.requestActivity,receipt:()=>ctx.state?.performanceReceipt,freeTokenView:()=>ctx.state?.freeToken};
}
function runInContext(code,context,options){connectScope(context);return vm.runInContext(code,context,options)}
module.exports={app,workspace,controllerSource,functionSource,connectScope,runInContext};
