import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from model_modalities import pi_model_inputs, prepare_mtplx_image_processor


VISION = {"hidden_size": 1152, "patch_size": 16, "spatial_merge_size": 2,
          "temporal_patch_size": 2}
PROCESSOR = {"patch_size": 16, "merge_size": 2, "temporal_patch_size": 2,
             "size": {"shortest_edge": 65536, "longest_edge": 16777216},
             "do_rescale": True, "rescale_factor": 1 / 255,
             "do_normalize": True, "image_mean": [0.5] * 3, "image_std": [0.5] * 3,
             "image_processor_type": "Qwen2VLImageProcessor"}


class ModelModalitiesTests(unittest.TestCase):
    def artifact(self, root):
        (root / "config.json").write_text(json.dumps({"model_type": "qwen3_5", "vision_config": VISION}))
        (root / "model.safetensors.index.json").write_text(json.dumps({
            "weight_map": {"vision_tower.blocks.0.weight": "vision.safetensors"}}))
        (root / "vision.safetensors").write_bytes(b"fixture-weight-payload" * 2)
        (root / "processor_config.json").write_text(json.dumps({
            "image_processor": PROCESSOR, "processor_class": "Qwen3VLProcessor"}))

    def test_installed_tower_and_supported_serving_route_are_both_required(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "config.json").write_text(json.dumps({
                "model_type": "qwen3_5", "vision_config": VISION,
            }))
            (root / "preprocessor_config.json").write_text(json.dumps(PROCESSOR))
            index = root / "model.safetensors.index.json"
            index.write_text(json.dumps({"weight_map": {"vision_tower.blocks.0.weight": "vision.safetensors"}}))
            self.assertEqual(pi_model_inputs("mtplx", "mtplx 2.11.2", folder), ["text"])
            (root / "vision.safetensors").write_bytes(b"fixture-weight-payload" * 2)
            self.assertEqual(pi_model_inputs("mtplx", "mtplx 2.11.2", folder), ["text", "image"])
            for backend, version in [("omlx", "0.6.4"), ("mtplx", "2.7.1"), ("mtplx", "2.11.2rc1")]:
                self.assertEqual(pi_model_inputs(backend, version, folder), ["text"])
            index.write_text(json.dumps({"weight_map": {"language_model.weight": "vision.safetensors"}}))
            self.assertEqual(pi_model_inputs("mtplx", "2.11.2", folder), ["text"])

    def test_combined_publisher_config_is_prepared_before_advertising_images(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.artifact(root)
            source = (root / "processor_config.json").read_bytes()
            target = root / "preprocessor_config.json"
            self.assertEqual(pi_model_inputs("mtplx", "2.11.2", folder), ["text"])
            self.assertFalse(target.exists(), "A capability read must not modify the model")
            self.assertTrue(prepare_mtplx_image_processor("mtplx", "2.11.2", folder))
            self.assertEqual(json.loads(target.read_text()), PROCESSOR)
            self.assertEqual((root / "processor_config.json").read_bytes(), source)
            self.assertEqual(pi_model_inputs("mtplx", "2.11.2", folder), ["text", "image"])
            before = target.stat().st_mtime_ns
            self.assertTrue(prepare_mtplx_image_processor("mtplx", "2.11.2", folder))
            self.assertEqual(target.stat().st_mtime_ns, before)
            self.assertFalse(list(root.glob(".preprocessor-*")))

    def test_bad_processor_is_neither_published_nor_advertised(self):
        for invalid in (None, {}, {**PROCESSOR, "patch_size": 14},
                        {**PROCESSOR, "image_std": [0, 0.5, 0.5]},
                        {**PROCESSOR, "rescale_factor": float("nan")},
                        {**PROCESSOR, "size": {"shortest_edge": 100, "longest_edge": 10}}):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                self.artifact(root)
                (root / "processor_config.json").write_text(json.dumps({"image_processor": invalid}))
                self.assertFalse(prepare_mtplx_image_processor("mtplx", "2.11.2", folder))
                self.assertFalse((root / "preprocessor_config.json").exists())
                (root / "preprocessor_config.json").write_text(json.dumps(invalid))
                self.assertEqual(pi_model_inputs("mtplx", "2.11.2", folder), ["text"])

    def test_existing_invalid_config_is_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.artifact(root)
            target = root / "preprocessor_config.json"
            target.write_text("invalid publisher config")
            self.assertFalse(prepare_mtplx_image_processor("mtplx", "2.11.2", folder))
            self.assertEqual(target.read_text(), "invalid publisher config")

    def test_unwritable_model_stays_text_only_and_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.artifact(root)
            with patch("model_modalities.os.link", side_effect=PermissionError):
                self.assertFalse(prepare_mtplx_image_processor("mtplx", "2.11.2", folder))
            self.assertFalse(list(root.glob(".preprocessor-*")))
            self.assertEqual(pi_model_inputs("mtplx", "2.11.2", folder), ["text"])

    def test_unsupported_route_does_not_modify_model(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.artifact(root)
            for backend, version in (("omlx", "0.6.4"), ("mtplx", "2.7.1")):
                self.assertFalse(prepare_mtplx_image_processor(backend, version, folder))
                self.assertFalse((root / "preprocessor_config.json").exists())

    def test_pi_launch_prepares_selected_runtime_before_building_input_contract(self):
        import launcher
        with tempfile.TemporaryDirectory() as folder:
            self.artifact(Path(folder))
            plan = launcher.LaunchPlan(run_id="vision-preparation", backend="mtplx", client="pi",
                model={"id":"fixture", "name":"Fixture", "path":folder, "backends":{}},
                project=folder, context=131072, output=4096, reasoning="medium", port=18082,
                mode="custom", options={}, runtime_binary="/selected/mtplx")
            with patch.object(launcher, "command_version", side_effect=lambda binary:
                              "2.11.2" if binary == "/selected/mtplx" else "0.85.1"):
                launcher.build_pi_client(plan, launcher.ClientRoute("fixture", "fixture", "http://127.0.0.1/v1", "test"))
            provider = json.loads(plan.client_env["LLM_LAUNCHER_PI_PROVIDER"])
            self.assertEqual(provider["model"]["input"], ["text", "image"])

    def test_bad_metadata_or_shard_outside_model_does_not_advertise_vision(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(pi_model_inputs("mtplx", "2.11.2", folder), ["text"])
            (root / "config.json").write_text("[]")
            (root / "model.safetensors.index.json").write_text("{}")
            self.assertEqual(pi_model_inputs("mtplx", "2.11.2", folder), ["text"])
            (root / "config.json").write_text(json.dumps({"model_type":"qwen3_5", "vision_config":{"depth":27}}))
            (root / "model.safetensors.index.json").write_text(json.dumps({
                "weight_map":{"model.visual.weight":"../outside.safetensors"},
            }))
            self.assertEqual(pi_model_inputs("mtplx", "2.11.2", folder), ["text"])
