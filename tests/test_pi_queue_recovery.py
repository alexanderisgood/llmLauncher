import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import Mock, patch

import launcher


class QueueRecovery(unittest.TestCase):
    def console(self, folder, project="/project"):
        plan = Mock(project=project, run_id="surface", client="pi", backend="mtplx", model={"name": "fixture"})
        process = Mock(pid=1)
        process.poll.return_value = None
        return launcher.AgentConsole(owner_run_id="owner", plan=plan, process=process,
            master_fd=-1, cols=100, rows=30, protocol="pi-rpc", rpc_queue_directory=Path(folder))

    def state(self, console, session="/sessions/one.jsonl"):
        launcher.pi_rpc_event_output(console, {"type": "response", "command": "get_state",
            "success": True, "data": {"sessionFile": session, "isStreaming": False}})

    def test_queued_text_survives_controller_recreation_and_does_not_auto_run(self):
        with tempfile.TemporaryDirectory() as folder:
            original = self.console(folder)
            self.state(original)
            original.rpc_streaming = True
            manager = launcher.RunManager()
            messages = ["Use blue instead <script>alert(1)</script>", "Verify the keyboard controls\nThen stop."]
            for message in messages:
                result = manager._write_pi_rpc_console(original, {"command": "prompt", "message": message})
            self.assertEqual([x["message"] for x in result["queuedMessages"]], messages)
            path = launcher.pi_rpc_queue_path(original)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            restored = self.console(folder)
            self.state(restored)
            self.assertEqual(restored.rpc_follow_up_queue, messages)
            self.assertTrue(restored.rpc_queue_paused)
            self.assertFalse(restored.rpc_queue_advance_allowed)
            self.assertEqual([x["message"] for x in restored.output_slice(0)["queuedMessages"]], messages)
            with patch.object(launcher, "atomic_json") as write:
                self.state(restored)
                write.assert_not_called()

    def test_public_conversation_identity_survives_run_and_engine_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            first = self.console(folder)
            self.assertEqual(first.public()["conversationId"], "")
            self.state(first)
            identity = first.public()["conversationId"]
            self.assertRegex(identity, r"^[a-f0-9]{64}$")
            self.assertEqual(first.output_slice(0)["conversationId"], identity)
            self.assertEqual(first.public()["conversationRevision"], 1)
            self.state(first)
            self.assertEqual(first.public()["conversationRevision"], 1)
            restored = self.console(folder)
            restored.owner_run_id = "new-owner"
            restored.plan.run_id = "new-surface"
            restored.plan.backend = "omlx"
            self.state(restored)
            self.assertEqual(restored.public()["conversationId"], identity)
            self.state(restored, "/sessions/two.jsonl")
            self.assertNotEqual(restored.public()["conversationId"], identity)
            self.assertEqual(restored.output_slice(0)["conversationRevision"], 2)
            other_project = self.console(folder, project="/other")
            self.state(other_project)
            self.assertNotEqual(other_project.public()["conversationId"], identity)
            first.protocol = "terminal"
            self.assertEqual(first.public()["conversationId"], "")

    def test_acceptance_and_clear_are_saved_and_other_sessions_are_isolated(self):
        with tempfile.TemporaryDirectory() as folder:
            original = self.console(folder)
            self.state(original)
            original.rpc_follow_up_queue = ["first", "second"]
            launcher.pi_rpc_save_queue(original)
            original.rpc_queued_prompt_message = "first"
            launcher.pi_rpc_accept_queued_prompt(original)
            restored = self.console(folder)
            self.state(restored)
            self.assertEqual(restored.rpc_follow_up_queue, ["second"])
            self.state(restored, "/sessions/two.jsonl")
            self.assertEqual(restored.rpc_follow_up_queue, [])
            self.state(restored)
            self.assertEqual(restored.rpc_follow_up_queue, ["second"])
            launcher.RunManager()._write_pi_rpc_console(restored, {"command": "clear_queue"})
            fresh = self.console(folder)
            self.state(fresh)
            self.assertEqual(fresh.rpc_follow_up_queue, [])

    def test_disk_failure_is_visible_without_losing_memory_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            console = self.console(folder)
            self.state(console)
            console.rpc_follow_up_queue = ["keep this"]
            with patch.object(launcher, "atomic_json", side_effect=OSError("disk full")):
                launcher.pi_rpc_record_queue(console, "1 waiting")
            self.assertEqual(console.rpc_follow_up_queue, ["keep this"])
            self.assertIn("could not be saved", console.public()["queueSaveError"])

    def test_edit_and_delete_one_duplicate_persist_without_sending(self):
        with tempfile.TemporaryDirectory() as folder:
            console = self.console(folder)
            self.state(console)
            console.rpc_follow_up_queue = ["same", "same", "last"]
            console.rpc_queue_paused = True
            launcher.pi_rpc_save_queue(console)
            manager = launcher.RunManager()
            with patch.object(manager, "_write_pi_rpc_command") as send:
                item = console.public()["queuedMessages"][1]
                manager._write_pi_rpc_console(console, {"command": "edit_queued_message", "queueId": item["id"], "message": "edited\nwith details"})
                item = console.public()["queuedMessages"][0]
                manager._write_pi_rpc_console(console, {"command": "delete_queued_message", "queueId": item["id"]})
                send.assert_not_called()
            restored = self.console(folder)
            self.state(restored)
            self.assertEqual(restored.rpc_follow_up_queue, ["edited\nwith details", "last"])
            self.assertTrue(restored.rpc_queue_paused)

    def test_stale_selection_sending_head_and_failed_save_preserve_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            console = self.console(folder)
            self.state(console)
            console.rpc_follow_up_queue = ["same", "same"]
            launcher.pi_rpc_save_queue(console)
            manager = launcher.RunManager()
            item = console.public()["queuedMessages"][0]
            command = {"command": "delete_queued_message", "queueId": item["id"]}
            console.rpc_queued_prompt_message = "same"
            self.assertFalse(console.public()["queuedMessages"][0]["editable"])
            with self.assertRaisesRegex(ValueError, "already being sent"):
                manager._write_pi_rpc_console(console, command)
            launcher.pi_rpc_accept_queued_prompt(console)
            with self.assertRaisesRegex(ValueError, "changed"):
                manager._write_pi_rpc_console(console, command)
            current = console.public()["queuedMessages"][0]
            with patch.object(launcher, "atomic_json", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(ValueError, "Could not save"):
                    manager._write_pi_rpc_console(console, {**command, "queueId": current["id"]})
            self.assertEqual(console.rpc_follow_up_queue, ["same"])
            for message in ["", " ", '"' * 40000]:
                with self.assertRaises(ValueError):
                    manager._write_pi_rpc_console(console, {"command": "edit_queued_message", "queueId": current["id"], "message": message})
            self.assertEqual(console.rpc_follow_up_queue, ["same"])


if __name__ == "__main__":
    unittest.main()
