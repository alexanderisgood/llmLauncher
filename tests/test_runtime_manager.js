"use strict";
const assert=require("node:assert/strict"),Runtime=require("../runtime_manager.js");
class Element {
  constructor(document){this.ownerDocument=document;this.value="";this.checked=false;this.disabled=false;this.open=false;
    this.dataset={};this.textContent="";this.style={};this.listeners={};this.attributes=[];this.htmlWrites=0;this.markup="";
    this.classList={toggle:()=>{},add:()=>{},remove:()=>{}};}
  querySelector(){return null;}querySelectorAll(){return [];}contains(item){return item===this;}
  set innerHTML(value){this.markup=value;this.htmlWrites++;}get innerHTML(){return this.markup;}
  addEventListener(name,fn){this.listeners[name]=fn;}emit(name){this.listeners[name]?.({target:this});}
  closest(){return {setAttribute:()=>{}};}focus(){this.ownerDocument.activeElement=this;}
  showModal(){this.open=true;}close(){this.open=false;this.emit("close");}
}
const ids=["openRuntimeManager","refreshRuntimeManager","runtimeAdvancedTools","runtimeAgents","runtimeCards","runtimeDialog",
  "runtimeManagerStatus","runtimeManagerSummary","runtimePromotionConsent","runtimePromotionConsentCopy","runtimePromotionConsentPanel",
  "runtimePromotionModel","runtimePromotionPercent","runtimePromotionPhase","runtimePromotionPlan","runtimePromotionProgressBar",
  "runtimePromotionStartButton","runtimePromotionStartLabel","runtimePromotionStatus","runtimePromotionStopButton","runtimePromotionSuite",
  "runtimeSummaryBadge","runtimeUpdateCatalogBadge","runtimeUpdateConsent","runtimeUpdateConsentCopy","runtimeUpdateConsentPanel",
  "runtimeUpdatePercent","runtimeUpdatePhase","runtimeUpdatePlan","runtimeUpdateProgressBar","runtimeUpdateStartButton",
  "runtimeUpdateStartLabel","runtimeUpdateStartTitle","runtimeUpdateStatus","runtimeUpdateStopButton","runtimeUpdateTracks"];
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const release={channel:"stable",label:"Stable <img src=x>",version:"1.0.0",action:"install",canPlan:true,releasedAt:"2026-01-01",
  tag:"v1.0.0",commit:"a".repeat(40),sha256:"b".repeat(64),fileName:"generated.whl",summary:"Generated evidence"};
const updatePlan=()=>({id:"update-plan",confirmation:"install:exact:hash",action:"install",release,
  destination:{exists:false,path:"/generated/runtimes/1.0.0"},installer:{dependencyPolicy:"Exact pinned dependencies"},
  rollback:{detail:"Previous copy kept"},steps:["Verify generated wheel"],checks:[{state:"pass",label:"Checksum",detail:"Exact hash"}],canStart:true});
const candidate={id:"candidate-exact",version:"1.0.0",channelLabel:"Verified candidate",path:"/generated/candidate",managedVerification:{verified:true}};
const selected={id:"selected-exact",version:"0.9.0",channelLabel:"Selected",path:"/generated/selected",selected:true};
const inventory=()=>({checkedAt:"2026-10-06T12:00:00Z",releaseCatalog:{auditedAt:"2026-10-01"},summary:{message:"Generated local checks"},agents:[],
  runtimes:[{id:"omlx",label:"oMLX <img src=x>",level:"ready",headline:"Installed",selected,candidates:[selected,candidate],checks:[],update:{},app:{available:true}},
    {id:"freetoken",label:"Hidden route",candidates:[candidate],app:{available:true}}]});
const comparison=()=>({id:"comparison-plan",confirmation:"compare:exact-revisions",canStart:true,selected,candidate,model:{id:"generated",name:"Original Q6"},
  workload:{label:"Generated agent workload",generatedRequests:4},executionOrder:["selected","candidate","candidate","selected"],checks:[],steps:[],rollback:{detail:"Previous kept"}});
const result=()=>({id:"measured-result",confirmation:"promote:exact-evidence",canPromote:true,selectionChanged:false,candidate,medianSpeedup:1.06,worstCaseSpeedup:1.04,
  memoryRegressionBytes:0,measurements:{candidate:{thermalWorst:"Nominal"}},checks:[],recommendation:"Generated measurements passed"});
