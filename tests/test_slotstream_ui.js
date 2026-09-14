"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(require("node:path").join(__dirname,"../app.js"),"utf8");
function section(start,end) { const a=source.indexOf(start),b=source.indexOf(end,a+start.length); assert.ok(a>=0&&b>a); return source.slice(a,b); }
const elements={accelerationSelect:{value:"mtp"},depthInput:{value:"2"},slotstreamMemoryGB:{value:"34"}};
const ctx=vm.createContext({state:{backend:"slotstream"},$:id=>elements[id]});
vm.runInContext(section("function gatherOptions()", "function gatherGenerationSettings()")+section("function slotstreamDownloadMessage(","function renderModelOptions()"),ctx);
assert.deepEqual(JSON.parse(JSON.stringify(ctx.gatherOptions())),{acceleration:"mtp",depth:2,kv:"off",memoryGB:34});
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
vm.runInContext(section("function clearUnavailableModelControls()", "function modelChanged()"),ctx);
ctx.clearUnavailableModelControls();
assert.equal(options.mtp.disabled,true);assert.equal(options.dflash.disabled,true);
assert.equal(elements.accelerationSelect.value,"auto");
assert.match(elements.accelerationHelp.textContent,/Finish the model download/);
