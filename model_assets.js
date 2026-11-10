(function installModelAssets(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LLMModelAssets = api;
})(typeof globalThis === "object" ? globalThis : this, function modelAssetsFactory() {
  "use strict";
  const clone = value => value == null ? value : JSON.parse(JSON.stringify(value));
  const esc = value => String(value ?? "").replace(/[&<>"']/g, character => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[character]);
  function modelEngineModes(model = {}, engine = {}, isUzu = () => false) {
    if (engine?.id === "uzu" && isUzu(model)) return [{id:"dflash-weaver",label:"DFlash + Weaver",
      available:engine.runnable === true,detail:"Fixed runtime-managed acceleration with the bundled draft and Weaver tree"}];
    return (engine?.modes || []).filter(mode=>mode.available);
  }
  function modelChecks(model = {}, isUzu = () => false) {
    const checks = Array.isArray(model?.doctor?.checks) ? model.doctor.checks : [];
    if (!isUzu(model)) return checks;
    return checks.map(check=>check?.id==="acceleration"?{...check,label:"Fixed acceleration",
      detail:"DFlash + Weaver is built into this Uzu artifact; local qualification measures the complete fixed route."}:check);
  }
  function createController({elements, api, selectedModelId, lookupModel, applyRoute, acceptCatalog,
    refreshModels, onActivityChange, otherWork:otherOperationActive, presentRoute, engineVisible, modelVisible,
    featureEnabled, isUzu, contextLabel, backendLabel, backendMark, formatNumber, formatBytes, notify}) {
    const store = {library:null,libraryRoots:[],libraryLoading:false,query:"",engine:"all",surface:"all",libraryState:"all",
      phase:"idle",status:null,plan:null,roots:[],searchResults:[],searching:false,inspecting:false,generation:0,
      completionId:"",downloaderReady:false,starting:false,stopping:false,reviewFresh:false};
    const node = id => elements[id];
    function acquisitionMessage(value, error = false) {
      node("acquisitionStatus").textContent = value;
      node("acquisitionStatus").dataset.error = String(error);
    }
    let libraryPending = null, statusPending = null, statusRevision = 0, searchGeneration = 0, approval = "", reviewInput = "";
    const markup = new WeakMap();
    function html(element, value) {
      if (markup.get(element) === value) return;
      const key = item => item.getAttribute("data-library-details-model") || item.className;
      const disclosures = new Map([...element.querySelectorAll("details")].map(item=>[key(item),item.open]));
      element.innerHTML = value; markup.set(element,value);
      [...element.querySelectorAll("details")].forEach(item=>{if(disclosures.has(key(item)))item.open=disclosures.get(key(item));});
    }
    const inputKey = () => JSON.stringify([node("acquisitionRepoId").value.trim(),node("acquisitionRevision").value.trim(),
      node("acquisitionDestination").value,store.roots.find(root=>root.id===node("acquisitionDestination").value)?.path||""]);
    const planKey = plan => JSON.stringify([plan?.id,plan?.confirmation,plan?.repo,plan?.selection,plan?.destination,plan?.checks,plan?.canStart]);
    function invalidateReview(message = "Inputs changed. Inspect the exact files again before approving a download.") {
      store.generation += 1; store.inspecting = false; store.reviewFresh = false; approval = "";
      node("acquisitionConsent").checked = false;
      if (store.plan && !isActive()) node("acquisitionStatus").textContent = message;
      updateControls();
    }
    function acceptConsent() { approval = node("acquisitionConsent").checked && store.reviewFresh ? planKey(store.plan) : ""; updateControls(); }
    function libraryCheckMarkup(check) {
      const marker = check.state === "pass" ? "✓" : check.state === "advisory" ? "!" : "×";
      return `<div class="model-library-check ${esc(check.state)}"><i aria-hidden="true">${marker}</i><span><strong>${esc(check.label)}</strong><small>${esc(check.detail)}</small></span></div>`;
    }

    function enginesFor(model = {}) {
      return (model.engines || []).filter(engine => engineVisible(engine.id));
    }

    function presentEngine(model = {}, engine = {}) {
      return presentRoute(engine, {
        backend:engine.id,
        modelName:model.name,
        modelReady:model.ready,
      });
    }

    function engineModes(model = {}, engine = {}) {
      return modelEngineModes(model,engine,isUzu);
    }

    function libraryChecks(model = {}) {
      return modelChecks(model,isUzu);
    }

    function overviewFor(model = {}) {
      const engines = enginesFor(model);
      const runnable = engines.filter(engine => engine.runnable);
      const ready = runnable.filter(engine => presentEngine(model, engine).tone === "good");
      const experimental = runnable.filter(engine => presentEngine(model, engine).attention);
      const routes = engines.reduce((total, engine) => total + (engine.surfaces || [])
        .filter(surface => surface.supported).length, 0);
      const accelerators = engines.reduce((total, engine) => total + engineModes(model, engine)
        .filter(mode => mode.id !== "ar").length, 0);
      const evidenceRuns = engines.reduce((total, engine) => (
        total + Number(engine.evidence?.savedRuns || 0)
      ), 0);
      return {
        engines, runnable, ready, experimental, routes, accelerators, evidenceRuns,
        state:ready.length ? "ready" : experimental.length ? "attention" : "blocked",
      };
    }

    function engineMarkup(model, engine) {
      const modes = engineModes(model, engine);
      const surfaces = (engine.surfaces || []).map(surface => `<span class="model-library-surface ${surface.supported ? "supported" : "unavailable"}" title="${esc(surface.reason)}">${esc(surface.label)}</span>`).join("");
      const presentation = presentEngine(model, engine);
      const performanceEvidence = presentation.performanceEvidence || {};
      const hostSupport = presentation.hostSupport || {};
      const evidenceTier = String(performanceEvidence.tier || "").toLowerCase();
      const latest = engine.evidence?.latest;
      const latestModeLabel = engine.id === "uzu" && latest ? "DFlash + Weaver" : latest?.winnerLabel;
      const evidence = presentation.attention
        ? `<div class="model-library-evidence experimental"><strong>${esc(String(hostSupport.state || hostSupport.tier || "").toLowerCase() === "experimental" ? (hostSupport.label || "Experimental on this Mac") : performanceEvidence.label || "Local qualification needed")}</strong><span>${esc(presentation.detail || "This route can be selected explicitly, but it is not used as an automatic speed recommendation.")}</span><small>${esc(evidenceTier === "upstream-measured" ? `Upstream evidence${performanceEvidence.sourceHardware ? ` · ${performanceEvidence.sourceHardware}` : ""} · not verified on this Mac` : "Not automatically preferred")}</small></div>`
        : latest
        ? `<div class="model-library-evidence"><strong>${esc(latestModeLabel || "Measured route")} ${engine.id === "uzu" ? "was measured in" : "won"} the last saved ${esc(latest.suite || "local")} run</strong><span>${esc(latest.recommendation || "Matching local benchmark evidence is saved for this model and runtime.")}</span><small>${esc(latest.createdAt ? new Date(latest.createdAt).toLocaleString([], {dateStyle:"medium", timeStyle:"short"}) : "Saved locally")} · ${formatNumber(engine.evidence.savedRuns)} matching run${Number(engine.evidence.savedRuns) === 1 ? "" : "s"}</small></div>`
        : `<div class="model-library-evidence empty"><strong>No matching saved route evidence</strong><span>Availability is not a speed claim. Use Benchmark Lab before automatically preferring an accelerator.</span></div>`;
      const engineState = engine.status === "runtime-missing" ? "Missing" : presentation.label;
      const actionLabel = presentation.attention ? "Select route explicitly" : presentation.available ? `Use with ${esc(engine.label)}` : "Route unavailable";
      const actionDetail = presentation.attention
        ? "Not selected by automatic speed choices"
        : engine.evidence?.savedRuns ? `${formatNumber(engine.evidence.savedRuns)} saved evidence run${Number(engine.evidence.savedRuns) === 1 ? "" : "s"}` : "Selection changes no files and starts nothing";
      return `<section class="model-library-engine ${esc(presentation.attention ? "experimental" : engine.status)}">
        <header><div><span class="runtime-icon ${esc(engine.id === "lmstudio" ? "lms" : engine.id)}" aria-hidden="true">${esc(backendMark(engine.id))}</span><span><strong>${esc(engine.label)}</strong><small>${esc(engine.reason)}</small></span></div><em>${esc(engineState)}</em></header>
        <div class="model-library-engine-facts"><div><small>Decode modes</small><span class="model-library-pills">${modes.map(mode => `<b title="${esc(mode.detail)}">${esc(mode.label)}</b>`).join("") || "None"}</span></div><div><small>Work surfaces</small><span class="model-library-pills">${surfaces}</span></div></div>
        ${evidence}
        <div class="model-library-engine-action"><span>${esc(actionDetail)}</span><button type="button" class="text-button" data-library-model="${esc(model.id)}" data-library-backend="${esc(engine.id)}" ${presentation.available ? "" : "disabled"}>${actionLabel}</button></div>
      </section>`;
    }

    function cardMarkup(model) {
      const doctor = model.doctor || {};
      const isSelected = selectedModelId() === model.id;
      const engineScoped = store.engine !== "all";
      const overview = overviewFor(model);
      const visibleEngines = store.engine === "all"
        ? overview.engines
        : overview.engines.filter(engine => engine.id === store.engine);
      const scopedEngine = engineScoped ? visibleEngines[0] : null;
      const scopedPresentation = scopedEngine ? presentEngine(model, scopedEngine) : null;
      const scopedRoutes = scopedEngine
        ? (scopedEngine.surfaces || []).filter(surface => surface.supported).length
        : overview.routes;
      const scopedModes = scopedEngine
        ? engineModes(model, scopedEngine).length
        : overview.accelerators;
      const cardState = engineScoped
        ? (scopedPresentation?.attention ? "attention" : scopedPresentation?.available ? "ready" : "blocked")
        : overview.state;
      const stateLabel = engineScoped
        ? (scopedPresentation?.label || "Unavailable")
        : overview.state === "ready" ? "Ready" : overview.state === "attention" ? "Review" : "Blocked";
      const diagnosisHeadline = engineScoped
        ? scopedPresentation?.attention
          ? `${scopedEngine.label} needs an explicit choice.`
          : scopedPresentation?.available
          ? `Ready with ${scopedEngine.label}.`
          : `${scopedEngine?.label || backendLabel(store.engine)} cannot use this checkpoint.`
        : overview.ready.length
          ? `Ready with ${overview.ready.map(engine => engine.label).join(", ")}.`
          : overview.experimental.length
            ? "A visible engine route needs review."
            : "No visible engine can use this checkpoint.";
      const diagnosisDetail = engineScoped
        ? (scopedPresentation?.detail || scopedEngine?.reason || "This engine has no compatible route for the checkpoint.")
        : overview.ready.length
          ? `${formatNumber(overview.routes)} supported work-surface route${overview.routes === 1 ? "" : "s"} across the engines shown here.`
          : (overview.experimental[0]
            ? presentEngine(model, overview.experimental[0]).detail || overview.experimental[0].reason
            : overview.engines[0]?.reason || "No visible compatibility report is available.");
      const detailSummary = engineScoped
        ? `${formatNumber(scopedRoutes)} available surface${scopedRoutes === 1 ? "" : "s"} · ${formatNumber(scopedModes)} decode mode${scopedModes === 1 ? "" : "s"}`
        : `${formatNumber(overview.runnable.length)} engines · ${formatNumber(overview.accelerators)} accelerators · ${formatNumber(overview.evidenceRuns)} evidence runs`;
      return `<article class="model-library-card ${esc(cardState)}">
        <header><div><span class="model-library-format" aria-hidden="true">${esc(String(model.format || "?").slice(0, 4).toUpperCase())}</span><span><strong>${esc(model.name)}</strong><small>${esc(model.architecture)} · ${esc(model.origins?.join(" + ") || "Detected locally")}</small></span></div><em>${esc(stateLabel)}</em></header>
        <div class="model-library-meta"><span>${esc(String(model.format || "unknown").toUpperCase())}</span><span>${esc(model.quantization)}</span><span>${esc(model.sizeLabel)}</span><span>${model.nativeContext ? esc(contextLabel(model)) : "Context unknown"}</span><span>${formatNumber(scopedRoutes)} available route${scopedRoutes === 1 ? "" : "s"}</span></div>
        <code class="model-library-path" title="${esc(model.path)}">${esc(model.path)}</code>
        <div class="model-library-diagnosis"><i aria-hidden="true">${cardState === "ready" ? "✓" : cardState === "attention" ? "!" : "×"}</i><p><strong>${esc(diagnosisHeadline)}</strong><span>${esc(diagnosisDetail)}</span></p></div>
        <details class="model-library-details" data-library-details-model="${esc(model.id)}" ${isSelected ? "open" : ""}><summary><span>${engineScoped ? `${esc(scopedEngine?.label || backendLabel(store.engine))} details` : "Compatibility details"}</span><small>${detailSummary}</small></summary><div>
          <div class="model-library-checks">${libraryChecks(model).map(libraryCheckMarkup).join("")}</div>
          <div class="model-library-engines">${visibleEngines.map(engine => engineMarkup(model, engine)).join("")}</div>
        </div></details>
      </article>`;
    }

    function matches(model) {
      if (!modelVisible(model)) return false;
      const visibleEngines = enginesFor(model);
      const overview = overviewFor(model);
      const scopedEngine = store.engine === "all"
        ? null
        : visibleEngines.find(item => item.id === store.engine);
      const scopedPresentation = scopedEngine ? presentEngine(model, scopedEngine) : null;
      const scopedState = scopedPresentation?.attention ? "attention" : scopedPresentation?.available ? "ready" : "blocked";
      if (
        store.libraryState !== "all"
        && (scopedEngine ? scopedState : overview.state) !== store.libraryState
      ) return false;
      if (store.engine !== "all") {
        const engine = visibleEngines.find(item => item.id === store.engine);
        if (!engine) return false;
      }
      if (store.surface !== "all") {
        const candidateEngines = scopedEngine ? [scopedEngine] : visibleEngines;
        const supported = candidateEngines.some(engine =>
          (engine.surfaces || []).some(surface => surface.id === store.surface && surface.supported));
        if (!supported) return false;
      }
      const query = store.query.trim().toLowerCase();
      if (!query) return true;
      const searchable = [
        model.name, model.path, model.format, model.architecture, model.modelType,
        model.quantization, ...(model.origins || []), model.doctor?.headline,
        model.doctor?.nextAction,
        ...visibleEngines.flatMap(engine => [
          engine.label, engine.reason, ...(engine.modes || []).map(mode => mode.label),
          ...(engine.surfaces || []).flatMap(surface => [surface.label, surface.reason]),
        ]),
      ].join(" ").toLowerCase();
      return searchable.includes(query);
    }

    function renderLibrary() {
      const inventory = store.library;
      if (!inventory) return;
      if (!engineVisible(store.engine)) {
        store.engine = "all";
        node("modelLibraryEngineFilter").value = "all";
      }
      const allModels = (inventory.models || []).filter(modelVisible);
      const availableEngines = new Map();
      for (const model of allModels) for (const engine of enginesFor(model)) availableEngines.set(engine.id,engine.label);
      const filter = node("modelLibraryEngineFilter");
      const selectedEngine = store.engine;
      html(filter, '<option value="all">All engines</option>' + [...availableEngines]
        .sort((left,right)=>String(left[1]).localeCompare(String(right[1])))
        .map(([id,label])=>`<option value="${esc(id)}">${esc(label)}</option>`).join(""));
      store.engine = selectedEngine === "all" || availableEngines.has(selectedEngine) ? selectedEngine : "all";
      filter.value = store.engine;
      const models = allModels.filter(matches);
      const visibleReports = allModels.map(overviewFor);
      const summary = {
        models:allModels.length,
        ready:visibleReports.filter(report => report.state === "ready").length,
        attention:visibleReports.filter(report => report.state === "attention").length,
        blocked:visibleReports.filter(report => report.state === "blocked").length,
        launchableRoutes:visibleReports.reduce((total, report) => total + report.routes, 0),
      };
      node("modelLibraryBadge").textContent = `${formatNumber(summary.models)} detected`;
      node("modelLibraryBadge").className = `setup-badge ${summary.blocked ? "warning" : "ready"}`;
      const scoped = store.engine !== "all";
      const scopedReports = scoped ? models.map(model => {
        const engine = enginesFor(model)
          .find(item => item.id === store.engine);
        return engine ? {engine, presentation:presentEngine(model, engine)} : null;
      }).filter(Boolean) : [];
      const summaryFacts = scoped ? [
        [models.length, "shown"],
        [scopedReports.filter(item => item.presentation.tone === "good").length, "qualified / ready"],
        [scopedReports.filter(item => item.presentation.attention).length, "review"],
        [scopedReports.filter(item => !item.presentation.available).length, "unavailable"],
      ] : [
        [models.length, "shown"], [summary.ready || 0, "ready"],
        [summary.attention || 0, "review"], [summary.blocked || 0, "blocked"],
        [summary.launchableRoutes || 0, "available routes"],
      ];
      html(node("modelLibrarySummary"), summaryFacts.map(([value, label]) => `<span><strong>${formatNumber(value)}</strong><small>${esc(label)}</small></span>`).join(""));
      html(node("modelLibraryCards"), models.length
        ? models.map(cardMarkup).join("")
        : `<div class="model-library-empty"><strong>No models match these filters.</strong><span>Clear the filters or rescan the known folders.</span></div>`);
      const filtered = Boolean(store.query || store.engine !== "all" || store.surface !== "all" || store.libraryState !== "all");
      node("clearModelLibraryFilters").disabled = !filtered;
    }

    function loadLibrary() {
      if (libraryPending) return libraryPending;
      libraryPending = readLibrary().finally(()=>{libraryPending=null;});
      return libraryPending;
    }
    async function readLibrary() {
      store.libraryLoading = true;
      node("refreshModelLibrary").disabled = true;
      node("refreshModelLibrary").textContent = "Scanning…";
      node("modelLibraryStatus").textContent = "Scanning known local folders and installed commands without loading a model…";
      if (!store.library) node("modelLibraryCards").innerHTML = '<div class="model-library-empty"><strong>Building the compatibility report…</strong><span>No model process is being started.</span></div>';
      try {
        const data = await api.library();
        store.library = clone(data.modelLibrary);
        store.libraryRoots = clone(data.roots || []);
        if (Array.isArray(data.models)) {
          acceptCatalog(data.models);
        }
        renderLibrary();
        const existingRoots = store.libraryRoots.filter(root => root.exists);
        node("modelLibraryStatus").textContent = `Checked ${formatNumber(existingRoots.length)} existing model root${existingRoots.length === 1 ? "" : "s"} locally at ${new Date().toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"})}. Nothing was started or changed.`;
      } catch (error) {
        node("modelLibraryStatus").textContent = error.message;
      } finally {
        store.libraryLoading = false;
        node("refreshModelLibrary").disabled = false;
        node("refreshModelLibrary").textContent = "Rescan known folders";
      }
    }

    async function showLibrary() {
      if (!node("modelLibraryDialog").open) node("modelLibraryDialog").showModal();
      if (store.library) renderLibrary();
      else await loadLibrary();
    }

    async function showFreeTokenReview() {
      if (!featureEnabled("freetoken")) return;
      store.query = "";
      store.engine = "freetoken";
      store.surface = "all";
      store.libraryState = "all";
      node("modelLibrarySearch").value = "";
      node("modelLibraryEngineFilter").value = "freetoken";
      node("modelLibrarySurfaceFilter").value = "all";
      node("modelLibraryStateFilter").value = "all";
      await showLibrary();
      renderLibrary();
      node("modelLibraryStatus").textContent = "Showing every detected checkpoint against native or connected FreeToken. Incompatible models stay visible with their exact reason; nothing was loaded or downloaded.";
    }

    function clearFilters() {
      store.query = "";
      store.engine = "all";
      store.surface = "all";
      store.libraryState = "all";
      node("modelLibrarySearch").value = "";
      node("modelLibraryEngineFilter").value = "all";
      node("modelLibrarySurfaceFilter").value = "all";
      node("modelLibraryStateFilter").value = "all";
      renderLibrary();
      node("modelLibrarySearch").focus();
    }

    function useRoute(modelId, backend) {
      if (!engineVisible(backend)) { node("modelLibraryStatus").textContent = "That engine is temporarily hidden in this launcher build."; return; }
      const rawModel = lookupModel(modelId);
      const report = store.library?.models?.find(model => model.id === modelId);
      const engine = report?.engines?.find(item => item.id === backend);
      if (!rawModel || !engine?.runnable) { node("modelLibraryStatus").textContent = "That route changed during the scan. Refresh the library before selecting it."; return; }
      try {
        applyRoute(modelId,backend);
        node("modelLibraryDialog").close();
        notify(`${rawModel.name} with ${engine.label} is selected. Nothing has started.`);
      } catch(error) { node("modelLibraryStatus").textContent = error.message; }
    }

    function isActive(status = store.status || {}) {
      return ["queued","downloading","stopping","verifying"].includes(status.phase || store.phase);
    }


    function renderRoots() {
      if (!store.roots.length) return;
      const select = node("acquisitionDestination");
      const previous = select.value;
      html(select, store.roots.map(root => `<option value="${esc(root.id)}">${esc(root.label)}</option>`).join(""));
      if (store.roots.some(root => root.id === previous)) select.value = previous;
      const root = store.roots.find(item => item.id === select.value);
      node("acquisitionDestinationHelp").textContent = root
        ? `${root.label}: ${root.path}`
        : "Only a fixed known model folder can be used.";
    }

    function renderSearchResults() {
      const results = store.searchResults || [];
      if (!results.length) {
        html(node("acquisitionSearchResults"), store.searching
          ? '<div class="acquisition-search-empty"><strong>Searching the public Hub…</strong><span>No model files are being downloaded.</span></div>'
          : "");
        return;
      }
      html(node("acquisitionSearchResults"), results.map(result => {
        const format = result.formats?.length ? result.formats.join(" + ") : "Inspect files";
        const stateLabel = result.disabled ? "Disabled" : result.private ? "Private" : result.gated ? "Gated" : result.draftOnly ? "Draft component" : "Public";
        return `<article class="acquisition-search-result ${result.inspectable ? "" : "blocked"}">
          <div><strong>${esc(result.id)}</strong><span>${esc(format)} · ${esc(result.quantization || "Inspect files")} · ${esc(result.license || "License not declared")}</span><small>${formatNumber(result.downloads)} downloads · ${formatNumber(result.likes)} likes</small></div>
          <div><em>${esc(stateLabel)}</em><button type="button" class="text-button" data-acquisition-repo="${esc(result.id)}" data-acquisition-revision="${esc(result.revision || "")}" ${result.inspectable ? "" : "disabled"}>Inspect</button></div>
        </article>`;
      }).join(""));
    }

    function acquisitionCheckMarkup(check = {}) {
      const marker = check.state === "pass" ? "✓" : check.state === "advisory" ? "!" : "×";
      return `<article class="acquisition-check ${esc(check.state || "blocked")}"><i aria-hidden="true">${marker}</i><div><strong>${esc(check.label || "Check")}</strong><span>${esc(check.detail || "No detail available.")}</span></div></article>`;
    }

    function renderPlan(plan, inspected = false) {
      if (!plan?.repo || !plan?.destination) return;
      const changed = planKey(store.plan) !== planKey(plan);
      store.plan = clone(plan);
      if (changed) { approval = ""; node("acquisitionConsent").checked = false; }
      if (inspected) { store.reviewFresh = true; reviewInput = inputKey(); }

      const variants = Array.isArray(plan.variants) ? plan.variants : [];
      const selection = plan.selection;
      const showVariants = variants.length > 1;
      node("acquisitionVariantField").classList.toggle("hidden", !showVariants);
      if (showVariants) {
        html(node("acquisitionVariant"), [
          '<option value="">Choose one exact file set…</option>',
          ...variants.map(variant => `<option value="${esc(variant.id)}">${esc(variant.label)} · ${formatBytes(variant.sizeBytes)}</option>`),
        ].join(""));
        node("acquisitionVariant").value = selection?.id || "";
      }

      const pinned = String(plan.repo.pinnedRevision || "");
      const repoParts = String(plan.repo.id || "").split("/").map(encodeURIComponent);
      const repoUrl = `https://huggingface.co/${repoParts.join("/")}/tree/${encodeURIComponent(pinned)}`;
      const blocked = (plan.checks || []).some(check => check.state === "blocked");
      const facts = [
        ["Pinned commit", pinned ? pinned.slice(0, 12) : "Unavailable", pinned],
        ["License", plan.repo.license || "Not declared", plan.repo.license || "Not declared"],
        ["Exact file set", selection?.label || (plan.variantRequired ? "Choose a variant" : "Unavailable"), selection?.label || ""],
        ["Selected size", selection ? formatBytes(selection.sizeBytes) : "—", selection ? `${selection.fileCount} exact files` : ""],
        ["Remaining", selection ? formatBytes(plan.destination.remainingBytes) : "—", selection ? `${formatBytes(plan.destination.existingBytes)} already present` : ""],
        ["Destination", plan.destination.label || plan.destination.kind, plan.destination.path || ""],
      ];
      const engines = (plan.expectedEngines || []).map(engine => `<article class="acquisition-engine ${engine.expectedCompatible ? "expected" : "unavailable"}"><span class="runtime-icon ${esc(engine.id === "lmstudio" ? "lms" : engine.id)}" aria-hidden="true">${esc(backendMark(engine.id))}</span><div><strong>${esc(engine.label)}</strong><small>${esc(engine.detail)}</small></div><em>${engine.expectedReady ? "Installed · expected" : engine.expectedCompatible ? "Expected · runtime missing" : "Not this format"}</em></article>`).join("");
      const files = selection?.files || [];
      const fileList = files.length
        ? `<details class="acquisition-files"><summary><span>Review ${formatNumber(files.length)} exact files</span><small>Names, sizes, and available pinned checksums</small></summary><div>${files.map(file => `<span><code title="${esc(file.path)}">${esc(file.path)}</code><b>${formatBytes(file.size)}</b><small>${file.sha256 ? `SHA-256 ${esc(file.sha256.slice(0, 16))}…` : "Exact size verification"}</small></span>`).join("")}</div></details>`
        : "";
      html(node("acquisitionPlan"), `<div class="acquisition-plan-heading"><div><span>${esc(selection?.format?.toUpperCase() || "HUB")}</span><div><h3>${esc(plan.repo.id)}</h3><p>${selection ? `${esc(selection.label)} at one immutable commit.` : "Choose one exact supported file set."}</p></div></div><a href="${repoUrl}" target="_blank" rel="noreferrer">Review model page ↗</a></div>
        <div class="acquisition-facts">${facts.map(([label,value,title]) => `<span><small>${esc(label)}</small><strong title="${esc(title)}">${esc(value)}</strong></span>`).join("")}</div>
        <div class="acquisition-checks">${(plan.checks || []).map(acquisitionCheckMarkup).join("")}</div>
        <section class="acquisition-engine-plan"><div><h4>Expected local routes</h4><p>These are scanner predictions, not speed claims. Model Library performs the post-download compatibility scan, then Benchmark Lab measures this Mac.</p></div><div>${engines}</div></section>
        ${fileList}
        <p class="acquisition-plan-note ${blocked ? "blocked" : ""}">${blocked ? "This plan cannot start until every blocked check is resolved." : `Approval is bound to ${esc(plan.confirmation)} and expires at ${esc(new Date(plan.expiresAt).toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"}))}.`}</p>`);

      node("acquisitionStartTitle").textContent = plan.actionLabel || "Download pinned files";
      node("acquisitionStartLabel").textContent = selection
        ? `${formatBytes(plan.destination.remainingBytes)} remaining · resumable`
        : "Choose one exact file set";
      node("acquisitionConsentCopy").textContent = selection
        ? `${plan.repo.id}@${pinned.slice(0, 12)} · ${selection.fileCount} exact files · ${plan.destination.path}. No runtime or downloaded code will be started.`
        : "Choose one exact file set before approval is available.";
      node("acquisitionBadge").textContent = blocked ? (plan.variantRequired ? "Choose variant" : "Blocked") : "Consent required";
      node("acquisitionBadge").className = `setup-badge${blocked ? " warning" : ""}`;
      if (!isActive()) {
        node("acquisitionStatus").textContent = blocked
          ? ((plan.checks || []).find(check => check.state === "blocked")?.detail || "Resolve the blocked checks before downloading.")
          : `Inspection complete. Nothing has been downloaded; review the pinned model page and exact plan before approval.`;
      }
      updateControls();
    }

    function updateControls() {
      const active = isActive() || store.starting || store.stopping;
      const otherWork = otherOperationActive();
      const plan = store.plan;
      const consentReady = Boolean(plan?.canStart && plan?.selection && store.reviewFresh && reviewInput === inputKey()
        && !store.inspecting && !active && !otherWork);
      node("acquisitionSearch").disabled = active || store.searching;
      node("acquisitionSearchButton").disabled = active || store.searching;
      for (const id of ["acquisitionRepoId","acquisitionRevision","acquisitionDestination","acquisitionVariant"]) {
        node(id).disabled = active || store.inspecting;
      }
      node("acquisitionInspectButton").disabled = active || store.inspecting;
      node("acquisitionConsent").disabled = !consentReady;
      node("acquisitionConsentPanel").classList.toggle("inactive", !consentReady);
      if (!consentReady) { approval = ""; node("acquisitionConsent").checked = false; }
      node("acquisitionStartButton").disabled = !consentReady || !node("acquisitionConsent").checked || approval !== planKey(plan);
      node("acquisitionStopButton").disabled = !isActive() || store.starting || store.stopping;
      node("acquisitionOpenLibrary").disabled = store.phase !== "completed" || !store.status?.result;
      if (otherWork && plan?.canStart && !active) {
        node("acquisitionConsentCopy").textContent = "Finish or stop the active launcher operation before approving this pinned acquisition.";
      } else if (plan?.selection) {
        node("acquisitionConsentCopy").textContent = `${plan.repo.id}@${String(plan.repo.pinnedRevision || "").slice(0,12)} · ${plan.selection.fileCount} exact files · ${plan.destination.path}. No runtime or downloaded code will be started.`;
      }
    }

    function useStatus(envelope = {}) {
      const status = envelope.acquisition || envelope;
      if (Array.isArray(envelope.roots)) {
        const before = inputKey();
        store.roots = clone(envelope.roots);
        renderRoots();
        if (store.reviewFresh && before !== inputKey()) invalidateReview("The destination changed. Inspect its current pinned plan again.");
      }
      if (typeof envelope.downloaderReady === "boolean") store.downloaderReady = envelope.downloaderReady;
      const previous = store.phase;
      statusRevision += 1;
      store.status = clone(status);
      store.phase = status.phase || "idle";
      if (status.plan) renderPlan(status.plan);
      const progress = Math.max(0, Math.min(1, Number(status.progress || 0)));
      const percent = Math.round(progress * 100);
      node("acquisitionPercent").textContent = `${percent}%`;
      node("acquisitionProgressBar").style.width = `${percent}%`;
      node("acquisitionProgressBar").parentElement.setAttribute("aria-valuenow", String(percent));
      node("acquisitionPhase").textContent = ({
        idle:"Ready to inspect", queued:"Queued", downloading:"Downloading pinned files",
        stopping:"Stopping", verifying:"Verifying files", completed:"Verified",
        cancelled:"Stopped · resumable", failed:"Needs attention",
      })[store.phase] || store.phase;
      if (status.message && (store.phase !== "idle" || !store.plan)) {
        acquisitionMessage(status.message, store.phase === "failed");
      }
      if (isActive()) {
        node("acquisitionBadge").textContent = store.phase === "verifying" ? "Verifying" : "Download active";
        node("acquisitionBadge").className = "setup-badge active";
      } else if (store.phase === "completed") {
        node("acquisitionBadge").textContent = "Pinned files verified";
        node("acquisitionBadge").className = "setup-badge ready";
      } else if (["cancelled","failed"].includes(store.phase)) {
        node("acquisitionBadge").textContent = store.phase === "failed" ? "Check required" : "Files preserved";
        node("acquisitionBadge").className = "setup-badge warning";
      }
      if (previous !== store.phase && ["completed","cancelled","failed"].includes(store.phase)) {
        node("acquisitionConsent").checked = false;
      }
      updateControls();
      onActivityChange();
      const completedId = status.phase === "completed" && status.result
        ? JSON.stringify([status.plan?.id, status.result.repoId, status.result.pinnedRevision, status.result.path, status.result.modelName]) : "";
      if (completedId && store.completionId !== completedId) {
        store.completionId = completedId;
        refreshModels().catch(() => {});
      }
    }


    async function showAcquisition() {
      if (node("modelLibraryDialog").open) node("modelLibraryDialog").close();
      if (!node("acquisitionDialog").open) node("acquisitionDialog").showModal();
      await refresh();
      if (!store.downloaderReady) {
        node("acquisitionStatus").textContent = "The launcher-managed public model downloader is unavailable. Search and inspection may be unavailable until a supported oMLX runtime is installed.";
      }
    }

    async function search() {
      const query = node("acquisitionSearch").value.trim();
      if (store.searching || store.starting || isActive()) return;
      const generation = ++searchGeneration;
      store.searching = true;
      renderSearchResults();
      acquisitionMessage(`Searching the public Hub for “${query}”. No model files are being downloaded…`);
      updateControls();
      try {
        const data = await api.search({query});
        if (generation !== searchGeneration) return;
        store.searchResults = clone(data.search?.results || []);
        renderSearchResults();
        node("acquisitionStatus").textContent = store.searchResults.length
          ? `Found ${store.searchResults.length} public result${store.searchResults.length === 1 ? "" : "s"}. Choose Inspect to pin and validate its exact file tree.`
          : "No public text-generation repositories matched that search.";
      } catch (error) {
        if (generation !== searchGeneration) return;
        if (!store.searchResults.length) html(node("acquisitionSearchResults"), `<div class="acquisition-search-empty error"><strong>Search unavailable.</strong><span>${esc(error.message)}</span></div>`);
        acquisitionMessage(error.message, true);
      } finally {
        if (generation !== searchGeneration) return;
        store.searching = false;
        updateControls();
      }
    }

    async function inspect(variantId = "") {
      if (store.inspecting || store.starting || isActive()) return;
      const repoId = node("acquisitionRepoId").value.trim();
      const revision = node("acquisitionRevision").value.trim();
      const destination = node("acquisitionDestination").value;
      const generation = ++store.generation;
      store.inspecting = true;
      store.reviewFresh = false; approval = ""; node("acquisitionConsent").checked = false;
      acquisitionMessage("Reading public repository metadata and the pinned file tree. Nothing is being downloaded…");
      node("acquisitionBadge").textContent = "Inspecting";
      node("acquisitionBadge").className = "setup-badge active";
      updateControls();
      try {
        const data = await api.inspect({repoId,revision,destination,variantId});
        if (generation !== store.generation) return;
        renderPlan(data.plan, true);
      } catch (error) {
        if (generation === store.generation) {
          acquisitionMessage(error.message, true);
          node("acquisitionBadge").textContent = "Inspection failed";
          node("acquisitionBadge").className = "setup-badge warning";
        }
      } finally {
        if (generation === store.generation) {
          store.inspecting = false;
          updateControls();
        }
      }
    }

    async function start() {
      const plan = store.plan;
      if (!plan?.canStart || !plan.selection || !store.reviewFresh || reviewInput !== inputKey() || otherOperationActive()
        || store.starting || store.inspecting || !node("acquisitionConsent").checked || approval !== planKey(plan) || isActive()) return;
      const approved = approval;
      let failed = false;
      store.starting = true; statusRevision += 1; updateControls();
      try {
        const data = await api.start({planId:plan.id,confirmation:plan.confirmation,licenseReviewed:true});
        node("acquisitionConsent").checked = false;
        useStatus({acquisition:{
          phase:"queued", progress:Number(plan.destination.existingBytes || 0) / Math.max(1, Number(plan.selection?.sizeBytes || 1)),
          downloadedBytes:Number(plan.destination.existingBytes || 0),
          message:"Acquisition approved. Preparing the pinned destination…", plan:data.plan, result:null,
        }});
      } catch (error) {
        failed = true;
        acquisitionMessage(error.message, true);
        notify(error.message, true);
      } finally {
        store.starting = false;
        if (failed && store.reviewFresh && reviewInput === inputKey() && approved === planKey(store.plan)) {
          approval = approved; node("acquisitionConsent").checked = true;
        }
        updateControls();
      }
    }

    async function stop() {
      if (store.stopping || store.starting || !isActive()) return;
      store.stopping = true; statusRevision += 1; updateControls();
      try {
        await api.stop();
        await refresh(true);
      } catch (error) { acquisitionMessage(error.message, true); }
      finally { store.stopping = false; updateControls(); }
    }

    async function showAcquiredLibrary() {
      const modelName = store.status?.result?.modelName || "";
      node("acquisitionDialog").close();
      await refreshModels();
      await showLibrary();
      if (modelName) {
        store.query = modelName;
        node("modelLibrarySearch").value = modelName;
        renderLibrary();
      }
    }

    node("openModelLibrary").addEventListener("click",showLibrary);
    node("refreshModelLibrary").addEventListener("click",loadLibrary);
    node("clearModelLibraryFilters").addEventListener("click",clearFilters);
    node("openAcquisitionCenter").addEventListener("click",showAcquisition);
    node("acquisitionSearchForm").addEventListener("submit",event=>{event.preventDefault();void search();});
    node("acquisitionInspectButton").addEventListener("click",()=>inspect());
    for (const id of ["acquisitionRepoId","acquisitionRevision"]) node(id).addEventListener("input",()=>invalidateReview());
    node("acquisitionDialog").addEventListener("close",()=>{if(!isActive()&&!store.starting)invalidateReview();searchGeneration+=1;store.searching=false;});
    node("acquisitionDestination").addEventListener("change",()=>{
      invalidateReview();renderRoots();if(store.plan&&!isActive())void inspect(node("acquisitionVariant").value);
    });
    node("acquisitionVariant").addEventListener("change",event=>{invalidateReview();void inspect(event.currentTarget.value);});
    node("acquisitionConsent").addEventListener("change",acceptConsent);
    node("acquisitionStartButton").addEventListener("click",start);
    node("acquisitionStopButton").addEventListener("click",stop);
    node("acquisitionOpenLibrary").addEventListener("click",showAcquiredLibrary);
    node("acquisitionSearchResults").addEventListener("click",event=>{
      const button=event.target.closest("[data-acquisition-repo]");if(!button||button.disabled)return;
      node("acquisitionRepoId").value=button.dataset.acquisitionRepo||"";
      node("acquisitionRevision").value=button.dataset.acquisitionRevision||"";void inspect();
    });
    for(const [id,field,eventName] of [["modelLibrarySearch","query","input"],["modelLibraryEngineFilter","engine","change"],
      ["modelLibrarySurfaceFilter","surface","change"],["modelLibraryStateFilter","libraryState","change"]]) {
      node(id).addEventListener(eventName,event=>{
        store[field]=field==="engine"&&!engineVisible(event.currentTarget.value)?"all":event.currentTarget.value;
        event.currentTarget.value=store[field];renderLibrary();
      });
    }
    node("modelLibraryCards").addEventListener("click",event=>{
      const button=event.target.closest("[data-library-model][data-library-backend]");
      if(button&&!button.disabled)useRoute(button.dataset.libraryModel,button.dataset.libraryBackend);
    });
    function refresh(fresh = false) {
      if (statusPending) return fresh ? statusPending.then(()=>refresh()) : statusPending;
      const revision = statusRevision;
      statusPending = api.status().then(data=>{if(revision===statusRevision)useStatus(data);})
        .finally(()=>{statusPending=null;});
      return statusPending;
    }
    return {renderLibrary, loadLibrary, showLibrary, showFreeTokenReview, clearFilters, useRoute, isActive,
      renderRoots, renderSearchResults, renderPlan, updateControls, useStatus, showAcquisition, search, inspect,
      start, stop, showAcquiredLibrary, refresh, engineModes, libraryChecks, overview:overviewFor, presentation:presentEngine, engineMarkup,
      invalidateReview, acceptConsent,
      setEngineFilter:engine=>{store.engine=engineVisible(engine)?engine:"all";node("modelLibraryEngineFilter").value=store.engine;renderLibrary();},
      cardMarkup, matches, snapshot:() => clone(store),
      invalidateLibrary:() => { store.library = null; },
      activity:() => ({phase:store.phase,status:store.status ? {phase:store.status.phase,message:store.status.message,
        progress:store.status.progress,plan:store.status.plan ? {repo:{id:store.status.plan.repo?.id}} : null} : null})};
  }
  return {createController,modelEngineModes,modelChecks};
});
