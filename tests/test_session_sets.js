"use strict";
const assert = require("node:assert/strict");
const SessionSets = require("../session_sets.js");

class Element {
  constructor(document) {
    this.ownerDocument=document; this.open=false; this.disabled=false; this.checked=false;
    this.value=""; this.textContent=""; this.className=""; this.htmlWrites=0; this.listeners={};
    this.selectionStart=this.selectionEnd=0; this.parts={}; this.attributes={};
    this.classList={add:()=>{},remove:()=>{},toggle:()=>{}};
  }
  set innerHTML(value) {this.markup=value;this.htmlWrites++;}
  get innerHTML() {return this.markup||"";}
  querySelector(name) {return this.parts[name] ||= new Element(this.ownerDocument);}
  querySelectorAll() {return [];}
  contains() {return false;}
  getAttribute(name) {return this.attributes[name]??null;}
  addEventListener(name,fn) {(this.listeners[name] ||= []).push(fn);}
  emit(name) {for(const fn of this.listeners[name]||[]) fn({target:this});}
  focus() {this.ownerDocument.activeElement=this;}
  showModal() {this.open=true;}
  close() {this.open=false;this.emit("close");}
  scrollIntoView() {}
}
const ids=["openSessionSets","sessionSetDialog","sessionSetStatus","sessionSetPlanPanel","sessionSetOpenButton",
  "sessionSetStopButton","sessionSetConsentPanel","sessionSetPlanWarning","sessionSetPlanTitle","sessionSetPlanState",
  "sessionSetPlanDetail","sessionSetPlanFacts","sessionSetConsentTitle","sessionSetConsentCopy","sessionSetConsent",
  "sessionSetCountBadge","sessionSetSaveSummary","sessionSetName","sessionSetSaveButton","sessionSetCancelEdit","sessionSetCards"];
const request={backend:"kolibri",client:"omp",modelId:"original-q6",context:8192,output:1024,reasoning:"off",
  agentHost:"console",options:{memoryGB:12,kv:"off",prefillSize:64,promptCacheGB:1},
  generation:{sampling:"custom",temperature:0,seed:42},project:"/generated"};
const set=(id="one")=>({id,name:"<img src=x onerror=alert(1)> "+id,ready:true,baseRequest:request,
  surfaceCount:2,surfaceLabels:["oh-my-pi","Chat"],modelName:"Original Q6",updatedAt:"2026-10-06"});
const plan=(id="one",changes={})=>({setId:id,setName:"Saved "+id,ready:true,mode:"reuse",confirmation:"exact-confirmation",
  surfaceCount:2,existingMatchCount:1,willOpenSurfaceCount:1,hubConsoleCount:1,chatCount:1,terminalCount:0,...changes});
