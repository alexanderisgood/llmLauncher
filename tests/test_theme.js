"use strict";
const benchmarkSources = require("./helpers/benchmark_sources.js");

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const themes = require("../theme.js");

assert.equal(themes.DEFAULT_THEME, "graphite");
assert.equal(themes.DEFAULT_DETAIL, "focused");
assert.deepEqual(themes.THEMES.map(theme => theme.id), ["frost", "graphite", "daylight", "ember", "midnight"]);
assert.deepEqual(themes.DETAIL_LEVELS.map(level => level.id), ["focused", "detailed"]);
assert.equal(themes.normaliseTheme(" DAYLIGHT "), "daylight");
assert.equal(themes.normaliseTheme(" FROST "), "frost");
assert.equal(themes.normaliseTheme(" EMBER "), "ember");
assert.equal(themes.normaliseTheme("unknown"), "graphite");
assert.equal(themes.normaliseTheme({secret:true}), "graphite");
assert.equal(themes.normaliseDetail(" DETAILED "), "detailed");
assert.equal(themes.normaliseDetail("unknown"), "focused");
assert.equal(themes.normaliseDetail({secret:true}), "focused");

const values = new Map();
const storage = {
  getItem:key => values.get(key) || null,
  setItem:(key, value) => values.set(key, value),
};
const element = {dataset:{}};

assert.equal(themes.initialiseTheme(element, storage), "graphite");
assert.equal(element.dataset.theme, "graphite");
assert.deepEqual(themes.writeTheme(storage, "ember"), {theme:"ember", stored:true});
assert.equal(values.get(themes.STORAGE_KEY), "ember");
assert.equal(themes.initialiseTheme(element, storage), "ember");
assert.equal(element.dataset.theme, "ember");
assert.equal(themes.applyTheme(element, "midnight"), "midnight");
assert.equal(element.dataset.theme, "midnight");
assert.equal(themes.initialiseDetail(element, storage), "focused");
assert.equal(element.dataset.detail, "focused");
assert.deepEqual(themes.writeDetail(storage, "detailed"), {detail:"detailed", stored:true});
assert.equal(values.get(themes.DETAIL_STORAGE_KEY), "detailed");
assert.equal(themes.initialiseDetail(element, storage), "detailed");
assert.equal(element.dataset.detail, "detailed");
assert.equal(themes.applyDetail(element, "focused"), "focused");
assert.equal(element.dataset.detail, "focused");

values.set(themes.STORAGE_KEY, "daylight");
values.set(themes.DETAIL_STORAGE_KEY, "detailed");
assert.deepEqual(themes.initialiseAppearance(element, storage), {theme:"daylight", detail:"detailed"});
assert.equal(element.dataset.theme, "daylight");
assert.equal(element.dataset.detail, "detailed");

const blockedStorage = {
  getItem() { throw new Error("blocked"); },
  setItem() { throw new Error("blocked"); },
};
assert.equal(themes.readTheme(blockedStorage), "graphite");
assert.deepEqual(themes.writeTheme(blockedStorage, "midnight"), {theme:"midnight", stored:false});
assert.equal(themes.readDetail(blockedStorage), "focused");
assert.deepEqual(themes.writeDetail(blockedStorage, "detailed"), {detail:"detailed", stored:false});

