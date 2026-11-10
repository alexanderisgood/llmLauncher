/* Complete Benchmark Lab and Calibration workspace; exact evidence stays authoritative. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;root.LLMBenchmarkWorkspace=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 function freezeCopy(value){
  if(Array.isArray(value))return Object.freeze(value.map(freezeCopy));
  if(value&&typeof value==='object')return Object.freeze(Object.fromEntries(Object.entries(value).map(([key,item])=>[key,freezeCopy(item)])));
  return value;
 }
 function createController(options){
  const {nodes,network,platform,formatting,capabilities,settings:settingsPort,evidence,operations,effects,receipt:receiptPort,polling}=options;
  const CalibrationDecision=options.decision;
  const policy=freezeCopy(options.policy);
  const enginePreferenceLabels=Object.freeze({...options.preferenceLabels});
  const $=id=>nodes[id];
  const {setTimeout,clearTimeout}=platform;
  let calibrationError="",benchmarkError="",statusEpoch=0,reviewGeneration=0;
  const state={calibrationPlan: null,calibrationLoading: false,calibrationGeneration: 0,calibrationEntry: null,calibrationDetailsOpen: false,calibrationJobId: "",calibrationCompletionId: "",calibrationApplying: false,calibrationStarting: false,calibrationProfileContractId: "",benchmarkPhase: "idle",benchmarkResultId: "",benchmarkStatus: null,benchmarkReview: null,benchmarkHistory: null,benchmarkHistoryKey: "",benchmarkHistoryLoading: false,benchmarkHistoryGeneration: 0,benchmarkHistoryTimer: null,benchmarkHistoryError: ""};
  Object.defineProperties(state,{
   backend:{get:()=>settingsPort.snapshot().backend},client:{get:()=>settingsPort.snapshot().client},
   runPhase:{get:()=>operations.snapshot().runPhase},setupPhase:{get:()=>operations.snapshot().setupPhase},
   optimalLabel:{get:()=>settingsPort.snapshot().optimalLabel},performanceReceipt:{get:()=>receiptPort.current()},
  });
  const renderedMarkup=new WeakMap();
  function setMarkup(node,markup){
   if(renderedMarkup.get(node)===markup)return;
   node.innerHTML=markup;renderedMarkup.set(node,markup);
  }
  const endpoints=Object.freeze({'/api/benchmark/history':'history','/api/benchmark/start':'start','/api/benchmark/stop':'stop',
   '/api/calibration/plan':'plan','/api/profiles/save':'saveProfile'});
  const api=(path,options)=>network[endpoints[path]](options);
  let initialized=false,pollTask=null;
  const pollBenchmarkStatus=()=>pollTask?pollTask():Promise.resolve();
function benchmarkCandidates(cap = {}, backend = state.backend) {
  if (backend === "freetoken") return [{
    id:cap.native === true ? "native" : "remote",
    label:cap.native === true ? "Native greedy" : "Server managed",
    available:Boolean(cap.runnable),
  }];
  if (backend === "llamacpp") return [{
    id:"ar", label:"SSD PLE", available:capabilities.llamaCppPleCapabilityQualified(cap),
  }];
  if (backend === "uzu") return [{
    id:"ar",
    label:typeof cap.runtimeManagedAcceleration === "string" && cap.runtimeManagedAcceleration.trim()
      ? cap.runtimeManagedAcceleration.trim() : "DFlash + Weaver",
    available:Boolean(cap.runnable),
  }];
  if (["swiftlm", "mference", "whallm"].includes(backend)) return [{
    id:"ar", label:"Exact SSD stream", available:Boolean(cap.runnable),
  }];
  const modes = [{id:"ar", label:"AR", available:Boolean(cap.runnable)}];
  if (cap.mtp) modes.push({id:"mtp", label:"MTP", available:true});
  if (backend === "omlx" && cap.dflash) modes.push({id:"dflash2", label:"DFlash 2", available:true});
  return modes;
}

function engineShootoutRoutes(model = capabilities.selectedModel()) {
  if (!model) return [];
  const kv = settingsPort.runtimeKvValue();
  const reasoning = $("reasoningSelect").value;
  const binaryKeys = Object.fromEntries(
    capabilities.visibleEngineAdapters().map(adapter => [adapter.id, adapter.binaryKey]),
  );
  const kvChoices = {omlx:["off","q8","q6","q4"], lmstudio:["off"], mtplx:["off","q8","q4"], uzu:["off"], freetoken:["off"], swiftlm:["off"], mference:["off"], whallm:["off"], slotstream:model.backends?.slotstream?.kvChoices || ["off"], splash:["off"], strata:["off"], rec:["off"], llamacpp:["off"], rapidmlx:["off"], kolibri:model.backends?.kolibri?.kvChoices || ["off"]};
  const ssdLane = model.ssdStreaming?.recommended === true;
  const ssdBackends = model.ssdStreaming?.calibration?.engines || ["swiftlm", "mference"];
  const backends = capabilities.visibleEngineAdapters().map(adapter => adapter.id)
    .filter(backend => backend !== "llamacpp")
    .filter(backend => !ssdLane || ssdBackends.includes(backend) || model.backends?.[backend]?.runnable === true);
  return backends.map(backend => {
    const cap = model.backends?.[backend] || {};
    const support = capabilities.resolvedClientSupport(backend, state.client, model);
    const routeReasoning = cap[state.client === "codex" ? "codexReasoning" : "agentReasoning"] || ["auto"];
    const benchmarkReasoning = cap.agentReasoning || ["auto"];
    let reason = "";
    const binaryKey = binaryKeys[backend] || capabilities.backendBinaryKey(backend);
    if (!capabilities.runtimeInstalled(binaryKey)) reason = "Runtime not installed";
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
      backend, label:formatting.backendName(backend), eligible:!reason, reason,
      modes:benchmarkCandidates(cap, backend),
    };
  });
}

function benchmarkWinnerLabel(winner) {
  return ({ar:"AR", mtp:"MTP", dflash2:"DFlash 2", "dflash-weaver":"DFlash + Weaver"})[winner] || winner || "Unknown";
}

function renderBenchmarkCard() {
  const model = capabilities.selectedModel();
  const cap = model?.backends?.[state.backend] || {};
  const candidates = model ? benchmarkCandidates(cap) : [];
  const benchmark = cap.localBenchmark;
  const badge = $("benchmarkCardBadge");
  setMarkup($("benchmarkCardModes"), candidates.map(mode => `<span class="${mode.available ? "available" : ""}${benchmark?.winner === mode.id ? " winner" : ""}">${formatting.esc(mode.label)}</span>`).join(""));
  if (!model) {
    badge.textContent = "No model";
    $("benchmarkCardSummary").textContent = "Select a runnable model to inspect its measurable acceleration routes.";
    $("openBenchmarkButton").disabled = true;
    return;
  }
  if (state.backend === "freetoken" && capabilities.freeTokenRoute(model) === "remote") {
    badge.textContent = "Live TPS";
    $("benchmarkCardSummary").textContent = "Chat and Hub Console show the connected route's live TPS. Remote-host and network performance stay outside the Mac-only Benchmark Lab.";
    $("openBenchmarkButton").disabled = true;
    return;
  }
  if (state.backend === "freetoken" && capabilities.freeTokenRoute(model) === "native") {
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
  } else if (state.backend === "uzu") {
    badge.textContent = "Fixed route";
    $("benchmarkCardSummary").textContent = `${candidates[0]?.label || "DFlash + Weaver"} is bundled with this checkpoint and measured as one complete Uzu route.`;
  } else {
    badge.textContent = "AR only";
    $("benchmarkCardSummary").textContent = "No verified acceleration competitor is available for this exact route yet.";
  }
}

function renderBenchmarkSetup() {
  const model = capabilities.selectedModel();
  const cap = model?.backends?.[state.backend] || {};
  const candidates = model ? benchmarkCandidates(cap) : [];
  const engineRoutes = engineShootoutRoutes(model);
  const eligibleEngines = engineRoutes.filter(route => route.eligible);
  const suite = $("benchmarkSuiteSelect").value;
  const agentic = suite === "agentic";
  const mtplxOperators = Boolean(
    state.backend === "mtplx" && agentic && capabilities.mtplxLongContextCapabilityExact(model)
    && Number($("contextInput").value) >= 65_536
    && $("profileSelect").value === "turbo"
  );
  $("benchmarkStartLabel").textContent = mtplxOperators
    ? "3 setups · AR + MTP default + long-context"
    : agentic ? "Four staged turns per route" : "Reloads each measured route";
  $("benchmarkRoute").textContent = model
    ? `${formatting.backendName(state.backend)} · ${model.name} · ${agentic ? "agent-shaped" : "prompt-range"} evidence bound to ${formatting.clientName(state.client)}`
    : "Choose a runnable model and acceleration route.";
  setMarkup($("benchmarkModes"), candidates.map(mode => `<span class="${mode.available ? "available" : ""}">${formatting.esc(mode.label)}</span>`).join(""));
  if (mtplxOperators) {
    setMarkup($("benchmarkModes"), ["AR", "MTP · default", "MTP · 2.11 long-context"]
      .map(label => `<span class="available">${formatting.esc(label)}</span>`).join(""));
    $("benchmarkSuiteHelp").textContent = "Current engine: three isolated loads, 18 generated requests, with near-64K prompts. Keeps your reasoning, sampling, KV and cooling settings.";
  } else if (agentic) {
    $("benchmarkSuiteHelp").textContent = "Four staged coding-agent turns: cold 8K prefix, shared-prefix reuse, 4K synthetic tool-result ingestion, and a warm follow-up.";
  }
  setMarkup($("benchmarkEngineStrip"), engineRoutes.map(route => {
    const routeModes = route.modes.map(mode => mode.label).join(" + ");
    const detail = route.eligible ? routeModes : route.reason;
    return `<span class="${route.eligible ? "available" : "excluded"}" title="${formatting.esc(detail)}"><i aria-hidden="true">${route.eligible ? "✓" : "×"}</i><b>${formatting.esc(route.label)}</b><small>${formatting.esc(detail)}</small></span>`;
  }).join(""));
  const remoteEngine = state.backend === "freetoken" && capabilities.freeTokenRoute(model) === "remote";
  const nativeFreeToken = state.backend === "freetoken" && capabilities.freeTokenRoute(model) === "native";
  const sharedWhallm = state.backend === "whallm" && model?.sharedServer === true;
  const comparisonExcluded = remoteEngine || nativeFreeToken || sharedWhallm;
  const comparable = Boolean(model && cap.runnable && candidates.length > 1 && !comparisonExcluded);
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
  const acquisitionActive = operations.acquisitionIsActive();
  const routeCheckActive = operations.routeCheckIsActive();
  const aneActive = operations.aneWorkIsActive();
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
    : sharedWhallm
    ? "Whallm owns a separate full-expert checkpoint. Use its live local TPS and route telemetry; it is never treated as equivalent to a pruned REAP or repacked artifact."
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
      ? `This suite needs at least ${formatting.formatNumber(suiteRequirement)} context tokens; the visible context is ${formatting.formatNumber(visibleContext)}.`
      : agentic
        ? `Uses the visible ${formatting.formatNumber(visibleContext)} context and four growing turns with the exact ${$("reasoningSelect").value} reasoning, sampling, KV, and tuning contract.`
        : `Uses the visible ${formatting.formatNumber(visibleContext)} context, ${$("reasoningSelect").value} reasoning, sampling, KV, and tuning controls.`;
  $("benchmarkShootoutLabel").textContent = eligibleEngines.length >= 2
    ? `${eligibleEngines.length} engines · ${shootoutRoutes} routes · ${shootoutRoutes * stepsPerRoute} measured steps`
    : "Needs at least two contract-compatible engines";
  $("benchmarkScenarioStrip").classList.toggle("hidden", !agentic);
}

function benchmarkHistoryRequest() {
  const request = settingsPort.gather("custom");
  request.suite = $("benchmarkSuiteSelect").value;
  request.enginePreference = $("benchmarkPreferenceSelect").value;
  return request;
}

function benchmarkHistoryRequestKey(request) {
  return JSON.stringify({
    modelId:request.modelId, backend:request.backend, client:request.client,
    context:request.context, output:request.output, reasoning:request.reasoning,
    options:request.options || {}, chat:request.chat || null, generation:request.generation || null,
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
  return `<svg class="benchmark-history-sparkline" viewBox="0 0 ${width} ${height}" role="img" aria-label="${formatting.esc(series.label)} trend across ${points.length} matching runs"><polyline points="${line}"></polyline><circle cx="${lastX.toFixed(1)}" cy="${lastY.toFixed(1)}" r="2.4"></circle></svg>`;
}

function renderBenchmarkHistory() {
  const history = state.benchmarkHistory;
  const badge = $("benchmarkHistoryBadge");
  const freshness = $("benchmarkHistoryFreshness");
  const active = ["queued","cooldown","starting","running","stopping"].includes(state.benchmarkPhase);
  $("benchmarkHistoryRetry").classList.toggle("hidden", !state.benchmarkHistoryError);
  $("benchmarkHistoryRetry").disabled=state.benchmarkHistoryLoading;
  if (state.benchmarkHistoryLoading && !history) {
    badge.textContent = "Loading…";
    freshness.className = "benchmark-history-freshness";
    freshness.textContent = "Checking saved local evidence for every visible contract field…";
    setMarkup($("benchmarkHistoryTrend"), "");
    setMarkup($("benchmarkHistoryRuns"), "");
    setMarkup($("benchmarkHistoryOther"), "");
    $("benchmarkHistoryRerun").disabled = true;
    return;
  }
  if (!history) {
    badge.textContent = "Unavailable";
    freshness.className = "benchmark-history-freshness warning";
    freshness.textContent = state.benchmarkHistoryError || "History could not be loaded for this selection.";
    $("benchmarkHistoryRerun").disabled = true;
    setMarkup($("benchmarkHistoryTrend"), "");
    setMarkup($("benchmarkHistoryRuns"), "");
    setMarkup($("benchmarkHistoryOther"), "");
    return;
  }
  badge.textContent = history.shootoutCount
    ? `${history.shootoutCount} matching shootout${history.shootoutCount === 1 ? "" : "s"}`
    : (history.currentRouteRuns?.length ? `${history.currentRouteRuns.length} route run${history.currentRouteRuns.length === 1 ? "" : "s"}` : "No exact runs");
  freshness.className = `benchmark-history-freshness ${history.freshness === "current" ? "current" : "warning"}`;
  freshness.textContent = history.freshnessMessage;
  if(state.benchmarkHistoryError){
    badge.textContent="Refresh failed";
    freshness.className="benchmark-history-freshness warning";
    freshness.textContent=`${state.benchmarkHistoryError} Last loaded history is shown; retry to refresh it.`;
  }
  setMarkup($("benchmarkHistoryTrend"), (history.series || []).map(series => {
    const latest = series.points?.at(-1);
    const change = series.improvementPercent;
    const changeClass = typeof change === "number" ? (change > 0.5 ? "improved" : (change < -0.5 ? "regressed" : "flat")) : "flat";
    const changeText = typeof change === "number"
      ? `${change > 0 ? "+" : ""}${change.toFixed(1)}% vs previous`
      : `${series.points?.length || 0} matching run${series.points?.length === 1 ? "" : "s"}`;
    return `<article class="benchmark-history-series"><div><strong>${formatting.esc(series.label)}</strong><small>${formatting.esc(latest?.display || "No comparable value")}</small><em class="${changeClass}">${formatting.esc(changeText)}</em></div>${benchmarkHistorySparkline(series)}</article>`;
  }).join("") || `<p class="benchmark-history-empty">A second complete matching shootout will create per-engine trend lines.</p>`);
  const runRows = (history.runs || []).map(run => {
    const statusLabel = ({trusted:"Usable result",tie:"Practical tie",incomplete:"Incomplete test","workload-mismatch":"Workload mismatch","conditions-mismatched":"Conditions differed"})[run.status] || run.status;
    const engines = (run.engines || [])
      .filter(engine => capabilities.uiEngineVisible(engine.backend || engine.id))
      .map(engine => `${engine.label} · ${engine.valueDisplay}`).join("  |  ");
    return `<article class="benchmark-history-run ${formatting.esc(run.status)}"><div class="benchmark-history-run-head"><strong>${formatting.esc(benchmarkHistoryDate(run.createdAt))}</strong><em>${formatting.esc(statusLabel)}</em></div><p>${run.trustedWinner ? `<b>${formatting.esc(run.winnerLabel)} won.</b> ` : ""}${formatting.esc(run.summary)}</p><small>${formatting.esc(engines)}</small></article>`;
  });
  const routeRows = (history.currentRouteRuns || []).map(run => `<article class="benchmark-history-run"><div class="benchmark-history-run-head"><strong>${formatting.esc(benchmarkHistoryDate(run.createdAt))}</strong><button type="button" class="text-button" data-review-benchmark="${formatting.esc(run.id)}" data-review-suite="${formatting.esc(run.suite || history.contract.suite)}" ${active ? "disabled" : ""}>View results</button></div><p><b>${formatting.esc(run.winnerLabel)} route.</b> ${formatting.esc(run.recommendation || "Measured locally.")}</p><small>${formatting.esc(run.display)}</small></article>`);
  setMarkup($("benchmarkHistoryRuns"), [...runRows, ...routeRows].join("") || `<p class="benchmark-history-empty">No saved run matches this exact visible contract yet.</p>`);
  const other = history.otherEvidence || {};
  setMarkup($("benchmarkHistoryOther"), other.count
    ? `<span>Retained but not comparable now</span>${(other.reasons || []).map(item => `<em>${formatting.esc(item.label)} · ${Number(item.count || 0)}</em>`).join("")}`
    : `<span>No mismatched historical evidence for this model.</span>`);
  const rerun = $("benchmarkHistoryRerun");
  rerun.disabled = active || Boolean(state.benchmarkHistoryError) || !history.canRerunShootout;
  rerun.textContent = history.canRerunShootout ? "Rerun this visible contract" : "Needs two compatible engines";
}

async function loadBenchmarkHistory(force = false) {
  const generation = ++state.benchmarkHistoryGeneration;
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
    state.benchmarkHistoryLoading=false;
    renderBenchmarkHistory();
    return;
  }
  state.benchmarkHistoryLoading = true;
  state.benchmarkHistoryError = "";
  if (key !== state.benchmarkHistoryKey) state.benchmarkHistory = null;
  renderBenchmarkHistory();
  try {
    const data = await api("/api/benchmark/history", {method:"POST",body:JSON.stringify(request)});
    if (generation !== state.benchmarkHistoryGeneration) return;
    // The current-engine 64K sweep has a different input schedule from the
    // cross-engine Agentic suite. Keep both histories without conflating them.
    if (request.backend === "mtplx" && request.suite === "agentic"
        && Number(request.context) >= 65536 && request.options?.profile === "turbo"
        && capabilities.mtplxLongContextCapabilityExact(capabilities.selectedModel())) {
      const extra = await api("/api/benchmark/history", {method:"POST", body:JSON.stringify({
        ...request, suite:policy.MTPLX_LONG_CONTEXT_SUITE,
      })});
      if (generation !== state.benchmarkHistoryGeneration) return;
      data.history.currentRouteRuns = [
        ...(extra.history.currentRouteRuns || []), ...(data.history.currentRouteRuns || []),
      ];
      if (extra.history.currentRouteRuns?.length && !data.history.exactRecordCount) {
        data.history.freshnessMessage = "Saved current-engine settings tests are available below. No matching cross-engine comparison for this workload yet.";
      }
    }
    state.benchmarkHistoryKey = key;
    state.benchmarkHistory = data.history;
  } catch (error) {
    if (generation !== state.benchmarkHistoryGeneration) return;
    if(key !== state.benchmarkHistoryKey) state.benchmarkHistory = null;
    state.benchmarkHistoryError = String(error.message || "History could not be refreshed.").slice(0,2048);
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

function benchmarkDisplayedStatus(status = state.benchmarkStatus || {}) {
  const review = state.benchmarkReview;
  if (!review) return status;
  let key;
  try { key = benchmarkHistoryRequestKey(benchmarkHistoryRequest()); } catch (_) {}
  if (["queued", "cooldown", "starting", "running", "stopping"].includes(status.phase)
      || key !== review.requestKey || (status.job?.id || null) !== review.jobId) {
    state.benchmarkReview = null;
    return status;
  }
  return {phase:"completed", progress:1, result:review.result, savedReview:true};
}

async function reviewBenchmarkResult(recordId, suite) {
  const generation=++reviewGeneration;
  try {
    if (calibrationBenchmarkActive()) return;
    const request = benchmarkHistoryRequest();
    const requestKey = benchmarkHistoryRequestKey(request);
    const jobId = state.benchmarkStatus?.job?.id || null;
    const data = await api("/api/benchmark/history", {method:"POST", body:JSON.stringify({
      ...request, suite, reviewRecordId:recordId,
    })});
    if (generation !== reviewGeneration || calibrationBenchmarkActive() || requestKey !== benchmarkHistoryRequestKey(benchmarkHistoryRequest())
        || jobId !== (state.benchmarkStatus?.job?.id || null)) return;
    if (data.history?.reviewResult?.id !== recordId) throw new Error("That saved result is unavailable.");
    state.benchmarkReview = {result:data.history.reviewResult, requestKey, jobId};
    renderBenchmarkStatus(state.benchmarkStatus || {phase:"idle"});
    $("benchmarkHistoryPanel").open = false;
    $("benchmarkResults").scrollIntoView({block:"nearest"});
  } catch (error) { if(generation===reviewGeneration) effects.showNotice(error.message, true); }
}

function calibrationSuiteControlValue(suite) {
  if (capabilities.isUzuQualificationSuite(suite)) return "agentic";
  return suite === policy.LLAMACPP_PLE_QUALIFICATION_SUITE ? "agentic" : suite;
}

async function openPerformanceBenchmarkLab(receipt = state.performanceReceipt) {
  $("benchmarkSuiteSelect").value = calibrationSuiteControlValue(
    receipt?.suite || receiptPort.performanceReceiptSuite(),
  );
  $("benchmarkPreferenceSelect").value = "throughput";
  await openBenchmarkLab();
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
    throughput:"Ranks each engine's correctness-verified safe route by median generation TPS; leads below 3% remain ties.",
    fastest:"Ranks aggregate output speed for ordinary suites or total staged time for Agentic.",
    responsive:"Ranks the median measured time to first output; a lead below 3% remains a tie.",
    memory:"Ranks the smallest system-wide unified-memory headroom drop; differences below 512 MB remain a tie.",
    thermal:"Requires every engine to start at the same public macOS thermal state, then ranks worst state and speed.",
  };
  $("benchmarkPreferenceHelp").textContent = help[preference] || help.fastest;
  if (state.benchmarkStatus) renderBenchmarkResults(benchmarkDisplayedStatus());
  renderBenchmarkSetup();
  scheduleBenchmarkHistory();
}

function engineShootoutApplyBinding(result, profile, preference) {
  const candidate = profile?.evidenceBinding
    || (result?.selectedPreference === preference ? result?.evidenceBinding : null);
  const recordIds = candidate?.recordIds;
  if (
    !candidate || typeof candidate !== "object" || Array.isArray(candidate)
    || candidate.scope !== "engine"
    || candidate.suite !== result?.suite
    || candidate.preference !== preference
    || candidate.shootoutId !== result?.id
    || !recordIds || typeof recordIds !== "object" || Array.isArray(recordIds)
    || !Object.keys(recordIds).length
  ) return null;
  return JSON.parse(JSON.stringify(candidate));
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
  }))).filter(engine => capabilities.uiEngineVisible(engine.backend));
  const recommended = profile?.backend || result?.recommendedBackend;
  const trustedWinner = Boolean(profile?.trustedWinner ?? result?.trustedWinner);
  const applyReadyTier = [
    "cross-engine-local-benchmark",
    "cross-engine-leading-band",
    "cross-engine-noise-floor",
  ].includes(profile?.evidenceTier);
  const applyBinding = result?.matrixWorkloadComparable !== false && applyReadyTier
    ? engineShootoutApplyBinding(result, profile, preference) : null;
  const profileComparisons = new Map((profile?.comparedEngines || []).map(item => [item.backend, item]));
  const cards = engines.map(engine => {
    const winner = Boolean(applyBinding && engine.backend === recommended);
    const profileComparison = profileComparisons.get(engine.backend);
    const modeLabel = engine.routeSettingsLabel
      || engine.modeLabel || (engine.mode ? benchmarkWinnerLabel(engine.mode) : "Measuring…");
    const qualityText = !result
      ? "Waiting for the complete matrix"
      : engine.qualityMatchesMatrix
        ? "✓ Greedy output agrees across engines"
        : "! Greedy output differs from the matrix";
    const memoryText = Number.isInteger(engine.peakPressureDeltaBytes)
      ? `${formatting.formatBytes(engine.peakPressureDeltaBytes)} · ${Number(engine.minimumHeadroomPercent || 0).toFixed(0)}% left`
      : "Not measured";
    const ttftText = typeof engine.firstTokenSeconds === "number" && Number.isFinite(engine.firstTokenSeconds) ? `${engine.firstTokenSeconds.toFixed(2)} s` : "Not measured";
    const thermalText = engine.thermalWorst && engine.thermalWorst !== "unavailable"
      ? (engine.thermalStart && engine.thermalStart !== "unavailable" ? `${engine.thermalStart} → ${engine.thermalWorst}` : engine.thermalWorst)
      : "Not measured";
    const cooldownText = ({"reference-ready":"Reference ready",ready:"Comparable",timeout:"Timed out","condition-improved":"Higher headroom",unavailable:"Unavailable"})[engine.resourceCooldownStatus] || "Not measured";
    const decodeTps = formatting.finiteMetric(engine.decodeTokensPerSecond);
    const badge = winner ? enginePreferenceLabels[preference] : (profileComparison?.profileDisplay || engine.display || "Queued");
    return `<article class="benchmark-result engine-result ${winner ? "winner" : ""}"><div class="benchmark-result-head"><strong>${formatting.esc(engine.label || formatting.backendName(engine.backend))}</strong><em>${formatting.esc(badge)}</em></div><div class="benchmark-metrics"><span>Fastest safe route<b>${formatting.esc(modeLabel)}</b></span><span>Workload result<b>${formatting.esc(engine.display || "Measuring…")}</b></span><span>Generation speed<b>${decodeTps === null ? "Not measured" : `${decodeTps.toFixed(1)} tok/s`}</b></span><span>First output<b>${formatting.esc(ttftText)}</b></span><span>Memory use<b>${formatting.esc(memoryText)}</b></span><span>Thermal state<b>${formatting.esc(thermalText)}</b></span><span>Start gate<b>${formatting.esc(cooldownText)}</b></span></div>${engine.runtimeVersion ? `<p class="benchmark-runtime">${formatting.esc(engine.runtimeVersion)}</p>` : ""}<p class="benchmark-quality ${result && !engine.qualityMatchesMatrix ? "bad" : ""}">${qualityText}</p></article>`;
  }).join("");
  const recommendationText = profile?.recommendation || result?.recommendation;
  const recommendationHeading = trustedWinner
    ? `${profile?.label || result?.decision?.label || formatting.backendName(recommended)} wins for ${enginePreferenceLabels[preference] || "this goal"}.`
    : profile?.engineChanged
      ? `${profile?.label || formatting.backendName(recommended)} leads the measured group.`
      : `${profile?.label || formatting.backendName(recommended)} stays selected.`;
  const recommendation = recommendationText
    ? `<div class="benchmark-recommendation"><span><strong>${formatting.esc(recommendationHeading)}</strong> ${formatting.esc(recommendationText)}</span>${applyBinding ? `<button type="button" class="text-button" data-apply-shootout>Apply ${formatting.esc(enginePreferenceLabels[preference] || "measured result")}</button>` : ""}</div>`
    : "";
  setMarkup($("benchmarkResults"), cards + recommendation);
}

function renderMtpTuningResults(status) {
  const result = status.result?.kind === "lmstudio-mtp-tuning" ? status.result : null;
  const sweep = result?.tuningSweep || status.tuning || {};
  const candidates = Array.isArray(sweep.candidates) ? sweep.candidates : [];
  const selectedKey = sweep.selectedCandidateKey || "";
  const baseline = result?.modes?.ar || status.modes?.ar;
  const selectedSettings = sweep.selectedSettings || candidates.find(item => item.key === selectedKey)?.settings;
  const winner = result?.winner;
  const selectionMetric = sweep.selectionMetric || status.job?.tuningPlan?.selectionMetric || result?.selectionMetric || "end-to-end-tokens-per-second";
  const generationMetric = selectionMetric === "generation-tokens-per-second";
  const selectedSpeedField = generationMetric ? "medianDecodeTokensPerSecond" : "medianEndToEndTokensPerSecond";
  const selectedSpeedLabel = generationMetric ? "Generation TPS" : "End-to-end TPS";
  const baselineSpeed = Number(baseline?.[selectedSpeedField]);
  const facts = `<div class="benchmark-tuning-facts"><span><small>AR ${formatting.esc(selectedSpeedLabel)}</small><b>${Number.isFinite(baselineSpeed) ? `${baselineSpeed.toFixed(1)} tok/s` : "Preparing…"}</b></span><span><small>Search progress</small><b>${candidates.length} / ${Number(sweep.maximumCandidates || status.job?.tuningPlan?.maximumMtpCandidates || 10)} candidates</b></span><span><small>Current choice</small><b>${selectedSettings ? `max ${selectedSettings.depth} · min ${selectedSettings.mtpMinTokens} · ${Number(selectedSettings.mtpMinContinueProbability).toFixed(2)}` : "Waiting…"}</b></span><span><small>Final route</small><b>${winner ? benchmarkWinnerLabel(winner) : "Not committed"}</b></span></div>`;
  const stageLabels = {depth:"Draft maximum",cutoff:"Probability cutoff",minimum:"Draft minimum"};
  const cards = candidates.length
    ? `<div class="benchmark-tuning-candidates">${candidates.map(candidate => {
      const settings = candidate.settings || {};
      const selected = candidate.key === selectedKey || candidate.selected === true;
      const badge = selected ? (result ? "Selected" : "Leading") : (stageLabels[candidate.stage] || "Measured");
      const quality = candidate.qualityMatchesAR === true;
      return `<article class="benchmark-tuning-candidate ${selected ? "selected" : ""} ${quality ? "" : "mismatch"}"><header><strong>max ${formatting.esc(settings.depth)} · min ${formatting.esc(settings.mtpMinTokens)} · cutoff ${Number(settings.mtpMinContinueProbability || 0).toFixed(2)}</strong><em>${formatting.esc(badge)}</em></header><div><span>Median <b>${Number(candidate.medianSpeedupVsAR || 0).toFixed(2)}× AR</b></span><span>Worst <b>${Number(candidate.worstCaseSpeedupVsAR || 0).toFixed(2)}× AR</b></span><span>${formatting.esc(selectedSpeedLabel)} <b>${Number(candidate[selectedSpeedField] || 0).toFixed(1)} tok/s</b></span></div><p class="benchmark-quality ${quality ? "" : "bad"}">${quality ? "✓ Exact greedy output matches AR" : "! Greedy output mismatch"}</p></article>`;
    }).join("")}</div>`
    : `<p class="benchmark-tuning-empty">The AR reference is measured first. Candidate results appear here as complete, cache-isolated loads finish.</p>`;
  const recommendation = result?.recommendation
    ? `<div class="benchmark-recommendation"><strong>${formatting.esc(benchmarkWinnerLabel(result.winner))} recommendation.</strong> ${formatting.esc(result.recommendation)}</div>`
    : "";
  setMarkup($("benchmarkResults"), `<section class="benchmark-tuning-result"><div class="benchmark-tuning-result-head"><div><span>Bounded LM Studio search</span><strong>${result ? "Complete evidence contract" : "Provisional measurements"}</strong></div><em>${candidates.length} tested</em></div>${facts}${cards}</section>${recommendation}`);
}

function renderDflashTuningResults(status) {
  const result = status.result?.kind === "omlx-dflash2-tuning" ? status.result : null;
  const sweep = result?.tuningSweep || status.tuning || {};
  const candidates = Array.isArray(sweep.candidates) ? sweep.candidates : [];
  const selectedKey = sweep.selectedCandidateKey || "";
  const baseline = result?.modes?.ar || status.modes?.ar;
  const selectedSettings = sweep.selectedSettings || candidates.find(item => item.key === selectedKey)?.settings;
  const winner = result?.winner;
  const selectionMetric = sweep.selectionMetric || status.job?.tuningPlan?.selectionMetric || result?.selectionMetric || "end-to-end-tokens-per-second";
  const generationMetric = selectionMetric === "generation-tokens-per-second";
  const selectedSpeedField = generationMetric ? "medianDecodeTokensPerSecond" : "medianEndToEndTokensPerSecond";
  const selectedSpeedLabel = generationMetric ? "Generation TPS" : "End-to-end TPS";
  const baselineSpeed = Number(baseline?.[selectedSpeedField]);
  const selectedLabel = selectedSettings
    ? `block ${selectedSettings.blockSize} · ${selectedSettings.verifyMode} · ${selectedSettings.draftQuant}`
    : "Waiting…";
  const facts = `<div class="benchmark-tuning-facts"><span><small>AR ${formatting.esc(selectedSpeedLabel)}</small><b>${Number.isFinite(baselineSpeed) ? `${baselineSpeed.toFixed(1)} tok/s` : "Preparing…"}</b></span><span><small>Search progress</small><b>${candidates.length} / ${Number(sweep.maximumCandidates || status.job?.tuningPlan?.maximumDflashCandidates || 10)} candidates</b></span><span><small>Best tested DFlash</small><b>${formatting.esc(selectedLabel)}</b></span><span><small>Final route</small><b>${winner ? benchmarkWinnerLabel(winner) : "Not committed"}</b></span></div>`;
  const stageLabels = {block:"Block size",verifier:"Verifier",quantization:"Draft precision"};
  const cards = candidates.length
    ? `<div class="benchmark-tuning-candidates">${candidates.map(candidate => {
      const settings = candidate.settings || {};
      const selected = candidate.key === selectedKey || candidate.selected === true;
      const badge = selected ? (result ? "Selected" : "Leading") : (stageLabels[candidate.stage] || "Measured");
      const quality = candidate.qualityMatchesAR === true;
      return `<article class="benchmark-tuning-candidate ${selected ? "selected" : ""} ${quality ? "" : "mismatch"}"><header><strong>block ${formatting.esc(settings.blockSize)} · ${formatting.esc(settings.verifyMode)} · ${formatting.esc(settings.draftQuant)}</strong><em>${formatting.esc(badge)}</em></header><div><span>Median <b>${Number(candidate.medianSpeedupVsAR || 0).toFixed(2)}× AR</b></span><span>Worst <b>${Number(candidate.worstCaseSpeedupVsAR || 0).toFixed(2)}× AR</b></span><span>${formatting.esc(selectedSpeedLabel)} <b>${Number(candidate[selectedSpeedField] || 0).toFixed(1)} tok/s</b></span></div><p class="benchmark-quality ${quality ? "" : "bad"}">${quality ? "✓ Exact greedy output matches AR" : "! Greedy output mismatch"}</p></article>`;
    }).join("")}</div>`
    : `<p class="benchmark-tuning-empty">AR and native MTP references are measured first when available. Complete, cache-isolated DFlash candidates appear here as they finish.</p>`;
  const recommendation = result?.recommendation
    ? `<div class="benchmark-recommendation"><strong>${formatting.esc(benchmarkWinnerLabel(result.winner))} recommendation.</strong> ${formatting.esc(result.recommendation)}</div>`
    : "";
  setMarkup($("benchmarkResults"), `<section class="benchmark-tuning-result"><div class="benchmark-tuning-result-head"><div><span>Bounded oMLX DFlash search</span><strong>${result ? "Complete evidence contract" : "Provisional measurements"}</strong></div><em>${candidates.length} tested</em></div>${facts}${cards}</section>${recommendation}`);
}

function benchmarkRouteApplyBinding(status = {}) {
  const result = status.result;
  if (
    status.phase !== "completed" || !result || result.scope !== "local"
    || (result.kind && result.kind !== "mtplx-long-context-operator-tuning")
    || result.qualityPassed !== true
    || result.backend !== state.backend || result.modelId !== capabilities.selectedModel()?.id
    || result.client !== state.client || result.reasoning !== $("reasoningSelect").value
    || Number($("contextInput").value) !== result.contextMin
    || Number($("contextInput").value) !== result.contextMax
    || Number($("outputInput").value) !== result.outputMax
  ) return null;
  return evidence.copiedEvidenceBinding({
    scope:"route", suite:result.suite, preference:"throughput", recordId:result.id,
  });
}

async function applyBenchmarkRouteResult() {
  const binding = benchmarkRouteApplyBinding(benchmarkDisplayedStatus());
  if (!binding) {
    effects.showNotice("This result no longer matches the visible model and settings. Restore them before applying.", true);
    return false;
  }
  const applied = await evidence.applyOptimal("current", "throughput", false, binding);
  if (applied && $("benchmarkDialog").open) $("benchmarkDialog").close();
  return applied;
}

function benchmarkResultRecommendation(result) {
  if (result?.kind === "mtplx-long-context-operator-tuning" && result.winner === "mtp"
      && result.mtplxOperatorSweep?.selectedRoute === "default") {
    const candidate = result.mtplxOperatorSweep.candidates?.find(item => item.route === "dense-27b-long-context-2111");
    const gain = formatting.finiteMetric(candidate?.medianSpeedupVsDefault);
    if (candidate?.qualityMatchesAR === true && candidate?.resourceComparable === true
        && gain !== null && gain >= 1 && gain < 1.03) {
      return `Keep default MTP: long-context MTP was only ${((gain - 1) * 100).toFixed(1)}% faster on median generation TPS, below the 3% switching threshold. Both passed the correctness check; this is a practical tie.`;
    }
  }
  if (result?.kind === "mtplx-long-context-operator-tuning" && result.winner === "ar") {
    const sweep = result.mtplxOperatorSweep;
    const selected = (sweep?.candidates || []).find(candidate => candidate.route === sweep.selectedRoute);
    if (selected?.qualityMatchesAR === false) {
      return "Keep AR: the tested MTP output did not exactly match the greedy reference. Its measured speed is shown, but it is not eligible for automatic selection.";
    }
  }
  return result?.recommendation || "";
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
  if (status.result?.kind === "mtplx-long-context-operator-tuning") {
    const result = status.result, sweep = result.mtplxOperatorSweep;
    const recommendation = benchmarkResultRecommendation(result);
    const arSpeeds = (sweep.arMeasurement?.samples || [])
      .map(sample => formatting.finiteMetric(sample.decodeTokensPerSecond))
      .filter(speed => speed !== null && speed > 0);
    const rows = [
      {label:"AR", winner:result.winner === "ar", quality:true,
        speed:sweep.arMeasurement?.medianDecodeTokensPerSecond,
        worst:arSpeeds.length ? Math.min(...arSpeeds) : null},
      ...(sweep.candidates || []).map(candidate => ({
        label:candidate.route === "default" ? "Default MTP" : "Long-context MTP",
        winner:result.winner === "mtp" && candidate.route === sweep.selectedRoute,
        quality:candidate.qualityMatchesAR === true,
        speed:candidate.medianGenerationTokensPerSecond,
        worst:candidate.worstGenerationTokensPerSecond,
      })),
    ];
    const cards = rows.map(row => `<article class="benchmark-result ${row.winner ? "winner" : ""}"><div class="benchmark-result-head"><strong>${formatting.esc(row.label)}</strong><em>${row.winner ? "Winner" : "Measured"}</em></div><div class="benchmark-metrics"><span>Generation<b>${formatting.finiteMetric(row.speed) === null ? "Not reported" : `${Number(row.speed).toFixed(1)} tok/s`}</b></span><span>Slowest turn<b>${formatting.finiteMetric(row.worst) === null ? "Not reported" : `${Number(row.worst).toFixed(1)} tok/s`}</b></span></div><p class="benchmark-quality ${row.quality ? "" : "bad"}">${row.quality ? "✓ Correctness check passed" : "! Correctness check failed"}</p></article>`).join("");
    setMarkup($("benchmarkResults"), cards + `<div class="benchmark-recommendation"><span>${formatting.esc(recommendation)}</span>${benchmarkRouteApplyBinding(status) ? '<button type="button" class="text-button" data-apply-benchmark-route>Use measured settings</button>' : ""}</div>`);
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
      ? `<span>End-to-end<b>${Number(values.medianEndToEndTokensPerSecond || 0).toFixed(1)} tok/s</b></span><span>Decode<b>${Number(values.medianDecodeTokensPerSecond || 0).toFixed(1)} tok/s</b></span><span>Warm prefix<b>${Number(agentic.warmPrefixTTFTSeconds || 0).toFixed(2)} s TTFT</b></span><span>Tool ingestion<b>${Number(agentic.toolIngestTTFTSeconds || 0).toFixed(2)} s TTFT</b></span><span>Cache telemetry<b>${agentic.cacheTelemetryAvailable ? `${formatting.formatNumber(cacheTokens)} tokens` : "Not reported"}</b></span><span>Stages<b>${values.samples?.length || 0}</b></span>`
      : `<span>Output speed<b>${Number(values.medianEndToEndTokensPerSecond || 0).toFixed(1)} tok/s</b></span><span>Decode<b>${Number(values.medianDecodeTokensPerSecond || 0).toFixed(1)} tok/s</b></span><span>First token<b>${Number(values.medianTTFT || 0).toFixed(2)} s</b></span><span>Samples<b>${values.samples?.length || 0}</b></span>`;
    const telemetry = values.resourceTelemetry || {};
    const resourceMetrics = telemetry.memoryAvailable || telemetry.thermalAvailable
      ? `<span>${telemetry.memorySemanticsVersion === 2 ? "Memory use" : "Historical pressure"}<b>${telemetry.memoryAvailable ? `${formatting.formatBytes(telemetry.peakPressureDeltaBytes)} · ${Number(telemetry.minimumHeadroomPercent || 0).toFixed(0)}% left` : "Unavailable"}</b></span><span>Thermal state<b>${telemetry.thermalAvailable ? formatting.esc(`${telemetry.thermalStart || "nominal"} → ${telemetry.thermalWorst || "nominal"}`) : "Unavailable"}</b></span>`
      : "";
    const metrics = baseMetrics + resourceMetrics;
    const reuse = agentic
      ? `<p class="benchmark-reuse">Cold ÷ warm-prefix TTFT <b>${Number(agentic.prefixReuseFactor || 0).toFixed(2)}×</b> · tool-ingest ÷ follow-up <b>${Number(agentic.toolReuseFactor || 0).toFixed(2)}×</b></p>`
      : "";
    return `<article class="benchmark-result ${winner === mode ? "winner" : ""}"><div class="benchmark-result-head"><strong>${formatting.esc(values.label || benchmarkWinnerLabel(mode))}</strong><em>${winner === mode ? "Winner" : (speedup ? `${Number(speedup).toFixed(2)}× AR` : "Measured")}</em></div><div class="benchmark-metrics">${metrics}</div>${reuse}<p class="benchmark-quality ${qualityKnown && !values.qualityMatchesAR ? "bad" : ""}">${qualityText}</p></article>`;
  }).join("");
  const applyBinding = benchmarkRouteApplyBinding(status);
  const recommendation = result?.recommendation ? `<div class="benchmark-recommendation"><span><strong>${formatting.esc(benchmarkWinnerLabel(result.winner))} recommendation.</strong> ${formatting.esc(result.recommendation)}</span>${applyBinding ? '<button type="button" class="text-button" data-apply-benchmark-route>Use measured settings</button>' : ""}</div>` : "";
  setMarkup($("benchmarkResults"), cards + recommendation);
}

function renderBenchmarkLiveTps(status = {}) {
  const active = ["queued", "cooldown", "starting", "running", "stopping"].includes(status.phase);
  const speed = formatting.finiteMetric(status.liveMetric?.decodeTokensPerSecond);
  const field = $("benchmarkLiveTps");
  field.classList.toggle("hidden", !active);
  field.textContent = !active ? ""
    : speed === null ? "Measuring…" : `Last completed turn · ${speed.toFixed(1)} tok/s`;
  field.title = active
    ? [status.liveMetric?.backendLabel, status.liveMetric?.modeLabel, status.liveMetric?.stageLabel]
      .filter(Boolean).join(" · ") : "";
}

function renderBenchmarkStatus(status = {}) {
  state.benchmarkStatus = status;
  state.benchmarkPhase = status.phase || "idle";
  const displayed = benchmarkDisplayedStatus(status);
  const progress = Math.max(0, Math.min(1, Number(displayed.progress || 0)));
  const percent = Math.round(progress * 100);
  $("benchmarkPhase").textContent = ({idle:"Ready",queued:"Queued",cooldown:"Stabilising Mac",starting:"Loading route",running:"Measuring",stopping:"Stopping",completed:"Completed",cancelled:"Cancelled",failed:"Failed"})[state.benchmarkPhase] || state.benchmarkPhase;
  if (displayed.savedReview) $("benchmarkPhase").textContent = "Saved result";
  $("benchmarkPercent").textContent = `${percent}%`;
  $("benchmarkProgressBar").style.width = `${percent}%`;
  const track = $("benchmarkProgressBar").parentElement;
  track.setAttribute("aria-valuenow", String(percent));
  $("benchmarkStatus").textContent = (displayed.phase === "completed" && benchmarkResultRecommendation(displayed.result))
    || status.message || "Nothing will start until you press Run benchmark.";
  if(benchmarkError) $("benchmarkStatus").textContent=benchmarkError;
  renderBenchmarkLiveTps(status);
  const order = status.result?.executionOrder || status.job?.executionOrder || [];
  const cooldown = status.result?.resourceCooldown || status.job?.resourceCooldown;
  const mtpTuning = status.result?.kind === "lmstudio-mtp-tuning" || status.job?.kind === "lmstudio-mtp-tuning";
  const dflashTuning = status.result?.kind === "omlx-dflash2-tuning" || status.job?.kind === "omlx-dflash2-tuning";
  const ssdStreaming = status.job?.ssdStreaming === true;
  $("benchmarkFairness").textContent = ssdStreaming
    ? `SSD-streaming run order: ${order.map(formatting.backendName).join(" → ")}. Every runtime gets a fresh process and the same native-routing agent workload; first-turn and warm stages are kept separate without forcing a privileged macOS cache purge.`
    : mtpTuning
    ? `One AR reference and up to ${Number(status.job?.tuningPlan?.maximumMtpCandidates || status.result?.tuningSweep?.maximumCandidates || 10)} MTP candidates. Every candidate receives a fresh load, exact greedy parity, and the same bounded Mac-condition gate.`
    : dflashTuning
      ? `${(status.job?.tuningPlan?.baselineModes || status.result?.tuningSweep?.baselineModes || ["ar"]).map(benchmarkWinnerLabel).join(" + ")} reference routes and up to ${Number(status.job?.tuningPlan?.maximumDflashCandidates || status.result?.tuningSweep?.maximumCandidates || 10)} DFlash candidates. Every candidate receives a fresh load, exact greedy parity, and the same bounded Mac-condition gate.`
    : order.length
      ? `Rotated run order: ${order.map(formatting.backendName).join(" → ")}. Before every route, Launcher waits up to ${Number(cooldown?.maxWaitSeconds || 60).toFixed(0)} seconds for comparable Mac conditions.`
      : "Every measured route receives a fresh model load.";
  renderBenchmarkResults(displayed);
  renderBenchmarkHistory();
  renderBenchmarkSetup();
  if ($("calibrationDialog")?.open) {
    renderCalibrationBenchmark(status);
    if(calibrationError && !calibrationBenchmarkActive()) $("calibrationStatus").textContent=calibrationError;
  }
  settingsPort.refreshLaunchability();
  if (status.phase === "completed" && status.result?.id && state.benchmarkResultId !== status.result.id) {
    state.benchmarkResultId = status.result.id;
    state.benchmarkHistoryKey = "";
    effects.loadModels(false).finally(() => {
      loadBenchmarkHistory(true);
      receiptPort.loadPerformanceReceipt(true);
    });
  }
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
  benchmarkError="";
  try {
    const request = settingsPort.gather("custom");
    request.suite = $("benchmarkSuiteSelect").value;
    request.enginePreference = $("benchmarkPreferenceSelect").value;
    if (["engines", "mtp-tune", "dflash-tune"].includes(scope)) request.scope = scope;
    const data = await api("/api/benchmark/start", {method:"POST", body:JSON.stringify(request)});
    statusEpoch+=1;
    state.benchmarkPhase = "queued";
    const shootout = data.benchmark?.kind === "engine-shootout";
    const mtpTuning = data.benchmark?.kind === "lmstudio-mtp-tuning";
    const dflashTuning = data.benchmark?.kind === "omlx-dflash2-tuning";
    const engines = Object.fromEntries((data.benchmark?.engines || [])
      .filter(engine => capabilities.uiEngineVisible(engine.backend))
      .map(engine => [engine.backend, {...engine, phase:"queued", modes:{}, record:null}]));
    renderBenchmarkStatus({
      phase:"queued", progress:0,
      message:shootout
        ? `Engine Shootout accepted. Preparing ${formatting.backendName(data.benchmark.executionOrder?.[0])} first in this rotated run…`
        : mtpTuning
          ? "MTP tuning accepted. Preparing the AR reference route…"
          : dflashTuning
            ? "DFlash 2 tuning accepted. Preparing the AR reference route…"
          : "Benchmark accepted. Preparing the first route…",
      job:data.benchmark, modes:{}, engines, tuning:(mtpTuning || dflashTuning) ? {candidates:[]} : undefined,
    });
  } catch (error) { benchmarkError=String(error.message || "The benchmark could not be started.").slice(0,2048); $("benchmarkStatus").textContent = benchmarkError; effects.showNotice(benchmarkError, true); }
}

async function stopBenchmark() {
  benchmarkError="";
  try {
    await api("/api/benchmark/stop", {method:"POST", body:"{}"});
    statusEpoch+=1;
    await Promise.all([effects.pollStatus(), pollBenchmarkStatus()]);
  } catch (error) { benchmarkError=String(error.message || "The benchmark could not be stopped.").slice(0,2048); $("benchmarkStatus").textContent = benchmarkError; }
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
    || operations.acquisitionIsActive()
    || operations.routeCheckIsActive()
    || operations.aneWorkIsActive()
    || calibrationBenchmarkActive()
    || state.calibrationLoading
    || state.calibrationStarting
    || state.calibrationApplying
    || operations.profileBusy();
}

function calibrationMeasurementAdmission(plan = state.calibrationPlan || {}) {
  // Route qualification has its own stricter, freshly sampled admission
  // contract.  Ordinary engine comparisons begin with the visible route and
  // therefore use the launcher's signature-bound session admission.
  return plan.routeQualification === true
    ? operations.sessionAdmissionDecision(plan.memoryAdmission)
    : operations.currentSessionAdmission();
}

function calibrationQualificationProfile(plan = state.calibrationPlan || {}) {
  let backend = capabilities.controllerRouteQualificationBackend(plan);
  if (!backend && plan?.qualificationPreparation?.kind === "qwen-ple-safe-qualification-v1") {
    backend = "omlx";
  }
  const llama = backend === "llamacpp";
  const uzu = backend === "uzu";
  return {
    backend,
    llama,
    uzu,
    routeLabel:llama ? "llama.cpp SSD PLE" : uzu ? "Uzu DFlash + Weaver" : backend === "omlx" ? "oMLX Qwen PLE" : "the exact route",
    subtitle:llama
      ? "Qualify the exact pinned llama.cpp SSD PLE route at fixed 8K under the exact 44 GiB ceiling."
      : uzu
        ? "Qualify Uzu's fixed DFlash + Weaver route for this exact context on built-in Chat."
        : backend === "omlx"
          ? "Measure and qualify the exact oMLX Qwen PLE route without inventing a second engine."
          : "Measure and qualify this exact route.",
    reasoningLabel:llama ? "Runtime-controlled" : uzu ? "Model default · on" : null,
    startMessage:llama
      ? "Pinned llama.cpp SSD PLE qualification accepted. Loading the exact fixed-8K route…"
      : uzu
        ? "Uzu qualification accepted. Loading the fixed DFlash + Weaver route…"
        : backend === "omlx"
          ? "Route qualification accepted. Preparing the exact oMLX AR + PLE mmap route…"
          : "Route qualification accepted. Preparing the exact route…",
  };
}

function llamaQualificationContractExact(plan = state.calibrationPlan || {}) {
  if (capabilities.controllerRouteQualificationBackend(plan) !== "llamacpp") return false;
  const model = capabilities.selectedModel();
  const capability = model?.backends?.llamacpp || {};
  const contract = plan.qualificationContract;
  const route = plan.routeSpec;
  const reasoning = plan.reasoningContract || {};
  const receiptFingerprint = String(capability.receiptFingerprint || "");
  const runtimeVersion = String(capability.runtimeVersion || "");
  const scenariosExact = Array.isArray(contract?.scenarioContract)
    && contract.scenarioContract.length === policy.LLAMACPP_PLE_QUALIFICATION_SCENARIOS.length
    && contract.scenarioContract.every(
      (scenario, index) => scenario === policy.LLAMACPP_PLE_QUALIFICATION_SCENARIOS[index],
    );
  return capabilities.llamaCppPleQualified(model)
    && plan.routeQualification === true
    && String(plan.model?.id || "") === String(model?.id || "")
    && String(plan.request?.modelId || "") === String(model?.id || "")
    && plan.request?.backend === "llamacpp"
    && plan.request?.context === policy.LLAMACPP_PLE_QUALIFICATION_CONTEXT
    && plan.request?.reasoning === "auto"
    && capability.memoryCeilingBytes === policy.LLAMACPP_PLE_QUALIFICATION_MEMORY_LIMIT_BYTES
    && /^[0-9a-f]{64}$/.test(receiptFingerprint)
    && runtimeVersion.length > 0
    && contract?.id === policy.LLAMACPP_PLE_QUALIFICATION_CONTRACT_ID
    && contract.version === policy.LLAMACPP_PLE_QUALIFICATION_CONTRACT_VERSION
    && contract.scope === "route"
    && contract.clientAgnostic === true
    && contract.backend === "llamacpp"
    && contract.exactContext === policy.LLAMACPP_PLE_QUALIFICATION_CONTEXT
    && contract.configuredOutputLimit === plan.request?.output
    && contract.measuredRequestMaxTokens === policy.LLAMACPP_PLE_QUALIFICATION_SAMPLE_MAX_TOKENS
    && scenariosExact
    && contract.sampleMaxTokens === policy.LLAMACPP_PLE_QUALIFICATION_SAMPLE_MAX_TOKENS
    && contract.answerReserveTokens === policy.LLAMACPP_PLE_QUALIFICATION_ANSWER_RESERVE_TOKENS
    && contract.thinkingBudgetTokens === policy.LLAMACPP_PLE_QUALIFICATION_THINKING_TOKENS
    && contract.minimumDecodeTokensPerSecond === policy.LLAMACPP_PLE_QUALIFICATION_MINIMUM_TPS
    && contract.minimumCompletionTokens === policy.LLAMACPP_PLE_QUALIFICATION_MINIMUM_COMPLETION_TOKENS
    && contract.reasoningBoundaryContractId === policy.LLAMACPP_PLE_QUALIFICATION_REASONING_BOUNDARY_ID
    && contract.reasoningBudgetMessageSha256 === policy.LLAMACPP_PLE_QUALIFICATION_REASONING_MESSAGE_SHA256
    && contract.reasoningPolicy === "runtime-fixed-on"
    && contract.toolProbeRequired === true
    && contract.memoryProofRequired === true
    && contract.memoryCeilingBytes === policy.LLAMACPP_PLE_QUALIFICATION_MEMORY_LIMIT_BYTES
    && contract.receiptFingerprint === receiptFingerprint
    && contract.runtimeVersion === runtimeVersion
    && route?.id === policy.LLAMACPP_PLE_QUALIFICATION_CONTRACT_ID
    && route.version === policy.LLAMACPP_PLE_QUALIFICATION_CONTRACT_VERSION
    && route.scope === "route"
    && route.clientAgnostic === true
    && route.backend === "llamacpp"
    && route.suite === policy.LLAMACPP_PLE_QUALIFICATION_SUITE
    && route.context === policy.LLAMACPP_PLE_QUALIFICATION_CONTEXT
    && route.reasoningPolicy === "runtime-fixed-on"
    && route.toolProbeRequired === true
    && route.memoryProofRequired === true
    && route.memoryCeilingBytes === policy.LLAMACPP_PLE_QUALIFICATION_MEMORY_LIMIT_BYTES
    && reasoning.runtimeControlled === true
    && reasoning.reasoningEnabled === true
    && reasoning.policy === "runtime-fixed-reasoning-on"
    && reasoning.measured === "auto";
}

function uzuQualificationContractExact(plan = state.calibrationPlan || {}) {
  if (capabilities.controllerRouteQualificationBackend(plan) !== "uzu") return false;
  const model = capabilities.selectedModel();
  const capability = model?.backends?.uzu || {};
  const contract = plan.qualificationContract;
  const route = plan.routeSpec;
  const reasoning = plan.reasoningContract || {};
  const context = Number(plan.request?.context);
  const expectedSuite = capabilities.uzuQualificationSuite(context);
  const expectedId = capabilities.uzuQualificationContractId(context);
  const receiptFingerprint = String(capability.benchmarkModelFingerprint || "");
  const runtimeVersion = String(capability.runtimeVersion || "");
  const runtimeSha = String(capability.runtimeIdentity?.binary?.sha256 || "");
  const runtimeSize = Number(capability.runtimeIdentity?.binary?.size);
  const runtimeCommit = String(capability.runtimeIdentity?.upstreamCommit || "");
  const runtimePatchSha = String(capability.runtimeIdentity?.sourcePatchSha256 || "");
  const systemContract = capability.qualificationSystemContract || {};
  const expectedOsReserveBytes = Number(systemContract.osReserveBytes);
  const expectedSandboxProfileSha256 = String(systemContract.sandboxProfileSha256 || "");
  const expectedRawListenerProtected = systemContract.rawListenerProtected === true;
  const osReserveBytes = Number(contract?.osReserveBytes);
  const contextWindows = Array.isArray(capability.contextWindows)
    ? capability.contextWindows.map(Number) : [];
  const scenariosExact = Array.isArray(contract?.scenarioContract)
    && contract.scenarioContract.length === policy.UZU_QUALIFICATION_SCENARIOS.length
    && contract.scenarioContract.every(
      (scenario, index) => scenario === policy.UZU_QUALIFICATION_SCENARIOS[index],
    );
  return model?.ready === true && model?.uzuNative === true
    && capability.runnable === true
    && capability.runtimeManagedAcceleration === "DFlash + Weaver"
    && contextWindows.length === policy.UZU_QUALIFICATION_CONTEXTS.length
    && policy.UZU_QUALIFICATION_CONTEXTS.every((value, index) => contextWindows[index] === value)
    && capability.contextMaximum === policy.UZU_QUALIFICATION_CONTEXTS.at(-1)
    && capability.runtimeIdentity?.binaryIdentityPinned === true
    && capability.runtimeIdentity?.nativeBoundaryContractId === policy.UZU_NATIVE_BOUNDARY_CONTRACT_ID
    && capability.runtimeIdentity?.nativeBearerAuthentication === true
    && capability.runtimeIdentity?.oneUseApiKeyFile === true
    && capability.runtimeIdentity?.nativeContextLimit === true
    && capability.runtimeIdentity?.nativeOutputLimit === true
    && systemContract.nativeBoundaryContractId === policy.UZU_NATIVE_BOUNDARY_CONTRACT_ID
    && systemContract.nativeBearerAuthentication === true
    && systemContract.oneUseApiKeyFile === true
    && systemContract.nativeContextLimit === true
    && systemContract.nativeOutputLimit === true
    && plan.routeQualification === true
    && String(plan.model?.id || "") === String(model?.id || "")
    && String(plan.request?.modelId || "") === String(model?.id || "")
    && plan.request?.backend === "uzu"
    && plan.request?.client === "chat"
    && plan.request?.reasoning === "auto"
    && plan.request?.options?.acceleration === "off"
    && plan.request?.options?.depth === 1
    && plan.request?.options?.kv === "off"
    && Number.isInteger(plan.request?.output)
    && plan.request.output >= policy.UZU_QUALIFICATION_SAMPLE_MIN_TOKENS
    && Boolean(expectedSuite) && Boolean(expectedId)
    && plan.suite?.id === expectedSuite
    && /^[0-9a-f]{64}$/.test(receiptFingerprint)
    && runtimeVersion.length > 0
    && runtimeSha === policy.UZU_RUNTIME_RELEASE_BINARY_SHA256
    && contract?.id === expectedId
    && contract.version === policy.UZU_QUALIFICATION_CONTRACT_VERSION
    && contract.scope === "route"
    && contract.clientAgnostic === false
    && contract.client === "chat"
    && contract.backend === "uzu"
    && contract.exactContext === context
    && contract.configuredOutputLimit === plan.request?.output
    && contract.measuredRequestMaxTokens === Math.min(policy.UZU_QUALIFICATION_SAMPLE_MAX_TOKENS, plan.request.output)
    && scenariosExact
    && contract.sampleMaxTokens === Math.min(policy.UZU_QUALIFICATION_SAMPLE_MAX_TOKENS, plan.request.output)
    && contract.outputBudgetPolicy?.id === "uzu-remaining-context-output-v1"
    && contract.outputBudgetPolicy.maximumTokens === contract.sampleMaxTokens
    && contract.outputBudgetPolicy.minimumTokens === policy.UZU_QUALIFICATION_SAMPLE_MIN_TOKENS
    && contract.outputBudgetPolicy.promptReserveTokens === 512
    && contract.outputBudgetPolicy.followupReserveTokens === policy.UZU_QUALIFICATION_SAMPLE_MIN_TOKENS + 128
    && contract.answerReserveTokens === policy.UZU_QUALIFICATION_ANSWER_RESERVE_TOKENS
    && contract.thinkingBudgetTokens == null
    && contract.minimumDecodeTokensPerSecond === policy.UZU_QUALIFICATION_MINIMUM_TPS
    && contract.minimumCompletionTokens === policy.UZU_QUALIFICATION_MINIMUM_COMPLETION_TOKENS
    && contract.reasoningPolicy === "runtime-default-on"
    && contract.toolProbeRequired === false
    && contract.memoryProofRequired === true
    && Number.isSafeInteger(contract.memoryCeilingBytes)
    && [36 * 1024 ** 3, policy.UZU_QUALIFICATION_MEMORY_LIMIT_BYTES].includes(contract.memoryCeilingBytes)
    && contract.memoryCeilingBytes <= policy.UZU_QUALIFICATION_MEMORY_LIMIT_BYTES
    && contract.fixedAcceleration === "DFlash + Weaver"
    && contract.kvStateDataType === "BF16"
    && contract.prefixCache === true
    && capabilities.uzuQualificationPromptExercisePolicyExact(
      contract.promptExercisePolicy, context,
    )
    && contract.osReservePolicy === "max-4gib-or-10-percent-total-v1"
    && contract.osReserveMinimumBytes === policy.UZU_QUALIFICATION_OS_RESERVE_MINIMUM_BYTES
    && Number.isSafeInteger(expectedOsReserveBytes)
    && expectedOsReserveBytes >= policy.UZU_QUALIFICATION_OS_RESERVE_MINIMUM_BYTES
    && osReserveBytes === expectedOsReserveBytes
    && contract.receiptFingerprint === receiptFingerprint
    && contract.modelFingerprint === receiptFingerprint
    && contract.modelRegistryId === capability.modelRegistryId
    && contract.modelCommit === capability.modelCommit
    && contract.modelToolchainVersion === capability.modelToolchainVersion
    && contract.runtimeBinarySha256 === runtimeSha
    && runtimeSize === policy.UZU_RUNTIME_RELEASE_BINARY_SIZE
    && contract.runtimeBinarySize === runtimeSize
    && runtimeCommit === policy.UZU_RUNTIME_UPSTREAM_COMMIT
    && contract.runtimeUpstreamCommit === runtimeCommit
    && runtimePatchSha === policy.UZU_RUNTIME_SOURCE_PATCH_SHA256
    && contract.runtimeSourcePatchSha256 === runtimePatchSha
    && /^[0-9a-f]{64}$/.test(expectedSandboxProfileSha256)
    && contract.sandboxProfileSha256 === expectedSandboxProfileSha256
    && expectedRawListenerProtected
    && contract.rawListenerProtected === true
    && contract.nativeBoundaryContractId === policy.UZU_NATIVE_BOUNDARY_CONTRACT_ID
    && contract.nativeBearerAuthentication === true
    && contract.oneUseApiKeyFile === true
    && contract.nativeContextLimitTokens === context
    && contract.nativeMaxOutputTokens === plan.request?.output
    && contract.runtimeVersion === runtimeVersion
    && capability.runtimeIdentity?.ready === true
    && capability.runtimeIdentity?.networkSandbox === true
    && capability.runtimeIdentity?.memorySafetyBlocked === false
    && capability.runtimeIdentity?.listenerIsolationBlocked === false
    && (
      capability.runtimeIdentity?.rawListenerAuthenticated === true
      || capability.runtimeIdentity?.rawListenerIsolated === true
    )
    && route?.id === expectedId
    && route.version === policy.UZU_QUALIFICATION_CONTRACT_VERSION
    && route.scope === "route"
    && route.clientAgnostic === false
    && route.client === "chat"
    && route.backend === "uzu"
    && route.mode === "ar"
    && route.modeLabel === "Fixed DFlash + Weaver"
    && route.suite === expectedSuite
    && route.context === context
    && route.reasoningPolicy === "runtime-default-on"
    && route.toolProbeRequired === false
    && route.memoryProofRequired === true
    && route.memoryCeilingBytes === policy.UZU_QUALIFICATION_MEMORY_LIMIT_BYTES
    && reasoning.runtimeControlled === true
    && reasoning.reasoningEnabled === true
    && reasoning.policy === "runtime-default-reasoning-on"
    && reasoning.requested === "auto"
    && reasoning.measured === "auto";
}

function routeQualificationContractExact(plan = state.calibrationPlan || {}) {
  const backend = capabilities.controllerRouteQualificationBackend(plan);
  if (backend === "llamacpp") return llamaQualificationContractExact(plan);
  if (backend === "uzu") return uzuQualificationContractExact(plan);
  return backend === "omlx" || plan.routeQualification !== true;
}

function firstQualificationMetric(...values) {
  for (const value of values) {
    const metric = formatting.finiteMetric(value);
    if (metric !== null && metric >= 0) return metric;
  }
  return null;
}

function firstQualificationCheck(...values) {
  const explicit = values.find(value => typeof value === "boolean");
  return typeof explicit === "boolean" ? explicit : null;
}

function routeQualificationResultMetrics(route = {}, result = {}) {
  const routeQualification = route.qualification || {};
  const resultQualification = result.qualification || {};
  const metrics = route.metrics || routeQualification.metrics
    || result.qualificationMetrics || resultQualification.metrics || {};
  const sampleCount = firstQualificationMetric(
    route.sampleCount, metrics.sampleCount, result.sampleCount,
  );
  const reasoningTurns = firstQualificationMetric(
    route.reasoningTurns, metrics.reasoningTurns, result.reasoningTurns,
  );
  const answerTurns = firstQualificationMetric(
    route.answerTurns, metrics.answerTurns, result.answerTurns,
  );
  const countVerified = sampleCount !== null && sampleCount > 0
    && reasoningTurns === sampleCount && answerTurns === sampleCount;
  const reasoningFinal = firstQualificationCheck(
    route.reasoningFinalVerified,
    route.checks?.reasoningFinalAnswer,
    routeQualification.reasoningFinalVerified,
    result.reasoningFinalVerified,
    result.checks?.reasoningFinalAnswer,
    resultQualification.reasoningFinalVerified,
    route.reasoningObserved === true && route.answerObserved === true ? true : undefined,
    routeQualification.reasoningObserved === true && routeQualification.answerObserved === true ? true : undefined,
    resultQualification.reasoningObserved === true && resultQualification.answerObserved === true ? true : undefined,
    countVerified ? true : undefined,
  );
  return {
    tps:firstQualificationMetric(
      route.decodeTokensPerSecond, route.medianDecodeTokensPerSecond,
      metrics.medianDecodeTokensPerSecond, result.decodeTokensPerSecond,
    ),
    minimumTps:firstQualificationMetric(
      route.minimumDecodeTokensPerSecond,
      metrics.minimumDecodeTokensPerSecond,
      result.minimumDecodeTokensPerSecond,
      resultQualification.minimumDecodeTokensPerSecond,
    ),
    ttft:firstQualificationMetric(
      route.firstTokenSeconds, route.medianTTFTSeconds,
      metrics.medianTTFTSeconds, result.firstTokenSeconds,
    ),
    peakMemory:firstQualificationMetric(
      route.peakMemoryBytes,
      route.peakProcessPhysicalFootprintBytes,
      route.resourceTelemetry?.peakProcessPhysicalFootprintBytes,
      metrics.peakMemoryBytes,
      result.peakMemoryBytes,
      result.peakProcessPhysicalFootprintBytes,
      result.resourceTelemetry?.peakProcessPhysicalFootprintBytes,
    ),
    reasoningFinal,
    reasoningBoundary:firstQualificationCheck(
      route.reasoningBoundaryVerified,
      route.checks?.reasoningBoundary,
      routeQualification.reasoningBoundaryVerified,
      result.reasoningBoundaryVerified,
      result.checks?.reasoningBoundary,
      resultQualification.reasoningBoundaryVerified,
    ),
    jinjaTool:firstQualificationCheck(
      route.jinjaToolVerified,
      route.toolContractVerified,
      route.checks?.jinjaTool,
      routeQualification.jinjaToolVerified,
      result.jinjaToolVerified,
      result.toolContractVerified,
      result.checks?.jinjaTool,
      resultQualification.jinjaToolVerified,
    ),
    cleanUnload:firstQualificationCheck(
      route.cleanUnloadVerified,
      route.unloadVerified,
      route.checks?.cleanUnload,
      routeQualification.cleanUnloadVerified,
      result.cleanUnloadVerified,
      result.unloadVerified,
      result.checks?.cleanUnload,
      resultQualification.cleanUnloadVerified,
    ),
    correctness:firstQualificationCheck(
      route.correctnessVerified,
      route.checks?.correctness,
      routeQualification.correctnessVerified,
      result.correctnessVerified,
      result.checks?.correctness,
      resultQualification.correctnessVerified,
    ),
  };
}

function routeQualificationFactsMarkup(route = {}, result = {}, backend = "") {
  const metrics = routeQualificationResultMetrics(route, result);
  const check = value => value === true ? "Passed" : value === false ? "Failed" : "Not reported";
  const tps = metrics.tps === null ? "Not reported" : `${metrics.tps.toFixed(1)} tok/s`;
  const minimumTps = metrics.minimumTps === null
    ? "Not reported"
    : `${metrics.minimumTps.toFixed(1)} tok/s`;
  const ttft = metrics.ttft === null ? "Not reported" : `${metrics.ttft.toFixed(2)}s`;
  if (backend === "uzu") {
    const peak = metrics.peakMemory === null
      ? "Not reported"
      : `${(metrics.peakMemory / (1024 ** 3)).toFixed(1)} GiB / ${policy.UZU_QUALIFICATION_MEMORY_LIMIT_BYTES / (1024 ** 3)} GiB`;
    return `<small class="calibration-result-tps">Generation TPS · ${formatting.esc(tps)}</small><small class="calibration-result-settings">Slowest turn · ${formatting.esc(minimumTps)} · target ≥${policy.UZU_QUALIFICATION_MINIMUM_TPS}</small><small class="calibration-result-settings">BF16 KV · runtime fixed · Peak memory · ${formatting.esc(peak)} · TTFT · ${formatting.esc(ttft)}</small><small class="calibration-result-settings">Reasoning + final answer · ${formatting.esc(check(metrics.reasoningFinal))} · Correctness · ${formatting.esc(check(metrics.correctness))} · Clean unload · ${formatting.esc(check(metrics.cleanUnload))}</small>`;
  }
  if (backend !== "llamacpp") {
    return `<small class="calibration-result-tps">Generation TPS · ${formatting.esc(tps)}</small><small class="calibration-result-settings">TTFT · ${formatting.esc(ttft)} · Reasoning + final answer · ${formatting.esc(check(metrics.reasoningFinal))}</small>`;
  }
  const peak = metrics.peakMemory === null
    ? "Not reported"
    : `${(metrics.peakMemory / (1024 ** 3)).toFixed(1)} GiB / ${policy.LLAMACPP_PLE_QUALIFICATION_MEMORY_LIMIT_BYTES / (1024 ** 3)} GiB`;
  return `<small class="calibration-result-tps">Generation TPS · ${formatting.esc(tps)}</small><small class="calibration-result-settings">Slowest turn · ${formatting.esc(minimumTps)} · target ≥${policy.LLAMACPP_PLE_QUALIFICATION_MINIMUM_TPS}</small><small class="calibration-result-settings">TTFT · ${formatting.esc(ttft)} · Peak memory · ${formatting.esc(peak)}</small><small class="calibration-result-settings">Reasoning + final answer · ${formatting.esc(check(metrics.reasoningFinal))} · Clean forced handoff · ${formatting.esc(check(metrics.reasoningBoundary))}</small><small class="calibration-result-settings">Correctness check · ${formatting.esc(check(metrics.correctness))} · Jinja tool check · ${formatting.esc(check(metrics.jinjaTool))} · Clean unload · ${formatting.esc(check(metrics.cleanUnload))}</small>`;
}

function updateCalibrationHelp() {
  const suite = $("calibrationSuiteSelect").value;
  const preference = $("calibrationPreferenceSelect").value;
  const cooling = $("calibrationCoolingSelect").value;
  const routeQualification = state.calibrationPlan?.routeQualification === true;
  const qualification = calibrationQualificationProfile();
  const coolingLocked = state.calibrationPlan?.calibrationCoolingLocked === true;
  $("calibrationSuiteHelp").textContent = routeQualification
    ? qualification.llama
      ? "Uses four bounded generated turns at fixed 8K to verify reasoning, final answers, Jinja tool calling, and clean unload."
      : "Uses four bounded generated turns to verify cold load, prefix reuse, tool ingestion, reasoning, and final answers."
    : ({
    agentic:"Measures cold prefill, prefix reuse, tool ingestion, and a warm follow-up.",
    standard:"Measures repeated 2K and 8K prompt routes for general chat throughput.",
    quick:"A smaller first signal using 512 and 2K prompts; rerun a representative suite before a major decision.",
    thorough:"Measures 4K, 16K, and 32K prompts with repeated passes and many model reloads.",
  })[suite] || "Uses generated local prompts.";
  $("calibrationPreferenceHelp").textContent = routeQualification
    ? "Chooses which recorded route metric is shown most prominently; it does not invent an engine winner."
    : ({
    throughput:"Ranks each engine's correctness-verified safe route by median generation TPS; leads below 3% remain ties.",
    fastest:"Uses complete-workload time and keeps leads inside 3% as ties.",
    responsive:"Uses measured time to first output and keeps leads inside 3% as ties.",
    memory:"Uses system-wide unified-memory headroom and requires at least a 512 MB advantage.",
    thermal:"Requires comparable starting conditions, then ranks worst public macOS thermal state and speed.",
  })[preference] || "Uses matching local evidence only.";
  $("calibrationCoolingHelp").textContent = coolingLocked
    ? `${state.calibrationPlan.calibrationCoolingReason || "This runtime exposes no fan control; macOS controls cooling."} The launcher's independent memory guard remains active.`
    : cooling === "max"
      ? "Maximum fans is an explicit loud-mode choice for MTPLX routes in this measurement."
      : "The launcher will not force maximum fans. macOS may still increase cooling under sustained load.";
}

function calibrationPlanRequest() {
  const request = settingsPort.gather("custom");
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
  const qualificationBackend = capabilities.selectedRouteQualificationBackend();
  const missing = (next.missingEngines || [])
    .filter(item => capabilities.uiEngineVisible(item.backend || item.id))
    .map(item => item.label).filter(Boolean);
  $("calibrationOriginTitle").textContent = qualificationBackend
    ? "This route needs a local qualification"
    : entry.source === "optimizer-result"
      ? `${preferenceLabel} needs a local measurement`
      : `Measure before choosing ${preferenceLabel.toLowerCase()}`;
  $("calibrationOriginDetail").textContent = next.reason || (qualificationBackend === "llamacpp"
    ? "Qualify this one pinned fixed-8K SSD PLE route; no engine winner is chosen."
    : qualificationBackend
      ? "Qualify this exact route; no engine winner is chosen."
      : missing.length
        ? `Matching evidence is missing for ${missing.join(", ")}.`
        : "Review the exact engines, workload, reload count, and request count before anything runs.");
}

function completedCalibrationDecision(status = state.benchmarkStatus || {}) {
  if (!calibrationOwnsBenchmark(status) || status.phase !== "completed") return null;
  const result = status.result || {};
  if (result.persistence?.saved !== true) return null;
  if (result.matrixWorkloadComparable === false) return null;
  const preference = $("calibrationPreferenceSelect").value;
  const decision = result.profiles?.[preference] || result.decision || {};
  if (!["cross-engine-local-benchmark", "cross-engine-leading-band", "cross-engine-noise-floor", "local-route-qualification"].includes(decision.evidenceTier)) return null;
  const evidenceBinding = completedCalibrationEvidenceBinding(result, decision);
  const expectedScope = decision.evidenceTier === "local-route-qualification"
    || result.kind === "route-qualification" ? "route" : "engine";
  if (
    !evidenceBinding
    || evidenceBinding.scope !== expectedScope
    || evidenceBinding.preference !== preference
    || evidenceBinding.suite !== result.suite
    || (
      expectedScope === "engine"
      && String(evidenceBinding.shootoutId || "") !== String(result.id || "")
    )
  ) return null;
  return {result, decision, evidenceBinding};
}

function completedCalibrationEvidenceBinding(result = {}, decision = {}) {
  return [
    decision.evidenceBinding,
    decision.engineEvidenceBinding,
    result.evidenceBinding,
    result.evidence?.evidenceBinding,
    result.receipt?.evidenceBinding,
    result.persistence?.evidenceBinding,
  ].map(evidence.copiedEvidenceBinding).find(Boolean) || null;
}

function promoteCompletedCalibrationResult(status = state.benchmarkStatus || {}) {
  const completed = completedCalibrationDecision(status);
  if (!completed || !state.calibrationPlan) return false;
  const {result, decision, evidenceBinding} = completed;
  const backend = String(decision.backend || "");
  const backendLabel = decision.label || formatting.backendName(backend);
  state.calibrationPlan = {
    ...state.calibrationPlan,
    action:"apply-existing",
    evidence:{
      ...(state.calibrationPlan.evidence || {}),
      trusted:Boolean(decision.trustedWinner),
      decisionReady:true,
      tier:decision.evidenceTier,
      label:CalibrationDecision.summary({...decision, backendLabel}),
      backend,
      backendLabel,
      engineChanged:Boolean(decision.engineChanged),
      leadingBackends:decision.leadingBackends || [],
      currentInLeadingBand:decision.currentInLeadingBand === true,
      detail:decision.rationale?.[0] || decision.recommendation || result.recommendation || "The measured result is ready.",
      exactOutputMatch:decision.exactOutputMatch === true || result.exactOutputMatch === true,
      outputWarning:decision.outputWarning || result.outputWarning || "",
      comparedEngines:decision.comparedEngines || (result.qualified ? [] : result.engines) || [],
      qualified:Boolean(decision.qualified || result.qualified),
      qualifiedRoutes:decision.qualifiedRoutes || result.qualifiedRoutes || [],
      ...(evidenceBinding ? {evidenceBinding} : {}),
    },
  };
  return true;
}

function calibrationParityRejectionNote(engine = {}) {
  const rejectedFasterCount = Number(
    engine.settingsSearch?.rejectedFasterCandidateCount || 0,
  );
  if (!Number.isInteger(rejectedFasterCount) || rejectedFasterCount <= 0) return "";
  const accelerator = engine.backend === "omlx"
    ? "DFlash 2" : ["lmstudio", "mtplx"].includes(engine.backend) ? "MTP" : "accelerator";
  const plural = rejectedFasterCount > 1;
  return `${plural ? `${rejectedFasterCount} faster raw ${accelerator} candidates were` : `A faster raw ${accelerator} candidate was`} excluded after failing greedy output parity with AR; ${plural ? "their" : "its"} TPS is not trusted or used here.`;
}

function calibrationRoutePreview(plan) {
  return (plan?.engines || [])
    .filter(engine => engine.eligible && capabilities.uiEngineVisible(engine.backend || engine.id))
    .map(engine => {
      const modes = (engine.modes || []).map(mode => mode.label).filter(Boolean);
      const unavailable = modes.length <= 1 && engine.accelerationReason
        ? ` (${String(engine.accelerationReason).replace(/^This model /, "model ").replace(/[.]$/, "")})`
        : "";
      const route = modes.length > 1 ? modes.join(" + ") : `${modes[0] || "AR"} only${unavailable}`;
      return `${engine.label}: ${route}`;
    })
    .join(" · ");
}

function calibrationAlternativeMarkup(plan, controlsLocked) {
  const alternative = (plan?.modelAlternatives || []).find(item => (
    item?.differentModel === true
    && item?.intelligenceContractChanged === true
    && item?.requiresExplicitSelection === true
  ));
  if (!alternative) return "";
  const modelId = alternative.modelId || alternative.id;
  if (!modelId) return "";
  const modelName = alternative.modelName || alternative.name || "27B DFlash model";
  const backend = alternative.backend || "omlx";
  const hostState = String(alternative.hostSupport?.state || alternative.hostSupport?.tier || "supported").toLowerCase();
  const evidenceTier = String(alternative.performanceEvidence?.tier || "").toLowerCase();
  const verifiedHere = evidenceTier === "verified-this-mac";
  const capacity = alternative.capacity || {};
  const unavailable = hostState === "unavailable" || hostState === "unsupported"
    || capacity.launchable === false;
  const modes = (alternative.modes || ["DFlash 2"])
    .map(mode => typeof mode === "object" ? mode.label : mode)
    .filter(Boolean);
  const facts = [
    alternative.backendLabel || formatting.backendName(backend),
    ...modes,
    capacity.sizeLabel,
    capacity.quantization,
    alternative.hostSupport?.label,
    alternative.performanceEvidence?.label,
  ].filter((value, index, values) => value && values.indexOf(value) === index);
  const evidenceCopy = verifiedHere
    ? "A matching DFlash result is verified on this Mac, but this route changes the model and intelligence contract and is never selected automatically."
    : "This smaller/different 27B DFlash route changes the model and intelligence contract. It is not verified here or selected automatically.";
  return `<article class="calibration-engine excluded"><header><strong>Different 27B DFlash model</strong><em>${unavailable ? "Unavailable" : "Explicit choice"}</em></header><p>${formatting.esc(evidenceCopy)}</p><div class="calibration-engine-modes">${facts.slice(0, 4).map(item => `<span>${formatting.esc(item)}</span>`).join("")}</div><div class="calibration-engine-alternative"><small><b>${formatting.esc(modelName)}</b>${facts.length > 4 ? ` · ${formatting.esc(facts.slice(4).join(" · "))}` : ""}</small><button type="button" class="text-button" data-calibration-model="${formatting.esc(modelId)}" ${controlsLocked || unavailable ? "disabled" : ""}>Select different 27B model</button></div></article>`;
}

function renderCalibrationPlan() {
  let plan = state.calibrationPlan;
  if (
    plan && plan.action !== "apply-existing"
    && completedCalibrationDecision()
    && promoteCompletedCalibrationResult()
  ) plan = state.calibrationPlan;
  const routeQualification = plan?.routeQualification === true;
  const qualificationPreparation = plan?.qualificationPreparation || null;
  const qualification = calibrationQualificationProfile(plan || {});
  const qualificationFlow = routeQualification
    || qualificationPreparation?.kind === "qwen-ple-safe-qualification-v1";
  $("calibrationDialog").classList.toggle("route-qualification", qualificationFlow);
  $("calibrationDialogTitle").textContent = qualificationFlow ? "Route Qualification" : "Calibration Assistant";
  $("calibrationDialogSubtitle").textContent = qualificationFlow
    ? qualification.subtitle
    : "Find the best installed engine for the exact model and work you selected.";
  $("calibrationPreferenceLabel").textContent = qualificationFlow ? "Result metric" : "Decision goal";
  $("calibrationEnginesTitle").textContent = qualificationFlow ? "Route being qualified" : "Included engines";
  const active = calibrationBenchmarkActive();
  const controlsLocked = state.calibrationLoading || state.calibrationStarting
    || active || state.calibrationApplying;
  if (routeQualification && plan?.suite?.id) {
    $("calibrationSuiteSelect").value = calibrationSuiteControlValue(plan.suite.id);
  }
  const coolingLocked = plan?.calibrationCoolingLocked === true;
  if (coolingLocked) {
    $("calibrationCoolingSelect").value = plan.calibrationCooling || "default";
  }
  $("calibrationSuiteSelect").disabled = controlsLocked || routeQualification;
  $("calibrationPreferenceSelect").disabled = controlsLocked;
  $("calibrationCoolingSelect").disabled = controlsLocked || coolingLocked;
  if (!plan) {
    $("calibrationPhase").closest(".calibration-progress")?.classList.remove("hidden");
    calibrationStateBadge("calibrationContractState", state.calibrationLoading ? "Checking" : "Unavailable", state.calibrationLoading ? "" : "blocked");
    calibrationStateBadge("calibrationEngineState", "Waiting", "");
    calibrationStateBadge("calibrationEvidenceState", "Waiting", "");
    setMarkup($("calibrationPlanFacts"), "");
    setMarkup($("calibrationEngineCards"), "");
    setMarkup($("calibrationResults"), "");
    $("calibrationResults").classList.add("hidden");
    $("calibrationEvidence").className = "calibration-evidence blocked";
    setMarkup($("calibrationEvidence"), `<i aria-hidden="true">!</i><span><strong>${state.calibrationLoading ? "Inspecting the visible contract…" : "A valid calibration plan is not available."}</strong><small>${formatting.esc($("calibrationStatus").textContent || "Choose a ready model and valid settings.")}</small></span>`);
    $("calibrationConsent").disabled = true;
    $("calibrationConsent").checked = false;
    $("calibrationConsentPanel").classList.add("hidden");
    $("calibrationStartButton").disabled = true;
    $("calibrationStartButton").dataset.action = "measure";
    $("calibrationStartButton").dataset.admission = "checking";
    $("calibrationStartButton").title = "";
    $("calibrationStartButton").classList.remove("primary");
    $("calibrationStartButton").classList.add("secondary");
    $("calibrationStartButton").querySelector("strong").textContent = state.calibrationLoading
      ? "Checking route" : "Test unavailable";
    $("calibrationStartLabel").textContent = state.calibrationLoading
      ? "Waiting for the current plan" : "Choose a valid route first";
    $("calibrationApplyButton").disabled = true;
    $("calibrationApplyButton").classList.remove("primary");
    $("calibrationApplyButton").classList.add("secondary");
    $("calibrationApplyButton").textContent = "Apply result";
    $("calibrationApplyButton").title = state.calibrationLoading
      ? "Wait for the current calibration plan." : "No applicable calibration result is available.";
    $("calibrationProfilePanel").classList.add("hidden");
    return;
  }
  const request = plan.request || {};
  const reasoningContract = plan.reasoningContract || {};
  const normalizedReasoning = reasoningContract.normalized === true;
  const qualificationContractExact = routeQualificationContractExact(plan);
  const kv = qualification.uzu
    ? "BF16 · runtime fixed"
    : request.options?.kv && request.options.kv !== "off" ? String(request.options.kv).toUpperCase() : "Full precision";
  calibrationStateBadge(
    "calibrationContractState",
    qualificationContractExact ? "Locked" : "Contract mismatch",
    qualificationContractExact ? "ready" : "blocked",
  );
  const contextAdjustment = plan.contextAdjustment?.reason ? ` ${plan.contextAdjustment.reason}` : "";
  $("calibrationContract").textContent = qualification.llama
    ? `${plan.model.name} · exact route · fixed ${formatting.formatNumber(policy.LLAMACPP_PLE_QUALIFICATION_CONTEXT)} context · ${formatting.formatNumber(request.output)} configured max response. Generated qualification probes are capped at ${formatting.formatNumber(policy.LLAMACPP_PLE_QUALIFICATION_SAMPLE_MAX_TOKENS)} tokens, so longer outputs remain configured rather than measured. Reasoning is runtime-controlled and stays on. This route-level receipt can be reused by compatible work surfaces with the same sampling contract. Qualification is valid only below the exact 44 GiB Metal ceiling; model, quantisation, sampling, prompt contract, full-precision KV, and one request lane stay fixed.`
    : qualification.uzu
      ? `${plan.model.name} · built-in Chat · exact ${formatting.exactContextTier(request.context)} context · ${formatting.formatNumber(request.output)} max response. DFlash + Weaver, packaged sampling, model-default reasoning, and BF16 KV stay fixed for this qualification.`
    : (normalizedReasoning
      ? `${plan.model.name} · ${plan.clientLabel} · ${formatting.formatNumber(request.context)} context · ${formatting.formatNumber(request.output)} max response. ${reasoningContract.detail} Your launch setting changes only if you apply the result.`
      : `${plan.model.name} · ${plan.clientLabel} · ${formatting.formatNumber(request.context)} context · ${formatting.formatNumber(request.output)} max response. The model, quantisation, reasoning, sampling, prompt contract, and KV precision stay fixed.`) + contextAdjustment;
  const planFacts = qualification.llama ? [
    ["Workload", plan.suite.label], ["Route", "Pinned SSD PLE"],
    ["Context", "Fixed 8K"], ["Reasoning", qualification.reasoningLabel],
    ["Memory ceiling", "44 GiB exact"], ["KV precision", kv],
    ["Measured turns", "4 bounded"], ["Cooling", plan.calibrationCoolingLabel || "Automatic"],
  ] : qualification.uzu ? [
    ["Route", "DFlash + Weaver"], ["Context", `Exact ${formatting.exactContextTier(request.context)}`],
    ["Work surface", "Built-in Chat"], ["Reasoning", qualification.reasoningLabel],
    ["KV cache", kv], ["Memory ceiling", `${policy.UZU_QUALIFICATION_MEMORY_LIMIT_BYTES / (1024 ** 3)} GiB`],
    ["Measured turns", "4 bounded"], ["Minimum speed", `≥${policy.UZU_QUALIFICATION_MINIMUM_TPS} tok/s each`],
  ] : [
    ["Workload", plan.suite.label], ["Goal", plan.preferenceLabel],
    ...(plan.ssdStreaming ? [["Route type", "SSD-streamed MoE"]] : []),
    ["Reasoning", normalizedReasoning ? `Model default (from ${reasoningContract.requested})` : request.reasoning], ["KV precision", kv],
    [plan.countsAreMaximum ? "Max model reloads" : "Model reloads", String(plan.modelReloadCount)],
    [plan.countsAreMaximum ? "Max measured requests" : "Measured requests", String(plan.measuredRequestCount)],
    [routeQualification ? "Qualified routes" : "Compared engines", String(plan.eligibleEngineCount)], ["Cooling", plan.calibrationCoolingLabel || "Automatic"],
  ];
  setMarkup($("calibrationPlanFacts"), planFacts
    .map(([label,value]) => `<span><small>${formatting.esc(label)}</small><b title="${formatting.esc(value)}">${formatting.esc(value)}</b></span>`).join(""));
  calibrationStateBadge(
    "calibrationEngineState",
    plan.ready
      ? routeQualification ? `${plan.eligibleEngineCount} route` : `${plan.eligibleEngineCount} comparable`
      : `${plan.eligibleEngineCount} eligible`,
    plan.ready ? "ready" : "blocked",
  );
  const calibrationEngineMarkup = (plan.engines || [])
    .filter(engine => capabilities.uiEngineVisible(engine.backend || engine.id))
    .map(engine => {
      const setupCount = Number(engine.measurementRouteCount || 0);
      const setupLabel = engine.eligible && !routeQualification && setupCount > 0
        ? `Up to ${setupCount} setup${setupCount === 1 ? "" : "s"}`
        : engine.eligible ? "Exact route" : "Excluded";
      const search = engine.settingsSearch || {};
      const axes = Array.isArray(search.axes) ? search.axes : [];
      const searchDetail = search.kind
        ? `${search.label} · up to ${search.maximumCandidateCount} candidate setup${search.maximumCandidateCount === 1 ? "" : "s"} + ${search.referenceSetupCount} reference setup${search.referenceSetupCount === 1 ? "" : "s"}${axes.length ? ` · ${axes.join(", ")}` : ""}`
        : "";
      return `<article class="calibration-engine ${engine.eligible ? "eligible" : "excluded"}"><header><strong>${formatting.esc(engine.label)}</strong><em>${formatting.esc(setupLabel)}</em></header><p>${formatting.esc(engine.modeDetail || engine.reason)}</p>${searchDetail ? `<small class="calibration-engine-settings calibration-detail-only">Settings search · ${formatting.esc(searchDetail)}</small>` : engine.settingsLabel ? `<small class="calibration-engine-settings calibration-detail-only">Fixed controls · ${formatting.esc(engine.settingsLabel)}</small>` : ""}<div class="calibration-engine-modes">${(engine.modes || []).map(mode => `<span>${formatting.esc(mode.label)}</span>`).join("") || ""}</div></article>`;
    }).join("");
  setMarkup($("calibrationEngineCards"), `${calibrationEngineMarkup}${calibrationAlternativeMarkup(plan, controlsLocked)}`);
  const evidence = plan.evidence || {};
  const evidenceReady = plan.action === "apply-existing";
  const completed = completedCalibrationDecision();
  const completedResult = completed?.result || null;
  const completedDecision = completed?.decision || null;
  const completedDecisionReady = Boolean(completed);
  const resultPending = Boolean(completedDecisionReady && !evidenceReady);
  const completedEvidenceBinding = completedResult && completedDecision
    ? completedCalibrationEvidenceBinding(completedResult, completedDecision) : null;
  const shownEvidence = resultPending ? {
    trusted:Boolean(completedDecision.trustedWinner),
    label:CalibrationDecision.summary(completedDecision),
    backend:completedDecision.backend,
    backendLabel:completedDecision.label,
    engineChanged:Boolean(completedDecision.engineChanged),
    leadingBackends:completedDecision.leadingBackends || [],
    currentInLeadingBand:completedDecision.currentInLeadingBand === true,
    detail:completedDecision.rationale?.[0] || completedDecision.recommendation || completedResult.recommendation || "The completed result is being saved.",
    outputWarning:completedDecision.outputWarning || completedResult.outputWarning || "",
    comparedEngines:completedDecision.comparedEngines || (completedResult.qualified ? [] : completedResult.engines) || [],
    qualified:Boolean(completedDecision.qualified || completedResult.qualified),
    qualifiedRoutes:completedDecision.qualifiedRoutes || completedResult.qualifiedRoutes || [],
    ...(completedEvidenceBinding ? {evidenceBinding:completedEvidenceBinding} : {}),
  } : evidence;
  const resultReady = evidenceReady || resultPending;
  const preparationAvailable = Boolean(
    !resultReady && !plan.ready
    && qualificationPreparation?.applicable === true
    && qualificationPreparation?.resolvesVisibleSettings === true
    && qualificationPreparation?.doesNotChangeMacOS === true
  );
  calibrationStateBadge(
    "calibrationEvidenceState",
    !qualificationContractExact ? "Contract mismatch"
      : resultReady ? (routeQualification ? "Route qualified" : shownEvidence.trusted ? "Winner ready" : "Result ready")
        : (plan.ready ? routeQualification ? "Ready to qualify" : "Ready to test" : preparationAvailable ? "Prepare settings" : "Blocked"),
    !qualificationContractExact ? "blocked"
      : resultReady ? "ready" : (plan.ready || preparationAvailable ? "" : "blocked"),
  );
  const blockers = (plan.blockers || []).join(" ");
  const routePreview = calibrationRoutePreview(plan);
  const preparationAdmission = qualificationPreparation?.nextAdmission || {};
  const memoryBlocker = plan.memoryAdmission || {};
  const systemSettingBlocked = routeQualification
    && memoryBlocker.decision === "system-setting";
  const runtimeConflictBlocked = routeQualification
    && memoryBlocker.decision === "runtime-conflict";
  const requiredMetalLimitBytes = Number(
    memoryBlocker.estimate?.requiredMetalWiredLimitBytes
      || memoryBlocker.estimate?.memoryCeilingBytes
      || 0,
  );
  const requiredMetalLimitGiB = requiredMetalLimitBytes > 0
    ? Math.ceil(requiredMetalLimitBytes / (1024 ** 3)) : null;
  const metalApprovalLabel = requiredMetalLimitGiB
    ? `Set exact ${requiredMetalLimitGiB} GiB Metal limit`
    : "Set the required Metal memory limit";
  const preparationDetail = preparationAvailable
    ? [
        qualificationPreparation.summary,
        preparationAdmission.label ? `Next check: ${preparationAdmission.label}.` : "",
        "This changes only the visible launcher settings; macOS is not changed.",
      ].filter(Boolean).join(" ")
    : "";
  const evidenceDetail = !qualificationContractExact
    ? qualification.uzu
      ? "The controller did not preserve this exact Uzu context, DFlash + Weaver, BF16 KV, Chat, and memory-safety contract. Refresh models before qualifying or applying it."
      : qualification.llama
        ? "The controller did not preserve the pinned llama.cpp fixed-8K, runtime-controlled reasoning, exact-44-GiB contract. Refresh models before qualifying or applying it."
        : "The controller did not preserve this exact qualification contract. Refresh models before qualifying or applying it."
    : resultReady
    ? [shownEvidence.detail, shownEvidence.outputWarning].filter(Boolean).join(" ")
    : preparationAvailable ? preparationDetail
    : plan.ready
      ? routeQualification
        ? qualification.llama
          ? `One exact pinned llama.cpp SSD PLE load will run four generated reasoning turns at fixed 8K. Every turn must expose separate reasoning and a final answer; authoritative TPS and TTFT, peak memory below the exact 44 GiB ceiling, one valid Jinja tool call, and a clean unload are required.${routePreview ? ` Route: ${routePreview}.` : ""}`
          : qualification.uzu
            ? `One exact Uzu DFlash + Weaver load will run four generated Chat turns at ${formatting.exactContextTier(request.context)}. Every turn must reach at least ${policy.UZU_QUALIFICATION_MINIMUM_TPS} tok/s with reasoning and a final answer; BF16 KV memory, correctness, and clean unload are checked.${routePreview ? ` Route: ${routePreview}.` : ""}`
          : `One exact oMLX AR + PLE mmap load will run four generated reasoning turns. Authoritative usage, generation TPS, time to first output, memory pressure, and thermal state are recorded; every turn must expose separate reasoning and a final answer.${routePreview ? ` Route: ${routePreview}.` : ""}`
        : plan.ssdStreaming
        ? `${plan.eligibleEngineCount} SSD runtimes will be tested one at a time using generated prompts. First-turn and warm-prefix TPS, time to first output, memory pressure, and thermal state are recorded. The OS file cache is observed rather than forcibly purged.${routePreview ? ` Routes: ${routePreview}.` : ""}`
        : `${plan.eligibleEngineCount} engines and their supported settings will be tested one at a time using generated prompts.${routePreview ? ` Setups: ${routePreview}.` : ""}`
      : systemSettingBlocked
        ? `${metalApprovalLabel}. Unlock this Mac, run sudo /usr/sbin/sysctl -w iogpu.wired_limit_mb=45056 in Terminal, then choose Recheck limit. The launcher will only accept an exact readback and will not raise it further.`
        : runtimeConflictBlocked
          ? memoryBlocker.detail
        : blockers;
  $("calibrationEvidence").className = `calibration-evidence${!qualificationContractExact ? " blocked" : resultReady ? " trusted" : plan.ready || preparationAvailable ? "" : " blocked"}`;
  setMarkup($("calibrationEvidence"), `<i aria-hidden="true">${!qualificationContractExact ? "×" : resultReady ? "◆" : plan.ready || preparationAvailable ? "◇" : "×"}</i><span><strong>${formatting.esc(!qualificationContractExact ? "Exact qualification contract unavailable" : resultReady ? shownEvidence.label : plan.ready ? routeQualification ? "Ready to qualify this route" : "Ready to test engines + settings" : preparationAvailable ? "Prepare this route safely" : systemSettingBlocked ? metalApprovalLabel : runtimeConflictBlocked ? memoryBlocker.label : "This setup cannot be tested yet")}</strong><small>${formatting.esc(evidenceDetail)}</small></span>`);
  $("calibrationPhase").closest(".calibration-progress")?.classList.toggle(
    "hidden", !active && !resultReady && !plan.ready,
  );
  const measuredDecision = completedDecision || (evidenceReady ? evidence : null);
  const measuredEngines = routeQualification
    ? Array.isArray(measuredDecision?.qualifiedRoutes) ? measuredDecision.qualifiedRoutes : []
    : Array.isArray(measuredDecision?.comparedEngines) ? measuredDecision.comparedEngines : [];
  const measuredDecisionReady = Boolean(completedDecision
    ? ["cross-engine-local-benchmark", "cross-engine-leading-band", "cross-engine-noise-floor", "local-route-qualification"]
      .includes(completedDecision.evidenceTier)
    : evidenceReady);
  $("calibrationResults").classList.toggle("hidden", measuredEngines.length === 0);
  setMarkup($("calibrationResults"), measuredEngines.length ? `<strong>${routeQualification ? "Route qualification result" : "Measured engine results"}</strong><div>${measuredEngines.map((engine, index) => {
    const selected = measuredDecisionReady && engine.backend === (measuredDecision.backend || shownEvidence.backend);
    const mode = qualification.uzu ? "DFlash + Weaver"
      : engine.mode === "dflash2" ? "DFlash 2" : engine.mode === "mtp" ? "MTP" : plan.ssdStreaming ? "SSD stream" : "AR";
    const testedModes = Array.isArray(engine.testedModes) && engine.testedModes.length
      ? engine.testedModes : [engine.mode || "ar"];
    const search = engine.settingsSearch || {};
    const tuningCount = Number(search.testedCandidateCount || 0);
    const testedRoutes = testedModes.map(item => (
      item === "mtp" && search.kind === "mtplx-depth" && tuningCount > 0
        ? `MTP depth (${tuningCount} candidates)`
        : item === "mtp" && search.kind === "lmstudio-mtp" && tuningCount > 0
          ? `MTP tuned (${tuningCount} candidates)`
          : item === "dflash2" && search.kind === "omlx-dflash2" && tuningCount > 0
            ? `DFlash tuned (${tuningCount} candidates)`
        : benchmarkWinnerLabel(item)
    ));
    const testedLabel = routeQualification
      ? `Measured ${engine.reasoningTurns || 0}/${engine.sampleCount || 0} reasoning turns with final answers`
      : plan.ssdStreaming
      ? "Tested exact native SSD streaming"
      : testedModes.length > 1
      ? `Tested ${testedRoutes.join(" + ")}`
      : `Tested AR only · ${engine.accelerationReason || "no verified accelerator in this artifact"}`;
    const exactRoute = search.selectedSetupLabel || engine.routeSettingsLabel
      || (qualification.llama ? "SSD PLE · exact 8K"
        : qualification.uzu ? `DFlash + Weaver · exact ${formatting.exactContextTier(request.context)}` : mode);
    const modeLabel = routeQualification ? exactRoute : plan.ssdStreaming ? exactRoute : search.kind ? `Selected: ${exactRoute}` : testedModes.length > 1 ? `Winner: ${exactRoute}` : "AR only";
    const testedSetups = Number(search.testedSetupCount || 0);
    const maximumSetups = Number(search.maximumSetupCount || 0);
    const setupCoverage = search.kind && testedSetups > 0 && maximumSetups >= testedSetups
      ? `Tested ${testedSetups}/${maximumSetups} setups`
      : "";
    const searchAxes = Array.isArray(search.axes) ? search.axes : [];
    const searchDetail = search.kind
      ? `${tuningCount}/${Number(search.maximumCandidateCount || tuningCount)} ${search.label || "tuning"} candidates · ${Number(search.referenceSetupCount || 0)} reference setup${Number(search.referenceSetupCount || 0) === 1 ? "" : "s"}${searchAxes.length ? ` · axes: ${searchAxes.join(", ")}` : ""}`
      : "";
    const decodeTps = formatting.finiteMetric(engine.decodeTokensPerSecond);
    const parityRejectionNote = calibrationParityRejectionNote(engine);
    const badge = CalibrationDecision.resultBadge(routeQualification ? {...measuredDecision, qualified:true} : measuredDecision, engine, index);
    const qualificationFacts = routeQualification
      ? routeQualificationFactsMarkup(engine, completedResult || {}, qualification.backend)
      : decodeTps === null ? "" : `<small class="calibration-result-tps">Generation ${decodeTps.toFixed(1)} tok/s</small>`;
    return `<article class="${selected ? "selected" : ""}" title="${formatting.esc(engine.modeDetail || testedLabel)}"><span><b>${formatting.esc(engine.label || formatting.backendName(engine.backend))}</b><small>${formatting.esc(modeLabel)}</small></span><strong>${formatting.esc(engine.profileDisplay || engine.display || "Measured")}</strong>${setupCoverage ? `<small class="calibration-result-coverage">${formatting.esc(setupCoverage)}</small>` : ""}<small class="calibration-result-modes calibration-detail-only">${formatting.esc(testedLabel)}</small>${searchDetail ? `<small class="calibration-result-settings calibration-detail-only">Search detail · ${formatting.esc(searchDetail)}</small>` : engine.settingsLabel ? `<small class="calibration-result-settings calibration-detail-only">Fixed controls · ${formatting.esc(engine.settingsLabel)}</small>` : ""}${parityRejectionNote ? `<small class="calibration-result-settings calibration-detail-only">${formatting.esc(parityRejectionNote)}</small>` : ""}${qualificationFacts}<em>${formatting.esc(badge)}</em></article>`;
  }).join("")}</div>` : "");
  if (state.calibrationProfileContractId !== plan.contractId) {
    state.calibrationProfileContractId = plan.contractId;
    $("calibrationProfileName").value = plan.suggestedProfileName || "Quick Launch";
  }
  const measurementAdmission = calibrationMeasurementAdmission(plan);
  const measurementAdmissionRelevant = routeQualification
    ? Boolean(plan.memoryAdmission)
    : ["measure", "apply-existing"].includes(plan.action) && plan.ready;
  const measurementAdmissionBlocked = Boolean(
    measurementAdmissionRelevant && !measurementAdmission.actionReady,
  );
  const canMeasure = ["measure", "apply-existing"].includes(plan.action)
    && plan.ready && qualificationContractExact
    && measurementAdmission.actionReady
    && !resultPending && !calibrationOperationBlocked();
  const canRefreshResult = resultPending && qualificationContractExact
    && !calibrationOperationBlocked();
  const canPrepare = preparationAvailable && !calibrationOperationBlocked();
  const canRecheckSystemSetting = systemSettingBlocked && !calibrationOperationBlocked();
  const canRecheckRuntimeConflict = runtimeConflictBlocked && !calibrationOperationBlocked();
  const measurementAdmissionBlocksAction = measurementAdmissionBlocked
    && !resultPending && !canPrepare && !canRecheckSystemSetting && !canRecheckRuntimeConflict;
  $("calibrationConsent").disabled = true;
  $("calibrationConsent").checked = false;
  $("calibrationConsentPanel").classList.add("hidden");
  $("calibrationConsentCopy").textContent = plan.ready
    ? `${routeQualification ? "1 exact route" : `${plan.eligibleEngineCount} engines`} · ${plan.countsAreMaximum ? "up to " : ""}${plan.modelReloadCount} isolated reloads · ${plan.countsAreMaximum ? "up to " : ""}${plan.measuredRequestCount} generated local requests · ${plan.calibrationCoolingLabel || "Automatic"} cooling · up to ${Math.round(plan.resourceCooldownMaxSecondsPerRoute)} seconds of cancellable settling before each route.`
    : blockers || "Resolve the engine blockers before measurement.";
  $("calibrationStartButton").disabled = !(canMeasure || canRefreshResult || canPrepare || canRecheckSystemSetting || canRecheckRuntimeConflict);
  $("calibrationStartButton").dataset.admission = measurementAdmissionBlocksAction ? "blocked" : "ready";
  $("calibrationStartButton").dataset.action = canPrepare
    ? "prepare" : canRecheckSystemSetting ? "recheck-limit" : canRecheckRuntimeConflict ? "recheck-conflict" : "measure";
  let measurementAction = evidenceReady
    ? "Retest engines + settings" : resultPending ? "Use saved result" : "Test engines + settings";
  let measurementDetail = evidenceReady
    ? "Replace this saved measurement"
    : resultPending ? "The test is complete — this will not run it again"
    : plan.ready ? `${plan.eligibleEngineCount} engines · ${plan.countsAreMaximum ? "up to " : ""}${plan.routeCount} setups`
      : "Resolve the blockers above";
  if (routeQualification) {
    measurementAction = evidenceReady
      ? "Requalify route" : resultPending ? "Use saved result" : "Qualify route";
    measurementDetail = evidenceReady
      ? "Replace this saved qualification"
      : resultPending ? "The qualification is complete — this will not run it again"
      : !qualificationContractExact ? "Refresh the exact controller contract"
      : plan.ready ? qualification.llama
        ? "1 route · fixed 8K · exact 44 GiB ceiling"
        : qualification.uzu
          ? `1 route · exact ${formatting.exactContextTier(request.context)} · 4 bounded Chat turns`
          : "1 route · 4 bounded reasoning turns"
        : systemSettingBlocked ? metalApprovalLabel
          : runtimeConflictBlocked ? memoryBlocker.label : "Resolve the blockers above";
  }
  if (canPrepare) {
    measurementAction = "Prepare safe test";
    measurementDetail = "Visible settings only · does not change macOS";
  } else if (canRecheckSystemSetting) {
    measurementAction = "Recheck limit";
    measurementDetail = requiredMetalLimitGiB
      ? `Requires the exact ${requiredMetalLimitGiB} GiB Metal limit · does not change macOS`
      : "Recheck the required Metal limit · does not change macOS";
  } else if (canRecheckRuntimeConflict) {
    measurementAction = "Recheck Whallm";
    measurementDetail = "Unload or close Whallm, then recheck · the launcher will not stop it";
  } else if (measurementAdmissionBlocked && !resultPending) {
    measurementDetail = operations.sessionAdmissionBlockerCopy(measurementAdmission);
  }
  $("calibrationStartButton").title = measurementAdmissionBlocksAction
    ? measurementAdmission.detail : "";
  $("calibrationStartButton").querySelector("strong").textContent = measurementAction;
  $("calibrationStartLabel").textContent = measurementDetail;
  const routeEvidenceQualified = !routeQualification || shownEvidence.qualified === true;
  const canApply = evidenceReady && Boolean(evidence.evidenceBinding)
    && routeEvidenceQualified && qualificationContractExact
    && !calibrationOperationBlocked();
  $("calibrationApplyButton").disabled = !canApply;
  $("calibrationApplyButton").classList.toggle("primary", canApply);
  $("calibrationApplyButton").classList.toggle("secondary", !canApply);
  $("calibrationStartButton").classList.toggle("primary", !evidenceReady);
  $("calibrationStartButton").classList.toggle("secondary", evidenceReady);
  const applyResultLabel = routeQualification
    ? "Apply qualified route" : CalibrationDecision.applyLabel(evidence);
  $("calibrationApplyButton").textContent = normalizedReasoning && !routeQualification
    ? `${applyResultLabel} + model default` : applyResultLabel;
  $("calibrationApplyButton").title = routeQualification
    ? canApply
      ? `Apply the qualified ${qualification.routeLabel} without running the test again.`
      : !qualificationContractExact
        ? "The exact qualification contract no longer matches. Refresh before applying."
        : !routeEvidenceQualified
          ? "This route did not pass qualification, so it cannot be applied."
          : !evidenceReady
            ? "Complete the route qualification before applying it."
            : !evidence.evidenceBinding
              ? "The completed qualification has no immutable apply reference yet. Refresh it before applying."
              : "Wait for the current launcher operation to finish before applying."
    : normalizedReasoning
      ? "Apply the measured engine and its model-default reasoning contract."
      : "Apply the measured engine and settings to the launcher.";
  $("calibrationProfilePanel").classList.toggle("hidden", !canApply || active);
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
  const liveTps = formatting.finiteMetric(status.liveMetric?.decodeTokensPerSecond);
  const showLiveTps = Boolean(active && owns);
  $("calibrationLiveTps").classList.toggle("hidden", !showLiveTps);
  $("calibrationLiveTps").textContent = showLiveTps
    ? liveTps === null ? "Measuring…" : `Last completed turn · ${liveTps.toFixed(1)} tok/s`
    : "";
  $("calibrationLiveTps").title = showLiveTps
    ? [status.liveMetric?.backendLabel, status.liveMetric?.modeLabel, status.liveMetric?.stageLabel]
      .filter(Boolean).join(" · ")
    : "";
  if (state.calibrationStarting) {
    $("calibrationBadge").textContent = "Starting";
    $("calibrationBadge").className = "setup-badge active";
    $("calibrationPhase").textContent = "Submitting";
    $("calibrationStatus").textContent = state.calibrationPlan?.routeQualification
      ? "Submitting this exact route qualification…"
      : "Submitting this exact engine comparison…";
    return;
  }
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
    const immutableBinding = completedCalibrationEvidenceBinding(result, decision);
    const saved = result.persistence?.saved === true && immutableBinding
      ? " Saved locally; no second test is needed."
      : result.persistence?.saved === true
        ? " Saved locally; refresh the result before applying it."
        : immutableBinding
          ? " You can use the result without testing again."
          : " Refresh the result before applying it.";
    $("calibrationStatus").textContent = result.kind === "route-qualification"
      ? `${decision.recommendation || "The exact route is qualified."}${saved}`
      : decision.trustedWinner
      ? `${decision.label} won for ${enginePreferenceLabels[decision.preference] || "this goal"}.${saved}`
      : `${decision.recommendation || "The engines finished in a practical tie, so the current engine is kept."}${saved}`;
    if (promoteCompletedCalibrationResult(status)) renderCalibrationPlan();
    if (result.id && state.calibrationCompletionId !== result.id) {
      state.calibrationCompletionId = result.id;
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
  const preparationAvailable = Boolean(
    plan?.qualificationPreparation?.applicable === true
    && plan?.qualificationPreparation?.resolvesVisibleSettings === true
    && plan?.qualificationPreparation?.doesNotChangeMacOS === true
  );
  if (!state.calibrationLoading && plan?.action === "apply-existing") {
    // Reopening a persisted result has no live job progress, but its completed
    // measurement must not be presented as a fresh 0% run.
    $("calibrationPercent").textContent = "100%";
    $("calibrationProgressBar").style.width = "100%";
    $("calibrationProgressBar").parentElement.setAttribute("aria-valuenow", "100");
  }
  $("calibrationBadge").textContent = state.calibrationLoading ? "Checking" : plan?.action === "apply-existing" ? "Result ready" : plan?.ready ? "Ready" : preparationAvailable ? "Prepare" : "Blocked";
  $("calibrationBadge").className = `setup-badge${plan?.action === "apply-existing" ? " ready" : !plan?.ready && plan ? " warning" : ""}`;
  $("calibrationPhase").textContent = plan?.action === "apply-existing" ? "Ready to use" : plan?.ready ? "Ready to test" : "Needs attention";
  if (!state.calibrationLoading) {
    $("calibrationStatus").textContent = plan?.action === "apply-existing"
      ? "Your saved result matches these settings. No new test is needed."
      : plan?.ready ? plan.routeQualification ? "Choose Qualify route when you are ready." : "Choose Test engines + settings when you are ready."
        : preparationAvailable ? "Prepare the visible safe qualification settings first; macOS stays unchanged."
          : ((plan?.blockers || ["Choose a valid comparable setup."])[0]);
  }
}

function renderCalibration() {
  const expanded = effects.activeDetail() === "detailed" || state.calibrationDetailsOpen;
  $("calibrationDialog").classList.toggle("show-calibration-details", state.calibrationDetailsOpen);
  $("calibrationDetailToggle").setAttribute("aria-expanded", String(expanded));
  $("calibrationDetailToggle").textContent = state.calibrationDetailsOpen ? "Hide details" : "Full details";
  updateCalibrationHelp();
  renderCalibrationEntry();
  renderCalibrationPlan();
  renderCalibrationBenchmark(state.benchmarkStatus || {});
  if(calibrationError && !calibrationBenchmarkActive()) $("calibrationStatus").textContent=calibrationError;
}

async function loadCalibrationPlan(resetJob = true) {
  calibrationError="";
  const generation = ++state.calibrationGeneration;
  let request;
  try { request = calibrationPlanRequest(); }
  catch (error) {
    state.calibrationPlan = null;
    state.calibrationLoading = false;
    calibrationError=String(error.message || "Calibration could not be checked.").slice(0,2048);
    $("calibrationStatus").textContent = calibrationError;
    renderCalibration();
    return null;
  }
  state.calibrationLoading = true;
  state.calibrationPlan = null;
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
      calibrationError=String(error.message || "Calibration could not be checked.").slice(0,2048);
      $("calibrationStatus").textContent = calibrationError;
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
    : "throughput";
  const recommendedSuite = options.decision?.engineNextAction?.recommendedSuite
    || receiptPort.performanceReceiptSuite();
  state.calibrationEntry = options.source ? {
    source:options.source,
    preference,
    decision:options.decision || null,
  } : null;
  state.calibrationDetailsOpen = false;
  effects.closeOptimizerMenu();
  $("calibrationSuiteSelect").value = calibrationSuiteControlValue(recommendedSuite);
  $("calibrationPreferenceSelect").value = preference;
  state.calibrationGeneration += 1;
  state.calibrationLoading = true;
  state.calibrationPlan = null;
  $("calibrationStatus").textContent = "Inspecting the visible route before enabling any action…";
  renderCalibration();
  if (!$("calibrationDialog").open) {
    const visibleCooling = $("fanSelect").value;
    const matchingCooling = [...$("calibrationCoolingSelect").options]
      .find(item => item.value === visibleCooling && !item.disabled);
    if (matchingCooling && !calibrationBenchmarkActive()) {
      $("calibrationCoolingSelect").value = visibleCooling;
    }
    $("calibrationDialog").showModal();
  }
  await pollBenchmarkStatus();
  await loadCalibrationPlan(!calibrationBenchmarkActive());
}

async function selectCalibrationAlternative(modelId) {
  if (calibrationOperationBlocked()) return;
  const alternative = (state.calibrationPlan?.modelAlternatives || [])
    .find(item => String(item?.modelId || item?.id || "") === String(modelId || ""));
  if (!alternative || alternative.requiresExplicitSelection !== true) {
    effects.showNotice("That different-model route does not expose an explicit selection contract.", true);
    return;
  }
  const alternativeBackend = String(alternative.backend || state.backend);
  if (!capabilities.uiEngineVisible(alternativeBackend)) {
    effects.showNotice("That different-model runtime is not available in this launcher view.", true);
    return;
  }
  if (alternativeBackend !== state.backend) {
    settingsPort.selectBackend(alternativeBackend);
  }
  const option = [...$("modelSelect").options]
    .find(item => item.value === String(modelId || "") && !item.disabled);
  if (!option) {
    effects.showNotice("That different 27B model is no longer available. Rescan models and try again.", true);
    return;
  }
  $("modelSelect").value = option.value;
  settingsPort.modelChanged();
  scheduleBenchmarkHistory();
  state.calibrationEntry = null;
  await loadCalibrationPlan(true);
  effects.showNotice(`Selected ${capabilities.selectedModel()?.name || "the different 27B model"}. This explicit choice changes the model; review its own qualification before testing.`);
}

async function prepareQwenRouteQualification() {
  const preparation = state.calibrationPlan?.qualificationPreparation;
  const settings = preparation?.settings;
  if (
    preparation?.kind !== "qwen-ple-safe-qualification-v1"
    || preparation.applicable !== true
    || preparation.resolvesVisibleSettings !== true
    || preparation.doesNotChangeMacOS !== true
    || !settings || calibrationOperationBlocked()
  ) return;
  if (String(preparation.modelId || "") !== String(capabilities.selectedModel()?.id || "")) {
    effects.showNotice("The selected Qwen artifact changed. Reopen Route Qualification.", true);
    return;
  }
  if (settings.backend !== "omlx" || state.backend !== "omlx") {
    effects.showNotice("This preparation is bound to the visible oMLX route.", true);
    return;
  }
  const optionValues = settings.options || {};
  const selectTargets = [
    ["accelerationSelect", optionValues.acceleration],
    ["burstSelect", optionValues.burst],
    ["anePrefillSelect", optionValues.anePrefill],
    ["memoryGuardSelect", optionValues.memoryGuard],
    ["reasoningSelect", settings.reasoning],
    ["calibrationCoolingSelect", settings.calibrationCooling],
  ];
  const invalid = selectTargets.find(([id, value]) =>
    ![...$(id).options].some(item => item.value === String(value) && !item.disabled)
  );
  if (invalid || !Number.isInteger(settings.context) || !Number.isInteger(settings.output)) {
    effects.showNotice("The safe qualification controls are no longer available. Refresh models and try again.", true);
    return;
  }
  if (!settingsPort.setRuntimeKvValue("omlx", optionValues.kv)) {
    effects.showNotice("The full-precision KV route is no longer available.", true);
    return;
  }

  settingsPort.cancelOptimization("Prepared the explicit Qwen qualification settings.");
  $("contextInput").value = String(settings.context);
  $("outputInput").value = String(settings.output);
  $("depthInput").value = String(optionValues.depth);
  for (const [id, value] of selectTargets) $(id).value = String(value);
  settingsPort.setRangeVisual($("depthInput"), $("depthValue"));
  settingsPort.updateAccelerationState();
  settingsPort.resetSessionAcknowledgement();
  settingsPort.refreshLaunchability();
  settingsPort.persistVisibleRoute();
  scheduleBenchmarkHistory();
  receiptPort.schedulePerformanceReceipt();

  const next = await loadCalibrationPlan(true);
  const admission = next?.memoryAdmission || next?.qualificationPreparation?.nextAdmission;
  const remaining = admission?.decision === "system-setting"
    ? ` ${admission.label}: ${admission.detail}` : "";
  effects.showNotice(`Safe Qwen test settings prepared. macOS was not changed.${remaining}`);
}

async function startCalibration() {
  let plan = state.calibrationPlan;
  if (completedCalibrationDecision() && plan?.action !== "apply-existing") {
    promoteCompletedCalibrationResult();
    renderCalibration();
    return;
  }
  if (!plan?.ready || !["measure", "apply-existing"].includes(plan.action) || calibrationOperationBlocked()) return;
  let expectedRequestSignature = "";
  try { expectedRequestSignature = JSON.stringify(calibrationPlanRequest()); }
  catch (error) {
    calibrationError=String(error.message || "Calibration could not be started.").slice(0,2048);
    $("calibrationStatus").textContent = calibrationError;
    effects.showNotice(calibrationError, true);
    return;
  }
  calibrationError="";
  state.calibrationStarting = true;
  $("calibrationStatus").textContent = plan.routeQualification
    ? "Submitting this exact route qualification…"
    : "Submitting this exact engine comparison…";
  settingsPort.refreshLaunchability();
  renderCalibration();
  try {
    if (plan.routeQualification) {
      // Qualification capacity is stricter than ordinary launch admission and
      // may change with memory pressure or the exact Metal limit. Refresh its
      // own plan immediately before any model-loading request.
      plan = await loadCalibrationPlan(false);
      if (!plan) return;
      const admission = calibrationMeasurementAdmission(plan || {});
      if (!admission.actionReady) {
        const blocker = operations.sessionAdmissionBlockerCopy(admission);
        $("calibrationStatus").textContent = blocker;
        effects.showNotice(blocker, true);
        return;
      }
    } else if (!await operations.requireFreshSessionAdmission()) {
      renderCalibration();
      return;
    }
    if (
      !plan?.ready
      || !["measure", "apply-existing"].includes(plan.action)
      || !routeQualificationContractExact(plan)
      || JSON.stringify(calibrationPlanRequest()) !== expectedRequestSignature
    ) {
      $("calibrationStatus").textContent = "The route changed while it was being checked. Review the current plan before testing.";
      return;
    }
    const request = calibrationPlanRequest();
    request.scope = "engines";
    if (plan.routeQualification) request.scope = "qualification";
    const data = await api("/api/benchmark/start", {method:"POST", body:JSON.stringify(request)});
    statusEpoch+=1;
    benchmarkError="";
    state.calibrationJobId = data.benchmark.id;
    state.calibrationCompletionId = "";
    state.benchmarkPhase = "queued";
    const engines = Object.fromEntries((data.benchmark.engines || [])
      .filter(engine => capabilities.uiEngineVisible(engine.backend))
      .map(engine => [engine.backend, {...engine, phase:"queued", modes:{}, record:null}]));
    renderBenchmarkStatus({
      phase:"queued", progress:0,
      message:plan.routeQualification
        ? calibrationQualificationProfile(plan).startMessage
        : `Calibration accepted. Preparing ${formatting.backendName(data.benchmark.executionOrder?.[0])} first in this rotated run…`,
      job:data.benchmark, modes:{}, engines,
    });
  } catch (error) {
    calibrationError=String(error.message || "Calibration could not be started.").slice(0,2048);
    $("calibrationStatus").textContent = calibrationError;
    effects.showNotice(calibrationError, true);
  } finally {
    state.calibrationStarting = false;
    settingsPort.refreshLaunchability();
    renderCalibration();
  }
}

async function stopCalibration() {
  if (!calibrationOwnsBenchmark() || !calibrationBenchmarkActive()) return;
  await stopBenchmark();
}

function calibrationRouteEvidenceApplyReady(plan = state.calibrationPlan || {}) {
  if (plan.routeQualification !== true) return true;
  const qualification = calibrationQualificationProfile(plan);
  const exactContract = qualification.uzu
    ? uzuQualificationContractExact(plan)
    : qualification.llama ? llamaQualificationContractExact(plan) : true;
  return exactContract
    && plan.evidence?.qualified === true
    && Boolean(plan.evidence?.evidenceBinding);
}

async function applyCalibrationResult(saveProfile = false) {
  const plan = state.calibrationPlan;
  if (!plan || plan.action !== "apply-existing" || calibrationOperationBlocked()) return;
  const routeQualification = plan.routeQualification === true;
  const evidenceBinding = evidence.copiedEvidenceBinding(plan.evidence?.evidenceBinding);
  const expectedScope = routeQualification ? "route" : "engine";
  if (
    !evidenceBinding
    || evidenceBinding.scope !== expectedScope
    || evidenceBinding.preference !== plan.preference
  ) {
    $("calibrationStatus").textContent = "The saved result has no usable exact apply reference. Refresh Calibration before applying it.";
    return;
  }
  if (routeQualification && !calibrationRouteEvidenceApplyReady(plan)) {
    $("calibrationStatus").textContent = "The exact qualified route and its immutable apply reference are no longer available. Refresh Calibration before applying.";
    return;
  }
  const reasoningContract = plan.reasoningContract || {};
  const previousReasoning = $("reasoningSelect").value;
  const previousCooling = $("fanSelect").value;
  const previousContext = $("contextInput").value;
  let reasoningChanged = false;
  let coolingChanged = false;
  let contextChanged = false;
  let routeApplied = false;
  const name = $("calibrationProfileName").value.trim();
  if (saveProfile && !name) {
    $("calibrationStatus").textContent = "Give the Quick Launch profile a name before saving it.";
    return;
  }
  calibrationError="";
  state.calibrationApplying = true;
  renderCalibration();
  $("calibrationStatus").textContent = plan.routeQualification
    ? "Rechecking the immutable qualification and applying this exact route…"
    : "Rechecking and applying the measured engine decision to the visible controls…";
  try {
    const measuredContext = Number(plan.request?.context);
    if (Number.isInteger(measuredContext) && measuredContext > 0 && String(measuredContext) !== previousContext) {
      $("contextInput").value = String(measuredContext);
      contextChanged = true;
      settingsPort.refreshLaunchability();
    }
    if (reasoningContract.normalized === true) {
      const measured = String(reasoningContract.measured || "auto");
      const option = [...$("reasoningSelect").options].find(item => item.value === measured);
      if (!option) throw new Error("The qualified reasoning setting is no longer available.");
      $("reasoningSelect").value = measured;
      reasoningChanged = measured !== previousReasoning;
      settingsPort.refreshLaunchability();
    }
    const measuredCooling = String(plan.calibrationCooling || "smart");
    const coolingOption = [...$("fanSelect").options].find(item => item.value === measuredCooling);
    if (!coolingOption) throw new Error("The calibrated cooling setting is no longer available.");
    $("fanSelect").value = measuredCooling;
    coolingChanged = measuredCooling !== previousCooling;
    const applyScope = plan.routeQualification ? "current" : "engine";
    if (!evidenceBinding) {
      throw new Error("The saved result has no exact apply reference. Refresh Calibration before applying it.");
    }
    const applied = await evidence.applyOptimal(
      applyScope, plan.preference, false, evidenceBinding,
    );
    if (!applied) throw new Error("The measured decision no longer matches the visible contract, so nothing was saved.");
    routeApplied = true;
    if (saveProfile) {
      const appliedBinding = evidence.activeEvidenceBindingFor(
        applyScope === "engine" ? "engine" : "route", plan.preference,
      );
      if (!appliedBinding) {
        throw new Error("The applied result no longer has a reusable reference. Refresh Calibration before saving it.");
      }
      const data = await api("/api/profiles/save", {
        method:"POST",
        body:JSON.stringify({
          name, enginePolicy:"measured", enginePreference:plan.preference,
          request:settingsPort.gather("custom"),
          evidenceBinding:appliedBinding,
        }),
      });
      effects.useProfileInventory(data);
      effects.showNotice(`Applied ${state.optimalLabel || "the calibrated route"}${reasoningChanged ? ` at ${plan.routeQualification ? reasoningContract.measured : "model-default"} reasoning` : ""}${contextChanged ? ` at ${formatting.formatNumber(measuredContext)} context` : ""} and saved “${name}” as an auto-measured Quick Launch profile.`);
    } else {
      const contextNote = contextChanged ? ` Context is now ${formatting.formatNumber(measuredContext)}, the common fixed SSD window shown in Calibration.` : "";
      effects.showNotice((plan.routeQualification && calibrationQualificationProfile(plan).llama
        ? `Applied the qualified llama.cpp SSD PLE route at fixed 8K with runtime-controlled reasoning and the exact 44 GiB qualification ceiling.`
        : plan.routeQualification && calibrationQualificationProfile(plan).uzu
          ? `Applied the qualified Uzu DFlash + Weaver route at exact ${formatting.exactContextTier(measuredContext)} with runtime-fixed BF16 KV.`
        : reasoningChanged
        ? plan.routeQualification
          ? `Applied ${state.optimalLabel || "the qualified route"}. Reasoning changed from ${previousReasoning} to ${reasoningContract.measured} so the route matches its completed qualification; cooling is ${plan.calibrationCoolingLabel || "Automatic"}.`
          : `Applied ${state.optimalLabel || "the calibrated route"}. Reasoning changed from ${previousReasoning} to model default so the measured engine result remains like-for-like; cooling is ${plan.calibrationCoolingLabel || "Automatic"}.`
        : `Applied ${state.optimalLabel || "the calibrated route"} with ${plan.calibrationCoolingLabel || "Automatic"} cooling. Model, response limit, reasoning, sampling, and KV precision were preserved.`) + contextNote);
    }
    if ($("calibrationDialog").open) $("calibrationDialog").close();
  } catch (error) {
    if (reasoningChanged && !routeApplied) {
      $("reasoningSelect").value = previousReasoning;
      settingsPort.refreshLaunchability();
    }
    if (coolingChanged && !routeApplied) {
      $("fanSelect").value = previousCooling;
      settingsPort.refreshLaunchability();
    }
    if (contextChanged && !routeApplied) {
      $("contextInput").value = previousContext;
      settingsPort.refreshLaunchability();
    }
    calibrationError=String(error.message || "The measured result could not be applied.").slice(0,2048);
    $("calibrationStatus").textContent = calibrationError;
    effects.showNotice(calibrationError, true);
  } finally {
    state.calibrationApplying = false;
    settingsPort.refreshLaunchability();
    if ($("calibrationDialog").open) renderCalibration();
  }
}

function completedCalibrationMatchesOptimizerChoice(scope, preference) {
  const plan = state.calibrationPlan;
  const binding = evidence.copiedEvidenceBinding(plan?.evidence?.evidenceBinding);
  const modelId = String(plan?.model?.id || plan?.request?.modelId || "");
  return scope === "engine"
    && plan?.action === "apply-existing"
    && plan.routeQualification !== true
    && plan.preference === preference
    && binding?.scope === "engine"
    && binding.preference === preference
    && Boolean(modelId)
    && modelId === String(capabilities.selectedModel()?.id || "")
    && (!plan.request?.client || plan.request.client === state.client);
}
  function initialize(){
   if(initialized)return;initialized=true;
   pollTask=polling.register({interval:()=>polling.interval(calibrationBenchmarkActive(),nodes.benchmarkDialog.open),
    run:async()=>{const epoch=statusEpoch;try{const status=await network.status();if(epoch===statusEpoch)renderBenchmarkStatus(status);}catch(_error){}}});
$("homeCompareEngines").addEventListener("click", () => $("openCalibrationAssistant").click());
$("openBenchmarkButton").addEventListener("click", openBenchmarkLab);
$("benchmarkSuiteSelect").addEventListener("change", benchmarkSuiteChanged);
$("benchmarkPreferenceSelect").addEventListener("change", benchmarkPreferenceChanged);
$("benchmarkStartButton").addEventListener("click", () => startBenchmark("current"));
$("benchmarkShootoutButton").addEventListener("click", () => startBenchmark("engines"));
$("benchmarkMtpTuneButton").addEventListener("click", () => startBenchmark("mtp-tune"));
$("benchmarkDflashTuneButton").addEventListener("click", () => startBenchmark("dflash-tune"));
$("benchmarkStopButton").addEventListener("click", stopBenchmark);
$("benchmarkHistoryRerun").addEventListener("click", () => startBenchmark("engines"));
$("benchmarkHistoryRetry").addEventListener("click", () => loadBenchmarkHistory(true));
$("benchmarkHistoryRuns").addEventListener("click", event => {
  const button = event.target.closest("[data-review-benchmark]");
  if (button && !button.disabled) void reviewBenchmarkResult(button.dataset.reviewBenchmark, button.dataset.reviewSuite);
});
$("benchmarkResults").addEventListener("click", event => {
  if (event.target.closest("[data-apply-benchmark-route]")) {
    void applyBenchmarkRouteResult();
    return;
  }
  if (!event.target.closest("[data-apply-shootout]")) return;
  const preference = $("benchmarkPreferenceSelect").value;
  const result = state.benchmarkStatus?.result?.kind === "engine-shootout"
    ? state.benchmarkStatus.result : null;
  const profile = result?.profiles?.[preference] || result?.decision || null;
  const evidenceBinding = engineShootoutApplyBinding(result, profile, preference);
  if (!evidenceBinding) {
    effects.showNotice("That measured result has no exact apply reference. Refresh it before applying.", true);
    return;
  }
  void evidence.applyOptimal("engine", preference, false, evidenceBinding);
});
$("openCalibrationAssistant").addEventListener("click", () => openCalibrationAssistant());
$("calibrationDetailToggle").addEventListener("click", () => {
  state.calibrationDetailsOpen = !state.calibrationDetailsOpen;
  renderCalibration();
});
$("calibrationEngineCards").addEventListener("click", event => {
  const button = event.target.closest("[data-calibration-model]");
  if (button && !button.disabled) void selectCalibrationAlternative(button.dataset.calibrationModel);
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
$("calibrationStartButton").addEventListener("click", () => {
  if ($("calibrationStartButton").dataset.action === "prepare") {
    void prepareQwenRouteQualification();
  } else if (["recheck-limit", "recheck-conflict"].includes($("calibrationStartButton").dataset.action)) {
    void loadCalibrationPlan(true);
  } else void startCalibration();
});
$("calibrationStopButton").addEventListener("click", stopCalibration);
$("calibrationApplyButton").addEventListener("click", () => applyCalibrationResult(false));
$("calibrationSaveButton").addEventListener("click", () => applyCalibrationResult(true));
  }
  const methods={benchmarkCandidates,engineShootoutRoutes,benchmarkWinnerLabel,renderBenchmarkCard,renderBenchmarkSetup,benchmarkHistoryRequest,benchmarkHistoryRequestKey,benchmarkHistoryDate,benchmarkHistorySparkline,renderBenchmarkHistory,loadBenchmarkHistory,scheduleBenchmarkHistory,benchmarkDisplayedStatus,reviewBenchmarkResult,calibrationSuiteControlValue,openPerformanceBenchmarkLab,benchmarkSuiteChanged,benchmarkPreferenceChanged,engineShootoutApplyBinding,renderEngineShootoutResults,renderMtpTuningResults,renderDflashTuningResults,benchmarkRouteApplyBinding,applyBenchmarkRouteResult,benchmarkResultRecommendation,renderBenchmarkResults,renderBenchmarkLiveTps,renderBenchmarkStatus,openBenchmarkLab,startBenchmark,stopBenchmark,calibrationBenchmarkActive,calibrationOwnsBenchmark,calibrationOperationBlocked,calibrationMeasurementAdmission,calibrationQualificationProfile,llamaQualificationContractExact,uzuQualificationContractExact,routeQualificationContractExact,firstQualificationMetric,firstQualificationCheck,routeQualificationResultMetrics,routeQualificationFactsMarkup,updateCalibrationHelp,calibrationPlanRequest,calibrationStateBadge,renderCalibrationEntry,completedCalibrationDecision,completedCalibrationEvidenceBinding,promoteCompletedCalibrationResult,calibrationParityRejectionNote,calibrationRoutePreview,calibrationAlternativeMarkup,renderCalibrationPlan,renderCalibrationBenchmark,renderCalibration,loadCalibrationPlan,openCalibrationAssistant,selectCalibrationAlternative,prepareQwenRouteQualification,startCalibration,stopCalibration,calibrationRouteEvidenceApplyReady,applyCalibrationResult,completedCalibrationMatchesOptimizerChoice,pollBenchmarkStatus,initialize};
  methods.benchmarkDisplayedStatus=status=>structuredClone(benchmarkDisplayedStatus(status));
  methods.completedCalibrationDecision=status=>structuredClone(completedCalibrationDecision(status));
  methods.calibrationMeasurementAdmission=plan=>structuredClone(calibrationMeasurementAdmission(plan));
  methods.loadCalibrationPlan=async resetJob=>structuredClone(await loadCalibrationPlan(resetJob));
  methods.renderBenchmarkStatus=status=>renderBenchmarkStatus(structuredClone(status));
  methods.view=()=>Object.freeze({phase:state.benchmarkPhase,message:String(state.benchmarkStatus?.message || ""),calibrationApplying:state.calibrationApplying,
   calibrationStarting:state.calibrationStarting,loading:state.calibrationLoading,historyLoading:state.benchmarkHistoryLoading,
   hasPlan:Boolean(state.calibrationPlan),calibrationError,benchmarkError,hasHistory:Boolean(state.benchmarkHistory),historyError:state.benchmarkHistoryError});
  methods.status=()=>structuredClone(state.benchmarkStatus);
  return Object.freeze(methods);
 }
 return Object.freeze({createController,nodeIds:Object.freeze(["accelerationSelect","anePrefillSelect","benchmarkCardBadge","benchmarkCardModes","benchmarkCardSummary","benchmarkContract","benchmarkDflashTuneButton","benchmarkDflashTuner","benchmarkDflashTunerSummary","benchmarkDialog","benchmarkEngineStrip","benchmarkFairness","benchmarkHistoryBadge","benchmarkHistoryFreshness","benchmarkHistoryOther","benchmarkHistoryPanel","benchmarkHistoryRerun","benchmarkHistoryRetry","benchmarkHistoryRuns","benchmarkHistoryTrend","benchmarkLiveTps","benchmarkModes","benchmarkMtpTuneButton","benchmarkMtpTuner","benchmarkMtpTunerSummary","benchmarkPercent","benchmarkPhase","benchmarkPreferenceHelp","benchmarkPreferenceSelect","benchmarkProgressBar","benchmarkResults","benchmarkRoute","benchmarkSafetyCopy","benchmarkScenarioStrip","benchmarkShootoutButton","benchmarkShootoutLabel","benchmarkStartButton","benchmarkStartLabel","benchmarkStatus","benchmarkStopButton","benchmarkSuiteHelp","benchmarkSuiteSelect","burstSelect","calibrationApplyButton","calibrationBadge","calibrationConsent","calibrationConsentCopy","calibrationConsentPanel","calibrationContract","calibrationContractState","calibrationCoolingHelp","calibrationCoolingSelect","calibrationDetailToggle","calibrationDialog","calibrationDialogSubtitle","calibrationDialogTitle","calibrationEngineCards","calibrationEngineState","calibrationEnginesTitle","calibrationEvidence","calibrationEvidenceState","calibrationLiveTps","calibrationOrigin","calibrationOriginDetail","calibrationOriginTitle","calibrationPercent","calibrationPhase","calibrationPlanFacts","calibrationPreferenceHelp","calibrationPreferenceLabel","calibrationPreferenceSelect","calibrationProfileName","calibrationProfilePanel","calibrationProgressBar","calibrationResults","calibrationSaveButton","calibrationStartButton","calibrationStartLabel","calibrationStatus","calibrationStopButton","calibrationSuiteHelp","calibrationSuiteSelect","contextInput","depthInput","depthValue","dflashDraftQuantSelect","dflashVerifySelect","fanSelect","homeCompareEngines","memoryGuardSelect","modelSelect","mtpMinContinueProbabilityInput","mtpMinTokensInput","openBenchmarkButton","openCalibrationAssistant","outputInput","profileSelect","reasoningSelect","samplingMode"]),policyKeys:Object.freeze(["LLAMACPP_PLE_QUALIFICATION_ANSWER_RESERVE_TOKENS","LLAMACPP_PLE_QUALIFICATION_CONTEXT","LLAMACPP_PLE_QUALIFICATION_CONTRACT_ID","LLAMACPP_PLE_QUALIFICATION_CONTRACT_VERSION","LLAMACPP_PLE_QUALIFICATION_MEMORY_LIMIT_BYTES","LLAMACPP_PLE_QUALIFICATION_MINIMUM_COMPLETION_TOKENS","LLAMACPP_PLE_QUALIFICATION_MINIMUM_TPS","LLAMACPP_PLE_QUALIFICATION_REASONING_BOUNDARY_ID","LLAMACPP_PLE_QUALIFICATION_REASONING_MESSAGE_SHA256","LLAMACPP_PLE_QUALIFICATION_SAMPLE_MAX_TOKENS","LLAMACPP_PLE_QUALIFICATION_SCENARIOS","LLAMACPP_PLE_QUALIFICATION_SUITE","LLAMACPP_PLE_QUALIFICATION_THINKING_TOKENS","MTPLX_LONG_CONTEXT_SUITE","UZU_NATIVE_BOUNDARY_CONTRACT_ID","UZU_QUALIFICATION_ANSWER_RESERVE_TOKENS","UZU_QUALIFICATION_CONTEXTS","UZU_QUALIFICATION_CONTRACT_VERSION","UZU_QUALIFICATION_MEMORY_LIMIT_BYTES","UZU_QUALIFICATION_MINIMUM_COMPLETION_TOKENS","UZU_QUALIFICATION_MINIMUM_TPS","UZU_QUALIFICATION_OS_RESERVE_MINIMUM_BYTES","UZU_QUALIFICATION_SAMPLE_MAX_TOKENS","UZU_QUALIFICATION_SAMPLE_MIN_TOKENS","UZU_QUALIFICATION_SCENARIOS","UZU_RUNTIME_RELEASE_BINARY_SHA256","UZU_RUNTIME_RELEASE_BINARY_SIZE","UZU_RUNTIME_SOURCE_PATCH_SHA256","UZU_RUNTIME_UPSTREAM_COMMIT"])});
});
