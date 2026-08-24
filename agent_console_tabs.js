(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.LLMAgentConsoleTabs = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const VERSION = 1;
  const MAX_TABS = 12;
  const MAX_QUERY = 200;
  const MAX_MATCHES = 500;
  const ID_PATTERN = /^[a-zA-Z0-9][a-zA-Z0-9-]{0,79}$/;

  const safeId = value => {
    const id = typeof value === "string" ? value : "";
    return ID_PATTERN.test(id) ? id : "";
  };

  const safeOffset = value => {
    if (typeof value === "boolean") return 0;
    const parsed = Number(value);
    return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : 0;
  };

  function allowedSurfaceIds(values) {
    const result = [];
    const seen = new Set();
    for (const value of Array.isArray(values) ? values : []) {
      const id = safeId(value);
      if (!id || seen.has(id)) continue;
      seen.add(id);
      result.push(id);
      if (result.length >= MAX_TABS) break;
    }
    return result;
  }

  function normalizeRecovery(value, ownerRunId, surfaceIds) {
    const owner = safeId(ownerRunId);
    const allowed = allowedSurfaceIds(surfaceIds);
    const allowedSet = new Set(allowed);
    const fallback = {
      version:VERSION, valid:false, ownerRunId:owner,
      activeSurfaceId:"", visible:false, seen:{},
    };
    if (
      !owner || !value || typeof value !== "object"
      || value.version !== VERSION || safeId(value.ownerRunId) !== owner
    ) return fallback;
    const seen = {};
    if (value.seen && typeof value.seen === "object" && !Array.isArray(value.seen)) {
      for (const id of allowed) {
        if (Object.prototype.hasOwnProperty.call(value.seen, id)) {
          seen[id] = safeOffset(value.seen[id]);
        }
      }
    }
    const active = safeId(value.activeSurfaceId);
    return {
      version:VERSION,
      valid:true,
      ownerRunId:owner,
      activeSurfaceId:allowedSet.has(active) ? active : "",
      visible:value.visible === true,
      seen,
    };
  }

  function buildRecovery(ownerRunId, activeSurfaceId, visible, seenOffsets, surfaceIds) {
    const owner = safeId(ownerRunId);
    const allowed = allowedSurfaceIds(surfaceIds);
    const allowedSet = new Set(allowed);
    const active = safeId(activeSurfaceId);
    const seen = {};
    for (const id of allowed) {
      const value = seenOffsets && typeof seenOffsets === "object" ? seenOffsets[id] : 0;
      seen[id] = safeOffset(value);
    }
    return {
      version:VERSION,
      ownerRunId:owner,
      activeSurfaceId:allowedSet.has(active) ? active : "",
      visible:visible === true,
      seen,
    };
  }

  function findMatches(value, rawQuery, limit = MAX_MATCHES) {
    const text = String(value || "");
    const query = String(rawQuery || "").slice(0, MAX_QUERY);
    const maximum = Math.max(1, Math.min(MAX_MATCHES, Number(limit) || MAX_MATCHES));
    if (!query) return {query:"", ranges:[], truncated:false};
    const haystack = text.toLocaleLowerCase();
    const needle = query.toLocaleLowerCase();
    if (!needle) return {query, ranges:[], truncated:false};
    const ranges = [];
    let offset = 0;
    let truncated = false;
    while (offset <= haystack.length - needle.length) {
      const start = haystack.indexOf(needle, offset);
      if (start < 0) break;
      if (ranges.length >= maximum) {
        truncated = true;
        break;
      }
      ranges.push({start, end:start + needle.length});
      offset = start + Math.max(1, needle.length);
    }
    return {query, ranges, truncated};
  }

  function nextMatchIndex(current, count, direction = 1) {
    const total = Math.max(0, Number(count) || 0);
    if (!total) return -1;
    const index = Number.isInteger(current) ? current : -1;
    return ((index + (direction < 0 ? -1 : 1)) % total + total) % total;
  }

  function tabPresentation(value = {}) {
    const attachment = value.attachment && typeof value.attachment === "object" ? value.attachment : {};
    const consoleRecord = value.consoleRecord && typeof value.consoleRecord === "object" ? value.consoleRecord : {};
    const activity = value.activity && typeof value.activity === "object" ? value.activity : {};
    const state = String(consoleRecord.state || attachment.status || "starting");
    const end = safeOffset(
      consoleRecord.bufferEnd ?? consoleRecord.outputRevision ?? consoleRecord.nextOffset,
    );
    const seenEnd = safeOffset(value.seenEnd);
    const unreadBytes = Math.max(0, end - seenEnd);
    const requestState = String(activity.state || "");
    let label;
    let tone;
    if (requestState === "queued" || requestState === "cancelling") {
      const position = Math.max(1, Number(activity.queuePosition) || 1);
      label = requestState === "cancelling" ? "Cancelling" : `Queue #${position}`;
      tone = "queued";
    } else if (requestState === "running") {
      label = "Generating";
      tone = "generating";
    } else if (unreadBytes > 0 && value.active !== true) {
      label = "New output";
      tone = "unread";
    } else if (state === "running") {
      label = "Ready";
      tone = "running";
    } else if (state === "starting") {
      label = "Starting";
      tone = "starting";
    } else if (state === "stopping") {
      label = "Stopping";
      tone = "stopping";
    } else if (state === "failed") {
      label = "Failed";
      tone = "failed";
    } else if (state === "exited") {
      label = "Exited";
      tone = "stopped";
    } else {
      label = "Stopped";
      tone = "stopped";
    }
    return {state, end, seenEnd, unreadBytes, unread:unreadBytes > 0, label, tone};
  }

  return {
    VERSION, MAX_TABS, MAX_QUERY, MAX_MATCHES,
    safeId, safeOffset, allowedSurfaceIds,
    normalizeRecovery, buildRecovery,
    findMatches, nextMatchIndex, tabPresentation,
  };
});
