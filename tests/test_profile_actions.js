"use strict";
const benchmarkSources = require("./helpers/benchmark_sources.js");

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const RoutePreferenceCore = require("../route_preferences.js");
const connectSavedLaunches = require("./helpers/saved_launches_harness.js");

const app = benchmarkSources.controllerSource;
const html = fs.readFileSync(path.join(__dirname, "../index.html"), "utf8");
const plain = value => JSON.parse(JSON.stringify(value));
const APPLIED_PROFILE_KEY = "llm-launcher-applied-profile-v1";
function between(start, end) {
  const from = app.indexOf(start), to = app.indexOf(end, from + start.length);
  assert.ok(from >= 0 && to > from, `Missing production profile functions: ${start}`);
  return app.slice(from, to);
}

class Element {
  constructor() {
    this.value = "";
    this.textContent = "";
    this.innerHTML = "";
    this.className = "";
    this.dataset = {};
    this.options = [];
    this.disabled = false;
    this.open = false;
    this.hidden = false;
    this.children = new Map();
    this.listeners = new Map();
    const classes = new Set();
    this.classList = {
      add: (...names) => names.forEach(name => classes.add(name)),
      remove: (...names) => names.forEach(name => classes.delete(name)),
      contains: name => classes.has(name),
      toggle(name, force) {
        const enabled = force === undefined ? !classes.has(name) : Boolean(force);
        if (enabled) classes.add(name); else classes.delete(name);
        return enabled;
      },
    };
  }
  querySelector(selector) {
    if (!this.children.has(selector)) this.children.set(selector, new Element());
    return this.children.get(selector);
  }
  setAttribute(name, value) { this[name] = String(value); }
  removeAttribute(name) { delete this[name]; }
  close() { this.open = false; }
  showModal() { this.open = true; }
  focus() { this.focused = true; }
  scrollIntoView() { this.scrolled = true; }
  addEventListener(name, callback) { this.listeners.set(name, callback); }
  async click() {
    if (!this.disabled) return this.listeners.get("click")?.({target:this});
  }
}

