"""No weights/GPU: exercise the actual upstream processor's transaction state."""
import ast
import asyncio
import copy
import hashlib
import json
from contextlib import aclosing
from pathlib import Path
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from dflash_thinking_budget import DFlashThinkingBudget, _token_piece_reader, create_budget, install_dflash_thinking_budget

ROOT = Path(__file__).resolve().parents[1]
NATIVE = (Path.home() / 'Library/Application Support/LLM Launcher/runtimes/omlx-0.6.4'
          / 'lib/python3.11/site-packages')


class Rows:
    """Tiny scalar logits fixture, only the operations used by this processor."""
    def __init__(self, rows, rank=3):
        self.rows = copy.deepcopy(rows)
        self.rank = rank
        self.shape = (1, len(rows), len(rows[0])) if rank == 3 else (1, len(rows[0]))
    def __getitem__(self, item):
        return Rows(self.rows[item[1]], self.rank)
    def __setitem__(self, item, value):
        for row in self.rows:
            row[item[-1]] = value
    def choices(self):
        return [max(range(len(row)), key=row.__getitem__) for row in self.rows]


def logits(rows=1, preferred=3):
    data = [[-10.0] * 100 for _ in range(rows)]
    for row in data:
        row[preferred] = 1.0
    return Rows(data)


def native_processor_class():
    path = NATIVE / 'omlx/api/thinking.py'
    tree = ast.parse(path.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ThinkingBudgetProcessor')
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), cls], type_ignores=[])
    namespace = {}
    exec(compile(ast.fix_missing_locations(module), str(path), 'exec'), namespace)
    return namespace['ThinkingBudgetProcessor']


