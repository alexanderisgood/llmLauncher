"use strict";

const assert = require("node:assert/strict");
const context = require("../workspace_context.js");

assert.deepEqual(
  context.normalisePath({webkitRelativePath:"launcher/src/chat.js"}),
  {root:"launcher", name:"src/chat.js"},
);
for (const path of ["/launcher/src/chat.js", "launcher/../secret", "~/secret.txt", "C:/secret.txt", "chat.js"]) {
  assert.equal(context.normalisePath({webkitRelativePath:path}), null);
}

const policyOptions = {
  ignoredSegments:new Set([".git", "node_modules", "dist"]),
  supported:file => /\.(?:js|md|txt|json)$/i.test(file.name),
  maximumFileBytes:512 * 1024,
};
const fake = (name, size = 100) => ({name, size});
assert.equal(context.pathPolicy("src/chat.js", fake("chat.js"), policyOptions), "ready");
assert.equal(context.pathPolicy(".env", fake(".env"), policyOptions), "sensitive");
assert.equal(context.pathPolicy("config/credentials.json", fake("credentials.json"), policyOptions), "sensitive");
assert.equal(context.pathPolicy("node_modules/pkg/index.js", fake("index.js"), policyOptions), "ignored");
assert.equal(context.pathPolicy("package-lock.json", fake("package-lock.json"), policyOptions), "generated");
assert.equal(context.pathPolicy("image.png", fake("image.png"), policyOptions), "unsupported");
assert.equal(context.pathPolicy("large.txt", fake("large.txt", 600 * 1024), policyOptions), "large");

const terms = context.queryTerms(
  "Please fix queueMessage handling in this repository",
  new Set(["please", "this", "repository", "in"]),
);
assert.deepEqual(terms, ["fix", "queue", "message", "handling"]);
const chatFile = {
  name:"src/chat.js", priority:context.candidatePriority("src/chat.js"),
  searchText:"queue message queue message", content:"queue message",
};
const readmeFile = {
  name:"README.md", priority:context.candidatePriority("README.md"),
  searchText:"general launcher overview", content:"general launcher overview",
};
assert.ok(context.fileScore(chatFile, terms) > context.fileScore(readmeFile, terms));

const longContent = `${"header\n".repeat(900)}queueMessage target\n${"tail\n".repeat(900)}`;
const clipped = context.excerpt(
  {content:longContent, searchText:longContent.toLowerCase()},
  ["queue", "message"],
  2_000,
);
assert.equal(clipped.truncated, true);
assert.ok(clipped.content.includes("queueMessage target"));
assert.ok(clipped.content.includes("Omitted text is not available"));
assert.ok(clipped.content.length <= 2_000);

assert.equal(context.availableContextCharacters({
  contextTokens:16_384, outputTokens:512, historyCharacters:1_000,
}), 40_616);
assert.equal(context.requestCharacterBudget({
  contextTokens:16_384, outputTokens:512, historyCharacters:1_000,
  maximumCharacters:96_000, contextShare:.22,
}), 10_813);
assert.equal(context.requestCharacterBudget({
  contextTokens:16_384, outputTokens:512, historyCharacters:1_000,
  manualCharacters:40_000, maximumCharacters:96_000, contextShare:.22,
}), 616);

console.log("Workspace Context policy and retrieval core passed.");
