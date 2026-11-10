"""Shared LM Studio residency proof uses read-only generated native replies."""
import io
import json
from types import SimpleNamespace
import unittest
from unittest import mock

import benchmark_evidence
import launcher


class SharedModelUnloadTests(unittest.TestCase):
    def setUp(self):
        self.plan = launcher.LaunchPlan("a1b2c3d4-generated", "lmstudio", "pi",
            {"name": "Generated", "servedId": "llm-launcher-a1b2c3d4"}, "/generated",
            8192, 1024, "off", 1234, "custom", {})
        self.manager = SimpleNamespace(plan=None, process=None, proxy_process=None,
            aux_process=None, snapshot=lambda: {"phase": "idle"})

    def receipt(self, reply, *, ports=(1234,), safe=True, closed=True, status=200):
        raw = reply if isinstance(reply, bytes) else json.dumps(reply).encode()
        response = io.BytesIO(raw)
        response.status = status
        with mock.patch.object(launcher, "lmstudio_server_status", return_value=(True, 1234)), \
                mock.patch.object(launcher, "lmstudio_server_is_safe", return_value=safe), \
                mock.patch.object(launcher, "_loopback_port_is_closed", return_value=closed) as port_probe, \
                mock.patch.object(launcher.urllib.request, "urlopen", return_value=response) as read, \
                mock.patch.object(launcher.subprocess, "Popen", side_effect=AssertionError("No process may start")), \
                mock.patch.object(launcher.os, "killpg", side_effect=AssertionError("No process may be signalled")):
            result = launcher.benchmark_clean_unload_evidence(self.manager, None, None,
                list(ports), plan=self.plan)
            if read.called:
                self.assertEqual(read.call_args.args[0].full_url, "http://127.0.0.1:1234/api/v1/models")
            self.assertNotIn(mock.call(1234), port_probe.call_args_list)
        return result

    def test_exact_unloaded_instance_preserves_service_and_unrelated_models(self):
        receipt = self.receipt({"models": [{"loaded_instances": [{"id": "unrelated-model"}]}]})
        self.assertTrue(receipt["clean"])
        self.assertTrue(receipt["modelUnloaded"])
        self.assertTrue(receipt["sharedServerRetained"])
        self.assertEqual(receipt["checkedPorts"], [])
        self.assertNotIn("processExited", receipt)
        self.assertIsNone(benchmark_evidence.unload_receipt_issue(receipt, "lmstudio"))
        self.assertIsNotNone(benchmark_evidence.unload_receipt_issue(receipt, "omlx"))

    def test_target_loaded_loading_or_malformed_inventory_cannot_certify_cleanup(self):
        target = self.plan.model["servedId"]
        for reply in ({"models": [{"loaded_instances": [{"id": target}]}]},
                      {"models": [{"loaded_instances": [], "loading_instances": [{"id": target}]}]},
                      {"models": [{}]}, {"models": [{"loaded_instances": None}]},
                      {"models": [{"loaded_instances": [{"id": None}]}]}, {"data": []},
                      b"{" , b"x" * 4_000_001):
            with self.subTest(reply=str(reply)[:100]):
                receipt = self.receipt(reply)
                self.assertFalse(receipt["clean"])
                self.assertFalse(receipt["modelUnloaded"])
                self.assertIsNotNone(benchmark_evidence.unload_receipt_issue(receipt, "lmstudio"))

    def test_private_listener_and_native_service_safety_remain_required(self):
        valid = {"models": [{"loaded_instances": []}]}
        self.assertFalse(self.receipt(valid, ports=(1234, 1235), closed=False)["clean"])
        self.assertFalse(self.receipt(valid, safe=False)["clean"])
        self.assertFalse(self.receipt(valid, status=500)["clean"])
        receipt = self.receipt(valid, ports=(1235, 1234))
        self.assertTrue(receipt["clean"])
        self.assertEqual(receipt["checkedPorts"], [1235])
        self.assertIsNone(benchmark_evidence.unload_receipt_issue(receipt, "lmstudio"))

    def test_replacement_or_invalid_identifier_cannot_certify_the_old_owner(self):
        self.manager.plan = object()
        self.assertFalse(self.receipt({"models": []})["clean"])
        self.manager.plan = None
        self.plan.model["servedId"] = "llm-launcher-deadbeef"
        self.assertFalse(self.receipt({"models": []})["clean"])

    def test_replacement_during_native_read_does_not_reuse_an_idle_snapshot(self):
        response = io.BytesIO(b'{"models":[]}')
        response.status = 200
        def native_read(*_args, **_kwargs):
            self.manager.plan = object()
            return response
        with mock.patch.object(launcher, "lmstudio_server_status", return_value=(True, 1234)), \
                mock.patch.object(launcher, "lmstudio_server_is_safe", return_value=True), \
                mock.patch.object(launcher.urllib.request, "urlopen", side_effect=native_read):
            receipt = launcher.benchmark_clean_unload_evidence(self.manager, None, None,
                [1234], plan=self.plan)
        self.assertTrue(receipt["modelUnloaded"])
        self.assertFalse(receipt["managerIdle"])
        self.assertFalse(receipt["clean"])


if __name__ == "__main__":
    unittest.main()
