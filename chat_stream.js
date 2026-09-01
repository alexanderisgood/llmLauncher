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
  const CLEAN_TERMINAL_REASONS = new Set(["stop", "completed", "complete", "success", "succeeded"]);
  const FAILED_TERMINAL_REASONS = new Set([
    "error", "failed", "failure", "incomplete", "content_filter", "tool_calls", "function_call",
  ]);
  const ABORTED_TERMINAL_REASONS = new Set(["abort", "aborted", "cancel", "cancelled", "canceled"]);
  const TERMINAL_STATE_PRIORITY = Object.freeze({clean:1, limited:2, aborted:3, failed:4});

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

  function responseTerminalState(event) {
    if (!event || typeof event !== "object" || Array.isArray(event)) return "";
    const choice = Array.isArray(event.choices) ? event.choices[0] : null;
    const response = event.response && typeof event.response === "object" && !Array.isArray(event.response)
      ? event.response : null;
    if (event.error || response?.error) return "failed";
    let state = responseLimitReached(event) ? "limited" : "";

    const eventType = String(event.type || "").trim().toLocaleLowerCase()
      .replace(/[.\s-]+/g, "_");
    if (["response_failed", "error"].includes(eventType)) {
      state = mergeResponseTerminalState(state, "failed");
    } else if (eventType === "response_incomplete" && state !== "limited") {
      state = mergeResponseTerminalState(state, "failed");
    } else if (["response_cancelled", "response_canceled"].includes(eventType)) {
      state = mergeResponseTerminalState(state, "aborted");
    } else if (eventType === "response_completed") {
      state = mergeResponseTerminalState(state, "clean");
    }

    const candidates = [
      choice?.finish_reason,
      choice?.finishReason,
      event.finish_reason,
      event.finishReason,
      event.stop_reason,
      event.stopReason,
      event.status,
      response?.status,
    ];
    for (const candidate of candidates) {
      const reason = normaliseReason(candidate);
      if (!reason) continue;
      if (ABORTED_TERMINAL_REASONS.has(reason)) {
        state = mergeResponseTerminalState(state, "aborted");
      } else if (FAILED_TERMINAL_REASONS.has(reason) && !(reason === "incomplete" && state === "limited")) {
        state = mergeResponseTerminalState(state, "failed");
      } else if (CLEAN_TERMINAL_REASONS.has(reason)) {
        state = mergeResponseTerminalState(state, "clean");
      }
    }
    return state;
  }

  function mergeResponseTerminalState(current, next) {
    const left = Object.hasOwn(TERMINAL_STATE_PRIORITY, current) ? current : "";
    const right = Object.hasOwn(TERMINAL_STATE_PRIORITY, next) ? next : "";
    if (!right) return left;
    if (!left) return right;
    return TERMINAL_STATE_PRIORITY[right] >= TERMINAL_STATE_PRIORITY[left] ? right : left;
  }

  function finalResponseTerminalState(state, doneSeen = false) {
    if (Object.hasOwn(TERMINAL_STATE_PRIORITY, state)) return state;
    // [DONE] is framing, not semantic proof that the model completed. Require
    // an explicit finish reason or Responses terminal event before advancing a queue.
    return "unexpected-eof";
  }

  function responseTerminalFailure(event) {
    if (!event || typeof event !== "object" || Array.isArray(event)) return "";
    const response = event.response && typeof event.response === "object" && !Array.isArray(event.response)
      ? event.response : null;
    const candidates = [
      event.error?.message,
      typeof event.error === "string" ? event.error : "",
      response?.error?.message,
      typeof response?.error === "string" ? response.error : "",
    ];
    for (const candidate of candidates) {
      if (typeof candidate !== "string") continue;
      const text = candidate.replace(/\0/g, "").trim();
      if (text) return text.slice(0, 800);
    }
    return "";
  }

  function responseTerminalMessage(state, event = null) {
    const detail = responseTerminalFailure(event);
    if (detail) return detail;
    if (state === "aborted") return "The model aborted generation before returning a clean completion.";
    if (state === "failed") return "The model reported that generation failed before returning a clean completion.";
    if (state === "unexpected-eof") return "The model stream ended before reporting a clean completion.";
    return "";
  }

  function contentText(value) {
    if (typeof value === "string") return value;
    if (Array.isArray(value)) return value.map(contentText).join("");
    if (!value || typeof value !== "object") return "";
    for (const key of ["text", "content", "thinking", "reasoning_content", "reasoning", "delta"]) {
      if (typeof value[key] === "string") return value[key];
      if (Array.isArray(value[key])) return contentText(value[key]);
    }
    return "";
  }

  function partitionContent(value) {
    const parts = Array.isArray(value) ? value : [value];
    let text = "";
    let reasoning = "";
    for (const part of parts) {
      const kind = String(part?.type || "").toLocaleLowerCase();
      const content = contentText(part);
      if (kind.includes("reasoning") || kind.includes("thinking")) reasoning += content;
      else text += content;
    }
    return {text, reasoning};
  }

  function eventParts(event) {
    if (event?.error) {
      throw new Error(event.error.message || event.error || "The model returned a streaming error.");
    }
    const choice = Array.isArray(event?.choices) ? event.choices[0] : null;
    const delta = choice?.delta && typeof choice.delta === "object"
      ? choice.delta
      : event?.delta && typeof event.delta === "object" ? event.delta : {};
    const message = choice?.message || event?.message || {};
    const content = partitionContent(
      delta.content ?? message.content ?? choice?.text ?? event?.content,
    );
    let explicitReasoning = contentText(
      delta.reasoning_content ?? delta.reasoning ?? delta.thinking
      ?? message.reasoning_content ?? message.reasoning ?? message.thinking
      ?? event?.reasoning_content ?? event?.reasoning ?? event?.thinking,
    );
    const eventType = String(event?.type || delta?.type || "").toLocaleLowerCase();
    if (!explicitReasoning && typeof event?.delta === "string"
      && (eventType.includes("reasoning") || eventType.includes("thinking"))) {
      explicitReasoning = event.delta;
    }
    const reasoning = explicitReasoning && explicitReasoning !== content.reasoning
      ? `${content.reasoning}${explicitReasoning}` : (explicitReasoning || content.reasoning);
    return {text:content.text, reasoning};
  }

  function hasFinalAnswer(value) {
    return typeof value?.content === "string" && Boolean(value.content.trim());
  }

  function messageContextCharacters(message) {
    if (!message || typeof message !== "object") return 0;
    const content = String(message.content || "");
    const reasoning = message.role === "assistant"
      ? String(message.reasoning || message.reasoning_content || "") : "";
    return content.length + reasoning.length;
  }

  function incompleteAnswerKind(message) {
    if (!message || message.role !== "assistant") return "";
    // A model can spend its entire allowance in exposed reasoning. Preserve
    // that as a continuable response-limit state even when answer text is empty.
    if (message.truncated) return "truncated";
    if (message.interrupted) {
      if (!hasFinalAnswer(message) && String(message.reasoning || "").trim()) {
        return "reasoning-only";
      }
      return "interrupted";
    }
    if (
      message.exclude && message.stopped && !message.interrupted
      && !message.truncated && hasFinalAnswer(message)
    ) return "failed";
    return "";
  }

  function incompleteRecoveryOperation(message) {
    return ["reasoning-only", "interrupted", "failed"].includes(incompleteAnswerKind(message))
      && message.continuation === true ? "continue" : "message";
  }

  function pausedQueueRecoveryAction(action, message, isActiveTail) {
    if (!isActiveTail) return false;
    const kind = incompleteAnswerKind(message);
    return (action === "retry" && ["reasoning-only", "interrupted", "failed"].includes(kind))
      || (action === "continue" && kind === "truncated");
  }

  function blocksIncompleteTailRecovery(message) {
    if (!message || message.pending) return false;
    if (incompleteAnswerKind(message)) return true;
    if (message.exclude && message.stopped) return false;
    return Boolean(message.content || message.reasoning || message.interrupted);
  }

  function shouldPersistHistoryMessage(message) {
    if (!message || typeof message !== "object" || message.pending) return false;
    if (message.content || message.interrupted) return true;
    return Boolean(message.truncated && String(message.reasoning || "").trim());
  }

  function shouldDrainQueue(outcome) {
    return String(outcome || "") === "complete";
  }

  function createSseDataParser(onData) {
    if (typeof onData !== "function") throw new TypeError("An SSE data callback is required.");
    let buffer = "";
    let dataLines = [];
    let dataSeen = false;
    let doneSeen = false;

    const dispatch = () => {
      if (!dataLines.length) return;
      const data = dataLines.join("\n");
      dataLines = [];
      if (!data.trim()) return;
      if (data.trim() === "[DONE]") {
        doneSeen = true;
        return;
      }
      dataSeen = true;
      onData(data);
    };

    const consumeLine = line => {
      if (line === "") {
        dispatch();
        return;
      }
      if (line.startsWith(":")) return;
      const colon = line.indexOf(":");
      const field = colon < 0 ? line : line.slice(0, colon);
      if (field !== "data") return;
      let value = colon < 0 ? "" : line.slice(colon + 1);
      if (value.startsWith(" ")) value = value.slice(1);
      if (dataLines.length) {
        // A few local OpenAI-compatible servers omit SSE's blank event
        // separator. Preserve real multiline JSON, but recover when the
        // previous data field was already one complete JSON event.
        try {
          JSON.parse(dataLines.join("\n"));
          dispatch();
        } catch (_error) {}
      }
      dataLines.push(value);
    };

    const drain = (finishing = false) => {
      while (buffer) {
        let newline = -1;
        for (let index = 0; index < buffer.length; index += 1) {
          if (buffer[index] === "\n" || buffer[index] === "\r") {
            newline = index;
            break;
          }
        }
        if (newline < 0) break;
        if (!finishing && buffer[newline] === "\r" && newline === buffer.length - 1) break;
        const line = buffer.slice(0, newline);
        const width = buffer[newline] === "\r" && buffer[newline + 1] === "\n" ? 2 : 1;
        buffer = buffer.slice(newline + width);
        consumeLine(line);
      }
      if (finishing && buffer) {
        consumeLine(buffer);
        buffer = "";
      }
      if (finishing) dispatch();
    };

    return Object.freeze({
      push(chunk) {
        if (chunk) buffer += String(chunk);
        drain(false);
      },
      finish() { drain(true); },
      sawData() { return dataSeen; },
      sawDone() { return doneSeen; },
    });
  }

  return Object.freeze({
    blocksIncompleteTailRecovery,
    contentText,
    createSseDataParser,
    eventParts,
    finalResponseTerminalState,
    hasFinalAnswer,
    incompleteAnswerKind,
    incompleteRecoveryOperation,
    messageContextCharacters,
    partitionContent,
    pausedQueueRecoveryAction,
    mergeResponseTerminalState,
    responseLimitReached,
    responseLimitReason,
    responseTerminalFailure,
    responseTerminalMessage,
    responseTerminalState,
    shouldPersistHistoryMessage,
    shouldDrainQueue,
  });
});
