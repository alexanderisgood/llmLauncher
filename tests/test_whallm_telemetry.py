import copy
import io
import json
import unittest
from types import SimpleNamespace
from unittest import mock

import launcher
import whallm_runtime
import whallm_telemetry as telemetry


class WhallmTelemetry(unittest.TestCase):
    def setUp(self):
        self.config = {"install": {"modelPath": "/private/model", "runtimeIdentity": "runtime"},
                       "context": 16384, "output": 4096}
        self.plan = SimpleNamespace(run_id="owner", backend="whallm", purpose="session", port=18082,
            model={"nativeWhallm": {"runtimeIdentity": "runtime"}}, secrets={"apiKey": "private-test-key"},
            options={"_whallmConfig": self.config})
        self.activity = {"lanes": 1, "coverage": {"allLauncherSurfaces": True},
            "active": [{"id": "request-a", "state": "running", "runSeconds": 11}], "recent": []}
        self.snapshot = {"loaded_model": whallm_runtime.SERVED_ID, "loading_model": None,
            "model_path": "/private/model", "runtime": {"slots": 4096, "read_workers": 4,
                "prompt_cache_memory_gib": 2, "ane_prefill_ratio": .25, "mtp_enabled": False},
            "launcher_contract": {"context": 16384, "output": 4096, "memoryGiB": 40,
                "manifestSHA256": whallm_runtime.MANIFEST_SHA256, "runtimeIdentity": "runtime"},
            "performance": {"completed_request_count": 4, "runtime_prompt_tokens": 10000,
                "prompt_cache_reused_tokens": 8000, "runtime_generation_tokens": 51,
                "generation_tokens": 51, "generating": True, "request_seconds": 10,
                "time_to_first_token_seconds": 5, "prefill_tokens_per_second": 400,
                "decode_end_to_end_tokens_per_second": 10, "decode_model_step_tokens_per_second": 100,
                "unrelated": "must not copy"}}
        self.observations = {}

    def merge(self):
        return telemetry.merge_activity(self.plan, self.activity, self.snapshot, self.observations)

    def finish(self):
        self.snapshot["performance"].update(generating=False, completed_request_count=5)
        self.activity["recent"] = [{"id": "request-a", "state": "completed", "runSeconds": 11,
                                   "usageReported": True, "promptTokens": 10000, "completionTokens": 51}]
        self.activity["active"] = []

    def test_live_native_rates_exclude_cached_tokens_and_model_step_timing(self):
        request = self.merge()["active"][0]
        self.assertEqual(request["runtimeTokensPerSecond"], 10)
        self.assertEqual(request["liveTelemetry"]["phase"], "decode")
        self.assertEqual(request["liveTelemetry"]["contextTokens"], 10051)
        self.assertEqual(request["promptProcessing"]["processedTokens"], 2000)
        self.assertEqual(request["promptProcessing"]["cachedTokens"], 8000)
        self.assertEqual(request["promptProcessing"]["tokensPerSecond"], 400)
        self.assertNotIn("liveTelemetry", self.activity["active"][0])
        self.assertNotIn("must not copy", json.dumps(self.observations))

    def test_previous_native_receipt_does_not_leak_into_new_prefill(self):
        self.merge()
        self.finish()
        self.assertEqual(self.merge()["recent"][0]["runtimeTokensPerSecond"], 10)
        self.activity["active"] = [{"id": "request-b", "state": "running", "runSeconds": .2}]
        # Server starts before runtime.start resets the previous metrics.
        self.snapshot["performance"].update(generating=True, generation_tokens=0)
        request = self.merge()["active"][0]
        self.assertEqual(request["liveTelemetry"], {"source": "whallm-native-stats", "phase": "prefill"})
        self.assertNotIn("runtimeTokensPerSecond", request)
        self.assertNotIn("promptProcessing", request)
        self.snapshot["performance"].update(runtime_generation_tokens=0, request_seconds=.1,
            time_to_first_token_seconds=0, prefill_tokens_per_second=0,
            decode_end_to_end_tokens_per_second=0)
        self.assertNotIn("promptProcessing", self.merge()["active"][0])

    def test_final_receipt_requires_next_counter_and_matching_usage(self):
        for change in ({"completed_request_count": 6}, {"runtime_prompt_tokens": 9999},
                       {"runtime_generation_tokens": 52}):
            with self.subTest(change=change):
                self.setUp(); self.merge(); self.finish()
                self.snapshot["performance"].update(change)
                self.assertNotIn("runtimeTokensPerSecond", self.merge()["recent"][0])
        self.setUp(); self.merge(); self.finish()
        self.assertEqual(self.merge()["recent"][0]["runtimeTokensPerSecond"], 10)
        # Reusing the same final response's counts does not bind a different relay request.
        self.activity["recent"][0]["id"] = "request-b"
        self.assertNotIn("runtimeTokensPerSecond", self.merge()["recent"][0])

    def test_a_fast_completion_can_match_one_counter_change_between_polls(self):
        self.activity["active"] = []
        self.snapshot["performance"]["generating"] = False
        self.merge()
        self.finish()
        self.assertEqual(self.merge()["recent"][0]["promptProcessing"]["tokensPerSecond"], 400)
        self.plan.run_id = "different-owner"
        self.assertNotIn("promptProcessing", self.merge()["recent"][0])

    def test_malformed_unowned_ambiguous_or_stale_metrics_are_not_published(self):
        mutations = [lambda: self.snapshot.update(loaded_model="other"),
            lambda: self.snapshot.update(runtime=[]),
            lambda: self.activity.update(lanes=2),
            lambda: self.activity["active"].append(copy.deepcopy(self.activity["active"][0])),
            lambda: self.snapshot["performance"].update(request_seconds=100),
            lambda: self.snapshot["performance"].update(runtime_prompt_tokens=True),
            lambda: self.snapshot["performance"].update(prompt_cache_reused_tokens=10001),
            lambda: self.snapshot["performance"].update(request_seconds=float("inf"))]
        for mutate in mutations:
            self.setUp(); mutate()
            self.assertNotIn("liveTelemetry", self.merge()["active"][0])
        self.setUp()
        self.snapshot["performance"].update(prefill_tokens_per_second=float("nan"),
                                             decode_end_to_end_tokens_per_second=10**500)
        request = self.merge()["active"][0]
        self.assertNotIn("runtimeTokensPerSecond", request)
        self.assertNotIn("promptProcessing", request)
        self.setUp()
        self.snapshot["performance"]["prefill_tokens_per_second"] = 2000
        self.assertNotIn("promptProcessing", self.merge()["active"][0],
                         "total prompt tokens divided by TTFT must not include cached tokens")

    def test_status_fetch_is_private_bounded_and_optional_for_health_checks(self):
        with mock.patch.object(telemetry.urllib.request, "urlopen",
            return_value=io.BytesIO(json.dumps(self.snapshot).encode())) as opened:
            telemetry.request_activity(self.plan, self.activity, self.observations)
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:18082/api/status")
        self.assertEqual(request.get_header("Authorization"), "Bearer private-test-key")
        self.assertEqual(opened.call_args.kwargs["timeout"], .6)
        with mock.patch.object(telemetry.urllib.request, "urlopen",
            return_value=io.BytesIO(b" " * (telemetry.MAX_STATUS_BYTES + 1))):
            self.assertIs(telemetry.request_activity(self.plan, self.activity, self.observations), self.activity)
        manager = launcher.RunManager()
        manager.plan = self.plan
        manager.state = {"phase": "running"}
        with mock.patch.object(manager, "_session_proxy_api", return_value=self.activity), \
             mock.patch.object(telemetry, "request_activity", return_value=self.activity) as fetch:
            manager.request_activity(include_engine_telemetry=False)
            fetch.assert_not_called()
            manager.request_activity()
            fetch.assert_called_once()
            fetch.reset_mock()
            manager.state["phase"] = "stopping"
            manager.request_activity()
            fetch.assert_not_called()
        self.plan.model.pop("nativeWhallm")
        with mock.patch.object(telemetry.urllib.request, "urlopen") as opened:
            telemetry.request_activity(self.plan, self.activity, self.observations)
            opened.assert_not_called()


if __name__ == "__main__":
    unittest.main()
