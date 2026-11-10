(function installAgentConsoleInput(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LLMAgentConsoleInputCore = api;
})(typeof globalThis === "object" ? globalThis : this, function agentConsoleInputFactory() {
  "use strict";

  const AGENT_CONSOLE_MAX_INPUT_BYTES = 64 * 1024;
  const PI_MESSAGE_ENVELOPE_BYTES = 256;
  const PI_MESSAGE_MAX_BYTES = AGENT_CONSOLE_MAX_INPUT_BYTES - PI_MESSAGE_ENVELOPE_BYTES;
  const TERMINAL_BATCH_CHARACTERS = 60_000;
  const utf8Encoder = new TextEncoder();

  function utf8ByteLength(value) {
    return utf8Encoder.encode(String(value ?? "")).byteLength;
  }

  function agentLabel(protocol = "pi-rpc") { return protocol === "omp-rpc" ? "oh-my-pi" : "Pi"; }

  function isStructuredProtocol(protocol) { return protocol === "pi-rpc" || protocol === "omp-rpc"; }

  function validatePiPrompt(value, label = "Pi") {
    const text = typeof value === "string" ? value : "";
    // Account for JSON escaping before accepting text into the local queue.
    const bytes = utf8ByteLength(JSON.stringify(text)) - 2;
    if (!text.trim()) {
      return {
        ok:false, bytes, maximumBytes:PI_MESSAGE_MAX_BYTES,
        error:`Enter a message for ${label}.`,
      };
    }
    if (bytes > PI_MESSAGE_MAX_BYTES) {
      return {
        ok:false, bytes, maximumBytes:PI_MESSAGE_MAX_BYTES,
        error:`This encoded ${label} message uses ${bytes.toLocaleString()} bytes. Keep it at or below ${PI_MESSAGE_MAX_BYTES.toLocaleString()} bytes; your text has not been cleared.`,
      };
    }
    return {ok:true, bytes, maximumBytes:PI_MESSAGE_MAX_BYTES, error:""};
  }

  function takeNextBatch(queue, maximumCharacters = TERMINAL_BATCH_CHARACTERS) {
    if (!Array.isArray(queue) || !queue.length) return null;
    const first = queue[0];
    if (first && typeof first === "object") {
      const item = queue.shift();
      return {items:[item], payload:item, structured:true};
    }
    const limit = Math.max(1, Math.floor(Number(maximumCharacters) || TERMINAL_BATCH_CHARACTERS));
    const items = [];
    let payload = "";
    while (queue.length && typeof queue[0] !== "object" && payload.length < limit) {
      const item = queue.shift();
      items.push(item);
      payload += String(item ?? "");
    }
    return items.length ? {items, payload, structured:false} : null;
  }

  function restoreFailedBatch(queue, batch) {
    if (!Array.isArray(queue) || !Array.isArray(batch?.items) || !batch.items.length) return queue;
    queue.unshift(...batch.items);
    return queue;
  }

  function isPiPrompt(value) {
    return Boolean(value && typeof value === "object" && value.command === "prompt");
  }

  function queuedPiPromptCount(queue) {
    return (Array.isArray(queue) ? queue : []).reduce(
      (count, item) => count + (isPiPrompt(item) ? 1 : 0),
      0,
    );
  }

  function visiblePiPendingMessages(serverPending, queue, inFlightPromptCount = 0) {
    return Math.max(0, Math.floor(Number(serverPending) || 0))
      + queuedPiPromptCount(queue)
      + Math.max(0, Math.floor(Number(inFlightPromptCount) || 0));
  }

  function discardQueuedPiPrompts(queue) {
    if (!Array.isArray(queue)) return 0;
    let removed = 0;
    for (let index = queue.length - 1; index >= 0; index -= 1) {
      if (!isPiPrompt(queue[index])) continue;
      queue.splice(index, 1);
      removed += 1;
    }
    return removed;
  }

  function piQueueEntries(meta, queue, inFlight = []) {
    const stored = (Array.isArray(meta?.queuedMessages) ? meta.queuedMessages : [])
      .filter(item => item && typeof item.message === "string")
      .map(item => ({message:item.message, label:item.kind === "steer" ? "Steering" : "Follow-up",
        source:"server", id:item.id, editable:item.editable === true}));
    const sending = (Array.isArray(inFlight) ? inFlight : []).filter(isPiPrompt)
      .map(item => ({message:item.message, label:"Sending…"}));
    const local = (Array.isArray(queue) ? queue : []).filter(isPiPrompt)
      .map(item => ({message:item.message, label:"Waiting to send", source:"local", localItem:item, editable:true}));
    return [...stored, ...sending, ...local];
  }

  return Object.freeze({
    AGENT_CONSOLE_MAX_INPUT_BYTES,
    PI_MESSAGE_ENVELOPE_BYTES,
    PI_MESSAGE_MAX_BYTES,
    TERMINAL_BATCH_CHARACTERS,
    utf8ByteLength,
    validatePiPrompt,
    agentLabel, isStructuredProtocol,
    takeNextBatch,
    restoreFailedBatch,
    isPiPrompt,
    queuedPiPromptCount,
    visiblePiPendingMessages,
    discardQueuedPiPrompts,
    piQueueEntries,
  });
});
