"""No-model checks for adopting exact local Uzu receipts without relabelling."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
PATCH_ROOT = ROOT / "runtime_patches/uzu/0.5.23"


def load_helper(name):
    spec = importlib.util.spec_from_file_location(name, PATCH_ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


candidate = load_helper("candidate_qualification")
adoption = load_helper("adopt_qualification")


class UzuQualificationAdoptionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.source = Path(self.directory.name) / "benchmarks.json"
        self.records = [
            {"id": key, "contextMin": context, "hardwareFingerprint": "this-mac",
             "originalEvidence": {"unchanged": True}}
            for key, context in adoption.RECORDS.items()
        ]
        self.write_records(self.records)
        self.app = SimpleNamespace(
            UZU_RUNTIME_RELEASE_BINARY_SHA256=candidate.BINARY_SHA256,
            UZU_RUNTIME_RELEASE_BINARY_SIZE=candidate.BINARY_SIZE,
            UZU_RUNTIME_SOURCE_PATCH_SHA256=candidate.PATCH_CHAIN_SHA256,
            UZU_RUNTIME_TAG=candidate.TAG,
            UZU_RUNTIME_PATH=Path("/unused/exact/mirai"),
            uzu_runtime_contract=Mock(return_value={"ready": True}),
            hardware_fingerprint=Mock(return_value="this-mac"),
            uzu_model_records=Mock(return_value=[{"id": candidate.MODEL_ID}]),
            calibration_plan=Mock(return_value={
                "action": "apply-existing", "evidence": {"qualified": True},
            }),
        )
        modules = patch.dict(sys.modules, {"candidate_qualification": candidate})
        modules.start()
        self.addCleanup(modules.stop)

    def write_records(self, records):
        self.source.write_text(json.dumps({"records": records}))

    def verify(self):
        return adoption.verified_records(self.app, self.source)

    def test_exact_receipts_revalidated_at_both_contexts_without_rewriting(self):
        before = self.source.read_bytes()
        selected = self.verify()
        self.assertEqual(selected, self.records)
        self.assertEqual(self.source.read_bytes(), before)
        self.app.uzu_model_records.assert_called_once_with(self.records, "this-mac")
        contexts = [call.args[0]["context"] for call in self.app.calibration_plan.call_args_list]
        self.assertEqual(contexts, [65536, 131072])
        selected[0]["originalEvidence"]["unchanged"] = False
        self.assertTrue(self.records[0]["originalEvidence"]["unchanged"])
        self.assertEqual(self.source.read_bytes(), before)

    def test_each_runtime_identity_component_must_match(self):
        for name in ("UZU_RUNTIME_RELEASE_BINARY_SHA256", "UZU_RUNTIME_RELEASE_BINARY_SIZE",
                     "UZU_RUNTIME_SOURCE_PATCH_SHA256", "UZU_RUNTIME_TAG"):
            with self.subTest(name=name), patch.object(self.app, name, "different"):
                with self.assertRaisesRegex(ValueError, "not pinned"):
                    self.verify()
        self.app.calibration_plan.assert_not_called()

    def test_installed_runtime_must_be_ready_not_just_same_version(self):
        self.app.uzu_runtime_contract.return_value = {"ready": False}
        with self.assertRaisesRegex(ValueError, "not safely installed"):
            self.verify()
        self.app.calibration_plan.assert_not_called()

    def test_missing_and_duplicate_receipts_rejected(self):
        for records in (self.records[:1], self.records + self.records[:1],
                        [self.records[0], self.records[0]]):
            with self.subTest(ids=[record["id"] for record in records]):
                self.write_records(records)
                with self.assertRaisesRegex(ValueError, "missing or duplicated"):
                    self.verify()

    def test_other_hardware_or_wrong_context_cannot_be_adopted(self):
        for name, value in (("hardwareFingerprint", "other-mac"), ("contextMin", 32768)):
            with self.subTest(field=name):
                records = copy.deepcopy(self.records)
                records[0][name] = value
                self.write_records(records)
                with self.assertRaisesRegex(ValueError, "hardware and measured context"):
                    self.verify()

    def test_current_planner_must_accept_each_saved_qualification(self):
        for rejected in ({"action": "measure", "evidence": {"qualified": True}},
                         {"action": "apply-existing", "evidence": {"qualified": False}}):
            with self.subTest(plan=rejected):
                self.app.calibration_plan.side_effect = [
                    {"action": "apply-existing", "evidence": {"qualified": True}}, rejected,
                ]
                with self.assertRaisesRegex(ValueError, "131072-token qualification"):
                    self.verify()

    def test_unrelated_receipts_are_not_imported(self):
        self.write_records(self.records + [{"id": "unrelated-private-result"}])
        self.assertEqual(self.verify(), self.records)


if __name__ == "__main__":
    unittest.main()
