"""Complete private work-surface planning for Pi, OMP, OpenCode, Codex and Chat.

Owns exact temporary provider/command configuration. Named live ports supply
runtime selection, current model identity and tested session validation; global
agent settings are never written and importing this module starts nothing.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Callable, Protocol
import omp_runtime

@dataclass(frozen=True)
class ClientPolicy:
    uzu_pi_tested_version: str

@dataclass(frozen=True)
class ClientPaths:
    app_directory: Callable[[], Path]
    state_directory: Callable[[], Path]

@dataclass(frozen=True)
class ClientServices:
    binary: Callable[[str], str | None]
    required_binary: Callable[[str], str]
    command_version: Callable[[str | None], str]
    artifact_fingerprint: Callable[[Path, dict[str, Any]], str]
    read_json: Callable[[Path], dict[str, Any]]
    validated_pi_session_file: Callable[[Any, str], str | None]
    prepare_mtplx_image_processor: Callable[[str, str, str], None]
    pi_model_inputs: Callable[[str, str, str], list[str]]
    token_urlsafe: Callable[[int], str]

class LaunchPlan(Protocol):
    run_id: str
    backend: str
    client: str
    model: dict[str, Any]
    project: str
    context: int
    output: int
    reasoning: str
    port: int
    client_port: int | None
    agent_host: str
    purpose: str
    runtime_binary: str | None
    pi_session_file: str | None
    run_dir: Path | None
    client_env: dict[str, str]
    client_argv: list[str]
    secrets: dict[str, str]
    warnings: list[str]

@dataclass(frozen=True)
class ClientRoute:
    """Private connection details shared by work-surface builders."""

    provider: str
    served: str
    base_url: str
    api_key: str

class ClientPlanner:
    def __init__(self, policy: ClientPolicy, paths: ClientPaths, services: ClientServices):
        self.policy, self.paths, self.services = policy, paths, services
        self.builders = MappingProxyType({
            'pi': self.build_pi_client, 'omp': self.build_omp_client,
            'opencode': self.build_opencode_client, 'codex': self.build_codex_client,
            'chat': self.build_chat_client,
        })

    def client_route(self, plan: LaunchPlan) -> ClientRoute:
        client_port = plan.client_port or plan.port
        return ClientRoute(provider=f'launcher-{plan.backend}-{plan.run_id[:8]}', served=str(plan.model['servedId']), base_url=f'http://127.0.0.1:{client_port}/v1', api_key=plan.secrets.get('clientApiKey') or plan.secrets.get('apiKey', 'local'))

    def build_chat_client(self, plan: LaunchPlan, _route: ClientRoute) -> None:
        if plan.purpose in {'benchmark', 'route-check'}:
            plan.client_argv = []
            plan.client_env = {}
            plan.warnings.append('This private check uses generated local prompts and does not open a work surface or save response text.' if plan.purpose == 'route-check' else 'Benchmark Lab uses generated local prompts and does not open an agent or save response text.')
        else:
            plan.client_argv = []
            plan.client_env = {}
            plan.warnings.append("Built-in chat streams through the launcher's private loopback route and enforces the visible response ceiling.")

    def pi_model_identity(self, plan: LaunchPlan) -> tuple[str, str]:
        artifact_path = str(plan.model.get('path') or '')
        artifact = self.services.artifact_fingerprint(Path(artifact_path), self.services.read_json(Path(artifact_path) / 'config.json')) if artifact_path and Path(artifact_path).is_dir() else ''
        pi_identity = hashlib.sha256(json.dumps([plan.backend, artifact_path, artifact, plan.model.get('id') or plan.model.get('name')], separators=(',', ':')).encode()).hexdigest()[:24]
        return (f'launcher-{plan.backend}-{pi_identity}', f'local-{pi_identity}')

    def pi_browser_test_module(self, project: str) -> str | None:
        """Advertise existing browser tooling; never install it during launch."""
        candidates = [Path(project) / 'node_modules' / 'playwright', Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright', Path('/opt/homebrew/lib/node_modules/playwright'), Path('/usr/local/lib/node_modules/playwright')]
        for candidate in candidates:
            if (candidate / 'index.js').is_file() and self.services.read_json(candidate / 'package.json').get('name') == 'playwright':
                return str(candidate.resolve())
        return None

    def selected_pi_binary(self, plan: LaunchPlan) -> str | None:
        pi_binary = self.services.binary('pi')
        if plan.backend == 'uzu' and self.services.command_version(pi_binary) != self.policy.uzu_pi_tested_version:
            preserved = self.paths.state_directory() / 'runtimes' / 'pi-uzu-0.84.2' / 'node_modules' / '.bin' / 'pi'
            if not preserved.is_file() or self.services.command_version(str(preserved)) != self.policy.uzu_pi_tested_version:
                raise ValueError('The installed Pi version changed; Uzu requires its tested Pi 0.84.2 transport and the preserved runtime is unavailable.')
            pi_binary = str(preserved)
        return pi_binary

    def model_inputs(self, plan: LaunchPlan, runtime_version: str) -> list[str]:
        # Splash's native scanner checks the tower, processor and weight files.
        # Use that route's capability for MLX vision as well as GGUF projectors.
        capability = plan.model.get('backends', {}).get(plan.backend, {})
        splash = plan.model.get('splash', {})
        if (plan.backend == 'splash' and capability.get('runnable') is True
                and splash.get('visionFormat') in {'safetensors', 'gguf'}
                and capability.get('input') == ['text', 'image']):
            return ['text', 'image']
        return self.services.pi_model_inputs(
            plan.backend, runtime_version, str(plan.model.get('path') or ''))

    def build_pi_client(self, plan: LaunchPlan, route: ClientRoute) -> None:
        pi_binary = self.selected_pi_binary(plan)
        request_headers = {'x-mtplx-client': 'pi'} if plan.backend == 'mtplx' else {}
        pi_provider, pi_model = self.pi_model_identity(plan)
        runtime_version = self.services.command_version(plan.runtime_binary or self.services.binary('mtplx')) if plan.backend == 'mtplx' else ''
        model_path = str(plan.model.get('path') or '')
        self.services.prepare_mtplx_image_processor(plan.backend, runtime_version, model_path)
        model_contract: dict[str, Any] = {'id': pi_model, 'name': plan.model['name'], 'reasoning': plan.reasoning != 'off', 'contextWindow': plan.context, 'maxTokens': plan.output, 'input': self.model_inputs(plan, runtime_version)}
        if plan.backend in {'rec', 'rapidmlx'}:
            model_contract['compat'] = {'requiresReasoningContentOnAssistantMessages': True, 'supportsStrictMode': False}
        if plan.backend in {'whallm', 'splash', 'strata', 'kolibri'}:
            allowed = set(plan.model.get('backends', {}).get(plan.backend, {}).get('agentReasoning') or [])
            model_contract.update({'supportsReasoningEffort': True, 'thinkingLevelMap': {level: ('none' if level == 'off' else level) if level in allowed else None for level in ('off', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max')}})
        provider_data = {'id': pi_provider, 'transportModel': route.served, 'name': f'LLM Launcher · {plan.backend}', 'baseUrl': route.base_url, 'apiKey': route.api_key, 'headers': request_headers, 'model': model_contract}
        if plan.backend in {'rec', 'rapidmlx'}:
            provider_data['backend'] = plan.backend
        if plan.backend in {'omlx', 'mtplx'}:
            provider_data['memoryCompaction'] = True
        if plan.backend in {'omlx', 'mtplx', 'splash', 'kolibri'}:
            provider_data['compactionRecovery'] = True
        browser_module = self.pi_browser_test_module(plan.project)
        if browser_module:
            provider_data['browserTestModule'] = browser_module
            if plan.run_dir:
                provider_data['browserArtifactDir'] = str(plan.run_dir / 'browser')
        plan.client_env['LLM_LAUNCHER_PI_PROVIDER'] = json.dumps(provider_data, separators=(',', ':'))
        plan.client_argv = [pi_binary, '--extension', str(self.paths.app_directory() / 'pi-provider.js'), '--extension', str(self.paths.app_directory() / 'pi-context-policy.js'), '--extension', str(self.paths.app_directory() / 'pi-workflow.js'), '--provider', pi_provider, '--model', pi_model]
        if plan.pi_session_file:
            plan.client_argv.extend(['--session', self.services.validated_pi_session_file(plan.pi_session_file, plan.project)])
        if plan.agent_host == 'console':
            plan.client_argv.extend(['--extension', str(self.paths.app_directory() / 'pi-hub-commands.js'), '--mode', 'rpc'])
        if plan.reasoning != 'auto':
            plan.client_argv.extend(['--thinking', plan.reasoning])

    def _require_omp_console_support(self, client: str, agent_host: str) -> None:
        if client == 'omp' and agent_host == 'console' and (not omp_runtime.console_supported(self.services.command_version(self.services.binary('omp')))):
            raise ValueError(f'oh-my-pi Hub Console is verified for {omp_runtime.TESTED_RPC_VERSION}. Choose Terminal for this installed version.')

    def build_omp_client(self, plan: LaunchPlan, route: ClientRoute) -> None:
        binary = self.services.binary('omp')
        if not binary:
            raise ValueError('oh-my-pi is not installed. Install omp and rescan runtimes.')
        self._require_omp_console_support(plan.client, plan.agent_host)
        runtime_version = self.services.command_version(plan.runtime_binary or self.services.binary('mtplx')) if plan.backend == 'mtplx' else ''
        model_path = str(plan.model.get('path') or '')
        self.services.prepare_mtplx_image_processor(plan.backend, runtime_version, model_path)
        provider, _model = self.pi_model_identity(plan)
        omp_runtime.build_client(plan, route, binary=binary, app_dir=self.paths.app_directory(), provider=provider, inputs=self.model_inputs(plan, runtime_version), console_verified=omp_runtime.console_supported(self.services.command_version(binary)))

    def build_opencode_client(self, plan: LaunchPlan, route: ClientRoute) -> None:
        runtime_version = self.services.command_version(plan.runtime_binary or self.services.binary('mtplx')) if plan.backend == 'mtplx' else ''
        model_inputs = self.model_inputs(plan, runtime_version)
        request_headers = {'x-mtplx-client': 'opencode'} if plan.backend == 'mtplx' else {}
        plugins: list[str] = []
        if plan.backend == 'mtplx':
            assert plan.run_dir
            plugin_path = plan.run_dir / 'mtplx-opencode-session.js'
            plugin_path.write_text('const providerID = ' + json.dumps(route.provider) + ";\nexport const LLMLauncherMTPLXSession = async () => ({\n  'chat.headers': async (input, output) => {\n    const active = input?.model?.providerID || input?.provider?.id;\n    if (active !== providerID) return;\n    output.headers ||= {};\n    output.headers['x-mtplx-client'] = 'opencode';\n    if (input?.sessionID) output.headers['x-mtplx-session-id'] = String(input.sessionID);\n  }\n});\nexport default LLMLauncherMTPLXSession;\n", encoding='utf-8')
            plugin_path.chmod(384)
            plugins.append(plugin_path.as_uri())
        major = 1
        try:
            text = self.services.command_version(self.services.required_binary('opencode'))
            major = int(re.search('(\\d+)', text).group(1)) if re.search('(\\d+)', text) else 1
        except (ValueError, AttributeError):
            pass
        if major >= 2:
            overlay = {'providers': {route.provider: {'name': f'LLM Launcher · {plan.backend}', 'package': '@opencode-ai/ai/providers/openai-compatible', 'settings': {'baseURL': route.base_url, 'apiKey': route.api_key, 'headers': request_headers}, 'models': {route.served: {'name': plan.model['name'], 'limit': {'context': plan.context, 'output': plan.output}, 'capabilities': {'tools': True, 'input': model_inputs, 'output': ['text']}}}}}, 'model': f'{route.provider}/{route.served}'}
        else:
            overlay = {'$schema': 'https://opencode.ai/config.json', 'provider': {route.provider: {'npm': '@ai-sdk/openai-compatible', 'name': f'LLM Launcher · {plan.backend}', 'options': {'baseURL': route.base_url, 'apiKey': route.api_key, 'headers': request_headers}, 'models': {route.served: {'name': plan.model['name'], 'modalities': {'input': model_inputs, 'output': ['text']}, 'limit': {'context': plan.context, 'output': plan.output}}}}}, 'model': f'{route.provider}/{route.served}'}
        if major < 2:
            model_settings = overlay['provider'][route.provider]['models'][route.served]
            model_settings.update(tool_call=True, reasoning=plan.reasoning != 'off')
            if plan.backend in {'mtplx', 'rec', 'rapidmlx'} and plan.reasoning != 'off':
                model_settings['interleaved'] = {'field': 'reasoning_content'}
        elif plan.backend in {'rec', 'rapidmlx'}:
            model_settings = overlay['providers'][route.provider]['models'][route.served]
            model_settings['capabilities']['reasoning'] = {'supported': plan.reasoning != 'off', 'toggle': False}
            model_settings['compatibility'] = {
                'reasoningField': 'reasoning_content', 'requireReasoning': plan.reasoning != 'off',
                'maxTokensField': 'max_tokens',
            }
        if plugins:
            overlay['plugin'] = plugins
        plan.client_env['OPENCODE_CONFIG_CONTENT'] = json.dumps(overlay, separators=(',', ':'))
        plan.client_argv = [self.services.required_binary('opencode'), plan.project, '--model', f'{route.provider}/{route.served}']

    def build_codex_client(self, plan: LaunchPlan, route: ClientRoute) -> None:
        allowed_reasoning = list(plan.model['backends'][plan.backend].get('codexReasoning') or ['auto'])
        if plan.reasoning not in allowed_reasoning:
            choices = ', '.join(allowed_reasoning)
            raise ValueError(f'This model/runtime supports these Codex reasoning choices: {choices}.')
        if plan.output < 1024:
            raise ValueError('Codex local-model sessions need a response limit of at least 1,024 tokens.')
        codex_provider = f"launcher_{plan.backend}_{plan.run_id[:8].replace('-', '_')}"

        def config(key: str, value: Any) -> list[str]:
            rendered = json.dumps(value, separators=(',', ':')) if isinstance(value, (str, bool)) else str(value)
            return ['-c', f'{key}={rendered}']
        client_key = str(plan.secrets.get('clientApiKey') or self.services.token_urlsafe(32))
        plan.secrets['clientApiKey'] = client_key
        plan.client_env['LLM_LAUNCHER_CODEX_API_KEY'] = client_key
        plan.client_argv = [self.services.required_binary('codex'), '-C', plan.project, '--model', route.served]
        plan.client_argv += config('model_provider', codex_provider)
        plan.client_argv += config(f'model_providers.{codex_provider}.name', f'LLM Launcher · {plan.backend}')
        plan.client_argv += config(f'model_providers.{codex_provider}.base_url', route.base_url)
        plan.client_argv += config(f'model_providers.{codex_provider}.env_key', 'LLM_LAUNCHER_CODEX_API_KEY')
        plan.client_argv += config(f'model_providers.{codex_provider}.requires_openai_auth', False)
        plan.client_argv += config(f'model_providers.{codex_provider}.wire_api', 'responses')
        plan.client_argv += config(f'model_providers.{codex_provider}.supports_websockets', False)
        plan.client_argv += config('web_search', 'disabled')
        plan.client_argv += config('model_supports_reasoning_summaries', plan.reasoning != 'off')
        if plan.backend in {'mtplx', 'rapidmlx'}:
            plan.client_argv += config('features.remote_compaction_v2', False)
        plan.client_argv += config('model_context_window', plan.context)
        compact_at = min(int(plan.context * 0.9), plan.context - plan.output)
        plan.client_argv += config('model_auto_compact_token_limit', compact_at)
        plan.client_argv += config('model_auto_compact_token_limit_scope', 'total')
        if plan.reasoning != 'auto':
            effort = 'none' if plan.backend == 'rapidmlx' and plan.reasoning == 'off' else plan.reasoning
            plan.client_argv += config('model_reasoning_effort', effort)
        route_kind = 'connected FreeToken route' if plan.backend == 'freetoken' and plan.model.get('remote') is True else 'fully local route'
        plan.warnings.append(f'Codex uses a temporary Responses provider; your normal Codex configuration remains active and unchanged. Hosted web search is disabled because this is a {route_kind}.')
        if plan.backend == 'mtplx':
            plan.warnings.append('The private launcher relay translates Codex Responses traffic to MTPLX Chat Completions, including standard and namespaced function-tool round trips; unsupported future tool shapes fail before inference.')
        elif plan.backend == 'rapidmlx':
            plan.warnings.append('Rapid MLX uses its native stateless Responses API with complete inline history. Stored responses and remote compaction are unavailable; this session uses local compaction.')

    def build_client_plan(self, plan: LaunchPlan) -> None:
        if plan.backend == 'rapidmlx' and plan.reasoning not in {'auto', 'off'}:
            raise ValueError('Rapid MLX reasoning must be auto or off.')
        if plan.backend == 'rec':
            if plan.reasoning != 'auto':
                raise ValueError('Rec always enables Flint reasoning; select Model default.')
            if plan.client == 'codex':
                raise ValueError('Rec provides Chat Completions; this integration does not provide the Responses API required by Codex.')
        builder = self.builders.get(plan.client)
        if builder is None:
            raise ValueError('Unknown work-surface adapter.')
        builder(plan, self.client_route(plan))
