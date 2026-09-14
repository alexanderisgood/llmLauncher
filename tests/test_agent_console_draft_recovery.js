"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

if (!process.env.LLM_LAUNCHER_BROWSER_PACKAGE) {
  console.log("Draft recovery browser fixture skipped (set LLM_LAUNCHER_BROWSER_PACKAGE).");
} else (async () => {
  const {chromium} = require(process.env.LLM_LAUNCHER_BROWSER_PACKAGE);
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1000,height:760}});
    const errors = [];
    page.on('pageerror', error=>errors.push(error.message));
    const html = fs.readFileSync(path.resolve(__dirname,"../index.html"),"utf8");
    const dialog = html.slice(html.indexOf('  <dialog id="agentConsoleDraftsDialog"'),
      html.indexOf('  <dialog id="modelLibraryDialog"'));
    await page.route("**/*", route=>route.fulfill({contentType:"text/html",
      body:`<!doctype html><html data-theme="frost"><head><meta charset="utf-8"></head><body><input id="agentConsoleInput">${dialog}</body></html>`}));
    await page.goto("http://127.0.0.1:19876/");
    for (const file of ["styles.css","launcher-home.css"]) {
      await page.addStyleTag({path:path.resolve(__dirname,"..",file)});
    }
    for (const file of ["chat_drafts.js","agent_console_tabs.js"]) {
      await page.addScriptTag({path:path.resolve(__dirname,"..",file)});
    }
    const app = fs.readFileSync(path.resolve(__dirname,"../app.js"),"utf8");
    const between = (a,b)=>app.slice(app.indexOf(a),app.indexOf(b,app.indexOf(a)));
    const longDraft = '<script>alert("unsafe")</script>\n' + 'Full draft retained. '.repeat(1000);
    await page.addScriptTag({content:`
      const state={agentConsoleOwnerRunId:'new-run',agentConsoleSurfaceId:'new-surface',
        agentConsoleViews:{'new-surface':{meta:{protocol:'pi-rpc',conversationId:'a'.repeat(64)}}}};
      const $=id=>document.getElementById(id);
      const currentAgentConsoleView=()=>state.agentConsoleViews[state.agentConsoleSurfaceId];
      const ChatDraftsCore=LLMChatDraftsCore, AgentConsoleTabsCore=LLMAgentConsoleTabs;
      const api=()=>{throw new Error('Draft recovery must never call the agent API');};
      ${between('const AGENT_CONSOLE_DRAFTS_KEY =','const CHAT_QUEUE_MAX_CHARACTERS')}
      ${between('function agentConsoleRunDraftKey()', 'function reconcileAgentConsoleViewMeta(')}
      persistAgentConsoleDraft('old-run:old-surface','Continue developing');
      persistAgentConsoleDraft('another-run:another-surface',${JSON.stringify(longDraft)});
      restoreAgentConsoleDraft();
      openAgentConsoleDrafts();
    `});
    const options = page.locator("#agentConsoleDraftsList button");
    assert.deepEqual(errors,[], 'The actual draft functions must initialise without script errors');
    assert.equal(await options.count(),2);
    assert.equal(await page.locator('#agentConsoleDraftsList script').count(),0);
    assert.ok((await options.first().textContent()).length<350,"Picker previews stay bounded");
    await page.screenshot({path:"/tmp/launcher-draft-recovery-fixture.png"});
    await page.locator('#agentConsoleInput').evaluate(input=>{
      input.value='Keep current draft'; saveAgentConsoleDraft();
    });
    await options.filter({hasText:'Continue developing'}).click();
    assert.equal(await page.locator('#agentConsoleInput').inputValue(),'Keep current draft');
    assert.match(await page.locator('#agentConsoleDraftsStatus').textContent(),/kept/);
    await page.locator('#agentConsoleInput').evaluate(input=>{
      input.value=''; saveAgentConsoleDraft();
    });
    await options.filter({hasText:'Continue developing'}).click();
    assert.equal(await page.locator('#agentConsoleInput').inputValue(),'Continue developing');
    assert.equal(await page.locator('dialog').evaluate(node=>node.open),false);
    assert.equal(await page.evaluate(()=>ChatDraftsCore.readDraft(agentConsoleDrafts(),'old-run:old-surface')),'');
    assert.equal(await page.evaluate(()=>ChatDraftsCore.readDraft(agentConsoleDrafts(),agentConsoleDraftKey())),'Continue developing');
    await page.evaluate(()=>{
      $('agentConsoleInput').dataset.draftKey='';
      delete currentAgentConsoleView().inputDraftKey;
      agentConsoleDraftEnvelope=null;
      restoreAgentConsoleDraft();
    });
    assert.equal(await page.locator('#agentConsoleInput').inputValue(),'Continue developing',
      'The recovered draft persists under the new conversation identity');
    await page.evaluate(()=>{
      $('agentConsoleInput').value=''; saveAgentConsoleDraft(); openAgentConsoleDrafts();
    });
    await page.locator('#agentConsoleDraftsList button').click();
    assert.ok((await page.locator('#agentConsoleInput').inputValue()).length>19000,
      'Recovery uses the complete stored text, not the bounded preview');
    console.log('Browser draft recovery: legacy run keys, exact text, bounded safe previews, occupied composer and refresh passed.');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
