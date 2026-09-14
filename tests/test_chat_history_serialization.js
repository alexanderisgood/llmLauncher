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
  sourceBetween("function setChatBusy(busy)", "\nfunction queueChatMessage"),
  sourceBetween("async function startChatTurn(content = \"\", options = {})", "\nasync function createChatBranch"),
  sourceBetween("function sendChat()", "\nfunction chatHasPersistableTranscript"),
  sourceBetween("async function runChatRevision(task)", "\nasync function trimChatToRecent"),
  sourceBetween("function currentChatHistoryPayload()", "\nfunction chatHistoryDate"),
  sourceBetween("async function recoverInterruptedChatTurn()", "\nasync function openChatHistory"),
  sourceBetween("async function deleteChatHistoryThread(historyId)", "\nfunction updateChatWorkspace"),
].join("\n");

function createHarness({saveRejects = false} = {}) {
  const historyId = "43e84f69-4476-4456-9a34-9e04ca90bd0c";
  const calls = {api:[], busy:[], draftMoves:0};
  let releaseSave;
  const saveGate = new Promise(resolve => { releaseSave = resolve; });
  let releaseHistory;
  const historyGate = new Promise(resolve => { releaseHistory = resolve; });
  const stored = new Map([[historyId, {id:historyId, title:"Active chat"}]]);
  const elements = {
    chatHistoryDialog:{open:false},
    chatHistoryStatus:{textContent:"", className:""},
    chatInput:{value:"must not send during delete", disabled:false},
    chatSendButton:{
      disabled:false,
      classList:{remove() {}},
      querySelector(selector) {
        if (!this.parts) this.parts = {strong:{textContent:""}, span:{textContent:""}};
        return selector === "strong" ? this.parts.strong : this.parts.span;
      },
    },
    chatStopButton:{disabled:false, classList:{toggle() {}}},
    chatComposerHint:{textContent:""},
    newChatButton:{disabled:false},
    chatSidebarNew:{disabled:false},
    chatHistoryButton:{disabled:false},
  };
  const state = {
    chatAbort:null,
    chatActiveThread:{id:historyId, title:"Active chat"},
    chatAttachment:{model:"Test model", backend:"omlx", context:32768, output:4096, reasoning:"high"},
    chatBranch:null,
    chatContextBusy:false,
    chatDraftKey:`history:${historyId}`,
    chatEditingMessageId:"",
    chatHistoryBusyId:"",
    chatHistoryDeleteConfirmId:historyId,
    chatHistoryEditingId:"",
    chatHistoryId:historyId,
    chatHistoryLoaded:false,
    chatHistoryLoading:false,
    chatHistoryMutationTail:null,
    chatHistorySaving:false,
    chatHistoryThreads:[{id:historyId, title:"Active chat"}],
    chatMessages:[
      {id:"u1", role:"user", content:"Keep me ordered", pending:false},
      {id:"a1", role:"assistant", content:"Ordered", pending:false},
    ],
    chatOwnerRunId:"owner-1",
    chatQueue:[],
    chatQueueEditingId:"",
    chatQueuePaused:false,
    chatRevisionBusy:false,
    chatRunId:"surface-1",
    chatSidebarEditingId:"",
    chatSidebarMenuId:"",
    chatTurnRecoveryChecked:true,
    runPhase:"running",
    runStatus:{run:{runId:"owner-1", model:"Test model", backend:"omlx"}},
  };
  const context = {
    ChatStreamCore,
    CHAT_DRAFT_OPTIONS:{},
    JSON,
    console,
    state,
    $:id => elements[id] || (elements[id] = {}),
    api:async (endpoint, options = {}) => {
      const body = options.body ? JSON.parse(options.body) : null;
      calls.api.push({endpoint, body});
      if (endpoint === "/api/chat/history/save") {
        await saveGate;
        if (saveRejects) throw new Error("simulated save failure");
        stored.set(body.id, {...body, title:"Active chat"});
        return {thread:{...body, title:"Active chat"}, threads:[...stored.values()]};
      }
      if (endpoint === "/api/chat/history/delete") {
        stored.delete(body.id);
        return {threads:[...stored.values()]};
      }
      if (endpoint === "/api/chat/history") {
        await historyGate;
        return {threads:[{id:"stale-list", title:"Older snapshot"}]};
      }
      throw new Error(`unexpected endpoint ${endpoint}`);
    },
    ChatDraftsCore:{moveDraft:envelope => { calls.draftMoves += 1; return envelope; }},
    localUuid:() => "79950282-42c4-4a09-b5a7-2f73e781d268",
    migrateChatDraftToHistory:() => {},
    migrateChatQueueKey:() => {},
    newChatDraftKey:() => "draft:79950282-42c4-4a09-b5a7-2f73e781d268",
    readChatDraftEnvelope:() => ({version:1, activeKey:"", drafts:{}}),
    renderChatHistory:() => {},
    renderChatMessages:() => {},
    renderChatContextPack:() => {},
    renderChatDraftStatus:() => {},
    renderChatQueue:() => {},
    renderChatRoute:() => {},
    renderChatSidebar:() => {},
    renderQuickStart:() => {},
    restorePendingChatDraftConversation:async () => {},
    showNotice:() => {},
    writeChatDraftEnvelope:() => true,
  };
  vm.createContext(context);
  vm.runInContext(production, context);
  return {
    calls, context, elements, historyId, releaseHistory, releaseSave, state, stored,
  };
}

