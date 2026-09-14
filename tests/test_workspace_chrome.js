"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const app = fs.readFileSync(require.resolve("../app.js"), "utf8");
function source(start, end) {
  const from = app.indexOf(start), to = app.indexOf(end, from);
  assert.ok(from >= 0 && to > from);
  return app.slice(from, to);
}
const mutations = [];
const previewVisibility = [];
const elements = new Map();
function element(id) {
  if (!elements.has(id)) {
    const classes = new Set(["chatWorkspace", "agentWorkspace"].includes(id) ? ["hidden"] : []);
    let text = id === "configTitle" ? "Your local AI" : "";
    elements.set(id, {hidden:true, dataset:{consoleSurface:"pi"},
      classList:{contains:name=>classes.has(name), add:name=>classes.add(name),
        toggle(name, enabled) { mutations.push([id, name, enabled]);
          if (enabled) classes.add(name); else classes.delete(name); }},
      get textContent() { return text; },
      set textContent(value) { mutations.push([id, "text", value]); text=value; },
    });
  }
  return elements.get(id);
}
const state = {agentConsoleVisible:false, agentConsoleSurfaceId:"pi", chatRunId:"",
  chatOwnerRunId:"", agentConsoleOwnerRunId:"owner", runStatus:{attachments:[]}};
const run = {runId:"owner", client:"pi"};
const context = vm.createContext({state, $:element,
  agentPiTimelineView:{setVisible:(_timeline, visible)=>previewVisibility.push(visible)},
  sessionRouteActive:()=>true, syncAgentConsoleViews:()=>{},
  currentAgentConsoleView:()=>({meta:{surface:"Pi",client:"pi",model:"Qwen"}}),
  agentConsoleShowsPiTimeline:()=>true, renderAgentConsole:()=>{},
  scheduleAgentConsoleRead:()=>{}, setChatBusy:()=>{}, updateWorkSurface:()=>{},
});
vm.runInContext([
  source("function updateWorkspaceChrome()", "\nfunction agentConsoleBaseOffset"),
  source("function updateAgentWorkspace(run, phase)", "\nfunction scheduleAgentConsoleRead"),
].join("\n"),context);
function refresh() {
  context.updateChatWorkspace(run,"running");
  context.updateAgentWorkspace(run,"running");
}
function chromeWrites() {
  return mutations.filter(([id])=>["configTitle","configScroll","launchDock"].includes(id));
}
refresh();
assert.equal(previewVisibility.at(-1),false,"Home suspends screenshot resources");
state.agentConsoleVisible=true;
refresh();
assert.equal(previewVisibility.at(-1),true,"Returning to Pi resumes screenshot resources");
assert.equal(element("configTitle").textContent,"Agent Console");
assert.ok(element("configScroll").classList.contains("hidden"));
mutations.length=0;
for(let i=0;i<200;i++) refresh();
assert.deepEqual(chromeWrites(),[],"Idle Hub polls must not briefly expose the form or replace its heading");
state.agentConsoleVisible=false;
refresh();
assert.equal(previewVisibility.at(-1),false,"Leaving Pi suspends screenshot resources");
assert.equal(element("configTitle").textContent,"Your local AI");
assert.equal(element("configScroll").classList.contains("hidden"),false);
assert.equal(element("launchDock").classList.contains("hidden"),false);
assert.equal(chromeWrites().length,3,"Home updates the heading and two visibility flags once");
element("chatWorkspace").classList.toggle("hidden",false);
context.updateWorkspaceChrome();
assert.equal(element("configTitle").textContent,"Chat");
assert.ok(element("configScroll").classList.contains("hidden"));
console.log("Workspace visibility: 200 stable Hub refreshes have zero shared-chrome mutations; Home and Chat transitions pass.");
