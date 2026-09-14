"use strict";

const assert = require("node:assert/strict");
const path = require("node:path");
const {browserArtifactUrls} = require("../pi_timeline_view.js");

const runId = "794c4295-92c4-4b89-a1e9-1df7a3953cfc";
const name = "1788853200000-1234abcd.png";
const saved = {saved:true, mimeType:"image/png", path:`/private/launcher/runs/${runId}/browser/${name}`};
const item = {key:"shot", kind:"toolResult", title:"Result · browser_check", text:JSON.stringify(saved)};
const url = `/api/browser-artifact?runId=${runId}&name=${name}`;
assert.deepEqual(browserArtifactUrls(item), [url]);
assert.deepEqual(browserArtifactUrls({...item, text:JSON.stringify({results:[saved,saved]})}), [url]);
const lateSteps = [...Array(11).fill({action:"inspect",ok:true}),saved];
assert.deepEqual(browserArtifactUrls({...item,text:JSON.stringify({results:lateSteps})}),[url],
  "The twelfth sequence action can contain a screenshot");
for (const invalid of [
  {...item, kind:"answer"},
  {...item, title:"Result · bash"},
  {...item, text:"{"},
  {...item, text:"null"},
  {...item, text:JSON.stringify({...saved,saved:false})},
  {...item, text:JSON.stringify({...saved,mimeType:"image/svg+xml"})},
  ...[
    `https://evil.test/runs/${runId}/browser/${name}`,
    `/private/launcher/runs/${runId}/browser/../../secret.png`,
    `/private/launcher/runs/${runId}/browser/${name}?external=https://evil.test`,
    `/private/launcher/runs/${runId}/browser/evil.svg`,
    `/private/launcher/runs/${runId}/browser/%2e%2e.png`,
    `/tmp/${name}`,
  ].map(file => ({...item,text:JSON.stringify({...saved,path:file})})),
]) assert.deepEqual(browserArtifactUrls(invalid), [], `Unsafe preview: ${invalid.text}`);

