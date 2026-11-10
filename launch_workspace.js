/* Complete Launch Workspace: selected contracts, admission and resident session views. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;root.LLMLaunchWorkspace=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const immutable=value=>Array.isArray(value)?Object.freeze(value.map(immutable)):value&&typeof value==='object'?Object.freeze(Object.fromEntries(Object.entries(value).map(([key,item])=>[key,immutable(item)]))):value;
 function createController(options){
  const {nodes,collections,platform,cores,network,registry:registryPort,jobs:jobsPort,shell:shellPort,surfaces:surfacesPort,saved:savedPort,assets:assetsPort,benchmark:benchmarkPort,preflight:preflightPort}=options;
  const formattingPort=options.formatting;
  const policy=immutable(options.policy);
  const $=id=>nodes[id];
  const {RoutePreferenceCore,LaunchFlow,LauncherHomeCore,ChatStatusCore,CalibrationDecision,UiPresenter}=cores;
  const LLMRoutePreferenceCore=RoutePreferenceCore;
  const performance=platform.performance;
  const sleep=platform.sleep;
  const state={activeEvidenceBinding: null,activeEvidenceSignature: "",applyingOptimal: false,backend: "mtplx",cacheObservatory: null,catalogNotice: "",chatDefaultsModelId: "",client: "pi",freeToken: null,freeTokenBusy: false,homeEngineFeedback:"",homeEngineFeedbackSignature:"",idlePolicyBusy: false,launchPreparing:false,modelVerificationLoading: false,modelVerificationTimer: null,models: [],optimalLabel: "",optimalSignature: "",optimizationGeneration: 0,optimizerMenuOpen: false,pendingOptimizerBackend: "",pendingOptimizerSnapshot: null,performanceReceipt: null,performanceReceiptError: "",performanceReceiptGeneration: 0,performanceReceiptKey: "",performanceReceiptLoading: true,performanceReceiptTimer: null,requestActivity: null,requestCancelBusyId: "",routePreferenceReady: false,runPhase: "idle",runStatus: null,selected: null,sessionAcknowledgementId: "",sessionAdmissionError: "",sessionAdmissionErrorAt: 0,sessionAdmissionErrorSignature: "",sessionAdmissionPendingSignature: "",sessionAdmissionSignature: "",sessionAdmissionTimer: null,sessionAttachmentBusy: false,sessionAttachmentGeneration: 0,sessionAttachmentLoading: false,sessionAttachmentOwnerRunId: "",sessionAttachmentPlan: null,sessionAttachmentSignature: "",sessionAttachmentTimer: null,sessionDashboard: null,sessionGeneration: 0,sessionLastLoadedAt: 0,sessionLoading: false,warmRouteGeneration: 0,warmRouteLoading: false,warmRoutePendingSignature: "",warmRoutePlan: null,warmRouteSignature: "",warmRouteTimer: null};
  Object.defineProperties(state,{binaries:{get:()=>registryPort.binaries()},adapters:{get:()=>registryPort.adapters()},clientSupport:{get:()=>registryPort.clientSupport()},aneClonePhase:{get:()=>jobsPort.snapshot().aneClonePhase},aneCloneStatus:{get:()=>jobsPort.snapshot().aneCloneStatus},anePhase:{get:()=>jobsPort.snapshot().anePhase},aneStatus:{get:()=>jobsPort.snapshot().aneStatus},setupPhase:{get:()=>jobsPort.snapshot().setupPhase},setupStatus:{get:()=>jobsPort.snapshot().setupStatus},routeCheckPhase:{get:()=>jobsPort.snapshot().routeCheckPhase},routeCheckStatus:{get:()=>jobsPort.snapshot().routeCheckStatus},verifiedLaunchBusy:{get:()=>jobsPort.snapshot().verifiedLaunchBusy}});
  let activeLaunchFlow=null,launchReviewResolve=null;
  let runEpoch=0,idlePolicyGeneration=0,pendingIdlePolicy=null;
  let rapidDefaultsModelId="";
  let splashStandardControls=null;
  let homeModelGroups = [];
  const setupDefaults = Object.fromEntries(RoutePreferenceCore.SETUP_FIELDS.map(id => [id, $(id)?.value]));
  const renderedMarkup=new WeakMap();
  function setMarkup(node,markup){if(renderedMarkup.get(node)===markup)return;node.innerHTML=markup;renderedMarkup.set(node,markup);}
  function currentPolicyOwner(){return state.runStatus?.run?.runId || state.sessionDashboard?.hub?.session?.runId || null;}
  function retireIdlePolicy(){idlePolicyGeneration+=1;pendingIdlePolicy=null;state.idlePolicyBusy=false;}
  const endpointNames=Object.freeze({"/api/benchmark/history":"benchmarkHistory","/api/benchmark/start":"benchmarkStart","/api/benchmark/status":"benchmarkStatus","/api/benchmark/stop":"benchmarkStop","/api/calibration/plan":"calibrationPlan","/api/freetoken/connect":"freetokenConnect","/api/freetoken/disconnect":"freetokenDisconnect","/api/launch":"launch","/api/log":"log","/api/models":"models","/api/optimal":"optimal","/api/optimal-engine":"optimalEngine","/api/preview":"preview","/api/session/attach":"sessionAttach","/api/session/attachment-plan":"sessionAttachmentPlan","/api/session/idle-policy":"sessionIdlePolicy","/api/session/plan":"sessionPlan","/api/session/request/cancel":"sessionRequestCancel","/api/session/warm-attach":"sessionWarmAttach","/api/session/warm-plan":"sessionWarmPlan","/api/status":"status","/api/stop":"stop"});
  const api=(path,opts)=>{const name=endpointNames[path];if(!name)throw Error('Unsupported Launch Workspace operation.');return Promise.resolve(network[name](opts)).then(value=>structuredClone(value))};
  let initialized=false,statusTask=null;
  const pollStatus=()=>statusTask?statusTask():Promise.resolve();
function updateMtplxLongContextControl() {
  const select = $("mtplxOperatorRouteSelect");
  const help = $("mtplxOperatorRouteHelp");
  if (!select || !help) return;
  const model = selectedModel();
  const capabilityReady = registryPort.mtplxLongContextCapabilityExact(model);
  const values = {
    backend:state.backend,
    acceleration:$("accelerationSelect").value,
    profile:$("profileSelect").value,
    context:Number($("contextInput").value),
    output:Number($("outputInput").value),
    depth:Number($("depthInput").value),
    fan:$("fanSelect").value,
    client:state.client,
    reasoning:$("reasoningSelect").value,
    kv:$("mtplxKv").value,
  };
  const shapeEligible = registryPort.mtplxLongContextRouteEligible(model, values);
  const eligible = Boolean(shapeEligible && registryPort.mtplxLongContextMeasuredRecord(model, values));
  const measured = [...select.options].find(option => option.value === policy.MTPLX_OPERATOR_ROUTE_2111);
  if (measured) {
    measured.disabled = !eligible;
    measured.hidden = !eligible;
  }
  const resetUnavailableRoute = !eligible && select.value !== policy.MTPLX_OPERATOR_ROUTE_DEFAULT;
  if (resetUnavailableRoute) {
    select.value = policy.MTPLX_OPERATOR_ROUTE_DEFAULT;
    clearActiveEvidenceBinding();
    if (!state.applyingOptimal && (state.optimalSignature || state.optimalLabel)) {
      state.optimalSignature = "";
      state.optimalLabel = "";
      setOptimizationState(
        "custom", "Custom",
        "The measured 2.11.1 long-context route is no longer available for this setup.",
      );
    }
  }
  help.textContent = eligible
    ? "Measured 2.11.1 route ready for this exact setup."
    : capabilityReady && shapeEligible
      ? "Runtime default. Run Calibration once for this exact setup to unlock the measured 2.11.1 route."
      : capabilityReady
        ? "Runtime default. Choose MTP, Turbo, and at least 65,536 context tokens before testing the faster route."
      : "Runtime default. The measured 2.11.1 route is not ready for this model and runtime.";
}

function selectedModel() { return state.models.find(model => model.id === $("modelSelect").value) || null; }

function routeRuntimeInstalled(backend) {
  if (!registryPort.uiEngineVisible(backend)) return false;
  const key = registryPort.backendBinaryKey(backend);
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
  const backends = orderedRouteIds("engines", ["omlx", "lmstudio", "mtplx", "rapidmlx", "rec", "uzu", "freetoken", "swiftlm", "mference", "whallm", "slotstream", "splash", "strata", "llamacpp", "kolibri"])
    .filter(registryPort.uiEngineVisible);
  const clients = orderedRouteIds("workSurfaces", ["pi", "omp", "opencode", "codex", "chat"]);
  const models = state.models.filter(registryPort.uiModelVisible);
  const routes = [];
  for (const backend of backends) {
    if (!routeRuntimeInstalled(backend)) continue;
    for (const model of models) {
      const capability = model?.backends?.[backend];
      if (!model?.ready || !capability?.runnable) continue;
      if (backend === "llamacpp" && !registryPort.llamaCppPleQualified(model)) continue;
      if (!registryPort.routeCapabilityPresentation(capability, {
        backend, modelName:model.name, modelReady:model.ready,
      }).available) continue;
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

function persistVisibleRoute(includeSettings = true) {
  if (!state.routePreferenceReady) return false;
  const route = currentVisibleRoute();
  const available = visibleRouteCatalog();
  if (!route || !RoutePreferenceCore.isRouteAvailable(route, available)) return false;
  if (includeSettings) RoutePreferenceCore.writeSetup(platform.storage(), route, Object.fromEntries(
    RoutePreferenceCore.SETUP_FIELDS.map(id => [id, splashStandardControls?.[id] ?? $(id)?.value]),
  ));
  return RoutePreferenceCore.writeRoute(platform.storage(), route).stored;
}

function restoreVisibleSettings(route) {
  const saved = RoutePreferenceCore.readSetup(platform.storage(), route);
  if (!saved) return false;
  const restore = id => {
    const control = $(id), value = saved.controls[id];
    if (!control || typeof value !== "string") return;
    if (control.tagName === "SELECT") {
      if (![...control.options].some(option => option.value === value && !option.disabled)) return;
    } else if (control.type === "number" || control.type === "range") {
      if (value !== "") {
        const number = Number(value);
        if (!Number.isFinite(number)
            || (control.min !== "" && number < Number(control.min))
            || (control.max !== "" && number > Number(control.max))) return;
      } else if (!["seedInput", "freeTokenExpertCacheInput"].includes(id)) return;
    }
    control.value = value;
  };
  for (const id of RoutePreferenceCore.SETUP_FIELDS) {
    if (id !== "mtplxOperatorRouteSelect") restore(id);
  }
  // Reconcile current model/runtime limits and capabilities before restoring
  // an evidence-gated accelerator. Stored settings are never approval evidence.
  modelChanged();
  restore("mtplxOperatorRouteSelect");
  updateMtplxLongContextControl();
  refreshLaunchability();
  schedulePerformanceReceipt();
  return true;
}

function selectCatalogRoute(candidates) {
  if (state.launchPreparing || state.applyingOptimal) return false;
  const current = currentVisibleRoute();
  if (candidates?.some(route => RoutePreferenceCore.routeKey(route) === RoutePreferenceCore.routeKey(current))) return true;
  const preferred = candidates?.find(route => route.backend === state.backend && route.client === state.client)
    || candidates?.find(route => route.client === state.client);
  const next = RoutePreferenceCore.selectInitialRoute({
    preference:preferred, current, routes:candidates,
  });
  if (!next) return false;
  state.backend = next.backend;
  state.client = next.client;
  for (const [id, value] of Object.entries(setupDefaults)) {
    if (typeof value === "string") $(id).value = value;
  }
  const model = state.models.find(item => item.id === next.modelId);
  const cap = model?.backends?.[next.backend];
  const contextMaximum = cap?.contextMaximum || model?.nativeContext;
  const context = model?.defaultContext || Number($("contextInput").value);
  if (contextMaximum) $("contextInput").value = String(Math.min(context, contextMaximum));
  if (model?.defaultOutput) $("outputInput").value = String(model.defaultOutput);
  if (model?.defaultReasoning) $("reasoningSelect").value = model.defaultReasoning;
  state.chatDefaultsModelId = "";
  updateBackend(false, next.modelId);
  restoreVisibleSettings(next);
  persistVisibleRoute();
  benchmarkPort.scheduleBenchmarkHistory();
  return true;
}

function selectModelRoute(modelId, backend) {
  return selectCatalogRoute(visibleRouteCatalog().filter(route =>
    route.modelId === modelId && route.backend === backend));
}

function initialiseVisibleRoute() {
  const preference = RoutePreferenceCore.readRoute(platform.storage());
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
  restoreVisibleSettings(route);
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
  if (backend === "splash" && splashDspineActive() && model?.id === selectedModel()?.id && !["chat", "omp"].includes(client)) {
    return {supported:false, reason:"Experimental DSpine runs in Chat and oh-my-pi."};
  }
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
  if (backend === "kolibri") return $("kolibriKv").value;
  if (backend === "omlx") return $("omlxKv").value;
  if (backend === "mtplx") return $("mtplxKv").value;
  if (backend === "slotstream") return $("slotstreamKv").value;
  return "off";
}

function runtimeKvLabel(backend, options = {}) {
  const selected = options.kv && options.kv !== "off" ? String(options.kv).toUpperCase() : "Full";
  return backend === "omlx" && options.acceleration === "dflash" && selected !== "Full"
    ? (options.dflashVerify === "ddtree" ? `${selected} · incompatible with DDTree` : `${selected} (DFlash)`)
    : selected;
}

function updateOmlxKvControl() {
  const label = $("omlxKvLabel");
  const hint = $("omlxKvHint");
  if (!label || !hint) return;
  const control = $("omlxKv");
  const effective = $("omlxEffectiveKv");
  const fullPrecisionOnly = state.backend === "omlx" && selectedModel()?.omlxExpertOffload?.supported === true;
  for (const option of control.options) option.disabled = fullPrecisionOnly && option.value !== "off";
  if (fullPrecisionOnly) {
    label.textContent = "KV cache";
    control.hidden = false;
    effective.hidden = true;
    hint.textContent = "Flash expert offload uses full-precision QSA cache in this oMLX release. Select Full precision to launch.";
    return;
  }
  const dflash = $("accelerationSelect").value === "dflash";
  const verifier = $("dflashVerifySelect").value;
  label.textContent = "KV cache";
  control.hidden = false;
  const quantized = control.value !== "off";
  effective.hidden = !dflash || !quantized;
  effective.textContent = verifier === "ddtree"
    ? "Choose Adaptive or Fixed DFlash to use quantized KV."
    : `DFlash cache: ${String(control.value).toUpperCase()}`;
  hint.textContent = dflash
    ? (verifier === "ddtree"
      ? "DDTree requires full precision. Your cache selection is preserved when switching verifier."
      : "Q8, Q6 and Q4 reduce DFlash cache memory and retain prefix reuse. Lower precision can change output. Applies on next launch.")
    : "Quantized KV saves memory but can change output. Never changed by optimisation.";
}

function setRuntimeKvValue(backend, value) {
  if (backend === "rapidmlx") return value === "off";
  if (["lmstudio", "uzu", "freetoken", "swiftlm", "mference", "whallm", "splash", "strata", "rec", "llamacpp"].includes(backend)) return value === "off";
  const control = backend === "kolibri" ? $("kolibriKv") : backend === "slotstream" ? $("slotstreamKv") : backend === "omlx" ? $("omlxKv") : $("mtplxKv");
  const option = [...control.options].find(item => item.value === String(value));
  if (!option) return false;
  control.value = String(value);
  return true;
}

function gatherOptions() {
  if (state.backend === "splash") {
    return {acceleration:splashDspineActive() ? "dspine" : "off", depth:1, kv:"off"};
  }
  if (state.backend === "rapidmlx") {
    return {acceleration:$("accelerationSelect").value, depth:Number($("depthInput").value), kv:"off"};
  }
  if (state.backend === "kolibri") {
    return {acceleration:"off", depth:1, kv:$("kolibriKv").value,
      memoryGB:Number($("kolibriMemoryGB").value), memoryMode:$("kolibriMemoryMode").value,
      prefillSize:Number($("kolibriPrefillSelect").value), promptCacheGB:Number($("kolibriPromptCacheGB").value)};
  }
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
  if (state.backend === "swiftlm") {
    return {
      acceleration:"off", depth:1, kv:"off",
      prefillSize:Number($("swiftlmPrefillSelect").value),
      nativeExpertTopK:Number($("swiftlmTopK").value || 0),
    };
  }
  if (state.backend === "mference") {
    return {
      acceleration:"off", depth:1, kv:"off",
      promptCacheMode:$("mferencePromptCache").value,
      queueLimit:Number($("mferenceQueueLimit").value),
    };
  }
  if (state.backend === "slotstream") {
    return {acceleration:$("accelerationSelect").value, depth:Number($("depthInput").value), kv:$("slotstreamKv").value, memoryGB:Number($("slotstreamMemoryGB").value), memoryMode:$("slotstreamMemoryMode").value};
  }
  if (["uzu", "whallm", "strata", "rec", "llamacpp"].includes(state.backend)) {
    return {acceleration:"off", depth:1, kv:"off"};
  }
  return {
    acceleration: $("accelerationSelect").value,
    depth: Number($("depthInput").value),
    profile: $("profileSelect").value,
    ...(state.backend === "mtplx" ? {
      mtplxOperatorRoute: $("mtplxOperatorRouteSelect").value,
    } : {}),
    kv: runtimeKvValue(),
    fan: $("fanSelect").value,
    burst: $("burstSelect").value,
    dflashVerify: $("dflashVerifySelect").value,
    dflashDraftQuant: $("dflashDraftQuantSelect").value,
    anePrefill: $("anePrefillSelect").value,
    memoryGuard: selectedModel()?.omlxExpertOffload?.supported && state.backend === "omlx" ? "high" : $("memoryGuardSelect").value,
    ...(state.backend === "omlx" && selectedModel()?.omlxExpertOffload?.supported ? {
      expertResidentPercent: Number($("omlxExpertResidentPercent").value),
      omlxMemoryGB: Number($("omlxMemoryGB").value),
    } : {}),
    gpu: $("gpuSelect").value,
    parallel: Number($("parallelInput").value),
    mtpMinTokens: Number($("mtpMinTokensInput").value),
    mtpMinContinueProbability: Number($("mtpMinContinueProbabilityInput").value),
  };
}

function gatherGenerationSettings() {
  if (splashDspineActive()) {
    return {sampling:"custom", temperature:0, topP:1, topK:0, presencePenalty:0,
      frequencyPenalty:0, repetitionPenalty:1, seed:null};
  }
  const seed = $("seedInput").value.trim();
  return {
    sampling: $("samplingMode").value,
    temperature: Number($("temperatureInput").value),
    topP: Number($("topPInput").value),
    topK: Number($("topKInput").value),
    presencePenalty: Number($("presencePenaltyInput").value),
    frequencyPenalty: Number($("frequencyPenaltyInput").value),
    repetitionPenalty: Number($("repetitionPenaltyInput").value),
    seed: seed === "" ? null : Number(seed),
  };
}

function gatherChatSettings() {
  return {
    systemPrompt: $("systemPrompt").value,
    ...gatherGenerationSettings(),
  };
}

function gather(mode = "custom", includeMemoryAcknowledgement = true) {
  const model = selectedModel();
  if (!model) throw new Error("Choose a ready model.");
  const request = {
    backend: state.backend, client: state.client, modelId: model.id,
    project: $("projectPath").value, context: Number($("contextInput").value),
    output: Number($("outputInput").value), reasoning: $("reasoningSelect").value,
    mode, options: gatherOptions(), generation:gatherGenerationSettings(),
  };
  if (state.client === "chat") request.chat = gatherChatSettings();
  else request.agentHost = LauncherHomeCore.agentHostFor(state.client, $("agentHostSelect").value, {
    ompRpcQualified:state.binaries?.omp?.consoleSupported === true,
  });
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
    agentHost: state.client === "chat" ? "launcher" : LauncherHomeCore.agentHostFor(state.client, $("agentHostSelect").value, {
      ompRpcQualified:state.binaries?.omp?.consoleSupported === true,
    }),
    generation:gatherGenerationSettings(),
    chat: state.client === "chat" ? gatherChatSettings() : null,
  });
}

function speedSignature() {
  const options = gatherOptions();
  return JSON.stringify({
    backend: state.backend, model: selectedModel()?.id || "",
    kv: options.kv,
    values: Object.fromEntries((policy.optimizerKeys[state.backend] || []).map(key => [key, options[key]])),
  });
}

function optimizerEvidenceContractSignature() {
  const model = selectedModel();
  const capability = model?.backends?.[state.backend] || {};
  return JSON.stringify({
    backend:state.backend,
    modelId:model?.id || "",
    modelFingerprint:capability.benchmarkModelFingerprint || "",
    runtimeVersion:capability.runtimeVersion || "",
    client:state.client,
    context:Number($("contextInput").value),
    output:Number($("outputInput").value),
    reasoning:$("reasoningSelect").value,
    kv:runtimeKvValue(),
    generation:gatherGenerationSettings(),
    modelSampling:model?.defaultSampling || {},
    speed:speedSignature(),
  });
}

function copiedEvidenceBinding(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const scope = String(value.scope || "");
  const suite = String(value.suite || "");
  const preference = String(value.preference || "");
  if (!["engine", "route"].includes(scope) || !suite || !preference) return null;
  if (scope === "engine") {
    const records = value.recordIds;
    if (
      typeof value.shootoutId !== "string" || !value.shootoutId
      || !records || typeof records !== "object" || Array.isArray(records)
      || Object.keys(records).length < 2
      || Object.values(records).some(id => typeof id !== "string" || !id)
    ) return null;
  } else if (typeof value.recordId !== "string" || !value.recordId) return null;
  return JSON.parse(JSON.stringify(value));
}

function clearActiveEvidenceBinding() {
  state.activeEvidenceBinding = null;
  state.activeEvidenceSignature = "";
}

function activeEvidenceBindingFor(scope, preference) {
  const binding = copiedEvidenceBinding(state.activeEvidenceBinding);
  if (
    !binding || binding.scope !== scope || binding.preference !== preference
    || state.activeEvidenceSignature !== optimizerEvidenceContractSignature()
  ) return null;
  return binding;
}

function rememberActiveEvidenceBinding(value) {
  const binding = copiedEvidenceBinding(value);
  if (!binding) {
    clearActiveEvidenceBinding();
    return;
  }
  state.activeEvidenceBinding = binding;
  state.activeEvidenceSignature = optimizerEvidenceContractSignature();
}

function optimizerValueSnapshot() {
  return Object.fromEntries(Object.entries(policy.optimizerControls).map(([key, id]) => [key, $(id).value]));
}

function restoreOptimizerValues(snapshot) {
  Object.entries(snapshot || {}).forEach(([key, value]) => {
    const control = $(policy.optimizerControls[key]);
    if (control) control.value = value === null || value === undefined ? "" : String(value);
  });
  setRangeVisual($("depthInput"), $("depthValue"));
  setRangeVisual($("parallelInput"), $("parallelValue"));
  setRangeVisual($("mtpMinTokensInput"), $("mtpMinTokensValue"));
  setRangeVisual($("mtpMinContinueProbabilityInput"), $("mtpMinContinueProbabilityValue"));
  updateAccelerationState();
}

function clearOptimizerAnimationClasses() {
  collections.optimizerControls.filter(node=>node.classList.contains("optimizing")||node.classList.contains("optimized")).forEach(field => {
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
  clearActiveEvidenceBinding();
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
  clearActiveEvidenceBinding();
  state.optimalSignature = "";
  state.optimalLabel = "";
  setOptimizationState("custom", "Custom", reason);
}

function setOptimizerInteractionLocked(locked) {
  const advanced = $("advancedControls");
  // The diagnostic actions remain usable while tuning fields are locked.
  advanced.querySelectorAll(".advanced-body > :not(#launchTools)").forEach(section => {
    section.inert = Boolean(locked);
    section.classList.toggle("interaction-locked", Boolean(locked));
  });
}

function setOptimizerMenu(open, focusFirst = false) {
  const menu = $("optimizerMenu");
  const button = $("optimizerMenuButton");
  const next = Boolean(open && !button.disabled);
  if (next) { shellPort.setThemeMenu(false); shellPort.setHubToolsMenu(false); }
  state.optimizerMenuOpen = next;
  menu.hidden = !next;
  button.setAttribute("aria-expanded", String(next));
  if (next && focusFirst) menu.querySelector('[role="menuitem"]')?.focus();
}

function closeOptimizerMenu() { setOptimizerMenu(false); }

function toggleOptimizerMenu() {
  setOptimizerMenu(!state.optimizerMenuOpen, !state.optimizerMenuOpen);
}

function reasoningChoices(client = state.client) {
  const capability = selectedModel()?.backends?.[state.backend];
  return capability?.[client === "codex" ? "codexReasoning" : "agentReasoning"] || ["auto"];
}

function normalizeReasoningSelection(client = state.client) {
  const allowed = reasoningChoices(client);
  const select = $("reasoningSelect");
  if (!allowed.includes(select.value)) {
    select.value = allowed.includes("auto") ? "auto" : (allowed[0] || "auto");
  }
  return select.value;
}

function clientInstalled(client) {
  const adapter = registryPort.adapterDescriptor("workSurfaces", client);
  if (adapter) return Boolean(adapter.installed);
  return client === "chat" || Boolean(state.binaries?.[client]?.installed);
}

function clientAvailability(client = state.client) {
  const support = resolvedClientSupport(state.backend, client);
  if (!support?.supported) return { available: false, reason: support?.reason || "This runtime and work surface are not compatible." };
  if (!clientInstalled(client)) return { available: false, reason: `${formattingPort.clientName(client)} is not installed.` };
  const allowed = reasoningChoices(client);
  if (!allowed.includes($("reasoningSelect").value)) {
    const labels = allowed.map(value => value === "auto" ? "Model default" : value).join(", ");
    return { available: false, reason: `This exact route can enforce these reasoning choices: ${labels}. Choose one explicitly.` };
  }
  return { available: true, reason: support.reason || "Supported" };
}

function chatSettingsError() {
  if (state.client === "chat" && $("systemPrompt").value.length > 32000) return "System prompt must be at most 32,000 characters.";
  if (splashDspineActive()) return "";
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
  const repetitionPenaltyText = $("repetitionPenaltyInput").value.trim();
  if (!temperatureText) return "Temperature is required when custom sampling is selected.";
  if (!topPText) return "Top P is required when custom sampling is selected.";
  if (!topKText) return "Top K is required when custom sampling is selected.";
  if (!presencePenaltyText) return "Presence penalty is required when custom sampling is selected.";
  if (!frequencyPenaltyText) return "Frequency penalty is required when custom sampling is selected.";
  if (!repetitionPenaltyText) return "Repetition penalty is required when custom sampling is selected.";
  const temperature = Number(temperatureText);
  const topP = Number(topPText);
  const topK = Number(topKText);
  const presencePenalty = Number(presencePenaltyText);
  const frequencyPenalty = Number(frequencyPenaltyText);
  const repetitionPenalty = Number(repetitionPenaltyText);
  const seedText = $("seedInput").value.trim();
  if (!Number.isFinite(temperature) || temperature < 0 || temperature > 2) return "Temperature must be between 0 and 2.";
  if (!Number.isFinite(topP) || topP < 0 || topP > 1) return "Top P must be between 0 and 1.";
  if (!Number.isInteger(topK) || topK < 0 || topK > 1000000) return "Top K must be a whole number between 0 and 1,000,000.";
  if (!Number.isFinite(presencePenalty) || presencePenalty < -2 || presencePenalty > 2) return "Presence penalty must be between -2 and 2.";
  if (!Number.isFinite(frequencyPenalty) || frequencyPenalty < -2 || frequencyPenalty > 2) return "Frequency penalty must be between -2 and 2.";
  if (!Number.isFinite(repetitionPenalty) || repetitionPenalty < 0 || repetitionPenalty > 10) return "Repetition penalty must be between 0 and 10.";
  if (state.backend === "rec" && frequencyPenalty !== 0) return "Rec requires frequency penalty 0. Reset it to 0, or use model sampling defaults.";
  if (state.backend === "rec" && repetitionPenalty !== 1) return "Rec requires repetition penalty 1. Reset it to 1, or use model sampling defaults.";
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
  if (model?.nativeContext && context > model.nativeContext) return `This model advertises at most ${formattingPort.formatNumber(model.nativeContext)} context tokens. The launcher will not silently lower your value.`;
  const rapidMaximum = state.backend === "rapidmlx" && Number(model?.backends?.rapidmlx?.contextMaximum);
  if (rapidMaximum > 0 && context > rapidMaximum) return `Rapid MLX supports at most ${formattingPort.formatNumber(rapidMaximum)} context tokens for this route.`;
  const capability = model?.backends?.[state.backend];
  const runtimeWindows = selectedContextWindows(capability);
  if (Array.isArray(runtimeWindows) && !runtimeWindows.includes(context)) {
    return `${formattingPort.backendName(state.backend)} supports these exact context windows: ${runtimeWindows.map(formattingPort.formatNumber).join(", ")}.`;
  }
  if (!Number.isInteger(output) || output < 256) return "Maximum response must be at least 256 tokens.";
  const outputMaximum = model?.backends?.[state.backend]?.outputMaximum || model?.outputMaximum;
  if (outputMaximum && output > outputMaximum) return `This route supports at most ${formattingPort.formatNumber(outputMaximum)} response tokens.`;
  if (output >= context) return "Maximum response must be smaller than context.";
  if (context - output < 1024) return "Leave at least 1,024 context tokens for instructions and history.";
  if (state.client === "codex" && output < 1024) return "Codex local sessions need at least 1,024 response tokens.";
  return "";
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

function setRangeVisual(input, output = formattingPort.rangeOutputFor(input)) {
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
    ? `${readiness.runtimeDetected || "oMLX"}${readiness.runtimeRecommended ? " · current recommended build" : ` · supported; ${readiness.recommendedRuntime || "rc3"} recommended`}`
    : `${readiness.runtimeDetected || "Not installed"} · needs ${readiness.recommendedRuntime || "0.6.3rc3"}`;
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
  $("dflashChecks").innerHTML = checks.map(check => `<div class="dflash-check ${check.ready ? "pass" : "pending"}"><i>${check.ready ? "✓" : "!"}</i><span><b>${formattingPort.esc(check.title)}</b>${formattingPort.esc(check.detail)}</span></div>`).join("");
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
  $("aneChecks").innerHTML = checks.map(check => `<div class="dflash-check ${check.ready ? "pass" : "pending"}"><i>${check.ready ? "✓" : "!"}</i><span><b>${formattingPort.esc(check.title)}</b>${formattingPort.esc(check.detail)}</span></div>`).join("");
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
  $("aneReleaseLink").href = readiness.releaseUrl || "https://github.com/jundot/omlx/releases/tag/v0.6.3rc3";
  $("openAneButton").disabled = !(state.backend === "omlx" && selectedModel());
}

function rapidMtpDepths(cap = selectedModel()?.backends?.rapidmlx || {}) {
  if (cap.mtp !== true) return [1];
  const declared = Array.isArray(cap.depthChoices)
    ? cap.depthChoices.map(Number).filter(value => Number.isInteger(value) && value >= 1) : [];
  const maximum = Math.max(1, Number(cap.depthMax) || Math.max(Number(cap.depth) || 1, ...declared));
  const choices = [...new Set(declared.filter(value => value <= maximum))].sort((a,b) => a-b);
  return choices.length ? choices : Array.from({length:maximum}, (_,index) => index + 1);
}

function updateAccelerationState() {
  const cap = selectedModel()?.backends?.[state.backend] || {};
  const rapid = state.backend === "rapidmlx";
  if (rapid) {
    for (const option of $("accelerationSelect").options) {
      option.disabled = option.value === "mtp" ? cap.mtp !== true : !["auto", "off"].includes(option.value);
      if (option.value === "auto") option.textContent = cap.mtp === true ? "Auto · native MTP" : "Auto · AR";
    }
    const choices = rapidMtpDepths(cap);
    if (cap.mtp !== true) $("depthInput").value = "1";
    $("depthInput").min = String(choices[0]);
    $("depthInput").max = String(choices.at(-1));
    const control = $("rapidmlxDepthSelect");
    const markup = choices.map(value => `<option value="${value}">${value}${value === Number(cap.depth) ? " · native default" : ""}</option>`).join("");
    if (control.innerHTML !== markup) control.innerHTML = markup;
    control.value = choices.includes(Number($("depthInput").value)) ? $("depthInput").value : "";
    control.disabled = cap.mtp !== true || !["auto", "mtp"].includes($("accelerationSelect").value);
    $("rapidmlxMtpHelp").textContent = cap.mtp === true
      ? "Auto uses the native MTP route. Draft depth controls how many tokens are proposed before verification; available depths come from this model and runtime."
      : cap.mtpReason || "This checkpoint has no compatible MTP head. Auto and Off use standard decoding.";
  } else {
    $("depthInput").min = "1";
    const automatic = $("accelerationSelect").querySelector('option[value="auto"]');
    if (automatic) automatic.textContent = "Auto";
  }
  $("depthInput").closest(".range-field")?.classList.toggle("hidden", rapid);
  const managedLabel = typeof cap.runtimeManagedAcceleration === "string"
    ? cap.runtimeManagedAcceleration.trim() : "";
  $("uzuAccelerationLabel").textContent = managedLabel || "DFlash + Weaver";
  const mode = $("accelerationSelect").value;
  const relevant = ((mode === "mtp" || (rapid && mode === "auto")) && cap.mtp) || (mode === "dflash" && cap.dflash);
  $("depthInput").disabled = rapid || !relevant;
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
  updateMtplxLongContextControl();
}

function splashDspineActive() {
  return state.backend === "splash" && $("splashAccelerationSelect")?.value === "dspine";
}

function selectedContextWindows(capability) {
  return splashDspineActive()
    ? capability?.dspineContexts || [capability?.dspineContext]
    : capability?.contextWindows;
}

function updateSplashAcceleration() {
  const select = $("splashAccelerationSelect");
  if (!select) return;
  const cap = state.backend === "splash" ? selectedModel()?.backends?.splash : null;
  const option = select.querySelector('option[value="dspine"]');
  if (option) option.disabled = cap?.dspine !== true;
  if (state.backend === "splash" && cap?.dspine !== true) select.value = "off";
  const active = splashDspineActive();
  if (active && !splashStandardControls) {
    splashStandardControls = Object.fromEntries(
      ["contextInput", "outputInput", "samplingMode"].map(id => [id, $(id).value]),
    );
    if (!["chat", "omp"].includes(state.client)) state.client = "chat";
    updateChatSamplingControls();
  } else if (!active && splashStandardControls) {
    for (const [id, value] of Object.entries(splashStandardControls)) $(id).value = value;
    splashStandardControls = null;
    updateChatSamplingControls();
  }
  if (active && !selectedContextWindows(cap).includes(Number($("contextInput").value))) {
    $("contextInput").value = String(cap.dspineContext);
    if (Number($("outputInput").value) > cap.dspineContext - 1024) {
      $("outputInput").value = String(Math.min(cap.dspineOutput, cap.dspineContext - 1024));
    }
  }
  $("splashAccelerationHelp").textContent = active
    ? "Experimental DSpine with greedy sampling. 256K uses a compact draft with BF16 refinement. Chat and oh-my-pi support reasoning and tool calls."
    : cap?.dspine === true
      ? "DSpine supports Chat and oh-my-pi with up to 256K context and greedy sampling."
      : cap?.dspineReason || "DSpine requires the supported Qwen3.8-27B 4-bit MLX checkpoint and local draft.";
}

function updateChatSamplingControls() {
  const capability = selectedModel()?.backends?.[state.backend] || {};
  const customSupported = Boolean(selectedModel()) && capability.customSampling !== false;
  const dspine = splashDspineActive();
  $("samplingMode").disabled = dspine;
  const modelOption = $("samplingMode").querySelector('option[value="model"]');
  if (modelOption) modelOption.textContent = dspine ? "Greedy · DSpine" : "Model defaults";
  if (dspine) $("samplingMode").value = "model";
  const customOption = $("samplingMode").querySelector('option[value="custom"]');
  if (customOption) customOption.disabled = !customSupported;
  if (!customSupported && $("samplingMode").value === "custom") $("samplingMode").value = "model";
  const custom = $("samplingMode").value === "custom";
  $("chatSettings").classList.toggle("sampling-defaults", !custom);
  collections.chatSamplers.forEach(field => {
    field.hidden = !custom;
    field.classList.toggle("inactive", !custom);
  });
  for (const id of [
    "temperatureInput", "topPInput", "topKInput", "presencePenaltyInput",
    "frequencyPenaltyInput", "repetitionPenaltyInput", "seedInput",
  ]) $(id).disabled = !custom;
  for (const [id, neutral] of [["frequencyPenaltyInput", 0], ["repetitionPenaltyInput", 1]]) {
    const field = $(id);
    const rec = state.backend === "rec";
    // Keep a prior route's non-neutral value editable so it can be reset.
    if (rec && custom) field.disabled = field.value.trim() !== "" && Number(field.value) === neutral;
    field.title = rec ? `Rec requires ${neutral}. Reset any previous value to ${neutral}, or choose model defaults.` : "";
  }
  if (dspine) {
    $("samplingHelp").textContent = "DSpine uses temperature 0 and neutral penalties.";
  } else if (!customSupported) {
    $("samplingHelp").textContent = capability.samplingReason || "This route uses fixed runtime decoding.";
  } else if (!custom) {
    const defaults = selectedModel()?.defaultSampling || {};
    const parts = [];
    if (defaults.temperature !== undefined) parts.push(`temperature ${defaults.temperature}`);
    if (defaults.top_p !== undefined) parts.push(`top P ${defaults.top_p}`);
    if (defaults.top_k !== undefined) parts.push(`top K ${defaults.top_k}`);
    $("samplingHelp").textContent = parts.length ? `Detected defaults: ${parts.join(" · ")}.` : "The runtime uses this model's generation defaults.";
  } else {
    $("samplingHelp").textContent = state.backend === "rec"
      ? "Rec supports temperature, top P, top K, presence penalty and seed. Frequency must be 0 and repetition must be 1; reset any values from another engine."
      : "These request values override the model defaults for every turn.";
  }
  const presence = Number($("presencePenaltyInput").value || 0);
  const frequency = Number($("frequencyPenaltyInput").value || 0);
  const repetition = Number($("repetitionPenaltyInput").value || 1);
  const seed = $("seedInput").value.trim();
  const penaltyLabel = presence === 0 && frequency === 0 && repetition === 1
    ? "Penalties neutral" : `Presence ${presence} · frequency ${frequency} · repetition ${repetition}`;
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

function visibleSessionAdmissionRequest() {
  try { return gather("custom", false); }
  catch (_) { return null; }
}

function visibleSessionAdmissionSignature(request = null) {
  const visible = request || visibleSessionAdmissionRequest();
  return visible ? JSON.stringify(visible) : "";
}

function sessionAdmissionDecision(admission, acknowledgementId = "") {
  if (!admission || typeof admission !== "object") return {
    known:false, actionReady:false, decision:"unknown",
    label:"Capacity check unavailable",
    detail:"Refresh the route before starting a model.",
  };
  const needsReview = admission.requiresAcknowledgement === true;
  const acknowledged = Boolean(
    needsReview && admission.contractId
    && acknowledgementId === admission.contractId
  );
  return {
    known:true,
    actionReady:Boolean(admission.launchable === true && (!needsReview || acknowledged)),
    launchable:admission.launchable === true,
    needsReview,
    acknowledged,
    decision:String(admission.decision || "unknown"),
    label:String(admission.label || "Capacity unavailable"),
    detail:String(admission.detail || "This route is not ready to start."),
    contractId:String(admission.contractId || ""),
  };
}

function currentSessionAdmission(now = Date.now()) {
  const warm = currentWarmRoutePlan();
  if (warm?.canAttach) return {
    known:true, actionReady:true, launchable:true, warm:true,
    decision:"ready", label:"Loaded route ready",
    detail:warm.detail || "This work surface can reuse the loaded model.",
  };
  const signature = visibleSessionAdmissionSignature();
  if (!signature) return {
    known:false, actionReady:false, decision:"invalid",
    label:"Finish the visible settings",
    detail:"Choose a ready model and valid settings first.",
  };
  const matching = Boolean(
    state.sessionDashboard?.admission
    && state.sessionAdmissionSignature === signature
  );
  const age = matching ? Math.max(0, now - Number(state.sessionLastLoadedAt || 0)) : Infinity;
  const failed = Boolean(
    state.sessionAdmissionError
    && state.sessionAdmissionErrorSignature === signature
    && Number(state.sessionAdmissionErrorAt || 0) >= Number(state.sessionLastLoadedAt || 0)
  ) ? state.sessionAdmissionError : "";
  if (failed || !matching || age > policy.SESSION_ADMISSION_MAX_AGE_MS) {
    const pending = Boolean(
      state.sessionLoading
      && state.sessionAdmissionPendingSignature === signature
    );
    return {
      known:false, actionReady:false, pending,
      decision:failed ? "error" : "checking",
      label:failed ? "Capacity check unavailable" : "Checking Mac capacity",
      detail:failed || "Checking whether this exact route fits safely before it can start.",
      signature,
    };
  }
  return {
    ...sessionAdmissionDecision(
      state.sessionDashboard.admission,
      state.sessionAcknowledgementId,
    ),
    signature, age,
  };
}

function sessionAdmissionBlockerCopy(admission = currentSessionAdmission()) {
  if (admission.actionReady) return "";
  if (admission.decision === "checking") return "Checking this route fits safely…";
  if (admission.decision === "error") return "Capacity check unavailable. Refresh and try again.";
  if (admission.needsReview && !admission.acknowledged) {
    return "Review this route’s memory estimate in Sessions before starting.";
  }
  if (admission.decision === "pressure") {
    return admission.detail || "This setup exceeds the available memory, including cache macOS can reclaim.";
  }
  if (admission.decision === "configuration") {
    if (/high-memory mode/i.test(admission.label)) {
      return "Choose High memory in Runtime controls, or pick a smaller route.";
    }
    return /context|memory/i.test(admission.label)
      ? "This setup is too large for this Mac. Reduce context or choose another runtime."
      : admission.label;
  }
  if (admission.decision === "unknown") return "Memory safety could not be confirmed. Refresh before starting.";
  if (admission.decision === "qualification") return "This route needs its one-time qualification before launch.";
  return admission.label || "This route is not safe to start yet.";
}

function scheduleSessionAdmissionPlan(immediate = false) {
  const request = visibleSessionAdmissionRequest();
  const signature = visibleSessionAdmissionSignature(request);
  if (!signature || currentWarmRoutePlan()?.canAttach) {
    if (state.sessionAdmissionTimer !== null) platform.clearTimeout(state.sessionAdmissionTimer);
    state.sessionAdmissionTimer = null;
    return;
  }
  const current = state.sessionAdmissionSignature === signature
    && Boolean(state.sessionDashboard?.admission);
  const age = current ? Date.now() - Number(state.sessionLastLoadedAt || 0) : Infinity;
  const recentFailure = Boolean(
    state.sessionAdmissionError
    && state.sessionAdmissionErrorSignature === signature
    && Number(state.sessionAdmissionErrorAt || 0) >= Number(state.sessionLastLoadedAt || 0)
    && Date.now() - Number(state.sessionAdmissionErrorAt || 0) < policy.SESSION_ADMISSION_REFRESH_MS
  );
  if (recentFailure) return;
  if (current && age < policy.SESSION_ADMISSION_REFRESH_MS) return;
  if (
    state.sessionLoading
    && state.sessionAdmissionPendingSignature === signature
  ) return;
  if (state.sessionAdmissionTimer !== null) platform.clearTimeout(state.sessionAdmissionTimer);
  state.sessionAdmissionTimer = platform.setTimeout(() => {
    state.sessionAdmissionTimer = null;
    void loadSessionDashboard({force:current, request});
  }, immediate ? 0 : policy.SESSION_ADMISSION_DEBOUNCE_MS);
}

async function requireFreshSessionAdmission() {
  const request = visibleSessionAdmissionRequest();
  if (!request) return false;
  const expectedSignature = visibleSessionAdmissionSignature(request);
  const refreshed = await loadSessionDashboard({force:true, request});
  if (!refreshed || visibleSessionAdmissionSignature() !== expectedSignature) {
    const pending = state.sessionLoading
      && state.sessionAdmissionPendingSignature === expectedSignature;
    shellPort.showNotice(
      pending ? "Checking this route fits safely…"
        : sessionAdmissionBlockerCopy(currentSessionAdmission()),
      true,
    );
    refreshLaunchability();
    return false;
  }
  const admission = currentSessionAdmission();
  if (admission.actionReady) return true;
  shellPort.showNotice(sessionAdmissionBlockerCopy(admission), true);
  refreshLaunchability();
  return false;
}

function clearWarmRoutePlan() {
  if (state.warmRouteTimer) platform.clearTimeout(state.warmRouteTimer);
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
  if (state.warmRouteTimer) platform.clearTimeout(state.warmRouteTimer);
  state.warmRoutePlan = null;
  state.warmRouteSignature = "";
  state.warmRoutePendingSignature = signature;
  state.warmRouteTimer = platform.setTimeout(() => {
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
  const ompRpcQualified = state.binaries?.omp?.consoleSupported === true;
  LauncherHomeCore.syncAgentHost($("agentHostSelect"), state.client, {ompRpcQualified});
  $("agentHostHelp").textContent = state.client === "omp" && !ompRpcQualified
    ? "This oh-my-pi version opens in macOS Terminal. Update to a supported version to use Hub Console."
    : "Hub Console stays in the launcher. Terminal opens the assistant in a separate macOS window.";
  const freeTokenMode = state.backend === "freetoken" ? freeTokenRoute() : "unavailable";
  const warm = currentWarmRoutePlan();
  $("chatSettings").classList.remove("hidden");
  $("systemPromptField").hidden = !chat;
  $("agentHostSettings").classList.toggle("hidden", chat);
  $("projectLabel").textContent = chat ? "Working folder" : "Project folder";
  $("launchLabel").textContent = warm?.canAttach
    ? (warm.action?.label || (chat ? "Open warm chat" : `Open ${formattingPort.clientName(state.client)}`))
    : chat ? "Start chat" : "Launch";
  if (warm?.canAttach) {
    $("launchSummary").textContent = `Reuse loaded ${formattingPort.backendName(warm.loadedRoute?.backend || state.backend)} · no model reload`;
  } else if (state.runPhase === "running" && state.warmRouteLoading) {
    $("launchSummary").textContent = "Checking the loaded route…";
  } else $("launchSummary").textContent = "Checks included";
}

function updateContextChoices() {
  const input = $("contextInput");
  const select = $("contextSelect");
  const capability = selectedModel()?.backends?.[state.backend];
  const maximum = state.backend === "rapidmlx" ? Number(capability?.contextMaximum) : 0;
  const contextWindows = selectedContextWindows(capability);
  const windows = [...new Set((contextWindows || [])
    .map(Number).filter(value => Number.isInteger(value) && value > 0 && (!maximum || value <= maximum)))].sort((a, b) => a - b);
  const fixed = windows.length > 0;
  input.classList.toggle("hidden", fixed);
  select.classList.toggle("hidden", !fixed);
  select.disabled = !fixed || windows.length === 1 && splashDspineActive();
  $("contextField").htmlFor = fixed ? "contextSelect" : "contextInput";
  if (!fixed) return;
  const current = Number(input.value);
  const choices = windows.map(value => `<option value="${value}">${formattingPort.exactContextTier(value)} · ${formattingPort.formatNumber(value)} tokens</option>`).join("");
  const markup = (windows.includes(current) ? "" : '<option value="" disabled>Choose a supported context</option>') + choices;
  if (select.innerHTML !== markup) select.innerHTML = markup;
  select.value = windows.includes(current) ? String(current) : "";
}

function refreshLaunchability() {
  updateSplashAcceleration();
  updateContextChoices();
  updateOmlxKvControl();
  const selected = selectedModel();
  const allowedReasoning = reasoningChoices();
  normalizeReasoningSelection();
  [...$("reasoningSelect").options].forEach(option => {
    option.disabled = !allowedReasoning.includes(option.value);
    const budgets = state.backend === "splash"
      ? {auto:32768, low:1024, medium:4096, xhigh:32768}
      : {minimal:1024, low:2048, medium:4096, high:8192, xhigh:16384};
    const budget = ["mtplx", "splash"].includes(state.backend) && budgets[option.value];
    option.textContent = budget
      ? `${option.value === "auto" ? "Model default" : option.value} · up to ${formattingPort.formatNumber(Math.min(budget, Math.max(0, Math.floor(Number($("outputInput").value) / 2))))} thinking tokens`
      : (option.value === "auto" ? "Model default" : option.value);
  });
  $("reasoningSelect").title = state.backend === "mtplx"
    ? "These levels set a thinking-token ceiling. The model may finish thinking sooner. Native effort also applies when supported by the model template. Changes apply on launch."
    : state.backend === "splash"
    ? "Splash thinking has an enforced token ceiling. At the ceiling the model continues into an answer or tool call in the same request. Roughly half Max response is reserved for that output. Model default uses xhigh; off disables thinking. Changes apply on launch."
    : state.backend === "rec"
    ? "Flint reasoning is always enabled. Its thinking and answer share Max response."
    : "Reasoning settings supported by this model and engine.";
  collections.backendButtons.forEach(button => {
    if (!registryPort.uiEngineVisible(button.dataset.backend)) {
      button.hidden = true;
      button.disabled = true;
      button.setAttribute("aria-disabled", "true");
      button.setAttribute("aria-pressed", "false");
      return;
    }
    button.hidden = false;
    const key = registryPort.backendBinaryKey(button.dataset.backend);
    const installed = Boolean(state.binaries?.[key]?.installed);
    const connectable = button.dataset.backend === "freetoken";
    const verifyingPle = button.dataset.backend === "llamacpp" && Boolean(registryPort.llamaCppPleCheckingModel());
    const qualifiedPle = button.dataset.backend !== "llamacpp"
      || Boolean(registryPort.llamaCppPleModel()) || verifyingPle;
    const unavailable = (!installed && !connectable) || !qualifiedPle || state.applyingOptimal;
    button.disabled = unavailable;
    button.setAttribute("aria-disabled", String(unavailable));
    button.setAttribute("aria-pressed", String(button.dataset.backend === state.backend));
    button.classList.toggle("disabled", unavailable);
    button.classList.toggle("disconnected", connectable && !installed);
    if (button.dataset.backend === "llamacpp") button.title = verifyingPle
      ? "Pinned Qwen3.8 Flash-Next is being SHA-256 verified in this controller"
      : qualifiedPle
      ? "Pinned Qwen3.8 Flash-Next route ready · fixed 8K context"
      : "No pinned verified artifact route is available";
    if (connectable) button.title = installed
      ? state.freeToken?.connected && state.freeToken?.native?.installed
        ? "Native FreeToken and a connected server are available"
        : state.freeToken?.native?.installed
          ? "Native FreeToken port detected"
          : "Connected FreeToken server"
      : "Select to set up FreeToken";
  });
  collections.clientButtons.forEach(button => {
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
  const runtimeKey = registryPort.backendBinaryKey(state.backend);
  const runtimeReady = Boolean(state.binaries?.[runtimeKey]?.installed);
  const limits = limitError();
  const chatError = chatSettingsError();
  const freeTokenError = freeTokenSettingsError();
  const runActive = ["preflight","starting","running","stopping"].includes(state.runPhase);
  const routeCheckActive = ["queued","starting","running","stopping"].includes(state.routeCheckPhase);
  const benchmarkActive = ["queued","cooldown","starting","running","stopping"].includes(benchmarkPort.view().phase);
  const setupActive = ["queued","downloading","stopping","verifying"].includes(state.setupPhase);
  const acquisitionActive = jobsPort.acquisitionIsActive();
  const aneActive = jobsPort.aneWorkIsActive();
  const runtimeControlError = accelerationSelectionError() || (state.backend === "omlx" && $("accelerationSelect").value === "dflash" && $("anePrefillSelect").value === "tuned"
    ? "DFlash 2 and tuned ANE prefill cannot run in the same oMLX engine. Choose one."
    : state.backend === "omlx" && $("accelerationSelect").value === "dflash"
      && $("dflashVerifySelect").value === "ddtree" && $("omlxKv").value !== "off"
    ? "Quantized KV requires Adaptive or Fixed DFlash. DDTree needs full precision."
    : "");
  const modelReady = Boolean(
    model?.backends?.[state.backend]?.runnable && model?.ready
    && (state.backend !== "llamacpp" || registryPort.llamaCppPleQualified(model))
  );
  const warm = currentWarmRoutePlan();
  const admission = currentSessionAdmission();
  const controlsReady = Boolean(runtimeReady && modelReady && client.available && !limits && !chatError && !freeTokenError && !runtimeControlError && !state.applyingOptimal && !state.verifiedLaunchBusy && !savedPort.isBusy() && !benchmarkPort.view().calibrationStarting && !benchmarkPort.view().calibrationApplying && !routeCheckActive && !benchmarkActive && !setupActive && !acquisitionActive && !aneActive);
  const coldControlsReady = Boolean(controlsReady && !runActive);
  const coldLaunchable = Boolean(coldControlsReady && !state.launchPreparing);
  const warmLaunchable = Boolean(controlsReady && state.runPhase === "running" && warm?.canAttach);
  const launchable = (coldLaunchable || warmLaunchable) && !state.launchPreparing;
  $("launchButton").disabled = !launchable;
  $("launchButton").dataset.warm = warmLaunchable ? "true" : "false";
  // Capacity admission gates model loads, not read-only inspection or controls
  // that can move the user to a safer engine.  The actual Route Check and
  // Calibration start buttons apply the same admission below.
  $("routeCheckButton").disabled = !coldControlsReady;
  $("previewButton").disabled = !coldControlsReady;
  $("applyOptimal").disabled = !coldControlsReady;
  $("optimizerMenuButton").disabled = !coldControlsReady;
  $("optimizerVerifiedLaunch").disabled = !coldControlsReady;
  $("optimizerCalibrate").disabled = !coldControlsReady;
  collections.optimizerButtons.forEach(button => { button.disabled = !coldControlsReady; });
  $("homeFastestEngine").disabled = !coldControlsReady || Boolean(state.launchPreparing);
  $("homeFastestEngine").setAttribute("aria-busy", String(Boolean(state.applyingOptimal)));
  UiPresenter.property($("homeFastestEngine"), "textContent", state.applyingOptimal ? "Checking runtimes…" : "Choose fastest runtime");
  if (!coldControlsReady) closeOptimizerMenu();
  const supportEntries = (state.adapters?.workSurfaces || []).map(
    adapter => [adapter.id, resolvedClientSupport(state.backend, adapter.id, selected)],
  );
  const unsupported = supportEntries
    .filter(([name, support]) => !support.supported || !clientInstalled(name))
    .map(([name, support]) => `${formattingPort.clientName(name)} unavailable: ${clientInstalled(name) ? support.reason : "not installed"}`);
  const selectedSupportReason = resolvedClientSupport(state.backend, state.client, selected).reason || "Compatible local route";
  const selectedReason = state.backend === "uzu" && state.client === "chat"
    ? `Chat only for initial qualification · ${selectedSupportReason}`
    : selectedSupportReason;
  const compatibilityDetail = [selectedReason, ...unsupported].join(" · ");
  $("compatibilityLine").textContent = shellPort.activeDetail() === "detailed" ? compatibilityDetail : selectedReason;
  $("compatibilityLine").title = compatibilityDetail;
  let blocker = "";
  if (!runtimeReady) blocker = state.backend === "freetoken"
    ? "Install the native FreeToken port or connect a server."
    : `${formattingPort.backendName(state.backend)} is not installed.`;
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
  else if (coldControlsReady && !admission.actionReady && !["checking", "qualification"].includes(admission.decision)) blocker = sessionAdmissionBlockerCopy(admission);
  else if (acquisitionActive) blocker = "Model Acquisition owns the pinned download and verification until it finishes or is stopped.";
  else if (setupActive) blocker = "Setup Assistant owns the model download until it finishes or is stopped.";
  else if (routeCheckActive) blocker = "Route Check owns the temporary model until its synthetic probes finish or are stopped.";
  else if (benchmarkActive) blocker = "Benchmark Lab owns the model runtime until its comparison finishes or is stopped.";
  else if (aneActive) blocker = jobsPort.aneCloneIsActive()
    ? "FP16 copy preparation owns its private staging folder until it finishes or is stopped."
    : "ANE Tuner owns the private model engine until it finishes or is stopped.";
  else if (runActive && state.runPhase === "running" && warmLaunchable) blocker = "";
  else if (runActive && state.runPhase === "running" && state.warmRouteLoading) blocker = "Checking whether the visible controls exactly match the loaded model route…";
  else if (runActive && state.runPhase === "running") blocker = warm?.detail || "The visible route does not exactly match the loaded model. Open Sessions for details or stop it before loading another.";
  else if (runActive) blocker = "Wait for the active route transition to finish.";
  shellPort.showNotice(blocker || state.catalogNotice, Boolean(blocker));
  updateAccelerationState();
  scheduleWarmRoutePlan();
  updateWorkSurface();
  const admissionBlocked = Boolean(coldControlsReady && !admission.actionReady);
  $("launchButton").dataset.admission = admissionBlocked ? "blocked" : "ready";
  $("launchButton").title = admissionBlocked ? admission.detail : "";
  if (admissionBlocked) $("launchSummary").textContent = "Check & start";
  updateLaunchHome(admission);
  benchmarkPort.renderBenchmarkSetup();
  jobsPort.updateSetupControls();
  jobsPort.updateAcquisitionControls();
  if ($("runtimeDialog")?.open) jobsPort.updateRuntimeControls();
  jobsPort.updateAneControls();
  renderPerformanceReceipt();
  savedPort.renderQuickStart();
  savedPort.renderProfileEditBanner();
  if ($("profileDialog")?.open) savedPort.renderProfiles();
  if ($("calibrationDialog")?.open) benchmarkPort.renderCalibration();
  if ($("routeCheckDialog")?.open) preflightPort.renderRouteCheck();
  scheduleSessionAdmissionPlan();
}

function updateBackend(preserveOptimization = false, modelId = "") {
  if (!registryPort.uiEngineVisible(state.backend)) state.backend = "mtplx";
  if (state.backend !== "splash") updateSplashAcceleration();
  if (!preserveOptimization) cancelOptimization("Runtime changed; review or apply its recommended controls.");
  collections.backendButtons.forEach(button => button.classList.toggle("selected", button.dataset.backend === state.backend));
  $("mtplxControls").classList.toggle("hidden", state.backend !== "mtplx");
  $("omlxControls").classList.toggle("hidden", state.backend !== "omlx");
  $("lmstudioControls").classList.toggle("hidden", state.backend !== "lmstudio");
  $("uzuControls").classList.toggle("hidden", state.backend !== "uzu");
  $("freetokenControls").classList.toggle("hidden", state.backend !== "freetoken");
  $("swiftlmControls").classList.toggle("hidden", state.backend !== "swiftlm");
  $("mferenceControls").classList.toggle("hidden", state.backend !== "mference");
  const slotstreamQ8 = $("slotstreamKv").querySelector('option[value="q8"]');
  if (slotstreamQ8) slotstreamQ8.disabled = !selectedModel()?.backends?.slotstream?.kv;
  $("slotstreamControls").classList.toggle("hidden", state.backend !== "slotstream");
  $("splashControls").classList.toggle("hidden", state.backend !== "splash");
  $("strataControls").classList.toggle("hidden", state.backend !== "strata");
  $("recControls").classList.toggle("hidden", state.backend !== "rec");
  $("rapidmlxControls").classList.toggle("hidden", state.backend !== "rapidmlx");
  if (state.backend === "rapidmlx") {
    rapidDefaultsModelId = "";
  }
  $("kolibriControls").classList.toggle("hidden", state.backend !== "kolibri");
  $("whallmControls").classList.toggle("hidden", state.backend !== "whallm");
  $("llamacppControls").classList.toggle("hidden", state.backend !== "llamacpp");
  $("sharedRuntimeControls").classList.toggle("hidden", ["kolibri", "uzu", "freetoken", "swiftlm", "mference", "whallm", "splash", "strata", "rec", "llamacpp"].includes(state.backend));
  $("advancedSummary").textContent = ({
    mtplx:"MTPLX controls", omlx:"oMLX controls", lmstudio:"LM Studio controls",
    uzu:"Uzu · Mirai · fixed acceleration",
    freetoken:"FreeToken route controls", swiftlm:"SwiftLM SSD controls",
    mference:"Mference SSD controls", whallm:"Whallm SSD route", slotstream:"Slotstream · MTP and SSD",
    splash:"Splash · local models + DFlash2",
    strata:"Strata · Qwen3.8 Flash-Next",
    rec:"Rec · Flint reasoning and tools",
    rapidmlx:"Rapid MLX · AR and optional MTP",
    kolibri:"Kolibri SSD · KV, prefill and expert cache",
    llamacpp:"llama.cpp · SSD PLE route",
  })[state.backend];
  if (state.backend === "kolibri" || ["swiftlm", "mference", "whallm", "slotstream", "strata", "llamacpp"].includes(state.backend)) $("ssdRuntimeDisclosure").open = true;
  const swiftReady = Boolean(state.binaries?.swiftlm?.installed);
  const mferenceReady = Boolean(state.binaries?.mference?.installed);
  const whallmReady = Boolean(state.binaries?.whallm?.installed);
  const llamaCppReady = Boolean(state.binaries?.llamacpp?.installed);
  const llamaCppModel = registryPort.llamaCppPleModel();
  const llamaCppChecking = registryPort.llamaCppPleCheckingModel();
  const whallmModel = state.models.find(model => model.backends?.whallm?.runnable && (model.nativeWhallm || model.sharedServer === true));
  const whallmRoute = whallmModel ? registryPort.routeCapabilityPresentation(whallmModel.backends.whallm, {
    backend:"whallm", modelName:whallmModel.name, modelReady:whallmModel.ready,
  }) : null;
  const whallmModelReady = whallmRoute?.tone === "good";
  $("ssdRuntimeStatus").textContent = state.backend === "slotstream"
    ? (state.models.find(model => model.slotstream)?.backends?.slotstream?.reason || "Install the pinned Slotstream runtime and its Qwen model, then rescan.")
    : state.backend === "kolibri"
    ? (state.models.find(model => model.kolibri)?.backends?.kolibri?.reason || "Download the complete Kolibri Q6 model, then rescan.")
    : state.backend === "strata"
    ? (selectedModel()?.backends?.strata?.reason || state.models.find(model => model.strata)?.backends?.strata?.reason || "Select the launcher Strata split-GGUF runtime and rescan for the prepared Qwen3.8 Flash-Next route.")
    : state.backend === "splash"
    ? (selectedModel()?.backends?.splash?.reason || state.models.find(model => model.splash && model.backends?.splash?.runnable)?.backends?.splash?.reason || "Install Splash 1.5.0 and rescan for compatible GGUF files, including split Flash-Next GGUFs. Flash-Next requires GGUF; 27B and 35B also support MLX Q4.")
    : state.backend === "llamacpp"
    ? llamaCppModel
      ? "Pinned verified artifact route ready · fixed 8K context."
      : llamaCppChecking
        ? `Verifying the pinned artifact in this controller · ${formattingPort.formatNumber(llamaCppChecking.verificationProgress?.completed || 0)}/${formattingPort.formatNumber(llamaCppChecking.verificationProgress?.total || 28)} shards.`
      : llamaCppReady
        ? "Runtime found; no pinned verified artifact route is available yet."
        : "The verified artifact route is advertised, but its pinned runtime is not installed."
    : whallmModel?.nativeWhallm
    ? "Qwen3.8 Flash is installed. Launch starts its engine automatically with thinking enabled."
    : whallmRoute?.attention
    ? `${whallmRoute.label}. ${whallmRoute.detail || "Whallm can be selected explicitly, but it is not automatically preferred on this Mac."}`
    : whallmModelReady
    ? "Whallm's full-expert Qwen route is live. It stays separate from pruned or repacked checkpoint comparisons."
    : whallmReady
      ? "Whallm is installed; start its pinned Qwen server, then rescan. SwiftLM/Mference compare only matching artifacts."
      : swiftReady && mferenceReady
        ? "SwiftLM and Mference are installed; calibration needs artifacts proving one matching source revision."
        : `${swiftReady || mferenceReady ? "One paired-artifact runtime" : "No paired-artifact runtime"} installed · Whallm is a separate full-Qwen option.`;
  renderFreeTokenConnection();
  renderModelOptions(modelId);
}

function slotstreamDownloadMessage(model) {
  const install = model?.slotstream;
  if (!install || (install.ready && install.mtp)) return "";
  return `Slotstream download: ${Number(install.completeFiles || 0)} of ${Number(install.totalFiles || 25)} files complete. ${install.ready ? "The model can run; its MTP head is still missing." : "Launch becomes available after all required files pass verification."} This view refreshes while the download finishes.`;
}

function renderModelOptions(modelId = "") {
  const downloadStatus = $("slotstreamDownloadStatus");
  const downloadMessage = state.backend === "slotstream" ? slotstreamDownloadMessage(state.models.find(model => model.slotstream)) : "";
  downloadStatus.textContent = downloadMessage;
  downloadStatus.classList.toggle("hidden", !downloadMessage);
  const select = $("modelSelect");
  const previous = modelId || select.value;
  if (!registryPort.uiEngineVisible(state.backend)) state.backend = "mtplx";
  const visibleModels = state.models.filter(registryPort.uiModelVisible);
  const routePresentation = model => registryPort.routeCapabilityPresentation(model.backends?.[state.backend] || {}, {
    backend:state.backend, modelName:model.name, modelReady:model.ready,
  });
  const compatible = visibleModels.filter(model => routePresentation(model).available);
  const option = (model, disabled = false) => `<option value="${formattingPort.esc(model.id)}" ${disabled ? "disabled" : ""}>${formattingPort.esc(model.name)}${disabled ? ` — ${formattingPort.esc(model.backends?.[state.backend]?.reason || model.status)}` : ""}</option>`;
  if (state.backend === "freetoken") {
    const native = compatible.filter(model => freeTokenRoute(model) === "native");
    const remote = compatible.filter(model => freeTokenRoute(model) === "remote");
    const groups = [
      native.length ? `<optgroup label="Native on this Mac">${native.map(model => option(model)).join("")}</optgroup>` : "",
      remote.length ? `<optgroup label="Connected FreeToken server">${remote.map(model => option(model)).join("")}</optgroup>` : "",
    ].join("");
    const markup = groups || `<option value="">${state.freeToken?.native?.installed ? "Native port detected — no compatible local Qwen3-MoE checkpoint" : "Install the native port or connect a FreeToken server"}</option>`;
    if (select.dataset.catalog !== markup) { select.innerHTML = markup; select.dataset.catalog = markup; }
  } else {
    const markup = compatible.length
      ? compatible.map(model => option(model)).join("")
      : '<option value="">No compatible models — choose another engine or open Models</option>';
    if (select.dataset.catalog !== markup) { select.innerHTML = markup; select.dataset.catalog = markup; }
  }
  if (compatible.some(model => model.id === previous)) select.value = previous;
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
  $("repetitionPenaltyInput").value = String(defaults.repetition_penalty ?? 1);
  $("seedInput").value = "";
  updateChatSamplingControls();
}

function accelerationSelectionError(cap = selectedModel()?.backends?.[state.backend] || {}) {
  // These routes own acceleration and ignore the shared selector entirely.
  if (["uzu", "freetoken", "swiftlm", "mference", "whallm", "splash", "strata", "rec", "llamacpp"].includes(state.backend)) return "";
  const mode = $("accelerationSelect").value;
  if (state.backend === "rapidmlx" && !["auto", "off", "mtp"].includes(mode)) {
    return "Rapid MLX supports Auto, AR or MTP for this route. Choose an available mode.";
  }
  if (state.backend === "rapidmlx" && mode === "mtp" && cap.mtp !== true) {
    return "MTP is unavailable for this Rapid MLX model and runtime. Choose AR.";
  }
  if (state.backend === "rapidmlx" && !rapidMtpDepths(cap).includes(Number($("depthInput").value))) {
    return "Choose an MTP draft depth supported by this Rapid MLX model and runtime.";
  }
  if ((mode === "mtp" && !cap.mtp) || (mode === "dflash" && !cap.dflash)) {
    return `Selected ${mode === "mtp" ? "MTP" : "DFlash"} is unavailable. Restore its model files or explicitly choose another acceleration mode.`;
  }
  return "";
}

function clearUnavailableModelControls() {
  const acceleration = $("accelerationSelect");
  acceleration.querySelector('option[value="mtp"]').disabled = true;
  acceleration.querySelector('option[value="dflash"]').disabled = true;
  $("accelerationHelp").textContent = "Finish the model download to inspect its available acceleration.";
  $("contextInput").removeAttribute("max");
  $("outputInput").removeAttribute("max");
  updateAccelerationState();
  updateChatSamplingControls();
}

function modelChanged() {
  const model = selectedModel();
  if (state.backend === "splash") updateSplashAcceleration();
  const previousId = state.selected?.id || "";
  if (previousId && previousId !== (model?.id || "")) {
    cancelOptimization("Model changed; reapply the speed preset for this artifact.");
  }
  state.selected = model;
  const q8Option = $("slotstreamKv")?.querySelector('option[value="q8"]');
  if (q8Option) q8Option.disabled = model?.backends?.slotstream?.kv !== true;
  const card = $("modelCard");
  if (!model) {
    clearUnavailableModelControls();
    const freeTokenMissing = state.backend === "freetoken";
    card.innerHTML = freeTokenMissing
      ? state.freeToken?.native?.installed
        ? `<div class="model-title"><strong>No compatible native checkpoint</strong><span class="badge bad">Inspect</span></div><div class="model-meta"><span>The port is ready, but no complete local Qwen3-MoE checkpoint passed its fail-closed preflight. A remote server remains optional.</span></div>`
        : `<div class="model-title"><strong>FreeToken is unavailable</strong><span class="badge bad">Set up</span></div><div class="model-meta"><span>Install the native port or configure a server above.</span></div>`
      : `<div class="model-title"><strong>No launchable model</strong><span class="badge bad">Unavailable</span></div><div class="model-meta"><span>Try another runtime or finish the model download</span></div>`;
    updateFreeTokenNativeControls();
    renderDflashReadiness({});
    renderAneReadiness({});
    $("qwenPleMemoryControls").classList.add("hidden");
    $("omlxExpertControls").classList.add("hidden");
    $("memoryGuardSelect").value = "balanced";
    benchmarkPort.renderBenchmarkCard();
    refreshLaunchability();
    schedulePerformanceReceipt();
    return;
  }
  const cap = model.backends?.[state.backend] || {};
  if (state.backend === "rapidmlx" && rapidDefaultsModelId !== model.id) {
    const preferred = ["auto", "off", "mtp"].includes(cap.preferredAcceleration) ? cap.preferredAcceleration : "auto";
    $("accelerationSelect").value = preferred === "mtp" && cap.mtp !== true ? "off" : preferred;
    const choices = rapidMtpDepths(cap);
    $("depthInput").value = String(choices.includes(Number(cap.depth)) ? Number(cap.depth) : choices[0]);
    rapidDefaultsModelId = model.id;
  }
  const qwenPleRoute = state.backend === "omlx" && model.qwen4Ple?.supported === true;
  const expertOffloadRoute = qwenPleRoute && model.omlxExpertOffload?.supported === true;
  $("qwenPleMemoryControls").classList.toggle("hidden", !qwenPleRoute || expertOffloadRoute);
  $("omlxExpertControls").classList.toggle("hidden", !expertOffloadRoute);
  if (!qwenPleRoute) $("memoryGuardSelect").value = "balanced";
  updateFreeTokenNativeControls();
  applyModelChatDefaults(model);
  card.classList.remove("loading");
  const experimentalFreeToken = state.backend === "freetoken"
    && freeTokenRoute(model) === "native" && freeTokenQualification(model).experimental;
  const routePresentation = registryPort.routeCapabilityPresentation({
    ...cap,
    experimental:experimentalFreeToken || cap.experimental === true,
  }, {backend:state.backend, modelName:model.name, modelReady:model.ready});
  const statusClass = routePresentation.tone;
  const statusLabel = routePresentation.label || model.status;
  const statusTitle = routePresentation.detail
    ? ` title="${formattingPort.esc(routePresentation.detail)}"` : "";
  const pleChip = model.qwen4Ple?.supported === true
    ? model.omlxExpertOffload?.supported === true
      ? `<span>Experts and ngrams on SSD</span><span>RAM cache adjustable</span>`
      : `<span>N-gram PLE on SSD</span><span>${formattingPort.esc(formattingPort.formatBytes(model.qwen4Ple.residentBytes || 0))} estimated resident</span>`
    : "";
  const ssdChip = model.ssdStreaming?.recommended === true
    ? `<span>SSD streaming recommended</span>`
    : model.ssdStreaming?.candidate === true ? `<span>SSD streaming optional</span>` : "";
  card.innerHTML = `<div class="model-title"><strong>${formattingPort.esc(model.name)}</strong><span class="badge ${statusClass}"${statusTitle}>${formattingPort.esc(statusLabel)}</span></div><div class="model-meta"><span>${formattingPort.esc(model.format.toUpperCase())}</span><span>${formattingPort.esc(model.quantization)}</span><span>${formattingPort.esc(model.sizeLabel)}</span><span>${formattingPort.esc(formattingPort.modelContextLabel(model, cap, state.backend))}</span>${pleChip}${ssdChip}<span>${formattingPort.esc(model.origins.join(" + "))}</span><span>${formattingPort.esc(cap.reason)}</span></div>`;
  const nativeTopK = Number(cap.nativeExpertTopK || 0);
  $("swiftlmTopK").value = String(Number.isInteger(nativeTopK) && nativeTopK > 0 ? nativeTopK : 0);
  $("swiftlmTopKHelp").textContent = nativeTopK > 0
    ? `Locked to this checkpoint's native top-${nativeTopK} routing.`
    : "The runtime reads native routing from the checkpoint; no approximation is applied.";
  const rapidMaximum = state.backend === "rapidmlx" ? Number(cap.contextMaximum) : 0;
  const contextMaximum = rapidMaximum > 0 ? Math.min(rapidMaximum, model.nativeContext || rapidMaximum) : model.nativeContext;
  if (contextMaximum) $("contextInput").max = contextMaximum;
  else $("contextInput").removeAttribute("max");
  const contextWindows = selectedContextWindows(cap);
  const runtimeWindows = Array.isArray(contextWindows) ? contextWindows.map(Number).filter(value => Number.isInteger(value) && (!rapidMaximum || value <= rapidMaximum)) : [];
  const reconciledLimits = LLMRoutePreferenceCore.reconcileRuntimeLimits({
    context:Number($("contextInput").value),
    output:Number($("outputInput").value),
    contextWindows:runtimeWindows,
    outputMaximum:cap.outputMaximum || model.outputMaximum,
  });
  if (cap.outputMaximum || model.outputMaximum) $("outputInput").max = String(cap.outputMaximum || model.outputMaximum);
  else $("outputInput").removeAttribute("max");
  if (reconciledLimits.contextChanged) {
    $("contextInput").value = String(reconciledLimits.context);
  }
  if (reconciledLimits.outputChanged) {
    $("outputInput").value = String(reconciledLimits.output);
    cancelOptimization(
      `${formattingPort.backendName(state.backend)} uses a ${formattingPort.formatNumber(reconciledLimits.context)}-token window, so max response was reduced to ${formattingPort.formatNumber(reconciledLimits.output)} to preserve ${formattingPort.formatNumber(reconciledLimits.promptBudget)} tokens for instructions and history.`,
    );
  }
  if (runtimeWindows.length) {
    $("contextInput").title = `${formattingPort.backendName(state.backend)} context choices: ${runtimeWindows.map(formattingPort.formatNumber).join(", ")}`;
  } else $("contextInput").removeAttribute("title");
  const acceleration = $("accelerationSelect");
  [...acceleration.options].forEach(option => { option.disabled = false; });
  const mtp = acceleration.querySelector('option[value="mtp"]');
  const dflash = acceleration.querySelector('option[value="dflash"]');
  mtp.disabled = !cap.mtp;
  dflash.disabled = !cap.dflash;
  if (cap.mtp || cap.dflash) {
    $("depthInput").max = String(Math.max(1, Number(cap.depthMax || 1)));
    if (Number($("depthInput").value) > Number($("depthInput").max)) $("depthInput").value = String(cap.depth || 1);
  } else $("depthInput").max = "8";
  setRangeVisual($("depthInput"), $("depthValue"));
  setRangeVisual($("parallelInput"), $("parallelValue"));
  const available = [cap.mtp ? "MTP" : "", state.backend !== "rapidmlx" && cap.dflash ? "DFlash 2" : ""].filter(Boolean);
  $("accelerationHelp").textContent = accelerationSelectionError(cap) || (available.length ? `${available.join(" and ")} available for this exact runtime/model route.` : cap.mtpReason || "No verified speculative path.");
  renderDflashReadiness(cap);
  renderAneReadiness(cap);
  benchmarkPort.renderBenchmarkCard();
  refreshLaunchability();
  schedulePerformanceReceipt();
}

async function loadModels(userTriggered = false) {
  if (state.modelVerificationLoading) return;
  state.modelVerificationLoading = true;
  if (state.modelVerificationTimer) platform.clearTimeout(state.modelVerificationTimer);
  state.modelVerificationTimer = null;
  if (userTriggered) cancelOptimization("Model capabilities were rescanned; reapply the current speed preset.");
  $("refreshModels").disabled = true;
  $("refreshModels").textContent = "Scanning models…";
  $("refreshModels").title = "Refreshing configured model folders.";
  try {
    const data = await api("/api/models");
    state.models = data.models;
    assetsPort.invalidateLibrary();
    const incompleteOrnith = state.models.find(model => /ornith/i.test(model.name) && !model.ready);
    state.catalogNotice = incompleteOrnith ? `${incompleteOrnith.name} is detected but still downloading. It becomes selectable after every weight shard finishes.` : "";
    renderModelOptions();
    const checking = state.models.find(model => model.verificationState === "checking");
    if (savedPort.shortcutsLoaded() && !checking) void savedPort.loadQuickStart(true);
    if (checking) {
      const completed = Number(checking.verificationProgress?.completed || 0);
      const total = Number(checking.verificationProgress?.total || 28);
      $("refreshModels").textContent = "Verifying pinned model…";
      $("refreshModels").title = `${formattingPort.formatNumber(completed)} / ${formattingPort.formatNumber(total)} shards checked in this controller.`;
      state.modelVerificationTimer = platform.setTimeout(() => { void loadModels(false); }, 700);
    }
  } catch (error) { shellPort.showNotice(error.message, true); }
  finally {
    state.modelVerificationLoading = false;
    const checking = state.models.some(model => model.verificationState === "checking");
    $("refreshModels").disabled = checking;
    if (!checking) {
      $("refreshModels").textContent = "Rescan models";
      $("refreshModels").title = "Refresh configured model folders.";
    }
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
    return `Metal hot experts must be blank or a whole number from 0 to ${formattingPort.formatNumber(maximumExperts)}.`;
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
    `${formattingPort.formatNumber(batch)} active sequence${batch === 1 ? "" : "s"}`,
    expert === "" ? "resident Metal experts" : `${formattingPort.formatNumber(expert)} hot Metal experts`,
    prefix ? `${formattingPort.formatNumber(prefix)} cached prefixes` : "prefix cache off",
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
  if (!registryPort.uiFeatureEnabled("freetoken")) {
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
    $("freeTokenConnectionDetail").textContent = `${formattingPort.formatNumber(connection.modelCount)} live model${Number(connection.modelCount) === 1 ? "" : "s"} · ${connection.transportEncrypted ? "encrypted HTTPS" : "HTTP transport"} · checked ${connection.checkedAt ? new Date(connection.checkedAt).toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"}) : "recently"}`;
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
  $("freeTokenBadge").textContent = state.freeTokenBusy ? "Checking" : connected ? `${formattingPort.formatNumber(connection.modelCount)} models` : "Not connected";
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
    ? `<strong>${formattingPort.esc(connection.server || "FreeToken API")}</strong><span title="${formattingPort.esc((connection.models || []).join(", "))}">${formattingPort.esc((connection.models || []).join(" · "))}</span>`
    : "<strong>No server connected</strong><span>Add its private address to discover available models.</span>";
  $("freeTokenDisconnect").disabled = state.freeTokenBusy || !connected;
  $("freeTokenConnect").disabled = state.freeTokenBusy;
  $("freeTokenEndpoint").disabled = state.freeTokenBusy;
  $("freeTokenApiKey").disabled = state.freeTokenBusy;
  $("freeTokenContext").disabled = state.freeTokenBusy;
  updateFreeTokenNativeControls();
}

function openFreeTokenDialog() {
  if (!registryPort.uiFeatureEnabled("freetoken")) return;
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
  if (!registryPort.uiFeatureEnabled("freetoken")) return;
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
    registryPort.useRuntimes(data.binaries || state.binaries);
    registryPort.useAdapters(data.adapters || state.adapters);
    state.models = data.models || [];
    assetsPort.invalidateLibrary();
    state.backend = "freetoken";
    $("freeTokenStatus").textContent = `Connected. ${formattingPort.formatNumber(state.freeToken.modelCount)} model${Number(state.freeToken.modelCount) === 1 ? "" : "s"} discovered; no model was started or stopped.`;
    renderFreeTokenConnection(true);
    renderModelOptions();
    registryPort.applyBootstrapData({binaries:state.binaries, adapters:state.adapters, freeToken:state.freeToken});
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
  if (!registryPort.uiFeatureEnabled("freetoken")) return;
  if (state.freeTokenBusy || !state.freeToken?.connected) return;
  if (!platform.confirm("Disconnect this launcher from FreeToken? The remote server and loaded model will keep running.")) return;
  state.freeTokenBusy = true;
  $("freeTokenStatus").className = "freetoken-status";
  $("freeTokenStatus").textContent = "Removing the launcher connection…";
  renderFreeTokenConnection();
  try {
    const data = await api("/api/freetoken/disconnect", {method:"POST", body:"{}"});
    state.freeToken = data.freeToken;
    registryPort.useRuntimes(data.binaries || state.binaries);
    registryPort.useAdapters(data.adapters || state.adapters);
    state.models = data.models || [];
    assetsPort.invalidateLibrary();
    $("freeTokenStatus").textContent = "Launcher disconnected. The FreeToken server and its model were not stopped.";
    renderModelOptions();
    registryPort.applyBootstrapData({binaries:state.binaries, adapters:state.adapters, freeToken:state.freeToken});
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
  if (state.backend === "rapidmlx" && key === "depth") return $("rapidmlxDepthSelect").closest(".optimizable");
  const control = $(policy.optimizerControls[key]);
  return control?.closest(".optimizable") || null;
}

async function revealFirstChangedControl(keys) {
  const field = keys.map(fieldForKey).find(Boolean);
  const scroller = nodes.configScroll;
  if (!field || !scroller) return;
  await new Promise(resolve => platform.requestAnimationFrame(resolve));
  const fieldRect = field.getBoundingClientRect();
  const scrollRect = scroller.getBoundingClientRect();
  if (fieldRect.top >= scrollRect.top && fieldRect.bottom <= scrollRect.bottom) return;
  const delta = fieldRect.top < scrollRect.top
    ? fieldRect.top - scrollRect.top - 12
    : fieldRect.bottom - scrollRect.bottom + 12;
  scroller.scrollTo({top: scroller.scrollTop + delta, behavior: shellPort.reducedMotion() ? "auto" : "smooth"});
}

function optimizerValueMatches(key, expected) {
  const control = $(policy.optimizerControls[key]);
  if (!control) return false;
  if (expected === null || expected === undefined) return control.value === "";
  return control.type === "range"
    ? Number(control.value) === Number(expected)
    : control.value === String(expected);
}

async function animateRange(input, target, generation) {
  const start = Number(input.value), end = Number(target);
  if (!Number.isFinite(end)) return;
  const output = formattingPort.rangeOutputFor(input);
  if (shellPort.reducedMotion() || start === end) {
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
      if (progress < 1) platform.requestAnimationFrame(frame); else resolve();
    };
    platform.requestAnimationFrame(frame);
  });
}

async function animateOptimalControl(key, value, generation) {
  const rapidDepth = state.backend === "rapidmlx" && key === "depth";
  const control = $(rapidDepth ? "rapidmlxDepthSelect" : policy.optimizerControls[key]);
  const field = fieldForKey(key);
  if (!control || !field || (control.disabled && !rapidDepth) || field.closest(".hidden")) return;
  field.classList.remove("optimized");
  field.classList.add("optimizing");
  if (control.type === "range") await animateRange(control, value, generation);
  else if (control.tagName === "SELECT") {
    const option = [...control.options].find(item => item.value === String(value) && !item.disabled);
    if (!option) { field.classList.remove("optimizing"); return; }
    control.value = String(value);
    if (!shellPort.reducedMotion()) await sleep(150);
  } else {
    control.value = value === null || value === undefined ? "" : String(value);
    if (!shellPort.reducedMotion()) await sleep(150);
  }
  if (generation !== state.optimizationGeneration) return;
  control.dispatchEvent(new platform.Event("change", {bubbles:true}));
  field.classList.remove("optimizing");
  field.classList.add("optimized");
  platform.setTimeout(() => field.classList.remove("optimized"), 600);
}

async function applyOptimal(scope = "current", enginePreference = "throughput", openCalibrationOnMissing = true, evidenceBinding = null) {
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
      ? `Checking ${policy.enginePreferenceLabels[enginePreference] || "the selected goal"} evidence across every compatible installed engine.`
      : "Checking this model and runtime's evidence.",
  );
  refreshLaunchability();
  let applyError = "";
  let applied = false;
  let calibrationFallback = null;
  try {
    const bindingScope = engineSelection ? "engine" : "route";
    const suppliedBinding = evidenceBinding === null
      ? activeEvidenceBindingFor(bindingScope, enginePreference)
      : copiedEvidenceBinding(evidenceBinding);
    if (evidenceBinding !== null && !suppliedBinding) {
      throw new Error("That measured result reference is no longer valid. Refresh Calibration before applying it.");
    }
    const request = {
      backend:state.backend, modelId:model.id, client:state.client,
      context:Number($("contextInput").value), output:Number($("outputInput").value),
      reasoning:$("reasoningSelect").value,
      options:gatherOptions(),
      generation:gatherGenerationSettings(),
    };
    if (engineSelection) request.enginePreference = enginePreference;
    if (suppliedBinding) request.evidenceBinding = suppliedBinding;
    if (state.client === "chat") request.chat = gatherChatSettings();
    const endpoint = engineSelection ? "/api/optimal-engine" : "/api/optimal";
    const data = await api(endpoint, {method:"POST", body:JSON.stringify(request)});
    const result = data.optimization;
    if (generation !== state.optimizationGeneration || selectedModel()?.id !== result.modelId) return;
    if (!registryPort.uiEngineVisible(result.backend)) {
      throw new Error("The measured result points to an engine that is temporarily hidden in this launcher build.");
    }
    if (!engineSelection && state.backend !== result.backend) throw new Error("The current-engine optimiser returned a different runtime.");
    if (result.backend === "mtplx") {
      const requestedOperatorRoute = result.options?.mtplxOperatorRoute;
      const operatorRoute = registryPort.mtplxOperatorRouteFromOptimization(
        result, engineSelection, model, Number($("contextInput").value),
      );
      result.options = {...(result.options || {}), mtplxOperatorRoute:operatorRoute};
      const routeKey = "mtplxOperatorRoute";
      const currentOperatorRoute = $("mtplxOperatorRouteSelect").value;
      result.changedKeys = (Array.isArray(result.changedKeys) ? result.changedKeys : [])
        .filter(key => key !== routeKey);
      if (currentOperatorRoute !== operatorRoute) result.changedKeys.push(routeKey);
      result.appliedKeys = (Array.isArray(result.appliedKeys) ? result.appliedKeys : [])
        .filter(key => key !== routeKey);
      result.appliedKeys.push(routeKey);
      if (
        requestedOperatorRoute === policy.MTPLX_OPERATOR_ROUTE_2111
        && operatorRoute === policy.MTPLX_OPERATOR_ROUTE_DEFAULT
      ) {
        const rationaleKey = engineSelection ? "engineRationale" : "rationale";
        result[rationaleKey] = [
          "The 2.11.1 long-context choice stayed on Runtime default because this result did not carry matching local measurement evidence.",
          ...(Array.isArray(result[rationaleKey]) ? result[rationaleKey] : []),
        ];
      }
    }
    const nextAction = engineSelection ? result.engineNextAction : null;
    if (nextAction?.id === "calibrate") {
      clearActiveEvidenceBinding();
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
      const changed = result.changedKeys
        .filter(key => policy.optimizerControls[key])
        .sort((left, right) => Number(left === "mtplxOperatorRoute") - Number(right === "mtplxOperatorRoute"));
      if (changed.length) {
        $("advancedControls").open = true;
        await revealFirstChangedControl(changed);
      }
      for (const key of changed) {
        await animateOptimalControl(key, result.options[key], generation);
        if (generation !== state.optimizationGeneration) return;
        if (!shellPort.reducedMotion()) await sleep(45);
      }
      if (protectedSnapshot(!engineSelection) !== protectedBefore) throw new Error("A protected intelligence or context control changed; optimisation was cancelled.");
      const mismatch = result.appliedKeys
        .filter(key => policy.optimizerControls[key])
        .find(key => !optimizerValueMatches(key, result.options[key]));
      if (mismatch) throw new Error(`The ${mismatch} control did not reach the verified value; optimisation was cancelled.`);
      state.optimalSignature = speedSignature();
      const operatorResultLabel = result.backend === "mtplx"
        ? registryPort.mtplxOperatorRouteLabel(result.options) : "";
      const resultLabel = operatorResultLabel || (engineSelection
        ? (result.engineEvidenceLabel || result.evidenceLabel)
        : result.evidenceLabel);
      state.optimalLabel = resultLabel;
      const visibleRationale = engineSelection && result.engineRationale?.length
        ? result.engineRationale
        : result.rationale;
      const detail = changed.length
        ? `${changed.length} control${changed.length === 1 ? "" : "s"} updated · ${visibleRationale.join(" ")}`
        : `Already using this setup · ${visibleRationale.join(" ")}`;
      setOptimizationState("applied", resultLabel, detail);
      const returnedBinding = copiedEvidenceBinding(
        (engineSelection ? result.engineEvidenceBinding : result.evidenceBinding)
        || result.evidenceBinding || suppliedBinding,
      );
      if (
        returnedBinding?.scope === bindingScope
        && returnedBinding.preference === enginePreference
      ) rememberActiveEvidenceBinding(returnedBinding);
      else clearActiveEvidenceBinding();
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
    clearActiveEvidenceBinding();
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
      if (applyError) shellPort.showNotice(applyError, true);
    }
  }
  if (openCalibrationOnMissing && calibrationFallback && generation === state.optimizationGeneration) {
    await benchmarkPort.openCalibrationAssistant({
      source:"optimizer-result",
      preference:calibrationFallback.preference,
      decision:calibrationFallback.decision,
    });
  }
  if (applied && generation === state.optimizationGeneration) {
    persistVisibleRoute();
    schedulePerformanceReceipt(true);
  }
  return applied;
}

async function prepareVerifiedQuickLaunch(enginePreference = "throughput") {
  if (state.applyingOptimal || jobsPort.routeCheckIsActive()) return;
  const applied = await applyOptimal("engine", enginePreference);
  if (!applied) return;
  preflightPort.setIntent("verified-launch");
  await preflightPort.openRouteCheck("verified-launch");
}

async function preview() {
  try {
    shellPort.showNotice("");
    const data = await api("/api/preview", {method:"POST", body:JSON.stringify(gather("custom"))});
    const plan = data.plan;
    const warnings = [plan.runtimeAdvisory?.detail, ...(plan.warnings || [])].filter(Boolean);
    const chatSampling = plan.client === "chat"
      ? ` · ${plan.chat.sampling === "custom" ? `temperature ${plan.chat.temperature}, top P ${plan.chat.topP}, top K ${plan.chat.topK}, presence ${plan.chat.presencePenalty}, frequency ${plan.chat.frequencyPenalty}${plan.chat.seed === null ? "" : `, seed ${plan.chat.seed}`}` : "model sampling defaults"}`
      : "";
    $("previewContent").innerHTML = `
      <div class="preview-row"><span>Engine</span><code>${formattingPort.esc(plan.engineCommand)}</code></div>
      <div class="preview-row"><span>Work surface</span><code>${formattingPort.esc(plan.clientCommand)}</code></div>
      <div class="preview-row"><span>Contract</span><code>${formattingPort.esc(`${formattingPort.formatNumber(plan.context)} context · ${formattingPort.formatNumber(plan.output)} output · ${plan.reasoning} reasoning${chatSampling} · model localhost:${plan.port}${plan.clientPort !== plan.port ? ` · ${plan.purpose === "session" ? "private session relay" : "compatibility guard"} localhost:${plan.clientPort}` : ""}`)}</code></div>
      ${warnings.length ? `<ul class="warning-list">${warnings.map(warning => `<li>${formattingPort.esc(warning)}</li>`).join("")}</ul>` : ""}`;
    $("previewDialog").showModal();
  } catch (error) { shellPort.showNotice(error.message, true); }
}

function renderLaunchMemoryEstimate(admission) {
  const element = $("launchMemoryEstimate");
  if (!element) return;
  const estimate = admission.known && admission.signature === state.sessionAdmissionSignature
    ? state.sessionDashboard?.admission?.estimate : null;
  const bytes = Number(estimate?.estimatedWorkingSetBytes);
  let label = "Checking memory…";
  let detail = "The estimate updates automatically for your model and settings. Click for memory details.";
  if (admission.warm) {
    label = "Reusing engine";
    detail = "This launch reuses the running engine. It loads model weights on demand if needed.";
  } else if (estimate?.remoteEngine || estimate?.sharedEngine) {
    label = "Model managed by server";
    detail = estimate.basis || "The connected server owns model memory.";
  } else if (estimate && estimate.geometryReady !== false && Number.isFinite(bytes) && bytes > 0) {
    label = `Est. peak ~${(bytes / 1024 ** 3).toFixed(1)} GiB`;
    detail = `Full-context session estimate including model, cache and runtime reserve. Actual peaks during prompt processing can vary. Excludes macOS and other apps; ${(Number(estimate.osReserveBytes || 0) / 1024 ** 3).toFixed(1)} GiB is reserved separately for macOS. Click for details.`;
  } else if (!admission.pending && admission.decision !== "checking") {
    label = "Memory estimate unavailable";
    detail = admission.detail || "Finish the model settings to estimate memory.";
  }
  element.textContent = label;
  element.title = detail;
  element.dataset.pressure = String(["pressure", "review"].includes(admission.decision));
}

function updateLaunchHome(admission = currentSessionAdmission()) {
  renderLaunchMemoryEstimate(admission);
  homeModelGroups = LauncherHomeCore.modelRouteGroups(state.models, visibleRouteCatalog(), formattingPort.backendName);
  launchHome.update(admission, homeModelGroups);
}

function renderLaunchPreparation(value) {
  $("launchPreparation").hidden = false;
  $("launchPreparation").dataset.phase = value.phase;
  $("launchPreparationTitle").textContent = value.title;
  $("launchPreparationDetail").textContent = value.detail;
  const progress = $("launchPreparationProgress");
  progress.hidden = ["error", "review", "done"].includes(value.phase);
  if (Number.isFinite(value.progress)) progress.value = Math.max(0, Math.min(1, value.progress));
  else progress.removeAttribute("value");
  $("continueLaunchPreparation").hidden = value.phase !== "review";
  $("cancelLaunchPreparation").textContent = value.phase === "error" ? "Dismiss" : "Cancel";
  $("cancelLaunchPreparation").disabled = ["starting", "stopping"].includes(value.phase);
  $("launchPreparationMark").textContent = value.phase === "error" ? "!" : value.phase === "review" ? "!" : "◌";
}

async function startSimpleLaunch() {
  if (state.launchPreparing) return;
  if (currentWarmRoutePlan()?.canAttach) return launch();
  let original;
  try { original = gather("custom", false); }
  catch (error) { shellPort.showNotice(error.message, true); return; }
  const signature = JSON.stringify(original);
  state.launchPreparing = true;
  activeLaunchFlow = LaunchFlow.create({
    api,
    update:renderLaunchPreparation,
    isCurrent:() => visibleSessionAdmissionSignature() === signature,
    review:admission => new Promise(resolve => {
      launchReviewResolve = resolve;
      renderLaunchPreparation({phase:"review", title:"This setup needs more memory", detail:admission.detail});
    }),
  });
  refreshLaunchability();
  try {
    const request = await activeLaunchFlow.prepare(original);
    renderLaunchPreparation({phase:"starting", title:"Opening your session", detail:"Loading the model and checking the connection…"});
    // /api/launch revalidates capacity and the optional exact acknowledgement
    // again at the model-load boundary; no browser decision bypasses it.
    const accepted = await launch(request, {admissionChecked:true});
    if (!accepted) throw new Error($("notice").textContent || "The model could not start. Try again.");
    $("launchPreparation").hidden = true;
  } catch (error) {
    renderLaunchPreparation({phase:"error", title:/cancelled/i.test(error.message) ? "Launch cancelled" : "Couldn’t start this session", detail:error.message});
  } finally {
    state.launchPreparing = false;
    activeLaunchFlow = null;
    launchReviewResolve = null;
    refreshLaunchability();
  }
}

function cancelSimpleLaunch() {
  activeLaunchFlow?.cancel();
  if (launchReviewResolve) { launchReviewResolve(false); launchReviewResolve = null; }
  if (!state.launchPreparing) $("launchPreparation").hidden = true;
  else renderLaunchPreparation({phase:"stopping", title:"Cancelling launch", detail:"Stopping any capacity test started by this launch…"});
}

async function launch(requestOverride = null, launchOptions = {}) {
  try {
    shellPort.showNotice("Validating the visible settings…");
    const request = requestOverride && typeof requestOverride === "object" && requestOverride.backend
      ? requestOverride : gather("custom");
    const warm = requestOverride
      ? (launchOptions.warmPlan?.canAttach && launchOptions.warmPlan?.confirmation
        ? launchOptions.warmPlan : null)
      : currentWarmRoutePlan();
    if (!warm && launchOptions.admissionChecked !== true && !await requireFreshSessionAdmission()) return false;
    const opensLauncherSurface = request.client === "chat";
    let currentChatSavedForSurface = false;
    if (surfacesPort.chatView().surfaceId && opensLauncherSurface) {
      if (!await surfacesPort.saveChatBeforeSurfaceExit("open that work surface again")) return false;
      currentChatSavedForSurface = true;
    }
    if (warm?.canAttach && warm.confirmation) {
      request.warmRouteConfirmation = warm.confirmation;
      const data = await api("/api/session/warm-attach", {
        method:"POST", body:JSON.stringify(request),
      });
      runEpoch+=1;
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
        if (await surfacesPort.enterChatSurface(data.attachment, {currentChatSaved:currentChatSavedForSurface})) {
          shellPort.showNotice("Warm Chat opened on the loaded model. The engine and model weights were not reloaded.");
        }
      } else if (data.attachment.agentHost === "console") {
        surfacesPort.enterAgentConsole(data.attachment);
        shellPort.showNotice(`${data.attachment.surface} opened in Hub Console on the loaded model. No model weights were reloaded.`);
      } else {
        shellPort.showNotice(`${data.attachment.surface} opened in Terminal on the loaded model. No model weights were reloaded.`);
      }
      scheduleWarmRoutePlan(true);
      if ($("sessionDialog")?.open) await loadSessionDashboard();
      return true;
    }
    const data = await api("/api/launch", {method:"POST", body:JSON.stringify(request)});
    runEpoch+=1;retireIdlePolicy();
    state.sessionAcknowledgementId = "";
    if (data.run.client === "chat") {
      surfacesPort.initializePrimaryChat(data.run);
    } else if (data.run.agentHost === "console") {
      surfacesPort.enterAgentConsole({
        id:data.run.runId, ownerRunId:data.run.runId, primary:true,
        client:data.run.client, surface:formattingPort.clientName(data.run.client),
        backend:data.run.backend, model:data.run.model, project:data.run.project,
        context:data.run.context, output:data.run.output, reasoning:data.run.reasoning,
        agentHost:"console", status:"starting", detail:"Loading the model before Hub Console opens.",
      });
    }
    shellPort.showNotice(data.verifiedLaunch ? "Verified route accepted. Starting the selected work surface…" : "");
    renderRun({phase:"preflight", message:"Launch accepted. Running preflight…", run:data.run, events:[]});
    return true;
  } catch (error) {
    shellPort.showNotice(error.message, true);
    if (/Open Sessions/i.test(error.message)) await openSessionDashboard();
    return false;
  }
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
    setMarkup($("sessionCacheFacts"), [
      ["Engine", report.engineResident ? "Resident" : "Not loaded"],
      ["Policy", policyLabel],
      ["Observed turns", formattingPort.formatNumber(report.observationCount || 0)],
      ["Cache reports", formattingPort.formatNumber(report.cacheTelemetryReportedTurns || 0)],
      ["Confirmed reuse", formattingPort.formatNumber(report.confirmedHitTurns || 0)],
      ["Reported token reuse", rate],
    ].map(([label,value]) => `<span><small>${formattingPort.esc(label)}</small><b title="${formattingPort.esc(value)}">${formattingPort.esc(value)}</b></span>`).join(""));
    if (last) {
      const turnState = last.interrupted ? "Interrupted" : last.completed ? "Completed" : "Ended";
      const cacheDetail = last.cacheTelemetryReported
        ? `${formattingPort.formatNumber(last.cachedPromptTokens || 0)} of ${formattingPort.formatNumber(last.promptTokens || 0)} prompt tokens reported cached`
        : last.usageReported ? "Token usage reported; cache detail omitted" : "Runtime usage omitted";
      const timing = last.ttftSeconds !== null && last.ttftSeconds !== undefined
        && Number.isFinite(Number(last.ttftSeconds))
        ? ` · first output ${Number(last.ttftSeconds).toFixed(2)}s` : "";
      setMarkup($("sessionCacheLast"), `<strong>${formattingPort.esc(`${turnState} Chat turn`)}</strong><span>${formattingPort.esc(`${cacheDetail}${timing}`)}</span>`);
    } else {
      setMarkup($("sessionCacheLast"), "<strong>No observed Chat turns</strong><span>Built-in Chat reports appear here when the runtime exposes authoritative usage.</span>");
    }
    $("sessionCacheCoverage").textContent = report.coverage?.detail
      || "Only controller-relayed built-in Chat turns are counted; direct agent traffic is never guessed.";
  }

  if ($("chatCacheState")) {
    $("chatCacheState").textContent = report.label || "Cache state unavailable";
    const lastDetail = last?.cacheTelemetryReported
      ? `${formattingPort.formatNumber(last.cachedPromptTokens || 0)} cached prompt tokens in the latest observed turn.`
      : report.detail;
    $("chatCacheDetail").textContent = lastDetail || "Timing alone is not treated as a cache hit.";
    $("chatCacheState").parentElement.dataset.state = report.state || "idle";
    const cacheSignal = $("chatStatusCache");
    if (cacheSignal) {
      const compact = ChatStatusCore.cacheSummary(report);
      $("chatStatusCacheValue").textContent = compact.value;
      cacheSignal.dataset.state = compact.state;
      cacheSignal.title = lastDetail || "Cache reuse is shown only from runtime-reported token fields.";
      surfacesPort.updateChatStatusSummaryLabel();
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
  const latestMeasured = recent.find(request => formattingPort.requestTps(request));
  const latestSpeed = formattingPort.requestTps(latestMeasured);
  const liveMeasured = active.find(request => formattingPort.requestTps(request)?.primaryKind === "live");
  const liveSpeed = formattingPort.requestTps(liveMeasured);
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
        ? formattingPort.formatShortDuration(policy.remainingSeconds)
        : policy.enabled ? "Waiting for relay" : "Off";
    setMarkup($("sessionActivityFacts"), [
      ["Engine lanes", formattingPort.formatNumber(report.lanes || 0)],
      ["Generating", formattingPort.formatNumber(report.activeCount || 0)],
      ["Waiting", formattingPort.formatNumber(report.queuedCount || 0)],
      ["Surfaces", formattingPort.formatNumber(report.surfaces?.length || 0)],
      [liveSpeed ? "Live TPS" : "Latest measured TPS", latestTps],
      ["Idle unload", idleValue],
    ].map(([label,value]) => `<span><small>${formattingPort.esc(label)}</small><b title="${formattingPort.esc(value)}">${formattingPort.esc(value)}</b></span>`).join(""));
    if (headlineSpeed) $("sessionActivityFacts").querySelectorAll("b")[4].title = headlineSpeed.label;

    const requestRow = (request, historical = false) => {
      const running = request.state === "running";
      const waiting = request.state === "queued" || request.state === "cancelling";
      const speed = formattingPort.requestTps(request);
      const liveDetail = formattingPort.liveRequestDetail(request);
      const completedDetail = formattingPort.completedRequestDetail(request);
      const timing = running
        ? `${formattingPort.liveRequestPhaseLabel(request) || "Generating"} · ${formattingPort.formatShortDuration(request.runSeconds)}${speed ? ` · ${speed.label}` : ""}${liveDetail ? ` · ${liveDetail}` : ""}${request.firstOutputSeconds !== null && request.firstOutputSeconds !== undefined ? ` · first output ${formattingPort.formatShortDuration(request.firstOutputSeconds)}` : " · awaiting first output"}`
        : waiting
          ? `${request.state === "cancelling" ? "Cancelling" : `Queue #${formattingPort.formatNumber(request.queuePosition || 1)}`} · ${formattingPort.formatShortDuration(request.waitSeconds)} waiting`
          : `${String(request.result || "completed").replaceAll("-", " ")} · ${formattingPort.formatShortDuration(request.runSeconds || 0)}${speed ? ` · ${speed.label}` : " · TPS unavailable"}${completedDetail ? ` · ${completedDetail}` : ""}`;
      const protocol = request.protocol === "responses" ? "Responses" : request.protocol === "chat-completions" ? "Chat Completions" : "local API";
      const cancel = !historical && request.canCancel
        ? `<button type="button" data-session-cancel-request="${formattingPort.esc(request.id)}" data-session-request-surface="${formattingPort.esc(request.surfaceId || "")}"${state.requestCancelBusyId ? " disabled" : ""}>${state.requestCancelBusyId === request.id ? "Cancelling…" : "Cancel"}</button>`
        : "";
      return `<article class="session-request ${formattingPort.esc(request.state || "completed")}"><i aria-hidden="true"></i><div class="session-request-main"><strong>${formattingPort.esc(`${request.surface || formattingPort.clientName(request.client)} · ${protocol}`)}</strong><span>${formattingPort.esc(timing)}</span></div>${cancel}</article>`;
    };
    const rows = [
      ...active.map(request => requestRow(request)),
      ...queued.map(request => requestRow(request)),
      ...recent.map(request => requestRow(request, true)),
    ];
    setMarkup($("sessionActivityList"), rows.length ? rows.join("")
      : `<div class="session-activity-empty"><strong>${report.engineResident ? "Relay ready · no requests" : "No request activity"}</strong><span>${formattingPort.esc(report.engineResident ? "The loaded model is warm and waiting for Chat or an agent." : "Start a normal model session to create its private request relay.")}</span></div>`);

    const pendingTimeout=state.idlePolicyBusy && pendingIdlePolicy?.ownerRunId===currentPolicyOwner()
      ? pendingIdlePolicy.timeoutMinutes : policy.timeoutMinutes;
    const timeout = String(Number(pendingTimeout || 0));
    const select = $("sessionIdleTimeout");
    if ([...select.options].some(option => option.value === timeout)) select.value = timeout;
    const eligible = Boolean(report.engineResident && policy.eligible);
    [...select.options].forEach(option => { option.disabled = option.value !== "0" && !eligible; });
    select.disabled = !report.engineResident || state.idlePolicyBusy || (!eligible && !policy.enabled);
    $("sessionIdlePolicyDetail").textContent = state.idlePolicyBusy ? "Saving the session-only idle policy…" : policy.detail || "Keep the model loaded until you stop it.";
    $("sessionActivityCoverage").textContent = `${report.coverage?.detail || "Only launcher-created surfaces are observed."} No prompt, response, reasoning, tool, or project content is stored.`;
  }

  if ($("chatActivityState")) {
    const current = [...active, ...queued].find(item => item.surfaceId === surfacesPort.chatView().surfaceId);
    const inline = $("chatActivityState").parentElement;
    const chatRecent = recent.find(item => item.surfaceId === surfacesPort.chatView().surfaceId && formattingPort.requestTps(item));
    const chatSpeed = formattingPort.requestTps(chatRecent);
    if (current?.state === "running") {
      const currentSpeed = formattingPort.requestTps(current);
      const liveDetail = formattingPort.liveRequestDetail(current);
      $("chatActivityState").textContent = `${formattingPort.liveRequestPhaseLabel(current) || "Generating"}${currentSpeed ? ` · ${currentSpeed.primary.toFixed(1)} tok/s` : ` · ${formattingPort.formatShortDuration(current.runSeconds)}`}`;
      $("chatActivityDetail").textContent = `${liveDetail ? `${liveDetail}. ` : ""}${formattingPort.formatNumber(report.lanes || 1)} engine lane${Number(report.lanes || 1) === 1 ? "" : "s"} · ${formattingPort.formatNumber(queued.length)} other request${queued.length === 1 ? "" : "s"} waiting.`;
      inline.dataset.state = "running";
    } else if (current) {
      $("chatActivityState").textContent = `Engine queue #${formattingPort.formatNumber(current.queuePosition || 1)}`;
      $("chatActivityDetail").textContent = `${formattingPort.formatShortDuration(current.waitSeconds)} waiting behind earlier launcher-created work.`;
      inline.dataset.state = "queued";
    } else if (active.length) {
      $("chatActivityState").textContent = `${active[0].surface || "Another surface"} is generating`;
      $("chatActivityDetail").textContent = `${formattingPort.formatNumber(report.activeCount)} of ${formattingPort.formatNumber(report.lanes || 1)} configured engine lanes active.`;
      inline.dataset.state = "busy";
    } else {
      $("chatActivityState").textContent = report.engineResident
        ? `Relay idle${chatSpeed ? ` · ${chatSpeed.primary.toFixed(1)} tok/s ${chatSpeed.primaryKind} last turn` : ""}`
        : "Relay unavailable";
      $("chatActivityDetail").textContent = report.engineResident
        ? `${formattingPort.formatNumber(report.lanes || 1)} engine-matched lane${Number(report.lanes || 1) === 1 ? "" : "s"} ready for launcher-created surfaces.`
        : report.detail || "Request activity is unavailable.";
      inline.dataset.state = report.engineResident ? "idle" : "unavailable";
    }
    $("chatActivityState").title = chatSpeed
      ? `Last completed Chat turn: ${chatSpeed.label}`
      : "TPS appears only when the runtime reports authoritative token usage.";
    const speedSignal = $("chatStatusSpeed");
    const laneSignal = $("chatStatusLane");
    if (speedSignal && laneSignal) {
      const compact = ChatStatusCore.activitySummary(report, surfacesPort.chatView().surfaceId);
      $("chatStatusSpeedValue").textContent = compact.speed.value;
      speedSignal.dataset.state = compact.speed.state;
      speedSignal.title = compact.speed.title;
      $("chatStatusLaneValue").textContent = compact.lane.value;
      laneSignal.dataset.state = compact.lane.state;
      laneSignal.title = `${$("chatActivityState").textContent}. ${$("chatActivityDetail").textContent}`;
      surfacesPort.updateChatStatusSummaryLabel();
    }
  }
}

function renderFocusedRunStatus({phase, message, active, stopLabel, logAvailable}) {
  const panel = $("focusedRunStatus");
  if (!panel) return;
  const safePhase = String(phase || "idle");
  const safeStopLabel = state.runStatus?.run?.purpose === "session"
    ? "End session" : String(stopLabel || "Stop process");
  panel.dataset.phase = safePhase;
  $("focusedRunPhase").textContent = safePhase;
  $("focusedRunMessage").textContent = message || "Ready";
  const consoleAvailable = active && Boolean(surfacesPort.currentAgentConsoleView());
  $("focusedConsoleButton").hidden = !consoleAvailable;
  $("focusedConsoleButton").textContent = `Return to ${surfacesPort.currentAgentConsoleView()?.meta?.surface || "Hub"}`;
  $("focusedStopButton").hidden = !active;
  $("focusedLogButton").hidden = consoleAvailable;
  $("focusedStopButton").disabled = !active;
  $("focusedStopButton").setAttribute("aria-label", safeStopLabel);
  $("focusedStopButton").title = safeStopLabel;
  $("focusedLogButton").disabled = !logAvailable;
  $("agentConsoleLogButton").disabled = !logAvailable;
}

function renderRun(status) {
  if((state.runStatus?.run?.runId || null)!==(status.run?.runId || null)){runEpoch+=1;retireIdlePolicy();}
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
  if (surfacesPort.hasPendingChatReview() && !runActive) surfacesPort.chatReviewStopped(status.message);
  const setupActive = jobsPort.setupIsActive();
  const acquisitionActive = jobsPort.acquisitionIsActive();
  const routeCheckActive = jobsPort.routeCheckIsActive();
  const benchmarkActive = ["queued","cooldown","starting","running","stopping"].includes(benchmarkPort.view().phase);
  const aneActive = jobsPort.aneWorkIsActive();
  const displayPhase = acquisitionActive ? assetsPort.activity().phase : (setupActive ? state.setupPhase : (routeCheckActive ? state.routeCheckPhase : (aneActive ? (jobsPort.aneCloneIsActive() ? state.aneClonePhase : state.anePhase) : (benchmarkActive && !runActive ? benchmarkPort.view().phase : phase))));
  const displayMessage = acquisitionActive
    ? assetsPort.activity().status?.message
    : setupActive
    ? state.setupStatus?.message
    : (routeCheckActive ? state.routeCheckStatus?.message : (aneActive ? (jobsPort.aneCloneIsActive() ? state.aneCloneStatus?.message : state.aneStatus?.message) : (benchmarkActive && !runActive ? benchmarkPort.view().message : status.message)));
  const anyActive = runActive || setupActive || acquisitionActive || routeCheckActive || benchmarkActive || aneActive;
  const stopLabel = acquisitionActive ? "Stop model download" : (setupActive ? "Stop download" : (routeCheckActive ? "Stop Route Check" : (aneActive ? (jobsPort.aneCloneIsActive() ? "Stop FP16 copy" : "Stop ANE Tuner") : (benchmarkActive && !runActive ? "Stop benchmark" : "Stop process"))));
  $("phaseBadge").textContent = displayPhase;
  $("statusMessage").textContent = displayMessage || "Ready";
  $("stopButton").disabled = !anyActive;
  $("stopButton").textContent = stopLabel;
  $("logButton").disabled = phase === "idle";
  renderFocusedRunStatus({phase:displayPhase, message:displayMessage, active:anyActive, stopLabel, logAvailable:phase !== "idle"});
  $("healthPill").className = `status-pill ${displayPhase}`;
  if (status.run) {
    const run = status.run;
    const route = run.purpose === "benchmark" ? `${run.backend} → Benchmark Lab` : (run.purpose === "route-check" ? `${run.backend} → Route Check` : (run.purpose === "ane-tune" ? "oMLX → ANE Tuner" : `${run.backend} → ${formattingPort.clientName(run.client)}`));
    $("runFacts").classList.remove("hidden");
    const clientRouteLabel = run.purpose === "session" ? "Session relay" : "Compatibility guard";
    $("runFacts").innerHTML = `<div><span>Model</span><b>${formattingPort.esc(run.model)}</b></div><div><span>Route</span><b>${formattingPort.esc(route)}</b></div><div><span>Context</span><b>${formattingPort.formatNumber(run.context)}</b></div><div><span>Model API</span><b>127.0.0.1:${run.port}</b></div>${run.clientPort !== run.port ? `<div><span>${clientRouteLabel}</span><b>127.0.0.1:${run.clientPort}</b></div>` : ""}`;
  } else if (acquisitionActive && assetsPort.activity().status?.plan) {
    const acquisition = assetsPort.activity().status;
    $("runFacts").classList.remove("hidden");
    $("runFacts").innerHTML = `<div><span>Model</span><b>${formattingPort.esc(acquisition.plan.repo?.id || "Pinned model")}</b></div><div><span>Route</span><b>Public pinned acquisition</b></div><div><span>Progress</span><b>${Math.round(Number(acquisition.progress || 0) * 100)}%</b></div>`;
  } else if (setupActive && state.setupStatus?.plan) {
    const setup = state.setupStatus;
    $("runFacts").classList.remove("hidden");
    $("runFacts").innerHTML = `<div><span>Model</span><b>${formattingPort.esc(setup.plan.target?.name || "DFlash 2 draft")}</b></div><div><span>Route</span><b>Pinned model download</b></div><div><span>Progress</span><b>${Math.round(Number(setup.progress || 0) * 100)}%</b></div>`;
  } else if (routeCheckActive && state.routeCheckStatus?.job) {
    const check = state.routeCheckStatus;
    $("runFacts").classList.remove("hidden");
    $("runFacts").innerHTML = `<div><span>Model</span><b>${formattingPort.esc(check.job.model || "Selected model")}</b></div><div><span>Route</span><b>${formattingPort.esc(`${check.job.backendLabel} → ${check.job.surface}`)}</b></div><div><span>Progress</span><b>${Math.round(Number(check.progress || 0) * 100)}%</b></div>`;
  } else if (aneActive && state.aneStatus?.job) {
    const tuning = state.aneStatus;
    $("runFacts").classList.remove("hidden");
    $("runFacts").innerHTML = `<div><span>Model</span><b>${formattingPort.esc(tuning.job.model || "Qwen")}</b></div><div><span>Route</span><b>Private ANE measurement</b></div><div><span>Progress</span><b>${Math.round(Number(tuning.progress || 0) * 100)}%</b></div>`;
  } else $("runFacts").classList.add("hidden");
  refreshLaunchability();
  surfacesPort.syncAgentConsoleViews(status, status.run, phase);
  surfacesPort.updateChatWorkspace(status.run, phase);
  surfacesPort.updateAgentWorkspace(status.run, phase);
  if ($("sessionSetDialog")?.open) savedPort.renderSessionSets();
}

function performanceReceiptSuite() {
  const qualificationBackend = registryPort.selectedRouteQualificationBackend();
  if (qualificationBackend === "llamacpp") {
    return policy.LLAMACPP_PLE_QUALIFICATION_SUITE;
  }
  if (qualificationBackend === "uzu") {
    const suite = registryPort.uzuQualificationSuite(Number($("contextInput").value));
    if (!suite) {
      throw new Error("Uzu qualification is available only at an exact 16K, 32K, 64K, or 128K context tier.");
    }
    return suite;
  }
  return CalibrationDecision.receiptSuite(
    state.client,
    qualificationBackend === "omlx",
  );
}

function performanceReceiptSuiteOrder(request = {}, routeQualification = false) {
  const preferred = String(request.suite || "").trim();
  if (!preferred) return [];
  if (routeQualification) return [preferred];
  const clientOrder = request.client === "chat"
    ? ["standard", "agentic", "thorough", "quick"]
    : ["agentic", "standard", "thorough", "quick"];
  const operatorSuite = request.backend === "mtplx" && Number(request.context) >= 65536
    && request.options?.profile === "turbo" && registryPort.mtplxLongContextCapabilityExact(selectedModel())
    ? [policy.MTPLX_LONG_CONTEXT_SUITE] : [];
  return [preferred, ...operatorSuite, ...clientOrder].filter((suite, index, suites) => (
    suite && suites.indexOf(suite) === index
  ));
}

function performanceReceiptNeedsFallback(receipt) {
  return !receipt || ["missing", "incomplete"].includes(receipt.state);
}

function performanceReceiptSuiteLabel(receipt = {}) {
  const explicit = String(receipt.suiteLabel || "").trim();
  if (explicit) return explicit;
  const labels = {
    agentic:"Agentic Route Lab",
    [policy.LLAMACPP_PLE_QUALIFICATION_SUITE]:"SSD PLE Route Qualification",
    "route-qualification-uzu-16k":"Uzu Route Qualification · 16K",
    "route-qualification-uzu-32k":"Uzu Route Qualification · 32K",
    "route-qualification-uzu-64k":"Uzu Route Qualification · 64K",
    "route-qualification-uzu-128k":"Uzu Route Qualification · 128K",
    standard:"Standard",
    thorough:"Thorough",
    quick:"Quick",
  };
  return labels[receipt.suite] || labels[performanceReceiptSuite()] || "Measured workload";
}

function performanceReceiptRequest() {
  const request = gather("custom");
  request.suite = performanceReceiptSuite();
  request.enginePreference = "throughput";
  request.reasoningPolicy = "all-engines-model-default";
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
    reasoningPolicy:request.reasoningPolicy || "exact",
    options:request.options || {}, sampling,
    suite:request.suite, enginePreference:request.enginePreference,
  });
}

function performanceReceiptAge(receipt) {
  const age = formattingPort.finiteMetric(receipt?.ageDays);
  if (age === null) return "date unavailable";
  if (age < 1 / 24) return "just measured";
  if (age < 1) return "measured today";
  if (age < 2) return "measured yesterday";
  return `${Math.round(age)} days old`;
}

function performanceReceiptView(receipt) {
  if (state.backend === "uzu" && state.client === "pi") {
    return {
      state:"missing", icon:"○", title:"Uzu Pi · fixed DFlash + Weaver",
      detail:"Launch uses the matching Chat capacity test. Pi speed is not measured yet.",
      action:"Capacity", actionId:"review-capacity",
      titleText:"Pi uses the qualified context and live memory guard. Chat TPS is not an agent-speed result.",
    };
  }
  const focused = shellPort.activeDetail() === "focused";
  const qualificationBackend = registryPort.performanceReceiptQualificationBackend(receipt);
  const routeQualification = Boolean(qualificationBackend);
  const pendingQualificationBackend = ["missing", "incomplete"].includes(receipt?.state)
    ? registryPort.selectedRouteQualificationBackend() : "";
  const qualificationContextBackend = qualificationBackend || pendingQualificationBackend;
  const qualificationNeeded = Boolean(qualificationContextBackend);
  const llamaQualification = qualificationContextBackend === "llamacpp";
  const uzuQualification = qualificationContextBackend === "uzu";
  const suite = performanceReceiptSuiteLabel(receipt);
  const eligible = Array.isArray(receipt?.eligibleBackends)
    ? receipt.eligibleBackends.filter(registryPort.uiEngineVisible) : [];
  const reasoningNormalized = receipt?.reasoningContract?.normalized === true;
  const contextNormalized = Number.isInteger(receipt?.contextAdjustment?.measured);
  const reasoningLabel = reasoningNormalized
    ? `${receipt.reasoningContract.label || "Model default"} reasoning`
    : "";
  const contextLabel = contextNormalized
    ? `${formattingPort.formatNumber(receipt.contextAdjustment.measured)} common SSD context`
    : "";
  const age = performanceReceiptAge(receipt);
  const firstOutput = formattingPort.finiteMetric(receipt?.firstTokenSeconds);
  const selectedSetup = receipt?.settingsSearch?.selectedSetupLabel
    || receipt?.routeSettingsLabel || receipt?.modeLabel || "";
  const testedSetups = Number(receipt?.settingsSearch?.testedSetupCount || 0);
  const maximumSetups = Number(receipt?.settingsSearch?.maximumSetupCount || 0);
  const setupCoverage = testedSetups > 0 && maximumSetups >= testedSetups
    ? `${testedSetups}/${maximumSetups} setups tested`
    : "";
  const measured = [
    suite,
    selectedSetup,
    setupCoverage,
    receipt?.workloadDisplay,
    firstOutput === null ? "" : `${firstOutput.toFixed(2)}s first output`,
    age,
  ].filter(Boolean).join(" · ");
  const measuredTitle = [receipt?.backendLabel, selectedSetup].filter(Boolean).join(" · ");
  const fullSummary = [receipt?.summary, measured].filter(Boolean).join(" ");
  if (["trusted-engine", "trusted-route"].includes(receipt?.state)) {
    const engineReceipt = receipt.state === "trusted-engine" && !routeQualification;
    const focusedTitle = routeQualification
      ? `Qualified route · ${receipt.modeLabel || "verified route"}`
      : engineReceipt
        ? `Best measured · ${receipt.backendLabel || "engine"}`
        : `Measured route · ${receipt.modeLabel || "verified route"}`;
    if (receipt.fresh && (reasoningNormalized || contextNormalized)) return {
      state:"trusted", icon:"◆",
      title:focused ? focusedTitle : `Measured · ${measuredTitle || "verified route"}`,
      detail:focused
        ? [engineReceipt ? selectedSetup : receipt.backendLabel, setupCoverage, suite, receipt.workloadDisplay, reasoningLabel, contextLabel, age].filter(Boolean).join(" · ")
        : [measured, reasoningLabel, contextLabel, "review before applying"].filter(Boolean).join(" · "),
      action:"Review", actionId:"review-normalized", titleText:fullSummary,
    };
    if (receipt.fresh) return {
      state:"trusted", icon:"◆",
      title:focused ? focusedTitle
        : routeQualification
          ? `Qualified · ${measuredTitle || "verified route"}`
          : `Measured · ${measuredTitle || "verified route"}`,
      detail:focused
        ? [engineReceipt ? selectedSetup : receipt.backendLabel, setupCoverage, suite, receipt.workloadDisplay, age].filter(Boolean).join(" · ")
        : measured || `${suite} exact-contract evidence`,
      action:"Apply", actionId:engineReceipt ? "apply-engine" : "apply-route",
      titleText:fullSummary,
    };
    return {
      state:"stale", icon:"◇",
      title:focused
        ? routeQualification ? "Saved route qualification needs rechecking" : "Saved result needs rechecking"
        : `Saved · ${measuredTitle || "verified route"}`,
      detail:focused ? [measuredTitle, suite, age].filter(Boolean).join(" · ") : `${suite} · ${age} · rerun before relying on current conditions`,
      action:"Rerun", actionId:routeQualification ? "measure-qualification" : "rerun-lab", titleText:fullSummary,
    };
  }
  if (receipt?.state === "tie") {
    const leaders = Array.isArray(receipt.leadingBackends)
      ? receipt.leadingBackends.filter(item => registryPort.uiEngineVisible(item?.backend || item)) : [];
    const leaderNames = leaders.map(item => item?.label || formattingPort.backendName(item?.backend || item));
    const currentOutside = receipt.currentInLeadingBand === false;
    const currentName = receipt.currentBackendLabel || formattingPort.backendName(receipt.currentBackend || state.backend);
    const recommendedName = receipt.recommendedLabel || formattingPort.backendName(receipt.recommendedBackend);
    const leadingText = leaderNames.length
      ? `${leaderNames.join(leaderNames.length === 2 ? " and " : ", ")} are within 3%`
      : "The leading engines are within 3%";
    if (!receipt.fresh) return {
      state:"stale", icon:"◇", title:focused ? "Saved tie needs rechecking" : "Saved leading group · recheck",
      detail:focused ? `${leadingText} · ${suite} · ${age}` : `${suite} · ${age}`,
      action:"Rerun", actionId:"rerun-lab", titleText:fullSummary,
    };
    if (currentOutside && receipt.recommendedBackend) return {
      state:"tie", icon:"◆",
      title:focused ? `Apply leading engine · ${recommendedName}` : `Measured leader · ${recommendedName}`,
      detail:focused ? `${leadingText} · ${suite} · ${currentName} is outside` : `${suite} · ${currentName} is outside the measured leading group`,
      action:"Apply", actionId:"apply-engine", titleText:fullSummary,
    };
    return {
      state:"tie", icon:"≈", title:focused ? "Leading engines tied" : "Measured leading group · current kept",
      detail:focused ? `${leadingText} · ${suite} · current route is competitive` : `${suite} · ${age}`,
      action:"Review", actionId:"review-lab", titleText:fullSummary,
    };
  }
  if (receipt?.state === "incomplete") return {
    state:"incomplete", icon:"!",
    title:focused
      ? qualificationNeeded ? "Finish this route qualification" : "Finish the engine comparison"
      : qualificationNeeded ? "Route qualification incomplete" : "Measurement incomplete",
    detail:qualificationNeeded
      ? llamaQualification
        ? `${suite} · fixed-8K llama.cpp SSD PLE evidence is not complete`
        : uzuQualification
          ? `${suite} · the exact DFlash + Weaver context still needs a complete run`
        : `${suite} · this exact route still needs a complete run`
      : focused
        ? `${suite} · ${eligible.length} compatible engine${eligible.length === 1 ? "" : "s"} still need a complete run`
        : `${suite} · ${eligible.length} compatible engine${eligible.length === 1 ? "" : "s"} · no winner promoted`,
    action:"Measure", actionId:qualificationNeeded
      ? "measure-qualification" : eligible.length >= 2 ? "measure-engine" : "measure-route",
    titleText:fullSummary,
  };
  if (qualificationNeeded) return {
    state:"missing", icon:"◇",
    title:focused
      ? llamaQualification ? "Qualify this pinned SSD PLE route"
        : uzuQualification ? "Qualify this Uzu route"
          : "Qualify this SSD-backed PLE route"
      : "Route qualification needed",
    detail:focused
      ? llamaQualification
        ? "Fixed 8K · runtime-controlled reasoning · exact 44 GiB ceiling"
        : uzuQualification
          ? `${formattingPort.exactContextTier(Number($("contextInput").value))} · DFlash + Weaver · BF16 KV · Chat`
        : "Measure reasoning TPS and final-answer reliability on this Mac"
      : llamaQualification
        ? "Pinned llama.cpp SSD PLE · fixed 8K · not qualified yet"
        : uzuQualification
          ? `Uzu DFlash + Weaver · exact ${formattingPort.exactContextTier(Number($("contextInput").value))} · not qualified yet`
        : "Exact oMLX AR + N-gram PLE mmap route · not qualified yet",
    action:"Qualify", actionId:"measure-qualification", titleText:fullSummary,
  };
  const routeModes = benchmarkPort.benchmarkCandidates(selectedModel()?.backends?.[state.backend] || {}).length;
  if (receipt?.scope === "engine" && eligible.length >= 2) return {
    state:"missing", icon:"◇", title:focused ? "Compare compatible engines" : "No exact engine result",
    detail:focused ? `${suite} · ${eligible.length} engines can run this model and work surface` : `${eligible.length} compatible engines · ${suite}`,
    action:"Measure", actionId:"measure-engine", titleText:fullSummary,
  };
  if (routeModes > 1) return {
    state:"missing", icon:"◇", title:focused ? "Compare this engine's speed options" : "No exact route result",
    detail:focused
      ? benchmarkPort.benchmarkCandidates(selectedModel()?.backends?.[state.backend] || {}).map(item => item.label).join(" vs ")
      : `${benchmarkPort.benchmarkCandidates(selectedModel()?.backends?.[state.backend] || {}).map(item => item.label).join(" vs ")} · ${suite}`,
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
    && !registryPort.performanceReceiptQualificationBackend(receipt)
    ? String(receipt.backend || "")
    : receipt?.state === "tie" && receipt?.fresh && receipt?.currentInLeadingBand === false
      ? String(receipt.recommendedBackend || "") : "";
  collections.backendButtons.forEach(button => {
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
    view = shellPort.activeDetail() === "focused"
      ? {state:"loading", icon:"◇", title:"Checking saved measurements…", detail:"This does not start the model.", action:"…", actionId:"", titleText:""}
      : {state:"loading", icon:"◇", title:"Checking measurements…", detail:"Matching intelligence, sampling, limits, KV, workload, runtime and Mac.", action:"…", actionId:"", titleText:""};
  } else if (state.performanceReceiptError) {
    view = {state:"error", icon:"!", title:"Evidence unavailable", detail:state.performanceReceiptError, action:"Retry", actionId:"retry", titleText:state.performanceReceiptError};
  } else if (state.performanceReceipt) view = performanceReceiptView(state.performanceReceipt);
  else view = shellPort.activeDetail() === "focused"
    ? {state:"missing", icon:"◇", title:"Measure this route", detail:"No matching speed result is saved yet.", action:"Measure", actionId:"measure-route", titleText:""}
    : {state:"missing", icon:"◇", title:"No exact performance receipt", detail:"Measure this visible contract before choosing a winner.", action:"Measure", actionId:"measure-route", titleText:""};
  launchHome.renderOverview(currentSessionAdmission());
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
  const measureBlocked = ["measure-engine", "measure-qualification"].includes(view.actionId)
    && $("optimizerCalibrate").disabled;
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
    const routeQualification = Boolean(registryPort.selectedRouteQualificationBackend());
    const suites = performanceReceiptSuiteOrder(request, routeQualification);
    let preferredReceipt = null;
    let firstIncomplete = null;
    let completeReceipt = null;
    for (const suite of suites) {
      const suiteRequest = {...request, suite};
      const data = await api("/api/benchmark/history", {
        method:"POST", body:JSON.stringify(suiteRequest),
      });
      if (generation !== state.performanceReceiptGeneration) return;
      const receipt = data.history?.receipt || null;
      if (!receipt || receipt.suite !== suite) {
        throw new Error("The controller returned no exact-contract receipt for the requested workload suite.");
      }
      if (!preferredReceipt) preferredReceipt = receipt;
      if (receipt.state === "incomplete" && !firstIncomplete) firstIncomplete = receipt;
      if (!performanceReceiptNeedsFallback(receipt)) {
        completeReceipt = receipt;
        break;
      }
    }
    state.performanceReceipt = completeReceipt || firstIncomplete || preferredReceipt;
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
  platform.clearTimeout(state.performanceReceiptTimer);
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
  state.performanceReceiptTimer = platform.setTimeout(() => {
    if (generation === state.performanceReceiptGeneration) loadPerformanceReceipt(force, prepared);
  }, 180);
}

async function activatePerformanceReceipt() {
  const button = $("performanceReceipt");
  if (button.disabled) return;
  const action = button.dataset.action;
  if (action === "review-capacity") return openSessionDashboard();
  if (action === "retry") return loadPerformanceReceipt(true);
  if (["apply-engine", "apply-route"].includes(action) && !state.performanceReceipt?.evidenceBinding) {
    shellPort.showNotice("That saved result has no exact apply reference. Refresh performance evidence before applying it.", true);
    return loadPerformanceReceipt(true);
  }
  if (action === "apply-engine") return applyOptimal(
    "engine", "throughput", false, state.performanceReceipt.evidenceBinding,
  );
  if (action === "apply-route") return applyOptimal(
    "current", "throughput", false, state.performanceReceipt.evidenceBinding,
  );
  if (action === "measure-engine") return benchmarkPort.openCalibrationAssistant({source:"performance-receipt", preference:"throughput"});
  if (action === "measure-qualification") return benchmarkPort.openCalibrationAssistant({source:"performance-receipt", preference:"throughput"});
  if (action === "review-normalized") return benchmarkPort.openCalibrationAssistant({source:"performance-receipt", preference:"throughput"});
  if (["measure-route", "rerun-lab", "review-lab"].includes(action)) return benchmarkPort.openPerformanceBenchmarkLab();
}

async function applyOptimizerMenuChoice(scope = "current", preference = "throughput") {
  closeOptimizerMenu();
  if (benchmarkPort.completedCalibrationMatchesOptimizerChoice(scope, preference)) {
    return benchmarkPort.applyCalibrationResult(false);
  }
  return applyOptimal(scope, preference);
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
  return bytes >= 0 ? `${formattingPort.formatBytes(bytes)} left` : `${formattingPort.formatBytes(-bytes)} over headroom`;
}

function sessionAttachmentRequest() {
  const run = state.sessionDashboard?.hub?.session;
  if (!run) throw new Error("No launcher-owned model session is running.");
  const client = $("sessionAttachClient").value;
  const ompRpcQualified = state.binaries?.omp?.consoleSupported === true;
  LauncherHomeCore.syncAgentHost($("sessionAttachAgentHost"), client, {ompRpcQualified});
  const request = {
    ownerRunId:run.runId,
    client,
    project:$("sessionAttachProject").value || run.project,
  };
  const seed = $("sessionAttachSeed").value.trim();
  const generation = {
    sampling:$("sessionAttachSampling").value,
    temperature:Number($("sessionAttachTemperature").value),
    topP:Number($("sessionAttachTopP").value),
    topK:Number($("sessionAttachTopK").value),
    presencePenalty:Number($("sessionAttachPresencePenalty").value),
    frequencyPenalty:Number($("sessionAttachFrequencyPenalty").value),
    repetitionPenalty:Number($("sessionAttachRepetitionPenalty").value),
    seed:seed === "" ? null : Number(seed),
  };
  request.generation = generation;
  if (client !== "chat") request.agentHost = LauncherHomeCore.agentHostFor(client, $("sessionAttachAgentHost").value, {ompRpcQualified});
  if (client === "chat") {
    request.chat = {
      systemPrompt:$("sessionAttachSystemPrompt").value,
      ...generation,
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
    $("sessionAttachRepetitionPenalty").value = "1";
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
      ? `${formattingPort.clientName(option.value)} is not installed.`
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
    ? `Every surface below shares the loaded ${formattingPort.backendName(run.backend)} model through private relay port ${run.clientPort || run.port}; attaching never creates a second model allocation.`
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
      actions = `<button type="button" data-session-open-chat="${formattingPort.esc(attachment.id)}">Open</button>${attachment.canDetach ? `<button type="button" class="detach" data-session-detach-chat="${formattingPort.esc(attachment.id)}">End</button>` : ""}`;
    } else if (attachment.agentHost === "console" && attachment.canOpen) {
      actions = `<button type="button" data-session-open-console="${formattingPort.esc(attachment.id)}">Open</button>${attachment.canStop ? `<button type="button" class="detach" data-session-stop-console="${formattingPort.esc(attachment.id)}">Stop</button>` : ""}${attachment.canRestart ? `<button type="button" data-session-restart-console="${formattingPort.esc(attachment.id)}">Restart</button>` : ""}`;
    }
    return `<article class="session-attachment"><div class="session-attachment-main"><strong>${formattingPort.esc(`${attachment.surface}${attachment.primary ? " · primary" : " · attached"}`)}</strong><span>${formattingPort.esc(`${formattingPort.formatNumber(attachment.context)} context · ${attachment.reasoning} reasoning`)}</span><small title="${formattingPort.esc(attachment.project || "")}">${formattingPort.esc(attachment.client === "chat" ? (attachment.chat?.sampling === "custom" ? "Custom sampling" : "Model sampling defaults") : projectName)}</small></div><div class="session-attachment-actions">${actions || `<span class="session-attachment-status ${statusClass}">${formattingPort.esc(statusLabel)}</span>`}</div></article>`;
  }).join("") : `<div class="session-active-route idle"><strong>No reusable surface yet</strong><span>The active route must reach Running first.</span></div>`;

  const client = $("sessionAttachClient").value;
  const chat = client === "chat";
  const ompRpcQualified = state.binaries?.omp?.consoleSupported === true;
  LauncherHomeCore.syncAgentHost($("sessionAttachAgentHost"), client, {ompRpcQualified});
  $("sessionAttachHostHelp").textContent = client === "omp" && !ompRpcQualified
    ? "This oh-my-pi version uses macOS Terminal. Update to a supported version to use Hub Console."
    : "Hub Console stays private and launcher-owned.";
  $("sessionAttachProjectField").classList.toggle("hidden", chat);
  $("sessionAttachHostField").classList.toggle("hidden", chat);
  $("sessionAttachChatPanel").classList.remove("hidden");
  $("sessionAttachSystemPromptField").hidden = !chat;
  const custom = $("sessionAttachSampling").value === "custom";
  collections.sessionSamplers.forEach(field => {
    field.hidden = !custom;
    field.classList.toggle("inactive", !custom);
  });
  const controls = [
    "sessionAttachClient", "sessionAttachAgentHost", "sessionAttachProject", "sessionAttachSystemPrompt",
    "sessionAttachSampling", "sessionAttachTemperature", "sessionAttachTopP",
    "sessionAttachTopK", "sessionAttachPresencePenalty", "sessionAttachFrequencyPenalty",
    "sessionAttachRepetitionPenalty", "sessionAttachSeed",
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
    || state.runStatus?.run?.runId || surfacesPort.chatView().ownerRunId;
  if (!ownerRunId) return;
  state.requestCancelBusyId = requestId;
  renderRequestActivity();
  try {
    const data = await api("/api/session/request/cancel", {
      method:"POST", body:JSON.stringify({ownerRunId, requestId}),
    });
    state.requestActivity = data.activity;
    if (state.sessionDashboard?.hub) state.sessionDashboard.hub.activity = data.activity;
    if (surfaceId && surfaceId === surfacesPort.chatView().surfaceId) surfacesPort.abortChatResponse();
    renderRequestActivity(data.activity);
  } catch (error) {
    shellPort.showNotice(error.message, true);
  } finally {
    state.requestCancelBusyId = "";
    renderRequestActivity();
  }
}

async function setSessionIdlePolicy() {
  if (state.idlePolicyBusy) return;
  const ownerRunId = currentPolicyOwner();
  if (!ownerRunId) return;
  const timeoutMinutes = Number($("sessionIdleTimeout").value);
  const generation=++idlePolicyGeneration;
  pendingIdlePolicy={ownerRunId,timeoutMinutes};
  state.idlePolicyBusy = true;
  renderRequestActivity();
  try {
    const data = await api("/api/session/idle-policy", {
      method:"POST", body:JSON.stringify({ownerRunId, timeoutMinutes}),
    });
    if(generation!==idlePolicyGeneration || currentPolicyOwner()!==ownerRunId)return;
    state.requestActivity = data.activity;
    if (state.sessionDashboard?.hub) state.sessionDashboard.hub.activity = data.activity;
    renderRequestActivity(data.activity);
  } catch (error) {
    if(generation===idlePolicyGeneration && currentPolicyOwner()===ownerRunId)shellPort.showNotice(error.message, true);
  } finally {
    if(generation===idlePolicyGeneration){state.idlePolicyBusy=false;pendingIdlePolicy=null;renderRequestActivity();}
  }
}

function scheduleSessionAttachmentPlan(immediate = false) {
  state.sessionAttachmentPlan = null;
  state.sessionAttachmentSignature = "";
  if (state.sessionAttachmentTimer) platform.clearTimeout(state.sessionAttachmentTimer);
  renderSessionAttachmentPanel();
  state.sessionAttachmentTimer = platform.setTimeout(() => {
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

async function attachSessionSurface() {
  if (state.sessionAttachmentBusy || !state.sessionAttachmentPlan?.ready) return;
  let request;
  try { request = sessionAttachmentRequest(); }
  catch (error) {
    $("sessionAttachStatus").textContent = error.message;
    $("sessionAttachStatus").className = "session-dashboard-status error";
    return;
  }
  const opensLauncherSurface = request.client === "chat";
  let currentChatSavedForSurface = false;
  if (surfacesPort.chatView().surfaceId && opensLauncherSurface) {
    if (!await surfacesPort.saveChatBeforeSurfaceExit("open that work surface again")) return;
    currentChatSavedForSurface = true;
  }
  state.sessionAttachmentBusy = true;
  renderSessionAttachmentPanel();
  try {
    const data = await api("/api/session/attach", {method:"POST", body:JSON.stringify(request)});
    if (state.sessionDashboard) state.sessionDashboard.hub = data.hub;
    state.sessionAttachmentPlan = null;
    state.sessionAttachmentSignature = "";
    if (data.attachment.client === "chat") {
      if (await surfacesPort.enterChatSurface(data.attachment, {currentChatSaved:currentChatSavedForSurface})) {
        shellPort.showNotice("Chat attached to the loaded model. No engine or model weights were reloaded.");
      }
    } else if (data.attachment.agentHost === "console") {
      surfacesPort.enterAgentConsole(data.attachment);
      shellPort.showNotice(`${data.attachment.surface} attached in Hub Console. The existing model allocation is unchanged.`);
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
    ["Available for loading", resource.memoryAvailable ? formattingPort.formatBytes(resource.headroomBytes) : "Unknown"],
    ...(Number.isFinite(resource.reclaimableCacheBytes) ? [
      ["Unused RAM", formattingPort.formatBytes(resource.unusedMemoryBytes)],
      ["Reclaimable cache", formattingPort.formatBytes(resource.reclaimableCacheBytes)],
      ["Apps and system", formattingPort.formatBytes(resource.inUseMemoryBytes)],
    ] : []),
    ["Installed", resource.totalMemoryBytes ? formattingPort.formatBytes(resource.totalMemoryBytes) : "Unknown"],
    ["Thermal", resource.thermalAvailable ? resource.thermalState : "Unavailable"],
    ["Low Power", resource.lowPowerMode === null || resource.lowPowerMode === undefined ? "Unknown" : resource.lowPowerMode ? "On" : "Off"],
    ["Source", resource.memoryAvailable ? "macOS memory counters" : "Unavailable"],
    ["Checked", resource.capturedAt ? new Date(resource.capturedAt).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit",second:"2-digit"}) : "Now"],
  ].map(([label,value]) => `<span><small>${formattingPort.esc(label)}</small><b title="${formattingPort.esc(value)}">${formattingPort.esc(value)}</b></span>`).join("");
  $("sessionResourceDetail").textContent = "Available RAM includes unused RAM and reclaimable cache. macOS releases that cache as the model allocates memory.";

  const run = hub.session || hub.internalRun;
  $("sessionActiveState").textContent = operation.active ? operation.phase : "Idle";
  $("sessionActiveState").className = operation.active ? "warning" : "ready";
  if (run) {
    const surface = run.purpose === "session" ? formattingPort.clientName(run.client) : operation.label;
    const projectName = String(run.project || "").split("/").filter(Boolean).pop() || "Local route";
    const routeLocation = run.routeKind === "connected"
      ? "connected server through private localhost bridge"
      : run.routeKind === "shared"
        ? "shared local engine through private localhost bridge"
      : run.routeKind === "native"
        ? "native on this Mac"
        : "localhost";
    $("sessionActiveRoute").className = "session-active-route";
    $("sessionActiveRoute").innerHTML = `<strong>${formattingPort.esc(run.model)}</strong><span>${formattingPort.esc(formattingPort.backendName(run.backend))} → ${formattingPort.esc(surface)} · ${formattingPort.formatNumber(run.context)} context</span><small title="${formattingPort.esc(run.project || "")}">${formattingPort.esc(projectName)} · ${formattingPort.esc(routeLocation)} · localhost:${formattingPort.esc(run.clientPort || run.port)}</small>`;
  } else {
    $("sessionActiveRoute").className = "session-active-route idle";
    $("sessionActiveRoute").innerHTML = `<strong>No launcher-owned model session</strong><span>${formattingPort.esc(operation.detail || "Ready for a new route.")}</span><small>External runtimes are deliberately outside launcher ownership.</small>`;
  }
  $("sessionComponents").innerHTML = (hub.components || []).map(component => `<div class="session-component ${component.running ? "" : "stopped"}"><i aria-hidden="true"></i><span title="${formattingPort.esc(component.label)}">${formattingPort.esc(component.label)}</span><em>${component.pid ? `PID ${formattingPort.formatNumber(component.pid)}` : component.owned === "model-only" ? "model only" : component.owned ? "owned" : "handoff"}</em></div>`).join("");
  $("sessionOwnershipDetail").textContent = dashboard.policy?.reason || "One launcher-owned route at a time prevents accidental duplicate model allocations.";

  const visibleDecision = warmReady ? "ready" : admission.decision;
  const decisionClass = sessionDecisionClass(visibleDecision);
  $("sessionAdmissionTitle").textContent = warmReady
    ? "Reuse the loaded route"
    : admission.estimate?.remoteEngine ? "Connected server route"
    : admission.estimate?.sharedEngine ? "Shared local engine route"
    : admission.estimate?.ssdPle ? "Measured qualified-route capacity"
    : "Full-context capacity estimate";
  $("sessionAdmissionState").textContent = warmReady ? "Warm route available" : admission.label || "Unavailable";
  $("sessionAdmissionState").className = decisionClass;
  $("sessionAdmissionDetail").textContent = warmReady
    ? warmRoute.detail : admission.detail || "Choose a valid visible route.";
  const estimate = admission.estimate;
  if (warmReady) {
    $("sessionEstimateFacts").innerHTML = [
      ["Model loads", "0"],
      ["Weight reload", "No"],
      ["Engine", warmRoute.loadedRoute?.backendLabel || formattingPort.backendName(warmRoute.loadedRoute?.backend)],
      ["Model", warmRoute.loadedRoute?.model || "Loaded model"],
      ["Context", formattingPort.formatNumber(warmRoute.loadedRoute?.context || 0)],
      ["Prefix reuse", "Reported per turn"],
    ].map(([label,value]) => `<span><small>${formattingPort.esc(label)}</small><b title="${formattingPort.esc(value)}">${formattingPort.esc(value)}</b></span>`).join("");
    $("sessionEstimateBar").innerHTML = "";
    $("sessionEstimateBasis").textContent = "The visible engine contract matches exactly. Opening the selected surface does not load weights; a cache hit is still claimed only when the runtime reports cached prompt tokens.";
  } else if (estimate?.remoteEngine) {
    $("sessionEstimateFacts").innerHTML = [
      ["Model location", "FreeToken server"],
      ["Mac weight load", "None"],
      ["Mac KV load", "None"],
      ["Context", formattingPort.formatNumber(estimate.contextTokens)],
      ["Agent endpoint", "Private loopback"],
      ["Remote stop", "Never"],
    ].map(([label,value]) => `<span><small>${formattingPort.esc(label)}</small><b title="${formattingPort.esc(value)}">${formattingPort.esc(value)}</b></span>`).join("");
    $("sessionEstimateBar").innerHTML = "";
    $("sessionEstimateBasis").textContent = estimate.basis;
  } else if (estimate?.sharedEngine) {
    $("sessionEstimateFacts").innerHTML = [
      ["Model owner", "Whallm"],
      ["Launcher adds", formattingPort.formatBytes(estimate.estimatedWorkingSetBytes)],
      ["Published checkpoint", "Full 512 experts"],
      ["M5 Pro MLX active memory", formattingPort.formatBytes(
        estimate.observedMlxActiveMemoryBytes ?? estimate.observedEnginePeakBytes,
      )],
      ["Context", formattingPort.formatNumber(estimate.contextTokens)],
      ["Launcher stop", "Bridge only"],
    ].map(([label,value]) => `<span><small>${formattingPort.esc(label)}</small><b title="${formattingPort.esc(value)}">${formattingPort.esc(value)}</b></span>`).join("");
    $("sessionEstimateBar").innerHTML = "";
    $("sessionEstimateBasis").textContent = estimate.basis;
  } else if (estimate?.ssdPle) {
    const measuredPeak = Number(estimate.measuredProcessGroupPeakBytes || 0);
    const required = Number(estimate.requiredHeadroomBytes || 0);
    $("sessionEstimateFacts").innerHTML = [
      ["Route proof", estimate.qualifiedRoute ? "Fresh local qualification" : "Qualification needed"],
      ["Measured process peak", measuredPeak > 0 ? formattingPort.formatBytes(measuredPeak) : "Not measured"],
      ["Available for loading", resource.memoryAvailable ? formattingPort.formatBytes(resource.headroomBytes) : "Unknown"],
      ["Required before load", required > 0 ? formattingPort.formatBytes(required) : "Unavailable"],
      ["Strict Metal ceiling", formattingPort.formatBytes(estimate.memoryCeilingBytes)],
      ["Protected for macOS", formattingPort.formatBytes(estimate.osReserveBytes)],
    ].map(([label,value]) => `<span><small>${formattingPort.esc(label)}</small><b title="${formattingPort.esc(value)}">${formattingPort.esc(value)}</b></span>`).join("");
    const denominator = Math.max(Number(resource.totalMemoryBytes || 0), measuredPeak + Number(estimate.osReserveBytes || 0), 1);
    $("sessionEstimateBar").innerHTML = [
      ["weights", measuredPeak, "Measured route peak"],
      ["reserve", Number(estimate.osReserveBytes || 0), "Protected macOS reserve"],
    ].filter(item => item[1] > 0).map(([kind,value,label]) => `<span class="${kind}" style="width:${Math.max(.4, value / denominator * 100).toFixed(2)}%" title="${formattingPort.esc(`${label}: ${formattingPort.formatBytes(value)}`)}"></span>`).join("");
    $("sessionEstimateBasis").textContent = estimate.basis;
  } else if (estimate) {
    const companion = estimate.companionLabels?.length ? `${formattingPort.formatBytes(estimate.companionBytes)} · ${estimate.companionLabels.join(" + ")}` : formattingPort.formatBytes(estimate.companionBytes);
    const modelLabel = estimate.pleMmap ? "Resident weights" : "Model weights";
    const modelFacts = [
      [modelLabel, formattingPort.formatBytes(estimate.modelBytes)],
      ...(estimate.pleMmap ? [["N-gram PLE on SSD", formattingPort.formatBytes(estimate.ssdPleBytes)]] : []),
      ...(estimate.pleMmap && estimate.memoryGuard === "high" ? [
        ["oMLX process guard", formattingPort.formatGiB(estimate.memoryGuardHardWatermarkBytes)],
        ["Required Metal limit", formattingPort.formatGiB(estimate.requiredMetalWiredLimitBytes)],
      ] : []),
      ...(Number(estimate.companionBytes || 0) > 0 ? [["Companions", companion]] : []),
      [`${estimate.kvPrecision === "off" ? "Full" : String(estimate.kvPrecision).toUpperCase()} KV · ${formattingPort.formatNumber(estimate.contextTokens)}`, estimate.geometryReady ? formattingPort.formatBytes(estimate.kvCacheBytes) : "Geometry unavailable"],
      ["Runtime reserve", formattingPort.formatBytes(estimate.runtimeReserveBytes)],
      ["macOS reserve", formattingPort.formatBytes(estimate.osReserveBytes)],
      ["After launch", sessionProjectedLabel(admission.projectedHeadroomBytes)],
    ];
    $("sessionEstimateFacts").innerHTML = modelFacts.map(([label,value]) => `<span><small>${formattingPort.esc(label)}</small><b title="${formattingPort.esc(value)}">${formattingPort.esc(value)}</b></span>`).join("");
    const segments = [
      ["weights", estimate.modelBytes, "Model weights"],
      ["companion", estimate.companionBytes, "Companion weights"],
      ["kv", estimate.kvCacheBytes, "Full-context KV capacity"],
      ["runtime", estimate.runtimeReserveBytes, "Runtime reserve"],
      ["reserve", estimate.osReserveBytes, "Protected macOS reserve"],
    ];
    const denominator = Math.max(Number(resource.totalMemoryBytes || 0), segments.reduce((sum, item) => sum + Number(item[1] || 0), 0), 1);
    $("sessionEstimateBar").innerHTML = segments.filter(item => Number(item[1]) > 0).map(([kind,value,label]) => `<span class="${kind}" style="width:${Math.max(.4, Number(value) / denominator * 100).toFixed(2)}%" title="${formattingPort.esc(`${label}: ${formattingPort.formatBytes(value)}`)}"></span>`).join("");
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

async function loadSessionDashboard(options = {}) {
  const force = options?.force !== false;
  let request = options?.request && typeof options.request === "object"
    ? options.request : visibleSessionAdmissionRequest();
  let signature = visibleSessionAdmissionSignature(request);
  const currentSignature = visibleSessionAdmissionSignature();
  // A debounced request may reach this point after the user has changed a
  // control.  Never ask for, display, or authorize the older contract.
  if (signature && currentSignature && signature !== currentSignature) {
    request = visibleSessionAdmissionRequest();
    signature = visibleSessionAdmissionSignature(request);
  }
  if (!request || !signature) {
    state.sessionGeneration += 1;
    state.sessionLoading = false;
    state.sessionAdmissionPendingSignature = "";
    state.sessionAdmissionError = "";
    state.sessionAdmissionErrorSignature = "";
    state.sessionAdmissionErrorAt = 0;
    state.sessionDashboard = null;
    $("sessionDashboardStatus").textContent = "Finish the visible settings before checking capacity.";
    $("sessionDashboardStatus").className = "session-dashboard-status error";
    renderSessionDashboard();
    refreshLaunchability();
    return null;
  }
  const cached = state.sessionAdmissionSignature === signature
    && Boolean(state.sessionDashboard?.admission);
  if (!force && cached && Date.now() - Number(state.sessionLastLoadedAt || 0) < policy.SESSION_ADMISSION_REFRESH_MS) {
    return state.sessionDashboard;
  }
  if (
    !force && state.sessionLoading
    && state.sessionAdmissionPendingSignature === signature
  ) return state.sessionDashboard;
  const generation = ++state.sessionGeneration;
  state.sessionLoading = true;
  state.sessionAdmissionPendingSignature = signature;
  renderSessionDashboard();
  try {
    const data = await api("/api/session/plan", {method:"POST", body:JSON.stringify(request)});
    if (
      generation !== state.sessionGeneration
      || signature !== visibleSessionAdmissionSignature()
    ) return null;
    const next = data.sessions;
    if (!next?.admission || typeof next.admission !== "object") {
      throw new Error("The capacity check did not return a usable result.");
    }
    const nextContract = next?.admission?.contractId || "";
    if (state.sessionAdmissionSignature !== signature || state.sessionAcknowledgementId !== nextContract) {
      state.sessionAcknowledgementId = "";
    }
    if (!next?.admission?.requiresAcknowledgement) state.sessionAcknowledgementId = "";
    state.sessionAdmissionSignature = signature;
    state.sessionDashboard = next;
    state.sessionLastLoadedAt = Date.now();
    state.sessionAdmissionError = "";
    state.sessionAdmissionErrorSignature = "";
    state.sessionAdmissionErrorAt = 0;
    if (
      next?.warmRoute?.ownerRunId === state.runStatus?.run?.runId
      && signature === JSON.stringify(request)
    ) {
      state.warmRoutePlan = next.warmRoute;
      state.warmRouteSignature = warmRouteRequestSignature(request);
    }
    return next;
  } catch (error) {
    if (
      generation === state.sessionGeneration
      && signature === visibleSessionAdmissionSignature()
    ) {
      if (state.sessionAdmissionSignature !== signature) state.sessionDashboard = null;
      state.sessionAdmissionError = error.message;
      state.sessionAdmissionErrorSignature = signature;
      state.sessionAdmissionErrorAt = Date.now();
      $("sessionDashboardStatus").textContent = error.message;
      $("sessionDashboardStatus").className = "session-dashboard-status error";
    }
    return null;
  } finally {
    if (generation === state.sessionGeneration) {
      state.sessionLoading = false;
      state.sessionAdmissionPendingSignature = "";
      renderSessionDashboard();
      refreshLaunchability();
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

async function showLog() {
  try { const data = await api("/api/log"); $("logContent").textContent = data.log || "No engine output yet."; $("logDialog").showModal(); }
  catch (error) { shellPort.showNotice(error.message, true); }
}

async function stopRun() {
  try {
    if (surfacesPort.chatView().surfaceId) {
      const ready = await surfacesPort.saveChatBeforeSurfaceExit("stop this model session again");
      if (!ready) return false;
    } else if (surfacesPort.chatView().generating) surfacesPort.abortChatResponse();
    await api("/api/stop", {method:"POST", body:"{}"});
    runEpoch+=1;retireIdlePolicy();
    if (surfacesPort.agentConsoleIsVisible()) surfacesPort.leaveAgentConsole();
    await Promise.all([pollStatus(), jobsPort.pollRouteCheckStatus(), benchmarkPort.pollBenchmarkStatus(), jobsPort.pollSetupStatus(), jobsPort.pollAcquisitionStatus(), jobsPort.pollAneStatus(), jobsPort.pollAneCloneStatus(), jobsPort.pollRuntimeUpdateStatus()]);
    return true;
  }
  catch (error) { shellPort.showNotice(error.message, true); return false; }
}

function setProfileSelect(id, value, label) {
  const control = $(id);
  const option = [...control.options].find(item => item.value === String(value) && !item.disabled);
  if (!option) throw new Error(`${label} is no longer available in the current launcher controls.`);
  control.value = String(value);
}

function applyProfileRequest(request) {
  if (!registryPort.uiRequestVisible(request)) {
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
  const options = request.options || {};
  if (request.backend === "splash") {
    setProfileSelect("splashAccelerationSelect", options.acceleration || "off", "The saved Splash acceleration");
    refreshLaunchability();
  }
  $("projectPath").value = request.project;
  $("contextInput").value = String(request.context);
  $("outputInput").value = String(request.output);
  setProfileSelect("reasoningSelect", request.reasoning, "The saved reasoning level");
  if (request.client !== "chat") {
    setProfileSelect("agentHostSelect", request.agentHost || "terminal", "The saved agent window");
  }
  if (request.backend === "rapidmlx" && options.depth !== undefined && !rapidMtpDepths().includes(Number(options.depth))) {
    throw new Error("The saved MTP draft depth is no longer supported by this Rapid MLX model and runtime.");
  }
  if (request.backend !== "splash") {
    setProfileSelect("accelerationSelect", options.acceleration ?? (request.backend === "rapidmlx" ? selectedModel()?.backends?.rapidmlx?.preferredAcceleration || "auto" : undefined), "The saved acceleration route");
  }
  if (!setRuntimeKvValue(request.backend, options.kv || "off")) {
    throw new Error("The saved KV precision is no longer available in this engine.");
  }
  const optionControls = {
    profile:"profileSelect", fan:"fanSelect", burst:"burstSelect",
    dflashVerify:"dflashVerifySelect", dflashDraftQuant:"dflashDraftQuantSelect",
    anePrefill:"anePrefillSelect", memoryGuard:"memoryGuardSelect", gpu:"gpuSelect",
    expertResidentPercent:"omlxExpertResidentPercent",
  };
  for (const [key, id] of Object.entries(optionControls)) {
    if (options[key] !== undefined) setProfileSelect(id, options[key], `The saved ${key} control`);
  }
  if (options.omlxMemoryGB !== undefined) $("omlxMemoryGB").value = String(options.omlxMemoryGB);
  if (options.depth !== undefined) $("depthInput").value = String(options.depth);
  if (request.backend === "kolibri") {
    $("kolibriMemoryMode").value = options.memoryMode || "auto";
    if (options.memoryGB !== undefined) $("kolibriMemoryGB").value = String(options.memoryGB);
    setProfileSelect("kolibriPrefillSelect", options.prefillSize ?? 64, "The saved prefill chunk");
    $("kolibriPromptCacheGB").value = String(options.promptCacheGB ?? 1);
  }
  if (request.backend === "slotstream") $("slotstreamMemoryMode").value = options.memoryMode || "auto";
  if (request.backend === "slotstream" && options.memoryGB !== undefined) $("slotstreamMemoryGB").value = String(options.memoryGB);
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
  const generation = request.generation || request.chat || {sampling:"model"};
  if (!splashDspineActive()) setProfileSelect("samplingMode", generation.sampling || "model", "The saved sampling mode");
  if (!splashDspineActive() && generation.sampling === "custom") {
    $("temperatureInput").value = String(generation.temperature);
    $("topPInput").value = String(generation.topP);
    $("topKInput").value = String(generation.topK);
    $("presencePenaltyInput").value = String(generation.presencePenalty ?? 0);
    $("frequencyPenaltyInput").value = String(generation.frequencyPenalty ?? 0);
    $("repetitionPenaltyInput").value = String(generation.repetitionPenalty ?? 1);
    $("seedInput").value = generation.seed === null || generation.seed === undefined ? "" : String(generation.seed);
  }
  if (request.client === "chat") {
    $("systemPrompt").value = request.chat?.systemPrompt || "";
  }
  updateChatSamplingControls();
  if (request.backend === "mtplx") {
    updateMtplxLongContextControl();
    setProfileSelect(
      "mtplxOperatorRouteSelect", registryPort.savedMtplxOperatorRoute(options),
      "The saved long-context execution route",
    );
  } else {
    $("mtplxOperatorRouteSelect").value = policy.MTPLX_OPERATOR_ROUTE_DEFAULT;
  }
  updateAccelerationState();
  state.optimalSignature = "";
  state.optimalLabel = "";
  setOptimizationState("custom", "Saved profile", "The profile's exact visible settings are applied.");
  refreshLaunchability();
  persistVisibleRoute();
}
  const launchHome=LauncherHomeCore.createController({nodes,
    view:()=>Object.freeze({backend:state.backend,client:state.client,runPhase:state.runPhase,performanceReceipt:state.performanceReceipt,
      performanceReceiptLoading:state.performanceReceiptLoading,performanceReceiptError:state.performanceReceiptError,
      launchPreparing:state.launchPreparing,applyingOptimal:state.applyingOptimal,homeEngineFeedbackSignature:state.homeEngineFeedbackSignature,homeEngineFeedback:state.homeEngineFeedback}),
    createOption:()=>platform.createOption(),markPreparing:shellPort.markPreparing,presenter:UiPresenter,
    backendName:formattingPort.backendName,clientName:formattingPort.clientName,protectedSnapshot,formatNumber:formattingPort.formatNumber,exactContextTier:formattingPort.exactContextTier,
    gatherOptions,runtimeKvLabel,currentWarmRoutePlan,clientAvailability,selectedModel,esc:formattingPort.esc});
  function initialize(){
   if(initialized)return;initialized=true;
   statusTask=options.polling.register('run',{interval:()=>platform.isHidden()?10000:1800,
    run:async()=>{const epoch=runEpoch;try{const status=await network.status();if(epoch!==runEpoch)return;renderRun(status);if(nodes.sessionDialog?.open&&Date.now()-state.sessionLastLoadedAt>=4500)loadSessionDashboard();}catch(_error){}}});
   options.polling.register('slotstreamDownload',{interval:()=>state.backend==='slotstream'&&state.models.some(model=>model.slotstream&&(!model.ready||!model.slotstream.mtp))?30000:Infinity,run:()=>loadModels(false)});
collections.backendButtons.forEach(button => button.addEventListener("click", () => {
  if (button.disabled || !registryPort.uiEngineVisible(button.dataset.backend)) return;
  const backend = button.dataset.backend;
  if (state.backend !== backend) { state.backend = backend; updateBackend(); benchmarkPort.scheduleBenchmarkHistory(); }
  if (
    backend === "freetoken" && !state.freeToken?.connected
    && !state.freeToken?.native?.installed
  ) openFreeTokenDialog();
}));
for (const id of RoutePreferenceCore.SETUP_FIELDS) {
  $(id)?.addEventListener("change", () => {
    if (!state.applyingOptimal) persistVisibleRoute();
  });
}
collections.clientButtons.forEach(button => button.addEventListener("click", () => {
  if (!button.disabled && state.client !== button.dataset.client) {
    cancelOptimization("Work surface changed; reapply the speed preset for this workload.");
    state.client = button.dataset.client;
    updateMtplxLongContextControl();
    refreshLaunchability();
    persistVisibleRoute(false);
    benchmarkPort.scheduleBenchmarkHistory();
    schedulePerformanceReceipt();
  }
}));
$("homeModelSearch").addEventListener("input", () => updateLaunchHome());
$("homeModelList").addEventListener("click", event => {
  const button = event.target.closest("[data-home-model]");
  const group = homeModelGroups.find(row => row.id === button?.dataset.homeModel);
  if (group) selectCatalogRoute(group.routes);
});
$("reasoningSelect").addEventListener("change", () => { cancelOptimization("Reasoning changed; reapply to refresh the evidence match."); updateMtplxLongContextControl(); refreshLaunchability(); benchmarkPort.scheduleBenchmarkHistory(); schedulePerformanceReceipt(); });
$("contextInput").addEventListener("input", () => { cancelOptimization("Context changed; reapply to refresh the context-specific recommendation."); updateMtplxLongContextControl(); refreshLaunchability(); benchmarkPort.scheduleBenchmarkHistory(); schedulePerformanceReceipt(); });
$("contextSelect").addEventListener("change", () => {
  $("contextInput").value = $("contextSelect").value;
  $("contextInput").dispatchEvent(new platform.Event("input", {bubbles:true}));
  $("contextInput").dispatchEvent(new platform.Event("change", {bubbles:true}));
  persistVisibleRoute();
});
$("splashAccelerationSelect").addEventListener("change", () => {
  cancelOptimization("Splash acceleration changed.");
  refreshLaunchability();
  persistVisibleRoute();
  benchmarkPort.scheduleBenchmarkHistory();
  schedulePerformanceReceipt();
});
$("outputInput").addEventListener("input", () => { cancelOptimization("Response limit changed; reapply to refresh the workload recommendation."); updateMtplxLongContextControl(); refreshLaunchability(); benchmarkPort.scheduleBenchmarkHistory(); schedulePerformanceReceipt(); });
$("projectPath").addEventListener("input", () => {
  savedPort.rememberAppliedProfile();
  refreshLaunchability();
});
$("agentHostSelect").addEventListener("change", () => {
  clearWarmRoutePlan();
  refreshLaunchability();
  scheduleWarmRoutePlan(true);
});
$("omlxKv").addEventListener("change", () => { cancelOptimization("KV precision changed; reapply to refresh the benchmark match."); refreshLaunchability(); benchmarkPort.scheduleBenchmarkHistory(); schedulePerformanceReceipt(); });
for (const id of ["kolibriKv", "kolibriMemoryMode", "kolibriMemoryGB", "kolibriPrefillSelect", "kolibriPromptCacheGB"]) {
  const updateKolibriSettings = () => {
    cancelOptimization("Kolibri cache or memory settings changed.");
    refreshLaunchability(); benchmarkPort.scheduleBenchmarkHistory(); schedulePerformanceReceipt();
    persistVisibleRoute();
  };
  $(id).addEventListener("change", updateKolibriSettings);
  if (["kolibriMemoryGB", "kolibriPromptCacheGB"].includes(id)) {
    $(id).addEventListener("input", updateKolibriSettings);
  }
}
$("rapidmlxDepthSelect").addEventListener("change", () => {
  $("depthInput").value = $("rapidmlxDepthSelect").value;
  updateAccelerationState();
  markOptimizerCustom();
  refreshLaunchability();
  benchmarkPort.scheduleBenchmarkHistory();
  schedulePerformanceReceipt();
  persistVisibleRoute();
});
$("slotstreamKv").addEventListener("change", () => { cancelOptimization("KV precision changed; reapply to refresh the benchmark match."); refreshLaunchability(); benchmarkPort.scheduleBenchmarkHistory(); schedulePerformanceReceipt(); });
$("mtplxKv").addEventListener("change", () => { cancelOptimization("KV precision changed; reapply to refresh the benchmark match."); updateMtplxLongContextControl(); refreshLaunchability(); benchmarkPort.scheduleBenchmarkHistory(); schedulePerformanceReceipt(); });
for (const id of ["omlxExpertResidentPercent", "omlxMemoryGB"]) {
  $(id).addEventListener("change", () => {
    cancelOptimization("Expert memory settings changed; refresh the capacity estimate.");
    clearWarmRoutePlan();
    refreshLaunchability();
    benchmarkPort.scheduleBenchmarkHistory();
    schedulePerformanceReceipt();
    persistVisibleRoute();
  });
}
$("memoryGuardSelect").addEventListener("change", () => {
  // The optimiser dispatches the same change event after moving this control.
  // Treat only a user edit as invalidating the in-flight recommendation.
  if (!state.applyingOptimal) {
    cancelOptimization("Memory mode changed; reapply to refresh the benchmark match.");
  }
  clearWarmRoutePlan();
  refreshLaunchability();
  benchmarkPort.scheduleBenchmarkHistory();
  schedulePerformanceReceipt();
});
$("refreshModels").addEventListener("click", () => loadModels(true));
$("openFreeTokenConnection").addEventListener("click", () => {
  if ($("openFreeTokenConnection").dataset.action === "models") void assetsPort.openFreeTokenModelReview();
  else openFreeTokenDialog();
});
$("freeTokenForm").addEventListener("submit", connectFreeToken);
$("freeTokenDisconnect").addEventListener("click", disconnectFreeToken);
$("freeTokenExperimentalConsent").addEventListener("change", event => {
  event.currentTarget.dataset.modelId = event.currentTarget.checked
    ? String(selectedModel()?.id || "") : "";
  updateFreeTokenNativeControls();
  refreshLaunchability();
});
$("previewButton").addEventListener("click", preview);
$("applyOptimal").addEventListener("click", () => applyOptimal("current"));
$("performanceReceipt").addEventListener("click", activatePerformanceReceipt);
$("optimizerMenuButton").addEventListener("click", toggleOptimizerMenu);
$("optimizerVerifiedLaunch").addEventListener("click", () => prepareVerifiedQuickLaunch("throughput"));
collections.optimizerButtons.forEach(button => button.addEventListener("click", async () => {
  await applyOptimizerMenuChoice(button.dataset.optimizerScope, button.dataset.enginePreference || "throughput");
  if (button.id === "homeFastestEngine") {
    state.homeEngineFeedback = $("optimizationStatus").textContent;
    state.homeEngineFeedbackSignature = protectedSnapshot();
    updateLaunchHome();
  }
}));
$("optimizerCalibrate").addEventListener("click", () => benchmarkPort.openCalibrationAssistant({source:"optimizer-menu", preference:"throughput"}));
platform.onDocumentClick(event => {
  if (state.optimizerMenuOpen && !$("optimizerAction").contains(event.target)) closeOptimizerMenu();
});
platform.onDocumentKeyDown(event => {
  if (!state.optimizerMenuOpen) return;
  if (event.key === "Escape") {
    event.preventDefault(); closeOptimizerMenu(); $("optimizerMenuButton").focus(); return;
  }
  if (!["ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) return;
  const items = [...$("optimizerMenu").querySelectorAll('[role="menuitem"]:not(:disabled)')];
  if (!items.length) return;
  event.preventDefault();
  const current = items.indexOf(platform.activeElement());
  const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 : event.key === "ArrowDown" ? (current + 1 + items.length) % items.length : (current - 1 + items.length) % items.length;
  items[next].focus();
});
$("launchButton").addEventListener("click", startSimpleLaunch);
$("launchMemoryEstimate").addEventListener("click", openSessionDashboard);
$("cancelLaunchPreparation").addEventListener("click", cancelSimpleLaunch);
$("continueLaunchPreparation").addEventListener("click", () => {
  if (launchReviewResolve) { launchReviewResolve(true); launchReviewResolve = null; }
});
$("homeEngineSelect").addEventListener("change", event => {
  const modelId = selectedModel()?.id;
  const group = homeModelGroups.find(row => row.routes.some(route => route.modelId === modelId));
  if (!selectCatalogRoute(group?.routes.filter(route => route.backend === event.target.value))) {
    event.target.value = state.backend;
  }
});
$("stopButton").addEventListener("click", stopRun);
$("logButton").addEventListener("click", showLog);
$("focusedStopButton").addEventListener("click", stopRun);
$("focusedLogButton").addEventListener("click", showLog);
$("sessionRefreshButton").addEventListener("click", () => loadSessionDashboard({force:true}));
$("sessionStopButton").addEventListener("click", stopSessionFromDashboard);
$("sessionAttachClient").addEventListener("change", () => scheduleSessionAttachmentPlan(true));
$("sessionAttachAgentHost").addEventListener("change", () => scheduleSessionAttachmentPlan(true));
$("sessionAttachSampling").addEventListener("change", () => scheduleSessionAttachmentPlan(true));
for (const id of [
  "sessionAttachProject", "sessionAttachSystemPrompt", "sessionAttachTemperature",
  "sessionAttachTopP", "sessionAttachTopK", "sessionAttachPresencePenalty",
  "sessionAttachFrequencyPenalty", "sessionAttachRepetitionPenalty", "sessionAttachSeed",
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
  if (open) void surfacesPort.enterChatSurface(attachments.find(item => item.id === open.dataset.sessionOpenChat));
  else if (detach) void surfacesPort.detachChatSurface(attachments.find(item => item.id === detach.dataset.sessionDetachChat));
  else if (openConsole) surfacesPort.enterAgentConsole(attachments.find(item => item.id === openConsole.dataset.sessionOpenConsole));
  else if (stopConsole) surfacesPort.stopAgentConsoleSurface(attachments.find(item => item.id === stopConsole.dataset.sessionStopConsole));
  else if (restartConsole) surfacesPort.restartAgentConsoleSurface(attachments.find(item => item.id === restartConsole.dataset.sessionRestartConsole));
});
$("sessionConsent").addEventListener("change", () => {
  const admission = state.sessionDashboard?.admission;
  state.sessionAcknowledgementId = $("sessionConsent").checked && admission?.requiresAcknowledgement
    ? admission.contractId || "" : "";
  renderSessionDashboard();
  refreshLaunchability();
});
$("openSetupButton").addEventListener("click", jobsPort.openSetupAssistant);
$("openAneButton").addEventListener("click", jobsPort.openAneTuner);
$("samplingMode").addEventListener("change", () => {
  if (!state.applyingOptimal) cancelOptimization("Sampling changed; reapply to refresh the evidence match.");
  updateChatSamplingControls();
  updateMtplxLongContextControl();
  refreshLaunchability();
  benchmarkPort.scheduleBenchmarkHistory();
  schedulePerformanceReceipt();
});
$("systemPrompt").addEventListener("input", () => { refreshLaunchability(); benchmarkPort.scheduleBenchmarkHistory(); });
for (const id of [
  "temperatureInput", "topPInput", "topKInput", "presencePenaltyInput",
  "frequencyPenaltyInput", "repetitionPenaltyInput", "seedInput",
]) {
  $(id).addEventListener("input", () => {
    if (!state.applyingOptimal) cancelOptimization("Sampling changed; reapply to refresh the evidence match.");
    updateMtplxLongContextControl();
    refreshLaunchability();
    benchmarkPort.scheduleBenchmarkHistory();
    schedulePerformanceReceipt();
  });
}
Object.values(policy.optimizerControls).forEach(id => {
  const control = $(id);
  control.addEventListener("input", () => {
    if (control.type === "range") setRangeVisual(control);
    if (["accelerationSelect", "depthInput", "profileSelect", "mtplxOperatorRouteSelect", "fanSelect"].includes(id)) updateAccelerationState();
    if (id.startsWith("freeToken")) {
      updateFreeTokenNativeControls();
      refreshLaunchability();
    }
    markOptimizerCustom();
    schedulePerformanceReceipt();
  });
  control.addEventListener("change", () => {
    if (["accelerationSelect", "depthInput", "profileSelect", "mtplxOperatorRouteSelect", "fanSelect"].includes(id)) updateAccelerationState();
    if (id.startsWith("freeToken")) updateFreeTokenNativeControls();
    markOptimizerCustom();
    refreshLaunchability();
    benchmarkPort.scheduleBenchmarkHistory();
    schedulePerformanceReceipt();
  });
});
  }
  const methods={updateMtplxLongContextControl,selectedModel,routeRuntimeInstalled,orderedRouteIds,visibleRouteCatalog,currentVisibleRoute,persistVisibleRoute,restoreVisibleSettings,initialiseVisibleRoute,freeTokenRoute,freeTokenQualification,freeTokenExperimentalConsentRequired,freeTokenExperimentalConsentAccepted,resolvedClientSupport,runtimeKvValue,runtimeKvLabel,updateOmlxKvControl,setRuntimeKvValue,gatherOptions,gatherGenerationSettings,gatherChatSettings,gather,protectedSnapshot,speedSignature,optimizerEvidenceContractSignature,copiedEvidenceBinding,clearActiveEvidenceBinding,activeEvidenceBindingFor,rememberActiveEvidenceBinding,optimizerValueSnapshot,restoreOptimizerValues,clearOptimizerAnimationClasses,setOptimizationState,markOptimizerCustom,cancelOptimization,setOptimizerInteractionLocked,setOptimizerMenu,closeOptimizerMenu,toggleOptimizerMenu,reasoningChoices,normalizeReasoningSelection,clientInstalled,clientAvailability,chatSettingsError,limitError,rangePrecision,quantizedRangeValue,setRangeVisual,renderDflashReadiness,renderAneReadiness,updateAccelerationState,updateChatSamplingControls,warmRouteRequestSignature,currentWarmRoutePlan,visibleSessionAdmissionRequest,visibleSessionAdmissionSignature,sessionAdmissionDecision,currentSessionAdmission,sessionAdmissionBlockerCopy,scheduleSessionAdmissionPlan,requireFreshSessionAdmission,clearWarmRoutePlan,scheduleWarmRoutePlan,loadWarmRoutePlan,updateWorkSurface,updateContextChoices,refreshLaunchability,updateBackend,slotstreamDownloadMessage,renderModelOptions,applyModelChatDefaults,accelerationSelectionError,clearUnavailableModelControls,modelChanged,loadModels,freeTokenEndpointLabel,freeTokenSettingsError,updateFreeTokenNativeControls,renderFreeTokenConnection,openFreeTokenDialog,connectFreeToken,disconnectFreeToken,fieldForKey,revealFirstChangedControl,optimizerValueMatches,animateRange,animateOptimalControl,applyOptimal,prepareVerifiedQuickLaunch,preview,renderLaunchMemoryEstimate,updateLaunchHome,renderLaunchPreparation,startSimpleLaunch,cancelSimpleLaunch,launch,renderCacheObservatory,renderRequestActivity,renderFocusedRunStatus,renderRun,performanceReceiptSuite,performanceReceiptSuiteOrder,performanceReceiptNeedsFallback,performanceReceiptSuiteLabel,performanceReceiptRequest,performanceReceiptRequestKey,performanceReceiptAge,performanceReceiptView,renderEngineEvidenceChoices,renderPerformanceReceipt,loadPerformanceReceipt,schedulePerformanceReceipt,activatePerformanceReceipt,applyOptimizerMenuChoice,sessionDecisionClass,sessionProjectedLabel,sessionAttachmentRequest,syncSessionAttachmentForm,renderSessionAttachmentPanel,cancelSessionRequest,setSessionIdlePolicy,scheduleSessionAttachmentPlan,loadSessionAttachmentPlan,attachSessionSurface,renderSessionDashboard,loadSessionDashboard,openSessionDashboard,stopSessionFromDashboard,showLog,stopRun,setProfileSelect,applyProfileRequest,initialize,pollStatus};
  methods.view=()=>Object.freeze({backend:state.backend,client:state.client,phase:state.runPhase,launchPreparing:state.launchPreparing,applyingOptimal:state.applyingOptimal,optimalLabel:state.optimalLabel,modelCount:state.models.length,selectedModelId:String(state.selected?.id || ""),catalogNotice:state.catalogNotice,admissionLoading:state.sessionLoading});
  methods.runState=()=>structuredClone(state.runStatus);
  methods.activity=()=>structuredClone(state.requestActivity);
  methods.sessionState=()=>structuredClone(state.sessionDashboard);
  methods.receipt=()=>structuredClone(state.performanceReceipt);
  methods.catalog=()=>structuredClone(state.models);
  methods.setBackend=backend=>{state.backend=String(backend);};
  methods.selectBackend=(backend,preserveModel=false)=>{state.backend=String(backend);updateBackend(Boolean(preserveModel));};
  methods.selectClient=client=>{state.client=String(client);updateMtplxLongContextControl();refreshLaunchability();persistVisibleRoute(false);};
  methods.selectModelRoute=selectModelRoute;
  methods.useModelInventory=value=>{state.models=structuredClone(value);};
  methods.invalidateAttachmentPlan=()=>{state.sessionAttachmentPlan=null;state.sessionAttachmentSignature='';};
  methods.settingsView=()=>Object.freeze({backend:state.backend,client:state.client,optimalLabel:state.optimalLabel,applyingOptimal:state.applyingOptimal,routePreferenceReady:state.routePreferenceReady});
  methods.freeTokenView=()=>structuredClone(state.freeToken);
  methods.resetAcknowledgement=()=>{state.sessionAcknowledgementId='';};
  methods.continuePreparation=()=>{if(launchReviewResolve){launchReviewResolve(true);launchReviewResolve=null;}};
  methods.useFreeTokenFacts=value=>{state.freeToken=structuredClone(value);};
  methods.updateOwnedHub=(hub,ownerRunId)=>{if(state.runStatus?.run?.runId!==ownerRunId)return null;
   const nextHub=structuredClone(hub);
   state.runStatus={...state.runStatus,attachments:nextHub?.attachments||state.runStatus.attachments,agentConsoles:nextHub?.agentConsoles||[]};
   if(state.sessionDashboard)state.sessionDashboard.hub=nextHub;return structuredClone(state.runStatus);};
  methods.updateOwnedChatSettings=(ownerRunId,chat)=>{if(state.runStatus?.run?.runId===ownerRunId&&state.runStatus.run.client==='chat')state.runStatus.run.chat=structuredClone(chat);};
  for(const name of ['renderRun','renderRequestActivity','renderCacheObservatory']){const owned=methods[name];methods[name]=value=>owned(structuredClone(value));}
  for(const name of ['selectedModel','currentWarmRoutePlan','visibleRouteCatalog','benchmarkDisplayedStatus','loadSessionDashboard','loadSessionAttachmentPlan']){
   if(!methods[name])continue;const owned=methods[name];methods[name]=(...args)=>{const result=owned(...args);return result&&typeof result.then==='function'?result.then(value=>structuredClone(value)):structuredClone(result)};
  }
  return Object.freeze(methods);
 }
 return Object.freeze({createController,nodeIds:Object.freeze(["accelerationHelp","accelerationSelect","advancedControls","advancedSummary","agentConsoleLogButton","agentHostHelp","agentHostSelect","agentHostSettings","aneBadge","aneChecks","anePrefillHelp","anePrefillSelect","aneReleaseLink","aneStatus","applyOptimal","burstSelect","calibrationDialog","cancelLaunchPreparation","chatActivityDetail","chatActivityState","chatCacheDetail","chatCacheState","chatSamplingAdvancedSummary","chatSettings","chatStatusCache","chatStatusCacheValue","chatStatusLane","chatStatusLaneValue","chatStatusSpeed","chatStatusSpeedValue","compatibilityLine","configScroll","configSubtitle","configTitle","contextField","contextInput","contextSelect","continueLaunchPreparation","customLaunchEditor","depthHelp","depthInput","depthLabel","depthValue","dflashBadge","dflashChecks","dflashDraftQuantSelect","dflashStatus","dflashTuning","dflashVerifySelect","fanSelect","focusedConsoleButton","focusedLogButton","focusedRunMessage","focusedRunPhase","focusedRunStatus","focusedStopButton","freeTokenApiKey","freeTokenApiKeyHelp","freeTokenBadge","freeTokenBatchSelect","freeTokenConnect","freeTokenConnectionBanner","freeTokenConnectionDetail","freeTokenConnectionSummary","freeTokenConnectionTitle","freeTokenContext","freeTokenDialog","freeTokenDisconnect","freeTokenDocsLink","freeTokenEndpoint","freeTokenExperimentalConsent","freeTokenExperimentalConsentPanel","freeTokenExpertCacheInput","freeTokenForm","freeTokenInstallLink","freeTokenNativeControlStatus","freeTokenNativeControls","freeTokenPlatform","freeTokenPrefixCacheSelect","freeTokenQualificationDetail","freeTokenQualificationMark","freeTokenQualificationPanel","freeTokenQualificationTitle","freeTokenRemoteControls","freeTokenStatus","freetokenControls","frequencyPenaltyInput","gpuSelect","healthPill","homeCompareEngines","homeEngineGuide","homeEngineSelect","homeFastestEngine","homeFastestEngineHelp","homeLaunchDetail","homeLaunchHint","homeMeasuredFirst","homeMeasuredSpeed","homeMeasurementDetail","homeModelList","homeModelSearch","homeModelSearchStatus","homePerformance","homeRouteAgent","homeRouteContext","homeRouteEngine","homeRouteMeta","homeRouteModel","homeRouteOutput","homeRouteReadiness","homeSettingsSummary","hubToolsMenuButton","kolibriControls","kolibriKv","kolibriMemoryGB","kolibriMemoryMode","kolibriPrefillSelect","kolibriPromptCacheGB","launchButton","launchLabel","launchMemoryEstimate","launchOverview","launchPreparation","launchPreparationDetail","launchPreparationMark","launchPreparationProgress","launchPreparationTitle","launchSettings","launchSummary","launchTools","llamacppControls","lmstudioControls","lmstudioMtpTuning","localChip","logButton","logContent","logDialog","memoryGuardSelect","mferenceControls","mferencePromptCache","mferenceQueueLimit","modelCard","modelSelect","mtpMinContinueProbabilityInput","mtpMinContinueProbabilityValue","mtpMinTokensInput","mtpMinTokensValue","mtplxControls","mtplxKv","mtplxOperatorRouteHelp","mtplxOperatorRouteSelect","notice","omlxControls","omlxEffectiveKv","omlxExpertControls","omlxExpertResidentPercent","omlxKv","omlxKvHint","omlxKvLabel","omlxMemoryGB","openAneButton","openFreeTokenConnection","openSetupButton","optimizationBadge","optimizationPanel","optimizationStatus","optimizerAction","optimizerCalibrate","optimizerMenu","optimizerMenuButton","optimizerVerifiedLaunch","outputInput","parallelInput","parallelValue","performanceReceipt","performanceReceiptAction","performanceReceiptDetail","performanceReceiptIcon","performanceReceiptTitle","phaseBadge","presencePenaltyInput","previewButton","previewContent","previewDialog","profileDialog","profileSelect","projectLabel","projectPath","quickStart","qwenPleMemoryControls","reasoningSelect","refreshModels","repetitionPenaltyInput","routeCheckButton","routeCheckDialog","runFacts","rapidmlxControls","rapidmlxDepthSelect","rapidmlxMtpHelp","recControls","runtimeDialog","samplingHelp","samplingMode","seedInput","sessionActiveRoute","sessionActiveState","sessionActivityCoverage","sessionActivityDetail","sessionActivityFacts","sessionActivityList","sessionActivitySection","sessionActivityState","sessionAdmissionDetail","sessionAdmissionState","sessionAdmissionTitle","sessionAttachAgentHost","sessionAttachButton","sessionAttachChatPanel","sessionAttachClient","sessionAttachControls","sessionAttachFrequencyPenalty","sessionAttachHostField","sessionAttachHostHelp","sessionAttachPlanDetail","sessionAttachPresencePenalty","sessionAttachProject","sessionAttachProjectField","sessionAttachRepetitionPenalty","sessionAttachSampling","sessionAttachSeed","sessionAttachStatus","sessionAttachSystemPrompt","sessionAttachSystemPromptField","sessionAttachTemperature","sessionAttachTopK","sessionAttachTopP","sessionAttachmentList","sessionBadge","sessionCacheCoverage","sessionCacheFacts","sessionCacheLast","sessionCachePolicy","sessionCacheSection","sessionCacheState","sessionComponents","sessionConsent","sessionConsentCopy","sessionConsentPanel","sessionDashboardStatus","sessionDialog","sessionEstimateBar","sessionEstimateBasis","sessionEstimateFacts","sessionIdlePolicyDetail","sessionIdleTimeout","sessionMemoryBar","sessionOwnershipDetail","sessionRefreshButton","sessionResourceDetail","sessionResourceFacts","sessionResourceState","sessionSetDialog","sessionStopButton","sessionSurfaceDetail","sessionSurfaceSection","sessionSurfaceState","sharedRuntimeControls","slotstreamControls","slotstreamDownloadStatus","slotstreamKv","slotstreamMemoryGB","slotstreamMemoryMode","splashAccelerationHelp","splashAccelerationSelect","splashControls","strataControls","ssdRuntimeDisclosure","ssdRuntimeStatus","statusMessage","stopButton","swiftlmControls","swiftlmPrefillSelect","swiftlmTopK","swiftlmTopKHelp","systemPrompt","systemPromptField","temperatureInput","themeMenuButton","topKInput","topPInput","uzuAccelerationLabel","uzuControls","whallmControls"]),endpointNames:Object.freeze({"/api/benchmark/history":"benchmarkHistory","/api/benchmark/start":"benchmarkStart","/api/benchmark/status":"benchmarkStatus","/api/benchmark/stop":"benchmarkStop","/api/calibration/plan":"calibrationPlan","/api/freetoken/connect":"freetokenConnect","/api/freetoken/disconnect":"freetokenDisconnect","/api/launch":"launch","/api/log":"log","/api/models":"models","/api/optimal":"optimal","/api/optimal-engine":"optimalEngine","/api/preview":"preview","/api/session/attach":"sessionAttach","/api/session/attachment-plan":"sessionAttachmentPlan","/api/session/idle-policy":"sessionIdlePolicy","/api/session/plan":"sessionPlan","/api/session/request/cancel":"sessionRequestCancel","/api/session/warm-attach":"sessionWarmAttach","/api/session/warm-plan":"sessionWarmPlan","/api/status":"status","/api/stop":"stop"})});
});
