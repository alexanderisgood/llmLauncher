"""Opt-in already-running Splash: forced thinking exit and continued output.

LLM_LAUNCHER_SPLASH_BUDGET_LIVE_PORT=18082 python3 -m unittest discover -s tests -p test_splash_reasoning_live.py
Only local inference requests; no tools are executed and no engine is started.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import time
import unittest
import urllib.request


@unittest.skipUnless(os.environ.get('LLM_LAUNCHER_SPLASH_BUDGET_LIVE_PORT'), 'Opt-in running patched Splash')
class LiveThinkingBudgetTests(unittest.TestCase):
    def request(self, body):
        port = int(os.environ['LLM_LAUNCHER_SPLASH_BUDGET_LIVE_PORT'])
        req = urllib.request.Request(f'http://127.0.0.1:{port}/v1/chat/completions',
            data=json.dumps(body).encode(), headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req, timeout=120) as response:
            if body.get('stream'):
                chunks = [json.loads(line[6:]) for line in response
                          if line.startswith(b'data: ') and line.strip() != b'data: [DONE]']
                usage = next(c['usage'] for c in reversed(chunks) if c.get('usage'))
                choices = [v for c in chunks for v in c.get('choices', [])]
                return {'choices':[{'message':{
                    'content':''.join(c.get('delta',{}).get('content','') or '' for c in choices),
                    'reasoning_content':''.join(c.get('delta',{}).get('reasoning_content','') or '' for c in choices)},
                    'finish_reason':next(c['finish_reason'] for c in reversed(choices) if c.get('finish_reason'))}],
                    'usage':usage}
            return json.load(response)

    def test_concurrent_budgets_continue_to_text_json_and_tool(self):
        base = {'model':'incoai/Qwen3.8-27B-Splash', 'reasoning_effort':'xhigh', 'max_tokens':2048,
                'messages':[{'role':'user', 'content':
                    'Before answering, think through all 100 cases of the finite precision problem, '
                    'one by one in detail. Then return the exact marker BUDGET_OK.'}]}
        bodies = [
            {**base, 'thinking_budget_tokens':32, 'stream':True, 'stream_options':{'include_usage':True}},
            {**base, 'thinking_budget_tokens':64, 'response_format':{'type':'json_schema',
                'json_schema':{'name':'result', 'schema':{'type':'object',
                    'properties':{'result':{'type':'string', 'enum':['BUDGET_OK']}},
                    'required':['result'], 'additionalProperties':False}}}},
            {**base, 'thinking_budget_tokens':96, 'messages':[{'role':'user', 'content':
                'In private thinking, check 100 distinct finite precision cases in detail. '
                'Then call record_result exactly once with result BUDGET_OK. '
                'Use the tool to return the marker; no prose answer is needed.'}],
             'tool_choice':'required', 'tools':[
                {'type':'function','function':{'name':'record_result',
                    'description':'Record the final result marker.', 'parameters':{'type':'object',
                        'properties':{'result':{'type':'string','enum':['BUDGET_OK']}},
                        'required':['result'], 'additionalProperties':False}}}]},
        ]
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(self.request, bodies))
        for body, result in zip(bodies, results):
            usage = result['usage']
            reasoning = usage['completion_tokens_details']['reasoning_tokens']
            self.assertGreaterEqual(reasoning, body['thinking_budget_tokens'] - 8,
                                    'The test must actually reach the budget')
            self.assertLessEqual(reasoning, body['thinking_budget_tokens'])
            self.assertGreater(usage['completion_tokens'], reasoning + 1,
                               'The model must generate actual output after closing thinking')
            self.assertNotEqual(result['choices'][0]['finish_reason'], 'length',
                                str(result['choices'][0]['message'].get('content', ''))[:500])
        self.assertIn('BUDGET_OK', results[0]['choices'][0]['message']['content'])
        self.assertEqual(json.loads(results[1]['choices'][0]['message']['content']), {'result':'BUDGET_OK'})
        call = results[2]['choices'][0]['message']['tool_calls'][0]['function']
        self.assertEqual(call['name'], 'record_result')
        self.assertEqual(json.loads(call['arguments']), {'result':'BUDGET_OK'})
        print('Live native budget exits:', [r['usage']['completion_tokens_details']['reasoning_tokens'] for r in results],
              f'; text/JSON/tool output verified in {time.monotonic()-started:.1f}s')


if __name__ == '__main__':
    unittest.main()
