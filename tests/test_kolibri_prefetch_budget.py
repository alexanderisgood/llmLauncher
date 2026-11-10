"""No-model bounds for unqualified async original-row prefetch experiments."""
from __future__ import annotations

import threading
import unittest

from bench.kolibri_prefetch_variant import PrefetchBudget


class PrefetchBoundsTests(unittest.TestCase):
    def test_running_and_completed_retained_results_share_one_hard_budget(self):
        budget = PrefetchBudget(max_outstanding=2,max_bytes=12,workers=1)
        self.addCleanup(budget.close)
        completed = budget.submit(lambda:b"original",cost=7)
        self.assertEqual(completed.result(timeout=2),b"original")
        # Completion does not free a buffer still retained for absorption.
        self.assertIsNone(budget.submit(lambda:b"extra",cost=6))
        second = budget.submit(lambda:b"bytes",cost=5)
        self.assertEqual(second.result(timeout=2),b"bytes")
        self.assertIsNone(budget.submit(lambda:b"extra",cost=1))
        self.assertEqual(budget.snapshot()["reservedBytes"],12)
        budget.release(completed,used=True); budget.release(second)
        stats = budget.snapshot()
        self.assertEqual(stats["reservedBytes"],0); self.assertEqual(stats["outstanding"],0)
        self.assertEqual(stats["peakReservedBytes"],12); self.assertEqual(stats["peakOutstanding"],2)

    def test_discarded_running_io_cannot_let_new_reads_escape_memory_cap(self):
        budget = PrefetchBudget(max_outstanding=1,max_bytes=10)
        entered,finish = threading.Event(),threading.Event()
        def read():
            entered.set(); finish.wait(5); return b"original"
        future = budget.submit(read,cost=10)
        try:
            self.assertTrue(entered.wait(2))
            budget.release(future)
            self.assertIsNone(budget.submit(lambda:b"extra",cost=1))
            self.assertEqual(budget.snapshot()["reservedBytes"],10)
            finish.set(); self.assertEqual(future.result(timeout=2),b"original")
        finally:
            finish.set(); budget.close()
        self.assertEqual(budget.snapshot()["reservedBytes"],0)
        self.assertEqual(budget.snapshot()["discarded"],1)

    def test_queued_unused_read_is_cancelled_and_releases_its_reservation(self):
        budget = PrefetchBudget(max_outstanding=2,max_bytes=20,workers=1)
        entered,finish = threading.Event(),threading.Event()
        def read():
            entered.set(); finish.wait(5); return b"original"
        first = budget.submit(read,cost=10)
        try:
            self.assertTrue(entered.wait(2))
            queued = budget.submit(lambda:b"queued",cost=10)
            budget.release(queued)
            self.assertTrue(queued.cancelled())
            self.assertEqual(budget.snapshot()["reservedBytes"],10)
            finish.set(); first.result(timeout=2); budget.release(first,used=True)
        finally:
            finish.set(); budget.close()
        self.assertEqual(budget.snapshot()["outstanding"],0)

    def test_reader_failure_can_be_discarded_and_retried_without_leaking_budget(self):
        budget = PrefetchBudget(max_outstanding=1,max_bytes=10)
        self.addCleanup(budget.close)
        def fail():
            raise IOError("short read")
        failed = budget.submit(fail,cost=8)
        with self.assertRaisesRegex(IOError,"short read"):
            failed.result(timeout=2)
        budget.release(failed)
        good = budget.submit(lambda:b"original",cost=10)
        self.assertEqual(good.result(timeout=2),b"original"); budget.release(good,used=True)
        self.assertEqual(budget.snapshot()["reservedBytes"],0)


if __name__ == "__main__":
    unittest.main()
