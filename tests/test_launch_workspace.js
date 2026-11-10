'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{harness}=require('./helpers/launch_workspace_harness.js'),frozen=require('./fixtures/launch_workspace_legacy.json');
(async()=>{
 const source=fs.readFileSync(path.join(__dirname,'../launch_workspace.js'),'utf8'),h=harness(),c=h.controller;
 const app=fs.readFileSync(path.join(__dirname,'../app.js'),'utf8');for(const key of frozen.privateStateKeys)assert.equal(new RegExp(`state\\.${key}\\b`).test(app),false,`Private ${key} has no outside read/write`);for(const method of frozen.methods)assert.ok(app.includes(`return launchWorkspace.${method.name}(...args);`));assert.equal(app.includes('const launchHome = LauncherHomeCore.createController'),false,'Root no longer injects whole app state/document into Home');
 assert.equal(frozen.methods.length,132);assert.equal(frozen.handlers.length,58);
 const markup=require('./fixtures/launch_workspace_markup.json'),repairs=require('./fixtures/launch_workspace_repairs.json');
 const approved=new Set(['launch','stopRun','renderRun','renderRequestActivity','setSessionIdlePolicy']);
 for(const repair of repairs)assert.ok(approved.has(repair.method),'Only demonstrated owner/epoch/pending-selection repairs alter frozen methods');
 for(const method of frozen.methods){let expected=method.portSource;
  if(method.name==='updateBackend'){
   const before='Install Splash 1.2.1 and rescan for compatible GGUF files or MLX Q4 checkpoints. MLX Q6 requires the MLX engine.';
   const after='Install Splash 1.4.0 and rescan for compatible GGUF files, including split Flash-Next GGUFs. Flash-Next requires GGUF; 27B and 35B also support MLX Q4.';
   assert.equal(expected.split(before).length,2,'Only the Splash empty-catalog help changes');expected=expected.replace(before,after);
  }
  for(const patch of markup.filter(x=>x.method===method.name)){const parts=patch.before.match(/^(.*)\.innerHTML = ([\s\S]*);$/);assert.ok(parts);assert.equal(patch.after,`setMarkup(${parts[1]}, ${parts[2]});`,'Identical full original markup expressions remain');assert.ok(expected.includes(patch.before));expected=expected.replace(patch.before,patch.after)}
  const repair=repairs.find(x=>x.method===method.name);if(repair){const lines=expected.split('\n');for(const patch of [...repair.patches].reverse()){assert.deepEqual(lines.slice(patch.start,patch.end),patch.before);lines.splice(patch.start,patch.end-patch.start,...patch.after)}expected=lines.join('\n')}
  assert.ok(source.includes(expected),`Full original ${method.name} body with only explicit ports/demonstrated repairs`);
 }
 for(const handler of frozen.handlers)assert.ok(source.includes(handler.portSource),'Complete owned handler behavior survives explicit ports/split shared menu composition');
 assert.equal('state' in c,false);assert.equal('document' in c,false);assert.equal(Object.isFrozen(c),true);
 c.initialize();c.initialize();assert.equal(h.polls.length,2);assert.equal(h.nodes.launchButton.listenerCount('click'),1);
 await c.loadModels();assert.equal(c.view().modelCount,1);assert.equal(c.selectedModel().id,h.model.id);const detached=c.selectedModel();detached.name='Caller changed';assert.equal(c.selectedModel().name,h.model.name);
 const request=c.gather('custom',false);assert.equal(request.modelId,h.model.id);assert.equal(request.client,'pi');assert.equal(request.backend,'mtplx');assert.equal(request.context,16384);assert.equal(request.output,1024);assert.equal(request.options.kv,'off');assert.equal(request.reasoning,'auto');
 await c.loadSessionDashboard();assert.equal(c.currentSessionAdmission().actionReady,true);const session=c.sessionState();session.admission.launchable=false;assert.equal(c.currentSessionAdmission().actionReady,true,'Public snapshots cannot mutate admission');
 // Ordinary launch captures the selected contract and invokes no benchmark.
 await c.startSimpleLaunch();const accepted=h.requests.find(x=>x.method==='launch');assert.equal(accepted.body.modelId,request.modelId);assert.equal(accepted.body.context,request.context);assert.equal(accepted.body.output,request.output);assert.equal(accepted.body.reasoning,request.reasoning);assert.equal(accepted.body.options.kv,request.options.kv);assert.equal(h.requests.some(x=>x.method==='benchmarkStart'),false);assert.equal(c.view().phase,'preflight');assert.equal(c.view().launchPreparing,false);
 const status=c.runState();status.run.model='Caller changed';assert.equal(c.runState().run.model,h.model.name);
 // Explicit child updates are fenced to the current owner and detach inputs.
 assert.equal(c.updateOwnedHub({attachments:[{id:'wrong'}]},'other-owner'),null);
 const hub={attachments:[{id:'owned'}],agentConsoles:[]};c.updateOwnedHub(hub,'generated-run');hub.attachments[0].id='Caller changed';assert.equal(c.runState().attachments[0].id,'owned');
 const incoming={phase:'running',run:{runId:'new-owner',client:'chat'},cache:{state:'idle'},activity:structuredClone(h.activity),events:[]};c.renderRun(incoming);incoming.run.runId='Caller changed';assert.equal(c.runState().run.runId,'new-owner');
 const settings={systemPrompt:'Generated'};c.updateOwnedChatSettings('old-owner',settings);assert.equal(c.runState().run.chat,undefined);c.updateOwnedChatSettings('new-owner',settings);settings.systemPrompt='Caller changed';assert.equal(c.runState().run.chat.systemPrompt,'Generated');
 await c.stopRun();assert.equal(h.requests.filter(x=>x.method==='stop').length,1);
 console.log('Complete 132-method/58-handler Launch source, startup, selected contract, admission, launch/Stop and detached owner-bound views passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
