"""Actual native parser and chat SSE logic: no weights, fake token events."""
import ast
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace
import time
import unittest
import uuid

NATIVE = Path(os.environ.get('OMLX_TEST_NATIVE_SITE', str(
    Path.home()/'Library/Application Support/LLM Launcher/runtimes/omlx-0.6.4/lib/python3.11/site-packages')))


def load_function(path, name, namespace):
    node = next(n for n in ast.parse(path.read_text()).body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    tree = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), node], type_ignores=[])
    exec(compile(ast.fix_missing_locations(tree), str(path), 'exec'), namespace)
    return namespace[name]


class Chunk(SimpleNamespace):
    def model_dump_json(self, **kwargs):
        return json.dumps(self, default=lambda x: {k:v for k,v in vars(x).items() if v is not None})


@unittest.skipUnless((NATIVE/'omlx/api/thinking.py').is_file(), 'audited oMLX runtime required')
class NativeCompletionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.thinking = {}
        path = NATIVE/'omlx/api/thinking.py'
        exec(compile(path.read_text(), str(path), 'exec'), self.thinking)
        self.Parser = self.thinking['ThinkingParser']

    def test_native_summary_distinguishes_length_from_eos_at_exact_limit(self):
        reason = load_function(NATIVE/'omlx/engine/dflash.py', '_generation_finish_reason', {})
        self.assertEqual(reason(SimpleNamespace(generation_tokens=3, generated_token_ids=(1,2,3)), 3, {99}), 'length')
        self.assertEqual(reason(SimpleNamespace(generation_tokens=3, generated_token_ids=(1,2,99)), 3, {99}), 'stop')
        self.assertEqual(reason(SimpleNamespace(generation_tokens=2, generated_token_ids=(1,99)), 3, {99}), 'stop')
        self.assertEqual(reason(SimpleNamespace(generation_tokens=3, generated_token_ids=(1,2,3)), 3, {99}, SimpleNamespace(finish_reason='tool_calls')), 'length')
        self.assertEqual(reason(None, 3, {99}), 'error')

    def test_strict_parser_preserves_unfinished_reasoning_and_partial_marker(self):
        for text in ('<think>unfinished reasoning', '<think>unfinished </thi', '<think:first>plain text'):
            parser = self.Parser(recover_unclosed=False)
            t,c = parser.feed(text); ft,fc = parser.finish()
            if text.startswith('<think>'):
                self.assertEqual(c+fc, '')
                self.assertEqual(t+ft, text[len('<think>'):])
            else:
                self.assertEqual(c+fc, text)
        parser = self.Parser(recover_unclosed=False)
        t,c = parser.feed('<think>work</think>answer'); ft,fc = parser.finish()
        self.assertEqual((t+ft,c+fc), ('work','answer'))
        self.assertFalse(parser.in_thinking)
        # Unrelated engines keep their original upstream recovery policy.
        parser = self.Parser(); parser.feed('<think>legacy recovery')
        self.assertEqual(parser.finish(), ('','legacy recovery'))

    async def run_stream(self, fragments, *, strict=True, finish='length', tools=True):
        extraction_calls = []
        class Filter:
            active = True
            def __init__(self,*args,**kwargs): pass
            def feed(self,text): return text
            def finish(self): return ''
            def take_recovery_candidate(self): return ''
        def extraction(thinking, regular, **kwargs):
            extraction_calls.append((thinking,regular))
            return SimpleNamespace(cleaned_text=regular, cleaned_thinking=thinking, tool_calls=None)
        async def generate(**kwargs):
            for text in fragments:
                yield SimpleNamespace(new_text=text, finished=False, finish_reason=None, tool_calls=None)
            yield SimpleNamespace(new_text='', finished=True, finish_reason=finish, tool_calls=None,
                                  prompt_tokens=12, completion_tokens=32, cached_tokens=0)
        engine = SimpleNamespace(tokenizer=None, preserve_native_thinking=strict, stream_chat=generate)
        metrics = SimpleNamespace(record_request_complete=lambda **kwargs:None)
        ns = dict(self.thinking, time=time, uuid=uuid, json=json, logger=logging.getLogger(__name__),
                  ChatCompletionChunk=Chunk, ChatCompletionChunkChoice=Chunk, ChatCompletionChunkDelta=Chunk,
                  ToolCallStreamFilter=Filter, extract_tool_calls_with_thinking=extraction,
                  _streaming_error_payload=lambda error,context: {'message':str(error)},
                  _resolve_metric_durations=lambda *args,**kwargs:(.1,.2),
                  get_server_metrics=lambda:metrics, _format_generation_speed_for_log=lambda *args,**kwargs:'fixture')
        stream = load_function(NATIVE/'omlx/server.py', 'stream_chat_completion', ns)
        request = SimpleNamespace(model='qwen-fixture', response_format=None, stream_options=None, max_tokens=32)
        frames = [chunk async for chunk in stream(engine, [], request, tools=[{}] if tools else None)]
        self.assertEqual(frames[-1], 'data: [DONE]\n\n')
        events = [json.loads(frame[6:]) for frame in frames[:-1]]
        thinking = ''.join(c.get('delta',{}).get('reasoning_content','') for e in events for c in e.get('choices',[]))
        content = ''.join(c.get('delta',{}).get('content','') for e in events for c in e.get('choices',[]))
        reasons = [c['finish_reason'] for e in events for c in e.get('choices',[]) if c.get('finish_reason')]
        return thinking,content,reasons,extraction_calls

    async def test_cutoff_keeps_thinking_out_of_answer_and_tool_execution(self):
        result = await self.run_stream(['<thi','nk>Let me calculate. ', '<tool_call>{"name":"write"}'])
        self.assertEqual(result, ('Let me calculate. <tool_call>{"name":"write"}', '', ['length'], []))

    async def test_eos_before_thinking_close_is_not_fabricated_answer(self):
        result = await self.run_stream(['<think>unfinished'], finish='stop')
        self.assertEqual(result, ('unfinished', '', ['stop'], []))

    async def test_normal_closed_reasoning_and_answer_remain_visible(self):
        result = await self.run_stream(['<think>real work</thi','nk>answer'], finish='stop')
        self.assertEqual(result[:3], ('real work','answer',['stop']))
        self.assertEqual(result[3], [('real work','answer')])

    async def test_other_engines_keep_upstream_recovery(self):
        result = await self.run_stream(['<think>legacy'], strict=False, tools=False)
        self.assertEqual(result[:3], ('legacy','legacy',['length']))


if __name__ == '__main__': unittest.main()
