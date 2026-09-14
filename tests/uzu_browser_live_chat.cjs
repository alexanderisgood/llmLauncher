"use strict";

// Called only by the explicitly opted-in browser harness. This starts one
// ordinary launcher-owned Uzu session and always stops only that exact run.
const assert = require("node:assert/strict");
const path = require("node:path");

module.exports = async function verifyLiveChat({page, context, base, output}) {
  let ownedRunId = null;
  let stage = "launch";
  const status = async () => (await context.request.get(`${base}/api/status`)).json();
  try {
    await page.setViewportSize({width:1440, height:1080});
    const launchResponse = page.waitForResponse(response =>
      response.url() === `${base}/api/launch` && response.request().method() === "POST"
    );
    await page.locator("#launchButton").click();
    const response = await launchResponse;
    const launched = await response.json();
    assert.equal(response.status(), 202, launched.error || "Launch was not accepted");
    ownedRunId = launched.run.runId;
    assert.ok(ownedRunId, "Capture the exact owned run before waiting for readiness");
    console.log(`Browser Chat: launcher accepted run ${ownedRunId}; waiting for Uzu.`);
    await page.waitForFunction(() =>
      !document.getElementById("chatWorkspace").classList.contains("hidden")
      && !document.getElementById("chatInput").disabled
    );
    await page.locator("#chatSidebarToggle").click();
    const firstPrompt = "Launcher browser QA: write 120 numbered lines for a scrolling test. Each line should contain its number followed by the words Local chat rendering works. Do not discuss the task. After line 120 finish with BROWSER-QA-DONE.";
    await page.locator("#chatInput").fill(firstPrompt);
    await page.locator("#chatSendButton").click();
    stage = "visible thinking";
    await page.waitForFunction(() =>
      [...document.querySelectorAll(".chat-reasoning-body")].some(node => node.textContent.trim().length > 0)
    );
    console.log("Browser Chat: separate thinking is visible; queuing a follow-up.");
    await page.locator("#chatInput").fill("Now answer this arithmetic check: what is 17 + 25? Give six short ways to verify the answer. Finish with QUEUE-QA-DONE.");
    await page.locator("#chatSendButton").click();
    stage = "queued follow-up";
    await page.waitForFunction(() =>
      !document.getElementById("chatQueue").classList.contains("hidden")
      && document.getElementById("chatQueue").textContent.includes("17 + 25")
    );
    console.log("Browser Chat: follow-up is queued; waiting for a scrollable answer.");
    stage = "scrollable transcript";
    await page.waitForFunction(() => {
      const messages = document.getElementById("chatMessages");
      return messages.scrollHeight > messages.clientHeight + 200;
    });
    stage = "pointer scrolling transcript to top";
    // Use the transcript's blank padding, not its nested thinking scroller.
    await page.locator("#chatMessages").hover({position:{x:5, y:5}});
    await page.mouse.wheel(0, -20000);
    await page.waitForFunction(() => document.getElementById("chatMessages").scrollTop < 10,
      null, {timeout:10_000});
    const before = await page.locator("#chatMessages").evaluate(node => node.textContent.length);
    stage = "scroll position during streaming";
    await page.waitForFunction(length =>
      document.getElementById("chatMessages").textContent.length > length + 100, before
    );
    const scrollTop = await page.locator("#chatMessages").evaluate(node => node.scrollTop);
    assert.ok(scrollTop < 10, "Streaming must not pull a reader back to the bottom");
    console.log("Browser Chat: queue visible and scroll position preserved while output grows.");
    stage = "completed queued answer";
    await page.waitForFunction(() => {
      const answers = [...document.querySelectorAll(".chat-message.assistant .chat-message-body")];
      return answers.some(node => node.textContent.includes("QUEUE-QA-DONE"))
        && document.getElementById("chatStopButton").classList.contains("hidden");
    }, null, {timeout:180_000});
    const transcript = (await page.locator(".chat-message.assistant .chat-message-body").allInnerTexts()).join("\n");
    assert.match(transcript, /BROWSER-QA-DONE/);
    assert.match(transcript, /42/);
    stage = "measured TPS";
    // The usage dashboard polls independently of the completed response stream.
    await page.waitForFunction(() => /[0-9].*(tok|TPS)/i.test(
      document.getElementById("chatStatusSpeedValue").textContent
    ), null, {timeout:10_000});
    const speed = await page.locator("#chatStatusSpeedValue").innerText();
    assert.match(speed, /[0-9].*(tok|TPS)/i, "The completed response must expose measured TPS");
    await page.screenshot({path:path.join(output, "uzu-live-chat-queue-scroll.png"), fullPage:true});
    stage = "End chat";
    const stopped = page.waitForResponse(response =>
      response.url() === `${base}/api/stop` && response.request().method() === "POST"
    );
    await page.locator("#endChatButton").click();
    assert.equal((await stopped).status(), 200, "End chat must stop the owned model");
    await page.waitForFunction(() => document.getElementById("endChatButton").disabled);
    assert.equal((await status()).phase, "idle", "End chat must unload without harness cleanup");
    assert.equal(await page.locator("#chatWorkspace").isVisible(), true,
      "The ended conversation should remain readable");
    assert.match((await page.locator(".chat-message.assistant .chat-message-body").allInnerTexts()).join("\n"), /QUEUE-QA-DONE/);
    await page.screenshot({path:path.join(output, "uzu-live-chat-ended.png"), fullPage:true});
    console.log(`Browser Chat: both answers completed, TPS displayed (${speed}), End chat unloaded the model and retained the transcript.`);
  } catch (error) {
    console.error(`Browser Chat test stopped at: ${stage}`);
    if (typeof page.evaluate === "function") {
      console.error(JSON.stringify(await page.evaluate(() => {
        const node = document.getElementById("chatMessages");
        return {scrollTop:node.scrollTop, scrollHeight:node.scrollHeight,
          clientHeight:node.clientHeight,
          assistantCount:node.querySelectorAll(".assistant").length};
      })));
    }
    if (typeof page.screenshot === "function") {
      await page.screenshot({path:path.join(output, "chat-failure-before-stop.png"), fullPage:true});
    }
    throw error;
  } finally {
    if (ownedRunId) {
      const current = await status();
      if (current.run?.runId === ownedRunId && current.phase !== "idle") {
        const bootstrap = await (await context.request.get(`${base}/api/bootstrap`)).json();
        await context.request.post(`${base}/api/stop`, {
          headers:{"X-Launcher-Token":bootstrap.token}, data:{},
        });
      } else if (current.phase !== "idle") {
        throw new Error("Another run replaced the browser test; it was not stopped.");
      }
      const deadline = Date.now() + 30_000;
      let idle = false;
      while (Date.now() < deadline) {
        if ((await status()).phase === "idle") {idle = true; break;}
        await new Promise(resolve => setTimeout(resolve, 250));
      }
      if (!idle) throw new Error("The owned browser-test model did not return to idle after Stop.");
    }
  }
};
