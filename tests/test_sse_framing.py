import random
import unittest

from sse_framing import EventScanner, pop_event


class SSEFramingTests(unittest.TestCase):
    def test_incremental_scan_matches_full_scan_for_fragmented_streams(self):
        rng = random.Random(93)
        wires = [b"a\n\nb\r\n\r\nc\n\n", b"\r\n\r\n\n\n", b"unfinished\r\n",
                 b"data: {\"text\":\"\xf0\x9f\xa6\x99\"}\r\n\r\n"]
        wires += [bytes(rng.choices(b"abc\r\n", k=1000)) for _ in range(20)]
        for wire in wires:
            for size in (1, 2, 3, 7, 64, 5000):
                scanner = EventScanner()
                pending, reference = bytearray(), bytearray()
                for start in range(0, len(wire), size):
                    pending.extend(wire[start:start + size])
                    reference.extend(wire[start:start + size])
                    while True:
                        result = scanner.pop(pending)
                        self.assertEqual(result, pop_event(reference))
                        self.assertEqual(pending, reference)
                        if result is None:
                            break

    def test_forwarding_and_reset_keep_split_separators(self):
        for separator in (b"\n\n", b"\r\n\r\n"):
            for split in range(1, len(separator)):
                scanner = EventScanner()
                prefix = b"x" * 100 + separator[:split]
                pending = bytearray(prefix)
                self.assertIsNone(scanner.pop(pending))
                forwarded = scanner.forward_prefix(pending)
                pending.extend(separator[split:] + b"next\n\n")
                self.assertEqual(forwarded + scanner.pop(pending), b"x" * 100 + separator)
                self.assertEqual(scanner.pop(pending), b"next\n\n")
                pending.extend(b"another unfinished event")
                self.assertIsNone(scanner.pop(pending))
                pending.clear()
                scanner.reset()
                pending.extend(b"new\n\n")
                self.assertEqual(scanner.pop(pending), b"new\n\n")

    def test_search_work_is_linear_for_a_large_fragmented_event(self):
        class MeasuredBuffer(bytearray):
            scanned = 0

            def find(self, needle, start=0):
                self.scanned += len(self) - start
                return super().find(needle, start)

        pending = MeasuredBuffer()
        scanner = EventScanner()
        for _ in range(200):
            pending.extend(b"x" * 4096)
            self.assertIsNone(scanner.pop(pending))
        for byte in b"\r\n\r\n":
            pending.append(byte)
            result = scanner.pop(pending)
        self.assertEqual(len(result), 200 * 4096 + 4)
        self.assertLess(pending.scanned, 3 * len(result),
                        "Each append must search only new bytes and the separator overlap")


if __name__ == "__main__":
    unittest.main()
