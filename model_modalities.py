"""Prepare and advertise image input for the audited local serving route."""
import json
import math
import os
import re
import tempfile
from pathlib import Path


def _vision_artifact(backend: str, runtime_version: str, model_path: str):
    # Audited MTPLX OpenAI routes flatten image parts before applying the
    # publisher's string-content template, then splice in the vision embeddings.
    # Other engines (including oMLX DFlash) retain their text-only contract.
    if backend != "mtplx" or not re.fullmatch(
        r"(?:mtplx\s+)?2\.11\.2(?:\s+\(2\.11\.2\))?", runtime_version.strip(), re.I,
    ):
        return None
    try:
        root = Path(model_path).resolve(strict=True)
        config = json.loads((root / "config.json").read_text())
        index = json.loads((root / "model.safetensors.index.json").read_text())
        if not isinstance(config.get("vision_config"), dict) or not config["vision_config"]:
            return None
        if config.get("model_type") not in {"qwen3_5", "qwen3_6"}:
            return None
        weights = index.get("weight_map")
        if not isinstance(weights, dict):
            return None
        shards = {value for key, value in weights.items()
                  if key.startswith(("vision_tower.", "model.visual."))}
        if not shards:
            return None
        for shard in shards:
            path = (root / shard).resolve(strict=True)
            if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size <= 16:
                return None
    except (OSError, ValueError, TypeError, AttributeError):
        return None
    return root, config["vision_config"]


def _read_config(path: Path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _processor_matches(processor: dict, vision: dict) -> bool:
    """Validate the values MTPLX consumes, including the tower's patch geometry."""
    if not isinstance(processor, dict):
        return False
    for key, model_key in (("patch_size", "patch_size"),
                           ("merge_size", "spatial_merge_size"),
                           ("temporal_patch_size", "temporal_patch_size")):
        value = processor.get(key)
        if type(value) is not int or value <= 0 or value != vision.get(model_key):
            return False
    size = processor.get("size", {})
    if not isinstance(size, dict):
        return False
    low = processor.get("min_pixels", size.get("shortest_edge"))
    high = processor.get("max_pixels", size.get("longest_edge"))
    if type(low) is not int or type(high) is not int or not 0 < low <= high:
        return False
    for key in ("do_rescale", "do_normalize"):
        if type(processor.get(key)) is not bool:
            return False
    if processor["do_rescale"]:
        scale = processor.get("rescale_factor")
        if type(scale) not in (int, float) or not math.isfinite(scale) or scale <= 0:
            return False
    if processor["do_normalize"]:
        for key in ("image_mean", "image_std"):
            values = processor.get(key)
            if not isinstance(values, list) or len(values) != 3 or any(
                type(v) not in (int, float) or not math.isfinite(v)
                or (key == "image_std" and v <= 0) for v in values
            ):
                return False
    return True


def prepare_mtplx_image_processor(backend: str, runtime_version: str, model_path: str) -> bool:
    """Supply MTPLX 2.11.2's legacy filename from the publisher's combined config.

    Run during client preparation, never during a read-only capability scan.
    Preserve existing files; do not invent defaults or download another model's
    settings. A failed preparation leaves the route text-only.
    """
    artifact = _vision_artifact(backend, runtime_version, model_path)
    if artifact is None:
        return False
    root, vision = artifact
    target = root / "preprocessor_config.json"
    if target.exists() or target.is_symlink():
        return _processor_matches(_read_config(target), vision)
    processor = _read_config(root / "processor_config.json").get("image_processor")
    if not _processor_matches(processor, vision):
        return False
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=root,
                                         prefix=".preprocessor-", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(processor, handle, indent=2, allow_nan=False)
            handle.write("\n")
        # Publish the complete file without overwriting a concurrent install.
        os.link(temporary, target)
    except FileExistsError:
        pass
    except OSError:
        return False
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return _processor_matches(_read_config(target), vision)


def pi_model_inputs(backend: str, runtime_version: str, model_path: str) -> list[str]:
    artifact = _vision_artifact(backend, runtime_version, model_path)
    if artifact is not None:
        root, vision = artifact
        if _processor_matches(_read_config(root / "preprocessor_config.json"), vision):
            return ["text", "image"]
    return ["text"]
