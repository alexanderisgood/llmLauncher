"""Opt-in installed Pi conversion across launcher restart identities."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from tests import test_pi_model_identity


@unittest.skipUnless(os.environ.get('LLM_LAUNCHER_PI_INTEGRATION') == '1', 'installed Pi check')
class InstalledIdentity(unittest.TestCase):
    def test_native_conversion_retains_reasoning_after_transport_restart(self):
        helper = test_pi_model_identity.PiModelIdentity()
        pairs = [[helper.build(run, backend, model)[1] for run in ['before', 'after']]
                 for backend, model in [('mtplx','qwopus-mxfp4'),('omlx','qwen-6bit')]]
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)/'identities.json'
            data.write_text(json.dumps(pairs))
            script = """
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {convertMessages} from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/node_modules/@earendil-works/pi-ai/dist/api/openai-completions.js';
for (const [first, second] of JSON.parse(fs.readFileSync(process.argv[1], 'utf8'))) {
  const model={...second.model,provider:second.id,api:'openai-completions',input:['text']};
  const prior={role:'assistant',provider:first.id,model:first.model.id,api:model.api,
    content:[{type:'thinking',thinking:'RESTART_REASONING_7319',thinkingSignature:'reasoning_content'},
             {type:'text',text:'Decision made.'}],stopReason:'stop',timestamp:1};
  const context={messages:[{role:'user',content:'Decide',timestamp:0},prior,
                          {role:'user',content:'Continue',timestamp:2}]};
  const wire=convertMessages(model,context,{supportsDeveloperRole:false});
  assert.equal(wire[1].reasoning_content,'RESTART_REASONING_7319');
  assert.equal(wire[1].content,'Decision made.');
  prior.provider='launcher-old-process'; prior.model=first.transportModel;
  const broken=convertMessages(model,context,{supportsDeveloperRole:false});
  assert.equal(broken[1].reasoning_content,undefined);
  assert.ok(broken[1].content.includes('RESTART_REASONING_7319'));
}
console.log('Native Pi preserves reasoning after restart; previous process identity reproduces corruption.');
"""
            result = subprocess.run(['node','--input-type=module','-e',script,str(data)],
                                    text=True,capture_output=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
