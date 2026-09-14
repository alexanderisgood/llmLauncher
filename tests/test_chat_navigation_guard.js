"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const ChatStreamCore = require("../chat_stream.js");

function sourceBetween(startMarker, endMarker) {
  const start = app.indexOf(startMarker);
  const end = app.indexOf(endMarker, start + startMarker.length);
  assert.ok(start >= 0, `missing production marker: ${startMarker}`);
  assert.ok(end > start, `missing production end marker: ${endMarker}`);
  return app.slice(start, end);
}

const production = [
  sourceBetween("function chatHasPersistableTranscript()", "\nasync function newChat"),
  sourceBetween("async function newChat()", "\nfunction currentChatHistoryPayload"),
  sourceBetween("function currentChatHistoryPayload()", "\nfunction chatHistoryDate"),
  sourceBetween("async function openUnsavedChatDraft(key)", "\nfunction chatSurfaceRoute"),
  sourceBetween("async function openChatHistoryThread(historyId, options = {})", "\nasync function deleteChatHistoryThread"),
].join("\n");

function createHarness({messages, saveFails = false, deferFirstSave = false} = {}) {
  const calls = {
    activate:[], api:[], focus:0, notices:[], persist:0, renderHistory:0,
    renderMessages:0, renderRoute:0, renderSidebar:0, reset:0,
  };
  let releaseFirstSave = null;
  const firstSaveGate = deferFirstSave
    ? new Promise(resolve => { releaseFirstSave = resolve; }) : null;
  const chatInput = {
    isConnected:true,
    focus() { calls.focus += 1; },
  };
  const focused = {
    isConnected:true,
    focus() { calls.focus += 1; },
  };
  const elements = {
    chatInput,
    chatHistoryDialog:{open:false, close() {}},
  };
  const state = {
    chatAbort:null,
    chatActiveThread:null,
    chatAttachment:{model:"Current model", backend:"omlx", context:32768, output:4096, reasoning:"high"},
    chatBranch:null,
    chatContextBusy:false,
    chatContextFiles:[],
    chatContextReducedAt:0,
    chatDraftKey:"surface:surface-1:new:current",
    chatEditingMessageId:"",
    chatFollowOutput:false,
    chatHistoryBusyId:"",
    chatHistoryId:"",
    chatHistoryMutationTail:null,
    chatHistorySaving:false,
    chatHistoryThreads:[],
    chatMessages:messages || [],
    chatOwnerRunId:"owner-1",
    chatQueue:[],
    chatQueueEditingId:"",
    chatRevisionBusy:false,
    chatRunId:"surface-1",
    chatSidebarCollapsed:false,
    chatSidebarEditingId:"",
    chatSidebarMenuId:"",
    chatTranscriptActiveId:"",
    chatTranscriptQuery:"",
    chatTranscriptSearchOpen:false,
    chatWorkspaceContext:null,
    runPhase:"running",
    runStatus:{run:{runId:"owner-1", model:"Current model", backend:"omlx"}},
  };
  let generatedIds = 0;
  const context = {
    ChatStreamCore,
    JSON,
    console,
    document:{activeElement:focused},
    matchMedia:() => ({matches:false}),
    requestAnimationFrame:callback => { callback(); return 1; },
    state,
    $:id => elements[id] || (elements[id] = {open:false}),
    activateChatDraft:(surfaceId, options) => calls.activate.push({surfaceId, options}),
    api:async (endpoint, options = {}) => {
      calls.api.push({endpoint, body:options.body ? JSON.parse(options.body) : null});
      if (endpoint === "/api/chat/history/save") {
        if (saveFails) throw new Error("history store unavailable");
        const body = JSON.parse(options.body);
        const saveCalls = calls.api.filter(call => call.endpoint === "/api/chat/history/save");
        if (firstSaveGate && saveCalls.length === 1) await firstSaveGate;
        return {
          thread:{...body, title:"Saved chat"},
          threads:[{...body, title:"Saved chat"}],
        };
      }
      if (endpoint === "/api/chat/history/get") {
        return {
          thread:{
            id:"target-history", title:"Earlier chat", model:"Earlier model", backend:"lmstudio",
            messages:[],
          },
        };
      }
      throw new Error(`unexpected endpoint ${endpoint}`);
    },
    chatDraftSurfacePrefix:() => "surface:surface-1:",
    isPortableChatDraftKey:key => String(key || "").startsWith("surface:surface-1:new:"),
    chatThreadSummary:thread => ({id:thread.id, title:thread.title}),
    localUuid:() => `generated-history-${++generatedIds}`,
    migrateChatDraftToHistory:historyId => { calls.migrated = historyId; },
    normaliseChatMessage:message => ({...message}),
    persistChatSessionState:() => { calls.persist += 1; },
    renderChatHistory:() => { calls.renderHistory += 1; },
    renderChatMessages:() => { calls.renderMessages += 1; },
    renderChatRoute:() => { calls.renderRoute += 1; },
    renderChatSidebar:() => { calls.renderSidebar += 1; },
    renderQuickStart:() => {},
    resetChatConversation:() => {
      calls.reset += 1;
      state.chatMessages = [];
      state.chatHistoryId = "";
      state.chatDraftKey = "";
    },
    showNotice:(message, error = false) => calls.notices.push({message, error}),
    setChatBusy:() => {},
    sleep:() => new Promise(resolve => setTimeout(resolve, 0)),
  };
  vm.createContext(context);
  vm.runInContext(production, context);
  return {
    calls, context, focused, state,
    releaseFirstSave:() => { if (releaseFirstSave) releaseFirstSave(); },
  };
}

