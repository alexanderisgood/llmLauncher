'use strict';
const Workspace=require('../../benchmark_workspace.js');
const fixture=require('../fixtures/benchmark_workspace_legacy.json');
const decision=require('../../calibration_decision.js');
function element(id){
 const classes=new Set(),listeners=new Map();let html='',writes=0;
 const node={id,dataset:{},style:{},value:'',textContent:'',className:'',title:'',disabled:false,checked:false,open:false,options:[],attributes:{},
  classList:{add:(...items)=>items.forEach(x=>classes.add(x)),remove:(...items)=>items.forEach(x=>classes.delete(x)),contains:x=>classes.has(x),
   toggle:(x,on)=>{const yes=on??!classes.has(x);if(yes)classes.add(x);else classes.delete(x);return yes}},
  get innerHTML(){return html},set innerHTML(value){html=String(value);writes++},get markupWrites(){return writes},
  setAttribute(name,value){node.attributes[name]=String(value)},removeAttribute(name){delete node.attributes[name]},
  parentElement:{setAttribute(name,value){node.attributes['parent:'+name]=String(value)}},
  closest:()=>({classList:node.classList}),querySelector:()=>({textContent:''}),querySelectorAll:()=>[],scrollIntoView(){node.scrolled=true},
  showModal(){node.open=true},close(){node.open=false},
  addEventListener:(event,fn)=>{const group=listeners.get(event)||[];group.push(fn);listeners.set(event,group)},
  listenerCount:event=>(listeners.get(event)||[]).length,
  dispatch:(event,data={})=>(listeners.get(event)||[]).map(fn=>fn({target:node,currentTarget:node,...data})),
 };return node;
}
function harness(overrides={}){
 const nodes=Object.fromEntries(Workspace.nodeIds.map(id=>[id,element(id)]));
 const visible={backend:'omlx',client:'chat',optimalLabel:'Generated winner'},activity={runPhase:'idle',setupPhase:'idle'};
 const model={id:'generated-model',name:'Generated model',ready:true,backends:{omlx:{runnable:true,mtp:true,dflash:true,agentReasoning:['auto','off'],kv:true},lmstudio:{runnable:true,mtp:true,agentReasoning:['auto','off']}}};
 const request={modelId:model.id,backend:'omlx',client:'chat',context:8192,output:1024,reasoning:'auto',options:{kv:'off'},chat:{sampling:'model'}};
 const binding={scope:'engine',suite:'agentic',preference:'throughput',shootoutId:'fixture-comparison',recordIds:{omlx:'omlx-fixture',lmstudio:'lmstudio-fixture'}};
 const plan={action:'measure',ready:true,model:{id:model.id,name:model.name},clientLabel:'Chat',request:structuredClone(request),contractId:'generated-contract',
  suite:{id:'agentic',label:'Agentic'},preference:'throughput',preferenceLabel:'Highest generation TPS',reasoningContract:{normalized:false},
  calibrationCooling:'default',calibrationCoolingLabel:'System controlled',eligibleEngineCount:2,modelReloadCount:2,measuredRequestCount:8,
  engines:[{backend:'omlx',label:'oMLX',eligible:true,modes:[{label:'AR'},{label:'MTP'}],modeDetail:'Generated exact route'}],evidence:{},suggestedProfileName:'Generated profile'};
 const history={contract:{suite:'agentic'},freshness:'current',freshnessMessage:'Generated matching records',shootoutCount:0,currentRouteRuns:[],runs:[],series:[],otherEvidence:{count:0},canRerunShootout:true};
 const requests=[],notices=[],applies=[],timers=[],polls=[];let status={phase:'idle'},receiptValue=null,activeBinding=binding;
 const groups=Object.fromEntries(Object.keys(fixture.callbacks).map(group=>[group,Object.fromEntries(fixture.callbacks[group].split(' ').map(name=>[name,()=>{}]))]));
 Object.assign(groups.formatting,{esc:value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;'),
  formatBytes:String,formatNumber:value=>Number(value).toLocaleString('en-US'),finiteMetric:value=>typeof value==='number'&&Number.isFinite(value)?value:null,
  backendName:value=>({omlx:'oMLX',lmstudio:'LM Studio'})[value]||value,clientName:String,exactContextTier:value=>`${value} tokens`});
 Object.assign(groups.capabilities,{selectedModel:()=>model,visibleEngineAdapters:()=>Object.keys(model.backends).map(id=>({id,binaryKey:id})),
  backendBinaryKey:value=>value,runtimeInstalled:()=>true,resolvedClientSupport:()=>({supported:true}),uiEngineVisible:()=>true,
  freeTokenRoute:()=>false,mtplxLongContextCapabilityExact:()=>false,llamaCppPleCapabilityQualified:()=>false,llamaCppPleQualified:()=>false,
  selectedRouteQualificationBackend:()=>'',controllerRouteQualificationBackend:()=>'',isUzuQualificationSuite:()=>false});
 Object.assign(groups.settings,{snapshot:()=>({...visible}),gather:()=>structuredClone({...request,backend:visible.backend,client:visible.client}),runtimeKvValue:()=>request.options.kv,
  setRuntimeKvValue:(_backend,value)=>{request.options.kv=value;return true},selectBackend:value=>{visible.backend=value},resetSessionAcknowledgement(){}});
 Object.assign(groups.operations,{snapshot:()=>({...activity}),acquisitionIsActive:()=>false,routeCheckIsActive:()=>false,aneWorkIsActive:()=>false,profileBusy:()=>false,
  currentSessionAdmission:()=>({known:true,actionReady:true,decision:'ready'}),sessionAdmissionDecision:value=>value||{actionReady:false},
  sessionAdmissionBlockerCopy:()=> 'Generated capacity blocked',requireFreshSessionAdmission:async()=>true});
 Object.assign(groups.effects,{showNotice:(...args)=>notices.push(args),pollStatus:async()=>{},loadModels:()=>Promise.resolve(),activeDetail:()=> 'simple'});
 Object.assign(groups.receipt,{current:()=>structuredClone(receiptValue),performanceReceiptSuite:()=> 'agentic',loadPerformanceReceipt:async()=>{}});
 Object.assign(groups.evidence,{copiedEvidenceBinding:value=>value?structuredClone(value):null,activeEvidenceBindingFor:()=>structuredClone(activeBinding),
  applyOptimal:async(...args)=>{applies.push(args);return true}});
 const network={history:async()=>({history:structuredClone(history)}),plan:async()=>({plan:structuredClone(plan)}),
  start:async()=>({benchmark:{id:'fixture-comparison',kind:'engine-shootout',executionOrder:['omlx','lmstudio'],engines:[]}}),stop:async()=>({ok:true}),
  status:async()=>structuredClone(status),saveProfile:async()=>({profiles:[]})};
 for(const[group,values]of Object.entries(overrides))if(groups[group])Object.assign(groups[group],values);else if(group==='network')Object.assign(network,values);
 for(const[name,fn]of Object.entries(network))network[name]=async options=>{requests.push({method:name,body:options?.body?JSON.parse(options.body):null});return fn(options)};
 for(const id of ['benchmarkSuiteSelect','calibrationSuiteSelect'])nodes[id].value='agentic';
 for(const id of ['benchmarkPreferenceSelect','calibrationPreferenceSelect'])nodes[id].value='throughput';
 for(const id of ['calibrationCoolingSelect','fanSelect']){nodes[id].value='default';nodes[id].options=[{value:'default'},{value:'smart'}]}
 nodes.reasoningSelect.value='auto';nodes.reasoningSelect.options=[{value:'auto'},{value:'off'}];nodes.contextInput.value='8192';nodes.outputInput.value='1024';nodes.depthInput.value='3';
 nodes.samplingMode.value='model';nodes.modelSelect.value=model.id;nodes.modelSelect.options=[{value:model.id}];
 const policy=structuredClone(fixture.policyValues);
 const controller=Workspace.createController({nodes,...groups,network,decision,policy,preferenceLabels:{throughput:'highest generation TPS',responsive:'responsiveness'},
  platform:{setTimeout:fn=>{timers.push(fn);return timers.length},clearTimeout(){}},
  polling:{interval:()=>1000,register:task=>{polls.push(task);return task.run}}});
 return {controller,nodes,visible,activity,model,request,binding,plan,history,requests,notices,applies,timers,polls,policy,
  setStatus:value=>{status=value},setReceipt:value=>{receiptValue=value},setActiveBinding:value=>{activeBinding=value}};
}
module.exports={harness,element};