function fixture({runPhase = "running", storage = new Map()} = {}) {
  const nodes = new Map();
  const $ = id => {
    if (!nodes.has(id)) nodes.set(id, new Element());
    return nodes.get(id);
  };
  const select = (id, values, initial = values[0]) => {
    $(id).options = values.map(value => ({value, disabled:false}));
    $(id).value = initial;
  };
  select("modelSelect", ["unrelated", "saved-model"]);
  select("reasoningSelect", ["auto", "medium", "low"]);
  select("agentHostSelect", ["terminal", "hub"]);
  select("accelerationSelect", ["off", "dflash"]);
  select("samplingMode", ["model", "custom"]);
  select("profilePolicySelect", ["fixed", "measured"]);
  select("profileGoalSelect", ["throughput", "latency"]);
  select("dflashDraftQuantSelect", ["q4", "q8"]);
  $("contextInput").value = "131072";
  $("outputInput").value = "16384";
  $("projectPath").value = "/tmp/unrelated-project";
  $("profileEditBanner").hidden = true;
  $("profileRunNotice").hidden = true;
  $("profileRunAction").textContent = html.match(/id="profileRunAction"[^>]*>([^<]*)</)?.[1] || "";
  $("profileDialog").open = true;

  const profile = {
    id:"saved-42", name:"Saved game setup", ready:true, enginePolicy:"fixed",
    enginePreference:"throughput", updatedAt:"2026-09-08T09:00:00Z",
    request:{backend:"omlx", client:"pi", modelId:"saved-model", project:"/tmp/saved-game",
      context:32768, output:4096, reasoning:"medium", agentHost:"hub",
      options:{acceleration:"dflash", kv:"off", dflashDraftQuant:"q8"},
      generation:{sampling:"model"}},
  };
  const state = {
    backend:"mtplx", client:"chat", runPhase, routeCheckPhase:"idle",
    benchmarkPhase:"idle", setupPhase:"idle", profileBusy:false, profileLoading:false,
    applyingOptimal:false, launchPending:false, profiles:[plain(profile)], profileLimit:32,
    profileEditingId:"", profileDeleteConfirmId:"", quickStartLoading:false,
  };
  const calls = [], notices = [], persisted = [];
  let inventory = async () => ({profiles:[plain(profile)]});
  let save = async () => ({profiles:[plain(profile)]});
  let launches = 0;
  let sessionOpens = 0;
  let refreshes = 0;
  const context = vm.createContext({
    state, $, console, RoutePreferenceCore,
    themeStorage:() => ({
      getItem:key => storage.get(key) ?? null,
      setItem:(key, value) => storage.set(key, String(value)),
      removeItem:key => storage.delete(key),
    }),
    acquisitionIsActive:() => false, aneWorkIsActive:() => false,
    uiProfileVisible:() => true, uiRequestVisible:() => true,
    profileUiReady:p => p.ready === true,
    profileUiReason:p => p.reason || "Ready to apply.",
    measuredProfileEvidenceBinding:() => null, activeEvidenceBindingFor:() => null,
    copiedEvidenceBinding:value => value ? plain(value) : null,
    requestUsesExperimentalFreeToken:() => false,
    freeTokenExperimentalConsentRequired:() => false,
    enginePreferenceLabels:{throughput:"Highest speed"},
    backendName:value => value, clientName:value => value,
    esc:value => String(value ?? ""), formatNumber:value => String(value),
    renderQuickStart() {}, setQuickStartEditor() {},
    refreshLaunchability() { refreshes++; }, cancelOptimization() {}, updateBackend() {},
    // Model selection saves defaults before the remaining profile fields load.
    modelChanged() { context.persistVisibleRoute(); },
    persistVisibleRoute() { persisted.push(plain(context.gather())); return true; },
    setRangeVisual() {}, updateChatSamplingControls() {}, updateAccelerationState() {},
    setOptimizationState() {}, MTPLX_OPERATOR_ROUTE_DEFAULT:"default",
    setRuntimeKvValue(_backend, value) { $("kvFixture").value = value; return true; },
    showNotice(message, error = false) { notices.push({message, error}); },
    requestAnimationFrame(callback) { callback(); },
    async launch() { launches++; return true; },
    openSessionDashboard() { sessionOpens++; },
    async applyOptimal() { throw new Error("Editing must not start optimization."); },
    async api(endpoint, options = {}) {
      const body = options.body ? JSON.parse(options.body) : null;
      calls.push({endpoint, body});
      if (endpoint === "/api/profiles") return inventory();
      if (endpoint === "/api/profiles/save") return save(body);
      throw new Error(`Unexpected runtime action: ${endpoint}`);
    },
    gather() {
      return {backend:state.backend, client:state.client, modelId:$("modelSelect").value,
        project:$("projectPath").value, context:Number($("contextInput").value),
        output:Number($("outputInput").value), reasoning:$("reasoningSelect").value,
        agentHost:$("agentHostSelect").value,
        options:{acceleration:$("accelerationSelect").value, kv:$("kvFixture").value,
          dflashDraftQuant:$("dflashDraftQuantSelect").value},
        generation:{sampling:$("samplingMode").value}};
    },
  });
  benchmarkSources.runInContext(between('function runtimeKvLabel(', 'function updateOmlxKvControl('), context);
  benchmarkSources.runInContext(
    between("function currentVisibleRoute(", "function persistVisibleRoute(")
      + between("function profileSettingsBlockReason(", "function profileBackendLabel(")
      + between("function profileBackendLabel(", "function measuredProfileEvidenceBinding(")
      + between("function profileDate(", "async function deleteSavedProfile("), context,
  );
  benchmarkSources.runInContext(between('function profileExternalSettingsReason()', 'const profilesManager ='), context);
  const manager=connectSavedLaunches(context);
  for(const [key,field] of Object.entries({profiles:"profiles",profileBusy:"busy",profileLoading:"loading",
    profileEditingId:"editingId",profileEditingEvidenceBinding:"editingEvidence",profileDeleteConfirmId:"deleteConfirmId"})) {
    Object.defineProperty(state,key,{configurable:true,get:()=>manager.snapshot()[field]});
  }
  if(!storage.size)manager.useInventory({profiles:[plain(profile)]});
  benchmarkSources.runInContext(between('$("projectPath").addEventListener(', '$("agentHostSelect").addEventListener('), context);
  return {context, state, $, profile, manager, calls, notices, persisted, storage, get launches() { return launches; },
    get refreshes() { return refreshes; },
    get sessionOpens() { return sessionOpens; },
    selectRoute(request = profile.request) {
      state.backend = request.backend;
      state.client = request.client;
      $("modelSelect").value = request.modelId;
    },
    inventory(fn) { inventory = fn; }, save(fn) { save = fn; }};
}

