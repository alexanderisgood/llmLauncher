"""Frozen pre-extraction manager behavior; test-only controller dependencies."""
from __future__ import annotations
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import threading
import time
from typing import Any
from launcher import (
    validated_setup_request, DFLASH2_DRAFT_REPO, DFLASH2_DRAFT_BYTES,
    DFLASH2_DRAFT_SIZE_LABEL, STATE_DIR, build_dflash2_download_argv,
    read_log_tail, directory_size, read_json, weight_completeness,
    dflash2_draft_complete, LaunchCancelled, validated_hf_repo_id,
    validated_hf_revision, fetch_model_acquisition_snapshot,
    build_model_acquisition_plan, MODEL_ACQUISITION_PLAN_TTL_SECONDS,
    MODEL_ACQUISITION_SCHEMA_VERSION, MODEL_ACQUISITION_MARKER,
    _acquisition_safe_child, atomic_json, build_model_acquisition_download_argv,
    _hf_public_environment, _acquisition_present_bytes, verify_model_acquisition,
)

class SetupManager:
    """Own one explicit, pinned model download without touching runtime installs."""

    ACTIVE_PHASES = {"queued", "downloading", "stopping", "verifying"}

    def __init__(self, run_manager: RunManager, benchmark_manager: BenchmarkManager) -> None:
        self.run_manager = run_manager
        self.benchmark_manager = benchmark_manager
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
        _model, plan = validated_setup_request(payload, models)
        if payload.get("confirmation") != DFLASH2_DRAFT_REPO:
            raise ValueError("Confirm the pinned DFlash 2 download in Setup Assistant first.")
        draft = plan["draft"]
        if draft.get("complete"):
            raise ValueError("The complete pinned DFlash 2 draft is already installed.")
        if not draft.get("canDownload"):
            raise ValueError(str(draft.get("detail") or "This download cannot start safely."))
        if self.run_manager.snapshot().get("phase") != "idle":
            raise ValueError("Stop the active launcher session before downloading a model.")
        if self.benchmark_manager.is_active():
            raise ValueError("Stop Benchmark Lab before downloading a model.")
        with self.lock:
            if self.is_active():
                raise ValueError("A setup download is already running.")
            self.cancel_event = threading.Event()
            initial = int(draft.get("existingBytes") or 0)
            self.state = {
                "phase": "queued",
                "message": "Download approved. Preparing the pinned destination…",
                "progress": min(0.98, initial / DFLASH2_DRAFT_BYTES),
                "downloadedBytes": initial,
                "plan": copy.deepcopy(plan), "events": [],
            }
            thread = threading.Thread(target=self._worker, args=(copy.deepcopy(plan),), daemon=True)
            self.thread = thread
            thread.start()
            return copy.deepcopy(plan)

    @staticmethod
    def _terminate(process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                pass

    def cancel(self) -> None:
        with self.lock:
            if not self.is_active():
                return
            self.cancel_event.set()
            self.state["phase"] = "stopping"
            self.state["message"] = "Stopping the download; completed files will be kept for resume…"
            process = self.process
        if process is not None:
            self._terminate(process)

    @staticmethod
    def _log_tail(path: Path) -> str:
        return read_log_tail(path, 2_000).strip()

    def _worker(self, plan: dict[str, Any]) -> None:
        draft = plan["draft"]
        destination = Path(str(draft["destination"]))
        setup_dir = STATE_DIR / "setup"
        log_path = setup_dir / f"{plan['id']}.log"
        process: subprocess.Popen | None = None
        try:
            destination.mkdir(parents=True, exist_ok=True)
            setup_dir.mkdir(parents=True, exist_ok=True)
            argv = build_dflash2_download_argv(plan)
            with open(log_path, "ab", buffering=0) as log_handle:
                process = subprocess.Popen(
                    argv, stdin=subprocess.DEVNULL, stdout=log_handle,
                    stderr=subprocess.STDOUT, start_new_session=True,
                    close_fds=True,
                )
                with self.lock:
                    self.process = process
                    self.state["phase"] = "downloading"
                self._event(
                    f"Downloading the pinned {DFLASH2_DRAFT_SIZE_LABEL} draft. "
                    "Partial files remain resumable if stopped."
                )
                while process.poll() is None:
                    if self.cancel_event.wait(0.5):
                        self._terminate(process)
                        raise LaunchCancelled("Setup download cancelled.")
                    downloaded = directory_size(destination)
                    with self.lock:
                        self.state["downloadedBytes"] = downloaded
                        self.state["progress"] = min(0.98, downloaded / DFLASH2_DRAFT_BYTES)
                return_code = process.wait()
            if self.cancel_event.is_set():
                raise LaunchCancelled("Setup download cancelled.")
            if return_code != 0:
                detail = self._log_tail(log_path)
                raise RuntimeError(
                    "The pinned draft download failed. Existing files were kept for resume."
                    + (f" {detail}" if detail else "")
                )

            with self.lock:
                self.state["phase"] = "verifying"
                self.state["progress"] = 0.99
            self._event("Download finished. Verifying tensor structure and target pairing…")
            config = read_json(destination / "config.json")
            ready, status, measured = weight_completeness(destination, config)
            if not ready or not dflash2_draft_complete(destination, config):
                raise RuntimeError(
                    f"The download finished but failed strict DFlash 2 validation ({status}). "
                    "It was not marked ready."
                )
            present_bytes = directory_size(destination)
            with self.lock:
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
        except LaunchCancelled:
            with self.lock:
                self.state["phase"] = "cancelled"
                self.state["downloadedBytes"] = directory_size(destination)
            self._event("Download stopped. Completed files were preserved for a later resume.", "warning")
        except Exception as error:  # noqa: BLE001
            if self.cancel_event.is_set():
                with self.lock:
                    self.state["phase"] = "cancelled"
                self._event("Download stopped. Completed files were preserved for a later resume.", "warning")
            else:
                with self.lock:
                    self.state["phase"] = "failed"
                self._event(str(error), "error")
        finally:
            if process is not None and process.poll() is None:
                self._terminate(process)
            with self.lock:
                if self.process is process:
                    self.process = None
                if self.thread is threading.current_thread():
                    self.thread = None

class ModelAcquisitionManager:
    """Own public Hub inspection plans and one exact, resumable model download."""

    ACTIVE_PHASES = {"queued", "downloading", "stopping", "verifying"}

    def __init__(self, run_manager: RunManager, benchmark_manager: BenchmarkManager) -> None:
        self.run_manager = run_manager
        self.benchmark_manager = benchmark_manager
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
        repo_id = validated_hf_repo_id(payload.get("repoId"))
        revision = validated_hf_revision(payload.get("revision"))
        destination_kind = str(payload.get("destination") or "lmstudio")
        variant_id = str(payload.get("variantId") or "")
        cache_key = f"{repo_id}@{revision or 'default'}"
        with self.lock:
            self._prune()
            cached = self.snapshots.get(cache_key)
        if cached:
            snapshot = copy.deepcopy(cached[1])
        else:
            snapshot = fetch_model_acquisition_snapshot(repo_id, revision)
            with self.lock:
                self.snapshots[cache_key] = (
                    time.time() + MODEL_ACQUISITION_PLAN_TTL_SECONDS,
                    copy.deepcopy(snapshot),
                )
        plan = build_model_acquisition_plan(snapshot, destination_kind, variant_id)
        expires = time.time() + MODEL_ACQUISITION_PLAN_TTL_SECONDS
        plan["expiresAt"] = datetime.fromtimestamp(expires, timezone.utc).isoformat()
        with self.lock:
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
        plan = build_model_acquisition_plan(
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
        if self.run_manager.snapshot().get("phase") != "idle":
            raise ValueError("Stop the active launcher session before downloading a model.")
        if self.benchmark_manager.is_active():
            raise ValueError("Stop Benchmark Lab before downloading a model.")
        with self.lock:
            if self.is_active():
                raise ValueError("A model acquisition is already running.")
            self.cancel_event = threading.Event()
            initial = int(plan.get("destination", {}).get("existingBytes") or 0)
            total = int(plan.get("selection", {}).get("sizeBytes") or 1)
            self.state = {
                "phase": "queued",
                "message": "Acquisition approved. Preparing the pinned destination…",
                "progress": min(0.97, initial / max(1, total) * 0.97),
                "downloadedBytes": initial,
                "plan": copy.deepcopy(plan), "result": None, "events": [],
            }
            thread = threading.Thread(target=self._worker, args=(copy.deepcopy(plan),), daemon=True)
            self.thread = thread
            thread.start()
        return copy.deepcopy(plan)

    @staticmethod
    def _terminate(process: subprocess.Popen) -> None:
        SetupManager._terminate(process)

    def cancel(self) -> None:
        with self.lock:
            if not self.is_active():
                return
            self.cancel_event.set()
            self.state["phase"] = "stopping"
            self.state["message"] = "Stopping the model download; verified files and partial cache data will remain for resume…"
            process = self.process
        if process is not None:
            self._terminate(process)

    @staticmethod
    def _log_tail(path: Path) -> str:
        return SetupManager._log_tail(path)

    @staticmethod
    def _marker_value(plan: dict[str, Any], status: str, verification: dict[str, Any] | None = None) -> dict[str, Any]:
        repo = plan["repo"]
        selection = plan["selection"]
        return {
            "schemaVersion": MODEL_ACQUISITION_SCHEMA_VERSION,
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
        marker_path = _acquisition_safe_child(destination, MODEL_ACQUISITION_MARKER)
        atomic_json(marker_path, self._marker_value(plan, status, verification))

    def _verification_progress(self, fraction: float) -> None:
        with self.lock:
            self.state["progress"] = 0.98 + min(1.0, max(0.0, float(fraction))) * 0.02

    def _worker(self, plan: dict[str, Any]) -> None:
        destination = Path(str(plan["destination"]["path"])).resolve(strict=False)
        acquisition_dir = STATE_DIR / "acquisition"
        log_path = acquisition_dir / f"{plan['id']}.log"
        process: subprocess.Popen | None = None
        try:
            # Validate the complete argv before creating anything. Resolve again
            # after mkdir so a replaced parent symlink cannot escape known roots.
            argv = build_model_acquisition_download_argv(plan)
            destination.mkdir(parents=True, exist_ok=True)
            if Path(str(plan["destination"]["path"])).resolve(strict=True) != destination:
                raise ValueError("The acquisition destination changed before download.")
            acquisition_dir.mkdir(parents=True, exist_ok=True)
            self._update_marker(plan, "verifying" if plan.get("action") == "verify" else "downloading")
            if plan.get("action") != "verify":
                with open(log_path, "ab", buffering=0) as log_handle:
                    process = subprocess.Popen(
                        argv, stdin=subprocess.DEVNULL, stdout=log_handle,
                        stderr=subprocess.STDOUT, start_new_session=True,
                        close_fds=True, env=_hf_public_environment(),
                    )
                    with self.lock:
                        self.process = process
                        self.state["phase"] = "downloading"
                    self._event(
                        f"Downloading {plan['selection']['fileCount']} exact files from "
                        f"{plan['repo']['id']}@{plan['repo']['pinnedRevision'][:12]}. Partial files remain resumable."
                    )
                    total = int(plan["selection"]["sizeBytes"])
                    while process.poll() is None:
                        if self.cancel_event.wait(0.5):
                            self._terminate(process)
                            raise LaunchCancelled("Model acquisition cancelled.")
                        present = _acquisition_present_bytes(destination, plan["selection"]["files"])
                        with self.lock:
                            self.state["downloadedBytes"] = present
                            self.state["progress"] = min(0.97, present / max(1, total) * 0.97)
                    return_code = process.wait()
                if self.cancel_event.is_set():
                    raise LaunchCancelled("Model acquisition cancelled.")
                if return_code != 0:
                    detail = self._log_tail(log_path)
                    raise RuntimeError(
                        "The pinned model download failed. Existing files were preserved for resume."
                        + (f" {detail}" if detail else "")
                    )

            with self.lock:
                self.state["phase"] = "verifying"
                self.state["progress"] = 0.98
                self.state["downloadedBytes"] = _acquisition_present_bytes(
                    destination, plan["selection"]["files"],
                )
            self._event("Download complete. Verifying exact sizes, pinned checksums, and artifact structure…")
            verification = verify_model_acquisition(
                plan, self.cancel_event, self._verification_progress,
            )
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
                self.state["phase"] = "completed"
                self.state["progress"] = 1.0
                self.state["downloadedBytes"] = int(plan["selection"]["sizeBytes"])
                self.state["result"] = copy.deepcopy(result)
                public_plan = self.state.get("plan")
                if isinstance(public_plan, dict):
                    public_plan["action"] = "verified"
                    public_plan["actionLabel"] = "Verified and ready to rescan"
            self._event("Pinned model files verified. Open Model Library to inspect the newly scanned routes.")
        except LaunchCancelled:
            try:
                self._update_marker(plan, "partial")
            except Exception:  # noqa: BLE001
                pass
            with self.lock:
                self.state["phase"] = "cancelled"
                self.state["downloadedBytes"] = _acquisition_present_bytes(
                    destination, plan["selection"]["files"],
                ) if destination.exists() else 0
            self._event("Model acquisition stopped. Existing verified files and partial cache data were preserved for resume.", "warning")
        except Exception as error:  # noqa: BLE001
            try:
                self._update_marker(plan, "failed")
            except Exception:  # noqa: BLE001
                pass
            if self.cancel_event.is_set():
                with self.lock:
                    self.state["phase"] = "cancelled"
                self._event("Model acquisition stopped. Existing files were preserved for resume.", "warning")
            else:
                with self.lock:
                    self.state["phase"] = "failed"
                self._event(str(error), "error")
        finally:
            if process is not None and process.poll() is None:
                self._terminate(process)
            with self.lock:
                if self.process is process:
                    self.process = None
                if self.thread is threading.current_thread():
                    self.thread = None
