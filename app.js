const state = {
  token: "", models: [], binaries: {}, adapters: {engines:[], workSurfaces:[]}, clientSupport: {}, backend: "mtplx", client: "pi",
  freeToken: null, freeTokenBusy: false,
  selected: null, statusTimer: null, catalogNotice: "", applyingOptimal: false,
  optimizationGeneration: 0, optimalSignature: "", optimalLabel: "",
  pendingOptimizerSnapshot: null, pendingOptimizerBackend: "",
  optimizerMenuOpen: false, themeMenuOpen: false, hubToolsMenuOpen: false, runtimeInventory: null, runtimeLoading: false,
  runtimeUpdateCatalog: null, runtimeUpdatePlan: null, runtimeUpdateStatus: null,
  runtimeUpdatePhase: "idle", runtimeUpdateLoading: false, runtimeUpdateCompletionId: "",
  runtimePromotionPlan: null, runtimePromotionStatus: null,
  runtimePromotionPhase: "idle", runtimePromotionLoading: false,
  runtimePromotionCompletionId: "", runtimePromotionApplying: false,
  modelLibrary: null, modelLibraryRoots: [], modelLibraryLoading: false,
  modelLibraryQuery: "", modelLibraryEngine: "all", modelLibrarySurface: "all",
  modelLibraryState: "all",
  acquisitionPhase: "idle", acquisitionStatus: null, acquisitionPlan: null,
  acquisitionRoots: [], acquisitionSearchResults: [], acquisitionSearching: false,
  acquisitionInspecting: false, acquisitionGeneration: 0,
  acquisitionCompletionId: "", acquisitionDownloaderReady: false,
  profiles: [], profileLimit: 32, profileLoading: false, profileBusy: false,
  profileEditingId: "", profileDeleteConfirmId: "",
  sessionSets: [], sessionSetLimit: 16, sessionSetLoading: false,
  sessionSetBusy: false, sessionSetEditingId: "", sessionSetDeleteConfirmId: "",
  sessionSetPlan: null, sessionSetPlanLoading: false, sessionSetStatus: null,
  sessionSetSelectedId: "", sessionSetCompletionId: "", sessionSetStatusLoading: false,
  quickStartLoading: false, quickStartLoaded: false, quickStartError: "",
  quickStartRoutesOpen: false,
  calibrationPlan: null, calibrationLoading: false, calibrationGeneration: 0,
  calibrationEntry: null,
  calibrationDetailsOpen: false,
  calibrationJobId: "", calibrationCompletionId: "", calibrationApplying: false,
  calibrationProfileContractId: "",
  sessionDashboard: null, sessionLoading: false, sessionGeneration: 0,
  sessionAcknowledgementId: "", sessionAdmissionSignature: "", sessionLastLoadedAt: 0,
  sessionAttachmentPlan: null, sessionAttachmentLoading: false,
  sessionAttachmentBusy: false, sessionAttachmentGeneration: 0,
  sessionAttachmentOwnerRunId: "", sessionAttachmentSignature: "", sessionAttachmentTimer: null,
  warmRoutePlan: null, warmRouteLoading: false, warmRouteGeneration: 0,
  warmRouteSignature: "", warmRoutePendingSignature: "", warmRouteTimer: null,
  cacheObservatory: null, requestActivity: null,
  requestCancelBusyId: "", idlePolicyBusy: false,
  agentConsoleOwnerRunId: "", agentConsoleSurfaceId: "", agentConsoleMeta: null,
  agentConsoleViews: {}, agentConsoleRecoveryOwnerRunId: "",
  agentConsoleTimer: null, agentConsoleReading: false,
  agentConsoleVisible: false, agentConsoleBusy: false, agentConsoleResizeTimer: null,
  agentConsoleDismissed: false, agentConsoleSearchOpen: false,
  agentConsoleSearchQuery: "", agentConsoleSearchIndex: -1,
  agentConsoleCopyBusy: false,
  routeCheckPhase: "idle", routeCheckStatus: null, routeCheckPlan: null,
  routeCheckLoading: false, routeCheckGeneration: 0, routeCheckCompletionId: "",
  routeCheckIntent: "inspect", routeCheckInputSignature: "", verifiedLaunchBusy: false,
  runPhase: "idle", runStatus: null, chatMessages: [], chatAbort: null, chatRunId: "",
  chatOwnerRunId: "", chatAttachment: null, chatQueue: [],
  chatQueuePaused: false, chatQueueRecovered: false, chatQueueStorageAvailable: null,
  chatContextFiles: [], chatContextBusy: false, chatWorkspaceContext: null,
  chatBranch: null, chatEditingMessageId: "", chatQueueEditingId: "",
  chatContextReducedAt: 0, chatRevisionBusy: false,
  chatHistoryId: "", chatHistoryThreads: [], chatHistoryLoading: false,
  chatHistorySaving: false,
  chatHistoryDeleteConfirmId: "", chatHistoryEditingId: "",
  chatHistoryBusyId: "", chatHistoryQuery: "", chatHistoryLoaded: false,
  chatResumePlan: null, chatResumePlanLoading: false, chatResumeGeneration: 0,
  chatResumeHistoryId: "", chatResumeStarting: false,
  chatResumePending: null, chatResumeOpening: false,
  chatSidebarQuery: "", chatSidebarCollapsed: false, chatSidebarMenuId: "",
  chatSidebarEditingId: "", chatActiveThread: null,
  chatRunSettings: null, chatRunSettingsKey: "", chatRunSettingsBusy: false,
  chatRunSettingsGeneration: 0,
  chatDraftKey: "", chatDraftTimer: null, chatDraftRestored: false,
  chatDraftSavedAt: 0, chatDraftStorageAvailable: null,
  chatDraftPendingHistoryId: "",
  chatTurnTabId: "", chatTurnTabStorageAvailable: null, chatTurnRecoveryChecked: false,
  chatTurnRecoveryAvailable: null, chatTurnRecoveredHistoryId: "",
  chatTurnCheckpoint: null, chatTurnCheckpointTimer: null,
  chatTurnCheckpointPromise: null, chatTurnCheckpointDirty: false,
  chatTurnCheckpointLastAt: 0,
  chatDefaultsModelId: "", chatRenderFrame: null, chatFollowOutput: true,
  chatRenderRevision: 0, chatScrollInteractionRevision: 0,
  chatTranscriptSearchOpen: false, chatTranscriptQuery: "", chatTranscriptActiveId: "",
  benchmarkPhase: "idle", benchmarkResultId: "", benchmarkStatus: null,
  benchmarkHistory: null, benchmarkHistoryKey: "", benchmarkHistoryLoading: false,
  benchmarkHistoryGeneration: 0, benchmarkHistoryTimer: null, benchmarkHistoryError: "",
  performanceReceipt: null, performanceReceiptKey: "", performanceReceiptLoading: true,
  performanceReceiptGeneration: 0, performanceReceiptTimer: null, performanceReceiptError: "",
  setupPhase: "idle", setupStatus: null, setupPlan: null,
  setupRenderedPlanId: "", setupCompletionId: "",
  anePhase: "idle", aneStatus: null, aneCompletionId: "",
  aneClonePhase: "idle", aneCloneStatus: null, aneClonePlan: null,
  aneCloneRenderedPlanId: "", aneCloneCompletionPath: "", aneCloneLoading: false,
  routePreferenceReady: false,
};

const $ = (id) => document.getElementById(id);
// Keep the completed integration available for later without advertising an
// unfinished route in the everyday launcher. Re-enabling is one deliberate flag.
const UI_FEATURES = Object.freeze({freetoken:false});
function uiFeatureEnabled(feature) { return UI_FEATURES[feature] === true; }
function uiEngineVisible(backend) {
  return String(backend || "") !== "freetoken" || uiFeatureEnabled("freetoken");
}
function uiRequestVisible(request = {}) { return uiEngineVisible(request?.backend); }
function uiProfileVisible(profile = {}) {
  return uiRequestVisible(profile.request) && uiEngineVisible(profile.resolution?.backend);
}
function uiSessionSetVisible(sessionSet = {}) { return uiRequestVisible(sessionSet.baseRequest); }
function uiModelVisible(model = {}) {
  return uiFeatureEnabled("freetoken")
    || !(model.remote === true && model.modelType === "freetoken-remote");
}
function visibleEngineAdapters() {
  return (state.adapters?.engines || []).filter(adapter => uiEngineVisible(adapter.id));
}
function applyUiFeatureVisibility() {
  for (const feature of Object.keys(UI_FEATURES)) {
    const enabled = uiFeatureEnabled(feature);
    document.querySelectorAll(`[data-ui-feature="${feature}"]`).forEach(element => {
      element.hidden = !enabled;
      if ("disabled" in element) element.disabled = !enabled;
    });
  }
  if (!uiEngineVisible(state.backend)) state.backend = "mtplx";
  if (!uiFeatureEnabled("freetoken") && $("modelLibraryEngineFilter")?.value === "freetoken") {
    $("modelLibraryEngineFilter").value = "all";
    state.modelLibraryEngine = "all";
  }
  document.documentElement.dataset.freetokenUi = uiFeatureEnabled("freetoken") ? "enabled" : "hidden";
}
const ThemeCore = globalThis.LLMThemeCore;
if (!ThemeCore) throw new Error("Appearance theme support did not load.");
const WorkspaceContextCore = globalThis.LLMWorkspaceContextCore;
if (!WorkspaceContextCore) throw new Error("Workspace Context support did not load.");
const RoutePreferenceCore = globalThis.LLMRoutePreferenceCore;
if (!RoutePreferenceCore) throw new Error("Visible route preference support did not load.");
const ChatDraftsCore = globalThis.LLMChatDraftsCore;
if (!ChatDraftsCore) throw new Error("Chat draft recovery support did not load.");
const ChatQueueCore = globalThis.LLMChatQueueCore;
if (!ChatQueueCore) throw new Error("Chat queue recovery support did not load.");
const ChatScrollCore = globalThis.LLMChatScrollCore;
if (!ChatScrollCore) throw new Error("Chat scroll support did not load.");
const ChatTranscriptCore = globalThis.LLMChatTranscriptCore;
if (!ChatTranscriptCore) throw new Error("Chat transcript navigation support did not load.");
const ChatStreamCore = globalThis.LLMChatStreamCore;
if (!ChatStreamCore) throw new Error("Chat stream termination support did not load.");
const ChatStatusCore = globalThis.LLMChatStatusCore;
if (!ChatStatusCore) throw new Error("Compact Chat status support did not load.");
const SafeMarkdownCore = globalThis.LLMSafeMarkdownCore;
if (!SafeMarkdownCore) throw new Error("Safe Chat Markdown support did not load.");
const TerminalCore = globalThis.LLMTerminalCore;
if (!TerminalCore) throw new Error("Hub Console terminal support did not load.");
const AgentConsoleTabsCore = globalThis.LLMAgentConsoleTabs;
if (!AgentConsoleTabsCore) throw new Error("Hub Console tab support did not load.");
const formatNumber = (n) => Number(n || 0).toLocaleString();
const formatBytes = (bytes) => {
  const value = Math.max(0, Number(bytes || 0));
  if (value >= 1e12) return `${(value / 1e12).toFixed(1)} TB`;
  if (value >= 1e9) return `${(value / 1e9).toFixed(value < 10e9 ? 2 : 1)} GB`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(0)} MB`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(0)} KB`;
  return `${Math.round(value)} B`;
};
const formatShortDuration = (seconds) => {
  const value = Math.max(0, Number(seconds || 0));
  if (value < 10) return `${value.toFixed(1)}s`;
  if (value < 60) return `${Math.round(value)}s`;
  if (value < 3600) return `${Math.floor(value / 60)}m ${Math.round(value % 60)}s`;
  return `${Math.floor(value / 3600)}h ${Math.round((value % 3600) / 60)}m`;
};
const finiteMetric = value => (
  value !== null && value !== undefined && Number.isFinite(Number(value))
    ? Number(value) : null
);
const requestTps = ChatStatusCore.requestTps;
function requestLiveTelemetry(request) {
  const source = request?.liveTelemetry?.source;
  return request?.state === "running" && (source === "mtplx-flight" || source === "omlx-activity")
    ? request.liveTelemetry : null;
}
function liveRequestPhaseLabel(request) {
  const live = requestLiveTelemetry(request);
  if (!live) return "";
  if (live.phase === "prefill") return "Reading context";
  const reasoning = typeof live.reasoningCharacters === "number" ? live.reasoningCharacters : 0;
  const content = typeof live.contentCharacters === "number" ? live.contentCharacters : 0;
  if (content > 0) return "Answering";
  if (reasoning > 0) return "Reasoning";
  return live.source === "omlx-activity" ? "Generating" : "Decoding";
}
function liveRequestDetail(request) {
  const live = requestLiveTelemetry(request);
  if (!live) return "";
  const parts = [];
  if (Number.isInteger(live.processedPromptTokens) && Number.isInteger(live.promptTokens)) {
    parts.push(`${formatNumber(live.processedPromptTokens)} / ${formatNumber(live.promptTokens)} prompt`);
  } else if (Number.isInteger(live.contextTokens)) {
    parts.push(`${formatNumber(live.contextTokens)} context`);
  }
  if (Number.isInteger(live.generatedTokens)) parts.push(`${formatNumber(live.generatedTokens)} generated`);
  const acceptance = Array.isArray(live.acceptancePercentByDepth)
    ? live.acceptancePercentByDepth
      .map((value, index) => typeof value === "number" && Number.isFinite(value) ? `D${index + 1} ${value.toFixed(0)}%` : "")
      .filter(Boolean)
    : [];
  if (acceptance.length) parts.push(`MTP ${acceptance.join(" / ")}`);
  if (typeof live.stalledSeconds === "number" && live.stalledSeconds >= 5) {
    parts.push(`No new token for ${formatShortDuration(live.stalledSeconds)}`);
  }
  return parts.join(" · ");
}
function completedRequestDetail(request) {
  if (request?.runtimeStatsSource !== "lmstudio-response-stats") return "";
  const acceptance = finiteMetric(request.speculativeAcceptancePercent);
  return acceptance !== null && acceptance >= 0 && acceptance <= 100
    ? `MTP ${acceptance.toFixed(acceptance < 10 ? 1 : 0)}% accepted`
    : "";
}
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
const optimizerControls = {
  acceleration: "accelerationSelect", depth: "depthInput", profile: "profileSelect",
  fan: "fanSelect", burst: "burstSelect", dflashVerify: "dflashVerifySelect",
  dflashDraftQuant: "dflashDraftQuantSelect", anePrefill: "anePrefillSelect",
  gpu: "gpuSelect", parallel: "parallelInput",
  mtpMinTokens: "mtpMinTokensInput",
  mtpMinContinueProbability: "mtpMinContinueProbabilityInput",
  maxBatchSize: "freeTokenBatchSelect",
  expertCacheSize: "freeTokenExpertCacheInput",
  prefixCacheEntries: "freeTokenPrefixCacheSelect",
};
const optimizerKeys = {
  mtplx: ["acceleration", "depth", "profile", "fan"],
  omlx: ["acceleration", "depth", "dflashVerify", "dflashDraftQuant", "burst", "anePrefill"],
  lmstudio: [
    "acceleration", "depth", "mtpMinTokens",
    "mtpMinContinueProbability", "gpu", "parallel",
  ],
  freetoken: ["maxBatchSize", "expertCacheSize", "prefixCacheEntries"],
};
const enginePreferenceLabels = {
  fastest:"Fastest total", responsive:"Fastest first response",
  memory:"Lowest memory pressure", thermal:"Best thermal stability",
};
const CHAT_QUEUE_MAX_MESSAGES = 32;
const AGENT_CONSOLE_RECOVERY_KEY = "llm-launcher-agent-console-view-v1";
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
let chatMessageSequence = 0;

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.method === "POST") {
    headers["Content-Type"] = "application/json";
    headers["X-Launcher-Token"] = state.token;
  }
  const response = await fetch(path, { ...options, headers });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function showNotice(message, error = false) {
  const box = $("notice");
  if (!message) { box.classList.add("hidden"); return; }
  box.textContent = message;
  box.className = `notice${error ? " error" : ""}`;
}

function selectedModel() { return state.models.find(model => model.id === $("modelSelect").value) || null; }

function routeRuntimeInstalled(backend) {
  if (!uiEngineVisible(backend)) return false;
  const key = backend === "lmstudio" ? "lms" : backend;
  return Boolean(state.binaries?.[key]?.installed);
}

function orderedRouteIds(collection, fallback) {
  const allowed = new Set(fallback);
  return [...new Set([
    ...(state.adapters?.[collection] || []).map(adapter => adapter.id),
    ...fallback,
  ])].filter(id => allowed.has(id));
}

function visibleRouteCatalog() {
  const backends = orderedRouteIds("engines", ["omlx", "lmstudio", "mtplx", "freetoken"])
    .filter(uiEngineVisible);
  const clients = orderedRouteIds("workSurfaces", ["pi", "opencode", "codex", "chat"]);
  const routes = [];
  for (const backend of backends) {
    if (!routeRuntimeInstalled(backend)) continue;
    for (const model of state.models) {
      const capability = model?.backends?.[backend];
      if (!model?.ready || !capability?.runnable) continue;
      for (const client of clients) {
        const support = resolvedClientSupport(backend, client, model);
        if (clientInstalled(client) && support?.supported) {
          routes.push({backend, modelId:model.id, client});
        }
      }
    }
  }
  return routes;
}

function currentVisibleRoute() {
  return RoutePreferenceCore.normaliseRoute({
    backend:state.backend,
    modelId:String($("modelSelect")?.value || ""),
    client:state.client,
  });
}

function persistVisibleRoute() {
  if (!state.routePreferenceReady) return false;
  const route = currentVisibleRoute();
  const available = visibleRouteCatalog();
  if (!route || !RoutePreferenceCore.isRouteAvailable(route, available)) return false;
  return RoutePreferenceCore.writeRoute(themeStorage(), route).stored;
}

function initialiseVisibleRoute() {
  const preference = RoutePreferenceCore.readRoute(themeStorage());
  const route = RoutePreferenceCore.selectInitialRoute({
    preference,
    current:currentVisibleRoute(),
    routes:visibleRouteCatalog(),
  });
  if (!route) {
    state.routePreferenceReady = true;
    return null;
  }
  if (state.backend !== route.backend) {
    state.backend = route.backend;
    updateBackend(true);
  }
  const option = [...$("modelSelect").options].find(item => item.value === route.modelId && !item.disabled);
  if (option) $("modelSelect").value = route.modelId;
  state.client = route.client;
  modelChanged();
  state.routePreferenceReady = true;
  persistVisibleRoute();
  return route;
}

function freeTokenRoute(model = selectedModel()) {
  if (model?.remote === true) return "remote";
  if (model?.nativeFreetoken === true || model?.backends?.freetoken?.native === true) return "native";
  return "unavailable";
}

function freeTokenQualification(model = selectedModel()) {
  const capability = model?.backends?.freetoken || {};
  const qualification = capability.nativeContract?.qualification || {};
  const policy = qualification.launcher || {};
  const readiness = String(capability.qualificationReadiness || policy.readiness || "unknown");
  const qualified = Boolean(
    capability.realCheckpointVerified === true
    && qualification.real_checkpoint_verified === true
    && qualification.inspected_checkpoint_qualified === true
    && readiness === "qualified_real_checkpoint"
  );
  return {
    readiness,
    qualified,
    experimental:readiness === "experimental_synthetic_only" && !qualified,
    largeDownloadRecommended:policy.large_download_recommended === true,
  };
}

function freeTokenExperimentalConsentRequired(model = selectedModel()) {
  return state.backend === "freetoken"
    && freeTokenRoute(model) === "native"
    && freeTokenQualification(model).experimental;
}

function freeTokenExperimentalConsentAccepted(model = selectedModel()) {
  const input = $("freeTokenExperimentalConsent");
  return !freeTokenExperimentalConsentRequired(model) || Boolean(
    input?.checked && input.dataset.modelId === String(model?.id || "")
  );
}

function resolvedClientSupport(backend = state.backend, client = state.client, model = selectedModel()) {
  const fallback = state.clientSupport?.[backend]?.[client] || {};
  const candidate = model?.backends?.[backend]?.clientSupport?.[client];
  if (candidate && typeof candidate.supported === "boolean") {
    return {
      supported:candidate.supported,
      reason:String(candidate.reason || fallback.reason || "Compatibility is unavailable."),
    };
  }
  if (
    backend === "freetoken" && !model
    && state.freeToken?.native?.installed && !state.freeToken?.connected
  ) {
    return client === "chat"
      ? {supported:true, reason:"Native FreeToken Chat needs a compatible local Qwen3-MoE checkpoint"}
      : {supported:false, reason:"The native FreeToken milestone has no tool calling or Responses API yet"};
  }
  return {
    supported:fallback.supported === true,
    reason:String(fallback.reason || "This runtime and work surface are not compatible."),
  };
}

function runtimeKvValue(backend = state.backend) {
  if (backend === "omlx") return $("omlxKv").value;
  if (backend === "mtplx") return $("mtplxKv").value;
  return "off";
}

function setRuntimeKvValue(backend, value) {
  if (backend === "lmstudio" || backend === "freetoken") return value === "off";
  const control = backend === "omlx" ? $("omlxKv") : $("mtplxKv");
  const option = [...control.options].find(item => item.value === String(value));
  if (!option) return false;
  control.value = String(value);
  return true;
}

function gatherOptions() {
  if (state.backend === "freetoken") {
    const expertText = $("freeTokenExpertCacheInput").value.trim();
    return {
      acceleration:"off", depth:1, kv:"off",
      maxBatchSize:Number($("freeTokenBatchSelect").value),
      expertCacheSize:expertText === "" ? null : Number(expertText),
      prefixCacheEntries:Number($("freeTokenPrefixCacheSelect").value),
      experimentalQualificationConsent:freeTokenExperimentalConsentAccepted(),
    };
  }
  return {
    acceleration: $("accelerationSelect").value,
    depth: Number($("depthInput").value),
    profile: $("profileSelect").value,
    kv: runtimeKvValue(),
    fan: $("fanSelect").value,
    burst: $("burstSelect").value,
    dflashVerify: $("dflashVerifySelect").value,
    dflashDraftQuant: $("dflashDraftQuantSelect").value,
    anePrefill: $("anePrefillSelect").value,
    gpu: $("gpuSelect").value,
    parallel: Number($("parallelInput").value),
    mtpMinTokens: Number($("mtpMinTokensInput").value),
    mtpMinContinueProbability: Number($("mtpMinContinueProbabilityInput").value),
  };
}

function gatherChatSettings() {
  const seed = $("seedInput").value.trim();
  return {
    systemPrompt: $("systemPrompt").value,
    sampling: $("samplingMode").value,
    temperature: Number($("temperatureInput").value),
    topP: Number($("topPInput").value),
    topK: Number($("topKInput").value),
    presencePenalty: Number($("presencePenaltyInput").value),
    frequencyPenalty: Number($("frequencyPenaltyInput").value),
    seed: seed === "" ? null : Number(seed),
  };
}

function gather(mode = "custom", includeMemoryAcknowledgement = true) {
  const model = selectedModel();
  if (!model) throw new Error("Choose a ready model.");
  const request = {
    backend: state.backend, client: state.client, modelId: model.id,
    project: $("projectPath").value, context: Number($("contextInput").value),
    output: Number($("outputInput").value), reasoning: $("reasoningSelect").value,
    mode, options: gatherOptions(),
  };
  if (state.client === "chat") request.chat = gatherChatSettings();
  else request.agentHost = $("agentHostSelect").value;
  const admissionSignature = JSON.stringify(request);
  if (
    includeMemoryAcknowledgement
    && state.sessionAcknowledgementId
    && state.sessionAdmissionSignature === admissionSignature
  ) request.memoryAcknowledgement = state.sessionAcknowledgementId;
  return request;
}

function protectedSnapshot(includeBackend = true) {
  const model = selectedModel();
  return JSON.stringify({
    ...(includeBackend ? {backend: state.backend} : {}),
    model: model?.id || "", project: $("projectPath").value,
    context: $("contextInput").value,
    output: $("outputInput").value, reasoning: $("reasoningSelect").value,
    kv: runtimeKvValue(),
    agentHost: state.client === "chat" ? "launcher" : $("agentHostSelect").value,
    chat: state.client === "chat" ? gatherChatSettings() : null,
  });
}

function speedSignature() {
  const options = gatherOptions();
  return JSON.stringify({
    backend: state.backend, model: selectedModel()?.id || "",
    kv: options.kv,
    values: Object.fromEntries((optimizerKeys[state.backend] || []).map(key => [key, options[key]])),
  });
}

function optimizerValueSnapshot() {
  return Object.fromEntries(Object.entries(optimizerControls).map(([key, id]) => [key, $(id).value]));
}

function restoreOptimizerValues(snapshot) {
  Object.entries(snapshot || {}).forEach(([key, value]) => {
    const control = $(optimizerControls[key]);
    if (control) control.value = value === null || value === undefined ? "" : String(value);
  });
  setRangeVisual($("depthInput"), $("depthValue"));
  setRangeVisual($("parallelInput"), $("parallelValue"));
  setRangeVisual($("mtpMinTokensInput"), $("mtpMinTokensValue"));
  setRangeVisual($("mtpMinContinueProbabilityInput"), $("mtpMinContinueProbabilityValue"));
  updateAccelerationState();
}

function clearOptimizerAnimationClasses() {
  document.querySelectorAll(".optimizable.optimizing, .optimizable.optimized").forEach(field => {
    field.classList.remove("optimizing", "optimized");
  });
}

function setOptimizationState(kind, label = "", detail = "") {
  const badge = $("optimizationBadge");
  badge.dataset.state = kind;
  badge.textContent = label || ({custom:"Custom", applying:"Applying…", applied:"Optimised"}[kind] || kind);
  $("optimizationStatus").textContent = detail;
  $("optimizationStatus").title = detail;
  if (kind !== "applied") $("launchSummary").textContent = "Current visible settings";
  else $("launchSummary").textContent = label;
}

function markOptimizerCustom() {
  if (state.applyingOptimal) return;
  if (state.optimalSignature && speedSignature() === state.optimalSignature) return;
  state.optimalSignature = "";
  state.optimalLabel = "";
  setOptimizationState("custom", "Custom", "Performance controls were edited.");
}

function cancelOptimization(reason = "") {
  const rollbackBackend = state.pendingOptimizerBackend;
  if (state.applyingOptimal && state.pendingOptimizerSnapshot) {
    restoreOptimizerValues(state.pendingOptimizerSnapshot);
  }
  state.pendingOptimizerSnapshot = null;
  state.pendingOptimizerBackend = "";
  state.optimizationGeneration += 1;
  state.applyingOptimal = false;
  if (rollbackBackend && state.backend !== rollbackBackend) {
    state.backend = rollbackBackend;
    updateBackend(true);
  }
  clearOptimizerAnimationClasses();
  setOptimizerInteractionLocked(false);
  $("optimizationPanel").setAttribute("aria-busy", "false");
  state.optimalSignature = "";
  state.optimalLabel = "";
  setOptimizationState("custom", "Custom", reason);
}

function setOptimizerInteractionLocked(locked) {
  const advanced = $("advancedControls");
  if (locked) {
    advanced.setAttribute("inert", "");
    advanced.classList.add("interaction-locked");
  } else {
    advanced.removeAttribute("inert");
    advanced.classList.remove("interaction-locked");
  }
}

function setOptimizerMenu(open, focusFirst = false) {
  const menu = $("optimizerMenu");
  const button = $("optimizerMenuButton");
  const next = Boolean(open && !button.disabled);
  if (next) { setThemeMenu(false); setHubToolsMenu(false); }
  state.optimizerMenuOpen = next;
  menu.hidden = !next;
  button.setAttribute("aria-expanded", String(next));
  if (next && focusFirst) menu.querySelector('[role="menuitem"]')?.focus();
}

function closeOptimizerMenu() { setOptimizerMenu(false); }

function toggleOptimizerMenu() {
  setOptimizerMenu(!state.optimizerMenuOpen, !state.optimizerMenuOpen);
}

function themeStorage() {
  try { return globalThis.localStorage; } catch (_error) { return null; }
}

function activeTheme() {
  return ThemeCore.normaliseTheme(document.documentElement.dataset.theme);
}

function activeDetail() {
  return ThemeCore.normaliseDetail(document.documentElement.dataset.detail);
}

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

function updateAgentConsoleStatusSummaryLabel() {
  const summary = $("agentConsoleStatusSummary");
  const panel = $("agentConsoleStatusPanel");
  if (!summary || !panel) return;
  const processState = $("agentConsoleStatusState")?.hidden
    ? "" : $("agentConsoleStatusState")?.textContent;
  summary.setAttribute("aria-label", [
    $("agentConsoleStatusSurface")?.textContent,
    $("agentConsoleStatusModel")?.textContent,
    `Speed ${$("agentConsoleStatusSpeedValue")?.textContent || "not reported"}`,
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

function syncAgentConsoleStatusDetailMode(detail = activeDetail()) {
  const panel = $("agentConsoleStatusPanel");
  if (!panel) return;
  panel.open = detail === "detailed";
  renderAgentConsoleStatusDisclosure();
}

function renderRuntimeAdvancedDisclosure() {
  const panel = $("runtimeAdvancedTools");
  if (!panel) return;
  const label = panel.querySelector("summary em");
  if (label) label.textContent = panel.open ? "Hide tools" : "Show tools";
}

function syncRuntimeAdvancedDetailMode(detail = activeDetail()) {
  const panel = $("runtimeAdvancedTools");
  if (!panel) return;
  const workflowOpen = Boolean(
    state.runtimeUpdatePlan || state.runtimePromotionPlan
    || runtimeUpdateIsActive() || runtimePromotionIsActive()
  );
  panel.open = workflowOpen || detail === "detailed";
  renderRuntimeAdvancedDisclosure();
}

function renderRuntimeCardDisclosure(panel) {
  if (!panel) return;
  const label = panel.querySelector(":scope>summary em");
  if (label) label.textContent = panel.open ? "Hide" : "Details";
}

function syncRuntimeCardDetailMode(detail = activeDetail()) {
  document.querySelectorAll(".runtime-card-details").forEach(panel => {
    panel.open = detail === "detailed";
    renderRuntimeCardDisclosure(panel);
  });
}

function renderThemeMenu() {
  const active = activeTheme();
  const detail = activeDetail();
  const definition = ThemeCore.THEMES.find(theme => theme.id === active) || ThemeCore.THEMES[0];
  $("themeToolbarLabel").textContent = definition.label;
  $("themeMenuButton").setAttribute("aria-label", `Appearance: ${definition.label} theme, ${detail} information level`);
  document.querySelectorAll("[data-theme-choice]").forEach(button => {
    const selected = button.dataset.themeChoice === active;
    button.classList.toggle("selected", selected);
    button.setAttribute("aria-checked", String(selected));
  });
  document.querySelectorAll("[data-detail-choice]").forEach(button => {
    const selected = button.dataset.detailChoice === detail;
    button.classList.toggle("selected", selected);
    button.setAttribute("aria-checked", String(selected));
  });
  const detailed = detail === "detailed";
  $("interfaceDetailButton").setAttribute("aria-pressed", String(detailed));
  $("interfaceDetailButton").setAttribute("aria-label", detailed ? "Switch to focused view" : "Show detailed diagnostics and explanations");
  $("interfaceDetailButton").querySelector("strong").textContent = detailed ? "Focused view" : "Show details";
}

function setThemeMenu(open, focusSelected = false) {
  const next = Boolean(open);
  if (next) { closeOptimizerMenu(); setHubToolsMenu(false); }
  state.themeMenuOpen = next;
  $("themeMenu").hidden = !next;
  $("themeMenuButton").setAttribute("aria-expanded", String(next));
  if (next && focusSelected) {
    ($("themeMenu").querySelector('[aria-checked="true"]') || $("themeMenu").querySelector('[role="menuitemradio"]'))?.focus();
  }
}

function closeThemeMenu() { setThemeMenu(false); }

function selectTheme(value) {
  const theme = ThemeCore.applyTheme(document.documentElement, value);
  ThemeCore.writeTheme(themeStorage(), theme);
  renderThemeMenu();
  closeThemeMenu();
  $("themeMenuButton").focus();
}

function selectDetail(value, focusMenuButton = true) {
  const detail = ThemeCore.applyDetail(document.documentElement, value);
  ThemeCore.writeDetail(themeStorage(), detail);
  renderThemeMenu();
  renderQuickStart();
  syncChatStatusDetailMode(detail);
  syncChatResumeDetailMode(detail);
  syncAgentConsoleStatusDetailMode(detail);
  syncRuntimeAdvancedDetailMode(detail);
  syncRuntimeCardDetailMode(detail);
  if (state.models.length) refreshLaunchability();
  closeThemeMenu();
  if (focusMenuButton) $("themeMenuButton").focus();
}

function toggleInterfaceDetail() {
  const button = $("interfaceDetailButton");
  selectDetail(activeDetail() === "focused" ? "detailed" : "focused", false);
  button.focus();
}

function setHubToolsMenu(open, focusFirst = false) {
  const next = Boolean(open);
  if (next) { closeOptimizerMenu(); setThemeMenu(false); }
  state.hubToolsMenuOpen = next;
  $("hubToolsMenu").hidden = !next;
  $("hubToolsMenuButton").setAttribute("aria-expanded", String(next));
  if (next && focusFirst) $("hubToolsMenu").querySelector('[role="menuitem"]')?.focus();
}

function closeHubToolsMenu() { setHubToolsMenu(false); }

function reasoningChoices(client = state.client) {
  const capability = selectedModel()?.backends?.[state.backend];
  return capability?.[client === "codex" ? "codexReasoning" : "agentReasoning"] || ["auto"];
}

function adapterDescriptor(collection, id) {
  return (state.adapters?.[collection] || []).find(adapter => adapter.id === id);
}

function clientName(client) {
  return adapterDescriptor("workSurfaces", client)?.label
    || ({pi:"Pi", opencode:"OpenCode", codex:"Codex", chat:"Chat"})[client]
    || client;
}

function clientInstalled(client) {
  const adapter = adapterDescriptor("workSurfaces", client);
  if (adapter) return Boolean(adapter.installed);
  return client === "chat" || Boolean(state.binaries?.[client]?.installed);
}

function clientAvailability(client = state.client) {
  const support = resolvedClientSupport(state.backend, client);
  if (!support?.supported) return { available: false, reason: support?.reason || "This runtime and work surface are not compatible." };
  if (!clientInstalled(client)) return { available: false, reason: `${clientName(client)} is not installed.` };
  const allowed = reasoningChoices(client);
  if (!allowed.includes($("reasoningSelect").value)) {
    const labels = allowed.map(value => value === "auto" ? "Model default" : value).join(", ");
    return { available: false, reason: `This exact route can enforce these reasoning choices: ${labels}. Choose one explicitly.` };
  }
  return { available: true, reason: support.reason || "Supported" };
}

function chatSettingsError() {
  if (state.client !== "chat") return "";
  if ($("systemPrompt").value.length > 32000) return "System prompt must be at most 32,000 characters.";
  const capability = selectedModel()?.backends?.[state.backend] || {};
  if ($("samplingMode").value === "custom" && capability.customSampling === false) {
    return capability.samplingReason || "This model/runtime route does not support custom sampling.";
  }
  if ($("samplingMode").value !== "custom") return "";
  const temperatureText = $("temperatureInput").value.trim();
  const topPText = $("topPInput").value.trim();
  const topKText = $("topKInput").value.trim();
  const presencePenaltyText = $("presencePenaltyInput").value.trim();
  const frequencyPenaltyText = $("frequencyPenaltyInput").value.trim();
  if (!temperatureText) return "Temperature is required when custom sampling is selected.";
  if (!topPText) return "Top P is required when custom sampling is selected.";
  if (!topKText) return "Top K is required when custom sampling is selected.";
  if (!presencePenaltyText) return "Presence penalty is required when custom sampling is selected.";
  if (!frequencyPenaltyText) return "Frequency penalty is required when custom sampling is selected.";
  const temperature = Number(temperatureText);
  const topP = Number(topPText);
  const topK = Number(topKText);
  const presencePenalty = Number(presencePenaltyText);
  const frequencyPenalty = Number(frequencyPenaltyText);
  const seedText = $("seedInput").value.trim();
  if (!Number.isFinite(temperature) || temperature < 0 || temperature > 2) return "Temperature must be between 0 and 2.";
  if (!Number.isFinite(topP) || topP < 0 || topP > 1) return "Top P must be between 0 and 1.";
  if (!Number.isInteger(topK) || topK < 0 || topK > 1000000) return "Top K must be a whole number between 0 and 1,000,000.";
  if (!Number.isFinite(presencePenalty) || presencePenalty < -2 || presencePenalty > 2) return "Presence penalty must be between -2 and 2.";
  if (!Number.isFinite(frequencyPenalty) || frequencyPenalty < -2 || frequencyPenalty > 2) return "Frequency penalty must be between -2 and 2.";
  if (seedText !== "") {
    const seed = Number(seedText);
    if (!Number.isInteger(seed) || seed < 0 || seed > 4294967295) return "Seed must be a whole number between 0 and 4,294,967,295.";
  }
  return "";
}

function limitError() {
  const model = selectedModel();
  const context = Number($("contextInput").value);
  const output = Number($("outputInput").value);
  if (!Number.isInteger(context) || context < 1024) return "Context must be at least 1,024 tokens.";
  if (model?.nativeContext && context > model.nativeContext) return `This model advertises at most ${formatNumber(model.nativeContext)} context tokens. The launcher will not silently lower your value.`;
  if (!Number.isInteger(output) || output < 256) return "Maximum response must be at least 256 tokens.";
  if (output >= context) return "Maximum response must be smaller than context.";
  if (context - output < 1024) return "Leave at least 1,024 context tokens for instructions and history.";
  if (state.client === "codex" && output < 1024) return "Codex local sessions need at least 1,024 response tokens.";
  return "";
}

const rangeOutputIds = {
  depthInput:"depthValue", parallelInput:"parallelValue",
  mtpMinTokensInput:"mtpMinTokensValue",
  mtpMinContinueProbabilityInput:"mtpMinContinueProbabilityValue",
};

function rangeOutputFor(input) {
  return $(rangeOutputIds[input?.id]);
}

function rangePrecision(input) {
  const step = String(input.step || "1");
  return step.includes(".") ? step.split(".")[1].length : 0;
}

function quantizedRangeValue(input, value) {
  const min = Number(input.min || 0), max = Number(input.max || 100);
  const step = Math.max(Number(input.step || 1), Number.EPSILON);
  const clamped = Math.max(min, Math.min(max, Number(value)));
  return Number((min + Math.round((clamped - min) / step) * step).toFixed(rangePrecision(input)));
}

function setRangeVisual(input, output = rangeOutputFor(input)) {
  const min = Number(input.min || 0), max = Number(input.max || 100), value = Number(input.value);
  const percent = max > min ? ((value - min) / (max - min)) * 100 : 0;
  input.style.setProperty("--range-progress", `${Math.max(0, Math.min(100, percent))}%`);
  if (output) output.textContent = value.toFixed(rangePrecision(input));
}

function renderDflashReadiness(cap = {}) {
  const readiness = cap.dflashReadiness || {};
  const targetReady = Boolean(readiness.targetCompatible);
  const runtimeReady = Boolean(readiness.runtimeReady);
  const draftReady = Boolean(readiness.draftInstalled);
  const runtimeDetail = runtimeReady
    ? `${readiness.runtimeDetected || "oMLX"}${readiness.runtimeRecommended ? " · current recommended build" : ` · supported; ${readiness.recommendedRuntime || "rc2"} recommended`}`
    : `${readiness.runtimeDetected || "Not installed"} · needs ${readiness.recommendedRuntime || "0.6.3rc2"}`;
  const draftDetail = draftReady
    ? `${readiness.draftRepo || "Matching draft"} installed`
    : readiness.draftDetected
      ? `Draft detected but ${readiness.draftStatus || "incomplete"}`
      : `${readiness.draftSizeLabel || "3.85 GB"} draft not installed`;
  const checks = [
    {ready:targetReady, title:"Target", detail:readiness.targetReason || "No matching published draft"},
    {ready:runtimeReady, title:"Runtime", detail:runtimeDetail},
    {ready:draftReady, title:"Draft", detail:draftDetail},
  ];
  $("dflashChecks").innerHTML = checks.map(check => `<div class="dflash-check ${check.ready ? "pass" : "pending"}"><i>${check.ready ? "✓" : "!"}</i><span><b>${esc(check.title)}</b>${esc(check.detail)}</span></div>`).join("");
  const blockers = checks.filter(check => !check.ready).length;
  const badge = $("dflashBadge");
  badge.className = cap.dflash ? "ready" : "pending";
  badge.textContent = cap.dflash ? "Ready" : (targetReady ? `${blockers} step${blockers === 1 ? "" : "s"}` : "No pair");
  $("dflashStatus").textContent = cap.dflash
    ? (cap.dflashBenchmarkVerified ? "Paired and locally benchmarked." : "Pair ready; choose it manually until a local benchmark proves it wins.")
    : cap.dflashReason || "Select an oMLX model to inspect its DFlash 2 path.";
  $("openSetupButton").disabled = !(state.backend === "omlx" && targetReady);
  $("openSetupButton").innerHTML = cap.dflash
    ? 'Review Setup Assistant <span aria-hidden="true">→</span>'
    : 'Open Setup Assistant <span aria-hidden="true">→</span>';
}

function renderAneReadiness(cap = {}) {
  const readiness = cap.aneReadiness || {};
  const checks = [
    {ready:Boolean(readiness.modelCompatible), title:"Checkpoint", detail:readiness.modelReason || "Dense Qwen affine layout required"},
    {ready:Boolean(readiness.runtimeVersionReady ?? readiness.runtimeReady), title:"oMLX version", detail:(readiness.runtimeVersionReady ?? readiness.runtimeReady) ? `${readiness.runtimeDetected || "Ready"}` : `${readiness.runtimeDetected || "Not installed"} · needs ${readiness.minimumRuntime || "0.6.3rc2"}`},
    {ready:Boolean(readiness.kernelReady), title:"Native kernel", detail:readiness.kernelReason || "Native Qwen prefill kernel required"},
    {ready:Boolean(readiness.memoryReady), title:"Memory reserve", detail:readiness.memory?.reason || "Checkpoint weights + 8 GB reserve"},
  ];
  $("aneChecks").innerHTML = checks.map(check => `<div class="dflash-check ${check.ready ? "pass" : "pending"}"><i>${check.ready ? "✓" : "!"}</i><span><b>${esc(check.title)}</b>${esc(check.detail)}</span></div>`).join("");
  const verified = Boolean(cap.aneTuningVerified && cap.aneTuning?.accepted);
  const recommendation = cap.aneTuning?.recommendation || {};
  const tunedOption = $("anePrefillSelect").querySelector('option[value="tuned"]');
  tunedOption.disabled = !verified;
  tunedOption.textContent = verified
    ? `Use measured split · +${Number(recommendation.speedup_percent || 0).toFixed(1)}% prefill`
    : "Use measured local split · tune first";
  if (!verified && $("anePrefillSelect").value === "tuned") $("anePrefillSelect").value = "off";
  const badge = $("aneBadge");
  badge.className = verified ? "measured" : (readiness.ready ? "ready" : "");
  badge.textContent = verified ? "Measured" : (readiness.ready ? "Ready to tune" : "Blocked");
  $("aneStatus").textContent = verified
    ? cap.aneReason
    : cap.aneTuning?.decision || readiness.reason || cap.aneReason || "Select an oMLX checkpoint to inspect ANE prefill.";
  $("anePrefillHelp").textContent = verified
    ? "Exact model/runtime/Mac match; still approximate and explicit."
    : "Approximate and never enabled silently; run the local tuner first.";
  $("aneReleaseLink").href = readiness.releaseUrl || "https://github.com/jundot/omlx/releases/tag/v0.6.3rc2";
  $("openAneButton").disabled = !(state.backend === "omlx" && selectedModel());
}

function backendName(backend) {
  return adapterDescriptor("engines", backend)?.label
    || ({omlx:"oMLX", lmstudio:"LM Studio", mtplx:"MTPLX", freetoken:"FreeToken"})[backend]
    || backend;
}

function backendMark(backend) {
  return ({omlx:"O", lmstudio:"LM", mtplx:"M", freetoken:"FT", lms:"LM"})[backend] || "?";
}

function benchmarkCandidates(cap = {}, backend = state.backend) {
  if (backend === "freetoken") return [{
    id:cap.native === true ? "native" : "remote",
    label:cap.native === true ? "Native greedy" : "Server managed",
    available:Boolean(cap.runnable),
  }];
  const modes = [{id:"ar", label:"AR", available:Boolean(cap.runnable)}];
  if (cap.mtp) modes.push({id:"mtp", label:"MTP", available:true});
  if (backend === "omlx" && cap.dflash) modes.push({id:"dflash2", label:"DFlash 2", available:true});
  return modes;
}

function engineShootoutRoutes(model = selectedModel()) {
  if (!model) return [];
  const kv = runtimeKvValue();
  const reasoning = $("reasoningSelect").value;
  const binaryKeys = Object.fromEntries(
    visibleEngineAdapters().map(adapter => [adapter.id, adapter.binaryKey]),
  );
  const kvChoices = {omlx:["off","q8","q6","q4"], lmstudio:["off"], mtplx:["off","q8","q4"], freetoken:["off"]};
  return visibleEngineAdapters().map(adapter => adapter.id).map(backend => {
    const cap = model.backends?.[backend] || {};
    const support = resolvedClientSupport(backend, state.client, model);
    const routeReasoning = cap[state.client === "codex" ? "codexReasoning" : "agentReasoning"] || ["auto"];
    const benchmarkReasoning = cap.agentReasoning || ["auto"];
    let reason = "";
    const binaryKey = binaryKeys[backend] || ({omlx:"omlx", lmstudio:"lms", mtplx:"mtplx", freetoken:"freetoken"})[backend];
    if (!state.binaries?.[binaryKey]?.installed) reason = "Runtime not installed";
    else if (!model.ready || !cap.runnable) reason = cap.reason || "Model is not runnable";
    else if (!support?.supported) reason = support?.reason || "Work surface unsupported";
    else if (state.client === "chat" && $("samplingMode").value === "custom" && cap.customSampling === false) {
      reason = cap.samplingReason || "Cannot preserve custom sampling";
    }
    else if (backend === "freetoken") {
      reason = cap.native === true
        ? "Native FreeToken is greedy-only, so cross-engine sampling is not comparable yet"
        : "Connected FreeToken performance includes another host and network path";
    }
    else if (!routeReasoning.includes(reasoning) || !benchmarkReasoning.includes(reasoning)) reason = "Cannot preserve this reasoning level";
    else if (!kvChoices[backend].includes(kv) || (kv !== "off" && !cap.kv)) reason = "Cannot preserve this KV precision";
    return {
      backend, label:backendName(backend), eligible:!reason, reason,
      modes:benchmarkCandidates(cap, backend),
    };
  });
}

function benchmarkWinnerLabel(winner) {
  return ({ar:"AR", mtp:"MTP", dflash2:"DFlash 2"})[winner] || winner || "Unknown";
}

function renderBenchmarkCard() {
  const model = selectedModel();
  const cap = model?.backends?.[state.backend] || {};
  const candidates = model ? benchmarkCandidates(cap) : [];
  const benchmark = cap.localBenchmark;
  const badge = $("benchmarkCardBadge");
  $("benchmarkCardModes").innerHTML = candidates.map(mode => `<span class="${mode.available ? "available" : ""}${benchmark?.winner === mode.id ? " winner" : ""}">${esc(mode.label)}</span>`).join("");
  if (!model) {
    badge.textContent = "No model";
    $("benchmarkCardSummary").textContent = "Select a runnable model to inspect its measurable acceleration routes.";
    $("openBenchmarkButton").disabled = true;
    return;
  }
  if (state.backend === "freetoken" && freeTokenRoute(model) === "remote") {
    badge.textContent = "Live TPS";
    $("benchmarkCardSummary").textContent = "Chat and Hub Console show the connected route's live TPS. Remote-host and network performance stay outside the Mac-only Benchmark Lab.";
    $("openBenchmarkButton").disabled = true;
    return;
  }
  if (state.backend === "freetoken" && freeTokenRoute(model) === "native") {
    badge.textContent = "Native TPS";
    $("benchmarkCardSummary").textContent = "Chat shows native prefill and generation TPS live. The current greedy-only port stays out of cross-engine comparisons until it can preserve the same sampling contract.";
    $("openBenchmarkButton").disabled = true;
    return;
  }
  $("openBenchmarkButton").disabled = false;
  if (benchmark) {
    const historyCount = Number(cap.benchmarkHistoryCount || 1);
    badge.textContent = historyCount > 1 ? `${historyCount} saved` : "Measured";
    $("benchmarkCardSummary").textContent = `${benchmarkWinnerLabel(benchmark.winner)} won the newest saved local ${benchmark.suite || ""} run for this artifact and runtime. Apply fastest rechecks the complete visible contract; open Benchmark Lab for exact history.`.trim();
  } else if (candidates.length > 1) {
    badge.textContent = "Ready";
    $("benchmarkCardSummary").textContent = `${candidates.map(mode => mode.label).join(" vs ")} can be measured on this exact runtime/model route.`;
  } else {
    badge.textContent = "AR only";
    $("benchmarkCardSummary").textContent = "No verified acceleration competitor is available for this exact route yet.";
  }
}

function renderBenchmarkSetup() {
  const model = selectedModel();
  const cap = model?.backends?.[state.backend] || {};
  const candidates = model ? benchmarkCandidates(cap) : [];
  const engineRoutes = engineShootoutRoutes(model);
  const eligibleEngines = engineRoutes.filter(route => route.eligible);
  const suite = $("benchmarkSuiteSelect").value;
  const agentic = suite === "agentic";
  $("benchmarkRoute").textContent = model
    ? `${backendName(state.backend)} · ${model.name} · ${agentic ? "agent-shaped" : "prompt-range"} evidence bound to ${clientName(state.client)}`
    : "Choose a runnable model and acceleration route.";
  $("benchmarkModes").innerHTML = candidates.map(mode => `<span class="${mode.available ? "available" : ""}">${esc(mode.label)}</span>`).join("");
  $("benchmarkEngineStrip").innerHTML = engineRoutes.map(route => {
    const routeModes = route.modes.map(mode => mode.label).join(" + ");
    const detail = route.eligible ? routeModes : route.reason;
    return `<span class="${route.eligible ? "available" : "excluded"}" title="${esc(detail)}"><i aria-hidden="true">${route.eligible ? "✓" : "×"}</i><b>${esc(route.label)}</b><small>${esc(detail)}</small></span>`;
  }).join("");
  const remoteEngine = state.backend === "freetoken" && freeTokenRoute(model) === "remote";
  const nativeFreeToken = state.backend === "freetoken" && freeTokenRoute(model) === "native";
  const freeTokenExcluded = remoteEngine || nativeFreeToken;
  const comparable = Boolean(model && cap.runnable && candidates.length > 1 && !freeTokenExcluded);
  const suiteRequirement = ({quick:2688, standard:8960, thorough:33792, agentic:16384})[suite] || 2688;
  const visibleContext = Number($("contextInput").value);
  const contextEnough = Number.isFinite(visibleContext) && visibleContext >= suiteRequirement;
  const runnable = comparable && contextEnough;
  const shootoutRunnable = Boolean(model && eligibleEngines.length >= 2 && contextEnough);
  const shootoutRoutes = eligibleEngines.reduce((sum, route) => sum + route.modes.length, 0);
  const stepsPerRoute = ({agentic:6, quick:4, standard:6, thorough:8})[suite] || 4;
  const active = ["queued","cooldown","starting","running","stopping"].includes(state.benchmarkPhase);
  const runActive = ["preflight","starting","running","stopping"].includes(state.runPhase);
  const setupActive = ["queued","downloading","stopping","verifying"].includes(state.setupPhase);
  const acquisitionActive = acquisitionIsActive();
  const routeCheckActive = routeCheckIsActive();
  const aneActive = aneWorkIsActive();
  const operationBlocked = active || setupActive || acquisitionActive || routeCheckActive || aneActive || (runActive && !active);
  const mtpTunerVisible = Boolean(model && state.backend === "lmstudio" && cap.mtp);
  const mtpTunerRunnable = Boolean(mtpTunerVisible && cap.runnable && cap.mtpRuntimeVerified && contextEnough);
  const dflashTunerVisible = Boolean(model && state.backend === "omlx" && cap.dflash);
  const dflashTunerRunnable = Boolean(
    dflashTunerVisible && cap.runnable && cap.dflashReadiness?.runtimeRecommended && contextEnough
  );
  $("benchmarkStartButton").disabled = !runnable || operationBlocked;
  $("benchmarkShootoutButton").disabled = !shootoutRunnable || operationBlocked;
  $("benchmarkMtpTuner").classList.toggle("hidden", !mtpTunerVisible);
  $("benchmarkMtpTuneButton").disabled = !mtpTunerRunnable || operationBlocked;
  $("benchmarkDflashTuner").classList.toggle("hidden", !dflashTunerVisible);
  $("benchmarkDflashTuneButton").disabled = !dflashTunerRunnable || operationBlocked;
  $("benchmarkStopButton").disabled = !active;
  if (mtpTunerVisible) {
    const depth = Math.max(1, Number($("depthInput").value || cap.depth || 1));
    const minimum = Math.max(0, Math.min(depth, Number($("mtpMinTokensInput").value || 0)));
    const cutoff = Math.max(0, Math.min(1, Number($("mtpMinContinueProbabilityInput").value || 0)));
    $("benchmarkMtpTunerSummary").textContent = cap.mtpRuntimeVerified
      ? `Starts at max ${depth}, min ${minimum}, cutoff ${cutoff.toFixed(2)} · up to 11 fresh loads · up to ${11 * stepsPerRoute} generated requests.`
      : (cap.mtpReason || "This exact model/runtime MTP load path has not been verified.");
  }
  if (dflashTunerVisible) {
    const block = Math.max(1, Math.min(Number(cap.dflashMaxBlockSize || 1), Number($("depthInput").value || cap.dflashBlockSize || 1)));
    const verifier = $("dflashVerifySelect").value || "adaptive";
    const quant = $("dflashDraftQuantSelect").value || "native";
    const referenceLoads = 1 + (cap.mtp ? 1 : 0);
    const maximumLoads = referenceLoads + 10;
    $("benchmarkDflashTunerSummary").textContent = cap.dflashReadiness?.runtimeRecommended
      ? `Starts at block ${block}, ${verifier}, ${quant} · up to ${maximumLoads} fresh loads · up to ${maximumLoads * stepsPerRoute} generated requests.`
      : `The bounded tuner requires ${cap.dflashReadiness?.recommendedRuntime || "the recommended oMLX DFlash build"}; ordinary manual benchmarking remains available.`;
  }
  $("benchmarkContract").textContent = remoteEngine
    ? "FreeToken is a connected server route. Use live TPS for this path; Mac-only engine evidence never mixes in network and remote-host performance."
    : nativeFreeToken
    ? "Native FreeToken reports live local TPS, but this greedy-only milestone cannot yet preserve Benchmark Lab's cross-engine sampling contract."
    : acquisitionActive
    ? "Model Acquisition owns the pinned download and verification until it finishes or is stopped."
    : setupActive
    ? "Setup Assistant owns the model download until it finishes or is stopped."
    : routeCheckActive
      ? "Route Check owns the temporary model until its synthetic probes finish or are stopped."
    : aneActive
      ? "ANE Tuner owns the private model engine until its measurement finishes or is stopped."
    : !comparable
    ? "This route needs at least one verified acceleration competitor before it can be benchmarked."
    : !contextEnough
      ? `This suite needs at least ${formatNumber(suiteRequirement)} context tokens; the visible context is ${formatNumber(visibleContext)}.`
      : agentic
        ? `Uses the visible ${formatNumber(visibleContext)} context and four growing turns with the exact ${$("reasoningSelect").value} reasoning, sampling, KV, and tuning contract.`
        : `Uses the visible ${formatNumber(visibleContext)} context, ${$("reasoningSelect").value} reasoning, sampling, KV, and tuning controls.`;
  $("benchmarkShootoutLabel").textContent = eligibleEngines.length >= 2
    ? `${eligibleEngines.length} engines · ${shootoutRoutes} routes · ${shootoutRoutes * stepsPerRoute} measured steps`
    : "Needs at least two contract-compatible engines";
  $("benchmarkScenarioStrip").classList.toggle("hidden", !agentic);
}

function updateAccelerationState() {
  const cap = selectedModel()?.backends?.[state.backend] || {};
  const mode = $("accelerationSelect").value;
  const relevant = (mode === "mtp" && cap.mtp) || (mode === "dflash" && cap.dflash);
  $("depthInput").disabled = !relevant;
  $("depthLabel").textContent = mode === "dflash" ? "DFlash block size" : (mode === "mtp" ? "MTP draft depth" : "Speculative depth");
  $("depthHelp").textContent = relevant
    ? (mode === "dflash" ? "Tokens drafted and verified per DFlash cycle." : "Maximum tokens proposed per MTP verification cycle.")
    : "Depth is inactive until a verified speculative route is selected.";
  const dflashActive = state.backend === "omlx" && mode === "dflash" && cap.dflash;
  $("dflashVerifySelect").disabled = !dflashActive;
  $("dflashDraftQuantSelect").disabled = !dflashActive;
  $("dflashTuning").classList.toggle("inactive", !dflashActive);
  const lmstudioMtpActive = state.backend === "lmstudio" && mode === "mtp" && cap.mtp;
  const mtpMinimum = $("mtpMinTokensInput");
  mtpMinimum.max = String(Math.max(0, Number($("depthInput").value || 1)));
  if (Number(mtpMinimum.value) > Number(mtpMinimum.max)) mtpMinimum.value = mtpMinimum.max;
  mtpMinimum.disabled = !lmstudioMtpActive;
  $("mtpMinContinueProbabilityInput").disabled = !lmstudioMtpActive;
  $("lmstudioMtpTuning").classList.toggle("inactive", !lmstudioMtpActive);
  setRangeVisual(mtpMinimum);
  setRangeVisual($("mtpMinContinueProbabilityInput"));
}

function updateChatSamplingControls() {
  const capability = selectedModel()?.backends?.[state.backend] || {};
  const customSupported = capability.customSampling !== false;
  const customOption = $("samplingMode").querySelector('option[value="custom"]');
  if (customOption) customOption.disabled = !customSupported;
  if (!customSupported && $("samplingMode").value === "custom") $("samplingMode").value = "model";
  const custom = $("samplingMode").value === "custom";
  $("chatSettings").classList.toggle("sampling-defaults", !custom);
  document.querySelectorAll(".chat-sampler").forEach(field => field.classList.toggle("inactive", !custom));
  for (const id of [
    "temperatureInput", "topPInput", "topKInput", "presencePenaltyInput",
    "frequencyPenaltyInput", "seedInput",
  ]) $(id).disabled = !custom;
  if (!customSupported) {
    $("samplingHelp").textContent = capability.samplingReason || "This route uses fixed runtime decoding.";
  } else if (!custom) {
    const defaults = selectedModel()?.defaultSampling || {};
    const parts = [];
    if (defaults.temperature !== undefined) parts.push(`temperature ${defaults.temperature}`);
    if (defaults.top_p !== undefined) parts.push(`top P ${defaults.top_p}`);
    if (defaults.top_k !== undefined) parts.push(`top K ${defaults.top_k}`);
    $("samplingHelp").textContent = parts.length ? `Detected defaults: ${parts.join(" · ")}.` : "The runtime uses this model's generation defaults.";
  } else {
    $("samplingHelp").textContent = "These request values override the model defaults for every turn.";
  }
  const presence = Number($("presencePenaltyInput").value || 0);
  const frequency = Number($("frequencyPenaltyInput").value || 0);
  const seed = $("seedInput").value.trim();
  const penaltyLabel = presence === 0 && frequency === 0
    ? "Penalties off" : `Presence ${presence} · frequency ${frequency}`;
  $("chatSamplingAdvancedSummary").textContent = custom
    ? `${penaltyLabel} · ${seed ? `seed ${seed}` : "random seed"}`
    : "Available with custom sampling";
}

function warmRouteRequestSignature(request = null) {
  try {
    const visible = request || gather("custom", false);
    return JSON.stringify({
      ownerRunId:state.runStatus?.run?.runId || "",
      request:visible,
    });
  } catch (_) { return ""; }
}

function currentWarmRoutePlan() {
  if (state.runPhase !== "running" || !state.warmRoutePlan) return null;
  const signature = warmRouteRequestSignature();
  if (!signature || signature !== state.warmRouteSignature) return null;
  if (state.warmRoutePlan.ownerRunId !== state.runStatus?.run?.runId) return null;
  return state.warmRoutePlan;
}

function clearWarmRoutePlan() {
  if (state.warmRouteTimer) clearTimeout(state.warmRouteTimer);
  state.warmRouteTimer = null;
  state.warmRoutePlan = null;
  state.warmRouteSignature = "";
  state.warmRoutePendingSignature = "";
  state.warmRouteLoading = false;
}

function scheduleWarmRoutePlan(immediate = false) {
  if (state.runPhase !== "running" || !state.runStatus?.run || state.runStatus.run.purpose !== "session") {
    if (state.warmRoutePlan || state.warmRouteTimer || state.warmRouteSignature) clearWarmRoutePlan();
    return;
  }
  const signature = warmRouteRequestSignature();
  if (!signature) {
    state.warmRoutePlan = null;
    state.warmRouteSignature = "";
    return;
  }
  if (signature === state.warmRouteSignature && state.warmRoutePlan) return;
  if (state.warmRouteLoading || (state.warmRouteTimer && signature === state.warmRoutePendingSignature)) return;
  if (state.warmRouteTimer) clearTimeout(state.warmRouteTimer);
  state.warmRoutePlan = null;
  state.warmRouteSignature = "";
  state.warmRoutePendingSignature = signature;
  state.warmRouteTimer = setTimeout(() => {
    state.warmRouteTimer = null;
    void loadWarmRoutePlan();
  }, immediate ? 0 : 220);
}

async function loadWarmRoutePlan(force = false) {
  if (state.runPhase !== "running" || !state.runStatus?.run) return null;
  let request;
  try { request = gather("custom", false); }
  catch (_) {
    state.warmRoutePlan = null;
    state.warmRouteSignature = "";
    refreshLaunchability();
    return null;
  }
  const signature = warmRouteRequestSignature(request);
  if (!force && signature === state.warmRouteSignature && state.warmRoutePlan) return state.warmRoutePlan;
  const generation = ++state.warmRouteGeneration;
  state.warmRouteLoading = true;
  state.warmRoutePendingSignature = signature;
  try {
    const data = await api("/api/session/warm-plan", {method:"POST", body:JSON.stringify(request)});
    if (generation !== state.warmRouteGeneration || signature !== warmRouteRequestSignature()) return null;
    state.warmRoutePlan = data.warmRoute;
    state.warmRouteSignature = signature;
    if (state.sessionDashboard) state.sessionDashboard.warmRoute = data.warmRoute;
    return data.warmRoute;
  } catch (error) {
    if (generation === state.warmRouteGeneration) {
      state.warmRoutePlan = {
        state:"unavailable", canAttach:false,
        ownerRunId:state.runStatus?.run?.runId || null,
        detail:error.message,
      };
      state.warmRouteSignature = signature;
    }
    return null;
  } finally {
    if (generation === state.warmRouteGeneration) {
      state.warmRouteLoading = false;
      state.warmRoutePendingSignature = "";
      refreshLaunchability();
      if ($("sessionDialog")?.open) renderSessionDashboard();
    }
  }
}

function updateWorkSurface() {
  const chat = state.client === "chat";
  const freeTokenMode = state.backend === "freetoken" ? freeTokenRoute() : "unavailable";
  const warm = currentWarmRoutePlan();
  $("chatSettings").classList.toggle("hidden", !chat);
  $("agentHostSettings").classList.toggle("hidden", chat);
  $("projectLabel").textContent = chat ? "Working folder" : "Project folder";
  $("launchLabel").textContent = warm?.canAttach
    ? (warm.action?.label || (chat ? "Open warm chat" : `Open ${clientName(state.client)}`))
    : chat ? "Start chat" : "Launch";
  if (warm?.canAttach) {
    $("launchSummary").textContent = `Reuse loaded ${backendName(warm.loadedRoute?.backend || state.backend)} · no model reload`;
  } else if (state.runPhase === "running" && state.warmRouteLoading) {
    $("launchSummary").textContent = "Checking the loaded route…";
  } else $("launchSummary").textContent = state.optimalLabel || "Current visible settings";
  $("configSubtitle").textContent = freeTokenMode === "remote"
      ? (chat ? "Choose a connected FreeToken model for private bridged chat." : "Choose a connected FreeToken model and work surface.")
      : freeTokenMode === "native" || (state.backend === "freetoken" && state.freeToken?.native?.installed)
        ? "Choose a compatible checkpoint for launcher-owned native FreeToken Chat."
        : (chat ? "Choose a runtime and model for a private local chat." : "Choose a runtime, model and work surface.");
  document.querySelectorAll("[data-client]").forEach(button => {
    button.classList.toggle("selected", button.dataset.client === state.client);
  });
  updateChatSamplingControls();
}

function refreshLaunchability() {
  const selected = selectedModel();
  const allowedReasoning = reasoningChoices();
  [...$("reasoningSelect").options].forEach(option => { option.disabled = !allowedReasoning.includes(option.value); });
  document.querySelectorAll("[data-backend]").forEach(button => {
    if (!uiEngineVisible(button.dataset.backend)) {
      button.hidden = true;
      button.disabled = true;
      button.setAttribute("aria-disabled", "true");
      button.setAttribute("aria-pressed", "false");
      return;
    }
    const key = button.dataset.backend === "lmstudio" ? "lms" : button.dataset.backend;
    const installed = Boolean(state.binaries?.[key]?.installed);
    const connectable = button.dataset.backend === "freetoken";
    const unavailable = (!installed && !connectable) || state.applyingOptimal;
    button.disabled = unavailable;
    button.setAttribute("aria-disabled", String(unavailable));
    button.setAttribute("aria-pressed", String(button.dataset.backend === state.backend));
    button.classList.toggle("disabled", unavailable);
    button.classList.toggle("disconnected", connectable && !installed);
    if (connectable) button.title = installed
      ? state.freeToken?.connected && state.freeToken?.native?.installed
        ? "Native FreeToken and a connected server are available"
        : state.freeToken?.native?.installed
          ? "Native FreeToken port detected"
          : "Connected FreeToken server"
      : "Select to set up FreeToken";
  });
  document.querySelectorAll("[data-client]").forEach(button => {
    const support = resolvedClientSupport(state.backend, button.dataset.client, selected);
    const installed = clientInstalled(button.dataset.client);
    const unavailable = !support?.supported || !installed;
    button.disabled = unavailable;
    button.setAttribute("aria-disabled", String(unavailable));
    button.setAttribute("aria-pressed", String(button.dataset.client === state.client));
    button.classList.toggle("unsupported", unavailable);
    button.title = !installed ? "Not installed" : (support?.reason || "Compatibility is unknown");
  });
  const model = selected;
  const client = clientAvailability();
  const runtimeKey = state.backend === "lmstudio" ? "lms" : state.backend;
  const runtimeReady = Boolean(state.binaries?.[runtimeKey]?.installed);
  const limits = limitError();
  const chatError = chatSettingsError();
  const freeTokenError = freeTokenSettingsError();
  const runActive = ["preflight","starting","running","stopping"].includes(state.runPhase);
  const routeCheckActive = ["queued","starting","running","stopping"].includes(state.routeCheckPhase);
  const benchmarkActive = ["queued","cooldown","starting","running","stopping"].includes(state.benchmarkPhase);
  const setupActive = ["queued","downloading","stopping","verifying"].includes(state.setupPhase);
  const acquisitionActive = acquisitionIsActive();
  const aneActive = aneWorkIsActive();
  const runtimeControlError = state.backend === "omlx" && $("accelerationSelect").value === "dflash" && $("anePrefillSelect").value === "tuned"
    ? "DFlash 2 and tuned ANE prefill cannot run in the same oMLX engine. Choose one."
    : "";
  const modelReady = Boolean(model?.backends[state.backend].runnable && model?.ready);
  const warm = currentWarmRoutePlan();
  const controlsReady = Boolean(runtimeReady && modelReady && client.available && !limits && !chatError && !freeTokenError && !runtimeControlError && !state.applyingOptimal && !state.verifiedLaunchBusy && !state.profileBusy && !state.calibrationApplying && !routeCheckActive && !benchmarkActive && !setupActive && !acquisitionActive && !aneActive);
  const coldLaunchable = Boolean(controlsReady && !runActive);
  const warmLaunchable = Boolean(controlsReady && state.runPhase === "running" && warm?.canAttach);
  const launchable = coldLaunchable || warmLaunchable;
  $("launchButton").disabled = !launchable;
  $("launchButton").dataset.warm = warmLaunchable ? "true" : "false";
  $("routeCheckButton").disabled = !coldLaunchable;
  $("previewButton").disabled = !coldLaunchable;
  $("applyOptimal").disabled = !coldLaunchable;
  $("optimizerMenuButton").disabled = !coldLaunchable;
  $("optimizerVerifiedLaunch").disabled = !coldLaunchable;
  $("optimizerCalibrate").disabled = !coldLaunchable;
  document.querySelectorAll("[data-optimizer-scope]").forEach(button => { button.disabled = !coldLaunchable; });
  if (!coldLaunchable) closeOptimizerMenu();
  const supportEntries = (state.adapters?.workSurfaces || []).map(
    adapter => [adapter.id, resolvedClientSupport(state.backend, adapter.id, selected)],
  );
  const unsupported = supportEntries
    .filter(([name, support]) => !support.supported || !clientInstalled(name))
    .map(([name, support]) => `${clientName(name)} unavailable: ${clientInstalled(name) ? support.reason : "not installed"}`);
  const selectedReason = resolvedClientSupport(state.backend, state.client, selected).reason || "Compatible local route";
  const compatibilityDetail = [selectedReason, ...unsupported].join(" · ");
  $("compatibilityLine").textContent = activeDetail() === "detailed" ? compatibilityDetail : selectedReason;
  $("compatibilityLine").title = compatibilityDetail;
  let blocker = "";
  if (!runtimeReady) blocker = state.backend === "freetoken"
    ? "Install the native FreeToken port or connect a server."
    : `${state.backend === "lmstudio" ? "LM Studio" : state.backend} is not installed.`;
  else if (!model) blocker = state.backend === "freetoken" && state.freeToken?.native?.installed
    ? "Native FreeToken is installed, but no compatible local Qwen3-MoE checkpoint passed preflight."
    : "No ready model is available for this runtime.";
  else if (!model.backends[state.backend].runnable) blocker = model.backends[state.backend].reason;
  else if (!client.available) blocker = client.reason;
  else if (!model.ready) blocker = model.status;
  else if (limits) blocker = limits;
  else if (chatError) blocker = chatError;
  else if (freeTokenError) blocker = freeTokenError;
  else if (runtimeControlError) blocker = runtimeControlError;
  else if (acquisitionActive) blocker = "Model Acquisition owns the pinned download and verification until it finishes or is stopped.";
  else if (setupActive) blocker = "Setup Assistant owns the model download until it finishes or is stopped.";
  else if (routeCheckActive) blocker = "Route Check owns the temporary model until its synthetic probes finish or are stopped.";
  else if (benchmarkActive) blocker = "Benchmark Lab owns the model runtime until its comparison finishes or is stopped.";
  else if (aneActive) blocker = aneCloneIsActive()
    ? "FP16 copy preparation owns its private staging folder until it finishes or is stopped."
    : "ANE Tuner owns the private model engine until it finishes or is stopped.";
  else if (runActive && state.runPhase === "running" && warmLaunchable) blocker = "";
  else if (runActive && state.runPhase === "running" && state.warmRouteLoading) blocker = "Checking whether the visible controls exactly match the loaded model route…";
  else if (runActive && state.runPhase === "running") blocker = warm?.detail || "The visible route does not exactly match the loaded model. Open Sessions for details or stop it before loading another.";
  else if (runActive) blocker = "Wait for the active route transition to finish.";
  showNotice(blocker || state.catalogNotice, Boolean(blocker));
  updateAccelerationState();
  scheduleWarmRoutePlan();
  updateWorkSurface();
  renderBenchmarkSetup();
  updateSetupControls();
  updateAcquisitionControls();
  updateAneControls();
  renderPerformanceReceipt();
  renderQuickStart();
  if ($("profileDialog")?.open) renderProfiles();
  if ($("calibrationDialog")?.open) renderCalibration();
  if ($("routeCheckDialog")?.open) renderRouteCheck();
}

function updateBackend(preserveOptimization = false) {
  if (!uiEngineVisible(state.backend)) state.backend = "mtplx";
  if (!preserveOptimization) cancelOptimization("Runtime changed; review or apply its recommended controls.");
  document.querySelectorAll("[data-backend]").forEach(button => button.classList.toggle("selected", button.dataset.backend === state.backend));
  $("mtplxControls").classList.toggle("hidden", state.backend !== "mtplx");
  $("omlxControls").classList.toggle("hidden", state.backend !== "omlx");
  $("lmstudioControls").classList.toggle("hidden", state.backend !== "lmstudio");
  $("freetokenControls").classList.toggle("hidden", state.backend !== "freetoken");
  $("sharedRuntimeControls").classList.toggle("hidden", state.backend === "freetoken");
  $("advancedSummary").textContent = ({mtplx:"MTPLX controls", omlx:"oMLX controls", lmstudio:"LM Studio controls", freetoken:"FreeToken route controls"})[state.backend];
  renderFreeTokenConnection();
  renderModelOptions();
}

function renderModelOptions() {
  const select = $("modelSelect");
  const previous = select.value;
  if (!uiEngineVisible(state.backend)) state.backend = "mtplx";
  const visibleModels = state.models.filter(uiModelVisible);
  const compatible = visibleModels.filter(model => model.backends[state.backend].runnable);
  const unavailable = visibleModels.filter(model => !model.backends[state.backend].runnable);
  const option = (model, disabled = false) => `<option value="${esc(model.id)}" ${disabled ? "disabled" : ""}>${esc(model.name)}${disabled ? ` — ${esc(model.backends[state.backend].reason || model.status)}` : ""}</option>`;
  if (state.backend === "freetoken") {
    const native = compatible.filter(model => freeTokenRoute(model) === "native");
    const remote = compatible.filter(model => freeTokenRoute(model) === "remote");
    const groups = [
      native.length ? `<optgroup label="Native on this Mac">${native.map(model => option(model)).join("")}</optgroup>` : "",
      remote.length ? `<optgroup label="Connected FreeToken server">${remote.map(model => option(model)).join("")}</optgroup>` : "",
    ].join("");
    select.innerHTML = groups || `<option value="">${state.freeToken?.native?.installed ? "Native port detected — no compatible local Qwen3-MoE checkpoint" : "Install the native port or connect a FreeToken server"}</option>`;
  } else select.innerHTML = compatible.length
    ? `<optgroup label="Ready for ${state.backend}">${compatible.map(model => option(model)).join("")}</optgroup>${unavailable.length ? `<optgroup label="Detected but unavailable">${unavailable.map(model => option(model, true)).join("")}</optgroup>` : ""}`
    : `<option value="">No ready models for this runtime</option>${unavailable.map(model => option(model, true)).join("")}`;
  if (compatible.some(model => model.id === previous)) select.value = previous;
  else if (state.backend === "mtplx") {
    const qwen = compatible.find(model => /qwen3\.8.*optimized-speed/i.test(model.name));
    if (qwen) select.value = qwen.id;
  }
  modelChanged();
}

function applyModelChatDefaults(model) {
  if (!model || state.chatDefaultsModelId === model.id) {
    updateChatSamplingControls();
    return;
  }
  state.chatDefaultsModelId = model.id;
  const defaults = model.defaultSampling || {};
  $("temperatureInput").value = String(defaults.temperature ?? 0.7);
  $("topPInput").value = String(defaults.top_p ?? 1);
  $("topKInput").value = String(defaults.top_k ?? 0);
  $("presencePenaltyInput").value = String(defaults.presence_penalty ?? 0);
  $("frequencyPenaltyInput").value = String(defaults.frequency_penalty ?? 0);
  $("seedInput").value = "";
  updateChatSamplingControls();
}

function modelChanged() {
  const model = selectedModel();
  const previousId = state.selected?.id || "";
  if (previousId && previousId !== (model?.id || "")) {
    cancelOptimization("Model changed; reapply the speed preset for this artifact.");
  }
  state.selected = model;
  const card = $("modelCard");
  if (!model) {
    const freeTokenMissing = state.backend === "freetoken";
    card.innerHTML = freeTokenMissing
      ? state.freeToken?.native?.installed
        ? `<div class="model-title"><strong>No compatible native checkpoint</strong><span class="badge bad">Inspect</span></div><div class="model-meta"><span>The port is ready, but no complete local Qwen3-MoE checkpoint passed its fail-closed preflight. A remote server remains optional.</span></div>`
        : `<div class="model-title"><strong>FreeToken is unavailable</strong><span class="badge bad">Set up</span></div><div class="model-meta"><span>Install the native port or configure a server above.</span></div>`
      : `<div class="model-title"><strong>No launchable model</strong><span class="badge bad">Unavailable</span></div><div class="model-meta"><span>Try another runtime or finish the model download</span></div>`;
    updateFreeTokenNativeControls();
    renderDflashReadiness({});
    renderAneReadiness({});
    renderBenchmarkCard();
    refreshLaunchability();
    schedulePerformanceReceipt();
    persistVisibleRoute();
    return;
  }
  const cap = model.backends[state.backend];
  updateFreeTokenNativeControls();
  applyModelChatDefaults(model);
  card.classList.remove("loading");
  const experimentalFreeToken = state.backend === "freetoken"
    && freeTokenRoute(model) === "native" && freeTokenQualification(model).experimental;
  const statusClass = experimentalFreeToken ? "warning" : model.ready ? "good" : "bad";
  const statusLabel = experimentalFreeToken ? "Experimental" : model.status;
  card.innerHTML = `<div class="model-title"><strong>${esc(model.name)}</strong><span class="badge ${statusClass}">${esc(statusLabel)}</span></div><div class="model-meta"><span>${esc(model.format.toUpperCase())}</span><span>${esc(model.quantization)}</span><span>${esc(model.sizeLabel)}</span><span>${formatNumber(model.nativeContext || 0)} context</span><span>${esc(model.origins.join(" + "))}</span><span>${esc(cap.reason)}</span></div>`;
  if (model.nativeContext) $("contextInput").max = model.nativeContext;
  else $("contextInput").removeAttribute("max");
  const acceleration = $("accelerationSelect");
  [...acceleration.options].forEach(option => { option.disabled = false; });
  const mtp = acceleration.querySelector('option[value="mtp"]');
  const dflash = acceleration.querySelector('option[value="dflash"]');
  mtp.disabled = !cap.mtp;
  dflash.disabled = !cap.dflash;
  if ((acceleration.value === "mtp" && !cap.mtp) || (acceleration.value === "dflash" && !cap.dflash)) acceleration.value = "auto";
  if (cap.mtp || cap.dflash) {
    $("depthInput").max = String(Math.max(1, Number(cap.depthMax || 1)));
    if (Number($("depthInput").value) > Number($("depthInput").max)) $("depthInput").value = String(cap.depth || 1);
  } else $("depthInput").max = "8";
  setRangeVisual($("depthInput"), $("depthValue"));
  const available = [cap.mtp ? "MTP" : "", cap.dflash ? "DFlash 2" : ""].filter(Boolean);
  $("accelerationHelp").textContent = available.length ? `${available.join(" and ")} available for this exact runtime/model route.` : cap.mtpReason || "No verified speculative path.";
  renderDflashReadiness(cap);
  renderAneReadiness(cap);
  renderBenchmarkCard();
  refreshLaunchability();
  schedulePerformanceReceipt();
  persistVisibleRoute();
}

async function loadModels(userTriggered = false) {
  if (userTriggered) cancelOptimization("Model capabilities were rescanned; reapply the current speed preset.");
  $("refreshModels").disabled = true;
  $("refreshModels").querySelector("strong").textContent = "Scanning models…";
  $("refreshModels").querySelector("small").textContent = "Refreshing configured model folders.";
  try {
    const data = await api("/api/models");
    state.models = data.models;
    state.modelLibrary = null;
    const incompleteOrnith = state.models.find(model => /ornith/i.test(model.name) && !model.ready);
    state.catalogNotice = incompleteOrnith ? `${incompleteOrnith.name} is detected but still downloading. It becomes selectable after every weight shard finishes.` : "";
    renderModelOptions();
    if (state.quickStartLoaded) void loadQuickStart(true);
  } catch (error) { showNotice(error.message, true); }
  finally {
    $("refreshModels").disabled = false;
    $("refreshModels").querySelector("strong").textContent = "Rescan models";
    $("refreshModels").querySelector("small").textContent = "Refresh configured model folders.";
  }
}

function freeTokenEndpointLabel(connection = state.freeToken || {}) {
  if (!connection.endpoint) return "";
  try { return new URL(connection.endpoint).host; }
  catch (_) { return String(connection.endpoint); }
}

function freeTokenSettingsError() {
  if (state.backend !== "freetoken" || freeTokenRoute() !== "native") return "";
  const batch = Number($("freeTokenBatchSelect").value);
  const prefix = Number($("freeTokenPrefixCacheSelect").value);
  const expertText = $("freeTokenExpertCacheInput").value.trim();
  const expert = expertText === "" ? null : Number(expertText);
  const maximumExperts = Number(selectedModel()?.backends?.freetoken?.nativeExpertCount || 4096);
  if (!Number.isInteger(batch) || batch < 1 || batch > 16) return "Choose 1–16 active FreeToken sequences.";
  if (!Number.isInteger(prefix) || prefix < 0 || prefix > 128) return "Choose 0–128 FreeToken prefix-cache entries.";
  if (expert !== null && (!Number.isInteger(expert) || expert < 0 || expert > maximumExperts)) {
    return `Metal hot experts must be blank or a whole number from 0 to ${formatNumber(maximumExperts)}.`;
  }
  if (batch > 1 && prefix > 0) return "Native FreeToken cannot combine concurrent batching with prefix caching yet.";
  if (!freeTokenExperimentalConsentAccepted()) {
    return "Review and approve this synthetic-only experimental run first.";
  }
  return "";
}

function updateFreeTokenNativeControls() {
  const route = freeTokenRoute();
  const native = state.backend === "freetoken" && route === "native";
  const remote = state.backend === "freetoken" && route === "remote";
  $("freeTokenNativeControls").classList.toggle("hidden", !native);
  $("freeTokenRemoteControls").classList.toggle("hidden", !remote);
  const model = selectedModel();
  const capability = model?.backends?.freetoken || {};
  const qualification = freeTokenQualification(model);
  const qualificationPanel = $("freeTokenQualificationPanel");
  const consentPanel = $("freeTokenExperimentalConsentPanel");
  const consent = $("freeTokenExperimentalConsent");
  qualificationPanel.classList.toggle("hidden", !native);
  qualificationPanel.classList.toggle("qualified", native && qualification.qualified);
  if (!native || !qualification.experimental || consent.dataset.modelId !== String(model?.id || "")) {
    consent.checked = false;
    consent.dataset.modelId = "";
  }
  consentPanel.classList.toggle("hidden", !native || !qualification.experimental);
  if (native && qualification.qualified) {
    $("freeTokenQualificationMark").textContent = "✓";
    $("freeTokenQualificationTitle").textContent = "This exact real checkpoint is qualified";
    $("freeTokenQualificationDetail").textContent = "The port supplied runtime-owned serve and token-generation evidence tied to this checkpoint.";
  } else if (native && qualification.experimental) {
    $("freeTokenQualificationMark").textContent = "!";
    $("freeTokenQualificationTitle").textContent = "Experimental · synthetic path only";
    $("freeTokenQualificationDetail").textContent = "Tiny synthetic serving passed, but this real checkpoint has not. Use only an existing local model; no large download is recommended.";
  } else if (native) {
    $("freeTokenQualificationMark").textContent = "×";
    $("freeTokenQualificationTitle").textContent = "Checkpoint evidence unavailable";
    $("freeTokenQualificationDetail").textContent = "Rescan after updating the native port; unknown qualification receipts stay fail-closed.";
  }
  const maximumExperts = Math.max(0, Number(capability.nativeExpertCount || 4096));
  $("freeTokenExpertCacheInput").max = String(maximumExperts);
  const error = freeTokenSettingsError();
  const consentMissing = native && qualification.experimental && !freeTokenExperimentalConsentAccepted(model);
  const batch = Number($("freeTokenBatchSelect").value || 1);
  const prefix = Number($("freeTokenPrefixCacheSelect").value || 0);
  const expert = $("freeTokenExpertCacheInput").value.trim();
  $("freeTokenNativeControlStatus").textContent = error || [
    `${formatNumber(batch)} active sequence${batch === 1 ? "" : "s"}`,
    expert === "" ? "resident Metal experts" : `${formatNumber(expert)} hot Metal experts`,
    prefix ? `${formatNumber(prefix)} cached prefixes` : "prefix cache off",
  ].join(" · ");
  $("freeTokenNativeControlStatus").classList.toggle("error", Boolean(error) && !consentMissing);
  $("freeTokenNativeControlStatus").classList.toggle("warning", consentMissing);
}

function renderFreeTokenConnection(forceForm = false) {
  const connection = state.freeToken || {};
  const connected = connection.connected === true;
  const selected = state.backend === "freetoken";
  const route = freeTokenRoute();
  const native = route === "native";
  const qualification = freeTokenQualification();
  const nativeStatus = connection.native || {};
  const endpoint = freeTokenEndpointLabel(connection);
  const banner = $("freeTokenConnectionBanner");
  if (!uiFeatureEnabled("freetoken")) {
    banner.classList.add("hidden");
    banner.hidden = true;
    $("localChip").textContent = "Local only";
    $("localChip").classList.remove("connected");
    return;
  }
  banner.classList.toggle("hidden", !selected);
  banner.classList.toggle("connected", selected && route === "remote");
  banner.classList.toggle("native", selected && native);
  banner.classList.toggle("experimental", selected && native && qualification.experimental);
  if (native) {
    $("freeTokenConnectionTitle").textContent = "Native FreeToken · this Mac";
    const maturity = qualification.qualified
      ? "exact real checkpoint qualified"
      : qualification.experimental ? "experimental · synthetic-only evidence" : "qualification unavailable";
    $("freeTokenConnectionDetail").textContent = `${nativeStatus.version || connection.nativeVersion || "MLX/Metal port"} · ${maturity} · launcher-owned Stop`;
  } else if (connected) {
    $("freeTokenConnectionTitle").textContent = `Connected to ${endpoint || "FreeToken"}`;
    $("freeTokenConnectionDetail").textContent = `${formatNumber(connection.modelCount)} live model${Number(connection.modelCount) === 1 ? "" : "s"} · ${connection.transportEncrypted ? "encrypted HTTPS" : "HTTP transport"} · checked ${connection.checkedAt ? new Date(connection.checkedAt).toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"}) : "recently"}`;
  } else if (nativeStatus.installed) {
    $("freeTokenConnectionTitle").textContent = "Native FreeToken port detected";
    $("freeTokenConnectionDetail").textContent = "Choose a compatible local Qwen3-MoE checkpoint, or add an optional remote server.";
  } else {
    $("freeTokenConnectionTitle").textContent = "Connect a FreeToken server";
    $("freeTokenConnectionDetail").textContent = "Discover its live models, then use them with Chat, Pi, OpenCode, or Codex.";
  }
  const inspectNativeModels = selected && route === "unavailable" && nativeStatus.installed;
  $("openFreeTokenConnection").dataset.action = inspectNativeModels ? "models" : "remote";
  $("openFreeTokenConnection").textContent = inspectNativeModels
    ? "Review local models"
    : connected ? "Remote connection" : "Add remote server";
  $("localChip").textContent = selected && route === "remote" ? "Connected engine" : "Local only";
  $("localChip").classList.toggle("connected", selected && route === "remote");

  const dialog = $("freeTokenDialog");
  if (!dialog) return;
  $("freeTokenBadge").textContent = state.freeTokenBusy ? "Checking" : connected ? `${formatNumber(connection.modelCount)} models` : "Not connected";
  $("freeTokenBadge").className = `setup-badge ${connected ? "ready" : "warning"}`;
  $("freeTokenPlatform").textContent = connection.localInstallReason || "FreeToken's current local runtime targets Linux x86_64 with NVIDIA CUDA 13; this Mac uses it as a connected engine.";
  $("freeTokenDocsLink").href = connection.docsUrl || "https://github.com/FlashML-org/FreeToken/blob/main/docs/quickstart.md";
  $("freeTokenInstallLink").href = connection.installUrl || "https://github.com/FlashML-org/FreeToken/blob/main/docs/install.md";
  if (forceForm || !dialog.open) {
    $("freeTokenEndpoint").value = connected ? String(connection.endpoint || "") : $("freeTokenEndpoint").value;
    $("freeTokenContext").value = String(connection.context || 131072);
    $("freeTokenApiKey").value = "";
  }
  $("freeTokenApiKey").placeholder = connected && connection.hasApiKey ? "Saved key (leave blank to keep)" : "Optional";
  $("freeTokenApiKeyHelp").textContent = connected && connection.hasApiKey
    ? "A private key is saved locally. Leave this blank to keep it when reconnecting to the same address."
    : "Leave blank if the server has no key.";
  const summary = $("freeTokenConnectionSummary");
  summary.classList.toggle("connected", connected);
  summary.innerHTML = connected
    ? `<strong>${esc(connection.server || "FreeToken API")}</strong><span title="${esc((connection.models || []).join(", "))}">${esc((connection.models || []).join(" · "))}</span>`
    : "<strong>No server connected</strong><span>Add its private address to discover available models.</span>";
  $("freeTokenDisconnect").disabled = state.freeTokenBusy || !connected;
  $("freeTokenConnect").disabled = state.freeTokenBusy;
  $("freeTokenEndpoint").disabled = state.freeTokenBusy;
  $("freeTokenApiKey").disabled = state.freeTokenBusy;
  $("freeTokenContext").disabled = state.freeTokenBusy;
  updateFreeTokenNativeControls();
}

function openFreeTokenDialog() {
  if (!uiFeatureEnabled("freetoken")) return;
  renderFreeTokenConnection(true);
  if (!$("freeTokenDialog").open) $("freeTokenDialog").showModal();
  $("freeTokenStatus").className = "freetoken-status";
  $("freeTokenStatus").textContent = state.freeToken?.connected
    ? "Connection details are local to this launcher. Reconnect only when you want to refresh the live model catalog."
    : "Opening this window makes no network request.";
  if (!state.freeToken?.connected) $("freeTokenEndpoint").focus();
}

async function connectFreeToken(event) {
  event?.preventDefault?.();
  if (!uiFeatureEnabled("freetoken")) return;
  if (state.freeTokenBusy || !$("freeTokenForm").reportValidity()) return;
  state.freeTokenBusy = true;
  $("freeTokenStatus").className = "freetoken-status";
  $("freeTokenStatus").textContent = "Reading the server's standard model catalog…";
  renderFreeTokenConnection();
  try {
    const apiKey = $("freeTokenApiKey").value;
    const data = await api("/api/freetoken/connect", {
      method:"POST",
      body:JSON.stringify({
        endpoint:$("freeTokenEndpoint").value,
        apiKey,
        keepApiKey:apiKey === "" && Boolean(state.freeToken?.hasApiKey),
        context:Number($("freeTokenContext").value),
      }),
    });
    state.freeToken = data.freeToken;
    state.binaries = data.binaries || state.binaries;
    state.adapters = data.adapters || state.adapters;
    state.models = data.models || [];
    state.modelLibrary = null;
    state.backend = "freetoken";
    $("freeTokenStatus").textContent = `Connected. ${formatNumber(state.freeToken.modelCount)} model${Number(state.freeToken.modelCount) === 1 ? "" : "s"} discovered; no model was started or stopped.`;
    renderFreeTokenConnection(true);
    renderModelOptions();
    applyBootstrapData({binaries:state.binaries, adapters:state.adapters, freeToken:state.freeToken});
    schedulePerformanceReceipt();
  } catch (error) {
    $("freeTokenStatus").textContent = error.message;
    $("freeTokenStatus").className = "freetoken-status error";
  } finally {
    state.freeTokenBusy = false;
    renderFreeTokenConnection();
    refreshLaunchability();
  }
}

async function disconnectFreeToken() {
  if (!uiFeatureEnabled("freetoken")) return;
  if (state.freeTokenBusy || !state.freeToken?.connected) return;
  if (!window.confirm("Disconnect this launcher from FreeToken? The remote server and loaded model will keep running.")) return;
  state.freeTokenBusy = true;
  $("freeTokenStatus").className = "freetoken-status";
  $("freeTokenStatus").textContent = "Removing the launcher connection…";
  renderFreeTokenConnection();
  try {
    const data = await api("/api/freetoken/disconnect", {method:"POST", body:"{}"});
    state.freeToken = data.freeToken;
    state.binaries = data.binaries || state.binaries;
    state.adapters = data.adapters || state.adapters;
    state.models = data.models || [];
    state.modelLibrary = null;
    $("freeTokenStatus").textContent = "Launcher disconnected. The FreeToken server and its model were not stopped.";
    renderModelOptions();
    applyBootstrapData({binaries:state.binaries, adapters:state.adapters, freeToken:state.freeToken});
  } catch (error) {
    $("freeTokenStatus").textContent = error.message;
    $("freeTokenStatus").className = "freetoken-status error";
  } finally {
    state.freeTokenBusy = false;
    renderFreeTokenConnection(true);
    refreshLaunchability();
  }
}

function fieldForKey(key) {
  const control = $(optimizerControls[key]);
  return control?.closest(".optimizable") || null;
}

async function revealFirstChangedControl(keys) {
  const field = keys.map(fieldForKey).find(Boolean);
  const scroller = document.querySelector(".config-scroll");
  if (!field || !scroller) return;
  await new Promise(resolve => requestAnimationFrame(resolve));
  const fieldRect = field.getBoundingClientRect();
  const scrollRect = scroller.getBoundingClientRect();
  if (fieldRect.top >= scrollRect.top && fieldRect.bottom <= scrollRect.bottom) return;
  const delta = fieldRect.top < scrollRect.top
    ? fieldRect.top - scrollRect.top - 12
    : fieldRect.bottom - scrollRect.bottom + 12;
  scroller.scrollTo({top: scroller.scrollTop + delta, behavior: reducedMotion() ? "auto" : "smooth"});
}

function optimizerValueMatches(key, expected) {
  const control = $(optimizerControls[key]);
  if (!control) return false;
  if (expected === null || expected === undefined) return control.value === "";
  return control.type === "range"
    ? Number(control.value) === Number(expected)
    : control.value === String(expected);
}

async function animateRange(input, target, generation) {
  const start = Number(input.value), end = Number(target);
  if (!Number.isFinite(end)) return;
  const output = rangeOutputFor(input);
  if (reducedMotion() || start === end) {
    input.value = String(quantizedRangeValue(input, end));
    setRangeVisual(input, output);
    return;
  }
  const duration = 380;
  const started = performance.now();
  await new Promise(resolve => {
    const frame = (now) => {
      if (generation !== state.optimizationGeneration) { resolve(); return; }
      const progress = Math.min(1, (now - started) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      input.value = String(quantizedRangeValue(input, start + (end - start) * eased));
      setRangeVisual(input, output);
      if (progress < 1) requestAnimationFrame(frame); else resolve();
    };
    requestAnimationFrame(frame);
  });
}

async function animateOptimalControl(key, value, generation) {
  const control = $(optimizerControls[key]);
  const field = fieldForKey(key);
  if (!control || !field || control.disabled || field.closest(".hidden")) return;
  field.classList.remove("optimized");
  field.classList.add("optimizing");
  if (control.type === "range") await animateRange(control, value, generation);
  else if (control.tagName === "SELECT") {
    const option = [...control.options].find(item => item.value === String(value) && !item.disabled);
    if (!option) { field.classList.remove("optimizing"); return; }
    control.value = String(value);
    if (!reducedMotion()) await sleep(150);
  } else {
    control.value = value === null || value === undefined ? "" : String(value);
    if (!reducedMotion()) await sleep(150);
  }
  if (generation !== state.optimizationGeneration) return;
  control.dispatchEvent(new Event("change", {bubbles:true}));
  field.classList.remove("optimizing");
  field.classList.add("optimized");
  setTimeout(() => field.classList.remove("optimized"), 600);
}

async function applyOptimal(scope = "current", enginePreference = "fastest", openCalibrationOnMissing = true) {
  const model = selectedModel();
  if (!model || state.applyingOptimal) return false;
  closeOptimizerMenu();
  const generation = ++state.optimizationGeneration;
  const engineSelection = scope === "engine";
  const originalBackend = state.backend;
  const protectedBefore = protectedSnapshot(!engineSelection);
  const optimizerBefore = optimizerValueSnapshot();
  state.pendingOptimizerSnapshot = optimizerBefore;
  state.pendingOptimizerBackend = originalBackend;
  state.applyingOptimal = true;
  setOptimizerInteractionLocked(true);
  $("optimizationPanel").setAttribute("aria-busy", "true");
  setOptimizationState(
    "applying", "Applying…",
    engineSelection
      ? `Checking ${enginePreferenceLabels[enginePreference] || "the selected goal"} evidence across every compatible installed engine.`
      : "Checking this model and runtime's evidence.",
  );
  refreshLaunchability();
  let applyError = "";
  let applied = false;
  let calibrationFallback = null;
  try {
    const request = {
      backend:state.backend, modelId:model.id, client:state.client,
      context:Number($("contextInput").value), output:Number($("outputInput").value),
      reasoning:$("reasoningSelect").value,
      options:gatherOptions(),
    };
    if (engineSelection) request.enginePreference = enginePreference;
    if (state.client === "chat") request.chat = gatherChatSettings();
    const endpoint = engineSelection ? "/api/optimal-engine" : "/api/optimal";
    const data = await api(endpoint, {method:"POST", body:JSON.stringify(request)});
    const result = data.optimization;
    if (generation !== state.optimizationGeneration || selectedModel()?.id !== result.modelId) return;
    if (!uiEngineVisible(result.backend)) {
      throw new Error("The measured result points to an engine that is temporarily hidden in this launcher build.");
    }
    if (!engineSelection && state.backend !== result.backend) throw new Error("The current-engine optimiser returned a different runtime.");
    const nextAction = engineSelection ? result.engineNextAction : null;
    if (nextAction?.id === "calibrate") {
      calibrationFallback = {preference:enginePreference, decision:result};
      state.optimalSignature = "";
      state.optimalLabel = "";
      setOptimizationState(
        "custom", "Measurement needed",
        `${nextAction.reason} Review the exact calibration plan before anything runs.`,
      );
    } else {
      if (engineSelection && result.backend !== state.backend) {
        state.backend = result.backend;
        updateBackend(true);
        if (selectedModel()?.id !== result.modelId) throw new Error("The selected model is not available in the recommended engine.");
      }
      if (!setRuntimeKvValue(result.backend, result.options.kv || "off")) {
        throw new Error("The recommended engine could not preserve the selected KV precision.");
      }
      const changed = result.changedKeys.filter(key => optimizerControls[key]);
      if (changed.length) {
        $("advancedControls").open = true;
        await revealFirstChangedControl(changed);
      }
      for (const key of changed) {
        await animateOptimalControl(key, result.options[key], generation);
        if (generation !== state.optimizationGeneration) return;
        if (!reducedMotion()) await sleep(45);
      }
      if (protectedSnapshot(!engineSelection) !== protectedBefore) throw new Error("A protected intelligence or context control changed; optimisation was cancelled.");
      const mismatch = result.appliedKeys
        .filter(key => optimizerControls[key])
        .find(key => !optimizerValueMatches(key, result.options[key]));
      if (mismatch) throw new Error(`The ${mismatch} control did not reach the verified value; optimisation was cancelled.`);
      state.optimalSignature = speedSignature();
      const resultLabel = engineSelection
        ? (result.engineEvidenceLabel || result.evidenceLabel)
        : result.evidenceLabel;
      state.optimalLabel = resultLabel;
      const visibleRationale = engineSelection && result.engineRationale?.length
        ? result.engineRationale
        : result.rationale;
      const detail = changed.length
        ? `${changed.length} control${changed.length === 1 ? "" : "s"} updated · ${visibleRationale.join(" ")}`
        : `Already using this setup · ${visibleRationale.join(" ")}`;
      setOptimizationState("applied", resultLabel, detail);
      applied = true;
    }
  } catch (error) {
    if (generation === state.optimizationGeneration) {
      if (state.backend !== originalBackend) {
        state.backend = originalBackend;
        updateBackend(true);
      }
      restoreOptimizerValues(optimizerBefore);
    }
    state.optimalSignature = "";
    state.optimalLabel = "";
    setOptimizationState("custom", "Custom", "Optimisation could not be applied.");
    applyError = error.message;
  } finally {
    if (generation === state.optimizationGeneration) {
      clearOptimizerAnimationClasses();
      state.pendingOptimizerSnapshot = null;
      state.pendingOptimizerBackend = "";
      state.applyingOptimal = false;
      setOptimizerInteractionLocked(false);
      $("optimizationPanel").setAttribute("aria-busy", "false");
      refreshLaunchability();
      if (applyError) showNotice(applyError, true);
    }
  }
  if (openCalibrationOnMissing && calibrationFallback && generation === state.optimizationGeneration) {
    await openCalibrationAssistant({
      source:"optimizer-result",
      preference:calibrationFallback.preference,
      decision:calibrationFallback.decision,
    });
  }
  return applied;
}

async function prepareVerifiedQuickLaunch(enginePreference = "fastest") {
  if (state.applyingOptimal || routeCheckIsActive()) return;
  const applied = await applyOptimal("engine", enginePreference);
  if (!applied) return;
  state.routeCheckIntent = "verified-launch";
  await openRouteCheck("verified-launch");
}

function routeCheckIsActive(status = state.routeCheckStatus || {}) {
  return ["queued","starting","running","stopping"].includes(status.phase || state.routeCheckPhase);
}

function routeCheckVisibleSignature() {
  try { return JSON.stringify(gather("custom", false)); }
  catch (_) { return ""; }
}

function routeCheckVisibleMatches() {
  return Boolean(
    state.routeCheckInputSignature
    && routeCheckVisibleSignature() === state.routeCheckInputSignature
  );
}

function routeCheckReceiptReady(status = state.routeCheckStatus || {}) {
  const receipt = status.result?.receipt;
  const expires = Date.parse(receipt?.expiresAt || "");
  return Boolean(
    status.phase === "completed"
    && status.result?.temporaryRouteStopped === true
    && ["pass","advisory"].includes(status.result?.verdict)
    && receipt?.ready === true
    && Number.isFinite(expires) && expires > Date.now()
    && routeCheckVisibleMatches()
  );
}

function routeCheckItemMarkup(check = {}) {
  const status = check.status || "pending";
  const icon = ({pass:"✓",advisory:"!",fail:"×",running:"…",skipped:"–",pending:"·"})[status] || "·";
  return `<article class="route-check-item ${esc(status)}"><i aria-hidden="true">${icon}</i><div><strong>${esc(check.label || check.id)}</strong><small>${esc(check.detail || "Waiting for the live check.")}</small></div></article>`;
}

function renderRouteCheck() {
  const plan = state.routeCheckPlan;
  const rawStatus = state.routeCheckStatus || {};
  const ownsStatus = Boolean(
    plan?.contractId && rawStatus.job?.contractId === plan.contractId,
  );
  const status = ownsStatus ? rawStatus : {phase:"idle",progress:0,checks:[],result:null};
  const phase = status.phase || "idle";
  const active = routeCheckIsActive(status);
  const visibleMatches = routeCheckVisibleMatches();
  const route = plan?.route;
  const work = plan?.work;
  const checks = status.checks?.length ? status.checks : (plan?.checks || []);
  $("routeCheckRoute").textContent = route
    ? `${route.backendLabel} → ${route.surface} · ${route.model}`
    : "Inspecting the visible model route…";
  $("routeCheckFacts").innerHTML = route ? [
    ["Protocol", route.protocol],
    ["Context", formatNumber(route.context)],
    ["Max response", formatNumber(route.output)],
    ["Reasoning", route.reasoning],
    ["Live work", `${work?.modelLoads || 1} load · ${work?.generatedRequests || 1} request${work?.generatedRequests === 1 ? "" : "s"}`],
  ].map(([label,value]) => `<span><small>${esc(label)}</small><b title="${esc(value)}">${esc(value)}</b></span>`).join("") : "";
  $("routeCheckChecks").innerHTML = checks.map(routeCheckItemMarkup).join("") || '<p class="runtime-empty">Finish the visible route settings to build its checks.</p>';
  const guided = state.routeCheckIntent === "verified-launch";
  $("routeCheckKicker").textContent = guided ? "Measured engine · live route proof" : "Synthetic local preflight";
  $("routeCheckTitle").textContent = guided ? "Verified Quick Launch" : "Route Check";

  const progress = Math.max(0, Math.min(1, Number(status.progress || 0)));
  const percent = Math.round(progress * 100);
  $("routeCheckPercent").textContent = `${percent}%`;
  $("routeCheckProgressBar").style.width = `${percent}%`;
  $("routeCheckProgressBar").parentElement.setAttribute("aria-valuenow", String(percent));
  $("routeCheckPhase").textContent = ({
    idle:state.routeCheckLoading ? "Planning" : "Ready to review",
    queued:"Queued",starting:"Loading model",running:"Checking protocol",
    stopping:"Stopping",completed:"Completed",cancelled:"Stopped",failed:"Failed",
  })[phase] || phase;
  $("routeCheckStatus").textContent = state.routeCheckLoading
    ? "Validating the visible settings and current Mac capacity without starting anything…"
    : (ownsStatus && status.message) || plan?.detail || "Opening this plan does not start a model.";

  let badgeText = "Read only";
  let badgeClass = "";
  if (active) { badgeText = "Live check"; badgeClass = "active"; }
  else if (status.result?.verdict === "pass") { badgeText = "Passed"; badgeClass = "ready"; }
  else if (status.result?.verdict === "advisory") { badgeText = "Advisories"; badgeClass = "warning"; }
  else if (phase === "failed" || status.result?.verdict === "fail") { badgeText = "Failed"; badgeClass = "warning"; }
  else if (plan && !visibleMatches) { badgeText = "Settings changed"; badgeClass = "warning"; }
  else if (plan?.ready === false) { badgeText = "Blocked"; badgeClass = "warning"; }
  $("routeCheckBadge").textContent = badgeText;
  $("routeCheckBadge").className = `setup-badge${badgeClass ? ` ${badgeClass}` : ""}`;

  const result = status.result;
  const receiptReady = routeCheckReceiptReady(status);
  const receipt = result?.receipt;
  const receiptDetail = receiptReady
    ? ` Checked launch available until ${new Date(receipt.expiresAt).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"})}.`
    : (result && !visibleMatches ? " Visible settings changed, so this evidence cannot authorize launch." : "");
  $("routeCheckResult").className = `route-check-result${result ? ` ${result.verdict || ""}` : " hidden"}`;
  $("routeCheckResult").innerHTML = result
    ? `<strong>${esc(result.verdict === "pass" ? "Route passed." : result.verdict === "advisory" ? "Route passed with advisories." : "Route failed.")}</strong> ${esc(result.summary || "Review the individual checks.")}${esc(receiptDetail)}<br><small>No generated response text was stored and no work surface was opened.</small>`
    : "";

  const canStart = Boolean(plan?.ready && visibleMatches && !active && !state.routeCheckLoading && !receiptReady && !acquisitionIsActive());
  $("routeCheckConsent").disabled = true;
  $("routeCheckConsent").checked = false;
  $("routeCheckConsentPanel").classList.add("hidden");
  $("routeCheckConsentCopy").textContent = work
    ? `${work.modelLoads} temporary model load · ${work.generatedRequests} generated request${work.generatedRequests === 1 ? "" : "s"} · at most ${work.maxGeneratedTokensPerRequest} tokens each · automatic unload.`
    : "The model-load and generated-request count will appear after the read-only plan is ready.";
  $("routeCheckStartButton").disabled = !(canStart && plan?.contractId);
  $("routeCheckStartButton").classList.toggle("hidden", receiptReady);
  $("routeCheckStopButton").disabled = !active;
  $("routeCheckStartLabel").textContent = plan?.ready
    ? "Synthetic prompts · automatic unload"
    : "Waiting for a valid plan";
  const showCheckedLaunch = guided || Boolean(receipt);
  $("routeCheckLaunchButton").classList.toggle("hidden", !showCheckedLaunch);
  $("routeCheckLaunchButton").disabled = !receiptReady || state.verifiedLaunchBusy;
  $("routeCheckLaunchLabel").textContent = state.verifiedLaunchBusy
    ? "Revalidating the exact receipt…"
    : receiptReady
      ? `${route?.backendLabel || "Checked engine"} · ${route?.surface || "selected surface"}`
      : visibleMatches ? "Complete Route Check first" : "Settings changed · check again";
}

async function loadRouteCheckPlan() {
  if (state.routeCheckLoading || routeCheckIsActive()) return;
  const generation = ++state.routeCheckGeneration;
  state.routeCheckLoading = true;
  state.routeCheckPlan = null;
  renderRouteCheck();
  try {
    const request = gather("custom", false);
    const inputSignature = JSON.stringify(request);
    const data = await api("/api/route-check/plan", {
      method:"POST",
      body:JSON.stringify(request),
    });
    if (generation !== state.routeCheckGeneration) return;
    state.routeCheckPlan = data.plan;
    state.routeCheckInputSignature = inputSignature;
  } catch (error) {
    if (generation !== state.routeCheckGeneration) return;
    state.routeCheckPlan = {ready:false,detail:error.message,checks:[]};
    state.routeCheckInputSignature = "";
  } finally {
    if (generation === state.routeCheckGeneration) state.routeCheckLoading = false;
    renderRouteCheck();
  }
}

async function openRouteCheck(intent = "inspect") {
  state.routeCheckIntent = intent === "verified-launch" ? "verified-launch" : "inspect";
  if (!$("routeCheckDialog").open) $("routeCheckDialog").showModal();
  await pollRouteCheckStatus();
  if (!routeCheckIsActive()) await loadRouteCheckPlan();
  else renderRouteCheck();
}

async function startRouteCheck() {
  const plan = state.routeCheckPlan;
  if (!plan?.ready || !plan.contractId || !routeCheckVisibleMatches() || routeCheckIsActive()) return;
  try {
    const request = JSON.parse(JSON.stringify(plan.request));
    request.confirmation = plan.contractId;
    const data = await api("/api/route-check/start", {
      method:"POST", body:JSON.stringify(request),
    });
    state.routeCheckPhase = "queued";
    state.routeCheckStatus = {
      phase:"queued", progress:.03,
      message:"Route Check accepted. Preparing the temporary local model route…",
      job:data.routeCheck, checks:plan.checks, result:null,
    };
    renderRouteCheck();
    refreshLaunchability();
  } catch (error) {
    $("routeCheckStatus").textContent = error.message;
    showNotice(error.message, true);
  }
}

async function pollRouteCheckStatus() {
  try {
    const status = await api("/api/route-check/status");
    state.routeCheckStatus = status;
    state.routeCheckPhase = status.phase || "idle";
    if ($("routeCheckDialog")?.open) renderRouteCheck();
    refreshLaunchability();
    if (
      status.phase === "completed" && status.job?.id
      && state.routeCheckCompletionId !== status.job.id
    ) {
      state.routeCheckCompletionId = status.job.id;
      showNotice(status.result?.summary || "Route Check completed.", status.result?.verdict === "fail");
    }
  } catch (_) {}
}

async function stopRouteCheck() {
  try {
    await api("/api/route-check/stop", {method:"POST", body:"{}"});
    await Promise.all([pollStatus(), pollRouteCheckStatus()]);
  } catch (error) { $("routeCheckStatus").textContent = error.message; }
}

async function launchCheckedRoute() {
  const status = state.routeCheckStatus || {};
  const plan = state.routeCheckPlan;
  if (!plan?.contractId || !routeCheckReceiptReady(status) || state.verifiedLaunchBusy) return;
  state.verifiedLaunchBusy = true;
  refreshLaunchability();
  renderRouteCheck();
  try {
    const currentRequest = gather("custom", false);
    const inputSignature = JSON.stringify(currentRequest);
    const data = await api("/api/route-check/plan", {
      method:"POST", body:JSON.stringify(currentRequest),
    });
    if (data.plan?.contractId !== plan.contractId) {
      state.routeCheckPlan = data.plan;
      state.routeCheckInputSignature = inputSignature;
      throw new Error("Visible settings changed after Route Check. Review and check this exact route again.");
    }
    const request = gather("custom");
    request.routeVerification = {
      jobId:status.job.id,
      contractId:plan.contractId,
    };
    const launched = await launch(request);
    if (launched) {
      state.routeCheckIntent = "inspect";
      if ($("routeCheckDialog").open) $("routeCheckDialog").close();
    }
  } catch (error) {
    $("routeCheckStatus").textContent = error.message;
    showNotice(error.message, true);
  } finally {
    state.verifiedLaunchBusy = false;
    refreshLaunchability();
    if ($("routeCheckDialog").open) renderRouteCheck();
  }
}

async function preview() {
  try {
    showNotice("");
    const data = await api("/api/preview", {method:"POST", body:JSON.stringify(gather("custom"))});
    const plan = data.plan;
    const chatSampling = plan.client === "chat"
      ? ` · ${plan.chat.sampling === "custom" ? `temperature ${plan.chat.temperature}, top P ${plan.chat.topP}, top K ${plan.chat.topK}, presence ${plan.chat.presencePenalty}, frequency ${plan.chat.frequencyPenalty}${plan.chat.seed === null ? "" : `, seed ${plan.chat.seed}`}` : "model sampling defaults"}`
      : "";
    $("previewContent").innerHTML = `
      <div class="preview-row"><span>Engine</span><code>${esc(plan.engineCommand)}</code></div>
      <div class="preview-row"><span>Work surface</span><code>${esc(plan.clientCommand)}</code></div>
      <div class="preview-row"><span>Contract</span><code>${esc(`${formatNumber(plan.context)} context · ${formatNumber(plan.output)} output · ${plan.reasoning} reasoning${chatSampling} · model localhost:${plan.port}${plan.clientPort !== plan.port ? ` · ${plan.purpose === "session" ? "private session relay" : "compatibility guard"} localhost:${plan.clientPort}` : ""}`)}</code></div>
      ${plan.warnings.length ? `<ul class="warning-list">${plan.warnings.map(warning => `<li>${esc(warning)}</li>`).join("")}</ul>` : ""}`;
    $("previewDialog").showModal();
  } catch (error) { showNotice(error.message, true); }
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

function chatHistoryDraftKey(historyId, surfaceId = state.chatRunId) {
  return `${chatDraftSurfacePrefix(surfaceId)}history:${String(historyId || "").slice(0, 72)}`;
}

function newChatDraftKey(surfaceId = state.chatRunId) {
  const id = localUuid();
  return `${chatDraftSurfacePrefix(surfaceId)}new:${id}`;
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

function chatDraftHistoryIdFromKey(key, surfaceId = state.chatRunId) {
  const prefix = `${chatDraftSurfacePrefix(surfaceId)}history:`;
  if (!String(key || "").startsWith(prefix)) return "";
  const value = String(key).slice(prefix.length);
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
    ? value.toLocaleLowerCase() : "";
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
  const prefix = chatDraftSurfacePrefix(surfaceId);
  const active = options.restoreActive && String(envelope.activeKey || "").startsWith(prefix)
    ? envelope.activeKey : "";
  const explicitKey = String(options.key || "").startsWith(prefix) ? String(options.key) : "";
  const key = explicitKey || (options.historyId
    ? chatHistoryDraftKey(options.historyId, surfaceId)
    : active || newChatDraftKey(surfaceId));
  state.chatDraftKey = key;
  state.chatDraftPendingHistoryId = active
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

async function launch(requestOverride = null, launchOptions = {}) {
  try {
    showNotice("Validating the visible settings…");
    const request = requestOverride && typeof requestOverride === "object" && requestOverride.backend
      ? requestOverride : gather("custom");
    const warm = requestOverride
      ? (launchOptions.warmPlan?.canAttach && launchOptions.warmPlan?.confirmation
        ? launchOptions.warmPlan : null)
      : currentWarmRoutePlan();
    if (warm?.canAttach && warm.confirmation) {
      request.warmRouteConfirmation = warm.confirmation;
      const data = await api("/api/session/warm-attach", {
        method:"POST", body:JSON.stringify(request),
      });
      state.sessionAcknowledgementId = "";
      state.cacheObservatory = data.hub?.cache || state.cacheObservatory;
      if (state.runStatus) {
        state.runStatus = {
          ...state.runStatus,
          attachments:data.hub?.attachments || state.runStatus.attachments,
          cache:data.hub?.cache || state.runStatus.cache,
        };
      }
      if (state.sessionDashboard) state.sessionDashboard.hub = data.hub;
      clearWarmRoutePlan();
      if (data.attachment.client === "chat") {
        enterChatSurface(data.attachment);
        showNotice("Warm Chat opened on the loaded model. The engine and model weights were not reloaded.");
      } else if (data.attachment.agentHost === "console") {
        enterAgentConsole(data.attachment);
        showNotice(`${data.attachment.surface} opened in Hub Console on the loaded model. No model weights were reloaded.`);
      } else {
        showNotice(`${data.attachment.surface} opened in Terminal on the loaded model. No model weights were reloaded.`);
      }
      scheduleWarmRoutePlan(true);
      if ($("sessionDialog")?.open) await loadSessionDashboard();
      return true;
    }
    const data = await api("/api/launch", {method:"POST", body:JSON.stringify(request)});
    state.sessionAcknowledgementId = "";
    if (data.run.client === "chat") {
      if (state.chatAbort) state.chatAbort.abort();
      state.chatAbort = null;
      persistChatSessionState();
      resetChatConversation();
      state.chatRunId = data.run.runId;
      state.chatOwnerRunId = data.run.runId;
      state.chatAttachment = null;
      activateChatDraft(data.run.runId, {restore:false});
      renderChatMessages();
    } else if (data.run.agentHost === "console") {
      enterAgentConsole({
        id:data.run.runId, ownerRunId:data.run.runId, primary:true,
        client:data.run.client, surface:clientName(data.run.client),
        backend:data.run.backend, model:data.run.model, project:data.run.project,
        context:data.run.context, output:data.run.output, reasoning:data.run.reasoning,
        agentHost:"console", status:"starting", detail:"Loading the model before Hub Console opens.",
      });
    }
    showNotice(data.verifiedLaunch ? "Verified route accepted. Starting the selected work surface…" : "");
    renderRun({phase:"preflight", message:"Launch accepted. Running preflight…", run:data.run, events:[]});
    return true;
  } catch (error) {
    showNotice(error.message, true);
    if (/Open Sessions/i.test(error.message)) await openSessionDashboard();
    return false;
  }
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
}

function chatContent(value) {
  if (typeof value === "string") return value;
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return typeof value.text === "string" ? value.text : (typeof value.content === "string" ? value.content : "");
  }
  if (!Array.isArray(value)) return "";
  return value.map(part => {
    if (typeof part === "string") return part;
    if (part && typeof part === "object") return typeof part.text === "string" ? part.text : (typeof part.content === "string" ? part.content : "");
    return "";
  }).join("");
}

function partitionChatContent(value) {
  if (!Array.isArray(value)) return {text:chatContent(value), reasoning:""};
  let text = "", reasoning = "";
  for (const part of value) {
    const kind = String(part?.type || "").toLowerCase();
    const content = chatContent(part);
    if (kind.includes("reasoning") || kind.includes("thinking")) reasoning += content;
    else text += content;
  }
  return {text, reasoning};
}

function chatEventParts(event) {
  if (event?.error) throw new Error(event.error.message || event.error || "The model returned a streaming error.");
  const choice = event?.choices?.[0];
  const delta = choice?.delta || {};
  const message = choice?.message || event?.message || {};
  const contentParts = partitionChatContent(delta.content ?? message.content ?? choice?.text ?? event?.content);
  const explicitReasoning = chatContent(
    delta.reasoning_content ?? delta.reasoning ?? delta.thinking
    ?? message.reasoning_content ?? message.reasoning ?? message.thinking
    ?? event?.reasoning_content ?? event?.thinking,
  );
  return {text:contentParts.text, reasoning:explicitReasoning || contentParts.reasoning};
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
  const consumeEvent = event => {
    const parts = chatEventParts(event);
    if (parts.reasoning) onPart("reasoning", parts.reasoning);
    if (parts.text) emitThinkTaggedText(thinkParser, parts.text, onPart);
    const usage = chatEventUsage(event);
    if (usage) onPart("usage", usage);
    const limitReason = ChatStreamCore.responseLimitReason(event);
    if (limitReason) onPart("truncated", limitReason);
  };
  const contentType = response.headers.get("Content-Type") || "";
  if (contentType.toLowerCase().includes("application/json")) {
    const data = await response.json();
    consumeEvent(data);
    if (thinkParser.buffer) onPart(thinkParser.thinking ? "reasoning" : "content", thinkParser.buffer);
    return;
  }
  if (!response.body) throw new Error("This browser could not read the model stream.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let rawText = "";
  let sawData = false;
  const consumeLine = (line) => {
    const clean = line.replace(/\r$/, "");
    if (!clean.startsWith("data:")) return;
    const data = clean.slice(5).trim();
    if (!data || data === "[DONE]") return;
    sawData = true;
    const event = JSON.parse(data);
    consumeEvent(event);
  };
  while (true) {
    const {value, done} = await reader.read();
    const decoded = decoder.decode(value || new Uint8Array(), {stream:!done});
    rawText += decoded;
    buffer += decoded;
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) consumeLine(line);
    if (done) break;
  }
  if (buffer.trim()) consumeLine(buffer);
  if (!sawData && rawText.trim().startsWith("{")) {
    consumeEvent(JSON.parse(rawText));
  }
  if (thinkParser.buffer) onPart(thinkParser.thinking ? "reasoning" : "content", thinkParser.buffer);
}

function renderCacheObservatory(cache = state.cacheObservatory) {
  const report = cache && typeof cache === "object" ? cache : {
    state:"idle", label:"No resident model", detail:"Start a normal model session to observe cache reports.",
    policy:{configuration:"inactive", detail:"No normal launcher-owned model route is active."},
    observationCount:0, completedTurns:0, cacheTelemetryReportedTurns:0,
    confirmedHitTurns:0, reportedPromptTokens:0, reportedCachedPromptTokens:0,
    reportedTokenReuseRate:null, lastObservation:null,
  };
  state.cacheObservatory = report;
  const stateClass = report.state === "confirmed-reuse" || report.state === "warming"
    ? "ready" : ["reported-no-reuse", "telemetry-unavailable"].includes(report.state) ? "warning" : "";
  const rate = report.reportedTokenReuseRate !== null && report.reportedTokenReuseRate !== undefined
    && Number.isFinite(Number(report.reportedTokenReuseRate))
    ? `${(Number(report.reportedTokenReuseRate) * 100).toFixed(1)}%`
    : "Not reported";
  const policyLabel = ({
    "launcher-enabled":"Launcher enabled",
    "engine-managed":"Engine managed",
    inactive:"Inactive",
  })[report.policy?.configuration] || "Runtime managed";
  const last = report.lastObservation;

  if ($("sessionCacheState")) {
    $("sessionCacheState").textContent = report.label || "Cache state unavailable";
    $("sessionCacheState").className = stateClass;
    $("sessionCacheSection").dataset.state = report.state || "idle";
    $("sessionCachePolicy").textContent = report.policy?.detail || report.detail || "Cache policy is unavailable.";
    $("sessionCacheFacts").innerHTML = [
      ["Engine", report.engineResident ? "Resident" : "Not loaded"],
      ["Policy", policyLabel],
      ["Observed turns", formatNumber(report.observationCount || 0)],
      ["Cache reports", formatNumber(report.cacheTelemetryReportedTurns || 0)],
      ["Confirmed reuse", formatNumber(report.confirmedHitTurns || 0)],
      ["Reported token reuse", rate],
    ].map(([label,value]) => `<span><small>${esc(label)}</small><b title="${esc(value)}">${esc(value)}</b></span>`).join("");
    if (last) {
      const turnState = last.interrupted ? "Interrupted" : last.completed ? "Completed" : "Ended";
      const cacheDetail = last.cacheTelemetryReported
        ? `${formatNumber(last.cachedPromptTokens || 0)} of ${formatNumber(last.promptTokens || 0)} prompt tokens reported cached`
        : last.usageReported ? "Token usage reported; cache detail omitted" : "Runtime usage omitted";
      const timing = last.ttftSeconds !== null && last.ttftSeconds !== undefined
        && Number.isFinite(Number(last.ttftSeconds))
        ? ` · first output ${Number(last.ttftSeconds).toFixed(2)}s` : "";
      $("sessionCacheLast").innerHTML = `<strong>${esc(`${turnState} Chat turn`)}</strong><span>${esc(`${cacheDetail}${timing}`)}</span>`;
    } else {
      $("sessionCacheLast").innerHTML = "<strong>No observed Chat turns</strong><span>Built-in Chat reports appear here when the runtime exposes authoritative usage.</span>";
    }
    $("sessionCacheCoverage").textContent = report.coverage?.detail
      || "Only controller-relayed built-in Chat turns are counted; direct agent traffic is never guessed.";
  }

  if ($("chatCacheState")) {
    $("chatCacheState").textContent = report.label || "Cache state unavailable";
    const lastDetail = last?.cacheTelemetryReported
      ? `${formatNumber(last.cachedPromptTokens || 0)} cached prompt tokens in the latest observed turn.`
      : report.detail;
    $("chatCacheDetail").textContent = lastDetail || "Timing alone is not treated as a cache hit.";
    $("chatCacheState").parentElement.dataset.state = report.state || "idle";
    const cacheSignal = $("chatStatusCache");
    if (cacheSignal) {
      const compact = ChatStatusCore.cacheSummary(report);
      $("chatStatusCacheValue").textContent = compact.value;
      cacheSignal.dataset.state = compact.state;
      cacheSignal.title = lastDetail || "Cache reuse is shown only from runtime-reported token fields.";
      updateChatStatusSummaryLabel();
    }
  }
}

function renderRequestActivity(activity = state.requestActivity) {
  const report = activity && typeof activity === "object" ? activity : {
    state:"idle", detail:"Start a normal model session to create its private request relay.",
    engineResident:false, lanes:0, activeCount:0, queuedCount:0,
    active:[], queued:[], recent:[], surfaces:[], idleSeconds:null,
    coverage:{allLauncherSurfaces:false, detail:"Only launcher-created surfaces are observed; independent engine clients are never guessed."},
    idlePolicy:{enabled:false, timeoutMinutes:0, eligible:false, remainingSeconds:null, detail:"Keep the model loaded until you stop it."},
  };
  state.requestActivity = report;
  const active = Array.isArray(report.active) ? report.active : [];
  const queued = Array.isArray(report.queued) ? report.queued : [];
  const recent = Array.isArray(report.recent) ? report.recent.slice(0, 3) : [];
  const policy = report.idlePolicy || {};
  const busy = active.length > 0 || queued.length > 0;
  const latestMeasured = recent.find(request => requestTps(request));
  const latestSpeed = requestTps(latestMeasured);
  const liveMeasured = active.find(request => requestTps(request)?.primaryKind === "live");
  const liveSpeed = requestTps(liveMeasured);
  const headlineSpeed = liveSpeed || latestSpeed;
  const latestTps = headlineSpeed?.compact || "Runtime did not report";
  const stateLabel = report.state === "unavailable"
    ? "Relay unavailable"
    : busy ? `${active.length} active · ${queued.length} waiting`
      : report.engineResident ? "Relay idle" : "No resident model";

  if ($("sessionActivityState")) {
    $("sessionActivitySection").dataset.state = report.state || (busy ? "busy" : "idle");
    $("sessionActivityState").textContent = stateLabel;
    $("sessionActivityState").className = busy ? "warning" : report.state === "unavailable" ? "blocked" : report.engineResident ? "ready" : "";
    $("sessionActivityDetail").textContent = report.detail || "Request activity is unavailable.";
    const idleValue = busy ? "Paused"
      : policy.enabled && policy.remainingSeconds !== null && policy.remainingSeconds !== undefined
        ? formatShortDuration(policy.remainingSeconds)
        : policy.enabled ? "Waiting for relay" : "Off";
    $("sessionActivityFacts").innerHTML = [
      ["Engine lanes", formatNumber(report.lanes || 0)],
      ["Generating", formatNumber(report.activeCount || 0)],
      ["Waiting", formatNumber(report.queuedCount || 0)],
      ["Surfaces", formatNumber(report.surfaces?.length || 0)],
      [liveSpeed ? "Live TPS" : "Latest measured TPS", latestTps],
      ["Idle unload", idleValue],
    ].map(([label,value]) => `<span><small>${esc(label)}</small><b title="${esc(value)}">${esc(value)}</b></span>`).join("");
    if (headlineSpeed) $("sessionActivityFacts").querySelectorAll("b")[4].title = headlineSpeed.label;

    const requestRow = (request, historical = false) => {
      const running = request.state === "running";
      const waiting = request.state === "queued" || request.state === "cancelling";
      const speed = requestTps(request);
      const liveDetail = liveRequestDetail(request);
      const completedDetail = completedRequestDetail(request);
      const timing = running
        ? `${liveRequestPhaseLabel(request) || "Generating"} · ${formatShortDuration(request.runSeconds)}${speed ? ` · ${speed.label}` : ""}${liveDetail ? ` · ${liveDetail}` : ""}${request.firstOutputSeconds !== null && request.firstOutputSeconds !== undefined ? ` · first output ${formatShortDuration(request.firstOutputSeconds)}` : " · awaiting first output"}`
        : waiting
          ? `${request.state === "cancelling" ? "Cancelling" : `Queue #${formatNumber(request.queuePosition || 1)}`} · ${formatShortDuration(request.waitSeconds)} waiting`
          : `${String(request.result || "completed").replaceAll("-", " ")} · ${formatShortDuration(request.runSeconds || 0)}${speed ? ` · ${speed.label}` : " · TPS unavailable"}${completedDetail ? ` · ${completedDetail}` : ""}`;
      const protocol = request.protocol === "responses" ? "Responses" : request.protocol === "chat-completions" ? "Chat Completions" : "local API";
      const cancel = !historical && request.canCancel
        ? `<button type="button" data-session-cancel-request="${esc(request.id)}" data-session-request-surface="${esc(request.surfaceId || "")}"${state.requestCancelBusyId ? " disabled" : ""}>${state.requestCancelBusyId === request.id ? "Cancelling…" : "Cancel"}</button>`
        : "";
      return `<article class="session-request ${esc(request.state || "completed")}"><i aria-hidden="true"></i><div class="session-request-main"><strong>${esc(`${request.surface || clientName(request.client)} · ${protocol}`)}</strong><span>${esc(timing)}</span></div>${cancel}</article>`;
    };
    const rows = [
      ...active.map(request => requestRow(request)),
      ...queued.map(request => requestRow(request)),
      ...recent.map(request => requestRow(request, true)),
    ];
    $("sessionActivityList").innerHTML = rows.length ? rows.join("")
      : `<div class="session-activity-empty"><strong>${report.engineResident ? "Relay ready · no requests" : "No request activity"}</strong><span>${esc(report.engineResident ? "The loaded model is warm and waiting for Chat or an agent." : "Start a normal model session to create its private request relay.")}</span></div>`;

    const timeout = String(Number(policy.timeoutMinutes || 0));
    const select = $("sessionIdleTimeout");
    if ([...select.options].some(option => option.value === timeout)) select.value = timeout;
    const eligible = Boolean(report.engineResident && policy.eligible);
    [...select.options].forEach(option => { option.disabled = option.value !== "0" && !eligible; });
    select.disabled = !report.engineResident || state.idlePolicyBusy || (!eligible && !policy.enabled);
    $("sessionIdlePolicyDetail").textContent = state.idlePolicyBusy ? "Saving the session-only idle policy…" : policy.detail || "Keep the model loaded until you stop it.";
    $("sessionActivityCoverage").textContent = `${report.coverage?.detail || "Only launcher-created surfaces are observed."} No prompt, response, reasoning, tool, or project content is stored.`;
  }

  if ($("chatActivityState")) {
    const current = [...active, ...queued].find(item => item.surfaceId === state.chatRunId);
    const inline = $("chatActivityState").parentElement;
    const chatRecent = recent.find(item => item.surfaceId === state.chatRunId && requestTps(item));
    const chatSpeed = requestTps(chatRecent);
    if (current?.state === "running") {
      const currentSpeed = requestTps(current);
      const liveDetail = liveRequestDetail(current);
      $("chatActivityState").textContent = `${liveRequestPhaseLabel(current) || "Generating"}${currentSpeed ? ` · ${currentSpeed.primary.toFixed(1)} tok/s` : ` · ${formatShortDuration(current.runSeconds)}`}`;
      $("chatActivityDetail").textContent = `${liveDetail ? `${liveDetail}. ` : ""}${formatNumber(report.lanes || 1)} engine lane${Number(report.lanes || 1) === 1 ? "" : "s"} · ${formatNumber(queued.length)} other request${queued.length === 1 ? "" : "s"} waiting.`;
      inline.dataset.state = "running";
    } else if (current) {
      $("chatActivityState").textContent = `Engine queue #${formatNumber(current.queuePosition || 1)}`;
      $("chatActivityDetail").textContent = `${formatShortDuration(current.waitSeconds)} waiting behind earlier launcher-created work.`;
      inline.dataset.state = "queued";
    } else if (active.length) {
      $("chatActivityState").textContent = `${active[0].surface || "Another surface"} is generating`;
      $("chatActivityDetail").textContent = `${formatNumber(report.activeCount)} of ${formatNumber(report.lanes || 1)} configured engine lanes active.`;
      inline.dataset.state = "busy";
    } else {
      $("chatActivityState").textContent = report.engineResident
        ? `Relay idle${chatSpeed ? ` · ${chatSpeed.primary.toFixed(1)} tok/s ${chatSpeed.primaryKind} last turn` : ""}`
        : "Relay unavailable";
      $("chatActivityDetail").textContent = report.engineResident
        ? `${formatNumber(report.lanes || 1)} engine-matched lane${Number(report.lanes || 1) === 1 ? "" : "s"} ready for launcher-created surfaces.`
        : report.detail || "Request activity is unavailable.";
      inline.dataset.state = report.engineResident ? "idle" : "unavailable";
    }
    $("chatActivityState").title = chatSpeed
      ? `Last completed Chat turn: ${chatSpeed.label}`
      : "TPS appears only when the runtime reports authoritative token usage.";
    const speedSignal = $("chatStatusSpeed");
    const laneSignal = $("chatStatusLane");
    if (speedSignal && laneSignal) {
      const compact = ChatStatusCore.activitySummary(report, state.chatRunId);
      $("chatStatusSpeedValue").textContent = compact.speed.value;
      speedSignal.dataset.state = compact.speed.state;
      speedSignal.title = compact.speed.title;
      $("chatStatusLaneValue").textContent = compact.lane.value;
      laneSignal.dataset.state = compact.lane.state;
      laneSignal.title = `${$("chatActivityState").textContent}. ${$("chatActivityDetail").textContent}`;
      updateChatStatusSummaryLabel();
    }
  }
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
  const historyCharacters = (messages || []).reduce((total, message) => total + String(message.content || "").length, 0);
  return WorkspaceContextCore.availableContextCharacters({
    contextTokens:Number(run.context || 16_384),
    outputTokens:Number(run.output || 4_096),
    historyCharacters,
  });
}

function chatWorkspaceRequestCharacterBudget(messages, manualCharacters = 0) {
  const run = state.chatAttachment || state.runStatus?.run || {};
  const historyCharacters = (messages || []).reduce((total, message) => total + String(message.content || "").length, 0);
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
    container.innerHTML = `<div class="chat-empty"><span aria-hidden="true">●</span><strong>Ready when you are</strong><p>Ask the selected model anything. Streamed reasoning appears in a separate panel when exposed, and completed turns are saved locally.</p></div>`;
    state.chatFollowOutput = true;
    renderChatTranscriptToolbar([]);
    updateChatScrollUi();
    return;
  }
  const fragment = document.createDocumentFragment();
  const landmarks = new Map(
    ChatTranscriptCore.turnLandmarks(state.chatMessages).map(item => [item.id, item]),
  );
  state.chatMessages.forEach((message, index) => {
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
    const landmark = landmarks.get(message.id);
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
      const recovery = document.createElement("em");
      recovery.className = "chat-message-recovery";
      recovery.textContent = "Recovered partial · interrupted";
      recovery.title = "The page closed during generation. This is only the visible text checkpointed before the stream ended.";
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
      const addAction = (action, text, title = text, target = actions) => {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.chatAction = action;
        button.dataset.chatMessageId = message.id;
        button.textContent = text;
        button.title = title;
        button.setAttribute("aria-label", `${title} for this ${message.role} message`);
        const mutatesConversation = action !== "copy";
        button.disabled = Boolean(
          mutatesConversation
          && (state.chatAbort || state.chatRevisionBusy || state.chatEditingMessageId
            || state.chatQueue.length),
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
        const hasEarlierUser = state.chatMessages.slice(0, index).some(item => item.role === "user" && !item.pending);
        if (hasEarlierUser) addMoreAction("regenerate", "Regenerate", "Generate another answer in a new branch");
        if (message.content) {
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
      body.setAttribute("aria-label", "No visible model output was received before the page closed.");
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
    if (!editing && message.role === "assistant" && message.usage) {
      const usage = document.createElement("div");
      usage.className = "chat-message-usage";
      const cached = Number.isInteger(message.usage.cachedPromptTokens)
        ? ` · ${formatNumber(message.usage.cachedPromptTokens)} cached`
        : "";
      usage.textContent = `${formatNumber(message.usage.promptTokens)} prompt tokens · ${formatNumber(message.usage.completionTokens)} response tokens${cached} · runtime reported`;
      article.append(usage);
    }
    fragment.append(article);
  });
  container.replaceChildren(fragment);
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
    || state.chatRevisionBusy || state.chatContextBusy || state.runPhase !== "running" || !state.chatRunId,
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
  const ready = state.runPhase === "running" && Boolean(state.chatRunId);
  const revisionBusy = Boolean(state.chatRevisionBusy);
  const editingMessage = Boolean(state.chatEditingMessageId);
  const contextBusy = Boolean(state.chatContextBusy);
  button.disabled = !ready || revisionBusy || editingMessage || contextBusy;
  button.classList.remove("stopping");
  const queueMode = busy || state.chatQueue.length > 0;
  button.querySelector("strong").textContent = queueMode ? "Queue" : "Send";
  button.querySelector("span").textContent = queueMode ? "+" : "↑";
  $("chatStopButton").classList.toggle("hidden", !busy);
  $("chatStopButton").disabled = !busy;
  $("chatInput").disabled = !ready || revisionBusy || editingMessage || contextBusy;
  $("newChatButton").disabled = !ready || busy || (state.chatQueue.length > 0 && !state.chatQueuePaused) || revisionBusy || editingMessage || contextBusy;
  $("chatSidebarNew").disabled = $("newChatButton").disabled;
  $("chatHistoryButton").disabled = !ready || revisionBusy || editingMessage;
  $("chatComposerHint").textContent = contextBusy
    ? "Reading and validating selected text locally…"
    : revisionBusy
    ? "Preserving the original and preparing the branch…"
    : editingMessage
      ? "Finish or cancel the message edit before sending another turn"
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
    state.chatAbort || state.chatQueuePaused || state.chatQueueEditingId || !state.chatQueue.length || state.runPhase !== "running"
    || !state.chatRunId || state.chatRunId !== surfaceId
  ) return;
  const next = state.chatQueue.shift();
  persistChatQueue();
  setChatBusy(false);
  const started = await startChatTurn(next.content);
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
    !state.chatQueuePaused || !state.chatQueue.length || state.chatAbort
    || state.chatQueueEditingId || state.chatRevisionBusy || state.chatContextBusy
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
  const value = String(content || "");
  if (
    state.runPhase !== "running" || !state.chatRunId || state.chatAbort
    || state.chatContextBusy
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
    .filter(message => !message.pending && !message.exclude && message.content)
    .map(({role, content: text}) => ({role, content:text}));
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
  state.chatFollowOutput = true;
  state.chatEditingMessageId = "";
  if (user) clearChatDraft();
  const controller = new AbortController();
  state.chatAbort = controller;
  const checkpoint = beginChatTurnCheckpoint(surfaceId, ownerRunId, checkpointUser, assistant);
  renderChatMessages({forceBottom:true});
  setChatBusy(true);
  try {
    const response = await fetch("/api/chat", {
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
    if (!assistant.content) assistant.content = "The runtime exposed reasoning but returned no final answer.";
  } catch (error) {
    if (error.name === "AbortError") {
      if (user) user.exclude = true;
      assistant.exclude = true;
      assistant.stopped = true;
      if (!assistant.content) assistant.content = "Generation stopped.";
    } else {
      if (user) user.exclude = true;
      assistant.exclude = true;
      assistant.stopped = true;
      assistant.content = assistant.content || `Chat error: ${error.message}`;
    }
  } finally {
    assistant.pending = false;
    if (state.chatAbort === controller) state.chatAbort = null;
    await finishChatTurnCheckpoint(checkpoint);
    setChatBusy(false);
    renderChatMessages();
    if (state.chatRunId === surfaceId) {
      const saved = await saveCurrentChatHistory();
      if (saved) await clearChatTurnCheckpoint(checkpoint);
      if (state.runPhase === "running") input.focus();
      setTimeout(() => processChatQueue(surfaceId), 0);
    }
    void pollStatus();
  }
  return true;
}

function chatMessageIndex(messageId) {
  return state.chatMessages.findIndex(message => message.id === messageId);
}

async function createChatBranch(messages, sourcePoint, kind, notice) {
  if (state.chatAbort || !messages.some(message => message.role === "user")) return false;
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

async function continueChatMessage(messageId) {
  const selectedIndex = chatMessageIndex(messageId);
  if (selectedIndex < 0 || state.chatMessages[selectedIndex].role !== "assistant") return;
  const activeIndices = state.chatMessages
    .map((message, index) => ({message, index}))
    .filter(item => !item.message.pending && !item.message.exclude && item.message.content);
  const selected = state.chatMessages[selectedIndex];
  const isActiveTail = activeIndices.at(-1)?.index === selectedIndex && !selected.stopped;
  if (!isActiveTail) {
    const messages = state.chatMessages.slice(0, selectedIndex + 1)
      .filter(message => !message.pending && message.content)
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
  void startChatTurn("", {operation:"continue"});
}

async function copyLocalText(value) {
  const text = String(value || "");
  if (!text) return false;
  try {
    await navigator.clipboard.writeText(text);
  } catch (_error) {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.append(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }
  return true;
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
  if (state.chatAbort || state.chatRevisionBusy) return;
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
    || state.chatRevisionBusy || state.chatContextBusy
  ) return;
  if (state.chatAbort || state.chatQueue.length) {
    queueChatMessage(content);
    return;
  }
  void startChatTurn(content);
}

async function newChat() {
  persistChatSessionState();
  await saveCurrentChatHistory();
  if (state.chatAbort) state.chatAbort.abort();
  const surfaceId = state.chatRunId;
  resetChatConversation();
  if (surfaceId) activateChatDraft(surfaceId, {restore:false});
  renderChatMessages();
  renderChatSidebar();
  renderChatRoute(state.runStatus?.run);
  if (state.runPhase === "running") $("chatInput").focus();
}

function currentChatHistoryPayload() {
  const messages = state.chatMessages
    .filter(message => !message.pending && (message.content || message.interrupted))
    .map(message => ({
      role:message.role,
      content:message.content,
      reasoning:message.reasoning || "",
      usage:message.usage || undefined,
      stopped:Boolean(message.stopped),
      exclude:Boolean(message.exclude),
      interrupted:Boolean(message.interrupted),
      continuation:Boolean(message.continuation),
      truncated:Boolean(message.truncated),
      createdAt:message.createdAt || undefined,
    }));
  if (!messages.some(message => message.role === "user")) return null;
  const run = state.runStatus?.run || state.chatAttachment || {};
  return {
    id:ensureChatHistoryId(),
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

async function saveCurrentChatHistory() {
  const payload = currentChatHistoryPayload();
  if (!payload) return null;
  while (state.chatHistorySaving) await sleep(25);
  const surfaceId = state.chatRunId;
  const previousId = state.chatHistoryId;
  state.chatHistorySaving = true;
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
    return data.thread;
  } catch (error) {
    showNotice(`The chat completed, but local history could not be saved: ${error.message}`, true);
    return null;
  } finally {
    state.chatHistorySaving = false;
    if ($("chatHistoryDialog")?.open) renderChatHistory();
    renderChatSidebar();
  }
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
  const prefix = `${chatDraftSurfacePrefix()}new:`;
  const draftEnvelope = readChatDraftEnvelope();
  const keys = new Set([
    ...Object.keys(draftEnvelope.drafts),
    ...Object.keys(queueEnvelope.queues || {}),
  ].filter(key => key.startsWith(prefix)));
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
    || state.chatHistoryBusyId || state.runPhase !== "running" || !state.chatRunId
    || !String(key || "").startsWith(`${chatDraftSurfacePrefix()}new:`)
  ) return;
  if (!state.chatHistoryId && key === state.chatDraftKey) {
    $("chatInput").focus();
    return;
  }
  persistChatSessionState();
  await saveCurrentChatHistory();
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
    if (state.runStatus?.run?.runId === state.chatRunId && state.runStatus.run.client === "chat") {
      state.runStatus.run.chat = chat;
    }
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
  card.dataset.state = savedMismatch || originChanged ? "changed" : "current";
  $("chatRouteModel").textContent = route.model;
  $("chatRouteDetail").textContent = `${profileBackendLabel(route.backend)} · ${formatNumber(route.context)} context · ${formatNumber(route.output)} max response · ${route.reasoning} reasoning · ${samplingLabel}`;
  $("chatRunSettingsButton").setAttribute(
    "aria-label", `Chat controls, ${samplingLabel}. Changes apply to the next request.`,
  );
  if (savedMismatch) {
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
  $("chatStatusRouteState").hidden = card.dataset.state !== "changed";
  $("chatStatusRouteState").title = $("chatRouteNotice").textContent;
  updateChatStatusSummaryLabel();
  $("chatTitle").textContent = thread?.title || route.model;
  const routeNote = route.routeKind === "connected"
    ? "requests use the connected server; transcript history stays on this Mac"
    : route.routeKind === "native"
      ? "native on this Mac; launcher Stop unloads it"
      : "streamed thinking shown when the runtime exposes it";
  $("chatMeta").textContent = `${profileBackendLabel(route.backend)} · ${route.model} · ${routeNote}`;
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
      const disabled = historyBusy || actionBusy || state.chatResumeStarting ? " disabled" : "";
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
          ? `<button type="button" data-chat-history-resume="${esc(thread.id)}"${historyBusy || actionBusy || state.chatResumeStarting ? " disabled" : ""}>Review resume</button>`
          : `<button type="button" disabled title="${thread.resumeAvailable ? "This saved engine is temporarily hidden." : "Open and save this conversation once on an active Chat route to make it resumable."}">Route unavailable</button>`;
      const actions = editing ? "" : `<div class="chat-history-actions">${primaryAction}<details class="chat-history-more"${confirming ? " open" : ""}><summary aria-label="More actions for ${title}">More <span aria-hidden="true">⌄</span></summary><div><button type="button" aria-pressed="${thread.pinned ? "true" : "false"}" data-chat-history-pin="${esc(thread.id)}"${disabled}>${thread.pinned ? "Unpin" : "Pin"}</button><button type="button" data-chat-history-rename="${esc(thread.id)}"${disabled}>Rename</button><button type="button" data-chat-history-export="${esc(thread.id)}"${actionBusy ? " disabled" : ""}>Export</button><button type="button" class="delete" data-chat-history-delete="${esc(thread.id)}"${disabled}>${confirming ? "Confirm delete" : "Delete"}</button></div></details></div>`;
      return `<article class="chat-history-card${thread.pinned ? " pinned" : ""}" data-chat-history-card="${esc(thread.id)}"><div class="chat-history-main"><div class="chat-history-title-row">${thread.pinned ? `<i aria-label="Pinned">★ Pinned</i>` : ""}${editing ? `<form class="chat-history-rename" data-chat-history-rename-form="${esc(thread.id)}"><label class="sr-only" for="chat-title-${esc(thread.id)}">Chat title</label><input id="chat-title-${esc(thread.id)}" type="text" maxlength="72" value="${title}" required><button type="submit">Save</button><button type="button" data-chat-history-cancel-rename>Cancel</button></form>` : `<strong>${title}</strong>`}</div><span>${esc(`${routeLine} · ${thread.messageCount || 0} messages`)}</span>${resumeNote}${branch}${interrupted}<small title="${esc(thread.preview || "")}">${esc(`${chatHistoryDate(thread.updatedAt)}${thread.preview ? ` · ${thread.preview}` : ""}`)}</small></div>${actions}</article>`;
    }).join("") : `<div class="chat-history-empty">${query ? "No saved chats match that search." : "No previous chats yet. Completed turns will appear here automatically."}</div>`;
}

function chatResumePromptChoiceReady(plan = state.chatResumePlan) {
  if (!plan?.requiresSystemPrompt) return true;
  return Boolean($("chatResumeSystemPrompt").value || $("chatResumeWithoutPrompt").checked);
}

function renderChatResumePlan() {
  const plan = state.chatResumePlan;
  const loading = state.chatResumePlanLoading;
  const route = plan?.route;
  const blocked = Boolean(plan && plan.mode === "blocked");
  const choiceReady = chatResumePromptChoiceReady(plan);
  const memoryReady = !plan?.requiresMemoryAcknowledgement || $("chatResumeMemoryConsent").checked;
  const experimentalReady = !plan?.requiresExperimentalApproval || $("chatResumeExperimentalConsent").checked;
  const routeReady = Boolean(plan && !blocked && route && plan.request);
  $("chatResumeBadge").textContent = loading ? "Checking" : blocked ? "Blocked" : routeReady ? "Ready" : "Unavailable";
  $("chatResumeBadge").className = `setup-badge ${loading ? "active" : blocked ? "warning" : routeReady ? "ready" : ""}`;
  $("chatResumeTitle").textContent = plan?.thread?.title || "Resume previous chat";
  $("chatResumeSubtitle").textContent = route
    ? `${route.backendLabel} · ${route.model}`
    : "Review the exact saved route before anything starts.";
  $("chatResumeRoute").className = `chat-resume-route${blocked ? " blocked" : routeReady ? " ready" : ""}`;
  if (loading && !plan) {
    $("chatResumeRoute").innerHTML = "<p>Revalidating the saved engine, model, folder, controls, and current Mac capacity…</p>";
  } else if (route) {
    const mode = plan.mode === "reuse" ? "Reuse loaded weights" : plan.mode === "launch" ? "New local load" : "Blocked";
    const estimate = plan.admission?.estimate?.estimatedWorkingSetBytes;
    const reasoning = `${route.reasoning} · ${route.sampling === "custom" ? "custom" : "model defaults"}`;
    $("chatResumeRoute").innerHTML = `<div class="chat-resume-primary"><span><small>Engine</small><strong>${esc(route.backendLabel)}</strong></span><span><small>Model</small><strong title="${esc(route.model)}">${esc(route.model)}</strong></span><span><small>Action</small><strong>${esc(mode)}</strong></span></div><details id="chatResumeContract" class="chat-resume-contract"${activeDetail() === "detailed" ? " open" : ""}><summary><span><strong>Route details</strong><small>${esc(`${formatNumber(route.context)} context · ${formatNumber(route.output)} max · ${reasoning}`)}</small></span><i aria-hidden="true">⌄</i></summary><div class="chat-resume-facts"><span><small>Context</small><strong>${formatNumber(route.context)}</strong></span><span><small>Max response</small><strong>${formatNumber(route.output)}</strong></span><span><small>Reasoning · sampling</small><strong>${esc(reasoning)}</strong></span><span><small>Project folder</small><strong title="${esc(route.project)}">${esc(route.project)}</strong></span><span><small>Memory estimate</small><strong>${estimate ? formatBytes(estimate) : plan.mode === "reuse" ? "Already resident" : "Unavailable"}</strong></span><span><small>System prompt</small><strong>${plan.requiresSystemPrompt ? "Re-entry required" : "None saved or required"}</strong></span></div></details><p class="chat-resume-route-detail">${esc(plan.detail || "Review this exact route before starting.")}</p>`;
  } else {
    $("chatResumeRoute").innerHTML = `<p>${esc(plan?.detail || "This conversation has no resumable route snapshot.")}</p>`;
  }
  $("chatResumePromptPanel").classList.toggle("hidden", !plan?.requiresSystemPrompt);
  $("chatResumeSystemPrompt").disabled = $("chatResumeWithoutPrompt").checked || loading || state.chatResumeStarting;
  $("chatResumeMemoryPanel").classList.toggle("hidden", !plan?.requiresMemoryAcknowledgement);
  $("chatResumeMemoryTitle").textContent = plan?.admission?.label || "I reviewed this Mac capacity estimate.";
  $("chatResumeMemoryCopy").textContent = plan?.admission?.detail || "This one-time acknowledgement is bound to the exact saved route.";
  $("chatResumeExperimentalPanel").classList.toggle("hidden", !plan?.requiresExperimentalApproval);
  $("chatResumeStatus").textContent = loading
    ? "Checking only; no runtime, model weights, port, project files, or Chat surface has been opened."
    : plan?.detail || "Choose a resumable conversation.";
  $("chatResumeStatus").className = `session-dashboard-status${blocked ? " error" : ""}`;
  $("chatResumeApply").disabled = !routeReady || !choiceReady || loading || state.chatResumeStarting;
  $("chatResumeStart").disabled = !routeReady || !choiceReady || !memoryReady || !experimentalReady || loading || state.chatResumeStarting;
  $("chatResumeStartLabel").textContent = state.chatResumeStarting
    ? "Starting exact saved route…"
    : plan?.mode === "reuse" ? "No model reload" : plan?.mode === "launch" ? "Normal local safeguards apply" : "Route unavailable";
}

function chatResumeDecisionPayload(historyId = state.chatResumeHistoryId) {
  const payload = {id:historyId};
  if (!state.chatResumePlan?.requiresSystemPrompt) return payload;
  const prompt = $("chatResumeSystemPrompt").value;
  const without = $("chatResumeWithoutPrompt").checked;
  if (prompt && without) throw new Error("Choose a replacement system prompt or continue without it, not both.");
  if (!prompt && !without) throw new Error("Re-enter the original system prompt or explicitly continue without it.");
  if (prompt) payload.systemPrompt = prompt;
  else payload.continueWithoutSystemPrompt = true;
  return payload;
}

async function loadChatResumePlan(historyId, includeDecision = false) {
  const generation = ++state.chatResumeGeneration;
  state.chatResumePlanLoading = true;
  renderChatResumePlan();
  try {
    const payload = includeDecision ? chatResumeDecisionPayload(historyId) : {id:historyId};
    const data = await api("/api/chat/history/resume-plan", {
      method:"POST", body:JSON.stringify(payload),
    });
    if (generation !== state.chatResumeGeneration) return null;
    if (data.plan?.request && !uiRequestVisible(data.plan.request)) {
      state.chatResumePlan = {
        mode:"blocked", ready:false,
        detail:"This conversation is preserved, but its saved engine is temporarily hidden in this launcher build.",
        thread:data.plan.thread || {id:historyId, title:"Resume previous chat"},
      };
      return state.chatResumePlan;
    }
    state.chatResumePlan = data.plan;
    return data.plan;
  } catch (error) {
    if (generation === state.chatResumeGeneration) {
      state.chatResumePlan = {
        mode:"blocked", ready:false, detail:error.message,
        thread:{id:historyId, title:"Resume previous chat"},
      };
    }
    return null;
  } finally {
    if (generation === state.chatResumeGeneration) {
      state.chatResumePlanLoading = false;
      renderChatResumePlan();
    }
  }
}

async function openChatResumeDialog(historyId) {
  if (state.chatResumeStarting || !historyId) return;
  const thread = state.chatHistoryThreads.find(item => item.id === historyId);
  if (thread && !uiEngineVisible(thread.backend)) {
    showNotice("That transcript is still available in Chats, but its saved engine is temporarily hidden.");
    return;
  }
  state.chatResumeHistoryId = historyId;
  state.chatResumePlan = null;
  $("chatResumeSystemPrompt").value = "";
  $("chatResumeWithoutPrompt").checked = false;
  $("chatResumeMemoryConsent").checked = false;
  $("chatResumeExperimentalConsent").checked = false;
  if ($("chatHistoryDialog").open) $("chatHistoryDialog").close();
  if (!$("chatResumeDialog").open) $("chatResumeDialog").showModal();
  renderChatResumePlan();
  await loadChatResumePlan(historyId, false);
}

async function completePendingChatResume() {
  const pending = state.chatResumePending;
  if (
    !pending || state.chatResumeOpening || state.runPhase !== "running"
    || !state.chatRunId || state.chatAbort
  ) return;
  state.chatResumeOpening = true;
  try {
    await openChatHistoryThread(pending.historyId, {
      coldResume:true, skipCurrentSave:true,
      systemPromptDecision:pending.systemPromptDecision,
    });
  } finally {
    state.chatResumePending = null;
    state.chatResumeOpening = false;
    state.chatResumeStarting = false;
    renderChatHistory();
    renderQuickStart();
  }
}

async function applyChatResume(startAfter) {
  if (state.chatResumeStarting || !state.chatResumeHistoryId) return;
  state.chatResumeStarting = true;
  renderChatResumePlan();
  try {
    const plan = await loadChatResumePlan(state.chatResumeHistoryId, true);
    if (!plan?.ready || !plan.request || plan.mode === "blocked") {
      throw new Error(plan?.detail || "The saved Chat route is not ready.");
    }
    if (!uiRequestVisible(plan.request)) {
      throw new Error("This conversation's saved engine is temporarily hidden in this launcher build.");
    }
    if (startAfter && plan.requiresMemoryAcknowledgement && !$("chatResumeMemoryConsent").checked) {
      throw new Error("Review and approve the current Mac capacity estimate first.");
    }
    if (startAfter && plan.requiresExperimentalApproval && !$("chatResumeExperimentalConsent").checked) {
      throw new Error("Approve this one experimental FreeToken load first.");
    }
    const request = JSON.parse(JSON.stringify(plan.request));
    if (startAfter && plan.requiresMemoryAcknowledgement) {
      request.memoryAcknowledgement = plan.admission?.contractId || "";
    }
    if (startAfter && plan.requiresExperimentalApproval) {
      request.options = {...(request.options || {}), experimentalQualificationConsent:true};
    }
    applyProfileRequest(request);
    if (!startAfter) {
      setQuickStartEditor(true);
      $("chatResumeDialog").close();
      showNotice(`Applied the saved route for “${plan.thread?.title || "Local chat"}”. Nothing was started.`);
      state.chatResumeStarting = false;
      renderChatResumePlan();
      renderQuickStart();
      return;
    }
    state.chatResumePending = {
      historyId:state.chatResumeHistoryId,
      systemPromptDecision:plan.systemPromptDecision || "not-required",
    };
    $("chatResumeDialog").close();
    const started = await launch(request, {warmPlan:plan.warmRoute});
    if (!started) {
      state.chatResumePending = null;
      state.chatResumeStarting = false;
      renderChatResumePlan();
      return;
    }
    await completePendingChatResume();
  } catch (error) {
    state.chatResumePending = null;
    state.chatResumeStarting = false;
    $("chatResumeStatus").textContent = error.message;
    $("chatResumeStatus").className = "session-dashboard-status error";
    if (!$("chatResumeDialog").open) $("chatResumeDialog").showModal();
    renderChatResumePlan();
  }
}

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
    renderChatHistory();
    renderChatSidebar();
    await restorePendingChatDraftConversation();
    return;
  }
  state.chatHistoryLoading = true;
  renderChatHistory();
  renderChatSidebar();
  let loaded = false;
  try {
    await recoverInterruptedChatTurn();
    const data = await api("/api/chat/history");
    state.chatHistoryThreads = Array.isArray(data.threads) ? data.threads : [];
    state.chatHistoryLoaded = true;
    loaded = true;
    $("chatHistoryStatus").textContent = state.runPhase === "running" && state.chatRunId
      ? "Open uses the current Chat route. Saved routes can also be reviewed later without loading a model."
      : "Resumable conversations can re-open their exact saved route after a read-only review. Older conversations remain readable and exportable.";
    $("chatHistoryStatus").className = "session-dashboard-status";
  } catch (error) {
    $("chatHistoryStatus").textContent = error.message;
    $("chatHistoryStatus").className = "session-dashboard-status error";
  } finally {
    state.chatHistoryLoading = false;
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
    renderChatHistory();
    renderChatSidebar();
  }
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
      lines.push("_Recovered partial response: generation was interrupted when the launcher page closed._", "");
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
    || state.chatHistoryBusyId || state.runPhase !== "running" || !state.chatRunId
  ) return;
  persistChatSessionState();
  if (!options.skipCurrentSave) await saveCurrentChatHistory();
  state.chatHistoryBusyId = historyId;
  renderChatHistory();
  renderChatSidebar();
  try {
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
  } catch (error) {
    $("chatHistoryStatus").textContent = error.message;
    $("chatHistoryStatus").className = "session-dashboard-status error";
  } finally {
    state.chatHistoryBusyId = "";
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
    renderChatHistory();
    renderChatSidebar();
  }
}

function updateChatWorkspace(run, phase) {
  const primaryChat = run?.client === "chat" && run?.purpose === "session";
  if (!run || (state.chatOwnerRunId && state.chatOwnerRunId !== run.runId)) {
    if (!$("chatRunSettingsPanel").hidden) closeChatRunSettings(false);
    state.chatRunSettings = null;
    state.chatRunSettingsKey = "";
    if (state.chatAbort) state.chatAbort.abort();
    persistChatSessionState();
    state.chatRunId = "";
    state.chatOwnerRunId = "";
    state.chatAttachment = null;
    resetChatConversation();
    $("chatInput").value = "";
    sizeChatInput();
    renderChatDraftStatus();
  }
  const selectedAttachment = Boolean(
    state.chatAttachment?.client === "chat"
    && state.chatAttachment.ownerRunId === run?.runId
  );
  if (primaryChat && run.runId && !selectedAttachment && state.chatRunId !== run.runId) {
    if (state.chatAbort) state.chatAbort.abort();
    persistChatSessionState();
    state.chatRunId = run.runId;
    state.chatOwnerRunId = run.runId;
    state.chatAttachment = {
      id:run.runId, ownerRunId:run.runId, primary:true, client:"chat",
      surface:"Chat", backend:run.backend, model:run.model,
      context:run.context, output:run.output, reasoning:run.reasoning,
    };
    resetChatConversation();
    state.chatRunId = run.runId;
    state.chatOwnerRunId = run.runId;
    activateChatDraft(run.runId, {restoreActive:true});
    renderChatMessages();
  }
  const chatRun = primaryChat || selectedAttachment;
  const visible = chatRun && ["running", "stopping"].includes(phase) && !state.agentConsoleVisible;
  const controlsReady = Boolean(visible && phase === "running");
  $("chatRunSettingsButton").disabled = !controlsReady;
  if (!controlsReady && !$("chatRunSettingsPanel").hidden) closeChatRunSettings(false);
  if (!visible) {
    state.chatRunSettings = null;
    state.chatRunSettingsKey = "";
  }
  $("chatWorkspace").classList.toggle("hidden", !visible);
  $("configScroll").classList.toggle("hidden", visible);
  $("launchDock").classList.toggle("hidden", visible);
  if (visible) {
    $("configTitle").textContent = "Chat";
    const route = chatSurfaceRoute(run);
    $("configSubtitle").textContent = `${profileBackendLabel(route?.backend)} · ${route?.model || "Local model"}`;
    renderChatRoute(run);
    renderChatUsage();
    renderChatSidebar();
    if (!state.chatHistoryLoaded && !state.chatHistoryLoading) void loadChatHistory(false);
    $("endChatButton").textContent = state.chatAttachment?.primary === false ? "End attached chat" : "End chat";
    if (controlsReady && state.chatResumePending) void completePendingChatResume();
  } else {
    $("configTitle").textContent = "Launch configuration";
  }
  setChatBusy(Boolean(state.chatAbort));
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
  };
}

function currentAgentConsoleView() {
  return state.agentConsoleViews[state.agentConsoleSurfaceId] || null;
}

function reconcileAgentConsoleViewMeta(view, incoming = {}) {
  if (!view) return {meta:{...incoming}, generationChanged:false, stale:false};
  const result = AgentConsoleTabsCore.reconcileConsoleMeta(view.meta, incoming);
  view.meta = result.meta;
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
  view.offset = base;
  view.renderedText = "";
  view.loaded = false;
  if (clearInput) view.inputQueue = [];
  if (renderPlaceholder && view === currentAgentConsoleView()) {
    $("agentTerminalOutput").textContent = "Waiting for agent output…";
    $("agentTerminalOutput").dataset.consoleSurface = state.agentConsoleSurfaceId;
    $("agentConsoleJumpLatest").hidden = true;
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
  if (state.agentConsoleTimer !== null) clearTimeout(state.agentConsoleTimer);
  if (state.agentConsoleResizeTimer !== null) clearTimeout(state.agentConsoleResizeTimer);
  state.agentConsoleTimer = null;
  state.agentConsoleResizeTimer = null;
  state.agentConsoleOwnerRunId = "";
  state.agentConsoleSurfaceId = "";
  state.agentConsoleMeta = null;
  state.agentConsoleViews = {};
  state.agentConsoleRecoveryOwnerRunId = "";
  state.agentConsoleVisible = false;
  state.agentConsoleReading = false;
  state.agentConsoleSearchOpen = false;
  state.agentConsoleSearchQuery = "";
  state.agentConsoleSearchIndex = -1;
  $("agentConsoleTabs").replaceChildren();
  $("agentConsoleSearch").classList.add("hidden");
  $("agentConsoleFindButton").setAttribute("aria-expanded", "false");
  $("agentConsoleSearchInput").value = "";
  resetAgentConsoleTerminal(null);
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

function syncAgentConsoleViews(status = state.runStatus, run = status?.run, phase = status?.phase || state.runPhase) {
  const routeActive = Boolean(
    run?.purpose === "session" && run.runId
    && ["preflight","starting","running","stopping"].includes(phase),
  );
  if (!routeActive) {
    if (state.agentConsoleOwnerRunId || Object.keys(state.agentConsoleViews).length) clearAgentConsoleSelection(true);
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
    if (!allowed.has(id)) delete state.agentConsoleViews[id];
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
      const reconciliation = reconcileAgentConsoleViewMeta(view, descriptor.meta);
      if (reconciliation.generationChanged || AgentConsoleTabsCore.consoleNeedsReplay(view.meta, view.offset)) {
        view.recovering = true;
      }
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
    reconcileAgentConsoleViewMeta(state.agentConsoleViews[surfaceId], attachment);
  }
  selectAgentConsole(surfaceId, {focus:true, show:true});
  if ($("sessionDialog")?.open) $("sessionDialog").close();
}

function selectAgentConsole(surfaceId, {focus = true, show = true} = {}) {
  const view = state.agentConsoleViews[surfaceId];
  if (!view) return;
  if (state.agentConsoleTimer !== null) clearTimeout(state.agentConsoleTimer);
  state.agentConsoleTimer = null;
  state.agentConsoleSurfaceId = surfaceId;
  state.agentConsoleMeta = view.meta;
  state.agentConsoleVisible = show;
  state.agentConsoleDismissed = !show;
  state.agentConsoleSearchIndex = -1;
  view.seenEnd = Math.max(view.seenEnd, view.offset);
  persistAgentConsoleRecovery();
  if (state.runStatus?.run?.runId === state.agentConsoleOwnerRunId) {
    updateChatWorkspace(state.runStatus.run, state.runPhase);
    updateAgentWorkspace(state.runStatus.run, state.runPhase);
    renderAgentTerminalOutput({preserveScroll:false});
  }
  scheduleAgentConsoleRead(view.loaded ? 0 : 40);
  scheduleAgentConsoleResize();
  if (focus) requestAnimationFrame(() => $("agentTerminalViewport").focus());
}

function leaveAgentConsole() {
  state.agentConsoleVisible = false;
  state.agentConsoleDismissed = true;
  if (state.agentConsoleTimer !== null) clearTimeout(state.agentConsoleTimer);
  state.agentConsoleTimer = null;
  persistAgentConsoleRecovery();
  updateChatWorkspace(state.runStatus?.run, state.runPhase);
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

function agentConsoleProjectName(value) {
  return String(value || "").split("/").filter(Boolean).pop() || "Project";
}

function renderAgentConsoleTabs() {
  const views = Object.entries(state.agentConsoleViews);
  const tabs = $("agentConsoleTabs");
  const rows = views.map(([id, view]) => {
    const activity = agentConsoleRequestActivity(id).current;
    const attachment = view.meta;
    const consoleRecord = view.meta;
    const active = id === state.agentConsoleSurfaceId;
    const presentation = AgentConsoleTabsCore.tabPresentation({
      attachment, consoleRecord, activity, active, seenEnd:view.seenEnd,
    });
    view.unreadBytes = active && state.agentConsoleVisible ? Math.max(0, presentation.end - view.offset) : presentation.unreadBytes;
    const surface = attachment.surface || clientName(attachment.client) || "Agent";
    const project = agentConsoleProjectName(attachment.project);
    const marker = attachment.primary ? "Primary" : project;
    const label = `${surface}, ${marker}, ${presentation.label}`;
    const badge = presentation.unreadBytes > 0 && !active
      ? `${presentation.label} · ${formatBytes(presentation.unreadBytes)}` : presentation.label;
    return `<button id="agent-console-tab-${esc(id)}" type="button" role="tab" data-agent-console-tab="${esc(id)}" aria-selected="${active}" aria-controls="agentTerminalViewport" aria-label="${esc(label)}" tabindex="${active ? "0" : "-1"}" class="agent-console-tab ${active ? "active" : ""} ${esc(presentation.tone)}"><i aria-hidden="true"></i><span><strong>${esc(surface)}</strong><small>${esc(marker)}</small></span><em>${esc(badge)}</em></button>`;
  });
  const markup = rows.join("");
  if (tabs.innerHTML !== markup) tabs.innerHTML = markup;
  const view = currentAgentConsoleView();
  $("agentConsoleFindButton").disabled = !view;
  $("agentConsoleCopyButton").disabled = !view?.renderedText || state.agentConsoleCopyBusy;
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
  return viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 64;
}

function updateAgentConsoleScrollUi() {
  const button = $("agentConsoleJumpLatest");
  button.hidden = !currentAgentConsoleView() || agentConsoleNearBottom();
}

function scrollAgentConsoleToLatest() {
  const viewport = $("agentTerminalViewport");
  viewport.scrollTop = viewport.scrollHeight;
  updateAgentConsoleScrollUi();
  viewport.focus({preventScroll:true});
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
  if (!view?.renderedText || state.agentConsoleCopyBusy) return;
  state.agentConsoleCopyBusy = true;
  renderAgentConsoleTabs();
  try {
    await navigator.clipboard.writeText(view.renderedText);
    showNotice("Copied the bounded visible Agent Console text.");
  } catch (error) {
    showNotice(`Could not copy the Agent Console: ${error.message}`, true);
  } finally {
    state.agentConsoleCopyBusy = false;
    renderAgentConsoleTabs();
  }
}

function renderAgentConsole() {
  const view = currentAgentConsoleView();
  const attachment = currentAgentConsoleAttachment() || view?.meta || state.agentConsoleMeta || {};
  const record = currentAgentConsoleRecord();
  if (view) {
    reconcileAgentConsoleViewMeta(view, attachment);
    if (record) reconcileAgentConsoleViewMeta(view, record);
    state.agentConsoleMeta = view.meta;
  }
  const meta = view?.meta || attachment;
  const surface = meta.surface || clientName(meta.client) || "Agent";
  const stateLabel = String(meta.state || meta.status || "starting");
  $("agentConsoleTitle").textContent = `${surface} · Hub Console`;
  $("agentConsoleInputLabel").textContent = `Message ${surface}`;
  $("agentConsoleInput").placeholder = `Ask ${surface}…`;
  $("agentConsoleMeta").textContent = meta.project
    ? `${meta.project} · agent-supplied terminal styling is preserved; output is bounded in memory and never saved by the launcher.`
    : "Agent-supplied terminal styling is preserved; output stays in bounded session memory and never enters Chat history.";
  $("agentConsoleRoute").textContent = meta.backend
    ? `${backendName(meta.backend)} → ${surface} · ${meta.model || "Local model"}`
    : "Waiting for the active model";
  $("agentConsoleStatusSurface").textContent = meta.backend
    ? `${surface} · ${backendName(meta.backend)}` : surface;
  $("agentConsoleStatusModel").textContent = [
    meta.model || "Waiting for the active model",
    meta.project ? agentConsoleProjectName(meta.project) : "Project unavailable",
  ].join(" · ");

  const activity = agentConsoleRequestActivity();
  const compactActivity = ChatStatusCore.activitySummary(activity.report, state.agentConsoleSurfaceId);
  const currentMeasured = requestTps(activity.current);
  const latestMeasured = requestTps(activity.latest);
  const detailedMeasured = currentMeasured || (!activity.current ? latestMeasured : null);
  $("agentConsoleTps").textContent = detailedMeasured?.compact || compactActivity.speed.value;
  $("agentConsoleTps").title = compactActivity.speed.title;
  const firstOutput = activity.current?.firstOutputSeconds ?? activity.latest?.firstOutputSeconds;
  $("agentConsoleTtft").textContent = firstOutput !== null && firstOutput !== undefined
    ? formatShortDuration(firstOutput) : activity.current ? "Waiting…" : "—";
  const livePhase = liveRequestPhaseLabel(activity.current);
  $("agentConsoleLane").textContent = activity.current?.state === "queued"
    ? `Queue #${formatNumber(activity.current.queuePosition || 1)}`
    : activity.current?.state === "running" ? `${livePhase || "Generating"} · ${formatShortDuration(activity.current.runSeconds || 0)}`
      : activity.report.engineResident ? `${formatNumber(activity.report.lanes || 1)} lane${Number(activity.report.lanes || 1) === 1 ? "" : "s"} · idle` : "Relay unavailable";

  const speedSignal = $("agentConsoleStatusSpeed");
  const laneSignal = $("agentConsoleStatusLane");
  $("agentConsoleStatusSpeedValue").textContent = compactActivity.speed.value;
  speedSignal.dataset.state = compactActivity.speed.state;
  speedSignal.title = compactActivity.speed.title;
  $("agentConsoleStatusLaneValue").textContent = livePhase || compactActivity.lane.value;
  laneSignal.dataset.state = compactActivity.lane.state;
  laneSignal.title = [$("agentConsoleLane").textContent, liveRequestDetail(activity.current)].filter(Boolean).join(". ");
  const processLabels = {
    starting:"Starting", stopping:"Stopping", failed:"Failed",
    exited:"Exited", stopped:"Stopped",
  };
  const processLabel = processLabels[stateLabel] || "";
  $("agentConsoleStatusState").textContent = processLabel;
  $("agentConsoleStatusState").hidden = !processLabel;
  $("agentConsoleStatusPanel").dataset.activityState = compactActivity.lane.state;
  $("agentConsoleStatusPanel").dataset.processState = stateLabel;
  updateAgentConsoleStatusSummaryLabel();

  const canInput = Boolean(meta.canInput ?? stateLabel === "running");
  $("agentConsoleInput").disabled = !canInput || state.agentConsoleBusy;
  $("agentConsoleEnterButton").disabled = !canInput || state.agentConsoleBusy;
  $("agentConsoleEscapeButton").disabled = !canInput || state.agentConsoleBusy;
  $("agentConsoleInterruptButton").disabled = !canInput || state.agentConsoleBusy;
  $("agentConsoleStopButton").disabled = state.agentConsoleBusy || !(meta.canStop ?? ["starting","running","stopping"].includes(stateLabel));
  $("agentConsoleRestartButton").disabled = state.agentConsoleBusy || !(meta.canRestart ?? ["exited","stopped","failed"].includes(stateLabel));
  const dropped = Number(meta.droppedBytes || 0);
  $("agentConsoleStatus").textContent = `${view?.recovering ? "Restoring the latest console screen… " : ""}${meta.detail || `Hub Console is ${stateLabel}.`}${dropped ? ` Earlier output was discarded after the 2 MB memory cap (${formatBytes(dropped)} dropped).` : ""}`;
  $("agentConsoleStatus").className = stateLabel === "failed" ? "error" : "";
  renderAgentConsoleTabs();
}

function updateAgentWorkspace(run, phase) {
  const routeActive = Boolean(run && ["preflight","starting","running","stopping"].includes(phase));
  if (routeActive) syncAgentConsoleViews(state.runStatus, run, phase);
  else if (state.agentConsoleOwnerRunId) clearAgentConsoleSelection(true);
  const view = currentAgentConsoleView();
  const selected = view?.meta || state.agentConsoleMeta;
  const visible = Boolean(state.agentConsoleVisible && routeActive && selected);
  $("agentWorkspace").classList.toggle("hidden", !visible);
  if (visible) $("chatWorkspace").classList.add("hidden");
  const chatVisible = !$("chatWorkspace").classList.contains("hidden");
  $("configScroll").classList.toggle("hidden", visible || chatVisible);
  $("launchDock").classList.toggle("hidden", visible || chatVisible);
  if (visible) {
    $("configTitle").textContent = "Agent Console";
    $("configSubtitle").textContent = `${selected.surface || clientName(selected.client)} · ${selected.model || run?.model || "Local model"}`;
    renderAgentConsole();
    if ($("agentTerminalOutput").dataset.consoleSurface !== state.agentConsoleSurfaceId) {
      renderAgentTerminalOutput({preserveScroll:false});
    }
    scheduleAgentConsoleRead(0);
  } else if (!chatVisible) {
    $("configTitle").textContent = "Launch configuration";
    updateWorkSurface();
  }
}

function scheduleAgentConsoleRead(delay = 120) {
  if (!state.agentConsoleVisible || !state.agentConsoleOwnerRunId || !currentAgentConsoleView()) return;
  if (state.agentConsoleTimer !== null || state.agentConsoleReading) return;
  state.agentConsoleTimer = setTimeout(() => {
    state.agentConsoleTimer = null;
    void readAgentConsole();
  }, Math.max(0, Number(delay) || 0));
}

function decodeAgentConsoleChunk(view, value) {
  if (!value) return "";
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return view.decoder.decode(bytes, {stream:true});
}

async function readAgentConsole() {
  if (state.agentConsoleReading || !state.agentConsoleVisible) return;
  const ownerRunId = state.agentConsoleOwnerRunId;
  const surfaceId = state.agentConsoleSurfaceId;
  const requestedView = state.agentConsoleViews[surfaceId];
  if (!requestedView) return;
  state.agentConsoleReading = true;
  let nextDelay = null;
  try {
    const data = await api("/api/agent-console/read", {
      method:"POST", body:JSON.stringify({ownerRunId, surfaceId, offset:requestedView.offset}),
    });
    const view = state.agentConsoleViews[surfaceId];
    if (!view || ownerRunId !== state.agentConsoleOwnerRunId) return;
    const output = data.console;
    if (output.reset) {
      resetAgentConsoleTerminal(view, output.baseOffset, {
        renderPlaceholder:false, clearInput:false,
      });
    }
    const decoded = decodeAgentConsoleChunk(view, output.data);
    if (decoded) view.terminal.write(decoded);
    view.offset = AgentConsoleTabsCore.safeOffset(output.nextOffset ?? view.offset);
    view.loaded = true;
    view.recovering = false;
    reconcileAgentConsoleViewMeta(view, output);
    const stillActive = surfaceId === state.agentConsoleSurfaceId && state.agentConsoleVisible;
    if (stillActive) {
      view.seenEnd = Math.max(view.seenEnd, view.offset);
      state.agentConsoleMeta = view.meta;
      renderAgentTerminalOutput();
      renderAgentConsole();
      const backlog = agentConsoleBufferEnd(output) > view.offset;
      nextDelay = backlog ? 0 : output.state === "running" ? 120 : null;
    }
    persistAgentConsoleRecovery();
  } catch (error) {
    const stillActive = ownerRunId === state.agentConsoleOwnerRunId && surfaceId === state.agentConsoleSurfaceId;
    if (stillActive && ["preflight","starting"].includes(state.runPhase)) nextDelay = 500;
    else if (stillActive) {
      $("agentConsoleStatus").textContent = error.message;
      $("agentConsoleStatus").className = "error";
      nextDelay = 1000;
    }
  } finally {
    state.agentConsoleReading = false;
    if (state.agentConsoleVisible && nextDelay !== null) scheduleAgentConsoleRead(nextDelay);
    else if (state.agentConsoleVisible && surfaceId !== state.agentConsoleSurfaceId) scheduleAgentConsoleRead(0);
  }
}

function queueAgentConsoleInput(value) {
  const view = currentAgentConsoleView();
  if (!value || !view || !state.agentConsoleOwnerRunId || !state.agentConsoleSurfaceId) return;
  view.inputQueue.push(String(value));
  void flushAgentConsoleInput(view, state.agentConsoleOwnerRunId, state.agentConsoleSurfaceId);
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

async function flushAgentConsoleInput(view, ownerRunId, surfaceId) {
  if (!view || view.inputSending) return;
  view.inputSending = true;
  try {
    while (view.inputQueue.length) {
      let value = "";
      while (view.inputQueue.length && value.length < 60000) {
        value += view.inputQueue.shift();
      }
      const data = await api("/api/agent-console/input", {
        method:"POST", body:JSON.stringify({ownerRunId, surfaceId, data:value}),
      });
      if (state.agentConsoleViews[surfaceId] === view && ownerRunId === state.agentConsoleOwnerRunId) {
        reconcileAgentConsoleViewMeta(view, data.console);
      }
      if (surfaceId === state.agentConsoleSurfaceId) {
        state.agentConsoleMeta = view.meta;
        renderAgentConsole();
      }
    }
  } catch (error) {
    view.inputQueue = [];
    if (surfaceId === state.agentConsoleSurfaceId) {
      $("agentConsoleStatus").textContent = error.message;
      $("agentConsoleStatus").className = "error";
    }
  } finally {
    view.inputSending = false;
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
  state.agentConsoleBusy = true;
  renderAgentConsole();
  try {
    const data = await api("/api/agent-console/stop", {
      method:"POST", body:JSON.stringify({ownerRunId:target.ownerRunId, surfaceId:target.id || target.surfaceId}),
    });
    if (state.runStatus) {
      state.runStatus = {...state.runStatus, attachments:data.hub?.attachments || state.runStatus.attachments, agentConsoles:data.hub?.agentConsoles || []};
    }
    if (state.sessionDashboard) state.sessionDashboard.hub = data.hub;
    syncAgentConsoleViews(state.runStatus, state.runStatus?.run, state.runPhase);
    const targetId = target.id || target.surfaceId;
    const view = state.agentConsoleViews[targetId];
    if (view) reconcileAgentConsoleViewMeta(view, data.console);
    if (targetId === state.agentConsoleSurfaceId && view) state.agentConsoleMeta = view.meta;
    renderAgentConsole();
    if ($("sessionDialog")?.open) await loadSessionDashboard();
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    state.agentConsoleBusy = false;
    renderAgentConsole();
  }
}

async function restartAgentConsoleSurface(attachment = null) {
  const target = attachment || currentAgentConsoleAttachment() || state.agentConsoleMeta;
  if (!target || state.agentConsoleBusy) return;
  state.agentConsoleBusy = true;
  renderAgentConsole();
  try {
    const data = await api("/api/agent-console/restart", {
      method:"POST", body:JSON.stringify({ownerRunId:target.ownerRunId, surfaceId:target.id || target.surfaceId}),
    });
    if (state.runStatus) {
      state.runStatus = {...state.runStatus, attachments:data.hub?.attachments || state.runStatus.attachments, agentConsoles:data.hub?.agentConsoles || []};
    }
    if (state.sessionDashboard) state.sessionDashboard.hub = data.hub;
    syncAgentConsoleViews(state.runStatus, state.runStatus?.run, state.runPhase);
    const targetId = target.id || target.surfaceId;
    const view = state.agentConsoleViews[targetId];
    if (view) {
      reconcileAgentConsoleViewMeta(view, data.console);
      view.seenEnd = 0;
      resetAgentConsoleTerminal(view, 0);
    }
    if (targetId === state.agentConsoleSurfaceId && view) {
      state.agentConsoleMeta = view.meta;
      state.agentConsoleVisible = true;
      renderAgentTerminalOutput({preserveScroll:false});
      scheduleAgentConsoleRead(0);
      scheduleAgentConsoleResize();
    }
    if ($("sessionDialog")?.open) await loadSessionDashboard();
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    state.agentConsoleBusy = false;
    renderAgentConsole();
  }
}

function renderFocusedRunStatus({phase, message, active, stopLabel, logAvailable}) {
  const panel = $("focusedRunStatus");
  if (!panel) return;
  const safePhase = String(phase || "idle");
  const safeStopLabel = String(stopLabel || "Stop process");
  panel.dataset.phase = safePhase;
  $("focusedRunPhase").textContent = safePhase;
  $("focusedRunMessage").textContent = message || "Ready";
  $("focusedStopButton").disabled = !active;
  $("focusedStopButton").setAttribute("aria-label", safeStopLabel);
  $("focusedStopButton").title = safeStopLabel;
  $("focusedLogButton").disabled = !logAvailable;
}

function renderRun(status) {
  const phase = status.phase || "idle";
  state.runStatus = status;
  state.runPhase = phase;
  if (status.cache) state.cacheObservatory = status.cache;
  else if (phase !== "running") state.cacheObservatory = null;
  if (status.activity) state.requestActivity = status.activity;
  else if (!["preflight","starting","running","stopping"].includes(phase)) state.requestActivity = null;
  renderRequestActivity(state.requestActivity);
  renderCacheObservatory(state.cacheObservatory);
  const runActive = ["preflight","starting","running","stopping"].includes(phase);
  if (state.chatResumePending && !runActive) {
    const title = state.chatHistoryThreads.find(item => item.id === state.chatResumePending.historyId)?.title || "saved chat";
    state.chatResumePending = null;
    state.chatResumeStarting = false;
    showNotice(`Could not resume “${title}”: ${status.message || "the saved route stopped before Chat became ready."}`, true);
  }
  const setupActive = setupIsActive();
  const acquisitionActive = acquisitionIsActive();
  const routeCheckActive = routeCheckIsActive();
  const benchmarkActive = ["queued","cooldown","starting","running","stopping"].includes(state.benchmarkPhase);
  const aneActive = aneWorkIsActive();
  const displayPhase = acquisitionActive ? state.acquisitionPhase : (setupActive ? state.setupPhase : (routeCheckActive ? state.routeCheckPhase : (aneActive ? (aneCloneIsActive() ? state.aneClonePhase : state.anePhase) : (benchmarkActive && !runActive ? state.benchmarkPhase : phase))));
  const displayMessage = acquisitionActive
    ? state.acquisitionStatus?.message
    : setupActive
    ? state.setupStatus?.message
    : (routeCheckActive ? state.routeCheckStatus?.message : (aneActive ? (aneCloneIsActive() ? state.aneCloneStatus?.message : state.aneStatus?.message) : (benchmarkActive && !runActive ? state.benchmarkStatus?.message : status.message)));
  const anyActive = runActive || setupActive || acquisitionActive || routeCheckActive || benchmarkActive || aneActive;
  const stopLabel = acquisitionActive ? "Stop model download" : (setupActive ? "Stop download" : (routeCheckActive ? "Stop Route Check" : (aneActive ? (aneCloneIsActive() ? "Stop FP16 copy" : "Stop ANE Tuner") : (benchmarkActive && !runActive ? "Stop benchmark" : "Stop process"))));
  $("phaseBadge").textContent = displayPhase;
  $("statusMessage").textContent = displayMessage || "Ready";
  $("stopButton").disabled = !anyActive;
  $("stopButton").textContent = stopLabel;
  $("logButton").disabled = phase === "idle";
  renderFocusedRunStatus({phase:displayPhase, message:displayMessage, active:anyActive, stopLabel, logAvailable:phase !== "idle"});
  $("healthPill").className = `status-pill ${displayPhase}`;
  if (status.run) {
    const run = status.run;
    const route = run.purpose === "benchmark" ? `${run.backend} → Benchmark Lab` : (run.purpose === "route-check" ? `${run.backend} → Route Check` : (run.purpose === "ane-tune" ? "oMLX → ANE Tuner" : `${run.backend} → ${clientName(run.client)}`));
    $("runFacts").classList.remove("hidden");
    const clientRouteLabel = run.purpose === "session" ? "Session relay" : "Compatibility guard";
    $("runFacts").innerHTML = `<div><span>Model</span><b>${esc(run.model)}</b></div><div><span>Route</span><b>${esc(route)}</b></div><div><span>Context</span><b>${formatNumber(run.context)}</b></div><div><span>Model API</span><b>127.0.0.1:${run.port}</b></div>${run.clientPort !== run.port ? `<div><span>${clientRouteLabel}</span><b>127.0.0.1:${run.clientPort}</b></div>` : ""}`;
  } else if (acquisitionActive && state.acquisitionStatus?.plan) {
    const acquisition = state.acquisitionStatus;
    $("runFacts").classList.remove("hidden");
    $("runFacts").innerHTML = `<div><span>Model</span><b>${esc(acquisition.plan.repo?.id || "Pinned model")}</b></div><div><span>Route</span><b>Public pinned acquisition</b></div><div><span>Progress</span><b>${Math.round(Number(acquisition.progress || 0) * 100)}%</b></div>`;
  } else if (setupActive && state.setupStatus?.plan) {
    const setup = state.setupStatus;
    $("runFacts").classList.remove("hidden");
    $("runFacts").innerHTML = `<div><span>Model</span><b>${esc(setup.plan.target?.name || "DFlash 2 draft")}</b></div><div><span>Route</span><b>Pinned model download</b></div><div><span>Progress</span><b>${Math.round(Number(setup.progress || 0) * 100)}%</b></div>`;
  } else if (routeCheckActive && state.routeCheckStatus?.job) {
    const check = state.routeCheckStatus;
    $("runFacts").classList.remove("hidden");
    $("runFacts").innerHTML = `<div><span>Model</span><b>${esc(check.job.model || "Selected model")}</b></div><div><span>Route</span><b>${esc(`${check.job.backendLabel} → ${check.job.surface}`)}</b></div><div><span>Progress</span><b>${Math.round(Number(check.progress || 0) * 100)}%</b></div>`;
  } else if (aneActive && state.aneStatus?.job) {
    const tuning = state.aneStatus;
    $("runFacts").classList.remove("hidden");
    $("runFacts").innerHTML = `<div><span>Model</span><b>${esc(tuning.job.model || "Qwen")}</b></div><div><span>Route</span><b>Private ANE measurement</b></div><div><span>Progress</span><b>${Math.round(Number(tuning.progress || 0) * 100)}%</b></div>`;
  } else $("runFacts").classList.add("hidden");
  refreshLaunchability();
  syncAgentConsoleViews(status, status.run, phase);
  updateChatWorkspace(status.run, phase);
  updateAgentWorkspace(status.run, phase);
  if ($("sessionSetDialog")?.open) renderSessionSets();
}

async function pollStatus() {
  try {
    renderRun(await api("/api/status"));
    if ($("sessionDialog")?.open && Date.now() - state.sessionLastLoadedAt >= 4500) loadSessionDashboard();
  } catch (_) {}
}

function benchmarkHistoryRequest() {
  const request = gather("custom");
  request.suite = $("benchmarkSuiteSelect").value;
  request.enginePreference = $("benchmarkPreferenceSelect").value;
  return request;
}

function benchmarkHistoryRequestKey(request) {
  return JSON.stringify({
    modelId:request.modelId, backend:request.backend, client:request.client,
    context:request.context, output:request.output, reasoning:request.reasoning,
    kv:request.options?.kv || "off", chat:request.chat || null,
    suite:request.suite, enginePreference:request.enginePreference,
  });
}

function benchmarkHistoryDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unknown time" : date.toLocaleString([], {dateStyle:"medium",timeStyle:"short"});
}

function benchmarkHistorySparkline(series) {
  const points = series.points || [];
  if (points.length < 2) return `<span class="benchmark-history-baseline">Run again to create a trend</span>`;
  const width = 112, height = 30, pad = 3;
  const performance = points.map(point => series.lowerIsBetter ? -Number(point.value) : Number(point.value));
  const low = Math.min(...performance), high = Math.max(...performance);
  const span = Math.max(0.000001, high - low);
  const coordinates = performance.map((value, index) => {
    const x = pad + index * (width - pad * 2) / Math.max(1, performance.length - 1);
    const y = height - pad - (value - low) / span * (height - pad * 2);
    return [x, y];
  });
  const line = coordinates.map(([x,y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const [lastX,lastY] = coordinates.at(-1);
  return `<svg class="benchmark-history-sparkline" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(series.label)} trend across ${points.length} matching runs"><polyline points="${line}"></polyline><circle cx="${lastX.toFixed(1)}" cy="${lastY.toFixed(1)}" r="2.4"></circle></svg>`;
}

function renderBenchmarkHistory() {
  const history = state.benchmarkHistory;
  const badge = $("benchmarkHistoryBadge");
  const freshness = $("benchmarkHistoryFreshness");
  const active = ["queued","cooldown","starting","running","stopping"].includes(state.benchmarkPhase);
  if (state.benchmarkHistoryLoading && !history) {
    badge.textContent = "Loading…";
    freshness.className = "benchmark-history-freshness";
    freshness.textContent = "Checking saved local evidence for every visible contract field…";
    $("benchmarkHistoryTrend").innerHTML = "";
    $("benchmarkHistoryRuns").innerHTML = "";
    $("benchmarkHistoryOther").innerHTML = "";
    $("benchmarkHistoryRerun").disabled = true;
    return;
  }
  if (!history) {
    badge.textContent = "Unavailable";
    freshness.className = "benchmark-history-freshness warning";
    freshness.textContent = state.benchmarkHistoryError || "History could not be loaded for this selection.";
    $("benchmarkHistoryRerun").disabled = true;
    return;
  }
  badge.textContent = history.shootoutCount
    ? `${history.shootoutCount} matching shootout${history.shootoutCount === 1 ? "" : "s"}`
    : (history.currentRouteRuns?.length ? `${history.currentRouteRuns.length} route run${history.currentRouteRuns.length === 1 ? "" : "s"}` : "No exact runs");
  freshness.className = `benchmark-history-freshness ${history.freshness === "current" ? "current" : "warning"}`;
  freshness.textContent = history.freshnessMessage;
  $("benchmarkHistoryTrend").innerHTML = (history.series || []).map(series => {
    const latest = series.points?.at(-1);
    const change = series.improvementPercent;
    const changeClass = typeof change === "number" ? (change > 0.5 ? "improved" : (change < -0.5 ? "regressed" : "flat")) : "flat";
    const changeText = typeof change === "number"
      ? `${change > 0 ? "+" : ""}${change.toFixed(1)}% vs previous`
      : `${series.points?.length || 0} matching run${series.points?.length === 1 ? "" : "s"}`;
    return `<article class="benchmark-history-series"><div><strong>${esc(series.label)}</strong><small>${esc(latest?.display || "No comparable value")}</small><em class="${changeClass}">${esc(changeText)}</em></div>${benchmarkHistorySparkline(series)}</article>`;
  }).join("") || `<p class="benchmark-history-empty">A second complete matching shootout will create per-engine trend lines.</p>`;
  const runRows = (history.runs || []).map(run => {
    const statusLabel = ({trusted:"Usable result",tie:"Practical tie",incomplete:"Incomplete test","workload-mismatch":"Workload mismatch","conditions-mismatched":"Conditions differed"})[run.status] || run.status;
    const engines = (run.engines || [])
      .filter(engine => uiEngineVisible(engine.backend || engine.id))
      .map(engine => `${engine.label} · ${engine.valueDisplay}`).join("  |  ");
    return `<article class="benchmark-history-run ${esc(run.status)}"><div class="benchmark-history-run-head"><strong>${esc(benchmarkHistoryDate(run.createdAt))}</strong><em>${esc(statusLabel)}</em></div><p>${run.trustedWinner ? `<b>${esc(run.winnerLabel)} won.</b> ` : ""}${esc(run.summary)}</p><small>${esc(engines)}</small></article>`;
  });
  const routeRows = (history.currentRouteRuns || []).map(run => `<article class="benchmark-history-run"><div class="benchmark-history-run-head"><strong>${esc(benchmarkHistoryDate(run.createdAt))}</strong><em>Current engine</em></div><p><b>${esc(run.winnerLabel)} route.</b> ${esc(run.recommendation || "Measured locally.")}</p><small>${esc(run.display)}</small></article>`);
  $("benchmarkHistoryRuns").innerHTML = [...runRows, ...routeRows].join("") || `<p class="benchmark-history-empty">No saved run matches this exact visible contract yet.</p>`;
  const other = history.otherEvidence || {};
  $("benchmarkHistoryOther").innerHTML = other.count
    ? `<span>Retained but not comparable now</span>${(other.reasons || []).map(item => `<em>${esc(item.label)} · ${Number(item.count || 0)}</em>`).join("")}`
    : `<span>No mismatched historical evidence for this model.</span>`;
  const rerun = $("benchmarkHistoryRerun");
  rerun.disabled = active || !history.canRerunShootout;
  rerun.textContent = history.canRerunShootout ? "Rerun this visible contract" : "Needs two compatible engines";
}

async function loadBenchmarkHistory(force = false) {
  let request;
  try { request = benchmarkHistoryRequest(); }
  catch (error) {
    state.benchmarkHistory = null;
    state.benchmarkHistoryLoading = false;
    state.benchmarkHistoryError = error.message;
    renderBenchmarkHistory();
    return;
  }
  const key = benchmarkHistoryRequestKey(request);
  if (!force && key === state.benchmarkHistoryKey && state.benchmarkHistory) {
    renderBenchmarkHistory();
    return;
  }
  const generation = ++state.benchmarkHistoryGeneration;
  state.benchmarkHistoryLoading = true;
  state.benchmarkHistoryError = "";
  if (key !== state.benchmarkHistoryKey) state.benchmarkHistory = null;
  renderBenchmarkHistory();
  try {
    const data = await api("/api/benchmark/history", {method:"POST",body:JSON.stringify(request)});
    if (generation !== state.benchmarkHistoryGeneration) return;
    state.benchmarkHistoryKey = key;
    state.benchmarkHistory = data.history;
  } catch (error) {
    if (generation !== state.benchmarkHistoryGeneration) return;
    state.benchmarkHistory = null;
    state.benchmarkHistoryError = error.message;
  } finally {
    if (generation === state.benchmarkHistoryGeneration) {
      state.benchmarkHistoryLoading = false;
      renderBenchmarkHistory();
    }
  }
}

function scheduleBenchmarkHistory(force = false) {
  if (!$("benchmarkDialog").open) return;
  clearTimeout(state.benchmarkHistoryTimer);
  state.benchmarkHistoryTimer = setTimeout(() => loadBenchmarkHistory(force), 120);
}

function performanceReceiptSuite() {
  return ["pi", "opencode", "codex"].includes(state.client) ? "agentic" : "standard";
}

function performanceReceiptRequest() {
  const request = gather("custom");
  request.suite = performanceReceiptSuite();
  request.enginePreference = "fastest";
  return request;
}

function performanceReceiptRequestKey(request) {
  const customSampling = request.client === "chat" && request.chat?.sampling === "custom";
  const sampling = request.client === "chat"
      ? (customSampling ? {
        mode:"custom", temperature:request.chat.temperature, topP:request.chat.topP,
        topK:request.chat.topK, presencePenalty:request.chat.presencePenalty,
        frequencyPenalty:request.chat.frequencyPenalty, seed:request.chat.seed,
      } : {mode:"model"})
    : null;
  return JSON.stringify({
    modelId:request.modelId, backend:request.backend, client:request.client,
    context:request.context, output:request.output, reasoning:request.reasoning,
    kv:request.options?.kv || "off", sampling,
    suite:request.suite, enginePreference:request.enginePreference,
  });
}

function performanceReceiptAge(receipt) {
  const age = finiteMetric(receipt?.ageDays);
  if (age === null) return "date unavailable";
  if (age < 1 / 24) return "just measured";
  if (age < 1) return "measured today";
  if (age < 2) return "measured yesterday";
  return `${Math.round(age)} days old`;
}

function performanceReceiptView(receipt) {
  const focused = activeDetail() === "focused";
  const suite = receipt?.suiteLabel || (performanceReceiptSuite() === "agentic" ? "Agentic Route Lab" : "Standard");
  const eligible = Array.isArray(receipt?.eligibleBackends)
    ? receipt.eligibleBackends.filter(uiEngineVisible) : [];
  const age = performanceReceiptAge(receipt);
  const firstOutput = finiteMetric(receipt?.firstTokenSeconds);
  const measured = [
    receipt?.workloadDisplay,
    firstOutput === null ? "" : `${firstOutput.toFixed(2)}s first output`,
    age,
  ].filter(Boolean).join(" · ");
  const measuredTitle = [receipt?.backendLabel, receipt?.modeLabel].filter(Boolean).join(" · ");
  const fullSummary = [receipt?.summary, measured].filter(Boolean).join(" ");
  if (["trusted-engine", "trusted-route"].includes(receipt?.state)) {
    if (receipt.fresh) return {
      state:"trusted", icon:"◆",
      title:focused
        ? (receipt.state === "trusted-engine" ? `Best measured · ${receipt.backendLabel || "engine"}` : `Best setting · ${receipt.modeLabel || "verified route"}`)
        : `Measured · ${measuredTitle || "verified route"}`,
      detail:focused
        ? [receipt.state === "trusted-engine" ? receipt.modeLabel : receipt.backendLabel, receipt.workloadDisplay, age].filter(Boolean).join(" · ")
        : measured || `${suite} exact-contract evidence`,
      action:"Apply", actionId:receipt.state === "trusted-engine" ? "apply-engine" : "apply-route",
      titleText:fullSummary,
    };
    return {
      state:"stale", icon:"◇",
      title:focused ? "Saved result needs rechecking" : `Saved · ${measuredTitle || "verified route"}`,
      detail:focused ? [measuredTitle, age].filter(Boolean).join(" · ") : `${age} · rerun before relying on current conditions`,
      action:"Rerun", actionId:"rerun-lab", titleText:fullSummary,
    };
  }
  if (receipt?.state === "tie") return {
    state:"tie", icon:"≈", title:focused ? "No clear engine winner" : "Measured tie · no safe engine switch",
    detail:focused ? `${eligible.length} engines finished within the 3% noise floor` : `${suite} · ${age}`,
    action:"Review", actionId:"review-lab", titleText:fullSummary,
  };
  if (receipt?.state === "incomplete") return {
    state:"incomplete", icon:"!", title:focused ? "Finish the engine comparison" : "Measurement incomplete",
    detail:focused
      ? `${eligible.length} compatible engine${eligible.length === 1 ? "" : "s"} still need a complete run`
      : `${eligible.length} compatible engine${eligible.length === 1 ? "" : "s"} · no winner promoted`,
    action:"Measure", actionId:eligible.length >= 2 ? "measure-engine" : "measure-route",
    titleText:fullSummary,
  };
  const routeModes = benchmarkCandidates(selectedModel()?.backends?.[state.backend] || {}).length;
  if (receipt?.scope === "engine" && eligible.length >= 2) return {
    state:"missing", icon:"◇", title:focused ? "Compare compatible engines" : "No exact engine result",
    detail:focused ? `${eligible.length} engines can run this model and work surface` : `${eligible.length} compatible engines · ${suite}`,
    action:"Measure", actionId:"measure-engine", titleText:fullSummary,
  };
  if (routeModes > 1) return {
    state:"missing", icon:"◇", title:focused ? "Compare this engine's speed options" : "No exact route result",
    detail:focused
      ? benchmarkCandidates(selectedModel()?.backends?.[state.backend] || {}).map(item => item.label).join(" vs ")
      : `${benchmarkCandidates(selectedModel()?.backends?.[state.backend] || {}).map(item => item.label).join(" vs ")} · ${suite}`,
    action:"Measure", actionId:"measure-route", titleText:fullSummary,
  };
  return {
    state:"missing", icon:"○", title:focused ? "One verified route" : "No measured accelerator",
    detail:focused ? "No acceleration comparison is available for this engine and model" : "AR is the only verified route for this engine and model",
    action:"Details", actionId:"review-lab", titleText:fullSummary,
  };
}

function renderEngineEvidenceChoices(receipt) {
  const winner = receipt?.state === "trusted-engine" && receipt?.fresh
    ? String(receipt.backend || "") : "";
  document.querySelectorAll("[data-backend]").forEach(button => {
    const best = Boolean(winner && button.dataset.backend === winner);
    button.classList.toggle("measured-best", best);
    const badge = button.querySelector(".choice-evidence");
    if (badge) badge.textContent = best ? "Best" : "";
    if (best) button.setAttribute("aria-description", "Best measured engine for the exact visible model and workload contract");
    else button.removeAttribute("aria-description");
  });
}

function renderPerformanceReceipt() {
  const button = $("performanceReceipt");
  if (!button) return;
  let view;
  if (!selectedModel()) {
    view = {state:"missing", icon:"○", title:"Choose a runnable model", detail:"Performance evidence follows the visible route.", action:"", actionId:"", titleText:""};
  } else if (state.performanceReceiptLoading && !state.performanceReceipt) {
    view = activeDetail() === "focused"
      ? {state:"loading", icon:"◇", title:"Checking saved measurements…", detail:"This does not start the model.", action:"…", actionId:"", titleText:""}
      : {state:"loading", icon:"◇", title:"Checking measurements…", detail:"Matching intelligence, sampling, limits, KV, workload, runtime and Mac.", action:"…", actionId:"", titleText:""};
  } else if (state.performanceReceiptError) {
    view = {state:"error", icon:"!", title:"Evidence unavailable", detail:state.performanceReceiptError, action:"Retry", actionId:"retry", titleText:state.performanceReceiptError};
  } else if (state.performanceReceipt) view = performanceReceiptView(state.performanceReceipt);
  else view = activeDetail() === "focused"
    ? {state:"missing", icon:"◇", title:"Measure this route", detail:"No matching speed result is saved yet.", action:"Measure", actionId:"measure-route", titleText:""}
    : {state:"missing", icon:"◇", title:"No exact performance receipt", detail:"Measure this visible contract before choosing a winner.", action:"Measure", actionId:"measure-route", titleText:""};
  renderEngineEvidenceChoices(state.performanceReceipt);
  button.dataset.state = view.state;
  button.dataset.action = view.actionId;
  button.setAttribute("aria-busy", String(view.state === "loading"));
  $("performanceReceiptIcon").textContent = view.icon;
  $("performanceReceiptTitle").textContent = view.title;
  $("performanceReceiptDetail").textContent = view.detail;
  $("performanceReceiptAction").textContent = view.action;
  const accessible = [view.title, view.detail, view.action && `${view.action}.`, view.titleText].filter(Boolean).join(" ");
  button.setAttribute("aria-label", accessible);
  button.title = accessible;
  const applyBlocked = ["apply-engine", "apply-route"].includes(view.actionId) && $("applyOptimal").disabled;
  const measureBlocked = view.actionId === "measure-engine" && $("optimizerCalibrate").disabled;
  button.disabled = !view.actionId || view.state === "loading" || applyBlocked || measureBlocked;
}

async function loadPerformanceReceipt(force = false, prepared = null) {
  let request, key;
  try {
    request = prepared?.request || performanceReceiptRequest();
    key = prepared?.key || performanceReceiptRequestKey(request);
  } catch (error) {
    state.performanceReceiptGeneration += 1;
    state.performanceReceipt = null;
    state.performanceReceiptKey = "";
    state.performanceReceiptLoading = false;
    state.performanceReceiptError = error.message;
    renderPerformanceReceipt();
    return;
  }
  if (!force && key === state.performanceReceiptKey && state.performanceReceipt) {
    state.performanceReceiptLoading = false;
    renderPerformanceReceipt();
    return;
  }
  const generation = ++state.performanceReceiptGeneration;
  state.performanceReceiptKey = key;
  state.performanceReceiptLoading = true;
  state.performanceReceiptError = "";
  state.performanceReceipt = null;
  renderPerformanceReceipt();
  try {
    const data = await api("/api/benchmark/history", {method:"POST", body:JSON.stringify(request)});
    if (generation !== state.performanceReceiptGeneration) return;
    state.performanceReceipt = data.history?.receipt || null;
    if (!state.performanceReceipt) throw new Error("The controller returned no exact-contract receipt.");
  } catch (error) {
    if (generation !== state.performanceReceiptGeneration) return;
    state.performanceReceipt = null;
    state.performanceReceiptError = error.message;
  } finally {
    if (generation === state.performanceReceiptGeneration) {
      state.performanceReceiptLoading = false;
      renderPerformanceReceipt();
    }
  }
}

function schedulePerformanceReceipt(force = false) {
  clearTimeout(state.performanceReceiptTimer);
  let prepared;
  try {
    const request = performanceReceiptRequest();
    prepared = {request, key:performanceReceiptRequestKey(request)};
  } catch (error) {
    state.performanceReceiptGeneration += 1;
    state.performanceReceipt = null;
    state.performanceReceiptKey = "";
    state.performanceReceiptLoading = false;
    state.performanceReceiptError = error.message;
    renderPerformanceReceipt();
    return;
  }
  if (!force && prepared.key === state.performanceReceiptKey && state.performanceReceipt) {
    renderPerformanceReceipt();
    return;
  }
  const generation = ++state.performanceReceiptGeneration;
  if (prepared.key !== state.performanceReceiptKey) {
    state.performanceReceipt = null;
    state.performanceReceiptError = "";
    state.performanceReceiptKey = prepared.key;
  }
  state.performanceReceiptLoading = true;
  renderPerformanceReceipt();
  state.performanceReceiptTimer = setTimeout(() => {
    if (generation === state.performanceReceiptGeneration) loadPerformanceReceipt(force, prepared);
  }, 180);
}

async function openPerformanceBenchmarkLab(receipt = state.performanceReceipt) {
  $("benchmarkSuiteSelect").value = receipt?.suite || performanceReceiptSuite();
  $("benchmarkPreferenceSelect").value = "fastest";
  await openBenchmarkLab();
}

async function activatePerformanceReceipt() {
  const button = $("performanceReceipt");
  if (button.disabled) return;
  const action = button.dataset.action;
  if (action === "retry") return loadPerformanceReceipt(true);
  if (action === "apply-engine") return applyOptimal("engine", "fastest");
  if (action === "apply-route") return applyOptimal("current");
  if (action === "measure-engine") return openCalibrationAssistant({source:"performance-receipt", preference:"fastest"});
  if (["measure-route", "rerun-lab", "review-lab"].includes(action)) return openPerformanceBenchmarkLab();
}

function benchmarkSuiteChanged() {
  const help = {
    agentic:"Four staged coding-agent turns: cold 8K prefix, shared-prefix reuse, 4K synthetic tool-result ingestion, and a warm follow-up.",
    quick:"One measured pass at roughly 512 and 2K prompt tokens, plus warm-up and correctness checks.",
    standard:"Two measured passes at roughly 2K and 8K prompt tokens for stronger thermal and noise evidence.",
    thorough:"Two measured passes at roughly 4K, 16K, and 32K prompt tokens. Expect several model reloads and a long run.",
  };
  $("benchmarkSuiteHelp").textContent = help[$("benchmarkSuiteSelect").value] || help.quick;
  const agentic = $("benchmarkSuiteSelect").value === "agentic";
  $("benchmarkSafetyCopy").textContent = agentic
    ? "Generated prompts contain no project data. Each route gets the same growing synthetic conversation, exact greedy output is checked, and authoritative usage is required."
    : "Generated prompts contain no project data. Each route is cache-isolated, exact greedy output is checked, and authoritative usage is required.";
  $("benchmarkStartLabel").textContent = agentic ? "Four staged turns per route" : "Reloads each measured route";
  renderBenchmarkSetup();
  scheduleBenchmarkHistory();
}

function benchmarkPreferenceChanged() {
  const preference = $("benchmarkPreferenceSelect").value;
  const help = {
    fastest:"Ranks aggregate output speed for ordinary suites or total staged time for Agentic.",
    responsive:"Ranks the median measured time to first output; a lead below 3% remains a tie.",
    memory:"Ranks the smallest system-wide unified-memory headroom drop; differences below 512 MB remain a tie.",
    thermal:"Requires every engine to start at the same public macOS thermal state, then ranks worst state and speed.",
  };
  $("benchmarkPreferenceHelp").textContent = help[preference] || help.fastest;
  if (state.benchmarkStatus) renderBenchmarkResults(state.benchmarkStatus);
  renderBenchmarkSetup();
  scheduleBenchmarkHistory();
}

function renderEngineShootoutResults(status) {
  const result = status.result?.kind === "engine-shootout" ? status.result : null;
  const preference = $("benchmarkPreferenceSelect").value;
  const profile = result?.profiles?.[preference] || result?.decision || null;
  const phaseLabels = {queued:"Queued",cooldown:"Stabilising Mac",starting:"Loading",running:"Measuring",measured:"Measurement staged",completed:"Completed"};
  const engines = (result?.engines || Object.values(status.engines || {}).map(engine => ({
    backend:engine.backend, label:engine.label,
    mode:engine.record?.winner, modeLabel:engine.record?.winnerLabel,
    display:phaseLabels[engine.phase] || engine.phase,
    qualityMatchesMatrix:true, runtimeVersion:"",
  }))).filter(engine => uiEngineVisible(engine.backend));
  const recommended = profile?.backend || result?.recommendedBackend;
  const trustedWinner = Boolean(profile?.trustedWinner ?? result?.trustedWinner);
  const profileComparisons = new Map((profile?.comparedEngines || []).map(item => [item.backend, item]));
  const cards = engines.map(engine => {
    const winner = Boolean(trustedWinner && engine.backend === recommended);
    const profileComparison = profileComparisons.get(engine.backend);
    const modeLabel = engine.modeLabel || (engine.mode ? benchmarkWinnerLabel(engine.mode) : "Measuring…");
    const qualityText = !result
      ? "Waiting for the complete matrix"
      : engine.qualityMatchesMatrix
        ? "✓ Greedy output agrees across engines"
        : "! Greedy output differs from the matrix";
    const memoryText = Number.isInteger(engine.peakPressureDeltaBytes)
      ? `${formatBytes(engine.peakPressureDeltaBytes)} · ${Number(engine.minimumHeadroomPercent || 0).toFixed(0)}% left`
      : "Not measured";
    const ttftText = typeof engine.firstTokenSeconds === "number" && Number.isFinite(engine.firstTokenSeconds) ? `${engine.firstTokenSeconds.toFixed(2)} s` : "Not measured";
    const thermalText = engine.thermalWorst && engine.thermalWorst !== "unavailable"
      ? (engine.thermalStart && engine.thermalStart !== "unavailable" ? `${engine.thermalStart} → ${engine.thermalWorst}` : engine.thermalWorst)
      : "Not measured";
    const cooldownText = ({"reference-ready":"Reference ready",ready:"Comparable",timeout:"Timed out","condition-improved":"Higher headroom",unavailable:"Unavailable"})[engine.resourceCooldownStatus] || "Not measured";
    const decodeTps = finiteMetric(engine.decodeTokensPerSecond);
    const badge = winner ? enginePreferenceLabels[preference] : (profileComparison?.profileDisplay || engine.display || "Queued");
    return `<article class="benchmark-result engine-result ${winner ? "winner" : ""}"><div class="benchmark-result-head"><strong>${esc(engine.label || backendName(engine.backend))}</strong><em>${esc(badge)}</em></div><div class="benchmark-metrics"><span>Fastest safe route<b>${esc(modeLabel)}</b></span><span>Workload result<b>${esc(engine.display || "Measuring…")}</b></span><span>Generation speed<b>${decodeTps === null ? "Not measured" : `${decodeTps.toFixed(1)} tok/s`}</b></span><span>First output<b>${esc(ttftText)}</b></span><span>Memory pressure<b>${esc(memoryText)}</b></span><span>Thermal state<b>${esc(thermalText)}</b></span><span>Start gate<b>${esc(cooldownText)}</b></span></div>${engine.runtimeVersion ? `<p class="benchmark-runtime">${esc(engine.runtimeVersion)}</p>` : ""}<p class="benchmark-quality ${result && !engine.qualityMatchesMatrix ? "bad" : ""}">${qualityText}</p></article>`;
  }).join("");
  const recommendationText = profile?.recommendation || result?.recommendation;
  const recommendation = recommendationText
    ? `<div class="benchmark-recommendation"><span><strong>${trustedWinner ? `${esc(profile?.label || result?.decision?.label || backendName(recommended))} wins for ${esc(enginePreferenceLabels[preference] || "this goal")}.` : "Current engine kept."}</strong> ${esc(recommendationText)}</span>${trustedWinner ? `<button type="button" class="text-button" data-apply-shootout>Apply ${esc(enginePreferenceLabels[preference] || "measured winner")}</button>` : ""}</div>`
    : "";
  $("benchmarkResults").innerHTML = cards + recommendation;
}

function renderMtpTuningResults(status) {
  const result = status.result?.kind === "lmstudio-mtp-tuning" ? status.result : null;
  const sweep = result?.tuningSweep || status.tuning || {};
  const candidates = Array.isArray(sweep.candidates) ? sweep.candidates : [];
  const selectedKey = sweep.selectedCandidateKey || "";
  const baseline = result?.modes?.ar || status.modes?.ar;
  const selectedSettings = sweep.selectedSettings || candidates.find(item => item.key === selectedKey)?.settings;
  const winner = result?.winner;
  const baselineSpeed = Number(baseline?.medianEndToEndTokensPerSecond);
  const facts = `<div class="benchmark-tuning-facts"><span><small>AR reference</small><b>${Number.isFinite(baselineSpeed) ? `${baselineSpeed.toFixed(1)} tok/s` : "Preparing…"}</b></span><span><small>Search progress</small><b>${candidates.length} / ${Number(sweep.maximumCandidates || status.job?.tuningPlan?.maximumMtpCandidates || 10)} candidates</b></span><span><small>Current choice</small><b>${selectedSettings ? `max ${selectedSettings.depth} · min ${selectedSettings.mtpMinTokens} · ${Number(selectedSettings.mtpMinContinueProbability).toFixed(2)}` : "Waiting…"}</b></span><span><small>Final route</small><b>${winner ? benchmarkWinnerLabel(winner) : "Not committed"}</b></span></div>`;
  const stageLabels = {depth:"Draft maximum",cutoff:"Probability cutoff",minimum:"Draft minimum"};
  const cards = candidates.length
    ? `<div class="benchmark-tuning-candidates">${candidates.map(candidate => {
      const settings = candidate.settings || {};
      const selected = candidate.key === selectedKey || candidate.selected === true;
      const badge = selected ? (result ? "Selected" : "Leading") : (stageLabels[candidate.stage] || "Measured");
      const quality = candidate.qualityMatchesAR === true;
      return `<article class="benchmark-tuning-candidate ${selected ? "selected" : ""} ${quality ? "" : "mismatch"}"><header><strong>max ${esc(settings.depth)} · min ${esc(settings.mtpMinTokens)} · cutoff ${Number(settings.mtpMinContinueProbability || 0).toFixed(2)}</strong><em>${esc(badge)}</em></header><div><span>Median <b>${Number(candidate.medianSpeedupVsAR || 0).toFixed(2)}× AR</b></span><span>Worst <b>${Number(candidate.worstCaseSpeedupVsAR || 0).toFixed(2)}× AR</b></span><span>Output <b>${Number(candidate.medianEndToEndTokensPerSecond || 0).toFixed(1)} tok/s</b></span></div><p class="benchmark-quality ${quality ? "" : "bad"}">${quality ? "✓ Exact greedy output matches AR" : "! Greedy output mismatch"}</p></article>`;
    }).join("")}</div>`
    : `<p class="benchmark-tuning-empty">The AR reference is measured first. Candidate results appear here as complete, cache-isolated loads finish.</p>`;
  const recommendation = result?.recommendation
    ? `<div class="benchmark-recommendation"><strong>${esc(benchmarkWinnerLabel(result.winner))} recommendation.</strong> ${esc(result.recommendation)}</div>`
    : "";
  $("benchmarkResults").innerHTML = `<section class="benchmark-tuning-result"><div class="benchmark-tuning-result-head"><div><span>Bounded LM Studio search</span><strong>${result ? "Complete evidence contract" : "Provisional measurements"}</strong></div><em>${candidates.length} tested</em></div>${facts}${cards}</section>${recommendation}`;
}

function renderDflashTuningResults(status) {
  const result = status.result?.kind === "omlx-dflash2-tuning" ? status.result : null;
  const sweep = result?.tuningSweep || status.tuning || {};
  const candidates = Array.isArray(sweep.candidates) ? sweep.candidates : [];
  const selectedKey = sweep.selectedCandidateKey || "";
  const baseline = result?.modes?.ar || status.modes?.ar;
  const selectedSettings = sweep.selectedSettings || candidates.find(item => item.key === selectedKey)?.settings;
  const winner = result?.winner;
  const baselineSpeed = Number(baseline?.medianEndToEndTokensPerSecond);
  const selectedLabel = selectedSettings
    ? `block ${selectedSettings.blockSize} · ${selectedSettings.verifyMode} · ${selectedSettings.draftQuant}`
    : "Waiting…";
  const facts = `<div class="benchmark-tuning-facts"><span><small>AR reference</small><b>${Number.isFinite(baselineSpeed) ? `${baselineSpeed.toFixed(1)} tok/s` : "Preparing…"}</b></span><span><small>Search progress</small><b>${candidates.length} / ${Number(sweep.maximumCandidates || status.job?.tuningPlan?.maximumDflashCandidates || 10)} candidates</b></span><span><small>Best tested DFlash</small><b>${esc(selectedLabel)}</b></span><span><small>Final route</small><b>${winner ? benchmarkWinnerLabel(winner) : "Not committed"}</b></span></div>`;
  const stageLabels = {block:"Block size",verifier:"Verifier",quantization:"Draft precision"};
  const cards = candidates.length
    ? `<div class="benchmark-tuning-candidates">${candidates.map(candidate => {
      const settings = candidate.settings || {};
      const selected = candidate.key === selectedKey || candidate.selected === true;
      const badge = selected ? (result ? "Selected" : "Leading") : (stageLabels[candidate.stage] || "Measured");
      const quality = candidate.qualityMatchesAR === true;
      return `<article class="benchmark-tuning-candidate ${selected ? "selected" : ""} ${quality ? "" : "mismatch"}"><header><strong>block ${esc(settings.blockSize)} · ${esc(settings.verifyMode)} · ${esc(settings.draftQuant)}</strong><em>${esc(badge)}</em></header><div><span>Median <b>${Number(candidate.medianSpeedupVsAR || 0).toFixed(2)}× AR</b></span><span>Worst <b>${Number(candidate.worstCaseSpeedupVsAR || 0).toFixed(2)}× AR</b></span><span>Output <b>${Number(candidate.medianEndToEndTokensPerSecond || 0).toFixed(1)} tok/s</b></span></div><p class="benchmark-quality ${quality ? "" : "bad"}">${quality ? "✓ Exact greedy output matches AR" : "! Greedy output mismatch"}</p></article>`;
    }).join("")}</div>`
    : `<p class="benchmark-tuning-empty">AR and native MTP references are measured first when available. Complete, cache-isolated DFlash candidates appear here as they finish.</p>`;
  const recommendation = result?.recommendation
    ? `<div class="benchmark-recommendation"><strong>${esc(benchmarkWinnerLabel(result.winner))} recommendation.</strong> ${esc(result.recommendation)}</div>`
    : "";
  $("benchmarkResults").innerHTML = `<section class="benchmark-tuning-result"><div class="benchmark-tuning-result-head"><div><span>Bounded oMLX DFlash search</span><strong>${result ? "Complete evidence contract" : "Provisional measurements"}</strong></div><em>${candidates.length} tested</em></div>${facts}${cards}</section>${recommendation}`;
}

function renderBenchmarkResults(status) {
  if (status.result?.kind === "engine-shootout" || status.job?.kind === "engine-shootout") {
    renderEngineShootoutResults(status);
    return;
  }
  if (status.result?.kind === "lmstudio-mtp-tuning" || status.job?.kind === "lmstudio-mtp-tuning") {
    renderMtpTuningResults(status);
    return;
  }
  if (status.result?.kind === "omlx-dflash2-tuning" || status.job?.kind === "omlx-dflash2-tuning") {
    renderDflashTuningResults(status);
    return;
  }
  const result = status.result;
  const modes = result?.modes || status.modes || {};
  const winner = result?.winner;
  const cards = Object.entries(modes).map(([mode, values]) => {
    const speedup = mode === "ar" ? 1 : values.medianSpeedupVsAR;
    const qualityKnown = typeof values.qualityMatchesAR === "boolean";
    const qualityText = qualityKnown ? (values.qualityMatchesAR ? "✓ Greedy output matches AR" : "! Greedy output mismatch") : "✓ Correctness probe recorded";
    const agentic = values.agenticMetrics;
    const cacheTokens = agentic
      ? Math.max(Number(agentic.warmCachedPromptTokens || 0), Number(agentic.steadyCachedPromptTokens || 0))
      : 0;
    const baseMetrics = agentic
      ? `<span>End-to-end<b>${Number(values.medianEndToEndTokensPerSecond || 0).toFixed(1)} tok/s</b></span><span>Decode<b>${Number(values.medianDecodeTokensPerSecond || 0).toFixed(1)} tok/s</b></span><span>Warm prefix<b>${Number(agentic.warmPrefixTTFTSeconds || 0).toFixed(2)} s TTFT</b></span><span>Tool ingestion<b>${Number(agentic.toolIngestTTFTSeconds || 0).toFixed(2)} s TTFT</b></span><span>Cache telemetry<b>${agentic.cacheTelemetryAvailable ? `${formatNumber(cacheTokens)} tokens` : "Not reported"}</b></span><span>Stages<b>${values.samples?.length || 0}</b></span>`
      : `<span>Output speed<b>${Number(values.medianEndToEndTokensPerSecond || 0).toFixed(1)} tok/s</b></span><span>Decode<b>${Number(values.medianDecodeTokensPerSecond || 0).toFixed(1)} tok/s</b></span><span>First token<b>${Number(values.medianTTFT || 0).toFixed(2)} s</b></span><span>Samples<b>${values.samples?.length || 0}</b></span>`;
    const telemetry = values.resourceTelemetry || {};
    const resourceMetrics = telemetry.memoryAvailable || telemetry.thermalAvailable
      ? `<span>Memory pressure<b>${telemetry.memoryAvailable ? `${formatBytes(telemetry.peakPressureDeltaBytes)} · ${Number(telemetry.minimumHeadroomPercent || 0).toFixed(0)}% left` : "Unavailable"}</b></span><span>Thermal state<b>${telemetry.thermalAvailable ? esc(`${telemetry.thermalStart || "nominal"} → ${telemetry.thermalWorst || "nominal"}`) : "Unavailable"}</b></span>`
      : "";
    const metrics = baseMetrics + resourceMetrics;
    const reuse = agentic
      ? `<p class="benchmark-reuse">Cold ÷ warm-prefix TTFT <b>${Number(agentic.prefixReuseFactor || 0).toFixed(2)}×</b> · tool-ingest ÷ follow-up <b>${Number(agentic.toolReuseFactor || 0).toFixed(2)}×</b></p>`
      : "";
    return `<article class="benchmark-result ${winner === mode ? "winner" : ""}"><div class="benchmark-result-head"><strong>${esc(values.label || benchmarkWinnerLabel(mode))}</strong><em>${winner === mode ? "Winner" : (speedup ? `${Number(speedup).toFixed(2)}× AR` : "Measured")}</em></div><div class="benchmark-metrics">${metrics}</div>${reuse}<p class="benchmark-quality ${qualityKnown && !values.qualityMatchesAR ? "bad" : ""}">${qualityText}</p></article>`;
  }).join("");
  const recommendation = result?.recommendation ? `<div class="benchmark-recommendation"><strong>${esc(benchmarkWinnerLabel(result.winner))} recommendation.</strong> ${esc(result.recommendation)}</div>` : "";
  $("benchmarkResults").innerHTML = cards + recommendation;
}

function renderBenchmarkStatus(status = {}) {
  state.benchmarkStatus = status;
  state.benchmarkPhase = status.phase || "idle";
  const progress = Math.max(0, Math.min(1, Number(status.progress || 0)));
  const percent = Math.round(progress * 100);
  $("benchmarkPhase").textContent = ({idle:"Ready",queued:"Queued",cooldown:"Stabilising Mac",starting:"Loading route",running:"Measuring",stopping:"Stopping",completed:"Completed",cancelled:"Cancelled",failed:"Failed"})[state.benchmarkPhase] || state.benchmarkPhase;
  $("benchmarkPercent").textContent = `${percent}%`;
  $("benchmarkProgressBar").style.width = `${percent}%`;
  const track = $("benchmarkProgressBar").parentElement;
  track.setAttribute("aria-valuenow", String(percent));
  $("benchmarkStatus").textContent = status.message || "Nothing will start until you press Run benchmark.";
  const order = status.result?.executionOrder || status.job?.executionOrder || [];
  const cooldown = status.result?.resourceCooldown || status.job?.resourceCooldown;
  const mtpTuning = status.result?.kind === "lmstudio-mtp-tuning" || status.job?.kind === "lmstudio-mtp-tuning";
  const dflashTuning = status.result?.kind === "omlx-dflash2-tuning" || status.job?.kind === "omlx-dflash2-tuning";
  $("benchmarkFairness").textContent = mtpTuning
    ? `One AR reference and up to ${Number(status.job?.tuningPlan?.maximumMtpCandidates || status.result?.tuningSweep?.maximumCandidates || 10)} MTP candidates. Every candidate receives a fresh load, exact greedy parity, and the same bounded Mac-condition gate.`
    : dflashTuning
      ? `${(status.job?.tuningPlan?.baselineModes || status.result?.tuningSweep?.baselineModes || ["ar"]).map(benchmarkWinnerLabel).join(" + ")} reference routes and up to ${Number(status.job?.tuningPlan?.maximumDflashCandidates || status.result?.tuningSweep?.maximumCandidates || 10)} DFlash candidates. Every candidate receives a fresh load, exact greedy parity, and the same bounded Mac-condition gate.`
    : order.length
      ? `Rotated run order: ${order.map(backendName).join(" → ")}. Before every route, Launcher waits up to ${Number(cooldown?.maxWaitSeconds || 60).toFixed(0)} seconds for comparable Mac conditions.`
      : "Every measured route receives a fresh model load.";
  renderBenchmarkResults(status);
  renderBenchmarkHistory();
  renderBenchmarkSetup();
  if ($("calibrationDialog")?.open) renderCalibrationBenchmark(status);
  refreshLaunchability();
  if (status.phase === "completed" && status.result?.id && state.benchmarkResultId !== status.result.id) {
    state.benchmarkResultId = status.result.id;
    state.benchmarkHistoryKey = "";
    loadModels(false).finally(() => {
      loadBenchmarkHistory(true);
      loadPerformanceReceipt(true);
    });
  }
}

async function pollBenchmarkStatus() {
  try { renderBenchmarkStatus(await api("/api/benchmark/status")); } catch (_) {}
}

async function openBenchmarkLab() {
  renderBenchmarkSetup();
  benchmarkSuiteChanged();
  benchmarkPreferenceChanged();
  await pollBenchmarkStatus();
  if (!$("benchmarkDialog").open) $("benchmarkDialog").showModal();
  loadBenchmarkHistory();
}

async function startBenchmark(scope = "current") {
  try {
    const request = gather("custom");
    request.suite = $("benchmarkSuiteSelect").value;
    request.enginePreference = $("benchmarkPreferenceSelect").value;
    if (["engines", "mtp-tune", "dflash-tune"].includes(scope)) request.scope = scope;
    const data = await api("/api/benchmark/start", {method:"POST", body:JSON.stringify(request)});
    state.benchmarkPhase = "queued";
    const shootout = data.benchmark?.kind === "engine-shootout";
    const mtpTuning = data.benchmark?.kind === "lmstudio-mtp-tuning";
    const dflashTuning = data.benchmark?.kind === "omlx-dflash2-tuning";
    const engines = Object.fromEntries((data.benchmark?.engines || [])
      .filter(engine => uiEngineVisible(engine.backend))
      .map(engine => [engine.backend, {...engine, phase:"queued", modes:{}, record:null}]));
    renderBenchmarkStatus({
      phase:"queued", progress:0,
      message:shootout
        ? `Engine Shootout accepted. Preparing ${backendName(data.benchmark.executionOrder?.[0])} first in this rotated run…`
        : mtpTuning
          ? "MTP tuning accepted. Preparing the AR reference route…"
          : dflashTuning
            ? "DFlash 2 tuning accepted. Preparing the AR reference route…"
          : "Benchmark accepted. Preparing the first route…",
      job:data.benchmark, modes:{}, engines, tuning:(mtpTuning || dflashTuning) ? {candidates:[]} : undefined,
    });
  } catch (error) { $("benchmarkStatus").textContent = error.message; showNotice(error.message, true); }
}

async function stopBenchmark() {
  try {
    await api("/api/benchmark/stop", {method:"POST", body:"{}"});
    await Promise.all([pollStatus(), pollBenchmarkStatus()]);
  } catch (error) { $("benchmarkStatus").textContent = error.message; }
}

function calibrationBenchmarkActive(status = state.benchmarkStatus || {}) {
  return ["queued","cooldown","starting","running","stopping"].includes(status.phase || state.benchmarkPhase);
}

function calibrationOwnsBenchmark(status = state.benchmarkStatus || {}) {
  const jobId = status.job?.id || status.result?.id || "";
  return Boolean(state.calibrationJobId && jobId === state.calibrationJobId);
}

function calibrationOperationBlocked() {
  return ["preflight","starting","running","stopping"].includes(state.runPhase)
    || ["queued","downloading","stopping","verifying"].includes(state.setupPhase)
    || acquisitionIsActive()
    || routeCheckIsActive()
    || aneWorkIsActive()
    || calibrationBenchmarkActive()
    || state.calibrationApplying
    || state.profileBusy;
}

function updateCalibrationHelp() {
  const suite = $("calibrationSuiteSelect").value;
  const preference = $("calibrationPreferenceSelect").value;
  const cooling = $("calibrationCoolingSelect").value;
  $("calibrationSuiteHelp").textContent = ({
    agentic:"Measures cold prefill, prefix reuse, tool ingestion, and a warm follow-up.",
    standard:"Measures repeated 2K and 8K prompt routes for general chat throughput.",
    quick:"A smaller first signal using 512 and 2K prompts; rerun a representative suite before a major decision.",
    thorough:"Measures 4K, 16K, and 32K prompts with repeated passes and many model reloads.",
  })[suite] || "Uses generated local prompts.";
  $("calibrationPreferenceHelp").textContent = ({
    fastest:"Uses complete-workload time and keeps leads inside 3% as ties.",
    responsive:"Uses measured time to first output and keeps leads inside 3% as ties.",
    memory:"Uses system-wide unified-memory headroom and requires at least a 512 MB advantage.",
    thermal:"Requires comparable starting conditions, then ranks worst public macOS thermal state and speed.",
  })[preference] || "Uses matching local evidence only.";
  $("calibrationCoolingHelp").textContent = cooling === "max"
    ? "Maximum fans is an explicit loud-mode choice for MTPLX routes in this measurement."
    : "The launcher will not force maximum fans. macOS may still increase cooling under sustained load.";
}

function calibrationPlanRequest() {
  const request = gather("custom");
  request.suite = $("calibrationSuiteSelect").value;
  request.enginePreference = $("calibrationPreferenceSelect").value;
  request.calibrationCooling = $("calibrationCoolingSelect").value;
  request.options.fan = request.calibrationCooling;
  request.reasoningPolicy = "all-engines-model-default";
  return request;
}

function calibrationStateBadge(id, text, kind = "") {
  const badge = $(id);
  badge.textContent = text;
  badge.className = kind;
}

function renderCalibrationEntry() {
  const entry = state.calibrationEntry;
  const box = $("calibrationOrigin");
  box.classList.toggle("hidden", !entry);
  if (!entry) return;
  const next = entry.decision?.engineNextAction || {};
  const preferenceLabel = enginePreferenceLabels[entry.preference] || "Best engine";
  const missing = (next.missingEngines || [])
    .filter(item => uiEngineVisible(item.backend || item.id))
    .map(item => item.label).filter(Boolean);
  $("calibrationOriginTitle").textContent = entry.source === "optimizer-result"
    ? `${preferenceLabel} needs a local measurement`
    : `Measure before choosing ${preferenceLabel.toLowerCase()}`;
  $("calibrationOriginDetail").textContent = next.reason || (missing.length
    ? `Matching evidence is missing for ${missing.join(", ")}.`
    : "Review the exact engines, workload, reload count, and request count before anything runs.");
}

function renderCalibrationPlan() {
  const plan = state.calibrationPlan;
  const active = calibrationBenchmarkActive();
  const controlsLocked = state.calibrationLoading || active || state.calibrationApplying;
  $("calibrationSuiteSelect").disabled = controlsLocked;
  $("calibrationPreferenceSelect").disabled = controlsLocked;
  $("calibrationCoolingSelect").disabled = controlsLocked;
  if (!plan) {
    calibrationStateBadge("calibrationContractState", state.calibrationLoading ? "Checking" : "Unavailable", state.calibrationLoading ? "" : "blocked");
    calibrationStateBadge("calibrationEngineState", "Waiting", "");
    calibrationStateBadge("calibrationEvidenceState", "Waiting", "");
    $("calibrationPlanFacts").innerHTML = "";
    $("calibrationEngineCards").innerHTML = "";
    $("calibrationResults").innerHTML = "";
    $("calibrationResults").classList.add("hidden");
    $("calibrationEvidence").className = "calibration-evidence blocked";
    $("calibrationEvidence").innerHTML = `<i aria-hidden="true">!</i><span><strong>${state.calibrationLoading ? "Inspecting the visible contract…" : "A valid calibration plan is not available."}</strong><small>${esc($("calibrationStatus").textContent || "Choose a ready model and valid settings.")}</small></span>`;
    $("calibrationConsent").disabled = true;
    $("calibrationConsent").checked = false;
    $("calibrationConsentPanel").classList.add("hidden");
    $("calibrationStartButton").disabled = true;
    $("calibrationApplyButton").disabled = true;
    $("calibrationProfilePanel").classList.add("hidden");
    return;
  }
  const request = plan.request || {};
  const reasoningContract = plan.reasoningContract || {};
  const normalizedReasoning = reasoningContract.normalized === true;
  const kv = request.options?.kv && request.options.kv !== "off" ? String(request.options.kv).toUpperCase() : "Full precision";
  calibrationStateBadge("calibrationContractState", "Locked", "ready");
  $("calibrationContract").textContent = normalizedReasoning
    ? `${plan.model.name} · ${plan.clientLabel} · ${formatNumber(request.context)} context · ${formatNumber(request.output)} max response. ${reasoningContract.detail} Your launch setting changes only if you apply the result.`
    : `${plan.model.name} · ${plan.clientLabel} · ${formatNumber(request.context)} context · ${formatNumber(request.output)} max response. The model, quantisation, reasoning, sampling, prompt contract, and KV precision stay fixed.`;
  $("calibrationPlanFacts").innerHTML = [
    ["Workload", plan.suite.label], ["Goal", plan.preferenceLabel],
    ["Reasoning", normalizedReasoning ? `Model default (from ${reasoningContract.requested})` : request.reasoning], ["KV precision", kv],
    ["Model reloads", String(plan.modelReloadCount)], ["Measured requests", String(plan.measuredRequestCount)],
    ["Compared engines", String(plan.eligibleEngineCount)], ["Cooling", plan.calibrationCoolingLabel || "Automatic"],
  ].map(([label,value]) => `<span><small>${esc(label)}</small><b title="${esc(value)}">${esc(value)}</b></span>`).join("");
  calibrationStateBadge(
    "calibrationEngineState",
    plan.ready ? `${plan.eligibleEngineCount} comparable` : `${plan.eligibleEngineCount} eligible`,
    plan.ready ? "ready" : "blocked",
  );
  $("calibrationEngineCards").innerHTML = (plan.engines || [])
    .filter(engine => uiEngineVisible(engine.backend || engine.id))
    .map(engine => `<article class="calibration-engine ${engine.eligible ? "eligible" : "excluded"}"><header><strong>${esc(engine.label)}</strong><em>${engine.eligible ? "Comparable" : "Excluded"}</em></header><p>${esc(engine.reason)}</p><div class="calibration-engine-modes">${(engine.modes || []).map(mode => `<span>${esc(mode.label)}</span>`).join("") || ""}</div></article>`).join("");
  const evidence = plan.evidence || {};
  const evidenceReady = plan.action === "apply-existing";
  const completedResult = calibrationOwnsBenchmark()
    && state.benchmarkStatus?.phase === "completed"
    ? (state.benchmarkStatus.result || {}) : null;
  const completedDecision = completedResult
    ? (completedResult.profiles?.[$("calibrationPreferenceSelect").value] || completedResult.decision || {})
    : null;
  const completedDecisionReady = Boolean(
    completedResult?.matrixWorkloadComparable !== false
    && ["cross-engine-local-benchmark","cross-engine-noise-floor"].includes(completedDecision?.evidenceTier),
  );
  const resultPending = Boolean(completedDecisionReady && !evidenceReady);
  const shownEvidence = resultPending ? {
    trusted:Boolean(completedDecision.trustedWinner),
    label:completedDecision.trustedWinner
      ? `${completedDecision.label} is fastest`
      : `No clear winner — keep ${completedDecision.label}`,
    backendLabel:completedDecision.label,
    detail:completedDecision.rationale?.[0] || completedDecision.recommendation || completedResult.recommendation || "The completed result is being saved.",
    outputWarning:completedDecision.outputWarning || completedResult.outputWarning || "",
    comparedEngines:completedDecision.comparedEngines || completedResult.engines || [],
  } : evidence;
  const resultReady = evidenceReady || resultPending;
  calibrationStateBadge(
    "calibrationEvidenceState",
    resultReady ? (shownEvidence.trusted ? "Winner ready" : "Result ready") : (plan.ready ? "Ready to test" : "Blocked"),
    resultReady ? "ready" : (plan.ready ? "" : "blocked"),
  );
  const blockers = (plan.blockers || []).join(" ");
  const evidenceDetail = resultReady
    ? [shownEvidence.detail, shownEvidence.outputWarning].filter(Boolean).join(" ")
    : plan.ready
      ? `${plan.eligibleEngineCount} engines will be tested one at a time using generated prompts.`
      : blockers;
  $("calibrationEvidence").className = `calibration-evidence${resultReady ? " trusted" : plan.ready ? "" : " blocked"}`;
  $("calibrationEvidence").innerHTML = `<i aria-hidden="true">${resultReady ? "◆" : plan.ready ? "◇" : "×"}</i><span><strong>${esc(resultReady ? shownEvidence.label : plan.ready ? "Ready to test the engines" : "This setup cannot be tested yet")}</strong><small>${esc(evidenceDetail)}</small></span>`;
  const measuredDecision = completedDecision || (evidenceReady ? evidence : null);
  const measuredEngines = Array.isArray(measuredDecision?.comparedEngines)
    ? measuredDecision.comparedEngines : [];
  const measuredDecisionReady = Boolean(completedDecision
    ? ["cross-engine-local-benchmark", "cross-engine-noise-floor"]
      .includes(completedDecision.evidenceTier)
    : evidenceReady);
  $("calibrationResults").classList.toggle("hidden", measuredEngines.length === 0);
  $("calibrationResults").innerHTML = measuredEngines.length ? `<strong>Measured engine results</strong><div>${measuredEngines.map((engine, index) => {
    const selected = measuredDecisionReady && engine.backend === (measuredDecision.backend || shownEvidence.backend);
    const mode = engine.mode === "dflash2" ? "DFlash 2" : engine.mode === "mtp" ? "MTP" : "AR";
    const decodeTps = finiteMetric(engine.decodeTokensPerSecond);
    return `<article class="${selected ? "selected" : ""}"><span><b>${esc(engine.label || backendName(engine.backend))}</b><small>${esc(mode)}</small></span><strong>${esc(engine.profileDisplay || engine.display || "Measured")}</strong>${decodeTps === null ? "" : `<small class="calibration-result-tps">Generation ${decodeTps.toFixed(1)} tok/s</small>`}<em>${selected ? "Best result" : `#${index + 1}`}</em></article>`;
  }).join("")}</div>` : "";
  if (state.calibrationProfileContractId !== plan.contractId) {
    state.calibrationProfileContractId = plan.contractId;
    $("calibrationProfileName").value = plan.suggestedProfileName || "Quick Launch";
  }
  const canMeasure = ["measure", "apply-existing"].includes(plan.action)
    && plan.ready && !resultPending && !calibrationOperationBlocked();
  $("calibrationConsent").disabled = true;
  $("calibrationConsent").checked = false;
  $("calibrationConsentPanel").classList.add("hidden");
  $("calibrationConsentCopy").textContent = plan.ready
    ? `${plan.eligibleEngineCount} engines · ${plan.modelReloadCount} isolated reloads · ${plan.measuredRequestCount} generated local requests · ${plan.calibrationCoolingLabel || "Automatic"} cooling · up to ${Math.round(plan.resourceCooldownMaxSecondsPerRoute)} seconds of cancellable settling before each route.`
    : blockers || "Resolve the engine blockers before measurement.";
  $("calibrationStartButton").disabled = !canMeasure;
  $("calibrationStartButton").querySelector("strong").textContent = evidenceReady
    ? "Retest engines" : resultPending ? "Saving result…" : "Test engines";
  $("calibrationStartLabel").textContent = evidenceReady
    ? "Replace this saved measurement"
    : resultPending ? "No second test needed"
    : plan.ready ? `${plan.eligibleEngineCount} engines · ${plan.routeCount} routes` : "Resolve the blockers above";
  const canApply = evidenceReady && !calibrationOperationBlocked();
  $("calibrationApplyButton").disabled = !canApply;
  $("calibrationApplyButton").className = evidenceReady ? "primary" : "secondary";
  $("calibrationStartButton").className = evidenceReady ? "secondary" : "primary";
  $("calibrationApplyButton").textContent = evidence.trusted
    ? `Use ${evidence.backendLabel}${normalizedReasoning ? " + model default" : ""}`
    : `Keep ${evidence.backendLabel || "current engine"}${normalizedReasoning ? " + model default" : ""}`;
  $("calibrationProfilePanel").classList.toggle("hidden", !evidenceReady || active);
  $("calibrationSaveButton").disabled = !canApply || !$("calibrationProfileName").value.trim();
}

function renderCalibrationBenchmark(status = state.benchmarkStatus || {}) {
  const active = calibrationBenchmarkActive(status);
  const owns = calibrationOwnsBenchmark(status);
  const phase = status.phase || "idle";
  const progress = owns ? Math.max(0, Math.min(1, Number(status.progress || 0))) : 0;
  const percent = Math.round(progress * 100);
  $("calibrationPercent").textContent = `${percent}%`;
  $("calibrationProgressBar").style.width = `${percent}%`;
  $("calibrationProgressBar").parentElement.setAttribute("aria-valuenow", String(percent));
  $("calibrationStopButton").disabled = !(active && owns);
  const liveTps = finiteMetric(status.liveMetric?.decodeTokensPerSecond);
  const showLiveTps = Boolean(active && owns);
  $("calibrationLiveTps").classList.toggle("hidden", !showLiveTps);
  $("calibrationLiveTps").textContent = showLiveTps
    ? liveTps === null ? "Generation TPS: measuring…" : `Generation TPS: ${liveTps.toFixed(1)}`
    : "";
  $("calibrationLiveTps").title = showLiveTps
    ? [status.liveMetric?.backendLabel, status.liveMetric?.modeLabel, status.liveMetric?.stageLabel]
      .filter(Boolean).join(" · ")
    : "";
  if (active) {
    $("calibrationBadge").textContent = owns ? "Measuring" : "Benchmark busy";
    $("calibrationBadge").className = "setup-badge active";
    $("calibrationPhase").textContent = owns
      ? ({queued:"Queued",cooldown:"Stabilising Mac",starting:"Loading route",running:"Measuring",stopping:"Stopping"})[phase] || phase
      : "Another benchmark is active";
    $("calibrationStatus").textContent = owns ? (status.message || "Calibration is running.") : "Benchmark Lab currently owns the model runtime. Stop or finish it before calibrating.";
    return;
  }
  if (owns && phase === "completed") {
    $("calibrationBadge").textContent = "Result ready";
    $("calibrationBadge").className = "setup-badge ready";
    $("calibrationPhase").textContent = "Finished";
    $("calibrationPercent").textContent = "100%";
    $("calibrationProgressBar").style.width = "100%";
    $("calibrationProgressBar").parentElement.setAttribute("aria-valuenow", "100");
    const result = status.result || {};
    const decision = result.profiles?.[$("calibrationPreferenceSelect").value] || result.decision || {};
    $("calibrationStatus").textContent = decision.trustedWinner
      ? `${decision.label} won for ${enginePreferenceLabels[decision.preference] || "this goal"}. You can use the result without testing again.`
      : (decision.recommendation || "The engines finished in a practical tie, so the current engine is kept.");
    if (result.id && state.calibrationCompletionId !== result.id) {
      state.calibrationCompletionId = result.id;
      loadModels(false).then(() => loadCalibrationPlan(false)).catch(error => {
        $("calibrationStatus").textContent = error.message;
      });
    }
    return;
  }
  if (owns && ["failed","cancelled"].includes(phase)) {
    $("calibrationBadge").textContent = phase === "failed" ? "Needs attention" : "Stopped";
    $("calibrationBadge").className = "setup-badge warning";
    $("calibrationPhase").textContent = phase === "failed" ? "Failed" : "Stopped";
    $("calibrationStatus").textContent = status.message || "No partial calibration result was promoted.";
    return;
  }
  const plan = state.calibrationPlan;
  $("calibrationBadge").textContent = state.calibrationLoading ? "Checking" : plan?.action === "apply-existing" ? "Result ready" : plan?.ready ? "Ready" : "Blocked";
  $("calibrationBadge").className = `setup-badge${plan?.action === "apply-existing" ? " ready" : !plan?.ready && plan ? " warning" : ""}`;
  $("calibrationPhase").textContent = plan?.action === "apply-existing" ? "Ready to use" : plan?.ready ? "Ready to test" : "Needs attention";
  if (!state.calibrationLoading) {
    $("calibrationStatus").textContent = plan?.action === "apply-existing"
      ? "Your saved result matches these settings. No new test is needed."
      : plan?.ready ? "Choose Test engines when you are ready." : ((plan?.blockers || ["Choose a valid comparable setup."])[0]);
  }
}

function renderCalibration() {
  const expanded = activeDetail() === "detailed" || state.calibrationDetailsOpen;
  $("calibrationDialog").classList.toggle("show-calibration-details", state.calibrationDetailsOpen);
  $("calibrationDetailToggle").setAttribute("aria-expanded", String(expanded));
  $("calibrationDetailToggle").textContent = state.calibrationDetailsOpen ? "Hide details" : "Full details";
  updateCalibrationHelp();
  renderCalibrationEntry();
  renderCalibrationPlan();
  renderCalibrationBenchmark(state.benchmarkStatus || {});
}

async function loadCalibrationPlan(resetJob = true) {
  let request;
  try { request = calibrationPlanRequest(); }
  catch (error) {
    state.calibrationPlan = null;
    $("calibrationStatus").textContent = error.message;
    renderCalibration();
    return null;
  }
  const generation = ++state.calibrationGeneration;
  state.calibrationLoading = true;
  if (resetJob && !calibrationBenchmarkActive()) {
    state.calibrationJobId = "";
    state.calibrationCompletionId = "";
  }
  $("calibrationStatus").textContent = "Inspecting installed engines and exact-contract evidence without starting a model…";
  renderCalibration();
  try {
    const data = await api("/api/calibration/plan", {method:"POST", body:JSON.stringify(request)});
    if (generation !== state.calibrationGeneration) return null;
    state.calibrationPlan = data.plan;
    return data.plan;
  } catch (error) {
    if (generation === state.calibrationGeneration) {
      state.calibrationPlan = null;
      $("calibrationStatus").textContent = error.message;
    }
    return null;
  } finally {
    if (generation === state.calibrationGeneration) {
      state.calibrationLoading = false;
      renderCalibration();
    }
  }
}

async function openCalibrationAssistant(options = {}) {
  const preference = Object.prototype.hasOwnProperty.call(enginePreferenceLabels, options.preference)
    ? options.preference
    : "fastest";
  const recommendedSuite = options.decision?.engineNextAction?.recommendedSuite
    || (state.client === "chat" ? "standard" : "agentic");
  state.calibrationEntry = options.source ? {
    source:options.source,
    preference,
    decision:options.decision || null,
  } : null;
  state.calibrationDetailsOpen = false;
  closeOptimizerMenu();
  $("calibrationSuiteSelect").value = recommendedSuite;
  $("calibrationPreferenceSelect").value = preference;
  if (!$("calibrationDialog").open) $("calibrationDialog").showModal();
  await pollBenchmarkStatus();
  await loadCalibrationPlan(!calibrationBenchmarkActive());
}

async function startCalibration() {
  const plan = state.calibrationPlan;
  if (!plan?.ready || !["measure", "apply-existing"].includes(plan.action) || calibrationOperationBlocked()) return;
  try {
    const request = calibrationPlanRequest();
    request.scope = "engines";
    const data = await api("/api/benchmark/start", {method:"POST", body:JSON.stringify(request)});
    state.calibrationJobId = data.benchmark.id;
    state.calibrationCompletionId = "";
    state.benchmarkPhase = "queued";
    const engines = Object.fromEntries((data.benchmark.engines || [])
      .filter(engine => uiEngineVisible(engine.backend))
      .map(engine => [engine.backend, {...engine, phase:"queued", modes:{}, record:null}]));
    renderBenchmarkStatus({
      phase:"queued", progress:0,
      message:`Calibration accepted. Preparing ${backendName(data.benchmark.executionOrder?.[0])} first in this rotated run…`,
      job:data.benchmark, modes:{}, engines,
    });
  } catch (error) {
    $("calibrationStatus").textContent = error.message;
    showNotice(error.message, true);
  }
}

async function stopCalibration() {
  if (!calibrationOwnsBenchmark() || !calibrationBenchmarkActive()) return;
  await stopBenchmark();
}

async function applyCalibrationResult(saveProfile = false) {
  const plan = state.calibrationPlan;
  if (!plan || plan.action !== "apply-existing" || calibrationOperationBlocked()) return;
  const reasoningContract = plan.reasoningContract || {};
  const previousReasoning = $("reasoningSelect").value;
  const previousCooling = $("fanSelect").value;
  let reasoningChanged = false;
  let coolingChanged = false;
  let routeApplied = false;
  const name = $("calibrationProfileName").value.trim();
  if (saveProfile && !name) {
    $("calibrationStatus").textContent = "Give the Quick Launch profile a name before saving it.";
    return;
  }
  state.calibrationApplying = true;
  renderCalibration();
  $("calibrationStatus").textContent = "Rechecking and applying the measured engine decision to the visible controls…";
  try {
    if (reasoningContract.normalized === true) {
      const measured = String(reasoningContract.measured || "auto");
      const option = [...$("reasoningSelect").options].find(item => item.value === measured);
      if (!option) throw new Error("The calibrated model-default reasoning setting is no longer available.");
      $("reasoningSelect").value = measured;
      reasoningChanged = measured !== previousReasoning;
      refreshLaunchability();
    }
    const measuredCooling = String(plan.calibrationCooling || "smart");
    const coolingOption = [...$("fanSelect").options].find(item => item.value === measuredCooling);
    if (!coolingOption) throw new Error("The calibrated cooling setting is no longer available.");
    $("fanSelect").value = measuredCooling;
    coolingChanged = measuredCooling !== previousCooling;
    const applied = await applyOptimal("engine", plan.preference, false);
    if (!applied) throw new Error("The measured decision no longer matches the visible contract, so nothing was saved.");
    routeApplied = true;
    if (saveProfile) {
      const data = await api("/api/profiles/save", {
        method:"POST",
        body:JSON.stringify({
          name, enginePolicy:"measured", enginePreference:plan.preference,
          request:gather("custom"),
        }),
      });
      useProfileInventory(data);
      showNotice(`Applied ${state.optimalLabel || "the calibrated route"}${reasoningChanged ? " at model-default reasoning" : ""} and saved “${name}” as an auto-measured Quick Launch profile.`);
    } else {
      showNotice(reasoningChanged
        ? `Applied ${state.optimalLabel || "the calibrated route"}. Reasoning changed from ${previousReasoning} to model default so the measured three-engine result remains like-for-like; cooling is ${plan.calibrationCoolingLabel || "Automatic"}.`
        : `Applied ${state.optimalLabel || "the calibrated route"} with ${plan.calibrationCoolingLabel || "Automatic"} cooling. Model, limits, reasoning, sampling, and KV precision were preserved.`);
    }
    if ($("calibrationDialog").open) $("calibrationDialog").close();
  } catch (error) {
    if (reasoningChanged && !routeApplied) {
      $("reasoningSelect").value = previousReasoning;
      refreshLaunchability();
    }
    if (coolingChanged && !routeApplied) {
      $("fanSelect").value = previousCooling;
      refreshLaunchability();
    }
    $("calibrationStatus").textContent = error.message;
    showNotice(error.message, true);
  } finally {
    state.calibrationApplying = false;
    refreshLaunchability();
    if ($("calibrationDialog").open) renderCalibration();
  }
}

function sessionDecisionClass(decision) {
  if (decision === "ready") return "ready";
  if (["review", "unknown"].includes(decision)) return "warning";
  if (["pressure", "busy", "invalid"].includes(decision)) return "blocked";
  return "";
}

function sessionProjectedLabel(value) {
  if (!Number.isFinite(Number(value))) return "Unavailable";
  const bytes = Number(value);
  return bytes >= 0 ? `${formatBytes(bytes)} left` : `${formatBytes(-bytes)} over headroom`;
}

function sessionAttachmentRequest() {
  const run = state.sessionDashboard?.hub?.session;
  if (!run) throw new Error("No launcher-owned model session is running.");
  const client = $("sessionAttachClient").value;
  const request = {
    ownerRunId:run.runId,
    client,
    project:$("sessionAttachProject").value || run.project,
  };
  if (client !== "chat") request.agentHost = $("sessionAttachAgentHost").value;
  if (client === "chat") {
    const seed = $("sessionAttachSeed").value.trim();
    request.chat = {
      systemPrompt:$("sessionAttachSystemPrompt").value,
      sampling:$("sessionAttachSampling").value,
      temperature:Number($("sessionAttachTemperature").value),
      topP:Number($("sessionAttachTopP").value),
      topK:Number($("sessionAttachTopK").value),
      presencePenalty:Number($("sessionAttachPresencePenalty").value),
      frequencyPenalty:Number($("sessionAttachFrequencyPenalty").value),
      seed:seed === "" ? null : Number(seed),
    };
  }
  return request;
}

function syncSessionAttachmentForm(run, phase) {
  const active = Boolean(run && phase === "running");
  if (run && state.sessionAttachmentOwnerRunId !== run.runId) {
    state.sessionAttachmentOwnerRunId = run.runId;
    state.sessionAttachmentPlan = null;
    state.sessionAttachmentSignature = "";
    $("sessionAttachProject").value = run.project || "";
    $("sessionAttachAgentHost").value = "console";
    $("sessionAttachSystemPrompt").value = "";
    $("sessionAttachSampling").value = "model";
    $("sessionAttachTemperature").value = "0.7";
    $("sessionAttachTopP").value = "1";
    $("sessionAttachTopK").value = "0";
    $("sessionAttachPresencePenalty").value = "0";
    $("sessionAttachFrequencyPenalty").value = "0";
    $("sessionAttachSeed").value = "";
  }
  const backend = run?.backend || "";
  const runModel = state.models.find(model => model.id === run?.modelId) || selectedModel();
  const options = [...$("sessionAttachClient").options];
  for (const option of options) {
    const support = resolvedClientSupport(backend, option.value, runModel);
    const installed = option.value === "chat" || Boolean(state.binaries?.[option.value]?.installed);
    option.disabled = !active || !support?.supported || !installed;
    option.title = !installed
      ? `${clientName(option.value)} is not installed.`
      : support?.reason || "Unavailable for this engine.";
  }
  const selected = options.find(option => option.value === $("sessionAttachClient").value);
  if (!selected || selected.disabled) {
    const fallback = options.find(option => !option.disabled);
    if (fallback) $("sessionAttachClient").value = fallback.value;
  }
}

function renderSessionAttachmentPanel() {
  const dashboard = state.sessionDashboard;
  const hub = dashboard?.hub || {};
  const run = hub.session;
  const active = Boolean(run && hub.phase === "running");
  syncSessionAttachmentForm(run, hub.phase);
  const attachments = Array.isArray(hub.attachments) ? hub.attachments : [];
  $("sessionSurfaceSection").classList.toggle("inactive", !active);
  $("sessionAttachControls").classList.toggle("hidden", !active);
  $("sessionSurfaceState").textContent = active
    ? `${attachments.length} surface${attachments.length === 1 ? "" : "s"} · one model`
    : "No active route";
  $("sessionSurfaceState").className = active ? "ready" : "";
  $("sessionSurfaceDetail").textContent = active
    ? `Every surface below shares the loaded ${backendName(run.backend)} model through private relay port ${run.clientPort || run.port}; attaching never creates a second model allocation.`
    : "Start a normal session, then open another compatible agent or Chat without loading the model weights again.";
  $("sessionAttachmentList").innerHTML = attachments.length ? attachments.map(attachment => {
    const projectName = String(attachment.project || "").split("/").filter(Boolean).pop() || "Launcher";
    const statusClass = attachment.status === "handoff" ? "handoff" : attachment.status === "unavailable" ? "unavailable" : "";
    const statusLabel = attachment.status === "handoff" ? "Terminal handoff"
      : attachment.status === "ready" ? "Ready"
        : attachment.status === "running" ? "Hub Console running"
          : String(attachment.status || "unknown").replaceAll("-", " ");
    let actions = "";
    if (attachment.client === "chat" && attachment.canOpen) {
      actions = `<button type="button" data-session-open-chat="${esc(attachment.id)}">Open</button>${attachment.canDetach ? `<button type="button" class="detach" data-session-detach-chat="${esc(attachment.id)}">End</button>` : ""}`;
    } else if (attachment.agentHost === "console" && attachment.canOpen) {
      actions = `<button type="button" data-session-open-console="${esc(attachment.id)}">Open</button>${attachment.canStop ? `<button type="button" class="detach" data-session-stop-console="${esc(attachment.id)}">Stop</button>` : ""}${attachment.canRestart ? `<button type="button" data-session-restart-console="${esc(attachment.id)}">Restart</button>` : ""}`;
    }
    return `<article class="session-attachment"><div class="session-attachment-main"><strong>${esc(`${attachment.surface}${attachment.primary ? " · primary" : " · attached"}`)}</strong><span>${esc(`${formatNumber(attachment.context)} context · ${attachment.reasoning} reasoning`)}</span><small title="${esc(attachment.project || "")}">${esc(attachment.client === "chat" ? (attachment.chat?.sampling === "custom" ? "Custom sampling" : "Model sampling defaults") : projectName)}</small></div><div class="session-attachment-actions">${actions || `<span class="session-attachment-status ${statusClass}">${esc(statusLabel)}</span>`}</div></article>`;
  }).join("") : `<div class="session-active-route idle"><strong>No reusable surface yet</strong><span>The active route must reach Running first.</span></div>`;

  const client = $("sessionAttachClient").value;
  const chat = client === "chat";
  $("sessionAttachProjectField").classList.toggle("hidden", chat);
  $("sessionAttachHostField").classList.toggle("hidden", chat);
  $("sessionAttachChatPanel").classList.toggle("hidden", !chat);
  const custom = $("sessionAttachSampling").value === "custom";
  document.querySelectorAll(".session-attach-sampler").forEach(field => field.classList.toggle("inactive", !custom));
  const controls = [
    "sessionAttachClient", "sessionAttachAgentHost", "sessionAttachProject", "sessionAttachSystemPrompt",
    "sessionAttachSampling", "sessionAttachTemperature", "sessionAttachTopP",
    "sessionAttachTopK", "sessionAttachPresencePenalty", "sessionAttachFrequencyPenalty",
    "sessionAttachSeed",
  ];
  for (const id of controls) {
    const control = $(id);
    const samplerDisabled = control.closest(".session-attach-sampler") && !custom;
    control.disabled = !active || state.sessionAttachmentBusy || Boolean(samplerDisabled);
  }
  const plan = state.sessionAttachmentPlan;
  $("sessionAttachPlanDetail").textContent = state.sessionAttachmentLoading
    ? "Checking the exact loaded-model contract without allocating anything…"
    : plan?.detail || (active ? "Choose a compatible work surface." : "A running normal session is required.");
  const button = $("sessionAttachButton");
  button.disabled = !active || state.sessionAttachmentBusy || state.sessionAttachmentLoading || !plan?.ready;
  button.querySelector("strong").textContent = state.sessionAttachmentBusy
    ? "Attaching…" : plan?.action?.label || "Attach surface";
  button.querySelector("small").textContent = plan?.action?.usesSessionRelay
    ? "Uses the private scheduler · no model reload" : "No model reload";
}

async function cancelSessionRequest(requestId, surfaceId = "") {
  if (!requestId || state.requestCancelBusyId) return;
  const ownerRunId = state.sessionDashboard?.hub?.session?.runId
    || state.runStatus?.run?.runId || state.chatOwnerRunId;
  if (!ownerRunId) return;
  state.requestCancelBusyId = requestId;
  renderRequestActivity();
  try {
    const data = await api("/api/session/request/cancel", {
      method:"POST", body:JSON.stringify({ownerRunId, requestId}),
    });
    state.requestActivity = data.activity;
    if (state.sessionDashboard?.hub) state.sessionDashboard.hub.activity = data.activity;
    if (surfaceId && surfaceId === state.chatRunId) state.chatAbort?.abort();
    renderRequestActivity(data.activity);
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    state.requestCancelBusyId = "";
    renderRequestActivity();
  }
}

async function setSessionIdlePolicy() {
  if (state.idlePolicyBusy) return;
  const ownerRunId = state.sessionDashboard?.hub?.session?.runId
    || state.runStatus?.run?.runId;
  if (!ownerRunId) return;
  const timeoutMinutes = Number($("sessionIdleTimeout").value);
  state.idlePolicyBusy = true;
  renderRequestActivity();
  try {
    const data = await api("/api/session/idle-policy", {
      method:"POST", body:JSON.stringify({ownerRunId, timeoutMinutes}),
    });
    state.requestActivity = data.activity;
    if (state.sessionDashboard?.hub) state.sessionDashboard.hub.activity = data.activity;
    renderRequestActivity(data.activity);
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    state.idlePolicyBusy = false;
    renderRequestActivity();
  }
}

function scheduleSessionAttachmentPlan(immediate = false) {
  state.sessionAttachmentPlan = null;
  state.sessionAttachmentSignature = "";
  if (state.sessionAttachmentTimer) clearTimeout(state.sessionAttachmentTimer);
  renderSessionAttachmentPanel();
  state.sessionAttachmentTimer = setTimeout(() => {
    state.sessionAttachmentTimer = null;
    void loadSessionAttachmentPlan(true);
  }, immediate ? 0 : 260);
}

async function loadSessionAttachmentPlan(force = false) {
  const run = state.sessionDashboard?.hub?.session;
  const phase = state.sessionDashboard?.hub?.phase;
  if (!run || phase !== "running") {
    state.sessionAttachmentPlan = null;
    renderSessionAttachmentPanel();
    return null;
  }
  let request;
  try { request = sessionAttachmentRequest(); }
  catch (error) {
    state.sessionAttachmentPlan = null;
    $("sessionAttachStatus").textContent = error.message;
    $("sessionAttachStatus").className = "session-dashboard-status error";
    renderSessionAttachmentPanel();
    return null;
  }
  const signature = JSON.stringify(request);
  if (!force && signature === state.sessionAttachmentSignature && state.sessionAttachmentPlan) return state.sessionAttachmentPlan;
  const generation = ++state.sessionAttachmentGeneration;
  state.sessionAttachmentLoading = true;
  state.sessionAttachmentSignature = signature;
  renderSessionAttachmentPanel();
  try {
    const data = await api("/api/session/attachment-plan", {method:"POST", body:JSON.stringify(request)});
    if (generation !== state.sessionAttachmentGeneration) return null;
    state.sessionAttachmentPlan = data.plan;
    $("sessionAttachStatus").textContent = "Plan only: the engine, model weights, ports, project data, Terminal, and Hub Console were untouched.";
    $("sessionAttachStatus").className = "session-dashboard-status";
    return data.plan;
  } catch (error) {
    if (generation === state.sessionAttachmentGeneration) {
      state.sessionAttachmentPlan = null;
      $("sessionAttachStatus").textContent = error.message;
      $("sessionAttachStatus").className = "session-dashboard-status error";
    }
    return null;
  } finally {
    if (generation === state.sessionAttachmentGeneration) {
      state.sessionAttachmentLoading = false;
      renderSessionAttachmentPanel();
    }
  }
}

function enterChatSurface(attachment) {
  if (!attachment || attachment.client !== "chat") return;
  state.agentConsoleVisible = false;
  state.agentConsoleDismissed = true;
  if (state.agentConsoleTimer !== null) clearTimeout(state.agentConsoleTimer);
  state.agentConsoleTimer = null;
  persistAgentConsoleRecovery();
  if (state.chatRunId !== attachment.id) {
    if (!$("chatRunSettingsPanel").hidden) closeChatRunSettings(false);
    state.chatRunSettings = null;
    state.chatRunSettingsKey = "";
    if (state.chatAbort) state.chatAbort.abort();
    persistChatSessionState();
    resetChatConversation();
  }
  state.chatAttachment = attachment;
  state.chatRunId = attachment.id;
  state.chatOwnerRunId = attachment.ownerRunId;
  if (!state.chatDraftKey) activateChatDraft(attachment.id, {restoreActive:true});
  renderChatMessages();
  updateChatWorkspace(state.runStatus?.run, state.runPhase);
  updateAgentWorkspace(state.runStatus?.run, state.runPhase);
  if ($("sessionDialog").open) $("sessionDialog").close();
  requestAnimationFrame(() => $("chatInput").focus());
}

async function attachSessionSurface() {
  if (state.sessionAttachmentBusy || !state.sessionAttachmentPlan?.ready) return;
  let request;
  try { request = sessionAttachmentRequest(); }
  catch (error) {
    $("sessionAttachStatus").textContent = error.message;
    $("sessionAttachStatus").className = "session-dashboard-status error";
    return;
  }
  state.sessionAttachmentBusy = true;
  renderSessionAttachmentPanel();
  try {
    const data = await api("/api/session/attach", {method:"POST", body:JSON.stringify(request)});
    if (state.sessionDashboard) state.sessionDashboard.hub = data.hub;
    state.sessionAttachmentPlan = null;
    state.sessionAttachmentSignature = "";
    if (data.attachment.client === "chat") {
      enterChatSurface(data.attachment);
      showNotice("Chat attached to the loaded model. No engine or model weights were reloaded.");
    } else if (data.attachment.agentHost === "console") {
      enterAgentConsole(data.attachment);
      showNotice(`${data.attachment.surface} attached in Hub Console. The existing model allocation is unchanged.`);
    } else {
      $("sessionAttachStatus").textContent = `${data.attachment.surface} opened in a background Terminal. The existing model allocation is unchanged.`;
      $("sessionAttachStatus").className = "session-dashboard-status";
      await loadSessionDashboard();
    }
  } catch (error) {
    $("sessionAttachStatus").textContent = error.message;
    $("sessionAttachStatus").className = "session-dashboard-status error";
  } finally {
    state.sessionAttachmentBusy = false;
    renderSessionAttachmentPanel();
  }
}

async function detachChatSurface(attachment) {
  if (!attachment?.canDetach) return;
  if (state.chatRunId === attachment.id && state.chatAbort) state.chatAbort.abort();
  try {
    const data = await api("/api/session/detach", {
      method:"POST",
      body:JSON.stringify({ownerRunId:attachment.ownerRunId, attachmentId:attachment.id}),
    });
    if (state.chatRunId === attachment.id) {
      persistChatSessionState();
      state.chatRunId = "";
      state.chatOwnerRunId = "";
      state.chatAttachment = null;
      resetChatConversation();
      $("chatInput").value = "";
      sizeChatInput();
      renderChatDraftStatus();
      updateChatWorkspace(state.runStatus?.run, state.runPhase);
    }
    if (state.sessionDashboard) state.sessionDashboard.hub = data.hub;
    state.sessionAttachmentPlan = null;
    state.sessionAttachmentSignature = "";
    await loadSessionDashboard();
  } catch (error) {
    showNotice(error.message, true);
  }
}

async function endCurrentChatSurface() {
  if (state.chatAttachment?.primary === false) {
    await detachChatSurface(state.chatAttachment);
    return;
  }
  await stopRun();
}

function renderSessionDashboard() {
  const dashboard = state.sessionDashboard;
  if (!dashboard) {
    $("sessionBadge").textContent = state.sessionLoading ? "Inspecting" : "Unavailable";
    $("sessionBadge").className = `setup-badge${state.sessionLoading ? "" : " warning"}`;
    $("sessionDashboardStatus").textContent = state.sessionLoading
      ? "Inspecting launcher ownership and public macOS capacity without starting anything…"
      : "A current session plan is not available.";
    renderRequestActivity();
    renderCacheObservatory();
    renderSessionAttachmentPanel();
    return;
  }
  const resource = dashboard.resource || {};
  const hub = dashboard.hub || {};
  const operation = dashboard.operation || {};
  const admission = dashboard.admission || {};
  const warmRoute = currentWarmRoutePlan() || dashboard.warmRoute || {};
  const warmReady = Boolean(warmRoute.canAttach && hub.phase === "running");
  renderRequestActivity(hub.activity || state.requestActivity);
  renderCacheObservatory(hub.cache || state.cacheObservatory);
  const memoryPercent = resource.memoryAvailable ? Math.max(0, Math.min(100, Number(resource.headroomPercent || 0))) : 0;
  $("sessionMemoryBar").style.width = `${memoryPercent}%`;
  $("sessionMemoryBar").parentElement.setAttribute("aria-valuenow", String(Math.round(memoryPercent)));
  $("sessionResourceState").textContent = resource.memoryAvailable ? `${Math.round(memoryPercent)}% headroom` : "Unavailable";
  $("sessionResourceState").className = resource.memoryAvailable ? (memoryPercent >= 25 ? "ready" : "warning") : "warning";
  $("sessionResourceFacts").innerHTML = [
    ["Available", resource.memoryAvailable ? formatBytes(resource.headroomBytes) : "Unknown"],
    ["Installed", resource.totalMemoryBytes ? formatBytes(resource.totalMemoryBytes) : "Unknown"],
    ["Thermal", resource.thermalAvailable ? resource.thermalState : "Unavailable"],
    ["Low Power", resource.lowPowerMode === null || resource.lowPowerMode === undefined ? "Unknown" : resource.lowPowerMode ? "On" : "Off"],
    ["Signal", resource.memorySource || "Unavailable"],
    ["Checked", resource.capturedAt ? new Date(resource.capturedAt).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit",second:"2-digit"}) : "Now"],
  ].map(([label,value]) => `<span><small>${esc(label)}</small><b title="${esc(value)}">${esc(value)}</b></span>`).join("");
  $("sessionResourceDetail").textContent = "System-wide headroom includes every app on this Mac; it is not presented as process RSS or exact GPU allocation.";

  const run = hub.session || hub.internalRun;
  $("sessionActiveState").textContent = operation.active ? operation.phase : "Idle";
  $("sessionActiveState").className = operation.active ? "warning" : "ready";
  if (run) {
    const surface = run.purpose === "session" ? clientName(run.client) : operation.label;
    const projectName = String(run.project || "").split("/").filter(Boolean).pop() || "Local route";
    const routeLocation = run.routeKind === "connected"
      ? "connected server through private localhost bridge"
      : run.routeKind === "native"
        ? "native on this Mac"
        : "localhost";
    $("sessionActiveRoute").className = "session-active-route";
    $("sessionActiveRoute").innerHTML = `<strong>${esc(run.model)}</strong><span>${esc(backendName(run.backend))} → ${esc(surface)} · ${formatNumber(run.context)} context</span><small title="${esc(run.project || "")}">${esc(projectName)} · ${esc(routeLocation)} · localhost:${esc(run.clientPort || run.port)}</small>`;
  } else {
    $("sessionActiveRoute").className = "session-active-route idle";
    $("sessionActiveRoute").innerHTML = `<strong>No launcher-owned model session</strong><span>${esc(operation.detail || "Ready for a new route.")}</span><small>External runtimes are deliberately outside launcher ownership.</small>`;
  }
  $("sessionComponents").innerHTML = (hub.components || []).map(component => `<div class="session-component ${component.running ? "" : "stopped"}"><i aria-hidden="true"></i><span title="${esc(component.label)}">${esc(component.label)}</span><em>${component.pid ? `PID ${formatNumber(component.pid)}` : component.owned === "model-only" ? "model only" : component.owned ? "owned" : "handoff"}</em></div>`).join("");
  $("sessionOwnershipDetail").textContent = dashboard.policy?.reason || "One launcher-owned route at a time prevents accidental duplicate model allocations.";

  const visibleDecision = warmReady ? "ready" : admission.decision;
  const decisionClass = sessionDecisionClass(visibleDecision);
  $("sessionAdmissionTitle").textContent = warmReady
    ? "Reuse the loaded route"
    : admission.estimate?.remoteEngine ? "Connected server route" : "Full-context capacity estimate";
  $("sessionAdmissionState").textContent = warmReady ? "Warm route available" : admission.label || "Unavailable";
  $("sessionAdmissionState").className = decisionClass;
  $("sessionAdmissionDetail").textContent = warmReady
    ? warmRoute.detail : admission.detail || "Choose a valid visible route.";
  const estimate = admission.estimate;
  if (warmReady) {
    $("sessionEstimateFacts").innerHTML = [
      ["Model loads", "0"],
      ["Weight reload", "No"],
      ["Engine", warmRoute.loadedRoute?.backendLabel || backendName(warmRoute.loadedRoute?.backend)],
      ["Model", warmRoute.loadedRoute?.model || "Loaded model"],
      ["Context", formatNumber(warmRoute.loadedRoute?.context || 0)],
      ["Prefix reuse", "Reported per turn"],
    ].map(([label,value]) => `<span><small>${esc(label)}</small><b title="${esc(value)}">${esc(value)}</b></span>`).join("");
    $("sessionEstimateBar").innerHTML = "";
    $("sessionEstimateBasis").textContent = "The visible engine contract matches exactly. Opening the selected surface does not load weights; a cache hit is still claimed only when the runtime reports cached prompt tokens.";
  } else if (estimate?.remoteEngine) {
    $("sessionEstimateFacts").innerHTML = [
      ["Model location", "FreeToken server"],
      ["Mac weight load", "None"],
      ["Mac KV load", "None"],
      ["Context", formatNumber(estimate.contextTokens)],
      ["Agent endpoint", "Private loopback"],
      ["Remote stop", "Never"],
    ].map(([label,value]) => `<span><small>${esc(label)}</small><b title="${esc(value)}">${esc(value)}</b></span>`).join("");
    $("sessionEstimateBar").innerHTML = "";
    $("sessionEstimateBasis").textContent = estimate.basis;
  } else if (estimate) {
    const companion = estimate.companionLabels?.length ? `${formatBytes(estimate.companionBytes)} · ${estimate.companionLabels.join(" + ")}` : formatBytes(estimate.companionBytes);
    $("sessionEstimateFacts").innerHTML = [
      ["Model weights", formatBytes(estimate.modelBytes)],
      ["Companions", companion],
      [`${estimate.kvPrecision === "off" ? "Full" : String(estimate.kvPrecision).toUpperCase()} KV · ${formatNumber(estimate.contextTokens)}`, estimate.geometryReady ? formatBytes(estimate.kvCacheBytes) : "Geometry unavailable"],
      ["Runtime reserve", formatBytes(estimate.runtimeReserveBytes)],
      ["macOS reserve", formatBytes(estimate.osReserveBytes)],
      ["After launch", sessionProjectedLabel(admission.projectedHeadroomBytes)],
    ].map(([label,value]) => `<span><small>${esc(label)}</small><b title="${esc(value)}">${esc(value)}</b></span>`).join("");
    const segments = [
      ["weights", estimate.modelBytes, "Model weights"],
      ["companion", estimate.companionBytes, "Companion weights"],
      ["kv", estimate.kvCacheBytes, "Full-context KV capacity"],
      ["runtime", estimate.runtimeReserveBytes, "Runtime reserve"],
      ["reserve", estimate.osReserveBytes, "Protected macOS reserve"],
    ];
    const denominator = Math.max(Number(resource.totalMemoryBytes || 0), segments.reduce((sum, item) => sum + Number(item[1] || 0), 0), 1);
    $("sessionEstimateBar").innerHTML = segments.filter(item => Number(item[1]) > 0).map(([kind,value,label]) => `<span class="${kind}" style="width:${Math.max(.4, Number(value) / denominator * 100).toFixed(2)}%" title="${esc(`${label}: ${formatBytes(value)}`)}"></span>`).join("");
    $("sessionEstimateBasis").textContent = `${estimate.basis} ${estimate.parallelLanes > 1 ? `${estimate.parallelLanes} parallel LM Studio lanes are included.` : "One request lane is included."}`;
  } else {
    $("sessionEstimateFacts").innerHTML = "";
    $("sessionEstimateBar").innerHTML = "";
    $("sessionEstimateBasis").textContent = admission.detail || "Complete the current settings to calculate capacity.";
  }

  const needsConsent = Boolean(!warmReady && admission.requiresAcknowledgement && admission.launchable && admission.contractId);
  $("sessionConsentPanel").classList.toggle("inactive", !needsConsent);
  $("sessionConsent").disabled = !needsConsent;
  $("sessionConsent").checked = needsConsent && state.sessionAcknowledgementId === admission.contractId;
  $("sessionConsentCopy").textContent = needsConsent
    ? `${admission.label}. Approval is bound to contract ${admission.contractId} and is cleared when visible settings change.`
    : warmReady ? "No capacity override is needed because this action reuses the resident model allocation."
      : admission.decision === "ready" ? "No override is needed; the protected macOS reserve remains available." : "Resolve the active operation or visible settings before launch.";
  $("sessionStopButton").disabled = !operation.active;
  $("sessionBadge").textContent = warmReady ? "Warm route" : operation.active ? "1 active" : admission.decision === "ready" ? "Ready" : admission.label || "Review";
  $("sessionBadge").className = `setup-badge ${operation.active ? "active" : decisionClass}`;
  $("sessionDashboardStatus").className = "session-dashboard-status";
  $("sessionDashboardStatus").textContent = admission.privacy?.startsRuntime === false
    ? "Plan only: no runtime started, port allocated, project content read, or run directory created."
    : "Capacity plan refreshed.";
  renderSessionAttachmentPanel();
}

async function loadSessionDashboard() {
  if (state.sessionLoading) return state.sessionDashboard;
  let request;
  try { request = gather("custom", false); }
  catch (error) {
    state.sessionDashboard = null;
    $("sessionDashboardStatus").textContent = error.message;
    $("sessionDashboardStatus").className = "session-dashboard-status error";
    renderSessionDashboard();
    return null;
  }
  const signature = JSON.stringify(request);
  const generation = ++state.sessionGeneration;
  state.sessionLoading = true;
  renderSessionDashboard();
  try {
    const data = await api("/api/session/plan", {method:"POST", body:JSON.stringify(request)});
    if (generation !== state.sessionGeneration) return null;
    const next = data.sessions;
    const nextContract = next?.admission?.contractId || "";
    if (state.sessionAdmissionSignature !== signature || state.sessionAcknowledgementId !== nextContract) {
      state.sessionAcknowledgementId = "";
    }
    if (!next?.admission?.requiresAcknowledgement) state.sessionAcknowledgementId = "";
    state.sessionAdmissionSignature = signature;
    state.sessionDashboard = next;
    if (
      next?.warmRoute?.ownerRunId === state.runStatus?.run?.runId
      && signature === JSON.stringify(request)
    ) {
      state.warmRoutePlan = next.warmRoute;
      state.warmRouteSignature = warmRouteRequestSignature(request);
    }
    return next;
  } catch (error) {
    if (generation === state.sessionGeneration) {
      state.sessionDashboard = null;
      $("sessionDashboardStatus").textContent = error.message;
      $("sessionDashboardStatus").className = "session-dashboard-status error";
    }
    return null;
  } finally {
    if (generation === state.sessionGeneration) {
      state.sessionLoading = false;
      state.sessionLastLoadedAt = Date.now();
      renderSessionDashboard();
      if (state.sessionDashboard?.hub?.session && state.sessionDashboard?.hub?.phase === "running") {
        void loadSessionAttachmentPlan();
      }
    }
  }
}

async function openSessionDashboard() {
  if (!$("sessionDialog").open) $("sessionDialog").showModal();
  await loadSessionDashboard();
}

async function stopSessionFromDashboard() {
  await stopRun();
  await loadSessionDashboard();
}

function setupIsActive() {
  return ["queued","downloading","stopping","verifying"].includes(state.setupPhase);
}

function updateSetupControls() {
  const plan = state.setupPlan;
  const active = setupIsActive();
  const runActive = ["preflight","starting","running","stopping"].includes(state.runPhase);
  const benchmarkActive = ["queued","cooldown","starting","running","stopping"].includes(state.benchmarkPhase);
  const routeCheckActive = routeCheckIsActive();
  const aneActive = aneWorkIsActive();
  const acquisitionActive = acquisitionIsActive();
  const canDownload = Boolean(plan?.draft?.canDownload && !plan?.draft?.complete);
  const blocked = runActive || benchmarkActive || routeCheckActive || aneActive || acquisitionActive;
  $("setupConsent").disabled = !canDownload || active || blocked;
  $("setupConsentPanel").classList.toggle("inactive", !canDownload || active || blocked);
  $("setupDownloadButton").disabled = !canDownload || !$("setupConsent").checked || active || blocked;
  $("setupStopButton").disabled = !active;
}

function renderSetupPlan(plan) {
  if (!plan?.draft || !plan?.runtime || !plan?.target) return;
  const changed = state.setupRenderedPlanId !== plan.id;
  state.setupPlan = plan;
  state.setupRenderedPlanId = plan.id || "";
  if (changed) $("setupConsent").checked = false;

  const runtime = plan.runtime;
  const draft = plan.draft;
  $("setupRoute").textContent = `${plan.target.name || "Selected model"} · ${plan.stepsRemaining} setup step${plan.stepsRemaining === 1 ? "" : "s"} remaining`;
  $("setupRuntimeStep").className = `setup-step ${runtime.recommendedBuild ? "pass" : (runtime.supported ? "advisory" : "pending")}`;
  $("setupRuntimeState").textContent = runtime.recommendedBuild ? "Recommended" : (runtime.supported ? "Supported" : "Manual step");
  $("setupRuntimeDetail").textContent = `${runtime.detected} · ${runtime.detail}`;
  $("setupRuntimeLink").href = runtime.releaseUrl;

  $("setupDraftStep").className = `setup-step ${draft.complete ? "pass" : (draft.canDownload ? "pending" : "blocked")}`;
  $("setupDraftState").textContent = draft.complete ? "Verified" : (draft.detected ? "Resume available" : (draft.canDownload ? "Ready to download" : "Blocked"));
  $("setupDraftDetail").textContent = `${draft.detail} Revision ${String(draft.revision || "").slice(0, 12)} is fixed for this plan.`;
  $("setupDraftDestination").textContent = draft.destination || "—";
  $("setupDiskDetail").textContent = draft.complete
    ? `${formatBytes(draft.existingBytes)} present and verified`
    : draft.diskReady
      ? `${formatBytes(draft.remainingBytes)} remaining · ${formatBytes(draft.freeBytes)} free`
      : `${formatBytes(draft.freeBytes)} free · ${formatBytes(draft.admissionBytes)} required`;
  $("setupDraftLink").href = draft.url;
  $("setupVerification").innerHTML = (plan.verification?.checks || []).map(check => `<li><i aria-hidden="true">✓</i>${esc(check)}</li>`).join("");
  $("setupConsentCopy").textContent = `This creates or resumes ${draft.repo} at the fixed ${String(draft.revision || "").slice(0, 12)} revision only. It will not install oMLX, change agent settings, or modify existing weights.`;
  $("setupDownloadLabel").textContent = draft.complete ? "Already installed" : (draft.canDownload ? `${draft.sizeLabel} · resumable` : "Resolve the blocker above");
  $("setupBadge").textContent = plan.ready ? "Route ready" : (draft.canDownload ? "Consent required" : "Review only");
  $("setupBadge").className = `setup-badge${plan.ready ? " ready" : ""}`;

  if (state.setupPhase === "idle") {
    const progress = draft.complete ? 1 : Math.min(0.98, Number(draft.existingBytes || 0) / Math.max(1, Number(draft.sizeBytes || 1)));
    const percent = Math.round(progress * 100);
    $("setupPhase").textContent = plan.ready ? "Ready" : "Ready to review";
    $("setupPercent").textContent = `${percent}%`;
    $("setupProgressBar").style.width = `${percent}%`;
    $("setupProgressBar").parentElement.setAttribute("aria-valuenow", String(percent));
    $("setupStatus").textContent = plan.ready
      ? "The pinned pair is complete. Benchmark it locally before choosing DFlash 2 automatically."
      : draft.canDownload
        ? "Review the destination and manual runtime step, then approve the download if you want it."
        : draft.detail;
  }
  updateSetupControls();
}

function renderSetupStatus(status = {}) {
  const previous = state.setupPhase;
  state.setupStatus = status;
  state.setupPhase = status.phase || "idle";
  if (state.setupPhase === "idle" && state.setupPlan && !status.plan) {
    renderSetupPlan(state.setupPlan);
    if (state.runStatus) renderRun(state.runStatus);
    else refreshLaunchability();
    return;
  }
  if (status.plan) renderSetupPlan(status.plan);
  const progress = Math.max(0, Math.min(1, Number(status.progress || 0)));
  const percent = Math.round(progress * 100);
  $("setupPhase").textContent = ({idle:"Ready to review",queued:"Queued",downloading:"Downloading",stopping:"Stopping",verifying:"Verifying",completed:"Verified",cancelled:"Stopped",failed:"Needs attention"})[state.setupPhase] || state.setupPhase;
  $("setupPercent").textContent = `${percent}%`;
  $("setupProgressBar").style.width = `${percent}%`;
  $("setupProgressBar").parentElement.setAttribute("aria-valuenow", String(percent));
  if (status.message) $("setupStatus").textContent = status.message;
  if (setupIsActive()) {
    $("setupBadge").textContent = state.setupPhase === "verifying" ? "Verifying" : "Download active";
    $("setupBadge").className = "setup-badge active";
  } else if (state.setupPhase === "completed") {
    $("setupBadge").textContent = "Draft verified";
    $("setupBadge").className = "setup-badge ready";
  } else if (["cancelled","failed"].includes(state.setupPhase)) {
    $("setupBadge").textContent = state.setupPhase === "failed" ? "Check required" : "Files preserved";
    $("setupBadge").className = "setup-badge warning";
  }
  if (previous !== state.setupPhase && ["completed","cancelled","failed"].includes(state.setupPhase)) {
    $("setupConsent").checked = false;
  }
  updateSetupControls();
  if (state.runStatus) renderRun(state.runStatus);
  else refreshLaunchability();
  const completedId = status.phase === "completed" ? status.plan?.id : "";
  if (completedId && state.setupCompletionId !== completedId) {
    state.setupCompletionId = completedId;
    loadModels(false).then(() => {
      if ($("setupDialog").open) loadSetupPlan();
    }).catch(() => {});
  }
}

async function pollSetupStatus() {
  try { renderSetupStatus(await api("/api/setup/status")); } catch (_) {}
}

async function loadSetupPlan() {
  const model = selectedModel();
  if (!model) throw new Error("Choose a compatible oMLX target first.");
  const data = await api("/api/setup/plan", {method:"POST", body:JSON.stringify({modelId:model.id})});
  renderSetupPlan(data.plan);
  return data.plan;
}

async function openSetupAssistant() {
  $("setupConsent").checked = false;
  $("setupStatus").textContent = "Inspecting the selected target without changing your Mac…";
  if (!$("setupDialog").open) $("setupDialog").showModal();
  try {
    await pollSetupStatus();
    if (!(setupIsActive() && state.setupStatus?.plan)) await loadSetupPlan();
  } catch (error) {
    $("setupStatus").textContent = error.message;
    $("setupBadge").textContent = "Unavailable";
    $("setupBadge").className = "setup-badge warning";
    updateSetupControls();
  }
}

async function startSetupDownload() {
  const plan = state.setupPlan;
  if (!plan || !$("setupConsent").checked) return;
  try {
    const data = await api("/api/setup/download-draft", {
      method:"POST",
      body:JSON.stringify({modelId:plan.target.modelId, confirmation:plan.draft.repo}),
    });
    renderSetupStatus({phase:"queued",progress:Number(plan.draft.existingBytes || 0) / Math.max(1, Number(plan.draft.sizeBytes || 1)),message:"Download approved. Preparing the pinned destination…",plan:data.plan});
  } catch (error) {
    $("setupStatus").textContent = error.message;
    showNotice(error.message, true);
  }
}

async function stopSetup() {
  try {
    await api("/api/setup/stop", {method:"POST", body:"{}"});
    await pollSetupStatus();
  } catch (error) { $("setupStatus").textContent = error.message; }
}

function aneIsActive() {
  return ["queued","starting","running","stopping"].includes(state.anePhase);
}

function aneCloneIsActive() {
  return ["queued","validating","converting","verifying","stopping"].includes(state.aneClonePhase);
}

function aneWorkIsActive() {
  return aneIsActive() || aneCloneIsActive();
}

function aneVisibleRecord() {
  const model = selectedModel();
  if (!model) return null;
  const live = state.aneStatus?.result;
  if (live?.modelId === model.id) return live;
  return model.backends?.omlx?.aneTuning || null;
}

function renderAneDialogSetup() {
  const model = selectedModel();
  const cap = model?.backends?.omlx || {};
  const readiness = cap.aneReadiness || {};
  const memory = readiness.memory || {};
  const checks = [
    {ready:Boolean(readiness.modelCompatible), title:"Checkpoint layout", detail:readiness.modelReason || "Dense Qwen affine checkpoint required"},
    {ready:Boolean(readiness.runtimeVersionReady ?? readiness.runtimeReady), title:"oMLX version", detail:(readiness.runtimeVersionReady ?? readiness.runtimeReady) ? `${readiness.runtimeDetected} includes the guarded tuner path.` : `${readiness.runtimeDetected || "Not installed"} must be updated to ${readiness.minimumRuntime || "0.6.3rc2"}.`},
    {ready:Boolean(readiness.kernelReady), title:"Native Qwen kernel", detail:readiness.kernelReason || "The selected installation must pass oMLX's native-kernel self-check."},
    {ready:Boolean(readiness.memoryReady), title:"Memory admission", detail:readiness.memoryReady ? `${formatBytes(memory.totalBytes)} installed · ${formatBytes(memory.reserveBytes)} conservative reserve.` : memory.reason || "Capacity could not be proven."},
  ];
  $("aneDialogChecks").innerHTML = checks.map(check => `<article class="ane-dialog-check ${check.ready ? "pass" : "blocked"}"><strong>${esc(check.title)}</strong><span>${esc(check.detail)}</span><em>${check.ready ? "Passed" : "Blocked"}</em></article>`).join("");
  $("aneRoute").textContent = model
    ? `${model.name} · ${readiness.quantizationMode || "unknown"} ${readiness.bits || "?"}-bit / group ${readiness.groupSize || "?"}`
    : "Choose an oMLX checkpoint to inspect.";
  if (!aneIsActive() && !["completed","failed","cancelled"].includes(state.anePhase)) {
    $("aneDialogStatus").textContent = readiness.ready
      ? "Ready for an isolated GPU baseline and ANE/GPU split measurement."
      : readiness.reason || cap.aneReason || "Select a compatible checkpoint.";
  }
  updateAneControls();
}

function updateAneControls() {
  const model = selectedModel();
  const readiness = model?.backends?.omlx?.aneReadiness || {};
  const active = aneIsActive();
  const cloneActive = aneCloneIsActive();
  const runActive = ["preflight","starting","running","stopping"].includes(state.runPhase);
  const benchmarkActive = ["queued","cooldown","starting","running","stopping"].includes(state.benchmarkPhase);
  const setupActive = setupIsActive();
  const blockedByOtherWork = cloneActive || benchmarkActive || setupActive || acquisitionIsActive() || routeCheckIsActive() || runtimeUpdateIsActive() || runtimePromotionIsActive() || (runActive && !active);
  const canStart = Boolean(state.backend === "omlx" && model && readiness.ready && !active && !blockedByOtherWork);
  const cpuAvailable = Boolean(readiness.cpuSharingAvailable);
  const cpuInput = $("aneCpuAssist");
  if (active && typeof state.aneStatus?.job?.cpuAssist === "boolean") {
    cpuInput.checked = state.aneStatus.job.cpuAssist;
  } else if (!cpuAvailable) {
    cpuInput.checked = false;
  }
  cpuInput.disabled = active || !canStart || !cpuAvailable;
  $("aneCpuAssistPanel").classList.toggle("inactive", cpuInput.disabled);
  $("aneCpuAssistCopy").textContent = readiness.cpuSharingReason
    || "Requires a separate all-FP16 checkpoint clone and a larger memory reserve.";
  const cpuSummary = cpuInput.checked
    ? "ANE + GPU + CPU candidates"
    : cpuAvailable
      ? `Optional · ${formatBytes(readiness.cpuMemory?.reserveBytes || 0)} reserve ready`
      : "ANE + GPU only · FP16 clone required";
  $("aneCpuAssistSummary").textContent = cpuSummary;
  $("aneCpuAssistFact").textContent = cpuInput.checked
    ? "On · measured CPU candidates"
    : "Off · ANE + GPU only";
  if (cpuInput.checked) $("aneAdvanced").open = true;
  $("aneConsent").disabled = true;
  $("aneConsent").checked = false;
  $("aneConsentPanel").classList.add("hidden");
  $("aneStartButton").disabled = !canStart;
  $("aneStopButton").disabled = !active;
  const record = aneVisibleRecord();
  $("aneUseButton").disabled = active || !record?.accepted;
  const badge = $("aneDialogBadge");
  if (active) {
    badge.textContent = "Measurement active";
    badge.className = "setup-badge active";
  } else if (record?.accepted) {
    badge.textContent = "Measured result ready";
    badge.className = "setup-badge ready";
  } else if (readiness.ready) {
    badge.textContent = "Ready";
    badge.className = "setup-badge";
  } else {
    badge.textContent = "Read only";
    badge.className = "setup-badge warning";
  }
  updateAneCloneControls();
}

function renderAneResults(status = {}) {
  const record = aneVisibleRecord();
  const sameModel = !status.job?.modelId || status.job.modelId === selectedModel()?.id;
  const rows = sameModel && status.results?.length ? status.results : (record?.results || []);
  const recommendation = sameModel && status.recommendation ? status.recommendation : (record?.recommendation || null);
  const cards = rows.filter(row => row.state !== "pending" || aneIsActive()).map(row => {
    const speed = Number(row.speedup_percent);
    const measured = Number.isFinite(Number(row.processing_tps)) && Number(row.processing_tps) > 0;
    const recommended = Boolean(recommendation?.enabled && row.enabled && measured && Math.abs(Number(row.processing_tps) - Number(recommendation.processing_tps)) < 0.02);
    const cpuParts = row.cpu_enabled ? [
      Number(row.cpu_fraction) > 0 ? `gate/up ${Math.round(Number(row.cpu_fraction) * 100)}%` : "",
      Number(row.cpu_down_fraction) > 0 ? `down ${Math.round(Number(row.cpu_down_fraction) * 100)}%` : "",
      Number(row.cpu_gdn_fraction) > 0 ? `GDN ${Math.round(Number(row.cpu_gdn_fraction) * 100)}%` : "",
    ].filter(Boolean) : [];
    const split = row.enabled
      ? `ANE ${Math.round(Number(row.mlp_fraction || 0) * 100)}%${row.gdn_enabled ? ` · GDN ${Math.round(Number(row.gdn_fraction || 0) * 100)}%` : ""}${cpuParts.length ? ` · CPU ${cpuParts.join(" / ")}` : ""}`
      : "GPU-only baseline";
    return `<article class="ane-result ${recommended ? "recommended" : ""}"><div class="ane-result-head"><strong>${esc(row.label || "Candidate")}</strong><em>${recommended ? "Recommended" : esc(row.state || "Measured")}</em></div><b class="ane-result-metric">${measured ? `${Number(row.processing_tps).toFixed(1)} tok/s` : "—"}</b><p>${esc(split)}${Number.isFinite(speed) ? ` · ${speed >= 0 ? "+" : ""}${speed.toFixed(1)}%` : ""}${row.error ? ` · ${row.error}` : ""}</p></article>`;
  }).join("");
  const decision = record?.decision
    ? `<div class="ane-decision ${record.accepted ? "" : "rejected"}"><strong>${record.accepted ? "Measured option ready." : "GPU path retained."}</strong> ${esc(record.decision)}${record.executionObserved ? ` Positive trace: up to ${formatNumber(record.maxOperations)} ANE operations.` : ""}</div>`
    : "";
  $("aneResults").innerHTML = cards + decision;
}

function renderAneStatus(status = {}) {
  state.aneStatus = status;
  state.anePhase = status.phase || "idle";
  const progress = Math.max(0, Math.min(1, Number(status.progress || 0)));
  const percent = Math.round(progress * 100);
  $("anePhase").textContent = ({idle:"Ready to inspect",queued:"Queued",starting:"Loading model",running:"Measuring",stopping:"Stopping",completed:"Completed",cancelled:"Stopped",failed:"Needs attention"})[state.anePhase] || state.anePhase;
  $("anePercent").textContent = `${percent}%`;
  $("aneProgressBar").style.width = `${percent}%`;
  $("aneProgressBar").parentElement.setAttribute("aria-valuenow", String(percent));
  if (status.message) $("aneDialogStatus").textContent = status.message;
  renderAneResults(status);
  renderAneDialogSetup();
  if (state.runStatus) renderRun(state.runStatus);
  else refreshLaunchability();
  const completionId = status.phase === "completed" ? status.result?.id : "";
  if (completionId && state.aneCompletionId !== completionId) {
    state.aneCompletionId = completionId;
    loadModels(false).then(() => {
      renderAneReadiness(selectedModel()?.backends?.omlx || {});
      renderAneResults(state.aneStatus || {});
      renderAneDialogSetup();
    }).catch(() => {});
  }
}

async function pollAneStatus() {
  try { renderAneStatus(await api("/api/ane/status")); } catch (_) {}
}

async function openAneTuner() {
  if (!aneIsActive()) $("aneCpuAssist").checked = false;
  renderAneDialogSetup();
  renderAneResults(state.aneStatus || {});
  if (!$("aneDialog").open) $("aneDialog").showModal();
  await pollAneStatus();
}

async function startAneTuning() {
  const model = selectedModel();
  if (!model || aneIsActive()) return;
  try {
    const data = await api("/api/ane/start", {
      method:"POST",
      body:JSON.stringify({modelId:model.id, project:$("projectPath").value, cpuAssist:$("aneCpuAssist").checked}),
    });
    renderAneStatus({phase:"queued",progress:0,message:"ANE tuning accepted. Preparing an isolated oMLX engine…",job:data.tuning,results:[],recommendation:null,result:null});
  } catch (error) {
    $("aneDialogStatus").textContent = error.message;
    showNotice(error.message, true);
  }
}

async function stopAneTuning() {
  try {
    await api("/api/ane/stop", {method:"POST", body:"{}"});
    await Promise.all([pollStatus(), pollAneStatus()]);
  } catch (error) { $("aneDialogStatus").textContent = error.message; }
}

async function useAneResult() {
  try {
    await loadModels(false);
    const cap = selectedModel()?.backends?.omlx || {};
    if (!cap.aneTuningVerified) throw new Error("The measured result no longer matches this checkpoint, runtime, and Mac. Retune before using it.");
    $("anePrefillSelect").value = "tuned";
    $("anePrefillSelect").dispatchEvent(new Event("change", {bubbles:true}));
    showNotice("Measured ANE prefill selected. It is experimental and approximate; Preview shows the private run settings before launch.");
    $("aneDialog").close();
  } catch (error) { $("aneDialogStatus").textContent = error.message; }
}

function renderAneClonePlan(plan) {
  if (!plan) return;
  const changed = state.aneCloneRenderedPlanId !== plan.planId;
  state.aneClonePlan = plan;
  state.aneCloneRenderedPlanId = plan.planId || "";
  if (changed && !aneCloneIsActive()) $("aneCloneConsent").checked = false;
  $("aneCloneRoute").textContent = `${plan.model || plan.sourceName || "Selected checkpoint"} · separate local FP16 copy`;
  $("aneCloneSource").textContent = plan.source || "—";
  $("aneCloneSource").title = plan.source || "";
  $("aneCloneDestination").textContent = plan.destination || "—";
  $("aneCloneDestination").title = plan.destination || "";
  $("aneCloneStorage").textContent = plan.ready
    ? `${plan.requiredSizeLabel || formatBytes(plan.requiredBytes)} needed · ${plan.freeSizeLabel || formatBytes(plan.freeBytes)} free`
    : `${plan.freeSizeLabel || formatBytes(plan.freeBytes)} free`;
  $("aneCloneRuntime").textContent = plan.runtimeVersion || "Unavailable";
  $("aneCloneBlockers").innerHTML = (plan.blockers || []).map(item => `<li>${esc(item)}</li>`).join("");
  $("aneCloneConsentCopy").textContent = plan.ready
    ? `Creates ${plan.destinationName}. Approx. ${plan.sourceSizeLabel || formatBytes(plan.sourceBytes)} will be copied; the original remains read-only.`
    : "Nothing will be written until every blocker is resolved and a fresh plan is approved.";
  $("aneCloneStartLabel").textContent = plan.ready
    ? `${plan.sourceSizeLabel || formatBytes(plan.sourceBytes)} · source untouched`
    : "Resolve the blocker above";
  if (state.aneClonePhase === "idle") {
    $("aneClonePhase").textContent = "Ready to review";
    $("aneClonePercent").textContent = "0%";
    $("aneCloneProgressBar").style.width = "0%";
    $("aneCloneProgressBar").parentElement.setAttribute("aria-valuenow", "0");
    $("aneCloneStatus").textContent = plan.ready
      ? "Review the exact paths and storage estimate, then approve the separate copy if you want CPU-sharing candidates."
      : (plan.blockers || ["This copy cannot be prepared yet."])[0];
  }
  updateAneCloneControls();
}

function updateAneCloneControls() {
  const model = selectedModel();
  const readiness = model?.backends?.omlx?.aneReadiness || {};
  const active = aneCloneIsActive();
  const samePlan = Boolean(state.aneClonePlan?.modelId && state.aneClonePlan.modelId === model?.id);
  const sameResult = Boolean(state.aneCloneStatus?.result?.path && samePlan);
  const tunerActive = aneIsActive();
  const runActive = ["preflight","starting","running","stopping"].includes(state.runPhase);
  const otherActive = runActive || tunerActive || setupIsActive() || acquisitionIsActive()
    || routeCheckIsActive() || ["queued","cooldown","starting","running","stopping"].includes(state.benchmarkPhase)
    || runtimeUpdateIsActive() || runtimePromotionIsActive();
  const inspectable = Boolean(state.backend === "omlx" && model && (
    readiness.cpuCloneEligible || (samePlan && (active || sameResult))
  ));
  $("aneClonePlanButton").disabled = !inspectable || tunerActive || state.aneCloneLoading;
  $("aneClonePlanButton").textContent = active && samePlan ? "View progress…" : sameResult ? "View prepared copy…" : "Prepare copy…";
  $("aneCloneReason").textContent = active && samePlan
    ? (state.aneCloneStatus?.message || "Preparing the separate FP16 copy…")
    : readiness.cpuCloneReason || "Select a compatible BF16 checkpoint to inspect this option.";

  const plan = state.aneClonePlan;
  const canStart = Boolean(plan?.ready && samePlan && !active && !otherActive && !sameResult);
  $("aneCloneConsent").disabled = !canStart;
  $("aneCloneConsentPanel").classList.toggle("inactive", !canStart);
  $("aneCloneStartButton").disabled = !canStart || !$("aneCloneConsent").checked;
  $("aneCloneStopButton").disabled = !active;
  $("aneCloneUseButton").disabled = active || !state.aneCloneStatus?.result?.verified;
  const badge = $("aneCloneBadge");
  if (active) {
    badge.textContent = "Copy active";
    badge.className = "setup-badge active";
  } else if (state.aneCloneStatus?.result?.verified) {
    badge.textContent = "Verified";
    badge.className = "setup-badge ready";
  } else if (plan?.ready) {
    badge.textContent = "Consent required";
    badge.className = "setup-badge";
  } else {
    badge.textContent = "Read only";
    badge.className = "setup-badge warning";
  }
}

function renderAneCloneStatus(status = {}) {
  const previous = state.aneClonePhase;
  state.aneCloneStatus = status;
  state.aneClonePhase = status.phase || "idle";
  if (status.plan) renderAneClonePlan(status.plan);
  const progress = Math.max(0, Math.min(1, Number(status.progress || 0)));
  const percent = Math.round(progress * 100);
  $("aneClonePhase").textContent = ({idle:"Ready to review",queued:"Queued",validating:"Validating source",converting:"Creating FP16 copy",verifying:"Verifying copy",stopping:"Stopping",completed:"Verified",cancelled:"Stopped",failed:"Needs attention"})[state.aneClonePhase] || state.aneClonePhase;
  $("aneClonePercent").textContent = `${percent}%`;
  $("aneCloneProgressBar").style.width = `${percent}%`;
  $("aneCloneProgressBar").parentElement.setAttribute("aria-valuenow", String(percent));
  if (status.message) $("aneCloneStatus").textContent = status.message;
  if (previous !== state.aneClonePhase && ["completed","cancelled","failed"].includes(state.aneClonePhase)) {
    $("aneCloneConsent").checked = false;
  }
  updateAneCloneControls();
  updateAneControls();
  if (state.runStatus) renderRun(state.runStatus);
  else refreshLaunchability();
  const completionPath = status.phase === "completed" ? status.result?.path || "" : "";
  if (completionPath && state.aneCloneCompletionPath !== completionPath) {
    state.aneCloneCompletionPath = completionPath;
    loadModels(false).then(() => {
      updateAneCloneControls();
      renderAneDialogSetup();
    }).catch(() => {});
  }
}

async function pollAneCloneStatus() {
  try { renderAneCloneStatus(await api("/api/ane/clone/status")); } catch (_) {}
}

async function openAneClonePlan() {
  const model = selectedModel();
  if (!model) return;
  state.aneCloneLoading = true;
  $("aneCloneConsent").checked = false;
  $("aneCloneStatus").textContent = "Checking the source, destination, runtime, and free storage without writing anything…";
  if ($("aneDialog").open) $("aneDialog").close();
  if (!$("aneCloneDialog").open) $("aneCloneDialog").showModal();
  updateAneCloneControls();
  try {
    await pollAneCloneStatus();
    const currentBelongsToModel = state.aneCloneStatus?.plan?.modelId === model.id;
    if (!aneCloneIsActive() && !(state.aneCloneStatus?.phase === "completed" && currentBelongsToModel)) {
      const data = await api("/api/ane/clone/plan", {method:"POST", body:JSON.stringify({modelId:model.id})});
      state.aneClonePhase = "idle";
      renderAneClonePlan(data.plan);
    }
  } catch (error) {
    $("aneCloneStatus").textContent = error.message;
    $("aneCloneBadge").textContent = "Unavailable";
    $("aneCloneBadge").className = "setup-badge warning";
  } finally {
    state.aneCloneLoading = false;
    updateAneCloneControls();
  }
}

async function startAneClone() {
  const plan = state.aneClonePlan;
  if (!plan || !$("aneCloneConsent").checked) return;
  try {
    const data = await api("/api/ane/clone/start", {
      method:"POST",
      body:JSON.stringify({planId:plan.planId, confirmation:plan.confirmation, approved:true}),
    });
    renderAneCloneStatus({phase:"queued",progress:0,message:"Copy approved. Preparing an isolated staging folder…",plan:data.plan,result:null});
  } catch (error) {
    $("aneCloneStatus").textContent = error.message;
    showNotice(error.message, true);
  }
}

async function stopAneClone() {
  try {
    await api("/api/ane/clone/stop", {method:"POST",body:"{}"});
    await Promise.all([pollStatus(), pollAneCloneStatus()]);
  } catch (error) { $("aneCloneStatus").textContent = error.message; }
}

async function useAneClone() {
  const path = state.aneCloneStatus?.result?.path;
  if (!path) return;
  try {
    await loadModels(false);
    const model = state.models.find(item => item.path === path && item.backends?.omlx?.runnable);
    if (!model) throw new Error("The verified copy is not selectable yet. Rescan models after its folder is visible to the launcher.");
    state.backend = "omlx";
    updateBackend();
    $("modelSelect").value = model.id;
    modelChanged();
    $("aneAdvanced").open = true;
    $("aneCloneDialog").close();
    showNotice("The verified FP16 copy is selected. CPU-sharing candidates are now available inside the ANE Tuner; nothing has started.");
  } catch (error) { $("aneCloneStatus").textContent = error.message; }
}

async function showLog() {
  try { const data = await api("/api/log"); $("logContent").textContent = data.log || "No engine output yet."; $("logDialog").showModal(); }
  catch (error) { showNotice(error.message, true); }
}
async function stopRun() {
  try {
    if (state.chatAbort) state.chatAbort.abort();
    await api("/api/stop", {method:"POST", body:"{}"});
    await Promise.all([pollStatus(), pollRouteCheckStatus(), pollBenchmarkStatus(), pollSetupStatus(), pollAcquisitionStatus(), pollAneStatus(), pollAneCloneStatus(), pollRuntimeUpdateStatus()]);
  }
  catch (error) { showNotice(error.message, true); }
}

function profileRunBlocked() {
  return ["preflight","starting","running","stopping"].includes(state.runPhase)
    || ["queued","starting","running","stopping"].includes(state.routeCheckPhase)
    || ["queued","cooldown","starting","running","stopping"].includes(state.benchmarkPhase)
    || ["queued","downloading","stopping","verifying"].includes(state.setupPhase)
    || acquisitionIsActive()
    || aneWorkIsActive()
    || state.applyingOptimal;
}

function profileBackendLabel(backend) {
  return ({omlx:"oMLX", lmstudio:"LM Studio", mtplx:"MTPLX", freetoken:"FreeToken"})[backend] || backend || "Unknown engine";
}

function requestUsesExperimentalFreeToken(request = {}) {
  if (request.backend !== "freetoken") return false;
  const model = state.models.find(item => item.id === request.modelId);
  return freeTokenRoute(model) === "native" && freeTokenQualification(model).experimental;
}

function quickStartEntries() {
  const resumableChat = [...state.chatHistoryThreads]
    .filter(item => item.resumeAvailable && uiEngineVisible(item.backend))
    .sort((left, right) => Date.parse(right.updatedAt || 0) - Date.parse(left.updatedAt || 0))[0] || null;
  return {
    profile:state.profiles.find(item => item.ready) || null,
    sessionSet:state.sessionSets.find(item => item.ready) || null,
    chat:resumableChat,
  };
}

function renderQuickStart() {
  const panel = $("quickStart");
  if (!panel) return;
  const {profile, sessionSet, chat} = quickStartEntries();
  const available = Boolean(state.quickStartLoaded && (profile || sessionSet || chat));
  panel.classList.toggle("hidden", !available);
  $("customLaunchEditor").classList.remove("quick-start-collapsed");
  $("customLaunchEditor").removeAttribute("inert");
  $("customLaunchEditor").setAttribute("aria-hidden", "false");
  $("launchDock").classList.remove("quick-start-collapsed");
  const count = [profile, sessionSet, chat].filter(Boolean).length;
  if (!available) state.quickStartRoutesOpen = false;
  $("quickStartSummary").textContent = available
    ? `${count} optional shortcut${count === 1 ? "" : "s"}`
    : "Optional shortcuts are available.";
  $("quickStartCustom").setAttribute("aria-expanded", String(state.quickStartRoutesOpen));
  $("quickStartCustom").textContent = state.quickStartRoutesOpen ? "Hide saved routes" : "Show saved routes";
  $("quickStartCards").classList.toggle("hidden", !state.quickStartRoutesOpen);
  if (!available) {
    $("quickStartCards").replaceChildren();
    return;
  }
  const profileBlocked = profileRunBlocked() || state.profileBusy || state.quickStartLoading;
  const sessionBlocked = state.sessionSetBusy || state.sessionSetLoading
    || state.sessionSetPlanLoading || sessionSetIsActive() || state.quickStartLoading;
  const chatBlocked = state.chatResumeStarting || state.chatHistoryBusyId || state.quickStartLoading;
  const cards = [];
  if (profile) {
    const request = profile.request || {};
    const experimental = requestUsesExperimentalFreeToken(request);
    const engine = profile.resolution?.label || profileBackendLabel(request.backend);
    cards.push(`<article class="quick-start-card profile"><span class="quick-start-icon" aria-hidden="true">▣</span><div><small>Launch profile</small><strong title="${esc(profile.name)}">${esc(profile.name)}</strong><span title="${esc(profile.modelName || request.modelId || "")}">${esc(profile.modelName || request.modelId || "Local model")} · ${esc(engine)} · ${esc(clientName(request.client))}</span></div><button type="button" class="primary" data-quick-profile-launch="${esc(profile.id)}"${profileBlocked ? " disabled" : ""}>${experimental ? "Review" : "Launch"}</button></article>`);
  }
  if (sessionSet) {
    const request = sessionSet.baseRequest || {};
    const count = Number(sessionSet.surfaceCount || 0);
    cards.push(`<article class="quick-start-card session-set"><span class="quick-start-icon" aria-hidden="true">▤</span><div><small>Session Set</small><strong title="${esc(sessionSet.name)}">${esc(sessionSet.name)}</strong><span title="${esc(sessionSet.modelName || request.modelId || "")}">${esc(sessionSet.modelName || request.modelId || "Local model")} · ${formatNumber(count)} surface${count === 1 ? "" : "s"}</span></div><button type="button" class="secondary" data-quick-session-review="${esc(sessionSet.id)}"${sessionBlocked ? " disabled" : ""}>Review</button></article>`);
  }
  if (chat) {
    const activeChat = state.runPhase === "running" && Boolean(state.chatRunId);
    cards.push(`<article class="quick-start-card chat"><span class="quick-start-icon" aria-hidden="true">●</span><div><small>Previous chat</small><strong title="${esc(chat.title || "Local chat")}">${esc(chat.title || "Local chat")}</strong><span title="${esc(chat.model || "Local model")}">${esc(chat.model || "Local model")} · ${esc(profileBackendLabel(chat.backend))}${chat.resumeNeedsSystemPrompt ? " · prompt re-entry" : ""}</span></div><button type="button" class="secondary" data-quick-chat="${esc(chat.id)}"${chatBlocked ? " disabled" : ""}>${activeChat ? "Open" : "Review"}</button></article>`);
  }
  $("quickStartCards").innerHTML = cards.join("");
}

function setQuickStartEditor(open, scroll = false) {
  if (open && state.models.length) updateWorkSurface();
  if (scroll && open) requestAnimationFrame(() => {
    $("customLaunchEditor").scrollIntoView({behavior:"smooth", block:"start"});
  });
}

function toggleQuickStartRoutes() {
  state.quickStartRoutesOpen = !state.quickStartRoutesOpen;
  renderQuickStart();
  if (state.quickStartRoutesOpen) requestAnimationFrame(() => {
    $("quickStartCards").scrollIntoView({behavior:"smooth", block:"nearest"});
  });
}

async function loadQuickStart(force = false) {
  if (state.quickStartLoading || (state.quickStartLoaded && !force)) {
    renderQuickStart();
    return;
  }
  state.quickStartLoading = true;
  state.quickStartError = "";
  renderQuickStart();
  const [profiles, sessionSets, chatHistory] = await Promise.allSettled([
    api("/api/profiles"), api("/api/session-sets"), api("/api/chat/history"),
  ]);
  if (profiles.status === "fulfilled") useProfileInventory(profiles.value);
  if (sessionSets.status === "fulfilled") useSessionSetInventory(sessionSets.value);
  if (chatHistory.status === "fulfilled" && Array.isArray(chatHistory.value.threads)) {
    state.chatHistoryThreads = chatHistory.value.threads;
  }
  const errors = [profiles, sessionSets, chatHistory]
    .filter(result => result.status === "rejected")
    .map(result => result.reason?.message || "Saved routes could not be checked.");
  state.quickStartError = errors.join(" ");
  state.quickStartLoaded = true;
  state.quickStartLoading = false;
  renderQuickStart();
}

async function reviewQuickSessionSet(setId) {
  if (state.sessionSetBusy || state.sessionSetPlanLoading || sessionSetIsActive()) return;
  await openSessionSetManager();
  if (!state.sessionSets.some(item => item.id === setId && item.ready)) {
    setSessionSetMessage("That saved workspace is no longer ready. Review its current status below.", "error");
    return;
  }
  await planSessionSet(setId);
}

function profileDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Saved locally" : `Updated ${date.toLocaleDateString([], {month:"short", day:"numeric"})}`;
}

function setProfileStatus(message, kind = "") {
  const status = $("profileManagerStatus");
  status.textContent = message;
  status.className = `profile-manager-status${kind ? ` ${kind}` : ""}`;
}

function useProfileInventory(data) {
  state.profiles = Array.isArray(data?.profiles) ? data.profiles.filter(uiProfileVisible) : [];
  state.profileLimit = Number(data?.limit || 32);
  renderQuickStart();
}

function updateProfilePolicyControls() {
  const measured = $("profilePolicySelect").value === "measured";
  const locked = state.profileBusy || state.profileLoading;
  $("profileGoalField").classList.toggle("inactive", !measured);
  $("profileGoalSelect").disabled = !measured || locked;
  $("profilePolicyHelp").textContent = measured
    ? "Rechecks matching measurements whenever this profile is applied."
    : "Reuses the selected engine and exact runtime controls.";
  $("profileName").disabled = locked;
  $("profilePolicySelect").disabled = locked;
  $("profileSaveButton").disabled = locked || !$("profileName").value.trim();
  $("profileCancelEdit").disabled = locked;
  $("profileCancelEdit").classList.toggle("hidden", !state.profileEditingId);
  $("profileSaveButton").querySelector("strong").textContent = state.profileEditingId ? "Update profile" : "Save current settings";
  $("profileSaveButton").querySelector("small").textContent = state.profileEditingId ? "Replace with visible settings" : "Nothing starts";
}

function renderProfiles() {
  renderQuickStart();
  const count = state.profiles.length;
  $("profileCountBadge").textContent = state.profileLoading ? "Loading" : `${count}/${state.profileLimit} saved`;
  const blocked = profileRunBlocked() || state.profileBusy;
  if (!count && !state.profileLoading) {
    $("profileCards").innerHTML = `<div class="profile-empty"><strong>No launch profiles yet</strong><span>Name the current setup above to save its engine, model, work surface, limits, reasoning, sampling, KV precision, and runtime controls.</span></div>`;
    updateProfilePolicyControls();
    return;
  }
  $("profileCards").innerHTML = state.profiles.map(profile => {
    const request = profile.request || {};
    const options = request.options || {};
    const experimentalFreeToken = profile.ready && requestUsesExperimentalFreeToken(request);
    const resolution = profile.resolution || {};
    const policy = profile.enginePolicy === "measured";
    const engine = resolution.label || profileBackendLabel(request.backend);
    const policyLabel = policy
      ? `${enginePreferenceLabels[profile.enginePreference] || "Measured goal"} · ${engine}`
      : `Fixed · ${engine}`;
    const resolutionDetail = profile.ready
      ? experimentalFreeToken
        ? "Settings are reusable; experimental approval is deliberately never saved. Review it before a new model run."
        : (resolution.detail || "Ready to apply.")
      : (profile.reason || "This saved route is no longer available.");
    const disabled = !profile.ready || blocked;
    const armed = state.profileDeleteConfirmId === profile.id;
    const editing = state.profileEditingId === profile.id;
    const client = clientName(request.client || "");
    const limits = request.context && request.output
      ? `${formatNumber(request.context)} / ${formatNumber(request.output)}`
      : "Unavailable";
    const kv = options.kv && options.kv !== "off" ? String(options.kv).toUpperCase() : "Full";
    return `<article class="profile-card ${profile.ready ? "ready" : "unavailable"}${editing ? " editing" : ""}">
      <header><div class="profile-card-title"><span class="profile-card-icon" aria-hidden="true">${policy ? "◇" : "▣"}</span><span><strong title="${esc(profile.name)}">${esc(profile.name)}</strong><small title="${esc(profile.modelName || request.modelId || "")}">${esc(profile.modelName || request.modelId || "Unknown model")} · ${esc(profileDate(profile.updatedAt))}</small></span></div><em class="profile-card-state">${experimentalFreeToken ? "Review" : profile.ready ? "Ready" : "Unavailable"}</em></header>
      <div class="profile-contract"><span><small>Surface</small><b>${esc(client)}</b></span><span><small>Context / output</small><b>${esc(limits)}</b></span><span><small>Reasoning</small><b>${esc(request.reasoning || "auto")}</b></span><span><small>KV precision</small><b>${esc(kv)}</b></span></div>
      <code class="profile-project" title="${esc(request.project || "")}">${esc(request.project || "Project unavailable")}</code>
      <div class="profile-resolution"><i aria-hidden="true">${profile.ready ? (resolution.trustedWinner ? "◆" : "◇") : "×"}</i><span><strong>${esc(policyLabel)}</strong><small>${esc(resolutionDetail)}</small></span></div>
      <div class="profile-actions"><button type="button" class="primary profile-launch" data-profile-launch="${esc(profile.id)}" ${disabled ? "disabled" : ""}>${experimentalFreeToken ? "Review" : "Launch"}</button><button type="button" class="secondary" data-profile-apply="${esc(profile.id)}" ${disabled ? "disabled" : ""}>Apply</button><button type="button" class="text-button" data-profile-edit="${esc(profile.id)}" ${state.profileBusy ? "disabled" : ""}>${editing ? "Editing" : "Edit"}</button><button type="button" class="danger profile-delete${armed ? " armed" : ""}" data-profile-delete="${esc(profile.id)}" ${state.profileBusy ? "disabled" : ""}>${armed ? "Confirm delete" : "Delete"}</button></div>
    </article>`;
  }).join("");
  updateProfilePolicyControls();
}

async function loadProfiles() {
  if (state.profileLoading) return;
  state.profileLoading = true;
  renderProfiles();
  setProfileStatus("Rechecking every saved route against the current model catalog and installed engines…");
  try {
    const data = await api("/api/profiles");
    useProfileInventory(data);
    setProfileStatus(state.profiles.length
      ? "Profiles were rechecked locally. Unavailable routes stay saved but cannot be applied."
      : "Save the current visible setup above. No engine will start.");
  } catch (error) {
    setProfileStatus(error.message, "error");
  } finally {
    state.profileLoading = false;
    renderProfiles();
  }
}

async function openProfileManager() {
  state.profileDeleteConfirmId = "";
  setQuickStartEditor(true);
  if (!$("profileDialog").open) $("profileDialog").showModal();
  await loadProfiles();
}

function resetProfileEditor(clearName = true) {
  state.profileEditingId = "";
  if (clearName) $("profileName").value = "";
  $("profilePolicySelect").value = "fixed";
  $("profileGoalSelect").value = "fastest";
  renderProfiles();
}

function editProfile(profileId) {
  const profile = state.profiles.find(item => item.id === profileId);
  if (!profile || state.profileBusy) return;
  state.profileEditingId = profile.id;
  state.profileDeleteConfirmId = "";
  $("profileName").value = profile.name;
  $("profilePolicySelect").value = profile.enginePolicy;
  $("profileGoalSelect").value = profile.enginePreference;
  setProfileStatus(`Updating “${profile.name}”. Saving will replace it with the current visible launcher settings.`);
  renderProfiles();
  $("profileName").focus();
}

function setProfileSelect(id, value, label) {
  const control = $(id);
  const option = [...control.options].find(item => item.value === String(value) && !item.disabled);
  if (!option) throw new Error(`${label} is no longer available in the current launcher controls.`);
  control.value = String(value);
}

function applyProfileRequest(request) {
  if (!uiRequestVisible(request)) {
    throw new Error("This saved route uses an engine that is temporarily hidden in this launcher build.");
  }
  cancelOptimization("A saved launch profile replaced the visible runtime controls.");
  state.backend = request.backend;
  state.client = request.client;
  updateBackend(true);
  const modelOption = [...$("modelSelect").options].find(option => option.value === request.modelId && !option.disabled);
  if (!modelOption) throw new Error("This profile's model is no longer available in its saved engine.");
  $("modelSelect").value = request.modelId;
  modelChanged();
  $("projectPath").value = request.project;
  $("contextInput").value = String(request.context);
  $("outputInput").value = String(request.output);
  setProfileSelect("reasoningSelect", request.reasoning, "The saved reasoning level");
  if (request.client !== "chat") {
    setProfileSelect("agentHostSelect", request.agentHost || "terminal", "The saved agent window");
  }
  const options = request.options || {};
  setProfileSelect("accelerationSelect", options.acceleration, "The saved acceleration route");
  if (!setRuntimeKvValue(request.backend, options.kv || "off")) {
    throw new Error("The saved KV precision is no longer available in this engine.");
  }
  const optionControls = {
    profile:"profileSelect", fan:"fanSelect", burst:"burstSelect",
    dflashVerify:"dflashVerifySelect", dflashDraftQuant:"dflashDraftQuantSelect",
    anePrefill:"anePrefillSelect", gpu:"gpuSelect",
  };
  for (const [key, id] of Object.entries(optionControls)) {
    if (options[key] !== undefined) setProfileSelect(id, options[key], `The saved ${key} control`);
  }
  if (options.depth !== undefined) $("depthInput").value = String(options.depth);
  if (options.parallel !== undefined) $("parallelInput").value = String(options.parallel);
  if (options.mtpMinTokens !== undefined) $("mtpMinTokensInput").value = String(options.mtpMinTokens);
  if (options.mtpMinContinueProbability !== undefined) $("mtpMinContinueProbabilityInput").value = String(options.mtpMinContinueProbability);
  if (request.backend === "freetoken") {
    if (options.maxBatchSize !== undefined) setProfileSelect("freeTokenBatchSelect", options.maxBatchSize, "The saved active-sequence count");
    if (options.prefixCacheEntries !== undefined) setProfileSelect("freeTokenPrefixCacheSelect", options.prefixCacheEntries, "The saved prefix-cache size");
    $("freeTokenExpertCacheInput").value = options.expertCacheSize === null || options.expertCacheSize === undefined
      ? "" : String(options.expertCacheSize);
    $("freeTokenExperimentalConsent").checked = false;
    $("freeTokenExperimentalConsent").dataset.modelId = "";
    updateFreeTokenNativeControls();
  }
  setRangeVisual($("depthInput"), $("depthValue"));
  setRangeVisual($("parallelInput"), $("parallelValue"));
  setRangeVisual($("mtpMinTokensInput"), $("mtpMinTokensValue"));
  setRangeVisual($("mtpMinContinueProbabilityInput"), $("mtpMinContinueProbabilityValue"));
  if (request.client === "chat") {
    const chat = request.chat || {};
    $("systemPrompt").value = chat.systemPrompt || "";
    setProfileSelect("samplingMode", chat.sampling || "model", "The saved sampling mode");
    if (chat.sampling === "custom") {
      $("temperatureInput").value = String(chat.temperature);
      $("topPInput").value = String(chat.topP);
      $("topKInput").value = String(chat.topK);
      $("presencePenaltyInput").value = String(chat.presencePenalty ?? 0);
      $("frequencyPenaltyInput").value = String(chat.frequencyPenalty ?? 0);
      $("seedInput").value = chat.seed === null || chat.seed === undefined ? "" : String(chat.seed);
    }
  }
  updateAccelerationState();
  updateChatSamplingControls();
  state.optimalSignature = "";
  state.optimalLabel = "";
  setOptimizationState("custom", "Saved profile", "The profile's exact visible settings are applied.");
  refreshLaunchability();
}

async function applySavedProfile(profileId, launchAfter = false) {
  if (state.profileBusy || profileRunBlocked()) return;
  state.profileBusy = true;
  state.profileDeleteConfirmId = "";
  refreshLaunchability();
  setProfileStatus("Rechecking this profile against current local engines, models, and measurements…");
  try {
    const inventory = await api("/api/profiles");
    useProfileInventory(inventory);
    const profile = state.profiles.find(item => item.id === profileId);
    if (!profile) throw new Error("That launch profile no longer exists.");
    if (!profile.ready) throw new Error(profile.reason || "This launch profile is no longer available.");
    applyProfileRequest(profile.request);
    if (profile.enginePolicy === "measured") {
      setProfileStatus(`Applying “${profile.name}” and rechecking its measured engine goal…`);
      const optimized = await applyOptimal("engine", profile.enginePreference);
      if (!optimized) throw new Error("The measured engine decision could not be applied. The profile was not launched.");
    }
    if (launchAfter && freeTokenExperimentalConsentRequired()) {
      setQuickStartEditor(true);
      if ($("profileDialog").open) $("profileDialog").close();
      $("advancedControls").open = true;
      showNotice(`Applied “${profile.name}”. Its FreeToken approval was not saved; review the amber checkpoint evidence and approve this new experimental run before launching.`);
      requestAnimationFrame(() => {
        $("freeTokenQualificationPanel").scrollIntoView({behavior:"smooth", block:"center"});
        $("freeTokenExperimentalConsent").focus();
      });
      return;
    }
    if (launchAfter) {
      setProfileStatus(`Launching “${profile.name}” with the revalidated visible contract…`);
      const started = await launch();
      if (!started) throw new Error("The profile was applied, but final launch validation did not accept it.");
      if ($("profileDialog").open) $("profileDialog").close();
    } else {
      setQuickStartEditor(true);
      if ($("profileDialog").open) $("profileDialog").close();
      showNotice(`Applied “${profile.name}”${profile.enginePolicy === "measured" ? ` · ${state.optimalLabel || "measured engine decision"}` : " · fixed engine"}.`);
    }
  } catch (error) {
    if (launchAfter) setQuickStartEditor(true);
    setProfileStatus(error.message, "error");
    showNotice(error.message, true);
  } finally {
    state.profileBusy = false;
    refreshLaunchability();
    if ($("profileDialog").open) renderProfiles();
  }
}

async function saveCurrentProfile() {
  if (state.profileBusy || state.profileLoading) return;
  let request;
  try { request = gather("custom"); }
  catch (error) { setProfileStatus(error.message, "error"); return; }
  const name = $("profileName").value.trim();
  if (!name) { setProfileStatus("Give this launch profile a name.", "error"); return; }
  const editing = state.profileEditingId;
  state.profileBusy = true;
  refreshLaunchability();
  setProfileStatus(editing ? "Validating and updating this local profile…" : "Validating and saving these settings locally…");
  try {
    const body = {
      name,
      enginePolicy:$("profilePolicySelect").value,
      enginePreference:$("profileGoalSelect").value,
      request,
    };
    if (editing) body.id = editing;
    const data = await api("/api/profiles/save", {method:"POST", body:JSON.stringify(body)});
    useProfileInventory(data);
    state.profileEditingId = "";
    $("profileName").value = "";
    $("profilePolicySelect").value = "fixed";
    $("profileGoalSelect").value = "fastest";
    setProfileStatus(editing ? "Profile updated. Nothing was started." : "Profile saved privately on this Mac. Nothing was started.", "success");
  } catch (error) {
    setProfileStatus(error.message, "error");
  } finally {
    state.profileBusy = false;
    refreshLaunchability();
    renderProfiles();
  }
}

async function deleteSavedProfile(profileId) {
  if (state.profileBusy) return;
  const profile = state.profiles.find(item => item.id === profileId);
  if (!profile) return;
  if (state.profileDeleteConfirmId !== profileId) {
    state.profileDeleteConfirmId = profileId;
    setProfileStatus(`Click Confirm delete to permanently remove “${profile.name}”.`);
    renderProfiles();
    return;
  }
  state.profileBusy = true;
  renderProfiles();
  setProfileStatus(`Deleting “${profile.name}”…`);
  try {
    const data = await api("/api/profiles/delete", {method:"POST", body:JSON.stringify({id:profileId})});
    useProfileInventory(data);
    if (state.profileEditingId === profileId) resetProfileEditor();
    state.profileDeleteConfirmId = "";
    setProfileStatus(`“${profile.name}” was deleted. This local preset cannot be recovered.`, "success");
  } catch (error) {
    setProfileStatus(error.message, "error");
  } finally {
    state.profileBusy = false;
    renderProfiles();
  }
}

const SESSION_SET_ACTIVE_PHASES = new Set(["starting", "waiting", "attaching", "stopping"]);
const SESSION_SET_FINISHED_PHASES = new Set(["completed", "failed", "cancelled"]);

function sessionSetIsActive(status = state.sessionSetStatus) {
  return SESSION_SET_ACTIVE_PHASES.has(status?.phase || "idle");
}

function currentSessionSetRoute() {
  const run = state.runStatus?.run;
  return state.runPhase === "running" && run?.purpose === "session" && uiEngineVisible(run.backend)
    ? run : null;
}

function setSessionSetMessage(message, kind = "") {
  const status = $("sessionSetStatus");
  status.textContent = message || "";
  status.className = `session-dashboard-status${kind ? ` ${kind}` : ""}`;
}

function useSessionSetInventory(data) {
  state.sessionSets = Array.isArray(data?.sets) ? data.sets.filter(uiSessionSetVisible) : [];
  state.sessionSetLimit = Number(data?.limit || 16);
  renderQuickStart();
}

function useSessionSetStatus(data, announceFinished = false) {
  const next = data?.sessionSet || data;
  if (!next || typeof next !== "object") return;
  state.sessionSetStatus = next;
  if (sessionSetIsActive(next) && next.setId) state.sessionSetSelectedId = next.setId;
  const finished = SESSION_SET_FINISHED_PHASES.has(next.phase);
  const completionId = String(next.jobId || "");
  if (!announceFinished && finished && completionId) {
    state.sessionSetCompletionId = completionId;
  } else if (announceFinished && finished && completionId && state.sessionSetCompletionId !== completionId) {
    state.sessionSetCompletionId = completionId;
    const failed = next.phase === "failed";
    showNotice(next.message || (failed ? "The Session Set could not finish opening." : "Session Set opening finished."), failed);
    void pollStatus();
  }
}

function sessionSetFactMarkup(facts) {
  return facts.map(([label, value]) => `<span><small>${esc(label)}</small><b title="${esc(String(value))}">${esc(String(value))}</b></span>`).join("");
}

function renderSessionSetPlan() {
  const panel = $("sessionSetPlanPanel");
  const openButton = $("sessionSetOpenButton");
  const stopButton = $("sessionSetStopButton");
  const consentPanel = $("sessionSetConsentPanel");
  const warning = $("sessionSetPlanWarning");
  const status = state.sessionSetStatus || {};
  const active = sessionSetIsActive(status);
  const selectedFinished = (
    SESSION_SET_FINISHED_PHASES.has(status.phase)
    && status.jobId
    && status.setId === state.sessionSetSelectedId
    && !state.sessionSetPlan
    && !state.sessionSetPlanLoading
  );

  if (active || selectedFinished) {
    panel.classList.remove("hidden");
    const finished = SESSION_SET_FINISHED_PHASES.has(status.phase);
    const stateLabels = {
      starting:"Starting", waiting:"Loading model", attaching:"Opening surfaces",
      stopping:"Stopping", completed:"Opened", failed:"Needs attention", cancelled:"Stopped",
    };
    $("sessionSetPlanTitle").textContent = `${finished ? "Result" : "Opening"} · ${status.setName || "Session Set"}`;
    $("sessionSetPlanState").textContent = stateLabels[status.phase] || status.phase || "Working";
    $("sessionSetPlanDetail").textContent = status.message || "Opening this saved workspace.";
    $("sessionSetPlanFacts").innerHTML = sessionSetFactMarkup([
      ["Route", status.mode === "launch" ? "New model load" : status.mode === "reuse" ? "Resident model" : "No changes"],
      ["Saved surfaces", formatNumber(status.totalSurfaceCount || 0)],
      ["Newly opened", formatNumber(status.openedSurfaceCount || 0)],
      ["Still pending", formatNumber(status.pendingSurfaceCount || 0)],
    ]);
    warning.textContent = status.error || "";
    warning.classList.toggle("hidden", !status.error);
    consentPanel.classList.add("hidden");
    stopButton.classList.toggle("hidden", !active);
    stopButton.disabled = state.sessionSetBusy || status.phase === "stopping";
    openButton.classList.add("hidden");
    return;
  }

  const plan = state.sessionSetPlan;
  if (!plan && !state.sessionSetPlanLoading) {
    panel.classList.add("hidden");
    return;
  }
  panel.classList.remove("hidden");
  openButton.classList.remove("hidden");
  stopButton.classList.add("hidden");
  if (state.sessionSetPlanLoading) {
    $("sessionSetPlanTitle").textContent = "Checking saved workspace";
    $("sessionSetPlanState").textContent = "Read-only";
    $("sessionSetPlanDetail").textContent = "Revalidating the model, engine, projects, work surfaces, resident route, and current memory headroom…";
    $("sessionSetPlanFacts").innerHTML = "";
    warning.classList.add("hidden");
    consentPanel.classList.add("hidden");
    openButton.disabled = true;
    openButton.querySelector("strong").textContent = "Checking plan";
    openButton.querySelector("small").textContent = "Nothing opens during review";
    return;
  }

  const modeLabels = {
    launch:"Load one model", reuse:"Reuse loaded model",
    "already-open":"No changes", blocked:"Unavailable",
  };
  $("sessionSetPlanTitle").textContent = plan.setName || "Opening plan";
  $("sessionSetPlanState").textContent = plan.requiresExperimentalApproval ? "Experimental" : plan.ready ? "Ready" : "Blocked";
  $("sessionSetPlanDetail").textContent = plan.detail || "Review the exact opening plan.";
  $("sessionSetPlanFacts").innerHTML = sessionSetFactMarkup([
    ["Route", modeLabels[plan.mode] || plan.mode || "Unavailable"],
    ["Saved surfaces", formatNumber(plan.surfaceCount || 0)],
    ["Already matched", formatNumber(plan.existingMatchCount || 0)],
    ["Opening now", formatNumber(plan.willOpenSurfaceCount || 0)],
    ["Window mix", `${formatNumber(plan.hubConsoleCount || 0)} Hub · ${formatNumber(plan.chatCount || 0)} Chat · ${formatNumber(plan.terminalCount || 0)} Terminal`],
  ]);
  const warnings = [];
  if (plan.terminalCount) {
    warnings.push(
      `${formatNumber(plan.terminalCount)} agent${Number(plan.terminalCount) === 1 ? "" : "s"} will open as an external Terminal handoff. `
      + "The launcher cannot monitor those window lifetimes, so saved Terminal surfaces are always treated as new windows."
    );
  }
  if (plan.unverifiedTerminalHandoffCount) {
    warnings.push(
      `The resident route also has ${formatNumber(plan.unverifiedTerminalHandoffCount)} earlier Terminal handoff `
      + `registration${Number(plan.unverifiedTerminalHandoffCount) === 1 ? "" : "s"} whose window state cannot be verified.`
    );
  }
  if (plan.admission?.requiresAcknowledgement) {
    warnings.push(`${plan.admission.label || "Memory review required"}: ${plan.admission.detail || "Review the current memory estimate."}`);
  }
  if (plan.requiresExperimentalApproval) {
    warnings.push("This new native FreeToken load has only tiny-synthetic end-to-end verification. The saved Session Set does not contain approval, and no large model download is recommended.");
  }
  warning.textContent = warnings.join(" ");
  warning.classList.toggle("hidden", warnings.length === 0);
  const needsConsent = Boolean(
    plan.ready
    && plan.mode !== "already-open"
    && (plan.requiresExperimentalApproval || plan.admission?.requiresAcknowledgement)
  );
  consentPanel.classList.toggle("hidden", !needsConsent);
  $("sessionSetConsentTitle").textContent = plan.requiresExperimentalApproval
    ? plan.admission?.requiresAcknowledgement
      ? "I accept this memory estimate and approve this explicit experimental FreeToken run."
      : "I reviewed the evidence and approve this explicit experimental FreeToken run."
    : plan.admission?.requiresAcknowledgement
      ? "I accept this current memory estimate and exact opening plan."
      : "I accept this exceptional opening plan.";
  $("sessionSetConsentCopy").textContent = plan.requiresExperimentalApproval
    ? "This one approval is bound to the current opening plan and is never saved back into the Session Set."
    : plan.mode === "launch"
    ? "This will load one model, open its primary surface, then attach the remaining surfaces to the same private relay."
    : "This will open only the missing surfaces on the already-loaded model.";
  const consentAccepted = !needsConsent || $("sessionSetConsent").checked;
  openButton.disabled = !plan.ready || state.sessionSetBusy || !consentAccepted;
  openButton.querySelector("strong").textContent = plan.action?.label || (plan.ready ? "Open Session Set" : "Unavailable");
  openButton.querySelector("small").textContent = plan.mode === "launch"
    ? "One shared model route"
    : plan.mode === "reuse"
    ? "No model reload"
    : plan.mode === "already-open"
    ? "No process or window changes"
    : "Resolve the issue above";
}

function renderSessionSets() {
  renderQuickStart();
  const count = state.sessionSets.length;
  const route = currentSessionSetRoute();
  const operationActive = sessionSetIsActive();
  const locked = state.sessionSetBusy || state.sessionSetLoading || operationActive;
  $("sessionSetCountBadge").textContent = state.sessionSetLoading ? "Loading" : `${count}/${state.sessionSetLimit} saved`;
  $("sessionSetCountBadge").className = `setup-badge${state.sessionSetLoading ? "" : " ready"}`;

  const attachments = Array.isArray(state.runStatus?.attachments) ? state.runStatus.attachments : [];
  const surfaceCount = route ? Math.max(1, attachments.length) : 0;
  $("sessionSetSaveSummary").textContent = route
    ? `${surfaceCount} work surface${surfaceCount === 1 ? "" : "s"} share ${route.model} through ${profileBackendLabel(route.backend)}. Saving captures settings only.`
    : operationActive
    ? (state.sessionSetStatus?.message || "A Session Set is opening.")
    : "Start a normal model session to save its current agents and Chats.";
  $("sessionSetName").disabled = locked || !route;
  $("sessionSetSaveButton").disabled = locked || !route || !$("sessionSetName").value.trim();
  $("sessionSetSaveButton").textContent = state.sessionSetEditingId ? "Replace saved set" : "Save current session";
  $("sessionSetCancelEdit").classList.toggle("hidden", !state.sessionSetEditingId);
  $("sessionSetCancelEdit").disabled = locked;

  if (!count) {
    $("sessionSetCards").innerHTML = state.sessionSetLoading
      ? `<div class="session-set-empty"><strong>Checking saved Session Sets…</strong><span>Nothing is being launched.</span></div>`
      : `<div class="session-set-empty"><strong>No Session Sets yet</strong><span>Start one model session, attach the agents and Chats you want, then save that complete workspace above.</span></div>`;
    renderSessionSetPlan();
    return;
  }
  $("sessionSetCards").innerHTML = state.sessionSets.map(item => {
    const selected = item.id === state.sessionSetSelectedId;
    const editing = item.id === state.sessionSetEditingId;
    const armed = item.id === state.sessionSetDeleteConfirmId;
    const labels = Array.isArray(item.surfaceLabels) ? item.surfaceLabels : [];
    const chips = labels.length
      ? labels.map((label, index) => `<span>${index === 0 ? "Primary · " : ""}${esc(label)}</span>`).join("")
      : `<span>${formatNumber(item.surfaceCount || 0)} saved surface${Number(item.surfaceCount) === 1 ? "" : "s"}</span>`;
    const request = item.baseRequest || {};
    const experimentalFreeToken = item.ready && requestUsesExperimentalFreeToken(request);
    const detail = item.ready
      ? `${profileBackendLabel(request.backend)} · ${formatNumber(item.surfaceCount || 0)} surface${Number(item.surfaceCount) === 1 ? "" : "s"}${item.terminalCount ? ` · ${formatNumber(item.terminalCount)} external Terminal` : ""}${experimentalFreeToken ? " · new model loads need fresh experimental approval" : ""}`
      : (item.reason || "This saved workspace is no longer available.");
    return `<article class="session-set-card ${item.ready ? "ready" : "unavailable"}${selected ? " selected" : ""}">
      <header><div class="session-set-card-title"><i aria-hidden="true">▤</i><span><strong title="${esc(item.name)}">${esc(item.name)}</strong><small title="${esc(item.modelName || request.modelId || "")}">${esc(item.modelName || request.modelId || "Unknown model")} · ${esc(profileDate(item.updatedAt))}</small></span></div><em>${experimentalFreeToken ? "Review" : item.ready ? "Ready" : "Unavailable"}</em></header>
      <div class="session-set-surfaces">${chips}</div>
      <p class="session-set-card-detail">${esc(detail)}</p>
      <div class="session-set-card-actions"><button type="button" class="primary session-set-review" data-session-set-review="${esc(item.id)}" ${!item.ready || locked ? "disabled" : ""}>Review opening</button><button type="button" class="secondary" data-session-set-apply="${esc(item.id)}" ${!item.ready || locked || profileRunBlocked() ? "disabled" : ""}>Apply primary</button><button type="button" class="text-button" data-session-set-edit="${esc(item.id)}" ${locked || !route ? "disabled" : ""}>${editing ? "Replacing" : "Replace"}</button><button type="button" class="danger${armed ? " armed" : ""}" data-session-set-delete="${esc(item.id)}" ${locked ? "disabled" : ""}>${armed ? "Confirm delete" : "Delete"}</button></div>
    </article>`;
  }).join("");
  renderSessionSetPlan();
}

async function loadSessionSets(initial = false) {
  if (state.sessionSetLoading) return;
  state.sessionSetLoading = true;
  renderSessionSets();
  if (!initial) setSessionSetMessage("Rechecking saved workspaces against the current models, engines, and live route…");
  try {
    const [inventory, status] = await Promise.all([
      api("/api/session-sets"), api("/api/session-sets/status"),
    ]);
    useSessionSetInventory(inventory);
    useSessionSetStatus(status, false);
    if (!sessionSetIsActive()) {
      setSessionSetMessage(countSessionSetsMessage(), "");
    } else {
      setSessionSetMessage(state.sessionSetStatus?.message || "A Session Set is opening.");
    }
  } catch (error) {
    setSessionSetMessage(error.message, "error");
  } finally {
    state.sessionSetLoading = false;
    renderSessionSets();
  }
}

function countSessionSetsMessage() {
  return state.sessionSets.length
    ? "Every saved route was checked locally. Review an opening plan before any model, agent, Chat, or window starts."
    : "Save a running multi-surface workspace above. No model or window starts while saving.";
}

async function openSessionSetManager() {
  state.sessionSetDeleteConfirmId = "";
  state.sessionSetPlan = null;
  state.sessionSetPlanLoading = false;
  state.sessionSetSelectedId = sessionSetIsActive() ? (state.sessionSetStatus?.setId || "") : "";
  $("sessionSetConsent").checked = false;
  if (!$("sessionSetDialog").open) $("sessionSetDialog").showModal();
  await loadSessionSets(true);
}

function resetSessionSetEditor(clearName = true) {
  state.sessionSetEditingId = "";
  if (clearName) $("sessionSetName").value = "";
  renderSessionSets();
}

function editSessionSet(setId) {
  const item = state.sessionSets.find(entry => entry.id === setId);
  if (!item || state.sessionSetBusy || !currentSessionSetRoute()) return;
  state.sessionSetEditingId = item.id;
  state.sessionSetDeleteConfirmId = "";
  $("sessionSetName").value = item.name;
  setSessionSetMessage(`Replacing “${item.name}”. Saving will use the complete workspace that is running now.`);
  renderSessionSets();
  $("sessionSetName").focus();
}

async function saveCurrentSessionSet() {
  if (state.sessionSetBusy || state.sessionSetLoading || !currentSessionSetRoute()) return;
  const name = $("sessionSetName").value.trim();
  if (!name) { setSessionSetMessage("Give this Session Set a name.", "error"); return; }
  const editing = state.sessionSetEditingId;
  state.sessionSetBusy = true;
  renderSessionSets();
  setSessionSetMessage(editing ? "Validating and replacing this saved workspace…" : "Validating and saving this running workspace locally…");
  try {
    const body = {name};
    if (editing) body.id = editing;
    const data = await api("/api/session-sets/save-active", {method:"POST", body:JSON.stringify(body)});
    useSessionSetInventory(data);
    if (state.sessionSetSelectedId === editing) state.sessionSetPlan = null;
    state.sessionSetEditingId = "";
    $("sessionSetName").value = "";
    setSessionSetMessage(editing
      ? "Session Set replaced with the current work surfaces. No new process or window was started."
      : "Session Set saved privately on this Mac. No new process or window was started.", "success");
  } catch (error) {
    setSessionSetMessage(error.message, "error");
  } finally {
    state.sessionSetBusy = false;
    renderSessionSets();
  }
}

async function applySessionSetPrimary(setId) {
  if (state.sessionSetBusy || profileRunBlocked()) return;
  state.sessionSetBusy = true;
  renderSessionSets();
  setSessionSetMessage("Rechecking the saved primary route before applying its visible controls…");
  try {
    const inventory = await api("/api/session-sets");
    useSessionSetInventory(inventory);
    const item = state.sessionSets.find(entry => entry.id === setId);
    if (!item) throw new Error("That Session Set no longer exists.");
    if (!item.ready) throw new Error(item.reason || "That Session Set is no longer available.");
    applyProfileRequest(item.baseRequest);
    setQuickStartEditor(true);
    if ($("sessionSetDialog").open) $("sessionSetDialog").close();
    showNotice(`Applied the primary settings from “${item.name}”. Nothing was started.`);
  } catch (error) {
    setSessionSetMessage(error.message, "error");
    showNotice(error.message, true);
  } finally {
    state.sessionSetBusy = false;
    renderSessionSets();
  }
}

async function deleteSavedSessionSet(setId) {
  if (state.sessionSetBusy || sessionSetIsActive()) return;
  const item = state.sessionSets.find(entry => entry.id === setId);
  if (!item) return;
  if (state.sessionSetDeleteConfirmId !== setId) {
    state.sessionSetDeleteConfirmId = setId;
    setSessionSetMessage(`Click Confirm delete to permanently remove “${item.name}”.`);
    renderSessionSets();
    return;
  }
  state.sessionSetBusy = true;
  renderSessionSets();
  setSessionSetMessage(`Deleting “${item.name}”…`);
  try {
    const data = await api("/api/session-sets/delete", {method:"POST", body:JSON.stringify({id:setId})});
    useSessionSetInventory(data);
    if (state.sessionSetSelectedId === setId) {
      state.sessionSetSelectedId = "";
      state.sessionSetPlan = null;
    }
    if (state.sessionSetEditingId === setId) resetSessionSetEditor();
    state.sessionSetDeleteConfirmId = "";
    setSessionSetMessage(`“${item.name}” was deleted. This settings-only preset cannot be recovered.`, "success");
  } catch (error) {
    setSessionSetMessage(error.message, "error");
  } finally {
    state.sessionSetBusy = false;
    renderSessionSets();
  }
}

async function planSessionSet(setId) {
  if (state.sessionSetBusy || state.sessionSetPlanLoading || sessionSetIsActive()) return;
  state.sessionSetSelectedId = setId;
  state.sessionSetDeleteConfirmId = "";
  state.sessionSetPlan = null;
  state.sessionSetPlanLoading = true;
  $("sessionSetConsent").checked = false;
  setSessionSetMessage("Building a side-effect-free opening plan…");
  renderSessionSets();
  try {
    const data = await api("/api/session-sets/plan", {method:"POST", body:JSON.stringify({id:setId})});
    state.sessionSetPlan = data.plan || null;
    setSessionSetMessage(state.sessionSetPlan?.ready
      ? "Plan ready. Nothing has opened yet."
      : (state.sessionSetPlan?.detail || "This Session Set cannot open yet."),
    state.sessionSetPlan?.ready ? "success" : "error");
  } catch (error) {
    state.sessionSetPlan = null;
    setSessionSetMessage(error.message, "error");
  } finally {
    state.sessionSetPlanLoading = false;
    renderSessionSets();
    requestAnimationFrame(() => $("sessionSetPlanPanel").scrollIntoView({behavior:"smooth", block:"nearest"}));
  }
}

async function openPlannedSessionSet() {
  const plan = state.sessionSetPlan;
  if (!plan?.ready || state.sessionSetBusy || sessionSetIsActive()) return;
  const needsConsent = Boolean(
    plan.mode !== "already-open"
    && (plan.requiresExperimentalApproval || plan.admission?.requiresAcknowledgement)
  );
  if (needsConsent && !$("sessionSetConsent").checked) {
    setSessionSetMessage("Review and approve the exact opening plan first.", "error");
    return;
  }
  const body = {id:plan.setId, confirmation:plan.confirmation};
  if (plan.requiresExperimentalApproval) {
    body.experimentalQualificationConsent = true;
  }
  if (plan.admission?.requiresAcknowledgement) {
    body.memoryAcknowledgement = plan.admission.contractId;
  }
  state.sessionSetBusy = true;
  renderSessionSets();
  setSessionSetMessage(plan.mode === "already-open" ? "Confirming the resident workspace…" : "Opening the Session Set…");
  try {
    const data = await api("/api/session-sets/open", {method:"POST", body:JSON.stringify(body)});
    state.sessionSetPlan = null;
    useSessionSetStatus(data, true);
    setSessionSetMessage(data.sessionSet?.message || "Session Set opening started.", data.sessionSet?.phase === "failed" ? "error" : "success");
    await pollStatus();
  } catch (error) {
    setSessionSetMessage(error.message, "error");
    showNotice(error.message, true);
  } finally {
    state.sessionSetBusy = false;
    renderSessionSets();
  }
}

async function loadSessionSetStatus(announceFinished = true) {
  if (state.sessionSetStatusLoading) return;
  state.sessionSetStatusLoading = true;
  try {
    const data = await api("/api/session-sets/status");
    useSessionSetStatus(data, announceFinished);
    if (sessionSetIsActive()) setSessionSetMessage(state.sessionSetStatus?.message || "A Session Set is opening.");
    renderSessionSets();
  } catch (_) {
    // The main controller poll owns connection-loss messaging.
  } finally {
    state.sessionSetStatusLoading = false;
  }
}

async function cancelSessionSetOpen() {
  if (state.sessionSetBusy || !sessionSetIsActive()) return;
  state.sessionSetBusy = true;
  renderSessionSets();
  try {
    const data = await api("/api/session-sets/stop", {method:"POST", body:"{}"});
    useSessionSetStatus(data, false);
    setSessionSetMessage(data.sessionSet?.message || "Stopping the remaining work surfaces…");
  } catch (error) {
    setSessionSetMessage(error.message, "error");
  } finally {
    state.sessionSetBusy = false;
    renderSessionSets();
  }
}

function applyBootstrapData(boot, setProject = false) {
  state.token = boot.token || state.token;
  if (boot.controllerSourceCurrent === false) {
    showNotice(
      boot.controllerRestartMessage
        || "LLM Launcher was updated. Restart the launcher and refresh this page before starting new work.",
      true,
    );
  }
  if (boot.binaries) state.binaries = boot.binaries;
  if (boot.adapters) state.adapters = boot.adapters;
  if (boot.clientSupport) state.clientSupport = boot.clientSupport;
  if (boot.freeToken) state.freeToken = boot.freeToken;
  const binaries = Object.entries(state.binaries).filter(([name]) => (
    uiFeatureEnabled("freetoken") || !String(name).startsWith("freetoken")
  ));
  const binaryLabels = {lms:"LM Studio", hf:"Model downloader", freetoken:"FreeToken"};
  $("toolCount").textContent = `${binaries.filter(([,value]) => value.installed).length}/${binaries.length} ready`;
  $("binaryList").innerHTML = binaries.map(([name, value]) => `<div class="binary ${value.installed ? "" : "missing"}"><div><strong>${esc(binaryLabels[name] || name)}</strong><span title="${esc(value.path || "")}">${esc(value.version)}</span></div><em>${value.installed ? "Ready" : "Missing"}</em><i aria-hidden="true"></i></div>`).join("");
  if (setProject && !$("projectPath").value) {
    $("projectPath").value = boot.roots?.find(root => root.label === "Documents")?.path?.replace(/\/models$/i, "/Code") || "";
  }
  renderFreeTokenConnection();
}

function modelLibraryCheckMarkup(check) {
  const marker = check.state === "pass" ? "✓" : check.state === "advisory" ? "!" : "×";
  return `<div class="model-library-check ${esc(check.state)}"><i aria-hidden="true">${marker}</i><span><strong>${esc(check.label)}</strong><small>${esc(check.detail)}</small></span></div>`;
}

function visibleModelLibraryEngines(model = {}) {
  return (model.engines || []).filter(engine => uiEngineVisible(engine.id));
}

function visibleModelLibraryOverview(model = {}) {
  const engines = visibleModelLibraryEngines(model);
  const runnable = engines.filter(engine => engine.runnable);
  const ready = runnable.filter(engine => !engine.experimental);
  const experimental = runnable.filter(engine => engine.experimental);
  const routes = engines.reduce((total, engine) => total + (engine.surfaces || [])
    .filter(surface => surface.supported).length, 0);
  const accelerators = engines.reduce((total, engine) => total + (engine.modes || [])
    .filter(mode => mode.available && mode.id !== "ar").length, 0);
  const evidenceRuns = engines.reduce((total, engine) => (
    total + Number(engine.evidence?.savedRuns || 0)
  ), 0);
  return {
    engines, runnable, ready, experimental, routes, accelerators, evidenceRuns,
    state:ready.length ? "ready" : experimental.length ? "attention" : "blocked",
  };
}

function modelLibraryEngineMarkup(model, engine) {
  const modes = (engine.modes || []).filter(mode => mode.available);
  const surfaces = (engine.surfaces || []).map(surface => `<span class="model-library-surface ${surface.supported ? "supported" : "unavailable"}" title="${esc(surface.reason)}">${esc(surface.label)}</span>`).join("");
  const latest = engine.evidence?.latest;
  const evidence = engine.experimental
    ? `<div class="model-library-evidence experimental"><strong>Synthetic path verified · real checkpoint not qualified</strong><span>An existing local checkpoint can be selected only for an explicit experimental run. This receipt does not recommend a large model download.</span><small>Runtime-owned qualification schema 1</small></div>`
    : latest
    ? `<div class="model-library-evidence"><strong>${esc(latest.winnerLabel || "Measured route")} won the last saved ${esc(latest.suite || "local")} run</strong><span>${esc(latest.recommendation || "Matching local benchmark evidence is saved for this model and runtime.")}</span><small>${esc(latest.createdAt ? new Date(latest.createdAt).toLocaleString([], {dateStyle:"medium", timeStyle:"short"}) : "Saved locally")} · ${formatNumber(engine.evidence.savedRuns)} matching run${Number(engine.evidence.savedRuns) === 1 ? "" : "s"}</small></div>`
    : `<div class="model-library-evidence empty"><strong>No matching saved route evidence</strong><span>Availability is not a speed claim. Use Benchmark Lab before automatically preferring an accelerator.</span></div>`;
  const engineState = engine.experimental ? "Experimental" : engine.runnable ? "Ready" : engine.status === "runtime-missing" ? "Missing" : "Unavailable";
  const actionLabel = engine.experimental ? "Select experimental route" : engine.runnable ? `Use with ${esc(engine.label)}` : "Route unavailable";
  const actionDetail = engine.experimental
    ? "Requires explicit approval; starts nothing here"
    : engine.evidence?.savedRuns ? `${formatNumber(engine.evidence.savedRuns)} saved evidence run${Number(engine.evidence.savedRuns) === 1 ? "" : "s"}` : "Selection changes no files and starts nothing";
  return `<section class="model-library-engine ${esc(engine.status)}">
    <header><div><span class="runtime-icon ${esc(engine.id === "lmstudio" ? "lms" : engine.id)}" aria-hidden="true">${esc(backendMark(engine.id))}</span><span><strong>${esc(engine.label)}</strong><small>${esc(engine.reason)}</small></span></div><em>${engineState}</em></header>
    <div class="model-library-engine-facts"><div><small>Decode modes</small><span class="model-library-pills">${modes.map(mode => `<b title="${esc(mode.detail)}">${esc(mode.label)}</b>`).join("") || "None"}</span></div><div><small>Work surfaces</small><span class="model-library-pills">${surfaces}</span></div></div>
    ${evidence}
    <div class="model-library-engine-action"><span>${actionDetail}</span><button type="button" class="text-button" data-library-model="${esc(model.id)}" data-library-backend="${esc(engine.id)}" ${engine.runnable ? "" : "disabled"}>${actionLabel}</button></div>
  </section>`;
}

function modelLibraryCardMarkup(model) {
  const doctor = model.doctor || {};
  const isSelected = state.selected?.id === model.id;
  const engineScoped = state.modelLibraryEngine !== "all";
  const overview = visibleModelLibraryOverview(model);
  const visibleEngines = state.modelLibraryEngine === "all"
    ? overview.engines
    : overview.engines.filter(engine => engine.id === state.modelLibraryEngine);
  const scopedEngine = engineScoped ? visibleEngines[0] : null;
  const scopedRoutes = scopedEngine
    ? (scopedEngine.surfaces || []).filter(surface => surface.supported).length
    : overview.routes;
  const scopedModes = scopedEngine
    ? (scopedEngine.modes || []).filter(mode => mode.available).length
    : overview.accelerators;
  const cardState = engineScoped
    ? (scopedEngine?.experimental ? "attention" : scopedEngine?.runnable ? "ready" : "blocked")
    : overview.state;
  const stateLabel = engineScoped
    ? (scopedEngine?.experimental ? "Experimental" : scopedEngine?.runnable ? "Ready" : "Unavailable")
    : overview.state === "ready" ? "Ready" : overview.state === "attention" ? "Review" : "Blocked";
  const diagnosisHeadline = engineScoped
    ? scopedEngine?.experimental
      ? `${scopedEngine.label} is available only as an experimental run.`
      : scopedEngine?.runnable
      ? `Ready with ${scopedEngine.label}.`
      : `${scopedEngine?.label || backendName(state.modelLibraryEngine)} cannot use this checkpoint.`
    : overview.ready.length
      ? `Ready with ${overview.ready.map(engine => engine.label).join(", ")}.`
      : overview.experimental.length
        ? "A visible engine route needs review."
        : "No visible engine can use this checkpoint.";
  const diagnosisDetail = engineScoped
    ? (scopedEngine?.reason || "This engine has no compatible route for the checkpoint.")
    : overview.ready.length
      ? `${formatNumber(overview.routes)} supported work-surface route${overview.routes === 1 ? "" : "s"} across the engines shown here.`
      : (overview.experimental[0]?.reason || overview.engines[0]?.reason || "No visible compatibility report is available.");
  const detailSummary = engineScoped
    ? `${formatNumber(scopedRoutes)} ready surface${scopedRoutes === 1 ? "" : "s"} · ${formatNumber(scopedModes)} decode mode${scopedModes === 1 ? "" : "s"}`
    : `${formatNumber(overview.runnable.length)} engines · ${formatNumber(overview.accelerators)} accelerators · ${formatNumber(overview.evidenceRuns)} evidence runs`;
  return `<article class="model-library-card ${esc(cardState)}">
    <header><div><span class="model-library-format" aria-hidden="true">${esc(String(model.format || "?").slice(0, 4).toUpperCase())}</span><span><strong>${esc(model.name)}</strong><small>${esc(model.architecture)} · ${esc(model.origins?.join(" + ") || "Detected locally")}</small></span></div><em>${esc(stateLabel)}</em></header>
    <div class="model-library-meta"><span>${esc(String(model.format || "unknown").toUpperCase())}</span><span>${esc(model.quantization)}</span><span>${esc(model.sizeLabel)}</span><span>${model.nativeContext ? `${formatNumber(model.nativeContext)} context` : "Context unknown"}</span><span>${formatNumber(scopedRoutes)} ${scopedEngine?.experimental ? "experimental" : "ready"} route${scopedRoutes === 1 ? "" : "s"}</span></div>
    <code class="model-library-path" title="${esc(model.path)}">${esc(model.path)}</code>
    <div class="model-library-diagnosis"><i aria-hidden="true">${cardState === "ready" ? "✓" : cardState === "attention" ? "!" : "×"}</i><p><strong>${esc(diagnosisHeadline)}</strong><span>${esc(diagnosisDetail)}</span></p></div>
    <details class="model-library-details" ${isSelected ? "open" : ""}><summary><span>${engineScoped ? `${esc(scopedEngine?.label || backendName(state.modelLibraryEngine))} details` : "Compatibility details"}</span><small>${detailSummary}</small></summary><div>
      <div class="model-library-checks">${(doctor.checks || []).map(modelLibraryCheckMarkup).join("")}</div>
      <div class="model-library-engines">${visibleEngines.map(engine => modelLibraryEngineMarkup(model, engine)).join("")}</div>
    </div></details>
  </article>`;
}

function modelLibraryMatches(model) {
  if (!uiModelVisible(model)) return false;
  const visibleEngines = visibleModelLibraryEngines(model);
  const scopedEngine = state.modelLibraryEngine === "all"
    ? null
    : visibleEngines.find(item => item.id === state.modelLibraryEngine);
  const scopedState = scopedEngine?.experimental ? "attention" : scopedEngine?.runnable ? "ready" : "blocked";
  if (
    state.modelLibraryState !== "all"
    && (scopedEngine ? scopedState : model.doctor?.state) !== state.modelLibraryState
  ) return false;
  if (state.modelLibraryEngine !== "all") {
    const engine = visibleEngines.find(item => item.id === state.modelLibraryEngine);
    if (!engine) return false;
  }
  if (state.modelLibrarySurface !== "all") {
    const candidateEngines = scopedEngine ? [scopedEngine] : visibleEngines;
    const supported = candidateEngines.some(engine =>
      (engine.surfaces || []).some(surface => surface.id === state.modelLibrarySurface && surface.supported));
    if (!supported) return false;
  }
  const query = state.modelLibraryQuery.trim().toLowerCase();
  if (!query) return true;
  const searchable = [
    model.name, model.path, model.format, model.architecture, model.modelType,
    model.quantization, ...(model.origins || []), model.doctor?.headline,
    model.doctor?.nextAction,
    ...visibleEngines.flatMap(engine => [
      engine.label, engine.reason, ...(engine.modes || []).map(mode => mode.label),
      ...(engine.surfaces || []).flatMap(surface => [surface.label, surface.reason]),
    ]),
  ].join(" ").toLowerCase();
  return searchable.includes(query);
}

function renderModelLibrary() {
  const inventory = state.modelLibrary;
  if (!inventory) return;
  if (!uiEngineVisible(state.modelLibraryEngine)) {
    state.modelLibraryEngine = "all";
    $("modelLibraryEngineFilter").value = "all";
  }
  const allModels = (inventory.models || []).filter(uiModelVisible);
  const models = allModels.filter(modelLibraryMatches);
  const visibleReports = allModels.map(visibleModelLibraryOverview);
  const summary = {
    models:allModels.length,
    ready:visibleReports.filter(report => report.state === "ready").length,
    attention:visibleReports.filter(report => report.state === "attention").length,
    blocked:visibleReports.filter(report => report.state === "blocked").length,
    launchableRoutes:visibleReports.reduce((total, report) => total + report.routes, 0),
  };
  $("modelLibraryBadge").textContent = `${formatNumber(summary.models)} detected`;
  $("modelLibraryBadge").className = `setup-badge ${summary.blocked ? "warning" : "ready"}`;
  const scoped = state.modelLibraryEngine !== "all";
  const scopedReports = scoped ? models.map(model =>
    visibleModelLibraryEngines(model).find(engine => engine.id === state.modelLibraryEngine)
  ).filter(Boolean) : [];
  const summaryFacts = scoped ? [
    [models.length, "shown"],
    [scopedReports.filter(engine => engine.runnable && !engine.experimental).length, "qualified / ready"],
    [scopedReports.filter(engine => engine.experimental).length, "experimental"],
    [scopedReports.filter(engine => !engine.runnable).length, "unavailable"],
  ] : [
    [models.length, "shown"], [summary.ready || 0, "ready"],
    [summary.attention || 0, "review"], [summary.blocked || 0, "blocked"],
    [summary.launchableRoutes || 0, "ready routes"],
  ];
  $("modelLibrarySummary").innerHTML = summaryFacts.map(([value, label]) => `<span><strong>${formatNumber(value)}</strong><small>${esc(label)}</small></span>`).join("");
  $("modelLibraryCards").innerHTML = models.length
    ? models.map(modelLibraryCardMarkup).join("")
    : `<div class="model-library-empty"><strong>No models match these filters.</strong><span>Clear the filters or rescan the known folders.</span></div>`;
  const filtered = Boolean(state.modelLibraryQuery || state.modelLibraryEngine !== "all" || state.modelLibrarySurface !== "all" || state.modelLibraryState !== "all");
  $("clearModelLibraryFilters").disabled = !filtered;
}

async function loadModelLibrary() {
  if (state.modelLibraryLoading) return;
  state.modelLibraryLoading = true;
  $("refreshModelLibrary").disabled = true;
  $("refreshModelLibrary").textContent = "Scanning…";
  $("modelLibraryStatus").textContent = "Scanning known local folders and installed commands without loading a model…";
  if (!state.modelLibrary) $("modelLibraryCards").innerHTML = '<div class="model-library-empty"><strong>Building the compatibility report…</strong><span>No model process is being started.</span></div>';
  try {
    const data = await api("/api/model-library");
    state.modelLibrary = data.modelLibrary;
    state.modelLibraryRoots = data.roots || [];
    if (Array.isArray(data.models)) {
      state.models = data.models;
      renderModelOptions();
      if (state.quickStartLoaded) void loadQuickStart(true);
    }
    renderModelLibrary();
    const existingRoots = state.modelLibraryRoots.filter(root => root.exists);
    $("modelLibraryStatus").textContent = `Checked ${formatNumber(existingRoots.length)} existing model root${existingRoots.length === 1 ? "" : "s"} locally at ${new Date().toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"})}. Nothing was started or changed.`;
  } catch (error) {
    $("modelLibraryStatus").textContent = error.message;
  } finally {
    state.modelLibraryLoading = false;
    $("refreshModelLibrary").disabled = false;
    $("refreshModelLibrary").textContent = "Rescan known folders";
  }
}

async function openModelLibrary() {
  if (!$("modelLibraryDialog").open) $("modelLibraryDialog").showModal();
  if (state.modelLibrary) renderModelLibrary();
  else await loadModelLibrary();
}

async function openFreeTokenModelReview() {
  if (!uiFeatureEnabled("freetoken")) return;
  state.modelLibraryQuery = "";
  state.modelLibraryEngine = "freetoken";
  state.modelLibrarySurface = "all";
  state.modelLibraryState = "all";
  $("modelLibrarySearch").value = "";
  $("modelLibraryEngineFilter").value = "freetoken";
  $("modelLibrarySurfaceFilter").value = "all";
  $("modelLibraryStateFilter").value = "all";
  await openModelLibrary();
  renderModelLibrary();
  $("modelLibraryStatus").textContent = "Showing every detected checkpoint against native or connected FreeToken. Incompatible models stay visible with their exact reason; nothing was loaded or downloaded.";
}

function clearModelLibraryFilters() {
  state.modelLibraryQuery = "";
  state.modelLibraryEngine = "all";
  state.modelLibrarySurface = "all";
  state.modelLibraryState = "all";
  $("modelLibrarySearch").value = "";
  $("modelLibraryEngineFilter").value = "all";
  $("modelLibrarySurfaceFilter").value = "all";
  $("modelLibraryStateFilter").value = "all";
  renderModelLibrary();
  $("modelLibrarySearch").focus();
}

function useModelLibraryRoute(modelId, backend) {
  if (!uiEngineVisible(backend)) {
    $("modelLibraryStatus").textContent = "That engine is temporarily hidden in this launcher build.";
    return;
  }
  const rawModel = state.models.find(model => model.id === modelId);
  const report = state.modelLibrary?.models?.find(model => model.id === modelId);
  const engine = report?.engines?.find(item => item.id === backend);
  if (!rawModel || !engine?.runnable) {
    $("modelLibraryStatus").textContent = "That route changed during the scan. Refresh the library before selecting it.";
    return;
  }
  state.backend = backend;
  updateBackend();
  const option = [...$("modelSelect").options].find(item => item.value === modelId && !item.disabled);
  if (!option) {
    $("modelLibraryStatus").textContent = "The model is no longer selectable for that engine. Refresh the library.";
    return;
  }
  $("modelSelect").value = modelId;
  modelChanged();
  setQuickStartEditor(true);
  scheduleBenchmarkHistory();
  $("modelLibraryDialog").close();
  showNotice(`${rawModel.name} with ${engine.label} is selected. Nothing has started.`);
}

function acquisitionIsActive(status = state.acquisitionStatus || {}) {
  return ["queued","downloading","stopping","verifying"].includes(status.phase || state.acquisitionPhase);
}

function acquisitionOtherOperationActive() {
  return ["preflight","starting","running","stopping"].includes(state.runPhase)
    || routeCheckIsActive()
    || ["queued","cooldown","starting","running","stopping"].includes(state.benchmarkPhase)
    || setupIsActive()
    || aneWorkIsActive();
}

function renderAcquisitionRoots() {
  if (!state.acquisitionRoots.length) return;
  const select = $("acquisitionDestination");
  const previous = select.value;
  select.innerHTML = state.acquisitionRoots.map(root => `<option value="${esc(root.id)}">${esc(root.label)}</option>`).join("");
  if (state.acquisitionRoots.some(root => root.id === previous)) select.value = previous;
  const root = state.acquisitionRoots.find(item => item.id === select.value);
  $("acquisitionDestinationHelp").textContent = root
    ? `${root.label}: ${root.path}`
    : "Only a fixed known model folder can be used.";
}

function renderAcquisitionSearchResults() {
  const results = state.acquisitionSearchResults || [];
  if (!results.length) {
    $("acquisitionSearchResults").innerHTML = state.acquisitionSearching
      ? '<div class="acquisition-search-empty"><strong>Searching the public Hub…</strong><span>No model files are being downloaded.</span></div>'
      : "";
    return;
  }
  $("acquisitionSearchResults").innerHTML = results.map(result => {
    const format = result.formats?.length ? result.formats.join(" + ") : "Inspect files";
    const stateLabel = result.disabled ? "Disabled" : result.private ? "Private" : result.gated ? "Gated" : result.draftOnly ? "Draft component" : "Public";
    return `<article class="acquisition-search-result ${result.inspectable ? "" : "blocked"}">
      <div><strong>${esc(result.id)}</strong><span>${esc(format)} · ${esc(result.quantization || "Inspect files")} · ${esc(result.license || "License not declared")}</span><small>${formatNumber(result.downloads)} downloads · ${formatNumber(result.likes)} likes</small></div>
      <div><em>${esc(stateLabel)}</em><button type="button" class="text-button" data-acquisition-repo="${esc(result.id)}" data-acquisition-revision="${esc(result.revision || "")}" ${result.inspectable ? "" : "disabled"}>Inspect</button></div>
    </article>`;
  }).join("");
}

function acquisitionCheckMarkup(check = {}) {
  const marker = check.state === "pass" ? "✓" : check.state === "advisory" ? "!" : "×";
  return `<article class="acquisition-check ${esc(check.state || "blocked")}"><i aria-hidden="true">${marker}</i><div><strong>${esc(check.label || "Check")}</strong><span>${esc(check.detail || "No detail available.")}</span></div></article>`;
}

function renderAcquisitionPlan(plan) {
  if (!plan?.repo || !plan?.destination) return;
  const changed = state.acquisitionPlan?.id !== plan.id;
  state.acquisitionPlan = plan;
  if (changed) $("acquisitionConsent").checked = false;

  const variants = Array.isArray(plan.variants) ? plan.variants : [];
  const selection = plan.selection;
  const showVariants = variants.length > 1;
  $("acquisitionVariantField").classList.toggle("hidden", !showVariants);
  if (showVariants) {
    $("acquisitionVariant").innerHTML = [
      '<option value="">Choose one exact file set…</option>',
      ...variants.map(variant => `<option value="${esc(variant.id)}">${esc(variant.label)} · ${formatBytes(variant.sizeBytes)}</option>`),
    ].join("");
    $("acquisitionVariant").value = selection?.id || "";
  }

  const pinned = String(plan.repo.pinnedRevision || "");
  const repoParts = String(plan.repo.id || "").split("/").map(encodeURIComponent);
  const repoUrl = `https://huggingface.co/${repoParts.join("/")}/tree/${encodeURIComponent(pinned)}`;
  const blocked = (plan.checks || []).some(check => check.state === "blocked");
  const facts = [
    ["Pinned commit", pinned ? pinned.slice(0, 12) : "Unavailable", pinned],
    ["License", plan.repo.license || "Not declared", plan.repo.license || "Not declared"],
    ["Exact file set", selection?.label || (plan.variantRequired ? "Choose a variant" : "Unavailable"), selection?.label || ""],
    ["Selected size", selection ? formatBytes(selection.sizeBytes) : "—", selection ? `${selection.fileCount} exact files` : ""],
    ["Remaining", selection ? formatBytes(plan.destination.remainingBytes) : "—", selection ? `${formatBytes(plan.destination.existingBytes)} already present` : ""],
    ["Destination", plan.destination.label || plan.destination.kind, plan.destination.path || ""],
  ];
  const engines = (plan.expectedEngines || []).map(engine => `<article class="acquisition-engine ${engine.expectedCompatible ? "expected" : "unavailable"}"><span class="runtime-icon ${esc(engine.id === "lmstudio" ? "lms" : engine.id)}" aria-hidden="true">${esc(backendMark(engine.id))}</span><div><strong>${esc(engine.label)}</strong><small>${esc(engine.detail)}</small></div><em>${engine.expectedReady ? "Installed · expected" : engine.expectedCompatible ? "Expected · runtime missing" : "Not this format"}</em></article>`).join("");
  const files = selection?.files || [];
  const fileList = files.length
    ? `<details class="acquisition-files"><summary><span>Review ${formatNumber(files.length)} exact files</span><small>Names, sizes, and available pinned checksums</small></summary><div>${files.map(file => `<span><code title="${esc(file.path)}">${esc(file.path)}</code><b>${formatBytes(file.size)}</b><small>${file.sha256 ? `SHA-256 ${esc(file.sha256.slice(0, 16))}…` : "Exact size verification"}</small></span>`).join("")}</div></details>`
    : "";
  $("acquisitionPlan").innerHTML = `<div class="acquisition-plan-heading"><div><span>${esc(selection?.format?.toUpperCase() || "HUB")}</span><div><h3>${esc(plan.repo.id)}</h3><p>${selection ? `${esc(selection.label)} at one immutable commit.` : "Choose one exact supported file set."}</p></div></div><a href="${repoUrl}" target="_blank" rel="noreferrer">Review model page ↗</a></div>
    <div class="acquisition-facts">${facts.map(([label,value,title]) => `<span><small>${esc(label)}</small><strong title="${esc(title)}">${esc(value)}</strong></span>`).join("")}</div>
    <div class="acquisition-checks">${(plan.checks || []).map(acquisitionCheckMarkup).join("")}</div>
    <section class="acquisition-engine-plan"><div><h4>Expected local routes</h4><p>These are scanner predictions, not speed claims. Model Library performs the post-download compatibility scan, then Benchmark Lab measures this Mac.</p></div><div>${engines}</div></section>
    ${fileList}
    <p class="acquisition-plan-note ${blocked ? "blocked" : ""}">${blocked ? "This plan cannot start until every blocked check is resolved." : `Approval is bound to ${esc(plan.confirmation)} and expires at ${esc(new Date(plan.expiresAt).toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"}))}.`}</p>`;

  $("acquisitionStartTitle").textContent = plan.actionLabel || "Download pinned files";
  $("acquisitionStartLabel").textContent = selection
    ? `${formatBytes(plan.destination.remainingBytes)} remaining · resumable`
    : "Choose one exact file set";
  $("acquisitionConsentCopy").textContent = selection
    ? `${plan.repo.id}@${pinned.slice(0, 12)} · ${selection.fileCount} exact files · ${plan.destination.path}. No runtime or downloaded code will be started.`
    : "Choose one exact file set before approval is available.";
  $("acquisitionBadge").textContent = blocked ? (plan.variantRequired ? "Choose variant" : "Blocked") : "Consent required";
  $("acquisitionBadge").className = `setup-badge${blocked ? " warning" : ""}`;
  if (!acquisitionIsActive()) {
    $("acquisitionStatus").textContent = blocked
      ? ((plan.checks || []).find(check => check.state === "blocked")?.detail || "Resolve the blocked checks before downloading.")
      : `Inspection complete. Nothing has been downloaded; review the pinned model page and exact plan before approval.`;
  }
  updateAcquisitionControls();
}

function updateAcquisitionControls() {
  const active = acquisitionIsActive();
  const otherWork = acquisitionOtherOperationActive();
  const plan = state.acquisitionPlan;
  const consentReady = Boolean(plan?.canStart && plan?.selection && !active && !otherWork);
  $("acquisitionSearch").disabled = active || state.acquisitionSearching;
  $("acquisitionSearchButton").disabled = active || state.acquisitionSearching;
  for (const id of ["acquisitionRepoId","acquisitionRevision","acquisitionDestination","acquisitionVariant"]) {
    $(id).disabled = active || state.acquisitionInspecting;
  }
  $("acquisitionInspectButton").disabled = active || state.acquisitionInspecting;
  $("acquisitionConsent").disabled = !consentReady;
  $("acquisitionConsentPanel").classList.toggle("inactive", !consentReady);
  if (!consentReady) $("acquisitionConsent").checked = false;
  $("acquisitionStartButton").disabled = !consentReady || !$("acquisitionConsent").checked;
  $("acquisitionStopButton").disabled = !active;
  $("acquisitionOpenLibrary").disabled = state.acquisitionPhase !== "completed" || !state.acquisitionStatus?.result;
  if (otherWork && plan?.canStart && !active) {
    $("acquisitionConsentCopy").textContent = "Finish or stop the active launcher operation before approving this pinned acquisition.";
  }
}

function renderAcquisitionStatus(envelope = {}) {
  const status = envelope.acquisition || envelope;
  if (Array.isArray(envelope.roots)) {
    state.acquisitionRoots = envelope.roots;
    renderAcquisitionRoots();
  }
  if (typeof envelope.downloaderReady === "boolean") state.acquisitionDownloaderReady = envelope.downloaderReady;
  const previous = state.acquisitionPhase;
  state.acquisitionStatus = status;
  state.acquisitionPhase = status.phase || "idle";
  if (status.plan) renderAcquisitionPlan(status.plan);
  const progress = Math.max(0, Math.min(1, Number(status.progress || 0)));
  const percent = Math.round(progress * 100);
  $("acquisitionPercent").textContent = `${percent}%`;
  $("acquisitionProgressBar").style.width = `${percent}%`;
  $("acquisitionProgressBar").parentElement.setAttribute("aria-valuenow", String(percent));
  $("acquisitionPhase").textContent = ({
    idle:"Ready to inspect", queued:"Queued", downloading:"Downloading pinned files",
    stopping:"Stopping", verifying:"Verifying files", completed:"Verified",
    cancelled:"Stopped · resumable", failed:"Needs attention",
  })[state.acquisitionPhase] || state.acquisitionPhase;
  if (status.message && (state.acquisitionPhase !== "idle" || !state.acquisitionPlan)) {
    $("acquisitionStatus").textContent = status.message;
  }
  if (acquisitionIsActive()) {
    $("acquisitionBadge").textContent = state.acquisitionPhase === "verifying" ? "Verifying" : "Download active";
    $("acquisitionBadge").className = "setup-badge active";
  } else if (state.acquisitionPhase === "completed") {
    $("acquisitionBadge").textContent = "Pinned files verified";
    $("acquisitionBadge").className = "setup-badge ready";
  } else if (["cancelled","failed"].includes(state.acquisitionPhase)) {
    $("acquisitionBadge").textContent = state.acquisitionPhase === "failed" ? "Check required" : "Files preserved";
    $("acquisitionBadge").className = "setup-badge warning";
  }
  if (previous !== state.acquisitionPhase && ["completed","cancelled","failed"].includes(state.acquisitionPhase)) {
    $("acquisitionConsent").checked = false;
  }
  updateAcquisitionControls();
  if (state.runStatus) renderRun(state.runStatus);
  else refreshLaunchability();
  const completedId = status.phase === "completed" && status.result
    ? `${status.result.repoId}@${status.result.pinnedRevision}` : "";
  if (completedId && state.acquisitionCompletionId !== completedId) {
    state.acquisitionCompletionId = completedId;
    loadModels(false).catch(() => {});
  }
}

async function pollAcquisitionStatus() {
  try { renderAcquisitionStatus(await api("/api/acquisition/status")); } catch (_) {}
}

async function openAcquisitionCenter() {
  if ($("modelLibraryDialog").open) $("modelLibraryDialog").close();
  if (!$("acquisitionDialog").open) $("acquisitionDialog").showModal();
  await pollAcquisitionStatus();
  if (!state.acquisitionDownloaderReady) {
    $("acquisitionStatus").textContent = "The launcher-managed public model downloader is unavailable. Search and inspection may be unavailable until a supported oMLX runtime is installed.";
  }
}

async function searchAcquisitionModels() {
  const query = $("acquisitionSearch").value.trim();
  if (state.acquisitionSearching || acquisitionIsActive()) return;
  state.acquisitionSearching = true;
  state.acquisitionSearchResults = [];
  renderAcquisitionSearchResults();
  $("acquisitionStatus").textContent = `Searching the public Hub for “${query}”. No model files are being downloaded…`;
  updateAcquisitionControls();
  try {
    const data = await api("/api/acquisition/search", {method:"POST", body:JSON.stringify({query})});
    state.acquisitionSearchResults = data.search?.results || [];
    renderAcquisitionSearchResults();
    $("acquisitionStatus").textContent = state.acquisitionSearchResults.length
      ? `Found ${state.acquisitionSearchResults.length} public result${state.acquisitionSearchResults.length === 1 ? "" : "s"}. Choose Inspect to pin and validate its exact file tree.`
      : "No public text-generation repositories matched that search.";
  } catch (error) {
    $("acquisitionSearchResults").innerHTML = `<div class="acquisition-search-empty error"><strong>Search unavailable.</strong><span>${esc(error.message)}</span></div>`;
    $("acquisitionStatus").textContent = error.message;
  } finally {
    state.acquisitionSearching = false;
    updateAcquisitionControls();
  }
}

async function inspectAcquisitionModel(variantId = "") {
  if (state.acquisitionInspecting || acquisitionIsActive()) return;
  const repoId = $("acquisitionRepoId").value.trim();
  const revision = $("acquisitionRevision").value.trim();
  const destination = $("acquisitionDestination").value;
  const generation = ++state.acquisitionGeneration;
  state.acquisitionInspecting = true;
  $("acquisitionStatus").textContent = "Reading public repository metadata and the pinned file tree. Nothing is being downloaded…";
  $("acquisitionBadge").textContent = "Inspecting";
  $("acquisitionBadge").className = "setup-badge active";
  updateAcquisitionControls();
  try {
    const data = await api("/api/acquisition/inspect", {
      method:"POST", body:JSON.stringify({repoId, revision, destination, variantId}),
    });
    if (generation !== state.acquisitionGeneration) return;
    renderAcquisitionPlan(data.plan);
  } catch (error) {
    if (generation === state.acquisitionGeneration) {
      $("acquisitionStatus").textContent = error.message;
      $("acquisitionBadge").textContent = "Inspection failed";
      $("acquisitionBadge").className = "setup-badge warning";
    }
  } finally {
    if (generation === state.acquisitionGeneration) {
      state.acquisitionInspecting = false;
      updateAcquisitionControls();
    }
  }
}

async function startAcquisition() {
  const plan = state.acquisitionPlan;
  if (!plan || !$("acquisitionConsent").checked || acquisitionIsActive()) return;
  try {
    const data = await api("/api/acquisition/start", {
      method:"POST",
      body:JSON.stringify({planId:plan.id, confirmation:plan.confirmation, licenseReviewed:true}),
    });
    $("acquisitionConsent").checked = false;
    renderAcquisitionStatus({acquisition:{
      phase:"queued", progress:Number(plan.destination.existingBytes || 0) / Math.max(1, Number(plan.selection?.sizeBytes || 1)),
      downloadedBytes:Number(plan.destination.existingBytes || 0),
      message:"Acquisition approved. Preparing the pinned destination…", plan:data.plan, result:null,
    }});
  } catch (error) {
    $("acquisitionStatus").textContent = error.message;
    showNotice(error.message, true);
  }
}

async function stopAcquisition() {
  try {
    await api("/api/acquisition/stop", {method:"POST", body:"{}"});
    await pollAcquisitionStatus();
  } catch (error) { $("acquisitionStatus").textContent = error.message; }
}

async function openAcquiredModelLibrary() {
  const modelName = state.acquisitionStatus?.result?.modelName || "";
  $("acquisitionDialog").close();
  await loadModels(false);
  await openModelLibrary();
  if (modelName) {
    state.modelLibraryQuery = modelName;
    $("modelLibrarySearch").value = modelName;
    renderModelLibrary();
  }
}

function runtimeUpdateIsActive(phase = state.runtimeUpdatePhase) {
  return ["queued", "downloading", "verifying", "installing", "smoke-testing", "promoting", "stopping"].includes(phase);
}

function runtimeUpdateTrackMarkup(release) {
  const stateLabel = release.selected ? "Selected" : release.verified ? "Verified" : release.installed ? "Installed" : "Available";
  const actionLabel = release.action === "verify" ? "Review verification" : release.action === "install" ? "Review install" : "Unavailable";
  return `<article class="runtime-update-track ${release.selected ? "selected" : ""} ${release.preview ? "preview" : "stable"}">
    <header><span><strong>${esc(release.label)} · oMLX ${esc(release.version)}</strong><small>${release.preview ? "Release candidate" : "Production track"} · audited ${new Date(release.releasedAt).toLocaleDateString()}</small></span><em>${esc(stateLabel)}</em></header>
    <p>${esc(release.summary)}</p>
    <div><a href="${esc(release.releaseUrl)}" target="_blank" rel="noopener">Official release notes ↗</a><button type="button" class="secondary" data-runtime-update-channel="${esc(release.channel)}" ${!release.canPlan ? "disabled" : ""}>${esc(actionLabel)}</button></div>
  </article>`;
}

function renderRuntimeUpdateCatalog(catalog) {
  state.runtimeUpdateCatalog = catalog || state.runtimeUpdateCatalog;
  const current = state.runtimeUpdateCatalog;
  if (!current) return;
  $("runtimeUpdateCatalogBadge").textContent = `Audited ${current.catalogAuditedAt || "locally"}`;
  $("runtimeUpdateTracks").innerHTML = (current.releases || []).map(runtimeUpdateTrackMarkup).join("");
}

function runtimeUpdatePlanCheckMarkup(check) {
  const icon = check.state === "pass" ? "✓" : check.state === "advisory" ? "!" : "×";
  return `<div class="runtime-update-check ${esc(check.state)}"><i aria-hidden="true">${icon}</i><span><strong>${esc(check.label)}</strong><small>${esc(check.detail)}</small></span></div>`;
}

function runtimeUpdateResultMarkup(plan) {
  const result = state.runtimeUpdateStatus?.result;
  if (!result || result.version !== plan?.release?.version) return "";
  const kernel = result.smoke?.nativeKernel;
  return `<div class="runtime-update-result"><i aria-hidden="true">✓</i><span><strong>oMLX ${esc(result.version)} ${esc(result.action)}</strong><small>${esc(result.nextAction || "Verification completed.")}</small><em>${kernel?.ready ? "Native Qwen kernel passed" : "Core runtime passed; native kernel remains advisory"} · selection ${result.selectionChanged ? "changed" : "unchanged"}</em></span></div>`;
}

function renderRuntimeUpdatePlan(plan, resetConsent = false) {
  state.runtimeUpdatePlan = plan || null;
  syncRuntimeAdvancedDetailMode();
  if (resetConsent) $("runtimeUpdateConsent").checked = false;
  if (!plan) {
    $("runtimeUpdatePlan").innerHTML = '<div class="runtime-update-empty"><strong>Choose Review exact plan.</strong><span>No network request or filesystem change happens until a reviewed plan is approved separately.</span></div>';
    updateRuntimeUpdateControls();
    return;
  }
  const release = plan.release || {};
  const action = plan.action === "verify" ? "Verify installed copy" : plan.action === "install" ? "Install side by side" : "Blocked";
  const network = plan.review?.networkOnStart ? "Approved public dependency staging" : "No network request";
  const networkDetail = plan.review?.networkDetail || network;
  const steps = (plan.steps || []).map((step, index) => `<li><i>${index + 1}</i><span>${esc(step)}</span></li>`).join("");
  $("runtimeUpdatePlan").innerHTML = `<div class="runtime-update-plan-head"><div><span>${esc(release.label || "Release")} track</span><h4>oMLX ${esc(release.version)} · ${esc(action)}</h4><p>${esc(release.summary || "")}</p></div><em class="${release.preview ? "preview" : "stable"}">${release.preview ? "Preview" : "Stable"}</em></div>
    <div class="runtime-update-facts">
      <span><small>Immutable source</small><strong>${esc(release.tag)} · ${esc(String(release.commit || "").slice(0, 12))}</strong><code title="${esc(release.commit)}">${esc(release.commit)}</code></span>
      <span><small>Official wheel</small><strong>${esc(release.fileName)}</strong><code title="${esc(release.sha256)}">SHA-256 ${esc(release.sha256)}</code></span>
      <span><small>Versioned destination</small><strong>${plan.destination?.exists ? "Existing exact copy" : "New isolated copy"}</strong><code title="${esc(plan.destination?.path)}">${esc(plan.destination?.path)}</code></span>
      <span><small>Runtime impact</small><strong>${esc(network)}</strong><code title="${esc(networkDetail)}">${esc(networkDetail)}</code></span>
    </div>
    <div class="runtime-update-checks">${(plan.checks || []).map(runtimeUpdatePlanCheckMarkup).join("")}</div>
    <details class="runtime-update-contract" open><summary>Exact execution contract <span>${plan.steps?.length || 0} steps</span></summary><ol>${steps}</ol><p><strong>Dependency boundary.</strong> ${esc(plan.installer?.dependencyPolicy || "")}</p><p><strong>Rollback.</strong> ${esc(plan.rollback?.detail || "")}</p></details>
    ${runtimeUpdateResultMarkup(plan)}`;
  $("runtimeUpdateConsentCopy").textContent = plan.canStart
    ? `${action} oMLX ${release.version}. The selected runtime will not change automatically.`
    : "One or more safety checks blocked this exact plan.";
  updateRuntimeUpdateControls();
}

function updateRuntimeUpdateControls() {
  const plan = state.runtimeUpdatePlan;
  const active = runtimeUpdateIsActive();
  const canStart = Boolean(plan?.canStart && $("runtimeUpdateConsent").checked && !active && !state.runtimeUpdateLoading);
  $("runtimeUpdateConsent").disabled = !plan?.canStart || active || state.runtimeUpdateLoading;
  $("runtimeUpdateConsentPanel").classList.toggle("inactive", !plan?.canStart || active);
  $("runtimeUpdateStartButton").disabled = !canStart;
  $("runtimeUpdateStopButton").disabled = !active;
  $("runtimeUpdateStartTitle").textContent = plan?.action === "verify" ? "Verify installed copy" : "Install verified copy";
  $("runtimeUpdateStartLabel").textContent = !plan
    ? "Waiting for a reviewed plan"
    : active ? "Runtime operation in progress"
    : plan.action === "verify" ? `Local checks only · oMLX ${plan.release.version}`
    : `Side by side · oMLX ${plan.release.version}`;
  $("runtimeUpdateTracks").querySelectorAll("button").forEach(button => { button.disabled = active || state.runtimeUpdateLoading; });
}

function renderRuntimeUpdateStatus(data) {
  if (data?.catalog) renderRuntimeUpdateCatalog(data.catalog);
  const update = data?.runtimeUpdate || data;
  if (!update) return;
  state.runtimeUpdateStatus = update;
  state.runtimeUpdatePhase = update.phase || "idle";
  syncRuntimeAdvancedDetailMode();
  if (update.plan && (!state.runtimeUpdatePlan || runtimeUpdateIsActive(update.phase))) {
    renderRuntimeUpdatePlan(update.plan);
  }
  const progress = Math.max(0, Math.min(1, Number(update.progress || 0)));
  const labels = {
    idle:"Ready to review", queued:"Approved", downloading:"Downloading",
    verifying:"Verifying checksum", installing:"Installing in isolation",
    "smoke-testing":"Running smoke tests", promoting:"Promoting verified copy",
    stopping:"Stopping safely", completed:"Completed", failed:"Failed", cancelled:"Stopped",
  };
  $("runtimeUpdatePhase").textContent = labels[update.phase] || update.phase || "Ready";
  $("runtimeUpdatePercent").textContent = `${Math.round(progress * 100)}%`;
  $("runtimeUpdateProgressBar").style.width = `${Math.round(progress * 100)}%`;
  $("runtimeUpdateProgressBar").closest("[role=progressbar]")?.setAttribute("aria-valuenow", String(Math.round(progress * 100)));
  $("runtimeUpdateStatus").textContent = update.message || "No runtime update is running.";
  if (state.runtimeUpdatePlan) renderRuntimeUpdatePlan(state.runtimeUpdatePlan);
  updateRuntimeUpdateControls();
  if (update.phase === "completed" && update.result) {
    const completionId = `${update.result.version}:${update.result.action}:${update.result.path}`;
    if (completionId !== state.runtimeUpdateCompletionId) {
      state.runtimeUpdateCompletionId = completionId;
      void refreshAfterRuntimeUpdate();
    }
  }
}

async function pollRuntimeUpdateStatus() {
  try {
    const data = await api("/api/runtime/update/status");
    renderRuntimeUpdateStatus(data);
  } catch (error) {
    if ($("runtimeDialog").open) $("runtimeUpdateStatus").textContent = error.message;
  }
}

async function inspectRuntimeUpdate(channel) {
  if (state.runtimeUpdateLoading || runtimeUpdateIsActive()) return;
  state.runtimeUpdateLoading = true;
  $("runtimeUpdateConsent").checked = false;
  $("runtimeUpdateStatus").textContent = "Revalidating the exact local destination and audited release contract…";
  updateRuntimeUpdateControls();
  try {
    const data = await api("/api/runtime/update/plan", {method:"POST", body:JSON.stringify({channel})});
    renderRuntimeUpdatePlan(data.plan, true);
    $("runtimeUpdateStatus").textContent = data.plan.canStart
      ? "Exact plan ready. Review every check and approve it separately."
      : "The plan is blocked; review the failed safety check.";
  } catch (error) {
    $("runtimeUpdateStatus").textContent = error.message;
  } finally {
    state.runtimeUpdateLoading = false;
    updateRuntimeUpdateControls();
  }
}

async function startRuntimeUpdate() {
  const plan = state.runtimeUpdatePlan;
  if (!plan || !plan.canStart || !$("runtimeUpdateConsent").checked || runtimeUpdateIsActive()) return;
  state.runtimeUpdateLoading = true;
  updateRuntimeUpdateControls();
  try {
    const data = await api("/api/runtime/update/start", {
      method:"POST",
      body:JSON.stringify({planId:plan.id, confirmation:plan.confirmation, reviewed:true}),
    });
    $("runtimeUpdateConsent").checked = false;
    renderRuntimeUpdateStatus({runtimeUpdate:{
      phase:"queued", progress:0.02, downloadedBytes:0,
      message:"Runtime plan approved. Revalidating its exact destination…",
      plan:data.plan, result:null, events:[],
    }});
  } catch (error) {
    $("runtimeUpdateStatus").textContent = error.message;
  } finally {
    state.runtimeUpdateLoading = false;
    updateRuntimeUpdateControls();
  }
}

async function stopRuntimeUpdate() {
  try {
    await api("/api/runtime/update/stop", {method:"POST", body:"{}"});
    await pollRuntimeUpdateStatus();
  } catch (error) { $("runtimeUpdateStatus").textContent = error.message; }
}

async function refreshAfterRuntimeUpdate() {
  try {
    const [runtimeData, boot] = await Promise.all([api("/api/runtime/status"), api("/api/bootstrap")]);
    renderRuntimeManager(runtimeData.runtimeManager);
    applyBootstrapData(boot);
    await loadModels(false);
  } catch (error) {
    $("runtimeManagerStatus").textContent = `The update completed, but the local inventory refresh failed: ${error.message}`;
  }
}

function runtimePromotionIsActive(phase = state.runtimePromotionPhase) {
  return ["queued", "cooldown", "starting", "running", "stopping"].includes(phase);
}

function runtimePromotionRequest(candidateId) {
  const request = gather("custom", false);
  request.backend = "omlx";
  request.candidateId = candidateId;
  request.suite = $("runtimePromotionSuite").value;
  request.options = {
    ...request.options,
    acceleration:"off", kv:"off", anePrefill:"off", burst:"balanced",
  };
  return request;
}

function runtimePromotionResultMarkup() {
  const result = state.runtimePromotionStatus?.result;
  if (!result) return "";
  const candidate = result.measurements?.candidate || {};
  const memory = result.memoryRegressionBytes;
  const memoryLabel = Number.isFinite(Number(memory))
    ? `${Number(memory) > 0 ? "+" : Number(memory) < 0 ? "−" : ""}${formatBytes(Math.abs(Number(memory)))} pressure`
    : "Unavailable";
  const action = result.selectionChanged
    ? '<em>Promoted · previous copy remains installed</em>'
    : result.canPromote
      ? `<button type="button" class="text-button" data-runtime-promote="${esc(result.id)}">Promote measured candidate</button>`
      : '<em>Promotion withheld</em>';
  return `<section class="runtime-promotion-result ${result.canPromote ? "trusted" : ""}">
    <header><strong>${result.canPromote ? "Candidate cleared every gate" : "Selected runtime kept"}</strong>${action}</header>
    <p>${esc(result.recommendation || "Comparison completed.")}</p>
    <div class="runtime-promotion-metrics">
      <span><small>Median speed</small><strong>${Number(result.medianSpeedup || 0) >= 1 ? "+" : ""}${((Number(result.medianSpeedup || 1) - 1) * 100).toFixed(1)}%</strong></span>
      <span><small>Worst case</small><strong>${Number(result.worstCaseSpeedup || 0) >= 1 ? "+" : ""}${((Number(result.worstCaseSpeedup || 1) - 1) * 100).toFixed(1)}%</strong></span>
      <span><small>Memory guard</small><strong>${esc(memoryLabel)}</strong></span>
      <span><small>Candidate thermal</small><strong>${esc(candidate.thermalWorst || "Unavailable")}</strong></span>
    </div>
    <div class="runtime-update-checks">${(result.checks || []).map(runtimeUpdatePlanCheckMarkup).join("")}</div>
  </section>`;
}

function renderRuntimePromotionPlan(plan) {
  state.runtimePromotionPlan = plan || null;
  syncRuntimeAdvancedDetailMode();
  if (!plan) {
    $("runtimePromotionPlan").innerHTML = '<div class="runtime-promotion-empty"><strong>Install or verify a second oMLX copy, then choose Measure update.</strong><span>Planning hashes both executables and checks the model contract without loading weights.</span></div>' + runtimePromotionResultMarkup();
    updateRuntimePromotionControls();
    return;
  }
  const selected = plan.selected || {};
  const candidate = plan.candidate || {};
  const workload = plan.workload || {};
  const steps = (plan.steps || []).map((step, index) => `<li><i>${index + 1}</i><span>${esc(step)}</span></li>`).join("");
  const order = (plan.executionOrder || []).map(role => role === "selected" ? `Selected ${selected.version}` : `Candidate ${candidate.version}`).join(" → ");
  $("runtimePromotionPlan").innerHTML = `<div class="runtime-update-plan-head"><div><span>Exact same-model A/B</span><h4>${esc(selected.version)} versus ${esc(candidate.version)}</h4><p>${esc(plan.model?.name || "Model")} · ${esc(workload.label || "Workload")}</p></div><em>Selection unchanged</em></div>
    <div class="runtime-promotion-route">
      <div class="runtime-promotion-copy"><span>Selected reference</span><strong>${esc(selected.label)} · ${esc(selected.version)}</strong><code title="${esc(selected.path)}">${esc(selected.path)}</code><small>Revision ${esc(selected.revision?.id || "")}</small></div>
      <div class="runtime-promotion-arrow" aria-hidden="true">⇄</div>
      <div class="runtime-promotion-copy candidate"><span>Verified candidate</span><strong>${esc(candidate.label)} · ${esc(candidate.version)}</strong><code title="${esc(candidate.path)}">${esc(candidate.path)}</code><small>Revision ${esc(candidate.revision?.id || "")}</small></div>
    </div>
    <div class="runtime-promotion-summary">
      <span><small>Model</small><strong>${esc(plan.model?.name || "")}</strong></span>
      <span><small>Workload</small><strong>${esc(workload.label || "")}</strong></span>
      <span><small>Controlled mode</small><strong>AR · full-precision KV</strong></span>
      <span><small>Execution order</small><strong title="${esc(order)}">${esc(order)}</strong></span>
    </div>
    <div class="runtime-update-checks">${(plan.checks || []).map(runtimeUpdatePlanCheckMarkup).join("")}</div>
    <details class="runtime-update-contract"><summary>Promotion contract <span>${plan.steps?.length || 0} steps</span></summary><ol>${steps}</ol><p><strong>Threshold.</strong> Candidate must match deterministic output, beat the selected copy by at least 3% at both median and worst case, begin under comparable Mac conditions, add no more than 512 MB pressure, and reach no worse thermal state.</p><p><strong>Rollback.</strong> ${esc(plan.rollback?.detail || "")}</p></details>
    ${runtimePromotionResultMarkup()}`;
  $("runtimePromotionConsentCopy").textContent = `Measure ${selected.version} and ${candidate.version} with ${workload.generatedRequests || 0} generated requests. Nothing is selected automatically.`;
  updateRuntimePromotionControls();
}

function updateRuntimePromotionControls() {
  const plan = state.runtimePromotionPlan;
  const active = runtimePromotionIsActive();
  const canStart = Boolean(plan?.canStart && !active && !state.runtimePromotionLoading);
  $("runtimePromotionConsent").disabled = true;
  $("runtimePromotionConsent").checked = false;
  $("runtimePromotionConsentPanel").classList.add("hidden");
  $("runtimePromotionStartButton").disabled = !canStart;
  $("runtimePromotionStopButton").disabled = !active;
  $("runtimePromotionSuite").disabled = active || state.runtimePromotionLoading;
  $("runtimePromotionStartLabel").textContent = !plan
    ? "Waiting for an exact plan"
    : active ? "Runtime comparison in progress"
    : `${plan.workload?.label || "Generated workload"} · two fresh loads`;
  $("runtimeCards").querySelectorAll("[data-runtime-compare]").forEach(button => {
    button.disabled = active || state.runtimePromotionLoading;
  });
}

function renderRuntimePromotionStatus(data) {
  const status = data?.runtimePromotion || data;
  if (!status) return;
  if (!status.result && data?.latestResult) status.result = data.latestResult;
  state.runtimePromotionStatus = status;
  state.runtimePromotionPhase = status.phase || "idle";
  syncRuntimeAdvancedDetailMode();
  if (status.plan && (!state.runtimePromotionPlan || runtimePromotionIsActive(status.phase))) {
    renderRuntimePromotionPlan(status.plan);
  }
  const progress = Math.max(0, Math.min(1, Number(status.progress || 0)));
  const labels = {
    idle:"Ready to plan", queued:"Approved", cooldown:"Stabilising Mac",
    starting:"Loading runtime", running:"Measuring", stopping:"Stopping safely",
    completed:"Comparison complete", failed:"Needs attention", cancelled:"Stopped",
  };
  const planReady = status.phase === "idle" && Boolean(state.runtimePromotionPlan);
  $("runtimePromotionPhase").textContent = planReady ? "Plan ready" : labels[status.phase] || status.phase || "Ready";
  $("runtimePromotionPercent").textContent = `${Math.round(progress * 100)}%`;
  $("runtimePromotionProgressBar").style.width = `${Math.round(progress * 100)}%`;
  $("runtimePromotionProgressBar").closest("[role=progressbar]")?.setAttribute("aria-valuenow", String(Math.round(progress * 100)));
  $("runtimePromotionStatus").textContent = planReady
    ? "Exact comparison plan ready. Review both copies and every promotion guard."
    : status.message || "No runtime comparison is running.";
  if (state.runtimePromotionPlan) renderRuntimePromotionPlan(state.runtimePromotionPlan);
  else if (status.result) renderRuntimePromotionPlan(null);
  updateRuntimePromotionControls();
}

async function pollRuntimePromotionStatus() {
  try {
    renderRuntimePromotionStatus(await api("/api/runtime/promotion/status"));
  } catch (error) {
    if ($("runtimeDialog").open) $("runtimePromotionStatus").textContent = error.message;
  }
}

async function inspectRuntimePromotion(candidateId) {
  if (state.runtimePromotionLoading || runtimePromotionIsActive()) return;
  state.runtimePromotionLoading = true;
  $("runtimePromotionStatus").textContent = "Hashing both installed executable revisions and validating the visible model contract…";
  updateRuntimePromotionControls();
  try {
    const data = await api("/api/runtime/promotion/plan", {
      method:"POST", body:JSON.stringify(runtimePromotionRequest(candidateId)),
    });
    renderRuntimePromotionPlan(data.plan);
    $("runtimePromotionPhase").textContent = "Plan ready";
    $("runtimePromotionStatus").textContent = "Exact comparison plan ready. Review both copies and every promotion guard.";
  } catch (error) {
    $("runtimePromotionStatus").textContent = error.message;
  } finally {
    state.runtimePromotionLoading = false;
    updateRuntimePromotionControls();
  }
}

async function startRuntimePromotion() {
  const plan = state.runtimePromotionPlan;
  if (!plan?.canStart || runtimePromotionIsActive()) return;
  state.runtimePromotionLoading = true;
  updateRuntimePromotionControls();
  try {
    const data = await api("/api/runtime/promotion/start", {
      method:"POST",
      body:JSON.stringify({planId:plan.id, confirmation:plan.confirmation, reviewed:true}),
    });
    renderRuntimePromotionStatus({runtimePromotion:{
      phase:"queued", progress:0, message:"Runtime comparison started. Revalidating both exact copies…",
      plan:data.plan, result:null, modes:{}, runtimes:{}, events:[],
    }});
  } catch (error) {
    $("runtimePromotionStatus").textContent = error.message;
  } finally {
    state.runtimePromotionLoading = false;
    updateRuntimePromotionControls();
  }
}

async function stopRuntimePromotion() {
  try {
    await api("/api/runtime/promotion/stop", {method:"POST", body:"{}"});
    await pollRuntimePromotionStatus();
  } catch (error) { $("runtimePromotionStatus").textContent = error.message; }
}

async function applyRuntimePromotion() {
  const result = state.runtimePromotionStatus?.result;
  if (!result?.canPromote || result.selectionChanged || state.runtimePromotionApplying) return;
  state.runtimePromotionApplying = true;
  $("runtimePromotionStatus").textContent = "Revalidating the measured evidence and both executable revisions before promotion…";
  try {
    const data = await api("/api/runtime/promotion/apply", {
      method:"POST",
      body:JSON.stringify({resultId:result.id, confirmation:result.confirmation}),
    });
    renderRuntimeManager(data.runtimeManager);
    state.runtimePromotionStatus.result = data.result;
    renderRuntimePromotionPlan(state.runtimePromotionPlan);
    applyBootstrapData(await api("/api/bootstrap"));
    await loadModels(false);
    $("runtimePromotionStatus").textContent = `oMLX ${data.result.candidate?.version || "candidate"} is selected for new sessions. The previous copy remains installed for rollback.`;
  } catch (error) {
    $("runtimePromotionStatus").textContent = error.message;
  } finally {
    state.runtimePromotionApplying = false;
    updateRuntimePromotionControls();
  }
}

function runtimeCheckMarkup(check) {
  const stateClass = check.ready ? "pass" : (check.advisory ? "advisory" : "blocked");
  return `<div class="runtime-check ${stateClass}"><i aria-hidden="true">${check.ready ? "✓" : check.advisory ? "!" : "×"}</i><span><strong>${esc(check.label)}</strong><small>${esc(check.detail)}</small></span></div>`;
}

function runtimeCandidateMarkup(runtime, candidate) {
  const badges = [
    candidate.selected ? '<em class="selected">Selected</em>' : "",
    candidate.recommended && !candidate.selected ? '<em class="recommended">Recommended installed copy</em>' : "",
    candidate.managedVerification?.verified ? '<em class="verified">Official checksum verified</em>' : "",
  ].join("");
  const measure = runtime.id === "omlx" && !candidate.selected && candidate.managedVerification?.verified
    ? `<button type="button" class="text-button" data-runtime-compare="${esc(candidate.id)}">Measure update</button>`
    : "";
  return `<div class="runtime-candidate ${candidate.selected ? "selected" : ""}">
    <div><strong>${esc(candidate.channelLabel)}</strong><span>${esc(candidate.version)}</span><code title="${esc(candidate.resolvedPath || candidate.path)}">${esc(candidate.path)}</code></div>
    <div class="runtime-candidate-action">${badges}${measure}<button type="button" class="text-button" data-runtime-select="${esc(runtime.id)}" data-candidate-id="${esc(candidate.id)}" ${candidate.selected ? "disabled" : ""}>${candidate.selected ? "In use" : "Use for new sessions"}</button></div>
  </div>`;
}

function runtimeReleaseMarkup(release) {
  if (!release) return "";
  const highlights = (release.highlights || []).slice(0, 3).map(item =>
    `<span><strong>${esc(item.value)}</strong><small>${esc(item.label)}</small></span>`).join("");
  const workflow = release.needsReview && release.workflow?.length
    ? `<details class="runtime-release-workflow"><summary>Safe evaluation order <span>${release.workflow.length} steps</span></summary><ol>${release.workflow.map((step, index) => `<li><i>${index + 1}</i><span>${esc(step)}</span></li>`).join("")}</ol></details>`
    : "";
  const released = release.releasedAt
    ? new Date(release.releasedAt).toLocaleDateString([], {dateStyle:"medium"})
    : "Date unavailable";
  const advisory = release.activeAdvisory
    ? `<div class="runtime-release-advisory"><i aria-hidden="true">!</i><span><strong>${esc(release.activeAdvisory.headline || "Runtime re-test required")}</strong><small>${esc(release.activeAdvisory.detail || "Repeat affected measurements after updating.")}</small></span></div>`
    : "";
  return `<section class="runtime-release ${esc(release.state || "unknown-local-version")}">
    <header><span><small>Audited upstream</small><strong>${esc(release.displayVersion || release.version || "Unknown")}</strong></span><em>${esc(release.label || "Review")}</em></header>
    <p>${esc(release.summary || release.detail || "")}</p>
    ${advisory}
    ${highlights ? `<div class="runtime-release-highlights">${highlights}</div>` : ""}
    ${workflow}
    <footer>Released ${esc(released)} · catalog checked ${esc(release.auditedAt || "locally")}</footer>
  </section>`;
}

function runtimeCardMarkup(runtime) {
  const selected = runtime.selected;
  const update = runtime.update || {};
  const release = runtime.release || update.release;
  const links = [
    update.primaryUrl ? `<a href="${esc(update.primaryUrl)}" target="_blank" rel="noopener">${esc(update.primaryLabel || "Official update guidance")} ↗</a>` : "",
    update.docsUrl && update.docsUrl !== update.primaryUrl ? `<a href="${esc(update.docsUrl)}" target="_blank" rel="noopener">Installation docs ↗</a>` : "",
  ].filter(Boolean).join("");
  const advanced = update.developerCommand
    ? `<details class="runtime-advanced"><summary>Advanced Homebrew path</summary><p>${esc(update.detail || "")}</p><code>${esc(update.developerCommand)}</code><small>${update.developerCommandReady ? "Full Metal compiler detected." : "Blocked here: the full Xcode Metal compiler was not detected."}</small></details>`
    : `<p class="runtime-update-detail">${esc(update.detail || "")}</p>`;
  const selectedVersion = selected?.version || "Not installed";
  const auditedVersion = release?.displayVersion || release?.version || "Not audited";
  const detailOpen = activeDetail() === "detailed" ? " open" : "";
  return `<article class="runtime-card ${esc(runtime.level)}">
    <header><div><span class="runtime-icon ${esc(runtime.id)}" aria-hidden="true">${runtime.id === "lms" ? "LM" : runtime.id === "omlx" ? "O" : "M"}</span><span><strong>${esc(runtime.label)}</strong><small>${esc(runtime.headline)}</small></span></div><em>${runtime.level === "ready" ? "Ready" : runtime.level === "advisory" ? "Review" : "Missing"}</em></header>
    <div class="runtime-card-overview"><span><small>Selected</small><strong>${esc(selectedVersion)}</strong></span><span><small>Audited</small><strong>${esc(auditedVersion)}</strong></span></div>
    <details class="runtime-card-details"${detailOpen}><summary><span><strong>Checks, copies &amp; guidance</strong><small>${runtime.checks?.length || 0} checks · ${runtime.candidates?.length || 0} installed ${runtime.candidates?.length === 1 ? "copy" : "copies"}</small></span><em>${detailOpen ? "Hide" : "Details"}</em></summary><div class="runtime-card-details-body">
      <div class="runtime-selected"><span>Selected for new sessions</span><strong>${esc(selectedVersion)}</strong><code title="${esc(selected?.path || "")}">${esc(selected?.path || "No executable selected")}</code></div>
      ${runtimeReleaseMarkup(release)}
      <div class="runtime-checks">${(runtime.checks || []).map(runtimeCheckMarkup).join("")}</div>
      <details class="runtime-copies" ${runtime.candidates?.length > 1 ? "open" : ""}><summary>Installed copies <span>${runtime.candidates?.length || 0}</span></summary><div>${(runtime.candidates || []).map(candidate => runtimeCandidateMarkup(runtime, candidate)).join("") || '<p class="runtime-empty">No supported local executable was found.</p>'}</div></details>
      <div class="runtime-update"><strong>${esc(update.headline || "Review the official installation guidance.")}</strong>${advanced}<div class="runtime-links">${links}</div><small>${esc(update.rollback || "")}</small></div>
    </div></details>
  </article>`;
}

function renderRuntimeManager(inventory) {
  state.runtimeInventory = inventory;
  const runtimes = (inventory?.runtimes || []).filter(runtime => uiEngineVisible(runtime.id === "lms" ? "lmstudio" : runtime.id));
  const summary = inventory?.summary || {};
  const installed = runtimes.filter(runtime => runtime.selected).length;
  $("runtimeSummaryBadge").textContent = `${installed}/${runtimes.length || 3} installed`;
  $("runtimeSummaryBadge").className = `setup-badge ${summary.advisories ? "warning" : "ready"}`;
  $("runtimeManagerSummary").textContent = summary.message || "Local runtime inspection completed.";
  $("runtimeCards").innerHTML = runtimes.map(runtimeCardMarkup).join("");
  $("runtimeCards").querySelectorAll(".runtime-card-details").forEach(panel => {
    panel.addEventListener("toggle", () => renderRuntimeCardDisclosure(panel));
    renderRuntimeCardDisclosure(panel);
  });
  $("runtimeAgents").innerHTML = (inventory?.agents || []).map(agent => `<div class="runtime-agent ${agent.installed ? "" : "missing"}"><span><strong>${esc(agent.label)}</strong><small>${esc(agent.version)}</small></span><em>${agent.installed ? "Ready" : "Missing"}</em></div>`).join("");
  updateRuntimePromotionControls();
}

async function loadRuntimeManager() {
  if (state.runtimeLoading) return;
  state.runtimeLoading = true;
  $("runtimePromotionModel").textContent = selectedModel()?.name || "Choose a model in the launcher";
  $("refreshRuntimeManager").disabled = true;
  $("runtimeManagerStatus").textContent = "Running local checks without starting any runtime…";
  try {
    const [data, updateData, promotionData] = await Promise.all([
      api("/api/runtime/status"), api("/api/runtime/update/status"),
      api("/api/runtime/promotion/status"),
    ]);
    renderRuntimeManager(data.runtimeManager);
    renderRuntimeUpdateStatus(updateData);
    renderRuntimePromotionStatus(promotionData);
    const auditedAt = data.runtimeManager.releaseCatalog?.auditedAt || "the bundled audit date";
    $("runtimeManagerStatus").textContent = `Checked locally at ${new Date(data.runtimeManager.checkedAt).toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"})}. Official-release evidence was audited ${auditedAt} and read from the bundled catalog; no network check was performed.`;
  } catch (error) {
    $("runtimeManagerStatus").textContent = error.message;
  } finally {
    state.runtimeLoading = false;
    $("refreshRuntimeManager").disabled = false;
  }
}

async function openRuntimeManager() {
  if (!$("runtimeDialog").open) $("runtimeDialog").showModal();
  syncRuntimeAdvancedDetailMode();
  if (!state.runtimePromotionPlan && !runtimePromotionIsActive()) {
    $("runtimePromotionSuite").value = ["pi","opencode","codex"].includes(state.client) ? "agentic" : "standard";
  }
  await loadRuntimeManager();
  syncRuntimeAdvancedDetailMode();
}

async function selectRuntime(runtime, candidateId, button) {
  if (state.runtimeLoading) return;
  state.runtimeLoading = true;
  $("runtimeManagerStatus").textContent = "Verifying the exact installed executable before switching new sessions…";
  if (button) button.disabled = true;
  try {
    const data = await api("/api/runtime/select", {
      method:"POST",
      body:JSON.stringify({runtime, candidateId, confirmation:`select:${candidateId}`}),
    });
    renderRuntimeManager(data.runtimeManager);
    const boot = await api("/api/bootstrap");
    applyBootstrapData(boot);
    await loadModels(false);
    $("runtimeManagerStatus").textContent = `${({omlx:"oMLX", lms:"LM Studio", mtplx:"MTPLX"})[runtime] || runtime} selection updated for new sessions. No software was installed or removed.`;
  } catch (error) {
    $("runtimeManagerStatus").textContent = error.message;
    if (button) button.disabled = false;
  } finally {
    state.runtimeLoading = false;
  }
}

async function init() {
  applyUiFeatureVisibility();
  renderThemeMenu();
  renderQuickStart();
  syncChatStatusDetailMode();
  syncAgentConsoleStatusDetailMode();
  resetAgentConsoleTerminal();
  setRangeVisual($("depthInput"), $("depthValue"));
  setRangeVisual($("parallelInput"), $("parallelValue"));
  setRangeVisual($("mtpMinTokensInput"), $("mtpMinTokensValue"));
  setRangeVisual($("mtpMinContinueProbabilityInput"), $("mtpMinContinueProbabilityValue"));
  state.chatSidebarCollapsed = matchMedia("(max-width: 820px)").matches;
  renderChatSidebar();
  renderChatDraftStatus();
  try {
    const boot = await api("/api/bootstrap");
    applyBootstrapData(boot, true);
    await loadModels(false);
    initialiseVisibleRoute();
    await Promise.all([pollStatus(), pollRouteCheckStatus(), pollBenchmarkStatus(), pollSetupStatus(), pollAcquisitionStatus(), pollAneStatus(), pollAneCloneStatus(), pollRuntimePromotionStatus(), loadSessionSetStatus(false), loadQuickStart()]);
    await loadChatHistory(false);
    state.statusTimer = setInterval(() => {
      pollStatus(); pollRouteCheckStatus(); pollBenchmarkStatus(); pollSetupStatus(); pollAcquisitionStatus(); pollAneStatus(); pollAneCloneStatus(); pollRuntimePromotionStatus();
      if ($("runtimeDialog").open || runtimeUpdateIsActive()) pollRuntimeUpdateStatus();
      if ($("sessionSetDialog").open || sessionSetIsActive()) loadSessionSetStatus(true);
    }, 1800);
  } catch (error) { showNotice(`The local controller did not initialise: ${error.message}`, true); }
}

document.querySelectorAll("[data-backend]").forEach(button => button.addEventListener("click", () => {
  if (button.disabled || !uiEngineVisible(button.dataset.backend)) return;
  const backend = button.dataset.backend;
  if (state.backend !== backend) { state.backend = backend; updateBackend(); scheduleBenchmarkHistory(); }
  if (
    backend === "freetoken" && !state.freeToken?.connected
    && !state.freeToken?.native?.installed
  ) openFreeTokenDialog();
}));
document.querySelectorAll("[data-client]").forEach(button => button.addEventListener("click", () => {
  if (!button.disabled && state.client !== button.dataset.client) {
    cancelOptimization("Work surface changed; reapply the speed preset for this workload.");
    state.client = button.dataset.client;
    refreshLaunchability();
    persistVisibleRoute();
    scheduleBenchmarkHistory();
    schedulePerformanceReceipt();
  }
}));
$("modelSelect").addEventListener("change", () => { modelChanged(); scheduleBenchmarkHistory(); });
$("reasoningSelect").addEventListener("change", () => { cancelOptimization("Reasoning changed; reapply to refresh the evidence match."); refreshLaunchability(); scheduleBenchmarkHistory(); schedulePerformanceReceipt(); });
$("contextInput").addEventListener("input", () => { cancelOptimization("Context changed; reapply to refresh the context-specific recommendation."); refreshLaunchability(); scheduleBenchmarkHistory(); schedulePerformanceReceipt(); });
$("outputInput").addEventListener("input", () => { cancelOptimization("Response limit changed; reapply to refresh the workload recommendation."); refreshLaunchability(); scheduleBenchmarkHistory(); schedulePerformanceReceipt(); });
$("projectPath").addEventListener("input", refreshLaunchability);
$("agentHostSelect").addEventListener("change", () => {
  clearWarmRoutePlan();
  refreshLaunchability();
  scheduleWarmRoutePlan(true);
});
$("omlxKv").addEventListener("change", () => { cancelOptimization("KV precision changed; reapply to refresh the benchmark match."); refreshLaunchability(); scheduleBenchmarkHistory(); schedulePerformanceReceipt(); });
$("mtplxKv").addEventListener("change", () => { cancelOptimization("KV precision changed; reapply to refresh the benchmark match."); refreshLaunchability(); scheduleBenchmarkHistory(); schedulePerformanceReceipt(); });
$("refreshModels").addEventListener("click", () => loadModels(true));
$("openFreeTokenConnection").addEventListener("click", () => {
  if ($("openFreeTokenConnection").dataset.action === "models") void openFreeTokenModelReview();
  else openFreeTokenDialog();
});
$("openFreeTokenControls").addEventListener("click", openFreeTokenDialog);
$("freeTokenForm").addEventListener("submit", connectFreeToken);
$("freeTokenDisconnect").addEventListener("click", disconnectFreeToken);
$("freeTokenExperimentalConsent").addEventListener("change", event => {
  event.currentTarget.dataset.modelId = event.currentTarget.checked
    ? String(selectedModel()?.id || "") : "";
  updateFreeTokenNativeControls();
  refreshLaunchability();
});
$("hubToolsMenuButton").addEventListener("click", () => setHubToolsMenu(!state.hubToolsMenuOpen, !state.hubToolsMenuOpen));
$("hubToolsMenu").addEventListener("click", event => {
  if (event.target.closest('[role="menuitem"]')) closeHubToolsMenu();
});
$("hubToolsMenu").addEventListener("keydown", event => {
  const items = [...$("hubToolsMenu").querySelectorAll('[role="menuitem"]:not(:disabled)')];
  if (event.key === "Escape") {
    event.preventDefault(); closeHubToolsMenu(); $("hubToolsMenuButton").focus(); return;
  }
  if (!items.length || !["ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const current = items.indexOf(document.activeElement);
  const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 : event.key === "ArrowDown" ? (current + 1 + items.length) % items.length : (current - 1 + items.length) % items.length;
  items[next].focus();
});
$("themeMenuButton").addEventListener("click", () => setThemeMenu(!state.themeMenuOpen, !state.themeMenuOpen));
$("themeMenu").addEventListener("click", event => {
  const themeChoice = event.target.closest("[data-theme-choice]");
  const detailChoice = event.target.closest("[data-detail-choice]");
  if (themeChoice) selectTheme(themeChoice.dataset.themeChoice);
  else if (detailChoice) selectDetail(detailChoice.dataset.detailChoice);
});
$("themeMenu").addEventListener("keydown", event => {
  const items = [...$("themeMenu").querySelectorAll('[role="menuitemradio"]')];
  if (event.key === "Escape") {
    event.preventDefault(); closeThemeMenu(); $("themeMenuButton").focus(); return;
  }
  if (["Enter", " "].includes(event.key)) {
    const themeChoice = event.target.closest("[data-theme-choice]");
    const detailChoice = event.target.closest("[data-detail-choice]");
    if (themeChoice) { event.preventDefault(); selectTheme(themeChoice.dataset.themeChoice); }
    else if (detailChoice) { event.preventDefault(); selectDetail(detailChoice.dataset.detailChoice); }
    return;
  }
  if (!items.length || !["ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const current = items.indexOf(document.activeElement);
  const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 : event.key === "ArrowDown" ? (current + 1 + items.length) % items.length : (current - 1 + items.length) % items.length;
  items[next].focus();
});
$("interfaceDetailButton").addEventListener("click", toggleInterfaceDetail);
$("routeCheckButton").addEventListener("click", () => openRouteCheck("inspect"));
$("routeCheckStartButton").addEventListener("click", startRouteCheck);
$("routeCheckStopButton").addEventListener("click", stopRouteCheck);
$("routeCheckLaunchButton").addEventListener("click", launchCheckedRoute);
$("previewButton").addEventListener("click", preview);
$("applyOptimal").addEventListener("click", () => applyOptimal("current"));
$("performanceReceipt").addEventListener("click", activatePerformanceReceipt);
$("optimizerMenuButton").addEventListener("click", toggleOptimizerMenu);
$("optimizerVerifiedLaunch").addEventListener("click", () => prepareVerifiedQuickLaunch("fastest"));
document.querySelectorAll("[data-optimizer-scope]").forEach(button => button.addEventListener("click", () => applyOptimal(button.dataset.optimizerScope, button.dataset.enginePreference || "fastest")));
$("optimizerCalibrate").addEventListener("click", () => openCalibrationAssistant({source:"optimizer-menu", preference:"fastest"}));
document.addEventListener("click", event => {
  if (state.optimizerMenuOpen && !$("optimizerAction").contains(event.target)) closeOptimizerMenu();
  if (state.themeMenuOpen && !$("themeMenuButton").closest(".theme-control").contains(event.target)) closeThemeMenu();
  if (state.hubToolsMenuOpen && !$("hubToolsMenuButton").closest(".hub-tools-control").contains(event.target)) closeHubToolsMenu();
});
document.addEventListener("keydown", event => {
  if (!state.optimizerMenuOpen) return;
  if (event.key === "Escape") {
    event.preventDefault(); closeOptimizerMenu(); $("optimizerMenuButton").focus(); return;
  }
  if (!["ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) return;
  const items = [...$("optimizerMenu").querySelectorAll('[role="menuitem"]:not(:disabled)')];
  if (!items.length) return;
  event.preventDefault();
  const current = items.indexOf(document.activeElement);
  const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 : event.key === "ArrowDown" ? (current + 1 + items.length) % items.length : (current - 1 + items.length) % items.length;
  items[next].focus();
});
$("launchButton").addEventListener("click", () => launch());
$("agentConsoleBackButton").addEventListener("click", leaveAgentConsole);
$("agentConsoleSessionsButton").addEventListener("click", openSessionDashboard);
$("agentConsoleStopButton").addEventListener("click", () => stopAgentConsoleSurface());
$("agentConsoleRestartButton").addEventListener("click", () => restartAgentConsoleSurface());
$("agentConsoleTabs").addEventListener("click", event => {
  const tab = event.target.closest("[data-agent-console-tab]");
  if (tab) selectAgentConsole(tab.dataset.agentConsoleTab);
});
$("agentConsoleTabs").addEventListener("keydown", event => {
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
  requestAnimationFrame(() => document.getElementById(`agent-console-tab-${surfaceId}`)?.focus());
});
$("agentConsoleFindButton").addEventListener("click", () => setAgentConsoleSearch(!state.agentConsoleSearchOpen));
$("agentConsoleCopyButton").addEventListener("click", copyAgentConsoleVisible);
$("agentConsoleSearch").addEventListener("submit", event => {
  event.preventDefault();
  moveAgentConsoleSearch(event.shiftKey ? -1 : 1);
});
$("agentConsoleSearchInput").addEventListener("input", event => {
  state.agentConsoleSearchQuery = String(event.target.value || "").slice(0, AgentConsoleTabsCore.MAX_QUERY);
  state.agentConsoleSearchIndex = -1;
  renderAgentTerminalOutput({focusMatch:false});
});
$("agentConsoleSearchInput").addEventListener("keydown", event => {
  if (event.key === "Escape") {
    event.preventDefault();
    setAgentConsoleSearch(false);
  } else if (event.key === "Enter") {
    event.preventDefault();
    moveAgentConsoleSearch(event.shiftKey ? -1 : 1);
  }
});
$("agentConsoleSearchPrevious").addEventListener("click", () => moveAgentConsoleSearch(-1));
$("agentConsoleSearchNext").addEventListener("click", () => moveAgentConsoleSearch(1));
$("agentConsoleSearchClose").addEventListener("click", () => setAgentConsoleSearch(false));
$("agentConsoleJumpLatest").addEventListener("click", scrollAgentConsoleToLatest);
$("agentTerminalViewport").addEventListener("scroll", updateAgentConsoleScrollUi, {passive:true});
$("agentConsoleForm").addEventListener("submit", event => {
  event.preventDefault();
  const value = $("agentConsoleInput").value;
  if (!value || $("agentConsoleInput").disabled) return;
  queueAgentConsoleInput(`${value}\r`);
  $("agentConsoleInput").value = "";
  $("agentTerminalViewport").focus();
});
$("agentConsoleEscapeButton").addEventListener("click", () => queueAgentConsoleInput("\u001b"));
$("agentConsoleInterruptButton").addEventListener("click", () => queueAgentConsoleInput("\u0003"));
$("agentTerminalViewport").addEventListener("keydown", event => {
  if (event.isComposing) return;
  const value = agentConsoleKeyData(event);
  if (value === null) return;
  event.preventDefault();
  queueAgentConsoleInput(value);
});
$("agentTerminalViewport").addEventListener("paste", event => {
  const value = event.clipboardData?.getData("text");
  if (!value) return;
  event.preventDefault();
  queueAgentConsoleInput(value.replaceAll("\n", "\r"));
});
window.addEventListener("resize", scheduleAgentConsoleResize);
$("stopButton").addEventListener("click", stopRun);
$("logButton").addEventListener("click", showLog);
$("focusedStopButton").addEventListener("click", stopRun);
$("focusedLogButton").addEventListener("click", showLog);
$("openBenchmarkButton").addEventListener("click", openBenchmarkLab);
$("benchmarkSuiteSelect").addEventListener("change", benchmarkSuiteChanged);
$("benchmarkPreferenceSelect").addEventListener("change", benchmarkPreferenceChanged);
$("benchmarkStartButton").addEventListener("click", () => startBenchmark("current"));
$("benchmarkShootoutButton").addEventListener("click", () => startBenchmark("engines"));
$("benchmarkMtpTuneButton").addEventListener("click", () => startBenchmark("mtp-tune"));
$("benchmarkDflashTuneButton").addEventListener("click", () => startBenchmark("dflash-tune"));
$("benchmarkStopButton").addEventListener("click", stopBenchmark);
$("benchmarkHistoryRerun").addEventListener("click", () => startBenchmark("engines"));
$("benchmarkResults").addEventListener("click", event => {
  if (event.target.closest("[data-apply-shootout]")) applyOptimal("engine", $("benchmarkPreferenceSelect").value);
});
$("openCalibrationAssistant").addEventListener("click", () => openCalibrationAssistant());
$("calibrationDetailToggle").addEventListener("click", () => {
  state.calibrationDetailsOpen = !state.calibrationDetailsOpen;
  renderCalibration();
});
$("calibrationSuiteSelect").addEventListener("change", () => loadCalibrationPlan(true));
$("calibrationCoolingSelect").addEventListener("change", () => loadCalibrationPlan(true));
$("calibrationPreferenceSelect").addEventListener("change", () => {
  if (state.calibrationEntry) {
    state.calibrationEntry = {
      source:state.calibrationEntry.source,
      preference:$("calibrationPreferenceSelect").value,
      decision:null,
    };
  }
  loadCalibrationPlan(true);
});
$("calibrationProfileName").addEventListener("input", renderCalibrationPlan);
$("calibrationStartButton").addEventListener("click", startCalibration);
$("calibrationStopButton").addEventListener("click", stopCalibration);
$("calibrationApplyButton").addEventListener("click", () => applyCalibrationResult(false));
$("calibrationSaveButton").addEventListener("click", () => applyCalibrationResult(true));
$("openSessionDashboard").addEventListener("click", openSessionDashboard);
$("sessionRefreshButton").addEventListener("click", loadSessionDashboard);
$("sessionStopButton").addEventListener("click", stopSessionFromDashboard);
$("sessionAttachClient").addEventListener("change", () => scheduleSessionAttachmentPlan(true));
$("sessionAttachAgentHost").addEventListener("change", () => scheduleSessionAttachmentPlan(true));
$("sessionAttachSampling").addEventListener("change", () => scheduleSessionAttachmentPlan(true));
for (const id of [
  "sessionAttachProject", "sessionAttachSystemPrompt", "sessionAttachTemperature",
  "sessionAttachTopP", "sessionAttachTopK", "sessionAttachPresencePenalty",
  "sessionAttachFrequencyPenalty", "sessionAttachSeed",
]) $(id).addEventListener("input", () => scheduleSessionAttachmentPlan(false));
$("sessionAttachButton").addEventListener("click", attachSessionSurface);
$("sessionActivityList").addEventListener("click", event => {
  const cancel = event.target.closest("[data-session-cancel-request]");
  if (cancel && !cancel.disabled) void cancelSessionRequest(
    cancel.dataset.sessionCancelRequest,
    cancel.dataset.sessionRequestSurface || "",
  );
});
$("sessionIdleTimeout").addEventListener("change", setSessionIdlePolicy);
$("sessionAttachmentList").addEventListener("click", event => {
  const open = event.target.closest("[data-session-open-chat]");
  const detach = event.target.closest("[data-session-detach-chat]");
  const openConsole = event.target.closest("[data-session-open-console]");
  const stopConsole = event.target.closest("[data-session-stop-console]");
  const restartConsole = event.target.closest("[data-session-restart-console]");
  const attachments = state.sessionDashboard?.hub?.attachments || [];
  if (open) enterChatSurface(attachments.find(item => item.id === open.dataset.sessionOpenChat));
  else if (detach) detachChatSurface(attachments.find(item => item.id === detach.dataset.sessionDetachChat));
  else if (openConsole) enterAgentConsole(attachments.find(item => item.id === openConsole.dataset.sessionOpenConsole));
  else if (stopConsole) stopAgentConsoleSurface(attachments.find(item => item.id === stopConsole.dataset.sessionStopConsole));
  else if (restartConsole) restartAgentConsoleSurface(attachments.find(item => item.id === restartConsole.dataset.sessionRestartConsole));
});
$("sessionConsent").addEventListener("change", () => {
  const admission = state.sessionDashboard?.admission;
  state.sessionAcknowledgementId = $("sessionConsent").checked && admission?.requiresAcknowledgement
    ? admission.contractId || "" : "";
  renderSessionDashboard();
});
$("openSetupButton").addEventListener("click", openSetupAssistant);
$("setupConsent").addEventListener("change", updateSetupControls);
$("setupDownloadButton").addEventListener("click", startSetupDownload);
$("setupStopButton").addEventListener("click", stopSetup);
$("openAneButton").addEventListener("click", openAneTuner);
$("aneCpuAssist").addEventListener("change", updateAneControls);
$("aneStartButton").addEventListener("click", startAneTuning);
$("aneStopButton").addEventListener("click", stopAneTuning);
$("aneUseButton").addEventListener("click", useAneResult);
$("aneClonePlanButton").addEventListener("click", openAneClonePlan);
$("aneCloneConsent").addEventListener("change", updateAneCloneControls);
$("aneCloneStartButton").addEventListener("click", startAneClone);
$("aneCloneStopButton").addEventListener("click", stopAneClone);
$("aneCloneUseButton").addEventListener("click", useAneClone);
$("openModelLibrary").addEventListener("click", openModelLibrary);
$("refreshModelLibrary").addEventListener("click", loadModelLibrary);
$("clearModelLibraryFilters").addEventListener("click", clearModelLibraryFilters);
$("openAcquisitionCenter").addEventListener("click", openAcquisitionCenter);
$("acquisitionSearchForm").addEventListener("submit", event => { event.preventDefault(); searchAcquisitionModels(); });
$("acquisitionInspectButton").addEventListener("click", () => inspectAcquisitionModel());
$("acquisitionDestination").addEventListener("change", () => {
  renderAcquisitionRoots();
  if (state.acquisitionPlan && !acquisitionIsActive()) inspectAcquisitionModel($("acquisitionVariant").value);
});
$("acquisitionVariant").addEventListener("change", event => {
  $("acquisitionConsent").checked = false;
  inspectAcquisitionModel(event.currentTarget.value);
});
$("acquisitionConsent").addEventListener("change", updateAcquisitionControls);
$("acquisitionStartButton").addEventListener("click", startAcquisition);
$("acquisitionStopButton").addEventListener("click", stopAcquisition);
$("acquisitionOpenLibrary").addEventListener("click", openAcquiredModelLibrary);
$("acquisitionSearchResults").addEventListener("click", event => {
  const button = event.target.closest("[data-acquisition-repo]");
  if (!button || button.disabled) return;
  $("acquisitionRepoId").value = button.dataset.acquisitionRepo || "";
  $("acquisitionRevision").value = button.dataset.acquisitionRevision || "";
  inspectAcquisitionModel();
});
$("modelLibrarySearch").addEventListener("input", event => {
  state.modelLibraryQuery = event.currentTarget.value;
  renderModelLibrary();
});
$("modelLibraryEngineFilter").addEventListener("change", event => {
  state.modelLibraryEngine = uiEngineVisible(event.currentTarget.value)
    ? event.currentTarget.value : "all";
  event.currentTarget.value = state.modelLibraryEngine;
  renderModelLibrary();
});
$("modelLibrarySurfaceFilter").addEventListener("change", event => {
  state.modelLibrarySurface = event.currentTarget.value;
  renderModelLibrary();
});
$("modelLibraryStateFilter").addEventListener("change", event => {
  state.modelLibraryState = event.currentTarget.value;
  renderModelLibrary();
});
$("modelLibraryCards").addEventListener("click", event => {
  const button = event.target.closest("[data-library-model][data-library-backend]");
  if (button && !button.disabled) useModelLibraryRoute(button.dataset.libraryModel, button.dataset.libraryBackend);
});
$("openRuntimeManager").addEventListener("click", openRuntimeManager);
$("refreshRuntimeManager").addEventListener("click", loadRuntimeManager);
$("runtimeAdvancedTools").addEventListener("toggle", renderRuntimeAdvancedDisclosure);
$("runtimeUpdateConsent").addEventListener("change", updateRuntimeUpdateControls);
$("runtimeUpdateStartButton").addEventListener("click", startRuntimeUpdate);
$("runtimeUpdateStopButton").addEventListener("click", stopRuntimeUpdate);
$("runtimePromotionStartButton").addEventListener("click", startRuntimePromotion);
$("runtimePromotionStopButton").addEventListener("click", stopRuntimePromotion);
$("runtimePromotionSuite").addEventListener("change", () => {
  if (runtimePromotionIsActive()) return;
  renderRuntimePromotionPlan(null);
  $("runtimePromotionStatus").textContent = "Workload changed. Choose Measure update again to create an exact plan.";
});
$("runtimePromotionPlan").addEventListener("click", event => {
  if (event.target.closest("[data-runtime-promote]")) applyRuntimePromotion();
});
$("runtimeUpdateTracks").addEventListener("click", event => {
  const button = event.target.closest("[data-runtime-update-channel]");
  if (button && !button.disabled) inspectRuntimeUpdate(button.dataset.runtimeUpdateChannel);
});
$("runtimeCards").addEventListener("click", event => {
  const compare = event.target.closest("[data-runtime-compare]");
  const button = event.target.closest("[data-runtime-select]");
  if (compare && !compare.disabled) inspectRuntimePromotion(compare.dataset.runtimeCompare);
  else if (button) selectRuntime(button.dataset.runtimeSelect, button.dataset.candidateId, button);
});
$("openProfileManager").addEventListener("click", openProfileManager);
$("quickStartCustom").addEventListener("click", toggleQuickStartRoutes);
$("quickStartCards").addEventListener("click", event => {
  const profile = event.target.closest("[data-quick-profile-launch]");
  const sessionSet = event.target.closest("[data-quick-session-review]");
  const chat = event.target.closest("[data-quick-chat]");
  if (profile && !profile.disabled) applySavedProfile(profile.dataset.quickProfileLaunch, true);
  else if (sessionSet && !sessionSet.disabled) reviewQuickSessionSet(sessionSet.dataset.quickSessionReview);
  else if (chat && !chat.disabled) {
    if (state.runPhase === "running" && state.chatRunId) openChatHistoryThread(chat.dataset.quickChat);
    else openChatResumeDialog(chat.dataset.quickChat);
  }
});
$("profilePolicySelect").addEventListener("change", updateProfilePolicyControls);
$("profileName").addEventListener("input", updateProfilePolicyControls);
$("profileSaveForm").addEventListener("submit", event => { event.preventDefault(); saveCurrentProfile(); });
$("profileCancelEdit").addEventListener("click", () => {
  resetProfileEditor();
  setProfileStatus("Update cancelled. Saved profiles were not changed.");
});
$("profileCards").addEventListener("click", event => {
  const launchButton = event.target.closest("[data-profile-launch]");
  const applyButton = event.target.closest("[data-profile-apply]");
  const editButton = event.target.closest("[data-profile-edit]");
  const deleteButton = event.target.closest("[data-profile-delete]");
  if (launchButton) applySavedProfile(launchButton.dataset.profileLaunch, true);
  else if (applyButton) applySavedProfile(applyButton.dataset.profileApply, false);
  else if (editButton) editProfile(editButton.dataset.profileEdit);
  else if (deleteButton) deleteSavedProfile(deleteButton.dataset.profileDelete);
});
$("openSessionSets").addEventListener("click", openSessionSetManager);
$("sessionSetName").addEventListener("input", renderSessionSets);
$("sessionSetName").addEventListener("keydown", event => {
  if (event.key === "Enter" && !$("sessionSetSaveButton").disabled) {
    event.preventDefault();
    saveCurrentSessionSet();
  }
});
$("sessionSetSaveButton").addEventListener("click", saveCurrentSessionSet);
$("sessionSetCancelEdit").addEventListener("click", () => {
  resetSessionSetEditor();
  setSessionSetMessage("Replacement cancelled. Saved Session Sets were not changed.");
});
$("sessionSetConsent").addEventListener("change", renderSessionSetPlan);
$("sessionSetOpenButton").addEventListener("click", openPlannedSessionSet);
$("sessionSetStopButton").addEventListener("click", cancelSessionSetOpen);
$("sessionSetCards").addEventListener("click", event => {
  const review = event.target.closest("[data-session-set-review]");
  const apply = event.target.closest("[data-session-set-apply]");
  const edit = event.target.closest("[data-session-set-edit]");
  const remove = event.target.closest("[data-session-set-delete]");
  if (review) planSessionSet(review.dataset.sessionSetReview);
  else if (apply) applySessionSetPrimary(apply.dataset.sessionSetApply);
  else if (edit) editSessionSet(edit.dataset.sessionSetEdit);
  else if (remove) deleteSavedSessionSet(remove.dataset.sessionSetDelete);
});
$("samplingMode").addEventListener("change", () => { updateChatSamplingControls(); refreshLaunchability(); scheduleBenchmarkHistory(); schedulePerformanceReceipt(); });
$("systemPrompt").addEventListener("input", () => { refreshLaunchability(); scheduleBenchmarkHistory(); });
for (const id of [
  "temperatureInput", "topPInput", "topKInput", "presencePenaltyInput",
  "frequencyPenaltyInput", "seedInput",
]) {
  $(id).addEventListener("input", () => { refreshLaunchability(); scheduleBenchmarkHistory(); schedulePerformanceReceipt(); });
}
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
$("chatStopButton").addEventListener("click", () => state.chatAbort?.abort());
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
$("agentConsoleStatusPanel").addEventListener("toggle", renderAgentConsoleStatusDisclosure);
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
document.addEventListener("click", event => {
  if (!state.chatSidebarMenuId || event.target.closest("[data-chat-sidebar-thread]")) return;
  state.chatSidebarMenuId = "";
  state.chatHistoryDeleteConfirmId = "";
  renderChatSidebar();
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
$("chatResumeSystemPrompt").addEventListener("input", renderChatResumePlan);
$("chatResumeWithoutPrompt").addEventListener("change", () => {
  if ($("chatResumeWithoutPrompt").checked) $("chatResumeSystemPrompt").value = "";
  renderChatResumePlan();
});
$("chatResumeMemoryConsent").addEventListener("change", renderChatResumePlan);
$("chatResumeExperimentalConsent").addEventListener("change", renderChatResumePlan);
$("chatResumeApply").addEventListener("click", () => applyChatResume(false));
$("chatResumeStart").addEventListener("click", () => applyChatResume(true));
$("chatHistoryList").addEventListener("submit", event => {
  const form = event.target.closest("[data-chat-history-rename-form]");
  if (!form) return;
  event.preventDefault();
  updateChatHistoryThread(form.dataset.chatHistoryRenameForm, {title:form.querySelector("input").value});
});
$("newChatButton").addEventListener("click", newChat);
$("endChatButton").addEventListener("click", endCurrentChatSurface);
window.addEventListener("beforeunload", persistChatSessionState);

Object.values(optimizerControls).forEach(id => {
  const control = $(id);
  control.addEventListener("input", () => {
    if (control.type === "range") setRangeVisual(control);
    if (id === "accelerationSelect" || id === "depthInput") updateAccelerationState();
    if (id.startsWith("freeToken")) {
      updateFreeTokenNativeControls();
      refreshLaunchability();
    }
    markOptimizerCustom();
  });
  control.addEventListener("change", () => {
    if (id === "accelerationSelect" || id === "depthInput") updateAccelerationState();
    if (id.startsWith("freeToken")) updateFreeTokenNativeControls();
    markOptimizerCustom();
    refreshLaunchability();
  });
});

init();
