"""Passive Rapid MLX inventory/selection with generated files and metadata."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

import launcher
from tests.test_runtime_catalog import PrivateRuntimeFixture


class RapidMLXDiscoveryTests(unittest.TestCase):
    def inspection(self, binary, *, ready=True):
        return {"binary":str(binary), "python":"/generated/python3", "version":"0.16.9",
                "ready":ready, "identity":{"generated":True},
                "reason":"Generated package metadata verified" if ready else "Generated missing dependency"}

    def test_candidate_order_uses_managed_install_then_standard_paths(self):
        specs = launcher.RUNTIME_CANDIDATE_SPECS['rapidmlx']
        self.assertEqual(specs[0][1], str(launcher.MANAGED_RUNTIMES_DIR / 'rapidmlx-0.16.9/bin/rapid-mlx'))
        self.assertEqual([row[1] for row in specs[2:]], ['~/.rapid-mlx/bin/rapid-mlx',
            '~/.local/bin/rapid-mlx', '/opt/homebrew/bin/rapid-mlx', 'rapid-mlx'])

    def test_registry_has_all_clients_and_tracks_passive_adapter_source(self):
        launcher.validate_adapter_registries()
        self.assertEqual(launcher.ENGINE_ADAPTERS['rapidmlx'].label, 'Rapid MLX')
        self.assertEqual(set(launcher.CLIENT_SUPPORT['rapidmlx']), {'pi', 'omp', 'opencode', 'codex', 'chat'})
        self.assertTrue(all(row['supported'] for row in launcher.CLIENT_SUPPORT['rapidmlx'].values()))
        self.assertIn(Path(launcher.APP_DIR) / 'rapidmlx_runtime.py', launcher.CONTROLLER_SOURCE_PATHS)

    def test_version_reads_helper_metadata_without_executing_cli(self):
        binary='/generated/bin/rapid-mlx'
        helper=SimpleNamespace(inspect_runtime=mock.Mock(return_value=self.inspection(binary)))
        with mock.patch.dict('sys.modules', {'rapidmlx_runtime':helper}), \
                mock.patch.object(launcher.runtime_probes, 'probe_output', side_effect=AssertionError('CLI probe is forbidden')):
            self.assertEqual(launcher.command_version(binary), 'Rapid MLX 0.16.9')
            self.assertFalse(launcher.rapidmlx_runtime_contract(None)['ready'])
        helper.inspect_runtime.assert_called_once_with(binary)

    def test_runtime_manager_is_local_resident_and_rejects_unready_selection(self):
        with tempfile.TemporaryDirectory(prefix='rapidmlx-inventory-') as folder:
            generated=PrivateRuntimeFixture(folder)
            binary=generated.binary_paths['rapidmlx']
            helper=SimpleNamespace(inspect_runtime=mock.Mock(return_value=self.inspection(binary)))
            with generated.patches(), mock.patch.dict('sys.modules', {'rapidmlx_runtime':helper}):
                before=generated.snapshot()
                catalog=generated.catalog()
                inventory=catalog.runtime_inventory()
                rapid=next(row for row in inventory['runtimes'] if row['id']=='rapidmlx')
                self.assertEqual(rapid['label'], 'Rapid MLX')
                self.assertTrue(rapid['selected']['launchReady'])
                self.assertEqual(rapid['update']['docsUrl'], 'https://github.com/raullenchai/Rapid-MLX')
                self.assertEqual(rapid['release']['version'], '0.16.9')
                self.assertIn('Local model server', [item['label'] for item in rapid['checks']])
                self.assertNotIn('SSD', str(rapid))
                self.assertFalse(inventory['safety']['startsApplications'])
                self.assertFalse(inventory['safety']['usesNetwork'])
                self.assertEqual(generated.snapshot(), before)
                helper.inspect_runtime.return_value=self.inspection(binary, ready=False)
                rejected=next(row for row in catalog.runtime_inventory()['runtimes'] if row['id']=='rapidmlx')
                self.assertEqual(rejected['level'], 'blocked')
                self.assertIn('needs attention', rejected['headline'])
                candidate=catalog.runtime_candidates('rapidmlx')[0]
                with mock.patch.object(launcher, 'atomic_json', side_effect=AssertionError('Selection must not write')), \
                        self.assertRaisesRegex(ValueError, 'missing dependency'):
                    launcher.select_runtime_candidate({'runtime':'rapidmlx', 'candidateId':candidate['id'],
                        'confirmation':f"select:{candidate['id']}"})


if __name__ == '__main__':
    unittest.main()