@unittest.skipUnless((NATIVE / 'omlx/api/thinking.py').is_file(), 'audited oMLX processor required')
class BudgetTransactions(unittest.TestCase):
    def setUp(self):
        mx = ModuleType('mlx.core')
        mx.full = lambda shape, value: Rows([[value] * shape[-1] for _ in range(shape[-2] if len(shape) == 3 else 1)], len(shape))
        mx.concatenate = lambda arrays, axis: Rows([row for array in arrays for row in array.rows])
        self.modules = patch.dict('sys.modules', {'mlx': ModuleType('mlx'), 'mlx.core': mx})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.Processor = native_processor_class()

    def processor(self, budget, **kwargs):
        return self.Processor([90], budget, think_start_token_id=99,
                              leading_token_ids=[1], trailing_token_ids=[2], **kwargs)

    def test_speculative_commits_equal_ar_across_every_budget_boundary(self):
        prompt = [45, 99, 1]
        for budget in (1, 2, 4, 5, 8):
            for draft in (3, 77, 90):
                with self.subTest(budget=budget, draft=draft):
                    reference = self.processor(budget)
                    expected = []
                    for _ in range(15):
                        expected.append(reference(prompt + expected, logits()).choices()[0])
                    adapter = DFlashThinkingBudget(self.processor(budget), prompt)
                    staged = adapter.process_first_logits(logits()).choices()[0]
                    committed = []
                    while len(committed) < 15:
                        candidates = [staged, draft, draft, draft][:min(4, 15-len(committed))]
                        decisions = adapter.process_block(logits(len(candidates)), committed, candidates).choices()
                        accepted = 0
                        for proposal, decision in zip(candidates[1:], decisions):
                            if proposal != decision:
                                break
                            accepted += 1
                        adapter.commit(accepted)
                        committed.extend(candidates[:1+accepted])
                        staged = decisions[accepted]
                    self.assertEqual(committed, expected)
                    self.assertEqual(adapter.history, prompt + committed)

    def test_rejected_natural_close_does_not_disable_budget(self):
        adapter = DFlashThinkingBudget(self.processor(4), [99])
        adapter.process_first_logits(logits())
        adapter.process_block(logits(4), [], [3, 90, 77, 77])
        self.assertTrue(adapter.processor._done)
        adapter.commit(0)
        self.assertFalse(adapter.processor._done)
        self.assertEqual(adapter.processor._thinking_tokens, 2)
        rows = adapter.process_block(logits(2), [3], [3, 3]).choices()
        self.assertEqual(rows, [3, 1])

    def test_unchanged_logits_keep_identity_before_and_after_natural_close(self):
        adapter = DFlashThinkingBudget(self.processor(100), [99])
        first = logits()
        self.assertIs(adapter.process_first_logits(first), first)
        block = logits(3)
        self.assertIs(adapter.process_block(block, [], [3, 90, 3]), block)
        adapter.commit(2)
        after = logits(2)
        self.assertIs(adapter.process_block(after, [3, 90, 3], [3, 3]), after)

    def test_factory_uses_executor_tokenizer_and_only_current_open_think(self):
        class Tokenizer:
            def encode(self, text, **kwargs):
                return {'<think>':[99], '</think>':[90], '\n':[1], '\n\n':[2]}[text]
            def convert_ids_to_tokens(self, token):
                return 'x'
        engine = SimpleNamespace(_executor_tokenizer=Tokenizer(), _tokenizer_obj=object(),
                                 _output_parser_factory=None)
        native_module = ModuleType('omlx.api.thinking')
        native_module.ThinkingBudgetProcessor = self.Processor
        with patch.dict('sys.modules', {'omlx.api.thinking':native_module}):
            adapter = create_budget(engine, 4, [99, 1])
            self.assertIsInstance(adapter, DFlashThinkingBudget)
            self.assertEqual(adapter.processor._thinking_tokens, 0)
            self.assertIsNone(create_budget(engine, 4, [99, 90, 2]))
            self.assertIsNone(create_budget(engine, 4, [99, 1, 3, 4, 5]))

    def test_fast_bytelevel_tokenizer_uses_installed_mlx_byte_mapping(self):
        path = NATIVE / 'mlx_lm/tokenizer_utils.py'
        tree = ast.parse(path.read_text())
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == 'BPEStreamingDetokenizer')
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'make_byte_decoder')
        namespace = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), str(path), 'exec'), namespace)
        detokenizer = type('BPEStreamingDetokenizer', (), {
            '_byte_decoder':None, 'make_byte_decoder':namespace['make_byte_decoder']})
        module = ModuleType('mlx_lm.tokenizer_utils')
        module.BPEStreamingDetokenizer = detokenizer
        tokenizer = SimpleNamespace(
            backend_tokenizer=SimpleNamespace(decoder=SimpleNamespace(
                __getstate__=lambda: b'{"type":"ByteLevel"}')),
            convert_ids_to_tokens=lambda token: {10:'\u00e2', 11:'\u0124', 12:'\u00ac', 90:'</think>'}[token])
        with patch.dict('sys.modules', {'mlx_lm.tokenizer_utils':module}):
            read = _token_piece_reader(tokenizer)
        self.assertEqual(read(10)+read(11)+read(12), '€'.encode())

    def test_natural_close_and_cached_prompt_reasoning_do_not_reconsume_budget(self):
        # Cached/historical reasoning is all prompt; only new output is counted.
        prompt = [99] + [3] * 10000 + [90, 45, 99, 1]
        adapter = DFlashThinkingBudget(self.processor(6), prompt)
        adapter.process_first_logits(logits())
        rows = adapter.process_block(logits(3), [], [90, 3, 3]).choices()
        adapter.commit(2)
        self.assertEqual(rows, [3, 3, 3])
        self.assertTrue(adapter.processor._done)
        fresh = DFlashThinkingBudget(self.processor(6), prompt)
        fresh.process_first_logits(logits())
        self.assertEqual(fresh.processor._thinking_tokens, 1)

    def test_utf8_boundary_is_preserved_across_rejected_branch(self):
        pieces = {10: b'\xe2', 11: b'\x82', 12: b'\xac'}
        adapter = DFlashThinkingBudget(self.processor(2, token_to_piece=lambda t: pieces.get(t, 'x')), [99])
        adapter.process_first_logits(logits())
        rows = adapter.process_block(logits(4), [], [10, 11, 12, 3]).choices()
        self.assertEqual(rows[:3], [3, 3, 1])
        adapter.commit(0)
        self.assertEqual(adapter.processor._pending_utf8, b'\xe2')
        rows = adapter.process_block(logits(2), [10], [11, 12]).choices()
        self.assertEqual(rows, [3, 1])

    def test_inner_ar_fallback_matches_original_processor(self):
        prompt = [99]
        adapter = DFlashThinkingBudget(self.processor(4), prompt)
        reference = self.processor(4)
        generated = [adapter.process_first_logits(logits()).choices()[0]]
        expected = [reference(prompt, logits()).choices()[0]]
        for _ in range(10):
            generated.append(adapter.process_next_logits(logits(), generated).choices()[0])
            expected.append(reference(prompt + expected, logits()).choices()[0])
        self.assertEqual(generated, expected)

    def test_invalid_transaction_fails_instead_of_drifting_budget(self):
        adapter = DFlashThinkingBudget(self.processor(4), [99])
        adapter.process_first_logits(logits())
        with self.assertRaisesRegex(RuntimeError, 'repeated'):
            adapter.process_first_logits(logits())
        with self.assertRaisesRegex(RuntimeError, 'committed tokens'):
            adapter.process_block(logits(), [55], [3])
        adapter.process_block(logits(), [], [3])
        with self.assertRaisesRegex(RuntimeError, 'out of order'):
            adapter.process_block(logits(), [], [3])
        with self.assertRaisesRegex(RuntimeError, 'acceptance row'):
            adapter.commit(1)


