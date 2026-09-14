"""Memory recovery must leave room for subsequent work, not only one retry."""
import contextlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

import launcher
import session_proxy


@unittest.skipUnless(os.environ.get('LLM_LAUNCHER_PI_INTEGRATION') == '1', 'Opt-in installed Pi')
class MemoryCompaction(unittest.TestCase):
    def test_recovery_leaves_room_for_two_following_requests(self):
        self.run_recovery(20)

    def test_memory_overflow_below_default_retention_still_compacts(self):
        # ~60k real reported tokens, but under Pi's 20k character estimate.
        # Previously native preparation returned None before our hook ran.
        self.run_recovery(6)

    def test_another_memory_overflow_after_recovery_can_compact_again(self):
        self.run_recovery(6, grow_again=True)

    def test_mtplx_streamed_admission_refusal_compacts_and_continues(self):
        self.run_recovery(6, backend='mtplx')

    def test_mtplx_http_admission_refusal_compacts_and_continues(self):
        self.run_recovery(6, backend='mtplx', http_error=True)

    def run_recovery(self, history_turns, grow_again=False, backend='omlx', http_error=False):
        normal_sizes, summaries, rejections = [], [], []

        class Responder(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                summary = 'context summarization assistant' in str(body['messages'][0]['content'])
                size = sum(len(str(m['content'])) for m in body['messages'])
                self.close_connection = True
                if not summary:
                    normal_sizes.append(size)
                    if size > 55000:
                        rejections.append(size)
                        if backend == 'mtplx':
                            payload=json.dumps({'choices':[{'index':0,'delta':{},'finish_reason':'error'}], 'error': {
                                'code':'insufficient_memory','type':'server_error','status':507,
                                'message':"insufficient memory: this prompt projects 40.7 GiB against the engine's 40.0 GiB limit (107326 prompt tokens, 40 not cached). The request was refused before prefill instead of pushing the Mac into swap."
                            }}).encode()
                            self.send_response(507 if http_error else 200)
                            self.send_header('Content-Type','application/json' if http_error else 'text/event-stream')
                            self.end_headers()
                            self.wfile.write(payload if http_error else b'data: '+payload+b'\n\ndata: [DONE]\n\n')
                            return
                        payload = session_proxy.normalize_omlx_compactable_error(json.dumps({'error': {
                            'code':'prefill_memory_exceeded', 'message':'Prompt processing exceeds available memory'
                        }}).encode())
                        self.send_response(400); self.send_header('Content-Type','application/json'); self.end_headers()
                        self.wfile.write(payload); return
                else:
                    summaries.append(size)
                self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.end_headers()
                text = 'Summary: retain the task and file references; older generated work is saved.' if summary else 'Continuing successfully.'
                if grow_again and not summary:
                    text += 'generated additional code\n' * 150
                chunk = {'id':'fixture','model':'fixture','choices':[{'index':0,'delta':{'content':text},'finish_reason':None}]}
                self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode())
                chunk['choices'] = [{'index':0,'delta':{},'finish_reason':'stop'}]
                chunk['usage'] = {'prompt_tokens':size//3,'completion_tokens':30,'total_tokens':size//3+30}
                self.wfile.write(('data: '+json.dumps(chunk)+'\n\ndata: [DONE]\n\n').encode())

        server = ThreadingHTTPServer(('127.0.0.1',0), Responder)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        relay = None
        route_port = server.server_port
        if backend == 'mtplx':
            relay = ThreadingHTTPServer(('127.0.0.1',0), session_proxy.ProxyHandler)
            relay.config={'backend':backend,'upstreamPort':server.server_port,'upstreamKey':'fixture-private',
                'servedModel':'fixture','servedModelAliases':[],'outputLimit':4096}
            relay.registry=session_proxy.SurfaceRegistry([{'id':'11111111-1111-4111-8111-111111111111','client':'pi','key':'test-local-key-1234567890',
                'samplingContract':{'schemaVersion':1,'controlled':True,'mode':'model','values':{}},
                'samplingEnforcement':{'protocol':'chat-completions','representableFields':[],'implicitModelDefaults':False}}])
            relay.scheduler=session_proxy.RequestScheduler(1)
            relay.daemon_threads=True
            threading.Thread(target=relay.serve_forever,daemon=True).start()
            route_port=relay.server_port
        manager = launcher.RunManager()
        try:
            with tempfile.TemporaryDirectory(prefix='pi-memory-headroom-') as directory, contextlib.ExitStack() as cleanup:
                root = Path(directory); config=root/'config'; config.mkdir()
                original_settings = json.dumps({'compaction':{'enabled':True,'reserveTokens':16384,'keepRecentTokens':20000}})
                (config/'settings.json').write_text(original_settings)
                session = root/'seed.jsonl'
                entries = [{'type':'session','version':3,'id':'memory-fixture','timestamp':'2026-01-01T00:00:00Z','cwd':str(root)}]
                parent = None
                for index in range(history_turns):
                    for role, content in [('user',f'Continue task {index}'),('assistant', 'generated code line\n' * 500)]:
                        identifier = f'entry-{index}-{role}'
                        message = {'role':role,'content':[{'type':'text','text':content}],'timestamp':index*1000}
                        if role == 'assistant':
                            message.update({'provider':'launcher-fixture','model':'fixture','api':'openai-completions','stopReason':'stop',
                                'usage':{'input':60000,'output':1000,'cacheRead':0,'cacheWrite':0,'totalTokens':61000,'cost':{'input':0,'output':0,'cacheRead':0,'cacheWrite':0,'total':0}}})
                        entries.append({'type':'message','id':identifier,'parentId':parent,'timestamp':'2026-01-01T00:00:00Z','message':message})
                        parent = identifier
                session.write_text(''.join(json.dumps(e)+'\n' for e in entries))
                plan = launcher.LaunchPlan(run_id='memory-fixture',backend=backend,client='pi',
                    model={'name':'fixture','id':'fixture','backends':{}},project=str(root),context=131072,output=4096,
                    reasoning='off',port=server.server_port,mode='ar',options={},agent_host='console',pi_session_file=str(session))
                with mock.patch.dict(launcher.BINARIES,{'pi':shutil.which('pi')}):
                    launcher.build_pi_client(plan,launcher.ClientRoute('launcher-fixture','fixture',f'http://127.0.0.1:{route_port}/v1','test-local-key-1234567890'))
                if relay:
                    relay.config['servedModelAliases']=[launcher.pi_model_identity(plan)[1]]
                plan.client_argv.extend(['--no-tools','--no-extensions','--no-skills','--no-prompt-templates','--no-themes',
                    '--no-context-files','--no-approve','--offline','--system-prompt','Local memory fixture only.'])
                plan.client_env.update({'PI_CODING_AGENT_DIR':str(config),'PI_CODING_AGENT_SESSION_DIR':str(root/'sessions'),'PI_OFFLINE':'1','PI_TELEMETRY':'0'})
                manager.plan=plan
                manager.state={'phase':'running','run':plan.public(),'events':[]}
                manager.attachments[plan.run_id]=launcher.SurfaceAttachment(owner_run_id=plan.run_id,plan=plan,primary=True)
                with mock.patch.dict(os.environ,{'PATH':os.environ['PATH']},clear=True):
                    console=manager._launch_agent_console(plan,manager.cancel_event)
                cleanup.callback(manager._stop_agent_console_process,console)
                turns = 6 if grow_again else 3
                for turn in range(turns):
                    message = f'Next step {turn}'
                    manager._write_pi_rpc_console(console,{'command':'prompt','message':message})
                    deadline=time.monotonic()+20
                    while time.monotonic()<deadline:
                        if not console.rpc_streaming and not console.rpc_prompt_inflight: break
                        time.sleep(.025)
                    else: self.fail(f'turn={turn}, requests={normal_sizes}, streaming={console.rpc_streaming}, inflight={console.rpc_prompt_inflight}, pending={console.rpc_pending_messages}, compacting={console.rpc_compacting}, commands={console.rpc_command_ids}; ' + bytes(console.output).decode(errors='replace')[-1000:])
                compacted=[json.loads(line) for line in session.read_text().splitlines() if json.loads(line).get('type')=='compaction']
                expected_compactions = 2 if grow_again else 1
                self.assertEqual(len(compacted),expected_compactions, normal_sizes)
                self.assertEqual(len(rejections),expected_compactions, normal_sizes)
                self.assertEqual(len(normal_sizes),turns + expected_compactions, normal_sizes)
                self.assertLess(max(size for size in normal_sizes if size not in rejections),55000 if grow_again else 45000,normal_sizes)
                self.assertIn('Freeing extra room',bytes(console.output).decode(errors='replace'))
                self.assertEqual((config/'settings.json').read_text(),original_settings)
                print('Memory recovery request sizes:',normal_sizes)
        finally:
            if relay:
                relay.shutdown();relay.server_close()
            server.shutdown();server.server_close()


if __name__=='__main__':unittest.main()
