"""Offline replacement of one Flash-Next GGUF PLE table, preserving main weights.

The first shard is repacked without its old PLE tensor. Other shards and the
standalone BF16 table use APFS clones, with only their small headers changed.
Every output tensor must match its input SHA-256 before exclusive publication.
No original model file is changed or removed.
"""
from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import sys
import tempfile
import time

PLE = "per_layer_token_embd.weight"
BF16 = 30  # GGML_TYPE_BF16, also Splash install.gguf.TENSOR_TYPES[30].
EXPECTED_SHAPE = (160, 320001536)
CHUNK = 16 * 1024**2
MAX_HEADER = 128 * 1024**2
MAX_ITEMS = 1_000_000
MAX_FIELDS = 16384
RESERVE = 2 * 1024**3
SCALARS = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f",
           7: "?", 10: "Q", 11: "q", 12: "d"}
# Exact GGML serialized block sizes, restricted to source formats this helper
# can verify. Unknown formats fail closed rather than inferring payload sizes.
BLOCKS = {0: (1, 4), 1: (1, 2), BF16: (1, 2), 2: (32, 18), 3: (32, 20),
          6: (32, 22), 7: (32, 24), 8: (32, 34), 10: (256, 84),
          11: (256, 110), 12: (256, 144), 13: (256, 176), 14: (256, 210),
          16: (256, 66), 17: (256, 74), 18: (256, 98), 19: (256, 50),
          20: (32, 18), 21: (256, 110), 22: (256, 82), 23: (256, 136),
          29: (256, 56), 39: (32, 17), 42: (64, 18)}
PLE_KEYS = {"layers", "ngram_size", "heads_per_ngram", "conv_kernel",
            "eos_token_id", "image_token_id", "layer_multipliers",
            "head_offsets", "head_vocab_sizes"}
SPLIT_KEYS = ("split.no", "split.count", "split.tensors.count")


class PreparationError(ValueError):
    """Inputs cannot be safely prepared without changing the main model."""


def align(value, alignment):
    return (value + alignment - 1) // alignment * alignment