if (!process.env.LLM_LAUNCHER_BROWSER_PACKAGE) {
  console.log("Browser artifact URL tests passed; real DOM fixture skipped (requires installed Playwright path).");
} else {
  (async () => {
    const {chromium} = require(process.env.LLM_LAUNCHER_BROWSER_PACKAGE);
    const browser = await chromium.launch({headless:true});
    try {
      const page = await browser.newPage();
      const imageRequests = [];
      await page.route("**/*", route => {
        const requested = new URL(route.request().url());
        if (requested.origin !== "http://127.0.0.1:19876") return route.abort();
        if (requested.pathname === "/api/browser-artifact") {
          imageRequests.push(requested.pathname + requested.search);
          return route.fulfill({contentType:"image/png", body:Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jXioAAAAASUVORK5CYII=", "base64")});
        }
        return route.fulfill({contentType:"text/html", body:'<div id="viewport" style="height:800px;overflow:auto"><div id="timeline"></div></div>'});
      });
      await page.goto("http://127.0.0.1:19876/");
      await page.addScriptTag({path:path.resolve(__dirname,"../pi_timeline.js")});
      await page.addScriptTag({path:path.resolve(__dirname,"../pi_timeline_view.js")});
      await page.evaluate(first => {
        window.fixtureView = LLMPiTimelineView.createTimelineView({document,core:LLMPiTimelineCore,formatTimestamp:()=>null});
        window.fixtureRender = items => fixtureView.render(document.querySelector('#timeline'),items,{
          viewport:document.querySelector('#viewport'),surfaceId:'fixture',followTail:false,preserveScroll:false,
        });
        fixtureRender([first]);
      }, item);
      const details = page.locator("details");
      assert.equal(await details.evaluate(node=>node.open), false, "Screenshot results keep the normal collapsed default");
      assert.equal(await details.locator(".agent-pi-event-body").textContent(), "",
        "Collapsed results keep their text in the journal, not duplicated in the DOM");
      assert.equal(await details.locator("img").getAttribute("src"), null);
      assert.equal(await details.locator("img").getAttribute("loading"), "lazy");
      assert.equal(await details.locator("a").textContent(), "Open screenshot");
      assert.equal(await details.locator("a").getAttribute("href"), url);
      assert.equal(imageRequests.length, 0, "Collapsed screenshots must not fetch images eagerly");
      await details.locator("summary").click();
      await page.waitForFunction(()=>document.querySelector('details img').naturalWidth===1);
      assert.equal(await details.locator(".agent-pi-event-body").textContent(), item.text);
      assert.deepEqual(imageRequests,[url]);
      await details.locator("summary").click();
      await page.waitForFunction(()=>!document.querySelector('details img').hasAttribute('src'));
      assert.equal(await details.locator(".agent-pi-event-body").textContent(), "");
      const closedUpdate = {...item,text:JSON.stringify({...saved,note:"Updated while closed"})};
      await page.evaluate(next=>fixtureRender([next]),closedUpdate);
      assert.equal(await details.locator(".agent-pi-event-body").textContent(), "");
      assert.equal(await details.locator("a").getAttribute("href"),url,"Collapsed images retain access to saved artifacts");
      await details.locator("summary").click();
      await page.waitForFunction(()=>document.querySelector('details img').naturalWidth===1);
      assert.equal(await details.locator(".agent-pi-event-body").textContent(), closedUpdate.text,
        "Reopening shows the latest result, not the original closure's text");
      await details.evaluate(node=>{window.originalCard=node;window.originalImage=node.querySelector('img');});
      const updated = {...item,text:JSON.stringify({...saved,note:"Screenshot retained locally"})};
      await page.evaluate(next=>fixtureRender([next]),updated);
      assert.equal(await details.evaluate(node=>node===window.originalCard && node.open),true);
      assert.equal(await details.locator("img").evaluate(node=>node===window.originalImage),true,
        "Text updates retain the already loaded screenshot node");
      await page.evaluate(()=>fixtureView.setVisible(document.querySelector('#timeline'),false));
      assert.equal(await details.locator("img").getAttribute("src"),null,
        "Leaving the Hub releases expanded screenshots without closing their cards");
      assert.equal(await details.evaluate(node=>node===window.originalCard && node.open),true);
      await page.evaluate(next=>{
        fixtureRender([next]);
        document.querySelector('details').dispatchEvent(new Event('toggle'));
      },{...item,text:JSON.stringify({results:lateSteps})});
      assert.equal(await details.locator("img").getAttribute("src"),null,
        "A late result or disclosure event cannot reload a hidden preview");
      await page.evaluate(()=>fixtureView.setVisible(document.querySelector('#timeline'),true));
      await page.waitForFunction(()=>document.querySelector('details img').naturalWidth===1);
      assert.equal(await details.locator("img").getAttribute("src"),url,
        "Returning restores an expanded screenshot");
      await page.evaluate(next=>fixtureRender([next]),{...item,text:JSON.stringify({results:lateSteps})});
      assert.equal(await details.locator("img").count(),1,"A screenshot at step12 has a Hub preview");
      assert.equal(await details.locator("img").getAttribute("src"),url);
      const second = {...saved,path:saved.path.replace(name,"1788853200001-5678efab.png")};
      await page.evaluate(next=>fixtureRender([next]),{...item,text:JSON.stringify({results:[saved,second,saved]})});
      assert.equal(await details.locator("img").count(),2,"Sequences preview each unique local screenshot");
      assert.equal(await details.evaluate(node=>node.open),true);
      await page.evaluate(next=>fixtureRender([next]),{...item,text:JSON.stringify({saved:true,path:"https://evil.test/x.png",mimeType:"image/png"})});
      assert.equal(await details.locator("img").count(),0,"Replacing output cannot retain a stale screenshot preview");
      assert.equal(await page.evaluate(()=>window.originalImage.getAttribute("src")), null,
        "Removing a preview releases its decoded image resource");
      assert.equal(await details.evaluate(node=>node.open),true);
      const longText = "retained result\n".repeat(4000);
      await page.evaluate(text=>fixtureRender(Array.from({length:100},(_,i)=>({
        key:`result-${i}`,kind:'toolResult',title:'Result · read',text,
      }))),longText);
      assert.equal(await page.locator('.agent-pi-event-body').evaluateAll(nodes=>nodes.reduce((n,node)=>n+node.textContent.length,0)),0,
        "Long collapsed history adds no body text to the DOM");
      await page.locator('details summary').last().click();
      await page.waitForFunction(()=>document.querySelector('details:last-child .agent-pi-event-body').textContent.length>0);
      assert.equal(await page.locator('details').last().locator('.agent-pi-event-body').textContent(),longText);
      await page.evaluate(()=>fixtureRender([{key:'thinking',kind:'thinking',title:'',text:'Visible live reasoning'}]));
      await page.waitForFunction(()=>document.querySelector('details').open);
      assert.equal(await page.locator('.agent-pi-event-body').textContent(),'Visible live reasoning',
        "Live thinking remains expanded and readable");
      await page.evaluate(next=>fixtureRender([next]),item);
      await details.locator('summary').click();
      await page.waitForFunction(()=>document.querySelector('details img').naturalWidth===1);
      await page.evaluate(()=>{
        window.removedCard=document.querySelector('details');
        fixtureView.clear(document.querySelector('#timeline'));
        removedCard.dispatchEvent(new Event('toggle'));
      });
      assert.equal(await page.locator('#timeline > *').count(),0);
      assert.equal(await page.evaluate(()=>removedCard.querySelector('img').hasAttribute('src')),false,
        "Reset releases image sources; delayed events on detached cards cannot restore them");
      console.log("Hub screenshot preview passed: safe local URLs, lazy expanded images, sequence artifacts and preserved disclosure/DOM state.");
    } finally { await browser.close(); }
  })().catch(error=>{console.error(error);process.exitCode=1;});
}
