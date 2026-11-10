"""Frozen pre-extraction catalog entry points; used only by isolated tests."""
from __future__ import annotations
import copy, hashlib, json, urllib.parse
from pathlib import Path
from typing import Any
import launcher as current
import kolibri_runtime,slotstream_runtime,splash_runtime,whallm_runtime
ANE_FP16_CLONE_SOURCE_URL = current.ANE_FP16_CLONE_SOURCE_URL
ANE_TUNER_MINIMUM_RUNTIME = current.ANE_TUNER_MINIMUM_RUNTIME
ANE_TUNER_MINIMUM_SPEEDUP_PERCENT = current.ANE_TUNER_MINIMUM_SPEEDUP_PERCENT
ANE_TUNER_RELEASE_URL = current.ANE_TUNER_RELEASE_URL
ANE_TUNER_REPEATS = current.ANE_TUNER_REPEATS
ANE_TUNER_SEQUENCE_LENGTH = current.ANE_TUNER_SEQUENCE_LENGTH
BACKEND_LABELS = current.BACKEND_LABELS
BINARIES = current.BINARIES
CLIENT_ADAPTERS = current.CLIENT_ADAPTERS
DEFAULT_CONTEXT = current.DEFAULT_CONTEXT
DFLASH2_DRAFT_REPO = current.DFLASH2_DRAFT_REPO
DFLASH2_DRAFT_SIZE_LABEL = current.DFLASH2_DRAFT_SIZE_LABEL
DFLASH2_DRAFT_URL = current.DFLASH2_DRAFT_URL
DFLASH2_MINIMUM_RUNTIME = current.DFLASH2_MINIMUM_RUNTIME
DFLASH2_RECOMMENDED_RUNTIME = current.DFLASH2_RECOMMENDED_RUNTIME
DFLASH2_RELEASE_URL = current.DFLASH2_RELEASE_URL
ENGINE_ADAPTERS = current.ENGINE_ADAPTERS
FREETOKEN_NATIVE_API_VERSION = current.FREETOKEN_NATIVE_API_VERSION
FREETOKEN_NATIVE_SCHEMA_VERSION = current.FREETOKEN_NATIVE_SCHEMA_VERSION
LLAMACPP_ATOMIC_SHARDS = current.LLAMACPP_ATOMIC_SHARDS
LLAMACPP_ATOMIC_VARIANT = current.LLAMACPP_ATOMIC_VARIANT
LLAMACPP_PLE_CONTEXT = current.LLAMACPP_PLE_CONTEXT
LLAMACPP_PLE_MEMORY_CEILING_BYTES = current.LLAMACPP_PLE_MEMORY_CEILING_BYTES
LMSTUDIO_MTP_MIN_CONTINUE_PROBABILITY_DEFAULT = current.LMSTUDIO_MTP_MIN_CONTINUE_PROBABILITY_DEFAULT
LMSTUDIO_MTP_MIN_TOKENS_DEFAULT = current.LMSTUDIO_MTP_MIN_TOKENS_DEFAULT
MFERENCE_CONTEXT_WINDOWS = current.MFERENCE_CONTEXT_WINDOWS
MODEL_LIBRARY_SCHEMA_VERSION = current.MODEL_LIBRARY_SCHEMA_VERSION
SSD_ARTIFACT_BACKENDS = current.SSD_ARTIFACT_BACKENDS
SSD_STREAMING_BACKENDS = current.SSD_STREAMING_BACKENDS
SSD_STREAMING_CONTRACT_VERSION = current.SSD_STREAMING_CONTRACT_VERSION
WHALLM_CONTEXT_WINDOWS = current.WHALLM_CONTEXT_WINDOWS
WHALLM_MODEL_BYTES = current.WHALLM_MODEL_BYTES
WHALLM_MODEL_ID = current.WHALLM_MODEL_ID

def _mtplx_long_context_capability(*args, **kwargs):
    return current._mtplx_long_context_capability(*args, **kwargs)

def _physical_directory_identity(*args, **kwargs):
    return current._physical_directory_identity(*args, **kwargs)

def _preferred_physical_candidate_path(*args, **kwargs):
    return current._preferred_physical_candidate_path(*args, **kwargs)

def _preferred_scan_root_spellings(*args, **kwargs):
    return current._preferred_scan_root_spellings(*args, **kwargs)

def ane_cpu_sharing_profile(*args, **kwargs):
    return current.ane_cpu_sharing_profile(*args, **kwargs)

def ane_fp16_clone_source_profile(*args, **kwargs):
    return current.ane_fp16_clone_source_profile(*args, **kwargs)

def ane_memory_readiness(*args, **kwargs):
    return current.ane_memory_readiness(*args, **kwargs)

def ane_quantization_profile(*args, **kwargs):
    return current.ane_quantization_profile(*args, **kwargs)

def benchmark_public_mode_label(*args, **kwargs):
    return current.benchmark_public_mode_label(*args, **kwargs)

def candidate_dirs(*args, **kwargs):
    return current.candidate_dirs(*args, **kwargs)

def checkpoint_has_mtp_weights(*args, **kwargs):
    return current.checkpoint_has_mtp_weights(*args, **kwargs)

def command_version(*args, **kwargs):
    return current.command_version(*args, **kwargs)

def deep_get(*args, **kwargs):
    return current.deep_get(*args, **kwargs)

def dflash2_draft_complete(*args, **kwargs):
    return current.dflash2_draft_complete(*args, **kwargs)

def dflash2_draft_shape(*args, **kwargs):
    return current.dflash2_draft_shape(*args, **kwargs)

def dflash2_pair_fingerprint(*args, **kwargs):
    return current.dflash2_pair_fingerprint(*args, **kwargs)

def dflash2_target_profile(*args, **kwargs):
    return current.dflash2_target_profile(*args, **kwargs)

def display_size(*args, **kwargs):
    return current.display_size(*args, **kwargs)

def hardware_fingerprint(*args, **kwargs):
    return current.hardware_fingerprint(*args, **kwargs)

def inspect_native_freetoken_model(*args, **kwargs):
    return current.inspect_native_freetoken_model(*args, **kwargs)

def is_dflash2_draft(*args, **kwargs):
    return current.is_dflash2_draft(*args, **kwargs)

def is_qwen4_exp_config(*args, **kwargs):
    return current.is_qwen4_exp_config(*args, **kwargs)

def latest_benchmark_records_by_identity(*args, **kwargs):
    return current.latest_benchmark_records_by_identity(*args, **kwargs)

def llamacpp_atomic_scan_contract(*args, **kwargs):
    return current.llamacpp_atomic_scan_contract(*args, **kwargs)

def llamacpp_runtime_contract(*args, **kwargs):
    return current.llamacpp_runtime_contract(*args, **kwargs)

def lmstudio_assistant_drafter_readiness(*args, **kwargs):
    return current.lmstudio_assistant_drafter_readiness(*args, **kwargs)

def lmstudio_assistant_drafter_runtime_contract(*args, **kwargs):
    return current.lmstudio_assistant_drafter_runtime_contract(*args, **kwargs)

def lmstudio_backend_preference(*args, **kwargs):
    return current.lmstudio_backend_preference(*args, **kwargs)

def lmstudio_draft_compatibility_receipts(*args, **kwargs):
    return current.lmstudio_draft_compatibility_receipts(*args, **kwargs)

def lmstudio_gguf_catalog(*args, **kwargs):
    return current.lmstudio_gguf_catalog(*args, **kwargs)

def lmstudio_model_load_key_index(*args, **kwargs):
    return current.lmstudio_model_load_key_index(*args, **kwargs)

def lmstudio_mtp_load_supported(*args, **kwargs):
    return current.lmstudio_mtp_load_supported(*args, **kwargs)

def lmstudio_runtime_identity(*args, **kwargs):
    return current.lmstudio_runtime_identity(*args, **kwargs)

def lmstudio_runtime_packs(*args, **kwargs):
    return current.lmstudio_runtime_packs(*args, **kwargs)

def load_ane_tuning_records(*args, **kwargs):
    return current.load_ane_tuning_records(*args, **kwargs)

def load_benchmark_records(*args, **kwargs):
    return current.load_benchmark_records(*args, **kwargs)

def load_freetoken_connection(*args, **kwargs):
    return current.load_freetoken_connection(*args, **kwargs)

def matching_ane_tuning_record(*args, **kwargs):
    return current.matching_ane_tuning_record(*args, **kwargs)

def matching_benchmark_records(*args, **kwargs):
    return current.matching_benchmark_records(*args, **kwargs)

def matching_dflash2_draft(*args, **kwargs):
    return current.matching_dflash2_draft(*args, **kwargs)

def mference_model_supported(*args, **kwargs):
    return current.mference_model_supported(*args, **kwargs)

def model_artifact_fingerprint(*args, **kwargs):
    return current.model_artifact_fingerprint(*args, **kwargs)

def model_default_sampling(*args, **kwargs):
    return current.model_default_sampling(*args, **kwargs)

def model_memory_geometry(*args, **kwargs):
    return current.model_memory_geometry(*args, **kwargs)

def model_roots(*args, **kwargs):
    return current.model_roots(*args, **kwargs)

def mtplx_long_context_2111_contract(*args, **kwargs):
    return current.mtplx_long_context_2111_contract(*args, **kwargs)

def mtplx_sidecar_path(*args, **kwargs):
    return current.mtplx_sidecar_path(*args, **kwargs)

def native_mtplx_mtp_ready(*args, **kwargs):
    return current.native_mtplx_mtp_ready(*args, **kwargs)

def omlx_has_recommended_dflash2_runtime(*args, **kwargs):
    return current.omlx_has_recommended_dflash2_runtime(*args, **kwargs)

def omlx_qwen_kernel_status(*args, **kwargs):
    return current.omlx_qwen_kernel_status(*args, **kwargs)

def omlx_supports_dflash2(*args, **kwargs):
    return current.omlx_supports_dflash2(*args, **kwargs)

def omlx_version_at_least(*args, **kwargs):
    return current.omlx_version_at_least(*args, **kwargs)

def physical_memory_bytes(*args, **kwargs):
    return current.physical_memory_bytes(*args, **kwargs)

def plist_version(*args, **kwargs):
    return current.plist_version(*args, **kwargs)

def probe_whallm_endpoint(*args, **kwargs):
    return current.probe_whallm_endpoint(*args, **kwargs)

def qwen4_expert_offload_profile(*args, **kwargs):
    return current.qwen4_expert_offload_profile(*args, **kwargs)

def qwen4_ple_profile(*args, **kwargs):
    return current.qwen4_ple_profile(*args, **kwargs)

