/** Session-scoped oh-my-pi provider. No persistent model configuration. */
import {isAbsolute, resolve} from "node:path";

async function loadNativeSessionManager() {
  const {SessionManager} = await import("@oh-my-pi/pi-coding-agent");
  return SessionManager;
}

function optionText(value, limit) {
  return typeof value === "string"
    ? value.replace(/[\x00-\x1f\x7f-\x9f]/g, " ").replace(/\s+/g, " ").trim().slice(0, limit)
    : "";
}

function sessionTime(session) {
  for (const value of [session.modified, session.created]) {
    if (value === undefined || value === null) continue;
    const date = new Date(value);
    if (Number.isFinite(date.getTime())) return `${date.toISOString().slice(0, 16).replace("T", " ")} UTC`;
  }
  return "Unknown date";
}

export function createResumeHandler({loadSessionManager = loadNativeSessionManager} = {}) {
  return async (_args, ctx) => {
    // The launcher consumes this only after this command's correlated response.
    // Clearing it also makes a cancelled second picker unable to reuse a choice.
    ctx.ui.setStatus("launcher.resumeSession", undefined);
    const SessionManager = await loadSessionManager();
    const sessions = await SessionManager.listForPicker(ctx.cwd, ctx.sessionManager.getSessionDir());
    const current = ctx.sessionManager.getSessionFile();
    const currentPath = typeof current === "string" && current ? resolve(current) : "";
    const seen = new Set();
    const choices = [];
    for (const session of sessions) {
      if (!session || typeof session.path !== "string" || !isAbsolute(session.path)
          || session.path.length > 4096 || /[\x00-\x1f\x7f]/.test(session.path)) continue;
      const path = resolve(session.path);
      if (path === currentPath || seen.has(path)) continue;
      seen.add(path);
      const title = optionText(session.title, 100) || optionText(session.firstMessage, 100)
        || optionText(session.id, 100) || "Untitled conversation";
      choices.push({path, label: `${choices.length + 1}. ${title} · ${sessionTime(session)}`});
      if (choices.length === 100) break;
    }
    if (!choices.length) {
      ctx.ui.notify("No other saved OMP conversations in this project.", "info");
      return;
    }
    const selected = await ctx.ui.select("Resume an OMP conversation", choices.map(choice => choice.label));
    if (selected === undefined || selected === null) return;
    const choice = choices.find(item => item.label === selected);
    if (!choice) throw new Error("The selected OMP conversation is no longer in this picker.");
    // Native switch_session with the current provider/model override is owned by
    // the launcher. CommandContext.switchSession would restore a historical model.
    ctx.ui.setStatus("launcher.resumeSession", JSON.stringify({sessionPath: choice.path}));
  };
}

export default function launcherOMPProvider(omp) {
  const raw = process.env.LLM_LAUNCHER_OMP_PROVIDER;
  if (!raw) throw new Error("LLM Launcher oh-my-pi provider data is missing");
  const data = JSON.parse(raw);
  const url = new URL(data.baseUrl);
  if (url.protocol !== "http:" || url.hostname !== "127.0.0.1" || !url.port
      || url.pathname !== "/v1" || url.username || url.password || url.search || url.hash
      || !/^launcher-[a-z0-9-]+$/.test(data.id) || !Array.isArray(data.models)
      || data.models.length !== 1) {
    throw new Error("Invalid local oh-my-pi provider contract");
  }
  const {id, ...provider} = data;
  omp.registerProvider(id, provider);
  if (process.env.LLM_LAUNCHER_AGENT_HOST === "console") {
    omp.registerCommand("resume", {
      description: "Resume a saved OMP conversation in this project",
      handler: createResumeHandler(),
    });
  }
}
