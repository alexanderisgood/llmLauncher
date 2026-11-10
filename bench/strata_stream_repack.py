#!/usr/bin/env python3
"""Lossless, bounded-storage preparation of the pinned Strata Q4 Metal model.

Plans from small GGUF headers, then streams each pinned source shard directly
into its final tensor locations. No complete source-shard copy is retained.
Whole source SHA-256 and per-tensor output SHA-256 must both pass before the
files are published. This changes layout only, never tensor bytes or types.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
STRATA = ROOT / "bench/runtimes/strata-0.1.44.1"
REVISION = "38bb39ee97821de2c9009abb7e93950eec396e66"
BASE = f"https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF/resolve/{REVISION}/UD-Q4_K_XL/"
PINS = [
    (10946624, "4448186216b3af4cc558bbce2c3213f01608f8f8b2e5267a9767971dd3ec8082"),
    (49859583136, "3f342f1c1580473f1ee94ddd5b28206e8c07a70fa1a366f59d1d6c922919a6c9"),
    (49376141504, "56758f40269cad5cd9b0d3d6fbae0f40f6d5be6de49e4ab392dbe83157d9cbd3"),
    (12087983520, "753bda48b98ba4f1636134a90a967de1b2d3908a236c026e464777342e53510a"),
]
SOURCES = [{"name": f"Qwen3.8-Flash-Next-UD-Q4_K_XL-{i:05d}-of-00004.gguf",
            "size": size, "sha256": sha} for i, (size, sha) in enumerate(PINS, 1)]
ALIGN = 16384
CHUNK = 16 << 20
RESERVE = 10 << 30


class PreparationPaused(Exception):
    """An owned preparation window ended at a durable resumable checkpoint."""


def upstream():
    path = STRATA / "metal/tools/metal_repack.py"
    spec = importlib.util.spec_from_file_location("strata_upstream_repack", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prefix(source, count):
    count = min(count, source["size"])
    request = urllib.request.Request(BASE + source["name"], headers={
        "Range": f"bytes=0-{count - 1}", "Accept-Encoding": "identity"})
    with urllib.request.urlopen(request, timeout=60) as response:
        if response.headers.get("Content-Encoding", "identity") != "identity":
            raise ValueError("Encoded source response")
        if response.status == 206:
            if response.headers.get("Content-Range") != f"bytes 0-{count - 1}/{source['size']}":
                raise ValueError("Incorrect source range")
        elif response.status != 200 or count != source["size"]:
            raise ValueError("Source ignored the bounded range request")
        body = response.read(count + 1)
    if len(body) != count:
        raise ValueError("Incorrect header byte count")
    if count == source["size"] and hashlib.sha256(body).hexdigest() != source["sha256"]:
        raise ValueError("Complete small shard checksum mismatch")
    return body


def headers(work, repack, sources=SOURCES):
    readers = []
    for i, source in enumerate(sources):
        path = work / f"header-{i}.gguf"
        if path.exists() or path.is_symlink():
            if owned_regular(path).st_size > 32 << 20:
                raise ValueError("Unexpectedly large cached source header")
        count = min(1 << 20, source["size"])
        while True:
            if not path.exists() or path.stat().st_size < count:
                body = prefix(source, count)
                temporary = path.with_suffix(".fetch")
                with temporary.open("xb") as handle:
                    handle.write(body)
                os.replace(temporary, path)
            try:
                reader = repack.Reader(path)
                if reader.data > path.stat().st_size:
                    reader.f.close()
                    raise struct.error("Incomplete aligned header")
                break
            except (struct.error, UnicodeError):
                if count >= min(32 << 20, source["size"]):
                    raise
                count = min(count * 2, source["size"])
        reader.source_index = i
        reader.prefix_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        reader.prefix_bytes = path.stat().st_size
        readers.append(reader)
    return readers


def layout(repack, metadata, tensors, *, pad_tail=True):
    kv = [raw for key, raw in metadata if not key.startswith("split.") and key != "general.alignment"]
    kv.append(repack.gguf_str("general.alignment") + struct.pack("<II", 4, ALIGN))
    infos, ordered, offset = [], [], 0
    for original in tensors:
        tensor = {**original, "new": offset}
        ordered.append(tensor)
        infos.append(repack.gguf_str(tensor["name"]) + struct.pack("<I", len(tensor["dims"])) +
                     struct.pack(f"<{len(tensor['dims'])}Q", *tensor["dims"]) +
                     struct.pack("<IQ", tensor["type"], offset))
        offset = (offset + tensor["bytes"] + ALIGN - 1) // ALIGN * ALIGN
    head = struct.pack("<4sIQQ", b"GGUF", 3, len(ordered), len(kv)) + b"".join(kv) + b"".join(infos)
    data = (len(head) + ALIGN - 1) // ALIGN * ALIGN
    if not pad_tail and ordered:
        offset = ordered[-1]["new"] + ordered[-1]["bytes"]
    return {"header": head + bytes(data - len(head)), "data": data, "size": data + offset, "tensors": ordered}


def plans(repack, readers, sources=SOURCES):
    every, names = [], set()
    for reader, source in zip(readers, sources, strict=True):
        end = reader.data
        for tensor in sorted(reader.tensors, key=lambda t: t["abs"]):
            if tensor["name"] in names or tensor["abs"] < end or tensor["bytes"] <= 0:
                raise ValueError("Duplicate or overlapping source tensor")
            end = tensor["abs"] + tensor["bytes"]
            if end > source["size"] or not 1 <= len(tensor["dims"]) <= 4:
                raise ValueError("Tensor outside its pinned source")
            names.add(tensor["name"])
            every.append(tensor)
    # Preserve upstream's dense order across shards, then its expert order.
    every = [t for r in readers for t in r.tensors]
    ple = [t for t in every if t["name"] == repack.PLE]
    if len(ple) != 1:
        raise ValueError("Expected exactly one unchanged n-gram tensor")
    keep = [t for t in every if t["name"] != repack.PLE]
    dense = [t for t in keep if "_exps." not in t["name"]]
    role = {"ffn_gate_exps": 0, "ffn_up_exps": 1, "ffn_down_exps": 2}

    def key(tensor):
        match = re.match(r"blk\.(\d+)\.", tensor["name"])
        return (int(match.group(1)) if match else -1, role.get(tensor["name"].split(".")[2], 9))

    experts = sorted((t for t in keep if "_exps." in t["name"]), key=key)
    return {"native": layout(repack, readers[0].kv, dense + experts),
            # NgramStore requires the file to end exactly after the PLE table.
            "ple": layout(repack, readers[0].kv, ple, pad_tail=False)}


def expert_identity(outputs, expected_layers=48, expected_experts=512):
    layers = {}
    for tensor in outputs["native"]["tensors"]:
        match = re.fullmatch(r"blk\.(\d+)\.(ffn_gate_exps|ffn_up_exps|ffn_down_exps)\.weight", tensor["name"])
        if match:
            if len(tensor["dims"]) != 3 or tensor["dims"][-1] != expected_experts:
                raise ValueError("Expected the original full-expert tensor dimensions")
            layers.setdefault(int(match.group(1)), {})[match.group(2)] = tensor["type"]
    roles = {"ffn_gate_exps", "ffn_up_exps", "ffn_down_exps"}
    if set(layers) != set(range(expected_layers)) or any(set(row) != roles for row in layers.values()):
        raise ValueError("Expected every expert role in every original layer")
    if any(row["ffn_gate_exps"] != row["ffn_up_exps"] for row in layers.values()):
        raise ValueError("Gate/up quantization mismatch")
    counts = Counter((row["ffn_gate_exps"], row["ffn_down_exps"]) for row in layers.values())
    return {"layers": len(layers), "expertsPerLayer": expected_experts,
            "quantizationCombinations": [{"gateUpType": gu, "downType": dn, "layers": n}
                                         for (gu, dn), n in sorted(counts.items())]}


def source_segments(outputs, readers, sources):
    """Retain the small original header/padding gaps, making each source reconstructible."""
    result, gap_sizes = [], []
    for index, source in enumerate(sources):
        tensors = []
        for target, plan in outputs.items():
            for tensor in plan["tensors"]:
                if tensor["src"] is readers[index]:
                    tensors.append({"start": tensor["abs"], "length": tensor["bytes"],
                                    "target": target, "offset": plan["data"] + tensor["new"],
                                    "name": tensor["name"]})
        segments, cursor, gap_offset = [], 0, 0
        for tensor in sorted(tensors, key=lambda t: t["start"]):
            if tensor["start"] > cursor:
                length = tensor["start"] - cursor
                segments.append({"start": cursor, "length": length, "target": f"gap-{index}", "offset": gap_offset})
                gap_offset += length
            segments.append(tensor)
            cursor = tensor["start"] + tensor["length"]
        if cursor < source["size"]:
            segments.append({"start": cursor, "length": source["size"] - cursor,
                             "target": f"gap-{index}", "offset": gap_offset})
            gap_offset += source["size"] - cursor
        if gap_offset > 64 << 20:
            raise ValueError("Unexpectedly large non-tensor source area")
        if sum(s["length"] for s in segments) != source["size"]:
            raise ValueError("Source intervals do not cover every original byte")
        result.append(segments)
        gap_sizes.append(gap_offset)
    return result, gap_sizes


def write_at(fd, body, offset):
    view = memoryview(body)
    while view:
        count = os.pwrite(fd, view, offset)
        if count <= 0:
            raise OSError("Short output write")
        view, offset = view[count:], offset + count


def reconstruct_hash(segments, handles):
    """Verify the pinned whole-source hash directly from actual prepared tensor bytes."""
    whole, tensors = hashlib.sha256(), {}
    for segment in segments:
        offset, left = segment["offset"], segment["length"]
        tensor = hashlib.sha256() if "name" in segment else None
        while left:
            body = os.pread(handles[segment["target"]].fileno(), min(CHUNK, left), offset)
            if not body:
                raise ValueError("Prepared file is truncated")
            whole.update(body)
            if tensor is not None:
                tensor.update(body)
            offset, left = offset + len(body), left - len(body)
        if tensor is not None:
            tensors[segment["name"]] = tensor.hexdigest()
    return {"sha256": whole.hexdigest(), "tensorSha256": tensors}


def reconstruct_prefix(segments, handles, limit):
    digest = hashlib.sha256()
    consumed = 0
    for segment in segments:
        left = min(segment["length"], max(0, limit - segment["start"]))
        offset = segment["offset"]
        while left:
            body = os.pread(handles[segment["target"]].fileno(), min(CHUNK, left), offset)
            if not body:
                raise ValueError("Prepared prefix is truncated")
            digest.update(body)
            consumed += len(body)
            offset, left = offset + len(body), left - len(body)
        if consumed == limit:
            return digest
    if consumed != limit:
        raise ValueError("Prepared prefix does not cover its checkpoint")
    return digest


def body_response(source, start=0):
    headers = {"Accept-Encoding": "identity"}
    if start:
        headers["Range"] = f"bytes={start}-{source['size'] - 1}"
    request = urllib.request.Request(BASE + source["name"], headers=headers)
    return urllib.request.urlopen(request, timeout=120)


def ingest(source, reader, segments, handles, work, opener=body_response, resume=None, checkpoint=None, deadline=None):
    whole, head = hashlib.sha256(), hashlib.sha256()
    position, cursor, synced = 0, 0, 0
    if resume is not None:
        position = resume.get("position")
        if type(position) is not int or not 0 < position < source["size"]:
            raise ValueError("Invalid partial-source checkpoint")
        whole = reconstruct_prefix(segments, handles, position)
        if whole.hexdigest() != resume.get("sha256"):
            raise ValueError("Prepared prefix differs from its durable checkpoint")
        head = reconstruct_prefix(segments, handles, min(position, reader.prefix_bytes))
        if position >= reader.prefix_bytes and head.hexdigest() != reader.prefix_sha256:
            raise ValueError("Resumed prefix does not match the pinned header plan")
        synced = position
    request_start = position
    opened = opener(source, position) if position else opener(source)
    with opened as response:
        if response.headers.get("Content-Encoding", "identity") != "identity":
            raise ValueError("Encoded source body")
        if response.status == 206:
            if response.headers.get("Content-Range") != f"bytes {request_start}-{source['size'] - 1}/{source['size']}":
                raise ValueError("Incorrect whole-source range")
        elif response.status != 200 or request_start:
            raise ValueError("Unsuccessful source body response")
        length = response.headers.get("Content-Length")
        if length is not None and int(length) != source["size"] - request_start:
            raise ValueError("Incorrect source length")
        while position < source["size"]:
            body = response.read(min(CHUNK, source["size"] - position))
            if not body:
                raise ValueError("Source download ended early")
            if shutil.disk_usage(work).free < RESERVE + len(body):
                raise OSError("Protected free-disk reserve reached")
            whole.update(body)
            if position < reader.prefix_bytes:
                head.update(body[:reader.prefix_bytes - position])
            end = position + len(body)
            while cursor < len(segments) and segments[cursor]["start"] + segments[cursor]["length"] <= position:
                cursor += 1
            index = cursor
            while index < len(segments) and segments[index]["start"] < end:
                segment = segments[index]
                begin = max(position, segment["start"])
                stop = min(end, segment["start"] + segment["length"])
                write_at(handles[segment["target"]].fileno(), memoryview(body)[begin - position:stop - position],
                         segment["offset"] + begin - segment["start"])
                index += 1
            position = end
            pause = deadline is not None and time.monotonic() >= deadline and position < source["size"]
            if position - synced >= 1 << 30 or pause:
                for handle in handles.values():
                    os.fsync(handle.fileno())
                synced = position
                if checkpoint is not None:
                    checkpoint({"position": position, "sha256": whole.hexdigest()})
                print(f"[stream] {source['name']}: {position / 1e9:.1f}/{source['size'] / 1e9:.1f} GB", flush=True)
            if pause:
                raise PreparationPaused("Preparation paused after a durable source-prefix checkpoint")
        if response.read(1):
            raise ValueError("Source download exceeds pinned length")
    if whole.hexdigest() != source["sha256"] or head.hexdigest() != reader.prefix_sha256:
        raise ValueError("Source checksum or header/body binding failed")
    for handle in handles.values():
        os.fsync(handle.fileno())
    proof = reconstruct_hash(segments, handles)
    if proof["sha256"] != source["sha256"]:
        raise ValueError("Prepared tensor bytes do not reconstruct the pinned source")
    return proof


def owned_regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError("Preparation path is not an owned regular file")
    return info


def write_json(path, value):
    if path.exists() or path.is_symlink():
        owned_regular(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def download(work, repack, readers, outputs, sources=SOURCES, opener=body_response, max_seconds=None):
    segments, gaps = source_segments(outputs, readers, sources)
    signature_data = {"sources": sources, "prefixes": [r.prefix_sha256 for r in readers],
                      "outputs": {key: {"size": p["size"], "header": hashlib.sha256(p["header"]).hexdigest()}
                                  for key, p in outputs.items()}, "segments": segments}
    signature = hashlib.sha256(json.dumps(signature_data, sort_keys=True).encode()).hexdigest()
    state_path = work / "stream-state.json"
    state = None
    if state_path.exists() or state_path.is_symlink():
        owned_regular(state_path)
        state = json.loads(state_path.read_text())
        if state.get("schemaVersion") != 1 or state.get("planSha256") != signature:
            raise ValueError("Existing preparation journal belongs to a different layout")
    total = sum(plan["size"] for plan in outputs.values()) + sum(gaps)
    if state is None and shutil.disk_usage(work).free < total + RESERVE:
        raise OSError("Prepared model plus protected disk reserve does not fit")
    specs = {key: {"path": work / f"{key}.gguf.part", "size": plan["size"]} for key, plan in outputs.items()}
    specs.update({f"gap-{i}": {"path": work / f"gap-{i}.bin", "size": size} for i, size in enumerate(gaps)})
    handles, paths, created = {}, {}, []
    started = time.monotonic()
    deadline = started + max_seconds if max_seconds is not None else None
    try:
        for key, spec in specs.items():
            path = spec["path"]
            final = work / f"{key}.gguf" if key in outputs else None
            if state is None:
                if path.exists() or path.is_symlink() or (final is not None and (final.exists() or final.is_symlink())):
                    raise FileExistsError("Unowned preparation output already exists")
                handle = path.open("x+b", buffering=0)
                created.append((path, os.fstat(handle.fileno()).st_ino))
                handle.truncate(spec["size"])
                if key in outputs:
                    write_at(handle.fileno(), outputs[key]["header"], 0)
            else:
                if final is not None and final.exists():
                    if path.exists() and path.stat().st_ino != final.stat().st_ino:
                        raise ValueError("Conflicting published and partial files")
                    path = final
                info = owned_regular(path)
                if [info.st_dev, info.st_ino] != state["fileIdentities"][key] or info.st_size != spec["size"]:
                    raise ValueError("Preparation file identity changed")
                handle = path.open("r+b", buffering=0)
                if key in outputs and os.pread(handle.fileno(), len(outputs[key]["header"]), 0) != outputs[key]["header"]:
                    handle.close()
                    raise ValueError("Prepared GGUF header changed")
            repack.nocache(handle)
            handles[key], paths[key] = handle, path
        if state is None:
            state = {"schemaVersion": 1, "planSha256": signature, "stage": "downloading", "verified": {},
                     "fileIdentities": {key: [os.fstat(h.fileno()).st_dev, os.fstat(h.fileno()).st_ino]
                                        for key, h in handles.items()}}
            write_json(state_path, state)
        for index, source in enumerate(sources):
            if deadline is not None and time.monotonic() >= deadline:
                raise PreparationPaused("Preparation window ended before the next source")
            if str(index) in state["verified"]:
                proof = reconstruct_hash(segments[index], handles)
                if proof["sha256"] == source["sha256"]:
                    state["verified"][str(index)] = proof
                    print(f"[stream] verified existing source {index + 1}/{len(sources)}", flush=True)
                    continue
                if any(paths[key].name == f"{key}.gguf" for key in outputs):
                    raise ValueError("Published model failed source reconstruction; files left unchanged")

            def checkpoint(progress):
                state.update(stage="downloading", active={"sourceIndex": index, **progress})
                write_json(state_path, state)

            active = state.get("active")
            resume = active if isinstance(active, dict) and active.get("sourceIndex") == index else None
            proof = ingest(source, readers[index], segments[index], handles, work, opener, resume, checkpoint, deadline)
            state["verified"][str(index)] = proof
            state["active"] = None
            write_json(state_path, state)
            print(f"[stream] source {index + 1}/{len(sources)}: complete SHA-256 and tensor read-back passed", flush=True)
        # Canonical upstream padding is zero; restore it independently of source gaps.
        for key, plan in outputs.items():
            cursor = plan["data"]
            for tensor in plan["tensors"]:
                start = plan["data"] + tensor["new"]
                if start > cursor:
                    write_at(handles[key].fileno(), bytes(start - cursor), cursor)
                cursor = start + tensor["bytes"]
            if cursor < plan["size"]:
                write_at(handles[key].fileno(), bytes(plan["size"] - cursor), cursor)
            os.fsync(handles[key].fileno())
        state["stage"] = "publishing"
        write_json(state_path, state)
        result = {"schemaVersion": 1, "status": "verified", "sourceRevision": REVISION,
                  "planSha256": signature, "sources": sources, "sourceProofs": state["verified"], "outputs": {}}
        for key, plan in outputs.items():
            handle = handles[key]
            handle.seek(0)
            digest = hashlib.sha256()
            while body := handle.read(CHUNK):
                digest.update(body)
            final = work / f"{key}.gguf"
            partial = specs[key]["path"]
            if paths[key] != final:
                os.link(partial, final)  # never overwrites an existing file
                partial.unlink()
            elif partial.exists():
                if partial.stat().st_ino != final.stat().st_ino:
                    raise ValueError("Conflicting partial file during publication")
                partial.unlink()
            result["outputs"][key] = {"path": str(final), "bytes": plan["size"], "sha256": digest.hexdigest(),
                                       "tensors": len(plan["tensors"])}
        result.update(elapsedSeconds=time.monotonic() - started, freeBytesAfter=shutil.disk_usage(work).free)
        write_json(work / "verified-model.json", result)
        state["stage"] = "complete"
        write_json(state_path, state)
        return result
    finally:
        for handle in handles.values():
            handle.close()
        if state is None:
            for path, inode in created:
                if path.exists() and not path.is_symlink() and path.stat().st_ino == inode:
                    path.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--download", action="store_true", help="stream full weights after reviewing the header plan")
    parser.add_argument("--max-seconds", type=int, help="pause the transfer at a durable checkpoint to share test windows")
    args = parser.parse_args(argv)
    if args.max_seconds is not None and args.max_seconds < 1:
        parser.error("--max-seconds must be positive")
    work = args.work.absolute()
    if work.is_symlink() or work.resolve() != work:
        raise ValueError("Preparation directory must not be a link")
    work.mkdir(parents=True, exist_ok=True)
    repack = upstream()
    readers = headers(work, repack)
    try:
        outputs = plans(repack, readers)
        receipt = {"sourceRevision": REVISION, "sources": SOURCES,
                   "expertIdentity": expert_identity(outputs),
                   "upstreamRepackSha256": hashlib.sha256((STRATA / "metal/tools/metal_repack.py").read_bytes()).hexdigest(),
                   "outputs": {key: {"bytes": value["size"], "tensorCount": len(value["tensors"]),
                                      "headerSha256": hashlib.sha256(value["header"]).hexdigest()}
                               for key, value in outputs.items()},
                   "freeBytes": shutil.disk_usage(work).free, "reserveBytes": RESERVE}
        receipt["requiredBytesWithReserve"] = sum(p["size"] for p in outputs.values()) + RESERVE
        print(json.dumps(receipt, indent=2), flush=True)
        if args.download:
            import sys
            sys.path.insert(0, str(ROOT))
            from bench import harness
            with harness.bench_run("Strata lossless direct Q4 preparation", minimum_headroom_gb=20):
                running = subprocess.run(["pgrep", "-x", "strata"], capture_output=True, text=True)
                if running.returncode == 0:
                    raise RuntimeError("Stop the live Strata engine before preparing weights")
                if running.returncode != 1:
                    raise RuntimeError("Could not confirm that Strata is stopped")
                try:
                    result = download(work, repack, readers, outputs, max_seconds=args.max_seconds)
                except PreparationPaused:
                    result = {"status": "paused", "progressJournal": str(work / "stream-state.json")}
            print(json.dumps({key: value for key, value in result.items() if key != "sourceProofs"}, indent=2), flush=True)
    finally:
        for reader in readers:
            reader.f.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
