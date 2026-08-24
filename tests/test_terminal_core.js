"use strict";

const assert = require("node:assert/strict");
const {MAX_STYLED_RUNS, TerminalBuffer, segmentStyledRuns} = require("../terminal_core.js");

const terminal = new TerminalBuffer(40, 12, 4);
terminal.write("alpha\r\nbeta");
assert.equal(terminal.toString(), "alpha\nbeta");

terminal.write("\x1b[2J\x1b[Hready");
assert.equal(terminal.toString(), "ready");
terminal.write("\x1b[1;1HHELLO\x1b[1;3H!!");
assert.equal(terminal.toString(), "HE!!O");

terminal.write("\x1b[?1049hfull-screen\x1b[2;1Hagent\x1b[?1049l");
assert.equal(terminal.toString(), "HE!!O");

terminal.write("\r\nline-2\r\nline-3\r\nline-4\r\nline-5\r\nline-6\r\nline-7\r\nline-8\r\nline-9\r\nline-10\r\nline-11\r\nline-12\r\nline-13\r\nline-14");
assert.ok(terminal.scrollback.length <= 4);
assert.match(terminal.toString(), /line-14$/);

terminal.resize(50, 14);
assert.equal(terminal.cols, 50);
assert.equal(terminal.rows, 14);
terminal.write("\x1b[3;1Hwide: 界");
assert.match(terminal.toString(), /wide: 界/);

const wrapping = new TerminalBuffer(40, 12, 4);
wrapping.write("x".repeat(40));
assert.equal(wrapping.cursor().y, 0, "a full final column must wait before wrapping");
wrapping.write("y");
assert.equal(wrapping.cursor().y, 1, "the next printable character triggers autowrap");

const styled = new TerminalBuffer(40, 12, 4);
styled.write("\x1b[1;31mthinking\x1b[0m answer \x1b[38;5;202mindexed\x1b[0m \x1b[48;2;12;34;56mtruecolor\x1b[0m");
const styledRuns = styled.toStyledRuns();
assert.equal(styledRuns.map(run => run.text).join(""), styled.toString());
const thinking = styledRuns.find(run => run.text.includes("thinking"));
assert.equal(thinking.style.bold, true);
assert.deepEqual(thinking.style.foreground, {mode:"indexed", value:1});
assert.deepEqual(styledRuns.find(run => run.text.includes("indexed")).style.foreground, {mode:"indexed", value:202});
assert.deepEqual(styledRuns.find(run => run.text.includes("truecolor")).style.background, {mode:"rgb", red:12, green:34, blue:56});
assert.equal(styledRuns.find(run => run.text.includes("answer")).styleKey, "");
const crossStyleNeedle = "ing ans";
const crossStyleStart = styled.toString().indexOf(crossStyleNeedle);
const styledSegments = segmentStyledRuns(styledRuns, [{
  start:crossStyleStart, end:crossStyleStart + crossStyleNeedle.length,
}]);
assert.equal(styledSegments.map(segment => segment.text).join(""), styled.toString());
assert.equal(styledSegments.filter(segment => segment.matchIndex === 0).map(segment => segment.text).join(""), crossStyleNeedle);
assert.ok(new Set(styledSegments.filter(segment => segment.matchIndex === 0).map(segment => segment.styleKey)).size > 1, "search marks must retain style boundaries");

const overwritten = new TerminalBuffer(40, 12, 4);
overwritten.write("\x1b[31mA\x1b[0m\x1b[1G\x1b[32mB\x1b[0m");
assert.equal(overwritten.toString(), "B");
assert.deepEqual(overwritten.toStyledRuns()[0].style.foreground, {mode:"indexed", value:2});
overwritten.write("\x1b[1G\x1b[2Kplain");
assert.equal(overwritten.toStyledRuns()[0].styleKey, "", "erasing a line must clear stale cell styling");

const styledScrollback = new TerminalBuffer(40, 12, 4);
styledScrollback.write("\x1b[35mviolet\x1b[0m\r\n" + Array.from({length:13}, (_, index) => `line-${index}`).join("\r\n"));
assert.equal(styledScrollback.toStyledRuns().map(run => run.text).join(""), styledScrollback.toString());
assert.ok(styledScrollback.toStyledRuns().some(run => run.style.foreground?.value === 5), "scrollback must retain SGR style cells");

const hostileStyling = new TerminalBuffer(40, 12, 5000);
for (let index = 0; index < 4200; index += 1) {
  hostileStyling.write(`\x1b[${index % 2 ? 31 : 32}m${index % 10}\x1b[0m\r\n`);
}
const boundedRuns = hostileStyling.toStyledRuns();
assert.ok(boundedRuns.length <= MAX_STYLED_RUNS + 1, "style-run output must stay bounded");
assert.equal(boundedRuns.map(run => run.text).join(""), hostileStyling.toString(), "style overflow must never drop terminal text");

console.log("Hub Console terminal parser, ANSI styles, alternate screen, bounds, and resize passed");
