"""Pinned model-download jobs with explicit controller-independent boundaries.

Owns Setup Assistant and Model Acquisition admission, status, inspection caches,
verification orchestration, resumable markers and only their downloader groups.
Model/runtime policies and authoritative artifact validators stay with callers.
"""
from __future__ import annotations
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import threading
import time
from typing import Any, Callable
from log_tail import read_log_tail


class DownloadCancelled(RuntimeError):
    """An owned job stopped before it could commit a verified result."""


@dataclass(frozen=True)
class ProcessPolicy:
    poll_seconds: float = 0.5
    terminate_seconds: float = 8.0
    kill_seconds: float = 3.0
    cancel_join_seconds: float = 1.0


@dataclass(frozen=True)
class SetupPolicy:
    state_dir: Path
    draft_repo: str
    draft_bytes: int
    draft_size_label: str
    process: ProcessPolicy = ProcessPolicy()


@dataclass(frozen=True)
class AcquisitionPolicy:
    state_dir: Path
    plan_ttl_seconds: float
    schema_version: int
    marker_name: str
    process: ProcessPolicy = ProcessPolicy()


@dataclass(frozen=True)
class SetupServices:
    validated_plan: Callable[[dict[str, Any], list[dict[str, Any]]], tuple[dict[str, Any], dict[str, Any]]]
    download_argv: Callable[[dict[str, Any]], list[str]]
    present_bytes: Callable[[Path], int]
    verify_draft: Callable[[Path], tuple[bool, str]]
    launcher_idle: Callable[[], bool]
    benchmark_active: Callable[[], bool]
    cancelled_error: type[Exception] = DownloadCancelled


@dataclass(frozen=True)
class AcquisitionServices:
    validate_repo: Callable[[Any], str]
    validate_revision: Callable[[Any], str]
    fetch_snapshot: Callable[[str, str], dict[str, Any]]
    build_plan: Callable[[dict[str, Any], str, str], dict[str, Any]]
    download_argv: Callable[[dict[str, Any]], list[str]]
    public_environment: Callable[[], dict[str, str]]
    present_bytes: Callable[[Path, list[dict[str, Any]]], int]
    safe_child: Callable[[Path, str], Path]
    write_marker: Callable[[Path, dict[str, Any]], None]
    verify_artifacts: Callable[[dict[str, Any], threading.Event, Callable[[float], None]], dict[str, Any]]
    launcher_idle: Callable[[], bool]
    benchmark_active: Callable[[], bool]
    cancelled_error: type[Exception] = DownloadCancelled


def terminate_owned_downloader(process: subprocess.Popen, policy: ProcessPolicy = ProcessPolicy()) -> None:
    """Retire the fresh downloader session even when its leader exits first."""
    running = process.poll() is None
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except OSError:
        return
    try:
        if running:
            process.wait(timeout=policy.terminate_seconds)
        else:
            time.sleep(min(policy.terminate_seconds, 0.25))
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        return
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
        if running:
            process.wait(timeout=policy.kill_seconds)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _check_cancelled(cancel_event: threading.Event, message: str) -> None:
    if cancel_event.is_set():
        raise DownloadCancelled(message)


class _DownloadOwnership:
    """A job's cancellation and only its freshly spawned downloader group."""

    def _initialize_ownership(self) -> None:
        self._process_cleanup_lock = threading.Lock()
        self._retired_process: subprocess.Popen | None = None

    def _retire_process(self, process: subprocess.Popen) -> None:
        with self._process_cleanup_lock:
            if self._retired_process is process:
                return
            terminate_owned_downloader(process, self.policy.process)
            self._retired_process = process
            with self.lock:
                if self.process is process:
                    self.process = None

    def _publish_process(self, process: subprocess.Popen, cancel_event: threading.Event) -> None:
        with self.lock:
            accepted = cancel_event is self.cancel_event and not cancel_event.is_set()
            if accepted:
                self.process = process
                self.state["phase"] = "downloading"
        if not accepted:
            self._retire_process(process)
            raise DownloadCancelled("The download was cancelled before its process was published.")

    def _cancel_download(self, message: str) -> None:
        with self.lock:
            # is_active includes teardown threads to exclude an overlapping
            # retry; it must not reopen an already committed terminal result.
            if self.state.get("phase") not in self.ACTIVE_PHASES:
                return
            self.cancel_event.set()
            self.state["phase"] = "stopping"
            self.state["message"] = message
            process, thread = self.process, self.thread
        if process is not None:
            self._retire_process(process)
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=self.policy.process.cancel_join_seconds)