const currentMessages = [
  {id:"user-1", role:"user", content:"Keep this completed transcript", pending:false},
  {id:"assistant-1", role:"assistant", content:"It must remain visible", pending:false},
];

async function assertFailedNavigation(method, actionText) {
  const harness = createHarness({messages:currentMessages.map(message => ({...message})), saveFails:true});
  const {calls, context, state} = harness;
  const before = {
    messages:JSON.parse(JSON.stringify(state.chatMessages)),
    historyId:state.chatHistoryId,
    draftKey:state.chatDraftKey,
  };
  await method(context);
  assert.deepEqual(state.chatMessages, before.messages);
  assert.equal(state.chatHistoryId, before.historyId, "a failed save must not create a phantom history id");
  assert.equal(state.chatDraftKey, before.draftKey, "a failed save must not migrate the draft key");
  assert.equal(calls.reset, 0, "navigation must not reset the current transcript");
  assert.equal(calls.activate.length, 0, "navigation must not activate another draft");
  assert.equal(calls.api.filter(call => call.endpoint === "/api/chat/history/save").length, 1);
  assert.equal(calls.api.filter(call => call.endpoint === "/api/chat/history/get").length, 0);
  assert.equal(calls.focus, 1, "keyboard focus must return to the still-current chat");
  assert.equal(calls.notices.length, 1);
  assert.equal(calls.notices[0].error, true);
  assert.match(calls.notices[0].message, /Stayed in the current chat/);
  assert.match(calls.notices[0].message, actionText);
}

async function run() {
  await assertFailedNavigation(context => context.newChat(), /choose New chat again/);
  await assertFailedNavigation(
    context => context.openUnsavedChatDraft("surface:surface-1:new:other"),
    /open that unsent draft again/,
  );
  await assertFailedNavigation(
    context => context.openChatHistoryThread("target-history"),
    /open that saved chat again/,
  );

  const emptyNew = createHarness({messages:[], saveFails:true});
  await emptyNew.context.newChat();
  assert.equal(emptyNew.calls.api.length, 0, "an empty chat needs no history write");
  assert.equal(emptyNew.calls.reset, 1);

  const emptyDraft = createHarness({messages:[], saveFails:true});
  await emptyDraft.context.openUnsavedChatDraft("surface:surface-1:new:other");
  assert.equal(emptyDraft.calls.api.length, 0, "an empty chat may switch drafts without saving");
  assert.equal(emptyDraft.calls.reset, 1);
  assert.deepEqual(JSON.parse(JSON.stringify(emptyDraft.calls.activate)), [{
    surfaceId:"surface-1", options:{key:"surface:surface-1:new:other", restore:true},
  }]);

  const emptyHistory = createHarness({messages:[], saveFails:true});
  await emptyHistory.context.openChatHistoryThread("target-history");
  assert.deepEqual(
    emptyHistory.calls.api.map(call => call.endpoint),
    ["/api/chat/history/get"],
    "an empty chat may open saved history without a redundant save",
  );
  assert.equal(emptyHistory.state.chatHistoryId, "target-history");
  assert.equal(emptyHistory.calls.reset, 0);

  const serial = createHarness({
    messages:currentMessages.map(message => ({...message})),
    deferFirstSave:true,
  });
  const firstSave = serial.context.saveCurrentChatHistory();
  const secondSave = serial.context.saveCurrentChatHistory();
  await new Promise(resolve => setTimeout(resolve, 5));
  assert.equal(
    serial.calls.api.filter(call => call.endpoint === "/api/chat/history/save").length,
    1,
    "a second save must wait before constructing and submitting its payload",
  );
  serial.releaseFirstSave();
  await Promise.all([firstSave, secondSave]);
  const serialSaves = serial.calls.api.filter(call => call.endpoint === "/api/chat/history/save");
  assert.equal(serialSaves.length, 2);
  assert.equal(
    serialSaves[0].body.id, serialSaves[1].body.id,
    "serialized first saves must update one thread instead of creating duplicate IDs",
  );

  const doubleOpen = createHarness({
    messages:currentMessages.map(message => ({...message})),
    deferFirstSave:true,
  });
  const openingFirst = doubleOpen.context.openChatHistoryThread("target-history");
  const openingSecond = doubleOpen.context.openChatHistoryThread("second-history");
  await new Promise(resolve => setTimeout(resolve, 5));
  assert.deepEqual(
    doubleOpen.calls.api.map(call => call.endpoint),
    ["/api/chat/history/save"],
    "a second transcript selection must not enqueue another save or GET",
  );
  doubleOpen.releaseFirstSave();
  await Promise.all([openingFirst, openingSecond]);
  assert.deepEqual(
    doubleOpen.calls.api.map(call => call.endpoint),
    ["/api/chat/history/save", "/api/chat/history/get"],
  );
  assert.equal(doubleOpen.state.chatHistoryId, "target-history");
  assert.equal(doubleOpen.calls.activate.length, 1, "only the first requested target may activate");

  console.log("Chat navigation preserves unsaved transcripts and serializes first-save IDs without duplicates.");
}

run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
