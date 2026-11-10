"""Presentation caching must save probes without changing launch or safety truth."""
from __future__ import annotations

import ctypes
import io
import os
import subprocess
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import controller_read_api
import launcher
import resource_telemetry
import runtime_probes
from controller_cache import SingleFlightCache


class SharedCacheTests(unittest.TestCase):
    def test_concurrent_refreshes_share_one_loader_and_return_detached_results(self):
        cache = SingleFlightCache(10)
        entered, release = threading.Event(), threading.Event()
        count = 0

        def load():
            nonlocal count
            count += 1
            entered.set()
            self.assertTrue(release.wait(2))
            return {"models": [{"name": "Qwen"}]}

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(cache.get, "models", load, refresh=True)]
            self.assertTrue(entered.wait(2))
            futures += [pool.submit(cache.get, "models", load, refresh=True) for _ in range(3)]
            # Read events deterministically instead of relying on scheduling sleeps.
            for _ in range(1000):
                if cache.statistics()["coalesced"] == 3:
                    break
                threading.Event().wait(0.001)
            release.set()
            results = [future.result(timeout=2) for future in futures]
        self.assertEqual(count, 1)
        self.assertEqual(cache.statistics()["coalesced"], 3)
        results[0]["models"][0]["name"] = "changed"
        self.assertEqual(results[1]["models"][0]["name"], "Qwen")
        self.assertEqual(cache.get("models", load)["models"][0]["name"], "Qwen")

    def test_ttl_refresh_and_entry_bound(self):
        clock = mock.Mock(return_value=10)
        cache = SingleFlightCache(2, maximum_entries=2, clock=clock)
        load = mock.Mock(side_effect=[1, 2, 3, 4, 5])
        self.assertEqual(cache.get("one", load), 1)
        self.assertEqual(cache.get("one", load), 1)
        clock.return_value = 12
        self.assertEqual(cache.get("one", load), 2)
        self.assertEqual(cache.get("one", load, refresh=True), 3)
        cache.get("two", load)
        cache.get("three", load)
        self.assertEqual(list(cache.entries), ["two", "three"])
        self.assertEqual(cache.statistics()["entries"], 2)

    def test_invalidating_an_inflight_read_cannot_republish_old_catalog(self):
        cache = SingleFlightCache(10)
        entered, release = threading.Event(), threading.Event()

        def old():
            entered.set()
            self.assertTrue(release.wait(2))
            return "old"

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(cache.get, "models", old)
            self.assertTrue(entered.wait(2))
            cache.clear()
            self.assertEqual(cache.get("models", lambda: "new"), "new")
            release.set()
            self.assertEqual(future.result(timeout=2), "old")
        self.assertEqual(cache.get("models", lambda: "wrong"), "new")

    def test_failed_probe_wakes_waiters_and_next_read_retries(self):
        cache = SingleFlightCache(10)
        entered, release = threading.Event(), threading.Event()

        def failing():
            entered.set()
            self.assertTrue(release.wait(2))
            raise OSError("runtime not ready")

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(cache.get, "runtime", failing)
            self.assertTrue(entered.wait(2))
            second = pool.submit(cache.get, "runtime", failing)
            for _ in range(1000):
                if cache.statistics()["coalesced"] == 1:
                    break
                threading.Event().wait(0.001)
            release.set()
            for future in (first, second):
                with self.assertRaisesRegex(OSError, "not ready"):
                    future.result(timeout=2)
        self.assertEqual(cache.get("runtime", lambda: "ready"), "ready")


