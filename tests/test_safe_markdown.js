"use strict";

const assert = require("node:assert/strict");
const markdown = require("../safe_markdown.js");

const sample = markdown.parse(`# Safe response

Raw HTML stays text: <script>alert("no")</script>.

**Bold**, *emphasis*, ~~removed~~, \`inline code\`, and [official](https://example.com/docs).

[unsafe](javascript:alert(1)) and [credentials](https://user:pass@example.com/) stay literal.

![diagram](https://example.com/diagram.png)

> A quoted **runtime note**.

- ordinary item
- [x] completed task

3. third
4. fourth

| Route | TPS |
|:---|---:|
| oMLX | 37.8 |

\`\`\`js
<button onclick="steal()">never HTML</button>
\`\`\``);

function walk(value, output = []) {
  if (Array.isArray(value)) value.forEach(item => walk(item, output));
  else if (value && typeof value === "object") {
    if (value.type) output.push(value);
    Object.values(value).forEach(item => walk(item, output));
  }
  return output;
}

const nodes = walk(sample.blocks);
assert.ok(nodes.some(node => node.type === "heading" && node.level === 1));
assert.ok(nodes.some(node => node.type === "strong"));
assert.ok(nodes.some(node => node.type === "emphasis"));
assert.ok(nodes.some(node => node.type === "delete"));
assert.ok(nodes.some(node => node.type === "quote"));
assert.ok(nodes.some(node => node.type === "table" && node.align.join(",") === "left,right"));
assert.ok(nodes.some(node => node.type === "code" && node.text.includes("onclick") && node.closed));
assert.equal(nodes.filter(node => node.type === "link").length, 2, "only the safe link and inert image reference may become links");
assert.ok(nodes.some(node => node.type === "link" && node.imageReference));
assert.equal(nodes.some(node => ["html", "image"].includes(node.type)), false);

const plainText = nodes.filter(node => node.type === "text").map(node => node.text).join(" ");
assert.match(plainText, /<script>alert\("no"\)<\/script>/);
assert.match(plainText, /\[unsafe\]\(javascript:alert\(1\)\)/);
assert.match(plainText, /\[credentials\]\(https:\/\/user:pass@example\.com\/\)/);

const lists = sample.blocks.filter(block => block.type === "list");
assert.equal(lists[0].items[1].checked, true);
assert.equal(lists[1].ordered, true);
assert.equal(lists[1].start, 3);

const streamingFence = markdown.parse("```python\nprint('still streaming')").blocks[0];
assert.deepEqual(
  {type:streamingFence.type, language:streamingFence.language, closed:streamingFence.closed},
  {type:"code", language:"python", closed:false},
);

assert.equal(markdown.safeLink("https://example.com/path"), "https://example.com/path");
assert.equal(markdown.safeLink("http://127.0.0.1:8080/local"), "http://127.0.0.1:8080/local");
assert.equal(markdown.safeLink("javascript:alert(1)"), null);
assert.equal(markdown.safeLink("data:text/html,bad"), null);
assert.equal(markdown.safeLink("https://user:pass@example.com"), null);
assert.equal(markdown.safeLink("https://example.com/a b"), null);

const escaped = markdown.parse("\\*literal\\* and `**code**`").blocks[0].children;
assert.deepEqual(escaped, [
  {type:"text", text:"*literal* and "},
  {type:"code", text:"**code**"},
]);

console.log("Safe streaming Markdown structure, URL policy, and inert-content handling passed.");