function deferred() {let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
function harness(overrides={}) {
  const document={activeElement:null};
  const elements=Object.fromEntries(ids.map(id=>[id,new Element(document)]));
  const calls={inventory:0,status:0,plan:[],open:[],save:[],remove:[],stop:0,apply:[],refresh:0,notices:[]};
  let workspace={run:{runId:"active",model:"Original Q6",backend:"kolibri"},surfaceCount:2};
  const api={inventory:async()=>{calls.inventory++;return {sets:[set()],limit:16};},status:async()=>{calls.status++;return {sessionSet:{phase:"idle"}};},
    plan:async body=>{calls.plan.push(body);return {plan:plan(body.id)};},
    open:async body=>{calls.open.push(body);return {sessionSet:{phase:"attaching",jobId:"job",setId:body.id,mode:"reuse",message:"Opening missing surfaces"}};},
    save:async body=>{calls.save.push(body);return {sets:[set(body.id||"new")]};},
    remove:async body=>{calls.remove.push(body);return {sets:[]};},
    stop:async()=>{calls.stop++;return {sessionSet:{phase:"cancelled",setId:"one",jobId:"job",message:"Remaining surfaces stopped"}};},...overrides};
  const controller=SessionSets.createController({elements,api,workspace:()=>workspace,visible:item=>item.baseRequest?.backend!=="hidden",
    backendLabel:() => "Kolibri SSD",formatNumber:String,dateLabel:()=>"Saved locally",experimental:()=>false,canApply:()=>true,
    applyPrimary:body=>{calls.apply.push(body);body.context=1;},openEditor:()=>{},notify:(...args)=>calls.notices.push(args),
    refreshRoute:async()=>{calls.refresh++;},schedule:fn=>fn()});
  return {controller,elements,calls,document,api,noWorkspace:()=>{workspace=null;}};
}
const consent=h=>{h.elements.sessionSetConsent.checked=true;h.elements.sessionSetConsent.emit("change");};

(async()=>{
  {
    const h=harness();await h.controller.show();
    assert.equal(h.calls.inventory,1);assert.equal(h.calls.status,1);assert.equal(h.calls.open.length,0);
    assert.equal(h.calls.plan.length,0,"Opening the manager is side-effect-free");
    assert.match(h.elements.sessionSetCards.innerHTML,/&lt;img/);assert.doesNotMatch(h.elements.sessionSetCards.innerHTML,/<img/);
    h.controller.useInventory({sets:[set(),{...set("hidden"),baseRequest:{backend:"hidden"}}]});
    assert.equal(h.controller.snapshot().sets.length,1,"Hidden routes remain filtered");
  }
  {
    const h=harness();await h.controller.show();
    h.api.plan=async()=>({plan:plan("one",{requiresExperimentalApproval:true,admission:{requiresAcknowledgement:true,contractId:"capacity"}})});
    await h.controller.review("one");await h.controller.open();assert.equal(h.calls.open.length,0);
    consent(h);assert.equal(h.elements.sessionSetOpenButton.disabled,false);await h.controller.open();
    assert.deepEqual(h.calls.open,[{id:"one",confirmation:"exact-confirmation",experimentalQualificationConsent:true,memoryAcknowledgement:"capacity"}]);
    assert.equal(h.calls.save.length,0,"Opening never persists approval or assembles new surface settings");
    h.controller.useStatus({sessionSet:{phase:"completed",jobId:"job",setId:"one",message:"Opened"}},true);
    h.controller.useStatus({sessionSet:{phase:"completed",jobId:"job",setId:"one",message:"Opened"}},true);
    assert.equal(h.calls.notices.filter(args=>args[0]==="Opened").length,1);
  }
  {
    const old=deferred(),h=harness();await h.controller.show();
    h.api.plan=body=>body.id==="one"?old.promise:Promise.resolve({plan:plan("two")});
    const stale=h.controller.review("one");h.elements.sessionSetDialog.close();await h.controller.show();
    await h.controller.review("two");old.resolve({plan:plan()});await stale;
    assert.equal(h.controller.snapshot().plan.setId,"two");assert.equal(h.calls.open.length,0);
    const copy=h.controller.snapshot();copy.plan.confirmation="tampered";
    assert.equal(h.controller.snapshot().plan.confirmation,"exact-confirmation","Inspection cannot mutate the exact reviewed contract");
  }
  {
    const h=harness();await h.controller.show();let contract="old";
    h.api.plan=async()=>({plan:plan("one",{mode:"launch",admission:{requiresAcknowledgement:true,contractId:contract}})});
    await h.controller.review("one");consent(h);contract="new";await h.controller.review("one");
    assert.equal(h.elements.sessionSetConsent.checked,false);await h.controller.open();assert.equal(h.calls.open.length,0);
    consent(h);let reject=true;
    h.api.open=async body=>{h.calls.open.push(body);if(reject)throw new Error("Capacity changed; review again");return {sessionSet:{phase:"completed",jobId:"new-job",setId:"one"}};};
    await h.controller.open();assert.match(h.elements.sessionSetStatus.textContent,/Capacity changed/);
    assert.equal(h.controller.snapshot().busy,false);assert.equal(h.controller.snapshot().plan.setId,"one");
    reject=false;await h.controller.open();assert.equal(h.calls.open.length,2);assert.equal(h.calls.open[1].memoryAcknowledgement,"new");
  }
  {
    const h=harness();await h.controller.show();await h.controller.review("one");
    const stale=deferred();h.api.status=()=>stale.promise;const reading=h.controller.refreshStatus();
    await h.controller.open();stale.resolve({sessionSet:{phase:"idle"}});await reading;
    assert.equal(h.controller.snapshot().status.phase,"attaching","An older status reply cannot erase a newly accepted operation");
    let reject=true;h.api.stop=async()=>{h.calls.stop++;if(reject)throw new Error("Stop rejected");return {sessionSet:{phase:"cancelled",jobId:"job",setId:"one"}};};
    await h.controller.stop();assert.equal(h.controller.isActive(),true);assert.match(h.elements.sessionSetStatus.textContent,/Stop rejected/);
    reject=false;await h.controller.stop();assert.equal(h.controller.isActive(),false);assert.equal(h.calls.stop,2);
  }
  {
    const h=harness();await h.controller.show();h.api.inventory=async()=>{throw new Error("Saved workspace storage was preserved; repair the file");};
    await h.controller.load();assert.equal(h.controller.snapshot().sets.length,1);assert.match(h.elements.sessionSetStatus.textContent,/preserved/);
    assert.equal(h.controller.snapshot().loading,false);
    h.api.inventory=async()=>({sets:[set()]});await h.controller.apply("one");
    assert.deepEqual(h.calls.apply[0].options,request.options);assert.equal(h.calls.apply[0].context,1);
    assert.equal(h.controller.snapshot().sets[0].baseRequest.context,8192);
    assert.equal(h.calls.open.length,0,"Apply primary changes only visible controls");
  }
  {
    const h=harness();await h.controller.show();h.controller.edit("one");
    h.elements.sessionSetName.value="  Replacement  ";await h.controller.save();
    assert.deepEqual(h.calls.save,[{name:"Replacement",id:"one"}]);assert.equal(h.controller.snapshot().editingId,"");
    assert.equal(h.calls.open.length,0);h.controller.edit("one");h.controller.resetEditor();
    assert.equal(h.calls.save.length,1,"Cancel update never writes");
    await h.controller.remove("one");assert.equal(h.calls.remove.length,0);await h.controller.remove("one");
    assert.deepEqual(h.calls.remove,[{id:"one"}]);assert.equal(h.controller.snapshot().sets.length,0);
  }
  {
    const h=harness();await h.controller.show();const cards=h.elements.sessionSetCards.htmlWrites;
    h.elements.sessionSetName.value="Typing preserved";h.elements.sessionSetName.focus();
    h.elements.sessionSetName.selectionStart=2;h.elements.sessionSetName.selectionEnd=5;
    for(let index=0;index<100;index++){h.controller.useStatus({sessionSet:{phase:"idle"}});h.controller.render();}
    assert.equal(h.elements.sessionSetCards.htmlWrites,cards,"Unchanged status preserves card nodes and focus");
    assert.equal(h.document.activeElement,h.elements.sessionSetName);assert.equal(h.elements.sessionSetName.selectionEnd,5);
    h.noWorkspace();h.elements.sessionSetName.value="Cannot save";await h.controller.save();assert.equal(h.calls.save.length,0);
  }
  console.log("Session Sets component: exact review/approval, stale replies, apply-only, private CRUD, retry/cancel, retained storage errors and stable focus passed.");
})().catch(error=>{console.error(error);process.exitCode=1;});
