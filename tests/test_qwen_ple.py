from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import launcher
import qwen_ple
from tensor_inventory import bounded_strict_json_file, safetensors_inventory


def tiny_config() -> dict:
    return {
        "model_type": "qwen4_exp",
        "text_config": {
            "model_type": "qwen4_exp_text", "num_hidden_layers": 4,
            "hidden_size": 128, "vocab_size": 1024, "ple_embed_dim": 128,
            "ngram_size": 2, "heads_per_ngram": 2,
            "ngram_vocab_size_base": 1000,
            "make_ngram_vocab_size_divisible_by": 4, "split_ngram_parts": 2,
            "seed": 1234, "eos_token_id": [0, 1], "ple_layer_ids": [1, 2],
        },
    }


def checkpoint(root: Path, config: dict, affine: bool = False) -> None:
    geometry, error = qwen_ple._qwen4_ple_geometry(config)
    if error or not geometry:
        raise ValueError(error)
    tensors = {}
    offset = 0

    def add(name, dtype, shape, width):
        nonlocal offset
        elements = 1
        for value in shape:
            elements *= value
        end = offset + elements * width
        tensors[name] = {"dtype": dtype, "shape": shape, "data_offsets": [offset, end]}
        offset = end

    add("language_model.model.embed_tokens.weight", "BF16", [2, 128], 2)
    for layer in geometry["layers"]:
        prefix = f'language_model.model.layers.{layer["layerIndex"]}.ple.ple_embedding.ngram_embedding'
        for shard, rows in enumerate(layer["shardRows"]):
            base = f"{prefix}.shard_{shard}"
            if affine:
                add(base + ".weight", "U32", [rows, 8], 4)
                add(base + ".scales", "BF16", [rows, 2], 2)
                add(base + ".biases", "BF16", [rows, 2], 2)
            else:
                add(base + ".weight", "BF16", [rows, 64], 2)
    header = json.dumps(tensors, separators=(",", ":")).encode()
    shard = root / "model.safetensors"
    with shard.open("wb") as handle:
        handle.write(len(header).to_bytes(8, "little"))
        handle.write(header)
        handle.truncate(8 + len(header) + offset)
    (root / "config.json").write_text(json.dumps(config))
    (root / "model.safetensors.index.json").write_text(json.dumps({
        "weight_map": {name: shard.name for name in tensors},
    }))


