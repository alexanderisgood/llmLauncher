"""Exercise host shutdown with a tiny subprocess instead of loading a model."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest


class QwenHostLifecycleTests(unittest.TestCase):
    def test_sigterm_and_sigint_wait_for_owned_server_cleanup(self):
        helper = Path(__file__).resolve().parents[1] / "tools/run_qwen35_moe_128k.py"
        for stop_signal in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=stop_signal), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                ready, stopped = root / "ready", root / "stopped"
                model = root / "model.gguf"
                model.touch()
                engine = root / "engine"
                engine.write_text(
                    f"#!{sys.executable}\n"
                    "import os,pathlib,signal,time\n"
                    "def stop(*args):\n"
                    f" pathlib.Path({str(stopped)!r}).touch()\n"
                    " raise SystemExit(0)\n"
                    "signal.signal(signal.SIGTERM,stop)\n"
                    f"pathlib.Path({str(ready)!r}).write_text(str(os.getpid()))\n"
                    "while True: time.sleep(.05)\n"
                )
                engine.chmod(0o700)
                runner = root / "runner.py"
                runner.write_text(
                    "import importlib.util,pathlib,sys\n"
                    f"spec=importlib.util.spec_from_file_location('host',{str(helper)!r})\n"
                    "host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)\n"
                    f"host.SERVER=pathlib.Path({str(engine)!r})\n"
                    f"sys.argv=['host','--model',{str(model)!r}]\n"
                    "raise SystemExit(host.main())\n"
                )
                process = subprocess.Popen([sys.executable, str(runner)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
                try:
                    deadline = time.monotonic() + 5
                    while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                        time.sleep(.02)
                    self.assertTrue(ready.exists(), "fake engine did not start")
                    process.send_signal(stop_signal)
                    self.assertEqual(process.wait(timeout=5), 128 + stop_signal)
                    self.assertTrue(stopped.exists(), "helper exited without stopping its engine")
                finally:
                    # Kill only this test's engine if an assertion interrupted cleanup.
                    if ready.exists() and not stopped.exists():
                        try:
                            os.kill(int(ready.read_text()), signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    if process.poll() is None:
                        process.kill()
                    process.wait()
                    process.stderr.close()


if __name__ == "__main__":
    unittest.main()
