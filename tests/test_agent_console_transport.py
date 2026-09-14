"""Exercise real PTY backpressure without loading a model or running user tools."""
import os
import pty
import threading
import time
import tty
import unittest
from unittest.mock import Mock

import launcher
from agent_console_transport import ConsoleTransport


class ConsoleBackpressureTests(unittest.TestCase):
    def test_large_commands_arrive_intact_in_order_under_duplex_pressure(self):
        master, slave = pty.openpty()
        tty.setraw(slave)
        transport = ConsoleTransport(master)
        expected = ("first:" + "🙂" * 15000 + "\nsecond:" + "z" * 60000 + "\n").encode()
        received = bytearray()
        output = bytearray()
        errors = []

        def child():
            try:
                while len(received) < len(expected):
                    part = os.read(slave, 512)
                    if not part:
                        break
                    received.extend(part)
                    os.write(slave, b"progress\n")
            except OSError as error:
                errors.append(error)

        def pump():
            try:
                while value := transport.read():
                    output.extend(value)
            except OSError:
                pass

        worker = threading.Thread(target=child, daemon=True)
        reader = threading.Thread(target=pump, daemon=True)
        try:
            for command in expected.splitlines(keepends=True):
                transport.send(command)
            worker.start()
            reader.start()
            worker.join(timeout=5)
            self.assertFalse(worker.is_alive(), "Duplex transfer jammed")
            self.assertEqual(errors, [])
            self.assertEqual(bytes(received), expected)
            self.assertIn(b"progress", output)
        finally:
            transport.close()
            os.close(slave)
            worker.join(timeout=1)
            reader.join(timeout=1)
            self.assertFalse(reader.is_alive())

    def test_queue_is_bounded_and_redundant_state_probes_are_coalesced(self):
        master, slave = pty.openpty()
        tty.setraw(slave)
        transport = ConsoleTransport(master, max_pending_bytes=12, max_pending_messages=2)
        try:
            transport.send(b"state\n", coalesce_key="state")
            for _ in range(1000):
                transport.send(b"state\n", coalesce_key="state")
            transport.send(b"hello\n")
            with self.assertRaisesRegex(ValueError, "buffer is full"):
                transport.send(b"extra\n")
            os.write(slave, b"ready")
            self.assertEqual(transport.read(), b"ready")
            os.write(slave, b"next")
            self.assertEqual(transport.read(), b"next")
            self.assertEqual(os.read(slave, 100), b"state\nhello\n")
        finally:
            transport.close()
            os.close(slave)

    def test_close_wakes_idle_reader_and_rejects_new_input(self):
        master, slave = pty.openpty()
        transport = ConsoleTransport(master)
        result = []
        reader = threading.Thread(target=lambda: result.append(transport.read()), daemon=True)
        try:
            reader.start()
            transport.close()
            reader.join(timeout=1)
            self.assertFalse(reader.is_alive())
            self.assertEqual(result, [b""])
            with self.assertRaisesRegex(ValueError, "no longer accepting"):
                transport.send(b"late input")
            transport.close()
        finally:
            transport.close()
            os.close(slave)

    def test_full_input_does_not_block_output_or_console_state(self):
        master, slave = pty.openpty()
        tty.setraw(slave)
        os.set_blocking(master, False)
        try:
            while True:
                os.write(master, b"x" * 4096)
        except BlockingIOError:
            pass
        os.set_blocking(master, True)
        process = Mock()
        process.poll.return_value = None
        process.wait.return_value = 0
        console = launcher.AgentConsole(
            owner_run_id="pressure", plan=Mock(run_id="pressure"), process=process,
            master_fd=master, cols=100, rows=30,
        )
        manager = launcher.RunManager()
        sent = threading.Event()
        errors = []

        def send():
            try:
                manager._write_pi_rpc_command(console, {"type": "get_state"})
            except Exception as error:
                errors.append(error)
            finally:
                sent.set()

        writer = threading.Thread(target=send, daemon=True)
        reader = threading.Thread(target=manager._read_agent_console, args=(console,), daemon=True)
        try:
            writer.start()
            self.assertTrue(sent.wait(0.5), "A full Pi input buffer blocked the sender")
            self.assertEqual(errors, [])
            self.assertTrue(console.lock.acquire(timeout=0.5), "Status is locked behind input")
            console.lock.release()
            reader.start()
            os.write(slave, b"still producing output")
            deadline = time.monotonic() + 2
            while b"still producing output" not in console.output and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertIn(b"still producing output", console.output)
        finally:
            os.close(slave)
            writer.join(timeout=2)
            manager._close_agent_console_fd(console)
            if reader.ident is not None:
                reader.join(timeout=2)
                self.assertFalse(reader.is_alive(), "Closing the console did not release its reader")


if __name__ == "__main__":
    unittest.main()
