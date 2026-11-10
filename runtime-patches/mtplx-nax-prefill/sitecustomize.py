"""Auto-install hook for the BQ=128 prefill lane inside the engine process.

Used as ``PYTHONPATH=<this dir>`` on an MTPLX launch. Importing mlx this early
aborts the interpreter (nanobind duplicate registration), so the patch is
deferred until the engine itself has imported ``mlx_lm.models.base``.
"""

from __future__ import annotations

import atexit
import json
import os
import sys
import threading
import time

_OUT = os.environ.get("MTPLX_FUSED_PREFILL_COUNTERS_OUT",
                      "/private/tmp/mtplx_fused_prefill.json")


def _dump() -> None:
    module = sys.modules.get("prefill_patch")
    if module is None:
        return
    try:
        with open(_OUT, "w") as handle:
            json.dump(dict(module.COUNTERS), handle, indent=2)
    except Exception:
        pass


def _install() -> None:
    if str(os.environ.get("MTPLX_FUSED_PREFILL_SDPA", "")).strip().lower() not in {
        "1", "true", "yes", "on",
    }:
        return
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    atexit.register(_dump)

    def wait_and_install() -> None:
        deadline = time.monotonic() + 1800.0
        while time.monotonic() < deadline:
            if "mlx_lm.models.base" in sys.modules:
                try:
                    import prefill_patch

                    if prefill_patch.install():
                        return
                except Exception:
                    pass
            time.sleep(0.05)

    threading.Thread(target=wait_and_install, name="mtplx-fused-prefill",
                     daemon=True).start()


_install()
