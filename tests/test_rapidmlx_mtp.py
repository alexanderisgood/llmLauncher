"""Header-only MTP discovery: trained tensors, native layouts and identity."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

import rapidmlx_mtp


def head_keys(family="qwen3_5", prefix=""):
    anchors = ({"pre_fc_norm_embedding.weight", "pre_fc_norm_hidden.weight",
                "fc_embedding.weight", "fc_hidden.weight"} if family == "qwen4_exp" else
               {"enorm.weight", "hnorm.weight", "eh_proj.weight", "norm.weight"} if family == "hy_v3" else
               {"pre_fc_norm_embedding.weight", "pre_fc_norm_hidden.weight", "fc.weight", "norm.weight"})
    return {prefix + key for key in anchors | {
        "layers.0.self_attn.q_proj.weight", "layers.0.mlp.gate_proj.weight"}}


def safetensors(path, keys, *, packed=False):
    header, offset = {}, 0
    for key in sorted(keys):
        header[key] = {"dtype": "U32" if packed and key.endswith(".weight") else "F32",
                       "shape": [1], "data_offsets": [offset, offset + 4]}
        offset += 4
    raw = json.dumps(header).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("<Q", len(raw)) + raw + bytes(offset))


class RapidMTPTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "Qwen3.8-27B-MLX-4bit"
        self.root.mkdir()
        self.config = {"model_type": "qwen3_5", "text_config": {"mtp_num_hidden_layers": 1}}
        (self.root / "config.json").write_text(json.dumps(self.config))

    def test_nested_sidecar_enables_qwen27_depth_three_without_process_or_tensor_reads(self):
        head = self.root / "mtp/model.safetensors"
        safetensors(head, head_keys())
        with mock.patch("subprocess.Popen", side_effect=AssertionError("MTP discovery started a process")):
            found = rapidmlx_mtp.inspect_mtp(self.root, self.config)
        self.assertTrue(found["supported"], found["reason"])
        self.assertEqual(found["sidecarPath"], str(head))
        self.assertEqual(found["depth"], 3)
        self.assertEqual(found["depthChoices"], [1, 2, 3, 4, 5, 6])
        self.assertIn(str(head), found["files"])

    def test_config_and_filename_alone_do_not_claim_a_trained_predictor(self):
        safetensors(self.root / "mtp.safetensors", {"model.layers.0.self_attn.q_proj.weight"})
        found = rapidmlx_mtp.inspect_mtp(self.root, self.config)
        self.assertFalse(found["supported"])
        self.assertIn("missing trained head", found["reason"])
        self.assertFalse(rapidmlx_mtp.inspect_mtp(self.root, {"model_type": "flint"})["supported"])
        self.assertFalse(rapidmlx_mtp.inspect_mtp(self.root, {
            "model_type": "qwen3_5", "text_config": {"mtp_num_hidden_layers": 0}})["supported"])

    def test_integrated_qwen_head_passes_one_explicit_file_to_single_file_injector(self):
        keys = head_keys(prefix="mtp.")
        safetensors(self.root / "model-00001.safetensors", keys | {"model.embed_tokens.weight"})
        index = {key: "model-00001.safetensors" for key in keys}
        (self.root / "model.safetensors.index.json").write_text(json.dumps({"weight_map": index}))
        found = rapidmlx_mtp.inspect_mtp(self.root, self.config)
        self.assertTrue(found["supported"], found["reason"])
        self.assertEqual(found["sidecarPath"], str(self.root / "model-00001.safetensors"))
        self.assertIn(str(self.root / "model.safetensors.index.json"), found["files"])

    def test_qwen4_integrated_multiple_shards_use_target_root_and_native_depth_choices(self):
        config = {"model_type": "qwen4_exp", "text_config": {"mtp_num_hidden_layers": 1}}
        keys = sorted(head_keys("qwen4_exp", "mtp."))
        index = {}
        for number, group in enumerate((keys[:3], keys[3:])):
            name = f"model-{number:05}.safetensors"
            safetensors(self.root / name, group)
            index.update({key: name for key in group})
        (self.root / "model.safetensors.index.json").write_text(json.dumps({"weight_map": index}))
        found = rapidmlx_mtp.inspect_mtp(self.root, config)
        self.assertTrue(found["supported"], found["reason"])
        self.assertEqual(found["sidecarPath"], str(self.root))
        self.assertEqual(found["depth"], 1)
        self.assertEqual(found["depthChoices"], [1, 2])
        # A Qwen3.5 injector cannot consume a set of head shards as a directory.
        found = rapidmlx_mtp.inspect_mtp(self.root, self.config, index)
        self.assertFalse(found["supported"])
        self.assertIn("one safetensors file", found["reason"])

    def test_flash_index_missing_head_and_payload_truncation_are_rejected(self):
        config = {"model_type": "qwen4_exp", "text_config": {"mtp_num_hidden_layers": 1}}
        keys = head_keys("qwen4_exp", "mtp.")
        target = self.root / "model.safetensors"
        safetensors(target, keys)
        index = {key: target.name for key in keys | {"mtp.absent.weight"}}
        found = rapidmlx_mtp.inspect_mtp(self.root, config, index)
        self.assertFalse(found["supported"])
        self.assertIn("missing head tensors", found["reason"])
        target.write_bytes(target.read_bytes()[:-1])
        found = rapidmlx_mtp.inspect_mtp(self.root, config)
        self.assertFalse(found["supported"])
        self.assertIn("truncated", found["reason"])

    def test_packed_head_needs_affine_companions_and_complete_blocks(self):
        target = self.root / "mtp.safetensors"
        keys = head_keys()
        safetensors(target, keys, packed=True)
        found = rapidmlx_mtp.inspect_mtp(self.root, self.config)
        self.assertFalse(found["supported"])
        self.assertIn("scales or biases", found["reason"])
        all_keys = keys | {key.removesuffix(".weight") + suffix for key in keys
                           for suffix in (".scales", ".biases")}
        safetensors(target, all_keys, packed=True)
        self.assertTrue(rapidmlx_mtp.inspect_mtp(self.root, self.config)["supported"])
        safetensors(target, {key for key in keys if ".mlp." not in key})
        self.assertFalse(rapidmlx_mtp.inspect_mtp(self.root, self.config)["supported"])

    def test_hy3_uses_its_own_head_schema_and_requires_exactly_one_layer(self):
        target = self.root / "model-mtp.safetensors"
        safetensors(target, head_keys("hy_v3", "mtp."))
        config = {"model_type": "hy_v3", "num_nextn_predict_layers": 1}
        found = rapidmlx_mtp.inspect_mtp(self.root, config)
        self.assertTrue(found["supported"], found["reason"])
        self.assertEqual(found["depth"], 1)
        self.assertFalse(rapidmlx_mtp.inspect_mtp(self.root, {**config, "num_nextn_predict_layers": 2})["supported"])

    def test_paths_cannot_escape_and_training_contract_is_part_of_identity(self):
        outside = self.root.parent / "outside.safetensors"
        safetensors(outside, head_keys(prefix="mtp."))
        index = {key: "../outside.safetensors" for key in head_keys(prefix="mtp.")}
        self.assertFalse(rapidmlx_mtp.inspect_mtp(self.root, self.config, index)["supported"])
        head = self.root / "mtp.safetensors"
        safetensors(head, head_keys())
        contract = self.root / "mtplx_runtime.json"
        contract.write_text('{"base_hidden_variant":"post_norm"}')
        before = rapidmlx_mtp.inspect_mtp(self.root, self.config)
        contract.write_text('{"base_hidden_variant":"pre_norm"}')
        after = rapidmlx_mtp.inspect_mtp(self.root, self.config)
        self.assertTrue(before["supported"])
        self.assertIn(str(contract), before["files"])
        self.assertNotEqual(before["signatures"], after["signatures"])

    def test_hugging_face_snapshot_weight_symlink_keeps_lexical_native_path(self):
        blob = self.root.parent / "blobs" / "aabbcc"
        keys = head_keys(prefix="mtp.")
        safetensors(blob, keys)
        linked = self.root / "model-00001.safetensors"
        linked.symlink_to(blob)
        index = {key: linked.name for key in keys}
        found = rapidmlx_mtp.inspect_mtp(self.root, self.config, index)
        self.assertTrue(found["supported"], found["reason"])
        self.assertEqual(found["sidecarPath"], str(linked))
        signature = next(item for item in found["signatures"] if item["path"] == str(linked))
        self.assertEqual(signature["inode"], blob.stat().st_ino)
        for invalid in (str(blob), "../blobs/aabbcc", "unused/../model-00001.safetensors"):
            with self.subTest(invalid=invalid):
                self.assertFalse(rapidmlx_mtp.inspect_mtp(self.root, self.config,
                    {key: invalid for key in keys})["supported"])


if __name__ == "__main__":
    unittest.main()
