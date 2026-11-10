"use strict";
// Every request is generated/intercepted: no Hub access, download or model.
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
if(!process.env.LLM_LAUNCHER_BROWSER_PACKAGE)console.log("Model Library/acquisition browser fixture skipped (opt-in).");
else {
  const {chromium}=require(process.env.LLM_LAUNCHER_BROWSER_PACKAGE),root=path.resolve(__dirname,".."),base="http://127.0.0.1:18793";
  const support={pi:{supported:true},omp:{supported:true},chat:{supported:true},opencode:{supported:false},codex:{supported:false}};
  const cap={runnable:true,agentReasoning:["off","medium"],customSampling:true,kvChoices:["off","q8","q6","q4"],
    contextWindows:[2048,4096,8192,16384,32768],outputMaximum:8192,clientSupport:support};
  const model={id:"asset-q6",name:"Generated Original Q6 <img src=x>",ready:true,status:"Ready",format:"gguf",quantization:"Q6_K",
    nativeContext:32768,sizeLabel:"Generated weights",origins:["Generated"],architecture:"qwen",path:"/generated/model.gguf",backends:{kolibri:cap}};
  const engine={id:"kolibri",label:"Kolibri SSD",runnable:true,status:"ready",reason:"Generated compatibility",
    surfaces:[{id:"pi",label:"Pi",supported:true},{id:"omp",label:"oh-my-pi",supported:true}],modes:[{id:"ar",label:"AR",available:true}]};
  const report={...model,engines:[engine],doctor:{checks:[{state:"pass",label:"Original weights",detail:"Generated check"}]}};
  const commit="a".repeat(40),variants=[{id:"q6",label:"Original Q6",sizeBytes:100},{id:"q4",label:"Other Q4",sizeBytes:70}];
  const pinned=variant=>({id:"plan-"+variant,confirmation:"generated/repository@"+commit+":"+variant,canStart:Boolean(variant),variantRequired:!variant,
    repo:{id:"generated/repository",pinnedRevision:commit,license:"MIT"},expiresAt:"2099-01-01T00:00:00Z",variants,
    destination:{kind:"documents",label:"Generated model root",path:"/generated/models/repository",remainingBytes:100,existingBytes:0},
    selection:variant?{id:variant,label:variant==="q6"?"Original Q6":"Other Q4",format:"gguf",fileCount:1,sizeBytes:variant==="q6"?100:70,
      files:[{path:variant+".gguf",size:variant==="q6"?100:70,sha256:"b".repeat(64)}]}:null,
    checks:[{state:variant?"pass":"blocked",label:"Exact file set",detail:variant?"Pinned size and checksum":"Choose one file set"}],
    expectedEngines:[{id:"kolibri",label:"Kolibri SSD",expectedCompatible:true,expectedReady:true,detail:"Scanner prediction only"}]});
  (async()=>{
    const browser=await chromium.launch({headless:true}),context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
    const errors=[],posts=[];let phase="idle",activePlan=null,failedInspect=false,failedStart=false,failedLibrary=false,runActive=false;
    page.setDefaultTimeout(20_000);page.on("pageerror",error=>errors.push(error.message));
    await context.route("**/*",async route=>{try{
      const req=route.request(),url=new URL(req.url()),endpoint=url.pathname;
      if(url.origin!==base)return route.abort("blockedbyclient");
      if(!endpoint.startsWith("/api/")){const name=endpoint==="/"?"index.html":endpoint.slice(1);
        return /^[\w.-]+\.(?:js|css|html)$/.test(name)?route.fulfill({path:path.join(root,name)}):route.fulfill({status:404,body:""});}
      const body=req.method()==="POST"?req.postDataJSON():{};if(req.method()==="POST"){
        posts.push({endpoint,body});assert.ok(["/api/acquisition/search","/api/acquisition/inspect","/api/acquisition/start","/api/acquisition/stop",
          "/api/session/plan","/api/session/warm-plan","/api/session/attachment-plan","/api/benchmark/history","/api/chat/turn/recover"].includes(endpoint),"Fixture forbids any model launch or unrelated mutation");}
      let payload={phase:"idle",profiles:[],sets:[],threads:[],sessionSets:[],sessionSet:{phase:"idle"},runtimePromotion:{phase:"idle"}};
      if(endpoint==="/api/bootstrap")payload={token:"generated-token",controllerSourceCurrent:true,roots:[],clientSupport:{kolibri:support},
        binaries:{kolibri:{installed:true},pi:{installed:true},omp:{installed:true,consoleSupported:true}},
        adapters:{engines:[{id:"kolibri",label:"Kolibri SSD",installed:true}],workSurfaces:[{id:"pi",label:"Pi",installed:true},{id:"omp",label:"oh-my-pi",installed:true},{id:"chat",label:"Chat",installed:true}]}};
      if(endpoint==="/api/models")payload={models:[model]};
      if(endpoint==="/api/status")payload=runActive?{phase:"running",run:{runId:"generated-run",purpose:"session",backend:"kolibri",client:"pi",
        agentHost:"terminal",model:model.name,modelId:model.id,context:8192,output:1024,reasoning:"off",project:"/generated/project"},events:[],attachments:[]}:{phase:"idle",events:[]};
      if(endpoint==="/api/model-library"){
        if(failedLibrary)return route.fulfill({status:503,json:{error:"Generated library network error; cached catalog kept"}});
        payload={models:[model],modelLibrary:{models:[report]},roots:[{id:"generated",path:"/generated/models",exists:true}]};}
      if(endpoint==="/api/acquisition/status")payload={acquisition:{phase,progress:phase==="downloading"?.5:0,message:"Generated acquisition status",plan:activePlan,result:null},
        downloaderReady:true,roots:[{id:"documents",label:"Generated models",path:"/generated/models"}]};
      if(endpoint==="/api/acquisition/search")payload={search:{results:[{id:"generated/repository",revision:"main",formats:["gguf"],license:"MIT",inspectable:true,downloads:1,likes:1},
        {id:"gated/repository",gated:true,inspectable:false,formats:["gguf"],license:"Custom"}]}};
      if(endpoint==="/api/acquisition/inspect"){
        if(failedInspect)return route.fulfill({status:503,json:{error:"Generated inspection unavailable; retry safely"}});
        assert.equal(body.repoId,"generated/repository");assert.equal(body.destination,"documents");payload={plan:pinned(body.variantId)};}
      if(endpoint==="/api/acquisition/start"){
        assert.deepEqual(body,{planId:"plan-q6",confirmation:pinned("q6").confirmation,licenseReviewed:true});
        if(failedStart)return route.fulfill({status:409,json:{error:"Generated start rejected; no files changed"}});
        phase="downloading";activePlan=pinned("q6");payload={plan:activePlan};}
      if(endpoint==="/api/acquisition/stop"){assert.deepEqual(body,{});phase="cancelled";payload={ok:true};}
      if(endpoint==="/api/chat/turn/recover")payload={recovered:false,discarded:false,threads:[]};
      if(endpoint==="/api/session/plan")payload={sessions:{hub:{phase:runActive?"running":"idle",attachments:[]},operation:{active:false},warmRoute:{canAttach:false},
        resource:{memoryAvailable:true,totalMemoryBytes:48*1024**3,headroomBytes:32*1024**3,headroomPercent:67},
        admission:{decision:"ready",launchable:true,requiresAcknowledgement:false,label:"Ready",contractId:"generated",estimate:{geometryReady:true,estimatedWorkingSetBytes:12*1024**3}}}};
      return route.fulfill({json:payload});
    }catch(error){errors.push(error.message);await route.abort("failed");}});
    try{
      await page.goto(base);await page.waitForFunction(()=>launchWorkspace.view().modelCount===1);
      await page.locator("#openModelLibrary").click();await page.locator(".model-library-card").waitFor();
      assert.equal(await page.locator("#modelLibraryCards img").count(),0);
      await page.locator("#modelLibraryEngineFilter").selectOption("kolibri");assert.equal(await page.locator(".model-library-card").count(),1);
      await page.locator("#modelLibrarySurfaceFilter").selectOption("omp");assert.equal(await page.locator(".model-library-card").count(),1);
      await page.locator("#modelLibrarySearch").fill("no-matching-name");assert.equal(await page.locator(".model-library-card").count(),0);
      await page.locator("#clearModelLibraryFilters").click();assert.equal(await page.locator("#modelLibrarySearch").evaluate(node=>node===document.activeElement),true);
      failedLibrary=true;await page.locator("#refreshModelLibrary").click();await page.waitForFunction(()=>document.getElementById("modelLibraryStatus").textContent.includes("cached catalog kept"));
      assert.equal(await page.locator(".model-library-card").count(),1);failedLibrary=false;
      await page.locator('[data-library-model="asset-q6"][data-library-backend="kolibri"]').click();
      await page.waitForFunction(()=>!document.getElementById("modelLibraryDialog").open);assert.ok(!posts.some(item=>item.endpoint==="/api/launch"));
      await page.locator("#openModelLibrary").click();await page.locator("#openAcquisitionCenter").click();
      await page.locator("#acquisitionSearch").fill("Generated public Q6");await page.locator("#acquisitionSearchButton").click();
      await page.locator('[data-acquisition-repo="generated/repository"]').waitFor();
      assert.equal(await page.locator('[data-acquisition-repo="gated/repository"]').isDisabled(),true);
      await page.locator('[data-acquisition-repo="generated/repository"]').click();await page.locator("#acquisitionVariantField").waitFor({state:"visible"});
      assert.equal(await page.locator("#acquisitionStartButton").isDisabled(),true);
      await page.locator("#acquisitionVariant").selectOption("q6");await page.waitForFunction(()=>!document.getElementById("acquisitionConsent").disabled);
      assert.match(await page.locator("#acquisitionPlan").innerText(),/MIT/);assert.match(await page.locator("#acquisitionPlan").innerText(),/Original Q6/);
      assert.equal(posts.filter(item=>item.endpoint==="/api/acquisition/start").length,0,"Search and inspection never download");
      await page.locator("#acquisitionConsent").check();await page.locator("#acquisitionRepoId").fill("edited/repository");
      assert.equal(await page.locator("#acquisitionStartButton").isDisabled(),true);assert.equal(await page.locator("#acquisitionConsent").isChecked(),false);
      await page.locator("#acquisitionRepoId").fill("generated/repository");failedInspect=true;await page.locator("#acquisitionInspectButton").click();
      await page.waitForFunction(()=>document.getElementById("acquisitionStatus").textContent.includes("retry safely"));assert.equal(await page.locator("#acquisitionStartButton").isDisabled(),true);
      failedInspect=false;await page.locator("#acquisitionInspectButton").click();await page.locator("#acquisitionVariant").selectOption("q6");
      await page.waitForFunction(()=>!document.getElementById("acquisitionConsent").disabled);
      runActive=true;await page.evaluate(()=>pollStatus());assert.equal(await page.locator("#acquisitionConsent").isDisabled(),true);
      runActive=false;await page.evaluate(()=>pollStatus());await page.locator("#acquisitionConsent").check();
      assert.doesNotMatch(await page.locator("#acquisitionConsentCopy").innerText(),/Finish or stop/);
      failedStart=true;await page.locator("#acquisitionStartButton").click();await page.waitForFunction(()=>document.getElementById("acquisitionStatus").textContent.includes("start rejected"));
      assert.equal(await page.locator("#acquisitionStartButton").isEnabled(),true);
      assert.equal(await page.locator("#acquisitionStatus").isVisible(),true);
      const output=path.join(root,"build/browser-qa");fs.mkdirSync(output,{recursive:true});
      await page.screenshot({path:path.join(output,"model-acquisition-desktop.png")});await page.setViewportSize({width:390,height:844});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      await page.screenshot({path:path.join(output,"model-acquisition-mobile.png")});
      failedStart=false;await page.locator("#acquisitionStartButton").click();await page.waitForFunction(()=>document.getElementById("acquisitionStopButton").disabled===false);
      await page.locator("#acquisitionStopButton").click();await page.waitForFunction(()=>document.getElementById("acquisitionPhase").textContent.includes("resumable"));
      assert.equal(posts.filter(item=>item.endpoint==="/api/acquisition/start").length,2);assert.equal(posts.filter(item=>item.endpoint==="/api/acquisition/stop").length,1);
      assert.deepEqual(errors,[]);const stale=path.join(output,"model-assets-failure.json");if(fs.existsSync(stale))fs.unlinkSync(stale);
      console.log("Integrated model assets browser: inert catalog/filter/apply-only, exact variant/license/commit, changed-input consent, inspection/start retry, active-route guard, stop/resume and desktop/mobile passed. All replies generated; no download or model.");
    }catch(error){const output=path.join(root,"build/browser-qa");fs.mkdirSync(output,{recursive:true});fs.writeFileSync(path.join(output,"model-assets-failure.json"),JSON.stringify({errors,posts,text:await page.locator("body").innerText()},null,2));throw error;}
    finally{await browser.close();}
  })().catch(error=>{console.error(error);process.exitCode=1;});
}
