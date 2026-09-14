import { existsSync, realpathSync } from "node:fs";
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";

export function installCompactionSettings(SettingsManager, {
  contextWindow = 0, triggerTokens = 0, memoryLimited = false,
} = {}) {
  const prototype = SettingsManager.prototype;
  const installed = Symbol.for("llm-launcher.compaction-settings");
  if (prototype[installed]) return;
  const original = prototype.getCompactionKeepRecentTokens;
  const originalSettings = prototype.getCompactionSettings;
  if (typeof original !== "function" || typeof originalSettings !== "function") {
    throw new Error("This Pi version cannot apply the launcher compaction settings.");
  }
  // Pi's 16K reserve / 20K recent-history defaults exceed small local windows.
  // Keep room for a summary and the next response without changing saved settings.
  const contextBudget = Number.isSafeInteger(contextWindow) && contextWindow > 0
    ? Math.max(1, Math.floor(contextWindow / 4)) : Infinity;
  const retentionLimit = Math.min(contextBudget, memoryLimited ? 8000 : Infinity);
  // Pi prepares compaction BEFORE calling session_before_compact. At the
  // default 20k character-estimated retention it can return nothing, even
  // when the real prompt already exceeds GPU memory. Apply the cap at the
  // settings read, including manual compaction and subsequent recoveries.
  // This adapter exists only in this launcher-owned Pi process; it
  // never writes global/project settings or modifies the installed Pi files.
  prototype.getCompactionKeepRecentTokens = function (...args) {
    return Math.min(original.apply(this, args), retentionLimit);
  };
  prototype.getCompactionSettings = function (...args) {
    const settings = originalSettings.apply(this, args);
    const summaryReserve = Math.min(settings.reserveTokens, contextBudget);
    const early = contextWindow > triggerTokens && triggerTokens > 0;
    return {
      ...settings,
      reserveTokens: early ? Math.max(summaryReserve, contextWindow - triggerTokens) : summaryReserve,
      ...(early ? {launcherSummaryReserveTokens: summaryReserve} : {}),
    };
  };
  Object.defineProperty(prototype, installed, { value: true });
}

export function prepareMemoryCompaction(event, prepareCompaction) {
  // Earlier admission must not also enlarge Pi's summary output budget:
  // native summarization derives maxTokens from reserveTokens.
  const summaryReserve = event.preparation.settings.launcherSummaryReserveTokens;
  if (Number.isFinite(summaryReserve)) {
    event.preparation.settings.reserveTokens = summaryReserve;
    delete event.preparation.settings.launcherSummaryReserveTokens;
  }
  if (!["overflow", "manual"].includes(event.reason)) return false;
  const entries = event.branchEntries || [];
  const lastAssistant = [...entries].reverse().find(e => e.type === "message" && e.message?.role === "assistant");
  const error = String(lastAssistant?.message?.errorMessage || "");
  const admissionRefused = error.includes("prefill_memory_exceeded")
    || (error.startsWith("insufficient memory: this prompt projects ") && error.includes("refused before prefill"));
  if (!admissionRefused) return false;
  const settings = event.preparation.settings;
  // Pi's normal 20k retention target uses a character estimate. Code/tool
  // messages can cost far more real tokens, leaving almost no memory headroom.
  // Recompute the native cut point (including tool pairs and file tracking),
  // rather than just changing the setting after the cut was already chosen.
  const prepared = prepareCompaction(entries, {
    ...settings, keepRecentTokens: Math.min(settings.keepRecentTokens, 8000),
  });
  if (!prepared) return false;
  Object.assign(event.preparation, prepared);
  return true;
}

