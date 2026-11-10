"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const app = fs.readFileSync(path.join(root, "agent_console_workspace.js"), "utf8");
const index = fs.readFileSync(path.join(root, "index.html"), "utf8");
const AgentConsoleInputCore = require("../agent_console_input.js");
const AgentConsoleTabsCore = require("../agent_console_tabs.js");
const PiTimelineCore = require("../pi_timeline.js");

function sourceBetween(startMarker, endMarker) {
  const start = app.indexOf(startMarker);
  const end = app.indexOf(endMarker, start + startMarker.length);
  assert.ok(start >= 0, `missing production marker: ${startMarker}`);
  assert.ok(end > start, `missing production end marker: ${endMarker}`);
  return app.slice(start, end);
}

assert.equal(AgentConsoleInputCore.AGENT_CONSOLE_MAX_INPUT_BYTES, 65_536);
assert.equal(AgentConsoleInputCore.PI_MESSAGE_MAX_BYTES, 65_280);
assert.equal(AgentConsoleInputCore.utf8ByteLength("A£🙂"), 7);
assert.equal(
  AgentConsoleInputCore.validatePiPrompt("🙂".repeat(16_320)).ok,
  true,
  "the exact UTF-8 byte limit is accepted",
);
const oversized = AgentConsoleInputCore.validatePiPrompt(`${"🙂".repeat(16_320)}a`);
assert.equal(oversized.ok, false);
assert.equal(oversized.bytes, 65_281);
assert.match(oversized.error, /has not been cleared/);
assert.equal(AgentConsoleInputCore.validatePiPrompt(" \n\t ").ok, false);

const firstPrompt = {command:"prompt", message:"first"};
const secondPrompt = {command:"prompt", message:"second"};
const thirdPrompt = {command:"prompt", message:"third"};
const ordered = [firstPrompt, secondPrompt];
const failedBatch = AgentConsoleInputCore.takeNextBatch(ordered);
ordered.push(thirdPrompt);
AgentConsoleInputCore.restoreFailedBatch(ordered, failedBatch);
assert.deepEqual(
  ordered,
  [firstPrompt, secondPrompt, thirdPrompt],
  "a failed in-flight item returns ahead of every later queued item",
);

const terminalQueue = ["a", "b", {command:"abort"}, "c"];
const terminalBatch = AgentConsoleInputCore.takeNextBatch(terminalQueue);
assert.equal(terminalBatch.payload, "ab");
assert.deepEqual(terminalBatch.items, ["a", "b"]);
assert.deepEqual(terminalQueue, [{command:"abort"}, "c"]);
AgentConsoleInputCore.restoreFailedBatch(terminalQueue, terminalBatch);
assert.deepEqual(terminalQueue, ["a", "b", {command:"abort"}, "c"]);

const visibleQueue = [
  {command:"prompt", message:"local one"},
  {command:"abort"},
  {command:"prompt", message:"local two"},
];
assert.equal(AgentConsoleInputCore.queuedPiPromptCount(visibleQueue), 2);
assert.equal(AgentConsoleInputCore.visiblePiPendingMessages(3, visibleQueue, 1), 6);
assert.equal(AgentConsoleInputCore.discardQueuedPiPrompts(visibleQueue), 2);
assert.deepEqual(visibleQueue, [{command:"abort"}]);

