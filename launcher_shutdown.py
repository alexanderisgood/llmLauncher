"""Explicit Quit shutdown of local engine services and launcher sessions.

Normal Stop retains its narrower ownership semantics. This module is invoked
only by the authenticated Quit action, which also stops independently launched
servers of the installed engines. It never matches a process by model name or
by a loose substring such as 'python', 'mlx', or 'codex'.
"""
from __future__ import annotations

import os
import json
import hashlib
import re
import signal
import stat
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from service_shutdown import stop_engine_services
from retitled_servers import identify_retitled_servers

ENGINE_KEYS = ("omlx", "mtplx", "mirai", "swiftlm", "mference", "slotstream", "splash", "rec", "rapidmlx", "whallm", "llamacpp")
SERVER_ACTIONS = frozenset({"serve", "server", "api-server"})
QUIT_MARKER = ".quit-marker"


@dataclass(frozen=True)
class LocalProcess:
    uid: int
    pid: int
    parent: int
    started: str
    command: str

    def same_identity(self, other: LocalProcess | None) -> bool:
        # Parentage changes when the server exits; it is not process identity.
        return bool(other and (self.uid, self.pid, self.started, self.command)
                    == (other.uid, other.pid, other.started, other.command))

    def same_process(self, other: LocalProcess | None) -> bool:
        """Birth identity stays visible even when a process changes its title."""
        return bool(other and (self.uid, self.pid, self.started)
                    == (other.uid, other.pid, other.started))


def process_snapshot() -> dict[int, LocalProcess]:
    result = subprocess.run(
        ["/bin/ps", "-ww", "-axo", "uid=,pid=,ppid=,lstart=,command="],
        capture_output=True, text=True, timeout=5, check=True,
    )
    if len(result.stdout) > 8 * 1024**2:
        raise RuntimeError("The local process inventory is too large to verify safely.")
    processes = {}
    for line in result.stdout.splitlines():
        fields = line.strip().split(None, 8)
        if len(fields) != 9:
            continue
        try:
            process = LocalProcess(int(fields[0]), int(fields[1]), int(fields[2]), " ".join(fields[3:8]), fields[8])
        except ValueError:
            continue
        if process.uid == os.getuid() and process.pid > 1:
            processes[process.pid] = process
    return processes


def _command_tail(command: str, executable: str) -> str | None:
    """Match native commands or exact scripts behind Python, Node or Bun."""
    candidates = {executable, str(Path(executable).expanduser().resolve())}
    for candidate in candidates:
        # ps does not shell-quote paths with spaces. Comparing the known path
        # and its following boundary preserves that identity without shlex.
        for prefix in (candidate, f'"{candidate}"', f"'{candidate}'"):
            if command == prefix:
                return ""
            if command.startswith(prefix + " "):
                return command[len(prefix):].strip()
    interpreter, _, rest = command.partition(" ")
    if re.fullmatch(r"(?:python(?:\d+(?:\.\d+)*)?|pypy\d*|node|bun)", Path(interpreter).name):
        if Path(interpreter).name not in {"node", "bun"}:
            # Only known no-argument flags are skipped. In particular -c/-m,
            # their payloads, and arbitrary interpreter options never match a
            # trusted script mentioned later in an unrelated command.
            while rest:
                option, separator, remainder = rest.partition(" ")
                if not separator or not re.fullmatch(r"-[ISBuEsOq]+", option):
                    break
                rest = remainder.lstrip()
        for candidate in candidates:
            for prefix in (candidate, f'"{candidate}"', f"'{candidate}'"):
                if rest == prefix or rest.startswith(prefix + " "):
                    return rest[len(prefix):].strip()
    return None


def _installed_server_scripts(key: str, binary: str) -> set[str]:
    """Derive only documented companion scripts of exact installed engines."""
    paths = {Path(binary).expanduser(), Path(binary).expanduser().resolve()}
    servers = set()
    for path in paths:
        if key == "splash" and path.name == "splash" and path.parent.name == "engine":
            servers.add(str(path.parent.parent / "server/server.py"))
        elif key == "whallm" and path.name == "dsv4-app" and path.parent.name == "MacOS" and path.parent.parent.name == "Contents":
            servers.add(str(path.parent.parent / "Resources/runtime/deepseek_v4_ssd/server.py"))
    return servers


