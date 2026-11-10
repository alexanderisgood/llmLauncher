"""Positive read-only identity of installed servers whose argv was overwritten.

oMLX's serve command sets the reserved ``omlx-server`` title. The title only
selects candidates: receipts also require current-user kernel birth identity,
the exact installed interpreter and exact mapped native libraries from one
known oMLX environment. Dedicated native server binaries use exact executable
identity. This module never signals a process or manages a launchd job.

Public summaries contain metadata only. Private receipts are for the caller's
final sweep and must be revalidated against kernel birth before each signal.
"""
from __future__ import annotations

import ast
import ctypes
from dataclasses import dataclass
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any, Callable, Iterable


MAX_PATH = 4096
MAX_SOURCE = 64 * 1024
MAX_LSOF = 4 * 1024**2
NATIVE_NAMES = {"llamacpp": {"llama-server"}, "mference": {"MferenceServer"},
                "swiftlm": {"SwiftLM", "MLXServer"}}
MACHO_MAGIC = {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe",
               b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"}


class _BSDInfo(ctypes.Structure):
    """Public macOS PROC_PIDTBSDINFO layout, including microsecond start time."""
    _fields_ = [
        *[(name, ctypes.c_uint32) for name in ("flags", "status", "xstatus", "pid", "ppid", "uid", "gid",
                                             "ruid", "rgid", "svuid", "svgid", "reserved")],
        ("comm", ctypes.c_char * 16), ("name", ctypes.c_char * 32),
        *[(name, ctypes.c_uint32) for name in ("nfiles", "pgid", "jobc", "tdev", "tpgid")],
        ("nice", ctypes.c_int32), ("start_seconds", ctypes.c_uint64), ("start_microseconds", ctypes.c_uint64),
    ]


@dataclass(frozen=True)
class KernelIdentity:
    uid: int
    pid: int
    start_seconds: int
    start_microseconds: int
    executable: str


def native_process_identity(pid: int) -> KernelIdentity | None:
    """Read UID, exact birth and executable through libproc; fail closed."""
    if (sys.platform != "darwin" or type(pid) is not int or pid <= 1
            or ctypes.sizeof(_BSDInfo) != 136 or _BSDInfo.start_seconds.offset != 120
            or _BSDInfo.start_microseconds.offset != 128 or _BSDInfo.uid.offset != 20):
        return None
    try:
        library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        info = library.proc_pidinfo
        info.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
        info.restype = ctypes.c_int
        read_path = library.proc_pidpath
        read_path.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        read_path.restype = ctypes.c_int
        details = _BSDInfo()
        if info(pid, 3, 0, ctypes.byref(details), ctypes.sizeof(details)) != ctypes.sizeof(details):
            return None
        buffer = ctypes.create_string_buffer(MAX_PATH)
        length = read_path(pid, buffer, MAX_PATH)
        if not 0 < length < MAX_PATH or details.pid != pid or details.start_seconds <= 0 or details.start_microseconds >= 1_000_000:
            return None
        path = buffer.value.decode("utf-8")
        if not Path(path).is_absolute() or any(ord(char) < 32 for char in path):
            return None
        return KernelIdentity(int(details.uid), pid, int(details.start_seconds), int(details.start_microseconds), path)
    except (AttributeError, OSError, ValueError, TypeError, UnicodeError, ctypes.ArgumentError):
        return None


@dataclass(frozen=True)
class FileIdentity:
    path: str
    device: int
    inode: int
    size: int
    modified: int
    changed: int
    mode: int
    uid: int

    def unchanged(self) -> bool:
        return file_identity(Path(self.path)) == self


def file_identity(path: Path) -> FileIdentity | None:
    try:
        resolved = path.resolve(strict=True)
        details = resolved.stat()
        if (not stat.S_ISREG(details.st_mode) or details.st_uid not in {0, os.getuid()}
                or details.st_mode & 0o022 or any(ord(char) < 32 for char in str(resolved))):
            return None
        return FileIdentity(str(resolved), details.st_dev, details.st_ino, details.st_size,
                            details.st_mtime_ns, details.st_ctime_ns, details.st_mode, details.st_uid)
    except (OSError, ValueError):
        return None


def _source(path: Path) -> tuple[str, FileIdentity] | None:
    identity = file_identity(path)
    if identity is None or not 0 < identity.size <= MAX_SOURCE:
        return None
    try:
        data = Path(identity.path).read_text(encoding="utf-8")
        if not identity.unchanged():
            return None
        return data, identity
    except (OSError, UnicodeError):
        return None


def _mapped_records(output: bytes, expected_pid: int) -> list[dict[str, str]]:
    if len(output) > MAX_LSOF:
        raise RuntimeError("Mapped file inventory exceeded its verification bound")
    records = []
    current = None
    pid = None
    for chunk in output.split(b"\0"):
        chunk = chunk.lstrip(b"\n")
        if not chunk:
            continue
        key, value = chr(chunk[0]), chunk[1:].decode("utf-8")
        if key == "p":
            if current is not None:
                records.append(current)
            current = None
            pid = int(value)
            if pid != expected_pid:
                raise RuntimeError("Mapped file inventory changed process identity")
        elif key == "f":
            if current is not None:
                records.append(current)
            current = {"f": value} if pid == expected_pid else None
        elif current is not None and key in {"t", "D", "i", "n"}:
            if key in current:
                raise RuntimeError("Mapped file inventory is ambiguous")
            current[key] = value
    if current is not None:
        records.append(current)
    return records


def native_mapped_files(pid: int) -> set[tuple[str, int, int]] | None:
    """Return exact mapped text paths/device/inode, never ordinary open files."""
    try:
        result = subprocess.run(["/usr/sbin/lsof", "-nP", "-a", "-p", str(pid), "-d", "txt", "-F0pftnDi"],
                                capture_output=True, timeout=5, check=False)
        if result.returncode != 0:
            return None
        files = set()
        for record in _mapped_records(result.stdout, pid):
            if record.get("f") != "txt" or record.get("t") != "REG":
                continue
            name = record.get("n", "")
            if Path(name).is_absolute() and "D" in record and "i" in record:
                files.add((name, int(record["D"], 16), int(record["i"])))
        return files
    except (OSError, ValueError, UnicodeError, RuntimeError, subprocess.TimeoutExpired):
        return None


@dataclass(frozen=True)
class OmlxEnvironment:
    root: str
    version: str
    sources: tuple[FileIdentity, ...]
    interpreters: tuple[FileIdentity, ...]
    modules: tuple[FileIdentity, ...]

    def unchanged(self) -> bool:
        return all(item.unchanged() for item in (*self.sources, *self.interpreters, *self.modules))


def inspect_omlx_environment(binary: str) -> OmlxEnvironment | None:
    """Derive only the package environment of an exact installed oMLX entry point."""
    try:
        entry = _source(Path(binary).expanduser())
        if entry is None:
            return None
        text, cli = entry
        path = Path(cli.path)
        if path.name != "omlx" or path.parent.name != "bin":
            return None
        tree = ast.parse(text)
        if not any(isinstance(node, ast.ImportFrom) and node.module == "omlx.cli"
                   and any(alias.name == "main" for alias in node.names) for node in tree.body):
            return None
        root = path.parent.parent
        versions = sorted((root / "lib").glob("python[0-9]*"))
        if not 1 <= len(versions) <= 4:
            return None
        for version_dir in versions:
            site = version_dir / "site-packages"
            # The interpreter may be shared, but the identifying native
            # package files must belong to this one installed environment.
            # Do not reinterpret symlinks to another/global MLX package as
            # proof of an unrelated environment's server.
            site.resolve(strict=True).relative_to(root.resolve(strict=True))
            version_source = _source(site / "omlx/_version.py")
            if version_source is None:
                continue
            package_version = None
            for node in ast.parse(version_source[0]).body:
                if (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets)
                        and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
                    package_version = node.value.value
            if not package_version or not re.fullmatch(r"[0-9][A-Za-z0-9.+_-]{0,63}", package_version):
                continue
            module_paths = []
            for folder, stem in (("setproctitle", "_setproctitle"), ("mlx", "core")):
                options = [item for item in (site / folder).glob(stem + "*.so")
                           if re.fullmatch(re.escape(stem) + r"(?:\.cpython-[0-9]+-darwin|\.abi3)\.so", item.name)]
                if len(options) != 1:
                    break
                module_paths.extend(options)
            if len(module_paths) != 2:
                continue
            module_paths.append(site / "mlx/lib/libmlx.dylib")
            modules = tuple(file_identity(item) for item in module_paths)
            if any(item is None for item in modules):
                continue
            Path(version_source[1].path).relative_to(site.resolve(strict=True))
            for module in modules:
                Path(module.path).relative_to(site.resolve(strict=True))
            candidates = []
            for name in ("python", "python3", version_dir.name):
                candidate = file_identity(root / "bin" / name)
                if candidate:
                    candidates.append(candidate)
                    # Framework Python can re-exec its app entry point; only
                    # that exact installed interpreter's sibling is allowed.
                    framework = file_identity(Path(candidate.path).parent.parent / "Resources/Python.app/Contents/MacOS/Python")
                    if framework:
                        candidates.append(framework)
            if not candidates:
                continue
            return OmlxEnvironment(str(root), package_version, (cli, version_source[1]),
                                   tuple(dict.fromkeys(candidates)), modules)
        return None
    except (OSError, ValueError, SyntaxError):
        return None


@dataclass(frozen=True)
class VerifiedServer:
    engine: str
    process: Any
    kernel: KernelIdentity
    executable: FileIdentity
    environment: OmlxEnvironment | None = None

    def revalidate(self, reader: Callable[[int], KernelIdentity | None] = native_process_identity) -> bool:
        """Fast exact native UID/birth/image check immediately before a signal."""
        return reader(self.process.pid) == self.kernel and self.executable.unchanged()


def _binaries(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)) and len(value) <= 64 and all(isinstance(item, str) for item in value):
        return value
    return ()


