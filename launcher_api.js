(function(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.LLMLauncherApi = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function() {
  "use strict";

  const READ_POSTS = new Set([
    "/api/agent-console/read", "/api/session/plan", "/api/session/warm-plan",
    "/api/session/attachment-plan", "/api/preview", "/api/benchmark/history",
    "/api/calibration/plan",
  ]);

  function canReplayRead(path, options) {
    if (READ_POSTS.has(path)) return true;
    if (path !== "/api/hub/fans") return false;
    try {
      const body = JSON.parse(options.body || "{}");
      return body && typeof body === "object" && !Array.isArray(body)
        && !Object.prototype.hasOwnProperty.call(body, "mode");
    } catch { return false; }
  }

  function createClient({fetch, getToken, setToken}) {
    let refreshing = null;

    async function refresh(rejectedToken) {
      if (getToken() !== rejectedToken) return true;
      if (!refreshing) {
        refreshing = (async () => {
          const controller = new AbortController();
          const timeout = setTimeout(() => controller.abort(), 5000);
          try {
            const response = await fetch("/api/bootstrap", {cache:"no-store", signal:controller.signal});
            if (!response.ok) throw new Error("Controller unavailable");
            const boot = await response.json();
            if (typeof boot.token !== "string" || !boot.token) throw new Error("Missing controller token");
            // A newer bootstrap may have completed while this fetch was pending.
            if (getToken() === rejectedToken) setToken(boot.token);
          } finally { clearTimeout(timeout); }
        })().finally(() => { refreshing = null; });
      }
      await refreshing;
      return getToken() !== rejectedToken;
    }

    function throwIfAborted(signal) {
      if (signal?.aborted) throw signal.reason || new DOMException("Aborted", "AbortError");
    }

    async function response(path, options = {}) {
      const post = String(options.method || "GET").toUpperCase() === "POST";
      const headers = {...(options.headers || {})};
      const token = getToken();
      if (post) {
        headers["Content-Type"] = "application/json";
        headers["X-Launcher-Token"] = token;
      }
      let result = await fetch(path, {...options, headers});
      if (post && result.status === 403) {
        throwIfAborted(options.signal);
        let changed;
        try { changed = await refresh(token); }
        catch {
          throwIfAborted(options.signal);
          throw new Error("Could not reconnect to the launcher. Try again when it is running.");
        }
        throwIfAborted(options.signal);
        if (changed) {
          // Authentication was rejected before dispatch. Only read operations
          // can follow a new controller automatically: Stop/Launch/Send must
          // not be replayed against a possibly different active model route.
          if (!canReplayRead(path, options)) {
            throw new Error("Reconnected to the restarted launcher. This action was not sent; try again.");
          }
          headers["X-Launcher-Token"] = getToken();
          result = await fetch(path, {...options, headers});
        }
      }
      return result;
    }

    async function json(path, options = {}) {
      const result = await response(path, options);
      let data;
      try { data = await result.json(); }
      catch {
        throw new Error(result.status === 403
          ? "The launcher rejected this request. Check the active session and try again."
          : `The launcher returned an unreadable response (${result.status}). Try again.`);
      }
      if (!result.ok) throw new Error(data.error || `Request failed (${result.status})`);
      return data;
    }
    return {response, json};
  }

  return {createClient};
});
