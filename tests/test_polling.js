"use strict";
const assert = require("node:assert/strict");
const {createPoller} = require("../polling.js");

(async () => {
  let now = 0, calls = 0, release;
  const poller = createPoller({now:() => now});
  const poll = poller.add("held", {interval:10, run:() => {
    calls++;
    return new Promise(resolve => { release = resolve; });
  }});
  const first = poll();
  assert.equal(poll(), first, "Manual and timer polling share one in-flight request");
  await Promise.resolve();
  now = 100;
  await poller.tick();
  assert.equal(calls, 1, "A slow request must never create a backlog");
  release("ready");
  assert.equal(await first, "ready");
  const second = poll();
  await Promise.resolve();
  assert.equal(calls, 2);
  release();
  await second;

  let attempts = 0;
  const retry = poller.add("failure", {interval:1, run:() => {
    if (++attempts === 1) throw new Error("offline");
    return "recovered";
  }});
  await assert.rejects(retry(), /offline/);
  assert.equal(await retry(), "recovered", "Failures release the in-flight slot");

  const counts = Array(8).fill(0);
  const scheduled = createPoller({now:() => now});
  let visible = false;
  for (let i = 0; i < 8; i++) scheduled.add(String(i), {
    interval:() => i === 0 || visible ? 1800 : 30000,
    run:() => counts[i]++,
  });
  for (now = 0; now < 60000; now += 1800) await scheduled.tick();
  assert.deepEqual(counts, [34, 2, 2, 2, 2, 2, 2, 2]);
  visible = true;
  await scheduled.tick();
  assert.equal(counts[1], 3, "Opening a panel resumes frequent polling immediately");
  let disabledCalls = 0;
  scheduled.add("disabled", {interval:Infinity, run:() => disabledCalls++});
  await scheduled.tick();
  assert.equal(disabledCalls, 0);
  console.log("Polling: coalescing, failure recovery, visibility and 272 → 48 background requests/minute passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });
