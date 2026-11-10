"""Frozen complete pre-extraction capacity/admission domain. Test-only."""

def qwen4_qsa_allocation_high_water_tokens(context: int, step: int) -> int:
    """Bound the largest QSA capacity reachable by any prefill/decode split."""
    if context <= 0 or step <= 0:
        return 0
    rounded_context = ((context + step - 1) // step) * step
    largest_managed_capacity_below_context = ((context - 1) // step) * step
    doubled_capacity = 2 * largest_managed_capacity_below_context
    return max(step, rounded_context, doubled_capacity)

def public_session_resource(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Expose physical reclaimable capacity separately from macOS pressure."""
    condition = benchmark_resource_condition(snapshot)
    total = int(condition.get("totalMemoryBytes") or snapshot.get("totalBytes") or 0)
    pressure = snapshot.get("freePercent")
    pressure_ready = bool(
        snapshot.get("memoryAvailable") is True
        and isinstance(pressure, (int, float)) and not isinstance(pressure, bool)
        and math.isfinite(float(pressure)) and 0 <= float(pressure) <= 100
    )
    return {
        "memorySemanticsVersion": darwin_memory.MEMORY_SEMANTICS_VERSION,
        "memoryAvailable": condition.get("memoryAvailable") is True,
        "memorySource": condition.get("memorySource"),
        "totalMemoryBytes": total if total > 0 else None,
        "headroomPercent": condition.get("headroomPercent"),
        "headroomBytes": condition.get("headroomBytes"),
        "pressureAvailable": pressure_ready,
        "pressureFreePercent": float(pressure) if pressure_ready else None,
        "pressureSource": snapshot.get("memorySource") if pressure_ready else None,
        "thermalAvailable": condition.get("thermalAvailable") is True,
        "thermalState": str(condition.get("thermalState") or "unavailable"),
        "thermalStateValue": condition.get("thermalStateValue"),
        "lowPowerMode": condition.get("lowPowerMode"),
        "metalWiredLimitBytes": max(0, int(snapshot.get("metalWiredLimitBytes") or 0)),
        "metalRecommendedWorkingSetBytes": max(0, int(snapshot.get("metalRecommendedWorkingSetBytes") or 0)),
        "capturedAt": datetime.now(timezone.utc).isoformat(),
    }

def dflash_quantized_fallback(backend: str, options: dict[str, Any]) -> bool:
    return bool(
        isinstance(options, dict) and backend == "omlx"
        and options.get("acceleration") == "dflash"
        and options.get("kv") in {"q4", "q6", "q8"}
    )

def effective_kv_precision(backend: str, options: dict[str, Any]) -> str:
    """Cache precision wired at launch; incompatible DDTree requests are rejected."""
    if (backend == "omlx" and options.get("acceleration") == "dflash"
            and options.get("dflashVerify", "adaptive") == "ddtree"):
        return "off"
    return str(options.get("kv") or "off")

def launch_memory_estimate(
    request: dict[str, Any], model: dict[str, Any], resource: dict[str, Any],
) -> dict[str, Any]:
    """Estimate conservative full-selected-context capacity without loading model code."""
    options = request.get("options") if isinstance(request.get("options"), dict) else {}
    backend = str(request.get("backend") or "")
    context = int(request.get("context") or 0)
    requested_kv = str(options.get("kv") or "off")
    kv = effective_kv_precision(backend, options)
    if backend == "slotstream" and model.get("slotstream"):
        memory_gb = _profile_integer(options.get("memoryGB"), slotstream_runtime.DEFAULT_MEMORY_GB, 12, None, "Slotstream process memory (GB)")
        budget = memory_gb * 1_000_000_000
        total = int(resource.get("totalMemoryBytes") or 0)
        reserve = max(SESSION_OS_RESERVE_MIN_BYTES, round(total * SESSION_OS_RESERVE_FRACTION))
        automatic = options.get("memoryMode", "auto") == "auto"
        if automatic:
            budget = min(budget, max(12_000_000_000, int(resource.get("headroomBytes") or 0) - reserve))
        return {"version": SESSION_MEMORY_ESTIMATE_VERSION, "modelBytes": 0,
                "ssdWeightBytes": int(model["size"]), "companionBytes": 0, "companionLabels": [],
                "kvCacheBytes": 0, "kvPrecision": "native · included in process budget", "kvScalarBytes": None,
                "contextTokens": context, "parallelLanes": 1, "runtimeReserveBytes": budget,
                "estimatedWorkingSetBytes": budget, "osReserveBytes": reserve,
                "requiredHeadroomBytes": budget + reserve, "geometryReady": True,
                "geometry": {"ready": True, "slotstream": True},
                "memoryCeilingBytes": memory_gb * 1_000_000_000 + 2 * 1024**3, "ssdStreaming": True,
                "basis": "Whole-process memory budget including expert cache, MTP, active context and retained prefix. Automatic sizing can shrink the expert cache within this ceiling. The native memory planner rechecks full selected-context feasibility before launch; this is a budget, not a measured peak."}
    if backend == "kolibri" and model.get("kolibri"):
        memory = kolibri_runtime.memory_plan(model["kolibri"], context, options, resource)
        return {**memory, "version": SESSION_MEMORY_ESTIMATE_VERSION,
                "modelBytes": memory["residentWeightBytes"], "ssdWeightBytes": model["size"],
                "companionBytes": 0, "companionLabels": [], "parallelLanes": 1,
                "kvScalarBytes": 2 if memory["kv"] == "off" else None,
                "geometryReady": True, "geometry": {"ready": True, "kolibri": True},
                "ssdStreaming": True}
    if backend == "splash" and model.get("splash"):
        estimate = splash_runtime.memory_estimate(model["splash"], context)
        total = int(resource.get("totalMemoryBytes") or 0)
        reserve = max(SESSION_OS_RESERVE_MIN_BYTES, round(total * SESSION_OS_RESERVE_FRACTION))
        working = int(estimate["estimatedWorkingSetBytes"])
        return {
            "version": SESSION_MEMORY_ESTIMATE_VERSION,
            "modelBytes": estimate["modelBytes"],
            "ssdWeightBytes": 0,
            "companionBytes": estimate["runtimeReserveBytes"],
            "companionLabels": ["Splash runtime reserve"],
            "kvCacheBytes": estimate["kvCacheBytes"],
            "kvPrecision": estimate["kvPrecision"],
            "kvScalarBytes": None,
            "contextTokens": context,
            "parallelLanes": estimate["parallelLanes"],
            "runtimeReserveBytes": estimate["runtimeReserveBytes"],
            "estimatedWorkingSetBytes": working,
            "osReserveBytes": reserve,
            "requiredHeadroomBytes": working + reserve,
            "geometryReady": True,
            "geometry": {"ready": True, "splash": True},
            "basis": estimate["basis"],
        }
    if backend == "whallm" and model.get("nativeWhallm"):
        working_set = whallm_runtime.WORKING_SET_BYTES
        total = int(resource.get("totalMemoryBytes") or 0)
        reserve = max(SESSION_OS_RESERVE_MIN_BYTES, round(total * SESSION_OS_RESERVE_FRACTION))
        resident = int(model["nativeWhallm"]["commonBytes"]) + whallm_runtime.SLOTS * 2_611_200
        return {
            "version": SESSION_MEMORY_ESTIMATE_VERSION, "modelBytes": resident,
            "ssdWeightBytes": int(model["size"]), "companionBytes": 0, "companionLabels": [],
            "kvCacheBytes": 0, "kvPrecision": "MXFP8 · included in working-set allowance", "kvScalarBytes": None,
            "contextTokens": context, "parallelLanes": 1,
            "runtimeReserveBytes": max(0, working_set - resident),
            "estimatedWorkingSetBytes": working_set, "osReserveBytes": reserve,
            "requiredHeadroomBytes": working_set + reserve,
            "geometryReady": True, "geometry": {"ready": True, "nativeWhallm": True},
            "memoryCeilingBytes": whallm_runtime.MEMORY_BYTES, "nativeWhallm": True,
            "basis": "Bounded 4,096-slot full-expert runtime with 2 GiB prompt cache and 16K context; 125 GB of SSD weights are not fully resident RAM. The 26 GiB working-set allowance includes margin above the initial 23 GiB observation; it is an estimate, not a measured 16K process peak.",
        }
    if backend == "whallm" and model.get("sharedServer") is True:
        bridge_reserve = 512 * 1024**2
        return {
            "version": SESSION_MEMORY_ESTIMATE_VERSION,
            "modelBytes": 0,
            "companionBytes": 0,
            "companionLabels": [],
            "kvCacheBytes": 0,
            "kvPrecision": "Whallm-managed",
            "kvScalarBytes": None,
            "contextTokens": context,
            "parallelLanes": 1,
            "runtimeReserveBytes": bridge_reserve,
            "estimatedWorkingSetBytes": bridge_reserve,
            "osReserveBytes": 0,
            "requiredHeadroomBytes": bridge_reserve,
            "geometryReady": True,
            "geometry": {"ready": True, "sharedServer": True},
            "sharedEngine": True,
            "observedMlxActiveMemoryBytes": WHALLM_MEASURED_PEAK_BYTES,
            "basis": (
                "Whallm is already serving this model before it becomes selectable. The launcher adds only a bounded "
                "private bridge; Whallm owns model, KV, and SSD-cache memory. Upstream's M5 Pro measurements reached "
                "22.75 GiB of MLX active memory through the published 16K-input case; this is not process RSS, and "
                "Whallm's official support floor remains 64 GiB."
            ),
        }
    if backend == "freetoken" and model.get("remote") is True:
        return {
            "version": SESSION_MEMORY_ESTIMATE_VERSION,
            "modelBytes": 0,
            "companionBytes": 0,
            "companionLabels": [],
            "kvCacheBytes": 0,
            "kvPrecision": "server-managed",
            "kvScalarBytes": 0,
            "contextTokens": context,
            "parallelLanes": 1,
            "runtimeReserveBytes": 0,
            "estimatedWorkingSetBytes": 0,
            "osReserveBytes": 0,
            "requiredHeadroomBytes": 0,
            "geometryReady": False,
            "geometry": {"ready": False, "remote": True},
            "remoteEngine": True,
            "basis": "Model weights, KV cache, and MoE execution remain on the configured FreeToken server; this Mac owns only bounded launcher bridges and the selected work surface.",
        }
    if backend == "freetoken" and model.get("nativeFreetoken") is True:
        capability = model.get("backends", {}).get("freetoken", {})
        contract = capability.get("nativeContract", {})
        sizing = contract.get("sizing", {}) if isinstance(contract, dict) else {}
        per_token = sizing.get("kv_cache_bytes_per_token")
        model_bytes = sizing.get("weight_bytes")
        geometry_ready = bool(
            isinstance(per_token, int) and not isinstance(per_token, bool) and per_token > 0
            and isinstance(model_bytes, int) and not isinstance(model_bytes, bool) and model_bytes > 0
        )
        model_bytes = int(model_bytes) if geometry_ready else max(0, int(model.get("size") or 0))
        lanes = bounded_integer(
            options.get("maxBatchSize"), 1, 1, FREETOKEN_NATIVE_MAX_BATCH_SIZE,
            "FreeToken maximum batch size",
        )
        kv_bytes = int(per_token) * context * lanes if geometry_ready else 0
        runtime_reserve = SESSION_RUNTIME_BASE_RESERVE_BYTES + round(model_bytes * 0.08)
        working_set = model_bytes + kv_bytes + runtime_reserve
        total = int(resource.get("totalMemoryBytes") or 0)
        os_reserve = max(
            SESSION_OS_RESERVE_MIN_BYTES,
            round(total * SESSION_OS_RESERVE_FRACTION) if total > 0 else 0,
        )
        return {
            "version": SESSION_MEMORY_ESTIMATE_VERSION,
            "modelBytes": model_bytes,
            "companionBytes": 0,
            "companionLabels": [],
            "kvCacheBytes": kv_bytes,
            "kvPrecision": "full",
            "kvScalarBytes": None,
            "contextTokens": context,
            "parallelLanes": lanes,
            "runtimeReserveBytes": runtime_reserve,
            "estimatedWorkingSetBytes": working_set,
            "osReserveBytes": os_reserve,
            "requiredHeadroomBytes": working_set + os_reserve,
            "geometryReady": geometry_ready,
            "geometry": {
                "ready": geometry_ready,
                "source": "freetoken-native-capability-schema",
                "kvCacheBytesPerToken": int(per_token) if geometry_ready else None,
            },
            "nativeFreeToken": True,
            "basis": "Native FreeToken schema v1 weight and per-token KV sizing at the full selected context, plus a conservative launcher runtime and macOS reserve.",
        }
    if backend == "uzu" and model.get("uzuNative") is True:
        geometry = model.get("memoryGeometry") if isinstance(model.get("memoryGeometry"), dict) else {}
        geometry_ready = bool(geometry.get("ready") is True)
        target_kv_bytes = 0
        draft_kv_bytes = 0
        kv_bytes = 0
        if geometry_ready and context > 0:
            target_kv_bytes = round(
                2 * int(geometry["fullAttentionLayers"]) * context
                * int(geometry["kvHeads"]) * int(geometry["headDimension"]) * 2.0
            )
            draft_kv_bytes = (
                context * UZU_DRAFT_FULL_ATTENTION_BYTES_PER_TOKEN
                + UZU_DRAFT_SLIDING_CACHE_BYTES
            )
            kv_bytes = target_kv_bytes + draft_kv_bytes
        target_bytes = next(
            size for name, size, _crc in UZU_MODEL_FILE_MANIFEST
            if name == "model.safetensors"
        )
        draft_bytes = next(
            size for name, size, _crc in UZU_MODEL_FILE_MANIFEST
            if name == "speculator/model.safetensors"
        )
        total_weights = target_bytes + draft_bytes
        long_context_steps = (
            context // UZU_LONG_CONTEXT_PREFILL_RESERVE_STEP_TOKENS
            if context >= UZU_LONG_CONTEXT_PREFILL_RESERVE_STEP_TOKENS else 0
        )
        prefill_transient_reserve = (
            long_context_steps * UZU_LONG_CONTEXT_PREFILL_RESERVE_STEP_BYTES
        )
        runtime_reserve = (
            SESSION_RUNTIME_BASE_RESERVE_BYTES
            + round(total_weights * 0.08)
            + prefill_transient_reserve
        )
        working_set = total_weights + kv_bytes + runtime_reserve
        total = int(resource.get("totalMemoryBytes") or 0)
        os_reserve = max(
            SESSION_OS_RESERVE_MIN_BYTES,
            round(total * SESSION_OS_RESERVE_FRACTION) if total > 0 else 0,
        )
        return {
            "version": SESSION_MEMORY_ESTIMATE_VERSION,
            "modelBytes": target_bytes,
            "companionBytes": draft_bytes,
            "companionLabels": ["bundled DFlash draft"],
            "kvCacheBytes": kv_bytes,
            "targetKvCacheBytes": target_kv_bytes,
            "draftKvCacheBytes": draft_kv_bytes,
            "kvPrecision": "BF16 · runtime fixed",
            "kvScalarBytes": 2.0,
            "contextTokens": context,
            "parallelLanes": 1,
            "runtimeReserveBytes": runtime_reserve,
            "prefillTransientReserveBytes": prefill_transient_reserve,
            "estimatedWorkingSetBytes": working_set,
            "osReserveBytes": os_reserve,
            "requiredHeadroomBytes": working_set + os_reserve,
            "processMemoryCeilingBytes": UZU_PROCESS_MEMORY_CEILING_BYTES,
            "processCeilingAdmissionMarginBytes": UZU_PROCESS_CEILING_ADMISSION_MARGIN_BYTES,
            "geometryReady": geometry_ready,
            "geometry": copy.deepcopy(geometry),
            "uzuSpeculative": True,
            "estimateIsConservative": True,
            "basis": (
                "Pinned Uzu target plus bundled DFlash draft, runtime-fixed BF16 target and draft "
                "KV at the selected exact context (including the draft sliding window), a separate "
                "long-context prefill reserve, runtime workspace, and protected macOS reserve. "
                "Admission also keeps a margin below the independent live process-group ceiling; "
                "the whole-Mac headroom guard can stop the route sooner."
            ),
        }
    qwen4_ple = model.get("qwen4Ple") if isinstance(model.get("qwen4Ple"), dict) else {}
    if backend == "omlx" and qwen4_ple.get("supported") is True:
        geometry = model.get("memoryGeometry") if isinstance(model.get("memoryGeometry"), dict) else {}
        bytes_per_token = geometry.get("fullBytesPerToken")
        allocation_step = geometry.get("qsaAllocationStepTokens")
        geometry_ready = bool(
            geometry.get("ready") is True
            and geometry.get("qwen4Qsa") is True
            and isinstance(bytes_per_token, int) and not isinstance(bytes_per_token, bool)
            and bytes_per_token > 0
            and isinstance(allocation_step, int) and not isinstance(allocation_step, bool)
            and allocation_step == OMLX_QWEN4_QSA_ALLOCATION_STEP_TOKENS
        )
        allocated_context = (
            qwen4_qsa_allocation_high_water_tokens(
                context, int(allocation_step),
            )
            if geometry_ready and context > 0 else 0
        )
        kv_bytes = (
            int(bytes_per_token) * allocated_context
            if geometry_ready and allocated_context > 0 else 0
        )
        model_bytes = max(0, int(qwen4_ple.get("residentBytes") or 0))
        offload_options = omlx_expert_offload_options(model, options)
        expert_savings = (int(model["omlxExpertOffload"]["expertBytes"] * (1 - offload_options[0])) if offload_options else 0)
        model_bytes = max(0, model_bytes - expert_savings)
        checkpoint_bytes = max(0, int(qwen4_ple.get("checkpointBytes") or 0))
        ple_bytes = max(0, int(qwen4_ple.get("pleBytes") or 0))
        runtime_reserve = SESSION_RUNTIME_BASE_RESERVE_BYTES
        working_set = model_bytes + kv_bytes + runtime_reserve
        total = int(resource.get("totalMemoryBytes") or 0)
        os_reserve = max(
            SESSION_OS_RESERVE_MIN_BYTES,
            round(total * SESSION_OS_RESERVE_FRACTION) if total > 0 else 0,
        )
        metal_estimate = model_bytes + kv_bytes + OMLX_QWEN4_METAL_WORKSPACE_BYTES
        gib = 1024**3
        guarded_metal_estimate = math.ceil(
            metal_estimate / OMLX_QWEN4_METAL_PREFILL_SAFE_RATIO
        )
        required_metal_limit = max(
            0 if offload_options else OMLX_QWEN4_METAL_FLOOR_BYTES,
            ((guarded_metal_estimate + gib - 1) // gib) * gib,
        )
        memory_guard = "high" if offload_options else str(options.get("memoryGuard") or "balanced")
        return {
            "version": SESSION_MEMORY_ESTIMATE_VERSION,
            "modelBytes": model_bytes,
            "checkpointBytes": checkpoint_bytes,
            "pleBytes": ple_bytes,
            "ssdPleBytes": ple_bytes,
            "expertOffload": bool(offload_options),
            "expertResidentPercent": offload_options[0] * 100 if offload_options else None,
            "expertOffloadSavedBytes": expert_savings,
            "pleMmap": True,
            "pleStorage": "mmap",
            "memoryGuard": memory_guard,
            "memoryGuardCeilingBytes": (
                offload_options[1] if offload_options else OMLX_QWEN4_HIGH_MEMORY_CEILING_BYTES
                if memory_guard == "high" else 0
            ),
            "memoryGuardHardWatermarkBytes": (
                int(offload_options[1] * OMLX_QWEN4_HIGH_MEMORY_HARD_THRESHOLD) if offload_options else OMLX_QWEN4_HIGH_MEMORY_HARD_BYTES
                if memory_guard == "high" else 0
            ),
            "requiredMetalWiredLimitBytes": required_metal_limit,
            "companionBytes": 0,
            "companionLabels": [],
            "kvCacheBytes": kv_bytes,
            "kvPrecision": "full",
            "kvScalarBytes": 2.0,
            "contextTokens": context,
            "allocatedContextTokens": allocated_context,
            "contextAllocationStepTokens": (
                int(allocation_step) if geometry_ready else None
            ),
            "parallelLanes": 1,
            "runtimeReserveBytes": runtime_reserve,
            "estimatedWorkingSetBytes": working_set,
            "osReserveBytes": os_reserve,
            "requiredHeadroomBytes": working_set + os_reserve,
            "geometryReady": geometry_ready,
            "geometry": copy.deepcopy(geometry),
            "estimateIsConservative": True,
            "basis": (
                "Qwen4 PLE capacity: the indexed N-gram table is read-only SSD mmap, the remaining checkpoint "
                "uses oMLX's 1.05 resident estimate, QSA raw and pooled index keys plus MRoPE positions stay full precision, "
                "the active cache is charged for 8,192-token growth and a worst-case prefill-to-decode doubling, "
                "and runtime plus macOS reserves remain separate. The context-derived Metal limit includes "
                "oMLX's 95% prefill safety margin and is checked independently from the process guard. "
                + ("Expert tensor savings are subtracted once for the selected resident share; the complete routing remains available from SSD."
                   if offload_options else "This is not swap or expert streaming.")
            ),
        }
    if backend in SSD_STREAMING_BACKENDS:
        capability = model.get("backends", {}).get(backend, {})
        ssd_profile = capability.get("ssdProfile") if isinstance(capability.get("ssdProfile"), dict) else {}
        weight_bytes = max(0, int(ssd_profile.get("weightBytes") or model.get("size") or 0))
        experts = max(1, int(ssd_profile.get("expertCount") or 1))
        top_k = max(1, int(ssd_profile.get("nativeExpertTopK") or 1))
        active_fraction = min(1.0, float(top_k) / float(experts))
        # Shared tensors, active routed experts, bounded double buffering, and
        # server workspace remain resident. The inactive expert store stays on
        # SSD and is intentionally excluded from unified-memory admission.
        resident_weights = min(
            weight_bytes,
            round(weight_bytes * min(0.35, 0.08 + active_fraction * 2.0))
            + 1_073_741_824,
        )
        geometry = model.get("memoryGeometry") if isinstance(model.get("memoryGeometry"), dict) else {}
        kv_bytes = 0
        if geometry.get("ready") and context > 0:
            kv_bytes = round(
                2 * int(geometry["fullAttentionLayers"]) * context
                * int(geometry["kvHeads"]) * int(geometry["headDimension"]) * 2.0
            )
        runtime_reserve = SESSION_RUNTIME_BASE_RESERVE_BYTES
        working_set = resident_weights + kv_bytes + runtime_reserve
        total = int(resource.get("totalMemoryBytes") or 0)
        os_reserve = max(
            SESSION_OS_RESERVE_MIN_BYTES,
            round(total * SESSION_OS_RESERVE_FRACTION) if total > 0 else 0,
        )
        return {
            "version": SESSION_MEMORY_ESTIMATE_VERSION,
            "modelBytes": resident_weights,
            "ssdWeightBytes": weight_bytes,
            "ssdStreamedBytes": max(0, weight_bytes - resident_weights),
            "companionBytes": 0, "companionLabels": [],
            "kvCacheBytes": kv_bytes, "kvPrecision": "full", "kvScalarBytes": 2.0,
            "contextTokens": context, "parallelLanes": 1,
            "runtimeReserveBytes": runtime_reserve,
            "estimatedWorkingSetBytes": working_set,
            "osReserveBytes": os_reserve,
            "requiredHeadroomBytes": working_set + os_reserve,
            "geometryReady": geometry.get("ready") is True,
            "geometry": copy.deepcopy(geometry),
            "ssdStreaming": True,
            "estimateIsConservative": True,
            "basis": (
                "Conservative SSD-streaming working set: shared tensors, native top-k routed experts, "
                "double-buffered I/O, full-precision KV at the selected context, runtime workspace, and macOS reserve."
            ),
        }
    geometry = model.get("memoryGeometry") if isinstance(model.get("memoryGeometry"), dict) else {}
    geometry_ready = bool(geometry.get("ready"))
    scalar_bytes = {
        # Quantized MLX caches also carry bounded per-group scale/bias data.
        "off": 2.0, "q8": 1.0625, "q6": 0.8125, "q4": 0.5625,
    }.get(kv, 2.0)
    lanes = int(options.get("parallel") or 1) if backend == "lmstudio" else 1
    lanes = min(16, max(1, lanes))
    kv_bytes = 0
    if geometry_ready and context > 0:
        kv_bytes = round(
            2
            * int(geometry["fullAttentionLayers"])
            * context
            * int(geometry["kvHeads"])
            * int(geometry["headDimension"])
            * scalar_bytes
            * lanes
        )

    model_bytes = max(0, int(model.get("size") or 0))
    capability = model.get("backends", {}).get(backend, {})
    acceleration = str(options.get("acceleration") or "auto")
    companion_bytes = 0
    companion_labels: list[str] = []
    if acceleration == "dflash" and backend == "omlx":
        draft_bytes = max(0, int(capability.get("dflashDraftSize") or 0))
        if draft_bytes:
            companion_bytes += draft_bytes
            companion_labels.append("DFlash 2 draft")
    sidecar_bytes = max(0, int(model.get("mtpSidecarSize") or 0))
    uses_sidecar = bool(
        backend in {"lmstudio", "mtplx"} and sidecar_bytes
        and acceleration != "off"
        and (acceleration == "mtp" or capability.get("mtp") is True)
    )
    if uses_sidecar:
        companion_bytes += sidecar_bytes
        companion_labels.append("MTP sidecar")
    if backend == "omlx" and str(options.get("anePrefill") or "off") == "tuned":
        # The guarded upstream path materialises an additional low-precision ANE slice.
        ane_slice = round(model_bytes * 0.25)
        companion_bytes += ane_slice
        companion_labels.append("ANE prefill slice")
        ane_record = capability.get("aneTuning") if isinstance(capability, dict) else None
        recommendation = ane_record.get("recommendation") if isinstance(ane_record, dict) else None
        if isinstance(recommendation, dict) and recommendation.get("cpu_enabled") is True:
            # Upstream's shared CPU path needs additional compiled/dequantised workspace.
            companion_bytes += ANE_TUNER_RESERVE_BYTES
            companion_labels.append("CPU-sharing workspace")

    runtime_reserve = SESSION_RUNTIME_BASE_RESERVE_BYTES + round(model_bytes * 0.08)
    working_set = model_bytes + companion_bytes + kv_bytes + runtime_reserve
    total = int(resource.get("totalMemoryBytes") or 0)
    os_reserve = max(
        SESSION_OS_RESERVE_MIN_BYTES,
        round(total * SESSION_OS_RESERVE_FRACTION) if total > 0 else 0,
    )
    return {
        "version": SESSION_MEMORY_ESTIMATE_VERSION,
        "modelBytes": model_bytes,
        "companionBytes": companion_bytes,
        "companionLabels": companion_labels,
        "kvCacheBytes": kv_bytes,
        "kvPrecision": kv,
        "requestedKvPrecision": requested_kv,
        "kvScalarBytes": scalar_bytes,
        "contextTokens": context,
        "parallelLanes": lanes,
        "runtimeReserveBytes": runtime_reserve,
        "estimatedWorkingSetBytes": working_set,
        "osReserveBytes": os_reserve,
        "requiredHeadroomBytes": working_set + os_reserve,
        "geometryReady": geometry_ready,
        "geometry": copy.deepcopy(geometry),
        "basis": (
            "Conservative capacity at the full selected context; actual paged-cache residency can be lower."
            + (
                f" DDTree requires full-precision KV; switch to Adaptive or Fixed DFlash to use {requested_kv.upper()}."
                if kv != requested_kv else ""
            )
        ),
    }

def _llamacpp_qualified_session_capacity(
    request: dict[str, Any], model: dict[str, Any], resource: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any]]:
    """Resolve one fresh exact qualification without using GGUF file size as RAM."""
    record: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    try:
        sampling_contract = validated_sampling_contract(
            model, request, str(request["client"]),
            request.get("chat") if isinstance(request.get("chat"), dict) else None,
        )
        evidence = optimizer_evidence(
            model, int(request["context"]), int(request["output"]),
            str(request["client"]), str(request["reasoning"]),
            str(request.get("options", {}).get("kv") or "off"),
            request.get("chat") if isinstance(request.get("chat"), dict) else None,
            sampling_contract,
        )
        add_benchmark_engine_evidence(
            evidence, model,
            request.get("options") if isinstance(request.get("options"), dict) else {},
            ["llamacpp"],
        )
        record = verified_route_qualification(model, "llamacpp", evidence)
        spec = route_qualification_spec(model, "llamacpp")
        metrics = route_qualification_metrics(record, spec) if record and spec else None
    except (KeyError, TypeError, ValueError):
        record = None
        metrics = None
    peak = (
        int(metrics["peakMemoryBytes"])
        if isinstance(metrics, dict)
        and isinstance(metrics.get("peakMemoryBytes"), int)
        and not isinstance(metrics.get("peakMemoryBytes"), bool)
        else 0
    )
    reserve = SESSION_OS_RESERVE_MIN_BYTES
    estimate = {
        "version": SESSION_MEMORY_ESTIMATE_VERSION,
        "qualifiedRoute": record is not None and metrics is not None and peak > 0,
        "qualificationRecordId": str(record.get("id") or "") if record else "",
        "qualificationCreatedAt": str(record.get("createdAt") or "") if record else "",
        "artifactBytesOnDisk": max(0, int(model.get("size") or 0)),
        "measuredProcessGroupPeakBytes": peak or None,
        "estimatedWorkingSetBytes": peak,
        "requiredHeadroomBytes": peak + reserve if peak else reserve,
        "osReserveBytes": reserve,
        "memoryCeilingBytes": LLAMACPP_PLE_MEMORY_CEILING_BYTES,
        "contextTokens": LLAMACPP_PLE_CONTEXT,
        "parallelLanes": 1,
        "geometryReady": True,
        "ssdPle": True,
        "estimateIsMeasured": peak > 0,
        "basis": (
            "Exact local route qualification process-group peak plus a protected 4 GiB macOS reserve. "
            "The 79 GiB split GGUF is an on-disk artifact and is not treated as a resident-memory estimate."
            if peak else
            "No fresh exact route qualification is bound to these visible settings; the on-disk GGUF size is not used as a bypassable RAM warning."
        ),
    }
    return record, metrics, estimate

def uzu_estimate_within_process_ceiling(estimate: dict[str, Any]) -> bool:
    """Keep estimated Uzu residency safely below the independent live stop."""
    working_set = estimate.get("estimatedWorkingSetBytes")
    ceiling = estimate.get("processMemoryCeilingBytes")
    margin = estimate.get("processCeilingAdmissionMarginBytes")
    return bool(
        isinstance(working_set, int) and not isinstance(working_set, bool)
        and isinstance(ceiling, int) and not isinstance(ceiling, bool)
        and isinstance(margin, int) and not isinstance(margin, bool)
        and working_set > 0 and margin >= 0
        and working_set + margin < ceiling
    )

def _uzu_qualified_session_record(
    request: dict[str, Any], model: dict[str, Any],
) -> dict[str, Any] | None:
    """Resolve capacity only, without promoting Chat measurements as Pi speed.

    The tested Pi transport shares the native sampler, context/output bounds,
    and live process guard. Its capacity can use the exact Chat receipt; the
    original receipt and all optimizer/performance client bindings stay intact.
    """
    try:
        sampling_contract = validated_sampling_contract(
            model, request, str(request["client"]),
            request.get("chat") if isinstance(request.get("chat"), dict) else None,
        )
        evidence = optimizer_evidence(
            model, int(request["context"]), int(request["output"]),
            str(request["client"]), str(request["reasoning"]),
            str(request.get("options", {}).get("kv") or "off"),
            request.get("chat") if isinstance(request.get("chat"), dict) else None,
            sampling_contract,
        )
        add_benchmark_engine_evidence(
            evidence, model,
            request.get("options") if isinstance(request.get("options"), dict) else {},
            ["uzu"],
        )
        if request.get("client") == "pi":
            if not uzu_pi_transport_supported(model.get("backends", {}).get("uzu")):
                return None
            evidence["client"] = "chat"
        exact = verified_route_qualification(model, "uzu", evidence)
        if exact is not None:
            return exact
        # Capacity is bounded by the total context window and live memory
        # guard, not by a larger per-response ceiling. Reuse only when the
        # bounded probe budget is identical; never relabel the stored receipt
        # or use this relaxation for optimizer/performance comparisons.
        requested_output = request.get("output")
        if (
            isinstance(requested_output, bool) or not isinstance(requested_output, int)
            or not 0 < requested_output <= int(request["context"])
        ):
            return None
        capability = model.get("backends", {}).get("uzu", {})
        records = list(capability.get("localBenchmarks") or [])
        if isinstance(capability.get("localBenchmark"), dict):
            records.append(capability["localBenchmark"])
        probe_budget = route_qualification_sample_tokens("uzu", requested_output)
        outputs = sorted({
            record["configuredOutputLimit"] for record in records
            if isinstance(record, dict)
            and isinstance(record.get("configuredOutputLimit"), int)
            and not isinstance(record.get("configuredOutputLimit"), bool)
            and record["configuredOutputLimit"] != requested_output
            and record.get("measuredRequestMaxTokens") == probe_budget
            and route_qualification_sample_tokens("uzu", record["configuredOutputLimit"]) == probe_budget
        }, reverse=True)
        for output in outputs:
            candidate_evidence = copy.deepcopy(evidence)
            candidate_evidence["output"] = output
            candidate = verified_route_qualification(model, "uzu", candidate_evidence)
            if candidate is not None:
                return candidate
        return None
    except (KeyError, TypeError, ValueError):
        return None

def uzu_qualification_memory_ceiling_supported(value: Any) -> bool:
    """Retain receipts measured under the previous, stricter 36 GiB guard.

    Their measured peak must still be below their recorded ceiling. This does
    not upgrade their context tier or rewrite historical qualification evidence.
    """
    return (
        type(value) is int
        and value in (36 * 1024**3, UZU_PROCESS_MEMORY_CEILING_BYTES)
        and value <= UZU_PROCESS_MEMORY_CEILING_BYTES
    )

def uzu_128k_staged_qualification_proof(
    request: dict[str, Any], model: dict[str, Any], resource: dict[str, Any],
    estimate_128k: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project 128K from a fresh matching 64K measured process-group peak."""
    context = request.get("context")
    if context != 131_072 or isinstance(context, bool):
        return {"required": False, "ready": True}
    staged_request = copy.deepcopy(request)
    staged_request["context"] = 65_536
    record = _uzu_qualified_session_record(staged_request, model)
    if record is None:
        return {
            "required": True,
            "ready": False,
            "reason": "missing-64k-receipt",
            "detail": (
                "Qualify the matching 64K Uzu route first. Its fresh measured process-group "
                "peak is required before the 128K model load can be admitted."
            ),
        }
    spec_64k = route_qualification_spec(model, "uzu", 65_536)
    metrics_64k = (
        route_qualification_metrics(record, spec_64k)
        if spec_64k is not None else None
    )
    estimate_64k = launch_memory_estimate(staged_request, model, resource)
    current_estimate = (
        copy.deepcopy(estimate_128k)
        if isinstance(estimate_128k, dict)
        else launch_memory_estimate(request, model, resource)
    )
    peak_64k = metrics_64k.get("peakMemoryBytes") if isinstance(metrics_64k, dict) else None
    working_64k = estimate_64k.get("estimatedWorkingSetBytes")
    working_128k = current_estimate.get("estimatedWorkingSetBytes")
    margin = current_estimate.get("processCeilingAdmissionMarginBytes")
    ceiling = current_estimate.get("processMemoryCeilingBytes")
    if not (
        isinstance(peak_64k, int) and not isinstance(peak_64k, bool) and peak_64k > 0
        and isinstance(working_64k, int) and not isinstance(working_64k, bool)
        and isinstance(working_128k, int) and not isinstance(working_128k, bool)
        and working_64k > 0 and working_128k > working_64k
        and isinstance(margin, int) and not isinstance(margin, bool) and margin >= 0
        and isinstance(ceiling, int) and not isinstance(ceiling, bool)
        and ceiling == UZU_PROCESS_MEMORY_CEILING_BYTES
        and margin == UZU_PROCESS_CEILING_ADMISSION_MARGIN_BYTES
    ):
        return {
            "required": True,
            "ready": False,
            "reason": "invalid-64k-proof",
            "detail": (
                "The matching 64K receipt no longer exposes a complete measured peak and "
                "comparable 64K-to-128K working-set estimate."
            ),
        }
    growth = working_128k - working_64k
    projected_peak = peak_64k + growth
    projected_with_margin = projected_peak + margin
    ready = projected_with_margin < ceiling
    return {
        "required": True,
        "ready": ready,
        "reason": "ready" if ready else "projected-ceiling",
        "detail": (
            "The fresh matching 64K process-group peak plus estimated 64K-to-128K growth "
            f"and the protected 2 GiB live-ceiling margin fit below {ceiling / 1024**3:.0f} GiB."
            if ready else
            "The fresh matching 64K process-group peak plus estimated 64K-to-128K growth "
            f"and the protected 2 GiB margin do not fit below Uzu's {ceiling / 1024**3:.0f} GiB live ceiling."
        ),
        "receiptId": str(record.get("id") or ""),
        "receiptCreatedAt": str(record.get("createdAt") or ""),
        "measured64KProcessGroupPeakBytes": peak_64k,
        "estimated64KWorkingSetBytes": working_64k,
        "estimated128KWorkingSetBytes": working_128k,
        "estimatedWorkingSetGrowthBytes": growth,
        "processCeilingAdmissionMarginBytes": margin,
        "projected128KProcessGroupPeakBytes": projected_peak,
        "projected128KProcessGroupPeakWithMarginBytes": projected_with_margin,
        "processMemoryCeilingBytes": ceiling,
    }

def session_memory_admission(
    payload: dict[str, Any], models: list[dict[str, Any]],
    resource: dict[str, Any], hub: dict[str, Any], operation: dict[str, Any],
    *, allow_unmeasured_mtplx_operator: bool = False,
) -> dict[str, Any]:
    """Return a one-launch admission decision; never allocate a port or create run files."""
    request = validated_launch_profile_request(
        payload, models,
        allow_unmeasured_mtplx_operator=allow_unmeasured_mtplx_operator,
    )
    model = next(item for item in models if item.get("id") == request["modelId"])
    llama_route = request.get("backend") == "llamacpp"
    uzu_route = request.get("backend") == "uzu"
    llama_record: dict[str, Any] | None = None
    llama_metrics: dict[str, Any] | None = None
    if llama_route:
        llama_record, llama_metrics, estimate = _llamacpp_qualified_session_capacity(
            request, model, resource,
        )
    else:
        estimate = launch_memory_estimate(request, model, resource)
    uzu_record = _uzu_qualified_session_record(request, model) if uzu_route else None
    phase = str(hub.get("phase") or "idle")
    operation_active = bool(operation.get("active"))
    qwen4_ple_route = bool(
        request.get("backend") == "omlx" and estimate.get("pleMmap") is True
    )
    memory_guard = str(request.get("options", {}).get("memoryGuard") or "balanced")
    headroom = int(resource.get("headroomBytes") or 0)
    high_memory_route = qwen4_ple_route and (memory_guard == "high" or estimate.get("expertOffload") is True)
    effective_metal_limit = int(resource.get("metalWiredLimitBytes") or 0)
    if estimate.get("expertOffload") and not effective_metal_limit:
        effective_metal_limit = int(resource.get("metalRecommendedWorkingSetBytes") or 0)
    high_hard_watermark = int(
        estimate.get("memoryGuardHardWatermarkBytes")
        or OMLX_QWEN4_HIGH_MEMORY_HARD_BYTES
    )
    high_minimum_headroom = int(
        estimate.get("requiredHeadroomBytes") or SESSION_OS_RESERVE_MIN_BYTES
    )
    total_memory = int(resource.get("totalMemoryBytes") or 0)
    required_metal_limit = int(
        estimate.get("requiredMetalWiredLimitBytes")
        or OMLX_QWEN4_METAL_FLOOR_BYTES
    )
    if phase in {"preflight", "starting", "running", "stopping"} or operation_active:
        decision = "busy"
        requires_acknowledgement = False
        launchable = False
        label = "Another local operation is active"
        detail = str(operation.get("detail") or hub.get("message") or "Stop it before starting another model load.")
    elif request.get("backend") == "freetoken" and model.get("remote") is True:
        decision = "ready"
        requires_acknowledgement = False
        launchable = True
        label = "Connected route is ready"
        detail = "FreeToken already owns the model on its configured server; this launch starts only a private loopback bridge and the selected work surface."
    elif request.get("backend") == "whallm" and model.get("sharedServer") is True:
        decision = "ready"
        requires_acknowledgement = False
        launchable = True
        label = "Whallm route is already loaded"
        detail = "Whallm already owns the model and SSD cache; this launch adds only a private loopback bridge and the selected work surface. The 48 GiB host remains an experimental upstream configuration."
    elif request.get("backend") == "slotstream" and model.get("slotstream"):
        required = int(estimate["requiredHeadroomBytes"])
        launchable = bool(resource.get("memoryAvailable") is True and headroom >= required)
        requires_acknowledgement = False
        decision = "ready" if launchable else "pressure"
        label = "Slotstream is ready to plan" if launchable else "Free memory before loading Slotstream"
        detail = f"The memory estimate needs {required / 1024**3:.1f} GiB of headroom including the macOS reserve. Automatic sizing adapts the expert cache to available memory; the native planner checks the selected context and MTP before loading."
    elif request.get("backend") == "kolibri" and model.get("kolibri"):
        launchable = estimate.get("ready") is True
        requires_acknowledgement = False
        decision = "ready" if launchable else "pressure"
        label = "Kolibri is ready to load" if launchable else "Free memory before loading Kolibri"
        detail = (
            f"The current plan keeps {estimate['residentWeightBytes'] / 1e9:.1f} GB of Q6 weights in memory "
            f"({estimate['residentExpertsPerLayer']}/384 experts per layer), with separate room for {estimate['kvPrecision']} KV, "
            f"the {estimate['prefillSize']}-token prefill chunk and macOS. "
            "Available memory is rechecked before loading."
        )
    elif request.get("backend") == "splash" and model.get("splash"):
        required = int(estimate["requiredHeadroomBytes"])
        launchable = bool(resource.get("memoryAvailable") is True and headroom >= required)
        requires_acknowledgement = False
        decision = "ready" if launchable else "pressure"
        label = "Splash is ready to plan" if launchable else "Free memory before loading Splash"
        detail = (
            f"Splash needs about {required / 1024**3:.1f} GiB of headroom including the macOS reserve: "
            "the packed target, draft and vision weights, its paged KV for the selected context, and a "
            "runtime reserve. The engine re-checks the full context before loading."
        )
    elif request.get("backend") == "whallm" and model.get("nativeWhallm"):
        conflict = whallm_qualification_conflict(timeout=0.35)
        required = int(estimate["requiredHeadroomBytes"])
        launchable = bool(not conflict and resource.get("memoryAvailable") is True and headroom >= required)
        requires_acknowledgement = False
        decision = "ready" if launchable else "pressure"
        label = "Full Qwen is ready to load" if launchable else "Free memory before loading Qwen"
        detail = (
            "A separate Whallm model is active; use its shared route or unload it before starting another copy."
            if conflict else
            f"The owned 16K route needs about {required / 1024**3:.1f} GiB of free headroom including the protected macOS reserve. Its process and MLX memory are capped at 40 GiB."
        )
    elif uzu_route and uzu_record is None:
        decision = "qualification"
        requires_acknowledgement = False
        launchable = False
        label = "Qualify this exact Uzu context once"
        detail = (
            "No fresh successful Uzu qualification matches this runtime, model receipt, "
            "context, bounded test budget, reasoning, packaged sampling, and fixed DFlash + Weaver "
            "route. Run the bounded qualification; it cannot be bypassed by a checkbox."
        )
    elif uzu_route and resource.get("memoryAvailable") is not True:
        decision = "unknown"
        requires_acknowledgement = False
        launchable = False
        label = "Memory headroom unavailable"
        detail = "Uzu is blocked until macOS can report current unified-memory headroom; this route cannot be approved through an acknowledgement."
    elif uzu_route and estimate.get("geometryReady") is not True:
        decision = "unknown"
        requires_acknowledgement = False
        launchable = False
        label = "Uzu KV capacity unavailable"
        detail = "Uzu is blocked because the pinned config no longer exposes the exact attention geometry required for a full-context estimate."
    elif uzu_route and not uzu_estimate_within_process_ceiling(estimate):
        decision = "configuration"
        requires_acknowledgement = False
        launchable = False
        label = "Reduce Uzu context"
        detail = (
            "The selected context's conservative working-set estimate does not leave the "
            f"required {UZU_PROCESS_CEILING_ADMISSION_MARGIN_BYTES / 1024**3:.0f} GiB margin below "
            f"Uzu's {UZU_PROCESS_MEMORY_CEILING_BYTES / 1024**3:.0f} GiB live process ceiling."
        )
    elif uzu_route and int(resource.get("headroomBytes") or 0) < int(estimate["requiredHeadroomBytes"]):
        decision = "pressure"
        requires_acknowledgement = False
        launchable = False
        label = "Free memory before Uzu launch"
        detail = (
            f"This bounded Uzu route needs about {int(estimate['requiredHeadroomBytes']) / 1024**3:.1f} GiB "
            f"including the protected macOS reserve; current headroom is {int(resource.get('headroomBytes') or 0) / 1024**3:.1f} GiB. "
            "Close memory-heavy apps and refresh capacity."
        )
    elif uzu_route:
        decision = "ready"
        requires_acknowledgement = False
        launchable = True
        label = "Bounded Uzu route ready"
        detail = (
            f"Saved {int(request['context']) // 1024}K capacity check reused. "
            f"Current memory and the {UZU_PROCESS_MEMORY_CEILING_BYTES / 1024**3:.0f} GiB live guard pass. "
            "The check proves context capacity; it does not benchmark a full-length response."
        )
    elif llama_route and (llama_record is None or llama_metrics is None):
        decision = "qualification"
        requires_acknowledgement = False
        launchable = False
        label = "Qualify this exact route once"
        detail = (
            "No fresh successful llama.cpp SSD-PLE qualification matches the current model, runtime, "
            "8K context, response limit, reasoning, sampling, and fixed engine settings. Run the bounded "
            "route qualification; a checkbox cannot bypass it."
        )
    elif (
        llama_route
        and int(resource.get("metalWiredLimitBytes") or 0)
        != LLAMACPP_PLE_MEMORY_CEILING_BYTES
    ):
        decision = "system-setting"
        requires_acknowledgement = False
        launchable = False
        label = "Set the exact 44 GiB Metal limit"
        detail = (
            "This qualified route can load only while the Metal wired-memory limit equals exactly "
            "44 GiB (45056 MiB). The launcher never raises it or accepts a higher value."
        )
    elif llama_route and (whallm_conflict := whallm_qualification_conflict(timeout=0.35)):
        decision = "runtime-conflict"
        requires_acknowledgement = False
        launchable = False
        label = LLAMACPP_WHALLM_CONFLICT_LABEL
        detail = str(whallm_conflict["detail"])
    elif llama_route and resource.get("memoryAvailable") is not True:
        decision = "unknown"
        requires_acknowledgement = False
        launchable = False
        label = "Memory headroom unavailable"
        detail = (
            "macOS did not provide current unified-memory headroom, so the measured qualified route "
            "cannot be admitted safely. Refresh capacity and retry."
        )
    elif llama_route and headroom < int(estimate["requiredHeadroomBytes"]):
        decision = "pressure"
        requires_acknowledgement = False
        launchable = False
        label = "Free memory before launch"
        detail = (
            f"This exact qualification measured a {int(estimate['measuredProcessGroupPeakBytes']) / 1024**3:.1f} GiB "
            f"process-group peak and protects another {SESSION_OS_RESERVE_MIN_BYTES / 1024**3:.0f} GiB for macOS. "
            f"Current headroom is {headroom / 1024**3:.1f} GiB; close memory-heavy apps and refresh."
        )
    elif llama_route:
        decision = "ready"
        requires_acknowledgement = False
        launchable = True
        label = "Qualified SSD-PLE route ready"
        detail = (
            f"The fresh exact receipt, {int(estimate['measuredProcessGroupPeakBytes']) / 1024**3:.1f} GiB measured peak, "
            "44 GiB ceiling, current headroom, and Whallm isolation all pass."
        )
    elif qwen4_ple_route and not high_memory_route:
        decision = "configuration"
        requires_acknowledgement = False
        launchable = False
        label = "Choose Qwen high-memory mode"
        detail = (
            "Every verified Qwen PLE mmap route requires the dedicated High memory guard. "
            "Choose High memory in Runtime controls before loading or qualifying this checkpoint."
        )
    elif (
        high_memory_route
        and int(estimate.get("estimatedWorkingSetBytes") or 0) > high_hard_watermark
    ):
        decision = "configuration"
        requires_acknowledgement = False
        launchable = False
        label = "Reduce expert RAM share or context" if estimate.get("expertOffload") else "Reduce Qwen context"
        detail = (
            f"This context needs an estimated {int(estimate.get('estimatedWorkingSetBytes') or 0) / 1024**3:.1f} GiB "
            f"working set, above the actual {high_hard_watermark / 1024**3:.1f} GiB oMLX hard watermark. "
            + ("Reduce the expert RAM share or context before starting." if estimate.get("expertOffload") else
               "Reduce context before starting; approval cannot override the process guard.")
        )
    elif high_memory_route and not estimate.get("geometryReady"):
        decision = "unknown"
        requires_acknowledgement = False
        launchable = False
        label = "KV capacity unavailable"
        detail = (
            "Qwen high-memory mode is blocked because the checkpoint does not expose the exact QSA "
            "geometry needed to prove its full-context KV allocation."
        )
    elif (
        high_memory_route
        and total_memory > 0
        and int(estimate.get("requiredHeadroomBytes") or 0) > total_memory
    ):
        decision = "configuration"
        requires_acknowledgement = False
        launchable = False
        label = "Reduce Qwen memory"
        detail = (
            f"This route projects {int(estimate.get('estimatedWorkingSetBytes') or 0) / 1024**3:.1f} GiB "
            f"for the model session plus a protected {int(estimate.get('osReserveBytes') or 0) / 1024**3:.1f} GiB "
            f"for macOS, which exceeds this Mac's {total_memory / 1024**3:.1f} GiB physical memory. "
            "Reduce context or use a smaller checkpoint; approval cannot bypass physical capacity."
        )
    elif high_memory_route and total_memory <= 0:
        decision = "unknown"
        requires_acknowledgement = False
        launchable = False
        label = "Physical memory unavailable"
        detail = (
            "Qwen high-memory mode is blocked because macOS did not provide the physical-memory "
            "capacity needed to prove the projected session plus protected OS reserve can fit."
        )
    elif high_memory_route and resource.get("memoryAvailable") is not True:
        decision = "unknown"
        requires_acknowledgement = False
        launchable = False
        label = "Memory headroom unavailable"
        detail = (
            "Qwen high-memory mode is blocked because macOS did not provide current unified-memory "
            "headroom. Refresh capacity before starting this exceptional route."
        )
    elif high_memory_route and headroom < high_minimum_headroom:
        decision = "pressure"
        requires_acknowledgement = False
        launchable = False
        label = "Free memory before launch"
        detail = (
            f"This Qwen route requires about {high_minimum_headroom / 1024**3:.1f} GiB of measured headroom "
            f"for the projected model session and protected macOS reserve; only {headroom / 1024**3:.1f} GiB "
            "is available. Close memory-heavy "
            "apps and refresh capacity."
        )
    elif (
        high_memory_route
        and effective_metal_limit < required_metal_limit
    ):
        decision = "system-setting"
        requires_acknowledgement = False
        launchable = False
        label = "Raise the temporary Metal limit"
        detail = (
            f"The selected context needs a temporary {required_metal_limit / 1024**3:.0f} GiB Apple GPU "
            f"wired-memory limit. This is separate from the {int(estimate.get('memoryGuardCeilingBytes') or OMLX_QWEN4_HIGH_MEMORY_CEILING_BYTES) / 1024**3:g} GiB "
            "oMLX process guard; the Metal setting resets at reboot and should return to 0 after qualification."
        )
    elif high_memory_route:
        decision = "ready"
        requires_acknowledgement = False
        launchable = True
        label = "Qwen high-memory route ready"
        detail = (
            "The verified PLE geometry, oMLX hard watermark, measured headroom, and temporary "
            "Metal wired-memory limit all satisfy the dedicated High memory route gate."
        )
    elif resource.get("memoryAvailable") is not True:
        decision = "unknown"
        requires_acknowledgement = True
        launchable = True
        label = "Capacity needs review"
        detail = "macOS unified-memory headroom was unavailable, so the launcher cannot prove this load has enough reserve."
    elif not estimate["geometryReady"]:
        decision = "unknown"
        requires_acknowledgement = True
        launchable = True
        label = "KV capacity needs review"
        detail = "The checkpoint does not expose enough attention geometry for a full-context KV estimate."
    else:
        working_set = int(estimate["estimatedWorkingSetBytes"])
        required = int(estimate["requiredHeadroomBytes"])
        if headroom >= required:
            decision = "ready"
            requires_acknowledgement = False
            launchable = True
            label = "Capacity looks ready"
            detail = "Current headroom covers the conservative full-context estimate and keeps the OS reserve."
        elif headroom >= working_set:
            decision = "review"
            requires_acknowledgement = True
            launchable = True
            label = "OS reserve would be tight"
            detail = "The estimated session fits current headroom, but it would consume part of the protected macOS reserve."
        else:
            decision = "pressure"
            requires_acknowledgement = True
            launchable = True
            label = "Projected memory pressure"
            detail = "The conservative full-context estimate is larger than current unified-memory headroom and may compress or swap heavily."
    headroom_value = resource.get("headroomBytes")
    projected = None if estimate.get("remoteEngine") or estimate.get("sharedEngine") else (
        int(headroom_value) - int(estimate["estimatedWorkingSetBytes"])
        if isinstance(headroom_value, int) and not isinstance(headroom_value, bool) else None
    )
    contract_id = hashlib.sha256(json.dumps(
        {
            "request": request, "estimateVersion": SESSION_MEMORY_ESTIMATE_VERSION,
            "qualificationRecordId": estimate.get("qualificationRecordId"),
            "measuredProcessGroupPeakBytes": estimate.get("measuredProcessGroupPeakBytes"),
        },
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()[:16]
    return {
        "contractId": contract_id,
        "decision": decision,
        "label": label,
        "detail": detail,
        "launchable": launchable,
        "requiresAcknowledgement": requires_acknowledgement,
        "request": request,
        "route": {
            "backend": request["backend"], "backendLabel": BACKEND_LABELS[request["backend"]],
            "client": request["client"], "modelId": request["modelId"],
            "model": str(model.get("name") or request["modelId"]),
            "context": request["context"], "kv": str(request.get("options", {}).get("kv") or "off"),
        },
        "estimate": estimate,
        "projectedHeadroomBytes": projected,
        "privacy": {
            "startsRuntime": False, "allocatesPort": False, "createsRunFiles": False,
            "usesProjectData": False,
        },
    }

def route_qualification_memory_admission(
    request: dict[str, Any], models: list[dict[str, Any]], *,
    resource_snapshot: dict[str, Any] | None = None,
    hub: dict[str, Any] | None = None,
    operation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply the dedicated fail-closed capacity gate for one qualified route.

    This is read-only: it samples current capacity and never changes the Metal
    limit.  Callers running inside Benchmark Lab may pass the current benchmark
    as an inactive operation so the gate evaluates the model load rather than
    blocking on its own worker state.
    """
    current_hub = copy.deepcopy(hub) if isinstance(hub, dict) else MANAGER.hub_snapshot()
    current_operation = (
        copy.deepcopy(operation)
        if isinstance(operation, dict) else active_launcher_operation(current_hub)
    )
    snapshot = (
        copy.deepcopy(resource_snapshot)
        if isinstance(resource_snapshot, dict) else apple_resource_snapshot()
    )
    visible = validated_launch_profile_request(request, models)
    model = next(item for item in models if item.get("id") == visible["modelId"])
    spec = route_qualification_spec(
        model, str(visible.get("backend") or ""), int(visible.get("context") or 0),
    )
    if spec is not None and spec["backend"] == "llamacpp":
        resource = public_session_resource(snapshot)
        phase = str(current_hub.get("phase") or "idle")
        busy = phase in {"preflight", "starting", "running", "stopping"} or bool(
            current_operation.get("active")
        )
        cap = snapshot.get("metalWiredLimitBytes")
        headroom = resource.get("headroomBytes")
        memory_ready = bool(
            resource.get("memoryAvailable") is True
            and isinstance(headroom, int) and not isinstance(headroom, bool)
            and headroom >= SESSION_OS_RESERVE_MIN_BYTES
        )
        if busy:
            decision, label = "busy", "Another local operation is active"
            detail = str(current_operation.get("detail") or current_hub.get("message") or "Stop it before qualification.")
        elif cap != LLAMACPP_PLE_MEMORY_CEILING_BYTES:
            decision, label = "system-setting", "Set the exact 44 GiB Metal limit"
            detail = "The audited SSD-PLE route requires the wired-memory limit to equal exactly 44 GiB throughout qualification."
        else:
            whallm_conflict = whallm_qualification_conflict()
            if whallm_conflict:
                decision, label = "runtime-conflict", LLAMACPP_WHALLM_CONFLICT_LABEL
                detail = str(whallm_conflict["detail"])
            elif not memory_ready:
                decision, label = "pressure", "Free memory before qualification"
                detail = "Current macOS headroom must preserve at least 4 GiB before the receipt-bound SSD-PLE load."
            else:
                decision, label = "ready", "llama.cpp SSD-PLE route ready"
                detail = "The exact receipt, 8K route, 44 GiB cap, and current macOS reserve passed the pre-load gate."
        return {
            "contractId": hashlib.sha256(json.dumps(
                {"request": visible, "qualification": spec["id"]},
                sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")).hexdigest()[:16],
            "decision": decision, "label": label, "detail": detail,
            "launchable": decision == "ready", "requiresAcknowledgement": False,
            "request": visible,
            "route": {
                "backend": "llamacpp", "backendLabel": BACKEND_LABELS["llamacpp"],
                "client": visible["client"], "modelId": visible["modelId"],
                "model": str(model.get("name") or visible["modelId"]),
                "context": LLAMACPP_PLE_CONTEXT, "kv": "off",
            },
            "estimate": {
                "basis": "Receipt-bound lazy mmap route; qualification measures Darwin physical footprint.",
                "memoryCeilingBytes": LLAMACPP_PLE_MEMORY_CEILING_BYTES,
                "osReserveBytes": SESSION_OS_RESERVE_MIN_BYTES,
            },
            "projectedHeadroomBytes": None,
            "privacy": {
                "startsRuntime": False, "allocatesPort": False,
                "createsRunFiles": False, "usesProjectData": False,
                "changesExternalState": False,
            },
        }
    if spec is not None and spec["backend"] == "uzu":
        resource = public_session_resource(snapshot)
        phase = str(current_hub.get("phase") or "idle")
        busy = phase in {"preflight", "starting", "running", "stopping"} or bool(
            current_operation.get("active")
        )
        estimate = launch_memory_estimate(visible, model, resource)
        headroom = resource.get("headroomBytes")
        required = estimate.get("requiredHeadroomBytes")
        ceiling_ready = uzu_estimate_within_process_ceiling(estimate)
        staged_proof = uzu_128k_staged_qualification_proof(
            visible, model, resource, estimate,
        )
        memory_ready = bool(
            resource.get("memoryAvailable") is True
            and estimate.get("geometryReady") is True
            and ceiling_ready
            and staged_proof.get("ready") is True
            and isinstance(headroom, int) and not isinstance(headroom, bool)
            and isinstance(required, int) and not isinstance(required, bool)
            and headroom >= required
        )
        if busy:
            decision, label = "busy", "Another local operation is active"
            detail = str(
                current_operation.get("detail")
                or current_hub.get("message")
                or "Stop it before qualification."
            )
        elif estimate.get("geometryReady") is not True:
            decision, label = "unknown", "Uzu KV capacity unavailable"
            detail = (
                "The pinned config no longer exposes the exact attention geometry required "
                "for a full-context estimate."
            )
        elif not ceiling_ready:
            decision, label = "configuration", "Reduce Uzu context"
            detail = (
                "The selected context's conservative working-set estimate does not leave the "
                f"required {UZU_PROCESS_CEILING_ADMISSION_MARGIN_BYTES / 1024**3:.0f} GiB margin below "
                f"Uzu's {UZU_PROCESS_MEMORY_CEILING_BYTES / 1024**3:.0f} GiB live process ceiling."
            )
        elif staged_proof.get("ready") is not True:
            staged_reason = str(staged_proof.get("reason") or "")
            decision = (
                "configuration" if staged_reason == "projected-ceiling" else "qualification"
            )
            label = (
                "Qualify Uzu at 64K first"
                if staged_reason == "missing-64k-receipt" else
                "128K projection exceeds Uzu ceiling"
                if staged_reason == "projected-ceiling" else
                "Refresh the 64K Uzu qualification"
            )
            detail = str(
                staged_proof.get("detail")
                or "A fresh matching 64K measurement is required before 128K qualification."
            )
        elif not memory_ready:
            decision, label = "pressure", "Free memory before Uzu qualification"
            detail = (
                "The exact context must fit the pinned target, bundled draft, BF16 cache, "
                "runtime workspace, and protected macOS reserve before Uzu can load."
            )
        else:
            decision, label = "ready", f"{spec['routeLabel']} ready to qualify"
            detail = (
                f"The pinned receipts, exact {int(visible['context']):,}-token context, "
                f"current headroom, and {UZU_PROCESS_MEMORY_CEILING_BYTES / 1024**3:.0f} GiB "
                "live process-group ceiling passed the pre-load gate."
            )
        return {
            "contractId": hashlib.sha256(json.dumps(
                {"request": visible, "qualification": spec["id"]},
                sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")).hexdigest()[:16],
            "decision": decision, "label": label, "detail": detail,
            "launchable": decision == "ready", "requiresAcknowledgement": False,
            "request": visible,
            "route": {
                "backend": "uzu", "backendLabel": BACKEND_LABELS["uzu"],
                "client": "chat", "modelId": visible["modelId"],
                "model": str(model.get("name") or visible["modelId"]),
                "context": int(visible["context"]), "kv": "off",
            },
            "estimate": estimate,
            "stagedQualification": staged_proof,
            "projectedHeadroomBytes": (
                int(headroom) - int(required)
                if isinstance(headroom, int) and isinstance(required, int) else None
            ),
            "privacy": {
                "startsRuntime": False, "allocatesPort": False,
                "createsRunFiles": False, "usesProjectData": False,
                "changesExternalState": False,
            },
        }
    return session_memory_admission(
        request, models, public_session_resource(snapshot),
        current_hub, current_operation,
    )

def strict_model_load_admission_ready(admission: dict[str, Any]) -> bool:
    """Return whether an automated model load has an unqualified ready decision."""
    return bool(
        admission.get("launchable") is True
        and admission.get("requiresAcknowledgement") is False
        and admission.get("decision") == "ready"
    )

def route_qualification_admission_ready(admission: dict[str, Any]) -> bool:
    """Require the fail-closed, no-approval outcome before a route qualification load."""
    return strict_model_load_admission_ready(admission)

def require_live_model_load_admission(
    request: dict[str, Any], models: list[dict[str, Any]], *, purpose: str,
    approval_payload: dict[str, Any] | None = None,
    resource_snapshot: dict[str, Any] | None = None,
    hub: dict[str, Any] | None = None,
    operation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Re-sample capacity immediately before one caller-owned model load.

    Automated measurements never accept the normal interactive memory-review
    acknowledgement.  Session Sets retain that acknowledgement contract, while
    receipt-bound qualification continues to use its specialized Uzu/llama.cpp
    rules.  The current caller's own operation is ignored, but a different
    active launcher operation still blocks the load.
    """
    if purpose not in MODEL_LOAD_OWNER_KINDS:
        raise ValueError("Unknown model-load admission purpose.")
    current_hub = copy.deepcopy(hub) if isinstance(hub, dict) else MANAGER.hub_snapshot()
    if isinstance(operation, dict):
        current_operation = copy.deepcopy(operation)
    else:
        current_operation = active_launcher_operation(current_hub)
        owner_kind = MODEL_LOAD_OWNER_KINDS[purpose]
        if (
            current_operation.get("active") is True
            and current_operation.get("kind") == owner_kind
        ):
            current_operation = {
                "active": False, "kind": owner_kind, "phase": "starting",
                "detail": f"This {MODEL_LOAD_PURPOSE_LABELS[purpose]} owns the next model load.",
            }
    snapshot = (
        copy.deepcopy(resource_snapshot)
        if isinstance(resource_snapshot, dict) else apple_resource_snapshot()
    )
    if purpose == "route-qualification":
        admission = route_qualification_memory_admission(
            request, models, resource_snapshot=snapshot,
            hub=current_hub, operation=current_operation,
        )
    else:
        admission = session_memory_admission(
            request, models, public_session_resource(snapshot),
            current_hub, current_operation,
            allow_unmeasured_mtplx_operator=purpose == "benchmark",
        )
    if purpose in AUTOMATED_MODEL_LOAD_PURPOSES:
        if not strict_model_load_admission_ready(admission):
            raise RuntimeError(
                f"Capacity changed immediately before the {MODEL_LOAD_PURPOSE_LABELS[purpose]} model load. "
                f"{admission.get('label') or 'The route is blocked'}: "
                f"{admission.get('detail') or 'refresh capacity and try again.'} "
                "Automated measurements require a ready decision and cannot use a memory acknowledgement."
            )
    else:
        require_session_launch_admission(
            approval_payload if isinstance(approval_payload, dict) else request,
            admission,
        )
    return admission

def require_session_launch_admission(
    payload: dict[str, Any], admission: dict[str, Any],
) -> dict[str, Any]:
    """Fail closed unless the current one-launch admission may proceed."""
    if not isinstance(admission, dict) or admission.get("launchable") is not True:
        detail = admission.get("detail") if isinstance(admission, dict) else None
        raise ValueError(str(detail or "Another launcher operation is active."))
    if admission.get("requiresAcknowledgement") is True:
        expected = str(admission.get("contractId") or "")
        supplied = str(payload.get("memoryAcknowledgement") or "")
        if not expected or not secrets.compare_digest(supplied, expected):
            raise ValueError(
                f"{admission.get('label') or 'Capacity review required'}: "
                f"{admission.get('detail') or 'Review the current memory estimate.'} "
                "Open Sessions, review the capacity estimate, and approve this exact launch once."
            )
    return admission
