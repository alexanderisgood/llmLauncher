"""Invalid native settings must fail before catalog/auth materialization."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import launcher


class OmlxPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix="omlx-preflight-")
        self.root=Path(self.temporary.name)
        self.model={"id":"generated-qwen","name":"Generated Qwen","path":str(self.root/"model"),
            "templateReasoningEfforts":["low"],"backends":{"omlx":{}}}
        self.cap={"mtp":False,"runtimeVersion":"0.6.4"}
    def tearDown(self):self.temporary.cleanup()
    def plan(self,options,reasoning="auto"):
        return launcher.LaunchPlan(run_id="generated-plan",backend="omlx",client="pi",model=copy.deepcopy(self.model),
            project=str(self.root),context=8192,output=1024,reasoning=reasoning,port=18765,
            mode="custom",options=options,run_dir=self.root/"run")
    def assert_no_materialization(self,plan,pattern):
        with mock.patch.object(launcher,"omlx_expert_offload_options",return_value=None), \
                mock.patch.object(launcher.secrets,"token_urlsafe",side_effect=AssertionError("secret generated")), \
                mock.patch.object(launcher.secrets,"token_hex",side_effect=AssertionError("secret generated")), \
                mock.patch.object(launcher,"atomic_json",side_effect=AssertionError("settings written")):
            with self.assertRaisesRegex(ValueError,pattern):launcher.build_omlx(plan,self.cap)
        self.assertFalse(plan.run_dir.exists())
        self.assertFalse(plan.secrets)
    def test_invalid_acceleration_kv_ane_burst_or_template_effort_creates_nothing(self):
        for options,reasoning,message in [
            ({"acceleration":"invalid"},"auto","acceleration"),
            ({"acceleration":"off","kv":"invalid"},"auto","KV"),
            ({"acceleration":"off","anePrefill":"invalid"},"auto","ANE"),
            ({"acceleration":"off","burst":"invalid"},"auto","burst"),
            ({"acceleration":"off"},"high","reasoning effort")]:
            with self.subTest(options=options,reasoning=reasoning):
                self.assert_no_materialization(self.plan(options,reasoning),message)
    def test_late_dflash_precision_and_adapter_failures_are_preflight_only(self):
        self.cap.update(dflash=True,dflashVersion="2",dflashBlockSize=4,dflashMaxBlockSize=8,
            dflashRuntimeVersion="0.6.4",dflashDraftPath=str(self.root/"draft"))
        with mock.patch.object(launcher,"dflash2_capability_valid",return_value=True), \
                mock.patch.object(launcher,"omlx_plan_runtime_version",return_value="0.6.4"):
            for option,value,message in [("dflashDraftQuant","invalid","precision"),("dflashVerify","invalid","verification")]:
                self.assert_no_materialization(self.plan({"acceleration":"dflash",option:value}),message)
            with mock.patch.object(launcher,"omlx_runtime_python",return_value=None):
                self.assert_no_materialization(self.plan({"acceleration":"dflash"}),"runtime Python")


if __name__=="__main__":unittest.main()
