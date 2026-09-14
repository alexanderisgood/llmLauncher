"""Bounded reads for launcher log previews and diagnostic evidence."""

import os
from pathlib import Path


def read_log_tail(path: Path, characters: int) -> str:
    """Return the last UTF-8 characters with read_text's newline handling.

    Four bytes per character covers UTF-8 and CRLF. One extra character
    keeps a potentially split leading sequence outside the returned suffix.
    Both reading and allocation are bounded even when a log keeps growing.
    """
    if characters <= 0:
        return ""
    byte_limit = 4 * characters + 4
    try:
        with path.open("rb") as handle:
            size = handle.seek(0, os.SEEK_END)
            handle.seek(max(0, size - byte_limit))
            data = handle.read(byte_limit)
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")[-characters:]
