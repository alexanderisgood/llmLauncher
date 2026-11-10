"""Opt-in actual Metal proof for exact resident expert reuse during prefill."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
NATIVE_PYTHON = os.environ.get("LLM_LAUNCHER_KOLIBRI_PYTHON")


@unittest.skipUnless(NATIVE_PYTHON,"Set LLM_LAUNCHER_KOLIBRI_PYTHON for bounded synthetic native Q6 validation")
class NativePrefillTests(unittest.TestCase):
    def test_resident_reuse_preserves_q6_rows_router_order_and_warm_cache(self):
        result = subprocess.run([NATIVE_PYTHON,str(ROOT / "tests/fixtures/kolibri_native_sweep_check.py")],
                                capture_output=True,text=True,timeout=60,check=False)
        self.assertEqual(result.returncode,0,result.stderr)
        evidence = json.loads(result.stdout)
        self.assertFalse(evidence["engineInferenceMeasured"])
        self.assertLess(evidence["peakMlxMemoryBytes"],512 * 2**20)
        checks = {item["scenario"]:item for item in evidence["checks"]}
        self.assertEqual(set(checks),{"cold","interleaved-resident","contiguous-resident",
                                     "all-resident","batched-count-skew","no-warm","wide-batch","s3fifo-legacy"})
        for item in checks.values():
            self.assertTrue(item["bitwiseQ6Output"])
            self.assertTrue(item["sameWarmExpertOrder"])
            self.assertLessEqual(item["cachedBytes"],item["baselineBytes"])
        self.assertEqual(checks["all-resident"]["cachedBytes"],0)
        self.assertEqual(checks["interleaved-resident"]["cachedBytes"] * 2,
                         checks["interleaved-resident"]["baselineBytes"])
        self.assertEqual(checks["s3fifo-legacy"]["cachedBytes"],checks["s3fifo-legacy"]["baselineBytes"])


if __name__ == "__main__":
    unittest.main()
