(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LLMChatResume = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function decisionPayload(plan, historyId, {prompt = "", withoutPrompt = false} = {}) {
    const payload = {id:historyId};
    if (!plan?.requiresSystemPrompt) return payload;
    if (prompt && withoutPrompt) throw new Error("Choose a replacement system prompt or continue without it, not both.");
    if (!prompt && !withoutPrompt) throw new Error("Re-enter the original system prompt or explicitly continue without it.");
    if (prompt) payload.systemPrompt = prompt;
    else payload.continueWithoutSystemPrompt = true;
    return payload;
  }

  function createController({elements, fetchPlan, requestVisible, engineVisible,
    formatNumber, formatBytes, detailed, applyRequest, launchRequest,
    openTranscript, readyToOpen, onApplied, notify, beforeOpen = () => {}, onChange = () => {}}) {
    const e = elements;
    const document = e.route.ownerDocument;
    let historyId = "", plan = null, loading = false, starting = false;
    let generation = 0, pending = null, opening = false, error = "";
    let renderedPlan, renderedLoading, memoryConsentId = "", experimentalConsentId = "";
    const clone = value => JSON.parse(JSON.stringify(value));
    const make = (tag, className, text) => {
      const node = document.createElement(tag);
      if (className) node.className = className;
      if (text !== undefined) node.textContent = String(text ?? "");
      return node;
    };
    const changed = () => onChange({starting, pending:Boolean(pending), opening});
    const choices = () => ({prompt:e.systemPrompt.value, withoutPrompt:e.withoutPrompt.checked});
    const memoryId = value => value?.admission?.contractId || "";
    const experimentalId = value => value?.experimentalContractId || JSON.stringify(value?.request || null);
    const routeReady = value => Boolean(value && value.mode !== "blocked" && value.route && value.request);
    const promptReady = () => !plan?.requiresSystemPrompt || Boolean(e.systemPrompt.value || e.withoutPrompt.checked);

    function clearPrivateChoices() {
      e.systemPrompt.value = "";
      e.withoutPrompt.checked = false;
      e.memoryConsent.checked = false;
      e.experimentalConsent.checked = false;
      memoryConsentId = experimentalConsentId = "";
    }

    function fact(label, value, title = false) {
      const item = make("span");
      const strong = make("strong", "", value);
      if (title) strong.title = String(value ?? "");
      item.append(make("small", "", label), strong);
      return item;
    }

    function renderRoute() {
      // Typed prompts and consent changes leave this tree in place. Native
      // details state, focus, selection and scroll therefore survive input.
      if (renderedPlan === plan && (plan || renderedLoading === loading)) return;
      renderedPlan = plan; renderedLoading = loading;
      const previousDetails = e.route.querySelector("details");
      const detailsOpen = previousDetails ? previousDetails.open : detailed();
      const route = plan?.route;
      e.route.className = `chat-resume-route${plan?.mode === "blocked" ? " blocked" : routeReady(plan) ? " ready" : ""}`;
      if (loading && !plan) {
        e.route.replaceChildren(make("p", "", "Revalidating the saved engine, model, folder, controls, and current Mac capacity…"));
      } else if (route) {
        const mode = plan.mode === "reuse" ? "Reuse loaded weights" : plan.mode === "launch" ? "New local load" : "Blocked";
        const reasoning = `${route.reasoning} · ${route.sampling === "custom" ? "custom" : "model defaults"}`;
        const primary = make("div", "chat-resume-primary");
        primary.append(fact("Engine", route.backendLabel), fact("Model", route.model, true), fact("Action", mode));
        const details = make("details", "chat-resume-contract");
        details.id = "chatResumeContract"; details.open = detailsOpen;
        const summary = make("summary");
        const copy = make("span");
        copy.append(make("strong", "", "Route details"), make("small", "",
          `${formatNumber(route.context)} context · ${formatNumber(route.output)} max · ${reasoning}`));
        const icon = make("i", "", "⌄"); icon.setAttribute("aria-hidden", "true");
        summary.append(copy, icon);
        const estimate = plan.admission?.estimate?.estimatedWorkingSetBytes;
        const facts = make("div", "chat-resume-facts");
        facts.append(fact("Context", formatNumber(route.context)), fact("Max response", formatNumber(route.output)),
          fact("Reasoning · sampling", reasoning), fact("Project folder", route.project, true),
          fact("Memory estimate", estimate ? formatBytes(estimate) : plan.mode === "reuse" ? "Already resident" : "Unavailable"),
          fact("System prompt", plan.requiresSystemPrompt ? "Re-entry required" : "None saved or required"));
        details.append(summary, facts);
        e.route.replaceChildren(primary, details,
          make("p", "chat-resume-route-detail", plan.detail || "Review this exact route before starting."));
      } else {
        e.route.replaceChildren(make("p", "", plan?.detail || "This conversation has no resumable route snapshot."));
      }
    }

    function render() {
      const blocked = plan?.mode === "blocked", ready = routeReady(plan);
      e.badge.textContent = loading ? "Checking" : blocked ? "Blocked" : ready ? "Ready" : "Unavailable";
      e.badge.className = `setup-badge ${loading ? "active" : blocked ? "warning" : ready ? "ready" : ""}`;
      e.title.textContent = plan?.thread?.title || "Resume previous chat";
      e.subtitle.textContent = plan?.route ? `${plan.route.backendLabel} · ${plan.route.model}`
        : "Review the exact saved route before anything starts.";
      renderRoute();
      e.promptPanel.classList.toggle("hidden", !plan?.requiresSystemPrompt);
      e.systemPrompt.disabled = e.withoutPrompt.checked || loading || starting;
      e.memoryPanel.classList.toggle("hidden", !plan?.requiresMemoryAcknowledgement);
      e.memoryTitle.textContent = plan?.admission?.label || "I reviewed this Mac capacity estimate.";
      e.memoryCopy.textContent = plan?.admission?.detail || "This one-time acknowledgement is bound to the exact saved route.";
      e.experimentalPanel.classList.toggle("hidden", !plan?.requiresExperimentalApproval);
      e.status.textContent = error || (loading
        ? "Checking only; no runtime, model weights, port, project files, or Chat surface has been opened."
        : plan?.detail || "Choose a resumable conversation.");
      e.status.className = `session-dashboard-status${error || blocked ? " error" : ""}`;
      e.apply.disabled = !ready || !promptReady() || loading || starting;
      e.start.disabled = Boolean(e.apply.disabled || (plan?.requiresMemoryAcknowledgement && !e.memoryConsent.checked)
        || (plan?.requiresExperimentalApproval && !e.experimentalConsent.checked));
      e.startLabel.textContent = starting ? "Starting exact saved route…"
        : plan?.mode === "reuse" ? "No model reload" : plan?.mode === "launch" ? "Normal local safeguards apply" : "Route unavailable";
    }

    function acceptPlan(value) {
      if (e.memoryConsent.checked && memoryConsentId !== memoryId(value)) {
        e.memoryConsent.checked = false; memoryConsentId = "";
      }
      if (e.experimentalConsent.checked && experimentalConsentId !== experimentalId(value)) {
        e.experimentalConsent.checked = false; experimentalConsentId = "";
      }
      plan = value;
    }

    async function load(id, includeDecision = false) {
      const serial = ++generation;
      loading = true; error = ""; render();
      let payload;
      try {
        payload = includeDecision ? decisionPayload(plan, id, choices()) : {id};
      } catch (failure) {
        loading = false; error = failure.message; render();
        return null;
      }
      try {
        const data = await fetchPlan(payload);
        if (serial !== generation || id !== historyId) return null;
        const next = data.plan;
        if (next?.request && !requestVisible(next.request)) {
          acceptPlan({mode:"blocked", ready:false,
            detail:"This conversation is preserved, but its saved engine is temporarily hidden in this launcher build.",
            thread:next.thread || {id, title:"Resume previous chat"}});
          return plan;
        }
        acceptPlan(next);
        return next;
      } catch (failure) {
        if (serial === generation && id === historyId) {
          error = failure.message;
          acceptPlan({mode:"blocked", ready:false, detail:failure.message,
            thread:{id, title:"Resume previous chat"}});
        }
        return null;
      } finally {
        if (serial === generation) { loading = false; render(); }
      }
    }

    async function open(id, summary = null) {
      if (starting || !id) return null;
      if (summary && !engineVisible(summary.backend)) {
        notify("That transcript is still available in Chats, but its saved engine is temporarily hidden.");
        return null;
      }
      historyId = id; plan = null; error = "";
      clearPrivateChoices();
      beforeOpen();
      if (!e.dialog.open) e.dialog.showModal();
      render();
      return load(id, false);
    }

    async function completePending() {
      if (!pending?.accepted || opening || !readyToOpen()) return false;
      const current = pending;
      opening = true; changed();
      try {
        await openTranscript(current.historyId, {coldResume:true, skipCurrentSave:true,
          systemPromptDecision:current.systemPromptDecision});
        return true;
      } finally {
        pending = null; opening = false; starting = false;
        plan = null; clearPrivateChoices(); changed(); render();
      }
    }

    async function apply(startAfter) {
      if (starting || !historyId) return false;
      starting = true; error = ""; render(); changed();
      try {
        const next = await load(historyId, true);
        if (!next?.ready || !next.request || next.mode === "blocked") throw new Error(next?.detail || error || "The saved Chat route is not ready.");
        if (!requestVisible(next.request)) throw new Error("This conversation's saved engine is temporarily hidden in this launcher build.");
        if (startAfter && next.requiresMemoryAcknowledgement && !e.memoryConsent.checked) {
          throw new Error("Review and approve the current Mac capacity estimate first.");
        }
        if (startAfter && next.requiresExperimentalApproval && !e.experimentalConsent.checked) {
          throw new Error("Approve this one experimental FreeToken load first.");
        }
        const request = clone(next.request);
        if (startAfter && next.requiresMemoryAcknowledgement) request.memoryAcknowledgement = memoryId(next);
        if (startAfter && next.requiresExperimentalApproval) {
          request.options = {...(request.options || {}), experimentalQualificationConsent:true};
        }
        // Applying controls receives a separate copy; a view adapter cannot
        // silently alter the exact request subsequently sent to the launcher.
        await applyRequest(clone(request));
        if (!startAfter) {
          e.dialog.close();
          notify(`Applied the saved route for “${next.thread?.title || "Local chat"}”. Nothing was started.`);
          onApplied(); starting = false; plan = null; clearPrivateChoices(); changed(); render();
          return true;
        }
        pending = {historyId, title:next.thread?.title || "saved chat", accepted:false,
          systemPromptDecision:next.systemPromptDecision || "not-required"};
        e.dialog.close(); changed();
        const started = await launchRequest(request, {warmPlan:next.warmRoute});
        if (!started) { pending = null; starting = false; plan = null; clearPrivateChoices(); changed(); render(); return false; }
        if (pending) pending.accepted = true;
        await completePending();
        return true;
      } catch (failure) {
        pending = null; starting = false; error = failure.message;
        if (!e.dialog.open) e.dialog.showModal();
        render(); changed();
        return false;
      }
    }

    function stopped(message) {
      if (!pending?.accepted) return;
      const title = pending.title;
      pending = null; starting = false; opening = false; plan = null;
      clearPrivateChoices(); render(); changed();
      notify(`Could not resume “${title}”: ${message || "the saved route stopped before Chat became ready."}`, true);
    }

    e.systemPrompt.addEventListener("input", render);
    e.withoutPrompt.addEventListener("change", () => {
      if (e.withoutPrompt.checked) e.systemPrompt.value = "";
      render();
    });
    e.memoryConsent.addEventListener("change", () => {
      memoryConsentId = e.memoryConsent.checked ? memoryId(plan) : ""; render();
    });
    e.experimentalConsent.addEventListener("change", () => {
      experimentalConsentId = e.experimentalConsent.checked ? experimentalId(plan) : ""; render();
    });
    e.apply.addEventListener("click", () => { void apply(false); });
    e.start.addEventListener("click", () => { void apply(true); });
    e.dialog.addEventListener("close", () => {
      if (starting || pending) return;
      generation += 1; loading = false; plan = null; error = "";
      clearPrivateChoices(); render();
    });

    return {open, load, render, apply, completePending, stopped,
      isStarting:() => starting, hasPending:() => Boolean(pending),
      pendingHistoryId:() => pending?.historyId || ""};
  }

  return {createController, decisionPayload};
});
