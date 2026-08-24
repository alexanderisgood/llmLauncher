#!/usr/bin/env python3
"""Executes one private, validated client plan inside Terminal."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path


def fail(message: str) -> None:
    print(f"LLM Launcher: {message}", file=sys.stderr)
    raise SystemExit(2)


def main() -> None:
    if len(sys.argv) != 2:
        fail("expected one launch plan")
    plan_path = Path(sys.argv[1]).resolve()
    state_root = (Path.home() / "Library" / "Application Support" / "LLM Launcher" / "runs").resolve()
    try:
        plan_path.relative_to(state_root)
    except ValueError:
        fail("plan is outside the launcher state folder")
    try:
        info = plan_path.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            fail("plan permissions are not private")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        fail(f"cannot read plan: {error}")
    argv = plan.get("argv")
    allowed = plan.get("allowedExecutable")
    client_name = plan.get("clientName")
    cwd = plan.get("cwd")
    extra_env = plan.get("env", {})
    if not isinstance(argv, list) or not argv or not all(isinstance(v, str) and "\0" not in v for v in argv):
        fail("invalid arguments")
    if client_name not in {"pi", "opencode", "codex"}:
        fail("unexpected client name")
    if (
        argv[0] != allowed
        or not isinstance(allowed, str)
        or not os.path.isabs(allowed)
        or Path(allowed).name != client_name
        or not os.access(allowed, os.X_OK)
    ):
        fail("unexpected client executable")
    if not isinstance(cwd, str) or not Path(cwd).is_dir():
        fail("project folder no longer exists")
    if not isinstance(extra_env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in extra_env.items()):
        fail("invalid environment")
    env = os.environ.copy()
    env.update(extra_env)
    os.chdir(cwd)
    os.execve(argv[0], argv, env)


if __name__ == "__main__":
    main()
