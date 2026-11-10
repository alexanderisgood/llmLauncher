"use strict";
const assert=require("node:assert/strict");
const connect=require("./helpers/saved_launches_harness.js");
class Element {
  constructor(document){this.ownerDocument=document;this.listeners={};this.children={};this.value="";this.open=false;this.disabled=false;
    this.attributes={};this.textContent="";this.htmlWrites=0;this.selectionStart=this.selectionEnd=0;
    this.classList={add:()=>{},remove:()=>{},toggle:()=>{}};}
  set innerHTML(value){this.markup=value;this.htmlWrites++;}get innerHTML(){return this.markup||"";}
  addEventListener(name,fn){this.listeners[name]=fn;}getAttribute(name){return this.attributes[name]??null;}
  setAttribute(name,value){this.attributes[name]=String(value);}removeAttribute(name){delete this.attributes[name];}
  querySelector(name){return this.children[name] ||= new Element(this.ownerDocument);}querySelectorAll(){return [];}
  contains(){return false;}focus(){this.ownerDocument.activeElement=this;}scrollIntoView(){}
  showModal(){this.open=true;}close(){this.open=false;}
}
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
const exact={backend:"kolibri",modelId:"original-q6",client:"omp",project:"/generated/project",context:8192,output:1024,
  reasoning:"off",agentHost:"console",options:{memoryMode:"fixed",memoryGB:12,prefillSize:64,promptCacheGB:1,kv:"off"},
  generation:{sampling:"custom",temperature:0,topP:1,topK:0,seed:42}};
const profile=(id="one")=>({id,name:"Saved <img src=x onerror=alert(1)> "+id,ready:true,enginePolicy:"fixed",
  enginePreference:"throughput",modelName:"Original Q6",request:structuredClone(exact)});