async function testProductionFailureOrdering() {
  const production = sourceBetween(
    "async function flushAgentConsoleInput(view, ownerRunId, surfaceId)",
    "\nfunction agentConsoleDimensions",
  );
  const view = {
    inputQueue:[{command:"prompt", message:"A"}],
    inputSending:false,
    inputError:"",
    inputRetryPending:false,
  };
  const state = {
    agentConsoleViews:{surface:view},
    agentConsoleOwnerRunId:"owner",
    agentConsoleSurfaceId:"surface",
  };
  const calls = [];
  let scheduledReads = 0;
  let rejectFirst;
  let markFirstStarted;
  const firstStarted = new Promise(resolve => { markFirstStarted = resolve; });
  let first = true;
  const context = {
    AgentConsoleInputCore,
    JSON,
    Boolean,
    state,
    console,
    api:(endpoint, options) => {
      calls.push(JSON.parse(options.body));
      if (first) {
        first = false;
        markFirstStarted();
        return new Promise((_resolve, reject) => { rejectFirst = reject; });
      }
      return Promise.resolve({console:{}});
    },
    reconcileAgentConsoleViewMeta:() => {},
    renderAgentConsole:() => {},
    scheduleAgentConsoleRead:() => { scheduledReads += 1; },
  };
  vm.createContext(context);
  vm.runInContext(production, context);

  const failed = context.flushAgentConsoleInput(view, "owner", "surface");
  await firstStarted;
  view.inputQueue.push(
    {command:"prompt", message:"B"},
    {command:"prompt", message:"C"},
  );
  rejectFirst(new Error("temporary controller failure"));
  await failed;

  assert.deepEqual(
    view.inputQueue.map(item => item.message),
    ["A", "B", "C"],
    "production sender must retain both the failed prompt and later follow-ups",
  );
  assert.equal(view.inputRetryPending, true);
  assert.match(view.inputError, /still first in the local queue/);

  await context.flushAgentConsoleInput(view, "owner", "surface");
  assert.deepEqual(
    calls.map(call => call.message),
    ["A", "A", "B", "C"],
    "retry must preserve original order after the failed network attempt",
  );
  assert.deepEqual(view.inputQueue, []);
  assert.equal(view.inputRetryPending, false);
  assert.equal(view.inputError, "");
  assert.equal(scheduledReads, 3, "every accepted prompt restarts output polling");
}

async function testPiResponseStopBypassesDeferredPromptQueue() {
  const production = sourceBetween(
    "function agentConsoleResponseTargetIsCurrent(view, ownerRunId, surfaceId, startedAt)",
    "\nfunction agentConsoleDimensions",
  );
  const firstPrompt = {command:"prompt", message:"A"};
  const secondPrompt = {command:"prompt", message:"B"};
  const thirdPrompt = {command:"prompt", message:"C"};
  const view = {
    meta:{protocol:"pi-rpc", startedAt:"2026-09-04T10:00:00Z", streaming:true},
    inputQueue:[firstPrompt],
    inputSending:false,
    inputInFlightPromptCount:0,
    inputError:"",
    inputRetryPending:false,
    abortBusy:false,
    abortRequest:null,
    readDrainRemaining:0,
  };
  const state = {
    agentConsoleMeta:view.meta,
    agentConsoleViews:{surface:view},
    agentConsoleOwnerRunId:"owner",
    agentConsoleSurfaceId:"surface",
  };
  const calls = [];
  const reconciliations = [];
  const notices = [];
  let scheduledReads = 0;
  let rejectFirstPrompt;
  let resolveAbort;
  let markFirstPromptStarted;
  let markAbortStarted;
  const firstPromptStarted = new Promise(resolve => { markFirstPromptStarted = resolve; });
  const abortStarted = new Promise(resolve => { markAbortStarted = resolve; });
  const context = {
    AgentConsoleInputCore,
    AgentConsoleTabsCore,
    JSON,
    Boolean,
    String,
    state,
    console,
    api:(_endpoint, options) => {
      const payload = JSON.parse(options.body);
      calls.push(payload);
      if (payload.command === "prompt" && payload.message === "A") {
        markFirstPromptStarted();
        return new Promise((_resolve, reject) => { rejectFirstPrompt = reject; });
      }
      if (payload.command === "abort") {
        markAbortStarted();
        return new Promise(resolve => { resolveAbort = resolve; });
      }
      return Promise.reject(new Error(`Unexpected Hub input: ${JSON.stringify(payload)}`));
    },
    agentConsoleUsesStructuredPi:targetView => targetView?.meta?.protocol === "pi-rpc",
    currentAgentConsoleView:() => state.agentConsoleViews[state.agentConsoleSurfaceId] || null,
    queueAgentConsoleInput:() => { throw new Error("Pi abort must not enter the prompt FIFO"); },
    reconcileAgentConsoleViewMeta:(targetView, incoming) => {
      reconciliations.push(incoming);
      targetView.meta = {...targetView.meta, ...incoming};
    },
    renderAgentConsole:() => {},
    scheduleAgentConsoleRead:() => { scheduledReads += 1; },
    showNotice:(message, error) => notices.push({message, error}),
  };
  vm.createContext(context);
  vm.runInContext(production, context);

  const inputSend = context.flushAgentConsoleInput(view, "owner", "surface");
  await firstPromptStarted;
  view.inputQueue.push(secondPrompt, thirdPrompt);

  const stop = context.stopAgentConsoleResponse();
  await abortStarted;
  assert.deepEqual(
    calls.map(call => [call.command, call.message || ""]),
    [["prompt", "A"], ["abort", ""]],
    "Stop response must dispatch immediately while the ordinary prompt POST is unresolved",
  );
  assert.deepEqual(
    view.inputQueue,
    [secondPrompt, thirdPrompt],
    "the out-of-band abort must not consume or reorder queued follow-up prompts",
  );
  assert.equal(view.inputSending, true);
  assert.equal(view.abortBusy, true);

  await context.stopAgentConsoleResponse();
  assert.equal(calls.length, 2, "a second click while abort is pending must not dispatch twice");

  resolveAbort({console:{
    protocol:"pi-rpc", startedAt:"2026-09-04T10:00:00Z", streaming:true,
  }});
  await stop;
  assert.equal(view.abortBusy, false);
  assert.equal(view.abortRequest, null);
  assert.equal(reconciliations.length, 1);
  assert.equal(scheduledReads, 1, "the response stop must always resume output polling");
  assert.deepEqual(notices, []);

  rejectFirstPrompt(new Error("deferred prompt failed"));
  await inputSend;
  assert.deepEqual(
    view.inputQueue,
    [firstPrompt, secondPrompt, thirdPrompt],
    "the ordinary sender must restore its failed prompt ahead of untouched follow-ups",
  );
  assert.equal(view.inputRetryPending, true);
}

