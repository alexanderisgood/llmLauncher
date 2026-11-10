"use strict";
// Actual app/modules with generated API responses only. Intercept every
// request; never contact a controller, load a model or read user history.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
if (!process.env.LLM_LAUNCHER_BROWSER_PACKAGE) {
  console.log("Saved Chat resume browser fixture skipped (opt-in).");
} else {
  const {chromium} = require(process.env.LLM_LAUNCHER_BROWSER_PACKAGE);
  const root = path.resolve(__dirname, "..");
  const base = "http://127.0.0.1:18791";
  const support = {chat:{supported:true}, pi:{supported:true}, omp:{supported:true},
    codex:{supported:false}, opencode:{supported:false}};
  const cap = {runnable:true, customSampling:true, contextWindows:[2048,4096,8192,16384,32768],
    contextMaximum:32768, outputMaximum:8192, agentReasoning:["off","low","medium","high"],
    kv:true, kvChoices:["off","q8","q6","q4"], prefillSizes:[64,128,256], clientSupport:support};
  const model = {id:"fixture-q6", name:"Generated Kolibri Q6", format:"mlx", ready:true, status:"Ready",
    quantization:"6-bit", sizeLabel:"Generated weights", nativeContext:32768,
    origins:["Generated fixture"], backends:{kolibri:cap}};
  const historyId = "9d12aa4e-c129-4c53-bad0-0fce34611c6b";
  const thread = {id:historyId, title:'Saved <img src=x onerror="window.attacked=true">', model:model.name,
    backend:"kolibri", context:8192, output:1024, reasoning:"off", resumeAvailable:true,
    resumeNeedsSystemPrompt:true, updatedAt:"2026-10-06T12:00:00Z", messageCount:2,
    messages:[{role:"user",content:"Generated fixture question"},{role:"assistant",content:"Generated fixture answer"}]};
  const requestTemplate = {backend:"kolibri",client:"chat",modelId:model.id,project:"/generated/project",
    context:8192,output:1024,reasoning:"off",mode:"custom",
    options:{acceleration:"off",depth:1,kv:"off",memoryMode:"auto",memoryGB:12,prefillSize:64,promptCacheGB:1},
    generation:{sampling:"custom",temperature:0,topP:1,topK:0},chat:{sampling:"custom",temperature:0,topP:1,topK:0}};
  (async () => {
    const browser = await chromium.launch({headless:true});
    const context = await browser.newContext({viewport:{width:1440,height:1000}});
    const page = await context.newPage();
    const errors = [], posts = [], launches = [];
    let memoryContract = "capacity-one", failPlan = false, launched = false;
    const run = {runId:"30266d96-92d7-4e3d-bca4-467f75a9e539", purpose:"session", client:"chat", backend:"kolibri",modelId:model.id,
      model:model.name, project:"/generated/project", context:8192, output:1024, reasoning:"off", options:requestTemplate.options};
    page.on("pageerror", error => errors.push(error.message));
    page.setDefaultTimeout(20_000);
    await context.route("**/*", async route => {
      const req = route.request(), url = new URL(req.url()), endpoint = url.pathname;
      if (url.origin !== base) return route.abort("blockedbyclient");
      if (!endpoint.startsWith("/api/")) {
        const name = endpoint === "/" ? "index.html" : endpoint.slice(1);
        if (!/^[\w.-]+\.(?:js|css|html)$/.test(name)) return route.fulfill({status:404,body:""});
        return route.fulfill({path:path.join(root,name)});
      }
      const body = req.method() === "POST" ? req.postDataJSON() : {};
      if (req.method() === "POST") posts.push({endpoint,body});
      let payload = {phase:"idle",profiles:[],sessionSets:[],threads:[thread],sessionSet:{phase:"idle"},runtimePromotion:{phase:"idle"}};
      if (endpoint === "/api/bootstrap") payload = {token:"synthetic-token", controllerSourceCurrent:true,
        roots:[{label:"Generated",path:"/generated/models"}], clientSupport:{kolibri:support},
        binaries:{kolibri:{installed:true,version:"Fixture",path:"/fixture/python"}},
        adapters:{engines:[{id:"kolibri",label:"Kolibri SSD",installed:true}],workSurfaces:[{id:"chat",label:"Chat",installed:true}]}};
      if (endpoint === "/api/models") payload = {models:[model]};
      if (endpoint === "/api/status") payload = launched ? {phase:"running",run,events:[],attachments:[]} : {phase:"idle",events:[]};
      if (endpoint === "/api/chat/history") payload = {threads:[thread],limit:100,version:8};
      if (endpoint === "/api/chat/turn/recover") payload = {recovered:false,discarded:false,threads:[thread]};
      if (endpoint === "/api/chat/history/resume-plan") {
        if (failPlan) return route.fulfill({status:503,json:{ok:false,storageError:true,error:"Generated unreadable history; original file kept."}});
        const request = structuredClone(requestTemplate);
        if (body.systemPrompt) request.chat.systemPrompt = body.systemPrompt;
        payload = {plan:{thread:{id:historyId,title:thread.title},mode:"launch",request,
          ready:Boolean(body.systemPrompt || body.continueWithoutSystemPrompt),requiresSystemPrompt:true,
          requiresMemoryAcknowledgement:true,systemPromptDecision:body.systemPrompt ? "replacement" : "omitted",
          route:{backend:"kolibri",backendLabel:"Kolibri SSD",model:model.name,project:request.project,
            context:8192,output:1024,reasoning:"off",sampling:"custom"},
          admission:{contractId:memoryContract,label:"Review generated capacity",detail:"This acknowledgement matches the exact route.",
            estimate:{estimatedWorkingSetBytes:12_000_000_000}},detail:"Generated read-only saved-route review."}};
      }
      if (endpoint === "/api/session/plan") payload = {sessions:{hub:{phase:launched ? "running" : "idle",attachments:[]},
        operation:{active:false},warmRoute:{canAttach:false},resource:{memoryAvailable:true,totalMemoryBytes:48*1024**3,
          headroomBytes:32*1024**3,headroomPercent:67},admission:{decision:"ready",launchable:true,requiresAcknowledgement:false,
          label:"Ready",contractId:"generated-live-capacity",estimate:{geometryReady:true,estimatedWorkingSetBytes:12_000_000_000}}}};
      if (endpoint === "/api/chat/settings/get") payload = {settings:{chat:requestTemplate.chat}, run};
      if (endpoint === "/api/chat/history/get") payload = {thread};
      if (endpoint === "/api/launch") { launches.push(body); launched = true; payload = {run}; }
      const allowed = new Set(["/api/benchmark/history","/api/session/plan","/api/session/warm-plan","/api/session/attachment-plan",
        "/api/chat/turn/recover","/api/chat/history/resume-plan","/api/chat/history/get","/api/chat/settings/get","/api/launch"]);
      if (req.method() === "POST") assert.ok(allowed.has(endpoint), `Unexpected generated fixture mutation ${endpoint}`);
      return route.fulfill({json:payload});
    });
    try {
      await page.goto(base);
      await page.waitForFunction(() => chatWorkspace.view().historyLoaded && launchWorkspace.view().modelCount === 1);
      await page.evaluate(id => openChatResumeDialog(id),historyId);
      await page.waitForFunction(() => !document.getElementById("chatResumeSystemPrompt").disabled);
      assert.equal(await page.locator("#chatResumeTitle img").count(),0);
      assert.equal(await page.evaluate(() => window.attacked),undefined);
      const text = "Private generated instructions <script>inert</script>";
      await page.locator("#chatResumeSystemPrompt").fill(text);
      await page.locator("#chatResumeContract").evaluate(node => node.open = true);
      await page.locator("#chatResumeSystemPrompt").evaluate(node => { node.focus(); node.setSelectionRange(8,17); });
      const changed = await page.evaluate(() => {
        const field = document.getElementById("chatResumeSystemPrompt"), contract = document.getElementById("chatResumeContract");
        field.dispatchEvent(new Event("input",{bubbles:true}));
        return {same:contract === document.getElementById("chatResumeContract"),open:contract.open,
          focused:document.activeElement === field,start:field.selectionStart,end:field.selectionEnd};
      });
      assert.deepEqual(changed,{same:true,open:true,focused:true,start:8,end:17});
      await page.locator("#chatResumeApply").click();
      await page.waitForFunction(() => !document.getElementById("chatResumeDialog").open);
      assert.equal(launches.length,0,"Apply route only must never dispatch a model load");
      assert.equal(await page.locator("#contextInput").inputValue(),"8192");
      assert.equal(await page.locator("#outputInput").inputValue(),"1024");
      assert.equal(await page.locator("#systemPrompt").inputValue(),text);
      await page.evaluate(id => openChatResumeDialog(id),historyId);
      assert.equal(await page.locator("#chatResumeSystemPrompt").inputValue(),"","private text is not retained across reviews");
      await page.locator("#chatResumeWithoutPrompt").check();
      await page.locator("#chatResumeMemoryConsent").check();
      memoryContract = "capacity-two";
      await page.locator("#chatResumeStart").click();
      await page.waitForFunction(() => document.getElementById("chatResumeStatus").textContent.includes("Review and approve"));
      assert.equal(launches.length,0); assert.equal(await page.locator("#chatResumeMemoryConsent").isChecked(),false);
      await page.setViewportSize({width:390,height:844});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),false);
      const output = path.join(root,"build/browser-qa"); fs.mkdirSync(output,{recursive:true});
      await page.screenshot({path:path.join(output,"chat-resume-mobile.png"),fullPage:true});
      await page.locator("#chatResumeMemoryConsent").check();
      await page.locator("#chatResumeStart").click();
      await page.waitForFunction(() => chatWorkspace.view().activeThreadId === "9d12aa4e-c129-4c53-bad0-0fce34611c6b");
      assert.equal(launches.length,1);
      assert.equal(launches[0].memoryAcknowledgement,"capacity-two");
      assert.equal(launches[0].context,8192); assert.equal(launches[0].output,1024);
      assert.equal(launches[0].options.kv,"off"); assert.equal(launches[0].chat.systemPrompt,undefined);
      await page.evaluate(id => openChatResumeDialog(id),historyId);
      failPlan = true;
      await page.evaluate(id => chatResumeReview.load(id),historyId);
      assert.match(await page.locator("#chatResumeStatus").innerText(),/unreadable history/);
      assert.equal(await page.evaluate(() => chatWorkspace.threads().length),1,"unreadable storage preserves the cached inventory");
      assert.equal(await page.evaluate(() => document.getElementById("chatResumeRoute").querySelector("script")),null);
      assert.deepEqual(errors,[]);
      console.log("Browser resume: exact apply/launch, inert names, private choices, renewed consent, mobile geometry and readable storage errors passed; all API replies generated, no model loaded.");
    } catch (error) {
      console.error("Generated resume fixture state", await page.evaluate(() => {
        let chat = {}; try { chat = chatWorkspace.view(); } catch (_error) {}
        let pending = false; try { pending = chatResumeReview.hasPending(); } catch (_error) {}
        return {phase:launchWorkspace.view().phase,pending,historyBusy:chat.historyBusy,surface:chat.surfaceId,activeThread:chat.activeThreadId,
          notice:document.getElementById("notice").textContent,review:document.getElementById("chatResumeStatus").textContent};
      }));
      console.error("Generated requests", posts.map(item => item.endpoint), "launches", launches.length, "page errors", errors);
      throw error;
    } finally { await browser.close(); }
  })().catch(error => { console.error(error); process.exitCode = 1; });
}
