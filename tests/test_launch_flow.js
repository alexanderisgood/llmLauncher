"use strict";
const assert = require("node:assert/strict");
const {test} = require("node:test");
const {create} = require("../launch_flow.js");
const original = {backend:"uzu",client:"pi",modelId:"local",context:131072,output:16384,reasoning:"auto",project:"/project",agentHost:"console",generation:{samplingMode:"model"},options:{kv:"off",acceleration:"off"}};
const ready = {decision:"ready",launchable:true,requiresAcknowledgement:false};
const plan = {routeQualification:true,ready:true,action:"measure",memoryAdmission:ready};
const qualified = {...plan,action:"apply-existing",evidence:{qualified:true}};
function harness(handler, extras={}) {
  const calls = [], updates = [];
  const flow = create({
    api:async (path, options) => {const request=options?.body ? JSON.parse(options.body) : undefined;calls.push({path,request});return handler(path,request,calls);},
    update:value=>updates.push(value),isCurrent:()=>true,review:async()=>{throw new Error("Unexpected review");},pause:async()=>{},...extras,
  });
  return {flow,calls,updates};
}
test("ready launch preserves every setting and starts no optional test",async()=>{
  const h=harness(()=>({sessions:{admission:ready}}));
  assert.deepEqual(await h.flow.prepare(original),original);
  assert.deepEqual(h.calls.map(c=>c.path),["/api/session/plan"]);
});
test("qualification runs once, revalidates success and admits original Pi settings",async()=>{
  let sessions=0,plans=0;
  const h=harness(path=>{
    if(path==="/api/session/plan")return {sessions:{admission:++sessions===1?{decision:"qualification"}:ready}};
    if(path==="/api/calibration/plan")return {plan:++plans===1?plan:qualified};
    if(path==="/api/benchmark/start")return {benchmark:{id:"owned"}};
    if(path==="/api/benchmark/status")return {job:{id:"owned"},phase:"completed"};
    throw new Error(path);
  });
  assert.deepEqual(await h.flow.prepare(original),original);
  const start=h.calls.find(c=>c.path==="/api/benchmark/start").request;
  assert.equal(start.client,"chat");assert.equal(start.scope,"qualification");assert.equal(start.context,131072);assert.equal(start.output,16384);
  assert.equal(original.client,"pi");assert.equal(sessions,2);
});
test("128K automatically stages the required 64K capacity test, preserving selected context",async()=>{
  let sessions=0;const measured=new Set();let job=0,context=0;
  const h=harness((path,r)=>{
    if(path==="/api/session/plan")return {sessions:{admission:++sessions===1?{decision:"qualification"}:ready}};
    if(path==="/api/calibration/plan")return {plan:measured.has(r.context)?qualified:r.context===131072&&!measured.has(65536)?{...plan,ready:false,memoryAdmission:{stagedQualification:{reason:"missing-64k-receipt"}}}:plan};
    if(path==="/api/benchmark/start"){context=r.context;return {benchmark:{id:String(++job)}};}
    if(path==="/api/benchmark/status"){measured.add(context);return {job:{id:String(job)},phase:"completed"};}
    throw new Error(path);
  });
  assert.deepEqual(await h.flow.prepare(original),original);
  assert.deepEqual(h.calls.filter(c=>c.path==="/api/benchmark/start").map(c=>c.request.context),[65536,131072]);
});
for(const admission of [undefined,{decision:"pressure",launchable:false,detail:"Close heavy apps"},{decision:"unknown"}]) {
  test(`unavailable capacity never authorizes launch: ${admission?.decision}`,async()=>{
    const h=harness(()=>({sessions:{admission}}));await assert.rejects(h.flow.prepare(original));assert.equal(h.calls.length,1);
  });
}
test("memory review happens inline, and only exact acknowledgement is returned",async()=>{
  const h=harness(()=>({sessions:{admission:{...ready,requiresAcknowledgement:true,contractId:"exact"}}}),{review:async a=>a.contractId==="exact"});
  assert.equal((await h.flow.prepare(original)).memoryAcknowledgement,"exact");
});
test("declined memory review stops launch",async()=>{
  const h=harness(()=>({sessions:{admission:{...ready,requiresAcknowledgement:true,contractId:"exact"}}}),{review:async()=>false});
  await assert.rejects(h.flow.prepare(original),/cancelled/);
});
test("finished but unqualified test does not launch or rerun indefinitely",async()=>{
  const h=harness(path=>path==="/api/session/plan"?{sessions:{admission:{decision:"qualification"}}}:path==="/api/calibration/plan"?{plan}:path==="/api/benchmark/start"?{benchmark:{id:"owned"}}:{job:{id:"owned"},phase:"completed"});
  await assert.rejects(h.flow.prepare(original),/without a matching/);
  assert.equal(h.calls.filter(c=>c.path==="/api/benchmark/start").length,1);
});
test("a failed capacity test is never treated as a pass",async()=>{
  const h=harness(path=>path==="/api/session/plan"?{sessions:{admission:{decision:"qualification"}}}:path==="/api/calibration/plan"?{plan}:path==="/api/benchmark/start"?{benchmark:{id:"owned"}}:{job:{id:"owned"},phase:"failed",message:"Memory guard stopped the test"});
  await assert.rejects(h.flow.prepare(original),/Memory guard/);
});
test("cancel during start stops only the job returned to this launch",async()=>{
  let h;h=harness(path=>{
    if(path==="/api/session/plan")return {sessions:{admission:{decision:"qualification"}}};
    if(path==="/api/calibration/plan")return {plan};
    if(path==="/api/benchmark/start"){h.flow.cancel();return {benchmark:{id:"owned"}};}
    if(path==="/api/benchmark/status")return {job:{id:"owned"},phase:"running"};
    if(path==="/api/benchmark/stop")return {ok:true};
    throw new Error(path);
  });
  await assert.rejects(h.flow.prepare(original),/cancelled/);
  assert.deepEqual(h.calls.find(c=>c.path==="/api/benchmark/stop").request,{jobId:"owned"});
});
test("changed settings stop preparation before any model load",async()=>{
  let current=true;const h=harness(()=>{current=false;return {sessions:{admission:{decision:"qualification"}}};},{isCurrent:()=>current});
  await assert.rejects(h.flow.prepare(original),/Settings changed/);assert.equal(h.calls.length,1);
});
test("a replaced job is never cancelled by this launch",async()=>{
  const h=harness(path=>path==="/api/session/plan"?{sessions:{admission:{decision:"qualification"}}}:path==="/api/calibration/plan"?{plan}:path==="/api/benchmark/start"?{benchmark:{id:"owned"}}:{job:{id:"someone-else"},phase:"running"});
  await assert.rejects(h.flow.prepare(original),/capacity check changed/);
  assert.equal(h.calls.some(c=>c.path==="/api/benchmark/stop"),false);
});
test("qualification never silently runs an engine comparison",async()=>{
  const h=harness(path=>path==="/api/session/plan"?{sessions:{admission:{decision:"qualification"}}}:{plan:{...plan,routeQualification:false}});
  await assert.rejects(h.flow.prepare(original),/needs attention/);assert.equal(h.calls.length,2);
});
