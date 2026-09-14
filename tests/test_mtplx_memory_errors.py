import json
import unittest
import session_proxy as proxy

ERROR = {'code':'insufficient_memory','type':'server_error','status':507,
    'message':"insufficient memory: this prompt projects 40.7 GiB against the engine's 40.0 GiB limit (0.7 GiB over) after reclamation (107326 prompt tokens, 40 not cached). This request was refused before prefill instead of pushing the Mac into swap."}

class MtplxMemoryErrorTests(unittest.TestCase):
    def test_json_error_preserves_native_diagnostics_and_is_idempotent(self):
        original=json.dumps({'error':ERROR}).encode()
        result=proxy.normalize_mtplx_compactable_error(original)
        error=json.loads(result)['error']
        self.assertEqual({k:error[k] for k in ['code','type','status']},{k:ERROR[k] for k in ['code','type','status']})
        self.assertTrue(error['message'].startswith('context_length_exceeded: prefill_memory_exceeded:'))
        self.assertIn(ERROR['message'],error['message'])
        self.assertEqual(proxy.normalize_mtplx_compactable_error(result),result)

    def test_unrelated_errors_do_not_trigger_replay(self):
        for payload in [b'broken',b'[]',b'{"error":"bad"}',json.dumps({'error':{**ERROR,'message':'allocation failed during decode'}}).encode(),json.dumps({'error':{**ERROR,'message':'sustained critical memory pressure during prefill'}}).encode(),json.dumps({'error':{**ERROR,'code':'RuntimeError'}}).encode()]:
            self.assertEqual(proxy.normalize_mtplx_compactable_error(payload),payload)

    def test_fragmented_stream_preserves_progress_and_terminal_error(self):
        progress=b'data: {"id":"test","choices":[{"delta":{}}],"mtplx_progress":{"phase":"waiting"}}\n\n'
        error=json.dumps({'id':'test','choices':[{'index':0,'delta':{},'finish_reason':'error'}],'error':ERROR}).encode()
        frame=b'id: error-id\r\ndata: '+error+b'\r\n\r\n'
        stream=progress+frame+b'data: [DONE]\n\n'
        for step in [1,7,len(stream)]:
            guard=proxy.ChatCompletionLimitGuard(100000,mtplx_memory_recovery=True)
            output=b''.join(guard.feed(stream[i:i+step]) for i in range(0,len(stream),step))+guard.finish()
            self.assertTrue(output.startswith(progress))
            self.assertIn(b'id: error-id\r\n',output)
            self.assertIn(b'context_length_exceeded: prefill_memory_exceeded:',output)
            self.assertIn(b'"finish_reason": "error"',output)
            self.assertTrue(output.endswith(b'data: [DONE]\n\n'))
            self.assertTrue(guard.memory_refused)

    def test_other_engines_and_successes_are_unchanged(self):
        frame=b'data: '+json.dumps({'error':ERROR}).encode()+b'\n\n'
        guard=proxy.ChatCompletionLimitGuard(100000)
        self.assertEqual(guard.feed(frame)+guard.finish(),frame)
        success=b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\ndata: [DONE]\n\n'
        guard=proxy.ChatCompletionLimitGuard(100000,mtplx_memory_recovery=True)
        self.assertEqual(guard.feed(success)+guard.finish(),success)
        self.assertFalse(guard.memory_refused)

if __name__=='__main__':unittest.main()
