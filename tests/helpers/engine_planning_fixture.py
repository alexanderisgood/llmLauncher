"""Explicit production-equivalent ports for generated engine plan fixtures."""
from pathlib import Path

import engine_planning as domain


def make_planner(owner):
    policy = domain.EnginePolicy(
        launch=owner._launch_contract_policy(), thinking_budgets=owner.THINKING_BUDGETS,
        omlx=domain.OmlxPolicy(
            expert_offload_version=owner.OMLX_EXPERT_OFFLOAD_VERSION,
            high_memory_ceiling_gib=owner.OMLX_QWEN4_HIGH_MEMORY_CEILING_GIB,
            high_memory_soft_threshold=owner.OMLX_QWEN4_HIGH_MEMORY_SOFT_THRESHOLD,
            high_memory_hard_threshold=owner.OMLX_QWEN4_HIGH_MEMORY_HARD_THRESHOLD,
            ane_sequence_length=owner.ANE_TUNER_SEQUENCE_LENGTH,
            recommended_dflash_runtime=owner.DFLASH2_RECOMMENDED_RUNTIME),
        mtplx=domain.MtplxPolicy(
            dense_geometry=owner.MTPLX_LONG_CONTEXT_DENSE_GEOMETRY,
            candidate_route=owner.MTPLX_LONG_CONTEXT_2111_ROUTE,
            minimum_operator_context=owner.MTPLX_LONG_CONTEXT_MINIMUM,
            compiled_verify_fence=owner.MTPLX_COMPILED_VERIFY_PROFILE_FENCE,
            baseline_environment=owner.MTPLX_LONG_CONTEXT_BASELINE_ENV,
            candidate_environment=owner.MTPLX_LONG_CONTEXT_CANDIDATE_ENV),
        uzu=domain.UzuPolicy(
            model_id=owner.UZU_MODEL_REGISTRY_ID, model_commit=owner.UZU_MODEL_COMMIT,
            toolchain_version=owner.UZU_MODEL_TOOLCHAIN_VERSION,
            boundary_contract_id=owner.UZU_NATIVE_BOUNDARY_CONTRACT_ID,
            context_windows=owner.UZU_SAFE_CONTEXT_WINDOWS,
            process_memory_ceiling_bytes=owner.UZU_PROCESS_MEMORY_CEILING_BYTES,
            sandbox_executable=owner.UZU_SANDBOX_EXECUTABLE,
            network_sandbox_profile=owner.UZU_NETWORK_SANDBOX_PROFILE,
            api_key_filename=owner.UZU_API_KEY_FILE_NAME,
            private_bearer_filenames=owner.UZU_PRIVATE_BEARER_FILE_NAMES),
        llamacpp=domain.LlamaCppPolicy(
            context=owner.LLAMACPP_PLE_CONTEXT,
            memory_ceiling_bytes=owner.LLAMACPP_PLE_MEMORY_CEILING_BYTES,
            memory_ceiling_gib=owner.LLAMACPP_PLE_MEMORY_CEILING_GIB,
            whallm_conflict_label=owner.LLAMACPP_WHALLM_CONFLICT_LABEL,
            runtime_directory=owner.LLAMACPP_RUNTIME_DIR, server_path=owner.LLAMACPP_SERVER_PATH,
            runtime_file_manifest=owner.LLAMACPP_RUNTIME_FILE_MANIFEST,
            model_file_manifest=owner.LLAMACPP_ATOMIC_FILE_MANIFEST,
            acquisition_marker=owner.MODEL_ACQUISITION_MARKER,
            reasoning_budget_message=owner.LLAMACPP_QWEN_REASONING_BUDGET_MESSAGE,
            api_key_filename=owner.LLAMACPP_API_KEY_FILE_NAME,
            private_bearer_filenames=owner.LLAMACPP_PRIVATE_BEARER_FILE_NAMES),
        whallm=domain.WhallmPolicy(model_id=owner.WHALLM_MODEL_ID,
            endpoint=owner.WHALLM_ENDPOINT, context_windows=owner.WHALLM_CONTEXT_WINDOWS))
    paths = domain.PlanningPaths(lambda:owner.APP_DIR, lambda:owner.STATE_DIR, lambda:owner.FREETOKEN_BRIDGE)
    runtime = domain.RuntimeServices(
        selected_binary=lambda key:owner.BINARIES.get(key), required_binary=lambda key:owner.BINARIES[key],
        command_version=lambda *a,**k:owner.command_version(*a,**k),
        omlx_plan_runtime_version=lambda *a,**k:owner.omlx_plan_runtime_version(*a,**k),
        omlx_runtime_python=lambda *a,**k:owner.omlx_runtime_python(*a,**k),
        omlx_qwen_kernel_status=lambda *a,**k:owner.omlx_qwen_kernel_status(*a,**k),
        semantic_version_key=owner.semantic_version_key, exact_omlx_version=owner._exact_omlx_version,
        recommended_dflash_runtime=owner.omlx_has_recommended_dflash2_runtime, safe_int=owner.safe_int)
    models = domain.ModelServices(
        artifact_fingerprint=lambda *a,**k:owner.model_artifact_fingerprint(*a,**k),
        weight_completeness=lambda *a,**k:owner.weight_completeness(*a,**k),
        normalized_model_type=owner._normalized_model_type, qwen_ple_record=owner.is_qwen4_exp_record,
        strong_path_identity=lambda *a,**k:owner._llamacpp_strong_path_identity(*a,**k),
        preserved_thinking_template=lambda *a,**k:owner.preserved_qwopus_template(*a,**k))
    memory = domain.MemoryServices(
        physical_memory_bytes=lambda:owner.physical_memory_bytes(),
        wired_limit_bytes=lambda:owner.apple_iogpu_wired_limit_bytes(),
        resource_snapshot=lambda:owner.apple_resource_snapshot(),
        public_resource=lambda *a,**k:owner.public_session_resource(*a,**k),
        launch_estimate=lambda *a,**k:owner.launch_memory_estimate(*a,**k),
        ane_memory_readiness=lambda *a,**k:owner.ane_memory_readiness(*a,**k))
    omlx = domain.OmlxChecks(
        dflash_capability_valid=lambda *a,**k:owner.dflash2_capability_valid(*a,**k),
        ane_record_valid=lambda *a,**k:owner.verified_ane_tuning_record(*a,**k),
        cpu_sharing_profile=lambda *a,**k:owner.ane_cpu_sharing_profile(*a,**k),
        expert_offload_options=lambda *a,**k:owner.omlx_expert_offload_options(*a,**k),
        ple_profile=lambda *a,**k:owner.qwen4_ple_profile(*a,**k),
        expert_offload_profile=lambda *a,**k:owner.qwen4_expert_offload_profile(*a,**k))
    mtplx = domain.MtplxChecks(
        operator_route=lambda *a,**k:owner.validated_mtplx_operator_route(*a,**k),
        long_context_contract=lambda *a,**k:owner.mtplx_long_context_2111_contract(*a,**k),
        capability_matches=lambda *a,**k:owner._mtplx_long_context_capability_matches(*a,**k))
    uzu = domain.UzuChecks(
        runtime_contract=lambda *a,**k:owner.uzu_runtime_contract(*a,**k),
        listener_protection_ready=lambda *a,**k:owner.uzu_listener_protection_ready(*a,**k),
        model_cache_contract=lambda:owner._uzu_model_cache_contract(),
        ensure_offline_catalog=lambda *a,**k:owner._ensure_uzu_offline_catalog(*a,**k),
        validated_offline_catalog=lambda *a,**k:owner._validated_uzu_offline_catalog(*a,**k),
        open_executable=lambda *a,**k:owner._open_uzu_runtime_executable(*a,**k),
        confirm_open_executable=lambda *a,**k:owner._confirm_open_uzu_executable(*a,**k))
    llamacpp = domain.LlamaCppChecks(
        runtime_contract=lambda *a,**k:owner.llamacpp_runtime_contract(*a,**k),
        artifact_contract=lambda *a,**k:owner.llamacpp_atomic_artifact_contract(*a,**k),
        qualified_session_capacity=lambda *a,**k:owner._llamacpp_qualified_session_capacity(*a,**k))
    freetoken = domain.FreeTokenChecks(
        connection=lambda:owner.load_freetoken_connection(),
        validate_native_contract=lambda *a,**k:owner.validate_native_freetoken_contract(*a,**k),
        inspect_native_model=lambda *a,**k:owner.inspect_native_freetoken_model(*a,**k))
    whallm = domain.WhallmChecks(
        qualification_conflict=lambda:owner.whallm_qualification_conflict(),
        probe_endpoint=lambda:owner.probe_whallm_endpoint())
    io = domain.PlanningIO(read_json=lambda *a,**k:owner.read_json(*a,**k),
        atomic_json=lambda *a,**k:owner.atomic_json(*a,**k),
        token_urlsafe=lambda *a,**k:owner.secrets.token_urlsafe(*a,**k),
        token_hex=lambda *a,**k:owner.secrets.token_hex(*a,**k), slug=owner.slug)
    return domain.EnginePlanner(policy, paths, runtime, models, memory, omlx, mtplx, uzu, llamacpp, freetoken, whallm, io)