export function prepareLoopCompaction(event, prepareCompaction) {
  if (event.reason !== "manual") return false;
  const entries = event.branchEntries || [];
  const marker = entries.findLastIndex(entry => entry.type === "custom_message"
    && entry.customType === "launcher-loop-stop");
  if (marker < 0 || entries.slice(marker + 1).some(entry => entry.type === "compaction"
      || (entry.type === "message" && entry.message?.role === "user"))) return false;
  // Normal retention can leave the entire failed round verbatim after the
  // summary. Let native Pi summarize it, retaining its tool/file bookkeeping
  // and the full original transcript rather than replaying the same loop.
  const prepared = prepareCompaction(entries, {...event.preparation.settings, keepRecentTokens: 0});
  if (!prepared) return false;
  Object.assign(event.preparation, prepared);
  return true;
}

export function installCompactionRecovery(AgentSession, compact, recoveryStream, onRetry = () => {}) {
  const prototype = AgentSession.prototype;
  const installed = Symbol.for('llm-launcher.compaction-recovery');
  if (prototype[installed]) return;
  const original = prototype._runDefaultCompaction;
  // Both manual and automatic compaction share this native entry point.
  // Keep persistence, cut points, file metadata, and queued-message handling
  // in Pi; intercept only the standalone summary stream in this process.
  if (typeof original !== 'function' || original.length !== 8 || compact.length !== 12) {
    throw new Error('This Pi version cannot apply the launcher compaction recovery.');
  }
  prototype._runDefaultCompaction = function (preparation, model, apiKey, headers, instructions, signal, env, reason) {
    const stream = recoveryStream(this.agent.streamFunction, onRetry);
    return compact(preparation, model, apiKey, headers, instructions, signal,
      this.thinkingLevel, stream, env, this.settingsManager.getRetrySettings(),
      this._summarizationRetryCallbacks({source: 'compaction', reason}), undefined);
  };
  Object.defineProperty(prototype, installed, {value: true});
}

// Both launcher surfaces use Pi's native compaction with the same bounded
// context settings. No commands, terminal UI overrides, or settings writes.
export default async function contextPolicy(pi) {
  const {cleanCompactionReasoning, compactionRecoveryStream} = await import(new URL('./pi_context_recovery.js', import.meta.url).href);
  const entryDir = dirname(realpathSync(process.argv[1]));
  const dist = existsSync(join(entryDir, "core/compaction/compaction.js")) ? entryDir : dirname(entryDir);
  // Pi's bundled CLI and this adapter must share the SettingsManager prototype.
  const { SettingsManager, AgentSession, compact } = await import(pathToFileURL(join(entryDir, "index.js")).href);
  const { prepareCompaction } = await import(pathToFileURL(join(dist, "core/compaction/compaction.js")).href);
  const provider = JSON.parse(process.env.LLM_LAUNCHER_PI_PROVIDER || "{}");
  let compactionUI;
  // The 4K housekeeping cap belongs to oMLX/MTPLX. Keep other supported
  // transports (including preserved Pi 0.84.2 for Uzu) on their native path.
  if (provider.compactionRecovery) {
    installCompactionRecovery(AgentSession, compact, compactionRecoveryStream, () => {
      compactionUI?.notify('The checkpoint was incomplete. Retrying once with a shorter summary; the conversation stays saved.', 'info');
    });
  }
  // Honour the selected window. Native engine admission handles actual memory
  // pressure; a model-name-based ceiling silently discards usable context.
  installCompactionSettings(SettingsManager, {
    contextWindow: provider.model?.contextWindow || 0,
    memoryLimited: Boolean(provider.memoryCompaction),
  });
  pi.on("session_before_compact", (event, ctx) => {
    compactionUI = ctx.ui;
    if (prepareLoopCompaction(event, prepareCompaction)) {
      ctx.ui.notify("Creating a clean handover from the stalled turn. The original conversation stays saved.", "info");
    }
    cleanCompactionReasoning(event.preparation);
  });
  if (provider.memoryCompaction) {
    pi.on("session_before_compact", (event, ctx) => {
      if (prepareMemoryCompaction(event, prepareCompaction)) {
        ctx.ui.notify("Freeing extra room for the next steps: summarising more older work while keeping recent messages and file references.", "info");
      }
      cleanCompactionReasoning(event.preparation);
    });
  }
}
