#!/usr/bin/env python3
"""Print the interesting metadata of a GGUF file without loading the model.

Usage: python3 bench/gguf_info.py <file.gguf> [--json]
"""
from __future__ import annotations

import json
import pathlib
import struct
import sys

TYPE_NAMES = (
    "uint8", "int8", "uint16", "int16", "uint32", "int32", "float32",
    "bool", "string", "array", "uint64", "int64", "float64",
)
FIXED = {
    0: ("<B", 1), 1: ("<b", 1), 2: ("<H", 2), 3: ("<h", 2),
    4: ("<I", 4), 5: ("<i", 4), 6: ("<f", 4), 7: ("<?", 1),
    10: ("<Q", 8), 11: ("<q", 8), 12: ("<d", 8),
}


def read_value(handle, value_type: int):
    if value_type == 8:
        length = struct.unpack("<Q", handle.read(8))[0]
        return handle.read(length).decode("utf-8", "replace")
    if value_type == 9:
        item_type = struct.unpack("<I", handle.read(4))[0]
        count = struct.unpack("<Q", handle.read(8))[0]
        values = [read_value(handle, item_type) for _ in range(count)]
        return values
    fmt, size = FIXED[value_type]
    return struct.unpack(fmt, handle.read(size))[0]


INTERESTING = (
    "general.architecture", "general.name", "general.size_label",
    "general.file_type", "general.quantization_version",
    "context_length", "block_count", "embedding_length", "feed_forward_length",
    "attention.head_count", "attention.head_count_kv", "attention.key_length",
    "attention.value_length", "rope.freq_base", "expert_count",
    "expert_used_count", "expert_feed_forward_length", "expert_shared_count",
    "expert_group_count", "expert_group_used_count", "ssm.state_size",
    "ssm.conv_kernel", "ssm.inner_size", "ssm.group_count", "ssm.time_step_rank",
    "full_attention_interval", "attention.sliding_window",
)


def main() -> int:
    path = pathlib.Path(sys.argv[1]).expanduser()
    with path.open("rb") as handle:
        magic = handle.read(4)
        if magic != b"GGUF":
            raise SystemExit(f"not a GGUF file: {magic!r}")
        version = struct.unpack("<I", handle.read(4))[0]
        tensor_count = struct.unpack("<Q", handle.read(8))[0]
        kv_count = struct.unpack("<Q", handle.read(8))[0]
        metadata: dict[str, object] = {}
        for _ in range(kv_count):
            key_length = struct.unpack("<Q", handle.read(8))[0]
            key = handle.read(key_length).decode("utf-8", "replace")
            value_type = struct.unpack("<I", handle.read(4))[0]
            metadata[key] = read_value(handle, value_type)
    prefix = str(metadata.get("general.architecture", ""))
    summary = {"version": version, "tensorCount": tensor_count, "metadataCount": kv_count}
    for name in INTERESTING:
        key = name if "." in name and name.startswith("general") else f"{prefix}.{name}"
        if key in metadata:
            summary[key] = metadata[key]
    summary["general.name"] = metadata.get("general.name")
    summary["general.size_label"] = metadata.get("general.size_label")
    summary["general.file_type"] = metadata.get("general.file_type")
    summary["tensorTypeCounts"] = {}
    if "--json" in sys.argv:
        print(json.dumps(summary, indent=2, default=str))
    else:
        for key, value in summary.items():
            if isinstance(value, list) and len(value) > 8:
                print(f"{key}: [{len(value)} values] {value[:8]}...")
            else:
                print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
