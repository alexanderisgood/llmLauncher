"""Frozen inference feature before extraction; test-only explicit imports."""
from __future__ import annotations
import copy
from dataclasses import dataclass, fields
import hashlib
from http import HTTPStatus
import json
import re
import threading
import time
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol
import urllib.error
import urllib.request
import generation_metrics
from response_metrics import ResponseMetrics as StreamResponseMetrics
from sse_framing import ResponseOutcome
from sampling_contract import (SamplingContractError, build_sampling_contract,
    canonicalize_sampling, load_sampling_contract, rewrite_chat_completions_request)

from launcher import (
    BENCHMARK_PROBE_CONTRACT,
    CHAT_REASONING_LEVELS,
    CLIENT_ADAPTERS,
    LLAMACPP_QUALIFICATION_CORRECTNESS_ID,
    LLAMACPP_QUALIFICATION_REASONING_BOUNDARY_ID,
    LLAMACPP_QWEN_REASONING_BUDGET_MESSAGE,
    LaunchCancelled,
    MANAGER,
    MAX_JSON,
    ROUTE_CHECK_MAX_TOKENS,
    ROUTE_CHECK_PROMPT,
    ROUTE_CHECK_TOOL_NAME,
    ROUTE_QUALIFICATION_MAX_TOKENS,
    ROUTE_QUALIFICATION_THINKING_TOKENS,
    UZU_QUALIFICATION_CORRECTNESS_ID,
    _CHAT_ABORTED_TERMINAL_REASONS,
    _CHAT_CLEAN_TERMINAL_REASONS,
    _CHAT_FAILED_TERMINAL_REASONS,
    _CHAT_LIMIT_TERMINAL_REASONS,
    _CHAT_TERMINAL_PRIORITY,
    _ROUTE_CHECK_TERMINAL_PRIORITY,
    deep_get,
    sampling_contract_from_settings,
    sampling_route_enforcement,
    validated_chat_messages,
)

def apply_chat_reasoning_contract(
    body: dict[str, Any], backend: str, reasoning: str,
) -> dict[str, Any]:
    """Pin request-level thinking controls without merging reasoning into content."""
    if reasoning not in CHAT_REASONING_LEVELS:
        raise ValueError("Unknown reasoning level.")
    if backend not in {"whallm", "omlx", "uzu", "slotstream", "splash", "kolibri"}:
        return body

    # These top-level controls belong to Whallm. oMLX pins the same visible
    # contract in its launcher-owned per-model settings, so remove inherited
    # agent controls rather than letting them contradict that server contract.
    body.pop("thinking_mode", None)
    body.pop("reasoning_effort", None)
    body.pop("enable_thinking", None)
    body.pop("chat_template_kwargs", None)
    if backend == "uzu":
        if reasoning not in {"auto", "off"}:
            raise ValueError("This Qwen3.6 Uzu artifact supports reasoning on or off, not effort levels.")
        body["reasoning_effort"] = "disabled" if reasoning == "off" else "default"
        return body
    if backend in {"slotstream", "kolibri"}:
        body.pop("think", None)
        if reasoning != "auto":
            body["reasoning_effort"] = "none" if reasoning == "off" else reasoning
        return body
    if backend == "splash":
        body.pop("think", None)
        if reasoning == "auto":
            return body
        if reasoning not in {"off", "low", "medium", "xhigh"}:
            raise ValueError("Splash supports reasoning off, low, medium or xhigh.")
        body["reasoning_effort"] = "none" if reasoning == "off" else reasoning
        return body
    if backend == "omlx" or reasoning == "auto":
        return body
    if reasoning == "off":
        body.update({"thinking_mode": "chat", "reasoning_effort": "none"})
    else:
        body.update({"thinking_mode": "thinking", "reasoning_effort": reasoning})
    return body


def build_chat_completion_request(
    plan: LaunchPlan, payload: dict[str, Any],
) -> urllib.request.Request:
    """Build one bounded OpenAI-compatible request for the active chat run."""
    if plan.client != "chat":
        raise ValueError("The active run is not a built-in chat session.")
    messages = validated_chat_messages(payload, str(plan.chat.get("systemPrompt") or ""))
    body: dict[str, Any] = {
        "model": plan.model["servedId"],
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
        "max_tokens": plan.output,
    }
    apply_chat_reasoning_contract(body, plan.backend, plan.reasoning)
    raw_contract = getattr(plan, "sampling_contract", None)
    plan_chat = getattr(plan, "chat", None)
    contract_document = (
        raw_contract
        if isinstance(raw_contract, dict) else
        sampling_contract_from_settings(plan.model, plan_chat)
        if isinstance(plan_chat, dict) and plan_chat.get("sampling") in {"model", "custom"} else
        build_sampling_contract(
            "model", model_defaults=plan.model.get("defaultSampling"),
        ).as_dict()
    )
    raw_enforcement = getattr(plan, "sampling_enforcement", None)
    enforcement = (
        raw_enforcement
        if isinstance(raw_enforcement, dict) else
        sampling_route_enforcement(
            plan.backend, "chat",
            plan.model.get("backends", {}).get(plan.backend, {}),
            contract_document, protocol="chat-completions",
        )
    )
    assert enforcement is not None
    try:
        body = rewrite_chat_completions_request(
            body, contract_document,
            representable_fields=enforcement["representableFields"],
            implicit_model_defaults=enforcement["implicitModelDefaults"],
        )
    except SamplingContractError as error:
        raise ValueError(str(error)) from error
    return urllib.request.Request(
        f"http://127.0.0.1:{plan.client_port or plan.port}/v1/chat/completions",
        data=json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {plan.secrets.get('clientApiKey') or plan.secrets.get('apiKey', 'local')}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json",
        },
    )


def build_benchmark_completion_request(
    plan: LaunchPlan, prompt: str | list[dict[str, str]], max_tokens: int,
    sampling: dict[str, Any], *, reasoning_budget_tokens: int | None = None,
    greedy_probe: bool = False,
) -> urllib.request.Request:
    if isinstance(prompt, str):
        messages = [{"role": "user", "content": prompt}]
    elif (
        isinstance(prompt, list) and prompt
        and all(
            isinstance(message, dict)
            and message.get("role") in {"system", "user", "assistant"}
            and isinstance(message.get("content"), str)
            for message in prompt
        )
    ):
        messages = copy.deepcopy(prompt)
    else:
        raise ValueError("Benchmark messages are invalid.")
    body: dict[str, Any] = {
        "model": plan.model["servedId"],
        "messages": messages,
        "stream": True,
    }
    if plan.backend == "uzu":
        # Uzu always emits final usage, ignores stream_options, and its current
        # server does not preserve the launcher's full sampling contract.
        # Qualification therefore measures the packaged model defaults only.
        body["max_completion_tokens"] = max_tokens
    else:
        body["stream_options"] = {"include_usage": True}
        body["max_tokens"] = max_tokens
    qualification_budget = (
        reasoning_budget_tokens
        if reasoning_budget_tokens is not None else
        plan.options.get("_qualificationThinkingBudgetTokens")
    )
    if reasoning_budget_tokens is not None and (
        plan.backend != "llamacpp"
        or isinstance(reasoning_budget_tokens, bool)
        or not isinstance(reasoning_budget_tokens, int)
        or not 0 <= reasoning_budget_tokens < max_tokens
        or max_tokens != ROUTE_QUALIFICATION_MAX_TOKENS
    ):
        raise ValueError("The explicit reasoning-boundary budget is invalid.")
    if (
        plan.backend == "llamacpp"
        and isinstance(qualification_budget, int)
        and not isinstance(qualification_budget, bool)
        and 0 <= qualification_budget < max_tokens
        and max_tokens == ROUTE_QUALIFICATION_MAX_TOKENS
    ):
        body["reasoning_budget_tokens"] = qualification_budget
        body["reasoning_budget_message"] = LLAMACPP_QWEN_REASONING_BUDGET_MESSAGE
    apply_chat_reasoning_contract(body, plan.backend, plan.reasoning)
    try:
        requested_sampling = canonicalize_sampling(sampling)
        raw_plan_contract = getattr(plan, "sampling_contract", None)
        plan_contract = (
            load_sampling_contract(raw_plan_contract)
            if isinstance(raw_plan_contract, dict) else None
        )
        plan_chat = getattr(plan, "chat", None)
        if (
            plan_contract is None and isinstance(plan_chat, dict)
            and plan_chat.get("sampling") in {"model", "custom"}
        ):
            plan_contract = load_sampling_contract(
                sampling_contract_from_settings(plan.model, plan_chat)
            )
        if plan_contract is None and (plan.backend == "uzu" or not requested_sampling):
            plan_contract = build_sampling_contract(
                "model", model_defaults=plan.model.get("defaultSampling"),
            )
        if greedy_probe:
            if plan.backend == "uzu":
                raise ValueError("Uzu's packaged sampler cannot run a fixed greedy probe.")
            fixed_probe = copy.deepcopy(BENCHMARK_PROBE_CONTRACT["sampling"])
            if requested_sampling != canonicalize_sampling(fixed_probe):
                raise ValueError("The fixed benchmark probe sampling contract changed.")
            request_contract = build_sampling_contract("custom", custom=fixed_probe)
        elif plan_contract is not None:
            # Uzu's pinned package owns its sampler. Its qualification passes a
            # historical greedy probe dictionary, but that dictionary was
            # never representable and was deliberately omitted on the wire.
            request_contract = plan_contract
        else:
            request_contract = build_sampling_contract(
                "custom", custom=requested_sampling,
            )
        enforcement = sampling_route_enforcement(
            plan.backend, "chat",
            plan.model.get("backends", {}).get(plan.backend, {}),
            request_contract.as_dict(), protocol="chat-completions",
        )
        assert enforcement is not None
        body = rewrite_chat_completions_request(
            body, request_contract,
            representable_fields=enforcement["representableFields"],
            implicit_model_defaults=enforcement["implicitModelDefaults"],
        )
        if plan.backend == "splash" and body.get("top_k") == 0:
            # Splash validates top_k >= 1 even when decoding is greedy; at
            # temperature 0 the value is unused (the engine selects its greedy
            # cohort), so pinning the minimum preserves the measured contract.
            body["top_k"] = 1
    except SamplingContractError as error:
        raise ValueError(str(error)) from error
    return urllib.request.Request(
        f"http://127.0.0.1:{plan.port}/v1/chat/completions",
        data=json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {plan.secrets.get('apiKey', 'local')}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json",
        },
    )


