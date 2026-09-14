"""Opt-in installed Pi: repeated native reads add evidence to the next turn only."""
import contextlib
import hashlib
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


def message_text(message):
    content = message.get('content') or ''
    if isinstance(content, str):
        return content
    return '\n'.join(block.get('text', '') for block in content if isinstance(block, dict))


@unittest.skipUnless(os.environ.get('LLM_LAUNCHER_PI_INTEGRATION') == '1', 'Opt-in installed Pi')
class InstalledProgressCheck(unittest.TestCase):
    def test_native_read_cycle_note_joins_next_natural_request_without_extra_turn(self):
        requests, errors = [], []
        files = {'a.txt': 'ALPHA_NATIVE_EVIDENCE_6172\n', 'b.txt': 'BETA_NATIVE_EVIDENCE_8049\n'}
        prompt = 'Inspect the two local fixture files and report the observed evidence.'
        completed = 'Completed the fixture inspection with both observed values.'

        class Responder(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append(body)
                number = len(requests)
                self.close_connection = True
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Connection', 'close')
                self.end_headers()

                def chunk(delta, finish=None):
                    event = {'id': 'progress-fixture', 'choices': [
                        {'index': 0, 'delta': delta, 'finish_reason': finish}]}
                    self.wfile.write(('data: ' + json.dumps(event) + '\n\n').encode())

                try:
                    chunk({'role': 'assistant'})
                    if number <= 6:
                        path = ('a.txt', 'b.txt')[(number - 1) % 2]
                        chunk({'tool_calls': [{'index': 0, 'id': f'native-read-{number}',
                            'type': 'function', 'function': {'name': 'read',
                            'arguments': json.dumps({'path': path})}}]})
                        chunk({}, 'tool_calls')
                    else:
                        # The seventh request follows read 6 normally. A forced
                        # extra turn is an error even if it produces valid text.
                        if number != 7:
                            errors.append(f'Unexpected extra provider request {number}')
                        chunk({'content': completed})
                        chunk({}, 'stop')
                    self.wfile.write(b'data: [DONE]\n\n')
                except (BrokenPipeError, ConnectionResetError) as error:
                    errors.append(type(error).__name__)

        server = ThreadingHTTPServer(('127.0.0.1', 0), Responder)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        manager = launcher.RunManager()
        try:
            with tempfile.TemporaryDirectory(prefix='pi-native-progress-') as directory, \
                    contextlib.ExitStack() as cleanup:
                root = Path(directory)
                for name, content in files.items():
                    (root / name).write_text(content)
                config = root / 'config'
                config.mkdir()
                (config / 'settings.json').write_text('{}')
                plan = launcher.LaunchPlan(run_id='native-progress-fixture', backend='omlx', client='pi',
                    model={'name': 'Fixture', 'id': 'fixture', 'backends': {}}, project=str(root),
                    context=16384, output=1024, reasoning='off', port=server.server_port,
                    mode='ar', options={}, agent_host='console')
                binary = shutil.which('pi')
                self.assertIsNotNone(binary, 'Install Pi before enabling this integration test')
                with mock.patch.dict(launcher.BINARIES, {'pi': binary}):
                    launcher.build_pi_client(plan, launcher.ClientRoute('launcher-fixture', 'fixture',
                        f'http://127.0.0.1:{server.server_port}/v1', 'local-fixture-key'))
                plan.client_argv += ['--tools', 'read', '--no-extensions', '--no-skills',
                    '--no-prompt-templates', '--no-themes', '--no-context-files', '--no-approve',
                    '--offline', '--system-prompt', 'Isolated native read fixture only.']
                plan.client_env.update({'PI_CODING_AGENT_DIR': str(config),
                    'PI_CODING_AGENT_SESSION_DIR': str(root / 'sessions'),
                    'PI_OFFLINE': '1', 'PI_TELEMETRY': '0'})
                manager.plan = plan
                manager.state = {'phase': 'running', 'run': plan.public(), 'events': []}
                manager.attachments[plan.run_id] = launcher.SurfaceAttachment(
                    owner_run_id=plan.run_id, plan=plan, primary=True)
                with mock.patch.dict(os.environ, {'PATH': os.environ['PATH']}, clear=True):
                    console = manager._launch_agent_console(plan, manager.cancel_event)
                cleanup.callback(manager._stop_agent_console_process, console)
                manager.write_agent_console({'ownerRunId': plan.run_id, 'surfaceId': plan.run_id,
                    'command': 'prompt', 'message': prompt})
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if (console.rpc_settle_revision and not console.rpc_streaming
                            and not console.rpc_prompt_inflight):
                        break
                    time.sleep(.025)
                else:
                    self.fail(bytes(console.output).decode(errors='replace')[-6000:])

                self.assertEqual(errors, [])
                self.assertEqual(len(requests), 7, 'Six reads, then one natural completion request')
                self.assertIsNone(console.process.poll(), 'The existing Pi process remains alive')
                self.assertFalse(console.rpc_follow_up_queue)
                self.assertFalse(console.rpc_pending_messages)
                self.assertFalse(console.rpc_loop_stop_reason)
                self.assertFalse(console.rpc_tool_format_error)
                for body in requests:
                    self.assertEqual([tool['function']['name'] for tool in body['tools']], ['read'])
                for index, body in enumerate(requests):
                    tool_results = [message for message in body['messages'] if message['role'] == 'tool']
                    self.assertEqual(len(tool_results), index, 'Each request follows one real native read')
                    for result_index, result in enumerate(tool_results):
                        expected = files[('a.txt', 'b.txt')[result_index % 2]].strip()
                        self.assertIn(expected, message_text(result))

                entries = [json.loads(line) for path in (root / 'sessions').rglob('*.jsonl')
                           for line in path.read_text().splitlines()]
                notes = [entry for entry in entries if entry.get('type') == 'custom_message'
                         and entry.get('customType') == 'launcher-progress-check']
                self.assertEqual(len(notes), 1, 'Exactly one evidence-based progress note is saved')
                note = notes[0]
                self.assertTrue(note['display'])
                evidence = note.get('details') or {}
                self.assertEqual(evidence.get('cycles'), 3)
                self.assertEqual([(item['tool'], item['input']) for item in evidence.get('actions', [])],
                                 [('read', {'path': 'a.txt'}), ('read', {'path': 'b.txt'})])
                content = message_text(note)
                self.assertTrue(content)
                for body in requests[:6]:
                    self.assertFalse(any(content in message_text(message) for message in body['messages']),
                                     'No progress note appears before three completed cycles')
                seventh = requests[6]['messages']
                note_indices = [index for index, message in enumerate(seventh)
                                if content in message_text(message)]
                self.assertEqual(len(note_indices), 1, 'The note reaches model context exactly once: '
                                 + json.dumps({'note': content, 'messages': seventh[-3:]}))
                last_result = max(index for index, message in enumerate(seventh) if message['role'] == 'tool')
                self.assertGreater(note_indices[0], last_result, 'All six native results precede the note')

                saved_results = [entry['message'] for entry in entries
                                 if entry.get('message', {}).get('role') == 'toolResult']
                self.assertEqual(len(saved_results), 6)
                self.assertTrue(all(not result.get('isError') for result in saved_results))
                for action, result in zip(evidence['actions'], saved_results[:2]):
                    encoded = json.dumps(result['content'], ensure_ascii=False, separators=(',', ':')).encode()
                    self.assertEqual(action['resultHash'], hashlib.sha256(encoded).hexdigest(),
                                     'The note fingerprints the actual native read output')
                self.assertEqual([result['toolCallId'] for result in saved_results],
                                 [f'native-read-{number}' for number in range(1, 7)])
                saved_assistants = [entry['message'] for entry in entries
                                    if entry.get('message', {}).get('role') == 'assistant']
                self.assertEqual(len(saved_assistants), 7, 'No abort, retry, or unsolicited assistant turn')
                self.assertEqual(saved_assistants[-1]['stopReason'], 'stop')
                self.assertIn(completed, message_text(saved_assistants[-1]))
                self.assertEqual(len([entry for entry in entries
                    if entry.get('message', {}).get('role') == 'user']), 1)
                timeline = list(console.rpc_timeline_items.values())
                visible_notes = [item for item in timeline if item.get('title') == 'Progress check']
                self.assertEqual(len(visible_notes), 1, 'The Hub displays the same progress note once')
                self.assertIn(content, visible_notes[0]['text'])
                self.assertFalse(any(item.get('title') == 'Repetition paused' for item in timeline))
                for name, expected in files.items():
                    self.assertEqual((root / name).read_text(), expected, 'Inspection does not change files')
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
