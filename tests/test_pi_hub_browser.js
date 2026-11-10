"use strict";
// Real installed Pi and real Hub DOM/handlers; generated SSE, no model load.
const assert = require("node:assert/strict");
const {spawn} = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");
if (process.env.LLM_LAUNCHER_PI_HUB_BROWSER !== "1" || !process.env.LLM_LAUNCHER_BROWSER_PACKAGE) {
  console.log("Installed Pi Hub browser check skipped (opt-in).");
} else {
  (async () => {
    const {chromium} = require(process.env.LLM_LAUNCHER_BROWSER_PACKAGE);
    const child = spawn(process.env.LLM_LAUNCHER_TEST_PYTHON || "/opt/homebrew/bin/python3",
      [path.join(__dirname, "fixtures/pi_hub_browser_server.py")], {
        cwd:path.resolve(__dirname, ".."),
        env:{PATH:process.env.PATH, LLM_LAUNCHER_PI_HUB_BROWSER:"1"},
        stdio:["ignore", "pipe", "pipe"],
      });
    let diagnostics = "", browser;
    child.stderr.on("data", data => { diagnostics = (diagnostics + data).slice(-8000); });
    const exited = new Promise(resolve => child.once("exit", (code, signal) => resolve({code,signal})));
    try {
      const base = await new Promise((resolve, reject) => {
        let text = "";
        const timer = setTimeout(() => reject(new Error("Fixture startup timed out: " + diagnostics)), 30_000);
        child.once("exit", () => { clearTimeout(timer); reject(new Error("Fixture exited: " + diagnostics)); });
        child.stdout.on("data", data => {
          text += data;
          if (text.includes("\n")) {
            clearTimeout(timer);
            try { resolve(JSON.parse(text.split("\n")[0]).base); } catch (e) { reject(e); }
          }
        });
      });
      browser = await chromium.launch({headless:true});
      const context = await browser.newContext({viewport:{width:1440,height:1000}});
      const page = await context.newPage();
      page.setDefaultTimeout(25_000);
      const errors = [];
      page.on("pageerror", error => errors.push(error.message));
      await context.route("**/*", route => new URL(route.request().url()).origin === base
        ? route.continue() : route.abort("blockedbyclient"));
      await page.goto(base);
      await page.locator("#agentConsoleInput").waitFor({state:"visible"});
      assert.equal(await page.locator(".app-bar").isVisible(), false, "Hub has one header, without the app banner");
      assert.equal(await page.locator("#agentConsoleTabs").isVisible(), false, "A single session needs no duplicate tab");
      assert.equal(await page.locator("#agentConsoleCompactButton").isVisible(), false, "Compaction is in the overflow menu");
      assert.equal(await page.locator("#agentConsoleStatus").isVisible(), false, "Idle instructions do not repeat under the composer");
      const send = async message => {
        await page.locator("#agentConsoleInput").fill(message);
        await page.locator("#agentConsoleEnterButton").click();
      };
      const answer = text => page.locator(".agent-pi-event-answer").filter({hasText:text});
      const idle = () => page.waitForFunction(() =>
        document.getElementById("agentPiTimelineViewport").getAttribute("aria-busy") === "false"
        && document.getElementById("agentConsoleEnterButton").innerText === "Send");
      await send("first");
      await answer("Final answer for first.").waitFor();
      await idle();
      await answer("Final answer for first.").evaluate(node => { window.completedAnswerNode = node; });
      await send("long");
      await page.waitForFunction(() => document.getElementById("agentPiTimeline").textContent.includes("Line 070:"));
      await answer("Line 070:").evaluate(node => { window.streamingAnswerNode = node; });
      const viewport = page.locator("#agentPiTimelineViewport");
      await viewport.hover();
      await page.mouse.wheel(0, -100000);
      await page.waitForFunction(() => document.getElementById("agentPiTimelineViewport").scrollTop < 2);
      await page.waitForFunction(() => document.getElementById("agentPiTimeline").textContent.includes("Line 200:"));
      assert.ok(await answer("Line 200:").evaluate(node => node === window.streamingAnswerNode),
        "Streaming should update the existing card body without replacing the card");
      assert.ok(await answer("Final answer for first.").evaluate(node => node === window.completedAnswerNode),
        "Streaming must keep completed message DOM nodes in place instead of rebuilding the transcript");
      assert.ok(await viewport.evaluate(node => node.scrollTop) < 2, "Streaming must not drag the reader to the bottom");
      await page.locator("#agentPiTimelineJumpLatest").waitFor({state:"visible"});
      // Queue from the actual composer, then let enough deltas evict the old
      // delivery journal. A real browser reload must retain both conversations.
      await send("queued");
      await page.waitForFunction(() => document.getElementById("agentConsoleEscapeButton").disabled === false);
      await page.locator("#agentConsoleQueueMessages pre").filter({hasText:"queued"}).waitFor();
      assert.equal(await page.locator("#agentConsoleQueue").getAttribute("open"), "");
      await page.waitForFunction(() => document.getElementById("agentPiTimeline").textContent.includes("Line 599:"));
      const overflow = await (await context.request.get(base+"/fixture/status")).json();
      assert.ok(overflow.timelineRevision > overflow.journalLimit && overflow.journalBaseRevision > 1,
        "The real delivery journal must actually overflow before the reload check");
      await page.reload();
      await answer("Final answer for first.").waitFor();
      await answer("Line 599:").waitFor();
      await page.locator("#agentConsoleQueueMessages pre").filter({hasText:"queued"}).waitFor();
      const token = (await (await context.request.get(base+"/api/bootstrap")).json()).token;
      assert.equal((await context.request.post(base+"/fixture/release", {headers:{"X-Launcher-Token":token}})).status(), 200);
      await answer("Final answer for queued.").waitFor();
      await idle();
      assert.equal(await page.locator("#agentConsoleQueue").isVisible(), false);
      assert.equal(await answer("Final answer for first.").count(), 1);
      assert.equal(await answer("Final answer for long.").count(), 1);
      await send("hold");
      await page.waitForFunction(() => document.getElementById("agentPiTimelineViewport").getAttribute("aria-busy") === "true");
      await send("must-not-run");
      await page.locator("#agentConsoleInterruptButton").click();
      await idle();
      assert.match(await page.locator("#agentConsoleStatus").innerText(), /paused/);
      assert.equal(await page.locator("#agentConsoleQueueMessages pre").innerText(), "must-not-run");
      assert.match(await page.locator("#agentConsoleQueueSummary").innerText(), /paused/);
      assert.doesNotMatch(await page.locator("#agentConsoleStatus").innerText(), /returned thinking without/);
      await page.locator("#agentConsoleActionsMenu > summary").click();
      await page.locator("#agentConsoleEscapeButton").click();
      await page.waitForFunction(() =>
        document.querySelector("#agentConsoleActionsMenu > summary") === document.activeElement);
      await send("after-stop");
      await answer("Final answer for after-stop.").waitFor();
      await idle();
      assert.doesNotMatch(await page.locator("#agentPiTimeline").innerText(),
        /finished its reasoning without a final response/,
        "A deliberate Stop must not masquerade as a model thinking-only failure");
      const observed = await (await context.request.get(base+"/fixture/status")).json();
      assert.deepEqual(observed.requests, ["first", "long", "queued", "hold", "after-stop"]);
      assert.equal(await answer("Final answer for first.").count(), 1);
      assert.ok(await page.locator(".agent-pi-event-thinking").count() >= 4);
      for (const [theme, width] of [["frost",1440], ["daylight",960]]) {
        await page.setViewportSize({width,height:1000});
        await page.locator("#agentConsoleBackButton").click();
        assert.ok(await page.locator(".app-bar").isVisible());
        await page.locator("#launchTools").evaluate(node => node.open = true);
        assert.ok(await page.locator("#homeFastestEngine").isVisible(), "Runtime comparison stays in launch diagnostics");
        await page.locator("#launchTools").evaluate(node => node.open = false);
        await page.locator("#hubToolsMenuButton").click();
        await page.locator("#themeMenuButton").click();
        await page.locator(`[data-theme-choice="${theme}"]`).click();
        assert.equal(await page.locator("#hubToolsMenuButton").evaluate(node => node === document.activeElement), true,
          "Appearance returns keyboard focus to the visible Advanced button");
        await page.locator("#focusedConsoleButton").click();
        assert.equal(await viewport.evaluate(node => getComputedStyle(node).backgroundColor), "rgb(0, 0, 0)");
        const thinkingColor = await page.locator(".agent-pi-event-thinking").first().evaluate(node => getComputedStyle(node).backgroundColor);
        const answerColor = await page.locator(".agent-pi-event-answer").first().evaluate(node => getComputedStyle(node).backgroundColor);
        assert.notEqual(thinkingColor, answerColor, `${theme}: thinking stays distinct from the answer`);
        const buttons = await page.locator(".agent-console-keys > button").evaluateAll(nodes =>
          nodes.filter(node => node.getClientRects().length)
            .map(node => ({top:node.getBoundingClientRect().top,height:node.getBoundingClientRect().height})));
        assert.ok(Math.max(...buttons.map(b=>b.top)) - Math.min(...buttons.map(b=>b.top)) <= 1, `${theme}: composer buttons align`);
        assert.ok(Math.max(...buttons.map(b=>b.height)) - Math.min(...buttons.map(b=>b.height)) <= 1, `${theme}: composer buttons have equal height`);
      }
      await page.setViewportSize({width:390,height:844});
      assert.ok(await viewport.evaluate(node => node.clientHeight) > 600, "Mobile Hub leaves most of the screen for conversation");
      assert.ok(await page.locator("#agentConsoleStatusModel").isVisible(), "The active model stays identifiable on mobile");
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false,
        "Mobile Hub does not overflow horizontally");
      const statusSummary = page.locator("#agentConsoleStatusSummary");
      await statusSummary.focus();
      assert.ok(await statusSummary.evaluate(node => node === document.activeElement && node.getClientRects().length > 0),
        "Mobile status retains a visible keyboard focus target");
      await page.keyboard.press("Enter");
      assert.ok(await page.locator("#agentConsoleStatusPanel").evaluate(node => node.open),
        "Keyboard users can open mobile status details");
      await page.keyboard.press("Escape");
      assert.equal(await page.locator("#agentConsoleStatusPanel").evaluate(node => node.open), false);
      assert.ok(await statusSummary.evaluate(node => node === document.activeElement),
        "Closing mobile details restores summary focus");
      await page.locator("#agentConsoleActionsMenu > summary").click();
      await page.locator("#agentConsoleCopyButton").click();
      await page.waitForFunction(() =>
        document.querySelector("#agentConsoleActionsMenu > summary") === document.activeElement);
      await page.setViewportSize({width:1440,height:1000});
      await page.locator("#agentConsoleBackButton").click();
      await page.locator("#launchOverview").waitFor({state:"visible"});
      assert.ok(await page.locator("#quitLauncherButton").isVisible(), "Quit is visible on the launcher");
      assert.equal(await page.locator('[data-client="omp"]').count(), 1, "oh-my-pi is a first-class assistant choice");
      const homeSelection = await page.locator("#modelSelect").inputValue();
      const homeContext = await page.locator("#contextInput").inputValue();
      await page.locator("#homeModelSearch").fill("no-matching-model-name");
      assert.equal(await page.locator("#modelSelect").inputValue(), homeSelection, "Search does not change the chosen model");
      assert.equal(await page.locator("#contextInput").inputValue(), homeContext, "Search does not reset settings");
      assert.match(await page.locator("#homeModelSearchStatus").innerText(), /0 matches/);
      await page.locator("#homeModelSearch").fill("");
      const output = path.resolve(__dirname, "../build/browser-qa");
      fs.mkdirSync(output, {recursive:true});
      await page.screenshot({path:path.join(output, "launcher-home-desktop.png")});
      const boxes = await page.locator("#launchOverview").evaluate(node => ({overview:node.getBoundingClientRect().x, model:document.getElementById("homeModelList").getBoundingClientRect().x}));
      assert.ok(boxes.overview > boxes.model, "Desktop keeps settings beside the model library");
      await page.setViewportSize({width:390,height:844});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, "Mobile launcher does not overflow horizontally");
      assert.ok(await page.locator("#quitLauncherButton span[aria-hidden]").isVisible(),"Mobile Quit keeps its visible power icon");
      assert.match(await page.locator("#quitLauncherButton").innerText(),/Quit/,"Mobile Quit has a visible text label");
      assert.ok(await page.locator("#homeModelList").evaluate(node=>node.getBoundingClientRect().width)>300,"Mobile model selection uses the available width");
      assert.ok(await page.locator("#launchOverview").evaluate(node=>node.getBoundingClientRect().width)>300,"Mobile setup summary uses the available width");
      assert.equal(await page.locator("#launchSettings").evaluate(node=>node.open),true);
      assert.ok(await page.locator("#outputInput").isVisible(),"Model settings are directly visible on mobile");
      await page.screenshot({path:path.join(output, "launcher-home-mobile.png"),fullPage:true});
      await page.setViewportSize({width:1440,height:1000});
      await page.locator("#focusedConsoleButton").click();
      fs.mkdirSync(output, {recursive:true});
      await page.screenshot({path:path.join(output, "pi-hub-controls.png")});
      await page.locator("#agentConsoleActionsMenu > summary").click();
      await page.locator("#agentConsoleStopButton").click();
      await page.waitForFunction(() => document.getElementById("agentConsoleInput").disabled);
      assert.equal(await answer("Final answer for after-stop.").count(), 1, "Stopping Pi retains its answer");
      assert.deepEqual(errors, []);
      console.log("Installed Pi in real Hub browser: streaming scroll, queue, reload after journal overflow, Stop response/recovery and retained stopped transcript passed. No model loaded.");
    } finally {
      if (browser) await browser.close();
      child.kill("SIGTERM");
      const result = await Promise.race([exited, new Promise(resolve => {
        const timer=setTimeout(() => resolve(null), 10_000); timer.unref();
      })]);
      assert.ok(result, "Fixture cleanup did not finish; inspect its process before retrying");
      assert.equal(result.code, 0, diagnostics);
    }
  })().catch(error => { console.error(error); process.exitCode = 1; });
}
