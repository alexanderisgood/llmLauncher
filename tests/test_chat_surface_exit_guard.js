"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");

function sourceBetween(startMarker, endMarker) {
  const start = app.indexOf(startMarker);
  const end = app.indexOf(endMarker, start + startMarker.length);
  assert.ok(start >= 0, `missing production marker: ${startMarker}`);
  assert.ok(end > start, `missing production end marker: ${endMarker}`);
  return app.slice(start, end);
}

const production = [
  sourceBetween("function leaveAgentConsole()", "\nfunction currentAgentConsoleAttachment"),
  sourceBetween("async function saveChatBeforeSurfaceExit(retryAction)", "\nasync function newChat"),
  sourceBetween("async function enterChatSurface(attachment, options = {})", "\nasync function attachSessionSurface"),
  sourceBetween("async function attachSessionSurface()", "\nasync function detachChatSurface"),
  sourceBetween("async function detachChatSurface(attachment)", "\nasync function endCurrentChatSurface"),
  sourceBetween("async function endCurrentChatSurface()", "\nfunction renderSessionDashboard"),
  sourceBetween("async function stopRun()", "\nfunction profileRunBlocked"),
].join("\n");

function createHarness({
  saveResult = true,
  storageResult = true,
  attachmentRequest = {client:"chat", agentHost:"launcher"},
} = {}) {
  const calls = {
    abort:0, activate:[], api:[], clear:[], focus:0, loadDashboard:0,
    persistConsole:0, persistQueue:0, persistSession:0, polls:[], reset:0,
    retained:[],
    save:[], setBusy:0, enterConsole:[],
  };
  const elements = {
    chatInput:{value:"", focus() { calls.focus += 1; }},
    chatRunSettingsPanel:{hidden:true},
    sessionDialog:{open:false, close() {}},
  };
  const state = {
    agentConsoleDismissed:false,
    agentConsoleTimer:null,
    agentConsoleVisible:true,
    chatAbort:null,
    chatAttachment:{
      id:"surface-1", ownerRunId:"owner-1", client:"chat", primary:true, canDetach:true,
    },
    chatDraftKey:"surface:surface-1:history:current",
    chatHistoryId:"current-history",
    chatHistoryBusyId:"",
    chatHistoryLoading:false,
    chatMessages:[
      {role:"user", content:"Keep me"},
      {role:"assistant", content:"Saved response"},
    ],
    chatOwnerRunId:"owner-1",
    chatPostmortem:null,
    chatAttachmentObserved:true,
    chatQueue:[],
    chatQueuePaused:false,
    chatQueueRecovered:false,
    chatRunId:"surface-1",
    chatRunSettings:null,
    chatRunSettingsKey:"",
    chatTurnSettlement:null,
    runPhase:"running",
    runStatus:{run:{runId:"owner-1", client:"chat"}},
    sessionAttachmentPlan:{ready:true},
    sessionAttachmentSignature:"signature",
    sessionDashboard:{hub:{}},
  };
  const context = {
    JSON,
    Promise,
    console,
    state,
    $:id => elements[id] || (elements[id] = {}),
    activateChatDraft:(surfaceId, options) => calls.activate.push({surfaceId, options}),
    api:async (endpoint, options = {}) => {
      calls.api.push({endpoint, body:options.body || ""});
      if (endpoint === "/api/session/attach") {
        const request = JSON.parse(options.body || "{}");
        return {
          hub:{phase:"running", attachments:[]},
          attachment:request.client === "chat" ? {
            id:"surface-2", ownerRunId:"owner-1", client:"chat",
            primary:false, canDetach:true,
          } : {
            id:"surface-pi", ownerRunId:"owner-1", client:request.client,
            agentHost:request.agentHost, surface:"Pi", primary:false, canDetach:true,
          },
        };
      }
      if (endpoint === "/api/session/detach") return {hub:{phase:"running", attachments:[]}};
      if (endpoint === "/api/stop") return {ok:true};
      throw new Error(`unexpected endpoint ${endpoint}`);
    },
    clearChatTurnCheckpoint:async checkpoint => {
      calls.clear.push({...checkpoint});
      return true;
    },
    closeChatRunSettings:() => {},
    enterAgentConsole:attachment => { calls.enterConsole.push({...attachment}); },
    loadSessionDashboard:async () => { calls.loadDashboard += 1; },
    persistAgentConsoleRecovery:() => { calls.persistConsole += 1; },
    saveAgentConsoleDraft:() => {},
    persistChatQueue:() => { calls.persistQueue += 1; },
    persistChatSessionState:() => {
      calls.persistSession += 1;
      return storageResult;
    },
    pollAcquisitionStatus:async () => { calls.polls.push("acquisition"); },
    pollAneCloneStatus:async () => { calls.polls.push("ane-clone"); },
    pollAneStatus:async () => { calls.polls.push("ane"); },
    pollBenchmarkStatus:async () => { calls.polls.push("benchmark"); },
    pollRouteCheckStatus:async () => { calls.polls.push("route-check"); },
    pollRuntimeUpdateStatus:async () => { calls.polls.push("runtime"); },
    pollSetupStatus:async () => { calls.polls.push("setup"); },
    pollStatus:async () => { calls.polls.push("status"); },
    renderChatDraftStatus:() => {},
    renderChatMessages:() => {},
    renderSessionAttachmentPanel:() => {},
    requestAnimationFrame:callback => { callback(); return 1; },
    resetChatConversation:() => {
      calls.reset += 1;
      state.chatMessages = [];
      state.chatHistoryId = "";
      state.chatDraftKey = "";
    },
    retainChatPostmortem:(phase, message, options = {}) => {
      const marker = {state:phase === "failed" ? "failed" : "stopped", phase, message, ...options};
      calls.retained.push(marker);
      state.chatPostmortem = marker;
      return marker;
    },
    saveChatBeforeNavigation:async (retryAction, options = {}) => {
      calls.save.push({retryAction, options:{...options}});
      return saveResult;
    },
    sessionAttachmentRequest:() => ({...attachmentRequest}),
    setChatBusy:() => { calls.setBusy += 1; },
    showNotice:() => {},
    sizeChatInput:() => {},
    updateAgentWorkspace:() => {},
    updateChatWorkspace:() => {},
  };
  vm.createContext(context);
  vm.runInContext(production, context);
  return {calls, context, state};
}

