"""Opt-in CPU-only validation against the installed, SHA-pinned Uzu tokenizer.

Run with a Python containing tokenizers and LLM_LAUNCHER_UZU_TOKENIZER_INTEGRATION=1.
No model tensors, GPU libraries, network requests, or model processes are used.
"""
import hashlib
import os
import unittest

import launcher


@unittest.skipUnless(
    os.environ.get("LLM_LAUNCHER_UZU_TOKENIZER_INTEGRATION") == "1",
    "opt-in installed Uzu tokenizer check",
)
class UzuTokenizerIntegrationTests(unittest.TestCase):
    def test_fixed_corpus_fits_all_context_tiers_with_real_tokenizer(self):
        from tokenizers import Tokenizer

        path = (
            launcher.UZU_MODEL_CACHE_ROOT
            / launcher.UZU_MODEL_REGISTRY_ID.replace(":", "-")
            / launcher.UZU_MODEL_TOOLCHAIN_VERSION / "tokenizer.json"
        )
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest(),
            launcher.UZU_MODEL_FILE_SHA256["tokenizer.json"],
        )
        tokenizer = Tokenizer.from_file(str(path))
        for count in (128, 8_000, 49_152, 122_880):
            text = launcher.uzu_qualification_words(count, 183_211)
            actual = len(tokenizer.encode(" " + text, add_special_tokens=False).ids)
            self.assertLessEqual(actual, count)
            self.assertGreaterEqual(actual, count - 1)
        for suite in launcher.BENCHMARK_SUITES.values():
            if not suite.get("uzuTokenBudgetedCorpus"):
                continue
            for case in launcher.benchmark_agentic_cases(suite, require_complete_answer=True):
                # Content-only count, plus a conservative framing allowance.
                # Native authoritative rendered-chat usage remains required by
                # qualification; this test does not substitute for that proof.
                content_tokens = sum(
                    len(tokenizer.encode(m["content"], add_special_tokens=False).ids)
                    for m in case["messages"]
                )
                with self.subTest(tier=suite["requiredContext"], case=case["scenario"]):
                    self.assertLessEqual(abs(content_tokens - case["targetPromptTokens"]), 512)
                    # Templates seed the conversation; only the adaptive cases
                    # below are sent, with their own output allowance.
                    if suite["requiredContext"] >= 65536 and case["scenario"] in {"toolIngest", "steadyTurn"}:
                        self.assertGreaterEqual(content_tokens, int(suite["requiredContext"] * .9))

            history, previous = [], None
            for template in launcher.benchmark_agentic_cases(suite, require_complete_answer=True):
                case = launcher.uzu_conversation_case(
                    template, history, previous, suite["requiredContext"],
                    launcher.UZU_QUALIFICATION_SAMPLE_MAX_TOKENS,
                )
                content_tokens = sum(
                    len(tokenizer.encode(m.get(key, ""), add_special_tokens=False).ids)
                    for m in case["messages"] for key in ("content", "reasoning_content")
                )
                # Approximate framing is only a CPU preflight; authoritative
                # rendered usage still gates the actual run and saved receipt.
                framed_tokens = content_tokens + 12 * len(case["messages"])
                with self.subTest(conversation=suite["requiredContext"], case=case["scenario"]):
                    self.assertLessEqual(abs(framed_tokens - case["targetPromptTokens"]), 512)
                    self.assertGreaterEqual(case["maxTokens"], launcher.UZU_QUALIFICATION_SAMPLE_MIN_TOKENS)
                    self.assertLess(framed_tokens + case["maxTokens"], suite["requiredContext"])
                    if suite["requiredContext"] >= 65536 and case["scenario"] in {"toolIngest", "steadyTurn"}:
                        self.assertGreaterEqual(framed_tokens, int(suite["requiredContext"] * .9))
                reply = {"role": "assistant", "content": " result" * 128,
                         "reasoning_content": " reason" * 384}
                history = [*case["messages"], reply]
                previous = {"promptTokens": framed_tokens, "completionTokens": 512}


if __name__ == "__main__":
    unittest.main()
