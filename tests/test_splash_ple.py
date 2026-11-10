"""Lossless main weights and independent cloned PLE header replacement."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest import mock

import splash_ple as ple


SHAPE = (32, 2)


def array_entry(key, kind, values):
    data = (b"".join(ple.gguf_string(value) for value in values) if kind == 8 else
            struct.pack("<" + ple.SCALARS[kind] * len(values), *values))
    return {"key": key, "kind": 9, "value": list(values), "raw":
            ple.gguf_string(key) + struct.pack("<IIQ", 9, kind, len(values)) + data}


def schema():
    prefix = "qwen4exp.ple."
    scalar = {"ngram_size": 3, "heads_per_ngram": 8, "conv_kernel": 4,
              "eos_token_id": 248044, "image_token_id": 248056}
    result = [ple.entry("general.architecture", 8, "qwen4exp"),
              ple.entry("general.alignment", 4, 32),
              ple.entry("general.name", 8, "Fixture model: metadata remains intact")]
    result += [ple.entry(prefix + key, 4, value) for key, value in scalar.items()]
    result += [array_entry(prefix + "layers", 4, [1]),
               array_entry(prefix + "layer_multipliers", 10, [23703573157769, 20109073645365, 8052911324071]),
               array_entry(prefix + "head_offsets", 10, [0, 20, 40]),
               array_entry(prefix + "head_vocab_sizes", 10, [20, 20, 24]),
               array_entry("tokenizer.ggml.tokens", 8, ["one", "two", "<|end|>"])]
    return result


def write_gguf(path, entries, specs):
    tensors, payloads, offset = [], [], 0
    for name, kind, dims, payload in specs:
        tensors.append({"name": name, "type": kind, "dims": list(dims), "offset": offset})
        payloads.append((offset, payload))
        offset = ple.align(offset + len(payload), 32)
    header = ple.encode_header(entries, tensors, 32)
    with path.open("wb") as handle:
        handle.write(header)
        handle.truncate(len(header) + offset)
        for start, payload in payloads:
            handle.seek(len(header) + start)
            handle.write(payload)
    return path


class SplashPleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.sources = []
        for number in range(2):
            entries = schema() + [ple.entry("split.no", 2, number), ple.entry("split.count", 2, 2),
                                  ple.entry("split.tensors.count", 5, 3)]
            specs = ([(ple.PLE, 20, SHAPE, b"p" * 36),
                      ("blk.0.ffn_up_exps.weight", 12, (256,), b"q" * 144)] if number == 0 else
                     [("blk.1.ffn_down_exps.weight", 14, (256,), b"r" * 210)])
            self.sources.append(write_gguf(self.root / f"Model-Q4_K_M-{number + 1:05d}-of-00002.gguf", entries, specs))
        self.replacement = write_gguf(self.root / "PLE-BF16.gguf", schema(),
                                      [(ple.PLE, ple.BF16, SHAPE, b"b" * 128)])
        self.output = self.root / "prepared"
        self.clones = []

    def clone(self, source, destination):
        self.clones.append((source, destination))
        shutil.copyfile(source, destination)
        return "test-independent-copy"

    def build(self, **options):
        return ple.build_replacement(self.sources, self.replacement, self.output,
                                     cloner=self.clone, expected_shape=SHAPE, **options)

    def test_main_tensors_and_metadata_survive_and_bf16_payload_offset_does_not_move(self):
        before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in [*self.sources, self.replacement]}
        originals = [ple.Header(path) for path in self.sources]
        bf16 = ple.Header(self.replacement)
        receipt = self.build()
        outputs = [ple.Header(path) for path in receipt["outputPaths"]]
        self.assertEqual(len(outputs), 3)
        self.assertEqual(len(self.clones), 2)
        self.assertTrue(receipt["mainTensorParityVerified"])
        self.assertTrue(receipt["sourceChecksPassed"])
        self.assertEqual(receipt["mainTensorCount"], 2)
        self.assertEqual(receipt["plePrecision"], "BF16")
        self.assertEqual(outputs[1].data_offset, originals[1].data_offset)
        self.assertEqual(outputs[2].data_offset, bf16.data_offset)
        self.assertEqual(outputs[2].tensors[0]["absoluteOffset"], bf16.tensors[0]["absoluteOffset"])
        self.assertEqual(outputs[2].tensors[0]["type"], ple.BF16)
        self.assertEqual(outputs[2].tensors[0]["dims"], list(SHAPE))
        self.assertEqual(outputs[0].values["general.name"], originals[0].values["general.name"])
        self.assertEqual(outputs[0].values["tokenizer.ggml.tokens"], ["one", "two", "<|end|>"])
        for item in originals[0].entries:
            if not item["key"].startswith("split."):
                self.assertEqual(next(e["raw"] for e in outputs[0].entries if e["key"] == item["key"]), item["raw"])
        actual_names = []
        for number, header in enumerate(outputs):
            self.assertEqual(header.values["split.no"], number)
            self.assertEqual(header.values["split.count"], 3)
            self.assertEqual(header.values["split.tensors.count"], 3)
            actual_names += [tensor["name"] for tensor in header.tensors]
        self.assertCountEqual(actual_names, [ple.PLE, "blk.0.ffn_up_exps.weight", "blk.1.ffn_down_exps.weight"])
        self.assertEqual({str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in [*self.sources, self.replacement]}, before)
        self.assertEqual(json.loads((self.output / "receipt.json").read_text()), receipt)
        self.assertTrue(all(item["inputSha256"] == item["outputSha256"] for item in receipt["tensors"]))

    def test_first_shard_argument_finds_other_parts_and_plan_reads_no_payload(self):
        plan = ple.plan_replacement(self.sources[0], self.replacement, expected_shape=SHAPE)
        self.assertEqual(plan["outputShardCount"], 3)
        self.assertEqual(plan["copiedMainBytes"], 144)
        self.assertEqual(plan["parts"][-1]["sourceDataOffset"], plan["parts"][-1]["outputDataOffset"])
        self.assertFalse(self.output.exists())

    def test_mismatched_hash_schema_and_missing_required_key_are_refused(self):
        for mode in ("mismatch", "missing"):
            entries = schema()
            key = "qwen4exp.ple.layer_multipliers"
            entries = [item for item in entries if item["key"] != key]
            if mode == "mismatch":
                entries.append(array_entry(key, 10, [1, 2, 3]))
            write_gguf(self.replacement, entries, [(ple.PLE, ple.BF16, SHAPE, b"b" * 128)])
            with self.assertRaisesRegex(ple.PreparationError, "hashing schema"):
                self.build()
            self.assertFalse(self.output.exists())

    def test_wrong_dimensions_and_non_bf16_replacements_are_refused(self):
        for dims, kind, payload in (((32, 3), ple.BF16, b"b" * 192), (SHAPE, 20, b"p" * 36)):
            write_gguf(self.replacement, schema(), [(ple.PLE, kind, dims, payload)])
            with self.assertRaises(ple.PreparationError):
                self.build()
            self.assertFalse(self.output.exists())

    def test_duplicate_tensor_names_across_main_parts_are_refused(self):
        original = ple.Header(self.sources[1])
        write_gguf(self.sources[1], original.entries,
                   [("blk.0.ffn_up_exps.weight", 14, (256,), b"r" * 210)])
        with self.assertRaisesRegex(ple.PreparationError, "Duplicate tensor across"):
            self.build()

    def test_duplicate_metadata_keys_are_refused(self):
        write_gguf(self.replacement, [*schema(), ple.entry("general.architecture", 8, "qwen4exp")],
                   [(ple.PLE, ple.BF16, SHAPE, b"b" * 128)])
        with self.assertRaisesRegex(ple.PreparationError, "Duplicate or empty GGUF metadata key"):
            self.build()

    def test_truncated_payload_can_be_planned_as_headers_but_never_built(self):
        original = ple.Header(self.replacement)
        with self.replacement.open("r+b") as handle:
            handle.truncate(original.data_offset)
        plan = ple.plan_replacement(self.sources, self.replacement, header_only=True, expected_shape=SHAPE)
        self.assertTrue(plan["headerOnly"])
        with self.assertRaisesRegex(ple.PreparationError, "Truncated GGUF tensor payload"):
            self.build()

    def test_mutation_during_clone_prevents_publication_and_removes_staging(self):
        def mutate(source, destination):
            result = self.clone(source, destination)
            with source.open("ab") as handle:
                handle.write(b"changed")
            return result
        with self.assertRaisesRegex(ple.PreparationError, "Source changed"):
            ple.build_replacement(self.sources, self.replacement, self.output,
                                  cloner=mutate, expected_shape=SHAPE)
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob(".splash-ple-*")))

    def test_corrupted_clone_is_detected_by_output_tensor_hashes(self):
        def corrupt(source, destination):
            self.clone(source, destination)
            header = ple.Header(destination)
            with destination.open("r+b") as handle:
                handle.seek(header.tensors[0]["absoluteOffset"])
                handle.write(b"corrupted")
        with self.assertRaisesRegex(ple.PreparationError, "SHA-256 mismatch"):
            ple.build_replacement(self.sources, self.replacement, self.output,
                                  cloner=corrupt, expected_shape=SHAPE)
        self.assertFalse(self.output.exists())

    def test_hard_link_cloner_is_rejected_before_source_header_can_be_changed(self):
        before = self.sources[1].read_bytes()
        with self.assertRaisesRegex(ple.PreparationError, "independent regular file"):
            ple.build_replacement(self.sources, self.replacement, self.output,
                                  cloner=os.link, expected_shape=SHAPE)
        self.assertEqual(self.sources[1].read_bytes(), before)
        self.assertFalse(self.output.exists())

    def test_cloner_cannot_alias_a_different_original_input(self):
        before = self.replacement.read_bytes()
        def cross_link(source, destination):
            os.link(self.replacement, destination)
        with self.assertRaisesRegex(ple.PreparationError, "independent regular file"):
            ple.build_replacement(self.sources, self.replacement, self.output,
                                  cloner=cross_link, expected_shape=SHAPE)
        self.assertEqual(self.replacement.read_bytes(), before)

    def test_existing_or_symlink_output_is_never_overwritten(self):
        self.output.mkdir()
        sentinel = self.output / "important"
        sentinel.write_text("preserve")
        with self.assertRaisesRegex(ple.PreparationError, "new directory"):
            self.build()
        self.assertEqual(sentinel.read_text(), "preserve")
        sentinel.unlink()
        self.output.rmdir()
        self.output.symlink_to(self.root / "absent")
        with self.assertRaisesRegex(ple.PreparationError, "new directory"):
            self.build()

    def test_publication_does_not_replace_a_directory_created_during_verification(self):
        def race(event):
            if event["phase"] == "verify" and not self.output.exists():
                self.output.mkdir()
                (self.output / "important").write_text("preserve")
        with self.assertRaises(OSError):
            self.build(progress=race)
        self.assertEqual((self.output / "important").read_text(), "preserve")

    def test_low_disk_space_refuses_before_any_clones(self):
        with mock.patch.object(ple.shutil, "disk_usage", return_value=types_disk_usage(0)):
            with self.assertRaisesRegex(ple.PreparationError, "Insufficient disk space"):
                self.build()
        self.assertFalse(self.clones)

    def test_clone_requirement_and_guarded_copy_are_explicit(self):
        destination = self.root / "copied"
        with mock.patch.object(ple.sys, "platform", "linux"):
            with self.assertRaisesRegex(ple.PreparationError, "APFS cloning is required"):
                ple.clone_file(self.replacement, destination)
            self.assertFalse(destination.exists())
            with mock.patch.object(ple.shutil, "disk_usage", return_value=types_disk_usage(0)):
                with self.assertRaisesRegex(ple.PreparationError, "Insufficient disk space"):
                    ple.clone_file(self.replacement, destination, allow_copy=True)
            self.assertFalse(destination.exists())

    @unittest.skipUnless(ple.sys.platform == "darwin", "APFS clonefile is a macOS interface")
    def test_real_apfs_clones_have_independent_inodes_and_verified_payloads(self):
        receipt = ple.build_replacement(self.sources, self.replacement, self.output, expected_shape=SHAPE)
        self.assertEqual([record["method"] for record in receipt["outputs"]], ["repack", "apfs-clone", "apfs-clone"])
        self.assertTrue(receipt["mainTensorParityVerified"])
        self.assertNotEqual(Path(receipt["outputPaths"][-1]).stat().st_ino, self.replacement.stat().st_ino)


def types_disk_usage(free):
    return shutil._ntuple_diskusage(total=free, used=0, free=free)


if __name__ == "__main__":
    unittest.main()
