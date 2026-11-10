"use strict";
const assert = require("node:assert/strict");
const Resume = require("../chat_resume.js");

class Element {
  constructor(document, tag = "div") {
    this.ownerDocument = document; this.tagName = tag.toUpperCase(); this.children = [];
    this.listeners = new Map(); this.attributes = {}; this.className = ""; this._text = "";
    this.value = ""; this.checked = false; this.disabled = false; this.open = false;
    this.selectionStart = this.selectionEnd = 0; this.replacements = 0;
    this.classList = {toggle:(name, enabled) => { this.attributes[name] = enabled; }};
  }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(""); }
  set innerHTML(_value) { throw new Error("Untrusted history text must use inert DOM nodes"); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; this._text = ""; this.replacements += 1; }
  querySelector(selector) {
    return this.children.find(child => child.tagName.toLowerCase() === selector)
      || this.children.map(child => child.querySelector(selector)).find(Boolean) || null;
  }
  setAttribute(name, value) { this.attributes[name] = value; }
  addEventListener(name, fn) { this.listeners.set(name, [...(this.listeners.get(name) || []), fn]); }
  emit(name) { for (const fn of this.listeners.get(name) || []) fn({target:this}); }
  focus() { this.ownerDocument.activeElement = this; }
  showModal() { this.open = true; }
  close() { this.open = false; this.emit("close"); }
}

function deferred() {
  let resolve, reject;
  const promise = new Promise((a, b) => { resolve = a; reject = b; });
  return {promise, resolve, reject};
}

function savedPlan(id = "one", changes = {}) {
  return {
    mode:"launch", ready:true, thread:{id, title:`Saved ${id}`},
    route:{backendLabel:"Kolibri SSD", backend:"kolibri", model:"Original Q6", context:8192,
      output:1024, reasoning:"off", sampling:"custom", project:"/generated/project"},
    request:{backend:"kolibri", client:"chat", modelId:"exact", project:"/generated/project", context:8192,
      output:1024, reasoning:"off", options:{kv:"off", memoryGB:12, prefillSize:64},
      generation:{sampling:"custom", temperature:0, topP:1, topK:0}},
    detail:"Exact saved settings; revalidation is read-only.", ...changes,
  };
}

function harness(options = {}) {
  const document = {activeElement:null, createElement(tag) { return new Element(this, tag); }};
  const elements = Object.fromEntries(["dialog", "route", "badge", "title", "subtitle", "promptPanel", "systemPrompt",
    "withoutPrompt", "memoryPanel", "memoryConsent", "memoryTitle", "memoryCopy", "experimentalPanel",
    "experimentalConsent", "status", "apply", "start", "startLabel"].map(key => [key, new Element(document)]));
  const calls = {plans:[], apply:[], launch:[], transcripts:[], notices:[], changes:[], onlyApply:0};
  let ready = false;
  const controller = Resume.createController({elements,
    fetchPlan:async payload => { calls.plans.push(payload); return options.fetchPlan ? options.fetchPlan(payload)
      : {plan:savedPlan(payload.id)}; },
    requestVisible:options.requestVisible || (() => true), engineVisible:() => true,
    formatNumber:String, formatBytes:value => `${value} bytes`, detailed:() => false,
    applyRequest:async request => { calls.apply.push(request); if (options.mutateApplied) request.context = 1; },
    launchRequest:async (...args) => { calls.launch.push(args); return options.launch ? options.launch(...args) : true; },
    openTranscript:async (...args) => { calls.transcripts.push(args); }, readyToOpen:() => ready,
    onApplied:() => { calls.onlyApply += 1; }, notify:(...args) => calls.notices.push(args),
    onChange:value => calls.changes.push(value),
  });
  return {controller, elements, document, calls, ready:() => { ready = true; }};
}

