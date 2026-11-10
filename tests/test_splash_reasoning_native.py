"""Opt-in real tokenizer/llguidance tests under Splash's Python, without GPU.

LLM_LAUNCHER_SPLASH_NATIVE=1 /opt/homebrew/opt/splash/libexec/python/bin/python3 -m unittest discover -s tests -p test_splash_reasoning_native.py
"""
import os
from pathlib import Path
import sys
import unittest

from splash_reasoning import ThinkingConstraint, THINK_END, WORDS, CLOSURE_RESERVE, verify_frontend


@unittest.skipUnless(os.environ.get('LLM_LAUNCHER_SPLASH_NATIVE'), 'Opt-in installed Splash tokenizer/grammar')
class NativeThinkingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        native = Path(os.environ.get('LLM_LAUNCHER_SPLASH_LIBEXEC', '/opt/homebrew/opt/splash/libexec')) / 'server'
        verify_frontend(native)
        cls.modern = (native / '__init__.py').is_file()
        if cls.modern:
            sys.path.insert(0, str(native.parent))
            from server.constraints import ConstraintFactory
            from server import tool_schema
        else:
            sys.path.insert(0, str(native))
            from constraints import ConstraintFactory
            import tool_schema
        from transformers import AutoTokenizer
        cls.schema = tool_schema
        cls.tokenizer = AutoTokenizer.from_pretrained(
            str(Path.home() / 'Library/Application Support/Splash/models/incoai/Qwen3.8-27B-Splash/tokenizer'),
            local_files_only=True)
        cls.factory = ConstraintFactory(cls.tokenizer)

    def encode(self, text):
        return self.tokenizer.encode(text, add_special_tokens=False)

    def force(self, grammar, text='Reconsider the precision limits once again.'):
        tokens = self.encode(text)
        c = ThinkingConstraint(self.factory.create(grammar), len(tokens) + CLOSURE_RESERVE)
        c.consume(tokens)
        mask = memoryview(c.masks([])).cast('I')
        self.assertEqual(sum(w.bit_count() for w in mask), 1)
        self.assertTrue(mask[THINK_END // 32] & (1 << (THINK_END % 32)))
        c.consume([THINK_END])
        return c

    def test_json_after_forced_close(self):
        grammar = self.schema.json_grammar({'type':'object', 'properties':{'answer':{'type':'integer'}},
                                          'required':['answer'], 'additionalProperties':False}, True)
        c = self.force(grammar)
        c.consume(self.encode('{"answer":7}'))
        c.finish()
        self.assertTrue(c.inner.matcher.is_accepting())

    def test_required_tool_grammar_survives_close(self):
        policy = self.schema.ToolPolicy(**({'strict':frozenset({'read'}),'constrained':True} if self.modern else {'validators':{}}), schemas={'read':{
            'type':'object','properties':{'path':{'type':'string'}},'required':['path']}},
            required=True, parallel=False)
        c = self.force(self.schema.tool_grammar(policy, True))
        c.consume(self.encode('<tool_call>\n<function=read>\n<parameter=path>\nfractal.js\n</parameter>\n</function>\n</tool_call>'))
        c.finish()
        self.assertTrue(c.inner.matcher.is_accepting())

    def test_speculative_close_does_not_commit_matcher(self):
        grammar = self.schema.json_grammar({'type':'object'}, True)
        token = self.encode(' a')[0]
        c = ThinkingConstraint(self.factory.create(grammar), 3 + CLOSURE_RESERVE)
        c.consume([token])
        simulation = [token, token, THINK_END, *self.encode('{}')]
        first = c.masks(simulation)
        self.assertEqual(first, c.masks(simulation))
        mask = memoryview(first).cast('I')[2*WORDS:3*WORDS]
        self.assertEqual(sum(w.bit_count() for w in mask), 1)
        c.consume(simulation)
        c.finish()
        self.assertTrue(c.inner.matcher.is_accepting())

    def test_unicode_budget_boundaries(self):
        grammar = self.schema.json_grammar({'type':'object'}, True)
        tokens = self.encode('精度を確かめる 🌊🧪')
        for boundary in range(1, len(tokens) + 1):
            with self.subTest(boundary=boundary):
                c = ThinkingConstraint(self.factory.create(grammar), boundary + CLOSURE_RESERVE)
                c.consume(tokens[:boundary])
                remaining = iter(tokens[boundary:])
                while True:
                    mask = memoryview(c.masks([])).cast('I')
                    if mask[THINK_END // 32] & (1 << (THINK_END % 32)):
                        self.assertEqual(sum(w.bit_count() for w in mask), 1)
                        break
                    c.consume([next(remaining)])
                self.assertLessEqual(c.tokens, c.budget)
                c.consume([THINK_END])
                c.consume(self.encode('{}'))
                c.finish()


if __name__ == '__main__':
    unittest.main()
