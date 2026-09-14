"use strict";
// Read-only real-browser regression against a completed local three-engine run.
// Never starts calibration/inference or saves profiles; browser storage is isolated.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const shootoutId = process.env.LLM_LAUNCHER_CROSS_ENGINE_REVIEW_ID;
if (!shootoutId || !process.env.LLM_LAUNCHER_BROWSER_PACKAGE) {
  console.log("Live three-engine saved-result browser check skipped (opt-in).");
} else {
  (async () => {
    const {chromium} = require(process.env.LLM_LAUNCHER_BROWSER_PACKAGE);
    const base = "http://127.0.0.1:18080";
    const browser = await chromium.launch({headless:true});
    const context = await browser.newContext({viewport:{width:1440,height:1080}});
    const page = await context.newPage();
    page.setDefaultTimeout(60_000);
    const errors = [], blocked = [], applies = [];
    const allowed = new Set(["/api/calibration/plan", "/api/optimal", "/api/optimal-engine",
      "/api/session/plan", "/api/session/warm-plan", "/api/session/attachment-plan",
      "/api/preview", "/api/benchmark/history"]);
    page.on("pageerror", error => errors.push(error.message));
    await context.route("**/*", async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin === base && url.pathname === "/api/chat/turn/recover") {
        return route.fulfill({json:{recovered:false,discarded:false,threads:[]}});
      }
      if (url.origin !== base || (request.method() !== "GET"
          && !(request.method() === "POST" && allowed.has(url.pathname)))) {
        blocked.push(`${request.method()} ${url.pathname}`);
        return route.abort("blockedbyclient");
      }
      return route.continue();
    });
    const output = path.resolve(__dirname, "../build/browser-qa");
    fs.mkdirSync(output,{recursive:true});
    try {
      const status = await (await context.request.get(base+"/api/status")).json();
      assert.equal(status.phase,"idle","Wait for every model route to unload");
      const job = await (await context.request.get(base+"/api/benchmark/status")).json();
      assert.ok(["idle","completed"].includes(job.phase),"Do not review a running/failed calibration as complete");
      const {models} = await (await context.request.get(base+"/api/models")).json();
      const model = models.find(m => Object.values(m.backends || {}).some(c =>
        (c.localBenchmarks || []).some(r=>r.shootoutId===shootoutId)));
      assert.ok(model,"The result must exist in the real saved catalog");
      const records = ["omlx","lmstudio","mtplx"].map(backend => {
        const record = model.backends[backend].localBenchmarks.find(r=>r.shootoutId===shootoutId);
        assert.ok(record,`${backend} needs a completed saved record`);
        assert.equal(record.probeContract.version,"fixed-greedy-wire-v1");
        return record;
      });
      const reference = records.find(r=>r.backend==="mtplx");
      const expectedRecordIds = Object.fromEntries(records.map(r=>[r.backend,r.id]));
      assert.equal(reference.client,"chat");
      assert.equal(reference.selectionPreference,"throughput");
      await page.goto(base);
      await page.locator('#modelSelect option[value]').first().waitFor({state:"attached"});
      await page.locator('[data-client="chat"]').click();
      await page.locator('#backendChoices [data-backend="mtplx"]').click();
      await page.locator("#modelSelect").selectOption(model.id);
      for (const [id,value] of [["contextInput",reference.contextMin],["outputInput",reference.outputMax]]) {
        await page.locator('#'+id).fill(String(value));
        await page.locator('#'+id).press("Tab");
      }
      await page.locator("#reasoningSelect").selectOption(reference.reasoning);
      if (!await page.locator("#advancedControls").evaluate(n=>n.open)) {
        await page.locator("#advancedControls > summary").click();
      }
      await page.locator("#profileSelect").selectOption(reference.engineSettings.profile);
      await page.locator("#fanSelect").selectOption(reference.engineSettings.fan);
      await page.locator("#mtplxKv").selectOption(reference.targetKV);

      const openResult = async () => {
        await page.locator("#hubToolsMenuButton").click();
        await page.locator("#openCalibrationAssistant").click();
        await page.locator("#calibrationSuiteSelect").selectOption("agentic");
        await page.locator("#calibrationPreferenceSelect").selectOption("throughput");
        await page.waitForFunction(()=>!document.getElementById("calibrationApplyButton").disabled);
        assert.equal(await page.locator("#calibrationPercent").innerText(),"100%");
        const cards=page.locator("#calibrationResults > article");
        assert.equal(await cards.count(),3,"All three engine results are shown");
        assert.match(await page.locator("#calibrationStartButton").innerText(),/Retest|Test again/i);
      };
      const checkedResponse = async response => {
        assert.equal(response.status(),200,JSON.stringify(await response.json()));
        const body=response.request().postDataJSON();
        assert.equal(body.evidenceBinding?.shootoutId,shootoutId);
        assert.deepEqual(body.evidenceBinding.recordIds,expectedRecordIds);
        const result=(await response.json()).optimization;
        assert.ok(result && result.engineNextAction?.requiresCalibration===false);
        applies.push(result.backend);
        return result;
      };
      const applyResult = async () => {
        const pending=page.waitForResponse(r=>r.url()===base+"/api/optimal-engine" && r.request().method()==="POST");
        await page.locator("#calibrationApplyButton").click();
        const result=await checkedResponse(await pending);
        await page.waitForFunction(()=>!document.getElementById("calibrationDialog").open);
        assert.equal(await page.locator(`[data-backend="${result.backend}"]`).first().getAttribute("aria-pressed"),"true");
        return result;
      };
      await openResult();
      await page.screenshot({path:path.join(output,"three-engine-results.png")});
      const chosen=await applyResult();
      await page.reload();
      await page.locator(`#modelSelect option[value="${model.id}"]`).waitFor({state:"attached"});
      assert.equal(await page.locator("#modelSelect").inputValue(),model.id);
      assert.equal(await page.locator("#contextInput").inputValue(),String(reference.contextMin));
      await openResult();
      assert.equal((await applyResult()).backend,chosen.backend);
      // The exact saved engine shortcut must apply the same matrix, not reopen calibration.
      await page.waitForFunction(()=>document.getElementById("performanceReceipt").dataset.action==="apply-engine"
        && !document.getElementById("performanceReceipt").disabled);
      const pending=page.waitForResponse(r=>r.url()===base+"/api/optimal-engine" && r.request().method()==="POST");
      await page.locator("#performanceReceipt").click();
      await checkedResponse(await pending);
      assert.equal(await page.locator("#calibrationDialog").evaluate(n=>n.open),false);
      assert.equal(applies.length,3);
      assert.deepEqual(errors,[]);
      assert.deepEqual(blocked,[],"No launch, replacement test or profile mutation is permitted");
      console.log(`Saved three-engine comparison ${shootoutId}: results, Apply/reload/Apply and saved-settings shortcut passed without retesting.`);
    } catch (error) {
      await page.screenshot({path:path.join(output,"three-engine-apply-failure.png")});
      console.error(JSON.stringify({errors,blocked}));
      throw error;
    } finally {
      await context.close();
      await browser.close();
    }
  })().catch(error=>{console.error(error);process.exitCode=1;});
}
