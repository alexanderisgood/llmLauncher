"""No-model isolation tests for the developer-only candidate runner."""
import fcntl
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "candidate_qualification", ROOT / "runtime_patches/uzu/0.5.23/candidate_qualification.py",
)
candidate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(candidate)


class UzuCandidateQualificationTests(unittest.TestCase):
    def test_state_identity_isolated_without_changing_safety_or_original_maps(self):
        normal = Path("/owner/production")
        specs = {"mirai": (("normal", "old-path", "baseline"),)}
        binaries = {"mirai": "old-path", "omlx": "other-engine"}
        app = SimpleNamespace(
            STATE_DIR=normal, RUNS_DIR=normal / "runs", LOGS_DIR=normal / "logs",
            MANAGED_RUNTIMES_DIR=normal / "runtimes",
            RUNTIME_PREFERENCES_FILE=normal / "runtime-preferences.json",
            RUNTIME_UPDATE_DIR=normal / "runtime-updates",
            MODEL_CACHE=Path("/owner/models"), APP_DIR=ROOT,
            UZU_PROCESS_MEMORY_CEILING_BYTES=38 * 1024**3,
            UZU_PROCESS_CEILING_ADMISSION_MARGIN_BYTES=2 * 1024**3,
            RUNTIME_CANDIDATE_SPECS=specs, BINARIES=binaries,
            _VERIFIED_FILE_SHA256_CACHE={"baseline": True},
        )
        lock = candidate.configure_candidate(app)
        self.assertEqual(candidate.ROOT, ROOT)
        self.assertEqual(lock, normal / "controller-instance.lock")
        for name in ("STATE_DIR", "RUNS_DIR", "LOGS_DIR", "MANAGED_RUNTIMES_DIR",
                     "RUNTIME_PREFERENCES_FILE", "RUNTIME_UPDATE_DIR", "UZU_RUNTIME_PATH"):
            self.assertTrue(getattr(app, name).is_relative_to(candidate.STATE), name)
        self.assertEqual(app.MODEL_CACHE, Path("/owner/models"))
        self.assertEqual(app.APP_DIR, ROOT)
        self.assertEqual(app.UZU_PROCESS_MEMORY_CEILING_BYTES, 38 * 1024**3)
        self.assertEqual(app.UZU_PROCESS_CEILING_ADMISSION_MARGIN_BYTES, 2 * 1024**3)
        self.assertEqual(app.UZU_RUNTIME_RELEASE_BINARY_SHA256, candidate.BINARY_SHA256)
        self.assertEqual(app.UZU_RUNTIME_SOURCE_PATCH_SHA256, candidate.PATCH_CHAIN_SHA256)
        self.assertNotEqual(app.BINARIES["mirai"], binaries["mirai"])
        self.assertEqual(specs["mirai"][0][1], "old-path")
        self.assertEqual(app._VERIFIED_FILE_SHA256_CACHE, {})

    def test_patch_chain_fingerprint_matches_reviewed_order(self):
        import hashlib
        combined = b"".join((candidate.PATCH_ROOT / name).read_bytes() for name in (
            "llm-launcher-hardening.patch", "experimental-bounded-prefill.patch",
            "experimental-quiet-build.patch",
        ))
        self.assertEqual(hashlib.sha256(combined).hexdigest(), candidate.PATCH_CHAIN_SHA256)

    def test_running_controller_excludes_candidate_and_metadata_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "controller-instance.lock"
            metadata = '{"port":18080,"pid":123}'
            path.write_text(metadata)
            with path.open("r") as controller:
                fcntl.flock(controller, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(RuntimeError, "Stop the normal launcher"):
                    candidate.exclusive_controller_lock(path)
            with candidate.exclusive_controller_lock(path):
                with self.assertRaisesRegex(RuntimeError, "Stop the normal launcher"):
                    candidate.exclusive_controller_lock(path)
            self.assertEqual(path.read_text(), metadata)
            with candidate.exclusive_controller_lock(path):
                pass

    def test_controller_lock_rejects_symlinks_and_hardlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "lock"
            target.touch()
            link = Path(directory) / "link"
            link.symlink_to(target)
            with self.assertRaises(OSError):
                candidate.exclusive_controller_lock(link)
            link.unlink()
            link.hardlink_to(target)
            with self.assertRaisesRegex(ValueError, "single owner-owned"):
                candidate.exclusive_controller_lock(target)

    def test_request_preserves_real_qualification_not_short_smoke(self):
        for context in (65536, 131072):
            payload = candidate.request(context)
            self.assertEqual(payload["context"], context)
            self.assertEqual(payload["output"], 16384)
            self.assertEqual(payload["scope"], "qualification")
            self.assertEqual(payload["reasoning"], "auto")
            self.assertEqual(payload["generation"], {"sampling": "model"})
            self.assertEqual(payload["calibrationCooling"], "default")
        with self.assertRaises(ValueError):
            candidate.request(32768)


if __name__ == "__main__":
    unittest.main()
