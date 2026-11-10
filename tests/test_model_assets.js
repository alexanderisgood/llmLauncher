"use strict";
const assert=require("node:assert/strict"),Assets=require("../model_assets.js");
class Element {
  constructor(document){this.ownerDocument=document;this.value="";this.checked=false;this.disabled=false;this.open=false;
    this.textContent="";this.listeners={};this.style={};this.dataset={};this.markup="";this.htmlWrites=0;this.selectionStart=this.selectionEnd=0;
    this.classList={toggle:()=>{},add:()=>{},remove:()=>{}};this.parentElement={setAttribute:()=>{}};}
  addEventListener(name,fn){this.listeners[name]=fn;}querySelectorAll(){return [];}
  set innerHTML(value){this.markup=value;this.htmlWrites++;}get innerHTML(){return this.markup;}
  focus(){this.ownerDocument.activeElement=this;}showModal(){this.open=true;}close(){this.open=false;this.listeners.close?.();}
  emit(name){this.listeners[name]?.({target:this,currentTarget:this});}
}
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
const ids=["openModelLibrary","refreshModelLibrary","clearModelLibraryFilters","modelLibraryDialog","modelLibrarySearch",
  "modelLibraryEngineFilter","modelLibrarySurfaceFilter","modelLibraryStateFilter","modelLibraryBadge","modelLibrarySummary",
  "modelLibraryCards","modelLibraryStatus","openAcquisitionCenter","acquisitionDialog","acquisitionSearchForm","acquisitionSearch",
  "acquisitionSearchButton","acquisitionSearchResults","acquisitionRepoId","acquisitionRevision","acquisitionDestination",
  "acquisitionDestinationHelp","acquisitionInspectButton","acquisitionVariantField","acquisitionVariant","acquisitionPlan",
  "acquisitionConsent","acquisitionConsentPanel","acquisitionConsentCopy","acquisitionBadge","acquisitionStartButton",
  "acquisitionStartTitle","acquisitionStartLabel","acquisitionStopButton","acquisitionOpenLibrary","acquisitionPhase",
  "acquisitionPercent","acquisitionProgressBar","acquisitionStatus"];
const plan=(changes={})=>({id:"plan-one",confirmation:"exact-repo@commit/file-set",canStart:true,expiresAt:"2099-01-01T00:00:00Z",
  repo:{id:"generated/repository",pinnedRevision:"a".repeat(40),license:"MIT"},
  destination:{kind:"documents",label:"Generated models",path:"/generated/models",remainingBytes:100,existingBytes:0},
  selection:{id:"q6",label:"Original Q6",format:"gguf",fileCount:1,sizeBytes:100,files:[{path:"original-q6.gguf",size:100,sha256:"b".repeat(64)}]},
  variants:[{id:"q6",label:"Original Q6",sizeBytes:100},{id:"q4",label:"Other Q4",sizeBytes:70}],
  checks:[{state:"pass",label:"Pinned files",detail:"Exact sizes and hashes"}],expectedEngines:[],...changes});
const model={id:"one",name:"Inert <img src=x>",format:"gguf",ready:true,path:"/generated/original-q6.gguf",
  engines:[{id:"kolibri",label:"Kolibri SSD",runnable:true,status:"ready",surfaces:[{id:"omp",label:"oh-my-pi",supported:true}],modes:[]}]};
