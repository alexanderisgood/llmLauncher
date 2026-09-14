"""Compare the adapter against installed native chat dispatch without MLX/weights."""
import ast
import asyncio
from contextlib import aclosing
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

import omlx_hub_runtime as adapter


class PromptReuseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path.home() / "Library/Application Support/LLM Launcher/runtimes/omlx-0.6.4/lib/python3.11/site-packages/omlx/engine/dflash.py"
        if not source.exists():
            raise unittest.SkipTest("Requires the audited oMLX 0.6.4 source, but no model weights")
        tree = ast.parse(source.read_text())
        engine = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DFlashEngine")
        methods = {node.name:node for node in engine.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        cls.defaults = {arg.arg:ast.literal_eval(default) for arg, default in
            zip(methods['stream_generate'].args.args[-len(methods['stream_generate'].args.defaults):],
                methods['stream_generate'].args.defaults)}
        # Execute the installed chat dispatch and tokenizer dispatch unchanged.
        module = ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),
            methods['stream_chat'], methods['_tokenize_prompt']],type_ignores=[])
        cls.convert = staticmethod(lambda tools:[{'converted':copy.deepcopy(tool)} for tool in tools])
        namespace = {'aclosing':aclosing,'convert_tools_for_template':cls.convert}
        exec(compile(ast.fix_missing_locations(module),str(source),'exec'),namespace)
        cls.native_chat = staticmethod(namespace['stream_chat'])
        cls.native_tokenize = staticmethod(namespace['_tokenize_prompt'])

    def engine(self):
        owner = self
        class DFlashEngine:
            _loaded = True
            _in_fallback_mode = False
            _fallback_engine_type = 'llm'
            def __init__(self):
                self.renders = self.encodes = 0
                self._tokenizer_obj = SimpleNamespace(encode=self.encode)
            def encode(self,prompt):
                self.encodes += 1
                return list(prompt.encode('utf-8'))
            def _apply_chat_template(self,messages,tools,**kwargs):
                self.renders += 1
                return json.dumps([messages,tools,kwargs],ensure_ascii=False,sort_keys=True)
            def _tokenize_prompt(self,prompt):
                return owner.native_tokenize(self,prompt)
            async def stream_chat(self,*args,**kwargs):
                async with aclosing(owner.native_chat(self,*args,**kwargs)) as stream:
                    async for output in stream: yield output
            async def stream_generate(self,prompt,**kwargs):
                self.received = {**owner.defaults,**kwargs}
                self.tokens = self._tokenize_prompt(prompt)
                yield SimpleNamespace(new_text='same output')
        return DFlashEngine()

    def test_native_dispatch_parity_and_one_encode(self):
        async def run():
            for partial in (None, False, True):
                for tools in (None, [{'type':'function','function':{'name':'edit','parameters':{'type':'object'}}}]):
                    messages = [{'role':'user','content':'Review café 🙂'}, {'role':'assistant','content':'<think>unfinished'}]
                    settings = {'max_tokens':512,'tools':tools,'temperature':0.65,'top_p':0.9,
                        'top_k':30,'min_p':0.01,'repetition_penalty':1.03,'presence_penalty':0.2,
                        'stop':['STOP'],'thinking_budget':4096,
                        'chat_template_kwargs':{'enable_thinking':True},'is_partial':partial}
                    baseline = self.engine()
                    expected = [output.new_text async for output in baseline.stream_chat(messages,**settings)]
                    async def original(engine,messages,request,**kwargs):
                        async for output in engine.stream_chat(messages,**settings): yield output.new_text
                    with tempfile.TemporaryDirectory() as root:
                        server = SimpleNamespace(stream_chat_completion=original)
                        adapter.install(server,131072,str(Path(root)/'preview.json'))
                        candidate = self.engine()
                        actual = [text async for text in server.stream_chat_completion(candidate,messages,SimpleNamespace(max_tokens=512))]
                    self.assertEqual(actual,expected)
                    self.assertEqual(candidate.tokens,baseline.tokens)
                    self.assertEqual(candidate.received,baseline.received)
                    self.assertEqual((candidate.renders,candidate.encodes),(1,1))
        with patch.dict(sys.modules,{'omlx.api.tool_calling':SimpleNamespace(convert_tools_for_template=self.convert)}):
            asyncio.run(run())

    def test_multimodal_fallback_cannot_bypass_text_route_guard(self):
        async def original(engine,messages,request,**kwargs):
            async for output in engine.stream_chat(messages): yield output.new_text
        async def run():
            with tempfile.TemporaryDirectory() as root:
                server = SimpleNamespace(stream_chat_completion=original)
                adapter.install(server,131072,str(Path(root)/'preview.json'))
                engine = self.engine()
                engine._fallback_engine_type = 'vlm'
                engine._has_multimodal_content = lambda messages:True
                with self.assertRaisesRegex(ValueError,'text-only'):
                    async for _ in server.stream_chat_completion(engine,[],SimpleNamespace(max_tokens=512)): pass
                self.assertEqual(engine.encodes,0)
        asyncio.run(run())


if __name__ == '__main__': unittest.main()
