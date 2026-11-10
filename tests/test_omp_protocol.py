"""Official OMP v18.6.3 wire and yield/settlement contract regressions.

Fixtures use the published rpc.md schemas and rpc-frame.ts framing algorithm;
native process/provider qualification is separately exercised by installed RPC
tests. These tests import neither launcher nor any model/process runtime.
"""
import base64
import copy
import json
import unittest

from omp_protocol import (Adapter, FrameDecoder, ProtocolError, MAX_RPC_FRAME_BYTES,
                          MAX_RPC_REASSEMBLED_BYTES, RPC_CHUNK_PAYLOAD_BYTES,
                          MAX_PENDING_COMMANDS, MAX_COMMAND_OUTPUT_BYTES, encode_output_frames)


def line(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"


READY = {"type": "ready", "protocolVersion": 1, "supportedProtocolVersions": [1, 2],
         "maxFrameBytes": 1048576, "maxReassembledFrameBytes": 67108864}
IDLE = {"isStreaming": False, "isCompacting": False, "isSettled": True,
        "hasPendingAsyncWork": False, "queuedMessageCount": 0,
        "queuedMessages": {"steering": [], "followUp": []}, "sessionFile": "/isolated/session.jsonl"}


def source_chunks(payload, chunk_id="rpc-1"):
    """Independent translation of official encoder's 256KiB/base64 format."""
    count = (len(payload) + RPC_CHUNK_PAYLOAD_BYTES - 1) // RPC_CHUNK_PAYLOAD_BYTES
    return [{"type": "rpc_chunk", "chunkId": chunk_id, "index": index,
             "count": count, "byteLength": len(payload),
             "data": base64.b64encode(payload[index * RPC_CHUNK_PAYLOAD_BYTES:
                                             (index + 1) * RPC_CHUNK_PAYLOAD_BYTES]).decode("ascii")}
            for index in range(count)]


def response(identifier, command, **values):
    return {"type": "response", "id": identifier, "command": command, "success": True, **values}


class WireTests(unittest.TestCase):
    def setUp(self):
        # Multibyte characters cross physical chunk boundaries. This exceeds
        # 1MiB without requiring any model or large-memory maximum-size test.
        self.value = {"type": "message_end", "messageId": "msg-12",
                      "message": {"role": "assistant", "content": [{"type": "text", "text": "🙂雪" * 160000}]}}
        self.raw = line(self.value)[:-1]

    def test_actual_source_chunk_shape_is_lossless_and_nonterminal_until_final(self):
        decoder = FrameDecoder()
        chunks = source_chunks(self.raw)
        self.assertGreater(len(chunks), 3)
        for item in chunks[:-1]:
            self.assertIsNone(decoder.receive_line(line(item)))
        self.assertEqual(decoder.receive_line(line(chunks[-1])), self.value)
        decoder.finish()
        self.assertEqual(decoder.receive_line(line({"type": "agent_end", "messages": [], "messageCount": 12})),
                         {"type": "agent_end", "messages": [], "messageCount": 12})

    def test_stdout_encoder_matches_source_chunk_headers_and_physical_limit(self):
        encoded = list(encode_output_frames(self.value, chunk_id="rpc-1"))
        self.assertEqual([json.loads(item) for item in encoded], source_chunks(self.raw))
        self.assertTrue(all(len(item) <= MAX_RPC_FRAME_BYTES for item in encoded))
        decoder = FrameDecoder()
        result = None
        for item in encoded:
            result = decoder.receive_line(item)
        self.assertEqual(result, self.value)

    def test_exact_physical_boundary_includes_newline(self):
        overhead = len(line({"type": "notice", "message": ""}))
        value = {"type": "notice", "message": "a" * (MAX_RPC_FRAME_BYTES - overhead)}
        self.assertEqual(len(line(value)), MAX_RPC_FRAME_BYTES)
        self.assertEqual(FrameDecoder().receive_line(line(value)), value)
        value["message"] += "a"
        with self.assertRaises(ProtocolError):
            FrameDecoder().receive_line(line(value))
        self.assertEqual(json.loads(next(encode_output_frames(value)))["type"], "rpc_chunk")

    def test_v1_fixture_encoder_rejects_oversize_without_silent_elision(self):
        with self.assertRaises(ProtocolError):
            list(encode_output_frames(self.value, protocol_version=1))

    def test_byte_lines_must_be_complete_strict_utf8_json_objects(self):
        invalid = [b'{}', b'{}\n{}\n', b'[]\n', b'null\n', b'{"type":"x","type":"y"}\n',
                   b'{"type":"x","value":NaN}\n', b'{"type":"x","value":1e9999}\n', b'{"type":"\xff"}\n']
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ProtocolError):
                decoder = FrameDecoder()
                decoder.receive_line(item)
            self.assertTrue(decoder.failed)

    def test_canonical_base64_and_per_chunk_decoded_bounds(self):
        for data in ("", "!!!!", "YQ", "YR==", "YQ===", "YQ==\n", "雪", base64.b64encode(b'a' * (RPC_CHUNK_PAYLOAD_BYTES + 1)).decode()):
            item = source_chunks(self.raw)[0]
            item["data"] = data
            with self.subTest(data=data[:20]), self.assertRaises(ProtocolError):
                FrameDecoder().receive_line(line(item))

    def test_metadata_types_ranges_and_native_count_limit(self):
        changes = [("chunkId", ""), ("chunkId", "a" * 129), ("index", True), ("index", 0.0),
                   ("index", -1), ("index", 99), ("count", True), ("count", 1), ("count", 257),
                   ("byteLength", True), ("byteLength", MAX_RPC_FRAME_BYTES - 1),
                   ("byteLength", MAX_RPC_REASSEMBLED_BYTES + 1), ("byteLength", 1 << 54)]
        for key, value in changes:
            item = source_chunks(self.raw)[0]
            item[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ProtocolError):
                FrameDecoder().receive_line(line(item))

    def test_native_chunk_id_allows_unicode_but_remains_bounded(self):
        decoder = FrameDecoder()
        for item in source_chunks(self.raw, "native 雪 id"):
            result = decoder.receive_line(line(item))
        self.assertEqual(result, self.value)

    def test_interleaving_reordering_interrupting_and_mismatched_headers_fail_closed(self):
        for change in ({"index": 0}, {"index": 2}, {"chunkId": "other"}, {"count": 9}, {"byteLength": len(self.raw) + 1}):
            chunks = source_chunks(self.raw)
            decoder = FrameDecoder()
            decoder.receive_line(line(chunks[0]))
            chunks[1].update(change)
            with self.subTest(change=change), self.assertRaises(ProtocolError):
                decoder.receive_line(line(chunks[1]))
            self.assertTrue(decoder.failed)
            with self.assertRaises(ProtocolError):
                decoder.receive_line(line({"type": "session_settled"}))
        decoder = FrameDecoder()
        decoder.receive_line(line(source_chunks(self.raw)[0]))
        with self.assertRaises(ProtocolError):
            decoder.receive_line(line({"type": "session_settled"}))

    def test_final_byte_length_and_strict_logical_utf8_json(self):
        invalid = [self.raw[:-1], self.raw.replace(b'\xf0', b'\xff', 1),
                   b'[' + b' ' * MAX_RPC_FRAME_BYTES + b']',
                   b'{"type":"rpc_chunk","data":"' + b'a' * MAX_RPC_FRAME_BYTES + b'"}']
        for payload in invalid:
            with self.subTest(prefix=payload[:30]), self.assertRaises(ProtocolError):
                decoder = FrameDecoder()
                for item in source_chunks(payload):
                    decoder.receive_line(line(item))
        chunks = source_chunks(self.raw)
        for item in chunks:
            item["byteLength"] += 1
        with self.assertRaises(ProtocolError):
            decoder = FrameDecoder()
            for item in chunks:
                decoder.receive_line(line(item))

    def test_eof_cannot_discard_incomplete_logical_frame(self):
        decoder = FrameDecoder()
        decoder.receive_line(line(source_chunks(self.raw)[0]))
        with self.assertRaises(ProtocolError):
            decoder.finish()
        self.assertTrue(decoder.failed)


