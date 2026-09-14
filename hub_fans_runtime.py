"""Small runtime entry point for the installed MTPLX thermal API."""

from __future__ import annotations

import json
import sys
from typing import Any

import mtplx.thermal as thermal


def _known_mode(summary: Any) -> str | None:
    if not isinstance(summary, dict) or summary.get("ok") is not True:
        return None
    if thermal._summary_indicates_auto(summary):
        return "default"
    if thermal._summary_indicates_max(summary):
        return "max"
    return None


def _run(requested_mode: str | None) -> dict[str, Any]:
    if requested_mode not in (None, "default", "max"):
        raise RuntimeError("the installed thermal helper received an unsupported fan mode")
    if requested_mode == "max":
        changed = thermal.set_thermal_profile_verified("performance")
    elif requested_mode == "default":
        changed = thermal.restore_thermal_profile_verified()
    else:
        changed = None
    if changed is not None and (not isinstance(changed, dict) or changed.get("ok") is not True):
        raise RuntimeError("fan change could not be verified")

    # The installed verified helpers already return the post-change summary.
    # Reusing it avoids a second status probe that could race a daemon update.
    summary = changed.get("after") if changed is not None else thermal.fan_summary()
    current_mode = _known_mode(summary)
    if current_mode is None:
        raise RuntimeError("fan readings did not identify a verified mode")
    if requested_mode is not None and current_mode != requested_mode:
        raise RuntimeError(f"requested {requested_mode}, but fan readings show {current_mode}")
    return {"mode": current_mode, "smartAvailable": False}


def main(argv: list[str] | None = None) -> int:
    requested = argv if argv is not None else sys.argv[1:]
    mode = requested[0] if requested and requested[0] else None
    try:
        print(json.dumps(_run(mode), separators=(",", ":")))
    except Exception as error:
        print(f"fan helper: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
