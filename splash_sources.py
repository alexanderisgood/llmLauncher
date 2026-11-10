"""Inspect and assemble local models using the selected Splash release's loaders.

Runs under Splash's bundled Python. Inspection reads headers only; preparation
links existing weights and fetches only a missing matching DFlash2 checkpoint.
"""
from __future__ import annotations

import collections
import hashlib
import importlib
import json
import os
import pathlib
import re
import sys
import tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import flash_vision


def file_identity(path: pathlib.Path) -> dict:
    stat = path.stat()
    return {"path": str(path.resolve()), "bytes": stat.st_size,
            "mtime": stat.st_mtime_ns, "ctime": stat.st_ctime_ns,
            "device": stat.st_dev, "inode": stat.st_ino}


def local_api():
    """The public local preparation API first shipped in Splash 1.4."""
    try:
        module = importlib.import_module("install.local")
    except ModuleNotFoundError as error:
        if error.name != "install.local":
            raise
        return None
    return module if callable(getattr(module, "prepare_local_model", None)) else None


def source_path(path: pathlib.Path) -> pathlib.Path:
    # Keep a GGUF's leaf name: Hub snapshots link split part names to opaque
    # blobs, but Splash finds the other parts by their names beside that link.
    path = pathlib.Path(os.path.abspath(path.expanduser()))
    return path.parent.resolve(strict=True) / path.name


def inspect_source(path: pathlib.Path) -> dict:
    api = local_api()
    return inspect_current_source(path, api) if api else inspect_legacy_source(path)


def inspect_legacy_source(path: pathlib.Path) -> dict:
    from install import families, gguf, hub, models, upstream

    path = path.resolve(strict=True)
    before = file_identity(path)
    if path.is_file() and path.suffix == ".gguf":
        metadata = gguf.Metadata(path, tensors=True)
        gguf.require_loadable(metadata)
        config = gguf.model_config(metadata)
        if (metadata.values.get("tokenizer.ggml.model") != "gpt2"
                or metadata.values.get("tokenizer.ggml.pre") != "qwen35"):
            raise models.ModelError("Splash requires the GGUF gpt2/qwen35 tokenizer")
        if metadata.values.get("split.count", 1) != 1:
            raise models.ModelError("Splash requires a single-file GGUF target")
        arch = gguf.text_architecture(metadata)
        if (metadata.values.get(arch + ".rope.freq_base") != 10000000
                or metadata.values.get(arch + ".rope.dimension_count") != 64
                or metadata.values.get(arch + ".rope.scaling.type", "none") != "none"):
            raise models.ModelError("Unsupported Splash rotary embedding configuration")
        family = families.family_for(config)
        loaded = set(gguf.loaded_tensors(metadata))
        kinds = collections.Counter(gguf.TENSOR_TYPES.get(kind, str(kind))
                                    for name, kind in metadata.tensors.items()
                                    if name in loaded)
        primary = next((name for name, _ in kinds.most_common() if name != "F32"), "F32")
        format_name = "gguf"
        files = [path]
        label = path.stem
        quantization = primary
        vision_format = "none"
    elif path.is_dir():
        repo = hub.Repository.local_directory(path)
        # A local checkpoint without a complete vision tower remains usable
        # for text; no tokenizer/configuration is borrowed from another model.
        try:
            target = upstream._mlx_target(repo, False)
        except models.ModelError:
            target = upstream._mlx_target(repo, True)
        config = target.config
        family = families.family_for(config)
        files = sorted({path / name for name in target.files.values()})
        format_name = "mlx-affine"
        vision_format = target.vision_format
        label = path.name
        quantization = "4-bit affine · group 64"
    else:
        raise models.ModelError("Choose a supported local GGUF or MLX checkpoint")
    identities = [file_identity(item) for item in files]
    if before != file_identity(path) or any(item["bytes"] <= 0 for item in identities):
        raise models.ModelError("Model files changed or are incomplete; rescan models")
    identity = hashlib.sha256(json.dumps([format_name, config, identities], sort_keys=True).encode()).hexdigest()
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", label)
    slug = re.sub(r"-+", "-", slug).strip("-_")[:70] or "model"
    text = config["text_config"]
    return {"kind": "source", "path": str(path), "id": f"local/{slug}-{identity[:12]}",
            "name": label, "family": family.name, "format": format_name,
            "quantization": quantization, "identity": identity,
            "targetBytes": sum(item.stat().st_size for item in files if item.suffix in (".gguf", ".safetensors")),
            "nativeContext": text["max_position_embeddings"], "hiddenSize": text["hidden_size"],
            "layers": text["num_hidden_layers"], "kvHeads": text["num_key_value_heads"],
            "headDim": text["head_dim"], "visionFormat": vision_format,
            "draftRepo": family.draft.repo, "files": identities}


