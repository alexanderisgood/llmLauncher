"""Standalone Console feature contracts and frozen pre-extraction equivalence."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import agent_console_rpc as rpc
import launcher


class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 6, 12, 0, 0, tzinfo=timezone.utc)


class Process:
    pid = 17

    def poll(self):
        return None


def console(cls=rpc.AgentConsole, **changes):
    plan = SimpleNamespace(run_id="fixture-surface", client="pi", backend="mtplx",
                           project="/fixture/project", model={"name": "Fixture model"})
    values = dict(owner_run_id="fixture-owner", plan=plan, process=Process(), master_fd=-1,
                  cols=100, rows=30, protocol="pi-rpc", started_at="2026-10-06T12:00:00+00:00",
                  surface_label="Pi")
    return cls(**{**values, **changes})


class ConsoleFeatureTests(unittest.TestCase):
    def test_frozen_legacy_transcript_replay_public_schema_and_terminal_output_match(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/agent-console-rpc-v3.json").read_text())
        for cls in (rpc.AgentConsole, launcher.AgentConsole):
            value = console(cls)
            rendered = []
            with patch.object(rpc, "datetime", Clock), patch.object(rpc.time, "monotonic", return_value=100.0):
                for event in fixture["events"]:
                    data = rpc.pi_rpc_event_output(value, event)
                    rendered.append(data.decode("utf-8"))
                    value.append(data)
                actual = {"public": value.public(), "output": value.output_slice(0, 0, timeline_version=1),
                          "rendered": rendered}
            with self.subTest(cls=cls):
                self.assertEqual(actual, fixture["expected"])

    def test_domain_import_does_not_import_launcher_or_allocate_controller_state(self):
        result = subprocess.run([sys.executable, "-c",
                                 "import sys, agent_console_rpc; assert 'launcher' not in sys.modules"],
                                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_frozen_policy_limits_are_per_console_and_retain_whole_unicode_events(self):
        small = console(policy=replace(rpc.DEFAULT_POLICY, max_events=2, max_replay_items=3,
                                       max_event_text_bytes=12, max_text_bytes=120, max_buffer=24))
        other = console()
        with self.assertRaises(FrozenInstanceError):
            small.policy.max_events = 100
        for index in range(8):
            small.append_timeline("answer", "🙂" * 5, item_id=f"a:{index}", operation="replace")
            other.append_timeline("answer", "🙂" * 5, item_id=f"a:{index}", operation="replace")
        self.assertEqual(len(small.rpc_timeline_events), 2)
        self.assertEqual(len(small.rpc_timeline_items), 3)
        self.assertEqual(len(other.rpc_timeline_events), 8)
        for item in small.timeline_slice(0)["timelineEvents"]:
            self.assertLessEqual(len(item["text"].encode()), 12)
            self.assertNotIn("�", item["text"])
        small.append(b"bytes" * 20)
        self.assertEqual(len(small.output), 24)
        self.assertEqual(small.base_offset, 76)
        self.assertEqual(other.output, bytearray())

    def test_tracking_and_transient_delta_bounds_use_console_policy(self):
        value = console(policy=replace(rpc.DEFAULT_POLICY, max_tracked_items=2, max_transient_text_items=2,
                                       max_buffer=24, max_text_bytes=36, max_event_text_bytes=12))
        rpc.pi_rpc_event_output(value, {"type": "agent_start"})
        rpc.pi_rpc_event_output(value, {"type": "message_start", "message": {"role": "assistant", "content": []}})
        for index in range(10):
            rpc.pi_rpc_event_output(value, {"type": "message_update", "assistantMessageEvent": {
                "type": "text_delta", "contentIndex": index, "delta": "🙂" * 5}})
        self.assertLessEqual(len(value.rpc_message_blocks), 2)
        self.assertLessEqual(len(value.rpc_timeline_message_blocks), 2)
        self.assertLessEqual(len(value.rpc_timeline_delta_counts), 2)
        self.assertLessEqual(sum(len(text.encode()) for text in value.rpc_message_blocks.values()), 24)

    def test_explicit_policy_cannot_disable_its_bounds_or_borrow_mutable_sets(self):
        for changes in ({"max_event_text_bytes": 0}, {"max_events": -1}, {"max_buffer": True},
                        {"timeline_kinds": {"answer"}}, {"structured_protocols": ["pi-rpc"]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(rpc.DEFAULT_POLICY, **changes)

    def test_queue_callbacks_receive_exact_session_bound_paths_and_change_only_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            reads, writes = [], []
            session = "/isolated/session.jsonl"
            saved = {"version": 1, "sessionFile": session, "project": "/fixture/project", "messages": ["Resume 雪"]}

            def read(path):
                reads.append(path)
                return saved

            def write(path, record):
                writes.append((path, record))

            value = console(rpc_queue_directory=Path(folder), queue_io=rpc.QueueIO(read, write))
            rpc.pi_rpc_bind_queue(value, session)
            expected_path = Path(folder) / (hashlib.sha256(("/fixture/project\n" + session).encode()).hexdigest() + ".json")
            self.assertEqual(reads, [expected_path])
            self.assertEqual(writes[0][0], expected_path)
            self.assertEqual(writes[0][1], saved)
            self.assertTrue(value.rpc_queue_paused)
            self.assertFalse(value.rpc_queue_advance_allowed)
            rpc.pi_rpc_bind_queue(value, session)
            rpc.pi_rpc_save_queue(value)
            self.assertEqual(len(reads), 1)
            self.assertEqual(len(writes), 1)

    def test_queue_failure_remains_visible_without_losing_restored_messages(self):
        with tempfile.TemporaryDirectory() as folder:
            session = "/isolated/session.jsonl"
            saved = {"version": 1, "sessionFile": session, "project": "/fixture/project", "messages": ["Keep exact original"]}

            def fail(path, value):
                raise OSError("read-only fixture")

            value = console(rpc_queue_directory=Path(folder), queue_io=rpc.QueueIO(lambda path: saved, fail))
            rpc.pi_rpc_bind_queue(value, session)
            self.assertEqual(value.rpc_follow_up_queue, saved["messages"])
            self.assertTrue(value.rpc_queue_paused)
            self.assertIn("could not be saved", value.public()["queueSaveError"])
            self.assertFalse(value.rpc_queue_advance_allowed)

    def test_existing_pi_identity_is_preserved_and_omp_gets_its_separate_identity(self):
        pi = console()
        pi.rpc_queue_session = "/isolated/session.jsonl"
        expected = hashlib.sha256(json.dumps([pi.plan.project, pi.rpc_queue_session], separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(pi.conversation_id(), expected)
        pi.plan.run_id = "different-run"
        pi.plan.backend = "kolibri"
        self.assertEqual(pi.conversation_id(), expected)
        omp = console(protocol="omp-rpc")
        omp.rpc_queue_session = pi.rpc_queue_session
        self.assertNotEqual(omp.conversation_id(), expected)
        self.assertNotIn("session.jsonl", json.dumps(pi.public()))

    def test_native_aborted_result_overrides_clean_assistant_and_pauses_queue(self):
        value = console()
        value.rpc_last_assistant = {"terminalState": "clean", "textCharacters": 10, "toolCalls": 0}
        value.rpc_prompt_result_status = "aborted"
        value.rpc_queue_advance_allowed = True
        value.rpc_follow_up_queue = ["Preserve pending request"]
        output = rpc.pi_rpc_settled_output(value)
        self.assertIn(b"Queued follow-ups", output)
        self.assertTrue(value.rpc_queue_paused)
        self.assertFalse(value.rpc_queue_advance_allowed)
        self.assertEqual(value.rpc_follow_up_queue, ["Preserve pending request"])
        self.assertEqual(value.rpc_settle_revision, 1)

    def test_local_command_settles_cleanly_without_inventing_an_assistant_answer(self):
        value = console(protocol="omp-rpc")
        value.rpc_local_command = True
        value.rpc_queue_advance_allowed = True
        value.rpc_follow_up_queue = ["Next explicit request"]
        output = rpc.pi_rpc_settled_output(value)
        self.assertNotIn(b"NO FINAL ANSWER", output)
        self.assertFalse(value.rpc_queue_paused)
        self.assertEqual(value.rpc_last_assistant, {})
        self.assertFalse(any(event["kind"] == "answer" for event in value.rpc_timeline_events))

    def test_compatibility_constants_have_one_domain_source_of_truth(self):
        self.assertEqual(launcher.AGENT_CONSOLE_MAX_BUFFER, rpc.DEFAULT_POLICY.max_buffer)
        self.assertEqual(launcher.PI_RPC_TIMELINE_MAX_EVENT_TEXT_BYTES, rpc.DEFAULT_POLICY.max_event_text_bytes)
        self.assertEqual(launcher.PI_RPC_TIMELINE_KINDS, rpc.DEFAULT_POLICY.timeline_kinds)
        self.assertEqual(launcher.STRUCTURED_AGENT_PROTOCOLS, rpc.DEFAULT_POLICY.structured_protocols)


if __name__ == "__main__":
    unittest.main()