function fixture(options={}){
  const document={activeElement:null},elements=Object.fromEntries(ids.map(id=>[id,new Element(document)]));
  elements.acquisitionRepoId.value="generated/repository";elements.acquisitionRevision.value="main";elements.acquisitionDestination.value="documents";
  const calls={library:0,search:[],inspect:[],start:[],stop:0,status:0,apply:[],refresh:0,notices:[]};let other=false;
  const api={library:async()=>{calls.library++;return {modelLibrary:{models:[model]},roots:[],models:[model]};},
    status:async()=>{calls.status++;return {acquisition:{phase:"idle"},downloaderReady:true,roots:[{id:"documents",label:"Generated models",path:"/generated/models"}]};},
    search:async body=>{calls.search.push(body);return {search:{results:[{id:"generated/repository",inspectable:true,license:"MIT"}]}};},
    inspect:async body=>{calls.inspect.push(body);return {plan:plan()};},
    start:async body=>{calls.start.push(body);return {plan:plan()};},stop:async()=>{calls.stop++;},...options};
  const manager=Assets.createController({elements,api,selectedModelId:()=>"one",lookupModel:id=>id==="one"?model:null,
    applyRoute:(...args)=>calls.apply.push(args),acceptCatalog:()=>{},refreshModels:async()=>{calls.refresh++;},onActivityChange:()=>{},
    otherWork:()=>other,presentRoute:engine=>({tone:engine.runnable?"good":"blocked",available:engine.runnable,attention:false,label:"Ready"}),
    engineVisible:id=>id!=="freetoken",modelVisible:()=>true,featureEnabled:()=>false,isUzu:()=>false,
    contextLabel:()=>"8K",backendLabel:String,backendMark:()=>"K",formatNumber:String,formatBytes:value=>value+" bytes",
    notify:(...args)=>calls.notices.push(args)});
  return {manager,elements,calls,api,document,other:value=>{other=value;}};
}
const approve=h=>{h.elements.acquisitionConsent.checked=true;h.elements.acquisitionConsent.emit("change");};
(async()=>{
  {
    const h=fixture();await h.manager.showLibrary();assert.equal(h.calls.library,1);assert.equal(h.calls.start.length,0);
    assert.match(h.elements.modelLibraryStatus.textContent,/Nothing was started or changed/);
    assert.match(h.elements.modelLibraryCards.innerHTML,/&lt;img/,h.elements.modelLibraryStatus.textContent);assert.doesNotMatch(h.elements.modelLibraryCards.innerHTML,/<img/);
    assert.match(h.elements.modelLibraryEngineFilter.innerHTML,/value="kolibri"/);
    h.manager.useRoute("one","freetoken");assert.equal(h.calls.apply.length,0);
    h.manager.useRoute("one","kolibri");assert.deepEqual(h.calls.apply,[["one","kolibri"]]);assert.equal(h.calls.start.length,0);
  }
  {
    const h=fixture();await h.manager.showAcquisition();await h.manager.search();await h.manager.inspect();
    assert.deepEqual(h.calls.inspect,[{repoId:"generated/repository",revision:"main",destination:"documents",variantId:""}]);
    await h.manager.start();assert.equal(h.calls.start.length,0,"Inspection and unapproved plans never download");
    approve(h);const pending=deferred();h.api.start=body=>{h.calls.start.push(body);return pending.promise;};
    const first=h.manager.start();await h.manager.start();assert.equal(h.calls.start.length,1);
    assert.deepEqual(h.calls.start[0],{planId:"plan-one",confirmation:"exact-repo@commit/file-set",licenseReviewed:true});
    pending.resolve({plan:plan()});await first;assert.equal(h.manager.isActive(),true);
  }
  {
    const h=fixture();await h.manager.showAcquisition();await h.manager.inspect();approve(h);
    h.elements.acquisitionRepoId.value="different/repository";h.elements.acquisitionRepoId.emit("input");
    await h.manager.start();assert.equal(h.calls.start.length,0);assert.equal(h.elements.acquisitionConsent.checked,false);
    h.elements.acquisitionRepoId.value="generated/repository";await h.manager.inspect();approve(h);
    h.manager.renderPlan(plan({repo:{...plan().repo,license:"Changed license"}}),true);
    assert.equal(h.elements.acquisitionConsent.checked,false,"Even the same plan ID cannot retain approval for changed facts");
  }
  {
    const stale=deferred(),h=fixture();await h.manager.showAcquisition();h.api.inspect=()=>stale.promise;
    const reading=h.manager.inspect();h.elements.acquisitionDialog.close();
    stale.resolve({plan:plan()});await reading;assert.equal(h.manager.snapshot().plan,null,"A closed inspection cannot restore an old plan");
    h.api.inspect=async()=>({plan:plan()});await h.manager.inspect();approve(h);h.other(true);h.manager.updateControls();
    await h.manager.start();assert.equal(h.calls.start.length,0,"An active model or other operation blocks acquisition start");
  }
  {
    const h=fixture();await h.manager.showAcquisition();await h.manager.inspect();approve(h);let fail=true;
    h.api.start=async body=>{h.calls.start.push(body);if(fail)throw new Error("Generated start rejection");return {plan:plan()};};
    await h.manager.start();assert.match(h.elements.acquisitionStatus.textContent,/rejection/);assert.equal(h.manager.snapshot().starting,false);
    assert.equal(h.elements.acquisitionConsent.checked,true,"A rejected unchanged plan remains explicitly retryable");
    fail=false;await h.manager.start();assert.equal(h.calls.start.length,2);
    h.api.stop=async()=>{h.calls.stop++;throw new Error("Generated Stop rejection");};await h.manager.stop();
    assert.equal(h.manager.isActive(),true);assert.match(h.elements.acquisitionStatus.textContent,/Stop rejection/);
    h.api.stop=async()=>{h.calls.stop++;};h.api.status=async()=>({acquisition:{phase:"cancelled",message:"Files preserved"}});
    await h.manager.stop();assert.equal(h.manager.isActive(),false);assert.equal(h.calls.stop,2);
  }
  {
    const h=fixture();await h.manager.showLibrary();h.api.library=async()=>{throw new Error("Generated catalog unavailable");};
    await h.manager.loadLibrary();assert.equal(h.manager.snapshot().library.models.length,1);assert.match(h.elements.modelLibraryStatus.textContent,/unavailable/);
    await h.manager.showAcquisition();await h.manager.search();h.api.search=async()=>{throw new Error("Generated network failure");};
    await h.manager.search();assert.equal(h.manager.snapshot().searchResults.length,1);assert.match(h.elements.acquisitionStatus.textContent,/failure/);
  }
  {
    const h=fixture();await h.manager.showAcquisition();await h.manager.inspect();
    const planWrites=h.elements.acquisitionPlan.htmlWrites,rootWrites=h.elements.acquisitionDestination.htmlWrites;
    h.elements.acquisitionRevision.focus();h.elements.acquisitionRevision.selectionStart=1;h.elements.acquisitionRevision.selectionEnd=3;
    for(let index=0;index<30;index++)h.manager.useStatus({acquisition:{phase:"idle",plan:plan()},roots:[{id:"documents",label:"Generated models",path:"/generated/models"}]});
    assert.equal(h.elements.acquisitionPlan.htmlWrites,planWrites);assert.equal(h.elements.acquisitionDestination.htmlWrites,rootWrites);
    assert.equal(h.document.activeElement,h.elements.acquisitionRevision);assert.equal(h.elements.acquisitionRevision.selectionEnd,3);
  }
  {
    const h=fixture();const result={repoId:"generated/repository",pinnedRevision:"a".repeat(40),modelName:"Original Q6",path:"/generated/q6"};
    h.manager.useStatus({acquisition:{phase:"completed",plan:plan(),result}});
    h.manager.useStatus({acquisition:{phase:"completed",plan:plan(),result}});assert.equal(h.calls.refresh,1);
    h.manager.useStatus({acquisition:{phase:"completed",plan:plan({id:"second-plan"}),result:{...result,path:"/generated/q4",modelName:"Other Q4"}}});
    assert.equal(h.calls.refresh,2,"A second variant at the same commit must refresh the local catalog too");
  }
  console.log("Model assets component: read-only catalog/inspection, exact pinned approval, input/plan invalidation, duplicate guards, warm restrictions, retry/cache preservation and stable focus passed.");
})().catch(error=>{console.error(error);process.exitCode=1;});