async function testPiResponseStopSkipsSupersededGeneration() {
  const production = sourceBetween(
    "function agentConsoleResponseTargetIsCurrent(view, ownerRunId, surfaceId, startedAt)",
    "\nasync function flushAgentConsoleInput",
  );
  const view = {
    meta:{protocol:"pi-rpc", startedAt:"2026-09-04T10:00:00Z", streaming:true},
    inputQueue:[], abortBusy:false, abortRequest:null, readDrainRemaining:0,
  };
  const state = {
    agentConsoleMeta:view.meta,
    agentConsoleViews:{surface:view},
    agentConsoleOwnerRunId:"owner",
    agentConsoleSurfaceId:"surface",
  };
  let resolveAbort;
  let markAbortStarted;
  let reconciliations = 0;
  let scheduledReads = 0;
  const abortStarted = new Promise(resolve => { markAbortStarted = resolve; });
  const context = {
    AgentConsoleTabsCore,
    JSON,
    Boolean,
    String,
    state,
    console,
    api:() => {
      markAbortStarted();
      return new Promise(resolve => { resolveAbort = resolve; });
    },
    agentConsoleUsesStructuredPi:() => true,
    currentAgentConsoleView:() => view,
    queueAgentConsoleInput:() => {},
    reconcileAgentConsoleViewMeta:() => { reconciliations += 1; },
    renderAgentConsole:() => {},
    scheduleAgentConsoleRead:() => { scheduledReads += 1; },
    showNotice:() => {},
  };
  vm.createContext(context);
  vm.runInContext(production, context);

  const stop = context.stopAgentConsoleResponse();
  await abortStarted;
  view.meta = {...view.meta, startedAt:"2026-09-04T10:01:00Z"};
  resolveAbort({console:{
    protocol:"pi-rpc", startedAt:"2026-09-04T10:00:00Z", streaming:true,
  }});
  await stop;

  assert.equal(reconciliations, 0, "an old abort response must not alter a restarted process view");
  assert.equal(view.meta.startedAt, "2026-09-04T10:01:00Z");
  assert.equal(view.abortBusy, false);
  assert.equal(scheduledReads, 1, "a stale abort completion must still request fresh output");
}

