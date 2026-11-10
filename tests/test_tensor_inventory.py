from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import launcher
import tensor_inventory as inventory


def write_shard(path: Path, header: dict | bytes, payload_bytes: int = 2) -> bytes:
    encoded = header if isinstance(header, bytes) else json.dumps(header, separators=(",", ":")).encode()
    with path.open("wb") as handle:
        handle.write(len(encoded).to_bytes(8, "little"))
        handle.write(encoded)
        handle.truncate(8 + len(encoded) + payload_bytes)
    return encoded


class TensorInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.shard = self.root / "model.safetensors"
        self.cache = inventory.HeaderCache()
        self.header = {
            "a": {"dtype": "U8", "shape": [1], "data_offsets": [0, 1]},
            "b": {"dtype": "U8", "shape": [1], "data_offsets": [1, 2]},
        }
        write_shard(self.shard, self.header)

    def read(self):
        return inventory.safetensors_inventory(self.root, cache=self.cache)

    def test_exact_legacy_result_including_source_receipt_and_header_hash(self) -> None:
        expected = launcher.safetensors_inventory(self.root)
        self.assertEqual(self.read(), expected)
        self.assertEqual(self.read(), expected)
        valid, tensors, manifest = self.read()
        self.assertTrue(valid)
        self.assertEqual(tensors["a"]["shape"], [1])
        raw_header = json.dumps(self.header, separators=(",", ":")).encode()
        self.assertEqual(manifest[0]["header_sha256"], hashlib.sha256(raw_header).hexdigest())

    def test_warm_read_skips_only_decoding_and_freshly_reads_the_header(self) -> None:
        expected = self.read()
        with mock.patch.object(inventory, "_decode_header", wraps=inventory._decode_header) as decoder, mock.patch.object(inventory.hashlib, "sha256", wraps=hashlib.sha256) as hashing:
            self.assertEqual(self.read(), expected)
        decoder.assert_not_called()
        hashing.assert_called_once()

    def test_returned_nested_structures_cannot_poison_cached_metadata(self) -> None:
        expected = self.read()
        _valid, tensors, manifest = self.read()
        tensors["a"]["shape"][0] = 999
        tensors["b"]["data_offsets"].clear()
        tensors.clear()
        manifest[0]["header_sha256"] = "untrusted"
        self.assertEqual(self.read(), expected)

    def test_rewrite_with_preserved_size_and_mtime_revalidates_header(self) -> None:
        self.assertTrue(self.read()[0])
        before = self.shard.stat()
        changed = {**self.header, "b": {**self.header["b"], "data_offsets": [0, 1]}}
        write_shard(self.shard, changed)
        os.utime(self.shard, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(before.st_size, self.shard.stat().st_size)
        self.assertFalse(self.read()[0])

    def test_same_forged_identity_still_binds_to_current_header_digest(self) -> None:
        # Digest revalidation remains required even if a filesystem supplies
        # unchanged identity metadata for modified header bytes.
        forged = (1, 2, 3, 4, 5)
        encoded = json.dumps(self.header).encode()
        self.cache.validated(encoded, 2, hashlib.sha256(encoded).hexdigest(), forged)
        changed = {**self.header, "b": {**self.header["b"], "data_offsets": [0, 1]}}
        bad = json.dumps(changed).encode()
        with self.assertRaises(ValueError):
            self.cache.validated(bad, 2, hashlib.sha256(bad).hexdigest(), forged)

    def test_atomic_replacement_never_reuses_old_source_identity(self) -> None:
        before = self.read()
        replacement = self.root / "replacement"
        write_shard(replacement, self.header)
        replacement.replace(self.shard)
        after = self.read()
        self.assertTrue(after[0])
        self.assertNotEqual(before[2][0]["inode"], after[2][0]["inode"])
        with mock.patch.object(inventory, "_decode_header", wraps=inventory._decode_header) as decoder:
            write_shard(self.shard, self.header)
            self.assertTrue(self.read()[0])
        decoder.assert_called_once()

    def test_symlink_retarget_freshly_revalidates_target_and_link_receipt(self) -> None:
        original = self.root / "original.blob"
        self.shard.replace(original)
        self.shard.symlink_to(original.name)
        before = self.read()
        self.assertTrue(before[0])
        alternative = self.root / "alternative.blob"
        write_shard(alternative, {"different": {"dtype": "U8", "shape": [2], "data_offsets": [0, 2]}})
        self.shard.unlink()
        self.shard.symlink_to(alternative.name)
        after = self.read()
        self.assertTrue(after[0])
        self.assertEqual(set(after[1]), {"different"})
        self.assertEqual(after[2][0]["link_target"], alternative.name)
        self.assertNotEqual(before[2][0]["inode"], after[2][0]["inode"])

    def test_source_swap_during_header_read_fails_closed(self) -> None:
        self.assertTrue(self.read()[0])
        replacement = self.root / "replacement"
        write_shard(replacement, self.header)
        original_fstat = inventory.os.fstat
        calls = 0

        def replace_on_after(fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                replacement.replace(self.shard)
            return original_fstat(fd)

        with mock.patch.object(inventory.os, "fstat", side_effect=replace_on_after):
            self.assertFalse(self.read()[0])

    def test_index_is_rechecked_even_when_all_headers_are_cached(self) -> None:
        self.shard.unlink()
        first = self.root / "model-00001-of-00002.safetensors"
        second = self.root / "model-00002-of-00002.safetensors"
        write_shard(first, {"a": self.header["a"]}, 1)
        write_shard(second, {"b": {**self.header["b"], "data_offsets": [0, 1]}}, 1)
        index = self.root / "model.safetensors.index.json"
        index.write_text(json.dumps({"weight_map": {"a": first.name, "b": second.name}}))
        self.assertTrue(self.read()[0])
        index.write_text(json.dumps({"weight_map": {"a": second.name, "b": first.name}}))
        with mock.patch.object(inventory, "_decode_header", wraps=inventory._decode_header) as decoder:
            self.assertFalse(self.read()[0])
        decoder.assert_not_called()

    def test_added_removed_and_auxiliary_shards_are_discovered_freshly(self) -> None:
        self.assertTrue(self.read()[0])
        write_shard(self.root / "auxiliary.safetensors", self.header)
        self.assertTrue(self.read()[0])
        duplicate = self.root / "model-duplicate.safetensors"
        write_shard(duplicate, self.header)
        self.assertFalse(self.read()[0])
        duplicate.unlink()
        self.assertTrue(self.read()[0])
        self.shard.unlink()
        self.assertFalse(self.read()[0])

    def test_missing_index_remains_supported_but_malformed_present_index_fails_closed(self) -> None:
        self.assertTrue(self.read()[0])
        index = self.root / "model.safetensors.index.json"
        malformed = [
            b'{"weight_map":', b'{"weight_map":{},"weight_map":{"a":"model.safetensors"}}',
            b'{}', b'{"weight_map":{}}', b'{"weight_map":[]}', b'[]',
        ]
        for document in malformed:
            with self.subTest(document=document):
                index.write_bytes(document)
                self.assertEqual(self.read(), (False, {}, []))
                self.assertEqual(launcher.safetensors_inventory(self.root), (False, {}, []))
        index.unlink()
        self.assertTrue(self.read()[0])
        index.symlink_to("missing-index.blob")
        self.assertEqual(self.read(), (False, {}, []))

    def test_controller_wrapper_preserves_current_index_reader_injection(self) -> None:
        index = self.root / "model.safetensors.index.json"
        index.write_text(json.dumps({"weight_map": {"a": self.shard.name, "b": self.shard.name}}))
        self.assertTrue(launcher.safetensors_inventory(self.root)[0])
        with mock.patch.object(launcher, "_bounded_strict_json_file", return_value=({}, {})) as reader:
            self.assertFalse(launcher.safetensors_inventory(self.root)[0])
        reader.assert_called_once_with(index)

    def test_byte_layout_duplicate_keys_and_invalid_types_fail_closed(self) -> None:
        cases = [
            ({**self.header, "b": {**self.header["b"], "data_offsets": [0, 1]}}, 2),
            ({**self.header, "b": {**self.header["b"], "data_offsets": [2, 3]}}, 3),
            (self.header, 3),
            ({"a": {"dtype": [], "shape": [1], "data_offsets": [0, 1]}}, 1),
            ({"a": {"dtype": "U8", "shape": [True], "data_offsets": [0, 1]}}, 1),
            ({"a": {"dtype": "U8", "shape": [0], "data_offsets": [0, 1]}}, 1),
            ({"a": {"dtype": "U8", "shape": [2**1000] * 1000, "data_offsets": [0, 1]}}, 1),
            (b'{"a":{"dtype":"U8","shape":[1],"data_offsets":[0,1]},"a":{}}', 1),
        ]
        for header, payload in cases:
            with self.subTest(header_type=type(header).__name__, payload=payload):
                write_shard(self.shard, header, payload)
                self.assertEqual(self.read(), (False, {}, []))

    def test_cache_retention_is_bounded_and_can_be_disabled(self) -> None:
        cache = inventory.HeaderCache(maximum_entries=1, maximum_bytes=1)
        with mock.patch.object(inventory, "_decode_header", wraps=inventory._decode_header) as decoder:
            self.assertTrue(inventory.safetensors_inventory(self.root, cache=cache)[0])
            self.assertTrue(inventory.safetensors_inventory(self.root, cache=cache)[0])
        self.assertEqual(decoder.call_count, 2)
        self.assertEqual(cache._bytes, 0)
        self.assertEqual(len(cache._entries), 0)
        cache = inventory.HeaderCache(maximum_entries=1)
        self.assertTrue(inventory.safetensors_inventory(self.root, cache=cache)[0])
        write_shard(self.shard, {"new": {"dtype": "U8", "shape": [2], "data_offsets": [0, 2]}})
        self.assertTrue(inventory.safetensors_inventory(self.root, cache=cache)[0])
        self.assertEqual(len(cache._entries), 1)
        self.assertLessEqual(cache._bytes, cache.maximum_bytes)
        cache.clear()
        self.assertEqual(cache._bytes, 0)

    def test_uncached_and_cached_paths_produce_identical_receipts(self) -> None:
        uncached = inventory.safetensors_inventory(self.root, cache=None)
        self.assertEqual(self.read(), uncached)
        self.assertEqual(self.read(), uncached)

    def test_strict_json_reader_preserves_receipt_and_rejects_duplicates_limits_and_nonobjects(self) -> None:
        config = self.root / "config.json"
        config.write_text('{"config":{"model_type":"qwen"}}')
        expected = launcher._bounded_strict_json_file(config)
        self.assertEqual(inventory.bounded_strict_json_file(config), expected)
        for value, limit in [(b'{"a":1,"a":2}', 100), (b'[]', 100), (b'{"a":1}', 2)]:
            config.write_bytes(value)
            self.assertEqual(inventory.bounded_strict_json_file(config, limit), ({}, {}))


if __name__ == "__main__":
    unittest.main()
