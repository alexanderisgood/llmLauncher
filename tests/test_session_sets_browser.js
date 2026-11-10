"use strict";
// Actual integrated app with every request intercepted; generated workspaces
// and controller replies only. No process, model, global settings or Quit.
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
if(!process.env.LLM_LAUNCHER_BROWSER_PACKAGE) {
  console.log("Session Sets browser fixture skipped (opt-in).");
} else {
  const {chromium}=require(process.env.LLM_LAUNCHER_BROWSER_PACKAGE);
  const root=path.resolve(__dirname,".."),base="http://127.0.0.1:18792";
  const support={pi:{supported:true},omp:{supported:true},chat:{supported:true},codex:{supported:false},opencode:{supported:false}};
  const capability={runnable:true,customSampling:true,contextWindows:[2048,4096,8192,16384,32768],
    contextMaximum:32768,outputMaximum:8192,agentReasoning:["off","low","medium","high"],
    kv:true,kvChoices:["off","q8","q6","q4"],prefillSizes:[64,128,256],clientSupport:support};
  const model={id:"saved-q6-fixture",name:"Generated Original Q6",ready:true,format:"mlx",status:"Ready",
    nativeContext:32768,quantization:"6-bit",sizeLabel:"Generated weights",origins:["Generated fixture"],backends:{kolibri:capability}};
  const request={backend:"kolibri",client:"omp",modelId:model.id,project:"/generated/project",agentHost:"console",
    context:8192,output:1024,reasoning:"off",mode:"custom",
    options:{acceleration:"off",depth:1,kv:"off",memoryMode:"fixed",memoryGB:12,prefillSize:64,promptCacheGB:1},
    generation:{sampling:"custom",temperature:0,topP:1,topK:0,seed:42}};
  const saved=id=>({id,name:'Saved <img src=x onerror="window.attacked=true"> '+id,ready:true,
    baseRequest:structuredClone(request),modelName:model.name,surfaceCount:2,hubConsoleCount:1,chatCount:1,
    terminalCount:0,surfaceLabels:["oh-my-pi · Hub Console","Chat"],updatedAt:"2026-10-06T12:00:00Z"});
  const profile={id:"profile-one",name:"Generated saved launch",ready:true,enginePolicy:"fixed",
    modelName:model.name,request:structuredClone(request),updatedAt:"2026-10-06T12:00:00Z"};
  (async()=>{
    const browser=await chromium.launch({headless:true});
    const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
    const errors=[],posts=[];let sets=[saved("one")],profiles=[profile],contract="capacity-one",openRejected=false,stopRejected=false,
      storageFailure=false,profileStorageFailure=false,runActive=false,job={phase:"idle"};
    const run={runId:"generated-owner",purpose:"session",backend:"kolibri",modelId:model.id,model:model.name,
      client:"pi",agentHost:"terminal",project:request.project,context:8192,output:1024,reasoning:"off",options:request.options};
    page.setDefaultTimeout(20_000);page.on("pageerror",error=>errors.push(error.message));
    await context.route("**/*",async route=>{
      try {
      const req=route.request(),url=new URL(req.url()),endpoint=url.pathname;
      if(url.origin!==base)return route.abort("blockedbyclient");
      if(!endpoint.startsWith("/api/")) {
        const name=endpoint==="/"?"index.html":endpoint.slice(1);
        return /^[\w.-]+\.(?:js|css|html)$/.test(name)?route.fulfill({path:path.join(root,name)}):route.fulfill({status:404,body:""});
      }
      const body=req.method()==="POST"?req.postDataJSON():{};
      if(req.method()==="POST") {
        posts.push({endpoint,body});
        assert.ok(["/api/benchmark/history","/api/session/plan","/api/session/warm-plan","/api/session/attachment-plan",
          "/api/chat/turn/recover","/api/session-sets/plan","/api/session-sets/open","/api/session-sets/stop",
          "/api/session-sets/save-active","/api/session-sets/delete","/api/profiles/save","/api/profiles/delete"].includes(endpoint),"Fixture forbids model launches and unrelated mutations");
      }
      let payload={phase:"idle",profiles:[],sets,threads:[],sessionSets:[],sessionSet:job,runtimePromotion:{phase:"idle"}};
      if(endpoint==="/api/bootstrap")payload={token:"generated-token",controllerSourceCurrent:true,roots:[],
        binaries:{kolibri:{installed:true,version:"Fixture"},pi:{installed:true,version:"Fixture"},
          omp:{installed:true,version:"omp/18.6.3",consoleSupported:true}},clientSupport:{kolibri:support},
        adapters:{engines:[{id:"kolibri",label:"Kolibri SSD",installed:true}],
          workSurfaces:[{id:"pi",label:"Pi",installed:true},{id:"omp",label:"oh-my-pi",installed:true},{id:"chat",label:"Chat",installed:true}]}};
      if(endpoint==="/api/models")payload={models:[model]};
      if(endpoint==="/api/chat/history")payload={threads:[
        {id:"hidden-chat",title:"Hidden FreeToken route",backend:"freetoken",model:"Hidden model",resumeAvailable:true,
          updatedAt:"2026-10-06T13:00:00Z",messageCount:1},
        {id:"saved-chat",title:"Generated previous chat",backend:"kolibri",model:model.name,resumeAvailable:true,
          updatedAt:"2026-10-06T12:00:00Z",messageCount:1},
      ]};
      if(endpoint==="/api/profiles") {
        if(profileStorageFailure)return route.fulfill({status:503,json:{ok:false,storageError:true,
          error:"Generated saved-launch storage error; original file kept."}});
        payload={profiles,limit:32};
      }
      if(endpoint==="/api/profiles/save") {
        assert.ok(runActive,"Draft settings can be saved while the existing model remains loaded");
        assert.equal(body.id,profile.id);assert.equal(body.name,"Edited saved launch");
        assert.equal(body.enginePolicy,"fixed");assert.equal(body.request.backend,"kolibri");
        assert.equal(body.request.modelId,model.id);assert.equal(body.request.client,"omp");
        assert.equal(body.request.context,16384);assert.equal(body.request.output,1024);assert.equal(body.request.reasoning,"medium");
        assert.equal(body.request.options.kv,"off");assert.equal(body.request.options.memoryMode,"fixed");assert.equal(body.request.options.memoryGB,12);
        assert.equal(body.request.options.prefillSize,64);assert.equal(body.request.agentHost,"console");
        assert.equal(body.request.generation.temperature,0);assert.equal(body.request.generation.seed,42);
        profiles=[{...profile,name:body.name,request:body.request}];payload={profiles,limit:32};
      }
      if(endpoint==="/api/profiles/delete") {assert.deepEqual(body,{id:profile.id});profiles=[];payload={profiles,limit:32};}
      if(endpoint==="/api/status")payload=runActive?{phase:"running",run,attachments:[{id:"primary"},{id:"chat"}],events:[]}:{phase:"idle",events:[]};
      if(endpoint==="/api/chat/turn/recover")payload={recovered:false,discarded:false,threads:[]};
      if(endpoint==="/api/session-sets") {
        if(storageFailure)return route.fulfill({status:503,json:{ok:false,storageError:true,error:"Generated saved-workspace storage error; original file kept."}});
        payload={sets,limit:16};
      }
      if(endpoint==="/api/session-sets/status")payload={sessionSet:job};
      if(endpoint==="/api/session-sets/plan")payload={plan:{setId:body.id,setName:sets.find(item=>item.id===body.id).name,
        ready:true,mode:"reuse",confirmation:"exact-"+contract,surfaceCount:2,existingMatchCount:1,willOpenSurfaceCount:1,
        hubConsoleCount:1,chatCount:1,terminalCount:0,admission:{requiresAcknowledgement:true,contractId:contract,
          label:"Generated memory review",detail:"Exact current capacity"},detail:"Only missing surfaces open on the resident model."}};
      if(endpoint==="/api/session-sets/open") {
        if(openRejected)return route.fulfill({status:409,json:{ok:false,error:"Generated capacity rejection. Saved set kept; retry or review."}});
        assert.deepEqual(body,{id:"one",confirmation:"exact-"+contract,memoryAcknowledgement:contract});
        job={phase:"attaching",jobId:"generated-job",setId:"one",setName:sets[0].name,mode:"reuse",
          totalSurfaceCount:2,openedSurfaceCount:0,pendingSurfaceCount:1,message:"Opening missing surfaces on one resident model"};
        payload={sessionSet:job};
      }
      if(endpoint==="/api/session-sets/stop") {
        assert.deepEqual(body,{});
        if(stopRejected)return route.fulfill({status:409,json:{ok:false,error:"Generated Stop rejection; operation retained."}});
        job={...job,phase:"cancelled",pendingSurfaceCount:0,message:"Remaining surfaces stopped; resident model kept"};payload={sessionSet:job};
      }
      if(endpoint==="/api/session-sets/save-active") {
        assert.ok(runActive);assert.deepEqual(body,{name:"Generated saved workspace"});
        sets.push({...saved("new"),name:body.name});payload={sets,limit:16};
      }
      if(endpoint==="/api/session-sets/delete") {sets=sets.filter(item=>item.id!==body.id);payload={sets,limit:16};}
      if(endpoint==="/api/session/plan")payload={sessions:{hub:{phase:runActive?"running":"idle",attachments:[]},operation:{active:false},
        warmRoute:{canAttach:false},resource:{memoryAvailable:true,totalMemoryBytes:48*1024**3,headroomBytes:32*1024**3,headroomPercent:67},
        admission:{decision:"ready",launchable:true,requiresAcknowledgement:false,label:"Ready",contractId:"visible-capacity",
          estimate:{geometryReady:true,estimatedWorkingSetBytes:12*1024**3}}}};
      return route.fulfill({json:payload});
      } catch(error) {errors.push(error.message);await route.abort("failed");}
    });
    try {
      await page.goto(base);await page.waitForFunction(()=>launchWorkspace.view().modelCount===1&&profilesManager.shortcutsLoaded());
      await page.locator("#quickStartCustom").click();
      assert.equal(await page.locator('[data-quick-chat="saved-chat"]').count(),1,"Visible resumable chats remain eligible shortcuts");
      assert.equal(await page.locator('[data-quick-chat="hidden-chat"]').count(),0,"A newer hidden route never replaces the visible shortcut");
      const manager=async()=>{await page.locator("#hubToolsMenuButton").click();await page.locator("#openSessionSets").click();
        await page.locator('[data-session-set-review="one"]').waitFor();};
      await manager();
      assert.equal(await page.locator("#sessionSetCards img").count(),0);assert.equal(await page.evaluate(()=>window.attacked),undefined);
      await page.locator('[data-session-set-review="one"]').click();await page.locator("#sessionSetConsentPanel").waitFor({state:"visible"});
      assert.equal(posts.filter(item=>item.endpoint==="/api/session-sets/open").length,0,"Review never opens a route or surface");
      await page.locator("#sessionSetConsent").check();contract="capacity-two";
      await page.locator('[data-session-set-review="one"]').click();
      await page.waitForFunction(()=>document.getElementById("sessionSetPlanState").textContent==="Ready");
      assert.equal(await page.locator("#sessionSetConsent").isChecked(),false);assert.equal(await page.locator("#sessionSetOpenButton").isDisabled(),true);
      await page.locator("#sessionSetConsent").check();openRejected=true;await page.locator("#sessionSetOpenButton").click();
      await page.waitForFunction(()=>document.getElementById("sessionSetStatus").textContent.includes("capacity rejection"));
      assert.equal(await page.locator("#sessionSetOpenButton").isEnabled(),true,"Rejected opens remain retryable");
      openRejected=false;await page.locator("#sessionSetOpenButton").click();await page.locator("#sessionSetStopButton").waitFor({state:"visible"});
      assert.match(await page.locator("#sessionSetPlanFacts").innerText(),/Resident model/);
      stopRejected=true;await page.locator("#sessionSetStopButton").click();
      await page.waitForFunction(()=>document.getElementById("sessionSetStatus").textContent.includes("Stop rejection"));
      stopRejected=false;await page.locator("#sessionSetStopButton").click();
      await page.waitForFunction(()=>document.getElementById("sessionSetPlanState").textContent==="Stopped");
      await page.locator('[data-session-set-apply="one"]').click();
      await page.waitForFunction(()=>!document.getElementById("sessionSetDialog").open);
      assert.equal(await page.locator("#contextInput").inputValue(),"8192");assert.equal(await page.locator("#outputInput").inputValue(),"1024");
      assert.equal(await page.locator("#kolibriMemoryGB").inputValue(),"12");assert.equal(await page.locator("#kolibriPrefillSelect").inputValue(),"64");
      assert.equal(await page.locator("#agentHostSelect").inputValue(),"console");
      assert.ok(!posts.some(item=>item.endpoint==="/api/launch"),"Apply and resident reuse never dispatch a second model load");
      runActive=true;await page.evaluate(()=>pollStatus());await manager();
      await page.locator("#sessionSetName").fill("Generated saved workspace");await page.locator("#sessionSetSaveButton").click();
      await page.locator('[data-session-set-edit="new"]').waitFor();await page.locator('[data-session-set-edit="new"]').click();
      await page.locator("#sessionSetName").evaluate(node=>{node.focus();node.setSelectionRange(3,9);});
      const stable=await page.evaluate(()=>{
        const button=document.querySelector('[data-session-set-edit="new"]'),field=document.getElementById("sessionSetName");
        for(let index=0;index<100;index++)renderSessionSets();
        return {same:button===document.querySelector('[data-session-set-edit="new"]'),focus:document.activeElement===field,
          start:field.selectionStart,end:field.selectionEnd};
      });assert.deepEqual(stable,{same:true,focus:true,start:3,end:9});
      await page.locator("#sessionSetCancelEdit").click();assert.equal(posts.filter(item=>item.endpoint==="/api/session-sets/save-active").length,1);
      await page.locator('[data-session-set-delete="new"]').click();
      assert.equal(posts.filter(item=>item.endpoint==="/api/session-sets/delete").length,0);
      assert.equal(await page.locator('[data-session-set-delete="new"]').evaluate(node=>node===document.activeElement),true);
      await page.locator('[data-session-set-delete="new"]').click();await page.locator('[data-session-set-delete="new"]').waitFor({state:"detached"});
      await page.keyboard.press("Escape");storageFailure=true;await manager();
      await page.waitForFunction(()=>document.getElementById("sessionSetStatus").textContent.includes("original file kept"));
      assert.equal(await page.locator(".session-set-card").count(),1,"Visible storage errors keep cached inventory intact");
      const output=path.join(root,"build/browser-qa");fs.mkdirSync(output,{recursive:true});
      await page.screenshot({path:path.join(output,"session-sets-desktop.png")});
      await page.setViewportSize({width:390,height:844});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      assert.ok(await page.locator("#sessionSetDialog").evaluate(node=>node.getBoundingClientRect().width)<=390);
      await page.screenshot({path:path.join(output,"session-sets-mobile.png")});
      await page.keyboard.press("Escape");profileStorageFailure=true;
      await page.locator("#hubToolsMenuButton").click();await page.locator("#openProfileManager").click();
      await page.waitForFunction(()=>document.getElementById("profileManagerStatus").textContent.includes("original file kept"));
      assert.equal(await page.locator(".profile-card").count(),1,"A profile storage error keeps the cached launch visible");
      assert.equal(await page.evaluate(()=>profilesManager.snapshot().profiles[0].id),profile.id);
      await page.evaluate(()=>loadQuickStart(true));
      assert.equal(await page.evaluate(()=>profilesManager.snapshot().profiles[0].id),profile.id,"Failed shortcut refresh cannot erase cached profiles");
      assert.match(await page.locator("#quickStartStatus").innerText(),/saved-launch storage error/);
      profileStorageFailure=false;await page.evaluate(()=>loadProfiles());
      assert.doesNotMatch(await page.locator("#profileManagerStatus").innerText(),/storage error/);
      assert.equal(await page.locator(".profile-card").count(),1,"A successful read recovers normally");
      await page.locator('[data-profile-edit="profile-one"]').click();
      await page.waitForFunction(()=>!document.getElementById("profileDialog").open&&!document.getElementById("profileEditBanner").hidden);
      assert.equal(await page.locator("#contextInput").inputValue(),"8192");
      await page.locator("#contextSelect").selectOption("16384");await page.locator("#reasoningSelect").selectOption("medium");
      await page.locator("#hubToolsMenuButton").click();await page.locator("#openProfileManager").click();
      await page.locator("#profileName").fill("Edited saved launch");await page.locator("#profileSaveButton").click();
      await page.waitForFunction(()=>document.getElementById("profileEditBanner").hidden);
      assert.equal(posts.filter(item=>item.endpoint==="/api/profiles/save").length,1);
      await page.locator('[data-profile-edit="profile-one"]').click();
      await page.waitForFunction(()=>!document.getElementById("profileEditBanner").hidden);
      await page.locator("#profileEditCancel").click();
      assert.equal(posts.filter(item=>item.endpoint==="/api/profiles/save").length,1,"Cancelling an edit never writes");
      await page.locator("#hubToolsMenuButton").click();await page.locator("#openProfileManager").click();
      await page.waitForFunction(()=>document.querySelector('[data-profile-apply="profile-one"]')?.disabled===false);
      const stableProfile=await page.evaluate(()=>{
        const button=document.querySelector('[data-profile-apply="profile-one"]');button.focus();
        for(let index=0;index<100;index++)renderProfiles();
        return {same:button===document.querySelector('[data-profile-apply="profile-one"]'),focus:document.activeElement===button};
      });assert.deepEqual(stableProfile,{same:true,focus:true});
      await page.screenshot({path:path.join(output,"saved-launches-mobile.png")});
      await page.setViewportSize({width:1440,height:1000});
      await page.screenshot({path:path.join(output,"saved-launches-desktop.png")});
      await page.locator('[data-profile-delete="profile-one"]').click();
      assert.equal(posts.filter(item=>item.endpoint==="/api/profiles/delete").length,0);
      await page.locator('[data-profile-delete="profile-one"]').click();await page.locator(".profile-card").waitFor({state:"detached"});
      assert.equal(posts.filter(item=>item.endpoint==="/api/profiles/delete").length,1);
      assert.ok(!posts.some(item=>item.endpoint==="/api/launch"));
      assert.deepEqual(errors,[]);
      const stale=path.join(output,"session-sets-failure.json");if(fs.existsSync(stale))fs.unlinkSync(stale);
      console.log("Integrated saved-workspace browser: exact consent/reuse, retry/apply/private CRUD/focus/mobile, and visible cached Session Set/profile storage errors plus recovery passed. No model loaded.");
    } catch(error) {
      const output=path.join(root,"build/browser-qa");fs.mkdirSync(output,{recursive:true});
      fs.writeFileSync(path.join(output,"session-sets-failure.json"),JSON.stringify({errors,posts,
        profiles:await page.evaluate(()=>profilesManager.snapshot()),
        shortcutDom:await page.locator("#quickStart").evaluate(node=>({className:node.className,
          detail:document.documentElement.dataset.detail,text:node.textContent,display:getComputedStyle(node).display})),
        text:await page.locator("body").innerText()},null,2)+"\n");
      throw error;
    } finally {await browser.close();}
  })().catch(error=>{console.error(error);process.exitCode=1;});
}
