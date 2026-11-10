const state = {
  token: "",
  binaries: {},
  adapters: {engines:[], workSurfaces:[]},
  clientSupport: {},
  statusTimer: null,
  themeMenuOpen: false,
  hubToolsMenuOpen: false,
  routeCheckPhase: "idle",
  routeCheckStatus: null,
  routeCheckPlan: null,
  routeCheckLoading: false,
  routeCheckGeneration: 0,
  routeCheckCompletionId: "",
  routeCheckIntent: "inspect",
  routeCheckInputSignature: "",
  verifiedLaunchBusy: false,
  setupPhase: "idle",
  setupStatus: null,
  setupPlan: null,
  setupRenderedPlanId: "",
  setupCompletionId: "",
  anePhase: "idle",
  aneStatus: null,
  aneCompletionId: "",
  aneClonePhase: "idle",
  aneCloneStatus: null,
  aneClonePlan: null,
  aneCloneRenderedPlanId: "",
  aneCloneCompletionPath: "",
  aneCloneLoading: false,

};

const $ = (id) => document.getElementById(id);
// Keep the completed integration available for later without advertising an
// unfinished route in the everyday launcher. Re-enabling is one deliberate flag.
const UI_FEATURES = Object.freeze({freetoken:false});
function uiFeatureEnabled(feature) { return UI_FEATURES[feature] === true; }
function uiEngineVisible(backend) {
  const id = String(backend || "");
  if (id === "freetoken") return uiFeatureEnabled("freetoken");
  if (id === "llamacpp") {
    return (state.adapters?.engines || []).some(adapter => adapter.id === "llamacpp");
  }
  return true;
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
  const llamaCppVisible = uiEngineVisible("llamacpp");
  document.querySelectorAll('[data-backend="llamacpp"]').forEach(element => {
    element.hidden = !llamaCppVisible;
    if (!llamaCppVisible && "disabled" in element) element.disabled = true;
  });
  if (!uiEngineVisible(launchWorkspace.view().backend)) launchWorkspace.setBackend("mtplx");
  if (!uiFeatureEnabled("freetoken") && $("modelLibraryEngineFilter")?.value === "freetoken") {
    $("modelLibraryEngineFilter").value = "all";
    modelAssets.setEngineFilter("all");
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
const ChatResumeCore = globalThis.LLMChatResume;
if (!ChatResumeCore) throw new Error("Saved Chat route review support did not load.");
const ChatStatusCore = globalThis.LLMChatStatusCore;
if (!ChatStatusCore) throw new Error("Compact Chat status support did not load.");
const SafeMarkdownCore = globalThis.LLMSafeMarkdownCore;
if (!SafeMarkdownCore) throw new Error("Safe Chat Markdown support did not load.");
const TerminalCore = globalThis.LLMTerminalCore;
if (!TerminalCore) throw new Error("Hub Console terminal support did not load.");
const AgentConsoleTabsCore = globalThis.LLMAgentConsoleTabs;
if (!AgentConsoleTabsCore) throw new Error("Hub Console tab support did not load.");
const AgentConsoleInputCore = globalThis.LLMAgentConsoleInputCore;
if (!AgentConsoleInputCore) throw new Error("Reliable Hub Console input support did not load.");
const UiPresenter = globalThis.LLMUiPresenter;
const LauncherHomeCore = globalThis.LLMLauncherHome;
if (!UiPresenter || !LauncherHomeCore) throw new Error("Launcher interface support did not load.");
const statusPoller = globalThis.LLMPolling.createPoller();
function statusPollInterval(active, dialogId) {
  const interval = active || $(dialogId)?.open ? 1800 : 30000;
  return Math.max(interval, document.hidden ? 10000 : 0);
}
const PiTimelineCore = globalThis.LLMPiTimelineCore;
if (!PiTimelineCore) throw new Error("Pi semantic timeline support did not load.");
const formatNumber = (n) => Number(n || 0).toLocaleString();
const formatBytes = (bytes) => {
  const value = Math.max(0, Number(bytes || 0));
  if (value >= 1e12) return `${(value / 1e12).toFixed(1)} TB`;
  if (value >= 1e9) return `${(value / 1e9).toFixed(value < 10e9 ? 2 : 1)} GB`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(0)} MB`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(0)} KB`;
  return `${Math.round(value)} B`;
};
const formatGiB = (bytes) => `${(Math.max(0, Number(bytes || 0)) / (1024 ** 3)).toFixed(0)} GiB`;
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
const RequestMetricsCore = globalThis.LLMRequestMetrics;
if (!RequestMetricsCore) throw new Error("Request metric presentation support did not load.");
function requestLiveTelemetry(request) { return RequestMetricsCore.liveTelemetry(request); }
function liveRequestPhaseLabel(request) { return RequestMetricsCore.phaseLabel(request, ChatStatusCore.requestPhase); }
function liveRequestDetail(request) { return RequestMetricsCore.liveDetail(request, {formatNumber, formatShortDuration}); }
function completedRequestDetail(request) { return RequestMetricsCore.completedDetail(request, finiteMetric); }

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
const MTPLX_OPERATOR_ROUTE_DEFAULT = "default";
const MTPLX_OPERATOR_ROUTE_2111 = "dense-27b-long-context-2111";
const MTPLX_LONG_CONTEXT_CONTRACT_VERSION = 1;
const MTPLX_LONG_CONTEXT_SWEEP_VERSION = 5;
const MTPLX_LONG_CONTEXT_SUITE = "mtplx-dense-27b-long-context-64k";
const MTPLX_BENCHMARK_FRESH_MILLISECONDS = 30 * 24 * 60 * 60 * 1000;

function mtplxExact2111Runtime(value) {
  return /^(?:mtplx\s+)?2\.11\.1(?:\s+\(2\.11\.1\))?$/i.test(
    String(value || "").trim().replace(/\s+/g, " "),
  );
}

function mtplxExactObjectKeys(value, keys) {
  return Boolean(
    value && typeof value === "object" && !Array.isArray(value)
    && Object.keys(value).length === keys.length
    && keys.every(key => Object.hasOwn(value, key)),
  );
}

function mtplxCanonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(mtplxCanonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map(key => (
      `${JSON.stringify(key)}:${mtplxCanonicalJson(value[key])}`
    )).join(",")}}`;
  }
  return JSON.stringify(value);
}

function mtplxVisibleSamplingContract(model) {
  const mode = String($("samplingMode")?.value || "");
  const aliases = [
    ["temperatureInput", "temperature"], ["topPInput", "top_p"],
    ["topKInput", "top_k"], ["presencePenaltyInput", "presence_penalty"],
    ["frequencyPenaltyInput", "frequency_penalty"],
    ["repetitionPenaltyInput", "repetition_penalty"], ["seedInput", "seed"],
  ];
  let values = {};
  if (mode === "model") {
    const defaults = model?.defaultSampling;
    if (!defaults || typeof defaults !== "object" || Array.isArray(defaults)) return null;
    const allowed = new Set(aliases.map(([, key]) => key));
    if (Object.keys(defaults).some(key => !allowed.has(key))) return null;
    for (const [, key] of aliases) {
      if (defaults[key] === null || defaults[key] === undefined) continue;
      if (typeof defaults[key] !== "number" || !Number.isFinite(defaults[key])) return null;
      values[key] = defaults[key];
    }
  } else if (mode === "custom") {
    for (const [id, key] of aliases) {
      const text = String($(id)?.value ?? "").trim();
      if (key === "seed" && text === "") continue;
      if (text === "") return null;
      const value = Number(text);
      if (!Number.isFinite(value)) return null;
      if (["top_k", "seed"].includes(key) && !Number.isInteger(value)) return null;
      values[key] = value;
    }
  } else return null;
  return {schemaVersion:1, controlled:true, mode, values};
}

function mtplxSamplingContractMatches(record, model) {
  const visible = mtplxVisibleSamplingContract(model);
  const stored = record?.samplingContract;
  return Boolean(
    visible
    && record?.samplingEvidenceVersion === 1
    && record?.samplingControlled === true
    && record?.samplingContractVersion === 1
    && /^[0-9a-f]{64}$/.test(String(record?.samplingFingerprint || ""))
    && /^[0-9a-f]{64}$/.test(String(record?.samplingContractFingerprint || ""))
    && mtplxExactObjectKeys(stored, ["schemaVersion", "controlled", "mode", "values"])
    && mtplxCanonicalJson(stored) === mtplxCanonicalJson(visible)
  );
}

function mtplxLongContextCapabilityExact(model) {
  const capability = model?.backends?.mtplx;
  const route = capability?.longContext2111;
  return Boolean(
    model?.ready === true
    && capability?.runnable === true
    && capability?.mtp === true
    && route && typeof route === "object" && !Array.isArray(route)
    && route.contractVersion === MTPLX_LONG_CONTEXT_CONTRACT_VERSION
    && route.ready === true
    && route.routeId === MTPLX_OPERATOR_ROUTE_2111
    && typeof route.contractId === "string"
    && route.contractId.trim().length > 0 && route.contractId.length <= 256
    && route.minimumContext === 65_536
    && route.requiredProfile === "turbo"
    && route.requiredAcceleration === "mtp"
    && mtplxExact2111Runtime(route.runtimeVersion)
    && mtplxExact2111Runtime(capability.runtimeVersion)
  );
}

function mtplxLongContextRouteEligible(model, values = {}) {
  const route = model?.backends?.mtplx?.longContext2111;
  const context = Number(values.context);
  return Boolean(
    values.backend === "mtplx"
    && mtplxLongContextCapabilityExact(model)
    && values.acceleration === route.requiredAcceleration
    && values.profile === route.requiredProfile
    && Number.isInteger(context) && context >= route.minimumContext
  );
}

function mtplxLongContextRecordMatches(record, model, values = {}, now = Date.now()) {
  const capability = model?.backends?.mtplx;
  const route = capability?.longContext2111;
  const sweep = record?.mtplxOperatorSweep;
  const context = Number(values.context);
  const output = Number(values.output);
  const depth = Number(values.depth);
  const createdAt = Date.parse(String(record?.createdAt || ""));
  const expectedSettings = {
    depth, mtplxOperatorRoute:MTPLX_OPERATOR_ROUTE_2111,
  };
  const engineSettings = record?.engineSettings;
  const candidate = Array.isArray(sweep?.candidates)
    ? sweep.candidates.find(item => item?.route === MTPLX_OPERATOR_ROUTE_2111) : null;
  return Boolean(
    mtplxLongContextRouteEligible(model, values)
    && Number.isInteger(output) && output > 0
    && Number.isInteger(depth) && depth > 0
    && Number.isFinite(createdAt) && createdAt <= now
    && now - createdAt <= MTPLX_BENCHMARK_FRESH_MILLISECONDS
    && record?.scope === "local"
    && record?.backend === "mtplx"
    && record?.kind === "mtplx-long-context-operator-tuning"
    && record?.suite === MTPLX_LONG_CONTEXT_SUITE
    && record?.workloadKind === "agentic"
    && record?.selectionMetric === "generation-tokens-per-second"
    && record?.baselinePassed === true && record?.qualityPassed === true
    && record?.winner === "mtp"
    && record?.runtimeVersion === capability.runtimeVersion
    && mtplxExact2111Runtime(record.runtimeVersion)
    && typeof capability.benchmarkModelFingerprint === "string"
    && /^[0-9a-f]{64}$/.test(capability.benchmarkModelFingerprint)
    && record?.modelFingerprint === capability.benchmarkModelFingerprint
    && Number.isInteger(record?.contextMin) && Number.isInteger(record?.contextMax)
    && record.contextMin <= context && context <= record.contextMax
    && Number.isInteger(record?.outputMin) && Number.isInteger(record?.outputMax)
    && record.outputMin <= output && output <= record.outputMax
    && record?.client === values.client
    && record?.reasoning === values.reasoning
    && record?.targetKV === values.kv
    && mtplxSamplingContractMatches(record, model)
    && mtplxExactObjectKeys(engineSettings, ["profile", "fan"])
    && engineSettings.profile === values.profile
    && engineSettings.fan === values.fan
    && mtplxCanonicalJson(record?.settings) === mtplxCanonicalJson(expectedSettings)
    && mtplxCanonicalJson(record?.modeSettings?.mtp) === mtplxCanonicalJson(expectedSettings)
    && sweep && typeof sweep === "object" && !Array.isArray(sweep)
    && sweep.version === MTPLX_LONG_CONTEXT_SWEEP_VERSION
    && sweep.strategy === "isolated-long-context-operator-comparison"
    && sweep.complete === true && sweep.resourceComparable === true
    && sweep.suiteName === MTPLX_LONG_CONTEXT_SUITE
    && sweep.requiredContext === route.minimumContext
    && sweep.contractId === route.contractId
    && sweep.baselineRoute === MTPLX_OPERATOR_ROUTE_DEFAULT
    && sweep.candidateRoute === MTPLX_OPERATOR_ROUTE_2111
    && sweep.candidateAccepted === true
    && sweep.selectedRoute === MTPLX_OPERATOR_ROUTE_2111
    && mtplxCanonicalJson(sweep.selectedSettings) === mtplxCanonicalJson(expectedSettings)
    && candidate?.selected === true
    && candidate?.qualityMatchesAR === true
    && candidate?.qualityMatchesDefault === true
    && candidate?.resourceComparable === true
    && ["ready", "condition-improved"].includes(candidate?.resourceCooldownStatus)
    && mtplxCanonicalJson(candidate?.settings) === mtplxCanonicalJson(expectedSettings)
  );
}

function mtplxLongContextMeasuredRecord(model, values = {}) {
  const capability = model?.backends?.mtplx;
  const records = Array.isArray(capability?.localBenchmarks)
    ? capability.localBenchmarks.filter(item => item && typeof item === "object") : [];
  if (capability?.localBenchmark && !records.includes(capability.localBenchmark)) {
    records.push(capability.localBenchmark);
  }
  return records
    .filter(record => mtplxLongContextRecordMatches(record, model, values))
    .sort((left, right) => Date.parse(right.createdAt) - Date.parse(left.createdAt))[0] || null;
}

function mtplxEngineEvidenceBindingExact(result = {}) {
  const binding = result.engineEvidenceBinding;
  const records = binding?.recordIds;
  return Boolean(
    binding && typeof binding === "object" && !Array.isArray(binding)
    && binding.scope === "engine"
    && typeof binding.suite === "string" && binding.suite.length > 0
    && binding.preference === result.enginePreference
    && typeof binding.shootoutId === "string" && binding.shootoutId.length > 0
    && records && typeof records === "object" && !Array.isArray(records)
    && typeof records.mtplx === "string" && records.mtplx.length > 0
  );
}

function mtplxOperatorRouteFromOptimization(result, engineSelection, model, context) {
  const requested = result?.options?.mtplxOperatorRoute;
  if (requested !== MTPLX_OPERATOR_ROUTE_2111) return MTPLX_OPERATOR_ROUTE_DEFAULT;
  const values = {
    backend:result?.backend,
    acceleration:result?.options?.acceleration,
    profile:result?.options?.profile,
    context,
    output:Number($("outputInput")?.value),
    depth:Number(result?.options?.depth),
    fan:result?.options?.fan,
    client:launchWorkspace.view().client,
    reasoning:$("reasoningSelect")?.value,
    kv:result?.options?.kv || "off",
  };
  if (!mtplxLongContextMeasuredRecord(model, values)) return MTPLX_OPERATOR_ROUTE_DEFAULT;
  if (!engineSelection) {
    return result?.evidenceTier === "local-benchmark"
      ? MTPLX_OPERATOR_ROUTE_2111 : MTPLX_OPERATOR_ROUTE_DEFAULT;
  }
  const comparisonTier = result?.engineEvidenceTier || result?.evidenceTier;
  const comparisonTrusted = [
    "cross-engine-local-benchmark",
    "cross-engine-leading-band",
    "cross-engine-noise-floor",
  ].includes(comparisonTier);
  return result?.settingsEvidenceTier === "local-benchmark"
    && comparisonTrusted && mtplxEngineEvidenceBindingExact(result)
    ? MTPLX_OPERATOR_ROUTE_2111 : MTPLX_OPERATOR_ROUTE_DEFAULT;
}

function savedMtplxOperatorRoute(options = {}) {
  const value = options.mtplxOperatorRoute ?? MTPLX_OPERATOR_ROUTE_DEFAULT;
  if ([MTPLX_OPERATOR_ROUTE_DEFAULT, MTPLX_OPERATOR_ROUTE_2111].includes(value)) return value;
  throw new Error("The saved long-context execution route is no longer supported.");
}

function mtplxOperatorRouteLabel(options = {}) {
  if (options.mtplxOperatorRoute !== MTPLX_OPERATOR_ROUTE_2111) return "";
  const depth = Number(options.depth);
  const depthLabel = Number.isInteger(depth) && depth > 0 ? ` D${depth}` : "";
  return `MTP${depthLabel} · 2.11.1 long-context`;
}

function updateMtplxLongContextControl(...args) { return launchWorkspace.updateMtplxLongContextControl(...args); }

const optimizerControls = {
  acceleration: "accelerationSelect", depth: "depthInput", profile: "profileSelect",
  mtplxOperatorRoute: "mtplxOperatorRouteSelect",
  fan: "fanSelect", burst: "burstSelect", dflashVerify: "dflashVerifySelect",
  dflashDraftQuant: "dflashDraftQuantSelect", anePrefill: "anePrefillSelect",
  memoryGuard: "memoryGuardSelect",
  expertResidentPercent: "omlxExpertResidentPercent", omlxMemoryGB: "omlxMemoryGB",
  gpu: "gpuSelect", parallel: "parallelInput",
  mtpMinTokens: "mtpMinTokensInput",
  mtpMinContinueProbability: "mtpMinContinueProbabilityInput",
  maxBatchSize: "freeTokenBatchSelect",
  expertCacheSize: "freeTokenExpertCacheInput",
  prefixCacheEntries: "freeTokenPrefixCacheSelect",
  prefillSize: "swiftlmPrefillSelect",
  nativeExpertTopK: "swiftlmTopK",
  promptCacheMode: "mferencePromptCache",
  queueLimit: "mferenceQueueLimit",
  memoryGB: "slotstreamMemoryGB", memoryMode: "slotstreamMemoryMode",
};
const optimizerKeys = {
  mtplx: ["acceleration", "depth", "profile", "mtplxOperatorRoute", "fan"],
  omlx: ["acceleration", "depth", "dflashVerify", "dflashDraftQuant", "burst", "anePrefill", "memoryGuard", "expertResidentPercent", "omlxMemoryGB"],
  lmstudio: [
    "acceleration", "depth", "mtpMinTokens",
    "mtpMinContinueProbability", "gpu", "parallel",
  ],
  freetoken: ["maxBatchSize", "expertCacheSize", "prefixCacheEntries"],
  swiftlm: ["prefillSize", "nativeExpertTopK"],
  mference: ["promptCacheMode", "queueLimit"],
  whallm: [],
  slotstream: ["acceleration", "depth", "memoryGB", "memoryMode"],
  splash: [],
  strata: [],
  rec: [],
  llamacpp: [],
  kolibri: [],
  rapidmlx: ["acceleration", "depth"],
};
const enginePreferenceLabels = {
  throughput:"Highest generation TPS",
  fastest:"Fastest total", responsive:"Fastest first response",
  memory:"Lowest memory use", thermal:"Best thermal stability",
};

























const launcherApi = globalThis.LLMLauncherApi.createClient({
  fetch:(...args) => fetch(...args), getToken:() => state.token,
  setToken:token => { state.token = token; },
});

async function api(path, options = {}) {
  return launcherApi.json(path, options);
}

function showNotice(message, error = false) {
  const box = $("notice");
  if (!message) { box.classList.add("hidden"); return; }
  box.textContent = message;
  box.className = `notice${error ? " error" : ""}`;
}

function selectedModel(...args) { return launchWorkspace.selectedModel(...args); }

function routeRuntimeInstalled(...args) { return launchWorkspace.routeRuntimeInstalled(...args); }

function orderedRouteIds(...args) { return launchWorkspace.orderedRouteIds(...args); }

function visibleRouteCatalog(...args) { return launchWorkspace.visibleRouteCatalog(...args); }

function currentVisibleRoute(...args) { return launchWorkspace.currentVisibleRoute(...args); }

function persistVisibleRoute(...args) { return launchWorkspace.persistVisibleRoute(...args); }

function restoreVisibleSettings(...args) { return launchWorkspace.restoreVisibleSettings(...args); }

function initialiseVisibleRoute(...args) { return launchWorkspace.initialiseVisibleRoute(...args); }

function freeTokenRoute(...args) { return launchWorkspace.freeTokenRoute(...args); }

function freeTokenQualification(...args) { return launchWorkspace.freeTokenQualification(...args); }

function freeTokenExperimentalConsentRequired(...args) { return launchWorkspace.freeTokenExperimentalConsentRequired(...args); }

function freeTokenExperimentalConsentAccepted(...args) { return launchWorkspace.freeTokenExperimentalConsentAccepted(...args); }

function resolvedClientSupport(...args) { return launchWorkspace.resolvedClientSupport(...args); }

function runtimeKvValue(...args) { return launchWorkspace.runtimeKvValue(...args); }

function runtimeKvLabel(...args) { return launchWorkspace.runtimeKvLabel(...args); }

function updateOmlxKvControl(...args) { return launchWorkspace.updateOmlxKvControl(...args); }

function setRuntimeKvValue(...args) { return launchWorkspace.setRuntimeKvValue(...args); }

function gatherOptions(...args) { return launchWorkspace.gatherOptions(...args); }

function gatherGenerationSettings(...args) { return launchWorkspace.gatherGenerationSettings(...args); }

function gatherChatSettings(...args) { return launchWorkspace.gatherChatSettings(...args); }

function gather(...args) { return launchWorkspace.gather(...args); }

function protectedSnapshot(...args) { return launchWorkspace.protectedSnapshot(...args); }

function speedSignature(...args) { return launchWorkspace.speedSignature(...args); }

function optimizerEvidenceContractSignature(...args) { return launchWorkspace.optimizerEvidenceContractSignature(...args); }

function copiedEvidenceBinding(...args) { return launchWorkspace.copiedEvidenceBinding(...args); }

function clearActiveEvidenceBinding(...args) { return launchWorkspace.clearActiveEvidenceBinding(...args); }

function activeEvidenceBindingFor(...args) { return launchWorkspace.activeEvidenceBindingFor(...args); }

function rememberActiveEvidenceBinding(...args) { return launchWorkspace.rememberActiveEvidenceBinding(...args); }

function optimizerValueSnapshot(...args) { return launchWorkspace.optimizerValueSnapshot(...args); }

function restoreOptimizerValues(...args) { return launchWorkspace.restoreOptimizerValues(...args); }

function clearOptimizerAnimationClasses(...args) { return launchWorkspace.clearOptimizerAnimationClasses(...args); }

function setOptimizationState(...args) { return launchWorkspace.setOptimizationState(...args); }

function markOptimizerCustom(...args) { return launchWorkspace.markOptimizerCustom(...args); }

function cancelOptimization(...args) { return launchWorkspace.cancelOptimization(...args); }

function setOptimizerInteractionLocked(...args) { return launchWorkspace.setOptimizerInteractionLocked(...args); }

function setOptimizerMenu(...args) { return launchWorkspace.setOptimizerMenu(...args); }

function closeOptimizerMenu(...args) { return launchWorkspace.closeOptimizerMenu(...args); }

function toggleOptimizerMenu(...args) { return launchWorkspace.toggleOptimizerMenu(...args); }

function themeStorage() {
  try { return globalThis.localStorage; } catch (_error) { return null; }
}

function activeTheme() {
  return ThemeCore.normaliseTheme(document.documentElement.dataset.theme);
}

function activeDetail() {
  return ThemeCore.normaliseDetail(document.documentElement.dataset.detail);
}

function updateChatStatusSummaryLabel(...args) { return chatWorkspace.updateChatStatusSummaryLabel(...args); }

function renderChatStatusDisclosure(...args) { return chatWorkspace.renderChatStatusDisclosure(...args); }

function syncChatStatusDetailMode(...args) { return chatWorkspace.syncChatStatusDetailMode(...args); }

function syncChatResumeDetailMode(...args) { return chatWorkspace.syncChatResumeDetailMode(...args); }

function syncAgentConsoleStatusDetailMode(detail = activeDetail()) { agentConsoleWorkspace.syncDetail(detail); }

function syncRuntimeAdvancedDetailMode(detail = activeDetail()) { runtimeManager.syncAdvanced(detail); }
function syncRuntimeCardDetailMode(detail = activeDetail()) { runtimeManager.syncCards(detail); }

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
  $("hubToolsMenuButton").focus();
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
  if (launchWorkspace.catalog().length) refreshLaunchability();
  closeThemeMenu();
  if (focusMenuButton) $("hubToolsMenuButton").focus();
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

function reasoningChoices(...args) { return launchWorkspace.reasoningChoices(...args); }

function normalizeReasoningSelection(...args) { return launchWorkspace.normalizeReasoningSelection(...args); }

function adapterDescriptor(collection, id) {
  return (state.adapters?.[collection] || []).find(adapter => adapter.id === id);
}

function llamaCppPleCapabilityQualified(capability) {
  const contextWindows = Array.isArray(capability?.contextWindows)
    ? capability.contextWindows.map(Number) : [];
  return capability?.runnable === true
    && capability?.llamacppPle === true
    && capability?.atomicPle?.ready === true
    && capability?.currentProcessVerified === true
    && capability?.atomicPle?.currentProcessVerified === true
    && Number.isInteger(capability?.verificationGeneration)
    && capability.verificationGeneration > 0
    && capability.atomicPle.verificationGeneration === capability.verificationGeneration
    && typeof capability?.receiptFingerprint === "string"
    && /^[0-9a-f]{64}$/.test(capability.receiptFingerprint)
    && contextWindows.length === 1 && contextWindows[0] === 8192;
}

function llamaCppPleQualified(model) {
  return model?.ready === true && llamaCppPleCapabilityQualified(model?.backends?.llamacpp);
}

function llamaCppPleModel() {
  return launchWorkspace.catalog().find(llamaCppPleQualified) || null;
}

function llamaCppPleCheckingModel() {
  return launchWorkspace.catalog().find(model => (
    model?.verificationState === "checking"
    && model?.backends?.llamacpp?.verificationState === "checking"
    && model?.backends?.llamacpp?.currentProcessVerified !== true
  )) || null;
}

const LLAMACPP_PLE_QUALIFICATION_CONTEXT = 8192;
const LLAMACPP_PLE_QUALIFICATION_MEMORY_LIMIT_BYTES = 44 * 1024 ** 3;
const LLAMACPP_PLE_QUALIFICATION_SUITE = "route-qualification-8k";
const LLAMACPP_PLE_QUALIFICATION_CONTRACT_ID = "atomicchat-llamacpp-ssd-ple-8k-v1";
const LLAMACPP_PLE_QUALIFICATION_CONTRACT_VERSION = 1;
const LLAMACPP_PLE_QUALIFICATION_SCENARIOS = Object.freeze([
  "cold", "warmPrefix", "toolIngest", "steadyTurn",
]);
const LLAMACPP_PLE_QUALIFICATION_SAMPLE_MAX_TOKENS = 512;
const LLAMACPP_PLE_QUALIFICATION_ANSWER_RESERVE_TOKENS = 128;
const LLAMACPP_PLE_QUALIFICATION_THINKING_TOKENS = 384;
const LLAMACPP_PLE_QUALIFICATION_MINIMUM_TPS = 15;
const LLAMACPP_PLE_QUALIFICATION_MINIMUM_COMPLETION_TOKENS = 128;
const LLAMACPP_PLE_QUALIFICATION_REASONING_BOUNDARY_ID = "atomicchat-budget-zero-boundary-v1";
const LLAMACPP_PLE_QUALIFICATION_REASONING_MESSAGE_SHA256 = "04dbe3b430e5be6b5f2f130343e8a0b55872538b1ca53c775e7d8afd9b4acb5a";
const UZU_QUALIFICATION_CONTEXTS = Object.freeze([16_384, 32_768, 65_536, 131_072]);
const UZU_QUALIFICATION_SUITES = Object.freeze({
  16_384:"route-qualification-uzu-16k",
  32_768:"route-qualification-uzu-32k",
  65_536:"route-qualification-uzu-64k",
  131_072:"route-qualification-uzu-128k",
});
const UZU_QUALIFICATION_MEMORY_LIMIT_BYTES = 38 * 1024 ** 3;
const UZU_QUALIFICATION_OS_RESERVE_MINIMUM_BYTES = 4 * 1024 ** 3;
const UZU_QUALIFICATION_CONTRACT_VERSION = 5;
const UZU_QUALIFICATION_NEAR_TIER_POLICY_ID = "uzu-near-tier-authoritative-prompt-v4-conversation";
const UZU_QUALIFICATION_NEAR_TIER_MINIMUM_CONTEXT = 65_536;
const UZU_QUALIFICATION_NEAR_TIER_SCENARIOS = Object.freeze(["toolIngest", "steadyTurn"]);
const UZU_QUALIFICATION_NEAR_TIER_FRACTION = 0.90;
const UZU_QUALIFICATION_PROMPT_TOLERANCE_FRACTION = 0.05;
const UZU_QUALIFICATION_PROMPT_TOLERANCE_MIN_TOKENS = 1_024;
const UZU_NATIVE_BOUNDARY_CONTRACT_ID = "uzu-native-auth-context-output-v1";
const UZU_RUNTIME_RELEASE_BINARY_SHA256 = "efe7fc98a8e063c30103a27badb4f308b8cb782708134a7805178f9e16caa0ce";
const UZU_RUNTIME_RELEASE_BINARY_SIZE = 65_079_520;
const UZU_RUNTIME_UPSTREAM_COMMIT = "115609b6ef7ce5a94fc761bf395780f032b09f9b";
const UZU_RUNTIME_SOURCE_PATCH_SHA256 = "680e2d72f0ba7a63fc822543022c6a1fc9b2895276fb7252a8049219de58692f";
const UZU_QUALIFICATION_SCENARIOS = Object.freeze([
  "cold", "warmPrefix", "toolIngest", "steadyTurn",
]);
const UZU_QUALIFICATION_SAMPLE_MAX_TOKENS = 8_192;
const UZU_QUALIFICATION_SAMPLE_MIN_TOKENS = 2_048;
const UZU_QUALIFICATION_ANSWER_RESERVE_TOKENS = 128;
const UZU_QUALIFICATION_MINIMUM_TPS = 15;
const UZU_QUALIFICATION_MINIMUM_COMPLETION_TOKENS = 128;

function uzuQualificationSuite(context) {
  return UZU_QUALIFICATION_SUITES[Number(context)] || "";
}

function uzuQualificationContractId(context) {
  const exact = Number(context);
  return UZU_QUALIFICATION_CONTEXTS.includes(exact)
    ? `qwen36-uzu-dflash-weaver-${exact / 1024}k-v5` : "";
}

function uzuQualificationPromptExercisePolicy(context) {
  const exact = Number(context);
  return {
    id:UZU_QUALIFICATION_NEAR_TIER_POLICY_ID,
    appliesAtOrAboveContextTokens:UZU_QUALIFICATION_NEAR_TIER_MINIMUM_CONTEXT,
    requiredScenarios:[...UZU_QUALIFICATION_NEAR_TIER_SCENARIOS],
    authoritativeUsageRequired:true,
    minimumContextFraction:UZU_QUALIFICATION_NEAR_TIER_FRACTION,
    minimumPromptTokens:Math.ceil(exact * UZU_QUALIFICATION_NEAR_TIER_FRACTION),
    targetPromptTokensRequired:true,
    targetToleranceFraction:UZU_QUALIFICATION_PROMPT_TOLERANCE_FRACTION,
    targetToleranceMinimumTokens:UZU_QUALIFICATION_PROMPT_TOLERANCE_MIN_TOKENS,
  };
}

function uzuQualificationPromptExercisePolicyExact(value, context) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const expected = uzuQualificationPromptExercisePolicy(context);
  const keys = Object.keys(expected);
  return Object.keys(value).length === keys.length
    && keys.every(key => (
      key === "requiredScenarios"
        ? Array.isArray(value[key])
          && value[key].length === expected[key].length
          && value[key].every((item, index) => item === expected[key][index])
        : value[key] === expected[key]
    ));
}

function isUzuQualificationSuite(suite) {
  return Object.values(UZU_QUALIFICATION_SUITES).includes(String(suite || ""));
}

function controllerRouteQualificationBackend(plan = {}) {
  if (plan?.routeQualification !== true) return "";
  const explicit = [
    plan.qualificationBackend,
    plan.qualifiedBackend,
    plan.qualificationRoute?.backend,
    plan.request?.backend,
  ].map(value => String(value || "")).find(Boolean);
  if (explicit) return explicit;
  const eligible = (plan.engines || [])
    .filter(engine => engine?.eligible === true)
    .map(engine => String(engine.backend || engine.id || ""))
    .filter(Boolean);
  return eligible.length === 1 ? eligible[0] : "";
}

function selectedRouteQualificationBackend() {
  const model = selectedModel();
  if (launchWorkspace.view().backend === "omlx" && model?.qwen4Ple?.supported === true) return "omlx";
  if (launchWorkspace.view().backend === "llamacpp" && llamaCppPleQualified(model)) return "llamacpp";
  const uzu = model?.backends?.uzu || {};
  if (
    launchWorkspace.view().backend === "uzu" && model?.ready === true && model?.uzuNative === true
    && uzu.runnable === true && uzu.runtimeManagedAcceleration === "DFlash + Weaver"
  ) return "uzu";
  return "";
}

function performanceReceiptQualificationBackend(receipt = null) {
  const explicitQualification = receipt?.routeQualification === true
    || receipt?.kind === "route-qualification"
    || receipt?.evidenceTier === "local-route-qualification"
    || receipt?.tier === "local-route-qualification";
  if (!explicitQualification) return "";
  const qualifiedBackend = String(receipt?.qualifiedBackend || "").trim();
  const receiptBackend = String(receipt?.backend || "").trim();
  if (qualifiedBackend && receiptBackend && qualifiedBackend !== receiptBackend) return "";
  return qualifiedBackend || receiptBackend;
}

function clientName(client) {
  return adapterDescriptor("workSurfaces", client)?.label
    || ({pi:"Pi", omp:"oh-my-pi", opencode:"OpenCode", codex:"Codex", chat:"Chat"})[client]
    || client;
}

function clientInstalled(...args) { return launchWorkspace.clientInstalled(...args); }

function clientAvailability(...args) { return launchWorkspace.clientAvailability(...args); }

function chatSettingsError(...args) { return launchWorkspace.chatSettingsError(...args); }

function limitError(...args) { return launchWorkspace.limitError(...args); }

function compactNativeContext(value) {
  const number = Number(value || 0);
  return number >= 100_000 ? `${Math.round(number / 1000)}K` : formatNumber(number);
}

function exactContextTier(value) {
  const number = Number(value || 0);
  return Number.isInteger(number) && number > 0 && number % 1024 === 0
    ? `${number / 1024}K` : formatNumber(number);
}

function isUzuModel(model = {}, capability = {}) {
  return model?.uzuNative === true || model?.modelType === "qwen3.6-uzu"
    || capability?.runtimeManagedAcceleration === "DFlash + Weaver"
    || (model?.engines || []).some(engine => engine?.id === "uzu" && engine?.artifactCompatible === true);
}

function modelContextLabel(model, capability = {}, backend = "") {
  const native = Number(model?.nativeContext || 0);
  if (isUzuModel(model, capability) && Number.isInteger(native) && native > 0) {
    return `${compactNativeContext(native)} native · guarded up to ${exactContextTier(UZU_QUALIFICATION_CONTEXTS.at(-1))}`;
  }
  const qualified = Number(capability?.contextMaximum || 0);
  if (Number.isInteger(native) && native > 0
    && Number.isInteger(qualified) && qualified > 0 && qualified < native) {
    return `${formatNumber(native)} native · ${formatNumber(qualified)} ${backend === "rapidmlx" ? "runtime cap" : "qualified cap"}`;
  }
  return `${formatNumber(native)} context`;
}

const rangeOutputIds = {
  depthInput:"depthValue", parallelInput:"parallelValue",
  mtpMinTokensInput:"mtpMinTokensValue",
  mtpMinContinueProbabilityInput:"mtpMinContinueProbabilityValue",
};

function rangeOutputFor(input) {
  return $(rangeOutputIds[input?.id]);
}

function rangePrecision(...args) { return launchWorkspace.rangePrecision(...args); }

function quantizedRangeValue(...args) { return launchWorkspace.quantizedRangeValue(...args); }

function setRangeVisual(...args) { return launchWorkspace.setRangeVisual(...args); }

function renderDflashReadiness(...args) { return launchWorkspace.renderDflashReadiness(...args); }

function renderAneReadiness(...args) { return launchWorkspace.renderAneReadiness(...args); }

function backendName(backend) {
  return adapterDescriptor("engines", backend)?.label
    || ({omlx:"oMLX", lmstudio:"LM Studio", mtplx:"MTPLX", uzu:"Uzu · Mirai", mirai:"Uzu · Mirai", freetoken:"FreeToken", swiftlm:"SwiftLM", mference:"Mference", whallm:"Whallm", slotstream:"Slotstream", rec:"Rec", llamacpp:"llama.cpp · SSD PLE", rapidmlx:"Rapid MLX"})[backend]
    || backend;
}

function backendMark(backend) {
  return ({omlx:"O", lmstudio:"LM", mtplx:"M", uzu:"U", mirai:"U", freetoken:"FT", swiftlm:"S", mference:"MF", whallm:"W", slotstream:"SS", rec:"R", llamacpp:"LC", lms:"LM", rapidmlx:"RM"})[backend] || "?";
}

function backendBinaryKey(backend) {
  return adapterDescriptor("engines", backend)?.binaryKey
    || ({omlx:"omlx", lmstudio:"lms", mtplx:"mtplx", uzu:"mirai", freetoken:"freetoken", swiftlm:"swiftlm", mference:"mference", whallm:"whallm", slotstream:"slotstream", llamacpp:"llamacpp"})[backend]
    || backend;
}

function routeCapabilityPresentation(capability = {}, {backend = "", modelName = "", modelReady = true} = {}) {
  const hostSupport = capability?.hostSupport && typeof capability.hostSupport === "object"
    ? capability.hostSupport : {};
  const performanceEvidence = capability?.performanceEvidence && typeof capability.performanceEvidence === "object"
    ? capability.performanceEvidence : {};
  const hostState = String(hostSupport.state || hostSupport.tier || "").trim().toLowerCase();
  const evidenceTier = String(performanceEvidence.tier || "").trim().toLowerCase();
  const specialRoute = ["whallm", "llamacpp"].includes(backend) || /flash[\s-]*next/i.test(String(modelName || ""));
  const pleContractReady = backend !== "llamacpp"
    || llamaCppPleCapabilityQualified(capability);
  const unavailable = modelReady !== true || capability.runnable !== true
    || hostState === "unavailable" || hostState === "unsupported" || !pleContractReady;
  const experimental = capability.experimental === true || hostState === "experimental";
  const verifiedHere = evidenceTier === "verified-this-mac"
    && performanceEvidence.automaticEligible === true;
  const hostDetail = String(hostSupport.detail || "").trim();
  const evidenceDetail = String(performanceEvidence.detail || "").trim();
  const routeDetail = String(capability.reason || (
    backend === "llamacpp" && !pleContractReady
      ? "The controller did not report a receipt-bound pinned 8K SSD-PLE contract." : ""
  )).trim();

  if (unavailable) return {
    available:false, attention:false, tone:"bad",
    label:"Unavailable", detail:hostDetail || routeDetail || evidenceDetail,
    hostSupport, performanceEvidence,
  };
  if (experimental) return {
    available:true, attention:true, tone:"warning",
    label:"Experimental", detail:hostDetail || evidenceDetail || routeDetail,
    hostSupport, performanceEvidence,
  };
  if (specialRoute && !verifiedHere) {
    return {
      available:true, attention:false, tone:"good",
      label:hostState === "supported" ? "Supported" : "Available",
      detail:hostDetail || routeDetail || "This route is available; exact local performance appears only in its saved performance receipt.",
      hostSupport, performanceEvidence,
    };
  }
  return {
    available:true, attention:false, tone:"good",
    label:verifiedHere ? "Verified here" : "Ready",
    detail:evidenceDetail || routeDetail || hostDetail,
    hostSupport, performanceEvidence,
  };
}

function benchmarkCandidates(...args) { return benchmarkWorkspace.benchmarkCandidates(...args); }

function engineShootoutRoutes(...args) { return benchmarkWorkspace.engineShootoutRoutes(...args); }

function benchmarkWinnerLabel(...args) { return benchmarkWorkspace.benchmarkWinnerLabel(...args); }

function renderBenchmarkCard(...args) { return benchmarkWorkspace.renderBenchmarkCard(...args); }

function renderBenchmarkSetup(...args) { return benchmarkWorkspace.renderBenchmarkSetup(...args); }

function updateAccelerationState(...args) { return launchWorkspace.updateAccelerationState(...args); }

function updateChatSamplingControls(...args) { return launchWorkspace.updateChatSamplingControls(...args); }

function warmRouteRequestSignature(...args) { return launchWorkspace.warmRouteRequestSignature(...args); }

function currentWarmRoutePlan(...args) { return launchWorkspace.currentWarmRoutePlan(...args); }

const SESSION_ADMISSION_REFRESH_MS = 5_000;
const SESSION_ADMISSION_MAX_AGE_MS = 15_000;
const SESSION_ADMISSION_DEBOUNCE_MS = 180;

function visibleSessionAdmissionRequest(...args) { return launchWorkspace.visibleSessionAdmissionRequest(...args); }

function visibleSessionAdmissionSignature(...args) { return launchWorkspace.visibleSessionAdmissionSignature(...args); }

function sessionAdmissionDecision(...args) { return launchWorkspace.sessionAdmissionDecision(...args); }

function currentSessionAdmission(...args) { return launchWorkspace.currentSessionAdmission(...args); }

function sessionAdmissionBlockerCopy(...args) { return launchWorkspace.sessionAdmissionBlockerCopy(...args); }

function scheduleSessionAdmissionPlan(...args) { return launchWorkspace.scheduleSessionAdmissionPlan(...args); }

async function requireFreshSessionAdmission(...args) { return launchWorkspace.requireFreshSessionAdmission(...args); }

function clearWarmRoutePlan(...args) { return launchWorkspace.clearWarmRoutePlan(...args); }

function scheduleWarmRoutePlan(...args) { return launchWorkspace.scheduleWarmRoutePlan(...args); }

async function loadWarmRoutePlan(...args) { return launchWorkspace.loadWarmRoutePlan(...args); }

function updateWorkSurface(...args) { return launchWorkspace.updateWorkSurface(...args); }

function updateContextChoices(...args) { return launchWorkspace.updateContextChoices(...args); }

function refreshLaunchability(...args) { return launchWorkspace.refreshLaunchability(...args); }

function updateBackend(...args) { return launchWorkspace.updateBackend(...args); }

function slotstreamDownloadMessage(...args) { return launchWorkspace.slotstreamDownloadMessage(...args); }

function renderModelOptions(...args) { return launchWorkspace.renderModelOptions(...args); }

function applyModelChatDefaults(...args) { return launchWorkspace.applyModelChatDefaults(...args); }

function accelerationSelectionError(...args) { return launchWorkspace.accelerationSelectionError(...args); }

function clearUnavailableModelControls(...args) { return launchWorkspace.clearUnavailableModelControls(...args); }

function modelChanged(...args) { return launchWorkspace.modelChanged(...args); }

async function loadModels(...args) { return launchWorkspace.loadModels(...args); }

function freeTokenEndpointLabel(...args) { return launchWorkspace.freeTokenEndpointLabel(...args); }

function freeTokenSettingsError(...args) { return launchWorkspace.freeTokenSettingsError(...args); }

function updateFreeTokenNativeControls(...args) { return launchWorkspace.updateFreeTokenNativeControls(...args); }

function renderFreeTokenConnection(...args) { return launchWorkspace.renderFreeTokenConnection(...args); }

function openFreeTokenDialog(...args) { return launchWorkspace.openFreeTokenDialog(...args); }

async function connectFreeToken(...args) { return launchWorkspace.connectFreeToken(...args); }

async function disconnectFreeToken(...args) { return launchWorkspace.disconnectFreeToken(...args); }

function fieldForKey(...args) { return launchWorkspace.fieldForKey(...args); }

async function revealFirstChangedControl(...args) { return launchWorkspace.revealFirstChangedControl(...args); }

function optimizerValueMatches(...args) { return launchWorkspace.optimizerValueMatches(...args); }

async function animateRange(...args) { return launchWorkspace.animateRange(...args); }

async function animateOptimalControl(...args) { return launchWorkspace.animateOptimalControl(...args); }

async function applyOptimal(...args) { return launchWorkspace.applyOptimal(...args); }

async function prepareVerifiedQuickLaunch(...args) { return launchWorkspace.prepareVerifiedQuickLaunch(...args); }

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
    && receipt?.toolContractVerified === true
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

  const admission = currentSessionAdmission();
  const canStart = Boolean(plan?.ready && visibleMatches && !active && !state.routeCheckLoading && !receiptReady && !acquisitionIsActive());
  $("routeCheckConsent").disabled = true;
  $("routeCheckConsent").checked = false;
  $("routeCheckConsentPanel").classList.add("hidden");
  $("routeCheckConsentCopy").textContent = work
    ? `${work.modelLoads} temporary model load · ${work.generatedRequests} generated request${work.generatedRequests === 1 ? "" : "s"} · at most ${work.maxGeneratedTokensPerRequest} tokens each · automatic unload.`
    : "The model-load and generated-request count will appear after the read-only plan is ready.";
  $("routeCheckStartButton").disabled = !(canStart && plan?.contractId && admission.actionReady);
  $("routeCheckStartButton").title = admission.actionReady ? "" : admission.detail;
  $("routeCheckStartButton").classList.toggle("hidden", receiptReady);
  $("routeCheckStopButton").disabled = !active;
  $("routeCheckStartLabel").textContent = !admission.actionReady
    ? sessionAdmissionBlockerCopy(admission)
    : plan?.ready ? "Synthetic prompts · automatic unload" : "Waiting for a valid plan";
  const showCheckedLaunch = guided || Boolean(receipt);
  $("routeCheckLaunchButton").classList.toggle("hidden", !showCheckedLaunch);
  $("routeCheckLaunchButton").disabled = !receiptReady || state.verifiedLaunchBusy || !admission.actionReady;
  $("routeCheckLaunchButton").title = receiptReady && !admission.actionReady ? admission.detail : "";
  $("routeCheckLaunchLabel").textContent = state.verifiedLaunchBusy
    ? "Revalidating the exact receipt…"
    : receiptReady && !admission.actionReady
      ? sessionAdmissionBlockerCopy(admission)
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
  let plan = state.routeCheckPlan;
  if (!plan?.ready || !plan.contractId || !routeCheckVisibleMatches() || routeCheckIsActive()) return;
  if (!await requireFreshSessionAdmission()) {
    renderRouteCheck();
    return;
  }
  plan = state.routeCheckPlan;
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

const pollRouteCheckStatus = statusPoller.add("routeCheck", {
  interval:() => statusPollInterval(routeCheckIsActive(), "routeCheckDialog"),
  run:async () => {
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
  },
});

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
  if (!await requireFreshSessionAdmission()) {
    renderRouteCheck();
    return;
  }
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
    const launched = await launch(request, {admissionChecked:true});
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

async function preview(...args) { return launchWorkspace.preview(...args); }

function readChatDraftEnvelope(...args) { return chatWorkspace.readChatDraftEnvelope(...args); }

function writeChatDraftEnvelope(...args) { return chatWorkspace.writeChatDraftEnvelope(...args); }

function readChatQueueEnvelope(...args) { return chatWorkspace.readChatQueueEnvelope(...args); }

function writeChatQueueEnvelope(...args) { return chatWorkspace.writeChatQueueEnvelope(...args); }

function persistChatQueue(...args) { return chatWorkspace.persistChatQueue(...args); }

function restoreChatQueue(...args) { return chatWorkspace.restoreChatQueue(...args); }

function migrateChatQueueKey(...args) { return chatWorkspace.migrateChatQueueKey(...args); }

function chatQueueCount(...args) { return chatWorkspace.chatQueueCount(...args); }

function chatDraftSurfacePrefix(...args) { return chatWorkspace.chatDraftSurfacePrefix(...args); }

function chatHistoryDraftKey(...args) { return chatWorkspace.chatHistoryDraftKey(...args); }

function newChatDraftKey(...args) { return chatWorkspace.newChatDraftKey(...args); }

function isPortableChatDraftKey(...args) { return chatWorkspace.isPortableChatDraftKey(...args); }

function localUuid(...args) { return chatWorkspace.localUuid(...args); }

function chatTurnTabIdentifier(...args) { return chatWorkspace.chatTurnTabIdentifier(...args); }

function chatDraftHistoryIdFromKey(...args) { return chatWorkspace.chatDraftHistoryIdFromKey(...args); }

function migrateLegacyChatHistoryStorage(...args) { return chatWorkspace.migrateLegacyChatHistoryStorage(...args); }

function sizeChatInput(...args) { return chatWorkspace.sizeChatInput(...args); }

function renderChatDraftStatus(...args) { return chatWorkspace.renderChatDraftStatus(...args); }

function persistChatDraftNow(...args) { return chatWorkspace.persistChatDraftNow(...args); }

function persistChatSessionState(...args) { return chatWorkspace.persistChatSessionState(...args); }

function scheduleChatDraftSave(...args) { return chatWorkspace.scheduleChatDraftSave(...args); }

function activateChatDraft(...args) { return chatWorkspace.activateChatDraft(...args); }

function clearChatDraft(...args) { return chatWorkspace.clearChatDraft(...args); }

function migrateChatDraftToHistory(...args) { return chatWorkspace.migrateChatDraftToHistory(...args); }

async function restorePendingChatDraftConversation(...args) { return chatWorkspace.restorePendingChatDraftConversation(...args); }





function renderLaunchMemoryEstimate(...args) { return launchWorkspace.renderLaunchMemoryEstimate(...args); }

function updateLaunchHome(...args) { return launchWorkspace.updateLaunchHome(...args); }

function renderLaunchPreparation(...args) { return launchWorkspace.renderLaunchPreparation(...args); }

async function startSimpleLaunch(...args) { return launchWorkspace.startSimpleLaunch(...args); }

function cancelSimpleLaunch(...args) { return launchWorkspace.cancelSimpleLaunch(...args); }

async function launch(...args) { return launchWorkspace.launch(...args); }

function nextChatMessageId(...args) { return chatWorkspace.nextChatMessageId(...args); }

function normaliseChatTimestamp(...args) { return chatWorkspace.normaliseChatTimestamp(...args); }

function formatChatTimestamp(...args) { return chatWorkspace.formatChatTimestamp(...args); }

function normaliseChatFailure(...args) { return chatWorkspace.normaliseChatFailure(...args); }

function normaliseChatMessage(...args) { return chatWorkspace.normaliseChatMessage(...args); }

function resetChatConversation(...args) { return chatWorkspace.resetChatConversation(...args); }

function chatEventUsage(...args) { return chatWorkspace.chatEventUsage(...args); }

function emitThinkTaggedText(...args) { return chatWorkspace.emitThinkTaggedText(...args); }

async function consumeChatResponse(...args) { return chatWorkspace.consumeChatResponse(...args); }

function renderCacheObservatory(...args) { return launchWorkspace.renderCacheObservatory(...args); }

function renderRequestActivity(...args) { return launchWorkspace.renderRequestActivity(...args); }

function renderChatUsage(...args) { return chatWorkspace.renderChatUsage(...args); }

function chatContextLocked(...args) { return chatWorkspace.chatContextLocked(...args); }

function normaliseChatWorkspacePath(...args) { return chatWorkspace.normaliseChatWorkspacePath(...args); }

function chatWorkspacePathPolicy(...args) { return chatWorkspace.chatWorkspacePathPolicy(...args); }

function chatWorkspaceCandidatePriority(...args) { return chatWorkspace.chatWorkspaceCandidatePriority(...args); }

function chatWorkspaceTerms(...args) { return chatWorkspace.chatWorkspaceTerms(...args); }

function chatWorkspaceFileScore(...args) { return chatWorkspace.chatWorkspaceFileScore(...args); }

function chatWorkspaceExcerpt(...args) { return chatWorkspace.chatWorkspaceExcerpt(...args); }

function chatRequestAvailableContextCharacters(...args) { return chatWorkspace.chatRequestAvailableContextCharacters(...args); }

function chatWorkspaceRequestCharacterBudget(...args) { return chatWorkspace.chatWorkspaceRequestCharacterBudget(...args); }

function chatContextRequestFiles(...args) { return chatWorkspace.chatContextRequestFiles(...args); }

function renderChatContextPack(...args) { return chatWorkspace.renderChatContextPack(...args); }

function supportedChatContextFile(...args) { return chatWorkspace.supportedChatContextFile(...args); }

async function addChatContextFiles(...args) { return chatWorkspace.addChatContextFiles(...args); }

async function addChatWorkspaceFolder(...args) { return chatWorkspace.addChatWorkspaceFolder(...args); }

function removeChatContextFile(...args) { return chatWorkspace.removeChatContextFile(...args); }

function chatScrollMetrics(...args) { return chatWorkspace.chatScrollMetrics(...args); }

function updateChatScrollUi(...args) { return chatWorkspace.updateChatScrollUi(...args); }

function scrollChatToLatest(...args) { return chatWorkspace.scrollChatToLatest(...args); }

function chatTranscriptMatches(...args) { return chatWorkspace.chatTranscriptMatches(...args); }

function renderChatTranscriptToolbar(...args) { return chatWorkspace.renderChatTranscriptToolbar(...args); }

function clearChatTranscriptHighlights(...args) { return chatWorkspace.clearChatTranscriptHighlights(...args); }

function highlightChatTranscriptText(...args) { return chatWorkspace.highlightChatTranscriptText(...args); }

function applyChatTranscriptSearch(...args) { return chatWorkspace.applyChatTranscriptSearch(...args); }

function openChatTranscriptSearch(...args) { return chatWorkspace.openChatTranscriptSearch(...args); }

function closeChatTranscriptSearch(...args) { return chatWorkspace.closeChatTranscriptSearch(...args); }

function stepChatTranscriptMatch(...args) { return chatWorkspace.stepChatTranscriptMatch(...args); }

function renderChatInline(...args) { return chatWorkspace.renderChatInline(...args); }

function renderChatMarkdown(...args) { return chatWorkspace.renderChatMarkdown(...args); }

function renderChatMessages(...args) { return chatWorkspace.renderChatMessages(...args); }

function renderChatQueue(...args) { return chatWorkspace.renderChatQueue(...args); }

function queueChatRender(...args) { return chatWorkspace.queueChatRender(...args); }

function setChatBusy(...args) { return chatWorkspace.setChatBusy(...args); }

function queueChatMessage(...args) { return chatWorkspace.queueChatMessage(...args); }

async function processChatQueue(...args) { return chatWorkspace.processChatQueue(...args); }

function resumeChatQueue(...args) { return chatWorkspace.resumeChatQueue(...args); }

function moveQueuedChatMessage(...args) { return chatWorkspace.moveQueuedChatMessage(...args); }

function editQueuedChatMessage(...args) { return chatWorkspace.editQueuedChatMessage(...args); }

function finishQueuedChatEdit(...args) { return chatWorkspace.finishQueuedChatEdit(...args); }

function ensureChatHistoryId(...args) { return chatWorkspace.ensureChatHistoryId(...args); }

function currentChatCheckpointPayload(...args) { return chatWorkspace.currentChatCheckpointPayload(...args); }

function scheduleChatTurnCheckpoint(...args) { return chatWorkspace.scheduleChatTurnCheckpoint(...args); }

async function flushChatTurnCheckpoint(...args) { return chatWorkspace.flushChatTurnCheckpoint(...args); }

function beginChatTurnCheckpoint(...args) { return chatWorkspace.beginChatTurnCheckpoint(...args); }

function cancelChatTurnCheckpoint(...args) { return chatWorkspace.cancelChatTurnCheckpoint(...args); }

async function finishChatTurnCheckpoint(...args) { return chatWorkspace.finishChatTurnCheckpoint(...args); }

async function clearChatTurnCheckpoint(...args) { return chatWorkspace.clearChatTurnCheckpoint(...args); }

async function startChatTurn(...args) { return chatWorkspace.startChatTurn(...args); }

function chatMessageIndex(...args) { return chatWorkspace.chatMessageIndex(...args); }

async function createChatBranch(...args) { return chatWorkspace.createChatBranch(...args); }

async function branchChatAt(...args) { return chatWorkspace.branchChatAt(...args); }

async function editAndRetryChatMessage(...args) { return chatWorkspace.editAndRetryChatMessage(...args); }

async function regenerateChatMessage(...args) { return chatWorkspace.regenerateChatMessage(...args); }

async function retryIncompleteChatMessage(...args) { return chatWorkspace.retryIncompleteChatMessage(...args); }

async function continueChatMessage(...args) { return chatWorkspace.continueChatMessage(...args); }

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

async function copyChatMessage(...args) { return chatWorkspace.copyChatMessage(...args); }

async function copyChatCode(...args) { return chatWorkspace.copyChatCode(...args); }

async function runChatRevision(...args) { return chatWorkspace.runChatRevision(...args); }

async function trimChatToRecent(...args) { return chatWorkspace.trimChatToRecent(...args); }

function sendChat(...args) { return chatWorkspace.sendChat(...args); }

function chatHasPersistableTranscript(...args) { return chatWorkspace.chatHasPersistableTranscript(...args); }

async function saveChatBeforeNavigation(...args) { return chatWorkspace.saveChatBeforeNavigation(...args); }

async function saveChatBeforeSurfaceExit(...args) { return chatWorkspace.saveChatBeforeSurfaceExit(...args); }

async function newChat(...args) { return chatWorkspace.newChat(...args); }

function currentChatHistoryPayload(...args) { return chatWorkspace.currentChatHistoryPayload(...args); }

async function runChatHistoryMutation(...args) { return chatWorkspace.runChatHistoryMutation(...args); }

async function saveCurrentChatHistory(...args) { return chatWorkspace.saveCurrentChatHistory(...args); }

async function waitForChatHistorySave(...args) { return chatWorkspace.waitForChatHistorySave(...args); }

function chatHistoryDate(...args) { return chatWorkspace.chatHistoryDate(...args); }

function chatThreadSummary(...args) { return chatWorkspace.chatThreadSummary(...args); }

function chatBranchKindLabel(...args) { return chatWorkspace.chatBranchKindLabel(...args); }

function chatHistoryMatches(...args) { return chatWorkspace.chatHistoryMatches(...args); }

function renderChatSidebarVisibility(...args) { return chatWorkspace.renderChatSidebarVisibility(...args); }

function chatUnsavedDrafts(...args) { return chatWorkspace.chatUnsavedDrafts(...args); }

function renderChatSidebar(...args) { return chatWorkspace.renderChatSidebar(...args); }

async function openUnsavedChatDraft(...args) { return chatWorkspace.openUnsavedChatDraft(...args); }

function chatSurfaceRoute(...args) { return chatWorkspace.chatSurfaceRoute(...args); }

function chatRunSettingsSurfaceKey(...args) { return chatWorkspace.chatRunSettingsSurfaceKey(...args); }

function chatRunSettingsPayload(...args) { return chatWorkspace.chatRunSettingsPayload(...args); }

function activeChatRunSettings(...args) { return chatWorkspace.activeChatRunSettings(...args); }

function setChatRunSettingsStatus(...args) { return chatWorkspace.setChatRunSettingsStatus(...args); }

function updateChatRunSamplingControls(...args) { return chatWorkspace.updateChatRunSamplingControls(...args); }

function setChatRunSettingsBusy(...args) { return chatWorkspace.setChatRunSettingsBusy(...args); }

function populateChatRunSettings(...args) { return chatWorkspace.populateChatRunSettings(...args); }

function gatherChatRunSettings(...args) { return chatWorkspace.gatherChatRunSettings(...args); }

function setChatRunSettingsBackgroundInert(...args) { return chatWorkspace.setChatRunSettingsBackgroundInert(...args); }

function closeChatRunSettings(...args) { return chatWorkspace.closeChatRunSettings(...args); }

async function openChatRunSettings(...args) { return chatWorkspace.openChatRunSettings(...args); }

async function saveChatRunSettings(...args) { return chatWorkspace.saveChatRunSettings(...args); }

function chatRoutesMatch(...args) { return chatWorkspace.chatRoutesMatch(...args); }

function chatRouteLabel(...args) { return chatWorkspace.chatRouteLabel(...args); }

function sessionRouteActive(run, phase) {
  return Boolean(
    run?.purpose === "session" && run.runId
    && ["preflight", "starting", "running", "stopping"].includes(phase),
  );
}

function surfacePostmortemMarker(phase, message, subject = "Surface") {
  const normalizedPhase = String(phase || "stopped").toLowerCase();
  const normalizedMessage = String(message || "")
    .replace(/\0/g, "").replace(/\s+/g, " ").trim().slice(0, 180);
  const failed = normalizedPhase === "failed"
    || /\b(?:failed|failure|error|crash(?:ed)?|unexpectedly terminated)\b/i.test(normalizedMessage);
  const stateLabel = failed ? "failed" : "stopped";
  const title = failed ? `${subject} failed` : `${subject} stopped`;
  const reason = /^(?:ready|idle|stopped)$/i.test(normalizedMessage) ? "" : normalizedMessage;
  return {
    state:stateLabel,
    title,
    detail:`${reason ? `${reason} ` : ""}Bounded output retained. Close it or open another surface to clear it.`,
  };
}

function retainChatPostmortem(...args) { return chatWorkspace.retainChatPostmortem(...args); }

function clearChatForReplacement(...args) { return chatWorkspace.clearChatForReplacement(...args); }

function renderChatRoute(...args) { return chatWorkspace.renderChatRoute(...args); }

function renderChatHistory(...args) { return chatWorkspace.renderChatHistory(...args); }


const launchWorkspace = LLMLaunchWorkspace.createController({
 nodes:Object.fromEntries(LLMLaunchWorkspace.nodeIds.map(id=>[id,$(id)])),
 collections:{backendButtons:[...document.querySelectorAll('[data-backend]')],clientButtons:[...document.querySelectorAll('[data-client]')],
  optimizerButtons:[...document.querySelectorAll('[data-optimizer-scope]')],optimizerControls:[...document.querySelectorAll('.optimizable')],
  chatSamplers:[...document.querySelectorAll('.chat-sampler')],sessionSamplers:[...document.querySelectorAll('.session-attach-sampler')]},
 cores:{RoutePreferenceCore,LaunchFlow,LauncherHomeCore,ChatStatusCore,CalibrationDecision,UiPresenter},
 policy:{optimizerControls,optimizerKeys,enginePreferenceLabels,SESSION_ADMISSION_REFRESH_MS,SESSION_ADMISSION_MAX_AGE_MS,SESSION_ADMISSION_DEBOUNCE_MS,MTPLX_OPERATOR_ROUTE_DEFAULT,MTPLX_OPERATOR_ROUTE_2111,MTPLX_LONG_CONTEXT_SUITE,LLAMACPP_PLE_QUALIFICATION_SUITE},
 platform:{setTimeout:(callback,delay)=>setTimeout(callback,delay),clearTimeout:handle=>clearTimeout(handle),requestAnimationFrame:callback=>requestAnimationFrame(callback),Event,performance,sleep,storage:themeStorage,
  confirm:message=>window.confirm(message),activeElement:()=>document.activeElement,isHidden:()=>document.hidden,
  createOption:()=>document.createElement('option'),onDocumentClick:callback=>document.addEventListener('click',callback),onDocumentKeyDown:callback=>document.addEventListener('keydown',callback)},
 polling:{register:(name,task)=>statusPoller.add(name,task)},
 network:{benchmarkHistory:options=>api("/api/benchmark/history",options),benchmarkStart:options=>api("/api/benchmark/start",options),benchmarkStatus:options=>api("/api/benchmark/status",options),benchmarkStop:options=>api("/api/benchmark/stop",options),calibrationPlan:options=>api("/api/calibration/plan",options),freetokenConnect:options=>api("/api/freetoken/connect",options),freetokenDisconnect:options=>api("/api/freetoken/disconnect",options),launch:options=>api("/api/launch",options),log:options=>api("/api/log",options),models:options=>api("/api/models",options),optimal:options=>api("/api/optimal",options),optimalEngine:options=>api("/api/optimal-engine",options),preview:options=>api("/api/preview",options),sessionAttach:options=>api("/api/session/attach",options),sessionAttachmentPlan:options=>api("/api/session/attachment-plan",options),sessionIdlePolicy:options=>api("/api/session/idle-policy",options),sessionPlan:options=>api("/api/session/plan",options),sessionRequestCancel:options=>api("/api/session/request/cancel",options),sessionWarmAttach:options=>api("/api/session/warm-attach",options),sessionWarmPlan:options=>api("/api/session/warm-plan",options),status:options=>api("/api/status",options),stop:options=>api("/api/stop",options)},
 formatting:{esc:(...args)=>esc(...args),
    formatBytes:(...args)=>formatBytes(...args),
    formatGiB:(...args)=>formatGiB(...args),
    formatNumber:(...args)=>formatNumber(...args),
    formatShortDuration:(...args)=>formatShortDuration(...args),
    finiteMetric:(...args)=>finiteMetric(...args),
    backendName:(...args)=>backendName(...args),
    clientName:(...args)=>clientName(...args),
    exactContextTier:(...args)=>exactContextTier(...args),
    rangeOutputFor:(...args)=>rangeOutputFor(...args),
    requestTps:(...args)=>requestTps(...args),
    liveRequestPhaseLabel:(...args)=>liveRequestPhaseLabel(...args),
    liveRequestDetail:(...args)=>liveRequestDetail(...args),
    completedRequestDetail:(...args)=>completedRequestDetail(...args),
    modelContextLabel:(...args)=>modelContextLabel(...args)},
 registry:{routeCapabilityPresentation:(...args)=>routeCapabilityPresentation(...args),
    backendBinaryKey:(...args)=>backendBinaryKey(...args),
    adapterDescriptor:(...args)=>adapterDescriptor(...args),
    uiEngineVisible:(...args)=>uiEngineVisible(...args),
    uiFeatureEnabled:(...args)=>uiFeatureEnabled(...args),
    uiModelVisible:(...args)=>uiModelVisible(...args),
    uiRequestVisible:(...args)=>uiRequestVisible(...args),
    llamaCppPleCheckingModel:(...args)=>llamaCppPleCheckingModel(...args),
    llamaCppPleModel:(...args)=>llamaCppPleModel(...args),
    llamaCppPleQualified:(...args)=>llamaCppPleQualified(...args),
    mtplxLongContextCapabilityExact:(...args)=>mtplxLongContextCapabilityExact(...args),
    mtplxLongContextMeasuredRecord:(...args)=>mtplxLongContextMeasuredRecord(...args),
    mtplxLongContextRouteEligible:(...args)=>mtplxLongContextRouteEligible(...args),
    mtplxOperatorRouteFromOptimization:(...args)=>mtplxOperatorRouteFromOptimization(...args),
    mtplxOperatorRouteLabel:(...args)=>mtplxOperatorRouteLabel(...args),
    savedMtplxOperatorRoute:(...args)=>savedMtplxOperatorRoute(...args),
    selectedRouteQualificationBackend:(...args)=>selectedRouteQualificationBackend(...args),
    performanceReceiptQualificationBackend:(...args)=>performanceReceiptQualificationBackend(...args),
    uzuQualificationSuite:(...args)=>uzuQualificationSuite(...args),
    applyBootstrapData:(...args)=>applyBootstrapData(...args),binaries:()=>state.binaries,adapters:()=>state.adapters,clientSupport:()=>state.clientSupport,
  useRuntimes:value=>{state.binaries=structuredClone(value)},useAdapters:value=>{state.adapters=structuredClone(value)}},
 jobs:{acquisitionIsActive:(...args)=>acquisitionIsActive(...args),
    setupIsActive:(...args)=>setupIsActive(...args),
    aneWorkIsActive:(...args)=>aneWorkIsActive(...args),
    aneCloneIsActive:(...args)=>aneCloneIsActive(...args),
    routeCheckIsActive:(...args)=>routeCheckIsActive(...args),
    pollAcquisitionStatus:(...args)=>pollAcquisitionStatus(...args),
    pollAneCloneStatus:(...args)=>pollAneCloneStatus(...args),
    pollAneStatus:(...args)=>pollAneStatus(...args),
    pollRouteCheckStatus:(...args)=>pollRouteCheckStatus(...args),
    pollRuntimeUpdateStatus:(...args)=>pollRuntimeUpdateStatus(...args),
    pollSetupStatus:(...args)=>pollSetupStatus(...args),
    updateAcquisitionControls:(...args)=>updateAcquisitionControls(...args),
    updateSetupControls:(...args)=>updateSetupControls(...args),
    updateAneControls:(...args)=>updateAneControls(...args),
    openSetupAssistant:(...args)=>openSetupAssistant(...args),
    openAneTuner:(...args)=>openAneTuner(...args),snapshot:()=>({setupPhase:state.setupPhase,setupStatus:state.setupStatus,anePhase:state.anePhase,aneStatus:state.aneStatus,
  aneClonePhase:state.aneClonePhase,aneCloneStatus:state.aneCloneStatus,routeCheckPhase:state.routeCheckPhase,routeCheckStatus:state.routeCheckStatus,verifiedLaunchBusy:state.verifiedLaunchBusy}),
  updateRuntimeControls:()=>runtimeManager.updateControls()},
 shell:{showNotice:(...args)=>showNotice(...args),
    activeDetail:(...args)=>activeDetail(...args),
    reducedMotion:(...args)=>reducedMotion(...args),
    setHubToolsMenu:(...args)=>setHubToolsMenu(...args),
    setThemeMenu:(...args)=>setThemeMenu(...args),markPreparing:value=>UiPresenter.data(document.body,'preparingLaunch',value)},
 surfaces:{agentConsoleIsVisible:(...args)=>agentConsoleIsVisible(...args),
    currentAgentConsoleView:(...args)=>currentAgentConsoleView(...args),
    enterAgentConsole:(...args)=>enterAgentConsole(...args),
    leaveAgentConsole:(...args)=>leaveAgentConsole(...args),
    saveChatBeforeSurfaceExit:(...args)=>saveChatBeforeSurfaceExit(...args),
    enterChatSurface:(...args)=>enterChatSurface(...args),
    updateAgentWorkspace:(...args)=>updateAgentWorkspace(...args),
    updateChatWorkspace:(...args)=>updateChatWorkspace(...args),
    syncAgentConsoleViews:(...args)=>syncAgentConsoleViews(...args),
    updateChatStatusSummaryLabel:(...args)=>updateChatStatusSummaryLabel(...args),
    selectAgentConsole:(...args)=>selectAgentConsole(...args),
    detachChatSurface:(...args)=>detachChatSurface(...args),
    stopAgentConsoleSurface:(...args)=>stopAgentConsoleSurface(...args),
    restartAgentConsoleSurface:(...args)=>restartAgentConsoleSurface(...args),chatView:()=>chatWorkspace.view(),initializePrimaryChat:run=>chatWorkspace.initializePrimary(run),abortChatResponse:()=>chatWorkspace.abortResponse(),
  hasPendingChatReview:()=>chatResumeReview.hasPending(),chatReviewStopped:message=>chatResumeReview.stopped(message)},
 saved:{loadQuickStart:(...args)=>loadQuickStart(...args),
    renderProfileEditBanner:(...args)=>renderProfileEditBanner(...args),
    renderProfiles:(...args)=>renderProfiles(...args),
    renderQuickStart:(...args)=>renderQuickStart(...args),
    renderSessionSets:(...args)=>renderSessionSets(...args),
    rememberAppliedProfile:(...args)=>rememberAppliedProfile(...args),isBusy:()=>profilesManager.isBusy(),shortcutsLoaded:()=>profilesManager.shortcutsLoaded()},
 assets:{openFreeTokenModelReview:(...args)=>openFreeTokenModelReview(...args),invalidateLibrary:()=>modelAssets.invalidateLibrary(),activity:()=>modelAssets.activity()},
 benchmark:{benchmarkCandidates:(...args)=>benchmarkCandidates(...args),
    renderBenchmarkCard:(...args)=>renderBenchmarkCard(...args),
    renderBenchmarkSetup:(...args)=>renderBenchmarkSetup(...args),
    renderCalibration:(...args)=>renderCalibration(...args),
    scheduleBenchmarkHistory:(...args)=>scheduleBenchmarkHistory(...args),
    applyCalibrationResult:(...args)=>applyCalibrationResult(...args),
    completedCalibrationMatchesOptimizerChoice:(...args)=>completedCalibrationMatchesOptimizerChoice(...args),
    openCalibrationAssistant:(...args)=>openCalibrationAssistant(...args),
    openPerformanceBenchmarkLab:(...args)=>openPerformanceBenchmarkLab(...args),
    pollBenchmarkStatus:(...args)=>pollBenchmarkStatus(...args),view:()=>benchmarkWorkspace.view()},
 preflight:{openRouteCheck:(...args)=>openRouteCheck(...args),
    renderRouteCheck:(...args)=>renderRouteCheck(...args),setIntent:value=>{state.routeCheckIntent=value}},
});

const chatResumeReview = ChatResumeCore.createController({
  elements:{
    dialog:$("chatResumeDialog"), route:$("chatResumeRoute"), badge:$("chatResumeBadge"),
    title:$("chatResumeTitle"), subtitle:$("chatResumeSubtitle"),
    promptPanel:$("chatResumePromptPanel"), systemPrompt:$("chatResumeSystemPrompt"),
    withoutPrompt:$("chatResumeWithoutPrompt"), memoryPanel:$("chatResumeMemoryPanel"),
    memoryConsent:$("chatResumeMemoryConsent"), memoryTitle:$("chatResumeMemoryTitle"),
    memoryCopy:$("chatResumeMemoryCopy"), experimentalPanel:$("chatResumeExperimentalPanel"),
    experimentalConsent:$("chatResumeExperimentalConsent"), status:$("chatResumeStatus"),
    apply:$("chatResumeApply"), start:$("chatResumeStart"), startLabel:$("chatResumeStartLabel"),
  },
  fetchPlan:payload => api("/api/chat/history/resume-plan", {method:"POST", body:JSON.stringify(payload)}),
  requestVisible:uiRequestVisible, engineVisible:uiEngineVisible,
  formatNumber, formatBytes, detailed:() => activeDetail() === "detailed",
  applyRequest:applyProfileRequest, launchRequest:launch, openTranscript:openChatHistoryThread,
  readyToOpen:() => {
    const chat = chatWorkspace.view();
    return launchWorkspace.view().phase === "running" && Boolean(chat.surfaceId)
      && !chat.generating && !chat.revisionBusy && !chat.editing && !chat.historyBusy;
  },
  beforeOpen:() => { if ($("chatHistoryDialog").open) $("chatHistoryDialog").close(); },
  onApplied:() => setQuickStartEditor(true), notify:showNotice,
  onChange:() => { renderChatHistory(); renderQuickStart(); },
});

const chatWorkspace = LLMChatWorkspace.createController({
  nodes:Object.fromEntries(LLMChatWorkspace.nodeIds.map(id=>[id,$(id)])),
  cores:{ChatDraftsCore,ChatQueueCore,ChatScrollCore,ChatStatusCore,ChatStreamCore,ChatTranscriptCore,SafeMarkdownCore,WorkspaceContextCore},
  api:{
    historyInventory:options=>api('/api/chat/history',options), historyGet:options=>api('/api/chat/history/get',options),
    historySave:options=>api('/api/chat/history/save',options), historyUpdate:options=>api('/api/chat/history/update',options),
    historyDelete:options=>api('/api/chat/history/delete',options),
    settingsGet:options=>api('/api/chat/settings/get',options), settingsUpdate:options=>api('/api/chat/settings/update',options),
    stopResponse:options=>api('/api/chat/stop',options), checkpoint:options=>api('/api/chat/turn/checkpoint',options),
    clearCheckpoint:options=>api('/api/chat/turn/clear',options), recoverCheckpoint:options=>api('/api/chat/turn/recover',options),
    detachSurface:options=>api('/api/session/detach',options), stream:options=>launcherApi.response('/api/chat',options),
  },
  platform:{dom:document,sessionStorage,requestAnimationFrame,setTimeout,clearTimeout,matchMedia,
    reducedMotion,activeDetail,onBeforeUnload:callback=>window.addEventListener('beforeunload',callback)},
  navigation:{agentVisible:()=>agentConsoleIsVisible(),suspendAgent:()=>agentConsoleWorkspace.suspend(),
    refreshAgent:()=>updateAgentWorkspace(),refreshChrome:()=>updateWorkspaceChrome(),
    closeSessions:()=>{if($('sessionDialog').open)$('sessionDialog').close();},stopRun:()=>stopRun()},
  callbacks:{showNotice:(...args)=>showNotice(...args),copyLocalText:(...args)=>copyLocalText(...args),
    pollStatus:(...args)=>pollStatus(...args),renderCacheObservatory:(...args)=>renderCacheObservatory(...args),
    renderRequestActivity:(...args)=>renderRequestActivity(...args),renderQuickStart:(...args)=>renderQuickStart(...args),
    surfacePostmortemMarker:(...args)=>surfacePostmortemMarker(...args),sessionRouteActive:(...args)=>sessionRouteActive(...args),
    runSettingsApplied:(surfaceId,chat)=>launchWorkspace.updateOwnedChatSettings(surfaceId,chat),
    surfaceDetached:async (hub,ownerRunId)=>{if(!launchWorkspace.updateOwnedHub(hub,ownerRunId))return;launchWorkspace.invalidateAttachmentPlan();await loadSessionDashboard();}},
  formatting:{esc,formatBytes,formatNumber,backendName,profileBackendLabel},
  policy:{uiEngineVisible},review:chatResumeReview,
  session:{snapshot:()=>({phase:launchWorkspace.view().phase,status:launchWorkspace.runState()}),token:()=>state.token},
});


function renderChatResumePlan(...args) { return chatWorkspace.renderChatResumePlan(...args); }

async function openChatResumeDialog(...args) { return chatWorkspace.openChatResumeDialog(...args); }

async function completePendingChatResume(...args) { return chatWorkspace.completePendingChatResume(...args); }

async function applyChatResume(...args) { return chatWorkspace.applyChatResume(...args); }

async function recoverInterruptedChatTurn(...args) { return chatWorkspace.recoverInterruptedChatTurn(...args); }

async function loadChatHistory(...args) { return chatWorkspace.loadChatHistory(...args); }

async function openChatHistory(...args) { return chatWorkspace.openChatHistory(...args); }

async function updateChatHistoryThread(...args) { return chatWorkspace.updateChatHistoryThread(...args); }

function chatHistoryMarkdown(...args) { return chatWorkspace.chatHistoryMarkdown(...args); }

async function exportChatHistoryThread(...args) { return chatWorkspace.exportChatHistoryThread(...args); }

async function openChatHistoryThread(...args) { return chatWorkspace.openChatHistoryThread(...args); }

async function deleteChatHistoryThread(...args) { return chatWorkspace.deleteChatHistoryThread(...args); }

function updateWorkspaceChrome() {
  const agentVisible = !$("agentWorkspace").classList.contains("hidden");
  const chatVisible = !$("chatWorkspace").classList.contains("hidden");
  const hideSettings = agentVisible || chatVisible;
  for (const id of ["configScroll", "launchDock"]) {
    const element = $(id);
    if (element.classList.contains("hidden") !== hideSettings) {
      element.classList.toggle("hidden", hideSettings);
    }
  }
  const title = agentVisible ? "Agent Console" : chatVisible ? "Chat" : "Your local AI";
  if ($("configTitle").textContent !== title) $("configTitle").textContent = title;
}

function updateChatWorkspace(...args) { return chatWorkspace.updateChatWorkspace(...args); }

const agentConsoleWorkspace = LLMAgentConsoleWorkspace.createController({
  elements:Object.fromEntries([
    "agentConsoleActionsMenu", "agentConsoleBackButton", "agentConsoleCommands", "agentConsoleCompactButton", "agentConsoleContextTokens",
    "agentConsoleCopyButton", "agentConsoleCustomFrame", "agentConsoleCustomUI", "agentConsoleDraftsButton", "agentConsoleDraftsDialog",
    "agentConsoleDraftsList", "agentConsoleDraftsStatus", "agentConsoleEnterButton", "agentConsoleEscapeButton", "agentConsoleFindButton",
    "agentConsoleForm", "agentConsoleHeadingDetail", "agentConsoleInput", "agentConsoleInputLabel", "agentConsoleInteraction",
    "agentConsoleInteractionCancel", "agentConsoleInteractionInput", "agentConsoleInteractionInputWrap", "agentConsoleInteractionMessage", "agentConsoleInteractionNo",
    "agentConsoleInteractionOptions", "agentConsoleInteractionSubmit", "agentConsoleInteractionTitle", "agentConsoleInterruptButton", "agentConsoleJumpLatest",
    "agentConsoleLane", "agentConsoleLivePhase", "agentConsoleLivePhaseText", "agentConsoleLiveDetail", "agentConsoleLiveQueue",
    "agentConsoleLogButton", "agentConsoleMeta",
    "agentConsolePrefillClock", "agentConsoleQueue", "agentConsoleQueueCancel", "agentConsoleQueueEditText", "agentConsoleQueueEditor",
    "agentConsoleQueueMessages", "agentConsoleQueueSave", "agentConsoleQueueSummary", "agentConsoleQueueWarning", "agentConsoleRestartButton",
    "agentConsoleRoute", "agentConsoleSearch", "agentConsoleSearchClose", "agentConsoleSearchInput", "agentConsoleSearchNext",
    "agentConsoleSearchPrevious", "agentConsoleSearchStatus", "agentConsoleSessionsButton", "agentConsoleStatus", "agentConsoleStatusContextValue",
    "agentConsoleStatusDisclosureLabel", "agentConsoleStatusLane", "agentConsoleStatusLaneValue", "agentConsoleStatusModel", "agentConsoleStatusPanel",
    "agentConsoleStatusPromptValue", "agentConsoleStatusSpeed", "agentConsoleStatusSpeedValue", "agentConsoleStatusState", "agentConsoleStatusSummary",
    "agentConsoleStatusSurface", "agentConsoleSteerButton", "agentConsoleStopButton", "agentConsoleTabs", "agentConsoleTitle",
    "agentConsoleTps", "agentConsoleTtft", "agentPiTimeline", "agentPiTimelineEmpty", "agentPiTimelineJumpLatest",
    "agentPiTimelineViewport", "agentTerminalOutput", "agentTerminalViewport", "agentWorkspace", "hubFanMessage",
    "hubFanMode", "agentConsoleStatusPrompt", "agentConsoleStatusPromptValue", "agentConsoleStatusContext", "agentConsoleStatusContextValue",
  ].map(id => [id, $(id)])),
  endpoints:{read:body => api("/api/agent-console/read", {method:"POST",body:JSON.stringify(body)}),
    input:body => api("/api/agent-console/input", {method:"POST",body:JSON.stringify(body)}),
    resize:body => api("/api/agent-console/resize", {method:"POST",body:JSON.stringify(body)}),
    stop:body => api("/api/agent-console/stop", {method:"POST",body:JSON.stringify(body)}),
    restart:body => api("/api/agent-console/restart", {method:"POST",body:JSON.stringify(body)}),
    fans:body => api("/api/hub/fans", {method:"POST",body:JSON.stringify(body)})},
  navigation:{beforeShow:() => !$("chatWorkspace").classList.contains("hidden")
      ? saveChatBeforeSurfaceExit("open that Hub Console again") : true,
    refreshChat:updateChatWorkspace, updateChrome:updateWorkspaceChrome,
    setConsoleVisible:visible => { if (visible) $("chatWorkspace").classList.add("hidden"); return !$("chatWorkspace").classList.contains("hidden"); },
    setSubtitle:label => { $("configSubtitle").textContent = label; }, showSettings:updateWorkSurface,
    closeSessions:() => { if ($("sessionDialog")?.open) $("sessionDialog").close(); },
    refreshSessions:async () => { if ($("sessionDialog")?.open) await loadSessionDashboard(); },
    showLog, openSessions:openSessionDashboard},
  onHubStatus:(hub,ownerRunId)=>launchWorkspace.updateOwnedHub(hub,ownerRunId),
  activitySnapshot:() => launchWorkspace.activity() || {}, storage:sessionStorage,
  copyText:text => navigator.clipboard.writeText(text), alertUser:message => window.alert(message), notify:showNotice,
  sessionRouteActive, surfacePostmortemMarker, backendName, clientName, formatBytes, formatNumber,
  formatShortDuration, formatTimestamp:formatChatTimestamp, liveRequestPhaseLabel, liveRequestDetail,
  cores:{TerminalCore, AgentConsoleTabsCore, AgentConsoleInputCore, ChatDraftsCore, PiTimelineCore,
    ChatStatusCore, UiPresenter, timelineViewFactory:globalThis.LLMPiTimelineView.createTimelineView},
});
function agentConsoleIsVisible() { return agentConsoleWorkspace.isVisible(); }
function currentAgentConsoleView() { return agentConsoleWorkspace.currentView(); }
function syncAgentConsoleViews(status, run = status?.run, phase = status?.phase || launchWorkspace.view().phase) { return agentConsoleWorkspace.observe(status, run, phase); }
function updateAgentWorkspace(run, phase) { return agentConsoleWorkspace.update(run, phase); }
function enterAgentConsole(attachment) { return agentConsoleWorkspace.enter(attachment); }
function selectAgentConsole(surfaceId = agentConsoleWorkspace.currentSurfaceId(), options) { return agentConsoleWorkspace.select(surfaceId, options); }
function leaveAgentConsole() { return agentConsoleWorkspace.leave(); }
function scheduleAgentConsoleRead() { agentConsoleWorkspace.wake(); }
function resetAgentConsoleTerminal() { agentConsoleWorkspace.resetTerminal(); }
function stopAgentConsoleSurface(attachment) { return agentConsoleWorkspace.stop(attachment); }
function restartAgentConsoleSurface(attachment) { return agentConsoleWorkspace.restart(attachment); }

function renderFocusedRunStatus(...args) { return launchWorkspace.renderFocusedRunStatus(...args); }

function renderRun(...args) { return launchWorkspace.renderRun(...args); }

const pollStatus = (...args) => launchWorkspace.pollStatus(...args);

function benchmarkHistoryRequest(...args) { return benchmarkWorkspace.benchmarkHistoryRequest(...args); }

function benchmarkHistoryRequestKey(...args) { return benchmarkWorkspace.benchmarkHistoryRequestKey(...args); }

function benchmarkHistoryDate(...args) { return benchmarkWorkspace.benchmarkHistoryDate(...args); }

function benchmarkHistorySparkline(...args) { return benchmarkWorkspace.benchmarkHistorySparkline(...args); }

function renderBenchmarkHistory(...args) { return benchmarkWorkspace.renderBenchmarkHistory(...args); }

async function loadBenchmarkHistory(...args) { return benchmarkWorkspace.loadBenchmarkHistory(...args); }

function scheduleBenchmarkHistory(...args) { return benchmarkWorkspace.scheduleBenchmarkHistory(...args); }

function benchmarkDisplayedStatus(...args) { return benchmarkWorkspace.benchmarkDisplayedStatus(...args); }

async function reviewBenchmarkResult(...args) { return benchmarkWorkspace.reviewBenchmarkResult(...args); }

function performanceReceiptSuite(...args) { return launchWorkspace.performanceReceiptSuite(...args); }

function calibrationSuiteControlValue(...args) { return benchmarkWorkspace.calibrationSuiteControlValue(...args); }

function performanceReceiptSuiteOrder(...args) { return launchWorkspace.performanceReceiptSuiteOrder(...args); }

function performanceReceiptNeedsFallback(...args) { return launchWorkspace.performanceReceiptNeedsFallback(...args); }

function performanceReceiptSuiteLabel(...args) { return launchWorkspace.performanceReceiptSuiteLabel(...args); }

function performanceReceiptRequest(...args) { return launchWorkspace.performanceReceiptRequest(...args); }

function performanceReceiptRequestKey(...args) { return launchWorkspace.performanceReceiptRequestKey(...args); }

function performanceReceiptAge(...args) { return launchWorkspace.performanceReceiptAge(...args); }

function performanceReceiptView(...args) { return launchWorkspace.performanceReceiptView(...args); }

function renderEngineEvidenceChoices(...args) { return launchWorkspace.renderEngineEvidenceChoices(...args); }

function renderPerformanceReceipt(...args) { return launchWorkspace.renderPerformanceReceipt(...args); }

async function loadPerformanceReceipt(...args) { return launchWorkspace.loadPerformanceReceipt(...args); }

function schedulePerformanceReceipt(...args) { return launchWorkspace.schedulePerformanceReceipt(...args); }

async function openPerformanceBenchmarkLab(...args) { return benchmarkWorkspace.openPerformanceBenchmarkLab(...args); }

async function activatePerformanceReceipt(...args) { return launchWorkspace.activatePerformanceReceipt(...args); }

function benchmarkSuiteChanged(...args) { return benchmarkWorkspace.benchmarkSuiteChanged(...args); }

function benchmarkPreferenceChanged(...args) { return benchmarkWorkspace.benchmarkPreferenceChanged(...args); }

function engineShootoutApplyBinding(...args) { return benchmarkWorkspace.engineShootoutApplyBinding(...args); }

function renderEngineShootoutResults(...args) { return benchmarkWorkspace.renderEngineShootoutResults(...args); }

function renderMtpTuningResults(...args) { return benchmarkWorkspace.renderMtpTuningResults(...args); }

function renderDflashTuningResults(...args) { return benchmarkWorkspace.renderDflashTuningResults(...args); }

function benchmarkRouteApplyBinding(...args) { return benchmarkWorkspace.benchmarkRouteApplyBinding(...args); }

async function applyBenchmarkRouteResult(...args) { return benchmarkWorkspace.applyBenchmarkRouteResult(...args); }

function benchmarkResultRecommendation(...args) { return benchmarkWorkspace.benchmarkResultRecommendation(...args); }

function renderBenchmarkResults(...args) { return benchmarkWorkspace.renderBenchmarkResults(...args); }

function renderBenchmarkLiveTps(...args) { return benchmarkWorkspace.renderBenchmarkLiveTps(...args); }

function renderBenchmarkStatus(...args) { return benchmarkWorkspace.renderBenchmarkStatus(...args); }

const pollBenchmarkStatus = (...args) => benchmarkWorkspace.pollBenchmarkStatus(...args);

async function openBenchmarkLab(...args) { return benchmarkWorkspace.openBenchmarkLab(...args); }

async function startBenchmark(...args) { return benchmarkWorkspace.startBenchmark(...args); }

async function stopBenchmark(...args) { return benchmarkWorkspace.stopBenchmark(...args); }

function calibrationBenchmarkActive(...args) { return benchmarkWorkspace.calibrationBenchmarkActive(...args); }

function calibrationOwnsBenchmark(...args) { return benchmarkWorkspace.calibrationOwnsBenchmark(...args); }

function calibrationOperationBlocked(...args) { return benchmarkWorkspace.calibrationOperationBlocked(...args); }

function calibrationMeasurementAdmission(...args) { return benchmarkWorkspace.calibrationMeasurementAdmission(...args); }

function calibrationQualificationProfile(...args) { return benchmarkWorkspace.calibrationQualificationProfile(...args); }

function llamaQualificationContractExact(...args) { return benchmarkWorkspace.llamaQualificationContractExact(...args); }

function uzuQualificationContractExact(...args) { return benchmarkWorkspace.uzuQualificationContractExact(...args); }

function routeQualificationContractExact(...args) { return benchmarkWorkspace.routeQualificationContractExact(...args); }

function firstQualificationMetric(...args) { return benchmarkWorkspace.firstQualificationMetric(...args); }

function firstQualificationCheck(...args) { return benchmarkWorkspace.firstQualificationCheck(...args); }

function routeQualificationResultMetrics(...args) { return benchmarkWorkspace.routeQualificationResultMetrics(...args); }

function routeQualificationFactsMarkup(...args) { return benchmarkWorkspace.routeQualificationFactsMarkup(...args); }

function updateCalibrationHelp(...args) { return benchmarkWorkspace.updateCalibrationHelp(...args); }

function calibrationPlanRequest(...args) { return benchmarkWorkspace.calibrationPlanRequest(...args); }

function calibrationStateBadge(...args) { return benchmarkWorkspace.calibrationStateBadge(...args); }

function renderCalibrationEntry(...args) { return benchmarkWorkspace.renderCalibrationEntry(...args); }

function completedCalibrationDecision(...args) { return benchmarkWorkspace.completedCalibrationDecision(...args); }

function completedCalibrationEvidenceBinding(...args) { return benchmarkWorkspace.completedCalibrationEvidenceBinding(...args); }

function promoteCompletedCalibrationResult(...args) { return benchmarkWorkspace.promoteCompletedCalibrationResult(...args); }

function calibrationParityRejectionNote(...args) { return benchmarkWorkspace.calibrationParityRejectionNote(...args); }

function calibrationRoutePreview(...args) { return benchmarkWorkspace.calibrationRoutePreview(...args); }

function calibrationAlternativeMarkup(...args) { return benchmarkWorkspace.calibrationAlternativeMarkup(...args); }

function renderCalibrationPlan(...args) { return benchmarkWorkspace.renderCalibrationPlan(...args); }

function renderCalibrationBenchmark(...args) { return benchmarkWorkspace.renderCalibrationBenchmark(...args); }

function renderCalibration(...args) { return benchmarkWorkspace.renderCalibration(...args); }

async function loadCalibrationPlan(...args) { return benchmarkWorkspace.loadCalibrationPlan(...args); }

async function openCalibrationAssistant(...args) { return benchmarkWorkspace.openCalibrationAssistant(...args); }

async function selectCalibrationAlternative(...args) { return benchmarkWorkspace.selectCalibrationAlternative(...args); }

async function prepareQwenRouteQualification(...args) { return benchmarkWorkspace.prepareQwenRouteQualification(...args); }

async function startCalibration(...args) { return benchmarkWorkspace.startCalibration(...args); }

async function stopCalibration(...args) { return benchmarkWorkspace.stopCalibration(...args); }

function calibrationRouteEvidenceApplyReady(...args) { return benchmarkWorkspace.calibrationRouteEvidenceApplyReady(...args); }

async function applyCalibrationResult(...args) { return benchmarkWorkspace.applyCalibrationResult(...args); }

function completedCalibrationMatchesOptimizerChoice(...args) { return benchmarkWorkspace.completedCalibrationMatchesOptimizerChoice(...args); }


const benchmarkWorkspace = LLMBenchmarkWorkspace.createController({
  nodes:Object.fromEntries(LLMBenchmarkWorkspace.nodeIds.map(id=>[id,$(id)])),
  decision:CalibrationDecision,preferenceLabels:enginePreferenceLabels,
  policy:{LLAMACPP_PLE_QUALIFICATION_ANSWER_RESERVE_TOKENS,LLAMACPP_PLE_QUALIFICATION_CONTEXT,LLAMACPP_PLE_QUALIFICATION_CONTRACT_ID,LLAMACPP_PLE_QUALIFICATION_CONTRACT_VERSION,LLAMACPP_PLE_QUALIFICATION_MEMORY_LIMIT_BYTES,LLAMACPP_PLE_QUALIFICATION_MINIMUM_COMPLETION_TOKENS,LLAMACPP_PLE_QUALIFICATION_MINIMUM_TPS,LLAMACPP_PLE_QUALIFICATION_REASONING_BOUNDARY_ID,LLAMACPP_PLE_QUALIFICATION_REASONING_MESSAGE_SHA256,LLAMACPP_PLE_QUALIFICATION_SAMPLE_MAX_TOKENS,LLAMACPP_PLE_QUALIFICATION_SCENARIOS,LLAMACPP_PLE_QUALIFICATION_SUITE,LLAMACPP_PLE_QUALIFICATION_THINKING_TOKENS,MTPLX_LONG_CONTEXT_SUITE,UZU_NATIVE_BOUNDARY_CONTRACT_ID,UZU_QUALIFICATION_ANSWER_RESERVE_TOKENS,UZU_QUALIFICATION_CONTEXTS,UZU_QUALIFICATION_CONTRACT_VERSION,UZU_QUALIFICATION_MEMORY_LIMIT_BYTES,UZU_QUALIFICATION_MINIMUM_COMPLETION_TOKENS,UZU_QUALIFICATION_MINIMUM_TPS,UZU_QUALIFICATION_OS_RESERVE_MINIMUM_BYTES,UZU_QUALIFICATION_SAMPLE_MAX_TOKENS,UZU_QUALIFICATION_SAMPLE_MIN_TOKENS,UZU_QUALIFICATION_SCENARIOS,UZU_RUNTIME_RELEASE_BINARY_SHA256,UZU_RUNTIME_RELEASE_BINARY_SIZE,UZU_RUNTIME_SOURCE_PATCH_SHA256,UZU_RUNTIME_UPSTREAM_COMMIT},
  platform:{setTimeout,clearTimeout},
  network:{history:options=>api('/api/benchmark/history',options),start:options=>api('/api/benchmark/start',options),
    stop:options=>api('/api/benchmark/stop',options),plan:options=>api('/api/calibration/plan',options),
    saveProfile:options=>api('/api/profiles/save',options),status:()=>api('/api/benchmark/status')},
  polling:{register:task=>statusPoller.add('benchmark',task),interval:(active,_dialogOpen)=>statusPollInterval(active,'benchmarkDialog')},
  formatting:{esc:(...args)=>esc(...args),
    formatBytes:(...args)=>formatBytes(...args),
    formatNumber:(...args)=>formatNumber(...args),
    finiteMetric:(...args)=>finiteMetric(...args),
    backendName:(...args)=>backendName(...args),
    clientName:(...args)=>clientName(...args),
    exactContextTier:(...args)=>exactContextTier(...args)},
  capabilities:{selectedModel:(...args)=>selectedModel(...args),
    visibleEngineAdapters:(...args)=>visibleEngineAdapters(...args),
    backendBinaryKey:(...args)=>backendBinaryKey(...args),
    resolvedClientSupport:(...args)=>resolvedClientSupport(...args),
    uiEngineVisible:(...args)=>uiEngineVisible(...args),
    freeTokenRoute:(...args)=>freeTokenRoute(...args),
    mtplxLongContextCapabilityExact:(...args)=>mtplxLongContextCapabilityExact(...args),
    llamaCppPleCapabilityQualified:(...args)=>llamaCppPleCapabilityQualified(...args),
    llamaCppPleQualified:(...args)=>llamaCppPleQualified(...args),
    selectedRouteQualificationBackend:(...args)=>selectedRouteQualificationBackend(...args),
    controllerRouteQualificationBackend:(...args)=>controllerRouteQualificationBackend(...args),
    uzuQualificationSuite:(...args)=>uzuQualificationSuite(...args),
    uzuQualificationContractId:(...args)=>uzuQualificationContractId(...args),
    uzuQualificationPromptExercisePolicyExact:(...args)=>uzuQualificationPromptExercisePolicyExact(...args),
    isUzuQualificationSuite:(...args)=>isUzuQualificationSuite(...args),runtimeInstalled:key=>Boolean(state.binaries?.[key]?.installed)},
  settings:{gather:(...args)=>gather(...args),
    runtimeKvValue:(...args)=>runtimeKvValue(...args),
    setRuntimeKvValue:(...args)=>setRuntimeKvValue(...args),
    cancelOptimization:(...args)=>cancelOptimization(...args),
    setRangeVisual:(...args)=>setRangeVisual(...args),
    updateAccelerationState:(...args)=>updateAccelerationState(...args),
    refreshLaunchability:(...args)=>refreshLaunchability(...args),
    persistVisibleRoute:(...args)=>persistVisibleRoute(...args),
    updateBackend:(...args)=>updateBackend(...args),
    modelChanged:(...args)=>modelChanged(...args),snapshot:()=>({backend:launchWorkspace.view().backend,client:launchWorkspace.view().client,optimalLabel:launchWorkspace.view().optimalLabel}),
    selectBackend:backend=>{launchWorkspace.setBackend(backend);updateBackend(true);},resetSessionAcknowledgement:()=>{launchWorkspace.resetAcknowledgement();}},
  evidence:{copiedEvidenceBinding:(...args)=>copiedEvidenceBinding(...args),
    activeEvidenceBindingFor:(...args)=>activeEvidenceBindingFor(...args),
    applyOptimal:(...args)=>applyOptimal(...args)},
  operations:{acquisitionIsActive:(...args)=>acquisitionIsActive(...args),
    routeCheckIsActive:(...args)=>routeCheckIsActive(...args),
    aneWorkIsActive:(...args)=>aneWorkIsActive(...args),
    currentSessionAdmission:(...args)=>currentSessionAdmission(...args),
    sessionAdmissionDecision:(...args)=>sessionAdmissionDecision(...args),
    sessionAdmissionBlockerCopy:(...args)=>sessionAdmissionBlockerCopy(...args),
    requireFreshSessionAdmission:(...args)=>requireFreshSessionAdmission(...args),snapshot:()=>({runPhase:launchWorkspace.view().phase,setupPhase:state.setupPhase}),profileBusy:()=>profilesManager.isBusy()},
  effects:{showNotice:(...args)=>showNotice(...args),
    pollStatus:(...args)=>pollStatus(...args),
    loadModels:(...args)=>loadModels(...args),
    useProfileInventory:(...args)=>useProfileInventory(...args),
    activeDetail:(...args)=>activeDetail(...args),
    closeOptimizerMenu:(...args)=>closeOptimizerMenu(...args)},
  receipt:{performanceReceiptSuite:(...args)=>performanceReceiptSuite(...args),
    loadPerformanceReceipt:(...args)=>loadPerformanceReceipt(...args),
    schedulePerformanceReceipt:(...args)=>schedulePerformanceReceipt(...args),current:()=>structuredClone(launchWorkspace.receipt())},
});

async function applyOptimizerMenuChoice(...args) { return launchWorkspace.applyOptimizerMenuChoice(...args); }

function sessionDecisionClass(...args) { return launchWorkspace.sessionDecisionClass(...args); }

function sessionProjectedLabel(...args) { return launchWorkspace.sessionProjectedLabel(...args); }

function sessionAttachmentRequest(...args) { return launchWorkspace.sessionAttachmentRequest(...args); }

function syncSessionAttachmentForm(...args) { return launchWorkspace.syncSessionAttachmentForm(...args); }

function renderSessionAttachmentPanel(...args) { return launchWorkspace.renderSessionAttachmentPanel(...args); }

async function cancelSessionRequest(...args) { return launchWorkspace.cancelSessionRequest(...args); }

async function stopChatResponse(...args) { return chatWorkspace.stopChatResponse(...args); }

async function setSessionIdlePolicy(...args) { return launchWorkspace.setSessionIdlePolicy(...args); }

function scheduleSessionAttachmentPlan(...args) { return launchWorkspace.scheduleSessionAttachmentPlan(...args); }

async function loadSessionAttachmentPlan(...args) { return launchWorkspace.loadSessionAttachmentPlan(...args); }

async function enterChatSurface(...args) { return chatWorkspace.enterChatSurface(...args); }

async function attachSessionSurface(...args) { return launchWorkspace.attachSessionSurface(...args); }

async function detachChatSurface(...args) { return chatWorkspace.detachChatSurface(...args); }

async function endCurrentChatSurface(...args) { return chatWorkspace.endCurrentChatSurface(...args); }

function renderSessionDashboard(...args) { return launchWorkspace.renderSessionDashboard(...args); }

async function loadSessionDashboard(...args) { return launchWorkspace.loadSessionDashboard(...args); }

async function openSessionDashboard(...args) { return launchWorkspace.openSessionDashboard(...args); }

async function stopSessionFromDashboard(...args) { return launchWorkspace.stopSessionFromDashboard(...args); }

function setupIsActive() {
  return ["queued","downloading","stopping","verifying"].includes(state.setupPhase);
}

function updateSetupControls() {
  const plan = state.setupPlan;
  const active = setupIsActive();
  const runActive = ["preflight","starting","running","stopping"].includes(launchWorkspace.view().phase);
  const benchmarkActive = ["queued","cooldown","starting","running","stopping"].includes(benchmarkWorkspace.view().phase);
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
    if (launchWorkspace.runState()) renderRun(launchWorkspace.runState());
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
  if (launchWorkspace.runState()) renderRun(launchWorkspace.runState());
  else refreshLaunchability();
  const completedId = status.phase === "completed" ? status.plan?.id : "";
  if (completedId && state.setupCompletionId !== completedId) {
    state.setupCompletionId = completedId;
    loadModels(false).then(() => {
      if ($("setupDialog").open) loadSetupPlan();
    }).catch(() => {});
  }
}

const pollSetupStatus = statusPoller.add("setup", {
  interval:() => statusPollInterval(setupIsActive(), "setupDialog"),
  run:async () => {
    try { renderSetupStatus(await api("/api/setup/status")); } catch (_) {}
  },
});

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
  const runActive = ["preflight","starting","running","stopping"].includes(launchWorkspace.view().phase);
  const benchmarkActive = ["queued","cooldown","starting","running","stopping"].includes(benchmarkWorkspace.view().phase);
  const setupActive = setupIsActive();
  const blockedByOtherWork = cloneActive || benchmarkActive || setupActive || acquisitionIsActive() || routeCheckIsActive() || runtimeUpdateIsActive() || runtimePromotionIsActive() || (runActive && !active);
  const canStart = Boolean(launchWorkspace.view().backend === "omlx" && model && readiness.ready && !active && !blockedByOtherWork);
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
  if (launchWorkspace.runState()) renderRun(launchWorkspace.runState());
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

const pollAneStatus = statusPoller.add("ane", {
  interval:() => statusPollInterval(aneIsActive(), "aneDialog"),
  run:async () => {
    try { renderAneStatus(await api("/api/ane/status")); } catch (_) {}
  },
});

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
  const runActive = ["preflight","starting","running","stopping"].includes(launchWorkspace.view().phase);
  const otherActive = runActive || tunerActive || setupIsActive() || acquisitionIsActive()
    || routeCheckIsActive() || ["queued","cooldown","starting","running","stopping"].includes(benchmarkWorkspace.view().phase)
    || runtimeUpdateIsActive() || runtimePromotionIsActive();
  const inspectable = Boolean(launchWorkspace.view().backend === "omlx" && model && (
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
  if (launchWorkspace.runState()) renderRun(launchWorkspace.runState());
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

const pollAneCloneStatus = statusPoller.add("aneClone", {
  interval:() => statusPollInterval(aneCloneIsActive(), "aneCloneDialog"),
  run:async () => {
    try { renderAneCloneStatus(await api("/api/ane/clone/status")); } catch (_) {}
  },
});

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
    const model = launchWorkspace.catalog().find(item => item.path === path && item.backends?.omlx?.runnable);
    if (!model) throw new Error("The verified copy is not selectable yet. Rescan models after its folder is visible to the launcher.");
    if (!launchWorkspace.selectModelRoute(model.id, "omlx")) {
      throw new Error("The verified copy is not selectable on oMLX.");
    }
    $("aneAdvanced").open = true;
    $("aneCloneDialog").close();
    showNotice("The verified FP16 copy is selected. CPU-sharing candidates are now available inside the ANE Tuner; nothing has started.");
  } catch (error) { $("aneCloneStatus").textContent = error.message; }
}

async function showLog(...args) { return launchWorkspace.showLog(...args); }
async function stopRun(...args) { return launchWorkspace.stopRun(...args); }

function profileRunBlocked() { return profilesManager.runBlocked(); }
function profileSettingsBlockReason() { return profilesManager.settingsBlockReason(); }
function profileLaunchBlockReason() { return profilesManager.launchBlockReason(); }
function renderProfileRunNotice() { profilesManager.renderRunNotice(); }
function renderProfileEditBanner() { profilesManager.renderEditBanner(); }

function profileBackendLabel(backend) {
  return backend ? backendName(backend) : "Unknown engine";
}

function measuredProfileEvidenceBinding(profile = {}) { return profilesManager.measuredBinding(profile); }
function profileUiReady(profile = {}) { return profilesManager.isReady(profile); }
function profileUiReason(profile = {}) { return profilesManager.reason(profile); }

function requestUsesExperimentalFreeToken(request = {}) {
  if (request.backend !== "freetoken") return false;
  const model = launchWorkspace.catalog().find(item => item.id === request.modelId);
  return freeTokenRoute(model) === "native" && freeTokenQualification(model).experimental;
}

function quickStartEntries() { return profilesManager.shortcutEntries(); }
function renderQuickStart() { profilesManager.renderShortcuts(); }

function setQuickStartEditor(open, scroll = false) {
  if (open && launchWorkspace.catalog().length) updateWorkSurface();
  if (scroll && open) requestAnimationFrame(() => {
    $("customLaunchEditor").scrollIntoView({behavior:"smooth", block:"start"});
  });
}

function toggleQuickStartRoutes() { profilesManager.toggleShortcuts(); }
function loadQuickStart(force = false) { return profilesManager.loadShortcuts(force); }

async function reviewQuickSessionSet(setId) {
  if (sessionSetsManager.isBlocked()) return;
  await openSessionSetManager();
  if (!sessionSetsManager.hasReadySet(setId)) {
    setSessionSetMessage("That saved workspace is no longer ready. Review its current status below.", "error");
    return;
  }
  await planSessionSet(setId);
}

function profileDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Saved locally" : `Updated ${date.toLocaleDateString([], {month:"short", day:"numeric"})}`;
}

function setProfileStatus(message, kind = "") { profilesManager.message(message, kind); }
function rememberAppliedProfile(profile = null) { profilesManager.remember(profile); }
function useProfileInventory(data) { profilesManager.useInventory(data); }
function updateProfilePolicyControls() { profilesManager.updateControls(); }
function renderProfiles() { profilesManager.render(); }
function loadProfiles() { return profilesManager.load(); }
function openProfileManager() { return profilesManager.show(); }
function resetProfileEditor(clearName = true) { profilesManager.resetEditor(clearName); }
function editProfile(profileId) { return profilesManager.edit(profileId); }

function setProfileSelect(...args) { return launchWorkspace.setProfileSelect(...args); }

function applyProfileRequest(...args) { return launchWorkspace.applyProfileRequest(...args); }

async function applySavedProfile(profileId, launchAfter = false, editAfter = false) { return profilesManager.apply(profileId, launchAfter, editAfter); }
async function saveCurrentProfile() { return profilesManager.save(); }
async function deleteSavedProfile(profileId) { return profilesManager.remove(profileId); }

function profileExternalSettingsReason() {
  if (launchWorkspace.view().applyingOptimal || benchmarkWorkspace.view().calibrationApplying) return "Wait for the settings update to finish.";
  if (launchWorkspace.view().launchPreparing || state.verifiedLaunchBusy || benchmarkWorkspace.view().calibrationStarting) return "Wait for launch preparation to finish.";
  return "";
}
function profileExternalLaunchReason() {
  if (["preflight","starting","running","stopping"].includes(launchWorkspace.view().phase)) return "A model session is already open. You can apply or edit settings for your next launch. End the current session in Sessions before launching a profile.";
  if (["queued","starting","running","stopping"].includes(state.routeCheckPhase)) return "A route check is running. Launch is available when it finishes.";
  if (["queued","cooldown","starting","running","stopping"].includes(benchmarkWorkspace.view().phase)) return "A benchmark is running. Launch is available when it finishes.";
  if (["queued","downloading","stopping","verifying"].includes(state.setupPhase) || acquisitionIsActive()) return "Model setup is in progress. Launch is available when it finishes.";
  if (aneWorkIsActive()) return "Engine tuning is in progress. Launch is available when it finishes.";
  return "";
}

const profilesManager = LLMSavedLaunches.createController({
  elements:Object.fromEntries([
    "openProfileManager", "profileDialog", "profileRunNotice", "profileRunMessage", "profileRunAction",
    "profileEditBanner", "profileEditName", "profileEditSave", "profileEditCancel", "profileEditStatus",
    "profileManagerStatus", "profileName", "profilePolicySelect", "profileGoalSelect", "profileGoalField",
    "profilePolicyHelp", "profileSaveButton", "profileSaveForm", "profileNameHint", "profileCancelEdit",
    "profileCountBadge", "profileCards", "quickStart", "quickStartSummary", "quickStartCustom",
    "quickStartCards", "quickStartStatus", "customLaunchEditor", "launchDock",
  ].map(id => [id, $(id)])),
  api:{
    inventory:() => api("/api/profiles"),
    save:body => api("/api/profiles/save", {method:"POST",body:JSON.stringify(body)}),
    remove:body => api("/api/profiles/delete", {method:"POST",body:JSON.stringify(body)}),
    sessionSets:() => api("/api/session-sets"), history:() => api("/api/chat/history"),
  },
  visible:uiProfileVisible, externalSettingsReason:profileExternalSettingsReason,
  externalLaunchReason:profileExternalLaunchReason,
  sessionActive:() => ["preflight","starting","running","stopping"].includes(launchWorkspace.view().phase),
  currentRoute:currentVisibleRoute, routeKey:RoutePreferenceCore.routeKey, selectedRequest:() => gather("custom"),
  applyRequest:applyProfileRequest, launchVisible:() => launch(),
  copyEvidence:copiedEvidenceBinding, activeEvidence:activeEvidenceBindingFor,
  applyEvidence:(scope, preference, binding) => applyOptimal(scope, preference, false, binding),
  backendLabel:profileBackendLabel, clientName, dateLabel:profileDate, formatNumber,
  kvLabel:runtimeKvLabel, preferenceLabels:enginePreferenceLabels, isExperimental:requestUsesExperimentalFreeToken,
  needsExperimentalConsent:freeTokenExperimentalConsentRequired, storage:themeStorage,
  restoreProject:project => { $("projectPath").value = project; refreshLaunchability(); },
  refreshControls:refreshLaunchability, openEditor:() => setQuickStartEditor(true),
  openEditSettings:() => { $("launchSettings").open = true; },
  revealSettings:() => { if (agentConsoleIsVisible()) leaveAgentConsole(); },
  focusSettings:editing => {
    $(editing ? "profileEditBanner" : "customLaunchEditor").scrollIntoView({behavior:"smooth", block:"start"});
    if (editing) $("reasoningSelect").focus({preventScroll:true});
  },
  revealExperimental:() => {
    $("advancedControls").open = true;
    requestAnimationFrame(() => { $("freeTokenQualificationPanel").scrollIntoView({behavior:"smooth",block:"center"}); $("freeTokenExperimentalConsent").focus(); });
  },
  openSessions:openSessionDashboard,
  shortcutContext:() => {
    const item = [...chatWorkspace.threads()].filter(chat => chat.resumeAvailable && uiEngineVisible(chat.backend))
      .sort((left,right) => Date.parse(right.updatedAt || 0) - Date.parse(left.updatedAt || 0))[0];
    return {sessionSet:sessionSetsManager.readySet(), sessionBlocked:sessionSetsManager.isBlocked(),
      chat:item ? {id:item.id,title:item.title,model:item.model,backend:item.backend,resumeNeedsSystemPrompt:item.resumeNeedsSystemPrompt} : null,
      chatBlocked:Boolean(chatResumeReview.isStarting() || chatWorkspace.view().historyBusy),
      chatActive:launchWorkspace.view().phase === "running" && Boolean(chatWorkspace.view().surfaceId)};
  },
  acceptSessionSets:useSessionSetInventory, acceptHistory:data => { chatWorkspace.useThreads(data.threads); },
  reviewSessionSet:reviewQuickSessionSet,
  openChatShortcut:id => launchWorkspace.view().phase === "running" && chatWorkspace.view().surfaceId ? openChatHistoryThread(id) : openChatResumeDialog(id),
  notify:showNotice,
});

const sessionSetsManager = LLMSessionSets.createController({
  elements:Object.fromEntries([
    "openSessionSets",
    "sessionSetDialog",
    "sessionSetStatus",
    "sessionSetPlanPanel",
    "sessionSetOpenButton",
    "sessionSetStopButton",
    "sessionSetConsentPanel",
    "sessionSetPlanWarning",
    "sessionSetPlanTitle",
    "sessionSetPlanState",
    "sessionSetPlanDetail",
    "sessionSetPlanFacts",
    "sessionSetConsentTitle",
    "sessionSetConsentCopy",
    "sessionSetConsent",
    "sessionSetCountBadge",
    "sessionSetSaveSummary",
    "sessionSetName",
    "sessionSetSaveButton",
    "sessionSetCancelEdit",
    "sessionSetCards",

  ].map(id => [id, $(id)])),
  api:{
    inventory:() => api("/api/session-sets"),
    status:() => api("/api/session-sets/status"),
    save:body => api("/api/session-sets/save-active", {method:"POST",body:JSON.stringify(body)}),
    remove:body => api("/api/session-sets/delete", {method:"POST",body:JSON.stringify(body)}),
    plan:body => api("/api/session-sets/plan", {method:"POST",body:JSON.stringify(body)}),
    open:body => api("/api/session-sets/open", {method:"POST",body:JSON.stringify(body)}),
    stop:() => api("/api/session-sets/stop", {method:"POST",body:"{}"}),
  },
  workspace:() => {
    const run = launchWorkspace.runState()?.run;
    if (launchWorkspace.view().phase !== "running" || run?.purpose !== "session" || !uiEngineVisible(run.backend)) return null;
    return {run:{runId:run.runId,backend:run.backend,model:run.model},
      surfaceCount:Math.max(1, Array.isArray(launchWorkspace.runState()?.attachments) ? launchWorkspace.runState().attachments.length : 0)};
  },
  visible:uiSessionSetVisible, backendLabel:profileBackendLabel, formatNumber, dateLabel:profileDate,
  experimental:requestUsesExperimentalFreeToken, canApply:() => !profileRunBlocked(),
  applyPrimary:applyProfileRequest, openEditor:() => setQuickStartEditor(true),
  notify:showNotice, refreshRoute:() => pollStatus(), onChange:renderQuickStart,
});
function sessionSetIsActive(status) { return status === undefined ? sessionSetsManager.isActive() : sessionSetsManager.isActive(status); }
function setSessionSetMessage(message, kind = "") { sessionSetsManager.message(message, kind); }
function useSessionSetInventory(data) { sessionSetsManager.useInventory(data); }
function renderSessionSets() { sessionSetsManager.render(); }
function openSessionSetManager() { return sessionSetsManager.show(); }
function planSessionSet(setId) { return sessionSetsManager.review(setId); }
function loadSessionSetStatus(announceFinished = true) { return sessionSetsManager.refreshStatus(announceFinished); }

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
  applyUiFeatureVisibility();
  if (boot.clientSupport) state.clientSupport = boot.clientSupport;
  if (boot.freeToken) launchWorkspace.useFreeTokenFacts(boot.freeToken);
  const binaries = Object.entries(state.binaries).filter(([name]) => (
    uiFeatureEnabled("freetoken") || !String(name).startsWith("freetoken")
  ));
  const binaryLabels = {kolibri:"Kolibri SSD", lms:"LM Studio", mirai:"Uzu · Mirai", hf:"Model downloader", freetoken:"FreeToken", swiftlm:"SwiftLM", mference:"Mference", whallm:"Whallm", slotstream:"Slotstream", splash:"Splash", strata:"Strata", rec:"Rec", llamacpp:"llama.cpp · SSD PLE", rapidmlx:"Rapid MLX"};
  $("toolCount").textContent = `${binaries.filter(([,value]) => value.installed).length}/${binaries.length} ready`;
  $("binaryList").innerHTML = binaries.map(([name, value]) => `<div class="binary ${value.installed ? "" : "missing"}"><div><strong>${esc(binaryLabels[name] || name)}</strong><span title="${esc(value.path || "")}">${esc(value.version)}</span></div><em>${value.installed ? "Ready" : "Missing"}</em><i aria-hidden="true"></i></div>`).join("");
  if (setProject && !$("projectPath").value) {
    $("projectPath").value = boot.roots?.find(root => root.label === "Documents")?.path?.replace(/\/models$/i, "/Code") || "";
  }
  renderFreeTokenConnection();
}

function acquisitionOtherOperationActive() {
  return ["preflight","starting","running","stopping"].includes(launchWorkspace.view().phase)
    || routeCheckIsActive() || ["queued","cooldown","starting","running","stopping"].includes(benchmarkWorkspace.view().phase)
    || setupIsActive() || aneWorkIsActive();
}
const modelAssets = LLMModelAssets.createController({
  elements:Object.fromEntries([
    "openModelLibrary", "refreshModelLibrary", "clearModelLibraryFilters", "modelLibraryDialog", "modelLibrarySearch",
    "modelLibraryEngineFilter", "modelLibrarySurfaceFilter", "modelLibraryStateFilter", "modelLibraryBadge",
    "modelLibrarySummary", "modelLibraryCards", "modelLibraryStatus", "openAcquisitionCenter", "acquisitionDialog",
    "acquisitionSearchForm", "acquisitionSearch", "acquisitionSearchButton", "acquisitionSearchResults", "acquisitionRepoId",
    "acquisitionRevision", "acquisitionDestination", "acquisitionDestinationHelp", "acquisitionInspectButton",
    "acquisitionVariantField", "acquisitionVariant", "acquisitionPlan", "acquisitionConsent", "acquisitionConsentPanel",
    "acquisitionConsentCopy", "acquisitionBadge", "acquisitionStartButton", "acquisitionStartTitle", "acquisitionStartLabel",
    "acquisitionStopButton", "acquisitionOpenLibrary", "acquisitionPhase", "acquisitionPercent", "acquisitionProgressBar", "acquisitionStatus",
  ].map(id => [id, $(id)])),
  api:{library:() => api("/api/model-library"), status:() => api("/api/acquisition/status"),
    search:body => api("/api/acquisition/search", {method:"POST",body:JSON.stringify(body)}),
    inspect:body => api("/api/acquisition/inspect", {method:"POST",body:JSON.stringify(body)}),
    start:body => api("/api/acquisition/start", {method:"POST",body:JSON.stringify(body)}),
    stop:() => api("/api/acquisition/stop", {method:"POST",body:"{}"})},
  selectedModelId:() => launchWorkspace.selectedModel()?.id, lookupModel:id => launchWorkspace.catalog().find(model => model.id === id),
  applyRoute:(modelId, backend) => {
    if (!launchWorkspace.selectModelRoute(modelId, backend)) {
      throw new Error("The model is not selectable with an installed assistant on that runtime.");
    }
    setQuickStartEditor(true);
  },
  acceptCatalog:models => { launchWorkspace.useModelInventory(models); renderModelOptions(); if (profilesManager.shortcutsLoaded()) void loadQuickStart(true); },
  refreshModels:() => loadModels(false), onActivityChange:() => launchWorkspace.runState() ? renderRun(launchWorkspace.runState()) : refreshLaunchability(),
  otherWork:acquisitionOtherOperationActive, presentRoute:routeCapabilityPresentation, engineVisible:uiEngineVisible,
  modelVisible:uiModelVisible, featureEnabled:uiFeatureEnabled, isUzu:isUzuModel, contextLabel:modelContextLabel,
  backendLabel:backendName, backendMark, formatNumber, formatBytes, notify:showNotice,
});
function modelLibraryEngineModes(model = {}, engine = {}) { return modelAssets.engineModes(model, engine); }
function modelLibraryChecks(model = {}) { return modelAssets.libraryChecks(model); }
function renderModelLibrary() { modelAssets.renderLibrary(); }
function loadModelLibrary() { return modelAssets.loadLibrary(); }
function openModelLibrary() { return modelAssets.showLibrary(); }
function openFreeTokenModelReview() { return modelAssets.showFreeTokenReview(); }
function clearModelLibraryFilters() { modelAssets.clearFilters(); }
function useModelLibraryRoute(modelId, backend) { modelAssets.useRoute(modelId, backend); }
function acquisitionIsActive(status) { return status === undefined ? modelAssets.isActive() : modelAssets.isActive(status); }
function updateAcquisitionControls() { modelAssets.updateControls(); }
function renderAcquisitionStatus(envelope = {}) { modelAssets.useStatus(envelope); }
const pollAcquisitionStatus = statusPoller.add("acquisition", {
  interval:() => statusPollInterval(acquisitionIsActive(), "acquisitionDialog"),
  run:async () => { try { await modelAssets.refresh(); } catch (_) {} },
});
function openAcquisitionCenter() { return modelAssets.showAcquisition(); }
function searchAcquisitionModels() { return modelAssets.search(); }
function inspectAcquisitionModel(variantId = "") { return modelAssets.inspect(variantId); }
function startAcquisition() { return modelAssets.start(); }
function stopAcquisition() { return modelAssets.stop(); }
function openAcquiredModelLibrary() { return modelAssets.showAcquiredLibrary(); }

const runtimeManager = LLMRuntimeManager.createController({
  elements:Object.fromEntries([
    "refreshRuntimeManager", "runtimeAdvancedTools", "runtimeAgents", "runtimeCards", "runtimeDialog",
    "runtimeManagerStatus", "runtimeManagerSummary", "runtimePromotionConsent", "runtimePromotionConsentCopy", "runtimePromotionConsentPanel",
    "runtimePromotionModel", "runtimePromotionPercent", "runtimePromotionPhase", "runtimePromotionPlan", "runtimePromotionProgressBar",
    "runtimePromotionStartButton", "runtimePromotionStartLabel", "runtimePromotionStatus", "runtimePromotionStopButton", "runtimePromotionSuite",
    "runtimeSummaryBadge", "runtimeUpdateCatalogBadge", "runtimeUpdateConsent", "runtimeUpdateConsentCopy", "runtimeUpdateConsentPanel",
    "runtimeUpdatePercent", "runtimeUpdatePhase", "runtimeUpdatePlan", "runtimeUpdateProgressBar", "runtimeUpdateStartButton",
    "runtimeUpdateStartLabel", "runtimeUpdateStartTitle", "runtimeUpdateStatus", "runtimeUpdateStopButton", "runtimeUpdateTracks",
    "openRuntimeManager",
  ].map(id => [id, $(id)])),
  api:{inventory:() => api("/api/runtime/status"), updateStatus:() => api("/api/runtime/update/status"),
    promotionStatus:() => api("/api/runtime/promotion/status"),
    updatePlan:body => api("/api/runtime/update/plan", {method:"POST",body:JSON.stringify(body)}),
    updateStart:body => api("/api/runtime/update/start", {method:"POST",body:JSON.stringify(body)}),
    updateStop:() => api("/api/runtime/update/stop", {method:"POST",body:"{}"}),
    promotionPlan:body => api("/api/runtime/promotion/plan", {method:"POST",body:JSON.stringify(body)}),
    promotionStart:body => api("/api/runtime/promotion/start", {method:"POST",body:JSON.stringify(body)}),
    promotionStop:() => api("/api/runtime/promotion/stop", {method:"POST",body:"{}"}),
    promotionApply:body => api("/api/runtime/promotion/apply", {method:"POST",body:JSON.stringify(body)}),
    open:body => api("/api/runtime/open", {method:"POST",body:JSON.stringify(body)}),
    select:body => api("/api/runtime/select", {method:"POST",body:JSON.stringify(body)})},
  engineVisible:uiEngineVisible, selectedRequest:() => gather("custom", false),
  selectedModelName:() => selectedModel()?.name, selectedClient:() => launchWorkspace.view().client, informationLevel:activeDetail,
  currentOperation:() => acquisitionOtherOperationActive() || acquisitionIsActive() || sessionSetIsActive(),
  refreshSelection:async () => { applyBootstrapData(await api("/api/bootstrap")); await loadModels(false); },
  backendLabel:backendName, backendMark, formatBytes,
});
function runtimeUpdateIsActive(phase) { return runtimeManager.updateIsActive(phase); }
function runtimePromotionIsActive(phase) { return runtimeManager.promotionIsActive(phase); }
function loadRuntimeManager() { return runtimeManager.load(); }
function openRuntimeManager() { return runtimeManager.show(); }
const pollRuntimeUpdateStatus = statusPoller.add("update", {
  interval:() => runtimeUpdateIsActive() || $("runtimeDialog")?.open ? statusPollInterval(true, "runtimeDialog") : Infinity,
  run:() => runtimeManager.refreshUpdate(),
});
const pollRuntimePromotionStatus = statusPoller.add("promotion", {
  interval:() => statusPollInterval(runtimePromotionIsActive(), "runtimeDialog"),
  run:() => runtimeManager.refreshPromotion(),
});



statusPoller.add("sessionSets", {
  interval:() => $("sessionSetDialog").open || sessionSetIsActive()
    ? statusPollInterval(true, "sessionSetDialog") : Infinity,
  run:() => loadSessionSetStatus(true),
});
document.addEventListener("visibilitychange", () => {
  if (document.hidden) return;
  void statusPoller.tick();
  agentConsoleWorkspace.wake();
});

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
  chatWorkspace.initialize();
  renderChatSidebar();
  renderChatDraftStatus();
  try {
    const boot = await api("/api/bootstrap");
    applyBootstrapData(boot, true);
    await loadModels(false);
    initialiseVisibleRoute();
    await Promise.all([pollStatus(), pollRouteCheckStatus(), pollBenchmarkStatus(), pollSetupStatus(), pollAcquisitionStatus(), pollAneStatus(), pollAneCloneStatus(), pollRuntimePromotionStatus(), loadSessionSetStatus(false), loadQuickStart()]);
    await loadChatHistory(false);
    state.statusTimer = setInterval(() => { void statusPoller.tick(); }, 1800);
  } catch (error) { showNotice(`The local controller did not initialise: ${error.message}`, true); }
}

launchWorkspace.initialize();




benchmarkWorkspace.initialize();

















$("openFreeTokenControls").addEventListener("click", openFreeTokenDialog);



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
    event.preventDefault(); closeThemeMenu(); $("hubToolsMenuButton").focus(); return;
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







document.addEventListener("click", event => {
  if (state.themeMenuOpen && !$("themeMenuButton").closest(".theme-control").contains(event.target)) closeThemeMenu();
  if (state.hubToolsMenuOpen && !$("hubToolsMenuButton").closest(".hub-tools-control").contains(event.target)) closeHubToolsMenu();
});










$("focusedConsoleButton").addEventListener("click", () => selectAgentConsole());






















let launcherQuitting = false;
async function quitLauncher() {
  if (launcherQuitting) return;
  launcherQuitting = true;
  for (const id of ["quitLauncherButton", "agentConsoleQuitButton"]) $(id).disabled = true;
  $("quitLauncherTitle").textContent = "Closing your local AI";
  $("quitLauncherDetail").textContent = "Stopping local model engines and closing the launcher…";
  $("quitLauncherProgress").hidden = false;
  $("quitLauncherErrorActions").hidden = true;
  if (!$("quitLauncherDialog").open) $("quitLauncherDialog").showModal();
  try {
    const result = await api("/api/quit", {method:"POST", body:JSON.stringify({})});
    if (result.quitting !== true) throw new Error(result.message || "The controller did not confirm shutdown.");
    clearInterval(state.statusTimer);
    agentConsoleWorkspace.cancelRead();
    chatWorkspace.abortResponse();
    for (;;) {
      await sleep(300);
      let shutdown;
      try {
        shutdown = await api("/api/quit/status", {signal:AbortSignal.timeout(5000)});
      } catch (_error) {
        $("quitLauncherTitle").textContent = "Shutdown requested";
        $("quitLauncherDetail").textContent = "Shutdown was requested for local model processes, but completion could not be verified. Check the launcher and model processes before assuming they have stopped.";
        break;
      }
      if (shutdown.complete !== true) {
        if (shutdown.quitting !== true) {
          $("quitLauncherTitle").textContent = "Shutdown requested";
          $("quitLauncherDetail").textContent = "A controller is running, but completion of the requested shutdown could not be verified.";
          break;
        }
        continue;
      }
      const errors = Array.isArray(shutdown.errors) ? shutdown.errors : [];
      $("quitLauncherTitle").textContent = errors.length ? "Shutdown needs attention" : "Launcher closed";
      $("quitLauncherDetail").textContent = errors.length
        ? `The launcher is closing, but some processes could not be stopped: ${errors.map(error => typeof error === "string" ? error : error.message || error.error || "Unknown cleanup error").join("; ")}`
        : "Local model processes have been stopped. You can close this window.";
      break;
    }
    $("quitLauncherProgress").hidden = true;
  } catch (error) {
    launcherQuitting = false;
    for (const id of ["quitLauncherButton", "agentConsoleQuitButton"]) $(id).disabled = false;
    $("quitLauncherTitle").textContent = "Could not quit the launcher";
    $("quitLauncherDetail").textContent = error.message;
    $("quitLauncherProgress").hidden = true;
    $("quitLauncherErrorActions").hidden = false;
    $("quitLauncherRetryButton").focus();
  }
}
$("quitLauncherButton").addEventListener("click", quitLauncher);
$("agentConsoleQuitButton").addEventListener("click", quitLauncher);
$("quitLauncherRetryButton").addEventListener("click", quitLauncher);
$("quitLauncherDismissButton").addEventListener("click", () => { if (!launcherQuitting) $("quitLauncherDialog").close(); });
$("quitLauncherDialog").addEventListener("cancel", event => { if (launcherQuitting) event.preventDefault(); });
$("openSessionDashboard").addEventListener("click", openSessionDashboard);












$("setupConsent").addEventListener("change", updateSetupControls);
$("setupDownloadButton").addEventListener("click", startSetupDownload);
$("setupStopButton").addEventListener("click", stopSetup);

$("aneCpuAssist").addEventListener("change", updateAneControls);
$("aneStartButton").addEventListener("click", startAneTuning);
$("aneStopButton").addEventListener("click", stopAneTuning);
$("aneUseButton").addEventListener("click", useAneResult);
$("aneClonePlanButton").addEventListener("click", openAneClonePlan);
$("aneCloneConsent").addEventListener("change", updateAneCloneControls);
$("aneCloneStartButton").addEventListener("click", startAneClone);
$("aneCloneStopButton").addEventListener("click", stopAneClone);
$("aneCloneUseButton").addEventListener("click", useAneClone);

































































init();