def _native_servers(binaries: dict) -> dict[str, tuple[str, FileIdentity]]:
    found = {}
    for engine, names in NATIVE_NAMES.items():
        for binary in _binaries(binaries.get(engine)):
            identity = file_identity(Path(binary).expanduser())
            if not identity or Path(identity.path).name not in names or not identity.mode & 0o111:
                continue
            try:
                with Path(identity.path).open("rb") as handle:
                    magic = handle.read(4)
                if magic in MACHO_MAGIC and identity.unchanged():
                    found[identity.path] = (engine, identity)
            except OSError:
                continue
    return found


def _same_ps(original: Any, current: Any | None) -> bool:
    return bool(current and original.uid == current.uid == os.getuid()
                and original.pid == current.pid and original.started == current.started)


def identify_retitled_servers(*, processes: dict[int, Any], binaries: dict,
                             process_snapshot: Callable[[], dict[int, Any]],
                             native_reader: Callable[[int], KernelIdentity | None] = native_process_identity,
                             mapped_reader: Callable[[int], set[tuple[str, int, int]] | None] = native_mapped_files) -> dict:
    """Issue receipts from independent kernel/install/map proof; never title alone."""
    result = {"_processReceipts": {}, "_nativeReceipts": {}, "servers": [], "errors": []}
    environments = [environment for binary in _binaries(binaries.get("omlx"))
                    if (environment := inspect_omlx_environment(binary)) is not None]
    native_servers = _native_servers(binaries)
    native_candidates = {}
    for engine, names in NATIVE_NAMES.items():
        for binary in _binaries(binaries.get(engine)):
            try:
                path = Path(binary).expanduser().resolve()
                if path.name in names:
                    native_candidates[str(path)] = engine
            except (OSError, ValueError):
                continue
    for pid, process in processes.items():
        if process.uid != os.getuid() or pid <= 1 or pid == os.getpid() or not process.started:
            continue
        titled_omlx = process.command.strip() == "omlx-server"
        kernel = native_reader(pid)
        if kernel is None or kernel.uid != os.getuid() or kernel.pid != pid:
            if titled_omlx:
                result["errors"].append(f"An oMLX-titled process (PID {pid}) has no verifiable native UID/birth identity.")
            continue
        receipt = None
        if titled_omlx:
            mapped = mapped_reader(pid)
            for environment in environments:
                executable = next((item for item in environment.interpreters if item.path == kernel.executable), None)
                expected = {(item.path, item.device, item.inode) for item in environment.modules}
                if executable and mapped is not None and expected <= mapped and environment.unchanged():
                    receipt = VerifiedServer("omlx", process, kernel, executable, environment)
                    break
            if receipt is None:
                result["errors"].append(f"An oMLX-titled process (PID {pid}) does not match one exact installed interpreter/package environment.")
                continue
        elif kernel.executable in native_servers:
            engine, executable = native_servers[kernel.executable]
            receipt = VerifiedServer(engine, process, kernel, executable)
        elif kernel.executable in native_candidates:
            result["errors"].append(f"A {native_candidates[kernel.executable]} process (PID {pid}) has an unverifiable installed native server executable.")
            continue
        if receipt is None:
            continue
        if (not _same_ps(process, process_snapshot().get(pid)) or native_reader(pid) != kernel
                or not receipt.executable.unchanged() or receipt.environment and not receipt.environment.unchanged()):
            result["errors"].append(f"A positively identified {receipt.engine} process (PID {pid}) changed while its identity was checked.")
            continue
        result["_processReceipts"][pid] = process
        result["_nativeReceipts"][pid] = receipt
        result["servers"].append({"engine": receipt.engine, "pid": pid,
            "source": "installed-oMLX-mapped-environment" if receipt.environment else "installed-dedicated-native-server",
            "kernelStartSeconds": kernel.start_seconds, "kernelStartMicroseconds": kernel.start_microseconds,
            "installedVersion": receipt.environment.version if receipt.environment else None})
    return result
