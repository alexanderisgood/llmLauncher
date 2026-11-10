"""Audited side-by-side runtime updates, isolated from controller state.

Owns review admission, private installer/download lifecycle, strict wheel/source
checks, staged/final smoke verification and rollback cleanup. Selection remains
an explicit read-only port; completing an update never changes it.
"""
from __future__ import annotations
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import threading
import time
import uuid
import zipfile
from typing import Any, Callable
from download_jobs import terminate_owned_downloader
from log_tail import read_log_tail


class RuntimeUpdateCancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeUpdatePolicy:
    plan_ttl_seconds: float
    schema_version: int
    manifest_name: str
    capture_tail_bytes: int = 200_000
    cancel_join_seconds: float = 1.0

    def __post_init__(self) -> None:
        if (type(self.plan_ttl_seconds) not in (int, float) or not math.isfinite(self.plan_ttl_seconds)
                or self.plan_ttl_seconds <= 0 or type(self.schema_version) is not int or self.schema_version < 1
                or not self.manifest_name or Path(self.manifest_name).name != self.manifest_name
                or type(self.capture_tail_bytes) is not int or self.capture_tail_bytes < 1
                or type(self.cancel_join_seconds) not in (int, float) or not math.isfinite(self.cancel_join_seconds)
                or self.cancel_join_seconds < 0):
            raise ValueError("Invalid runtime update policy")


@dataclass(frozen=True)
class RuntimeUpdatePaths:
    managed_dir: Callable[[], Path]
    update_dir: Callable[[], Path]


@dataclass(frozen=True)
class RuntimeUpdateServices:
    build_plan: Callable[[Any], dict[str, Any]]
    launcher_idle: Callable[[], bool]
    benchmark_active: Callable[[], bool]
    selected_binary: Callable[[], str | None]
    exact_version: Callable[[str, str], bool]
    managed_verification: Callable[[str], dict[str, Any]]
    kernel_status: Callable[[str], dict[str, Any]]
    invalidate_kernel_cache: Callable[[], None]
    candidates: Callable[[], list[dict[str, Any]]]
    write_json: Callable[[Path, Any], None]
    patch_inspect: Callable[[Path], tuple[Any, Any, dict[str, Any]]]
    patch_apply: Callable[[Path], Any]
    cancelled_error: type[Exception] = RuntimeUpdateCancelled


def _safe_cleanup_staging(staging: Path, managed_root: Path) -> None:
    try:
        root = managed_root.expanduser().resolve(strict=False)
        parent = staging.parent.resolve(strict=False)
    except OSError:
        return
    if parent != root or not staging.name.startswith(".omlx-") or ".installing-" not in staging.name:
        return
    try:
        if staging.is_symlink():
            staging.unlink()
        elif staging.exists():
            shutil.rmtree(staging)
    except OSError:
        pass



def _rebase_staged_environment(staging: Path, target: Path, managed_root: Path) -> list[str]:
    """Rewrite generated venv launchers so they survive the atomic directory move."""
    try:
        root = managed_root.expanduser().resolve(strict=False)
        staging_parent = staging.parent.resolve(strict=False)
        target_parent = target.parent.resolve(strict=False)
    except OSError as error:
        raise RuntimeError("The isolated runtime paths could not be revalidated before promotion.") from error
    if (
        staging_parent != root or target_parent != root
        or not staging.name.startswith(".omlx-") or ".installing-" not in staging.name
        or not target.name.startswith("omlx-")
    ):
        raise RuntimeError("The isolated runtime paths changed before promotion.")
    bin_dir = staging / "bin"
    if bin_dir.is_symlink() or not bin_dir.is_dir():
        raise RuntimeError("The isolated runtime command directory changed before promotion.")
    source = str(staging).encode("utf-8")
    destination = str(target).encode("utf-8")
    rewritten: list[str] = []
    try:
        entries = list(bin_dir.iterdir())
    except OSError as error:
        raise RuntimeError("The isolated runtime commands could not be inspected before promotion.") from error
    for path in entries:
        if path.is_symlink() or not path.is_file():
            continue
        try:
            if path.stat().st_size > 2 * 1024 * 1024:
                continue
            contents = path.read_bytes()
        except OSError as error:
            raise RuntimeError("An isolated runtime command could not be inspected before promotion.") from error
        if source not in contents:
            continue
        if b"\0" in contents:
            raise RuntimeError("A generated runtime command contains an unsafe embedded staging path.")
        try:
            path.write_bytes(contents.replace(source, destination))
        except OSError as error:
            raise RuntimeError("A generated runtime command could not be prepared for its final path.") from error
        rewritten.append(path.name)
    required = {"omlx", "pip"}
    if not required.issubset(rewritten):
        raise RuntimeError("The isolated environment did not expose every relocatable runtime command.")
    for path in entries:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
            continue
        if source in path.read_bytes():
            raise RuntimeError("A generated runtime command still points at the private staging directory.")
    return sorted(rewritten)