function testProductionComposerValidation(protocol = "pi-rpc") {
  const production = sourceBetween(
    "function queueAgentConsoleInput(value)",
    "\nfunction agentConsoleKeyData",
  );
  const calls = {focus:0, queued:[], reports:0, retries:0, savedDrafts:0};
  const view = {
    meta:{protocol, commands:[{name:"help"}, {name:"stats"}]}, timelineLoaded:true,
    inputQueue:[], inputError:"", inputRetryPending:false,
  };
  const input = {
    value:`${"🙂".repeat(16_320)}a`, disabled:false, validity:"",
    setCustomValidity(value) { this.validity = value; },
    reportValidity() { calls.reports += 1; return false; },
    focus() { calls.focus += 1; },
  };
  const elements = {
    agentConsoleInput:input,
    agentPiTimelineViewport:{focus() { calls.focus += 1; }},
    agentTerminalViewport:{focus() { calls.focus += 1; }},
  };
  const state = {
    agentConsoleOwnerRunId:"owner", agentConsoleSurfaceId:"surface",
  };
  const context = {
    saveAgentConsoleDraft:() => { calls.savedDrafts += 1; },
    AgentConsoleInputCore,
    PiTimelineCore,
    state,
    console,
    currentAgentConsoleView:() => view,
    $:id => elements[id],
    renderAgentConsole:() => {},
  };
  vm.createContext(context);
  vm.runInContext(production, context);
  context.queueAgentConsoleInput = value => { calls.queued.push(value); };
  context.flushAgentConsoleInput = () => { calls.retries += 1; };

  assert.equal(context.submitAgentConsoleInput(), false);
  assert.equal(input.value.length > 0, true, "oversized text must remain in the composer");
  assert.deepEqual(calls.queued, []);
  assert.equal(calls.reports, 1);
  assert.match(input.validity, /has not been cleared/);

  input.value = "valid 🙂 message";
  assert.equal(context.submitAgentConsoleInput(), true);
  assert.deepEqual(
    JSON.parse(JSON.stringify(calls.queued)),
    [{command:"prompt", message:"valid 🙂 message"}],
  );
  assert.equal(input.value, "", "validated text clears only after it is safely queued");

  const retained = {command:"prompt", message:"earlier failed user prompt"};
  view.inputQueue = [retained];
  view.inputRetryPending = true;
  const queuedBefore = calls.queued.length;
  const draftsBefore = calls.savedDrafts;
  input.value = "  /resume synthetic-session  ";
  assert.equal(context.submitAgentConsoleInput(), false);
  assert.equal(input.value, "  /resume synthetic-session  ", "an unavailable command remains editable in the composer");
  assert.equal(input.disabled, false);
  assert.equal(calls.queued.length, queuedBefore, "an unsupported slash command never enters the local FIFO");
  assert.deepEqual(view.inputQueue, [retained], "prevalidation must not drop an earlier failed user prompt");
  assert.equal(view.inputRetryPending, true, "prevalidation leaves the existing retry queue intact");
  assert.equal(calls.savedDrafts, draftsBefore, "rejecting a command must not erase its saved draft");
  assert.match(input.validity, /\/resume is not available/);
  assert.match(input.validity, protocol === "omp-rpc" ? /oh-my-pi/ : /Pi/);
  input.value = "/";
  assert.equal(context.submitAgentConsoleInput(), false);
  assert.match(input.validity, /Choose a command/);
  for (const message of ["/help", " /stats with synthetic arguments ", "/tmp/synthetic-file.txt"]) {
    input.value = message;
    assert.equal(context.submitAgentConsoleInput(), true, "known commands and ordinary absolute paths remain accepted");
    assert.equal(calls.queued.at(-1).message, message);
    assert.equal(input.value, "");
  }

  view.inputQueue = [{command:"prompt", message:"retry me"}];
  view.inputRetryPending = true;
  view.inputError = "temporary failure";
  view.meta.queuePaused = true;
  view.meta.pendingMessages = 1;
  const commandsBeforeRetry = calls.queued.length;
  assert.equal(context.submitAgentConsoleInput(), true);
  assert.equal(calls.retries, 1, "empty composer submit provides an explicit retry path");
  assert.equal(calls.queued.length, commandsBeforeRetry, "local Retry send takes priority over resuming the server queue");
  assert.deepEqual(view.inputQueue, [{command:"prompt", message:"retry me"}]);
}

