"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const Chat=require("../chat_workspace.js");
const cores={ChatDraftsCore:require("../chat_drafts.js"),ChatQueueCore:require("../chat_queue.js"),
  ChatScrollCore:require("../chat_scroll.js"),ChatStatusCore:require("../chat_status.js"),
  ChatStreamCore:require("../chat_stream.js"),ChatTranscriptCore:require("../chat_transcript.js"),
  SafeMarkdownCore:require("../safe_markdown.js"),WorkspaceContextCore:require("../workspace_context.js")};
function element(tag="div"){
  const classes=new Set(),children=[],listeners=new Map();
  const node={tagName:tag.toUpperCase(),dataset:{},style:{},value:"",textContent:"",innerHTML:"",hidden:false,disabled:false,open:false,
    isConnected:true,clientHeight:400,scrollHeight:400,scrollTop:0,children,tabIndex:0,
    classList:{add:(...v)=>v.forEach(x=>classes.add(x)),remove:(...v)=>v.forEach(x=>classes.delete(x)),
      contains:v=>classes.has(v),toggle:(v,on)=>{if(on??!classes.has(v))classes.add(v);else classes.delete(v);}},
    append:(...v)=>children.push(...v),replaceChildren:(...v)=>{children.splice(0,children.length,...v)},
    get firstChild(){return children[0]||null},
    insertBefore(value,cursor){const old=children.indexOf(value);if(old>=0)children.splice(old,1);
      const at=cursor?children.indexOf(cursor):-1;children.splice(at>=0?at:children.length,0,value);value.parentNode=node;
      children.forEach((child,index)=>{child.nextSibling=children[index+1]||null;});},
    removeChild(value){const at=children.indexOf(value);if(at>=0)children.splice(at,1);
      children.forEach((child,index)=>{child.nextSibling=children[index+1]||null;});value.parentNode=null;return value;},
    querySelector:selector=>element(selector==="textarea"?"textarea":"span"),querySelectorAll:()=>[],
    setAttribute(){},removeAttribute(){},getAttribute(){return null},getClientRects:()=>[],
    focus(){},select(){},remove(){},click(){},contains:()=>false,closest:()=>null,
    addEventListener:(name,fn)=>{const group=listeners.get(name)||[];group.push(fn);listeners.set(name,group)},
    listenerCount:name=>(listeners.get(name)||[]).length,
    dispatch:(name,event={})=>(listeners.get(name)||[]).forEach(fn=>fn({target:node,currentTarget:node,preventDefault(){},...event})),
  };node.parentElement={setAttribute(){}};return node;
}
function harness(options={}){
  const nodes=Object.fromEntries(Chat.nodeIds.map(id=>[id,element()]));
  const storage=new Map(),requests=[],notices=[],frames=[],timers=[];
  let snapshot={phase:"idle",status:{phase:"idle",attachments:[]}},savedThreads=[];
  const api={};
  for(const method of ["historyInventory","historyDelete","historyGet","historyUpdate","historySave","settingsGet","settingsUpdate",
    "stopResponse","checkpoint","clearCheckpoint","recoverCheckpoint","detachSurface"]){
    api[method]=async settings=>{const body=settings?.body?JSON.parse(settings.body):{};requests.push({method,body});
      if(method==="historySave"){const thread={...body,id:body.id||"generated-history",title:"Generated",updatedAt:"2026-10-07",messageCount:body.messages?.length||0};savedThreads=[thread];return{thread,threads:savedThreads}}
      if(method==="historyInventory")return{threads:savedThreads};
      if(method==="recoverCheckpoint")return{available:false};
      return{ok:true,threads:savedThreads,hub:{phase:"running"}};};
  }
  api.stream=async settings=>{requests.push({method:"stream",body:JSON.parse(settings.body)});
    return new Response('data: {"choices":[{"delta":{"content":"Generated answer"}}]}\n\ndata: {"choices":[{"finish_reason":"stop"}],"usage":{"prompt_tokens":7,"completion_tokens":2,"total_tokens":9}}\n\ndata: [DONE]\n\n',
      {headers:{"Content-Type":"text/event-stream"}});};
  const controller=Chat.createController({nodes,cores,api,
    platform:{sessionStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value)},
      requestAnimationFrame:fn=>{frames.push(fn);return frames.length},setTimeout:fn=>{timers.push(fn);return timers.length},clearTimeout(){},
      matchMedia:()=>({matches:false}),reducedMotion:()=>false,activeDetail:()=>"simple",
      onBeforeUnload(){},
      dom:{createElement:element,createTextNode:text=>({nodeType:3,textContent:text}),createDocumentFragment:()=>element(),
        createTreeWalker:()=>({nextNode:()=>null}),querySelector:()=>null,activeElement:null,body:element(),addEventListener(){}}},
    navigation:{agentVisible:()=>false,suspendAgent(){},refreshAgent(){},refreshChrome(){},closeSessions(){},stopRun:async()=>true},
    callbacks:{showNotice:(message,error)=>notices.push({message,error}),copyLocalText:async()=>{},pollStatus:async()=>{},renderCacheObservatory(){},
      renderRequestActivity(){},renderQuickStart(){},surfacePostmortemMarker:(phase)=>({title:phase}),sessionRouteActive:(_run,phase)=>["running","stopping"].includes(phase),
      runSettingsApplied(){},surfaceDetached:options.surfaceDetached||(async()=>{})},
    formatting:{esc:value=>String(value??"").replaceAll("<","&lt;"),formatBytes:String,formatNumber:String,backendName:String,profileBackendLabel:String},
    review:{hasPending:()=>false,isStarting:()=>false,render(){},open:async()=>{},completePending:async()=>{},apply:async()=>{}},
    policy:{uiEngineVisible:()=>true},session:{snapshot:()=>snapshot,token:()=>"generated-token"}});
  return{controller,nodes,api,storage,requests,notices,frames,timers,setSnapshot:value=>{snapshot=value}};
}
(async()=>{
  const h=harness(),c=h.controller;
  const frozen=JSON.parse(fs.readFileSync(path.join(__dirname,"fixtures/chat_workspace_legacy.json"),"utf8"));
  assert.equal(frozen.functionCount,150);
  for(const method of frozen.functions){
    assert.equal(typeof c[method.name],"function",method.name);
    let expected=method.source;
    expected=expected.replace('if (state.runStatus?.run?.runId === state.chatRunId && state.runStatus.run.client === "chat") {\n      state.runStatus.run.chat = chat;\n    }','callbacks.runSettingsApplied(state.chatRunId, chat);');
    expected=expected.replace('  if ($("sessionDialog").open) $("sessionDialog").close();','  navigation.closeSessions();');
    expected=expected.replace('    if (state.sessionDashboard) state.sessionDashboard.hub = data.hub;\n    state.sessionAttachmentPlan = null;\n    state.sessionAttachmentSignature = "";\n    await loadSessionDashboard();','    await callbacks.surfaceDetached(data.hub, attachment.ownerRunId);');
    expected=expected.replace('  return stopRun();','  return navigation.stopRun();');
    if(method.name==='renderChatMessages'){
      const current=c[method.name].toString();
      // Preserve the complete original row builder. Only the cache entry,
      // linear predicate lookups and attached-child reconciliation changed.
      const before=expected.slice(expected.indexOf('    const article = document.createElement("article");'),expected.indexOf('    fragment.append(article);'))
        .replace('    const landmark = landmarks.get(message.id);\n','')
        .replace('const isMessageTail = !state.chatMessages.slice(index + 1)\n        .some(ChatStreamCore.blocksIncompleteTailRecovery);','const isMessageTail = tailRecovery[index];')
        .replace('const hasEarlierUser = state.chatMessages.slice(0, index).some(item => item.role === "user" && !item.pending);','const hasEarlierUser = earlierUsers[index];');
      const after=current.slice(current.indexOf('    const article = document.createElement("article");'),current.indexOf('    nextRows.set(message, {article, signature});'));
      assert.equal(after,before,'All original Markdown/role/action/disclosure/usage/edit row construction stays exact');
      assert.match(current,/renderedMessageRows\.get\(message\)/);assert.match(current,/container\.insertBefore\(article, cursor\)/);
    }else assert.equal(c[method.name].toString(),expected,`Complete frozen behavior for ${method.name}`);
  }
  const app=fs.readFileSync(path.join(__dirname,'../app.js'),'utf8');
  for(const key of frozen.privateStateKeys)assert.equal(app.includes(`state.${key}`),false,`Private ${key} has no outside write/read`);
  assert.equal(frozen.handlerCount,59);
  const componentSource=fs.readFileSync(path.join(__dirname,'../chat_workspace.js'),'utf8');
  for(const handler of frozen.handlerSources){
    const expected=handler.replace('window.addEventListener("beforeunload", persistChatSessionState);','platform.onBeforeUnload(persistChatSessionState);');
    assert.ok(componentSource.includes(expected),'Every complete owned handler survives the extraction');
  }
  assert.equal(Object.hasOwn(c.view(),'messages'),false);
  assert.equal(Object.hasOwn(c.view(),'draft'),false);
  assert.equal(Object.isFrozen(c),true);
  assert.equal("state" in c,false);
  c.initialize();assert.equal(c.view().sidebarCollapsed,false);
  // A repeated initializer must not attach a second message-submit callback.
  c.initialize();
  assert.equal(h.nodes.chatForm.listenerCount('submit'),1);
  assert.equal(await c.startChatTurn("inactive"),false);assert.equal(h.requests.some(r=>r.method==="stream"),false);
  c.initializePrimary({runId:"generated-owner"});
  h.setSnapshot({phase:"running",status:{phase:"running",run:{runId:"generated-owner",client:"chat",backend:"kolibri",model:"Generated Q6",context:8192,output:1024,reasoning:"off",chat:{sampling:"model"}},attachments:[]}});
  c.updateChatWorkspace({runId:"generated-owner",client:"chat",backend:"kolibri",model:"Generated Q6",context:8192,output:1024,reasoning:"off"},"running");
  await c.loadChatHistory(true);
  await new Promise(setImmediate);
  assert.equal(c.view().surfaceId,"generated-owner");
  h.nodes.chatInput.value="draft text";c.activateChatDraft("generated-owner",{restoreActive:true});
  h.nodes.chatInput.value="draft text";c.persistChatDraftNow();
  assert.ok([...h.storage.values()].some(raw=>raw.includes("draft text")));
  assert.equal(c.queueChatMessage("queued text"),true);
  assert.ok([...h.storage.values()].some(raw=>raw.includes("queued text")));
  assert.equal(await c.saveChatBeforeSurfaceExit("navigate again"),true,JSON.stringify(h.notices));
  assert.equal(c.view().generating,false);
  assert.equal(await c.startChatTurn("actual generated turn"),true);
  const sent=h.requests.find(row=>row.method==="stream");
  assert.equal(sent.body.runId,"generated-owner");
  assert.equal(sent.body.attachmentId,"generated-owner");
  assert.equal(sent.body.messages.at(-1).content,"actual generated turn");
  assert.ok(h.requests.some(row=>row.method==="historySave"&&row.body.messages.some(message=>message.content==="Generated answer")));
  assert.equal(c.view().generating,false);
  c.useThreads([{id:"history-1",title:"Existing",messages:[]}]);
  const rows=c.threads();rows[0].title="changed";
  assert.equal(c.thread("history-1").title,"Existing");
  c.thread("history-1").title="another external edit";
  assert.equal(c.thread("history-1").title,"Existing");
  assert.equal(c.normaliseChatMessage({role:"user",content:"hello"}).content,"hello");
  assert.equal(c.chatRoutesMatch({backend:"kolibri",modelId:"q6",context:8192,output:1024},{backend:"kolibri",modelId:"q6",context:8192,output:1024}),true);
  // A detach reply carries the owner captured before awaiting its request,
  // even if a replacement Chat and model become current meanwhile.
  const ownerReceipts=[];const launch=require('./helpers/launch_workspace_harness.js').harness();
  launch.controller.renderRun({phase:'running',run:{runId:'owner-B',client:'chat'},events:[]});
  const late=harness({surfaceDetached:async(hub,owner)=>{ownerReceipts.push(owner);assert.equal(launch.controller.updateOwnedHub(hub,owner),null);}});
  let resolveDetach;late.api.detachSurface=()=>new Promise(resolve=>{resolveDetach=resolve});
  late.controller.initializePrimary({runId:'owner-A'});
  const pendingDetach=late.controller.detachChatSurface({id:'attachment-A',ownerRunId:'owner-A',primary:false,client:'chat',canDetach:true});
  late.controller.initializePrimary({runId:'owner-B'});resolveDetach({hub:{phase:'running',attachments:[{id:'old-attachment'}]}});await pendingDetach;
  assert.deepEqual(ownerReceipts,['owner-A']);assert.equal(launch.controller.runState().run.runId,'owner-B');assert.equal(launch.controller.runState().attachments,undefined);
  console.log("Complete Chat component:150 methods, local drafts/queue, inactive admission, exact surface, detached history and navigation preservation passed. Generated data only.");
})().catch(error=>{console.error(error);process.exitCode=1});
