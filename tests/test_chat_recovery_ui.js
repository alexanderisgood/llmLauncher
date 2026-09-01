"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const app = fs.readFileSync(path.resolve(__dirname, "..", "app.js"), "utf8");

assert.match(app, /ChatStreamCore\.messageContextCharacters\(message\)/);
assert.match(app, /ChatStreamCore\.pausedQueueRecoveryAction\(action, message, isMessageTail\)/);
assert.match(app, /\.some\(ChatStreamCore\.blocksIncompleteTailRecovery\)/);
assert.match(app, /"retry", incompleteKind === "failed" \? "Retry message" : "Retry answer"/);
assert.match(app, /async function retryIncompleteChatMessage\(messageId\)/);
assert.match(app, /incompleteRecoveryOperation\(selected\) === "continue"/);
assert.match(app, /operation:"continue", recoverPausedQueue:true/);
assert.match(app, /state\.chatMessages\[userIndex\]\.exclude = false/);
assert.match(app, /recoverPausedQueue:true/);
assert.match(app, /let turnOutcome = "incomplete"/);
assert.match(app, /ChatStreamCore\.responseTerminalState\(event\)/);
assert.match(app, /ChatStreamCore\.finalResponseTerminalState\(terminalState, doneSeen\)/);
assert.match(app, /assistant\.failure = normaliseChatFailure\(error\.message\)/);
assert.match(app, /assistant\.interrupted = true/);
assert.match(app, /if \(assistant\.truncated\) \{[^]*?reasoningOnlyLimit/);
assert.match(app, /message\.content \|\| incompleteKind === "truncated"/);
assert.match(app, /operation === "continue" && message\.role === "assistant"[^]*?message\.truncated/);
assert.match(app, /turnOutcome = "truncated"/);
assert.match(app, /ChatStreamCore\.shouldDrainQueue\(turnOutcome\)/);
assert.match(app, /\.filter\(ChatStreamCore\.shouldPersistHistoryMessage\)/);

console.log("Incomplete local-chat turns preserve and safely resume the paused queue.");
