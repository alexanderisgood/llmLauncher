(function installRuntimeManager(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LLMRuntimeManager = api;
})(typeof globalThis === "object" ? globalThis : this, function runtimeManagerFactory() {
  "use strict";
  const clone = value => value == null ? value : JSON.parse(JSON.stringify(value));
  const esc = value => String(value ?? "").replace(/[&<>"']/g, character => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[character]);
  function createController({elements, api, engineVisible, selectedRequest, selectedModelName, selectedClient,
    informationLevel, currentOperation, refreshSelection, backendLabel, backendMark, formatBytes}) {
    const store = {runtimeInventory:null, runtimeLoading:false, runtimeOpening:false,
      runtimeUpdateCatalog:null, runtimeUpdatePlan:null, runtimeUpdateStatus:null,
      runtimeUpdatePhase:"idle", runtimeUpdateLoading:false, runtimeUpdateCompletionId:"",
      runtimePromotionPlan:null, runtimePromotionStatus:null, runtimePromotionPhase:"idle",
      runtimePromotionLoading:false, runtimePromotionApplying:false, updateStopping:false, promotionStopping:false};
    const node = id => elements[id];
    let generation = 0, updateRevision = 0, promotionRevision = 0, inventoryRevision = 0;
    let loadPending = null, updatePending = null, promotionPending = null;
    let approval = "", updateInspection = null, promotionInspection = null, comparisonRoute = "";
    const planKey = plan => JSON.stringify(plan);
    const routeKey = () => { try { return JSON.stringify([selectedRequest(), node("runtimePromotionSuite").value]); } catch (_) { return ""; } };
    const visibleRuntime = id => engineVisible(id === "lms" ? "lmstudio" : id);
    const runtimeRecord = id => visibleRuntime(id) ? store.runtimeInventory?.runtimes?.find(item => item.id === id) : null;
    const selectedCandidate = (id, candidateId) => runtimeRecord(id)?.candidates?.find(item => item.id === candidateId);
    const operationBlocked = () => Boolean(currentOperation());
    const updateBlocked = () => operationBlocked() || runtimePromotionIsActive() || store.runtimePromotionLoading || store.runtimePromotionApplying || store.runtimeLoading;
    const promotionBlocked = () => operationBlocked() || runtimeUpdateIsActive() || store.runtimeUpdateLoading || store.runtimeLoading;
    function message(id, value, error = false) { node(id).textContent = value; node(id).dataset.error = String(error); }
    function approveUpdate() {
      approval = node("runtimeUpdateConsent").checked && store.runtimeUpdatePlan?.canStart ? planKey(store.runtimeUpdatePlan) : "";
      updateRuntimeUpdateControls();
    }
    const markup = new WeakMap();
    function html(element, value) {
      if (markup.get(element) === value) return;
      const key = item => item.dataset.runtimeDisclosure || `${item.closest("[data-runtime-disclosure]")?.dataset.runtimeDisclosure || ""}:${item.className}`;
      const disclosures = new Map([...element.querySelectorAll("details")].map(item => [key(item), item.open]));
      const focused = element.ownerDocument.activeElement;
      const action = focused && element.contains(focused) ? [...focused.attributes].filter(item => item.name.startsWith("data-runtime") || item.name === "data-candidate-id") : [];
      element.innerHTML = value; markup.set(element, value);
      element.querySelectorAll("details").forEach(item => { if (disclosures.has(key(item))) item.open = disclosures.get(key(item)); });
      if (action.length) [...element.querySelectorAll("button")].find(button => action.every(item => button.getAttribute(item.name) === item.value))?.focus();
    }
    function renderRuntimeAdvancedDisclosure() {
      const panel = node("runtimeAdvancedTools");
      if (!panel) return;
      const label = panel.querySelector("summary em");
      if (label) label.textContent = panel.open ? "Hide tools" : "Show tools";
    }

    function syncRuntimeAdvancedDetailMode(detail = informationLevel()) {
      const panel = node("runtimeAdvancedTools");
      if (!panel) return;
      const workflowOpen = Boolean(
        store.runtimeUpdatePlan || store.runtimePromotionPlan
        || runtimeUpdateIsActive() || runtimePromotionIsActive()
      );
      panel.open = workflowOpen || detail === "detailed";
      renderRuntimeAdvancedDisclosure();
    }

    function renderRuntimeCardDisclosure(panel) {
      if (!panel) return;
      const label = panel.querySelector(":scope>summary em");
      if (label) label.textContent = panel.open ? "Hide" : "Details";
    }

    function syncRuntimeCardDetailMode(detail = informationLevel()) {
      node("runtimeCards").querySelectorAll(".runtime-card-details").forEach(panel => {
        panel.open = detail === "detailed";
        renderRuntimeCardDisclosure(panel);
      });
    }

    function runtimeUpdateIsActive(phase = store.runtimeUpdatePhase) {
      return ["queued", "downloading", "verifying", "installing", "smoke-testing", "promoting", "stopping"].includes(phase);
    }

    function runtimeUpdateTrackMarkup(release) {
      const stateLabel = release.selected ? "Selected" : release.verified ? "Verified" : release.installed ? "Installed" : "Available";
      const actionLabel = release.action === "verify" ? "Review verification" : release.action === "install" ? "Review install" : "Unavailable";
      return `<article class="runtime-update-track ${release.selected ? "selected" : ""} ${release.preview ? "preview" : "stable"}">
        <header><span><strong>${esc(release.label)} · oMLX ${esc(release.version)}</strong><small>${release.preview ? "Release candidate" : "Production track"} · audited ${new Date(release.releasedAt).toLocaleDateString()}</small></span><em>${esc(stateLabel)}</em></header>
        <p>${esc(release.summary)}</p>
        <div><a href="${esc(release.releaseUrl)}" target="_blank" rel="noopener">Official release notes ↗</a><button type="button" class="secondary" data-runtime-update-channel="${esc(release.channel)}" ${!release.canPlan ? "disabled" : ""}>${esc(actionLabel)}</button></div>
      </article>`;
    }

    function renderRuntimeUpdateCatalog(catalog) {
      store.runtimeUpdateCatalog = clone(catalog || store.runtimeUpdateCatalog);
      const current = store.runtimeUpdateCatalog;
      if (!current) return;
      node("runtimeUpdateCatalogBadge").textContent = `Audited ${current.catalogAuditedAt || "locally"}`;
      html(node("runtimeUpdateTracks"), (current.releases || []).map(runtimeUpdateTrackMarkup).join(""));
    }

    function runtimeUpdatePlanCheckMarkup(check) {
      const icon = check.state === "pass" ? "✓" : check.state === "advisory" ? "!" : "×";
      return `<div class="runtime-update-check ${esc(check.state)}"><i aria-hidden="true">${icon}</i><span><strong>${esc(check.label)}</strong><small>${esc(check.detail)}</small></span></div>`;
    }

    function runtimeUpdateResultMarkup(plan) {
      const result = store.runtimeUpdateStatus?.result;
      if (!result || result.version !== plan?.release?.version) return "";
      const kernel = result.smoke?.nativeKernel;
      return `<div class="runtime-update-result"><i aria-hidden="true">✓</i><span><strong>oMLX ${esc(result.version)} ${esc(result.action)}</strong><small>${esc(result.nextAction || "Verification completed.")}</small><em>${kernel?.ready ? "Native Qwen kernel passed" : "Core runtime passed; native kernel remains advisory"} · selection ${result.selectionChanged ? "changed" : "unchanged"}</em></span></div>`;
    }

    function renderRuntimeUpdatePlan(plan, resetConsent = false) {
      const next = clone(plan || null);
      const changed = planKey(next) !== planKey(store.runtimeUpdatePlan);
      if (resetConsent || changed) {
        approval = ""; node("runtimeUpdateConsent").checked = false;
      }
      store.runtimeUpdatePlan = next;
      if (changed) syncRuntimeAdvancedDetailMode();
      if (resetConsent) node("runtimeUpdateConsent").checked = false;
      if (!plan) {
        html(node("runtimeUpdatePlan"), '<div class="runtime-update-empty"><strong>Choose Review exact plan.</strong><span>No network request or filesystem change happens until a reviewed plan is approved separately.</span></div>');
        updateRuntimeUpdateControls();
        return;
      }
      const release = plan.release || {};
      const action = plan.action === "verify" ? "Verify installed copy" : plan.action === "install" ? "Install side by side" : "Blocked";
      const network = plan.review?.networkOnStart ? "Approved public dependency staging" : "No network request";
      const networkDetail = plan.review?.networkDetail || network;
      const steps = (plan.steps || []).map((step, index) => `<li><i>${index + 1}</i><span>${esc(step)}</span></li>`).join("");
      html(node("runtimeUpdatePlan"), `<div class="runtime-update-plan-head"><div><span>${esc(release.label || "Release")} track</span><h4>oMLX ${esc(release.version)} · ${esc(action)}</h4><p>${esc(release.summary || "")}</p></div><em class="${release.preview ? "preview" : "stable"}">${release.preview ? "Preview" : "Stable"}</em></div>
        <div class="runtime-update-facts">
          <span><small>Immutable source</small><strong>${esc(release.tag)} · ${esc(String(release.commit || "").slice(0, 12))}</strong><code title="${esc(release.commit)}">${esc(release.commit)}</code></span>
          <span><small>Official wheel</small><strong>${esc(release.fileName)}</strong><code title="${esc(release.sha256)}">SHA-256 ${esc(release.sha256)}</code></span>
          <span><small>Versioned destination</small><strong>${plan.destination?.exists ? "Existing exact copy" : "New isolated copy"}</strong><code title="${esc(plan.destination?.path)}">${esc(plan.destination?.path)}</code></span>
          <span><small>Runtime impact</small><strong>${esc(network)}</strong><code title="${esc(networkDetail)}">${esc(networkDetail)}</code></span>
        </div>
        <div class="runtime-update-checks">${(plan.checks || []).map(runtimeUpdatePlanCheckMarkup).join("")}</div>
        <details class="runtime-update-contract" open><summary>Exact execution contract <span>${plan.steps?.length || 0} steps</span></summary><ol>${steps}</ol><p><strong>Dependency boundary.</strong> ${esc(plan.installer?.dependencyPolicy || "")}</p><p><strong>Rollback.</strong> ${esc(plan.rollback?.detail || "")}</p></details>
        ${runtimeUpdateResultMarkup(plan)}`);
      node("runtimeUpdateConsentCopy").textContent = plan.canStart
        ? `${action} oMLX ${release.version}. The selected runtime will not change automatically.`
        : "One or more safety checks blocked this exact plan.";
      updateRuntimeUpdateControls();
    }

    function updateRuntimeUpdateControls() {
      const plan = store.runtimeUpdatePlan;
      const active = runtimeUpdateIsActive();
      const canStart = Boolean(plan?.canStart && node("runtimeUpdateConsent").checked && approval === planKey(plan) && !active && !store.runtimeUpdateLoading && !updateBlocked());
      node("runtimeUpdateConsent").disabled = !plan?.canStart || active || store.runtimeUpdateLoading || updateBlocked();
      node("runtimeUpdateConsentPanel").classList.toggle("inactive", !plan?.canStart || active);
      node("runtimeUpdateStartButton").disabled = !canStart;
      node("runtimeUpdateStopButton").disabled = !active || store.updateStopping;
      node("runtimeUpdateStartTitle").textContent = plan?.action === "verify" ? "Verify installed copy" : "Install verified copy";
      node("runtimeUpdateStartLabel").textContent = !plan
        ? "Waiting for a reviewed plan"
        : active ? "Runtime operation in progress"
        : plan.action === "verify" ? `Local checks only · oMLX ${plan.release.version}`
        : `Side by side · oMLX ${plan.release.version}`;
      if (plan && updateBlocked() && !active) node("runtimeUpdateStartLabel").textContent = "Finish the current operation before updating";
      node("runtimeUpdateTracks").querySelectorAll("button").forEach(button => { button.disabled = active || store.runtimeUpdateLoading || !store.runtimeUpdateCatalog?.releases?.find(release => release.channel === button.dataset.runtimeUpdateChannel)?.canPlan; });
    }

    function renderRuntimeUpdateStatus(data) {
      if (data?.catalog) renderRuntimeUpdateCatalog(data.catalog);
      const update = data?.runtimeUpdate || data;
      if (!update) return;
      store.runtimeUpdateStatus = clone(update);
      const previousPhase = store.runtimeUpdatePhase;
      store.runtimeUpdatePhase = update.phase || "idle";
      if (previousPhase !== store.runtimeUpdatePhase && runtimeUpdateIsActive()) syncRuntimeAdvancedDetailMode();
      if (update.plan && (!store.runtimeUpdatePlan || runtimeUpdateIsActive(update.phase))) {
        renderRuntimeUpdatePlan(update.plan);
      }
      const progress = Math.max(0, Math.min(1, Number(update.progress) || 0));
      const labels = {
        idle:"Ready to review", queued:"Approved", downloading:"Downloading",
        verifying:"Verifying checksum", installing:"Installing in isolation",
        "smoke-testing":"Running smoke tests", promoting:"Promoting verified copy",
        stopping:"Stopping safely", completed:"Completed", failed:"Failed", cancelled:"Stopped",
      };
      node("runtimeUpdatePhase").textContent = labels[update.phase] || update.phase || "Ready";
      node("runtimeUpdatePercent").textContent = `${Math.round(progress * 100)}%`;
      node("runtimeUpdateProgressBar").style.width = `${Math.round(progress * 100)}%`;
      node("runtimeUpdateProgressBar").closest("[role=progressbar]")?.setAttribute("aria-valuenow", String(Math.round(progress * 100)));
      if (node("runtimeUpdateStatus").dataset.error !== "true" || previousPhase !== store.runtimeUpdatePhase || runtimeUpdateIsActive()) message("runtimeUpdateStatus", update.message || "No runtime update is running.");
      if (store.runtimeUpdatePlan) renderRuntimeUpdatePlan(store.runtimeUpdatePlan);
      updateRuntimeUpdateControls();
      if (update.phase === "completed" && update.result) {
        const completionId = `${update.plan?.id || ""}:${update.result.version}:${update.result.action}:${update.result.path}`;
        if (completionId !== store.runtimeUpdateCompletionId) {
          store.runtimeUpdateCompletionId = completionId;
          void refreshAfterRuntimeUpdate();
        }
      }
    }


    async function inspectRuntimeUpdate(channel) {
      const release = store.runtimeUpdateCatalog?.releases?.find(item => item.channel === channel);
      if (store.runtimeUpdateLoading || runtimeUpdateIsActive() || !release?.canPlan) return;
      const token = {}; updateInspection = token; const view = generation; updateRevision += 1;
      store.runtimeUpdateLoading = true; approval = "";
      node("runtimeUpdateConsent").checked = false;
      message("runtimeUpdateStatus", "Revalidating the exact local destination and audited release contract…");
      updateRuntimeUpdateControls();
      try {
        const data = await api.updatePlan({channel});
        if (view !== generation || updateInspection !== token) return;
        renderRuntimeUpdatePlan(data.plan, true);
        message("runtimeUpdateStatus", data.plan.canStart
          ? "Exact plan ready. Review every check and approve it separately."
          : "The plan is blocked; review the failed safety check.");
      } catch (error) {
        if (view === generation && updateInspection === token) message("runtimeUpdateStatus", error.message, true);
      } finally {
        if (updateInspection !== token) return;
        updateInspection = null; store.runtimeUpdateLoading = false;
        updateRuntimeUpdateControls();
      }
    }

    async function startRuntimeUpdate() {
      const plan = store.runtimeUpdatePlan;
      if (!plan?.canStart || !node("runtimeUpdateConsent").checked || approval !== planKey(plan) || runtimeUpdateIsActive() || store.runtimeUpdateLoading || updateBlocked()) return;
      updateRevision += 1;
      store.runtimeUpdateLoading = true;
      updateRuntimeUpdateControls();
      try {
        const data = await api.updateStart({planId:plan.id, confirmation:plan.confirmation, reviewed:true});
        updateRevision += 1;
        node("runtimeUpdateConsent").checked = false; approval = "";
        renderRuntimeUpdateStatus({runtimeUpdate:{
          phase:"queued", progress:0.02, downloadedBytes:0,
          message:"Runtime plan approved. Revalidating its exact destination…",
          plan:data.plan, result:null, events:[],
        }});
      } catch (error) {
        message("runtimeUpdateStatus", error.message, true);
      } finally {
        store.runtimeUpdateLoading = false;
        updateRuntimeUpdateControls();
      }
    }

    async function stopRuntimeUpdate() {
      if (!runtimeUpdateIsActive() || store.updateStopping) return;
      store.updateStopping = true; updateRevision += 1; updateRuntimeUpdateControls();
      try { await api.updateStop(); await refreshUpdate(true); }
      catch (error) { message("runtimeUpdateStatus", error.message, true); }
      finally { store.updateStopping = false; updateRuntimeUpdateControls(); }
    }

    async function refreshAfterRuntimeUpdate() {
      try {
        const revision = ++inventoryRevision;
        const runtimeData = await api.inventory();
        if (revision === inventoryRevision) renderRuntimeManager(runtimeData.runtimeManager);
        await refreshSelection();
      } catch (error) {
        message("runtimeManagerStatus", `The update completed, but the local inventory refresh failed: ${error.message}`, true);
      }
    }

    function runtimePromotionIsActive(phase = store.runtimePromotionPhase) {
      return ["queued", "cooldown", "starting", "running", "stopping"].includes(phase);
    }

    function runtimePromotionRequest(candidateId) {
      const request = clone(selectedRequest());
      request.backend = "omlx";
      request.candidateId = candidateId;
      request.suite = node("runtimePromotionSuite").value;
      request.options = {
        ...request.options,
        acceleration:"off", kv:"off", anePrefill:"off", burst:"balanced",
      };
      return request;
    }

    function runtimePromotionResultMarkup() {
      const result = store.runtimePromotionStatus?.result;
      if (!result) return "";
      const candidate = result.measurements?.candidate || {};
      const memory = result.memoryRegressionBytes;
      const memoryLabel = Number.isFinite(Number(memory))
        ? `${Number(memory) > 0 ? "+" : Number(memory) < 0 ? "−" : ""}${formatBytes(Math.abs(Number(memory)))} pressure`
        : "Unavailable";
      const action = result.selectionChanged
        ? '<em>Promoted · previous copy remains installed</em>'
        : result.canPromote
          ? `<button type="button" class="text-button" data-runtime-promote="${esc(result.id)}">Promote measured candidate</button>`
          : '<em>Promotion withheld</em>';
      return `<section class="runtime-promotion-result ${result.canPromote ? "trusted" : ""}">
        <header><strong>${result.canPromote ? "Candidate cleared every gate" : "Selected runtime kept"}</strong>${action}</header>
        <p>${esc(result.recommendation || "Comparison completed.")}</p>
        <div class="runtime-promotion-metrics">
          <span><small>Median speed</small><strong>${Number(result.medianSpeedup || 0) >= 1 ? "+" : ""}${((Number(result.medianSpeedup || 1) - 1) * 100).toFixed(1)}%</strong></span>
          <span><small>Worst case</small><strong>${Number(result.worstCaseSpeedup || 0) >= 1 ? "+" : ""}${((Number(result.worstCaseSpeedup || 1) - 1) * 100).toFixed(1)}%</strong></span>
          <span><small>Memory guard</small><strong>${esc(memoryLabel)}</strong></span>
          <span><small>Candidate thermal</small><strong>${esc(candidate.thermalWorst || "Unavailable")}</strong></span>
        </div>
        <div class="runtime-update-checks">${(result.checks || []).map(runtimeUpdatePlanCheckMarkup).join("")}</div>
      </section>`;
    }

    function renderRuntimePromotionPlan(plan) {
      const changed = planKey(plan || null) !== planKey(store.runtimePromotionPlan);
      store.runtimePromotionPlan = clone(plan || null);
      if (changed) syncRuntimeAdvancedDetailMode();
      if (!plan) {
        html(node("runtimePromotionPlan"), '<div class="runtime-promotion-empty"><strong>Install or verify a second oMLX copy, then choose Measure update.</strong><span>Planning hashes both executables and checks the model contract without loading weights.</span></div>' + runtimePromotionResultMarkup());
        updateRuntimePromotionControls();
        return;
      }
      const selected = plan.selected || {};
      const candidate = plan.candidate || {};
      const workload = plan.workload || {};
      const steps = (plan.steps || []).map((step, index) => `<li><i>${index + 1}</i><span>${esc(step)}</span></li>`).join("");
      const order = (plan.executionOrder || []).map(role => role === "selected" ? `Selected ${selected.version}` : `Candidate ${candidate.version}`).join(" → ");
      html(node("runtimePromotionPlan"), `<div class="runtime-update-plan-head"><div><span>Exact same-model A/B</span><h4>${esc(selected.version)} versus ${esc(candidate.version)}</h4><p>${esc(plan.model?.name || "Model")} · ${esc(workload.label || "Workload")}</p></div><em>Selection unchanged</em></div>
        <div class="runtime-promotion-route">
          <div class="runtime-promotion-copy"><span>Selected reference</span><strong>${esc(selected.label)} · ${esc(selected.version)}</strong><code title="${esc(selected.path)}">${esc(selected.path)}</code><small>Revision ${esc(selected.revision?.id || "")}</small></div>
          <div class="runtime-promotion-arrow" aria-hidden="true">⇄</div>
          <div class="runtime-promotion-copy candidate"><span>Verified candidate</span><strong>${esc(candidate.label)} · ${esc(candidate.version)}</strong><code title="${esc(candidate.path)}">${esc(candidate.path)}</code><small>Revision ${esc(candidate.revision?.id || "")}</small></div>
        </div>
        <div class="runtime-promotion-summary">
          <span><small>Model</small><strong>${esc(plan.model?.name || "")}</strong></span>
          <span><small>Workload</small><strong>${esc(workload.label || "")}</strong></span>
          <span><small>Controlled mode</small><strong>AR · full-precision KV</strong></span>
          <span><small>Execution order</small><strong title="${esc(order)}">${esc(order)}</strong></span>
        </div>
        <div class="runtime-update-checks">${(plan.checks || []).map(runtimeUpdatePlanCheckMarkup).join("")}</div>
        <details class="runtime-update-contract"><summary>Promotion contract <span>${plan.steps?.length || 0} steps</span></summary><ol>${steps}</ol><p><strong>Threshold.</strong> Candidate must match deterministic output, beat the selected copy by at least 3% at both median and worst case, begin under comparable Mac conditions, add no more than 512 MB pressure, and reach no worse thermal state.</p><p><strong>Rollback.</strong> ${esc(plan.rollback?.detail || "")}</p></details>
        ${runtimePromotionResultMarkup()}`);
      node("runtimePromotionConsentCopy").textContent = `Measure ${selected.version} and ${candidate.version} with ${workload.generatedRequests || 0} generated requests. Nothing is selected automatically.`;
      updateRuntimePromotionControls();
    }

    function updateRuntimePromotionControls() {
      const plan = store.runtimePromotionPlan;
      const active = runtimePromotionIsActive();
      const canStart = Boolean(plan?.canStart && !active && !store.runtimePromotionLoading && !store.runtimePromotionApplying && !promotionBlocked() && Boolean(comparisonRoute) && comparisonRoute === routeKey());
      node("runtimePromotionConsent").disabled = true;
      node("runtimePromotionConsent").checked = false;
      node("runtimePromotionConsentPanel").classList.add("hidden");
      node("runtimePromotionStartButton").disabled = !canStart;
      node("runtimePromotionStopButton").disabled = !active || store.promotionStopping;
      node("runtimePromotionSuite").disabled = active || store.runtimePromotionLoading || store.runtimePromotionApplying;
      node("runtimePromotionStartLabel").textContent = plan && comparisonRoute !== routeKey() && !active
        ? "Visible settings changed · review this comparison again" : !plan
        ? "Waiting for an exact plan"
        : active ? "Runtime comparison in progress"
        : !plan.canStart
          ? (plan.memoryAdmission?.label || "Free memory before comparing runtimes")
        : `${plan.workload?.label || "Generated workload"} · two fresh loads`;
      if (plan && promotionBlocked() && !active) node("runtimePromotionStartLabel").textContent = "Finish the current operation before measuring";
      node("runtimePromotionPlan").querySelectorAll("[data-runtime-promote]").forEach(button => {
        button.disabled = active || store.runtimePromotionApplying || store.runtimeLoading || operationBlocked();
      });
      node("runtimeCards").querySelectorAll("[data-runtime-select]").forEach(button => {
        button.disabled = Boolean(selectedCandidate(button.dataset.runtimeSelect, button.dataset.candidateId)?.selected || store.runtimeLoading || active || runtimeUpdateIsActive() || store.runtimePromotionApplying || store.runtimeUpdateLoading || store.runtimePromotionLoading || operationBlocked());
      });
      node("runtimeCards").querySelectorAll("[data-runtime-compare]").forEach(button => {
        button.disabled = active || store.runtimePromotionLoading || store.runtimePromotionApplying || !selectedCandidate("omlx", button.dataset.runtimeCompare)?.managedVerification?.verified;
      });
    }

    function renderRuntimePromotionStatus(data) {
      const status = data?.runtimePromotion || data;
      if (!status) return;
      store.runtimePromotionStatus = clone({...status, result:status.result || data?.latestResult || null});
      const previousPhase = store.runtimePromotionPhase;
      store.runtimePromotionPhase = status.phase || "idle";
      if (previousPhase !== store.runtimePromotionPhase && runtimePromotionIsActive()) syncRuntimeAdvancedDetailMode();
      if (status.plan && (!store.runtimePromotionPlan || runtimePromotionIsActive(status.phase))) {
        renderRuntimePromotionPlan(status.plan);
      }
      const progress = Math.max(0, Math.min(1, Number(status.progress) || 0));
      const labels = {
        idle:"Ready to plan", queued:"Approved", cooldown:"Stabilising Mac",
        starting:"Loading runtime", running:"Measuring", stopping:"Stopping safely",
        completed:"Comparison complete", failed:"Needs attention", cancelled:"Stopped",
      };
      const planReady = status.phase === "idle" && Boolean(store.runtimePromotionPlan);
      node("runtimePromotionPhase").textContent = planReady ? "Plan ready" : labels[status.phase] || status.phase || "Ready";
      node("runtimePromotionPercent").textContent = `${Math.round(progress * 100)}%`;
      node("runtimePromotionProgressBar").style.width = `${Math.round(progress * 100)}%`;
      node("runtimePromotionProgressBar").closest("[role=progressbar]")?.setAttribute("aria-valuenow", String(Math.round(progress * 100)));
      if (node("runtimePromotionStatus").dataset.error !== "true" || previousPhase !== store.runtimePromotionPhase || runtimePromotionIsActive()) message("runtimePromotionStatus", planReady
        ? "Exact comparison plan ready. Review both copies and every promotion guard."
        : status.message || "No runtime comparison is running.");
      if (store.runtimePromotionPlan) renderRuntimePromotionPlan(store.runtimePromotionPlan);
      else if (store.runtimePromotionStatus.result) renderRuntimePromotionPlan(null);
      updateRuntimePromotionControls();
    }


    async function inspectRuntimePromotion(candidateId) {
      const candidate = selectedCandidate("omlx", candidateId);
      if (!candidate || candidate.selected || !candidate.managedVerification?.verified || store.runtimePromotionLoading || store.runtimePromotionApplying || runtimePromotionIsActive()) return;
      const token = {}; promotionInspection = token; const view = generation; const route = routeKey(); promotionRevision += 1;
      store.runtimePromotionLoading = true;
      message("runtimePromotionStatus", "Hashing both installed executable revisions and validating the visible model contract…");
      updateRuntimePromotionControls();
      try {
        const data = await api.promotionPlan(runtimePromotionRequest(candidateId));
        if (view !== generation || promotionInspection !== token || route !== routeKey()) return;
        comparisonRoute = route; renderRuntimePromotionPlan(data.plan);
        node("runtimePromotionPhase").textContent = "Plan ready";
        message("runtimePromotionStatus", "Exact comparison plan ready. Review both copies and every promotion guard.");
      } catch (error) {
        if (view === generation && promotionInspection === token) message("runtimePromotionStatus", error.message, true);
      } finally {
        if (promotionInspection !== token) return;
        promotionInspection = null; store.runtimePromotionLoading = false;
        updateRuntimePromotionControls();
      }
    }

    async function startRuntimePromotion() {
      const plan = store.runtimePromotionPlan;
      if (!plan?.canStart || !comparisonRoute || runtimePromotionIsActive() || store.runtimePromotionLoading || store.runtimePromotionApplying || promotionBlocked() || comparisonRoute !== routeKey()) return;
      promotionRevision += 1;
      store.runtimePromotionLoading = true;
      updateRuntimePromotionControls();
      try {
        const data = await api.promotionStart({planId:plan.id, confirmation:plan.confirmation, reviewed:true});
        promotionRevision += 1;
        renderRuntimePromotionStatus({runtimePromotion:{
          phase:"queued", progress:0, message:"Runtime comparison started. Revalidating both exact copies…",
          plan:data.plan, result:null, modes:{}, runtimes:{}, events:[],
        }});
      } catch (error) {
        message("runtimePromotionStatus", error.message, true);
      } finally {
        store.runtimePromotionLoading = false;
        updateRuntimePromotionControls();
      }
    }

    async function stopRuntimePromotion() {
      if (!runtimePromotionIsActive() || store.promotionStopping) return;
      store.promotionStopping = true; promotionRevision += 1; updateRuntimePromotionControls();
      try { await api.promotionStop(); await refreshPromotion(true); }
      catch (error) { message("runtimePromotionStatus", error.message, true); }
      finally { store.promotionStopping = false; updateRuntimePromotionControls(); }
    }

    async function applyRuntimePromotion(resultId = store.runtimePromotionStatus?.result?.id) {
      const result = store.runtimePromotionStatus?.result;
      if (result?.id !== resultId || !result?.canPromote || result.selectionChanged || store.runtimePromotionApplying || runtimePromotionIsActive() || store.runtimeLoading || operationBlocked()) return;
      promotionRevision += 1; inventoryRevision += 1;
      store.runtimePromotionApplying = true; updateRuntimePromotionControls();
      message("runtimePromotionStatus", "Revalidating the measured evidence and both executable revisions before promotion…");
      try {
        const data = await api.promotionApply({resultId:result.id, confirmation:result.confirmation});
        promotionRevision += 1; inventoryRevision += 1;
        renderRuntimeManager(data.runtimeManager);
        store.runtimePromotionStatus.result = clone(data.result);
        renderRuntimePromotionPlan(store.runtimePromotionPlan);
        await refreshSelection();
        message("runtimePromotionStatus", `oMLX ${data.result.candidate?.version || "candidate"} is selected for new sessions. The previous copy remains installed for rollback.`);
      } catch (error) {
        message("runtimePromotionStatus", error.message, true);
      } finally {
        store.runtimePromotionApplying = false;
        updateRuntimePromotionControls();
      }
    }

    function runtimeCheckMarkup(check) {
      const stateClass = check.ready ? "pass" : (check.advisory ? "advisory" : "blocked");
      return `<div class="runtime-check ${stateClass}"><i aria-hidden="true">${check.ready ? "✓" : check.advisory ? "!" : "×"}</i><span><strong>${esc(check.label)}</strong><small>${esc(check.detail)}</small></span></div>`;
    }

    function runtimeCandidateMarkup(runtime, candidate) {
      const badges = [
        candidate.selected ? '<em class="selected">Selected</em>' : "",
        candidate.recommended && !candidate.selected ? '<em class="recommended">Recommended installed copy</em>' : "",
        candidate.managedVerification?.verified ? '<em class="verified">Official checksum verified</em>' : "",
      ].join("");
      const measure = runtime.id === "omlx" && !candidate.selected && candidate.managedVerification?.verified
        ? `<button type="button" class="text-button" data-runtime-compare="${esc(candidate.id)}">Measure update</button>`
        : "";
      return `<div class="runtime-candidate ${candidate.selected ? "selected" : ""}">
        <div><strong>${esc(candidate.channelLabel)}</strong><span>${esc(candidate.version)}</span><code title="${esc(candidate.resolvedPath || candidate.path)}">${esc(candidate.path)}</code></div>
        <div class="runtime-candidate-action">${badges}${measure}<button type="button" class="text-button" data-runtime-select="${esc(runtime.id)}" data-candidate-id="${esc(candidate.id)}" ${candidate.selected ? "disabled" : ""}>${candidate.selected ? "In use" : "Use for new sessions"}</button></div>
      </div>`;
    }

    function runtimeReleaseMarkup(release) {
      if (!release) return "";
      const highlights = (release.highlights || []).slice(0, 3).map(item =>
        `<span><strong>${esc(item.value)}</strong><small>${esc(item.label)}</small></span>`).join("");
      const workflow = release.needsReview && release.workflow?.length
        ? `<details class="runtime-release-workflow"><summary>Safe evaluation order <span>${release.workflow.length} steps</span></summary><ol>${release.workflow.map((step, index) => `<li><i>${index + 1}</i><span>${esc(step)}</span></li>`).join("")}</ol></details>`
        : "";
      const released = release.releasedAt
        ? new Date(release.releasedAt).toLocaleDateString([], {dateStyle:"medium"})
        : "Date unavailable";
      const advisory = release.activeAdvisory
        ? `<div class="runtime-release-advisory"><i aria-hidden="true">!</i><span><strong>${esc(release.activeAdvisory.headline || "Runtime re-test required")}</strong><small>${esc(release.activeAdvisory.detail || "Repeat affected measurements after updating.")}</small></span></div>`
        : "";
      return `<section class="runtime-release ${esc(release.state || "unknown-local-version")}">
        <header><span><small>Audited upstream</small><strong>${esc(release.displayVersion || release.version || "Unknown")}</strong></span><em>${esc(release.label || "Review")}</em></header>
        <p>${esc(release.summary || release.detail || "")}</p>
        ${advisory}
        ${highlights ? `<div class="runtime-release-highlights">${highlights}</div>` : ""}
        ${workflow}
        <footer>Released ${esc(released)} · catalog checked ${esc(release.auditedAt || "locally")}</footer>
      </section>`;
    }

    function runtimeCardMarkup(runtime) {
      const selected = runtime.selected;
      const update = runtime.update || {};
      const release = runtime.release || update.release;
      const links = [
        update.primaryUrl ? `<a href="${esc(update.primaryUrl)}" target="_blank" rel="noopener">${esc(update.primaryLabel || "Official update guidance")} ↗</a>` : "",
        update.docsUrl && update.docsUrl !== update.primaryUrl ? `<a href="${esc(update.docsUrl)}" target="_blank" rel="noopener">Installation docs ↗</a>` : "",
      ].filter(Boolean).join("");
      const appAction = runtime.app?.available
        ? `<button type="button" class="text-button runtime-open-app" data-runtime-open="${esc(runtime.id)}">Open ${esc(runtime.app.label || runtime.label)}</button>`
        : "";
      const advanced = update.developerCommand
        ? `<details class="runtime-advanced"><summary>Advanced Homebrew path</summary><p>${esc(update.detail || "")}</p><code>${esc(update.developerCommand)}</code><small>${update.developerCommandReady ? "Full Metal compiler detected." : "Blocked here: the full Xcode Metal compiler was not detected."}</small></details>`
        : `<p class="runtime-update-detail">${esc(update.detail || "")}</p>`;
      const selectedVersion = selected?.version || "Not installed";
      const auditedVersion = release?.displayVersion || release?.version || "Not audited";
      const detailOpen = informationLevel() === "detailed" ? " open" : "";
      return `<article class="runtime-card ${esc(runtime.level)}">
        <header><div><span class="runtime-icon ${esc(runtime.id)}" aria-hidden="true">${esc(backendMark(runtime.id))}</span><span><strong>${esc(runtime.label)}</strong><small>${esc(runtime.headline)}</small></span></div><em>${runtime.level === "ready" ? "Ready" : runtime.level === "advisory" ? "Review" : "Missing"}</em></header>
        <div class="runtime-card-overview"><span><small>Selected</small><strong>${esc(selectedVersion)}</strong></span><span><small>Audited</small><strong>${esc(auditedVersion)}</strong></span></div>
        <details class="runtime-card-details" data-runtime-disclosure="${esc(runtime.id)}:card"${detailOpen}><summary><span><strong>Checks, copies &amp; guidance</strong><small>${runtime.checks?.length || 0} checks · ${runtime.candidates?.length || 0} installed ${runtime.candidates?.length === 1 ? "copy" : "copies"}</small></span><em>${detailOpen ? "Hide" : "Details"}</em></summary><div class="runtime-card-details-body">
          <div class="runtime-selected"><span>Selected for new sessions</span><strong>${esc(selectedVersion)}</strong><code title="${esc(selected?.path || "")}">${esc(selected?.path || "No executable selected")}</code></div>
          ${runtimeReleaseMarkup(release)}
          <div class="runtime-checks">${(runtime.checks || []).map(runtimeCheckMarkup).join("")}</div>
          <details class="runtime-copies" data-runtime-disclosure="${esc(runtime.id)}:copies" ${runtime.candidates?.length > 1 ? "open" : ""}><summary>Installed copies <span>${runtime.candidates?.length || 0}</span></summary><div>${(runtime.candidates || []).map(candidate => runtimeCandidateMarkup(runtime, candidate)).join("") || '<p class="runtime-empty">No supported local executable was found.</p>'}</div></details>
          <div class="runtime-update"><strong>${esc(update.headline || "Review the official installation guidance.")}</strong>${advanced}<div class="runtime-links">${appAction}${links}</div><small>${esc(update.rollback || "")}</small></div>
        </div></details>
      </article>`;
    }

    function renderRuntimeManager(inventory) {
      store.runtimeInventory = clone(inventory);
      const runtimes = (inventory?.runtimes || []).filter(runtime => engineVisible(runtime.id === "lms" ? "lmstudio" : runtime.id));
      const summary = inventory?.summary || {};
      const installed = runtimes.filter(runtime => runtime.selected).length;
      node("runtimeSummaryBadge").textContent = `${installed}/${runtimes.length || 3} installed`;
      node("runtimeSummaryBadge").className = `setup-badge ${summary.advisories ? "warning" : "ready"}`;
      node("runtimeManagerSummary").textContent = summary.message || "Local runtime inspection completed.";
      html(node("runtimeCards"), runtimes.map(runtimeCardMarkup).join(""));
      node("runtimeCards").querySelectorAll(".runtime-card-details").forEach(panel => {
        if (!panel.dataset.runtimeBound) { panel.dataset.runtimeBound = "true"; panel.addEventListener("toggle", () => renderRuntimeCardDisclosure(panel)); }
        renderRuntimeCardDisclosure(panel);
      });
      html(node("runtimeAgents"), (inventory?.agents || []).map(agent => `<div class="runtime-agent ${agent.installed ? "" : "missing"}"><span><strong>${esc(agent.label)}</strong><small>${esc(agent.version)}</small></span><em>${agent.installed ? "Ready" : "Missing"}</em></div>`).join(""));
      updateRuntimePromotionControls();
    }

    async function loadRuntimeManager() {
      if (loadPending) return loadPending;
      if (store.runtimeLoading) return;
      const view = generation, revision = ++inventoryRevision;
      store.runtimeLoading = true;
      node("runtimePromotionModel").textContent = selectedModelName() || "Choose a model in the launcher";
      node("refreshRuntimeManager").disabled = true;
      message("runtimeManagerStatus", "Running local checks without starting any runtime…");
      updateRuntimeUpdateControls(); updateRuntimePromotionControls();
      const pending = (async () => {
        try {
          const [data] = await Promise.all([api.inventory(), refreshUpdate(), refreshPromotion()]);
          if (view !== generation || revision !== inventoryRevision) return;
          renderRuntimeManager(data.runtimeManager);
          const auditedAt = data.runtimeManager.releaseCatalog?.auditedAt || "the bundled audit date";
          message("runtimeManagerStatus", `Checked locally at ${new Date(data.runtimeManager.checkedAt).toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"})}. Official-release evidence was audited ${auditedAt} and read from the bundled catalog; no network check was performed.`);
        } catch (error) { if (view === generation && revision === inventoryRevision) message("runtimeManagerStatus", error.message, true); }
        finally { store.runtimeLoading = false; node("refreshRuntimeManager").disabled = false; updateRuntimeUpdateControls(); updateRuntimePromotionControls(); }
      })();
      loadPending = pending;
      try { await pending; } finally { if (loadPending === pending) loadPending = null; }
    }

    async function openRuntimeManager() {
      if (!node("runtimeDialog").open) node("runtimeDialog").showModal();
      syncRuntimeAdvancedDetailMode();
      if (!store.runtimePromotionPlan && !runtimePromotionIsActive()) {
        node("runtimePromotionSuite").value = ["pi","omp","opencode","codex"].includes(selectedClient()) ? "agentic" : "standard";
      }
      if (loadPending) await loadPending;
      await loadRuntimeManager();
      syncRuntimeAdvancedDetailMode();
    }

    async function openRuntimeApp(runtime, button) {
      if (!runtimeRecord(runtime)?.app?.available || store.runtimeOpening) return;
      store.runtimeOpening = true;
      if (button) button.disabled = true;
      message("runtimeManagerStatus", `Opening ${backendLabel(runtime === "lms" ? "lmstudio" : runtime)}…`);
      try {
        const data = await api.open({runtime});
        message("runtimeManagerStatus", data.detail || `${data.label || "Runtime app"} opened.`);
      } catch (error) {
        message("runtimeManagerStatus", error.message, true);
      } finally {
        store.runtimeOpening = false;
        if (button) button.disabled = false;
      }
    }

    async function selectRuntime(runtime, candidateId, button) {
      const candidate = selectedCandidate(runtime, candidateId);
      if (!candidate || candidate.selected || store.runtimeLoading || runtimeUpdateIsActive() || runtimePromotionIsActive() || store.runtimePromotionApplying || store.runtimeUpdateLoading || store.runtimePromotionLoading || operationBlocked()) return;
      inventoryRevision += 1; store.runtimeLoading = true;
      updateRuntimeUpdateControls(); updateRuntimePromotionControls();
      message("runtimeManagerStatus", "Verifying the exact installed executable before switching new sessions…");
      if (button) button.disabled = true;
      try {
        const data = await api.select({runtime, candidateId, confirmation:`select:${candidateId}`});
        inventoryRevision += 1;
        renderRuntimeManager(data.runtimeManager);
        await refreshSelection();
        message("runtimeManagerStatus", `${({omlx:"oMLX", lms:"LM Studio", mtplx:"MTPLX", mirai:"Uzu · Mirai", uzu:"Uzu · Mirai"})[runtime] || runtime} selection updated for new sessions. No software was installed or removed.`);
      } catch (error) {
        message("runtimeManagerStatus", error.message, true);
        if (button) button.disabled = false;
      } finally {
        store.runtimeLoading = false; updateRuntimeUpdateControls(); updateRuntimePromotionControls();
      }
    }


    async function refreshUpdate(force = false) {
      if (updatePending) { await updatePending; if (!force) return; }
      const revision = updateRevision;
      const pending = (async () => {
        try { const data = await api.updateStatus(); if (revision === updateRevision) renderRuntimeUpdateStatus(data); }
        catch (error) { if (revision === updateRevision && node("runtimeDialog").open) message("runtimeUpdateStatus", error.message, true); }
      })();
      updatePending = pending;
      try { await pending; } finally { if (updatePending === pending) updatePending = null; }
    }
    async function refreshPromotion(force = false) {
      if (promotionPending) { await promotionPending; if (!force) return; }
      const revision = promotionRevision;
      const pending = (async () => {
        try { const data = await api.promotionStatus(); if (revision === promotionRevision) renderRuntimePromotionStatus(data); }
        catch (error) { if (revision === promotionRevision && node("runtimeDialog").open) message("runtimePromotionStatus", error.message, true); }
      })();
      promotionPending = pending;
      try { await pending; } finally { if (promotionPending === pending) promotionPending = null; }
    }
    node("openRuntimeManager").addEventListener("click", openRuntimeManager);
    node("refreshRuntimeManager").addEventListener("click", loadRuntimeManager);
    node("runtimeAdvancedTools").addEventListener("toggle", renderRuntimeAdvancedDisclosure);
    node("runtimeUpdateConsent").addEventListener("change", approveUpdate);
    node("runtimeUpdateStartButton").addEventListener("click", startRuntimeUpdate);
    node("runtimeUpdateStopButton").addEventListener("click", stopRuntimeUpdate);
    node("runtimePromotionStartButton").addEventListener("click", startRuntimePromotion);
    node("runtimePromotionStopButton").addEventListener("click", stopRuntimePromotion);
    node("runtimePromotionSuite").addEventListener("change", () => {
      if (runtimePromotionIsActive() || (store.runtimePromotionLoading && !promotionInspection)) return;
      promotionRevision += 1; promotionInspection = null; store.runtimePromotionLoading = false; comparisonRoute = "";
      renderRuntimePromotionPlan(null);
      message("runtimePromotionStatus", "Workload changed. Choose Measure update again to create an exact plan.");
    });
    node("runtimePromotionPlan").addEventListener("click", event => {
      const button = event.target.closest("[data-runtime-promote]");
      if (button && !button.disabled) void applyRuntimePromotion(button.dataset.runtimePromote);
    });
    node("runtimeUpdateTracks").addEventListener("click", event => {
      const button = event.target.closest("[data-runtime-update-channel]");
      if (button && !button.disabled) void inspectRuntimeUpdate(button.dataset.runtimeUpdateChannel);
    });
    node("runtimeCards").addEventListener("click", event => {
      const open = event.target.closest("[data-runtime-open]");
      const compare = event.target.closest("[data-runtime-compare]");
      const select = event.target.closest("[data-runtime-select]");
      if (open && !open.disabled) void openRuntimeApp(open.dataset.runtimeOpen, open);
      else if (compare && !compare.disabled) void inspectRuntimePromotion(compare.dataset.runtimeCompare);
      else if (select && !select.disabled) void selectRuntime(select.dataset.runtimeSelect, select.dataset.candidateId, select);
    });
    node("runtimeDialog").addEventListener("close", () => {
      generation += 1; updateRevision += 1; promotionRevision += 1;
      if (updateInspection) { updateInspection = null; store.runtimeUpdateLoading = false; }
      if (promotionInspection) { promotionInspection = null; store.runtimePromotionLoading = false; }
      approval = ""; node("runtimeUpdateConsent").checked = false;
      updateRuntimeUpdateControls(); updateRuntimePromotionControls();
    });
    return {show:openRuntimeManager, load:loadRuntimeManager, openApp:openRuntimeApp, select:selectRuntime,
      inspectUpdate:inspectRuntimeUpdate, startUpdate:startRuntimeUpdate, stopUpdate:stopRuntimeUpdate,
      inspectPromotion:inspectRuntimePromotion, startPromotion:startRuntimePromotion, stopPromotion:stopRuntimePromotion,
      applyPromotion:applyRuntimePromotion, renderInventory:renderRuntimeManager, renderUpdate:renderRuntimeUpdateStatus,
      renderPromotion:renderRuntimePromotionStatus, renderUpdatePlan:renderRuntimeUpdatePlan, refreshUpdate, refreshPromotion,
      updateControls:() => {updateRuntimeUpdateControls();updateRuntimePromotionControls();},
      syncAdvanced:syncRuntimeAdvancedDetailMode, syncCards:syncRuntimeCardDetailMode,
      updateIsActive:runtimeUpdateIsActive, promotionIsActive:runtimePromotionIsActive,
      snapshot:() => clone(store)};
  }
  return {createController};
});
