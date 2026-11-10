"use strict";
const assert = require("node:assert/strict");
const path = require("node:path");
if (!process.env.LLM_LAUNCHER_BROWSER_PACKAGE) {
  console.log("OMP semantic timeline browser fixture skipped (opt-in).");
} else (async () => {
  const {chromium} = require(process.env.LLM_LAUNCHER_BROWSER_PACKAGE);
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:390,height:844}});
    await page.route("**/*", route => route.abort("blockedbyclient"));
    await page.setContent('<div id="viewport" style="height:400px;overflow:auto"><div id="timeline" role="list"></div></div>');
    for (const file of ["pi_timeline.js","pi_timeline_view.js"]) {
      await page.addScriptTag({path:path.resolve(__dirname,"..",file)});
    }
    await page.evaluate(() => {
      window.fixtureView = LLMPiTimelineView.createTimelineView({document,core:LLMPiTimelineCore,formatTimestamp:() => null});
      window.fixtureItems = [{key:"answer",kind:"answer",text:'Visible <script>window.attacked=true</script> answer',title:""},
        {key:"usage",kind:"summary",text:"120 prompt tokens · 30 generated tokens",title:"Complete"}];
      fixtureView.render(document.getElementById("timeline"),fixtureItems,{viewport:document.getElementById("viewport"),
        surfaceId:"omp-generated",protocol:"omp-rpc",followTail:true});
    });
    assert.equal(await page.locator("#timeline article header strong").textContent(),"oh-my-pi");
    assert.match(await page.locator(".agent-pi-prompt-summary").getAttribute("title"),/^oh-my-pi-reported/);
    assert.equal(await page.locator("#timeline script").count(),0);
    assert.equal(await page.evaluate(() => window.attacked),undefined);
    await page.evaluate(() => {
      fixtureView.render(document.getElementById("timeline"),fixtureItems,{viewport:document.getElementById("viewport"),
        surfaceId:"omp-generated",protocol:"pi-rpc",followTail:true});
    });
    assert.equal(await page.locator("#timeline article header strong").textContent(),"Pi",
      "protocol changes rebuild stale agent labels even when item keys are identical");
    assert.match(await page.locator(".agent-pi-prompt-summary").getAttribute("title"),/^Pi-reported/);
    console.log("Browser OMP timeline: inert model text, correct agent/usage labels, protocol replacement and Pi defaults passed.");
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