test("Apply during a running session changes only the saved draft controls", async () => {
  const f = fixture();
  await f.context.applySavedProfile(f.profile.id, false);
  assert.deepEqual(plain(f.context.gather()), f.profile.request);
  assert.equal(f.persisted[0].context, 131072, "The early model-selection save still contains old defaults");
  assert.deepEqual(f.persisted.at(-1), f.profile.request,
    "The final saved draft must contain the fully restored profile, so refresh keeps its settings");
  assert.equal(f.state.runPhase, "running");
  assert.equal(f.launches, 0);
  assert.deepEqual(f.calls.map(call => call.endpoint), ["/api/profiles"]);
  assert.equal(f.$("profileDialog").open, false);
  assert.equal(f.state.profileBusy, false);
  assert.deepEqual([...f.storage], [[APPLIED_PROFILE_KEY, f.profile.id]],
    "Only the saved profile ID is stored; the folder remains in the server inventory");
});

test("A fresh page restores the matching profile folder from current server inventory using only its ID", async () => {
  const applied = fixture();
  await applied.context.applySavedProfile(applied.profile.id, false);
  const fresh = fixture({storage:applied.storage});
  fresh.selectRoute();
  const updated = {...fresh.profile, request:{...fresh.profile.request, project:"/tmp/server-updated-game"}};
  fresh.context.useProfileInventory({profiles:[updated]});
  assert.equal(fresh.$("projectPath").value, updated.request.project);
  assert.equal(fresh.refreshes, 1);
  assert.equal(fresh.$("contextInput").value, "131072", "Restoration changes only the folder");
  assert.deepEqual([...fresh.storage], [[APPLIED_PROFILE_KEY, fresh.profile.id]]);
  assert.equal(fresh.calls.length, 0);
  assert.equal(fresh.launches, 0);
});

test("A missing saved profile or different backend, model, or client leaves the folder unchanged", () => {
  for (const mismatch of [{backend:"mtplx"}, {modelId:"unrelated"}, {client:"chat"}, {missing:true}, {project:""}]) {
    const f = fixture({storage:new Map([[APPLIED_PROFILE_KEY, "saved-42"]])});
    f.selectRoute({...f.profile.request, ...mismatch});
    const profile = mismatch.project === "" ? {...f.profile, request:{...f.profile.request, project:""}} : f.profile;
    f.context.useProfileInventory({profiles:mismatch.missing ? [] : [profile]});
    assert.equal(f.$("projectPath").value, "/tmp/unrelated-project", JSON.stringify(mismatch));
    assert.equal(f.refreshes, 0);
    assert.equal(f.calls.length, 0);
  }
});

test("A manual folder change clears the reference and later inventory refreshes do not overwrite it", async () => {
  const f = fixture();
  await f.context.applySavedProfile(f.profile.id, false);
  f.$("projectPath").value = "/tmp/manually-chosen-game";
  f.$("projectPath").listeners.get("input")({target:f.$("projectPath")});
  assert.equal(f.storage.has(APPLIED_PROFILE_KEY), false);
  f.context.useProfileInventory({profiles:[f.profile]});
  assert.equal(f.$("projectPath").value, "/tmp/manually-chosen-game");
  const fresh = fixture({storage:f.storage});
  fresh.selectRoute();
  fresh.context.useProfileInventory({profiles:[fresh.profile]});
  assert.equal(fresh.$("projectPath").value, "/tmp/unrelated-project");
  assert.equal(fresh.refreshes, 0);
});

test("Project restoration runs once per page and saving an edited folder restores the profile reference", async () => {
  const f = fixture({storage:new Map([[APPLIED_PROFILE_KEY, "saved-42"]])});
  f.selectRoute();
  f.context.useProfileInventory({profiles:[f.profile]});
  f.context.useProfileInventory({profiles:[{...f.profile, request:{...f.profile.request, project:"/tmp/later-server-folder"}}]});
  assert.equal(f.$("projectPath").value, f.profile.request.project);
  assert.equal(f.refreshes, 1, "Repeated inventory updates must not change an already restored draft");
  await f.context.editProfile(f.profile.id);
  assert.deepEqual([...f.storage], [[APPLIED_PROFILE_KEY, f.profile.id]]);
  f.$("projectPath").value = "/tmp/edited-game";
  f.$("projectPath").listeners.get("input")({target:f.$("projectPath")});
  assert.equal(f.storage.has(APPLIED_PROFILE_KEY), false);
  let updated;
  f.save(async body => ({profiles:[updated = {...f.profile, request:body.request}]}));
  await f.$("profileEditSave").click();
  assert.equal(updated.request.project, "/tmp/edited-game");
  assert.deepEqual([...f.storage], [[APPLIED_PROFILE_KEY, f.profile.id]]);
  const fresh = fixture({storage:f.storage});
  fresh.selectRoute();
  fresh.context.useProfileInventory({profiles:[updated]});
  assert.equal(fresh.$("projectPath").value, "/tmp/edited-game");
});