class RequestOwnership(unittest.IsolatedAsyncioTestCase):
    async def test_budget_is_request_local_and_generator_close_drains_native(self):
        seen, closed = [], []
        class Engine:
            def _stream_dflash_events(self, *, logits_processor_factory=None): pass
            async def generate(self, **kwargs):
                return kwargs
            async def stream_generate(self, **kwargs):
                seen.append(kwargs)
                try:
                    yield 1
                    yield 2
                finally:
                    closed.append(kwargs)
        install_dflash_thinking_budget(Engine)
        installed = Engine.generate
        install_dflash_thinking_budget(Engine)
        self.assertIs(Engine.generate, installed)
        engine = Engine()
        first, second = await asyncio.gather(engine.generate(thinking_budget=4), engine.generate(thinking_budget=9))
        self.assertEqual(first['logits_processor_factory'].args[1], 4)
        self.assertEqual(second['logits_processor_factory'].args[1], 9)
        self.assertNotIn('logits_processor_factory', await engine.generate())
        stream = engine.stream_generate(thinking_budget=7)
        self.assertEqual(await anext(stream), 1)
        await stream.aclose()
        self.assertEqual(closed, seen)
        for budget in (False, 0, -1, '4'):
            with self.assertRaises(ValueError):
                await engine.generate(thinking_budget=budget)

    async def test_missing_native_patch_fails_before_wrapping(self):
        class Engine:
            def _stream_dflash_events(self): pass
        with self.assertRaisesRegex(RuntimeError, 'runtime patch is missing'):
            install_dflash_thinking_budget(Engine)


class PatchReceipt(unittest.TestCase):
    def test_patch_receipt_matches_audited_native_sources(self):
        folder = ROOT / 'runtime_patches/omlx/0.6.4'
        manifest = json.loads((folder / 'dflash-thinking-budget.json').read_text())
        data = (folder / manifest['patch']).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), manifest['patchSha256'])
        for path, hashes in manifest['files'].items():
            installed = NATIVE / path
            if not installed.is_file():
                continue
            contents = installed.read_bytes()
            self.assertIn(hashlib.sha256(contents).hexdigest(), hashes.values())