def _current_target(path, api, scratch):
    from install import models

    vision = flash_vision.inspect_model(path)
    projector = pathlib.Path(vision['projector']) if vision else None
    try:
        return api._inspect(path, projector, False, scratch)
    except models.VisionError:
        if projector is not None:
            raise
        # An incomplete MLX vision tower can still serve its own text model.
        return api._inspect(path, None, True, scratch)


def _mlx_quantization(config):
    quant = config.get("quantization") or config.get("quantization_config") or {}
    if not isinstance(quant, dict):
        return "MLX quantized"
    mode = quant.get("mode") or quant.get("quant_method") or "affine"
    bits, group = quant.get("bits"), quant.get("group_size")
    if isinstance(bits, int) and isinstance(group, int):
        return f"{bits}-bit {mode} · group {group}"
    return str(mode) if mode != "affine" else "MLX mixed quantization"


def _gguf_description(paths):
    """Header-only quantization and storage categories, including split files.

    Stored byte counts include each tensor's alignment padding. They describe
    disk storage, not runtime residency; Splash's planner owns the latter.
    """
    from install import gguf, models

    headers, spans = [], {}
    for path in paths:
        header = gguf.Metadata(path, tensors=True)
        headers.append(header)
        alignment = header.values.get("general.alignment", 32)
        if type(alignment) is not int or alignment <= 0:
            raise models.ModelError("Invalid GGUF tensor alignment")
        data_start = (header.consumed + alignment - 1) // alignment * alignment
        offsets = sorted((offset, name) for name, offset in header.offsets.items())
        payload = path.stat().st_size - data_start
        for index, (offset, name) in enumerate(offsets):
            end = offsets[index + 1][0] if index + 1 < len(offsets) else payload
            if not 0 <= offset < end <= payload:
                raise models.ModelError("GGUF tensor data is incomplete: " + name)
            spans[name] = end - offset
    metadata = gguf.merged_split(headers)
    loaded = set(gguf.loaded_tensors(metadata))
    kinds = collections.Counter(gguf.TENSOR_TYPES.get(kind, str(kind))
                                for name, kind in metadata.tensors.items() if name in loaded)
    # Mixed quants often have many tiny Q8 projections and huge Q4 experts.
    # Describe the dominant weight storage, excluding the separate PLE table.
    storage_kinds = collections.Counter()
    for name, kind in metadata.tensors.items():
        if name in loaded and name != "per_layer_token_embd.weight":
            storage_kinds[gguf.TENSOR_TYPES.get(kind, str(kind))] += spans[name]
    primary = next((name for name, _ in storage_kinds.most_common()
                    if name not in {"F32", "F16", "BF16"}),
                   next(iter(kinds), "F32"))
    arch = gguf.text_architecture(metadata)
    values = metadata.values
    expert_bytes = sum(size for name, size in spans.items()
                       if name in loaded and "_exps." in name)
    ple_bytes = spans.get("per_layer_token_embd.weight", 0)
    resident = sum(size for name, size in spans.items() if name in loaded) - expert_bytes - ple_bytes
    interval = values.get(arch + ".full_attention_interval", 4)
    layers = gguf.loaded_layers(metadata, arch)
    return primary, {
        "tensorTypes": dict(sorted(kinds.items())),
        "expertBytes": expert_bytes,
        "pleBytes": ple_bytes,
        "plePrecision": gguf.TENSOR_TYPES.get(metadata.tensors.get("per_layer_token_embd.weight"), "unknown"),
        "residentTensorBytes": resident,
        "expertCount": values.get(arch + ".expert_count", 0),
        "expertsPerToken": values.get(arch + ".expert_used_count", 0),
        "fullAttentionInterval": interval,
        "attentionLayers": layers // interval,
    }


