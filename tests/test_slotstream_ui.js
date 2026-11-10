"use strict";
const launchSources=require("./helpers/launch_sources.js");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = launchSources.controllerSource;
function section(start,end) { const a=source.indexOf(start),b=source.indexOf(end,a+start.length); assert.ok(a>=0&&b>a); return source.slice(a,b); }
const elements={accelerationSelect:{value:"mtp"},depthInput:{value:"2"},slotstreamMemoryGB:{value:"34"},slotstreamMemoryMode:{value:"auto"},slotstreamKv:{value:"off"}};
const ctx=vm.createContext({state:{backend:"slotstream"},$:id=>elements[id]});
launchSources.runInContext(section("function gatherOptions()", "function gatherGenerationSettings()")+section("function slotstreamDownloadMessage(","function renderModelOptions()"),ctx);
assert.deepEqual(JSON.parse(JSON.stringify(ctx.gatherOptions())),{acceleration:"mtp",depth:2,kv:"off",memoryGB:34,memoryMode:"auto"});
elements.accelerationSelect.value="off"; elements.slotstreamMemoryGB.value="28";
assert.equal(ctx.gatherOptions().memoryGB,28);
assert.equal(ctx.gatherOptions().acceleration,"off");
assert.match(ctx.slotstreamDownloadMessage({slotstream:{completeFiles:8,totalFiles:25,ready:false,mtp:false}}),/8 of 25 files complete/);
assert.match(ctx.slotstreamDownloadMessage({slotstream:{completeFiles:24,totalFiles:25,ready:true,mtp:false}}),/MTP head is still missing/);
assert.equal(ctx.slotstreamDownloadMessage({slotstream:{ready:true,mtp:true}}),"");
console.log("Slotstream controls and download status passed");

const options={mtp:{disabled:false},dflash:{disabled:false}};
elements.accelerationSelect={value:"dflash",querySelector:selector=>options[selector.includes("mtp")?"mtp":"dflash"]};
elements.accelerationHelp={textContent:"DFlash available"};
elements.contextInput={removeAttribute:()=>{}};elements.outputInput={removeAttribute:()=>{}};
ctx.updateAccelerationState=()=>{};ctx.updateChatSamplingControls=()=>{};
launchSources.runInContext(section("function clearUnavailableModelControls()", "function modelChanged()"),ctx);
ctx.clearUnavailableModelControls();
assert.equal(options.mtp.disabled,true);assert.equal(options.dflash.disabled,true);
assert.equal(elements.accelerationSelect.value,"dflash");
assert.match(elements.accelerationHelp.textContent,/Finish the model download/);

ctx.selectedModel=()=>({backends:{slotstream:{mtp:false}}});
launchSources.runInContext(section("function accelerationSelectionError(", "function clearUnavailableModelControls()"),ctx);
elements.accelerationSelect.value="mtp";
assert.match(ctx.accelerationSelectionError(),/Selected MTP is unavailable/);
assert.equal(ctx.accelerationSelectionError({mtp:true}),"");
assert.equal(elements.accelerationSelect.value,"mtp");
for (const backend of ["uzu", "freetoken", "swiftlm", "mference", "whallm", "splash", "llamacpp"]) {
  ctx.state.backend = backend;
  assert.equal(ctx.accelerationSelectionError({mtp:false,dflash:false}), "", backend);
}
ctx.state.backend = "slotstream";
assert.match(ctx.accelerationSelectionError({mtp:false}), /Selected MTP is unavailable/);
assert.doesNotMatch(section("function modelChanged()", "async function loadModels("),/acceleration.value = "auto"/);

ctx.selectedModel=()=>({nativeContext:262144,backends:{slotstream:{contextWindows:[16384,32768,65536,131072,262144],outputMaximum:261120}}});
ctx.formatNumber=n=>n.toLocaleString("en-US");
elements.contextInput.value="131072"; elements.outputInput.value="100000";
launchSources.runInContext(section("function limitError()", "function compactNativeContext("),ctx);
assert.equal(ctx.limitError(),"");
elements.contextInput.value="65536";
assert.match(ctx.limitError(),/smaller than context/);

const html=fs.readFileSync(require("node:path").join(__dirname,"../index.html"),"utf8");
assert.doesNotMatch(html.match(/<input[^>]*id="slotstreamMemoryGB"[^>]*>/)[0], /\bmax=/);
elements.slotstreamMemoryGB.value="48";
assert.equal(ctx.gatherOptions().memoryGB,48);

elements.slotstreamKv.value="q8";
assert.equal(ctx.gatherOptions().kv,"q8");
