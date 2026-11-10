from __future__ import annotations

def client_route(plan: LaunchPlan) -> ClientRoute:
    client_port = plan.client_port or plan.port
    return ClientRoute(
        provider=f"launcher-{plan.backend}-{plan.run_id[:8]}",
        served=str(plan.model["servedId"]),
        base_url=f"http://127.0.0.1:{client_port}/v1",
        api_key=plan.secrets.get("clientApiKey") or plan.secrets.get("apiKey", "local"),
    )

def build_chat_client(plan: LaunchPlan, _route: ClientRoute) -> None:
    if plan.purpose in {"benchmark", "route-check"}:
        plan.client_argv = []
        plan.client_env = {}
        plan.warnings.append(
            "This private check uses generated local prompts and does not open a work surface or save response text."
            if plan.purpose == "route-check" else
            "Benchmark Lab uses generated local prompts and does not open an agent or save response text."
        )
    else:
        plan.client_argv = []
        plan.client_env = {}
        plan.warnings.append(
            "Built-in chat streams through the launcher's private loopback route and enforces the visible response ceiling."
        )

def pi_model_identity(plan: LaunchPlan) -> tuple[str, str]:
    # Pi compares provider + model + API before retaining reasoning blocks.
    # A process/run ID is transport identity, not a different AI model.
    artifact_path = str(plan.model.get("path") or "")
    artifact = (model_artifact_fingerprint(Path(artifact_path), read_json(Path(artifact_path) / "config.json"))
                if artifact_path and Path(artifact_path).is_dir() else "")
    pi_identity = hashlib.sha256(json.dumps(
        [plan.backend, artifact_path, artifact, plan.model.get("id") or plan.model.get("name")],
        separators=(",", ":"),
    ).encode()).hexdigest()[:24]
    return f"launcher-{plan.backend}-{pi_identity}", f"local-{pi_identity}"

def pi_browser_test_module(project: str) -> str | None:
    """Advertise existing browser tooling; never install it during launch."""
    candidates = [
        Path(project) / "node_modules" / "playwright",
        Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright",
        Path("/opt/homebrew/lib/node_modules/playwright"),
        Path("/usr/local/lib/node_modules/playwright"),
    ]
    for candidate in candidates:
        if (candidate / "index.js").is_file() and read_json(candidate / "package.json").get("name") == "playwright":
            return str(candidate.resolve())
    return None

def selected_pi_binary(plan: LaunchPlan) -> str | None:
    pi_binary = BINARIES.get("pi")
    if plan.backend == "uzu" and command_version(pi_binary) != UZU_PI_TESTED_VERSION:
        preserved = STATE_DIR / "runtimes" / "pi-uzu-0.84.2" / "node_modules" / ".bin" / "pi"
        if not preserved.is_file() or command_version(str(preserved)) != UZU_PI_TESTED_VERSION:
            raise ValueError("The installed Pi version changed; Uzu requires its tested Pi 0.84.2 transport and the preserved runtime is unavailable.")
        pi_binary = str(preserved)
    return pi_binary

def build_pi_client(plan: LaunchPlan, route: ClientRoute) -> None:
    pi_binary = selected_pi_binary(plan)
    request_headers = {"x-mtplx-client": "pi"} if plan.backend == "mtplx" else {}
    pi_provider, pi_model = pi_model_identity(plan)
    runtime_version = command_version(plan.runtime_binary or BINARIES.get("mtplx")) if plan.backend == "mtplx" else ""
    model_path = str(plan.model.get("path") or "")
    prepare_mtplx_image_processor(plan.backend, runtime_version, model_path)
    model_contract: dict[str, Any] = {
        "id": pi_model,
        "name": plan.model["name"],
        "reasoning": plan.reasoning != "off",
        "contextWindow": plan.context,
        "maxTokens": plan.output,
        "input": pi_model_inputs(
            plan.backend, runtime_version, model_path,
        ),
    }
    if plan.backend in {"whallm", "splash", "kolibri"}:
        allowed = set(
            plan.model.get("backends", {}).get(plan.backend, {}).get("agentReasoning") or []
        )
        model_contract.update({
            "supportsReasoningEffort": True,
            "thinkingLevelMap": {
                level: ("none" if level == "off" else level) if level in allowed else None
                for level in ("off", "minimal", "low", "medium", "high", "xhigh", "max")
            },
        })
    provider_data = {
        "id": pi_provider,
        "transportModel": route.served,
        "name": f"LLM Launcher · {plan.backend}",
        "baseUrl": route.base_url,
        "apiKey": route.api_key,
        "headers": request_headers,
        "model": model_contract,
    }
    if plan.backend in {"omlx", "mtplx"}:
        provider_data["memoryCompaction"] = True
    if plan.backend in {"omlx", "mtplx", "splash", "kolibri"}:
        provider_data["compactionRecovery"] = True
    browser_module = pi_browser_test_module(plan.project)
    if browser_module:
        provider_data["browserTestModule"] = browser_module
        if plan.run_dir:
            provider_data["browserArtifactDir"] = str(plan.run_dir / "browser")
    plan.client_env["LLM_LAUNCHER_PI_PROVIDER"] = json.dumps(provider_data, separators=(",", ":"))
    plan.client_argv = [
        pi_binary,
        "--extension", str(APP_DIR / "pi-provider.js"),
        "--extension", str(APP_DIR / "pi-context-policy.js"),
        "--extension", str(APP_DIR / "pi-workflow.js"),
        "--provider", pi_provider, "--model", pi_model,
    ]
    if plan.pi_session_file:
        plan.client_argv.extend(["--session", validated_pi_session_file(plan.pi_session_file, plan.project)])
    if plan.agent_host == "console":
        # Hub Console owns the UI, so consume Pi's supported append-only JSONL
        # protocol instead of attempting to reconstruct its redraw-based TUI.
        plan.client_argv.extend(["--extension", str(APP_DIR / "pi-hub-commands.js"), "--mode", "rpc"])
    if plan.reasoning != "auto":
        plan.client_argv.extend(["--thinking", plan.reasoning])

