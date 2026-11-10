"""Frozen complete pre-extraction route_qualification domain. Test-only."""

def _llamacpp_route_qualification_capability(
    model: dict[str, Any],
) -> dict[str, Any] | None:
    """Return only the controller's exact receipt-bound AtomicChat capability."""
    capability = model.get("backends", {}).get("llamacpp", {})
    atomic = capability.get("atomicPle")
    model_atomic = model.get("atomicPle")
    receipt = capability.get("receiptFingerprint")
    if not (
        model.get("ready") is True
        and isinstance(capability, dict)
        and capability.get("runnable") is True
        and capability.get("llamacppPle") is True
        and capability.get("currentProcessVerified") is True
        and isinstance(capability.get("verificationGeneration"), int)
        and capability.get("verificationGeneration") > 0
        and isinstance(atomic, dict) and atomic.get("ready") is True
        and atomic.get("currentProcessVerified") is True
        and atomic.get("verificationGeneration") == capability.get("verificationGeneration")
        and isinstance(model_atomic, dict) and model_atomic == atomic
        and atomic.get("repoId") == LLAMACPP_ATOMIC_REPO
        and atomic.get("pinnedRevision") == LLAMACPP_ATOMIC_REVISION
        and atomic.get("variantId") == LLAMACPP_ATOMIC_VARIANT_ID
        and atomic.get("variant") == LLAMACPP_ATOMIC_VARIANT
        and atomic.get("shardCount") == LLAMACPP_ATOMIC_SHARDS
        and atomic.get("weightBytes") == LLAMACPP_ATOMIC_TOTAL_BYTES
        and atomic.get("context") == LLAMACPP_PLE_CONTEXT
        and capability.get("contextWindows") == [LLAMACPP_PLE_CONTEXT]
        and capability.get("contextMaximum") == LLAMACPP_PLE_CONTEXT
        and capability.get("memoryCeilingBytes") == LLAMACPP_PLE_MEMORY_CEILING_BYTES
        and isinstance(receipt, str)
        and re.fullmatch(r"[0-9a-f]{64}", receipt) is not None
        and atomic.get("receiptFingerprint") == receipt
        and capability.get("firstShard") == atomic.get("firstShard")
        and capability.get("modelPath") == model.get("path")
        and isinstance(capability.get("runtimeVersion"), str)
        and bool(capability.get("runtimeVersion"))
        and isinstance(capability.get("benchmarkModelFingerprint"), str)
        and re.fullmatch(r"[0-9a-f]{64}", capability["benchmarkModelFingerprint"]) is not None
        and capability.get("agentReasoning") == ["auto"]
        and capability.get("codexReasoning") == ["auto"]
    ):
        return None
    return capability

def route_qualification_spec(
    model: dict[str, Any], backend: str | None = None,
    context: int | None = None,
) -> dict[str, Any] | None:
    """Describe one exact single-route qualification without inventing peers."""
    selected = str(backend or "")
    if selected in {"", "omlx"} and is_qwen4_exp_record(model):
        capability = model.get("backends", {}).get("omlx", {})
        if (
            capability.get("runnable") is True
            and capability.get("mtp") is not True
            and capability.get("dflash") is not True
        ):
            return {
                "id": "qwen-omlx-ple-ar-v1", "version": 1,
                "backend": "omlx", "mode": "ar", "modeLabel": "AR + PLE mmap",
                "suite": "agentic", "context": None,
                "reasoningPolicy": "explicit-selectable",
                "toolProbeRequired": False, "memoryProofRequired": False,
                "routeLabel": "oMLX AR + PLE mmap route",
            }
    if selected in {"", "llamacpp"} and _llamacpp_route_qualification_capability(model):
        return {
            "id": "atomicchat-llamacpp-ssd-ple-8k-v1", "version": 1,
            "scope": "route", "clientAgnostic": True,
            "backend": "llamacpp", "mode": "ar", "modeLabel": "SSD PLE",
            "suite": ROUTE_QUALIFICATION_8K_SUITE,
            "context": LLAMACPP_PLE_CONTEXT,
            "reasoningPolicy": "runtime-fixed-on",
            "toolProbeRequired": True, "memoryProofRequired": True,
            "memoryCeilingBytes": LLAMACPP_PLE_MEMORY_CEILING_BYTES,
            "routeLabel": "llama.cpp SSD-PLE 8K route",
        }
    if selected in {"", "uzu"} and model.get("uzuNative") is True:
        capability = model.get("backends", {}).get("uzu", {})
        exact_context = (
            int(context)
            if isinstance(context, int) and not isinstance(context, bool)
            else UZU_SAFE_CONTEXT_WINDOWS[0]
        )
        suites = ROUTE_QUALIFICATION_UZU_SUITES_BY_CONTEXT
        if (
            capability.get("runnable") is True
            and capability.get("runtimeManagedAcceleration") == "DFlash + Weaver"
            and exact_context in suites
        ):
            context_k = exact_context // 1024
            return {
                "id": f"qwen36-uzu-dflash-weaver-{context_k}k-v5",
                "version": UZU_QUALIFICATION_CONTRACT_VERSION, "scope": "route",
                "clientAgnostic": False, "client": "chat",
                "backend": "uzu", "mode": "ar",
                "modeLabel": "Fixed DFlash + Weaver",
                "suite": suites[exact_context], "context": exact_context,
                "reasoningPolicy": "runtime-default-on",
                "toolProbeRequired": False, "memoryProofRequired": True,
                "memoryCeilingBytes": UZU_PROCESS_MEMORY_CEILING_BYTES,
                "routeLabel": f"Uzu DFlash + Weaver {context_k}K route",
            }
    return None

def route_qualification_reasoning_contract(
    payload: dict[str, Any], model: dict[str, Any], spec: dict[str, Any],
) -> dict[str, Any]:
    if spec["reasoningPolicy"] == "runtime-fixed-on":
        return {
            "policy": "runtime-fixed-reasoning-on",
            "requested": str(payload.get("reasoning") or "auto"),
            "measured": "auto", "normalized": False,
            "normalizedFor": [], "normalizedForLabels": [],
            "label": "Runtime controlled · reasoning on",
            "detail": (
                "The audited llama.cpp route fixes reasoning on at the server boundary; "
                "Auto accurately records that no user-selectable effort level is exposed."
            ),
            "changesVisibleSettingWhenApplied": False,
            "reasoningEnabled": True, "runtimeControlled": True,
        }
    if spec["reasoningPolicy"] == "runtime-default-on":
        requested = str(payload.get("reasoning") or "auto")
        enabled = requested == "auto"
        return {
            "policy": "runtime-default-reasoning-on",
            "requested": requested, "measured": "auto",
            "normalized": False,
            "normalizedFor": [], "normalizedForLabels": [],
            "label": "Model default · reasoning on",
            "detail": (
                "This first Uzu launcher route exposes only the artifact's packaged "
                "reasoning path; Auto measures that exact model-default behavior."
                if enabled else
                "Turn reasoning on (Auto) before qualifying this Uzu route."
            ),
            "changesVisibleSettingWhenApplied": False,
            "reasoningEnabled": enabled, "runtimeControlled": True,
        }
    return qwen_ple_route_qualification_reasoning_contract(payload, model)

