"""Full lifecycle extraction proof using private generated children and records.

No model, installed runtime, shared service, global configuration or durable
history is changed. The frozen class is test-only and never used by production.
"""
import ast
import copy
from contextlib import ExitStack
from dataclasses import FrozenInstanceError, fields, replace
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

import launcher
import run_lifecycle as lifecycle


FIXTURES = Path(__file__).parent / "fixtures"
METADATA = json.loads((FIXTURES / "run_lifecycle_legacy.json").read_text())


def load_fixture(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


legacy = load_fixture("frozen_run_lifecycle", FIXTURES / "run_lifecycle_legacy.py")


def policy():
    return lifecycle.LifecyclePolicy(**{
        item.name: getattr(launcher, item.name.upper())
        for item in fields(lifecycle.LifecyclePolicy)
    })


def services(*, root=None, overrides=None):
    overrides = overrides or {}
    groups = {}
    for name, callback_names in METADATA["groups"].items():
        values = {
            callback_name: overrides.get(callback_name) or
            (lambda *args, _name=callback_name, **kwargs: getattr(launcher, _name)(*args, **kwargs))
            for callback_name in callback_names
        }
        if name == "workspace":
            values["app_dir"] = lambda: root or launcher.APP_DIR
            values["state_dir"] = lambda: root or launcher.STATE_DIR
        if name == "runtime":
            values["binary"] = overrides.get("binary") or (lambda key: launcher.BINARIES.get(key))
            values["quitting"] = overrides.get("quitting") or (lambda: launcher.CONTROLLER_QUITTING.is_set())
        groups[name] = getattr(lifecycle, name.title() + "Services")(**values)
    return lifecycle.LifecycleServices(**groups)


def manager(*, root=None, overrides=None):
    return lifecycle.RunManager(policy(), services(root=root, overrides=overrides),
        lifecycle.LifecycleTypes(launcher.LaunchPlan, launcher.SurfaceAttachment,
            launcher.AgentConsole, launcher.LaunchCancelled))


def generated_plan(root, *, purpose="session", backend="omlx", client="chat"):
    return launcher.LaunchPlan("generated-owned-lifetime", backend, client,
        {"id":"fixture-model", "name":"Generated model", "servedId":"fixture-served",
         "path":str(root), "backends":{backend:{"customSampling":True,"agentReasoning":["off"]}}},
        str(root), 8192, 1024, "off", 18887, "ar", {"kv":"off"},
        purpose=purpose, run_dir=root, client_port=18888,
        chat={"sampling":"model","systemPrompt":""},
        secrets={"apiKey":"private-fixture-engine", "clientApiKey":"private-fixture-surface",
                 "proxyControlKey":"private-fixture-control"})


def resident(value, plan):
    value.plan = plan
    value.started_at = "2026-10-07T00:00:00+00:00"
    value.state = {"phase":"running", "message":"Generated ready", "run":plan.public(), "events":[]}
    value.session_proxy_port = plan.client_port
    value.session_proxy_control_key = plan.secrets["proxyControlKey"]
    value.attachments[plan.run_id] = launcher.SurfaceAttachment(plan.run_id, plan,
        primary=True, status="ready", attached_at=value.started_at)
    return value


def normalize(value):
    if isinstance(value, dict):
        return {key:("<time>" if key in {"time","observedAt","policySetAt","updatedAt","attachedAt","startedAt"}
                     else normalize(item)) for key,item in value.items()}
    if isinstance(value, (list,tuple)):
        return [normalize(item) for item in value]
    return value


class SourceProjection(ast.NodeTransformer):
    TYPES = {"Plan":"LaunchPlan", "Console":"AgentConsole", "Attachment":"SurfaceAttachment",
             "ExecutableLaunch":"UzuExecutableLaunch", "ActivityTarget":"_SessionActivityTarget"}

    def visit_Name(self, node):
        name = self.TYPES.get(node.id, node.id)
        name = {"cancelled_error":"LaunchCancelled", "make_plan":"LaunchPlan",
                "api_key_file":"_uzu_api_key_file", "max_input":"AGENT_CONSOLE_MAX_INPUT"}.get(name,name)
        return ast.copy_location(ast.Name(id=name,ctx=node.ctx),node)

    def visit_Call(self, node):
        spelling = ast.unparse(node.func)
        if spelling in {"self.services.workspace.app_dir","self.services.workspace.state_dir"}:
            return ast.Name(id="APP_DIR" if spelling.endswith("app_dir") else "STATE_DIR",ctx=ast.Load())
        if spelling == "self.services.runtime.quitting":
            return ast.Call(func=ast.Attribute(value=ast.Name(id="CONTROLLER_QUITTING",ctx=ast.Load()),attr="is_set",ctx=ast.Load()),args=[],keywords=[])
        if spelling == "self.services.runtime.binary":
            return ast.Call(func=ast.Attribute(value=ast.Name(id="BINARIES",ctx=ast.Load()),attr="get",ctx=ast.Load()),args=node.args,keywords=[])
        return self.generic_visit(node)

    def visit_Subscript(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == "BINARIES":
            return ast.Call(func=ast.Attribute(value=ast.Name(id="BINARIES",ctx=ast.Load()),attr="get",ctx=ast.Load()),args=[node.slice],keywords=[])
        return self.generic_visit(node)

    def visit_Attribute(self, node):
        spelling = ast.unparse(node)
        if spelling.startswith("self.policy.") and len(spelling.split(".")) == 3:
            return ast.Name(id=node.attr.upper(),ctx=ast.Load())
        if spelling.startswith("self.services.") and len(spelling.split(".")) == 4:
            return ast.Name(id=node.attr,ctx=ast.Load())
        if spelling.startswith("self.types."):
            return ast.Name(id={"plan":"LaunchPlan","attachment":"SurfaceAttachment",
                "console":"AgentConsole","cancelled":"LaunchCancelled"}[node.attr],ctx=ast.Load())
        return self.generic_visit(node)


def project_operation_epoch_seams(test, name, body):
    """Allow only the separately tested exact owner/epoch additions."""
    def same(actual, expected):
        test.assertEqual(ast.dump(actual, include_attributes=False),
                         ast.dump(ast.parse(expected).body[0], include_attributes=False))

    guard = '''if (
        (expected_plan is not None and self.plan is not expected_plan)
        or (expected_cancel_event is not None and self.cancel_event is not expected_cancel_event)
        or (expected_cancel_event is not None and expected_cancel_event.is_set())
    ):
        raise self.types.cancelled("The resident model route changed before this workspace action.")'''
    if name == "_validated_attachment_target":
        same(body[1].body[0], guard)
        del body[1].body[0]
    if name == "restart_agent_console":
        locked = next(item for item in body[0].body if isinstance(item, ast.With))
        same(locked.body[0], guard)
        del locked.body[0]
    if name == "attach_surface":
        locked = body[1].body
        call = locked[0].value
        test.assertEqual([(item.arg, ast.unparse(item.value)) for item in call.keywords],
                         [("expected_plan", "expected_plan"), ("expected_cancel_event", "expected_cancel_event")])
        call.keywords = []
        same(locked[3], '''with self.lock:
            if self.plan is not owner or self.cancel_event is not cancel_event or cancel_event.is_set():
                raise self.types.cancelled("The resident model route changed before this workspace action.")
            activity_target = self._activity_target_unlocked()''')
        del locked[3]
        handler = next(item for item in ast.walk(ast.Module(body=body, type_ignores=[]))
                       if isinstance(item, ast.ExceptHandler) and isinstance(item.type, ast.Name)
                       and item.type.id == "Exception")
        same(handler.body[1], '''with self.lock:
            published = self.attachments.get(attachment_id)
            console = self.agent_consoles.get(attachment_id)
            retained = bool(
                (published is not None and published.plan is attachment_plan)
                or (console is not None and console.plan is attachment_plan
                    and (console.process.poll() is None
                         or console.state in {"starting", "running", "stopping"}))
            )''')
        same(handler.body[2], '''if not retained:
            self.services.workspace.dispose_plan_secrets(attachment_plan)''')
        del handler.body[1:3]
    if name == "_activity_target_unlocked":
        call = body[0].value
        test.assertEqual(ast.unparse(call.args[-1]), "self.cancel_event")
        call.args.pop()
    if name == "_activity_target_matches_unlocked":
        value = body[0].value.values
        test.assertEqual(ast.unparse(value[1]), "target.cancel_epoch is self.cancel_event")
        del value[1]
    if name in {"register_session_surface", "unregister_session_surface", "attach_surface"}:
        for item in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(item, ast.Call):
                arguments = [entry for entry in item.keywords if entry.arg == "_target"]
                if arguments:
                    expected = "activity_target" if name == "attach_surface" else "_target"
                    test.assertEqual(ast.unparse(arguments[0].value), expected)
                    test.assertEqual(len(arguments), 1)
                    item.keywords = [entry for entry in item.keywords if entry.arg != "_target"]
    return body


class LifecycleSourceTests(unittest.TestCase):
    def test_controller_facade_preserves_all_public_call_shapes_and_complete_domain_binding(self):
        self.assertTrue(issubclass(launcher.RunManager,lifecycle.RunManager))
        for name in METADATA["methods"]:
            if name == "__init__": continue
            with self.subTest(method=name):
                old=inspect.signature(getattr(legacy.RunManager,name))
                current=inspect.signature(getattr(launcher.RunManager,name))
                additions = {
                    "_validated_attachment_target": ("expected_plan", "expected_cancel_event"),
                    "attach_surface": ("expected_plan", "expected_cancel_event"),
                    "restart_agent_console": ("expected_plan", "expected_cancel_event"),
                    "register_session_surface": ("_target",),
                    "unregister_session_surface": ("_target",),
                }.get(name, ())
                for added in additions:
                    self.assertEqual(current.parameters[added].kind, inspect.Parameter.KEYWORD_ONLY)
                    self.assertIsNone(current.parameters[added].default)
                self.assertEqual([(p.name,p.kind,p.default) for p in old.parameters.values()],
                                 [(p.name,p.kind,p.default) for p in current.parameters.values() if p.name not in additions])
                if name not in METADATA["staticHelpers"]:
                    self.assertIs(getattr(launcher.RunManager,name),getattr(lifecycle.RunManager,name))
        value=launcher.RunManager()
        self.assertIsInstance(value.policy,lifecycle.LifecyclePolicy)
        self.assertIsInstance(value.services,lifecycle.LifecycleServices)
        self.assertIs(launcher._SessionActivityTarget,lifecycle.ActivityTarget)
        self.assertIn(Path(lifecycle.__file__).resolve(),launcher.CONTROLLER_SOURCE_PATHS)

    def test_frozen_source_digest_and_all_78_method_bodies(self):
        text = (FIXTURES / "run_lifecycle_legacy.py").read_text()
        self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),METADATA["fixtureDigest"])
        frozen_tree = ast.parse(text)
        frozen_class = next(n for n in frozen_tree.body if isinstance(n,ast.ClassDef) and n.name=="RunManager")
        frozen = {n.name:n for n in frozen_class.body if isinstance(n,ast.FunctionDef)}
        current_tree = ast.parse(Path(lifecycle.__file__).read_text())
        current_class = next(n for n in current_tree.body if isinstance(n,ast.ClassDef) and n.name=="RunManager")
        current = {n.name:n for n in current_class.body if isinstance(n,ast.FunctionDef)}
        helpers = {n.name:n for n in current_tree.body if isinstance(n,ast.FunctionDef)}
        self.assertEqual(set(current),set(frozen))
        self.assertEqual(len(current),78)
        for name, old in frozen.items():
            with self.subTest(method=name):
                new = helpers[name] if name in METADATA["staticHelpers"] else current[name]
                old_body = copy.deepcopy(old.body)
                new_body = copy.deepcopy(new.body)
                new_body = project_operation_epoch_seams(self, name, new_body)
                if name == "__init__":
                    # Only explicit dependency publication precedes unchanged state initialization.
                    self.assertEqual([ast.unparse(item) for item in new_body[:3]],
                        ["self.policy = policy","self.services = services","self.types = types"])
                    new_body = new_body[3:]
                if name == "_unload_lmstudio_id":
                    # The live binary is an explicit helper argument; no default/global capture.
                    new_body = [copy.deepcopy(old_body[0]),*new_body]
                old_module = SourceProjection().visit(ast.Module(body=old_body,type_ignores=[]))
                new_module = SourceProjection().visit(ast.Module(body=new_body,type_ignores=[]))
                self.assertEqual(ast.dump(new_module,include_attributes=False),
                                 ast.dump(old_module,include_attributes=False))

    def test_import_is_controller_independent_and_has_no_process_or_io_side_effects(self):
        script = """
import builtins, pathlib, subprocess, sys
sys.path.insert(0,sys.argv[1])
original_import = builtins.__import__
def guarded(name,*args,**kwargs):
    if name == 'launcher': raise AssertionError('Controller dependency')
    return original_import(name,*args,**kwargs)
builtins.__import__ = guarded
subprocess.Popen = lambda *a,**k: (_ for _ in ()).throw(AssertionError('Process on import'))
pathlib.Path.write_text = lambda *a,**k: (_ for _ in ()).throw(AssertionError('Write on import'))
import run_lifecycle
assert 'launcher' not in sys.modules
"""
        result = subprocess.run([sys.executable,"-I","-B","-c",script,str(Path(lifecycle.__file__).parent)],
            stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_policy_freezes_all_collections_and_detaches_client_descriptors(self):
        labels = {"omlx":"Generated label"}
        adapters = {"chat":launcher.AdapterDescriptor("chat","Chat","surface",None,"chat-completions",True)}
        value = replace(policy(),backend_labels=labels,client_adapters=adapters)
        labels["omlx"] = "Changed source"; adapters.clear()
        self.assertEqual(value.backend_labels["omlx"],"Generated label")
        self.assertTrue(value.client_adapters["chat"].built_in)
        with self.assertRaises(TypeError): value.backend_labels["omlx"] = "changed"
        with self.assertRaises(FrozenInstanceError): value.client_adapters["chat"].built_in = False
        with self.assertRaises(FrozenInstanceError): value.surface_attachment_max = 0


class LifecycleBehaviorTests(unittest.TestCase):
    def test_integrated_facade_visible_cache_activity_and_history_bindings_match_frozen(self):
        with tempfile.TemporaryDirectory(prefix="lifecycle-integrated-visible-") as directory:
            root=Path(directory); values=(legacy.RunManager(),launcher.RunManager())
            saved=[]
            with mock.patch.object(launcher,"save_chat_history",side_effect=lambda payload,**kwargs:saved.append((payload,kwargs)) or {"saved":True}), \
                    mock.patch.object(legacy,"save_chat_history",side_effect=lambda payload,**kwargs:saved.append((payload,kwargs)) or {"saved":True}), \
                    mock.patch.object(launcher,"_chat_resume_contract_for_plan",return_value={"generated":"resume"}), \
                    mock.patch.object(legacy,"_chat_resume_contract_for_plan",return_value={"generated":"resume"}):
                outcomes=[]
                for value in values:
                    plan=generated_plan(root); resident(value,plan); value.idle_policy_set_at=0
                    value._session_proxy_api=lambda *_args,**_kwargs:{"state":"ready","activeCount":0,
                        "queuedCount":0,"idleSeconds":0,"coverage":{"allLauncherSurfaces":True}}
                    value.record_chat_cache_observation({"ownerRunId":plan.run_id,"attachmentId":plan.run_id},
                        {"completed":True,"promptTokens":10,"completionTokens":2,"cachedPromptTokens":8,
                         "cacheTelemetryReported":True,"ttftSeconds":.01,"totalSeconds":.04})
                    outcomes.append(normalize(value.snapshot()))
                    self.assertEqual(value.save_chat_history({"runId":plan.run_id,"messages":[]}),{"saved":True})
                self.assertEqual(outcomes[0],outcomes[1])
                self.assertEqual(saved[0],saved[1])
            with mock.patch.object(launcher,"save_chat_history",return_value={"saved":"late-bound"}) as save:
                self.assertEqual(values[1].save_chat_history({"messages":[]}),{"saved":"late-bound"})
            save.assert_called_once_with({"messages":[]},resume_contract=None)

    def test_idle_snapshot_and_resident_cache_contract_match_frozen(self):
        with tempfile.TemporaryDirectory(prefix="lifecycle-visible-") as directory:
            root=Path(directory)
            pair=(legacy.RunManager(),manager(root=root))
            for value in pair: value.idle_policy_set_at=0
            self.assertEqual(normalize(pair[0].snapshot()),normalize(pair[1].snapshot()))
            for value in pair:
                plan=generated_plan(root); resident(value,plan)
                value.idle_policy_set_at=0
                value.record_chat_cache_observation({"ownerRunId":plan.run_id,"attachmentId":plan.run_id},
                    {"completed":True,"promptTokens":100,"completionTokens":12,"cachedPromptTokens":75,
                     "cacheTelemetryReported":True,"ttftSeconds":.04,"totalSeconds":.2})
                value.record_chat_cache_observation({"ownerRunId":"wrong","attachmentId":plan.run_id},
                    {"completed":True,"promptTokens":999,"completionTokens":999})
            self.assertEqual(normalize(pair[0].cache_observatory()),normalize(pair[1].cache_observatory()))
            self.assertEqual(pair[1].cache_observatory()["reportedCachedPromptTokens"],75)
            self.assertEqual(pair[1].cache_observatory()["observationCount"],1)

    def test_live_runtime_and_paths_are_resolved_after_construction(self):
        with tempfile.TemporaryDirectory(prefix="lifecycle-live-services-") as directory:
            value=manager()
            with mock.patch.dict(launcher.BINARIES,{"omp":"generated-new-binary"}), \
                    mock.patch.object(launcher,"STATE_DIR",Path(directory)):
                self.assertEqual(value.services.runtime.binary("omp"),"generated-new-binary")
                self.assertEqual(value.services.workspace.state_dir(),Path(directory))
            with mock.patch.object(launcher,"session_request_lanes",return_value=7):
                self.assertEqual(value.services.activity.session_request_lanes(None),7)

    def test_activity_replaced_during_read_never_publishes_prior_route(self):
        with tempfile.TemporaryDirectory(prefix="lifecycle-activity-race-") as directory:
            value=resident(manager(root=Path(directory)),generated_plan(Path(directory)))
            target=value._activity_target_unlocked()
            replacement=generated_plan(Path(directory)); replacement.run_id="replacement"
            value.plan=replacement
            result=value.request_activity(include_engine_telemetry=False,_target=target)
            self.assertEqual(result["activeCount"],0)
            self.assertEqual(result["queuedCount"],0)
            self.assertIn("changed",result["detail"])
            self.assertFalse(value._activity_target_matches_unlocked(target))

    def test_session_proxy_stale_response_is_rejected_under_owner_lock(self):
        with tempfile.TemporaryDirectory(prefix="lifecycle-relay-race-") as directory:
            value=resident(manager(root=Path(directory)),generated_plan(Path(directory)))
            response=mock.MagicMock(); response.__enter__.return_value=response
            def finish(_size):
                value.plan=generated_plan(Path(directory)); value.plan.run_id="replacement"
                return b'{"version":1,"activeCount":0}'
            response.read.side_effect=finish
            with mock.patch.object(lifecycle.urllib.request,"urlopen",return_value=response):
                with self.assertRaisesRegex(ValueError,"route changed"):
                    value._session_proxy_api("GET","/__launcher/status")

    def test_idle_policy_matches_frozen_and_disables_shared_lmstudio_unload(self):
        with tempfile.TemporaryDirectory(prefix="lifecycle-idle-policy-") as directory:
            for backend in ("omlx","lmstudio","freetoken"):
                for timeout in (0,5,True,9):
                    outcomes=[]
                    for factory in (legacy.RunManager,lambda:manager(root=Path(directory))):
                        value=resident(factory(),generated_plan(Path(directory),backend=backend))
                        value.request_activity=lambda **_kwargs:{"generated":True}
                        try:
                            result=value.set_idle_policy({"ownerRunId":value.plan.run_id,"timeoutMinutes":timeout})
                            outcomes.append((result,value.idle_timeout_minutes))
                        except ValueError as error: outcomes.append(str(error))
                    self.assertEqual(outcomes[0],outcomes[1],(backend,timeout))

    def test_quitting_and_rejected_busy_start_preserve_existing_lifetime_and_bearers(self):
        with tempfile.TemporaryDirectory(prefix="lifecycle-rejected-start-") as directory:
            root=Path(directory); value=manager(root=root,overrides={"quitting":lambda:True})
            plan=generated_plan(root)
            with mock.patch.object(lifecycle.subprocess,"Popen",side_effect=AssertionError("No child")):
                with self.assertRaises(launcher.LaunchCancelled): value.start(plan)
            self.assertIsNone(value.plan); self.assertTrue(plan.secrets)
            value=resident(manager(root=root),generated_plan(root)); epoch=value.cancel_event
            rejected=generated_plan(root); rejected.run_id="rejected"
            with self.assertRaisesRegex(ValueError,"Another launcher run"): value.start(rejected)
            self.assertIs(value.cancel_event,epoch)
            self.assertTrue(rejected.secrets)

    def test_owned_cleanup_is_exactly_once_and_preserves_a_replacement(self):
        with tempfile.TemporaryDirectory(prefix="lifecycle-cleanup-latch-") as directory:
            disposed=[]; root=Path(directory)
            value=resident(manager(root=root,overrides={"dispose_plan_secrets":disposed.append}),generated_plan(root))
            value.cleanup_complete.clear()
            process=mock.Mock(); value.process=process
            entered=threading.Event(); release=threading.Event(); calls=[]
            def terminate(target,_timeout):
                if target is process:
                    calls.append(target); entered.set(); self.assertTrue(release.wait(3))
            with mock.patch.object(value,"_terminate_process",side_effect=terminate):
                first=threading.Thread(target=value._stop_owned,args=(value.plan,))
                second=threading.Thread(target=value._stop_owned,args=(value.plan,))
                first.start(); self.assertTrue(entered.wait(2)); second.start(); release.set()
                first.join(3); second.join(3)
            self.assertFalse(first.is_alive()); self.assertFalse(second.is_alive())
            self.assertEqual(calls,[process]); self.assertEqual(disposed,[value.plan])
            old=value.plan; replacement=generated_plan(root); value.plan=replacement
            with mock.patch.object(value,"_terminate_process") as terminate:
                value._stop_owned(old)
            terminate.assert_not_called(); self.assertIs(value.plan,replacement)

    def test_lmstudio_cleanup_targets_only_unique_owned_model_identifier(self):
        with tempfile.TemporaryDirectory(prefix="lifecycle-lms-scope-") as directory:
            root=Path(directory); plan=generated_plan(root,backend="lmstudio")
            plan.model["servedId"]="llm-launcher-aabbccdd"
            value=resident(manager(root=root,overrides={"binary":lambda key:"generated-lms" if key=="lms" else None,
                "dispose_plan_secrets":lambda _plan:None}),plan)
            with mock.patch.object(value,"_unload_lmstudio_id") as unload, \
                    mock.patch.object(value,"_schedule_lmstudio_cleanup") as schedule, \
                    mock.patch.object(value,"_terminate_process") as terminate:
                value._stop_owned(plan)
            unload.assert_called_once_with("llm-launcher-aabbccdd")
            schedule.assert_called_once_with("llm-launcher-aabbccdd")
            self.assertTrue(all(call.args[0] is None for call in terminate.call_args_list))
            value=manager(root=root,overrides={"binary":lambda _key:"generated-lms"})
            with mock.patch.object(lifecycle.subprocess,"Popen") as spawn:
                value._schedule_lmstudio_cleanup("llm-launcher-aabbccdd")
            command=spawn.call_args.args[0]
            self.assertEqual(command[1],str(root/"lmstudio_cleanup.py"))
            config=json.loads((root/"cleanup/llm-launcher-aabbccdd.json").read_text())
            self.assertEqual(config["identifier"],"llm-launcher-aabbccdd")
            self.assertEqual(config["deadlines"][-1],1020)
            self.assertNotIn("server",command)

    def test_attachment_overlay_preserves_native_contract_and_allocates_no_engine(self):
        with tempfile.TemporaryDirectory(prefix="lifecycle-attachment-") as directory:
            root=Path(directory); owner=generated_plan(root)
            owner.sampling_contract={"generated":"exact"}; owner.sampling_enforcement={"fields":["seed"]}
            target={"owner":owner,"client":"chat","project":str(root),"chat":owner.chat,
                "samplingContract":owner.sampling_contract,"samplingEnforcement":owner.sampling_enforcement,"agentHost":"launcher"}
            builds=[]; value=manager(root=root,overrides={"build_client_plan":builds.append})
            with mock.patch.object(lifecycle.subprocess,"Popen",side_effect=AssertionError("No engine")):
                attached=value._build_attachment_launch_plan(target,"generated-surface",18889,"private-attached-key")
            self.assertEqual((attached.backend,attached.context,attached.output,attached.reasoning,attached.options),
                (owner.backend,owner.context,owner.output,owner.reasoning,owner.options))
            self.assertEqual(attached.sampling_contract,owner.sampling_contract)
            self.assertIsNot(attached.sampling_contract,owner.sampling_contract)
            self.assertEqual(attached.engine_argv,[])
            self.assertEqual(builds,[attached]); self.assertEqual(attached.port,owner.port)
            self.assertEqual(attached.client_port,18889)
            self.assertTrue(attached.run_dir.is_relative_to(root))


class LifecycleProcessTests(unittest.TestCase):
    def test_uzu_retained_descriptor_handoff_revalidates_and_closes_before_publication(self):
        with tempfile.TemporaryDirectory(prefix="lifecycle-retained-executable-") as directory:
            root=Path(directory); plan=generated_plan(root,purpose="benchmark",backend="uzu")
            trace=[]; opened=object()
            handoff=mock.Mock(argv=["/dev/fd/40","serve"],pass_fds=(40,),executes_from_fd=False,opened=opened)
            handoff.close.side_effect=lambda:trace.append("closed")
            def validate(_plan): trace.append("validated"); return ("generated-image",)
            def prepare(_plan,identity):
                self.assertEqual(identity,("generated-image",)); trace.append("opened"); return handoff
            def confirm(receipt): self.assertIs(receipt,opened); trace.append("confirmed")
            value=manager(root=root,overrides={"validate_uzu_launch_boundary":validate,
                "prepare_uzu_executable_launch":prepare,"_confirm_open_uzu_executable":confirm,
                "_environment_without_dyld":lambda env:{key:item for key,item in env.items() if not key.startswith("DYLD_")},
                "dispose_plan_secrets":lambda _plan:None})
            value.plan=plan; value.state["phase"]="preflight"
            process=mock.Mock(); process.poll.return_value=None
            def spawn(*_args,**kwargs):
                self.assertEqual(kwargs["pass_fds"],(40,)); trace.append("spawned"); return process
            original=value._publish_owned_process
            def publish(*args): trace.append("published"); return original(*args)
            with mock.patch.object(lifecycle.subprocess,"Popen",side_effect=spawn), \
                    mock.patch.object(lifecycle.threading,"Thread"), \
                    mock.patch.object(value,"_wait_ready"), \
                    mock.patch.object(value,"_verify_lmstudio_reasoning"), \
                    mock.patch.object(value,"_verify_client_api"), \
                    mock.patch.object(value,"_publish_owned_process",side_effect=publish):
                value._worker(plan,value.cancel_event)
            self.assertEqual(trace,["validated","opened","spawned","confirmed","closed","published"])
            self.assertIs(value.process,process)
            self.assertEqual(value.state["phase"],"running")
            handoff.close.assert_called_once()

    def test_complete_owned_worker_launch_stop_and_new_epoch_use_only_generated_process(self):
        with tempfile.TemporaryDirectory(prefix="lifecycle-owned-engine-") as directory:
            root=Path(directory); plan=generated_plan(root,purpose="benchmark")
            plan.engine_argv=[sys.executable,"-c","import time; time.sleep(60)"]
            value=manager(root=root)
            def ready(_plan,_cancel): self.assertIsNotNone(value.process)
            def monitor(_plan,cancel): cancel.wait(5)
            with mock.patch.object(value,"_wait_ready",side_effect=ready), \
                    mock.patch.object(value,"_verify_lmstudio_reasoning"), \
                    mock.patch.object(value,"_verify_client_api"), \
                    mock.patch.object(value,"_monitor_run",side_effect=monitor):
                process=None
                try:
                    value.start(plan)
                    deadline=time.monotonic()+3
                    while value.state["phase"] != "running" and time.monotonic()<deadline: time.sleep(.01)
                    self.assertEqual(value.state["phase"],"running")
                    process=value.process; self.assertIsNone(process.poll())
                    epoch=value.cancel_event
                    value.stop(expected_plan=plan,expected_cancel_event=epoch)
                    self.assertIsNotNone(process.poll()); self.assertEqual(value.state["phase"],"idle")
                    self.assertIsNone(value.plan); self.assertFalse(plan.secrets)
                    self.assertTrue(value.cleanup_complete.is_set())
                finally:
                    value.stop()
                    if process is not None: value._terminate_process(process,.5)

    def test_late_owned_child_publication_stops_own_fixture_and_leaves_replacement(self):
        with tempfile.TemporaryDirectory(prefix="lifecycle-late-child-") as directory:
            root=Path(directory); value=manager(root=root)
            stale=generated_plan(root); old_epoch=threading.Event()
            replacement=generated_plan(root); replacement.run_id="replacement"
            resident(value,replacement); epoch=value.cancel_event
            process=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            try:
                with self.assertRaises(launcher.LaunchCancelled):
                    value._publish_owned_process("process",process,stale,old_epoch)
                self.assertIsNotNone(process.poll())
                self.assertIs(value.plan,replacement); self.assertIs(value.cancel_event,epoch)
                self.assertFalse(epoch.is_set()); self.assertIsNone(value.process)
            finally: value._terminate_process(process,.5)


def lifecycle_fixture_suite(module_name, file_name, class_name):
    module=load_fixture(module_name,Path(__file__).parent/file_name)
    base=getattr(module,class_name)
    class Standalone(base):
        def setUp(self):
            self.lifecycle_patch=mock.patch.object(launcher,"RunManager",side_effect=manager)
            self.lifecycle_patch.start()
            self.addCleanup(self.lifecycle_patch.stop)
            super().setUp()
    Standalone.__name__="Standalone"+class_name
    Standalone.__qualname__=Standalone.__name__
    return Standalone


# Reuse the established harmless PTY/wire/epoch scenarios against the new domain
# before replacing the controller class. Their original suites remain unchanged.
StandaloneOMPConsoleTests=lifecycle_fixture_suite("lifecycle_omp_fixture","test_omp_console.py","OMPConsoleTests")
StandaloneAgentConsoleOwnedExitTests=lifecycle_fixture_suite("lifecycle_exit_fixture","test_agent_console_owned_exit.py","AgentConsoleOwnedExitTests")
StandaloneRunWorkerStartTests=lifecycle_fixture_suite("lifecycle_start_fixture","test_run_worker_start.py","RunWorkerStartTests")


def guard_fixture_suite(module_name, file_name, class_name, selected):
    module=load_fixture(module_name,Path(__file__).parent/file_name)
    original=getattr(module,class_name)
    def setUp(self):
        patch=mock.patch.object(launcher,"RunManager",side_effect=manager)
        patch.start(); self.addCleanup(patch.stop)
        # Generated PID values are never eligible for real signals.
        signals=mock.patch.object(lifecycle.RunManager,"_terminate_process")
        signals.start(); self.addCleanup(signals.stop)
    return type("Standalone"+class_name,(unittest.TestCase,),
        {"setUp":setUp,**{name:getattr(original,name) for name in selected}})


StandaloneUzuMemoryGuardTests=guard_fixture_suite("lifecycle_uzu_guard_fixture","test_uzu_backend.py","UzuBackendTests",(
    "test_uzu_live_guard_enforces_38gib_current_or_peak",
    "test_uzu_live_guard_stops_only_after_sustained_whole_mac_pressure",
    "test_uzu_live_guard_fails_closed_when_system_pressure_is_unreadable"))
StandaloneLlamaMemoryGuardTests=guard_fixture_suite("lifecycle_llama_guard_fixture","test_launcher.py","LauncherTests",(
    "test_llamacpp_startup_memory_guard_stops_before_readiness",
    "test_llamacpp_guard_stops_if_whallm_activates_during_any_route",
    "test_llamacpp_running_monitor_persists_safety_violation"))


if __name__ == "__main__": unittest.main()