class LifecycleTests(unittest.TestCase):
    def boot(self, *, negotiate=True):
        adapter = Adapter(negotiate_v2=negotiate)
        result = adapter.receive_line(line(READY))
        self.assertFalse(adapter.can_input)
        if negotiate:
            self.assertEqual(len(result.commands), 1)
            command = result.commands[0]
            adapter.encode_command(command)
            self.assertFalse(adapter.can_input)
            adapter.receive_line(line(response(command["id"], "negotiate_protocol", data={"protocolVersion": 2})))
        adapter.encode_command({"id": "state-boot", "type": "get_state"})
        events = adapter.receive_line(line(response("state-boot", "get_state", data=copy.deepcopy(IDLE)))).events
        self.assertFalse(events[-1]["data"]["isStreaming"])
        self.assertTrue(adapter.can_input)
        self.assertFalse(adapter.busy)
        return adapter

    def prompt(self, adapter, identifier="prompt-1", command="prompt"):
        adapter.encode_command({"id": identifier, "type": command, "message": "Read the fixture"})
        adapter.receive_line(line(response(identifier, command)))

    def result(self, identifier="prompt-1", **values):
        return {"type": "prompt_result", "id": identifier, "agentInvoked": True,
                "status": "completed", "sessionSettled": True, **values}

    def test_qualification_requires_ready_negotiation_and_explicit_state_contract(self):
        adapter = Adapter()
        with self.assertRaisesRegex(ProtocolError, "qualified"):
            adapter.encode_command({"id": "early", "type": "prompt", "message": "x"})
        self.assertFalse(adapter.decoder.failed)
        commands = adapter.receive_line(line(READY)).commands
        adapter.encode_command({"id": "state", "type": "get_state"})
        adapter.receive_line(line(response("state", "get_state", data=IDLE)))
        self.assertFalse(adapter.can_input)
        adapter.encode_command(commands[0])
        adapter.receive_line(line(response(commands[0]["id"], "negotiate_protocol", data={"protocolVersion": 2})))
        self.assertTrue(adapter.can_input)
        self.assertEqual(adapter.protocol_version, 2)

    def test_explicit_v1_opt_out_still_requires_native_settlement_state(self):
        adapter = self.boot(negotiate=False)
        self.assertEqual(adapter.protocol_version, 1)
        self.prompt(adapter)
        self.assertTrue(adapter.busy)

    def test_unsupported_ready_and_missing_nonboolean_or_contradictory_state_fail_explicitly(self):
        for key, value in (("protocolVersion", True), ("supportedProtocolVersions", [True, 2]),
                           ("maxFrameBytes", 999999), ("maxReassembledFrameBytes", 999999)):
            ready = {**READY, key: value}
            with self.subTest(key=key), self.assertRaises(ProtocolError):
                Adapter().receive_line(line(ready))
        for update in ({"isSettled": None}, {"hasPendingAsyncWork": 0}, {"isSettled": True, "hasPendingAsyncWork": True},
                       {"isStreaming": True}, {"queuedMessageCount": True}):
            adapter = self.boot()
            adapter.encode_command({"id": "state-check", "type": "get_state"})
            with self.subTest(update=update), self.assertRaises(ProtocolError):
                adapter.receive_line(line(response("state-check", "get_state", data={**IDLE, **update})))
            self.assertFalse(adapter.can_input)

    def test_only_matching_negotiate_response_can_change_version(self):
        adapter = Adapter()
        command = adapter.receive_line(line(READY)).commands[0]
        adapter.encode_command(command)
        with self.assertRaises(ProtocolError):
            adapter.receive_line(line(response("unrelated", "negotiate_protocol", data={"protocolVersion": 2})))
        self.assertEqual(adapter.protocol_version, 1)

    def test_chunked_output_before_negotiation_is_fatal(self):
        adapter = Adapter()
        adapter.receive_line(line(READY))
        value = {"type": "command_output", "text": "x" * MAX_RPC_FRAME_BYTES}
        with self.assertRaisesRegex(ProtocolError, "before protocol v2"):
            adapter.receive_line(next(encode_output_frames(value)))

    def test_agent_end_yield_with_async_does_not_settle_or_complete_prompt(self):
        adapter = self.boot()
        self.prompt(adapter)
        adapter.receive_line(line({"type": "agent_start"}))
        ended = adapter.receive_line(line({"type": "agent_end", "messages": [], "yielded": True,
                                          "isTerminal": False, "awaitingAsyncWork": True}))
        self.assertEqual([event["type"] for event in ended.events], ["agent_end"])
        self.assertTrue(adapter.busy)
        self.assertEqual(adapter.active_prompt_id, "prompt-1")
        result = adapter.receive_line(line(self.result(sessionSettled=False)))
        self.assertEqual(result.events[0]["type"], "launcher_prompt_result")
        self.assertTrue(adapter.busy)
        self.assertEqual(adapter.active_prompt_id, "")
        adapter.receive_line(line({"type": "agent_start"}))
        adapter.receive_line(line({"type": "agent_end", "messages": [], "yielded": True}))
        self.assertEqual(adapter.receive_line(line({"type": "session_settled"})).events, [{"type": "agent_settled"}])
        self.assertFalse(adapter.busy)

    def test_final_prompt_result_then_native_settlement_emits_exactly_once_without_probe(self):
        adapter = self.boot()
        self.prompt(adapter)
        adapter.receive_line(line({"type": "agent_start"}))
        adapter.receive_line(line({"type": "agent_end", "messages": [], "yielded": True}))
        result = adapter.receive_line(line(self.result()))
        self.assertEqual([event["type"] for event in result.events], ["launcher_prompt_result"])
        self.assertFalse(adapter.busy)
        self.assertEqual(adapter.receive_line(line({"type": "session_settled"})).events, [{"type": "agent_settled"}])
        self.assertEqual(adapter.receive_line(line({"type": "session_settled"})).events, [])

    def test_retry_or_compaction_end_never_completes_a_prompt(self):
        adapter = self.boot()
        self.prompt(adapter)
        adapter.receive_line(line({"type": "agent_start"}))
        end = adapter.receive_line(line({"type": "agent_end", "messages": [], "yielded": False, "isTerminal": False}))
        self.assertEqual(end.events[0]["yielded"], False)
        self.assertTrue(adapter.busy)
        self.assertEqual(adapter.active_prompt_id, "prompt-1")

    def test_prompt_result_uses_correlated_status_not_clean_assistant_guess(self):
        for status in ("aborted", "error"):
            adapter = self.boot()
            self.prompt(adapter)
            adapter.receive_line(line({"type": "agent_start"}))
            adapter.receive_line(line({"type": "message_end", "messageId": "msg-2",
                                      "message": {"role": "assistant", "stopReason": "stop", "content": []}}))
            extra = {"error": {"message": "provider exhausted retries", "retryable": False}} if status == "error" else {}
            event = adapter.receive_line(line(self.result(status=status, **extra))).events[0]
            self.assertEqual(event["status"], status)
            self.assertEqual(event["id"], "prompt-1")

    def test_unrelated_duplicate_or_result_before_ack_cannot_release_a_prompt(self):
        for scenario in ("unrelated", "before-ack", "duplicate"):
            adapter = self.boot()
            if scenario == "before-ack":
                adapter.encode_command({"id": "prompt-1", "type": "prompt", "message": "x"})
            else:
                self.prompt(adapter)
            if scenario == "duplicate":
                adapter.receive_line(line(self.result()))
            identifier = "other" if scenario == "unrelated" else "prompt-1"
            with self.subTest(scenario=scenario), self.assertRaises(ProtocolError):
                adapter.receive_line(line(self.result(identifier)))
            self.assertFalse(adapter.can_input)

    def test_malformed_prompt_status_and_notice_shapes_raise_protocol_error_not_type_error(self):
        for frame in ({"type": "notice", "level": [], "message": "notice"},
                      self.result(status={"wrong": "shape"}), self.result(status=[]),
                      self.result(agentInvoked=1), self.result(sessionSettled=0),
                      self.result(status="error", error={"message": "failed", "retryable": "false"})):
            adapter = self.boot()
            self.prompt(adapter)
            with self.subTest(frame=frame), self.assertRaises(ProtocolError):
                adapter.receive_line(line(frame))
            self.assertFalse(adapter.can_input)

    def test_late_same_id_failure_after_ack_waits_for_error_result(self):
        adapter = self.boot()
        self.prompt(adapter, command="abort_and_prompt")
        event = adapter.receive_line(line(response("prompt-1", "abort_and_prompt", success=False, error="setup failed"))).events[0]
        self.assertEqual(event["command"], "prompt")
        self.assertTrue(event["ompAwaitingPromptResult"])
        self.assertTrue(adapter.busy)
        result = adapter.receive_line(line(self.result(agentInvoked=False, status="error",
                                                     error={"message": "setup failed", "retryable": False})))
        self.assertEqual(result.events[0]["status"], "error")

    def failed_preflight(self, adapter, identifier="failed-preflight"):
        adapter.encode_command({"id": identifier, "type": "prompt", "message": "rejected input"})
        return adapter.receive_line(line(response(identifier, "prompt", success=False, error="Preparation failed")))

    def test_native_tracked_preflight_failure_then_ack_and_result_keeps_connection_usable(self):
        adapter = self.boot()
        failure = self.failed_preflight(adapter)
        self.assertTrue(failure.events[0]["ompAwaitingPromptResult"])
        self.assertTrue(adapter.busy)
        self.assertTrue(adapter.can_input)
        adapter.receive_line(line(response("failed-preflight", "prompt")))
        result = adapter.receive_line(line(self.result("failed-preflight", agentInvoked=False, status="error",
                                                      error={"message": "Preparation failed", "retryable": False})))
        self.assertEqual(result.events[0]["status"], "error")
        self.assertTrue(adapter.can_input)
        self.assertFalse(adapter.busy)
        self.assertEqual(result.commands[0]["type"], "get_state", "No agent_start means no native settlement watcher")

    def test_outer_setup_only_failure_retires_on_fresh_quiet_state_without_fake_prompt_result(self):
        adapter = self.boot()
        failure = self.failed_preflight(adapter)
        command = failure.commands[0]
        adapter.encode_command(command)
        events = adapter.receive_line(line(response(command["id"], "get_state", data=IDLE))).events
        self.assertEqual(events[0]["type"], "response")
        self.assertFalse(events[0]["success"])
        self.assertFalse(events[0]["ompAwaitingPromptResult"])
        self.assertEqual(events[0]["error"], "Preparation failed")
        self.assertFalse(any(event["type"] in {"message_end", "launcher_prompt_result"} for event in events))
        self.assertFalse(adapter.busy)
        self.assertTrue(adapter.can_input)
        self.prompt(adapter, "recovery")
        self.assertEqual(adapter.active_prompt_id, "recovery")

    def test_state_encoded_before_error_is_not_a_causal_rejection_barrier(self):
        adapter = self.boot()
        adapter.encode_command({"id": "old-state", "type": "get_state"})
        failure = self.failed_preflight(adapter)
        events = adapter.receive_line(line(response("old-state", "get_state", data=IDLE))).events
        self.assertTrue(events[-1]["data"]["isStreaming"])
        self.assertFalse(any(event.get("success") is False for event in events))
        self.assertTrue(adapter.busy)
        command = failure.commands[0]
        adapter.encode_command(command)
        adapter.receive_line(line(response(command["id"], "get_state", data=IDLE)))
        self.assertFalse(adapter.busy)

    def test_state_overtaking_ack_retains_exact_late_failure_correlation_without_reopening(self):
        adapter = self.boot()
        command = self.failed_preflight(adapter).commands[0]
        adapter.encode_command(command)
        adapter.receive_line(line(response(command["id"], "get_state", data=IDLE)))
        self.assertFalse(adapter.busy)
        self.assertEqual(adapter.receive_line(line(response("failed-preflight", "prompt"))).events, [])
        late = self.result("failed-preflight", agentInvoked=False, status="error",
                           error={"message": "Preparation failed", "retryable": False})
        self.assertEqual(adapter.receive_line(line(late)).events, [])
        self.assertFalse(adapter.busy)
        self.assertTrue(adapter.can_input)
        with self.assertRaises(ProtocolError):
            adapter.receive_line(line(late))

    def test_busy_state_cannot_retire_failed_prompt_while_async_work_remains(self):
        adapter = self.boot()
        command = self.failed_preflight(adapter).commands[0]
        adapter.encode_command(command)
        events = adapter.receive_line(line(response(command["id"], "get_state", data={
            **IDLE, "isSettled": False, "hasPendingAsyncWork": True}))).events
        self.assertTrue(events[-1]["data"]["isStreaming"])
        self.assertTrue(adapter.busy)
        self.assertEqual(adapter.active_prompt_id, "failed-preflight")

    def test_quiet_failure_barrier_deduplicates_later_native_settlement_after_activity(self):
        adapter = self.boot()
        adapter.encode_command({"id": "failed-preflight", "type": "prompt", "message": "rejected input"})
        adapter.receive_line(line({"type": "agent_start"}))
        failure = adapter.receive_line(line(response("failed-preflight", "prompt", success=False, error="Preparation failed")))
        command = failure.commands[0]
        adapter.encode_command(command)
        adapter.receive_line(line(response(command["id"], "get_state", data=IDLE)))
        self.assertFalse(adapter.busy)
        self.assertEqual(adapter.receive_line(line({"type": "session_settled"})).events, [])

    def test_retired_error_cannot_swallow_unrelated_or_successful_turn_result(self):
        for result_id, status, invoked in (("unrelated", "error", False),
                                           ("failed-preflight", "completed", False),
                                           ("failed-preflight", "error", True)):
            adapter = self.boot()
            command = self.failed_preflight(adapter).commands[0]
            adapter.encode_command(command)
            adapter.receive_line(line(response(command["id"], "get_state", data=IDLE)))
            adapter.receive_line(line(response("failed-preflight", "prompt")))
            with self.subTest(result_id=result_id, status=status, invoked=invoked), self.assertRaises(ProtocolError):
                adapter.receive_line(line(self.result(result_id, status=status, agentInvoked=invoked,
                                                     error={"message": "failed", "retryable": False})))

    def test_duplicate_error_and_duplicate_late_ack_remain_protocol_errors(self):
        adapter = self.boot()
        self.failed_preflight(adapter)
        with self.assertRaises(ProtocolError):
            adapter.receive_line(line(response("failed-preflight", "prompt", success=False, error="Preparation failed")))
        adapter = self.boot()
        command = self.failed_preflight(adapter).commands[0]
        adapter.encode_command(command)
        adapter.receive_line(line(response(command["id"], "get_state", data=IDLE)))
        adapter.receive_line(line(response("failed-preflight", "prompt")))
        with self.assertRaises(ProtocolError):
            adapter.receive_line(line(response("failed-preflight", "prompt")))

    def test_local_slash_finishes_after_ack_without_fake_answer_or_double_settlement(self):
        adapter = self.boot()
        adapter.encode_command({"id": "local", "type": "prompt", "message": "/status"})
        output = adapter.receive_line(line({"type": "command_output", "text": "Native session: fixture"})).events
        self.assertEqual(output, [{"type": "launcher_command_output", "title": "Command output",
                                  "text": "Native session: fixture", "truncated": False}])
        self.assertTrue(adapter.busy)
        events = adapter.receive_line(line(response("local", "prompt", data={"agentInvoked": False}))).events
        self.assertEqual([event["type"] for event in events], ["response", "launcher_local_prompt_complete"])
        self.assertTrue(events[1]["sessionSettled"])
        self.assertFalse(adapter.busy)
        self.assertEqual(adapter.receive_line(line({"type": "session_settled"})).events, [])
        self.assertEqual(adapter.receive_line(line({"type": "session_settled"})).events, [])

    def test_local_command_during_background_work_does_not_claim_idle(self):
        adapter = self.boot()
        adapter.encode_command({"id": "state-bg", "type": "get_state"})
        adapter.receive_line(line(response("state-bg", "get_state", data={**IDLE, "isSettled": False, "hasPendingAsyncWork": True})))
        adapter.encode_command({"id": "local", "type": "prompt", "message": "/status"})
        events = adapter.receive_line(line(response("local", "prompt", data={"agentInvoked": False}))).events
        self.assertFalse(events[-1]["sessionSettled"])
        self.assertTrue(adapter.busy)
        self.assertEqual(adapter.receive_line(line({"type": "session_settled"})).events, [{"type": "agent_settled"}])

    def test_abort_and_prompt_async_local_result_completes_without_an_agent_turn(self):
        adapter = self.boot()
        self.prompt(adapter, "local-async", command="abort_and_prompt")
        events = adapter.receive_line(line(self.result("local-async", agentInvoked=False))).events
        self.assertEqual([event["type"] for event in events], ["launcher_prompt_result", "launcher_local_prompt_complete"])
        self.assertTrue(events[-1]["sessionSettled"])
        self.assertFalse(adapter.busy)
        self.assertEqual(adapter.receive_line(line({"type": "session_settled"})).events, [])

    def test_stale_agent_end_and_settlement_cannot_complete_new_pending_prompt(self):
        adapter = self.boot()
        adapter.encode_command({"id": "new", "type": "prompt", "message": "new task"})
        adapter.receive_line(line({"type": "agent_end", "messages": [], "yielded": True}))
        self.assertEqual(adapter.receive_line(line({"type": "session_settled"})).events, [])
        self.assertTrue(adapter.busy)
        adapter.receive_line(line(response("new", "prompt")))
        events = adapter.receive_line(line(self.result("new", agentInvoked=False, status="aborted"))).events
        self.assertEqual([event["type"] for event in events], ["launcher_prompt_result", "agent_settled"])
        self.assertFalse(adapter.busy)

    def test_new_agent_run_discards_old_deferred_settlement_proof(self):
        adapter = self.boot()
        adapter.encode_command({"id": "new", "type": "prompt", "message": "new task"})
        adapter.receive_line(line({"type": "session_settled"}))
        adapter.receive_line(line(response("new", "prompt")))
        adapter.receive_line(line({"type": "agent_start"}))
        events = adapter.receive_line(line(self.result("new", sessionSettled=False))).events
        self.assertEqual([event["type"] for event in events], ["launcher_prompt_result"])
        self.assertTrue(adapter.busy)

    def test_state_projects_pending_async_or_admission_as_busy_even_when_stream_false(self):
        adapter = self.boot()
        for index, data in enumerate(({**IDLE, "isSettled": False, "hasPendingAsyncWork": True},
                                      {**IDLE, "isSettled": False, "hasPendingAsyncWork": False})):
            identifier = f"state-{index}"
            adapter.encode_command({"id": identifier, "type": "get_state"})
            event = adapter.receive_line(line(response(identifier, "get_state", data=data))).events[-1]
            self.assertFalse(event["data"]["ompIsStreaming"])
            self.assertTrue(event["data"]["isStreaming"])
            self.assertTrue(adapter.busy)
        adapter.encode_command({"id": "state-final", "type": "get_state"})
        adapter.receive_line(line(response("state-final", "get_state", data=IDLE)))
        self.assertFalse(adapter.busy)

    def test_idle_state_cannot_race_unacknowledged_or_awaiting_result_prompt(self):
        adapter = self.boot()
        adapter.encode_command({"id": "new", "type": "prompt", "message": "new task"})
        for phase in ("unacknowledged", "accepted"):
            if phase == "accepted":
                adapter.receive_line(line(response("new", "prompt")))
            identifier = "state-" + phase
            adapter.encode_command({"id": identifier, "type": "get_state"})
            events = adapter.receive_line(line(response(identifier, "get_state", data=IDLE))).events
            self.assertTrue(events[-1]["data"]["isStreaming"])
            self.assertEqual(adapter.active_prompt_id, "new")

    def test_compaction_predicate_matches_source_and_normalizes_existing_semantic_event(self):
        adapter = self.boot()
        adapter.encode_command({"id": "compact-state", "type": "get_state"})
        # Native isRpcSessionSettled deliberately does not read isCompacting.
        adapter.receive_line(line(response("compact-state", "get_state", data={**IDLE, "isCompacting": True})))
        self.assertTrue(adapter.can_input)
        self.assertTrue(adapter.busy)
        self.assertEqual(adapter.receive_line(line({"type": "auto_compaction_start", "reason": "overflow", "action": "context-full"})).events[0]["type"], "compaction_start")
        self.assertEqual(adapter.receive_line(line({"type": "auto_compaction_end", "aborted": False, "willRetry": True})).events[0]["type"], "compaction_end")

    def test_command_catalog_projects_only_equivalent_display_fields(self):
        adapter = self.boot()
        command = json.loads(adapter.encode_command({"id": "catalog", "type": "get_commands"}))
        self.assertEqual(command["type"], "get_available_commands")
        native = {"name": "status", "source": "builtin", "description": "Status", "aliases": ["s"],
                  "input": {"hint": "filter"}, "subcommands": [{"name": "details"}]}
        event = adapter.receive_line(line(response("catalog", "get_available_commands", data={"commands": [native]}))).events[0]
        self.assertEqual(event["command"], "get_commands")
        self.assertEqual(event["data"]["commands"], [{"name": "status", "source": "builtin", "description": "Status"}])
        event = adapter.receive_line(line({"type": "available_commands_update", "commands": [native]})).events[0]
        self.assertEqual(event["command"], "get_commands")
        self.assertNotIn("sourceInfo", event["data"]["commands"][0])

    def test_history_uses_native_messages_instead_of_claiming_entry_schema_equivalence(self):
        adapter = self.boot()
        command = json.loads(adapter.encode_command({"id": "history", "type": "get_entries"}))
        self.assertEqual(command["type"], "get_messages")
        native = {"role": "user", "content": [{"type": "text", "text": "saved"}]}
        event = adapter.receive_line(line(response("history", "get_messages", data={"messages": [native]}))).events[0]
        self.assertEqual(event["command"], "get_messages")
        self.assertEqual(event["data"]["messages"], [native])

    def test_message_identity_and_delta_projection_keep_exact_text_and_no_mutation(self):
        adapter = self.boot()
        native = {"type": "message_start", "messageId": "msg-22", "message": {"role": "assistant", "content": []}}
        event = adapter.receive_line(line(native)).events[0]
        self.assertEqual(event["message"]["messageId"], "msg-22")
        self.assertNotIn("messageId", native["message"])
        for partial in ({"message": {"role": "assistant"}}, {}):
            update = {"type": "message_update", "messageId": "msg-22", "assistantMessageEvent": {
                "type": "thinking_delta", "contentIndex": 0, "delta": "thinking 雪 <script>literal</script>"}, **partial}
            event = adapter.receive_line(line(update)).events[0]
            self.assertEqual(event["assistantMessageEvent"], update["assistantMessageEvent"])
            self.assertNotIn("partial", event["assistantMessageEvent"])
        end = {"type": "message_end", "messageId": "msg-22", "message": {"role": "assistant", "content": []}}
        self.assertEqual(adapter.receive_line(line(end)).events[0]["message"]["messageId"], "msg-22")

    def test_native_queue_is_authoritative_and_unknown_side_channels_are_not_pi_events(self):
        adapter = self.boot()
        queue = {"type": "queue_update", "steering": ["Exact steer"], "followUp": ["Next"]}
        self.assertEqual(adapter.receive_line(line(queue)).events, [queue])
        self.assertTrue(adapter.busy)
        self.assertEqual(adapter.receive_line(line({"type": "subagent_event", "payload": {"type": "agent_end"}})).events, [])
        self.assertEqual(adapter.receive_line(line({"type": "live_end", "reason": "done"})).events, [])

    def test_command_output_is_utf8_bounded_and_never_an_assistant_answer(self):
        adapter = self.boot()
        event = adapter.receive_line(line({"type": "command_output", "text": "🙂" * 50000})).events[0]
        self.assertLessEqual(len(event["text"].encode("utf-8")), MAX_COMMAND_OUTPUT_BYTES)
        self.assertTrue(event["truncated"])
        self.assertEqual(event["type"], "launcher_command_output")

    def test_side_channel_answers_do_not_wait_for_nonexistent_rpc_responses(self):
        adapter = self.boot()
        for _ in range(MAX_PENDING_COMMANDS + 1):
            payload = adapter.encode_command({"type": "extension_ui_response", "id": "ui-native-1", "value": "Selected"})
            self.assertEqual(json.loads(payload)["id"], "ui-native-1")
        self.assertFalse(adapter.busy)

    def test_rejected_enqueue_discards_only_unsent_command_and_restores_idle(self):
        adapter = self.boot()
        adapter.encode_command({"id": "unsent", "type": "prompt", "message": "task"})
        self.assertTrue(adapter.busy)
        self.assertTrue(adapter.discard_command("unsent"))
        self.assertFalse(adapter.busy)
        self.assertEqual(adapter.active_prompt_id, "")
        self.prompt(adapter, "accepted")
        self.assertFalse(adapter.discard_command("accepted"))
        self.assertTrue(adapter.busy)

    def test_oversize_command_fails_before_registration_and_stdin_is_never_chunked(self):
        adapter = self.boot()
        for message in ("雪" * 30000, '"' * 40000):
            with self.assertRaises(ProtocolError):
                adapter.encode_command({"id": "too-large", "type": "prompt", "message": message})
            self.assertFalse(adapter.busy)
            self.assertFalse(adapter.discard_command("too-large"))
        payload = adapter.encode_command({"id": "too-large", "type": "prompt", "message": "line\n" * 1000})
        self.assertLessEqual(len(payload), 65536)
        self.assertEqual(payload.count(b"\n"), 1)
        self.assertEqual(json.loads(payload)["type"], "prompt")

    def test_pending_commands_are_bounded_and_bad_transport_invalidates_input(self):
        adapter = self.boot()
        for index in range(MAX_PENDING_COMMANDS):
            adapter.encode_command({"id": f"request-{index}", "type": "get_state"})
        with self.assertRaises(ProtocolError):
            adapter.encode_command({"id": "one-more", "type": "get_state"})
        self.assertTrue(adapter.can_input)
        with self.assertRaises(ProtocolError):
            adapter.receive_line(line({"type": "rpc_frame_error", "error": "Too large"}))
        self.assertFalse(adapter.can_input)
        with self.assertRaises(ProtocolError):
            adapter.encode_command({"id": "after-fatal", "type": "get_state"})


if __name__ == "__main__":
    unittest.main()
