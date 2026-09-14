"use strict";
// Isolated real-UI check; never loads a model or changes server-side profiles.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
if (!process.env.LLM_LAUNCHER_MTPLX_APPLY_LIVE || !process.env.LLM_LAUNCHER_BROWSER_PACKAGE) {
  console.log("Live MTPLX saved-result browser check skipped (opt-in).");
} else {
  const {chromium} = require(process.env.LLM_LAUNCHER_BROWSER_PACKAGE);
  (async () => {
    const base = "http://127.0.0.1:18080";
    const browser = await chromium.launch({headless:true});
    const context = await browser.newContext({viewport:{width:1440,height:1080}});
    const page = await context.newPage();
    page.setDefaultTimeout(60_000);
    const errors = [], blocked = [], applied = [];
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
    fs.mkdirSync(output, {recursive:true});
    try {
      assert.equal((await (await context.request.get(base+"/api/status")).json()).phase, "idle");
      const benchmark = await (await context.request.get(base+"/api/benchmark/status")).json();
      const historyId = process.env.LLM_LAUNCHER_MTPLX_REVIEW_RECORD_ID;
      let result = benchmark.result;
      if (historyId) {
        assert.equal(benchmark.phase, "idle", "Restarted-controller proof requires no in-memory completed job");
        const catalog = await (await context.request.get(base+"/api/models")).json();
        result = catalog.models.flatMap(model => model.backends?.mtplx?.localBenchmarks || [])
          .find(record => record.id === historyId);
        assert.ok(result, "The saved record must come from the real local catalog");
      } else {
        assert.equal(benchmark.phase, "completed", "Wait for the entire comparison before checking Apply");
      }
      assert.equal(result.backend, "mtplx");
      assert.equal(result.mtplxOperatorSweep.version, 5);
      await page.goto(base);
      await page.locator('#modelSelect option[value]').first().waitFor({state:"attached"});
      await page.locator('[data-client="chat"]').click();
      await page.locator('#backendChoices [data-backend="mtplx"]').click();
      await page.locator("#modelSelect").selectOption(result.modelId);
      await page.locator("#contextInput").fill(String(result.contextMin));
      await page.locator("#contextInput").press("Tab");
      await page.locator("#outputInput").fill(String(result.outputMax));
      await page.locator("#outputInput").press("Tab");
      await page.locator("#reasoningSelect").selectOption(result.reasoning);
      if (!await page.locator("#advancedControls").evaluate(node => node.open)) {
        await page.locator("#advancedControls > summary").click();
      }
      await page.locator("#profileSelect").selectOption("turbo");
      await page.locator("#fanSelect").selectOption("default");
      await page.locator("#mtplxKv").selectOption("off");
      const openResults = async () => {
        if (await page.locator("#interfaceDetailButton").getAttribute("aria-pressed") !== "true") {
          await page.locator("#interfaceDetailButton").click();
        }
        await page.locator("#openBenchmarkButton").click();
        if (historyId) {
          await page.locator("#benchmarkSuiteSelect").selectOption("agentic");
          await page.locator("#benchmarkPreferenceSelect").selectOption("throughput");
          if (!await page.locator("#benchmarkHistoryPanel").evaluate(node => node.open)) {
            await page.locator("#benchmarkHistoryPanel > summary").click();
          }
          const history = page.locator("#benchmarkHistoryRuns");
          await history.locator(`[data-review-benchmark="${historyId}"]`).click();
          await page.waitForFunction(() => document.getElementById("benchmarkPhase").textContent === "Saved result"
            && !document.getElementById("benchmarkHistoryPanel").open);
          assert.equal(await page.locator("#benchmarkHistoryPanel").evaluate(node => node.open),false,
            "Viewing a result should focus its cards rather than leave history covering Apply");
        }
        await page.locator("[data-apply-benchmark-route]").waitFor();
        assert.equal(await page.locator("#benchmarkPercent").innerText(), "100%");
      };
      const applyResult = async () => {
        const responsePromise = page.waitForResponse(response =>
          response.url() === base+"/api/optimal" && response.request().method() === "POST");
        await page.locator("[data-apply-benchmark-route]").click();
        const response = await responsePromise;
        const payload = response.request().postDataJSON();
        assert.equal(payload.evidenceBinding.recordId, result.id);
        assert.equal(response.status(), 200, JSON.stringify(await response.json()));
        applied.push(payload.evidenceBinding.recordId);
        await page.waitForFunction(() => !document.getElementById("benchmarkDialog").open);
        assert.equal(await page.locator("#calibrationDialog").evaluate(node => node.open), false);
        assert.equal(await page.locator("#accelerationSelect").inputValue(), result.winner === "ar" ? "off" : "mtp");
        assert.equal(await page.locator("#mtplxOperatorRouteSelect").inputValue(), result.settings.mtplxOperatorRoute || "default");
      };
      await openResults();
      if (result.winner === "ar" && result.modes.mtp?.qualityMatchesAR === false) {
        assert.match(await page.locator("#benchmarkStatus").innerText(), /output did not exactly match/);
      }
      await page.screenshot({path:path.join(output,"mtplx-completed-results.png"),fullPage:true});
      await applyResult();
      await page.reload();
      await page.locator(`#modelSelect option[value="${result.modelId}"]`).waitFor({state:"attached"});
      assert.equal(await page.locator("#modelSelect").inputValue(), result.modelId);
      assert.equal(await page.locator("#contextInput").inputValue(), String(result.contextMin));
      await openResults();
      await applyResult();
      await page.screenshot({path:path.join(output,"mtplx-applied-reloaded.png"),fullPage:true});
      assert.deepEqual(applied, [result.id,result.id]);
      if (historyId) {
        await page.waitForFunction(() => {
          const button = document.getElementById("performanceReceipt");
          return !button.disabled && button.dataset.action === "apply-route";
        });
        const responsePromise = page.waitForResponse(response =>
          response.url() === base+"/api/optimal" && response.request().method() === "POST");
        await page.locator("#performanceReceipt").click();
        const response = await responsePromise;
        assert.equal(response.status(),200,JSON.stringify(await response.json()));
        assert.equal(response.request().postDataJSON().evidenceBinding.recordId,result.id);
        assert.equal(await page.locator("#calibrationDialog").evaluate(node => node.open),false);
        assert.equal(await page.locator("#benchmarkDialog").evaluate(node => node.open),false);
      }
      for (const theme of ["daylight", "frost"]) {
        await page.locator("#themeMenuButton").click();
        await page.locator(`[data-theme-choice="${theme}"]`).click();
        await openResults();
        const layout = await page.locator("#benchmarkResults > article").evaluateAll(nodes =>
          nodes.map(node => {const r = node.getBoundingClientRect(); return {top:r.top, height:r.height};}));
        assert.equal(layout.length, 3);
        for (const row of layout) {
          assert.ok(Math.abs(row.top - layout[0].top) <= 1, `${theme}: result cards must align`);
          assert.ok(Math.abs(row.height - layout[0].height) <= 1, `${theme}: result cards must share height`);
        }
        const bounds = await page.locator("#benchmarkDialog").boundingBox();
        assert.ok(Math.abs(bounds.x + bounds.width / 2 - 720) <= 1, `${theme}: dialog stays centred`);
        await page.screenshot({path:path.join(output,`mtplx-results-${theme}.png`),fullPage:true});
        await page.keyboard.press("Escape");
        assert.equal(await page.locator("#benchmarkDialog").evaluate(node => node.open), false);
      }
      assert.deepEqual(errors, []);
      assert.deepEqual(blocked, [], "No new benchmark, launch, or profile mutation is allowed");
      assert.equal((await (await context.request.get(base+"/api/status")).json()).phase, "idle");
      console.log(`Real MTPLX result ${result.id}: ${historyId ? "review after controller restart and main-screen saved-settings shortcut, " : ""}Apply, reload, and Apply again passed without retesting or loading a model.`);
    } catch (error) {
      await page.screenshot({path:path.join(output,"mtplx-apply-failure.png"),fullPage:true});
      console.error(JSON.stringify({errors,blocked}));
      throw error;
    } finally {
      await context.close();
      await browser.close();
    }
  })().catch(error => {console.error(error); process.exitCode = 1;});
}