def qwen_ple_route_qualification_reasoning_contract(
    payload: dict[str, Any], model: dict[str, Any],
) -> dict[str, Any]:
    """Lock one explicit reasoning level for a Qwen PLE route qualification.

    A single route has no cross-engine reason to fall back to model-default
    reasoning.  When the visible setting is Auto, choose a real advertised
    level so the bounded qualification proves separate reasoning and answer
    output rather than merely proving that the server accepts a request.
    """
    requested = str(payload.get("reasoning") or "auto")
    capability = model.get("backends", {}).get("omlx", {})
    reasoning_key = "codexReasoning" if payload.get("client") == "codex" else "agentReasoning"
    choices = [str(item) for item in capability.get(reasoning_key) or []]
    explicit = [
        item for item in ("medium", "low", "high", "xhigh", "minimal", "max")
        if item in choices
    ]
    measured = requested
    normalized = False
    detail = "The selected reasoning level is preserved for this route qualification."
    if requested == "auto" and explicit:
        measured = explicit[0]
        normalized = True
        detail = (
            f"Auto is measured at {measured} so the qualification can verify both "
            "separate reasoning and a final answer. The visible setting changes only if "
            "you apply the qualified route."
        )
    enabled = measured not in {"auto", "off"} and measured in choices
    if requested == "off":
        detail = "Choose a reasoning level before qualifying this reasoning-capable route."
    elif not enabled:
        detail = (
            "oMLX does not advertise an explicit reasoning level for this exact model route, "
            "so reasoning reliability cannot be qualified yet."
        )
    return {
        "policy": "single-route-explicit-reasoning",
        "requested": requested,
        "measured": measured,
        "normalized": normalized,
        "normalizedFor": ["omlx"] if normalized else [],
        "normalizedForLabels": ["oMLX"] if normalized else [],
        "label": measured,
        "detail": detail,
        "changesVisibleSettingWhenApplied": normalized,
        "reasoningEnabled": enabled,
    }

def route_qualification_sample_tokens(backend: str, configured_output: int | None = None) -> int:
    if backend == "uzu":
        return min(UZU_QUALIFICATION_SAMPLE_MAX_TOKENS, configured_output) if configured_output is not None else UZU_QUALIFICATION_SAMPLE_MAX_TOKENS
    return ROUTE_QUALIFICATION_MAX_TOKENS

def uzu_qualification_output_policy(configured_output: int) -> dict[str, Any]:
    return {
        "id": UZU_QUALIFICATION_OUTPUT_POLICY_ID,
        "maximumTokens": route_qualification_sample_tokens("uzu", configured_output),
        "minimumTokens": UZU_QUALIFICATION_SAMPLE_MIN_TOKENS,
        "promptReserveTokens": UZU_QUALIFICATION_PROMPT_RESERVE_TOKENS,
        "followupReserveTokens": UZU_QUALIFICATION_SAMPLE_MIN_TOKENS + 128,
    }

def uzu_qualification_request_tokens(scenario: str, target: int, context: int, ceiling: int) -> int:
    remaining = context - target - UZU_QUALIFICATION_PROMPT_RESERVE_TOKENS
    if scenario == "toolIngest":
        remaining -= UZU_QUALIFICATION_SAMPLE_MIN_TOKENS + 128
    return min(ceiling, remaining)

def apply_route_qualification_budget(job: dict[str, Any]) -> None:
    """Keep bounded test output separate from the user's saved response ceiling.

    llama.cpp uses its explicit 384+128 reasoning/answer split. Uzu retains
    model-default reasoning with an adaptive allowance and no forced split.
    """
    backend = str(job.get("backend") or "")
    sample_tokens = route_qualification_sample_tokens(backend, int(job["output"]))
    minimum = UZU_QUALIFICATION_SAMPLE_MIN_TOKENS if backend == "uzu" else sample_tokens
    if int(job["output"]) < minimum:
        raise ValueError(
            f"Route qualification requires at least {minimum:,} visible response tokens."
        )
    answer_reserve = ROUTE_QUALIFICATION_ANSWER_RESERVE_TOKENS
    job["suite"]["maxTokens"] = sample_tokens
    # This legacy marker also identifies qualification streams. Only llama.cpp
    # turns it into a reasoning-boundary request; Uzu never receives a split.
    job["qualificationThinkingBudgetTokens"] = ROUTE_QUALIFICATION_THINKING_TOKENS
    job["qualificationAnswerReserveTokens"] = answer_reserve

def uzu_qualification_prompt_exercise_policy(exact_context: int) -> dict[str, Any]:
    """Bind long-context receipts to authoritative near-tier prompt exercise."""
    return {
        "id": UZU_QUALIFICATION_NEAR_TIER_POLICY_ID,
        "appliesAtOrAboveContextTokens": UZU_QUALIFICATION_NEAR_TIER_MINIMUM_CONTEXT,
        "requiredScenarios": list(UZU_QUALIFICATION_NEAR_TIER_SCENARIOS),
        "authoritativeUsageRequired": True,
        "minimumContextFraction": UZU_QUALIFICATION_NEAR_TIER_FRACTION,
        "minimumPromptTokens": math.ceil(
            exact_context * UZU_QUALIFICATION_NEAR_TIER_FRACTION
        ),
        "targetPromptTokensRequired": True,
        "targetToleranceFraction": UZU_QUALIFICATION_PROMPT_TOLERANCE_FRACTION,
        "targetToleranceMinimumTokens": UZU_QUALIFICATION_PROMPT_TOLERANCE_MIN_TOKENS,
    }

