"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const app = fs.readFileSync(require.resolve("../agent_console_workspace.js"), "utf8");
const between = (start, end) => app.slice(app.indexOf(start), app.indexOf(end,app.indexOf(start)));
const saved = new Map();
function harness({owner="owner", conversation=""} = {}) {
  const input = {value:"",dataset:{},setCustomValidity(){},reportValidity(){}};
  const state = {agentConsoleOwnerRunId:owner,agentConsoleSurfaceId:"one",agentConsoleViews:{
    one:{meta:{startedAt:"generation",protocol:"pi-rpc",conversationId:conversation}}, two:{meta:{startedAt:"generation"}},
  }};
  let finish, fail;
  const context = vm.createContext({
    state, console,
    AgentConsoleTabsCore:require("../agent_console_tabs.js"),
    ChatDraftsCore:require("../chat_drafts.js"),
    AgentConsoleInputCore:require("../agent_console_input.js"),
    sessionStorage:{getItem:key=>saved.get(key),setItem:(key,value)=>saved.set(key,value)},
    $:id=>id === "agentConsoleInput" ? input : {disabled:false},
    currentAgentConsoleView:()=>state.agentConsoleViews[state.agentConsoleSurfaceId],
    renderAgentConsole:()=>context.restoreAgentConsoleDraft(),
    reconcileAgentConsoleViewMeta:(view,incoming)=>{view.meta={...view.meta,...incoming};},
    scheduleAgentConsoleRead:()=>{}, showNotice:()=>{},
    api:()=>new Promise((resolve,reject)=>{finish=resolve;fail=reject;}),
  });
  vm.runInContext(between('const AGENT_CONSOLE_DRAFTS_KEY =','let agentConsoleDraftEnvelope = null;')+'let agentConsoleDraftEnvelope = null;',context);
  vm.runInContext(between('function agentConsoleRunDraftKey()', 'function reconcileAgentConsoleViewMeta('),context);
  vm.runInContext(between('async function steerAgentConsoleInput()', 'function agentConsoleKeyData('),context);
  vm.runInContext(between('function agentConsoleResponseTargetIsCurrent(', 'async function stopAgentConsoleResponse('),context);
  const type = text=>{input.value=text;context.saveAgentConsoleDraft();};
  const select = id=>{context.saveAgentConsoleDraft();state.agentConsoleSurfaceId=id;context.restoreAgentConsoleDraft();};
  context.restoreAgentConsoleDraft();
  return {context,input,state,type,select,resolve:(response={console:{}})=>finish(response),reject:()=>fail(new Error("offline"))};
}

async function main() {
  const h = harness();
  h.type("First unsent message 🙂");
  h.select("two");
  assert.equal(h.input.value, "", "A draft must not leak into another console");
  h.type("Second message");
  h.select("one");
  assert.equal(h.input.value,"First unsent message 🙂");
  const refreshed = harness();
  assert.equal(refreshed.input.value,"First unsent message 🙂","Refresh restores the unsent message");
  refreshed.state.agentConsoleOwnerRunId = "another-owner";
  refreshed.state.agentConsoleViews = {one:{meta:{startedAt:"new-generation"}}};
  refreshed.context.restoreAgentConsoleDraft();
  assert.equal(refreshed.input.value,"","A new model run must not inherit an old prompt");

  // Identical text in two consoles previously let a late acknowledgement clear
  // the wrong input. Resolve the actual production steering function after switching.
  h.type("same text");
  const sending = h.context.steerAgentConsoleInput();
  h.select("two");
  h.type("same text");
  h.resolve(); await sending;
  assert.equal(h.input.value,"same text");
  h.select("one");
  assert.equal(h.input.value,"","Acknowledged steering clears only its own draft");
  h.type("old text");
  const next = h.context.steerAgentConsoleInput();
  h.type("new text while sending");
  h.resolve(); await next;
  assert.equal(h.input.value,"new text while sending");
  const failed = h.context.steerAgentConsoleInput();
  h.reject(); await failed;
  assert.equal(h.input.value,"new text while sending","Failed steering retains the draft");
  const afterRefresh = harness();
  assert.equal(afterRefresh.input.value,"new text while sending");
  h.type("");
  assert.equal(harness().input.value,"","Clearing a draft also removes its persisted copy");
  saved.clear();
  const conversation = "a".repeat(64), otherConversation = "b".repeat(64);
  const pending = harness();
  pending.type("Draft typed before Pi reports its session");
  pending.state.agentConsoleViews.one.meta.conversationId = conversation;
  pending.context.restoreAgentConsoleDraft();
  assert.equal(pending.input.value,"Draft typed before Pi reports its session");
  const restarted = harness({owner:"new-run",conversation});
  assert.equal(restarted.input.value,pending.input.value,"Same conversation survives a new engine/run ID");
  const unrelated = harness({owner:"new-run",conversation:otherConversation});
  assert.equal(unrelated.input.value,"","Another conversation must not inherit the draft");
  const changeSession = id=>{
    restarted.state.agentConsoleViews.one.meta.conversationId = id;
    restarted.context.restoreAgentConsoleDraft();
  };
  changeSession(otherConversation);
  assert.equal(restarted.input.value,"");
  restarted.type("Second conversation's draft");
  changeSession(conversation);
  assert.equal(restarted.input.value,"Draft typed before Pi reports its session");
  restarted.type("identical draft");
  const steering = restarted.context.steerAgentConsoleInput();
  changeSession(otherConversation);
  restarted.type("identical draft");
  restarted.resolve({console:{conversationId:conversation}}); await steering;
  assert.equal(restarted.input.value,"identical draft","A late steer acknowledgement cannot clear a different conversation");
  assert.equal(restarted.state.agentConsoleViews.one.meta.conversationId,otherConversation,
    "A late acknowledgement cannot switch the visible conversation identity back");
  assert.equal(harness({owner:"third-run",conversation:otherConversation}).input.value,"identical draft");
  const legacy = harness({owner:"legacy"});
  legacy.type("Unknown legacy conversation");
  assert.equal(harness({owner:"legacy",conversation:"c".repeat(64)}).input.value,"",
    "Do not guess a persisted legacy draft's conversation after refresh");
  assert.equal(harness({owner:"legacy"}).input.value,"Unknown legacy conversation",
    "An unbound legacy draft is preserved");
  const lateIdentity = harness({owner:"legacy"});
  lateIdentity.state.agentConsoleViews.one.meta.conversationId = "d".repeat(64);
  lateIdentity.context.restoreAgentConsoleDraft();
  assert.equal(lateIdentity.input.value,"",
    "Delayed initial metadata does not make an old unbound draft safe to migrate");
  console.log("Hub drafts: surface isolation, refresh, owner isolation and in-flight steering passed.");
}
main().catch(error=>{console.error(error);process.exitCode=1;});
