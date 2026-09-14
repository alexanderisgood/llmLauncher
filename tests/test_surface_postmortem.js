"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const styles = fs.readFileSync(path.join(root, "styles.css"), "utf8");

function sourceBetween(startMarker, endMarker) {
  const start = app.indexOf(startMarker);
  const end = app.indexOf(endMarker, start + startMarker.length);
  assert.ok(start >= 0, `missing production marker: ${startMarker}`);
  assert.ok(end > start, `missing production end marker: ${endMarker}`);
  return app.slice(start, end);
}

const chatProduction = [
  sourceBetween("function updateWorkspaceChrome()", "\nfunction updateChatWorkspace"),
  sourceBetween("function sessionRouteActive(run, phase)", "\nfunction renderChatRoute"),
  sourceBetween("function updateChatWorkspace(run, phase)", "\nfunction agentConsoleBaseOffset"),
].join("\n");

const agentProduction = [
  sourceBetween("function updateWorkspaceChrome()", "\nfunction updateChatWorkspace"),
  sourceBetween("function sessionRouteActive(run, phase)", "\nfunction renderChatRoute"),
  sourceBetween("function retainAgentConsoleView(view, phase, message)", "\nfunction enterAgentConsole"),
  sourceBetween("function updateAgentWorkspace(run, phase)", "\nfunction scheduleAgentConsoleRead"),
].join("\n");

function element() {
  return {
    hidden:false,
    disabled:false,
    textContent:"",
    value:"",
    dataset:{},
    classList:{
      values:new Set(),
      add(...values) { values.forEach(value => this.values.add(value)); },
      remove(...values) { values.forEach(value => this.values.delete(value)); },
      toggle(value, force) {
        if (force === undefined ? !this.values.has(value) : force) this.values.add(value);
        else this.values.delete(value);
      },
      contains(value) { return this.values.has(value); },
    },
    setAttribute() {},
  };
}

function chatHarness() {
  const elements = {};
  const calls = {abort:0, persist:0, queue:0, reset:0, rendered:0};
  const pending = {
    id:"assistant-1", role:"assistant", content:"partial answer", reasoning:"partial thought",
    pending:true, stopped:false, interrupted:false, exclude:false, failure:"",
  };
  const state = {
    agentConsoleVisible:false,
    chatAbort:{signal:{aborted:false}, abort() { this.signal.aborted = true; calls.abort += 1; }},
    chatAttachment:{
      id:"chat-1", ownerRunId:"owner-1", primary:false, client:"chat",
      surface:"Chat", backend:"omlx", model:"Model One", context:8192, output:1024,
    },
    chatAttachmentObserved:true,
    chatHistoryLoaded:true,
    chatHistoryLoading:false,
    chatMessages:[{id:"user-1", role:"user", content:"hard task"}, pending],
    chatOwnerRunId:"owner-1",
    chatPostmortem:null,
    chatQueue:[{id:"queued-1", content:"follow up"}],
    chatQueuePaused:false,
    chatQueueRecovered:false,
    chatResumePending:null,
    chatRunId:"chat-1",
    chatRunSettings:{chat:{}},
    chatRunSettingsKey:"owner-1:chat-1",
    chatTurnSettlement:{surfaceId:"chat-1", exitRequested:false},
    runPhase:"failed",
    runStatus:{phase:"failed", message:"The local route failed unexpectedly.", run:null, attachments:[]},
  };
  const context = {
    console,
    state,
    $:id => elements[id] || (elements[id] = element()),
    activateChatDraft:() => {},
    chatSurfaceRoute:run => {
      const source = state.chatAttachment || run;
      return source ? {backend:source.backend, model:source.model} : null;
    },
    closeChatRunSettings:() => { elements.chatRunSettingsPanel.hidden = true; },
    completePendingChatResume:async () => {},
    loadChatHistory:async () => {},
    persistChatQueue:() => { calls.queue += 1; },
    persistChatSessionState:() => { calls.persist += 1; return true; },
    profileBackendLabel:value => value || "Local",
    renderChatDraftStatus:() => {},
    renderChatMessages:() => { calls.rendered += 1; },
    renderChatRoute:() => {},
    renderChatSidebar:() => {},
    renderChatUsage:() => {},
    resetChatConversation:() => {
      calls.reset += 1;
      state.chatMessages = [];
      state.chatQueue = [];
      state.chatPostmortem = null;
    },
    setChatBusy:() => {},
    sizeChatInput:() => {},
    updateWorkSurface:() => {},
  };
  elements.chatRunSettingsPanel = element();
  elements.chatWorkspace = element();
  elements.chatWorkspace.classList.add("hidden");
  elements.agentWorkspace = element();
  elements.agentWorkspace.classList.add("hidden");
  elements.configScroll = element();
  elements.launchDock = element();
  vm.createContext(context);
  vm.runInContext(chatProduction, context);
  return {calls, context, elements, pending, state};
}