def _private_regular(details: os.stat_result, *, maximum: int = 4096) -> bool:
    return bool(stat.S_ISREG(details.st_mode) and details.st_uid == os.getuid()
                and not details.st_mode & 0o077 and details.st_size <= maximum)


def mark_quit(runs_dir: Path) -> None:
    """Invalidate earlier Terminal plans before cancellation or enumeration."""
    directory = runs_dir.lstat()
    if (not stat.S_ISDIR(directory.st_mode) or runs_dir.is_symlink()
            or directory.st_uid != os.getuid() or directory.st_mode & 0o022):
        raise OSError("The launcher session folder cannot hold a private Quit marker.")
    descriptor = os.open(
        runs_dir / QUIT_MARKER,
        os.O_WRONLY | os.O_CREAT | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0), 0o600,
    )
    try:
        if not _private_regular(os.fstat(descriptor)):
            raise OSError("The launcher Quit marker is not a private regular file.")
        # Truncate only after validating the opened inode, never a symlink.
        os.ftruncate(descriptor, 0)
        os.write(descriptor, b"Pending Terminal plans were cancelled by Quit.\n")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def terminal_plan_cancelled(runs_dir: Path, plan_info: os.stat_result) -> bool:
    """An old Quit remains effective for delayed handoffs after a restart."""
    try:
        descriptor = os.open(runs_dir / QUIT_MARKER, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return False
    try:
        marker = os.fstat(descriptor)
        if not _private_regular(marker):
            raise OSError("The launcher Quit marker could not be verified.")
        return marker.st_mtime_ns >= plan_info.st_mtime_ns
    finally:
        os.close(descriptor)


def _extension_argument(command: str, path: str) -> bool:
    literal = re.escape(path)
    return bool(re.search(
        r"(?:^|\s)(?:--extension(?:=|\s+)|-e\s+)(?:\"" + literal
        + r"\"|'" + literal + "'|" + literal + r")(?=$|\s)", command,
    ))


def process_label(process: LocalProcess, binaries: dict[str, str | None], app_dir: Path) -> str | None:
    for key in ENGINE_KEYS:
        installed = binaries.get(key)
        if not installed:
            continue
        for binary in ([installed] if isinstance(installed, str) else installed):
            for script in _installed_server_scripts(key, binary):
                if _command_tail(process.command, script) is not None:
                    return key
            tail = _command_tail(process.command, binary)
            if tail is None:
                continue
            action = tail.split(None, 1)[0] if tail else ""
            if key == "rapidmlx":
                if action == "serve":
                    return key
                continue
            dedicated_server = bool(
                key in {"swiftlm", "mference"}
                and re.search(r"(?:^|\s)--model(?:=|\s+)\S", tail)
                and re.search(r"(?:^|\s)--port(?:=|\s+)\d+(?=$|\s)", tail)
            )
            if action in SERVER_ACTIONS or key == "llamacpp" or dedicated_server or (key == "splash" and action == "serve-native"):
                return key
    for relative in (
        "runtime_patches/kolibri/serve.py", "runtime_patches/kolibri/worker.py",
        "kolibri_runtime.py", "splash_runtime.py", "splash_reasoning.py", "splash_sources.py",
        "slotstream_runtime.py", "whallm_runtime.py", "rec_runtime.py",
        "session_proxy.py", "codex_proxy.py", "freetoken_bridge.py",
        "omlx_hub_runtime.py", "mtplx_hub_runtime.py", "hub_fans_runtime.py",
        "lmstudio_cleanup.py", "client_runner.py", "launcher.py",
    ):
        if _command_tail(process.command, str(app_dir / relative)) is not None:
            return "Kolibri" if relative.startswith("runtime_patches/kolibri/") else "LLM Launcher helper"
    for client, marker in (
        ("pi", str(app_dir / "pi-provider.js")),
        ("omp", str(app_dir / "omp-provider.mjs")),
        ("opencode", "--model launcher-"),
        ("codex", "model_providers.launcher_"),
    ):
        binary = binaries.get(client)
        marked = (_extension_argument(process.command, marker) if client in {"pi", "omp"}
                  else marker in process.command)
        if binary and marked and _command_tail(process.command, binary) is not None:
            return client
    return None


def terminal_agent_receipts(runs_dir: Path | None, processes: dict[int, LocalProcess]) -> dict[int, LocalProcess]:
    if runs_dir is None:
        return {}
    if runs_dir.is_symlink():
        return {}
    selected = {}
    paths = (*runs_dir.glob("*/agent-process.json"),
             *runs_dir.glob("*/attachments/*/agent-process.json"),
             *runs_dir.glob("*/agent-processes/*.json"),
             *runs_dir.glob("*/attachments/*/agent-processes/*.json"))
    root = runs_dir.resolve()
    for path in paths:
        try:
            # Every component belongs to a run or its attachment. Never follow
            # a replaced run, attachments folder, receipt folder, or receipt.
            if any(parent.is_symlink() for parent in (path, *path.parents)
                   if parent != runs_dir and root in (parent.resolve(), *parent.resolve().parents)):
                continue
            relative = path.resolve().relative_to(root).parts
            legacy = len(relative) == 2 or len(relative) == 4 and relative[1] == "attachments"
            multiple = (len(relative) == 3 and relative[1] == "agent-processes"
                        or len(relative) == 5 and relative[1] == "attachments" and relative[3] == "agent-processes")
            if not (legacy or multiple):
                continue
            descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(descriptor, "r", encoding="utf-8") as target:
                if not _private_regular(os.fstat(target.fileno())):
                    continue
                data = json.loads(target.read(4097))
            if not isinstance(data, dict):
                continue
            pid = data.get("pid")
            if isinstance(pid, bool) or not isinstance(pid, int) or pid == os.getpid():
                continue
            process = processes.get(pid)
            if process and process.uid == os.getuid() and process.started == data.get("started") and data.get("client") in {"pi", "omp", "opencode", "codex"}:
                selected[pid] = process
        except (OSError, ValueError, AttributeError):
            continue
    return selected


def register_terminal_agent(run_dir: Path, client: str) -> None:
    """Record before exec so Quit can find an agent even if its title changes."""
    process = process_snapshot().get(os.getpid())
    if not process:
        return
    # A saved Terminal command can be opened more than once. Keep every
    # agent's birth receipt so changed titles do not hide later instances.
    directory = run_dir / "agent-processes"
    directory.mkdir(mode=0o700, exist_ok=True)
    details = directory.lstat()
    if (not stat.S_ISDIR(details.st_mode) or details.st_uid != os.getuid()
            or details.st_mode & 0o077):
        raise OSError("The Terminal agent receipt folder is not private.")
    birth = hashlib.sha256(process.started.encode("utf-8")).hexdigest()[:16]
    path = directory / f"{process.pid}-{birth}.json"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as target:
        json.dump({"pid": process.pid, "started": process.started, "client": client}, target)


def select_processes(processes: dict[int, LocalProcess], binaries: dict[str, str | None], app_dir: Path,
                     runs_dir: Path | None = None) -> dict[int, LocalProcess]:
    selected = {
        pid: process for pid, process in processes.items()
        if pid != os.getpid() and process.uid == os.getuid()
        and process_label(process, binaries, app_dir)
    }
    selected.update(terminal_agent_receipts(runs_dir, processes))
    # Include subprocess workers and tools of the exact selected services.
    # Individual PIDs are used so an unrelated Terminal process group is safe.
    while True:
        children = {
            pid: process for pid, process in processes.items()
            if pid not in selected and pid != os.getpid()
            and process.uid == os.getuid() and process.parent in selected
        }
        if not children:
            return selected
        selected.update(children)


def stop_local_servers(binaries: dict[str, str | None], app_dir: Path, *, grace: float = 5.0,
                       runs_dir: Path | None = None,
                       verified_processes: dict[int, LocalProcess] | None = None,
                       native_receipts: dict | None = None) -> dict:
    """TERM exact identified services, then KILL only unchanged survivors."""
    initial = process_snapshot()
    selected = select_processes(initial, binaries, app_dir, runs_dir)
    # launchd can erase a server's command title and orphan its workers when
    # unloading a KeepAlive job. Its independently verified birth receipts
    # preserve those exact processes without trusting a generic title.
    verified = {
        pid: process for pid, process in (verified_processes or {}).items()
        if isinstance(process, LocalProcess) and process.uid == os.getuid()
        and pid == process.pid and pid != os.getpid()
        and process.same_process(initial.get(pid))
    }
    selected.update(verified)
    trusted_agents = {(process.uid, process.pid, process.started)
                      for process in terminal_agent_receipts(runs_dir, initial).values()}
    trusted_agents.update((process.uid, process.pid, process.started)
                         for process in verified.values())
    errors = []

    def send(process: LocalProcess, sig: int) -> bool:
        current = process_snapshot().get(process.pid)
        if not process.same_process(current):
            return False
        receipt = (native_receipts or {}).get(process.pid)
        if receipt is not None:
            if (not receipt.revalidate() or current is None
                    or receipt.environment is not None and current.command.strip() != "omlx-server"):
                errors.append(f"A verified local server (PID {process.pid}) changed before shutdown and was left running.")
                return False
        receipt_bound = (process.uid, process.pid, process.started) in trusted_agents
        if not (process.same_identity(current) or (receipt_bound and process.same_process(current))):
            return False
        try:
            os.kill(process.pid, sig)
            return True
        except ProcessLookupError:
            return False
        except OSError as error:
            errors.append(f"Could not stop {process_label(process, binaries, app_dir) or 'engine worker'} (PID {process.pid}): {error.strerror}.")
            return False

    for process in selected.values():
        send(process, signal.SIGTERM)
    deadline = time.monotonic() + grace
    remaining = selected
    while remaining and time.monotonic() < deadline:
        current = process_snapshot()
        trusted_agents.update((process.uid, process.pid, process.started)
                              for process in terminal_agent_receipts(runs_dir, current).values())
        # Catch helpers that appeared after the initial inventory while their
        # exact engine/agent parent is still identifiable.
        for pid, process in select_processes(current, binaries, app_dir, runs_dir).items():
            if pid not in selected or (
                selected[pid].same_process(process) and not selected[pid].same_identity(process)
            ):
                # An isolated wrapper can exec its exact installed engine
                # during inventory. Revalidate that new allowlisted command.
                selected[pid] = remaining[pid] = process
                send(process, signal.SIGTERM)
        remaining = {pid: process for pid, process in remaining.items() if process.same_process(current.get(pid))}
        if remaining:
            time.sleep(min(0.1, max(0, deadline - time.monotonic())))
    for process in remaining.values():
        send(process, signal.SIGKILL)
    if remaining:
        time.sleep(0.1)
    current = process_snapshot()
    survivors = [process for process in selected.values() if process.same_process(current.get(process.pid))]
    for process in survivors:
        if process.same_identity(current.get(process.pid)) or (process.uid, process.pid, process.started) in trusted_agents:
            errors.append(f"A local engine or agent (PID {process.pid}) is still stopping.")
        else:
            errors.append(f"A local engine or agent (PID {process.pid}) changed its title or command and could not be safely confirmed stopped.")
    return {"processesStopped": len(selected) - len(survivors), "errors": errors}


def lmstudio_service_running() -> bool:
    """Inspect existing processes without letting the SDK launch its host app."""
    applications = (
        "/Applications/LM Studio.app/Contents/MacOS/LM Studio",
        str(Path.home() / "Applications/LM Studio.app/Contents/MacOS/LM Studio"),
    )
    try:
        for process in process_snapshot().values():
            if any(_command_tail(process.command, path) is not None for path in applications):
                return True
            executable = process.command.partition(" ")[0]
            if Path(executable).name == "llmster":
                return True
    except (OSError, RuntimeError, subprocess.SubprocessError):
        pass
    return False


def stop_lmstudio(binary: str | None) -> list[str]:
    if not binary or not lmstudio_service_running():
        return []
    errors = []
    for arguments in (["unload", "--all"], ["server", "stop"]):
        try:
            result = subprocess.run(
                [binary, *arguments], stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=12, check=False,
            )
            if result.returncode != 0:
                action = "model unload" if arguments[0] == "unload" else "server stop"
                errors.append(f"LM Studio {action} was not confirmed (exit status {result.returncode}).")
        except (OSError, subprocess.TimeoutExpired):
            errors.append("LM Studio did not respond to its shutdown command.")
    return errors


def retitled_servers_for_quit(binaries: dict) -> dict:
    """Prove manual servers independently of launchd and overwritten argv."""
    return identify_retitled_servers(processes=process_snapshot(), binaries=binaries,
                                     process_snapshot=process_snapshot)


class ShutdownCoordinator:
    """One shared shutdown for HTTP Quit, signals, and controller exit."""
    def __init__(self, callbacks: Iterable[Callable[[], None]], *, binaries: dict,
                 app_dir: Path, shutdown_server: Callable[[], None], runs_dir: Path | None = None):
        self.callbacks = tuple(callbacks)
        self.binaries, self.app_dir = binaries, app_dir
        self.runs_dir = runs_dir
        self.shutdown_server = shutdown_server
        self.started = threading.Event()
        self.complete = threading.Event()
        self.lock = threading.Lock()
        self.state = {"quitting": False, "complete": False, "errors": [], "processesStopped": 0,
                      "servicesStopped": 0}

    def snapshot(self) -> dict:
        with self.lock:
            return {**self.state, "errors": list(self.state["errors"])}

    def request(self, *, all_local: bool = False) -> dict:
        with self.lock:
            if self.started.is_set():
                return {**self.state, "errors": list(self.state["errors"])}
            if all_local and self.runs_dir is not None:
                try:
                    mark_quit(self.runs_dir)
                except OSError:
                    self.state["errors"].append("Delayed Terminal launches could not be cancelled safely.")
            self.started.set()
            self.state["quitting"] = True
        thread = threading.Thread(target=self._run, args=(all_local,), name="launcher-quit", daemon=False)
        thread.start()
        return self.snapshot()

    def _run(self, all_local: bool) -> None:
        with self.lock:
            errors = list(self.state["errors"])
        stopped = 0
        services_stopped = 0
        try:
            # Cancellations establish their publication barriers before process
            # enumeration. A racing launch cannot publish a new live server.
            for callback in self.callbacks:
                try:
                    callback()
                except Exception as error:
                    errors.append(f"A launcher task could not finish shutdown: {type(error).__name__}.")
            if all_local:
                # A previously admitted attachment can publish a newer plan
                # while cleanup waits for its operation lock. Refresh after
                # all cancellation/publication barriers have committed.
                if self.runs_dir is not None:
                    try:
                        mark_quit(self.runs_dir)
                    except OSError:
                        message = "Delayed Terminal launches could not be cancelled safely."
                        if message not in errors:
                            errors.append(message)
                verified_processes = {}
                try:
                    def service_label(process: LocalProcess) -> str | None:
                        label = process_label(process, self.binaries, self.app_dir)
                        return label if label in {*ENGINE_KEYS, "Kolibri"} else None

                    service_result = stop_engine_services(
                        process_label=service_label, process_snapshot=process_snapshot,
                    )
                    services_stopped = service_result["servicesStopped"]
                    stopped += service_result["processesStopped"]
                    errors.extend(service_result["errors"])
                    verified_processes = service_result["_processReceipts"]
                except Exception as error:
                    errors.append(f"Could not inspect local engine services: {type(error).__name__}.")
                errors.extend(stop_lmstudio(self.binaries.get("lms")))
                native_receipts = {}
                try:
                    retitled = retitled_servers_for_quit(self.binaries)
                    verified_processes.update(retitled["_processReceipts"])
                    native_receipts = retitled["_nativeReceipts"]
                    errors.extend(retitled["errors"])
                except Exception as error:
                    errors.append(f"Could not verify retitled local servers: {type(error).__name__}.")
                try:
                    result = stop_local_servers(self.binaries, self.app_dir, runs_dir=self.runs_dir,
                                                verified_processes=verified_processes,
                                                native_receipts=native_receipts)
                    stopped += result["processesStopped"]
                    errors.extend(result["errors"])
                except Exception as error:
                    errors.append(f"Could not inspect remaining local servers: {type(error).__name__}.")
        finally:
            with self.lock:
                self.state.update(complete=True, processesStopped=stopped,
                                  servicesStopped=services_stopped, errors=errors)
            self.complete.set()
            # Let the browser observe completion and any errors before the
            # listener closes. This is shutdown-only, never a request delay.
            time.sleep(1)
            self.shutdown_server()
