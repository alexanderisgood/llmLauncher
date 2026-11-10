'use strict';
const assert=require('node:assert/strict'),Home=require('../launcher_home.js'),presenter=require('../ui_presenter.js'),frozen=require('./fixtures/launch_workspace_legacy.json');
const ids=[...new Set([...frozen.homeLegacySource.matchAll(/\$\("([^"\n]+)"\)/g)].map(x=>x[1]))];
function makeNodes(){return Object.fromEntries(ids.map(id=>[id,{dataset:{},value:'',textContent:'',title:'',disabled:false,inert:false,classList:{contains:()=>false},setAttribute(name,value){this[name]=String(value)},getAttribute(name){return this[name]},replaceChildren(...values){this.options=values}}]))}
const state={backend:'splash',client:'omp',performanceReceipt:{backend:'splash',state:'trusted-route',fresh:true,decodeTokensPerSecond:31.25,firstTokenSeconds:0.39},performanceReceiptLoading:false,performanceReceiptError:'',launchPreparing:false,applyingOptimal:false,homeEngineFeedbackSignature:'',homeEngineFeedback:''};
const common={presenter,backendName:String,clientName:String,protectedSnapshot:()=> 'contract',formatNumber:String,exactContextTier:String,gatherOptions:()=>({kv:'off'}),runtimeKvLabel:()=> 'Full precision',currentWarmRoutePlan:()=>null,clientAvailability:()=>({available:true}),selectedModel:()=>({name:'Generated model',backends:{splash:{}}})};
const oldNodes=makeNodes(),newNodes=makeNodes(),oldBody={dataset:{}},newBody={dataset:{}};
for(const nodes of [oldNodes,newNodes]){nodes.contextInput.value='16384';nodes.outputInput.value='1024';nodes.reasoningSelect.value='off'}
const buttons=[{dataset:{backend:'splash'},disabled:false,hidden:false},{dataset:{backend:'kolibri'},disabled:true,hidden:false}];
const legacy=Home.createController({...common,$:id=>oldNodes[id],state,document:{body:oldBody,querySelectorAll:()=>buttons,createElement:()=>({})}});
let reads=0;const modern=Home.createController({...common,nodes:newNodes,view:()=>{reads++;return Object.freeze({...state})},backendButtons:()=>buttons,createOption:()=>({}),markPreparing:value=>presenter.data(newBody,'preparingLaunch',value)});
function snapshot(nodes){return JSON.parse(JSON.stringify(nodes))}
for(const mutate of [()=>{},()=>{state.launchPreparing=true},()=>{state.launchPreparing=false;state.performanceReceiptLoading=true},()=>{state.performanceReceiptLoading=false;state.performanceReceiptError='Generated error'},()=>{state.performanceReceiptError='';state.backend='kolibri'},()=>{state.applyingOptimal=true;buttons[0].disabled=true},()=>{state.applyingOptimal=false;state.homeEngineFeedback='Generated decision';state.homeEngineFeedbackSignature='contract'}]){
 mutate();legacy.update({decision:'ready'});modern.update({decision:'ready'});assert.deepEqual(snapshot(newNodes),snapshot(oldNodes),'Narrow Home ports preserve every rendered property, attribute, option and label');assert.deepEqual(newBody,oldBody);
}
assert.ok(reads>0);assert.equal('state' in modern,false);assert.equal('document' in modern,false);
function legacyMethod(name,end){const start=frozen.homeLegacySource.indexOf(`    function ${name}(`),stop=frozen.homeLegacySource.indexOf(end,start);assert.ok(start>=0&&stop>start);return frozen.homeLegacySource.slice(start,stop).trim()}
assert.equal(modern.renderOverview.toString(),legacyMethod('renderOverview','\n    function update('),'The complete authoritative Home overview body is unchanged');
const expected=legacyMethod('update','\n    return {update, renderOverview};')
 .replace('presenter.data(document.body, "preparingLaunch", Boolean(state.launchPreparing));','markPreparing(Boolean(state.launchPreparing));')
 .replace('const buttons = [...document.querySelectorAll("[data-backend]")].filter(button => !button.hidden);','const buttons = backendButtons().filter(button => !button.hidden);')
 .replace('const option = document.createElement("option");','const option = createOption();');
assert.equal(modern.update.toString(),expected,'Only three explicit DOM port calls differ in the complete Home renderer');
console.log('Narrow Home ports preserve full legacy render bodies and seven generated view/capability transitions.');
