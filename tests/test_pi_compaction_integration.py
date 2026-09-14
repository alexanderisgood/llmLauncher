"""Opt-in installed Pi: native-style overflow compacts and retries automatically."""
import contextlib
import json
import os
import pty
import select
import signal
import subprocess
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock
import launcher
import session_proxy


@unittest.skipUnless(os.environ.get('LLM_LAUNCHER_PI_INTEGRATION') == '1', 'Opt-in installed Pi')
class InstalledPiCompaction(unittest.TestCase):
    def test_16k_whallm_compacts_once_at_threshold_and_continues(self):
        self.run_16k_context_fixture("console")

    def test_terminal_16k_uses_same_compaction_policy_as_hub(self):
        self.run_16k_context_fixture("terminal")

    def test_preserved_uzu_pi_0842_retains_native_compaction(self):
        preserved = launcher.STATE_DIR / 'runtimes/pi-uzu-0.84.2/node_modules/.bin/pi'
        if not preserved.is_file():
            self.skipTest('Preserved Uzu Pi 0.84.2 is not installed')
        self.run_16k_context_fixture('console', backend='uzu', pi_binary=str(preserved))

    def run_16k_context_fixture(self, surface, backend='whallm', pi_binary=None):
        normal_requests, summaries = [], []

        class Responder(BaseHTTPRequestHandler):
            def log_message(self, *_): pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                summary = 'context summarization assistant' in str(body['messages'][0]['content'])
                (summaries if summary else normal_requests).append(body)
                text = 'Summary: keep verified file references and continue the task.' if summary else 'Completed the next step.'
                prompt_tokens = 8000 if len(normal_requests) == 1 else 13000 if len(normal_requests) == 2 else 3000
                if summary:
                    prompt_tokens = 8000
                event = {'id':'small-context','model':'fixture','choices':[
                    {'index':0,'delta':{'content':text},'finish_reason':None},
                ]}
                self.close_connection = True
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                self.wfile.write(('data: '+json.dumps(event)+'\n\n').encode())
                event['choices'] = [{'index':0,'delta':{},'finish_reason':'stop'}]
                event['usage'] = {'prompt_tokens':prompt_tokens,'completion_tokens':100,'total_tokens':prompt_tokens+100}
                self.wfile.write(('data: '+json.dumps(event)+'\n\ndata: [DONE]\n\n').encode())

        server = ThreadingHTTPServer(('127.0.0.1',0), Responder)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        manager = launcher.RunManager()
        try:
            with tempfile.TemporaryDirectory(prefix='pi-small-context-') as directory, contextlib.ExitStack() as cleanup:
                root = Path(directory)
                config = root/'config'; config.mkdir()
                saved_settings = json.dumps({'compaction':{'enabled':True,'reserveTokens':16384,'keepRecentTokens':20000}})
                (config/'settings.json').write_text(saved_settings)
                session = root/'seed.jsonl'
                entries = [{'type':'session','version':3,'id':'small-context','timestamp':'2026-01-01T00:00:00Z','cwd':str(root)}]
                parent = None
                # Long character-estimated history makes native cut-point preparation
                # possible; reported usage, rather than characters, controls admission.
                for index in range(24):
                    for role, content in [('user',f'Perform step {index}'),('assistant','Evidence and file references.\n' * 150)]:
                        identifier = f'{index}-{role}'
                        message = {'role':role,'content':[{'type':'text','text':content}],'timestamp':index*1000}
                        if role == 'assistant':
                            message.update({'provider':'launcher-fixture','model':'fixture','api':'openai-completions','stopReason':'stop',
                                'usage':{'input':7800,'output':200,'cacheRead':0,'cacheWrite':0,'totalTokens':8000,
                                         'cost':{'input':0,'output':0,'cacheRead':0,'cacheWrite':0,'total':0}}})
                        entries.append({'type':'message','id':identifier,'parentId':parent,'timestamp':'2026-01-01T00:00:00Z','message':message})
                        parent = identifier
                session.write_text(''.join(json.dumps(entry)+'\n' for entry in entries))
                plan = launcher.LaunchPlan(run_id='small-context',backend=backend,client='pi',
                    model={'name':'Qwen3.8 Flash fixture','id':'fixture','backends':{'whallm':{'agentReasoning':['off','medium']}}},
                    project=str(root),context=16384,output=4096,reasoning='auto' if backend == 'uzu' else 'medium',port=server.server_port,
                    mode='ar',options={},agent_host=surface,pi_session_file=str(session))
                with mock.patch.dict(launcher.BINARIES, {'pi':pi_binary or shutil.which('pi')}):
                    launcher.build_pi_client(plan, launcher.ClientRoute('launcher-fixture','fixture',f'http://127.0.0.1:{server.server_port}/v1','test-local-key'))
                plan.client_argv.extend(['--no-tools','--no-extensions','--no-skills','--no-prompt-templates','--no-themes',
                    '--no-context-files','--no-approve','--offline','--system-prompt','Local fixture only.'])
                plan.client_env.update({'PI_CODING_AGENT_DIR':str(config),'PI_CODING_AGENT_SESSION_DIR':str(root/'sessions'),'PI_OFFLINE':'1','PI_TELEMETRY':'0'})
                shared = str(launcher.APP_DIR / 'pi-context-policy.js')
                hub = str(launcher.APP_DIR / 'pi-hub-commands.js')
                self.assertEqual(plan.client_argv.count(shared), 1)
                self.assertEqual(hub in plan.client_argv, surface == 'console')
                if surface == 'console':
                    manager.plan = plan
                    manager.state = {'phase':'running','run':plan.public(),'events':[]}
                    manager.attachments[plan.run_id] = launcher.SurfaceAttachment(owner_run_id=plan.run_id,plan=plan,primary=True)
                    with mock.patch.dict(os.environ, {'PATH':os.environ['PATH']}, clear=True):
                        console = manager._launch_agent_console(plan,manager.cancel_event)
                    cleanup.callback(manager._stop_agent_console_process,console)
                    send = lambda text: manager.write_agent_console({'ownerRunId':plan.run_id,'surfaceId':plan.run_id,'command':'prompt','message':text})
                    settled = lambda turn: not console.rpc_streaming and not console.rpc_prompt_inflight and not console.rpc_compacting
                    output = lambda: bytes(console.output).decode(errors='replace')[-4000:]
                else:
                    # A real interactive Pi TUI on an isolated PTY, using the exact
                    # Terminal launch extensions. Never open the user's Terminal.
                    probe = root/'terminal-probe.js'
                    ready = root/'terminal-ready'
                    ended = root/'terminal-ended'
                    probe.write_text("""import {writeFileSync,appendFileSync} from 'node:fs';
export default function probe(pi) {
  pi.on('session_start', () => writeFileSync(process.env.FIXTURE_READY, 'ready'));
  pi.on('agent_end', () => appendFileSync(process.env.FIXTURE_ENDED, 'done\\n'));
}
""")
                    plan.client_argv.extend(['--extension',str(probe)])
                    master, slave = pty.openpty()
                    process = subprocess.Popen(plan.client_argv, cwd=root,
                        env={'PATH':os.environ['PATH'], **plan.client_env, 'TERM':'xterm-256color',
                             'FIXTURE_READY':str(ready),'FIXTURE_ENDED':str(ended)},
                        stdin=slave,stdout=slave,stderr=slave,start_new_session=True)
                    os.close(slave)
                    captured = bytearray()
                    def drain():
                        while True:
                            try:
                                if not select.select([master],[],[],.2)[0]:
                                    if process.poll() is not None: return
                                    continue
                                chunk = os.read(master,65536)
                                if not chunk: return
                                captured.extend(chunk)
                                if len(captured)>65536: del captured[:-65536]
                            except OSError:
                                return
                    reader = threading.Thread(target=drain,daemon=True); reader.start()
                    def stop_terminal():
                        if process.poll() is None:
                            os.killpg(process.pid,signal.SIGTERM)
                            try: process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                os.killpg(process.pid,signal.SIGKILL); process.wait(timeout=5)
                        reader.join(timeout=1)
                        os.close(master)
                    cleanup.callback(stop_terminal)
                    output = lambda: bytes(captured).decode(errors='replace')[-4000:]
                    deadline = time.monotonic()+20
                    while not ready.exists():
                        if process.poll() is not None or time.monotonic()>deadline: self.fail(output())
                        time.sleep(.025)
                    send = lambda text: os.write(master,(text+'\r').encode())
                    settled = lambda turn: ended.exists() and len(ended.read_text().splitlines()) >= turn+1
                for turn in range(4):
                    send(f'Continue step {turn}')
                    deadline = time.monotonic()+25
                    while time.monotonic() < deadline:
                        if len(normal_requests) >= turn+1 and settled(turn):
                            break
                        time.sleep(.025)
                    else:
                        self.fail(output())
                    if turn == 0:
                        self.assertFalse(summaries, '8K usage must fit in the selected 16K window')
                self.assertEqual(len(normal_requests),4)
                compacted = [json.loads(line) for line in session.read_text().splitlines() if json.loads(line).get('type') == 'compaction']
                self.assertEqual(len(compacted),1, 'The threshold must compact once, then leave room for subsequent turns')
                self.assertTrue(summaries)
                self.assertTrue(all(0 < body['max_tokens'] <= 3276 for body in summaries))
                self.assertEqual((config/'settings.json').read_text(),saved_settings)
                if surface == 'console':
                    self.assertFalse(console.rpc_compacting)
                    self.assertEqual(json.loads(console.rpc_statuses['launcher.context']['text'])['tokens'],3100)
        finally:
            server.shutdown(); server.server_close()

    def test_overflow_compacts_retries_and_exports_installed_token_speed(self):
        self.run_overflow_fixture(False)

    def test_omlx_stream_overflow_compacts_and_retries(self):
        self.run_overflow_fixture(True)

    def test_omlx_prefill_memory_rejection_compacts_and_retries(self):
        self.run_overflow_fixture(False, memory_rejection=True)

    def run_overflow_fixture(self, omlx_stream, memory_rejection=False):
        requests = []
        requested_models = []
        relay_config = {'backend':'omlx','servedModel':'fixture','outputLimit':4096,
                        'reasoning':'off','servedModelAliases':[]}
        class Responder(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requested_models.append(body.get('model'))
                body = json.loads(session_proxy.transform_chat_request(
                    json.dumps(body).encode(), relay_config, {'client':'pi'}))
                requests.append(body)
                self.close_connection = True
                if len(requests) == 2:
                    payload = session_proxy.normalize_uzu_context_error(json.dumps({'error':{
                        'code':'context_length_exceeded', 'type':'invalid_request_error',
                        'message':'the canonical prompt plus the response limit exceeds the 8192-token server context'
                    }}).encode())
                    if memory_rejection:
                        payload = session_proxy.normalize_omlx_compactable_error(json.dumps({'error':{
                            'code':'prefill_memory_exceeded','type':'invalid_request_error',
                            'message':'oMLX prefill memory guard rejected this prompt: Prefill would require ~37.91 GB peak but metal_cap ceiling is 37.44 GB.',
                            'estimated_bytes':40703772936,'limit_bytes':40200896512,
                        }}).encode())
                    if omlx_stream:
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/event-stream')
                        self.end_headers()
                        self.wfile.write(b'data: {"error":{"message":"context_length_exceeded: The prompt has 8192 tokens and fills the 8192-token context window. Compact the conversation.","type":"server_error"}}\n\ndata: [DONE]\n\n')
                        return
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                text = ('Seed history. ' * 250) if len(requests) == 1 else ('Summary of previous work.' if len(requests) == 3 else 'Recovered and continued.')
                for part in [text[:50], text[50:]]:
                    value = {'id':'fixture','model':'fixture','choices':[{'index':0,'delta':{'content':part},'finish_reason':None}]}
                    self.wfile.write(('data: '+json.dumps(value)+'\n\n').encode())
                    self.wfile.flush()
                    time.sleep(.1)
                self.wfile.write(('data: '+json.dumps({'id':'fixture','model':'fixture','choices':[{'index':0,'delta':{},'finish_reason':'stop'}],
                    'usage':{'prompt_tokens':300,'completion_tokens':800 if len(requests)==1 else 20,'total_tokens':1100 if len(requests)==1 else 320}})+'\n\ndata: [DONE]\n\n').encode())
                self.wfile.flush()
        server = ThreadingHTTPServer(('127.0.0.1',0), Responder)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        manager = launcher.RunManager()
        try:
            with tempfile.TemporaryDirectory(prefix='pi-compact-test-') as directory, contextlib.ExitStack() as cleanup:
                root = Path(directory)
                config = root/'config'; config.mkdir()
                (config/'settings.json').write_text(json.dumps({'compaction':{'enabled':True,'reserveTokens':1024,'keepRecentTokens':128}}))
                plan = launcher.LaunchPlan(run_id='compact-fixture',backend='omlx',client='pi',
                    model={'name':'fixture','id':'fixture','backends':{}},project=str(root),
                    context=8192,output=4096,reasoning='off',port=server.server_port,mode='ar',options={},agent_host='console')
                with mock.patch.dict(launcher.BINARIES, {'pi':shutil.which('pi')}):
                    launcher.build_pi_client(plan, launcher.ClientRoute('launcher-fixture','fixture',f'http://127.0.0.1:{server.server_port}/v1','test-local-key'))
                relay_config['servedModelAliases'] = [launcher.pi_model_identity(plan)[1]]
                plan.client_argv.extend(['--no-tools','--no-extensions','--no-skills','--no-prompt-templates','--no-themes','--no-context-files','--no-approve','--offline','--system-prompt','Local fixture only.'])
                speed = Path.home()/'.pi/agent/npm/node_modules/pi-token-speed/index.ts'
                if speed.exists(): plan.client_argv.extend(['--extension',str(speed)])
                plan.client_env.update({'PI_CODING_AGENT_DIR':str(config),'PI_CODING_AGENT_SESSION_DIR':str(root/'sessions'),'PI_OFFLINE':'1','PI_TELEMETRY':'0'})
                manager.plan = plan
                manager.state = {'phase':'running', 'run':plan.public(), 'events':[]}
                manager.attachments[plan.run_id] = launcher.SurfaceAttachment(owner_run_id=plan.run_id, plan=plan, primary=True)
                with mock.patch.dict(os.environ, {'PATH':os.environ['PATH']}, clear=True):
                    console = manager._launch_agent_console(plan, manager.cancel_event)
                cleanup.callback(manager._stop_agent_console_process, console)
                def send(message):
                    manager.write_agent_console({'ownerRunId':plan.run_id,'surfaceId':plan.run_id,'command':'prompt','message':message})
                def wait(predicate):
                    deadline=time.monotonic()+25
                    while time.monotonic()<deadline:
                        if predicate(): return
                        time.sleep(.025)
                    self.fail(bytes(console.output).decode(errors='replace')[-4000:])
                send('seed')
                wait(lambda: len(requests)==1 and not console.rpc_streaming and not console.rpc_prompt_inflight)
                context_status = json.loads(console.rpc_statuses['launcher.context']['text'])
                self.assertEqual(context_status['tokens'], 1100)
                send('continue fixture')
                wait(lambda: len(requests)>=4 and not console.rpc_streaming and not console.rpc_prompt_inflight)
                self.assertEqual(len(requests),4)
                self.assertEqual(requested_models[2], relay_config['servedModelAliases'][0],
                                 'Native summaries bypass the ordinary provider request hook')
                self.assertTrue(all(body['model']=='fixture' for body in requests))
                items=list(console.rpc_timeline_items.values())
                self.assertTrue(any(i['title']=='Context ready' for i in items))
                self.assertTrue(any('Recovered and continued.' in i['text'] for i in items))
                self.assertFalse(console.rpc_compacting)
                self.assertEqual(json.loads(console.rpc_statuses['launcher.context']['text'])['tokens'], 320)
                if speed.exists():
                    self.assertIn('tok/s',console.rpc_statuses['tokenSpeed']['text'])
                session_file = next((root/'sessions').rglob('*.jsonl'))
                manager._stop_agent_console_process(console)
                plan.client_argv.extend(['--session', launcher.validated_pi_session_file(str(session_file), str(root))])
                with mock.patch.dict(os.environ, {'PATH':os.environ['PATH']}, clear=True):
                    console = manager._launch_agent_console(plan, manager.cancel_event)
                cleanup.callback(manager._stop_agent_console_process, console)
                wait(lambda: console.rpc_history_loaded)
                self.assertIn('Recovered and continued.', bytes(console.output).decode(errors='replace'))
                self.assertEqual(len(requests), 4, 'Resuming must not submit another model request')
                print('Installed Pi compacted overflow, retried once, exported pi-token-speed, and resumed saved history.')
        finally:
            server.shutdown(); server.server_close()

if __name__=='__main__': unittest.main()
