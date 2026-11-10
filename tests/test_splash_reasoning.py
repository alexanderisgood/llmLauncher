"""Speculative-mask and response-headroom regressions; no model needed."""
import types
import unittest

from splash_reasoning import ThinkingConstraint, THINK_END, EOS, ROW_BYTES, WORDS, thinking_budget, install_budget


def row(payload, index):
    return memoryview(payload).cast('I')[index * WORDS:(index + 1) * WORDS]


def allows(mask, token):
    return bool(mask[token // 32] & (1 << (token % 32)))


class FakeGrammar:
    def __init__(self):
        self.consumed = []

    def masks(self, simulation):
        # Real grammar restrictions survive the budget overlay.
        masks = bytearray(b'\xff' * (ROW_BYTES * (len(simulation) + 1)))
        words = memoryview(masks).cast('I')
        for r in range(len(simulation) + 1):
            words[r * WORDS] &= ~1  # token zero forbidden
        return bytes(masks)

    def consume(self, tokens):
        self.consumed.extend(tokens)


class QueuedGrammar(FakeGrammar):
    """The 1.2 frontend commits on its reader thread, then masks/finishes."""
    def __init__(self):
        super().__init__()
        self.pending = []

    def commit(self, tokens):
        self.pending.extend(tokens)

    def finish(self):
        self.consume(self.pending)
        self.pending = []

    def masks(self, simulation):
        self.finish()
        return super().masks(simulation)


class ThinkingBudgetTests(unittest.TestCase):
    def test_draft_crosses_boundary_without_committing_simulation(self):
        grammar = FakeGrammar()
        closed = []
        c = ThinkingConstraint(grammar, 11, closed.append)
        c.consume([41, 42])
        masks = c.masks([43, THINK_END, 44, 45])
        self.assertTrue(allows(row(masks, 0), 43))
        self.assertEqual(sum(w.bit_count() for w in row(masks, 1)), 1)
        self.assertTrue(allows(row(masks, 1), THINK_END))
        self.assertTrue(allows(row(masks, 2), 44))
        self.assertFalse(allows(row(masks, 2), 0), 'Do not bypass the tool grammar')
        self.assertEqual(c.tokens, 2)
        self.assertTrue(c.thinking, 'A proposed closing token has not been accepted')
        self.assertEqual(c.masks([43, THINK_END, 44, 45]), masks)
        c.consume([43, THINK_END, 44, 45])
        self.assertEqual(closed, [3])
        self.assertEqual(grammar.consumed, [41, 42, 43, THINK_END, 44, 45])
        self.assertFalse(c.thinking)
        self.assertEqual(c.masks([46]), grammar.masks([46]))

    def test_rejected_draft_cannot_exhaust_real_budget(self):
        c = ThinkingConstraint(FakeGrammar(), 11)
        c.masks([10, 11, 12, 13, 14, 15, 16, 17])
        c.consume([80])  # Only this replacement token was committed.
        self.assertEqual(c.tokens, 1)
        self.assertTrue(allows(row(c.masks([]), 0), 81))

    def test_natural_end_and_plain_text_output(self):
        c = ThinkingConstraint(None, 16)
        before = row(c.masks([]), 0)
        self.assertTrue(allows(before, THINK_END))
        self.assertTrue(allows(before, 100))
        self.assertTrue(all(not allows(before, token) for token in EOS))
        c.consume([100, THINK_END, 101])
        self.assertTrue(all(allows(row(c.masks([]), 0), token) for token in EOS))

    def test_zero_budget_forces_close_not_eos(self):
        c = ThinkingConstraint(None, 0)
        mask = row(c.masks([]), 0)
        self.assertEqual(sum(w.bit_count() for w in mask), 1)
        self.assertTrue(allows(mask, THINK_END))
        with self.assertRaises(ValueError):
            c.consume([100])

    def test_full_32k_boundary_leaves_answer_phase_open(self):
        c = ThinkingConstraint(FakeGrammar(), 32768)
        c.consume([100] * (32768 - 9))
        masks = c.masks([100, THINK_END, 101])
        self.assertTrue(allows(row(masks, 0), 100))
        self.assertEqual(sum(w.bit_count() for w in row(masks, 1)), 1)
        self.assertTrue(allows(row(masks, 1), THINK_END))
        c.consume([100, THINK_END, 101])
        self.assertEqual(c.tokens, 32760)
        self.assertFalse(c.thinking)
        self.assertTrue(allows(row(c.masks([]), 0), 102))

    def test_effort_and_output_reserve(self):
        self.assertEqual(thinking_budget('xhigh', 65536), 32768)
        self.assertEqual(thinking_budget('medium', 65536), 4096)
        self.assertEqual(thinking_budget('low', 65536), 1024)
        self.assertEqual(thinking_budget(None, 65536), 32768)
        self.assertEqual(thinking_budget('none', 65536), 0)
        for output in (1, 2, 256, 8192, 65536, 131072, 261120):
            self.assertLessEqual(thinking_budget('xhigh', output), output // 2)

    def test_modern_commits_are_counted_once_and_finish_checks_last_batch(self):
        grammar = QueuedGrammar()
        closed = []
        c = ThinkingConstraint(grammar, 11, closed.append)
        c.commit([41, 42])
        self.assertEqual(c.tokens, 0)
        masks = c.masks([43, THINK_END, 44])
        self.assertEqual(c.tokens, 2)
        self.assertTrue(allows(row(masks, 1), THINK_END))
        self.assertEqual(sum(w.bit_count() for w in row(masks, 1)), 1)
        self.assertEqual(c.masks([43, THINK_END, 44]), masks)
        c.commit([43, THINK_END, 44])
        c.finish()
        self.assertEqual(closed, [3])
        self.assertEqual(grammar.consumed, [41, 42, 43, THINK_END, 44])
        self.assertFalse(c.thinking)
        c.finish()
        self.assertEqual(closed, [3])

    def test_modern_finish_rejects_output_past_budget(self):
        c = ThinkingConstraint(None, 0)
        c.commit([100])
        with self.assertRaisesRegex(ValueError, 'past the enforced thinking budget'):
            c.finish()

    def test_modern_frontend_job_keeps_tools_and_budget(self):
        tools = object()
        grammar = QueuedGrammar()
        class Frontend:
            def _prepare(self, body, *args, **kwargs):
                return types.SimpleNamespace(max_new_tokens=body['max_tokens'], constraint=grammar,
                                             thinking=body.get('reasoning_effort') != 'none', tool_policy=tools)
        install_budget(Frontend)
        job = Frontend()._prepare({'reasoning_effort':'medium', 'max_tokens':8192})
        self.assertIs(job.tool_policy, tools)
        self.assertIs(job.constraint.inner, grammar)
        self.assertEqual(job.constraint.budget, 4096)
        off = Frontend()._prepare({'reasoning_effort':'none', 'max_tokens':8192})
        self.assertIs(off.constraint, grammar)

    def test_adapter_per_request_budget_no_global_state_or_request_rewrite(self):
        class Frontend:
            def _prepare(self, body, *args, **kwargs):
                thinking = body.get('reasoning_effort') != 'none'
                return types.SimpleNamespace(max_new_tokens=body['max_tokens'], constraint=None), thinking, False
        install_budget(Frontend)
        f = Frontend()
        body = {'reasoning_effort':'xhigh', 'max_tokens':65536, 'thinking_budget_tokens':32}
        a, _, _ = f._prepare(body)
        b, _, _ = f._prepare({**body, 'thinking_budget_tokens':99999})
        off, _, _ = f._prepare({**body, 'reasoning_effort':'none'})
        self.assertEqual(a.constraint.budget, 32)
        self.assertEqual(b.constraint.budget, 32768)
        self.assertEqual(a.max_new_tokens, 65536)
        self.assertEqual(body['thinking_budget_tokens'], 32)
        self.assertIsNone(off.constraint)
        a.constraint.consume([15])
        self.assertEqual(b.constraint.tokens, 0)
        for invalid in (-1, True, '32'):
            with self.assertRaises(ValueError):
                f._prepare({**body, 'thinking_budget_tokens':invalid})


if __name__ == '__main__':
    unittest.main()
