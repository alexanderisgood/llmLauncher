#!/usr/bin/env python3
"""Recover pinned Splash Q4 downloads with durable, bounded HTTP ranges.

The failed second shard is recovered first under Hugging Face's exact local
file lock. Other shards and the pinned draft are inspected only after the
original downloader exits. Active Xet partials and BF16 transfers are untouched.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import quote
import uuid

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
from tools import prepare_splash_flash_bf16 as pins

CHUNK_BYTES = 256 * 1024**2
CONTENT_RANGE = re.compile(r"bytes (\d+)-(\d+)/(\d+)")


@dataclass(frozen=True)
class Recovery:
    root: Path = Path.home() / ".lmstudio/models/bartowski/Qwen3.8-Flash-Next-GGUF"
    draft_root: Path = Path.home() / ".lmstudio/models/incoai/Qwen3.8-Flash-Next-DFlash2"
    runtime: Path = WORKSPACE / "bench/runtimes/splash-1.4.0"
    receipt: Path = WORKSPACE / "bench/results/20261021-splash-flash-download-recovery.json"
    completion_receipt: Path = WORKSPACE / "bench/results/20261021-splash-flash-q4-download.json"
    original_pid: int = 7500
    target_files: tuple[pins.Artifact, ...] = pins.Q4_FILES
    draft_files: tuple[pins.Artifact, ...] = pins.DRAFT_FILES
    chunk_bytes: int = CHUNK_BYTES
    poll_seconds: float = 15
    retries: int = 8


class ProtocolError(ValueError):
    pass


class TransientError(RuntimeError):
    pass


class Progress:
    def __init__(self, config):
        self.config = config
        self.value = {"schemaVersion": 1, "status": "running", "pid": os.getpid(),
            "startedAt": pins.timestamp(), "targetRepo": pins.Q4_REPO, "revision": pins.Q4_REVISION,
            "draftRepo": pins.DRAFT_REPO, "draftRevision": pins.DRAFT_REVISION,
            "originalPid": config.original_pid, "files": []}
        self.last_write = 0.0

    def update(self, phase=None, **values):
        if phase:
            print("Splash download recovery: " + phase, flush=True)
            self.value["phase"] = phase
        self.value.update(values)
        self.value["updatedAt"] = pins.timestamp()
        pins.atomic_json(self.config.receipt, self.value)
        self.last_write = time.monotonic()

    def hashing(self, path, size, total):
        if time.monotonic() - self.last_write > 5 or size == total:
            self.update(hashProgress={"path": str(path), "readBytes": size, "totalBytes": total})


@contextmanager
def hf_lock(root, artifact):
    # This is the same path and implementation held by hf_hub_download.
    from huggingface_hub._local_folder import get_local_download_paths
    from huggingface_hub.utils import WeakFileLock
    paths = get_local_download_paths(Path(root), artifact.path)
    with WeakFileLock(paths.lock_path):
        yield paths


def write_hf_metadata(paths, revision, artifact):
    # Write the SDK's documented local metadata layout while its exact file
    # lock is already held; calling its writer here would reacquire the lock.
    temporary = paths.metadata_path.with_name(paths.metadata_path.name + ".launcher-writing")
    with temporary.open("w") as handle:
        handle.write(f"{revision}\n{artifact.digest}\n{time.time()}\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, paths.metadata_path)


def immutable_url(repo, revision, artifact):
    return (f"https://huggingface.co/{repo}/resolve/{revision}/{quote(artifact.path, safe='/')}"
            f"?download=true&launcher_recovery={uuid.uuid4().hex}")


def read_range(client, repo, revision, artifact, start, end, target):
    expected = end - start + 1
    with client.stream("GET", immutable_url(repo, revision, artifact),
            headers={"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"}) as response:
        if response.status_code in {403, 408, 429, 500, 502, 503, 504}:
            raise TransientError(f"HTTP {response.status_code}; retrying this range with a fresh immutable resolve URL")
        if response.status_code != 206:
            raise ProtocolError(f"Expected HTTP 206 for range {start}-{end}; received {response.status_code}")
        parsed = CONTENT_RANGE.fullmatch(response.headers.get("Content-Range", ""))
        if not parsed or tuple(map(int, parsed.groups())) != (start, end, artifact.size):
            raise ProtocolError("Server returned an incorrect Content-Range")
        length = response.headers.get("Content-Length")
        if length is not None and (not length.isdigit() or int(length) != expected):
            raise ProtocolError("Server returned an incorrect range Content-Length")
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise ProtocolError("Compressed transfer cannot establish byte offsets")
        for entry in [*getattr(response, "history", []), response]:
            commit = entry.headers.get("X-Repo-Commit")
            if commit is not None and commit != revision:
                raise ProtocolError("Hub response does not match the pinned revision")
        received = 0
        digest = hashlib.sha256()
        for data in response.iter_bytes(chunk_size=1024**2):
            if received + len(data) > expected:
                raise ProtocolError("Range body exceeds its declared byte bounds")
            target.write(data)
            digest.update(data)
            received += len(data)
        if received != expected:
            raise TransientError("Range body ended before its declared byte bounds")
        return digest.hexdigest()


def partial_manifest(repo, revision, artifact):
    return {"schemaVersion": 1, "repo": repo, "revision": revision,
        "file": artifact.public(), "committedBytes": 0, "chunks": []}


def open_partial(paths, repo, revision, artifact):
    partial = paths.metadata_path.with_name(".launcher-http-" + artifact.digest + ".partial")
    ledger = partial.with_suffix(".json")
    if partial.is_symlink() or ledger.is_symlink():
        raise ProtocolError("Recovery partial or ledger must not be a symlink")
    state = pins.read_json(ledger)
    expected = partial_manifest(repo, revision, artifact)
    if state is None:
        if partial.exists() or ledger.exists():
            raise ProtocolError("Unknown recovery partial/ledger exists; refusing to overwrite it")
        state = expected
        pins.atomic_json(ledger, state)
    for key in ("schemaVersion", "repo", "revision", "file"):
        if state.get(key) != expected[key]:
            raise ProtocolError("Recovery partial provenance does not match the exact pinned artifact")
    committed = state.get("committedBytes")
    if type(committed) is not int or not 0 <= committed <= artifact.size or not isinstance(state.get("chunks"), list):
        raise ProtocolError("Invalid committed recovery offset")
    if not partial.exists() and committed:
        raise ProtocolError("Committed recovery data is missing")
    handle = partial.open("r+b" if partial.exists() else "x+b")
    try:
        offset = 0
        for chunk in state["chunks"]:
            start, end = chunk.get("start"), chunk.get("end")
            if (type(start) is not int or type(end) is not int or start != offset
                    or not start <= end < artifact.size):
                raise ProtocolError("Recovery chunk ledger has a gap or overlapping byte range")
            digest = hashlib.sha256()
            left = end - start + 1
            while left:
                block = handle.read(min(left, 16 * 1024**2))
                if not block:
                    raise ProtocolError("Committed recovery data is truncated")
                digest.update(block)
                left -= len(block)
            if digest.hexdigest() != chunk.get("sha256"):
                raise ProtocolError("Committed recovery chunk checksum mismatch")
            offset = end + 1
        if offset != committed:
            raise ProtocolError("Recovery chunk ledger does not match its committed offset")
        # Only this helper's uncommitted tail is discarded. SDK/Xet temporary
        # files use different names and are never opened or modified here.
        handle.seek(committed)
        handle.truncate()
        return handle, partial, ledger, state
    except BaseException:
        handle.close()
        raise


def publish_verified(partial, destination):
    # Same volume hard-link publication is atomic and refuses an existing
    # filename. A crash before unlink leaves only another name for these bytes.
    os.link(partial, destination, follow_symlinks=False)
    partial.unlink()


def recover_file(config, root, repo, revision, artifact, client, progress, *, locker=hf_lock,
                 range_reader=read_range, sleeper=time.sleep):
    progress.update("waiting-for-exact-hf-file-lock", file=artifact.path, root=str(root))
    with locker(root, artifact) as paths:
        if paths.file_path.exists():
            progress.update("verifying-existing-pinned-file", file=artifact.path)
            proof = pins.verify_artifact(root, artifact, progress.hashing)
            write_hf_metadata(paths, revision, artifact)
            return proof
        handle, partial, ledger, state = open_partial(paths, repo, revision, artifact)
        try:
            while state["committedBytes"] < artifact.size:
                start = state["committedBytes"]
                end = min(start + config.chunk_bytes, artifact.size) - 1
                for attempt in range(config.retries):
                    progress.update("downloading-bounded-http-range", file=artifact.path,
                        rangeStart=start, rangeEnd=end, committedBytes=start, expectedBytes=artifact.size,
                        attempt=attempt + 1, lastError=None)
                    try:
                        digest = range_reader(client, repo, revision, artifact, start, end, handle)
                        break
                    except ProtocolError:
                        handle.seek(start);handle.truncate();handle.flush();os.fsync(handle.fileno())
                        raise
                    except Exception as error:
                        handle.seek(start);handle.truncate();handle.flush();os.fsync(handle.fileno())
                        # No signed CDN URL or token is written to the receipt.
                        progress.update(lastError=f"{type(error).__name__}: range {start}-{end} interrupted; refreshing URL")
                        if attempt + 1 == config.retries:
                            raise RuntimeError("Range retries exhausted; committed partial was preserved for a later retry") from error
                        sleeper(min(30, 2 ** attempt))
                handle.flush();os.fsync(handle.fileno())
                if handle.tell() != end + 1:
                    raise ProtocolError("Range reader returned an inconsistent output position")
                state["chunks"].append({"start": start, "end": end, "sha256": digest})
                state["committedBytes"] = end + 1
                state["updatedAt"] = pins.timestamp()
                pins.atomic_json(ledger, state)
            progress.update("verifying-complete-http-download", file=artifact.path)
            # Full pinned SHA256 / Git blob checksum is independent of the
            # transport's per-chunk ledger, before any final path is published.
            proof = pins.verify_artifact(partial.parent,
                pins.Artifact(partial.name, artifact.size, artifact.digest, artifact.algorithm), progress.hashing)
            handle.close()
            publish_verified(partial, paths.file_path)
            write_hf_metadata(paths, revision, artifact)
            proof = {**proof, **pins.identity(paths.file_path)}
            return proof
        finally:
            handle.close()


def original_running(pid):
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    result = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "command="],
        text=True, capture_output=True, check=False)
    command = result.stdout.strip()
    if command and "download-splash-flash-q4.py" not in command and "<defunct>" not in command:
        raise ProtocolError("Original downloader PID now belongs to a different process; review before continuing")
    return bool(command and "<defunct>" not in command)


def run_recovery(config, client, *, recover=recover_file, alive=original_running, sleeper=time.sleep):
    if len(config.target_files) != 4 or config.chunk_bytes <= 0 or config.retries < 1:
        raise ValueError("Invalid pinned recovery configuration")
    progress = Progress(config)
    try:
        progress.update("recovering-failed-second-q4-shard")
        recovered_second = recover(config, config.root, pins.Q4_REPO, pins.Q4_REVISION,
            config.target_files[1], client, progress)
        progress.update("waiting-for-original-q4-downloader-to-exit", files=[recovered_second])
        while alive(config.original_pid):
            sleeper(config.poll_seconds)
        # Only now may remaining Q4 paths or the draft be recovered; their
        # original per-file locks are still acquired individually as well.
        proofs = []
        for artifact in config.target_files:
            proof = recover(config, config.root, pins.Q4_REPO, pins.Q4_REVISION, artifact, client, progress)
            proofs.append(proof)
            progress.update(files=proofs)
        draft_proofs = []
        for artifact in config.draft_files:
            draft_proofs.append(recover(config, config.draft_root, pins.DRAFT_REPO,
                pins.DRAFT_REVISION, artifact, client, progress))
        completed = {"targetRepo": pins.Q4_REPO, "revision": pins.Q4_REVISION,
            "quantization": "Q4_K_M", "files": [{"path": item["path"], "bytes": item["bytes"],
                "sha256": item["sha256"]} for item in proofs],
            "draftRoot": str(config.draft_root), "draftRevision": pins.DRAFT_REVISION,
            "verifiedDraftFiles": draft_proofs, "completedAt": time.time(),
            "recoveryReceipt": str(config.receipt), "transport": "pinned resumable bounded HTTP ranges"}
        pins.atomic_json(config.completion_receipt, completed)
        progress.update("ready", status="ready", completedAt=pins.timestamp(),
            verifiedDraftFiles=draft_proofs, completionReceipt=str(config.completion_receipt))
        return progress.value
    except BaseException as error:
        progress.update(status="failed", error=f"{type(error).__name__}: {error}", failedAt=pins.timestamp())
        raise


@contextmanager
def recovery_lock(config):
    path = config.receipt.with_suffix(".json.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise RuntimeError(f"Recovery worker lock already exists: {path}") from error
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump({"pid": os.getpid(), "startedAt": pins.timestamp()}, handle)
        yield
    finally:
        path.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", required=True)
    parser.add_argument("--original-pid", type=int, default=7500)
    args = parser.parse_args(argv)
    config = Recovery(original_pid=args.original_pid)
    if Path(sys.executable).resolve() != (config.runtime / "python/bin/python3").resolve():
        raise RuntimeError("Run recovery using Splash 1.4.0's bundled Python")
    import httpx
    with recovery_lock(config), httpx.Client(follow_redirects=True,
            timeout=httpx.Timeout(120, connect=30, write=30, pool=30)) as client:
        run_recovery(config, client)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
