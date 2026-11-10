"""Explicit live adapters for isolated runtime catalog fixtures."""
from datetime import datetime, timezone
from pathlib import Path
import time
import uuid
import runtime_catalog


def make_runtime_catalog(root):
    return runtime_catalog.RuntimeCatalog(
        policy=runtime_catalog.RuntimePolicy(
            discovery=runtime_catalog.DiscoveryPolicy(
                runtime_candidate_specs=root.RUNTIME_CANDIDATE_SPECS,
                runtime_app_specs=root.RUNTIME_APP_SPECS,
                runtime_preferences_version=root.RUNTIME_PREFERENCES_VERSION,
                llamacpp_runtime_tag=root.LLAMACPP_RUNTIME_TAG,
            ),
            releases=runtime_catalog.ReleasesPolicy(
                runtime_release_catalog=root.RUNTIME_RELEASE_CATALOG,
                runtime_release_catalog_audited_at=root.RUNTIME_RELEASE_CATALOG_AUDITED_AT,
                runtime_release_catalog_version=root.RUNTIME_RELEASE_CATALOG_VERSION,
                runtime_update_catalog=root.RUNTIME_UPDATE_CATALOG,
                runtime_update_archive=root.RUNTIME_UPDATE_ARCHIVE,
                runtime_update_catalog_audited_at=root.RUNTIME_UPDATE_CATALOG_AUDITED_AT,
            ),
            update=runtime_catalog.UpdatePolicy(
                runtime_update_manifest=root.RUNTIME_UPDATE_MANIFEST,
                runtime_update_schema_version=root.RUNTIME_UPDATE_SCHEMA_VERSION,
                runtime_update_estimated_install_bytes=root.RUNTIME_UPDATE_ESTIMATED_INSTALL_BYTES,
                runtime_update_disk_reserve_bytes=root.RUNTIME_UPDATE_DISK_RESERVE_BYTES,
            ),
            features=runtime_catalog.FeaturesPolicy(
                dflash2_minimum_runtime=root.DFLASH2_MINIMUM_RUNTIME,
                dflash2_recommended_runtime=root.DFLASH2_RECOMMENDED_RUNTIME,
                ane_tuner_minimum_runtime=root.ANE_TUNER_MINIMUM_RUNTIME,
                mtplx_agent_recommended_runtime=root.MTPLX_AGENT_RECOMMENDED_RUNTIME,
            ),
            links=runtime_catalog.LinksPolicy(
                omlx_install_url=root.OMLX_INSTALL_URL,
                omlx_install_docs_url=root.OMLX_INSTALL_DOCS_URL,
                lmstudio_update_docs_url=root.LMSTUDIO_UPDATE_DOCS_URL,
                lmstudio_runtime_docs_url=root.LMSTUDIO_RUNTIME_DOCS_URL,
                mtplx_install_docs_url=root.MTPLX_INSTALL_DOCS_URL,
                ssd_streaming_runtime_urls=root.SSD_STREAMING_RUNTIME_URLS,
            ),
            uzu=runtime_catalog.UzuPolicy(
                uzu_runtime_tag=root.UZU_RUNTIME_TAG,
                uzu_runtime_upstream_tag=root.UZU_RUNTIME_UPSTREAM_TAG,
                uzu_runtime_upstream_commit=root.UZU_RUNTIME_UPSTREAM_COMMIT,
                uzu_runtime_source_patch_sha256=root.UZU_RUNTIME_SOURCE_PATCH_SHA256,
                uzu_runtime_release_url=root.UZU_RUNTIME_RELEASE_URL,
                uzu_model_page_url=root.UZU_MODEL_PAGE_URL,
            ),
            promotion=runtime_catalog.PromotionPolicy(
                runtime_promotion_schema_version=root.RUNTIME_PROMOTION_SCHEMA_VERSION,
                runtime_promotion_max_age_days=root.RUNTIME_PROMOTION_MAX_AGE_DAYS,
                benchmark_minimum_speedup=root.BENCHMARK_MINIMUM_SPEEDUP,
                benchmark_memory_meaningful_bytes=root.BENCHMARK_MEMORY_MEANINGFUL_BYTES,
                benchmark_comparison_contract_version=root.BENCHMARK_COMPARISON_CONTRACT_VERSION,
            ),
        ),
        state=runtime_catalog.RuntimeState(),
        paths=runtime_catalog.RuntimePaths(
            managed_directory=lambda: root.MANAGED_RUNTIMES_DIR,
            llamacpp_server=lambda: root.LLAMACPP_SERVER_PATH,
            home=lambda: root.Path.home(),
        ),
        selection=runtime_catalog.RuntimeSelection(selected_binary=lambda runtime: root.BINARIES.get(runtime)),
        host=runtime_catalog.RuntimeHost(platform=lambda: root.sys.platform, machine=lambda: root.platform.machine()),
        clock=runtime_catalog.RuntimeClock(
            checked_at=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            now=lambda: datetime.now(timezone.utc), record_id=lambda: str(uuid.uuid4()),
        ),
        probes=runtime_catalog.ProbesPorts(
            executable=lambda *a, **kw: root.executable(*a, **kw),
            command_version=lambda *a, **kw: root.command_version(*a, **kw),
            run_capture=lambda *a, **kw: root.subprocess.run(*a, **kw),
        ),
        lmstudio=runtime_catalog.LmstudioPorts(
            lmstudio_cache_document=lambda *a, **kw: root._lmstudio_cache_document(*a, **kw),
            lmstudio_mtp_load_supported=lambda *a, **kw: root.lmstudio_mtp_load_supported(*a, **kw),
            lmstudio_assistant_drafter_load_supported=lambda *a, **kw: root.lmstudio_assistant_drafter_load_supported(*a, **kw),
            lmstudio_assistant_drafter_runtime_contract=lambda *a, **kw: root.lmstudio_assistant_drafter_runtime_contract(*a, **kw),
        ),
        native=runtime_catalog.NativePorts(
            llamacpp_runtime_contract=lambda *a, **kw: root.llamacpp_runtime_contract(*a, **kw),
            uzu_runtime_contract=lambda *a, **kw: root.uzu_runtime_contract(*a, **kw),
            uzu_listener_protection_ready=lambda *a, **kw: root.uzu_listener_protection_ready(*a, **kw),
            runtime_executable_revision=lambda *a, **kw: root.runtime_executable_revision(*a, **kw),
        ),
        io=runtime_catalog.IoPorts(
            read_json=lambda *a, **kw: root.read_json(*a, **kw),
            disk_free_for=lambda *a, **kw: root.disk_free_for(*a, **kw),
            display_size=lambda *a, **kw: root.display_size(*a, **kw),
        ),
        evidence=runtime_catalog.EvidencePorts(
            validated_benchmark_request=lambda *a, **kw: root.validated_benchmark_request(*a, **kw),
            hardware_fingerprint=lambda *a, **kw: root.hardware_fingerprint(*a, **kw),
            load_runtime_promotion_records=lambda *a, **kw: root.load_runtime_promotion_records(*a, **kw),
            benchmark_measurement_count=lambda *a, **kw: root.benchmark_measurement_count(*a, **kw),
            sampling_record_evidence=lambda *a, **kw: root.sampling_record_evidence(*a, **kw),
            cross_engine_benchmark_measurement=lambda *a, **kw: root.cross_engine_benchmark_measurement(*a, **kw),
        ),
        resources=runtime_catalog.ResourcesPorts(
            route_qualification_memory_admission=lambda *a, **kw: root.route_qualification_memory_admission(*a, **kw),
            strict_model_load_admission_ready=lambda *a, **kw: root.strict_model_load_admission_ready(*a, **kw),
        ),
    )
