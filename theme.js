(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LLMThemeCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const STORAGE_KEY = "llm-launcher-theme-v1";
  const DETAIL_STORAGE_KEY = "llm-launcher-detail-v1";
  const DEFAULT_THEME = "graphite";
  const DEFAULT_DETAIL = "focused";
  const THEMES = Object.freeze([
    Object.freeze({id:"graphite", label:"Graphite", detail:"Neutral charcoal with amber and sage accents."}),
    Object.freeze({id:"daylight", label:"Daylight", detail:"A clean light workspace with blue and jade accents."}),
    Object.freeze({id:"ember", label:"Ember", detail:"Warm cocoa surfaces with soft coral accents."}),
    Object.freeze({id:"midnight", label:"Midnight", detail:"The original deep-blue and violet palette."}),
  ]);
  const THEME_IDS = new Set(THEMES.map(theme => theme.id));
  const DETAIL_LEVELS = Object.freeze([
    Object.freeze({id:"focused", label:"Focused", detail:"Keep the launch path clear and reveal help when needed."}),
    Object.freeze({id:"detailed", label:"Detailed", detail:"Show diagnostics, evidence, helper copy, and secondary actions."}),
  ]);
  const DETAIL_IDS = new Set(DETAIL_LEVELS.map(level => level.id));

  function normaliseTheme(value) {
    return THEME_IDS.has(String(value || "").trim().toLowerCase())
      ? String(value).trim().toLowerCase()
      : DEFAULT_THEME;
  }

  function readTheme(storage) {
    try {
      return normaliseTheme(storage?.getItem?.(STORAGE_KEY));
    } catch (_error) {
      return DEFAULT_THEME;
    }
  }

  function writeTheme(storage, value) {
    const theme = normaliseTheme(value);
    try {
      storage?.setItem?.(STORAGE_KEY, theme);
      return {theme, stored:Boolean(storage?.setItem)};
    } catch (_error) {
      return {theme, stored:false};
    }
  }

  function applyTheme(element, value) {
    const theme = normaliseTheme(value);
    if (element?.dataset) element.dataset.theme = theme;
    return theme;
  }

  function initialiseTheme(element, storage) {
    return applyTheme(element, readTheme(storage));
  }

  function normaliseDetail(value) {
    return DETAIL_IDS.has(String(value || "").trim().toLowerCase())
      ? String(value).trim().toLowerCase()
      : DEFAULT_DETAIL;
  }

  function readDetail(storage) {
    try {
      return normaliseDetail(storage?.getItem?.(DETAIL_STORAGE_KEY));
    } catch (_error) {
      return DEFAULT_DETAIL;
    }
  }

  function writeDetail(storage, value) {
    const detail = normaliseDetail(value);
    try {
      storage?.setItem?.(DETAIL_STORAGE_KEY, detail);
      return {detail, stored:Boolean(storage?.setItem)};
    } catch (_error) {
      return {detail, stored:false};
    }
  }

  function applyDetail(element, value) {
    const detail = normaliseDetail(value);
    if (element?.dataset) element.dataset.detail = detail;
    return detail;
  }

  function initialiseDetail(element, storage) {
    return applyDetail(element, readDetail(storage));
  }

  function initialiseAppearance(element, storage) {
    return Object.freeze({
      theme:initialiseTheme(element, storage),
      detail:initialiseDetail(element, storage),
    });
  }

  return Object.freeze({
    STORAGE_KEY, DETAIL_STORAGE_KEY, DEFAULT_THEME, DEFAULT_DETAIL, THEMES, DETAIL_LEVELS,
    normaliseTheme, readTheme, writeTheme, applyTheme, initialiseTheme,
    normaliseDetail, readDetail, writeDetail, applyDetail, initialiseDetail, initialiseAppearance,
  });
});

if (typeof document !== "undefined") {
  let themeStorage = null;
  try { themeStorage = globalThis.localStorage; } catch (_error) {}
  globalThis.LLMThemeCore.initialiseAppearance(document.documentElement, themeStorage);
}
