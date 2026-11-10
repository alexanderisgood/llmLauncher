import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import launcher
import strata_runtime as strata
import session_proxy
import launch_contract

class StrataTests(unittest.TestCase):
    def fixture(self, root, prepared=True):
        files=[]
        for i in range(4):
            p=root/f'shard-{i}.gguf';p.write_bytes(b'GGUF'+bytes([i]));files.append(strata.file_identity(p))
        pack=root/'pack';pack.mkdir();(pack/'index.txt').write_text('fixture')
        rec={'schemaVersion':1,'id':strata.MODEL_ID,'sourceFiles':files,'sourceFirst':files[0]['path'],
             'native':files[0]['path'],'ple':files[-1]['path'],'pack':str(pack),'requiresSplitGguf':True,
             'nativeTensorsVerified':prepared,'weightBytes':15,'pleBytes':5,
             'artifacts':[strata.file_identity(pack/'index.txt')] if prepared else []}
        (root/'launcher-model.json').write_text(json.dumps(rec));return rec

    def test_source_and_pack_changes_prevent_launch(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);rec=self.fixture(root)
            self.assertTrue(strata.inspect_model(root)['ready'])
            (root/'pack/index.txt').write_text('changed')
            self.assertFalse(strata.inspect_model(root)['ready'])
            (root/'launcher-model.json').write_text(json.dumps(rec))
            (root/'shard-1.gguf').unlink()
            self.assertIsNone(strata.inspect_model(root))

    def test_pending_model_is_visible_but_not_runnable(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root,False)
            model=strata.inspect_model(root)
            install={'ready':True,'runtimeVersion':'Strata fixture','identity':'runtime','supportsSplitGguf':True}
            with mock.patch.object(strata.platform,'machine',return_value='arm64'):
                record=strata.model_record(install,model,[('strata','Strata'),('splash','Splash')],48*1024**3)
            self.assertFalse(record['ready']);self.assertFalse(record['backends']['strata']['runnable'])

    def test_original_runtime_cannot_claim_split_support(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root);model=strata.inspect_model(root)
            install={'ready':True,'supportsSplitGguf':False}
            with mock.patch.object(strata,'inspect_install',return_value=install):
                with self.assertRaisesRegex(ValueError,'split-GGUF'):
                    strata.validate_route('fixture',model,16384,512)

    def test_launch_uses_original_shards_and_upstream_mac_cache_defaults(self):
        model={'pack':'/pack','native':'/model/first.gguf','ple':'/model/table.gguf'}
        install={'root':'/runtime','engineBinary':'/runtime/engine/strata'}
        cfg=strata.server_config(install,model,context=16384,port=18538,api_key='test',log=Path('/private/log'))
        self.assertEqual(cfg['host'],'127.0.0.1');self.assertEqual(cfg['env']['STRATA_METAL_SPLIT_GGUF'],'1')
        self.assertEqual(cfg['args'][cfg['args'].index('--native')+1],model['native'])
        self.assertEqual(cfg['args'][cfg['args'].index('--expert-cache')+1],'64')
        self.assertNotIn('--native-dense-gguf',cfg['args'])
        self.assertNotIn('--mtp',cfg['args'])
        self.assertEqual(cfg['args'][cfg['args'].index('--prefill')+1],'auto')

    def test_registry_and_relay_support_actual_route(self):
        self.assertIn('strata',launcher.ENGINE_BUILDERS)
        self.assertTrue(launcher.CLIENT_SUPPORT['strata']['omp']['supported'])
        body=json.dumps({'model':strata.MODEL_ID,'messages':[{'role':'user','content':'test'}]}).encode()
        result=json.loads(session_proxy.transform_chat_request(body,{'backend':'strata','servedModel':strata.MODEL_ID,'reasoning':'off','outputLimit':512}))
        self.assertEqual(result['model'],strata.MODEL_ID)
        self.assertEqual(result['reasoning_effort'],'none')
        self.assertEqual(result['max_tokens'],512)

    def test_large_context_choices_reach_native_launch_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.fixture(root)
            model = strata.inspect_model(root)
            install = {'ready': True, 'supportsSplitGguf': True, 'identity': 'runtime',
                       'runtimeVersion': 'Strata fixture', 'root': '/runtime',
                       'engineBinary': '/runtime/engine/strata'}
            with mock.patch.object(strata.platform, 'machine', return_value='arm64'):
                record = strata.model_record(install, model, [('strata', 'Strata')], 48 * 1024**3)
            contexts = [16384, 32768, 65536, 131072, 262144]
            self.assertEqual(record['backends']['strata']['contextWindows'], contexts)
            self.assertEqual(record['nativeContext'], 262144)
            self.assertEqual(record['backends']['strata']['contextMaximum'], 262144)
            self.assertEqual(record['outputMaximum'], 261120)
            for context in contexts:
                with self.subTest(context=context), \
                        mock.patch.object(strata, 'inspect_install', return_value=install), \
                        mock.patch.dict(launcher.BINARIES, {'strata': install['engineBinary']}), \
                        mock.patch.object(launcher, 'RUNS_DIR', root / 'runs'), \
                        mock.patch.object(launcher, 'STATE_DIR', root / 'state'), \
                        mock.patch.object(launcher, 'free_port', side_effect=[18765, 18766]):
                    plan = launcher.normalized_request({
                        'backend': 'strata', 'client': 'chat', 'modelId': record['id'],
                        'project': str(root), 'context': context, 'output': context - 1024,
                        'reasoning': 'off', 'options': {'acceleration': 'off', 'kv': 'off'},
                    }, [record])
                    config = json.loads((plan.run_dir / 'strata.json').read_text())
                    self.assertEqual(plan.context, context)
                    self.assertEqual(config['context'], context)
                    self.assertEqual(plan.output, context - 1024)
                    self.assertEqual(config['output'], context - 1024)
                    with self.assertRaisesRegex(ValueError, '1,024 tokens'):
                        strata.validate_route('fixture', record, context, context - 1023)
                    body = json.dumps({'model': strata.MODEL_ID, 'messages': [{'role': 'user', 'content': 'test'}]}).encode()
                    relayed = json.loads(session_proxy.transform_chat_request(body, {
                        'backend': 'strata', 'servedModel': strata.MODEL_ID, 'outputLimit': plan.output}))
                    self.assertEqual(relayed['max_tokens'], context - 1024)
                    native = strata.server_config(install, model, context=config['context'],
                        port=18765, api_key='fixture', log=root / 'engine.log')
                    self.assertEqual(native['args'][native['args'].index('--max-context') + 1], str(context))

    def test_context_presets_reject_invalid_and_out_of_model_range(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.fixture(root)
            model = strata.inspect_model(root)
            install = {'ready': True, 'supportsSplitGguf': True}
            with mock.patch.object(strata, 'inspect_install', return_value=install):
                for context in (0, 32769, 262145, 524288, True, '65536'):
                    with self.subTest(context=context), self.assertRaisesRegex(ValueError, 'context preset'):
                        strata.validate_route('fixture', model, context, 4096)
                for context in (32769, 262145, 524288):
                    with self.subTest(context=context), self.assertRaisesRegex(ValueError, 'context windows'):
                        launch_contract.validate_runtime_context('strata', context)

if __name__=='__main__':unittest.main()
