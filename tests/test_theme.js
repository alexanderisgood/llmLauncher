"use strict";

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
assert.match(styles, /--mac-control-height:34px/);
assert.match(styles, /--mac-action-height:42px/);
assert.match(styles, /\.focused-run-status,\s*\n:root\[data-theme="frost"\] \.interface-detail-button,\s*\n:root\[data-theme="frost"\] \.local-chip\{height:var\(--mac-control-height\)/);
assert.match(styles, /\.optimize-button,\s*\n:root\[data-theme="frost"\] \.optimizer-menu-button,\s*\n:root\[data-theme="frost"\] \.performance-receipt/);
assert.match(styles, /\.calibration-actions,\.route-check-actions,\.benchmark-actions/);

console.log("Theme validation, persistence, and blocked-storage fallback passed; Frost control alignment passed.");
