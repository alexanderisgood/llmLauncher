(function installSavedLaunches(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LLMSavedLaunches = api;
})(typeof globalThis === "object" ? globalThis : this, function savedLaunchesFactory() {
  "use strict";
  const clone = value => value == null ? value : JSON.parse(JSON.stringify(value));
  const esc = value => String(value ?? "").replace(/[&<>"']/g, character => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[character]);
  const APPLIED_PROFILE_KEY = "llm-launcher-applied-profile-v1";
  function createController({elements, api, visible, externalSettingsReason, externalLaunchReason,
    sessionActive, currentRoute, routeKey, selectedRequest, applyRequest, launchVisible,
    copyEvidence, activeEvidence, applyEvidence, backendLabel, clientName, dateLabel, formatNumber,
    kvLabel, preferenceLabels, isExperimental, needsExperimentalConsent, storage,
    restoreProject, refreshControls, openEditor, openEditSettings, revealSettings, focusSettings,
    revealExperimental, openSessions, shortcutContext, acceptSessionSets, acceptHistory,
    reviewSessionSet, openChatShortcut, notify, schedule = callback => requestAnimationFrame(callback)}) {
    const store = {profiles:[],limit:32,loading:false,busy:false,editingId:"",deleteConfirmId:"",
      editingEvidence:null,projectRestored:false,shortcutLoading:false,shortcutLoaded:false,
      shortcutError:"",shortcutsOpen:false};
    const node = id => elements[id];
    let inventoryRevision = 0;
    let shortcutPending = null, inventoryPending = null;
    const markup = new WeakMap();
    function html(element, value) {
      if (markup.get(element) === value) return;
      const focused = element.ownerDocument?.activeElement;
      const action = focused && element.contains?.(focused)
        ? ["profile-launch","profile-apply","profile-edit","profile-delete","quick-profile-launch","quick-session-review","quick-chat"]
          .map(name => [`data-${name}`,focused.getAttribute?.(`data-${name}`)]).find(([, id]) => id != null) : null;
      element.innerHTML = value; markup.set(element,value);
      if (action) [...element.querySelectorAll("button")].find(button=>button.getAttribute(action[0])===action[1]&&!button.disabled)?.focus({preventScroll:true});
    }
    function runBlocked() {
      return Boolean(launchBlockReason());
    }

    function settingsBlockReason() {
      if (store.busy) return "Wait for the current profile change to finish.";
      if (store.loading) return "Saved profiles are still loading.";
      return externalSettingsReason();
    }
    function launchBlockReason() { return externalLaunchReason() || settingsBlockReason(); }

    function renderRunNotice() {
      const reason = launchBlockReason();
      node("profileRunNotice").hidden = !reason;
      node("profileRunMessage").textContent = reason;
      node("profileRunAction").hidden = !sessionActive();
    }

    function renderEditBanner() {
      node("profileEditBanner").hidden = !store.editingId;
      node("profileEditName").textContent = `Editing “${node("profileName").value.trim()}”`;
      node("profileEditSave").disabled = Boolean(settingsBlockReason()) || !node("profileName").value.trim();
      node("profileEditCancel").disabled = Boolean(settingsBlockReason());
    }

    function measuredBinding(profile = {}) {
      if (profile.enginePolicy !== "measured") return null;
      const binding = copyEvidence(profile.evidenceBinding);
      const resolvedBackend = String(profile.resolution?.backend || "");
      if (!binding || binding.preference !== profile.enginePreference) return null;
      if (binding.scope === "route") return binding;
      return binding.scope === "engine"
        && (!resolvedBackend || typeof binding.recordIds?.[resolvedBackend] === "string")
        ? binding : null;
    }

    function isReady(profile = {}) {
      return Boolean(
        profile.ready === true
        && (profile.enginePolicy !== "measured" || measuredBinding(profile)),
      );
    }

    function reason(profile = {}) {
      if (profile.ready !== true) {
        return profile.reason || "This saved route is no longer available.";
      }
      if (profile.enginePolicy === "measured" && !measuredBinding(profile)) {
        return "Run Calibration again before using this measured profile.";
      }
      return profile.resolution?.detail || "Ready to apply.";
    }

    function shortcutEntries() {
      const {sessionSet, chat} = shortcutContext();
      return clone({profile:store.profiles.find(isReady) || null, sessionSet, chat});
    }

    function renderShortcuts() {
      const panel = node("quickStart");
      if (!panel) return;
      const {profile, sessionSet, chat} = shortcutEntries();
      const available = Boolean(store.shortcutLoaded && (profile || sessionSet || chat || store.shortcutError));
      panel.classList.toggle("hidden", !available);
      node("customLaunchEditor").classList.remove("quick-start-collapsed");
      node("customLaunchEditor").removeAttribute("inert");
      node("customLaunchEditor").setAttribute("aria-hidden", "false");
      node("launchDock").classList.remove("quick-start-collapsed");
      const count = [profile, sessionSet, chat].filter(Boolean).length;
      if (!available) store.shortcutsOpen = false;
      node("quickStartSummary").textContent = available
        ? `${count} optional shortcut${count === 1 ? "" : "s"}`
        : "Optional shortcuts are available.";
      node("quickStartCustom").setAttribute("aria-expanded", String(store.shortcutsOpen));
      node("quickStartCustom").textContent = store.shortcutsOpen ? "Hide saved routes" : "Show saved routes";
      node("quickStartCards").classList.toggle("hidden", !store.shortcutsOpen);
      node("quickStartStatus").textContent = store.shortcutError;
      node("quickStartStatus").hidden = !store.shortcutError;
      if (!available) {
        html(node("quickStartCards"), "");
        return;
      }
      const profileBlocked = runBlocked() || store.busy || store.shortcutLoading;
      const sessionBlocked = shortcutContext().sessionBlocked || store.shortcutLoading;
      const chatBlocked = shortcutContext().chatBlocked || store.shortcutLoading;
      const cards = [];
      if (profile) {
        const request = profile.request || {};
        const experimental = isExperimental(request);
        const engine = profile.resolution?.label || backendLabel(request.backend);
        cards.push(`<article class="quick-start-card profile"><span class="quick-start-icon" aria-hidden="true">▣</span><div><small>Launch profile</small><strong title="${esc(profile.name)}">${esc(profile.name)}</strong><span title="${esc(profile.modelName || request.modelId || "")}">${esc(profile.modelName || request.modelId || "Local model")} · ${esc(engine)} · ${esc(clientName(request.client))}</span></div><button type="button" class="primary" data-quick-profile-launch="${esc(profile.id)}"${profileBlocked ? " disabled" : ""}>${experimental ? "Review" : "Launch"}</button></article>`);
      }
      if (sessionSet) {
        const request = sessionSet.baseRequest || {};
        const count = Number(sessionSet.surfaceCount || 0);
        cards.push(`<article class="quick-start-card session-set"><span class="quick-start-icon" aria-hidden="true">▤</span><div><small>Session Set</small><strong title="${esc(sessionSet.name)}">${esc(sessionSet.name)}</strong><span title="${esc(sessionSet.modelName || request.modelId || "")}">${esc(sessionSet.modelName || request.modelId || "Local model")} · ${formatNumber(count)} surface${count === 1 ? "" : "s"}</span></div><button type="button" class="secondary" data-quick-session-review="${esc(sessionSet.id)}"${sessionBlocked ? " disabled" : ""}>Review</button></article>`);
      }
      if (chat) {
        const activeChat = shortcutContext().chatActive;
        cards.push(`<article class="quick-start-card chat"><span class="quick-start-icon" aria-hidden="true">●</span><div><small>Previous chat</small><strong title="${esc(chat.title || "Local chat")}">${esc(chat.title || "Local chat")}</strong><span title="${esc(chat.model || "Local model")}">${esc(chat.model || "Local model")} · ${esc(backendLabel(chat.backend))}${chat.resumeNeedsSystemPrompt ? " · prompt re-entry" : ""}</span></div><button type="button" class="secondary" data-quick-chat="${esc(chat.id)}"${chatBlocked ? " disabled" : ""}>${activeChat ? "Open" : "Review"}</button></article>`);
      }
      html(node("quickStartCards"), cards.join(""));
    }

    function toggleShortcuts() {
      store.shortcutsOpen = !store.shortcutsOpen;
      renderShortcuts();
      if (store.shortcutsOpen) schedule(() => {
        node("quickStartCards").scrollIntoView({behavior:"smooth", block:"nearest"});
      });
    }

    function loadShortcuts(force = false) {
      if (shortcutPending) return shortcutPending;
      if (store.shortcutLoaded && !force) {
        renderShortcuts();
        return Promise.resolve();
      }
      shortcutPending = readShortcuts().finally(() => { shortcutPending = null; });
      return shortcutPending;
    }
    async function readShortcuts() {
      store.shortcutLoading = true;
      const revision = inventoryRevision;
      store.shortcutError = "";
      renderShortcuts();
      const [profiles, sessionSets, chatHistory] = await Promise.allSettled([
        api.inventory(), api.sessionSets(), api.history(),
      ]);
      if (profiles.status === "fulfilled" && revision === inventoryRevision) useInventory(profiles.value);
      if (sessionSets.status === "fulfilled") acceptSessionSets(sessionSets.value);
      if (chatHistory.status === "fulfilled" && Array.isArray(chatHistory.value.threads)) {
        acceptHistory(chatHistory.value);
      }
      const errors = [profiles, sessionSets, chatHistory]
        .filter(result => result.status === "rejected")
        .map(result => result.reason?.message || "Saved routes could not be checked.");
      store.shortcutError = errors.join(" ");
      store.shortcutLoaded = true;
      store.shortcutLoading = false;
      renderShortcuts();
    }

    function setMessage(message, kind = "") {
      const status = node("profileManagerStatus");
      status.textContent = message;
      status.className = `profile-manager-status${kind ? ` ${kind}` : ""}`;
      node("profileEditStatus").textContent = message;
      if (!node("profileDialog").open) notify(message, kind === "error");
    }

    function remember(profile = null) {
      // Keep only a preset reference in the browser, never a private project path.
      try {
        const profileStorage = storage();
        if (profile?.id) profileStorage?.setItem(APPLIED_PROFILE_KEY, profile.id);
        else profileStorage?.removeItem(APPLIED_PROFILE_KEY);
      } catch (_error) { /* Browsing with storage disabled remains usable. */ }
    }

    function restoreProjectOnce() {
      if (store.projectRestored) return;
      store.projectRestored = true;
      let id;
      try { id = storage()?.getItem(APPLIED_PROFILE_KEY); }
      catch (_error) { return; }
      const profile = store.profiles.find(item => item.id === id);
      const route = currentRoute();
      if (!route || !profile?.request?.project
          || routeKey(route) !== routeKey(profile.request)) return;
      restoreProject(profile.request.project);
    }

    function useInventory(data) {
      inventoryRevision += 1;
      store.profiles = Array.isArray(data?.profiles) ? clone(data.profiles.filter(visible)) : [];
      store.limit = Number(data?.limit || 32);
      restoreProjectOnce();
      renderShortcuts();
    }

    function updateControls() {
      const measured = node("profilePolicySelect").value === "measured";
      const lockReason = settingsBlockReason();
      const locked = Boolean(lockReason);
      node("profileGoalField").classList.toggle("inactive", !measured);
      node("profileGoalSelect").disabled = !measured || locked;
      node("profilePolicyHelp").textContent = measured
        ? "Rechecks matching measurements whenever this profile is applied."
        : "Reuses the selected engine and exact runtime controls.";
      node("profileName").disabled = locked;
      node("profilePolicySelect").disabled = locked;
      node("profileSaveButton").disabled = locked || !node("profileName").value.trim();
      node("profileSaveButton").title = lockReason || (!node("profileName").value.trim() ? "Enter a profile name to save these settings." : "");
      node("profileNameHint").textContent = !node("profileName").value.trim() ? "Enter a name to enable saving." : store.editingId ? "Updates this saved profile." : "Saves the settings shown in the launcher.";
      node("profileCancelEdit").disabled = locked;
      node("profileCancelEdit").classList.toggle("hidden", !store.editingId);
      node("profileSaveButton").querySelector("strong").textContent = store.editingId ? "Update profile" : "Save current settings";
      node("profileSaveButton").querySelector("small").textContent = !node("profileName").value.trim() ? "Enter a profile name" : store.editingId ? "Save edited settings" : "Nothing starts";
      renderEditBanner();
    }

    function render() {
      renderShortcuts();
      const count = store.profiles.length;
      node("profileCountBadge").textContent = store.loading ? "Loading" : `${count}/${store.limit} saved`;
      const settingsBlock = settingsBlockReason();
      const launchBlock = launchBlockReason();
      renderRunNotice();
      if (!count && !store.loading) {
        html(node("profileCards"), `<div class="profile-empty"><strong>No launch profiles yet</strong><span>Name the current setup above to save its engine, model, work surface, limits, reasoning, sampling, KV precision, and runtime controls.</span></div>`);
        updateControls();
        return;
      }
      html(node("profileCards"), store.profiles.map(profile => {
        const request = profile.request || {};
        const options = request.options || {};
        const experimentalFreeToken = profile.ready && isExperimental(request);
        const resolution = profile.resolution || {};
        const policy = profile.enginePolicy === "measured";
        const ready = isReady(profile);
        const engine = resolution.label || backendLabel(request.backend);
        const policyLabel = policy
          ? `${preferenceLabels[profile.enginePreference] || "Measured goal"} · ${engine}`
          : `Fixed · ${engine}`;
        const resolutionDetail = ready
          ? experimentalFreeToken
            ? "Settings are reusable; experimental approval is deliberately never saved. Review it before a new model run."
            : reason(profile)
          : reason(profile);
        const applyReason = settingsBlock || (!ready ? reason(profile) : "");
        const launchReason = launchBlock || applyReason;
        const editReason = settingsBlock || (!request.modelId ? "This profile has no saved model settings to edit." : "");
        const armed = store.deleteConfirmId === profile.id;
        const editing = store.editingId === profile.id;
        const client = clientName(request.client || "");
        const limits = request.context && request.output
          ? `${formatNumber(request.context)} / ${formatNumber(request.output)}`
          : "Unavailable";
        const kv = kvLabel(request.backend, options);
        return `<article class="profile-card ${ready ? "ready" : "unavailable"}${editing ? " editing" : ""}">
          <header><div class="profile-card-title"><span class="profile-card-icon" aria-hidden="true">${policy ? "◇" : "▣"}</span><span><strong title="${esc(profile.name)}">${esc(profile.name)}</strong><small title="${esc(profile.modelName || request.modelId || "")}">${esc(profile.modelName || request.modelId || "Unknown model")} · ${esc(dateLabel(profile.updatedAt))}</small></span></div><em class="profile-card-state">${experimentalFreeToken ? "Review" : ready ? "Ready" : policy ? "Needs test" : "Unavailable"}</em></header>
          <div class="profile-contract"><span><small>Surface</small><b>${esc(client)}</b></span><span><small>Context / output</small><b>${esc(limits)}</b></span><span><small>Reasoning</small><b>${esc(request.reasoning || "auto")}</b></span><span><small>KV precision</small><b>${esc(kv)}</b></span></div>
          <code class="profile-project" title="${esc(request.project || "")}">${esc(request.project || "Project unavailable")}</code>
          <div class="profile-resolution"><i aria-hidden="true">${ready ? (resolution.trustedWinner ? "◆" : "◇") : "×"}</i><span><strong>${esc(policyLabel)}</strong><small>${esc(resolutionDetail)}</small></span></div>
          <div class="profile-actions"><button type="button" class="primary profile-launch" data-profile-launch="${esc(profile.id)}" title="${esc(launchReason)}" ${launchReason ? "disabled" : ""}>${experimentalFreeToken ? "Review" : "Launch"}</button><button type="button" class="secondary" data-profile-apply="${esc(profile.id)}" title="${esc(applyReason || "Load these settings for your next launch")}" ${applyReason ? "disabled" : ""}>Apply</button><button type="button" class="text-button" data-profile-edit="${esc(profile.id)}" title="${esc(editReason || "Load this profile's settings in the editor")}" ${editReason ? "disabled" : ""}>${editing ? "Editing" : "Edit"}</button><button type="button" class="danger profile-delete${armed ? " armed" : ""}" data-profile-delete="${esc(profile.id)}" ${store.busy ? "disabled" : ""}>${armed ? "Confirm delete" : "Delete"}</button></div>
        </article>`;
      }).join(""));
      updateControls();
    }

    function load() {
      if (inventoryPending) return inventoryPending;
      if (store.busy) return Promise.resolve();
      inventoryPending = readInventory().finally(() => { inventoryPending = null; });
      return inventoryPending;
    }
    async function readInventory() {
      store.loading = true;
      const revision = inventoryRevision;
      render();
      setMessage("Rechecking every saved route against the current model catalog and installed engines…");
      try {
        const data = await api.inventory();
        if (revision === inventoryRevision) useInventory(data);
        setMessage(store.profiles.length
          ? "Apply loads settings for your next launch. Edit opens the saved settings to change them."
          : "Save the current visible setup above. No engine will start.");
      } catch (error) {
        setMessage(error.message, "error");
      } finally {
        store.loading = false;
        render();
      }
    }

    async function show() {
      store.deleteConfirmId = "";
      openEditor();
      if (!node("profileDialog").open) node("profileDialog").showModal();
      await load();
    }

    function resetEditor(clearName = true) {
      store.editingId = "";
      store.editingEvidence = null;
      if (clearName) node("profileName").value = "";
      node("profilePolicySelect").value = "fixed";
      node("profileGoalSelect").value = "throughput";
      render();
    }

    async function edit(profileId) {
      return apply(profileId, false, true);
    }

    async function apply(profileId, launchAfter = false, editAfter = false) {
      const blocker = launchAfter ? launchBlockReason() : settingsBlockReason();
      if (blocker) { setMessage(blocker, "error"); return; }
      store.busy = true;
      store.deleteConfirmId = "";
      refreshControls();
      setMessage("Rechecking this profile against current local engines, models, and measurements…");
      try {
        const inventory = await api.inventory();
        useInventory(inventory);
        const profile = store.profiles.find(item => item.id === profileId);
        if (!profile) throw new Error("That launch profile no longer exists.");
        if (!editAfter && !isReady(profile)) throw new Error(reason(profile));
        // A failed replacement must not leave Save targeting the previous preset.
        if (store.editingId) resetEditor();
        applyRequest(clone(profile.request));
        if (!editAfter && profile.enginePolicy === "measured") {
          const binding = measuredBinding(profile);
          const scope = binding?.scope === "route" ? "current" : "engine";
          setMessage(`Applying “${profile.name}” and rechecking its measured result…`);
          const optimized = await applyEvidence(scope, profile.enginePreference, binding);
          if (!optimized) throw new Error("The measured engine decision could not be applied. The profile was not launched.");
        }
        remember(profile);
        store.editingId = editAfter ? profile.id : "";
        store.editingEvidence = editAfter ? copyEvidence(profile.evidenceBinding) : null;
        if (editAfter) {
          node("profileName").value = profile.name;
          node("profilePolicySelect").value = profile.enginePolicy;
          node("profileGoalSelect").value = profile.enginePreference;
          openEditSettings();
          setMessage(`Change the settings below, then save “${profile.name}”. The running session keeps its current settings.`);
        }
        renderEditBanner();
        if (launchAfter && needsExperimentalConsent()) {
          openEditor();
          if (node("profileDialog").open) node("profileDialog").close();
          revealExperimental();
          notify(`Applied “${profile.name}”. Its FreeToken approval was not saved; review the amber checkpoint evidence and approve this new experimental run before launching.`);

          return;
        }
        if (launchAfter) {
          setMessage(`Launching “${profile.name}” with the revalidated visible contract…`);
          const started = await launchVisible();
          if (!started) throw new Error("The profile was applied, but final launch validation did not accept it.");
          if (node("profileDialog").open) node("profileDialog").close();
        } else {
          revealSettings();
          openEditor();
          if (node("profileDialog").open) node("profileDialog").close();
          notify(editAfter ? `Editing “${profile.name}”. Save changes when ready.` : `Applied “${profile.name}” for your next launch. The running session keeps its current settings.`);
          schedule(() => focusSettings(editAfter));
        }
      } catch (error) {
        if (launchAfter) openEditor();
        setMessage(error.message, "error");
        notify(error.message, true);
      } finally {
        store.busy = false;
        refreshControls();
        updateControls();
        if (node("profileDialog").open) render();
      }
    }

    async function save() {
      const blocker = settingsBlockReason();
      if (blocker) { setMessage(blocker, "error"); return; }
      let request;
      try { request = selectedRequest(); }
      catch (error) { setMessage(error.message, "error"); return; }
      const name = node("profileName").value.trim();
      if (!name) { setMessage("Give this launch profile a name.", "error"); return; }
      const editing = store.editingId;
      let message = "", failed = false;
      store.busy = true;
      inventoryRevision += 1;
      refreshControls();
      setMessage(editing ? "Validating and updating this local profile…" : "Validating and saving these settings locally…");
      try {
        const body = {
          name,
          enginePolicy:node("profilePolicySelect").value,
          enginePreference:node("profileGoalSelect").value,
          request,
        };
        if (body.enginePolicy === "measured") {
          const savedBinding = store.editingEvidence;
          const binding = activeEvidence("engine", body.enginePreference)
            || activeEvidence("route", body.enginePreference)
            || (savedBinding?.preference === body.enginePreference ? savedBinding : null);
          if (binding) body.evidenceBinding = binding;
        }
        if (editing) body.id = editing;
        const data = await api.save(body);
        useInventory(data);
        if (editing) remember(store.profiles.find(item => item.id === editing));
        store.editingId = "";
        store.editingEvidence = null;
        node("profileName").value = "";
        node("profilePolicySelect").value = "fixed";
        node("profileGoalSelect").value = "throughput";
        message = editing ? "Profile updated. The running session keeps its current settings." : "Profile saved privately on this Mac. Nothing was started.";
      } catch (error) {
        message = error.message;
        failed = true;
      } finally {
        store.busy = false;
        refreshControls();
        render();
        setMessage(message, failed ? "error" : "success");
      }
    }

    async function remove(profileId) {
      if (store.busy) return;
      const profile = store.profiles.find(item => item.id === profileId);
      if (!profile) return;
      if (store.deleteConfirmId !== profileId) {
        store.deleteConfirmId = profileId;
        setMessage(`Click Confirm delete to permanently remove “${profile.name}”.`);
        render();
        return;
      }
      store.busy = true;
      inventoryRevision += 1;
      render();
      setMessage(`Deleting “${profile.name}”…`);
      try {
        const data = await api.remove({id:profileId});
        useInventory(data);
        if (store.editingId === profileId) resetEditor();
        store.deleteConfirmId = "";
        setMessage(`“${profile.name}” was deleted. This local preset cannot be recovered.`, "success");
      } catch (error) {
        setMessage(error.message, "error");
      } finally {
        store.busy = false;
        render();
      }
    }
    node("openProfileManager").addEventListener("click",show);
    node("profileRunAction").addEventListener("click",()=>{node("profileDialog").close();openSessions();});
    node("profileEditSave").addEventListener("click",save);
    node("profileEditCancel").addEventListener("click",()=>{resetEditor();setMessage("Editing cancelled. The saved profile was not changed.");});
    node("profilePolicySelect").addEventListener("change",updateControls);
    node("profileName").addEventListener("input",updateControls);
    node("profileSaveForm").addEventListener("submit",event=>{event.preventDefault();void save();});
    node("profileCancelEdit").addEventListener("click",()=>{resetEditor();setMessage("Update cancelled. Saved profiles were not changed.");});
    node("profileCards").addEventListener("click",event=>{
      const button=event.target.closest("button");if(!button||button.disabled)return;
      for(const [name,action] of [["launch",id=>apply(id,true)],["apply",id=>apply(id,false)],["edit",edit],["delete",remove]]) {
        const id=button.getAttribute(`data-profile-${name}`);if(id!=null){void action(id);break;}
      }
    });
    node("quickStartCustom").addEventListener("click",toggleShortcuts);
    node("quickStartCards").addEventListener("click",event=>{
      const button=event.target.closest("button");if(!button||button.disabled)return;
      const profile=button.getAttribute("data-quick-profile-launch"),session=button.getAttribute("data-quick-session-review"),chat=button.getAttribute("data-quick-chat");
      if(profile!=null)void apply(profile,true);
      else if(session!=null)void reviewSessionSet(session);
      else if(chat!=null)void openChatShortcut(chat);
    });
    return {render, renderShortcuts, renderEditBanner, renderRunNotice, updateControls, load, show,
      apply, edit, save, remove, resetEditor, message:setMessage, useInventory, remember,
      loadShortcuts, toggleShortcuts, shortcutEntries, measuredBinding, isReady, reason,
      settingsBlockReason, launchBlockReason, runBlocked,
      isBusy:() => store.busy, shortcutsLoaded:() => store.shortcutLoaded,
      snapshot:() => clone(store)};
  }
  return {createController};
});