class RuntimeProbeTests(unittest.TestCase):
    def setUp(self):
        runtime_probes.clear_probe_cache()
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.binary = Path(self.folder.name) / "engine"
        self.binary.write_text("executable-v1")
        self.environment = {"PATH": "/usr/bin"}
        self.runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, stdout="engine 1.0.0"))

    def probe(self, args=("--version",)):
        return runtime_probes.probe_output(str(self.binary), args, self.environment, self.runner)

    def test_repeated_version_and_help_requests_share_probes_until_binary_changes(self):
        self.probe()
        self.probe()
        self.runner.assert_called_once()
        replacement = self.binary.with_suffix(".new")
        replacement.write_text("executable-v2")
        replacement.replace(self.binary)
        self.probe()
        self.assertEqual(self.runner.call_count, 2)
        self.probe(("serve", "--help"))
        self.probe(("serve", "--help"))
        self.assertEqual(self.runner.call_count, 3)
        self.environment["PATH"] = "/different"
        self.probe()
        self.assertEqual(self.runner.call_count, 4)

    def test_failed_probes_and_missing_executables_are_not_cached(self):
        self.runner.return_value = subprocess.CompletedProcess([], 1, stdout="warning: recovering")
        self.assertEqual(self.probe(), (1, "warning: recovering"))
        self.probe()
        self.assertEqual(self.runner.call_count, 2)
        self.binary.unlink()
        self.runner.return_value = subprocess.CompletedProcess([], 0, stdout="engine 1.0.0")
        self.probe()
        self.probe()
        self.assertEqual(self.runner.call_count, 4)

    def test_symlink_target_replacement_invalidates_probe(self):
        link = self.binary.with_suffix(".link")
        link.symlink_to(self.binary.name)
        runtime_probes.probe_output(str(link), ("--version",), self.environment, self.runner)
        other = self.binary.with_suffix(".other")
        other.write_text("another-executable")
        link.unlink()
        link.symlink_to(other.name)
        runtime_probes.probe_output(str(link), ("--version",), self.environment, self.runner)
        self.assertEqual(self.runner.call_count, 2)


class PresentationCatalogTests(unittest.TestCase):
    def setUp(self):
        launcher.PRESENTATION_MODELS.clear()
        self.addCleanup(launcher.PRESENTATION_MODELS.clear)

    def test_views_reuse_catalog_explicit_rescan_refreshes_and_launch_scanner_is_fresh(self):
        scan = mock.Mock(side_effect=[[{"name": "Qwen"}], [{"name": "Kolibri"}], [{"name": "fresh"}]])
        with mock.patch.object(launcher, "scan_models", scan), \
                mock.patch.object(launcher, "model_roots", return_value=[]):
            first = launcher.presentation_models()
            first[0]["name"] = "modified by view"
            self.assertEqual(launcher.presentation_models(), [{"name": "Qwen"}])
            response = controller_read_api.read_response("/api/models", launcher, "token")
            self.assertEqual(response["models"], [{"name": "Kolibri"}])
            self.assertEqual(launcher.scan_models(), [{"name": "fresh"}])
        self.assertEqual(scan.call_count, 3)

    def test_model_mutation_uses_fresh_discovery_after_a_cached_preview(self):
        scan = mock.Mock(side_effect=[[{"name": "cached"}], [{"name": "fresh"}]])
        save = mock.Mock(return_value={"saved": True})
        handler = launcher.Handler.__new__(launcher.Handler)
        handler.path = "/api/profiles/save"
        handler.headers = {"X-Launcher-Token": "token", "Content-Length": "2"}
        handler.server = SimpleNamespace(csrf_token="token")
        handler.rfile = io.BytesIO(b"{}")
        handler.allowed, handler.json_response, handler.send_error = mock.Mock(return_value=True), mock.Mock(), mock.Mock()
        with mock.patch.object(launcher, "scan_models", scan), \
                mock.patch.object(launcher, "model_roots", return_value=[]), \
                mock.patch.object(launcher, "save_launch_profile", save):
            launcher.presentation_models()
            handler.do_POST()
        save.assert_called_once_with({}, [{"name": "fresh"}])
        handler.json_response.assert_called_once_with({"ok": True, "saved": True})
        self.assertEqual(scan.call_count, 2)

    def test_lifecycle_reads_are_live_and_unknown_routes_do_not_resolve(self):
        manager = mock.Mock()
        manager.snapshot.side_effect = [{"phase": "running"}, {"phase": "idle"}]
        services = SimpleNamespace(MANAGER=manager)
        self.assertEqual(controller_read_api.read_response("/api/status", services, "token"), {"phase": "running"})
        self.assertEqual(controller_read_api.read_response("/api/status", services, "token"), {"phase": "idle"})
        self.assertIsNone(controller_read_api.read_response("/index.html", services, "token"))


