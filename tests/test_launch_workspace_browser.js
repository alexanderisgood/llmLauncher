'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
if(!process.env.LLM_LAUNCHER_BROWSER_PACKAGE)console.log('Standalone Launch Workspace generated browser skipped (opt-in).');
else(async()=>{
 const {chromium}=require(process.env.LLM_LAUNCHER_BROWSER_PACKAGE),root=path.resolve(__dirname,'..'),fixture=require('./fixtures/launch_workspace_legacy.json');
 let harnessSource=require('./helpers/launch_workspace_harness.js').harness.toString();
 harnessSource=harnessSource.replace('element(id)','document.getElementById(id)');
 harnessSource=harnessSource.replace(/ for\(const node of Object\.values\(nodes\)\)\{[^\n]*\}\n/,'');
 harnessSource=harnessSource.replace("backendButtons:Object.keys(model.backends).map(id=>{const node=element(id);node.dataset.backend=id;return node})","backendButtons:[...document.querySelectorAll('[data-backend]')]")
  .replace("clientButtons:Object.keys(support).map(id=>{const node=element(id);node.dataset.client=id;return node})","clientButtons:[...document.querySelectorAll('[data-client]')]")
  .replace('optimizerButtons:[],optimizerControls:[],chatSamplers:[],sessionSamplers:[]',"optimizerButtons:[...document.querySelectorAll('[data-optimizer-scope]')],optimizerControls:[...document.querySelectorAll('.optimizable')],chatSamplers:[...document.querySelectorAll('.chat-sampler')],sessionSamplers:[...document.querySelectorAll('.session-attach-sampler')]")
  .replace("nodes[id].options=[{value},{value:'off'},{value:'auto'},{value:'5'},{value:'0'}]",'')
  .replace('nodes.modelSelect.options=[{value:model.id}];','')
  .replace('uiEngineVisible:()=>true','uiEngineVisible:id=>id!=="freetoken"&&id!=="llamacpp"')
  .replace('performance:{now:()=>0}','performance')
  .replace('activeElement:()=>null,isHidden:()=>false,createOption:()=>({})','activeElement:()=>document.activeElement,isHidden:()=>document.hidden,createOption:()=>document.createElement("option")')
  .replace('onDocumentClick(){},onDocumentKeyDown(){}','onDocumentClick:fn=>document.addEventListener("click",fn),onDocumentKeyDown:fn=>document.addEventListener("keydown",fn)');
 const browser=await chromium.launch({headless:true}),output=path.join(root,'build/browser-qa');fs.mkdirSync(output,{recursive:true});const results=[];
 try{for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:900}}),errors=[];page.setDefaultTimeout(15000);page.on('pageerror',error=>errors.push(error.message));await page.route('**/*',route=>route.abort('blockedbyclient'));
  const html=fs.readFileSync(path.join(root,'index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace(/<link\b[^>]*>/gi,'');const css=['styles.css','launcher-home.css','saved-launches.css','model-assets.css','runtime-manager.css'].map(name=>fs.readFileSync(path.join(root,name),'utf8')).join('\n');await page.setContent(html.replace('</head>',`<style>${css}</style></head>`));
  for(const name of ['route_preferences.js','launch_flow.js','launcher_home.js','chat_status.js','calibration_decision.js','ui_presenter.js','request_metrics.js','launch_workspace.js'])await page.addScriptTag({path:path.join(root,name)});
  await page.evaluate(({fixture,harnessSource})=>{
   const Workspace=globalThis.LLMLaunchWorkspace,cores={RoutePreferenceCore:LLMRoutePreferenceCore,LaunchFlow,LauncherHomeCore:LLMLauncherHome,ChatStatusCore:LLMChatStatusCore,CalibrationDecision,UiPresenter:LLMUiPresenter};
   const build=eval('('+harnessSource+')');globalThis.fixture=build();globalThis.fixture.controller.initialize();
  },{fixture,harnessSource});
  await page.evaluate(async()=>{await fixture.controller.loadModels();await fixture.controller.loadSessionDashboard();fixture.controller.updateLaunchHome()});
  assert.match(await page.locator('#homeRouteModel').innerText(),/Generated model/);assert.equal(await page.locator('#homeRouteEngine').textContent(),'MTPLX');assert.equal(await page.locator('#homeRouteAgent').textContent(),'Pi');assert.equal(await page.locator('#contextInput').inputValue(),'16384');
  // Real keyboard/model controls keep the complete selected request contract.
  await page.locator('#launchSettings').evaluate(node=>node.open=true);await page.locator('#contextSelect').selectOption('32768');
  await page.evaluate(async()=>{await fixture.controller.loadSessionDashboard();fixture.controller.updateLaunchHome()});
  await page.locator('#launchButton').click();await page.waitForFunction(()=>fixture.controller.view().phase==='preflight');
  const body=await page.evaluate(()=>fixture.requests.find(x=>x.method==='launch').body);assert.equal(body.context,32768);assert.equal(body.output,1024);assert.equal(body.reasoning,'auto');assert.equal(body.options.kv,'off');assert.equal(body.client,'pi');
  await page.evaluate(()=>{fixture.controller.renderRun({phase:'running',run:{runId:'browser-owner',client:'pi',backend:'mtplx',model:'Generated model',context:32768,output:1024,reasoning:'auto',port:18987,clientPort:18988},activity:{...fixture.activity,active:[{id:'generated-request',state:'running',client:'pi',surface:'Generated Pi',surfaceId:'generated-surface',runSeconds:1,canCancel:true}]},events:[]});fixture.nodes.sessionDialog.showModal()});
  const focused=await page.evaluate(()=>{
   const button=document.querySelector('[data-session-cancel-request]');button.focus();const observer=new MutationObserver(()=>{});observer.observe(fixture.nodes.sessionActivityList,{childList:true});for(let i=0;i<30;i++)fixture.controller.renderRequestActivity(fixture.controller.activity());const mutations=observer.takeRecords().length;observer.disconnect();return{retained:button.isConnected,focusRetained:document.activeElement===button,mutations};
  });assert.deepEqual(focused,{retained:true,focusRetained:true,mutations:0});
  assert.doesNotMatch(await page.locator('#sessionResourceFacts').innerText(),/34359738368|51539607552/);assert.match(await page.locator('#sessionResourceFacts').innerText(),/GB/);
  await page.locator('#sessionIdleTimeout').selectOption('5');await page.waitForFunction(()=>fixture.requests.some(x=>x.method==='sessionIdlePolicy'&&x.body.timeoutMinutes===5));
  assert.equal(await page.locator('#sessionIdleTimeout').inputValue(),'5');
  await page.evaluate(()=>fixture.controller.renderRequestActivity({...fixture.activity,recent:[{id:'generated-native',state:'completed',client:'pi',surface:'Generated Splash example',backend:'splash',runSeconds:1,runtimeStatsSource:'splash-native-stats',runtimeTokensPerSecond:77.54,decodeTokensPerSecond:91.1,endToEndTokensPerSecond:50}]}));
  assert.match(await page.locator('#sessionActivityList').innerText(),/77\.5 tok\/s[\s\S]*first native batch excluded/);assert.doesNotMatch(await page.locator('#sessionActivityList').innerText(),/91\.1/);
  await page.evaluate(()=>fixture.controller.renderRequestActivity({...fixture.activity,recent:[{id:'generated-unknown',state:'completed',client:'pi',surface:'Generated unknown-source example',runSeconds:1,runtimeStatsSource:'unknown',runtimeTokensPerSecond:99}]}));assert.match(await page.locator('#sessionActivityList').innerText(),/TPS unavailable/);assert.doesNotMatch(await page.locator('#sessionActivityList').innerText(),/99\.0/);
  await page.evaluate(()=>fixture.controller.renderRequestActivity(fixture.activity));assert.match(await page.locator('#sessionActivityState').innerText(),/Relay idle/);
  await page.evaluate(()=>fixture.controller.renderRequestActivity({...fixture.activity,engineResident:false,active:[],queued:[],recent:[]}));assert.match(await page.locator('#sessionActivityState').innerText(),/No resident model/);
  await page.evaluate(()=>fixture.controller.renderRequestActivity(fixture.activity));
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.locator('#sessionActivitySection').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(output,`launch-workspace-session-${width}.png`),fullPage:false});
  await page.evaluate(()=>fixture.nodes.sessionDialog.close());await page.evaluate(()=>fixture.controller.renderRun({phase:'idle',events:[]}));
  await page.evaluate(async()=>{fixture.session.admission.requiresAcknowledgement=true;fixture.session.admission.contractId='browser-memory-contract';await fixture.controller.loadSessionDashboard()});
  await page.locator('#launchButton').click();await page.waitForFunction(()=>fixture.nodes.launchPreparation.dataset.phase==='review');assert.match(await page.locator('#launchPreparationTitle').textContent(),/more memory/);
  await page.locator('#continueLaunchPreparation').click();await page.waitForFunction(()=>fixture.controller.view().phase==='preflight');assert.equal(await page.evaluate(()=>fixture.requests.filter(x=>x.method==='launch').at(-1).body.memoryAcknowledgement),'browser-memory-contract');
  await page.evaluate(()=>{fixture.controller.renderRun({phase:'idle',events:[]});fixture.session.admission.requiresAcknowledgement=false;fixture.network.sessionPlan=()=>new Promise(resolve=>{globalThis.resolveDelayedPlan=resolve})});
  await page.locator('#launchButton').click();await page.waitForFunction(()=>typeof resolveDelayedPlan==='function');await page.locator('#cancelLaunchPreparation').click();
  await page.evaluate(()=>resolveDelayedPlan({sessions:structuredClone(fixture.session)}));await page.waitForFunction(()=>!fixture.controller.view().launchPreparing);assert.match(await page.locator('#launchPreparationDetail').textContent(),/cancelled/i);assert.equal(await page.evaluate(()=>fixture.requests.filter(x=>x.method==='launch').length),2);
  await page.locator('#cancelLaunchPreparation').click();
  await page.evaluate(async()=>{fixture.network.sessionPlan=async()=>({sessions:{...structuredClone(fixture.session),admission:{...fixture.session.admission,launchable:false,detail:'Generated route cannot fit safely'}}});await fixture.controller.loadSessionDashboard()});
  await page.locator('#launchButton').click();await page.waitForFunction(()=>!fixture.controller.view().launchPreparing);assert.match(await page.locator('#launchPreparationDetail').textContent(),/cannot fit safely/);
  await page.screenshot({path:path.join(output,`launch-workspace-error-${width}.png`),fullPage:false});await page.locator('#cancelLaunchPreparation').click();
  await page.evaluate(async()=>{fixture.network.sessionPlan=async()=>({sessions:structuredClone(fixture.session)});await fixture.controller.loadSessionDashboard()});
  await page.screenshot({path:path.join(output,`launch-workspace-home-${width}.png`),fullPage:false});
  assert.deepEqual(errors,[]);results.push({width,exactSelectedRequest:true,unchangedRows:focused,sessionIdleChoice:true,nativeAndUnknownTpsLabels:true,activeIdleRelayStates:true,exactMemoryReview:true,cancelAndBlockedRecovery:true,noOverflow:true});await page.close();
 }}finally{await browser.close()}
 console.log(JSON.stringify(results));
 if(process.env.LLM_LAUNCHER_LAUNCH_BROWSER_REPORT)fs.writeFileSync(process.env.LLM_LAUNCHER_LAUNCH_BROWSER_REPORT,JSON.stringify(results,null,2)+'\n');
})().catch(error=>{console.error(error);process.exitCode=1});