def identity(path):
    path = Path(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise PreparationError(f"Input is not a regular file: {path}")
    return {"path": str(path.absolute()), "resolvedPath": str(path.resolve()),
            "device": info.st_dev, "inode": info.st_ino, "bytes": info.st_size,
            "mtimeNs": info.st_mtime_ns, "ctimeNs": info.st_ctime_ns}


def unchanged(record):
    if identity(record["path"]) != record:
        raise PreparationError(f"Source changed during preparation: {record['path']}")


def gguf_string(value):
    encoded = value.encode("utf-8")
    return struct.pack("<Q", len(encoded)) + encoded


def entry(key, kind, value):
    if kind == 8:
        payload = gguf_string(value)
    elif kind in SCALARS:
        payload = struct.pack("<" + SCALARS[kind], value)
    else:
        raise PreparationError("Only scalar metadata entries can be created")
    return {"key": key, "kind": kind, "value": value,
            "raw": gguf_string(key) + struct.pack("<I", kind) + payload}


class Header:
    """Bounded GGUF v3 reader; retained metadata entries include original bytes."""

    def __init__(self, path, *, header_only=False):
        self.path = Path(path)
        self.source = identity(self.path)
        with self.path.open("rb") as stream:
            self._stream = stream
            magic, version, count, metadata_count = self.unpack("4sIQQ")
            if magic != b"GGUF" or version != 3:
                raise PreparationError("Expected a little-endian GGUF v3 file")
            if not 0 < count <= MAX_FIELDS or not 0 < metadata_count <= MAX_FIELDS:
                raise PreparationError("GGUF field counts exceed supported bounds")
            self.entries, self.values = [], {}
            for _ in range(metadata_count):
                start = stream.tell()
                key = self.string()
                if not key or key in self.values:
                    raise PreparationError("Duplicate or empty GGUF metadata key")
                kind, = self.unpack("I")
                value = self.value(kind)
                end = stream.tell()
                stream.seek(start)
                raw = self.read(end - start)
                self.entries.append({"key": key, "kind": kind, "value": value, "raw": raw})
                self.values[key] = value
            self.alignment = self.values.get("general.alignment", 32)
            if (type(self.alignment) is not int or self.alignment <= 0
                    or self.alignment > 1024**2 or self.alignment & (self.alignment - 1)):
                raise PreparationError("Invalid GGUF alignment")
            self.tensors, names = [], set()
            for _ in range(count):
                name = self.string()
                if not name or name in names:
                    raise PreparationError("Duplicate or empty GGUF tensor name")
                names.add(name)
                rank, = self.unpack("I")
                if not 1 <= rank <= 4:
                    raise PreparationError("Unsupported GGUF tensor rank")
                dims = self.unpack("Q" * rank)
                kind, offset = self.unpack("IQ")
                if kind not in BLOCKS or any(not 0 < size <= 2**40 for size in dims):
                    raise PreparationError(f"Unsupported tensor dimensions or type: {name}")
                elements = math.prod(dims)
                block, size = BLOCKS[kind]
                if dims[0] % block or elements > 2**63:
                    raise PreparationError(f"Invalid GGUF quantization block shape: {name}")
                nbytes = elements // block * size
                if offset % self.alignment:
                    raise PreparationError(f"Unaligned GGUF tensor: {name}")
                self.tensors.append({"name": name, "dims": list(dims), "type": kind,
                                     "offset": offset, "bytes": nbytes})
            consumed = stream.tell()
            self.data_offset = align(consumed, self.alignment)
            stream.seek(0)
            self.header_sha256 = hashlib.sha256(self.read(consumed)).hexdigest()
            self._stream = None
        end = 0
        for tensor in sorted(self.tensors, key=lambda item: item["offset"]):
            if tensor["offset"] < end:
                raise PreparationError("Overlapping GGUF tensor payloads")
            end = tensor["offset"] + tensor["bytes"]
            tensor["absoluteOffset"] = self.data_offset + tensor["offset"]
        self.minimum_size = self.data_offset + end
        if not header_only and self.minimum_size > self.source["bytes"]:
            raise PreparationError(f"Truncated GGUF tensor payload: {self.path}")
        unchanged(self.source)

    def read(self, count):
        if count < 0 or self._stream.tell() + count > MAX_HEADER:
            raise PreparationError("GGUF metadata exceeds the bounded header limit")
        data = self._stream.read(count)
        if len(data) != count:
            raise PreparationError("Truncated GGUF metadata")
        return data

    def unpack(self, fmt):
        return struct.unpack("<" + fmt, self.read(struct.calcsize("<" + fmt)))

    def string(self):
        length, = self.unpack("Q")
        try:
            return self.read(length).decode("utf-8")
        except UnicodeError as error:
            raise PreparationError("Invalid UTF-8 in GGUF metadata") from error

    def value(self, kind):
        if kind == 8:
            return self.string()
        if kind == 9:
            element, count = self.unpack("IQ")
            if element == 9 or element not in {*SCALARS, 8} or count > MAX_ITEMS:
                raise PreparationError("Invalid or oversized GGUF metadata array")
            return [self.value(element) for _ in range(count)]
        if kind not in SCALARS:
            raise PreparationError("Unknown GGUF metadata type")
        return self.unpack(SCALARS[kind])[0]


def source_paths(sources):
    if isinstance(sources, (str, Path)):
        first = Path(sources).expanduser().absolute()
        match = re.fullmatch(r"(.+)-00001-of-(\d{5})\.gguf", first.name)
        if match:
            count = int(match[2])
            if not 1 <= count <= 128:
                raise PreparationError("Invalid GGUF split count")
            return [first.with_name(f"{match[1]}-{number:05d}-of-{count:05d}.gguf")
                    for number in range(1, count + 1)]
        return [first]
    paths = [Path(path).expanduser().absolute() for path in sources]
    if not paths or len(paths) > 128:
        raise PreparationError("Choose a bounded set of GGUF source shards")
    return paths


def split_entries(header, number, count, total, *, minimal=False):
    values = {"split.no": number, "split.count": count, "split.tensors.count": total}
    entries = []
    for item in header.entries:
        key = item["key"]
        if minimal and key not in {"general.architecture", "general.alignment", *SPLIT_KEYS}:
            continue
        if key in values:
            if item["kind"] not in {0, 1, 2, 3, 4, 5, 10, 11} or type(item["value"]) is not int:
                raise PreparationError("Split metadata must use fixed-width integers")
            try:
                item = entry(key, item["kind"], values.pop(key))
            except struct.error as error:
                raise PreparationError("Updated split count does not fit its metadata field") from error
        entries.append(item)
    for key, value in values.items():
        entries.append(entry(key, 10 if key == "split.tensors.count" else 2, value))
    return entries


def encode_header(entries, tensors, alignment, *, data_offset=None):
    def serialize(values):
        return (struct.pack("<4sIQQ", b"GGUF", 3, len(tensors), len(values))
                + b"".join(item["raw"] for item in values)
                + b"".join(gguf_string(tensor["name"]) + struct.pack("<I", len(tensor["dims"]))
                           + struct.pack("<" + "Q" * len(tensor["dims"]), *tensor["dims"])
                           + struct.pack("<IQ", tensor["type"], tensor["offset"])
                           for tensor in tensors))
    raw = serialize(entries)
    if data_offset is not None:
        # Arbitrary trailing zero padding would change the loader's computed
        # data offset. An ignored string makes the parser consume the whole
        # original header extent, retaining every large payload's APFS blocks.
        padding = entry("launcher.splash_ple.padding", 8, "")
        remaining = data_offset - len(raw) - len(padding["raw"])
        if remaining < 0:
            raise PreparationError("Updated clone header cannot fit before its tensor payload")
        raw = serialize([*entries, entry(padding["key"], 8, " " * remaining)])
        if len(raw) != data_offset:
            raise PreparationError("Could not preserve the cloned tensor data offset")
    else:
        raw += bytes(align(len(raw), alignment) - len(raw))
    if len(raw) > MAX_HEADER:
        raise PreparationError("Output header exceeds the metadata limit")
    return raw


def _plan(sources, ple_source, *, header_only=False, expected_shape=EXPECTED_SHAPE):
    paths = source_paths(sources)
    main = [Header(path, header_only=header_only) for path in paths]
    ple = Header(Path(ple_source).expanduser().absolute(), header_only=header_only)
    identities = [(h.source["device"], h.source["inode"]) for h in [*main, ple]]
    if len(set(identities)) != len(identities):
        raise PreparationError("Source files must be distinct, without hard-linked duplicates")
    if main[0].values.get("general.architecture") != "qwen4exp" or ple.values.get("general.architecture") != "qwen4exp":
        raise PreparationError("PLE replacement requires the qwen4exp architecture")
    tensors = [tensor for header in main for tensor in header.tensors]
    if len({tensor["name"] for tensor in tensors}) != len(tensors):
        raise PreparationError("Duplicate tensor across source shards")
    old = [tensor for tensor in main[0].tensors if tensor["name"] == PLE]
    if len(old) != 1 or any(tensor["name"] == PLE for header in main[1:] for tensor in header.tensors):
        raise PreparationError("Exactly one old PLE table must belong to the first shard")
    if len(ple.tensors) != 1 or ple.tensors[0]["name"] != PLE or ple.tensors[0]["type"] != BF16:
        raise PreparationError("Replacement must contain only the original BF16 PLE tensor")
    if tuple(old[0]["dims"]) != tuple(expected_shape) or old[0]["dims"] != ple.tensors[0]["dims"]:
        raise PreparationError("PLE tensor dimensions do not match the original model")
    prefix = "qwen4exp.ple."
    original_keys = {key for key in main[0].values if key.startswith(prefix)}
    replacement_keys = {key for key in ple.values if key.startswith(prefix)}
    if not {prefix + key for key in PLE_KEYS} <= original_keys or original_keys != replacement_keys:
        raise PreparationError("PLE hashing schema keys are incomplete or incompatible")
    original_entries = {item["key"]: item for item in main[0].entries}
    replacement_entries = {item["key"]: item for item in ple.entries}
    for key in original_keys:
        first, other = original_entries[key], replacement_entries[key]
        if first["raw"] != other["raw"]:
            raise PreparationError(f"PLE hashing schema does not match: {key}")
    for number, header in enumerate(main):
        if header.values.get("split.no", 0) != number or header.values.get("split.count", 1) != len(main):
            raise PreparationError("Source GGUF split metadata is out of order or incomplete")
        if header.values.get("split.tensors.count", len(tensors)) != len(tensors):
            raise PreparationError("Source GGUF total tensor count does not match")
        architecture = header.values.get("general.architecture")
        if architecture not in (None, "qwen4exp"):
            raise PreparationError("Source shard architecture does not match")
    if ple.values.get("split.count", 1) != 1 or ple.values.get("split.no", 0) != 0:
        raise PreparationError("Replacement PLE must be a standalone GGUF")
    kept = []
    next_offset = 0
    for tensor in main[0].tensors:
        if tensor["name"] != PLE:
            kept.append({**tensor, "offset": next_offset})
            next_offset = align(next_offset + tensor["bytes"], main[0].alignment)
    count = len(main) + 1
    plans = [{"header": encode_header(split_entries(main[0], 0, count, len(tensors)), kept, main[0].alignment),
              "tensors": kept, "source": main[0], "mode": "repack", "payloadBytes": next_offset}]
    for number, header in enumerate(main[1:], 1):
        encoded = encode_header(split_entries(header, number, count, len(tensors)), header.tensors, header.alignment)
        if len(encoded) != header.data_offset:
            raise PreparationError("Source split metadata cannot be patched without moving payloads")
        plans.append({"header": encoded, "tensors": header.tensors, "source": header, "mode": "clone"})
    last = encode_header(split_entries(ple, count - 1, count, len(tensors), minimal=True),
                         ple.tensors, ple.alignment, data_offset=ple.data_offset)
    plans.append({"header": last, "tensors": ple.tensors, "source": ple, "mode": "clone"})
    return {"main": main, "ple": ple, "parts": plans, "tensorCount": len(tensors),
            "pleSchema": {key: main[0].values[key] for key in sorted(original_keys)},
            "headerOnly": header_only}


def plan_replacement(sources, ple_source, *, header_only=False, expected_shape=EXPECTED_SHAPE):
    plan = _plan(sources, ple_source, header_only=header_only, expected_shape=expected_shape)
    return {"version": 1, "headerOnly": header_only, "tensorCount": plan["tensorCount"],
            "mainTensorCount": plan["tensorCount"] - 1, "outputShardCount": len(plan["parts"]),
            "copiedMainBytes": sum(t["bytes"] for t in plan["parts"][0]["tensors"]),
            "plePrecision": "BF16", "pleDimensions": plan["ple"].tensors[0]["dims"],
            "pleSchema": plan["pleSchema"],
            "parts": [{"mode": part["mode"], "source": str(part["source"].path),
                       "sourceDataOffset": part["source"].data_offset, "outputDataOffset": len(part["header"]),
                       "tensorCount": len(part["tensors"]), "sourceMinimumBytes": part["source"].minimum_size}
                      for part in plan["parts"]]}


def clone_file(source, destination, *, allow_copy=False):
    """Clone on APFS; a full copy requires an explicit opt-in and free space."""
    if os.path.lexists(destination):
        raise PreparationError("Clone destination already exists")
    if sys.platform == "darwin":
        library = ctypes.CDLL(None, use_errno=True)
        clone = library.clonefile
        clone.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
        clone.restype = ctypes.c_int
        if clone(os.fsencode(source), os.fsencode(destination), 0) == 0:
            return "apfs-clone"
        failure = ctypes.get_errno()
        if failure not in {errno.EXDEV, errno.ENOTSUP, errno.EINVAL}:
            raise OSError(failure, os.strerror(failure), str(destination))
    if not allow_copy:
        raise PreparationError("APFS cloning is required; no large payload copy was started")
    if shutil.disk_usage(Path(destination).parent).free < Path(source).stat().st_size + RESERVE:
        raise PreparationError("Insufficient disk space for the explicitly allowed fallback copy")
    shutil.copyfile(source, destination)
    return "guarded-copy"


def _no_cache(stream):
    if sys.platform == "darwin":
        import fcntl
        try:
            fcntl.fcntl(stream.fileno(), 48, 1)  # Darwin F_NOCACHE.
        except OSError:
            pass


def tensor_hash(path, tensor):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        _no_cache(source)
        source.seek(tensor["absoluteOffset"])
        remaining = tensor["bytes"]
        while remaining:
            data = source.read(min(CHUNK, remaining))
            if not data:
                raise PreparationError("Tensor became truncated while hashing")
            digest.update(data)
            remaining -= len(data)
    return digest.hexdigest()


def atomic_publish(source, destination):
    """Publish a prepared directory atomically, refusing every existing target."""
    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        rename = library.renameatx_np
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        result = rename(-2, os.fsencode(source), -2, os.fsencode(destination), 4)  # RENAME_EXCL.
    elif sys.platform.startswith("linux") and hasattr(library, "renameat2"):
        rename = library.renameat2
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        result = rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1)  # NOREPLACE.
    else:
        raise PreparationError("This platform cannot publish a directory exclusively and atomically")
    if result:
        failure = ctypes.get_errno()
        raise OSError(failure, os.strerror(failure), str(destination))