def _safe_cleanup_failed_promotion(target: Path, version: str, managed_root: Path, selected_binary: str | None) -> None:
    """Remove only the exact unselected target created by this failed worker."""
    try:
        root = managed_root.expanduser().resolve(strict=False)
        parent = target.parent.resolve(strict=False)
        selected = selected_binary
        selected_target = (
            Path(selected).expanduser().resolve(strict=False).parent.parent
            if selected else None
        )
    except OSError:
        return
    if (
        parent != root or target.name != f"omlx-{version}"
        or selected_target == target.resolve(strict=False)
    ):
        return
    try:
        if target.is_symlink():
            target.unlink()
        elif target.exists():
            shutil.rmtree(target)
    except OSError:
        pass



class RuntimeUpdateManager:
    """Install or adopt one audited oMLX wheel without changing selection."""

    ACTIVE_PHASES = {
        "queued", "downloading", "verifying", "installing",
        "smoke-testing", "promoting", "stopping",
    }

    def __init__(self, policy: RuntimeUpdatePolicy, paths: RuntimeUpdatePaths, services: RuntimeUpdateServices) -> None:
        self.policy = policy
        self.paths = paths
        self.services = services
        self.lock = threading.RLock()
        self.cancel_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.process: subprocess.Popen | None = None
        self.plans: dict[str, dict[str, Any]] = {}
        self._cleanup_lock = threading.Lock()
        self._retired_processes: set[subprocess.Popen] = set()
        self._trust_committed = False
        self.state: dict[str, Any] = {
            "phase": "idle", "message": "No runtime update is running.",
            "progress": 0.0, "downloadedBytes": 0,
            "plan": None, "result": None, "events": [],
        }

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return json.loads(json.dumps(self.state))

    def is_active(self) -> bool:
        with self.lock:
            return bool(
                self.state.get("phase") in self.ACTIVE_PHASES
                or (self.thread and self.thread.is_alive())
            )

    def _event(self, message: str, level: str = "info") -> None:
        with self.lock:
            self.state["message"] = message
            self.state["events"] = (
                self.state.get("events", [])
                + [{"time": time.strftime("%H:%M:%S"), "level": level, "message": message}]
            )[-80:]

    def _prune(self) -> None:
        now = time.time()
        self.plans = {
            plan_id: entry for plan_id, entry in self.plans.items()
            if float(entry.get("expires", 0)) > now
        }

    def inspect(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.is_active():
            raise ValueError("Wait for the active runtime update to finish before replacing its plan.")
        plan = self.services.build_plan(payload.get("channel"))
        expires = time.time() + self.policy.plan_ttl_seconds
        plan["expiresAt"] = datetime.fromtimestamp(expires, timezone.utc).isoformat()
        with self.lock:
            if self.is_active():
                raise ValueError("Wait for the active runtime update to finish before replacing its plan.")
            self._prune()
            self.plans[plan["id"]] = {
                "expires": expires, "channel": plan["release"]["channel"],
                "plan": copy.deepcopy(plan),
            }
        return plan

    def _validated_start_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan_id = str(payload.get("planId") or "")
        with self.lock:
            self._prune()
            entry = copy.deepcopy(self.plans.get(plan_id))
        if not entry:
            raise ValueError("The runtime update plan expired or changed. Review it again.")
        plan = self.services.build_plan(entry["channel"])
        if plan.get("id") != plan_id:
            raise ValueError("The runtime, installer, or destination changed. Review a fresh update plan.")
        if payload.get("reviewed") is not True:
            raise ValueError("Review the release, checksum, destination, and rollback behaviour first.")
        if not secrets.compare_digest(
            str(payload.get("confirmation") or ""), str(plan.get("confirmation") or ""),
        ):
            raise ValueError("Confirm the exact audited runtime plan before continuing.")
        if not plan.get("canStart"):
            blocked = next(
                (item.get("detail") for item in plan.get("checks", []) if item.get("state") == "blocked"),
                "This runtime update cannot start safely.",
            )
            raise ValueError(str(blocked))
        return plan

    def start(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan = self._validated_start_plan(payload)
        if not self.services.launcher_idle():
            raise ValueError("Stop the active launcher session before changing installed runtimes.")
        if self.services.benchmark_active():
            raise ValueError("Stop Benchmark Lab before changing installed runtimes.")
        with self.lock:
            if self.is_active():
                raise ValueError("A runtime update is already running.")
            self.cancel_event = threading.Event()
            self._retired_processes.clear()
            self._trust_committed = False
            self.state = {
                "phase": "queued",
                "message": "Runtime plan approved. Revalidating its exact destination…",
                "progress": 0.02, "downloadedBytes": 0,
                "plan": copy.deepcopy(plan), "result": None, "events": [],
            }
            thread = threading.Thread(target=self._worker, args=(copy.deepcopy(plan),), daemon=True)
            self.thread = thread
            try:
                thread.start()
            except Exception:
                self.thread = None
                self.state["phase"] = "failed"
                self._event("The runtime update worker could not start. Try the reviewed operation again.", "error")
                raise
        return copy.deepcopy(plan)

    @staticmethod
    def _terminate(process: subprocess.Popen) -> None:
        terminate_owned_downloader(process)

    def cancel(self) -> None:
        with self.lock:
            if self.state.get("phase") not in self.ACTIVE_PHASES or self._trust_committed:
                return
            self.cancel_event.set()
            self.state["phase"] = "stopping"
            self.state["message"] = "Stopping the runtime update; the selected runtime remains unchanged…"
            process, thread = self.process, self.thread
        if process is not None:
            self._retire_process(process)
        if (thread is not None and thread is not threading.current_thread()
                and thread.ident is not None):
            thread.join(timeout=self.policy.cancel_join_seconds)

    def _check_cancelled(self) -> None:
        if self.cancel_event.is_set():
            raise self.services.cancelled_error("Runtime update cancelled.")

    def _phase(self, phase: str, progress: float) -> None:
        with self.lock:
            self._check_cancelled()
            self.state["phase"] = phase
            self.state["progress"] = progress

    def _publish_process(self, process: subprocess.Popen) -> None:
        with self.lock:
            accepted = not self.cancel_event.is_set()
            if accepted:
                self.process = process
        if not accepted:
            self._retire_process(process)
            raise self.services.cancelled_error("Runtime update cancelled before process publication.")

    def _retire_process(self, process: subprocess.Popen) -> None:
        with self._cleanup_lock:
            if process in self._retired_processes:
                return
            self._terminate(process)
            self._retired_processes.add(process)
            with self.lock:
                if self.process is process:
                    self.process = None

    @staticmethod
    def _log_tail(path: Path) -> str:
        return read_log_tail(path, 2000).strip()

    def _run_logged(
        self, argv: list[str], log_path: Path, phase: str,
        message: str, progress: float, environment: dict[str, str] | None = None,
    ) -> None:
        self._check_cancelled()
        self._event(message)
        self._phase(phase, progress)
        process: subprocess.Popen | None = None
        try:
            with open(log_path, "ab", buffering=0) as log_handle:
                self._check_cancelled()
                process = subprocess.Popen(
                    argv, stdin=subprocess.DEVNULL, stdout=log_handle,
                    stderr=subprocess.STDOUT, start_new_session=True,
                    close_fds=True, env=environment,
                )
                self._publish_process(process)
                while process.poll() is None:
                    if self.cancel_event.wait(0.25):
                        raise self.services.cancelled_error("Runtime update cancelled.")
                return_code = process.wait()
            self._check_cancelled()
            if return_code != 0:
                detail = self._log_tail(log_path)
                raise RuntimeError(message + " failed." + (f" {detail}" if detail else ""))
        finally:
            if process is not None:
                self._retire_process(process)

    def _run_capture(
        self, argv: list[str], timeout: float = 30,
        environment: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        self._check_cancelled()
        process = subprocess.Popen(
            argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, start_new_session=True,
            close_fds=True, env=environment,
        )
        tail = bytearray()
        reader_error: list[Exception] = []
        def drain() -> None:
            try:
                while value := process.stdout.read(32 * 1024):
                    tail.extend(value)
                    if len(tail) > self.policy.capture_tail_bytes:
                        del tail[:-self.policy.capture_tail_bytes]
            except (OSError, ValueError) as error:
                reader_error.append(error)
        reader: threading.Thread | None = None
        try:
            self._publish_process(process)
            reader = threading.Thread(target=drain, daemon=True, name="runtime-smoke-output")
            reader.start()
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                if self.cancel_event.wait(0.1):
                    raise self.services.cancelled_error("Runtime update cancelled.")
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"The runtime smoke test timed out: {Path(argv[0]).name}.")
            self._check_cancelled()
            return_code = process.wait()
        finally:
            # A descendant may retain stdout even after the command exited.
            # End this owned group before joining the bounded drainer.
            self._retire_process(process)
            if reader is not None and reader.ident is not None:
                reader.join(timeout=2)
            if reader is None or not reader.is_alive():
                process.stdout.close()
        if reader is not None and reader.is_alive():
            raise RuntimeError("The runtime smoke-test output did not close cleanly.")
        if reader_error:
            raise RuntimeError("The runtime smoke-test output could not be read.") from reader_error[0]
        return return_code, bytes(tail).decode("utf-8", errors="replace")

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            while True:
                if self.cancel_event.is_set():
                    raise self.services.cancelled_error("Runtime update cancelled.")
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _normalized_distribution(value: str) -> str:
        return re.sub(r"[-_.]+", "-", str(value or "")).lower()

    def _audit_official_wheel(self, artifact: Path, release: dict[str, Any]) -> dict[str, Any]:
        """Trust dependency URLs only when the checksum-pinned wheel declares audited commits."""
        try:
            with zipfile.ZipFile(artifact) as archive:
                metadata_entries = [
                    item for item in archive.infolist()
                    if item.filename.endswith(".dist-info/METADATA")
                    and item.filename.count("/") == 1
                ]
                if len(metadata_entries) != 1 or metadata_entries[0].file_size > 2 * 1024 * 1024:
                    raise RuntimeError("The official wheel has an unexpected package-metadata layout.")
                metadata = archive.read(metadata_entries[0]).decode("utf-8", "strict")
        except (OSError, UnicodeError, zipfile.BadZipFile, KeyError) as error:
            raise RuntimeError("The checksum-matched file is not a readable oMLX wheel.") from error

        requirements = re.findall(r"^Requires-Dist:\s*(.+?)\s*$", metadata, re.MULTILINE)
        expected = sorted(
            (
                self._normalized_distribution(item.get("name")),
                str(item.get("repository") or "").lower(),
                str(item.get("commit") or "").lower(),
            )
            for item in release.get("directSources") or []
        )
        optional_allowed = {
            (
                "mlx-audio", "blaizzy/mlx-audio",
                "51753266e0a4f766fd5e6fbc46652224efc23981",
            ),
        }
        base_sources: list[tuple[str, str, str]] = []
        all_sources: list[dict[str, Any]] = []
        for requirement in requirements:
            if "git+" not in requirement.lower() and not re.search(r"\s@\s*https?://", requirement, re.IGNORECASE):
                continue
            match = re.fullmatch(
                r"\s*([A-Za-z0-9_.-]+)(?:\[[A-Za-z0-9_,.-]+\])?\s*@\s*"
                r"git\+https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([0-9a-fA-F]{40})"
                r"(?:\s*;\s*(.+))?\s*",
                requirement,
            )
            if not match:
                raise RuntimeError("The official wheel declares a direct dependency that is not a full-commit public GitHub source.")
            name = self._normalized_distribution(match.group(1))
            repository = match.group(2).lower()
            commit = match.group(3).lower()
            marker = str(match.group(4) or "")
            optional = "extra" in marker.lower()
            identity = (name, repository, commit)
            if optional:
                if identity not in optional_allowed:
                    raise RuntimeError("The official wheel contains an unaudited optional source dependency.")
            else:
                base_sources.append(identity)
            all_sources.append({
                "name": name, "repository": match.group(2),
                "commit": commit, "optional": optional,
            })
        if sorted(base_sources) != expected:
            raise RuntimeError("The official wheel's direct-source dependency set does not match the audited release catalog.")
        if metadata.lower().count("git+") != len(all_sources):
            raise RuntimeError("The official wheel contains an unparsed Git dependency reference.")
        return {
            "metadataSha256": hashlib.sha256(metadata.encode("utf-8")).hexdigest(),
            "requirementCount": len(requirements),
            "directSources": all_sources,
            "baseDirectSourcesMatched": True,
        }

    def _wheelhouse_inventory(
        self, wheelhouse: Path, artifact: Path, release: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[Path]]:
        if wheelhouse.is_symlink() or not wheelhouse.is_dir():
            raise RuntimeError("The private dependency wheelhouse changed unexpectedly.")
        try:
            entries = sorted(wheelhouse.iterdir(), key=lambda item: item.name.lower())
        except OSError as error:
            raise RuntimeError("The private dependency wheelhouse could not be inventoried.") from error
        wheel_paths: list[Path] = []
        for entry in entries:
            if (
                entry.is_symlink() or not entry.is_file()
                or entry.suffix.lower() != ".whl" or not zipfile.is_zipfile(entry)
            ):
                raise RuntimeError("The private dependency wheelhouse contains an unexpected entry.")
            if entry.name == artifact.name:
                if not secrets.compare_digest(self._sha256(entry), str(release["sha256"])):
                    raise RuntimeError("pip's staged root wheel does not match the audited release checksum.")
                continue
            wheel_paths.append(entry)
        paths = [artifact, *wheel_paths]
        if not 2 <= len(paths) <= 512:
            raise RuntimeError("The private dependency wheelhouse has an unexpected number of artifacts.")
        rows: list[dict[str, Any]] = []
        normalized_files: dict[str, int] = {}
        for path in paths:
            if path.is_symlink() or not path.is_file() or not zipfile.is_zipfile(path):
                raise RuntimeError("The private dependency wheelhouse contains a non-wheel or symbolic link.")
            size = path.stat().st_size
            if not 0 < size <= 4 * 1024**3:
                raise RuntimeError("A private dependency wheel has an invalid size.")
            distribution = self._normalized_distribution(path.name.split("-", 1)[0])
            normalized_files[distribution] = normalized_files.get(distribution, 0) + 1
            if normalized_files[distribution] != 1:
                raise RuntimeError("The private dependency wheelhouse contains duplicate distributions.")
            digest = self._sha256(path)
            if path.name == artifact.name and not secrets.compare_digest(digest, str(release["sha256"])):
                raise RuntimeError("The root oMLX wheel changed while staging dependencies.")
            rows.append({
                "file": path.name, "distribution": distribution,
                "size": size, "sha256": digest,
                "root": path.name == artifact.name,
            })
        expected_sources = {
            self._normalized_distribution(item.get("name"))
            for item in release.get("directSources") or []
        }
        if any(normalized_files.get(name) != 1 for name in expected_sources):
            raise RuntimeError("One or more audited full-commit dependencies did not produce a staged wheel.")
        return rows, paths

    @staticmethod
    def _pip_environment() -> dict[str, str]:
        environment = {
            key: value for key, value in os.environ.items()
            if (
                not key.startswith(("PIP_", "PYTHON", "VIRTUAL_ENV", "UV_", "GIT_", "GH_"))
                and key not in {"GITHUB_TOKEN"}
            )
        }
        environment.update({
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INPUT": "1",
            "PIP_NO_CACHE_DIR": "1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "never",
        })
        return environment

    def _safe_cleanup_staging(self, staging: Path) -> None:
        return _safe_cleanup_staging(staging, self.paths.managed_dir())

    def _rebase_staged_environment(self, staging: Path, target: Path) -> list[str]:
        return _rebase_staged_environment(staging, target, self.paths.managed_dir())

    def _safe_cleanup_failed_promotion(self, target: Path, version: str) -> None:
        return _safe_cleanup_failed_promotion(target, version, self.paths.managed_dir(), self.services.selected_binary())

    def _download(self, plan: dict[str, Any], log_path: Path) -> Path:
        release = plan["release"]
        downloads = self.paths.update_dir() / "downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        final = downloads / str(release["fileName"])
        partial = final.with_suffix(final.suffix + ".part")
        expected = str(release["sha256"])
        for candidate in (final, partial):
            if candidate.is_symlink():
                raise ValueError("The runtime download cache contains an unexpected symbolic link.")
        if final.is_file():
            self._phase("verifying", 0.25)
            self._event("A cached official wheel exists. Rechecking its full SHA-256 before use…")
            if secrets.compare_digest(self._sha256(final), expected):
                with self.lock:
                    self.state["downloadedBytes"] = final.stat().st_size
                return final
            rejected = final.with_name(f"{final.name}.rejected-{int(time.time())}")
            os.replace(final, rejected)
            self._event("A cached file failed the published checksum and was preserved with a rejected suffix.", "warning")

        curl = str(plan["installer"].get("curl") or "")
        if not curl:
            raise RuntimeError("curl is unavailable for the approved HTTPS download.")
        argv = [
            curl, "-q", "--proto", "=https", "--tlsv1.2", "--fail",
            "--location", "--retry", "2", "--retry-delay", "1",
            "--continue-at", "-", "--output", str(partial), str(release["url"]),
        ]
        self._event(f"Downloading the exact official {release['sizeLabel']} wheel; partial bytes remain resumable.")
        process: subprocess.Popen | None = None
        try:
            with open(log_path, "ab", buffering=0) as log_handle:
                self._check_cancelled()
                process = subprocess.Popen(
                    argv, stdin=subprocess.DEVNULL, stdout=log_handle,
                    stderr=subprocess.STDOUT, start_new_session=True, close_fds=True,
                )
                self._publish_process(process)
                self._phase("downloading", 0.08)
                while process.poll() is None:
                    if self.cancel_event.wait(0.25):
                        raise self.services.cancelled_error("Runtime update cancelled.")
                    try:
                        downloaded = partial.stat().st_size
                    except OSError:
                        downloaded = 0
                    with self.lock:
                        self._check_cancelled()
                        self.state["downloadedBytes"] = downloaded
                        self.state["progress"] = min(0.24, 0.08 + downloaded / 40_000_000 * 0.16)
                return_code = process.wait()
        finally:
            if process is not None:
                self._retire_process(process)
        if self.cancel_event.is_set():
            raise self.services.cancelled_error("Runtime update cancelled.")
        if return_code != 0:
            detail = self._log_tail(log_path)
            raise RuntimeError("The official runtime wheel download failed; partial bytes were kept for resume." + (f" {detail}" if detail else ""))
        self._phase("verifying", 0.25)
        self._event("Download complete. Comparing every byte with the GitHub-published SHA-256…")
        actual = self._sha256(partial)
        if not secrets.compare_digest(actual, expected):
            rejected = partial.with_name(f"{partial.name}.rejected-{int(time.time())}")
            os.replace(partial, rejected)
            raise RuntimeError("The downloaded wheel failed its published SHA-256 and will not be installed.")
        os.chmod(partial, 0o600)
        os.replace(partial, final)
        with self.lock:
            self.state["downloadedBytes"] = final.stat().st_size
        return final

    def _smoke_runtime(self, target: Path, release: dict[str, Any]) -> dict[str, Any]:
        binary = target / "bin" / "omlx"
        python = target / "bin" / "python"
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise RuntimeError("The isolated environment did not create an executable oMLX command.")
        if not python.is_file() or not os.access(python, os.X_OK):
            raise RuntimeError("The isolated environment did not create its matching Python command.")
        local_patches = []
        if release["version"] == "0.6.4":
            receipt = self.services.patch_inspect(target)[2]
            if not receipt["applied"]:
                raise RuntimeError("The managed oMLX runtime is missing the launcher DFlash thinking-budget patch.")
            local_patches.append(receipt)
        return_code, version_output = self._run_capture([str(binary), "--version"], timeout=20)
        version_line = (version_output.strip().splitlines() or [""])[0][:100]
        if return_code != 0 or not self.services.exact_version(version_line, str(release["version"])):
            raise RuntimeError(f"The oMLX version smoke test returned {version_line or 'no version'} instead of {release['version']}.")
        return_code, metadata_output = self._run_capture([
            str(python), "-c",
            "import importlib.metadata as m; print(m.version('omlx'))",
        ], timeout=20)
        metadata_version = (metadata_output.strip().splitlines() or [""])[-1][:100]
        if return_code != 0 or not self.services.exact_version(metadata_version, str(release["version"])):
            raise RuntimeError("The installed package metadata does not match the approved oMLX version.")
        return_code, dependency_output = self._run_capture(
            [str(python), "-m", "pip", "check"], timeout=60,
            environment=self._pip_environment(),
        )
        if return_code != 0:
            raise RuntimeError("The isolated runtime failed its dependency check. " + dependency_output[-800:].strip())
        return_code, help_output = self._run_capture([str(binary), "--help"], timeout=30)
        if return_code != 0 or "serve" not in help_output.lower():
            raise RuntimeError("The oMLX command did not expose its expected server help surface.")
        kernel = self.services.kernel_status(str(binary))
        return {
            "version": version_line, "packageVersion": metadata_version,
            "dependencyCheck": dependency_output.strip()[:500] or "No broken requirements found.",
            "serverCommandReady": True, "nativeKernel": kernel,
            "serverStarted": False, "modelLoaded": False,
            "localPatches": local_patches,
        }

    def _dependency_inventory(self, target: Path) -> list[dict[str, str]]:
        return_code, output = self._run_capture(
            [str(target / "bin" / "python"), "-m", "pip", "list", "--format=json"],
            timeout=60, environment=self._pip_environment(),
        )
        if return_code != 0:
            return []
        try:
            values = json.loads(output)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        result = []
        for value in values if isinstance(values, list) else []:
            if not isinstance(value, dict) or len(result) >= 512:
                continue
            name = str(value.get("name") or "")[:120]
            version = str(value.get("version") or "")[:120]
            if name and version:
                result.append({"name": name, "version": version})
        return result

    def _manifest(
        self, plan: dict[str, Any], smoke: dict[str, Any],
        dependencies: list[dict[str, str]], *,
        source_audit: dict[str, Any], dependency_artifacts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        release = plan["release"]
        return {
            "schemaVersion": self.policy.schema_version,
            "runtime": "omlx", "version": release["version"],
            "channel": release["channel"], "tag": release["tag"],
            "sourceCommit": release["commit"], "artifactUrl": release["url"],
            "artifactFile": release["fileName"], "artifactSha256": release["sha256"],
            "installedAt": datetime.now(timezone.utc).isoformat(),
            "installerPython": copy.deepcopy(plan["installer"]["python"]),
            "dependencyPolicy": plan["installer"]["dependencyPolicy"],
            "sourceAudit": copy.deepcopy(source_audit),
            "dependencyArtifacts": copy.deepcopy(dependency_artifacts),
            "dependencies": dependencies,
            "smoke": copy.deepcopy(smoke),
            "selectionChanged": False, "finalPathVerified": True,
        }

    def _worker(self, plan: dict[str, Any]) -> None:
        release = plan["release"]
        target = Path(str(plan["destination"]["path"]))
        update_id = plan["id"][:16]
        log_dir = self.paths.update_dir() / "logs"
        log_path = log_dir / f"{update_id}.log"
        staging: Path | None = None
        selected_before = self.services.selected_binary()
        source_audit: dict[str, Any] = {}
        dependency_artifacts: list[dict[str, Any]] = []
        promoted_target = False
        try:
            self._check_cancelled()
            log_dir.mkdir(parents=True, exist_ok=True)
            root = self.paths.managed_dir().expanduser()
            if root.is_symlink():
                raise ValueError("The managed runtime root became a symbolic link; nothing was changed.")
            root.mkdir(parents=True, exist_ok=True)
            if root.resolve(strict=True) != target.parent.resolve(strict=True):
                raise ValueError("The approved runtime destination changed before work began.")

            if plan["action"] == "verify":
                provenance = self.services.managed_verification(str(target / "bin" / "omlx"))
                if not provenance.get("verified"):
                    raise RuntimeError("The installed runtime no longer matches the audited official wheel checksum.")
                source_audit = {
                    "mode": "adopted-official-provenance",
                    "artifactSha256": release["sha256"],
                    "detail": str(provenance.get("detail") or "Official wheel provenance matched."),
                }
                self._phase("smoke-testing", 0.55)
                self._event("Official checksum provenance matched. Running local version and dependency smoke tests…")
                smoke = self._smoke_runtime(target, release)
                dependencies = self._dependency_inventory(target)
                with self.lock:
                    self._check_cancelled()
                    self.services.write_json(target / self.policy.manifest_name, self._manifest(
                        plan, smoke, dependencies,
                        source_audit=source_audit, dependency_artifacts=dependency_artifacts,
                    ))
                    self._trust_committed = True
                action_label = "verified"
            else:
                artifact = self._download(plan, log_path)
                self._event("Root checksum matched. Auditing every direct-source URL and full commit in its package metadata…")
                source_audit = self._audit_official_wheel(artifact, release)
                source_audit.update({
                    "mode": "checksum-pinned-root-metadata",
                    "artifactSha256": release["sha256"],
                })
                if target.exists() or target.is_symlink():
                    raise RuntimeError("The versioned destination appeared after approval; it was not overwritten.")
                candidate = root / f".omlx-{release['version']}.installing-{uuid.uuid4().hex[:10]}"
                with self.lock:
                    self._check_cancelled()
                    try:
                        candidate.mkdir(mode=0o700)
                    except FileExistsError as error:
                        raise RuntimeError("A private staging destination collision occurred.") from error
                    # Cleanup receives this path only after we atomically created it.
                    staging = candidate
                python = str(plan["installer"]["python"]["path"])
                self._run_logged(
                    [python, "-m", "venv", str(staging)], log_path,
                    "installing", "Creating a fresh isolated Python environment", 0.36,
                )
                pip_environment = self._pip_environment()
                wheelhouse = staging / ".wheelhouse"
                wheelhouse.mkdir(mode=0o700)
                source_names = ",".join(
                    self._normalized_distribution(item.get("name"))
                    for item in release.get("directSources") or []
                )
                self._run_logged([
                    str(staging / "bin" / "python"), "-m", "pip", "--isolated",
                    "wheel", "--wheel-dir", str(wheelhouse), "--no-input", "--no-cache-dir",
                    "--index-url=https://pypi.org/simple", "--only-binary=:all:",
                    f"--no-binary={source_names}",
                    str(artifact),
                ], log_path, "installing", "Building a private wheelhouse from the audited commits and binary dependencies", 0.56, pip_environment)
                dependency_artifacts, install_paths = self._wheelhouse_inventory(
                    wheelhouse, artifact, release,
                )
                self._run_logged([
                    str(staging / "bin" / "python"), "-m", "pip", "--isolated",
                    "install", "--no-input", "--no-index", "--no-deps", "--only-binary=:all:",
                    *(str(path) for path in install_paths),
                ], log_path, "installing", "Installing only the hashed private wheelhouse with the network disabled", 0.74, pip_environment)
                if release["version"] == "0.6.4":
                    self._event("Applying the verified DFlash thinking-budget correction to this private copy…")
                    self.services.patch_apply(staging)
                self._phase("smoke-testing", 0.84)
                self._event("Install finished in staging. Running preliminary version, dependency, command, and native-kernel checks…")
                self._smoke_runtime(staging, release)
                if wheelhouse.is_symlink() or wheelhouse.parent != staging:
                    raise RuntimeError("The private wheelhouse changed before final cleanup.")
                shutil.rmtree(wheelhouse)
                if target.exists() or target.is_symlink():
                    raise RuntimeError("The final destination appeared during smoke testing; it was not overwritten.")
                rebased_commands = self._rebase_staged_environment(staging, target)
                self._phase("promoting", 0.94)
                self._event("Preliminary checks passed. Atomically promoting the rebased copy for final-path verification…")
                with self.lock:
                    self._check_cancelled()
                    os.replace(staging, target)
                    staging = None
                    promoted_target = True
                self._phase("smoke-testing", 0.97)
                self._event("Running every smoke test again from the final installed path before recording trust…")
                smoke = self._smoke_runtime(target, release)
                dependencies = self._dependency_inventory(target)
                manifest = self._manifest(
                    plan, smoke, dependencies,
                    source_audit=source_audit, dependency_artifacts=dependency_artifacts,
                )
                manifest["rebasedCommands"] = rebased_commands
                with self.lock:
                    self._check_cancelled()
                    self.services.write_json(target / self.policy.manifest_name, manifest)
                    self._trust_committed = True
                promoted_target = False
                action_label = "installed"

            self.services.invalidate_kernel_cache()
            candidate = next(
                (item for item in self.services.candidates()
                 if Path(item["path"]).expanduser().resolve(strict=False) == (target / "bin" / "omlx").resolve(strict=False)),
                None,
            )
            result = {
                "runtime": "omlx", "version": release["version"],
                "channel": release["channel"], "action": action_label,
                "path": str(target / "bin" / "omlx"),
                "candidateId": candidate.get("id") if candidate else None,
                "selectedBefore": selected_before, "selectedAfter": self.services.selected_binary(),
                "selectionChanged": self.services.selected_binary() != selected_before,
                "verified": True, "smoke": smoke,
                "stagedArtifactCount": len(dependency_artifacts),
                "nextAction": (
                    "This copy is already selected; run Benchmark Lab before treating preview acceleration as fastest."
                    if plan["destination"].get("selected") else
                    "Review the new installed candidate, explicitly choose it for new sessions, then run Benchmark Lab."
                ),
            }
            with self.lock:
                self._check_cancelled()
                self.state["phase"] = "completed"
                self.state["progress"] = 1.0
                self.state["result"] = copy.deepcopy(result)
            self._event(
                f"oMLX {release['version']} {action_label} successfully. The selected runtime was not changed."
            )
        except (RuntimeUpdateCancelled, self.services.cancelled_error):
            with self.lock:
                self.state["phase"] = "cancelled"
            self._event("Runtime update stopped. The selected runtime was unchanged; resumable download bytes were kept.", "warning")
        except Exception as error:  # noqa: BLE001
            if self.cancel_event.is_set():
                with self.lock:
                    self.state["phase"] = "cancelled"
                self._event("Runtime update stopped. The selected runtime was unchanged.", "warning")
            else:
                with self.lock:
                    self.state["phase"] = "failed"
                self._event(str(error), "error")
        finally:
            if staging is not None:
                self._safe_cleanup_staging(staging)
            if promoted_target:
                self._safe_cleanup_failed_promotion(target, str(release["version"]))
            with self.lock:
                process = self.process
            if process is not None:
                self._retire_process(process)
            with self.lock:
                self.process = None
                if self.thread is threading.current_thread():
                    self.thread = None
