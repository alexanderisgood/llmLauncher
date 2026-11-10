"""Both Pi surfaces load the same process-local context policy."""
import json
import unittest
from unittest.mock import patch

import launcher


class PiContextPolicy(unittest.TestCase):
    def test_both_surfaces_share_policy_without_loading_hub_ui_in_terminal(self):
        for backend, model in [('whallm', 'Qwen3.8 Flash'), ('omlx', 'Qwen3.8-27B'), ('mtplx', 'Qwopus'), ('splash', 'Qwen3.8-27B · Splash')]:
            providers = []
            for surface in ('terminal', 'console'):
                with self.subTest(backend=backend, surface=surface):
                    plan = launcher.LaunchPlan(run_id='context-policy-fixture', backend=backend, client='pi',
                        model={'id':'fixture', 'name':model, 'backends':{}}, project='/tmp',
                        context=16384, output=4096, reasoning='medium', port=18082,
                        mode='ar', options={}, agent_host=surface)
                    with patch.dict(launcher.BINARIES, {'pi':'pi'}):
                        launcher.build_pi_client(plan, launcher.ClientRoute('fixture','fixture','http://127.0.0.1:18082/v1','fixture'))
                    extensions = [plan.client_argv[i+1] for i, value in enumerate(plan.client_argv) if value == '--extension']
                    shared = str(launcher.APP_DIR / 'pi-context-policy.js')
                    hub = str(launcher.APP_DIR / 'pi-hub-commands.js')
                    self.assertEqual(extensions.count(shared), 1)
                    self.assertEqual(hub in extensions, surface == 'console')
                    self.assertEqual('--mode' in plan.client_argv, surface == 'console')
                    providers.append(json.loads(plan.client_env['LLM_LAUNCHER_PI_PROVIDER']))
            self.assertEqual(providers[0], providers[1])
            self.assertEqual(providers[0].get('memoryCompaction', False), backend in {'omlx', 'mtplx'})
            self.assertEqual(providers[0].get('compactionRecovery', False), backend in {'omlx', 'mtplx', 'splash'})
        self.assertIn(launcher.APP_DIR / 'pi-context-policy.js', launcher.CONTROLLER_SOURCE_PATHS)


if __name__ == '__main__':
    unittest.main()
