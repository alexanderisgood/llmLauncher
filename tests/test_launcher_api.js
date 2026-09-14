"use strict";
const assert = require("node:assert/strict");
const {createClient} = require("../launcher_api.js");
const ok = data => ({ok:true,status:200,json:async()=>data});
const forbidden = () => ({ok:false,status:403,json:async()=>{throw new Error("HTML error page");}});
const post = body => ({method:"POST",body:JSON.stringify(body || {})});

function harness(handler) {
  let token = "old";
  const calls = [];
  const client = createClient({getToken:()=>token,setToken:value=>{token=value;},
    fetch:async(path, options={})=>{
      calls.push({path,...options,headers:{...options.headers}});
      return handler(path,options);
    }});
  return {client,calls,get token(){return token;},set token(value){token=value;}};
}

async function main() {
  let resolveBoot;
  const boot = new Promise(resolve=>{resolveBoot=resolve;});
  const h = harness((path,options)=>path === "/api/bootstrap" ? boot :
    options.headers["X-Launcher-Token"] === "old" ? forbidden() : ok({ready:true}));
  const first = h.client.json("/api/agent-console/read",post());
  const second = h.client.json("/api/session/plan",post());
  resolveBoot(ok({token:"new"}));
  assert.deepEqual(await Promise.all([first,second]),[{ready:true},{ready:true}]);
  assert.equal(h.calls.filter(call=>call.path === "/api/bootstrap").length,1);
  assert.equal(h.token,"new");
  assert.deepEqual(h.calls.filter(call=>call.path === "/api/agent-console/read")
    .map(call=>call.headers["X-Launcher-Token"]),["old","new"]);

  for (const [path,body] of [["/api/launch",{}],["/api/stop",{}],["/api/agent-console/input",{command:"prompt",message:"Do work"}],
      ["/api/chat",{}],["/api/hub/fans",{mode:"max"}]]) {
    const mutation = harness(path=>path === "/api/bootstrap" ? ok({token:"new"}) : forbidden());
    await assert.rejects(mutation.client.response(path,post(body)),/This action was not sent/);
    assert.equal(mutation.calls.filter(call=>call.path === path).length,1,"Never replay mutations after restart");
    assert.equal(mutation.token,"new","Reconnect still repairs subsequent reads/actions");
  }
  const fans = harness((path,options)=>path === "/api/bootstrap" ? ok({token:"new"}) :
    options.headers["X-Launcher-Token"] === "old" ? forbidden() : ok({mode:"system"}));
  assert.equal((await fans.client.json("/api/hub/fans",post({runId:"owner"}))).mode,"system");

  const denied = harness(path=>path === "/api/bootstrap" ? ok({token:"new"}) : forbidden());
  await assert.rejects(denied.client.json("/api/agent-console/read",post()),/rejected this request/);
  assert.equal(denied.calls.length,3,"A persistent rejection must stop after one retry");

  for (const status of [400,409,500,503]) {
    const failure = harness(()=>({ok:false,status,json:async()=>({error:"original error"})}));
    await assert.rejects(failure.client.json("/api/stop",post()),/original error/);
    assert.equal(failure.calls.length,1);
  }
  const network = harness(()=>{throw new TypeError("network disconnected");});
  await assert.rejects(network.client.json("/api/agent-console/input",post()),/network disconnected/);
  assert.equal(network.calls.length,1,"Unknown delivery outcomes must not retry");

  let finish;
  const waiting = new Promise(resolve=>{finish=resolve;});
  const concurrent = harness((path,options)=>path === "/api/bootstrap" ? waiting :
    options.headers["X-Launcher-Token"] === "old" ? forbidden() : ok({ready:true}));
  const controller = new AbortController();
  const cancelled = concurrent.client.json("/api/agent-console/read",{...post(),signal:controller.signal});
  const surviving = concurrent.client.json("/api/session/plan",post());
  // Allow both rejected reads to reach the shared bootstrap.
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
  controller.abort();
  concurrent.token = "newer-bootstrap";
  finish(ok({token:"stale-bootstrap"}));
  await assert.rejects(cancelled,error=>error.name === "AbortError");
  assert.deepEqual(await surviving,{ready:true});
  assert.equal(concurrent.token,"newer-bootstrap","An older refresh must not overwrite a newer token");
  assert.equal(concurrent.calls.filter(call=>call.path === "/api/agent-console/read").length,1);

  const malformed = harness(path=>path === "/api/bootstrap" ? ok({}) : forbidden());
  await assert.rejects(malformed.client.json("/api/session/plan",post()),/Could not reconnect/);
  assert.equal(malformed.token,"old");
  const stream = {ok:true,status:200,body:{stream:true},json:()=>{throw new Error("Must not consume streaming body");}};
  const streaming = harness(()=>stream);
  assert.equal(await streaming.client.response("/api/chat",post()),stream);
  console.log("Launcher API: reconnect coalescing, read-only replay, mutation safety, cancellation and streaming passed.");
}
main().catch(error=>{console.error(error);process.exitCode=1;});