class NativeResourceTests(unittest.TestCase):
    def test_native_pressure_uses_same_kernel_percent_with_no_helper_or_cache(self):
        values = iter([81, 17])
        with mock.patch.object(resource_telemetry, "native_memory_free_percent", side_effect=lambda: next(values)), \
                mock.patch.object(resource_telemetry.subprocess, "run") as runner:
            first = resource_telemetry.apple_memory_pressure_state(lambda: 48 << 30)
            second = resource_telemetry.apple_memory_pressure_state(lambda: 48 << 30)
        runner.assert_not_called()
        self.assertEqual(first["freePercent"], 81.0)
        self.assertEqual(second["freePercent"], 17.0)
        self.assertEqual(first["memorySource"], "memorystatus_get_level")
        self.assertTrue(first["memoryAvailable"])

    def test_native_pressure_failure_retains_strict_command_fallback(self):
        raw = "The system has 51539607552.\nSystem-wide memory free percentage: 17%\n"
        with mock.patch.object(resource_telemetry.sys, "platform", "darwin"), \
                mock.patch.object(resource_telemetry, "native_memory_free_percent", return_value=None), \
                mock.patch.object(resource_telemetry.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout=raw)) as runner:
            pressure = resource_telemetry.apple_memory_pressure_state(lambda: 48 << 30)
        runner.assert_called_once()
        self.assertEqual(pressure["freePercent"], 17.0)
        self.assertTrue(pressure["memoryAvailable"])
        self.assertEqual(pressure["memorySource"], "memory_pressure -Q")

    def test_native_pressure_rejects_failed_and_out_of_range_readings(self):
        class NativeCall:
            argtypes = restype = None
            def __init__(self, returncode, percent):
                self.returncode, self.percent = returncode, percent
            def __call__(self, output):
                ctypes.cast(output, ctypes.POINTER(ctypes.c_uint32)).contents.value = self.percent
                return self.returncode
        for returncode, percent in ((0, 101), (-1, 80), (0, 0), (0, 100)):
            with self.subTest(returncode=returncode, percent=percent), \
                    mock.patch.object(resource_telemetry.sys, "platform", "darwin"), \
                    mock.patch.object(resource_telemetry.ctypes, "CDLL", return_value=SimpleNamespace(memorystatus_get_level=NativeCall(returncode, percent))):
                actual = resource_telemetry.native_memory_free_percent()
                self.assertEqual(actual, percent if returncode == 0 and percent <= 100 else None)

    def test_physical_memory_native_read_spawns_no_helper_and_is_live(self):
        values = iter([48 << 30, 64 << 30])
        with mock.patch.object(resource_telemetry, "native_sysctl_bytes", side_effect=lambda *args: next(values).to_bytes(8, os.sys.byteorder)), \
                mock.patch.object(resource_telemetry.subprocess, "run") as runner:
            self.assertEqual(resource_telemetry.physical_memory_bytes(), 48 << 30)
            self.assertEqual(resource_telemetry.physical_memory_bytes(), 64 << 30)
        runner.assert_not_called()

    def test_native_sysctl_rejects_growth_and_oversized_values(self):
        class NativeCall:
            argtypes = restype = None
            def __call__(self, name, buffer, size_ptr, new_value, new_size):
                size = ctypes.cast(size_ptr, ctypes.POINTER(ctypes.c_size_t))
                size.contents.value = 8 if buffer is None else 9
                return 0
        library = SimpleNamespace(sysctlbyname=NativeCall())
        with mock.patch.object(resource_telemetry.sys, "platform", "darwin"), \
                mock.patch.object(resource_telemetry.ctypes, "CDLL", return_value=library):
            self.assertIsNone(resource_telemetry.native_sysctl_bytes(b"hw.memsize", 8))
            self.assertIsNone(resource_telemetry.native_sysctl_bytes(b"hw.memsize", 4))

    def test_failed_sysctl_command_does_not_become_installed_memory(self):
        with mock.patch.object(resource_telemetry, "native_sysctl_bytes", return_value=None), \
                mock.patch.object(resource_telemetry.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, stdout="999")), \
                mock.patch.object(resource_telemetry.os, "sysconf", side_effect=[4096, 1024]):
            self.assertEqual(resource_telemetry.physical_memory_bytes(), 4 << 20)


if __name__ == "__main__":
    unittest.main()
