"""Quit-only unloading of proven current-user local inference LaunchAgents.

A title such as ``omlx-server`` does not prove which program owns a process.
Instead, bind a registered launchd label/PID to a safely opened LaunchAgent
whose exact executable and server action match an installed engine. Unload
that one job before the final process sweep so KeepAlive cannot respawn it.

This module never kills processes and never matches service-label prefixes.
Normal Stop and signal shutdown must not invoke it. Callers inject the exact
installed-engine predicate and process inventory; no launcher imports are
needed. Private process receipts in the result belong to the caller's final
PID/birth-identity sweep and must not be serialized into the UI response.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import plistlib
import re
import shlex
import stat
import subprocess
import time
from typing import Any, Callable


MAX_PLIST_BYTES = 64 * 1024
MAX_JOB_BYTES = 1024 * 1024
MAX_AGENTS = 1024
LABEL_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}\Z")
ENGINE_LABELS = frozenset({"omlx", "mtplx", "mirai", "swiftlm", "mference",
                           "slotstream", "splash", "rec", "rapidmlx", "whallm", "llamacpp"})


@dataclass(frozen=True)
class ServiceCommand:
    """Only the injected command predicate consumes this configured argv."""
    uid: int
    pid: int
    parent: int
    started: str
    command: str


@dataclass(frozen=True)
class PlistReceipt:
    label: str
    argv: tuple[str, ...]
    file_identity: tuple[int, ...]
    digest: str


@dataclass(frozen=True)
class VerifiedService:
    label: str
    engine: str
    path: Path
    plist: PlistReceipt
    process: Any | None


def _same_process(original: Any, current: Any | None, uid: int) -> bool:
    return bool(current is not None and original.uid == current.uid == uid
                and original.pid == current.pid and original.started == current.started)


def _descendants(original: Any, processes: dict[int, Any], uid: int) -> dict[int, Any]:
    """Snapshot the same-user tree while its proven root birth still exists."""
    if not _same_process(original, processes.get(original.pid), uid):
        return {}
    selected = {original.pid: original}
    while True:
        children = {pid: process for pid, process in processes.items()
                    if pid not in selected and pid > 1 and pid != os.getpid()
                    and process.uid == uid and process.parent in selected}
        if not children:
            return selected
        selected.update(children)


def _identity(details: os.stat_result) -> tuple[int, ...]:
    return (details.st_dev, details.st_ino, details.st_uid, details.st_mode,
            details.st_size, details.st_mtime_ns, details.st_ctime_ns, details.st_nlink)


def _has_symlink_component(path: Path) -> bool:
    for component in (path, *path.parents):
        if component.is_symlink():
            return True
    return False


def _read_plist(path: Path, uid: int) -> PlistReceipt | None:
    """Read only a bounded ordinary current-user file, never through symlinks."""
    if _has_symlink_component(path):
        return None
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_uid != uid
            or before.st_mode & 0o022 or before.st_nlink != 1
            or not 0 < before.st_size <= MAX_PLIST_BYTES):
        return None
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(descriptor)
        if _identity(opened) != _identity(before):
            return None
        data = os.read(descriptor, MAX_PLIST_BYTES + 1)
        if len(data) != before.st_size or _identity(os.fstat(descriptor)) != _identity(before):
            return None
    finally:
        os.close(descriptor)
    # A replacement inode or newly introduced parent symlink invalidates the
    # receipt even if the contents still look like the old service config.
    if _has_symlink_component(path) or _identity(path.lstat()) != _identity(before):
        return None
    try:
        config = plistlib.loads(data)
    except (ValueError, TypeError, OverflowError, plistlib.InvalidFileException):
        return None
    if not isinstance(config, dict):
        return None
    label = config.get("Label")
    args = config.get("ProgramArguments")
    if (not isinstance(label, str) or not LABEL_PATTERN.fullmatch(label)
            or not isinstance(args, list) or not 1 <= len(args) <= 128
            or any(not isinstance(arg, str) or not arg or len(arg) > 4096
                   or any(ord(char) < 32 or ord(char) == 127 for char in arg) for arg in args)):
        return None
    program = config.get("Program", args[0])
    if (not isinstance(program, str) or not program or len(program) > 4096
            or not Path(program).is_absolute()
            or any(ord(char) < 32 or ord(char) == 127 for char in program)):
        return None
    # Program, when present, owns the executable; argv[0] can be a custom
    # display name. Do not let an installed-looking argv[0] hide /bin/sh.
    argv = (program, *args[1:])
    if sum(len(arg) for arg in argv) > MAX_PLIST_BYTES // 2:
        return None
    return PlistReceipt(label, argv, _identity(before), hashlib.sha256(data).hexdigest())


def _jobs(runner: Callable[..., Any]) -> dict[str, int | None]:
    result = runner(["/bin/launchctl", "list"], capture_output=True, text=True, timeout=5, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Current-user launchd inventory failed (exit {result.returncode}).")
    if not isinstance(result.stdout, str) or len(result.stdout) > MAX_JOB_BYTES:
        raise RuntimeError("Current-user launchd inventory is too large to verify safely.")
    jobs = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if fields == ["PID", "Status", "Label"]:
            continue
        if len(fields) != 3 or not LABEL_PATTERN.fullmatch(fields[2]) or not re.fullmatch(r"-?\d+", fields[1]):
            continue
        pid = None if fields[0] == "-" else int(fields[0]) if fields[0].isdigit() else -1
        if pid is not None and pid <= 1:
            continue
        if fields[2] in jobs:
            raise RuntimeError("Current-user launchd inventory contains a duplicate label.")
        jobs[fields[2]] = pid
        if len(jobs) > MAX_AGENTS * 4:
            raise RuntimeError("Current-user launchd inventory has too many entries to verify safely.")
    return jobs


def _loaded_matches(service: VerifiedService, pid: int | None, uid: int,
                    runner: Callable[..., Any]) -> bool:
    """Confirm launchd's loaded executable/argv, not just an editable plist.

    launchctl print has no structured output mode. Accept only its bounded
    direct job fields and argument block; nested environment/resource fields
    are ignored. Ambiguous output fails closed rather than falling back to a
    title, label prefix or the on-disk configuration alone.
    """
    target = f"gui/{uid}/{service.label}"
    result = runner(["/bin/launchctl", "print", target], capture_output=True, text=True, timeout=5, check=False)
    if result.returncode != 0:
        return False
    output = result.stdout
    if not isinstance(output, str) or len(output) > MAX_JOB_BYTES:
        return False
    lines = output.splitlines()
    if not lines or lines[0] != target + " = {":
        return False
    indents = [line[:len(line) - len(line.lstrip())] for line in lines[1:] if line.strip()]
    indents = [indent for indent in indents if indent]
    if not indents:
        return False
    indent = min(indents, key=len)
    fields = {}
    args = None
    for index, line in enumerate(lines[1:], 1):
        leading = line[:len(line) - len(line.lstrip())]
        if leading != indent or " = " not in line:
            continue
        key, value = line[len(indent):].split(" = ", 1)
        if key not in {"path", "type", "program", "pid", "arguments"}:
            continue
        if key in fields:
            return False
        fields[key] = value
        if key == "arguments":
            if value != "{":
                return False
            args = []
            for argument in lines[index + 1:]:
                leading = argument[:len(argument) - len(argument.lstrip())]
                if leading == indent and argument[len(indent):] == "}":
                    break
                if not leading.startswith(indent) or len(leading) <= len(indent) or not argument.strip():
                    return False
                args.append(argument[len(leading):])
                if len(args) > 128:
                    return False
            else:
                return False
    loaded_pid = fields.get("pid")
    if loaded_pid is not None and not loaded_pid.isdigit():
        return False
    loaded_pid = int(loaded_pid) if loaded_pid is not None else None
    if (fields.get("path") != str(service.path) or fields.get("type") != "LaunchAgent"
            or fields.get("program") != service.plist.argv[0] or not args
            or loaded_pid != pid):
        return False
    return (fields["program"], *args[1:]) == service.plist.argv


def _engine(receipt: PlistReceipt, predicate: Callable[[Any], str | None], uid: int) -> str | None:
    label = predicate(ServiceCommand(uid, 0, 0, "", shlex.join(receipt.argv)))
    return label if label in ENGINE_LABELS else None


def _discover(directory: Path, jobs: dict[str, int | None], processes: dict[int, Any],
              predicate: Callable[[Any], str | None], uid: int, runner: Callable[..., Any],
              errors: list[str]) -> list[VerifiedService]:
    if not directory.exists():
        return []
    details = directory.lstat()
    if (_has_symlink_component(directory) or not stat.S_ISDIR(details.st_mode)
            or details.st_uid != uid or details.st_mode & 0o022):
        raise RuntimeError("The current-user LaunchAgents folder cannot be verified safely.")
    paths = sorted(directory.glob("*.plist"))
    if len(paths) > MAX_AGENTS:
        raise RuntimeError("The current-user LaunchAgents folder contains too many files to verify safely.")
    candidates = []
    labels = {}
    for path in paths:
        try:
            receipt = _read_plist(path, uid)
        except OSError:
            continue
        if receipt is None:
            continue
        labels[receipt.label] = labels.get(receipt.label, 0) + 1
        if receipt.label not in jobs:
            continue
        engine = _engine(receipt, predicate, uid)
        if engine is None:
            continue
        pid = jobs[receipt.label]
        process = processes.get(pid) if pid is not None else None
        # The service PID can have an arbitrary title. Its same-user birth
        # identity and exact launchd/config binding are what prove ownership.
        if pid is not None and (process is None or process.uid != uid or not process.started):
            errors.append(f"The {engine} service process identity could not be verified; it was left running.")
            continue
        service = VerifiedService(receipt.label, engine, path, receipt, process)
        if not _loaded_matches(service, pid, uid, runner):
            errors.append(f"The loaded {engine} service does not match its safe LaunchAgent configuration; it was left running.")
            continue
        candidates.append(service)
    return [item for item in candidates if labels[item.label] == 1]


def stop_engine_services(*, process_label: Callable[[Any], str | None],
                         process_snapshot: Callable[[], dict[int, Any]],
                         launch_agents: Path | None = None, timeout: float = 5,
                         runner: Callable[..., Any] | None = None) -> dict[str, Any]:
    """Unload exact proven jobs and verify both service and PID birth are gone.

    Unload failures, changed configs/registered PIDs and surviving processes
    are errors. Surviving verified process receipts can be handed to a final
    identity-bound sweep; this function itself never sends a process signal.
    """
    uid = os.getuid()
    runner = runner or subprocess.run
    directory = launch_agents if launch_agents is not None else Path.home() / "Library/LaunchAgents"
    result = {"servicesStopped": 0, "processesStopped": 0, "errors": [], "services": [],
              "_processReceipts": {}, "_survivingProcesses": {}}
    timeout = max(0, min(float(timeout), 30))
    try:
        processes = process_snapshot()
        services = _discover(directory, _jobs(runner), processes, process_label, uid, runner, result["errors"])
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        result["errors"].append(str(error))
        return result
    for service in services:
        state = {"label": service.label, "engine": service.engine, "pid": service.process.pid if service.process else None,
                 "unregistered": False, "processStopped": service.process is None}
        result["services"].append(state)
        service_receipts = {}
        try:
            current_plist = _read_plist(service.path, uid)
            if current_plist != service.plist or _engine(current_plist, process_label, uid) != service.engine:
                raise RuntimeError(f"The {service.engine} service configuration changed before Quit; it was left running.")
            jobs = _jobs(runner)
            current = process_snapshot()
            if service.label not in jobs:
                state["unregistered"] = True
                state["processStopped"] = service.process is None or not _same_process(service.process, current.get(service.process.pid), uid)
                if not state["processStopped"]:
                    # Config and process identity were proven before this
                    # disappearance, so the final sweep may finish this PID.
                    result["_processReceipts"][service.process.pid] = service.process
                    result["_survivingProcesses"][service.process.pid] = service.process
                    raise RuntimeError(f"The {service.engine} service is unregistered but its original process remains running.")
                if service.process is not None:
                    service_receipts = {pid: process for pid, process in _descendants(service.process, processes, uid).items()
                                        if _same_process(process, current.get(pid), uid)}
                    result["_processReceipts"].update(service_receipts)
            elif (jobs[service.label] != state["pid"] or service.process is not None
                    and not _same_process(service.process, current.get(service.process.pid), uid)):
                raise RuntimeError(f"The {service.engine} service process changed before Quit; it was left running.")
            else:
                if (not _loaded_matches(service, state["pid"], uid, runner)
                        or _read_plist(service.path, uid) != service.plist):
                    raise RuntimeError(f"The loaded {service.engine} service configuration changed before Quit; it was left running.")
                if service.process is not None:
                    # Preserve already-proven workers that daemonized or
                    # became orphans, and capture children created since the
                    # initial inventory, before launchd removes the parent.
                    service_receipts = {pid: process for pid, process in _descendants(service.process, processes, uid).items()
                                        if _same_process(process, current.get(pid), uid)}
                    service_receipts.update(_descendants(service.process, current, uid))
                    result["_processReceipts"].update(service_receipts)
                unloaded = runner(["/bin/launchctl", "bootout", f"gui/{uid}/{service.label}"],
                                  capture_output=True, text=True, timeout=5, check=False)
                if unloaded.returncode != 0:
                    result["errors"].append(f"Could not unload the {service.engine} service {service.label} (exit {unloaded.returncode}).")
                deadline = time.monotonic() + timeout
                while True:
                    current = process_snapshot()
                    for process in tuple(service_receipts.values()):
                        service_receipts.update(_descendants(process, current, uid))
                    result["_processReceipts"].update(service_receipts)
                    jobs = _jobs(runner)
                    state["unregistered"] = service.label not in jobs
                    state["processStopped"] = service.process is None or not _same_process(service.process, current.get(service.process.pid), uid)
                    if state["unregistered"] and state["processStopped"] or time.monotonic() >= deadline:
                        break
                    time.sleep(min(.1, max(0, deadline - time.monotonic())))
                if not state["unregistered"]:
                    result["errors"].append(f"The {service.engine} service {service.label} remains registered after Quit.")
                if not state["processStopped"]:
                    result["_survivingProcesses"][service.process.pid] = service.process
                    result["errors"].append(f"The {service.engine} service process (PID {service.process.pid}) remains running after Quit.")
            if state["unregistered"] and state["processStopped"]:
                result["servicesStopped"] += 1
            if service.process is not None and state["processStopped"]:
                result["processesStopped"] += 1
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
            result["errors"].append(str(error))
            if service.process is not None and service.process.pid in result["_processReceipts"]:
                try:
                    current = process_snapshot().get(service.process.pid)
                    if _same_process(service.process, current, uid):
                        result["_survivingProcesses"][service.process.pid] = service.process
                except (OSError, RuntimeError, subprocess.TimeoutExpired):
                    pass
        if service_receipts:
            try:
                current = process_snapshot()
                result["_survivingProcesses"].update({pid: process for pid, process in service_receipts.items()
                    if _same_process(process, current.get(pid), uid)})
                state["descendantPids"] = sorted(pid for pid in service_receipts if service.process is None or pid != service.process.pid)
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                result["errors"].append(f"Could not verify the {service.engine} worker processes after unload: {error}")
    return result
