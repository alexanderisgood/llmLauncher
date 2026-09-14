"""Installed Pi: one bounded summary retry recovers overflow without a new task turn."""
import contextlib
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import launcher
import session_proxy


@unittest.skipUnless(os.environ.get('LLM_LAUNCHER_PI_INTEGRATION') == '1', 'Opt-in installed Pi')
class CompactionRecovery(unittest.TestCase):
    def test_truncated_checkpoint_retries_and_recovers_pending_follow_up(self):
        self.run_recovery(False)

    def test_second_truncation_keeps_original_history_and_pending_follow_up(self):
        self.run_recovery(True)

    def test_truncated_turn_prefix_retries_without_regenerating_history(self):
        self.run_recovery(False, truncate_part='prefix')

    def run_recovery(self, fail_again, truncate_part='history'):
        normal, summaries = [], []
        started, release = threading.Event(), threading.Event()
        checkpoint = 'CHECKPOINT_7182: graphics edits are applied but browser verification is still pending.'
        queued = 'After that, report which checks actually passed.'
        complete = f'## Goal\nVerify the graphics.\n## Progress\n{checkpoint}\n## Next Steps\nInspect the result before claiming success.'

        class Responder(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                summary = body['messages'][0].get('content') == session_proxy.PI_SUMMARIZATION_SYSTEM_PROMPT
                (summaries if summary else normal).append(body)
                self.close_connection = True
                if not summary and len(normal) == 1:
                    started.set()
                    release.wait(15)
                    payload = session_proxy.normalize_omlx_compactable_error(json.dumps({'error': {
                        'code': 'prefill_memory_exceeded', 'message': 'Prompt processing exceeds available memory',
                    }}).encode())
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers(); self.wfile.write(payload)
                    return
                truncated = summary and (len(summaries) == (1 if truncate_part == 'history' else 2) or fail_again)
                text = ('PARTIAL_CHECKPOINT_MUST_NOT_BE_SAVED' if truncated else complete) if summary else 'Verified the next step.'
                count = 4096 if truncated else 120
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                event = {'id': 'compaction-recovery', 'choices': [{'index': 0, 'delta': {'content': text}, 'finish_reason': None}]}
                self.wfile.write(('data: ' + json.dumps(event) + '\n\n').encode())
                event['choices'] = [{'index': 0, 'delta': {}, 'finish_reason': 'length' if truncated else 'stop'}]
                event['usage'] = {'prompt_tokens': 2000, 'completion_tokens': count, 'total_tokens': 2000 + count}
                self.wfile.write(('data: ' + json.dumps(event) + '\n\ndata: [DONE]\n\n').encode())

        server = ThreadingHTTPServer(('127.0.0.1', 0), Responder)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        manager = launcher.RunManager()
        try:
            with tempfile.TemporaryDirectory(prefix='pi-summary-recovery-') as directory, contextlib.ExitStack() as cleanup:
                root = Path(directory)
                config = root / 'config'; config.mkdir()
                saved_settings = json.dumps({'compaction': {'enabled': True, 'reserveTokens': 16384, 'keepRecentTokens': 20000}})
                (config / 'settings.json').write_text(saved_settings)
                evidence_path = str(root / 'evidence.txt')
                (root / 'evidence.txt').write_text('Saved fixture evidence.\n')
                session = root / 'seed.jsonl'
                entries = [{'type': 'session', 'version': 3, 'id': 'summary-recovery', 'timestamp': '2026-01-01T00:00:00Z', 'cwd': str(root)}]
                def add(message):
                    entries.append({'type': 'message', 'id': str(len(entries)), 'parentId': entries[-1].get('id'),
                        'timestamp': '2026-01-01T00:00:00Z', 'message': message})
                usage = {'input': 60000, 'output': 1000, 'cacheRead': 0, 'cacheWrite': 0, 'totalTokens': 61000,
                         'cost': {'input': 0, 'output': 0, 'cacheRead': 0, 'cacheWrite': 0, 'total': 0}}
                for index in range(8):
                    add({'role': 'user', 'content': [{'type': 'text', 'text': f'Continue graphics task {index}. {checkpoint}'}], 'timestamp': index * 1000})
                    assistant = {'role': 'assistant', 'provider': 'launcher-fixture', 'model': 'fixture', 'api': 'openai-completions',
                                 'stopReason': 'stop', 'usage': usage, 'timestamp': index * 1000,
                                 'content': [{'type': 'text', 'text': 'Verified saved code and evidence.\n' * 300}]}
                    if index == 0:
                        assistant['content'].append({'type': 'toolCall', 'id': 'evidence-read', 'name': 'read', 'arguments': {'path': evidence_path}})
                        assistant['stopReason'] = 'toolUse'
                    add(assistant)
                    if index == 0:
                        add({'role': 'toolResult', 'toolCallId': 'evidence-read', 'toolName': 'read', 'content': [{'type': 'text', 'text': 'Saved fixture evidence.'}], 'isError': False, 'timestamp': 0})
                original = ''.join(json.dumps(entry) + '\n' for entry in entries)
                session.write_text(original)
                plan = launcher.LaunchPlan(run_id='summary-recovery', backend='omlx', client='pi',
                    model={'id': 'fixture', 'name': 'Qwopus fixture', 'backends': {}}, project=str(root),
                    context=131072, output=80000, reasoning='medium', port=server.server_port,
                    mode='ar', options={}, agent_host='console', pi_session_file=str(session))
                with mock.patch.dict(launcher.BINARIES, {'pi': shutil.which('pi')}):
                    launcher.build_pi_client(plan, launcher.ClientRoute('launcher-fixture', 'fixture', f'http://127.0.0.1:{server.server_port}/v1', 'fixture-key'))
                plan.client_argv += ['--no-tools', '--no-extensions', '--no-skills', '--no-prompt-templates', '--no-themes',
                                     '--no-context-files', '--no-approve', '--offline', '--system-prompt', 'Isolated recovery fixture only.']
                plan.client_env.update({'PI_CODING_AGENT_DIR': str(config), 'PI_CODING_AGENT_SESSION_DIR': str(root / 'sessions'),
                                       'PI_OFFLINE': '1', 'PI_TELEMETRY': '0'})
                manager.plan = plan
                manager.state = {'phase': 'running', 'run': plan.public(), 'events': []}
                manager.attachments[plan.run_id] = launcher.SurfaceAttachment(owner_run_id=plan.run_id, plan=plan, primary=True)
                with mock.patch.dict(os.environ, {'PATH': os.environ['PATH']}, clear=True):
                    console = manager._launch_agent_console(plan, manager.cancel_event)
                cleanup.callback(manager._stop_agent_console_process, console)
                def wait(predicate):
                    deadline = time.monotonic() + 25
                    while time.monotonic() < deadline:
                        if predicate(): return
                        time.sleep(.025)
                    self.fail(bytes(console.output).decode(errors='replace')[-6000:])
                manager._write_pi_rpc_console(console, {'command': 'prompt', 'message': 'Continue verifying the graphics.'})
                wait(started.is_set)
                manager._write_pi_rpc_console(console, {'command': 'prompt', 'message': queued})
                release.set()
                wait(lambda: len(summaries) >= 2 and not console.rpc_streaming and not console.rpc_prompt_inflight and not console.rpc_compacting)
                if not fail_again:
                    wait(lambda: len(normal) == 3 and not console.rpc_pending_messages and not console.rpc_follow_up_queue)
                saved = [json.loads(line) for line in session.read_text().splitlines()]
                compactions = [entry for entry in saved if entry.get('type') == 'compaction']
                self.assertEqual(len(summaries), 2 if fail_again else 3,
                                 'One history retry, then the native split-turn summary only after success')
                for body in summaries:
                    self.assertEqual(body['max_tokens'], 4096)
                    self.assertIn(checkpoint, json.dumps(body))
                    self.assertNotIn('PARTIAL_CHECKPOINT_MUST_NOT_BE_SAVED', json.dumps(body))
                for body in summaries[:2 if truncate_part == 'history' else 1]:
                    self.assertIn(evidence_path, json.dumps(body))
                self.assertIn('at most 500 words', json.dumps(summaries[1 if truncate_part == 'history' else 2]))
                for body in normal:
                    self.assertGreater(body['max_tokens'], 4096, 'Summary allowance does not leak into task requests')
                    self.assertLessEqual(body['max_tokens'], 80000, 'Pi may reserve context space within the selected task allowance')
                self.assertEqual(json.loads(plan.client_env['LLM_LAUNCHER_PI_PROVIDER'])['model']['maxTokens'], 80000)
                self.assertNotIn('PARTIAL_CHECKPOINT_MUST_NOT_BE_SAVED', session.read_text())
                self.assertEqual(saved[:len(entries)], entries, 'Original transcript entries remain intact')
                self.assertEqual((config / 'settings.json').read_text(), saved_settings)
                self.assertIsNone(console.process.poll())
                if fail_again:
                    self.assertEqual(len(normal), 1, 'Do not resume against an incomplete checkpoint')
                    self.assertFalse(compactions)
                    self.assertIn(queued, console.rpc_follow_up_queue)
                else:
                    self.assertEqual(len(compactions), 1)
                    self.assertFalse(compactions[0].get('fromHook'), 'Native compaction preserves native file tracking across later compactions')
                    self.assertIn(evidence_path, compactions[0]['details']['readFiles'])
                    self.assertIn(checkpoint, compactions[0]['summary'])
                    self.assertEqual(compactions[0]['usage']['output'], 4336, 'Summary accounting includes the failed 4096-token attempt and both native summary parts')
                    self.assertIn(checkpoint, json.dumps(normal[1]))
                    self.assertIn(queued, json.dumps(normal[2]))
                    new_users = [entry['message'] for entry in saved[len(entries):] if entry.get('message', {}).get('role') == 'user']
                    self.assertEqual(len(new_users), 2, 'One original request and one actual user follow-up; no synthetic repair turn')
                    self.assertEqual(len(normal), 3, 'Failed request, native recovery, then the queued user message')
                print('Compaction retry:', {'failedTwice': fail_again, 'summaryRequests': len(summaries), 'taskRequests': len(normal), 'checkpoints': len(compactions)})
        finally:
            release.set(); server.shutdown(); server.server_close()


if __name__ == '__main__': unittest.main()