def inspect_current_source(path: pathlib.Path, api) -> dict:
    from install import models

    path = source_path(path)
    selected_path = path
    before = file_identity(path)
    directory = path if path.is_dir() else path.parent
    candidates = directory.rglob("*") if path.is_dir() else directory.glob("*.gguf")
    before_files = {item: file_identity(item) for item in candidates if item.is_file()}
    vision = flash_vision.inspect_model(path)
    if vision:
        projector = pathlib.Path(vision['projector'])
        before_files[projector] = file_identity(projector)
    with tempfile.TemporaryDirectory(prefix="launcher-splash-inspect-") as scratch:
        repo, target = _current_target(path, api, pathlib.Path(scratch))
        config = json.loads(target.config.read_text(encoding="utf-8"))
        # The native inspection reads only config, shard indices and GGUF
        # headers. repo.paths names exclusively local files, so no Hub call or
        # payload load can be introduced while collecting their identities.
        paths = sorted({repo.paths[name] for name in target.files.values()})
        identities = [file_identity(item) for item in paths]
        if identities != [before_files.get(item) for item in paths]:
            raise models.ModelError("Model files changed during inspection; rescan models")
        target_paths = sorted({repo.paths[name] for key, name in target.files.items()
                               if key.startswith("target/") and name.endswith((".gguf", ".safetensors"))})
        vision_paths = {repo.paths[name] for key, name in target.files.items()
                        if key.startswith("vision/") and name.endswith((".gguf", ".safetensors"))}
        details = {}
        if target.format == "gguf":
            # Use the first shard as a stable selection regardless of which
            # split part the scanner encountered; preserve snapshot symlinks.
            path = target_paths[0]
            label = re.sub(r"-\d{5}-of-\d{5}$", "", path.stem)
            quantization, details = _gguf_description(target_paths)
        else:
            label = path.name
            quantization = _mlx_quantization(config)
        if before != file_identity(selected_path) or any(item["bytes"] <= 0 for item in identities):
            raise models.ModelError("Model files changed or are incomplete; rescan models")
        if identities != [file_identity(item) for item in paths]:
            raise models.ModelError("Model files changed during inspection; rescan models")
        identity = hashlib.sha256(json.dumps(
            [target.format, config, identities], sort_keys=True).encode()).hexdigest()
        slug = re.sub(r"[^A-Za-z0-9_-]+", "-", label)
        slug = re.sub(r"-+", "-", slug).strip("-_")[:70] or "model"
        text = config.get("text_config", config)
        return {"kind": "source", "path": str(path), "id": f"local/{slug}-{identity[:12]}",
                "name": label, "family": target.family.name, "format": target.format,
                "quantization": quantization, "identity": identity,
                "targetBytes": sum(item.stat().st_size for item in target_paths),
                "visionBytes": sum(item.stat().st_size for item in vision_paths - set(target_paths)),
                "nativeContext": text["max_position_embeddings"], "hiddenSize": text["hidden_size"],
                "layers": text["num_hidden_layers"], "kvHeads": text["num_key_value_heads"],
                "headDim": text["head_dim"], "visionFormat": target.vision_format,
                "vision": vision,
                "draftRepo": target.family.draft_repo, "files": identities,
                "streaming": target.family.name in {"Qwen3.8-Flash-Next", "Qwen3.6-35B-A3B"},
                **details}


def prepare_source(source: dict, destination: pathlib.Path, drafts: list[str]) -> pathlib.Path:
    api = local_api()
    return (prepare_current_source(source, destination, drafts, api) if api else
            prepare_legacy_source(source, destination, drafts))


def prepare_current_source(source, destination, drafts, api):
    from install import hub, models, upstream

    current = inspect_source(pathlib.Path(source["path"]))
    if current["identity"] != source["identity"]:
        raise models.ModelError("Splash model changed after scanning; rescan before launching")
    path = pathlib.Path(current["path"])
    options = {"language_only": current["visionFormat"] == "none", "models_dir": destination}
    if current.get('vision'):
        options['mmproj'] = current['vision']['projector']
    root = None
    # Always use the release's public preparation entry point, including when
    # a prior release has already assembled these same checkpoint files.
    for name in drafts:
        try:
            root = api.prepare_local_model(path, draft=name, **options)
            break
        except (models.ModelError, OSError, ValueError):
            continue
    if root is None:
        try:
            root = api.prepare_local_model(path, **options)
        except models.ModelError:
            # The public API is network-free. Download only a missing matching
            # draft, using the native validator before fetching its weights,
            # then give the resulting local snapshot to that same API.
            print(f"Preparing Splash's matching DFlash2 draft: {current['draftRepo']}",
                  file=sys.stderr, flush=True)
            with (hub.as_model_errors("cannot download Splash's matching draft"),
                  tempfile.TemporaryDirectory(prefix="launcher-splash-draft-") as scratch):
                _, target = _current_target(path, api, pathlib.Path(scratch))
                repo = hub.Repository.resolve(current["draftRepo"])
                downloaded = upstream.draft_files(repo, target)
                draft = downloaded["draft/config.json"].parent
                root = api.prepare_local_model(path, draft=draft, **options)
    if inspect_source(path)["identity"] != source["identity"]:
        raise models.ModelError("Splash model changed during preparation; rescan models")
    return root