class SetupManager(_DownloadOwnership):
    """Own one explicit, pinned model download without touching runtime installs."""

    ACTIVE_PHASES = {"queued", "downloading", "stopping", "verifying"}

    def __init__(self, policy: SetupPolicy, services: SetupServices) -> None:
        self.policy = policy
        self.services = services
        self._initialize_ownership()
        self.lock = threading.RLock()
        self.cancel_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.process: subprocess.Popen | None = None
        self.state: dict[str, Any] = {
            "phase": "idle", "message": "No setup action is running.",
            "progress": 0.0, "downloadedBytes": 0, "plan": None, "events": [],
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

    def start(self, payload: dict[str, Any], models: list[dict[str, Any]]) -> dict[str, Any]:
        _model, plan = self.services.validated_plan(payload, models)
        if payload.get("confirmation") != self.policy.draft_repo:
            raise ValueError("Confirm the pinned DFlash 2 download in Setup Assistant first.")
        draft = plan["draft"]
        if draft.get("complete"):
            raise ValueError("The complete pinned DFlash 2 draft is already installed.")
        if not draft.get("canDownload"):
            raise ValueError(str(draft.get("detail") or "This download cannot start safely."))
        if not self.services.launcher_idle():
            raise ValueError("Stop the active launcher session before downloading a model.")
        if self.services.benchmark_active():
            raise ValueError("Stop Benchmark Lab before downloading a model.")
        with self.lock:
            if self.is_active():
                raise ValueError("A setup download is already running.")
            self.cancel_event = threading.Event()
            self._retired_process = None
            initial = int(draft.get("existingBytes") or 0)
            self.state = {
                "phase": "queued",
                "message": "Download approved. Preparing the pinned destination…",
                "progress": min(0.98, initial / self.policy.draft_bytes),
                "downloadedBytes": initial,
                "plan": copy.deepcopy(plan), "events": [],
            }
            thread = threading.Thread(target=self._worker, args=(copy.deepcopy(plan), self.cancel_event), daemon=True)
            self.thread = thread
            try:
                thread.start()
            except Exception as error:
                self.thread = None
                self.state["phase"] = "failed"
                self._event(str(error), "error")
                raise
            return copy.deepcopy(plan)

    @staticmethod
    def _terminate(process: subprocess.Popen) -> None:
        terminate_owned_downloader(process)


    def cancel(self) -> None:
        self._cancel_download("Stopping the download; completed files will be kept for resume…")

    @staticmethod
    def _log_tail(path: Path) -> str:
        return read_log_tail(path, 2_000).strip()


    def _worker(self, plan: dict[str, Any], cancel_event: threading.Event | None = None) -> None:
        cancel_event = cancel_event or self.cancel_event
        draft = plan["draft"]
        destination = Path(str(draft["destination"]))
        setup_dir = self.policy.state_dir / "setup"
        log_path = setup_dir / f"{plan['id']}.log"
        process: subprocess.Popen | None = None
        try:
            _check_cancelled(cancel_event, "Setup download cancelled.")
            argv = self.services.download_argv(plan)
            _check_cancelled(cancel_event, "Setup download cancelled.")
            destination.mkdir(parents=True, exist_ok=True)
            setup_dir.mkdir(parents=True, exist_ok=True)
            _check_cancelled(cancel_event, "Setup download cancelled.")
            with open(log_path, "ab", buffering=0) as log_handle:
                process = subprocess.Popen(
                    argv, stdin=subprocess.DEVNULL, stdout=log_handle,
                    stderr=subprocess.STDOUT, start_new_session=True,
                    close_fds=True,
                )
                self._publish_process(process, cancel_event)
                self._event(
                    f"Downloading the pinned {self.policy.draft_size_label} draft. "
                    "Partial files remain resumable if stopped."
                )
                while process.poll() is None:
                    if cancel_event.wait(self.policy.process.poll_seconds):
                        self._retire_process(process)
                        raise DownloadCancelled("Setup download cancelled.")
                    downloaded = self.services.present_bytes(destination)
                    with self.lock:
                        self.state["downloadedBytes"] = downloaded
                        self.state["progress"] = min(0.98, downloaded / self.policy.draft_bytes)
                return_code = process.wait()
            self._retire_process(process)
            if cancel_event.is_set():
                raise DownloadCancelled("Setup download cancelled.")
            if return_code != 0:
                detail = self._log_tail(log_path)
                raise RuntimeError(
                    "The pinned draft download failed. Existing files were kept for resume."
                    + (f" {detail}" if detail else "")
                )

            with self.lock:
                _check_cancelled(cancel_event, "Setup download cancelled.")
                self.state["phase"] = "verifying"
                self.state["progress"] = 0.99
            self._event("Download finished. Verifying tensor structure and target pairing…")
            ready, status = self.services.verify_draft(destination)
            _check_cancelled(cancel_event, "Setup download cancelled.")
            if not ready:
                raise RuntimeError(
                    f"The download finished but failed strict DFlash 2 validation ({status}). "
                    "It was not marked ready."
                )
            present_bytes = self.services.present_bytes(destination)
            with self.lock:
                _check_cancelled(cancel_event, "Setup download cancelled.")
                self.state["phase"] = "completed"
                self.state["progress"] = 1.0
                self.state["downloadedBytes"] = present_bytes
                public_plan = self.state.get("plan")
                if isinstance(public_plan, dict) and isinstance(public_plan.get("draft"), dict):
                    public_draft = public_plan["draft"]
                    public_draft.update({
                        "detected": True, "complete": True,
                        "status": "Complete and strictly verified",
                        "existingBytes": present_bytes, "remainingBytes": 0,
                        "admissionBytes": 0, "diskReady": True,
                        "canDownload": False,
                        "detail": "The complete pinned draft is installed and strictly verified.",
                    })
                    runtime_supported = bool(public_plan.get("runtime", {}).get("supported"))
                    public_plan["ready"] = runtime_supported
                    public_plan["stepsRemaining"] = int(not runtime_supported)
            self._event(
                "Pinned draft verified. Refresh models, finish the official oMLX upgrade if needed, "
                "then run Benchmark Lab."
            )
        except (DownloadCancelled, self.services.cancelled_error):
            with self.lock:
                self.state["phase"] = "cancelled"
                self.state["downloadedBytes"] = self.services.present_bytes(destination)
            self._event("Download stopped. Completed files were preserved for a later resume.", "warning")
        except Exception as error:  # noqa: BLE001
            if cancel_event.is_set():
                with self.lock:
                    self.state["phase"] = "cancelled"
                self._event("Download stopped. Completed files were preserved for a later resume.", "warning")
            else:
                with self.lock:
                    self.state["phase"] = "failed"
                self._event(str(error), "error")
        finally:
            if process is not None:
                self._retire_process(process)
            with self.lock:
                if self.process is process:
                    self.process = None
                if self.thread is threading.current_thread():
                    self.thread = None

class ModelAcquisitionManager(_DownloadOwnership):
    """Own public Hub inspection plans and one exact, resumable model download."""

    ACTIVE_PHASES = {"queued", "downloading", "stopping", "verifying"}

    def __init__(self, policy: AcquisitionPolicy, services: AcquisitionServices) -> None:
        self.policy = policy
        self.services = services
        self._initialize_ownership()
        self.lock = threading.RLock()
        self.cancel_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.process: subprocess.Popen | None = None
        self.plans: dict[str, dict[str, Any]] = {}
        self.snapshots: dict[str, tuple[float, dict[str, Any]]] = {}
        self.state: dict[str, Any] = {
            "phase": "idle", "message": "No model acquisition is running.",
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
        self.snapshots = {
            key: entry for key, entry in self.snapshots.items()
            if float(entry[0]) > now
        }

    def inspect(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.is_active():
            raise ValueError("Wait for the active model acquisition to finish before replacing its plan.")
        repo_id = self.services.validate_repo(payload.get("repoId"))
        revision = self.services.validate_revision(payload.get("revision"))
        destination_kind = str(payload.get("destination") or "lmstudio")
        variant_id = str(payload.get("variantId") or "")
        cache_key = f"{repo_id}@{revision or 'default'}"
        with self.lock:
            self._prune()
            cached = self.snapshots.get(cache_key)
        if cached:
            snapshot = copy.deepcopy(cached[1])
        else:
            snapshot = self.services.fetch_snapshot(repo_id, revision)
            with self.lock:
                self.snapshots[cache_key] = (
                    time.time() + self.policy.plan_ttl_seconds,
                    copy.deepcopy(snapshot),
                )
        plan = self.services.build_plan(snapshot, destination_kind, variant_id)
        expires = time.time() + self.policy.plan_ttl_seconds
        plan["expiresAt"] = datetime.fromtimestamp(expires, timezone.utc).isoformat()
        with self.lock:
            if self.is_active():
                raise ValueError("Wait for the active model acquisition to finish before replacing its plan.")
            self._prune()
            self.plans[plan["id"]] = {
                "expires": expires, "snapshot": copy.deepcopy(snapshot),
                "destination": destination_kind,
                "variantId": plan.get("selection", {}).get("id") if isinstance(plan.get("selection"), dict) else variant_id,
                "plan": copy.deepcopy(plan),
            }
        return plan

    def _validated_start_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan_id = str(payload.get("planId") or "")
        with self.lock:
            self._prune()
            entry = copy.deepcopy(self.plans.get(plan_id))
        if not entry:
            raise ValueError("The acquisition plan expired or changed. Inspect the repository again.")
        plan = self.services.build_plan(
            entry["snapshot"], entry["destination"], entry["variantId"],
        )
        if plan.get("id") != plan_id:
            raise ValueError("The pinned acquisition identity changed. Inspect the repository again.")
        if payload.get("licenseReviewed") is not True:
            raise ValueError("Review the model page and license before approving this download.")
        if not secrets.compare_digest(
            str(payload.get("confirmation") or ""), str(plan.get("confirmation") or ""),
        ):
            raise ValueError("Confirm the exact repository and pinned commit before downloading.")
        if not plan.get("canStart"):
            blocked = next(
                (check.get("detail") for check in plan.get("checks", []) if check.get("state") == "blocked"),
                "This acquisition cannot start safely.",
            )
            raise ValueError(str(blocked))
        return plan

    def start(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan = self._validated_start_plan(payload)
        if not self.services.launcher_idle():
            raise ValueError("Stop the active launcher session before downloading a model.")
        if self.services.benchmark_active():
            raise ValueError("Stop Benchmark Lab before downloading a model.")
        with self.lock:
            if self.is_active():
                raise ValueError("A model acquisition is already running.")
            self.cancel_event = threading.Event()
            self._retired_process = None
            initial = int(plan.get("destination", {}).get("existingBytes") or 0)
            total = int(plan.get("selection", {}).get("sizeBytes") or 1)
            self.state = {
                "phase": "queued",
                "message": "Acquisition approved. Preparing the pinned destination…",
                "progress": min(0.97, initial / max(1, total) * 0.97),
                "downloadedBytes": initial,
                "plan": copy.deepcopy(plan), "result": None, "events": [],
            }
            thread = threading.Thread(target=self._worker, args=(copy.deepcopy(plan), self.cancel_event), daemon=True)
            self.thread = thread
            try:
                thread.start()
            except Exception as error:
                self.thread = None
                self.state["phase"] = "failed"
                self._event(str(error), "error")
                raise
        return copy.deepcopy(plan)

    @staticmethod
    def _terminate(process: subprocess.Popen) -> None:
        terminate_owned_downloader(process)


    def cancel(self) -> None:
        self._cancel_download("Stopping the model download; verified files and partial cache data will remain for resume…")

    @staticmethod
    def _log_tail(path: Path) -> str:
        return read_log_tail(path, 2_000).strip()


    def _marker_value(self, plan: dict[str, Any], status: str, verification: dict[str, Any] | None = None) -> dict[str, Any]:
        repo = plan["repo"]
        selection = plan["selection"]
        return {
            "schemaVersion": self.policy.schema_version,
            "repoId": repo["id"], "pinnedRevision": repo["pinnedRevision"],
            "variantId": selection["id"], "format": selection["format"],
            "files": [
                {"path": item["path"], "size": item["size"], "sha256": item.get("sha256") or ""}
                for item in selection["files"]
            ],
            "status": status,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "verification": copy.deepcopy(verification),
        }

    def _update_marker(self, plan: dict[str, Any], status: str, verification: dict[str, Any] | None = None) -> None:
        destination = Path(str(plan["destination"]["path"])).resolve(strict=False)
        marker_path = self.services.safe_child(destination, self.policy.marker_name)
        self.services.write_marker(marker_path, self._marker_value(plan, status, verification))

    def _verification_progress(self, fraction: float) -> None:
        with self.lock:
            self.state["progress"] = 0.98 + min(1.0, max(0.0, float(fraction))) * 0.02

    def _worker(self, plan: dict[str, Any], cancel_event: threading.Event | None = None) -> None:
        cancel_event = cancel_event or self.cancel_event
        destination = Path(str(plan["destination"]["path"])).resolve(strict=False)
        acquisition_dir = self.policy.state_dir / "acquisition"
        log_path = acquisition_dir / f"{plan['id']}.log"
        process: subprocess.Popen | None = None
        destination_prepared = False
        try:
            # Validate the complete argv before creating anything. Resolve again
            # after mkdir so a replaced parent symlink cannot escape known roots.
            _check_cancelled(cancel_event, "Model acquisition cancelled.")
            argv = self.services.download_argv(plan)
            _check_cancelled(cancel_event, "Model acquisition cancelled.")
            destination.mkdir(parents=True, exist_ok=True)
            if Path(str(plan["destination"]["path"])).resolve(strict=True) != destination:
                raise ValueError("The acquisition destination changed before download.")
            destination_prepared = True
            acquisition_dir.mkdir(parents=True, exist_ok=True)
            self._update_marker(plan, "verifying" if plan.get("action") == "verify" else "downloading")
            _check_cancelled(cancel_event, "Model acquisition cancelled.")
            if plan.get("action") != "verify":
                with open(log_path, "ab", buffering=0) as log_handle:
                    process = subprocess.Popen(
                        argv, stdin=subprocess.DEVNULL, stdout=log_handle,
                        stderr=subprocess.STDOUT, start_new_session=True,
                        close_fds=True, env=self.services.public_environment(),
                    )
                    self._publish_process(process, cancel_event)
                    self._event(
                        f"Downloading {plan['selection']['fileCount']} exact files from "
                        f"{plan['repo']['id']}@{plan['repo']['pinnedRevision'][:12]}. Partial files remain resumable."
                    )
                    total = int(plan["selection"]["sizeBytes"])
                    while process.poll() is None:
                        if cancel_event.wait(self.policy.process.poll_seconds):
                            self._retire_process(process)
                            raise DownloadCancelled("Model acquisition cancelled.")
                        present = self.services.present_bytes(destination, plan["selection"]["files"])
                        with self.lock:
                            self.state["downloadedBytes"] = present
                            self.state["progress"] = min(0.97, present / max(1, total) * 0.97)
                    return_code = process.wait()
                self._retire_process(process)
                if cancel_event.is_set():
                    raise DownloadCancelled("Model acquisition cancelled.")
                if return_code != 0:
                    detail = self._log_tail(log_path)
                    raise RuntimeError(
                        "The pinned model download failed. Existing files were preserved for resume."
                        + (f" {detail}" if detail else "")
                    )

            with self.lock:
                _check_cancelled(cancel_event, "Model acquisition cancelled.")
                self.state["phase"] = "verifying"
                self.state["progress"] = 0.98
                self.state["downloadedBytes"] = self.services.present_bytes(
                    destination, plan["selection"]["files"],
                )
            self._event("Download complete. Verifying exact sizes, pinned checksums, and artifact structure…")
            verification = self.services.verify_artifacts(
                plan, cancel_event, self._verification_progress,
            )
            _check_cancelled(cancel_event, "Model acquisition cancelled.")
            self._update_marker(plan, "verified", verification)
            result = {
                **verification,
                "repoId": plan["repo"]["id"],
                "pinnedRevision": plan["repo"]["pinnedRevision"],
                "destination": str(destination),
                "modelName": plan["repo"]["id"].split("/", 1)[1],
                "nextAction": "Rescan Model Library, inspect the exact runtime routes, then benchmark before claiming a fastest engine.",
            }
            with self.lock:
                _check_cancelled(cancel_event, "Model acquisition cancelled.")
                self.state["phase"] = "completed"
                self.state["progress"] = 1.0
                self.state["downloadedBytes"] = int(plan["selection"]["sizeBytes"])
                self.state["result"] = copy.deepcopy(result)
                public_plan = self.state.get("plan")
                if isinstance(public_plan, dict):
                    public_plan["action"] = "verified"
                    public_plan["actionLabel"] = "Verified and ready to rescan"
            self._event("Pinned model files verified. Open Model Library to inspect the newly scanned routes.")
        except (DownloadCancelled, self.services.cancelled_error):
            try:
                if destination_prepared:
                    self._update_marker(plan, "partial")
            except Exception:  # noqa: BLE001
                pass
            with self.lock:
                self.state["phase"] = "cancelled"
                self.state["downloadedBytes"] = self.services.present_bytes(
                    destination, plan["selection"]["files"],
                ) if destination.exists() else 0
            self._event("Model acquisition stopped. Existing verified files and partial cache data were preserved for resume.", "warning")
        except Exception as error:  # noqa: BLE001
            try:
                if destination_prepared:
                    self._update_marker(plan, "failed")
            except Exception:  # noqa: BLE001
                pass
            if cancel_event.is_set():
                with self.lock:
                    self.state["phase"] = "cancelled"
                self._event("Model acquisition stopped. Existing files were preserved for resume.", "warning")
            else:
                with self.lock:
                    self.state["phase"] = "failed"
                self._event(str(error), "error")
        finally:
            if process is not None:
                self._retire_process(process)
            with self.lock:
                if self.process is process:
                    self.process = None
                if self.thread is threading.current_thread():
                    self.thread = None
