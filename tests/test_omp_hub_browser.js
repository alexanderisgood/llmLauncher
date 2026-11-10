"use strict";
// Real verified OMP and production Hub/RunManager; disposable local SSE only.
const assert = require("node:assert/strict");
const {spawn} = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");
if (process.env.LLM_LAUNCHER_OMP_HUB_BROWSER !== "1" || !process.env.LLM_LAUNCHER_BROWSER_PACKAGE) {
  console.log("Verified OMP Hub browser check skipped (opt-in).");
} else {
  (async () => {
    const {chromium} = require(process.env.LLM_LAUNCHER_BROWSER_PACKAGE);
    const child = spawn(process.env.LLM_LAUNCHER_TEST_PYTHON || "/opt/homebrew/bin/python3",
      [path.join(__dirname,"fixtures/omp_hub_browser_server.py")], {
        cwd:path.resolve(__dirname,".."), env:{PATH:process.env.PATH,
          LLM_LAUNCHER_OMP_HUB_BROWSER:"1", LLM_LAUNCHER_OMP_BINARY:process.env.LLM_LAUNCHER_OMP_BINARY},
        stdio:["ignore","pipe","pipe"],
      });
    let diagnostics="", browser, page, context, base;const errors=[];
    child.stderr.on("data",data=>{diagnostics=(diagnostics+data).slice(-8000);});
    const exited=new Promise(resolve=>child.once("exit",(code,signal)=>resolve({code,signal})));
    try {
      base=await new Promise((resolve,reject)=>{
        let text="";
        const timer=setTimeout(()=>reject(new Error("Fixture startup timed out: "+diagnostics)),30_000);
        child.once("exit",()=>{clearTimeout(timer);reject(new Error("Fixture exited: "+diagnostics));});
        child.stdout.on("data",data=>{
          text+=data;
          if(text.includes("\n")) {
            clearTimeout(timer);
            try {resolve(JSON.parse(text.split("\n")[0]).base);} catch(error){reject(error);}
          }
        });
      });
      browser=await chromium.launch({headless:true});
      context=await browser.newContext({viewport:{width:1440,height:1000}});
      await context.route("**/*",route=>new URL(route.request().url()).origin===base
        ?route.continue():route.abort("blockedbyclient"));
      page=await context.newPage(); page.setDefaultTimeout(20_000);
      page.on("pageerror",error=>errors.push(error.message));
      await page.goto(base);
      await page.locator("#agentConsoleInput").waitFor({state:"visible"});
      await page.waitForFunction(()=>!document.getElementById("agentConsoleInput").disabled);
      const status=async()=> (await context.request.get(base+"/fixture/status")).json();
      const native=(await status()).console;
      assert.equal(native.protocol,"omp-rpc"); assert.equal(native.timelineVersion,1);
      assert.equal(native.canInput,true); assert.equal(native.supportsQueue,true);
      assert.ok(native.commands.some(command=>command.name==="stats"),"Native readonly slash commands are available");
      const send=async text=>{
        await page.locator("#agentConsoleInput").fill(text);
        await page.locator("#agentConsoleEnterButton").click();
      };
      const answer=text=>page.locator(".agent-pi-event-answer").filter({hasText:text});
      const idle=()=>page.waitForFunction(()=>
        document.getElementById("agentPiTimelineViewport").getAttribute("aria-busy")==="false"
        &&document.getElementById("agentConsoleEnterButton").innerText==="Send");
      await send("first"); await answer("Final answer for first.").waitFor(); await idle();
      assert.match(await answer("Final answer for first.").innerText(),/oh-my-pi/);
      assert.ok(await page.locator(".agent-pi-event-thinking").count()>0);
      assert.equal(await page.locator("#agentPiTimeline script").count(),0,"Generated model text stays inert");
      await send("queue-hold");
      await page.locator(".agent-pi-event-thinking").filter({hasText:"Generated OMP reasoning for queue-hold."}).waitFor();
      await send("queued-follow-up");
      await page.locator("#agentConsoleQueueMessages pre").filter({hasText:"queued-follow-up"}).waitFor();
      const token=(await (await context.request.get(base+"/api/bootstrap")).json()).token;
      assert.equal((await context.request.post(base+"/fixture/release",{headers:{"X-Launcher-Token":token}})).status(),200);
      await answer("Final answer for queued-follow-up.").waitFor(); await idle();
      assert.equal((await status()).console.pendingMessages,0,"A successful settled turn advances its exact queued follow-up");
      await send("hold");
      await page.waitForFunction(()=>document.getElementById("agentPiTimelineViewport").getAttribute("aria-busy")==="true");
      await page.locator(".agent-pi-event-thinking").filter({hasText:"Generated OMP reasoning for hold."}).waitFor();
      await send("must-not-run");
      await page.locator("#agentConsoleQueueMessages pre").filter({hasText:"must-not-run"}).waitFor();
      await page.locator("#agentConsoleInterruptButton").click(); await idle();
      assert.equal((await status()).console.queuePaused,true);
      assert.equal(await page.locator("#agentConsoleQueueMessages pre").innerText(),"must-not-run");
      assert.match(await page.locator("#agentConsoleQueueSummary").innerText(),/paused/);
      assert.doesNotMatch(await page.locator("#agentPiTimeline").innerText(),/finished its reasoning without a final response/);
      // Discard only the explicitly paused test message. Stop itself must retain it.
      await page.locator("#agentConsoleActionsMenu > summary").click();
      await page.locator("#agentConsoleEscapeButton").click();
      await send("after-stop"); await answer("Final answer for after-stop.").waitFor(); await idle();
      const beforeSlash=(await status()).requests.length;
      await send("/stats");
      await page.locator(".agent-pi-event-notice").filter({hasText:/Command output/}).first().waitFor();
      await idle();
      const observed=await status();
      assert.equal(observed.requests.length,beforeSlash,"A native readonly local slash never calls the model");
      assert.deepEqual(observed.requests,["first","queue-hold","queued-follow-up","hold","after-stop"]);
      assert.ok(observed.contracts.every(contract=>contract.model==="hub-fixture"&&contract.output===1024),
        "All native turns retain the selected provider model and output limit");
      assert.ok(observed.contracts.slice(1).every(contract=>contract.reasoningReplay
        &&contract.roles.includes("assistant")),"Follow-up turns carry actual assistant history and reasoning");
      assert.equal(observed.console.canInput,true);
      assert.doesNotMatch(await page.locator("#agentPiTimeline").innerText(),/finished its reasoning without a final response/);
      // Real composer persistence uses OMP's namespace even for the same
      // conversation hash as a preexisting Pi draft.
      const piKey="pi:"+observed.console.conversationId;
      await page.evaluate(key=>{
        const storageKey="llm-launcher-agent-console-drafts-v1";
        const envelope=JSON.parse(sessionStorage.getItem(storageKey)||'{"version":1,"drafts":{}}');
        envelope.drafts[key]={text:"Separate Pi draft",updatedAt:1};
        sessionStorage.setItem(storageKey,JSON.stringify(envelope));
      },piKey);
      await page.reload(); await page.locator("#agentConsoleInput").waitFor({state:"visible"});
      await page.locator("#agentConsoleInput").fill("OMP draft <literal>");
      await page.reload(); await page.locator("#agentConsoleInput").waitFor({state:"visible"});
      assert.equal(await page.locator("#agentConsoleInput").inputValue(),"OMP draft <literal>");
      const saved=await page.evaluate(()=>JSON.parse(sessionStorage.getItem("llm-launcher-agent-console-drafts-v1")));
      assert.equal(saved.drafts[piKey].text,"Separate Pi draft");
      assert.equal(saved.drafts["omp:"+observed.console.conversationId].text,"OMP draft <literal>");
      const viewport=page.locator("#agentPiTimelineViewport");
      await page.setViewportSize({width:390,height:844});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      assert.ok(await viewport.evaluate(node=>node.clientHeight)>600);
      assert.ok(await page.locator("#agentConsoleStatusModel").isVisible());
      const mobileHeader=await page.evaluate(()=>{
        const box=id=>document.getElementById(id).getBoundingClientRect().toJSON();
        return {model:box("agentConsoleStatusModel"),fans:box("hubFanMode"),home:box("agentConsoleBackButton"),
          actions:document.querySelector("#agentConsoleActionsMenu > summary").getBoundingClientRect().toJSON()};
      });
      assert.ok(mobileHeader.model.width>100,"The selected model has readable width on mobile");
      assert.ok(mobileHeader.fans.top>=mobileHeader.model.bottom,"Cooling controls never overlap the selected model");
      assert.ok(mobileHeader.home.left>=mobileHeader.model.right&&mobileHeader.actions.left>=mobileHeader.home.right,
        "Mobile identity and the Home/action controls occupy separate areas");
      const output=path.resolve(__dirname,"../build/browser-qa"); fs.mkdirSync(output,{recursive:true});
      await page.screenshot({path:path.join(output,"omp-hub-mobile.png")});
      await page.setViewportSize({width:1440,height:1000});
      await page.screenshot({path:path.join(output,"omp-hub-desktop.png")});
      await page.locator("#agentConsoleActionsMenu > summary").click();
      await page.locator("#agentConsoleStopButton").click();
      await page.waitForFunction(()=>document.getElementById("agentConsoleInput").disabled);
      await answer("Final answer for after-stop.").waitFor();
      let stopped;
      const exitDeadline=Date.now()+10_000;
      do {
        stopped=await status();
        if(!stopped.ompRunning) break;
        await new Promise(resolve=>setTimeout(resolve,100));
      } while(Date.now()<exitDeadline);
      assert.equal(stopped.ompRunning,false,"Only the owned agent is stopped");
      assert.deepEqual(errors,[]);
      fs.writeFileSync(path.join(output,"omp-hub-proof.json"),JSON.stringify({
        protocol:native.protocol,timelineVersion:native.timelineVersion,requests:observed.requests,
        providerContracts:observed.contracts,localSlashWithoutModel:true,queuedFollowUpDelivered:true,
        stopPreservedQueue:true,draftIsolation:true,mobileNoOverflow:true,
        nativeStateQualified:native.canInput,stopped:true,
      },null,2)+"\n");
      for(const name of ["omp-hub-failure.json","omp-hub-failure.png"]) {
        const stale=path.join(output,name); if(fs.existsSync(stale)) fs.unlinkSync(stale);
      }
      console.log("Real OMP Hub: qualified RPC, reasoning, queue/Stop recovery, local /stats, inert text, isolated drafts and mobile layout passed. No model loaded.");
    } catch(error) {
      if(page&&context&&base) {
        const output=path.resolve(__dirname,"../build/browser-qa"); fs.mkdirSync(output,{recursive:true});
        const fixture=await (await context.request.get(base+"/fixture/status")).json();
        const text=await page.locator("#agentWorkspace").innerText();
        const visibility=await page.evaluate(()=>{let consoleVisible=null,visibilityError="";try{consoleVisible=agentConsoleIsVisible();}catch(error){visibilityError=error.message;}return{run:launchWorkspace.runState(),consoleVisible,visibilityError,classes:document.getElementById("agentWorkspace").className};});
        fs.writeFileSync(path.join(output,"omp-hub-failure.json"),JSON.stringify({fixture,text,errors,diagnostics,visibility,body:await page.locator("body").innerText()},null,2)+"\n");
        await page.screenshot({path:path.join(output,"omp-hub-failure.png")});
      }
      throw error;
    } finally {
      if(browser) await browser.close(); child.kill("SIGTERM");
      const result=await Promise.race([exited,new Promise(resolve=>{
        const timer=setTimeout(()=>resolve(null),10_000);timer.unref();
      })]);
      assert.ok(result,"Fixture cleanup did not finish; inspect its owned process before retrying");
      assert.equal(result.code,0,diagnostics);
    }
  })().catch(error=>{console.error(error);process.exitCode=1;});
}
