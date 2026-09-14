"use strict";

// Opt-in, isolated browser check of the real local app. Model inference requires
// a separate explicit flag; neither mode changes profiles or installed runtimes.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

if (!process.env.LLM_LAUNCHER_BROWSER_PACKAGE) {
  console.log("Live launcher browser check skipped (opt-in).");
} else {
  const {chromium} = require(process.env.LLM_LAUNCHER_BROWSER_PACKAGE);
  const base = "http://127.0.0.1:18080";
  const output = path.resolve(__dirname, "../build/browser-qa");
  const modelId = "uzu-58a4a2b149eddad1e821e795";
  const liveChat = process.env.LLM_LAUNCHER_UZU_CHAT_LIVE === "1";
  const readOnlyPosts = new Set([
    "/api/calibration/plan", "/api/optimal", "/api/optimal-engine",
    "/api/session/plan", "/api/preview",
    "/api/session/warm-plan", "/api/session/attachment-plan",
    "/api/benchmark/history",
  ]);
  const chatPosts = new Set([
    "/api/launch", "/api/chat", "/api/chat/stop", "/api/stop",
    "/api/chat/settings/get", "/api/chat/history/get", "/api/chat/history/save",
    "/api/chat/turn/checkpoint", "/api/chat/turn/clear",
  ]);
  (async () => {
    const browser = await chromium.launch({headless:true});
    const context = await browser.newContext({viewport:{width:1440, height:1080}});
    const page = await context.newPage();
    page.setDefaultTimeout(120_000);
    const errors = [];
    const blocked = [];
    const applied = [];
    const existingHistoryIds = new Set();
    page.on("pageerror", error => errors.push(error.message));
    page.on("response", response => {
      if (new URL(response.url()).pathname === "/api/optimal") applied.push(response.status());
    });
    await context.route("**/*", async route => {
      const request = route.request();
      const url = new URL(request.url());
      if (url.origin === base && url.pathname === "/api/chat/turn/recover") {
        // This brand-new isolated tab has no interrupted chat. Do not let a
        // journal-recovery endpoint mutate the user's saved chat history.
        return route.fulfill({json:{recovered:false, discarded:false, threads:[]}});
      }
      if (url.origin !== base || (request.method() !== "GET" && !(
        request.method() === "POST" && (readOnlyPosts.has(url.pathname)
          || (liveChat && chatPosts.has(url.pathname)))
      ))) {
        blocked.push(`${request.method()} ${url.pathname}`);
        return route.abort("blockedbyclient");
      }
      if (request.method() === "POST" && url.pathname === "/api/launch") {
        const body = request.postDataJSON();
        assert.ok(liveChat && body.backend === "uzu" && body.client === "chat"
          && body.modelId === modelId && body.context === 131072,
        "The live browser may launch only the exact qualified Uzu 128K Chat route");
      }
      if (request.method() === "POST" && ["/api/chat/history/save", "/api/chat/turn/checkpoint"].includes(url.pathname)) {
        const body = request.postDataJSON();
        assert.ok(!existingHistoryIds.has(body.id) && !existingHistoryIds.has(body.historyId),
          "The browser test must never overwrite an existing conversation");
      }
      return route.continue();
    });
    fs.mkdirSync(output, {recursive:true});
    try {
      const initial = await (await context.request.get(`${base}/api/status`)).json();
      assert.equal(initial.phase, "idle", "Run this check only while the launcher is idle");
      if (liveChat) {
        const history = await (await context.request.get(`${base}/api/chat/history`)).json();
        for (const thread of history.threads || []) existingHistoryIds.add(thread.id);
      }
      await page.goto(base);
      await page.locator('#modelSelect option[value]').first().waitFor({state:"attached"});
      await page.locator('[data-client="chat"]').click();
      await page.locator('#backendChoices [data-backend="uzu"]').click();
      await page.locator(`#modelSelect option[value="${modelId}"]`).waitFor({state:"attached"});
      await page.locator("#modelSelect").selectOption(modelId);
      await page.locator("#contextInput").fill("131072");
      await page.locator("#contextInput").press("Tab");
      await page.locator("#outputInput").fill("16384");
      await page.locator("#outputInput").press("Tab");
      await page.locator("#reasoningSelect").selectOption("auto");
      await page.locator("#hubToolsMenuButton").click();
      await page.locator("#themeMenuButton").click();
      await page.locator('[data-theme-choice="frost"]').click();
      const openCalibration = async () => {
        await page.locator("#hubToolsMenuButton").click();
        await page.locator("#openCalibrationAssistant").click();
        await page.waitForFunction(() => {
          const button = document.getElementById("calibrationApplyButton");
          return document.getElementById("calibrationDialog").open && !button.disabled;
        });
        const progress = await page.locator("#calibrationProgressBar").evaluate(bar => ({
          filled:bar.getBoundingClientRect().width,
          total:bar.parentElement.getBoundingClientRect().width,
        }));
        assert.ok(progress.filled >= progress.total - 2, "Saved progress is visibly full, not animating from zero");
      };
      await openCalibration();
      await page.screenshot({path:path.join(output, "uzu-128k-calibration-frost.png")});
      const result = await page.locator("#calibrationDialog").innerText();
      assert.match(result, /128K|131,072/);
      assert.match(result, /38 GiB/);
      assert.equal(await page.locator("#calibrationPercent").innerText(), "100%");
      const geometry = await page.locator("#calibrationDialog").evaluate(dialog => {
        const box = dialog.getBoundingClientRect();
        const actions = [...dialog.querySelectorAll(".calibration-actions > button")]
          .map(button => button.getBoundingClientRect()).map(r => ({top:r.top, height:r.height}));
        return {center:box.x + box.width / 2, viewport:innerWidth, actions};
      });
      assert.ok(Math.abs(geometry.center - geometry.viewport / 2) <= 1, "Dialog stays centered");
      assert.ok(Math.max(...geometry.actions.map(r => r.top)) - Math.min(...geometry.actions.map(r => r.top)) <= 1, "Action buttons align horizontally");
      assert.ok(Math.max(...geometry.actions.map(r => r.height)) - Math.min(...geometry.actions.map(r => r.height)) <= 1, "Action buttons have equal heights");
      await page.locator("#calibrationApplyButton").click();
      await page.waitForFunction(() => !document.getElementById("calibrationDialog").open);
      assert.ok(applied.includes(200), "Apply must reach the real optimizer successfully");
      await openCalibration();
      assert.match(await page.locator("#calibrationStartButton").innerText(), /Retest|Requalify/i);
      await page.getByRole("button", {name:"Close Calibration Assistant", exact:true}).click();
      await page.waitForFunction(() => !document.getElementById("launchButton").disabled);
      await page.screenshot({path:path.join(output, "uzu-128k-applied-frost.png"), fullPage:true});
      await page.reload();
      await page.waitForFunction(() =>
        document.querySelector('#backendChoices [data-backend="uzu"]').getAttribute("aria-pressed") === "true"
        && document.getElementById("contextInput").value === "131072"
        && !document.getElementById("launchButton").disabled
      );
      await openCalibration();
      assert.equal(await page.locator("#calibrationPercent").innerText(), "100%");
      await page.getByRole("button", {name:"Close Calibration Assistant", exact:true}).click();
      for (const [theme, width] of [["frost", 1920], ["daylight", 960]]) {
        await page.setViewportSize({width, height:1080});
        await page.locator("#hubToolsMenuButton").click();
        await page.locator("#themeMenuButton").click();
        await page.locator(`[data-theme-choice="${theme}"]`).click();
        const workspace = await page.locator(".app-workspace").boundingBox();
        assert.ok(Math.abs(workspace.x + workspace.width / 2 - width / 2) <= 1, `${theme} workspace centered at ${width}px`);
        await openCalibration();
        const dialog = await page.locator("#calibrationDialog").boundingBox();
        assert.ok(dialog.x >= 0 && dialog.x + dialog.width <= width, `${theme} dialog fits viewport`);
        await page.screenshot({path:path.join(output, `uzu-128k-${theme}-${width}.png`)});
        await page.getByRole("button", {name:"Close Calibration Assistant", exact:true}).click();
      }
      assert.deepEqual(errors, [], "No uncaught browser errors");
      assert.deepEqual(blocked, [], "No unexpected mutation or external request attempted");
      if (liveChat) {
        await require("./uzu_browser_live_chat.cjs")({page, context, base, output});
        assert.deepEqual(errors, [], "No uncaught errors during real Chat");
        assert.deepEqual(blocked, [], "No unexpected writes during real Chat");
      }
      const final = await (await context.request.get(`${base}/api/status`)).json();
      assert.equal(final.phase, "idle", "The browser check must leave the launcher idle");
      console.log("Real browser: saved 128K result displayed at 100%, Apply and reload preserved the ready route; layouts aligned. " + (liveChat ? "Real Chat finished and the model unloaded." : "No model loaded."));
    } catch (error) {
      await page.screenshot({path:path.join(output, "browser-failure.png"), fullPage:true});
      console.error(JSON.stringify({pageErrors:errors, blockedRequests:blocked}));
      throw error;
    } finally {
      await context.close();
      await browser.close();
    }
  })().catch(error => {console.error(error.message); process.exitCode = 1;});
}
