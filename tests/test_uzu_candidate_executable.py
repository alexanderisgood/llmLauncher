"""Opt-in no-model smoke tests of a separately hash-pinned candidate executable."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.environ.get("LLM_LAUNCHER_UZU_CANDIDATE_BINARY"), "requires separately pinned candidate executable")
class UzuCandidateExecutableTests(unittest.TestCase):
    def test_cli_rejects_unsafe_startup_before_model_discovery(self) -> None:
        binary = Path(os.environ["LLM_LAUNCHER_UZU_CANDIDATE_BINARY"]).resolve(strict=True)
        expected = os.environ.get("LLM_LAUNCHER_UZU_CANDIDATE_SHA256", "")
        self.assertRegex(expected, r"^[0-9a-f]{64}$")
        with binary.open("rb") as handle:
            self.assertEqual(hashlib.file_digest(handle, "sha256").hexdigest(), expected)
        with tempfile.TemporaryDirectory(prefix="uzu-boundary-smoke-") as directory:
            root = Path(directory)
            root.chmod(0o700)
            # Never name an installed model. Deny networking and the model cache
            # as additional protection even if a startup rejection regresses.
            missing_model = root / "deliberately-nonexistent-model"
            self.assertFalse(missing_model.exists())
            cache = json.dumps(str(Path.home() / ".cache" / "mirai" / "models"))
            sandbox = f"(version 1)(allow default)(deny network-outbound)(deny file-read* (subpath {cache}))"

            def run(arguments: list[str]) -> tuple[int, str]:
                process = subprocess.Popen(
                    ["/usr/bin/sandbox-exec", "-p", sandbox, str(binary), *arguments],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                    start_new_session=True,
                )
                try:
                    output, _ = process.communicate(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
                    self.fail("Candidate startup did not reject within the bounded smoke-test timeout")
                return process.returncode, output

            status, help_text = run(["server", "--help"])
            self.assertEqual(status, 0, help_text)
            for option in ("--api-key-file", "--context-limit", "--max-output-tokens"):
                self.assertIn(option, help_text)

            key = root / "key"
            base = ["server", "--model", str(missing_model), "--port", "18997",
                    "--api-key-file", str(key), "--context-limit", "65536", "--max-output-tokens", "8192"]
            for label, host, mode, key_value, expected_error in (
                ("non-loopback", "0.0.0.0", 0o600, "x" * 48, "only a loopback host"),
                ("public key", "127.0.0.1", 0o644, "x" * 48, "mode 0600"),
                ("short key", "127.0.0.1", 0o600, "short", "32 to 512"),
            ):
                with self.subTest(label=label):
                    key.write_text(key_value)
                    key.chmod(mode)
                    status, output = run([*base, "--host", host])
                    self.assertNotEqual(status, 0)
                    self.assertIn(expected_error, output)
                    self.assertNotIn("Preparing model", output)
                    self.assertTrue(key.exists(), "Rejected startup must not consume the credential")

            for context_limit, output_limit, expected_error in (
                (0, 8192, "0 is not in 1024..=262144"),
                (262145, 8192, "262145 is not in 1024..=262144"),
                (65536, 0, "0 is not in 1..=262144"),
                (65536, 65537, "cannot exceed context-limit"),
            ):
                with self.subTest(context=context_limit, output=output_limit):
                    key.write_text("x" * 48)
                    key.chmod(0o600)
                    invalid_limits = list(base)
                    invalid_limits[invalid_limits.index("--context-limit") + 1] = str(context_limit)
                    invalid_limits[invalid_limits.index("--max-output-tokens") + 1] = str(output_limit)
                    status, output = run([*invalid_limits, "--host", "127.0.0.1"])
                    self.assertNotEqual(status, 0)
                    self.assertIn(expected_error, output)
                    self.assertTrue(key.exists(), "Invalid limits must be rejected before consuming the key")
                    self.assertNotIn("Preparing model", output)

            # A valid credential must be consumed even though the sentinel model
            # cannot resolve. This does NOT test authenticated HTTP completions.
            key.write_text("x" * 48)
            key.chmod(0o600)
            status, output = run([*base, "--host", "127.0.0.1"])
            self.assertNotEqual(status, 0)
            self.assertFalse(key.exists(), output)
            self.assertNotIn("Preparing model", output)
            self.assertNotIn("Failed to establish server security", output)


if __name__ == "__main__":
    unittest.main()
