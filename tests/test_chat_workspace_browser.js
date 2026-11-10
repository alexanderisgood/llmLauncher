"use strict";
// Full production app/component with generated local replies only.
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path"),http=require("node:http");
if(!process.env.LLM_LAUNCHER_BROWSER_PACKAGE){console.log("Complete Chat browser fixture skipped (opt-in).");}
else (async()=>{
 const {chromium}=require(process.env.LLM_LAUNCHER_BROWSER_PACKAGE),root=path.resolve(__dirname,"..");
 const historyId="9d12aa4e-c129-4c53-bad0-0fce34611c6b",owner="30266d96-92d7-4e3d-bca4-467f75a9e539";
 const support={chat:{supported:true},pi:{supported:true},omp:{supported:true},codex:{supported:false},opencode:{supported:false}};
 const cap={runnable:true,customSampling:true,contextWindows:[2048,8192,16384,32768],contextMaximum:32768,outputMaximum:8192,
   agentReasoning:["off","low","medium"],kv:true,kvChoices:["off","q8"],prefillSizes:[64,128],clientSupport:support};
 const model={id:"fixture-q6",name:"Generated Kolibri Q6",format:"mlx",ready:true,status:"Ready",quantization:"6-bit",
   sizeLabel:"Generated",nativeContext:32768,origins:["Generated"],backends:{kolibri:cap}};
 const run={runId:owner,purpose:"session",client:"chat",backend:"kolibri",modelId:model.id,model:model.name,project:"/generated/project",
   context:32768,output:1024,reasoning:"off",chat:{sampling:"model"},options:{kv:"off"}};
 const longMessages=Array.from({length:160},(_,i)=>({id:`generated-${i}`,role:i%2?"assistant":"user",createdAt:"2026-10-07T00:00:00Z",
   content:i%2?`## Generated answer ${i}\n\n${"A measured fixture paragraph with **bold** and [local text](https://example.invalid). ".repeat(8)}\n\n\`\`\`python\nprint(${i})\n\`\`\``:`Generated question ${i}`,
   ...(i%2?{reasoning:"Generated prior reasoning"}:{} )}));
 const thread={id:historyId,title:"Generated long history",model:model.name,backend:"kolibri",context:32768,output:1024,reasoning:"off",
   resumeAvailable:true,messageCount:longMessages.length,updatedAt:"2026-10-07T00:00:00Z",messages:longMessages};
 const posts=[],streams=[],timers=new Set();let failSave=false,history=[thread],recovery=null,recoverOnNextLoad=false;
 function emit(response,value){response.write(`data: ${JSON.stringify(value)}\n\n`);}
 const server=http.createServer((request,response)=>{
  if(request.url!=="/api/chat"){response.writeHead(404);response.end();return;}
  let raw="";request.on("data",bytes=>raw+=bytes);request.on("end",()=>{
   const body=JSON.parse(raw);streams.push({body,response});
   response.writeHead(200,{"Content-Type":"text/event-stream","Cache-Control":"no-cache"});
   emit(response,{choices:[{delta:{reasoning_content:"Generated live reasoning",content:"Generated partial **answer"}}]});
   response.flushHeaders();
   if(body.messages.at(-1)?.content.includes("hold fixture"))return;
   const timer=setTimeout(()=>{timers.delete(timer);if(response.destroyed)return;
    emit(response,{choices:[{delta:{content:"** finished."},finish_reason:"stop"}],usage:{prompt_tokens:120,completion_tokens:32,total_tokens:152}});
    response.end("data: [DONE]\n\n");},150);timers.add(timer);
  });
 });
 await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));const base=`http://127.0.0.1:${server.address().port}`;
 let browser;
 try{
  browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
  const errors=[];page.on("pageerror",error=>errors.push(error.message));page.setDefaultTimeout(15000);
  await context.route("**/*",async route=>{
   const request=route.request(),url=new URL(request.url()),endpoint=url.pathname;
   if(url.origin!==base)return route.abort("blockedbyclient");
   if(endpoint==="/api/chat")return route.continue();
   if(!endpoint.startsWith("/api/")){
    const name=endpoint==="/"?"index.html":endpoint.slice(1);
    if(!/^[\w.-]+\.(?:js|css|html)$/.test(name))return route.fulfill({status:404,body:""});
    if(name==="chat_workspace.js"&&process.env.LLM_LAUNCHER_CHAT_BASELINE)return route.fulfill({path:process.env.LLM_LAUNCHER_CHAT_BASELINE});
    return route.fulfill({path:path.join(root,name)});
   }
   const body=request.method()==="POST"?request.postDataJSON():{};if(request.method()==="POST")posts.push({endpoint,body});
   let payload={phase:"idle",profiles:[],sessionSets:[],threads:history,sessionSet:{phase:"idle"},runtimePromotion:{phase:"idle"}};
   if(endpoint==="/api/bootstrap")payload={token:"synthetic-token",controllerSourceCurrent:true,roots:[{label:"Generated",path:"/generated/models"}],
     clientSupport:{kolibri:support},binaries:{kolibri:{installed:true,version:"Fixture",path:"/fixture/python"}},
     adapters:{engines:[{id:"kolibri",label:"Kolibri SSD",installed:true}],workSurfaces:[{id:"chat",label:"Chat",installed:true}]}};
   if(endpoint==="/api/models")payload={models:[model]};
   if(endpoint==="/api/status")payload={phase:"running",run,events:[],attachments:[]};
   if(endpoint==="/api/chat/history")payload={threads:history,version:8};
   if(endpoint==="/api/chat/history/get")payload={thread:history.find(item=>item.id===body.id)||thread};
   if(endpoint==="/api/chat/history/save"){
    if(failSave)return route.fulfill({status:503,json:{ok:false,storageError:true,error:"Generated save failure; original history preserved."}});
    const saved={...body,...body.metadata,title:body.title||"Generated saved thread",messageCount:body.messages.length,updatedAt:"2026-10-07T00:01:00Z"};
    history=[saved,...history.filter(item=>item.id!==saved.id)];payload={thread:saved,threads:history};
   }
   if(endpoint==="/api/chat/turn/checkpoint"){recovery=body;payload={ok:true};}
   if(endpoint==="/api/chat/turn/clear"){recovery=null;payload={ok:true};}
   if(endpoint==="/api/chat/turn/recover"){
    if(recoverOnNextLoad){recoverOnNextLoad=false;const recovered={...history[0],hasInterruptedTurn:true,title:'Recovered generated turn'};
      history=[recovered,...history.slice(1)];payload={recovered:true,thread:recovered,threads:history};}
    else payload={recovered:false,threads:history};
   }
   if(endpoint==="/api/chat/settings/get")payload={settings:{chat:{sampling:"model"},contract:{model:run.model,context:run.context,output:run.output,reasoning:run.reasoning,customSampling:true}}};
   if(endpoint==="/api/chat/stop"){
    for(const entry of streams){if(entry.response.destroyed||entry.response.writableEnded)continue;
     emit(entry.response,{choices:[{delta:{},finish_reason:"aborted"}]});entry.response.end("data: [DONE]\n\n");}
    payload={surfaceId:owner,cancelled:1};
   }
   if(endpoint==="/api/session/plan")payload={sessions:{hub:{phase:"running",attachments:[]},operation:{active:false},warmRoute:{canAttach:false},
     admission:{decision:"ready",launchable:true,requiresAcknowledgement:false,label:"Ready",contractId:"generated-capacity",estimate:{}},resource:{memoryAvailable:true,totalMemoryBytes:48*1024**3,headroomBytes:32*1024**3}}};
   return route.fulfill({json:payload});
  });
  await page.goto(base);await page.waitForFunction(()=>chatWorkspace.view().historyLoaded&&chatWorkspace.view().surfaceId);
  await page.evaluate(id=>openChatHistoryThread(id),historyId);await page.waitForFunction(()=>chatWorkspace.view().activeThreadId);
  assert.equal(await page.locator("#chatMessages article").count(),160);
  const before=await page.evaluate(()=>{
   const measurements=[];for(let i=0;i<8;i++){const start=performance.now();chatWorkspace.renderChatMessages();measurements.push(performance.now()-start);}
   return measurements.sort((a,b)=>a-b)[Math.floor(measurements.length/2)];
  });
  await page.locator("#chatInput").fill("hold fixture");await page.locator("#chatSendButton").click();
  await page.waitForFunction(()=>chatWorkspace.view().generating&&document.getElementById("chatMessages").textContent.includes("Generated partial"));
  assert.equal(streams[0].body.runId,owner);assert.equal(streams[0].body.attachmentId,owner);
  const pendingProfile=await page.evaluate(()=>{
   const original=document.querySelectorAll('#chatMessages article')[1],id=original.dataset.chatMessageId;
   const current=()=>document.querySelector(`#chatMessages article[data-chat-message-id="${CSS.escape(id)}"]`);
   const disclosure=original.querySelector('.chat-reasoning');disclosure.open=true;
   const focused=original.querySelector('[data-chat-action="copy"]');focused.focus();
   const measurements=[];for(let i=0;i<8;i++){const start=performance.now();chatWorkspace.renderChatMessages();measurements.push(performance.now()-start);}
   return {medianMilliseconds:measurements.sort((a,b)=>a-b)[4],completedNodeRetained:original===current(),
     focusRetained:document.activeElement===focused,reasoningOpen:current().querySelector('.chat-reasoning').open};
  });
  if(process.env.LLM_LAUNCHER_CHAT_EXPECT_REUSE==='1')assert.deepEqual({...pendingProfile,medianMilliseconds:0},
    {medianMilliseconds:0,completedNodeRetained:true,focusRetained:true,reasoningOpen:true});

  await page.locator("#chatInput").fill("queued generated follow-up");await page.locator("#chatSendButton").click();
  assert.match(await page.locator("#chatQueue").innerText(),/queued generated follow-up/);
  await page.locator("#chatStopButton").click();await page.waitForFunction(()=>!chatWorkspace.view().generating);
  assert.ok(posts.some(item=>item.endpoint==="/api/chat/stop"&&item.body.runId===owner&&item.body.attachmentId===owner));
  assert.equal(streams.length,1,"Stop retains the queued follow-up without sending it");
  assert.match(await page.locator("#chatQueue").innerText(),/paused|Review/i);
  const retained=await page.locator("#chatMessages").innerText();assert.match(retained,/Generated partial/);
  failSave=true;await page.locator("#newChatButton").click();
  await page.waitForFunction(()=>document.getElementById("notice").textContent.includes("save"));
  assert.equal(chatId(await page.evaluate(()=>chatWorkspace.view())),historyId);
  assert.equal(await page.locator("#chatMessages").innerText(),retained,"Save failure preserves the transcript and queue");
  failSave=false;
  const paused=await page.evaluate(()=>[...document.querySelectorAll('#chatQueue [data-chat-queue-action]')].map(n=>({action:n.dataset.chatQueueAction,text:n.textContent})));
  await page.evaluate(()=>resumeChatQueue());await page.waitForFunction(()=>!chatWorkspace.view().generating&&document.getElementById("chatMessages").textContent.includes("finished."));
  assert.equal(streams.length,2);assert.ok(history.some(row=>row.messages?.some(message=>message.content.includes("finished."))));
  await page.locator("#chatTranscriptSearchToggle").click();await page.locator("#chatTranscriptSearchInput").fill("Generated answer");
  await page.waitForFunction(()=>document.getElementById("chatTranscriptCount").textContent!="");
  assert.ok(await page.locator("#chatMessages mark").count()>0);
  await page.locator("#chatTranscriptSearchClose").click();
  let editPreserved={same:null};
  if(process.env.LLM_LAUNCHER_CHAT_PROFILE_ONLY!=='1'){
  const originalHistoryId=chatId(await page.evaluate(()=>chatWorkspace.view()));
  await page.evaluate(()=>{
   const message=document.querySelectorAll('#chatMessages article')[0],more=message.querySelector('.chat-message-more');more.open=true;
   message.querySelector('[data-chat-action="edit"]').click();
  });
  await page.waitForSelector('#chatMessages textarea');
  await page.locator('#chatMessages textarea').fill('Edited generated question');
  editPreserved=await page.evaluate(()=>{
   const field=document.querySelector('#chatMessages textarea');field.focus();field.setSelectionRange(4,12);chatWorkspace.renderChatMessages();
   return {same:field===document.querySelector('#chatMessages textarea'),value:field.value,focused:document.activeElement===field,
     selection:[field.selectionStart,field.selectionEnd]};
  });
  if(process.env.LLM_LAUNCHER_CHAT_EXPECT_REUSE==='1')assert.deepEqual(editPreserved,
    {same:true,value:'Edited generated question',focused:true,selection:[4,12]});
  else if(editPreserved.value!=='Edited generated question')await page.locator('#chatMessages textarea').fill('Edited generated question');
  await page.locator('#chatMessages [data-chat-edit-form] button[type="submit"]').click();
  await page.waitForFunction(()=>!chatWorkspace.view().generating&&!chatWorkspace.view().revisionBusy&&!chatWorkspace.view().historyBusy&&document.getElementById('chatMessages').textContent.includes('Edited generated question')&&document.getElementById('chatMessages').textContent.includes('finished.'));
  assert.ok(history.some(row=>row.id!==originalHistoryId&&row.branchParentId===originalHistoryId&&row.branchKind==='edit'));
  assert.ok(history.some(row=>row.id===originalHistoryId),'Edit+retry preserves the original saved thread');
  assert.equal(streams.at(-1).body.messages.at(-1).content,'Edited generated question');
  await page.locator('#chatInput').fill('Recovered unfinished generated draft');
  await page.locator('#chatContextFileInput').setInputFiles({name:'generated.txt',mimeType:'text/plain',buffer:Buffer.from('GENERATED_CONTEXT_MUST_NOT_PERSIST')});
  await page.waitForFunction(()=>document.getElementById('chatContextPack').textContent.includes('generated.txt'));
  await page.evaluate(()=>persistChatSessionState());
  const storageValues=await page.evaluate(()=>Object.values(sessionStorage).join('\n'));
  assert.match(storageValues,/Recovered unfinished generated draft/);assert.doesNotMatch(storageValues,/GENERATED_CONTEXT_MUST_NOT_PERSIST/);
  recoverOnNextLoad=true;await page.reload();
  await page.waitForFunction(()=>chatWorkspace.view().historyLoaded&&!chatWorkspace.view().historyBusy);
  await page.waitForFunction(()=>document.getElementById('chatInput').value==='Recovered unfinished generated draft');
  assert.ok(posts.some(row=>row.endpoint==='/api/chat/turn/recover'));
  assert.ok(history[0].hasInterruptedTurn);
  assert.doesNotMatch(await page.locator('#chatContextPack').innerText(),/generated.txt/,'Selected context files are not silently restored');

  }
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  if(!await page.evaluate(()=>chatWorkspace.view().sidebarCollapsed))await page.locator('#chatSidebarToggle').click();
  assert.equal(await page.evaluate(()=>chatWorkspace.view().sidebarCollapsed),true);
  if(process.env.LLM_LAUNCHER_CHAT_PROFILE_ONLY!=='1')assert.equal(await page.locator('#chatInput').inputValue(),'Recovered unfinished generated draft');
  const output=path.join(root,"build/browser-qa");fs.mkdirSync(output,{recursive:true});await page.screenshot({path:path.join(output,"chat-workspace-mobile.png"),fullPage:true});
  await page.screenshot({path:path.join(output,"chat-workspace-mobile-viewport.png"),fullPage:false});
  assert.deepEqual(errors,[]);
  const report={success:true,historyMessages:160,medianRenderMilliseconds:before,pendingProfile,streamRequests:streams.length,exactOwnerAndSurface:true,
   stopQueuePaused:true,saveFailurePreserved:true,historySaved:true,editBranchPreserved:process.env.LLM_LAUNCHER_CHAT_PROFILE_ONLY==='1'?null:true,editSelectionPreserved:editPreserved.same,
   draftRecovered:process.env.LLM_LAUNCHER_CHAT_PROFILE_ONLY==='1'?null:true,contextNotPersisted:process.env.LLM_LAUNCHER_CHAT_PROFILE_ONLY==='1'?null:true,interruptedRecovery:process.env.LLM_LAUNCHER_CHAT_PROFILE_ONLY==='1'?null:true,mobileOverflow:false,modelsLoaded:false};
  fs.writeFileSync(process.env.LLM_LAUNCHER_CHAT_BROWSER_REPORT||path.join(output,"chat-workspace-browser.json"),JSON.stringify(report,null,2)+"\n");
  console.log("Complete Chat browser: exact owner, generated streaming, Stop/paused queue, save failure preservation, long history, transcript search and mobile layout passed.");
  console.log("Generated long-history median render ms:",before);
 }finally{for(const timer of timers)clearTimeout(timer);if(browser)await browser.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
 function chatId(view){return view.activeThreadId;}
})().catch(error=>{console.error(error);process.exitCode=1;});
