(function installChatScroll(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LLMChatScrollCore = api;
})(typeof globalThis === "object" ? globalThis : this, function chatScrollFactory() {
  "use strict";

  const FOLLOW_THRESHOLD = 72;

  function finiteNumber(value, fallback = 0) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function normaliseMetrics(metrics = {}) {
    const scrollHeight = Math.max(0, finiteNumber(metrics.scrollHeight));
    const clientHeight = Math.max(0, finiteNumber(metrics.clientHeight));
    const maximumTop = Math.max(0, scrollHeight - clientHeight);
    const scrollTop = Math.min(maximumTop, Math.max(0, finiteNumber(metrics.scrollTop)));
    return {scrollHeight, clientHeight, scrollTop, maximumTop};
  }

  function nearBottom(metrics, threshold = FOLLOW_THRESHOLD) {
    const clean = normaliseMetrics(metrics);
    const margin = Math.max(0, finiteNumber(threshold, FOLLOW_THRESHOLD));
    return clean.maximumTop - clean.scrollTop <= margin;
  }

  function restoredTop(metrics, previousTop = 0) {
    const clean = normaliseMetrics(metrics);
    return Math.min(clean.maximumTop, Math.max(0, finiteNumber(previousTop)));
  }

  function captureScroll(metrics, threshold = FOLLOW_THRESHOLD) {
    const clean = normaliseMetrics(metrics);
    const margin = Math.max(0, finiteNumber(threshold, FOLLOW_THRESHOLD));
    return {
      scrollTop:clean.scrollTop,
      follow:clean.maximumTop - clean.scrollTop <= margin,
    };
  }

  function restoredCapturedTop(metrics, capture, followIfMissing = false) {
    const clean = normaliseMetrics(metrics);
    if (!capture || typeof capture !== "object") {
      return followIfMissing ? clean.maximumTop : clean.scrollTop;
    }
    return capture.follow === true
      ? clean.maximumTop
      : restoredTop(clean, capture.scrollTop);
  }

  function renderAction({
    forceBottom = false,
    shouldFollow = false,
    capturedInteractionRevision = 0,
    currentInteractionRevision = 0,
    capturedRenderRevision = 0,
    currentRenderRevision = 0,
  } = {}) {
    if (capturedRenderRevision !== currentRenderRevision) return "stale";
    if (!forceBottom && capturedInteractionRevision !== currentInteractionRevision) {
      return "preserve-user";
    }
    return forceBottom || shouldFollow ? "follow" : "restore";
  }

  function queuedTurnShouldFollow(followOutput, metrics) {
    return followOutput === true && nearBottom(metrics);
  }

  return Object.freeze({
    FOLLOW_THRESHOLD,
    captureScroll,
    nearBottom,
    normaliseMetrics,
    queuedTurnShouldFollow,
    renderAction,
    restoredCapturedTop,
    restoredTop,
  });
});
