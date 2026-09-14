"""Install the audited local DFlash budget patch; never run during generation."""
import ast
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

MANIFEST = Path(__file__).parent / "runtime_patches/omlx/0.6.4/dflash-thinking-budget.json"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inspect(runtime, manifest_path=MANIFEST):
    manifest = json.loads(Path(manifest_path).read_text())
    sites = list(Path(runtime).glob("lib/python*/site-packages"))
    if len(sites) != 1:
        raise RuntimeError("The managed runtime must have one Python package directory.")
    site = sites[0].resolve()
    files = {}
    for relative, hashes in manifest["files"].items():
        path = site / relative
        if (Path(relative).is_absolute() or ".." in Path(relative).parts
                or Path(relative).parts[0] not in {"omlx", "dflash_mlx"}
                or path.suffix != ".py" or path.is_symlink()
                or not path.resolve().is_relative_to(site)):
            raise RuntimeError("Invalid native patch destination.")
        actual = digest(path.read_bytes())
        if actual not in (hashes["beforeSha256"], hashes["afterSha256"]):
            raise RuntimeError(f"Native source differs from the audited DFlash patch: {relative}")
        files[relative] = actual
    if not files:
        raise RuntimeError("The native patch has no files.")
    applied = all(files[name] == manifest["files"][name]["afterSha256"] for name in files)
    pristine = all(files[name] == manifest["files"][name]["beforeSha256"] for name in files)
    if not applied and not pristine:
        raise RuntimeError("The native DFlash patch is only partially installed.")
    return site, manifest, {"id": manifest["id"], "applied": applied,
                            "patchSha256": manifest["patchSha256"], "files": files}


def apply(runtime, manifest_path=MANIFEST):
    runtime = Path(runtime).resolve(strict=True)
    with (runtime / ".llm-launcher-patch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        site, manifest, receipt = inspect(runtime, manifest_path)
        if receipt["applied"]:
            return receipt
        patch = Path(manifest_path).parent / manifest["patch"]
        if digest(patch.read_bytes()) != manifest["patchSha256"]:
            raise RuntimeError("The native DFlash patch checksum changed.")
        originals = {name: (site / name).read_bytes() for name in manifest["files"]}
        with tempfile.TemporaryDirectory(prefix=".dflash-patch-", dir=runtime) as folder:
            staged = Path(folder)
            for name in originals:
                target = staged / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(site / name, target)
            result = subprocess.run(["/usr/bin/patch", "-t", "-p1", "-d", str(staged),
                                     "-i", str(patch.resolve())], capture_output=True, text=True, timeout=30)
            if result.returncode:
                raise RuntimeError("The audited native patch did not apply cleanly: " + result.stdout[-1000:])
            for name, hashes in manifest["files"].items():
                content = (staged / name).read_bytes()
                if digest(content) != hashes["afterSha256"]:
                    raise RuntimeError(f"Patched native source failed verification: {name}")
                ast.parse(content, filename=name)
            backup = runtime / ".llm-launcher-patches" / manifest["id"] / "original"
            for name, content in originals.items():
                destination = backup / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists() and destination.read_bytes() != content:
                    raise RuntimeError("The original native source backup differs; it was preserved.")
                destination.write_bytes(content)
            written = []
            try:
                for name in originals:
                    os.replace(staged / name, site / name)
                    written.append(name)
            except BaseException:
                for name in written:
                    restored = staged / name
                    restored.write_bytes(originals[name])
                    os.replace(restored, site / name)
                raise
        _, _, receipt = inspect(runtime, manifest_path)
        (backup.parent / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        return receipt


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(apply(args.runtime) if args.apply else inspect(args.runtime)[2]))
