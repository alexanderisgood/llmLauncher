(function installChatTranscript(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LLMChatTranscriptCore = api;
})(typeof globalThis === "object" ? globalThis : this, function chatTranscriptFactory() {
  "use strict";

  const MAX_QUERY_CHARACTERS = 160;
  const MAX_MESSAGES = 512;
  const MAX_RESULTS = 512;

  function normaliseText(value) {
    const text = String(value ?? "").slice(0, 2_000_000);
    let normalised = text;
    try { normalised = text.normalize("NFKC"); } catch (_error) { /* Keep the original text. */ }
    return normalised.toLocaleLowerCase().replace(/\s+/g, " ").trim();
  }

  function normaliseQuery(value) {
    return normaliseText(String(value ?? "").slice(0, MAX_QUERY_CHARACTERS));
  }

  function safeMessageId(message, index) {
    const value = typeof message?.id === "string" ? message.id.slice(0, 256) : "";
    return value || `message-${index + 1}`;
  }

  function searchMessages(messages, query) {
    const needle = normaliseQuery(query);
    if (!needle || !Array.isArray(messages)) return [];
    const matches = [];
    messages.slice(0, MAX_MESSAGES).forEach((message, index) => {
      if (!message || typeof message !== "object" || matches.length >= MAX_RESULTS) return;
      const fields = [];
      if (normaliseText(message.content).includes(needle)) fields.push("content");
      if (normaliseText(message.reasoning).includes(needle)) fields.push("reasoning");
      if (!fields.length) return;
      matches.push(Object.freeze({
        id:safeMessageId(message, index),
        index,
        role:message.role === "assistant" ? "assistant" : "user",
        fields:Object.freeze(fields),
      }));
    });
    return matches;
  }

  function turnLandmarks(messages) {
    if (!Array.isArray(messages)) return [];
    let turn = 0;
    return messages.slice(0, MAX_MESSAGES).filter(message => message && typeof message === "object")
      .map((message, index) => {
        const role = message.role === "assistant" ? "assistant" : "user";
        if (role === "user") turn += 1;
        const assignedTurn = Math.max(1, turn);
        return Object.freeze({
          id:safeMessageId(message, index),
          index,
          role,
          turn:assignedTurn,
          label:role === "user" ? `Turn ${assignedTurn}` : `Reply ${assignedTurn}`,
        });
      });
  }

  function nextMatchIndex(currentIndex, direction, count) {
    const length = Math.max(0, Math.floor(Number(count) || 0));
    if (!length) return -1;
    const delta = Number(direction) < 0 ? -1 : 1;
    const current = Number.isInteger(currentIndex) && currentIndex >= 0 && currentIndex < length
      ? currentIndex : (delta < 0 ? 0 : -1);
    return (current + delta + length) % length;
  }

  return Object.freeze({
    MAX_MESSAGES,
    MAX_QUERY_CHARACTERS,
    MAX_RESULTS,
    nextMatchIndex,
    normaliseQuery,
    searchMessages,
    turnLandmarks,
  });
});
