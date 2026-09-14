"""Opt-in installed Pi: native edit failure returns observed source through Hub."""
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


@unittest.skipUnless(os.environ.get('LLM_LAUNCHER_PI_INTEGRATION') == '1', 'Opt-in installed Pi')
class InstalledEditRecovery(unittest.TestCase):
    def test_native_atomic_failure_yields_exact_anchor_for_next_edit(self):
        requests, errors, file_observations = [], [], []
        actual = 'const PAL = {\n  red: "#e8483a",\n};\n\nfunction total(x, y) {\n  return x + y;\n}\n'
        invented = '  cave: {skyTop: "#1a1a2e"}\n};'
        target = None

        class Responder(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append(body)
                self.close_connection = True
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()

                def chunk(delta, finish=None):
                    value = {'id':'edit-fixture', 'choices':[{'index':0,'delta':delta,'finish_reason':finish}]}
                    self.wfile.write(('data: ' + json.dumps(value) + '\n\n').encode())

                def edit(identifier, edits):
                    chunk({'tool_calls':[{'index':0,'id':identifier,'type':'function','function':{
                        'name':'edit','arguments':json.dumps({'path':'fixture.js','edits':edits})}}]})
                    chunk({}, 'tool_calls')

                try:
                    if len(requests) == 1:
                        edit('invented-anchor', [
                            {'oldText':invented,'newText':invented + '\nconst THEMES = {};'},
                            {'oldText':'return x + y;','newText':'return x - y;'},
                        ])
                    elif len(requests) == 2:
                        file_observations.append(target.read_text())
                        result = [message for message in body['messages'] if message['role'] == 'tool'][-1]
                        content = result['content']
                        text = content if isinstance(content, str) else '\n'.join(block.get('text', '') for block in content)
                        if 'Launcher source observation after the native edit failed.' not in text:
                            raise AssertionError('Native tool_result hook did not attach source observation: ' + text)
                        evidence = json.loads(text[text.index('{"path":'):])
                        anchor = next(item['text'] for item in evidence['declarations'] if item['text'] == 'const PAL = {')
                        edit('observed-anchor', [
                            {'oldText':anchor,'newText':'const THEMES = {};\n' + anchor},
                            {'oldText':'return x + y;','newText':'return x - y;'},
                        ])
                    else:
                        chunk({'content':'Completed using the observed source anchor.'})
                        chunk({}, 'stop')
                except Exception as error:
                    errors.append(str(error))
                    chunk({'content':'Fixture failed: ' + str(error)})
                    chunk({}, 'stop')
                self.wfile.write(b'data: [DONE]\n\n')

        server = ThreadingHTTPServer(('127.0.0.1', 0), Responder)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        manager = launcher.RunManager()
        try:
            with tempfile.TemporaryDirectory(prefix='pi-native-edit-') as folder, contextlib.ExitStack() as cleanup:
                root = Path(folder)
                target = root / 'fixture.js'
                target.write_text(actual)
                config = root / 'config'
                config.mkdir()
                plan = launcher.LaunchPlan(run_id='native-edit-fixture', backend='omlx', client='pi',
                    model={'name':'Fixture','id':'fixture','backends':{}}, project=str(root), context=16384,
                    output=2048, reasoning='off', port=server.server_port, mode='ar', options={}, agent_host='console')
                with mock.patch.dict(launcher.BINARIES, {'pi':shutil.which('pi')}):
                    launcher.build_pi_client(plan, launcher.ClientRoute('launcher-fixture','fixture',
                        f'http://127.0.0.1:{server.server_port}/v1', 'local-fixture-key'))
                plan.client_argv += ['--tools','edit','--no-extensions','--no-skills','--no-prompt-templates',
                    '--no-themes','--no-context-files','--no-approve','--offline',
                    '--system-prompt','Isolated native edit fixture only.']
                plan.client_env.update({'PI_CODING_AGENT_DIR':str(config),
                    'PI_CODING_AGENT_SESSION_DIR':str(root / 'sessions'),'PI_OFFLINE':'1','PI_TELEMETRY':'0'})
                manager.plan = plan
                manager.state = {'phase':'running','run':plan.public(),'events':[]}
                manager.attachments[plan.run_id] = launcher.SurfaceAttachment(
                    owner_run_id=plan.run_id, plan=plan, primary=True)
                with mock.patch.dict(os.environ, {'PATH':os.environ['PATH']}, clear=True):
                    console = manager._launch_agent_console(plan, manager.cancel_event)
                cleanup.callback(manager._stop_agent_console_process, console)
                manager.write_agent_console({'ownerRunId':plan.run_id,'surfaceId':plan.run_id,
                    'command':'prompt','message':'Add THEMES and change total to subtraction in fixture.js.'})
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if len(requests) >= 2 and not console.rpc_streaming and not console.rpc_prompt_inflight:
                        break
                    time.sleep(.025)
                else:
                    self.fail(bytes(console.output).decode(errors='replace')[-6000:])
                self.assertEqual(errors, [])
                self.assertEqual(len(requests), 3, 'One failed edit, one corrected edit, then completion; no extra inspection')
                self.assertEqual(file_observations, [actual], 'The first batch must not apply its valid second replacement')
                self.assertEqual(target.read_text(), 'const THEMES = {};\n' + actual.replace('return x + y;', 'return x - y;'))
                items = list(console.rpc_timeline_items.values())
                failure = next(item for item in items if item['kind'] == 'toolResult'
                    and 'Could not find edits[0]' in item.get('text', ''))
                self.assertIn('Failed', failure['title'])
                self.assertIn('Launcher source observation', failure['text'])
                entries = [json.loads(line) for path in (root / 'sessions').rglob('*.jsonl')
                           for line in path.read_text().splitlines()]
                saved = next(entry['message'] for entry in entries if entry.get('message', {}).get('role') == 'toolResult'
                    and entry['message'].get('toolCallId') == 'invented-anchor')
                self.assertTrue(saved['isError'])
                self.assertIn('Could not find edits[0]', saved['content'][0]['text'])
                self.assertEqual(saved['details']['launcherEditEvidence']['declarations'][0]['text'], 'const PAL = {')
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
