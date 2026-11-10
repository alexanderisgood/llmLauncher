"use strict";
const launchSources=require("./helpers/launch_sources.js");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const app = launchSources.controllerSource + "\n" + require("./helpers/workspace_sources.js").consoleWorkspace;
const Timeline = require("../pi_timeline.js");
const Input = require("../agent_console_input.js");
const Drafts = require("../chat_drafts.js");
const Home = require("../launcher_home.js");

for (const protocol of ["pi-rpc", "omp-rpc"]) {
  assert.equal(Timeline.isStructuredProtocol(protocol), true);
  assert.equal(Input.isStructuredProtocol(protocol), true);
  assert.equal(Timeline.shouldUseTimeline(protocol, false), false);
  assert.equal(Timeline.shouldUseTimeline(protocol, true), true);
}
for (const protocol of ["terminal", "omp", "omp-rpc-unknown", "", null]) {
  assert.equal(Timeline.isStructuredProtocol(protocol), false);
  assert.equal(Input.isStructuredProtocol(protocol), false);
  assert.equal(Timeline.shouldUseTimeline(protocol, true), false);
}
assert.equal(Timeline.agentLabel("omp-rpc"), "oh-my-pi");
assert.equal(Input.agentLabel("omp-rpc"), "oh-my-pi");
assert.match(Input.validatePiPrompt("", "oh-my-pi").error, /oh-my-pi/);
assert.match(Input.validatePiPrompt('"'.repeat(40000), "oh-my-pi").error, /has not been cleared/);
assert.equal(Input.validatePiPrompt("exact instruction", "oh-my-pi").ok, true);
const value = Timeline.applyTimelineEnvelope(Timeline.emptyTimeline(), {
  timelineVersion:1, timelineRevision:1, timelineBaseRevision:0, timelineReset:true,
  timelineEvents:[{revision:1,itemId:"answer-one",kind:"answer",operation:"replace",text:"Kept inert <script>"}],
});
assert.equal(value.supported, true);
assert.match(Timeline.timelinePlainText(value.state, "omp-rpc"), /^oh-my-pi\n/);
assert.match(Timeline.timelinePlainText(value.state), /^Pi\n/);
assert.equal(Timeline.applyTimelineEnvelope(value.state, {timelineVersion:99}).supported, false,
  "unknown timeline versions retain the existing bounded terminal fallback");
assert.equal(Timeline.piTokenSpeed({protocol:"omp-rpc", extensionStatuses:{tokenSpeed:{text:"TPS: 900 tok/s"}}}), null,
  "Pi's extension estimate must never be attributed to oh-my-pi");

const keyStart = app.indexOf("function agentConsoleDraftKey()");
const keyEnd = app.indexOf("\nfunction agentConsoleDrafts",keyStart);
let metadata = {protocol:"pi-rpc", conversationId:"a".repeat(64)};
const context = vm.createContext({currentAgentConsoleView:() => ({meta:metadata}),agentConsoleRunDraftKey:() => "run:surface"});
launchSources.runInContext(app.slice(keyStart,keyEnd),context);
const piKey = context.agentConsoleDraftKey();
metadata = {...metadata,protocol:"omp-rpc"};
const ompKey = context.agentConsoleDraftKey();
assert.equal(piKey,"pi:"+"a".repeat(64)); assert.equal(ompKey,"omp:"+"a".repeat(64));
let drafts = Drafts.normaliseEnvelope(null);
drafts = Drafts.writeDraft(drafts,piKey,"Pi private draft",1);
drafts = Drafts.writeDraft(drafts,ompKey,"OMP private draft",2);
assert.equal(Drafts.readDraft(drafts,piKey),"Pi private draft");
assert.equal(Drafts.readDraft(drafts,ompKey),"OMP private draft");
metadata = {protocol:"omp-rpc",conversationId:"untrusted/../id"};
assert.equal(context.agentConsoleDraftKey(),"run:surface");

const host = {value:"console", options:[{value:"console",disabled:false,hidden:false},{value:"terminal"}]};
Home.syncAgentHost(host,"omp");
assert.equal(host.value,"terminal"); assert.equal(host.options[0].disabled,true);
host.value="console"; Home.syncAgentHost(host,"omp",{ompRpcQualified:true});
assert.equal(host.value,"console"); assert.equal(host.options[0].disabled,false);
assert.equal(host.options[0].hidden,false);
for (const qualified of [undefined, false, "true", 1, null]) {
  assert.equal(Home.agentHostFor("omp","console",{ompRpcQualified:qualified}),"terminal");
  host.value="console"; Home.syncAgentHost(host,"omp",{ompRpcQualified:qualified});
  assert.equal(host.value,"terminal");
}
assert.equal(Home.agentHostFor("omp","console",{ompRpcQualified:true}),"console");
assert.equal(Home.agentHostFor("omp","terminal",{ompRpcQualified:true}),"terminal",
  "Qualification never overwrites an explicit Terminal preference");
assert.equal(Home.agentHostFor("pi","console"),"console");

const elements = new Map(["projectPath","contextInput","outputInput","reasoningSelect","agentHostSelect",
  "sessionAttachClient","sessionAttachAgentHost","sessionAttachProject","sessionAttachSeed","sessionAttachSampling",
  "sessionAttachTemperature","sessionAttachTopP","sessionAttachTopK","sessionAttachPresencePenalty",
  "sessionAttachFrequencyPenalty","sessionAttachRepetitionPenalty"].map(id=>[id,{value:id.includes("AgentHost")||id==="agentHostSelect"?"console":"1",
    options:[{value:"console"},{value:"terminal"}]}]));
elements.get("sessionAttachClient").value="omp";
const gateState = {client:"omp",backend:"omlx",binaries:{},sessionDashboard:{hub:{session:{runId:"owner",project:"/generated"}}}};
const gateContext = vm.createContext({state:gateState,LauncherHomeCore:Home,$:id=>elements.get(id),
  selectedModel:()=>({id:"fixture"}),gatherOptions:()=>({}),gatherGenerationSettings:()=>({})});
for (const [begin,end] of [["function gather(mode", "\nfunction protectedSnapshot("],
  ["function sessionAttachmentRequest()", "\nfunction syncSessionAttachmentForm("]]) {
  launchSources.runInContext(app.slice(app.indexOf(begin),app.indexOf(end,app.indexOf(begin))),gateContext);
}
for (const consoleSupported of [undefined,false,"true",true]) {
  gateState.binaries = {omp:{consoleSupported}};
  elements.get("sessionAttachAgentHost").value="console";
  const expected=consoleSupported===true?"console":"terminal";
  assert.equal(gateContext.gather().agentHost,expected);
  assert.equal(gateContext.sessionAttachmentRequest().agentHost,expected);
}
gateState.client="pi";
assert.equal(gateContext.gather().agentHost,"console");
assert.ok((app.match(/state\.binaries\?\.omp\?\.consoleSupported === true/g)||[]).length>=5,
  "Requests and both host selectors must use explicit controller qualification");
console.log("OMP Hub: qualified host requests, version fallback, exact protocols, agent labels, Pi compatibility and isolated drafts passed.");