def build_replacement(sources, ple_source, output, *, cloner=None, allow_copy=False,
                      expected_shape=EXPECTED_SHAPE, progress=None):
    """Build and verify a distinct split GGUF; return its durable receipt."""
    output = Path(output).expanduser().absolute()
    if os.path.lexists(output) or not output.parent.is_dir() or output.name in {"", ".", ".."}:
        raise PreparationError("Output must be a new directory in an existing parent")
    plan = _plan(sources, ple_source, expected_shape=expected_shape)
    originals = [header.source for header in [*plan["main"], plan["ple"]]]
    # Resolve the destination parent before writing, rejecting an output within
    # an input file or any spelling that could alias the original model paths.
    if any(output.resolve() == Path(record["path"]).resolve() for record in originals):
        raise PreparationError("Output aliases an input")
    first = plan["main"][0].path.name
    base = re.sub(r"-\d{5}-of-\d{5}(?=\.gguf$)", "", first).removesuffix(".gguf") + "-BF16-PLE"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,180}", base):
        raise PreparationError("Source name cannot safely name the output shards")
    copied_bytes = sum(tensor["bytes"] for tensor in plan["parts"][0]["tensors"])
    if shutil.disk_usage(output.parent).free < copied_bytes + RESERVE:
        raise PreparationError("Insufficient disk space for the repacked first shard and reserve")
    clone = cloner or (lambda source, target: clone_file(source, target, allow_copy=allow_copy))
    stage = Path(tempfile.mkdtemp(prefix=".splash-ple-", dir=output.parent))
    receipt = {"version": 1, "createdAt": time.time(), "inputs": originals,
               "inputHeaders": [{"path": str(header.path), "sha256": header.header_sha256,
                                 "dataOffset": header.data_offset, "minimumBytes": header.minimum_size}
                                for header in [*plan["main"], plan["ple"]]],
               "plePrecision": "BF16", "pleSchema": plan["pleSchema"], "tensors": [],
               "outputPaths": [], "outputs": [], "mainTensorParityVerified": False}
    notify = progress or (lambda event: None)
    try:
        for number, part in enumerate(plan["parts"], 1):
            for record in originals:
                unchanged(record)
            name = f"{base}-{number:05d}-of-{len(plan['parts']):05d}.gguf"
            destination = stage / name
            notify({"phase": part["mode"], "part": number, "parts": len(plan["parts"]), "name": name})
            source_header = part["source"]
            input_by_name = {tensor["name"]: tensor for tensor in source_header.tensors}
            input_hashes = {}
            if part["mode"] == "repack":
                with source_header.path.open("rb") as source, destination.open("xb") as target:
                    _no_cache(target)
                    target.write(part["header"])
                    target.truncate(len(part["header"]) + part["payloadBytes"])
                    for tensor in part["tensors"]:
                        original = input_by_name[tensor["name"]]
                        source.seek(original["absoluteOffset"])
                        target.seek(len(part["header"]) + tensor["offset"])
                        digest = hashlib.sha256()
                        remaining = tensor["bytes"]
                        while remaining:
                            data = source.read(min(CHUNK, remaining))
                            if not data:
                                raise PreparationError("Source became truncated while repacking")
                            target.write(data)
                            digest.update(data)
                            remaining -= len(data)
                        input_hashes[tensor["name"]] = digest.hexdigest()
                    target.flush()
                    os.fsync(target.fileno())
                method = "repack"
            else:
                method = clone(source_header.path, destination) or "injected-clone"
                info = destination.lstat()
                if (not stat.S_ISREG(info.st_mode)
                        or (info.st_dev, info.st_ino) in {(record["device"], record["inode"]) for record in originals}):
                    raise PreparationError("Cloner must create an independent regular file")
                with destination.open("r+b") as target:
                    target.write(part["header"])
                    target.flush()
                    os.fsync(target.fileno())
            actual = Header(destination)
            if actual.data_offset != len(part["header"]) or len(actual.tensors) != len(part["tensors"]):
                raise PreparationError("Output GGUF header does not describe the planned tensor layout")
            expected = {tensor["name"]: tensor for tensor in part["tensors"]}
            for tensor in actual.tensors:
                wanted = expected.get(tensor["name"])
                if wanted is None or any(tensor[key] != wanted[key] for key in ("dims", "type", "bytes", "offset")):
                    raise PreparationError("Output changed a tensor's type, dimensions or offset")
                notify({"phase": "verify", "part": number, "name": tensor["name"]})
                source_hash = input_hashes.get(tensor["name"]) or tensor_hash(source_header.path, input_by_name[tensor["name"]])
                result_hash = tensor_hash(destination, tensor)
                if source_hash != result_hash:
                    raise PreparationError("Output tensor SHA-256 mismatch: " + tensor["name"])
                receipt["tensors"].append({"name": tensor["name"], "dims": tensor["dims"], "type": tensor["type"],
                                           "bytes": tensor["bytes"], "inputSha256": source_hash,
                                           "outputSha256": result_hash, "part": number})
            receipt["outputPaths"].append(str(output / name))
            receipt["outputs"].append({"path": str(output / name), "bytes": destination.stat().st_size,
                                       "dataOffset": actual.data_offset, "headerSha256": actual.header_sha256,
                                       "method": method})
        for record in originals:
            unchanged(record)
        main_records = sorted((tensor for tensor in receipt["tensors"] if tensor["name"] != PLE),
                              key=lambda tensor: tensor["name"])
        if len(main_records) != plan["tensorCount"] - 1:
            raise PreparationError("Output did not preserve the complete main tensor set")
        receipt["mainTensorDigest"] = hashlib.sha256(json.dumps(
            [{key: item[key] for key in ("name", "dims", "type", "bytes", "inputSha256")}
             for item in main_records], sort_keys=True).encode()).hexdigest()
        receipt["mainTensorParityVerified"] = True
        receipt["mainTensorCount"] = len(main_records)
        receipt["sourceChecksPassed"] = True
        receipt["ple"] = next(tensor for tensor in receipt["tensors"] if tensor["name"] == PLE)
        receipt["completedAt"] = time.time()
        with (stage / "receipt.json").open("x", encoding="utf-8") as handle:
            json.dump(receipt, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        atomic_publish(stage, output)
        return receipt
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", action="append", required=True, type=Path,
                        help="first source shard, or every shard in order using repeated --source")
    parser.add_argument("--ple", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="new output directory (required unless --plan-only)")
    parser.add_argument("--plan-only", action="store_true", help="check bounded headers without reading tensor payloads")
    parser.add_argument("--allow-copy", action="store_true", help="explicitly allow full-copy fallback when APFS clone is unavailable")
    args = parser.parse_args()
    sources = args.source[0] if len(args.source) == 1 else args.source
    if args.plan_only:
        result = plan_replacement(sources, args.ple, header_only=True)
    else:
        if args.output is None:
            parser.error("--output is required for preparation")
        result = build_replacement(sources, args.ple, args.output, allow_copy=args.allow_copy)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