def _benchmark_text_part(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(
            str(item.get("text") or item.get("content") or "")
            for item in value if isinstance(item, dict)
        )
    return ""


def _benchmark_cached_prompt_tokens(usage: dict[str, Any], prompt_tokens: int) -> int | None:
    """Read standard cache telemetry when present; absence remains unknown, not zero."""
    candidates: list[Any] = []
    for detail_key in ("prompt_tokens_details", "input_tokens_details"):
        details = usage.get(detail_key)
        if isinstance(details, dict) and "cached_tokens" in details:
            candidates.append(details.get("cached_tokens"))
    for direct_key in ("cached_tokens", "cache_read_input_tokens"):
        if direct_key in usage:
            candidates.append(usage.get(direct_key))
    for candidate in candidates:
        try:
            parsed = int(candidate)
        except (TypeError, ValueError):
            continue
        if isinstance(candidate, bool) or parsed < 0:
            continue
        return min(prompt_tokens, parsed)
    return None


def _openai_error_detail(payload: Any) -> str | None:
    """Return one bounded OpenAI-compatible error without exposing raw payloads."""
    if not isinstance(payload, dict):
        return None
    raw_error = payload.get("error")
    if raw_error is None and str(payload.get("type") or "") == "response.failed":
        response = payload.get("response")
        if isinstance(response, dict):
            raw_error = response.get("error")
    if raw_error is None:
        return None
    code = ""
    if isinstance(raw_error, dict):
        message = str(raw_error.get("message") or raw_error.get("detail") or "").strip()
        code = str(raw_error.get("omlx_code") or raw_error.get("code") or "").strip()
    else:
        message = str(raw_error).strip()
    message = re.sub(r"\s+", " ", message)[:1_200]
    code = re.sub(r"[^A-Za-z0-9_.-]", "", code)[:80]
    if not message:
        message = "The runtime reported an unspecified error."
    return f"{message} [{code}]" if code and code not in message else message


def benchmark_repeated_phrase_fraction(text: str) -> float:
    """Bounded repetition diagnostic only; never a correctness/qualification gate."""
    words = text[-32768:].split()[-4096:]
    count = len(words) - 15
    if count <= 0:
        return 0.0
    unique = {tuple(words[index:index + 16]) for index in range(count)}
    return round((count - len(unique)) / count, 4)


def run_benchmark_completion(
    plan: LaunchPlan, prompt: str | list[dict[str, str]], max_tokens: int,
    sampling: dict[str, Any],
    cancel_event: threading.Event, *, correctness_expected: str | None = None,
    reasoning_budget_tokens: int | None = None,
    reply_observer: Callable[[dict[str, str]], None] | None = None,
    greedy_probe: bool = False,
) -> dict[str, Any]:
    """Measure one streamed request and require authoritative token usage."""
    request = build_benchmark_completion_request(
        plan, prompt, max_tokens, sampling,
        reasoning_budget_tokens=reasoning_budget_tokens,
        greedy_probe=greedy_probe,
    )
    started = time.monotonic()
    first_token_at: float | None = None
    last_token_at: float | None = None
    output_events = 0
    outcome = ResponseOutcome("chat-completions", True)
    content: list[str] = []
    reasoning: list[str] = []
    usage: dict[str, Any] = {}
    finish_reasons: set[str] = set()
    strict_qualification_stream = (
        plan.backend in {"llamacpp", "uzu"}
        and plan.options.get("_qualificationThinkingBudgetTokens")
        == ROUTE_QUALIFICATION_THINKING_TOKENS
    )

    def observe_finish_reason(value: Any) -> None:
        if value is None:
            return
        if not isinstance(value, str):
            finish_reasons.add("invalid")
            return
        normalized = value.strip().casefold()
        if normalized:
            finish_reasons.add(normalized[:80])
    try:
        response = urllib.request.urlopen(request, timeout=900)
    except urllib.error.HTTPError as error:
        raw = error.read(16_000).decode("utf-8", "replace")
        raise RuntimeError(f"Benchmark request failed with HTTP {error.code}: {raw[:600]}") from error
    except (OSError, urllib.error.URLError) as error:
        raise RuntimeError(f"Benchmark could not reach the model: {error}") from error
    with response:
        content_type = response.headers.get("Content-Type", "").lower()
        metadata = StreamResponseMetrics("chat-completions", content_type, backend=plan.backend, maximum=MAX_JSON)
        if strict_qualification_stream and not content_type.startswith("text/event-stream"):
            raise RuntimeError(
                "Qualification requires a text/event-stream response so TTFT and decode TPS "
                "can be measured authoritatively."
            )
        if content_type.startswith("application/json"):
            data = json.loads(response.read(MAX_JSON))
            metadata.observe_payload(data)
            runtime_error = _openai_error_detail(data)
            if runtime_error:
                raise RuntimeError(f"Benchmark runtime rejected the request: {runtime_error}")
            total = time.monotonic() - started
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") if isinstance(choice, dict) else {}
            if isinstance(choice, dict):
                observe_finish_reason(choice.get("finish_reason"))
            if isinstance(message, dict):
                content.append(_benchmark_text_part(message.get("content")))
                reasoning.append(_benchmark_text_part(message.get("reasoning_content") or message.get("reasoning")))
            usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
            outcome.inspect(data)
        else:
            for raw_line in response:
                if cancel_event.is_set():
                    raise LaunchCancelled("Benchmark cancelled.")
                line = raw_line.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload or payload == "[DONE]":
                    continue
                try:
                    event = json.loads(payload)
                except ValueError as error:
                    if strict_qualification_stream:
                        raise RuntimeError(
                            "Qualification stream emitted a malformed JSON data event."
                        ) from error
                    outcome.invalid = True
                    continue
                outcome.inspect(event)
                emitted_output = metadata.observe_payload(event)
                runtime_error = _openai_error_detail(event)
                if runtime_error:
                    raise RuntimeError(f"Benchmark runtime rejected the request: {runtime_error}")
                if isinstance(event.get("usage"), dict):
                    usage = event["usage"]
                choices = event.get("choices")
                if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                    continue
                observe_finish_reason(choices[0].get("finish_reason"))
                delta = choices[0].get("delta")
                if not isinstance(delta, dict):
                    delta = choices[0].get("message") if isinstance(choices[0].get("message"), dict) else {}
                content_piece = _benchmark_text_part(delta.get("content"))
                reasoning_piece = _benchmark_text_part(delta.get("reasoning_content") or delta.get("reasoning"))
                if emitted_output:
                    last_token_at = time.monotonic() - started
                    output_events += 1
                    if first_token_at is None:
                        first_token_at = last_token_at
                if content_piece:
                    content.append(content_piece)
                if reasoning_piece:
                    reasoning.append(reasoning_piece)
        total = time.monotonic() - started
    prompt_tokens = StreamResponseMetrics._integer(usage.get("prompt_tokens"))
    completion_tokens = StreamResponseMetrics._integer(usage.get("completion_tokens"))
    if prompt_tokens is None or completion_tokens is None:
        raise RuntimeError(
            "This runtime did not return authoritative prompt/completion token usage; "
            "Benchmark Lab will not estimate a winner from characters or stream chunks."
        )
    if prompt_tokens <= 0 or completion_tokens <= 0:
        raise RuntimeError("The runtime returned an empty or invalid benchmark token count.")
    cached_prompt_tokens = _benchmark_cached_prompt_tokens(usage, prompt_tokens)
    ttft = first_token_at
    decode_seconds = (last_token_at - first_token_at
                      if last_token_at is not None and first_token_at is not None else 0)
    timing_valid = bool(content_type.startswith("text/event-stream")
                        and output_events >= 2 and completion_tokens > 1 and decode_seconds >= 0.001
                        and outcome.result in {"completed", "truncated"})
    timing_reason = (None if timing_valid else
                     "Buffered JSON has no streamed output timestamps" if content_type.startswith("application/json") else
                     "Incomplete or invalid stream" if outcome.result not in {"completed", "truncated"} else
                     "Not enough separately timed output to measure decode speed")
    decode_tokens = completion_tokens - 1
    observed_decode_tps = decode_tokens / decode_seconds if timing_valid else None
    native = generation_metrics.native_generation_proof(
        plan.backend, completion_tokens, metadata.public_runtime_stats(),
    )
    decode_tps = native["tokensPerSecond"] if native is not None else observed_decode_tps
    timing_source = native["source"] if native is not None else "engine-usage-and-relay-clock"
    timing_basis = native["basis"] if native is not None else "client output-event interval estimate"
    if plan.backend in generation_metrics.BUFFERED_GENERATION_BACKENDS and native is None:
        decode_tps = None
        timing_source = None
        timing_basis = "native request generation timing unavailable"
        timing_reason = "Buffered or speculative delivery cannot measure generation speed without validated native request timing."
    elif native is not None and decode_tps is None:
        timing_reason = "The complete response belonged to the first native batch; no subsequent generation interval was measured."
    elif native is not None and decode_tps is not None and outcome.result in {"completed", "truncated"}:
        timing_reason = None
    observed_timing_valid = timing_valid
    timing_valid = bool(decode_tps is not None and outcome.result in {"completed", "truncated"})
    output_identity = json.dumps(
        {"reasoning": "".join(reasoning), "content": "".join(content)},
        ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    reasoning_text = "".join(reasoning)
    answer_text = "".join(content)
    finish_reason = next(iter(finish_reasons)) if len(finish_reasons) == 1 else None
    response_limit_reached = finish_reason in {
        "length", "max_tokens", "max_output_tokens", "token_limit",
    }
    if len(finish_reasons) > 1:
        terminal_state = "unknown"
    elif response_limit_reached:
        terminal_state = "truncated"
    elif finish_reason == "stop":
        terminal_state = "complete"
    elif finish_reason is None:
        terminal_state = "unknown"
    else:
        terminal_state = "incomplete"
    if outcome.result not in {"completed", "truncated"}:
        terminal_state = "incomplete"
    answer_text = "".join(content).strip()
    requested_reasoning_budget = (
        reasoning_budget_tokens
        if reasoning_budget_tokens is not None else
        plan.options.get("_qualificationThinkingBudgetTokens")
    )
    if not (
        plan.backend == "llamacpp"
        and isinstance(requested_reasoning_budget, int)
        and not isinstance(requested_reasoning_budget, bool)
        and 0 <= requested_reasoning_budget < max_tokens
        and max_tokens == ROUTE_QUALIFICATION_MAX_TOKENS
    ):
        requested_reasoning_budget = None
    result = {
        "promptTokens": prompt_tokens,
        "authoritativeUsage": True,
        "cachedPromptTokens": cached_prompt_tokens,
        "uncachedPromptTokens": (
            prompt_tokens - cached_prompt_tokens if cached_prompt_tokens is not None else None
        ),
        "cacheHitRate": (
            round(cached_prompt_tokens / prompt_tokens, 6)
            if cached_prompt_tokens is not None else None
        ),
        "completionTokens": completion_tokens,
        "requestedMaxTokens": max_tokens,
        "thinkingBudgetTokensRequested": requested_reasoning_budget,
        "reasoningBudgetMessageSha256": (
            hashlib.sha256(
                LLAMACPP_QWEN_REASONING_BUDGET_MESSAGE.encode("utf-8")
            ).hexdigest()
            if requested_reasoning_budget is not None else None
        ),
        "ttftSeconds": round(ttft, 6) if ttft is not None else None,
        "transport": "sse" if content_type.startswith("text/event-stream") else "json",
        "responseOutcome": outcome.result,
        "decodeTimingValid": timing_valid,
        "timingInvalidReason": timing_reason,
        "decodeTimingBasis": timing_basis,
        "decodeTimingSource": timing_source,
        "generationProof": native,
        "nativeTimeToFirstTokenSeconds": metadata.public_runtime_stats().get("runtimeTimeToFirstTokenSeconds"),
        "nativePromptProcessing": copy.deepcopy(metadata.public_runtime_stats().get("promptProcessing")),
        "observedDecodeTimingValid": observed_timing_valid,
        "observedDecodeTokensPerSecond": round(observed_decode_tps, 4) if observed_decode_tps is not None else None,
        "totalSeconds": round(total, 6),
        "decodeTokensPerSecond": round(decode_tps, 4) if timing_valid else None,
        "endToEndTokensPerSecond": round(completion_tokens / max(total, 0.000_001), 4),
        "reasoningObserved": bool(reasoning_text.strip()),
        "answerObserved": bool(answer_text.strip()),
        "reasoningCharacters": len(reasoning_text.strip()),
        "answerCharacters": len(answer_text.strip()),
        "reasoningRepeatedPhraseFraction": benchmark_repeated_phrase_fraction(reasoning_text),
        "answerRepeatedPhraseFraction": benchmark_repeated_phrase_fraction(answer_text),
        "finishReason": finish_reason,
        "terminalState": terminal_state,
        "terminalComplete": terminal_state == "complete",
        "responseLimitReached": response_limit_reached,
        "outputHash": hashlib.sha256(output_identity).hexdigest(),
    }
    if correctness_expected is not None:
        uzu_correctness = plan.backend == "uzu"
        tag_leak = re.search(r"<\s*/?\s*(?:think|thinking)\b", answer_text, re.IGNORECASE)
        transition_leak = (
            LLAMACPP_QWEN_REASONING_BUDGET_MESSAGE.strip().casefold()
            in answer_text.casefold()
        )
        result["correctnessContract"] = {
            "id": (
                UZU_QUALIFICATION_CORRECTNESS_ID
                if uzu_correctness else LLAMACPP_QUALIFICATION_CORRECTNESS_ID
            ),
            "expectedAnswerSha256": hashlib.sha256(
                correctness_expected.encode("utf-8")
            ).hexdigest(),
            "observedAnswerSha256": hashlib.sha256(answer_text.encode("utf-8")).hexdigest(),
            "exact": answer_text == correctness_expected,
            "terminalComplete": terminal_state == "complete",
            "authoritativeUsage": True,
            "reasoningBoundaryContractId": (
                None if uzu_correctness else LLAMACPP_QUALIFICATION_REASONING_BOUNDARY_ID
            ),
            "reasoningBudgetTokensRequested": requested_reasoning_budget,
            "reasoningBudgetMessageSha256": result["reasoningBudgetMessageSha256"],
            "reasoningTagLeakDetected": tag_leak is not None,
            "transitionMessageLeakDetected": transition_leak,
            "reasoningBoundaryClean": bool(
                not uzu_correctness
                and requested_reasoning_budget == 0
                and answer_text == correctness_expected
                and terminal_state == "complete"
                and tag_leak is None
                and not transition_leak
            ),
        }
    if reply_observer is not None and result["terminalComplete"]:
        # Exact channel bytes preserve Uzu's message-prefix comparison. The
        # observer is local to a running qualification, never part of its result.
        reply_observer({
            "role": "assistant", "content": "".join(content),
            **({"reasoning_content": reasoning_text} if reasoning_text else {}),
        })
    return result


def build_route_check_request(
    plan: LaunchPlan, *, tool_probe: bool = False,
) -> urllib.request.Request:
    """Build one bounded synthetic request through the selected surface protocol."""
    descriptor = CLIENT_ADAPTERS.get(plan.client)
    if descriptor is None:
        raise ValueError("Unknown work-surface adapter.")
    tool_prompt = (
        f"Call {ROUTE_CHECK_TOOL_NAME} exactly once with status set to ready. "
        "This is synthetic local test data; do not inspect files or use another tool."
    )
    if descriptor.protocol == "responses":
        if not plan.client_port:
            raise ValueError("The Responses route has no private client port.")
        body: dict[str, Any] = {
            "model": plan.model["servedId"],
            "input": tool_prompt if tool_probe else ROUTE_CHECK_PROMPT,
            "stream": True,
            "max_output_tokens": min(ROUTE_CHECK_MAX_TOKENS, plan.output),
        }
        if tool_probe:
            body.update({
                "tools": [{
                    "type": "function",
                    "name": ROUTE_CHECK_TOOL_NAME,
                    "description": "Return a synthetic route-check status without accessing user data.",
                    "parameters": {
                        "type": "object",
                        "properties": {"status": {"type": "string", "enum": ["ready"]}},
                        "required": ["status"],
                        "additionalProperties": False,
                    },
                    "strict": False,
                }],
                "tool_choice": "auto",
            })
        api_key = str(
            plan.client_env.get("LLM_LAUNCHER_CODEX_API_KEY")
            or plan.secrets.get("apiKey") or "local"
        )
        url = f"http://127.0.0.1:{plan.client_port}/v1/responses"
    elif descriptor.protocol == "chat-completions":
        messages: list[dict[str, str]] = []
        generated_only_qualification = bool(
            tool_probe
            and plan.backend == "llamacpp"
            and plan.options.get("_qualificationThinkingBudgetTokens")
            == ROUTE_QUALIFICATION_THINKING_TOKENS
        )
        if (
            not generated_only_qualification
            and plan.client == "chat" and str(plan.chat.get("systemPrompt") or "")
        ):
            messages.append({"role": "system", "content": str(plan.chat["systemPrompt"])})
        messages.append({"role": "user", "content": tool_prompt if tool_probe else ROUTE_CHECK_PROMPT})
        body = {
            "model": plan.model["servedId"],
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            "max_tokens": min(ROUTE_CHECK_MAX_TOKENS, plan.output),
        }
        if generated_only_qualification:
            body.update({
                "reasoning_budget_tokens": 32,
                "reasoning_budget_message": LLAMACPP_QWEN_REASONING_BUDGET_MESSAGE,
            })
        if (
            not generated_only_qualification
            and plan.client == "chat" and plan.chat.get("sampling") == "custom"
        ):
            body.update({
                "temperature": plan.chat["temperature"],
                "top_p": plan.chat["topP"],
                "top_k": plan.chat["topK"],
                "presence_penalty": plan.chat["presencePenalty"],
                "frequency_penalty": plan.chat["frequencyPenalty"],
            })
            if plan.chat.get("seed") is not None:
                body["seed"] = plan.chat["seed"]
        if tool_probe:
            body.update({
                "tools": [{
                    "type": "function",
                    "function": {
                        "name": ROUTE_CHECK_TOOL_NAME,
                        "description": "Return a synthetic route-check status without accessing user data.",
                        "parameters": {
                            "type": "object",
                            "properties": {"status": {"type": "string", "enum": ["ready"]}},
                            "required": ["status"],
                            "additionalProperties": False,
                        },
                    },
                }],
                "tool_choice": "auto",
            })
        apply_chat_reasoning_contract(body, plan.backend, plan.reasoning)
        api_key = str(plan.secrets.get("apiKey") or "local")
        url = f"http://127.0.0.1:{plan.port}/v1/chat/completions"
    else:
        raise ValueError(f"Route Check does not know how to probe {descriptor.protocol}.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream, application/json",
    }
    if plan.backend == "mtplx" and plan.client in {"pi", "omp", "opencode"}:
        headers["x-mtplx-client"] = "pi" if plan.client == "omp" else plan.client
    return urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        method="POST",
        headers=headers,
    )


def _route_check_usage(usage: dict[str, Any]) -> dict[str, Any]:
    prompt_value = usage.get("prompt_tokens", usage.get("input_tokens"))
    completion_value = usage.get("completion_tokens", usage.get("output_tokens"))
    try:
        prompt_tokens = int(prompt_value)
        completion_tokens = int(completion_value)
    except (TypeError, ValueError):
        return {"available": False, "promptTokens": None, "completionTokens": None}
    if (
        isinstance(prompt_value, bool) or isinstance(completion_value, bool)
        or prompt_tokens < 0 or completion_tokens < 0
    ):
        return {"available": False, "promptTokens": None, "completionTokens": None}
    return {
        "available": True,
        "promptTokens": prompt_tokens,
        "completionTokens": completion_tokens,
    }


def _chat_cache_value_has_output(value: Any) -> bool:
    """Detect streamed output without copying or returning its contents."""
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, list):
        return any(_chat_cache_value_has_output(item) for item in value)
    if not isinstance(value, dict):
        return False
    if value.get("type") in {"tool_call", "function_call"}:
        return True
    return any(
        _chat_cache_value_has_output(value.get(key))
        for key in (
            "text", "content", "reasoning", "reasoning_content", "thinking",
            "tool_calls", "function_call", "function", "arguments",
        )
        if key in value
    )


