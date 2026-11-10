from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock
import uuid

import chat_history_store
import chat_store_io
import launcher


FIXED = datetime(2026, 10, 6, 12, 0, 0, tzinfo=timezone.utc)
THREAD = "00000000-0000-4000-8000-000000000001"
TAB = "00000000-0000-4000-8000-000000000002"
TURN = "00000000-0000-4000-8000-000000000003"


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FIXED if tz else FIXED.replace(tzinfo=None)


def resume():
    return {"version": 1, "capturedAt": FIXED.isoformat(), "requiresSystemPrompt": True,
            "request": {"backend": "omlx", "client": "chat", "modelId": "synthetic-qwen",
                        "project": "/tmp/generated-fixture", "reasoning": "auto", "context": 4096, "output": 512,
                        "options": {"kv": "off", "apiKey": "must-be-stripped"},
                        "chat": {"systemPrompt": "", "sampling": "model", "contextFiles": ["must-be-stripped"]}}}


def payload():
    return {"id": THREAD, "messages": [{"role": "user", "content": "Generated fixture prompt"},
                                       {"role": "assistant", "content": "Generated answer", "reasoning": "Visible model reasoning",
                                        "usage": {"promptTokens": 128, "completionTokens": 32, "cachedPromptTokens": 100},
                                        "createdAt": "2026-10-06T13:00:00+01:00"}],
            "metadata": {"model": "Synthetic Qwen", "backend": "omlx", "context": 4096, "output": 512,
                         "reasoning": "auto", "systemPrompt": "must-be-stripped", "contextFiles": ["private-file"]}}


class ChatHistoryStoreEquivalenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.controller_dir = root / "controller"
        self.module_dir = root / "module"
        self.store = chat_history_store.ChatHistoryStore(
            self.module_dir / "chat-history.json", self.module_dir / "chat-turn-journal.json",
            read_document=launcher.read_json, write_document=launcher.atomic_json,
            route_request_whitelist=launcher._profile_request_whitelist,
            clock=lambda: FIXED, new_id=lambda: THREAD,
        )
        self.state_patch = mock.patch.object(launcher, "STATE_DIR", self.controller_dir)
        self.date_patch = mock.patch.object(launcher, "datetime", FixedDateTime)
        self.uuid_patch = mock.patch.object(launcher.uuid, "uuid4", return_value=uuid.UUID(THREAD))
        for patch in (self.state_patch, self.date_patch, self.uuid_patch):
            patch.start(); self.addCleanup(patch.stop)

    def equivalent_documents(self):
        for name in ("chat-history.json", "chat-turn-journal.json"):
            controller = self.controller_dir / name
            module = self.module_dir / name
            self.assertEqual(controller.exists(), module.exists())
            if controller.exists():
                self.assertEqual(module.read_bytes(), controller.read_bytes())

    def test_save_get_update_delete_and_file_envelopes_are_exactly_equivalent(self):
        golden = json.loads((Path(__file__).parent / "fixtures" / "chat-history-store-v8.json").read_text())
        saved = self.store.save(payload(), resume_contract=resume())
        self.assertEqual(saved, golden["save"])
        self.assertEqual(saved, launcher.save_chat_history(payload(), resume_contract=resume()))
        self.equivalent_documents()
        self.assertEqual(self.store.inventory(), launcher.chat_history_inventory())
        self.assertEqual(self.store.get({"id": THREAD}), golden["get"])
        self.assertEqual(self.store.get({"id": THREAD}), launcher.get_chat_history({"id": THREAD}))
        updated = self.store.update({"id": THREAD, "title": "  Renamed   conversation ", "pinned": True})
        self.assertEqual(updated, golden["update"])
        self.assertEqual(updated, launcher.update_chat_history({"id": THREAD, "title": "  Renamed   conversation ", "pinned": True}))
        self.assertEqual(json.loads(self.store.history_path.read_text()), golden["storedAfterUpdate"])
        self.equivalent_documents()
        deleted = self.store.delete({"id": THREAD})
        self.assertEqual(deleted, golden["delete"])
        self.assertEqual(deleted, launcher.delete_chat_history({"id": THREAD}))
        self.equivalent_documents()

    def test_origin_metadata_branch_lineage_and_private_resume_are_equivalent(self):
        self.store.save(payload(), resume_contract=resume())
        launcher.save_chat_history(payload(), resume_contract=resume())
        changed = payload()
        changed["metadata"] = {"model": "Different displayed model", "backend": "mtplx"}
        self.assertEqual(self.store.save(changed), launcher.save_chat_history(changed))
        branch = {**payload(), "id": "00000000-0000-4000-8000-000000000004",
                  "metadata": {"branchParentId": THREAD, "branchParentTitle": "Original conversation",
                               "branchPoint": 2, "branchKind": "continue"}}
        self.assertEqual(self.store.save(branch), launcher.save_chat_history(branch))
        self.equivalent_documents()
        public = self.store.get({"id": THREAD})["thread"]
        self.assertEqual(public["originModel"], "Synthetic Qwen")
        self.assertEqual(public["model"], "Different displayed model")
        self.assertNotIn("resumeContract", public)
        self.assertTrue(public["resumeNeedsSystemPrompt"])

    def test_privacy_drops_request_only_fields_and_rejects_system_prompt_resume(self):
        saved = self.store.save(payload(), resume_contract=resume())
        raw = self.store.history_path.read_text()
        self.assertNotIn("must-be-stripped", raw)
        self.assertNotIn("private-file", raw)
        self.assertNotIn("apiKey", raw)
        self.assertNotIn("contextFiles", raw)
        self.assertNotIn("resumeContract", json.dumps(saved))
        private = resume()
        private["request"]["chat"]["systemPrompt"] = "Private request instruction"
        for operation in (self.store.save, launcher.save_chat_history):
            with self.assertRaisesRegex(ValueError, "stored system-prompt"):
                operation(payload(), resume_contract=private)

    def test_interrupted_checkpoint_recovery_and_clear_match_controller(self):
        messages = [{"role": "user", "content": "Generated interrupted task"},
                    {"role": "assistant", "content": "Partial output", "interrupted": True,
                     "failure": "Generated disconnect"}]
        checkpoint = {"tabId": TAB, "turnId": TURN, "historyId": THREAD, "messages": messages,
                      "metadata": payload()["metadata"]}
        self.assertEqual(self.store.checkpoint(checkpoint, resume_contract=resume()),
                         launcher.save_chat_turn_checkpoint(checkpoint, resume_contract=resume()))
        self.equivalent_documents()
        self.assertEqual(self.store.recover_checkpoint({"tabId": TAB}), launcher.recover_chat_turn_checkpoint({"tabId": TAB}))
        self.equivalent_documents()
        self.assertFalse(self.store.recover_checkpoint({"tabId": TAB})["recovered"])
        self.assertEqual(self.store.clear_checkpoint({"tabId": TAB, "turnId": TURN}), launcher.clear_chat_turn_checkpoint({"tabId": TAB, "turnId": TURN}))

    def test_completed_history_wins_against_older_checkpoint(self):
        self.store.save(payload()); launcher.save_chat_history(payload())
        entry = {"tabId": TAB, "turnId": TURN, "historyId": THREAD,
                 "updatedAt": (FIXED - timedelta(seconds=1)).isoformat(), "createdAt": FIXED.isoformat(),
                 "metadata": {}, "messages": [{"role": "user", "content": "older"},
                                                {"role": "assistant", "content": "older", "interrupted": True}]}
        self.store.write_journal_unlocked([entry]); launcher._write_chat_turn_journal_unlocked([entry])
        result = self.store.recover_checkpoint({"tabId": TAB})
        self.assertEqual(result, launcher.recover_chat_turn_checkpoint({"tabId": TAB}))
        self.assertTrue(result["discarded"])
        self.equivalent_documents()

    def test_pinned_retention_and_journal_age_character_limits_are_preserved(self):
        records = [{"id": str(uuid.UUID(int=index + 1)), "pinned": index == 0,
                    "updatedAt": f"2026-10-06T12:{index % 60:02}:00+00:00", "messages": []}
                   for index in range(120)]
        self.store.write_history_unlocked(records); launcher._write_chat_history_unlocked(records)
        self.equivalent_documents()
        loaded = self.store.load_history_unlocked()
        self.assertEqual(len(loaded), 100)
        self.assertTrue(loaded[0]["pinned"])
        entries = [{"tabId": str(index), "updatedAt": (FIXED - timedelta(days=index)).isoformat(),
                    "messages": [{"content": "fixture", "reasoning": "fixture"}]} for index in range(12)]
        self.store.write_journal_unlocked(entries); launcher._write_chat_turn_journal_unlocked(entries)
        self.equivalent_documents()
        self.assertLessEqual(len(self.store.load_journal_unlocked()), 8)

    def test_message_validation_equivalence_for_usage_dates_and_invalid_transcript_shapes(self):
        valid = payload()["messages"]
        self.assertEqual(self.store.validate_messages(valid), launcher._validated_chat_history_messages(valid))
        bad = [
            [{"role": "system", "content": "cannot persist"}],
            [{"role": "assistant", "content": "", "usage": {"promptTokens": True, "completionTokens": 1}}],
            [{"role": "user", "content": "x", "interrupted": True}],
            [{"role": "assistant", "content": "x", "createdAt": "2026-10-06T12:00:00"}],
            [{"role": "assistant", "content": "x", "usage": {"promptTokens": 2, "completionTokens": 1, "cachedPromptTokens": 3}}],
        ]
        for values in bad:
            with self.subTest(values=values):
                failures = []
                for validator in (self.store.validate_messages, launcher._validated_chat_history_messages):
                    with self.assertRaises(ValueError) as error:
                        validator(deepcopy(values))
                    failures.append(str(error.exception))
                self.assertEqual(*failures)


class ChatStoreIOTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = chat_history_store.ChatHistoryStore(
            self.root / "chat-history.json", self.root / "chat-turn-journal.json",
            route_request_whitelist=launcher._profile_request_whitelist,
            clock=lambda: FIXED,
        )

    def test_already_allowed_escaped_transcript_survives_the_former_4mib_reader_limit(self):
        values = payload()
        values["messages"][0]["content"] = "\x01" * 750_000
        self.store.save(values)
        self.assertGreater(self.store.history_path.stat().st_size, launcher.MAX_JSON)
        self.assertEqual(launcher.read_json(self.store.history_path), {}, "Demonstrate the former silent size mismatch")
        self.assertEqual(self.store.get({"id": THREAD})["thread"]["messages"][0]["content"], "\x01" * 750_000)
        self.assertEqual(len(self.store.inventory()["threads"]), 1)
        self.assertEqual(self.store.history_path.stat().st_mode & 0o777, 0o600)

    def test_incremental_reader_preserves_unicode_quotes_backslashes_braces_and_chunk_boundaries(self):
        prefix = '{"version":8,"threads":[{"content":"'
        body = "a" * (65535 - len(prefix)) + '\\"' + ' 🌎 \\\\ { [ \\u2603 ] } '
        document = prefix + body + '"}]}'
        path = self.store.history_path
        path.write_text(document, encoding="utf-8")
        expected = json.loads(document)
        actual = chat_store_io.read_document(path, collection_key="threads", maximum_bytes=200_000, maximum_record_bytes=100_000)
        self.assertEqual(actual, expected)

    def test_corrupt_oversized_wrong_schema_or_collection_files_are_preserved_on_mutation(self):
        self.store.save(payload())
        corrupt = [b'{"version":8,"threads":[', b'{"version":8,"threads":{}}',
                   b'{"version":999,"threads":[]}', b'{"version":8,"threads":[],"threads":[]}',
                   b'{"version":8,"threads":[]} trailing', b'{}', b'\xff']
        for data in corrupt:
            with self.subTest(data=data):
                self.store.history_path.write_bytes(data)
                with self.assertRaises(chat_store_io.StoreReadError):
                    self.store.save(payload())
                self.assertEqual(self.store.history_path.read_bytes(), data)
        limits = chat_history_store.ChatHistoryLimits(max_threads=1, max_characters=10, max_messages=2, metadata_max_bytes=100)
        small = chat_history_store.ChatHistoryStore(self.store.history_path, self.store.journal_path,
                                                   limits=limits, route_request_whitelist=launcher._profile_request_whitelist)
        data = b" " * (limits.history_max_bytes + 1)
        small.history_path.write_bytes(data)
        with self.assertRaises(chat_store_io.StoreReadError):
            small.delete({"id": THREAD})
        self.assertEqual(small.history_path.read_bytes(), data)

    def test_journal_corruption_cannot_clear_or_recover_into_history(self):
        self.store.save(payload())
        history = self.store.history_path.read_bytes()
        for data in [b'{"version":2,"entries":[]}', b'{"version":1,"entries":null}', b'{"entries":[']:
            self.store.journal_path.write_bytes(data)
            with self.assertRaises(chat_store_io.StoreReadError):
                self.store.recover_checkpoint({"tabId": TAB})
            self.assertEqual(self.store.history_path.read_bytes(), history)
            self.assertEqual(self.store.journal_path.read_bytes(), data)
            with self.assertRaises(chat_store_io.StoreReadError):
                self.store.clear_checkpoint({"tabId": TAB, "turnId": TURN})

    def test_reader_enforces_per_record_bound_without_materializing_the_entire_collection(self):
        path = self.store.history_path
        document = {"version": 8, "threads": [{"content": "x" * 200_000}, {"content": "second"}]}
        path.write_text(json.dumps(document))
        with self.assertRaisesRegex(chat_store_io.StoreReadError, "record exceeds"):
            chat_store_io.read_document(path, collection_key="threads", maximum_bytes=300_000, maximum_record_bytes=100_000)
        self.assertEqual(json.loads(path.read_text()), document)

    def test_tiny_records_and_invalid_array_values_cannot_exceed_the_decoded_count_budget(self):
        path = self.store.history_path
        for records in [[{}, {}, {}], [0], [[]], ["not a record"]]:
            document = {"version": 8, "threads": records}
            path.write_text(json.dumps(document))
            with self.subTest(records=records), self.assertRaises(chat_store_io.StoreReadError):
                chat_store_io.read_document(path, collection_key="threads", maximum_bytes=10_000,
                                            maximum_record_bytes=1_000, maximum_records=2)
            self.assertEqual(json.loads(path.read_text()), document)

    def test_message_counts_character_budgets_and_nested_metadata_are_checked_before_retention(self):
        limits = chat_history_store.ChatHistoryLimits(max_messages=2, max_characters=10)
        small = chat_history_store.ChatHistoryStore(self.store.history_path, self.store.journal_path,
                                                   limits=limits, route_request_whitelist=launcher._profile_request_whitelist)
        records = [
            {"messages": [{"content": "x"}] * 3},
            {"messages": [{"content": "x" * 11}]},
            {"messages": "not a message list"},
            {"metadata": list(range(20_000))},
        ]
        for record in records:
            document = {"version": 8, "threads": [record]}
            self.store.history_path.write_text(json.dumps(document))
            with self.subTest(record_keys=list(record)), self.assertRaises(chat_store_io.StoreReadError):
                small.inventory()
            self.assertEqual(json.loads(self.store.history_path.read_text()), document)

    def test_root_metadata_key_count_is_bounded(self):
        document = {"version": 8, "threads": [], **{f"unused{index}": 0 for index in range(16)}}
        self.store.history_path.write_text(json.dumps(document))
        with self.assertRaisesRegex(chat_store_io.StoreReadError, "root metadata"):
            self.store.inventory()
        self.assertEqual(json.loads(self.store.history_path.read_text()), document)

    def test_structured_record_overflow_is_rejected_before_decoding_a_large_array(self):
        document = {"version": 8, "threads": [{"unexpected": list(range(200))}]}
        path = self.store.history_path
        path.write_text(json.dumps(document))
        with mock.patch.object(chat_store_io.json, "loads", wraps=json.loads) as decoder:
            with self.assertRaisesRegex(chat_store_io.StoreReadError, "structured data"):
                chat_store_io.read_document(path, collection_key="threads", maximum_bytes=10_000,
                                            maximum_record_bytes=5_000, maximum_structural_tokens=100)
        self.assertTrue(all('"unexpected"' not in call.args[0] for call in decoder.call_args_list))
        self.assertEqual(json.loads(path.read_text()), document)

    def test_broken_symlink_is_unreadable_storage_not_an_empty_history(self):
        self.store.history_path.symlink_to("missing-private-history.json")
        with self.assertRaises(chat_store_io.StoreReadError):
            self.store.save(payload())
        self.assertTrue(self.store.history_path.is_symlink())

    def test_failed_or_oversized_write_keeps_original_and_removes_private_temporary_file(self):
        path = self.store.history_path
        original = b'{"version":8,"threads":[]}'
        path.write_bytes(original)
        with self.assertRaises(chat_store_io.StoreReadError):
            chat_store_io.write_document(path, {"version": 8, "threads": [{"content": "large" * 100}]}, maximum_bytes=100)
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse(list(self.root.glob(".chat-history.json.*.tmp")))

        with mock.patch.object(chat_store_io.os, "replace", side_effect=OSError("generated fixture failure")):
            with self.assertRaises(chat_store_io.StoreReadError):
                chat_store_io.write_document(path, {"version": 8, "threads": []}, maximum_bytes=100)
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse(list(self.root.glob(".chat-history.json.*.tmp")))

    def test_mutation_returns_its_committed_inventory_without_rereading_all_transcripts(self):
        reader = mock.Mock(wraps=self.store._read_document)
        self.store._read_document = reader
        self.store.save(payload())
        self.assertEqual(reader.call_count, 1)
        reader.reset_mock()
        self.store.update({"id": THREAD, "pinned": True})
        self.assertEqual(reader.call_count, 1)
        reader.reset_mock()
        self.store.delete({"id": THREAD})
        self.assertEqual(reader.call_count, 1)

    def test_concurrent_recovery_promotes_one_checkpoint_once(self):
        checkpoint = {"tabId": TAB, "turnId": TURN, "historyId": THREAD,
                      "messages": [{"role": "user", "content": "Generated task"},
                                   {"role": "assistant", "content": "Partial", "interrupted": True}]}
        self.store.checkpoint(checkpoint)
        start = threading.Barrier(3)
        results, errors = [], []
        def recover():
            try:
                start.wait()
                results.append(self.store.recover_checkpoint({"tabId": TAB}))
            except Exception as error:
                errors.append(error)
        threads = [threading.Thread(target=recover) for _ in range(2)]
        for thread in threads:
            thread.start()
        start.wait()
        for thread in threads:
            thread.join(2)
            self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(sum(result["recovered"] for result in results), 1)
        self.assertEqual(len(self.store.inventory()["threads"]), 1)
        self.assertEqual(self.store.load_journal_unlocked(), [])

    def test_recovery_cannot_overwrite_a_completed_save_that_waited_on_the_same_history(self):
        writer_waiting = threading.Event()
        class OrderedLock:
            def __init__(self):
                self.condition = threading.Condition()
                self.owner = None
                self.queue = []
            def __enter__(self):
                identity = threading.get_ident()
                with self.condition:
                    self.queue.append(identity)
                    if threading.current_thread().name == "completed-save":
                        writer_waiting.set()
                    while self.owner is not None or self.queue[0] != identity:
                        self.condition.wait()
                    self.queue.pop(0)
                    self.owner = identity
                return self
            def __exit__(self, *_):
                with self.condition:
                    self.owner = None
                    self.condition.notify_all()
        self.store.history_lock = OrderedLock()
        self.store._clock = lambda: FIXED + timedelta(seconds=1) if threading.current_thread().name == "completed-save" else FIXED
        checkpoint = {"tabId": TAB, "turnId": TURN, "historyId": THREAD,
                      "messages": [{"role": "user", "content": "Generated task"},
                                   {"role": "assistant", "content": "Partial", "interrupted": True}]}
        self.store.checkpoint(checkpoint)
        reading_history = threading.Event()
        actual_reader = self.store._read_document
        def reader(path):
            value = actual_reader(path)
            if path == self.store.history_path and threading.current_thread().name == "recover":
                reading_history.set()
                self.assertTrue(writer_waiting.wait(2))
            return value
        self.store._read_document = reader
        errors = []
        def recover():
            try:
                self.store.recover_checkpoint({"tabId": TAB})
            except Exception as error:
                errors.append(error)
        def completed_save():
            try:
                self.store.save({"id": THREAD, "messages": [{"role": "user", "content": "Generated task"},
                                                            {"role": "assistant", "content": "Completed output"}]})
            except Exception as error:
                errors.append(error)
        recovery = threading.Thread(target=recover, name="recover")
        writer = threading.Thread(target=completed_save, name="completed-save")
        recovery.start()
        self.assertTrue(reading_history.wait(2))
        writer.start()
        for thread in (recovery, writer):
            thread.join(2)
            self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        thread = self.store.get({"id": THREAD})["thread"]
        self.assertEqual(thread["messages"][-1]["content"], "Completed output")
        self.assertNotIn("interrupted", thread["messages"][-1])


if __name__ == "__main__":
    unittest.main()