def _require_omp_console_support(client: str, agent_host: str) -> None:
    if client == "omp" and agent_host == "console" and not omp_runtime.console_supported(command_version(BINARIES.get("omp"))):
        raise ValueError(f"oh-my-pi Hub Console is verified for {omp_runtime.TESTED_RPC_VERSION}. Choose Terminal for this installed version.")

def build_omp_client(plan: LaunchPlan, route: ClientRoute) -> None:
    binary = BINARIES.get("omp")
    if not binary:
        raise ValueError("oh-my-pi is not installed. Install omp and rescan runtimes.")
    _require_omp_console_support(plan.client, plan.agent_host)
    runtime_version = command_version(plan.runtime_binary or BINARIES.get("mtplx")) if plan.backend == "mtplx" else ""
    model_path = str(plan.model.get("path") or "")
    prepare_mtplx_image_processor(plan.backend, runtime_version, model_path)
    provider, _model = pi_model_identity(plan)
    omp_runtime.build_client(
        plan, route, binary=binary, app_dir=APP_DIR, provider=provider,
        inputs=pi_model_inputs(plan.backend, runtime_version, model_path),
        console_verified=omp_runtime.console_supported(command_version(binary)),
    )

def build_opencode_client(plan: LaunchPlan, route: ClientRoute) -> None:
    request_headers = {"x-mtplx-client": "opencode"} if plan.backend == "mtplx" else {}
    plugins: list[str] = []
    if plan.backend == "mtplx":
        assert plan.run_dir
        plugin_path = plan.run_dir / "mtplx-opencode-session.js"
        plugin_path.write_text(
            "const providerID = " + json.dumps(route.provider) + ";\n"
            "export const LLMLauncherMTPLXSession = async () => ({\n"
            "  'chat.headers': async (input, output) => {\n"
            "    const active = input?.model?.providerID || input?.provider?.id;\n"
            "    if (active !== providerID) return;\n"
            "    output.headers ||= {};\n"
            "    output.headers['x-mtplx-client'] = 'opencode';\n"
            "    if (input?.sessionID) output.headers['x-mtplx-session-id'] = String(input.sessionID);\n"
            "  }\n"
            "});\n"
            "export default LLMLauncherMTPLXSession;\n",
            encoding="utf-8",
        )
        plugin_path.chmod(0o600)
        plugins.append(plugin_path.as_uri())
    major = 1
    try:
        text = command_version(BINARIES["opencode"])
        major = int(re.search(r"(\d+)", text).group(1)) if re.search(r"(\d+)", text) else 1
    except (ValueError, AttributeError):
        pass
    if major >= 2:
        overlay = {"providers": {route.provider: {"name": f"LLM Launcher · {plan.backend}", "package": "@opencode-ai/ai/providers/openai-compatible", "settings": {"baseURL": route.base_url, "apiKey": route.api_key, "headers": request_headers}, "models": {route.served: {"name": plan.model["name"], "limit": {"context": plan.context, "output": plan.output}, "capabilities": {"tools": True, "input": ["text"], "output": ["text"]}}}}}, "model": f"{route.provider}/{route.served}"}
    else:
        overlay = {"$schema": "https://opencode.ai/config.json", "provider": {route.provider: {"npm": "@ai-sdk/openai-compatible", "name": f"LLM Launcher · {plan.backend}", "options": {"baseURL": route.base_url, "apiKey": route.api_key, "headers": request_headers}, "models": {route.served: {"name": plan.model["name"], "modalities": {"input": ["text"], "output": ["text"]}, "limit": {"context": plan.context, "output": plan.output}}}}}, "model": f"{route.provider}/{route.served}"}
    if major < 2:
        model_settings = overlay["provider"][route.provider]["models"][route.served]
        # Session-specific local IDs have no catalog capability metadata.
        model_settings.update(tool_call=True, reasoning=plan.reasoning != "off")
        if plan.backend == "mtplx" and plan.reasoning != "off":
            model_settings["interleaved"] = {"field": "reasoning_content"}
    if plugins:
        overlay["plugin"] = plugins
    plan.client_env["OPENCODE_CONFIG_CONTENT"] = json.dumps(overlay, separators=(",", ":"))
    plan.client_argv = [BINARIES["opencode"], plan.project, "--model", f"{route.provider}/{route.served}"]

