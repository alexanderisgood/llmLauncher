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
    "mtplx", "omlx", "lmstudio", "uzu", "freetoken", "swiftlm", "mference", "whallm", "slotstream", "splash", "strata", "rec", "llamacpp", "kolibri", "rapidmlx",
  ]);
  const CLIENTS = new Set(["pi", "omp", "opencode", "codex", "chat"]);
  const MIN_CONTEXT = 1024;
  const MIN_OUTPUT = 256;
  const MIN_PROMPT_BUDGET = 1024;
  const SETUP_STORAGE_KEY = "llm-launcher-visible-settings-v1";
  const MODEL_SETTINGS_KEY = "llm-launcher-model-settings-v2";
  const MAX_SAVED_SETUPS = 64;
  // Only non-secret form controls. Never persist prompts, project paths,
  // credentials, consent checkboxes, or a claim that a route is qualified.
  const SETUP_FIELDS = Object.freeze([
    "contextInput", "outputInput", "reasoningSelect", "samplingMode",
    "temperatureInput", "topPInput", "topKInput", "presencePenaltyInput",
    "frequencyPenaltyInput", "repetitionPenaltyInput", "seedInput",
    "accelerationSelect", "splashAccelerationSelect", "depthInput", "profileSelect", "fanSelect",
    "omlxKv", "mtplxKv", "burstSelect", "dflashVerifySelect", "dflashDraftQuantSelect",
    "anePrefillSelect", "memoryGuardSelect", "gpuSelect", "parallelInput",
    "mtpMinTokensInput", "mtpMinContinueProbabilityInput", "mtplxOperatorRouteSelect",
    "kolibriKv", "kolibriMemoryMode", "kolibriMemoryGB", "kolibriPrefillSelect", "kolibriPromptCacheGB",
    "omlxExpertResidentPercent", "omlxMemoryGB",
    "slotstreamKv", "slotstreamMemoryMode", "slotstreamMemoryGB",
    "swiftlmPrefillSelect", "mferencePromptCache", "mferenceQueueLimit",
    "freeTokenBatchSelect", "freeTokenPrefixCacheSelect", "freeTokenExpertCacheInput",
  ]);

  function setupKey(value) {
    const route = normaliseRoute(value);
    return route ? `${route.backend}\u0000${route.modelId}` : "";
  }

  function normaliseSetup(value, route) {
    const key = setupKey(route);
    if (!value || !key || setupKey(value.route) !== key) return null;
    const controls = {};
    for (const key of SETUP_FIELDS) {
      const field = value.controls?.[key];
      if (typeof field === "string" && field.length <= 64 && /^[a-zA-Z0-9_.+-]*$/.test(field)) controls[key] = field;
    }
    return {route:normaliseRoute(value.route), controls};
  }

  function readModelSetups(storage) {
    const raw = storage?.getItem?.(MODEL_SETTINGS_KEY);
    if (!raw || raw.length > 512 * 1024) return [];
    try {
      const value = JSON.parse(raw);
      return value?.version === 2 && Array.isArray(value.setups)
        ? value.setups.slice(0, MAX_SAVED_SETUPS).map(item => normaliseSetup(item, item?.route)).filter(Boolean) : [];
    } catch (_error) { return []; }
  }

  function readSetup(storage, route) {
    try {
      const key = setupKey(route);
      if (!key) return null;
      const saved = readModelSetups(storage).find(item => setupKey(item.route) === key);
      if (saved) return saved;
      const raw = storage?.getItem?.(SETUP_STORAGE_KEY);
      if (!raw || raw.length > 8192) return null;
      const value = JSON.parse(raw);
      return value?.version === 1 ? normaliseSetup(value, route) : null;
    } catch (_error) { return null; }
  }

  function writeSetup(storage, route, controls) {
    const value = normaliseSetup({route, controls}, route);
    if (!value) return false;
    try {
      const key = setupKey(route);
      const otherSetups = readModelSetups(storage).filter(item => setupKey(item.route) !== key);
      storage?.setItem?.(MODEL_SETTINGS_KEY, JSON.stringify({
        version:2, setups:[value, ...otherSetups.slice(0, MAX_SAVED_SETUPS - 1)],
      }));
      return Boolean(storage?.setItem);
    } catch (_error) { return false; }
  }

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

  function reconcileRuntimeLimits({context, output, contextWindows = [], outputMaximum} = {}) {
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
    const contextMaximum = Number.isInteger(nextContext)
      ? nextContext - MIN_PROMPT_BUDGET : Number.NaN;
    const runtimeMaximum = Number(outputMaximum);
    const maximumOutput = Number.isInteger(runtimeMaximum) && runtimeMaximum >= MIN_OUTPUT
      ? Math.min(contextMaximum, runtimeMaximum) : contextMaximum;
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
    SETUP_STORAGE_KEY, MODEL_SETTINGS_KEY, SETUP_FIELDS, normaliseSetup, readSetup, writeSetup,
  });
});
