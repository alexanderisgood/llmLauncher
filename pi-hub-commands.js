import { existsSync, realpathSync } from "node:fs";
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";

// RPC deliberately omits terminal custom components. Render their text and
// deliver browser key events through Pi's supported, cancellable input dialog.
export function installCustomUI(ui, keybindings) {
  if (ui.__launcherCustomUI) return;
  ui.__launcherCustomUI = true;
  let active = false;
  ui.custom = async factory => {
    if (active) throw new Error("Close the current Pi menu first.");
    active = true;
    let component, finished = false, result, waiting;
    const done = value => { result = value; finished = true; waiting?.abort(); };
    const render = () => {
      if (!component || finished) return;
      const lines = component.render(90);
      ui.setStatus("launcher.customUI", lines.join("\n").slice(0, 24000));
    };
    const tui = {
      terminal: { columns: 90, rows: 24 }, requestRender: render,
      requestFullRender: render, setFocus() {},
    };
    try {
      component = await factory(tui, ui.theme, keybindings, done);
      if (!component || typeof component.render !== "function") return result;
      while (!finished) {
        render();
        waiting = new AbortController();
        const key = await ui.input("__launcher_custom_ui__", "", { signal: waiting.signal });
        waiting = undefined;
        if (finished) break;
        if (key === undefined) { done(undefined); break; }
        await component.handleInput?.(key);
      }
      return result;
    } finally {
      finished = true;
      waiting?.abort();
      component?.dispose?.();
      ui.setStatus("launcher.customUI", undefined);
      active = false;
    }
  };
}

