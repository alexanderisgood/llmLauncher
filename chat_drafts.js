(function installChatDrafts(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LLMChatDraftsCore = api;
})(typeof globalThis === "object" ? globalThis : this, function chatDraftsFactory() {
  "use strict";

  const VERSION = 1;
  const DEFAULTS = Object.freeze({
    maximumDrafts:20,
    maximumDraftCharacters:200_000,
    maximumTotalCharacters:400_000,
    maximumKeyCharacters:240,
  });

  function optionsWithDefaults(options = {}) {
    return {
      maximumDrafts:Math.max(1, Number(options.maximumDrafts || DEFAULTS.maximumDrafts)),
      maximumDraftCharacters:Math.max(1, Number(options.maximumDraftCharacters || DEFAULTS.maximumDraftCharacters)),
      maximumTotalCharacters:Math.max(1, Number(options.maximumTotalCharacters || DEFAULTS.maximumTotalCharacters)),
      maximumKeyCharacters:Math.max(16, Number(options.maximumKeyCharacters || DEFAULTS.maximumKeyCharacters)),
    };
  }

  function validKey(value, options = {}) {
    const limits = optionsWithDefaults(options);
    return typeof value === "string"
      && value.length > 0
      && value.length <= limits.maximumKeyCharacters
      && !/[\u0000-\u001f\u007f]/.test(value);
  }

  function emptyEnvelope() {
    return {version:VERSION, activeKey:"", drafts:{}};
  }

  function normaliseEnvelope(value, options = {}) {
    const limits = optionsWithDefaults(options);
    const envelope = emptyEnvelope();
    if (!value || typeof value !== "object" || value.version !== VERSION) return envelope;
    const candidates = Object.entries(value.drafts && typeof value.drafts === "object" ? value.drafts : {})
      .filter(([key, draft]) => (
        validKey(key, limits)
        && draft && typeof draft === "object"
        && typeof draft.text === "string"
        && draft.text.length > 0
        && draft.text.length <= limits.maximumDraftCharacters
      ))
      .map(([key, draft]) => ({
        key,
        text:draft.text,
        updatedAt:Number.isFinite(Number(draft.updatedAt)) ? Math.max(0, Number(draft.updatedAt)) : 0,
      }))
      .sort((left, right) => right.updatedAt - left.updatedAt);
    let total = 0;
    for (const draft of candidates) {
      if (Object.keys(envelope.drafts).length >= limits.maximumDrafts) break;
      if (total + draft.text.length > limits.maximumTotalCharacters) continue;
      envelope.drafts[draft.key] = {text:draft.text, updatedAt:draft.updatedAt};
      total += draft.text.length;
    }
    if (validKey(value.activeKey, limits)) envelope.activeKey = value.activeKey;
    return envelope;
  }

  function prune(envelope, options = {}) {
    return normaliseEnvelope(envelope, options);
  }

  function setActive(envelope, key, options = {}) {
    const next = normaliseEnvelope(envelope, options);
    next.activeKey = validKey(key, options) ? key : "";
    return next;
  }

  function readDraft(envelope, key, options = {}) {
    if (!validKey(key, options)) return "";
    return normaliseEnvelope(envelope, options).drafts[key]?.text || "";
  }

  function writeDraft(envelope, key, text, updatedAt = Date.now(), options = {}) {
    const limits = optionsWithDefaults(options);
    if (!validKey(key, limits)) return normaliseEnvelope(envelope, limits);
    const next = normaliseEnvelope(envelope, limits);
    const value = String(text || "");
    if (!value) delete next.drafts[key];
    else next.drafts[key] = {
      text:value.slice(0, limits.maximumDraftCharacters),
      updatedAt:Number.isFinite(Number(updatedAt)) ? Math.max(0, Number(updatedAt)) : Date.now(),
    };
    next.activeKey = key;
    return prune(next, limits);
  }

  function removeDraft(envelope, key, options = {}) {
    const next = normaliseEnvelope(envelope, options);
    if (validKey(key, options)) delete next.drafts[key];
    if (next.activeKey === key) next.activeKey = "";
    return next;
  }

  function moveDraft(envelope, fromKey, toKey, options = {}) {
    const next = normaliseEnvelope(envelope, options);
    if (!validKey(toKey, options)) return next;
    const source = validKey(fromKey, options) ? next.drafts[fromKey] : null;
    if (source) {
      next.drafts[toKey] = {...source};
      if (fromKey !== toKey) delete next.drafts[fromKey];
    }
    next.activeKey = toKey;
    return prune(next, options);
  }

  return Object.freeze({
    VERSION,
    DEFAULTS,
    emptyEnvelope,
    normaliseEnvelope,
    setActive,
    readDraft,
    writeDraft,
    removeDraft,
    moveDraft,
  });
});
