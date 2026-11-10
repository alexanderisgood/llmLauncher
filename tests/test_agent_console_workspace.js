"use strict";
const assert=require("node:assert/strict"),fixture=require("./helpers/agent_console_workspace_harness.js"),{deferred}=fixture;
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function status(owner="owner",generation="generation"){
  const run={runId:owner,purpose:"session",client:"pi",agentHost:"console",model:"Original Q6",backend:"kolibri",context:8192};
  const metadata=(surfaceId,protocol)=>({ownerRunId:owner,surfaceId,id:surfaceId,client:protocol==="omp-rpc"?"omp":"pi",surface:protocol==="omp-rpc"?"oh-my-pi":"Pi",
    backend:"kolibri",model:"Original Q6",agentHost:"console",startedAt:generation,protocol,conversationId:"a".repeat(64),state:"running",canInput:true,
    canStop:true,canRestart:false,streaming:false,compacting:false,supportsSteering:true,bufferBaseOffset:0,bufferEnd:0});
  const agentConsoles=[metadata("pi-one","pi-rpc"),metadata("omp-two","omp-rpc")];
  return {phase:"running",run,agentConsoles,attachments:agentConsoles.map((meta,index)=>({...meta,primary:index===0,id:meta.surfaceId}))};
}
(async()=>{
  {
    const h=fixture();
    let now=1000;
    h.window.performance.now=()=>now;
    const running=status();
    running.agentConsoles[1].streaming=true;
    h.observe(running);
    h.controller.select("omp-two");
    const current={id:"active",surfaceId:"omp-two",state:"running",runSeconds:300,
      bytesRelayed:9000,firstOutputAt:new Date().toISOString()};
    h.activity({lanes:1,active:[current],queued:[
      {id:"queued-one",surfaceId:"omp-two",state:"queued",queuePosition:1},
      {id:"queued-two",surfaceId:"omp-two",state:"queued",queuePosition:2},
    ]});
    h.endpoints.read=async()=>({console:{...running.agentConsoles[1],timelineVersion:1,timelineReset:true,timelineBaseRevision:1,
      timelineRevision:2,nextTimelineRevision:2,timelineEvents:[
        {revision:1,kind:"toolCall",title:"Running · wait",text:"Waiting"},
        {revision:2,kind:"toolResult",title:"Running · task",text:"Running agent VisualsLayer...",createdAt:new Date().toISOString()},
      ],nextOffset:0}});
    await h.controller.read();
    assert.equal(h.elements.agentConsoleLivePhaseText.textContent,"Waiting for background agents");
    assert.equal(h.elements.agentConsoleLiveQueue.textContent,"1 running · 2 queued · 1 lane");
    assert.doesNotMatch(h.elements.agentConsoleLiveDetail.textContent,/flowing/,"The first sample cannot prove progress");
    now+=2000;
    current.bytesRelayed+=1000;
    h.controller.render();
    assert.match(h.elements.agentConsoleLiveDetail.textContent,/Response data flowing.*VisualsLayer/);
    now+=9000;
    h.controller.render();
    assert.match(h.elements.agentConsoleLiveDetail.textContent,/No new response data for 9s/);
    assert.equal(h.elements.agentConsoleStatusLaneValue.textContent,"Stream quiet");
    h.controller.dispose();
  }
  {
    const h=fixture();h.observe(status());assert.equal(h.controller.isVisible(),true);assert.equal(h.controller.currentSurfaceId(),"pi-one");
    h.elements.agentConsoleInput.value="Pi unsent 🙂";h.elements.agentConsoleInput.emit("input");h.controller.select("omp-two");
    assert.equal(h.elements.agentConsoleInput.value,"");h.elements.agentConsoleInput.value="OMP separate text";h.elements.agentConsoleInput.emit("input");h.controller.select("pi-one");
    assert.equal(h.elements.agentConsoleInput.value,"Pi unsent 🙂");assert.equal(h.calls.input.length,0,"Draft selection never invokes the agent");
    const persisted=JSON.parse(h.saved.get("llm-launcher-agent-console-drafts-v1"));assert.ok(persisted.drafts["pi:"+"a".repeat(64)]);assert.ok(persisted.drafts["omp:"+"a".repeat(64)]);
    h.controller.suspend();assert.equal(h.controller.isVisible(),false);assert.equal(h.timers.size,1,"Only deferred resize remains after read suspension");
    h.controller.dispose();assert.equal(h.timers.size,0);assert.equal(h.intervals.size,0);
    const refreshed=fixture({saved:h.saved});refreshed.observe(status());assert.equal(refreshed.controller.isVisible(),false,"Explicit workspace dismissal survives reload");
    refreshed.controller.select("pi-one");assert.equal(refreshed.elements.agentConsoleInput.value,"Pi unsent 🙂");refreshed.controller.dispose();
  }
  {
    const h=fixture();h.observe(status());const pending=deferred();h.endpoints.read=body=>{h.calls.read.push(body);return pending.promise;};
    const reading=h.controller.read();assert.deepEqual(h.calls.read[0],{ownerRunId:"owner",surfaceId:"pi-one",offset:0,timelineRevision:0,timelineVersion:1});
    h.observe(status("replacement","new-generation"));pending.resolve({console:{...status().agentConsoles[0],data:Buffer.from("OLD OUTPUT").toString("base64"),nextOffset:10}});await reading;
    assert.equal(h.controller.currentView().renderedText,"");assert.equal(h.elements.agentTerminalOutput.textContent.includes("OLD OUTPUT"),false,"Old owner output cannot enter a replacement console");
    h.controller.dispose();
  }
  {
    const h=fixture();h.observe(status());h.endpoints.read=async body=>{h.calls.read.push(body);return {console:{...status().agentConsoles[0],timelineVersion:1,timelineReset:true,timelineBaseRevision:1,
      timelineRevision:3,nextTimelineRevision:3,timelineEvents:[{revision:1,kind:"user",text:"Generated task"},{revision:2,kind:"thinking",text:"Reasoning"},{revision:3,kind:"answer",text:"<script>Inert answer</script>"}],data:"",nextOffset:0}};};
    await h.controller.read();assert.equal(h.controller.currentView().timelineLoaded,true);assert.equal(h.elements.agentTerminalViewport.hidden,true);
    assert.equal(h.calls.timeline.at(-1).items.length,3);assert.equal(h.calls.timeline.at(-1).options.protocol,"pi-rpc");
    h.endpoints.read=async()=>({console:{...status().agentConsoles[0],timelineVersion:999,data:Buffer.from("tail").toString("base64"),bufferEnd:20,nextOffset:20,baseOffset:0}});
    await h.controller.read();assert.equal(h.controller.currentView().timelineLoaded,false);assert.equal(h.controller.currentView().offset,0,"Version mismatch replays retained terminal buffer from its base");
    h.controller.dispose();
  }
  {
    const h=fixture();const notReady=status();notReady.agentConsoles[0].canInput=false;h.observe(notReady);
    h.elements.agentConsoleInput.value="Do not send before ready";assert.equal(h.controller.submit(),false);assert.equal(h.calls.input.length,0);
    h.observe(status());const pending=deferred();h.endpoints.input=body=>{h.calls.input.push(body);return pending.promise;};
    h.elements.agentConsoleInput.value="First exact message";assert.equal(h.controller.submit(),true);h.elements.agentConsoleInput.value="Second exact message";assert.equal(h.controller.submit(),true);
    assert.equal(h.calls.input.length,1);pending.reject(new Error("Generated network rejection"));await settle();assert.equal(h.controller.currentView().inputQueue.length,2);
    assert.match(h.controller.currentView().inputError,/still first/);assert.equal(h.elements.agentConsoleInput.value,"");
    h.endpoints.input=async body=>{h.calls.input.push(body);return {console:status().agentConsoles[0]};};assert.equal(h.controller.submit(),true);await settle();
    assert.deepEqual(h.calls.input.slice(1).map(item=>item.message),["First exact message","Second exact message"]);h.controller.dispose();
  }
  {
    const h=fixture();const streaming=status();streaming.agentConsoles[0].streaming=true;h.observe(streaming);
    const pending=deferred();h.endpoints.input=body=>{h.calls.input.push(body);return pending.promise;};h.elements.agentConsoleInput.value="Steer source only";h.elements.agentConsoleInput.emit("input");
    const steering=h.controller.steer();h.controller.select("omp-two");h.elements.agentConsoleInput.value="Keep OMP text";h.elements.agentConsoleInput.emit("input");
    pending.resolve({console:{...streaming.agentConsoles[0]}});await steering;assert.equal(h.elements.agentConsoleInput.value,"Keep OMP text");
    assert.deepEqual(h.calls.input[0],{ownerRunId:"owner",surfaceId:"pi-one",command:"steer",message:"Steer source only"});
    h.controller.select("pi-one");assert.equal(h.elements.agentConsoleInput.value,"");h.controller.currentView().inputQueue=[{command:"prompt",message:"Keep queued follow-up"}];
    h.endpoints.input=async body=>{h.calls.input.push(body);return {console:{...streaming.agentConsoles[0],streaming:false,queuePaused:true,pendingMessages:1}};};
    await h.controller.abort();assert.equal(h.calls.input.at(-1).command,"abort");assert.equal(h.controller.currentView().inputQueue[0].message,"Keep queued follow-up");h.controller.dispose();
  }
  {
    const h=fixture();h.observe(status());h.endpoints.stop=async body=>{h.calls.stop.push(body);return {hub:{attachments:[],agentConsoles:[]},console:{...status().agentConsoles[0],state:"stopped",canInput:false}};};
    await h.controller.stop();assert.deepEqual(h.calls.stop,[{ownerRunId:"owner",surfaceId:"pi-one"}]);assert.equal(h.calls.hub.length,1);assert.equal(h.controller.isVisible(),false);
    h.observe({...status(),phase:"failed",message:"Generated engine failed"});assert.equal(h.controller.currentView().postmortem.state,"failed");
    h.controller.select("pi-one");assert.equal(h.elements.agentConsoleInput.disabled,true,"Postmortem output never re-enables input");h.controller.dispose();
  }
  {
    const gate=deferred(),h=fixture({navigationOverrides:{beforeShow:()=>gate.promise}});h.observe(status());h.controller.suspend();
    const selecting=h.controller.select("omp-two");assert.equal(h.controller.isVisible(),false,"Chat save must finish before Console can hide it");
    gate.resolve(false);await selecting;assert.equal(h.controller.isVisible(),false);assert.equal(h.controller.currentSurfaceId(),"pi-one");h.controller.dispose();
    const permission=deferred(),stale=fixture({navigationOverrides:{beforeShow:()=>permission.promise}});stale.observe(status());
    const entering=stale.controller.enter(status().attachments[1]);stale.observe(status("new-owner","new-generation"));permission.resolve(true);await entering;
    assert.equal(stale.controller.currentView().meta.ownerRunId,"new-owner","Late navigation approval cannot revive a retired route");stale.controller.dispose();
    const response=deferred(),stopping=fixture();stopping.observe(status());stopping.endpoints.stop=()=>response.promise;
    const stopped=stopping.controller.stop();stopping.observe(status("replacement","new-generation"));response.resolve({hub:{attachments:[],agentConsoles:[]},console:{state:"stopped"}});await stopped;
    assert.equal(stopping.calls.hub.length,0,"A retired owner's Stop reply cannot replace current Hub attachments");assert.equal(stopping.controller.currentView().meta.ownerRunId,"replacement");stopping.controller.dispose();
  }
  console.log("Complete Agent Console workspace: owned state/navigation, Pi/OMP drafts/recovery, exact read/generation guards, semantic version fallback, ready gating, retry ordering, steering/abort queue preservation and lifecycle callbacks passed.");
})().catch(error=>{console.error(error);process.exitCode=1;});
