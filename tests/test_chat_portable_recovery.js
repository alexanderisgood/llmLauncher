"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const {webcrypto} = require("node:crypto");

const root = path.resolve(__dirname, "..");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const ChatDraftsCore = require("../chat_drafts.js");
const ChatQueueCore = require("../chat_queue.js");

const sourceBetween = require("./helpers/workspace_sources.js").between;

const production = [
  sourceBetween("function readChatDraftEnvelope()", "\nfunction persistChatQueue"),
  sourceBetween("function persistChatQueue(", "\nfunction chatQueueCount"),
  sourceBetween("function chatDraftSurfacePrefix(", "\nfunction sizeChatInput"),
  sourceBetween("function activateChatDraft(", "\nfunction clearChatDraft"),
].join("\n");

const draftStorageKey = "test-chat-drafts";
const queueStorageKey = "test-chat-queues";
const storage = new Map();
const sessionStorage = {
  getItem:key => storage.has(key) ? storage.get(key) : null,
  setItem:(key, value) => storage.set(key, String(value)),
};
const input = {value:"", style:{}, scrollHeight:30};
const state = {
  chatDraftKey:"",
  chatDraftPendingHistoryId:"",
  chatDraftRestored:false,
  chatDraftSavedAt:0,
  chatDraftStorageAvailable:true,
  chatDraftTimer:null,
  chatQueue:[],
  chatQueueEditingId:"",
  chatQueuePaused:false,
  chatQueueRecovered:false,
  chatQueueStorageAvailable:true,
  chatRunId:"surface-old",
  chatTurnTabId:"",
  chatTurnTabStorageAvailable:true,
};
const context = {
  CHAT_DRAFT_OPTIONS:{
    maximumDrafts:20, maximumDraftCharacters:200_000,
    maximumTotalCharacters:400_000, maximumKeyCharacters:240,
  },
  CHAT_DRAFT_STORAGE_KEY:draftStorageKey,
  CHAT_QUEUE_OPTIONS:{
    maximumQueues:20, maximumMessages:32, maximumMessageCharacters:1_000_000,
    maximumQueueCharacters:1_000_000, maximumTotalCharacters:1_000_000,
    maximumKeyCharacters:240,
  },
  CHAT_QUEUE_STORAGE_KEY:queueStorageKey,
  CHAT_TURN_TAB_STORAGE_KEY:"test-chat-tab",
  ChatDraftsCore,
  ChatQueueCore,
  Date,
  JSON,
  Uint8Array,
  console,
  crypto:webcrypto,
  renderChatDraftStatus:() => {},
  renderChatSidebar:() => {},
  sessionStorage,
  sizeChatInput:() => {},
  state,
  $:id => id === "chatInput" ? input : {},
};
vm.createContext(context);
vm.runInContext(production, context);

function storeDraftAndQueue(key, text, queued) {
  const drafts = ChatDraftsCore.writeDraft(
    ChatDraftsCore.emptyEnvelope(), key, text, 100, context.CHAT_DRAFT_OPTIONS,
  );
  const queues = ChatQueueCore.writeQueue(
    ChatQueueCore.emptyEnvelope(), key,
    queued.map((content, index) => ({id:`queued-${index}`, content})),
    100, context.CHAT_QUEUE_OPTIONS,
  );
  storage.set(draftStorageKey, JSON.stringify(drafts));
  storage.set(queueStorageKey, JSON.stringify(queues));
}

const historyId = "11111111-1111-4111-8111-111111111111";
const legacyHistoryKey = `surface:surface-old:history:${historyId}`;
storeDraftAndQueue(legacyHistoryKey, "unfinished follow-up", ["queued follow-up"]);

context.activateChatDraft("surface-new", {historyId, restore:true});
const durableHistoryKey = `history:${historyId}`;
assert.equal(state.chatDraftKey, durableHistoryKey);
assert.equal(input.value, "unfinished follow-up");
assert.deepEqual(JSON.parse(JSON.stringify(state.chatQueue)), [
  {id:"queued-0", content:"queued follow-up"},
]);
assert.equal(state.chatQueuePaused, true);
assert.equal(state.chatDraftPendingHistoryId, "", "an explicitly opened history must not recursively reopen itself");
let drafts = JSON.parse(storage.get(draftStorageKey));
let queues = JSON.parse(storage.get(queueStorageKey));
assert.equal(ChatDraftsCore.readDraft(drafts, legacyHistoryKey, context.CHAT_DRAFT_OPTIONS), "");
assert.equal(ChatDraftsCore.readDraft(drafts, durableHistoryKey, context.CHAT_DRAFT_OPTIONS), "unfinished follow-up");
assert.deepEqual(ChatQueueCore.readQueue(queues, legacyHistoryKey, context.CHAT_QUEUE_OPTIONS), []);
assert.equal(ChatQueueCore.readQueue(queues, durableHistoryKey, context.CHAT_QUEUE_OPTIONS).length, 1);

state.chatRunId = "surface-third";
state.chatDraftKey = "";
state.chatQueue = [];
input.value = "";
context.activateChatDraft("surface-third", {historyId, restore:true});
assert.equal(state.chatDraftKey, durableHistoryKey);
assert.equal(input.value, "unfinished follow-up");
assert.equal(state.chatQueue[0].content, "queued follow-up");

const portableDraftKey = context.newChatDraftKey("surface-third");
assert.match(portableDraftKey, /^draft:[0-9a-f-]{36}$/i);
storeDraftAndQueue(portableDraftKey, "brand-new unsent draft", ["brand-new queue"]);
state.chatRunId = "surface-fourth";
state.chatDraftKey = "";
state.chatQueue = [];
input.value = "";
context.activateChatDraft("surface-fourth", {restoreActive:true});
assert.equal(state.chatDraftKey, portableDraftKey);
assert.equal(input.value, "brand-new unsent draft");
assert.equal(state.chatQueue[0].content, "brand-new queue");
assert.equal(state.chatQueuePaused, true);

console.log("Chat drafts and paused queues survive Stop, detach, and replacement surface IDs.");