class QwenPleTests(unittest.TestCase):
    def profile(self, root, config, ready=True, version="omlx 0.6.4", **overrides):
        dependencies = {
            "is_qwen_config": launcher.is_qwen4_exp_config,
            "version_at_least": launcher.omlx_version_at_least,
            "json_reader": bounded_strict_json_file,
            "inventory_reader": safetensors_inventory,
            "geometry_reader": qwen_ple._qwen4_ple_geometry,
        }
        dependencies.update(overrides)
        return qwen_ple.qwen4_ple_profile(root, config, ready, version, **dependencies)

    def test_geometry_matches_constructor_golden_vocabularies_and_layer_order(self) -> None:
        config = tiny_config()
        config["text_config"]["ple_layer_ids"] = [2, 1, 2]
        geometry, error = qwen_ple._qwen4_ple_geometry(config)
        self.assertEqual(error, "")
        self.assertEqual(geometry, {
            "vocabSize": 1024, "seed": 1234, "eosTokenIds": [0, 1],
            "pleEmbedDim": 128, "ngramHeads": 2, "shardWidth": 64, "splitParts": 2,
            "layers": [
                {"layerId": 1, "layerIndex": 0, "pleIndex": 0, "paddedVocabulary": 2024, "shardRows": [1012, 1012]},
                {"layerId": 2, "layerIndex": 1, "pleIndex": 1, "paddedVocabulary": 2040, "shardRows": [1020, 1020]},
            ],
        })

    def test_sequential_primes_are_identical_to_individual_nth_constructor_values(self) -> None:
        for start, count in [(1, 8), (99, 40), (19_999_999, 64), (2_147_483_646, 16)]:
            with self.subTest(start=start):
                self.assertEqual(
                    qwen_ple._qwen4_ple_primes_after(start, count),
                    [qwen_ple._qwen4_ple_nth_prime_after(start, index + 1) for index in range(count)],
                )

    def test_prime_predicate_rejects_known_strong_pseudoprimes(self) -> None:
        for composite in [0, 1, 561, 1105, 3_215_031_751, 341_550_071_728_321, 3_825_123_056_546_413_051]:
            self.assertFalse(qwen_ple._qwen4_ple_is_prime(composite))
        for prime in [2, 3, 1_009, 2_147_483_647, 18_446_744_073_709_551_557]:
            self.assertTrue(qwen_ple._qwen4_ple_is_prime(prime))

    def test_constructor_bounds_attention_contract_and_integer_types_are_preserved(self) -> None:
        changes = [
            ("hidden_size", True), ("seed", 2**63), ("eos_token_id", [1024]),
            ("ple_layer_ids", [0]), ("ple_layer_ids", [4]),
            ("ple_embed_dim", 127), ("ngram_size", 65),
            ("layer_types", ["unsupported"] * 4), ("split_ngram_parts", 4097),
        ]
        for key, value in changes:
            config = tiny_config()
            config["text_config"][key] = value
            with self.subTest(key=key, value=value):
                geometry, error = qwen_ple._qwen4_ple_geometry(config)
                self.assertIsNone(geometry)
                self.assertTrue(error)

    def test_extraction_preserves_full_dense_and_affine_profile_receipts(self) -> None:
        for affine in [False, True]:
            with self.subTest(affine=affine), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                config = tiny_config()
                checkpoint(root, config, affine)
                expected = launcher.qwen4_ple_profile(root, config, True, "omlx 0.6.4")
                actual = self.profile(root, config)
                self.assertEqual(actual, expected)
                self.assertTrue(actual["supported"])
                self.assertEqual(actual["pleLayouts"], ["affine-q4-g32" if affine else "dense-bf16"])
                self.assertEqual(actual["pleLayerCount"], 2)
                self.assertEqual(actual["pleShardCount"], 4)
                self.assertTrue(actual["inventoryFingerprint"])
                self.assertTrue(actual["sourceFingerprint"])
                self.assertEqual(self.profile(root, config), actual)

    def test_runtime_and_readiness_gates_fail_before_filesystem_reads(self) -> None:
        config = tiny_config()
        for ready, version, supplied_config in [(False, "omlx 0.6.4", config), (True, "omlx 0.6.3", config), (True, "omlx 0.6.4", {})]:
            reader = mock.Mock(side_effect=AssertionError("Should not read"))
            actual = self.profile(Path("/unused"), supplied_config, ready, version, json_reader=reader, inventory_reader=reader)
            self.assertFalse(actual["supported"])
            reader.assert_not_called()

    def test_exact_current_config_and_index_are_required_on_every_profile_call(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = tiny_config()
            checkpoint(root, config)
            self.assertTrue(self.profile(root, config)["supported"])
            changed = deepcopy(config)
            changed["text_config"]["seed"] = 999
            (root / "config.json").write_text(json.dumps(changed))
            self.assertFalse(self.profile(root, config)["supported"])
            (root / "config.json").write_text(json.dumps(config))
            (root / "model.safetensors.index.json").write_text('{"weight_map":{}}')
            self.assertFalse(self.profile(root, config)["supported"])

    def test_expert_offload_uses_explicit_runtime_and_current_inventory_dependencies(self) -> None:
        reader = mock.Mock(return_value=(False, {}, []))
        actual = qwen_ple.qwen4_expert_offload_profile(
            Path("/unused"), tiny_config(), {"supported": True}, "omlx 0.7.0.dev2",
            exact_version=launcher._exact_omlx_version, inventory_reader=reader,
        )
        self.assertFalse(actual["supported"])
        reader.assert_called_once_with(Path("/unused"))
        reader.reset_mock()
        actual = qwen_ple.qwen4_expert_offload_profile(
            Path("/unused"), tiny_config(), {"supported": True}, "omlx 0.7.0.dev3",
            exact_version=launcher._exact_omlx_version, inventory_reader=reader,
        )
        self.assertFalse(actual["supported"])
        reader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
