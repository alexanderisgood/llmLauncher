(function installSessionSets(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LLMSessionSets = api;
})(typeof globalThis === "object" ? globalThis : this, function sessionSetsFactory() {
  "use strict";
  const clone = value => value == null ? value : JSON.parse(JSON.stringify(value));
  const esc = value => String(value ?? "").replace(/[&<>"']/g, character => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[character]);

  function createController({elements, api, workspace, visible, backendLabel, formatNumber,
    dateLabel, experimental, canApply, applyPrimary, openEditor, notify, refreshRoute,
    onChange = () => {}, schedule = callback => requestAnimationFrame(callback)}) {
    const store = {sets:[],limit:16,loading:false,busy:false,editingId:"",deleteConfirmId:"",
      plan:null,planLoading:false,status:null,selectedId:"",completionId:"",statusLoading:false};
    const node = id => elements[id];
    const changed = () => onChange();
    let reviewRevision = 0, statusRevision = 0, approval = "";
    const markup = new WeakMap();
    function html(element, value) {
      if (markup.get(element) === value) return;
      const focused = element.ownerDocument?.activeElement;
      const action = focused && element.contains?.(focused)
        ? ["review", "apply", "edit", "delete"].map(name => [`data-session-set-${name}`, focused.getAttribute?.(`data-session-set-${name}`)])
          .find(([, id]) => id != null) : null;
      element.innerHTML = value;
      markup.set(element, value);
      if (action) [...element.querySelectorAll("button")].find(button => button.getAttribute(action[0]) === action[1] && !button.disabled)?.focus({preventScroll:true});
    }
    const approvalKey = plan => JSON.stringify([plan?.setId, plan?.confirmation,
      plan?.requiresExperimentalApproval === true, plan?.admission?.requiresAcknowledgement === true,
      plan?.admission?.contractId]);
    function resetReview() {
      reviewRevision += 1;
      store.plan = null; store.planLoading = false;
      approval = ""; node("sessionSetConsent").checked = false;
    }
    function acceptConsent() {
      approval = node("sessionSetConsent").checked && store.plan ? approvalKey(store.plan) : "";
      renderPlan();
    }
    const SESSION_SET_ACTIVE_PHASES = new Set(["starting", "waiting", "attaching", "stopping"]);
    const SESSION_SET_FINISHED_PHASES = new Set(["completed", "failed", "cancelled"]);

    function isActive(status = store.status) {
      return SESSION_SET_ACTIVE_PHASES.has(status?.phase || "idle");
    }

    function currentRoute() { return workspace()?.run || null; }

    function message(message, kind = "") {
      const status = node("sessionSetStatus");
      status.textContent = message || "";
      status.className = `session-dashboard-status${kind ? ` ${kind}` : ""}`;
    }

    function useInventory(data) {
      store.sets = Array.isArray(data?.sets) ? clone(data.sets.filter(visible)) : [];
      store.limit = Number(data?.limit || 16);
      changed();
    }

    function useStatus(data, announceFinished = false) {
      const next = data?.sessionSet || data;
      if (!next || typeof next !== "object") return;
      statusRevision += 1;
      store.status = clone(next);
      if (isActive(next) && next.setId) store.selectedId = next.setId;
      const finished = SESSION_SET_FINISHED_PHASES.has(next.phase);
      const completionId = String(next.jobId || "");
      if (!announceFinished && finished && completionId) {
        store.completionId = completionId;
      } else if (announceFinished && finished && completionId && store.completionId !== completionId) {
        store.completionId = completionId;
        const failed = next.phase === "failed";
        notify(next.message || (failed ? "The Session Set could not finish opening." : "Session Set opening finished."), failed);
        void refreshRoute();
      }
    }

    function factMarkup(facts) {
      return facts.map(([label, value]) => `<span><small>${esc(label)}</small><b title="${esc(String(value))}">${esc(String(value))}</b></span>`).join("");
    }

    function renderPlan() {
      const panel = node("sessionSetPlanPanel");
      const openButton = node("sessionSetOpenButton");
      const stopButton = node("sessionSetStopButton");
      const consentPanel = node("sessionSetConsentPanel");
      const warning = node("sessionSetPlanWarning");
      const status = store.status || {};
      const active = isActive(status);
      const selectedFinished = (
        SESSION_SET_FINISHED_PHASES.has(status.phase)
        && status.jobId
        && status.setId === store.selectedId
        && !store.plan
        && !store.planLoading
      );

      if (active || selectedFinished) {
        panel.classList.remove("hidden");
        const finished = SESSION_SET_FINISHED_PHASES.has(status.phase);
        const stateLabels = {
          starting:"Starting", waiting:"Loading model", attaching:"Opening surfaces",
          stopping:"Stopping", completed:"Opened", failed:"Needs attention", cancelled:"Stopped",
        };
        node("sessionSetPlanTitle").textContent = `${finished ? "Result" : "Opening"} · ${status.setName || "Session Set"}`;
        node("sessionSetPlanState").textContent = stateLabels[status.phase] || status.phase || "Working";
        node("sessionSetPlanDetail").textContent = status.message || "Opening this saved workspace.";
        html(node("sessionSetPlanFacts"), factMarkup([
          ["Route", status.mode === "launch" ? "New model load" : status.mode === "reuse" ? "Resident model" : "No changes"],
          ["Saved surfaces", formatNumber(status.totalSurfaceCount || 0)],
          ["Newly opened", formatNumber(status.openedSurfaceCount || 0)],
          ["Still pending", formatNumber(status.pendingSurfaceCount || 0)],
        ]));
        warning.textContent = status.error || "";
        warning.classList.toggle("hidden", !status.error);
        consentPanel.classList.add("hidden");
        stopButton.classList.toggle("hidden", !active);
        stopButton.disabled = store.busy || status.phase === "stopping";
        openButton.classList.add("hidden");
        return;
      }

      const plan = store.plan;
      if (!plan && !store.planLoading) {
        panel.classList.add("hidden");
        return;
      }
      panel.classList.remove("hidden");
      openButton.classList.remove("hidden");
      stopButton.classList.add("hidden");
      if (store.planLoading) {
        node("sessionSetPlanTitle").textContent = "Checking saved workspace";
        node("sessionSetPlanState").textContent = "Read-only";
        node("sessionSetPlanDetail").textContent = "Revalidating the model, engine, projects, work surfaces, resident route, and current memory headroom…";
        html(node("sessionSetPlanFacts"), "");
        warning.classList.add("hidden");
        consentPanel.classList.add("hidden");
        openButton.disabled = true;
        openButton.querySelector("strong").textContent = "Checking plan";
        openButton.querySelector("small").textContent = "Nothing opens during review";
        return;
      }

      const modeLabels = {
        launch:"Load one model", reuse:"Reuse loaded model",
        "already-open":"No changes", blocked:"Unavailable",
      };
      node("sessionSetPlanTitle").textContent = plan.setName || "Opening plan";
      node("sessionSetPlanState").textContent = plan.requiresExperimentalApproval ? "Experimental" : plan.ready ? "Ready" : "Blocked";
      node("sessionSetPlanDetail").textContent = plan.detail || "Review the exact opening plan.";
      html(node("sessionSetPlanFacts"), factMarkup([
        ["Route", modeLabels[plan.mode] || plan.mode || "Unavailable"],
        ["Saved surfaces", formatNumber(plan.surfaceCount || 0)],
        ["Already matched", formatNumber(plan.existingMatchCount || 0)],
        ["Opening now", formatNumber(plan.willOpenSurfaceCount || 0)],
        ["Window mix", `${formatNumber(plan.hubConsoleCount || 0)} Hub · ${formatNumber(plan.chatCount || 0)} Chat · ${formatNumber(plan.terminalCount || 0)} Terminal`],
      ]));
      const warnings = [];
      if (plan.terminalCount) {
        warnings.push(
          `${formatNumber(plan.terminalCount)} agent${Number(plan.terminalCount) === 1 ? "" : "s"} will open as an external Terminal handoff. `
          + "The launcher cannot monitor those window lifetimes, so saved Terminal surfaces are always treated as new windows."
        );
      }
      if (plan.unverifiedTerminalHandoffCount) {
        warnings.push(
          `The resident route also has ${formatNumber(plan.unverifiedTerminalHandoffCount)} earlier Terminal handoff `
          + `registration${Number(plan.unverifiedTerminalHandoffCount) === 1 ? "" : "s"} whose window state cannot be verified.`
        );
      }
      if (plan.admission?.requiresAcknowledgement) {
        warnings.push(`${plan.admission.label || "Memory review required"}: ${plan.admission.detail || "Review the current memory estimate."}`);
      }
      if (plan.requiresExperimentalApproval) {
        warnings.push("This new native FreeToken load has only tiny-synthetic end-to-end verification. The saved Session Set does not contain approval, and no large model download is recommended.");
      }
      warning.textContent = warnings.join(" ");
      warning.classList.toggle("hidden", warnings.length === 0);
      const needsConsent = Boolean(
        plan.ready
        && plan.mode !== "already-open"
        && (plan.requiresExperimentalApproval || plan.admission?.requiresAcknowledgement)
      );
      consentPanel.classList.toggle("hidden", !needsConsent);
      node("sessionSetConsentTitle").textContent = plan.requiresExperimentalApproval
        ? plan.admission?.requiresAcknowledgement
          ? "I accept this memory estimate and approve this explicit experimental FreeToken run."
          : "I reviewed the evidence and approve this explicit experimental FreeToken run."
        : plan.admission?.requiresAcknowledgement
          ? "I accept this current memory estimate and exact opening plan."
          : "I accept this exceptional opening plan.";
      node("sessionSetConsentCopy").textContent = plan.requiresExperimentalApproval
        ? "This one approval is bound to the current opening plan and is never saved back into the Session Set."
        : plan.mode === "launch"
        ? "This will load one model, open its primary surface, then attach the remaining surfaces to the same private relay."
        : "This will open only the missing surfaces on the already-loaded model.";
      const consentAccepted = !needsConsent || (node("sessionSetConsent").checked && approval === approvalKey(plan));
      openButton.disabled = !plan.ready || store.busy || !consentAccepted;
      openButton.querySelector("strong").textContent = plan.action?.label || (plan.ready ? "Open Session Set" : "Unavailable");
      openButton.querySelector("small").textContent = plan.mode === "launch"
        ? "One shared model route"
        : plan.mode === "reuse"
        ? "No model reload"
        : plan.mode === "already-open"
        ? "No process or window changes"
        : "Resolve the issue above";
    }

    function render() {
      changed();
      const count = store.sets.length;
      const route = currentRoute();
      const operationActive = isActive();
      const locked = store.busy || store.loading || operationActive;
      node("sessionSetCountBadge").textContent = store.loading ? "Loading" : `${count}/${store.limit} saved`;
      node("sessionSetCountBadge").className = `setup-badge${store.loading ? "" : " ready"}`;

      const surfaceCount = route ? Math.max(1, Number(workspace()?.surfaceCount || 0)) : 0;
      node("sessionSetSaveSummary").textContent = route
        ? `${surfaceCount} work surface${surfaceCount === 1 ? "" : "s"} share ${route.model} through ${backendLabel(route.backend)}. Saving captures settings only.`
        : operationActive
        ? (store.status?.message || "A Session Set is opening.")
        : "Start a normal model session to save its current agents and Chats.";
      node("sessionSetName").disabled = locked || !route;
      node("sessionSetSaveButton").disabled = locked || !route || !node("sessionSetName").value.trim();
      node("sessionSetSaveButton").textContent = store.editingId ? "Replace saved set" : "Save current session";
      node("sessionSetCancelEdit").classList.toggle("hidden", !store.editingId);
      node("sessionSetCancelEdit").disabled = locked;

      if (!count) {
        html(node("sessionSetCards"), store.loading
          ? `<div class="session-set-empty"><strong>Checking saved Session Sets…</strong><span>Nothing is being launched.</span></div>`
          : `<div class="session-set-empty"><strong>No Session Sets yet</strong><span>Start one model session, attach the agents and Chats you want, then save that complete workspace above.</span></div>`);
        renderPlan();
        return;
      }
      html(node("sessionSetCards"), store.sets.map(item => {
        const selected = item.id === store.selectedId;
        const editing = item.id === store.editingId;
        const armed = item.id === store.deleteConfirmId;
        const labels = Array.isArray(item.surfaceLabels) ? item.surfaceLabels : [];
        const chips = labels.length
          ? labels.map((label, index) => `<span>${index === 0 ? "Primary · " : ""}${esc(label)}</span>`).join("")
          : `<span>${formatNumber(item.surfaceCount || 0)} saved surface${Number(item.surfaceCount) === 1 ? "" : "s"}</span>`;
        const request = item.baseRequest || {};
        const experimentalFreeToken = item.ready && experimental(request);
        const detail = item.ready
          ? `${backendLabel(request.backend)} · ${formatNumber(item.surfaceCount || 0)} surface${Number(item.surfaceCount) === 1 ? "" : "s"}${item.terminalCount ? ` · ${formatNumber(item.terminalCount)} external Terminal` : ""}${experimentalFreeToken ? " · new model loads need fresh experimental approval" : ""}`
          : (item.reason || "This saved workspace is no longer available.");
        return `<article class="session-set-card ${item.ready ? "ready" : "unavailable"}${selected ? " selected" : ""}">
          <header><div class="session-set-card-title"><i aria-hidden="true">▤</i><span><strong title="${esc(item.name)}">${esc(item.name)}</strong><small title="${esc(item.modelName || request.modelId || "")}">${esc(item.modelName || request.modelId || "Unknown model")} · ${esc(dateLabel(item.updatedAt))}</small></span></div><em>${experimentalFreeToken ? "Review" : item.ready ? "Ready" : "Unavailable"}</em></header>
          <div class="session-set-surfaces">${chips}</div>
          <p class="session-set-card-detail">${esc(detail)}</p>
          <div class="session-set-card-actions"><button type="button" class="primary session-set-review" data-session-set-review="${esc(item.id)}" ${!item.ready || locked ? "disabled" : ""}>Review opening</button><button type="button" class="secondary" data-session-set-apply="${esc(item.id)}" ${!item.ready || locked || !canApply() ? "disabled" : ""}>Apply primary</button><button type="button" class="text-button" data-session-set-edit="${esc(item.id)}" ${locked || !route ? "disabled" : ""}>${editing ? "Replacing" : "Replace"}</button><button type="button" class="danger${armed ? " armed" : ""}" data-session-set-delete="${esc(item.id)}" ${locked ? "disabled" : ""}>${armed ? "Confirm delete" : "Delete"}</button></div>
        </article>`;
      }).join(""));
      renderPlan();
    }

    async function load(initial = false) {
      if (store.loading) return;
      store.loading = true;
      const revision = statusRevision;
      render();
      if (!initial) message("Rechecking saved workspaces against the current models, engines, and live route…");
      try {
        const [inventory, status] = await Promise.all([
          api.inventory(), api.status(),
        ]);
        useInventory(inventory);
        if (revision === statusRevision) useStatus(status, false);
        if (!isActive()) {
          message(countMessage(), "");
        } else {
          message(store.status?.message || "A Session Set is opening.");
        }
      } catch (error) {
        message(error.message, "error");
      } finally {
        store.loading = false;
        render();
      }
    }

    function countMessage() {
      return store.sets.length
        ? "Every saved route was checked locally. Review an opening plan before any model, agent, Chat, or window starts."
        : "Save a running multi-surface workspace above. No model or window starts while saving.";
    }

    async function show() {
      store.deleteConfirmId = "";
      resetReview();
      store.selectedId = isActive() ? (store.status?.setId || "") : "";
      if (!node("sessionSetDialog").open) node("sessionSetDialog").showModal();
      await load(true);
    }

    function resetEditor(clearName = true) {
      store.editingId = "";
      if (clearName) node("sessionSetName").value = "";
      render();
    }

    function edit(setId) {
      const item = store.sets.find(entry => entry.id === setId);
      if (!item || store.busy || !currentRoute()) return;
      store.editingId = item.id;
      store.deleteConfirmId = "";
      node("sessionSetName").value = item.name;
      message(`Replacing “${item.name}”. Saving will use the complete workspace that is running now.`);
      render();
      node("sessionSetName").focus();
    }

    async function save() {
      if (store.busy || store.loading || !currentRoute()) return;
      const name = node("sessionSetName").value.trim();
      if (!name) { message("Give this Session Set a name.", "error"); return; }
      const editing = store.editingId;
      store.busy = true;
      render();
      message(editing ? "Validating and replacing this saved workspace…" : "Validating and saving this running workspace locally…");
      try {
        const body = {name};
        if (editing) body.id = editing;
        const data = await api.save(body);
        useInventory(data);
        if (store.selectedId === editing) store.plan = null;
        store.editingId = "";
        node("sessionSetName").value = "";
        message(editing
          ? "Session Set replaced with the current work surfaces. No new process or window was started."
          : "Session Set saved privately on this Mac. No new process or window was started.", "success");
      } catch (error) {
        message(error.message, "error");
      } finally {
        store.busy = false;
        render();
      }
    }

    async function apply(setId) {
      if (store.busy || !canApply()) return;
      store.busy = true;
      render();
      message("Rechecking the saved primary route before applying its visible controls…");
      try {
        const inventory = await api.inventory();
        useInventory(inventory);
        const item = store.sets.find(entry => entry.id === setId);
        if (!item) throw new Error("That Session Set no longer exists.");
        if (!item.ready) throw new Error(item.reason || "That Session Set is no longer available.");
        applyPrimary(clone(item.baseRequest));
        openEditor();
        if (node("sessionSetDialog").open) node("sessionSetDialog").close();
        notify(`Applied the primary settings from “${item.name}”. Nothing was started.`);
      } catch (error) {
        message(error.message, "error");
        notify(error.message, true);
      } finally {
        store.busy = false;
        render();
      }
    }

    async function remove(setId) {
      if (store.busy || isActive()) return;
      const item = store.sets.find(entry => entry.id === setId);
      if (!item) return;
      if (store.deleteConfirmId !== setId) {
        store.deleteConfirmId = setId;
        message(`Click Confirm delete to permanently remove “${item.name}”.`);
        render();
        return;
      }
      store.busy = true;
      render();
      message(`Deleting “${item.name}”…`);
      try {
        const data = await api.remove({id:setId});
        useInventory(data);
        if (store.selectedId === setId) {
          store.selectedId = "";
          store.plan = null;
        }
        if (store.editingId === setId) resetEditor();
        store.deleteConfirmId = "";
        message(`“${item.name}” was deleted. This settings-only preset cannot be recovered.`, "success");
      } catch (error) {
        message(error.message, "error");
      } finally {
        store.busy = false;
        render();
      }
    }

    async function review(setId) {
      if (store.busy || store.planLoading || isActive()) return;
      const revision = ++reviewRevision;
      store.selectedId = setId;
      store.deleteConfirmId = "";
      store.plan = null;
      store.planLoading = true;
      node("sessionSetConsent").checked = false;
      approval = "";
      message("Building a side-effect-free opening plan…");
      render();
      try {
        const data = await api.plan({id:setId});
        if (revision !== reviewRevision || store.selectedId !== setId) return;
        if (data.plan?.setId !== setId) throw new Error("The saved workspace changed during review. Review its current plan again.");
        store.plan = clone(data.plan);
        message(store.plan?.ready
          ? "Plan ready. Nothing has opened yet."
          : (store.plan?.detail || "This Session Set cannot open yet."),
        store.plan?.ready ? "success" : "error");
      } catch (error) {
        if (revision !== reviewRevision) return;
        store.plan = null;
        message(error.message, "error");
      } finally {
        if (revision !== reviewRevision) return;
        store.planLoading = false;
        render();
        schedule(() => {
          if (revision === reviewRevision && node("sessionSetDialog").open) node("sessionSetPlanPanel").scrollIntoView({behavior:"smooth", block:"nearest"});
        });
      }
    }

    async function open() {
      const plan = store.plan;
      if (!plan?.ready || store.busy || isActive() || plan.setId !== store.selectedId) return;
      const needsConsent = Boolean(
        plan.mode !== "already-open"
        && (plan.requiresExperimentalApproval || plan.admission?.requiresAcknowledgement)
      );
      if (needsConsent && (!node("sessionSetConsent").checked || approval !== approvalKey(plan))) {
        message("Review and approve the exact opening plan first.", "error");
        return;
      }
      const body = {id:plan.setId, confirmation:clone(plan.confirmation)};
      if (plan.requiresExperimentalApproval) {
        body.experimentalQualificationConsent = true;
      }
      if (plan.admission?.requiresAcknowledgement) {
        body.memoryAcknowledgement = plan.admission.contractId;
      }
      store.busy = true;
      render();
      message(plan.mode === "already-open" ? "Confirming the resident workspace…" : "Opening the Session Set…");
      try {
        const data = await api.open(body);
        store.plan = null;
        useStatus(data, true);
        message(data.sessionSet?.message || "Session Set opening started.", data.sessionSet?.phase === "failed" ? "error" : "success");
        await refreshRoute();
      } catch (error) {
        message(error.message, "error");
        notify(error.message, true);
      } finally {
        store.busy = false;
        render();
      }
    }

    async function refreshStatus(announceFinished = true) {
      if (store.statusLoading) return;
      store.statusLoading = true;
      const revision = statusRevision;
      try {
        const data = await api.status();
        if (revision !== statusRevision) return;
        useStatus(data, announceFinished);
        if (isActive()) message(store.status?.message || "A Session Set is opening.");
        render();
      } catch (_) {
        // The main controller poll owns connection-loss messaging.
      } finally {
        store.statusLoading = false;
      }
    }

    async function stop() {
      if (store.busy || !isActive()) return;
      store.busy = true;
      render();
      try {
        const data = await api.stop();
        useStatus(data, false);
        message(data.sessionSet?.message || "Stopping the remaining work surfaces…");
      } catch (error) {
        message(error.message, "error");
      } finally {
        store.busy = false;
        render();
      }
    }

    node("openSessionSets").addEventListener("click", show);
    node("sessionSetDialog").addEventListener("close", () => { resetReview(); render(); });
    node("sessionSetName").addEventListener("input", render);
    node("sessionSetName").addEventListener("keydown", event => {
      if (event.key === "Enter" && !node("sessionSetSaveButton").disabled) { event.preventDefault(); void save(); }
    });
    node("sessionSetSaveButton").addEventListener("click", save);
    node("sessionSetCancelEdit").addEventListener("click", () => {
      resetEditor(); message("Replacement cancelled. Saved Session Sets were not changed.");
    });
    node("sessionSetConsent").addEventListener("change", acceptConsent);
    node("sessionSetOpenButton").addEventListener("click", open);
    node("sessionSetStopButton").addEventListener("click", stop);
    node("sessionSetCards").addEventListener("click", event => {
      const button = event.target.closest("button");
      if (!button || button.disabled) return;
      for (const [name, action] of [["review", review], ["apply", apply], ["edit", edit], ["delete", remove]]) {
        const id = button.getAttribute(`data-session-set-${name}`);
        if (id != null) { void action(id); break; }
      }
    });

    return {render, renderPlan, load, show, resetEditor, edit, save, apply, remove, review, open,
      refreshStatus, stop, useInventory, useStatus, message, isActive,
      acceptConsent,
      isBlocked:() => store.busy || store.loading || store.planLoading || isActive(),
      readySet:() => clone(store.sets.find(item => item.ready) || null),
      hasReadySet:id => store.sets.some(item => item.id === id && item.ready),
      snapshot:() => clone(store)};
  }
  return {createController};
});
