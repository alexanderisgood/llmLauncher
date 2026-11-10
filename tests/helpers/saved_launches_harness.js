"use strict";
// Connect existing app adapters/fixtures to the real feature component.
const SavedLaunches=require("../../saved_launches.js");
const ids=["openProfileManager","profileDialog","profileRunNotice","profileRunMessage","profileRunAction",
  "profileEditBanner","profileEditName","profileEditSave","profileEditCancel","profileEditStatus",
  "profileManagerStatus","profileName","profilePolicySelect","profileGoalSelect","profileGoalField",
  "profilePolicyHelp","profileSaveButton","profileSaveForm","profileNameHint","profileCancelEdit",
  "profileCountBadge","profileCards","quickStart","quickStartSummary","quickStartCustom",
  "quickStartCards","quickStartStatus","customLaunchEditor","launchDock"];
module.exports=function connect(context, overrides={}) {
  const $=context.$;
  const manager=SavedLaunches.createController({
    elements:Object.fromEntries(ids.map(id=>[id,$(id)])),
    api:{inventory:()=>context.api("/api/profiles"),
      save:body=>context.api("/api/profiles/save",{method:"POST",body:JSON.stringify(body)}),
      remove:body=>context.api("/api/profiles/delete",{method:"POST",body:JSON.stringify(body)}),
      sessionSets:async()=>({sets:[]}),history:async()=>({threads:[]})},
    visible:context.uiProfileVisible||(()=>true),
    externalSettingsReason:()=>context.profileExternalSettingsReason?.()||"",
    externalLaunchReason:()=>context.profileExternalLaunchReason?.()||"",
    sessionActive:()=>["preflight","starting","running","stopping"].includes(context.state.runPhase),
    currentRoute:()=>context.currentVisibleRoute?.()||null,routeKey:context.RoutePreferenceCore?.routeKey||(()=>""),
    selectedRequest:()=>context.gather("custom"),applyRequest:request=>context.applyProfileRequest(request),
    launchVisible:()=>context.launch(),copyEvidence:value=>context.copiedEvidenceBinding(value),
    activeEvidence:(...args)=>context.activeEvidenceBindingFor(...args),
    applyEvidence:(scope,preference,binding)=>context.applyOptimal(scope,preference,false,binding),
    backendLabel:context.profileBackendLabel||String,clientName:context.clientName||String,
    dateLabel:context.profileDate||String,formatNumber:context.formatNumber||String,
    kvLabel:context.runtimeKvLabel||(()=>"Full precision"),preferenceLabels:context.enginePreferenceLabels||{},
    isExperimental:context.requestUsesExperimentalFreeToken||(()=>false),
    needsExperimentalConsent:()=>context.freeTokenExperimentalConsentRequired(),storage:()=>context.themeStorage?.(),
    restoreProject:project=>{$("projectPath").value=project;context.refreshLaunchability();},
    refreshControls:()=>context.refreshLaunchability(),openEditor:()=>context.setQuickStartEditor(true),
    openEditSettings:()=>{$("launchSettings").open=true;},
    revealSettings:()=>{if(context.state.agentConsoleVisible)context.leaveAgentConsole();},
    focusSettings:editing=>{$(editing?"profileEditBanner":"customLaunchEditor").scrollIntoView({behavior:"smooth",block:"start"});
      if(editing)$("reasoningSelect").focus({preventScroll:true});},
    revealExperimental:()=>{$("advancedControls").open=true;$("freeTokenQualificationPanel").scrollIntoView();$("freeTokenExperimentalConsent").focus();},
    openSessions:()=>context.openSessionDashboard?.(),shortcutContext:()=>({}),
    acceptSessionSets:()=>{},acceptHistory:()=>{},reviewSessionSet:()=>{},openChatShortcut:()=>{},
    notify:(...args)=>context.showNotice(...args),schedule:callback=>context.requestAnimationFrame(callback),
    ...overrides,
  });
  context.profilesManager=manager;
  return manager;
};
