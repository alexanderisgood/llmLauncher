"""Read-only source verification for the unqualified bounded-prefill candidate.

Reconstruct the pinned source plus all three reviewed patches in a temporary
directory. Never modify the supplied checkout, install a binary, or load a model.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

COMMIT = "115609b6ef7ce5a94fc761bf395780f032b09f9b"
PATCHES = {
    "llm-launcher-hardening.patch": "6caceb71adad8a609dec32e2c6eaf5bd72f0b7240564eeb9ead5c67bc53ab124",
    "experimental-bounded-prefill.patch": "e2218762985e121bd3fa7a305739666b3b22ae8f6a1b41651a978d9d27a41311",
    "experimental-quiet-build.patch": "73328dc97e4f6f0bf0f603212b4412f5f501d538cdb9332ccc0ac81c009bd614",
}


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def verify(source: Path) -> dict:
    source = source.resolve(strict=True)
    patch_root = Path(__file__).resolve().parent
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if revision != COMMIT:
        raise ValueError("Candidate checkout is not at the pinned upstream commit")
    for name, expected in PATCHES.items():
        if digest(patch_root / name) != expected:
            raise ValueError(f"Candidate patch identity changed: {name}")
    archive = subprocess.check_output(["git", "archive", "--format=tar", COMMIT], cwd=source)
    with tempfile.TemporaryDirectory(prefix="uzu-source-proof-") as directory:
        expected_tree = Path(directory)
        with tarfile.open(fileobj=io.BytesIO(archive)) as package:
            package.extractall(expected_tree, filter="data")
        for name in PATCHES:
            subprocess.run(["git", "apply", str(patch_root / name)], cwd=expected_tree,
                           check=True, capture_output=True)
        entries = {}
        mismatches = []
        for expected in sorted(expected_tree.rglob("*")):
            relative = expected.relative_to(expected_tree).as_posix()
            actual = source / relative
            if expected.is_symlink():
                target = str(expected.readlink())
                entries[relative] = {"symlink": target}
                if not actual.is_symlink() or str(actual.readlink()) != target:
                    mismatches.append(relative)
            elif expected.is_file():
                expected_hash = digest(expected)
                entries[relative] = {"sha256": expected_hash}
                if actual.is_symlink() or not actual.is_file() or digest(actual) != expected_hash:
                    mismatches.append(relative)
        # Reject unexpected non-ignored source files that could enter the build.
        untracked = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=source,
        ).decode().split("\0")
        mismatches.extend(name for name in untracked if name and name not in entries)
        if mismatches:
            raise ValueError("Candidate source differs from reviewed patches: " + ", ".join(mismatches[:20]))
        canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
        return {
            "upstreamCommit": COMMIT,
            "patchSha256": PATCHES,
            "sourceFilesVerified": len(entries),
            "sourceContentManifestSha256": hashlib.sha256(canonical).hexdigest(),
            "scope": "source-only; no binary admission or model qualification",
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(verify(arguments.source), indent=2))
