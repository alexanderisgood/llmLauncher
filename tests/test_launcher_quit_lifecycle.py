"""Quit closes a synthetic controller even with a stranded browser request."""
import json
from pathlib import Path
import re
import select
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request


class ControllerQuitLifecycleTests(unittest.TestCase):
    def test_cleanup_and_exit_do_not_wait_for_an_incomplete_http_body(self):
        app = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="launcher-quit-lifecycle-") as directory:
            root = Path(directory)
            # Process termination is completely stubbed. Only this synthetic
            # controller and its temporary state are created by the test.
            source = """
import pathlib,sys
import launcher,launcher_shutdown
root=pathlib.Path(sys.argv[1])
launcher.STATE_DIR=root/'state'
launcher.RUNS_DIR=launcher.STATE_DIR/'runs'
launcher.LOGS_DIR=launcher.STATE_DIR/'logs'
launcher.BINARIES={}
launcher.runtime_candidates=lambda _key: []
launcher.secrets.token_urlsafe=lambda _size: 'synthetic-quit-token'
launcher.open_controller_server=lambda _port: launcher.ControllerHTTPServer(('127.0.0.1',0),launcher.Handler)
launcher_shutdown.stop_lmstudio=lambda _binary: []
launcher_shutdown.stop_engine_services=lambda **_kwargs: {'servicesStopped':0,'processesStopped':0,'errors':[],'_processReceipts':{}}
launcher_shutdown.retitled_servers_for_quit=lambda _binaries: {'_processReceipts':{},'_nativeReceipts':{},'errors':[]}
launcher_shutdown.stop_local_servers=lambda *_args,**_kwargs: {'processesStopped':0,'errors':[]}
launcher.serve(True,0)
(root/'controller-exited').touch()
"""
            process = subprocess.Popen([sys.executable, "-u", "-c", source, str(root)],
                cwd=app,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            pending = None
            try:
                self.assertTrue(select.select([process.stdout], [], [], 10)[0], "controller never announced readiness")
                line = process.stdout.readline()
                match = re.search(r"http://127\.0\.0\.1:(\d+)/", line)
                self.assertIsNotNone(match, line)
                port = int(match.group(1))
                pending = socket.create_connection(("127.0.0.1",port),timeout=3)
                pending.sendall((f"POST /api/launch HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
                    "X-Launcher-Token: synthetic-quit-token\r\nContent-Length: 100\r\n\r\n{").encode())
                # Let the first handler enter its body read, keeping the socket
                # open throughout shutdown to expose a non-daemon join.
                time.sleep(.1)
                request = urllib.request.Request(f"http://127.0.0.1:{port}/api/quit",data=b"{}",
                    headers={"X-Launcher-Token":"synthetic-quit-token",
                             "Origin":f"http://127.0.0.1:{port}"})
                with urllib.request.urlopen(request,timeout=5) as response:
                    self.assertEqual(response.status,202)
                    self.assertTrue(json.load(response)["quitting"])
                self.assertEqual(process.wait(timeout=6),0)
                self.assertTrue((root/"controller-exited").is_file())
                self.assertTrue((root/"state/runs/.quit-marker").is_file())
                records = [json.loads(line) for line in
                    (root/"state/logs/controller-lifecycle.jsonl").read_text().splitlines()]
                self.assertIn({"event": "shutdown_requested", "reason": "user_quit"},
                    [{key: item[key] for key in ("event", "reason")}
                     for item in records if item["event"] == "shutdown_requested"])
                self.assertEqual(records[-1]["event"], "controller_exited")
            finally:
                if pending:
                    pending.close()
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait(timeout=3)
                process.stdout.close()
                process.stderr.close()

    def test_external_signals_record_the_reason_and_finish_owned_cleanup(self):
        app = Path(__file__).resolve().parents[1]
        for stop_signal in (signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal=stop_signal), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = """
import pathlib,sys
import launcher
root=pathlib.Path(sys.argv[1])
launcher.STATE_DIR=root/'state'
launcher.RUNS_DIR=launcher.STATE_DIR/'runs'
launcher.LOGS_DIR=launcher.STATE_DIR/'logs'
launcher.BINARIES={}
launcher.runtime_candidates=lambda _key: []
launcher.MANAGER.stop=lambda: (root/'owned-cleanup').touch()
launcher.open_controller_server=lambda _port: launcher.ControllerHTTPServer(('127.0.0.1',0),launcher.Handler)
launcher.serve(True,0)
"""
                process = subprocess.Popen([sys.executable, "-u", "-c", source, str(root)],
                    cwd=app, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    self.assertTrue(select.select([process.stdout], [], [], 10)[0])
                    line = process.stdout.readline()
                    match = re.search(r"http://127\.0\.0\.1:(\d+)/", line)
                    self.assertIsNotNone(match, line)
                    # An HTTP response proves serve_forever and signal handlers
                    # are ready, without any model or service discovery.
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{match.group(1)}/api/quit/status", timeout=5,
                    ) as response:
                        self.assertEqual(response.status, 200)
                    process.send_signal(stop_signal)
                    self.assertEqual(process.wait(timeout=6), 0)
                    self.assertTrue((root/"owned-cleanup").is_file())
                    self.assertFalse((root/"state/runs/.quit-marker").exists())
                    path = root/"state/logs/controller-lifecycle.jsonl"
                    records = [json.loads(line) for line in path.read_text().splitlines()]
                    requests = [item for item in records if item["event"] == "shutdown_requested"]
                    self.assertEqual([item["reason"] for item in requests], [stop_signal.name])
                    self.assertEqual(records[-2]["event"], "cleanup_complete")
                    self.assertEqual(records[-1]["event"], "controller_exited")
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
                    process.stdout.close()
                    process.stderr.close()


if __name__ == "__main__":
    unittest.main()
