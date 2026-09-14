"""Sleep and monitoring gaps must not become a saved speed recommendation."""
import unittest
from unittest import mock

import launcher


class BenchmarkTimingContinuityTests(unittest.TestCase):
    def samples_at(self, clocks):
        seen = []

        def invariant(value):
            seen.append(value)
            if value.get("timingDiscontinuity"):
                raise launcher.QualificationSafetyFailure(value["timingDiscontinuity"])

        sampler = launcher.BenchmarkTelemetrySampler(invariant_callback=invariant)
        with mock.patch.object(launcher, "apple_resource_snapshot", return_value={}):
            for monotonic, wall in clocks:
                with mock.patch.object(launcher.time, "monotonic", return_value=monotonic), \
                        mock.patch.object(launcher.time, "time", return_value=wall):
                    sampler._sample()
        return sampler, seen

    def test_normal_sampling_retains_continuity(self):
        sampler, seen = self.samples_at([(100, 1000), (101, 1001), (103, 1003)])
        self.assertIsNone(sampler.violation)
        self.assertFalse(sampler.stop_event.is_set())
        self.assertFalse(any(value.get("timingDiscontinuity") for value in seen))

    def test_sleep_detected_even_when_monotonic_clock_excludes_suspend(self):
        sampler, seen = self.samples_at([(100, 1000), (101, 22601)])
        self.assertIn("slept", sampler.violation)
        self.assertTrue(sampler.stop_event.is_set())
        self.assertIn("timingDiscontinuity", seen[-1])

    def test_monitoring_pause_and_wall_clock_jump_are_not_trusted(self):
        for clocks in ([(100, 1000), (131, 1031)],
                       [(100, 1000), (101, 900)],
                       [(100, 1000), (99, 1001)]):
            with self.subTest(clocks=clocks):
                sampler, _ = self.samples_at(clocks)
                self.assertIsNotNone(sampler.violation)


if __name__ == "__main__":
    unittest.main()