async function flushMicrotasks() {
  await Promise.resolve();
  await Promise.resolve();
}

async function run() {
  const blockedEnter = createHarness({saveResult:false});
  const originalAttachment = blockedEnter.state.chatAttachment;
  const entered = await blockedEnter.context.enterChatSurface({
    id:"surface-2", ownerRunId:"owner-1", client:"chat", primary:false,
  });
  assert.equal(entered, false);
  assert.equal(blockedEnter.state.chatRunId, "surface-1");
  assert.equal(blockedEnter.state.chatAttachment, originalAttachment);
  assert.equal(blockedEnter.calls.reset, 0);
  assert.equal(blockedEnter.calls.api.length, 0);
  assert.match(blockedEnter.calls.save[0].retryAction, /open that Chat surface again/);

  const blockedAttach = createHarness({saveResult:false});
  await blockedAttach.context.attachSessionSurface();
  assert.equal(
    blockedAttach.calls.api.length, 0,
    "save must finish before the backend creates an attachment",
  );
  assert.match(blockedAttach.calls.save[0].retryAction, /open that work surface again/);

  const attached = createHarness({saveResult:true});
  await attached.context.attachSessionSurface();
  assert.deepEqual(attached.calls.api.map(call => call.endpoint), ["/api/session/attach"]);
  assert.equal(
    attached.calls.save.length, 1,
    "the pre-API save must not repeat after attachment creation",
  );
  assert.equal(attached.state.chatRunId, "surface-2");

  const consoleAttach = createHarness({
    saveResult:false,
    attachmentRequest:{client:"pi", agentHost:"console"},
  });
  const consoleMessages = JSON.parse(JSON.stringify(consoleAttach.state.chatMessages));
  consoleAttach.state.chatAbort = {abort() { consoleAttach.calls.abort += 1; }};
  await consoleAttach.context.attachSessionSurface();
  assert.deepEqual(consoleAttach.calls.api.map(call => call.endpoint), ["/api/session/attach"]);
  assert.equal(consoleAttach.calls.save.length, 0, "Hub Console attach must not run the Chat exit guard");
  assert.equal(consoleAttach.calls.abort, 0, "Hub Console attach must not abort the active Chat turn");
  assert.equal(consoleAttach.state.chatRunId, "surface-1");
  assert.deepEqual(consoleAttach.state.chatMessages, consoleMessages);
  assert.equal(consoleAttach.calls.enterConsole.length, 1);

  const blockedDetach = createHarness({saveResult:false});
  blockedDetach.state.chatAttachment.primary = false;
  const detached = await blockedDetach.context.endCurrentChatSurface();
  assert.equal(detached, false);
  assert.equal(blockedDetach.state.chatRunId, "surface-1");
  assert.equal(blockedDetach.calls.reset, 0);
  assert.equal(blockedDetach.calls.api.length, 0, "a failed save must block the detach request");
  assert.match(blockedDetach.calls.save[0].retryAction, /end this attached chat again/);

  const blockedStop = createHarness({saveResult:false});
  const stopped = await blockedStop.context.endCurrentChatSurface();
  assert.equal(stopped, false);
  assert.equal(blockedStop.calls.api.length, 0, "a failed save must block the primary Stop request");
  assert.equal(blockedStop.state.chatRunId, "surface-1");
  assert.match(blockedStop.calls.save[0].retryAction, /stop this model session again/);

  const blockedLocalStorage = createHarness({saveResult:true, storageResult:false});
  blockedLocalStorage.context.$("chatInput").value = "typed immediately before Stop";
  const localStorageStop = await blockedLocalStorage.context.endCurrentChatSurface();
  assert.equal(localStorageStop, false);
  assert.equal(blockedLocalStorage.calls.api.length, 0);
  assert.equal(
    blockedLocalStorage.calls.save.length, 0,
    "history save cannot rescue an unsaved composer draft",
  );
  assert.equal(blockedLocalStorage.calls.abort, 0);
  assert.equal(blockedLocalStorage.state.chatRunId, "surface-1");

  const historyOperation = createHarness({saveResult:true});
  historyOperation.state.chatHistoryBusyId = "current-history";
  const historyBlockedStop = await historyOperation.context.endCurrentChatSurface();
  assert.equal(historyBlockedStop, false);
  assert.equal(historyOperation.calls.api.length, 0);
  assert.equal(historyOperation.calls.save.length, 0);
  assert.equal(historyOperation.state.chatRunId, "surface-1");

  let settleTurn;
  const active = createHarness({saveResult:false});
  const turn = {
    surfaceId:"surface-1",
    exitRequested:false,
    promise:new Promise(resolve => { settleTurn = resolve; }),
  };
  active.state.chatTurnSettlement = turn;
  active.state.chatAbort = {abort() { active.calls.abort += 1; }};
  active.state.chatQueue = [{id:"queued-1", content:"wait"}];
  const stopping = active.context.endCurrentChatSurface();
  await flushMicrotasks();
  assert.equal(turn.exitRequested, true);
  assert.equal(active.calls.abort, 1);
  assert.equal(active.state.chatQueuePaused, true);
  assert.equal(active.calls.persistQueue, 1);
  assert.equal(active.calls.api.length, 0, "Stop must wait for the active turn finalizer");
  settleTurn({surfaceId:"surface-1", historySaved:true, checkpointPersisted:false, checkpoint:null});
  assert.equal(await stopping, true);
  assert.deepEqual(active.calls.api.map(call => call.endpoint), ["/api/stop"]);
  assert.equal(active.calls.save.length, 0, "a successful turn-finalizer save must not be repeated");

  const recovered = createHarness({saveResult:true});
  recovered.state.chatAttachment.primary = false;
  recovered.state.chatTurnSettlement = {
    surfaceId:"surface-1",
    exitRequested:false,
    promise:Promise.resolve({
      surfaceId:"surface-1", historySaved:false, checkpointPersisted:true,
      checkpoint:{tabId:"tab-1", turnId:"turn-1"},
    }),
  };
  const recoveredDetach = await recovered.context.endCurrentChatSurface();
  assert.equal(recoveredDetach, true);
  assert.equal(recovered.calls.save.length, 1);
  assert.equal(recovered.calls.save[0].options.recoveryAvailable, true);
  assert.deepEqual(recovered.calls.clear, [{tabId:"tab-1", turnId:"turn-1"}]);
  assert.deepEqual(recovered.calls.api.map(call => call.endpoint), ["/api/session/detach"]);
  assert.equal(recovered.state.chatRunId, "surface-1");
  assert.equal(recovered.calls.reset, 0);
  assert.equal(recovered.calls.retained.length, 1);
  assert.equal(recovered.calls.retained[0].ended, true);
  assert.equal(recovered.state.chatMessages.length, 2);

  const nonChat = createHarness({saveResult:false});
  nonChat.state.chatRunId = "";
  nonChat.state.chatAttachment = null;
  nonChat.state.chatAbort = {abort() { nonChat.calls.abort += 1; }};
  assert.equal(await nonChat.context.stopRun(), true);
  assert.equal(nonChat.state.agentConsoleVisible, false, "ending a Hub session returns to the main screen");
  assert.equal(nonChat.state.agentConsoleDismissed, true, "polling must not reopen the ended Hub");
  assert.equal(nonChat.calls.abort, 1, "non-Chat Stop keeps its existing abort behavior");
  assert.equal(nonChat.calls.save.length, 0, "non-Chat Stop must not invoke Chat persistence");
  assert.deepEqual(nonChat.calls.api.map(call => call.endpoint), ["/api/stop"]);

  assert.match(app, /state\.chatTurnSettlement = turnSettlement/);
  assert.match(app, /silentFailure:turnSettlement\.exitRequested/);
  assert.match(app, /resolveTurnSettlement\(\{/);
  assert.match(app, /!turnSettlement\.exitRequested && ChatStreamCore\.shouldDrainQueue/);
  const launchSource = sourceBetween(
    "async function launch(requestOverride = null, launchOptions = {})",
    "\nfunction nextChatMessageId",
  );
  assert.ok(
    launchSource.indexOf("saveChatBeforeSurfaceExit")
      < launchSource.indexOf('api("/api/session/warm-attach"'),
    "warm attachment creation must follow the current Chat save guard",
  );

  console.log("Chat surface exit waits for active-turn recovery and blocks destructive transitions after save failure.");
}

run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
