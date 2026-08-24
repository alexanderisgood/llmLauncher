import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

const STATUS_ID = "ox-alpha-auto-continue";
const TARGET_PROVIDER = "openrouter";
const TARGET_MODEL = "stealth/ox-alpha";
const CONTINUE_MESSAGE = "continue";

// Give the user a moment to intervene after Ox Alpha genuinely settles.
const SETTLED_DELAY_MS = 5_000;
// Recover a provider stream that is truly silent. Active tools are never timed out.
const STALL_TIMEOUT_MS = 3 * 60_000;
// Prevent an unattended completed-task loop from running forever.
const MAX_AUTOMATIC_CONTINUES = 25;

type Timer = ReturnType<typeof setTimeout>;
type StopReason = "pending" | "stop" | "length" | "toolUse" | "error" | "aborted" | "deferred";

function isOxAlpha(ctx: ExtensionContext): boolean {
	return ctx.model?.provider === TARGET_PROVIDER && ctx.model?.id === TARGET_MODEL;
}

export default function oxAlphaAutoContinue(pi: ExtensionAPI) {
	let enabled = true;
	let shuttingDown = false;
	let agentRunning = false;
	let automaticContinues = 0;
	let lastStopReason: StopReason | undefined;
	let lastError = "";
	let settledTimer: Timer | undefined;
	let watchdogTimer: Timer | undefined;
	const activeTools = new Set<string>();

	function clearSettledTimer(): void {
		if (settledTimer !== undefined) clearTimeout(settledTimer);
		settledTimer = undefined;
	}

	function clearWatchdog(): void {
		if (watchdogTimer !== undefined) clearTimeout(watchdogTimer);
		watchdogTimer = undefined;
	}

	function clearTimers(): void {
		clearSettledTimer();
		clearWatchdog();
	}

	function statusText(ctx: ExtensionContext): string | undefined {
		if (!isOxAlpha(ctx)) return undefined;
		if (!enabled) return "Ox auto: off";
		if (automaticContinues >= MAX_AUTOMATIC_CONTINUES) return "Ox auto: limit reached";
		return `Ox auto: on · ${automaticContinues}/${MAX_AUTOMATIC_CONTINUES}`;
	}

	function renderStatus(ctx: ExtensionContext): void {
		ctx.ui.setStatus(STATUS_ID, statusText(ctx));
	}

	function pause(ctx: ExtensionContext, message: string): void {
		enabled = false;
		clearTimers();
		renderStatus(ctx);
		if (ctx.hasUI) ctx.ui.notify(message, "warning");
	}

	function atLimit(ctx: ExtensionContext): boolean {
		if (automaticContinues < MAX_AUTOMATIC_CONTINUES) return false;
		pause(
			ctx,
			`Ox Alpha auto-continue paused after ${MAX_AUTOMATIC_CONTINUES} automatic messages. `
				+ "Use /ox-auto reset to start another bounded run.",
		);
		return true;
	}

	function sendContinue(ctx: ExtensionContext, reason: "settled" | "stalled"): void {
		if (shuttingDown || !enabled || !isOxAlpha(ctx) || atLimit(ctx)) return;
		automaticContinues += 1;
		renderStatus(ctx);
		if (ctx.hasUI) {
			ctx.ui.notify(
				reason === "stalled"
					? `Ox Alpha was silent for ${STALL_TIMEOUT_MS / 60_000} minutes; interrupted the stalled request and queued “${CONTINUE_MESSAGE}” (${automaticContinues}/${MAX_AUTOMATIC_CONTINUES}).`
					: `Ox Alpha settled; sending “${CONTINUE_MESSAGE}” (${automaticContinues}/${MAX_AUTOMATIC_CONTINUES}).`,
				"info",
			);
		}
		if (reason === "stalled") {
			// Queue first so Pi owns the hand-off, then abort only the silent request.
			pi.sendUserMessage(CONTINUE_MESSAGE, { deliverAs: "followUp" });
			ctx.abort();
			return;
		}
		pi.sendUserMessage(CONTINUE_MESSAGE);
	}

	function armWatchdog(ctx: ExtensionContext): void {
		clearWatchdog();
		if (shuttingDown || !enabled || !agentRunning || !isOxAlpha(ctx)) return;
		watchdogTimer = setTimeout(() => {
			watchdogTimer = undefined;
			if (shuttingDown || !enabled || !agentRunning || !isOxAlpha(ctx)) return;
			if (ctx.isIdle()) return;
			if (activeTools.size > 0) {
				// Long builds and tests are legitimate work, even without terminal updates.
				armWatchdog(ctx);
				return;
			}
			sendContinue(ctx, "stalled");
		}, STALL_TIMEOUT_MS);
	}

	function noteActivity(ctx: ExtensionContext): void {
		if (agentRunning) armWatchdog(ctx);
	}

	pi.registerCommand("ox-auto", {
		description: "Control Ox Alpha auto-continue: on, off, status, or reset",
		handler: async (args, ctx) => {
			const action = args.trim().toLowerCase() || "status";
			if (action === "on") {
				enabled = true;
				shuttingDown = false;
				if (agentRunning) armWatchdog(ctx);
				renderStatus(ctx);
				ctx.ui.notify(
					isOxAlpha(ctx)
						? "Ox Alpha auto-continue is on."
						: `Auto-continue is armed but paused until ${TARGET_PROVIDER}/${TARGET_MODEL} is selected.`,
					"info",
				);
				return;
			}
			if (action === "off") {
				enabled = false;
				clearTimers();
				renderStatus(ctx);
				ctx.ui.notify("Ox Alpha auto-continue is off.", "info");
				return;
			}
			if (action === "reset") {
				automaticContinues = 0;
				enabled = true;
				shuttingDown = false;
				if (agentRunning) armWatchdog(ctx);
				renderStatus(ctx);
				ctx.ui.notify("Ox Alpha auto-continue counter reset and enabled.", "info");
				return;
			}
			if (action === "status") {
				ctx.ui.notify(
					`${enabled ? "On" : "Off"}; ${automaticContinues}/${MAX_AUTOMATIC_CONTINUES} automatic continuations used. `
						+ `Target: ${TARGET_PROVIDER}/${TARGET_MODEL}. Settled delay: ${SETTLED_DELAY_MS / 1_000}s. `
						+ `Silent-stream watchdog: ${STALL_TIMEOUT_MS / 60_000}m; active tools are exempt.`,
					"info",
				);
				return;
			}
			ctx.ui.notify("Usage: /ox-auto on | off | status | reset", "warning");
		},
	});

	pi.on("session_start", (_event, ctx) => {
		shuttingDown = false;
		agentRunning = false;
		automaticContinues = 0;
		lastStopReason = undefined;
		lastError = "";
		activeTools.clear();
		clearTimers();
		renderStatus(ctx);
		if (ctx.hasUI && isOxAlpha(ctx)) {
			ctx.ui.notify(
				`Ox Alpha auto-continue is on: “${CONTINUE_MESSAGE}” after ${SETTLED_DELAY_MS / 1_000}s idle, `
					+ `${STALL_TIMEOUT_MS / 60_000}m silent-stream recovery, cap ${MAX_AUTOMATIC_CONTINUES}. `
					+ "Use /ox-auto off to stop it.",
				"info",
			);
		}
	});

	pi.on("session_shutdown", (_event, ctx) => {
		shuttingDown = true;
		agentRunning = false;
		activeTools.clear();
		clearTimers();
		ctx.ui.setStatus(STATUS_ID, undefined);
	});

	pi.on("model_select", (_event, ctx) => {
		clearTimers();
		activeTools.clear();
		agentRunning = false;
		lastStopReason = undefined;
		lastError = "";
		renderStatus(ctx);
	});

	pi.on("input", (event, ctx) => {
		if (event.source !== "extension") {
			// A real user instruction supersedes any delayed automatic message.
			clearSettledTimer();
			automaticContinues = 0;
			renderStatus(ctx);
		}
	});

	pi.on("agent_start", (_event, ctx) => {
		clearSettledTimer();
		agentRunning = true;
		lastStopReason = undefined;
		lastError = "";
		activeTools.clear();
		armWatchdog(ctx);
	});

	pi.on("turn_start", (_event, ctx) => noteActivity(ctx));
	pi.on("message_update", (_event, ctx) => noteActivity(ctx));
	pi.on("after_provider_response", (_event, ctx) => noteActivity(ctx));

	pi.on("tool_execution_start", (event, ctx) => {
		activeTools.add(event.toolCallId);
		noteActivity(ctx);
	});
	pi.on("tool_execution_update", (_event, ctx) => noteActivity(ctx));
	pi.on("tool_execution_end", (event, ctx) => {
		activeTools.delete(event.toolCallId);
		noteActivity(ctx);
	});

	pi.on("message_end", (event) => {
		if (event.message.role !== "assistant") return;
		lastStopReason = event.message.stopReason as StopReason;
		lastError = event.message.errorMessage || "";
	});

	pi.on("agent_settled", (_event, ctx) => {
		agentRunning = false;
		activeTools.clear();
		clearWatchdog();
		if (shuttingDown || !enabled || !isOxAlpha(ctx) || ctx.hasPendingMessages()) return;
		if (lastStopReason === "error" || lastStopReason === "aborted" || lastStopReason === "deferred") {
			pause(
				ctx,
				`Ox Alpha auto-continue paused after ${lastStopReason}${lastError ? `: ${lastError}` : "."} `
					+ "Use /ox-auto on after resolving the provider issue.",
			);
			return;
		}
		if (atLimit(ctx)) return;
		clearSettledTimer();
		settledTimer = setTimeout(() => {
			settledTimer = undefined;
			if (
				shuttingDown || !enabled || !isOxAlpha(ctx)
				|| !ctx.isIdle() || ctx.hasPendingMessages()
			) return;
			sendContinue(ctx, "settled");
		}, SETTLED_DELAY_MS);
	});
}
