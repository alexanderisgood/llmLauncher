"""Qwen4 PLE geometry and exact indexed SSD storage contracts.

Filesystem readers and runtime predicates are explicit dependencies. This
module owns the tensor/layout proof and deterministic fingerprints, while the
controller owns runtime selection, current memory admission and launch state.
It never imports the controller or materializes model weights.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

Inventory = tuple[bool, dict[str, dict[str, Any]], list[dict[str, Any]]]

_QWEN4_PLE_INVENTORY_SCHEMA_VERSION = 1
_QWEN4_PLE_MARKER = ".ple.ple_embedding.ngram_embedding."
_QWEN4_PLE_DENSE_DTYPES = frozenset({"BF16", "F16", "F32", "F8_E4M3"})
_QWEN4_PLE_AFFINE_PARAMETER_DTYPES = frozenset({"BF16", "F16", "F32"})


def _qwen4_ple_is_prime(value: int) -> bool:
    """Deterministically test bounded 64-bit PLE vocabulary candidates."""
    if value < 2:
        return False
    small_primes = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    for prime in small_primes:
        if value % prime == 0:
            return value == prime
    divisor = value - 1
    shifts = 0
    while divisor % 2 == 0:
        shifts += 1
        divisor //= 2
    # This base set is deterministic for every unsigned 64-bit integer.
    for base in (2, 325, 9_375, 28_178, 450_775, 9_780_504, 1_795_265_022):
        if base % value == 0:
            continue
        candidate = pow(base, divisor, value)
        if candidate in {1, value - 1}:
            continue
        for _ in range(shifts - 1):
            candidate = pow(candidate, 2, value)
            if candidate == value - 1:
                break
        else:
            return False
    return True


def _qwen4_ple_nth_prime_after(start: int, count: int) -> int:
    candidate = start
    for _ in range(count):
        candidate += 1
        while not _qwen4_ple_is_prime(candidate):
            candidate += 1
    return candidate


def _qwen4_ple_primes_after(start: int, count: int) -> list[int]:
    """Enumerate the same bounded prime sequence once for all PLE heads."""
    values: list[int] = []
    candidate = start
    for _ in range(count):
        candidate += 1
        while not _qwen4_ple_is_prime(candidate):
            candidate += 1
        values.append(candidate)
    return values


def _qwen4_ple_geometry(config: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """Reproduce the bounded Qwen4 PLE constructor geometry used by oMLX."""
    text = config.get("text_config") if isinstance(config.get("text_config"), dict) else {}

    def integer(
        key: str, default: int | None = None, *, minimum: int = 1, maximum: int,
    ) -> int | None:
        value = text.get(key, default)
        if (
            not isinstance(value, int) or isinstance(value, bool)
            or not minimum <= value <= maximum
        ):
            return None
        return value

    layer_count = integer("num_hidden_layers", maximum=4_096)
    hidden_size = integer("hidden_size", maximum=1_000_000)
    vocab_size = integer("vocab_size", maximum=10_000_000)
    ple_embed_dim = (
        hidden_size
        if text.get("ple_embed_dim") is None
        else integer("ple_embed_dim", maximum=1_000_000)
    )
    ngram_size = integer("ngram_size", 3, minimum=2, maximum=64)
    heads_per_ngram = integer("heads_per_ngram", 8, maximum=128)
    ngram_vocab_base = integer(
        "ngram_vocab_size_base", 20_000_000, minimum=2, maximum=2_147_483_647,
    )
    divisible_by = integer(
        "make_ngram_vocab_size_divisible_by", 128, maximum=65_536,
    )
    split_parts = integer("split_ngram_parts", 128, maximum=4_096)
    seed = text.get("seed", 1_234)
    eos_token_id = text.get("eos_token_id")
    ple_layer_ids = text.get("ple_layer_ids")
    if any(value is None for value in (
        layer_count, hidden_size, vocab_size, ple_embed_dim, ngram_size, heads_per_ngram,
        ngram_vocab_base, divisible_by, split_parts,
    )):
        return None, "The Qwen4 PLE geometry contains missing or unsafe integer bounds."
    assert layer_count is not None
    assert hidden_size is not None
    assert vocab_size is not None
    assert ple_embed_dim is not None
    assert ngram_size is not None
    assert heads_per_ngram is not None
    assert ngram_vocab_base is not None
    assert divisible_by is not None
    assert split_parts is not None
    if (
        not isinstance(seed, int) or isinstance(seed, bool)
        or not -(2**63) <= seed < 2**63
    ):
        return None, "The Qwen4 PLE hashing seed is missing or unsafe."
    eos_ids = eos_token_id if isinstance(eos_token_id, list) else [eos_token_id]
    if (
        not eos_ids
        or any(
            not isinstance(value, int) or isinstance(value, bool)
            or not 0 <= value < vocab_size
            for value in eos_ids
        )
    ):
        return None, "The Qwen4 PLE end-of-sequence token contract is invalid."
    if (
        not isinstance(ple_layer_ids, list) or not ple_layer_ids
        or any(
            not isinstance(value, int) or isinstance(value, bool)
            or not 1 <= value <= layer_count
            for value in ple_layer_ids
        )
    ):
        return None, "The checkpoint does not declare a valid one-indexed Qwen4 PLE layer list."
    normalized_layers = sorted(set(ple_layer_ids))
    layer_types = text.get("layer_types")
    if layer_types is None:
        interval = integer("full_attention_interval", 4, maximum=4_096)
        if interval is None:
            return None, "The Qwen4 attention interval is invalid."
        normalized_types = [
            "linear_attention" if (index + 1) % interval else "qwen_sparse_attention"
            for index in range(layer_count)
        ]
    elif (
        not isinstance(layer_types, list) or len(layer_types) != layer_count
        or any(not isinstance(value, str) for value in layer_types)
    ):
        return None, "The Qwen4 layer-type list does not match the decoder depth."
    else:
        normalized_types = [
            "qwen_sparse_attention" if value == "full_attention" else value
            for value in layer_types
        ]
        if any(value not in {"linear_attention", "qwen_sparse_attention"} for value in normalized_types):
            return None, "The Qwen4 layer-type list contains an unsupported attention kind."
    if any(normalized_types[layer_id - 1] != "linear_attention" for layer_id in normalized_layers):
        return None, "Qwen4 PLE is only valid on declared linear-attention layers."

    ngram_heads = (ngram_size - 1) * heads_per_ngram
    if ngram_heads <= 0 or ngram_heads > 1_024 or ple_embed_dim % ngram_heads:
        return None, "The Qwen4 PLE embedding width is incompatible with its N-gram heads."
    if len(normalized_layers) * ngram_heads > 4_096:
        return None, "The Qwen4 PLE head count exceeds the launcher's bounded verifier."
    shard_width = ple_embed_dim // ngram_heads
    vocabulary_sequence = _qwen4_ple_primes_after(
        ngram_vocab_base - 1, len(normalized_layers) * ngram_heads,
    )
    layers: list[dict[str, Any]] = []
    for ple_index, layer_id in enumerate(normalized_layers):
        head_vocab_sizes = vocabulary_sequence[
            ple_index * ngram_heads:(ple_index + 1) * ngram_heads
        ]
        total_vocab = sum(head_vocab_sizes)
        padded_vocab = ((total_vocab + divisible_by - 1) // divisible_by) * divisible_by
        if split_parts > padded_vocab:
            return None, "The Qwen4 PLE split count exceeds its padded N-gram vocabulary."
        base_rows, extra_rows = divmod(padded_vocab, split_parts)
        layers.append({
            "layerId": layer_id,
            "layerIndex": layer_id - 1,
            "pleIndex": ple_index,
            "paddedVocabulary": padded_vocab,
            "shardRows": [
                base_rows + (1 if shard_index < extra_rows else 0)
                for shard_index in range(split_parts)
            ],
        })
    return {
        "vocabSize": vocab_size,
        "seed": seed,
        "eosTokenIds": eos_ids,
        "pleEmbedDim": ple_embed_dim,
        "ngramHeads": ngram_heads,
        "shardWidth": shard_width,
        "splitParts": split_parts,
        "layers": layers,
    }, ""


OMLX_EXPERT_OFFLOAD_VERSION = "0.7.0.dev2"
OMLX_EXPERT_RESIDENT_PERCENTAGES = (12.5, 25, 37.5, 50, 62.5, 75)


def qwen4_expert_offload_profile(
    path: Path, config: dict[str, Any], ple: dict[str, Any], version: str, *,
    exact_version: Callable[[str, str], bool],
    inventory_reader: Callable[[Path], Inventory],
) -> dict[str, Any]:
    """Validate every backbone expert's packed layout without materializing weights."""
    base = {"supported": False, "expertBytes": 0, "reason": "Expert SSD offload requires oMLX 0.7.0.dev2 and a verified Qwen Flash checkpoint."}
    if not exact_version(version, OMLX_EXPERT_OFFLOAD_VERSION) or not ple.get("supported"):
        return base
    valid, tensors, _ = inventory_reader(path)
    text = config.get("text_config", config)
    quant = config.get("quantization", text.get("quantization"))
    values = [text.get(k) for k in ("num_experts", "num_hidden_layers", "hidden_size", "moe_intermediate_size")]
    if not valid or not isinstance(quant, dict) or any(type(v) is not int or not 0 < v <= 65536 for v in values):
        return base
    experts, layers, hidden, intermediate = values
    expert_bytes = 0
    for layer in range(layers):
        for projection in ("gate_proj", "up_proj", "down_proj"):
            key = f"language_model.model.layers.{layer}.mlp.switch_mlp.{projection}"
            q = quant.get(key, quant)
            if not isinstance(q, dict):
                return base
            bits, group = q.get("bits", 4), q.get("group_size", 64)
            output, width = (hidden, intermediate) if projection == "down_proj" else (intermediate, hidden)
            if (q.get("mode", "affine") != "affine" or type(bits) is not int or bits not in (2, 3, 4, 5, 6, 8)
                    or type(group) is not int or group <= 0 or width % group or width * bits % 32
                    or key + ".bias" in tensors):
                return base
            for field in ("weight", "scales", "biases"):
                tensor = tensors.get(key + "." + field, {})
                shape = [experts, output, width * bits // 32 if field == "weight" else width // group]
                if tensor.get("shape") != shape or tensor.get("dtype") not in ({"U32"} if field == "weight" else {"F16", "BF16", "F32"}):
                    return base
                begin, end = tensor["data_offsets"]
                expert_bytes += end - begin
    return {"supported": True, "expertBytes": expert_bytes, "expertCount": experts,
            "layers": layers, "defaultResidentPercent": 25, "defaultMemoryGB": 41,
            "fingerprint": ple["inventoryFingerprint"], "runtimeVersion": version,
            "reason": "Full expert routing with an SSD-backed cache; MTP and DFlash are disabled."}


def qwen4_ple_profile(
    path: Path, config: dict[str, Any], ready: bool, runtime_version: str, *,
    is_qwen_config: Callable[[dict[str, Any]], bool],
    version_at_least: Callable[[str, str], bool],
    json_reader: Callable[[Path], tuple[dict[str, Any], dict[str, Any]]],
    inventory_reader: Callable[[Path], Inventory],
    geometry_reader: Callable[[dict[str, Any]], tuple[dict[str, Any] | None, str]],
) -> dict[str, Any]:
    """Prove Qwen4 PLE mmap eligibility from the exact indexed checkpoint."""
    base = {
        "supported": False,
        "storage": "unavailable",
        "checkpointBytes": 0,
        "pleBytes": 0,
        "rawResidentBytes": 0,
        "residentBytes": 0,
        "fullResidentBytes": 0,
        "runtimeMinimum": "0.6.4",
        "runtimeVersion": runtime_version,
        "inventorySchema": _QWEN4_PLE_INVENTORY_SCHEMA_VERSION,
        "inventoryFingerprint": "",
        "sourceFingerprint": "",
        "configFingerprint": "",
        "indexFingerprint": "",
        "index": None,
        "storageSource": None,
        "shardCount": 0,
        "tensorCount": 0,
        "pleLayerCount": 0,
        "pleShardCount": 0,
        "pleTensorCount": 0,
        "pleLayouts": [],
        # Kept for response-schema compatibility. Direct oMLX mmap deliberately
        # has no publisher sidecar manifest.
        "manifest": None,
        "reason": "A complete indexed Qwen4-Exp checkpoint is required.",
    }
    if not is_qwen_config(config):
        base["reason"] = "This checkpoint is not the root qwen4_exp architecture."
        return base
    if not ready:
        return base
    if not version_at_least(runtime_version, "0.6.4"):
        base["reason"] = "Qwen4 PLE SSD mmap requires oMLX 0.6.4 or newer."
        return base
    config_document, config_source = json_reader(path / "config.json")
    if not config_document or config_document != config:
        base["reason"] = "The Qwen4 config changed, contains duplicate keys, or could not be read safely."
        return base
    index_name = "model.safetensors.index.json"
    valid, tensors, shard_manifest = inventory_reader(path)
    if not valid:
        base["reason"] = "The complete indexed safetensors layout could not be verified."
        return base
    index_document, index_source = json_reader(path / index_name)
    weight_map = index_document.get("weight_map")
    if not isinstance(weight_map, dict) or not weight_map:
        base["reason"] = "Qwen4 direct PLE mmap requires a non-empty safetensors weight index."
        return base
    if (
        set(weight_map) != set(tensors)
        or set(weight_map.values()) != {str(item["name"]) for item in shard_manifest}
        or any(tensors[name]["shard"] != weight_map[name] for name in tensors)
    ):
        base["reason"] = "The Qwen4 safetensors index changed during structural validation."
        return base
    geometry, geometry_reason = geometry_reader(config_document)
    if geometry is None:
        base["reason"] = geometry_reason
        return base

    storage_names: set[str] = set()
    allowed_related_names: set[str] = set()
    layouts: set[str] = set()
    ple_bytes = 0
    ple_shards = 0

    def tensor_bytes(metadata: dict[str, Any]) -> int:
        return int(metadata["data_offsets"][1]) - int(metadata["data_offsets"][0])

    for layer in geometry["layers"]:
        layer_index = int(layer["layerIndex"])
        prefixes = (
            f"model.language_model.layers.{layer_index}.ple.ple_embedding.ngram_embedding",
            f"language_model.model.layers.{layer_index}.ple.ple_embedding.ngram_embedding",
        )
        scale_names = [f"{prefix}.weight_scale" for prefix in prefixes if f"{prefix}.weight_scale" in weight_map]
        if len(scale_names) > 1:
            base["reason"] = f"Qwen4 PLE layer {layer_index} declares duplicate shared scale aliases."
            return base
        if scale_names:
            scale_metadata = tensors[scale_names[0]]
            if scale_metadata.get("shape") != [1] or scale_metadata.get("dtype") not in _QWEN4_PLE_AFFINE_PARAMETER_DTYPES:
                base["reason"] = f"Qwen4 PLE layer {layer_index} has an invalid shared FP8 scale."
                return base
            allowed_related_names.add(scale_names[0])

        for shard_index, expected_rows in enumerate(layer["shardRows"]):
            bases = (
                *(f"{prefix}.shard_{shard_index}" for prefix in prefixes),
                *(f"{prefix}.shards.{shard_index}" for prefix in prefixes),
            )
            matched = [candidate for candidate in bases if f"{candidate}.weight" in weight_map]
            if len(matched) != 1:
                base["reason"] = (
                    f"Qwen4 PLE layer {layer_index} shard {shard_index} is missing or has duplicate aliases."
                )
                return base
            tensor_base = matched[0]
            weight_name = f"{tensor_base}.weight"
            scales_name = f"{tensor_base}.scales"
            biases_name = f"{tensor_base}.biases"
            weight = tensors[weight_name]
            shape = weight.get("shape")
            if not isinstance(shape, list) or len(shape) != 2 or shape[0] != expected_rows:
                base["reason"] = f"Qwen4 PLE tensor {weight_name} has an unexpected row shape."
                return base
            has_scales = scales_name in weight_map
            has_biases = biases_name in weight_map
            current_names = {weight_name}
            if not has_scales and not has_biases:
                if shape[1] != geometry["shardWidth"] or weight.get("dtype") not in _QWEN4_PLE_DENSE_DTYPES:
                    base["reason"] = f"Qwen4 PLE tensor {weight_name} is not a supported dense mmap row table."
                    return base
                layouts.add(f"dense-{str(weight.get('dtype')).lower()}")
            else:
                if not has_scales or not has_biases:
                    base["reason"] = f"Qwen4 PLE affine shard {tensor_base} has incomplete scales or biases."
                    return base
                scales = tensors[scales_name]
                biases = tensors[biases_name]
                scale_shape = scales.get("shape")
                if (
                    weight.get("dtype") != "U32"
                    or not isinstance(scale_shape, list) or len(scale_shape) != 2
                    or scale_shape != biases.get("shape")
                    or scale_shape[0] != expected_rows or scale_shape[1] <= 0
                    or scales.get("dtype") not in _QWEN4_PLE_AFFINE_PARAMETER_DTYPES
                    or biases.get("dtype") not in _QWEN4_PLE_AFFINE_PARAMETER_DTYPES
                    or scales.get("dtype") != biases.get("dtype")
                ):
                    base["reason"] = f"Qwen4 PLE affine shard {tensor_base} has incompatible parameter tensors."
                    return base
                dims = int(geometry["shardWidth"])
                if dims % int(scale_shape[1]):
                    base["reason"] = f"Qwen4 PLE affine shard {tensor_base} has a non-integral group size."
                    return base
                group_size = dims // int(scale_shape[1])
                packed_bits = int(shape[1]) * 32
                if packed_bits % dims:
                    base["reason"] = f"Qwen4 PLE affine shard {tensor_base} has a non-integral packed precision."
                    return base
                bits = packed_bits // dims
                if (
                    bits not in {2, 3, 4, 5, 6, 8}
                    or group_size not in {32, 64, 128}
                    or dims % group_size
                    or int(shape[1]) != dims * bits // 32
                ):
                    base["reason"] = f"Qwen4 PLE affine shard {tensor_base} uses an unsupported mmap layout."
                    return base
                layouts.add(f"affine-q{bits}-g{group_size}")
                current_names.update({scales_name, biases_name})
            storage_names.update(current_names)
            allowed_related_names.update(current_names)
            ple_bytes += sum(tensor_bytes(tensors[name]) for name in current_names)
            ple_shards += 1

    related_names = {name for name in tensors if _QWEN4_PLE_MARKER in name}
    if related_names != allowed_related_names:
        base["reason"] = "The indexed checkpoint contains unexpected or unclaimed Qwen4 PLE storage tensors."
        return base
    checkpoint_bytes = sum(int(item["size"]) for item in shard_manifest)
    if ple_bytes <= 0 or ple_bytes >= checkpoint_bytes:
        base["reason"] = "No valid indexed PLE N-gram tensor table was found."
        return base

    deterministic_shards = [
        {
            "name": str(item["name"]),
            "size": int(item["size"]),
            "headerSha256": str(item["header_sha256"]),
        }
        for item in sorted(shard_manifest, key=lambda value: str(value["name"]))
    ]
    deterministic_ple = [
        {
            "name": name,
            "shard": str(tensors[name]["shard"]),
            "dtype": str(tensors[name]["dtype"]),
            "shape": list(tensors[name]["shape"]),
            "dataOffsets": list(tensors[name]["data_offsets"]),
        }
        for name in sorted(allowed_related_names)
    ]
    index_encoded = json.dumps(
        index_document, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    index_fingerprint = hashlib.sha256(index_encoded).hexdigest()
    config_encoded = json.dumps(
        config_document, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    config_fingerprint = hashlib.sha256(config_encoded).hexdigest()
    inventory_identity = {
        "schema": _QWEN4_PLE_INVENTORY_SCHEMA_VERSION,
        "configFingerprint": config_fingerprint,
        "index": index_document,
        "shards": deterministic_shards,
        "pleGeometry": geometry,
        "pleTensors": deterministic_ple,
    }
    inventory_fingerprint = hashlib.sha256(json.dumps(
        inventory_identity, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    source_identity = {
        "schema": _QWEN4_PLE_INVENTORY_SCHEMA_VERSION,
        "config": config_source,
        "index": index_source,
        "shards": [
            {
                key: item[key]
                for key in (
                    "name", "size", "device", "inode", "mtime_ns", "ctime_ns",
                    "link_device", "link_inode", "link_size", "link_mode",
                    "link_mtime_ns", "link_ctime_ns", "link_target",
                )
            }
            for item in sorted(shard_manifest, key=lambda value: str(value["name"]))
        ],
    }
    source_fingerprint = hashlib.sha256(json.dumps(
        source_identity, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    raw_resident = checkpoint_bytes - ple_bytes
    base.update({
        "supported": True,
        "storage": "mmap",
        "storageSource": "indexed-safetensors",
        "checkpointBytes": checkpoint_bytes,
        "pleBytes": ple_bytes,
        "rawResidentBytes": raw_resident,
        "residentBytes": int(raw_resident * 1.05),
        "fullResidentBytes": int(checkpoint_bytes * 1.05),
        "inventoryFingerprint": inventory_fingerprint,
        "sourceFingerprint": source_fingerprint,
        "configFingerprint": config_fingerprint,
        "indexFingerprint": index_fingerprint,
        "index": index_name,
        "shardCount": len(shard_manifest),
        "tensorCount": len(tensors),
        "pleLayerCount": len(geometry["layers"]),
        "pleShardCount": ple_shards,
        "pleTensorCount": len(storage_names),
        "pleLayouts": sorted(layouts),
        "reason": "oMLX will memory-map the exact indexed PLE N-gram tensors read-only from SSD and keep the remaining checkpoint resident.",
    })
    return base
