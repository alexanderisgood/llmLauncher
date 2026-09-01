/** Session-scoped Pi provider. Nothing is written to ~/.pi. */
function assistantOutputState(message) {
  const content = message?.content;
  const blocks = Array.isArray(content) ? content : [];
  const text = typeof content === "string"
    ? content
    : blocks.filter(block => block?.type === "text").map(block => block.text || "").join("");
  const thinking = blocks
    .filter(block => block?.type === "thinking")
    .map(block => block.thinking || block.text || "")
    .join("");
  const toolCalls = blocks.some(block => block?.type === "toolCall" || block?.type === "tool_call");
  return {
    hasFinalOutput:Boolean(String(text || "").trim()) || toolCalls,
    hasThinking:Boolean(String(thinking || "").trim()),
  };
}

export default function launcherProvider(pi) {
  const raw = process.env.LLM_LAUNCHER_PI_PROVIDER;
  if (!raw) throw new Error("LLM Launcher provider data is missing");
  const data = JSON.parse(raw);
  const model = data.model;
  pi.on("before_provider_headers", (event, ctx) => {
    const headers = event?.headers;
    if (!headers || typeof headers !== "object") return;
    const client = Object.entries(headers).find(
      ([key]) => key.toLowerCase() === "x-mtplx-client",
    )?.[1];
    if (client !== "pi") return;
    event.headers["x-mtplx-session-id"] = String(
      ctx.sessionManager.getSessionId(),
    );
  });
  pi.registerProvider(data.id, {
    name: data.name,
    baseUrl: data.baseUrl,
    apiKey: data.apiKey || "local",
    headers: data.headers || {},
    authHeader: true,
    api: "openai-completions",
    models: [{
      id: model.id,
      name: model.name,
      reasoning: Boolean(model.reasoning),
      ...(model.thinkingLevelMap ? { thinkingLevelMap: model.thinkingLevelMap } : {}),
      input: ["text"],
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      contextWindow: model.contextWindow,
      maxTokens: model.maxTokens,
      compat: {
        supportsDeveloperRole: false,
        supportsReasoningEffort: Boolean(model.supportsReasoningEffort),
        supportsUsageInStreaming: true,
        maxTokensField: "max_tokens"
      }
    }]
  });
  pi.on("message_end", (event, ctx) => {
    const message = event?.message;
    if (message?.role !== "assistant") return;
    if (!ctx?.hasUI || typeof ctx.ui?.notify !== "function") return;
    if (message.stopReason === "length") {
      ctx.ui.notify(
        "The model used the complete response allowance before it finished. Send “continue” to resume this task, or raise Max response before launching the next hard task.",
        "warning",
      );
      return;
    }
    const output = assistantOutputState(message);
    if (output.hasThinking && !output.hasFinalOutput) {
      ctx.ui.notify(
        "The model finished its reasoning without a final response. Send “continue” to resume; queued follow-ups stay paused until Pi returns an answer.",
        "warning",
      );
    }
  });
}
