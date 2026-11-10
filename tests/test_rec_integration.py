"""Offline checks of the new Rec route through the launcher's real contracts."""
from contextlib import ExitStack
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

import launcher
import rec_runtime
from tests import test_rec_runtime
from tests.helpers.resource_admission_harness import Fixture, GIB, snapshot


class RecIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_rec_runtime.RecRuntimeTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        with mock.patch.object(rec_runtime, "host_support", return_value=(True, "Supported fixture Mac")):
            self.model = rec_runtime.model_record(self.fixture.install, self.fixture.model,
                [(key, value.label) for key, value in launcher.ENGINE_ADAPTERS.items()], 48 * GIB)
        self.payload = {"backend": "rec", "client": "chat", "modelId": self.model["id"],
            "project": str(self.root), "context": 32768, "output": 8192, "reasoning": "auto",
            "mode": "custom", "options": {"acceleration": "off", "depth": 1, "kv": "off"}}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.dict(launcher.BINARIES, rec=str(self.fixture.binary)))

    def forbid_materialization(self):
        stack = ExitStack()
        for owner, name in ((launcher, "free_port"), (Path, "mkdir"), (Path, "symlink_to"),
                            (launcher.secrets, "token_urlsafe"), (launcher.secrets, "token_hex"),
                            (launcher.uuid, "uuid4"), (launcher.subprocess, "Popen")):
            stack.enter_context(mock.patch.object(owner, name, side_effect=AssertionError("Launch allocated before validation")))
        return stack

    def test_auto_request_passes_real_preflight_without_allocating(self):
        # normalized_request materializes only after this exact validator passes.
        with self.forbid_materialization():
            contract = launcher._launch_contract_validator().validate_live(self.payload, [self.model])
            custom = launcher._launch_contract_validator().validate_live({**self.payload,
                "generation": {"sampling": "custom", "temperature": 1.0, "topP": 0.95, "topK": 20,
                    "frequencyPenalty": 0.0, "repetitionPenalty": 1.0}}, [self.model])
        contract.require_validated()
        self.assertEqual(contract.selected.backend, "rec")
        self.assertEqual((contract.selected.context, contract.selected.output, contract.selected.reasoning), (32768, 8192, "auto"))
        self.assertIn("artifact", contract.completed_stages)
        self.assertEqual(contract.selected.sampling_enforcement["representableFields"],
            ("frequency_penalty", "presence_penalty", "repetition_penalty", "seed", "temperature", "top_k", "top_p"))
        self.assertEqual(custom.selected.sampling_contract["values"]["frequency_penalty"], 0.0)
        self.assertEqual(custom.selected.sampling_contract["values"]["repetition_penalty"], 1.0)
        self.assertEqual(self.model["backends"]["rec"]["samplingFields"], rec_runtime.SAMPLING_FIELDS)

    def test_normalized_request_rejects_unsupported_controls_before_allocation(self):
        variants = [({"reasoning": "off"}, "reasoning choices"),
            ({"options": {"acceleration": "mtp"}}, "Rec acceleration"),
            ({"options": {"depth": 2}}, "Rec draft depth"),
            ({"options": {"kv": "q8"}}, "Rec KV precision"),
            ({"context": 262145}, "Context must be"),
            ({"generation": {"sampling": "custom", "frequencyPenalty": 0.5}}, "frequency_penalty"),
            ({"generation": {"sampling": "custom", "repetitionPenalty": 1.1}}, "repetition_penalty")]
        with self.forbid_materialization():
            for changes, expected in variants:
                with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, expected):
                    launcher.normalized_request({**self.payload, **changes}, [self.model])

    def test_builder_uses_adapter_private_configuration_and_native_served_id(self):
        run = self.fixture.create_run()
        plan = SimpleNamespace(backend="rec", client="chat", model=copy.deepcopy(self.model),
            context=32768, output=4096, reasoning="auto", port=18081, runtime_binary=None,
            options=dict(self.payload["options"]), run_dir=run, secrets={}, warnings=[])
        with mock.patch.object(rec_runtime, "prepare_run", wraps=rec_runtime.prepare_run) as prepare, \
                mock.patch.object(launcher.secrets, "token_hex", return_value="34" * 32), \
                mock.patch.object(launcher.subprocess, "Popen", side_effect=AssertionError("Unexpected live startup")):
            launcher.build_rec(plan, self.model["backends"]["rec"])
        self.assertEqual(prepare.call_args.kwargs["output"], 4096)
        self.assertEqual(plan.model["servedId"], "flint")
        self.assertEqual(plan.secrets["apiKey"], "34" * 32)
        self.assertEqual(json.loads((run / "rec.json").read_text())["context"], 32768)
        self.assertEqual(Path(plan.engine_argv[-1]), run / "rec.json")
        self.assertEqual(plan.engine_env["HF_HUB_OFFLINE"], "1")

    def test_resource_estimate_charges_resident_weights_kv_runtime_and_os(self):
        admission = Fixture().domain
        model = copy.deepcopy(self.model)
        model["size"] = model["rec"]["weightBytes"] = 21 * GIB
        model["rec"]["geometry"].update(fullAttentionLayers=14, slidingAttentionLayers=35)
        resource = admission.public_session_resource(snapshot(40 * GIB))
        estimate = admission.launch_memory_estimate(self.payload, model, resource)
        native = rec_runtime.memory_estimate(model["rec"], 32768)
        os_reserve = max(admission.policy.session_os_reserve_min_bytes,
            round(48 * GIB * admission.policy.session_os_reserve_fraction))
        self.assertEqual(estimate["modelBytes"], 21 * GIB)
        self.assertEqual(estimate["ssdWeightBytes"], 0)
        self.assertGreater(estimate["kvCacheBytes"], 0)
        self.assertEqual(estimate["estimatedWorkingSetBytes"], native["estimatedWorkingSetBytes"])
        self.assertEqual(estimate["requiredHeadroomBytes"], native["estimatedWorkingSetBytes"] + os_reserve)
        self.assertFalse(estimate.get("ssdStreaming", False))
        self.assertEqual(estimate["parallelLanes"], 1)


if __name__ == "__main__":
    unittest.main()
