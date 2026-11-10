(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LLMChatStatusCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function nonNegativeMetric(value) {
    return typeof value === "number" && Number.isFinite(value) && value >= 0
      ? value : null;
  }

  function requestTps(request) {
    if (!request || typeof request !== "object") return null;
    const nativeRequired = ["kolibri", "splash"].includes(request.backend)
      || ["kolibri-native-stats", "splash-native-stats"].includes(request.runtimeStatsSource);
    const decode = nativeRequired ? null : nonNegativeMetric(request.decodeTokensPerSecond);
    const endToEnd = nonNegativeMetric(request.endToEndTokensPerSecond);
    const runtimeSource = request.runtimeStatsSource;
    const runtimeMetric = ["lmstudio-response-stats", "whallm-native-stats", "slotstream-native-stats", "omlx-native-stats", "kolibri-native-stats", "splash-native-stats"].includes(runtimeSource)
      ? nonNegativeMetric(request.runtimeTokensPerSecond) : null;
    const runtime = runtimeMetric !== null && runtimeMetric > 0 ? runtimeMetric : null;
    const liveSource = request.liveTelemetry?.source;
    const knownLiveSource = ["mtplx-flight", "omlx-activity", "whallm-native-stats"].includes(liveSource);
    const liveMetric = request.state === "running" && knownLiveSource
      ? nonNegativeMetric(request.liveTelemetry?.tokensPerSecond) : null;
    const live = liveMetric !== null && liveMetric > 0 ? liveMetric : null;
    if (decode === null && endToEnd === null && live === null && runtime === null) return null;
    if (runtime !== null) {
      return {
        decode, endToEnd, runtime,
        primary:runtime, primaryKind:"runtime",
        compact:`${runtime.toFixed(1)} tok/s engine`,
        label:`${runtime.toFixed(1)} tok/s · ${runtimeSource === "whallm-native-stats" ? "Whallm native decode, including cache evaluation" : runtimeSource === "slotstream-native-stats" ? "Slotstream native decode" : runtimeSource === "omlx-native-stats" ? "oMLX native decode" : runtimeSource === "kolibri-native-stats" ? "Kolibri native decode" : runtimeSource === "splash-native-stats" ? "Splash stream lifecycle, first native batch excluded" : "LM Studio reported"}`,
      };
    }
    if (decode === null && endToEnd === null) {
      const prefill = request.liveTelemetry?.metricKind === "prefill";
      const sourceLabel = liveSource === "omlx-activity" ? "oMLX activity telemetry"
        : liveSource === "whallm-native-stats" ? "Whallm native telemetry" : "MTPLX flight telemetry";
      return {
        decode:null, endToEnd:null, primary:live,
        primaryKind:prefill ? "live-prefill" : "live",
        compact:`${live.toFixed(1)} tok/s ${prefill ? "prefill" : "live"}`,
        label:`${live.toFixed(1)} tok/s ${prefill ? "live prefill" : "live"} · ${sourceLabel}`,
      };
    }
    return {
      decode,
      endToEnd,
      primary:decode ?? endToEnd,
      primaryKind:decode !== null ? "decode" : "end-to-end",
      compact:decode !== null && endToEnd !== null
        ? `${decode.toFixed(1)} decode · ${endToEnd.toFixed(1)} end-to-end`
        : decode !== null ? `${decode.toFixed(1)} tok/s decode`
          : `${endToEnd.toFixed(1)} tok/s end-to-end`,
      label:decode !== null && endToEnd !== null
        ? `${decode.toFixed(1)} tok/s decode · ${endToEnd.toFixed(1)} tok/s end-to-end`
        : decode !== null ? `${decode.toFixed(1)} tok/s decode`
          : `${endToEnd.toFixed(1)} tok/s end-to-end`,
    };
  }

  function agentGenerationSpeed(current, latest, piSpeed, fallback) {
    const nativeRequired = ["kolibri", "splash"].includes(current?.backend || latest?.backend)
      || ["kolibri-native-stats", "splash-native-stats"].includes((current || latest)?.runtimeStatsSource);
    const currentSpeed = requestTps(current);
    const latestSpeed = requestTps(latest);
    const isDecode = speed => speed && !["live-prefill", "end-to-end"].includes(speed.primaryKind);
    const prefill = current?.liveTelemetry?.phase === "prefill" || currentSpeed?.primaryKind === "live-prefill";
    const measured = !prefill && isDecode(currentSpeed) ? currentSpeed : null;
    if (measured) return {
      value:`${measured.primary.toFixed(1)} tok/s · engine`, state:"measured",
      title:`Current decode speed: ${measured.label}. Engine token counts take precedence over Pi's live estimate.`,
    };
    if (!nativeRequired && !prefill && current?.state === "running" && piSpeed?.state === "live") return {
      ...piSpeed, value:piSpeed.value.replace("Pi live", "Pi estimate"),
    };
    if (prefill && current?.liveTelemetry?.source === "whallm-native-stats") return {
      value:"Waiting…", state:"unknown", title:"Whallm is processing this prompt; decode has not started.",
    };
    if (isDecode(latestSpeed)) return {
      value:`${latestSpeed.primary.toFixed(1)} tok/s · last`, state:"measured",
      title:`Last completed decode speed: ${latestSpeed.label}. Prompt processing is shown separately.`,
    };
    if (!nativeRequired && !prefill && piSpeed) return {...piSpeed, value:piSpeed.value.replace("Pi live", "Pi estimate")};
    return prefill ? {value:"Waiting…", state:"unknown", title:"Prompt processing is shown separately."} : fallback;
  }

  function activitySummary(report = {}, surfaceId = "") {
    const active = Array.isArray(report.active) ? report.active : [];
    const queued = Array.isArray(report.queued) ? report.queued : [];
    const recent = Array.isArray(report.recent) ? report.recent.slice(0, 32) : [];
    const current = [...active, ...queued].find(item => item?.surfaceId === surfaceId) || null;
    const latestRequest = recent.find(item => item?.surfaceId === surfaceId) || null;
    const latest = latestRequest && requestTps(latestRequest) ? latestRequest : null;
    const currentSpeed = requestTps(current);
    const lastSpeed = requestTps(latest);
    const displayedSpeed = currentSpeed || lastSpeed;
    const speed = displayedSpeed ? {
      value:`${displayedSpeed.primary.toFixed(1)} tok/s${currentSpeed?.primaryKind === "live-prefill" ? " prefill" : !currentSpeed && current ? " · last" : ""}`,
      state:"measured",
      title:`${currentSpeed ? "Current model request" : "Last completed model request"}: ${displayedSpeed.label}${!currentSpeed && current ? ". Current speed will update when the engine reports token usage." : ""}`,
    } : current?.state === "running" ? {
      value:"Awaiting token count", state:"measuring",
      title:"This engine has not reported token usage for the current request yet. Speed appears when that count arrives.",
    } : !current && latestRequest?.usageReported === true
      && latestRequest?.tpsSampleQualified === false ? {
      value:"Too short", state:"unknown",
      title:`The last reply had ${Math.max(0, Number(latestRequest.completionTokens) || 0)} output tokens; at least ${Math.max(1, Number(latestRequest.tpsSampleMinimumTokens) || 16)} are required for stable TPS.`,
    } : report.engineResident ? {
      value:"Not reported", state:"unknown",
      title:"TPS appears only when the runtime reports authoritative token usage.",
    } : {
      value:"Unavailable", state:"unavailable",
      title:"No launcher-owned engine relay is available.",
    };
    const queuePosition = nonNegativeMetric(current?.queuePosition);
    const lane = current?.state === "running"
      ? {value:"Generating", state:"running"}
      : current
        ? {value:`Queue #${Math.max(1, Math.floor(queuePosition || 1))}`, state:"queued"}
        : active.length
          ? {value:"Other surface busy", state:"busy"}
          : report.engineResident
            ? {value:"Idle", state:"idle"}
            : {value:"Unavailable", state:"unavailable"};
    return {speed, lane};
  }

  function requestPhase(request) {
    if (!request) return "";
    if (request.state === "cancelling") return "Stopping…";
    if (request.state === "queued") return "Waiting for the model…";
    if (request.state !== "running") return "";
    const live = request.liveTelemetry;
    if (["mtplx-flight", "omlx-activity", "whallm-native-stats"].includes(live?.source)) {
      if (live.phase === "prefill") return "Prefilling · reading context…";
      if (live.contentCharacters > 0) return "Answering…";
      if (live.reasoningCharacters > 0) return "Thinking…";
      if (live.phase === "decode") return "Generating…";
    }
    // A relay can observe first output, but cannot distinguish engine prefill
    // from other startup work without runtime telemetry.
    return request.firstOutputAt || nonNegativeMetric(request.firstOutputSeconds) !== null
      ? "Generating…" : "Preparing prompt…";
  }

  function cacheSummary(report = {}) {
    const last = report.lastObservation && typeof report.lastObservation === "object"
      ? report.lastObservation : null;
    const promptTokens = nonNegativeMetric(last?.promptTokens);
    const reportedCachedTokens = nonNegativeMetric(last?.cachedPromptTokens);
    if (last?.cacheTelemetryReported === true && promptTokens > 0 && reportedCachedTokens !== null) {
      const cachedPromptTokens = Math.min(promptTokens, reportedCachedTokens);
      const percent = (cachedPromptTokens / promptTokens) * 100;
      return {
        value:cachedPromptTokens > 0
          ? `${percent.toFixed(percent < 10 ? 1 : 0)}% reused` : "No reuse",
        state:String(report.state || (cachedPromptTokens > 0 ? "confirmed-reuse" : "reported-no-reuse")),
      };
    }
    if (report.state === "telemetry-unavailable") {
      return {value:"Not reported", state:"telemetry-unavailable"};
    }
    if (report.state === "warming") return {value:"Warming", state:"warming"};
    return report.engineResident
      ? {value:"Waiting", state:String(report.state || "idle")}
      : {value:"Unavailable", state:"unavailable"};
  }

  function contextSummary(usage, context, reducedPending = false) {
    if (!usage || typeof usage !== "object") {
      return {warning:false, percent:null, label:""};
    }
    const promptTokens = nonNegativeMetric(usage.promptTokens);
    const contextTokens = nonNegativeMetric(context);
    const percent = promptTokens !== null && contextTokens > 0
      ? (promptTokens / contextTokens) * 100 : null;
    const warning = !reducedPending && percent !== null && percent >= 85;
    return {
      warning,
      percent,
      label:warning ? `Context ${Math.round(percent)}%` : "",
    };
  }

  function promptProcessingClock(request, now = Date.now()) {
    if (request?.state !== "running") return null;
    const phase = request.liveTelemetry?.phase;
    if (phase === "decode" || (phase !== "prefill" &&
        (request.firstOutputAt || nonNegativeMetric(request.firstOutputSeconds) !== null))) return null;
    const started = Date.parse(request.startedAt);
    if (!Number.isFinite(started)) return null;
    const seconds = Math.max(0, Math.floor((now - started) / 1000));
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  }

  function promptProcessingSummary(current, latest) {
    const live = current?.liveTelemetry;
    const rate = nonNegativeMetric(live?.tokensPerSecond);
    if (current?.state === "running" && live?.metricKind === "prefill"
        && ["omlx-activity", "mtplx-flight"].includes(live.source) && rate > 0) {
      return {value:`${rate.toFixed(1)} tok/s`, state:"measured",
        title:"Live prompt-processing speed reported by the engine (prefill)."};
    }
    for (const request of [current, latest]) {
      const stats = request?.promptProcessing;
      const speed = nonNegativeMetric(stats?.tokensPerSecond);
      const processed = nonNegativeMetric(stats?.processedTokens);
      const cached = nonNegativeMetric(stats?.cachedTokens);
      if (!["uzu-native-stats", "omlx-dflash-prefill", "mtplx-prefill", "whallm-prefill", "slotstream-native-stats", "omlx-native-stats", "kolibri-native-stats", "splash-native-stats"].includes(stats?.source) || speed === null || processed === null || cached === null) continue;
      if (stats.source === "whallm-prefill" && request === latest && current && current !== latest) continue;
      const engine = {"uzu-native-stats":"Uzu", "mtplx-prefill":"MTPLX", "whallm-prefill":"Whallm", "slotstream-native-stats":"Slotstream", "omlx-native-stats":"oMLX", "kolibri-native-stats":"Kolibri", "splash-native-stats":"Splash"}[stats.source] || "oMLX DFlash";
      const attribution = stats.source === "slotstream-native-stats"
        ? " Native prefill timing attached to this response; excludes decode and cached tokens."
        : stats.source === "splash-native-stats"
        ? " Native request-start to first-token timing, including request preparation."
        : stats.source === "kolibri-native-stats"
        ? " Native prompt evaluation attached to this request and checked against its final token usage."
        : stats.source === "whallm-prefill"
        ? " Native prompt-to-first-token measurement, matched by serial request counters and token counts."
        : " Matched to this request's native response ID and token counts.";
      return {value:`${speed.toFixed(1)} tok/s${request === latest ? " · last" : ""}`,
        state:"measured", title:`${engine} reported ${speed.toFixed(1)} tok/s processing ${processed.toLocaleString()} new prompt tokens; ${cached.toLocaleString()} cached tokens are excluded.${stats.partial ? " Latest observed prefill sample; final processing statistics are not available yet." : attribution}${request === latest ? " Last completed request." : ""}`};
    }
    return {value:current ? "Waiting…" : "Not reported", state:"unknown",
      title:"Waiting for the engine's actual prefill measurement. Total prompt tokens divided by time to first output is not prompt-processing speed, especially with cached context."};
  }

  function agentContextSummary(meta, contextWindow, current, latest) {
    if (meta?.compacting) return {value:"Compacting…", state:"measuring", title:"Pi is freeing conversation context."};
    let usage;
    try { usage = JSON.parse(meta?.extensionStatuses?.["launcher.context"]?.text); } catch {}
    if (usage?.source === "pi-context-estimate") {
      const tokens = nonNegativeMetric(usage.tokens);
      const capacity = nonNegativeMetric(usage.contextWindow);
      if (tokens === null || !(capacity > 0)) return {value:"Recalculating…", state:"unknown",
        title:"Pi has no reliable context count yet. After compaction it updates following the next model response; this does not mean zero usage."};
      const percent = tokens / capacity * 100;
      return {value:`~${percent.toFixed(1)}%`, state:percent >= 85 ? "busy" : "measured",
        usedTokens:tokens, totalTokens:capacity, remainingTokens:Math.max(0, capacity - tokens),
        title:`Pi context estimate: ${tokens.toLocaleString()} / ${capacity.toLocaleString()} tokens, including conversation and generated output. The response allowance is not counted as used context.`};
    }
    const live = current?.liveTelemetry;
    const capacity = nonNegativeMetric(contextWindow);
    let tokens = ["mtplx-flight", "omlx-activity", "whallm-native-stats"].includes(live?.source)
      ? nonNegativeMetric(live.contextTokens) : null;
    let last = false;
    if (tokens === null && latest?.usageReported === true) {
      const prompt = nonNegativeMetric(latest.promptTokens);
      const completion = nonNegativeMetric(latest.completionTokens);
      if (prompt !== null && completion !== null) { tokens = prompt + completion; last = true; }
    }
    if (tokens === null || !(capacity > 0)) return {value:"Not reported", state:"unknown",
      title:"Waiting for a context count from Pi or the engine."};
    const percent = tokens / capacity * 100;
    return {value:`${percent.toFixed(1)}%${last ? " · last" : ""}`, state:percent >= 85 ? "busy" : "measured",
      usedTokens:tokens, totalTokens:capacity, remainingTokens:Math.max(0, capacity - tokens),
      title:`${last ? "Last request" : "Current request"}: ${tokens.toLocaleString()} / ${capacity.toLocaleString()} context tokens, including prompt and output.`};
  }

  return Object.freeze({requestTps, requestPhase, activitySummary, agentGenerationSpeed, cacheSummary, contextSummary,
    promptProcessingSummary, promptProcessingClock, agentContextSummary});
});
