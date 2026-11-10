'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
if(!process.env.LLM_LAUNCHER_BROWSER_PACKAGE)console.log('Benchmark/Calibration generated browser fixture skipped (opt-in).');
else(async()=>{
 const {chromium}=require(process.env.LLM_LAUNCHER_BROWSER_PACKAGE),root=path.resolve(__dirname,'..'),fixture=require('./fixtures/benchmark_workspace_legacy.json');
 const browser=await chromium.launch({headless:true});const output=path.join(root,'build/browser-qa');fs.mkdirSync(output,{recursive:true});
 const results=[];
 try{
  for(const width of [1440,390]){
   const page=await browser.newPage({viewport:{width,height:900}}),errors=[];page.on('pageerror',error=>errors.push(error.message));page.setDefaultTimeout(15000);
   await page.route('**/*',route=>route.abort('blockedbyclient'));
   let html=fs.readFileSync(path.join(root,'index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace(/<link\b[^>]*>/gi,'');
   const css=['styles.css','launcher-home.css','runtime-manager.css','saved-launches.css','model-assets.css'].filter(name=>fs.existsSync(path.join(root,name))).map(name=>fs.readFileSync(path.join(root,name),'utf8')).join('\n');
   await page.setContent(html.replace('</head>',`<style>${css}</style></head>`));
   await page.addScriptTag({path:path.join(root,'calibration_decision.js')});
   await page.addScriptTag({path:process.env.LLM_LAUNCHER_BENCHMARK_UI_SOURCE||path.join(root,'benchmark_workspace.js')});
   await page.evaluate(({policy,ids})=>{
    if(!document.getElementById('benchmarkHistoryRetry')){const button=document.createElement('button');button.id='benchmarkHistoryRetry';button.type='button';button.className='text-button hidden';button.textContent='Retry history';document.getElementById('benchmarkHistoryFreshness').after(button)}
    const nodes=Object.fromEntries(ids.map(id=>[id,document.getElementById(id)]));for(const[id,node]of Object.entries(nodes))if(!node)throw Error(`Missing explicit node ${id}`);
    const esc=value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
    const visible={backend:'omlx',client:'chat',optimalLabel:'Generated measured route'},activity={runPhase:'idle',setupPhase:'idle'},calls=[],applies=[],notices=[];
    const model={id:'generated-model',name:'Generated benchmark model',ready:true,backends:{omlx:{runnable:true,mtp:true,dflash:true,agentReasoning:['auto'],kv:true},lmstudio:{runnable:true,mtp:true,agentReasoning:['auto']}}};
    const request={modelId:model.id,backend:'omlx',client:'chat',context:16384,output:1024,reasoning:'auto',options:{kv:'off'},chat:{sampling:'model'}};
    const binding={scope:'engine',suite:'agentic',preference:'throughput',shootoutId:'generated-comparison',recordIds:{omlx:'generated-omlx',lmstudio:'generated-lms'}};
    const plan={action:'apply-existing',ready:true,model:{id:model.id,name:model.name},clientLabel:'Chat',request,contractId:'generated-contract',suite:{id:'agentic',label:'Agentic'},preference:'throughput',preferenceLabel:'Highest generation TPS',reasoningContract:{normalized:false},calibrationCooling:'default',calibrationCoolingLabel:'System controlled',eligibleEngineCount:2,modelReloadCount:2,measuredRequestCount:8,routeCount:4,resourceCooldownMaxSecondsPerRoute:30,engines:[{backend:'omlx',label:'oMLX',eligible:true,modes:[{label:'AR'},{label:'MTP'}],modeDetail:'Generated oMLX route'},{backend:'lmstudio',label:'LM Studio',eligible:true,modes:[{label:'AR'},{label:'MTP'}],modeDetail:'Generated LM Studio route'}],evidence:{trusted:true,tier:'cross-engine-local-benchmark',backend:'omlx',backendLabel:'oMLX',label:'Generated measured oMLX winner',detail:'Generated fixture only; no hardware TPS evidence.',comparedEngines:[{backend:'omlx',label:'oMLX',mode:'mtp',testedModes:['ar','mtp'],settingsLabel:'Generated MTP depth 3',decodeTokensPerSecond:20,display:'Generated 20.0 tok/s'},{backend:'lmstudio',label:'LM Studio',mode:'mtp',testedModes:['ar','mtp'],settingsLabel:'Generated MTP depth 3',decodeTokensPerSecond:15,display:'Generated 15.0 tok/s'}],evidenceBinding:binding},suggestedProfileName:'Generated profile'};
    const result={id:'generated-route',scope:'local',suite:'agentic',backend:'omlx',modelId:model.id,client:'chat',reasoning:'auto',qualityPassed:true,contextMin:16384,contextMax:16384,outputMax:1024,winner:'mtp',recommendation:'Generated MTP result',modes:{ar:{medianDecodeTokensPerSecond:10,samples:[{}]},mtp:{medianDecodeTokensPerSecond:20,samples:[{}]}}};
    const history={contract:{suite:'agentic'},freshness:'current',freshnessMessage:'Generated matching records',shootoutCount:0,runs:[],series:[],otherEvidence:{count:0},canRerunShootout:true,
      currentRouteRuns:Array.from({length:180},(_,i)=>({id:`generated-${i}`,suite:'agentic',createdAt:'2026-10-07T00:00:00Z',winnerLabel:'MTP',recommendation:`Generated result ${i}`,display:'20 tok/s'}))};
    let historyError=false,saveError=false,applySucceeds=true,status={phase:'idle'};
    for(const id of ['benchmarkSuiteSelect','calibrationSuiteSelect'])nodes[id].value='agentic';for(const id of ['benchmarkPreferenceSelect','calibrationPreferenceSelect'])nodes[id].value='throughput';
    for(const id of ['fanSelect','calibrationCoolingSelect']){if(![...nodes[id].options].some(x=>x.value==='default'))nodes[id].add(new Option('System controlled','default'));nodes[id].value='default'}
    nodes.reasoningSelect.innerHTML='<option value="auto">Auto</option><option value="off">Off</option>';nodes.reasoningSelect.value='auto';nodes.contextInput.value='16384';nodes.outputInput.value='1024';nodes.depthInput.value='3';nodes.samplingMode.value='model';
    nodes.modelSelect.innerHTML='<option value="generated-model">Generated benchmark model</option>';
    const controller=LLMBenchmarkWorkspace.createController({nodes,policy,decision:globalThis.CalibrationDecision,preferenceLabels:{throughput:'highest generation TPS'},
     platform:{setTimeout,clearTimeout},polling:{interval:()=>1000,register:task=>task.run},
     formatting:{esc,formatNumber:value=>Number(value).toLocaleString(),formatBytes:String,finiteMetric:value=>typeof value==='number'&&Number.isFinite(value)?value:null,backendName:String,clientName:String,exactContextTier:String},
     capabilities:{selectedModel:()=>model,visibleEngineAdapters:()=>[{id:'omlx',binaryKey:'omlx'},{id:'lmstudio',binaryKey:'lmstudio'}],backendBinaryKey:String,runtimeInstalled:()=>true,resolvedClientSupport:()=>({supported:true}),uiEngineVisible:()=>true,freeTokenRoute:()=>false,mtplxLongContextCapabilityExact:()=>false,llamaCppPleCapabilityQualified:()=>false,selectedRouteQualificationBackend:()=>'',controllerRouteQualificationBackend:()=>'',isUzuQualificationSuite:()=>false},
     settings:{snapshot:()=>({...visible}),gather:()=>structuredClone({...request,context:Number(nodes.contextInput.value),output:Number(nodes.outputInput.value),reasoning:nodes.reasoningSelect.value}),runtimeKvValue:()=> 'off',refreshLaunchability(){},setRuntimeKvValue:()=>true,persistVisibleRoute(){},cancelOptimization(){},setRangeVisual(){},updateAccelerationState(){},selectBackend:value=>{visible.backend=value},modelChanged(){},resetSessionAcknowledgement(){}},
     operations:{snapshot:()=>({...activity}),acquisitionIsActive:()=>false,routeCheckIsActive:()=>false,aneWorkIsActive:()=>false,profileBusy:()=>false,currentSessionAdmission:()=>({known:true,actionReady:true}),sessionAdmissionDecision:value=>value||{actionReady:false},sessionAdmissionBlockerCopy:()=> 'Generated blocked capacity',requireFreshSessionAdmission:async()=>true},
     evidence:{copiedEvidenceBinding:value=>value?structuredClone(value):null,activeEvidenceBindingFor:()=>structuredClone(binding),applyOptimal:async(...args)=>{applies.push(args);return applySucceeds}},
     effects:{showNotice:(...args)=>notices.push(args),pollStatus:async()=>{},loadModels:async()=>{},useProfileInventory(){},activeDetail:()=> 'simple',closeOptimizerMenu(){}},
     receipt:{current:()=>null,performanceReceiptSuite:()=> 'agentic',schedulePerformanceReceipt(){},loadPerformanceReceipt:async()=>{}},
     network:{status:async()=>structuredClone(status),history:async options=>{const body=JSON.parse(options.body);calls.push({method:'history',body});if(historyError)throw Error('Generated history refresh failure');return{history:body.reviewRecordId?{reviewResult:{...result,id:body.reviewRecordId}}:structuredClone(history)}},
      plan:async options=>{calls.push({method:'plan',body:JSON.parse(options.body)});return{plan:structuredClone(plan)}},start:async options=>{calls.push({method:'start',body:JSON.parse(options.body)});status={phase:'queued',job:{id:'generated-job'},modes:{}};return{benchmark:status.job}},stop:async()=>{calls.push({method:'stop'});status={phase:'cancelled'};return{ok:true}},saveProfile:async options=>{calls.push({method:'saveProfile',body:JSON.parse(options.body)});if(saveError)throw Error('Generated profile save failure');return{profiles:[]}}}});
    controller.initialize();globalThis.fixture={controller,nodes,plan,history,calls,applies,notices,setHistoryError:value=>{historyError=value},setSaveError:value=>{saveError=value},setApplySucceeds:value=>{applySucceeds=value}};
   },{policy:fixture.policyValues,ids:fixture.nodeIds});
   await page.evaluate(async()=>{await fixture.controller.openBenchmarkLab();});
   await page.waitForFunction(()=>fixture.controller.view().hasHistory);
   await page.locator('#benchmarkHistoryPanel').evaluate(node=>node.open=true);
   const timing=await page.evaluate(()=>{
    const button=document.querySelector('[data-review-benchmark]');button.focus();const samples=[],observer=new MutationObserver(()=>{});observer.observe(fixture.nodes.benchmarkHistoryRuns,{childList:true});
    for(let i=0;i<30;i++){const start=performance.now();fixture.controller.renderBenchmarkHistory();samples.push(performance.now()-start)}
    const mutations=observer.takeRecords().length;observer.disconnect();samples.sort((a,b)=>a-b);
    return{medianRenderMs:samples[15],mutations,retainedButton:button.isConnected,focusRetained:document.activeElement===button};
   });
   if(!process.env.LLM_LAUNCHER_BENCHMARK_UI_BASELINE){assert.equal(timing.retainedButton,true);assert.equal(timing.focusRetained,true);assert.equal(timing.mutations,0)}
   if(!process.env.LLM_LAUNCHER_BENCHMARK_UI_BASELINE){
    await page.evaluate(async()=>{fixture.setHistoryError(true);await fixture.controller.loadBenchmarkHistory(true)});
    assert.equal(await page.locator('[data-review-benchmark]').count(),180);assert.match(await page.locator('#benchmarkHistoryFreshness').innerText(),/Last loaded history is shown/);
    await page.evaluate(()=>fixture.setHistoryError(false));await page.locator('#benchmarkHistoryRetry').click();await page.waitForFunction(()=>fixture.controller.view().historyError==='');
   }
   await page.locator('[data-review-benchmark="generated-0"]').click();await page.waitForFunction(()=>fixture.controller.benchmarkDisplayedStatus().savedReview===true);
   assert.equal(await page.evaluate(()=>fixture.controller.status().phase),'idle');
   await page.evaluate(()=>fixture.controller.renderBenchmarkStatus({phase:'idle'}));assert.equal(await page.locator('#benchmarkPhase').textContent(),'Saved result');
   await page.locator('#benchmarkStartButton').click();await page.waitForFunction(()=>fixture.controller.view().phase==='queued');await page.locator('#benchmarkStopButton').click();await page.waitForFunction(()=>fixture.controller.view().phase==='cancelled');
   await page.evaluate(()=>fixture.nodes.benchmarkDialog.close());await page.evaluate(()=>fixture.controller.openCalibrationAssistant());
   assert.equal(await page.locator('#calibrationEngineCards article').count(),2);assert.match(await page.locator('#calibrationEvidence').innerText(),/Generated measured oMLX winner/);assert.match(await page.locator('#calibrationResults').innerText(),/Generated 20\.0 tok\/s[\s\S]*LM Studio[\s\S]*Generated 15\.0 tok\/s/);
   await page.locator('#calibrationProfileName').fill('Private generated profile');
   await page.evaluate(()=>fixture.setSaveError(true));await page.locator('#calibrationSaveButton').click();await page.waitForFunction(()=>fixture.notices.some(item=>String(item[0]).includes('Generated profile save failure')));
   const errorVisible=await page.evaluate(()=>fixture.nodes.calibrationStatus.textContent.includes('Generated profile save failure'));if(!process.env.LLM_LAUNCHER_BENCHMARK_UI_BASELINE){assert.equal(errorVisible,true);await page.evaluate(()=>fixture.controller.renderBenchmarkStatus({phase:'cancelled'}));assert.match(await page.locator('#calibrationStatus').textContent(),/Generated profile save failure/)}
   assert.equal(await page.locator('#calibrationProfileName').inputValue(),'Private generated profile');
   await page.evaluate(()=>fixture.setSaveError(false));await page.locator('#calibrationSaveButton').click();await page.waitForFunction(()=>!fixture.nodes.calibrationDialog.open);
   const geometry=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,applies:fixture.applies,calls:fixture.calls}));assert.ok(geometry.scrollWidth<=width+1);
   assert.deepEqual(geometry.applies.map(x=>x[3]),[fixtureBinding(),fixtureBinding()]);
   await page.evaluate(()=>fixture.controller.openCalibrationAssistant());await page.locator('#calibrationResults').scrollIntoViewIfNeeded();assert.equal(await page.locator('#calibrationSaveButton').isVisible(),true);await page.screenshot({path:path.join(output,`benchmark-workspace-${width}.png`),fullPage:false});
   assert.deepEqual(errors,[]);results.push({width,timing,exactApplyReferences:geometry.applies.length,generatedStartStop:true,profileSaveRecovery:true,errorVisible});await page.close();
  }
  if(process.env.LLM_LAUNCHER_BENCHMARK_UI_REPORT)fs.writeFileSync(process.env.LLM_LAUNCHER_BENCHMARK_UI_REPORT,JSON.stringify({scope:'Generated DOM work and synthetic ports only; no inference TPS claim',results},null,2)+'\n');
  console.log(JSON.stringify(results));
 }finally{await browser.close()}
 function fixtureBinding(){return{scope:'engine',suite:'agentic',preference:'throughput',shootoutId:'generated-comparison',recordIds:{omlx:'generated-omlx',lmstudio:'generated-lms'}}}
})().catch(error=>{console.error(error);process.exitCode=1});
