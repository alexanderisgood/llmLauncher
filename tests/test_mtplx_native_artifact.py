import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import launcher


class NativeArtifactTests(unittest.TestCase):
    def tearDown(self):
        launcher._mtplx_native_mtp_inspection.cache_clear()

    def test_nested_head_changes_model_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            config = {'mlx_lm_extra_tensors': {'mtp_file': 'mtp/weights.safetensors'}}
            (root/'mtp').mkdir()
            head = root/'mtp/weights.safetensors'
            head.write_bytes(b'first')
            self.assertEqual(launcher.mtplx_sidecar_path(root, config), head)
            before = launcher.model_artifact_fingerprint(root, config)
            head.write_bytes(b'changed-head')
            self.assertNotEqual(before, launcher.model_artifact_fingerprint(root, config))
            self.assertFalse(launcher.mtplx_sidecar_path(root, {'mlx_lm_extra_tensors': {'mtp_file': '../escape'}}).exists())

    def test_native_inspection_requires_actual_tensor_gate(self):
        receipt = {'model_dir':'/tmp/native-model', 'mtp_supported':'yes',
                   'unverified_model':False, 'mtp':{'passes_tensor_gate':True},
                   'compatibility':{'can_run':True}}
        with patch.object(launcher.subprocess, 'run') as run:
            run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(receipt))
            self.assertTrue(launcher._mtplx_native_mtp_inspection('mtplx','/tmp/native-model','one',1))
            receipt['mtp']['passes_tensor_gate'] = False
            run.return_value.stdout = json.dumps(receipt)
            self.assertFalse(launcher._mtplx_native_mtp_inspection('mtplx','/tmp/native-model','two',1))
            run.return_value.stdout = '[]'
            self.assertFalse(launcher._mtplx_native_mtp_inspection('mtplx','/tmp/native-model','three',1))
