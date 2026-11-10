import json
import unittest
from session_proxy import ResponseMetrics

class NativeMetricsTests(unittest.TestCase):
    def parse(self, backend='omlx', **changes):
        usage=dict(prompt_tokens=100,completion_tokens=40,prompt_tokens_details={'cached_tokens':0},
                   prompt_eval_duration=2,generation_duration=5,generation_tokens_per_second=8,time_to_first_token=2.1)
        usage.update(changes)
        m=ResponseMetrics('chat-completions','application/json',backend)
        m.feed(json.dumps({'usage':usage,'choices':[]}).encode());m.finish()
        return m.public_runtime_stats()
    def test_native_usage_timings(self):
        s=self.parse();self.assertEqual(s['runtimeStatsSource'],'omlx-native-stats')
        self.assertEqual(s['runtimeTokensPerSecond'],8)
        self.assertEqual(s['promptProcessing']['tokensPerSecond'],50)
    def test_cached_prefill_not_misrepresented(self):
        self.assertNotIn('promptProcessing',self.parse(prompt_tokens_details={'cached_tokens':90}))
    def test_wrong_engine_and_invalid_numbers(self):
        self.assertNotIn('runtimeTokensPerSecond',self.parse(backend='slotstream'))
        self.assertNotIn('runtimeTokensPerSecond',self.parse(generation_tokens_per_second=float('nan')))
        self.assertNotIn('promptProcessing',self.parse(prompt_eval_duration=0))
