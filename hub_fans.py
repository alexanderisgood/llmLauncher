"""Hub cooling controls.

MTPLX owns its native smart-fan policy. Other backends use the installed
MTPLX thermal helper in a short-lived runtime process so no model or MLX
initialisation is needed here.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.request
from typing import Any


RUNTIME = Path.home() / "Library/Application Support/MTPLX/runtime-venv"
RUNTIME_PYTHON = RUNTIME / "bin/python"
LOCAL_HELPER = Path(__file__).with_name("hub_fans_runtime.py")
FAN_MODES = frozenset({"default", "smart", "max"})
MAX_NATIVE_RESPONSE_BYTES = 128 * 1024


def _mode(value: Any) -> str | None:
    """Return a canonical fan mode, or None for an untrusted value."""
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    return value if value in FAN_MODES else None


def _read_native_response(response: Any) -> dict[str, Any]:
    """Read and validate one bounded JSON object from the native endpoint."""
    body = response.read(MAX_NATIVE_RESPONSE_BYTES + 1)
    if not isinstance(body, (bytes, bytearray, str)):
        raise ValueError("MTPLX returned a malformed fan-control response.")
    if len(body) > MAX_NATIVE_RESPONSE_BYTES:
        raise ValueError("MTPLX returned an unexpectedly large fan-control response.")
    try:
        result = json.loads(body)
    except (TypeError, ValueError, UnicodeDecodeError) as error:
        raise ValueError("MTPLX returned invalid JSON for fan control.") from error
    if not isinstance(result, dict):
        raise ValueError("MTPLX returned a malformed fan-control response.")
    return result


def _validate_native_result(result: dict[str, Any], requested_mode: str | None) -> dict[str, Any]:
    """Require both an explicit success flag and a known resulting mode."""
    flag = "verified" if requested_mode is not None else "ok"
    if type(result.get(flag)) is not bool or result[flag] is not True:
        raise ValueError("Fan mode could not be verified. Check that the MTPLX fan helper is installed.")
    current_mode = _mode(result.get("current_mode"))
    if current_mode is None:
        raise ValueError("Fan mode could not be verified: MTPLX reported an unknown mode.")
    if requested_mode is not None and current_mode != requested_mode:
        raise ValueError(
            f"Fan mode could not be verified: requested {requested_mode}, MTPLX reported {current_mode}."
        )
    return {"mode": current_mode, "smartAvailable": True}


def _run_local_helper(mode: str | None) -> dict[str, Any]:
    """Run the installed thermal API through the MTPLX runtime interpreter."""
    try:
        result = subprocess.run(
            [str(RUNTIME_PYTHON), str(LOCAL_HELPER), mode or ""],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        if result.returncode != 0:
            raise ValueError("the installed thermal helper could not verify the fan change")
        payload = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, TypeError, ValueError, UnicodeDecodeError) as error:
        raise ValueError(
            "Fan control unavailable or change not verified. Enable fan control in MTPLX, then retry."
        ) from error
    if not isinstance(payload, dict):
        raise ValueError("Fan control unavailable or change not verified. Enable fan control in MTPLX, then retry.")
    current_mode = _mode(payload.get("mode"))
    if current_mode not in {"default", "max"}:
        raise ValueError("Fan control could not be verified: the installed helper reported an unknown mode.")
    if mode is not None and current_mode != mode:
        raise ValueError("Fan control could not be verified: the helper reported a different mode.")
    if type(payload.get("smartAvailable")) is not bool or payload["smartAvailable"] is not False:
        raise ValueError("Fan control returned a malformed helper response.")
    return {"mode": current_mode, "smartAvailable": False}


def control_fans(plan: Any, mode: str | None = None) -> dict[str, Any]:
    """Read or change the selected backend's cooling mode."""
    if mode not in (None, "default", "smart", "max"):
        raise ValueError("Choose System, Smart, or Max fan mode.")
    if plan.backend == "mtplx":
        path = "fan_mode" if mode else "status"
        request = urllib.request.Request(
            f"http://127.0.0.1:{plan.port}/v1/mtplx/thermal/{path}",
            data=json.dumps({"mode": mode}).encode() if mode else None,
            headers={
                "Authorization": f"Bearer {plan.secrets.get('apiKey', 'local')}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                result = _read_native_response(response)
            return _validate_native_result(result, mode)
        except ValueError:
            raise
        except (OSError, urllib.error.URLError) as error:
            raise ValueError("Could not reach MTPLX fan control. Try again.") from error
    if mode == "smart":
        raise ValueError("Smart fan mode is available with MTPLX only.")
    return _run_local_helper(mode)
