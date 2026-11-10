import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import flash_vision
import model_modalities
import session_proxy
import strata_runtime


class FlashVisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.model = self.root / 'model'
        self.model.mkdir()
        self.source = self.model / 'part-1.gguf'
        self.source.write_bytes(b'GGUF source fixture')
        self.projector = self.root / 'projector.gguf'
        self.projector.write_bytes(b'GGUF image projector fixture')
        self.link = self.model / flash_vision.PROJECTOR_NAME
        self.link.symlink_to(self.projector)
        self.receipt = self.root / 'vision.json'
        self.receipt.write_text(json.dumps({'schemaVersion': 1, 'model': flash_vision.MODEL_ID,
            'sourceFiles': [flash_vision.file_identity(self.source)],
            'modelPaths': [str(self.model), str(self.source)],
            'projector': flash_vision.file_identity(self.projector)}))
        for name, value in [('RECEIPT', self.receipt), ('PROJECTOR_BYTES', self.projector.stat().st_size),
                ('PROJECTOR_SHA256', hashlib.sha256(self.projector.read_bytes()).hexdigest())]:
            p = mock.patch.object(flash_vision, name, value)
            p.start()
            self.addCleanup(p.stop)
        flash_vision._verified_projector.cache_clear()
        self.addCleanup(flash_vision._verified_projector.cache_clear)

    def test_only_complete_bound_routes_advertise_images(self):
        for backend in ('strata', 'splash', 'lmstudio'):
            self.assertEqual(model_modalities.pi_model_inputs(backend, '', str(self.model)), ['text', 'image'])
        self.assertEqual(model_modalities.pi_model_inputs('omlx', '', str(self.model)), ['text'])
        self.assertIsNone(flash_vision.inspect_model(self.root))
        self.source.write_bytes(b'changed source')
        self.assertIsNone(flash_vision.inspect_model(self.model))

    def test_missing_and_changed_projector_are_not_reported_as_vision(self):
        self.assertIsNotNone(flash_vision.inspect_model(self.model))
        self.projector.write_bytes(b'bad projector')
        self.assertIsNone(flash_vision.inspect_model(self.model))
        self.projector.unlink()
        self.assertEqual(model_modalities.pi_model_inputs('strata', '', str(self.model)), ['text'])

    def test_digest_is_checked_even_when_receipt_matches_new_file(self):
        self.projector.write_bytes(b'x' * flash_vision.PROJECTOR_BYTES)
        receipt = json.loads(self.receipt.read_text())
        receipt['projector'] = flash_vision.file_identity(self.projector)
        self.receipt.write_text(json.dumps(receipt))
        self.assertIsNone(flash_vision.inspect_model(self.model))

    def test_native_strata_config_enables_gpu_reader_and_original_model(self):
        vision = flash_vision.inspect_model(self.model)
        model = {'pack': '/pack', 'native': str(self.source), 'ple': '/bf16-ple', 'vision': vision}
        cfg = strata_runtime.server_config({'root': '/runtime', 'engineBinary': '/runtime/engine/strata'},
            model, context=262144, port=18538, api_key='fixture', log=self.root / 'log')
        self.assertTrue(cfg['vision']['gpu'])
        self.assertEqual(cfg['vision']['mmproj'], str(self.projector.resolve()))
        self.assertEqual(cfg['vision']['model'], str(self.source))
        self.assertEqual(cfg['vision']['exe'], '/runtime/engine/strata-vision')

    def test_user_and_tool_images_survive_the_private_relay(self):
        for backend in ('strata', 'splash', 'lmstudio'):
            content = [{'type': 'text', 'text': 'Read the picture'},
                       {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,fixture'}}]
            messages = [{'role': 'user', 'content': content},
                        {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'read1', 'type': 'function',
                         'function': {'name': 'read', 'arguments': '{}'}}]},
                        {'role': 'tool', 'tool_call_id': 'read1', 'content': content}]
            body = json.dumps({'model': 'fixture', 'messages': messages}).encode()
            out = json.loads(session_proxy.transform_chat_request(body, {'backend': backend,
                'servedModel': 'fixture', 'reasoning': 'off', 'outputLimit': 512}))
            self.assertEqual(out['messages'], messages)


if __name__ == '__main__':
    unittest.main()
