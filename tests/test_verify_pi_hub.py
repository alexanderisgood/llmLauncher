"""Deterministic evidence/cleanup checks; no controller, engine, or model."""
import json
import shutil
import subprocess
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from tools import verify_pi_hub as screen


class PiHubScreen(unittest.TestCase):
    idle = {'streaming':False, 'compacting':False, 'pendingMessages':0}

    def item(self, title='Complete', kind='summary', revision=2, item_id='turn2'):
        return {'revision':revision, 'kind':kind, 'title':title, 'text':'Recorded evidence', 'itemId':item_id}

    def test_idle_without_new_native_completion_is_not_success(self):
        self.assertIsNone(screen.stage_completion('prompt', [], set(), 1, self.idle))
        self.assertIsNone(screen.stage_completion('prompt', [self.item(revision=1)], set(), 1, self.idle))
        self.assertIsNone(screen.stage_completion('prompt', [self.item()], {'turn2'}, 1, self.idle))
        self.assertIsNone(screen.stage_completion('prompt', [self.item()], set(), 1, {**self.idle,'streaming':True}))
        self.assertEqual(screen.stage_completion('prompt', [self.item()], set(), 1, self.idle)['state'], 'complete')

    def test_all_failed_summary_types_remain_failures_when_queue_is_empty(self):
        for title in ('Failed', 'Stopped', 'Repetition paused', 'Response limit', 'Tool call failed', 'Incomplete'):
            with self.subTest(title=title):
                evidence = self.item(title)
                result = screen.stage_completion('prompt', [evidence], set(), 1, self.idle)
                self.assertEqual(result, {'state':'failed', 'evidence':[evidence]})

    def test_compact_requires_new_context_ready_and_rejects_errors(self):
        self.assertIsNone(screen.stage_completion('compact', [self.item()], set(), 1, self.idle))
        self.assertIsNone(screen.stage_completion('compact', [self.item('Context ready','notice',1)], set(), 1, self.idle))
        result = screen.stage_completion('compact', [self.item('Context ready','notice')], set(), 1, self.idle)
        self.assertEqual(result['state'], 'complete')
        for title,kind in [('Compaction cancelled','notice'), ('Compaction failed','error'), ('Pi error','error')]:
            self.assertEqual(screen.stage_completion('compact', [self.item(title,kind)], set(), 1, self.idle)['state'], 'failed')

    def test_production_reducer_handles_deltas_and_reset(self):
        timeline = screen.Timeline()
        self.addCleanup(timeline.close)
        def envelope(revision, events, reset=False):
            return {'timelineVersion':1,'timelineRevision':revision,'nextTimelineRevision':revision,
                    'timelineBaseRevision':1,'timelineReset':reset,'timelineEvents':events}
        first = {**self.item('Thinking','thinking',1,'thought'), 'text':'First', 'operation':'replace'}
        self.assertEqual(timeline.apply(envelope(1,[first]))[0]['text'], 'First')
        delta = {**first,'revision':2,'text':' second','operation':'append'}
        self.assertEqual(timeline.apply(envelope(2,[delta]))[0]['text'], 'First second')
        final = self.item(revision=3)
        final['operation'] = 'replace'
        self.assertEqual([i['title'] for i in timeline.apply(envelope(3,[final],True))], ['Complete'])

    def test_cleanup_only_stops_owned_fixture_and_confirms_idle(self):
        hub = mock.Mock()
        hub.call.side_effect = [{'phase':'running','run':{'runId':'ours','project':'/tmp/fixture'}}, {'ok':True}, {'phase':'idle'}]
        self.assertEqual(screen.stop_owned_fixture(hub, 'ours', Path('/tmp/fixture')), 'unloaded')
        self.assertEqual(hub.call.call_args_list[1], mock.call('/api/stop', {}, timeout=60))
        hub.reset_mock(); hub.call.side_effect = None
        hub.call.return_value = {'phase':'running','run':{'runId':'other','project':'/tmp/other'}}
        with self.assertRaisesRegex(RuntimeError, 'no longer owns'):
            screen.stop_owned_fixture(hub, 'ours', Path('/tmp/fixture'))
        self.assertEqual(hub.call.call_count, 1)

    def tap(self, **changes):
        counts = {'tests':8, 'pass':8, 'fail':0, 'cancelled':0, 'skipped':0, 'todo':0, **changes}
        return 'TAP version 13\n' + ''.join(f'# {key} {value}\n' for key,value in counts.items())

    def test_oracle_requires_all_eight_passes_and_no_missing_or_duplicate_totals(self):
        def check(text, code=0):
            return screen.oracle_result(SimpleNamespace(returncode=code, stdout=text))['passed']
        self.assertTrue(check(self.tap()))
        self.assertFalse(check(self.tap(), 1))
        for changes in ({'tests':0,'pass':0}, {'tests':7,'pass':7}, {'pass':7,'fail':1},
                        {'skipped':1}, {'cancelled':1}, {'todo':1}):
            with self.subTest(changes=changes): self.assertFalse(check(self.tap(**changes)))
        self.assertFalse(check(self.tap().replace('# skipped 0\n','')))
        self.assertFalse(check(self.tap()+'# pass 8\n'))

    def test_zero_exit_before_tests_is_rejected_by_real_node_oracle(self):
        with tempfile.TemporaryDirectory(prefix='hub-oracle-test-') as directory:
            root = Path(directory)
            shutil.copyfile(screen.ROOT/'tests/fixtures/pi-coding/cache.test.cjs', root/'cache.test.cjs')
            (root/'cache.cjs').write_text('process.exit(0);\n')
            check = subprocess.run(['node','--test','--test-reporter=tap','cache.test.cjs'], cwd=root,
                                   capture_output=True,text=True,timeout=15)
            self.assertEqual(check.returncode, 0)
            self.assertFalse(screen.oracle_result(check)['passed'])

    def test_warm_follow_up_modification_fails_even_when_all_tests_pass(self):
        class FakeHub:
            stage = 0
            project = None
            def call(self, path, data=None, **kwargs):
                if path == '/api/session/plan': return {}
                if path == '/api/launch':
                    self.project = Path(data['project'])
                    return {'run':{'runId':'fixture'}}
                if path == '/api/agent-console/input':
                    self.stage += 1
                    (self.project/'cache.cjs').write_text('repair' if self.stage == 1 else 'warm changed repair')
                    return {}
                if path == '/api/status':
                    if self.project is None: return {'phase':'idle'}
                    return {'phase':'running','run':{'runId':'fixture','project':str(self.project)},
                            'agentConsoles':[{'ownerRunId':'fixture','surfaceId':'fixture'}],
                            'activity':{'recent':[{'id':str(self.stage),'statusCode':200,'result':'completed','state':'completed'}] if self.stage else []}}
                if path == '/api/agent-console/read':
                    revision = self.stage*2
                    return {'console':{'state':'running','streaming':False,'compacting':False,'pendingMessages':0,
                        'nextOffset':0,'timelineVersion':1,'timelineBaseRevision':1,'timelineRevision':revision,'nextTimelineRevision':revision,
                        'timelineEvents':[
                            {'revision':revision-1,'kind':'thinking','title':'Thinking','text':'Measured thought','itemId':f'think{self.stage}','operation':'replace'},
                            {'revision':revision,'kind':'summary','title':'Complete','text':'Finished','itemId':f'turn{self.stage}','operation':'replace'}]}}
                raise AssertionError(path)
        hub = FakeHub()
        with tempfile.TemporaryDirectory(prefix='hub-warm-test-') as directory:
            root = Path(directory); route = root/'route.json'; route.write_text('{}')
            args = SimpleNamespace(controller='fixture',output=root/'result',route=route,timeout=30,compact=False)
            with mock.patch.object(screen,'Hub',return_value=hub), \
                 mock.patch.object(screen.subprocess,'run',side_effect=[SimpleNamespace(returncode=1,stdout='baseline failed',stderr=''),
                     SimpleNamespace(returncode=0,stdout=self.tap(),stderr='')]) as node, \
                 mock.patch.object(screen,'stop_owned_fixture',return_value='unloaded'):
                try: self.assertFalse(screen.verify(args))
                finally:
                    if hub.project: shutil.rmtree(hub.project)
            result = json.loads((root/'result/result.json').read_text())
            self.assertTrue(result['testsPassed'])
            self.assertFalse(result['warmUnchanged'])
            self.assertNotEqual(result['repairSha256'], result['afterWarmSha256'])
            self.assertTrue(all('--test-reporter=tap' in call.args[0] for call in node.call_args_list))

    def test_startup_failure_retains_launch_owner_for_cleanup(self):
        with tempfile.TemporaryDirectory(prefix='hub-screen-test-') as directory:
            root = Path(directory); route = root/'route.json'; route.write_text('{}')
            hub = mock.Mock()
            hub.call.side_effect = [{'phase':'idle'}, {}, {'run':{'runId':'owned-startup'}}, RuntimeError('startup unavailable')]
            args = SimpleNamespace(controller='fixture',output=root/'result',route=route,timeout=30,compact=False)
            with mock.patch.object(screen,'Hub',return_value=hub), mock.patch.object(screen,'Timeline'), \
                 mock.patch.object(screen.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='failed fixture',stderr='')), \
                 mock.patch.object(screen,'stop_owned_fixture',return_value='unloaded') as stop:
                with self.assertRaisesRegex(RuntimeError,'startup unavailable'):
                    screen.verify(args)
            stop.assert_called_once()
            self.assertEqual(stop.call_args.args[1], 'owned-startup')
            result = json.loads((root/'result/result.json').read_text())
            self.assertEqual(result['cleanup'], 'unloaded')
            self.assertEqual(result['error'], 'startup unavailable')
            self.assertFalse(result['completed'])


if __name__ == '__main__':
    unittest.main()
