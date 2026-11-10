"use strict";
// Synthetic catalog, read-only plans and generated Quit responses in a real
// browser. No server, model, installed binary or user profile is touched.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
if (!process.env.LLM_LAUNCHER_BROWSER_PACKAGE) {
  console.log("Populated launcher browser fixture skipped (opt-in).");
} else {
  const {chromium} = require(process.env.LLM_LAUNCHER_BROWSER_PACKAGE);
  const root = path.resolve(__dirname,"..");
  const base = "http://127.0.0.1:18999";
  const support = {pi:{supported:true,reason:"Generated fixture transport"},
    omp:{supported:true,reason:"Generated fixture transport in Terminal"},
    chat:{supported:true,reason:"Generated fixture Chat"},
    opencode:{supported:false,reason:"Unavailable in this generated fixture"},
    codex:{supported:false,reason:"Unavailable in this generated fixture"}};
  const capability = {runnable:true,reason:"Generated fixture only",agentReasoning:["auto","off","low","medium","xhigh"],
    contextWindows:[16384,32768,65536,131072,262144],outputMaximum:261120,
    customSampling:true,kvChoices:["off","q8","q4"],clientSupport:support};
  const models = [
    {id:"fixture-qwen-27b",name:"Qwen3.5 27B · Q4_K_M",format:"gguf",quantization:"Q4_K_M",sizeLabel:"16.7 GB",
      ready:true,status:"Ready",nativeContext:262144,origins:["Synthetic catalog"],backends:{splash:capability,kolibri:capability}},
    {id:"fixture-qwen-35b",name:"Qwen3.5 35B-A3B · Q4_K_M",format:"gguf",quantization:"Q4_K_M",sizeLabel:"20.1 GB",
      ready:true,status:"Ready",nativeContext:262144,origins:["Synthetic catalog"],backends:{splash:capability}},
    {id:"fixture-kolibri",name:"Kolibri Qwen · full Q6 experts",format:"gguf",quantization:"Q6_K",sizeLabel:"Synthetic expert model",
      ready:true,status:"Ready",nativeContext:262144,origins:["Synthetic catalog"],backends:{kolibri:capability}},
  ];
  const boot = {token:"generated-fixture-token",controllerSourceCurrent:true,roots:[{label:"Documents",path:"/workspace/models"}],
    binaries:Object.fromEntries(["splash","kolibri","pi","omp"].map(id=>[id,{installed:true,version:"Generated fixture",path:"/fixture/"+id}])),
    adapters:{engines:[{id:"splash",label:"Splash",binaryKey:"splash",installed:true},{id:"kolibri",label:"Kolibri SSD",binaryKey:"kolibri",installed:true}],
      workSurfaces:[{id:"pi",label:"Pi",installed:true},{id:"omp",label:"oh-my-pi",installed:true},{id:"chat",label:"Chat",installed:true}]},
    clientSupport:{splash:support,kolibri:support}};
  (async()=>{
    const browser = await chromium.launch({headless:true});
    const context = await browser.newContext({viewport:{width:1440,height:1100}});
    const page = await context.newPage();
    const errors = [], posts = [];
    let quitAttempts=0,quitStatusReads=0;
    page.on("pageerror",error=>errors.push(error.message));
    page.setDefaultTimeout(20_000);
    await context.route("**/*",route=>{
      const request=route.request(), url=new URL(request.url()), endpoint=url.pathname;
      if (url.origin !== base) return route.abort("blockedbyclient");
      if (!endpoint.startsWith("/api/")) {
        const name=endpoint==="/"?"index.html":endpoint.slice(1);
        if (!/^[\w.-]+\.(?:js|css|html)$/.test(name)) return route.fulfill({status:404,body:""});
        return route.fulfill({path:path.join(root,name)});
      }
      let payload={phase:"idle",profiles:[],sessionSets:[],threads:[],sessionSet:{phase:"idle"},runtimePromotion:{phase:"idle"}};
      if (request.method()==="POST") {
        posts.push({endpoint,body:request.postDataJSON()});
        assert.ok(["/api/benchmark/history","/api/session/plan","/api/session/warm-plan","/api/session/attachment-plan","/api/chat/turn/recover","/api/quit"].includes(endpoint),"Only generated plans and mock Quit responses are allowed");
      }
      const body=request.method()==="POST"?request.postDataJSON():{};
      if (endpoint==="/api/bootstrap") payload=boot;
      if (endpoint==="/api/models") payload={models};
      if (endpoint==="/api/quit") {
        if (++quitAttempts<3) return route.fulfill({status:409,json:{error:"Generated fixture: controller rejected shutdown."}});
        payload={quitting:true};
      }
      if (endpoint==="/api/quit/status") payload=++quitStatusReads===1?{quitting:true,complete:false}:{quitting:true,complete:true,errors:[],processesStopped:0};
      if (endpoint==="/api/chat/turn/recover") payload={recovered:false,discarded:false,threads:[]};
      if (endpoint==="/api/session/plan") payload={sessions:{
        hub:{phase:"idle",attachments:[]},operation:{active:false},warmRoute:{canAttach:false},
        resource:{totalMemoryBytes:48*1024**3,headroomBytes:40*1024**3,headroomPercent:83,memoryAvailable:true},
        admission:{decision:"ready",launchable:true,requiresAcknowledgement:false,label:"Ready",detail:"Generated capacity plan",contractId:"fixture-contract",
          estimate:{estimatedWorkingSetBytes:32.5*1024**3,osReserveBytes:8*1024**3,geometryReady:true,modelBytes:17*1024**3,kvCacheBytes:12*1024**3,runtimeReserveBytes:3.5*1024**3,contextTokens:body.context,kvPrecision:body.options?.kv||"off",basis:"Generated fixture only"}}}};
      if (endpoint==="/api/benchmark/history") payload={history:{series:[],runs:[],contract:{modelId:body.modelId},receipt:{backend:body.backend,backendLabel:body.backend==="splash"?"Splash":"Kolibri SSD",state:"trusted-route",fresh:true,suite:body.suite,suiteLabel:"Generated fixture",decodeTokensPerSecond:31.25,firstTokenSeconds:0.39,modeLabel:"DFlash2",eligibleBackends:[],recordId:"generated-fixture-only",summary:"Generated fixture measurement; not hardware evidence."}}};
      return route.fulfill({json:payload});
    });
    try {
      await page.goto(base);
      await page.waitForFunction(()=>document.getElementById("homeMeasuredSpeed").textContent==="31.3 tok/s").catch(async error=>{console.error({errors,notice:await page.locator("#notice").textContent()});throw error;});
      assert.equal(await page.locator("#modelSelect").inputValue(),models[0].id);
      await page.locator('[data-client="omp"]').click();
      assert.equal(await page.locator("#agentHostSelect").inputValue(),"terminal");
      assert.equal(await page.locator('#agentHostSelect option[value="console"]').evaluate(node=>node.disabled),true);
      await page.waitForFunction(()=>document.getElementById("homeRouteAgent").textContent==="oh-my-pi" && !document.getElementById("launchButton").disabled);
      await page.locator("#contextSelect").selectOption("262144");
      await page.locator("#outputInput").fill("200000");
      await page.locator("#outputInput").press("Tab");
      await page.locator("#reasoningSelect").selectOption("xhigh");
      await page.locator("#homeEngineSelect").selectOption("kolibri");
      assert.equal(await page.locator("#modelSelect").inputValue(),models[0].id,"Changing runtime keeps the selected weights");
      assert.notEqual(await page.locator("#outputInput").inputValue(),"200000","An unconfigured runtime starts with its own defaults");
      await page.locator("#homeEngineSelect").selectOption("splash");
      assert.equal(await page.locator("#contextSelect").inputValue(),"262144");
      assert.equal(await page.locator("#outputInput").inputValue(),"200000");
      assert.equal(await page.locator("#reasoningSelect").inputValue(),"xhigh");
      await page.locator("#homeModelSearch").fill("35B");
      assert.equal(await page.locator("#modelSelect").inputValue(),models[0].id,"Filtering must keep the selected model");
      assert.match(await page.locator("#homeModelSearchStatus").innerText(),/1 match/);
      await page.locator(`[data-home-model="${models[1].id}"]`).click();
      assert.notEqual(await page.locator("#outputInput").inputValue(),"200000","A different model keeps its own response limit");
      await page.locator("#homeModelSearch").fill("");
      await page.waitForFunction(()=>document.getElementById("homeRouteModel").textContent.includes("35B-A3B"));
      await page.waitForFunction(()=>document.getElementById("homeMeasuredSpeed").textContent==="31.3 tok/s");
      assert.ok(posts.some(item=>item.endpoint==="/api/session/plan"&&item.body.client==="omp"&&item.body.agentHost==="terminal"));
      const output=path.join(root,"build/browser-qa");fs.mkdirSync(output,{recursive:true});
      await page.locator("#homeModelSearch").blur();
      await page.screenshot({path:path.join(output,"launcher-home-populated-desktop.png")});
      await page.setViewportSize({width:390,height:844});
      assert.ok(await page.locator("#homeModelList").evaluate(node=>node.getBoundingClientRect().width)>300);
      assert.ok(await page.locator("#launchOverview").evaluate(node=>node.getBoundingClientRect().width)>300);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      assert.match(await page.locator("#quitLauncherButton").innerText(),/Quit/);
      await page.screenshot({path:path.join(output,"launcher-home-populated-mobile.png"),fullPage:true});
      await page.setViewportSize({width:1440,height:1100});
      await page.locator(`[data-home-model="${models[2].id}"]`).click();
      await page.waitForFunction(()=>document.getElementById("homeRouteModel").textContent.includes("Kolibri"));
      await page.locator("#launchSettings").evaluate(node=>node.open=true);
      await page.locator("#advancedControls").evaluate(node=>node.open=true);
      await page.locator("#kolibriKv").selectOption("q4");
      await page.waitForFunction(()=>document.getElementById("homeMeasuredSpeed").textContent==="31.3 tok/s");
      await page.waitForFunction(()=>document.getElementById("homeRouteReadiness").textContent==="Ready to launch");
      assert.ok(posts.some(item=>item.endpoint==="/api/benchmark/history"&&item.body.backend==="kolibri"&&item.body.options.kv==="q4"));
      await page.locator(`[data-home-model="${models[0].id}"]`).click();
      await page.locator("#homeEngineSelect").selectOption("splash");
      assert.equal(await page.locator("#outputInput").inputValue(),"200000");
      await page.locator(`[data-home-model="${models[2].id}"]`).click();
      assert.equal(await page.locator("#kolibriKv").inputValue(),"q4");
      // Qualification enables a deliberate Console choice. A later unavailable
      // version must restore Terminal before any read-only plan is requested.
      boot.binaries.omp.consoleSupported=true;
      boot.binaries.omp.consoleProtocol="omp-rpc";
      await page.reload(); await page.locator('[data-client="omp"]').click();
      await page.locator("#launchSettings").evaluate(node=>node.open=true);
      assert.equal(await page.locator('#agentHostSelect option[value="console"]').evaluate(node=>node.disabled),false);
      const consolePlan=page.waitForResponse(response=>new URL(response.url()).pathname==="/api/session/plan"
        &&response.request().postDataJSON()?.agentHost==="console"&&response.request().postDataJSON()?.client==="omp");
      await page.locator("#agentHostSelect").selectOption("console");
      await page.waitForFunction(()=>document.getElementById("homeRouteAgent").textContent==="oh-my-pi"&&
        !document.getElementById("launchButton").disabled);
      await consolePlan;
      assert.ok(posts.some(item=>item.endpoint==="/api/session/plan"&&item.body.client==="omp"&&item.body.agentHost==="console"));
      boot.binaries.omp.consoleSupported=false;
      await page.reload(); await page.locator('[data-client="omp"]').click();
      assert.equal(await page.locator("#agentHostSelect").inputValue(),"terminal");
      assert.equal(await page.locator('#agentHostSelect option[value="console"]').evaluate(node=>node.disabled),true);
      await page.locator("#quitLauncherButton").click();
      await page.waitForFunction(()=>document.getElementById("quitLauncherTitle").textContent==="Could not quit the launcher");
      assert.ok(await page.locator("#quitLauncherDialog").isVisible(),"Rejected Quit stays visible on every workspace");
      assert.ok(await page.locator("#quitLauncherRetryButton").evaluate(node=>node===document.activeElement));
      await page.keyboard.press("Escape");
      assert.equal(await page.locator("#quitLauncherDialog").evaluate(node=>node.open),false);
      await page.locator("#quitLauncherButton").click();
      await page.waitForFunction(()=>document.getElementById("quitLauncherTitle").textContent==="Could not quit the launcher");
      await page.screenshot({path:path.join(output,"launcher-quit-error.png")});
      await page.locator("#quitLauncherRetryButton").click();
      await page.keyboard.press("Escape");
      assert.equal(await page.locator("#quitLauncherDialog").evaluate(node=>node.open),true,"Escape cannot cancel a dispatched shutdown");
      await page.waitForFunction(()=>document.getElementById("quitLauncherTitle").textContent==="Launcher closed");
      assert.match(await page.locator("#quitLauncherDetail").innerText(),/have been stopped/);
      assert.equal(quitAttempts,3,"Only explicit clicks dispatch mock shutdown requests");
      assert.deepEqual(errors,[]);
      console.log("Populated browser: synthetic catalog/search, qualified OMP Console plans/version fallback, exact receipt TPS, mobile geometry and generated Quit rejection/retry/completion passed. No model loaded.");
    } finally {await browser.close();}
  })().catch(error=>{console.error(error);process.exitCode=1;});
}
