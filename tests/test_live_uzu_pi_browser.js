"use strict";

// Read-only real-browser admission check. The separate Python live test owns
// model inference; this harness cannot launch a model or modify saved profiles.
const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs");
if (process.env.LLM_LAUNCHER_UZU_PI_BROWSER !== "1") {
  console.log("Live Uzu Pi browser admission check skipped (opt-in).");
} else {
  const {chromium} = require(process.env.LLM_LAUNCHER_BROWSER_PACKAGE);
  const base = "http://127.0.0.1:18080";
  const reads = new Set(["/api/calibration/plan", "/api/optimal", "/api/optimal-engine",
    "/api/session/plan", "/api/preview", "/api/session/warm-plan", "/api/session/attachment-plan",
    "/api/benchmark/history"]);
  (async () => {
    const browser = await chromium.launch({headless:true});
    const context = await browser.newContext({viewport:{width:1440,height:1080}});
    const page = await context.newPage();
    const blocked = [], errors = [], admissions = [];
    page.on("pageerror", e => errors.push(e.message));
    page.on("response", async response => {
      if (new URL(response.url()).pathname === "/api/session/plan" && response.ok()) {
        try { admissions.push((await response.json()).sessions); } catch {}
      }
    });
    await context.route("**/*", async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin === base && url.pathname === "/api/chat/turn/recover") {
        return route.fulfill({status:200,contentType:"application/json",body:"{\"turns\":[]}"});
      }
      if (url.origin !== base || (request.method() !== "GET" && !reads.has(url.pathname))) {
        blocked.push(`${request.method()} ${url.pathname}`);
        return route.abort();
      }
      return route.continue();
    });
    try {
      assert.equal((await (await context.request.get(`${base}/api/status`)).json()).phase, "idle");
      await page.goto(base);
      await page.locator('#backendChoices [data-backend="uzu"]').click();
      await page.locator("#modelSelect").selectOption("uzu-58a4a2b149eddad1e821e795");
      await page.locator('[data-client="pi"]').click();
      await page.locator("#agentHostSelect").selectOption("console");
      await page.locator("#contextInput").fill("65536");
      await page.locator("#contextInput").press("Tab");
      await page.locator("#outputInput").fill("16384");
      await page.locator("#outputInput").press("Tab");
      await page.locator("#reasoningSelect").selectOption("auto");
      await page.waitForFunction(() => !document.getElementById("launchButton").disabled);
      assert.ok(admissions.some(p => p.admission?.request?.client === "pi" && p.admission.launchable),
        "Launch must have actual Pi capacity admission, not a stale Chat result");
      await page.reload();
      await page.waitForFunction(() => !document.getElementById("launchButton").disabled
        && document.getElementById("contextInput").value === "65536");
      assert.equal(await page.locator("#agentHostSelect").inputValue(), "console");
      assert.equal(await page.locator("#reasoningSelect").inputValue(), "auto");
      await page.waitForFunction(() => document.getElementById("performanceReceipt").dataset.action === "review-capacity");
      assert.doesNotMatch(await page.locator("#compatibilityLine").innerText(), /Chat only/);
      await page.locator("#optimizerMenuButton").click();
      const optimizationResponse = page.waitForResponse(r => new URL(r.url()).pathname === "/api/optimal-engine");
      await page.locator('[data-optimizer-scope="engine"][data-engine-preference="throughput"]').click();
      const optimization = (await (await optimizationResponse).json()).optimization;
      assert.equal(optimization.engineNextAction.id, "keep-current");
      assert.equal(optimization.engineEvidenceTier, "local-capacity-only");
      await page.waitForFunction(() => document.getElementById("optimizationPanel").getAttribute("aria-busy") === "false");
      assert.equal(await page.locator("#calibrationDialog").evaluate(d => d.open), false,
        "Keeping a qualified Pi route must not reopen a Chat-only test");
      await page.locator("#hubToolsMenuButton").click();
      const calibrationResponse = page.waitForResponse(r => new URL(r.url()).pathname === "/api/calibration/plan");
      await page.locator("#openCalibrationAssistant").click();
      const calibration = (await (await calibrationResponse).json()).plan;
      assert.equal(calibration.action, "blocked");
      assert.match(calibration.blockers.join(" "), /Pi speed testing is not yet available/);
      assert.equal(await page.locator("#calibrationStartButton").isDisabled(), true);
      await page.getByRole("button", {name:"Close Calibration Assistant",exact:true}).click();
      await page.waitForFunction(() => document.getElementById("performanceReceipt").dataset.action === "review-capacity"
        && !document.getElementById("launchButton").disabled);
      const output = path.resolve(__dirname, "../build/browser-qa");
      fs.mkdirSync(output, {recursive:true});
      await page.screenshot({path:path.join(output,"uzu-pi-primary-ready.png"),fullPage:true});
      assert.deepEqual(errors, []);
      assert.deepEqual(blocked, []);
      assert.equal((await (await context.request.get(`${base}/api/status`)).json()).phase, "idle");
      console.log("Real browser: Uzu Pi admission, reload and keep-current work without a repeat test; unsupported Pi speed calibration cannot run. No model launched.");
    } finally { await browser.close(); }
  })().catch(e => { console.error(e); process.exitCode=1; });
}