def validate_uzu_qualification_sample(
    sample: dict[str, Any], case: dict[str, Any], max_tokens: int,
) -> None:
    """Stop an unusable qualification before spending time on later turns."""
    if (
        sample.get("terminalComplete") is not True
        or sample.get("responseLimitReached") is True
        or sample.get("reasoningObserved") is not True
        or sample.get("answerObserved") is not True
    ):
        channels = (
            "Reasoning and answer output were both observed"
            if sample.get("reasoningObserved") and sample.get("answerObserved") else
            "Only reasoning output was observed"
            if sample.get("reasoningObserved") else
            "Only answer output was observed"
            if sample.get("answerObserved") else
            "No reasoning or answer output was observed"
        )
        # Only fixed labels and numeric metadata enter the persisted job error.
        # Do not include generated reasoning, answers, or arbitrary finish strings.
        counts = []
        for key, label in (
            ("completionTokens", "output tokens"),
            ("reasoningCharacters", "reasoning characters"),
            ("answerCharacters", "answer characters"),
        ):
            value = sample.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                counts.append(f"{value:,} {label}")
        end = (
            "the runtime reported a length limit"
            if sample.get("responseLimitReached") is True else
            "the runtime reported completion"
            if sample.get("terminalComplete") is True else
            "completion was not confirmed"
        )
        diagnostics = f" {channels}; {end}."
        if counts:
            diagnostics += f" Observed: {', '.join(counts)}."
        repetition = sample.get("reasoningRepeatedPhraseFraction")
        if isinstance(repetition, (int, float)) and not isinstance(repetition, bool) and 0.25 <= repetition <= 1:
            diagnostics += f" In the reasoning tail, {repetition:.0%} of 16-word windows were repeats."
        raise RuntimeError(
            f"Uzu's {case['label']} did not pass the complete reasoning-and-answer check "
            f"with a {max_tokens:,}-token test budget.{diagnostics} "
            "Qualification stopped; later turns cannot repair this result."
        )
    tolerance = max(
        UZU_QUALIFICATION_PROMPT_TOLERANCE_MIN_TOKENS,
        round(int(case["targetPromptTokens"]) * UZU_QUALIFICATION_PROMPT_TOLERANCE_FRACTION),
    )
    if abs(int(sample["promptTokens"]) - int(case["targetPromptTokens"])) > tolerance:
        raise RuntimeError(
            f"Uzu's {case['label']} tokenised outside its intended prompt size. "
            "Qualification stopped before another model request."
        )

def build_route_qualification_contract(
    spec: dict[str, Any], request: dict[str, Any], capability: dict[str, Any],
) -> dict[str, Any]:
    """Bind a qualification receipt to the exact runtime, artifact, and route."""
    backend = str(spec["backend"])
    contract: dict[str, Any] = {
        "id": spec["id"], "version": spec["version"], "backend": backend,
        "exactContext": int(request["context"]),
        "scenarioContract": list(ROUTE_QUALIFICATION_SCENARIOS),
        "sampleMaxTokens": route_qualification_sample_tokens(backend, int(request["output"])),
        "answerReserveTokens": ROUTE_QUALIFICATION_ANSWER_RESERVE_TOKENS,
        "minimumDecodeTokensPerSecond": (
            LLAMACPP_PLE_MINIMUM_DECODE_TPS if backend == "llamacpp" else
            UZU_QUALIFICATION_MINIMUM_DECODE_TPS if backend == "uzu" else None
        ),
        "thinkingBudgetTokens": (
            ROUTE_QUALIFICATION_THINKING_TOKENS if backend == "llamacpp" else None
        ),
        "reasoningPolicy": spec["reasoningPolicy"],
        "toolProbeRequired": spec["toolProbeRequired"],
        "memoryProofRequired": spec["memoryProofRequired"],
        "memoryCeilingBytes": spec.get("memoryCeilingBytes"),
        "receiptFingerprint": capability.get("receiptFingerprint"),
        "runtimeVersion": capability.get("runtimeVersion"),
    }
    if backend == "llamacpp":
        contract.update({
            "scope": "route",
            "clientAgnostic": True,
            "minimumCompletionTokens": ROUTE_QUALIFICATION_MINIMUM_COMPLETION_TOKENS,
            "configuredOutputLimit": int(request["output"]),
            "measuredRequestMaxTokens": ROUTE_QUALIFICATION_MAX_TOKENS,
            "reasoningBoundaryContractId": LLAMACPP_QUALIFICATION_REASONING_BOUNDARY_ID,
            "reasoningBudgetMessageSha256": hashlib.sha256(
                LLAMACPP_QWEN_REASONING_BUDGET_MESSAGE.encode("utf-8")
            ).hexdigest(),
        })
    elif backend == "uzu":
        runtime_identity = capability.get("runtimeIdentity")
        binary = (
            runtime_identity.get("binary")
            if isinstance(runtime_identity, dict) else None
        )
        runtime_sha = binary.get("sha256") if isinstance(binary, dict) else None
        runtime_size = binary.get("size") if isinstance(binary, dict) else None
        model_fingerprint = capability.get("benchmarkModelFingerprint")
        system_contract = capability.get("qualificationSystemContract")
        if (
            not isinstance(runtime_sha, str)
            or re.fullmatch(r"[0-9a-f]{64}", runtime_sha) is None
            or not isinstance(runtime_size, int)
            or isinstance(runtime_size, bool)
            or runtime_size != UZU_RUNTIME_RELEASE_BINARY_SIZE
            or not secrets.compare_digest(runtime_sha, UZU_RUNTIME_RELEASE_BINARY_SHA256)
            or not isinstance(model_fingerprint, str)
            or re.fullmatch(r"[0-9a-f]{64}", model_fingerprint) is None
            or capability.get("modelRegistryId") != UZU_MODEL_REGISTRY_ID
            or capability.get("modelCommit") != UZU_MODEL_COMMIT
            or capability.get("modelToolchainVersion") != UZU_MODEL_TOOLCHAIN_VERSION
            or not uzu_listener_protection_ready(runtime_identity)
            or runtime_identity.get("binaryIdentityPinned") is not True
            or runtime_identity.get("networkSandbox") is not True
            or runtime_identity.get("memorySafetyBlocked") is not False
            or runtime_identity.get("upstreamCommit") != UZU_RUNTIME_UPSTREAM_COMMIT
            or runtime_identity.get("sourcePatchSha256") != UZU_RUNTIME_SOURCE_PATCH_SHA256
            or runtime_identity.get("nativeBoundaryContractId") != UZU_NATIVE_BOUNDARY_CONTRACT_ID
            or runtime_identity.get("nativeBearerAuthentication") is not True
            or runtime_identity.get("oneUseApiKeyFile") is not True
            or runtime_identity.get("nativeContextLimit") is not True
            or runtime_identity.get("nativeOutputLimit") is not True
            or not isinstance(system_contract, dict)
            or system_contract.get("rawListenerProtected") is not True
            or system_contract.get("nativeBoundaryContractId") != UZU_NATIVE_BOUNDARY_CONTRACT_ID
            or system_contract.get("nativeBearerAuthentication") is not True
            or system_contract.get("oneUseApiKeyFile") is not True
            or system_contract.get("nativeContextLimit") is not True
            or system_contract.get("nativeOutputLimit") is not True
        ):
            raise ValueError(
                "The Uzu route no longer has a complete runtime and model receipt. Refresh models."
            )
        contract.update({
            "scope": "route", "clientAgnostic": False, "client": "chat",
            "minimumCompletionTokens": ROUTE_QUALIFICATION_MINIMUM_COMPLETION_TOKENS,
            "configuredOutputLimit": int(request["output"]),
            "measuredRequestMaxTokens": route_qualification_sample_tokens("uzu", int(request["output"])),
            "outputBudgetPolicy": uzu_qualification_output_policy(int(request["output"])),
            "modelFingerprint": model_fingerprint,
            "modelRegistryId": UZU_MODEL_REGISTRY_ID,
            "modelCommit": UZU_MODEL_COMMIT,
            "modelToolchainVersion": UZU_MODEL_TOOLCHAIN_VERSION,
            "runtimeBinarySha256": runtime_sha,
            "runtimeBinarySize": runtime_size,
            "runtimeUpstreamCommit": UZU_RUNTIME_UPSTREAM_COMMIT,
            "runtimeSourcePatchSha256": UZU_RUNTIME_SOURCE_PATCH_SHA256,
            "sandboxProfileSha256": UZU_SANDBOX_PROFILE_SHA256,
            "rawListenerProtected": True,
            "nativeBoundaryContractId": UZU_NATIVE_BOUNDARY_CONTRACT_ID,
            "nativeBearerAuthentication": True,
            "oneUseApiKeyFile": True,
            "nativeContextLimitTokens": int(request["context"]),
            "nativeMaxOutputTokens": int(request["output"]),
            "fixedAcceleration": "DFlash + Weaver",
            "kvStateDataType": "BF16",
            "prefixCache": True,
            "promptExercisePolicy": uzu_qualification_prompt_exercise_policy(
                int(request["context"])
            ),
            "osReservePolicy": "max-4gib-or-10-percent-total-v1",
            "memorySemanticsVersion": darwin_memory.MEMORY_SEMANTICS_VERSION,
            "osReserveMinimumBytes": SESSION_OS_RESERVE_MIN_BYTES,
            "osReserveBytes": max(
                SESSION_OS_RESERVE_MIN_BYTES,
                round(physical_memory_bytes() * SESSION_OS_RESERVE_FRACTION),
            ),
        })
        # For Uzu the model manifest itself is the receipt fingerprint.
        contract["receiptFingerprint"] = model_fingerprint
    return contract