function agentHarness() {
  const elements = {};
  const calls = {clear:0, persist:0, render:0, schedule:0};
  const view = {
    meta:{
      id:"pi-1", ownerRunId:"owner-1", surface:"Pi", client:"pi", primary:false,
      backend:"omlx", model:"Model One", state:"running", status:"running",
      canInput:true, canStop:true, streaming:true,
    },
    terminal:{toString:() => "partial terminal output"},
    timeline:{revision:9, items:[{kind:"answer", text:"partial semantic answer"}]},
    timelineSeenRevision:4,
    offset:128,
    seenEnd:64,
    loaded:true,
    inputQueue:[{command:"prompt", message:"later prompt"}],
    inputRetryPending:false,
    postmortem:null,
  };
  const state = {
    agentConsoleMeta:view.meta,
    agentConsoleOwnerRunId:"owner-1",
    agentConsoleReading:false,
    agentConsoleRecoveryOwnerRunId:"",
    agentConsoleSurfaceId:"pi-1",
    agentConsoleTimer:null,
    agentConsoleVisible:true,
    agentConsoleViews:{"pi-1":view},
    runPhase:"failed",
    runStatus:{phase:"failed", message:"Agent process crashed.", run:null, attachments:[], agentConsoles:[]},
  };
  const context = {
    console,
    Object,
    state,
    $:id => elements[id] || (elements[id] = element()),
    AgentConsoleTabsCore:{consoleNeedsReplay:() => false},
    PiTimelineCore:{safeRevision:value => Number(value) || 0},
    agentConsoleDescriptors:() => [],
    agentConsoleShowsPiTimeline:() => false,
    agentPiTimelineView:{setVisible:() => {}},
    clearAgentConsoleSelection:() => {
      calls.clear += 1;
      state.agentConsoleViews = {};
      state.agentConsoleOwnerRunId = "";
      state.agentConsoleSurfaceId = "";
      state.agentConsoleVisible = false;
    },
    clientName:value => value === "pi" ? "Pi" : String(value || "Agent"),
    createAgentConsoleView:meta => ({meta, inputQueue:[], postmortem:null}),
    currentAgentConsoleView:() => state.agentConsoleViews[state.agentConsoleSurfaceId] || null,
    persistAgentConsoleRecovery:() => { calls.persist += 1; },
    readAgentConsoleRecovery:() => ({valid:false, seen:{}}),
    reconcileAgentConsoleViewMeta:(target, incoming) => {
      target.meta = {...target.meta, ...incoming};
      return {generationChanged:false, stale:false};
    },
    renderAgentConsole:() => { calls.render += 1; },
    renderAgentPiTimeline:() => {},
    renderAgentTerminalOutput:() => {},
    resetAgentPiTimeline:() => {},
    scheduleAgentConsoleRead:() => { calls.schedule += 1; },
    updateWorkSurface:() => {},
  };
  elements.agentWorkspace = element();
  elements.agentWorkspace.classList.add("hidden");
  elements.chatWorkspace = element();
  elements.chatWorkspace.classList.add("hidden");
  elements.configScroll = element();
  elements.launchDock = element();
  elements.agentTerminalOutput = element();
  vm.createContext(context);
  vm.runInContext(agentProduction, context);
  return {calls, context, elements, state, view};
}

