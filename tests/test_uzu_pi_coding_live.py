"""Explicit real-model coding/queue test in an isolated disposable project.

Uses normal primary Pi launch and builtin file tools restricted by a test-only
extension. Only the implementation file is editable; tests run in a sandbox.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from test_uzu_candidate_live_boundary import private_session_files, termination_runs_cleanup

ROOT = Path(__file__).resolve().parents[1]
PATCH_ROOT = ROOT / 'runtime_patches/uzu/0.5.23'


@unittest.skipUnless(os.environ.get('LLM_LAUNCHER_UZU_PI_CODING_LIVE') == '1',
                     'requires explicit real-model coding test and exclusive idle controller')
class UzuPiCodingLiveTests(unittest.TestCase):
    def test_code_edit_tests_queued_followup_and_stop_recovery(self):
        sys.path.insert(0, str(PATCH_ROOT))
        import candidate_qualification as candidate
        spec = importlib.util.spec_from_file_location('uzu_pi_coding_app', ROOT / 'launcher.py')
        app = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = app
        spec.loader.exec_module(app)
        with candidate.exclusive_controller_lock(app.STATE_DIR / 'controller-instance.lock'), \
             termination_runs_cleanup(), private_session_files(), \
             tempfile.TemporaryDirectory(prefix='uzu-pi-coding-') as directory:
            root = Path(directory).resolve()
            project, config = root / 'project', root / 'config'
            project.mkdir(); config.mkdir()
            for name in ('cache.cjs', 'cache.test.cjs'):
                shutil.copyfile(ROOT / 'tests/fixtures/pi-coding' / name, project / name)
            audit = root / 'tool-audit.jsonl'
            original_source = (project / 'cache.cjs').read_bytes()
            original_tests = (project / 'cache.test.cjs').read_bytes()
            models = app.uzu_model_records(app.load_benchmark_records())
            payload = {**candidate.request(65536), 'client':'pi', 'agentHost':'console', 'project':str(project)}
            admission = app.session_dashboard_plan(payload, models).get('admission', {})
            self.assertTrue(app.strict_model_load_admission_ready(admission), admission)
            app.require_session_launch_admission(payload, admission)
            plan = app.normalized_request(payload, models, purpose='session')
            plan.client_argv.extend([
                '--no-session', '--tools', 'read,edit,write,run_tests', '--no-extensions', '--no-skills',
                '--no-prompt-templates', '--no-themes', '--no-context-files', '--no-approve', '--offline',
                '--extension', str(ROOT / 'tests/fixtures/pi-coding-policy.mjs'),
                '--system-prompt', 'Complete the requested coding task using only read, edit, write, and run_tests. '
                'The project contains cache.cjs and cache.test.cjs. Only cache.cjs may be edited. '
                'Use run_tests with no arguments to test changes. Do not use shell commands or external files.',
            ])
            plan.client_env.update({'PI_CODING_AGENT_DIR':str(config),
                'PI_CODING_AGENT_SESSION_DIR':str(root / 'sessions'), 'PI_OFFLINE':'1', 'PI_TELEMETRY':'0',
                'LLM_LAUNCHER_PI_FIXTURE_ROOT':str(project), 'LLM_LAUNCHER_PI_FIXTURE_AUDIT':str(audit)})
            console = None
            started = time.monotonic()
            stage = 'startup'
            succeeded = False
            try:
                with mock.patch.dict(os.environ, {'PATH':os.environ['PATH']}, clear=True):
                    app.MANAGER.start(plan)
                    deadline = time.monotonic() + 120
                    while app.MANAGER.snapshot().get('phase') != 'running':
                        status = app.MANAGER.snapshot()
                        self.assertNotIn(status.get('phase'), {'idle','failed','error'}, status.get('message'))
                        self.assertLess(time.monotonic(), deadline, 'Coding-test startup timed out')
                        time.sleep(0.25)
                console = app.MANAGER.agent_consoles[plan.run_id]
                print('Normal Uzu Pi coding session ready: 64K, 38 GiB guard, isolated project.', flush=True)

                def send(command, message=''):
                    return app.MANAGER.write_agent_console({'ownerRunId':plan.run_id,
                        'surfaceId':plan.run_id,'command':command,'message':message})

                def wait_for(predicate, label, seconds=600):
                    deadline = time.monotonic() + seconds
                    last_report = time.monotonic()
                    while time.monotonic() < deadline:
                        if predicate():
                            return
                        self.assertIsNone(console.process.poll(), 'Pi exited before ' + label)
                        self.assertEqual(app.MANAGER.snapshot().get('phase'), 'running')
                        if time.monotonic() - last_report > 20:
                            count = len(audit.read_text().splitlines()) if audit.exists() else 0
                            thinking = sum(len(item.get('text','')) for item in console.rpc_timeline_items.values()
                                if item['kind']=='thinking')
                            print(f'Coding check: {label}; {count} audited tool events; {thinking} retained reasoning characters.', flush=True)
                            last_report = time.monotonic()
                        time.sleep(0.1)
                    self.fail('Timed out: ' + label)

                def reduced_items():
                    result = subprocess.run([shutil.which('node'), '-e',
                        "const fs=require('fs'),t=require('./pi_timeline.js');"
                        "process.stdout.write(JSON.stringify(t.applyTimelineEnvelope(t.emptyTimeline(),"
                        "JSON.parse(fs.readFileSync(0,'utf8'))).state.items));"],
                        input=json.dumps(console.output_slice(0)),text=True,capture_output=True,cwd=ROOT,timeout=10)
                    self.assertEqual(result.returncode,0,result.stderr)
                    return json.loads(result.stdout)

                task = ('Read cache.cjs and cache.test.cjs, then repair TTLCache. It must enforce a positive '
                    'integer capacity and finite nonnegative TTL, implement expiry at now >= expires, '
                    'treat zero TTL as removal, refresh LRU recency on reads and overwrites without extending '
                    'TTL on reads, purge expired entries before eviction and size reporting, and preserve '
                    'falsy values and object keys. Keep the existing public API. Do not change tests. '
                    'Run the tests before and after your edit, and finish with a concise explanation and the test result.')
                stage = 'coding and queued follow-up'
                send('prompt',task)
                wait_for(lambda: console.rpc_streaming, 'first coding response',30)
                queued = send('prompt','Without using tools, explain the expiry boundary and which key gets evicted when capacity is full. Two sentences only.')
                self.assertEqual(queued['pendingMessages'],1)
                wait_for(lambda: not console.rpc_streaming and not console.rpc_prompt_inflight
                    and not console.rpc_follow_up_queue and not console.rpc_queued_prompt_message,
                    'coding task and queued follow-up')
                self.assertFalse(console.rpc_queue_paused, 'Coding turn ended with a protocol error')
                rows = [json.loads(line) for line in audit.read_text().splitlines()]
                self.assertTrue(all(row['allowed'] for row in rows if row['kind'] == 'tool'))
                self.assertTrue(any(row['kind']=='tool' and row['name'] in ('edit','write') for row in rows))
                test_runs = [row for row in rows if row['kind']=='tests']
                self.assertGreaterEqual(len(test_runs),2,'Pi must run tests before and after editing')
                self.assertNotEqual(test_runs[0]['code'],0,'The original fixture must expose a real bug')
                self.assertEqual(test_runs[-1]['code'],0,'Agent must finish with passing tests')
                self.assertTrue(test_runs[-1]['complete'],'All eight fixed tests must actually complete')
                self.assertNotEqual((project / 'cache.cjs').read_bytes(),original_source)
                self.assertEqual((project / 'cache.test.cjs').read_bytes(),original_tests)
                items = reduced_items()
                answers = [item for item in items if item['kind']=='answer']
                self.assertGreaterEqual(len(answers),2,'Both coding and queued answers must remain visible')
                self.assertTrue(any(item['kind']=='thinking' for item in items))
                self.assertTrue(any(item['kind']=='toolResult' for item in items))
                print(f'Coding edit and fixed tests passed; queued answer retained. {time.monotonic()-started:.1f}s including startup.',flush=True)

                # Exercise Stop against an actually streaming model response,
                # not an idle RPC acknowledgement or a fake server.
                stage = 'stop and recovery'
                event_revision = console.rpc_timeline_revision
                send('prompt','Without tools, count from 1 to 2000, writing every number separately.')
                wait_for(lambda: console.rpc_streaming and any(event.get('text') and event['kind'] in ('thinking','answer')
                    for event in console.timeline_slice(event_revision)['timelineEvents']), 'active response to interrupt',30)
                send('prompt','This queued message must not run before explicit recovery.')
                send('abort')
                wait_for(lambda: not console.rpc_streaming and not console.rpc_prompt_inflight,'abort terminal',30)
                self.assertTrue(console.rpc_queue_paused)
                send('clear_queue')
                previous_answers = len([item for item in reduced_items() if item['kind']=='answer'])
                send('prompt','Without tools, what is 41 + 1? Answer with the number only.')
                wait_for(lambda: not console.rpc_streaming and not console.rpc_prompt_inflight,'post-stop recovery',60)
                final_items = reduced_items()
                final_answers = [item for item in final_items if item['kind']=='answer']
                self.assertGreater(len(final_answers),previous_answers)
                self.assertEqual(final_answers[-1]['text'].strip(),'42')
                self.assertTrue(all(any(new.get('itemId')==old.get('itemId') and new.get('text')==old.get('text')
                    for new in final_answers) for old in answers),'Earlier answers disappeared after Stop/recovery')
                print('Real model Stop paused the queue; explicit recovery succeeded without losing prior answers.',flush=True)
                stage = 'completed'
                succeeded = True
            finally:
                app.MANAGER.stop()
                # Retain generated-test evidence for diagnosis; never raw
                # terminal output, provider config, project data or credentials.
                report = {'stage':stage,'passed':succeeded,'elapsedSeconds':round(time.monotonic()-started,3),
                    'toolAudit':[json.loads(line) for line in audit.read_text().splitlines()] if audit.exists() else [],
                    'timeline':console.timeline_slice(0) if console is not None else None,
                    'generatedSource':(project / 'cache.cjs').read_text(),
                    'modelStopped':app.MANAGER.process is None or app.MANAGER.process.poll() is not None,
                    'piStopped':console is None or console.process.poll() is not None}
                serialized = json.dumps(report)
                for value in plan.secrets.values():
                    if isinstance(value,str) and len(value)>8:
                        serialized = serialized.replace(value,'[redacted]')
                app.atomic_json(ROOT / 'build/uzu-pi-coding/last-run.json',json.loads(serialized))
                app.dispose_plan_secrets(plan)
                self.assertEqual(app.MANAGER.snapshot().get('phase'),'idle')
                if console is not None:
                    self.assertIsNotNone(console.process.poll())
                self.assertTrue(app.MANAGER.process is None or app.MANAGER.process.poll() is not None)
                print('Coding-test Pi and Uzu stopped cleanly.',flush=True)


if __name__ == '__main__':
    unittest.main()
