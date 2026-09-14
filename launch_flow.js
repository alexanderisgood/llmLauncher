(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LaunchFlow = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const copy = value => JSON.parse(JSON.stringify(value));
  const active = phase => ["queued", "cooldown", "starting", "running", "stopping"].includes(phase);

  // The controller remains authoritative. Preparation never grants a missing
  // receipt, edits the user's settings, or substitutes an optimization run.
  function create({api, update, isCurrent, review, pause = ms => new Promise(resolve => setTimeout(resolve, ms))}) {
    let cancelled = false;
    let ownedJob = null;
    function check() {
      if (cancelled) throw new Error("Launch cancelled.");
      if (!isCurrent()) throw new Error("Settings changed. Press Launch to use the new settings.");
    }
    const post = (path, request) => api(path, {method:"POST", body:JSON.stringify(request)});
    async function stopOwned() {
      if (!ownedJob) return;
      const status = await api("/api/benchmark/status");
      if (status.job?.id === ownedJob && active(status.phase)) {
        await post("/api/benchmark/stop", {jobId:ownedJob});
      }
      ownedJob = null;
    }
    async function qualify(request, prerequisite = false) {
      check();
      const test = copy(request);
      // Only Uzu's verified Pi transport shares Chat capacity. Its Pi speed
      // evidence is never inferred from this test.
      if (test.backend === "uzu" && test.client === "pi") {
        test.client = "chat";
        test.chat = {systemPrompt:"", ...test.generation};
        delete test.agentHost;
      }
      test.calibrationCooling = "default";
      test.enginePreference = "throughput";
      let plan = (await post("/api/calibration/plan", test)).plan;
      check();
      if (plan?.routeQualification !== true) throw new Error("This setup needs attention in Advanced settings before it can launch.");
      if (plan.action === "apply-existing" && plan.evidence?.qualified === true) return;
      if (!prerequisite && test.backend === "uzu" && test.context === 131072
          && plan.memoryAdmission?.stagedQualification?.reason === "missing-64k-receipt") {
        update({phase:"testing", title:"Preparing this model for its first launch", detail:"Checking 64K capacity first, then your selected 128K context. This can take several minutes."});
        await qualify({...test, context:65536}, true);
        check();
        plan = (await post("/api/calibration/plan", test)).plan;
      }
      check();
      const admission = plan?.memoryAdmission;
      if (!plan?.ready || plan.action !== "measure" || admission?.launchable !== true
          || admission.requiresAcknowledgement !== false || admission.decision !== "ready") {
        throw new Error(admission?.detail || plan?.blockers?.join(" ") || plan?.detail || "This model cannot be tested safely right now.");
      }
      update({phase:"testing", title:"First-use capacity check", detail:`Testing ${test.context.toLocaleString()} tokens. This can take several minutes; the session opens automatically when it passes.`});
      const started = await post("/api/benchmark/start", {...test, scope:"qualification"});
      ownedJob = started.benchmark?.id;
      if (!ownedJob) throw new Error("The capacity check did not return a job ID. Nothing will launch.");
      // Cancellation can arrive while the start request is in flight.
      check();
      while (true) {
        check();
        const status = await api("/api/benchmark/status");
        check();
        if (status.job?.id !== ownedJob) throw new Error("The capacity check changed. Nothing will launch.");
        update({
          phase:"testing", title:prerequisite ? "Checking 64K before 128K" : "First-use capacity check",
          detail:["queued", "cooldown", "starting"].includes(status.phase)
            ? "Preparing the model for its capacity check. This can take several minutes."
            : prerequisite ? "Testing 64K capacity. The 128K check follows automatically."
              : "Testing the selected capacity. Your session opens automatically when the check passes.",
          progress:status.progress,
        });
        if (!active(status.phase)) {
          ownedJob = null;
          if (status.phase !== "completed") throw new Error(status.message || "The capacity check did not pass.");
          break;
        }
        await pause(1000);
      }
      const verified = (await post("/api/calibration/plan", test)).plan;
      check();
      if (verified?.action !== "apply-existing" || verified.evidence?.qualified !== true) {
        throw new Error("The capacity check finished without a matching successful result. Nothing will launch.");
      }
    }
    return {
      cancel() { cancelled = true; },
      async prepare(original) {
        const request = copy(original);
        try {
          update({phase:"checking", title:"Getting ready", detail:"Checking the model and available memory…"});
          check();
          let admission = (await post("/api/session/plan", request)).sessions?.admission;
          check();
          if (admission?.decision === "qualification") {
            await qualify(request);
            update({phase:"checking", title:"Capacity check passed", detail:"Rechecking available memory before opening your session…"});
            admission = (await post("/api/session/plan", request)).sessions?.admission;
            check();
          }
          if (admission?.launchable !== true) throw new Error(admission?.detail || "This setup cannot launch yet. Check the model and available memory.");
          if (admission.requiresAcknowledgement) {
            if (!admission.contractId || !await review(admission)) throw new Error("Launch cancelled.");
            check();
            request.memoryAcknowledgement = admission.contractId;
          }
          check();
          return request;
        } catch (error) {
          try { await stopOwned(); }
          catch (_) { throw new Error(`${error.message} Could not confirm the capacity test stopped. Check Sessions before starting again.`); }
          throw error;
        }
      },
    };
  }
  return {create};
});