function testProductionPausedQueueResume(protocol) {
  const production = sourceBetween(
    "function queueAgentConsoleInput(value)",
    "\nfunction agentConsoleKeyData",
  );
  const saved = {id:"server:0", message:"synthetic saved follow-up", editable:true};
  const view = {meta:{protocol, queuePaused:true, pendingMessages:1, queuedMessages:[saved]},
    inputQueue:[], inputInFlightItems:[], inputSending:false, inputRetryPending:false, inputError:""};
  const input = {value:"", disabled:false, setCustomValidity() {}};
  let flushes = 0, drafts = 0;
  const context = vm.createContext({AgentConsoleInputCore, AgentConsoleTabsCore, PiTimelineCore,
    state:{agentConsoleOwnerRunId:"owner", agentConsoleSurfaceId:"surface"},
    currentAgentConsoleView:()=>view, renderAgentConsole() {},
    saveAgentConsoleDraft:()=>{ drafts += 1; },
    $:id=>id === "agentConsoleInput" ? input : {focus() {}},
  });
  vm.runInContext(production, context);
  context.flushAgentConsoleInput = ()=>{ flushes += 1; };
  assert.equal(context.submitAgentConsoleInput(), true);
  assert.deepEqual(JSON.parse(JSON.stringify(view.inputQueue)), [{command:"resume_queue"}],
    "empty Send resumes the server queue without copying or duplicating its saved message");
  assert.equal(flushes, 1);
  assert.equal(context.submitAgentConsoleInput(), false, "a second click cannot duplicate a queued resume action");
  assert.equal(flushes, 1);
  view.inputInFlightItems = view.inputQueue.splice(0);
  assert.equal(context.submitAgentConsoleInput(), false, "a resume already in flight is not sent twice");
  assert.deepEqual(view.meta.queuedMessages, [saved]);
  assert.equal(input.value, "");
  assert.equal(drafts, 0);
  view.inputInFlightItems = [];
  view.meta.queuePaused = false;
  assert.equal(context.submitAgentConsoleInput(), false, "an ordinary empty Send never resumes an active queue");
  view.meta.queuePaused = true;
  view.meta.pendingMessages = 0;
  assert.equal(context.submitAgentConsoleInput(), false, "an empty server queue remains idle");
  view.meta.pendingMessages = 1;
  view.meta.protocol = "terminal";
  assert.equal(context.submitAgentConsoleInput(), false, "terminal input keeps its existing empty-send behavior");
}

