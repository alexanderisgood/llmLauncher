#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Create a verified FP16 clone for oMLX ANE CPU sharing.

Derived from oMLX v0.6.3rc2's tools/clone_mlx_model_fp16.py. Packed integer
weights are copied unchanged; BF16 floating tensors are converted one shard at
a time. The source is read-only and the caller supplies a unique staging path.

The upstream utility and this modified version are licensed under Apache-2.0.
See THIRD_PARTY_NOTICES.md for attribution and the repository LICENSE for terms.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any

import mlx.core as mx
from safetensors import safe_open


FP16_MAX = 65_504.0


def emit(event: str, **fields: Any) -> None:
    print(json.dumps({"event": event, **fields}, separators=(",", ":")), flush=True)


def reject_symlinks(root: Path) -> None:
    for directory, names, files in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in [*names, *files]:
            item = base / name
            if item.is_symlink():
                raise ValueError(f"The source contains a symbolic link: {item.relative_to(root)}")


def clone_config(source: Path, destination: Path) -> None:
    config = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("config.json is not an object")
    if isinstance(config.get("text_config"), dict):
        config["text_config"]["dtype"] = "float16"
    if "dtype" in config:
        config["dtype"] = "float16"
    destination.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def conversion_issues(shard: Path, tensors: dict[str, mx.array]) -> list[str]:
    issues: list[str] = []
    for name, value in tensors.items():
        if not mx.issubdtype(value.dtype, mx.floating):
            continue
        if value.dtype not in (mx.bfloat16, mx.float16):
            issues.append(f"{shard.name}:{name}: unsupported floating dtype {value.dtype}")
            continue
        finite = mx.isfinite(value)
        non_finite = int(mx.sum(~finite).item())
        if non_finite:
            issues.append(f"{shard.name}:{name}: {non_finite} NaN or infinite value(s)")
        finite_abs = mx.where(
            finite,
            mx.abs(value).astype(mx.float32),
            mx.array(0.0, dtype=mx.float32),
        )
        maximum = float(mx.max(finite_abs).item()) if value.size else 0.0
        if maximum > FP16_MAX:
            issues.append(
                f"{shard.name}:{name}: maximum absolute value {maximum:g} exceeds the FP16 limit {FP16_MAX:g}"
            )
    return issues


def validate_conversion(shards: list[Path]) -> None:
    issues: list[str] = []
    for index, shard in enumerate(shards, start=1):
        tensors = mx.load(str(shard))
        issues.extend(conversion_issues(shard, tensors))
        del tensors
        mx.clear_cache()
        emit("validated", current=index, total=len(shards), file=shard.name)
    if issues:
        raise ValueError("FP16 clone validation failed: " + " | ".join(issues[:20]))


def clone_model(source: Path, destination: Path) -> None:
    source = source.resolve(strict=True)
    destination = destination.resolve(strict=False)
    if source == destination or source in destination.parents:
        raise ValueError("The destination must be outside the source model directory")
    if not source.is_dir() or not (source / "config.json").is_file():
        raise ValueError("The source model directory is incomplete")
    if not destination.parent.is_dir():
        raise ValueError("The destination parent does not exist")
    if destination.exists():
        raise ValueError("The staging destination already exists")
    reject_symlinks(source)
    shards = sorted(source.glob("*.safetensors"))
    if not shards:
        raise ValueError("No safetensors shards were found")

    validate_conversion(shards)
    destination.mkdir(mode=0o700)
    for item in sorted(source.iterdir(), key=lambda value: value.name):
        if item.suffix == ".safetensors":
            continue
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        elif item.name == "config.json":
            clone_config(item, target)
        else:
            shutil.copy2(item, target)

    for index, shard in enumerate(shards, start=1):
        target = destination / shard.name
        temporary = destination / f".{shard.name}.partial.safetensors"
        with safe_open(shard, framework="np") as handle:
            metadata = handle.metadata() or {}
        tensors = mx.load(str(shard))
        converted = {
            name: value.astype(mx.float16) if value.dtype == mx.bfloat16 else value
            for name, value in tensors.items()
        }
        mx.save_safetensors(str(temporary), converted, metadata=metadata)
        temporary.replace(target)
        del converted, tensors
        mx.clear_cache()
        emit("converted", current=index, total=len(shards), file=shard.name)
    emit("completed", current=len(shards), total=len(shards))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        clone_model(args.source, args.destination)
    except Exception as error:  # noqa: BLE001
        emit("error", message=str(error)[:2_000])
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
