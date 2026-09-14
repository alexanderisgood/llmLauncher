import io
import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

import launcher


class SessionActivityIdentity(unittest.TestCase):
    def setUp(self):
        self.manager = launcher.RunManager()
        self.first = self.plan("first", 18001)
        self.second = self.plan("second", 18002)
        self.install(self.first)

    @staticmethod
    def plan(run_id, port):
        return launcher.LaunchPlan(run_id=run_id, backend="uzu", client="chat",
            model={"id":run_id, "name":run_id}, project="/tmp", context=16384,
            output=4096, reasoning="medium", port=port, mode="ar", options={})

    def install(self, plan):
        with self.manager.lock:
            self.manager.plan = plan
            self.manager.session_proxy_port = plan.port + 100
            self.manager.session_proxy_control_key = f"private-{plan.run_id}"
            self.manager.state = {"phase":"running", "run":plan.public(), "events":[]}

    @staticmethod
    def activity(owner):
        return {"state":"busy", "lanes":1, "activeCount":1, "queuedCount":0,
            "active":[{"id":f"request-{owner.run_id}", "surfaceId":owner.run_id}],
            "queued":[], "recent":[], "surfaces":[{"id":owner.run_id}],
            "idleSeconds":0, "coverage":{"allLauncherSurfaces":True}}

    def during_blocked_call(self, operation, entered, release, switch):
        # A real worker guarantees the controller lock is not held during I/O.
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(operation)
            try:
                self.assertTrue(entered.wait(2), "status never reached the blocked I/O")
                switch()
            finally:
                release.set()
            return future.result(timeout=2)

    def assert_current_without_old_metrics(self, result, snapshot_method=None):
        activity = result if snapshot_method is None else result["activity"]
        if snapshot_method:
            key = "run" if snapshot_method == "snapshot" else "session"
            self.assertEqual(result[key]["runId"], self.second.run_id)
        self.assertEqual(activity["active"], [])
        self.assertEqual(activity["recent"], [])
        self.assertFalse(activity["coverage"]["allLauncherSurfaces"])
        self.assertFalse(activity["idlePolicy"]["eligible"])
        self.assertTrue(activity["engineResident"])
        self.assertNotIn("request-first", json.dumps(result))
        self.assertNotIn("private-", json.dumps(result))

    def test_blocked_relay_switch_drops_old_data_and_skips_old_engine(self):
        for method in ("request_activity", "snapshot", "hub_snapshot"):
            with self.subTest(method=method):
                self.install(self.first)
                entered, release = threading.Event(), threading.Event()

                def response(request, **_kwargs):
                    self.assertEqual(request.full_url, "http://127.0.0.1:18101/__launcher/status")
                    self.assertEqual(request.get_header("Authorization"), "Bearer private-first")
                    entered.set()
                    self.assertTrue(release.wait(2))
                    return io.BytesIO(json.dumps(self.activity(self.first)).encode())

                with mock.patch.object(launcher.urllib.request, "urlopen", side_effect=response) as fetch, \
                     mock.patch.object(launcher, "uzu_prompt_activity") as native:
                    result = self.during_blocked_call(getattr(self.manager, method), entered,
                        release, lambda: self.install(self.second))
                fetch.assert_called_once()
                native.assert_not_called()
                self.assert_current_without_old_metrics(result, None if method == "request_activity" else method)

    def test_switch_after_activity_collection_is_checked_by_both_snapshots(self):
        collect = self.manager.request_activity
        for method in ("snapshot", "hub_snapshot"):
            with self.subTest(method=method):
                self.install(self.first)

                def switch_after_collection(**kwargs):
                    activity = collect(**kwargs)
                    self.assertEqual(activity["active"][0]["id"], "request-first")
                    self.install(self.second)
                    return activity

                with mock.patch.object(self.manager, "_session_proxy_api", return_value=self.activity(self.first)), \
                     mock.patch.object(launcher, "uzu_prompt_activity", side_effect=lambda _plan, activity: activity), \
                     mock.patch.object(self.manager, "request_activity", side_effect=switch_after_collection):
                    result = getattr(self.manager, method)()
                self.assert_current_without_old_metrics(result, method)

    def test_switch_during_native_telemetry_drops_old_speed_and_context(self):
        for method in ("request_activity", "snapshot", "hub_snapshot"):
            with self.subTest(method=method):
                self.install(self.first)
                entered, release = threading.Event(), threading.Event()

                def native(owner, activity):
                    self.assertIs(owner, self.first)
                    entered.set()
                    self.assertTrue(release.wait(2))
                    activity["active"][0].update(runtimeTokensPerSecond=123, contextTokens=9000)
                    return activity

                with mock.patch.object(self.manager, "_session_proxy_api", return_value=self.activity(self.first)), \
                     mock.patch.object(launcher, "uzu_prompt_activity", side_effect=native):
                    result = self.during_blocked_call(getattr(self.manager, method), entered,
                        release, lambda: self.install(self.second))
                self.assert_current_without_old_metrics(result, None if method == "request_activity" else method)
                self.assertNotIn("runtimeTokensPerSecond", json.dumps(result))
                self.assertNotIn("contextTokens", json.dumps(result))

    def test_captured_target_cannot_be_redirected_to_new_relay(self):
        with self.manager.lock:
            target = self.manager._activity_target_unlocked()
        self.install(self.second)
        with mock.patch.object(launcher.urllib.request, "urlopen") as fetch:
            with self.assertRaisesRegex(ValueError, "route changed"):
                self.manager._session_proxy_api("GET", "/__launcher/status", _target=target)
        fetch.assert_not_called()

    def test_same_plan_relay_replacement_or_stop_invalidates_activity(self):
        for change in ("port", "key", "phase"):
            with self.subTest(change=change):
                self.install(self.first)

                def response(_request, **_kwargs):
                    with self.manager.lock:
                        if change == "port":
                            self.manager.session_proxy_port += 1
                        elif change == "key":
                            self.manager.session_proxy_control_key = "replacement-key"
                        else:
                            self.manager.state["phase"] = "idle"
                    return io.BytesIO(json.dumps(self.activity(self.first)).encode())

                with mock.patch.object(launcher.urllib.request, "urlopen", side_effect=response), \
                     mock.patch.object(launcher, "uzu_prompt_activity") as native:
                    activity = self.manager.request_activity()
                self.assertEqual(activity["active"], [])
                self.assertEqual(activity["engineResident"], change != "phase")
                self.assertFalse(activity["idlePolicy"]["eligible"])
                native.assert_not_called()

    def test_stable_owner_preserves_metrics_and_applies_current_idle_policy(self):
        original = self.activity(self.first)

        def response(_request, **_kwargs):
            with self.manager.lock:
                self.manager.idle_timeout_minutes = 15
            return io.BytesIO(json.dumps(original).encode())

        def native(_owner, activity):
            activity["active"][0]["runtimeTokensPerSecond"] = 23
            return activity

        with mock.patch.object(launcher.urllib.request, "urlopen", side_effect=response) as fetch, \
             mock.patch.object(launcher, "uzu_prompt_activity", side_effect=native):
            result = self.manager.snapshot()
        fetch.assert_called_once()
        self.assertEqual(result["run"]["runId"], self.first.run_id)
        self.assertEqual(result["activity"]["active"][0]["runtimeTokensPerSecond"], 23)
        self.assertTrue(result["activity"]["idlePolicy"]["eligible"])
        self.assertEqual(result["activity"]["idlePolicy"]["timeoutMinutes"], 15)
        self.assertNotIn("private-first", json.dumps(result))
        self.assertEqual(original, self.activity(self.first))


if __name__ == "__main__":
    unittest.main()
