(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.LLMPolling = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function createPoller({now = () => performance.now()} = {}) {
    const jobs = new Map();
    function add(name, {run, interval}) {
      if (jobs.has(name)) throw new Error(`Duplicate poll job: ${name}`);
      let pending = null;
      let startedAt = -Infinity;
      const invoke = () => {
        if (pending) return pending;
        startedAt = now();
        pending = Promise.resolve().then(run).finally(() => { pending = null; });
        return pending;
      };
      jobs.set(name, {
        invoke,
        due:() => {
          const delay = typeof interval === "function" ? interval() : interval;
          return !pending && Number.isFinite(delay) && now() - startedAt >= delay;
        },
      });
      return invoke;
    }
    function tick() {
      return Promise.allSettled([...jobs.values()].filter(job => job.due()).map(job => job.invoke()));
    }
    return {add, tick};
  }

  return {createPoller};
});
