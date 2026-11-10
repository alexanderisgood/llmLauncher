"""Byte-exact SSD planning tests; no checkpoint or native MLX import required."""
from __future__ import annotations

import copy
import dataclasses
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


VENDOR = Path(__file__).resolve().parents[1] / "runtime_patches/kolibri/streamlx"
PACKAGE = "_launcher_kolibri_reader_tests"


def load_reader():
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(VENDOR)]
    sys.modules[PACKAGE] = package
    index_spec = importlib.util.spec_from_file_location(f"{PACKAGE}.stindex", VENDOR / "stindex.py")
    index = importlib.util.module_from_spec(index_spec)
    sys.modules[index_spec.name] = index
    index_spec.loader.exec_module(index)
    reader_spec = importlib.util.spec_from_file_location(f"{PACKAGE}.reader", VENDOR / "reader.py")
    reader = importlib.util.module_from_spec(reader_spec)
    sys.modules[reader_spec.name] = reader
    # Range planning and raw byte reads need neither NumPy nor MLX arrays.
    # Stub just the import-time dtype names; tensor conversion remains untouched.
    core = types.ModuleType("mlx.core")
    core.bfloat16 = "bf16"
    mlx = types.ModuleType("mlx"); mlx.core = core
    numpy = types.ModuleType("numpy")
    for name in ("uint32", "uint16", "float16", "float32"):
        setattr(numpy, name, name)
    with mock.patch.dict(sys.modules, {"mlx": mlx, "mlx.core": core, "numpy": numpy}):
        reader_spec.loader.exec_module(reader)
    return index, reader


index, reader = load_reader()


class TensorGeometryTests(unittest.TestCase):
    def test_all_supported_tensor_precisions_address_the_exact_expert_row(self):
        for dtype, scalar_bytes in index.DTYPE_SIZE.items():
            with self.subTest(dtype=dtype):
                loc = index.TensorLoc("shard", 127, 384 * 512 * 24 * scalar_bytes,
                                      dtype, (384, 512, 24))
                stride = 512 * 24 * scalar_bytes
                self.assertEqual(loc.expert_range(0), ("shard", 127, stride))
                self.assertEqual(loc.expert_range(383), ("shard", 127 + 383 * stride, stride))
                cloned = copy.deepcopy(loc)
                self.assertEqual(cloned.expert_range(137), ("shard", 127 + 137 * stride, stride))
                with self.assertRaises(dataclasses.FrozenInstanceError):
                    loc.shape = (1, 2, 3)
                for invalid in (-1, 384):
                    with self.assertRaises(IndexError):
                        loc.expert_range(invalid)


class ExpertReadTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="kolibri-byte-fixture-")
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.fetch = reader.ExpertReader(None, workers=3, merge_gap=8, max_span=32)
        self.addCleanup(self.fetch.close)

    def test_coalescing_preserves_every_key_byte_range_gap_and_shard_boundary(self):
        first, second = self.root / "a", self.root / "b"
        first.write_bytes(bytes(range(128)))
        second.write_bytes(bytes(reversed(range(128))))
        requests = [("later",str(first),51,5), ("first",str(first),3,7),
                    ("adjacent",str(first),10,5), ("gap",str(first),20,4),
                    ("other",str(second),4,8), ("span-cap",str(first),30,8)]
        actual = self.fetch.read_ranges(requests)
        for key, path, offset, count in requests:
            self.assertEqual(bytes(actual[key]), Path(path).read_bytes()[offset:offset + count])
            self.assertEqual(len(actual[key]), count)
        plan = self.fetch._plan(requests)
        self.assertEqual(len(plan), 4)
        self.assertTrue(all(span[2] <= 32 for span in plan))
        self.assertEqual(self.fetch.reads, 4)
        self.assertEqual(self.fetch.useful_bytes, sum(item[3] for item in requests))
        self.assertEqual(self.fetch.bytes_read, sum(item[2] for item in plan))

    def test_large_coalesced_union_has_every_original_member_in_offset_order(self):
        requests = [(expert, "shard", expert * 8, 6) for expert in range(384)]
        plan = reader.ExpertReader.__new__(reader.ExpertReader)
        plan.merge_gap, plan.max_span = 2, 4096
        spans = plan._plan(reversed(requests))
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0][:3], ("shard",0,383 * 8 + 6))
        self.assertEqual(spans[0][3], [(expert,expert * 8,6) for expert in range(384)])

    def test_raw_expert_rows_keep_original_packed_bits_for_all_projection_parts(self):
        triples, expected = {}, {}
        payload = bytearray(b"metadata")
        for projection in index.PROJS:
            triples[projection] = {}
            for part in index.PARTS:
                dtype = "U32" if part == "weight" else "BF16"
                columns, scalar_bytes = (24,4) if part == "weight" else (2,2)
                stride = 2 * columns * scalar_bytes
                start = len(payload)
                for expert in range(6):
                    raw = bytes((len(payload) + offset) % 256 for offset in range(stride))
                    payload.extend(raw)
                    expected[(expert,projection,part)] = raw
                triples[projection][part] = index.TensorLoc(
                    str(self.root / "packed"),start,6 * stride,dtype,(6,2,columns))
        (self.root / "packed").write_bytes(payload)
        raw = self.fetch.read_experts_raw(triples,[5,0,3])
        self.assertEqual(set(raw), {(expert,p,q) for expert in (5,0,3)
                                  for p in index.PROJS for q in index.PARTS})
        for key,value in raw.items():
            self.assertEqual(bytes(value), expected[key])

    def test_truncated_weight_read_fails_and_a_repaired_shard_can_be_retried(self):
        shard = self.root / "short"
        shard.write_bytes(b"012345")
        with self.assertRaisesRegex(IOError, "short read"):
            self.fetch.read_ranges([("row",str(shard),2,8)])
        self.assertEqual(self.fetch.reads, 0)
        shard.write_bytes(b"0123456789")
        result = self.fetch.read_ranges([("row",str(shard),2,8)])
        self.assertEqual(bytes(result["row"]), b"23456789")
        self.assertEqual(self.fetch.reads, 1)


if __name__ == "__main__":
    unittest.main()
