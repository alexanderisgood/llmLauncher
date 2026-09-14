"use strict";
const assert = require("node:assert/strict");
const verify = require("./uzu_browser_live_chat.cjs");

async function checkCleanup(replaced) {
  const base = "http://127.0.0.1:18080";
  const stops = [];
  const statuses = [
    {phase:"running", run:{runId:replaced ? "someone-elses-run" : "owned-run"}},
    {phase:"idle", run:null},
  ];
  const page = {
    setViewportSize:async () => {},
    waitForResponse:async () => ({status:() => 202, json:async () => ({run:{runId:"owned-run"}})}),
    locator:() => ({click:async () => {}}),
    waitForFunction:async () => {throw new Error("synthetic readiness failure");},
  };
  const context = {request:{
    get:async url => ({json:async () => url.endsWith("/api/bootstrap") ? {token:"fixture-token"} : statuses.shift()}),
    post:async (url, request) => {stops.push({url, request});},
  }};
  await assert.rejects(verify({page, context, base, output:"/unused"}),
    replaced ? /Another run replaced/ : /synthetic readiness failure/);
  assert.equal(stops.length, replaced ? 0 : 1, "Stop only the exact owned run, even after a test error");
}

(async () => {
  await checkCleanup(false);
  await checkCleanup(true);
  console.log("Browser inference harness retains failures and unloads only its exact runId.");
})().catch(error => {console.error(error); process.exitCode = 1;});