function agentConsoleReadRaceHarness({control = "", currentStartedAt = "2026-09-04T10:00:00Z"} = {}) {
  const readProduction = sourceBetween(
    "function scheduleAgentConsoleRead(",
    "\nfunction queueAgentConsoleInput(value)",
  );
  const controlProduction = sourceBetween(
    "async function stopAgentConsoleSurface(attachment = null)",
    '\nlisten($("hubFanMode"),',
  );
  const target = {
    id:"surface", surfaceId:"surface", ownerRunId:"owner", agentHost:"console",
  };
  const writes = [];
  const resets = {terminal:0, timeline:0};
  const scheduled = [];
  const notices = [];
  let timerCalls = 0;
  const timers = [], cancelledTimers = [];
  let resolveRead;
  let markReadStarted;
  const readStarted = new Promise(resolve => { markReadStarted = resolve; });
  const view = {
    meta:{
      protocol:"pi-rpc", startedAt:currentStartedAt, state:"running",
      bufferBaseOffset:0, bufferEnd:10, nextOffset:10,
    },
    terminal:{write:value => writes.push(value)},
    decoder:new TextDecoder("utf-8", {fatal:false}),
    offset:10,
    seenEnd:10,
    loaded:true,
    recovering:false,
    inputQueue:[],
    inputSending:false,
    readDrainRemaining:0,
    postmortem:null,
    timeline:PiTimelineCore.emptyTimeline(),
    timelineSeenRevision:0,
    timelineLoaded:true,
    piFollowTail:true,
    piNewOutput:false,
  };
  const state = {
    agentConsoleBusy:false,
    agentConsoleMeta:view.meta,
    agentConsoleOwnerRunId:"owner",
    agentConsoleReadGeneration:0,
    agentConsoleReading:false,
    agentConsoleSurfaceId:"surface",
    agentConsoleTimer:null,
    agentConsoleVisible:true,
    agentConsoleViews:{surface:view},
    runPhase:"running",
    runStatus:null,
    sessionDashboard:null,
  };
  const controlConsole = control === "restart" ? {
    protocol:"pi-rpc", startedAt:"2026-09-04T10:01:00Z", state:"running",
    bufferBaseOffset:0, bufferEnd:0, nextOffset:0,
  } : {
    protocol:"pi-rpc", startedAt:currentStartedAt, state:"stopped",
    bufferBaseOffset:0, bufferEnd:10, nextOffset:10,
  };
  const elements = {
    agentConsoleStatus:{textContent:"", className:""},
    sessionDialog:{open:false},
  };
  const context = {
    AgentConsoleInputCore,
    AgentConsoleTabsCore,
    PiTimelineCore,
    JSON,
    Math,
    Number,
    TextDecoder,
    Uint8Array,
    atob,
    document:{hidden:false}, disposed:false,
    navigation:{refreshSessions:async()=>{}}, onHubStatus:()=>null,
    clearTimeout:id => cancelledTimers.push(id),
    setTimeout:(callback,delay) => { timers.push({callback,delay}); timerCalls += 1; return timerCalls; },
    state,
    console,
    $:id => elements[id] || (elements[id] = {}),
    agentConsoleBufferEnd:meta => AgentConsoleTabsCore.safeOffset(
      meta?.bufferEnd ?? meta?.nextOffset,
    ),
    agentConsoleShowsPiTimeline:targetView => targetView?.timelineLoaded === true,
    agentConsoleUsesStructuredPi:targetView => targetView?.meta?.protocol === "pi-rpc",
    api:endpoint => {
      if (endpoint === "/api/agent-console/read") {
        markReadStarted();
        return new Promise(resolve => { resolveRead = resolve; });
      }
      if (endpoint === `/api/agent-console/${control}`) {
        return Promise.resolve({hub:null, console:controlConsole});
      }
      return Promise.reject(new Error(`Unexpected endpoint: ${endpoint}`));
    },
    currentAgentConsoleAttachment:() => target,
    currentAgentConsoleView:() => state.agentConsoleViews[state.agentConsoleSurfaceId] || null,
    loadSessionDashboard:() => Promise.resolve(),
    persistAgentConsoleRecovery:() => {},
    reconcileAgentConsoleViewMeta:(targetView, incoming) => {
      const result = AgentConsoleTabsCore.reconcileConsoleMeta(targetView.meta, incoming);
      targetView.meta = result.meta;
      return result;
    },
    renderAgentConsole:() => {},
    renderAgentPiTimeline:() => {},
    renderAgentTerminalOutput:() => {},
    resetAgentConsoleTerminal:(targetView, baseOffset = 0) => {
      resets.terminal += 1;
      targetView.terminalSuppressed = false;
      targetView.decoder = new TextDecoder("utf-8", {fatal:false});
      targetView.offset = AgentConsoleTabsCore.safeOffset(baseOffset);
      targetView.loaded = false;
    },
    resetAgentPiTimeline:targetView => {
      resets.timeline += 1;
      targetView.timeline = PiTimelineCore.emptyTimeline();
      targetView.timelineLoaded = false;
    },
    scheduleAgentConsoleResize:() => {},
    showNotice:(message, error) => notices.push({message, error}),
    syncAgentConsoleViews:() => {},
    leaveAgentConsole:() => {},
  };
  vm.createContext(context);
  vm.runInContext(`${readProduction}\n${controlProduction}`, context);

  state.agentConsoleBusy = true;
  context.scheduleAgentConsoleRead(0);
  assert.equal(timerCalls, 0, "a Hub control operation must suspend new output reads");
  state.agentConsoleBusy = false;
  const schedule = context.scheduleAgentConsoleRead;
  context.scheduleAgentConsoleRead = delay => scheduled.push(delay);

  return {
    context, controlConsole, notices, readStarted, resets, scheduled, state, target, view, writes,
    schedule, timers, cancelledTimers,
    resolveRead:value => resolveRead(value),
  };
}

function staleAgentConsoleRead(startedAt = "2026-09-04T10:00:00Z") {
  return {console:{
    protocol:"pi-rpc", startedAt, state:"running", streaming:true,
    bufferBaseOffset:0, bufferEnd:40, nextOffset:40,
    data:"U1RBTEU=",
    timelineVersion:1, timelineBaseRevision:1, timelineRevision:1,
    nextTimelineRevision:1, timelineReset:false,
    timelineEvents:[{
      revision:1, kind:"answer", itemId:"old-answer", operation:"replace", text:"stale answer",
    }],
  }};
}

async function testControlInvalidatesPendingRead(control) {
  const harness = agentConsoleReadRaceHarness({control});
  const pendingRead = harness.context.readAgentConsole();
  await harness.readStarted;
  assert.equal(harness.state.agentConsoleReading, true);

  const operation = control === "restart"
    ? harness.context.restartAgentConsoleSurface(harness.target)
    : harness.context.stopAgentConsoleSurface(harness.target);
  await operation;
  assert.equal(harness.state.agentConsoleReadGeneration, 1);
  assert.equal(harness.state.agentConsoleReading, false);
  assert.deepEqual(harness.scheduled, [0], `${control} must resume polling after its control request settles`);

  harness.resolveRead(staleAgentConsoleRead());
  await pendingRead;
  assert.deepEqual(harness.writes, [], `${control} must not render terminal bytes from its superseded read`);
  assert.deepEqual(harness.view.timeline.items, [], `${control} must not restore stale semantic events`);
  assert.equal(harness.view.meta.state, control === "restart" ? "running" : "stopped");
  assert.equal(
    harness.view.meta.startedAt,
    control === "restart" ? harness.controlConsole.startedAt : "2026-09-04T10:00:00Z",
  );
  assert.equal(harness.view.readDrainRemaining, AgentConsoleTabsCore.FINAL_DRAIN_READS);
  assert.deepEqual(harness.notices, []);
}

async function testOlderServerGenerationIsDiscardedBeforeRendering() {
  const harness = agentConsoleReadRaceHarness({
    currentStartedAt:"2026-09-04T10:01:00Z",
  });
  const pendingRead = harness.context.readAgentConsole();
  await harness.readStarted;
  harness.resolveRead(staleAgentConsoleRead("2026-09-04T10:00:00Z"));
  await pendingRead;

  assert.deepEqual(harness.writes, [], "an older process generation must not write terminal bytes");
  assert.deepEqual(harness.view.timeline.items, [], "an older process generation must not alter the timeline");
  assert.equal(harness.view.offset, 10);
  assert.equal(harness.view.meta.startedAt, "2026-09-04T10:01:00Z");
  assert.deepEqual(harness.scheduled, [0], "discarding stale output must immediately request the current generation");
  assert.equal(harness.state.agentConsoleReading, false);
}

async function testSemanticPiSkipsTerminalAndRecoversFallback() {
  const h = agentConsoleReadRaceHarness();
  const read = async output => {
    const pending = h.context.readAgentConsole();
    h.resolveRead({console:output});
    await pending;
  };
  const output = {...staleAgentConsoleRead().console, data:"invalid base64: must never be decoded",
    nextOffset:20, bufferEnd:1000, outputRevision:1000};
  await read(output);
  assert.equal(h.view.timeline.items[0].text,"stale answer");
  assert.equal(h.view.terminalSuppressed,true);
  assert.equal(h.view.offset,1000,"Skip raw backlog when semantic history is authoritative");
  assert.equal(h.resets.terminal,1,"Release the existing hidden emulator scrollback once");
  assert.deepEqual(h.writes,[]);
  await read({...output,nextOffset:1000});
  assert.equal(h.resets.terminal,1,"An unchanged semantic read must not allocate another emulator");

  // Losing protocol support must replay retained terminal history, not quietly
  // show an obsolete conversation or begin halfway through an ANSI/UTF-8 stream.
  const unsupported = {...output,timelineVersion:99,baseOffset:100,bufferBaseOffset:100,
    nextOffset:1000,data:Buffer.from("partial tail").toString("base64")};
  await read(unsupported);
  assert.equal(h.view.timelineLoaded,false);
  assert.equal(h.view.offset,100);
  assert.equal(h.view.loaded,false);
  assert.equal(h.scheduled.at(-1),0,"Fallback recovery requests a replay immediately");
  assert.deepEqual(h.writes,[]);
  await read({...unsupported,data:Buffer.from("complete retained terminal").toString("base64")});
  assert.deepEqual(h.writes,["complete retained terminal"]);
  assert.equal(h.view.offset,1000);
  assert.equal(h.view.loaded,true);
}

