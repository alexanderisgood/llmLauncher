import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import launcher
from omlx_hub_runtime import PrefillWriter


class PrefillStats(unittest.TestCase):
    def test_native_event_receipt_preserves_events_and_cache_accounting(self):
        event_type = type('PrefillCompleteEvent', (SimpleNamespace,), {})
        event = event_type(prefill_us=2000000, prompt_token_count=40600,
                           prefill_tokens_computed=600, prefill_tokens_restored=40000)
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'stats.json'
            writer = PrefillWriter(path, 'chatcmpl-1')
            token = object()
            self.assertEqual(list(writer.events(iter([event, token]))), [event, token])
            writer.finish()
            records = json.loads(path.read_text())
            self.assertEqual(records[0]['tokensPerSecond'], 300)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            activity = {'active':[], 'recent':[{'runtimeResponseId':'chatcmpl-1',
                'usageReported':True, 'promptTokens':40600}]}
            merged = launcher.merge_omlx_prompt_stats(activity, records)
            stats = merged['recent'][0]['promptProcessing']
            self.assertEqual(stats['tokensPerSecond'],300)
            self.assertEqual(stats['cachedTokens'],40000)
            for i in range(40): PrefillWriter(path, f'chatcmpl-{i}')
            self.assertEqual(len(json.loads(path.read_text())),32)

    def test_mismatch_duplicate_and_unknown_response_rejected(self):
        receipt = {'responseId':'a', 'promptTokens':200, 'processedTokens':100,
            'cachedTokens':100, 'elapsedSeconds':1}
        for records, request in (([receipt], {'runtimeResponseId':'b'}),
                ([receipt,receipt], {'runtimeResponseId':'a'}),
                ([receipt], {'runtimeResponseId':'a', 'usageReported':True,'promptTokens':201}),
                ([{**receipt,'elapsedSeconds':0}],{'runtimeResponseId':'a'})):
            result = launcher.merge_omlx_prompt_stats({'recent':[request]}, records)
            self.assertNotIn('promptProcessing', result['recent'][0])

    def test_prefill_before_first_byte_requires_one_matching_active_request(self):
        start='2026-09-05T21:00:00+00:00'
        record={'responseId':'a','startedAt':1788642001,'phase':'prefill'}
        from datetime import datetime
        record['startedAt']=datetime.fromisoformat(start).timestamp()+1
        request={'state':'running','startedAt':start,'liveTelemetry':{'phase':'decode','tokensPerSecond':900}}
        result=launcher.merge_omlx_prompt_stats({'active':[request]},[record])
        self.assertEqual(result['active'][0]['liveTelemetry']['phase'],'prefill')
        self.assertIsNone(result['active'][0]['liveTelemetry']['tokensPerSecond'])
        result=launcher.merge_omlx_prompt_stats({'active':[request,request]},[record])
        self.assertEqual(result['active'][0]['liveTelemetry']['phase'],'decode')

if __name__ == '__main__': unittest.main()
