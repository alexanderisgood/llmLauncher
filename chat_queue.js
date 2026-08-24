(function installChatQueue(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LLMChatQueueCore = api;
})(typeof globalThis === "object" ? globalThis : this, function chatQueueFactory() {
  "use strict";

  const VERSION = 1;
  const DEFAULTS = Object.freeze({
    maximumQueues:20,
    maximumMessages:32,
    maximumMessageCharacters:1_000_000,
    maximumQueueCharacters:1_000_000,
    maximumTotalCharacters:1_000_000,
    maximumKeyCharacters:240,
  });

  function optionsWithDefaults(options = {}) {
    return {
      maximumQueues:Math.max(1, Number(options.maximumQueues || DEFAULTS.maximumQueues)),
      maximumMessages:Math.max(1, Number(options.maximumMessages || DEFAULTS.maximumMessages)),
      maximumMessageCharacters:Math.max(1, Number(options.maximumMessageCharacters || DEFAULTS.maximumMessageCharacters)),
      maximumQueueCharacters:Math.max(1, Number(options.maximumQueueCharacters || DEFAULTS.maximumQueueCharacters)),
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
    return {version:VERSION, queues:{}};
  }

  function normaliseItems(items, options = {}, updatedAt = 0) {
    const limits = optionsWithDefaults(options);
    if (!Array.isArray(items)) return [];
    const result = [];
    const identifiers = new Set();
    let characters = 0;
    for (let index = 0; index < items.length && result.length < limits.maximumMessages; index += 1) {
      const item = items[index];
      if (!item || typeof item !== "object" || typeof item.content !== "string") continue;
      if (!item.content.trim() || item.content.includes("\u0000")) continue;
      if (item.content.length > limits.maximumMessageCharacters) continue;
      if (characters + item.content.length > limits.maximumQueueCharacters) break;
      const candidate = typeof item.id === "string" && /^[a-z0-9._:-]{1,160}$/i.test(item.id)
        ? item.id : `recovered-${Math.floor(Number(updatedAt || 0))}-${index}`;
      const id = identifiers.has(candidate) ? `${candidate}-${index}`.slice(0, 160) : candidate;
      identifiers.add(id);
      result.push({id, content:item.content});
      characters += item.content.length;
    }
    return result;
  }

  function normaliseEnvelope(value, options = {}) {
    const limits = optionsWithDefaults(options);
    const envelope = emptyEnvelope();
    if (!value || typeof value !== "object" || value.version !== VERSION) return envelope;
    const candidates = Object.entries(value.queues && typeof value.queues === "object" ? value.queues : {})
      .filter(([key, queue]) => validKey(key, limits) && queue && typeof queue === "object")
      .map(([key, queue]) => {
        const updatedAt = Number.isFinite(Number(queue.updatedAt)) ? Math.max(0, Number(queue.updatedAt)) : 0;
        return {key, updatedAt, items:normaliseItems(queue.items, limits, updatedAt)};
      })
      .filter(queue => queue.items.length)
      .sort((left, right) => right.updatedAt - left.updatedAt);
    let totalCharacters = 0;
    for (const queue of candidates) {
      if (Object.keys(envelope.queues).length >= limits.maximumQueues) break;
      const queueCharacters = queue.items.reduce((total, item) => total + item.content.length, 0);
      if (totalCharacters + queueCharacters > limits.maximumTotalCharacters) continue;
      envelope.queues[queue.key] = {items:queue.items, updatedAt:queue.updatedAt};
      totalCharacters += queueCharacters;
    }
    return envelope;
  }

  function readQueue(envelope, key, options = {}) {
    if (!validKey(key, options)) return [];
    const queue = normaliseEnvelope(envelope, options).queues[key];
    return queue ? queue.items.map(item => ({...item})) : [];
  }

  function writeQueue(envelope, key, items, updatedAt = Date.now(), options = {}) {
    const limits = optionsWithDefaults(options);
    if (!validKey(key, limits)) return normaliseEnvelope(envelope, limits);
    const next = normaliseEnvelope(envelope, limits);
    const timestamp = Number.isFinite(Number(updatedAt)) ? Math.max(0, Number(updatedAt)) : Date.now();
    const clean = normaliseItems(items, limits, timestamp);
    if (clean.length) next.queues[key] = {items:clean, updatedAt:timestamp};
    else delete next.queues[key];
    return normaliseEnvelope(next, limits);
  }

  function removeQueue(envelope, key, options = {}) {
    const next = normaliseEnvelope(envelope, options);
    if (validKey(key, options)) delete next.queues[key];
    return next;
  }

  function moveQueue(envelope, fromKey, toKey, updatedAt = Date.now(), options = {}) {
    const limits = optionsWithDefaults(options);
    const next = normaliseEnvelope(envelope, limits);
    if (!validKey(toKey, limits)) return next;
    const source = validKey(fromKey, limits) ? next.queues[fromKey] : null;
    if (source) {
      next.queues[toKey] = {
        items:source.items.map(item => ({...item})),
        updatedAt:Number.isFinite(Number(updatedAt)) ? Math.max(0, Number(updatedAt)) : Date.now(),
      };
      if (fromKey !== toKey) delete next.queues[fromKey];
    }
    return normaliseEnvelope(next, limits);
  }

  return Object.freeze({
    VERSION,
    DEFAULTS,
    emptyEnvelope,
    normaliseEnvelope,
    readQueue,
    writeQueue,
    removeQueue,
    moveQueue,
  });
});
