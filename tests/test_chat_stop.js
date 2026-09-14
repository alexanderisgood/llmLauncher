"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const index = fs.readFileSync(path.join(root, "index.html"), "utf8");
const launcher = fs.readFileSync(path.join(root, "launcher.py"), "utf8");
const relay = fs.readFileSync(path.join(root, "session_proxy.py"), "utf8");

const start = app.indexOf("async function stopChatResponse() {");
const end = app.indexOf("\nasync function setSessionIdlePolicy()", start);
assert.ok(start >= 0 && end > start, "Chat Stop handler must remain independently testable");
const handler = app.slice(start, end);
assert.match(handler, /controller\.launcherStopRequested = true/);
assert.match(handler, /api\("\/api\/chat\/stop"/);
assert.match(handler, /runId:state\.chatOwnerRunId/);
assert.match(handler, /attachmentId:state\.chatRunId/);
assert.match(handler, /finally \{[\s\S]*controller\.abort\(\)/);
assert.ok(
  handler.indexOf('api("/api/chat/stop"') < handler.indexOf("controller.abort()"),
  "the authenticated relay cancellation must be requested before the browser stream aborts",
);
assert.match(app, /error\.name === "AbortError" \|\| controller\.launcherStopRequested/);
assert.match(app, /chatStopButton"\)\.addEventListener\("click", stopChatResponse\)/);
assert.match(index, /title="Stop the current response and pause queued messages"/);
assert.match(launcher, /elif self\.path == "\/api\/chat\/stop":/);
assert.match(launcher, /def cancel_chat_generation\(/);
assert.match(relay, /if action == "cancel":/);
assert.match(relay, /cancelled = self\.scheduler\.cancel_surface\(surface_id\)/);

console.log("Chat Stop private-relay cancellation contract passed.");
