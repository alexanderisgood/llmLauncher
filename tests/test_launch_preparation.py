"""Launch preparation must never cancel another user's newer benchmark."""
import threading
import unittest
from unittest.mock import Mock
import launcher


class LaunchPreparationCancellationTests(unittest.TestCase):
    def manager(self):
        manager = launcher.BenchmarkManager.__new__(launcher.BenchmarkManager)
        manager.lock = threading.RLock()
        manager.state = {"phase": "running", "job": {"id": "current"}}
        manager.cancel_event = threading.Event()
        manager.active_plan = None
        manager.run_manager = Mock()
        return manager

    def test_stale_launch_cannot_cancel_replacement_test(self):
        manager = self.manager()
        with self.assertRaisesRegex(ValueError, "no other job was stopped"):
            manager.cancel(expected_job_id="old")
        self.assertEqual(manager.state["phase"], "running")
        self.assertFalse(manager.cancel_event.is_set())
        manager.run_manager.stop.assert_not_called()

    def test_matching_launch_can_stop_its_test(self):
        manager = self.manager()
        manager.cancel(expected_job_id="current")
        self.assertEqual(manager.state["phase"], "stopping")
        self.assertTrue(manager.cancel_event.is_set())

    def test_existing_manual_stop_remains_available(self):
        manager = self.manager()
        manager.cancel()
        self.assertTrue(manager.cancel_event.is_set())

    def test_completed_job_does_not_reenter_stopping(self):
        manager = self.manager()
        manager.state["phase"] = "completed"
        manager.cancel(expected_job_id="current")
        self.assertEqual(manager.state["phase"], "completed")
        self.assertFalse(manager.cancel_event.is_set())


if __name__ == "__main__":
    unittest.main()
