import tempfile
from pathlib import Path
from unittest import TestCase, mock
import launcher

class PreservedPi(TestCase):
    def test_uzu_uses_verified_old_runtime_after_general_pi_upgrade(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            binary=root/'runtimes/pi-uzu-0.84.2/node_modules/.bin/pi'
            binary.parent.mkdir(parents=True);binary.write_text('fixture')
            plan=launcher.LaunchPlan(run_id='preserved-test',backend='uzu',client='pi',
                model={'id':'fixture','name':'Fixture','backends':{'uzu':{}}},
                project=folder,context=16384,output=4096,reasoning='auto',port=18082,mode='ar',options={})
            with mock.patch.object(launcher,'STATE_DIR',root), mock.patch.dict(launcher.BINARIES,{'pi':'/new/pi'}), mock.patch.object(
                    launcher,'command_version',side_effect=lambda path:'0.84.2' if str(path)==str(binary) else '0.85.1'):
                launcher.build_pi_client(plan,launcher.ClientRoute('fixture','fixture','http://127.0.0.1/v1','test'))
            self.assertEqual(plan.client_argv[0],str(binary))

    def test_hub_rejects_an_arbitrary_executable_even_when_preserved_pi_is_selected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            preserved = root / 'runtimes/pi-uzu-0.84.2/node_modules/.bin/pi'
            preserved.parent.mkdir(parents=True)
            preserved.write_text('fixture'); preserved.chmod(0o755)
            alternate = root / 'unverified-pi'
            alternate.write_text('fixture'); alternate.chmod(0o755)
            plan = launcher.LaunchPlan(run_id='preserved-guard', backend='uzu', client='pi',
                model={'id':'fixture', 'name':'Fixture', 'backends':{'uzu':{}}},
                project=folder, context=16384, output=4096, reasoning='auto', port=18082, mode='ar', options={})
            plan.client_argv = [str(alternate), '--mode', 'rpc']
            manager = launcher.RunManager()
            with mock.patch.object(launcher, 'STATE_DIR', root), mock.patch.dict(launcher.BINARIES, {'pi':'/new/pi'}), \
                    mock.patch.object(launcher, 'command_version', side_effect=lambda path: '0.84.2' if str(path) == str(preserved) else '0.85.1'), \
                    mock.patch.object(launcher.subprocess, 'Popen') as spawn:
                with self.assertRaisesRegex(ValueError, 'executable changed'):
                    manager._launch_agent_console(plan, manager.cancel_event)
                spawn.assert_not_called()
