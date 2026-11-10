"use strict";
// All requests are generated and intercepted. No runtime is installed, opened,
// measured or selected; no model/global settings/Quit endpoint is touched.
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
if(!process.env.LLM_LAUNCHER_BROWSER_PACKAGE)console.log("Runtime Manager browser fixture skipped (opt-in).");
else {
  const {chromium}=require(process.env.LLM_LAUNCHER_BROWSER_PACKAGE),root=path.resolve(__dirname,".."),base="http://127.0.0.1:18794";
  const support={pi:{supported:true},omp:{supported:true},chat:{supported:true},opencode:{supported:false},codex:{supported:false}};
  const cap={runnable:true,agentReasoning:["off","medium"],customSampling:true,kvChoices:["off","q8","q6","q4"],contextWindows:[2048,4096,8192,16384,32768],outputMaximum:8192,clientSupport:support};
  const model={id:"runtime-model",name:"Generated Original Q6",ready:true,status:"Ready",format:"mlx",quantization:"6-bit",nativeContext:32768,
    sizeLabel:"Generated weights",origins:["Generated"],architecture:"qwen",path:"/generated/model",backends:{omlx:cap}};
  const selected={id:"selected-exact",version:"0.9.0",channelLabel:"Selected reference",path:"/generated/runtimes/selected",revision:{id:"c".repeat(64)},label:"Selected reference",selected:true};
  const candidate={id:"candidate-exact",version:"1.0.0",channelLabel:"Verified candidate",path:"/generated/runtimes/candidate",revision:{id:"d".repeat(64)},label:"Verified candidate",managedVerification:{verified:true}};
  const release={channel:"stable",label:"Stable",version:"1.0.0",action:"install",canPlan:true,releasedAt:"2026-01-01",tag:"v1.0.0",
    commit:"a".repeat(40),sha256:"b".repeat(64),fileName:"generated.whl",summary:"Generated checksum and release evidence",releaseUrl:"https://example.invalid/release"};
  const catalog={catalogAuditedAt:"2026-10-06",releases:[release,{...release,channel:"blocked",label:"Unavailable preview",canPlan:false,preview:true}]};
  const updatePlan=()=>({id:"generated-update",confirmation:"install:exact-tag:checksum:destination",action:"install",release,
    destination:{exists:false,path:"/generated/runtimes/1.0.0"},installer:{dependencyPolicy:"Only the exact pinned dependency versions"},
    rollback:{detail:"The working selected copy stays installed"},steps:["Verify the exact generated checksum","Keep the selected copy unchanged"],
    checks:[{state:"pass",label:"Exact destination",detail:"Generated isolated copy"}],canStart:true});
  const comparison=()=>({id:"generated-comparison",confirmation:"measure:two-exact-revisions",canStart:true,selected,candidate,model:{id:model.id,name:model.name},
    workload:{label:"Generated agent workload",generatedRequests:4},executionOrder:["selected","candidate","candidate","selected"],checks:[{state:"pass",label:"Exact revisions",detail:"Generated hashes"}],
    steps:["Same original model and visible controls","Compare generated deterministic replies"],rollback:{detail:"Previous selected copy remains available"}});
  const result=()=>({id:"generated-result",confirmation:"promote:exact-revisions-and-measurements",canPromote:true,selectionChanged:false,candidate,
    medianSpeedup:1.07,worstCaseSpeedup:1.05,memoryRegressionBytes:0,measurements:{candidate:{thermalWorst:"Nominal"}},checks:[],recommendation:"Generated evidence cleared every gate"});
  (async()=>{
    const browser=await chromium.launch({headless:true}),context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
    const errors=[],posts=[],replies=[];let inventoryFailed=false,startFailed=false,selectFailed=false,openFailed=false,applyFailed=false,runActive=false,
      update={phase:"idle"},promotion={phase:"idle"},selectedId=selected.id,inventoryReads=0;
    const inventory=()=>({checkedAt:"2026-10-07T12:00:00Z",releaseCatalog:{auditedAt:"2026-10-06"},summary:{message:"Generated local runtime inspection"},agents:[{label:"oh-my-pi",version:"18.6.3",installed:true}],
      runtimes:[{id:"omlx",label:"oMLX <img src=x onerror=window.attacked=true>",level:"ready",headline:"Installed verified copies",selected:selectedId===selected.id?selected:candidate,
        candidates:[{...selected,selected:selectedId===selected.id},{...candidate,selected:selectedId===candidate.id}],checks:[{ready:true,label:"Installed copies",detail:"Generated executable paths"}],update:{},app:{available:true,label:"Generated app"}},
        {id:"lms",label:"LM Studio",level:"ready",headline:"Generated installed app",selected:{version:"0.4.0",path:"/generated/lms"},candidates:[],checks:[],update:{},app:{available:true}},
        {id:"freetoken",label:"Hidden FreeToken",level:"ready",selected,candidates:[candidate],checks:[],update:{},app:{available:true}}]});
    page.setDefaultTimeout(20_000);page.on("pageerror",error=>errors.push(error.message));
    await context.route("**/*",async route=>{try{
      const req=route.request(),url=new URL(req.url()),endpoint=url.pathname;if(url.origin!==base)return route.abort("blockedbyclient");
      if(!endpoint.startsWith("/api/")){const name=endpoint==="/"?"index.html":endpoint.slice(1);return /^[\w.-]+\.(?:js|css|html)$/.test(name)?route.fulfill({path:path.join(root,name)}):route.fulfill({status:404,body:""});}
      const body=req.method()==="POST"?req.postDataJSON():{};if(req.method()==="POST"){
        posts.push({endpoint,body});assert.ok(["/api/runtime/update/plan","/api/runtime/update/start","/api/runtime/update/stop","/api/runtime/promotion/plan",
          "/api/runtime/promotion/start","/api/runtime/promotion/stop","/api/runtime/promotion/apply","/api/runtime/select","/api/runtime/open",
          "/api/session/plan","/api/session/warm-plan","/api/session/attachment-plan","/api/benchmark/history","/api/chat/turn/recover"].includes(endpoint),"Fixture forbids actual model/install/config/quit requests");}
      let payload={phase:"idle",profiles:[],sets:[],threads:[],sessionSets:[],sessionSet:{phase:"idle"},runtimePromotion:{phase:"idle"}};
      if(endpoint==="/api/bootstrap")payload={token:"generated-token",controllerSourceCurrent:true,roots:[],clientSupport:{omlx:support},binaries:{omlx:{installed:true},pi:{installed:true},omp:{installed:true,consoleSupported:true}},
        adapters:{engines:[{id:"omlx",label:"oMLX",installed:true}],workSurfaces:[{id:"pi",label:"Pi",installed:true},{id:"omp",label:"oh-my-pi",installed:true},{id:"chat",label:"Chat",installed:true}]}};
      if(endpoint==="/api/models")payload={models:[model]};
      if(endpoint==="/api/status")payload=runActive?{phase:"running",events:[],run:{runId:"generated-run",purpose:"session",backend:"omlx",client:"pi",agentHost:"terminal",model:model.name,
        modelId:model.id,context:8192,output:1024,reasoning:"off",project:"/generated/project"},attachments:[]}:{phase:"idle",events:[]};
      if(endpoint==="/api/runtime/status"){inventoryReads++;if(inventoryFailed)return route.fulfill({status:503,json:{storageError:true,error:"Generated inspection unavailable; cached copies preserved"}});payload={runtimeManager:inventory()};}
      if(endpoint==="/api/runtime/update/status")payload={catalog,runtimeUpdate:update};
      if(endpoint==="/api/runtime/promotion/status")payload={runtimePromotion:promotion};
      if(endpoint==="/api/runtime/update/plan"){assert.deepEqual(body,{channel:"stable"});payload={plan:updatePlan()};}
      if(endpoint==="/api/runtime/update/start"){
        assert.deepEqual(body,{planId:"generated-update",confirmation:updatePlan().confirmation,reviewed:true});if(startFailed)return route.fulfill({status:409,json:{error:"Generated update rejected; retry safely"}});
        update={phase:"downloading",progress:.2,plan:updatePlan(),message:"Generated download only"};payload={plan:updatePlan()};}
      if(endpoint==="/api/runtime/update/stop"){assert.deepEqual(body,{});update={phase:"cancelled",plan:updatePlan(),message:"Generated update stopped safely"};payload={ok:true};}
      if(endpoint==="/api/runtime/promotion/plan"){
        assert.equal(body.backend,"omlx");assert.equal(body.candidateId,candidate.id);assert.equal(body.modelId,model.id);assert.equal(body.options.kv,"off");assert.equal(body.options.acceleration,"off");
        assert.equal(body.options.anePrefill,"off");assert.equal(body.options.burst,"balanced");assert.equal(body.suite,"agentic");payload={plan:comparison()};}
      if(endpoint==="/api/runtime/promotion/start"){assert.deepEqual(body,{planId:"generated-comparison",confirmation:comparison().confirmation,reviewed:true});promotion={phase:"running",plan:comparison(),message:"Generated comparison",progress:.5};payload={plan:comparison()};}
      if(endpoint==="/api/runtime/promotion/stop"){assert.deepEqual(body,{});promotion={phase:"cancelled",plan:comparison(),message:"Generated comparison stopped"};payload={ok:true};}
      if(endpoint==="/api/runtime/promotion/apply"){
        assert.deepEqual(body,{resultId:"generated-result",confirmation:result().confirmation});if(applyFailed)return route.fulfill({status:409,json:{error:"Generated promotion rejected; selected copy preserved"}});
        selectedId=candidate.id;promotion={phase:"completed",result:{...result(),selectionChanged:true}};payload={runtimeManager:inventory(),result:promotion.result};}
      if(endpoint==="/api/runtime/select"){
        assert.deepEqual(body,{runtime:"omlx",candidateId:selected.id,confirmation:"select:"+selected.id});if(selectFailed)return route.fulfill({status:409,json:{error:"Generated selection rejected; retry safely"}});selectedId=selected.id;payload={runtimeManager:inventory()};}
      if(endpoint==="/api/runtime/open"){assert.deepEqual(body,{runtime:"lms"});if(openFailed)return route.fulfill({status:503,json:{error:"Generated app opening failed; retry"}});payload={detail:"Generated app opening acknowledged"};}
      if(endpoint==="/api/chat/turn/recover")payload={recovered:false,discarded:false,threads:[]};
      if(endpoint==="/api/session/plan")payload={sessions:{hub:{phase:runActive?"running":"idle",attachments:[]},operation:{active:false},warmRoute:{canAttach:false},
        resource:{memoryAvailable:true,totalMemoryBytes:48*1024**3,headroomBytes:32*1024**3,headroomPercent:67},
        admission:{decision:"ready",launchable:true,requiresAcknowledgement:false,label:"Ready",contractId:"generated",estimate:{geometryReady:true,estimatedWorkingSetBytes:12*1024**3}}}};
      if(endpoint.startsWith("/api/runtime/"))replies.push({endpoint,phase:payload.runtimePromotion?.phase || payload.runtimeUpdate?.phase});
      return route.fulfill({json:payload});
    }catch(error){errors.push(error.message);await route.abort("failed");}});
    try {
      const out=path.join(root,"build/browser-qa");fs.mkdirSync(out,{recursive:true});
      await page.goto(base);await page.waitForFunction(()=>launchWorkspace.view().modelCount===1);await page.locator("#hubToolsMenuButton").click();await page.locator("#openRuntimeManager").click();
      await page.locator(".runtime-card").first().waitFor();assert.equal(await page.locator(".runtime-card").count(),2);assert.equal(await page.locator("#runtimeCards img").count(),0);
      assert.equal(posts.filter(item=>item.endpoint.startsWith("/api/runtime/")).length,0,"Opening Runtime Manager is read-only");
      await page.screenshot({path:path.join(out,"runtime-manager-desktop.png")});await page.setViewportSize({width:390,height:844});
      assert.equal(await page.locator("#runtimeDialog").evaluate(node=>node.scrollWidth<=node.clientWidth+1),true);
      await page.screenshot({path:path.join(out,"runtime-manager-mobile.png")});await page.setViewportSize({width:1440,height:1000});
      const first=page.locator('.runtime-card-details[data-runtime-disclosure="omlx:card"]');await first.locator("summary").first().click();
      const compare=page.locator('[data-runtime-compare="candidate-exact"]');await compare.focus();
      await page.evaluate(()=>{window.savedRuntimeButton=document.querySelector('[data-runtime-compare="candidate-exact"]');for(let i=0;i<25;i++)runtimeManager.renderInventory(runtimeManager.snapshot().runtimeInventory);});
      assert.equal(await compare.evaluate(node=>node===window.savedRuntimeButton&&node===document.activeElement),true);
      inventoryFailed=true;await page.locator("#refreshRuntimeManager").click();await page.waitForFunction(()=>document.getElementById("runtimeManagerStatus").textContent.includes("cached copies preserved"));
      assert.equal(await page.locator(".runtime-card").count(),2);inventoryFailed=false;await page.locator("#refreshRuntimeManager").click();
      await page.locator("#runtimeAdvancedTools>summary").click();assert.equal(await page.locator('[data-runtime-update-channel="blocked"]').isDisabled(),true);
      await page.locator('[data-runtime-update-channel="stable"]').click();await page.waitForFunction(()=>!document.getElementById("runtimeUpdateConsent").disabled);
      assert.match(await page.locator("#runtimeUpdatePlan").innerText(),new RegExp("a".repeat(40)));assert.match(await page.locator("#runtimeUpdatePlan").innerText(),new RegExp("b".repeat(64)));
      assert.equal(await page.locator("#runtimeUpdateStartButton").isDisabled(),true);assert.equal(posts.filter(item=>item.endpoint==="/api/runtime/update/start").length,0);
      await page.locator("#runtimeUpdateConsent").check();runActive=true;await page.evaluate(()=>pollStatus());assert.equal(await page.locator("#runtimeUpdateStartButton").isDisabled(),true);
      runActive=false;await page.evaluate(()=>pollStatus());assert.equal(await page.locator("#runtimeUpdateStartButton").isEnabled(),true);
      startFailed=true;await page.locator("#runtimeUpdateStartButton").click();await page.waitForFunction(()=>document.getElementById("runtimeUpdateStatus").textContent.includes("retry safely"));
      assert.equal(await page.locator("#runtimeUpdateStartButton").isEnabled(),true);await page.evaluate(()=>pollRuntimeUpdateStatus());assert.match(await page.locator("#runtimeUpdateStatus").innerText(),/retry safely/);
      await page.screenshot({path:path.join(out,"runtime-update-desktop.png")});
      await page.setViewportSize({width:390,height:844});assert.equal(await page.locator("#runtimeDialog").evaluate(node=>node.scrollWidth<=node.clientWidth+1),true);
      await page.locator("#runtimeUpdateStatus").scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,"runtime-update-mobile.png")});
      startFailed=false;await page.locator("#runtimeUpdateStartButton").click();await page.waitForFunction(()=>!document.getElementById("runtimeUpdateStopButton").disabled);
      await page.locator("#runtimeUpdateStopButton").click();await page.waitForFunction(()=>document.getElementById("runtimeUpdatePhase").textContent==="Stopped");
      const before=inventoryReads;update={phase:"completed",plan:updatePlan(),result:{version:release.version,action:"install",path:"/generated/runtime",selectionChanged:false}};
      await page.evaluate(()=>pollRuntimeUpdateStatus());await page.waitForFunction(()=>!runtimeManager.snapshot().runtimeLoading);
      assert.ok(inventoryReads>before);assert.equal(selectedId,selected.id);assert.equal(posts.filter(item=>item.endpoint==="/api/runtime/select").length,0);
      await compare.click();await page.waitForFunction(()=>document.getElementById("runtimePromotionPhase").textContent==="Plan ready");
      await page.locator("#runtimePromotionSuite").selectOption("quick");assert.equal(await page.locator("#runtimePromotionStartButton").isDisabled(),true);
      await page.locator("#runtimePromotionSuite").selectOption("agentic");await compare.click();await page.waitForFunction(()=>!document.getElementById("runtimePromotionStartButton").disabled);
      assert.equal(posts.filter(item=>item.endpoint==="/api/runtime/promotion/start").length,0,"Comparison inspection never measures or changes selection");
      await page.locator("#runtimePromotionStartButton").click();await page.waitForFunction(()=>!document.getElementById("runtimePromotionStopButton").disabled);
      await page.locator("#runtimePromotionStopButton").click();await page.waitForFunction(()=>document.getElementById("runtimePromotionPhase").textContent==="Stopped");
      promotion={phase:"completed",plan:comparison(),result:result()};await page.evaluate(()=>pollRuntimePromotionStatus());
      const promote=page.locator('[data-runtime-promote="generated-result"]');await promote.waitFor();assert.equal(selectedId,selected.id);
      applyFailed=true;await promote.click();await page.waitForFunction(()=>document.getElementById("runtimePromotionStatus").textContent.includes("selected copy preserved"));
      assert.equal(await promote.isEnabled(),true);await page.locator("#runtimePromotionStatus").scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,"runtime-promotion-mobile.png")});
      await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:path.join(out,"runtime-promotion-desktop.png")});
      applyFailed=false;await promote.click();await page.waitForFunction(()=>document.getElementById("runtimePromotionStatus").textContent.includes("is selected for new sessions"));
      assert.equal(selectedId,candidate.id);const rollback=page.locator('[data-runtime-select="omlx"][data-candidate-id="selected-exact"]');
      selectFailed=true;await rollback.click();await page.waitForFunction(()=>document.getElementById("runtimeManagerStatus").textContent.includes("selection rejected"));
      assert.equal(await rollback.isEnabled(),true);selectFailed=false;await rollback.click();await page.waitForFunction(()=>document.getElementById("runtimeManagerStatus").textContent.includes("selection updated"));assert.equal(selectedId,selected.id);
      assert.equal(await page.locator('[data-runtime-select="omlx"][data-candidate-id="candidate-exact"]').isEnabled(),true,"Selection completion restores other runtime controls");
      assert.equal(await page.locator("#runtimeManagerStatus").getAttribute("data-error"),"false");
      const app=page.locator('[data-runtime-open="lms"]');await page.locator('.runtime-card-details[data-runtime-disclosure="lms:card"]>summary').click();
      openFailed=true;await app.click();await page.waitForFunction(()=>document.getElementById("runtimeManagerStatus").textContent.includes("app opening failed"));assert.equal(await app.isEnabled(),true);
      openFailed=false;await app.click();await page.waitForFunction(()=>document.getElementById("runtimeManagerStatus").textContent.includes("opening acknowledged"));
      assert.deepEqual(errors,[]);assert.equal(await page.evaluate(()=>window.attacked===true),false);
      const failed=path.join(out,"runtime-manager-failure.json");if(fs.existsSync(failed))fs.unlinkSync(failed);
      fs.writeFileSync(path.join(out,"runtime-manager-proof.json"),JSON.stringify({fixture:"generated-only-no-runtime-or-model",posts,errors,inventoryReads},null,2));
      console.log("Runtime Manager integrated browser passed: read-only inventory/inspection, exact approval, cached errors, focus, active-route guard, Stop/retry, no automatic selection, measured promotion/rollback/app-open and desktop/mobile.");
    }catch(error){const out=path.join(root,"build/browser-qa");fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,"runtime-manager-failure.json"),JSON.stringify({errors,posts,replies,snapshot:await page.evaluate(()=>runtimeManager.snapshot()),promotion,text:await page.locator("body").innerText()},null,2));throw error;}
    finally{await browser.close();}
  })().catch(error=>{console.error(error);process.exitCode=1;});
}
