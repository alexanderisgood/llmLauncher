import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const source = readFileSync(new URL('../pi-context-policy.js', import.meta.url), 'utf8');
const { installCompactionSettings, prepareMemoryCompaction } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
class Settings {
  constructor(keep = 20000) { this.keep = keep; }
  getCompactionKeepRecentTokens() { return this.keep; }
  getCompactionSettings() { return {reserveTokens:16384, keepRecentTokens:this.getCompactionKeepRecentTokens()}; }
}
const settings = new Settings();
installCompactionSettings(Settings, {memoryLimited:true});
assert.equal(settings.getCompactionKeepRecentTokens(), 8000);
assert.equal(settings.keep, 20000, 'persistent settings are untouched');
assert.equal(new Settings(4000).getCompactionKeepRecentTokens(), 4000);
const first = Settings.prototype.getCompactionKeepRecentTokens;
installCompactionSettings(Settings, {memoryLimited:true});
assert.equal(Settings.prototype.getCompactionKeepRecentTokens, first, 'reload is idempotent');
for (const reason of ['manual', 'overflow']) for (const errorMessage of ['prefill_memory_exceeded', "insufficient memory: this prompt projects 40.7 GiB against 40.0 GiB; the request was refused before prefill"]) {
  const event = { reason, preparation: { settings: { keepRecentTokens: 20000 } }, branchEntries: [
    { type: 'message', message: { role: 'assistant', errorMessage } },
  ] };
  assert.equal(prepareMemoryCompaction(event, (entries, options) => {
    assert.equal(options.keepRecentTokens, 8000);
    return { firstKeptEntryId: 'native-cut-point' };
  }), true);
  assert.equal(event.preparation.firstKeptEntryId, 'native-cut-point');
}
console.log('Pi memory settings: early cap, smaller preferences, reload and manual recovery passed');

class EarlySettings {
  getCompactionKeepRecentTokens() { return 20000; }
  getCompactionSettings() { return {enabled:true, reserveTokens:16384, keepRecentTokens:this.getCompactionKeepRecentTokens()}; }
}
installCompactionSettings(EarlySettings, {contextWindow:131072, triggerTokens:65536, memoryLimited:true});
const early = new EarlySettings().getCompactionSettings();
assert.equal(131072 - early.reserveTokens, 65536);
assert.equal(early.keepRecentTokens, 8000);
const threshold = {reason:'threshold', preparation:{settings:early}};
assert.equal(prepareMemoryCompaction(threshold, () => { throw Error('do not recut threshold'); }), false);
assert.equal(threshold.preparation.settings.reserveTokens, 16384, 'summary output budget remains native');
assert.equal(threshold.preparation.settings.launcherSummaryReserveTokens, undefined);
// Use a fresh unpatched prototype for the smaller-window case.
class Small {
 getCompactionKeepRecentTokens() { return 20000; }
 getCompactionSettings() { return {reserveTokens:8192, keepRecentTokens:this.getCompactionKeepRecentTokens()}; }
}
installCompactionSettings(Small, {contextWindow:32768, triggerTokens:65536, memoryLimited:true});
assert.equal(new Small().getCompactionSettings().reserveTokens, 8192);
console.log('Earlier 27B compaction preserves summary budget and smaller context settings');

// The 16K route must admit real work before compaction and leave room after it.
class LocalSettings {
  constructor(reserve = 16384, keep = 20000) { this.reserve = reserve; this.keep = keep; }
  getCompactionKeepRecentTokens() { return this.keep; }
  getCompactionSettings() { return {enabled:true, reserveTokens:this.reserve, keepRecentTokens:this.getCompactionKeepRecentTokens()}; }
}
installCompactionSettings(LocalSettings, {contextWindow:16384});
const local = new LocalSettings();
assert.deepEqual(local.getCompactionSettings(), {enabled:true, reserveTokens:4096, keepRecentTokens:4096});
assert.equal(16384 - local.getCompactionSettings().reserveTokens, 12288);
assert.equal(local.reserve, 16384);
assert.equal(local.keep, 20000);
assert.deepEqual(new LocalSettings(1024, 128).getCompactionSettings(), {enabled:true, reserveTokens:1024, keepRecentTokens:128});
class LargeSettings {
  getCompactionKeepRecentTokens() { return 20000; }
  getCompactionSettings() { return {enabled:true, reserveTokens:16384, keepRecentTokens:this.getCompactionKeepRecentTokens()}; }
}
installCompactionSettings(LargeSettings, {contextWindow:131072});
assert.deepEqual(new LargeSettings().getCompactionSettings(), {enabled:true, reserveTokens:16384, keepRecentTokens:20000});
console.log('16K context has a 12K admission threshold; smaller preferences and large-window defaults remain intact');

class DisabledSettings {
  getCompactionKeepRecentTokens() { return 128; }
  getCompactionSettings() { return {enabled:false, reserveTokens:1024, keepRecentTokens:this.getCompactionKeepRecentTokens(), customPreference:'kept'}; }
}
installCompactionSettings(DisabledSettings, {contextWindow:16384});
assert.deepEqual(new DisabledSettings().getCompactionSettings(), {
  enabled:false, reserveTokens:1024, keepRecentTokens:128, customPreference:'kept',
}, 'The shared policy preserves disabled compaction and lower user preferences');
