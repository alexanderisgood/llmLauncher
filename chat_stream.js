(function installChatStream(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LLMChatStreamCore = api;
})(typeof globalThis === "object" ? globalThis : this, function chatStreamFactory() {
  "use strict";

  const RESPONSE_LIMIT_REASONS = new Set([
    "length",
    "max_tokens",
    "max_output_tokens",
    "max_completion_tokens",
    "token_limit",
  ]);

  function normaliseReason(value) {
    if (typeof value !== "string" || value.length > 80) return "";
    return value.trim().toLocaleLowerCase().replace(/[\s-]+/g, "_");
  }

  function responseLimitReason(event) {
    if (!event || typeof event !== "object" || Array.isArray(event)) return "";
    const choice = Array.isArray(event.choices) ? event.choices[0] : null;
    const response = event.response && typeof event.response === "object" && !Array.isArray(event.response)
      ? event.response : null;
    const candidates = [
      choice?.finish_reason,
      choice?.finishReason,
      event.finish_reason,
      event.finishReason,
      event.stop_reason,
      event.stopReason,
      event.incomplete_details?.reason,
      event.incompleteDetails?.reason,
      response?.incomplete_details?.reason,
      response?.incompleteDetails?.reason,
    ];
    for (const candidate of candidates) {
      const reason = normaliseReason(candidate);
      if (RESPONSE_LIMIT_REASONS.has(reason)) return reason;
    }
    return "";
  }

  function responseLimitReached(event) {
    return Boolean(responseLimitReason(event));
  }

  return Object.freeze({
    responseLimitReached,
    responseLimitReason,
  });
});