function run() {
  const chat = chatHarness();
  chat.context.updateChatWorkspace(null, "failed");
  assert.equal(chat.calls.reset, 0, "route failure must not reset the Chat transcript");
  assert.equal(chat.state.chatMessages.length, 2);
  assert.equal(chat.pending.content, "partial answer");
  assert.equal(chat.pending.reasoning, "partial thought");
  assert.equal(chat.pending.pending, false);
  assert.equal(chat.pending.interrupted, true);
  assert.equal(chat.state.chatQueue.length, 1);
  assert.equal(chat.state.chatQueuePaused, true);
  assert.equal(chat.state.chatTurnSettlement.exitRequested, true);
  assert.equal(chat.calls.abort, 1);
  assert.equal(chat.state.chatPostmortem.state, "failed");
  assert.equal(chat.elements.chatWorkspace.classList.contains("hidden"), false);

  chat.state.runPhase = "running";
  chat.state.runStatus = {
    phase:"running", message:"Replacement ready",
    run:{purpose:"session", runId:"owner-2", client:"pi"}, attachments:[],
  };
  chat.context.updateChatWorkspace(chat.state.runStatus.run, "running");
  assert.equal(chat.calls.reset, 1, "a replacement owner may clear the retained surface");
  assert.equal(chat.state.chatRunId, "");
  assert.equal(chat.state.chatMessages.length, 0);

  const agent = agentHarness();
  agent.context.updateAgentWorkspace(null, "failed");
  assert.equal(agent.calls.clear, 0, "route failure must not delete bounded Hub views");
  assert.equal(agent.state.agentConsoleViews["pi-1"], agent.view);
  assert.equal(agent.view.terminal.toString(), "partial terminal output");
  assert.equal(agent.view.timeline.items[0].text, "partial semantic answer");
  assert.equal(agent.view.postmortem.state, "failed");
  assert.equal(agent.view.meta.canInput, false);
  assert.equal(agent.view.inputQueue.length, 1);
  assert.equal(agent.view.inputRetryPending, true);
  assert.equal(agent.elements.agentWorkspace.classList.contains("hidden"), false);
  assert.equal(agent.calls.schedule, 0, "a dead route must not restart the read poll");

  agent.state.runPhase = "running";
  agent.state.runStatus = {
    phase:"running", message:"Owner still running",
    run:{purpose:"session", runId:"owner-1", client:"chat", agentHost:"launcher"},
    attachments:[], agentConsoles:[],
  };
  agent.context.syncAgentConsoleViews(agent.state.runStatus, agent.state.runStatus.run, "running");
  assert.equal(agent.calls.clear, 0, "surface removal inside the same owner must retain its view");
  assert.equal(agent.state.agentConsoleViews["pi-1"], agent.view);
  assert.equal(agent.view.postmortem.state, "failed", "a later removal must not downgrade a failure marker");

  const replacement = {purpose:"session", runId:"owner-2", client:"chat", agentHost:"launcher"};
  agent.context.syncAgentConsoleViews(
    {phase:"running", message:"Replacement ready", run:replacement, attachments:[], agentConsoles:[]},
    replacement,
    "running",
  );
  assert.equal(agent.calls.clear, 1, "a different active owner is an explicit replacement boundary");
  assert.equal(Object.keys(agent.state.agentConsoleViews).length, 0);

  assert.match(styles, /chat-status-panel\[data-route-state="failed"\]/);
  assert.match(styles, /chat-route-card\[data-state="stopped"\]/);
  assert.match(app, /retainChatPostmortem\([\s\S]*Partial output was retained/);
  assert.match(app, /if \(!allowed\.has\(id\)\) \{[\s\S]*retainAgentConsoleView/);
  assert.doesNotMatch(
    sourceBetween("function updateChatWorkspace(run, phase)", "\nfunction agentConsoleBaseOffset"),
    /if \(!run[^)]*\)[\s\S]{0,500}resetChatConversation/,
  );

  console.log("Chat and Hub Console retain bounded postmortem output until explicit replacement.");
}

run();