test("Edit awaits the saved controls, then Save persists the edited draft, not unrelated settings", async () => {
  const f = fixture();
  let resolveInventory;
  f.inventory(() => new Promise(resolve => { resolveInventory = resolve; }));
  const editing = f.context.editProfile(f.profile.id);
  assert.equal(f.$("contextInput").value, "131072");
  assert.equal(f.state.profileEditingId, "");
  assert.equal(f.$("profileEditBanner").hidden, true);
  assert.equal(f.persisted.length, 0);
  resolveInventory({profiles:[plain(f.profile)]});
  await editing;
  assert.equal(f.state.profileEditingId, f.profile.id);
  assert.equal(f.$("profileDialog").open, false);
  assert.equal(f.$("profileEditBanner").hidden, false);
  assert.equal(f.$("launchSettings").open, true, "Edit exposes the actual settings that the user can change");
  assert.equal(f.$("advancedControls").open, false, "Editing does not force diagnostic controls open");
  assert.match(f.$("profileEditName").textContent, /Saved game setup/);
  assert.deepEqual(plain(f.context.gather()), f.profile.request);
  assert.deepEqual(f.persisted.at(-1), f.profile.request);
  f.$("contextInput").value = "65536";
  f.$("reasoningSelect").value = "low";
  await f.$("profileEditSave").click();
  const saved = f.calls.find(call => call.endpoint === "/api/profiles/save").body;
  assert.equal(saved.id, f.profile.id);
  assert.equal(saved.name, f.profile.name);
  assert.deepEqual(saved.request, {...f.profile.request, context:65536, reasoning:"low"});
  assert.equal(f.state.profileEditingId, "");
  assert.equal(f.$("profileEditBanner").hidden, true);
  assert.equal(f.launches, 0);
  assert.equal(f.state.runPhase, "running");
});

test("Launch is blocked with a visible session action while Apply and Edit remain available", async () => {
  const f = fixture();
  f.context.renderProfiles();
  assert.equal(f.$("profileRunNotice").hidden, false);
  assert.match(f.$("profileRunMessage").textContent, /session|running/i);
  assert.match(f.$("profileRunAction").textContent, /Open sessions/);
  for (const action of ["apply", "edit"]) {
    const tag = f.$("profileCards").innerHTML.match(new RegExp(`<button[^>]*data-profile-${action}="saved-42"[^>]*>`));
    assert.ok(tag, `${action} button exists`);
    assert.doesNotMatch(tag[0], /\bdisabled\b/);
  }
  await f.context.applySavedProfile(f.profile.id, true);
  assert.equal(f.launches, 0);
  assert.equal(f.calls.length, 0);
  assert.equal(f.$("contextInput").value, "131072");
  assert.match(f.$("profileManagerStatus").textContent, /session|running/i);
  await f.$("profileRunAction").click();
  assert.equal(f.sessionOpens, 1);
  assert.equal(f.$("profileDialog").open, false);
  assert.equal(f.calls.length, 0, "Open sessions must not stop or launch an engine");
});

test("An empty name explains why Save is unavailable", async () => {
  const f = fixture();
  f.$("profileName").value = "   ";
  f.context.updateProfilePolicyControls();
  assert.equal(f.$("profileSaveButton").disabled, true);
  assert.match(f.$("profileSaveButton").querySelector("small").textContent, /Enter a profile name/);
  assert.match(f.$("profileNameHint").textContent, /Enter a (?:profile )?name/i);
  await f.context.saveCurrentProfile();
  assert.equal(f.calls.length, 0);
  assert.match(f.$("profileManagerStatus").textContent, /profile.*name/i);
});

test("A profile whose model is absent cannot open an editor over unrelated controls", async () => {
  const f = fixture();
  f.inventory(async () => ({profiles:[{...f.profile, ready:false, reason:"Saved model is unavailable."}]}));
  f.$("modelSelect").options = [{value:"unrelated", disabled:false}];
  await f.context.editProfile(f.profile.id);
  assert.equal(f.state.profileEditingId, "");
  assert.equal(f.$("contextInput").value, "131072");
  assert.equal(f.$("profileEditBanner").hidden, true);
  assert.ok(f.notices.some(notice => notice.error && /no longer available/.test(notice.message)));
  assert.equal(f.calls.some(call => call.endpoint === "/api/profiles/save"), false);
});

