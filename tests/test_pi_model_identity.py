"""Restarting a transport must not tell Pi it switched AI models."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import launcher


class PiModelIdentity(unittest.TestCase):
    def build(self, run, backend='mtplx', model='qwopus-mxfp4', path=None):
        plan = launcher.LaunchPlan(run_id=run, backend=backend, client='pi',
            model={'id':model,'name':model,'backends':{}, **({'path':path} if path else {})}, project='/tmp',
            context=131072, output=4096, reasoning='xhigh', port=18082,
            mode='custom', options={}, agent_host='console')
        with patch.dict(launcher.BINARIES, {'pi':'pi'}):
            launcher.build_pi_client(plan, launcher.ClientRoute(
                'launcher-'+backend+'-'+run, 'served-'+run, 'http://127.0.0.1:18082/v1', 'fixture'))
        return plan, json.loads(plan.client_env['LLM_LAUNCHER_PI_PROVIDER'])

    def test_restart_preserves_identity_but_not_transport(self):
        for backend, model in [('mtplx','qwopus-mxfp4'),('omlx','qwen-6bit')]:
            a, first = self.build('first',backend,model)
            b, second = self.build('second',backend,model)
            self.assertEqual(first['id'],second['id'])
            self.assertEqual(first['model']['id'],second['model']['id'])
            self.assertNotEqual(first['transportModel'],second['transportModel'])
            self.assertEqual(a.client_argv[a.client_argv.index('--provider')+1],first['id'])
            self.assertEqual(b.client_argv[b.client_argv.index('--model')+1],second['model']['id'])

    def test_different_quant_or_backend_is_not_claimed_as_same_model(self):
        ids=[self.build('same',backend,model)[1]['id'] for backend,model in [
            ('mtplx','qwopus-mxfp4'),('mtplx','qwen-6bit'),('omlx','qwen-6bit')]]
        self.assertEqual(len(set(ids)),3)

    def test_replacing_artifact_at_same_path_changes_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / 'config.json').write_text('{}')
            weights = path / 'model.safetensors'
            weights.write_bytes(b'fixture-one')
            first = self.build('first', path=folder)[1]['id']
            self.assertEqual(first, self.build('second', path=folder)[1]['id'])
            weights.write_bytes(b'different-fixture-two')
            self.assertNotEqual(first, self.build('third', path=folder)[1]['id'])
