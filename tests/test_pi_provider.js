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
    apiKey:"local", headers:{}, model:{
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
    assert.equal(registered.value.models[0].compat.supportsReasoningEffort, true);
    assert.deepEqual(registered.value.models[0].thinkingLevelMap, {off:"none", medium:"medium"});
    assert.ok(handlers.has("message_end"));
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
    console.log("Pi provider response-limit recovery notice passed");
  } finally {
    if (previous === undefined) delete process.env.LLM_LAUNCHER_PI_PROVIDER;
    else process.env.LLM_LAUNCHER_PI_PROVIDER = previous;
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
