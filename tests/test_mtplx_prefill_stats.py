import copy
import json
from session_proxy import ResponseMetrics
import unittest
from types import SimpleNamespace
from launcher import merge_mtplx_prompt_activity

class MtplxPrefillStats(unittest.TestCase):
    def setUp(self):
        self.plan=SimpleNamespace(run_id='run',model={'servedId':'model'})
        self.cache={}
        self.activity={'active':[{'id':'relay','state':'running','runSeconds':10}], 'recent':[]}
        self.snapshot={'model_id':'model','in_flight':[{'request_id':'chatcmpl-12345678','model':'model','age_s':9,'prefill_state':{'phase':'chunk','tokens_total':10000,'tokens_done':9000,'cached_tokens':8000,'elapsed_s':2}}], 'recent':[]}
    def merge(self):
        return merge_mtplx_prompt_activity(self.plan,self.activity,self.snapshot,self.cache)
    def test_live_excludes_cached_tokens_and_retains_sample_during_decode(self):
        stats=self.merge()['active'][0]['promptProcessing']
        self.assertEqual(stats['tokensPerSecond'],500)
        self.assertTrue(stats['partial'])
        self.snapshot['in_flight'][0]['prefill_state']=None
        self.assertEqual(self.merge()['active'][0]['promptProcessing'],stats)
        self.assertNotIn('promptProcessing',self.activity['active'][0])
    def test_final_native_receipt_replaces_partial_and_survives_completion(self):
        self.merge()
        self.activity['recent']=[dict(self.activity['active'][0],state='completed',usageReported=True,promptTokens=10000,runtimeResponseId='chatcmpl-12345678')]
        self.activity['active']=[]
        self.snapshot['in_flight']=[]
        self.snapshot['recent']=[{'request_id':'chatcmpl-12345678','prompt_tokens':10000,'cached_tokens':8000,'new_prefill_tokens':2000,'prompt_eval_time_s':5,'secret_text':'must not copy'}]
        stats=self.merge()['recent'][0]['promptProcessing']
        self.assertEqual(stats['tokensPerSecond'],400)
        self.assertFalse(stats['partial'])
        self.assertNotIn('secret_text',str(self.cache))
    def test_ambiguous_or_stale_lane_never_matches(self):
        for mutate in [lambda s:s['in_flight'].append(copy.deepcopy(s['in_flight'][0])),lambda s:s['in_flight'][0].update(age_s=100),lambda s:s.update(model_id='other')]:
            original=copy.deepcopy(self.snapshot);mutate(self.snapshot)
            self.assertNotIn('promptProcessing',self.merge()['active'][0]);self.snapshot=original
    def test_invalid_counts_and_rates_are_ignored(self):
        for change in [{'tokens_done':float('inf')},{'cached_tokens':9500},{'tokens_done':10001},{'elapsed_s':float('nan')},{'elapsed_s':0}]:
            original=copy.deepcopy(self.snapshot)
            self.snapshot['in_flight'][0]['prefill_state'].update(change)
            self.assertNotIn('promptProcessing',self.merge()['active'][0]);self.snapshot=original
    def test_relay_exports_native_mtplx_id_before_completion(self):
        metrics = ResponseMetrics("chat-completions", "text/event-stream", backend="mtplx")
        metrics.feed(("data: " + json.dumps({"id":"chatcmpl-12345678","choices":[{"delta":{"content":"hello"}}]}) + "\n\n").encode())
        self.assertEqual(metrics.public_runtime_stats()["runtimeResponseId"], "chatcmpl-12345678")

    def test_other_run_cannot_reuse_sample(self):
        self.merge();self.plan.run_id='new';self.snapshot['in_flight'][0]['prefill_state']=None
        self.assertNotIn('promptProcessing',self.merge()['active'][0])

if __name__=='__main__':unittest.main()
