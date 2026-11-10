(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LLMLauncherHome = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const ENGINE_HELP = Object.freeze({
    rapidmlx:"Rapid MLX runs compatible local MLX models on Apple silicon. Auto follows native MTP support; you can choose AR or tune a supported MTP draft depth. Model files can be shared across compatible engines, while format, memory and context limits still apply.",
    rec:"Rec runs the official Flint INT4 model in unified memory, with reasoning and function tools. Prompt and response share the selected context window.",
    splash:"Splash runs supported Qwen GGUF and MLX Q4 models with its own DFlash2 acceleration. The matching draft is prepared on first launch.",
    kolibri:"Kolibri streams the full Q6 expert model from SSD. Tune its RAM ceiling and prompt cache for repeated coding turns.",
    mtplx:"MTPLX uses native multi-token prediction where this model supports it. Compare acceleration on your exact model and context.",
    omlx:"oMLX supports MLX models, prompt reuse and compatible DFlash2 drafts. Saved measurements identify the best route for this setup.",
    uzu:"Uzu manages DFlash and Weaver acceleration. Context choices follow the installed runtime’s supported routes.",
    slotstream:"Slotstream streams experts from SSD and supports native multi-token prediction. Keep the matching model and MTP head together.",
    lmstudio:"Use models managed by LM Studio. The launcher checks the chosen model and connection before opening your assistant.",
    swiftlm:"SwiftLM streams expert weights from SSD. Its speed depends on the exact model artifact and available memory.",
    mference:"Mference streams expert weights from SSD and can reuse prompt state between requests.",
    whallm:"Whallm runs its full Qwen expert model from SSD. Review the capacity check for this Mac before launch.",
    llamacpp:"This pinned llama.cpp route keeps Qwen PLE tensors on SSD and uses a qualified 8K context contract.",
  });

  function engineGuidance(backend, capability = {}) {
    return ENGINE_HELP[backend] || capability.reason || "Choose a compatible model, then compare its measured performance on this Mac.";
  }

  function measurementView(receipt, backend, {loading = false, error = ""} = {}) {
    const finite = value => typeof value === "number" && Number.isFinite(value) && value >= 0;
    if (loading) return {speed:"Checking…", first:"Checking…", state:"loading", detail:"Looking for measurements that match this setup."};
    if (error) return {speed:"Unavailable", first:"—", state:"unknown", detail:"Saved measurements could not be read. You can retry in Performance & diagnostics."};
    const matches = receipt && receipt.backend === backend && receipt.fresh === true
      && receipt.reasoningContract?.normalized !== true && !Number.isInteger(receipt.contextAdjustment?.measured)
      && ["trusted", "trusted-engine", "trusted-route", "tie"].includes(receipt.state);
    if (!matches) return {speed:"Not measured", first:"—", state:"unknown", detail:"Measure this exact setup to see decode speed and time to first output."};
    const speed = receipt.decodeTokensPerSecond;
    const first = receipt.firstTokenSeconds;
    return {
      speed:finite(speed) ? `${speed.toFixed(1)} tok/s` : "Not reported",
      first:finite(first) ? `${first.toFixed(first < 10 ? 2 : 1)} s` : "Not reported",
      state:finite(speed) ? "measured" : "unknown",
      detail:"Saved local measurement · model, engine and visible settings must match.",
    };
  }

  // Keep the current selection available while filtering: typing a search must
  // never silently switch model weights or overwrite its generation settings.
  function filterModels(models, query, selectedId) {
    const terms = String(query || "").trim().toLocaleLowerCase().split(/\s+/).filter(Boolean).slice(0, 16);
    const matches = model => {
      const text = [model.name, model.id, model.family, model.quantization, model.modelType, model.searchText].filter(Boolean).join(" ").toLocaleLowerCase();
      return terms.every(term => text.includes(term));
    };
    let count = 0;
    const visible = models.filter(model => {
      const match = matches(model);
      if (match) count += 1;
      return model.id === selectedId || match;
    });
    return {models:visible, count, filtering:terms.length > 0};
  }

  function modelRouteGroups(models, routes, backendName) {
    const byModel = new Map();
    for (const route of routes) {
      if (!byModel.has(route.modelId)) byModel.set(route.modelId, []);
      byModel.get(route.modelId).push(route);
    }
    const groups = new Map();
    for (const model of models) {
      const modelRoutes = byModel.get(model.id);
      if (!modelRoutes) continue;
      // Runtime adapters can publish a second record for the same checkpoint.
      // Join only when the catalog identifies the same original file or folder.
      const artifact = model.strata?.sourceShardsVerified === true ? model.strata.sourceFirst
        : model.splash ? model.splash.path : model.artifact;
      const format = String(model.format || "").toUpperCase();
      const key = typeof artifact === "string" && artifact.startsWith("/") ? `${format}:artifact:${artifact}` : `id:${model.id}`;
      if (!groups.has(key)) groups.set(key, {model, routes:[], names:[]});
      const group = groups.get(key);
      if (typeof model.artifact === "string" && model.artifact.startsWith("/")) group.model = model;
      group.routes.push(...modelRoutes);
      group.names.push(model.name, model.quantization);
    }
    return [...groups.values()].map(({model, routes, names}) => {
      const engines = [...new Set(routes.map(route => route.backend))];
      return {
        id:model.id, name:model.name, model, routes, engines,
        searchText:[...names, ...engines.map(backendName), model.format].join(" "),
      };
    });
  }

  function agentHostFor(client, selectedHost, {ompRpcQualified = false} = {}) {
    return client === "omp" && ompRpcQualified !== true ? "terminal" : selectedHost;
  }

  function syncAgentHost(select, client, {ompRpcQualified = false} = {}) {
    const terminalOnly = client === "omp" && ompRpcQualified !== true;
    if (!select) return;
    const consoleOption = [...select.options].find(option => option.value === "console");
    if (consoleOption) {
      consoleOption.disabled = terminalOnly;
      consoleOption.hidden = terminalOnly;
    }
    if (terminalOnly) select.value = "terminal";
  }

  function createController(deps) {
    const {presenter, backendName, clientName, protectedSnapshot,
      formatNumber, exactContextTier, gatherOptions, runtimeKvLabel,
      currentWarmRoutePlan, clientAvailability, selectedModel, esc} = deps;
    const $ = deps.nodes ? id => deps.nodes[id] : deps.$;
    const viewKeys = ["backend", "client", "runPhase", "performanceReceipt", "performanceReceiptLoading",
      "performanceReceiptError", "launchPreparing", "applyingOptimal", "homeEngineFeedbackSignature", "homeEngineFeedback"];
    const state = deps.view ? Object.freeze(Object.defineProperties({}, Object.fromEntries(
      viewKeys.map(key => [key, {get:() => deps.view()[key]}]),
    ))) : deps.state;
    const createOption = deps.createOption || (() => deps.document.createElement("option"));
    const markPreparing = deps.markPreparing || (value => presenter.data(deps.document.body, "preparingLaunch", value));
    const text = (id, value) => presenter.property($(id), "textContent", value);
    let selectedGroup = null;

    function renderOverview(admission) {
      const model = selectedModel();
      const capability = model?.backends?.[state.backend] || {};
      text("homeRouteModel", selectedGroup?.name || model?.name || "Choose a model");
      presenter.property($("homeRouteModel"), "title", model?.name || "");
      text("homeRouteMeta", model ? [
        String(model.format || "").toUpperCase(),
        model.quantization,
        capability.runtimeVersion,
        capability.input?.includes("image") ? "Vision" : "",
      ].filter(Boolean).join(" · ") : "Select a model from your library.");
      text("homeRouteEngine", backendName(state.backend));
      text("homeRouteAgent", clientName(state.client));
      text("homeRouteContext", `${exactContextTier(Number($("contextInput").value))} tokens`);
      text("homeRouteOutput", `${formatNumber(Number($("outputInput").value))} tokens`);
      text("homeEngineGuide", engineGuidance(state.backend, capability));
      const measurements = measurementView(state.performanceReceipt, state.backend, {
        loading:state.performanceReceiptLoading, error:state.performanceReceiptError,
      });
      text("homeMeasuredSpeed", measurements.speed);
      text("homeMeasuredFirst", measurements.first);
      text("homeMeasurementDetail", measurements.detail);
      presenter.data($("homePerformance"), "state", measurements.state);
      presenter.property($("homeCompareEngines"), "disabled", !model || state.launchPreparing || state.applyingOptimal);
      const readiness = state.launchPreparing ? "Preparing" : !model ? "Select a model"
        : state.runPhase === "running" && !currentWarmRoutePlan()?.canAttach ? "Session running"
        : admission.pending || admission.decision === "checking" ? "Checking capacity"
        : !clientAvailability().available ? "Assistant unavailable"
        : ["ready", "acknowledged"].includes(admission.decision) || admission.warm ? "Ready to launch"
        : admission.decision === "qualification" ? "Capacity test needed" : "Review capacity";
      text("homeRouteReadiness", readiness);
      presenter.data($("launchOverview"), "ready", readiness === "Ready to launch");
    }

    function renderModelPicker(groups, group, busy) {
      const list = $("homeModelList");
      const filtered = filterModels(groups, $("homeModelSearch").value, group?.id);
      const markup = filtered.models.map(row => {
        const metadata = [String(row.model.format || "").toUpperCase(), row.model.quantization, row.model.sizeLabel]
          .filter(Boolean).join(" · ");
        return `<button type="button" class="model-list-item" data-home-model="${esc(row.id)}" aria-pressed="false">
          <span class="model-list-mark" aria-hidden="true">◇</span>
          <span><strong>${esc(row.name)}</strong><small>${esc(metadata)}</small></span>
        </button>`;
      }).join("");
      if (list.dataset.catalog !== markup) {
        list.innerHTML = markup;
        list.dataset.catalog = markup;
      }
      for (const button of list.querySelectorAll("[data-home-model]")) {
        presenter.attribute(button, "aria-pressed", String(button.dataset.homeModel === group?.id));
        presenter.property(button, "disabled", busy);
      }
      text("homeModelSearchStatus", filtered.filtering
        ? `${filtered.count} match${filtered.count === 1 ? "" : "es"}`
        : groups.length ? `${groups.length} available model${groups.length === 1 ? "" : "s"}` : "No runnable models found");
    }

    function update(admission, groups = []) {
      markPreparing(Boolean(state.launchPreparing));
      const model = selectedModel();
      selectedGroup = groups.find(row => row.routes.some(route => route.modelId === model?.id));
      const busy = state.launchPreparing || state.applyingOptimal;
      renderModelPicker(groups, selectedGroup, Boolean(busy));
      const engine = $("homeEngineSelect");
      const engines = selectedGroup?.engines || (model ? [state.backend] : []);
      const choices = engines.map(id => [id, backendName(id)]);
      const signature = JSON.stringify(choices);
      if (engine.dataset.catalog !== signature) {
        const options = (choices.length ? choices : [["", "Select a model"]]).map(([id, label]) => {
          const option = createOption();
          option.value = id;
          option.textContent = label;
          return option;
        });
        engine.replaceChildren(...options);
        engine.dataset.catalog = signature;
      }
      presenter.property(engine, "value", choices.some(([id]) => id === state.backend) ? state.backend : "");
      presenter.property(engine, "disabled", Boolean(busy || !selectedGroup));
      text("homeFastestEngineHelp", state.applyingOptimal
        ? "Checking saved calibration across compatible engines…"
        : state.homeEngineFeedbackSignature === protectedSnapshot() && state.homeEngineFeedback
          ? state.homeEngineFeedback : "Uses saved calibration, or measures compatible engines.");
      text("homeSettingsSummary", `${exactContextTier(Number($("contextInput").value))} context · ${formatNumber(Number($("outputInput").value))} max response · ${$("reasoningSelect").value === "auto" ? "Model-default reasoning" : $("reasoningSelect").value + " reasoning"}${state.backend === "omlx" && $("accelerationSelect").value === "dflash" ? ` · ${runtimeKvLabel("omlx", gatherOptions())} KV` : ""}`);
      for (const id of ["customLaunchEditor", "launchTools", "quickStart"]) {
        presenter.property($(id), "inert", Boolean(state.launchPreparing));
      }
      text("homeLaunchHint", state.launchPreparing ? "Getting your session ready"
        : currentWarmRoutePlan()?.canAttach ? "Your model is already loaded"
        : admission.decision === "qualification" ? "This setup needs a capacity check"
        : state.backend === "uzu" && admission.decision === "ready" ? "Saved capacity check reused"
        : "Ready when you are");
      text("homeLaunchDetail", admission.decision === "qualification"
        ? "The required capacity test runs automatically. It may take several minutes."
        : state.backend === "uzu" && admission.decision === "ready"
          ? "No repeat capacity test. Current memory and connection checks still run when you launch."
          : "Model, memory and connection checks run automatically.");
      if (!$("configScroll").classList.contains("hidden")) text("configTitle", "New session");
      if (!state.launchPreparing) text("launchSummary", currentWarmRoutePlan()?.canAttach ? "Use loaded model" : "Checks included");
      const available = clientAvailability();
      text("compatibilityLine", available.available ? `${clientName(state.client)} is available with this model.` : available.reason);
      presenter.property($("compatibilityLine"), "title", "");
      presenter.data($("compatibilityLine"), "available", Boolean(available.available));
      renderOverview(admission);
    }

    return {update, renderOverview};
  }

  return {engineGuidance, measurementView, filterModels, modelRouteGroups, agentHostFor, syncAgentHost, createController};
});
