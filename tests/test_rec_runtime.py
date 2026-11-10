"""Small metadata and launch-boundary fixtures; no Rec process loads weights."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import rec_runtime as rec


class RecRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.alias_temporary = tempfile.TemporaryDirectory(prefix="llmr-test-", dir="/tmp")
        self.addCleanup(self.alias_temporary.cleanup)
        self.alias_parent = Path(self.alias_temporary.name)
        self.root = Path(self.temporary.name).resolve()
        self.binary = self.root / "rec"
        self.binary.write_bytes(b"fixture official CLI\n")
        self.binary.chmod(0o700)
        self.model_root = self.root / "model"
        self.model_root.mkdir()
        config = {"model_type": "flint", "max_position_embeddings": 262144,
            "quantization": {"bits": 4, "group_size": 64},
            "mlx_export": {"bits": 4, "routed_expert_bits": 4, "embedding_bits": 8},
            "num_hidden_layers": 3, "layer_types": ["full_attention", "sliding_attention", "sliding_attention"],
            "num_key_value_heads": 4, "head_dim": 128, "sliding_window": 513}
        (self.model_root / "config.json").write_text(json.dumps(config))
        (self.model_root / "generation_config.json").write_text(json.dumps(rec.DEFAULT_SAMPLING))
        header = json.dumps({"fixture.weight": {"dtype": "F32", "shape": [2], "data_offsets": [0, 8]}}).encode()
        (self.model_root / "model-00000.safetensors").write_bytes(len(header).to_bytes(8, "little") + header + bytes(8))
        manifest = tuple((path.name, path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())
            for path in sorted(self.model_root.iterdir()))
        patcher = mock.patch.multiple(rec, MODEL_FILES=manifest, CLI_BYTES=self.binary.stat().st_size,
            RUN_ALIAS_PARENT=self.alias_parent,
            CLI_SHA256=hashlib.sha256(self.binary.read_bytes()).hexdigest())
        patcher.start()
        self.addCleanup(patcher.stop)
        self.install = rec.inspect_install(self.binary, data_dir=self.root / "global-data")
        self.model = rec.inspect_model(self.model_root)
        self.assertIsNotNone(self.model)

    def create_run(self):
        run = self.root / "run"
        run.mkdir(mode=0o700)
        return run

    def test_cli_hash_rejects_same_size_mutation_with_restored_mtime(self):
        self.assertTrue(self.install["ready"])
        self.assertEqual(self.install["version"], "0.1.0")
        before = self.binary.stat()
        self.binary.write_bytes(b"x" * before.st_size)
        os.utime(self.binary, ns=(before.st_atime_ns, before.st_mtime_ns))
        changed = rec.inspect_install(self.binary, data_dir=self.root / "global-data")
        self.assertFalse(changed["ready"])
        self.assertNotEqual(changed["identity"], self.install["identity"])

    def test_model_headers_and_native_payload_receipt_have_separate_meanings(self):
        self.assertFalse(self.model["payloadVerified"])
        stamps = {item["name"]: {key: item[key] for key in
            ("sha256", "size", "device", "inode", "mtime_ns", "ctime_ns")} for item in self.model["files"]}
        (self.model_root / "verified.json").write_text(json.dumps(stamps))
        verified = rec.inspect_model(self.model_root)
        self.assertTrue(verified["payloadVerified"])
        # Native receipt updates do not invalidate an otherwise identical model.
        self.assertEqual(verified["identity"], self.model["identity"])
        shard = self.model_root / "model-00000.safetensors"
        before = shard.stat()
        with shard.open("r+b") as handle:
            handle.seek(-1, os.SEEK_END)
            handle.write(b"x")
        os.utime(shard, ns=(before.st_atime_ns, before.st_mtime_ns))
        changed = rec.inspect_model(self.model_root)
        self.assertFalse(changed["payloadVerified"])
        self.assertNotEqual(changed["identity"], self.model["identity"])

    def test_incomplete_or_changed_checkpoint_cannot_be_catalogued(self):
        shard = self.model_root / "model-00000.safetensors"
        extra = self.model_root / "model-unexpected.safetensors"
        extra.write_bytes(shard.read_bytes())
        self.assertIsNone(rec.inspect_model(self.model_root))
        extra.unlink()
        source = self.model_root / "config.json"
        source.write_text(source.read_text().replace('"bits": 4', '"bits": 8'))
        self.assertIsNone(rec.inspect_model(self.model_root))
        shard.unlink()
        self.assertIsNone(rec.inspect_model(self.model_root))

    def test_memory_uses_full_context_and_bounded_sliding_layers(self):
        estimate = rec.memory_estimate(self.model, 32768)
        kv = 4 * 128 * 2 * 2 * (32768 + 2 * 513)
        self.assertEqual(estimate["kvCacheBytes"], kv)
        self.assertEqual(estimate["estimatedWorkingSetBytes"], self.model["weightBytes"] + kv + 2 * 1024**3)
        with mock.patch.object(rec, "host_support", return_value=(True, "Supported fixture Mac")):
            model = rec.model_record(self.install, self.model, [("rec", "Rec"), ("splash", "Splash")], 48 * 1024**3)
        self.assertTrue(model["backends"]["rec"]["runnable"])
        self.assertFalse(model["backends"]["splash"]["runnable"])
        self.assertEqual(model["backends"]["rec"]["agentReasoning"], ["auto"])
        self.assertEqual(model["defaultSampling"]["temperature"], 1.0)
        self.assertEqual(model["defaultSampling"]["top_p"], 0.95)
        self.assertEqual(model["defaultSampling"]["top_k"], 20)
        self.assertNotIn("min_p", model["backends"]["rec"]["samplingFields"])

    def test_private_run_reuses_weights_and_executes_foreground_cli(self):
        run = self.create_run()
        shared = Path(self.install["dataRoot"])
        (shared / "runtimes").mkdir(parents=True)
        (shared / "config").mkdir()
        sentinel = shared / "config/api-key"
        sentinel.write_text("Existing user key")
        key = "ab" * 32
        argv, environment = rec.prepare_run(self.install, self.model, run, 32768, 18081, key, output=4096)
        private = run / "rec-data/rec"
        self.assertEqual((private / "models" / rec.MODEL_CACHE_KEY).resolve(), self.model_root)
        self.assertEqual((private / "runtimes").resolve(), shared / "runtimes")
        self.assertEqual(stat.S_IMODE((private / "config/api-key").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((run / "rec.json").stat().st_mode), 0o600)
        self.assertEqual(sentinel.read_text(), "Existing user key")
        self.assertNotIn(key, " ".join(argv) + json.dumps(environment))
        self.assertIn("-I", argv)
        self.assertIn("-S", argv)
        self.assertEqual(environment["HF_HUB_OFFLINE"], "1")
        with mock.patch.object(rec.os, "execve") as execute:
            rec.run_verified(run / "rec.json")
        binary, native_argv, native_environment = execute.call_args.args
        self.assertEqual(binary, str(self.binary))
        self.assertEqual(native_argv, [str(self.binary), "serve", "flint", "--context", "32768", "--port", "18081"])
        self.assertEqual(Path(native_environment["XDG_DATA_HOME"]).resolve(), run / "rec-data")

    def test_long_run_folder_uses_short_owned_alias_and_precise_cleanup(self):
        run = self.root / ("long-launcher-folder-" * 7) / "run"
        run.mkdir(parents=True, mode=0o700)
        _argv, environment = rec.prepare_run(self.install, self.model, run, 32768, 18081, "56" * 32)
        alias = Path(environment["XDG_DATA_HOME"])
        self.assertGreater(len(os.fsencode(run / "rec-data/rec/state/control.sock")), 104)
        self.assertLess(len(os.fsencode(alias / "rec/state/control.sock")), 104)
        self.assertEqual(alias.parent, self.alias_parent)
        self.assertEqual(alias.name, hashlib.sha256(str(run).encode()).hexdigest()[:24])
        self.assertEqual(alias.resolve(), run / "rec-data")
        self.assertEqual(json.loads((run / "rec.json").read_text())["xdgDataHome"], str(alias))
        other = self.root / "unrelated-data"
        other.mkdir()
        marker = other / "keep"
        marker.write_text("untouched")
        alias.unlink()
        alias.symlink_to(other, target_is_directory=True)
        with mock.patch.object(rec.os, "execve") as execute:
            with self.assertRaisesRegex(ValueError, "short private data link changed"):
                rec.run_verified(run / "rec.json")
            execute.assert_not_called()
        self.assertFalse(rec.cleanup_run_alias(run))
        self.assertTrue(alias.is_symlink())
        self.assertEqual(marker.read_text(), "untouched")
        alias.unlink()
        alias.symlink_to(run / "rec-data", target_is_directory=True)
        self.assertTrue(rec.cleanup_run_alias(run))
        self.assertFalse(alias.is_symlink())
        self.assertTrue((run / "rec-data/rec/config/api-key").is_file())
        self.assertTrue((self.model_root / "config.json").is_file())
        self.assertFalse(rec.cleanup_run_alias(run))

    def test_alias_parent_cannot_be_shared_or_replaced_by_a_symlink(self):
        run = self.create_run()
        self.alias_parent.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "private owned directory"):
            rec.prepare_run(self.install, self.model, run, 32768, 18081, "78" * 32)
        self.alias_parent.chmod(0o700)
        run2 = self.root / "run2"
        run2.mkdir()
        linked_parent = self.root / "linked-alias-parent"
        linked_parent.symlink_to(self.alias_parent, target_is_directory=True)
        with mock.patch.object(rec, "RUN_ALIAS_PARENT", linked_parent):
            with self.assertRaisesRegex(ValueError, "private owned directory"):
                rec.prepare_run(self.install, self.model, run2, 32768, 18081, "78" * 32)

    def test_changed_model_or_public_key_permissions_stop_before_exec(self):
        run = self.create_run()
        rec.prepare_run(self.install, self.model, run, 32768, 18081, "12" * 32)
        key = run / "rec-data/rec/config/api-key"
        key.chmod(0o644)
        with mock.patch.object(rec.os, "execve") as execute:
            with self.assertRaisesRegex(ValueError, "API key file changed"):
                rec.run_verified(run / "rec.json")
            execute.assert_not_called()
        key.chmod(0o600)
        shard = self.model_root / "model-00000.safetensors"
        with shard.open("r+b") as handle:
            handle.seek(-1, os.SEEK_END)
            handle.write(b"x")
        with mock.patch.object(rec.os, "execve") as execute:
            with self.assertRaisesRegex(ValueError, "Flint changed"):
                rec.run_verified(run / "rec.json")
            execute.assert_not_called()

    def test_native_context_and_host_boundaries_are_explicit(self):
        for context, output in ((262145, 8192), (32768, 32768), (32768, True), (True, 1)):
            with self.subTest(context=context, output=output), self.assertRaises(ValueError):
                rec.planning_arguments(self.install, self.model, context, port=18081, output=output)
        with mock.patch.object(rec.platform, "system", return_value="Darwin"), mock.patch.object(rec.platform, "machine", return_value="arm64"):
            self.assertTrue(rec.host_support(48 * 1024**3, chip="Apple M5 Pro")[0])
            self.assertFalse(rec.host_support(32 * 1024**3, chip="Apple M5 Pro")[0])
            self.assertFalse(rec.host_support(96 * 1024**3, chip="Apple M4 Max")[0])
        rec.validate_served_catalog({"data": [{"id": "flint"}]})
        with self.assertRaises(ValueError):
            rec.validate_served_catalog({"data": [{"id": "unrelated"}]})

    def test_isolated_entrypoint_can_import_the_local_header_reader(self):
        missing = self.root / "missing-private-config.json"
        result = subprocess.run([sys.executable, "-I", "-S", "-B", str(Path(rec.__file__).resolve()), str(missing)],
            capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FileNotFoundError", result.stderr)
        self.assertNotIn("ModuleNotFoundError", result.stderr)


if __name__ == "__main__":
    unittest.main()
