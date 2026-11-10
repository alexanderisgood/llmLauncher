(function installAgentConsoleWorkspace(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LLMAgentConsoleWorkspace = api;
})(typeof globalThis === "object" ? globalThis : this, function agentConsoleWorkspaceFactory() {
  "use strict";
  function createController({elements, endpoints, navigation, onHubStatus, activitySnapshot,
    storage, copyText, alertUser, notify:showNotice, sessionRouteActive, surfacePostmortemMarker,
    backendName, clientName, formatBytes, formatNumber, formatShortDuration, formatTimestamp,
    liveRequestPhaseLabel, liveRequestDetail, cores}) {
    const {TerminalCore, AgentConsoleTabsCore, AgentConsoleInputCore, ChatDraftsCore,
      PiTimelineCore, ChatStatusCore, UiPresenter, timelineViewFactory} = cores;
    const $ = id => elements[id];
    // The DOM comes from the owned workspace node; callers do not supply a
    // document lookup or application state object.
    const document = $("agentWorkspace").ownerDocument;
    const window = document.defaultView;
    const requestAnimationFrame = callback => window.requestAnimationFrame(callback);
    const setTimeout = (callback, delay) => window.setTimeout(callback, delay);
    const clearTimeout = handle => window.clearTimeout(handle);
    const setInterval = (callback, delay) => window.setInterval(callback, delay);
    const clearInterval = handle => window.clearInterval(handle);
    const performance = window.performance;
    const ResizeObserver = window.ResizeObserver;
    const sessionStorage = storage;
    const esc = value => String(value ?? "").replace(/[&<>"']/g, character => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[character]);
    const agentPiTimelineView = timelineViewFactory({document, core:PiTimelineCore, formatTimestamp});
    let runSnapshot = null, disposed = false;
    const state = {agentConsoleOwnerRunId:"", agentConsoleSurfaceId:"", agentConsoleMeta:null,
      agentConsoleViews:{}, agentConsoleRecoveryOwnerRunId:"", agentConsoleTimer:null,
      agentConsoleReading:false, agentConsoleReadGeneration:0, agentConsoleVisible:false,
      agentConsoleBusy:false, agentConsoleResizeTimer:null, agentConsoleDismissed:false,
      agentConsoleSearchOpen:false, agentConsoleSearchQuery:"", agentConsoleSearchIndex:-1,
      agentConsoleCopyBusy:false};
    Object.defineProperties(state, {
      runStatus:{get:() => runSnapshot}, runPhase:{get:() => runSnapshot?.phase || "idle"},
      requestActivity:{get:() => activitySnapshot()},
    });
    const requestMethods = Object.freeze({
      "/api/agent-console/read":"read", "/api/agent-console/input":"input",
      "/api/agent-console/resize":"resize", "/api/agent-console/stop":"stop",
      "/api/agent-console/restart":"restart", "/api/hub/fans":"fans",
    });
    // Only these six explicit endpoint methods are available to this feature.
    const api = (path, options = {}) => {
      const method = requestMethods[path];
      if (!method || typeof endpoints[method] !== "function") throw new Error("Agent Console endpoint unavailable.");
      return endpoints[method](options.body ? JSON.parse(options.body) : {});
    };
    const listeners = [];
    function listen(target, name, handler, options) {
      target.addEventListener(name, handler, options); listeners.push([target, name, handler, options]);
    }
    function observeStatus(status, run = status?.run, phase = status?.phase || "idle") {
      if (disposed) return [];
      runSnapshot = status ? {...status, run, phase} : {run, phase};
      return syncAgentConsoleViews(runSnapshot, run, phase);
    }
    function suspend() {
      saveAgentConsoleDraft(); state.agentConsoleVisible = false; state.agentConsoleDismissed = true;
      invalidateAgentConsoleRead(); persistAgentConsoleRecovery();
    }
const AGENT_CONSOLE_RECOVERY_KEY = "llm-launcher-agent-console-view-v1";
const AGENT_CONSOLE_DRAFTS_KEY = "llm-launcher-agent-console-drafts-v1";
const AGENT_CONSOLE_DRAFT_OPTIONS = Object.freeze({
  maximumDrafts:12, maximumDraftCharacters:200_000, maximumTotalCharacters:800_000,
});
let agentConsoleDraftEnvelope = null;
function updateAgentConsoleStatusSummaryLabel() {
  const summary = $("agentConsoleStatusSummary");
  const panel = $("agentConsoleStatusPanel");
  if (!summary || !panel) return;
  const processState = $("agentConsoleStatusState")?.hidden
    ? "" : $("agentConsoleStatusState")?.textContent;
  UiPresenter.attribute(summary, "aria-label", [
    $("agentConsoleStatusSurface")?.textContent,
    $("agentConsoleStatusModel")?.textContent,
    `Speed ${$("agentConsoleStatusSpeedValue")?.textContent || "not reported"}`,
    `Prompt processing ${$("agentConsoleStatusPromptValue")?.textContent || "not reported"}`,
    `Context ${$("agentConsoleStatusContextValue")?.textContent || "not reported"}`,
    $("agentConsoleContextTokens")?.textContent,
    `Lane ${$("agentConsoleStatusLaneValue")?.textContent || "unknown"}`,
    processState,
    panel.open ? "Hide full Agent Console status details" : "Show full Agent Console status details",
  ].filter(Boolean).join(". "));
}

function renderAgentConsoleStatusDisclosure() {
  const panel = $("agentConsoleStatusPanel");
  if (!panel) return;
  $("agentConsoleStatusDisclosureLabel").textContent = panel.open ? "Hide" : "Details";
  updateAgentConsoleStatusSummaryLabel();
}

function syncAgentConsoleStatusDetailMode(detail = "focused") {
  const panel = $("agentConsoleStatusPanel");
  if (!panel) return;
  panel.open = false;
  renderAgentConsoleStatusDisclosure();
}

function agentConsoleBaseOffset(meta = {}) {
  return AgentConsoleTabsCore.safeOffset(meta.bufferBaseOffset ?? meta.baseOffset ?? meta.droppedBytes);
}

function agentConsoleBufferEnd(meta = {}) {
  return AgentConsoleTabsCore.safeOffset(meta.bufferEnd ?? meta.outputRevision ?? meta.nextOffset);
}

function createAgentConsoleView(meta = {}, savedSeenEnd = null) {
  const base = agentConsoleBaseOffset(meta);
  const end = agentConsoleBufferEnd(meta);
  return {
    meta:{...meta},
    terminal:new TerminalCore.TerminalBuffer(100, 30, 2000),
    decoder:new TextDecoder("utf-8", {fatal:false}),
    offset:base,
    seenEnd:savedSeenEnd === null ? end : AgentConsoleTabsCore.safeOffset(savedSeenEnd),
    renderedText:"",
    loaded:false,
    recovering:false,
    unreadBytes:0,
    inputQueue:[],
    inputSending:false,
    inputInFlightPromptCount:0,
    inputError:"",
    inputRetryPending:false,
    abortBusy:false,
    abortRequest:null,
    readDrainRemaining:AgentConsoleTabsCore.FINAL_DRAIN_READS,
    readIdleCount:0,
    postmortem:null,
    timeline:PiTimelineCore.emptyTimeline(),
    timelineSeenRevision:0,
    timelineLoaded:false,
    piFollowTail:true,
    piLastScrollTop:0,
    piNewOutput:false,
  };
}

function currentAgentConsoleView() {
  return state.agentConsoleViews[state.agentConsoleSurfaceId] || null;
}

function agentConsoleRunDraftKey() {
  const owner = AgentConsoleTabsCore.safeId(state.agentConsoleOwnerRunId);
  const surface = AgentConsoleTabsCore.safeId(state.agentConsoleSurfaceId);
  return owner && surface ? `${owner}:${surface}` : "";
}

function agentConsoleDraftKey() {
  const meta = currentAgentConsoleView()?.meta;
  const namespace = meta?.protocol === "pi-rpc" ? "pi" : meta?.protocol === "omp-rpc" ? "omp" : "";
  const conversation = namespace ? meta.conversationId : "";
  return typeof conversation === "string" && /^[a-f0-9]{64}$/.test(conversation)
    ? `${namespace}:${conversation}` : agentConsoleRunDraftKey();
}

function agentConsoleDrafts() {
  if (!agentConsoleDraftEnvelope) {
    let saved = null;
    try { saved = JSON.parse(sessionStorage.getItem(AGENT_CONSOLE_DRAFTS_KEY) || "null"); }
    catch (_) {}
    agentConsoleDraftEnvelope = ChatDraftsCore.normaliseEnvelope(saved, AGENT_CONSOLE_DRAFT_OPTIONS);
  }
  return agentConsoleDraftEnvelope;
}

function persistAgentConsoleDraft(key, text) {
  if (!key) return;
  // Keep an oversized draft intact in the composer; never save a truncated
  // instruction which could later be mistaken for the complete message.
  const value = text.length <= AGENT_CONSOLE_DRAFT_OPTIONS.maximumDraftCharacters ? text : "";
  agentConsoleDraftEnvelope = ChatDraftsCore.writeDraft(
    agentConsoleDrafts(), key, value, Date.now(), AGENT_CONSOLE_DRAFT_OPTIONS,
  );
  try { sessionStorage.setItem(AGENT_CONSOLE_DRAFTS_KEY, JSON.stringify(agentConsoleDraftEnvelope)); }
  catch (_) {}
}

function migrateAgentConsoleDraft(key) {
  const legacyKey = agentConsoleRunDraftKey();
  if (!legacyKey || legacyKey === key) return;
  const envelope = agentConsoleDrafts();
  // Only migrate this console's pre-identity draft. Never overwrite an existing
  // conversation draft or borrow one from another run merely by recency.
  if (!envelope.drafts[legacyKey] || envelope.drafts[key]) return;
  agentConsoleDraftEnvelope = ChatDraftsCore.moveDraft(
    envelope, legacyKey, key, AGENT_CONSOLE_DRAFT_OPTIONS,
  );
  try { sessionStorage.setItem(AGENT_CONSOLE_DRAFTS_KEY, JSON.stringify(agentConsoleDraftEnvelope)); }
  catch (_) {}
}

function saveAgentConsoleDraft() {
  const input = $("agentConsoleInput");
  const key = input.dataset.draftKey;
  const view = currentAgentConsoleView();
  if (!view || !key || key !== agentConsoleDraftKey()) return;
  if (view.inputDraft === input.value) return;
  view.inputDraft = input.value;
  view.inputDraftTypedUnbound = key === agentConsoleRunDraftKey();
  persistAgentConsoleDraft(key, input.value);
}

function restoreAgentConsoleDraft() {
  const input = $("agentConsoleInput");
  const key = agentConsoleDraftKey();
  const view = currentAgentConsoleView();
  if (input.dataset.draftKey === key && view?.inputDraftKey === key) return;
  if (view?.inputDraftKey && view.inputDraftKey === input.dataset.draftKey) {
    // A /new or /resume may change Pi's identity within the same console.
    persistAgentConsoleDraft(view.inputDraftKey, input.value);
  }
  if (view && view.inputDraftKey !== key) {
    // Only bind text typed here before this console's first reported identity.
    // Stored legacy drafts have no trustworthy conversation binding: /new may
    // have changed sessions since they were saved.
    if (view.inputDraftTypedUnbound && !view.inputDraftConversationSeen
        && view.inputDraftKey === agentConsoleRunDraftKey()) migrateAgentConsoleDraft(key);
    view.inputDraft = ChatDraftsCore.readDraft(agentConsoleDrafts(), key, AGENT_CONSOLE_DRAFT_OPTIONS);
    view.inputDraftKey = key;
    view.inputDraftTypedUnbound = false;
    if (/^(pi|omp):/.test(key)) view.inputDraftConversationSeen = true;
  }
  input.value = view?.inputDraft || "";
  input.dataset.draftKey = key;
  input.setCustomValidity("");
}

function recoverableAgentConsoleDrafts() {
  const current = agentConsoleDraftKey();
  return Object.entries(agentConsoleDrafts().drafts)
    .filter(([key]) => key !== current)
    .sort((a, b) => b[1].updatedAt - a[1].updatedAt);
}

function openAgentConsoleDrafts() {
  saveAgentConsoleDraft();
  const list = $("agentConsoleDraftsList");
  list.replaceChildren();
  for (const [key, draft] of recoverableAgentConsoleDrafts()) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary agent-console-saved-draft";
    const preview = document.createElement("span");
    preview.textContent = draft.text.slice(0, 240);
    const time = document.createElement("small");
    time.textContent = new Date(draft.updatedAt).toLocaleString();
    button.append(preview, time);
    button.addEventListener("click", () => recoverAgentConsoleDraft(key));
    list.append(button);
  }
  $("agentConsoleDraftsStatus").textContent = list.children.length ? "" : "No other saved drafts.";
  $("agentConsoleDraftsDialog").showModal();
}

function recoverAgentConsoleDraft(sourceKey) {
  const input = $("agentConsoleInput");
  const view = currentAgentConsoleView();
  const destination = agentConsoleDraftKey();
  const envelope = agentConsoleDrafts();
  const text = ChatDraftsCore.readDraft(envelope, sourceKey, AGENT_CONSOLE_DRAFT_OPTIONS);
  if (!view || !destination || !text || sourceKey === destination) return;
  if (input.value || ChatDraftsCore.readDraft(envelope, destination, AGENT_CONSOLE_DRAFT_OPTIONS)) {
    $("agentConsoleDraftsStatus").textContent = "Send or clear the current draft first; it has been kept.";
    return;
  }
  agentConsoleDraftEnvelope = ChatDraftsCore.moveDraft(
    envelope, sourceKey, destination, AGENT_CONSOLE_DRAFT_OPTIONS,
  );
  try { sessionStorage.setItem(AGENT_CONSOLE_DRAFTS_KEY, JSON.stringify(agentConsoleDraftEnvelope)); }
  catch (_) {}
  // Invalidate a cached source view so revisiting it cannot resurrect the moved
  // draft. Draft recovery never queues input or invokes the agent API.
  for (const other of Object.values(state.agentConsoleViews)) {
    if (other.inputDraftKey === sourceKey) other.inputDraftKey = "";
  }
  view.inputDraft = text;
  view.inputDraftKey = destination;
  input.dataset.draftKey = destination;
  input.value = text;
  input.setCustomValidity("");
  $("agentConsoleDraftsDialog").close();
  input.focus();
}

function reconcileAgentConsoleViewMeta(view, incoming = {}) {
  if (!view) return {meta:{...incoming}, generationChanged:false, stale:false};
  const result = AgentConsoleTabsCore.reconcileConsoleMeta(view.meta, incoming);
  view.meta = result.meta;
  if (result.generationChanged) {
    view.abortBusy = false;
    view.abortRequest = null;
  }
  return result;
}

function resetAgentConsoleTerminal(
  view = currentAgentConsoleView(), baseOffset = null,
  {renderPlaceholder = true, clearInput = true} = {},
) {
  if (!view) {
    $("agentTerminalOutput").textContent = "Waiting for agent output…";
    $("agentTerminalOutput").removeAttribute("data-console-surface");
    $("agentConsoleJumpLatest").hidden = true;
    return;
  }
  const base = baseOffset === null ? agentConsoleBaseOffset(view.meta) : AgentConsoleTabsCore.safeOffset(baseOffset);
  const cols = view.terminal?.cols || Number(view.meta?.cols) || 100;
  const rows = view.terminal?.rows || Number(view.meta?.rows) || 30;
  view.terminal = new TerminalCore.TerminalBuffer(cols, rows, 2000);
  view.decoder = new TextDecoder("utf-8", {fatal:false});
  view.terminalSuppressed = false;
  view.offset = base;
  view.renderedText = "";
  view.loaded = false;
  if (clearInput) {
    view.inputQueue = [];
    view.inputInFlightPromptCount = 0;
    view.inputError = "";
    view.inputRetryPending = false;
    view.abortBusy = false;
    view.abortRequest = null;
  }
  if (renderPlaceholder && view === currentAgentConsoleView()) {
    $("agentTerminalOutput").textContent = "Waiting for agent output…";
    $("agentTerminalOutput").dataset.consoleSurface = state.agentConsoleSurfaceId;
    $("agentConsoleJumpLatest").hidden = true;
  }
}

function resetAgentPiTimeline(view = currentAgentConsoleView(), {renderPlaceholder = true} = {}) {
  if (view) {
    view.readIdleCount = 0;
    view.timeline = PiTimelineCore.emptyTimeline();
    view.timelineSeenRevision = 0;
    view.timelineLoaded = false;
    view.piFollowTail = true;
    view.piLastScrollTop = 0;
    view.piNewOutput = false;
  }
  if (renderPlaceholder && (!view || view === currentAgentConsoleView())) {
    agentPiTimelineView.clear($("agentPiTimeline"));
    $("agentPiTimelineEmpty").hidden = false;
    $("agentPiTimelineJumpLatest").hidden = true;
  }
}

function readAgentConsoleRecovery(ownerRunId, surfaceIds) {
  let value = null;
  try { value = JSON.parse(sessionStorage.getItem(AGENT_CONSOLE_RECOVERY_KEY) || "null"); }
  catch (_) {}
  return AgentConsoleTabsCore.normalizeRecovery(value, ownerRunId, surfaceIds);
}

function persistAgentConsoleRecovery() {
  const ownerRunId = state.agentConsoleOwnerRunId;
  const surfaceIds = Object.keys(state.agentConsoleViews);
  if (!ownerRunId || !surfaceIds.length) return;
  const seen = Object.fromEntries(surfaceIds.map(id => [id, state.agentConsoleViews[id]?.seenEnd || 0]));
  const value = AgentConsoleTabsCore.buildRecovery(
    ownerRunId, state.agentConsoleSurfaceId, state.agentConsoleVisible, seen, surfaceIds,
  );
  try { sessionStorage.setItem(AGENT_CONSOLE_RECOVERY_KEY, JSON.stringify(value)); }
  catch (_) {}
}

function removeAgentConsoleRecovery() {
  try { sessionStorage.removeItem(AGENT_CONSOLE_RECOVERY_KEY); }
  catch (_) {}
}

function clearAgentConsoleSelection(removeRecovery = true) {
  saveAgentConsoleDraft();
  $("agentConsoleInput").dataset.draftKey = "";
  invalidateAgentConsoleRead();
  if (state.agentConsoleResizeTimer !== null) clearTimeout(state.agentConsoleResizeTimer);
  state.agentConsoleResizeTimer = null;
  state.agentConsoleOwnerRunId = "";
  state.agentConsoleSurfaceId = "";
  state.agentConsoleMeta = null;
  state.agentConsoleViews = {};
  state.agentConsoleRecoveryOwnerRunId = "";
  state.agentConsoleVisible = false;
  state.agentConsoleSearchOpen = false;
  state.agentConsoleSearchQuery = "";
  state.agentConsoleSearchIndex = -1;
  $("agentConsoleTabs").replaceChildren();
  $("agentConsoleSearch").classList.add("hidden");
  $("agentConsoleFindButton").setAttribute("aria-expanded", "false");
  $("agentConsoleSearchInput").value = "";
  resetAgentConsoleTerminal(null);
  resetAgentPiTimeline(null);
  if (removeRecovery) removeAgentConsoleRecovery();
}

function agentConsoleDescriptors(status = state.runStatus, ownerRunId = state.agentConsoleOwnerRunId) {
  const attachments = (Array.isArray(status?.attachments) ? status.attachments : [])
    .filter(item => item?.agentHost === "console" && item.ownerRunId === ownerRunId);
  const records = new Map(
    (Array.isArray(status?.agentConsoles) ? status.agentConsoles : [])
      .filter(item => item?.ownerRunId === ownerRunId)
      .map(item => [item.surfaceId || item.id, item]),
  );
  const result = attachments.map(attachment => {
    const consoleRecord = records.get(attachment.id) || null;
    records.delete(attachment.id);
    return {attachment, consoleRecord, meta:{...attachment, ...(consoleRecord || {})}};
  });
  for (const [id, consoleRecord] of records) {
    const attachment = {
      id, ownerRunId, agentHost:"console", primary:false,
      client:consoleRecord.client, surface:consoleRecord.surface,
      project:consoleRecord.project, backend:consoleRecord.backend,
      model:consoleRecord.model, status:consoleRecord.state,
    };
    result.push({attachment, consoleRecord, meta:{...attachment, ...consoleRecord}});
  }
  return result.slice(0, AgentConsoleTabsCore.MAX_TABS);
}

function retainAgentConsoleView(view, phase, message) {
  if (!view) return null;
  const surface = view.meta?.surface || clientName(view.meta?.client) || "Agent";
  const next = surfacePostmortemMarker(
    phase, message, `${surface} route`,
  );
  const previousFailed = view.postmortem?.state === "failed"
    || view.meta?.state === "failed" || view.meta?.status === "failed";
  const marker = previousFailed && next.state !== "failed"
    ? view.postmortem || surfacePostmortemMarker(
      "failed", view.meta?.detail || message, `${surface} route`,
    )
    : next;
  view.postmortem = marker;
  view.meta = {
    ...view.meta,
    state:marker.state,
    status:marker.state,
    detail:marker.detail,
    streaming:false,
    canInput:false,
    canStop:false,
    canRestart:false,
  };
  view.abortBusy = false;
  view.abortRequest = null;
  if (view.inputQueue.length) view.inputRetryPending = true;
  return marker;
}

function retainAgentConsoleViews(phase, message) {
  if (state.agentConsoleTimer !== null) clearTimeout(state.agentConsoleTimer);
  state.agentConsoleTimer = null;
  for (const view of Object.values(state.agentConsoleViews)) {
    retainAgentConsoleView(view, phase, message);
  }
  const selected = currentAgentConsoleView();
  if (selected) state.agentConsoleMeta = selected.meta;
  persistAgentConsoleRecovery();
  return Object.keys(state.agentConsoleViews).length;
}

function syncAgentConsoleViews(status = state.runStatus, run = status?.run, phase = status?.phase || state.runPhase) {
  const routeActive = sessionRouteActive(run, phase);
  if (!routeActive) {
    if (state.agentConsoleOwnerRunId || Object.keys(state.agentConsoleViews).length) {
      retainAgentConsoleViews(phase, status?.message);
    }
    return [];
  }
  const ownerRunId = run.runId;
  const descriptors = agentConsoleDescriptors(status, ownerRunId);
  if (
    !descriptors.length && run.client !== "chat" && run.agentHost === "console"
  ) {
    const attachment = {
      id:ownerRunId, ownerRunId, primary:true, agentHost:"console",
      client:run.client, surface:clientName(run.client), backend:run.backend,
      model:run.model, project:run.project, status:phase,
      detail:phase === "running"
        ? "Agent is running in the launcher-owned Hub Console."
        : "Loading the model before Hub Console opens.",
    };
    descriptors.push({attachment, consoleRecord:null, meta:{...attachment}});
  }
  const surfaceIds = descriptors.map(item => item.attachment.id);
  const ownerChanged = state.agentConsoleOwnerRunId !== ownerRunId;
  let recovery = null;
  if (ownerChanged) {
    clearAgentConsoleSelection(false);
    state.agentConsoleOwnerRunId = ownerRunId;
    recovery = readAgentConsoleRecovery(ownerRunId, surfaceIds);
    state.agentConsoleRecoveryOwnerRunId = recovery.valid ? ownerRunId : "";
  }

  const allowed = new Set(surfaceIds);
  for (const id of Object.keys(state.agentConsoleViews)) {
    if (!allowed.has(id)) {
      retainAgentConsoleView(
        state.agentConsoleViews[id], "stopped",
        "This Hub Console surface is no longer attached to the active route.",
      );
    }
  }
  for (const descriptor of descriptors) {
    const id = descriptor.attachment.id;
    let view = state.agentConsoleViews[id];
    if (!view) {
      const savedSeen = recovery?.valid && Object.prototype.hasOwnProperty.call(recovery.seen, id)
        ? recovery.seen[id] : null;
      view = createAgentConsoleView(descriptor.meta, savedSeen);
      state.agentConsoleViews[id] = view;
    } else {
      view.postmortem = null;
      const reconciliation = reconcileAgentConsoleViewMeta(view, descriptor.meta);
      if (reconciliation.generationChanged || AgentConsoleTabsCore.consoleNeedsReplay(view.meta, view.offset)) {
        view.recovering = true;
      }
      if (reconciliation.generationChanged) resetAgentPiTimeline(view, {renderPlaceholder:false});
    }
  }

  const primary = descriptors.find(item => item.attachment.primary) || null;
  if (!state.agentConsoleViews[state.agentConsoleSurfaceId]) {
    const recoveredId = recovery?.activeSurfaceId;
    state.agentConsoleSurfaceId = state.agentConsoleViews[recoveredId]
      ? recoveredId : primary?.attachment.id || surfaceIds[0] || "";
  }
  if (ownerChanged) {
    const primaryConsole = run.client !== "chat" && run.agentHost === "console";
    state.agentConsoleVisible = recovery?.valid
      ? Boolean(recovery.visible && state.agentConsoleSurfaceId)
      : Boolean(primaryConsole && state.agentConsoleSurfaceId);
    state.agentConsoleDismissed = !state.agentConsoleVisible;
  }
  const selected = currentAgentConsoleView();
  if (selected) {
    state.agentConsoleMeta = selected.meta;
    if (state.agentConsoleVisible && selected.loaded) {
      selected.seenEnd = Math.max(selected.seenEnd, selected.offset);
      selected.timelineSeenRevision = Math.max(
        selected.timelineSeenRevision,
        PiTimelineCore.safeRevision(selected.timeline?.revision),
      );
    }
  } else state.agentConsoleMeta = null;
  persistAgentConsoleRecovery();
  return descriptors;
}

function enterAgentConsole(attachment) {
  if (!attachment || attachment.agentHost !== "console") return;
  const ownerRunId = attachment.ownerRunId;
  const surfaceId = attachment.id || attachment.surfaceId;
  if (!ownerRunId || !surfaceId) return;
  if (state.agentConsoleOwnerRunId && state.agentConsoleOwnerRunId !== ownerRunId) {
    clearAgentConsoleSelection(false);
  }
  state.agentConsoleOwnerRunId = ownerRunId;
  if (!state.agentConsoleViews[surfaceId]) {
    state.agentConsoleViews[surfaceId] = createAgentConsoleView(attachment);
  } else {
    state.agentConsoleViews[surfaceId].postmortem = null;
    reconcileAgentConsoleViewMeta(state.agentConsoleViews[surfaceId], attachment);
  }
  selectAgentConsole(surfaceId, {focus:true, show:true});
  navigation.closeSessions();
}

function selectAgentConsole(surfaceId, {focus = true, show = true} = {}) {
  const view = state.agentConsoleViews[surfaceId];
  if (!view) return;
  saveAgentConsoleDraft();
  if (state.agentConsoleTimer !== null) clearTimeout(state.agentConsoleTimer);
  state.agentConsoleTimer = null;
  state.agentConsoleSurfaceId = surfaceId;
  state.agentConsoleMeta = view.meta;
  state.agentConsoleVisible = show;
  state.agentConsoleDismissed = !show;
  state.agentConsoleSearchIndex = -1;
  view.seenEnd = Math.max(view.seenEnd, view.offset);
  view.timelineSeenRevision = Math.max(
    view.timelineSeenRevision,
    PiTimelineCore.safeRevision(view.timeline?.revision),
  );
  persistAgentConsoleRecovery();
  if (state.runStatus?.run?.runId === state.agentConsoleOwnerRunId) {
    navigation.refreshChat(state.runStatus.run, state.runPhase);
    updateAgentWorkspace(state.runStatus.run, state.runPhase);
    if (agentConsoleShowsPiTimeline(view)) renderAgentPiTimeline({preserveScroll:false});
    else renderAgentTerminalOutput({preserveScroll:false});
  }
  scheduleAgentConsoleRead(view.loaded ? 0 : 40);
  scheduleAgentConsoleResize();
  if (focus) requestAnimationFrame(() => (
    agentConsoleShowsPiTimeline(view) ? $("agentPiTimelineViewport") : $("agentTerminalViewport")
  ).focus());
}

function leaveAgentConsole() {
  saveAgentConsoleDraft();
  state.agentConsoleVisible = false;
  state.agentConsoleDismissed = true;
  if (state.agentConsoleTimer !== null) clearTimeout(state.agentConsoleTimer);
  state.agentConsoleTimer = null;
  persistAgentConsoleRecovery();
  navigation.refreshChat(state.runStatus?.run, state.runPhase);
  updateAgentWorkspace(state.runStatus?.run, state.runPhase);
}

function currentAgentConsoleAttachment(status = state.runStatus) {
  const attachments = Array.isArray(status?.attachments) ? status.attachments : [];
  return attachments.find(item => item.id === state.agentConsoleSurfaceId && item.agentHost === "console") || null;
}

function currentAgentConsoleRecord(status = state.runStatus) {
  const consoles = Array.isArray(status?.agentConsoles) ? status.agentConsoles : [];
  return consoles.find(item => item.surfaceId === state.agentConsoleSurfaceId) || null;
}

function agentConsoleRequestActivity(surfaceId = state.agentConsoleSurfaceId) {
  const report = state.requestActivity || {};
  const active = Array.isArray(report.active) ? report.active : [];
  const queued = Array.isArray(report.queued) ? report.queued : [];
  const recent = Array.isArray(report.recent) ? report.recent : [];
  return {
    report,
    current:[...active, ...queued].find(item => item.surfaceId === surfaceId) || null,
    latest:recent.find(item => item.surfaceId === surfaceId) || null,
  };
}

let relaySample = null;
function relayProgress(request) {
  const bytes = request?.bytesRelayed;
  if (request?.state !== "running" || !request.id || !Number.isFinite(bytes) || bytes < 0) {
    relaySample = null;
    return null;
  }
  const now = performance.now();
  if (relaySample?.id !== request.id || bytes < relaySample.bytes) {
    relaySample = {id:request.id, bytes, lastChange:now, advanced:false};
  } else if (bytes > relaySample.bytes) {
    relaySample = {id:request.id, bytes, lastChange:now, advanced:true};
  }
  return {advanced:relaySample.advanced, quietSeconds:Math.floor((now - relaySample.lastChange) / 1000)};
}

function renderAgentActivity({report, current}, meta, view, postmortem) {
  const strip = $("agentConsoleLivePhase");
  if (postmortem || (!current && !meta.streaming && !meta.compacting)) {
    strip.hidden = true;
    relaySample = null;
    return "";
  }

  const items = meta.protocol === "omp-rpc" && meta.streaming ? view?.timeline?.items || [] : [];
  const waitingForWork = items.some(item => item.kind === "toolCall" && item.title === "Running · wait");
  const agentUpdate = items.findLast(item => item.kind === "toolResult" && item.title === "Running · task");
  const age = Date.now() - Date.parse(agentUpdate?.createdAt);
  const name = age >= 0 && age < 15_000
    ? /^Running agent ([\w .-]{1,72}?)\.\.\./.exec(agentUpdate.text)?.[1] : "";
  const progress = relayProgress(current);
  const active = Number.isInteger(report.activeCount) ? report.activeCount : report.active?.length || 0;
  const queued = Number.isInteger(report.queuedCount) ? report.queuedCount : report.queued?.length || 0;
  const lanes = Number(report.lanes) || 0;
  const details = [];
  let phase = meta.compacting ? "Compacting context" : "Agent working";
  let tone = "waiting";
  if (waitingForWork) phase = name ? "Waiting for background agents" : "Waiting for background work";
  else if (name) phase = "Background agents working";
  else if (!meta.compacting && current) phase = ChatStatusCore.requestPhase(current).replace(/…$/, "") || phase;
  if (current?.state === "running") {
    if (progress?.quietSeconds >= 8) {
      details.push(`No new response data for ${formatShortDuration(progress.quietSeconds)}`);
      tone = "quiet";
      if (!waitingForWork && !name) phase = "Waiting for model output";
    } else if (progress?.advanced && current.firstOutputAt) {
      details.push("Response data flowing");
      tone = "flowing";
    } else {
      details.push(current.firstOutputAt ? "Model request active" : "Waiting for first output");
    }
    if (Number.isFinite(current.runSeconds)) details.push(formatShortDuration(current.runSeconds) + " elapsed");
  } else if (current?.state === "queued") {
    details.push(`Model request queued #${current.queuePosition || 1}`);
    if (Number.isFinite(current.waitSeconds)) details.push(formatShortDuration(current.waitSeconds) + " waiting");
  }
  if (name) details.push(`Agent update: ${name}`);
  UiPresenter.property($("agentConsoleLivePhaseText"), "textContent", phase);
  UiPresenter.property($("agentConsoleLiveDetail"), "textContent", details.join(" · "));
  UiPresenter.property($("agentConsoleLiveDetail"), "hidden", !details.length);
  const queue = $("agentConsoleLiveQueue");
  UiPresenter.property(queue, "hidden", !active && !queued);
  UiPresenter.property(queue, "textContent", `${active} running · ${queued} queued${lanes ? ` · ${lanes} lane${lanes === 1 ? "" : "s"}` : ""}`);
  UiPresenter.property(queue, "title", "Model requests on the shared runtime. Follow-up messages have a separate queue.");
  UiPresenter.data(strip, "state", tone);
  UiPresenter.property(strip, "hidden", false);
  return tone;
}

function agentConsoleProjectName(value) {
  return String(value || "").split("/").filter(Boolean).pop() || "Project";
}

function renderAgentConsoleTabs() {
  const views = Object.entries(state.agentConsoleViews);
  const tabs = $("agentConsoleTabs");
  const rows = views.map(([id, view]) => {
    const activity = agentConsoleRequestActivity(id).current;
    const attachment = view.meta;
    const structuredPi = agentConsoleShowsPiTimeline(view);
    const localTimelineRevision = PiTimelineCore.safeRevision(view.timeline?.revision);
    const availableTimelineRevision = PiTimelineCore.timelineAvailableRevision(
      view.timeline, view.meta,
    );
    const consoleRecord = structuredPi ? {
      ...view.meta,
      bufferEnd:availableTimelineRevision,
      outputRevision:availableTimelineRevision,
    } : view.meta;
    const active = id === state.agentConsoleSurfaceId;
    const presentation = AgentConsoleTabsCore.tabPresentation({
      attachment, consoleRecord, activity, active,
      seenEnd:structuredPi ? view.timelineSeenRevision : view.seenEnd,
    });
    view.unreadBytes = active && state.agentConsoleVisible
      ? Math.max(0, presentation.end - (structuredPi ? localTimelineRevision : view.offset))
      : presentation.unreadBytes;
    const surface = attachment.surface || clientName(attachment.client) || "Agent";
    const project = agentConsoleProjectName(attachment.project);
    const marker = attachment.primary ? "Primary" : project;
    const label = `${surface}, ${marker}, ${presentation.label}`;
    const badge = presentation.unreadBytes > 0 && !active
      ? structuredPi ? `${presentation.label} · new events`
        : `${presentation.label} · ${formatBytes(presentation.unreadBytes)}`
      : presentation.label;
    const controls = structuredPi ? "agentPiTimelineViewport" : "agentTerminalViewport";
    return `<button id="agent-console-tab-${esc(id)}" type="button" role="tab" data-agent-console-tab="${esc(id)}" aria-selected="${active}" aria-controls="${controls}" aria-label="${esc(label)}" tabindex="${active ? "0" : "-1"}" class="agent-console-tab ${active ? "active" : ""} ${esc(presentation.tone)}"><i aria-hidden="true"></i><span><strong>${esc(surface)}</strong><small>${esc(marker)}</small></span><em>${esc(badge)}</em></button>`;
  });
  const markup = rows.join("");
  if (tabs.innerHTML !== markup) tabs.innerHTML = markup;
  const view = currentAgentConsoleView();
  const structuredPi = agentConsoleShowsPiTimeline(view);
  $("agentConsoleFindButton").hidden = structuredPi;
  $("agentConsoleFindButton").disabled = !view || structuredPi;
  $("agentConsoleCopyButton").disabled = !(structuredPi
    ? view?.timeline?.items?.length : view?.renderedText) || state.agentConsoleCopyBusy;
  $("agentConsoleFindButton").setAttribute("aria-expanded", String(state.agentConsoleSearchOpen));
  $("agentConsoleSearch").classList.toggle("hidden", !state.agentConsoleSearchOpen);
}

function agentTerminalIndexedColor(value) {
  const index = Math.max(0, Math.min(255, Number(value) || 0));
  if (index < 16) return `var(--terminal-ansi-${index})`;
  if (index < 232) {
    const offset = index - 16;
    const levels = [0, 95, 135, 175, 215, 255];
    const red = levels[Math.floor(offset / 36) % 6];
    const green = levels[Math.floor(offset / 6) % 6];
    const blue = levels[offset % 6];
    return `rgb(${red} ${green} ${blue})`;
  }
  const grey = 8 + ((index - 232) * 10);
  return `rgb(${grey} ${grey} ${grey})`;
}

function agentTerminalColor(color) {
  if (!color || typeof color !== "object") return "";
  if (color.mode === "indexed") return agentTerminalIndexedColor(color.value);
  if (color.mode === "rgb") {
    const channels = [color.red, color.green, color.blue]
      .map(value => Math.max(0, Math.min(255, Number(value) || 0)));
    return `rgb(${channels.join(" ")})`;
  }
  return "";
}

function applyAgentTerminalStyle(element, style = {}) {
  if (style.bold) element.classList.add("ansi-bold");
  if (style.dim) element.classList.add("ansi-dim");
  if (style.italic) element.classList.add("ansi-italic");
  if (style.underline) element.classList.add("ansi-underline");
  if (style.strike) element.classList.add("ansi-strike");
  let foreground = agentTerminalColor(style.foreground);
  let background = agentTerminalColor(style.background);
  if (style.inverse) {
    [foreground, background] = [
      background || "var(--terminal-background)",
      foreground || "var(--terminal-foreground)",
    ];
  }
  if (foreground) element.style.color = foreground;
  if (background) element.style.backgroundColor = background;
}

function agentConsoleNearBottom(viewport = $("agentTerminalViewport")) {
  return PiTimelineCore.isNearBottom(viewport);
}

function agentPiTimelineNearBottom(viewport = $("agentPiTimelineViewport")) {
  return PiTimelineCore.isNearBottom(viewport);
}

function updateAgentConsoleScrollUi() {
  const view = currentAgentConsoleView();
  const structuredPi = agentConsoleShowsPiTimeline(view);
  $("agentConsoleJumpLatest").hidden = structuredPi || !view || agentConsoleNearBottom();
  const timelineJump = $("agentPiTimelineJumpLatest");
  timelineJump.hidden = !structuredPi || !view || (
    view.piFollowTail !== false && agentPiTimelineNearBottom()
  );
  timelineJump.textContent = view?.piNewOutput ? "\u2193 New output" : "\u2193 Latest";
}

function scrollAgentConsoleToLatest() {
  const viewport = $("agentTerminalViewport");
  viewport.scrollTop = viewport.scrollHeight;
  updateAgentConsoleScrollUi();
  viewport.focus({preventScroll:true});
}

function scrollAgentPiTimelineToLatest() {
  const view = currentAgentConsoleView();
  const viewport = $("agentPiTimelineViewport");
  if (view) {
    view.piFollowTail = true;
    view.piNewOutput = false;
    view.piScrollIntent = "";
  }
  viewport.scrollTop = viewport.scrollHeight;
  if (view) view.piLastScrollTop = viewport.scrollTop;
  updateAgentConsoleScrollUi();
  viewport.focus({preventScroll:true});
}

let agentPiFollowFrame = 0;
function scheduleAgentPiTimelineFollow() {
  if (agentPiFollowFrame) return;
  agentPiFollowFrame = requestAnimationFrame(() => {
    agentPiFollowFrame = 0;
    const view = currentAgentConsoleView();
    const viewport = $("agentPiTimelineViewport");
    if (!view || !agentConsoleShowsPiTimeline(view) || viewport.hidden) return;
    if (view.piFollowTail !== false) {
      viewport.scrollTop = viewport.scrollHeight;
      view.piLastScrollTop = viewport.scrollTop;
      view.piNewOutput = false;
    }
    updateAgentConsoleScrollUi();
  });
}

function recordAgentPiScrollIntent(intent) {
  const view = currentAgentConsoleView();
  if (!view || !agentConsoleShowsPiTimeline(view)) return;
  view.piScrollIntent = intent;
  view.piScrollIntentUntil = performance.now() + 1200;
  if (intent === "up") detachAgentPiTimelineFollow();
}

function handleAgentPiTimelineScroll() {
  const view = currentAgentConsoleView();
  if (!view || !agentConsoleShowsPiTimeline(view)) {
    updateAgentConsoleScrollUi();
    return;
  }
  const viewport = $("agentPiTimelineViewport");
  const nextTop = Math.max(0, Number(viewport.scrollTop) || 0);
  view.piFollowTail = PiTimelineCore.followTailAfterScroll(
    view.piFollowTail,
    view.piLastScrollTop,
    nextTop,
    PiTimelineCore.isNearBottom(viewport, 4),
    performance.now() < (view.piScrollIntentUntil || 0) ? view.piScrollIntent : "",
  );
  view.piLastScrollTop = nextTop;
  if (view.piFollowTail) view.piNewOutput = false;
  updateAgentConsoleScrollUi();
  if (view.piFollowTail !== false && !agentPiTimelineNearBottom(viewport)) scheduleAgentPiTimelineFollow();
}

function detachAgentPiTimelineFollow() {
  const view = currentAgentConsoleView();
  if (!view || !agentConsoleShowsPiTimeline(view)) return;
  view.piFollowTail = false;
  updateAgentConsoleScrollUi();
}

function renderAgentTerminalOutput({preserveScroll = true, focusMatch = false} = {}) {
  const view = currentAgentConsoleView();
  const viewport = $("agentTerminalViewport");
  const output = $("agentTerminalOutput");
  if (!view) {
    output.textContent = "No launcher-owned Agent Console is available.";
    output.removeAttribute("data-console-surface");
    $("agentConsoleJumpLatest").hidden = true;
    return;
  }
  const nearBottom = agentConsoleNearBottom(viewport);
  const text = view.terminal.toString();
  const styledRuns = view.terminal.toStyledRuns?.() || [
    {text, styleKey:"", style:TerminalCore.DEFAULT_STYLE},
  ];
  view.renderedText = text;
  output.dataset.consoleSurface = state.agentConsoleSurfaceId;
  const matches = state.agentConsoleSearchOpen
    ? AgentConsoleTabsCore.findMatches(text, state.agentConsoleSearchQuery) : {ranges:[], truncated:false};
  const hasStyles = styledRuns.some(run => run.styleKey);
  if (!hasStyles && (!state.agentConsoleSearchOpen || !state.agentConsoleSearchQuery || !matches.ranges.length)) {
    output.textContent = text || "Waiting for agent output…";
    state.agentConsoleSearchIndex = matches.ranges.length ? 0 : -1;
  } else {
    if (!matches.ranges.length) state.agentConsoleSearchIndex = -1;
    else if (state.agentConsoleSearchIndex < 0 || state.agentConsoleSearchIndex >= matches.ranges.length) {
      state.agentConsoleSearchIndex = 0;
    }
    const fragment = document.createDocumentFragment();
    TerminalCore.segmentStyledRuns(styledRuns, matches.ranges).forEach(segment => {
      if (segment.matchIndex < 0 && !segment.styleKey) {
        fragment.append(document.createTextNode(segment.text));
        return;
      }
      const element = document.createElement(segment.matchIndex >= 0 ? "mark" : "span");
      element.classList.add("agent-terminal-segment");
      if (segment.matchIndex >= 0) {
        element.classList.toggle("current", segment.matchIndex === state.agentConsoleSearchIndex);
        element.dataset.agentConsoleMatch = String(segment.matchIndex);
      }
      applyAgentTerminalStyle(element, segment.style);
      element.textContent = segment.text;
      fragment.append(element);
    });
    output.replaceChildren(fragment);
  }
  const count = matches.ranges.length;
  $("agentConsoleSearchPrevious").disabled = !count;
  $("agentConsoleSearchNext").disabled = !count;
  $("agentConsoleSearchStatus").textContent = !state.agentConsoleSearchQuery
    ? "Type to search the bounded visible console."
    : !count ? "No matches in this console."
      : `${state.agentConsoleSearchIndex + 1} of ${count}${matches.truncated ? "+" : ""} matches`;
  $("agentConsoleCopyButton").disabled = !text || state.agentConsoleCopyBusy;
  if (focusMatch && count) {
    requestAnimationFrame(() => output.querySelector("mark.current")?.scrollIntoView({block:"center"}));
  } else if (!preserveScroll || nearBottom) {
    viewport.scrollTop = viewport.scrollHeight;
  }
  requestAnimationFrame(updateAgentConsoleScrollUi);
}

function renderAgentPiTimeline({preserveScroll = true} = {}) {
  const view = currentAgentConsoleView();
  const viewport = $("agentPiTimelineViewport");
  const timeline = $("agentPiTimeline");
  if (!view || !agentConsoleShowsPiTimeline(view)) {
    agentPiTimelineView.clear(timeline);
    $("agentPiTimelineEmpty").hidden = false;
    $("agentPiTimelineJumpLatest").hidden = true;
    return;
  }
  const items = view.timeline?.items || [];
  const visibleItems = view.toolPreview
    ? [...items, {kind:"toolCall", key:"engine-tool-preview", ...view.toolPreview}]
    : items;
  const followTail = !preserveScroll || view.piFollowTail !== false;
  agentPiTimelineView.render(timeline, visibleItems, {
    viewport, surfaceId:state.agentConsoleSurfaceId, preserveScroll, followTail, protocol:view.meta?.protocol,
  });
  $("agentPiTimelineEmpty").hidden = items.length > 0;
  if (followTail) {
    view.piFollowTail = true;
    view.piNewOutput = false;
  }
  view.piLastScrollTop = viewport.scrollTop;
  scheduleAgentPiTimelineFollow();
}

function setAgentConsoleSearch(open) {
  state.agentConsoleSearchOpen = Boolean(open);
  state.agentConsoleSearchIndex = -1;
  $("agentConsoleFindButton").setAttribute("aria-expanded", String(state.agentConsoleSearchOpen));
  $("agentConsoleSearch").classList.toggle("hidden", !state.agentConsoleSearchOpen);
  renderAgentTerminalOutput({focusMatch:state.agentConsoleSearchOpen});
  renderAgentConsoleTabs();
  if (state.agentConsoleSearchOpen) requestAnimationFrame(() => $("agentConsoleSearchInput").focus());
  else requestAnimationFrame(() => $("agentTerminalViewport").focus());
}

function moveAgentConsoleSearch(direction) {
  const view = currentAgentConsoleView();
  if (!view) return;
  const matches = AgentConsoleTabsCore.findMatches(view.renderedText, state.agentConsoleSearchQuery);
  state.agentConsoleSearchIndex = AgentConsoleTabsCore.nextMatchIndex(
    state.agentConsoleSearchIndex, matches.ranges.length, direction,
  );
  renderAgentTerminalOutput({focusMatch:true});
}

async function copyAgentConsoleVisible() {
  const view = currentAgentConsoleView();
  const visibleText = agentConsoleShowsPiTimeline(view)
    ? PiTimelineCore.timelinePlainText(view?.timeline, view?.meta?.protocol) : view?.renderedText;
  if (!visibleText || state.agentConsoleCopyBusy) return;
  state.agentConsoleCopyBusy = true;
  renderAgentConsoleTabs();
  try {
    await copyText(visibleText);
    showNotice(agentConsoleShowsPiTimeline(view)
      ? `Copied the visible ${AgentConsoleInputCore.agentLabel(view?.meta?.protocol)} conversation timeline.`
      : "Copied the bounded visible Agent Console text.");
  } catch (error) {
    showNotice(`Could not copy the Agent Console: ${error.message}`, true);
  } finally {
    state.agentConsoleCopyBusy = false;
    renderAgentConsoleTabs();
  }
}

function currentAgentConsoleInteraction(meta = currentAgentConsoleView()?.meta || {}) {
  const interactions = Array.isArray(meta?.interactions) ? meta.interactions : [];
  return interactions.find(item => item && typeof item === "object" && item.id) || null;
}

function renderAgentConsoleInteraction(meta, canInput) {
  renderAgentConsoleCommands(meta);
  const panel = $("agentConsoleInteraction");
  const interactions = Array.isArray(meta?.interactions) ? meta.interactions : [];
  const interaction = currentAgentConsoleInteraction(meta);
  if (!interaction || !AgentConsoleInputCore.isStructuredProtocol(meta.protocol)) {
    panel.hidden = true;
    panel.dataset.requestId = "";
    panel.dataset.custom = "false";
    return;
  }
  const method = String(interaction.method || "");
  const custom = interaction.title === "__launcher_custom_ui__";
  const changed = panel.dataset.requestId !== interaction.id;
  const openingCustom = custom && panel.dataset.custom !== "true";
  panel.dataset.custom = String(custom);
  panel.hidden = false;
  panel.dataset.requestId = interaction.id;
  panel.dataset.method = method;
  if (changed) {
    $("agentConsoleInteractionTitle").textContent = custom ? `${AgentConsoleInputCore.agentLabel(meta.protocol)} extension menu` : interaction.title || `${AgentConsoleInputCore.agentLabel(meta.protocol)} needs input`;
    const detail = method === "confirm" ? String(interaction.message || "") : "";
    $("agentConsoleInteractionMessage").textContent = [
      detail,
      interactions.length > 1 ? `${interactions.length - 1} more request${interactions.length === 2 ? "" : "s"} waiting.` : "",
    ].filter(Boolean).join(" ");
    const options = Array.isArray(interaction.options) ? interaction.options : [];
    $("agentConsoleInteractionOptions").innerHTML = options.map((option, index) =>
      `<button type="button" class="secondary compact" data-agent-console-option="${esc(option)}" title="${esc(option)}">${esc(option || `Option ${index + 1}`)}</button>`
    ).join("");
    $("agentConsoleInteractionInput").value = method === "editor" ? String(interaction.prefill || "") : "";
    $("agentConsoleInteractionInput").placeholder = method === "input"
      ? String(interaction.placeholder || "Enter a response…") : "Enter a response…";
  }
  const optionsVisible = method === "select";
  const inputVisible = !custom && (method === "input" || method === "editor");
  const confirmVisible = method === "confirm";
  $("agentConsoleInteractionOptions").hidden = !optionsVisible;
  $("agentConsoleInteractionInputWrap").hidden = !inputVisible;
  $("agentConsoleInteractionNo").hidden = !confirmVisible;
  $("agentConsoleInteractionSubmit").hidden = optionsVisible || custom;
  $("agentConsoleCustomUI").hidden = !custom;
  if (custom) {
    $("agentConsoleCustomFrame").textContent = meta.extensionStatuses?.["launcher.customUI"]?.text || "Opening menu…";
    if (openingCustom) $("agentConsoleCustomFrame").focus({preventScroll:true});
  }
  $("agentConsoleInteractionSubmit").querySelector("strong").textContent = confirmVisible ? "Yes" : "Continue";
  for (const button of panel.querySelectorAll("button")) button.disabled = !canInput || state.agentConsoleBusy;
  $("agentConsoleInteractionInput").disabled = !canInput || state.agentConsoleBusy;
}

function renderAgentConsoleCommands(meta = currentAgentConsoleView()?.meta || {}) {
  const panel = $("agentConsoleCommands");
  const input = $("agentConsoleInput");
  const query = input.value.trim();
  const visible = AgentConsoleInputCore.isStructuredProtocol(meta.protocol) && /^\/[\w:-]*$/.test(query);
  UiPresenter.property(panel, "hidden", !visible);
  if (!visible) return;
  const commands = (Array.isArray(meta.commands) ? meta.commands : [])
    .filter(c => c.name && c.name.toLowerCase().startsWith(query.slice(1).toLowerCase()))
    .sort((a, b) => a.name.localeCompare(b.name)).slice(0, 40);
  const markup = commands.length ? commands.map(c => `<button type="button" data-pi-command="${esc(c.name)}"><strong>/${esc(c.name)}</strong><span>${esc(c.description || c.source || "")}</span></button>`).join("")
    : "<p>No matching commands available in this session.</p>";
  if (panel.dataset.commandMarkup !== markup) {
    panel.innerHTML = markup;
    panel.dataset.commandMarkup = markup;
  }
}

const piMenuKeys = {up:"\x1b[A", down:"\x1b[B", right:"\x1b[C", left:"\x1b[D", enter:"\r"};

async function respondAgentConsoleInteraction(response) {
  const view = currentAgentConsoleView();
  const interaction = currentAgentConsoleInteraction(view?.meta);
  if (!view || !interaction || state.agentConsoleBusy) return;
  state.agentConsoleBusy = true;
  renderAgentConsole();
  try {
    const data = await api("/api/agent-console/input", {
      method:"POST",
      body:JSON.stringify({
        ownerRunId:state.agentConsoleOwnerRunId,
        surfaceId:state.agentConsoleSurfaceId,
        command:"extension_response",
        requestId:interaction.id,
        ...response,
      }),
    });
    if (state.agentConsoleViews[state.agentConsoleSurfaceId] === view) {
      reconcileAgentConsoleViewMeta(view, data.console);
      state.agentConsoleMeta = view.meta;
    }
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    state.agentConsoleBusy = false;
    renderAgentConsole();
    scheduleAgentConsoleRead(0);
  }
}

function renderAgentPrefillClock() {
  const clock = $("agentConsolePrefillClock");
  const value = state.agentConsoleVisible
    ? ChatStatusCore.promptProcessingClock(agentConsoleRequestActivity().current) : null;
  UiPresenter.property(clock, "hidden", value === null);
  UiPresenter.property(clock, "textContent", value === null ? "" : `◷ ${value}`);
  UiPresenter.property(clock, "title", "Time preparing this prompt, including cache restoration. Resets for each model request.");
}

function renderAgentConsoleQueue(meta, view, enabled, count) {
  const panel = $("agentConsoleQueue");
  const entries = enabled ? AgentConsoleInputCore.piQueueEntries(meta, view?.inputQueue, view?.inputInFlightItems) : [];
  const visible = enabled && (count > 0 || entries.length > 0 || meta.queueSaveError || view?.queueEdit);
  if (panel.hidden && visible) panel.open = true;
  panel.hidden = !visible;
  if (!visible) return;
  $("agentConsoleQueueSummary").textContent = `${Math.max(count, entries.length)} ${meta.queuePaused ? "paused" : "queued"} message${Math.max(count, entries.length) === 1 ? "" : "s"}`;
  const list = $("agentConsoleQueueMessages");
  const signature = JSON.stringify([state.agentConsoleSurfaceId, entries]);
  if (list.dataset.contents !== signature) {
    list.replaceChildren(...entries.map(item => {
      const row = document.createElement("li");
      const label = document.createElement("small");
      label.textContent = item.label;
      const message = document.createElement("pre");
      message.textContent = item.message;
      const actions = document.createElement("div");
      actions.className = "agent-console-queue-actions";
      if (item.editable) {
        for (const action of ["Edit", "Delete"]) {
          const button = document.createElement("button");
          button.type = "button";
          button.textContent = action;
          button.setAttribute("aria-label", `${action} queued message`);
          button.addEventListener("click", () => {
            if (action === "Delete") void changeAgentConsoleQueuedMessage(view, item, "delete");
            else {
              view.queueEdit = {item, text:item.message};
              renderAgentConsole();
              $("agentConsoleQueueEditText").focus();
            }
          });
          actions.append(button);
        }
      } else {
        actions.textContent = meta.queueEditingAvailable
          ? `Already sending to ${AgentConsoleInputCore.agentLabel(meta.protocol)}` : "Controls available after launcher restart";
      }
      row.append(label, actions, message);
      return row;
    }));
    list.dataset.contents = signature;
  }
  list.querySelectorAll("button").forEach(button => { button.disabled = Boolean(view?.queueMutationBusy); });
  const editor = $("agentConsoleQueueEditor");
  editor.hidden = !view?.queueEdit;
  if (view?.queueEdit && $("agentConsoleQueueEditText").value !== view.queueEdit.text) {
    $("agentConsoleQueueEditText").value = view.queueEdit.text;
  }
  $("agentConsoleQueueSave").disabled = Boolean(view?.queueMutationBusy);
  $("agentConsoleQueueCancel").disabled = Boolean(view?.queueMutationBusy);
  const warning = $("agentConsoleQueueWarning");
  warning.textContent = meta.queueSaveError || (count > entries.length
    ? "The older controller reports more queued messages but does not expose their text. Keep it open to retain them."
    : meta.queuePaused ? "Paused. Edit or delete messages here, or send a message to continue." : "");
  warning.hidden = !warning.textContent;
}

async function changeAgentConsoleQueuedMessage(view, item, action, message) {
  if (view !== currentAgentConsoleView() || view.queueMutationBusy) return;
  if (action === "edit") {
    const validation = AgentConsoleInputCore.validatePiPrompt(message, AgentConsoleInputCore.agentLabel(view?.meta?.protocol));
    if (!validation.ok) { showNotice(validation.error, true); return; }
  }
  const surfaceId = state.agentConsoleSurfaceId;
  const ownerRunId = state.agentConsoleOwnerRunId;
  view.queueMutationBusy = true;
  renderAgentConsole();
  try {
    if (item.source === "local") {
      const index = view.inputQueue.indexOf(item.localItem);
      if (index < 0) throw new Error("That message is already being sent. Wait for the queue to update.");
      if (action === "delete") view.inputQueue.splice(index, 1);
      else item.localItem.message = message;
      if (!view.inputQueue.length) { view.inputRetryPending = false; view.inputError = ""; }
    } else {
      const data = await api("/api/agent-console/input", {method:"POST", body:JSON.stringify({
        ownerRunId, surfaceId, command:action === "edit" ? "edit_queued_message" : "delete_queued_message",
        queueId:item.id, ...(action === "edit" ? {message} : {}),
      })});
      reconcileAgentConsoleViewMeta(view, data.console);
    }
    if (action === "edit" || view.queueEdit?.item === item) view.queueEdit = null;
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    view.queueMutationBusy = false;
    renderAgentConsole();
    scheduleAgentConsoleRead(0);
  }
}

let hubFanBusy = false;
let hubFanCheckedAt = 0;
let hubFanRunId = "";
let hubFanMode = "unknown";
async function updateHubFans(mode) {
  const runId = state.agentConsoleOwnerRunId;
  if (disposed || hubFanBusy || !runId) return;
  hubFanBusy = true;
  hubFanCheckedAt = Date.now();
  const changedRun = hubFanRunId !== runId;
  hubFanRunId = runId;
  const select = $("hubFanMode");
  const message = $("hubFanMessage");
  if (changedRun) {
    hubFanMode = "unknown";
    select.value = hubFanMode;
    select.querySelector('[value="smart"]').hidden = state.runStatus?.run?.backend !== "mtplx";
  }
  message.title = "";
  select.disabled = true;
  message.textContent = mode ? "Changing…" : "";
  try {
    const result = await api("/api/hub/fans", {method:"POST", body:JSON.stringify({runId, ...(mode ? {mode} : {})})});
    if (runId !== state.agentConsoleOwnerRunId) return;
    hubFanMode = result.mode || "unknown";
    select.value = hubFanMode;
    select.querySelector('[value="smart"]').hidden = !result.smartAvailable;
    message.textContent = "";
    select.title = "Changes cooling immediately. System restores macOS control.";
  } catch (error) {
    if (runId !== state.agentConsoleOwnerRunId) return;
    // A failed verification can follow a partial physical change. Do not
    // present the previous setting as a confirmed current fan mode.
    hubFanMode = "unknown";
    select.value = hubFanMode;
    message.textContent = mode ? "Change not verified" : "Fan control unavailable";
    message.title = error.message;
    select.title = error.message;
    if (mode) alertUser(error.message);
  } finally {
    hubFanBusy = false;
    select.disabled = false;
  }
}

function renderAgentConsole() {
  if (disposed) return;
  restoreAgentConsoleDraft();
  UiPresenter.property($("agentConsoleDraftsButton"), "hidden", !recoverableAgentConsoleDrafts().length);
  if (state.agentConsoleVisible && (hubFanRunId !== state.agentConsoleOwnerRunId || Date.now() - hubFanCheckedAt > 30000)) void updateHubFans();
  const view = currentAgentConsoleView();
  const attachment = currentAgentConsoleAttachment() || view?.meta || state.agentConsoleMeta || {};
  const record = currentAgentConsoleRecord();
  if (view) {
    reconcileAgentConsoleViewMeta(view, attachment);
    if (record) reconcileAgentConsoleViewMeta(view, record);
    if (view.postmortem) {
      view.meta = {
        ...view.meta,
        state:view.postmortem.state,
        status:view.postmortem.state,
        detail:view.postmortem.detail,
        streaming:false,
        canInput:false,
        canStop:false,
        canRestart:false,
      };
    }
    state.agentConsoleMeta = view.meta;
  }
  const meta = view?.meta || attachment;
  const postmortem = view?.postmortem || null;
  const structuredPi = AgentConsoleInputCore.isStructuredProtocol(meta.protocol);
  const agentLabel = AgentConsoleInputCore.agentLabel(meta.protocol);
  const showPiTimeline = agentConsoleShowsPiTimeline(view);
  const piInteraction = structuredPi ? currentAgentConsoleInteraction(meta) : null;
  const runtimeAdvisory = meta.runtimeAdvisory || state.runStatus?.run?.runtimeAdvisory || null;
  const surface = meta.surface || clientName(meta.client) || "Agent";
  const stateLabel = String(meta.state || meta.status || "starting");
  UiPresenter.property($("agentConsoleTitle"), "textContent", `${surface} · Hub Console`);
  UiPresenter.property($("agentConsoleHeadingDetail"), "textContent", meta.model || "");
  UiPresenter.property($("agentConsoleHeadingDetail"), "title", `${meta.model || ""} · ${stateLabel}`);
  UiPresenter.property($("agentConsoleMeta"), "textContent", postmortem
    ? `${meta.project || "Current project"} · bounded postmortem output retained in this launcher until another surface replaces it.`
    : showPiTimeline
    ? `${meta.project || "Current project"} · stable ${agentLabel} transcript with separate thinking, responses, tools, and follow-up queue; session output remains memory-only in the launcher.`
    : structuredPi
      ? view?.loaded
        ? `${meta.project || "Current project"} · this running ${agentLabel} session predates semantic timeline support, so its bounded terminal view remains available.`
        : `${meta.project || "Current project"} · checking ${agentLabel} timeline support; the bounded terminal view remains available meanwhile.`
    : meta.project
      ? `${meta.project} · agent-supplied terminal styling is preserved; output is bounded in memory and never saved by the launcher.`
      : "Agent-supplied terminal styling is preserved; output stays in bounded session memory and never enters Chat history.");
  UiPresenter.property($("agentConsoleRoute"), "textContent", meta.backend
    ? `${backendName(meta.backend)} → ${surface} · ${meta.model || "Local model"}`
    : "Waiting for the active model");
  UiPresenter.property($("agentConsoleStatusSurface"), "textContent", meta.backend
    ? `${surface} · ${backendName(meta.backend)}` : surface);
  UiPresenter.property($("agentConsoleStatusModel"), "textContent", [
    meta.model || "Waiting for the active model",
    meta.project ? agentConsoleProjectName(meta.project) : "Project unavailable",
  ].join(" · "));

  const activity = agentConsoleRequestActivity();
  const activelyResponding = Boolean(!postmortem && (activity.current || meta.streaming));
  const abortBusy = Boolean(structuredPi && view?.abortBusy);
  const pendingMessages = structuredPi ? AgentConsoleInputCore.visiblePiPendingMessages(
    meta.pendingMessages,
    view?.inputQueue,
    view?.inputInFlightPromptCount,
  ) : Math.max(0, Number(meta.pendingMessages) || 0);
  const piQueuePaused = structuredPi && meta.queuePaused === true;
  renderAgentConsoleQueue(meta, view, structuredPi, pendingMessages);
  const inputRetryPending = Boolean(view?.inputRetryPending && view.inputQueue.length);
  const compactActivity = ChatStatusCore.activitySummary(activity.report, state.agentConsoleSurfaceId);
  const piSpeed = structuredPi ? PiTimelineCore.piTokenSpeed(meta) : null;
  compactActivity.speed = ChatStatusCore.agentGenerationSpeed(
    activity.current, activity.latest, piSpeed, compactActivity.speed,
  );
  UiPresenter.property($("agentConsoleTps"), "textContent", compactActivity.speed.value);
  UiPresenter.property($("agentConsoleTps"), "title", compactActivity.speed.title);
  const firstOutput = activity.current ? activity.current.firstOutputSeconds : activity.latest?.firstOutputSeconds;
  UiPresenter.property($("agentConsoleTtft"), "textContent", firstOutput !== null && firstOutput !== undefined
    ? formatShortDuration(firstOutput) : activity.current ? "Waiting…" : "—");
  const livePhase = liveRequestPhaseLabel(activity.current);
  const relayTone = renderAgentActivity(activity, meta, view, postmortem);
  UiPresenter.property($("agentConsoleLane"), "textContent", activity.current?.state === "queued"
    ? `Queue #${formatNumber(activity.current.queuePosition || 1)}`
    : activity.current?.state === "running" ? `${livePhase || "Generating"} · ${formatShortDuration(activity.current.runSeconds || 0)}`
      : meta.streaming ? "Working · tools / agent"
      : activity.report.engineResident ? `${formatNumber(activity.report.lanes || 1)} lane${Number(activity.report.lanes || 1) === 1 ? "" : "s"} · idle` : "Relay unavailable");

  const promptSignal = ChatStatusCore.promptProcessingSummary(activity.current, activity.latest);
  renderAgentPrefillClock();
  const contextSignal = ChatStatusCore.agentContextSummary(meta, state.runStatus?.run?.context,
    activity.current, activity.latest);
  const contextTokens = $("agentConsoleContextTokens");
  UiPresenter.property(contextTokens, "hidden", contextSignal.usedTokens === undefined);
  UiPresenter.property(contextTokens, "textContent", contextTokens.hidden ? "" : `${formatNumber(contextSignal.usedTokens)} / ${formatNumber(contextSignal.totalTokens)} · ${formatNumber(contextSignal.remainingTokens)} left`);
  UiPresenter.property(contextTokens, "title", `${contextTokens.textContent} tokens. ${contextSignal.title}`);
  for (const [name, signal] of [["Prompt", promptSignal], ["Context", contextSignal]]) {
    UiPresenter.signal($(`agentConsoleStatus${name}`), $(`agentConsoleStatus${name}Value`), signal);
  }
  const speedSignal = $("agentConsoleStatusSpeed");
  const laneSignal = $("agentConsoleStatusLane");
  UiPresenter.signal(speedSignal, $("agentConsoleStatusSpeedValue"), compactActivity.speed);
  UiPresenter.property($("agentConsoleStatusLaneValue"), "textContent", meta.compacting ? "Compacting…"
    : relayTone === "quiet" ? "Stream quiet" : livePhase || compactActivity.lane.value);
  UiPresenter.data(laneSignal, "state", relayTone === "quiet" ? "busy" : compactActivity.lane.state);
  UiPresenter.property(laneSignal, "title", [$("agentConsoleLane").textContent, liveRequestDetail(activity.current)].filter(Boolean).join(". "));
  const processLabels = {
    starting:"Starting", stopping:"Stopping", failed:"Failed",
    exited:"Exited", stopped:"Stopped",
  };
  const processLabel = processLabels[stateLabel] || "";
  UiPresenter.property($("agentConsoleStatusState"), "textContent", processLabel);
  UiPresenter.property($("agentConsoleStatusState"), "hidden", !processLabel);
  UiPresenter.data($("agentConsoleStatusPanel"), "activityState", compactActivity.lane.state);
  UiPresenter.data($("agentConsoleStatusPanel"), "processState", stateLabel);
  updateAgentConsoleStatusSummaryLabel();

  const canInput = Boolean(!postmortem && (meta.canInput ?? stateLabel === "running"));
  UiPresenter.property($("agentTerminalViewport"), "hidden", showPiTimeline);
  UiPresenter.property($("agentPiTimelineViewport"), "hidden", !showPiTimeline);
  UiPresenter.attribute($("agentPiTimelineViewport"), "aria-busy", String(showPiTimeline && activelyResponding));
  if (showPiTimeline && state.agentConsoleSearchOpen) {
    state.agentConsoleSearchOpen = false;
    state.agentConsoleSearchIndex = -1;
    $("agentConsoleSearch").classList.add("hidden");
    $("agentConsoleFindButton").setAttribute("aria-expanded", "false");
  }
  renderAgentConsoleInteraction(meta, canInput);
  UiPresenter.property($("agentConsoleInput"), "disabled", !canInput || state.agentConsoleBusy);
  UiPresenter.property($("agentConsoleCompactButton"), "hidden", !structuredPi);
  UiPresenter.property($("agentConsoleCompactButton"), "disabled", !canInput || activelyResponding || meta.compacting || state.agentConsoleBusy);
  UiPresenter.property($("agentConsoleEnterButton"), "disabled", !canInput || state.agentConsoleBusy || meta.compacting);
  UiPresenter.property($("agentConsoleSteerButton"), "hidden", !structuredPi || !activelyResponding);
  UiPresenter.property($("agentConsoleSteerButton"), "disabled", !canInput || state.agentConsoleBusy || meta.compacting || view?.steerBusy || meta.supportsSteering !== true);
  UiPresenter.property($("agentConsoleSteerButton"), "title", meta.supportsSteering === true
    ? `Deliver instructions before ${agentLabel}’s next model step, instead of waiting for the task to finish`
    : "Restart the launcher after the current task to enable steering.");
  UiPresenter.property($("agentConsoleSteerButton"), "textContent", view?.steerBusy ? "Steering…" : "Steer");
  UiPresenter.property($("agentConsoleStopButton"), "disabled", state.agentConsoleBusy || !(meta.canStop ?? ["starting","running","stopping"].includes(stateLabel)));
  UiPresenter.property($("agentConsoleRestartButton"), "disabled", state.agentConsoleBusy || !(meta.canRestart ?? ["exited","stopped","failed"].includes(stateLabel)));
  UiPresenter.property($("agentConsoleInputLabel"), "textContent", `Message ${surface}`);
  UiPresenter.property($("agentConsoleInput"), "placeholder", structuredPi && activelyResponding
    ? "Steer this task, or queue a follow-up…" : `Ask ${surface}…`);
  UiPresenter.property($("agentConsoleEnterButton").querySelector("strong"), "textContent", inputRetryPending
    ? "Retry send" : structuredPi && activelyResponding ? "Queue" : "Send");
  UiPresenter.property($("agentConsoleEscapeButton"), "textContent", structuredPi ? "Clear queue" : "Esc");
  UiPresenter.property($("agentConsoleEscapeButton"), "title", structuredPi
    ? `Remove queued ${agentLabel} follow-up messages` : "Send the Escape key");
  UiPresenter.property($("agentConsoleEscapeButton"), "disabled", !canInput || state.agentConsoleBusy || (structuredPi && pendingMessages < 1));
  UiPresenter.property($("agentConsoleEscapeButton"), "hidden", structuredPi && pendingMessages < 1);
  UiPresenter.property($("agentConsoleInterruptButton"), "hidden", structuredPi && !activelyResponding);
  UiPresenter.property($("agentConsoleInterruptButton"), "textContent", abortBusy
    ? "Stopping…" : structuredPi ? "Stop response" : "Ctrl-C");
  UiPresenter.property($("agentConsoleInterruptButton"), "title", structuredPi
    ? abortBusy ? `Waiting for ${agentLabel} to stop the current response` : `Abort ${agentLabel}'s current response`
    : "Interrupt the current agent action");
  UiPresenter.property($("agentConsoleInterruptButton"), "disabled", !canInput || state.agentConsoleBusy
    || (structuredPi && (!activelyResponding || abortBusy)));
  UiPresenter.attribute($("agentTerminalViewport"), "role", "application");
  UiPresenter.attribute($("agentTerminalViewport"),
    "aria-label",
    "Interactive agent terminal. Type to send keys; use the text field below for accessible input.",
  );
  const dropped = Number(meta.droppedBytes || 0);
  const interactionDetail = structuredPi
    ? abortBusy
      ? `Stopping ${agentLabel}'s current response…`
      : piInteraction
      ? piInteraction.title === "__launcher_custom_ui__"
        ? `${agentLabel} menu open. Use the arrow keys, Enter, or Cancel.`
        : `${agentLabel} is waiting for your answer to “${piInteraction.title || "an extension request"}”.`
      : piQueuePaused
      ? `${pendingMessages} message${pendingMessages === 1 ? " is" : "s are"} paused. Send to continue, or clear the queue in •••.`
      : pendingMessages
      ? `${pendingMessages} message${pendingMessages === 1 ? " is" : "s are"} queued.`
      : ""
    : "";
  UiPresenter.property($("agentConsoleStatus"), "textContent", postmortem?.detail || view?.inputError
    || `${view?.recovering ? "Restoring the latest console screen… " : ""}${interactionDetail || meta.detail || `Hub Console is ${stateLabel}.`}${runtimeAdvisory?.detail ? ` ${runtimeAdvisory.detail}` : ""}${dropped ? ` Earlier output was discarded after the 2 MB memory cap (${formatBytes(dropped)} dropped).` : ""}`);
  UiPresenter.property($("agentConsoleStatus"), "className", postmortem?.state === "failed" || view?.inputError || stateLabel === "failed"
    ? "error" : runtimeAdvisory || piInteraction || piQueuePaused ? "warning" : "");
  UiPresenter.property($("agentConsoleStatus"), "hidden", Boolean(structuredPi && canInput && !interactionDetail
    && !postmortem && !view?.inputError && !view?.recovering && !runtimeAdvisory && !dropped));
  renderAgentConsoleTabs();
}

function updateAgentWorkspace(run, phase) {
  const routeActive = sessionRouteActive(run, phase);
  if (routeActive) syncAgentConsoleViews(state.runStatus, run, phase);
  else if (state.agentConsoleOwnerRunId) {
    retainAgentConsoleViews(phase, state.runStatus?.message);
  }
  const view = currentAgentConsoleView();
  const selected = view?.meta || state.agentConsoleMeta;
  const retained = Boolean(view?.postmortem && selected);
  const visible = Boolean(state.agentConsoleVisible && selected && (routeActive || retained));
  agentPiTimelineView.setVisible($("agentPiTimeline"), visible && agentConsoleShowsPiTimeline(view));
  $("agentWorkspace").classList.toggle("hidden", !visible);
  const chatVisible = navigation.setConsoleVisible(visible);
  navigation.updateChrome();
  if (visible) {
    navigation.setSubtitle( `${selected.surface || clientName(selected.client)} · ${selected.model || run?.model || "Local model"}`);
    renderAgentConsole();
    if (agentConsoleShowsPiTimeline(view)) {
      if ($("agentPiTimeline").dataset.consoleSurface !== state.agentConsoleSurfaceId) {
        renderAgentPiTimeline({preserveScroll:false});
      }
    } else if ($("agentTerminalOutput").dataset.consoleSurface !== state.agentConsoleSurfaceId) {
      renderAgentTerminalOutput({preserveScroll:false});
    }
    if (!retained) scheduleAgentConsoleRead(0, {wake:false});
  } else if (!chatVisible) {
    navigation.showSettings();
  }
}

function scheduleAgentConsoleRead(delay = 120, {wake = delay === 0} = {}) {
  if (
    disposed || state.agentConsoleBusy || !state.agentConsoleVisible || !state.agentConsoleOwnerRunId
    || !currentAgentConsoleView() || currentAgentConsoleView().postmortem
  ) return;
  if (wake) {
    currentAgentConsoleView().readIdleCount = 0;
    if (state.agentConsoleTimer !== null) clearTimeout(state.agentConsoleTimer);
    state.agentConsoleTimer = null;
  }
  if (state.agentConsoleTimer !== null || state.agentConsoleReading) return;
  state.agentConsoleTimer = setTimeout(() => {
    state.agentConsoleTimer = null;
    void readAgentConsole();
  }, Math.max(document.hidden ? 1500 : 0, Number(delay) || 0));
}

function invalidateAgentConsoleRead() {
  if (state.agentConsoleTimer !== null) clearTimeout(state.agentConsoleTimer);
  state.agentConsoleTimer = null;
  state.agentConsoleReadGeneration += 1;
  state.agentConsoleReading = false;
}

function decodeAgentConsoleChunk(view, value) {
  if (!value) return "";
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return view.decoder.decode(bytes, {stream:true});
}

async function readAgentConsole() {
  if (disposed || state.agentConsoleReading || !state.agentConsoleVisible) return;
  const ownerRunId = state.agentConsoleOwnerRunId;
  const surfaceId = state.agentConsoleSurfaceId;
  const requestedView = state.agentConsoleViews[surfaceId];
  if (!requestedView || requestedView.postmortem) return;
  const readGeneration = state.agentConsoleReadGeneration;
  state.agentConsoleReading = true;
  let nextDelay = null;
  try {
    const readRequest = {ownerRunId, surfaceId, offset:requestedView.offset};
    if (agentConsoleUsesStructuredPi(requestedView)) {
      readRequest.timelineRevision = PiTimelineCore.safeRevision(requestedView.timeline?.revision);
      readRequest.timelineVersion = PiTimelineCore.VERSION;
    }
    const data = await api("/api/agent-console/read", {
      method:"POST", body:JSON.stringify(readRequest),
    });
    if (readGeneration !== state.agentConsoleReadGeneration) return;
    const view = state.agentConsoleViews[surfaceId];
    if (!view || ownerRunId !== state.agentConsoleOwnerRunId) return;
    const output = data.console;
    const reconciliation = reconcileAgentConsoleViewMeta(view, output);
    if (reconciliation.stale) {
      nextDelay = 0;
      return;
    }
    if (reconciliation.generationChanged) {
      resetAgentPiTimeline(view, {renderPlaceholder:false});
    }
    const timelineWasLoaded = view.timelineLoaded === true;
    const timelineResult = agentConsoleUsesStructuredPi(view)
      ? PiTimelineCore.applyTimelineEnvelope(view.timeline, output) : null;
    const preview = output.streaming && !output.compacting ? output.toolPreview || null : null;
    const previewChanged = JSON.stringify(view.toolPreview || null) !== JSON.stringify(preview);
    view.toolPreview = preview;
    const timelineNeedsRender = previewChanged || PiTimelineCore.shouldRenderTimeline(
      timelineWasLoaded, timelineResult,
    );
    if (timelineResult?.supported) {
      view.timeline = timelineResult.state;
      view.timelineLoaded = true;
      if (timelineNeedsRender && view.piFollowTail === false) view.piNewOutput = true;
    }
    const suppressTerminal = timelineResult?.supported === true;
    const replayTerminal = !suppressTerminal && view.terminalSuppressed === true;
    if (suppressTerminal) {
      if (!view.terminalSuppressed) {
        // Discard the hidden emulator's scrollback once the semantic view is
        // confirmed. Its independent revision cursor owns Pi history now.
        resetAgentConsoleTerminal(view, output.baseOffset, {renderPlaceholder:false, clearInput:false});
        if (surfaceId === state.agentConsoleSurfaceId) $("agentTerminalOutput").textContent = "";
      }
      view.terminalSuppressed = true;
      view.offset = agentConsoleBufferEnd(output);
    } else {
      if (replayTerminal || reconciliation.generationChanged || output.reset) {
        resetAgentConsoleTerminal(view, output.baseOffset, {renderPlaceholder:false, clearInput:false});
      }
      if (replayTerminal) {
        // The server no longer supports our timeline version. Request the
        // retained raw buffer from its base rather than render a partial tail.
        resetAgentPiTimeline(view, {renderPlaceholder:false});
      } else {
        const decoded = decodeAgentConsoleChunk(view, output.data);
        if (decoded) view.terminal.write(decoded);
        view.offset = AgentConsoleTabsCore.safeOffset(output.nextOffset ?? view.offset);
      }
    }
    view.loaded = !replayTerminal;
    view.recovering = false;
    if (view.postmortem) {
      view.meta = {
        ...view.meta,
        state:view.postmortem.state,
        status:view.postmortem.state,
        detail:view.postmortem.detail,
        streaming:false,
        canInput:false,
        canStop:false,
        canRestart:false,
      };
    }
    const stillActive = surfaceId === state.agentConsoleSurfaceId && state.agentConsoleVisible;
    if (stillActive) {
      view.seenEnd = Math.max(view.seenEnd, view.offset);
      view.timelineSeenRevision = Math.max(
        view.timelineSeenRevision,
        PiTimelineCore.safeRevision(view.timeline?.revision),
      );
      state.agentConsoleMeta = view.meta;
      if (agentConsoleShowsPiTimeline(view)) {
        if (timelineNeedsRender) renderAgentPiTimeline();
      } else renderAgentTerminalOutput();
      renderAgentConsole();
      const readPlan = AgentConsoleTabsCore.nextReadPlan({
        backlog:replayTerminal || agentConsoleBufferEnd(output) > view.offset
          || (timelineResult?.supported && !timelineResult.stale
            && PiTimelineCore.safeRevision(view.timeline.availableRevision)
              > PiTimelineCore.safeRevision(view.timeline.revision)),
        state:output.state || view.meta?.state || view.meta?.status,
        streaming:output.streaming === true || view.meta?.streaming === true,
        compacting:output.compacting === true || view.meta?.compacting === true,
        abortBusy:view.abortBusy,
        idleConfirmed:timelineResult?.supported === true && output.streaming === false
          && output.compacting === false,
        idleReads:view.readIdleCount,
        outputChanged:timelineNeedsRender || Boolean(output.data) || reconciliation.generationChanged,
        serverPending:output.pendingMessages ?? view.meta?.pendingMessages,
        localPending:view.inputQueue.length,
        inputSending:view.inputSending,
        drainRemaining:view.readDrainRemaining,
      });
      view.readDrainRemaining = readPlan.drainRemaining;
      view.readIdleCount = readPlan.idleReads || 0;
      nextDelay = readPlan.delay;
    }
    persistAgentConsoleRecovery();
  } catch (error) {
    if (readGeneration !== state.agentConsoleReadGeneration) return;
    const stillActive = ownerRunId === state.agentConsoleOwnerRunId && surfaceId === state.agentConsoleSurfaceId;
    if (stillActive && ["preflight","starting"].includes(state.runPhase)) nextDelay = 500;
    else if (stillActive) {
      $("agentConsoleStatus").textContent = error.message;
      $("agentConsoleStatus").className = "error";
      nextDelay = 1000;
    }
  } finally {
    if (readGeneration === state.agentConsoleReadGeneration) {
      state.agentConsoleReading = false;
      if (state.agentConsoleVisible && nextDelay !== null && !currentAgentConsoleView()?.postmortem) scheduleAgentConsoleRead(nextDelay);
      else if (state.agentConsoleVisible && surfaceId !== state.agentConsoleSurfaceId && !currentAgentConsoleView()?.postmortem) scheduleAgentConsoleRead(0);
    }
  }
}

function queueAgentConsoleInput(value) {
  const view = currentAgentConsoleView();
  if (!value || !view || !state.agentConsoleOwnerRunId || !state.agentConsoleSurfaceId) return;
  view.inputQueue.push(typeof value === "object" ? {...value} : String(value));
  view.readDrainRemaining = AgentConsoleTabsCore.FINAL_DRAIN_READS;
  renderAgentConsole();
  void flushAgentConsoleInput(view, state.agentConsoleOwnerRunId, state.agentConsoleSurfaceId);
}

function clearAgentConsolePendingMessages() {
  const view = currentAgentConsoleView();
  if (!view) return;
  if (!agentConsoleUsesStructuredPi(view)) {
    queueAgentConsoleInput("\u001b");
    return;
  }
  AgentConsoleInputCore.discardQueuedPiPrompts(view.inputQueue);
  queueAgentConsoleInput({command:"clear_queue"});
}

function agentConsoleUsesStructuredPi(view = currentAgentConsoleView()) {
  return AgentConsoleInputCore.isStructuredProtocol(view?.meta?.protocol);
}

function agentConsoleShowsPiTimeline(view = currentAgentConsoleView()) {
  return PiTimelineCore.shouldUseTimeline(view?.meta?.protocol, view?.timelineLoaded);
}

function validateAgentConsolePrompt(value, view = currentAgentConsoleView()) {
  const label = AgentConsoleInputCore.agentLabel(view?.meta?.protocol);
  const validation = AgentConsoleInputCore.validatePiPrompt(value, label);
  if (!validation.ok) return validation;
  const text = value.trim();
  if (text === "/") {
    return {...validation, ok:false, error:"Choose a command from the list below the message box."};
  }
  const slash = /^\/([A-Za-z][\w:-]*)(?:\s|$)/.exec(text);
  const commands = Array.isArray(view?.meta?.commands) ? view.meta.commands : [];
  if (slash && !commands.some(command => command?.name === slash[1])) {
    return {...validation, ok:false,
      error:`/${slash[1]} is not available in this ${label} session. Type / to see available commands; your text has not been cleared.`};
  }
  return validation;
}

function submitAgentConsoleInput() {
  const view = currentAgentConsoleView();
  const input = $("agentConsoleInput");
  const value = input.value;
  if (!view || input.disabled) return false;
  if (!value) {
    if (view.inputRetryPending && view.inputQueue.length) {
      view.inputRetryPending = false;
      view.inputError = "";
      void flushAgentConsoleInput(view, state.agentConsoleOwnerRunId, state.agentConsoleSurfaceId);
    } else if (agentConsoleUsesStructuredPi(view) && view.meta?.queuePaused === true
        && Number(view.meta?.pendingMessages) > 0) {
      const pendingControls = [...(view.inputQueue || []), ...(view.inputInFlightItems || [])];
      if (pendingControls.some(item => item?.command === "resume_queue")) return false;
      input.setCustomValidity("");
      view.inputError = "";
      queueAgentConsoleInput({command:"resume_queue"});
    } else return false;
    renderAgentConsole();
    (agentConsoleShowsPiTimeline(view) ? $("agentPiTimelineViewport") : $("agentTerminalViewport")).focus();
    return true;
  }
  if (agentConsoleUsesStructuredPi(view)) {
    const validation = validateAgentConsolePrompt(value, view);
    if (!validation.ok) {
      view.inputError = validation.error;
      input.setCustomValidity(validation.error);
      input.reportValidity();
      renderAgentConsole();
      input.focus();
      return false;
    }
  }
  input.setCustomValidity("");
  view.inputError = "";
  queueAgentConsoleInput(agentConsoleUsesStructuredPi(view)
    ? {command:"prompt", message:value} : `${value}\r`);
  input.value = "";
  saveAgentConsoleDraft();
  (agentConsoleShowsPiTimeline(view) ? $("agentPiTimelineViewport") : $("agentTerminalViewport")).focus();
  return true;
}

async function steerAgentConsoleInput() {
  const view = currentAgentConsoleView();
  const input = $("agentConsoleInput");
  if (!view || view.steerBusy || $("agentConsoleSteerButton").disabled) return;
  const message = input.value;
  saveAgentConsoleDraft();
  const draftKey = input.dataset.draftKey;
  const validation = AgentConsoleInputCore.validatePiPrompt(message, AgentConsoleInputCore.agentLabel(view?.meta?.protocol));
  if (!validation.ok || message.trimStart().startsWith("/")) {
    input.setCustomValidity(validation.error || "Use Send for slash commands. Steer accepts instructions for this task.");
    input.reportValidity();
    return;
  }
  input.setCustomValidity("");
  const ownerRunId = state.agentConsoleOwnerRunId;
  const surfaceId = state.agentConsoleSurfaceId;
  const startedAt = String(view.meta?.startedAt || "");
  const conversationId = String(view.meta?.conversationId || "");
  view.steerBusy = true;
  renderAgentConsole();
  try {
    const data = await api("/api/agent-console/input", {method:"POST",
      body:JSON.stringify({ownerRunId, surfaceId, command:"steer", message})});
    if (agentConsoleResponseTargetIsCurrent(view, ownerRunId, surfaceId, startedAt)
        && String(view.meta?.conversationId || "") === conversationId) {
      reconcileAgentConsoleViewMeta(view, data.console);
      if (view.inputDraftKey === draftKey && view.inputDraft === message) {
        // An acknowledgement belongs to its source console, even after a tab
        // switch. Preserve anything typed while the request was in flight.
        if (input.dataset.draftKey === draftKey && input.value === message) input.value = "";
        view.inputDraft = "";
        persistAgentConsoleDraft(draftKey, "");
      }
    }
  } catch (error) {
    showNotice(`Could not send steering. Your text has been kept. ${error.message}`, true);
  } finally {
    view.steerBusy = false;
    renderAgentConsole();
    scheduleAgentConsoleRead(0);
  }
}

function agentConsoleKeyData(event) {
  if (event.metaKey) return null;
  if (event.ctrlKey && !event.altKey && event.key?.length === 1) {
    const upper = event.key.toUpperCase();
    const code = upper.charCodeAt(0);
    if (code >= 64 && code <= 95) return String.fromCharCode(code - 64);
  }
  const keys = {
    Enter:"\r", Backspace:"\u007f", Tab:event.shiftKey ? "\u001b[Z" : "\t",
    Escape:"\u001b", ArrowUp:"\u001b[A", ArrowDown:"\u001b[B",
    ArrowRight:"\u001b[C", ArrowLeft:"\u001b[D", Home:"\u001b[H", End:"\u001b[F",
    PageUp:"\u001b[5~", PageDown:"\u001b[6~", Insert:"\u001b[2~", Delete:"\u001b[3~",
    F1:"\u001bOP", F2:"\u001bOQ", F3:"\u001bOR", F4:"\u001bOS",
    F5:"\u001b[15~", F6:"\u001b[17~", F7:"\u001b[18~", F8:"\u001b[19~",
    F9:"\u001b[20~", F10:"\u001b[21~", F11:"\u001b[23~", F12:"\u001b[24~",
  };
  if (Object.prototype.hasOwnProperty.call(keys, event.key)) return keys[event.key];
  if (event.key?.length === 1 && !event.ctrlKey) return `${event.altKey ? "\u001b" : ""}${event.key}`;
  return null;
}

function agentConsoleResponseTargetIsCurrent(view, ownerRunId, surfaceId, startedAt) {
  return Boolean(
    view && state.agentConsoleViews[surfaceId] === view
    && state.agentConsoleOwnerRunId === ownerRunId
    && String(view.meta?.startedAt || "") === startedAt
  );
}

async function stopAgentConsoleResponse() {
  const view = currentAgentConsoleView();
  const ownerRunId = state.agentConsoleOwnerRunId;
  const surfaceId = state.agentConsoleSurfaceId;
  if (!view || !ownerRunId || !surfaceId || view.abortBusy) return;
  if (!agentConsoleUsesStructuredPi(view)) {
    queueAgentConsoleInput("\u0003");
    return;
  }
  const startedAt = String(view.meta?.startedAt || "");
  const abortRequest = {};
  view.abortBusy = true;
  view.abortRequest = abortRequest;
  view.readDrainRemaining = AgentConsoleTabsCore.FINAL_DRAIN_READS;
  try {
    renderAgentConsole();
    if (
      view.abortRequest !== abortRequest
      || !agentConsoleResponseTargetIsCurrent(view, ownerRunId, surfaceId, startedAt)
    ) return;
    const data = await api("/api/agent-console/input", {
      method:"POST", body:JSON.stringify({ownerRunId, surfaceId, command:"abort"}),
    });
    const responseStartedAt = String(data.console?.startedAt || "");
    if (
      view.abortRequest === abortRequest
      && agentConsoleResponseTargetIsCurrent(view, ownerRunId, surfaceId, startedAt)
      && responseStartedAt === startedAt
    ) {
      reconcileAgentConsoleViewMeta(view, data.console);
      if (surfaceId === state.agentConsoleSurfaceId) {
        state.agentConsoleMeta = view.meta;
        renderAgentConsole();
      }
    }
  } catch (error) {
    if (
      view.abortRequest === abortRequest
      && agentConsoleResponseTargetIsCurrent(view, ownerRunId, surfaceId, startedAt)
    ) {
      showNotice(`Could not stop ${AgentConsoleInputCore.agentLabel(view.meta?.protocol)}'s current response. ${error.message}`, true);
    }
  } finally {
    if (view.abortRequest === abortRequest) {
      view.abortBusy = false;
      view.abortRequest = null;
      if (state.agentConsoleViews[surfaceId] === view && surfaceId === state.agentConsoleSurfaceId) {
        renderAgentConsole();
      }
    }
    scheduleAgentConsoleRead(0);
  }
}

async function flushAgentConsoleInput(view, ownerRunId, surfaceId) {
  if (!view || view.inputSending) return;
  view.inputSending = true;
  view.inputRetryPending = false;
  view.inputError = "";
  let activeBatch = null;
  try {
    while (view.inputQueue.length) {
      activeBatch = AgentConsoleInputCore.takeNextBatch(view.inputQueue);
      if (!activeBatch) break;
      view.inputInFlightPromptCount = AgentConsoleInputCore.queuedPiPromptCount(activeBatch.items);
      view.inputInFlightItems = activeBatch.items;
      renderAgentConsole();
      if (activeBatch.structured) {
        const data = await api("/api/agent-console/input", {
          method:"POST", body:JSON.stringify({ownerRunId, surfaceId, ...activeBatch.payload}),
        });
        activeBatch = null;
        view.inputInFlightPromptCount = 0;
        view.inputInFlightItems = [];
        if (state.agentConsoleViews[surfaceId] === view && ownerRunId === state.agentConsoleOwnerRunId) {
          reconcileAgentConsoleViewMeta(view, data.console);
        }
        if (surfaceId === state.agentConsoleSurfaceId) {
          state.agentConsoleMeta = view.meta;
          renderAgentConsole();
        }
        scheduleAgentConsoleRead(0);
        continue;
      }
      const data = await api("/api/agent-console/input", {
        method:"POST", body:JSON.stringify({ownerRunId, surfaceId, data:activeBatch.payload}),
      });
      activeBatch = null;
      view.inputInFlightPromptCount = 0;
      view.inputInFlightItems = [];
      if (state.agentConsoleViews[surfaceId] === view && ownerRunId === state.agentConsoleOwnerRunId) {
        reconcileAgentConsoleViewMeta(view, data.console);
      }
      if (surfaceId === state.agentConsoleSurfaceId) {
        state.agentConsoleMeta = view.meta;
        renderAgentConsole();
      }
      scheduleAgentConsoleRead(0);
    }
  } catch (error) {
    AgentConsoleInputCore.restoreFailedBatch(view.inputQueue, activeBatch);
    activeBatch = null;
    view.inputInFlightPromptCount = 0;
    view.inputInFlightItems = [];
    view.inputRetryPending = Boolean(view.inputQueue.length);
    view.inputError = view.inputRetryPending
      ? `Could not send the next Hub message. It is still first in the local queue; choose Retry send. ${error.message}`
      : error.message;
    if (surfaceId === state.agentConsoleSurfaceId) {
      renderAgentConsole();
    }
  } finally {
    view.inputSending = false;
    view.inputInFlightPromptCount = 0;
    view.inputInFlightItems = [];
    if (!view.inputRetryPending && !view.inputQueue.length) view.inputError = "";
    if (surfaceId === state.agentConsoleSurfaceId) renderAgentConsole();
  }
}

function agentConsoleDimensions() {
  const viewport = $("agentTerminalViewport");
  return {
    cols:Math.max(40, Math.min(240, Math.floor(Math.max(280, viewport.clientWidth - 30) / 6.7))),
    rows:Math.max(12, Math.min(100, Math.floor(Math.max(180, viewport.clientHeight - 26) / 15.2))),
  };
}

function scheduleAgentConsoleResize() {
  if (!state.agentConsoleVisible) return;
  if (state.agentConsoleResizeTimer !== null) clearTimeout(state.agentConsoleResizeTimer);
  state.agentConsoleResizeTimer = setTimeout(() => {
    state.agentConsoleResizeTimer = null;
    void resizeAgentConsole();
  }, 120);
}

async function resizeAgentConsole() {
  const view = currentAgentConsoleView();
  const meta = currentAgentConsoleRecord() || view?.meta || state.agentConsoleMeta;
  if (!state.agentConsoleVisible || !meta || !["running","starting"].includes(meta.state || meta.status)) return;
  if (agentConsoleUsesStructuredPi(view)) return;
  const size = agentConsoleDimensions();
  if (Number(meta.cols) === size.cols && Number(meta.rows) === size.rows) return;
  try {
    const data = await api("/api/agent-console/resize", {
      method:"POST", body:JSON.stringify({
        ownerRunId:state.agentConsoleOwnerRunId,
        surfaceId:state.agentConsoleSurfaceId,
        ...size,
      }),
    });
    if (view) {
      reconcileAgentConsoleViewMeta(view, data.console);
      view.terminal.resize(size.cols, size.rows);
      state.agentConsoleMeta = view.meta;
      renderAgentTerminalOutput();
    }
  } catch (_) {}
}

async function stopAgentConsoleSurface(attachment = null) {
  const target = attachment || currentAgentConsoleAttachment() || state.agentConsoleMeta;
  if (!target || state.agentConsoleBusy) return;
  const targetId = target.id || target.surfaceId;
  state.agentConsoleBusy = true;
  invalidateAgentConsoleRead();
  renderAgentConsole();
  try {
    const data = await api("/api/agent-console/stop", {
      method:"POST", body:JSON.stringify({ownerRunId:target.ownerRunId, surfaceId:targetId}),
    });
    if (target.ownerRunId !== state.agentConsoleOwnerRunId) return;
    const nextStatus = onHubStatus(data.hub, target.ownerRunId);
    if (nextStatus) observeStatus(nextStatus);
    syncAgentConsoleViews(state.runStatus, state.runStatus?.run, state.runPhase);
    const view = state.agentConsoleViews[targetId];
    if (view) {
      reconcileAgentConsoleViewMeta(view, data.console);
      view.readDrainRemaining = AgentConsoleTabsCore.FINAL_DRAIN_READS;
    }
    if (targetId === state.agentConsoleSurfaceId && view) state.agentConsoleMeta = view.meta;
    if (state.agentConsoleVisible && targetId === state.agentConsoleSurfaceId) leaveAgentConsole();
    renderAgentConsole();
    await navigation.refreshSessions();
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    state.agentConsoleBusy = false;
    renderAgentConsole();
    scheduleAgentConsoleRead(0);
  }
}

async function restartAgentConsoleSurface(attachment = null) {
  const target = attachment || currentAgentConsoleAttachment() || state.agentConsoleMeta;
  if (!target || state.agentConsoleBusy) return;
  const targetId = target.id || target.surfaceId;
  state.agentConsoleBusy = true;
  invalidateAgentConsoleRead();
  renderAgentConsole();
  try {
    const data = await api("/api/agent-console/restart", {
      method:"POST", body:JSON.stringify({ownerRunId:target.ownerRunId, surfaceId:targetId}),
    });
    if (target.ownerRunId !== state.agentConsoleOwnerRunId) return;
    const nextStatus = onHubStatus(data.hub, target.ownerRunId);
    if (nextStatus) observeStatus(nextStatus);
    syncAgentConsoleViews(state.runStatus, state.runStatus?.run, state.runPhase);
    const view = state.agentConsoleViews[targetId];
    if (view) {
      reconcileAgentConsoleViewMeta(view, data.console);
      view.seenEnd = 0;
      resetAgentConsoleTerminal(view, 0);
      resetAgentPiTimeline(view);
      view.readDrainRemaining = AgentConsoleTabsCore.FINAL_DRAIN_READS;
    }
    if (targetId === state.agentConsoleSurfaceId && view) {
      state.agentConsoleMeta = view.meta;
      state.agentConsoleVisible = true;
      if (agentConsoleShowsPiTimeline(view)) renderAgentPiTimeline({preserveScroll:false});
      else renderAgentTerminalOutput({preserveScroll:false});
      scheduleAgentConsoleResize();
    }
    await navigation.refreshSessions();
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    state.agentConsoleBusy = false;
    renderAgentConsole();
    scheduleAgentConsoleRead(0);
  }
}

listen($("hubFanMode"), "change", event => { if (event.target.value !== "unknown") void updateHubFans(event.target.value); });
listen($("agentConsoleBackButton"), "click", leaveAgentConsole);
listen($("agentConsoleLogButton"), "click", () => navigation.showLog());
listen($("agentConsoleSessionsButton"), "click", () => navigation.openSessions());
listen($("agentConsoleStopButton"), "click", () => stopAgentConsoleSurface());
listen($("agentConsoleRestartButton"), "click", () => restartAgentConsoleSurface());
listen($("agentConsoleTabs"), "click", event => {
  const tab = event.target.closest("[data-agent-console-tab]");
  if (tab) selectAgentConsole(tab.dataset.agentConsoleTab);
});
listen($("agentConsoleTabs"), "keydown", event => {
  if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) return;
  const tabs = [...$("agentConsoleTabs").querySelectorAll("[data-agent-console-tab]")];
  if (!tabs.length) return;
  event.preventDefault();
  const current = Math.max(0, tabs.indexOf(event.target.closest("[data-agent-console-tab]")));
  const next = event.key === "Home" ? 0
    : event.key === "End" ? tabs.length - 1
      : ["ArrowRight", "ArrowDown"].includes(event.key)
        ? (current + 1) % tabs.length : (current - 1 + tabs.length) % tabs.length;
  const surfaceId = tabs[next].dataset.agentConsoleTab;
  selectAgentConsole(surfaceId, {focus:false, show:true});
  requestAnimationFrame(() => [...$("agentConsoleTabs").querySelectorAll("[data-agent-console-tab]")].find(tab => tab.dataset.agentConsoleTab === surfaceId)?.focus());
});
listen($("agentConsoleFindButton"), "click", () => setAgentConsoleSearch(!state.agentConsoleSearchOpen));
listen($("agentConsoleCopyButton"), "click", copyAgentConsoleVisible);
listen($("agentConsoleDraftsButton"), "click", openAgentConsoleDrafts);
listen($("agentConsoleSearch"), "submit", event => {
  event.preventDefault();
  moveAgentConsoleSearch(event.shiftKey ? -1 : 1);
});
listen($("agentConsoleSearchInput"), "input", event => {
  state.agentConsoleSearchQuery = String(event.target.value || "").slice(0, AgentConsoleTabsCore.MAX_QUERY);
  state.agentConsoleSearchIndex = -1;
  renderAgentTerminalOutput({focusMatch:false});
});
listen($("agentConsoleSearchInput"), "keydown", event => {
  if (event.key === "Escape") {
    event.preventDefault();
    setAgentConsoleSearch(false);
  } else if (event.key === "Enter") {
    event.preventDefault();
    moveAgentConsoleSearch(event.shiftKey ? -1 : 1);
  }
});
listen($("agentConsoleSearchPrevious"), "click", () => moveAgentConsoleSearch(-1));
listen($("agentConsoleSearchNext"), "click", () => moveAgentConsoleSearch(1));
listen($("agentConsoleSearchClose"), "click", () => setAgentConsoleSearch(false));
listen($("agentConsoleJumpLatest"), "click", scrollAgentConsoleToLatest);
listen($("agentTerminalViewport"), "scroll", updateAgentConsoleScrollUi, {passive:true});
listen($("agentPiTimelineJumpLatest"), "click", scrollAgentPiTimelineToLatest);
listen($("agentPiTimelineViewport"), "scroll", handleAgentPiTimelineScroll, {passive:true});
listen($("agentPiTimelineViewport"), "wheel", event => {
  if (event.ctrlKey || !event.deltaY) return;
  recordAgentPiScrollIntent(event.deltaY < 0 ? "up" : "down");
}, {passive:true});
let agentPiTouchY = null;
listen($("agentPiTimelineViewport"), "touchstart", event => {
  agentPiTouchY = event.touches.length === 1 ? event.touches[0].clientY : null;
}, {passive:true});
listen($("agentPiTimelineViewport"), "touchmove", event => {
  const nextY = event.touches.length === 1 ? event.touches[0].clientY : null;
  if (agentPiTouchY !== null && nextY !== null && Math.abs(nextY - agentPiTouchY) > 2) {
    recordAgentPiScrollIntent(nextY > agentPiTouchY ? "up" : "down");
  }
  agentPiTouchY = nextY;
}, {passive:true});
let agentPiScrollbarPointer = null;
listen($("agentPiTimelineViewport"), "pointerdown", event => {
  if (event.pointerType === "touch" || event.button !== 0) return;
  const bounds = event.currentTarget.getBoundingClientRect();
  if (event.clientX >= bounds.right - 18) {
    agentPiScrollbarPointer = event.pointerId;
    recordAgentPiScrollIntent("scrollbar");
  }
}, {passive:true});
listen($("agentPiTimelineViewport"), "pointermove", event => {
  if (event.buttons === 1 && event.pointerId === agentPiScrollbarPointer) recordAgentPiScrollIntent("scrollbar");
}, {passive:true});
for (const type of ["pointerup", "pointercancel"]) listen(window, type, event => {
  if (event.pointerId !== agentPiScrollbarPointer) return;
  agentPiScrollbarPointer = null;
  const view = currentAgentConsoleView();
  if (view?.piScrollIntent === "scrollbar") view.piScrollIntentUntil = performance.now() + 100;
}, {passive:true});
const agentPiTimelineResizeObserver = new ResizeObserver(scheduleAgentPiTimelineFollow);
agentPiTimelineResizeObserver.observe($("agentPiTimeline"));
agentPiTimelineResizeObserver.observe($("agentPiTimelineViewport"));
listen($("agentConsoleInteractionOptions"), "click", event => {
  const button = event.target.closest("[data-agent-console-option]");
  if (button && !button.disabled) void respondAgentConsoleInteraction({value:button.dataset.agentConsoleOption || ""});
});
listen($("agentConsoleCustomUI"), "click", event => {
  const button = event.target.closest("[data-pi-key]");
  if (button && !button.disabled) void respondAgentConsoleInteraction({value:piMenuKeys[button.dataset.piKey]});
});
listen($("agentConsoleCustomFrame"), "keydown", event => {
  if (event.isComposing || event.metaKey || event.ctrlKey || event.altKey) return;
  const key = {ArrowUp:piMenuKeys.up, ArrowDown:piMenuKeys.down, ArrowLeft:piMenuKeys.left, ArrowRight:piMenuKeys.right, Enter:"\r", Escape:"\x1b", Backspace:"\x7f", Tab:"\t"}[event.key]
    || (event.key.length === 1 ? event.key : "");
  if (!key) return;
  event.preventDefault();
  void respondAgentConsoleInteraction({value:key});
});
listen($("agentConsoleCommands"), "click", event => {
  const button = event.target.closest("[data-pi-command]");
  if (!button) return;
  $("agentConsoleInput").value = `/${button.dataset.piCommand} `;
  saveAgentConsoleDraft();
  $("agentConsoleInput").focus();
  renderAgentConsoleCommands();
});
listen($("agentConsoleInput"), "keydown", event => {
  const panel = $("agentConsoleCommands");
  if (panel.hidden || !["Tab", "ArrowDown"].includes(event.key)) return;
  const first = panel.querySelector("button");
  if (first) { event.preventDefault(); first.focus(); }
});
listen($("agentConsoleInteractionCancel"), "click", () => {
  void respondAgentConsoleInteraction({cancelled:true});
});
listen($("agentConsoleInteractionNo"), "click", () => {
  void respondAgentConsoleInteraction({confirmed:false});
});
listen($("agentConsoleInteractionSubmit"), "click", () => {
  const method = $("agentConsoleInteraction").dataset.method;
  void respondAgentConsoleInteraction(method === "confirm"
    ? {confirmed:true} : {value:$("agentConsoleInteractionInput").value});
});
listen($("agentConsoleInteractionInput"), "keydown", event => {
  if (event.key === "Escape") {
    event.preventDefault();
    void respondAgentConsoleInteraction({cancelled:true});
  } else if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
    event.preventDefault();
    void respondAgentConsoleInteraction({value:event.currentTarget.value});
  }
});
listen($("agentConsoleForm"), "submit", event => {
  event.preventDefault();
  submitAgentConsoleInput();
});
listen($("agentConsoleSteerButton"), "click", steerAgentConsoleInput);
listen($("agentConsoleInput"), "input", event => {
  saveAgentConsoleDraft();
  renderAgentConsoleCommands();
  event.currentTarget.setCustomValidity("");
  const view = currentAgentConsoleView();
  if (view?.inputError && !view.inputRetryPending) {
    view.inputError = "";
    renderAgentConsole();
  }
});
listen($("agentConsoleCompactButton"), "click", () => queueAgentConsoleInput({command:"compact"}));
listen($("agentConsoleQueueEditText"), "input", event => {
  const view = currentAgentConsoleView();
  if (view?.queueEdit) view.queueEdit.text = event.target.value;
});
listen($("agentConsoleQueueCancel"), "click", () => {
  const view = currentAgentConsoleView();
  if (view) view.queueEdit = null;
  renderAgentConsole();
});
listen($("agentConsoleQueueSave"), "click", () => {
  const view = currentAgentConsoleView();
  if (view?.queueEdit) void changeAgentConsoleQueuedMessage(view, view.queueEdit.item, "edit", view.queueEdit.text);
});
listen($("agentConsoleEscapeButton"), "click", clearAgentConsolePendingMessages);
listen($("agentConsoleInterruptButton"), "click", () => {
  void stopAgentConsoleResponse();
});
listen($("agentTerminalViewport"), "keydown", event => {
  if (event.isComposing) return;
  if (agentConsoleUsesStructuredPi()) {
    if (event.key?.length === 1 && !event.metaKey && !event.ctrlKey && !event.altKey) {
      $("agentConsoleInput").focus();
    }
    return;
  }
  const value = agentConsoleKeyData(event);
  if (value === null) return;
  event.preventDefault();
  queueAgentConsoleInput(value);
});
listen($("agentTerminalViewport"), "paste", event => {
  const value = event.clipboardData?.getData("text");
  if (!value) return;
  if (agentConsoleUsesStructuredPi()) {
    event.preventDefault();
    $("agentConsoleInput").value += value;
    saveAgentConsoleDraft();
    $("agentConsoleInput").focus();
    return;
  }
  event.preventDefault();
  queueAgentConsoleInput(value.replaceAll("\n", "\r"));
});
listen($("agentPiTimelineViewport"), "keydown", event => {
  if (["ArrowUp", "PageUp", "Home"].includes(event.key)) recordAgentPiScrollIntent("up");
  if (["ArrowDown", "PageDown", "End"].includes(event.key)) recordAgentPiScrollIntent("down");
  if (event.isComposing || event.metaKey || event.ctrlKey || event.altKey || event.key?.length !== 1) return;
  event.preventDefault();
  $("agentConsoleInput").value += event.key;
  saveAgentConsoleDraft();
  $("agentConsoleInput").focus();
});
listen($("agentPiTimelineViewport"), "paste", event => {
  const value = event.clipboardData?.getData("text");
  if (!value) return;
  event.preventDefault();
  $("agentConsoleInput").value += value;
  saveAgentConsoleDraft();
  $("agentConsoleInput").focus();
});
listen(window, "resize", scheduleAgentConsoleResize);
listen(window, "pagehide", saveAgentConsoleDraft);
listen($("agentConsoleStatusPanel"), "toggle", renderAgentConsoleStatusDisclosure);
const prefillClockTimer = setInterval(renderAgentPrefillClock, 250);
listen($("agentConsoleActionsMenu"), "click", event => {
  if (!event.target.closest("button")) return;
  const menu = $("agentConsoleActionsMenu");
  menu.open = false;
  requestAnimationFrame(() => {
    // A command may focus its dialog or search field. Otherwise return focus
    // to the visible trigger instead of leaving it inside the closed menu.
    if (menu.contains(document.activeElement) || document.activeElement === document.body) {
      menu.querySelector("summary").focus();
    }
  });
});
listen(document, "pointerdown", event => {
  for (const id of ["agentConsoleActionsMenu", "agentConsoleStatusPanel"]) {
    const panel = $(id);
    if (panel.open && !panel.contains(event.target)) panel.open = false;
  }
});
listen($("agentWorkspace"), "keydown", event => {
  if (event.key !== "Escape") return;
  for (const id of ["agentConsoleActionsMenu", "agentConsoleStatusPanel"]) {
    const panel = $(id);
    if (panel.open) { panel.open = false; panel.querySelector("summary").focus(); event.preventDefault(); event.stopPropagation(); }
  }
});

    function beforeShow(action) {
      const ready = navigation.beforeShow ? navigation.beforeShow() : true;
      return ready && typeof ready.then === "function" ? ready.then(approved => approved ? action() : false) : ready ? action() : false;
    }
    function enter(attachment) {
      return beforeShow(() => {
        if (disposed || (runSnapshot?.run?.runId && attachment?.ownerRunId !== runSnapshot.run.runId)) return false;
        return enterAgentConsole(attachment);
      });
    }
    function select(surfaceId, options) {
      const expectedView = state.agentConsoleViews[surfaceId];
      return beforeShow(() => {
        if (disposed || !expectedView || state.agentConsoleViews[surfaceId] !== expectedView) return false;
        return selectAgentConsole(surfaceId, options);
      });
    }
    return {
      observe:observeStatus, update:updateAgentWorkspace, enter,
      select, leave:leaveAgentConsole, suspend, isVisible:() => state.agentConsoleVisible,
      currentView:currentAgentConsoleView, currentSurfaceId:() => state.agentConsoleSurfaceId,
      render:renderAgentConsole, renderTerminal:renderAgentTerminalOutput, renderTimeline:renderAgentPiTimeline,
      submit:submitAgentConsoleInput, steer:steerAgentConsoleInput, queue:queueAgentConsoleInput,
      flush:flushAgentConsoleInput, abort:stopAgentConsoleResponse, stop:stopAgentConsoleSurface, restart:restartAgentConsoleSurface,
      read:readAgentConsole, wake:() => scheduleAgentConsoleRead(0), cancelRead:invalidateAgentConsoleRead,
      resetTerminal:resetAgentConsoleTerminal, syncDetail:syncAgentConsoleStatusDetailMode,
      saveDraft:saveAgentConsoleDraft, openDrafts:openAgentConsoleDrafts, recoverDraft:recoverAgentConsoleDraft,
      dispose:() => {
        disposed = true; invalidateAgentConsoleRead();
        if (state.agentConsoleResizeTimer !== null) clearTimeout(state.agentConsoleResizeTimer);
        clearInterval(prefillClockTimer); agentPiTimelineResizeObserver.disconnect();
        if (agentPiFollowFrame) window.cancelAnimationFrame(agentPiFollowFrame);
        for (const [target, name, handler, options] of listeners) target.removeEventListener(name, handler, options);
        agentPiTimelineView.setVisible($("agentPiTimeline"), false);
      },
    };
  }
  return {createController};
});
