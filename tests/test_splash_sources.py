"""Local Splash loader contracts: split identity, native checks and preparation."""
from __future__ import annotations

import contextlib
import json
import pathlib
import sys
import tempfile
import types
import unittest
from unittest import mock

import splash_sources


class ModelError(RuntimeError):
    pass


class VisionError(ModelError):
    pass


class LocalLoaderFixture:
    """Small release-loader boundary, with real files and split snapshot links."""

    def __init__(self, root):
        self.root = root
        self.snapshot = root / "snapshots" / "commit"
        self.snapshot.mkdir(parents=True)
        self.parts = [self.snapshot / f"Flash-Q2_0-{n:05d}-of-00002.gguf" for n in (1, 2)]
        blobs = root / "blobs"
        blobs.mkdir()
        for n, (part, size) in enumerate(zip(self.parts, (256, 160))):
            blob = blobs / str(n)
            blob.write_bytes(bytes(size))
            part.symlink_to(blob)
        self.config = {"model_type": "qwen4_exp", "text_config": {
            "max_position_embeddings": 262144, "hidden_size": 2048,
            "num_hidden_layers": 4, "num_key_value_heads": 2, "head_dim": 256,
        }}
        self.family = types.SimpleNamespace(name="Qwen3.8-Flash-Next",
                                            draft_repo="incoai/Qwen3.8-Flash-Next-DFlash2")
        self.inspections = []
        self.api = types.SimpleNamespace(_inspect=self.inspect,
                                         prepare_local_model=mock.Mock())
        self.hub = types.SimpleNamespace(
            Repository=types.SimpleNamespace(resolve=mock.Mock()),
            as_model_errors=lambda _: contextlib.nullcontext(),
        )
        self.upstream = types.SimpleNamespace(draft_files=mock.Mock())
        fixture = self

        class Metadata:
            def __init__(self, path, tensors=False):
                self.values = {"general.architecture": "qwen4exp", "general.alignment": 32,
                               "qwen4exp.full_attention_interval": 4,
                               "qwen4exp.expert_count": 512, "qwen4exp.expert_used_count": 10}
                self.consumed = 32
                self.tensors = ({"token_embd.weight": 1, "blk.0.ffn_up_exps.weight": 42}
                                if pathlib.Path(path) == fixture.parts[0] else
                                {"per_layer_token_embd.weight": 20, "output.weight": 42})
                self.offsets = dict(zip(self.tensors, (0, 64)))

        def merged(headers):
            first = headers[0]
            first.tensors = {name: kind for h in headers for name, kind in h.tensors.items()}
            return first

        self.gguf = types.SimpleNamespace(
            Metadata=Metadata, merged_split=merged, loaded_tensors=lambda m: m.tensors,
            loaded_layers=lambda m, a: 4, text_architecture=lambda m: "qwen4exp",
            TENSOR_TYPES={1: "F16", 20: "IQ4_NL", 42: "Q2_0"},
        )
        self.models = types.SimpleNamespace(ModelError=ModelError, VisionError=VisionError)
        package = types.ModuleType("install")
        package.__path__ = []
        for name in ("models", "gguf", "hub", "upstream"):
            setattr(package, name, getattr(self, name))
        self.modules = {"install": package, "install.local": self.api}

    def inspect(self, path, mmproj, language_only, scratch):
        self.inspections.append((path, language_only, scratch))
        if not all(part.is_file() for part in self.parts):
            raise ModelError("the split GGUF is missing a part")
        config = scratch / "config.json"
        config.write_text(json.dumps(self.config))
        repo = types.SimpleNamespace(paths={p.name: p for p in self.parts})
        target = types.SimpleNamespace(
            config=config, family=self.family, format="gguf", vision_format="none",
            files={"target/" + p.name: p.name for p in self.parts},
        )
        return repo, target


class SplashSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name).resolve()
        self.fixture = LocalLoaderFixture(self.root)
        patch = mock.patch.dict(sys.modules, self.fixture.modules)
        patch.start()
        self.addCleanup(patch.stop)

    def test_split_snapshot_names_identity_and_native_storage_categories(self):
        fixture = self.fixture
        first = splash_sources.inspect_source(fixture.parts[0])
        second = splash_sources.inspect_source(fixture.parts[1])
        self.assertEqual(first, second)
        self.assertEqual(first["path"], str(fixture.parts[0]))
        self.assertEqual(first["name"], "Flash-Q2_0")
        self.assertEqual(first["targetBytes"], 416)
        self.assertEqual(first["tensorTypes"], {"F16": 1, "IQ4_NL": 1, "Q2_0": 2})
        self.assertEqual(first["quantization"], "Q2_0")
        self.assertEqual(first["expertBytes"], 160)
        self.assertEqual(first["pleBytes"], 64)
        self.assertEqual(first["plePrecision"], "IQ4_NL")
        self.assertEqual(first["residentTensorBytes"], 128)
        self.assertEqual(first["expertCount"], 512)
        self.assertEqual(first["expertsPerToken"], 10)
        self.assertEqual(first["attentionLayers"], 1)
        self.assertTrue(first["streaming"])
        self.assertEqual(first["draftRepo"], fixture.family.draft_repo)
        fixture.hub.Repository.resolve.assert_not_called()
        fixture.api.prepare_local_model.assert_not_called()
        self.assertEqual(sorted(p.name for p in fixture.snapshot.iterdir()), [p.name for p in fixture.parts])
        self.assertTrue(all(not item[2].exists() for item in fixture.inspections))

    def test_every_split_part_contributes_to_identity_and_incomplete_split_is_refused(self):
        source = splash_sources.inspect_source(self.fixture.parts[0])
        with self.fixture.parts[1].open("ab") as handle:
            handle.write(b"more")
        changed = splash_sources.inspect_source(self.fixture.parts[0])
        self.assertNotEqual(source["identity"], changed["identity"])
        self.fixture.parts[1].unlink()
        with self.assertRaisesRegex(ModelError, "missing a part"):
            splash_sources.inspect_source(self.fixture.parts[0])

    def test_native_refusal_is_preserved(self):
        self.fixture.api._inspect = mock.Mock(side_effect=ModelError("Flash-Next MLX is unsupported"))
        with self.assertRaisesRegex(ModelError, "Flash-Next MLX is unsupported"):
            splash_sources.inspect_source(self.fixture.parts[0])
        self.fixture.hub.Repository.resolve.assert_not_called()

    def test_a_split_part_changed_while_headers_are_read_is_refused(self):
        original = self.fixture.inspect
        def inspect(*args):
            result = original(*args)
            with self.fixture.parts[1].open("ab") as handle:
                handle.write(b"racing-write")
            return result
        self.fixture.api._inspect = inspect
        with self.assertRaisesRegex(ModelError, "changed during inspection"):
            splash_sources.inspect_source(self.fixture.parts[0])

    def test_incomplete_vision_retries_native_language_only_inspection(self):
        original = self.fixture.inspect
        def inspect(path, mmproj, language_only, scratch):
            if not language_only:
                raise VisionError("no vision tower")
            return original(path, mmproj, language_only, scratch)
        self.fixture.api._inspect = mock.Mock(side_effect=inspect)
        source = splash_sources.inspect_source(self.fixture.parts[0])
        self.assertEqual(source["visionFormat"], "none")
        self.assertEqual(self.fixture.api._inspect.call_count, 2)

    def test_preparation_reuses_local_draft_and_reprepares_on_every_launch(self):
        fixture = self.fixture
        source = splash_sources.inspect_source(fixture.parts[0])
        fixture.api.prepare_local_model.return_value = self.root / "prepared"
        destination = self.root / "assemblies"
        draft = self.root / "draft"
        for _ in range(2):
            self.assertEqual(splash_sources.prepare_source(source, destination, [str(draft)]),
                             self.root / "prepared")
        self.assertEqual(fixture.api.prepare_local_model.call_count, 2)
        fixture.api.prepare_local_model.assert_called_with(
            fixture.parts[0], draft=str(draft), language_only=True, models_dir=destination)
        fixture.hub.Repository.resolve.assert_not_called()

    def test_missing_draft_downloads_only_matching_family_then_uses_public_api(self):
        fixture = self.fixture
        source = splash_sources.inspect_source(fixture.parts[0])
        fixture.api.prepare_local_model.side_effect = [
            ModelError("draft is incompatible"), ModelError("no cached draft"), self.root / "prepared"]
        repository = fixture.hub.Repository.resolve.return_value
        draft = self.root / "downloaded-draft"
        fixture.upstream.draft_files.return_value = {"draft/config.json": draft / "config.json"}
        self.assertEqual(splash_sources.prepare_source(source, self.root / "assemblies", ["wrong-draft"]),
                         self.root / "prepared")
        fixture.hub.Repository.resolve.assert_called_once_with(source["draftRepo"])
        self.assertIs(fixture.upstream.draft_files.call_args.args[0], repository)
        fixture.api.prepare_local_model.assert_called_with(
            fixture.parts[0], draft=draft, language_only=True, models_dir=self.root / "assemblies")

    def test_changed_source_is_refused_before_preparation(self):
        source = splash_sources.inspect_source(self.fixture.parts[0])
        with self.fixture.parts[1].open("ab") as handle:
            handle.write(b"changed")
        with self.assertRaisesRegex(ModelError, "changed after scanning"):
            splash_sources.prepare_source(source, self.root / "assemblies", [])
        self.fixture.api.prepare_local_model.assert_not_called()

    def test_release_without_local_api_keeps_legacy_inspection_and_preparation(self):
        with mock.patch.object(splash_sources, "local_api", return_value=None), \
                mock.patch.object(splash_sources, "inspect_legacy_source", return_value={"legacy": True}) as inspect, \
                mock.patch.object(splash_sources, "prepare_legacy_source", return_value=self.root) as prepare:
            self.assertEqual(splash_sources.inspect_source(self.root), {"legacy": True})
            self.assertEqual(splash_sources.prepare_source({"path": "old"}, self.root, []), self.root)
            inspect.assert_called_once_with(self.root)
            prepare.assert_called_once_with({"path": "old"}, self.root, [])

    def test_current_mlx_quantization_labels_preserve_new_formats(self):
        self.assertEqual(splash_sources._mlx_quantization({"quantization": {"bits": 8, "group_size": 32}}),
                         "8-bit affine · group 32")
        self.assertEqual(splash_sources._mlx_quantization({"quantization": {"mode": "nvfp4"}}), "nvfp4")


if __name__ == "__main__":
    unittest.main()