def chat_cache_observation_event(event: Any) -> dict[str, Any]:
    """Return only cache/timing-safe facts from one chat event; never return text."""
    facts: dict[str, Any] = {"outputObserved": False, "usage": None}
    if not isinstance(event, dict):
        return facts

    choices = event.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            for key in ("delta", "message", "text"):
                if key in choice and _chat_cache_value_has_output(choice.get(key)):
                    facts["outputObserved"] = True
                    break
            if facts["outputObserved"]:
                break
    if not facts["outputObserved"]:
        for key in ("message", "content", "reasoning", "reasoning_content", "thinking"):
            if key in event and _chat_cache_value_has_output(event.get(key)):
                facts["outputObserved"] = True
                break

    raw_usage = event.get("usage")
    if isinstance(raw_usage, dict):
        normalized = _route_check_usage(raw_usage)
        if normalized["available"]:
            prompt_tokens = int(normalized["promptTokens"])
            cached_tokens = _benchmark_cached_prompt_tokens(raw_usage, prompt_tokens)
            facts["usage"] = {
                "promptTokens": prompt_tokens,
                "completionTokens": int(normalized["completionTokens"]),
                "cacheTelemetryReported": cached_tokens is not None,
                "cachedPromptTokens": cached_tokens,
            }
    return facts


