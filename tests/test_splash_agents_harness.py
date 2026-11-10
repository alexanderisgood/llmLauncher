"""Safety regression checks for the opt-in real-model agent harness."""
import signal
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from bench import splash_agents_live as harness


class SplashAgentHarnessTests(unittest.TestCase):
    def guard(self, reclaimable, decision="ready", launchable=True):
        admission = {"launchable": launchable, "decision": decision,
                     "requiresAcknowledgement": False,
                     "estimate": {"requiredHeadroomBytes": 25_000_000_000}}
        with mock.patch.object(harness.launcher, "apple_resource_snapshot", return_value={}), \
                mock.patch.object(harness.launcher, "public_session_resource", return_value={}), \
                mock.patch.object(harness.launcher, "session_memory_admission", return_value=admission) as gate, \
                mock.patch.object(harness.darwin_memory, "snapshot_reclaimable_bytes", return_value=reclaimable):
            result = harness.memory_guard({"id": "fixture"}, Path("/private/tmp"), {})
        self.assertEqual([item.args[0]["client"] for item in gate.call_args_list], ["pi", "omp"])
        return result

    def test_pressure_percentage_cannot_override_physical_guard(self):
        result = self.guard(19_000_000_000)
        self.assertFalse(result["ready"])
        self.assertEqual(result["physicalRequiredHeadroomBytes"], 25_000_000_000)

    def test_physical_capacity_cannot_override_launcher_admission(self):
        self.assertFalse(self.guard(40_000_000_000, decision="pressure", launchable=False)["ready"])

    def test_both_guards_are_required(self):
        self.assertTrue(self.guard(25_000_000_000)["ready"])

    def test_missing_physical_observation_fails_closed(self):
        self.assertFalse(self.guard(None)["ready"])

    def test_process_selection_includes_renamed_server_and_excludes_other_python(self):
        inventory = f"""101 101 omlx-server
102 102 /opt/engine/splash --model fixture
103 103 /opt/python {harness.launcher.APP_DIR}/splash_reasoning.py /repo/server/server.py
104 104 /opt/python unrelated_project.py splash
105 105 /bin/zsh -c ps -ww omlx-server
106 106 /opt/mtplx serve /models/fixture
107 107 /opt/python -I -B -u {harness.launcher.APP_DIR}/runtime_patches/kolibri/worker.py /private/tmp/config.json
108 108 /opt/python -u /other/project/worker.py /private/tmp/config.json
109 109 /opt/python -c {harness.launcher.APP_DIR}/runtime_patches/kolibri/worker.py
"""
        with mock.patch.object(harness.subprocess, "run", return_value=SimpleNamespace(stdout=inventory)):
            self.assertEqual(harness.foreign_engines({102, 103}), [(101, "omlx-server"), (106, "mtplx"), (107, "python")])

    def test_cleanup_signals_only_the_group_started_by_this_harness(self):
        child = mock.Mock(pid=7182)
        child.wait.side_effect = [subprocess.TimeoutExpired("fixture", 8), 0]
        with mock.patch.object(harness.os, "killpg") as send:
            harness.stop_owned(child)
        self.assertEqual(send.call_args_list, [mock.call(7182, signal.SIGTERM), mock.call(7182, signal.SIGKILL)])

    def test_installed_python_engine_script_is_detected_after_safe_flags(self):
        inventory = "201 201 /opt/python3 -I -B -u /exact/installed/omlx serve\n"
        with mock.patch.object(harness.subprocess, "run", return_value=SimpleNamespace(stdout=inventory)), \
                mock.patch.dict(harness.launcher.BINARIES, {"omlx": "/exact/installed/omlx"}):
            self.assertEqual(harness.foreign_engines(set()), [(201, "python3")])


if __name__ == "__main__":
    unittest.main()