@unittest.skipUnless((NATIVE / 'omlx/engine/dflash.py').is_file(), 'audited oMLX source required')
class NativePlumbing(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        import dflash_budget_patch
        cls.folder = tempfile.TemporaryDirectory(prefix='dflash-budget-test-')
        cls.addClassCleanup(cls.folder.cleanup)
        root = Path(cls.folder.name)
        site = root / 'lib/python3.11/site-packages'
        manifest = json.loads(dflash_budget_patch.MANIFEST.read_text())
        for relative in manifest['files']:
            target = site / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((NATIVE / relative).read_bytes())
        dflash_budget_patch.apply(root)
        cls.site = site

    def method(self, path, cls_name, method_name):
        tree = ast.parse((self.site / path).read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls_name)
        return copy.deepcopy(next(n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                                  and n.name == method_name))

    def load(self, methods, namespace):
        tree = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0),
                               *methods], type_ignores=[])
        exec(compile(ast.fix_missing_locations(tree), 'audited-native-dflash-fixture', 'exec'), namespace)
        return namespace

    async def test_native_chat_fallback_is_explicit_and_normal_close_reaches_sampler(self):
        names = ('chat', 'stream_chat')
        methods = [self.method('omlx/engine/dflash.py', 'DFlashEngine', name) for name in names]
        ns = self.load(methods, {'aclosing':aclosing})
        closed = []
        async def stream_generate(self, **kwargs):
            try:
                yield 'first'
                yield 'second'
            finally:
                closed.append(True)
        Engine = type('Engine', (), {name:ns[name] for name in names} | {
            '_loaded':True, '_in_fallback_mode':False, '_fallback_engine_type':'vlm',
            '_has_multimodal_content':staticmethod(lambda messages: bool(messages)),
            '_apply_chat_template':lambda *args, **kwargs:'prompt',
            'stream_generate':stream_generate})
        engine = Engine()
        for image in (False, True):
            engine._in_fallback_mode = not image
            messages = [{'image':True}] if image else []
            with self.assertRaisesRegex(ValueError, 'chat fallback'):
                await engine.chat(messages, thinking_budget=4)
            with self.assertRaisesRegex(ValueError, 'chat fallback'):
                await anext(engine.stream_chat(messages, thinking_budget=4))
        engine._in_fallback_mode = False
        stream = engine.stream_chat([], thinking_budget=4)
        self.assertEqual(await anext(stream), 'first')
        await stream.aclose()
        self.assertEqual(closed, [True])

    async def test_native_generation_rejects_eviction_before_engine_mutation(self):
        for name in ('generate', 'stream_generate'):
            node = self.method('omlx/engine/dflash.py', 'DFlashEngine', name)
            ns = self.load([node], {})
            Engine = type('Engine', (), {
                name:ns[name], '_loaded':True, '_in_fallback_mode':False,
                '_tokenize_prompt':lambda self, prompt:[99],
                '_should_fallback':lambda self, prompt:True})
            engine = Engine()
            with self.assertRaisesRegex(ValueError, 'model-eviction fallback'):
                result = getattr(engine, name)('prompt', logits_processor_factory=lambda tokens:None)
                if name == 'generate':
                    await result
                else:
                    await anext(result)

    async def test_ddtree_cannot_silently_drop_the_processor(self):
        node = self.method('dflash_mlx/engine/spec_epoch.py', 'SpeculativeSession', '_run_decode_events')
        ns = self.load([node], {})
        session = SimpleNamespace(runtime_config=SimpleNamespace(verify_mode='ddtree'),
                                  draft_model=SimpleNamespace(is_dflash2=False))
        stream = ns['_run_decode_events'](session, request=SimpleNamespace(temperature=0, logits_processor=object()),
                                         state=None, prefill=None, yield_pause=None)
        with self.assertRaisesRegex(ValueError, 'DDTree'):
            next(stream)

    async def test_native_stochastic_verify_uses_constrained_target_and_original_draft(self):
        node = self.method('dflash_mlx/engine/spec_epoch.py', 'SpeculativeSession', '_run_decode_events')
        loop = next(n for n in node.body if isinstance(n, ast.While))
        start = next(i for i,n in enumerate(loop.body) if isinstance(n, ast.AnnAssign)
                     and isinstance(n.target, ast.Name) and n.target.id == 'verify_token_ids_host')
        end = next(i for i,n in enumerate(loop.body[start:], start) if isinstance(n, ast.Expr)
                   and isinstance(n.value, ast.Call) and ast.unparse(n.value.func) == 'state.acceptance_history.append')
        statements = loop.body[start:end+1]
        class IDs:
            shape = (4,)
            def tolist(self): return [3, 5, 6, 7]
            def __getitem__(self, item): return self
        raw, constrained, draft = object(), object(), IDs()
        seen = []
        policy = SimpleNamespace(
            process_block=lambda values, history, candidates: (
                seen.append(('process', values, list(history), candidates)) or constrained),
            commit=lambda accepted:seen.append(('commit', accepted)))
        def rejection(ids, target_probs, draft_probs, draft_indices):
            self.assertIs(target_probs, constrained)
            self.assertIs(draft_probs, draft)
            self.assertIsNone(draft_indices)
            return 1, 42
        request = SimpleNamespace(logits_processor=policy, repetition_penalty=1,
                                  temperature=1, top_p=.95, top_k=20, min_p=0)
        ns = {'request':request, 'state':SimpleNamespace(generated_token_ids=[8, 9], acceptance_history=[]),
              'verify_logits':raw, 'verify_token_ids':IDs(), 'profile_cycles':False, 'capture_logits':False,
              'suppress_token_mask':None, 'draft_probs_arr':draft, 'draft_indices_arr':None,
              'sampling_probs':lambda values,*args:values, 'rejection_sample':rejection}
        exec(compile(ast.fix_missing_locations(ast.Module(body=statements, type_ignores=[])), 'native-verify-walk', 'exec'), ns)
        self.assertEqual(seen, [('process',raw,[8,9],[3,5,6,7]),('commit',1)])
        self.assertEqual(ns['staged_first_next_id'], 42)


if __name__ == '__main__':
    unittest.main()