def build_codex_client(plan: LaunchPlan, route: ClientRoute) -> None:
    allowed_reasoning = list(plan.model["backends"][plan.backend].get("codexReasoning") or ["auto"])
    if plan.reasoning not in allowed_reasoning:
        choices = ", ".join(allowed_reasoning)
        raise ValueError(f"This model/runtime supports these Codex reasoning choices: {choices}.")
    if plan.output < 1_024:
        raise ValueError("Codex local-model sessions need a response limit of at least 1,024 tokens.")
    # Command-line config layers are session-only: they preserve the
    # user's ~/.codex/config.toml, skills, plugins, permissions, and MCPs.
    codex_provider = f"launcher_{plan.backend}_{plan.run_id[:8].replace('-', '_')}"

    def config(key: str, value: Any) -> list[str]:
        rendered = json.dumps(value, separators=(",", ":")) if isinstance(value, (str, bool)) else str(value)
        return ["-c", f"{key}={rendered}"]

    client_key = str(plan.secrets.get("clientApiKey") or secrets.token_urlsafe(32))
    plan.secrets["clientApiKey"] = client_key
    plan.client_env["LLM_LAUNCHER_CODEX_API_KEY"] = client_key
    plan.client_argv = [BINARIES["codex"], "-C", plan.project, "--model", route.served]
    plan.client_argv += config("model_provider", codex_provider)
    plan.client_argv += config(f"model_providers.{codex_provider}.name", f"LLM Launcher · {plan.backend}")
    plan.client_argv += config(f"model_providers.{codex_provider}.base_url", route.base_url)
    plan.client_argv += config(f"model_providers.{codex_provider}.env_key", "LLM_LAUNCHER_CODEX_API_KEY")
    plan.client_argv += config(f"model_providers.{codex_provider}.requires_openai_auth", False)
    plan.client_argv += config(f"model_providers.{codex_provider}.wire_api", "responses")
    plan.client_argv += config(f"model_providers.{codex_provider}.supports_websockets", False)
    # Hosted web search is a server-side Responses tool. Local runtimes cannot
    # execute it, while Codex's own local/MCP tools remain available.
    plan.client_argv += config("web_search", "disabled")
    plan.client_argv += config("model_supports_reasoning_summaries", plan.reasoning != "off")
    if plan.backend == "mtplx":
        # MTPLX has no /responses/compact route. Codex retains its local
        # compaction path under the visible context/output contract.
        plan.client_argv += config("features.remote_compaction_v2", False)
    plan.client_argv += config("model_context_window", plan.context)
    compact_at = min(int(plan.context * 0.9), plan.context - plan.output)
    plan.client_argv += config("model_auto_compact_token_limit", compact_at)
    plan.client_argv += config("model_auto_compact_token_limit_scope", "total")
    if plan.reasoning != "auto":
        plan.client_argv += config("model_reasoning_effort", plan.reasoning)
    route_kind = (
        "connected FreeToken route"
        if plan.backend == "freetoken" and plan.model.get("remote") is True else
        "fully local route"
    )
    plan.warnings.append(f"Codex uses a temporary Responses provider; your normal Codex configuration remains active and unchanged. Hosted web search is disabled because this is a {route_kind}.")
    if plan.backend == "mtplx":
        plan.warnings.append(
            "The private launcher relay translates Codex Responses traffic to MTPLX Chat Completions, "
            "including standard and namespaced function-tool round trips; unsupported future tool shapes fail before inference."
        )

def build_client_plan(plan: LaunchPlan) -> None:
    builder = CLIENT_BUILDERS.get(plan.client)
    if builder is None:
        raise ValueError("Unknown work-surface adapter.")
    builder(plan, client_route(plan))