async function run() {
  {
    const first = deferred(), second = deferred();
    const h = harness({fetchPlan:p => p.id === "one" ? first.promise : second.promise});
    const old = h.controller.open("one"), current = h.controller.open("two");
    second.resolve({plan:savedPlan("two")}); await current;
    first.resolve({plan:savedPlan("one")}); await old;
    assert.equal(h.elements.title.textContent, "Saved two", "a stale response cannot replace the current selected conversation");
    assert.equal(h.calls.launch.length, 0); assert.equal(h.calls.apply.length, 0, "review is read-only");
  }
  {
    const h = harness(); await h.controller.open("one");
    assert.equal(await h.controller.apply(false), true);
    assert.deepEqual(h.calls.apply[0], savedPlan().request);
    assert.equal(h.calls.launch.length, 0); assert.equal(h.calls.transcripts.length, 0);
    assert.equal(h.calls.onlyApply, 1); assert.match(h.calls.notices[0][0], /Nothing was started/);
  }
  {
    const gate = deferred();
    const h = harness({mutateApplied:true, launch:() => gate.promise}); await h.controller.open("one");
    const starting = h.controller.apply(true);
    await new Promise(resolve => setTimeout(resolve, 0));
    h.ready(); await h.controller.completePending();
    h.controller.stopped("an older idle status");
    assert.equal(h.calls.transcripts.length, 0, "an old running/idle state cannot complete or cancel an unaccepted launch");
    assert.equal(h.calls.launch[0][0].context, 8192, "applying controls cannot mutate the exact launch request");
    gate.resolve(true); await starting;
    assert.equal(h.calls.transcripts.length, 1);
    assert.deepEqual(h.calls.transcripts[0], ["one", {coldResume:true, skipCurrentSave:true, systemPromptDecision:"not-required"}]);
    assert.equal(h.controller.isStarting(), false); assert.equal(h.controller.hasPending(), false);
  }
  {
    let count = 0;
    const h = harness({fetchPlan:async () => ({plan:savedPlan("one", {requiresMemoryAcknowledgement:true,
      admission:{contractId:++count === 1 ? "old" : "new", label:"Current capacity", detail:"Exact estimate"}})})});
    await h.controller.open("one"); h.elements.memoryConsent.checked = true; h.elements.memoryConsent.emit("change");
    assert.equal(await h.controller.apply(true), false);
    assert.equal(h.calls.launch.length, 0); assert.equal(h.elements.memoryConsent.checked, false,
      "capacity consent must reset when fresh planning changes its exact contract");
    assert.match(h.elements.status.textContent, /Review and approve/);
    h.elements.memoryConsent.checked = true; h.elements.memoryConsent.emit("change");
    assert.equal(await h.controller.apply(true), true); assert.equal(h.calls.launch[0][0].memoryAcknowledgement, "new");
  }
  {
    const h = harness({fetchPlan:async () => ({plan:savedPlan("one", {requiresSystemPrompt:true})})});
    await h.controller.open("one");
    h.elements.systemPrompt.value = "private replacement <script>inert</script>";
    h.elements.systemPrompt.focus(); h.elements.systemPrompt.selectionStart = 8; h.elements.systemPrompt.selectionEnd = 19;
    const details = h.elements.route.querySelector("details"); details.open = true;
    const replacements = h.elements.route.replacements;
    h.elements.systemPrompt.emit("input");
    assert.equal(h.elements.route.replacements, replacements); assert.equal(h.elements.route.querySelector("details"), details);
    assert.equal(details.open, true); assert.equal(h.document.activeElement, h.elements.systemPrompt);
    assert.equal(h.elements.systemPrompt.selectionStart, 8); assert.equal(h.elements.systemPrompt.selectionEnd, 19);
    assert.equal(await h.controller.apply(false), true);
    assert.equal(h.calls.plans[1].systemPrompt, "private replacement <script>inert</script>");
    assert.equal(h.elements.systemPrompt.value, "", "temporary prompt text is cleared after completing review");
  }
  {
    let count = 0;
    const h = harness({fetchPlan:async () => {
      const value = savedPlan("one", {requiresExperimentalApproval:true});
      if (++count > 1) value.request.modelId = "fresh-exact-model";
      return {plan:value};
    }});
    await h.controller.open("one"); h.elements.experimentalConsent.checked = true; h.elements.experimentalConsent.emit("change");
    assert.equal(await h.controller.apply(true), false);
    assert.equal(h.calls.launch.length, 0); assert.equal(h.elements.experimentalConsent.checked, false,
      "experimental approval cannot transfer to another revalidated request");
    h.elements.experimentalConsent.checked = true; h.elements.experimentalConsent.emit("change");
    assert.equal(await h.controller.apply(true), true);
    assert.equal(h.calls.launch[0][0].modelId, "fresh-exact-model");
    assert.equal(h.calls.launch[0][0].options.experimentalQualificationConsent, true);
    h.ready(); await h.controller.completePending();
    await h.controller.open("one"); assert.equal(h.elements.experimentalConsent.checked, false);
  }
  {
    const h = harness({fetchPlan:async () => ({plan:savedPlan("one", {requiresSystemPrompt:true})})});
    await h.controller.open("one");
    assert.equal(await h.controller.apply(true), false);
    assert.equal(h.calls.plans.length, 1, "missing explicit prompt choice is rejected before another API request");
    assert.match(h.elements.status.textContent, /Re-enter/);
    assert.equal(h.elements.promptPanel.attributes.hidden, false, "local choice errors keep the prompt editor available");
    h.elements.withoutPrompt.checked = true; h.elements.withoutPrompt.emit("change");
    assert.equal(await h.controller.apply(false), true);
    assert.equal(h.calls.plans[1].continueWithoutSystemPrompt, true);
    assert.equal("systemPrompt" in h.calls.plans[1], false);
  }
  {
    const text = '<img src=x onerror="globalThis.attacked=true">';
    const h = harness({fetchPlan:async () => ({plan:savedPlan("one", {thread:{id:"one", title:text},
      route:{...savedPlan().route, model:text, project:text}, detail:text})})});
    await h.controller.open("one");
    assert.equal(h.elements.title.textContent, text); assert.ok(h.elements.route.textContent.includes(text));
    assert.equal(h.elements.route.querySelector("img"), null); assert.equal(h.elements.route.querySelector("script"), null);
  }
  {
    let attempts = 0;
    const h = harness({launch:async () => { if (++attempts === 1) throw new Error("Port is already owned"); return true; }});
    await h.controller.open("one");
    assert.equal(await h.controller.apply(true), false);
    assert.match(h.elements.status.textContent, /Port is already owned/);
    assert.equal(h.elements.dialog.open, true); assert.equal(h.elements.start.disabled, false);
    assert.equal(h.controller.hasPending(), false); assert.equal(h.controller.isStarting(), false);
    assert.equal(await h.controller.apply(true), true); assert.equal(h.controller.hasPending(), true);
    h.ready(); await h.controller.completePending(); assert.equal(h.calls.transcripts.length, 1);
  }
  {
    const pending = deferred(); const h = harness({fetchPlan:() => pending.promise});
    const opening = h.controller.open("one"); h.elements.dialog.close();
    pending.resolve({plan:savedPlan()}); await opening;
    assert.equal(h.elements.dialog.open, false); assert.equal(h.elements.apply.disabled, true,
      "closing the review invalidates a late response and leaves no runnable plan");
  }
  assert.throws(() => Resume.decisionPayload({requiresSystemPrompt:true}, "one", {prompt:"text", withoutPrompt:true}), /not both/);
  assert.throws(() => Resume.decisionPayload({requiresSystemPrompt:true}, "one"), /Re-enter/);
  console.log("Saved Chat route review keeps planning inert, confirmations exact, and temporary choices private.");
}
run().catch(error => { console.error(error); process.exitCode = 1; });