async function testIdleConsoleBackoffAndWake() {
  const h = agentConsoleReadRaceHarness();
  const read = async extra => {
    const pending = h.context.readAgentConsole();
    h.resolveRead({console:{protocol:"pi-rpc",startedAt:h.view.meta.startedAt,
      state:"running",streaming:false,compacting:false,pendingMessages:0,
      bufferBaseOffset:0,bufferEnd:10,nextOffset:10,data:"",
      timelineVersion:1,timelineBaseRevision:1,timelineRevision:0,
      nextTimelineRevision:0,timelineReset:false,timelineEvents:[],...extra}});
    await pending;
  };
  for (let i=0;i<5;i++) await read({});
  assert.equal(h.scheduled.at(-1),750,"The production reader recognises a settled Pi console");
  await read({compacting:true});
  assert.equal(h.scheduled.at(-1),120,"Compaction keeps polling fast even without a normal stream");
  assert.equal(h.view.readIdleCount,0);
  await read({timelineRevision:3,nextTimelineRevision:1,timelineEvents:[
    {revision:1,kind:"answer",text:"New output"},
  ]});
  assert.equal(h.scheduled.at(-1),0,"Semantic backlog drains immediately despite an empty terminal payload");

  h.state.agentConsoleTimer=99;
  h.view.readIdleCount=4;
  h.schedule(0,{wake:false});
  assert.deepEqual(h.cancelledTimers,[],"Periodic status renders must not defeat idle backoff");
  h.schedule(0);
  assert.deepEqual(h.cancelledTimers,[99]);
  assert.equal(h.timers.at(-1).delay,0,"User actions replace the pending idle timer immediately");
  assert.equal(h.view.readIdleCount,0);
  h.state.agentConsoleReading=true;
  const timerCount=h.timers.length;
  h.schedule(0);
  assert.equal(h.state.agentConsoleTimer,null);
  assert.equal(h.timers.length,timerCount,"A wake never overlaps an in-flight read");
}

assert.ok(index.indexOf('src="agent_console_input.js"') < index.indexOf('src="app.js"'));
assert.match(index, /id="agentConsoleInput"[^>]+maxlength="65280"/);
const flushSource = sourceBetween(
  "async function flushAgentConsoleInput(view, ownerRunId, surfaceId)",
  "\nfunction agentConsoleDimensions",
);
assert.match(flushSource, /restoreFailedBatch\(view\.inputQueue, activeBatch\)/);
assert.match(flushSource, /scheduleAgentConsoleRead\(0\)/);
assert.doesNotMatch(flushSource, /view\.inputQueue\s*=\s*\[\]/);
const readSource = sourceBetween(
  "async function readAgentConsole()",
  "\nfunction queueAgentConsoleInput(value)",
);
assert.match(readSource, /AgentConsoleTabsCore\.nextReadPlan\(/);
assert.match(readSource, /readGeneration === state\.agentConsoleReadGeneration/);
assert.match(readSource, /readGeneration !== state\.agentConsoleReadGeneration/);
assert.match(readSource, /if \(reconciliation\.stale\)/);
const responseStopSource = sourceBetween(
  "async function stopAgentConsoleResponse()",
  "\nasync function flushAgentConsoleInput",
);
assert.match(responseStopSource, /command:"abort"/);
assert.doesNotMatch(responseStopSource, /inputQueue/);
const consoleRenderSource = sourceBetween(
  "function renderAgentConsole()",
  "\nfunction updateAgentWorkspace",
);
assert.match(consoleRenderSource, /abortBusy\s+\? "Stopping…"/);
assert.match(consoleRenderSource, /!activelyResponding \|\| abortBusy/);
assert.match(app, /listen\(\$\("agentConsoleInterruptButton"\), "click", \(\) => \{\s+void stopAgentConsoleResponse\(\)/);

Promise.resolve()
  .then(testProductionFailureOrdering)
  .then(testPiResponseStopBypassesDeferredPromptQueue)
  .then(testPiResponseStopSkipsSupersededGeneration)
  .then(testProductionComposerValidation)
  .then(() => testProductionComposerValidation("omp-rpc"))
  .then(() => testProductionPausedQueueResume("pi-rpc"))
  .then(() => testProductionPausedQueueResume("omp-rpc"))
  .then(() => testControlInvalidatesPendingRead("stop"))
  .then(() => testControlInvalidatesPendingRead("restart"))
  .then(testOlderServerGenerationIsDiscardedBeforeRendering)
  .then(testSemanticPiSkipsTerminalAndRecoversFallback)
  .then(testIdleConsoleBackoffAndWake)
  .then(() => console.log("Reliable Pi Hub input validation, queue ordering, and stale-read recovery passed."))
  .catch(error => {
    console.error(error);
    process.exitCode = 1;
  });

assert.equal(AgentConsoleInputCore.validatePiPrompt('"'.repeat(40000)).ok, false, 'JSON escaping counts toward the transport limit');
assert.equal(AgentConsoleInputCore.validatePiPrompt('line\n'.repeat(5000)).ok, true, 'multiline messages remain valid within the encoded budget');
