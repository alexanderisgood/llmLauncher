"""Small generated CLIs prove byte limits and retained child/group ownership."""
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock

import owned_cli_capture as capture


class OwnedCaptureTests(unittest.TestCase):
    def run_cli(self, code, **kwargs):
        return capture.capture_owned_cli([sys.executable,'-I','-B','-c',code],timeout=kwargs.pop('timeout',3),max_bytes=kwargs.pop('max_bytes',1024),terminate_grace=.02,**kwargs)

    def test_complete_output_exit_status_environment_and_utf8_bytes(self):
        result=self.run_cli("import os,sys;sys.stdout.buffer.write(('你好🙂'+os.environ['GENERATED_CAPTURE']).encode());sys.stderr.write('tail');sys.exit(7)",environment={'GENERATED_CAPTURE':' exact'})
        self.assertEqual(result.returncode,7);self.assertEqual(result.stdout.decode(),'你好🙂 exacttail')

    def test_byte_quota_is_exact_and_never_collects_unbounded_output(self):
        self.assertEqual(len(self.run_cli("import sys;sys.stdout.buffer.write(b'x'*2048)",max_bytes=2048).stdout),2048)
        with self.assertRaises(capture.CaptureLimitError):self.run_cli("import sys;sys.stdout.buffer.write(b'x'*2049)",max_bytes=2048)
        with self.assertRaises(capture.CaptureLimitError):self.run_cli("import os;\nwhile True:os.write(1,b'x'*65536)",max_bytes=8192)

    def test_silent_timeout_and_cancel_retire_only_the_generated_session(self):
        started=time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):self.run_cli('import time;time.sleep(30)',timeout=.05)
        self.assertLess(time.monotonic()-started,2)
        event=threading.Event();timer=threading.Timer(.05,event.set);timer.start()
        try:
            with self.assertRaises(capture.CaptureCancelled):self.run_cli('import time;time.sleep(30)',cancel_event=event)
        finally:timer.cancel();timer.join()
        with mock.patch.object(capture.subprocess,'Popen') as spawn:
            with self.assertRaises(capture.CaptureCancelled):self.run_cli('pass',cancel_event=event)
            spawn.assert_not_called()

    def test_exited_leader_with_descendant_pipe_retires_group_before_reaping(self):
        code="import os,time;child=os.fork();\nif child==0:\n print('child',flush=True);time.sleep(30);os._exit(0)\nprint(child,flush=True);os._exit(0)"
        started=time.monotonic();result=self.run_cli(code)
        self.assertEqual(result.returncode,0);self.assertIn(b'child',result.stdout)
        self.assertLess(time.monotonic()-started,2)

    def test_normal_and_nonzero_statuses_never_poll_or_reap_before_signals(self):
        original_wait=capture.subprocess.Popen.wait;calls=[]
        def waited(process,*a,**kw):calls.append('wait');return original_wait(process,*a,**kw)
        real_signal=os.killpg
        def signalled(pid,sig):calls.append(sig);return real_signal(pid,sig)
        with mock.patch.object(capture.subprocess.Popen,'poll',side_effect=AssertionError('poll reaps owned receipt')),mock.patch.object(capture.subprocess.Popen,'wait',waited),mock.patch.object(capture.os,'killpg',side_effect=signalled):
            self.assertEqual(self.run_cli('print("owned")').stdout,b'owned\n')
        self.assertEqual(calls[:3],[signal.SIGTERM,signal.SIGKILL,'wait'])

    def test_lost_or_reused_waitid_receipt_never_signals_or_waits_on_pid(self):
        for result in (ChildProcessError('reaped'),SimpleNamespace(si_pid=999999)):
            with self.subTest(result=result),tempfile.TemporaryFile() as stream:
                fake=SimpleNamespace(pid=888888,stdout=stream,returncode=None,wait=mock.Mock(side_effect=AssertionError('unowned wait')))
                with mock.patch.object(capture.subprocess,'Popen',return_value=fake),mock.patch.object(capture.os,'waitid',side_effect=result if isinstance(result,Exception) else None,return_value=None if isinstance(result,Exception) else result),mock.patch.object(capture.os,'killpg') as signals:
                    with self.assertRaises(capture.CaptureOwnershipError):self.run_cli('pass')
                signals.assert_not_called();fake.wait.assert_not_called();self.assertEqual(fake.returncode,-1)

    def test_import_performs_no_file_process_or_network_operations(self):
        spec=importlib.util.spec_from_file_location('private_owned_capture_import',capture.__file__);module=importlib.util.module_from_spec(spec)
        with mock.patch.object(capture.subprocess,'Popen',side_effect=AssertionError('import process')),mock.patch('builtins.open',side_effect=AssertionError('import I/O')):
            spec.loader.exec_module(module)

    def test_eight_mib_ascii_character_boundary_stays_exact(self):
        quota=8*1024**2
        self.assertEqual(len(self.run_cli(f"import sys;sys.stdout.buffer.write(b'x'*{quota})",max_bytes=quota).stdout),quota)
        with self.assertRaises(capture.CaptureLimitError):self.run_cli(f"import sys;sys.stdout.buffer.write(b'x'*{quota+1})",max_bytes=quota)

    def test_output_read_failure_still_kills_owned_group_before_wait(self):
        real_signal=capture.os.killpg;real_read=capture.os.read;real_spawn=capture.subprocess.Popen
        signals=[];failed_fd=None
        def send(pid,sig):signals.append(sig);return real_signal(pid,sig)
        def spawn(*args,**kwargs):
            nonlocal failed_fd
            process=real_spawn(*args,**kwargs);failed_fd=process.stdout.fileno();return process
        def read(fd,size):
            if fd==failed_fd:raise OSError('Generated read failure')
            return real_read(fd,size)
        with mock.patch.object(capture.subprocess,'Popen',side_effect=spawn),mock.patch.object(capture.os,'read',side_effect=read),mock.patch.object(capture.os,'killpg',side_effect=send):
            with self.assertRaises(OSError):self.run_cli("import time;print('generated',flush=True);time.sleep(30)")
        self.assertIn(signal.SIGKILL,signals)

    def test_unknown_permission_failure_is_not_treated_as_terminal_group(self):
        with tempfile.TemporaryFile() as stream:
            fake=SimpleNamespace(pid=888888,stdout=stream,returncode=None,wait=mock.Mock(return_value=0))
            exited=SimpleNamespace(si_pid=888888)
            with mock.patch.object(capture.subprocess,'Popen',return_value=fake),mock.patch.object(capture.os,'waitid',return_value=exited),mock.patch.object(capture.os,'killpg',side_effect=PermissionError('Generated permission failure')),mock.patch.object(capture,'_darwin_group_is_terminal',return_value=False):
                with self.assertRaises(PermissionError):self.run_cli('pass')

    def test_receipt_loss_after_term_or_kill_never_targets_reused_child(self):
        for loss_at in (3,4):
            with self.subTest(loss_at=loss_at),tempfile.TemporaryFile() as stream:
                fake=SimpleNamespace(pid=888888,stdout=stream,returncode=None,wait=mock.Mock(side_effect=AssertionError('unowned wait')))
                exited=SimpleNamespace(si_pid=888888);calls=[]
                def observe(*_args):
                    calls.append(1)
                    if len(calls)==loss_at:raise ChildProcessError('Generated reuse after reaping')
                    return exited
                with mock.patch.object(capture.subprocess,'Popen',return_value=fake),mock.patch.object(capture.os,'waitid',side_effect=observe),mock.patch.object(capture.os,'killpg') as signals:
                    with self.assertRaises(capture.CaptureOwnershipError):self.run_cli('pass')
                self.assertEqual([call.args[1] for call in signals.call_args_list],
                    [signal.SIGTERM] if loss_at==3 else [signal.SIGTERM,signal.SIGKILL])
                fake.wait.assert_not_called();self.assertEqual(fake.returncode,-1)

    def test_empty_secondary_argument_is_preserved_without_shell_interpretation(self):
        result=capture.capture_owned_cli([sys.executable,'-I','-B','-c',"import json,sys;print(json.dumps(sys.argv[1:]))",'--query',''],timeout=3,max_bytes=1024,terminate_grace=.02)
        self.assertEqual(result.stdout,b'["--query", ""]\n')
        with mock.patch.object(capture.subprocess,'Popen') as spawn:
            for argv in ([],[''],[sys.executable,'bad\0argument'],[sys.executable,1]):
                with self.subTest(argv=argv),self.assertRaises(ValueError):capture.capture_owned_cli(argv,timeout=1,max_bytes=10)
            spawn.assert_not_called()

    def test_bounded_observer_receives_the_same_bytes_and_failure_retires_owned_child(self):
        chunks=[]
        result=self.run_cli("import sys;sys.stdout.buffer.write(('你🙂\\n'*5000).encode())",max_bytes=65536,on_bytes=chunks.append)
        self.assertEqual(b''.join(chunks),result.stdout);self.assertTrue(all(len(chunk)<=32768 for chunk in chunks))
        real_signal=capture.os.killpg;signals=[]
        def signal_group(pid,sig):signals.append(sig);return real_signal(pid,sig)
        def failed(_data):raise ValueError('Generated decoder rejection')
        with mock.patch.object(capture.os,'killpg',side_effect=signal_group):
            with self.assertRaisesRegex(ValueError,'decoder rejection'):self.run_cli("import time;print('generated',flush=True);time.sleep(30)",on_bytes=failed)
        self.assertEqual(signals,[signal.SIGTERM,signal.SIGKILL])
