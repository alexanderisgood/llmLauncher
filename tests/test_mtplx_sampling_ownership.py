"""The Hub's validated sampler must reach MTPLX instead of becoming a hint."""
import json
import os
import unittest

import session_proxy
from sampling_contract import build_sampling_contract


class SamplingOwnership(unittest.TestCase):
    def test_late_pi_extension_cannot_restore_damaged_cache_affinity(self):
        recovered = "pi-session:recovery:" + "a" * 24
        body, headers = session_proxy.mtplx_launcher_request(b'{"messages":[]}', {
            "X-MTPLX-Session-ID": "pi-session",
            "X-LLM-Launcher-MTPLX-Recovery": recovered,
            "Authorization": "Bearer fixture",
        })
        self.assertEqual(headers["x-mtplx-session-id"], recovered)
        self.assertNotIn("X-MTPLX-Session-ID", headers)
        self.assertNotIn("X-LLM-Launcher-MTPLX-Recovery", headers)
        self.assertEqual(json.loads(body), {"messages": []})
        self.assertEqual(headers["Authorization"], "Bearer fixture")
        for invalid in ["plain-session", recovered + "\n", "x" * 300 + recovered]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                session_proxy.mtplx_launcher_request(b'{}', {
                    "x-llm-launcher-mtplx-recovery": invalid})

    def test_native_summary_alias_cannot_select_a_different_model(self):
        config={'backend':'mtplx','servedModel':'transport-current','outputLimit':4096,
                'servedModelAliases':['local-'+'a'*24]}
        body={'model':config['servedModelAliases'][0],'messages':[]}
        resolved=json.loads(session_proxy.transform_chat_request(json.dumps(body).encode(),config))
        self.assertEqual(resolved['model'],'transport-current')
        body['model']='another-model'
        with self.assertRaisesRegex(ValueError,'different model'):
            session_proxy.transform_chat_request(json.dumps(body).encode(),config)

    def request(self):
        contract = build_sampling_contract('model', model_defaults={
            'temperature': 1.0, 'top_p': .95, 'top_k': 20}).as_dict()
        policy = {'samplingContract': contract, 'samplingEnforcement': {
            'protocol': 'chat-completions', 'representableFields': ['temperature','top_p','top_k'],
            'implicitModelDefaults': False}}
        body = session_proxy.transform_chat_request(json.dumps({
            'model': 'served', 'messages': [{'role':'user','content':'Fixture'}],
            'max_tokens': 128, 'generation_mode': 'ar', 'depth': 8,
            'metadata': {'client':'pi'},
        }).encode(), {'backend':'mtplx', 'servedModel':'served', 'outputLimit':256,
                     'reasoning':'xhigh'}, policy)
        return session_proxy.mtplx_launcher_request(body, {
            'X-MTPLX-Client':'pi', 'X-MTPLX-Allow-Client-Controls':'false',
            'x-mtplx-session-id':'fixture-session', 'Authorization':'Bearer fixture'})

    def test_contract_and_affinity_survive_without_client_route_overrides(self):
        body, headers = self.request()
        value = json.loads(body)
        self.assertEqual(value['temperature'], 1.0)
        self.assertEqual(value['top_p'], .95)
        self.assertEqual(value['top_k'], 20)
        self.assertEqual(value['max_tokens'], 128)
        self.assertNotIn('generation_mode', value)
        self.assertNotIn('depth', value)
        self.assertEqual(headers['x-mtplx-session-id'], 'fixture-session')
        self.assertEqual(headers['Authorization'], 'Bearer fixture')
        self.assertEqual(headers['x-mtplx-client'], 'llm-launcher')
        self.assertNotIn('X-MTPLX-Client', headers)

    @unittest.skipUnless(os.environ.get('LLM_LAUNCHER_MTPLX_INTEGRATION') == '1',
                         'requires installed MTPLX Python')
    def test_native_runtime_honors_validated_controls(self):
        from mtplx.server import openai as server
        body, headers = self.request()
        metadata = json.loads(body)['metadata']
        self.assertFalse(server._client_controls_allowed({
            'x-mtplx-client':'pi', 'x-mtplx-allow-client-controls':'true'}, metadata))
        self.assertTrue(server._client_controls_allowed(headers, metadata))
        self.assertTrue(server._client_thinking_controls_allowed(headers, metadata))
