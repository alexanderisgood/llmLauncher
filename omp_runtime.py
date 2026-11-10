"""Session-only oh-my-pi adapter; the selected engine owns inference policy."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

CHAT_ROLES = ("default", "smol", "slow", "plan", "commit", "tiny", "memory", "task", "advisor")
EFFORTS = ("minimal", "low", "medium", "high", "xhigh", "max")
TESTED_RPC_VERSION = "18.6.3"
MANAGED_BINARY = Path(__file__).resolve().parent / "bench/runtimes" / f"omp-{TESTED_RPC_VERSION}" / "omp"


def discover_binary(resolve: Callable[[list[str]], str | None]) -> str | None:
    """Keep user-installed OMP preferred and discover the durable local copy.

    Qualification copies in /tmp are deliberately excluded: clearing temporary
    files must not make an installed launcher work surface disappear.
    """
    return resolve(["~/.bun/bin/omp", "~/.local/bin/omp", "/opt/homebrew/bin/omp", "omp", str(MANAGED_BINARY)])


def console_supported(version: Any) -> bool:
    """Native Hub lifecycle/framing was exercised on this exact release."""
    return isinstance(version, str) and version.strip() in {TESTED_RPC_VERSION, f"omp/{TESTED_RPC_VERSION}"}


def provider_contract(
    *, provider: str, served: str, name: str, base_url: str, api_key: str,
    backend: str, context: int, output: int, reasoning: str,
    allowed_reasoning: list[str], inputs: list[str], session_id: str = "",
) -> dict[str, Any]:
    """Keep transport IDs stable and replay real reasoning across tool turns."""
    efforts = [level for level in EFFORTS if level in allowed_reasoning]
    model: dict[str, Any] = {
        "id": served, "name": name, "reasoning": reasoning != "off",
        "input": inputs, "contextWindow": context, "maxTokens": output,
        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
        "compat": {
            "supportsStore": False, "supportsDeveloperRole": False,
            "supportsUsageInStreaming": True, "maxTokensField": "max_tokens",
            # The relay pins the selected reasoning setting. Avoid a catalog
            # heuristic overriding it (especially OMP's OpenAI off fallback).
            "supportsReasoningEffort": False, "supportsReasoningParams": False,
            "supportsStrictMode": False,
            "reasoningContentField": "reasoning_content",
            "requiresReasoningContentForToolCalls": True,
            "requiresReasoningContentForAllAssistantTurns": True,
            "allowsSyntheticReasoningContentForToolCalls": False,
            "requiresAssistantContentForToolCalls": False,
        },
    }
    if efforts and reasoning != "off":
        model["thinking"] = {
            "mode": "effort", "efforts": efforts,
            "requiresEffort": "off" not in allowed_reasoning,
            **({"defaultLevel": reasoning} if reasoning in efforts else {}),
        }
    headers = {"x-mtplx-client": "pi"} if backend == "mtplx" else {}
    if backend == "mtplx" and session_id:
        headers["x-mtplx-session-id"] = session_id
    return {
        "id": provider, "baseUrl": base_url, "apiKey": api_key,
        "api": "openai-completions", "authHeader": True,
        "headers": headers, "models": [model],
    }


def settings_overlay(provider: str, served: str) -> dict[str, Any]:
    """Route helper work locally too; never silently fall back to a cloud model."""
    selector = f"{provider}/{served}"
    return {
        "modelRoles": {role: selector for role in CHAT_ROLES},
        "enabledModels": [selector], "enabledProviders": [provider],
        "retry": {
            "modelFallback": False,
            "fallbackChains": {**{role: [] for role in CHAT_ROLES}, selector: []},
        },
        "contextPromotion": {"enabled": False},
    }


def write_overlay(run_dir: Path, overlay: dict[str, Any]) -> Path:
    """Create an owner-only overlay with no global configuration writes."""
    path = run_dir / "omp-settings.json"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as target:
        json.dump(overlay, target, ensure_ascii=False, separators=(",", ":"))
    return path


def build_client(plan: Any, route: Any, *, binary: str, app_dir: Path,
                 provider: str, inputs: list[str], console_verified: bool = False) -> None:
    if plan.agent_host not in {"terminal", "console"} or (plan.agent_host == "console" and not console_verified):
        raise ValueError("oh-my-pi Hub Console needs its verified native protocol. Choose Terminal for this installed version.")
    if plan.run_dir is None:
        raise ValueError("oh-my-pi needs a private session directory.")
    contract = provider_contract(
        provider=provider, served=route.served, name=plan.model["name"],
        base_url=route.base_url, api_key=route.api_key, backend=plan.backend,
        context=plan.context, output=plan.output, reasoning=plan.reasoning,
        allowed_reasoning=plan.model["backends"][plan.backend].get("agentReasoning") or ["auto"],
        inputs=inputs,
        session_id=plan.run_id,
    )
    overlay = write_overlay(plan.run_dir, settings_overlay(provider, route.served))
    plan.client_env["LLM_LAUNCHER_OMP_PROVIDER"] = json.dumps(contract, separators=(",", ":"))
    # OMP applies these inherited environment variables after --config. Pin
    # the session overrides too, so Terminal settings cannot reroute helpers.
    selector = f"{provider}/{route.served}"
    plan.client_env.update({name: selector for name in
                            ("PI_SMOL_MODEL", "PI_SLOW_MODEL", "PI_PLAN_MODEL")})
    plan.client_argv = [
        binary, "--extension", str(app_dir / "omp-provider.mjs"),
        # Resolve after the extension registers its provider. An explicit
        # --provider is resolved by OMP before extensions load.
        "--config", str(overlay), "--model", f"{provider}/{route.served}",
    ]
    if plan.reasoning != "auto":
        plan.client_argv.extend(["--thinking", plan.reasoning])
    if plan.agent_host == "console":
        plan.client_argv.extend(["--mode", "rpc"])
    plan.warnings.append(
        f"oh-my-pi opens in {'Hub Console' if plan.agent_host == 'console' else 'Terminal'} with this engine, context and response limit. "
        "Its helper roles use the same local model; settings are scoped to this session."
    )