export default async function hubCommands(pi) {
  const entryDir = dirname(realpathSync(process.argv[1]));
  const dist = existsSync(join(entryDir, "core/keybindings.js")) ? entryDir : dirname(entryDir);
  // Pi 0.85 publishes a bundled executable. Use its shared exports for
  // classes we patch so the adapter and running agent share one prototype.
  const shared = await import(pathToFileURL(join(entryDir, "index.js")).href);
  const { KeybindingsManager } = await import(pathToFileURL(join(dist, "core/keybindings.js")).href);
  const { SessionManager } = shared;
  pi.on("session_start", (_event, ctx) => installCustomUI(ctx.ui, KeybindingsManager.create()));
  const register = (name, description, handler) => pi.registerCommand(name, { description, handler });
  const idle = ctx => { if (!ctx.isIdle()) throw new Error("Stop the current response before changing the session."); };
  const historyChanged = ctx => ctx.ui.setStatus("launcher.historyChanged", "refresh");
  register("help", "List available Hub, extension, prompt and skill commands", async (_args, ctx) => {
    ctx.ui.notify(pi.getCommands().map(c => `/${c.name} — ${c.description || ""}`).join("\n"), "info");
  });
  register("session", "Show this session and its context usage", async (_args, ctx) => {
    const usage = ctx.getContextUsage();
    ctx.ui.notify([
      pi.getSessionName() || "Unnamed session", ctx.sessionManager.getSessionFile() || "Unsaved session",
      `Model: ${ctx.model?.id || "Unknown"}`,
      usage ? `Context: ${usage.tokens ?? "recalculating"} / ${usage.contextWindow} tokens (${usage.percent?.toFixed(1) ?? "?"}%)` : "Context: not measured yet",
    ].join("\n"), "info");
  });
  register("name", "Rename this session", async (args, ctx) => {
    const name = args.trim() || await ctx.ui.input("Session name");
    if (name?.trim()) { pi.setSessionName(name.trim()); ctx.ui.notify(`Session named ${name.trim()}`, "info"); }
  });
  register("new", "Start a fresh Pi conversation", async (_args, ctx) => {
    idle(ctx);
    await ctx.newSession({ withSession: async fresh => {
      historyChanged(fresh); fresh.ui.notify("New session started.", "info");
    } });
  });
  register("compact", "Summarise older messages to free context", async (args, ctx) => {
    idle(ctx);
    await new Promise((resolve, reject) => ctx.compact({ customInstructions: args || undefined, onComplete: resolve, onError: reject }));
  });
  register("reload", "Reload Pi extensions, prompts and skills", async (_args, ctx) => { idle(ctx); await ctx.reload(); });
  register("resume", "Choose a saved Pi session for this project", async (_args, ctx) => {
    idle(ctx);
    const sessions = await SessionManager.list(ctx.cwd, ctx.sessionManager.getSessionDir());
    const options = sessions.slice(0, 100).map((s, i) => `${i + 1}. ${s.name || s.firstMessage || s.id}`.slice(0, 490));
    const choice = await ctx.ui.select("Resume session", options);
    const index = options.indexOf(choice);
    if (index >= 0) await ctx.switchSession(sessions[index].path, { withSession: async fresh => historyChanged(fresh) });
  });
  register("fork", "Branch from an earlier user message", async (_args, ctx) => {
    idle(ctx);
    const entries = ctx.sessionManager.getBranch().filter(e => e.type === "message" && e.message.role === "user").slice(-100);
    const options = entries.map((e, i) => `${i + 1}. ${typeof e.message.content === "string" ? e.message.content : e.message.content.filter(b => b.type === "text").map(b => b.text).join(" ")}`.slice(0, 490));
    const choice = await ctx.ui.select("Fork from message", options);
    const index = options.indexOf(choice);
    if (index >= 0) await ctx.fork(entries[index].id, { withSession: async fresh => historyChanged(fresh) });
  });
  register("tree", "Navigate to another point in the conversation", async (_args, ctx) => {
    idle(ctx);
    const entries = ctx.sessionManager.getEntries().filter(e => e.type === "message").slice(-100);
    const options = entries.map((e, i) => {
      const content = e.message.content;
      const text = typeof content === "string" ? content : (content || []).filter(b => b.type === "text").map(b => b.text).join(" ");
      return `${i + 1}. ${e.message.role}: ${text || "[tool or thinking]"}`.slice(0, 490);
    });
    const choice = await ctx.ui.select("Conversation tree · recent entries", options);
    const index = options.indexOf(choice);
    if (index >= 0 && !(await ctx.navigateTree(entries[index].id)).cancelled) historyChanged(ctx);
  });
  register("hotkeys", "Show Hub command and menu keyboard controls", async (_args, ctx) => {
    ctx.ui.notify("Type / to browse commands. Tab or ↓ focuses the command list. Enter chooses a command; Enter again runs it. In extension menus use ↑ ↓ ← →, Enter, typing, and Escape. Cancel closes the menu.", "info");
  });
  register("thinking", "Choose the reasoning level for this session", async (args, ctx) => {
    idle(ctx);
    const levels = ["off", "minimal", "low", "medium", "high", "xhigh"];
    const level = args.trim() || await ctx.ui.select("Thinking level", levels);
    if (level === undefined) return;
    if (!levels.includes(level)) throw new Error(`Choose ${levels.join(", ")}.`);
    pi.setThinkingLevel(level);
    ctx.ui.notify(`Thinking: ${pi.getThinkingLevel()}`, "info");
  });
  register("settings", "Choose Hub session settings or open extension settings", async (_args, ctx) => {
    const choice = await ctx.ui.select("Session settings", ["Thinking level", "Model and engine", "Extension commands"]);
    if (choice === "Thinking level") {
      idle(ctx);
      const level = await ctx.ui.select("Thinking level", ["off", "minimal", "low", "medium", "high", "xhigh"]);
      if (level) pi.setThinkingLevel(level);
    } else if (choice === "Model and engine") ctx.ui.notify("Use the launcher's model and engine picker to change this local route.", "info");
    else if (choice) ctx.ui.notify("Type / to find your installed extensions, including their settings commands.", "info");
  });
  register("model", "Show the local model and how to change engines", async (_args, ctx) => {
    ctx.ui.notify(`Current model: ${ctx.model?.id || "Unknown"}. Use the launcher's model and engine picker to change this local route.`, "info");
  });
  register("quit", "Close this Pi agent", async (_args, ctx) => { idle(ctx); ctx.shutdown(); });
}