def route_qualification_metrics(
    record: dict[str, Any], spec: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Recompute the bounded, authoritative public metrics for one qualified route."""
    backend = str(record.get("backend") or "")
    contract = record.get("qualificationContract")
    contract_id = contract.get("id") if isinstance(contract, dict) else None
    if spec is not None:
        legacy_qwen_v1 = bool(
            spec["backend"] == "omlx"
            and contract is None
            and record.get("qualificationVersion") == 1
        )
        if not legacy_qwen_v1 and (
            backend != spec["backend"]
            or contract_id != spec["id"]
            or not isinstance(contract, dict)
            or contract.get("version") != spec["version"]
        ):
            return None
    if (
        record.get("kind") != "route-qualification"
        or record.get("qualificationVersion") != ROUTE_QUALIFICATION_VERSION
        or backend not in {"omlx", "llamacpp", "uzu"}
        or record.get("winner") != "ar"
        or record.get("comparedModes") != ["ar"]
    ):
        return None
    modes = record.get("modes")
    route = modes.get("ar") if isinstance(modes, dict) else None
    samples = route.get("samples") if isinstance(route, dict) else None
    if (
        not isinstance(samples, list)
        or len(samples) != len(ROUTE_QUALIFICATION_SCENARIOS)
        or [sample.get("scenario") for sample in samples if isinstance(sample, dict)]
        != ROUTE_QUALIFICATION_SCENARIOS
    ):
        return None
    prompt_tokens = 0
    completion_tokens = 0
    decode: list[float] = []
    ttft: list[float] = []
    reasoning_turns = 0
    answer_turns = 0
    for sample in samples:
        if not isinstance(sample, dict):
            return None
        prompt = sample.get("promptTokens")
        completion = sample.get("completionTokens")
        speed = sample.get("decodeTokensPerSecond")
        first = sample.get("ttftSeconds")
        elapsed = sample.get("totalSeconds")
        if (
            isinstance(prompt, bool) or not isinstance(prompt, int) or prompt <= 0
            or isinstance(completion, bool) or not isinstance(completion, int) or completion <= 0
            or isinstance(speed, bool) or not isinstance(speed, (int, float))
            or not math.isfinite(float(speed)) or float(speed) <= 0
            or isinstance(first, bool) or not isinstance(first, (int, float))
            or not math.isfinite(float(first)) or float(first) <= 0
            or isinstance(elapsed, bool) or not isinstance(elapsed, (int, float))
            or not math.isfinite(float(elapsed)) or float(elapsed) <= float(first)
            or sample.get("finishReason") != "stop"
            or sample.get("terminalState") != "complete"
            or sample.get("terminalComplete") is not True
            or sample.get("responseLimitReached") is not False
        ):
            return None
        prompt_tokens += prompt
        completion_tokens += completion
        decode.append(float(speed))
        ttft.append(float(first))
        reasoning_turns += int(sample.get("reasoningObserved") is True)
        answer_turns += int(sample.get("answerObserved") is True)
    result = {
        "promptTokens": prompt_tokens,
        "completionTokens": completion_tokens,
        "sampleCount": len(samples),
        "reasoningTurns": reasoning_turns,
        "answerTurns": answer_turns,
        "medianDecodeTokensPerSecond": round(statistics.median(decode), 3),
        "minimumDecodeTokensPerSecond": round(min(decode), 3),
        "medianTTFTSeconds": round(statistics.median(ttft), 4),
    }
    if backend == "llamacpp":
        telemetry = route.get("resourceTelemetry") if isinstance(route, dict) else None
        tool = record.get("toolContract")
        unload = record.get("unloadEvidence")
        correctness = record.get("correctnessContract")
        expected_correctness_hash = hashlib.sha256(
            LLAMACPP_QUALIFICATION_CORRECTNESS_EXPECTED.encode("utf-8")
        ).hexdigest()
        expected_budget_message_hash = hashlib.sha256(
            LLAMACPP_QWEN_REASONING_BUDGET_MESSAGE.encode("utf-8")
        ).hexdigest()
        checked_ports = unload.get("checkedPorts") if isinstance(unload, dict) else None
        closed_ports = unload.get("closedPorts") if isinstance(unload, dict) else None
        valid_checked_ports = bool(
            isinstance(checked_ports, list)
            and checked_ports
            and len(checked_ports) == len(set(checked_ports))
            and all(
                isinstance(port, int) and not isinstance(port, bool) and 1 <= port <= 65_535
                for port in checked_ports
            )
        )
        peak = telemetry.get("peakProcessPhysicalFootprintBytes") if isinstance(telemetry, dict) else None
        minimum_cap = telemetry.get("metalWiredLimitMinimumBytes") if isinstance(telemetry, dict) else None
        maximum_cap = telemetry.get("metalWiredLimitMaximumBytes") if isinstance(telemetry, dict) else None
        group_peak = telemetry.get("peakProcessGroupPhysicalFootprintBytes") if isinstance(telemetry, dict) else None
        if (
            not isinstance(contract, dict)
            or contract.get("id") != "atomicchat-llamacpp-ssd-ple-8k-v1"
            or contract.get("version") != 1
            or contract.get("scope") != "route"
            or contract.get("clientAgnostic") is not True
            or record.get("client") != "any"
            or contract.get("backend") != "llamacpp"
            or contract.get("exactContext") != LLAMACPP_PLE_CONTEXT
            or isinstance(contract.get("configuredOutputLimit"), bool)
            or not isinstance(contract.get("configuredOutputLimit"), int)
            or contract.get("configuredOutputLimit") < ROUTE_QUALIFICATION_MAX_TOKENS
            or record.get("configuredOutputLimit")
            != contract.get("configuredOutputLimit")
            or record.get("measuredRequestMaxTokens")
            != ROUTE_QUALIFICATION_MAX_TOKENS
            or record.get("outputMin") != ROUTE_QUALIFICATION_MAX_TOKENS
            or record.get("outputMax") != ROUTE_QUALIFICATION_MAX_TOKENS
            or contract.get("scenarioContract") != ROUTE_QUALIFICATION_SCENARIOS
            or contract.get("sampleMaxTokens") != ROUTE_QUALIFICATION_MAX_TOKENS
            or contract.get("answerReserveTokens") != ROUTE_QUALIFICATION_ANSWER_RESERVE_TOKENS
            or contract.get("minimumDecodeTokensPerSecond") != LLAMACPP_PLE_MINIMUM_DECODE_TPS
            or contract.get("thinkingBudgetTokens") != ROUTE_QUALIFICATION_THINKING_TOKENS
            or contract.get("minimumCompletionTokens")
            != ROUTE_QUALIFICATION_MINIMUM_COMPLETION_TOKENS
            or contract.get("measuredRequestMaxTokens")
            != ROUTE_QUALIFICATION_MAX_TOKENS
            or contract.get("reasoningBoundaryContractId")
            != LLAMACPP_QUALIFICATION_REASONING_BOUNDARY_ID
            or contract.get("reasoningBudgetMessageSha256")
            != expected_budget_message_hash
            or contract.get("reasoningPolicy") != "runtime-fixed-on"
            or contract.get("toolProbeRequired") is not True
            or contract.get("memoryProofRequired") is not True
            or contract.get("memoryCeilingBytes") != LLAMACPP_PLE_MEMORY_CEILING_BYTES
            or not isinstance(contract.get("receiptFingerprint"), str)
            or re.fullmatch(r"[0-9a-f]{64}", contract["receiptFingerprint"]) is None
            or not isinstance(contract.get("runtimeVersion"), str)
            or not contract["runtimeVersion"].strip()
            or record.get("contextMin") != LLAMACPP_PLE_CONTEXT
            or record.get("contextMax") != LLAMACPP_PLE_CONTEXT
            or not isinstance(peak, int) or isinstance(peak, bool)
            or not 0 < peak < LLAMACPP_PLE_MEMORY_CEILING_BYTES
            or minimum_cap != LLAMACPP_PLE_MEMORY_CEILING_BYTES
            or maximum_cap != LLAMACPP_PLE_MEMORY_CEILING_BYTES
            or telemetry.get("metalWiredLimitSampleCount") != telemetry.get("sampleCount")
            or not isinstance(telemetry.get("sampleCount"), int)
            or isinstance(telemetry.get("sampleCount"), bool)
            or telemetry.get("sampleCount") <= 0
            or telemetry.get("processFootprintAvailable") is not True
            or telemetry.get("processFootprintSource") != "proc_pid_rusage RUSAGE_INFO_V4"
            or telemetry.get("processGroupFootprintAvailable") is not True
            or telemetry.get("samplingComplete") is not True
            or not isinstance(telemetry.get("processGroupFootprintSampleCount"), int)
            or isinstance(telemetry.get("processGroupFootprintSampleCount"), bool)
            or telemetry.get("processGroupFootprintSampleCount") <= 0
            or telemetry.get("processAliveSampleCount")
            != telemetry.get("processFootprintSampleCount")
            or telemetry.get("processAliveSampleCount")
            != telemetry.get("processGroupFootprintSampleCount")
            or telemetry.get("processGroupMemberCountMinimum") != 1
            or telemetry.get("processGroupMemberCountMaximum") != 1
            or not isinstance(group_peak, int) or isinstance(group_peak, bool)
            or not 0 < group_peak < LLAMACPP_PLE_MEMORY_CEILING_BYTES
            or reasoning_turns != len(ROUTE_QUALIFICATION_SCENARIOS)
            or answer_turns != len(ROUTE_QUALIFICATION_SCENARIOS)
            or any(speed < LLAMACPP_PLE_MINIMUM_DECODE_TPS for speed in decode)
            or any(
                sample.get("thinkingBudgetTokensRequested")
                != ROUTE_QUALIFICATION_THINKING_TOKENS
                for sample in samples
            )
            or any(
                sample.get("reasoningBudgetMessageSha256")
                != expected_budget_message_hash
                for sample in samples
            )
            or any(
                sample.get("requestedMaxTokens") != ROUTE_QUALIFICATION_MAX_TOKENS
                for sample in samples
            )
            or any(
                int(sample["completionTokens"]) > ROUTE_QUALIFICATION_MAX_TOKENS
                for sample in samples
            )
            or any(
                int(sample["completionTokens"]) < ROUTE_QUALIFICATION_MINIMUM_COMPLETION_TOKENS
                for sample in samples
            )
            or any(
                abs(
                    float(sample["decodeTokensPerSecond"])
                    - round(
                        max(1, int(sample["completionTokens"]) - 1)
                        / max(
                            0.000_001,
                            float(sample["totalSeconds"]) - float(sample["ttftSeconds"]),
                        ),
                        4,
                    )
                ) > max(0.01, float(sample["decodeTokensPerSecond"]) * 0.001)
                for sample in samples
            )
            or any(
                int(sample["promptTokens"]) + ROUTE_QUALIFICATION_MAX_TOKENS
                > LLAMACPP_PLE_CONTEXT
                for sample in samples
            )
            or not isinstance(tool, dict)
            or tool.get("protocol") != "chat-completions"
            or tool.get("toolContractValid") is not True
            or tool.get("toolCallCount") != 1
            or tool.get("toolNameSeen") is not True
            or tool.get("terminalComplete") is not True
            or tool.get("thinkingBudgetTokensRequested") != 32
            or tool.get("reasoningBudgetMessageSha256")
            != expected_budget_message_hash
            or not isinstance(correctness, dict)
            or correctness.get("id") != LLAMACPP_QUALIFICATION_CORRECTNESS_ID
            or correctness.get("expectedAnswerSha256") != expected_correctness_hash
            or correctness.get("observedAnswerSha256") != expected_correctness_hash
            or correctness.get("exact") is not True
            or correctness.get("terminalComplete") is not True
            or correctness.get("authoritativeUsage") is not True
            or correctness.get("reasoningBoundaryContractId")
            != LLAMACPP_QUALIFICATION_REASONING_BOUNDARY_ID
            or correctness.get("reasoningBudgetTokensRequested") != 0
            or correctness.get("reasoningBudgetMessageSha256")
            != expected_budget_message_hash
            or correctness.get("reasoningTagLeakDetected") is not False
            or correctness.get("transitionMessageLeakDetected") is not False
            or correctness.get("reasoningBoundaryClean") is not True
            or not isinstance(unload, dict) or unload.get("clean") is not True
            or unload.get("processExited") is not True
            or unload.get("processGroupExited") is not True
            or unload.get("managerIdle") is not True
            or unload.get("portsClosed") is not True
            or not valid_checked_ports
            or closed_ports != checked_ports
        ):
            return None
        result.update({
            "peakMemoryBytes": group_peak,
            "toolContractVerified": True,
            "cleanUnloadVerified": True,
            "correctnessVerified": True,
            "correctnessContractId": LLAMACPP_QUALIFICATION_CORRECTNESS_ID,
            "reasoningBoundaryVerified": True,
            "reasoningBoundaryContractId": LLAMACPP_QUALIFICATION_REASONING_BOUNDARY_ID,
        })
    elif backend == "uzu":
        telemetry = route.get("resourceTelemetry") if isinstance(route, dict) else None
        unload = record.get("unloadEvidence")
        correctness = record.get("correctnessContract")
        exact_context = contract.get("exactContext") if isinstance(contract, dict) else None
        suites = ROUTE_QUALIFICATION_UZU_SUITES_BY_CONTEXT
        if isinstance(exact_context, bool) or not isinstance(exact_context, int) or exact_context not in suites:
            return None
        suite = BENCHMARK_SUITES.get(suites.get(exact_context, ""), {})
        prefix_tokens = int(suite.get("prefixTokens") or 0)
        tool_tokens = int(suite.get("toolTokens") or 0)
        expected_prompt_targets = [
            uzu_conversation_target(
                scenario, prefix_tokens if index < 2 else prefix_tokens + tool_tokens,
                samples[index - 1] if index else None, int(exact_context or 0),
                UZU_QUALIFICATION_SAMPLE_MAX_TOKENS,
            )
            for index, scenario in enumerate(ROUTE_QUALIFICATION_SCENARIOS)
        ]
        configured_output = contract.get("configuredOutputLimit")
        if isinstance(configured_output, bool) or not isinstance(configured_output, int):
            return None
        output_ceiling = route_qualification_sample_tokens("uzu", configured_output)
        expected_output_limits = [
            uzu_qualification_request_tokens(scenario, target, exact_context, output_ceiling)
            for scenario, target in zip(ROUTE_QUALIFICATION_SCENARIOS, expected_prompt_targets)
        ]
        expected_id = (
            f"qwen36-uzu-dflash-weaver-{int(exact_context) // 1024}k-v5"
            if isinstance(exact_context, int) and not isinstance(exact_context, bool)
            and exact_context in suites else ""
        )
        expected_prompt_policy = (
            uzu_qualification_prompt_exercise_policy(int(exact_context))
            if isinstance(exact_context, int) and not isinstance(exact_context, bool)
            and exact_context in suites else None
        )
        expected_correctness_hash = hashlib.sha256(
            UZU_QUALIFICATION_CORRECTNESS_EXPECTED.encode("utf-8")
        ).hexdigest()
        checked_ports = unload.get("checkedPorts") if isinstance(unload, dict) else None
        closed_ports = unload.get("closedPorts") if isinstance(unload, dict) else None
        valid_checked_ports = bool(
            isinstance(checked_ports, list)
            and checked_ports
            and len(checked_ports) == len(set(checked_ports))
            and all(
                isinstance(port, int) and not isinstance(port, bool) and 1 <= port <= 65_535
                for port in checked_ports
            )
        )
        sample_count = telemetry.get("sampleCount") if isinstance(telemetry, dict) else None
        memory_count = telemetry.get("memorySampleCount") if isinstance(telemetry, dict) else None
        total_memory = telemetry.get("totalMemoryBytes") if isinstance(telemetry, dict) else None
        physical_capacity = darwin_memory.telemetry_capacity_metrics(telemetry) if isinstance(telemetry, dict) else None
        minimum_percent = physical_capacity["minimumPercent"] if physical_capacity is not None else None
        minimum_headroom = physical_capacity["minimumBytes"] if physical_capacity is not None else None
        required_reserve = (
            max(
                SESSION_OS_RESERVE_MIN_BYTES,
                round(int(total_memory) * SESSION_OS_RESERVE_FRACTION),
            )
            if isinstance(total_memory, int) and not isinstance(total_memory, bool)
            and total_memory > 0 else None
        )
        group_peak = (
            telemetry.get("peakProcessGroupPhysicalFootprintBytes")
            if isinstance(telemetry, dict) else None
        )
        runtime_sha = contract.get("runtimeBinarySha256") if isinstance(contract, dict) else None
        model_fingerprint = contract.get("modelFingerprint") if isinstance(contract, dict) else None
        if (
            not isinstance(contract, dict)
            or not expected_id
            or contract.get("id") != expected_id
            or contract.get("version") != UZU_QUALIFICATION_CONTRACT_VERSION
            or contract.get("scope") != "route"
            or contract.get("clientAgnostic") is not False
            or contract.get("client") != "chat"
            or contract.get("backend") != "uzu"
            or record.get("client") != "chat"
            or record.get("reasoning") != "auto"
            or record.get("targetKV") != "off"
            or record.get("suite") != suites.get(exact_context)
            or record.get("contextMin") != exact_context
            or record.get("contextMax") != exact_context
            or record.get("scenarioContract") != ROUTE_QUALIFICATION_SCENARIOS
            or isinstance(contract.get("configuredOutputLimit"), bool)
            or not isinstance(contract.get("configuredOutputLimit"), int)
            or configured_output < UZU_QUALIFICATION_SAMPLE_MIN_TOKENS
            or record.get("configuredOutputLimit") != contract.get("configuredOutputLimit")
            or record.get("measuredRequestMaxTokens") != max(expected_output_limits)
            or record.get("outputMin") != min(expected_output_limits)
            or record.get("outputMax") != max(expected_output_limits)
            or contract.get("measuredRequestMaxTokens") != output_ceiling
            or contract.get("outputBudgetPolicy") != uzu_qualification_output_policy(configured_output)
            or contract.get("scenarioContract") != ROUTE_QUALIFICATION_SCENARIOS
            or contract.get("sampleMaxTokens") != output_ceiling
            or contract.get("answerReserveTokens") != ROUTE_QUALIFICATION_ANSWER_RESERVE_TOKENS
            or contract.get("minimumCompletionTokens")
            != ROUTE_QUALIFICATION_MINIMUM_COMPLETION_TOKENS
            or contract.get("minimumDecodeTokensPerSecond")
            != UZU_QUALIFICATION_MINIMUM_DECODE_TPS
            or contract.get("thinkingBudgetTokens") is not None
            or contract.get("reasoningPolicy") != "runtime-default-on"
            or contract.get("toolProbeRequired") is not False
            or contract.get("memoryProofRequired") is not True
            or not uzu_qualification_memory_ceiling_supported(contract.get("memoryCeilingBytes"))
            or contract.get("osReservePolicy") != "max-4gib-or-10-percent-total-v1"
            or contract.get("memorySemanticsVersion") != darwin_memory.MEMORY_SEMANTICS_VERSION
            or contract.get("osReserveMinimumBytes") != SESSION_OS_RESERVE_MIN_BYTES
            or required_reserve is None
            or contract.get("osReserveBytes") != required_reserve
            or not isinstance(model_fingerprint, str)
            or re.fullmatch(r"[0-9a-f]{64}", model_fingerprint) is None
            or contract.get("receiptFingerprint") != model_fingerprint
            or record.get("modelFingerprint") != model_fingerprint
            or contract.get("modelRegistryId") != UZU_MODEL_REGISTRY_ID
            or contract.get("modelCommit") != UZU_MODEL_COMMIT
            or contract.get("modelToolchainVersion") != UZU_MODEL_TOOLCHAIN_VERSION
            or not isinstance(runtime_sha, str)
            or re.fullmatch(r"[0-9a-f]{64}", runtime_sha) is None
            or not secrets.compare_digest(runtime_sha, UZU_RUNTIME_RELEASE_BINARY_SHA256)
            or not isinstance(contract.get("runtimeBinarySize"), int)
            or isinstance(contract.get("runtimeBinarySize"), bool)
            or contract.get("runtimeBinarySize") != UZU_RUNTIME_RELEASE_BINARY_SIZE
            or contract.get("runtimeUpstreamCommit") != UZU_RUNTIME_UPSTREAM_COMMIT
            or contract.get("runtimeSourcePatchSha256") != UZU_RUNTIME_SOURCE_PATCH_SHA256
            or contract.get("sandboxProfileSha256") != UZU_SANDBOX_PROFILE_SHA256
            or contract.get("rawListenerProtected") is not True
            or contract.get("nativeBoundaryContractId") != UZU_NATIVE_BOUNDARY_CONTRACT_ID
            or contract.get("nativeBearerAuthentication") is not True
            or contract.get("oneUseApiKeyFile") is not True
            or contract.get("nativeContextLimitTokens") != exact_context
            or contract.get("nativeMaxOutputTokens") != contract.get("configuredOutputLimit")
            or contract.get("fixedAcceleration") != "DFlash + Weaver"
            or contract.get("kvStateDataType") != "BF16"
            or contract.get("prefixCache") is not True
            or expected_prompt_policy is None
            or contract.get("promptExercisePolicy") != expected_prompt_policy
            or not isinstance(contract.get("runtimeVersion"), str)
            or not contract["runtimeVersion"].strip()
            or contract.get("runtimeVersion") != record.get("runtimeVersion")
            or not isinstance(telemetry, dict)
            or telemetry.get("samplingComplete") is not True
            or not isinstance(sample_count, int) or isinstance(sample_count, bool)
            or sample_count <= 0
            or telemetry.get("memoryAvailable") is not True
            or telemetry.get("version") != 2
            or telemetry.get("memorySemanticsVersion") != darwin_memory.MEMORY_SEMANTICS_VERSION
            or telemetry.get("memorySource") != darwin_memory.PHYSICAL_MEMORY_SOURCE
            or physical_capacity is None
            or memory_count != sample_count
            or not isinstance(minimum_percent, (int, float))
            or isinstance(minimum_percent, bool)
            or not math.isfinite(float(minimum_percent))
            or not 0 <= float(minimum_percent) <= 100
            or not isinstance(minimum_headroom, int) or isinstance(minimum_headroom, bool)
            or minimum_headroom < required_reserve
            or telemetry.get("processFootprintAvailable") is not True
            or telemetry.get("processFootprintSource") != "proc_pid_rusage RUSAGE_INFO_V4"
            or telemetry.get("processGroupFootprintAvailable") is not True
            or not isinstance(telemetry.get("processAliveSampleCount"), int)
            or isinstance(telemetry.get("processAliveSampleCount"), bool)
            or telemetry.get("processAliveSampleCount") <= 0
            or telemetry.get("processAliveSampleCount")
            != telemetry.get("processFootprintSampleCount")
            or telemetry.get("processAliveSampleCount")
            != telemetry.get("processGroupFootprintSampleCount")
            or not isinstance(telemetry.get("processGroupMemberCountMinimum"), int)
            or isinstance(telemetry.get("processGroupMemberCountMinimum"), bool)
            or telemetry.get("processGroupMemberCountMinimum") < 1
            or not isinstance(telemetry.get("processGroupMemberCountMaximum"), int)
            or isinstance(telemetry.get("processGroupMemberCountMaximum"), bool)
            or telemetry.get("processGroupMemberCountMaximum")
            < telemetry.get("processGroupMemberCountMinimum")
            or not isinstance(group_peak, int) or isinstance(group_peak, bool)
            or not 0 < group_peak < contract["memoryCeilingBytes"]
            or reasoning_turns != len(ROUTE_QUALIFICATION_SCENARIOS)
            or answer_turns != len(ROUTE_QUALIFICATION_SCENARIOS)
            or [sample.get("targetPromptTokens") for sample in samples]
            != expected_prompt_targets
            or any(
                abs(int(sample["promptTokens"]) - expected_prompt_targets[index])
                > max(
                    UZU_QUALIFICATION_PROMPT_TOLERANCE_MIN_TOKENS,
                    round(
                        expected_prompt_targets[index]
                        * UZU_QUALIFICATION_PROMPT_TOLERANCE_FRACTION
                    ),
                )
                for index, sample in enumerate(samples)
            )
            or (
                int(exact_context) >= UZU_QUALIFICATION_NEAR_TIER_MINIMUM_CONTEXT
                and any(
                    sample.get("authoritativeUsage") is not True
                    or int(sample["promptTokens"])
                    < int(expected_prompt_policy["minimumPromptTokens"])
                    for sample in samples
                    if sample.get("scenario") in UZU_QUALIFICATION_NEAR_TIER_SCENARIOS
                )
            )
            or any(speed < UZU_QUALIFICATION_MINIMUM_DECODE_TPS for speed in decode)
            or any(
                sample.get("requestedMaxTokens") != expected_output_limits[index]
                or expected_output_limits[index] < UZU_QUALIFICATION_SAMPLE_MIN_TOKENS
                or int(sample["completionTokens"]) < ROUTE_QUALIFICATION_MINIMUM_COMPLETION_TOKENS
                or int(sample["completionTokens"]) > expected_output_limits[index]
                or int(sample["promptTokens"]) + expected_output_limits[index]
                > int(exact_context)
                for index, sample in enumerate(samples)
            )
            or not isinstance(correctness, dict)
            or correctness.get("id") != UZU_QUALIFICATION_CORRECTNESS_ID
            or correctness.get("expectedAnswerSha256") != expected_correctness_hash
            or correctness.get("observedAnswerSha256") != expected_correctness_hash
            or correctness.get("exact") is not True
            or correctness.get("terminalComplete") is not True
            or correctness.get("authoritativeUsage") is not True
            or not isinstance(unload, dict) or unload.get("clean") is not True
            or unload.get("processExited") is not True
            or unload.get("processGroupExited") is not True
            or unload.get("managerIdle") is not True
            or unload.get("portsClosed") is not True
            or not valid_checked_ports
            or closed_ports != checked_ports
        ):
            return None
        result.update({
            "peakMemoryBytes": group_peak,
            "minimumSystemHeadroomBytes": minimum_headroom,
            "systemReserveBytes": required_reserve,
            "toolContractVerified": False,
            "cleanUnloadVerified": True,
            "correctnessVerified": True,
            "correctnessContractId": UZU_QUALIFICATION_CORRECTNESS_ID,
            "reasoningBoundaryVerified": False,
            "reasoningBoundaryContractId": None,
        })
    return result

def verified_route_qualification(
    model: dict[str, Any], backend: str, evidence: dict[str, Any],
) -> dict[str, Any] | None:
    """Return only a complete local receipt-bound single-route qualification."""
    requested_context = (evidence or {}).get("context")
    spec = route_qualification_spec(
        model, backend,
        requested_context
        if isinstance(requested_context, int) and not isinstance(requested_context, bool)
        else None,
    )
    if spec is None:
        return None
    capability = model.get("backends", {}).get(backend, {})
    candidates = capability.get("localBenchmarks")
    records = [item for item in candidates if isinstance(item, dict)] if isinstance(candidates, list) else []
    latest = capability.get("localBenchmark")
    if isinstance(latest, dict) and latest not in records:
        records.append(latest)
    matches: list[dict[str, Any]] = []
    for record in records:
        metrics = route_qualification_metrics(record, spec)
        stored = record.get("qualification")
        if (
            metrics is None
            or not route_qualification_record_is_fresh(record)
            or not isinstance(stored, dict)
            or stored.get("reasoningEnabled") is not True
            or stored.get("reasoningObserved") is not True
            or stored.get("answerObserved") is not True
            or (
                backend == "llamacpp"
                and stored.get("reasoningBoundaryVerified") is not True
            )
            or stored.get("terminalCompletionObserved") is not True
            or stored.get("authoritativeUsage") is not True
            or stored.get("metrics") != metrics
            or not _local_benchmark_record_verified(capability, record, evidence)
        ):
            continue
        matches.append(record)
    if not matches:
        return None
    return copy.deepcopy(max(matches, key=lambda item: str(item.get("createdAt") or "")))

def public_route_qualification_result(
    model: dict[str, Any], record: dict[str, Any], preference: str = "throughput",
) -> dict[str, Any]:
    """Expose one qualified route without presenting it as a competition winner."""
    backend = str(record.get("backend") or "")
    record_context = record.get("contextMin")
    spec = route_qualification_spec(
        model, backend,
        record_context
        if isinstance(record_context, int) and not isinstance(record_context, bool)
        else None,
    )
    measurement = cross_engine_benchmark_measurement(record)
    metrics = route_qualification_metrics(record, spec) if spec else None
    if measurement is None or metrics is None:
        raise RuntimeError("The saved route qualification is incomplete.")
    value, profile_display, _lower_is_better = _benchmark_history_value(
        measurement, preference,
    )
    return {
        "backend": backend, "label": BACKEND_LABELS[backend],
        "qualified": True, "mode": "ar",
        "modeLabel": "Fixed DFlash + Weaver" if backend == "uzu" else "AR",
        "testedModes": ["ar"],
        "modeDetail": (
            "Qualified the exact receipt-bound llama.cpp SSD-PLE 8K route with a clean forced-"
            "reasoning handoff, final-answer output, Jinja tools, bounded memory, and clean unload."
            if backend == "llamacpp" else
            "Qualified the exact Uzu DFlash + Weaver route at this context with packaged "
            "reasoning, authoritative usage, bounded memory, and clean unload."
            if backend == "uzu" else
            "Qualified the exact Qwen PLE mmap autoregressive route with separate reasoning and final-answer output."
        ),
        "settingsLabel": benchmark_engine_settings_label(
            backend, record.get("engineSettings"),
        ),
        "routeSettingsLabel": (
            "SSD PLE · exact 8K" if backend == "llamacpp" else
            f"Fixed DFlash + Weaver · exact {int(record.get('contextMin') or 0) // 1024}K"
            if backend == "uzu" else "AR · PLE mmap"
        ),
        "display": measurement["display"],
        "profileDisplay": profile_display if value is not None else measurement["display"],
        "firstTokenSeconds": measurement.get("firstTokenSeconds"),
        "decodeTokensPerSecond": measurement.get("decodeTokensPerSecond"),
        "minimumDecodeTokensPerSecond": metrics.get("minimumDecodeTokensPerSecond"),
        "peakPressureDeltaBytes": measurement.get("peakPressureDeltaBytes"),
        "baselineHeadroomPercent": measurement.get("baselineHeadroomPercent"),
        "minimumHeadroomPercent": measurement.get("minimumHeadroomPercent"),
        "totalMemoryBytes": measurement.get("totalMemoryBytes"),
        "thermalStart": measurement.get("thermalStart"),
        "thermalStartValue": measurement.get("thermalStartValue"),
        "thermalWorst": measurement.get("thermalWorst"),
        "thermalWorstValue": measurement.get("thermalWorstValue"),
        "lowPowerMode": measurement.get("lowPowerMode"),
        "resourceCooldownStatus": measurement.get("resourceCooldownStatus"),
        "promptTokens": metrics["promptTokens"],
        "completionTokens": metrics["completionTokens"],
        "configuredOutputLimit": record.get("configuredOutputLimit"),
        "measuredRequestMaxTokens": record.get("measuredRequestMaxTokens"),
        "reasoningTurns": metrics["reasoningTurns"],
        "answerTurns": metrics["answerTurns"],
        "sampleCount": metrics["sampleCount"],
        "peakMemoryBytes": metrics.get("peakMemoryBytes"),
        "reasoningObserved": metrics["reasoningTurns"] == metrics["sampleCount"],
        "answerObserved": metrics["answerTurns"] == metrics["sampleCount"],
        "toolContractVerified": metrics.get("toolContractVerified") is True,
        "cleanUnloadVerified": metrics.get("cleanUnloadVerified") is True,
        "correctnessVerified": metrics.get("correctnessVerified") is True,
        "correctnessContractId": metrics.get("correctnessContractId"),
        "reasoningBoundaryVerified": metrics.get("reasoningBoundaryVerified") is True,
        "reasoningBoundaryContractId": metrics.get("reasoningBoundaryContractId"),
        "recordId": record.get("id"),
        "runtimeVersion": record.get("runtimeVersion"),
    }
