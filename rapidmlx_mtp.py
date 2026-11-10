"""Passive native-MTP discovery for Rapid-MLX 0.16.9.

Only safetensors headers are read. The native injector remains responsible for
the complete model-specific tensor/shape validation when the engine starts.
No MLX imports, checkpoint execution, downloads, or tensor materialization.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import struct
from typing import Any


_NATIVE_FAMILIES = {"qwen3_5", "qwen3_5_moe", "hy_v3", "qwen4_exp"}
_MAX_HEADER_BYTES = 64 * 1024**2
_ITEM_BYTES = {"BOOL": 1, "U8": 1, "I8": 1, "I16": 2, "U16": 2,
               "F16": 2, "BF16": 2, "I32": 4, "U32": 4, "F32": 4,
               "F64": 8, "I64": 8, "U64": 8, "F8_E4M3": 1, "F8_E5M2": 1}


def _identity(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {"path": str(path), "device": stat.st_dev, "inode": stat.st_ino,
            "size": stat.st_size, "mtimeNs": stat.st_mtime_ns,
            "ctimeNs": stat.st_ctime_ns}


def _inside(root: Path, name: str) -> Path:
    if (not isinstance(name, str) or not name or Path(name).is_absolute()
            or ".." in Path(name).parts):
        raise ValueError("MTP index contains an invalid local filename")
    # HF snapshots deliberately symlink weight leaves into sibling blobs/.
    # Validate index names lexically, then stat/read the linked regular data;
    # resolving here would reject every ordinary cached HF checkpoint.
    path = root / name
    if not path.is_file():
        raise ValueError("MTP tensor file is missing from the checkpoint directory")
    return path


def _header(path: Path) -> dict[str, dict[str, Any]]:
    before = _identity(path)
    with path.open("rb") as stream:
        raw_size = stream.read(8)
        if len(raw_size) != 8:
            raise ValueError("MTP safetensors header is truncated")
        size = struct.unpack("<Q", raw_size)[0]
        if not 2 <= size <= _MAX_HEADER_BYTES or 8 + size > before["size"]:
            raise ValueError("MTP safetensors header has an invalid size")
        raw = stream.read(size)
    metadata = json.loads(raw)
    if not isinstance(metadata, dict):
        raise ValueError("MTP safetensors header is not an object")
    tensors = {}
    for key, item in metadata.items():
        if key == "__metadata__":
            continue
        if not isinstance(key, str) or not isinstance(item, dict):
            raise ValueError("Invalid MTP tensor metadata")
        shape, offsets, dtype = item.get("shape"), item.get("data_offsets"), item.get("dtype")
        if (not isinstance(shape, list)
                or any(isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in shape)
                or not isinstance(offsets, list) or len(offsets) != 2
                or any(isinstance(n, bool) or not isinstance(n, int) for n in offsets)
                or dtype not in _ITEM_BYTES):
            raise ValueError("Invalid MTP tensor shape, offsets, or dtype")
        count = _ITEM_BYTES[dtype]
        for extent in shape:
            count *= extent
        start, end = offsets
        if start < 0 or end - start != count or 8 + size + end > before["size"]:
            raise ValueError("MTP tensor payload is truncated or has invalid offsets")
        tensors[key] = item
    if _identity(path) != before:
        raise ValueError("MTP tensor file changed during inspection")
    return tensors


def _layer_count(config: dict, family: str) -> int:
    keys = ("num_nextn_predict_layers", "mtp_num_hidden_layers") if family == "hy_v3" else ("mtp_num_hidden_layers",)
    text = config.get("text_config")
    for owner in (config, text if isinstance(text, dict) else {}):
        for key in keys:
            try:
                value = int(owner.get(key, 0))
            except (TypeError, ValueError, OverflowError):
                continue
            if value > 0:
                return value
    return 0


def _check_head(tensors: dict[str, dict], family: str, layers: int) -> None:
    # These trained-head roles distinguish a real predictor from an ordinary
    # target shard, an empty lookalike, or a config-only MTP declaration.
    normalized = {key.removeprefix("mtp."): value for key, value in tensors.items()
                  if family != "qwen4_exp" or key.startswith("mtp.")}
    if family == "qwen4_exp":
        required = {"pre_fc_norm_embedding.weight", "pre_fc_norm_hidden.weight",
                    "fc_embedding.weight", "fc_hidden.weight"}
    elif family == "hy_v3":
        required = {"enorm.weight", "hnorm.weight", "eh_proj.weight", "norm.weight"}
    else:
        required = {"pre_fc_norm_embedding.weight", "pre_fc_norm_hidden.weight",
                    "fc.weight", "norm.weight"}
    if required - normalized.keys():
        raise ValueError("MTP file is missing trained head projection or normalization tensors")
    for layer in range(layers):
        prefix = f"layers.{layer}."
        for component in ("self_attn.", "mlp."):
            if not any(key.startswith(prefix + component) and key.endswith(".weight") for key in normalized):
                raise ValueError("MTP file is missing a predictor attention or feed-forward block")
    for key, info in normalized.items():
        if not key.endswith(".weight"):
            continue
        if info["dtype"] == "U32":
            stem = key.removesuffix(".weight")
            if stem + ".scales" not in normalized or stem + ".biases" not in normalized:
                raise ValueError("Packed MTP tensor is missing its affine scales or biases")


def inspect_mtp(root: Path, config: dict, weight_map: dict | None = None) -> dict:
    """Describe a locally available ordinary scheduler MTP head.

    ``sidecarPath`` is the exact local value for speculative-config ``model``.
    Flash-Next integrated heads use their indexed target directory; the other
    native injectors require one concrete safetensors file. ``depthMax=6`` for
    ordinary Qwen/HY3 is a launcher control bound, not an upstream hard limit.
    """
    result = {"supported": False, "reason": "This checkpoint has no supported native MTP head.",
              "sidecarPath": None, "depth": 1, "depthMax": 1,
              "depthChoices": [1], "files": [], "signatures": []}
    if not isinstance(config, dict) or config.get("model_type") not in _NATIVE_FAMILIES:
        return result
    family = config["model_type"]
    layers = _layer_count(config, family)
    if layers < 1:
        result["reason"] = "The target config does not declare a trained native MTP layer."
        return result
    if family in {"qwen4_exp", "hy_v3"} and layers != 1:
        result["reason"] = "Rapid-MLX currently supports exactly one MTP layer for this family."
        return result
    try:
        root = Path(root).expanduser().resolve(strict=True)
        files = [root / "config.json"] if (root / "config.json").is_file() else []
        # The injector consumes this local training contract for combined MTPLX
        # checkpoints; changing it must invalidate a planned launch.
        contract = root / "mtplx_runtime.json"
        if contract.is_file():
            files.append(contract)
        index_path = root / "model.safetensors.index.json"
        if index_path.is_file():
            files.append(index_path)
            if weight_map is None:
                if index_path.stat().st_size > _MAX_HEADER_BYTES:
                    raise ValueError("MTP tensor index is too large")
                weight_map = json.loads(index_path.read_text()).get("weight_map", {})
        if weight_map is not None and not isinstance(weight_map, dict):
            raise ValueError("Invalid local MTP tensor index")
        integrated = {key: name for key, name in (weight_map or {}).items()
                      if isinstance(key, str) and key.startswith("mtp.")}
        candidates = ([root / "model-mtp.safetensors", root / "model.safetensors"]
                      if family == "hy_v3" else
                      [root / "mtp.safetensors", root / "model-mtp.safetensors",
                       root / "mtp/model.safetensors", root / "model.safetensors"])
        # Flash's native injector supports all indexed mtp.* shards. Other
        # injectors load one file and cannot join a multi-shard integrated head.
        if family == "qwen4_exp" and integrated:
            paths = sorted({_inside(root, name) for name in integrated.values()})
            tensors = {}
            for path in paths:
                for key, info in _header(path).items():
                    if key.startswith("mtp."):
                        if key in tensors or integrated.get(key) != str(path.relative_to(root)):
                            raise ValueError("MTP index and tensor headers disagree")
                        tensors[key] = info
            if set(tensors) != set(integrated):
                raise ValueError("MTP index refers to missing head tensors")
            _check_head(tensors, family, layers)
            sidecar = root
            files.extend(paths)
        else:
            integrated_error = None
            if integrated:
                names = set(integrated.values())
                if len(names) != 1:
                    integrated_error = "This native MTP injector requires its complete head in one safetensors file"
                else:
                    candidates.append(_inside(root, next(iter(names))))
            sidecar = None
            errors = []
            for candidate in candidates:
                if not candidate.is_file():
                    continue
                path = _inside(root, str(candidate.relative_to(root)))
                try:
                    tensors = _header(path)
                    _check_head(tensors, family, layers)
                except (ValueError, OSError) as exc:
                    errors.append(str(exc))
                    continue
                sidecar = path
                files.append(path)
                local_contract = path.parent / "mtplx_runtime.json"
                if local_contract.is_file():
                    files.append(local_contract)
                break
            if sidecar is None:
                raise ValueError(integrated_error or (errors[0] if errors else "No local safetensors file contains a trained MTP head"))
        identities = [_identity(path) for path in sorted(set(files))]
        standard_27b = family in {"qwen3_5", "qwen3_5_moe"} and re.search(
            r"qwen3[._-]8[-_ ]+27b(?:[-_ .]|$)",
            " ".join(str(value) for value in (root.name, config.get("_name_or_path", ""))), re.I)
        depth = 3 if standard_27b else 1
        maximum = 2 if family == "qwen4_exp" else 6
        result.update(supported=True, reason="Local trained MTP head metadata found; the native injector validates the complete tensor contract at startup.",
                      sidecarPath=str(sidecar), depth=depth, depthMax=maximum,
                      depthChoices=list(range(1, maximum + 1)),
                      files=[item["path"] for item in identities], signatures=identities,
                      modelType=family, autoDepth=True)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result["reason"] = str(exc)
    return result
