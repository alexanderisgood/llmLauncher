#!/usr/bin/env python3
"""Prepare pinned Q4_K_M Flash-Next weights with the original BF16 PLE.

Run --plan for a read-only plan. --run downloads only the BF16 PLE source,
waits for the existing Q4/draft downloader, verifies every pinned input, then
publishes APFS clones and prepares Splash metadata without starting inference.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

WORKSPACE = Path(__file__).resolve().parents[1]
Q4_REPO = "bartowski/Qwen3.8-Flash-Next-GGUF"
Q4_REVISION = "db3a185731e162be9ffa4d52d20d7509939e60e8"
BF16_REPO = "Delgon/Qwen3.8-Flash-Next-PLE-GGUF"
BF16_REVISION = "5de86c89b5b78fc2711744475b4da50ddd9acb72"
DRAFT_REPO = "incoai/Qwen3.8-Flash-Next-DFlash2"
DRAFT_REVISION = "a22a1744e85c17364dcc54a6a420af7135d4c7f6"
GIB = 1024**3


@dataclass(frozen=True)
class Artifact:
    path: str
    size: int
    digest: str
    algorithm: str = "sha256"

    def public(self):
        return {"path": self.path, "bytes": self.size, self.algorithm: self.digest}


Q4_FILES = tuple(Artifact("Qwen3.8-Flash-Next-Q4_K_M/" + name, size, sha) for name, size, sha in (
    ("Qwen3.8-Flash-Next-Q4_K_M-00001-of-00004.gguf", 39956571840, "e79f9a424dbd07629f7d91bbeef14efe912d8be4bc36e13466ddac18b05c2c0f"),
    ("Qwen3.8-Flash-Next-Q4_K_M-00002-of-00004.gguf", 39505063904, "93b626330052cbfbdddc19b4e9d16da7c09eeef9974a7738bad644fb0dfb2177"),
    ("Qwen3.8-Flash-Next-Q4_K_M-00003-of-00004.gguf", 39652077728, "96e3ba02eca2c4a3fd529560103160021066181575ab411db63dcd8499f9e650"),
    ("Qwen3.8-Flash-Next-Q4_K_M-00004-of-00004.gguf", 485316608, "07f3a5593064a05ef6d03f88bce6ea4a52074124fa222a5b19a8807b52991119"),
))
BF16_FILE = Artifact("Qwen3.8-Flash-Next-PLE-BF16.gguf", 102400492480,
    "0ac215cf0c5767ca20c463ad467eb31341e0ce0ca6cc8eb4f934d4b5f6d1932d")
DRAFT_FILES = (
    Artifact("config.json", 1236, "b370fddafd42756538af6e1cbe8273cab6e6d803", "git-sha1"),
    Artifact("model.safetensors", 1206140008, "d6723f2a359eaf33ec0c95f22ae8edda896774020c552296a85e1913b4d3186f"),
)


@dataclass(frozen=True)
class Setup:
    workspace: Path = WORKSPACE
    runtime: Path = WORKSPACE / "bench/runtimes/splash-1.4.0"
    q4_root: Path = Path.home() / ".lmstudio/models/bartowski/Qwen3.8-Flash-Next-GGUF"
    bf16_root: Path = WORKSPACE / "bench/runtimes/splash-ple-source"
    output: Path = Path.home() / ".lmstudio/models/bartowski/Qwen3.8-Flash-Next-Q4_K_M-BF16-PLE"
    models_root: Path = Path.home() / "Library/Application Support/LLM Launcher/splash-models"
    draft_root: Path = Path.home() / ".lmstudio/models/incoai/Qwen3.8-Flash-Next-DFlash2"
    receipt: Path = WORKSPACE / "bench/results/20261021-splash-flash-q4-bf16-setup.json"
    q4_receipts: tuple[Path, ...] = (
        WORKSPACE / "bench/results/20261021-splash-flash-q4-download.json",
        Path("/tmp/splash-flash-download-progress.json"),
    )
    q4_revision: str = Q4_REVISION
    bf16_revision: str = BF16_REVISION
    draft_revision: str = DRAFT_REVISION
    q4_files: tuple[Artifact, ...] = Q4_FILES
    bf16_file: Artifact = BF16_FILE
    draft_files: tuple[Artifact, ...] = DRAFT_FILES
    poll_seconds: float = 15
    wait_seconds: float = 7 * 86400


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".writing-" + str(os.getpid()))
    with temporary.open("w") as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def public_plan(config):
    return {
        "schemaVersion": 1, "mainPrecision": "Q4_K_M", "plePrecision": "BF16",
        "target": {"repo": Q4_REPO, "revision": config.q4_revision,
            "root": str(config.q4_root), "files": [item.public() for item in config.q4_files]},
        "ple": {"repo": BF16_REPO, "revision": config.bf16_revision,
            "root": str(config.bf16_root), "file": config.bf16_file.public()},
        "draft": {"repo": DRAFT_REPO, "revision": config.draft_revision,
            "root": str(config.draft_root),
            "files": [item.public() for item in config.draft_files]},
        "output": str(config.output), "runtime": str(config.runtime),
        "modelsRoot": str(config.models_root), "receipt": str(config.receipt),
        "q4DownloadReceipts": [str(path) for path in config.q4_receipts],
        "storage": "APFS clones required; main tensor bytes are preserved; no inference is started",
        "cleanup": "Only the four verified original Q4 shard files and verified original BF16 PLE file, after native validation and preparation",
    }


def plan_digest(config):
    return hashlib.sha256(json.dumps(public_plan(config), sort_keys=True).encode()).hexdigest()


def validate_pins(config):
    for name, selected, pinned in (
        ("Q4 revision", config.q4_revision, Q4_REVISION),
        ("BF16 PLE revision", config.bf16_revision, BF16_REVISION),
        ("draft revision", config.draft_revision, DRAFT_REVISION),
    ):
        if selected != pinned:
            raise ValueError(f"{name} does not match the pinned source")
    for artifact in (*config.q4_files, config.bf16_file, *config.draft_files):
        relative = Path(artifact.path)
        if relative.is_absolute() or ".." in relative.parts or artifact.size <= 0:
            raise ValueError("Unsafe or incomplete source artifact manifest")
    roots = [config.output.absolute(), config.q4_root.absolute(), config.bf16_root.absolute()]
    if roots[0] in roots[1:] or any(roots[0] in path.parents or path in roots[0].parents for path in roots[1:]):
        raise ValueError("Output and original input directories must be separate")


class Progress:
    def __init__(self, config):
        self.config = config
        previous = read_json(config.receipt)
        if isinstance(previous, dict) and previous.get("planDigest") != plan_digest(config):
            raise ValueError("Existing setup receipt belongs to a different pinned plan")
        self.value = previous if isinstance(previous, dict) else {
            "schemaVersion": 1, "plan": public_plan(config), "planDigest": plan_digest(config),
            "startedAt": timestamp(),
        }
        self.last_write = 0.0

    def update(self, phase=None, **values):
        if phase:
            self.value["phase"] = phase
            print(f"Splash BF16 PLE setup: {phase}", flush=True)
        self.value.update(values)
        self.value["updatedAt"] = timestamp()
        atomic_json(self.config.receipt, self.value)
        self.last_write = time.monotonic()

    def hashing(self, path, read_bytes, total):
        if time.monotonic() - self.last_write >= 5 or read_bytes == total:
            self.update(hashProgress={"path": str(path), "readBytes": read_bytes, "totalBytes": total})

    def building(self, event):
        if time.monotonic() - self.last_write >= 2 or event.get("phase") != self.value.get("buildProgress", {}).get("phase"):
            self.update(buildProgress=event)


def identity(path):
    path = Path(path)
    stat = path.stat()
    return {"path": str(path.absolute()), "resolvedPath": str(path.resolve()),
        "bytes": stat.st_size, "mtimeNs": stat.st_mtime_ns, "ctimeNs": stat.st_ctime_ns,
        "device": stat.st_dev, "inode": stat.st_ino}


def verify_artifact(root, artifact, progress=None):
    root = Path(root).resolve(strict=True)
    path = root / artifact.path
    path.resolve(strict=True).relative_to(root)
    before = identity(path)
    if not path.is_file() or before["bytes"] != artifact.size:
        raise ValueError(f"Pinned source size mismatch: {path}")
    if artifact.algorithm == "git-sha1":
        digest = hashlib.sha1(f"blob {artifact.size}\0".encode())
    elif artifact.algorithm == "sha256":
        digest = hashlib.sha256()
    else:
        raise ValueError("Unknown pinned source digest algorithm")
    read_bytes = 0
    with path.open("rb") as source:
        for block in iter(lambda: source.read(16 * 1024**2), b""):
            digest.update(block)
            read_bytes += len(block)
            if progress:
                progress(path, read_bytes, artifact.size)
    if digest.hexdigest() != artifact.digest or identity(path) != before:
        raise ValueError(f"Pinned source checksum mismatch or file changed: {path}")
    return {**before, artifact.algorithm: artifact.digest, "algorithm": artifact.algorithm, "verifiedAt": timestamp()}


def completed_q4_receipt(config):
    partial = None
    for path in config.q4_receipts:
        record = read_json(path)
        if not isinstance(record, dict):
            continue
        if (record.get("targetRepo") != Q4_REPO or record.get("revision") != Q4_REVISION
                or record.get("draftRevision", DRAFT_REVISION) != DRAFT_REVISION or record.get("quantization") != "Q4_K_M"):
            raise ValueError("Q4 download receipt does not match the pinned target/draft revisions")
        expected = {str((config.q4_root / artifact.path).absolute()): artifact for artifact in config.q4_files}
        files = record.get("files")
        if not isinstance(files, list) or len(files) > len(expected):
            raise ValueError("Q4 receipt has an invalid or duplicate shard manifest")
        seen = set()
        for entry in files:
            key = str(Path(entry.get("path", "")).absolute())
            artifact = expected.get(key)
            if artifact is None or key in seen or entry.get("bytes") != artifact.size or entry.get("sha256") != artifact.digest:
                raise ValueError("Completed Q4 receipt has an unexpected shard checksum, size or path")
            seen.add(key)
        if record.get("completedAt"):
            draft = Path(str(record.get("draftRoot") or ""))
            if (len(files) != len(expected) or record.get("draftRevision") != DRAFT_REVISION
                    or not draft.is_absolute() or not draft.is_dir()):
                raise ValueError("Completed Q4 receipt has incomplete target or local draft evidence")
            return record
        partial = record
    # The downloader also publishes a durable project receipt. If a reboot
    # loses /tmp before that final write, pinned files remain sufficient:
    # every byte is independently hashed immediately after this size gate.
    artifacts = [(config.q4_root, item) for item in config.q4_files]
    artifacts += [(config.draft_root, item) for item in config.draft_files]
    if all((root / item.path).is_file() and (root / item.path).stat().st_size == item.size for root, item in artifacts):
        return {"targetRepo": Q4_REPO, "revision": Q4_REVISION,
            "quantization": "Q4_K_M", "draftRevision": DRAFT_REVISION,
            "draftRoot": str(config.draft_root),
            "files": [{"path": str(config.q4_root / item.path), "bytes": item.size, "sha256": item.digest} for item in config.q4_files],
            "completionEvidence": "pinned local files; full independent checksum verification follows",
            "priorPartialReceipt": partial}
    return None


def download_bf16(config, progress):
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    os.environ["HF_XET_NUM_CONCURRENT_RANGE_GETS"] = "4"
    from huggingface_hub import hf_hub_download
    config.bf16_root.mkdir(parents=True, exist_ok=True)
    stopped = threading.Event()
    def heartbeat():
        while not stopped.wait(15):
            parts = list((config.bf16_root / ".cache/huggingface/download").glob("*.incomplete"))
            progress.update(downloadProgress={"stagedBytes": sum(path.stat().st_size for path in parts if path.is_file()),
                "expectedBytes": config.bf16_file.size, "heartbeatAt": timestamp()})
    monitor = threading.Thread(target=heartbeat, daemon=True)
    monitor.start()
    try:
        return Path(hf_hub_download(BF16_REPO, config.bf16_file.path,
            revision=BF16_REVISION, local_dir=config.bf16_root))
    finally:
        stopped.set()
        monitor.join()


def preflight(config, progress):
    sys.path.insert(0, str(config.workspace))
    import splash_runtime
    install = splash_runtime.inspect_install(libexec=config.runtime)
    if not install or not install.get("ready") or install.get("version") != "1.4.0":
        raise ValueError("Splash 1.4.0 runtime failed its release identity check")
    missing_q4 = sum(remaining_download_bytes(config.q4_root, item) for item in config.q4_files)
    missing_bf16 = remaining_download_bytes(config.bf16_root, config.bf16_file)
    # Only allocated bytes of the exact pinned partials reduce this reserve;
    # sparse apparent file length does not imply storage is already available.
    required = missing_q4 + missing_bf16 + 16 * GIB
    for requested in (config.output.parent, config.bf16_root):
        root = requested
        while not root.exists():
            root = root.parent
        free = shutil.disk_usage(root).free
        if free < required:
            raise ValueError(f"Insufficient free storage at {root}: need a conservative {required / GIB:.1f} GiB, have {free / GIB:.1f} GiB")
    progress.update(storagePreflight={"conservativeAdditionalBytes": required, "checkedAt": timestamp()})


def remaining_download_bytes(root, artifact):
    complete = Path(root) / artifact.path
    if complete.is_file() and complete.stat().st_size == artifact.size:
        return 0
    cache = Path(root) / ".cache/huggingface/download" / Path(artifact.path).parent
    allocated = 0
    for path in cache.glob(f"*.{artifact.digest}.*.incomplete"):
        try:
            info = path.stat()
        except FileNotFoundError:
            continue
        allocated += min(info.st_size, info.st_blocks * 512)
    return max(0, artifact.size - min(artifact.size, allocated))


def build_output(config, sources, ple, output, progress):
    sys.path.insert(0, str(config.workspace))
    import splash_ple
    return splash_ple.build_replacement(sources, ple, output, progress=progress.building)


def inspect_output(config, paths, progress):
    sys.path.insert(0, str(config.workspace))
    import splash_runtime
    install = splash_runtime.inspect_install(libexec=config.runtime)
    if not install or not install.get("ready") or install.get("version") != "1.4.0":
        raise ValueError("Splash 1.4.0 runtime failed its release identity check")
    sources = splash_runtime.inspect_sources(install, [str(paths[0])])
    if len(sources) != 1:
        raise ValueError("Splash rejected the prepared split GGUF headers")
    return sources[0]


def require_precision(source):
    if source.get("family") != "Qwen3.8-Flash-Next" or source.get("plePrecision") != "BF16":
        raise ValueError("Native inspection did not confirm Flash-Next with original BF16 PLE")
    if source.get("quantization") not in {"Q4_K", "Q4_K_M"}:
        raise ValueError("Native inspection did not confirm Q4 main weights")


def prepare_output(config, source, draft, progress):
    environment = dict(os.environ)
    environment.update(HF_HUB_OFFLINE="1", HF_HUB_DISABLE_PROGRESS_BARS="1")
    process = subprocess.run([str(config.runtime / "python/bin/python3"), "-I", "-B",
        str(config.workspace / "splash_sources.py"), str(config.runtime), "prepare"],
        input=json.dumps({"source": source, "destination": str(config.models_root), "drafts": [str(draft)]}),
        text=True, stdout=subprocess.PIPE, env=environment, check=True)
    try:
        return Path(json.loads(process.stdout.splitlines()[-1])["root"])
    except (IndexError, ValueError, KeyError) as error:
        raise ValueError("Splash did not return a prepared model directory") from error


def validate_prepared_root(config, prepared, output_paths, draft_proofs):
    prepared = Path(prepared).resolve(strict=True)
    prepared.relative_to(config.models_root.resolve(strict=True))
    document = read_json(prepared / "model.json")
    if not isinstance(document, dict) or not isinstance(document.get("files"), dict):
        raise ValueError("Splash prepared model has no readable file manifest")
    expected = {str(Path(path).resolve(strict=True)) for path in output_paths}
    references = set()
    draft_references = set()
    for name, item in document["files"].items():
        if name.startswith("target/") and name.endswith(".gguf"):
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise ValueError("Splash prepared target has an invalid source reference")
            references.add(str(Path(item["path"]).resolve(strict=True)))
        elif name.startswith("draft/"):
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise ValueError("Splash prepared draft has an invalid source reference")
            draft_references.add(str(Path(item["path"]).resolve(strict=True)))
    if references != expected:
        raise ValueError("Splash prepared target does not reference exactly the final cloned model shards")
    if draft_references != {proof["resolvedPath"] for proof in draft_proofs}:
        raise ValueError("Splash prepared model does not reference exactly the independently verified pinned draft")
    return prepared


def cleanup_verified_inputs(config, proofs, progress):
    # Check every input before deleting any: a late replacement preserves all
    # originals for diagnosis. No glob, parent-directory or cache deletion.
    cleanup_started = bool(progress.value.get("cleanupStartedAt"))
    allowed = {str(root.resolve() / item.path): item for root, item in
        [(config.q4_root, item) for item in config.q4_files] + [(config.bf16_root, config.bf16_file)]}
    if len(proofs) != len(allowed) or {proof["path"] for proof in proofs} != set(allowed):
        raise ValueError("Cleanup proofs do not name exactly the pinned original source files")
    for proof in proofs:
        expected = allowed[proof["path"]]
        if proof.get("bytes") != expected.size or proof.get(expected.algorithm) != expected.digest:
            raise ValueError("Cleanup proof does not match a pinned original source checksum")
    remaining = []
    removed = []
    for proof in proofs:
        if not Path(proof["path"]).exists():
            if not cleanup_started:
                raise ValueError(f"Verified original disappeared before cleanup: {proof['path']}")
            removed.append(proof["path"])
            continue
        current = identity(proof["path"])
        if current != {key: proof[key] for key in current}:
            raise ValueError(f"Verified original changed before cleanup: {proof['path']}")
        remaining.append(proof)
    progress.update("cleaning-verified-originals", cleanupStartedAt=progress.value.get("cleanupStartedAt") or timestamp(), removedOriginals=removed)
    for proof in remaining:
        path = Path(proof["path"])
        current = identity(path)
        if current != {key: proof[key] for key in current}:
            raise ValueError(f"Verified original changed during cleanup: {path}")
        path.unlink()
        removed.append(str(path))
        progress.update(removedOriginals=removed)


def run_setup(config, *, downloader=download_bf16, builder=build_output,
              inspector=inspect_output, preparer=prepare_output, sleeper=time.sleep, preflight_check=preflight):
    validate_pins(config)
    progress = Progress(config)
    try:
        if progress.value.get("preparedRoot") and progress.value.get("publishedRoot") == str(config.output):
            # Preparation is a durable qualification checkpoint. A restart
            # during cleanup must not redownload removed 102 GB originals.
            paths = [Path(path) for path in progress.value["outputPaths"]]
            for proof in progress.value["verifiedOutputs"]:
                current = identity(proof["path"])
                if current != {key: proof[key] for key in current}:
                    raise ValueError("Qualified output changed before cleanup recovery")
            require_precision(inspector(config, paths, progress))
            validate_prepared_root(config, progress.value["preparedRoot"], paths, progress.value["verifiedDraftFiles"])
            for proof in progress.value["verifiedDraftFiles"]:
                current = identity(proof["path"])
                if current != {key: proof[key] for key in current}:
                    raise ValueError("Pinned draft changed before cleanup recovery")
            if progress.value.get("status") != "ready":
                cleanup_verified_inputs(config, progress.value["verifiedInputs"], progress)
                progress.update("ready", status="ready", completedAt=timestamp())
            return progress.value
        progress.update("checking-runtime-and-storage", status="running", pid=os.getpid(), error=None)
        preflight_check(config, progress)
        progress.update("downloading-original-bf16-ple", status="running", pid=os.getpid(), error=None)
        downloaded = Path(downloader(config, progress))
        if downloaded.absolute() != (config.bf16_root / config.bf16_file.path).absolute():
            raise ValueError("BF16 download returned an unexpected source path")
        progress.update("verifying-original-bf16-ple")
        bf16_proof = verify_artifact(config.bf16_root, config.bf16_file, progress.hashing)
        progress.update(bf16Proof=bf16_proof)
        progress.update("waiting-for-existing-q4-and-draft-download")
        wait_start = time.monotonic()
        while (q4_receipt := completed_q4_receipt(config)) is None:
            if time.monotonic() - wait_start > config.wait_seconds:
                raise TimeoutError("Existing Q4/draft download did not finish; originals and partial downloads were preserved")
            sleeper(config.poll_seconds)
        progress.update("verifying-pinned-q4-and-draft", originalDownloadReceipt=q4_receipt)
        q4_proofs = [verify_artifact(config.q4_root, item, progress.hashing) for item in config.q4_files]
        draft = Path(q4_receipt["draftRoot"])
        draft_proofs = [verify_artifact(draft, item, progress.hashing) for item in config.draft_files]
        progress.update(verifiedInputs=[*q4_proofs, bf16_proof], verifiedDraftFiles=draft_proofs)
        sources = [config.q4_root / item.path for item in config.q4_files]
        if config.output.exists():
            if progress.value.get("publishedRoot") != str(config.output) or not progress.value.get("mainTensorParityVerified"):
                raise ValueError("Output directory already exists without this setup's verified publication receipt")
            output_paths = [Path(path) for path in progress.value["outputPaths"]]
        else:
            config.output.parent.mkdir(parents=True, exist_ok=True)
            progress.update("building-verified-apfs-clones", plannedOutput=str(config.output))
            # The builder owns hidden staging and exclusive atomic publication;
            # no second rename or stale staging-path receipt is necessary.
            built = builder(config, sources, downloaded, config.output, progress)
            if built.get("mainTensorParityVerified") is not True:
                raise ValueError("Replacement builder did not prove main tensor byte parity")
            paths = [Path(path) for path in built.get("outputPaths", [])]
            if len(paths) != len(config.q4_files) + 1 or any(path.parent != config.output for path in paths):
                raise ValueError("Replacement builder returned an unexpected output shard set")
            for path in paths:
                if not path.is_file():
                    raise ValueError("Replacement builder output is incomplete")
            output_paths = paths
            progress.update("published-cloned-model", publishedRoot=str(config.output),
                outputPaths=[str(path) for path in output_paths], builderReceipt=built,
                mainTensorParityVerified=True, mainTensorDigest=built.get("mainTensorDigest"))
        progress.update("native-header-validation")
        source = inspector(config, output_paths, progress)
        require_precision(source)
        progress.update(nativeSource=source, mainPrecision="Q4_K_M", plePrecision="BF16")
        progress.update("preparing-native-splash-metadata-offline")
        prepared = preparer(config, source, draft, progress)
        prepared = validate_prepared_root(config, prepared, output_paths, draft_proofs)
        progress.update("native-model-prepared", preparedRoot=str(prepared), preparedAt=timestamp(),
            verifiedOutputs=[identity(path) for path in output_paths])
        cleanup_verified_inputs(config, [*q4_proofs, bf16_proof], progress)
        progress.update("ready", status="ready", completedAt=timestamp())
        return progress.value
    except BaseException as error:
        progress.update(status="failed", failedAt=timestamp(), error=f"{type(error).__name__}: {error}")
        raise


@contextmanager
def setup_lock(config):
    lock = config.receipt.with_suffix(config.receipt.suffix + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise RuntimeError(f"Setup lock exists at {lock}; inspect its PID before retrying") from error
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump({"pid": os.getpid(), "startedAt": timestamp(), "planDigest": plan_digest(config)}, handle)
        yield
    finally:
        lock.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--plan", action="store_true", help="Print the pinned plan without downloads or writes")
    action.add_argument("--run", action="store_true", help="Perform the pinned preparation and persist progress")
    arguments = parser.parse_args(argv)
    config = Setup()
    validate_pins(config)
    if arguments.plan:
        print(json.dumps({**public_plan(config), "existingReceipt": read_json(config.receipt)}, indent=2))
        return 0
    expected_python = config.runtime / "python/bin/python3"
    if Path(sys.executable).resolve() != expected_python.resolve():
        raise RuntimeError(f"Run this worker using Splash 1.4.0's bundled Python: {expected_python}")
    with setup_lock(config):
        result = run_setup(config)
    print(json.dumps({"status": result["status"], "preparedRoot": result["preparedRoot"], "receipt": str(config.receipt)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
