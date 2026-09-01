(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LLMRoutePreferenceCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const STORAGE_KEY = "llm-launcher-route-v1";
  const VERSION = 1;
  const MAX_MODEL_ID = 2048;
  const BACKENDS = new Set([
    "mtplx", "omlx", "lmstudio", "freetoken", "swiftlm", "mference", "whallm", "llamacpp",
  ]);
  const CLIENTS = new Set(["pi", "opencode", "codex", "chat"]);
  const MIN_CONTEXT = 1024;
  const MIN_OUTPUT = 256;
  const MIN_PROMPT_BUDGET = 1024;

  function normaliseRoute(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return null;
    const backend = typeof value.backend === "string" ? value.backend.trim().toLowerCase() : "";
    const modelId = typeof value.modelId === "string" ? value.modelId.trim() : "";
    const client = typeof value.client === "string" ? value.client.trim().toLowerCase() : "";
    if (!BACKENDS.has(backend) || !CLIENTS.has(client) || !modelId || modelId.length > MAX_MODEL_ID) return null;
    return Object.freeze({backend, modelId, client});
  }

  function readRoute(storage) {
    try {
      const parsed = JSON.parse(storage?.getItem?.(STORAGE_KEY) || "null");
      if (!parsed || parsed.version !== VERSION) return null;
      return normaliseRoute(parsed);
    } catch (_error) {
      return null;
    }
  }

  function writeRoute(storage, value) {
    const route = normaliseRoute(value);
    if (!route) return {route:null, stored:false};
    try {
      storage?.setItem?.(STORAGE_KEY, JSON.stringify({version:VERSION, ...route}));
      return {route, stored:Boolean(storage?.setItem)};
    } catch (_error) {
      return {route, stored:false};
    }
  }

  function routeKey(value) {
    const route = normaliseRoute(value);
    return route ? `${route.backend}\u0000${route.modelId}\u0000${route.client}` : "";
  }

  function availableRoutes(values) {
    const routes = [];
    const seen = new Set();
    for (const value of Array.isArray(values) ? values : []) {
      const route = normaliseRoute(value);
      const key = routeKey(route);
      if (!route || seen.has(key)) continue;
      seen.add(key);
      routes.push(route);
    }
    return routes;
  }

  function isRouteAvailable(value, values) {
    const key = routeKey(value);
    return Boolean(key && availableRoutes(values).some(route => routeKey(route) === key));
  }

  function selectInitialRoute({preference = null, current = null, routes = []} = {}) {
    const available = availableRoutes(routes);
    if (!available.length) return null;
    const remembered = normaliseRoute(preference);
    const visible = normaliseRoute(current);
    if (remembered) {
      const exact = available.find(route => routeKey(route) === routeKey(remembered));
      if (exact) return Object.freeze({...exact, source:"remembered"});
    }
    if (visible) {
      const exact = available.find(route => routeKey(route) === routeKey(visible));
      if (exact) return Object.freeze({...exact, source:"current"});
      const sameModel = available.find(route => route.backend === visible.backend && route.modelId === visible.modelId);
      if (sameModel) return Object.freeze({...sameModel, source:"current-fallback"});
      const sameSurface = available.find(route => route.backend === visible.backend && route.client === visible.client);
      if (sameSurface) return Object.freeze({...sameSurface, source:"current-fallback"});
      const sameEngine = available.find(route => route.backend === visible.backend);
      if (sameEngine) return Object.freeze({...sameEngine, source:"current-fallback"});
    }
    return Object.freeze({...available[0], source:"available"});
  }

  function reconcileRuntimeLimits({context, output, contextWindows = []} = {}) {
    const requestedContext = Number(context);
    const requestedOutput = Number(output);
    const windows = [...new Set((Array.isArray(contextWindows) ? contextWindows : [])
      .map(Number)
      .filter(value => Number.isInteger(value) && value >= MIN_CONTEXT))]
      .sort((left, right) => left - right);
    let nextContext = requestedContext;
    if (
      windows.length
      && Number.isInteger(requestedContext)
      && !windows.includes(requestedContext)
    ) {
      nextContext = windows.filter(value => value <= requestedContext).at(-1) || windows[0];
    }
    let nextOutput = requestedOutput;
    const maximumOutput = Number.isInteger(nextContext)
      ? nextContext - MIN_PROMPT_BUDGET : Number.NaN;
    if (
      Number.isInteger(requestedOutput)
      && requestedOutput >= MIN_OUTPUT
      && Number.isInteger(maximumOutput)
      && maximumOutput >= MIN_OUTPUT
      && requestedOutput > maximumOutput
    ) nextOutput = maximumOutput;
    return Object.freeze({
      context:nextContext,
      output:nextOutput,
      contextChanged:nextContext !== requestedContext,
      outputChanged:nextOutput !== requestedOutput,
      promptBudget:Number.isInteger(nextContext) && Number.isInteger(nextOutput)
        ? nextContext - nextOutput : null,
    });
  }

  return Object.freeze({
    STORAGE_KEY, VERSION, MAX_MODEL_ID, MIN_CONTEXT, MIN_OUTPUT, MIN_PROMPT_BUDGET,
    normaliseRoute, readRoute, writeRoute, routeKey,
    availableRoutes, isRouteAvailable, selectInitialRoute, reconcileRuntimeLimits,
  });
});
