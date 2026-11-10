#!/usr/bin/env python3
"""Opt-in actual launchd Quit verification using only an owned harmless fixture.

Registers one uniquely named temporary current-user LaunchAgent. Its stdlib
Python loopback server has KeepAlive and a generic worker child. The test uses
the real service proof/unload and birth-bound process sweep, with all targets
restricted to this fixture. No AI model/GPU, user project, real /api/quit,
global settings or permanent LaunchAgents files. Always cleans up in finally.

Run explicitly: python3 bench/quit_owned_service.py --result /private/tmp/quit-proof.json
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
from pathlib import Path
import plistlib
import signal
import subprocess
import sys
import tempfile
import time
from unittest import mock
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import launcher_shutdown
import service_shutdown


class LaunchdUnavailable(RuntimeError):
    pass


STUB = r'''import json
import os
from pathlib import Path
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

mode, state_path = sys.argv[1:]
if mode == "worker":
    while True:
        time.sleep(.2)
else:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass
        def do_GET(self):
            body = b'{"synthetic_fixture":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = subprocess.Popen([sys.executable, "-I", "-B", "-u", __file__, "worker", state_path],
                              stdin=subprocess.DEVNULL, start_new_session=True)
    fd = os.open(state_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump({"parentPid":os.getpid(), "workerPid":worker.pid,
                   "uid":os.getuid(), "port":server.server_port}, handle)
    server.serve_forever(poll_interval=.05)
'''


def jobs():
    result = subprocess.run(["/bin/launchctl", "list"], capture_output=True, text=True, timeout=5)
    if result.returncode != 0:
        raise RuntimeError("Current-user launchd inventory is unavailable")
    return service_shutdown._jobs(lambda _argv, **_kwargs: result)


def same_birth(original, current):
    return bool(current and original.uid == current.uid == os.getuid()
                and original.pid == current.pid and original.started == current.started)


def current_omlx_receipt():
    registered = jobs()
    pid = registered.get("homebrew.mxcl.omlx")
    process = launcher_shutdown.process_snapshot().get(pid) if pid else None
    return process


def run(result_path: Path, *, idle_omlx_port: int | None = None) -> dict:
    uid = os.getuid()
    label = f"com.llm-launcher.quit-fixture.{os.getpid()}.{uuid.uuid4().hex[:12]}"
    target = f"gui/{uid}/{label}"
    report = {"kind": "owned-synthetic-launchd-Quit-verification", "uid": uid, "fixtureLabel": label,
              "usesAIModel": False, "usesGPU": False, "realQuitEndpointInvoked": False,
              "registeredFixtureOnly": True, "errors": [], "signalTargets": []}
    real_kill = os.kill
    fixture_receipts = {}
    before_omlx = None
    failure = None
    with tempfile.TemporaryDirectory(prefix="launcher-quit-service-", dir="/private/tmp") as temporary:
        folder = Path(temporary).resolve()
        script = folder / "fixture_server.py"
        script.write_text(STUB); script.chmod(0o600)
        state_path = folder / "fixture-state.json"
        plist_path = folder / (label + ".plist")
        python = str(Path(sys.executable).resolve())
        config = {"Label": label, "ProgramArguments": [python, "-I", "-B", "-u", str(script), "serve", str(state_path)],
                  "RunAtLoad": True, "KeepAlive": True, "ThrottleInterval": 1,
                  "WorkingDirectory": str(folder), "StandardOutPath": str(folder / "stdout.log"),
                  "StandardErrorPath": str(folder / "stderr.log")}
        plist_path.write_bytes(plistlib.dumps(config)); plist_path.chmod(0o600)
        framework_python = Path(python).parent.parent / "Resources/Python.app/Contents/MacOS/Python"

        def fixture_runner(argv, **kwargs):
            allowed = (["/bin/launchctl", "list"], ["/bin/launchctl", "print", f"gui/{uid}"],
                       ["/bin/launchctl", "print", target], ["/bin/launchctl", "bootout", target],
                       ["/bin/launchctl", "bootstrap", f"gui/{uid}", str(plist_path)])
            if argv not in allowed:
                raise RuntimeError("A launchd operation outside the owned fixture was rejected")
            return subprocess.run(argv, **kwargs)

        def remember_fixture():
            current = launcher_shutdown.process_snapshot()
            for pid, process in current.items():
                tail = launcher_shutdown._command_tail(process.command, str(script))
                # Framework Python may re-exec its exact installed app entry
                # point. Normalize only that same interpreter for this
                # private fixture path; no broad Python/title matching.
                executable, separator, rest = process.command.partition(" ")
                if tail is None and separator and executable == str(framework_python):
                    tail = launcher_shutdown._command_tail("python3 " + rest, str(script))
                if tail and tail.split(None, 1)[0] in {"serve", "worker"}:
                    fixture_receipts[pid] = process
            return current

        def fixture_signal(pid, sig):
            original = fixture_receipts.get(pid)
            current = launcher_shutdown.process_snapshot().get(pid)
            if not original or not same_birth(original, current):
                raise RuntimeError("A signal outside the fixture's proven PID birth was rejected")
            report["signalTargets"].append({"pid": pid, "signal": int(sig), "uid": uid, "started": original.started})
            real_kill(pid, sig)

        try:
            if sys.platform != "darwin":
                raise LaunchdUnavailable("Current-user GUI launchd verification requires macOS")
            gui = fixture_runner(["/bin/launchctl", "print", f"gui/{uid}"], capture_output=True, text=True, timeout=5)
            if gui.returncode != 0:
                raise LaunchdUnavailable(f"Current-user GUI launchd domain is unavailable (exit {gui.returncode})")
            before_omlx = current_omlx_receipt()
            started = fixture_runner(["/bin/launchctl", "bootstrap", f"gui/{uid}", str(plist_path)],
                                     capture_output=True, text=True, timeout=5)
            if started.returncode != 0:
                raise LaunchdUnavailable(f"Owned fixture bootstrap was unavailable (exit {started.returncode})")
            report["fixtureBootstrapConfirmed"] = True
            deadline = time.monotonic() + 15
            state = None
            while time.monotonic() < deadline:
                current = remember_fixture()
                if state_path.is_file():
                    with contextlib.suppress(ValueError, OSError):
                        state = json.loads(state_path.read_text())
                        parent, worker = current.get(state.get("parentPid")), current.get(state.get("workerPid"))
                        if parent and worker and parent.uid == worker.uid == uid and worker.parent == parent.pid:
                            break
                time.sleep(.1)
            else:
                raise RuntimeError("The owned fixture server/worker did not become ready")
            with urllib.request.urlopen(f"http://127.0.0.1:{state['port']}/health", timeout=3) as response:
                if json.load(response) != {"synthetic_fixture": True}:
                    raise AssertionError("The owned synthetic server did not return its fixture marker")
            report.update({"fixtureParentPid": parent.pid, "fixtureWorkerPid": worker.pid,
                           "fixtureLoopbackReady": True, "keepAliveConfigured": True})
            fixture_receipts.update({parent.pid: parent, worker.pid: worker})
            binaries = {"omlx": str(script)}
            service = service_shutdown.stop_engine_services(
                process_label=lambda process: launcher_shutdown.process_label(process, binaries, folder),
                process_snapshot=launcher_shutdown.process_snapshot, launch_agents=folder,
                timeout=3, runner=fixture_runner)
            report["serviceResult"] = {key: value for key, value in service.items() if not key.startswith("_")}
            receipts = service["_processReceipts"]
            if parent.pid not in receipts or worker.pid not in receipts:
                raise AssertionError("The actual launchd service proof did not capture parent and worker births")
            if service["errors"] or service["servicesStopped"] != 1:
                raise AssertionError("The owned fixture LaunchAgent was not cleanly unloaded")
            fixture_receipts.update(receipts)
            with mock.patch.object(launcher_shutdown.os, "kill", side_effect=fixture_signal):
                sweep = launcher_shutdown.stop_local_servers(binaries, folder, grace=3, verified_processes=receipts)
            report["sweepResult"] = sweep
            if sweep["errors"]:
                raise AssertionError("The fixture worker process sweep did not finish cleanly")
            current = remember_fixture()
            if any(same_birth(original, current.get(pid)) for pid, original in receipts.items()):
                raise AssertionError("A fixture parent or captured worker remains running")
            if label in jobs():
                raise AssertionError("The owned fixture job remains registered")
            report.update({"jobUnregistered": True, "parentStopped": True, "capturedWorkersStopped": True})
            # Three periods exceed the fixture's one-second launchd throttle.
            # With the job unregistered there is no KeepAlive source to reload.
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if label in jobs() or any(launcher_shutdown._command_tail(process.command, str(script)) is not None
                                         for process in launcher_shutdown.process_snapshot().values()):
                    raise AssertionError("The owned fixture restarted after Quit")
                time.sleep(.25)
            report["noKeepAliveRestart"] = True
        except LaunchdUnavailable as error:
            report["unavailable"] = str(error)
        except Exception as error:
            report["errors"].append(f"{type(error).__name__}: {error}")
            failure = error
        finally:
            # The exact fixture target is always removed, even after uncertain
            # bootstrap outcomes. No other job label or process may be touched.
            try:
                remember_fixture()
            except Exception as error:
                report["errors"].append(f"Fixture inventory cleanup failed: {type(error).__name__}")
            if sys.platform == "darwin":
                try:
                    fixture_runner(["/bin/launchctl", "bootout", target], capture_output=True, text=True, timeout=5)
                    report["fixtureFinallyUnregistered"] = label not in jobs()
                except Exception as error:
                    report["errors"].append(f"Fixture registration cleanup failed: {type(error).__name__}")
            try:
                current = remember_fixture()
                for pid, original in tuple(fixture_receipts.items()):
                    if same_birth(original, current.get(pid)):
                        fixture_signal(pid, signal.SIGTERM)
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    current = launcher_shutdown.process_snapshot()
                    if not any(same_birth(original, current.get(pid)) for pid, original in fixture_receipts.items()):
                        break
                    time.sleep(.1)
                current = launcher_shutdown.process_snapshot()
                for pid, original in tuple(fixture_receipts.items()):
                    if same_birth(original, current.get(pid)):
                        fixture_signal(pid, signal.SIGKILL)
                report["fixtureProcessesFinallyGone"] = not any(
                    same_birth(original, launcher_shutdown.process_snapshot().get(pid)) for pid, original in fixture_receipts.items())
            except Exception as error:
                report["errors"].append(f"Fixture process cleanup failed: {type(error).__name__}")
            if before_omlx is not None:
                current = launcher_shutdown.process_snapshot().get(before_omlx.pid)
                report["foreignOmlxIdentityUntouched"] = same_birth(before_omlx, current) and jobs().get("homebrew.mxcl.omlx") == before_omlx.pid
                if not report["foreignOmlxIdentityUntouched"]:
                    report["errors"].append("The independently running oMLX identity changed during the fixture test")
                if idle_omlx_port is not None:
                    with urllib.request.urlopen(f"http://127.0.0.1:{idle_omlx_port}/api/status", timeout=3) as response:
                        status = json.load(response)
                    report["foreignOmlxStillIdle"] = all(status.get(field) == 0 for field in
                        ("models_loaded", "models_loading", "active_requests", "waiting_requests", "total_requests"))
            result_path.parent.mkdir(parents=True, exist_ok=True)
            result_path.write_text(json.dumps(report, indent=2) + "\n")
    report["temporaryFixtureFilesRemoved"] = not folder.exists()
    result_path.write_text(json.dumps(report, indent=2) + "\n")
    if failure is not None:
        raise failure
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--idle-omlx-port", type=int)
    args = parser.parse_args()
    report = run(args.result, idle_omlx_port=args.idle_omlx_port)
    print(json.dumps({key: report.get(key) for key in ("fixtureLabel", "unavailable", "jobUnregistered",
        "parentStopped", "capturedWorkersStopped", "noKeepAliveRestart", "foreignOmlxIdentityUntouched",
        "fixtureFinallyUnregistered", "fixtureProcessesFinallyGone", "temporaryFixtureFilesRemoved", "errors")}))


if __name__ == "__main__":
    main()