def prepare_dspine_source(source, destination):
    """Link a text target and tokenizer for the native external-draft route."""
    from install import hub, models, upstream
    from splash_runtime import dspine_target

    path = pathlib.Path(source["path"])
    current = inspect_source(path)
    if current["identity"] != source["identity"] or not dspine_target(current):
        raise models.ModelError("DSpine target changed or is incompatible; rescan models")
    repo = hub.Repository.local_directory(path)
    target = upstream.mlx_target(repo, language_only=True)
    files = {name: repo.paths[original] for name, original in target.files.items()}
    link = models.local_selection_link(destination, path, None, None, True)
    root = upstream.publish(destination, link, {
        "version": 1, "model": str(path), "family": target.family.name,
        "target_format": target.format, "vision_format": "none", "external_draft": "dspine",
        "sources": {"target": repo.identity()},
    }, files)
    if inspect_source(path)["identity"] != source["identity"]:
        raise models.ModelError("DSpine target changed during preparation; rescan models")
    return root


def prepare_legacy_source(source: dict, destination: pathlib.Path, drafts: list[str]) -> pathlib.Path:
    from install import assembly, families, gguf, hub, models, upstream

    current = inspect_source(pathlib.Path(source["path"]))
    if current["identity"] != source["identity"]:
        raise models.ModelError("Splash model changed after scanning; rescan before launching")
    family = families.named(current["family"])
    # Reuse verified assemblies without downloading metadata or hashing all
    # target weights again on subsequent launches.
    for manifest in sorted((destination / ".resolved").glob("*/model.json")):
        try:
            record = models.read_json(manifest)
            if record.get("model") == current["id"] and record.get("family") == family.name:
                assembly.verify(manifest.parent)
                return manifest.parent
        except (models.ModelError, OSError, ValueError):
            continue
    draft_repo = None
    draft_files = None
    for name in drafts:
        try:
            candidate = hub.Repository.local_directory(name)
            draft_files = upstream._draft_files(candidate, family)
            draft_repo = candidate
            break
        except (models.ModelError, OSError, ValueError):
            continue
    if draft_repo is None:
        print(f"Preparing Splash's matching DFlash2 draft: {family.draft.repo}", file=sys.stderr, flush=True)
        with hub.as_model_errors("cannot download Splash's matching draft"):
            draft_repo = hub.Repository.resolve(family.draft.repo)
            draft_files = upstream._draft_files(draft_repo, family)

    path = pathlib.Path(current["path"])
    files = dict(draft_files)
    if current["format"] == "gguf":
        files["target/" + path.name] = path
        derived = gguf.derived_files(path)
        metadata_root = destination / ".local-metadata" / current["identity"]
        metadata_root.mkdir(parents=True, exist_ok=True)
        for name, data in derived.items():
            output = metadata_root / name
            output.parent.mkdir(parents=True, exist_ok=True)
            if not output.is_file() or output.read_bytes() != data:
                output.write_bytes(data)
            files[name] = output
        files["tokenizer/config.json"] = metadata_root / "config.json"
    else:
        repo = hub.Repository.local_directory(path)
        target = upstream._mlx_target(repo, current["visionFormat"] == "none")
        files.update({name: path / filename for name, filename in target.files.items()})
    # Hash each source once, even when configuration/shards are linked into
    # several places. No model weights are copied or requantized.
    records = {item: assembly.file_record(item) for item in set(files.values())}
    record = {"version": 1, "model": source["id"], "family": family.name,
              "target_format": current["format"], "vision_format": current["visionFormat"],
              "sources": {"target": {"repo": str(path.parent if path.is_file() else path), "revision": None},
                          "draft": draft_repo.identity()},
              "files": {name: records[item] for name, item in sorted(files.items())}}
    if current["format"] == "gguf":
        record["metadata"] = assembly.metadata_key(record["files"])
    if inspect_source(path)["identity"] != source["identity"]:
        raise models.ModelError("Splash model changed during preparation; rescan models")
    return assembly.build(destination, record, files)


def main() -> None:
    sys.path.insert(0, str(pathlib.Path(sys.argv[1]).resolve()))
    mode = sys.argv[2]
    request = json.loads(sys.stdin.read(4 * 1024 * 1024))
    if mode == "inspect":
        results = []
        for value in request["paths"]:
            try:
                results.append({"path": value, "source": inspect_source(pathlib.Path(value))})
            except (OSError, ValueError, RuntimeError, KeyError) as error:
                results.append({"path": value, "error": str(error)[:2000]})
        print(json.dumps(results))
    elif mode == "prepare":
        root = prepare_source(request["source"], pathlib.Path(request["destination"]), request.get("drafts", []))
        print(json.dumps({"root": str(root)}))
    elif mode == "prepare-dspine":
        api = local_api()
        if not api:
            raise ValueError("DSpine needs the patched Splash 1.6.0 runtime.")
        root = prepare_dspine_source(request["source"], pathlib.Path(request["destination"]))
        print(json.dumps({"root": str(root)}))
    else:
        raise ValueError("Unknown Splash source operation")


if __name__ == "__main__":
    main()