def _chat_terminal_reason(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 80:
        return ""
    return re.sub(r"[\s-]+", "_", value.strip().casefold())


def chat_stream_terminal_state(event: Any) -> str:
    """Classify only explicit upstream terminal evidence; missing evidence stays unknown."""
    if not isinstance(event, dict):
        return ""
    choices = event.get("choices")
    choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
    response = event.get("response") if isinstance(event.get("response"), dict) else {}
    if event.get("error") or response.get("error"):
        return "failed"

    candidates = [
        choice.get("finish_reason"), choice.get("finishReason"),
        event.get("finish_reason"), event.get("finishReason"),
        event.get("stop_reason"), event.get("stopReason"),
        deep_get(event, ("incomplete_details", "reason"), ("incompleteDetails", "reason")),
        deep_get(response, ("incomplete_details", "reason"), ("incompleteDetails", "reason")),
    ]
    reasons = [_chat_terminal_reason(candidate) for candidate in candidates]
    state = (
        "limited" if any(reason in _CHAT_LIMIT_TERMINAL_REASONS for reason in reasons)
        else ""
    )

    event_type = re.sub(r"[.\s-]+", "_", str(event.get("type") or "").strip().casefold())
    if event_type in {"response_failed", "error"}:
        state = merge_chat_stream_terminal_state(state, "failed")
    elif event_type == "response_incomplete" and state != "limited":
        state = merge_chat_stream_terminal_state(state, "failed")
    elif event_type in {"response_cancelled", "response_canceled"}:
        state = merge_chat_stream_terminal_state(state, "aborted")
    elif event_type == "response_completed":
        state = merge_chat_stream_terminal_state(state, "clean")

    for candidate in (choice.get("finish_reason"), choice.get("finishReason"),
                      event.get("finish_reason"), event.get("finishReason"),
                      event.get("stop_reason"), event.get("stopReason"),
                      event.get("status"), response.get("status")):
        reason = _chat_terminal_reason(candidate)
        if reason in _CHAT_ABORTED_TERMINAL_REASONS:
            state = merge_chat_stream_terminal_state(state, "aborted")
        elif reason in _CHAT_FAILED_TERMINAL_REASONS and not (
            reason == "incomplete" and state == "limited"
        ):
            state = merge_chat_stream_terminal_state(state, "failed")
        elif reason in _CHAT_CLEAN_TERMINAL_REASONS:
            state = merge_chat_stream_terminal_state(state, "clean")
    return state


def merge_chat_stream_terminal_state(current: str, next_state: str) -> str:
    left = current if current in _CHAT_TERMINAL_PRIORITY else ""
    right = next_state if next_state in _CHAT_TERMINAL_PRIORITY else ""
    if not right:
        return left
    if not left:
        return right
    return right if _CHAT_TERMINAL_PRIORITY[right] >= _CHAT_TERMINAL_PRIORITY[left] else left


def final_chat_stream_terminal_state(state: str, done_seen: bool = False) -> str:
    if state in _CHAT_TERMINAL_PRIORITY:
        return state
    # [DONE] only closes SSE framing.  It cannot prove that generation reached
    # a semantic terminal state, so queues still require an explicit finish.
    return "unexpected-eof"


def _route_check_response_parts(value: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """Extract bounded public facts from one Responses payload without retaining text."""
    content: list[str] = []
    reasoning: list[str] = []
    usage: dict[str, Any] = {}

    def item_parts(item: Any) -> None:
        if not isinstance(item, dict):
            return
        for part in item.get("content", []) if isinstance(item.get("content"), list) else []:
            if not isinstance(part, dict):
                continue
            part_type = str(part.get("type") or "")
            text = _benchmark_text_part(part.get("text") or part.get("content"))
            if part_type in {"reasoning_text", "summary_text"}:
                reasoning.append(text)
            elif text:
                content.append(text)
        summary = item.get("summary")
        if isinstance(summary, list):
            reasoning.append(_benchmark_text_part(summary))

    event_type = str(value.get("type") or "")
    delta = value.get("delta")
    if isinstance(delta, str):
        if "reasoning" in event_type or "summary" in event_type:
            reasoning.append(delta)
        elif "output_text" in event_type:
            content.append(delta)
    item_parts(value.get("item"))
    response = value.get("response") if isinstance(value.get("response"), dict) else value
    if isinstance(response.get("usage"), dict):
        usage = response["usage"]
    output = response.get("output")
    if isinstance(output, list):
        for item in output:
            item_parts(item)
    output_text = response.get("output_text")
    if isinstance(output_text, str):
        content.append(output_text)
    return "".join(content), "".join(reasoning), usage


def _merge_route_check_terminal(current: str, incoming: str) -> str:
    return (
        incoming
        if _ROUTE_CHECK_TERMINAL_PRIORITY.get(incoming, 0)
        >= _ROUTE_CHECK_TERMINAL_PRIORITY.get(current, 0)
        else current
    )


def _route_check_terminal_event(
    protocol: str, value: dict[str, Any], *, tool_probe: bool,
) -> str:
    """Classify explicit protocol completion; clean EOF alone is never proof."""
    if protocol == "responses":
        event_type = str(value.get("type") or "").strip().casefold()
        response = value.get("response") if isinstance(value.get("response"), dict) else value
        status = str(response.get("status") or value.get("status") or "").strip().casefold()
        if event_type in {"error", "response.failed"} or status in {"failed", "error"}:
            return "failed"
        if event_type in {"response.incomplete", "response.cancelled", "response.canceled"}:
            return "incomplete"
        if status in {"incomplete", "cancelled", "canceled"}:
            return "incomplete"
        if event_type == "response.completed" or status == "completed":
            return "complete"
        return ""

    state = ""
    for choice_state in _route_check_chat_terminal_events(
        value, tool_probe=tool_probe,
    ).values():
        state = _merge_route_check_terminal(state, choice_state)
    return state


def _route_check_chat_terminal_events(
    value: dict[str, Any], *, tool_probe: bool,
) -> dict[str, str]:
    states: dict[str, str] = {}
    choices = value.get("choices")
    if not isinstance(choices, list):
        choices = []
    for fallback_index, choice in enumerate(choices):
        if not isinstance(choice, dict):
            continue
        choice_index = str(choice.get("index", fallback_index))
        reason = _chat_terminal_reason(
            choice.get("finish_reason", choice.get("finishReason"))
        )
        state = ""
        if reason in _CHAT_LIMIT_TERMINAL_REASONS:
            state = _merge_route_check_terminal(state, "incomplete")
        elif reason in {"tool_calls", "function_call"}:
            state = _merge_route_check_terminal(
                state, "complete" if tool_probe else "failed",
            )
        elif reason in _CHAT_CLEAN_TERMINAL_REASONS:
            state = _merge_route_check_terminal(state, "complete")
        elif reason:
            state = _merge_route_check_terminal(state, "failed")
        if state:
            states[choice_index] = _merge_route_check_terminal(
                states.get(choice_index, ""), state,
            )
    return states


def run_route_check_request(
    plan: LaunchPlan, cancel_event: threading.Event, *, tool_probe: bool = False,
) -> dict[str, Any]:
    """Run a synthetic route request and return only protocol evidence, never generated text."""
    request = build_route_check_request(plan, tool_probe=tool_probe)
    protocol = CLIENT_ADAPTERS[plan.client].protocol
    started = time.monotonic()
    first_output: float | None = None
    content_characters = 0
    reasoning_characters = 0
    tool_calls = _RouteCheckToolCallAssembler(protocol)
    usage: dict[str, Any] = {}
    event_count = 0
    terminal_state = ""
    done_seen = False
    chat_terminal_states: dict[str, str] = {}
    responses_terminal_seen = False
    try:
        response = urllib.request.urlopen(request, timeout=900)
    except urllib.error.HTTPError as error:
        raw = error.read(16_000).decode("utf-8", "replace")
        raise RuntimeError(
            f"The {protocol} probe was rejected with HTTP {error.code}: {raw[:600]}"
        ) from error
    except (OSError, urllib.error.URLError) as error:
        raise RuntimeError(f"The {protocol} probe could not reach the route: {error}") from error

    with response:
        content_type = response.headers.get("Content-Type", "").lower()
        streamed = content_type.startswith("text/event-stream")
        if content_type.startswith("application/json"):
            data = json.loads(response.read(MAX_JSON))
            runtime_error = _openai_error_detail(data)
            if runtime_error:
                raise RuntimeError(f"The {protocol} probe was rejected: {runtime_error}")
            terminal_state = _merge_route_check_terminal(
                terminal_state,
                _route_check_terminal_event(protocol, data, tool_probe=tool_probe),
            )
            if protocol == "chat-completions":
                for choice_index, choice_state in _route_check_chat_terminal_events(
                    data, tool_probe=tool_probe,
                ).items():
                    chat_terminal_states[choice_index] = _merge_route_check_terminal(
                        chat_terminal_states.get(choice_index, ""), choice_state,
                    )
            if protocol == "responses":
                tool_calls.add_responses_payload(data)
                content, reasoning, found_usage = _route_check_response_parts(data)
                content_characters += len(content)
                reasoning_characters += len(reasoning)
                usage = found_usage or usage
            else:
                tool_calls.add_chat_payload(data, streamed=False)
                choice = (data.get("choices") or [{}])[0]
                message = choice.get("message") if isinstance(choice, dict) else {}
                if isinstance(message, dict):
                    content_characters += len(_benchmark_text_part(message.get("content")))
                    reasoning_characters += len(_benchmark_text_part(
                        message.get("reasoning_content") or message.get("reasoning")
                    ))
                usage = data.get("usage") if isinstance(data.get("usage"), dict) else usage
            if content_characters or reasoning_characters or tool_calls.evidence()["toolCallCount"]:
                first_output = time.monotonic() - started
        else:
            for raw_line in response:
                if cancel_event.is_set():
                    raise LaunchCancelled("Route Check stopped.")
                line = raw_line.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload:
                    continue
                if payload == "[DONE]":
                    done_seen = True
                    continue
                if done_seen:
                    raise RuntimeError(
                        f"The {protocol} stream emitted data after its terminal marker."
                    )
                try:
                    event = json.loads(payload)
                except ValueError:
                    raise RuntimeError(
                        f"The {protocol} stream emitted a malformed JSON event."
                    )
                if responses_terminal_seen:
                    raise RuntimeError(
                        "The Responses stream emitted data after its terminal event."
                    )
                if (
                    protocol == "chat-completions" and chat_terminal_states
                    and _chat_cache_value_has_output(event)
                ):
                    raise RuntimeError(
                        "The Chat Completions stream emitted output after its terminal event."
                    )
                event_count += 1
                runtime_error = _openai_error_detail(event)
                if runtime_error:
                    raise RuntimeError(f"The {protocol} stream reported an error: {runtime_error}")
                terminal_state = _merge_route_check_terminal(
                    terminal_state,
                    _route_check_terminal_event(protocol, event, tool_probe=tool_probe),
                )
                event_terminal = _route_check_terminal_event(
                    protocol, event, tool_probe=tool_probe,
                )
                if protocol == "chat-completions":
                    for choice_index, choice_state in _route_check_chat_terminal_events(
                        event, tool_probe=tool_probe,
                    ).items():
                        chat_terminal_states[choice_index] = _merge_route_check_terminal(
                            chat_terminal_states.get(choice_index, ""), choice_state,
                        )
                before = (
                    content_characters + reasoning_characters
                    + int(tool_calls.evidence()["toolCallCount"])
                )
                if protocol == "responses":
                    if event.get("type") in {"error", "response.failed"}:
                        raise RuntimeError("The Responses stream reported a failed event.")
                    tool_calls.add_responses_payload(event)
                    content, reasoning, found_usage = _route_check_response_parts(event)
                    content_characters += len(content)
                    reasoning_characters += len(reasoning)
                    usage = found_usage or usage
                else:
                    tool_calls.add_chat_payload(event, streamed=True)
                    if isinstance(event.get("usage"), dict):
                        usage = event["usage"]
                    choices = event.get("choices")
                    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                        delta = choices[0].get("delta")
                        if not isinstance(delta, dict):
                            delta = choices[0].get("message") if isinstance(choices[0].get("message"), dict) else {}
                        content_characters += len(_benchmark_text_part(delta.get("content")))
                        reasoning_characters += len(_benchmark_text_part(
                            delta.get("reasoning_content") or delta.get("reasoning")
                        ))
                after = (
                    content_characters + reasoning_characters
                    + int(tool_calls.evidence()["toolCallCount"])
                )
                if after > before and first_output is None:
                    first_output = time.monotonic() - started
                if protocol == "responses" and event_terminal:
                    responses_terminal_seen = True
    terminal_complete = terminal_state == "complete" and (
        not streamed or protocol == "responses" or done_seen
    )
    if protocol == "chat-completions":
        terminal_complete = (
            terminal_complete and chat_terminal_states.get("0") == "complete"
        )
    if not terminal_complete and terminal_state == "complete":
        terminal_state = "unexpected-eof"
    elif not terminal_state:
        terminal_state = "unexpected-eof"
    tool_evidence = tool_calls.evidence()
    tool_terminal_complete = terminal_complete
    if tool_probe and protocol == "chat-completions":
        tool_terminal_complete = (
            terminal_complete
            and tool_calls.chat_choice_indexes() == {"0"}
            and chat_terminal_states.get("0") == "complete"
        )
    if tool_probe and not tool_terminal_complete:
        tool_evidence.update({
            "toolCall": False,
            "toolContractValid": False,
            "toolContractDetail": (
                "The tool-call stream did not reach an explicit complete terminal state."
            ),
        })
    elapsed = time.monotonic() - started
    return {
        "protocol": protocol,
        "accepted": True,
        "streamed": streamed and event_count > 0,
        "eventCount": event_count,
        "contentCharacters": content_characters,
        "reasoningCharacters": reasoning_characters,
        **tool_evidence,
        "terminalState": terminal_state,
        "terminalComplete": terminal_complete,
        "thinkingBudgetTokensRequested": (
            32
            if tool_probe and plan.backend == "llamacpp"
            and plan.options.get("_qualificationThinkingBudgetTokens")
            == ROUTE_QUALIFICATION_THINKING_TOKENS
            else None
        ),
        "reasoningBudgetMessageSha256": (
            hashlib.sha256(
                LLAMACPP_QWEN_REASONING_BUDGET_MESSAGE.encode("utf-8")
            ).hexdigest()
            if tool_probe and plan.backend == "llamacpp"
            and plan.options.get("_qualificationThinkingBudgetTokens")
            == ROUTE_QUALIFICATION_THINKING_TOKENS
            else None
        ),
        "usage": _route_check_usage(usage),
        "firstOutputSeconds": round(first_output, 4) if first_output is not None else None,
        "totalSeconds": round(elapsed, 4),
    }


class _RouteCheckToolCallAssembler:
    """Assemble one OpenAI tool call without retaining its arguments in public evidence."""

    def __init__(self, protocol: str) -> None:
        self._protocol = protocol
        self._calls: dict[str, dict[str, Any]] = {}
        self._aliases: dict[str, str] = {}
        self._shape_errors: list[str] = []
        self._next = 0

    def _shape_error(self, detail: str) -> None:
        if detail not in self._shape_errors:
            self._shape_errors.append(detail)

    @staticmethod
    def _aliases_for(
        value: dict[str, Any], *, index: Any = None, item_id: Any = None,
    ) -> list[str]:
        aliases: list[str] = []
        for prefix, candidate in (
            ("id", value.get("id")),
            ("call", value.get("call_id")),
            ("item", item_id),
            ("index", index),
        ):
            if candidate is not None and str(candidate):
                aliases.append(f"{prefix}:{candidate}")
        return aliases

    @staticmethod
    def _merge_fragment(current: str, incoming: str) -> str:
        if not incoming:
            return current
        if not current or incoming.startswith(current):
            return incoming
        if current.startswith(incoming) or incoming == current:
            return current
        return current + incoming

    def _merge_calls(self, keep: str, discard: str) -> None:
        if keep == discard:
            return
        keep_aliases = {
            alias for alias, target in self._aliases.items() if target == keep
        }
        discard_aliases = {
            alias for alias, target in self._aliases.items() if target == discard
        }
        first = self._calls[keep]
        second = self._calls.pop(discard)
        first["name"] = self._merge_fragment(first["name"], second["name"])
        if first["argumentsFinal"] and second["argumentsFinal"]:
            if first["arguments"] != second["arguments"]:
                first["conflict"] = True
        elif second["argumentsFinal"]:
            first["arguments"] = second["arguments"]
            first["argumentsFinal"] = True
        elif not first["argumentsFinal"]:
            first["arguments"] += second["arguments"]
        first["conflict"] = first["conflict"] or second["conflict"]
        first["identityConflict"] = (
            first["identityConflict"] or second["identityConflict"]
            or any(
                len({
                    alias for alias in keep_aliases | discard_aliases
                    if alias.startswith(f"{prefix}:")
                }) > 1
                for prefix in ("id", "call", "item")
            )
        )
        first["positionConflict"] = (
            first["positionConflict"] or second["positionConflict"]
            or len({
                alias for alias in keep_aliases | discard_aliases
                if alias.startswith("index:")
            }) > 1
        )
        for field in (
            "chatIdSeen", "chatTypeSeen", "functionWrapperSeen",
            "responsesCallIdSeen", "responsesItemIdSeen",
        ):
            first[field] = first[field] or second[field]
        first["chatChoiceIndexes"].update(second["chatChoiceIndexes"])
        for alias, canonical in list(self._aliases.items()):
            if canonical == discard:
                self._aliases[alias] = keep

    def _call(self, aliases: list[str]) -> dict[str, Any]:
        known = list(dict.fromkeys(
            self._aliases[alias] for alias in aliases if alias in self._aliases
        ))
        if known:
            canonical = known[0]
            for duplicate in known[1:]:
                self._merge_calls(canonical, duplicate)
        else:
            canonical = f"tool:{self._next}"
            self._next += 1
            self._calls[canonical] = {
                "name": "", "arguments": "", "argumentsFinal": False,
                "conflict": False, "identityConflict": False,
                "positionConflict": False,
                "chatIdSeen": False, "chatTypeSeen": False,
                "functionWrapperSeen": False,
                "responsesCallIdSeen": False, "responsesItemIdSeen": False,
                "chatChoiceIndexes": set(),
            }
        call = self._calls[canonical]
        bound_aliases = {
            alias for alias, target in self._aliases.items() if target == canonical
        }
        for alias in aliases:
            prefix = alias.split(":", 1)[0]
            if prefix in {"id", "call", "item", "index"} and any(
                existing != alias and existing.startswith(f"{prefix}:")
                for existing in bound_aliases
            ):
                if prefix == "index":
                    call["positionConflict"] = True
                else:
                    call["identityConflict"] = True
        for alias in aliases:
            self._aliases[alias] = canonical
        return call

    def add(
        self, value: Any, *, index: Any = None, item_id: Any = None,
        arguments_final: bool = False, name_delta: bool = False,
    ) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            self._shape_error("A tool-call entry was not a JSON object.")
            return None
        function = value.get("function") if isinstance(value.get("function"), dict) else value
        aliases = self._aliases_for(value, index=index, item_id=item_id)
        if not aliases:
            aliases = self._aliases_for(function, index=index, item_id=item_id)
        call = self._call(aliases)
        name = function.get("name")
        if name is not None:
            if name_delta:
                # Chat Completions emits name fragments, not cumulative snapshots.
                call["name"] += str(name)
            else:
                call["name"] = self._merge_fragment(call["name"], str(name))
        arguments = function.get("arguments")
        if arguments is None:
            return call
        if not isinstance(arguments, str):
            self._shape_error("Tool-call arguments must be a JSON string on the wire.")
            return call
        incoming = arguments
        if arguments_final:
            if call["argumentsFinal"] and call["arguments"] != incoming:
                call["conflict"] = True
            elif incoming or not call["arguments"]:
                call["arguments"] = incoming
            call["argumentsFinal"] = True
        elif call["argumentsFinal"]:
            call["conflict"] = True
        else:
            call["arguments"] += incoming
        return call

    def add_chat_payload(self, value: dict[str, Any], *, streamed: bool) -> None:
        choices = value.get("choices")
        if not isinstance(choices, list):
            return
        for fallback_choice_index, choice in enumerate(choices):
            if not isinstance(choice, dict):
                continue
            choice_index = choice.get("index", fallback_choice_index)
            message = choice.get("delta") if streamed else choice.get("message")
            if not isinstance(message, dict):
                message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
            calls = message.get("tool_calls")
            if not isinstance(calls, list):
                if "tool_calls" in message:
                    self._shape_error(
                        "A Chat Completions tool_calls field was not an array."
                    )
                continue
            for fallback_index, call in enumerate(calls):
                if not isinstance(call, dict):
                    self._shape_error("A Chat Completions tool-call entry was not an object.")
                    continue
                raw_index = call.get("index")
                if streamed and (
                    isinstance(raw_index, bool) or not isinstance(raw_index, int)
                    or raw_index < 0
                ):
                    self._shape_error(
                        "A streamed Chat Completions tool-call chunk had no valid index."
                    )
                call_index = raw_index if isinstance(raw_index, int) else fallback_index
                call_id = call.get("id")
                id_seen = isinstance(call_id, str) and bool(call_id)
                if "id" in call and not id_seen:
                    self._shape_error("A Chat Completions tool-call ID was malformed.")
                call_type = call.get("type")
                type_seen = call_type == "function"
                if "type" in call and not type_seen:
                    self._shape_error(
                        "A Chat Completions tool call did not use type function."
                    )
                function = call.get("function")
                wrapper_seen = isinstance(function, dict)
                if not wrapper_seen:
                    self._shape_error(
                        "A Chat Completions tool-call chunk had no function wrapper."
                    )
                    function = {}
                if "name" in function and not isinstance(function.get("name"), str):
                    self._shape_error("A Chat Completions function name was malformed.")
                if "arguments" in function and not isinstance(function.get("arguments"), str):
                    self._shape_error(
                        "Chat Completions function arguments were not a JSON string."
                    )
                normalized = {**call, "function": function}
                record = self.add(
                    normalized, index=f"{choice_index}:{call_index}",
                    arguments_final=not streamed, name_delta=streamed,
                )
                if record is not None:
                    record["chatIdSeen"] = record["chatIdSeen"] or id_seen
                    record["chatTypeSeen"] = record["chatTypeSeen"] or type_seen
                    record["functionWrapperSeen"] = (
                        record["functionWrapperSeen"] or wrapper_seen
                    )
                    record["chatChoiceIndexes"].add(str(choice_index))

    def add_responses_payload(self, value: dict[str, Any]) -> None:
        event_type = str(value.get("type") or "")
        if event_type in {
            "response.function_call_arguments.delta",
            "response.function_call_arguments.done",
        }:
            output_index = value.get("output_index")
            if (
                isinstance(output_index, bool) or not isinstance(output_index, int)
                or output_index < 0
            ):
                self._shape_error(
                    "A Responses function-argument event had no valid output index."
                )
            if not isinstance(value.get("item_id"), str) or not value.get("item_id"):
                self._shape_error(
                    "A Responses function-argument event had no valid item ID."
                )
            arguments = value.get("arguments") if event_type.endswith(".done") else value.get("delta")
            if not isinstance(arguments, str):
                self._shape_error(
                    "A Responses function-argument event did not contain a string fragment."
                )
            synthetic = {
                "call_id": value.get("call_id"),
                "arguments": arguments if isinstance(arguments, str) else "",
            }
            record = self.add(
                synthetic, index=value.get("output_index"), item_id=value.get("item_id"),
                arguments_final=event_type.endswith(".done"),
            )
            if record is not None and isinstance(value.get("call_id"), str) and value.get("call_id"):
                record["responsesCallIdSeen"] = True

        item = value.get("item")
        if isinstance(item, dict) and str(item.get("type") or "") in {"function_call", "tool_call"}:
            output_index = value.get("output_index")
            if event_type in {"response.output_item.added", "response.output_item.done"} and (
                isinstance(output_index, bool) or not isinstance(output_index, int)
                or output_index < 0
            ):
                self._shape_error("A Responses function item had no valid output index.")
            if item.get("type") != "function_call":
                self._shape_error("A Responses tool item did not use type function_call.")
            if not isinstance(item.get("id"), str) or not item.get("id"):
                self._shape_error("A Responses function item had no valid item ID.")
            if not isinstance(item.get("call_id"), str) or not item.get("call_id"):
                self._shape_error("A Responses function item had no valid call ID.")
            if "name" in item and not isinstance(item.get("name"), str):
                self._shape_error("A Responses function name was malformed.")
            if "arguments" in item and not isinstance(item.get("arguments"), str):
                self._shape_error("Responses function arguments were not a JSON string.")
            record = self.add(
                item, index=value.get("output_index"), item_id=item.get("id"),
                arguments_final=event_type == "response.output_item.done",
            )
            if record is not None:
                record["responsesCallIdSeen"] = (
                    record["responsesCallIdSeen"]
                    or isinstance(item.get("call_id"), str) and bool(item.get("call_id"))
                )
                record["responsesItemIdSeen"] = (
                    record["responsesItemIdSeen"]
                    or isinstance(item.get("id"), str) and bool(item.get("id"))
                )

        response = value.get("response") if isinstance(value.get("response"), dict) else value
        output = response.get("output") if isinstance(response, dict) else None
        if isinstance(output, list):
            for output_index, output_item in enumerate(output):
                if (
                    isinstance(output_item, dict)
                    and str(output_item.get("type") or "") in {"function_call", "tool_call"}
                ):
                    if output_item.get("type") != "function_call":
                        self._shape_error(
                            "A Responses output item did not use type function_call."
                        )
                    if not isinstance(output_item.get("id"), str) or not output_item.get("id"):
                        self._shape_error("A Responses output item had no valid item ID.")
                    if (
                        not isinstance(output_item.get("call_id"), str)
                        or not output_item.get("call_id")
                    ):
                        self._shape_error("A Responses output item had no valid call ID.")
                    if "name" in output_item and not isinstance(output_item.get("name"), str):
                        self._shape_error("A Responses function name was malformed.")
                    if "arguments" in output_item and not isinstance(output_item.get("arguments"), str):
                        self._shape_error("Responses function arguments were not a JSON string.")
                    record = self.add(
                        output_item, index=output_index, item_id=output_item.get("id"),
                        arguments_final=True,
                    )
                    if record is not None:
                        record["responsesCallIdSeen"] = (
                            record["responsesCallIdSeen"]
                            or isinstance(output_item.get("call_id"), str)
                            and bool(output_item.get("call_id"))
                        )
                        record["responsesItemIdSeen"] = (
                            record["responsesItemIdSeen"]
                            or isinstance(output_item.get("id"), str)
                            and bool(output_item.get("id"))
                        )

    def evidence(self) -> dict[str, Any]:
        calls = list(self._calls.values())
        count = len(calls)
        name_seen = any(call["name"] == ROUTE_CHECK_TOOL_NAME for call in calls)
        valid = False
        if count != 1:
            detail = (
                "The route did not emit the required tool call."
                if count == 0 else
                f"The route emitted {count} tool calls; exactly one is required."
            )
        else:
            call = calls[0]
            if self._shape_errors:
                detail = self._shape_errors[0]
            elif self._protocol == "chat-completions" and not (
                call["chatIdSeen"] and call["chatTypeSeen"]
                and call["functionWrapperSeen"]
            ):
                detail = (
                    "The Chat Completions tool call was missing its required ID, "
                    "function type, or function wrapper."
                )
            elif self._protocol == "responses" and not (
                call["responsesCallIdSeen"] and call["responsesItemIdSeen"]
            ):
                detail = (
                    "The Responses function call was missing its required item ID or call ID."
                )
            elif self._protocol == "responses" and not call["argumentsFinal"]:
                detail = (
                    "The Responses function call never reached a final argument event or output item."
                )
            elif call["name"] != ROUTE_CHECK_TOOL_NAME:
                detail = "The route selected a different tool than the synthetic route-check tool."
            elif call["identityConflict"]:
                detail = "The route reused one tool position with conflicting call identifiers."
            elif call["positionConflict"]:
                detail = "The route reused one tool-call ID across different output positions."
            elif call["conflict"]:
                detail = "The route returned conflicting argument payloads for the tool call."
            else:
                try:
                    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                        value: dict[str, Any] = {}
                        for key, item in pairs:
                            if key in value:
                                raise ValueError("duplicate JSON object key")
                            value[key] = item
                        return value

                    arguments = json.loads(
                        call["arguments"], object_pairs_hook=unique_object,
                    )
                except (TypeError, ValueError):
                    detail = "The route-check tool arguments were not valid JSON."
                else:
                    if arguments != {"status": "ready"}:
                        detail = "The route-check tool arguments did not exactly match the required status contract."
                    else:
                        valid = True
                        detail = "The route emitted exactly one route-check tool call with the required arguments."
        return {
            "toolCall": valid,
            "toolContractValid": valid,
            "toolCallCount": count,
            "toolNameSeen": name_seen,
            "toolContractDetail": detail,
        }

    def chat_choice_indexes(self) -> set[str]:
        calls = list(self._calls.values())
        return set(calls[0]["chatChoiceIndexes"]) if len(calls) == 1 else set()


class FrozenChatRelay:
    def stream_chat(self, request: urllib.request.Request) -> None:
        """Relay a private upstream stream without exposing its API key."""
        observation_context = getattr(request, "_launcher_cache_context", None)
        started = time.monotonic()
        first_output_at: float | None = None
        last_usage: dict[str, Any] | None = None
        output_observed = False
        terminal_state = ""
        done_seen = False
        upstream_interrupted = False
        browser_interrupted = False
        try:
            response = urllib.request.urlopen(request, timeout=900)
        except urllib.error.HTTPError as error:
            try:
                raw = error.read(16_000).decode("utf-8", "replace")
                parsed = json.loads(raw)
                detail = deep_get(parsed, ("error", "message"), ("message",))
                message = str(detail or raw or error.reason)[:800]
            except (OSError, ValueError, UnicodeError):
                message = str(error.reason)
            raise RuntimeError(f"The model rejected the chat request (HTTP {error.code}): {message}") from error
        except (OSError, urllib.error.URLError) as error:
            raise RuntimeError(f"Could not reach the active model for chat: {error}") from error

        content_type = response.headers.get("Content-Type", "text/event-stream; charset=utf-8")
        if not (
            content_type.lower().startswith("text/event-stream")
            or content_type.lower().startswith("application/json")
        ):
            content_type = "text/event-stream; charset=utf-8"
        is_sse = content_type.lower().startswith("text/event-stream")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        self.close_connection = True
        try:
            with response:
                while True:
                    try:
                        line = response.readline()
                    except (ConnectionResetError, TimeoutError, OSError):
                        upstream_interrupted = True
                        break
                    if not line:
                        break
                    try:
                        self.wfile.write(line)
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
                        browser_interrupted = True
                        break
                    try:
                        decoded = line.decode("utf-8", "replace").strip()
                        payload_text = decoded[5:].strip() if decoded.startswith("data:") else decoded
                        if payload_text == "[DONE]":
                            done_seen = True
                            continue
                        if not payload_text:
                            continue
                        event = json.loads(payload_text)
                        terminal_state = merge_chat_stream_terminal_state(
                            terminal_state, chat_stream_terminal_state(event),
                        )
                        facts = chat_cache_observation_event(event)
                        if facts.get("outputObserved") is True:
                            output_observed = True
                            if first_output_at is None:
                                first_output_at = time.monotonic() - started
                        if isinstance(facts.get("usage"), dict):
                            last_usage = facts["usage"]
                    except (TypeError, ValueError, UnicodeError):
                        # The relay remains byte-for-byte authoritative. An
                        # unrecognised line merely leaves observability unknown.
                        pass
        except (ConnectionResetError, TimeoutError, OSError):
            upstream_interrupted = True

        final_terminal_state = final_chat_stream_terminal_state(terminal_state, done_seen)
        if upstream_interrupted:
            final_terminal_state = merge_chat_stream_terminal_state(
                final_terminal_state, "failed",
            )
        if (
            is_sse and not browser_interrupted
            and (upstream_interrupted or final_terminal_state == "unexpected-eof")
        ):
            message = (
                "The upstream model stream failed before reporting a clean completion."
                if upstream_interrupted else
                "The model stream ended before reporting a clean completion."
            )
            frame = (
                "\n\ndata: " + json.dumps({
                    "type": "launcher.stream_error", "error": {"message": message},
                }, ensure_ascii=False, separators=(",", ":")) + "\n\n"
            ).encode("utf-8")
            try:
                self.wfile.write(frame)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
                browser_interrupted = True
        total = time.monotonic() - started
        completed = final_terminal_state == "clean" and not browser_interrupted
        interrupted = bool(
            browser_interrupted
            or final_terminal_state in {"failed", "aborted", "unexpected-eof"}
        )
        MANAGER.record_chat_cache_observation(observation_context, {
            "completed": completed,
            "interrupted": interrupted,
            "outputObserved": output_observed,
            "promptTokens": last_usage.get("promptTokens") if last_usage else None,
            "completionTokens": last_usage.get("completionTokens") if last_usage else None,
            "cacheTelemetryReported": (
                last_usage.get("cacheTelemetryReported") is True if last_usage else False
            ),
            "cachedPromptTokens": last_usage.get("cachedPromptTokens") if last_usage else None,
            "ttftSeconds": first_output_at,
            "totalSeconds": total,
        })

