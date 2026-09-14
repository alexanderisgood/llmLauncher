(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.LLMPiTimelineCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const VERSION = 1;
  // Keep the browser-side materialized view inside the same limits as the
  // launcher-owned Pi event journal. Appended deltas must not bypass them.
  const MAX_ITEMS = 512;
  const MAX_ITEM_TEXT_BYTES = 64 * 1024;
  const MAX_TOTAL_TEXT_BYTES = 512 * 1024;
  const MAX_TITLE_BYTES = 512;
  const MAX_ITEM_ID_BYTES = 512;
  const KINDS = new Set([
    "user", "thinking", "answer", "toolCall", "toolResult", "notice", "error", "queue", "summary",
  ]);
  const OPERATIONS = new Set(["append", "replace"]);
  const utf8Encoder = new TextEncoder();
  const utf8Decoder = new TextDecoder("utf-8", {fatal:true});
  const itemBytes = new WeakMap();
  const normalizedStates = new WeakSet();

  function immutableState(value) {
    Object.freeze(value.items);
    normalizedStates.add(value);
    return Object.freeze(value);
  }

  function utf8ByteLength(value) {
    return utf8Encoder.encode(String(value || "")).byteLength;
  }

  function truncateUtf8(value, maximumBytes, keepTail = false) {
    const text = String(value || "");
    const limit = Math.max(0, Math.floor(Number(maximumBytes) || 0));
    const encoded = utf8Encoder.encode(text);
    if (encoded.byteLength <= limit) return text;
    if (!limit) return "";
    if (keepTail) {
      let start = encoded.byteLength - limit;
      while (start < encoded.byteLength && (encoded[start] & 0xc0) === 0x80) start += 1;
      return utf8Decoder.decode(encoded.subarray(start));
    }
    let end = limit;
    while (end > 0 && end < encoded.byteLength && (encoded[end] & 0xc0) === 0x80) end -= 1;
    return utf8Decoder.decode(encoded.subarray(0, end));
  }

  function boundItem(value) {
    if (value && itemBytes.has(value)) return value;
    const title = truncateUtf8(value?.title, Math.min(MAX_TITLE_BYTES, MAX_ITEM_TEXT_BYTES));
    const textBudget = Math.max(0, MAX_ITEM_TEXT_BYTES - utf8ByteLength(title));
    const item = Object.freeze({
      key:truncateUtf8(value?.key, MAX_ITEM_ID_BYTES),
      revision:safeRevision(value?.revision),
      kind:KINDS.has(value?.kind) ? value.kind : "notice",
      text:truncateUtf8(value?.text, textBudget, true),
      title,
      itemId:truncateUtf8(value?.itemId, MAX_ITEM_ID_BYTES),
      createdAt:normalizeTimestamp(value?.createdAt),
    });
    itemBytes.set(item, utf8ByteLength(item.text) + utf8ByteLength(title));
    return item;
  }

  function normalizeTimestamp(value) {
    if (typeof value !== "string" || !value || value.length > 48) return "";
    const date = new Date(value);
    return Number.isFinite(date.getTime()) ? date.toISOString() : "";
  }

  function itemTextBytes(value) {
    if (value && itemBytes.has(value)) return itemBytes.get(value);
    return utf8ByteLength(value?.text) + utf8ByteLength(value?.title);
  }

  function boundMaterializedItems(values) {
    // The launcher normally sends an already bounded journal, but keep this
    // client-side boundary independent of the payload size.  Slicing before
    // normalising avoids making a second large array when a stale/broken
    // provider returns an oversized envelope.
    const source = Array.isArray(values) ? values.slice(-MAX_ITEMS) : [];
    const items = source.map(boundItem);
    let totalBytes = items.reduce((total, item) => total + itemTextBytes(item), 0);
    let first = Math.max(0, items.length - MAX_ITEMS);
    for (let index = 0; index < first; index += 1) totalBytes -= itemTextBytes(items[index]);
    while (first < items.length && totalBytes > MAX_TOTAL_TEXT_BYTES) {
      totalBytes -= itemTextBytes(items[first]);
      first += 1;
    }
    return items.slice(first);
  }

  function safeRevision(value) {
    if (typeof value === "boolean") return 0;
    const parsed = Number(value);
    return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : 0;
  }

  function emptyTimeline() {
    return immutableState({
      version:VERSION,
      baseRevision:0,
      revision:0,
      availableRevision:0,
      items:[],
    });
  }

  function normalizeEvent(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return null;
    const revision = safeRevision(value.revision);
    const kind = typeof value.kind === "string" ? value.kind : "";
    if (!revision || !KINDS.has(kind) || typeof value.text !== "string") return null;
    const itemId = typeof value.itemId === "string" && value.itemId
      ? truncateUtf8(value.itemId, MAX_ITEM_ID_BYTES) : "";
    const operation = typeof value.operation === "string" && OPERATIONS.has(value.operation)
      ? value.operation : "";
    return {
      revision,
      kind,
      text:truncateUtf8(value.text, MAX_ITEM_TEXT_BYTES, true),
      title:typeof value.title === "string" ? truncateUtf8(value.title, MAX_TITLE_BYTES) : "",
      itemId,
      operation,
      createdAt:normalizeTimestamp(value.createdAt),
    };
  }

  function isLegacyPresentationNotice(value) {
    // Older running controllers mislabeled Pi's per-token UI updates as
    // notices. Filter before bounding so a browser refresh repairs a live
    // session without stopping its model or losing its conversation.
    return value?.kind === "notice" && value.title === "Pi notice"
      && String(value.itemId || "").startsWith("interaction:")
      && ["setStatus", "setWidget", "setTitle", "set_editor_text"].includes(value.text);
  }

  function thinkingIsOpen(key, expanded) {
    return expanded.has(key) ? expanded.get(key) === true : true;
  }

  function applyTimelineEnvelope(previousValue, envelopeValue) {
    const previous = previousValue && typeof previousValue === "object"
      ? previousValue : emptyTimeline();
    const envelope = envelopeValue && typeof envelopeValue === "object" ? envelopeValue : {};
    if (envelope.timelineVersion !== VERSION) {
      return {state:previous, supported:false, changed:false, reset:false, accepted:0};
    }

    const reset = envelope.timelineReset === true;
    const nextRevision = safeRevision(envelope.nextTimelineRevision);
    if (!reset && nextRevision < safeRevision(previous.revision)) {
      return {state:previous, supported:true, changed:false, reset:false, accepted:0, stale:true};
    }

    const baseRevision = safeRevision(envelope.timelineBaseRevision);
    const availableRevision = safeRevision(envelope.timelineRevision);
    const events = Array.isArray(envelope.timelineEvents) ? envelope.timelineEvents : [];
    const trusted = normalizedStates.has(previous);
    if (!reset && trusted && nextRevision === previous.revision
        && baseRevision === previous.baseRevision
        && Math.max(nextRevision, availableRevision) === previous.availableRevision
        && events.every(event => safeRevision(event?.revision) <= previous.revision)) {
      return {state:previous, supported:true, changed:false, reset:false, accepted:0, stale:false};
    }
    let items = reset
      ? []
      : trusted ? previous.items.slice()
      : (Array.isArray(previous.items)
        ? previous.items.filter(item => !isLegacyPresentationNotice(item)).map(boundItem) : []);
    const mutableById = new Map();
    items.forEach((item, index) => {
      if (item.itemId) mutableById.set(item.itemId, index);
    });
    let materializedBytes = items.reduce((total, item) => total + itemTextBytes(item), 0);

    const compactMaterializedItems = () => {
      // Keep the working set close to the rendered bound while processing a
      // large delta batch.  The small headroom avoids copying on every event;
      // the final bound below still enforces the exact public limits.
      if (items.length <= MAX_ITEMS * 2 && materializedBytes <= MAX_TOTAL_TEXT_BYTES * 2) return;
      items = boundMaterializedItems(items);
      materializedBytes = items.reduce((total, item) => total + itemTextBytes(item), 0);
      mutableById.clear();
      items.forEach((item, index) => {
        if (item.itemId) mutableById.set(item.itemId, index);
      });
    };

    let eventCursor = reset ? Math.max(0, baseRevision - 1) : safeRevision(previous.revision);
    let accepted = 0;
    for (const rawEvent of events) {
      const event = normalizeEvent(rawEvent);
      if (!event || event.revision <= eventCursor) continue;
      eventCursor = event.revision;
      accepted += 1;
      if (isLegacyPresentationNotice(event)) continue;
      const mutable = Boolean(event.itemId && event.operation);
      const existingIndex = mutable ? mutableById.get(event.itemId) : undefined;
      if (existingIndex !== undefined) {
        const existing = items[existingIndex];
        const replacement = boundItem({
          ...existing,
          text:event.operation === "replace" ? event.text : `${existing.text}${event.text}`,
          kind:event.kind,
          revision:event.revision,
          title:event.title || existing.title,
        });
        items[existingIndex] = replacement;
        materializedBytes += itemTextBytes(replacement) - itemTextBytes(existing);
        compactMaterializedItems();
        continue;
      }
      const item = boundItem({
        key:mutable ? `item:${event.itemId}` : `revision:${event.revision}`,
        revision:event.revision,
        kind:event.kind,
        text:event.text,
        title:event.title,
        createdAt:event.createdAt,
        itemId:mutable ? event.itemId : "",
      });
      items.push(item);
      materializedBytes += itemTextBytes(item);
      if (mutable) mutableById.set(event.itemId, items.length - 1);
      compactMaterializedItems();
    }

    const boundedItems = boundMaterializedItems(items);
    const revision = Math.max(eventCursor, nextRevision);
    const state = immutableState({
      version:VERSION,
      baseRevision,
      revision,
      availableRevision:Math.max(revision, availableRevision),
      items:boundedItems,
    });
    return {
      state,
      supported:true,
      changed:reset || accepted > 0 || revision !== safeRevision(previous.revision),
      reset,
      accepted,
      stale:false,
    };
  }

  function timelinePlainText(value) {
    const labels = {
      user:"You", thinking:"Thinking", answer:"Pi", toolCall:"Tool call",
      toolResult:"Tool result", notice:"Notice", error:"Error", queue:"Queue", summary:"Prompt summary",
    };
    return (Array.isArray(value?.items) ? value.items : []).map(item => {
      const label = String(item.title || labels[item.kind] || "Event");
      return `${label}\n${String(item.text || "")}`.trimEnd();
    }).filter(Boolean).join("\n\n");
  }

  function timelineAvailableRevision(value, metadata) {
    return Math.max(
      safeRevision(value?.revision),
      safeRevision(value?.availableRevision),
      safeRevision(metadata?.timelineRevision),
    );
  }

  function shouldUseTimeline(protocol, timelineLoaded) {
    return protocol === "pi-rpc" && timelineLoaded === true;
  }

  function shouldRenderTimeline(wasLoaded, result) {
    return Boolean(
      result?.supported === true
      && (wasLoaded !== true || result.changed === true || result.reset === true)
    );
  }

  function isNearBottom(metrics, threshold = 64) {
    const height = Math.max(0, Number(metrics?.scrollHeight) || 0);
    const top = Math.max(0, Number(metrics?.scrollTop) || 0);
    const viewport = Math.max(0, Number(metrics?.clientHeight) || 0);
    return height - top - viewport < Math.max(0, Number(threshold) || 0);
  }

  function restoredScrollTop(previousTop, wasNearBottom, nextScrollHeight) {
    return wasNearBottom
      ? Math.max(0, Number(nextScrollHeight) || 0)
      : Math.max(0, Number(previousTop) || 0);
  }

  function followTailAfterScroll(wasFollowing, previousTop, nextTop, nearBottom, intent = "") {
    const previous = Math.max(0, Number(previousTop) || 0);
    const next = Math.max(0, Number(nextTop) || 0);
    // Layout, card collapse, and browser scroll anchoring also emit scroll
    // events. Only a known user gesture may change the follow preference.
    if (intent === "up") return false;
    if ((intent === "down" || intent === "scrollbar") && nearBottom === true) return true;
    if (intent === "scrollbar" && next < previous - 1) return false;
    return wasFollowing !== false;
  }

  function anchoredScrollTop(previousTop, previousAnchorTop, nextAnchorTop) {
    const previous = Math.max(0, Number(previousTop) || 0);
    const before = Number(previousAnchorTop);
    const after = Number(nextAnchorTop);
    if (!Number.isFinite(before) || !Number.isFinite(after)) return previous;
    return Math.max(0, previous + after - before);
  }

  function toolIsActive(item) {
    return /^(Writing|Running) · /.test(item?.title || "");
  }

  function toolIsOpen(item, previous) {
    const active = toolIsActive(item);
    if (!previous || previous.active !== active) return active;
    return previous.open === true;
  }

  function toolDisplayText(item) {
    if (item?.kind !== "toolCall") return item?.text || "";
    try {
      const args = JSON.parse(item.text);
      if (!args || typeof args !== "object") return item.text;
      const path = args.path || args.file_path || "";
      if (typeof args.content === "string") return [path, args.content].filter(Boolean).join("\n\n");
      if (typeof args.newText === "string") return [path,
        ...(typeof args.oldText === "string" ? ["Before:\n" + args.oldText] : []),
        "After:\n" + args.newText].filter(Boolean).join("\n\n");
      if (typeof args.command === "string") return args.command;
    } catch { /* Historical and non-JSON tool output stays readable as text. */ }
    return item?.text || "";
  }

  function piTokenSpeed(metadata, now = Date.now()) {
    const status = metadata?.extensionStatuses?.tokenSpeed;
    const match = /(?:TPS:\s*)?([\d]+(?:\.[\d]+)?)\s*tok\/s/.exec(status?.text || "");
    if (!match) return null;
    const live = metadata.streaming === true && metadata.compacting !== true
      && now - Date.parse(status.updatedAt) < 5000;
    return {
      value:`${match[1]} tok/s · Pi ${live ? "live" : "last"}`,
      state:live ? "live" : "idle",
      title:`From your installed pi-token-speed extension. ${status.text}. Pi may estimate live tokens between provider usage reports.`,
    };
  }

  return {
    VERSION, MAX_ITEMS, MAX_ITEM_TEXT_BYTES, MAX_TOTAL_TEXT_BYTES,
    MAX_TITLE_BYTES, MAX_ITEM_ID_BYTES, KINDS,
    safeRevision, utf8ByteLength, truncateUtf8, itemTextBytes,
    boundItem, boundMaterializedItems, emptyTimeline, normalizeEvent,
    isLegacyPresentationNotice, thinkingIsOpen,
    toolIsActive, toolIsOpen, toolDisplayText, piTokenSpeed,
    applyTimelineEnvelope, timelinePlainText, timelineAvailableRevision,
    shouldUseTimeline, shouldRenderTimeline,
    isNearBottom, restoredScrollTop, followTailAfterScroll, anchoredScrollTop,
  };
});
