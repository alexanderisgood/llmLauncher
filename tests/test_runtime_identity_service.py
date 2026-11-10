"""Standalone runtime identity equivalence and filesystem race tests.

All runtimes and policies are generated tiny local fixtures. No executable is
run, no installed runtime is changed, and no model/network operation occurs.
"""
from contextlib import ExitStack
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import launcher
import runtime_identity as identity


class RuntimeIdentityServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="runtime-identity-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.uzu_dir = self.root / "uzu-fixture"; self.uzu_dir.mkdir(mode=0o700)
        self.uzu = self.uzu_dir / "mirai"
        self.bytes = b"tiny reviewed executable bytes\n"
        self.uzu.write_bytes(self.bytes); self.uzu.chmod(0o500)
        self.sandbox = self.root / "sandbox-exec"
        self.sandbox.write_bytes(b"not executed\n"); self.sandbox.chmod(0o700)
        self.uzu_policy = identity.UzuRuntimePolicy(
            executable=self.uzu, tag="0.5.23-test", directory_mode=0o700, binary_mode=0o500,
            release_url="https://example.invalid/fixture", upstream_commit="fixture-commit",
            source_patch_sha256="a" * 64, source_patches=("fixture.patch",),
            binary_sha256=hashlib.sha256(self.bytes).hexdigest(), binary_size=len(self.bytes),
            boundary_contract_id="fixture-native-boundary", memory_hotfix_url="https://example.invalid/fix",
            sandbox_executable=self.sandbox,
        )
        self.llama_dir = self.root / "llama-fixture"; self.llama_dir.mkdir()
        self.llama = self.llama_dir / "llama-server"
        self.llama.write_bytes(b"tiny native server bytes\n"); self.llama.chmod(0o700)
        self.dylib = self.llama_dir / "libfixture.1.dylib"
        self.dylib.write_bytes(b"tiny native library bytes\n")
        (self.llama_dir / "libfixture.dylib").symlink_to(self.dylib.name)
        self.llama_policy = identity.LlamaCppRuntimePolicy(
            server=self.llama, directory=self.llama_dir, tag="b10740", commit="b" * 40,
            archive_sha256="c" * 64, required_flags=("--fixture-ple",),
            files=((self.llama.name, self.llama.name, hashlib.sha256(self.llama.read_bytes()).hexdigest()),
                   ("libfixture.dylib", self.dylib.name, hashlib.sha256(self.dylib.read_bytes()).hexdigest())),
        )
        self.forbid_process = mock.patch.object(launcher.subprocess, "run", side_effect=AssertionError("No runtime may execute"))
        self.forbid_process.start(); self.addCleanup(self.forbid_process.stop)

    def old_uzu(self):
        constants = {
            "UZU_RUNTIME_PATH": self.uzu_policy.executable, "UZU_RUNTIME_TAG": self.uzu_policy.tag,
            "UZU_RUNTIME_DIRECTORY_MODE": self.uzu_policy.directory_mode, "UZU_RUNTIME_BINARY_MODE": self.uzu_policy.binary_mode,
            "UZU_RUNTIME_RELEASE_URL": self.uzu_policy.release_url, "UZU_RUNTIME_UPSTREAM_COMMIT": self.uzu_policy.upstream_commit,
            "UZU_RUNTIME_SOURCE_PATCH_SHA256": self.uzu_policy.source_patch_sha256, "UZU_RUNTIME_SOURCE_PATCHES": self.uzu_policy.source_patches,
            "UZU_RUNTIME_RELEASE_BINARY_SHA256": self.uzu_policy.binary_sha256, "UZU_RUNTIME_RELEASE_BINARY_SIZE": self.uzu_policy.binary_size,
            "UZU_NATIVE_BOUNDARY_CONTRACT_ID": self.uzu_policy.boundary_contract_id, "UZU_MEMORY_HOTFIX_URL": self.uzu_policy.memory_hotfix_url,
            "UZU_SANDBOX_EXECUTABLE": self.uzu_policy.sandbox_executable,
        }
        stack = ExitStack()
        for name, value in constants.items():
            stack.enter_context(mock.patch.object(launcher, name, value))
        stack.enter_context(mock.patch.object(identity.sys, "platform", "darwin"))
        stack.enter_context(mock.patch.object(identity.platform, "machine", return_value="arm64"))
        return stack

    def old_llama(self):
        stack = ExitStack()
        for name, value in {"LLAMACPP_SERVER_PATH": self.llama_policy.server, "LLAMACPP_RUNTIME_DIR": self.llama_policy.directory,
                            "LLAMACPP_RUNTIME_TAG": self.llama_policy.tag, "LLAMACPP_RUNTIME_COMMIT": self.llama_policy.commit,
                            "LLAMACPP_RUNTIME_ARCHIVE_SHA256": self.llama_policy.archive_sha256,
                            "LLAMACPP_RUNTIME_REQUIRED_FLAGS": self.llama_policy.required_flags,
                            "LLAMACPP_RUNTIME_FILE_MANIFEST": self.llama_policy.files}.items():
            stack.enter_context(mock.patch.object(launcher, name, value))
        stack.enter_context(mock.patch.object(launcher, "_cached_regular_file_sha256_matches", side_effect=self.matches))
        return stack

    @staticmethod
    def matches(path, expected):
        return hashlib.sha256(path.read_bytes()).hexdigest() == expected

    def test_generic_revision_metadata_is_identical_to_current_controller(self):
        expected = launcher.runtime_executable_revision(self.uzu)
        self.assertEqual(identity.executable_revision(self.uzu), expected)
        self.assertEqual(identity.strong_path_identity(self.uzu), launcher._llamacpp_strong_path_identity(self.uzu))
        self.assertEqual(identity.executable_stat_identity(self.uzu.stat()), launcher._executable_stat_identity(self.uzu.stat()))

    def test_generic_retained_descriptor_keeps_exact_bytes_and_closes_idempotently(self):
        opened = identity.open_executable_revision(self.uzu)
        try:
            self.assertEqual(opened.identity["sha256"], self.uzu_policy.binary_sha256)
            self.assertEqual(os.fstat(opened.fd).st_ino, opened.identity["inode"])
            self.assertEqual(json.loads(json.dumps(opened.identity)), launcher.runtime_executable_revision(self.uzu))
            descriptor = opened.fd
        finally:
            opened.close(); opened.close()
        self.assertEqual(opened.fd, -1)
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_promotion_symlink_resolves_to_same_revision_without_weakening_nofollow_open(self):
        alias = self.root / "selected-runtime"
        alias.symlink_to(self.uzu)
        self.assertEqual(identity.executable_revision(alias), launcher.runtime_executable_revision(alias))
        with self.assertRaises(ValueError):
            identity.open_executable_revision(alias)

    def test_uzu_ready_contract_and_boundary_flags_equal_current_controller(self):
        with self.old_uzu():
            expected = launcher.uzu_runtime_contract(self.uzu)
            result = identity.uzu_runtime_contract(self.uzu, self.uzu_policy)
        self.assertTrue(result["ready"])
        self.assertEqual(result, expected)
        for flag in ("nativeBearerAuthentication", "oneUseApiKeyFile", "nativeContextLimit", "nativeOutputLimit",
                     "binaryIdentityPinned", "localOnly", "telemetryBlocked", "automaticDownloadsBlocked"):
            self.assertTrue(result[flag], flag)

    def test_uzu_wrong_bytes_size_or_unpinned_digest_are_equivalent_failures(self):
        for policy in (replace(self.uzu_policy, binary_sha256="d" * 64),
                       replace(self.uzu_policy, binary_size=len(self.bytes) + 1),
                       replace(self.uzu_policy, binary_sha256="unverified")):
            with self.subTest(policy=policy):
                self.uzu_policy = policy
                with self.old_uzu():
                    self.assertEqual(identity.uzu_runtime_contract(self.uzu, policy), launcher.uzu_runtime_contract(self.uzu))
                self.assertFalse(identity.uzu_runtime_contract(self.uzu, policy)["ready"])

    def test_uzu_mode_hardlinks_alias_and_wrong_path_fail_like_current_controller(self):
        with self.old_uzu():
            self.uzu.chmod(0o700)
            self.assertEqual(identity.uzu_runtime_contract(self.uzu, self.uzu_policy), launcher.uzu_runtime_contract(self.uzu))
            self.uzu.chmod(0o500)
            alias = self.root / "alias"; alias.symlink_to(self.uzu)
            self.assertEqual(identity.uzu_runtime_contract(alias, self.uzu_policy), launcher.uzu_runtime_contract(alias))
            hardlink = self.root / "hardlink"; os.link(self.uzu, hardlink)
            self.assertEqual(identity.uzu_runtime_contract(self.uzu, self.uzu_policy), launcher.uzu_runtime_contract(self.uzu))
            hardlink.unlink()
            unrelated = self.root / "other-mirai"; unrelated.write_bytes(self.bytes); unrelated.chmod(0o500)
            self.assertEqual(identity.uzu_runtime_contract(unrelated, self.uzu_policy), launcher.uzu_runtime_contract(unrelated))

    def test_uzu_directory_and_ancestor_protection_match(self):
        with self.old_uzu():
            self.uzu_dir.chmod(0o755)
            result = identity.uzu_runtime_contract(self.uzu, self.uzu_policy)
            self.assertEqual(result, launcher.uzu_runtime_contract(self.uzu))
            self.assertIn("0700", result["reason"])
            self.uzu_dir.chmod(0o700)
            self.root.chmod(0o777)
            result = identity.uzu_runtime_contract(self.uzu, self.uzu_policy)
            self.assertEqual(result, launcher.uzu_runtime_contract(self.uzu))
            self.assertFalse(result["ready"])
            self.root.chmod(0o700)

    def test_uzu_retained_descriptor_is_owned_by_caller_and_replacement_is_rejected(self):
        with self.old_uzu():
            opened = identity.open_uzu_runtime_executable(self.uzu, self.uzu_policy)
            try:
                result = identity.uzu_runtime_contract(self.uzu, self.uzu_policy, opened_revision=opened)
                self.assertTrue(result["ready"])
                self.assertGreaterEqual(opened.fd, 0)
                self.uzu.rename(self.uzu.with_suffix(".old"))
                self.uzu.write_bytes(self.bytes); self.uzu.chmod(0o500)
                self.assertFalse(identity.uzu_runtime_contract(self.uzu, self.uzu_policy, opened_revision=opened)["ready"])
                with self.assertRaisesRegex(ValueError, "immediately before launch"):
                    identity.confirm_open_uzu_executable(opened, self.uzu_policy)
            finally:
                opened.close()

    def test_closed_descriptor_cannot_be_reused_for_uzu_contract(self):
        with self.old_uzu():
            opened = identity.open_uzu_runtime_executable(self.uzu, self.uzu_policy)
            opened.close()
            result = identity.uzu_runtime_contract(self.uzu, self.uzu_policy, opened_revision=opened)
        self.assertFalse(result["ready"])
        self.assertIn("already closed", result["reason"])

    def test_replacement_during_hash_fails_and_closes_descriptor(self):
        original_read = os.read
        replaced = False
        descriptors = []
        def racing_read(descriptor, size):
            nonlocal replaced
            descriptors.append(descriptor)
            result = original_read(descriptor, size)
            if result and not replaced:
                replaced = True
                self.uzu.rename(self.uzu.with_suffix(".before"))
                self.uzu.write_bytes(self.bytes); self.uzu.chmod(0o500)
            return result
        with mock.patch.object(identity.os, "read", side_effect=racing_read), self.assertRaisesRegex(ValueError, "changed"):
            identity.open_executable_revision(self.uzu)
        for descriptor in set(descriptors):
            with self.assertRaises(OSError):
                os.fstat(descriptor)

    def test_in_place_mutation_during_hash_is_rejected_even_with_same_inode(self):
        original_read = os.read
        mutated = False
        inode = self.uzu.stat().st_ino
        def racing_read(descriptor, size):
            nonlocal mutated
            result = original_read(descriptor, size)
            if result and not mutated:
                mutated = True
                self.uzu.chmod(0o700)
                self.uzu.write_bytes(b"changed executable data length\n")
                self.uzu.chmod(0o500)
            return result
        with mock.patch.object(identity.os, "read", side_effect=racing_read), self.assertRaisesRegex(ValueError, "changed"):
            identity.open_executable_revision(self.uzu)
        self.assertEqual(self.uzu.stat().st_ino, inode)

    def test_llamacpp_closure_and_contract_match_current_controller(self):
        with self.old_llama():
            expected = launcher.llamacpp_runtime_contract(str(self.llama))
            result = identity.llamacpp_runtime_contract(str(self.llama), self.llama_policy, self.matches)
            self.assertEqual(identity.llamacpp_runtime_closure_identities(self.llama_dir, self.llama_policy),
                             launcher._llamacpp_runtime_closure_identities(self.llama_dir))
        self.assertTrue(result["ready"])
        self.assertEqual(result, expected)

    def test_llamacpp_missing_modified_and_escaped_libraries_fail_equivalently(self):
        with self.old_llama():
            self.dylib.write_bytes(b"different bytes")
            self.assertEqual(identity.llamacpp_runtime_contract(str(self.llama), self.llama_policy, self.matches),
                             launcher.llamacpp_runtime_contract(str(self.llama)))
            alias = self.llama_dir / "libfixture.dylib"
            alias.unlink(); outside = self.root / self.dylib.name; self.dylib.rename(outside); alias.symlink_to(outside)
            self.assertEqual(identity.llamacpp_runtime_contract(str(self.llama), self.llama_policy, self.matches),
                             launcher.llamacpp_runtime_contract(str(self.llama)))

    def test_llamacpp_alias_target_swap_during_digest_cannot_pass_closure(self):
        changed = False
        def digest_with_race(path, digest):
            nonlocal changed
            matched = self.matches(path, digest)
            if not changed:
                changed = True
                alias = self.llama_dir / "libfixture.dylib"
                alias.unlink(); alias.symlink_to(self.llama.name)
            return matched
        result = identity.llamacpp_runtime_contract(str(self.llama), self.llama_policy, digest_with_race)
        self.assertFalse(result["ready"])

    def test_llamacpp_same_bytes_new_inode_during_digest_is_rejected(self):
        changed = False
        def digest_with_replacement(path, digest):
            nonlocal changed
            matched = self.matches(path, digest)
            if path == self.dylib and not changed:
                changed = True
                contents = path.read_bytes(); path.rename(path.with_suffix(".old")); path.write_bytes(contents)
            return matched
        result = identity.llamacpp_runtime_contract(str(self.llama), self.llama_policy, digest_with_replacement)
        self.assertFalse(result["ready"])
        self.assertIn("changed during byte verification", result["reason"])

    def test_no_controller_state_or_execution_dependency(self):
        self.assertNotIn("launcher", identity.__dict__)
        self.assertNotIn("BINARIES", identity.__dict__)
        self.assertNotIn("subprocess", identity.__dict__)
        self.assertTrue(identity.uzu_listener_protection_ready({"listenerIsolationBlocked": False, "rawListenerAuthenticated": True}))
        self.assertFalse(identity.uzu_listener_protection_ready({"rawListenerAuthenticated": True}))


if __name__ == "__main__":
    unittest.main()