def read_json(*args, **kwargs):
    return current.read_json(*args, **kwargs)

def resolved_client_support(*args, **kwargs):
    return current.resolved_client_support(*args, **kwargs)

def route_host_support(*args, **kwargs):
    return current.route_host_support(*args, **kwargs)

def route_performance_evidence(*args, **kwargs):
    return current.route_performance_evidence(*args, **kwargs)

def runtime_app_status(*args, **kwargs):
    return current.runtime_app_status(*args, **kwargs)

def safe_int(*args, **kwargs):
    return current.safe_int(*args, **kwargs)

def slug(*args, **kwargs):
    return current.slug(*args, **kwargs)

def ssd_streaming_model_profile(*args, **kwargs):
    return current.ssd_streaming_model_profile(*args, **kwargs)

def swiftlm_model_supported(*args, **kwargs):
    return current.swiftlm_model_supported(*args, **kwargs)

def template_reasoning_efforts(*args, **kwargs):
    return current.template_reasoning_efforts(*args, **kwargs)

def uzu_model_records(*args, **kwargs):
    return current.uzu_model_records(*args, **kwargs)

def verified_ane_tuning_record(*args, **kwargs):
    return current.verified_ane_tuning_record(*args, **kwargs)

def verified_mtplx_runtime(*args, **kwargs):
    return current.verified_mtplx_runtime(*args, **kwargs)

def weight_completeness(*args, **kwargs):
    return current.weight_completeness(*args, **kwargs)


