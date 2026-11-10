"""Generated Root integration witnesses; no model/service/settings operations."""
import copy
import io
import json
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest import mock

import launcher
import operation_contracts
from tests.test_run_lifecycle import generated_plan, manager, resident


class GeneratedOwner:
    def __init__(self):
        self.lock = threading.RLock()
        self.lifecycle_lock = threading.RLock()
        self.cancel_event = threading.Event()
        self.plan = self.process = None
        self.codex_proxy_port = self.session_proxy_port = None
        self.llamacpp_safety_violation = None
        self.attachments = {}
        self.state = {"phase": "idle", "message": "Generated owner"}
        self.stops = []
        self.reject = self.accept_then_fail = False

    def snapshot(self):
        return copy.deepcopy(self.state)

    def start(self, plan):
        if self.reject:
            raise ValueError("Generated busy rejection")
        self.plan = plan
        self.cancel_event = threading.Event()
        self.state["phase"] = "starting"
        if self.accept_then_fail:
            raise RuntimeError("Generated failure after admission")

    def stop(self, *, expected_plan, expected_cancel_event):
        with self.lock:
            if self.plan is expected_plan and self.cancel_event is expected_cancel_event:
                self.stops.append((expected_plan, expected_cancel_event))
                self.cancel_event.set()
                self.plan = None
                self.state["phase"] = "idle"


