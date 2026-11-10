"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const root=path.resolve(__dirname,"../..");
const app=fs.readFileSync(path.join(root,"app.js"),"utf8");
const consoleWorkspace=fs.readFileSync(path.join(root,"agent_console_workspace.js"),"utf8");
const launchWorkspace=fs.readFileSync(path.join(root,"launch_workspace.js"),"utf8");
const launchNames=new Set(require("../fixtures/launch_workspace_legacy.json").methods.map(item=>item.name));
const chatWorkspace=fs.readFileSync(path.join(root,"chat_workspace.js"),"utf8");
function between(startMarker,endMarker){
  const launchOwned=launchNames.has(startMarker.match(/function ([A-Za-z0-9_]+)/)?.[1]);
  const consoleOwned=/AgentConsole|AgentWorkspace|AgentPiTimeline/.test(startMarker);
  const chatOwned=/Chat|chat/.test(startMarker);
  for(const source of launchOwned?[launchWorkspace,app,chatWorkspace,consoleWorkspace]:consoleOwned?[consoleWorkspace,app,chatWorkspace]:chatOwned?[chatWorkspace,app,consoleWorkspace]:[app,chatWorkspace,consoleWorkspace]){
    const start=source.indexOf(startMarker);if(start<0)continue;
    const boundary=endMarker==="\nfunction agentConsoleBaseOffset"&&source===app?"\nconst agentConsoleWorkspace":endMarker;
    let end=source.indexOf(boundary,start+startMarker.length);
    if(end<=start&&(source===chatWorkspace||source===launchWorkspace)){
      // A neighboring controller function now belongs to another domain.
      // The complete Chat function ends before its next own declaration.
      const next=/\n(?:async )?function |\n    function initialize\(/g;
      next.lastIndex=start+startMarker.length;
      const match=next.exec(source);if(match)end=match.index;
    }
    if(end<=start)continue;
    return source.slice(start,end);
  }
  assert.fail(`Missing complete production region: ${startMarker} → ${endMarker}`);
}
module.exports={app,consoleWorkspace,chatWorkspace,launchWorkspace,between};