def scan_models() -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    roots = model_roots()
    preferred_root_spellings = _preferred_scan_root_spellings(roots)
    lmstudio_load_keys = lmstudio_model_load_key_index()
    benchmark_records = load_benchmark_records()
    ane_tuning_records = load_ane_tuning_records()
    machine_fingerprint = hardware_fingerprint() if benchmark_records or ane_tuning_records else ""
    installed_memory = physical_memory_bytes()
    for uzu_model in uzu_model_records(
        benchmark_records, machine_fingerprint or None,
    ):
        records[f"uzu:{uzu_model['id']}"] = uzu_model
    discovered: dict[tuple[int, int], dict[str, Any]] = {}
    for origin, root in roots:
        scanned_root = root.expanduser().absolute()
        root_identity = _physical_directory_identity(scanned_root)
        preferred_root = preferred_root_spellings.get(root_identity) if root_identity else None
        for candidate in candidate_dirs(scanned_root):
            candidate_identity = _physical_directory_identity(candidate)
            if candidate_identity is None:
                continue
            real = _preferred_physical_candidate_path(
                candidate, scanned_root, preferred_root, candidate_identity,
            )
            if real is None:
                continue
            item = discovered.setdefault(
                candidate_identity, {"path": real, "origins": []},
            )
            if origin not in item["origins"]:
                item["origins"].append(origin)

    slotstream_install = slotstream_runtime.discover(BINARIES.get("slotstream"))
    if slotstream_install and slotstream_install.get("ready"):
        shared_path = Path(slotstream_install["modelPath"]).resolve()
        identity = _physical_directory_identity(shared_path)
        if identity is not None:
            discovered.setdefault(identity, {"path": shared_path, "origins": ["Slotstream shared checkpoint"]})

    omlx_version = command_version(BINARIES.get("omlx"))
    lmstudio_cli_version = command_version(BINARIES.get("lms"))
    lmstudio_packs = lmstudio_runtime_packs()
    lmstudio_app = runtime_app_status("lms")
    lmstudio_app_version = plist_version(Path("/Applications/LM Studio.app/Contents/Info.plist"))
    lmstudio_version = lmstudio_runtime_identity(
        lmstudio_cli_version, lmstudio_app_version, lmstudio_packs,
    )
    lmstudio_mtp_runtime = lmstudio_mtp_load_supported(BINARIES.get("lms"))
    lmstudio_assistant_runtime = lmstudio_assistant_drafter_runtime_contract(
        BINARIES.get("lms"), lmstudio_cli_version, lmstudio_app,
        lmstudio_packs, lmstudio_backend_preference(),
    )
    lmstudio_gguf_models = lmstudio_gguf_catalog()
    lmstudio_draft_receipts = lmstudio_draft_compatibility_receipts()
    mtplx_version = command_version(BINARIES.get("mtplx"))
    swiftlm_version = command_version(BINARIES.get("swiftlm"))
    mference_version = command_version(BINARIES.get("mference"))
    whallm_version = command_version(BINARIES.get("whallm"))
    llamacpp_runtime = llamacpp_runtime_contract(BINARIES.get("llamacpp"))
    llamacpp_version = str(llamacpp_runtime.get("version") or "Not installed")
    freetoken_native_binary = BINARIES.get("freetoken_native")
    freetoken_native_version = command_version(freetoken_native_binary)
    dflash2_runtime = omlx_supports_dflash2(omlx_version)
    dflash2_runtime_recommended = omlx_has_recommended_dflash2_runtime(omlx_version)
    ane_runtime_version_ready = omlx_version_at_least(
        omlx_version, ANE_TUNER_MINIMUM_RUNTIME,
    )
    ane_kernel = omlx_qwen_kernel_status(BINARIES.get("omlx"))
    ane_runtime_ready = bool(
        ane_runtime_version_ready and ane_kernel.get("ready")
    )
    dflash2_candidates: list[dict[str, Any]] = []
    dflash2_drafts: list[dict[str, Any]] = []
    for item in discovered.values():
        real = item["path"]
        config = read_json(real / "config.json")
        if real.name.endswith(".gturbo"):
            manifest = read_json(real / "manifest.json")
            tokenizer_config = read_json(real / "tokenizer" / "config.json")
            config = {**tokenizer_config, **manifest}
        if not is_dflash2_draft(real, config):
            continue
        ready, status, size = weight_completeness(real, config)
        complete = ready and dflash2_draft_complete(real, config)
        candidate = {
            "path": str(real), "config": config, "complete": complete,
            "status": "Ready" if complete else status, "size": size,
        }
        dflash2_candidates.append(candidate)
        if complete:
            dflash2_drafts.append(candidate)

    for item in discovered.values():
        if not isinstance(item, dict):
            continue
        real = item["path"]
        key = str(real)
        config = read_json(real / "config.json")
        if real.name.endswith(".gturbo"):
            # Mference bundles keep their pinned model contract in the bundle
            # manifest rather than a Hugging Face-style root config.  Use the
            # same merged view for admission, fingerprinting, and launch-time
            # revalidation so a scan cannot approve one artifact and later
            # reject the unchanged bundle as stale.
            config = {
                **read_json(real / "tokenizer" / "config.json"),
                **read_json(real / "manifest.json"),
            }
        # Draft checkpoints are helpers, never standalone target models.
        if is_dflash2_draft(real, config):
            continue
        ready, status, weight_bytes = weight_completeness(real, config)
        atomic_named_variant = real.name == LLAMACPP_ATOMIC_VARIANT
        atomic_ple = (
            llamacpp_atomic_scan_contract(real)
            if atomic_named_variant else {
                "ready": False,
                "reason": "The dedicated llama.cpp route requires the exact pinned AtomicChat GGUF split.",
            }
        )
        if atomic_named_variant:
            # A single >1 MB GGUF is normally a complete standalone model, but
            # this allowlisted variant is an exact 28-shard split.  Bind its
            # library readiness to the parent acquisition receipt so an
            # interrupted nested download is never advertised as Ready.
            ready = atomic_ple.get("ready") is True
            status = (
                "Ready" if ready else
                str(atomic_ple.get("reason") or "The pinned 28-shard split is incomplete.")
            )
            if ready:
                weight_bytes = int(atomic_ple["weightBytes"])
        ggufs = sorted(real.glob("*.gguf"))
        model_tensors = [
            tensor for tensor in real.glob("*.safetensors")
            if tensor.name != "mtp.safetensors" and tensor.stat().st_size > 0
        ]
        fmt = (
            "mference"
            if real.name.endswith(".gturbo") else
            "gguf" if ggufs and not model_tensors else "mlx"
        )
        artifact = ggufs[0] if fmt == "gguf" else real
        context = deep_get(
            config,
            ("text_config", "max_position_embeddings"),
            ("max_position_embeddings",),
            ("model_max_length",),
        )
        try:
            context = int(context)
            if not 1_024 <= context <= 2_000_000:
                context = None
        except (TypeError, ValueError):
            context = None
        root_model_type = str(config.get("model_type") or "unknown")
        text_model_type = str(deep_get(config, ("text_config", "model_type")) or "unknown")
        model_type = text_model_type if text_model_type != "unknown" else root_model_type
        architectures = config.get("architectures") or deep_get(config, ("text_config", "architectures")) or []
        architecture = str(architectures[0]) if isinstance(architectures, list) and architectures else model_type
        quant = deep_get(config, ("quantization", "bits"), ("quantization_config", "bits"))
        quantization = f"{quant}-bit" if isinstance(quant, (int, float)) else "From artifact"
        atomic_ple_ready = bool(
            atomic_ple.get("ready") is True
            and atomic_ple.get("currentProcessVerified") is True
            and isinstance(atomic_ple.get("verificationGeneration"), int)
            and atomic_ple.get("verificationGeneration") > 0
        )
        if atomic_ple_ready:
            context = LLAMACPP_PLE_CONTEXT
            root_model_type = "qwen4exp"
            text_model_type = "qwen4exp"
            model_type = "qwen4exp"
            architecture = "Qwen3.8-Flash-Next · Qwen4Exp"
            quantization = "AD-3.84bpw · IQ4_XS-M64 · SSD-only PLE"
        qwen4_ple = qwen4_ple_profile(real, config, ready and fmt == "mlx", omlx_version)
        expert_offload = qwen4_expert_offload_profile(real, config, qwen4_ple, omlx_version)
        ssd_profile = ssd_streaming_model_profile(
            real, config, weight_bytes, installed_memory,
        )
        swiftlm_family_ready, swiftlm_family_reason = swiftlm_model_supported(
            real, config, ssd_profile,
        )
        mference_family_ready, mference_family_reason = mference_model_supported(
            real, ssd_profile,
        )
        ane_profile = ane_quantization_profile(config)
        ane_memory = ane_memory_readiness(weight_bytes, installed_memory)
        ane_cpu_profile = ane_cpu_sharing_profile(real)
        ane_clone_profile = ane_fp16_clone_source_profile(real, config, weight_bytes)
        ane_cpu_memory = ane_memory_readiness(weight_bytes, installed_memory, cpu_assist=True)
        ane_ready_to_tune = bool(
            ready and fmt == "mlx" and ane_profile["compatible"]
            and ane_runtime_ready and ane_memory["ready"]
        )
        if not ready or fmt != "mlx":
            ane_reason = "ANE tuning requires a complete MLX checkpoint."
        elif not ane_profile["compatible"]:
            ane_reason = str(ane_profile["reason"])
        elif not ane_runtime_version_ready:
            ane_reason = f"Update {omlx_version} to oMLX {ANE_TUNER_MINIMUM_RUNTIME} or newer before tuning ANE prefill."
        elif not ane_kernel.get("ready"):
            ane_reason = str(
                ane_kernel.get("reason")
                or "The selected oMLX installation has no verified native Qwen kernel."
            )
        elif not ane_memory["ready"]:
            ane_reason = str(ane_memory["reason"])
        else:
            ane_reason = "Ready for a temporary GPU baseline and ANE/GPU split measurement."
        ane_cpu_available = bool(
            ane_ready_to_tune
            and ane_cpu_profile["eligible"]
            and ane_cpu_memory["ready"]
        )
        if not ane_cpu_profile["eligible"]:
            ane_cpu_reason = str(ane_cpu_profile["reason"])
        elif not ane_cpu_memory["ready"]:
            ane_cpu_reason = str(ane_cpu_memory["reason"])
        elif not ane_ready_to_tune:
            ane_cpu_reason = "Resolve the standard ANE Tuner checks before adding CPU candidates."
        else:
            ane_cpu_reason = "This separate FP16 clone can include measured CPU-sharing candidates."
        ane_readiness = {
            "ready": ane_ready_to_tune,
            "modelCompatible": bool(ane_profile["compatible"]),
            "modelReason": ane_profile["reason"],
            "quantizationMode": ane_profile["mode"],
            "bits": ane_profile["bits"],
            "groupSize": ane_profile["groupSize"],
            "runtimeReady": ane_runtime_ready,
            "runtimeVersionReady": ane_runtime_version_ready,
            "runtimeDetected": omlx_version,
            "minimumRuntime": ANE_TUNER_MINIMUM_RUNTIME,
            "kernelReady": bool(ane_kernel.get("ready")),
            "kernelState": str(ane_kernel.get("state") or "unverified"),
            "kernelReason": str(ane_kernel.get("reason") or "Native Qwen kernel not verified."),
            "releaseUrl": ANE_TUNER_RELEASE_URL,
            "memoryReady": bool(ane_memory["ready"]),
            "memory": ane_memory,
            "cpuMemoryReady": bool(ane_cpu_memory["ready"]),
            "cpuMemory": ane_cpu_memory,
            "sequenceLength": ANE_TUNER_SEQUENCE_LENGTH,
            "repeats": ANE_TUNER_REPEATS,
            "minimumSpeedupPercent": ANE_TUNER_MINIMUM_SPEEDUP_PERCENT,
            "cpuSharingEligible": bool(ane_cpu_profile["eligible"]),
            "cpuSharingAvailable": ane_cpu_available,
            "cpuSharingReason": ane_cpu_reason,
            "cpuFloatDtypes": ane_cpu_profile["floatDtypes"],
            "cpuFloatingTensorCount": ane_cpu_profile["floatingTensorCount"],
            "cpuGateUpScalePairs": ane_cpu_profile["gateUpScalePairs"],
            "cpuDownProjectionEligible": bool(ane_cpu_profile["downProjectionEligible"]),
            "cpuGdnEligible": bool(ane_cpu_profile["gdnEligible"]),
            "cpuProfileFingerprint": ane_cpu_profile["profileFingerprint"],
            "cpuCloneEligible": bool(ane_clone_profile["eligible"]),
            "cpuCloneReason": ane_clone_profile["reason"],
            "cpuCloneSourceUrl": ANE_FP16_CLONE_SOURCE_URL,
            "experimental": True,
            "approximate": True,
            "reason": ane_reason,
        }
        mtp_layers = deep_get(config, ("text_config", "mtp_num_hidden_layers"), ("mtp_num_hidden_layers",))
        mtp_declared = isinstance(mtp_layers, int) and mtp_layers > 0
        integrated_mtp = mtp_declared and checkpoint_has_mtp_weights(real, config)
        sidecar_path = mtplx_sidecar_path(real, config)
        sidecar_mtp = sidecar_path.is_file()
        try:
            mtp_sidecar_bytes = sidecar_path.stat().st_size if sidecar_mtp else 0
        except OSError:
            mtp_sidecar_bytes = 0
        runtime = read_json(real / "mtplx_runtime.json")
        reasoning_efforts = template_reasoning_efforts(real)
        default_sampling = model_default_sampling(real)
        if atomic_ple_ready:
            # These are the publisher's thinking-mode defaults embedded in the
            # pinned GGUF chat template. Keep the first qualification on model
            # defaults instead of inventing an engine-side sampler.
            reasoning_efforts = ["low", "medium", "xhigh"]
            default_sampling = {"temperature": 1.0, "top_p": 0.95, "top_k": 20}
        lm_reasoning_efforts = [level for level in reasoning_efforts if level in {"low", "medium", "high"}]
        mtplx_verified = verified_mtplx_runtime(real, runtime, config)
        mtplx_native_ready = mtplx_verified or bool(
            ready and fmt == "mlx" and runtime and native_mtplx_mtp_ready(real, config)
        )
        mtp_depth = runtime.get("mtp_depth_default") if isinstance(runtime.get("mtp_depth_default"), int) else 3
        mtp_depth_max = safe_int(runtime.get("mtp_depth_max"), 3, 1, 8) if mtplx_native_ready else 1
        # `lms load` resolves LM Studio's canonical/default identifier,
        # not necessarily the case-preserved catalog path. Recent MLX entries
        # may also use `model@6bit` aliases that a folder name cannot recreate.
        canonical_lm_key = lmstudio_load_keys.get(str(real))
        if canonical_lm_key:
            lm_key = canonical_lm_key
            lm_catalogued = True
        else:
            try:
                lm_relative = real.relative_to(Path.home() / ".lmstudio" / "models")
            except ValueError:
                lm_key = str(artifact)
                lm_catalogued = False
            else:
                derived_lm_key = "/".join(lm_relative.parts[:2]) if len(lm_relative.parts) >= 2 else lm_relative.name
                lm_key = derived_lm_key.lower()
                lm_catalogued = True
        lmstudio_assistant_drafter = lmstudio_assistant_drafter_readiness(
            real, lmstudio_gguf_models, lmstudio_draft_receipts,
            lmstudio_assistant_runtime,
        )
        qwen4_architecture = is_qwen4_exp_config(config)
        omlx_artifact_ready = bool(
            ready and fmt == "mlx"
            and (not qwen4_architecture or qwen4_ple.get("supported") is True)
        )
        omlx_mtp = bool(
            omlx_artifact_ready and integrated_mtp and not sidecar_mtp
            and model_type.startswith(("qwen3_5", "qwen3_6", "deepseek_v4", "qwen4_exp"))
        )
        lmstudio_mtp_artifact = bool(
            ready and lm_catalogued and sidecar_mtp and mtplx_verified
        )
        lmstudio_mtp = bool(lmstudio_mtp_runtime and lmstudio_mtp_artifact)
        dflash2_profile = (
            dflash2_target_profile(real, config)
            if ready and fmt == "mlx" and not qwen4_architecture else None
        )
        dflash2_candidate = matching_dflash2_draft(real, config, dflash2_candidates) if dflash2_profile else None
        dflash2_complete_draft = matching_dflash2_draft(real, config, dflash2_drafts) if dflash2_profile else None
        dflash2_draft = dflash2_complete_draft if dflash2_runtime else None
        dflash2_ready = dflash2_draft is not None
        dflash2_pair_id = None
        dflash2_shape = None
        if dflash2_draft:
            dflash2_shape = dflash2_draft_shape(dflash2_draft["config"])
            dflash2_pair_id = dflash2_pair_fingerprint(
                real,
                config,
                Path(str(dflash2_draft["path"])),
                dflash2_draft["config"],
            )
        dflash2_default_block = int(dflash2_shape["block_size"]) if dflash2_shape else None
        if dflash2_ready:
            dflash2_reason = "Compatible local DFlash 2 draft detected; choose it manually or add a matching local benchmark before the optimiser selects it."
        elif not dflash2_profile:
            dflash2_reason = "No published DFlash 2 draft matches this target model's family and geometry."
        elif not dflash2_runtime and not dflash2_complete_draft:
            dflash2_reason = (
                f"Target matches {DFLASH2_DRAFT_REPO}; update oMLX {omlx_version} to "
                f"{DFLASH2_RECOMMENDED_RUNTIME} and download the {DFLASH2_DRAFT_SIZE_LABEL} draft."
            )
        elif not dflash2_runtime:
            dflash2_reason = (
                f"Matching draft is installed; update oMLX {omlx_version} to "
                f"{DFLASH2_RECOMMENDED_RUNTIME} to enable DFlash 2."
            )
        elif dflash2_candidate and not dflash2_candidate.get("complete"):
            dflash2_reason = "The matching DFlash 2 draft is present but its weight download is incomplete or invalid."
        elif not dflash2_complete_draft:
            dflash2_reason = (
                f"Runtime is ready; download the matching {DFLASH2_DRAFT_SIZE_LABEL} "
                f"{DFLASH2_DRAFT_REPO} draft."
            )
        else:
            dflash2_reason = "Installed DFlash 2 drafts do not match this target model's family, layer count, and vocabulary."
        dflash2_readiness = {
            "targetCompatible": bool(dflash2_profile),
            "targetReason": (
                f"Exact {DFLASH2_DRAFT_REPO} geometry match"
                if dflash2_profile else "No published matching draft"
            ),
            "runtimeReady": dflash2_runtime,
            "runtimeRecommended": dflash2_runtime_recommended,
            "runtimeDetected": omlx_version,
            "minimumRuntime": DFLASH2_MINIMUM_RUNTIME,
            "recommendedRuntime": DFLASH2_RECOMMENDED_RUNTIME,
            "releaseUrl": DFLASH2_RELEASE_URL,
            "draftInstalled": dflash2_complete_draft is not None,
            "draftDetected": dflash2_candidate is not None,
            "draftComplete": bool(dflash2_candidate and dflash2_candidate.get("complete")),
            "draftPath": str(dflash2_candidate.get("path")) if dflash2_candidate else None,
            "draftStatus": (
                str(dflash2_candidate.get("status") or "Detected")
                if dflash2_candidate else "Not installed"
            ),
            "draftRepo": DFLASH2_DRAFT_REPO,
            "draftUrl": DFLASH2_DRAFT_URL,
            "draftSizeLabel": DFLASH2_DRAFT_SIZE_LABEL,
            "ready": dflash2_ready,
        }
        backend = {
            "omlx": {
                "runnable": omlx_artifact_ready,
                "reason": (
                    "Ready for oMLX with read-only PLE N-gram SSD mmap"
                    if qwen4_ple.get("supported") is True else
                    str(qwen4_ple.get("reason"))
                    if qwen4_architecture else
                    "Ready for oMLX" if ready and fmt == "mlx" else
                    "oMLX requires a complete MLX artifact"
                ),
                "qwen4Ple": copy.deepcopy(qwen4_ple),
                "mtp": omlx_mtp,
                "mtpReason": "Native integrated MTP tensors detected" if omlx_mtp else ("Config advertises MTP, but this conversion contains no MTP tensors" if mtp_declared and not sidecar_mtp else "No verified oMLX-native MTP tensors"),
                "dflash": dflash2_ready,
                "dflashVersion": "2" if dflash2_ready else None,
                "dflashReason": dflash2_reason,
                "dflashDraftPath": dflash2_draft.get("path") if dflash2_draft else None,
                "dflashDraftSize": int(dflash2_draft.get("size") or 0) if dflash2_draft else 0,
                "dflashBlockSize": dflash2_default_block if dflash2_ready else None,
                "dflashMaxBlockSize": int(dflash2_shape["block_size"]) if dflash2_shape else None,
                "dflashPairFingerprint": dflash2_pair_id,
                "dflashRuntimeVersion": omlx_version,
                "dflashBenchmark": None,
                "dflashBenchmarkVerified": False,
                "dflashPreferred": False,
                "dflashReadiness": dflash2_readiness,
                "anePrefill": False,
                "aneReason": ane_reason,
                "aneReadiness": ane_readiness,
                "aneTuning": None,
                "aneTuningVerified": False,
                "preferredAcceleration": "mtp" if omlx_mtp else "off",
                "depth": dflash2_default_block if dflash2_ready else 1,
                "depthMax": int(dflash2_shape["block_size"]) if dflash2_shape else (3 if omlx_mtp and qwen4_architecture else 8 if omlx_mtp else 1),
                # Qwen4 QSA carries unquantised index keys and MRoPE positions.
                # Keep TurboQuant fail-closed until this exact route is measured.
                "kv": not qwen4_architecture,
                "agentReasoning": ["auto", "off", *reasoning_efforts],
                "codexReasoning": ["auto", *reasoning_efforts],
            },
            "lmstudio": {
                    "runnable": ready and lm_catalogued and not qwen4_architecture and not atomic_ple_ready,
                    "reason": (
                        "This exact AtomicChat split is admitted only through the pinned llama.cpp SSD-PLE route."
                        if atomic_ple_ready else
                        "LM Studio has no verified external Qwen4 PLE mmap route."
                        if qwen4_architecture else
                        "LM Studio catalog model" if lm_catalogued else
                        "Detected external GGUF; register/import it in LM Studio first"
                        if ready and fmt == "gguf" else "Not registered with LM Studio"
                    ),
                    "mtp": lmstudio_mtp,
                    "mtpReason": (
                        "Selected LM Studio CLI exposes load-time Draft MTP and the sidecar pairing/audit is valid; benchmark this route before the optimiser prefers it."
                        if lmstudio_mtp else
                        "The selected LM Studio CLI does not expose the complete load-time Draft MTP flag contract."
                        if lmstudio_mtp_artifact and not lmstudio_mtp_runtime else
                        "MTP sidecar is present but its pairing/audit is not verified."
                        if sidecar_mtp else "No MTP sidecar found."
                    ),
                    "mtpRuntimeVerified": lmstudio_mtp_runtime,
                    "assistantDrafter": lmstudio_assistant_drafter,
                    "preferredAcceleration": "off",
                    "dflash": False,
                    "dflashVersion": None,
                    "dflashReason": f"{lmstudio_cli_version} does not expose a verified DFlash 2 loading route.",
                    "kv": False,
                    # LM Studio's Chat Completions compatibility route does
                    # not expose a reasoning control. Codex uses Responses,
                    # where only levels advertised by both the model template
                    # and LM Studio's public API vocabulary are offered.
                    "agentReasoning": ["auto"],
                    "codexReasoning": ["auto", *lm_reasoning_efforts],
                    "depth": mtp_depth,
                    "depthMax": mtp_depth_max if lmstudio_mtp else 1,
                    "mtpMinTokens": LMSTUDIO_MTP_MIN_TOKENS_DEFAULT,
                    "mtpMinContinueProbability": LMSTUDIO_MTP_MIN_CONTINUE_PROBABILITY_DEFAULT,
            },
            "mtplx": {
                    "runnable": ready and fmt == "mlx" and not qwen4_architecture,
                    "reason": (
                        "MTPLX has no verified external Qwen4 PLE mmap route."
                        if qwen4_architecture else
                        "MLX artifact; MTPLX validates again before loading"
                        if ready and fmt == "mlx" else
                        "MTPLX requires a complete compatible MLX artifact"
                    ),
                    "mtp": mtplx_native_ready,
                    "mtpReason": (
                        "Verified MTPLX runtime contract"
                        if mtplx_native_ready else
                        "No matching MTP weights have been verified by MTPLX."
                    ),
                    "dflash": False,
                    "dflashVersion": None,
                    "dflashReason": f"{mtplx_version} serves native MTP or AR; DFlash 2 is not a serving mode.",
                    "kv": True,
                    "profile": runtime.get("recommended_profile") if isinstance(runtime.get("recommended_profile"), str) else "sustained",
                    "depth": mtp_depth,
                    "depthMax": mtp_depth_max,
                    "agentReasoning": ["auto", "off", "low", "medium", "high", "xhigh"],
                    "codexReasoning": ["auto", "low", "medium", "high", "xhigh"],
            },
            "freetoken": {
                    "runnable": False,
                    "reason": (
                        "The native FreeToken port currently accepts only complete Qwen3-MoE MLX checkpoints."
                        if freetoken_native_binary else
                        "Install the native Apple-Silicon port or connect a FreeToken server."
                    ),
                    "mtp": False,
                    "mtpReason": "Native FreeToken owns expert execution; speculative MTP is not exposed.",
                    "dflash": False,
                    "dflashVersion": None,
                    "dflashReason": "DFlash 2 is not a FreeToken serving mode.",
                    "kv": False,
                    "preferredAcceleration": "off",
                    "depth": 1,
                    "depthMax": 1,
                    "agentReasoning": ["auto"],
                    "codexReasoning": ["auto"],
                    "customSampling": False,
                    "samplingReason": "The native FreeToken milestone currently uses greedy decoding only.",
            },
            "swiftlm": {
                    "runnable": bool(
                        ready and fmt == "mlx" and ssd_profile["moe"]
                        and swiftlm_family_ready
                    ),
                    "reason": (
                        swiftlm_family_reason
                        if ready and fmt == "mlx" and ssd_profile["moe"] else
                        "SwiftLM SSD streaming requires a complete MLX Mixture-of-Experts checkpoint."
                    ),
                    "mtp": False,
                    "mtpReason": "MTP is deliberately disabled for SSD-streamed MoEs because verification multiplies expert I/O fan-out.",
                    "dflash": False,
                    "dflashVersion": None,
                    "dflashReason": "DFlash is outside the exact SSD-streaming calibration contract.",
                    "kv": False,
                    "preferredAcceleration": "off",
                    "depth": 1,
                    "depthMax": 1,
                    "agentReasoning": ["auto", "off"],
                    "codexReasoning": ["auto"],
                    "ssdStreaming": True,
                    "ssdProfile": copy.deepcopy(ssd_profile),
                    "modelPath": str(real),
                    "nativeExpertTopK": int(ssd_profile.get("nativeExpertTopK") or 0),
                    "prefillSize": 512,
                    "exactExpertRouting": True,
            },
            "mference": {
                    "runnable": bool(ready and fmt == "mference" and mference_family_ready),
                    "reason": mference_family_reason,
                    "mtp": False,
                    "mtpReason": "Mference uses model-native expert execution; no speculative route is included in SSD calibration.",
                    "dflash": False,
                    "dflashVersion": None,
                    "dflashReason": "DFlash is outside Mference's pinned model contract.",
                    "kv": False,
                    "preferredAcceleration": "off",
                    "depth": 1,
                    "depthMax": 1,
                    "agentReasoning": ["auto"],
                    "codexReasoning": ["auto"],
                    "ssdStreaming": True,
                    "ssdProfile": copy.deepcopy(ssd_profile),
                    "modelPath": str(real),
                    "promptCacheMode": "on",
                    "queueLimit": 4,
                    "contextWindows": list(MFERENCE_CONTEXT_WINDOWS),
                    "contextMaximum": max(MFERENCE_CONTEXT_WINDOWS),
                    "exactExpertRouting": True,
            },
            "whallm": {
                    "runnable": False,
                    "reason": (
                        "Whallm uses its own pinned 125 GB Qwen3.8 Flash-Next MXFP4 install; "
                        "it cannot consume this scanned model folder. Start Whallm's server "
                        "and rescan to use its advertised model."
                        if ssd_profile.get("qwen38FlashNext") else
                        "Whallm currently accepts only its pinned Qwen3.8 Flash-Next checkpoint."
                    ),
                    "mtp": False,
                    "mtpReason": (
                        "Whallm's optional Qwen MTP prototype is confined to its own pinned install "
                        "and is not an acceleration mode for this scanned model folder."
                    ),
                    "dflash": False,
                    "dflashVersion": None,
                    "dflashReason": "DFlash is not a Whallm serving mode.",
                    "kv": False,
                    "preferredAcceleration": "off",
                    "depth": 1,
                    "depthMax": 1,
                    "agentReasoning": ["auto", "off", "low", "medium", "high", "xhigh", "max"],
                    "codexReasoning": ["auto", "off", "low", "medium", "high", "xhigh", "max"],
                    "ssdStreaming": True,
                    "ssdProfile": copy.deepcopy(ssd_profile),
                    "exactExpertRouting": True,
            },
            "llamacpp": {
                    "runnable": bool(atomic_ple_ready and llamacpp_runtime.get("ready") is True),
                    "reason": (
                        str(llamacpp_runtime.get("reason") or "The pinned llama.cpp runtime is not ready.")
                        if atomic_ple_ready else str(atomic_ple.get("reason") or "This GGUF is not allowlisted.")
                    ),
                    "mtp": False,
                    "mtpReason": "MTP and draft-model speculation are disabled for the initial SSD-PLE qualification.",
                    "dflash": False,
                    "dflashVersion": None,
                    "dflashReason": "DFlash is a different serving route and is not mixed into this qualification.",
                    "kv": False,
                    "preferredAcceleration": "off",
                    "depth": 1,
                    "depthMax": 1,
                    "agentReasoning": ["auto"],
                    "codexReasoning": ["auto"],
                    "contextWindows": [LLAMACPP_PLE_CONTEXT],
                    "contextMaximum": LLAMACPP_PLE_CONTEXT,
                    "atomicPle": copy.deepcopy(atomic_ple),
                    "llamacppPle": atomic_ple_ready,
                    "verificationState": atomic_ple.get("verificationState"),
                    "currentProcessVerified": atomic_ple.get("currentProcessVerified") is True,
                    "verificationGeneration": atomic_ple.get("verificationGeneration"),
                    "verifiedShards": int(atomic_ple.get("verifiedShards") or 0),
                    "totalShards": int(
                        atomic_ple.get("totalShards") or LLAMACPP_ATOMIC_SHARDS
                    ),
                    "presentationSnapshot": atomic_ple.get("presentationSnapshot") is True,
                    "receiptFingerprint": atomic_ple.get("receiptFingerprint"),
                    "modelPath": str(real),
                    "firstShard": atomic_ple.get("firstShard"),
                    "memoryCeilingBytes": LLAMACPP_PLE_MEMORY_CEILING_BYTES,
                    "exactExpertRouting": True,
            },
        }
        model_fingerprint = model_artifact_fingerprint(real, config) if ready else ""
        freetoken_capability = backend["freetoken"]
        if freetoken_native_binary and ready and fmt == "mlx":
            if model_type != "qwen3_moe":
                freetoken_capability["reason"] = (
                    f"Native FreeToken schema {FREETOKEN_NATIVE_SCHEMA_VERSION} supports model_type=qwen3_moe; "
                    f"this checkpoint reports {model_type}."
                )
            else:
                try:
                    native_contract = inspect_native_freetoken_model(
                        real, int(context or DEFAULT_CONTEXT), model_fingerprint,
                    )
                    rejection = native_contract.get("rejection")
                    supported_contract = native_contract.get("supported") is True
                    startup_allowed = native_contract.get("startup", {}).get("default_allowed") is True
                    qualification = native_contract["qualification"]
                    qualification_policy = qualification["launcher"]
                    real_checkpoint_verified = (
                        qualification.get("real_checkpoint_verified") is True
                        and qualification.get("inspected_checkpoint_qualified") is True
                        and qualification_policy.get("readiness") == "qualified_real_checkpoint"
                    )
                    experimental_checkpoint = (
                        qualification_policy.get("readiness") == "experimental_synthetic_only"
                    )
                    if supported_contract and startup_allowed:
                        native_reason = (
                            "Native FreeToken qualified this exact real checkpoint with an end-to-end serve and token-generation receipt."
                            if real_checkpoint_verified else
                            "This existing local checkpoint passed format and memory preflight, but the port has only tiny-synthetic end-to-end verification. An explicit experimental-run approval is required."
                        )
                    elif supported_contract:
                        working = native_contract.get("working_set", {})
                        needed = native_contract.get("sizing", {}).get("weights_plus_kv_bytes")
                        budget = working.get("budget_after_headroom_bytes")
                        native_reason = (
                            "Native FreeToken supports this checkpoint, but its maximum-context working-set preflight "
                            f"needs {display_size(int(needed)) if isinstance(needed, int) else 'more memory'} against "
                            f"a {display_size(int(budget)) if isinstance(budget, int) else 'smaller'} safe budget. "
                            "The launcher will not apply the unsafe override automatically."
                        )
                    else:
                        native_reason = str(
                            rejection.get("message")
                            if isinstance(rejection, dict) else
                            "Native FreeToken rejected this checkpoint."
                        )[:600]
                    max_context = native_contract.get("model", {}).get("max_context_tokens")
                    expert_count = deep_get(
                        config, ("text_config", "num_experts"),
                        ("text_config", "num_local_experts"),
                        ("num_experts",), ("num_local_experts",),
                    )
                    freetoken_capability.update({
                        "runnable": bool(supported_contract and startup_allowed),
                        "reason": native_reason,
                        "native": True,
                        "nativeContract": native_contract,
                        "nativeBinary": str(Path(freetoken_native_binary).expanduser().resolve()),
                        "nativeApiVersion": FREETOKEN_NATIVE_API_VERSION,
                        "qualificationReadiness": qualification_policy.get("readiness"),
                        "realCheckpointVerified": real_checkpoint_verified,
                        "experimentalQualification": experimental_checkpoint,
                        "largeDownloadRecommended": qualification_policy.get("large_download_recommended") is True,
                        "nativeExpertCount": (
                            int(expert_count)
                            if isinstance(expert_count, int) and not isinstance(expert_count, bool)
                            and expert_count > 0 else None
                        ),
                        "nativeMaxContext": (
                            int(max_context)
                            if isinstance(max_context, int) and not isinstance(max_context, bool)
                            else context
                        ),
                        "clientSupport": {
                            "chat": {
                                "supported": native_contract.get("support", {}).get("chat_completions") is True,
                                "reason": (
                                    "Native streaming Chat Completions on an exactly qualified real checkpoint; greedy decoding in the current port milestone."
                                    if real_checkpoint_verified else
                                    "Native streaming Chat Completions; this checkpoint remains an explicit synthetic-only experimental run."
                                ),
                            },
                            "pi": {
                                "supported": False,
                                "reason": "Native FreeToken does not expose tool calling yet, so Pi is blocked fail-closed.",
                            },
                            "omp": {
                                "supported": False,
                                "reason": "Native FreeToken does not expose tool calling yet, so oh-my-pi is blocked fail-closed.",
                            },
                            "opencode": {
                                "supported": False,
                                "reason": "Native FreeToken does not expose tool calling yet, so OpenCode is blocked fail-closed.",
                            },
                            "codex": {
                                "supported": False,
                                "reason": "Native FreeToken does not expose the Responses API yet, so Codex is blocked fail-closed.",
                            },
                        },
                    })
                except ValueError as error:
                    freetoken_capability["reason"] = str(error)[:600]
        ane_record = matching_ane_tuning_record(
            ane_tuning_records, model_fingerprint, omlx_version,
            machine_fingerprint or None,
        ) if ane_tuning_records and model_fingerprint else None
        ane_verified = verified_ane_tuning_record(
            ane_record, model_fingerprint, omlx_version,
            machine_fingerprint or None,
        ) if ane_record else False
        omlx_capability = backend["omlx"]
        omlx_capability["aneTuning"] = ane_record
        omlx_capability["aneTuningVerified"] = ane_verified
        omlx_capability["anePrefill"] = ane_verified
        omlx_capability["aneReadiness"]["tuned"] = ane_verified
        omlx_capability["aneReadiness"]["latestResultAccepted"] = bool(ane_record and ane_record.get("accepted"))
        if ane_verified:
            speedup = float(ane_record["recommendation"]["speedup_percent"])
            omlx_capability["aneReason"] = (
                f"A local ANE execution trace proved a {speedup:.1f}% prefill gain for this exact checkpoint/runtime/Mac."
            )
        runtime_versions = {
            "omlx": omlx_version,
            "lmstudio": lmstudio_version,
            "mtplx": mtplx_version,
            "freetoken": freetoken_native_version,
            "swiftlm": swiftlm_version,
            "mference": mference_version,
            "whallm": whallm_version,
            "llamacpp": llamacpp_version,
        }
        mtplx_scan_model = {
            "name": real.name,
            "path": str(real),
            "format": fmt,
            "architecture": architecture,
            "modelType": model_type,
            "rootModelType": root_model_type,
            "textModelType": text_model_type,
            "nativeContext": context,
            "ready": ready,
        }
        mtplx_scan_capability = {
            **backend["mtplx"],
            "runtimeVersion": mtplx_version,
            "benchmarkModelFingerprint": model_fingerprint,
        }
        mtplx_long_context_receipt = mtplx_long_context_2111_contract(
            mtplx_scan_model, mtplx_scan_capability,
            runtime_version=mtplx_version,
        )
        backend["mtplx"]["longContext2111"] = _mtplx_long_context_capability(
            mtplx_long_context_receipt, mtplx_version,
        )
        for backend_name, capability in backend.items():
            runtime_version = runtime_versions[backend_name]
            capability["runtimeVersion"] = runtime_version
            capability["benchmarkModelFingerprint"] = model_fingerprint
            # These local routes consume the same verified model artifact from
            # which ``defaultSampling`` was read. Model mode may therefore
            # leave protocol-specific fields implicit when a client API cannot
            # spell every artifact default. Custom mode never receives this
            # exception.
            capability["implicitSamplingDefaultsVerified"] = bool(
                ready and capability.get("runnable") is True
            )
            if backend_name in SSD_STREAMING_BACKENDS:
                capability["artifactFingerprint"] = model_fingerprint
                capability["comparisonIdentity"] = ssd_profile.get("comparisonIdentity")
            capability["localBenchmark"] = None
            capability["localBenchmarks"] = []
            capability["fallbackAcceleration"] = capability.get("preferredAcceleration")
            benchmark_history = matching_benchmark_records(
                benchmark_records, backend_name, model_fingerprint,
                runtime_version, capability, machine_fingerprint or None,
            )
            capability["benchmarkHistoryCount"] = len(benchmark_history)
            benchmarks = latest_benchmark_records_by_identity(benchmark_history)
            capability["localBenchmarks"] = benchmarks
            benchmark = benchmarks[-1] if benchmarks else None
            if not benchmark:
                continue
            capability["localBenchmark"] = benchmark
            capability["preferredAccelerationSource"] = "local-benchmark"
            winner = benchmark.get("winner")
            if winner == "dflash2" and capability.get("dflash"):
                capability["preferredAcceleration"] = "dflash"
                capability["dflashBenchmark"] = copy.deepcopy(benchmark)
                capability["dflashBenchmarkVerified"] = benchmark.get("qualityPassed") is True
                capability["dflashPreferred"] = True
            elif winner == "mtp" and capability.get("mtp"):
                capability["preferredAcceleration"] = "mtp"
                # A catalog scan knows only artifact/runtime/Mac identity. It
                # must not copy request-specific tuning coordinates into the
                # artifact capability before context, reasoning, sampling, KV,
                # and engine controls have been verified. ``fastest_safe_options``
                # applies those coordinates later from an exact matching record.
            elif winner == "ar":
                capability["preferredAcceleration"] = "off"

        if expert_offload.get("supported"):
            backend["omlx"].update({
                "expertOffload": True, "experimental": True,
                "mtp": False, "dflash": False, "depth": 1, "depthMax": 1,
                "preferredAcceleration": "off", "fallbackAcceleration": "off", "anePrefill": False,
                "reason": expert_offload["reason"], "mtpReason": "oMLX expert offload requires MTP to be off.",
            })
        shared_slotstream = bool(slotstream_install and str(real) == str(Path(slotstream_install["modelPath"]).resolve()))
        if shared_slotstream:
            for engine_name, engine_cap in backend.items():
                if engine_name != "omlx":
                    engine_cap["runnable"] = False
                    engine_cap["reason"] = "Use the separate Slotstream route for this engine."
            backend["omlx"]["runnable"] = bool(omlx_artifact_ready and expert_offload.get("supported"))
            if not backend["omlx"]["runnable"]:
                backend["omlx"]["reason"] = expert_offload["reason"]
        records[key] = {
            "id": slug(key),
            "name": "Qwen3.8 Flash-Next · oMLX · SSD experts" if shared_slotstream else real.name,
            "path": str(real),
            "artifact": str(artifact),
            "origins": list(item["origins"]),
            "format": fmt,
            "architecture": architecture,
            "modelType": model_type,
            "rootModelType": root_model_type,
            "textModelType": text_model_type,
            "nativeContext": context,
            "quantization": quantization,
            "size": weight_bytes,
            "sizeLabel": display_size(weight_bytes),
            "memoryGeometry": model_memory_geometry(config),
            "qwen4Ple": copy.deepcopy(qwen4_ple),
            "omlxExpertOffload": copy.deepcopy(expert_offload),
            "mtpSidecarSize": mtp_sidecar_bytes,
            "ready": ready,
            "status": status,
            "mtp": {"declared": mtp_declared, "integrated": integrated_mtp, "sidecar": sidecar_mtp},
            "templateReasoningEfforts": reasoning_efforts,
            "defaultSampling": default_sampling,
            "lmKey": lm_key,
            "nativeFreetoken": freetoken_capability.get("native") is True,
            "ssdStreaming": ssd_profile,
            "atomicPle": copy.deepcopy(atomic_ple),
            "verificationState": atomic_ple.get("verificationState") if atomic_named_variant else None,
            "currentProcessVerified": atomic_ple.get("currentProcessVerified") is True,
            "verificationProgress": {
                "completed": int(atomic_ple.get("verifiedShards") or 0),
                "total": int(atomic_ple.get("totalShards") or LLAMACPP_ATOMIC_SHARDS),
            } if atomic_named_variant else None,
            "backends": backend,
        }
    # A verified Mference repack and its ordinary MLX source are separate
    # folders. Link only receipts that prove the same pinned source revision
    # or source index; display-name similarity is never enough.
    ssd_groups: dict[str, list[dict[str, Any]]] = {}
    for record in records.values():
        profile = record.get("ssdStreaming")
        identity = str(profile.get("comparisonIdentity") or "") if isinstance(profile, dict) else ""
        if identity:
            ssd_groups.setdefault(identity, []).append(record)
    for identity, group in ssd_groups.items():
        route_sources: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
        for source_record in group:
            for backend_name in SSD_ARTIFACT_BACKENDS:
                capability = source_record.get("backends", {}).get(backend_name, {})
                if capability.get("runnable") is True:
                    route_sources.setdefault(backend_name, (source_record, capability))
        if len(route_sources) < 2:
            continue
        for target_record in group:
            for backend_name, (source_record, source_capability) in route_sources.items():
                target_capability = target_record.get("backends", {}).get(backend_name, {})
                if target_capability.get("runnable") is True:
                    continue
                paired = copy.deepcopy(source_capability)
                paired.update({
                    "pairedArtifact": True,
                    "pairedArtifactName": str(source_record.get("name") or "SSD model bundle"),
                    "pairedArtifactModelId": str(source_record.get("id") or ""),
                    "comparisonIdentity": identity,
                    "reason": (
                        f"Uses the verified equivalent {source_record.get('name')} artifact for "
                        f"{BACKEND_LABELS[backend_name]}."
                    ),
                })
                target_record["backends"][backend_name] = paired
            target_record["ssdStreaming"]["pairedCalibrationReady"] = True
            target_record["ssdStreaming"]["pairedEngines"] = list(SSD_ARTIFACT_BACKENDS)
    freetoken = load_freetoken_connection()
    if freetoken:
        endpoint_label = urllib.parse.urlsplit(str(freetoken["endpoint"])).netloc
        runtime_label = str(freetoken.get("server") or "FreeToken remote API")
        for remote_model_id in freetoken["models"]:
            remote_fingerprint = hashlib.sha256(json.dumps({
                "engine": "freetoken",
                "connection": freetoken["id"],
                "model": remote_model_id,
                "context": freetoken["context"],
            }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            remote_backends: dict[str, dict[str, Any]] = {}
            for engine_id, descriptor in ENGINE_ADAPTERS.items():
                if engine_id == "freetoken":
                    remote_backends[engine_id] = {
                        "runnable": True,
                        "reason": f"Advertised live by the configured FreeToken server at {endpoint_label}.",
                        "mtp": False,
                        "mtpReason": "FreeToken automatically selects fused, offload, CPU, or hybrid MoE execution on its server.",
                        "dflash": False,
                        "dflashVersion": None,
                        "dflashReason": "DFlash 2 is not a FreeToken serving mode.",
                        "kv": False,
                        "preferredAcceleration": "off",
                        "fallbackAcceleration": "off",
                        "depth": 1,
                        "depthMax": 1,
                        "agentReasoning": ["auto"],
                        "codexReasoning": ["auto"],
                        "runtimeVersion": runtime_label,
                        "benchmarkModelFingerprint": remote_fingerprint,
                        "localBenchmark": None,
                        "localBenchmarks": [],
                        "benchmarkHistoryCount": 0,
                        "remote": True,
                        "connectionId": freetoken["id"],
                    }
                else:
                    remote_backends[engine_id] = {
                        "runnable": False,
                        "reason": f"This model is advertised by FreeToken at {endpoint_label}, not present as a verified local {descriptor.label} artifact.",
                        "mtp": False,
                        "mtpReason": "No equivalent local artifact was asserted.",
                        "dflash": False,
                        "dflashVersion": None,
                        "dflashReason": "No equivalent local artifact was asserted.",
                        "kv": False,
                        "preferredAcceleration": "off",
                        "fallbackAcceleration": "off",
                        "depth": 1,
                        "depthMax": 1,
                        "agentReasoning": ["auto"],
                        "codexReasoning": ["auto"],
                        "runtimeVersion": "Not applicable",
                        "benchmarkModelFingerprint": remote_fingerprint,
                        "localBenchmark": None,
                        "localBenchmarks": [],
                        "benchmarkHistoryCount": 0,
                    }
            record_key = f"freetoken:{freetoken['id']}:{remote_model_id}"
            records[record_key] = {
                "id": "freetoken-" + hashlib.sha256(record_key.encode("utf-8", "replace")).hexdigest()[:24],
                "name": remote_model_id,
                "path": "FreeToken remote endpoint",
                "artifact": f"freetoken:{remote_fingerprint[:24]}",
                "origins": [f"FreeToken · {endpoint_label}"],
                "format": "remote api",
                "architecture": "Server managed",
                "modelType": "freetoken-remote",
                "nativeContext": int(freetoken["context"]),
                "quantization": "Server managed",
                "size": 0,
                "sizeLabel": "Remote",
                "memoryGeometry": {"ready": False, "remote": True},
                "mtpSidecarSize": 0,
                "ready": True,
                "status": "Connected",
                "mtp": {"declared": False, "integrated": False, "sidecar": False},
                "templateReasoningEfforts": [],
                "defaultSampling": {},
                "lmKey": remote_model_id,
                "remote": True,
                "remoteConnectionId": freetoken["id"],
                "remoteModelId": remote_model_id,
                "backends": remote_backends,
            }
    whallm = probe_whallm_endpoint()
    if whallm:
        source_revision = "bcd9f01ddc9cff2316eb84281bebcd5b058bddce"
        comparison_identity = hashlib.sha256(
            f"ssd-source-v1\0qwen/qwen3.8-flash-next-fp8\0revision\0{source_revision}".encode("utf-8")
        ).hexdigest()
        model_fingerprint = hashlib.sha256(json.dumps({
            "engine": "whallm", "version": whallm_version,
            "model": WHALLM_MODEL_ID, "revision": source_revision,
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        ssd_profile = {
            "version": SSD_STREAMING_CONTRACT_VERSION,
            "candidate": True, "recommended": True, "moe": True,
            "oversized": True, "qwen38FlashNext": True,
            "expertCount": 512, "nativeExpertTopK": 10,
            "weightBytes": WHALLM_MODEL_BYTES,
            "installedMemoryBytes": installed_memory,
            "weightToMemoryRatio": round(WHALLM_MODEL_BYTES / installed_memory, 4) if installed_memory else None,
            "format": "whallm-mxfp4", "reason": (
                "Whallm advertises its pinned full 512-expert Qwen3.8 Flash-Next model on loopback. "
                "This 48 GiB Mac is experimental because Whallm publishes a 64 GiB support floor."
            ),
            "sourceContract": {
                "sourceModel": "qwen/qwen3.8-flash-next-fp8",
                "proofKind": "revision", "proof": source_revision,
                "comparisonIdentity": comparison_identity,
                "verifiedForCrossFormatComparison": True,
            },
            "comparisonIdentity": comparison_identity,
            "crossFormatComparisonReady": True,
            "calibration": {
                "suite": "agentic", "engines": ["whallm"],
                "freshProcessPerEngine": False, "coldAndWarmStages": True,
                "nativeExpertRoutingRequired": True,
                "metrics": ["generationTps", "ttft", "peakMemory", "thermalState", "prefixReuse"],
            },
        }
        remote_backends: dict[str, dict[str, Any]] = {}
        for engine_id, descriptor in ENGINE_ADAPTERS.items():
            if engine_id == "whallm":
                remote_backends[engine_id] = {
                    "runnable": True,
                    "reason": (
                        "Live Whallm 1.1.x loopback route · full 512 experts · experimental on 48 GiB. "
                        "Public M5 Pro measurements cover up to 16,384 input tokens."
                    ),
                    "mtp": False, "mtpReason": (
                        "Whallm 1.1.4 exposes an optional default-off MTP prototype, but its "
                        "published formal total-time and tail-latency gates did not accept it. "
                        "The launcher keeps it unavailable until an exact local route qualification exists."
                    ),
                    "dflash": False, "dflashVersion": None,
                    "dflashReason": "DFlash is not a Whallm serving mode.",
                    "kv": False, "preferredAcceleration": "off", "fallbackAcceleration": "off",
                    "depth": 1, "depthMax": 1,
                    "agentReasoning": ["auto", "off", "low", "medium", "high", "xhigh", "max"],
                    "codexReasoning": ["auto", "off", "low", "medium", "high", "xhigh", "max"],
                    "runtimeVersion": whallm_version,
                    "benchmarkModelFingerprint": model_fingerprint,
                    "localBenchmark": None, "localBenchmarks": [], "benchmarkHistoryCount": 0,
                    "ssdStreaming": True, "ssdProfile": copy.deepcopy(ssd_profile),
                    "comparisonIdentity": comparison_identity,
                    "exactExpertRouting": True, "remote": False, "sharedServer": True,
                    "contextWindows": list(WHALLM_CONTEXT_WINDOWS),
                    "contextMaximum": max(WHALLM_CONTEXT_WINDOWS),
                    "customSampling": False,
                    "samplingReason": (
                        "Whallm's public Qwen API does not expose every custom launcher sampling field; "
                        "use the model's thinking or chat defaults."
                    ),
                }
            else:
                remote_backends[engine_id] = {
                    "runnable": False,
                    "reason": f"This model is owned by Whallm's pinned install, not a {descriptor.label} model folder.",
                    "mtp": False, "mtpReason": "No equivalent local artifact was asserted.",
                    "dflash": False, "dflashVersion": None,
                    "dflashReason": "No equivalent local artifact was asserted.",
                    "kv": False, "preferredAcceleration": "off", "fallbackAcceleration": "off",
                    "depth": 1, "depthMax": 1,
                    "agentReasoning": ["auto"], "codexReasoning": ["auto"],
                    "runtimeVersion": "Not applicable",
                    "benchmarkModelFingerprint": model_fingerprint,
                    "localBenchmark": None, "localBenchmarks": [], "benchmarkHistoryCount": 0,
                }
        record_key = f"whallm:{WHALLM_MODEL_ID}:{source_revision}"
        records[record_key] = {
            "id": "whallm-" + model_fingerprint[:24],
            "name": "Qwen3.8 Flash-Next · Whallm full experts",
            "path": "Whallm shared loopback server",
            "artifact": f"whallm:{source_revision[:24]}",
            "origins": ["Whallm · 127.0.0.1:11434"],
            "format": "Whallm MXFP4 + SSD", "architecture": "Qwen4Exp · 512 experts",
            "modelType": "whallm-qwen38-flash-next",
            "nativeContext": max(WHALLM_CONTEXT_WINDOWS),
            "quantization": "MXFP4 experts · FP8 n-gram",
            "size": WHALLM_MODEL_BYTES, "sizeLabel": display_size(WHALLM_MODEL_BYTES),
            "memoryGeometry": {"ready": False, "sharedServer": True},
            "mtpSidecarSize": 0, "ready": True, "status": "Connected",
            "mtp": {"declared": False, "integrated": False, "sidecar": False},
            "templateReasoningEfforts": ["low", "medium", "xhigh"],
            "defaultSampling": {}, "lmKey": WHALLM_MODEL_ID,
            "sharedServer": True, "remote": False,
            "remoteModelId": WHALLM_MODEL_ID,
            "ssdStreaming": ssd_profile, "backends": remote_backends,
        }
    if not whallm:
        native_whallm = whallm_runtime.discover(BINARIES.get("whallm"))
        if native_whallm:
            native_record = whallm_runtime.model_record(
                native_whallm,
                [(engine_id, descriptor.label) for engine_id, descriptor in ENGINE_ADAPTERS.items()],
                installed_memory,
            )
            records[native_record["id"]] = native_record
    slotstream_install = slotstream_runtime.discover(BINARIES.get("slotstream"))
    if slotstream_install:
        slotstream_record = slotstream_runtime.model_record(
            slotstream_install, [(key, value.label) for key, value in ENGINE_ADAPTERS.items()], installed_memory,
        )
        slot_cap = slotstream_record["backends"]["slotstream"]
        slot_history = matching_benchmark_records(
            benchmark_records, "slotstream", slot_cap["benchmarkModelFingerprint"],
            slot_cap["runtimeVersion"], slot_cap, machine_fingerprint or None,
        )
        slot_cap["benchmarkHistoryCount"] = len(slot_history)
        slot_cap["localBenchmarks"] = latest_benchmark_records_by_identity(slot_history)
        if slot_cap["localBenchmarks"]:
            slot_cap["localBenchmark"] = slot_cap["localBenchmarks"][-1]
            slot_cap["preferredAccelerationSource"] = "local-benchmark"
            slot_cap["preferredAcceleration"] = "mtp" if slot_cap["localBenchmark"].get("winner") == "mtp" else "off"
        records[slotstream_record["id"]] = slotstream_record
    splash_install = splash_runtime.inspect_install(BINARIES.get("splash"))
    if splash_install:
        splash_sources = splash_runtime.inspect_sources(
            splash_install,
            splash_runtime.source_candidates([
                *(item["path"] for item in discovered.values()),
                *splash_runtime.installed_source_roots(),
            ]),
        )
        for splash_pack in [*(splash_install.get("packs") or ()), *splash_sources]:
            splash_record = splash_runtime.model_record(
                splash_install, splash_pack,
                [(key, value.label) for key, value in ENGINE_ADAPTERS.items()],
                installed_memory,
            )
            splash_record["splash"]["draftCandidates"] = [draft["path"] for draft in dflash2_drafts]
            splash_cap = splash_record["backends"]["splash"]
            splash_history = matching_benchmark_records(
                benchmark_records, "splash", splash_cap["benchmarkModelFingerprint"],
                splash_cap["runtimeVersion"], splash_cap, machine_fingerprint or None,
            )
            splash_cap["benchmarkHistoryCount"] = len(splash_history)
            splash_cap["localBenchmarks"] = latest_benchmark_records_by_identity(splash_history)
            if splash_cap["localBenchmarks"]:
                splash_cap["localBenchmark"] = splash_cap["localBenchmarks"][-1]
            records[splash_record["id"]] = splash_record
    kolibri_install = kolibri_runtime.inspect_runtime(BINARIES.get("kolibri"))
    for scanned_model in records.values():
        kolibri_model = (
            kolibri_runtime.inspect_model(Path(scanned_model["path"]))
            if scanned_model.get("modelType") == "kolibri1" else None
        )
        scanned_model.setdefault("backends", {})["kolibri"] = kolibri_runtime.capability(kolibri_model, kolibri_install)
        if kolibri_model:
            scanned_model["kolibri"] = kolibri_model
            scanned_model["defaultOutput"] = kolibri_runtime.DEFAULT_OUTPUT
            scanned_model["outputMaximum"] = kolibri_runtime.OUTPUT_MAXIMUM
            scanned_model["defaultSampling"] = {"temperature": 1.0, "top_p": 0.97, "top_k": 128}
            for other, other_cap in scanned_model["backends"].items():
                if other != "kolibri":
                    other_cap["runnable"] = False
                    other_cap["reason"] = "Use Kolibri SSD to run this Q6 checkpoint with bounded expert offloading."
        capabilities = scanned_model.get("backends")
        if not isinstance(capabilities, dict):
            continue
        for backend_name, capability in capabilities.items():
            if not isinstance(capability, dict):
                continue
            descriptor = ENGINE_ADAPTERS.get(backend_name)
            installed = bool(descriptor and descriptor.public().get("installed") is True)
            compatible = bool(
                scanned_model.get("ready") is True
                and capability.get("runnable") is True
            )
            capability["performanceEvidence"] = route_performance_evidence(
                scanned_model, backend_name, capability,
            )
            capability["hostSupport"] = route_host_support(
                scanned_model, backend_name, capability,
                runtime_installed=installed,
                artifact_compatible=compatible,
            )

    result = list(records.values())
    result.sort(key=lambda item: (not item["ready"], item["name"].lower()))
    return result


def model_library_inventory(models: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a read-only compatibility report from the canonical model scan.

    This deliberately performs no launches, downloads, model loads, or state
    writes. Compatibility remains derived from the same adapter registry,
    support matrix, and scanner capabilities used by launch validation.
    """
    engine_descriptors = {
        engine_id: descriptor.public()
        for engine_id, descriptor in ENGINE_ADAPTERS.items()
    }
    surface_descriptors = {
        surface_id: descriptor.public()
        for surface_id, descriptor in CLIENT_ADAPTERS.items()
    }
    reports: list[dict[str, Any]] = []

    for source in models:
        model = source if isinstance(source, dict) else {}
        model_ready = model.get("ready") is True
        remote_model = model.get("remote") is True
        backend_capabilities = model.get("backends")
        if not isinstance(backend_capabilities, dict):
            backend_capabilities = {}
        engine_reports: list[dict[str, Any]] = []
        launchable_routes = 0
        launchable_engines = 0
        accelerator_count = 0
        evidence_count = 0

        for engine_id, descriptor in ENGINE_ADAPTERS.items():
            public_engine = engine_descriptors[engine_id]
            capability = backend_capabilities.get(engine_id)
            if not isinstance(capability, dict):
                capability = {}
            runtime_installed = public_engine["installed"] is True
            artifact_compatible = model_ready and capability.get("runnable") is True
            runnable = runtime_installed and artifact_compatible
            qualification_policy = (
                capability.get("nativeContract", {}).get("qualification", {}).get("launcher", {})
                if engine_id == "freetoken" else {}
            )
            qualification_readiness = str(qualification_policy.get("readiness") or "")
            performance_evidence = route_performance_evidence(
                model, engine_id, capability,
            )
            host_support = route_host_support(
                model, engine_id, capability,
                runtime_installed=runtime_installed,
                artifact_compatible=artifact_compatible,
            )
            experimental = host_support["state"] == "experimental"
            if runnable:
                launchable_engines += 1

            if not runtime_installed:
                engine_status = "runtime-missing"
                engine_reason = f"{descriptor.label} is not installed."
            elif not artifact_compatible:
                engine_status = "incompatible"
                engine_reason = str(
                    capability.get("reason")
                    or model.get("status")
                    or f"This artifact is not compatible with {descriptor.label}."
                )
            else:
                engine_status = "experimental" if experimental else "ready"
                engine_reason = str(capability.get("reason") or "Ready")

            fixed_uzu_route = bool(
                engine_id == "uzu"
                and capability.get("runtimeManagedAcceleration") == "DFlash + Weaver"
            )
            modes = [{
                "id": "ar",
                "label": benchmark_public_mode_label(engine_id, "ar"),
                "kind": "fixed-route" if fixed_uzu_route else "baseline",
                "available": artifact_compatible,
                "detail": (
                    "Runtime-managed bundled DFlash draft and Weaver verification tree"
                    if fixed_uzu_route else "Standard autoregressive decoding"
                ),
            }]
            if model.get("uzuNative") is True and engine_id != "uzu":
                modes = []
            if fixed_uzu_route and artifact_compatible:
                accelerator_count += 1
            if capability.get("mtp") is True:
                modes.append({
                    "id": "mtp", "label": "MTP", "kind": "accelerator",
                    "available": artifact_compatible,
                    "detail": str(capability.get("mtpReason") or "Verified MTP route"),
                })
                accelerator_count += 1
            if engine_id == "omlx" and capability.get("dflash") is True:
                modes.append({
                    "id": "dflash2", "label": "DFlash 2", "kind": "accelerator",
                    "available": artifact_compatible,
                    "detail": str(capability.get("dflashReason") or "Exact DFlash 2 pair"),
                })
                accelerator_count += 1
            if engine_id == "omlx" and capability.get("anePrefill") is True:
                modes.append({
                    "id": "ane-prefill", "label": "ANE prefill", "kind": "accelerator",
                    "available": artifact_compatible,
                    "detail": str(capability.get("aneReason") or "Locally verified ANE prefill split"),
                })
                accelerator_count += 1

            surface_reports: list[dict[str, Any]] = []
            for surface_id, surface_descriptor in CLIENT_ADAPTERS.items():
                public_surface = surface_descriptors[surface_id]
                surface_installed = public_surface["installed"] is True
                matrix = resolved_client_support(engine_id, surface_id, capability)
                matrix_supported = matrix.get("supported") is True
                reasoning_key = "codexReasoning" if surface_id == "codex" else "agentReasoning"
                reasoning = capability.get(reasoning_key)
                reasoning_ready = isinstance(reasoning, list) and bool(reasoning)
                supported = bool(
                    runnable and surface_installed and matrix_supported and reasoning_ready
                )
                if supported:
                    launchable_routes += 1
                    route_reason = str(matrix.get("reason") or "Compatible")
                elif not runtime_installed:
                    route_reason = f"Install {descriptor.label} first."
                elif not artifact_compatible:
                    route_reason = engine_reason
                elif not surface_installed:
                    route_reason = f"{surface_descriptor.label} is not installed."
                elif not matrix_supported:
                    route_reason = str(matrix.get("reason") or "This protocol route is unsupported.")
                elif not reasoning_ready:
                    route_reason = "No enforceable reasoning mode is advertised for this route."
                else:
                    route_reason = "This route is unavailable."
                surface_reports.append({
                    "id": surface_id,
                    "label": surface_descriptor.label,
                    "installed": surface_installed,
                    "builtIn": public_surface["builtIn"],
                    "protocol": surface_descriptor.protocol,
                    "supported": supported,
                    "reason": route_reason,
                    "reasoning": list(reasoning) if isinstance(reasoning, list) else [],
                })

            history_count = capability.get("benchmarkHistoryCount")
            if not isinstance(history_count, int) or isinstance(history_count, bool) or history_count < 0:
                history_count = 0
            benchmark = capability.get("localBenchmark")
            if not isinstance(benchmark, dict):
                benchmark = None
            if benchmark and history_count == 0:
                history_count = 1
            evidence_count += history_count
            evidence = {
                "savedRuns": history_count,
                "latest": None if not benchmark else {
                    "winner": str(benchmark.get("winner") or ""),
                    "winnerLabel": benchmark_public_mode_label(
                        engine_id, str(benchmark.get("winner") or "ar")
                    ),
                    "suite": str(benchmark.get("suite") or ""),
                    "createdAt": str(benchmark.get("createdAt") or ""),
                    "recommendation": str(benchmark.get("recommendation") or ""),
                    "qualityPassed": benchmark.get("qualityPassed") is True,
                },
            }
            engine_reports.append({
                "id": engine_id,
                "label": descriptor.label,
                "protocol": descriptor.protocol,
                "runtimeInstalled": runtime_installed,
                "artifactCompatible": artifact_compatible,
                "runnable": runnable,
                "experimental": experimental,
                "status": engine_status,
                "reason": engine_reason,
                "runtimeVersion": str(capability.get("runtimeVersion") or ""),
                "performanceEvidence": performance_evidence,
                "hostSupport": host_support,
                "qualification": {
                    "readiness": qualification_readiness,
                    "realCheckpointVerified": capability.get("realCheckpointVerified") is True,
                    "largeDownloadRecommended": qualification_policy.get("large_download_recommended") is True,
                } if engine_id == "freetoken" and capability.get("native") is True else None,
                "modes": modes,
                "surfaces": surface_reports,
                "evidence": evidence,
            })

        checks = [{
            "id": "artifact",
            "label": "Served model" if remote_model else "Artifact completeness",
            "state": "pass" if model_ready else "blocked",
            "detail": (
                "Advertised by the connected FreeToken server during model discovery."
                if remote_model and model_ready else
                str(model.get("status") or ("Ready" if model_ready else "Incomplete artifact"))
            ),
        }, {
            "id": "engines",
            "label": "Connected engine" if remote_model else "Installed engines",
            "state": "pass" if launchable_engines else "blocked",
            "detail": (
                f"{launchable_engines} connected engine route is available."
                if remote_model and launchable_engines else
                "The connected FreeToken route is unavailable."
                if remote_model else
                f"{launchable_engines} installed engine{'s' if launchable_engines != 1 else ''} can load this artifact."
                if launchable_engines else "No installed engine can load this artifact."
            ),
        }, {
            "id": "surfaces",
            "label": "Launchable work surfaces",
            "state": "pass" if launchable_routes else "blocked",
            "detail": (
                f"{launchable_routes} engine/surface route{'s' if launchable_routes != 1 else ''} are ready."
                if launchable_routes else "No installed engine and work-surface route is ready."
            ),
        }]
        if remote_model:
            checks.append({
                "id": "performance", "label": "Performance reporting",
                "state": "pass",
                "detail": "Live TPS is reported for this connected route; remote-host and network time stay out of Mac-only Benchmark Lab.",
            })
        elif accelerator_count == 0:
            checks.append({
                "id": "acceleration", "label": "Acceleration evidence",
                "state": "advisory",
                "detail": (
                    "The fixed DFlash + Weaver route is not currently runnable."
                    if model.get("uzuNative") is True else
                    "No verified speculative accelerator is available; standard AR remains valid."
                ),
            })
        elif evidence_count == 0:
            checks.append({
                "id": "acceleration", "label": "Acceleration evidence",
                "state": "advisory",
                "detail": f"{accelerator_count} accelerator route{'s' if accelerator_count != 1 else ''} are available, but none has matching saved benchmark evidence.",
            })
        else:
            checks.append({
                "id": "acceleration", "label": "Acceleration evidence",
                "state": "pass",
                "detail": f"{evidence_count} matching saved benchmark run{'s' if evidence_count != 1 else ''} cover available local routes.",
            })

        if any(check["state"] == "blocked" for check in checks):
            doctor_state = "blocked"
            if not model_ready:
                headline = "Finish or repair this artifact before launch."
                next_action = "Rescan after every required weight shard is present."
            elif not launchable_engines:
                headline = "No installed engine can load this model yet."
                next_action = "Review the engine reasons below, then install or select a compatible runtime."
            else:
                headline = "The model loads, but no complete work-surface route is ready."
                next_action = "Install a compatible agent launcher or use the built-in Chat route where supported."
        elif any(check["state"] == "advisory" for check in checks):
            doctor_state = "attention"
            headline = "Usable now, with an optimisation advisory."
            next_action = (
                "Run Benchmark Lab before preferring an accelerator automatically."
                if accelerator_count else
                "Use the fixed DFlash + Weaver route after its runtime checks pass."
                if model.get("uzuNative") is True else
                "Use standard AR; no speculative speedup is claimed for this artifact."
            )
        else:
            doctor_state = "ready"
            headline = (
                "Ready on the connected FreeToken route."
                if remote_model else "Ready across installed local routes."
            )
            next_action = (
                "Choose FreeToken below to put this served model into the launcher without starting it. Reconnect to refresh the server's model list."
                if remote_model else
                "Choose an engine below to put this model into the launcher without starting it."
            )

        reports.append({
            "id": str(model.get("id") or ""),
            "name": str(model.get("name") or "Unnamed model"),
            "path": str(model.get("path") or ""),
            "artifact": str(model.get("artifact") or ""),
            "origins": [str(item) for item in (model.get("origins") or [])],
            "format": str(model.get("format") or "unknown"),
            "architecture": str(model.get("architecture") or "unknown"),
            "modelType": str(model.get("modelType") or "unknown"),
            "nativeContext": model.get("nativeContext") if isinstance(model.get("nativeContext"), int) else None,
            "quantization": str(model.get("quantization") or "Unknown"),
            "size": model.get("size") if isinstance(model.get("size"), int) else 0,
            "sizeLabel": str(model.get("sizeLabel") or display_size(model.get("size") or 0)),
            "ready": model_ready,
            "status": str(model.get("status") or "Unknown"),
            "engines": engine_reports,
            "counts": {
                "launchableEngines": launchable_engines,
                "launchableRoutes": launchable_routes,
                "accelerators": accelerator_count,
                "evidenceRuns": evidence_count,
            },
            "doctor": {
                "state": doctor_state,
                "headline": headline,
                "nextAction": next_action,
                "checks": checks,
            },
        })

    summary = {
        "models": len(reports),
        "ready": sum(item["doctor"]["state"] == "ready" for item in reports),
        "attention": sum(item["doctor"]["state"] == "attention" for item in reports),
        "blocked": sum(item["doctor"]["state"] == "blocked" for item in reports),
        "launchableRoutes": sum(item["counts"]["launchableRoutes"] for item in reports),
    }
    return {
        "schemaVersion": MODEL_LIBRARY_SCHEMA_VERSION,
        "readOnly": True,
        "summary": summary,
        "models": reports,
        "engines": list(engine_descriptors.values()),
        "workSurfaces": list(surface_descriptors.values()),
    }
