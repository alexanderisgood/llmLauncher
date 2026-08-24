"use strict";

const assert = require("node:assert/strict");
const path = require("node:path");
const {createJiti} = require("/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/node_modules/jiti/lib/jiti.cjs");

let nextTimer = 1;
const timers = new Map();
const realSetTimeout = global.setTimeout;
const realClearTimeout = global.clearTimeout;
global.setTimeout = (callback, delay) => {
  const id = nextTimer++;
  timers.set(id, {callback, delay});
  return id;
};
global.clearTimeout = id => timers.delete(id);

function takeTimer(delay) {
  const entry = [...timers.entries()].find(([, timer]) => timer.delay === delay);
  assert.ok(entry, `expected a ${delay}ms timer`);
  timers.delete(entry[0]);
  return entry[1].callback;
}

try {
  const jiti = createJiti(__filename);
  const extension = jiti(path.resolve(__dirname, "../pi-extensions/ox-alpha-auto-continue.ts")).default;
  const handlers = new Map();
  const commands = new Map();
  const sent = [];
  const notices = [];
  const statuses = [];
  let aborted = 0;
  let idle = true;
  let pending = false;

  const pi = {
    on(name, handler) { handlers.set(name, handler); },
    registerCommand(name, command) { commands.set(name, command); },
    sendUserMessage(message, options) { sent.push({message, options}); },
  };
  const context = {
    model:{provider:"openrouter", id:"stealth/ox-alpha"},
    hasUI:true,
    isIdle:() => idle,
    hasPendingMessages:() => pending,
    abort:() => { aborted += 1; },
    ui:{
      notify:(message, level) => notices.push({message, level}),
      setStatus:(id, value) => statuses.push({id, value}),
    },
  };

  extension(pi);
  assert.ok(commands.has("ox-auto"));
  assert.ok(handlers.has("agent_settled"));

  handlers.get("session_start")({reason:"startup"}, context);
  assert.match(statuses.at(-1).value, /Ox auto: on/);

  idle = false;
  handlers.get("agent_start")({}, context);
  assert.ok([...timers.values()].some(timer => timer.delay === 180000));
  handlers.get("message_end")({message:{role:"assistant", stopReason:"stop"}}, context);
  idle = true;
  handlers.get("agent_settled")({}, context);
  takeTimer(5000)();
  assert.deepEqual(sent.at(-1), {message:"continue", options:undefined});

  // Provider errors pause rather than creating a costly retry loop.
  idle = false;
  handlers.get("agent_start")({}, context);
  handlers.get("message_end")({message:{role:"assistant", stopReason:"error", errorMessage:"rate limited"}}, context);
  idle = true;
  handlers.get("agent_settled")({}, context);
  assert.match(statuses.at(-1).value, /off/);
  assert.match(notices.at(-1).message, /rate limited/);

  // Reset re-enables. A truly silent provider stream is aborted only after
  // its follow-up has been placed in Pi's own queue.
  commands.get("ox-auto").handler("reset", context);
  idle = false;
  handlers.get("agent_start")({}, context);
  takeTimer(180000)();
  assert.deepEqual(sent.at(-1), {message:"continue", options:{deliverAs:"followUp"}});
  assert.equal(aborted, 1);

  // An executing tool exempts legitimate long builds from the watchdog.
  commands.get("ox-auto").handler("reset", context);
  idle = false;
  handlers.get("agent_start")({}, context);
  handlers.get("tool_execution_start")({toolCallId:"tool-1"}, context);
  takeTimer(180000)();
  assert.equal(aborted, 1);
  assert.ok([...timers.values()].some(timer => timer.delay === 180000));

  // Pending user work suppresses the settled continuation.
  handlers.get("tool_execution_end")({toolCallId:"tool-1"}, context);
  handlers.get("message_end")({message:{role:"assistant", stopReason:"stop"}}, context);
  idle = true;
  pending = true;
  const before = sent.length;
  handlers.get("agent_settled")({}, context);
  assert.equal(sent.length, before);
  assert.ok(![...timers.values()].some(timer => timer.delay === 5000));

  console.log("Ox Alpha auto-continue lifecycle, error, watchdog, and tool safeguards passed");
} finally {
  global.setTimeout = realSetTimeout;
  global.clearTimeout = realClearTimeout;
}
