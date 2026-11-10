"""Opt-in harmless owned launchd service test; never targets a real AI server."""
import os
from pathlib import Path
import tempfile
import unittest

from bench.quit_owned_service import run


@unittest.skipUnless(os.environ.get("LLM_LAUNCHER_QUIT_SERVICE_LIVE") == "1", "Opt-in owned LaunchAgent Quit check")
class OwnedServiceQuitLiveTests(unittest.TestCase):
    def test_exact_service_and_worker_are_stopped_without_restart(self):
        with tempfile.TemporaryDirectory(prefix="quit-fixture-report-", dir="/private/tmp") as temporary:
            report = run(Path(temporary) / "quit-report.json")
            if report.get("unavailable"):
                self.skipTest(report["unavailable"])
            self.assertEqual(report["errors"], [])
            for field in ("jobUnregistered", "parentStopped", "capturedWorkersStopped", "noKeepAliveRestart",
                          "fixtureFinallyUnregistered", "fixtureProcessesFinallyGone", "temporaryFixtureFilesRemoved"):
                self.assertTrue(report[field], field)
            self.assertFalse(report["usesAIModel"])
            self.assertFalse(report["usesGPU"])
            self.assertFalse(report["realQuitEndpointInvoked"])
            self.assertTrue(all(item["uid"] == os.getuid() for item in report["signalTargets"]))


if __name__ == "__main__":
    unittest.main()