test("Switching from an open editor to an unavailable profile clears the previous save target", async () => {
  const f = fixture();
  await f.context.editProfile(f.profile.id);
  assert.equal(f.state.profileEditingId, f.profile.id);
  const absent = {...f.profile, id:"saved-missing", name:"Unavailable setup", ready:false,
    request:{...f.profile.request, modelId:"missing-model"}};
  const inventory = [plain(f.profile), plain(absent)];
  f.inventory(async () => ({profiles:plain(inventory)}));
  await f.context.editProfile(absent.id);
  assert.equal(f.state.profileEditingId, "");
  assert.equal(f.$("profileEditBanner").hidden, true);
  assert.equal(f.$("profileEditSave").disabled, true);
  await f.$("profileEditSave").click();
  assert.equal(f.calls.some(call => call.endpoint === "/api/profiles/save"), false);
  assert.deepEqual(plain(f.state.profiles), inventory);
  assert.ok(f.notices.some(notice => notice.error && /no longer available/.test(notice.message)));
});

test("Save failures remain visible with the modal closed; cancelling never saves", async () => {
  const f = fixture();
  await f.context.editProfile(f.profile.id);
  f.save(async () => { throw new Error("Profile storage is unavailable."); });
  await f.$("profileEditSave").click();
  assert.equal(f.$("profileDialog").open, false);
  assert.equal(f.state.profileEditingId, f.profile.id);
  assert.ok(f.notices.some(notice => notice.error && /storage is unavailable/.test(notice.message)));
  const beforeCancel = f.calls.length;
  await f.$("profileEditCancel").click();
  assert.equal(f.state.profileEditingId, "");
  assert.equal(f.$("profileEditBanner").hidden, true);
  assert.equal(f.calls.length, beforeCancel);
  assert.equal(f.launches, 0);
});

test("Stale measured profiles can be edited without optimization and retain their evidence for save validation", async () => {
  const f = fixture();
  const evidence = {scope:"route", preference:"throughput", recordId:"measurement-42"};
  const stale = {...f.profile, ready:false, enginePolicy:"measured", evidenceBinding:evidence,
    reason:"Run Calibration again before using this measured profile."};
  f.inventory(async () => ({profiles:[plain(stale)]}));
  await f.context.editProfile(stale.id);
  assert.equal(f.state.profileEditingId, stale.id);
  assert.deepEqual(plain(f.context.gather()), stale.request);
  assert.deepEqual(f.persisted.at(-1), stale.request);
  assert.deepEqual(plain(f.state.profileEditingEvidenceBinding), evidence);
  assert.notEqual(f.state.profileEditingEvidenceBinding, evidence);
  await f.$("profileEditSave").click();
  const saved = f.calls.find(call => call.endpoint === "/api/profiles/save").body;
  assert.equal(saved.enginePolicy, "measured");
  assert.deepEqual(saved.evidenceBinding, evidence);
  assert.equal(f.launches, 0);
  assert.deepEqual(f.calls.map(call => call.endpoint), ["/api/profiles", "/api/profiles/save"]);
});

test("Preparation blocks draft changes and reports why even outside the modal", async () => {
  const f = fixture({runPhase:"starting"});
  f.state.launchPreparing = true;
  f.$("profileDialog").open = false;
  await f.context.applySavedProfile(f.profile.id, false);
  assert.equal(f.calls.length, 0);
  assert.equal(f.$("contextInput").value, "131072");
  assert.ok(f.notices.some(notice => notice.error && notice.message.length));
});

test("Loading, profile writes and optimization cannot race a second Apply", async () => {
  for (const field of ["profileLoading", "profileBusy", "applyingOptimal"]) {
    const f = fixture();
    let complete, pending;
    if(field==="applyingOptimal")f.state.applyingOptimal=true;
    else {
      f.inventory(()=>new Promise(resolve=>{complete=resolve;}));
      pending=field==="profileLoading"?f.manager.load():f.context.applySavedProfile(f.profile.id,false);
    }
    assert.ok(f.context.profileSettingsBlockReason(), `${field} must block draft changes`);
    const previousCalls=f.calls.length;
    await f.context.applySavedProfile(f.profile.id, false);
    assert.equal(f.calls.length, previousCalls, `${field} must not fetch or apply another profile`);
    assert.equal(f.$("contextInput").value, "131072");
    if(complete){complete({profiles:[plain(f.profile)]});await pending;}
  }
});

test("The editor and blocked-run affordances exist in the actual page", () => {
  for (const id of ["profileEditBanner", "profileEditName", "profileEditSave", "profileEditCancel", "profileRunNotice", "profileRunAction"]) {
    assert.ok(html.includes(`id="${id}"`), `Missing profile action element: ${id}`);
  }
});
