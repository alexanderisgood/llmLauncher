"use strict";
const fs=require("node:fs"),Workspace=require("../../agent_console_workspace.js");
class Element {
  constructor(document,tag="div"){this.ownerDocument=document;this.tagName=tag;this.hidden=false;this.disabled=false;this.open=false;this.value="";
    this.textContent="";this.dataset={};this.style={};this.children=[];this.listeners=new Map();this.attributes=new Map();this.markup="";
    this.scrollTop=0;this.scrollHeight=600;this.clientHeight=300;this.clientWidth=600;this.virtual=new Map();const classes=new Set();
    this.classList={contains:value=>classes.has(value),add:value=>classes.add(value),remove:value=>classes.delete(value),
      toggle:(value,on)=>{const flag=on??!classes.has(value);flag?classes.add(value):classes.delete(value);return flag;}};}
  addEventListener(name,fn){if(!this.listeners.has(name))this.listeners.set(name,[]);this.listeners.get(name).push(fn);}
  removeEventListener(name,fn){this.listeners.set(name,(this.listeners.get(name)||[]).filter(item=>item!==fn));}
  emit(name,details={}){for(const fn of this.listeners.get(name)||[])fn({target:this,currentTarget:this,preventDefault(){},stopPropagation(){},...details});}
  set innerHTML(value){this.markup=value;}get innerHTML(){return this.markup;}
  append(...nodes){this.children.push(...nodes);}replaceChildren(...nodes){this.children=nodes;this.markup="";}
  querySelector(selector){if(!this.virtual.has(selector))this.virtual.set(selector,new Element(this.ownerDocument,selector));return this.virtual.get(selector);}
  querySelectorAll(selector){const all=this.children.flatMap(child=>[child,...child.querySelectorAll(selector)]);return all.filter(item=>selector==="button"?item.tagName==="button":false);}
  getAttribute(name){return this.attributes.get(name)||null;}setAttribute(name,value){this.attributes.set(name,String(value));}removeAttribute(name){this.attributes.delete(name);}
  focus(){this.ownerDocument.activeElement=this;}setCustomValidity(value){this.validity=value;}reportValidity(){}scrollIntoView(){}
  showModal(){this.open=true;}close(){this.open=false;}contains(item){return item===this||this.children.includes(item);}
}
module.exports=function fixture({saved=new Map(),overrides={},navigationOverrides={}}={}){
  let timer=0;const timers=new Map(),frames=new Map(),intervals=new Map();
  const window=new Element(null);window.performance={now:()=>100};window.requestAnimationFrame=fn=>{frames.set(++timer,fn);return timer;};window.cancelAnimationFrame=id=>frames.delete(id);
  window.setTimeout=(fn,delay)=>{timers.set(++timer,{fn,delay});return timer;};window.clearTimeout=id=>timers.delete(id);
  window.setInterval=fn=>{intervals.set(++timer,fn);return timer;};window.clearInterval=id=>intervals.delete(id);
  window.ResizeObserver=class {observe(){}disconnect(){this.disconnected=true;}};
  const document=new Element(null);document.defaultView=window;document.activeElement=null;document.hidden=false;
  document.createElement=tag=>new Element(document,tag);document.createTextNode=text=>{const node=new Element(document,"text");node.textContent=text;return node;};
  document.createDocumentFragment=()=>new Element(document,"fragment");document.body=new Element(document,"body");
  const source=fs.readFileSync(require.resolve("../../agent_console_workspace.js"),"utf8");
  const ids=[...new Set([...source.matchAll(/\$\("([^\"]+)"\)/g)].map(match=>match[1]).concat("agentConsoleStatusPrompt","agentConsoleStatusPromptValue","agentConsoleStatusContext","agentConsoleStatusContextValue"))];
  const elements=Object.fromEntries(ids.map(id=>[id,new Element(document)]));elements.agentWorkspace.classList.add("hidden");
  const calls={read:[],input:[],resize:[],stop:[],restart:[],fans:[],navigation:[],notice:[],hub:[],timeline:[]};
  let status={phase:"idle"},activity={active:[],queued:[],recent:[]};
  const endpoints=Object.fromEntries(["read","input","resize","stop","restart","fans"].map(name=>[name,async body=>{
    calls[name].push(body);return name==="fans"?{mode:"system",smartAvailable:false}:{console:{...status.agentConsoles?.find(item=>item.surfaceId===body.surfaceId)}};
  }]));Object.assign(endpoints,overrides);
  const controller=Workspace.createController({elements,endpoints,storage:{getItem:key=>saved.get(key)||null,setItem:(key,value)=>saved.set(key,value),removeItem:key=>saved.delete(key)},
    copyText:async text=>calls.copied=text,alertUser:message=>calls.notice.push(message),notify:(...args)=>calls.notice.push(args),
    activitySnapshot:()=>activity,onHubStatus:hub=>{calls.hub.push(hub);status={...status,attachments:hub?.attachments||status.attachments,agentConsoles:hub?.agentConsoles||[]};return status;},
    navigation:{refreshChat:()=>calls.navigation.push("chat"),closeSessions:()=>calls.navigation.push("close-sessions"),setConsoleVisible:visible=>{calls.navigation.push(["visible",visible]);return false;},
      updateChrome:()=>calls.navigation.push("chrome"),setSubtitle:value=>calls.navigation.push(["subtitle",value]),showSettings:()=>calls.navigation.push("settings"),
      refreshSessions:async()=>calls.navigation.push("refresh-sessions"),showLog:()=>calls.navigation.push("log"),openSessions:()=>calls.navigation.push("sessions"),...navigationOverrides},
    sessionRouteActive:(run,phase)=>run?.purpose==="session"&&["preflight","starting","running","stopping"].includes(phase),
    surfacePostmortemMarker:(phase,message,subject)=>({state:phase==="failed"?"failed":"stopped",title:subject,detail:message}),
    backendName:String,clientName:String,formatBytes:value=>value+" B",formatNumber:String,formatShortDuration:value=>value+"s",formatTimestamp:String,
    liveRequestPhaseLabel:()=>"Generating",liveRequestDetail:()=>"Generated request",
    cores:{TerminalCore:require("../../terminal_core.js"),AgentConsoleTabsCore:require("../../agent_console_tabs.js"),AgentConsoleInputCore:require("../../agent_console_input.js"),
      ChatDraftsCore:require("../../chat_drafts.js"),PiTimelineCore:require("../../pi_timeline.js"),ChatStatusCore:require("../../chat_status.js"),UiPresenter:require("../../ui_presenter.js"),
      timelineViewFactory:()=>({clear:()=>{},setVisible:()=>{},render:(node,items,options)=>calls.timeline.push({items,options})})}});
  const observe=value=>{status=value;controller.observe(value);controller.update(value.run,value.phase);};
  return {controller,elements,calls,endpoints,saved,document,window,timers,frames,intervals,observe,activity:value=>{activity=value;}};
};
module.exports.deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
