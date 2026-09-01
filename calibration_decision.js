"use strict";

(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.CalibrationDecision = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function backendLabel(decision = {}) {
    return String(decision.backendLabel || decision.label || decision.backend || "selected engine");
  }

  function summary(decision = {}) {
    const label = backendLabel(decision);
    if (decision.qualified === true || decision.evidenceTier === "local-route-qualification") {
      return `${label} route qualified`;
    }
    if (decision.trusted === true || decision.trustedWinner === true) return `${label} is fastest`;
    if (decision.engineChanged === true) return `Leading engines tied — use ${label}`;
    return `No clear winner — keep ${label}`;
  }

  function applyLabel(decision = {}) {
    if (decision.qualified === true || decision.tier === "local-route-qualification") {
      return `Use qualified route · ${backendLabel(decision)}`;
    }
    return `Apply result · ${backendLabel(decision)}`;
  }

  function resultBadge(decision = {}, engine = {}, index = 0) {
    const selected = String(engine.backend || "") === String(decision.backend || "");
    if (selected && (decision.qualified === true || decision.evidenceTier === "local-route-qualification")) {
      return "Qualified";
    }
    if (selected && (decision.trusted === true || decision.trustedWinner === true)) return "Best result";
    if (selected && decision.engineChanged === true) return "Recommended";
    if (selected) return "Kept · within 3%";
    if (engine.leading === true) return "Tied leader";
    return `#${Number(index) + 1}`;
  }

  function receiptSuite(client, qwenPleQualification = false) {
    if (qwenPleQualification === true) return "agentic";
    return ["pi", "opencode", "codex"].includes(String(client || ""))
      ? "agentic" : "standard";
  }

  return {backendLabel, summary, applyLabel, receiptSuite, resultBadge};
});
