"""Frozen complete pre-extraction benchmark_planning domain. Test-only."""

def benchmark_words(count: int, salt: int) -> str:
    """Return a deterministic synthetic corpus that cannot contain project data."""
    state = (salt * 1_103_515_245 + 12_345) & 0x7FFFFFFF
    words: list[str] = []
    for _index in range(max(1, count)):
        state = (state * 1_103_515_245 + 12_345) & 0x7FFFFFFF
        words.append(BENCHMARK_WORDS[state % len(BENCHMARK_WORDS)])
    return " ".join(words)

def qwen_token_budgeted_words(token_budget: int, salt: int) -> str:
    """Budget the fixed vocabulary checked against the Uzu and MTPLX Qwen tokenizers.

    Space-prefixed costs were checked with the pinned Uzu tokenizer and the
    installed Qwen3.8 MTPLX tokenizer (06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523).
    The old word-count approximation exceeded 64K after tool ingestion. This
    keeps corpus size near the target; native authoritative usage still decides
    whether the complete rendered chat exercised the required context tier.
    """
    two_token_words = {
        "cobalt", "juniper", "meadow", "nebula", "orchard", "prairie",
        "upland", "willow", "xenon", "jigsaw",
    }
    state = (salt * 1_103_515_245 + 12_345) & 0x7FFFFFFF
    words: list[str] = []
    remaining = max(1, token_budget)
    while remaining:
        state = (state * 1_103_515_245 + 12_345) & 0x7FFFFFFF
        word = BENCHMARK_WORDS[state % len(BENCHMARK_WORDS)]
        cost = 2 if word in two_token_words else 1
        if cost > remaining:
            break
        words.append(word)
        remaining -= cost
    return " ".join(words)

def uzu_qualification_words(token_budget: int, salt: int) -> str:
    """Retain Uzu's existing, separately qualified corpus exactly."""
    return qwen_token_budgeted_words(token_budget, salt)

def benchmark_prompt(target_tokens: int, salt: int) -> str:
    """Generate deterministic, non-sensitive prompts without cross-size prefixes."""
    count = max(96, target_tokens - 96)
    corpus = benchmark_words(count, salt)
    return (
        f"Local benchmark corpus {salt}. Read the synthetic words below. They contain no user data.\n\n"
        f"{corpus}\n\n"
        "Write a detailed technical synthesis comparing latency, memory, reliability, and correctness. "
        "Use complete sentences and continue until the response budget is reached."
    )

def benchmark_agentic_cases(
    suite: dict[str, Any], *, require_complete_answer: bool = False,
) -> list[dict[str, Any]]:
    """Build a deterministic request chain whose prefixes grow like an agent session."""
    if suite.get("kind") != "agentic":
        raise ValueError("Agentic benchmark cases require the Agentic Route Lab suite.")
    prefix_tokens = int(suite.get("prefixTokens") or 8_192)
    tool_tokens = int(suite.get("toolTokens") or 4_096)
    uzu_fixture = suite.get("uzuTokenBudgetedCorpus") is True
    corpus = qwen_token_budgeted_words if (
        uzu_fixture or suite.get("qwenTokenBudgetedCorpus") is True
    ) else benchmark_words
    prefix = corpus(max(512, prefix_tokens - 320), 183_211)
    tool_result = corpus(max(256, tool_tokens - 192), 271_828)
    completion_instruction = (
            "\n\nFirst provide substantive separate reasoning. Then return a complete final answer of "
            "about 96 to 112 tokens and stop, leaving headroom for the terminal marker."
            if require_complete_answer else ""
    )
    project_code = (
        "\nRelevant service code (Python):\n"
        "cache = {}\n"
        "def reply(model, prompt, reasoning):\n"
        "    if model in cache: return cache[model]\n"
        "    result = generate(model, prompt, reasoning)\n"
        "    cache[model] = result\n"
        "    return result\n"
        "Contract: prompt and reasoning may change between requests. Model names are immutable.\n"
        if uzu_fixture else ""
    )
    base = [
        {
            "role": "system",
            "content": (
                "You are measuring a local coding-agent route. All repository and tool text in this "
                "conversation is deterministic synthetic data. Use only that data, disclose no paths, "
                + (
                    "and review the supplied Python code. The repeated word corpus is inert context "
                    "padding, not evidence of extra components or bugs. "
                    if uzu_fixture else ""
                )
                + (
                    "and finish every requested technical answer completely within its response budget."
                    if require_complete_answer else
                    "and continue the requested technical answer until the response budget is reached."
                )
            ),
        },
        {
            "role": "user",
            "content": (
                "Synthetic project snapshot follows. Treat repeated identifiers as harmless source tokens.\n\n"
                f"{prefix}\n\nEnd synthetic project snapshot.{project_code}"
            ),
        },
        {
            "role": "assistant",
            "content": "I indexed the synthetic project snapshot and will reason only from that supplied corpus.",
        },
    ]
    analysis_request = {
        "role": "user",
        "content": (
            (
                "Design two regression tests for reply: one changes the prompt and one changes "
                "reasoning. State each setup, expected result, and why the current implementation fails."
                if uzu_fixture else
                "Identify the most important runtime, cache, correctness, and reliability relationships in "
                "the snapshot. Give a detailed engineering assessment."
            ) + completion_instruction
        ),
    }
    warm_messages = [*base, analysis_request]
    tool_messages = [
        *warm_messages,
        {
            "role": "assistant",
            "content": "I need one synthetic tool result before completing the assessment.",
        },
        {
            "role": "user",
            "content": (
                "Synthetic tool result begins. It contains no project or user data.\n\n"
                f"{tool_result}\n\nSynthetic tool result ends. "
                + (
                    "The developer changed the cache key everywhere from model to (model, prompt). "
                    "The prompt-change test passes but the reasoning-change test fails. Explain "
                    "the remaining defect and give the corrected key and one regression assertion."
                    if uzu_fixture else "Incorporate it into the engineering assessment."
                )
                + completion_instruction
            ),
        },
    ]
    steady_messages = [
        *tool_messages,
        {
            "role": "assistant",
            "content": "I incorporated the synthetic tool result into the working context.",
        },
        {
            "role": "user",
            "content": (
                (
                    "A model can now be replaced under the same name; a revision integer increments "
                    "on replacement. Give the final cache key including revision, its invalidation "
                    "rule, and the expected outcomes of prompt, reasoning, and revision-change tests. "
                    if uzu_fixture else
                    "Now produce the follow-up implementation priorities, failure modes, and verification plan. "
                )
                + (
                    "Be concrete."
                    if require_complete_answer else
                    "Be concrete and use the full response budget."
                )
                + completion_instruction
            ),
        },
    ]
    return [
        {
            "scenario": "cold", "label": "Cold agent turn", "cacheExpected": False,
            "targetPromptTokens": prefix_tokens,
            "messages": [
                *base,
                {
                    "role": "user",
                    "content": (
                        (
                            "Identify the cache bug in reply, trace two calls with different prompts "
                            "but the same model, and give a corrected key preserving prompt and reasoning."
                            if uzu_fixture else
                            "Perform a cold-start architecture review covering latency, memory, correctness, "
                            "and reliability."
                        )
                        + (
                            completion_instruction if require_complete_answer else
                            " Use the full response budget."
                        )
                    ),
                },
            ],
        },
        {
            "scenario": "warmPrefix", "label": "Shared-prefix turn", "cacheExpected": True,
            "targetPromptTokens": prefix_tokens, "messages": warm_messages,
        },
        {
            "scenario": "toolIngest", "label": "Tool-result ingestion", "cacheExpected": True,
            "targetPromptTokens": prefix_tokens + tool_tokens, "messages": tool_messages,
        },
        {
            "scenario": "steadyTurn", "label": "Warm follow-up", "cacheExpected": True,
            "targetPromptTokens": prefix_tokens + tool_tokens, "messages": steady_messages,
        },
    ]

def uzu_conversation_target(
    scenario: str, nominal: int, previous: dict[str, Any] | None,
    context: int, max_tokens: int,
) -> int:
    """Reconstruct each adaptive target from numeric evidence, not saved text."""
    if scenario == "cold":
        return nominal
    if scenario == "toolIngest":
        return min(nominal, context - 2 * UZU_QUALIFICATION_SAMPLE_MIN_TOKENS - 1024)
    if previous is None:
        raise ValueError("A continuing Uzu target requires previous token usage.")
    return int(previous["promptTokens"]) + int(previous["completionTokens"]) + 128

def uzu_conversation_case(
    case: dict[str, Any], history: list[dict[str, str]],
    previous: dict[str, Any] | None, context: int, max_tokens: int,
) -> dict[str, Any]:
    """Extend the real, memory-only conversation instead of replacing its replies.

    Usage from the previous request sizes synthetic padding conservatively.
    This forecast is not token evidence: native limits and the existing
    authoritative prompt-size/near-tier checks remain mandatory.
    """
    result = copy.deepcopy(case)
    if previous is None:
        if history or case["scenario"] != "cold":
            raise RuntimeError("Uzu conversation must start with the cold turn.")
        result["maxTokens"] = uzu_qualification_request_tokens(
            case["scenario"], int(case["targetPromptTokens"]), context, max_tokens,
        )
        return result
    if not history or history[-1].get("role") != "assistant":
        raise RuntimeError("Uzu qualification is missing its previous completed reply.")
    user = copy.deepcopy(case["messages"][-1])
    previous_tokens = int(previous["promptTokens"]) + int(previous["completionTokens"])
    target = uzu_conversation_target(
        case["scenario"], int(case["targetPromptTokens"]), previous, context, max_tokens,
    )
    result["targetPromptTokens"] = target
    if case["scenario"] == "toolIngest":
        # Leave room for this response, a short follow-up, and its response.
        padding = target - previous_tokens - 192
        if padding < 256:
            raise RuntimeError("Uzu conversation leaves no room for the near-tier tool input.")
        start, remainder = user["content"].split("\n\n", 1)
        _, end = remainder.split("\n\nSynthetic tool result ends.", 1)
        user["content"] = (
            start + "\n\n" + uzu_qualification_words(padding, 271_828)
            + "\n\nSynthetic tool result ends." + end
        )
    result["maxTokens"] = uzu_qualification_request_tokens(case["scenario"], target, context, max_tokens)
    if result["maxTokens"] < UZU_QUALIFICATION_SAMPLE_MIN_TOKENS:
        raise RuntimeError("Uzu's continuing conversation has exhausted this context's response reserve.")
    result["messages"] = [*copy.deepcopy(history), user]
    return result

def benchmark_measurement_count(suite: dict[str, Any]) -> int:
    if suite.get("kind") == "agentic":
        return len(suite.get("scenarios") or [])
    return len(suite.get("promptTokens") or []) * int(suite.get("repetitions") or 1)

