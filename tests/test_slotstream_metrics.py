import json
import unittest
import session_proxy as proxy


class SlotstreamMetricsTests(unittest.TestCase):
    def event(self, **changes):
        stats = dict(version=1, phase='completed', prompt_tokens=4000, processed_tokens=100,
                     cached_tokens=3900, prefill_seconds=0.5, decode_tokens=64, decode_seconds=4,
                     drafted_tokens=60, accepted_drafts=45, expert_pool_bytes=19000000000,
                     expert_pool_slots=6870, expert_hit_rate=.8)
        stats.update(changes)
        return dict(id='chatcmpl-12345678-1234-1234-1234-123456789abc', choices=[],
                    slotstream_metrics=stats, usage=dict(prompt_tokens=4000, completion_tokens=64))

    def parse(self, event, streaming=True, backend='slotstream'):
        metrics = proxy.ResponseMetrics('chat-completions', 'text/event-stream' if streaming else 'application/json', backend)
        wire=json.dumps(event).encode()
        if streaming: wire=b'data: '+wire+b'\n\n'
        for start in range(0,len(wire),7): metrics.feed(wire[start:start+7])
        if not streaming: metrics.finish()
        return metrics

    def test_native_stats_stream_and_json(self):
        for streaming in [True,False]:
            metrics=self.parse(self.event(),streaming)
            stats=metrics.public_runtime_stats()
            self.assertEqual(stats['promptProcessing']['tokensPerSecond'],200)
            self.assertEqual(stats['promptProcessing']['cachedTokens'],3900)
            self.assertEqual(stats['runtimeTokensPerSecond'],16)
            self.assertEqual(stats['speculativeAcceptancePercent'],75)
            self.assertEqual(stats['expertCache']['hitRatePercent'],80)
            self.assertEqual(stats['runtimeStatsSource'],'slotstream-native-stats')
            self.assertFalse(metrics.output_seen)

    def test_prefill_available_before_output_and_usage(self):
        event=self.event(phase='prefilled');event.pop('usage')
        metrics=self.parse(event)
        self.assertEqual(metrics.public_runtime_stats()['promptProcessing']['tokensPerSecond'],200)
        self.assertNotIn('runtimeTokensPerSecond',metrics.public_runtime_stats())
        self.assertEqual(metrics.public_usage(),(None,None))
        self.assertFalse(metrics.output_seen)

    def test_invalid_or_unrelated_metadata_not_reported(self):
        for changes in [dict(processed_tokens=101),dict(cached_tokens=True),dict(prefill_seconds=0),
                        dict(prefill_seconds=float('nan')),dict(version=True),dict(phase='invented')]:
            with self.subTest(changes=changes):
                self.assertEqual(self.parse(self.event(**changes)).public_runtime_stats(),{})
        self.assertEqual(self.parse(self.event(),backend='omlx').public_runtime_stats(),{})

    def test_usage_mismatch_and_impossible_acceptance(self):
        self.assertNotIn('runtimeTokensPerSecond',self.parse(self.event(decode_tokens=65)).public_runtime_stats())
        self.assertNotIn('speculativeAcceptancePercent',self.parse(self.event(accepted_drafts=61)).public_runtime_stats())
        event=self.event();event['usage']['prompt_tokens']=5000
        self.assertEqual(self.parse(event).public_runtime_stats(),{})

    def test_scheduler_retains_only_numeric_metadata(self):
        # Exercise the real public active and completion snapshots.
        scheduler=proxy.RequestScheduler(1)
        rid=scheduler.begin({'id':'test','client':'pi'},'chat-completions')
        self.assertTrue(scheduler.await_turn(rid))
        stats=self.parse(self.event()).public_runtime_stats()
        stats['promptProcessing']['secret']='private prompt'
        scheduler.set_runtime_stats(rid,stats)
        active=scheduler.snapshot([])['active'][0]
        self.assertEqual(active['promptProcessing']['tokensPerSecond'],200)
        self.assertNotIn('secret',active['promptProcessing'])
        self.assertIsNone(active['firstOutputAt'])
        scheduler.set_usage(rid,4000,64)
        scheduler.finish(rid,'completed',200)
        recent=scheduler.snapshot([])['recent'][0]
        self.assertEqual(recent['expertCache']['allocatedBytes'],19000000000)
        self.assertEqual(recent['runtimeStatsSource'],'slotstream-native-stats')
        rid=scheduler.begin({'id':'test','client':'pi'},'chat-completions')
        scheduler.set_runtime_stats(rid,stats)
        scheduler.set_usage(rid,5000,64)
        self.assertIsNone(scheduler.snapshot([])['queued'][0]['promptProcessing'])



if __name__=='__main__': unittest.main()
