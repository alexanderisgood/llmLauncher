"""Explicit live-port wiring for isolated catalog and artifact fixtures."""
import model_catalog as domain


def make_catalog(owner, state=None):
    def descriptor(value):
        return domain.CatalogDescriptor(value.id,value.label,value.kind,value.binary_key,value.protocol,value.built_in)
    policy = domain.CatalogPolicy(
        engines={key:descriptor(value) for key,value in owner.ENGINE_ADAPTERS.items()},
        surfaces={key:descriptor(value) for key,value in owner.CLIENT_ADAPTERS.items()},
        backend_labels=owner.BACKEND_LABELS,
        general=domain.GeneralCatalogPolicy(
            default_context=owner.DEFAULT_CONTEXT,
            max_json=owner.MAX_JSON,
            model_library_schema_version=owner.MODEL_LIBRARY_SCHEMA_VERSION,
            model_acquisition_schema_version=owner.MODEL_ACQUISITION_SCHEMA_VERSION,
            model_acquisition_marker=owner.MODEL_ACQUISITION_MARKER,
            route_evidence_schema_version=owner.ROUTE_EVIDENCE_SCHEMA_VERSION,
            omlx_qwen4_qsa_allocation_step_tokens=owner.OMLX_QWEN4_QSA_ALLOCATION_STEP_TOKENS,
        ),
        ssd=domain.SsdCatalogPolicy(
            ssd_artifact_backends=owner.SSD_ARTIFACT_BACKENDS,
            ssd_streaming_backends=owner.SSD_STREAMING_BACKENDS,
            ssd_streaming_contract_version=owner.SSD_STREAMING_CONTRACT_VERSION,
            ssd_streaming_min_weight_ratio=owner.SSD_STREAMING_MIN_WEIGHT_RATIO,
            mference_context_windows=owner.MFERENCE_CONTEXT_WINDOWS,
            mference_known_flags=owner.MFERENCE_KNOWN_FLAGS,
            mference_streaming_arch_signatures=owner.MFERENCE_STREAMING_ARCH_SIGNATURES,
        ),
        dflash=domain.DflashCatalogPolicy(
            dflash2_draft_repo=owner.DFLASH2_DRAFT_REPO,
            dflash2_draft_size_label=owner.DFLASH2_DRAFT_SIZE_LABEL,
            dflash2_draft_url=owner.DFLASH2_DRAFT_URL,
            dflash2_minimum_runtime=owner.DFLASH2_MINIMUM_RUNTIME,
            dflash2_recommended_runtime=owner.DFLASH2_RECOMMENDED_RUNTIME,
            dflash2_release_url=owner.DFLASH2_RELEASE_URL,
            dflash2_target_geometry=owner.DFLASH2_TARGET_GEOMETRY,
        ),
        ane=domain.AneCatalogPolicy(
            ane_cpu_tuner_reserve_bytes=owner.ANE_CPU_TUNER_RESERVE_BYTES,
            ane_fp16_clone_source_url=owner.ANE_FP16_CLONE_SOURCE_URL,
            ane_tuner_minimum_runtime=owner.ANE_TUNER_MINIMUM_RUNTIME,
            ane_tuner_minimum_speedup_percent=owner.ANE_TUNER_MINIMUM_SPEEDUP_PERCENT,
            ane_tuner_release_url=owner.ANE_TUNER_RELEASE_URL,
            ane_tuner_repeats=owner.ANE_TUNER_REPEATS,
            ane_tuner_reserve_bytes=owner.ANE_TUNER_RESERVE_BYTES,
            ane_tuner_sequence_length=owner.ANE_TUNER_SEQUENCE_LENGTH,
        ),
        atomic=domain.AtomicCatalogPolicy(
            atomic_presentation_snapshot_max_bytes=owner.ATOMIC_PRESENTATION_SNAPSHOT_MAX_BYTES,
            atomic_presentation_snapshot_schema_version=owner.ATOMIC_PRESENTATION_SNAPSHOT_SCHEMA_VERSION,
            llamacpp_atomic_file_manifest=owner.LLAMACPP_ATOMIC_FILE_MANIFEST,
            llamacpp_atomic_repo=owner.LLAMACPP_ATOMIC_REPO,
            llamacpp_atomic_revision=owner.LLAMACPP_ATOMIC_REVISION,
            llamacpp_atomic_shards=owner.LLAMACPP_ATOMIC_SHARDS,
            llamacpp_atomic_total_bytes=owner.LLAMACPP_ATOMIC_TOTAL_BYTES,
            llamacpp_atomic_variant=owner.LLAMACPP_ATOMIC_VARIANT,
            llamacpp_atomic_variant_id=owner.LLAMACPP_ATOMIC_VARIANT_ID,
            llamacpp_ple_context=owner.LLAMACPP_PLE_CONTEXT,
            llamacpp_ple_memory_ceiling_bytes=owner.LLAMACPP_PLE_MEMORY_CEILING_BYTES,
        ),
        lmstudio=domain.LmstudioCatalogPolicy(
            lmstudio_assistant_drafter_families=owner.LMSTUDIO_ASSISTANT_DRAFTER_FAMILIES,
            lmstudio_mtp_min_continue_probability_default=owner.LMSTUDIO_MTP_MIN_CONTINUE_PROBABILITY_DEFAULT,
            lmstudio_mtp_min_tokens_default=owner.LMSTUDIO_MTP_MIN_TOKENS_DEFAULT,
            lmstudio_assistant_drafter_minimum_app=owner.LMSTUDIO_ASSISTANT_DRAFTER_MINIMUM_APP,
            lmstudio_assistant_drafter_minimum_llama_pack=owner.LMSTUDIO_ASSISTANT_DRAFTER_MINIMUM_LLAMA_PACK,
            lmstudio_assistant_drafter_release_url=owner.LMSTUDIO_ASSISTANT_DRAFTER_RELEASE_URL,
        ),
        mtplx=domain.MtplxCatalogPolicy(
            mtplx_long_context_2111_contract_version=owner.MTPLX_LONG_CONTEXT_2111_CONTRACT_VERSION,
            mtplx_long_context_2111_route=owner.MTPLX_LONG_CONTEXT_2111_ROUTE,
            mtplx_long_context_baseline_env=owner.MTPLX_LONG_CONTEXT_BASELINE_ENV,
            mtplx_long_context_candidate_env=owner.MTPLX_LONG_CONTEXT_CANDIDATE_ENV,
            mtplx_long_context_dense_geometry=owner.MTPLX_LONG_CONTEXT_DENSE_GEOMETRY,
            mtplx_long_context_minimum=owner.MTPLX_LONG_CONTEXT_MINIMUM,
        ),
        freetoken=domain.FreetokenCatalogPolicy(
            freetoken_native_api_version=owner.FREETOKEN_NATIVE_API_VERSION,
            freetoken_native_inspection_max_response=owner.FREETOKEN_NATIVE_INSPECTION_MAX_RESPONSE,
            freetoken_native_qualification_schema_version=owner.FREETOKEN_NATIVE_QUALIFICATION_SCHEMA_VERSION,
            freetoken_native_real_checkpoint_test_kind=owner.FREETOKEN_NATIVE_REAL_CHECKPOINT_TEST_KIND,
            freetoken_native_schema_name=owner.FREETOKEN_NATIVE_SCHEMA_NAME,
            freetoken_native_schema_version=owner.FREETOKEN_NATIVE_SCHEMA_VERSION,
            freetoken_native_synthetic_coverage=owner.FREETOKEN_NATIVE_SYNTHETIC_COVERAGE,
            freetoken_native_synthetic_evidence_id=owner.FREETOKEN_NATIVE_SYNTHETIC_EVIDENCE_ID,
        ),
        uzu=domain.UzuCatalogPolicy(
            session_os_reserve_fraction=owner.SESSION_OS_RESERVE_FRACTION,
            session_os_reserve_min_bytes=owner.SESSION_OS_RESERVE_MIN_BYTES,
            uzu_model_commit=owner.UZU_MODEL_COMMIT,
            uzu_model_file_manifest=owner.UZU_MODEL_FILE_MANIFEST,
            uzu_model_file_sha256=owner.UZU_MODEL_FILE_SHA256,
            uzu_model_manifest_max_bytes=owner.UZU_MODEL_MANIFEST_MAX_BYTES,
            uzu_model_manifest_max_files=owner.UZU_MODEL_MANIFEST_MAX_FILES,
            uzu_model_registry_id=owner.UZU_MODEL_REGISTRY_ID,
            uzu_model_registry_max_bytes=owner.UZU_MODEL_REGISTRY_MAX_BYTES,
            uzu_model_registry_max_entries=owner.UZU_MODEL_REGISTRY_MAX_ENTRIES,
            uzu_model_registry_operational_contract=owner.UZU_MODEL_REGISTRY_OPERATIONAL_CONTRACT,
            uzu_model_repository=owner.UZU_MODEL_REPOSITORY,
            uzu_model_toolchain_version=owner.UZU_MODEL_TOOLCHAIN_VERSION,
            uzu_safe_context_windows=owner.UZU_SAFE_CONTEXT_WINDOWS,
            uzu_sandbox_profile_sha256=owner.UZU_SANDBOX_PROFILE_SHA256,
        ),
        whallm=domain.WhallmCatalogPolicy(
            whallm_context_windows=owner.WHALLM_CONTEXT_WINDOWS,
            whallm_model_bytes=owner.WHALLM_MODEL_BYTES,
            whallm_model_id=owner.WHALLM_MODEL_ID,
            whallm_support_floor_bytes=owner.WHALLM_SUPPORT_FLOOR_BYTES,
        ),
    )
    paths=domain.CatalogPaths(state_directory=lambda:owner.STATE_DIR,
        acquisition_roots=lambda:owner.model_acquisition_roots(),
        uzu_cache_root=lambda:owner.UZU_MODEL_CACHE_ROOT,
        uzu_registry_path=lambda:owner.UZU_MODEL_REGISTRY_PATH,
        uzu_resolved_models_path=lambda:owner.UZU_RESOLVED_MODELS_PATH)
    values=domain.CatalogValues(
        deep_get=lambda *a,**k:owner.deep_get(*a,**k),
        safe_int=lambda *a,**k:owner.safe_int(*a,**k),
        slug=lambda *a,**k:owner.slug(*a,**k),
        display_size=lambda *a,**k:owner.display_size(*a,**k),
        qwen_ple_config=lambda *a,**k:owner.is_qwen4_exp_config(*a,**k),
        semantic_version_key=lambda *a,**k:owner.semantic_version_key(*a,**k),
    )
    runtime=domain.CatalogRuntimes(
        selected_binary=lambda key:owner.BINARIES.get(key),
        command_version=lambda *a,**k:owner.command_version(*a,**k),
        lmstudio_runtime_packs=lambda *a,**k:owner.lmstudio_runtime_packs(*a,**k),
        app_status=lambda *a,**k:owner.runtime_app_status(*a,**k),
        plist_version=lambda *a,**k:owner.plist_version(*a,**k),
        lmstudio_mtp_load_supported=lambda *a,**k:owner.lmstudio_mtp_load_supported(*a,**k),
        lmstudio_assistant_drafter_load_supported=lambda *a,**k:owner.lmstudio_assistant_drafter_load_supported(*a,**k),
        lmstudio_backend_preference=lambda *a,**k:owner.lmstudio_backend_preference(*a,**k),
        lmstudio_runtime_identity=lambda *a,**k:owner.lmstudio_runtime_identity(*a,**k),
        omlx_supports_dflash2=lambda *a,**k:owner.omlx_supports_dflash2(*a,**k),
        omlx_recommended_dflash_runtime=lambda *a,**k:owner.omlx_has_recommended_dflash2_runtime(*a,**k),
        omlx_version_at_least=lambda *a,**k:owner.omlx_version_at_least(*a,**k),
        omlx_kernel_status=lambda *a,**k:owner.omlx_qwen_kernel_status(*a,**k),
        llamacpp_runtime_contract=lambda *a,**k:owner.llamacpp_runtime_contract(*a,**k),
        uzu_runtime_contract=lambda *a,**k:owner.uzu_runtime_contract(*a,**k),
        uzu_listener_protection_ready=lambda *a,**k:owner.uzu_listener_protection_ready(*a,**k),
        native_freetoken_host_supported=lambda *a,**k:owner.native_freetoken_host_supported(*a,**k),
        physical_memory_bytes=lambda *a,**k:owner.physical_memory_bytes(*a,**k),
    )
    artifacts=domain.CatalogArtifacts(
        cached_regular_file_sha256_matches=lambda *a,**k:owner._cached_regular_file_sha256_matches(*a,**k),
        safetensors_inventory=lambda *a,**k:owner.safetensors_inventory(*a,**k),
        qwen_ple_profile=lambda *a,**k:owner.qwen4_ple_profile(*a,**k),
        qwen_expert_offload_profile=lambda *a,**k:owner.qwen4_expert_offload_profile(*a,**k),
        atomic_shard_relative=lambda *a,**k:owner.llamacpp_atomic_shard_relative(*a,**k),
    )
    evidence=domain.CatalogEvidence(
        load_benchmarks=lambda *a,**k:owner.load_benchmark_records(*a,**k),
        load_ane_records=lambda *a,**k:owner.load_ane_tuning_records(*a,**k),
        hardware_fingerprint=lambda *a,**k:owner.hardware_fingerprint(*a,**k),
        matching_benchmarks=lambda *a,**k:owner.matching_benchmark_records(*a,**k),
        latest_by_identity=lambda *a,**k:owner.latest_benchmark_records_by_identity(*a,**k),
        matching_ane_record=lambda *a,**k:owner.matching_ane_tuning_record(*a,**k),
        verified_ane_record=lambda *a,**k:owner.verified_ane_tuning_record(*a,**k),
        route_performance=lambda *a,**k:owner.route_performance_evidence(*a,**k),
        public_mode_label=lambda *a,**k:owner.benchmark_public_mode_label(*a,**k),
    )
    surfaces=domain.CatalogSurfaces(
        resolved_support=lambda *a,**k:owner.resolved_client_support(*a,**k),
    )
    connections=domain.CatalogConnections(
        freetoken_connection=lambda *a,**k:owner.load_freetoken_connection(*a,**k),
        whallm_endpoint=lambda *a,**k:owner.probe_whallm_endpoint(*a,**k),
    )
    io=domain.CatalogIO(
        read_json=lambda *a,**k:owner.read_json(*a,**k),
        atomic_json=lambda *a,**k:owner.atomic_json(*a,**k),
        run_catalog_cli=lambda *a,**k:owner.subprocess.run(*a,**k),
        token_hex=lambda *a,**k:owner.secrets.token_hex(*a,**k),
    )
    return domain.ModelCatalog(policy, state if state is not None else domain.CatalogState(), paths, values, runtime, artifacts, evidence, surfaces, connections, io)
