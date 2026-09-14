"""Opt-in CPU-only checks of the isolated, NOT INSTALLED Uzu prefill patch."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PATCH_ROOT = ROOT / "runtime_patches" / "uzu" / "0.5.23"
COMMIT = "115609b6ef7ce5a94fc761bf395780f032b09f9b"
STREAM = "crates/uzu-engine/src/engine/language_model/stream/stream.rs"
ALLOCATOR = "crates/uzu-engine/src/backends/common/allocator/range_allocator.rs"
METAL_COMPILER = "crates/uzu-engine/build/metal/compiler.rs"


def function_source(source: str, name: str) -> str:
    start = source.index(f"fn {name}(")
    opening = source.index("{", start)
    depth = 1
    cursor = opening + 1
    while depth:
        depth += (source[cursor] == "{") - (source[cursor] == "}")
        cursor += 1
    return source[start:cursor]


@unittest.skipUnless(os.environ.get("LLM_LAUNCHER_UZU_SOURCE"), "requires pinned Uzu source; no model load")
class UzuPrefillCandidateTests(unittest.TestCase):
    def test_complete_source_verifier_rejects_modified_build_input(self) -> None:
        spec = importlib.util.spec_from_file_location("uzu_candidate_source_proof", PATCH_ROOT / "verify_candidate_source.py")
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        source = Path(os.environ["LLM_LAUNCHER_UZU_SOURCE"]).resolve()
        report = verifier.verify(source)
        self.assertGreater(report["sourceFilesVerified"], 1500)
        self.assertEqual(report["sourceContentManifestSha256"],
                         "85ed840a55874324f63360bff43e22b0ec3f676b727bfa8f11759ca2adc2749c")
        actual_digest = verifier.digest
        with mock.patch.object(verifier, "digest", side_effect=lambda path: (
            "0" * 64 if path == source / STREAM else actual_digest(path)
        )):
            with self.assertRaisesRegex(ValueError, "Candidate source differs"):
                verifier.verify(source)

    def test_patch_allocator_lifetimes_and_token_schedule(self) -> None:
        source = Path(os.environ["LLM_LAUNCHER_UZU_SOURCE"]).resolve()
        rustc = shutil.which("rustc") or "/opt/homebrew/bin/rustc"
        self.assertEqual(subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=source, text=True,
        ).strip(), COMMIT)
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            for name in (STREAM, ALLOCATOR, METAL_COMPILER):
                contents = subprocess.check_output(["git", "show", f"{COMMIT}:{name}"], cwd=source)
                destination = fixture / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(contents)
            self.assertEqual(hashlib.sha256((fixture / ALLOCATOR).read_bytes()).hexdigest(),
                             "dbec9d8fb9eeff0807c0596d8518e4de72d4c7032fa83c5a7c9e29697f35a873")
            original_compiler = (fixture / METAL_COMPILER).read_text()
            for patch_name in ("experimental-bounded-prefill.patch", "experimental-quiet-build.patch"):
                patch = PATCH_ROOT / patch_name
                for arguments in (["--check"], []):
                    subprocess.run(["git", "apply", *arguments, str(patch)], cwd=fixture, check=True, capture_output=True)
            compiler = (fixture / METAL_COMPILER).read_text()
            self.assertEqual(function_source(compiler, "shard_footers"),
                             function_source(original_compiler, "shard_footers"))
            self.assertIn("let num_concurrent_compiles = 1;", compiler)
            self.assertIn(".buffered(2)", compiler)
            self.assertNotIn("try_join_all", compiler)
            stream = (fixture / STREAM).read_text()
            self.assertIn("let max_batch_size = 1024;", stream)
            self.assertIn("prefill_submission_boundary(encoded_prefill_tokens, sample_last)", stream)
            self.assertIn(".wait_until_completed()", stream)
            probe = (PATCH_ROOT / "allocator_probe.rs").read_text()
            probe += "\n" + function_source(stream, "prefill_chunk_parts")
            probe += "\n" + function_source(stream, "prefill_submission_boundary")
            probe += r'''
#[test]
fn submissions_preserve_tokens_sampling_and_group_boundaries() {
    for length in [1, 2, 1023, 1024, 1025, 8191, 8192, 8193, 16384, 49152, 98304, 131072] {
        for split in [false, true] {
            let tokens: Vec<u64> = (0..length as u64).collect();
            let batches = tokens.len().div_ceil(1024);
            let mut seen = Vec::new();
            let mut group_tokens = 0;
            let mut sampled_positions = Vec::new();
            for (index, chunk) in tokens.chunks(1024).enumerate() {
                for (part, sample_last) in prefill_chunk_parts(chunk, index + 1 == batches, split).into_iter().flatten() {
                    assert!(!part.is_empty() && part.len() <= 1024);
                    seen.extend_from_slice(part);
                    group_tokens += part.len();
                    assert!(group_tokens <= 8192);
                    if sample_last {
                        sampled_positions.push(seen.len() - 1);
                        assert!(!prefill_submission_boundary(group_tokens, true));
                    }
                    if prefill_submission_boundary(group_tokens, sample_last) {
                        assert_eq!(group_tokens, 8192);
                        group_tokens = 0;
                    }
                }
            }
            assert_eq!(seen, tokens);
            assert_eq!(sampled_positions, vec![length - 1]);
        }
    }
}
'''
            probe_path = fixture / "probe.rs"
            probe_path.write_text(probe)
            executable = fixture / "probe"
            subprocess.run([rustc, "--edition=2024", "--test", str(probe_path), "-o", str(executable)],
                           env={**os.environ, "UZU_SOURCE": str(fixture)}, check=True, capture_output=True)
            result = subprocess.run([str(executable)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("4 passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
