"""Opt-in real Codex CLI -> launcher bridge -> deterministic local fixture."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import launcher
import codex_proxy
import responses_bridge


@unittest.skipUnless(os.environ.get('LLM_LAUNCHER_CODEX_INTEGRATION') == '1', 'Opt-in installed Codex')
class InstalledCodex(unittest.TestCase):
    def test_local_tool_roundtrip_reasoning_and_cached_usage(self):
        requests, errors = [], []
        config = {'backend':'mtplx','servedModel':'fixture-local','outputLimit':4096,'reasoning':'high'}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                try:
                    raw = self.rfile.read(int(self.headers['Content-Length']))
                    request = responses_bridge.translate_responses_request(
                        codex_proxy.transform_response_request(raw, config), config)
                    body = json.loads(request.body)
                    requests.append(body)
                    returned = [m for m in body['messages'] if m['role'] == 'tool']
                    if returned:
                        assert 'LOCAL_TOOL_RECEIPT' in returned[-1]['content'], returned[-1]
                        delta = {'content':'LOCAL_CODEX_VERIFIED'}
                        finish = 'stop'
                    else:
                        name = next(k for k,v in request.by_wire_name.items() if v.name == 'exec_command')
                        delta = {'reasoning_content':'Read the fixture, then report its result.',
                                 'tool_calls':[{'index':0,'id':'call_fixture','type':'function',
                                    'function':{'name':name,'arguments':json.dumps({'cmd':'cat fixture.txt','max_output_tokens':50})}}]}
                        finish = 'tool_calls'
                    chunk = {'choices':[{'index':0,'delta':delta,'finish_reason':finish}],
                             'usage':{'prompt_tokens':100,'completion_tokens':10,'total_tokens':110,
                                      'prompt_tokens_details':{'cached_tokens':60},
                                      'completion_tokens_details':{'reasoning_tokens':4}}}
                    bridge = responses_bridge.ChatStreamBridge(request)
                    wire = bridge.feed(('data: '+json.dumps(chunk)+'\n\ndata: [DONE]\n\n').encode()) + bridge.finish()
                    self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.end_headers()
                    self.wfile.write(wire)
                except Exception as exc:
                    errors.append(str(exc)); self.send_response(400); self.end_headers()
                    self.wfile.write(json.dumps({'error':{'message':str(exc)}}).encode())
        server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with tempfile.TemporaryDirectory(prefix='launcher-codex-fixture-') as folder:
                root=Path(folder); (root/'fixture.txt').write_text('LOCAL_TOOL_RECEIPT\n')
                plan=launcher.LaunchPlan(run_id='codex-fixture',backend='mtplx',client='codex',
                    model={'name':'Fixture','backends':{'mtplx':{'codexReasoning':['high']}}},
                    project=folder,context=32768,output=4096,reasoning='high',port=server.server_port,mode='ar',options={})
                launcher.build_codex_client(plan,launcher.ClientRoute('fixture','fixture-local',f'http://127.0.0.1:{server.server_port}/v1','fixture-key'))
                args=[plan.client_argv[0],'exec',*plan.client_argv[1:],'--ignore-user-config','--ephemeral','--skip-git-repo-check','--json','-s','read-only',
                      '-c','features.apps=false','-c','features.multi_agent=false',
                      'Read fixture.txt and report the receipt. Local integration fixture only.']
                env={k:v for k,v in os.environ.items() if k in {'PATH','HOME','TMPDIR','USER','SHELL'}}
                env.update(plan.client_env)
                result=subprocess.run(args,env=env,cwd=folder,capture_output=True,text=True,timeout=50)
                self.assertEqual(result.returncode,0, '\n'.join(errors)+result.stderr[-1500:]+result.stdout[-1500:])
                self.assertFalse(errors)
                self.assertEqual(len(requests),2)
                events=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
                self.assertTrue(any(e.get('item',{}).get('text')=='LOCAL_CODEX_VERIFIED' for e in events))
                usage=next(e['usage'] for e in events if e.get('type')=='turn.completed')
                self.assertGreater(usage['cached_input_tokens'],0)
                self.assertTrue(any(m.get('reasoning_content') for m in requests[1]['messages']))
        finally:
            server.shutdown(); server.server_close()
