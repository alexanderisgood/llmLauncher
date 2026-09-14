"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

(async () => {
  const source = fs.readFileSync(path.resolve(__dirname, "../pi-provider.js"), "utf8");
  const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
  const provider = (await import(moduleUrl)).default;
  const handlers = new Map();
  const notices = [];
  let registered;
  const previous = process.env.LLM_LAUNCHER_PI_PROVIDER;
  process.env.LLM_LAUNCHER_PI_PROVIDER = JSON.stringify({
    id:"launcher-test", name:"Launcher test", baseUrl:"http://127.0.0.1:1/v1",
    apiKey:"local", headers:{}, transportModel:"wire-model", model:{
      id:"model-test", name:"Model test", reasoning:true,
      supportsReasoningEffort:true,
      thinkingLevelMap:{off:"none", medium:"medium"},
      contextWindow:131072, maxTokens:16384,
    },
  });
  try {
    provider({
      on(name, handler) { handlers.set(name, handler); },
      registerProvider(id, value) { registered = {id, value}; },
    });
    assert.equal(registered.id, "launcher-test");
    assert.deepEqual(registered.value.models[0].input, ["text"]);
    const visionContract = JSON.parse(process.env.LLM_LAUNCHER_PI_PROVIDER);
    visionContract.model.input = ["text", "image"];
    process.env.LLM_LAUNCHER_PI_PROVIDER = JSON.stringify(visionContract);
    let visionRegistered;
    provider({on() {}, registerProvider(_id, value) { visionRegistered = value; }});
    assert.deepEqual(visionRegistered.models[0].input, ["text", "image"]);
    for (const [name, client, expected] of [
      ["qwopus3.8-27b-flash-mxfp4-vision-mtplx", "pi", "native"],
      ["Qwen3.8-27B-MLX-6bit", "pi", undefined],
      ["qwopus3.8-27b-flash", undefined, undefined],
    ]) {
      const config = {...visionContract, model:{...visionContract.model, name}};
      process.env.LLM_LAUNCHER_PI_PROVIDER = JSON.stringify(config);
      const nativeHandlers = new Map();
      provider({on:(event, handler)=>nativeHandlers.set(event,handler), registerProvider() {}});
      const event = {headers:client ? {"x-mtplx-client":client} : {}};
      nativeHandlers.get("before_provider_headers")(event, {sessionManager:{getSessionId:()=>"saved-session"}});
      assert.equal(event.headers["x-mtplx-tool-prompt-mode"], expected);
    }
    const payload={model:"model-test",messages:[{role:"user",content:"hi"}]};
    const transported=handlers.get("before_provider_request")({payload});
    assert.equal(transported.model,"wire-model");
    assert.equal(payload.model,"model-test","keep Pi's stable model identity untouched");
    assert.equal(transported.messages,payload.messages);
    assert.equal(handlers.get("before_provider_request")({payload:{model:"unrelated"}}),undefined);
    assert.equal(registered.value.models[0].compat.supportsReasoningEffort, true);
    assert.deepEqual(registered.value.models[0].thinkingLevelMap, {off:"none", medium:"medium"});
    assert.ok(handlers.has("message_end"));
    const statuses = [];
    let contextTokens = 27858;
    const statusContext = {hasUI:true, ui:{setStatus:(key,text) => statuses.push({key,usage:JSON.parse(text)})},
      getContextUsage:() => ({tokens:contextTokens,contextWindow:131072})};
    handlers.get("session_start")({},statusContext);
    assert.equal(statuses.at(-1).key, "launcher.context");
    assert.equal(statuses.at(-1).usage.tokens, 27858);
    contextTokens = null;
    handlers.get("session_compact")({},statusContext);
    assert.equal(statuses.at(-1).usage.tokens, null);
    contextTokens = 4096;
    handlers.get("agent_end")({},statusContext);
    assert.equal(statuses.at(-1).usage.tokens, 4096);
    const context = {hasUI:true, ui:{notify:(message, level) => notices.push({message, level})}};
    handlers.get("message_end")({message:{role:"assistant", stopReason:"stop"}}, context);
    assert.equal(notices.length, 0);
    handlers.get("message_end")({message:{role:"assistant", stopReason:"length"}}, context);
    assert.equal(notices.length, 1);
    assert.equal(notices[0].level, "warning");
    assert.match(notices[0].message, /Send “continue”/);
    handlers.get("message_end")({message:{
      role:"assistant", stopReason:"stop",
      content:[{type:"thinking", thinking:"still working"}],
    }}, context);
    assert.equal(notices.length, 2);
    assert.match(notices[1].message, /without a final response/);
    assert.match(notices[1].message, /queued follow-ups stay paused/);
    handlers.get("message_end")({message:{
      role:"assistant", stopReason:"stop",
      content:[{type:"thinking", thinking:"work"}, {type:"text", text:"done"}],
    }}, context);
    assert.equal(notices.length, 2);
    for (const stopReason of ["aborted", "error", undefined]) {
      handlers.get("message_end")({message:{
        role:"assistant", stopReason,
        content:[{type:"thinking", thinking:"interrupted work"}],
      }}, context);
      assert.equal(notices.length, 2, `${stopReason} is not a clean thinking-only finish`);
    }
    console.log("Pi provider response-limit recovery notice passed");
  } finally {
    if (previous === undefined) delete process.env.LLM_LAUNCHER_PI_PROVIDER;
    else process.env.LLM_LAUNCHER_PI_PROVIDER = previous;
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