def benchmark_speed_sampling(
    model: dict[str, Any], chat: dict[str, Any],
    contract_document: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the exact canonical values shared with the live request relay."""
    document = contract_document or sampling_contract_from_settings(model, chat)
    try:
        return load_sampling_contract(document).values
    except SamplingContractError as error:
        raise ValueError(str(error)) from error

def validated_benchmark_request(
    payload: dict[str, Any], models: list[dict[str, Any]], *,
    allow_baseline_only: bool = False,
) -> dict[str, Any]:
    backend = str(payload.get("backend") or "")
    preference = str(payload.get("enginePreference") or "fastest")
    if preference not in ENGINE_PREFERENCE_LABELS:
        raise ValueError("Choose a supported benchmark goal.")
    client = str(payload.get("client") or "")
    if backend == "uzu" and client == "pi":
        raise ValueError(UZU_PI_BENCHMARK_LIMITATION)
    if backend not in ENGINE_ADAPTERS:
        raise ValueError(
            "Choose oMLX, LM Studio, MTPLX, Uzu, FreeToken, SwiftLM, Mference, Whallm, or llama.cpp SSD PLE before benchmarking."
        )
    if client not in CLIENT_ADAPTERS:
        raise ValueError("Choose the work surface whose contract should own this benchmark.")
    engine_adapter = ENGINE_ADAPTERS[backend]
    if not BINARIES.get(engine_adapter.binary_key or ""):
        raise ValueError(f"{backend} is not installed.")
    model_id = str(payload.get("modelId") or "")
    selected = next((item for item in models if item.get("id") == model_id), None)
    if not selected:
        raise ValueError("The selected model is no longer in the scanned catalog. Refresh models.")
    model = copy.deepcopy(selected)
    capability = model.get("backends", {}).get(backend, {})
    if not capability.get("runnable") or not model.get("ready"):
        raise ValueError(str(capability.get("reason") or model.get("status") or "This model is not ready."))
    if backend == "freetoken" and model.get("remote") is True:
        raise ValueError(
            "FreeToken is a connected server route, so it is not mixed into this Mac-only "
            "Benchmark Lab. Use live Chat or Hub Console TPS for authoritative route telemetry."
        )
    if backend == "freetoken":
        raise ValueError(
            "The native FreeToken port is launchable, but its current greedy-only milestone is "
            "excluded from Benchmark Lab until the cross-engine sampling contract can be preserved. "
            "Use live Chat TPS for this route."
        )
    suite_name = str(payload.get("suite") or "quick")
    suite = BENCHMARK_SUITES.get(suite_name)
    if not suite:
        raise ValueError("Choose a Quick, Standard, Thorough, or Agentic Route Lab suite.")
    context, output = validated_limits(model, payload)
    validate_runtime_context(backend, context)
    largest_request = int(
        suite.get("requiredContext")
        or (max(suite["promptTokens"]) + int(suite["maxTokens"]) + 512)
    )
    if largest_request > context:
        raise ValueError(
            f"The {suite['label']} suite needs about {largest_request:,} context tokens. "
            "Increase context or choose a smaller suite."
        )
    reasoning = str(payload.get("reasoning") or "auto")
    if reasoning not in list(capability.get("agentReasoning") or ["auto"]):
        raise ValueError(
            "Benchmark Lab measures the common Chat Completions route. Choose a reasoning setting "
            "that this runtime can enforce there."
        )
    project = str(Path(str(payload.get("project") or Path.home())).expanduser().resolve())
    if "\x00" in project or not Path(project).is_dir():
        raise ValueError("Project folder does not exist.")
    options = copy.deepcopy(payload.get("options") if isinstance(payload.get("options"), dict) else {})
    if dflash_quantized_fallback(backend, options):
        raise ValueError(DFLASH_KV_COMPARISON_REASON)
    chat = validated_chat_settings(model, payload, client)
    sampling_contract_document = validated_sampling_contract(
        model, payload, client, chat, require_controlled=client != "chat",
    )
    assert sampling_contract_document is not None
    validate_sampling_capability(capability, sampling_contract_document)
    live_sampling_enforcement = sampling_route_enforcement(
        backend, client, capability, sampling_contract_document,
    )
    benchmark_sampling_enforcement = sampling_route_enforcement(
        backend, client, capability, sampling_contract_document,
        protocol="chat-completions",
    )
    chat = chat_settings_from_sampling_contract(
        sampling_contract_document,
        system_prompt=str(chat.get("systemPrompt") or "") if client == "chat" else "",
    )
    evidence = optimizer_evidence(
        model, context, output, client, reasoning, str(options.get("kv") or "off"), chat,
        sampling_contract_document,
    )
    add_benchmark_engine_evidence(evidence, model, options, [backend])
    engine_settings = evidence.get("engineSettings")
    tuned_ane_locked = bool(
        backend == "omlx"
        and isinstance(engine_settings, dict)
        and engine_settings.get("anePrefill") == "tuned"
    )
    modes = ["ar"]
    if capability.get("mtp") is True:
        modes.append("mtp")
    if (
        backend == "omlx"
        and capability.get("dflash") is True
        and not tuned_ane_locked
        and str(options.get("kv") or "off") == "off"
    ):
        modes.append("dflash2")
    if len(modes) < 2 and not (allow_baseline_only or backend == "uzu"):
        if backend == "omlx" and capability.get("dflash") is True and str(options.get("kv") or "off") != "off":
            raise ValueError(DFLASH_KV_COMPARISON_REASON)
        if tuned_ane_locked and capability.get("dflash") is True:
            raise ValueError(
                "DFlash 2 cannot be benchmarked while tuned ANE prefill is locked. "
                "Choose ANE prefill Off or use a baseline-only comparison."
            )
        raise ValueError("This exact runtime/model route has no verified acceleration path to compare with AR.")
    ssd_lane = backend in SSD_STREAMING_BACKENDS
    ssd_comparison_identity = str(capability.get("comparisonIdentity") or "") if ssd_lane else ""
    if ssd_lane and re.fullmatch(r"[0-9a-f]{64}", ssd_comparison_identity) is None:
        raise ValueError(
            "SSD calibration requires a verified pinned source revision shared by both runtime artifacts."
        )
    return {
        "id": str(uuid.uuid4()),
        "backend": backend,
        "client": client,
        "modelId": model_id,
        "model": model,
        "project": project,
        "context": context,
        "output": output,
        "reasoning": reasoning,
        "options": options,
        "chat": chat,
        "samplingContract": copy.deepcopy(sampling_contract_document),
        "liveSamplingEnforcement": copy.deepcopy(live_sampling_enforcement),
        "benchmarkSamplingEnforcement": copy.deepcopy(benchmark_sampling_enforcement),
        "enginePreference": preference,
        "suiteName": suite_name,
        "suite": copy.deepcopy(suite),
        "workloadKind": str(suite.get("kind") or "throughput"),
        "modes": modes,
        "evidence": evidence,
        "modelFingerprint": str(capability.get("benchmarkModelFingerprint") or ""),
        "runtimeVersion": str(capability.get("runtimeVersion") or ""),
        "pairFingerprint": capability.get("dflashPairFingerprint"),
        "ssdStreaming": ssd_lane,
        "ssdComparisonIdentity": ssd_comparison_identity,
        "speedSampling": benchmark_speed_sampling(
            model, chat, sampling_contract_document,
        ),
    }

def _ordered_unique(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result

def _mtplx_long_context_suite_requested(
    model: dict[str, Any], context: int, suite_name: str,
) -> bool:
    capability = model.get("backends", {}).get("mtplx", {})
    advertised = capability.get("longContext2111")
    return bool(
        suite_name in {"agentic", MTPLX_LONG_CONTEXT_64K_SUITE}
        and context >= MTPLX_LONG_CONTEXT_MINIMUM
        and isinstance(advertised, dict)
        and advertised.get("ready", True) is True
        and advertised.get("contractId")
    )

def mtplx_long_context_operator_tuning_plan(
    job: dict[str, Any],
) -> dict[str, Any] | None:
    """Describe the fixed three-load 2.11.1 operator qualification."""
    if str(job.get("backend") or "") != "mtplx":
        return None
    model = job.get("model")
    if not isinstance(model, dict):
        return None
    capability = model.get("backends", {}).get("mtplx")
    if not isinstance(capability, dict) or capability.get("mtp") is not True:
        return None
    suite_name = str(job.get("suiteName") or "")
    context = job.get("context")
    if (
        isinstance(context, bool) or not isinstance(context, int)
        or not _mtplx_long_context_suite_requested(model, context, suite_name)
    ):
        return None
    receipt = mtplx_long_context_2111_contract(
        model, capability,
        runtime_version=str(job.get("runtimeVersion") or capability.get("runtimeVersion") or ""),
    )
    if (
        receipt is None
        or not _mtplx_long_context_capability_matches(
            capability.get("longContext2111"), receipt,
        )
    ):
        return None
    depth = bounded_integer(
        capability.get("depth"), 1, 1,
        int(capability.get("depthMax") or 1), "MTPLX MTP depth",
    )
    suite = BENCHMARK_SUITES[MTPLX_LONG_CONTEXT_64K_SUITE]
    steps_per_route = 2 + benchmark_measurement_count(suite)
    return {
        "version": MTPLX_LONG_CONTEXT_2111_SWEEP_VERSION,
        "strategy": "isolated-long-context-operator-comparison",
        "suiteName": MTPLX_LONG_CONTEXT_64K_SUITE,
        "requiredContext": MTPLX_LONG_CONTEXT_MINIMUM,
        "contractId": str(receipt["contractId"]),
        "contract": copy.deepcopy(receipt),
        "baselineRoute": MTPLX_LONG_CONTEXT_DEFAULT_ROUTE,
        "candidateRoute": MTPLX_LONG_CONTEXT_2111_ROUTE,
        "baselineEnvironment": copy.deepcopy(MTPLX_LONG_CONTEXT_BASELINE_ENV),
        "candidateEnvironment": copy.deepcopy(MTPLX_LONG_CONTEXT_CANDIDATE_ENV),
        "fixedMtpDepth": depth,
        "maximumModelLoads": 3,
        "stepsPerRoute": steps_per_route,
        "maximumGeneratedRequests": 3 * steps_per_route,
        "freshLoadPerRoute": True,
        "greedyParityPerRoute": True,
        "selectionMetric": "generation-tokens-per-second",
        "minimumMedianSpeedup": BENCHMARK_MINIMUM_SPEEDUP,
        "minimumWorstSpeedup": BENCHMARK_MINIMUM_SPEEDUP,
        "resourceGatePerRoute": True,
        "resourceCooldownMemoryToleranceBytes": BENCHMARK_COOLDOWN_MEMORY_TOLERANCE_BYTES,
        "qualificationContract": {
            "suiteName": MTPLX_LONG_CONTEXT_64K_SUITE,
            "generatedPromptsOnly": True,
            "authoritativeUsageRequired": True,
            "minimumPromptTokens": MTPLX_LONG_CONTEXT_MINIMUM_PROMPT,
            "targetPromptTokens": MTPLX_LONG_CONTEXT_TARGET_PROMPT,
        },
    }

def benchmark_job_measurement_routes(job: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand public modes into the exact fresh-load routes a shootout will run."""
    tuning = job.get("calibrationTuningPlan")
    if (
        job.get("backend") == "mtplx"
        and isinstance(tuning, dict)
        and tuning.get("strategy") == "isolated-long-context-operator-comparison"
    ):
        depth = int(tuning["fixedMtpDepth"])
        contract_id = str(tuning["contractId"])
        return [
            {"mode": "ar", "label": "AR", "stateKey": "ar", "settings": {}},
            {
                "mode": "mtp", "label": f"MTP D{depth} · 2.11 default",
                "stateKey": "mtp-default",
                "settings": {
                    "depth": depth,
                    "mtplxOperatorRoute": MTPLX_LONG_CONTEXT_DEFAULT_ROUTE,
                },
                "operatorRoute": MTPLX_LONG_CONTEXT_DEFAULT_ROUTE,
                "contractId": contract_id,
            },
            {
                "mode": "mtp", "label": f"MTP D{depth} · 2.11 long-context",
                "stateKey": "mtp-long-context-2111",
                "settings": {
                    "depth": depth,
                    "mtplxOperatorRoute": MTPLX_LONG_CONTEXT_2111_ROUTE,
                },
                "operatorRoute": MTPLX_LONG_CONTEXT_2111_ROUTE,
                "contractId": contract_id,
            },
        ]
    routes: list[dict[str, Any]] = []
    for mode in job.get("modes") or []:
        if job.get("backend") == "mtplx" and mode == "mtp":
            for depth in mtplx_mtp_depth_candidates(job["model"]["backends"]["mtplx"]):
                routes.append({
                    "mode": "mtp", "label": f"MTP D{depth}",
                    "stateKey": f"mtp-d{depth}", "settings": {"depth": depth},
                })
        else:
            routes.append({
                "mode": str(mode),
                "label": benchmark_public_mode_label(str(job.get("backend") or ""), mode),
                "stateKey": str(mode), "settings": {},
            })
    return routes

def benchmark_job_base_maximum_route_count(job: dict[str, Any]) -> int:
    tuning = job.get("calibrationTuningPlan")
    return int(tuning["maximumModelLoads"]) if isinstance(tuning, dict) else len(
        benchmark_job_measurement_routes(job)
    )

def benchmark_job_maximum_route_count(job: dict[str, Any]) -> int:
    """Return the exact disclosed upper bound including engine-setting candidates."""
    sweep = job.get("engineSettingsSweep")
    if isinstance(sweep, dict):
        return int(sweep.get("maximumModelLoads") or 0)
    return benchmark_job_base_maximum_route_count(job)

def benchmark_job_public_modes(job: dict[str, Any]) -> list[dict[str, str]]:
    """Keep calibration route disclosure compact while showing an MTPLX depth search."""
    modes: list[dict[str, str]] = []
    for mode in job.get("modes") or []:
        label = benchmark_public_mode_label(str(job.get("backend") or ""), mode)
        if mode == "ar" and job.get("backend") in SSD_STREAMING_BACKENDS:
            label = "Exact SSD stream"
        elif (
            mode == "mtp" and job.get("backend") == "lmstudio"
            and isinstance(job.get("calibrationTuningPlan"), dict)
        ):
            label = f"MTP tuned ≤{BENCHMARK_MTP_TUNER_MAX_CANDIDATES}"
        elif mode == "mtp" and job.get("backend") == "mtplx":
            tuning = job.get("calibrationTuningPlan")
            if (
                isinstance(tuning, dict)
                and tuning.get("strategy")
                == "isolated-long-context-operator-comparison"
            ):
                label = "MTP default + 2.11 long-context"
            else:
                depths = mtplx_mtp_depth_candidates(
                    job["model"]["backends"]["mtplx"],
                )
                if len(depths) > 1:
                    label = f"MTP D1–D{max(depths)}"
        elif (
            mode == "dflash2" and job.get("backend") == "omlx"
            and isinstance(job.get("calibrationTuningPlan"), dict)
        ):
            label = f"DFlash tuned ≤{BENCHMARK_DFLASH_TUNER_MAX_CANDIDATES}"
        modes.append({"id": str(mode), "label": label})
    return modes

def _public_benchmark_count(value: Any, fallback: int = 0) -> int:
    """Return a non-negative count while treating malformed legacy data as absent."""
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return max(0, fallback)

def _public_rejected_faster_candidate_count(candidates: Any) -> int:
    if not isinstance(candidates, list):
        return 0
    return sum(
        1 for candidate in candidates
        if isinstance(candidate, dict)
        and candidate.get("qualityMatchesAR") is False
        and isinstance(candidate.get("medianSpeedupVsAR"), (int, float))
        and not isinstance(candidate.get("medianSpeedupVsAR"), bool)
        and math.isfinite(float(candidate["medianSpeedupVsAR"]))
        and float(candidate["medianSpeedupVsAR"]) > 1.0
    )

def public_benchmark_settings_search_plan(
    job: dict[str, Any],
) -> dict[str, Any] | None:
    sweep = job.get("engineSettingsSweep")
    if isinstance(sweep, dict):
        inner = _public_benchmark_route_search_plan(job) or {}
        presets = len(sweep["candidates"])
        maximum = int(sweep["maximumModelLoads"])
        return {
            "version": 1, "kind": "runtime-and-route",
            "label": "Runtime and acceleration settings", "strategy": "staged",
            "maximumSetupCount": maximum,
            "maximumCandidateCount": maximum - presets,
            "referenceSetupCount": presets,
            "axes": [*_public_runtime_search_axes(sweep), *inner.get("axes", [])],
        }
    return _public_benchmark_route_search_plan(job)

def _public_runtime_search_axes(sweep: dict[str, Any]) -> list[str]:
    labels = {
        "burst": "Burst preset", "gpu": "GPU offload", "profile": "Runtime profile",
        "prefillSize": "Prefill batch size", "promptCacheMode": "Prompt caching",
    }
    return [labels[axis] for axis in sweep.get("searchedAxes", []) if axis in labels]

def _public_benchmark_route_search_plan(
    job: dict[str, Any],
) -> dict[str, Any] | None:
    """Project the bounded engine-owned setup search without exposing its receipt."""
    backend = str(job.get("backend") or "")
    tuning = job.get("calibrationTuningPlan")
    try:
        disclosed_maximum = (
            tuning.get("maximumModelLoads")
            if isinstance(tuning, dict)
            else len(benchmark_job_measurement_routes(job))
        )
    except (KeyError, TypeError, ValueError):
        disclosed_maximum = 0
    maximum_setups = _public_benchmark_count(disclosed_maximum)
    if maximum_setups <= 0:
        return None
    if backend == "lmstudio" and isinstance(tuning, dict):
        maximum_candidates = _public_benchmark_count(
            tuning.get("maximumMtpCandidates")
            or BENCHMARK_MTP_TUNER_MAX_CANDIDATES,
            BENCHMARK_MTP_TUNER_MAX_CANDIDATES,
        )
        reference_setups = max(1, maximum_setups - maximum_candidates)
        return {
            "version": 1,
            "kind": "lmstudio-mtp",
            "label": "MTP settings",
            "strategy": "bounded",
            "maximumSetupCount": maximum_setups,
            "maximumCandidateCount": maximum_candidates,
            "referenceSetupCount": reference_setups,
            "axes": [
                "MTP draft depth", "minimum draft tokens", "continuation cutoff",
            ],
        }
    if backend == "omlx" and isinstance(tuning, dict):
        maximum_candidates = _public_benchmark_count(
            tuning.get("maximumDflashCandidates")
            or BENCHMARK_DFLASH_TUNER_MAX_CANDIDATES,
            BENCHMARK_DFLASH_TUNER_MAX_CANDIDATES,
        )
        reference_setups = max(1, maximum_setups - maximum_candidates)
        return {
            "version": 1,
            "kind": "omlx-dflash2",
            "label": "DFlash 2 settings",
            "strategy": "bounded",
            "maximumSetupCount": maximum_setups,
            "maximumCandidateCount": maximum_candidates,
            "referenceSetupCount": reference_setups,
            "axes": [
                "DFlash block size", "verification mode", "draft precision",
            ],
        }
    if backend != "mtplx" or "mtp" not in {
        str(mode) for mode in job.get("modes") or []
    }:
        return None
    if (
        isinstance(tuning, dict)
        and tuning.get("strategy") == "isolated-long-context-operator-comparison"
    ):
        return {
            "version": 1,
            "kind": "mtplx-operator",
            "label": "MTP operator route",
            "strategy": "fixed-comparison",
            "maximumSetupCount": maximum_setups,
            "maximumCandidateCount": max(0, maximum_setups - 1),
            "referenceSetupCount": 1,
            "axes": ["MTP operator route"],
        }
    depths = mtplx_mtp_depth_candidates(
        job["model"]["backends"]["mtplx"],
    )
    if len(depths) <= 1:
        return None
    return {
        "version": 1,
        "kind": "mtplx-depth",
        "label": "MTP depth",
        "strategy": "exhaustive",
        "maximumSetupCount": maximum_setups,
        "maximumCandidateCount": len(depths),
        "referenceSetupCount": 1,
        "axes": ["MTP draft depth"],
    }

def public_benchmark_settings_search_result(
    record: dict[str, Any],
) -> dict[str, Any] | None:
    sweep = record.get("engineSettingsSweep")
    if isinstance(sweep, dict):
        records = sweep.get("records")
        if not isinstance(records, dict):
            return None
        reference = records.get(sweep.get("tuningReferenceKey"))
        if not isinstance(reference, dict) or "engineSettingsSweep" in reference:
            return None
        inner = _public_benchmark_route_search_result(reference) or {}
        presets = len(records)
        modes = len(record.get("comparedModes", []))
        tested = inner.get("testedSetupCount", modes) + (presets - 1) * modes
        maximum = _public_benchmark_count(sweep.get("maximumModelLoads"))
        backend = str(record.get("backend") or "")
        return {
            "version": 1, "kind": "runtime-and-route",
            "label": "Runtime and acceleration settings", "strategy": "staged",
            "selectedSetupLabel": " · ".join(filter(None, [
                benchmark_engine_settings_label(backend, record.get("engineSettings")),
                benchmark_route_settings_label(backend, record.get("winner"), record.get("settings")),
            ])),
            "testedSetupCount": tested, "maximumSetupCount": maximum,
            "testedCandidateCount": max(0, tested - presets),
            "maximumCandidateCount": max(0, maximum - presets),
            "referenceSetupCount": presets,
            "rejectedFasterCandidateCount": inner.get("rejectedFasterCandidateCount", 0),
            "axes": [*_public_runtime_search_axes(sweep), *inner.get("axes", [])],
        }
    return _public_benchmark_route_search_result(record)

def _public_benchmark_route_search_result(
    record: dict[str, Any],
) -> dict[str, Any] | None:
    """Normalize supported tuning results for UI/history without raw candidates."""
    backend = str(record.get("backend") or "")
    sweep: dict[str, Any] | None = None
    kind = ""
    label = ""
    strategy = ""
    axes: list[str] = []
    reference_setups = 1
    maximum_candidates = 0
    candidate_count = 0
    if backend == "lmstudio" and isinstance(record.get("tuningSweep"), dict):
        sweep = record["tuningSweep"]
        kind, label, strategy = "lmstudio-mtp", "MTP settings", "bounded"
        axes = ["MTP draft depth", "minimum draft tokens", "continuation cutoff"]
        maximum_candidates = _public_benchmark_count(
            sweep.get("maximumCandidates"), BENCHMARK_MTP_TUNER_MAX_CANDIDATES,
        )
    elif backend == "omlx" and isinstance(record.get("tuningSweep"), dict):
        sweep = record["tuningSweep"]
        kind, label, strategy = "omlx-dflash2", "DFlash 2 settings", "bounded"
        axes = ["DFlash block size", "verification mode", "draft precision"]
        baseline_modes = sweep.get("baselineModes")
        reference_setups = max(
            1, len(baseline_modes) if isinstance(baseline_modes, list) else 1,
        )
        maximum_candidates = _public_benchmark_count(
            sweep.get("maximumCandidates"), BENCHMARK_DFLASH_TUNER_MAX_CANDIDATES,
        )
    elif backend == "mtplx" and isinstance(record.get("mtplxOperatorSweep"), dict):
        sweep = record["mtplxOperatorSweep"]
        kind, label, strategy = (
            "mtplx-operator", "MTP operator route", "fixed-comparison",
        )
        axes = ["MTP operator route"]
        candidates = sweep.get("candidates")
        maximum_candidates = len(candidates) if isinstance(candidates, list) else 2
    elif backend == "mtplx" and isinstance(record.get("mtpDepthSweep"), dict):
        sweep = record["mtpDepthSweep"]
        kind, label, strategy = "mtplx-depth", "MTP depth", "exhaustive"
        axes = ["MTP draft depth"]
        depths = sweep.get("depthCandidates")
        maximum_candidates = (
            len(depths) if isinstance(depths, list)
            else _public_benchmark_count(sweep.get("candidateCount"))
        )
    if sweep is None:
        return None
    raw_count = sweep.get("candidateCount")
    candidates = sweep.get("candidates")
    candidate_count = (
        len(candidates)
        if isinstance(candidates, list)
        else _public_benchmark_count(raw_count)
    )
    if maximum_candidates <= 0:
        maximum_candidates = candidate_count
    maximum_candidates = max(candidate_count, maximum_candidates)
    selected_setup = benchmark_route_settings_label(
        backend, record.get("winner"), record.get("settings"),
    )
    return {
        "version": 1,
        "kind": kind,
        "label": label,
        "strategy": strategy,
        "selectedSetupLabel": selected_setup,
        "testedSetupCount": candidate_count + reference_setups,
        "maximumSetupCount": maximum_candidates + reference_setups,
        "testedCandidateCount": candidate_count,
        "maximumCandidateCount": maximum_candidates,
        "referenceSetupCount": reference_setups,
        "rejectedFasterCandidateCount": (
            _public_rejected_faster_candidate_count(candidates)
        ),
        "axes": axes,
    }

def lmstudio_mtp_tuning_candidate_key(settings: dict[str, Any]) -> str:
    """Return the stable public identity for one exact LM Studio MTP load."""
    return (
        f"m{int(settings['depth'])}-n{int(settings['mtpMinTokens'])}-"
        f"p{float(settings['mtpMinContinueProbability']):.2f}"
    )

def lmstudio_mtp_tuning_depths(
    capability: dict[str, Any], anchor_depth: int,
) -> list[int]:
    """Choose representative depths without allowing an unbounded model-load grid."""
    maximum = max(1, int(capability.get("depthMax") or 1))
    anchor = max(1, min(maximum, int(anchor_depth)))
    if maximum <= 4:
        return _ordered_unique([anchor, *range(1, maximum + 1)])
    midpoint = max(1, min(maximum, (maximum + 1) // 2))
    return _ordered_unique([anchor, 1, maximum, midpoint])

def lmstudio_mtp_tuning_plan(job: dict[str, Any]) -> dict[str, Any]:
    """Describe the bounded adaptive search without loading a model."""
    capability = job["model"]["backends"]["lmstudio"]
    anchor = lmstudio_mtp_controls(job["options"], capability)
    steps_per_route = 2 + benchmark_measurement_count(job["suite"])
    maximum_candidates = BENCHMARK_MTP_TUNER_MAX_CANDIDATES
    maximum_loads = 1 + maximum_candidates
    return {
        "version": BENCHMARK_MTP_TUNER_VERSION,
        "strategy": "bounded-coordinate-search",
        "selectionMetric": benchmark_route_selection_metric(job),
        "anchor": anchor,
        "depthCandidates": lmstudio_mtp_tuning_depths(capability, anchor["depth"]),
        "cutoffCandidates": list(BENCHMARK_MTP_TUNER_CUTOFFS),
        "minimumCandidates": ["selected", 0, 1, "maximum"],
        "maximumMtpCandidates": maximum_candidates,
        "maximumModelLoads": maximum_loads,
        "stepsPerRoute": steps_per_route,
        "maximumGeneratedRequests": maximum_loads * steps_per_route,
        "freshLoadPerCandidate": True,
        "greedyParityPerCandidate": True,
        "resourceGatePerCandidate": True,
        "resourceCooldownMemoryToleranceBytes": BENCHMARK_COOLDOWN_MEMORY_TOLERANCE_BYTES,
    }

def validated_lmstudio_mtp_tuning_request(
    payload: dict[str, Any], models: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate one consented, exact-contract LM Studio MTP tuning sweep."""
    job = validated_benchmark_request(payload, models)
    capability = job["model"].get("backends", {}).get("lmstudio", {})
    if job["backend"] != "lmstudio":
        raise ValueError("Automatic MTP tuning is available only for LM Studio.")
    if capability.get("mtp") is not True or capability.get("mtpRuntimeVerified") is not True:
        raise ValueError(str(
            capability.get("mtpReason")
            or "This exact LM Studio model/runtime route has no verified load-time MTP path."
        ))
    job["kind"] = "lmstudio-mtp-tuning"
    job["tuningPlan"] = lmstudio_mtp_tuning_plan(job)
    return job

def dflash2_tuning_candidate_key(settings: dict[str, Any]) -> str:
    """Return the stable public identity for one exact DFlash model load."""
    return (
        f"b{int(settings['blockSize'])}-{str(settings['verifyMode'])}-"
        f"{str(settings['draftQuant'])}"
    )

def dflash2_tuning_block_sizes(
    capability: dict[str, Any], anchor_block: int,
) -> list[int]:
    """Cover checkpoint extremes and useful interior points with at most five loads."""
    maximum = max(1, int(capability.get("dflashMaxBlockSize") or 1))
    anchor = max(1, min(maximum, int(anchor_block)))
    if maximum <= 4:
        return _ordered_unique([anchor, *range(1, maximum + 1)])
    three_quarters = max(1, min(maximum, (3 * maximum + 2) // 4))
    midpoint = max(1, min(maximum, (maximum + 1) // 2))
    return _ordered_unique([anchor, maximum, three_quarters, midpoint, 1])

def dflash2_tuning_plan(job: dict[str, Any]) -> dict[str, Any]:
    """Describe the bounded DFlash coordinate search without loading a model."""
    capability = job["model"]["backends"]["omlx"]
    anchor = dflash2_tuning_controls(job["options"], capability)
    steps_per_route = 2 + benchmark_measurement_count(job["suite"])
    baseline_modes = [mode for mode in job["modes"] if mode != "dflash2"]
    maximum_candidates = BENCHMARK_DFLASH_TUNER_MAX_CANDIDATES
    maximum_loads = len(baseline_modes) + maximum_candidates
    return {
        "version": BENCHMARK_DFLASH_TUNER_VERSION,
        "strategy": "bounded-coordinate-search",
        "selectionMetric": benchmark_route_selection_metric(job),
        "searchedAxes": ["blockSize", "verifyMode", "draftQuant"],
        "anchor": anchor,
        "blockCandidates": dflash2_tuning_block_sizes(
            capability, anchor["blockSize"],
        ),
        "verifyCandidates": list(BENCHMARK_DFLASH_TUNER_VERIFY_MODES),
        "quantCandidates": list(BENCHMARK_DFLASH_TUNER_DRAFT_QUANTS),
        "baselineModes": baseline_modes,
        "maximumDflashCandidates": maximum_candidates,
        "maximumModelLoads": maximum_loads,
        "stepsPerRoute": steps_per_route,
        "maximumGeneratedRequests": maximum_loads * steps_per_route,
        "freshLoadPerCandidate": True,
        "greedyParityPerCandidate": True,
        "resourceGatePerCandidate": True,
        "resourceCooldownMemoryToleranceBytes": BENCHMARK_COOLDOWN_MEMORY_TOLERANCE_BYTES,
    }

def validated_dflash2_tuning_request(
    payload: dict[str, Any], models: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate one exact-pair oMLX DFlash tuning sweep without starting it."""
    job = validated_benchmark_request(payload, models)
    if job["backend"] != "omlx":
        raise ValueError("Automatic DFlash 2 tuning is available only for oMLX.")
    capability = job["model"].get("backends", {}).get("omlx", {})
    if capability.get("dflash") is not True or capability.get("dflashVersion") != "2":
        raise ValueError(str(
            capability.get("dflashReason")
            or "This exact oMLX model/runtime route has no verified DFlash 2 pair."
        ))
    if str(job["options"].get("kv") or "off") != "off":
        raise ValueError(DFLASH_KV_COMPARISON_REASON)
    if "dflash2" not in job.get("modes", []):
        raise ValueError(
            "DFlash 2 tuning cannot start while tuned ANE prefill is locked for this comparison. "
            "Choose ANE prefill Off first."
        )
    scanned_runtime = str(capability.get("dflashRuntimeVersion") or "")
    current_runtime = command_version(BINARIES.get("omlx"))
    if (
        not omlx_has_recommended_dflash2_runtime(scanned_runtime)
        or not secrets.compare_digest(scanned_runtime, current_runtime)
    ):
        raise ValueError(
            "DFlash tuning requires the scanned recommended oMLX build to still be selected. "
            "Refresh models after changing runtimes."
        )
    if not dflash2_capability_valid(job["model"], capability):
        raise ValueError(
            "The DFlash target/draft/runtime pair changed after scanning. Refresh models before tuning."
        )
    job["kind"] = "omlx-dflash2-tuning"
    job["tuningPlan"] = dflash2_tuning_plan(job)
    return job

def prepare_calibration_tuning_plan(job: dict[str, Any]) -> None:
    """Attach a bounded engine-owned search plan to a cross-engine job in place."""
    backend = str(job.get("backend") or "")
    modes = {str(mode) for mode in job.get("modes") or []}
    plan_job = copy.deepcopy(job)
    # Cross-engine calibration starts each engine from its audited defaults;
    # controls belonging to the currently visible engine must not bias another.
    plan_job["options"] = {}
    if backend == "mtplx" and "mtp" in modes:
        tuning = mtplx_long_context_operator_tuning_plan(plan_job)
        if tuning is not None:
            # The 2.11.1 operator comparison is meaningful only inside the
            # release's Turbo route.  Calibration owns engine-specific speed
            # controls, so bind both isolated MTP loads to Turbo even when the
            # currently visible MTPLX control is Sustained.  Rebuild the saved
            # engine-settings evidence at the same time; otherwise planning
            # would advertise a runnable three-load sweep that the launch-time
            # receipt correctly rejects, or later reuse would look for the
            # wrong profile.
            mtplx_options = copy.deepcopy(job.get("options") or {})
            mtplx_options["profile"] = "turbo"
            mtplx_options["mtplxOperatorRoute"] = MTPLX_LONG_CONTEXT_DEFAULT_ROUTE
            job["options"] = mtplx_options
            evidence = job.get("evidence")
            if isinstance(evidence, dict):
                add_benchmark_engine_evidence(
                    evidence, job["model"], mtplx_options, ["mtplx"],
                )
            job["suiteName"] = MTPLX_LONG_CONTEXT_64K_SUITE
            job["suite"] = copy.deepcopy(
                BENCHMARK_SUITES[MTPLX_LONG_CONTEXT_64K_SUITE]
            )
            job["workloadKind"] = "agentic"
            job["calibrationTuningPlan"] = tuning
            return
    if backend == "lmstudio" and "mtp" in modes:
        job["calibrationTuningPlan"] = lmstudio_mtp_tuning_plan(plan_job)
    elif backend == "omlx" and "dflash2" in modes:
        job["calibrationTuningPlan"] = dflash2_tuning_plan(plan_job)

def engine_settings_sweep_contract(job: dict[str, Any]) -> dict[str, Any]:
    """Bind a settings search to the immutable workload it is allowed to measure."""
    evidence = job.get("evidence") if isinstance(job.get("evidence"), dict) else {}
    return {
        "backend": str(job.get("backend") or ""),
        "modelFingerprint": str(job.get("modelFingerprint") or ""),
        "runtimeVersion": str(job.get("runtimeVersion") or ""),
        "hardwareFingerprint": hardware_fingerprint(),
        "suite": str(job.get("suiteName") or ""),
        "client": str(job.get("client") or ""),
        "reasoning": str(job.get("reasoning") or ""),
        "targetKV": str(evidence.get("kv") or "off"),
        "samplingFingerprint": str(evidence.get("samplingFingerprint") or ""),
        "context": int(job.get("context") or 0),
        "output": int(job.get("output") or 0),
        "selectionPreference": str(job.get("enginePreference") or "throughput"),
    }

def _engine_settings_candidate_key(backend: str, settings: dict[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps(
        settings, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()[:16]
    return f"{backend}-{digest}"

def _engine_settings_candidate_label(backend: str, settings: dict[str, Any]) -> str:
    if backend == "omlx":
        return f"Burst {str(settings.get('burst') or 'balanced').title()}"
    if backend == "lmstudio":
        return "Full GPU" if settings.get("gpu") == "max" else "CPU only"
    if backend == "mtplx":
        return f"{str(settings.get('profile') or 'sustained').replace('-', ' ').title()} profile"
    if backend == "swiftlm":
        return f"Prefill {int(settings.get('prefillSize') or 512)}"
    if backend == "mference":
        return "Prompt cache on" if settings.get("promptCacheMode") == "on" else "Prompt cache off"
    return BACKEND_LABELS.get(backend, backend)

def _engine_settings_for_sweep_candidate(
    job: dict[str, Any], option_updates: dict[str, Any],
) -> dict[str, Any]:
    backend = str(job["backend"])
    model = job["model"]
    capability = model["backends"][backend]
    options = copy.deepcopy(job.get("options") or {})
    options.update(copy.deepcopy(option_updates))
    canonical = validated_profile_options(backend, model, capability, options)
    settings = benchmark_engine_settings(backend, canonical)
    if backend == "omlx" and is_qwen4_exp_record(model):
        settings["pleStorage"] = "mmap"
    return settings

def _engine_settings_sweep_candidates(job: dict[str, Any]) -> tuple[
    list[dict[str, Any]], list[str], list[dict[str, Any]],
]:
    """Build a small deterministic coordinate, never a Cartesian product."""
    backend = str(job["backend"])
    base = benchmark_engine_settings(backend, job.get("options"))
    preference = str(job.get("enginePreference") or "throughput")
    updates: list[dict[str, Any]] = []
    searched: list[str] = []
    constrained: list[dict[str, Any]] = []
    if backend == "omlx":
        searched = ["burst"]
        updates = [{"burst": value} for value in _ordered_unique([
            base.get("burst", "balanced"), "off", "light", "balanced", "aggressive",
        ])]
        constrained.extend([
            {
                "key": "anePrefill", "value": base.get("anePrefill", "off"),
                "reason": "Approximate ANE prefill is separately qualified and cannot share DFlash 2.",
            },
            {
                "key": "memoryGuard", "value": base.get("memoryGuard", "balanced"),
                "reason": "Memory guard is a model-safety contract, not a speed coordinate.",
            },
        ])
    elif backend == "lmstudio":
        searched = ["gpu"]
        updates = [
            {"gpu": value, "parallel": 1}
            for value in _ordered_unique([base.get("gpu", "max"), "max", "off"])
        ]
        constrained.append({
            "key": "parallel", "value": 1,
            "reason": "Calibration issues one request at a time; parallel lanes cannot be ranked serially.",
        })
    elif backend == "mtplx":
        tuning = job.get("calibrationTuningPlan")
        if (
            isinstance(tuning, dict)
            and tuning.get("strategy") == "isolated-long-context-operator-comparison"
        ):
            profiles = ["turbo"]
            constrained.append({
                "key": "profile", "value": "turbo",
                "reason": "The audited 2.11.1 long-context operator contract requires Turbo.",
            })
        else:
            anchor = str(base.get("profile") or "sustained")
            preference_profiles = {
                "throughput": ["turbo", "sustained", "performance-cold"],
                "fastest": ["turbo", "sustained", "performance-cold"],
                "responsive": ["performance-cold", "turbo", "sustained"],
                "memory": ["stable", "sustained", "exact"],
                "thermal": ["stable", "sustained", "exact"],
            }
            profiles = _ordered_unique([
                anchor, *preference_profiles.get(preference, preference_profiles["throughput"]),
            ])[:4]
            searched = ["profile"]
        updates = [{"profile": value} for value in profiles]
        constrained.append({
            "key": "fan", "value": base.get("fan", "smart"),
            "reason": "Cooling is the user's explicit Calibration safety choice.",
        })
    elif backend == "swiftlm":
        searched = ["prefillSize"]
        updates = [{"prefillSize": value} for value in _ordered_unique([
            base.get("prefillSize", 512), *SSD_STREAMING_PREFILL_SIZES,
        ])]
        constrained.extend([
            {
                "key": "nativeExpertTopK", "value": base.get("nativeExpertTopK", 0),
                "reason": "The checkpoint's native expert routing is fidelity-owned.",
            },
            {
                "key": "ssdCacheState", "value": "natural-cold-to-warm",
                "reason": "macOS file cache is observed, never falsely purged.",
            },
        ])
    elif backend == "mference":
        agentic = str(job.get("workloadKind") or "") == "agentic"
        searched = ["promptCacheMode"] if agentic else []
        cache_modes = (
            _ordered_unique([base.get("promptCacheMode", "on"), "on", "off"])
            if agentic else [base.get("promptCacheMode", "on")]
        )
        updates = [
            {"promptCacheMode": value, "queueLimit": 1}
            for value in cache_modes
        ]
        constrained.extend([
            {
                "key": "queueLimit", "value": 1,
                "reason": "A serial workload cannot measure queue-depth throughput.",
            },
            {
                "key": "ssdCacheState", "value": "natural-cold-to-warm",
                "reason": "macOS file cache is observed, never falsely purged.",
            },
        ])
        if not agentic:
            constrained.append({
                "key": "promptCacheMode", "value": cache_modes[0],
                "reason": "Prompt-cache ranking requires the Agentic shared-prefix workload.",
            })
    else:
        return [], [], []
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for update in updates:
        settings = _engine_settings_for_sweep_candidate(job, update)
        key = _engine_settings_candidate_key(backend, settings)
        if key in seen:
            continue
        seen.add(key)
        candidates.append({
            "key": key,
            "label": _engine_settings_candidate_label(backend, settings),
            "settings": settings,
        })
    return candidates, searched, constrained

def prepare_engine_settings_sweep(job: dict[str, Any]) -> None:
    """Plan AR presets, acceleration tuning, then each retained route at every preset."""
    if job.get("routeQualification") is True:
        return
    candidates, axes, constrained = _engine_settings_sweep_candidates(job)
    if not candidates:
        return
    base_loads = benchmark_job_base_maximum_route_count(job)
    loads = base_loads + (len(candidates) - 1) * len(job["modes"])
    job["engineSettingsSweep"] = {
        "version": ENGINE_SETTINGS_SWEEP_VERSION,
        "strategy": "staged-runtime-and-route-search",
        "backend": job["backend"],
        "selectionPreference": job.get("enginePreference") or "throughput",
        "contract": engine_settings_sweep_contract(job),
        "searchedAxes": axes,
        "constrainedAxes": constrained,
        "candidates": candidates,
        "maximumEngineSettingLoads": len(candidates),
        "baseRouteLoads": base_loads,
        "maximumModelLoads": loads,
        "stepsPerLoad": 2 + benchmark_measurement_count(job["suite"]),
        "maximumGeneratedRequests": loads * (2 + benchmark_measurement_count(job["suite"])),
        "globalCartesianSearch": False,
    }

def validate_engine_settings_sweep_budget(jobs: list[dict[str, Any]]) -> None:
    loads = sum(benchmark_job_maximum_route_count(job) for job in jobs)
    requests = sum(
        benchmark_job_maximum_route_count(job)
        * (2 + benchmark_measurement_count(job["suite"]))
        for job in jobs
    )
    if (
        loads > ENGINE_SETTINGS_SWEEP_MAX_MODEL_LOADS
        or requests > ENGINE_SETTINGS_SWEEP_MAX_GENERATED_REQUESTS
    ):
        raise ValueError(
            "The requested Calibration matrix exceeds the bounded settings-search budget "
            f"({loads}/{ENGINE_SETTINGS_SWEEP_MAX_MODEL_LOADS} model loads, "
            f"{requests}/{ENGINE_SETTINGS_SWEEP_MAX_GENERATED_REQUESTS} generated requests). "
            "Choose a smaller compatible engine set or workload."
        )

def rotated_engine_shootout_jobs(
    jobs: list[dict[str, Any]], model: dict[str, Any], shootout_id: str,
) -> tuple[list[dict[str, Any]], str]:
    """Rotate the first engine across matching runs to reduce fixed-order bias."""
    if len(jobs) < 2:
        return list(jobs), "single-engine"
    backends = [str(job["backend"]) for job in jobs]
    prior: list[tuple[str, list[str]]] = []
    for capability in (model.get("backends") or {}).values():
        if not isinstance(capability, dict):
            continue
        records = capability.get("localBenchmarks")
        candidates = [item for item in records if isinstance(item, dict)] if isinstance(records, list) else []
        latest = capability.get("localBenchmark")
        if isinstance(latest, dict) and latest not in candidates:
            candidates.append(latest)
        for record in candidates:
            order = record.get("shootoutExecutionOrder")
            if (
                isinstance(order, list) and order
                and all(isinstance(item, str) for item in order)
                and order[0] in backends
            ):
                prior.append((str(record.get("createdAt") or ""), list(order)))
    if prior:
        previous_first = max(prior, key=lambda item: item[0])[1][0]
        rotation = (backends.index(previous_first) + 1) % len(backends)
        strategy = "round-robin-after-previous-shootout"
    else:
        digest = hashlib.sha256(shootout_id.encode("utf-8")).digest()
        rotation = int.from_bytes(digest[:4], "big") % len(backends)
        strategy = "shootout-id-seeded-rotation"
    ordered = list(jobs[rotation:]) + list(jobs[:rotation])
    return ordered, strategy

def validated_route_qualification_request(
    payload: dict[str, Any], models: list[dict[str, Any]],
) -> dict[str, Any]:
    """Lock one exact receipt-bound route; never manufacture an engine comparison."""
    model_id = str(payload.get("modelId") or "")
    model = next((item for item in models if item.get("id") == model_id), None)
    if not model:
        raise ValueError("The selected model is no longer in the scanned catalog. Refresh models.")
    preference = str(payload.get("enginePreference") or "throughput")
    if preference not in ENGINE_PREFERENCE_LABELS:
        raise ValueError("Choose a supported route-qualification metric.")
    visible = validated_launch_profile_request(payload, models)
    backend = str(visible.get("backend") or "")
    spec = route_qualification_spec(model, backend, int(visible.get("context") or 0))
    if spec is None:
        raise ValueError("This exact controller-scanned route has no dedicated qualification contract.")
    if backend == "omlx" and visible.get("options", {}).get("memoryGuard") != "high":
        raise ValueError(
            "Choose Qwen high-memory mode before qualifying this PLE route."
        )
    if backend == "llamacpp":
        if visible.get("client") == "codex":
            raise ValueError("The fixed llama.cpp SSD-PLE qualification does not expose a Codex Responses route.")
        if int(visible.get("context") or 0) != LLAMACPP_PLE_CONTEXT:
            raise ValueError("The llama.cpp SSD-PLE qualification is fixed to exactly 8,192 context tokens.")
        if int(visible.get("output") or 0) < ROUTE_QUALIFICATION_MAX_TOKENS:
            raise ValueError(
                "The llama.cpp SSD-PLE qualification requires at least 512 visible response tokens."
            )
    if backend == "uzu":
        if visible.get("client") != "chat":
            raise ValueError(
                "The first Uzu qualification is limited to the built-in Chat surface."
            )
        if int(visible.get("context") or 0) != int(spec["context"]):
            raise ValueError(
                f"This Uzu qualification is fixed to exactly {int(spec['context']):,} context tokens."
            )
        if int(visible.get("output") or 0) < UZU_QUALIFICATION_SAMPLE_MIN_TOKENS:
            raise ValueError(
                "The Uzu qualification requires at least 2,048 visible response tokens."
            )
    reasoning_contract = route_qualification_reasoning_contract(visible, model, spec)
    if reasoning_contract.get("reasoningEnabled") is not True:
        raise ValueError(str(reasoning_contract.get("detail") or "Choose a reasoning level first."))
    request = copy.deepcopy(visible)
    request["reasoning"] = reasoning_contract["measured"]
    request["suite"] = spec["suite"]
    if backend == "omlx":
        request.setdefault("options", {})["fan"] = validated_calibration_cooling(payload)
    job = validated_benchmark_request(
        request, models, allow_baseline_only=True,
    )
    if job.get("modes") != ["ar"]:
        raise ValueError(
            "This model now exposes another verified route. Use engine/route calibration instead."
        )
    eligible: list[str] = []
    excluded: list[dict[str, str]] = []
    kv = str(request.get("options", {}).get("kv") or "off")
    chat = request.get("chat") if isinstance(request.get("chat"), dict) else None
    if backend in {"llamacpp", "uzu"}:
        eligible = [backend]
        excluded = [
            {"backend": candidate, "label": BACKEND_LABELS[candidate],
             "reason": "Not part of this receipt-bound single-route qualification."}
            for candidate in ENGINE_ADAPTERS if candidate != backend
        ]
    else:
        for candidate in ENGINE_ADAPTERS:
            allowed, reason = benchmark_backend_eligibility(
                model, candidate, request["client"], request["reasoning"], kv, chat,
            )
            if allowed:
                eligible.append(candidate)
            else:
                excluded.append({
                    "backend": candidate, "label": BACKEND_LABELS[candidate], "reason": reason,
                })
    if eligible != [backend]:
        raise ValueError(
            "Single-route qualification is available only while the selected route is the sole exact-artifact route."
        )
    capability = model["backends"][backend]
    qualification_contract = build_route_qualification_contract(
        spec, request, capability,
    )
    job.update({
        "kind": "route-qualification",
        "routeQualification": True,
        "qualificationVersion": ROUTE_QUALIFICATION_VERSION,
        "qualificationReasoningContract": copy.deepcopy(reasoning_contract),
        "qualificationContract": qualification_contract,
        "enginePreference": preference,
    })
    # Keep the four bounded agentic stages while reserving part of each sample
    # for the final answer that makes the route usable.
    apply_route_qualification_budget(job)
    return {
        "id": job["id"], "kind": "route-qualification",
        "request": copy.deepcopy(request),
        "reasoningContract": reasoning_contract,
        "routeSpec": copy.deepcopy(spec),
        "qualificationContract": copy.deepcopy(qualification_contract),
        "enginePreference": job["enginePreference"],
        "modelId": model_id, "model": model["name"],
        "client": request["client"],
        "suite": job["suiteName"], "suiteLabel": job["suite"]["label"],
        "workloadKind": job["workloadKind"],
        "job": job, "jobs": [job],
        "executionOrder": [backend],
        "excludedEngines": excluded,
    }

def validated_engine_shootout_request(
    payload: dict[str, Any], models: list[dict[str, Any]],
) -> dict[str, Any]:
    """Lock one visible contract across every compatible installed engine."""
    if dflash_quantized_fallback(str(payload.get("backend") or ""), payload.get("options") or {}):
        raise ValueError(DFLASH_KV_COMPARISON_REASON)
    preference = str(payload.get("enginePreference") or "throughput")
    if preference not in ENGINE_PREFERENCE_LABELS:
        raise ValueError("Choose a supported Engine Shootout decision goal.")
    model_id = str(payload.get("modelId") or "")
    model = next((item for item in models if item.get("id") == model_id), None)
    if not model:
        raise ValueError("The selected model is no longer in the scanned catalog. Refresh models.")
    atomic_spec = route_qualification_spec(model, "llamacpp")
    if atomic_spec is not None and atomic_spec["backend"] == "llamacpp":
        raise ValueError(
            "The receipt-bound llama.cpp SSD-PLE route uses dedicated single-route qualification; "
            "it cannot enter a generic Engine Shootout or be presented as a cross-engine winner."
        )
    reasoning_contract = benchmark_reasoning_contract(payload, model)
    comparison_payload = copy.deepcopy(payload)
    comparison_payload["reasoning"] = reasoning_contract["measured"]
    comparison_payload, context_adjustment = normalized_ssd_comparison_request(
        comparison_payload, model,
    )
    if "calibrationCooling" in payload:
        calibration_cooling = validated_calibration_cooling(payload)
        comparison_options = comparison_payload.get("options")
        if not isinstance(comparison_options, dict):
            comparison_options = {}
            comparison_payload["options"] = comparison_options
        comparison_options["fan"] = calibration_cooling
    current = optimal_request(comparison_payload, models)
    client = str(comparison_payload.get("client") or "")
    requested_suite = str(
        comparison_payload.get("suite")
        or ("standard" if client == "chat" else "agentic")
    )
    if _mtplx_long_context_suite_requested(
        model, int(comparison_payload.get("context") or 0), requested_suite,
    ):
        comparison_payload["suite"] = MTPLX_LONG_CONTEXT_64K_SUITE
    reasoning = str(comparison_payload.get("reasoning") or "auto")
    options = comparison_payload.get("options") if isinstance(comparison_payload.get("options"), dict) else {}
    kv = str(options.get("kv") or "off")
    chat = validated_chat_settings(model, comparison_payload, client)
    shootout_id = str(uuid.uuid4())
    jobs: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    ssd_profile = model.get("ssdStreaming") if isinstance(model.get("ssdStreaming"), dict) else {}
    ssd_lane = ssd_profile.get("recommended") is True
    candidate_backends = ssd_profile_candidate_backends(ssd_profile) if ssd_lane else tuple(ENGINE_ADAPTERS)
    for backend in candidate_backends:
        allowed, reason = benchmark_backend_eligibility(
            model, backend, client, reasoning, kv, chat,
        )
        if not allowed:
            excluded.append({
                "backend": backend, "label": BACKEND_LABELS[backend], "reason": reason,
            })
            continue
        candidate = copy.deepcopy(comparison_payload)
        candidate["backend"] = backend
        candidate.pop("scope", None)
        try:
            candidate["options"] = validated_cross_engine_profile_options(
                backend, model, model.get("backends", {}).get(backend, {}),
                candidate.get("options"),
            )
            if ssd_lane:
                candidate["options"]["ssdCacheState"] = "natural-cold-to-warm"
            job = validated_benchmark_request(
                candidate, models, allow_baseline_only=True,
            )
        except ValueError as error:
            excluded.append({
                "backend": backend, "label": BACKEND_LABELS[backend], "reason": str(error),
            })
            continue
        job["shootoutId"] = shootout_id
        job["enginePreference"] = preference
        prepare_calibration_tuning_plan(job)
        prepare_engine_settings_sweep(job)
        jobs.append(job)
    if len(jobs) < 2:
        detail = "; ".join(
            f"{item['label']}: {item['reason']}" for item in excluded
        )
        single_route_detail = (
            " Whallm owns a separate pinned full-expert checkpoint, so it cannot be compared "
            "as the same artifact as a SwiftLM, Mference, or pruned REAP model."
            if model.get("sharedServer") is True else ""
        )
        raise ValueError(
            "Engine Shootout needs at least two installed engines that can preserve the selected "
            "model, client, reasoning, sampling, context, response limit, and KV precision."
            + single_route_detail
            + (f" {detail}" if detail else "")
        )
    fingerprints = {str(job.get("modelFingerprint") or "") for job in jobs}
    if ssd_lane:
        comparison_identities = {
            str(job["model"].get("backends", {}).get(job["backend"], {}).get("comparisonIdentity") or "")
            for job in jobs
        }
        if "" in comparison_identities or len(comparison_identities) != 1:
            raise ValueError(
                "SSD calibration needs verified SwiftLM and Mference artifacts from the same pinned source revision."
            )
    elif "" in fingerprints or len(fingerprints) != 1:
        raise ValueError(
            "The compatible engines do not resolve to the same model artifact fingerprint, so a "
            "cross-engine speed comparison would not be trustworthy."
        )
    validate_engine_settings_sweep_budget(jobs)
    jobs, order_strategy = rotated_engine_shootout_jobs(jobs, model, shootout_id)
    execution_order = [str(job["backend"]) for job in jobs]
    for index, job in enumerate(jobs):
        job["shootoutExecutionOrder"] = list(execution_order)
        job["shootoutOrderIndex"] = index
        job["shootoutOrderStrategy"] = order_strategy
    # Final result selection must validate against the engine controls that were
    # actually measured.  A tuner may intentionally normalize an engine-owned
    # setting after the visible request was captured (MTPLX 2.11.1 long-context
    # measurements, for example, require Turbo).  Keeping the old visible value
    # here makes an otherwise valid completed record look stale and sends Apply
    # back into Calibration.
    measured_request = copy.deepcopy(comparison_payload)
    measured_options = copy.deepcopy(measured_request.get("options") or {})
    for job in jobs:
        settings = job.get("evidence", {}).get("engineSettings")
        if isinstance(settings, dict):
            measured_options.update(copy.deepcopy(settings))
    measured_request["options"] = measured_options
    return {
        "id": shootout_id,
        "kind": "engine-shootout",
        "request": measured_request,
        "reasoningContract": reasoning_contract,
        "enginePreference": preference,
        "modelId": model_id,
        "model": model["name"],
        "client": client,
        "suite": jobs[0]["suiteName"],
        "suiteLabel": jobs[0]["suite"]["label"],
        "workloadKind": jobs[0]["workloadKind"],
        "jobs": jobs,
        "executionOrder": execution_order,
        "orderStrategy": order_strategy,
        "excludedEngines": excluded,
        "ssdStreaming": ssd_lane,
        "ssdContract": copy.deepcopy(ssd_profile.get("calibration")) if ssd_lane else None,
        "contextAdjustment": context_adjustment,
    }

def validated_calibration_cooling(payload: dict[str, Any]) -> str:
    """Return the explicit MTPLX cooling policy for a calibration run."""
    cooling = str(payload.get("calibrationCooling") or "smart")
    if cooling not in {"default", "smart", "max"}:
        raise ValueError("Choose Automatic, System controlled, or Maximum calibration cooling.")
    return cooling

def qwen_ple_qualification_preparation(
    request: dict[str, Any], model: dict[str, Any], models: list[dict[str, Any]],
    calibration_cooling: str,
) -> dict[str, Any]:
    """Return one explicit, side-effect-free 48 GiB qualification preset.

    This helper changes only the visible request contract.  It never changes a
    macOS system setting, starts a runtime, or assumes that the resulting route
    has passed the separate live memory-admission gate.
    """
    prepared_payload = copy.deepcopy(request)
    prepared_payload.update({
        "backend": "omlx",
        "context": QWEN_PLE_QUALIFICATION_CONTEXT,
        "output": QWEN_PLE_QUALIFICATION_OUTPUT,
        "reasoning": QWEN_PLE_QUALIFICATION_REASONING,
    })
    prepared_options = copy.deepcopy(prepared_payload.get("options") or {})
    prepared_options.update({
        "acceleration": "off",
        "depth": 1,
        "kv": "off",
        "burst": "aggressive",
        "anePrefill": "off",
        "memoryGuard": "high",
        "fan": "smart",
    })
    prepared_payload["options"] = prepared_options
    prepared = validated_launch_profile_request(prepared_payload, models)

    current_options = request.get("options") if isinstance(request.get("options"), dict) else {}
    changes: list[dict[str, str | int]] = []

    def changed(key: str, current: Any, value: Any, label: str) -> None:
        if current != value:
            changes.append({"key": key, "value": value, "label": label})

    changed("context", request.get("context"), prepared["context"], "16,384 context")
    changed("output", request.get("output"), prepared["output"], "8,192 max response")
    changed(
        "reasoning", request.get("reasoning"), prepared["reasoning"],
        "Medium reasoning",
    )
    for key, label in (
        ("acceleration", "Exact autoregressive route"),
        ("kv", "Full-precision KV"),
        ("burst", "Throughput stream batching"),
        ("anePrefill", "Approximate ANE prefill off"),
        ("memoryGuard", "High memory guard"),
    ):
        changed(key, current_options.get(key), prepared["options"].get(key), label)
    if calibration_cooling != "smart":
        changes.append({
            "key": "calibrationCooling", "value": "smart",
            "label": "Automatic cooling",
        })

    return {
        "kind": "qwen-ple-safe-qualification-v1",
        "applicable": bool(changes),
        "modelId": str(model.get("id") or request.get("modelId") or ""),
        "settings": {
            "backend": "omlx",
            "context": prepared["context"],
            "output": prepared["output"],
            "reasoning": prepared["reasoning"],
            "calibrationCooling": "smart",
            "options": {
                key: prepared["options"][key]
                for key in (
                    "acceleration", "depth", "kv", "burst", "anePrefill",
                    "memoryGuard",
                )
            },
        },
        "request": prepared,
        "changes": changes,
        "summary": (
            "Prepare the exact oMLX AR route at 16K context, 8K response, medium "
            "reasoning, full-precision KV, High memory guard, and Automatic cooling."
        ),
        "doesNotChangeMacOS": True,
    }

def calibration_plan(
    payload: dict[str, Any], models: list[dict[str, Any]],
) -> dict[str, Any]:
    """Describe an exact-contract calibration without starting or allocating anything."""
    if dflash_quantized_fallback(str(payload.get("backend") or ""), payload.get("options") or {}):
        raise ValueError(DFLASH_KV_COMPARISON_REASON)
    calibration_cooling = validated_calibration_cooling(payload)
    raw_options = (
        copy.deepcopy(payload.get("options"))
        if isinstance(payload.get("options"), dict) else {}
    )
    selected = next(
        (item for item in models if item.get("id") == str(payload.get("modelId") or "")),
        None,
    )
    calibration_payload = copy.deepcopy(payload)
    context_adjustment: dict[str, Any] | None = None
    if selected is not None:
        calibration_payload, context_adjustment = normalized_ssd_comparison_request(
            calibration_payload, selected,
        )
    visible_request = validated_launch_profile_request(
        calibration_payload, models, preserve_comparison_controls=True,
    )
    preference = str(payload.get("enginePreference") or "throughput")
    if preference not in ENGINE_PREFERENCE_LABELS:
        raise ValueError("Choose a supported calibration goal.")
    model = next(item for item in models if item.get("id") == visible_request["modelId"])
    route_spec = route_qualification_spec(
        model, str(visible_request.get("backend") or ""),
        int(visible_request.get("context") or 0),
    )
    route_qualification_candidate = route_spec is not None
    # Uzu owns its fixed DFlash + Weaver route and exposes no fan-control
    # surface.  Collapse every otherwise-valid UI cooling choice to the one
    # truthful contract before building jobs or looking up saved evidence, so
    # a cosmetic Smart/Maximum selection cannot fragment qualification receipts.
    uzu_system_cooling = bool(
        route_spec is not None and route_spec.get("backend") == "uzu"
    )
    if uzu_system_cooling:
        calibration_cooling = "default"
    requested_suite_name = str(
        payload.get("suite")
        or ("standard" if visible_request["client"] == "chat" else "agentic")
    )
    if (
        route_spec is None
        and _mtplx_long_context_suite_requested(
            model, int(visible_request.get("context") or 0), requested_suite_name,
        )
    ):
        requested_suite_name = MTPLX_LONG_CONTEXT_64K_SUITE
    suite_name = str(route_spec["suite"]) if route_spec else requested_suite_name
    suite = BENCHMARK_SUITES.get(suite_name)
    if not suite:
        raise ValueError("Choose a Quick, Standard, Thorough, or Agentic calibration workload.")
    reasoning_contract = (
        route_qualification_reasoning_contract(visible_request, model, route_spec)
        if route_qualification_candidate else
        benchmark_reasoning_contract(
            {
                **visible_request,
                "reasoningPolicy": payload.get("reasoningPolicy")
                or BENCHMARK_REASONING_POLICY_ALL_ENGINES,
            },
            model,
        )
    )
    measurement_payload = copy.deepcopy(visible_request)
    measurement_payload["reasoning"] = reasoning_contract["measured"]
    measurement_payload.setdefault("options", {})["fan"] = calibration_cooling
    request = validated_launch_profile_request(
        measurement_payload, models, preserve_comparison_controls=True,
    )
    kv = str(request.get("options", {}).get("kv") or "off")
    engines: list[dict[str, Any]] = []
    jobs: list[dict[str, Any]] = []
    ssd_profile = model.get("ssdStreaming") if isinstance(model.get("ssdStreaming"), dict) else {}
    ssd_lane = ssd_profile.get("recommended") is True
    candidate_backends = (
        (str(route_spec["backend"]),) if route_spec else
        ssd_profile_candidate_backends(ssd_profile) if ssd_lane else tuple(ENGINE_ADAPTERS)
    )
    for backend in candidate_backends:
        allowed, reason = benchmark_backend_eligibility(
            model, backend, request["client"], request["reasoning"], kv,
            request.get("chat") if isinstance(request.get("chat"), dict) else None,
        )
        job: dict[str, Any] | None = None
        if allowed:
            candidate = copy.deepcopy(request)
            candidate["backend"] = backend
            candidate["suite"] = suite_name
            try:
                candidate_option_source = copy.deepcopy(raw_options)
                candidate_option_source.update({
                    "acceleration": (
                        "off"
                        if route_spec and backend in {"llamacpp", "uzu"}
                        else "auto"
                    ), "kv": kv,
                    "fan": calibration_cooling,
                })
                candidate["options"] = (
                    validated_profile_options(
                        backend, model, model.get("backends", {}).get(backend, {}),
                        candidate_option_source,
                    )
                    if route_spec else
                    validated_cross_engine_profile_options(
                        backend, model, model.get("backends", {}).get(backend, {}),
                        candidate_option_source,
                    )
                )
                job = validated_benchmark_request(
                    candidate, models, allow_baseline_only=True,
                )
                # The engine-owned MTP/DFlash search must use the same goal as
                # the surrounding cross-engine comparison.
                job["enginePreference"] = preference
                if (
                    route_qualification_candidate and backend == route_spec["backend"]
                    and job.get("modes") == ["ar"]
                ):
                    capability = model["backends"][backend]
                    qualification_contract = build_route_qualification_contract(
                        route_spec, request, capability,
                    )
                    job.update({
                        "kind": "route-qualification",
                        "routeQualification": True,
                        "qualificationVersion": ROUTE_QUALIFICATION_VERSION,
                        "qualificationReasoningContract": copy.deepcopy(reasoning_contract),
                        "qualificationContract": qualification_contract,
                        "enginePreference": preference,
                    })
                    apply_route_qualification_budget(job)
                if backend in SSD_STREAMING_BACKENDS:
                    job["options"]["ssdCacheState"] = "natural-cold-to-warm"
                    add_benchmark_engine_evidence(
                        job["evidence"], model, job["options"], [backend],
                    )
                prepare_calibration_tuning_plan(job)
                prepare_engine_settings_sweep(job)
            except ValueError as error:
                allowed = False
                reason = str(error)
        if job is not None:
            jobs.append(job)
        measured_modes = list(job.get("modes") or []) if job is not None else []
        measurement_route_count = (
            benchmark_job_maximum_route_count(job) if job is not None else 0
        )
        engine_settings = (
            job.get("evidence", {}).get("engineSettings")
            if job is not None else {}
        )
        mode_detail = (
            benchmark_mode_summary(
                model, backend, measured_modes or ["ar"], engine_settings,
                kv=kv,
            )
            if job is not None else ""
        )
        if job is not None and job.get("routeQualification") is True:
            mode_detail = (
                f"Qualifies one exact {route_spec['routeLabel']} across cold, shared-prefix, "
                "tool-ingestion, and warm reasoning turns."
            )
        if (
            job is not None and backend == "lmstudio"
            and isinstance(job.get("calibrationTuningPlan"), dict)
        ):
            mode_detail += (
                f" LM Studio searches up to {BENCHMARK_MTP_TUNER_MAX_CANDIDATES} "
                "bounded MTP depth, minimum, and cutoff combinations; only the fastest "
                "AR-matching load is kept."
            )
        elif (
            job is not None and backend == "omlx"
            and isinstance(job.get("calibrationTuningPlan"), dict)
        ):
            mode_detail += (
                f" oMLX searches up to {BENCHMARK_DFLASH_TUNER_MAX_CANDIDATES} bounded "
                "DFlash block, verifier, and draft-precision combinations; only the fastest "
                "AR-matching load is kept."
            )
        elif job is not None and backend == "mtplx" and "mtp" in measured_modes:
            tuning = job.get("calibrationTuningPlan")
            if (
                isinstance(tuning, dict)
                and tuning.get("strategy")
                == "isolated-long-context-operator-comparison"
            ):
                mode_detail += (
                    " MTPLX measures AR, the isolated default MTP operators, and the "
                    "2.11.1 long-context operators at one fixed verified depth. The "
                    "candidate must clear exact output, resource, median-TPS, and "
                    "worst-TPS gates before it can be kept."
                )
            else:
                depths = mtplx_mtp_depth_candidates(
                    job["model"]["backends"]["mtplx"],
                )
                if len(depths) > 1:
                    mode_detail += (
                        f" MTPLX is reloaded at every verified draft depth (D1–D{max(depths)}); "
                        "only the fastest AR-matching depth is kept."
                    )
        engine_capability = model.get("backends", {}).get(backend, {})
        engine_runtime_installed = bool(
            ENGINE_ADAPTERS[backend].public().get("installed") is True
        )
        engine_artifact_compatible = bool(
            model.get("ready") is True
            and engine_capability.get("runnable") is True
        )
        engines.append({
            "backend": backend,
            "label": BACKEND_LABELS[backend],
            "eligible": bool(job is not None),
            "reason": (
                route_qualification_engine_reason(backend)
                if job is not None and job.get("routeQualification") is True else
                (
                    "Uses model-default reasoning so every included engine shares the same "
                    "benchmark setting."
                    if backend not in reasoning_contract["normalizedFor"] else
                    "Uses its model-controlled reasoning mode; this benchmark route does not "
                    f"offer a separate {reasoning_contract['requested']} selector."
                )
                if job is not None and reasoning_contract["normalized"] else
                "Uses the verified equivalent source revision, native expert routing, and the same work contract."
                if job is not None and ssd_lane else
                "Preserves this exact model, work surface, reasoning, sampling, limits, and KV precision."
                if job is not None else str(reason)
            ),
            "modes": benchmark_job_public_modes(job) if job is not None else [],
            "measurementRouteCount": measurement_route_count,
            "settingsSearch": (
                public_benchmark_settings_search_plan(job)
                if job is not None else None
            ),
            "modeDetail": mode_detail,
            "accelerationReason": (
                benchmark_acceleration_reason(model, backend, measured_modes, kv=kv)
                if job is not None else ""
            ),
            "settingsLabel": (
                benchmark_engine_settings_label(backend, engine_settings)
                if job is not None else ""
            ),
            "acceleratedAlternatives": (
                accelerated_model_alternatives(model, backend, models)
                if job is not None and not set(measured_modes).intersection({"mtp", "dflash2"})
                else []
            ),
            "runtimeVersion": str(job.get("runtimeVersion") or "") if job else "",
            "performanceEvidence": route_performance_evidence(
                model, backend, engine_capability,
                job.get("evidence") if job is not None else None,
            ),
            "hostSupport": route_host_support(
                model, backend, engine_capability,
                runtime_installed=engine_runtime_installed,
                artifact_compatible=engine_artifact_compatible,
            ),
        })
    validate_engine_settings_sweep_budget(jobs)

    route_qualification = bool(
        route_qualification_candidate
        and len(jobs) == 1
        and jobs[0].get("backend") == route_spec["backend"]
        and jobs[0].get("modes") == ["ar"]
        and reasoning_contract.get("reasoningEnabled") is True
    )
    qualification_preparation: dict[str, Any] | None = None
    if route_qualification_candidate and route_spec["backend"] == "omlx":
        try:
            qualification_preparation = qwen_ple_qualification_preparation(
                visible_request, model, models, calibration_cooling,
            )
        except (KeyError, StopIteration, ValueError):
            qualification_preparation = None
    blockers: list[str] = []
    fingerprints = {str(job.get("modelFingerprint") or "") for job in jobs}
    if route_qualification_candidate and reasoning_contract.get("reasoningEnabled") is not True:
        blockers.append(str(reasoning_contract.get("detail") or "Choose a reasoning level first."))
    elif request["backend"] == "uzu" and request["client"] == "pi":
        blockers.append(UZU_PI_BENCHMARK_LIMITATION)
    elif len(jobs) < 2 and not route_qualification:
        blockers.append(
            "Whallm's full-expert checkpoint has no equivalent second engine to compare; use its measured route directly."
            if model.get("sharedServer") is True else
            "SSD calibration needs both SwiftLM and Mference, plus verified equivalent model artifacts."
            if ssd_lane else
            "Calibration needs at least two installed engines that can preserve the complete measurement contract."
        )
    comparison_identities = {
        str(job["model"].get("backends", {}).get(job["backend"], {}).get("comparisonIdentity") or "")
        for job in jobs
    }
    if (
        not route_qualification and ssd_lane and jobs
        and ("" in comparison_identities or len(comparison_identities) != 1)
    ):
        blockers.append(
            "The SSD artifacts do not prove one matching pinned source revision, so their speeds cannot be compared safely."
        )
    elif (
        not route_qualification and not ssd_lane and jobs
        and ("" in fingerprints or len(fingerprints) != 1)
    ):
        blockers.append(
            "Compatible engines do not expose one matching model-artifact fingerprint, so their speeds cannot be compared safely."
        )
    memory_admission: dict[str, Any] | None = None
    if route_qualification:
        try:
            memory_admission = route_qualification_memory_admission(request, models)
        except (KeyError, StopIteration, ValueError) as error:
            blockers.append(
                "Current Qwen route capacity could not be verified: "
                + (str(error) or "refresh model and memory status before qualifying it.")
            )
        else:
            if not route_qualification_admission_ready(memory_admission):
                blockers.append(
                    f"{memory_admission.get('label') or 'Qwen route is not loadable'}: "
                    f"{memory_admission.get('detail') or 'refresh capacity before qualification.'}"
                )
    if qualification_preparation and qualification_preparation.get("applicable") is True:
        try:
            qualification_preparation["nextAdmission"] = route_qualification_memory_admission(
                qualification_preparation["request"], models,
            )
        except (KeyError, StopIteration, ValueError) as error:
            qualification_preparation["nextAdmission"] = {
                "decision": "unknown", "launchable": False,
                "requiresAcknowledgement": False,
                "label": "Capacity will be rechecked",
                "detail": str(error) or "Refresh capacity after preparing the visible route.",
            }
        qualification_preparation["resolvesVisibleSettings"] = (
            qualification_preparation["nextAdmission"].get("decision") != "configuration"
        )
    ready = not blockers
    route_count = sum(
        benchmark_job_maximum_route_count(job) for job in jobs
    ) if ready else 0
    measured_requests = sum(
        benchmark_job_maximum_route_count(job)
        * (
            2 + benchmark_measurement_count(job["suite"])
            + int(job.get("qualificationContract", {}).get("toolProbeRequired") is True)
        )
        for job in jobs
    ) if ready else 0
    prompt_schedule = (
        [
            {"id": scenario, "label": label}
            for scenario, label in (
                ("cold", "Cold agent turn"),
                ("warmPrefix", "Shared-prefix turn"),
                ("toolIngest", "Tool-result ingestion"),
                ("steadyTurn", "Warm follow-up"),
            )
        ]
        if suite.get("kind") == "agentic"
        else [
            {"id": str(tokens), "label": f"{tokens:,} prompt tokens"}
            for tokens in suite.get("promptTokens") or []
        ]
    )

    measured_request = copy.deepcopy(request)
    comparison_options = copy.deepcopy(measured_request.get("options") or {})
    for job in jobs:
        settings = job.get("evidence", {}).get("engineSettings")
        if isinstance(settings, dict):
            comparison_options.update(copy.deepcopy(settings))
    comparison_options["fan"] = calibration_cooling
    measured_request["options"] = comparison_options
    measured_request["enginePreference"] = preference
    decision = best_engine_request(measured_request, models)
    evidence_tier = str(decision.get("engineEvidenceTier") or decision.get("evidenceTier") or "")
    trusted = evidence_tier in {
        "cross-engine-local-benchmark", "local-route-qualification",
    }
    decision_ready = evidence_tier in {
        "cross-engine-local-benchmark", "cross-engine-leading-band",
        "cross-engine-noise-floor", "local-route-qualification",
    }
    raw_decision_binding = decision.get("engineEvidenceBinding")
    decision_binding: dict[str, Any] | None = None
    if raw_decision_binding is not None:
        try:
            candidate_binding = validated_optimizer_evidence_binding({
                "evidenceBinding": raw_decision_binding,
            })
        except ValueError:
            decision_ready = False
        else:
            expected_scope = (
                "route" if evidence_tier == "local-route-qualification" else "engine"
            )
            if (
                candidate_binding is None
                or candidate_binding.get("scope") != expected_scope
                or candidate_binding.get("suite") != suite_name
                or candidate_binding.get("preference") != preference
            ):
                decision_ready = False
            else:
                decision_binding = candidate_binding
    if decision_ready and raw_decision_binding is None:
        if evidence_tier == "local-route-qualification":
            fallback_binding = {
                "scope": "route", "suite": suite_name, "preference": preference,
            }
            qualified_routes = decision.get("qualifiedRoutes")
            record_id = (
                qualified_routes[0].get("recordId")
                if isinstance(qualified_routes, list) and len(qualified_routes) == 1
                and isinstance(qualified_routes[0], dict) else None
            )
            if record_id:
                fallback_binding["recordId"] = str(record_id)
                try:
                    decision_binding = validated_optimizer_evidence_binding({
                        "evidenceBinding": fallback_binding,
                    })
                except ValueError:
                    decision_ready = False
            else:
                decision_ready = False
        else:
            # A suite name alone is not an immutable engine result. Older
            # ungrouped matrices remain visible for review, but must be rerun
            # once before Apply can target one exact shootout fail-closed.
            decision_ready = False
    resolved_backend = str(decision.get("backend") or request["backend"])
    rationale = list(decision.get("engineRationale") or decision.get("rationale") or [])
    workload_comparison = (
        decision.get("engineDecision", {}).get("workloadComparison", {})
        if isinstance(decision.get("engineDecision"), dict) else {}
    )
    contract_value = {
        "modelId": request["modelId"], "client": request["client"],
        "context": request["context"], "output": request["output"],
        "reasoning": request["reasoning"], "kv": kv,
        "chat": request.get("chat"), "suite": suite_name,
        "enginePreference": preference, "calibrationCooling": calibration_cooling,
    }
    contract_id = hashlib.sha256(json.dumps(
        contract_value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()[:16]
    suggested_name = f"Quick Launch · {model.get('name') or request['modelId']}"
    if len(suggested_name) > LAUNCH_PROFILE_NAME_MAX:
        suggested_name = suggested_name[:LAUNCH_PROFILE_NAME_MAX].rstrip()
    model_alternatives = qwen_flash_next_model_alternatives(
        model, visible_request, models,
    )
    action = "apply-existing" if decision_ready else ("measure" if ready else "blocked")
    return {
        "version": 2,
        "contractId": contract_id,
        "action": action,
        "ready": ready,
        "routeQualification": route_qualification,
        "routeSpec": copy.deepcopy(route_spec) if route_qualification else None,
        "qualificationContract": (
            copy.deepcopy(jobs[0].get("qualificationContract"))
            if route_qualification else None
        ),
        "qualificationPreparation": copy.deepcopy(qualification_preparation),
        "blockers": blockers,
        "memoryAdmission": copy.deepcopy(memory_admission),
        "request": request,
        "reasoningContract": reasoning_contract,
        "model": {"id": request["modelId"], "name": str(model.get("name") or request["modelId"])},
        "client": request["client"],
        "clientLabel": {"pi": "Pi", "opencode": "OpenCode", "codex": "Codex", "chat": "Chat"}[request["client"]],
        "suite": {
            "id": suite_name, "label": str(suite["label"]),
            "kind": str(suite.get("kind") or "throughput"),
            "promptSchedule": prompt_schedule,
        },
        "suiteAdjustment": (
            {
                "requested": requested_suite_name,
                "measured": suite_name,
                "reason": "Single-route qualification uses the bounded four-turn reasoning workload.",
            }
            if route_qualification_candidate and requested_suite_name != suite_name else None
        ),
        "preference": preference,
        "preferenceLabel": ENGINE_PREFERENCE_LABELS[preference],
        "ssdStreaming": ssd_lane,
        "ssdContract": copy.deepcopy(ssd_profile.get("calibration")) if ssd_lane else None,
        "contextAdjustment": context_adjustment,
        "modelAlternatives": model_alternatives,
        "calibrationCooling": calibration_cooling,
        "calibrationCoolingLabel": {
            "default": "System controlled",
            "smart": "Automatic",
            "max": "Maximum fans",
        }[calibration_cooling],
        "calibrationCoolingLocked": uzu_system_cooling,
        "calibrationCoolingReason": (
            "Uzu does not expose fan control; macOS controls cooling for this fixed route."
            if uzu_system_cooling else ""
        ),
        "engines": engines,
        "eligibleEngineCount": len(jobs),
        "routeCount": route_count,
        "modelReloadCount": route_count,
        "measuredRequestCount": measured_requests,
        "countsAreMaximum": any(
            isinstance(job.get("calibrationTuningPlan"), dict) for job in jobs
        ),
        "resourceCooldownMaxSecondsPerRoute": BENCHMARK_COOLDOWN_MAX_SECONDS,
        "resourceCooldownMemoryToleranceBytes": BENCHMARK_COOLDOWN_MEMORY_TOLERANCE_BYTES,
        "evidence": {
            "trusted": trusted,
            "decisionReady": decision_ready,
            "tier": evidence_tier,
            "label": str(decision.get("engineEvidenceLabel") or decision.get("evidenceLabel") or "Current engine kept"),
            "backend": resolved_backend,
            "backendLabel": BACKEND_LABELS[resolved_backend],
            "engineChanged": bool(decision.get("engineChanged")),
            "leadingBackends": copy.deepcopy(decision.get("leadingBackends") or []),
            "currentInLeadingBand": decision.get("currentInLeadingBand") is True,
            "qualified": evidence_tier == "local-route-qualification",
            "detail": str(rationale[0]) if rationale else "No matching cross-engine winner is available yet.",
            "exactOutputMatch": workload_comparison.get("exactOutputMatch") is True,
            "outputWarning": str(
                decision.get("engineOutputWarning")
                or workload_comparison.get("warning") or ""
            ),
            **({"evidenceBinding": copy.deepcopy(decision_binding)} if decision_binding else {}),
            "comparedEngines": copy.deepcopy(decision.get("comparedEngines") or []),
            "qualifiedRoutes": copy.deepcopy(decision.get("qualifiedRoutes") or []),
        },
        "suggestedProfileName": suggested_name,
        "privacy": {
            "usesProjectData": False,
            "storesGeneratedText": False,
            "requiresExplicitStart": True,
        },
    }

def validated_ane_tuning_request(
    payload: dict[str, Any], models: list[dict[str, Any]],
) -> tuple[dict[str, Any], LaunchPlan, dict[str, Any]]:
    cpu_assist_value = payload.get("cpuAssist", False)
    if not isinstance(cpu_assist_value, bool):
        raise ValueError("CPU sharing must be an explicit on or off choice.")
    cpu_assist = cpu_assist_value is True
    model_id = str(payload.get("modelId") or "")
    model = next((item for item in models if item.get("id") == model_id), None)
    if not model:
        raise ValueError("Choose a scanned oMLX model before opening ANE Tuner.")
    capability = model.get("backends", {}).get("omlx") or {}
    readiness = capability.get("aneReadiness") or {}
    if not model.get("ready") or not capability.get("runnable"):
        raise ValueError(str(capability.get("reason") or "This model is not ready for oMLX."))
    if not readiness.get("ready"):
        raise ValueError(str(readiness.get("reason") or capability.get("aneReason") or "ANE Tuner is not ready for this route."))
    runtime_version = command_version(BINARIES.get("omlx"))
    if runtime_version != capability.get("runtimeVersion") or not omlx_version_at_least(
        runtime_version, ANE_TUNER_MINIMUM_RUNTIME,
    ):
        raise ValueError("The oMLX runtime changed after the scan. Rescan models before tuning.")
    kernel = omlx_qwen_kernel_status(BINARIES.get("omlx"))
    if not kernel.get("ready"):
        raise ValueError(str(
            kernel.get("reason")
            or "The selected oMLX installation no longer has a verified native Qwen kernel."
        ))
    try:
        model_path = Path(str(model["path"])).resolve(strict=True)
    except (KeyError, OSError, RuntimeError) as error:
        raise ValueError("The selected checkpoint moved after the scan. Rescan models.") from error
    config = read_json(model_path / "config.json")
    profile = ane_quantization_profile(config)
    cpu_profile = ane_cpu_sharing_profile(model_path)
    ready, _status, weight_bytes = weight_completeness(model_path, config)
    memory = ane_memory_readiness(weight_bytes, physical_memory_bytes())
    cpu_memory = ane_memory_readiness(weight_bytes, physical_memory_bytes(), cpu_assist=True)
    fingerprint = model_artifact_fingerprint(model_path, config)
    if not ready or not profile.get("compatible") or not memory.get("ready"):
        raise ValueError(str(profile.get("reason") if not profile.get("compatible") else memory.get("reason")))
    if not fingerprint or fingerprint != capability.get("benchmarkModelFingerprint"):
        raise ValueError("The checkpoint changed after the scan. Rescan models before tuning.")
    if cpu_assist:
        if not cpu_profile.get("eligible"):
            raise ValueError(str(cpu_profile.get("reason") or "This checkpoint is not an eligible FP16 CPU-sharing clone."))
        if not cpu_memory.get("ready"):
            raise ValueError(str(cpu_memory.get("reason") or "CPU candidate tuning needs more memory headroom."))
        if (
            not cpu_profile.get("profileFingerprint")
            or cpu_profile.get("profileFingerprint") != readiness.get("cpuProfileFingerprint")
        ):
            raise ValueError("The FP16 checkpoint tensor profile changed after the scan. Rescan models before tuning.")

    native_context = int(model.get("nativeContext") or 8_192)
    context = min(native_context, 8_192)
    if context < 1_280:
        raise ValueError("This checkpoint's advertised context is too small for the tuning harness.")
    plan_payload = {
        "backend": "omlx", "client": "chat", "modelId": model_id,
        "project": str(payload.get("project") or Path.home()),
        "context": context, "output": 256, "reasoning": "auto", "mode": "custom",
        "options": {
            "acceleration": "off", "depth": 1, "kv": "off",
            "burst": "aggressive", "dflashVerify": "adaptive",
            "dflashDraftQuant": "native", "anePrefill": "off",
        },
    }
    plan = normalized_request(plan_payload, models, purpose="ane-tune")
    job = {
        "id": str(uuid.uuid4()), "modelId": model_id, "model": model["name"],
        "sequenceLength": ANE_TUNER_SEQUENCE_LENGTH, "repeats": ANE_TUNER_REPEATS,
        "runtimeVersion": runtime_version,
        "modelFingerprint": fingerprint,
        "hardwareFingerprint": hardware_fingerprint(),
        "cpuAssist": cpu_assist,
        "cpuFloatDtype": "F16" if cpu_assist else None,
        "cpuProfileFingerprint": cpu_profile.get("profileFingerprint") if cpu_assist else None,
        "cpuGateEligible": cpu_assist,
        "cpuDownEligible": bool(cpu_assist and cpu_profile.get("downProjectionEligible")),
        "cpuGdnEligible": bool(cpu_assist and cpu_profile.get("gdnEligible")),
        "cpuReserveBytes": cpu_memory.get("reserveBytes") if cpu_assist else None,
        "approximate": True,
        "minimumSpeedupPercent": ANE_TUNER_MINIMUM_SPEEDUP_PERCENT,
    }
    return copy.deepcopy(model), plan, job
