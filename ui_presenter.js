(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LLMUiPresenter = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  // Compare with the DOM, rather than a shadow cache: another view may have
  // changed a shared control since its previous render.
  function property(element, name, value) {
    if (["disabled", "hidden", "inert"].includes(name)) value = Boolean(value);
    if (!element || element[name] === value) return false;
    element[name] = value;
    return true;
  }

  function attribute(element, name, value) {
    if (!element) return false;
    const next = String(value);
    if (element.getAttribute(name) === next) return false;
    element.setAttribute(name, next);
    return true;
  }

  function data(element, name, value) {
    if (!element) return false;
    return property(element.dataset, name, String(value));
  }

  function signal(element, valueElement, signal) {
    if (!signal) return;
    property(valueElement, "textContent", signal.value);
    property(element, "title", signal.title || "");
    data(element, "state", signal.state || "unknown");
  }

  return {property, attribute, data, signal};
});
