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
    const decode = nonNegativeMetric(request.decodeTokensPerSecond);
    const endToEnd = nonNegativeMetric(request.endToEndTokensPerSecond);
    const runtimeSource = request.runtimeStatsSource;
    const runtimeMetric = runtimeSource === "lmstudio-response-stats"
      ? nonNegativeMetric(request.runtimeTokensPerSecond) : null;
    const runtime = runtimeMetric !== null && runtimeMetric > 0 ? runtimeMetric : null;
    const liveSource = request.liveTelemetry?.source;
    const knownLiveSource = liveSource === "mtplx-flight" || liveSource === "omlx-activity";
    const liveMetric = request.state === "running" && knownLiveSource
      ? nonNegativeMetric(request.liveTelemetry?.tokensPerSecond) : null;
    const live = liveMetric !== null && liveMetric > 0 ? liveMetric : null;
    if (decode === null && endToEnd === null && live === null && runtime === null) return null;
    if (runtime !== null) {
      return {
        decode, endToEnd, runtime,
        primary:runtime, primaryKind:"runtime",
        compact:`${runtime.toFixed(1)} tok/s engine`,
        label:`${runtime.toFixed(1)} tok/s · LM Studio reported`,
      };
    }
    if (decode === null && endToEnd === null) {
      const prefill = request.liveTelemetry?.metricKind === "prefill";
      const sourceLabel = liveSource === "omlx-activity"
        ? "oMLX activity telemetry" : "MTPLX flight telemetry";
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

  function activitySummary(report = {}, surfaceId = "") {
    const active = Array.isArray(report.active) ? report.active : [];
    const queued = Array.isArray(report.queued) ? report.queued : [];
    const recent = Array.isArray(report.recent) ? report.recent.slice(0, 32) : [];
    const current = [...active, ...queued].find(item => item?.surfaceId === surfaceId) || null;
    const latestRequest = recent.find(item => item?.surfaceId === surfaceId) || null;
    const latest = latestRequest && requestTps(latestRequest) ? latestRequest : null;
    const currentSpeed = requestTps(current);
    const lastSpeed = requestTps(latest);
    const displayedSpeed = currentSpeed || (!current ? lastSpeed : null);
    const speed = displayedSpeed ? {
      value:`${displayedSpeed.primary.toFixed(1)} tok/s`,
      state:"measured",
      title:`${currentSpeed ? "Current Chat request" : "Last completed Chat turn"}: ${displayedSpeed.label}`,
    } : current?.state === "running" ? {
      value:"Measuring…", state:"measuring",
      title:"TPS is waiting for authoritative runtime usage.",
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

  return Object.freeze({requestTps, activitySummary, cacheSummary, contextSummary});
});