function fixture(options={}){
  const document={activeElement:null},elements=new Map(),$=id=>{if(!elements.has(id))elements.set(id,new Element(document));return elements.get(id);};
  $("profilePolicySelect").value="fixed";$("profileGoalSelect").value="throughput";$("profileDialog").open=true;
  const calls={reads:0,save:[],remove:[],apply:[],launch:0,evidence:[],notices:[],session:[],chat:[]};
  const context={$,state:{runPhase:"idle"},copiedEvidenceBinding:value=>value?structuredClone(value):null,
    activeEvidenceBindingFor:()=>null,themeStorage:()=>undefined,refreshLaunchability:()=>{},setQuickStartEditor:()=>{},
    gather:()=>structuredClone(exact),applyProfileRequest:request=>calls.apply.push(request),
    launch:async()=>{calls.launch++;return true;},applyOptimal:async(...args)=>{calls.evidence.push(args);return true;},
    freeTokenExperimentalConsentRequired:()=>false,showNotice:(...args)=>calls.notices.push(args),requestAnimationFrame:fn=>fn(),
    api:async(endpoint,request={})=>{
      if(endpoint==="/api/profiles"){calls.reads++;return {profiles:[profile()]};}
      const body=JSON.parse(request.body);
      if(endpoint==="/api/profiles/save"){calls.save.push(body);return {profiles:[{...profile(body.id||"new"),name:body.name,request:body.request}]};}
      if(endpoint==="/api/profiles/delete"){calls.remove.push(body);return {profiles:[]};}
      throw new Error(endpoint);
    }};
  const manager=connect(context,{reviewSessionSet:id=>calls.session.push(id),openChatShortcut:id=>calls.chat.push(id),...options});
  manager.useInventory({profiles:[profile()]});
  return {context,manager,$,calls,document};
}
(async()=>{
  {
    const h=fixture();await h.manager.loadShortcuts();
    assert.equal(h.calls.launch,0);assert.equal(h.calls.save.length,0);
    assert.match(h.$("quickStartCards").innerHTML,/&lt;img/);assert.doesNotMatch(h.$("quickStartCards").innerHTML,/<img/);
    assert.equal(h.$("customLaunchEditor").attributes.inert,undefined,"Saved routes never hide or lock the regular editor");
  }
  {
    const h=fixture(),pending=deferred();h.context.api=async()=>{h.calls.reads++;return pending.promise;};
    const first=h.manager.loadShortcuts(true),second=h.manager.loadShortcuts(true);
    assert.equal(first,second,"Repeated callers await the same active shortcut refresh");assert.equal(h.calls.reads,1);
    pending.resolve({profiles:[profile()]});await second;assert.equal(h.manager.snapshot().shortcutLoading,false);
  }
  {
    const h=fixture();h.$("profileName").value="Exact saved route";
    const pending=deferred();h.context.api=async(endpoint,request)=>{
      assert.equal(endpoint,"/api/profiles/save");h.calls.save.push(JSON.parse(request.body));return pending.promise;};
    const saving=h.manager.save();await h.manager.save();assert.equal(h.calls.save.length,1,"Double-submit cannot create another saved profile");
    assert.deepEqual(h.calls.save[0],{name:"Exact saved route",enginePolicy:"fixed",enginePreference:"throughput",request:exact});
    pending.resolve({profiles:[profile()]});await saving;assert.equal(h.manager.isBusy(),false);
  }
  {
    const h=fixture();await h.manager.remove("one");assert.equal(h.calls.remove.length,0);
    const pending=deferred();h.context.api=async(endpoint,request)=>{h.calls.remove.push(JSON.parse(request.body));return pending.promise;};
    const deleting=h.manager.remove("one");await h.manager.remove("one");assert.deepEqual(h.calls.remove,[{id:"one"}]);
    pending.resolve({profiles:[]});await deleting;assert.deepEqual(h.manager.snapshot().profiles,[]);
  }
  {
    const h=fixture();await h.manager.loadShortcuts();
    h.context.api=async()=>{throw new Error("Saved launches could not be read; original file kept.");};
    await h.manager.load();await h.manager.loadShortcuts(true);
    assert.equal(h.manager.snapshot().profiles.length,1);assert.match(h.$("profileManagerStatus").textContent,/original file kept/);
    assert.match(h.$("quickStartStatus").textContent,/original file kept/);assert.equal(h.$("quickStartStatus").hidden,false);
    assert.equal(h.manager.snapshot().shortcutLoading,false);
  }
  {
    const h=fixture();const stale=deferred();let first=true;
    h.context.api=async(endpoint,request)=>{
      if(endpoint==="/api/profiles")return first?(first=false,stale.promise):{profiles:[profile()]};
      h.calls.save.push(JSON.parse(request.body));return {profiles:[profile("new")]};};
    const loading=h.manager.loadShortcuts(true);h.$("profileName").value="New record";await h.manager.save();
    stale.resolve({profiles:[profile("old")]});await loading;
    assert.equal(h.manager.snapshot().profiles[0].id,"new","An older shortcut inventory cannot roll back an accepted write");
  }
  {
    const h=fixture();const pending=deferred();h.context.launch=async()=>{h.calls.launch++;return pending.promise;};
    const launching=h.manager.apply("one",true);await new Promise(resolve=>setTimeout(resolve,0));
    await h.manager.apply("one",true);assert.equal(h.calls.launch,1,"A pending accepted action cannot launch twice");
    pending.resolve(false);await launching;assert.match(h.$("profileManagerStatus").textContent,/final launch validation/);
    assert.equal(h.manager.isBusy(),false);assert.equal(h.$("profileDialog").open,true);
  }
  {
    const h=fixture({needsExperimentalConsent:()=>true});await h.manager.apply("one",true);
    assert.equal(h.calls.launch,0,"Unsaved experimental approval returns to explicit review");
    assert.ok(h.calls.notices.some(args=>String(args[0]).includes("approval was not saved")));
  }
  {
    const h=fixture();const binding={scope:"route",preference:"throughput",recordId:"qualified-record"};
    h.context.api=async()=>({profiles:[{...profile(),enginePolicy:"measured",evidenceBinding:binding}]});
    h.context.applyOptimal=async(...args)=>{h.calls.evidence.push(args);return false;};
    await h.manager.apply("one",true);assert.equal(h.calls.launch,0);
    assert.deepEqual(h.calls.evidence[0],["current","throughput",false,binding]);
    assert.match(h.$("profileManagerStatus").textContent,/measured engine decision/);
  }
  {
    const h=fixture();await h.manager.loadShortcuts();h.manager.toggleShortcuts();h.manager.render();
    const cards=h.$("profileCards").htmlWrites,shortcuts=h.$("quickStartCards").htmlWrites;
    h.$("profileName").value="Keep typing";h.$("profileName").focus();h.$("profileName").selectionStart=2;h.$("profileName").selectionEnd=7;
    for(let index=0;index<100;index++)h.manager.render();
    assert.equal(h.$("profileCards").htmlWrites,cards);assert.equal(h.$("quickStartCards").htmlWrites,shortcuts);
    assert.equal(h.document.activeElement,h.$("profileName"));assert.equal(h.$("profileName").selectionEnd,7);
  }
  console.log("Saved launches component: exact writes, duplicate guards, ID-only references, evidence/approval review, cached errors, stale inventories and stable shortcut/card focus passed.");
})().catch(error=>{console.error(error);process.exitCode=1;});
