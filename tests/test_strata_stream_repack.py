"""Prove streamed layout parity against Strata's actual pinned repacker."""
from copy import deepcopy
from contextlib import redirect_stdout
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace

from bench import strata_stream_repack as stream


def fixture(path, tensors, shard):
    def string(value):
        body = value.encode()
        return struct.pack("<Q", len(body)) + body

    metadata = [string("general.alignment") + struct.pack("<II", 4, 32),
                string("split.no") + struct.pack("<IH", 2, shard),
                string("general.name") + struct.pack("<I", 8) + string("tiny exact-layout fixture")]
    infos, data, offset = [], bytearray(), 0
    for name, dims, kind, raw in tensors:
        infos.append(string(name) + struct.pack("<I", len(dims)) +
                     struct.pack(f"<{len(dims)}Q", *dims) + struct.pack("<IQ", kind, offset))
        data.extend(raw)
        offset = (offset + len(raw) + 31) // 32 * 32
        data.extend(bytes(offset - len(data)))
    header = struct.pack("<4sIQQ", b"GGUF", 3, len(tensors), len(metadata)) + b"".join(metadata) + b"".join(infos)
    path.write_bytes(header + bytes((-len(header)) % 32) + data)


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repack = stream.upstream()
        first = self.root / "tiny-00001-of-00002.gguf"
        second = self.root / "tiny-00002-of-00002.gguf"
        fixture(first, [("token_embd.weight", (4, 2), 0, bytes(range(32))),
                        ("blk.0.ffn_down_exps.weight", (32, 2, 2), 7, bytes(range(96))),
                        (self.repack.PLE, (4, 3), 0, bytes(range(48)))], 0)
        fixture(second, [("blk.0.ffn_up_exps.weight", (256, 2, 2), 12, bytes(range(256)) * 2 + bytes(64)),
                         ("output_norm.weight", (4,), 0, bytes(range(16))),
                         ("blk.0.ffn_gate_exps.weight", (256, 2, 2), 12, bytes(576))], 1)
        self.paths = [first, second]
        self.readers = [self.repack.Reader(p) for p in self.paths]
        for index, reader in enumerate(self.readers):
            reader.source_index = index
        self.sources = [{"name": p.name, "size": p.stat().st_size,
                         "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in self.paths]
        for reader, source in zip(self.readers, self.sources):
            reader.prefix_bytes = source["size"]
            reader.prefix_sha256 = source["sha256"]

    def tearDown(self):
        for reader in self.readers:
            reader.f.close()
        self.temp.cleanup()

    def materialize(self, plan, name):
        output = self.root / name
        with output.open("w+b") as handle:
            handle.write(plan["header"])
            handle.truncate(plan["size"])
            for tensor in plan["tensors"]:
                source = tensor["src"].f
                source.seek(tensor["abs"])
                os.pwrite(handle.fileno(), source.read(tensor["bytes"]), plan["data"] + tensor["new"])
        return output

    def test_native_file_matches_official_repacker_byte_for_byte(self):
        plans = stream.plans(self.repack, self.readers, self.sources)
        mine = self.materialize(plans["native"], "streamed.gguf")
        official = self.root / "official.gguf"
        result = subprocess.run([sys.executable, str(stream.STRATA / "metal/tools/metal_repack.py"),
                                 "--shard1", str(self.paths[0]), "--out", str(official), "--verify"],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(mine.read_bytes(), official.read_bytes())
        self.assertEqual([t["name"] for t in plans["native"]["tensors"]],
                         ["token_embd.weight", "output_norm.weight", "blk.0.ffn_gate_exps.weight",
                          "blk.0.ffn_up_exps.weight", "blk.0.ffn_down_exps.weight"])

    def test_standalone_ple_preserves_original_tensor_and_metadata(self):
        plan = stream.plans(self.repack, self.readers, self.sources)["ple"]
        output = self.materialize(plan, "ple.gguf")
        reader = self.repack.Reader(output)
        try:
            self.assertEqual(len(reader.tensors), 1)
            tensor = reader.tensors[0]
            self.assertEqual((tensor["name"], tensor["dims"], tensor["type"]),
                             (self.repack.PLE, (4, 3), 0))
            self.assertEqual(self.repack.tensor_hash(reader.f, tensor["abs"], tensor["bytes"]),
                             hashlib.sha256(bytes(range(48))).hexdigest())
            self.assertEqual([key for key, _ in reader.kv], ["general.name", "general.alignment"])
            # Match NgramStore::open_gguf's exact payload-length contract,
            # including a table whose length is not a multiple of 16 KiB.
            self.assertEqual(output.stat().st_size - tensor["abs"], tensor["bytes"])
        finally:
            reader.f.close()

    def test_rejects_overlapping_or_out_of_bounds_source_intervals(self):
        tensor = self.readers[0].tensors[1]
        original = deepcopy({k: v for k, v in tensor.items() if k != "src"})
        tensor["abs"] = self.readers[0].tensors[0]["abs"]
        with self.assertRaisesRegex(ValueError, "overlapping"):
            stream.plans(self.repack, self.readers, self.sources)
        tensor.update(original)
        tensor["bytes"] = self.sources[0]["size"]
        with self.assertRaisesRegex(ValueError, "outside"):
            stream.plans(self.repack, self.readers, self.sources)

    def test_full_expert_identity_rejects_missing_layers_and_reduced_experts(self):
        outputs = stream.plans(self.repack, self.readers, self.sources)
        with self.assertRaises(ValueError):
            stream.expert_identity(outputs)
        identity = stream.expert_identity(outputs, expected_layers=1, expected_experts=2)
        self.assertEqual((identity["layers"], identity["expertsPerLayer"]), (1, 2))
        tensor = next(t for t in outputs["native"]["tensors"] if "ffn_gate_exps" in t["name"])
        tensor["dims"] = (*tensor["dims"][:-1], 1)
        with self.assertRaisesRegex(ValueError, "full-expert"):
            stream.expert_identity(outputs, expected_layers=1, expected_experts=2)

    def provider(self, source, start=0, corrupt=False):
        body = (self.root / source["name"]).read_bytes()
        if corrupt:
            body = body[:-1] + bytes([body[-1] ^ 1])
        result = io.BytesIO(body[start:])
        result.status = 206 if start else 200
        result.headers = {"Content-Length": str(len(body) - start)}
        if start:
            result.headers["Content-Range"] = f"bytes {start}-{len(body) - 1}/{len(body)}"
        return result

    def test_streamed_chunks_reconstruct_whole_sources_and_match_official_output(self):
        outputs = stream.plans(self.repack, self.readers, self.sources)
        work = self.root / "prepared"
        work.mkdir()
        with redirect_stdout(io.StringIO()), patch.object(stream, "CHUNK", 31):
            receipt = stream.download(work, self.repack, self.readers, outputs, self.sources, self.provider)
        expected = self.materialize(outputs["native"], "expected.gguf")
        self.assertEqual((work / "native.gguf").read_bytes(), expected.read_bytes())
        self.assertEqual(receipt["outputs"]["native"]["sha256"], hashlib.sha256(expected.read_bytes()).hexdigest())
        self.assertEqual([receipt["sourceProofs"][str(i)]["sha256"] for i in range(2)],
                         [source["sha256"] for source in self.sources])
        self.assertFalse((work / "native.gguf.part").exists())

    def test_corrupt_source_is_not_published_and_retry_reuses_only_verified_bytes(self):
        outputs = stream.plans(self.repack, self.readers, self.sources)
        work = self.root / "retry"
        work.mkdir()
        with redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "checksum"):
            stream.download(work, self.repack, self.readers, outputs, self.sources,
                            lambda source: self.provider(source, corrupt=source is self.sources[1]))
        self.assertFalse((work / "native.gguf").exists())
        self.assertFalse((work / "ple.gguf").exists())
        called = []

        def retry(source):
            called.append(source["name"])
            return self.provider(source)

        with redirect_stdout(io.StringIO()):
            receipt = stream.download(work, self.repack, self.readers, outputs, self.sources, retry)
        self.assertEqual(called, [self.sources[1]["name"]])
        self.assertEqual(receipt["status"], "verified")
        # A journal's claimed checksum cannot hide later tensor corruption.
        tensor = outputs["native"]["tensors"][0]
        with (work / "native.gguf").open("r+b") as handle:
            write_offset = outputs["native"]["data"] + tensor["new"]
            handle.seek(write_offset)
            handle.write(b"!")
        called.clear()
        with redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "Published model failed"):
            stream.download(work, self.repack, self.readers, outputs, self.sources, retry)
        self.assertEqual(called, [])

    def test_bounded_window_resumes_at_the_verified_prefix_without_retransmitting_it(self):
        outputs = stream.plans(self.repack, self.readers, self.sources)
        work = self.root / "bounded"
        work.mkdir()
        with redirect_stdout(io.StringIO()), patch.object(stream, "CHUNK", 31), \
             patch.object(stream.time, "monotonic", side_effect=[0, 0, 2]), \
             self.assertRaises(stream.PreparationPaused):
            stream.download(work, self.repack, self.readers, outputs, self.sources, self.provider, max_seconds=1)
        state = json.loads((work / "stream-state.json").read_text())
        self.assertEqual(state["active"]["position"], 31)
        self.assertFalse((work / "native.gguf").exists())
        called = []

        def resumed(source, start=0):
            called.append((source["name"], start))
            return self.provider(source, start)

        with redirect_stdout(io.StringIO()), patch.object(stream, "CHUNK", 31):
            receipt = stream.download(work, self.repack, self.readers, outputs, self.sources, resumed)
        self.assertEqual(called, [(self.sources[0]["name"], 31), (self.sources[1]["name"], 0)])
        self.assertEqual(receipt["status"], "verified")
        expected = self.materialize(outputs["native"], "expected-bounded.gguf")
        self.assertEqual((work / "native.gguf").read_bytes(), expected.read_bytes())

    def test_changed_partial_checkpoint_stops_before_another_network_request(self):
        outputs = stream.plans(self.repack, self.readers, self.sources)
        work = self.root / "changed-prefix"
        work.mkdir()
        with redirect_stdout(io.StringIO()), patch.object(stream, "CHUNK", 31), \
             patch.object(stream.time, "monotonic", side_effect=[0, 0, 2]), \
             self.assertRaises(stream.PreparationPaused):
            stream.download(work, self.repack, self.readers, outputs, self.sources, self.provider, max_seconds=1)
        with (work / "gap-0.bin").open("r+b") as handle:
            handle.write(b"!")
        provider = Mock(side_effect=AssertionError("must not fetch"))
        with self.assertRaisesRegex(ValueError, "durable checkpoint"):
            stream.download(work, self.repack, self.readers, outputs, self.sources, provider)
        provider.assert_not_called()
        self.assertFalse((work / "native.gguf").exists())

    def test_preexisting_file_and_disk_reserve_are_preserved(self):
        outputs = stream.plans(self.repack, self.readers, self.sources)
        work = self.root / "preserve"
        work.mkdir()
        sentinel = work / "native.gguf"
        sentinel.write_bytes(b"preserve existing data")
        with self.assertRaises(FileExistsError):
            stream.download(work, self.repack, self.readers, outputs, self.sources, self.provider)
        self.assertEqual(sentinel.read_bytes(), b"preserve existing data")
        self.assertFalse((work / "stream-state.json").exists())
        empty = self.root / "no-space"
        empty.mkdir()
        with patch.object(stream.shutil, "disk_usage", return_value=SimpleNamespace(free=0)), \
             self.assertRaisesRegex(OSError, "does not fit"):
            stream.download(empty, self.repack, self.readers, outputs, self.sources, self.provider)
        self.assertEqual(list(empty.iterdir()), [])


class RangeTests(unittest.TestCase):
    def test_source_pins_match_the_actual_pinned_upstream_setup(self):
        module = ast.parse((stream.STRATA / "setup.py").read_text())
        values = {}
        for node in module.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {"HF_REVISIONS", "UNSLOTH_SHARDS"}:
                        values[target.id] = ast.literal_eval(node.value)
        self.assertEqual(stream.REVISION, values["HF_REVISIONS"]["unsloth/Qwen3.8-Flash-Next-GGUF"])
        self.assertEqual({s["name"]: (s["size"], s["sha256"]) for s in stream.SOURCES}, values["UNSLOTH_SHARDS"])

    def test_bounded_range_and_complete_small_shard_checksum_are_required(self):
        source = {"name": "fixture.gguf", "size": 8, "sha256": hashlib.sha256(b"12345678").hexdigest()}

        def response(body, status, content_range=None):
            result = io.BytesIO(body)
            result.status = status
            result.headers = {"Content-Range": content_range} if content_range else {}
            return result

        with patch.object(stream.urllib.request, "urlopen", return_value=response(b"1234", 206, "bytes 0-3/8")):
            self.assertEqual(stream.prefix(source, 4), b"1234")
        for body, status, content_range, count in [(b"12345678", 200, None, 4),
                                                   (b"1234", 206, "bytes 1-4/8", 4),
                                                   (b"changed!", 200, None, 8)]:
            with self.subTest(status=status, count=count), \
                 patch.object(stream.urllib.request, "urlopen", return_value=response(body, status, content_range)):
                with self.assertRaises(ValueError):
                    stream.prefix(source, count)


if __name__ == "__main__":
    unittest.main()
