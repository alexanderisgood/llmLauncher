"""Actual installed Pi commands and extension menus, isolated from user settings."""
import contextlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest import mock

import launcher


@unittest.skipUnless(os.environ.get('LLM_LAUNCHER_PI_INTEGRATION') == '1', 'Opt-in installed Pi')
class PiSlashCommands(unittest.TestCase):
    def test_native_commands_and_token_speed_custom_menu(self):
        manager = launcher.RunManager()
        with tempfile.TemporaryDirectory(prefix='pi-slash-test-') as directory, contextlib.ExitStack() as cleanup:
            root = Path(directory)
            config = root / 'config'; config.mkdir()
            (config / 'settings.json').write_text('{}')
            plan = launcher.LaunchPlan(run_id='slash-fixture', backend='omlx', client='pi',
                model={'name':'fixture','id':'fixture','backends':{}}, project=str(root),
                context=8192, output=1024, reasoning='off', port=1, mode='ar', options={}, agent_host='console')
            with mock.patch.dict(launcher.BINARIES, {'pi':shutil.which('pi')}):
                launcher.build_pi_client(plan, launcher.ClientRoute('launcher-fixture','fixture','http://127.0.0.1:1/v1','test-local-key'))
            plan.client_argv.extend(['--no-tools','--no-extensions','--no-skills','--no-prompt-templates','--no-themes',
                '--no-context-files','--no-approve','--offline','--system-prompt','Command fixture only.'])
            speed = Path.home()/'.pi/agent/npm/node_modules/pi-token-speed/index.ts'
            self.assertTrue(speed.exists())
            plan.client_argv.extend(['--extension',str(speed)])
            plan.client_env.update({'PI_CODING_AGENT_DIR':str(config), 'PI_CODING_AGENT_SESSION_DIR':str(root/'sessions'),
                                   'PI_OFFLINE':'1', 'PI_TELEMETRY':'0'})
            manager.plan = plan
            manager.state = {'phase':'running','run':plan.public(),'events':[]}
            manager.attachments[plan.run_id] = launcher.SurfaceAttachment(owner_run_id=plan.run_id,plan=plan,primary=True)
            with mock.patch.dict(os.environ, {'PATH':os.environ['PATH']}, clear=True):
                console = manager._launch_agent_console(plan, manager.cancel_event)
            cleanup.callback(manager._stop_agent_console_process, console)
            def wait(predicate):
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    if predicate(): return
                    time.sleep(.025)
                self.fail(bytes(console.output).decode(errors='replace')[-6000:] + repr(console.rpc_statuses))
            def send(message):
                manager._write_pi_rpc_console(console, {'command':'prompt','message':message})
            wait(lambda: bool(console.rpc_commands))
            names = {c['name'] for c in console.rpc_commands}
            self.assertTrue({'tps','compact','new','session','name','help'} <= names, names)
            send('/name Browser commands')
            wait(lambda: not console.rpc_command_ids)
            send('/session')
            wait(lambda: not console.rpc_command_ids)
            self.assertIn('Browser commands', bytes(console.output).decode(errors='replace'))
            self.assertFalse(console.rpc_streaming)
            with self.assertRaisesRegex(ValueError, 'not available'):
                send('/not-a-command')
            # Extension commands must bypass the follow-up queue, even while busy.
            console.rpc_streaming = True
            send('/tps')
            wait(lambda: bool(console.rpc_interactions))
            self.assertFalse(console.rpc_follow_up_queue)
            self.assertIn('Display mode', console.rpc_statuses['launcher.customUI']['text'])
            first = console.rpc_interactions[0]['id']
            manager._write_pi_rpc_console(console, {'command':'extension_response','requestId':first,'value':'\x1b[B'})
            wait(lambda: console.rpc_interactions and console.rpc_interactions[0]['id'] != first)
            self.assertIn("Use the provider's token count", console.rpc_statuses['launcher.customUI']['text'])
            launcher.pi_rpc_event_output(console, {'type':'response','command':'get_state','success':True,'data':{'isStreaming':False}})
            self.assertTrue(console.rpc_interactions, 'State polling must not dismiss an extension menu')
            manager._write_pi_rpc_console(console, {'command':'extension_response','requestId':console.rpc_interactions[0]['id'],'cancelled':True})
            wait(lambda: not console.rpc_command_ids)
            self.assertNotIn('launcher.customUI', console.rpc_statuses)
            self.assertFalse(console.rpc_interactions)
            self.assertFalse(any('__launcher_custom_ui__' in e['text'] for e in console.rpc_timeline_events))
            # No model server exists: these actions must complete without inference.
            console.rpc_streaming = False
            send('/reload')
            wait(lambda: not console.rpc_command_ids)
            send('/tps')
            wait(lambda: bool(console.rpc_interactions))
            manager._write_pi_rpc_console(console, {'command':'extension_response','requestId':console.rpc_interactions[0]['id'],'value':'\x1b'})
            wait(lambda: not console.rpc_command_ids)
            previous_revision = console.rpc_timeline_revision
            send('/new')
            wait(lambda: not console.rpc_command_ids and console.rpc_history_loaded)
            self.assertFalse(console.rpc_streaming)
            self.assertTrue(console.timeline_slice(previous_revision)['timelineReset'], bytes(console.output).decode(errors='replace')[-5000:])


if __name__ == '__main__': unittest.main()
