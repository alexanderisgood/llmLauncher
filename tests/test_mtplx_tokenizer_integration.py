"""Opt-in, CPU-only check against the installed MTPLX Qwen tokenizer.

Use its existing Python environment and set
LLM_LAUNCHER_MTPLX_TOKENIZER_INTEGRATION to the tokenizer.json path.
No weights, GPU libraries, downloads, or model server are used.
"""
import copy
import hashlib
import os
from pathlib import Path
import unittest

import launcher


@unittest.skipUnless(
    os.environ.get("LLM_LAUNCHER_MTPLX_TOKENIZER_INTEGRATION"),
    "opt-in installed MTPLX tokenizer check",
)
class MTPLXTokenizerIntegrationTests(unittest.TestCase):
    def test_near_64k_cases_fit_and_old_word_count_reproduces_overflow(self):
        from tokenizers import Tokenizer

        path = Path(os.environ["LLM_LAUNCHER_MTPLX_TOKENIZER_INTEGRATION"])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         "06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523")
        tokenizer = Tokenizer.from_file(str(path))
        suite = launcher.BENCHMARK_SUITES[launcher.MTPLX_LONG_CONTEXT_64K_SUITE]
        def count(case):
            return sum(len(tokenizer.encode(m["content"], add_special_tokens=False).ids)
                       for m in case["messages"])

        for size in (128, 49152, 61440):
            text = launcher.qwen_token_budgeted_words(size, 183211)
            self.assertLessEqual(len(tokenizer.encode(" " + text, add_special_tokens=False).ids), size)
            self.assertEqual(text, launcher.uzu_qualification_words(size, 183211))
        for case in launcher.benchmark_agentic_cases(suite):
            with self.subTest(case=case["scenario"]):
                tokens = count(case)
                self.assertLessEqual(abs(tokens - case["targetPromptTokens"]), 512)
                # Allow 512 additional tokens for runtime chat-template framing;
                # actual server usage still gates the saved qualification.
                self.assertLess(tokens + 512 + suite["maxTokens"], suite["requiredContext"])
                if case["scenario"] in {"toolIngest", "steadyTurn"}:
                    self.assertGreaterEqual(tokens, launcher.MTPLX_LONG_CONTEXT_MINIMUM_PROMPT)
        old = copy.deepcopy(suite)
        old.pop("qwenTokenBudgetedCorpus")
        oversized = launcher.benchmark_agentic_cases(old)[2]
        self.assertGreater(count(oversized), suite["requiredContext"])


if __name__ == "__main__":
    unittest.main()
