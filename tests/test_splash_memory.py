"""Splash's streamed GGUF storage is admitted as a bounded native budget."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import launcher
import resource_admission
from tests.helpers.resource_admission_harness import Fixture, GIB, model, request, snapshot


def streaming_estimate(_pack, context):
    return {
        'version': 1, 'ssdStreaming': True, 'modelBytes': 0,
        'ssdWeightBytes': 150 * GIB, 'kvCacheBytes': 0,
        'kvPrecision': 'native; included in Metal budget', 'parallelLanes': 4,
        'runtimeReserveBytes': 2 * GIB, 'nativeMemoryBudgetBytes': 32 * GIB,
        'estimatedWorkingSetBytes': 34 * GIB, 'contextTokens': context,
        'geometryReady': True, 'geometry': {'ready': True, 'splash': True},
        'basis': 'Native streamed plan',
    }


class SplashStreamedAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        services = replace(self.fixture.services, native=replace(
            self.fixture.services.native, splash_memory_estimate=streaming_estimate))
        self.domain = resource_admission.ResourceAdmission(self.fixture.domain.policy, services)
        self.item = model('splash')
        self.item['size'] = 150 * GIB
        self.item['splash']['ssdStreaming'] = True
        self.request = request('splash', context=131072)

    def estimate(self, headroom, metal=40 * GIB):
        raw = snapshot(headroom)
        raw['metalRecommendedWorkingSetBytes'] = metal
        resource = self.domain.public_session_resource(raw)
        return resource, self.domain.launch_memory_estimate(self.request, self.item, resource)

    def test_large_target_is_not_fully_resident_and_budget_tracks_headroom(self):
        high_resource, high = self.estimate(40 * GIB)
        low_resource, low = self.estimate(25 * GIB)
        for resource, estimate in ((high_resource, high), (low_resource, low)):
            with self.subTest(headroom=resource['headroomBytes']):
                self.assertEqual(estimate['ssdWeightBytes'], 150 * GIB)
                self.assertEqual(estimate['modelBytes'], 0)
                self.assertLessEqual(estimate['requiredHeadroomBytes'], resource['headroomBytes'])
                self.assertEqual(estimate['estimatedWorkingSetBytes'], estimate['nativeMemoryBudgetBytes'])
                decision = self.domain.session_memory_admission(
                    self.request, [self.item], resource, {'phase': 'idle'}, {'active': False})
                self.assertTrue(decision['launchable'])
                self.assertIn('stream from SSD', decision['detail'])
        self.assertEqual(high['nativeMemoryBudgetBytes'], 38 * GIB)
        self.assertLess(low['nativeMemoryBudgetBytes'], high['nativeMemoryBudgetBytes'])

    def test_metal_limit_caps_budget_and_below_floor_blocks(self):
        resource, estimate = self.estimate(40 * GIB, metal=20 * GIB)
        self.assertEqual(estimate['nativeMemoryBudgetBytes'], 19 * GIB)
        self.assertTrue(estimate['nativeMemoryBudgetReady'])
        resource, estimate = self.estimate(40 * GIB, metal=10 * GIB)
        self.assertFalse(estimate['nativeMemoryBudgetReady'])
        decision = self.domain.session_memory_admission(
            self.request, [self.item], resource, {'phase': 'idle'}, {'active': False})
        self.assertFalse(decision['launchable'])

    def test_low_or_unavailable_headroom_cannot_admit_streaming(self):
        for raw in (snapshot(13 * GIB), snapshot(40 * GIB, available=False)):
            with self.subTest(raw=raw):
                resource = self.domain.public_session_resource(raw)
                decision = self.domain.session_memory_admission(
                    self.request, [self.item], resource, {'phase': 'idle'}, {'active': False})
                self.assertFalse(decision['launchable'])
                self.assertFalse(decision['requiresAcknowledgement'])

    def test_legacy_pack_estimate_matches_unchanged_full_residency_contract(self):
        fixture = Fixture()
        resource = fixture.domain.public_session_resource(snapshot())
        args = (request('splash'), model('splash'), resource)
        self.assertEqual(fixture.domain.launch_memory_estimate(*args), fixture.legacy['launch_memory_estimate'](*args))


class SplashStreamedLaunchBudgetTests(unittest.TestCase):
    def make_plan(self, folder):
        item = model('splash')
        item['size'] = 150 * GIB
        item['splash'].update(id='local/Flash-Next', identity='source-proof', ssdStreaming=True)
        run_dir = Path(folder) / 'run'
        run_dir.mkdir()
        return launcher.LaunchPlan(
            run_id='streamed-splash-fixture', backend='splash', client='chat',
            model=item, project=folder, context=131072, output=1024,
            reasoning='medium', port=18081, mode='custom', options={},
            purpose='benchmark', run_dir=run_dir)

    def test_fresh_headroom_reaches_explicit_native_memory_argument(self):
        with tempfile.TemporaryDirectory() as folder:
            plan = self.make_plan(folder)
            with mock.patch.object(launcher.splash_runtime, 'inspect_install', return_value={'ready': True, 'version': '1.4.0'}), \
                    mock.patch.object(launcher.splash_runtime, 'inspect_model', return_value=plan.model['splash']), \
                    mock.patch.object(launcher.splash_runtime, 'doctor', return_value={}), \
                    mock.patch.object(launcher.splash_runtime, 'memory_estimate', side_effect=streaming_estimate), \
                    mock.patch.object(launcher, 'apple_resource_snapshot', return_value=snapshot(25 * GIB)) as sample:
                launcher.build_splash(plan, plan.model['backends']['splash'])
            sample.assert_called_once()
            config = json.loads((plan.run_dir / 'splash.json').read_text())
            memory = int(config['maxMemory'])
            reserve = 2 * GIB
            self.assertEqual(memory, 25 * GIB - reserve)
            self.assertLess(memory, 32 * GIB)

    def test_headroom_loss_before_launch_stops_before_private_config(self):
        with tempfile.TemporaryDirectory() as folder:
            plan = self.make_plan(folder)
            with mock.patch.object(launcher.splash_runtime, 'inspect_install', return_value={'ready': True, 'version': '1.4.0'}), \
                    mock.patch.object(launcher.splash_runtime, 'inspect_model', return_value=plan.model['splash']), \
                    mock.patch.object(launcher.splash_runtime, 'doctor', return_value={}), \
                    mock.patch.object(launcher.splash_runtime, 'memory_estimate', side_effect=streaming_estimate), \
                    mock.patch.object(launcher, 'apple_resource_snapshot', return_value=snapshot(13 * GIB)):
                with self.assertRaisesRegex(ValueError, 'Free memory before loading Splash'):
                    launcher.build_splash(plan, plan.model['backends']['splash'])
            self.assertFalse((plan.run_dir / 'splash.json').exists())


class SplashCacheAdmissionTests(unittest.TestCase):
    def test_dspine_admission_treats_unused_and_reclaimable_ram_as_one_budget(self):
        fixture = Fixture()
        services = replace(fixture.services, native=replace(
            fixture.services.native, splash_memory_estimate=launcher.splash_runtime.memory_estimate))
        domain = resource_admission.ResourceAdmission(fixture.domain.policy, services)
        visible = request('splash', client='omp', context=262144, acceleration='dspine')
        item = model('splash')
        item['splash'].update(targetBytes=15 * GIB, dspineTargetBytes=15_149_711_360)
        manager = mock.Mock()
        manager.hub_snapshot.return_value = {'phase': 'idle'}
        manager.warm_route_plan.return_value = {'canAttach': False}
        manager.public_warm_route.side_effect = lambda plan: plan
        with mock.patch.object(launcher, 'MANAGER', manager), \
                mock.patch.object(launcher, 'active_launcher_operation', return_value={'active': False}), \
                mock.patch.object(launcher, 'session_memory_admission', side_effect=domain.session_memory_admission):
            for unused in (4 * GIB, 24 * GIB):
                dashboard = launcher.session_dashboard_plan(
                    visible, [item], {**snapshot(30 * GIB), 'freeBytes': unused})
                resource = dashboard['resource']
                self.assertEqual(dashboard['admission']['decision'], 'ready')
                self.assertEqual(resource['headroomBytes'], 30 * GIB)
                self.assertEqual(resource['unusedMemoryBytes'], unused)
                self.assertEqual(resource['reclaimableCacheBytes'], 30 * GIB - unused)
                self.assertEqual(resource['inUseMemoryBytes'], 18 * GIB)
                self.assertEqual(dashboard['admission']['estimate']['osReserveBytes'], 2 * GIB)
            blocked = launcher.session_dashboard_plan(
                visible, [item], {**snapshot(29 * GIB), 'freeBytes': 4 * GIB})
        self.assertEqual(blocked['admission']['decision'], 'pressure')
        self.assertIn('29.0 GiB is available, including reclaimable cache', blocked['admission']['detail'])


if __name__ == '__main__':
    unittest.main()