function fixture(overrides={}){
  const document={activeElement:null},elements=Object.fromEntries(ids.map(id=>[id,new Element(document)]));elements.runtimePromotionSuite.value="agentic";
  const calls={inventory:0,refresh:0,updatePlan:[],updateStart:[],updateStop:0,promotionPlan:[],promotionStart:[],promotionStop:0,promotionApply:[],open:[],select:[]};
  let route={backend:"omlx",client:"omp",modelId:"generated",context:8192,output:1024,reasoning:"off",agentHost:"console",project:"/generated/project",
    options:{acceleration:"dflash",kv:"q6",anePrefill:"on",burst:"fast",seed:42,temperature:0}},active=false;
  const api={inventory:async()=>{calls.inventory++;return {runtimeManager:inventory()};},
    updateStatus:async()=>({catalog:{releases:[release,{...release,channel:"blocked",canPlan:false}]},runtimeUpdate:{phase:"idle"}}),
    promotionStatus:async()=>({runtimePromotion:{phase:"idle"}}),updatePlan:async body=>{calls.updatePlan.push(body);return {plan:updatePlan()};},
    updateStart:async body=>{calls.updateStart.push(body);return {plan:updatePlan()};},updateStop:async()=>{calls.updateStop++;},
    promotionPlan:async body=>{calls.promotionPlan.push(body);return {plan:comparison()};},promotionStart:async body=>{calls.promotionStart.push(body);return {plan:comparison()};},
    promotionStop:async()=>{calls.promotionStop++;},promotionApply:async body=>{calls.promotionApply.push(body);return {runtimeManager:inventory(),result:{...result(),selectionChanged:true}};},
    open:async body=>{calls.open.push(body);return {detail:"Generated app open"};},select:async body=>{calls.select.push(body);return {runtimeManager:inventory()};},...overrides};
  const manager=Runtime.createController({elements,api,engineVisible:id=>id!=="freetoken",selectedRequest:()=>route,selectedModelName:()=>"Original Q6",
    selectedClient:()=>"omp",informationLevel:()=>"focused",currentOperation:()=>active,refreshSelection:async()=>{calls.refresh++;},
    backendLabel:String,backendMark:()=>"O",formatBytes:value=>value+" bytes"});
  return {manager,elements,calls,api,document,route:()=>route,setRoute:value=>{route={...route,...value};},active:value=>{active=value;}};
}
const approve=h=>{h.elements.runtimeUpdateConsent.checked=true;h.elements.runtimeUpdateConsent.emit("change");};
(async()=>{
  {
    const h=fixture();await h.manager.show();assert.equal(h.calls.inventory,1);assert.equal(h.elements.runtimePromotionSuite.value,"agentic");
    assert.match(h.elements.runtimeManagerStatus.textContent,/no network check/);assert.match(h.elements.runtimeCards.innerHTML,/&lt;img/);
    assert.doesNotMatch(h.elements.runtimeCards.innerHTML,/<img|Hidden route/);assert.equal(h.calls.open.length+h.calls.select.length,0);
    await h.manager.inspectUpdate("blocked");assert.equal(h.calls.updatePlan.length,0,"Blocked tracks never regain review capability");
    h.api.inventory=async()=>{throw new Error("Generated storage error; preserved inventory");};await h.manager.load();
    assert.match(h.elements.runtimeManagerStatus.textContent,/preserved inventory/);assert.match(h.elements.runtimeCards.innerHTML,/candidate-exact/);
  }
  {
    const h=fixture();await h.manager.show();await h.manager.inspectUpdate("stable");await h.manager.startUpdate();assert.equal(h.calls.updateStart.length,0);
    approve(h);h.manager.renderUpdatePlan({...updatePlan(),release:{...release,sha256:"c".repeat(64)}});
    assert.equal(h.elements.runtimeUpdateConsent.checked,false,"Changed exact facts invalidate approval even with the same plan ID");
    approve(h);const pending=deferred();h.api.updateStart=body=>{h.calls.updateStart.push(body);return pending.promise;};
    const starting=h.manager.startUpdate();await h.manager.startUpdate();h.elements.runtimeDialog.close();await h.manager.startUpdate();
    assert.equal(h.calls.updateStart.length,1,"Start cannot duplicate while pending, including close/reopen");
    assert.deepEqual(h.calls.updateStart[0],{planId:"update-plan",confirmation:"install:exact:hash",reviewed:true});
    pending.resolve({plan:updatePlan()});await starting;assert.equal(h.manager.updateIsActive(),true);assert.equal(h.elements.runtimeUpdateConsent.checked,false);
  }
  {
    const h=fixture();await h.manager.show();const pending=deferred();h.api.updatePlan=()=>pending.promise;
    const inspecting=h.manager.inspectUpdate("stable");h.elements.runtimeDialog.close();pending.resolve({plan:updatePlan()});await inspecting;
    assert.equal(h.manager.snapshot().runtimeUpdatePlan,null,"Closed inspection cannot restore a stale plan");
    h.api.updatePlan=async()=>({plan:updatePlan()});await h.manager.inspectUpdate("stable");approve(h);
    h.api.updateStart=async()=>{throw new Error("Generated rejection; retry");};await h.manager.startUpdate();
    assert.equal(h.elements.runtimeUpdateStartButton.disabled,false);assert.match(h.elements.runtimeUpdateStatus.textContent,/retry/);
    h.active(true);h.manager.updateControls();await h.manager.startUpdate();assert.equal(h.elements.runtimeUpdateStartButton.disabled,true);
  }
  {
    const h=fixture();await h.manager.show();await h.manager.inspectUpdate("stable");approve(h);
    const old=deferred();h.api.updateStatus=()=>old.promise;const reading=h.manager.refreshUpdate();await h.manager.startUpdate();
    old.resolve({runtimeUpdate:{phase:"idle",plan:updatePlan()}});await reading;assert.equal(h.manager.updateIsActive(),true,"Pre-start reads cannot overwrite accepted jobs");
    h.api.updateStatus=async()=>({runtimeUpdate:{phase:"cancelled",message:"Generated cancelled"}});const stop=deferred();h.api.updateStop=()=>{h.calls.updateStop++;return stop.promise;};
    const stopping=h.manager.stopUpdate();await h.manager.stopUpdate();assert.equal(h.calls.updateStop,1);stop.resolve({});await stopping;assert.equal(h.manager.updateIsActive(),false);
    h.manager.renderUpdate({runtimeUpdate:{phase:"completed",plan:updatePlan(),result:{version:release.version,action:"install",path:"/generated/runtime",selectionChanged:false}}});
    await settle();assert.equal(h.calls.refresh,1);assert.equal(h.calls.select.length+h.calls.promotionApply.length,0,"Completion refresh never selects a runtime");
  }
  {
    const h=fixture();await h.manager.show();const original=JSON.stringify(h.route());await h.manager.inspectPromotion(candidate.id);
    const request=h.calls.promotionPlan[0];assert.equal(request.modelId,"generated");assert.equal(request.output,1024);assert.equal(request.context,8192);
    assert.equal(request.agentHost,"console");assert.equal(request.reasoning,"off");assert.equal(request.candidateId,candidate.id);assert.equal(request.suite,"agentic");
    assert.deepEqual(request.options,{...h.route().options,acceleration:"off",kv:"off",anePrefill:"off",burst:"balanced"});assert.equal(JSON.stringify(h.route()),original);
    const pending=deferred();h.api.promotionStart=body=>{h.calls.promotionStart.push(body);return pending.promise;};const starting=h.manager.startPromotion();await h.manager.startPromotion();
    assert.equal(h.calls.promotionStart.length,1);assert.deepEqual(h.calls.promotionStart[0],{planId:"comparison-plan",confirmation:"compare:exact-revisions",reviewed:true});
    pending.resolve({plan:comparison()});await starting;assert.equal(h.manager.promotionIsActive(),true);assert.equal(h.calls.promotionApply.length,0);
  }
  {
    const h=fixture();await h.manager.show();const stale=deferred();h.api.promotionPlan=()=>stale.promise;const inspection=h.manager.inspectPromotion(candidate.id);
    h.setRoute({output:512});stale.resolve({plan:comparison()});await inspection;assert.equal(h.manager.snapshot().runtimePromotionPlan,null);
    h.api.promotionPlan=async()=>({plan:comparison()});await h.manager.inspectPromotion(candidate.id);h.setRoute({context:16384});await h.manager.startPromotion();assert.equal(h.calls.promotionStart.length,0);
    h.manager.renderPromotion({runtimePromotion:{phase:"completed",result:result()}});assert.equal(h.calls.promotionApply.length,0,"Measurement never promotes automatically");
    await h.manager.applyPromotion("wrong-result");assert.equal(h.calls.promotionApply.length,0);
    const pending=deferred();h.api.promotionApply=body=>{h.calls.promotionApply.push(body);return pending.promise;};const applying=h.manager.applyPromotion(result().id);await h.manager.applyPromotion(result().id);
    assert.equal(h.calls.promotionApply.length,1);assert.deepEqual(h.calls.promotionApply[0],{resultId:"measured-result",confirmation:"promote:exact-evidence"});
    pending.resolve({runtimeManager:inventory(),result:{...result(),selectionChanged:true}});await applying;assert.equal(h.calls.refresh,1);
  }
  {
    const h=fixture();await h.manager.show();await h.manager.select("freetoken",candidate.id);await h.manager.openApp("freetoken");await h.manager.select("omlx","unknown");
    assert.equal(h.calls.select.length+h.calls.open.length,0,"Hidden routes and unknown candidates cannot mutate selection");
    const pending=deferred();h.api.select=body=>{h.calls.select.push(body);return pending.promise;};const selecting=h.manager.select("omlx",candidate.id);await h.manager.select("omlx",candidate.id);
    assert.equal(h.calls.select.length,1);assert.deepEqual(h.calls.select[0],{runtime:"omlx",candidateId:"candidate-exact",confirmation:"select:candidate-exact"});
    pending.reject(new Error("Generated selection rejection"));await selecting;assert.equal(h.manager.snapshot().runtimeLoading,false);
    h.api.select=async body=>{h.calls.select.push(body);return {runtimeManager:inventory()};};await h.manager.select("omlx",candidate.id);assert.equal(h.calls.refresh,1);
    h.api.open=async()=>{throw new Error("Generated app failure");};await h.manager.openApp("omlx");assert.equal(h.manager.snapshot().runtimeOpening,false);
    h.api.open=async body=>{h.calls.open.push(body);return {detail:"Generated app opened"};};await h.manager.openApp("omlx");assert.deepEqual(h.calls.open,[{runtime:"omlx"}]);
  }
  {
    const h=fixture();await h.manager.show();const writes=h.elements.runtimeCards.htmlWrites;h.elements.runtimePromotionSuite.focus();
    for(let i=0;i<50;i++)h.manager.renderInventory(inventory());assert.equal(h.elements.runtimeCards.htmlWrites,writes,"Unchanged inventory retains focused controls");
    assert.equal(h.document.activeElement,h.elements.runtimePromotionSuite);
    const old=deferred();h.api.inventory=()=>old.promise;const loading=h.manager.load();h.elements.runtimeDialog.close();
    old.resolve({runtimeManager:{...inventory(),summary:{message:"Stale closed inventory"}}});await loading;
    assert.notEqual(h.elements.runtimeManagerSummary.textContent,"Stale closed inventory");
  }
  {
    const h=fixture();await h.manager.show();await h.manager.inspectPromotion(candidate.id);await h.manager.startPromotion();
    h.api.promotionStatus=async()=>({runtimePromotion:{phase:"cancelled",message:"Comparison stopped"}});
    await h.manager.stopPromotion();assert.equal(h.calls.promotionStop,1);assert.equal(h.elements.runtimePromotionPhase.textContent,"Stopped");
    const idle=fixture();await idle.manager.show();idle.manager.renderPromotion({runtimePromotion:{phase:"idle"},latestResult:result()});
    assert.match(idle.elements.runtimePromotionPlan.innerHTML,/measured-result/,"Latest measured evidence must render even without an active plan");
  }
  {
    const h=fixture();await h.manager.show();await h.manager.inspectUpdate("stable");approve(h);
    const accepted=deferred();h.api.updateStart=()=>accepted.promise;const starting=h.manager.startUpdate();
    const during=deferred();h.api.updateStatus=()=>during.promise;const reading=h.manager.refreshUpdate();
    accepted.resolve({plan:updatePlan()});await starting;during.resolve({runtimeUpdate:{phase:"idle"}});await reading;
    assert.equal(h.manager.updateIsActive(),true,"Reads begun during admission cannot overwrite an accepted job");
    const p=fixture();await p.manager.show();await p.manager.inspectPromotion(candidate.id);p.manager.renderPromotion({runtimePromotion:{phase:"completed",result:result()}});
    const acceptedPromotion=deferred();p.api.promotionApply=()=>acceptedPromotion.promise;const applying=p.manager.applyPromotion(result().id);
    const oldEvidence=deferred();p.api.promotionStatus=()=>oldEvidence.promise;const evidenceRead=p.manager.refreshPromotion();
    acceptedPromotion.resolve({runtimeManager:inventory(),result:{...result(),selectionChanged:true}});await applying;
    oldEvidence.resolve({runtimePromotion:{phase:"completed",result:result()}});await evidenceRead;
    assert.equal(p.manager.snapshot().runtimePromotionStatus.result.selectionChanged,true,"Late pre-commit evidence cannot undo successful promotion");
  }
  console.log("Runtime Manager complete feature behavior passed.");
})().catch(error=>{console.error(error);process.exitCode=1;});