async function run() {
  const harness = createHarness();
  const saving = harness.context.saveCurrentChatHistory();
  const deleting = harness.context.deleteChatHistoryThread(harness.historyId);

  assert.equal(harness.elements.chatInput.disabled, true, "history work must visibly disable the composer");
  assert.equal(harness.elements.chatSendButton.disabled, true);
  assert.match(harness.elements.chatComposerHint.textContent, /history change/);
  const directStart = await harness.context.startChatTurn("must not start during delete");
  assert.equal(directStart, false, "startChatTurn itself must enforce the history-operation lock");
  let revisionRuns = 0;
  await harness.context.runChatRevision(async () => { revisionRuns += 1; });
  assert.equal(revisionRuns, 0, "branch and retry actions must not mutate a transcript during delete");
  harness.context.sendChat();
  assert.equal(harness.state.chatMessages.length, 2, "the composer must not append during delete");
  assert.equal(harness.state.chatHistoryBusyId, harness.historyId);
  assert.deepEqual(
    harness.calls.api.map(call => call.endpoint),
    ["/api/chat/history/save"],
    "delete must wait behind the already-claimed save",
  );

  harness.releaseSave();
  await Promise.all([saving, deleting]);
  assert.deepEqual(
    harness.calls.api.map(call => call.endpoint),
    ["/api/chat/history/save", "/api/chat/history/delete"],
  );
  assert.equal(harness.stored.has(harness.historyId), false, "the completed save must not resurrect the deleted ID");
  assert.equal(harness.state.chatHistoryId, "", "deleting the active record must detach its history identity");
  assert.equal(harness.calls.draftMoves, 1, "the active draft must move exactly once");
  assert.equal(harness.calls.api.filter(call => call.endpoint === "/api/chat/history/save").length, 1);
  assert.equal(harness.state.chatHistoryBusyId, "");
  assert.equal(harness.state.chatHistorySaving, false);
  assert.equal(harness.state.chatHistoryMutationTail, null);
  assert.equal(harness.elements.chatInput.disabled, false, "the composer must recover after history work");
  assert.equal(harness.elements.chatSendButton.disabled, false);

  const failed = createHarness({saveRejects:true});
  const failedSave = failed.context.saveCurrentChatHistory({silentFailure:true});
  const deleteAfterFailure = failed.context.deleteChatHistoryThread(failed.historyId);
  assert.deepEqual(failed.calls.api.map(call => call.endpoint), ["/api/chat/history/save"]);
  failed.releaseSave();
  await Promise.all([failedSave, deleteAfterFailure]);
  assert.deepEqual(
    failed.calls.api.map(call => call.endpoint),
    ["/api/chat/history/save", "/api/chat/history/delete"],
    "a failed predecessor must release the ordered tail for delete",
  );
  assert.equal(failed.stored.has(failed.historyId), false);
  assert.equal(failed.state.chatHistoryMutationTail, null);
  assert.equal(failed.state.chatHistorySaving, false);
  assert.equal(failed.state.chatHistoryBusyId, "");

  const loadThenSave = createHarness();
  const loading = loadThenSave.context.loadChatHistory(true);
  const saveAfterLoad = loadThenSave.context.saveCurrentChatHistory();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.deepEqual(
    loadThenSave.calls.api.map(call => call.endpoint),
    ["/api/chat/history"],
    "a save claimed after History load must wait for its older snapshot",
  );
  loadThenSave.releaseHistory();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.deepEqual(
    loadThenSave.calls.api.map(call => call.endpoint),
    ["/api/chat/history", "/api/chat/history/save"],
  );
  loadThenSave.releaseSave();
  await Promise.all([loading, saveAfterLoad]);
  assert.equal(loadThenSave.state.chatHistoryThreads[0].id, loadThenSave.historyId);
  assert.equal(loadThenSave.state.chatHistoryMutationTail, null);

  console.log("Chat history saves and destructive operations are ordered without resurrection races.");
}

run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
