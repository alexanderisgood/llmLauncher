"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const core = require("../agent_console_input.js");
const app = fs.readFileSync(require("node:path").join(__dirname, "../app.js"), "utf8");
const start = app.indexOf("async function changeAgentConsoleQueuedMessage(");
const end = app.indexOf("\nfunction renderAgentConsole()", start);
assert.ok(start >= 0 && end > start);

async function main() {
  const first = {command:"prompt", message:"same"};
  const second = {command:"prompt", message:"same"};
  const view = {inputQueue:[first, second]};
  const notices = [], requests = [];
  let fail = false;
  const context = vm.createContext({
    AgentConsoleInputCore:core,
    currentAgentConsoleView:() => view,
    state:{agentConsoleSurfaceId:"surface", agentConsoleOwnerRunId:"owner"},
    renderAgentConsole:() => {}, scheduleAgentConsoleRead:() => {},
    showNotice:message => notices.push(message),
    reconcileAgentConsoleViewMeta:(target, meta) => { target.meta = meta; },
    api:async (url, options) => {
      requests.push({url, body:JSON.parse(options.body)});
      if (fail) throw new Error("Queue changed; original preserved");
      return {console:{pendingMessages:1}};
    },
  });
  vm.runInContext(app.slice(start, end), context);
  const change = context.changeAgentConsoleQueuedMessage;
  let entries = core.piQueueEntries({}, view.inputQueue);
  await change(view, entries[1], "edit", "new text\non two lines");
  assert.equal(first.message, "same");
  assert.equal(second.message, "new text\non two lines");
  await change(view, entries[0], "delete");
  assert.deepEqual(view.inputQueue, [second]);
  assert.equal(requests.length, 0, "Unsent browser entries are edited locally");
  await change(view, entries[0], "delete");
  assert.equal(notices.length, 1, "An entry already removed/sent cannot remove its successor");
  assert.deepEqual(view.inputQueue, [second]);

  const item = {source:"server", id:"snapshot:1", editable:true};
  view.queueEdit = {item, text:"keep my draft"};
  fail = true;
  await change(view, item, "edit", "keep my draft");
  assert.equal(view.queueEdit.text, "keep my draft", "Failed saves preserve the editor");
  assert.equal(view.queueMutationBusy, false);
  fail = false;
  await change(view, item, "edit", "keep my draft");
  assert.equal(view.queueEdit, null);
  assert.deepEqual(requests.at(-1).body, {ownerRunId:"owner", surfaceId:"surface",
    command:"edit_queued_message", queueId:"snapshot:1", message:"keep my draft"});
  await change(view, item, "delete");
  assert.equal(requests.at(-1).body.command, "delete_queued_message");
  const count = requests.length;
  await change(view, item, "edit", "   ");
  assert.equal(requests.length, count, "Empty edits never reach the server");
  entries = core.piQueueEntries({queuedMessages:[
    {message:"queued", id:"q:0", editable:true}, {message:"steering", kind:"steer"},
  ]}, [], [first]);
  assert.equal(entries[0].editable, true);
  assert.equal(entries[1].editable, false);
  assert.ok(!entries[2].editable, "Already-sending messages cannot be unsent");
  console.log("Queue edits preserve duplicates, stale selections and unsaved drafts.");
}
main().catch(error => { console.error(error); process.exitCode = 1; });
