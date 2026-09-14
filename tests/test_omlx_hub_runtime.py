import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import sys
import http.client
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from unittest.mock import patch

import codex_proxy
import omlx_hub_runtime as adapter
import session_proxy


class HubRuntimeTests(unittest.TestCase):
    def test_only_native_prompt_memory_rejection_requests_compaction(self):
        error = {'code':'prefill_memory_exceeded','message':'Prefill requires 37.91 GB; ceiling 37.44 GB',
                 'estimated_bytes':40703772936,'limit_bytes':40200896512}
        original = json.dumps({'error':error}).encode()
        rewritten = session_proxy.normalize_omlx_compactable_error(original)
        actual = json.loads(rewritten)['error']
        self.assertTrue(actual['message'].startswith('context_length_exceeded:'))
        self.assertIn(error['message'],actual['message'])
        for key in ('code','estimated_bytes','limit_bytes'):
            self.assertEqual(actual[key],error[key])
        self.assertEqual(session_proxy.normalize_omlx_compactable_error(rewritten),rewritten)
        for payload in (b'broken',b'[]',b'{"error":"bad"}',
                        b'{"error":{"code":"allocation_failed","message":"out of memory"}}'):
            self.assertEqual(session_proxy.normalize_omlx_compactable_error(payload),payload)

    def test_relay_publishes_response_identity_before_completion(self):
        self.run_relay_fixture(False)

    def test_relay_delivers_compactable_memory_error_and_marks_request_failed(self):
        self.run_relay_fixture(True)

    def run_relay_fixture(self, memory_rejection):
        release = threading.Event()
        class Upstream(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                if memory_rejection:
                    payload = b'{"error":{"code":"prefill_memory_exceeded","message":"Prompt peak exceeds Metal cap"}}'
                    self.send_response(400)
                    self.send_header('Content-Type','application/json')
                    self.send_header('Content-Length',str(len(payload)))
                    self.send_header('ETag','stale')
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                self.send_response(200)
                self.send_header('Content-Type','text/event-stream')
                self.end_headers()
                self.wfile.write(b'data: {"id":"chatcmpl-12345678","choices":[{"index":0,"delta":{"role":"assistant"}}]}\n\n')
                self.wfile.flush()
                release.wait(5)
                self.wfile.write(b'data: [DONE]\n\n')
        try:
            upstream = ThreadingHTTPServer(('127.0.0.1',0),Upstream)
            relay = ThreadingHTTPServer(('127.0.0.1',0),session_proxy.ProxyHandler)
        except PermissionError:
            self.skipTest('loopback unavailable')
        relay.config={'upstreamPort':upstream.server_port,'upstreamKey':'private','backend':'omlx'}
        relay.registry=session_proxy.SurfaceRegistry([{'id':'11111111-1111-4111-8111-111111111111','client':'pi','key':'client-key-1234567890',
            'samplingContract':{'schemaVersion':1,'controlled':True,'mode':'model','values':{}},
            'samplingEnforcement':{'protocol':'chat-completions','representableFields':[],'implicitModelDefaults':False}}])
        relay.scheduler=session_proxy.RequestScheduler(1)
        for server in (upstream,relay):
            server.daemon_threads=True
            threading.Thread(target=server.serve_forever,daemon=True).start()
        connection=http.client.HTTPConnection('127.0.0.1',relay.server_port,timeout=3)
        try:
            with patch.object(session_proxy,'transform_chat_request',side_effect=lambda body,*args:body):
                connection.request('POST','/v1/chat/completions',json.dumps({'stream':True,'max_tokens':32}),
                    {'Authorization':'Bearer client-key-1234567890','Content-Type':'application/json'})
                response=connection.getresponse()
                if memory_rejection:
                    self.assertEqual(response.status,400)
                    self.assertIsNone(response.getheader('Content-Length'))
                    self.assertIsNone(response.getheader('ETag'))
                    error = json.loads(response.read())['error']
                    self.assertEqual(error['code'],'prefill_memory_exceeded')
                    self.assertIn('context_length_exceeded:',error['message'])
                    recent = relay.scheduler.snapshot([])['recent']
                    self.assertEqual(recent[0]['result'],'upstream-error')
                    return
                self.assertEqual(response.status,200)
                deadline=time.monotonic()+2
                while time.monotonic()<deadline:
                    active=relay.scheduler.snapshot([])['active']
                    if active and active[0]['runtimeResponseId']: break
                    time.sleep(.01)
                self.assertEqual(active[0]['runtimeResponseId'],'chatcmpl-12345678')
                self.assertEqual(active[0]['state'],'running')
                release.set()
                response.read()
        finally:
            release.set()
            connection.close()
            for server in (relay,upstream): server.shutdown(); server.server_close()

    def test_byte_heavy_prompt_uses_native_guard_only_for_streaming(self):
        request = {'messages':[{'role':'user','content':'code = 123;\n' * 2000}],
                   'stream':True, 'max_tokens':4096}
        config = {'backend':'omlx','contextLimit':8192,'omlxNativeContextGuard':True}
        self.assertEqual(json.loads(codex_proxy.bound_omlx_request_to_context(
            request, config, 'max_tokens'))['max_tokens'],4096)
        for modified in ({**config,'omlxNativeContextGuard':False}, config):
            request['stream'] = modified is not config
            with self.assertRaisesRegex(ValueError,'context_length_exceeded'):
                codex_proxy.bound_omlx_request_to_context(request, modified, 'max_tokens')
        self.assertEqual(adapter.bounded_output(41000,100000,131072),90072)
        with self.assertRaisesRegex(ValueError,'context_length_exceeded'):
            adapter.bounded_output(8192,100,8192)

    def test_partial_code_is_readable_and_not_an_executable_call(self):
        text = '<tool_call>\n<function=write>\n<parameter=path>\ngame.js\n</parameter>\n<parameter=content>\nconst x = "<script>";\nconst y = '
        preview = adapter.tool_preview(text)
        self.assertEqual(preview['title'],'Writing · write')
        args = json.loads(preview['text'])
        self.assertEqual(args['path'],'game.js')
        self.assertIn('\nconst y = ',args['content'])
        self.assertIsNone(adapter.tool_preview(text+'</parameter></function></tool_call>'))

    def test_preview_is_private_bounded_and_cleared(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'preview.json'
            writer = adapter.PreviewWriter(path,'chatcmpl-12345678')
            writer.feed('<tool_call><function=write><parameter=content>'+ 'x'*100000)
            value = json.loads(path.read_text())
            self.assertEqual(value['responseId'],'chatcmpl-12345678')
            self.assertLessEqual(len(value['text']),60000)
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            writer.clear()
            self.assertFalse(path.exists())

    def test_large_tool_preview_keeps_header_and_newest_output_until_closed(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'preview.json'
            writer = adapter.PreviewWriter(path,'chatcmpl-long-preview')
            writer.feed('<tool_call><function=write><parameter=path>large.js</parameter><parameter=content>')
            for index in range(8):
                writer.last_write = 0
                suffix = f'\nlatest line {index} 🙂'
                writer.feed('x'*100000 + suffix)
                self.assertLessEqual(len(writer.text),256000)
                preview = json.loads(path.read_text())
                self.assertEqual(preview['title'],'Writing · write')
                self.assertTrue(preview['text'].endswith(suffix))
                self.assertLessEqual(len(preview['text']),60000)
            writer.last_write = 0
            writer.feed('</parameter></tool_call>')
            self.assertFalse(path.exists(),'Completion removes the large-call preview')
            writer.last_write = 0
            writer.feed('<tool_call><function=bash><parameter=command>echo next')
            preview = json.loads(path.read_text())
            self.assertEqual(preview['title'],'Writing · bash')
            self.assertEqual(preview['text'],'echo next')
            writer.clear()

    def test_non_tool_text_stays_bounded_without_retaining_old_call_headers(self):
        value = '<tool_call><function=write>done</tool_call>' + 'plain thinking '*30000
        bounded = adapter.bounded_preview_text(value)
        self.assertEqual(len(bounded),256000)
        self.assertNotIn('<tool_call>',bounded)
        self.assertIsNone(adapter.tool_preview(bounded))

    def test_adapter_clamps_actual_tokens_preserves_output_and_cleans_on_abort(self):
        cleanup = []
        class DFlashEngine:
            _in_fallback_mode = False
            def _apply_chat_template(self,*args,**kwargs): return 'real rendered prompt'
            def _tokenize_prompt(self,prompt): return [1]*8000
            def _stream_dflash_events(self):
                event = type('PrefillCompleteEvent', (SimpleNamespace,), {})(
                    prefill_us=2000000, prompt_token_count=8000,
                    prefill_tokens_computed=600, prefill_tokens_restored=7400)
                return iter([event]), None, set()
            async def stream_generate(self,**kwargs):
                try:
                    self.received = kwargs
                    events, _, _ = self._stream_dflash_events()
                    self.observed = list(events)
                    yield SimpleNamespace(new_text='<tool_call><function=write><parameter=content>const x = 1;')
                    yield SimpleNamespace(new_text='\nconst y = 2;')
                finally:
                    cleanup.append('native')
        async def original(engine,messages,request,**kwargs):
            try:
                # Match upstream: this bare loop does not own inner cleanup.
                async for output in engine.stream_chat(messages=messages,max_tokens=4096):
                    yield output.new_text
            finally:
                cleanup.append('server')
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'preview.json'
            server=SimpleNamespace(stream_chat_completion=original)
            adapter.install(server,8192,str(path))
            engine=DFlashEngine()
            native_events = engine._stream_dflash_events
            async def run():
                stream=server.stream_chat_completion(engine,[],SimpleNamespace(max_tokens=4096),response_id='chatcmpl-12345678')
                first=await anext(stream)
                self.assertEqual(first,'<tool_call><function=write><parameter=content>const x = 1;')
                self.assertEqual(engine.received['max_tokens'],192)
                self.assertTrue(path.exists())
                stats = json.loads(path.with_name('prompt-stats.json').read_text())
                self.assertEqual(stats[0]['tokensPerSecond'],300)
                self.assertEqual(stats[0]['cachedTokens'],7400)
                self.assertEqual(len(engine.observed),1)
                await stream.aclose()
                # These assertions run before asyncio.run finalizes abandoned
                # generators. GC/event-loop cleanup must not hide the leak.
                self.assertEqual(cleanup, ['server', 'native'])
                self.assertEqual(engine._stream_dflash_events, native_events)
                self.assertFalse(path.exists())
                stats = json.loads(path.with_name('prompt-stats.json').read_text())
                self.assertEqual(stats[0]['phase'], 'finished')
            with patch.dict(sys.modules,{'omlx.api.tool_calling':SimpleNamespace(convert_tools_for_template=lambda t:t)}):
                asyncio.run(run())

    def test_response_id_correlates_fragmented_stream_without_text(self):
        metrics=session_proxy.ResponseMetrics('chat-completions','text/event-stream','omlx')
        payload=b'data: {"id":"chatcmpl-12345678","choices":[{"delta":{"content":"private"}}]}\n\n'
        for i in range(0,len(payload),3): metrics.feed(payload[i:i+3])
        stats=metrics.public_runtime_stats()
        self.assertEqual(stats,{'runtimeResponseId':'chatcmpl-12345678'})
        scheduler=session_proxy.RequestScheduler(1)
        request=scheduler.begin({'id':'surface','client':'pi'},'chat-completions')
        scheduler.await_turn(request)
        scheduler.set_runtime_stats(request,stats)
        self.assertEqual(scheduler.snapshot([])['active'][0]['runtimeResponseId'],'chatcmpl-12345678')


if __name__ == '__main__': unittest.main()