const styles = fs.readFileSync(path.join(__dirname, "..", "styles.css"), "utf8");
const index = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
const app = benchmarkSources.controllerSource;
assert.match(styles, /--mac-control-height:34px/);
assert.match(styles, /--mac-action-height:42px/);
assert.match(styles, /\.launch-dock,\.optimization-panel\{align-items:start\}/);
assert.match(styles, /\.config-pane\{container-type:inline-size;container-name:launch-config\}/);
assert.match(styles, /\.optimizer-action\{min-width:220px\}/);
assert.match(styles, /@container launch-config \(max-width:880px\)\{\s*\.launch-dock\{grid-template-columns:minmax\(0,1fr\)\}/);
assert.match(styles, /\.performance-receipt\{height:44px;min-height:44px\}/);
assert.match(styles, /\.dock-actions>#launchButton\{width:200px;min-width:0;flex:0 0 200px\}/);
assert.match(styles, /#launchSummary\{max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap\}/);
assert.match(styles, /:root\[data-detail="focused"\] \.optimization-panel\{grid-template-columns:minmax\(0,1fr\)\}/);
assert.match(styles, /#backendChoices \.choice\{min-height:42px;padding:6px\}/);
assert.match(styles, /:root\[data-theme="frost"\] \.segmented\{min-height:42px/);
assert.match(styles, /\.chat-composer-actions \.secondary\.compact\{height:34px\}/);
assert.match(styles, /\.agent-console-keys \.primary,\.agent-console-keys \.secondary\.compact\{height:34px\}/);
assert.match(styles, /:root\[data-theme="frost"\] \.chat-composer-actions \.secondary\.compact,[\s\S]*:root\[data-theme="frost"\] \.agent-console-keys \.primary,[\s\S]*:root\[data-theme="frost"\] \.agent-console-keys \.secondary\.compact\{height:var\(--mac-control-height\)/);
assert.match(styles, /:root\[data-detail="focused"\] \.setup-grid>\.config-section\{margin-top:0\}/);
assert.match(styles, /:root\[data-theme="frost"\] \.app-workspace\{width:100%;max-width:1440px;height:100%;margin:0 auto/);
assert.match(styles, /\.focused-run-status,\s*\n:root\[data-theme="frost"\] \.interface-detail-button,\s*\n:root\[data-theme="frost"\] \.local-chip\{height:var\(--mac-control-height\)/);
assert.match(styles, /\.optimize-button,\s*\n:root\[data-theme="frost"\] \.optimizer-menu-button,\s*\n:root\[data-theme="frost"\] \.performance-receipt/);
assert.match(styles, /\.calibration-actions,\.route-check-actions,\.benchmark-actions/);
assert.match(index, /id="calibrationStartButton"[^>]*class="calibration-run-action primary"/);
assert.match(styles, /\.calibration-run-action\{min-width:205px;display:flex;align-items:center;justify-content:center;gap:9px\}/);
assert.match(styles, /\.calibration-actions>button\{height:44px\}/);
assert.match(styles, /\.agent-console-header-actions>button,\.agent-console-interaction-actions>button\{height:31px\}/);
assert.match(styles, /:root\[data-theme="frost"\] \.agent-console-header-actions>button,\s*\n:root\[data-theme="frost"\] \.agent-console-interaction-actions>button\{height:var\(--mac-compact-height\)/);
assert.doesNotMatch(app, /\$\("calibration(?:Start|Apply)Button"\)\.className\s*=/);
assert.match(app, /\$\("calibrationStartButton"\)\.classList\.toggle\("secondary", evidenceReady\)/);
assert.match(styles, /\.skeleton\{[^}]*linear-gradient\(90deg,var\(--surface-raised\),var\(--surface-strong\),var\(--surface-raised\)\)/);
assert.match(styles, /\.chat-sidebar-search button:hover:not\(:disabled\)\{background:var\(--surface-hover\);color:var\(--text\)\}/);
assert.match(styles, /\.chat-message\.interrupted \.chat-message-body\{[^}]*color:var\(--text\)/);
assert.match(styles, /\.chat-branch-badge\{[^}]*color:var\(--secondary\)/);
assert.match(styles, /\.chat-history-branch\{[^}]*color:var\(--secondary\)!important/);
assert.doesNotMatch(styles, /\.chat-sidebar-search button:hover:not\(:disabled\)\{background:#/);
assert.doesNotMatch(styles, /\.chat-branch-badge\{[^}]*color:#/);
assert.doesNotMatch(styles, /\.chat-history-branch\{[^}]*color:#[^}]*!important/);
assert.doesNotMatch(styles, /\.chat-message\.interrupted \.chat-message-body\{[^}]*color:#/);
assert.match(styles, /::-webkit-slider-runnable-track\{[^}]*var\(--surface-strong\)/);
assert.match(styles, /::-moz-range-track\{[^}]*background:var\(--surface-strong\)/);
assert.doesNotMatch(styles, /\.range-field input\[type="range"\][^\n]*#3b3a3b/);
assert.doesNotMatch(styles, /\.range-field input\[type="range"\][^\n]*#15161a/);

const frostDesktopCanvas = styles.indexOf(':root[data-theme="frost"] .app-workspace{width:100%;max-width:1440px;height:100%;margin:0 auto');
const frostResponsiveCanvas = styles.indexOf(':root[data-theme="frost"] .app-workspace{width:100%;height:auto;margin:0;border:0;border-radius:0;box-shadow:none}', frostDesktopCanvas);
assert.ok(frostDesktopCanvas >= 0 && frostResponsiveCanvas > frostDesktopCanvas, "Frost narrow-screen canvas override must follow its desktop precision rule");

assert.match(styles, /\.agent-workspace\{background:#000!important;color:#f5f7fa\}/);
assert.match(styles, /\.agent-workspace \.agent-console-header,[^\n]*background:#090a0c!important/);
assert.match(styles, /\.agent-workspace \.agent-terminal-shell,\.agent-workspace \.agent-terminal-viewport,\.agent-workspace \.agent-pi-timeline-viewport\{background:#000!important\}/);

console.log("Theme validation, persistence, and blocked-storage fallback passed; Frost alignment, light-surface tokens, and fixed-black Hub surfaces passed.");
