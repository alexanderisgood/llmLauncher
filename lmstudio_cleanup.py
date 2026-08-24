#!/usr/bin/env python3
"""Detached exact-ID cleanup for a cancelled LM Studio model load."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path


def fail(message: str) -> None:
    print(f"LLM Launcher cleanup: {message}", file=sys.stderr)
    raise SystemExit(2)


def load_config(path_text: str) -> tuple[Path, str, str, list[int]]:
    path = Path(path_text).resolve()
    root = (Path.home() / "Library" / "Application Support" / "LLM Launcher" / "cleanup").resolve()
    try:
        path.relative_to(root)
        info = path.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            fail("cleanup plan permissions are not private")
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        fail(f"invalid cleanup plan: {error}")
    identifier = value.get("identifier")
    lms = value.get("lms")
    deadlines = value.get("deadlines")
    if not isinstance(identifier, str) or not identifier.startswith("llm-launcher-") or len(identifier) > 160:
        fail("invalid model identifier")
    if not isinstance(lms, str) or not os.path.isabs(lms) or Path(lms).name != "lms" or not os.access(lms, os.X_OK):
        fail("invalid LM Studio executable")
    if (
        not isinstance(deadlines, list)
        or not deadlines
        or not all(isinstance(item, int) and not isinstance(item, bool) and 0 < item <= 1_200 for item in deadlines)
        or deadlines != sorted(set(deadlines))
    ):
        fail("invalid cleanup schedule")
    return path, identifier, lms, deadlines


def main() -> None:
    if len(sys.argv) != 2:
        fail("expected one cleanup plan")
    path, identifier, lms, deadlines = load_config(sys.argv[1])
    started = time.monotonic()
    try:
        for deadline in deadlines:
            remaining = deadline - (time.monotonic() - started)
            if remaining > 0:
                time.sleep(remaining)
            try:
                subprocess.run(
                    [lms, "unload", identifier], timeout=10, check=False,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
    finally:
        try:
            path.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
