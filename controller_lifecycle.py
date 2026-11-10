"""Small, durable controller exit records, independent of terminal output."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path


def record_event(logs_dir: Path, event: str, **details) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(), "event": event, **details,
    }
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(
            logs_dir / "controller-lifecycle.jsonl",
            os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            os.fchmod(descriptor, 0o600)
            os.write(descriptor, (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8"))
        finally:
            os.close(descriptor)
    except OSError:
        # Diagnostics must never prevent startup or model cleanup.
        pass