class OperationBridgeTests(unittest.TestCase):
    def test_current_and_admitted_distinguish_rejection_acceptance_and_replaced_epoch(self):
        with tempfile.TemporaryDirectory(prefix="operation-root-owner-") as directory:
            plan = generated_plan(Path(directory), purpose="route-check")
            owner = GeneratedOwner()
            bridge = launcher._TemporaryOperationOwner(owner)
            owner.reject = True
            with self.assertRaises(ValueError): bridge.port().start(plan)
            self.assertFalse(bridge.admitted(plan))
            owner.reject = False
            owner.accept_then_fail = True
            with self.assertRaises(RuntimeError): bridge.port().start(plan)
            self.assertTrue(bridge.admitted(plan))
            self.assertTrue(bridge.current(plan))
            epoch = owner.cancel_event
            owner.cancel_event = threading.Event()
            self.assertFalse(bridge.current(plan))
            bridge.port().stop(expected_plan=plan)
            self.assertEqual(owner.stops, [])
            self.assertFalse(epoch.is_set())

    def test_dispatch_revalidates_epoch_during_connect_and_releases_lock_for_response(self):
        import urllib.request
        with tempfile.TemporaryDirectory(prefix="operation-root-dispatch-") as directory:
            plan = generated_plan(Path(directory), purpose="route-check")
            owner = GeneratedOwner()
            bridge = launcher._TemporaryOperationOwner(owner)
            bridge.port().start(plan)
            calls = []
            class Connection:
                sock = None
                def __init__(self, *_args, **_kwargs): pass
                def connect(self): owner.cancel_event = threading.Event()
                def request(self, *_args, **_kwargs): calls.append("sent")
                def close(self): calls.append("closed")
            bridge.dispatcher.connection_factory = Connection
            with self.assertRaises(launcher.LaunchCancelled):
                bridge.port().open_request(plan, urllib.request.Request(f"http://127.0.0.1:{plan.port}/v1/chat/completions"), 900)
            self.assertEqual(calls, ["closed"])
            bridge.port().start(plan)
            stopped = threading.Event()
            class SuccessfulConnection(Connection):
                def connect(self): pass
                def getresponse(self):
                    worker = threading.Thread(target=lambda: (bridge.port().stop(expected_plan=plan), stopped.set()))
                    worker.start()
                    if not stopped.wait(1):
                        raise AssertionError("State lock held across response wait")
                    worker.join(1)
                    return types.SimpleNamespace(status=200, close=lambda: None)
            bridge.dispatcher.connection_factory = SuccessfulConnection
            with bridge.port().open_request(plan, urllib.request.Request(f"http://127.0.0.1:{plan.port}/v1/chat/completions"), 900): pass
            self.assertTrue(stopped.is_set())

    def test_session_lease_rejects_same_plan_new_epoch_before_surface_action(self):
        with tempfile.TemporaryDirectory(prefix="operation-root-lease-") as directory:
            plan = generated_plan(Path(directory))
            owner = GeneratedOwner()
            owner.start(plan)
            owner.attach_surface = mock.Mock()
            owner.restart_agent_console = mock.Mock()
            bridge = launcher._SessionResidenceAdapter(owner)
            with launcher.SESSION_OPERATION_LOCK:
                lease = bridge.acquire(plan.run_id)  # HTTP start fence is reentrant.
            owner.cancel_event = threading.Event()
            for action in (bridge.leased_snapshot, lambda value: bridge.attach_leased(value, {}),
                           lambda value: bridge.restart_leased(value, {})):
                with self.assertRaises(launcher.LaunchCancelled): action(lease)
            owner.attach_surface.assert_not_called()
            owner.restart_agent_console.assert_not_called()
            bridge.release(lease)
            self.assertEqual(bridge.leases, {})

    def test_native_attachment_witness_rejects_before_any_private_materialization(self):
        with tempfile.TemporaryDirectory(prefix="operation-native-attach-") as directory:
            root = Path(directory)
            value = resident(manager(root=root), generated_plan(root))
            original = value.cancel_event
            value.cancel_event = threading.Event()
            value._build_attachment_launch_plan = mock.Mock()
            with self.assertRaises(launcher.LaunchCancelled):
                value.attach_surface({"ownerRunId": value.plan.run_id, "client": "chat"},
                    expected_plan=value.plan, expected_cancel_event=original)
            value._build_attachment_launch_plan.assert_not_called()
            self.assertEqual(list(root.iterdir()), [])

    def test_native_restart_witness_rejects_before_status_argv_or_process_mutation(self):
        with tempfile.TemporaryDirectory(prefix="operation-native-restart-") as directory:
            root = Path(directory)
            plan = generated_plan(root, client="pi")
            value = resident(manager(root=root), plan)
            console = types.SimpleNamespace(owner_run_id=plan.run_id, plan=plan,
                process=types.SimpleNamespace(poll=lambda: 0), state="stopped", structured=False)
            value.agent_consoles[plan.run_id] = console
            epoch = value.cancel_event
            value.cancel_event = threading.Event()
            value._launch_agent_console = mock.Mock()
            before = value.attachments[plan.run_id].public(), copy.deepcopy(plan.client_argv)
            with self.assertRaises(launcher.LaunchCancelled):
                value.restart_agent_console({"ownerRunId": plan.run_id, "surfaceId": plan.run_id},
                    expected_plan=plan, expected_cancel_event=epoch)
            value._launch_agent_console.assert_not_called()
            self.assertEqual(before, (value.attachments[plan.run_id].public(), plan.client_argv))

    def test_activity_epoch_remains_private_and_rejects_equal_route_fields(self):
        with tempfile.TemporaryDirectory(prefix="operation-native-activity-") as directory:
            root = Path(directory)
            value = resident(manager(root=root), generated_plan(root))
            target = value._activity_target_unlocked()
            self.assertTrue(value._activity_target_matches_unlocked(target))
            self.assertNotIn("private-fixture", repr(target))
            self.assertNotIn("Event", repr(target))
            value.cancel_event = threading.Event()
            self.assertFalse(value._activity_target_matches_unlocked(target))
            with mock.patch("urllib.request.urlopen") as upstream:
                with self.assertRaises(ValueError):
                    value.register_session_surface(value.plan,
                        types.SimpleNamespace(run_id="old-surface", client="chat", secrets={"clientApiKey": "old-surface-key"},
                            sampling_contract={}, sampling_enforcement={}), _target=target)
                value.unregister_session_surface("old-surface", _target=target)
                upstream.assert_not_called()

    def test_default_registration_and_cleanup_preserve_wire_body_and_release_state_lock(self):
        with tempfile.TemporaryDirectory(prefix="operation-native-relay-") as directory:
            root = Path(directory)
            value = resident(manager(root=root), generated_plan(root))
            plan = generated_plan(root)
            plan.sampling_contract = {"mode": "model"}
            plan.sampling_enforcement = {"source": "generated"}
            requests = []
            class Response(io.BytesIO):
                def __enter__(self): return self
                def __exit__(self, *_args): self.close()
            def open_request(request, *, timeout):
                free = threading.Event()
                def probe():
                    with value.lock: free.set()
                worker = threading.Thread(target=probe)
                worker.start()
                self.assertTrue(free.wait(1), "Response wait must not retain state lock")
                worker.join(1)
                requests.append((request.full_url, request.get_method(), request.get_header("Authorization"), json.loads(request.data), timeout))
                return Response(b'{"ok":true}')
            with mock.patch("urllib.request.urlopen", side_effect=open_request):
                value.register_session_surface(value.plan, plan)
                value.unregister_session_surface(plan.run_id)
            self.assertEqual(requests, [
                (f"http://127.0.0.1:{plan.client_port}/__launcher/surfaces", "POST", "Bearer private-fixture-control",
                 {"action":"register", "surface":{"id":plan.run_id,"client":plan.client,"key":"private-fixture-surface",
                    "samplingContract":{"mode":"model"},"samplingEnforcement":{"source":"generated"}}}, 2.0),
                (f"http://127.0.0.1:{plan.client_port}/__launcher/surfaces", "POST", "Bearer private-fixture-control",
                 {"action":"unregister","surfaceId":plan.run_id}, 2.0),
            ])

    def test_failed_old_attachment_cleanup_never_contacts_replacement_relay(self):
        with tempfile.TemporaryDirectory(prefix="operation-native-cleanup-") as directory:
            root = Path(directory)
            owner = generated_plan(root, client="pi")
            value = resident(manager(root=root), owner)
            epoch = value.cancel_event
            target = {"owner":owner,"cancelEvent":epoch,"client":"pi"}
            overlay = generated_plan(root, client="pi")
            overlay.sampling_contract = overlay.sampling_enforcement = {}
            value._validated_attachment_target = mock.Mock(return_value=target)
            value._build_attachment_launch_plan = mock.Mock(return_value=overlay)
            def changed(*_args, **_kwargs):
                value.cancel_event = threading.Event()
                value.session_proxy_control_key = "new-private-relay-key"
                raise launcher.LaunchCancelled("Generated replacement after registration")
            value._launch_client = changed
            requests = []
            class Response(io.BytesIO):
                def __enter__(self): return self
                def __exit__(self, *_args): self.close()
            with mock.patch("urllib.request.urlopen", side_effect=lambda request, **_kwargs: (requests.append(request.get_header("Authorization")), Response(b'{"ok":true}'))[1]):
                with self.assertRaises(launcher.LaunchCancelled): value.attach_surface({})
            self.assertEqual(requests, ["Bearer private-fixture-control"])

    def test_unpublished_overlay_disposes_credentials_preserving_files_and_symlink_targets(self):
        import os
        for accepted in (False, True):
            with self.subTest(accepted=accepted), tempfile.TemporaryDirectory(prefix="operation-overlay-private-") as directory:
                root = Path(directory)
                owner = generated_plan(root, client="omp")
                value = resident(manager(root=root), owner)
                overlay_dir = root / "attachments" / "generated-overlay"
                overlay_dir.mkdir(parents=True, mode=0o700)
                overlay = generated_plan(overlay_dir, client="omp")
                overlay.run_id = "generated-overlay"
                overlay.sampling_contract = overlay.sampling_enforcement = {}
                config = overlay_dir / "omp-settings.json"
                config.write_text(json.dumps({"apiKey":"private-fixture-surface"}))
                config.chmod(0o600)
                unrelated = overlay_dir / "user-note.txt"
                unrelated.write_text("Preserved unrelated file")
                foreign = root / "foreign-private.json"
                foreign.write_text("Preserved symlink target")
                (overlay_dir / "codex-settings.json").symlink_to(foreign)
                value._validated_attachment_target = mock.Mock(return_value={
                    "owner":owner,"cancelEvent":value.cancel_event,"client":"omp",
                })
                value._build_attachment_launch_plan = mock.Mock(return_value=overlay)
                def rejected(*_args, **_kwargs):
                    if accepted:
                        value.attachments[overlay.run_id] = launcher.SurfaceAttachment(
                            owner.run_id, overlay, status="running")
                    value.cancel_event = threading.Event()
                    raise launcher.LaunchCancelled("Generated replacement")
                value._launch_client = rejected
                class Response(io.BytesIO):
                    def __enter__(self): return self
                    def __exit__(self, *_args): self.close()
                with mock.patch("urllib.request.urlopen", return_value=Response(b'{"ok":true}')), \
                        mock.patch("run_lifecycle.uuid.uuid4", return_value=overlay.run_id):
                    with self.assertRaises(launcher.LaunchCancelled): value.attach_surface({})
                self.assertEqual(config.exists(), accepted)
                if accepted:
                    self.assertEqual(os.stat(config).st_mode & 0o777, 0o600)
                    self.assertEqual(overlay.secrets["clientApiKey"], "private-fixture-surface")
                else:
                    self.assertNotIn("clientApiKey", overlay.secrets)
                self.assertEqual(unrelated.read_text(), "Preserved unrelated file")
                self.assertEqual(foreign.read_text(), "Preserved symlink target")

    def test_current_policy_and_callbacks_remain_live_without_cached_admission(self):
        old = launcher.ROUTE_CHECK_MAX_TOKENS
        with mock.patch.object(launcher, "ROUTE_CHECK_MAX_TOKENS", old + 1):
            self.assertEqual(launcher._route_check_policy().max_tokens, old + 1)
        services = launcher._route_check_services()
        with mock.patch.object(launcher, "normalized_request", return_value="fresh") as callback:
            self.assertEqual(services.normalized_request({}, []), "fresh")
            callback.assert_called_once_with({}, [])

    def test_complete_root_helper_and_constructor_signatures_remain_compatible(self):
        import ast
        import ane_jobs, route_check_jobs, session_set_jobs
        current = {node.name:node for node in ast.parse(Path(launcher.__file__).read_text()).body
                   if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        count = 0
        for filename in ("route_check_jobs_legacy.py", "ane_jobs_legacy.py", "session_set_jobs_legacy.py"):
            for node in ast.parse((Path(__file__).with_name("fixtures") / filename).read_text()).body:
                if isinstance(node, ast.FunctionDef):
                    self.assertEqual(ast.dump(node.args, include_attributes=False),
                                     ast.dump(current[node.name].args, include_attributes=False), node.name)
                    self.assertEqual(len(current[node.name].body), 1)
                    self.assertIsInstance(current[node.name].body[0], ast.Return)
                    count += 1
                elif isinstance(node, ast.ClassDef):
                    old = next(item for item in node.body if isinstance(item, ast.FunctionDef) and item.name == "__init__")
                    new = next(item for item in current[node.name].body if isinstance(item, ast.FunctionDef) and item.name == "__init__")
                    self.assertEqual(ast.dump(old.args, include_attributes=False),
                                     ast.dump(new.args, include_attributes=False), node.name)
        self.assertEqual(count, 16)
        for module, names in ((route_check_jobs, ("RouteCheckManager",)),
                              (ane_jobs, ("ANETunerManager", "ANEFP16CloneManager")),
                              (session_set_jobs, ("SessionSetRunner",))):
            self.assertIn(Path(module.__file__).resolve(), launcher.CONTROLLER_SOURCE_PATHS)
            for name in names:
                self.assertTrue(issubclass(getattr(launcher, name), getattr(module, name)))
        self.assertIn(Path(operation_contracts.__file__).resolve(), launcher.CONTROLLER_SOURCE_PATHS)

    def test_all_four_original_manager_method_signatures_and_static_call_shapes(self):
        import ast, inspect
        from tests.helpers.operation_jobs_harness import Fixture, SessionFixture
        fixture = Fixture()
        originals = {**fixture.legacy("route_check_jobs"), **fixture.legacy("ane_jobs"),
                     **SessionFixture().legacy()}
        exceptions = {("SessionSetRunner", "_wait_for_owner"), ("SessionSetRunner", "_worker")}
        checked = set()
        for filename in ("route_check_jobs_legacy.py", "ane_jobs_legacy.py", "session_set_jobs_legacy.py"):
            for node in ast.parse((Path(__file__).with_name("fixtures") / filename).read_text()).body:
                if not isinstance(node, ast.ClassDef): continue
                old_class, new_class = originals[node.name], getattr(launcher, node.name)
                for method in (item for item in node.body if isinstance(item, ast.FunctionDef)):
                    name = method.name
                    old = inspect.signature(getattr(old_class, name)).parameters
                    new = inspect.signature(getattr(new_class, name)).parameters
                    if (node.name, name) in exceptions:
                        # Only the documented private worker/wait transport adds
                        # an opaque lease; old argument names/defaults stay exact.
                        self.assertEqual(new["lease"].kind, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                        self.assertIs(new["lease"].default, inspect.Parameter.empty)
                        new = {key:value for key,value in new.items() if key != "lease"}
                    self.assertEqual([(p.name,p.kind,p.default) for p in old.values()],
                                     [(p.name,p.kind,p.default) for p in new.values()], (node.name,name))
                    checked.add((node.name,name))
        self.assertEqual({name for name,_method in checked},
            {"RouteCheckManager","ANETunerManager","ANEFP16CloneManager","SessionSetRunner"})
        self.assertGreater(len(checked), 35)

    def test_static_and_instance_engine_log_preserve_tail_whitespace_and_no_log(self):
        with tempfile.TemporaryDirectory(prefix="operation-static-log-") as directory:
            root = Path(directory)
            text = "prefix\n" + "🦙 entry\r\n" * 260_000 + " end  \n"
            (root / "engine.log").write_bytes(text.encode())
            expected = text.replace("\r\n", "\n")[-2_000_000:]
            plan = types.SimpleNamespace(run_dir=root)
            value = launcher.ANETunerManager(GeneratedOwner())
            with mock.patch.object(launcher, "read_log_tail", wraps=launcher.read_log_tail) as reader:
                self.assertEqual(launcher.ANETunerManager._read_engine_log(plan), expected)
                self.assertEqual(value._read_engine_log(plan), expected)
                self.assertEqual(reader.call_args_list, [mock.call(root / "engine.log", 2_000_000)] * 2)
                self.assertEqual(launcher.ANETunerManager._read_engine_log(types.SimpleNamespace(run_dir=None)), "")
                self.assertEqual(value._read_engine_log(types.SimpleNamespace(run_dir=None)), "")
                self.assertEqual(reader.call_count, 2)

    def test_static_clone_validation_and_idle_state_use_named_defaults_bound_instances_retain_policy(self):
        from tests.helpers.operation_jobs_harness import CloneFixture
        with tempfile.TemporaryDirectory(prefix="operation-static-clone-") as directory:
            fixture = CloneFixture(directory)
            _model, plan = fixture.clone_manager().planner.build_ane_fp16_clone_plan(
                {"modelId":fixture.plan.model["id"]}, [fixture.plan.model])
            stage = Path(directory) / "generated-stage"
            fixture.spawn(["generated-converter", str(stage)])
            with mock.patch.object(launcher, "_ane_services", return_value=fixture.ane_services):
                value = launcher.ANEFP16CloneManager(fixture.run)
                before = value.snapshot()
                self.assertEqual(launcher.ANEFP16CloneManager._verify_clone(plan, stage),
                                 value._verify_clone(plan, stage))
                self.assertEqual(value.snapshot(), before)
                changed = {**plan, "modelFingerprint":"changed-generated-source"}
                for verify in (launcher.ANEFP16CloneManager._verify_clone, value._verify_clone):
                    with self.assertRaisesRegex(ValueError, "source checkpoint changed"):
                        verify(changed, stage)
            value = launcher.SessionSetRunner(GeneratedOwner())
            original = value._idle_state()
            self.assertEqual(launcher.SessionSetRunner._idle_state(), original)
            with mock.patch.object(launcher, "SESSION_SET_STATUS_VERSION", original["version"] + 1):
                self.assertEqual(launcher.SessionSetRunner._idle_state()["version"], original["version"] + 1)
                self.assertEqual(value._idle_state(), original)


if __name__ == "__main__":
    unittest.main()
