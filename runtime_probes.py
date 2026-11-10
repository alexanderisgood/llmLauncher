"""Bounded informational CLI probes, shared across catalog and runtime screens."""
from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any, Callable

from controller_cache import SingleFlightCache


_PROBES = SingleFlightCache(ttl_seconds=15, maximum_entries=128)


def executable_identity(path: str) -> tuple[Any, ...] | None:
    """Track both the named link and its current regular executable target."""
    candidate = Path(path).expanduser()
    try:
        target = candidate.stat()
        named = candidate.lstat()
        if not stat.S_ISREG(target.st_mode):
            return None
        def fields(value: os.stat_result) -> tuple[int, ...]:
            return (value.st_dev, value.st_ino, value.st_mode, value.st_size,
                    value.st_mtime_ns, value.st_ctime_ns)
        return (str(candidate.absolute()), fields(named), fields(target))
    except (OSError, ValueError):
        return None


def probe_output(path: str, arguments: tuple[str, ...], environment: dict[str, str],
                 runner: Callable[..., Any] = subprocess.run) -> tuple[int, str]:
    """Cache successful probes only while executable identity and environment match."""
    identity = executable_identity(path)
    def run() -> tuple[int, str]:
        result = runner([path, *arguments], text=True, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, timeout=4, check=False, env=environment)
        output = str(result.stdout or "")[:200_000]
        if result.returncode != 0:
            # Failed probes must be retried after install/startup recovery; they
            # are not successful capability observations.
            raise _FailedProbe(int(result.returncode), output)
        return int(result.returncode), output
    try:
        if identity is None:
            return run()
        key = (identity, arguments, tuple(sorted(environment.items())), runner)
        return _PROBES.get(key, run)
    except _FailedProbe as error:
        return error.returncode, error.output


class _FailedProbe(Exception):
    def __init__(self, returncode: int, output: str) -> None:
        super().__init__("CLI probe did not succeed")
        self.returncode, self.output = returncode, output


def version_from_output(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    diagnostics = re.compile(r"^(?:warning|warn|npm warn|note|info)\b", re.IGNORECASE)
    candidates = [line for line in lines if not diagnostics.match(line)] or lines
    version = next((line for line in candidates if re.search(
        r"(?<!\d)v?\d+\.\d+(?:\.\d+)?(?:[-+][0-9A-Za-z.-]+)?", line,
    )), candidates[0] if candidates else "Installed")
    return version[:100]


def clear_probe_cache() -> None:
    _PROBES.clear()
