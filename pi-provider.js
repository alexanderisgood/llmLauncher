/** Session-scoped Pi provider. Nothing is written to ~/.pi. */
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
      input: ["text"],
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      contextWindow: model.contextWindow,
      maxTokens: model.maxTokens,
      compat: {
        supportsDeveloperRole: false,
        supportsReasoningEffort: false,
        supportsUsageInStreaming: true,
        maxTokensField: "max_tokens"
      }
    }]
  });
}
