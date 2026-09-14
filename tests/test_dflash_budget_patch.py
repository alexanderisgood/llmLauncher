import difflib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import dflash_budget_patch as patches


class NativeBudgetPatch(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.runtime = self.root / "runtime"
        self.site = self.runtime / "lib/python3.11/site-packages"
        self.before = {"omlx/engine/dflash.py": b"budget = None\n",
                       "dflash_mlx/runtime/__init__.py": b"process = False\n"}
        self.after = {"omlx/engine/dflash.py": b"budget = 4096\n",
                      "dflash_mlx/runtime/__init__.py": b"process = True\n"}
        for name, content in self.before.items():
            path = self.site / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.manifest = self.root / "patch.json"
        self.prepare()

    def prepare(self):
        text = "".join("".join(difflib.unified_diff(
            self.before[name].decode().splitlines(keepends=True),
            self.after[name].decode().splitlines(keepends=True),
            fromfile="a/" + name, tofile="b/" + name)) for name in self.before)
        (self.root / "fix.patch").write_text(text)
        self.manifest.write_text(json.dumps({"id": "fixture-budget", "patch": "fix.patch",
            "patchSha256": patches.digest(text.encode()),
            "files": {name: {"beforeSha256": patches.digest(content),
                              "afterSha256": patches.digest(self.after[name])}
                      for name, content in self.before.items()}}))

    def assertOriginal(self):
        for name, content in self.before.items():
            self.assertEqual((self.site / name).read_bytes(), content)

    def test_verified_patch_is_repeatable_and_preserves_originals(self):
        self.assertFalse(patches.inspect(self.runtime, self.manifest)[2]["applied"])
        receipt = patches.apply(self.runtime, self.manifest)
        self.assertTrue(receipt["applied"])
        for name in self.before:
            self.assertEqual((self.site / name).read_bytes(), self.after[name])
            backup = self.runtime / ".llm-launcher-patches/fixture-budget/original" / name
            self.assertEqual(backup.read_bytes(), self.before[name])
        self.assertEqual(patches.apply(self.runtime, self.manifest), receipt)

    def test_changed_source_is_rejected_before_any_other_file_changes(self):
        changed = "dflash_mlx/runtime/__init__.py"
        (self.site / changed).write_text("unreviewed = True\n")
        with self.assertRaisesRegex(RuntimeError, "differs"):
            patches.apply(self.runtime, self.manifest)
        self.assertEqual((self.site / "omlx/engine/dflash.py").read_bytes(),
                         self.before["omlx/engine/dflash.py"])
        self.assertEqual((self.site / changed).read_text(), "unreviewed = True\n")

    def test_changed_patch_or_invalid_python_cannot_touch_runtime(self):
        (self.root / "fix.patch").write_text("unreviewed patch")
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            patches.apply(self.runtime, self.manifest)
        self.assertOriginal()
        self.after["omlx/engine/dflash.py"] = b"def invalid(\n"
        self.prepare()
        with self.assertRaises(SyntaxError):
            patches.apply(self.runtime, self.manifest)
        self.assertOriginal()

    def test_write_failure_restores_previously_replaced_source(self):
        replace = patches.os.replace
        calls = 0
        def fail_second(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("fixture interrupted write")
            return replace(source, destination)
        with mock.patch.object(patches.os, "replace", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "interrupted"):
                patches.apply(self.runtime, self.manifest)
        self.assertOriginal()
        self.assertFalse(patches.inspect(self.runtime, self.manifest)[2]["applied"])

    def test_partial_install_is_reported_without_modifying_either_file(self):
        name = "omlx/engine/dflash.py"
        (self.site / name).write_bytes(self.after[name])
        with self.assertRaisesRegex(RuntimeError, "partially"):
            patches.apply(self.runtime, self.manifest)
        self.assertEqual((self.site / name).read_bytes(), self.after[name])
        self.assertEqual((self.site / "dflash_mlx/runtime/__init__.py").read_bytes(),
                         self.before["dflash_mlx/runtime/__init__.py"])


if __name__ == "__main__":
    unittest.main()
