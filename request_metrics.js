(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LLMRequestMetrics = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function liveTelemetry(request) {
    const source = request?.liveTelemetry?.source;
    return request?.state === "running" && (source === "mtplx-flight" || source === "omlx-activity")
      ? request.liveTelemetry : null;
  }

  function phaseLabel(request, fallback) {
    const live = liveTelemetry(request);
    if (!live) return fallback(request);
    if (live.phase === "prefill") return "Reading context";
    const reasoning = typeof live.reasoningCharacters === "number" ? live.reasoningCharacters : 0;
    const content = typeof live.contentCharacters === "number" ? live.contentCharacters : 0;
    if (content > 0) return "Answering";
    if (reasoning > 0) return "Reasoning";
    return live.source === "omlx-activity" ? "Generating" : "Decoding";
  }

  function liveDetail(request, {formatNumber, formatShortDuration}) {
    const live = liveTelemetry(request);
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

  function completedDetail(request, finiteMetric) {
    if (!["lmstudio-response-stats", "slotstream-native-stats"].includes(request?.runtimeStatsSource)) return "";
    const acceptance = finiteMetric(request.speculativeAcceptancePercent);
    const parts = [];
    if (acceptance !== null && acceptance >= 0 && acceptance <= 100) {
      parts.push(`MTP ${acceptance.toFixed(acceptance < 10 ? 1 : 0)}% accepted`);
    }
    const cache = request.expertCache;
    if (request.runtimeStatsSource === "slotstream-native-stats" && cache) {
      const bytes = finiteMetric(cache.allocatedBytes);
      const hit = finiteMetric(cache.hitRatePercent);
      if (bytes !== null && bytes >= 0) parts.push(`${(bytes / 1e9).toFixed(1)} GB expert cache`);
      if (hit !== null && hit >= 0 && hit <= 100) parts.push(`${hit.toFixed(0)}% expert cache hits`);
    }
    return parts.join(" · ");
  }

  return {liveTelemetry, phaseLabel, liveDetail, completedDetail};
});
