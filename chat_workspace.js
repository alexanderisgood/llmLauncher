/* Complete built-in Chat workspace: draft, queue, context, stream, history, branches and navigation. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;root.LLMChatWorkspace=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  function createController(options){
    const {nodes,cores,api:network,platform,navigation,callbacks,formatting,review,session}=options;
    const $=id=>nodes[id];
    const {ChatDraftsCore,ChatQueueCore,ChatScrollCore,ChatStatusCore,ChatStreamCore,ChatTranscriptCore,SafeMarkdownCore,WorkspaceContextCore}=cores;
    const {esc,formatBytes,formatNumber,backendName,profileBackendLabel}=formatting;
    const {showNotice,copyLocalText,pollStatus,renderCacheObservatory,renderRequestActivity,renderQuickStart,surfacePostmortemMarker}=callbacks;
    const {uiEngineVisible}=options.policy;
    const document=platform.dom;
    const {sessionStorage,requestAnimationFrame,setTimeout,clearTimeout,matchMedia}=platform;
    const reducedMotion=platform.reducedMotion;
    const activeDetail=platform.activeDetail;
    const agentConsoleIsVisible=navigation.agentVisible;
    const agentConsoleWorkspace={suspend:navigation.suspendAgent};
    const state={
      chatMessages: [],
      chatAbort: null,
      chatStopBusy: false,
      chatRunId: "",
      chatOwnerRunId: "",
      chatAttachment: null,
      chatAttachmentObserved: false,
      chatPostmortem: null,
      chatQueue: [],
      chatQueuePaused: false,
      chatQueueRecovered: false,
      chatQueueStorageAvailable: null,
      chatContextFiles: [],
      chatContextBusy: false,
      chatWorkspaceContext: null,
      chatBranch: null,
      chatEditingMessageId: "",
      chatQueueEditingId: "",
      chatContextReducedAt: 0,
      chatRevisionBusy: false,
      chatHistoryId: "",
      chatHistoryThreads: [],
      chatHistoryLoading: false,
      chatHistorySaving: false,
      chatHistoryMutationTail: null,
      chatHistoryDeleteConfirmId: "",
      chatHistoryEditingId: "",
      chatHistoryBusyId: "",
      chatHistoryQuery: "",
      chatHistoryLoaded: false,
      chatSidebarQuery: "",
      chatSidebarCollapsed: false,
      chatSidebarMenuId: "",
      chatSidebarEditingId: "",
      chatActiveThread: null,
      chatRunSettings: null,
      chatRunSettingsKey: "",
      chatRunSettingsBusy: false,
      chatRunSettingsGeneration: 0,
      chatDraftKey: "",
      chatDraftTimer: null,
      chatDraftRestored: false,
      chatDraftSavedAt: 0,
      chatDraftStorageAvailable: null,
      chatDraftPendingHistoryId: "",
      chatTurnTabId: "",
      chatTurnTabStorageAvailable: null,
      chatTurnRecoveryChecked: false,
      chatTurnRecoveryAvailable: null,
      chatTurnRecoveredHistoryId: "",
      chatTurnCheckpoint: null,
      chatTurnCheckpointTimer: null,
      chatTurnCheckpointPromise: null,
      chatTurnCheckpointDirty: false,
      chatTurnCheckpointLastAt: 0,
      chatTurnSettlement: null,
      chatRenderFrame: null,
      chatFollowOutput: true,
      chatRenderRevision: 0,
      chatScrollInteractionRevision: 0,
      chatTranscriptSearchOpen: false,
      chatTranscriptQuery: "",
      chatTranscriptActiveId: ""
    };
    Object.defineProperties(state,{
      runPhase:{get:()=>session.snapshot().phase},
      runStatus:{get:()=>session.snapshot().status},
      token:{get:()=>session.token()},
      agentConsoleVisible:{get:()=>navigation.agentVisible()},
    });
    const chatResumeReview=review;
    const updateAgentWorkspace=()=>navigation.refreshAgent();
    const updateWorkspaceChrome=()=>navigation.refreshChrome();
    const sessionRouteActive=callbacks.sessionRouteActive;
    let chatMessageSequence=0;
    let renderedMessageRows = new Map();
    const endpoints=Object.freeze({
      '/api/chat/history':'historyInventory','/api/chat/history/delete':'historyDelete',
      '/api/chat/history/get':'historyGet','/api/chat/history/update':'historyUpdate',
      '/api/chat/history/save':'historySave',
      '/api/chat/settings/get':'settingsGet','/api/chat/settings/update':'settingsUpdate',
      '/api/chat/stop':'stopResponse','/api/chat/turn/checkpoint':'checkpoint',
      '/api/chat/turn/clear':'clearCheckpoint','/api/chat/turn/recover':'recoverCheckpoint',
      '/api/session/detach':'detachSurface',
    });
    const api=(path,settings)=>network[endpoints[path]](settings);
    const launcherApi={response:(_path,settings)=>network.stream(settings)};
const CHAT_QUEUE_MAX_MESSAGES = 32;
const CHAT_QUEUE_MAX_CHARACTERS = 1_000_000;
const CHAT_QUEUE_STORAGE_KEY = "llm-launcher-chat-queues-v1";
const CHAT_TURN_TAB_STORAGE_KEY = "llm-launcher-chat-tab-id-v1";
const CHAT_TURN_CHECKPOINT_INTERVAL_MS = 1800;
const CHAT_QUEUE_OPTIONS = Object.freeze({
  maximumQueues:20,
  maximumMessages:CHAT_QUEUE_MAX_MESSAGES,
  maximumMessageCharacters:CHAT_QUEUE_MAX_CHARACTERS,
  maximumQueueCharacters:CHAT_QUEUE_MAX_CHARACTERS,
  maximumTotalCharacters:CHAT_QUEUE_MAX_CHARACTERS,
  maximumKeyCharacters:240,
});
const CHAT_RECENT_MESSAGE_LIMIT = 8;
const CHAT_CONTEXT_MAX_FILES = 24;
const CHAT_CONTEXT_MAX_FILE_BYTES = 512 * 1024;
const CHAT_CONTEXT_MAX_BYTES = 1_536 * 1024;
const CHAT_CONTEXT_MAX_CHARACTERS = 1_000_000;
const CHAT_WORKSPACE_INDEX_MAX_FILES = 500;
const CHAT_WORKSPACE_INDEX_MAX_BYTES = 16 * 1024 * 1024;
const CHAT_WORKSPACE_REQUEST_MAX_FILES = 12;
const CHAT_WORKSPACE_REQUEST_MAX_CHARACTERS = 96_000;
const CHAT_WORKSPACE_REQUEST_MAX_FILE_CHARACTERS = 24_000;
const CHAT_DRAFT_STORAGE_KEY = "llm-launcher-chat-drafts-v1";
const CHAT_DRAFT_OPTIONS = Object.freeze({
  maximumDrafts:20,
  maximumDraftCharacters:200_000,
  maximumTotalCharacters:400_000,
  maximumKeyCharacters:240,
});
const CHAT_CONTEXT_TEXT_EXTENSIONS = new Set([
  "txt", "md", "markdown", "json", "jsonl", "csv", "tsv", "yaml", "yml", "toml",
  "xml", "html", "css", "js", "mjs", "cjs", "ts", "tsx", "jsx", "py", "rs", "go",
  "java", "c", "h", "cpp", "hpp", "swift", "sh", "sql", "log", "ini", "cfg", "rb",
  "php", "scala", "kt", "kts", "lua", "r", "vue", "svelte", "dart", "ex", "exs",
  "erl", "hrl", "fs", "fsx", "cs", "csproj", "gradle", "proto", "graphql", "gql",
  "tex", "rst",
]);
const CHAT_CONTEXT_TEXT_BASENAMES = new Set([
  "makefile", "dockerfile", "gemfile", "procfile", "justfile", "license", "readme",
  "changelog", "authors", "notice", "cargo.lock", "go.mod", "go.sum",
]);
const CHAT_WORKSPACE_IGNORED_SEGMENTS = new Set([
  ".git", ".hg", ".svn", "node_modules", "bower_components", "vendor", "dist", "build",
  "out", "target", ".next", ".nuxt", ".cache", "coverage", "__pycache__", ".pytest_cache",
  ".mypy_cache", ".ruff_cache", ".venv", "venv", "env", "pods", "deriveddata",
]);
const CHAT_WORKSPACE_STOP_WORDS = new Set([
  "about", "after", "again", "also", "and", "are", "can", "could", "does", "for", "from",
  "have", "how", "into", "its", "please", "show", "that", "the", "this", "use", "what",
  "when", "where", "which", "with", "would", "you", "your", "repo", "repository", "code",
  "file", "files", "project",
]);
const CHAT_TRANSCRIPT_HIGHLIGHT_LIMIT = 1_024;
function updateChatStatusSummaryLabel() {
  const summary = $("chatStatusSummary");
  const panel = $("chatStatusPanel");
  if (!summary || !panel) return;
  const routeState = $("chatStatusRouteState")?.hidden ? "" : $("chatStatusRouteState")?.textContent;
  const warning = $("chatStatusWarning")?.hidden ? "" : $("chatStatusWarning")?.textContent;
  summary.setAttribute("aria-label", [
    $("chatStatusModel")?.textContent,
    $("chatStatusEngine")?.textContent,
    `Speed ${$("chatStatusSpeedValue")?.textContent || "not reported"}`,
    `Lane ${$("chatStatusLaneValue")?.textContent || "unknown"}`,
    `Cache ${$("chatStatusCacheValue")?.textContent || "unknown"}`,
    routeState, warning,
    panel.open ? "Hide full Chat status details" : "Show full Chat status details",
  ].filter(Boolean).join(". "));
}

function renderChatStatusDisclosure() {
  const panel = $("chatStatusPanel");
  if (!panel) return;
  $("chatStatusDisclosureLabel").textContent = panel.open ? "Hide" : "Details";
  updateChatStatusSummaryLabel();
}

function syncChatStatusDetailMode(detail = activeDetail()) {
  const panel = $("chatStatusPanel");
  if (!panel) return;
  panel.open = detail === "detailed";
  renderChatStatusDisclosure();
}

function syncChatResumeDetailMode(detail = activeDetail()) {
  const panel = $("chatResumeContract");
  if (panel) panel.open = detail === "detailed";
}

function readChatDraftEnvelope() {
  let raw = "";
  try {
    raw = sessionStorage.getItem(CHAT_DRAFT_STORAGE_KEY) || "";
    state.chatDraftStorageAvailable = true;
  } catch (_error) {
    state.chatDraftStorageAvailable = false;
    return ChatDraftsCore.emptyEnvelope();
  }
  if (!raw) return ChatDraftsCore.emptyEnvelope();
  try {
    return ChatDraftsCore.normaliseEnvelope(JSON.parse(raw), CHAT_DRAFT_OPTIONS);
  } catch (_error) {
    return ChatDraftsCore.emptyEnvelope();
  }
}

function writeChatDraftEnvelope(envelope) {
  try {
    sessionStorage.setItem(
      CHAT_DRAFT_STORAGE_KEY,
      JSON.stringify(ChatDraftsCore.normaliseEnvelope(envelope, CHAT_DRAFT_OPTIONS)),
    );
    state.chatDraftStorageAvailable = true;
    return true;
  } catch (_error) {
    state.chatDraftStorageAvailable = false;
    return false;
  }
}

function readChatQueueEnvelope() {
  let raw = "";
  try {
    raw = sessionStorage.getItem(CHAT_QUEUE_STORAGE_KEY) || "";
    state.chatQueueStorageAvailable = true;
  } catch (_error) {
    state.chatQueueStorageAvailable = false;
    return ChatQueueCore.emptyEnvelope();
  }
  if (!raw) return ChatQueueCore.emptyEnvelope();
  try {
    return ChatQueueCore.normaliseEnvelope(JSON.parse(raw), CHAT_QUEUE_OPTIONS);
  } catch (_error) {
    return ChatQueueCore.emptyEnvelope();
  }
}

function writeChatQueueEnvelope(envelope) {
  try {
    sessionStorage.setItem(
      CHAT_QUEUE_STORAGE_KEY,
      JSON.stringify(ChatQueueCore.normaliseEnvelope(envelope, CHAT_QUEUE_OPTIONS)),
    );
    state.chatQueueStorageAvailable = true;
    return true;
  } catch (_error) {
    state.chatQueueStorageAvailable = false;
    return false;
  }
}

function persistChatQueue(key = state.chatDraftKey) {
  if (!key) return false;
  const next = ChatQueueCore.writeQueue(
    readChatQueueEnvelope(), key, state.chatQueue, Date.now(), CHAT_QUEUE_OPTIONS,
  );
  return writeChatQueueEnvelope(next);
}

function restoreChatQueue(key = state.chatDraftKey, pause = true) {
  const items = key
    ? ChatQueueCore.readQueue(readChatQueueEnvelope(), key, CHAT_QUEUE_OPTIONS) : [];
  state.chatQueue = items;
  state.chatQueueEditingId = "";
  state.chatQueuePaused = Boolean(items.length && pause);
  state.chatQueueRecovered = Boolean(items.length && pause);
}

function migrateChatQueueKey(fromKey, toKey) {
  if (!fromKey || !toKey || fromKey === toKey) return;
  const next = ChatQueueCore.moveQueue(
    readChatQueueEnvelope(), fromKey, toKey, Date.now(), CHAT_QUEUE_OPTIONS,
  );
  writeChatQueueEnvelope(next);
}

function chatQueueCount(envelope, key) {
  return key ? ChatQueueCore.readQueue(envelope, key, CHAT_QUEUE_OPTIONS).length : 0;
}

function chatDraftSurfacePrefix(surfaceId = state.chatRunId) {
  return `surface:${String(surfaceId || "").slice(0, 96)}:`;
}

function chatHistoryDraftKey(historyId, _surfaceId = state.chatRunId) {
  // Saved conversations outlive the temporary run/attachment that happens to
  // display them. Keep their draft and paused queue under the history ID so a
  // Stop, detach, or warm attachment cannot strand unsent work under an old
  // surface ID.
  return `history:${String(historyId || "").slice(0, 72)}`;
}

function newChatDraftKey(_surfaceId = state.chatRunId) {
  return `draft:${localUuid()}`;
}

function isPortableChatDraftKey(key) {
  const raw = String(key || "");
  return /^draft:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(raw)
    || /^surface:[^:\u0000-\u001f\u007f]{1,96}:new:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(raw);
}

function localUuid() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  const bytes = new Uint8Array(16);
  if (globalThis.crypto?.getRandomValues) globalThis.crypto.getRandomValues(bytes);
  else for (let index = 0; index < bytes.length; index += 1) bytes[index] = Math.floor(Math.random() * 256);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map(value => value.toString(16).padStart(2, "0"));
  return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`;
}

function chatTurnTabIdentifier() {
  if (state.chatTurnTabId) return state.chatTurnTabId;
  const valid = value => /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(value || ""));
  try {
    const stored = sessionStorage.getItem(CHAT_TURN_TAB_STORAGE_KEY);
    state.chatTurnTabId = valid(stored) ? stored.toLocaleLowerCase() : localUuid();
    sessionStorage.setItem(CHAT_TURN_TAB_STORAGE_KEY, state.chatTurnTabId);
    state.chatTurnTabStorageAvailable = true;
  } catch (_error) {
    state.chatTurnTabId = localUuid();
    state.chatTurnTabStorageAvailable = false;
  }
  return state.chatTurnTabId;
}

function chatDraftHistoryIdFromKey(key, _surfaceId = state.chatRunId) {
  const raw = String(key || "");
  const legacy = /^surface:[^:\u0000-\u001f\u007f]{1,96}:history:(.+)$/.exec(raw);
  const value = raw.startsWith("history:") ? raw.slice("history:".length) : legacy?.[1] || "";
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
    ? value.toLocaleLowerCase() : "";
}

function migrateLegacyChatHistoryStorage(historyId) {
  const id = String(historyId || "").toLocaleLowerCase();
  const targetKey = chatHistoryDraftKey(id);
  if (!chatDraftHistoryIdFromKey(targetKey)) return targetKey;
  const suffix = `:history:${id}`;

  let drafts = readChatDraftEnvelope();
  const legacyDrafts = Object.entries(drafts.drafts || {})
    .filter(([key]) => key.startsWith("surface:") && key.toLocaleLowerCase().endsWith(suffix))
    .sort((left, right) => Number(right[1]?.updatedAt || 0) - Number(left[1]?.updatedAt || 0));
  const activeWasLegacy = chatDraftHistoryIdFromKey(drafts.activeKey) === id
    && drafts.activeKey !== targetKey;
  if (!drafts.drafts?.[targetKey] && legacyDrafts.length) {
    drafts = ChatDraftsCore.moveDraft(
      drafts, legacyDrafts[0][0], targetKey, CHAT_DRAFT_OPTIONS,
    );
  } else if (activeWasLegacy) {
    drafts = ChatDraftsCore.setActive(drafts, targetKey, CHAT_DRAFT_OPTIONS);
  }
  writeChatDraftEnvelope(drafts);

  let queues = readChatQueueEnvelope();
  const legacyQueues = Object.entries(queues.queues || {})
    .filter(([key]) => key.startsWith("surface:") && key.toLocaleLowerCase().endsWith(suffix))
    .sort((left, right) => Number(right[1]?.updatedAt || 0) - Number(left[1]?.updatedAt || 0));
  if (!queues.queues?.[targetKey] && legacyQueues.length) {
    queues = ChatQueueCore.moveQueue(
      queues, legacyQueues[0][0], targetKey, Date.now(), CHAT_QUEUE_OPTIONS,
    );
    writeChatQueueEnvelope(queues);
  }
  return targetKey;
}

function sizeChatInput() {
  const input = $("chatInput");
  if (!input) return;
  input.style.height = "auto";
  if (input.value) input.style.height = `${Math.min(180, input.scrollHeight)}px`;
}

function renderChatDraftStatus() {
  const status = $("chatDraftStatus");
  const clear = $("chatDraftClear");
  const input = $("chatInput");
  if (!status || !clear || !input) return;
  const characters = input.value.length;
  status.className = "";
  clear.disabled = !characters;
  if (!state.chatDraftKey || !state.chatRunId) {
    status.textContent = "Draft recovery starts when a local Chat route is ready.";
  } else if (state.chatDraftStorageAvailable === false) {
    status.className = "warning";
    status.textContent = "This browser blocked tab-local draft recovery; copy important unfinished text.";
  } else if (characters > CHAT_DRAFT_OPTIONS.maximumDraftCharacters) {
    status.className = "warning";
    status.textContent = `Draft recovery is capped at ${formatNumber(CHAT_DRAFT_OPTIONS.maximumDraftCharacters)} characters; the full text still remains in the composer.`;
  } else if (characters && state.chatDraftRestored) {
    status.className = "restored";
    status.textContent = "Recovered this unfinished message from the current browser tab.";
  } else if (characters) {
    status.textContent = state.chatDraftSavedAt
      ? "Draft saved in this browser tab only. The queue is recovered separately; context files are not stored."
      : "Saving unfinished text in this browser tab…";
  } else {
    status.textContent = "Unfinished text is kept in this tab only and cleared when sent.";
  }
}

function persistChatDraftNow() {
  if (state.chatDraftTimer !== null) {
    clearTimeout(state.chatDraftTimer);
    state.chatDraftTimer = null;
  }
  if (!state.chatDraftKey || !$("chatInput")) {
    renderChatDraftStatus();
    return false;
  }
  const next = ChatDraftsCore.writeDraft(
    readChatDraftEnvelope(), state.chatDraftKey, $("chatInput").value,
    Date.now(), CHAT_DRAFT_OPTIONS,
  );
  const stored = writeChatDraftEnvelope(next);
  state.chatDraftSavedAt = stored ? Date.now() : 0;
  renderChatDraftStatus();
  renderChatSidebar();
  return stored;
}

function persistChatSessionState() {
  const draftStored = persistChatDraftNow();
  const queueStored = persistChatQueue();
  return draftStored && queueStored;
}

function scheduleChatDraftSave() {
  if (state.chatDraftTimer !== null) clearTimeout(state.chatDraftTimer);
  state.chatDraftSavedAt = 0;
  state.chatDraftRestored = false;
  renderChatDraftStatus();
  state.chatDraftTimer = setTimeout(() => {
    state.chatDraftTimer = null;
    persistChatDraftNow();
  }, 260);
}

function activateChatDraft(surfaceId, options = {}) {
  if (!surfaceId) return;
  if (state.chatDraftTimer !== null) {
    clearTimeout(state.chatDraftTimer);
    state.chatDraftTimer = null;
  }
  let envelope = readChatDraftEnvelope();
  const requestedHistoryId = String(options.historyId || "").toLocaleLowerCase();
  const activeHistoryId = options.restoreActive
    ? chatDraftHistoryIdFromKey(envelope.activeKey) : "";
  if (requestedHistoryId || activeHistoryId) {
    migrateLegacyChatHistoryStorage(requestedHistoryId || activeHistoryId);
    envelope = readChatDraftEnvelope();
  }
  const prefix = chatDraftSurfacePrefix(surfaceId);
  const active = options.restoreActive && (
    String(envelope.activeKey || "").startsWith(prefix)
    || Boolean(chatDraftHistoryIdFromKey(envelope.activeKey))
    || isPortableChatDraftKey(envelope.activeKey)
  ) ? envelope.activeKey : "";
  const explicitKey = (
    String(options.key || "").startsWith(prefix)
    || isPortableChatDraftKey(options.key)
  ) ? String(options.key) : "";
  const key = explicitKey || (options.historyId
    ? chatHistoryDraftKey(options.historyId, surfaceId)
    : active || newChatDraftKey(surfaceId));
  state.chatDraftKey = key;
  state.chatDraftPendingHistoryId = !requestedHistoryId && active
    ? chatDraftHistoryIdFromKey(active, surfaceId) : "";
  envelope = ChatDraftsCore.setActive(envelope, key, CHAT_DRAFT_OPTIONS);
  writeChatDraftEnvelope(envelope);
  const text = options.restore === false
    ? "" : ChatDraftsCore.readDraft(envelope, key, CHAT_DRAFT_OPTIONS);
  $("chatInput").value = text;
  state.chatDraftRestored = Boolean(text);
  state.chatDraftSavedAt = text ? Date.now() : 0;
  restoreChatQueue(key, options.restore !== false);
  sizeChatInput();
  renderChatDraftStatus();
  renderChatSidebar();
}

function clearChatDraft(options = {}) {
  if (!state.chatDraftKey) return;
  if (!options.keepInput) $("chatInput").value = "";
  let envelope = ChatDraftsCore.removeDraft(
    readChatDraftEnvelope(), state.chatDraftKey, CHAT_DRAFT_OPTIONS,
  );
  envelope = ChatDraftsCore.setActive(envelope, state.chatDraftKey, CHAT_DRAFT_OPTIONS);
  writeChatDraftEnvelope(envelope);
  state.chatDraftRestored = false;
  state.chatDraftSavedAt = 0;
  sizeChatInput();
  renderChatDraftStatus();
  renderChatSidebar();
}

function migrateChatDraftToHistory(historyId) {
  if (!historyId || !state.chatRunId) return;
  const previousKey = state.chatDraftKey;
  persistChatDraftNow();
  persistChatQueue(previousKey);
  const nextKey = chatHistoryDraftKey(historyId);
  if (previousKey === nextKey) return;
  const next = ChatDraftsCore.moveDraft(
    readChatDraftEnvelope(), previousKey, nextKey, CHAT_DRAFT_OPTIONS,
  );
  migrateChatQueueKey(previousKey, nextKey);
  state.chatDraftKey = nextKey;
  writeChatDraftEnvelope(next);
  renderChatDraftStatus();
  renderChatSidebar();
}

async function restorePendingChatDraftConversation() {
  const historyId = state.chatDraftPendingHistoryId;
  state.chatDraftPendingHistoryId = "";
  if (!historyId || state.runPhase !== "running" || !state.chatRunId || state.chatMessages.length) return;
  if (state.chatHistoryThreads.some(thread => thread.id === historyId)) {
    await openChatHistoryThread(historyId, {
      recovery:true,
      interruptedRecovery:state.chatTurnRecoveredHistoryId === historyId,
      skipCurrentSave:true,
    });
    return;
  }
  const oldKey = state.chatDraftKey;
  const nextKey = newChatDraftKey();
  const next = ChatDraftsCore.moveDraft(
    readChatDraftEnvelope(), oldKey, nextKey, CHAT_DRAFT_OPTIONS,
  );
  migrateChatQueueKey(oldKey, nextKey);
  state.chatDraftKey = nextKey;
  writeChatDraftEnvelope(next);
  showNotice("Recovered the unfinished message, but its saved transcript is no longer available. It is now a new chat draft.");
  renderChatDraftStatus();
  renderChatSidebar();
}

function nextChatMessageId() {
  chatMessageSequence += 1;
  return `chat-message-${Date.now()}-${chatMessageSequence}`;
}

function normaliseChatTimestamp(value) {
  if (typeof value !== "string" || !value || value.length > 48) return "";
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toISOString() : "";
}

function formatChatTimestamp(value) {
  const timestamp = normaliseChatTimestamp(value);
  if (!timestamp) return null;
  const date = new Date(timestamp);
  return {
    timestamp,
    short:date.toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"}),
    long:date.toLocaleString([], {dateStyle:"medium", timeStyle:"short"}),
  };
}

function normaliseChatFailure(value) {
  return typeof value === "string" ? value.replace(/\0/g, "").trim().slice(0, 800) : "";
}

function normaliseChatMessage(message = {}) {
  return {
    id:nextChatMessageId(),
    role:message.role === "assistant" ? "assistant" : "user",
    content:String(message.content || ""),
    reasoning:String(message.reasoning || ""),
    usage:message.usage ? {...message.usage} : null,
    pending:Boolean(message.pending),
    stopped:Boolean(message.stopped),
    exclude:Boolean(message.exclude),
    interrupted:Boolean(message.interrupted),
    failure:normaliseChatFailure(message.failure),
    continuation:Boolean(message.continuation),
    truncated:Boolean(message.truncated),
    createdAt:normaliseChatTimestamp(message.createdAt),
  };
}

function resetChatConversation() {
  if (state.chatDraftTimer !== null) clearTimeout(state.chatDraftTimer);
  cancelChatTurnCheckpoint();
  state.chatMessages = [];
  state.chatQueue = [];
  state.chatQueuePaused = false;
  state.chatQueueRecovered = false;
  state.chatContextFiles = [];
  state.chatWorkspaceContext = null;
  state.chatContextBusy = false;
  state.chatBranch = null;
  state.chatEditingMessageId = "";
  state.chatQueueEditingId = "";
  state.chatContextReducedAt = 0;
  state.chatRevisionBusy = false;
  state.chatHistoryId = "";
  state.chatActiveThread = null;
  state.chatSidebarMenuId = "";
  state.chatSidebarEditingId = "";
  state.chatDraftKey = "";
  state.chatDraftTimer = null;
  state.chatDraftRestored = false;
  state.chatDraftSavedAt = 0;
  state.chatDraftPendingHistoryId = "";
  state.chatFollowOutput = true;
  state.chatTranscriptSearchOpen = false;
  state.chatTranscriptQuery = "";
  state.chatTranscriptActiveId = "";
  state.chatPostmortem = null;
}

function chatEventUsage(event) {
  const raw = event?.usage;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const integer = (...keys) => {
    for (const key of keys) {
      const value = raw[key];
      const parsed = typeof value === "string" && /^\d+$/.test(value) ? Number(value) : value;
      if (Number.isSafeInteger(parsed) && parsed >= 0) return parsed;
    }
    return null;
  };
  const promptTokens = integer("prompt_tokens", "input_tokens");
  const completionTokens = integer("completion_tokens", "output_tokens");
  if (!promptTokens || completionTokens === null) return null;
  const detail = raw.prompt_tokens_details || raw.input_tokens_details || {};
  const directCached = integer("cached_tokens", "cache_read_input_tokens");
  const nestedCached = Number.isSafeInteger(detail?.cached_tokens) && detail.cached_tokens >= 0
    ? detail.cached_tokens
    : null;
  const cachedPromptTokens = Math.min(promptTokens, directCached ?? nestedCached ?? promptTokens);
  return {
    source:"runtime", promptTokens, completionTokens,
    ...((directCached !== null || nestedCached !== null) ? {cachedPromptTokens} : {}),
  };
}

function emitThinkTaggedText(parser, chunk, onPart) {
  parser.buffer += chunk;
  while (parser.buffer) {
    const tag = parser.thinking ? "</think>" : "<think>";
    const index = parser.buffer.indexOf(tag);
    if (index >= 0) {
      const value = parser.buffer.slice(0, index);
      if (value) onPart(parser.thinking ? "reasoning" : "content", value);
      parser.buffer = parser.buffer.slice(index + tag.length);
      parser.thinking = !parser.thinking;
      continue;
    }
    let retained = 0;
    const maximum = Math.min(tag.length - 1, parser.buffer.length);
    for (let length = maximum; length > 0; length -= 1) {
      if (tag.startsWith(parser.buffer.slice(-length))) { retained = length; break; }
    }
    const ready = retained ? parser.buffer.slice(0, -retained) : parser.buffer;
    if (ready) onPart(parser.thinking ? "reasoning" : "content", ready);
    parser.buffer = retained ? parser.buffer.slice(-retained) : "";
    break;
  }
}

async function consumeChatResponse(response, onPart) {
  const thinkParser = {buffer:"", thinking:false};
  let terminalState = "";
  let terminalEvent = null;
  const consumeEvent = event => {
    const observedTerminal = ChatStreamCore.responseTerminalState(event);
    terminalState = ChatStreamCore.mergeResponseTerminalState(terminalState, observedTerminal);
    if (["failed", "aborted"].includes(observedTerminal)) terminalEvent = event;
    // Keep any already streamed answer intact; the terminal failure is raised
    // after the parser flushes a possible partial <think> tag fragment.
    if (event?.error) return;
    const parts = ChatStreamCore.eventParts(event);
    if (parts.reasoning) onPart("reasoning", parts.reasoning);
    if (parts.text) emitThinkTaggedText(thinkParser, parts.text, onPart);
    const usage = chatEventUsage(event);
    if (usage) onPart("usage", usage);
    const limitReason = ChatStreamCore.responseLimitReason(event);
    if (limitReason) onPart("truncated", limitReason);
  };
  const finish = doneSeen => {
    if (thinkParser.buffer) {
      onPart(thinkParser.thinking ? "reasoning" : "content", thinkParser.buffer);
      thinkParser.buffer = "";
    }
    const finalState = ChatStreamCore.finalResponseTerminalState(terminalState, doneSeen);
    if (["failed", "aborted", "unexpected-eof"].includes(finalState)) {
      const error = new Error(ChatStreamCore.responseTerminalMessage(finalState, terminalEvent));
      error.terminalState = finalState;
      throw error;
    }
    return finalState;
  };
  const contentType = response.headers.get("Content-Type") || "";
  if (contentType.toLowerCase().includes("application/json")) {
    const data = await response.json();
    consumeEvent(data);
    return finish(false);
  }
  if (!response.body) throw new Error("This browser could not read the model stream.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let rawText = "";
  const sse = ChatStreamCore.createSseDataParser(data => consumeEvent(JSON.parse(data)));
  while (true) {
    const {value, done} = await reader.read();
    const decoded = decoder.decode(value || new Uint8Array(), {stream:!done});
    rawText += decoded;
    sse.push(decoded);
    if (done) break;
  }
  sse.finish();
  if (!sse.sawData() && rawText.trim().startsWith("{")) {
    consumeEvent(JSON.parse(rawText));
  }
  return finish(sse.sawDone());
}

function renderChatUsage() {
  renderRequestActivity();
  renderCacheObservatory();
  const usage = [...state.chatMessages].reverse().find(message => message.role === "assistant" && message.usage)?.usage;
  const context = Number(state.chatAttachment?.context || state.runStatus?.run?.context || 0);
  const meter = $("chatUsageMeter");
  const contextActions = $("chatContextActions");
  if (!usage) {
    $("chatUsageValue").textContent = "Waiting for runtime report";
    $("chatUsageDetail").textContent = "No token estimate is invented when an engine omits usage.";
    $("chatUsage").dataset.state = "unknown";
    meter.style.width = "0%";
    meter.parentElement.setAttribute("aria-valuenow", "0");
    contextActions.classList.add("hidden");
    $("chatStatusPanel").dataset.contextState = "normal";
    $("chatStatusWarning").hidden = true;
    updateChatStatusSummaryLabel();
    return;
  }
  const promptTokens = Number(usage.promptTokens || 0);
  const completionTokens = Number(usage.completionTokens || 0);
  const percent = context > 0 ? (promptTokens / context) * 100 : null;
  const cached = Number.isInteger(usage.cachedPromptTokens)
    ? ` · ${formatNumber(usage.cachedPromptTokens)} cached`
    : "";
  $("chatUsageValue").textContent = `${formatNumber(promptTokens)} prompt · ${formatNumber(completionTokens)} response`;
  const reducedPending = state.chatContextReducedAt > 0
    && state.chatMessages.length <= state.chatContextReducedAt;
  $("chatUsageDetail").textContent = reducedPending
    ? `Previous prompt report${cached}. The next prompt keeps only the retained recent turns.`
    : percent === null
    ? `Reported by the runtime${cached}.`
    : `${percent.toFixed(percent < 10 ? 1 : 0)}% of ${formatNumber(context)} context in the latest prompt${cached}.`;
  const compactContext = ChatStatusCore.contextSummary(usage, context, reducedPending);
  const contextWarning = compactContext.warning;
  $("chatUsage").dataset.state = contextWarning ? "warning" : "ready";
  $("chatStatusPanel").dataset.contextState = contextWarning ? "warning" : "normal";
  $("chatStatusWarning").hidden = !contextWarning;
  if (contextWarning) {
    $("chatStatusWarning").textContent = compactContext.label;
    $("chatStatusWarning").title = $("chatUsageDetail").textContent;
  }
  updateChatStatusSummaryLabel();
  const bounded = Math.max(0, Math.min(100, percent || 0));
  meter.style.width = `${bounded}%`;
  meter.parentElement.setAttribute("aria-valuenow", String(Math.round(bounded)));
  const completedCount = state.chatMessages.filter(message => !message.pending && message.content).length;
  const canTrim = !reducedPending && percent !== null && percent >= 85
    && completedCount > CHAT_RECENT_MESSAGE_LIMIT;
  contextActions.classList.toggle("hidden", !canTrim);
  $("chatTrimButton").disabled = Boolean(
    state.chatAbort || state.chatRevisionBusy || state.chatEditingMessageId || state.chatQueue.length,
  );
}

function chatContextLocked() {
  return Boolean(
    state.chatAbort || state.chatRevisionBusy || state.chatEditingMessageId
    || state.chatQueueEditingId || (state.chatQueue.length && !state.chatQueuePaused)
    || state.chatContextBusy,
  );
}

function normaliseChatWorkspacePath(file) {
  return WorkspaceContextCore.normalisePath(file, 320);
}

function chatWorkspacePathPolicy(name, file) {
  return WorkspaceContextCore.pathPolicy(name, file, {
    ignoredSegments:CHAT_WORKSPACE_IGNORED_SEGMENTS,
    supported:supportedChatContextFile,
    maximumFileBytes:CHAT_CONTEXT_MAX_FILE_BYTES,
  });
}

function chatWorkspaceCandidatePriority(name) {
  return WorkspaceContextCore.candidatePriority(name);
}

function chatWorkspaceTerms(value) {
  return WorkspaceContextCore.queryTerms(value, CHAT_WORKSPACE_STOP_WORDS, 24);
}

function chatWorkspaceFileScore(file, terms) {
  return WorkspaceContextCore.fileScore(file, terms);
}

function chatWorkspaceExcerpt(file, terms, characterLimit) {
  return WorkspaceContextCore.excerpt(file, terms, characterLimit, formatNumber);
}

function chatRequestAvailableContextCharacters(messages) {
  const run = state.chatAttachment || state.runStatus?.run || {};
  const historyCharacters = (messages || []).reduce(
    (total, message) => total + ChatStreamCore.messageContextCharacters(message), 0,
  );
  return WorkspaceContextCore.availableContextCharacters({
    contextTokens:Number(run.context || 16_384),
    outputTokens:Number(run.output || 4_096),
    historyCharacters,
  });
}

function chatWorkspaceRequestCharacterBudget(messages, manualCharacters = 0) {
  const run = state.chatAttachment || state.runStatus?.run || {};
  const historyCharacters = (messages || []).reduce(
    (total, message) => total + ChatStreamCore.messageContextCharacters(message), 0,
  );
  return WorkspaceContextCore.requestCharacterBudget({
    contextTokens:Number(run.context || 16_384),
    outputTokens:Number(run.output || 4_096),
    historyCharacters,
    manualCharacters,
    maximumCharacters:CHAT_WORKSPACE_REQUEST_MAX_CHARACTERS,
    contextShare:.22,
  });
}

function chatContextRequestFiles(query, messages = []) {
  const result = state.chatContextFiles.map(file => ({name:file.name, content:file.content}));
  const manualCharacters = result.reduce((total, file) => total + file.content.length, 0);
  if (manualCharacters > chatRequestAvailableContextCharacters(messages)) {
    throw new Error(
      "The attached text is too large for the selected context, response ceiling, and current transcript. Remove files or choose a larger context before sending.",
    );
  }
  const workspace = state.chatWorkspaceContext;
  if (!workspace) return result;
  workspace.lastSelection = [];
  workspace.lastBudget = chatWorkspaceRequestCharacterBudget(messages, manualCharacters);
  const terms = chatWorkspaceTerms(query || [...messages].reverse().find(message => message.role === "user")?.content || "");
  const names = new Set(result.map(file => file.name.toLocaleLowerCase()));
  let remainingCharacters = Math.min(
    workspace.lastBudget,
    CHAT_CONTEXT_MAX_CHARACTERS - manualCharacters,
  );
  let remainingBytes = CHAT_CONTEXT_MAX_BYTES - state.chatContextFiles.reduce((total, file) => total + file.bytes, 0);
  const availableSlots = Math.min(CHAT_WORKSPACE_REQUEST_MAX_FILES, CHAT_CONTEXT_MAX_FILES - result.length);
  if (remainingCharacters < 256 || remainingBytes < 256 || availableSlots <= 0) return result;
  const ranked = workspace.files.map(file => ({file, score:chatWorkspaceFileScore(file, terms)}))
    .sort((left, right) => right.score - left.score || left.file.name.localeCompare(right.file.name));
  for (const item of ranked) {
    if (workspace.lastSelection.length >= availableSlots || remainingCharacters < 256 || remainingBytes < 256) break;
    const name = `${workspace.root}/${item.file.name}`;
    if (names.has(name.toLocaleLowerCase())) continue;
    const excerpt = chatWorkspaceExcerpt(
      item.file, terms,
      Math.min(CHAT_WORKSPACE_REQUEST_MAX_FILE_CHARACTERS, remainingCharacters),
    );
    const bytes = new TextEncoder().encode(excerpt.content).byteLength;
    if (bytes > remainingBytes || excerpt.content.length > remainingCharacters) continue;
    result.push({name, content:excerpt.content});
    names.add(name.toLocaleLowerCase());
    workspace.lastSelection.push({name, characters:excerpt.content.length, truncated:excerpt.truncated});
    remainingCharacters -= excerpt.content.length;
    remainingBytes -= bytes;
  }
  return result;
}

function renderChatContextPack() {
  const panel = $("chatContextPack");
  const list = $("chatContextFiles");
  const files = state.chatContextFiles;
  const workspace = state.chatWorkspaceContext;
  const locked = chatContextLocked();
  const ready = state.runPhase === "running" && Boolean(state.chatRunId);
  const totalBytes = files.reduce((total, file) => total + file.bytes, 0);
  panel.classList.toggle("hidden", files.length === 0 && !workspace);
  const parts = [];
  if (files.length) parts.push(`${files.length} attached · ${formatBytes(totalBytes)}`);
  if (workspace) parts.push(`${workspace.files.length} workspace files indexed locally`);
  $("chatContextPackSummary").textContent = parts.join(" · ") || "No files or workspace selected";
  $("chatContextClear").disabled = locked || (!files.length && !workspace);
  $("chatAttachButton").disabled = !ready || locked || files.length >= CHAT_CONTEXT_MAX_FILES;
  $("chatAttachButton").title = locked
    ? "Context files are locked while a response or queued turn is in flight"
    : `Attach up to ${CHAT_CONTEXT_MAX_FILES} local text files`;
  $("chatWorkspaceButton").disabled = !ready || locked;
  $("chatWorkspaceButton").title = locked
    ? "Workspace Context is locked while a response or queued turn is in flight"
    : "Choose one folder to index locally in this browser tab";
  $("chatWorkspaceContext").classList.toggle("hidden", !workspace);
  $("chatWorkspaceClear").disabled = locked || !workspace;
  if (workspace) {
    const excluded = workspace.stats.selected - workspace.stats.indexed;
    $("chatWorkspaceName").textContent = workspace.root;
    $("chatWorkspaceSummary").textContent = `${workspace.files.length} indexed · ${formatBytes(workspace.totalBytes)} · ${excluded} excluded${workspace.stats.sensitive ? ` · ${workspace.stats.sensitive} secret-risk blocked` : ""}`;
    $("chatWorkspaceSelection").textContent = workspace.lastSelection.length
      ? `${workspace.lastSelection.length} relevant file${workspace.lastSelection.length === 1 ? "" : "s"} sent in the latest request · ${formatNumber(workspace.lastBudget)}-character estimated retrieval budget`
      : "No folder text sent yet; a bounded relevant subset is chosen separately for each message.";
  }
  list.innerHTML = files.map(file => `
    <div class="chat-context-file">
      <span aria-hidden="true">TXT</span>
      <div><strong title="${esc(file.name)}">${esc(file.name)}</strong><small>${formatBytes(file.bytes)} · ${formatNumber(file.characters)} characters</small></div>
      <button type="button" data-chat-context-remove="${esc(file.id)}" aria-label="Remove ${esc(file.name)} from the Context Pack"${locked ? " disabled" : ""}>×</button>
    </div>
  `).join("");
}

function supportedChatContextFile(file) {
  const type = String(file?.type || "").toLowerCase();
  const basename = String(file?.name || "").split(/[\\/]/).at(-1)?.toLowerCase() || "";
  const extension = basename.includes(".") ? basename.split(".").pop() || "" : "";
  return type.startsWith("text/")
    || CHAT_CONTEXT_TEXT_BASENAMES.has(basename)
    || [...CHAT_CONTEXT_TEXT_BASENAMES].some(name => basename.startsWith(`${name}.`))
    || CHAT_CONTEXT_TEXT_EXTENSIONS.has(extension)
    || new Set([
      "application/json", "application/ld+json", "application/xml",
      "application/javascript", "application/x-javascript",
      "application/yaml", "application/x-yaml", "application/toml",
    ]).has(type);
}

async function addChatContextFiles(fileList) {
  const selected = Array.from(fileList || []);
  if (!selected.length || chatContextLocked()) return;
  state.chatContextBusy = true;
  renderChatContextPack();
  try {
    if (state.chatContextFiles.length + selected.length > CHAT_CONTEXT_MAX_FILES) {
      throw new Error(`A Context Pack may contain at most ${CHAT_CONTEXT_MAX_FILES} text files.`);
    }
    const proposed = state.chatContextFiles.map(file => ({...file}));
    const seen = new Set(proposed.map(file => file.name.toLocaleLowerCase()));
    let totalBytes = proposed.reduce((total, file) => total + file.bytes, 0);
    let totalCharacters = proposed.reduce((total, file) => total + file.characters, 0);
    for (const file of selected) {
      const name = String(file?.name || "").trim();
      if (
        !name || name.length > 320 || /[\\/]/.test(name)
        || /[\u0000-\u001f\u007f]/.test(name) || name === "." || name === ".."
      ) throw new Error("Choose text files with ordinary visible file names.");
      if (seen.has(name.toLocaleLowerCase())) {
        throw new Error(`“${name}” is already in this Context Pack.`);
      }
      if (!supportedChatContextFile(file)) {
        throw new Error(`“${name}” is not a supported text or source-code file.`);
      }
      if (Number(file.size || 0) > CHAT_CONTEXT_MAX_FILE_BYTES) {
        throw new Error(`“${name}” is larger than 512 KB. Attach a smaller text extract.`);
      }
      const content = await file.text();
      if (!content.trim()) throw new Error(`“${name}” is empty.`);
      if (content.includes("\u0000")) throw new Error(`“${name}” does not look like a text file.`);
      const bytes = new TextEncoder().encode(content).byteLength;
      if (bytes > CHAT_CONTEXT_MAX_FILE_BYTES) {
        throw new Error(`“${name}” is larger than 512 KB after text decoding.`);
      }
      totalBytes += bytes;
      totalCharacters += content.length;
      if (totalBytes > CHAT_CONTEXT_MAX_BYTES) {
        throw new Error("Context Pack files may total at most 1.5 MB.");
      }
      if (totalCharacters > CHAT_CONTEXT_MAX_CHARACTERS) {
        throw new Error(`Context Pack files may total at most ${formatNumber(CHAT_CONTEXT_MAX_CHARACTERS)} characters.`);
      }
      proposed.push({
        id:`context-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        name, content, bytes, characters:content.length,
      });
      seen.add(name.toLocaleLowerCase());
    }
    state.chatContextFiles = proposed;
    showNotice(
      `Attached ${selected.length} local text file${selected.length === 1 ? "" : "s"}. `
      + "They are request-only reference data and will not be saved to Chat History.",
    );
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    state.chatContextBusy = false;
    $("chatContextFileInput").value = "";
    renderChatContextPack();
    setChatBusy(Boolean(state.chatAbort));
  }
}

async function addChatWorkspaceFolder(fileList) {
  const selected = Array.from(fileList || []);
  if (!selected.length || chatContextLocked()) return;
  state.chatContextBusy = true;
  renderChatContextPack();
  const stats = {
    selected:selected.length, indexed:0, ignored:0, sensitive:0, generated:0,
    unsupported:0, empty:0, large:0, invalid:0, binary:0, limit:0, budget:0,
  };
  try {
    const candidates = [];
    const roots = new Set();
    for (const file of selected) {
      const path = normaliseChatWorkspacePath(file);
      if (!path) { stats.invalid += 1; continue; }
      roots.add(path.root);
      const policy = chatWorkspacePathPolicy(path.name, file);
      if (policy !== "ready") { stats[policy] += 1; continue; }
      candidates.push({file, ...path, priority:chatWorkspaceCandidatePriority(path.name)});
    }
    if (roots.size !== 1) throw new Error("Choose one workspace folder at a time.");
    candidates.sort((left, right) => (
      right.priority - left.priority
      || Number(left.file.size || 0) - Number(right.file.size || 0)
      || left.name.localeCompare(right.name)
    ));
    if (candidates.length > CHAT_WORKSPACE_INDEX_MAX_FILES) {
      stats.limit = candidates.length - CHAT_WORKSPACE_INDEX_MAX_FILES;
      candidates.length = CHAT_WORKSPACE_INDEX_MAX_FILES;
    }
    const files = [];
    let totalBytes = 0;
    for (const candidate of candidates) {
      const content = await candidate.file.text();
      if (!content.trim()) { stats.empty += 1; continue; }
      if (content.includes("\u0000")) { stats.binary += 1; continue; }
      const bytes = new TextEncoder().encode(content).byteLength;
      if (bytes > CHAT_CONTEXT_MAX_FILE_BYTES) { stats.large += 1; continue; }
      if (totalBytes + bytes > CHAT_WORKSPACE_INDEX_MAX_BYTES) { stats.budget += 1; continue; }
      files.push({
        id:`workspace-${files.length}-${Date.now()}`,
        name:candidate.name,
        content,
        searchText:`${candidate.name}\n${content}`.toLocaleLowerCase(),
        bytes,
        characters:content.length,
        priority:candidate.priority,
      });
      totalBytes += bytes;
    }
    if (!files.length) {
      throw new Error("No supported, non-sensitive text files remained after the workspace safety checks.");
    }
    stats.indexed = files.length;
    state.chatWorkspaceContext = {
      root:[...roots][0], files, totalBytes, stats, lastSelection:[], lastBudget:0,
    };
    const excluded = stats.selected - stats.indexed;
    showNotice(
      `Indexed ${files.length} text file${files.length === 1 ? "" : "s"} from “${state.chatWorkspaceContext.root}” in this browser tab. `
      + `${excluded} excluded by type, size, generated-folder, or secret-file rules.`,
    );
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    state.chatContextBusy = false;
    $("chatWorkspaceFolderInput").value = "";
    renderChatContextPack();
    setChatBusy(Boolean(state.chatAbort));
  }
}

function removeChatContextFile(fileId) {
  if (chatContextLocked()) return;
  state.chatContextFiles = state.chatContextFiles.filter(file => file.id !== fileId);
  renderChatContextPack();
}

function chatScrollMetrics(container = $("chatMessages")) {
  return {
    scrollHeight:container?.scrollHeight || 0,
    scrollTop:container?.scrollTop || 0,
    clientHeight:container?.clientHeight || 0,
  };
}

function updateChatScrollUi() {
  const container = $("chatMessages");
  const button = $("chatJumpLatest");
  if (!container || !button) return;
  const metrics = ChatScrollCore.normaliseMetrics(chatScrollMetrics(container));
  const show = Boolean(
    state.chatMessages.length
    && metrics.maximumTop > ChatScrollCore.FOLLOW_THRESHOLD
    && !state.chatFollowOutput,
  );
  button.classList.toggle("hidden", !show);
  $("chatJumpLatestStatus").textContent = state.chatAbort
    ? "Response continues below"
    : "Newest message is below";
}

function scrollChatToLatest({smooth = false} = {}) {
  const container = $("chatMessages");
  if (!container) return;
  state.chatFollowOutput = true;
  container.scrollTo({
    top:container.scrollHeight,
    behavior:smooth && !reducedMotion() ? "smooth" : "auto",
  });
  updateChatScrollUi();
}

function chatTranscriptMatches() {
  return ChatTranscriptCore.searchMessages(state.chatMessages, state.chatTranscriptQuery);
}

function renderChatTranscriptToolbar(matches = chatTranscriptMatches()) {
  const userTurns = state.chatMessages.filter(message => message.role === "user").length;
  const messages = state.chatMessages.length;
  $("chatTranscriptToolbar").dataset.empty = String(!messages);
  $("chatTranscriptCount").textContent = messages
    ? `${formatNumber(userTurns)} turn${userTurns === 1 ? "" : "s"} · ${formatNumber(messages)} message${messages === 1 ? "" : "s"}`
    : "No turns yet";
  const open = state.chatTranscriptSearchOpen;
  const toggle = $("chatTranscriptSearchToggle");
  const panel = $("chatTranscriptSearch");
  toggle.hidden = open;
  toggle.disabled = !messages;
  toggle.setAttribute("aria-expanded", String(open));
  panel.hidden = !open;
  $("chatTranscriptHint").textContent = open
    ? (state.chatTranscriptQuery ? "Matching messages are marked below." : "Search final answers and emitted thinking.")
    : "Find and jump within this conversation.";
  const input = $("chatTranscriptSearchInput");
  if (input.value !== state.chatTranscriptQuery) input.value = state.chatTranscriptQuery;
  let activeIndex = matches.findIndex(match => match.id === state.chatTranscriptActiveId);
  if (matches.length && activeIndex < 0) activeIndex = 0;
  $("chatTranscriptSearchStatus").textContent = !state.chatTranscriptQuery
    ? "Type to search this conversation"
    : !matches.length
      ? "No matching messages"
      : `${formatNumber(activeIndex + 1)} of ${formatNumber(matches.length)} matching message${matches.length === 1 ? "" : "s"}`;
  $("chatTranscriptPrevious").disabled = !matches.length;
  $("chatTranscriptNext").disabled = !matches.length;
}

function clearChatTranscriptHighlights(container = $("chatMessages")) {
  container.querySelectorAll("mark[data-chat-transcript-match]").forEach(mark => {
    const parent = mark.parentNode;
    mark.replaceWith(document.createTextNode(mark.textContent || ""));
    parent?.normalize();
  });
  container.querySelectorAll(".chat-message.search-match,.chat-message.search-active").forEach(article => {
    article.classList.remove("search-match", "search-active");
  });
}

function highlightChatTranscriptText(root, rawQuery, remaining) {
  if (!root || remaining <= 0) return 0;
  const needle = String(rawQuery || "").trim().slice(0, ChatTranscriptCore.MAX_QUERY_CHARACTERS).toLocaleLowerCase();
  if (!needle) return 0;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (!node.nodeValue || node.parentElement?.closest("button,textarea,input,mark")) continue;
    if (node.nodeValue.toLocaleLowerCase().includes(needle)) nodes.push(node);
  }
  let used = 0;
  for (const node of nodes) {
    if (used >= remaining) break;
    const text = node.nodeValue;
    const folded = text.toLocaleLowerCase();
    let cursor = 0;
    const fragment = document.createDocumentFragment();
    while (cursor < text.length && used < remaining) {
      const index = folded.indexOf(needle, cursor);
      if (index < 0) break;
      if (index > cursor) fragment.append(document.createTextNode(text.slice(cursor, index)));
      const mark = document.createElement("mark");
      mark.className = "chat-transcript-match";
      mark.dataset.chatTranscriptMatch = "true";
      mark.textContent = text.slice(index, index + needle.length);
      fragment.append(mark);
      cursor = index + needle.length;
      used += 1;
    }
    if (!used || cursor === 0) continue;
    if (cursor < text.length) fragment.append(document.createTextNode(text.slice(cursor)));
    node.replaceWith(fragment);
  }
  return used;
}

function applyChatTranscriptSearch({scrollActive = false} = {}) {
  const container = $("chatMessages");
  clearChatTranscriptHighlights(container);
  const matches = chatTranscriptMatches();
  if (!state.chatTranscriptQuery || !matches.length) {
    state.chatTranscriptActiveId = "";
    renderChatTranscriptToolbar(matches);
    return;
  }
  if (!matches.some(match => match.id === state.chatTranscriptActiveId)) {
    state.chatTranscriptActiveId = matches[0].id;
  }
  let remaining = CHAT_TRANSCRIPT_HIGHLIGHT_LIMIT;
  matches.forEach(match => {
    const article = container.querySelector(`[data-chat-message-id="${CSS.escape(match.id)}"]`);
    if (!article) return;
    article.classList.add("search-match");
    if (match.id === state.chatTranscriptActiveId) {
      article.classList.add("search-active");
      if (state.chatTranscriptSearchOpen && match.fields.includes("reasoning")) {
        article.querySelector(".chat-reasoning")?.setAttribute("open", "");
      }
    }
    if (match.fields.includes("content")) {
      const used = highlightChatTranscriptText(
        article.querySelector(".chat-message-body"), state.chatTranscriptQuery, remaining,
      );
      remaining -= used;
    }
    if (match.fields.includes("reasoning") && remaining > 0) {
      const used = highlightChatTranscriptText(
        article.querySelector(".chat-reasoning-body"), state.chatTranscriptQuery, remaining,
      );
      remaining -= used;
    }
  });
  renderChatTranscriptToolbar(matches);
  if (!scrollActive) return;
  const active = matches.find(match => match.id === state.chatTranscriptActiveId);
  const article = active
    ? container.querySelector(`[data-chat-message-id="${CSS.escape(active.id)}"]`) : null;
  if (!article) return;
  if (active.fields.includes("reasoning")) article.querySelector(".chat-reasoning")?.setAttribute("open", "");
  state.chatFollowOutput = false;
  article.scrollIntoView({block:"center", behavior:reducedMotion() ? "auto" : "smooth"});
  updateChatScrollUi();
}

function openChatTranscriptSearch() {
  if (!state.chatMessages.length) return;
  state.chatTranscriptSearchOpen = true;
  state.chatFollowOutput = false;
  renderChatTranscriptToolbar();
  requestAnimationFrame(() => {
    $("chatTranscriptSearchInput").focus();
    $("chatTranscriptSearchInput").select();
  });
}

function closeChatTranscriptSearch({focusToggle = true} = {}) {
  state.chatTranscriptSearchOpen = false;
  state.chatTranscriptQuery = "";
  state.chatTranscriptActiveId = "";
  applyChatTranscriptSearch();
  if (focusToggle) $("chatTranscriptSearchToggle").focus();
}

function stepChatTranscriptMatch(direction) {
  const matches = chatTranscriptMatches();
  if (!matches.length) return;
  const current = matches.findIndex(match => match.id === state.chatTranscriptActiveId);
  const next = ChatTranscriptCore.nextMatchIndex(current, direction, matches.length);
  state.chatTranscriptActiveId = matches[next].id;
  applyChatTranscriptSearch({scrollActive:true});
}

function renderChatInline(parent, tokens) {
  (tokens || []).forEach(token => {
    if (!token || typeof token !== "object") return;
    if (token.type === "text") {
      parent.append(document.createTextNode(String(token.text || "")));
      return;
    }
    if (token.type === "break") {
      parent.append(document.createElement("br"));
      return;
    }
    if (token.type === "code") {
      const code = document.createElement("code");
      code.textContent = String(token.text || "");
      parent.append(code);
      return;
    }
    if (["strong", "emphasis", "delete"].includes(token.type)) {
      const element = document.createElement(
        token.type === "strong" ? "strong" : token.type === "emphasis" ? "em" : "del",
      );
      renderChatInline(element, token.children);
      parent.append(element);
      return;
    }
    if (token.type === "link") {
      const anchor = document.createElement("a");
      anchor.href = token.url;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      anchor.referrerPolicy = "no-referrer";
      anchor.className = token.imageReference ? "chat-image-reference" : "";
      anchor.title = `Open external link: ${token.url}`;
      renderChatInline(anchor, token.children);
      parent.append(anchor);
    }
  });
}

function renderChatMarkdown(parent, value, {pending = false} = {}) {
  parent.classList.add("markdown");
  const report = SafeMarkdownCore.parse(value);
  let codeIndex = 0;
  const renderBlocks = (target, blocks) => {
    (blocks || []).forEach(block => {
      if (!block || typeof block !== "object") return;
      if (block.type === "paragraph") {
        const paragraph = document.createElement("p");
        renderChatInline(paragraph, block.children);
        target.append(paragraph);
      } else if (block.type === "heading") {
        const heading = document.createElement(`h${Math.min(6, Math.max(3, Number(block.level || 1) + 2))}`);
        heading.className = `chat-markdown-heading level-${Math.max(1, Math.min(6, Number(block.level || 1)))}`;
        renderChatInline(heading, block.children);
        target.append(heading);
      } else if (block.type === "rule") {
        target.append(document.createElement("hr"));
      } else if (block.type === "quote") {
        const quote = document.createElement("blockquote");
        renderBlocks(quote, block.blocks);
        target.append(quote);
      } else if (block.type === "list") {
        const list = document.createElement(block.ordered ? "ol" : "ul");
        if (block.ordered && Number(block.start || 1) !== 1) list.start = Number(block.start);
        block.items.forEach(item => {
          const row = document.createElement("li");
          if (item.checked !== null) {
            row.classList.add("task");
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.checked = Boolean(item.checked);
            checkbox.disabled = true;
            checkbox.setAttribute("aria-label", item.checked ? "Completed item" : "Incomplete item");
            row.append(checkbox);
          }
          const copy = document.createElement("span");
          renderChatInline(copy, item.children);
          row.append(copy);
          list.append(row);
        });
        target.append(list);
      } else if (block.type === "code") {
        codeIndex += 1;
        const section = document.createElement("section");
        section.className = `chat-code-block${!block.closed && pending ? " streaming" : ""}`;
        const header = document.createElement("header");
        const language = document.createElement("span");
        language.textContent = block.language === "text" ? "Code" : String(block.language || "Code");
        const copy = document.createElement("button");
        copy.type = "button";
        copy.dataset.chatCodeCopy = String(codeIndex);
        copy.textContent = "Copy code";
        copy.setAttribute("aria-label", `Copy ${language.textContent} code block`);
        header.append(language, copy);
        const pre = document.createElement("pre");
        const code = document.createElement("code");
        code.textContent = String(block.text || "");
        pre.append(code);
        section.append(header, pre);
        target.append(section);
      } else if (block.type === "table") {
        const scroller = document.createElement("div");
        scroller.className = "chat-table-scroll";
        scroller.tabIndex = 0;
        const table = document.createElement("table");
        const thead = document.createElement("thead");
        const headRow = document.createElement("tr");
        block.headers.forEach((tokens, index) => {
          const cell = document.createElement("th");
          cell.style.textAlign = block.align[index] || "left";
          renderChatInline(cell, tokens);
          headRow.append(cell);
        });
        thead.append(headRow);
        const tbody = document.createElement("tbody");
        block.rows.forEach(row => {
          const tableRow = document.createElement("tr");
          row.forEach((tokens, index) => {
            const cell = document.createElement("td");
            cell.style.textAlign = block.align[index] || "left";
            renderChatInline(cell, tokens);
            tableRow.append(cell);
          });
          tbody.append(tableRow);
        });
        table.append(thead, tbody);
        scroller.append(table);
        target.append(scroller);
      } else if (block.type === "notice") {
        const notice = document.createElement("p");
        notice.className = "chat-markdown-notice";
        notice.textContent = String(block.text || "Rich display was bounded.");
        target.append(notice);
      }
    });
  };
  renderBlocks(parent, report.blocks);
}

function renderChatMessages({forceBottom = false} = {}) {
  const container = $("chatMessages");
  const renderRevision = ++state.chatRenderRevision;
  const interactionRevision = state.chatScrollInteractionRevision;
  const previousMetrics = chatScrollMetrics(container);
  const previousTop = previousMetrics.scrollTop;
  const previouslyOpenReasoning = new Set(
    [...container.querySelectorAll(".chat-reasoning[open]")]
      .map(details => details.closest("[data-chat-message-id]")?.dataset.chatMessageId)
      .filter(Boolean),
  );
  const reasoningScrollCaptures = new Map(
    [...container.querySelectorAll(".chat-reasoning[open] .chat-reasoning-body")]
      .map(body => [
        body.closest("[data-chat-message-id]")?.dataset.chatMessageId || "",
        ChatScrollCore.captureScroll(chatScrollMetrics(body)),
      ])
      .filter(([messageId]) => Boolean(messageId)),
  );
  const previouslyOpenMessageActions = new Set(
    [...container.querySelectorAll(".chat-message-more[open]")]
      .map(details => details.closest("[data-chat-message-id]")?.dataset.chatMessageId)
      .filter(Boolean),
  );
  const shouldFollow = Boolean(
    forceBottom
    || (state.chatFollowOutput && ChatScrollCore.nearBottom(previousMetrics)),
  );
  const branchBadge = $("chatBranchBadge");
  branchBadge.classList.toggle("hidden", !state.chatBranch);
  branchBadge.title = state.chatBranch
    ? `Branch of ${state.chatBranch.parentTitle || "Local chat"}` : "";
  renderChatQueue();
  renderChatUsage();
  renderChatContextPack();
  if (!state.chatMessages.length) {
    renderedMessageRows.clear();
    container.innerHTML = `<div class="chat-empty"><span aria-hidden="true">●</span><strong>Ready when you are</strong><p>Ask the selected model anything. Streamed reasoning appears in a separate panel when exposed, and completed turns are saved locally.</p></div>`;
    state.chatFollowOutput = true;
    renderChatTranscriptToolbar([]);
    updateChatScrollUi();
    return;
  }
  const nextRows = new Map(), articles = [];
  const landmarks = new Map(
    ChatTranscriptCore.turnLandmarks(state.chatMessages).map(item => [item.id, item]),
  );
  // Prefix/suffix facts preserve the original action predicates in linear time.
  const earlierUsers = [], tailRecovery = [];
  let earlierUser = false, laterBlockingTurn = false;
  state.chatMessages.forEach((message, index) => {
    earlierUsers[index] = earlierUser;
    earlierUser ||= message.role === "user" && !message.pending;
  });
  for (let index = state.chatMessages.length - 1; index >= 0; index -= 1) {
    tailRecovery[index] = !laterBlockingTurn;
    laterBlockingTurn ||= ChatStreamCore.blocksIncompleteTailRecovery(state.chatMessages[index]);
  }
  const actionsBusy = Boolean(state.chatAbort || state.chatRevisionBusy || state.chatEditingMessageId
    || state.chatHistorySaving || state.chatHistoryLoading || state.chatHistoryBusyId || state.chatHistoryMutationTail);
  const updateActions = (article, message, index) => {
    for (const button of article.querySelectorAll("[data-chat-action]")) {
      const action = button.dataset.chatAction;
      const pausedQueueRecovery = Boolean(state.chatQueuePaused && state.chatQueue.length
        && ChatStreamCore.pausedQueueRecoveryAction(action, message, tailRecovery[index]));
      const disabled = Boolean(action !== "copy" && (actionsBusy || (state.chatQueue.length && !pausedQueueRecovery)));
      if (button.disabled !== disabled) button.disabled = disabled;
    }
  };
  state.chatMessages.forEach((message, index) => {
    const landmark = landmarks.get(message.id);
    const signature = [message.id, message.role, message.content, message.reasoning, message.pending, message.stopped, message.exclude,
      message.interrupted, message.continuation, message.truncated, message.failure, message.createdAt,
      Boolean(message.usage), message.usage?.promptTokens, message.usage?.completionTokens, message.usage?.cachedPromptTokens,
      state.runStatus?.run?.model, landmark?.label, landmark?.turn, earlierUsers[index], tailRecovery[index],
      message.role === "user" && state.chatEditingMessageId === message.id];
    const cached = renderedMessageRows.get(message);
    if (cached && cached.signature.length === signature.length
        && signature.every((value, item) => value === cached.signature[item])) {
      updateActions(cached.article, message, index);
      nextRows.set(message, cached);
      articles.push(cached.article);
      return;
    }
    const article = document.createElement("article");
    article.dataset.chatMessageId = message.id;
    article.id = `chat-landmark-${message.id}`;
    article.tabIndex = -1;
    article.className = `chat-message ${message.role}${message.pending ? " pending" : ""}${message.stopped ? " stopped" : ""}${message.interrupted ? " interrupted" : ""}${message.continuation ? " continuation" : ""}${message.truncated ? " truncated" : ""}`;
    const head = document.createElement("div");
    head.className = "chat-message-head";
    const dot = document.createElement("i");
    dot.setAttribute("aria-hidden", "true");
    const label = document.createElement("span");
    label.textContent = message.role === "user" ? "You" : state.runStatus?.run?.model || "Local model";
    head.append(dot, label);
    if (landmark) {
      const badge = document.createElement("span");
      badge.className = "chat-message-landmark";
      badge.textContent = landmark.label;
      head.append(badge);
      article.dataset.chatTurn = String(landmark.turn);
    }
    const messageTime = formatChatTimestamp(message.createdAt);
    if (messageTime) {
      const time = document.createElement("time");
      time.className = "chat-message-time";
      time.dateTime = messageTime.timestamp;
      time.textContent = messageTime.short;
      time.title = messageTime.long;
      head.append(time);
    }
    if (message.interrupted) {
      const reasoningOnly = Boolean(message.role === "assistant" && message.reasoning && !message.content);
      const recovery = document.createElement("em");
      recovery.className = "chat-message-recovery";
      recovery.textContent = reasoningOnly
        ? "No final answer"
        : message.content ? "Partial answer · incomplete" : "Generation incomplete";
      recovery.title = message.failure || (reasoningOnly
        ? "The runtime emitted thinking but completed without answer text. This turn is excluded from later prompts."
        : "The model turn ended without a clean completion. Any visible partial output was preserved.");
      head.append(recovery);
    }
    if (message.truncated) {
      const limit = document.createElement("em");
      limit.className = "chat-message-limit";
      limit.textContent = "Response limit reached";
      limit.title = "The runtime reported that this answer reached the configured maximum response. Continue is a separate request.";
      head.append(limit);
    }
    if (!message.pending) {
      const actions = document.createElement("div");
      actions.className = "chat-message-actions";
      const more = document.createElement("details");
      more.className = "chat-message-more";
      more.open = previouslyOpenMessageActions.has(message.id);
      const moreSummary = document.createElement("summary");
      moreSummary.textContent = "⋯";
      moreSummary.title = `More actions for this ${message.role} message`;
      moreSummary.setAttribute("aria-label", moreSummary.title);
      const moreMenu = document.createElement("div");
      moreMenu.setAttribute("role", "menu");
      moreMenu.setAttribute("aria-label", moreSummary.title);
      more.append(moreSummary, moreMenu);
      const isMessageTail = tailRecovery[index];
      const addAction = (action, text, title = text, target = actions) => {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.chatAction = action;
        button.dataset.chatMessageId = message.id;
        button.textContent = text;
        button.title = title;
        button.setAttribute("aria-label", `${title} for this ${message.role} message`);
        const mutatesConversation = action !== "copy";
        const pausedQueueRecovery = Boolean(
          state.chatQueuePaused && state.chatQueue.length
          && ChatStreamCore.pausedQueueRecoveryAction(action, message, isMessageTail),
        );
        button.disabled = Boolean(
          mutatesConversation
          && (state.chatAbort || state.chatRevisionBusy || state.chatEditingMessageId
            || state.chatHistorySaving || state.chatHistoryLoading
            || state.chatHistoryBusyId || state.chatHistoryMutationTail
            || (state.chatQueue.length && !pausedQueueRecovery)),
        );
        if (target === moreMenu) button.setAttribute("role", "menuitem");
        target.append(button);
      };
      const addMoreAction = (action, text, title = text) => addAction(action, text, title, moreMenu);
      if (message.content) addAction("copy", "Copy");
      if (message.role === "user") {
        addMoreAction("edit", "Edit + retry", "Edit this message and retry in a new branch");
        addMoreAction("branch", "Branch", "Create a new branch through this message");
      } else {
        const hasEarlierUser = earlierUsers[index];
        const incompleteKind = ChatStreamCore.incompleteAnswerKind(message);
        if (hasEarlierUser) addMoreAction("regenerate", "Regenerate", "Generate another answer in a new branch");
        if (hasEarlierUser && ["reasoning-only", "interrupted", "failed"].includes(incompleteKind)) {
          addAction(
            "retry", incompleteKind === "failed" ? "Retry message" : "Retry answer",
            "Retry the incomplete turn and preserve any paused follow-up messages",
          );
        }
        if (hasEarlierUser && (message.content || incompleteKind === "truncated")) {
          const target = message.truncated ? actions : moreMenu;
          addAction(
            "continue",
            message.truncated ? "Continue answer" : "Continue",
            message.truncated
              ? "Continue from the runtime-reported response limit without adding a fake user turn"
              : "Continue this answer without adding a fake user turn",
            target,
          );
        }
        addMoreAction("branch", "Branch", "Create a new branch through this answer");
      }
      if (moreMenu.childElementCount) actions.append(more);
      head.append(actions);
    }
    const body = document.createElement("div");
    body.className = "chat-message-body";
    if (message.role === "assistant" && message.content) {
      renderChatMarkdown(body, message.content, {pending:message.pending});
    } else body.textContent = message.content;
    if (message.interrupted && !message.content) {
      body.setAttribute("aria-label", message.reasoning
        ? "The model emitted reasoning but no final answer."
        : "No visible model output was received before the page closed.");
    }
    article.append(head);
    const editing = message.role === "user" && state.chatEditingMessageId === message.id;
    if (editing) {
      const form = document.createElement("form");
      form.className = "chat-message-edit";
      form.dataset.chatEditForm = message.id;
      const textarea = document.createElement("textarea");
      textarea.maxLength = 2_000_000;
      textarea.value = message.content;
      textarea.setAttribute("aria-label", "Edited user message");
      const formActions = document.createElement("div");
      formActions.className = "chat-message-edit-actions";
      const retry = document.createElement("button");
      retry.type = "submit";
      retry.textContent = "Save and retry";
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.dataset.chatEditCancel = message.id;
      cancel.textContent = "Cancel";
      formActions.append(retry, cancel);
      form.append(textarea, formActions);
      article.append(form);
    } else if (message.role === "assistant" && message.reasoning) {
      const thinkingLive = Boolean(message.pending && !message.content);
      const reasoning = document.createElement("details");
      reasoning.className = `chat-reasoning${thinkingLive ? " streaming" : ""}`;
      reasoning.open = Boolean(message.pending || previouslyOpenReasoning.has(message.id));
      const summary = document.createElement("summary");
      const reasoningTitle = document.createElement("span");
      reasoningTitle.className = "chat-reasoning-title";
      reasoningTitle.textContent = thinkingLive ? "Thinking live" : "Model thinking";
      summary.append(reasoningTitle);
      const note = document.createElement("span");
      note.className = "chat-reasoning-note";
      note.textContent = thinkingLive
        ? "runtime stream"
        : message.pending ? "earlier phase · review" : "runtime-emitted · review";
      summary.append(note);
      const reasoningBody = document.createElement("div");
      reasoningBody.className = "chat-reasoning-body";
      reasoningBody.textContent = message.reasoning;
      reasoning.append(summary, reasoningBody);
      article.append(reasoning);
    }
    if (!editing && message.role === "assistant" && message.content) {
      const answerLabel = document.createElement("div");
      answerLabel.className = `chat-answer-label${message.pending ? " streaming" : ""}`;
      const answerIcon = document.createElement("i");
      answerIcon.setAttribute("aria-hidden", "true");
      answerIcon.textContent = message.pending ? "↳" : "✓";
      const answerTitle = document.createElement("span");
      answerTitle.textContent = message.pending ? "Answering live" : "Final answer";
      answerLabel.append(answerIcon, answerTitle);
      article.append(answerLabel);
    }
    if (!editing) article.append(body);
    if (!editing && message.role === "assistant" && message.failure) {
      const failure = document.createElement("div");
      failure.className = "chat-message-failure";
      failure.setAttribute("role", "status");
      failure.textContent = message.failure;
      article.append(failure);
    }
    if (!editing && message.role === "assistant" && message.usage) {
      const usage = document.createElement("div");
      usage.className = "chat-message-usage";
      const cached = Number.isInteger(message.usage.cachedPromptTokens)
        ? ` · ${formatNumber(message.usage.cachedPromptTokens)} cached`
        : "";
      usage.textContent = `${formatNumber(message.usage.promptTokens)} prompt tokens · ${formatNumber(message.usage.completionTokens)} response tokens${cached} · runtime reported`;
      article.append(usage);
    }
    nextRows.set(message, {article, signature});
    articles.push(article);
  });
  // Leave unchanged rows attached: moving them through a fragment loses focus.
  const retainedArticles = new Set(articles);
  let cursor = container.firstChild;
  for (const article of articles) {
    while (cursor && !retainedArticles.has(cursor)) {
      const next = cursor.nextSibling;
      container.removeChild(cursor);
      cursor = next;
    }
    if (cursor === article) cursor = cursor.nextSibling;
    else container.insertBefore(article, cursor);
  }
  while (cursor) {
    const next = cursor.nextSibling;
    container.removeChild(cursor);
    cursor = next;
  }
  renderedMessageRows = nextRows;
  for (const reasoningBody of container.querySelectorAll(".chat-reasoning[open] .chat-reasoning-body")) {
    const article = reasoningBody.closest("[data-chat-message-id]");
    const messageId = article?.dataset.chatMessageId || "";
    reasoningBody.scrollTop = ChatScrollCore.restoredCapturedTop(
      chatScrollMetrics(reasoningBody),
      reasoningScrollCaptures.get(messageId),
      article?.classList.contains("pending") === true,
    );
  }
  applyChatTranscriptSearch();
  requestAnimationFrame(() => {
    const scrollAction = ChatScrollCore.renderAction({
      forceBottom,
      shouldFollow,
      capturedInteractionRevision:interactionRevision,
      currentInteractionRevision:state.chatScrollInteractionRevision,
      capturedRenderRevision:renderRevision,
      currentRenderRevision:state.chatRenderRevision,
    });
    if (scrollAction === "stale") return;
    if (state.chatEditingMessageId) {
      const editing = container.querySelector(`[data-chat-message-id="${CSS.escape(state.chatEditingMessageId)}"]`);
      editing?.scrollIntoView({block:"center"});
      editing?.querySelector("textarea")?.focus();
    } else if (scrollAction === "preserve-user") {
      state.chatFollowOutput = ChatScrollCore.nearBottom(chatScrollMetrics(container));
    } else if (scrollAction === "follow") {
      state.chatFollowOutput = true;
      container.scrollTop = container.scrollHeight;
    } else {
      state.chatFollowOutput = false;
      container.scrollTop = ChatScrollCore.restoredTop(chatScrollMetrics(container), previousTop);
    }
    updateChatScrollUi();
  });
}

function renderChatQueue() {
  const box = $("chatQueue");
  if (!state.chatQueue.length) {
    box.classList.add("hidden");
    box.innerHTML = "";
    return;
  }
  if (
    state.chatQueueEditingId
    && box.querySelector(`[data-chat-queue-edit-row="${CSS.escape(state.chatQueueEditingId)}"]`)
  ) return;
  const wasOpen = Boolean(box.querySelector(".chat-queue-disclosure")?.open);
  const shouldOpen = Boolean(wasOpen || state.chatQueuePaused || state.chatQueueEditingId);
  box.classList.remove("hidden");
  box.classList.toggle("paused", state.chatQueuePaused);
  const queueStatus = state.chatQueuePaused
    ? state.chatQueueRecovered
      ? "Recovered in this tab · review and reattach context before resuming"
      : "Paused after a message could not start · review before resuming"
    : state.chatQueueStorageAvailable === false
      ? "Waiting in memory · this browser blocked refresh recovery"
      : "Saved in this tab · sends in order after the current response";
  const resumeDisabled = Boolean(
    !state.chatQueuePaused || state.chatAbort || state.chatQueueEditingId
    || state.chatRevisionBusy || state.chatContextBusy || state.chatHistorySaving
    || state.chatHistoryLoading || state.chatHistoryBusyId
    || state.chatPostmortem || state.runPhase !== "running" || !state.chatRunId,
  );
  const nextPreview = String(state.chatQueue[0]?.content || "")
    .replace(/\s+/g, " ").trim().slice(0, 90) || "Waiting message";
  const queueTitle = state.chatQueuePaused
    ? "Queue paused · review required"
    : `${state.chatQueue.length} message${state.chatQueue.length === 1 ? "" : "s"} queued`;
  box.innerHTML = `<details class="chat-queue-disclosure"${shouldOpen ? " open" : ""}><summary><span class="chat-queue-summary-icon" aria-hidden="true">${state.chatQueuePaused ? "!" : "+"}</span><span class="chat-queue-summary-copy"><strong>${esc(queueTitle)}</strong><small title="${esc(nextPreview)}">Next: ${esc(nextPreview)}</small></span><em>${state.chatQueuePaused ? "Review" : "Manage"}<i aria-hidden="true">⌄</i></em></summary><div class="chat-queue-panel"><div class="chat-queue-head"><small>${esc(queueStatus)}</small><div class="chat-queue-head-actions">${state.chatQueuePaused ? `<button type="button" class="resume" data-chat-queue-resume${resumeDisabled ? " disabled" : ""}>Resume queue</button>` : ""}<button type="button" data-chat-queue-clear>Clear queue</button></div></div><div class="chat-queue-items">${state.chatQueue.map((item, index) => {
    if (state.chatQueueEditingId === item.id) {
      return `<div class="chat-queue-item"><div class="chat-queue-edit" data-chat-queue-edit-row="${esc(item.id)}"><textarea maxlength="${CHAT_QUEUE_MAX_CHARACTERS}" aria-label="Edit queued message">${esc(item.content)}</textarea><button type="button" data-chat-queue-save="${esc(item.id)}">Save</button><button type="button" data-chat-queue-cancel="${esc(item.id)}">Cancel</button></div></div>`;
    }
    return `<div class="chat-queue-item"><div class="chat-queue-item-content"><span title="${esc(item.content)}">${esc(item.content)}</span><em>#${index + 1}</em></div><div class="chat-queue-actions"><button type="button" title="Move earlier" aria-label="Move queued message earlier" data-chat-queue-move="${esc(item.id)}" data-chat-queue-direction="-1"${index === 0 ? " disabled" : ""}>↑</button><button type="button" title="Move later" aria-label="Move queued message later" data-chat-queue-move="${esc(item.id)}" data-chat-queue-direction="1"${index === state.chatQueue.length - 1 ? " disabled" : ""}>↓</button><button type="button" title="Edit" aria-label="Edit queued message" data-chat-queue-edit="${esc(item.id)}">✎</button><button type="button" title="Remove" aria-label="Remove queued message" data-chat-queue-remove="${esc(item.id)}">×</button></div></div>`;
  }).join("")}</div></div></details>`;
}

function queueChatRender() {
  if (state.chatRenderFrame !== null) return;
  state.chatRenderFrame = requestAnimationFrame(() => {
    state.chatRenderFrame = null;
    renderChatMessages();
  });
}

function setChatBusy(busy) {
  const button = $("chatSendButton");
  const retained = Boolean(state.chatPostmortem && state.chatRunId);
  const ready = state.runPhase === "running" && Boolean(state.chatRunId) && !retained;
  const revisionBusy = Boolean(state.chatRevisionBusy);
  const editingMessage = Boolean(state.chatEditingMessageId);
  const contextBusy = Boolean(state.chatContextBusy);
  const historyBusy = Boolean(
    state.chatHistorySaving || state.chatHistoryLoading || state.chatHistoryBusyId,
  );
  button.disabled = !ready || revisionBusy || editingMessage || contextBusy || historyBusy;
  button.classList.remove("stopping");
  const queueMode = busy || state.chatQueue.length > 0;
  button.querySelector("strong").textContent = queueMode ? "Queue" : "Send";
  button.querySelector("span").textContent = queueMode ? "+" : "↑";
  $("chatStopButton").classList.toggle("hidden", !busy || retained);
  $("chatStopButton").disabled = !busy || retained || state.chatStopBusy;
  $("chatStopButton").textContent = state.chatStopBusy ? "Stopping…" : "Stop response";
  $("chatInput").disabled = !ready || revisionBusy || editingMessage || contextBusy || historyBusy;
  $("newChatButton").disabled = (!ready && !retained) || busy || (state.chatQueue.length > 0 && !state.chatQueuePaused) || revisionBusy || editingMessage || contextBusy || historyBusy;
  $("newChatButton").textContent = retained ? "Close transcript" : "New chat";
  const sidebarNew = $("chatSidebarNew");
  sidebarNew.disabled = $("newChatButton").disabled;
  sidebarNew.title = retained ? "Close the retained transcript" : "Start a new chat";
  sidebarNew.setAttribute?.("aria-label", sidebarNew.title);
  $("chatHistoryButton").disabled = (!ready && !retained) || revisionBusy || editingMessage || historyBusy;
  $("chatComposerHint").textContent = contextBusy
    ? "Reading and validating selected text locally…"
    : historyBusy
      ? "Finishing the local history change before another message can start…"
    : revisionBusy
    ? "Preserving the original and preparing the branch…"
    : editingMessage
      ? "Finish or cancel the message edit before sending another turn"
    : retained
      ? `${state.chatPostmortem.title} · transcript retained locally until you close or replace it`
    : busy
    ? "Generating locally · Return queues next · Stop ends only this response"
    : state.chatQueueEditingId
      ? "Finish the queued-message edit; every waiting message keeps its place"
    : state.chatQueuePaused
      ? `${state.chatQueue.length} recovered message${state.chatQueue.length === 1 ? "" : "s"} paused · review or Resume queue`
    : state.chatQueue.length
      ? `${state.chatQueue.length} message${state.chatQueue.length === 1 ? "" : "s"} waiting`
      : "Return sends · Shift+Return adds a line";
  renderChatQueue();
  renderChatContextPack();
  renderChatMessages();
  if ($("chatHistoryDialog")?.open) renderChatHistory();
  renderChatSidebar();
  renderChatDraftStatus();
}

function queueChatMessage(content) {
  const value = String(content || "");
  if (!value.trim()) return false;
  const queuedCharacters = state.chatQueue.reduce((total, item) => total + item.content.length, 0);
  if (state.chatQueue.length >= CHAT_QUEUE_MAX_MESSAGES) {
    $("chatComposerHint").textContent = `Queue full · remove one of the ${CHAT_QUEUE_MAX_MESSAGES} waiting messages`;
    return false;
  }
  if (queuedCharacters + value.length > CHAT_QUEUE_MAX_CHARACTERS) {
    $("chatComposerHint").textContent = `Queue full · waiting messages may total at most ${formatNumber(CHAT_QUEUE_MAX_CHARACTERS)} characters`;
    return false;
  }
  state.chatQueue.push({
    id:`queued-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    content:value,
  });
  persistChatQueue();
  clearChatDraft();
  setChatBusy(Boolean(state.chatAbort));
  return true;
}

async function processChatQueue(surfaceId) {
  if (
    state.chatAbort || state.chatPostmortem || state.chatQueuePaused || state.chatQueueEditingId || !state.chatQueue.length || state.runPhase !== "running"
    || state.chatHistorySaving || state.chatHistoryLoading || state.chatHistoryBusyId
    || !state.chatRunId || state.chatRunId !== surfaceId
  ) return;
  const preserveReaderPosition = !ChatScrollCore.queuedTurnShouldFollow(
    state.chatFollowOutput, chatScrollMetrics(),
  );
  const next = state.chatQueue.shift();
  persistChatQueue();
  setChatBusy(false);
  const started = await startChatTurn(next.content, {preserveReaderPosition});
  if (
    !started && state.chatRunId === surfaceId && state.runPhase === "running"
    && !state.chatQueue.some(item => item.id === next.id)
  ) {
    state.chatQueue.unshift(next);
    state.chatQueuePaused = true;
    state.chatQueueRecovered = false;
    persistChatQueue();
    setChatBusy(false);
    showNotice("The next queued message could not start, so it was put back and the queue was paused.", true);
  }
}

function resumeChatQueue() {
  if (
    !state.chatQueuePaused || !state.chatQueue.length || state.chatAbort || state.chatPostmortem
    || state.chatQueueEditingId || state.chatRevisionBusy || state.chatContextBusy
    || state.chatHistorySaving || state.chatHistoryLoading || state.chatHistoryBusyId
    || state.runPhase !== "running" || !state.chatRunId
  ) return;
  state.chatQueuePaused = false;
  state.chatQueueRecovered = false;
  persistChatQueue();
  setChatBusy(false);
  showNotice("Queue resumed explicitly. Messages will send locally in order.");
  setTimeout(() => processChatQueue(state.chatRunId), 0);
}

function moveQueuedChatMessage(messageId, direction) {
  const index = state.chatQueue.findIndex(item => item.id === messageId);
  const target = index + Number(direction || 0);
  if (index < 0 || target < 0 || target >= state.chatQueue.length) return;
  const [item] = state.chatQueue.splice(index, 1);
  state.chatQueue.splice(target, 0, item);
  persistChatQueue();
  setChatBusy(Boolean(state.chatAbort));
}

function editQueuedChatMessage(messageId) {
  if (!state.chatQueue.some(item => item.id === messageId)) return;
  state.chatQueueEditingId = messageId;
  renderChatQueue();
  requestAnimationFrame(() => $("chatQueue").querySelector("textarea")?.focus());
}

function finishQueuedChatEdit(messageId, save) {
  const item = state.chatQueue.find(candidate => candidate.id === messageId);
  if (!item) return;
  if (save) {
    const textarea = $("chatQueue").querySelector(`[data-chat-queue-edit-row="${CSS.escape(messageId)}"] textarea`);
    const value = String(textarea?.value || "");
    if (!value.trim()) {
      $("chatComposerHint").textContent = "A queued message cannot be empty";
      textarea?.focus();
      return;
    }
    const otherCharacters = state.chatQueue.reduce(
      (total, candidate) => total + (candidate.id === messageId ? 0 : candidate.content.length), 0,
    );
    if (otherCharacters + value.length > CHAT_QUEUE_MAX_CHARACTERS) {
      $("chatComposerHint").textContent = `Queue full · waiting messages may total at most ${formatNumber(CHAT_QUEUE_MAX_CHARACTERS)} characters`;
      textarea?.focus();
      return;
    }
    item.content = value;
    persistChatQueue();
  }
  state.chatQueueEditingId = "";
  setChatBusy(Boolean(state.chatAbort));
  if (!state.chatAbort && !state.chatQueuePaused) setTimeout(() => processChatQueue(state.chatRunId), 0);
}

function ensureChatHistoryId() {
  if (state.chatHistoryId) return state.chatHistoryId;
  const historyId = localUuid();
  state.chatHistoryId = historyId;
  if (state.chatRunId && state.chatDraftKey) migrateChatDraftToHistory(historyId);
  return historyId;
}

function currentChatCheckpointPayload(checkpoint) {
  if (!checkpoint || state.chatRunId !== checkpoint.surfaceId) return null;
  const messages = state.chatMessages
    .filter(message => !message.pending || message.id === checkpoint.assistantId)
    .filter(message => message.content || message.reasoning || message.interrupted || message.id === checkpoint.assistantId)
    .map(message => ({
      role:message.role,
      content:message.content || "",
      reasoning:message.reasoning || "",
      usage:message.usage || undefined,
      stopped:message.id === checkpoint.assistantId || Boolean(message.stopped),
      exclude:[checkpoint.userId, checkpoint.assistantId].includes(message.id) || Boolean(message.exclude),
      interrupted:message.id === checkpoint.assistantId || Boolean(message.interrupted),
      failure:message.failure || undefined,
      continuation:Boolean(message.continuation),
      truncated:Boolean(message.truncated),
      createdAt:message.createdAt || undefined,
    }));
  if (!messages.some(message => message.role === "user") || messages.at(-1)?.interrupted !== true) return null;
  return {
    tabId:checkpoint.tabId,
    turnId:checkpoint.turnId,
    historyId:checkpoint.historyId,
    runId:checkpoint.ownerRunId,
    attachmentId:checkpoint.surfaceId,
    messages,
    metadata:state.chatBranch ? {
      branchParentId:state.chatBranch.parentId,
      branchParentTitle:state.chatBranch.parentTitle,
      branchPoint:state.chatBranch.point,
      branchKind:state.chatBranch.kind,
    } : {},
  };
}

function scheduleChatTurnCheckpoint(checkpoint, immediate = false) {
  if (!checkpoint || state.chatTurnCheckpoint !== checkpoint) return;
  state.chatTurnCheckpointDirty = true;
  if (state.chatTurnCheckpointPromise || state.chatTurnCheckpointTimer !== null) return;
  if (immediate) {
    void flushChatTurnCheckpoint(checkpoint);
    return;
  }
  const elapsed = Date.now() - state.chatTurnCheckpointLastAt;
  const delay = Math.max(0, CHAT_TURN_CHECKPOINT_INTERVAL_MS - elapsed);
  state.chatTurnCheckpointTimer = setTimeout(() => {
    state.chatTurnCheckpointTimer = null;
    void flushChatTurnCheckpoint(checkpoint);
  }, delay);
}

async function flushChatTurnCheckpoint(checkpoint) {
  if (
    !checkpoint || state.chatTurnCheckpoint !== checkpoint
    || !state.chatTurnCheckpointDirty || state.chatTurnCheckpointPromise
  ) return;
  const payload = currentChatCheckpointPayload(checkpoint);
  if (!payload) return;
  state.chatTurnCheckpointDirty = false;
  state.chatTurnCheckpointLastAt = Date.now();
  const request = api("/api/chat/turn/checkpoint", {
    method:"POST", body:JSON.stringify(payload),
  });
  state.chatTurnCheckpointPromise = request;
  try {
    await request;
    checkpoint.persisted = true;
    state.chatTurnRecoveryAvailable = true;
  } catch (_error) {
    state.chatTurnRecoveryAvailable = false;
  } finally {
    if (state.chatTurnCheckpointPromise === request) state.chatTurnCheckpointPromise = null;
    if (state.chatTurnCheckpoint && state.chatTurnCheckpointDirty) {
      scheduleChatTurnCheckpoint(state.chatTurnCheckpoint);
    }
  }
}

function beginChatTurnCheckpoint(surfaceId, ownerRunId, user, assistant) {
  cancelChatTurnCheckpoint();
  const tabId = chatTurnTabIdentifier();
  if (state.chatTurnTabStorageAvailable === false) return null;
  const checkpoint = {
    tabId,
    turnId:localUuid(),
    historyId:ensureChatHistoryId(),
    surfaceId,
    ownerRunId,
    userId:user?.id || "",
    assistantId:assistant.id,
    persisted:false,
  };
  state.chatTurnCheckpoint = checkpoint;
  state.chatTurnCheckpointLastAt = 0;
  state.chatTurnCheckpointDirty = false;
  scheduleChatTurnCheckpoint(checkpoint, true);
  return checkpoint;
}

function cancelChatTurnCheckpoint() {
  if (state.chatTurnCheckpointTimer !== null) clearTimeout(state.chatTurnCheckpointTimer);
  state.chatTurnCheckpointTimer = null;
  state.chatTurnCheckpoint = null;
  state.chatTurnCheckpointDirty = false;
  state.chatTurnCheckpointLastAt = 0;
}

async function finishChatTurnCheckpoint(checkpoint) {
  if (!checkpoint) return;
  if (state.chatTurnCheckpoint === checkpoint) {
    if (state.chatTurnCheckpointTimer !== null) clearTimeout(state.chatTurnCheckpointTimer);
    state.chatTurnCheckpointTimer = null;
    state.chatTurnCheckpoint = null;
    state.chatTurnCheckpointDirty = false;
    state.chatTurnCheckpointLastAt = 0;
  }
  const pending = state.chatTurnCheckpointPromise;
  if (pending) await pending.catch(() => null);
}

async function clearChatTurnCheckpoint(checkpoint) {
  if (!checkpoint) return false;
  try {
    await api("/api/chat/turn/clear", {
      method:"POST",
      body:JSON.stringify({tabId:checkpoint.tabId, turnId:checkpoint.turnId}),
    });
    return true;
  } catch (_error) {
    return false;
  }
}

async function startChatTurn(content = "", options = {}) {
  const operation = options.operation === "continue" ? "continue" : "message";
  const reuseLastUser = Boolean(options.reuseLastUser);
  const recoverPausedQueue = Boolean(
    options.recoverPausedQueue && state.chatQueuePaused && state.chatQueue.length,
  );
  const preserveReaderPosition = options.preserveReaderPosition === true;
  const value = String(content || "");
  if (
    state.runPhase !== "running" || !state.chatRunId || state.chatAbort || state.chatPostmortem
    || state.chatContextBusy || state.chatHistorySaving || state.chatHistoryLoading
    || state.chatHistoryBusyId
    || (operation === "message" && !reuseLastUser && !value.trim())
  ) return false;
  state.chatTranscriptSearchOpen = false;
  state.chatTranscriptQuery = "";
  state.chatTranscriptActiveId = "";
  const turnStartedAt = new Date().toISOString();
  const surfaceId = state.chatRunId;
  const ownerRunId = state.chatOwnerRunId || surfaceId;
  const input = $("chatInput");
  let user = null;
  if (!reuseLastUser && operation !== "continue") {
    user = normaliseChatMessage({role:"user", content:value, createdAt:turnStartedAt});
    state.chatMessages.push(user);
  }
  const requestMessages = state.chatMessages
    .filter(message => (
      !message.pending && !message.exclude
      && (
        message.content
        || (
          operation === "continue" && message.role === "assistant"
          && message.truncated && String(message.reasoning || "").trim()
        )
      )
    ))
    .map(({role, content: text, reasoning}) => ({
      role,
      content:text,
      ...(role === "assistant" && reasoning ? {reasoning_content:reasoning} : {}),
    }));
  const expectedTail = operation === "continue" ? "assistant" : "user";
  if (requestMessages.at(-1)?.role !== expectedTail) {
    if (user) state.chatMessages.pop();
    showNotice(
      operation === "continue"
        ? "Choose a completed model response to continue."
        : "Choose a user message to retry.",
      true,
    );
    return false;
  }
  const retrievalQuery = value.trim()
    ? value
    : [...requestMessages].reverse().find(message => message.role === "user")?.content || "";
  let contextFiles;
  try {
    contextFiles = chatContextRequestFiles(retrievalQuery, requestMessages);
  } catch (error) {
    if (user) state.chatMessages.pop();
    showNotice(error.message, true);
    renderChatMessages();
    return false;
  }
  renderChatContextPack();
  const assistant = normaliseChatMessage({
    role:"assistant", pending:true, continuation:operation === "continue", createdAt:turnStartedAt,
  });
  const checkpointUser = user || (reuseLastUser
    ? [...state.chatMessages].reverse().find(message => message.role === "user" && !message.exclude)
    : null);
  state.chatMessages.push(assistant);
  if (!preserveReaderPosition) state.chatFollowOutput = true;
  state.chatEditingMessageId = "";
  if (user) clearChatDraft();
  const controller = new AbortController();
  state.chatAbort = controller;
  const checkpoint = beginChatTurnCheckpoint(surfaceId, ownerRunId, checkpointUser, assistant);
  let resolveTurnSettlement;
  const turnSettlement = {
    surfaceId,
    exitRequested:false,
    promise:new Promise(resolve => { resolveTurnSettlement = resolve; }),
  };
  state.chatTurnSettlement = turnSettlement;
  let turnOutcome = "incomplete";
  renderChatMessages({forceBottom:!preserveReaderPosition});
  setChatBusy(true);
  try {
    const response = await launcherApi.response("/api/chat", {
      method:"POST",
      headers:{"Content-Type":"application/json", "X-Launcher-Token":state.token},
      body:JSON.stringify({
        runId:ownerRunId,
        attachmentId:surfaceId,
        messages:requestMessages,
        operation,
        contextFiles,
      }),
      signal:controller.signal,
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || `Chat request failed (${response.status}).`);
    }
    await consumeChatResponse(response, (kind, value) => {
      if (kind === "reasoning") assistant.reasoning += value;
      else if (kind === "usage") assistant.usage = value;
      else if (kind === "truncated") assistant.truncated = true;
      else assistant.content += value;
      if (kind !== "usage") scheduleChatTurnCheckpoint(checkpoint);
      queueChatRender();
    });
    if (!assistant.content && !assistant.reasoning) throw new Error("The runtime completed without returning text or exposed reasoning.");
    if (assistant.truncated) {
      turnOutcome = "truncated";
      if (state.chatQueue.length) {
        state.chatQueuePaused = true;
        state.chatQueueRecovered = false;
        persistChatQueue();
      }
      const reasoningOnlyLimit = !ChatStreamCore.hasFinalAnswer(assistant);
      showNotice(
        `${reasoningOnlyLimit ? "The model reached its response limit before returning a final answer." : "The answer reached its response limit."}${state.chatQueue.length ? " The message queue was paused until you continue the answer." : " Choose Continue answer to finish it."}`,
        true,
      );
    } else if (!ChatStreamCore.hasFinalAnswer(assistant)) {
      assistant.content = "";
      assistant.exclude = true;
      assistant.stopped = true;
      assistant.interrupted = true;
      turnOutcome = "reasoning-only";
      if (state.chatQueue.length) {
        state.chatQueuePaused = true;
        state.chatQueueRecovered = false;
        persistChatQueue();
      }
      showNotice(
        `The model finished its reasoning without a final answer.${state.chatQueue.length ? " The message queue was paused so nothing sends against an incomplete turn." : " Send Continue or retry the message."}`,
        true,
      );
    } else turnOutcome = "complete";
  } catch (error) {
    if (error.name === "AbortError" || controller.launcherStopRequested) {
      turnOutcome = "stopped";
      if (user) user.exclude = true;
      assistant.exclude = true;
      assistant.stopped = true;
      assistant.interrupted = true;
      assistant.failure = "Generation stopped before the model returned a clean completion.";
      if (state.chatQueue.length) {
        state.chatQueuePaused = true;
        state.chatQueueRecovered = false;
        persistChatQueue();
      }
      showNotice(
        `Generation stopped.${state.chatQueue.length ? " The message queue was paused until you retry or clear the incomplete turn." : " Any partial output was preserved."}`,
        true,
      );
    } else {
      turnOutcome = "failed";
      if (user) user.exclude = true;
      assistant.exclude = true;
      assistant.stopped = true;
      assistant.interrupted = true;
      assistant.failure = normaliseChatFailure(error.message)
        || "The model turn ended without a clean completion.";
      if (state.chatQueue.length) {
        state.chatQueuePaused = true;
        state.chatQueueRecovered = false;
        persistChatQueue();
      }
      showNotice(
        `${assistant.failure}${state.chatQueue.length ? " The message queue was paused so it cannot continue against an incomplete answer." : " Any partial output was preserved."}`,
        true,
      );
    }
  } finally {
    let historySaved = false;
    let checkpointCleared = false;
    try {
      assistant.pending = false;
      if (recoverPausedQueue && turnOutcome === "complete" && state.chatQueue.length) {
        state.chatQueuePaused = false;
        state.chatQueueRecovered = false;
        persistChatQueue();
        showNotice("The incomplete answer was recovered. Queued messages will now continue in order.");
      }
      if (state.chatAbort === controller) state.chatAbort = null;
      await finishChatTurnCheckpoint(checkpoint);
      setChatBusy(false);
      renderChatMessages();
      if (state.chatRunId === surfaceId) {
        const saved = await saveCurrentChatHistory({silentFailure:turnSettlement.exitRequested});
        historySaved = Boolean(saved);
        if (saved) checkpointCleared = await clearChatTurnCheckpoint(checkpoint);
        if (state.runPhase === "running" && !turnSettlement.exitRequested) input.focus();
        if (!turnSettlement.exitRequested && ChatStreamCore.shouldDrainQueue(turnOutcome)) {
          setTimeout(() => processChatQueue(surfaceId), 0);
        }
      }
      void pollStatus();
    } finally {
      resolveTurnSettlement({
        surfaceId,
        historySaved,
        checkpointPersisted:Boolean(checkpoint?.persisted && !checkpointCleared),
        checkpoint:checkpoint ? {tabId:checkpoint.tabId, turnId:checkpoint.turnId} : null,
      });
      if (state.chatTurnSettlement === turnSettlement) state.chatTurnSettlement = null;
    }
  }
  return true;
}

function chatMessageIndex(messageId) {
  return state.chatMessages.findIndex(message => message.id === messageId);
}

async function createChatBranch(messages, sourcePoint, kind, notice) {
  if (
    state.chatAbort || state.chatHistorySaving || state.chatHistoryLoading
    || state.chatHistoryBusyId || state.chatHistoryMutationTail
    || !messages.some(message => message.role === "user")
  ) return false;
  const parent = await saveCurrentChatHistory();
  if (!parent) {
    showNotice("The original chat could not be saved, so no branch was created.", true);
    return false;
  }
  state.chatMessages = messages.map(normaliseChatMessage);
  state.chatFollowOutput = true;
  state.chatQueue = [];
  state.chatQueueEditingId = "";
  state.chatEditingMessageId = "";
  state.chatTranscriptSearchOpen = false;
  state.chatTranscriptQuery = "";
  state.chatTranscriptActiveId = "";
  state.chatHistoryId = "";
  state.chatActiveThread = null;
  state.chatBranch = {
    parentId:parent.id,
    parentTitle:parent.title || "Local chat",
    point:Math.max(1, Number(sourcePoint || messages.length)),
    kind,
  };
  state.chatContextReducedAt = kind === "recent" ? state.chatMessages.length : 0;
  renderChatMessages({forceBottom:true});
  await saveCurrentChatHistory();
  showNotice(notice || `Created a branch of “${parent.title || "Local chat"}”. The original remains in History.`);
  return true;
}

async function branchChatAt(messageId) {
  const index = chatMessageIndex(messageId);
  if (index < 0) return;
  const messages = state.chatMessages.slice(0, index + 1)
    .filter(message => !message.pending && message.content);
  await createChatBranch(
    messages, index + 1, "branch",
    "Created a new branch through the selected message. The complete original remains in History.",
  );
}

async function editAndRetryChatMessage(messageId, content) {
  const index = chatMessageIndex(messageId);
  const value = String(content || "");
  if (index < 0 || state.chatMessages[index].role !== "user" || !value.trim()) {
    showNotice("An edited message cannot be empty.", true);
    return;
  }
  const messages = state.chatMessages.slice(0, index + 1)
    .filter(message => !message.pending && message.content)
    .map(message => ({...message, usage:message.usage ? {...message.usage} : null}));
  const edited = messages.at(-1);
  edited.content = value;
  edited.createdAt = new Date().toISOString();
  edited.exclude = false;
  edited.stopped = false;
  const created = await createChatBranch(
    messages, index + 1, "edit",
    "Edited the message in a new branch. Generating from that point now; the original remains in History.",
  );
  if (created) void startChatTurn("", {reuseLastUser:true});
}

async function regenerateChatMessage(messageId) {
  const assistantIndex = chatMessageIndex(messageId);
  if (assistantIndex < 0 || state.chatMessages[assistantIndex].role !== "assistant") return;
  let userIndex = assistantIndex - 1;
  while (userIndex >= 0 && state.chatMessages[userIndex].role !== "user") userIndex -= 1;
  if (userIndex < 0) return;
  const messages = state.chatMessages.slice(0, userIndex + 1)
    .filter(message => !message.pending && message.content)
    .map(message => ({...message, usage:message.usage ? {...message.usage} : null}));
  messages.at(-1).exclude = false;
  const created = await createChatBranch(
    messages, assistantIndex + 1, "regenerate",
    "Regenerating in a new branch. The previous answer remains in the original chat.",
  );
  if (created) void startChatTurn("", {reuseLastUser:true});
}

async function retryIncompleteChatMessage(messageId) {
  const assistantIndex = chatMessageIndex(messageId);
  if (assistantIndex < 0) return;
  const selected = state.chatMessages[assistantIndex];
  const isMessageTail = !state.chatMessages.slice(assistantIndex + 1)
    .some(ChatStreamCore.blocksIncompleteTailRecovery);
  if (!ChatStreamCore.pausedQueueRecoveryAction("retry", selected, isMessageTail)) {
    showNotice("Only the latest incomplete response can be retried in place.", true);
    return;
  }
  let userIndex = assistantIndex - 1;
  while (userIndex >= 0 && state.chatMessages[userIndex].role !== "user") userIndex -= 1;
  if (userIndex < 0) {
    showNotice("The unanswered user message is no longer available to retry.", true);
    return;
  }
  if (ChatStreamCore.incompleteRecoveryOperation(selected) === "continue") {
    void startChatTurn("", {operation:"continue", recoverPausedQueue:true});
  } else {
    state.chatMessages[userIndex].exclude = false;
    void startChatTurn("", {reuseLastUser:true, recoverPausedQueue:true});
  }
}

async function continueChatMessage(messageId) {
  const selectedIndex = chatMessageIndex(messageId);
  if (selectedIndex < 0 || state.chatMessages[selectedIndex].role !== "assistant") return;
  const activeIndices = state.chatMessages
    .map((message, index) => ({message, index}))
    .filter(item => (
      !item.message.pending && !item.message.exclude
      && (
        item.message.content
        || (
          item.message.role === "assistant" && item.message.truncated
          && String(item.message.reasoning || "").trim()
        )
      )
    ));
  const selected = state.chatMessages[selectedIndex];
  const isActiveTail = activeIndices.at(-1)?.index === selectedIndex && !selected.stopped;
  const recoverPausedQueue = Boolean(
    state.chatQueuePaused && state.chatQueue.length
    && ChatStreamCore.pausedQueueRecoveryAction("continue", selected, isActiveTail),
  );
  if (!isActiveTail) {
    const messages = state.chatMessages.slice(0, selectedIndex + 1)
      .filter(message => (
        !message.pending
        && (
          message.content
          || (
            message.role === "assistant" && message.truncated
            && String(message.reasoning || "").trim()
          )
        )
      ))
      .map(message => ({...message, usage:message.usage ? {...message.usage} : null}));
    messages.at(-1).exclude = false;
    messages.at(-1).stopped = false;
    for (let index = messages.length - 2; index >= 0; index -= 1) {
      if (messages[index].role === "user") {
        messages[index].exclude = false;
        break;
      }
    }
    const created = await createChatBranch(
      messages, selectedIndex + 1, "continue",
      "Continuing the selected answer in a new branch. The original remains in History.",
    );
    if (!created) return;
  }
  void startChatTurn("", {operation:"continue", recoverPausedQueue});
}

async function copyChatMessage(messageId) {
  const message = state.chatMessages.find(item => item.id === messageId);
  if (!message?.content || !await copyLocalText(message.content)) return;
  showNotice("Message copied locally.");
}

async function copyChatCode(button) {
  const code = button.closest(".chat-code-block")?.querySelector("code")?.textContent || "";
  if (!code || button.disabled) return;
  const original = button.textContent;
  try {
    button.disabled = true;
    if (!await copyLocalText(code)) return;
    button.textContent = "Copied";
    showNotice("Code block copied locally.");
  } catch (_error) {
    showNotice("That code block could not be copied.", true);
  } finally {
    setTimeout(() => {
      if (!button.isConnected) return;
      button.textContent = original;
      button.disabled = false;
    }, 1200);
  }
}

async function runChatRevision(task) {
  if (
    state.chatAbort || state.chatRevisionBusy || state.chatHistorySaving
    || state.chatHistoryLoading || state.chatHistoryBusyId
    || state.chatHistoryMutationTail
  ) return;
  state.chatRevisionBusy = true;
  renderChatMessages();
  setChatBusy(Boolean(state.chatAbort));
  try {
    await task();
  } finally {
    state.chatRevisionBusy = false;
    renderChatMessages();
    setChatBusy(Boolean(state.chatAbort));
  }
}

async function trimChatToRecent() {
  if (state.chatAbort) return;
  let selected = state.chatMessages
    .map((message, index) => ({message, index}))
    .filter(item => !item.message.pending && !item.message.exclude && item.message.content)
    .slice(-CHAT_RECENT_MESSAGE_LIMIT);
  while (selected.length && selected[0].message.role !== "user") selected.shift();
  if (!selected.length || selected[0].index === 0) {
    showNotice("There are not enough completed turns to reduce this transcript yet.");
    return;
  }
  const messages = selected.map(item => item.message);
  await createChatBranch(
    messages, selected.at(-1).index + 1, "recent",
    `Kept the latest ${messages.length} messages in a new branch. No summary was invented; the complete transcript remains in History.`,
  );
}

function sendChat() {
  const content = $("chatInput").value;
  if (
    !content.trim() || state.runPhase !== "running" || !state.chatRunId
    || state.chatRevisionBusy || state.chatContextBusy || state.chatHistorySaving
    || state.chatHistoryLoading || state.chatHistoryBusyId
  ) return;
  if (state.chatAbort || state.chatQueue.length) {
    queueChatMessage(content);
    return;
  }
  void startChatTurn(content);
}

function chatHasPersistableTranscript() {
  return state.chatMessages
    .filter(ChatStreamCore.shouldPersistHistoryMessage)
    .some(message => message.role === "user");
}

async function saveChatBeforeNavigation(retryAction, options = {}) {
  if (!chatHasPersistableTranscript()) return true;
  const focused = document.activeElement;
  const recoveryNotice = options.recoveryAvailable
    ? " The interrupted response also remains in local recovery and can be restored after a refresh."
    : "";
  const saved = await saveCurrentChatHistory({
    failureNotice:
      `Stayed in the current chat because its local history could not be saved. `
      + `Fix the save problem, then ${retryAction}.${recoveryNotice}`,
  });
  if (saved) return true;
  requestAnimationFrame(() => {
    const target = focused?.isConnected ? focused : $("chatInput");
    if (typeof target?.focus !== "function") return;
    try { target.focus({preventScroll:true}); }
    catch (_error) { target.focus(); }
  });
  return false;
}

async function saveChatBeforeSurfaceExit(retryAction) {
  const surfaceId = state.chatRunId;
  if (!surfaceId) return true;
  if (state.chatHistoryBusyId || state.chatHistoryLoading) {
    showNotice(
      `Stayed in the current chat while its local history change finishes. Then ${retryAction}.`,
      true,
    );
    requestAnimationFrame(() => $("chatInput")?.focus());
    return false;
  }
  const hasUnsentWork = Boolean(String($("chatInput")?.value || "") || state.chatQueue.length);
  const localStateStored = persistChatSessionState();
  if (hasUnsentWork && !localStateStored) {
    showNotice(
      `Stayed in the current chat because its unfinished message or queue could not be saved in this browser tab. Fix the storage problem, then ${retryAction}.`,
      true,
    );
    requestAnimationFrame(() => $("chatInput")?.focus());
    return false;
  }
  const turn = state.chatTurnSettlement?.surfaceId === surfaceId
    ? state.chatTurnSettlement : null;
  if (turn) turn.exitRequested = true;
  if (state.chatQueue.length) {
    state.chatQueuePaused = true;
    state.chatQueueRecovered = false;
    persistChatQueue();
    setChatBusy(Boolean(state.chatAbort));
  }
  if (state.chatAbort) state.chatAbort.abort();
  const outcome = turn ? await turn.promise : null;
  if (outcome?.historySaved) return true;
  const saved = await saveChatBeforeNavigation(retryAction, {
    recoveryAvailable:Boolean(outcome?.checkpointPersisted),
  });
  if (saved && outcome?.checkpoint) await clearChatTurnCheckpoint(outcome.checkpoint);
  return saved;
}

async function newChat() {
  if (
    state.chatAbort || state.chatRevisionBusy || state.chatEditingMessageId
    || state.chatHistoryBusyId || state.chatHistoryLoading
    || state.chatHistorySaving || state.chatHistoryMutationTail
  ) return;
  persistChatSessionState();
  if (!await saveChatBeforeNavigation("choose New chat again")) return;
  if (state.chatAbort) state.chatAbort.abort();
  const closeRetained = Boolean(state.chatPostmortem);
  const surfaceId = state.chatRunId;
  resetChatConversation();
  if (closeRetained) {
    state.chatRunId = "";
    state.chatOwnerRunId = "";
    state.chatAttachment = null;
    state.chatAttachmentObserved = false;
    $("chatInput").value = "";
    sizeChatInput();
    renderChatDraftStatus();
    updateChatWorkspace(state.runStatus?.run, state.runPhase);
    updateAgentWorkspace(state.runStatus?.run, state.runPhase);
  } else if (surfaceId) activateChatDraft(surfaceId, {restore:false});
  renderChatMessages();
  renderChatSidebar();
  if (!closeRetained) renderChatRoute(state.runStatus?.run);
  if (!closeRetained && state.runPhase === "running") $("chatInput").focus();
}

function currentChatHistoryPayload() {
  const messages = state.chatMessages
    .filter(ChatStreamCore.shouldPersistHistoryMessage)
    .map(message => ({
      role:message.role,
      content:message.content,
      reasoning:message.reasoning || "",
      usage:message.usage || undefined,
      stopped:Boolean(message.stopped),
      exclude:Boolean(message.exclude),
      interrupted:Boolean(message.interrupted),
      failure:message.failure || undefined,
      continuation:Boolean(message.continuation),
      truncated:Boolean(message.truncated),
      createdAt:message.createdAt || undefined,
    }));
  if (!messages.some(message => message.role === "user")) return null;
  const run = state.runStatus?.run || state.chatAttachment || {};
  return {
    // A failed save must not turn an unsaved transcript into a phantom
    // history entry or migrate its draft key. Commit both only after the
    // backend accepts the record in saveCurrentChatHistory().
    id:state.chatHistoryId || localUuid(),
    runId:state.chatOwnerRunId || state.runStatus?.run?.runId || "",
    attachmentId:state.chatRunId || "",
    messages,
    metadata:{
      model:run.model || "Local model",
      backend:run.backend || "local",
      context:Number(run.context || 0) || undefined,
      output:Number(run.output || 0) || undefined,
      reasoning:run.reasoning || "auto",
      ...(state.chatBranch ? {
        branchParentId:state.chatBranch.parentId,
        branchParentTitle:state.chatBranch.parentTitle,
        branchPoint:state.chatBranch.point,
        branchKind:state.chatBranch.kind,
      } : {}),
    },
  };
}

async function runChatHistoryMutation(operation) {
  // Claim a place synchronously, before the caller can yield. A boolean
  // "saving" flag leaves a one-microtask gap in which two first saves can both
  // invent different IDs, or a delete can race a late auto-save and resurrect
  // the conversation. Every history write now observes one ordered tail.
  const preceding = state.chatHistoryMutationTail;
  let release;
  const barrier = new Promise(resolve => { release = resolve; });
  state.chatHistoryMutationTail = barrier;
  if (preceding) await preceding;
  try {
    return await operation();
  } finally {
    release();
    if (state.chatHistoryMutationTail === barrier) state.chatHistoryMutationTail = null;
  }
}

async function saveCurrentChatHistory(options = {}) {
  return runChatHistoryMutation(async () => {
    // Construct only after every earlier mutation has committed. A second
    // first-save therefore reuses the ID assigned by the first one.
    const payload = currentChatHistoryPayload();
    if (!payload) return null;
    const surfaceId = state.chatRunId;
    const previousId = state.chatHistoryId;
    state.chatHistorySaving = true;
    setChatBusy(Boolean(state.chatAbort));
    let saved = false;
    try {
      const data = await api("/api/chat/history/save", {
        method:"POST", body:JSON.stringify(payload),
      });
      state.chatHistoryThreads = Array.isArray(data.threads) ? data.threads : state.chatHistoryThreads;
      if (state.chatRunId === surfaceId && state.chatHistoryId === previousId) {
        state.chatHistoryId = data.thread.id;
        state.chatActiveThread = chatThreadSummary(data.thread);
        migrateChatDraftToHistory(data.thread.id);
        renderChatRoute(state.runStatus?.run);
      }
      renderChatSidebar();
      renderQuickStart();
      saved = true;
      return data.thread;
    } catch (error) {
      const failureNotice = typeof options.failureNotice === "string"
        ? options.failureNotice.trim() : "";
      if (!options.silentFailure) {
        showNotice(
          failureNotice
            ? `${failureNotice} Save error: ${error.message}`
            : `The chat completed, but local history could not be saved: ${error.message}`,
          true,
        );
      }
      return null;
    } finally {
      state.chatHistorySaving = false;
      setChatBusy(Boolean(state.chatAbort));
      // Rebuilding the sidebar after a failed save would detach the control the
      // user just activated and lose keyboard focus. No visible history state
      // changed on failure, so redraw only after a committed save.
      if (saved && $("chatHistoryDialog")?.open) renderChatHistory();
      if (saved) renderChatSidebar();
    }
  });
}

async function waitForChatHistorySave() {
  const pending = state.chatHistoryMutationTail;
  if (pending) await pending;
}

function chatHistoryDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Saved locally" : date.toLocaleString([], {
    month:"short", day:"numeric", hour:"2-digit", minute:"2-digit",
  });
}

function chatThreadSummary(thread = {}) {
  return {
    id:String(thread.id || ""),
    title:String(thread.title || "Local chat"),
    model:String(thread.model || "Local model"),
    backend:String(thread.backend || "local"),
    context:Number(thread.context || 0),
    output:Number(thread.output || 0),
    reasoning:String(thread.reasoning || "auto"),
    originModel:String(thread.originModel || thread.model || "Local model"),
    originBackend:String(thread.originBackend || thread.backend || "local"),
    originContext:Number(thread.originContext || thread.context || 0),
    originOutput:Number(thread.originOutput || thread.output || 0),
    originReasoning:String(thread.originReasoning || thread.reasoning || "auto"),
    hasInterruptedTurn:Boolean(
      thread.hasInterruptedTurn
      || (thread.messages || []).some(message => message?.interrupted === true)
    ),
  };
}

function chatBranchKindLabel(kind) {
  return ({
    edit:"Edited retry", regenerate:"Regenerated answer", continue:"Continued answer",
    recent:"Recent-turn branch", branch:"Branch",
  })[kind] || "Branch";
}

function chatHistoryMatches(thread, query) {
  if (!query) return true;
  return [
    thread.title, thread.model, thread.backend, thread.preview, thread.branchParentTitle,
    thread.originModel, thread.originBackend,
  ].some(value => String(value || "").toLocaleLowerCase().includes(query));
}

function renderChatSidebarVisibility() {
  const layout = $("chatLayout");
  const toggle = $("chatSidebarToggle");
  if (!layout || !toggle) return;
  layout.classList.toggle("sidebar-closed", state.chatSidebarCollapsed);
  toggle.setAttribute("aria-expanded", state.chatSidebarCollapsed ? "false" : "true");
  toggle.textContent = state.chatSidebarCollapsed ? "Chats" : "Hide chats";
}

function chatUnsavedDrafts(query = "", queueEnvelope = readChatQueueEnvelope()) {
  if (
    !state.chatRunId
    || (state.chatDraftStorageAvailable === false && state.chatQueueStorageAvailable === false)
  ) return [];
  const draftEnvelope = readChatDraftEnvelope();
  const keys = new Set([
    ...Object.keys(draftEnvelope.drafts),
    ...Object.keys(queueEnvelope.queues || {}),
  ].filter(key => isPortableChatDraftKey(key)));
  const drafts = [...keys].map(key => {
    const draft = draftEnvelope.drafts[key];
    const queue = ChatQueueCore.readQueue(queueEnvelope, key, CHAT_QUEUE_OPTIONS);
    return {
      key,
      text:String(draft?.text || ""),
      queue,
      updatedAt:Math.max(Number(draft?.updatedAt || 0), Number(queueEnvelope.queues[key]?.updatedAt || 0)),
    };
  })
    .filter(item => item.text || item.queue.length)
    .filter(item => !query || `${item.text} ${item.queue.map(entry => entry.content).join(" ")}`.toLocaleLowerCase().includes(query))
    .sort((left, right) => right.updatedAt - left.updatedAt);
  return drafts.slice(0, CHAT_DRAFT_OPTIONS.maximumDrafts);
}

function renderChatSidebar() {
  const list = $("chatSidebarList");
  if (!list) return;
  const query = state.chatSidebarQuery.trim().toLocaleLowerCase();
  const matches = state.chatHistoryThreads.filter(thread => chatHistoryMatches(thread, query));
  const visible = matches.slice(0, 30);
  const queueEnvelope = readChatQueueEnvelope();
  const unsavedDrafts = chatUnsavedDrafts(query, queueEnvelope);
  const visibleIds = new Set(visible.map(thread => thread.id));
  if (state.chatSidebarMenuId && !visibleIds.has(state.chatSidebarMenuId)) state.chatSidebarMenuId = "";
  if (state.chatSidebarEditingId && !visibleIds.has(state.chatSidebarEditingId)) state.chatSidebarEditingId = "";
  const historyLocked = Boolean(state.chatAbort || state.chatRevisionBusy || state.chatEditingMessageId);
  const historyRequestBusy = Boolean(state.chatHistoryBusyId);
  const canOpen = state.runPhase === "running" && Boolean(state.chatRunId)
    && !historyLocked && !historyRequestBusy;
  $("chatSidebarStatus").textContent = state.chatHistoryLoading
    ? "Loading local history…"
    : query
      ? `${matches.length + unsavedDrafts.length} matching · local only`
      : `${state.chatHistoryThreads.length} chat${state.chatHistoryThreads.length === 1 ? "" : "s"}${unsavedDrafts.length ? ` · ${unsavedDrafts.length} unsent session${unsavedDrafts.length === 1 ? "" : "s"}` : ""}`;
  $("chatSidebarClearSearch").disabled = !state.chatSidebarQuery;
  const draftMarkup = unsavedDrafts.map(draft => {
    const preview = (draft.text || draft.queue[0]?.content || "Unfinished message").replace(/\s+/g, " ").trim().slice(0, 100);
    const active = !state.chatHistoryId && draft.key === state.chatDraftKey;
    const paused = Boolean(draft.queue.length && (!active || state.chatQueuePaused));
    const queueCopy = draft.queue.length
      ? ` · ${draft.queue.length} ${paused ? "paused" : "waiting"}` : "";
    const label = draft.text ? "Unsent draft" : paused ? "Paused queue" : "Waiting queue";
    const queueAria = draft.queue.length
      ? `${draft.queue.length} ${paused ? "paused" : "waiting"} message${draft.queue.length === 1 ? "" : "s"}`
      : "Draft";
    return `<button type="button" class="chat-sidebar-item draft" data-chat-sidebar-draft="${esc(draft.key)}" aria-current="${active ? "page" : "false"}"${canOpen ? "" : " disabled"}><span><strong>${label}</strong><small title="${esc(preview)}">${esc(preview)}</small><small>${esc(`${chatHistoryDate(draft.updatedAt)} · this tab only${queueCopy}`)}</small></span><em aria-label="${queueAria}">${draft.queue.length ? `${draft.queue.length}q` : "✎"}</em></button>`;
  }).join("");
  const threadMarkup = visible.map(thread => {
    const active = thread.id === state.chatHistoryId;
    const menuOpen = thread.id === state.chatSidebarMenuId;
    const editing = thread.id === state.chatSidebarEditingId;
    const confirming = thread.id === state.chatHistoryDeleteConfirmId;
    const actionBusy = thread.id === state.chatHistoryBusyId;
    const title = esc(thread.title || "Local chat");
    const actionDisabled = historyLocked || historyRequestBusy ? " disabled" : "";
    const exportDisabled = historyRequestBusy ? " disabled" : "";
    const branch = thread.branchParentId ? ` · ${chatBranchKindLabel(thread.branchKind)}` : "";
    const routeChanged = thread.originModel && (
      thread.originModel !== thread.model || thread.originBackend !== thread.backend
    );
    const route = `${profileBackendLabel(thread.backend)} · ${thread.model || "Local model"}`;
    const queued = chatQueueCount(queueEnvelope, chatHistoryDraftKey(thread.id));
    const interrupted = Boolean(thread.hasInterruptedTurn);
    const queuePaused = Boolean(queued && (!active || state.chatQueuePaused));
    const queueAria = queued
      ? `${queued} ${queuePaused ? "paused" : "waiting"} message${queued === 1 ? "" : "s"}`
      : interrupted ? "Interrupted turn recovered" : thread.pinned ? "Pinned" : routeChanged ? "Route changed" : "";
    const status = `${chatHistoryDate(thread.updatedAt)}${branch}${interrupted ? " · interrupted turn recovered" : ""}${queued ? ` · ${queued} ${queuePaused ? "paused" : "waiting"}` : ""}`;
    return `<article class="chat-sidebar-thread${active ? " active" : ""}${menuOpen ? " menu-open" : ""}${editing ? " editing" : ""}" data-chat-sidebar-thread="${esc(thread.id)}"${actionBusy ? ` aria-busy="true"` : ""}><div class="chat-sidebar-row"><button type="button" class="chat-sidebar-item" data-chat-sidebar-open="${esc(thread.id)}" aria-current="${active ? "page" : "false"}"${canOpen ? "" : " disabled"}><span><strong title="${title}">${title}</strong><small title="${esc(route)}">${esc(route)}</small><small>${esc(status)}</small></span><em aria-label="${queueAria}">${queued ? `${queued}q` : interrupted ? "!" : thread.pinned ? "★" : routeChanged ? "◇" : ""}</em></button><button type="button" class="chat-sidebar-more" data-chat-sidebar-menu-toggle="${esc(thread.id)}" aria-haspopup="menu" aria-expanded="${menuOpen ? "true" : "false"}" aria-controls="chat-sidebar-actions-${esc(thread.id)}" aria-label="Actions for ${title}"${historyRequestBusy ? " disabled" : ""}><span aria-hidden="true">⋯</span></button></div>${editing ? `<form class="chat-sidebar-rename" data-chat-sidebar-rename-form="${esc(thread.id)}"><label class="sr-only" for="chat-sidebar-title-${esc(thread.id)}">Chat title</label><input id="chat-sidebar-title-${esc(thread.id)}" type="text" maxlength="72" value="${title}" required><button type="submit">Save</button><button type="button" data-chat-sidebar-cancel-rename="${esc(thread.id)}">Cancel</button></form>` : menuOpen ? `<div id="chat-sidebar-actions-${esc(thread.id)}" class="chat-sidebar-actions" role="menu" aria-label="Actions for ${title}"><button type="button" role="menuitem" data-chat-sidebar-pin="${esc(thread.id)}" data-chat-sidebar-pinned="${thread.pinned ? "true" : "false"}"${actionDisabled}>${thread.pinned ? "Unpin" : "Pin"}</button><button type="button" role="menuitem" data-chat-sidebar-rename="${esc(thread.id)}"${actionDisabled}>Rename</button><button type="button" role="menuitem" data-chat-sidebar-export="${esc(thread.id)}"${exportDisabled}>Export</button><button type="button" role="menuitem" class="delete${confirming ? " confirming" : ""}" data-chat-sidebar-delete="${esc(thread.id)}"${actionDisabled}>${confirming ? "Confirm delete" : "Delete"}</button></div>` : ""}</article>`;
  }).join("");
  list.innerHTML = state.chatHistoryLoading && !state.chatHistoryLoaded
    ? `<div class="chat-sidebar-empty">Reading launcher-local conversations…</div>`
    : draftMarkup || threadMarkup ? `${draftMarkup}${threadMarkup}`
      : `<div class="chat-sidebar-empty">${query ? "No chats match this search." : "Completed turns will appear here automatically."}</div>`;
  renderChatSidebarVisibility();
}

async function openUnsavedChatDraft(key) {
  if (
    state.chatAbort || state.chatRevisionBusy || state.chatEditingMessageId
    || state.chatHistoryBusyId || state.chatHistoryLoading
    || state.chatHistorySaving || state.chatHistoryMutationTail
    || state.runPhase !== "running" || !state.chatRunId
    || !isPortableChatDraftKey(key)
  ) return;
  if (!state.chatHistoryId && key === state.chatDraftKey) {
    $("chatInput").focus();
    return;
  }
  persistChatSessionState();
  if (!await saveChatBeforeNavigation("open that unsent draft again")) return;
  const surfaceId = state.chatRunId;
  resetChatConversation();
  activateChatDraft(surfaceId, {key, restore:true});
  renderChatMessages();
  renderChatSidebar();
  renderChatRoute(state.runStatus?.run);
  showNotice("Reopened an unsent draft from this browser tab. No message was transmitted.");
  $("chatInput").focus();
}

function chatSurfaceRoute(run) {
  const source = state.chatAttachment?.client === "chat" ? state.chatAttachment : run;
  if (!source) return null;
  return {
    model:String(source.model || "Local model"),
    backend:String(source.backend || "local"),
    routeKind:String(source.routeKind || "local"),
    context:Number(source.context || 0),
    output:Number(source.output || 0),
    reasoning:String(source.reasoning || "auto"),
  };
}

function chatRunSettingsSurfaceKey() {
  if (!state.chatOwnerRunId || !state.chatRunId) return "";
  return `${state.chatOwnerRunId}:${state.chatRunId}`;
}

function chatRunSettingsPayload() {
  if (!state.chatOwnerRunId || !state.chatRunId) {
    throw new Error("The active Chat route is no longer available.");
  }
  return {runId:state.chatOwnerRunId, attachmentId:state.chatRunId};
}

function activeChatRunSettings(run = state.runStatus?.run) {
  if (state.chatRunSettingsKey === chatRunSettingsSurfaceKey() && state.chatRunSettings?.chat) {
    return state.chatRunSettings.chat;
  }
  if (state.chatAttachment?.chat) return state.chatAttachment.chat;
  return run?.client === "chat" ? run.chat || null : null;
}

function setChatRunSettingsStatus(message, kind = "") {
  const status = $("chatRunSettingsStatus");
  if (!status) return;
  status.textContent = message;
  status.className = `chat-run-settings-status${kind ? ` ${kind}` : ""}`;
}

function updateChatRunSamplingControls() {
  const contract = state.chatRunSettings?.contract || {};
  const customSupported = contract.customSampling !== false;
  const customOption = $("chatRunSamplingMode").querySelector('option[value="custom"]');
  if (customOption) customOption.disabled = !customSupported;
  if (!customSupported && $("chatRunSamplingMode").value === "custom") {
    $("chatRunSamplingMode").value = "model";
  }
  const custom = $("chatRunSamplingMode").value === "custom";
  $("chatRunSamplerFields").hidden = !custom;
  $("chatRunSamplingHelp").textContent = !customSupported
    ? contract.samplingReason || "This active route uses fixed runtime decoding."
    : custom
    ? "These values are sent with each future request in this active Chat."
    : "Use the generation defaults supplied by this model.";
}

function setChatRunSettingsBusy(busy) {
  state.chatRunSettingsBusy = busy;
  $("chatRunSettingsFields").disabled = busy || !state.chatRunSettings;
  $("chatRunSettingsSave").disabled = busy || !state.chatRunSettings;
}

function populateChatRunSettings(value) {
  const chat = value?.chat || {};
  const contract = value?.contract || {};
  const defaults = chat.modelDefaults || {};
  state.chatRunSettings = value;
  state.chatRunSettingsKey = chatRunSettingsSurfaceKey();
  $("chatRunContractModel").textContent = contract.model || "Loaded model";
  $("chatRunContractEngine").textContent = contract.backendLabel || backendName(contract.backend);
  $("chatRunContractContext").textContent = contract.context
    ? `${formatNumber(contract.context)} · ${formatNumber(contract.output)} out` : "Locked";
  $("chatRunContractReasoning").textContent = contract.reasoning === "auto"
    ? "Model default" : contract.reasoning || "Locked";
  $("chatRunSystemPrompt").value = chat.systemPrompt || "";
  $("chatRunSamplingMode").value = chat.sampling === "custom" ? "custom" : "model";
  $("chatRunTemperature").value = String(chat.temperature ?? defaults.temperature ?? 0.7);
  $("chatRunTopP").value = String(chat.topP ?? defaults.topP ?? defaults.top_p ?? 1);
  $("chatRunTopK").value = String(chat.topK ?? defaults.topK ?? defaults.top_k ?? 0);
  $("chatRunPresencePenalty").value = String(chat.presencePenalty ?? 0);
  $("chatRunFrequencyPenalty").value = String(chat.frequencyPenalty ?? 0);
  $("chatRunSeed").value = chat.seed === null || chat.seed === undefined ? "" : String(chat.seed);
  updateChatRunSamplingControls();
  setChatRunSettingsBusy(false);
}

function gatherChatRunSettings() {
  const seed = $("chatRunSeed").value.trim();
  return {
    systemPrompt:$("chatRunSystemPrompt").value,
    sampling:$("chatRunSamplingMode").value,
    temperature:Number($("chatRunTemperature").value),
    topP:Number($("chatRunTopP").value),
    topK:Number($("chatRunTopK").value),
    presencePenalty:Number($("chatRunPresencePenalty").value),
    frequencyPenalty:Number($("chatRunFrequencyPenalty").value),
    seed:seed === "" ? null : Number(seed),
  };
}

function setChatRunSettingsBackgroundInert(inert) {
  for (const element of [
    document.querySelector(".chat-header"), $("chatSidebar"),
    document.querySelector(".chat-conversation"),
  ]) {
    if (element) element.inert = Boolean(inert);
  }
}

function closeChatRunSettings(restoreFocus = true) {
  const panel = $("chatRunSettingsPanel");
  if (!panel || panel.hidden) return;
  state.chatRunSettingsGeneration += 1;
  state.chatRunSettingsBusy = false;
  panel.hidden = true;
  $("chatRunSettingsScrim").hidden = true;
  setChatRunSettingsBackgroundInert(false);
  $("chatRunSettingsButton").setAttribute("aria-expanded", "false");
  if (restoreFocus) $("chatRunSettingsButton").focus();
}

async function openChatRunSettings() {
  if (state.runPhase !== "running" || !state.chatRunId || state.chatRunSettingsBusy) return;
  const generation = ++state.chatRunSettingsGeneration;
  $("chatRunSettingsPanel").hidden = false;
  $("chatRunSettingsScrim").hidden = false;
  setChatRunSettingsBackgroundInert(true);
  $("chatRunSettingsButton").setAttribute("aria-expanded", "true");
  state.chatRunSettings = null;
  setChatRunSettingsBusy(true);
  setChatRunSettingsStatus("Loading the active Chat controls…");
  requestAnimationFrame(() => $("chatRunSettingsClose").focus());
  try {
    const data = await api("/api/chat/settings/get", {
      method:"POST", body:JSON.stringify(chatRunSettingsPayload()),
    });
    if (generation !== state.chatRunSettingsGeneration) return;
    populateChatRunSettings(data.settings);
    setChatRunSettingsStatus(
      state.chatQueue.length
        ? `${state.chatQueue.length} waiting message${state.chatQueue.length === 1 ? "" : "s"} will use whatever is saved when each request starts.`
        : "Changes apply to the next request without reloading the model.",
    );
    renderChatRoute(state.runStatus?.run);
  } catch (error) {
    if (generation !== state.chatRunSettingsGeneration) return;
    setChatRunSettingsBusy(false);
    $("chatRunSettingsFields").disabled = true;
    $("chatRunSettingsSave").disabled = true;
    setChatRunSettingsStatus(error.message, "error");
  }
}

async function saveChatRunSettings(event) {
  event.preventDefault();
  if (state.chatRunSettingsBusy || !state.chatRunSettings) return;
  if (!$("chatRunSettingsForm").reportValidity()) return;
  const generation = ++state.chatRunSettingsGeneration;
  setChatRunSettingsBusy(true);
  setChatRunSettingsStatus("Saving controls for the next request…");
  try {
    const data = await api("/api/chat/settings/update", {
      method:"POST",
      body:JSON.stringify({...chatRunSettingsPayload(), chat:gatherChatRunSettings()}),
    });
    if (generation !== state.chatRunSettingsGeneration) return;
    populateChatRunSettings(data.settings);
    const chat = data.settings.chat;
    if (state.chatAttachment) {
      state.chatAttachment.chat = {
        ...(state.chatAttachment.chat || {}),
        sampling:chat.sampling, hasSystemPrompt:Boolean(chat.systemPrompt),
      };
    }
    callbacks.runSettingsApplied(state.chatRunId, chat);
    renderChatRoute(state.runStatus?.run);
    setChatRunSettingsStatus(
      state.chatQueue.length
        ? `Saved. ${state.chatQueue.length} waiting message${state.chatQueue.length === 1 ? "" : "s"} will use this contract when sent.`
        : "Saved for the next message. The loaded model was not restarted.",
      "success",
    );
  } catch (error) {
    if (generation !== state.chatRunSettingsGeneration) return;
    setChatRunSettingsBusy(false);
    setChatRunSettingsStatus(error.message, "error");
  }
}

function chatRoutesMatch(left, right) {
  if (!left || !right) return false;
  return ["model", "backend", "context", "output", "reasoning"]
    .every(key => String(left[key] ?? "") === String(right[key] ?? ""));
}

function chatRouteLabel(route) {
  return `${profileBackendLabel(route?.backend)} · ${route?.model || "Local model"}`;
}

function retainChatPostmortem(phase, message, {ended = false} = {}) {
  if (!state.chatRunId) return null;
  const next = surfacePostmortemMarker(phase, message, "Chat route");
  const previous = state.chatPostmortem;
  state.chatPostmortem = {
    ...(previous?.state === "failed" && next.state !== "failed" ? previous : next),
    ownerRunId:state.chatOwnerRunId,
    surfaceId:state.chatRunId,
    ended:Boolean(ended || previous?.ended),
  };
  if (!$("chatRunSettingsPanel").hidden) closeChatRunSettings(false);
  state.chatRunSettings = null;
  state.chatRunSettingsKey = "";
  const turn = state.chatTurnSettlement?.surfaceId === state.chatRunId
    ? state.chatTurnSettlement : null;
  if (turn) turn.exitRequested = true;
  if (state.chatQueue.length) {
    state.chatQueuePaused = true;
    state.chatQueueRecovered = false;
    persistChatQueue();
  }
  for (const item of state.chatMessages) {
    if (!item.pending) continue;
    item.pending = false;
    item.stopped = true;
    item.interrupted = true;
    item.exclude = true;
    item.failure = item.failure || `${next.title}. Partial output was retained.`;
  }
  if (state.chatAbort && !state.chatAbort.signal?.aborted) state.chatAbort.abort();
  persistChatSessionState();
  return state.chatPostmortem;
}

function clearChatForReplacement() {
  if (!$("chatRunSettingsPanel").hidden) closeChatRunSettings(false);
  state.chatRunSettings = null;
  state.chatRunSettingsKey = "";
  if (state.chatAbort && !state.chatAbort.signal?.aborted) state.chatAbort.abort();
  persistChatSessionState();
  state.chatRunId = "";
  state.chatOwnerRunId = "";
  state.chatAttachment = null;
  state.chatAttachmentObserved = false;
  resetChatConversation();
  $("chatInput").value = "";
  sizeChatInput();
  renderChatDraftStatus();
}

function renderChatRoute(run = state.runStatus?.run) {
  const route = chatSurfaceRoute(run);
  const card = $("chatRouteCard");
  if (!route || !card) return;
  const chatSettings = activeChatRunSettings(run);
  const samplingLabel = chatSettings?.sampling === "custom" ? "custom sampling" : "model sampling";
  const thread = state.chatActiveThread;
  const savedMismatch = thread && !chatRoutesMatch(thread, route);
  const origin = thread ? {
    model:thread.originModel, backend:thread.originBackend,
    context:thread.originContext, output:thread.originOutput,
    reasoning:thread.originReasoning,
  } : null;
  const originChanged = origin && !chatRoutesMatch(origin, route);
  const postmortem = state.chatPostmortem;
  card.dataset.state = postmortem?.state || (savedMismatch || originChanged ? "changed" : "current");
  $("chatRouteModel").textContent = route.model;
  $("chatRouteDetail").textContent = `${profileBackendLabel(route.backend)} · ${formatNumber(route.context)} context · ${formatNumber(route.output)} max response · ${route.reasoning} reasoning · ${samplingLabel}`;
  $("chatRunSettingsButton").setAttribute(
    "aria-label", `Chat controls, ${samplingLabel}. Changes apply to the next request.`,
  );
  if (postmortem) {
    $("chatRouteState").textContent = postmortem.title;
    $("chatRouteNotice").textContent = postmortem.detail;
  } else if (savedMismatch) {
    $("chatRouteState").textContent = "Route differs";
    $("chatRouteNotice").textContent = `This transcript was last used with ${chatRouteLabel(thread)}. New replies use the loaded route shown above; no model was swapped.`;
  } else if (originChanged) {
    $("chatRouteState").textContent = "Route changed";
    $("chatRouteNotice").textContent = `This conversation started with ${chatRouteLabel(origin)}. Its latest replies use the loaded route shown above.`;
  } else if (thread) {
    $("chatRouteState").textContent = "Route matches";
    $("chatRouteNotice").textContent = "The saved transcript and currently loaded model contract match.";
  } else {
    $("chatRouteState").textContent = "Loaded route";
    $("chatRouteNotice").textContent = "Opening a saved transcript reuses this route and never loads different model weights behind your back.";
  }
  $("chatStatusPanel").dataset.routeState = card.dataset.state;
  $("chatStatusModel").textContent = route.model;
  $("chatStatusEngine").textContent = `${profileBackendLabel(route.backend)} · ${formatNumber(route.context)} context`;
  $("chatStatusRouteState").textContent = $("chatRouteState").textContent;
  $("chatStatusRouteState").hidden = !postmortem && card.dataset.state !== "changed";
  $("chatStatusRouteState").title = $("chatRouteNotice").textContent;
  updateChatStatusSummaryLabel();
  $("chatTitle").textContent = thread?.title || route.model;
  const routeNote = route.routeKind === "connected"
    ? "requests use the connected server; transcript history stays on this Mac"
    : route.routeKind === "native"
      ? "native on this Mac; launcher Stop unloads it"
      : "streamed thinking shown when the runtime exposes it";
  $("chatMeta").textContent = postmortem
    ? `${profileBackendLabel(route.backend)} · ${route.model} · bounded transcript retained`
    : `${profileBackendLabel(route.backend)} · ${route.model} · ${routeNote}`;
}

function renderChatHistory() {
  const threads = state.chatHistoryThreads;
  const query = state.chatHistoryQuery.trim().toLocaleLowerCase();
  const visible = query ? threads.filter(thread => chatHistoryMatches(thread, query)) : threads;
  const historyBusy = Boolean(
    state.chatAbort || state.chatRevisionBusy || state.chatEditingMessageId,
  );
  const canOpen = state.runPhase === "running" && Boolean(state.chatRunId) && !historyBusy;
  $("chatHistoryBadge").textContent = state.chatHistoryLoading
    ? "Loading" : query ? `${visible.length} of ${threads.length}` : `${threads.length} saved`;
  $("chatHistoryBadge").className = `setup-badge${state.chatHistoryLoading ? " active" : " ready"}`;
  $("chatHistoryClearSearch").disabled = !state.chatHistoryQuery;
  $("chatHistoryList").innerHTML = state.chatHistoryLoading
    ? `<div class="chat-history-empty">Reading launcher-local chat history…</div>`
    : visible.length ? visible.map(thread => {
      const confirming = state.chatHistoryDeleteConfirmId === thread.id;
      const editing = state.chatHistoryEditingId === thread.id;
      const actionBusy = state.chatHistoryBusyId === thread.id;
      const disabled = historyBusy || actionBusy || chatResumeReview.isStarting() ? " disabled" : "";
      const title = esc(thread.title || "Local chat");
      const resumeEngineVisible = uiEngineVisible(thread.backend);
      const branch = thread.branchParentId
        ? `<span class="chat-history-branch">${esc(`${chatBranchKindLabel(thread.branchKind)} of “${thread.branchParentTitle || "Local chat"}” at message ${thread.branchPoint || "?"}`)}</span>`
        : "";
      const interrupted = thread.hasInterruptedTurn
        ? `<span class="chat-history-interrupted">Interrupted turn recovered from the browser-tab journal</span>`
        : "";
      const resumeNote = thread.resumeAvailable && resumeEngineVisible
        ? `<span class="chat-history-resume-note${thread.resumeNeedsSystemPrompt ? " prompt" : ""}">${thread.resumeNeedsSystemPrompt ? "Cold resume ready · re-enter the unsaved system prompt" : "Cold resume ready · exact route settings saved"}</span>`
        : thread.resumeAvailable
          ? `<span>Transcript kept · its saved engine is temporarily hidden</span>`
          : `<span>Cold resume unavailable for this older conversation</span>`;
      const originChanged = thread.originModel && (
        thread.originModel !== thread.model || thread.originBackend !== thread.backend
      );
      const routeLine = originChanged
        ? `Latest: ${profileBackendLabel(thread.backend)} · ${thread.model || "Local model"} · started on ${profileBackendLabel(thread.originBackend)} · ${thread.originModel}`
        : `${profileBackendLabel(thread.backend)} · ${thread.model || "Local model"}`;
      const primaryAction = canOpen
        ? `<button type="button" data-chat-history-open="${esc(thread.id)}"${historyBusy || actionBusy ? " disabled" : ""}>Open</button>`
        : thread.resumeAvailable && resumeEngineVisible
          ? `<button type="button" data-chat-history-resume="${esc(thread.id)}"${historyBusy || actionBusy || chatResumeReview.isStarting() ? " disabled" : ""}>Review resume</button>`
          : `<button type="button" disabled title="${thread.resumeAvailable ? "This saved engine is temporarily hidden." : "Open and save this conversation once on an active Chat route to make it resumable."}">Route unavailable</button>`;
      const actions = editing ? "" : `<div class="chat-history-actions">${primaryAction}<details class="chat-history-more"${confirming ? " open" : ""}><summary aria-label="More actions for ${title}">More <span aria-hidden="true">⌄</span></summary><div><button type="button" aria-pressed="${thread.pinned ? "true" : "false"}" data-chat-history-pin="${esc(thread.id)}"${disabled}>${thread.pinned ? "Unpin" : "Pin"}</button><button type="button" data-chat-history-rename="${esc(thread.id)}"${disabled}>Rename</button><button type="button" data-chat-history-export="${esc(thread.id)}"${actionBusy ? " disabled" : ""}>Export</button><button type="button" class="delete" data-chat-history-delete="${esc(thread.id)}"${disabled}>${confirming ? "Confirm delete" : "Delete"}</button></div></details></div>`;
      return `<article class="chat-history-card${thread.pinned ? " pinned" : ""}" data-chat-history-card="${esc(thread.id)}"><div class="chat-history-main"><div class="chat-history-title-row">${thread.pinned ? `<i aria-label="Pinned">★ Pinned</i>` : ""}${editing ? `<form class="chat-history-rename" data-chat-history-rename-form="${esc(thread.id)}"><label class="sr-only" for="chat-title-${esc(thread.id)}">Chat title</label><input id="chat-title-${esc(thread.id)}" type="text" maxlength="72" value="${title}" required><button type="submit">Save</button><button type="button" data-chat-history-cancel-rename>Cancel</button></form>` : `<strong>${title}</strong>`}</div><span>${esc(`${routeLine} · ${thread.messageCount || 0} messages`)}</span>${resumeNote}${branch}${interrupted}<small title="${esc(thread.preview || "")}">${esc(`${chatHistoryDate(thread.updatedAt)}${thread.preview ? ` · ${thread.preview}` : ""}`)}</small></div>${actions}</article>`;
    }).join("") : `<div class="chat-history-empty">${query ? "No saved chats match that search." : "No previous chats yet. Completed turns will appear here automatically."}</div>`;
}

function renderChatResumePlan() { chatResumeReview.render(); }

async function openChatResumeDialog(historyId) {
  return chatResumeReview.open(historyId, state.chatHistoryThreads.find(thread => thread.id === historyId));
}

async function completePendingChatResume() { return chatResumeReview.completePending(); }

async function applyChatResume(startAfter) { return chatResumeReview.apply(startAfter); }

async function recoverInterruptedChatTurn() {
  if (state.chatTurnRecoveryChecked) return null;
  state.chatTurnRecoveryChecked = true;
  const tabId = chatTurnTabIdentifier();
  if (state.chatTurnTabStorageAvailable === false) return null;
  try {
    const data = await api("/api/chat/turn/recover", {
      method:"POST", body:JSON.stringify({tabId}),
    });
    state.chatTurnRecoveryAvailable = true;
    if (Array.isArray(data.threads)) state.chatHistoryThreads = data.threads;
    if (data.recovered && data.thread?.id) {
      state.chatTurnRecoveredHistoryId = data.thread.id;
      return data.thread;
    }
    return null;
  } catch (_error) {
    state.chatTurnRecoveryAvailable = false;
    return null;
  }
}

async function loadChatHistory(force = false) {
  if (state.chatHistoryLoading) return;
  if (!force && state.chatHistoryLoaded) {
    await waitForChatHistorySave();
    renderChatHistory();
    renderChatSidebar();
    await restorePendingChatDraftConversation();
    return;
  }
  state.chatHistoryLoading = true;
  setChatBusy(Boolean(state.chatAbort));
  renderChatHistory();
  renderChatSidebar();
  let loaded = false;
  try {
    await runChatHistoryMutation(async () => {
      await recoverInterruptedChatTurn();
      const data = await api("/api/chat/history");
      state.chatHistoryThreads = Array.isArray(data.threads) ? data.threads : [];
      state.chatHistoryLoaded = true;
      loaded = true;
      $("chatHistoryStatus").textContent = state.runPhase === "running" && state.chatRunId
        ? "Open uses the current Chat route. Saved routes can also be reviewed later without loading a model."
        : "Resumable conversations can re-open their exact saved route after a read-only review. Older conversations remain readable and exportable.";
      $("chatHistoryStatus").className = "session-dashboard-status";
    });
  } catch (error) {
    $("chatHistoryStatus").textContent = error.message;
    $("chatHistoryStatus").className = "session-dashboard-status error";
  } finally {
    state.chatHistoryLoading = false;
    setChatBusy(Boolean(state.chatAbort));
    renderChatHistory();
    renderChatSidebar();
    renderQuickStart();
  }
  if (loaded) await restorePendingChatDraftConversation();
}

async function openChatHistory() {
  state.chatSidebarMenuId = "";
  state.chatSidebarEditingId = "";
  renderChatSidebar();
  if (!$("chatHistoryDialog").open) $("chatHistoryDialog").showModal();
  await loadChatHistory(false);
}

async function updateChatHistoryThread(historyId, changes) {
  if (state.chatAbort || state.chatRevisionBusy || state.chatEditingMessageId || state.chatHistoryBusyId) return;
  state.chatHistoryBusyId = historyId;
  renderChatHistory();
  renderChatSidebar();
  setChatBusy(Boolean(state.chatAbort));
  return runChatHistoryMutation(async () => {
    try {
      const data = await api("/api/chat/history/update", {
        method:"POST", body:JSON.stringify({id:historyId, ...changes}),
      });
      state.chatHistoryThreads = Array.isArray(data.threads) ? data.threads : [];
      renderQuickStart();
      state.chatHistoryEditingId = "";
      state.chatSidebarEditingId = "";
      state.chatSidebarMenuId = "";
      state.chatHistoryDeleteConfirmId = "";
      if (state.chatHistoryId === historyId) {
        state.chatActiveThread = chatThreadSummary(data.thread);
        renderChatRoute(state.runStatus?.run);
      }
      $("chatHistoryStatus").textContent = changes.title
        ? "Chat renamed locally. Future auto-saves will preserve this title."
        : changes.pinned ? "Chat pinned to the top of local history." : "Chat unpinned.";
      $("chatHistoryStatus").className = "session-dashboard-status";
    } catch (error) {
      $("chatHistoryStatus").textContent = error.message;
      $("chatHistoryStatus").className = "session-dashboard-status error";
      showNotice(`Chat history was not updated: ${error.message}`, true);
    } finally {
      state.chatHistoryBusyId = "";
      setChatBusy(Boolean(state.chatAbort));
      renderChatHistory();
      renderChatSidebar();
    }
  });
}

function chatHistoryMarkdown(thread) {
  const lines = [
    `# ${thread.title || "Local chat"}`, "",
    `- Latest model: ${thread.model || "Local model"}`,
    `- Latest engine: ${thread.backend || "local"}`,
    `- Started with model: ${thread.originModel || thread.model || "Local model"}`,
    `- Started with engine: ${thread.originBackend || thread.backend || "local"}`,
    `- Updated: ${thread.updatedAt || "unknown"}`,
    ...(thread.branchParentId ? [
      `- Branch: ${chatBranchKindLabel(thread.branchKind)} of ${thread.branchParentTitle || "Local chat"} at message ${thread.branchPoint || "unknown"}`,
    ] : []),
    "",
  ];
  for (const message of thread.messages || []) {
    lines.push(`## ${message.role === "user" ? "You" : message.continuation ? "Local model · continuation" : "Local model"}`, "");
    if (message.createdAt) lines.push(`_${chatHistoryDate(message.createdAt)}_`, "");
    if (message.interrupted) {
      lines.push("_Incomplete model turn: any visible partial output was preserved and excluded from later prompts._", "");
    }
    if (message.failure) {
      lines.push(`_Terminal status: ${message.failure}_`, "");
    }
    if (message.truncated) {
      lines.push("_Response limit reached. The following continuation, if any, was requested separately._", "");
    }
    if (message.reasoning) {
      lines.push("### Model thinking (runtime-emitted)", "", message.reasoning, "", "### Response", "");
    }
    lines.push(message.content || (message.interrupted ? "_No visible model output had arrived._" : ""), "");
    if (message.usage) {
      const cached = Number.isInteger(message.usage.cachedPromptTokens)
        ? `; ${message.usage.cachedPromptTokens} cached prompt tokens`
        : "";
      lines.push(`_Runtime usage: ${message.usage.promptTokens} prompt tokens; ${message.usage.completionTokens} response tokens${cached}._`, "");
    }
  }
  return `${lines.join("\n").trim()}\n`;
}

async function exportChatHistoryThread(historyId) {
  if (state.chatHistoryBusyId) return;
  await waitForChatHistorySave();
  if (state.chatHistoryBusyId) return;
  state.chatHistoryBusyId = historyId;
  renderChatHistory();
  renderChatSidebar();
  try {
    const data = await api("/api/chat/history/get", {
      method:"POST", body:JSON.stringify({id:historyId}),
    });
    const thread = data.thread;
    const filename = String(thread.title || "local-chat")
      .normalize("NFKD").replace(/[^a-z0-9._-]+/gi, "-").replace(/^-+|-+$/g, "").slice(0, 64)
      || "local-chat";
    const url = URL.createObjectURL(new Blob([chatHistoryMarkdown(thread)], {type:"text/markdown;charset=utf-8"}));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${filename}.md`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
    state.chatSidebarMenuId = "";
    state.chatHistoryDeleteConfirmId = "";
    $("chatHistoryStatus").textContent = `Exported “${thread.title || "Local chat"}” as Markdown. Nothing was uploaded.`;
    $("chatHistoryStatus").className = "session-dashboard-status";
  } catch (error) {
    $("chatHistoryStatus").textContent = error.message;
    $("chatHistoryStatus").className = "session-dashboard-status error";
    showNotice(`Chat export failed: ${error.message}`, true);
  } finally {
    state.chatHistoryBusyId = "";
    renderChatHistory();
    renderChatSidebar();
  }
}

async function openChatHistoryThread(historyId, options = {}) {
  if (
    state.chatAbort || state.chatRevisionBusy || state.chatEditingMessageId
    || state.chatHistoryBusyId || state.chatHistoryLoading
    || state.chatHistorySaving || state.chatHistoryMutationTail
    || state.runPhase !== "running" || !state.chatRunId
  ) return;
  persistChatSessionState();
  if (
    !options.skipCurrentSave
    && !await saveChatBeforeNavigation("open that saved chat again")
  ) return;
  state.chatHistoryBusyId = historyId;
  renderChatHistory();
  renderChatSidebar();
  setChatBusy(Boolean(state.chatAbort));
  try {
    await runChatHistoryMutation(async () => {
      const data = await api("/api/chat/history/get", {
        method:"POST", body:JSON.stringify({id:historyId}),
      });
      const thread = data.thread;
      state.chatHistoryId = thread.id;
      state.chatActiveThread = chatThreadSummary(thread);
      state.chatMessages = (thread.messages || []).map(normaliseChatMessage);
      state.chatFollowOutput = true;
      state.chatBranch = thread.branchParentId ? {
        parentId:thread.branchParentId,
        parentTitle:thread.branchParentTitle || "Local chat",
        point:Number(thread.branchPoint || 1),
        kind:thread.branchKind || "branch",
      } : null;
      state.chatQueue = [];
      state.chatContextFiles = [];
      state.chatWorkspaceContext = null;
      state.chatContextBusy = false;
      state.chatEditingMessageId = "";
      state.chatQueueEditingId = "";
      state.chatTranscriptSearchOpen = false;
      state.chatTranscriptQuery = "";
      state.chatTranscriptActiveId = "";
      state.chatContextReducedAt = 0;
      activateChatDraft(state.chatRunId, {historyId:thread.id, restore:true});
      renderChatMessages({forceBottom:true});
      renderChatSidebar();
      renderChatRoute(state.runStatus?.run);
      if ($("chatHistoryDialog").open) $("chatHistoryDialog").close();
      if (matchMedia("(max-width: 820px)").matches) {
        state.chatSidebarCollapsed = true;
        renderChatSidebarVisibility();
      }
      if (options.interruptedRecovery || (thread.messages || []).some(message => message.interrupted)) {
        state.chatTurnRecoveredHistoryId = "";
        showNotice(`Recovered “${thread.title}” after the page closed during generation. The visible partial response is marked interrupted and will not be replayed into a new prompt.`);
      } else {
        showNotice(options.coldResume
          ? `Resumed “${thread.title}” on its saved ${profileBackendLabel(thread.backend)} route.${options.systemPromptDecision === "omitted" ? " Future replies will not use its original, unsaved system prompt." : ""}`
          : options.recovery
            ? `Recovered “${thread.title}” and its unfinished tab-local draft. Replies use the still-loaded model.`
            : `Opened “${thread.title}”. New replies use the currently loaded model and Chat settings.`);
      }
      $("chatInput").focus();
    });
  } catch (error) {
    $("chatHistoryStatus").textContent = error.message;
    $("chatHistoryStatus").className = "session-dashboard-status error";
  } finally {
    state.chatHistoryBusyId = "";
    setChatBusy(Boolean(state.chatAbort));
    renderChatHistory();
    renderChatSidebar();
  }
}

async function deleteChatHistoryThread(historyId) {
  if (state.chatHistoryDeleteConfirmId !== historyId) {
    state.chatHistoryDeleteConfirmId = historyId;
    renderChatHistory();
    renderChatSidebar();
    setTimeout(() => {
      if (state.chatHistoryDeleteConfirmId === historyId) {
        state.chatHistoryDeleteConfirmId = "";
        if ($("chatHistoryDialog").open) renderChatHistory();
        if (state.chatSidebarMenuId === historyId) renderChatSidebar();
      }
    }, 4500);
    return;
  }
  if (state.chatAbort || state.chatRevisionBusy || state.chatEditingMessageId || state.chatHistoryBusyId) return;
  const deletedTitle = state.chatHistoryThreads.find(thread => thread.id === historyId)?.title || "Local chat";
  state.chatHistoryBusyId = historyId;
  renderChatHistory();
  renderChatSidebar();
  setChatBusy(Boolean(state.chatAbort));
  return runChatHistoryMutation(async () => {
    try {
      const data = await api("/api/chat/history/delete", {
        method:"POST", body:JSON.stringify({id:historyId}),
      });
      state.chatHistoryThreads = Array.isArray(data.threads) ? data.threads : [];
      renderQuickStart();
      state.chatHistoryDeleteConfirmId = "";
      state.chatSidebarMenuId = "";
      state.chatSidebarEditingId = "";
      state.chatHistoryEditingId = "";
      if (state.chatHistoryId === historyId) {
        const oldKey = state.chatDraftKey;
        const nextKey = newChatDraftKey();
        const envelope = ChatDraftsCore.moveDraft(
          readChatDraftEnvelope(), oldKey, nextKey, CHAT_DRAFT_OPTIONS,
        );
        migrateChatQueueKey(oldKey, nextKey);
        state.chatHistoryId = "";
        state.chatActiveThread = null;
        state.chatDraftKey = nextKey;
        writeChatDraftEnvelope(envelope);
        renderChatRoute(state.runStatus?.run);
      }
      $("chatHistoryStatus").textContent = `Deleted “${deletedTitle}” from launcher-local history.`;
      $("chatHistoryStatus").className = "session-dashboard-status";
      showNotice(`Deleted “${deletedTitle}” from local Chat history.`);
    } catch (error) {
      state.chatHistoryDeleteConfirmId = "";
      $("chatHistoryStatus").textContent = error.message;
      $("chatHistoryStatus").className = "session-dashboard-status error";
      showNotice(`Chat deletion failed: ${error.message}`, true);
    } finally {
      state.chatHistoryBusyId = "";
      setChatBusy(Boolean(state.chatAbort));
      renderChatHistory();
      renderChatSidebar();
    }
  });
}

function updateChatWorkspace(run, phase) {
  const routeActive = sessionRouteActive(run, phase);
  if (
    routeActive && state.chatOwnerRunId
    && state.chatOwnerRunId !== run.runId
  ) clearChatForReplacement();

  const primaryChat = Boolean(routeActive && run.client === "chat");
  if (primaryChat && run.runId && state.chatRunId !== run.runId) {
    if (state.chatAbort) state.chatAbort.abort();
    persistChatSessionState();
    state.chatRunId = run.runId;
    state.chatOwnerRunId = run.runId;
    state.chatAttachment = {
      id:run.runId, ownerRunId:run.runId, primary:true, client:"chat",
      surface:"Chat", backend:run.backend, model:run.model,
      context:run.context, output:run.output, reasoning:run.reasoning,
    };
    state.chatAttachmentObserved = true;
    resetChatConversation();
    state.chatRunId = run.runId;
    state.chatOwnerRunId = run.runId;
    activateChatDraft(run.runId, {restoreActive:true});
    renderChatMessages();
  } else if (primaryChat && run.runId && !state.chatAttachment) {
    state.chatAttachment = {
      id:run.runId, ownerRunId:run.runId, primary:true, client:"chat",
      surface:"Chat", backend:run.backend, model:run.model,
      context:run.context, output:run.output, reasoning:run.reasoning,
    };
    state.chatAttachmentObserved = true;
  }

  const listedAttachment = Array.isArray(state.runStatus?.attachments)
    ? state.runStatus.attachments.find(item => (
      item?.id === state.chatRunId && item?.client === "chat"
      && item?.ownerRunId === state.chatOwnerRunId
    )) || null
    : null;
  if (listedAttachment) {
    state.chatAttachment = {...(state.chatAttachment || {}), ...listedAttachment};
    state.chatAttachmentObserved = true;
  }
  const currentPrimary = Boolean(
    primaryChat && state.chatRunId === run.runId
    && state.chatAttachment?.primary !== false
  );
  const currentAttachment = Boolean(
    routeActive && state.chatAttachment?.client === "chat"
    && state.chatAttachment?.primary === false
    && state.chatAttachment.ownerRunId === run.runId
    && (!state.chatAttachmentObserved || listedAttachment)
  );
  const currentSurface = currentPrimary || currentAttachment;
  if (currentSurface && !state.chatPostmortem?.ended) {
    state.chatPostmortem = null;
  } else if (
    state.chatRunId && (
      !routeActive
      || (["running", "stopping"].includes(phase) && !currentSurface)
    )
  ) {
    retainChatPostmortem(phase, state.runStatus?.message);
  }

  const chatRun = Boolean(currentSurface && !state.chatPostmortem);
  const retained = Boolean(state.chatPostmortem && state.chatRunId && state.chatAttachment);
  const visible = Boolean(
    (retained || (chatRun && ["running", "stopping"].includes(phase)))
    && !agentConsoleIsVisible()
  );
  const controlsReady = Boolean(visible && chatRun && phase === "running");
  $("chatRunSettingsButton").disabled = !controlsReady;
  if (!controlsReady && !$("chatRunSettingsPanel").hidden) closeChatRunSettings(false);
  if (!visible) {
    state.chatRunSettings = null;
    state.chatRunSettingsKey = "";
  }
  $("chatWorkspace").classList.toggle("hidden", !visible);
  updateWorkspaceChrome();
  if (visible) {
    const route = chatSurfaceRoute(run);
    $("configSubtitle").textContent = `${profileBackendLabel(route?.backend)} · ${route?.model || "Local model"}`;
    renderChatRoute(run);
    renderChatUsage();
    renderChatSidebar();
    if (!state.chatHistoryLoaded && !state.chatHistoryLoading) void loadChatHistory(false);
    else if (state.chatDraftPendingHistoryId) void restorePendingChatDraftConversation();
    $("endChatButton").textContent = retained
      ? state.chatPostmortem.title
      : state.chatAttachment?.primary === false ? "End attached chat" : "End chat";
    $("endChatButton").disabled = retained || !chatRun;
    if (controlsReady && chatResumeReview.hasPending()) void completePendingChatResume();
  }
  setChatBusy(Boolean(state.chatAbort));
}

async function stopChatResponse() {
  const controller = state.chatAbort;
  if (!controller || state.chatStopBusy) return;
  controller.launcherStopRequested = true;
  state.chatStopBusy = true;
  setChatBusy(true);
  try {
    await api("/api/chat/stop", {
      method:"POST",
      body:JSON.stringify({
        runId:state.chatOwnerRunId,
        attachmentId:state.chatRunId,
      }),
    });
  } catch (error) {
    showNotice(
      `The browser stopped reading, but the local runtime could not confirm cancellation: ${error.message}`,
      true,
    );
  } finally {
    controller.abort();
    state.chatStopBusy = false;
    setChatBusy(Boolean(state.chatAbort));
  }
}

async function enterChatSurface(attachment, options = {}) {
  if (!attachment || attachment.client !== "chat") return false;
  if (
    state.chatRunId && state.chatRunId !== attachment.id
    && options.currentChatSaved !== true
    && !await saveChatBeforeSurfaceExit("open that Chat surface again")
  ) return false;
  agentConsoleWorkspace.suspend();
  if (state.chatRunId !== attachment.id) {
    if (!$("chatRunSettingsPanel").hidden) closeChatRunSettings(false);
    state.chatRunSettings = null;
    state.chatRunSettingsKey = "";
    persistChatSessionState();
    resetChatConversation();
  }
  state.chatAttachment = attachment;
  state.chatAttachmentObserved = false;
  state.chatPostmortem = null;
  state.chatRunId = attachment.id;
  state.chatOwnerRunId = attachment.ownerRunId;
  if (!state.chatDraftKey) activateChatDraft(attachment.id, {restoreActive:true});
  renderChatMessages();
  updateChatWorkspace(state.runStatus?.run, state.runPhase);
  updateAgentWorkspace(state.runStatus?.run, state.runPhase);
  navigation.closeSessions();
  requestAnimationFrame(() => $("chatInput").focus());
  return true;
}

async function detachChatSurface(attachment) {
  if (!attachment?.canDetach) return false;
  if (
    state.chatRunId === attachment.id
    && !await saveChatBeforeSurfaceExit("end this attached chat again")
  ) return false;
  try {
    const data = await api("/api/session/detach", {
      method:"POST",
      body:JSON.stringify({ownerRunId:attachment.ownerRunId, attachmentId:attachment.id}),
    });
    if (state.chatRunId === attachment.id) {
      persistChatSessionState();
      state.chatAttachmentObserved = true;
      retainChatPostmortem(
        "stopped",
        "Attached Chat ended.",
        {ended:true},
      );
      updateChatWorkspace(state.runStatus?.run, state.runPhase);
    }
    await callbacks.surfaceDetached(data.hub, attachment.ownerRunId);
    return true;
  } catch (error) {
    showNotice(error.message, true);
    return false;
  }
}

async function endCurrentChatSurface() {
  if (state.chatAttachment?.primary === false) {
    return detachChatSurface(state.chatAttachment);
  }
  return navigation.stopRun();
}
    function initialize(){
      if (initialized) return;
      initialized = true;
      state.chatSidebarCollapsed=matchMedia('(max-width: 820px)').matches;
$("chatForm").addEventListener("submit", event => { event.preventDefault(); sendChat(); });
$("chatAttachButton").addEventListener("click", () => {
  if (!chatContextLocked()) $("chatContextFileInput").click();
});
$("chatContextFileInput").addEventListener("change", event => {
  void addChatContextFiles(event.currentTarget.files);
});
$("chatWorkspaceButton").addEventListener("click", () => {
  if (!chatContextLocked()) $("chatWorkspaceFolderInput").click();
});
$("chatWorkspaceFolderInput").addEventListener("change", event => {
  void addChatWorkspaceFolder(event.currentTarget.files);
});
$("chatContextFiles").addEventListener("click", event => {
  const remove = event.target.closest("[data-chat-context-remove]");
  if (remove && !remove.disabled) removeChatContextFile(remove.dataset.chatContextRemove);
});
$("chatContextClear").addEventListener("click", () => {
  if (chatContextLocked()) return;
  state.chatContextFiles = [];
  state.chatWorkspaceContext = null;
  renderChatContextPack();
});
$("chatWorkspaceClear").addEventListener("click", () => {
  if (chatContextLocked()) return;
  state.chatWorkspaceContext = null;
  renderChatContextPack();
});
$("chatInput").addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    sendChat();
  }
});
$("chatInput").addEventListener("input", event => {
  sizeChatInput();
  scheduleChatDraftSave();
});
$("chatDraftClear").addEventListener("click", () => {
  clearChatDraft();
  $("chatInput").focus();
});
$("chatStopButton").addEventListener("click", stopChatResponse);
$("chatQueue").addEventListener("click", event => {
  const remove = event.target.closest("[data-chat-queue-remove]");
  const move = event.target.closest("[data-chat-queue-move]");
  const edit = event.target.closest("[data-chat-queue-edit]");
  const save = event.target.closest("[data-chat-queue-save]");
  const cancel = event.target.closest("[data-chat-queue-cancel]");
  const resume = event.target.closest("[data-chat-queue-resume]");
  if (remove) {
    state.chatQueue = state.chatQueue.filter(item => item.id !== remove.dataset.chatQueueRemove);
    if (state.chatQueueEditingId === remove.dataset.chatQueueRemove) state.chatQueueEditingId = "";
    if (!state.chatQueue.length) {
      state.chatQueuePaused = false;
      state.chatQueueRecovered = false;
    }
    persistChatQueue();
  } else if (move) moveQueuedChatMessage(move.dataset.chatQueueMove, Number(move.dataset.chatQueueDirection));
  else if (edit) editQueuedChatMessage(edit.dataset.chatQueueEdit);
  else if (save) { finishQueuedChatEdit(save.dataset.chatQueueSave, true); return; }
  else if (cancel) { finishQueuedChatEdit(cancel.dataset.chatQueueCancel, false); return; }
  else if (resume) { resumeChatQueue(); return; }
  else if (event.target.closest("[data-chat-queue-clear]")) {
    state.chatQueue = [];
    state.chatQueueEditingId = "";
    state.chatQueuePaused = false;
    state.chatQueueRecovered = false;
    persistChatQueue();
  }
  setChatBusy(Boolean(state.chatAbort));
});
$("chatQueue").addEventListener("keydown", event => {
  const row = event.target.closest("[data-chat-queue-edit-row]");
  if (!row) return;
  if (event.key === "Escape") {
    event.preventDefault();
    finishQueuedChatEdit(row.dataset.chatQueueEditRow, false);
  } else if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
    event.preventDefault();
    finishQueuedChatEdit(row.dataset.chatQueueEditRow, true);
  }
});
$("chatMessages").addEventListener("click", event => {
  const codeCopy = event.target.closest("[data-chat-code-copy]");
  if (codeCopy) {
    void copyChatCode(codeCopy);
    return;
  }
  const cancel = event.target.closest("[data-chat-edit-cancel]");
  if (cancel) {
    state.chatEditingMessageId = "";
    renderChatMessages();
    setChatBusy(Boolean(state.chatAbort));
    return;
  }
  const button = event.target.closest("[data-chat-action]");
  if (!button || button.disabled) return;
  const messageId = button.dataset.chatMessageId;
  if (button.dataset.chatAction === "copy") copyChatMessage(messageId);
  else if (button.dataset.chatAction === "edit") {
    state.chatEditingMessageId = messageId;
    renderChatMessages();
    setChatBusy(Boolean(state.chatAbort));
  } else if (button.dataset.chatAction === "branch") {
    runChatRevision(() => branchChatAt(messageId));
  } else if (button.dataset.chatAction === "regenerate") {
    runChatRevision(() => regenerateChatMessage(messageId));
  } else if (button.dataset.chatAction === "retry") {
    runChatRevision(() => retryIncompleteChatMessage(messageId));
  } else if (button.dataset.chatAction === "continue") {
    runChatRevision(() => continueChatMessage(messageId));
  }
});
$("chatMessages").addEventListener("toggle", event => {
  const opened = event.target;
  if (!opened?.classList?.contains("chat-message-more") || !opened.open) return;
  for (const menu of $("chatMessages").querySelectorAll(".chat-message-more[open]")) {
    if (menu !== opened) menu.open = false;
  }
}, true);
$("chatMessages").addEventListener("submit", event => {
  const form = event.target.closest("[data-chat-edit-form]");
  if (!form) return;
  event.preventDefault();
  runChatRevision(() => editAndRetryChatMessage(
    form.dataset.chatEditForm, form.querySelector("textarea").value,
  ));
});
$("chatMessages").addEventListener("scroll", event => {
  state.chatFollowOutput = ChatScrollCore.nearBottom(chatScrollMetrics(event.currentTarget));
  updateChatScrollUi();
}, {passive:true});
const markChatScrollInteraction = () => {
  state.chatScrollInteractionRevision += 1;
};
$("chatMessages").addEventListener("wheel", markChatScrollInteraction, {passive:true});
$("chatMessages").addEventListener("touchstart", markChatScrollInteraction, {passive:true});
$("chatMessages").addEventListener("pointerdown", markChatScrollInteraction, {passive:true});
$("chatMessages").addEventListener("keydown", event => {
  if (["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "].includes(event.key)) {
    markChatScrollInteraction();
  }
});
$("chatJumpLatest").addEventListener("click", () => scrollChatToLatest());
$("chatTranscriptSearchToggle").addEventListener("click", openChatTranscriptSearch);
$("chatTranscriptSearchClose").addEventListener("click", () => closeChatTranscriptSearch());
$("chatTranscriptPrevious").addEventListener("click", () => stepChatTranscriptMatch(-1));
$("chatTranscriptNext").addEventListener("click", () => stepChatTranscriptMatch(1));
$("chatTranscriptSearchInput").addEventListener("input", event => {
  state.chatTranscriptQuery = event.currentTarget.value.slice(0, ChatTranscriptCore.MAX_QUERY_CHARACTERS);
  state.chatTranscriptActiveId = "";
  applyChatTranscriptSearch({scrollActive:Boolean(ChatTranscriptCore.normaliseQuery(state.chatTranscriptQuery))});
});
$("chatTranscriptSearchInput").addEventListener("keydown", event => {
  if (event.key === "Escape") {
    event.preventDefault();
    closeChatTranscriptSearch();
  } else if (event.key === "Enter" && !event.isComposing) {
    event.preventDefault();
    stepChatTranscriptMatch(event.shiftKey ? -1 : 1);
  }
});
document.addEventListener("keydown", event => {
  if (
    event.key.toLocaleLowerCase() !== "f" || (!event.metaKey && !event.ctrlKey)
    || $("chatWorkspace").classList.contains("hidden") || document.querySelector("dialog[open]")
  ) return;
  event.preventDefault();
  openChatTranscriptSearch();
});
$("chatTrimButton").addEventListener("click", () => runChatRevision(trimChatToRecent));
$("chatStatusPanel").addEventListener("toggle", renderChatStatusDisclosure);
$("chatHistoryButton").addEventListener("click", openChatHistory);
$("chatRunSettingsButton").addEventListener("click", () => {
  if ($("chatRunSettingsPanel").hidden) openChatRunSettings();
  else closeChatRunSettings();
});
$("chatRunSettingsClose").addEventListener("click", () => closeChatRunSettings());
$("chatRunSettingsCancel").addEventListener("click", () => closeChatRunSettings());
$("chatRunSettingsScrim").addEventListener("click", () => closeChatRunSettings());
$("chatRunSettingsForm").addEventListener("submit", saveChatRunSettings);
$("chatRunSamplingMode").addEventListener("change", updateChatRunSamplingControls);
$("chatRunSettingsPanel").addEventListener("keydown", event => {
  if (event.key === "Escape") {
    event.preventDefault();
    closeChatRunSettings();
  } else if (event.key === "Tab") {
    const focusable = [...$("chatRunSettingsPanel").querySelectorAll(
      'button:not(:disabled),textarea:not(:disabled),select:not(:disabled),input:not(:disabled),summary,[tabindex]:not([tabindex="-1"])',
    )].filter(element => !element.hidden && element.getClientRects().length);
    if (!focusable.length) return;
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault(); last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault(); first.focus();
    }
  }
});
$("openChatHistoryTop").addEventListener("click", openChatHistory);
$("chatHistoryRefresh").addEventListener("click", () => loadChatHistory(true));
$("chatSidebarToggle").addEventListener("click", () => {
  state.chatSidebarCollapsed = !state.chatSidebarCollapsed;
  if (state.chatSidebarCollapsed) {
    state.chatSidebarMenuId = "";
    state.chatSidebarEditingId = "";
    state.chatHistoryDeleteConfirmId = "";
  }
  renderChatSidebarVisibility();
});
$("chatSidebarNew").addEventListener("click", newChat);
$("chatSidebarManage").addEventListener("click", openChatHistory);
$("chatSidebarSearch").addEventListener("input", event => {
  state.chatSidebarQuery = event.currentTarget.value;
  renderChatSidebar();
});
$("chatSidebarClearSearch").addEventListener("click", () => {
  state.chatSidebarQuery = "";
  $("chatSidebarSearch").value = "";
  renderChatSidebar();
  $("chatSidebarSearch").focus();
});
$("chatSidebarList").addEventListener("click", event => {
  const toggle = event.target.closest("[data-chat-sidebar-menu-toggle]");
  const pin = event.target.closest("[data-chat-sidebar-pin]");
  const rename = event.target.closest("[data-chat-sidebar-rename]");
  const cancelRename = event.target.closest("[data-chat-sidebar-cancel-rename]");
  const exportButton = event.target.closest("[data-chat-sidebar-export]");
  const remove = event.target.closest("[data-chat-sidebar-delete]");
  const open = event.target.closest("[data-chat-sidebar-open]");
  const draft = event.target.closest("[data-chat-sidebar-draft]");
  if (toggle && !toggle.disabled) {
    const historyId = toggle.dataset.chatSidebarMenuToggle;
    const opening = state.chatSidebarMenuId !== historyId;
    state.chatSidebarMenuId = opening ? historyId : "";
    state.chatSidebarEditingId = "";
    if (!opening && state.chatHistoryDeleteConfirmId === historyId) state.chatHistoryDeleteConfirmId = "";
    renderChatSidebar();
    requestAnimationFrame(() => {
      const thread = $("chatSidebarList").querySelector(`[data-chat-sidebar-thread="${CSS.escape(historyId)}"]`);
      (opening ? thread?.querySelector('[role="menuitem"]') : thread?.querySelector("[data-chat-sidebar-menu-toggle]"))?.focus();
    });
  } else if (pin && !pin.disabled) {
    state.chatHistoryDeleteConfirmId = "";
    updateChatHistoryThread(pin.dataset.chatSidebarPin, {pinned:pin.dataset.chatSidebarPinned !== "true"});
  } else if (rename && !rename.disabled) {
    const historyId = rename.dataset.chatSidebarRename;
    state.chatSidebarMenuId = "";
    state.chatSidebarEditingId = historyId;
    state.chatHistoryDeleteConfirmId = "";
    renderChatSidebar();
    requestAnimationFrame(() => {
      const input = $("chatSidebarList").querySelector(`[data-chat-sidebar-thread="${CSS.escape(historyId)}"] .chat-sidebar-rename input`);
      input?.focus();
      input?.select();
    });
  } else if (cancelRename) {
    const historyId = cancelRename.dataset.chatSidebarCancelRename;
    state.chatSidebarEditingId = "";
    renderChatSidebar();
    requestAnimationFrame(() => $("chatSidebarList").querySelector(`[data-chat-sidebar-menu-toggle="${CSS.escape(historyId)}"]`)?.focus());
  } else if (exportButton && !exportButton.disabled) {
    state.chatHistoryDeleteConfirmId = "";
    exportChatHistoryThread(exportButton.dataset.chatSidebarExport);
  } else if (remove && !remove.disabled) {
    const historyId = remove.dataset.chatSidebarDelete;
    deleteChatHistoryThread(historyId).then(() => {
      if (state.chatHistoryDeleteConfirmId !== historyId) return;
      requestAnimationFrame(() => $("chatSidebarList").querySelector(`[data-chat-sidebar-delete="${CSS.escape(historyId)}"]`)?.focus());
    });
  } else if (open && !open.disabled) {
    state.chatSidebarMenuId = "";
    state.chatSidebarEditingId = "";
    state.chatHistoryDeleteConfirmId = "";
    openChatHistoryThread(open.dataset.chatSidebarOpen);
  } else if (draft && !draft.disabled) {
    state.chatSidebarMenuId = "";
    state.chatSidebarEditingId = "";
    state.chatHistoryDeleteConfirmId = "";
    openUnsavedChatDraft(draft.dataset.chatSidebarDraft);
  }
});
$("chatSidebarList").addEventListener("submit", event => {
  const form = event.target.closest("[data-chat-sidebar-rename-form]");
  if (!form) return;
  event.preventDefault();
  updateChatHistoryThread(form.dataset.chatSidebarRenameForm, {title:form.querySelector("input").value});
});
$("chatSidebarList").addEventListener("keydown", event => {
  const thread = event.target.closest("[data-chat-sidebar-thread]");
  if (!thread) return;
  const historyId = thread.dataset.chatSidebarThread;
  if (event.key === "Escape" && (state.chatSidebarMenuId === historyId || state.chatSidebarEditingId === historyId)) {
    event.preventDefault();
    state.chatSidebarMenuId = "";
    state.chatSidebarEditingId = "";
    state.chatHistoryDeleteConfirmId = "";
    renderChatSidebar();
    requestAnimationFrame(() => $("chatSidebarList").querySelector(`[data-chat-sidebar-menu-toggle="${CSS.escape(historyId)}"]`)?.focus());
    return;
  }
  const toggle = event.target.closest("[data-chat-sidebar-menu-toggle]");
  if (toggle && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
    event.preventDefault();
    state.chatSidebarMenuId = historyId;
    state.chatSidebarEditingId = "";
    renderChatSidebar();
    requestAnimationFrame(() => {
      const items = [...$("chatSidebarList").querySelectorAll(`[data-chat-sidebar-thread="${CSS.escape(historyId)}"] [role="menuitem"]:not(:disabled)`)];
      (event.key === "ArrowUp" ? items.at(-1) : items[0])?.focus();
    });
    return;
  }
  const menu = event.target.closest('[role="menu"]');
  if (!menu || !["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
  const items = [...menu.querySelectorAll('[role="menuitem"]:not(:disabled)')];
  if (!items.length) return;
  event.preventDefault();
  const current = Math.max(0, items.indexOf(document.activeElement));
  const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1
    : event.key === "ArrowUp" ? (current - 1 + items.length) % items.length
      : (current + 1) % items.length;
  items[next].focus();
});
$("chatHistorySearch").addEventListener("input", event => {
  state.chatHistoryQuery = event.currentTarget.value;
  renderChatHistory();
});
$("chatHistoryClearSearch").addEventListener("click", () => {
  state.chatHistoryQuery = "";
  $("chatHistorySearch").value = "";
  renderChatHistory();
  $("chatHistorySearch").focus();
});
$("chatHistoryList").addEventListener("click", event => {
  const open = event.target.closest("[data-chat-history-open]");
  const resume = event.target.closest("[data-chat-history-resume]");
  const pin = event.target.closest("[data-chat-history-pin]");
  const rename = event.target.closest("[data-chat-history-rename]");
  const cancelRename = event.target.closest("[data-chat-history-cancel-rename]");
  const exportButton = event.target.closest("[data-chat-history-export]");
  const remove = event.target.closest("[data-chat-history-delete]");
  if (open) openChatHistoryThread(open.dataset.chatHistoryOpen);
  else if (resume) openChatResumeDialog(resume.dataset.chatHistoryResume);
  else if (pin) updateChatHistoryThread(pin.dataset.chatHistoryPin, {pinned:pin.getAttribute("aria-pressed") !== "true"});
  else if (rename) {
    state.chatHistoryEditingId = rename.dataset.chatHistoryRename;
    renderChatHistory();
    requestAnimationFrame(() => $("chatHistoryList").querySelector(".chat-history-rename input")?.focus());
  }
  else if (cancelRename) { state.chatHistoryEditingId = ""; renderChatHistory(); }
  else if (exportButton) exportChatHistoryThread(exportButton.dataset.chatHistoryExport);
  else if (remove) deleteChatHistoryThread(remove.dataset.chatHistoryDelete);
});
$("chatHistoryList").addEventListener("submit", event => {
  const form = event.target.closest("[data-chat-history-rename-form]");
  if (!form) return;
  event.preventDefault();
  updateChatHistoryThread(form.dataset.chatHistoryRenameForm, {title:form.querySelector("input").value});
});
$("newChatButton").addEventListener("click", newChat);
$("endChatButton").addEventListener("click", endCurrentChatSurface);
document.addEventListener("click", event => {
  if (!state.chatSidebarMenuId || event.target.closest("[data-chat-sidebar-thread]")) return;
  state.chatSidebarMenuId = "";
  state.chatHistoryDeleteConfirmId = "";
  renderChatSidebar();
});
platform.onBeforeUnload(persistChatSessionState);
    }
    let initialized = false;
    const methods={updateChatStatusSummaryLabel,renderChatStatusDisclosure,syncChatStatusDetailMode,syncChatResumeDetailMode,readChatDraftEnvelope,writeChatDraftEnvelope,readChatQueueEnvelope,writeChatQueueEnvelope,persistChatQueue,restoreChatQueue,migrateChatQueueKey,chatQueueCount,chatDraftSurfacePrefix,chatHistoryDraftKey,newChatDraftKey,isPortableChatDraftKey,localUuid,chatTurnTabIdentifier,chatDraftHistoryIdFromKey,migrateLegacyChatHistoryStorage,sizeChatInput,renderChatDraftStatus,persistChatDraftNow,persistChatSessionState,scheduleChatDraftSave,activateChatDraft,clearChatDraft,migrateChatDraftToHistory,restorePendingChatDraftConversation,nextChatMessageId,normaliseChatTimestamp,formatChatTimestamp,normaliseChatFailure,normaliseChatMessage,resetChatConversation,chatEventUsage,emitThinkTaggedText,consumeChatResponse,renderChatUsage,chatContextLocked,normaliseChatWorkspacePath,chatWorkspacePathPolicy,chatWorkspaceCandidatePriority,chatWorkspaceTerms,chatWorkspaceFileScore,chatWorkspaceExcerpt,chatRequestAvailableContextCharacters,chatWorkspaceRequestCharacterBudget,chatContextRequestFiles,renderChatContextPack,supportedChatContextFile,addChatContextFiles,addChatWorkspaceFolder,removeChatContextFile,chatScrollMetrics,updateChatScrollUi,scrollChatToLatest,chatTranscriptMatches,renderChatTranscriptToolbar,clearChatTranscriptHighlights,highlightChatTranscriptText,applyChatTranscriptSearch,openChatTranscriptSearch,closeChatTranscriptSearch,stepChatTranscriptMatch,renderChatInline,renderChatMarkdown,renderChatMessages,renderChatQueue,queueChatRender,setChatBusy,queueChatMessage,processChatQueue,resumeChatQueue,moveQueuedChatMessage,editQueuedChatMessage,finishQueuedChatEdit,ensureChatHistoryId,currentChatCheckpointPayload,scheduleChatTurnCheckpoint,flushChatTurnCheckpoint,beginChatTurnCheckpoint,cancelChatTurnCheckpoint,finishChatTurnCheckpoint,clearChatTurnCheckpoint,startChatTurn,chatMessageIndex,createChatBranch,branchChatAt,editAndRetryChatMessage,regenerateChatMessage,retryIncompleteChatMessage,continueChatMessage,copyChatMessage,copyChatCode,runChatRevision,trimChatToRecent,sendChat,chatHasPersistableTranscript,saveChatBeforeNavigation,saveChatBeforeSurfaceExit,newChat,currentChatHistoryPayload,runChatHistoryMutation,saveCurrentChatHistory,waitForChatHistorySave,chatHistoryDate,chatThreadSummary,chatBranchKindLabel,chatHistoryMatches,renderChatSidebarVisibility,chatUnsavedDrafts,renderChatSidebar,openUnsavedChatDraft,chatSurfaceRoute,chatRunSettingsSurfaceKey,chatRunSettingsPayload,activeChatRunSettings,setChatRunSettingsStatus,updateChatRunSamplingControls,setChatRunSettingsBusy,populateChatRunSettings,gatherChatRunSettings,setChatRunSettingsBackgroundInert,closeChatRunSettings,openChatRunSettings,saveChatRunSettings,chatRoutesMatch,chatRouteLabel,retainChatPostmortem,clearChatForReplacement,renderChatRoute,renderChatHistory,renderChatResumePlan,openChatResumeDialog,completePendingChatResume,applyChatResume,recoverInterruptedChatTurn,loadChatHistory,openChatHistory,updateChatHistoryThread,chatHistoryMarkdown,exportChatHistoryThread,openChatHistoryThread,deleteChatHistoryThread,updateChatWorkspace,stopChatResponse,enterChatSurface,detachChatSurface,endCurrentChatSurface,initialize};
    methods.view=()=>Object.freeze({surfaceId:state.chatRunId,ownerRunId:state.chatOwnerRunId,
      generating:Boolean(state.chatAbort),revisionBusy:Boolean(state.chatRevisionBusy),
      editing:Boolean(state.chatEditingMessageId),historyBusy:Boolean(state.chatHistoryBusyId||state.chatHistoryLoading||state.chatHistorySaving||state.chatHistoryMutationTail),
      hasTranscript:chatHasPersistableTranscript(),sidebarCollapsed:state.chatSidebarCollapsed,
      historyLoaded:state.chatHistoryLoaded,activeThreadId:state.chatActiveThread?.id||"",
      attachment:state.chatAttachment?structuredClone(state.chatAttachment):null});
    methods.thread=id=>{const value=state.chatHistoryThreads.find(thread=>thread.id===id);return value?structuredClone(value):null;};
    methods.threads=()=>structuredClone(state.chatHistoryThreads);
    methods.useThreads=threads=>{state.chatHistoryThreads=structuredClone(threads||[]);renderChatHistory();renderChatSidebar();};
    methods.abortResponse=()=>state.chatAbort?.abort();
    methods.initializePrimary=plan=>{
      state.chatAbort?.abort();
      state.chatAbort = null;
      persistChatSessionState();
      resetChatConversation();
      state.chatRunId=plan.runId;state.chatOwnerRunId=plan.runId;
      state.chatAttachment=null;state.chatAttachmentObserved=false;
      activateChatDraft(plan.runId,{restore:false});
      renderChatMessages();
    };
    return Object.freeze(methods);
  }
  return Object.freeze({createController,nodeIds:Object.freeze(["chatAttachButton","chatBranchBadge","chatComposerHint","chatContextActions","chatContextClear","chatContextFileInput","chatContextFiles","chatContextPack","chatContextPackSummary","chatDraftClear","chatDraftStatus","chatForm","chatHistoryBadge","chatHistoryButton","chatHistoryClearSearch","chatHistoryDialog","chatHistoryList","chatHistoryRefresh","chatHistorySearch","chatHistoryStatus","chatInput","chatJumpLatest","chatJumpLatestStatus","chatLayout","chatMessages","chatMeta","chatQueue","chatResumeContract","chatRouteCard","chatRouteDetail","chatRouteModel","chatRouteNotice","chatRouteState","chatRunContractContext","chatRunContractEngine","chatRunContractModel","chatRunContractReasoning","chatRunFrequencyPenalty","chatRunPresencePenalty","chatRunSamplerFields","chatRunSamplingHelp","chatRunSamplingMode","chatRunSeed","chatRunSettingsButton","chatRunSettingsCancel","chatRunSettingsClose","chatRunSettingsFields","chatRunSettingsForm","chatRunSettingsPanel","chatRunSettingsSave","chatRunSettingsScrim","chatRunSettingsStatus","chatRunSystemPrompt","chatRunTemperature","chatRunTopK","chatRunTopP","chatSendButton","chatSidebar","chatSidebarClearSearch","chatSidebarList","chatSidebarManage","chatSidebarNew","chatSidebarSearch","chatSidebarStatus","chatSidebarToggle","chatStatusCacheValue","chatStatusDisclosureLabel","chatStatusEngine","chatStatusLaneValue","chatStatusModel","chatStatusPanel","chatStatusRouteState","chatStatusSpeedValue","chatStatusSummary","chatStatusWarning","chatStopButton","chatTitle","chatTranscriptCount","chatTranscriptHint","chatTranscriptNext","chatTranscriptPrevious","chatTranscriptSearch","chatTranscriptSearchClose","chatTranscriptSearchInput","chatTranscriptSearchStatus","chatTranscriptSearchToggle","chatTranscriptToolbar","chatTrimButton","chatUsage","chatUsageDetail","chatUsageMeter","chatUsageValue","chatWorkspace","chatWorkspaceButton","chatWorkspaceClear","chatWorkspaceContext","chatWorkspaceFolderInput","chatWorkspaceName","chatWorkspaceSelection","chatWorkspaceSummary","configSubtitle","endChatButton","newChatButton","openChatHistoryTop"])});
});
