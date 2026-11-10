#!/usr/bin/env python3
"""Rebuild the local Q8 fork. Build output is never automatically trusted/installed."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
COMMIT = "d25dffff1f3f56e70ddb9f11b82e7dc1b843f041"
METAL_HASH = "198488eb61359e953580a9c4530400feee1a06dd2f28a930a6ffa58aec66a597"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True, help="New, empty build directory")
    parser.add_argument("--metallib", type=Path, required=True, help="Pinned MLX 0.31.1 metallib")
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("Use 1–4 build workers on the shared 48 GiB machine.")
    if args.source_dir.exists():
        parser.error("The source directory must not already exist.")
    if hashlib.sha256(args.metallib.read_bytes()).hexdigest() != METAL_HASH:
        parser.error("The metallib does not match the pinned runtime.")
    subprocess.run(["git", "clone", "https://github.com/carloslfu/slotstream.git", str(args.source_dir)], check=True)
    def run(*command):
        return subprocess.run(command, cwd=args.source_dir, check=True)
    run("git", "checkout", "--detach", COMMIT)
    run("git", "apply", "--check", str(ROOT / "q8.patch"))
    run("git", "apply", str(ROOT / "q8.patch"))
    lib = args.source_dir / "Tools/lib/mlx-0.31.1.metallib"
    lib.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.metallib, lib)
    run("make", "build", f"SLOTSTREAM_BUILD_JOBS={args.jobs}")
    run("swift", "build", "-c", "release", "-j", str(args.jobs), "--product", "slotstream-checks")
    run(str(args.source_dir.resolve() / ".build/release/slotstream-checks"), "--tier", "t1", "--filter", "q8-cache")
    print("Build complete. Run model qualification and record the new binary hash before installation.")


if __name__ == "__main__":
    main()
