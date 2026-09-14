"""Distinguish lazy model startup without relaxing live request attribution."""
import copy
from types import SimpleNamespace
import unittest

import launcher


class OmlxStartupActivity(unittest.TestCase):
    def setUp(self):
        self.plan = SimpleNamespace(backend='omlx', model={
            'servedId': 'selected', 'backends': {'omlx': {'runtimeVersion': '0.6.4'}}})
        self.activity = {'active': [], 'queued': [], 'recent': [], 'engineResident': True}
        # Shape returned by native /admin/api/activity before its lazy load.
        self.snapshot = {'active_models': {'models': [], 'total_active_requests': 0,
                                           'total_waiting_requests': 0}}

    def merge(self, activity=None, snapshot=None):
        return launcher.merge_omlx_activity(self.plan,
            self.activity if activity is None else activity,
            self.snapshot if snapshot is None else snapshot)

    def test_native_empty_idle_snapshot_is_unloaded_not_an_identity_error(self):
        before = copy.deepcopy(self.activity)
        result = self.merge()
        self.assertEqual(result['engineTelemetry']['state'], 'unloaded')
        self.assertTrue(result['engineTelemetry']['available'])
        self.assertEqual(self.activity, before)
        self.assertEqual(result['active'], [])
        self.assertNotIn('tokensPerSecond', str(result))

    def test_empty_snapshot_cannot_hide_pending_or_unknown_work(self):
        for key in ('active', 'queued'):
            activity = {**self.activity, key: [{'id': 'pending'}]}
            self.assertEqual(self.merge(activity=activity)['engineTelemetry']['state'], 'unmatched')
        for key in ('total_active_requests', 'total_waiting_requests'):
            for value in (None, True, 1, -1, 'unknown'):
                with self.subTest(key=key, value=value):
                    snapshot = copy.deepcopy(self.snapshot)
                    snapshot['active_models'][key] = value
                    self.assertEqual(self.merge(snapshot=snapshot)['engineTelemetry']['state'], 'unmatched')
        self.plan.model['servedId'] = ''
        self.assertEqual(self.merge()['engineTelemetry']['state'], 'unmatched')

    def test_loading_and_loaded_states_require_one_exact_model(self):
        model = {'id': 'selected', 'is_loading': True, 'active_requests': 0}
        self.snapshot['active_models']['models'] = [model]
        self.assertEqual(self.merge()['engineTelemetry']['state'], 'loading')
        self.snapshot['active_models']['models'] = [model, model]
        self.assertEqual(self.merge()['engineTelemetry']['state'], 'unmatched')
        self.snapshot['active_models']['models'] = [{**model, 'id': 'different'}]
        self.assertEqual(self.merge()['engineTelemetry']['state'], 'unmatched')
        self.snapshot['active_models']['models'] = [{**model, 'is_loading': False}]
        self.assertEqual(self.merge()['engineTelemetry']['state'], 'idle')


if __name__ == '__main__':
    unittest.main()
