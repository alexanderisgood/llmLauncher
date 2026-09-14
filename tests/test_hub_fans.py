import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hub_fans import control_fans


class FanControlTests(unittest.TestCase):
    @staticmethod
    def _native_response(payload):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        return response

    def test_invalid_mode_never_executes(self):
        with patch('hub_fans.subprocess.run') as run:
            with self.assertRaises(ValueError):
                control_fans(SimpleNamespace(backend='omlx'), 'off')
            run.assert_not_called()

    def test_mtplx_uses_native_owner(self):
        response = self._native_response({'verified': True, 'current_mode': 'smart'})
        with patch('hub_fans.urllib.request.urlopen', return_value=response) as request, patch('hub_fans.subprocess.run') as run:
            result = control_fans(SimpleNamespace(backend='mtplx', port=18080, secrets={'apiKey':'test'}), 'smart')
            self.assertEqual(result['mode'], 'smart')
            self.assertEqual(json.loads(request.call_args.args[0].data), {'mode': 'smart'})
            run.assert_not_called()

    def test_mtplx_status_requires_known_mode(self):
        response = self._native_response({'ok': True})
        with patch('hub_fans.urllib.request.urlopen', return_value=response):
            with self.assertRaisesRegex(ValueError, 'unknown mode'):
                control_fans(SimpleNamespace(backend='mtplx', port=18080, secrets={}))

    def test_mtplx_rejects_non_object_response(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'[]'
        with patch('hub_fans.urllib.request.urlopen', return_value=response):
            with self.assertRaisesRegex(ValueError, 'malformed'):
                control_fans(SimpleNamespace(backend='mtplx', port=18080, secrets={}), 'max')

    def test_mtplx_rejects_unknown_mode_after_verified_change(self):
        response = self._native_response({'verified': True, 'current_mode': 'turbo'})
        with patch('hub_fans.urllib.request.urlopen', return_value=response):
            with self.assertRaisesRegex(ValueError, 'unknown mode'):
                control_fans(SimpleNamespace(backend='mtplx', port=18080, secrets={}), 'max')

    def test_mtplx_rejects_verified_change_that_reports_another_mode(self):
        response = self._native_response({'verified': True, 'current_mode': 'default'})
        with patch('hub_fans.urllib.request.urlopen', return_value=response):
            with self.assertRaisesRegex(ValueError, 'requested max'):
                control_fans(SimpleNamespace(backend='mtplx', port=18080, secrets={}), 'max')

    def test_unverified_native_change_is_error(self):
        response = self._native_response({'verified': False})
        with patch('hub_fans.urllib.request.urlopen', return_value=response):
            with self.assertRaises(ValueError):
                control_fans(SimpleNamespace(backend='mtplx', port=18080, secrets={}), 'max')

    def test_local_helper_uses_dedicated_runtime_module(self):
        completed = SimpleNamespace(returncode=0, stdout='{"mode":"max","smartAvailable":false}\n')
        with patch('hub_fans.subprocess.run', return_value=completed) as run:
            result = control_fans(SimpleNamespace(backend='omlx'), 'max')
        self.assertEqual(result, {'mode': 'max', 'smartAvailable': False})
        command = run.call_args.args[0]
        self.assertEqual(command[1].endswith('hub_fans_runtime.py'), True)
        self.assertEqual(command[2], 'max')

    def test_local_helper_rejects_unknown_mode(self):
        completed = SimpleNamespace(returncode=0, stdout='{"mode":"unknown","smartAvailable":false}\n')
        with patch('hub_fans.subprocess.run', return_value=completed):
            with self.assertRaisesRegex(ValueError, 'unknown mode'):
                control_fans(SimpleNamespace(backend='omlx'), 'max')

    def test_local_helper_rejects_mismatched_or_smart_mode(self):
        for mode in ('default', 'smart'):
            completed = SimpleNamespace(returncode=0, stdout=json.dumps(
                {'mode': mode, 'smartAvailable': False}))
            with self.subTest(mode=mode), patch('hub_fans.subprocess.run', return_value=completed):
                with self.assertRaisesRegex(ValueError, 'could not be verified'):
                    control_fans(SimpleNamespace(backend='omlx'), 'max')

    def test_local_helper_rejects_malformed_payload(self):
        completed = SimpleNamespace(returncode=0, stdout='[]')
        with patch('hub_fans.subprocess.run', return_value=completed):
            with self.assertRaisesRegex(ValueError, 'change not verified'):
                control_fans(SimpleNamespace(backend='omlx'), 'max')

    def test_missing_helper_is_actionable(self):
        with patch('hub_fans.subprocess.run', side_effect=FileNotFoundError):
            with self.assertRaisesRegex(ValueError, 'Enable fan control'):
                control_fans(SimpleNamespace(backend='omlx'), 'max')

if __name__ == '__main__':
    unittest.main()
