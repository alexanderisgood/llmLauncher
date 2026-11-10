"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const app = fs.readFileSync(require.resolve("../app.js"),"utf8");
const start = app.indexOf("let launcherQuitting = false;");
const end = app.indexOf('$("quitLauncherButton").addEventListener',start);
assert.ok(start >= 0 && end > start);

function harness(responses) {
  const calls = [], notices = [], elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id,{disabled:false,hidden:false,textContent:"",open:false,listeners:{},
      showModal(){this.open=true;},close(){this.open=false;},focus(){this.focused=true;},
      addEventListener(name,callback){this.listeners[name]=callback;}});
    return elements.get(id);
  };
  let release;
  const initial = new Promise(resolve=>{release=resolve;});
  const context = vm.createContext({$:element, agentConsoleWorkspace:{cancelRead:()=>{}}, chatWorkspace:{abortResponse:()=>{}}, state:{statusTimer:7,agentConsoleTimer:null},
    clearInterval:()=>{},clearTimeout:()=>{},AbortSignal,sleep:async()=>{},
    showNotice:text=>notices.push(text),api:async(path,options)=>{
      calls.push({path,options});
      if (path === "/api/quit") {
        await initial;
        const result=responses.shift();
        if (result instanceof Error) throw result;
        return result;
      }
      const response = responses.shift();
      if (response instanceof Error) throw response;
      return response;
    },
  });
  vm.runInContext(app.slice(start,end),context);
  vm.runInContext(app.slice(end,app.indexOf('$("openSessionDashboard").addEventListener',end)),context);
  return {calls,notices,element,release,context};
}

(async()=>{
  const complete = harness([{quitting:true},{quitting:true,complete:false},{complete:true,errors:[],processesStopped:4}]);
  const request = complete.context.quitLauncher();
  await complete.context.quitLauncher();
  assert.equal(complete.calls.length,1,"Repeated Quit clicks must not dispatch another shutdown");
  assert.equal(complete.calls[0].options.method,"POST");
  assert.equal(complete.element("quitLauncherButton").disabled,true);
  let cancellationPrevented=false;
  complete.element("quitLauncherDialog").listeners.cancel({preventDefault:()=>{cancellationPrevented=true;}});
  assert.equal(cancellationPrevented,true,"Escape cannot imply an already dispatched shutdown was cancelled");
  complete.release();
  await request;
  assert.equal(complete.calls.filter(call=>call.path==="/api/quit/status").length,2);
  assert.match(complete.element("quitLauncherDetail").textContent,/have been stopped/);

  const lost = harness([{quitting:true},new Error("Connection closed")]);
  const lostRequest = lost.context.quitLauncher();lost.release();await lostRequest;
  assert.equal(lost.element("quitLauncherTitle").textContent,"Shutdown requested");
  assert.match(lost.element("quitLauncherDetail").textContent,/Shutdown was requested/);
  assert.doesNotMatch(lost.element("quitLauncherDetail").textContent,/have been stopped/,"Disconnect alone cannot verify process cleanup");

  for (const failure of [new Error("HTTP 503: controller still reachable"),new Error("Status timed out")]) {
    const unverified = harness([{quitting:true},failure]);
    const pending = unverified.context.quitLauncher();unverified.release();await pending;
    assert.equal(unverified.element("quitLauncherTitle").textContent,"Shutdown requested");
    assert.match(unverified.element("quitLauncherDetail").textContent,/could not be verified/);
    assert.equal(unverified.calls.filter(call=>call.path==="/api/quit").length,1,"Unverified completion must not replay Quit");
  }

  const partial = harness([{quitting:true},{complete:true,errors:["oMLX process did not exit"]}]);
  const partialRequest = partial.context.quitLauncher();partial.release();await partialRequest;
  assert.equal(partial.element("quitLauncherTitle").textContent,"Shutdown needs attention");
  assert.match(partial.element("quitLauncherDetail").textContent,/oMLX process did not exit/);

  const restarted = harness([{quitting:true},{quitting:false,complete:false}]);
  const restartedRequest = restarted.context.quitLauncher();restarted.release();await restartedRequest;
  assert.equal(restarted.element("quitLauncherTitle").textContent,"Shutdown requested");
  assert.doesNotMatch(restarted.element("quitLauncherDetail").textContent,/have been stopped/);

  const rejected = harness([{quitting:false,message:"Authentication rejected"},{quitting:true},{complete:true,errors:[]}]);
  const rejectedRequest = rejected.context.quitLauncher();rejected.release();await rejectedRequest;
  assert.equal(rejected.element("quitLauncherDialog").open,true,"Quit errors must stay visible even when Home notices are hidden in Console");
  assert.equal(rejected.element("quitLauncherButton").disabled,false);
  assert.match(rejected.element("quitLauncherDetail").textContent,/Authentication rejected/);
  assert.equal(rejected.element("quitLauncherErrorActions").hidden,false);
  assert.equal(rejected.element("quitLauncherRetryButton").focused,true);
  let failedCancellationPrevented=false;
  rejected.element("quitLauncherDialog").listeners.cancel({preventDefault:()=>{failedCancellationPrevented=true;}});
  assert.equal(failedCancellationPrevented,false,"Escape may dismiss a rejected request");
  await rejected.element("quitLauncherRetryButton").listeners.click();
  assert.equal(rejected.calls.filter(call=>call.path==="/api/quit").length,2,"Only an explicit Retry dispatches a second Quit");
  assert.equal(rejected.element("quitLauncherTitle").textContent,"Launcher closed");
  const expired = harness([new Error("Reconnected to the restarted launcher. This action was not sent; try again.")]);
  const expiredRequest = expired.context.quitLauncher();expired.release();await expiredRequest;
  assert.equal(expired.calls.length,1,"Authentication rejection must not automatically replay Quit");
  assert.match(expired.element("quitLauncherDetail").textContent,/was not sent/);
  console.log("Quit UI: single dispatch, verified completion, connection-loss honesty, cleanup errors and rejection recovery passed.");
})().catch(error=>{console.error(error);process.exitCode=1;});
