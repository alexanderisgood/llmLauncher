"""LLM_LAUNCHER_PI_INTEGRATION=1: real Pi, local fixture, no command/file tools."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
from unittest import mock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import launcher
import session_proxy


@unittest.skipUnless(os.environ.get("LLM_LAUNCHER_PI_INTEGRATION") == "1",
                     "opt-in installed Pi tool recovery check")
class InstalledToolRecovery(unittest.TestCase):
    def test_native_retry_executes_only_valid_tool_call_and_is_bounded(self):
        requests = []
        request_sessions = []
        raw_sessions = []
        reasoning_chunks = []
        class Responder(BaseHTTPRequestHandler):
            def log_message(self, *_args): pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append(body)
                raw_sessions.append(self.headers.get('x-mtplx-session-id'))
                _, forwarded = session_proxy.mtplx_launcher_request(
                    json.dumps(body).encode(), dict(self.headers.items()))
                request_sessions.append(next((v for k, v in forwarded.items()
                                              if k.lower() == 'x-mtplx-session-id'), None))
                number = len(requests)
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Connection', 'close')
                self.end_headers()
                self.close_connection = True
                def chunk(delta, finish=None):
                    frame = {'id':'fixture', 'choices':[{'index':0,'delta':delta,'finish_reason':finish}]}
                    self.wfile.write(('data: '+json.dumps(frame)+'\n\n').encode())
                    self.wfile.flush()
                chunk({'role':'assistant'})
                if number in (20,22,24):
                    chunk({'content':'{"name": "fixture_lookup>\n'})
                    chunk({}, 'stop')
                elif number in (21,23,25):
                    chunk({'tool_calls':[{'index':0,'id':f'episode-{number}','type':'function',
                        'function':{'name':'fixture_lookup','arguments':'{"key":"alpha"}'}}]})
                    chunk({}, 'tool_calls')
                elif number == 26:
                    chunk({'content':'Three separate format failures recovered within the same prompt.'})
                    chunk({}, 'stop')
                elif number == 18:
                    paragraph = (Path(__file__).parent / 'fixtures/pi-reasoning/audio-loop.txt').read_text() + '\n'
                    try:
                        for index in range(120):
                            chunk({'reasoning_content':paragraph})
                            reasoning_chunks.append(index)
                            time.sleep(.025)
                        chunk({}, 'stop')
                    except (BrokenPipeError, ConnectionResetError):
                        return
                elif number == 19:
                    chunk({'content':'Ready for a new measured check.'})
                    chunk({}, 'stop')
                elif number in (12,16,17):
                    chunk({'content':'Let me run the lookup:'})
                    chunk({}, 'stop')
                elif number == 14:
                    chunk({'content':'Recovered with a completed lookup.'})
                    chunk({}, 'stop')
                elif number == 2 or number >= 7:
                    chunk({'tool_calls':[{'index':0,'id':f'valid-call-{number}','type':'function',
                        'function':{'name':'fixture_lookup','arguments':'{"key":"alpha"}'}}]})
                    chunk({}, 'tool_calls')
                else:
                    chunk({'content':'Recovered with a real tool.' if number == 3 else
                           '{"name":"fixture_lookup","arguments":{"key":"alpha"}}' if number == 1 else
                           '{"name": "fixture_lookup>\n'})
                    chunk({}, 'stop')
                self.wfile.write(b'data: [DONE]\n\n')

        server = ThreadingHTTPServer(('127.0.0.1',0), Responder)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        manager = launcher.RunManager()
        console = None
        try:
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                fixture_source = (Path(__file__).parent/'fixtures/pi-generated-tool.js').read_text()
                fixture = root/'generated-tool.js'
                fixture.write_text(fixture_source.replace('`fixture-${randomUUID()}`', "'fixture-stable'")
                                   .replace('++calls > 3', '++calls > 4'))
                late_policy = root/'late-global-policy.js'
                late_policy.write_text('''export default pi => {
                  pi.on('before_provider_headers', (event, ctx) => {
                    event.headers['x-mtplx-session-id'] = String(ctx.sessionManager.getSessionId());
                  });
                };''')
                plan = launcher.LaunchPlan(
                    run_id='tool-recovery-fixture', backend='mtplx', client='pi',
                    model={'name':'Fixture','id':'fixture','backends':{}}, project=str(root),
                    context=8192, output=512, reasoning='off', port=server.server_port,
                    mode='ar', options={}, agent_host='console')
                binary = shutil.which('pi')
                self.assertIsNotNone(binary)
                with mock.patch.dict(launcher.BINARIES, {'pi':binary}):
                    launcher.build_pi_client(plan,launcher.ClientRoute(
                        'launcher-fixture','fixture',f'http://127.0.0.1:{server.server_port}/v1','local-fixture'))
                plan.client_argv += [
                    '--extension', str(fixture),
                    '--extension', str(late_policy),
                    '--tools','fixture_lookup','--no-session','--no-extensions','--no-skills',
                    '--no-prompt-templates','--no-themes','--no-context-files',
                    '--no-approve','--offline','--system-prompt','Isolated fixture only.']
                plan.client_env.update({'PI_CODING_AGENT_DIR':str(root/'config'),
                    'PI_CODING_AGENT_SESSION_DIR':str(root/'sessions'),'PI_OFFLINE':'1','PI_TELEMETRY':'0'})
                manager.plan = plan
                manager.state = {'phase':'running','message':'Fixture','run':plan.public(),'events':[]}
                manager.attachments[plan.run_id] = launcher.SurfaceAttachment(
                    owner_run_id=plan.run_id,plan=plan,primary=True)
                with mock.patch.dict(os.environ,{'PATH':os.environ['PATH']},clear=True):
                    console = manager._launch_agent_console(plan,manager.cancel_event)
                def send(text):
                    manager.write_agent_console({'ownerRunId':plan.run_id,'surfaceId':plan.run_id,
                                                 'command':'prompt','message':text})
                def wait_for(count):
                    deadline = time.monotonic()+20
                    while time.monotonic()<deadline:
                        if len(requests)>=count and not console.rpc_streaming and not console.rpc_prompt_inflight:
                            return
                        time.sleep(.03)
                    self.fail(bytes(console.output).decode(errors='replace')[-4000:])
                send('Perform the fixture lookup for config.json')
                wait_for(3)
                self.assertEqual(len(requests),3)
                self.assertTrue(any('Tool-call recovery:' in str(m.get('content'))
                                    for m in requests[1]['messages']))
                self.assertTrue(any('Invalid tool output omitted' in str(m.get('content'))
                                    for m in requests[1]['messages']))
                self.assertFalse(any('{"name":"fixture_lookup","arguments"' in str(m.get('content'))
                                     for m in requests[1]['messages']),
                                 'The retry must not replay a valid JSON envelope that was never executed')
                results = [m for m in requests[2]['messages'] if m['role']=='tool']
                self.assertEqual(len(results),1)
                self.assertIn('fixture-',str(results[0]['content']))
                send('Try the operation again')
                wait_for(6)
                self.assertEqual(len(requests),6,'Initial malformed reply plus only two retries')
                transcript = bytes(console.output).decode(errors='replace')
                self.assertIn('Automatic recovery stopped after two attempts',transcript)
                self.assertEqual([item for item in console.rpc_timeline_items.values()
                                  if item['kind']=='summary'][-1]['title'], 'Tool call failed')
                self.assertFalse(console.rpc_queue_advance_allowed)
                self.assertIn('{"name": "fixture_lookup>',transcript,
                              'Model context cleanup must preserve the visible saved transcript')
                send('Perform the operation once')
                wait_for(10)
                self.assertEqual(len(requests),10,'Repeated native calls must stop before another cycle')
                transcript = bytes(console.output).decode(errors='replace')
                self.assertIn('three identical successful results',transcript)
                self.assertNotIn('Fixture call limit exceeded',transcript,
                                 'The fourth duplicate must be blocked before tool execution')
                items = list(console.rpc_timeline_items.values())
                summaries = [item for item in items if item['kind'] == 'summary']
                self.assertEqual(summaries[-1]['title'], 'Repetition paused')
                self.assertTrue(any(item['kind']=='toolResult' and item['title']=='Stopped · fixture_lookup'
                            for item in items), [(item['kind'], item.get('title'), item.get('text', '')[:450]) for item in items if item['kind']=='toolResult'])
                manager._stop_agent_console_process(console)
                with mock.patch.dict(os.environ,{'PATH':os.environ['PATH']},clear=True):
                    console = manager._launch_agent_console(plan,manager.cancel_event)
                send('Complete the lookup operation. Do not change tests.')
                wait_for(14)
                self.assertEqual(len(requests),14)
                self.assertTrue(any('Action recovery:' in str(m.get('content'))
                                    for m in requests[12]['messages']))
                self.assertIn('Recovered with a completed lookup.',bytes(console.output).decode(errors='replace'))
                send('Complete another lookup')
                wait_for(17)
                self.assertEqual(len(requests),17,'Repeated action promises get only one recovery')
                send('Investigate the scheduler')
                wait_for(18)
                self.assertLess(len(reasoning_chunks),100,'Abort the upstream stream before the repeated response finishes')
                self.assertEqual(len(requests),18,'Reasoning-loop pauses must not auto-retry')
                self.assertIn('repeating the same reasoning paragraphs',bytes(console.output).decode(errors='replace'))
                self.assertEqual([item for item in console.rpc_timeline_items.values()
                                  if item['kind']=='summary'][-1]['title'],'Repetition paused')
                send('Continue with a fresh measured check')
                wait_for(19)
                self.assertNotIn('The AudioContext is in suspended state', json.dumps(requests[18]['messages']),
                                 'Neither content nor structured reasoning may replay the observed loop')
                self.assertNotIn('Repetitive reasoning omitted', json.dumps(requests[18]['messages']),
                                 'Cleanup must not manufacture an assistant answer for the model to copy')
                self.assertRegex(request_sessions[18] or '', r':recovery:[0-9a-f]{24}$',
                                 'A rewritten history must not restore stale committed thinking')
                self.assertNotEqual(request_sessions[18], request_sessions[17])
                self.assertEqual(raw_sessions[18], raw_sessions[17],
                                 'The late plugin reproduced the installed header overwrite')
                # Fresh fixture tool counter, same native Pi recovery extension.
                manager._stop_agent_console_process(console)
                with mock.patch.dict(os.environ,{'PATH':os.environ['PATH']},clear=True):
                    console = manager._launch_agent_console(plan,manager.cancel_event)
                send('Complete three distinct lookups')
                wait_for(26)
                self.assertEqual(len(requests),26)
                results = [m for m in requests[25]['messages'] if m['role']=='tool']
                self.assertEqual(len(results),3,'Every independent format recovery must reach a real native tool result')
                self.assertIn('Three separate format failures recovered',bytes(console.output).decode(errors='replace'))
                # Replay the same real thrown error. Three observations may run;
                # the fourth unchanged call must pause before executing again.
                manager._stop_agent_console_process(console)
                fixture.write_text(fixture_source.replace(
                    'if (params.key !== "alpha" || ++calls > 3) throw new Error("Fixture call limit exceeded");',
                    'throw new Error(++calls > 3 ? "Unexpected fourth failing execution" : "Deliberate repeated failure");'))
                with mock.patch.dict(os.environ,{'PATH':os.environ['PATH']},clear=True):
                    console = manager._launch_agent_console(plan,manager.cancel_event)
                send('Repair the failing lookup')
                wait_for(30)
                self.assertEqual(len(requests),30,'Identical native failures must not produce an unbounded retry loop')
                results = [m for m in requests[29]['messages'] if m['role']=='tool']
                self.assertEqual(len(results),3)
                self.assertTrue(all('Deliberate repeated failure' in str(m['content']) for m in results),
                                'Every actual failure must reach the model unchanged')
                transcript = bytes(console.output).decode(errors='replace')
                self.assertIn('three identical failures',transcript)
                self.assertNotIn('Unexpected fourth failing execution',transcript)
                items = list(console.rpc_timeline_items.values())
                self.assertEqual(len([item for item in items
                    if item['kind']=='toolResult' and item['title']=='Failed · fixture_lookup']),3)
                self.assertTrue(any(item['kind']=='toolResult' and item['title']=='Stopped · fixture_lookup'
                                    for item in items))
                self.assertEqual([item for item in items if item['kind']=='summary'][-1]['title'],'Repetition paused')
                self.assertFalse(console.rpc_queue_advance_allowed)
                for body in requests:
                    self.assertEqual([t['function']['name'] for t in body['tools']],['fixture_lookup'])
        finally:
            if console is not None: manager._stop_agent_console_process(console)
            server.shutdown()
            server.server_close()
