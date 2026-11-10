"""Complete frozen capacity/admission decisions with synthetic live authority ports."""
from __future__ import annotations
import ast,copy,hashlib,inspect,json,subprocess,sys,tempfile,timeit,unittest
from pathlib import Path
from unittest import mock
from dataclasses import FrozenInstanceError
from contextlib import ExitStack
from types import SimpleNamespace
import launcher
import resource_admission as resource
from tests.helpers.resource_admission_harness import Fixture,policy,snapshot,model,request,FixedDateTime,GIB,META,ROOT

class Projection(ast.NodeTransformer):
    def visit_If(self,node):
        # Rec is a new route, checked separately by test_rec_integration.
        # Keep the frozen comparison for all pre-existing backend branches.
        if any(isinstance(item,ast.Constant) and item.value=='rec' for item in ast.walk(node.test)):
            return [self.visit(item) for item in node.orelse]
        return self.generic_visit(node)
    def visit_Attribute(self,node):
        spelling=ast.unparse(node)
        if spelling.startswith('self.policy.'):
            field=node.attr
            constants={name.lower():name for name in META['constants']}
            if field in constants:return ast.copy_location(ast.Name(id=constants[field],ctx=node.ctx),node)
        if spelling.startswith('self.services.'):
            lookup={f'self.services.{group}.{field}':name for name,(group,field) in META['callbacks'].items()}
            lookup.update({'self.services.native.kolibri_memory_plan':'kolibri_runtime.memory_plan','self.services.native.splash_memory_estimate':'splash_runtime.memory_estimate','self.services.live.hub_snapshot':'MANAGER.hub_snapshot'})
            if spelling in lookup:return ast.copy_location(ast.parse(lookup[spelling],mode='eval').body,node)
        for original,(group,field) in META['attributes'].items():
            if spelling==f'self.{group}.{field}':return ast.copy_location(ast.parse(original,mode='eval').body,node)
        if spelling.startswith('self.') and node.attr in META['functions']:return ast.copy_location(ast.Name(id=node.attr,ctx=node.ctx),node)
        return self.generic_visit(node)
    def visit_Name(self,node):
        if node.id=='ceiling' and getattr(self,'restore_ceiling',False):return ast.copy_location(ast.Name(id='UZU_PROCESS_MEMORY_CEILING_BYTES',ctx=node.ctx),node)
        return node

class ResourceSourceTests(unittest.TestCase):
    @staticmethod
    def splash_branches(body):
        # Only the function's top-level backend dispatch, including elifs.
        # Do not normalize unrelated nested conditions or their statements.
        branches=[]
        for statement in body:
            branch=statement
            while isinstance(branch,ast.If):
                if any(isinstance(node,ast.Constant) and node.value=='splash' for node in ast.walk(branch.test)):
                    branches.append(branch)
                branch=branch.orelse[0] if len(branch.orelse)==1 else None
        return branches

    def test_all16_complete_bodies_match_frozen_without_dropping_any_branch(self):
        fixture=(ROOT/'tests/fixtures/resource_admission_legacy.py').read_text().split('\n\n',1)[1]
        self.assertEqual(hashlib.sha256(fixture.encode()).hexdigest(),META['fixtureSha256'])
        old={item.name:item for item in ast.parse(fixture).body if isinstance(item,ast.FunctionDef)}
        parsed=ast.parse(Path(resource.__file__).read_text());new={item.name:item for item in parsed.body if isinstance(item,ast.FunctionDef)}
        klass=next(item for item in parsed.body if isinstance(item,ast.ClassDef) and item.name=='ResourceAdmission')
        new.update({item.name:item for item in klass.body if isinstance(item,ast.FunctionDef)})
        for name in META['functions']:
            with self.subTest(method=name):
                projection=Projection();projection.restore_ceiling=name=='uzu_qualification_memory_ceiling_supported'
                actual=projection.visit(ast.Module(body=copy.deepcopy(new[name].body),type_ignores=[]))
                expected=ast.Module(body=copy.deepcopy(old[name].body),type_ignores=[])
                for body in (actual.body,expected.body):
                    if isinstance(body[0],ast.Expr) and isinstance(body[0].value,ast.Constant) and isinstance(body[0].value.value,str):
                        body[0].value.value=inspect.cleandoc(body[0].value.value)
                if name in {'launch_memory_estimate','session_memory_admission'}:
                    # Splash 1.4 intentionally adds streamed memory planning.
                    # Its legacy behavior is covered by complete frozen records
                    # and new budgets by test_splash_memory. Keep AST equality
                    # for every other branch and the unchanged dispatch tests.
                    changed=self.splash_branches(actual.body)
                    original=self.splash_branches(expected.body)
                    self.assertEqual(len(changed),1)
                    self.assertEqual(len(original),1)
                    self.assertEqual(ast.dump(changed[0].test,include_attributes=False),ast.dump(original[0].test,include_attributes=False))
                    changed[0].body=copy.deepcopy(original[0].body)
                if name == 'launch_memory_estimate':
                    # Strata is a new SSD-streaming route, tested separately.
                    strata = [node for node in actual.body if isinstance(node, ast.If)
                              and "backend == 'strata'" in ast.unparse(node.test)]
                    self.assertEqual(len(strata), 1)
                    actual.body.remove(strata[0])
                    # Rapid accounts for the loader's native target and MTP
                    # bytes, even when another engine discovered the folder.
                    # Verify only this exact new overlay before projecting it
                    # away; every pre-existing backend statement stays exact.
                    overlay=ast.parse("""if backend == 'rapidmlx':
    capability = model.get('backends', {}).get('rapidmlx', {})
    native_bytes = int(capability.get('nativeWeightBytes') or 0)
    if native_bytes > 0:
        model = {**model, 'size': native_bytes,
                 'mtpSidecarSize': int(capability.get('mtpSidecarBytes') or 0)}
""").body[0]
                    overlays=[node for node in actual.body if isinstance(node,ast.If)
                              and ast.dump(node.test,include_attributes=False)==ast.dump(overlay.test,include_attributes=False)]
                    self.assertEqual(len(overlays),1)
                    self.assertEqual(ast.dump(overlays[0],include_attributes=False),ast.dump(overlay,include_attributes=False))
                    actual.body.remove(overlays[0])
                    sidecar=next(node for node in actual.body if isinstance(node,ast.Assign)
                                 and any(isinstance(target,ast.Name) and target.id=='uses_sidecar' for target in node.targets))
                    membership=next(node for node in ast.walk(sidecar.value) if isinstance(node,ast.Compare)
                                    and isinstance(node.left,ast.Name) and node.left.id=='backend')
                    self.assertEqual(ast.literal_eval(membership.comparators[0]),{'lmstudio','mtplx','rapidmlx'})
                    membership.comparators[0].elts=[item for item in membership.comparators[0].elts
                                                   if not (isinstance(item,ast.Constant) and item.value=='rapidmlx')]
                self.assertEqual(ast.dump(actual,include_attributes=False),ast.dump(expected,include_attributes=False))
    def test_import_is_independent_and_has_no_io_process_or_controller_side_effect(self):
        script='''import builtins,pathlib,subprocess,sys,urllib.request
sys.path.insert(0,sys.argv[1]);original=builtins.__import__
def guarded(name,*a,**k):
 if name=='launcher':raise AssertionError('controller imported')
 return original(name,*a,**k)
builtins.__import__=guarded
def forbidden(*a,**k):raise AssertionError('import side effect')
subprocess.Popen=forbidden;urllib.request.urlopen=forbidden;pathlib.Path.write_text=forbidden
import resource_admission
assert 'launcher' not in sys.modules
'''
        result=subprocess.run([sys.executable,'-I','-B','-c',script,str(ROOT)],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
    def test_policy_is_frozen_detached_and_pure_helpers_need_no_policy_factory(self):
        value=policy()
        with self.assertRaises(FrozenInstanceError):value.session_os_reserve_min_bytes=1
        with self.assertRaises(TypeError):value.backend_labels['kolibri']='changed'
        self.assertIsInstance(value.uzu_model_file_manifest,tuple)
        with mock.patch.object(resource.ResourceAdmission,'__init__',side_effect=AssertionError('no domain construction')):
            self.assertEqual(resource.qwen4_qsa_allocation_high_water_tokens(8193,8192),16384)
            self.assertEqual(resource.effective_kv_precision('omlx',{'acceleration':'dflash','dflashVerify':'ddtree','kv':'q6'}),'off')
            self.assertFalse(resource.strict_model_load_admission_ready({'launchable':True,'decision':'review','requiresAcknowledgement':True}))

class ResourceDecisionTests(unittest.TestCase):
    def compare(self,fixture,name,*args,**kwargs):
        with mock.patch.object(resource,'datetime',FixedDateTime):
            current=getattr(fixture.domain,name)(*copy.deepcopy(args),**copy.deepcopy(kwargs))
            original=fixture.legacy[name](*copy.deepcopy(args),**copy.deepcopy(kwargs))
        self.assertEqual(current,original)
        return current
    def test_all180_frozen_complete_records_match_current_domain(self):
        data=json.loads((ROOT/'tests/fixtures/resource_admission_records.json').read_text())
        self.assertEqual(data['sourceSha256'],hashlib.sha256((ROOT/'tests/fixtures/resource_admission_legacy.py').read_bytes()).hexdigest())
        self.assertEqual(len(data['cases']),180)
        fixture=Fixture()
        for case in data['cases']:
            with self.subTest(backend=case['request']['backend'],client=case['request']['client'],scenario=case['scenario']):
                estimate=fixture.domain.launch_memory_estimate(copy.deepcopy(case['request']),copy.deepcopy(case['model']),copy.deepcopy(case['resource']))
                decision=fixture.domain.session_memory_admission(copy.deepcopy(case['request']),[copy.deepcopy(case['model'])],copy.deepcopy(case['resource']),copy.deepcopy(case['hub']),copy.deepcopy(case['operation']))
                self.assertEqual(estimate,case['estimate']);self.assertEqual(decision,case['admission'])

    def test_rapid_native_target_bytes_and_separate_mtp_are_charged_once(self):
        fixture=Fixture()
        physical=fixture.domain.public_session_resource(snapshot())
        item=model('rapidmlx')
        item.update(size=50*GIB,mtpSidecarSize=7*GIB,
                    format='Slotstream MLX 4-bit + SSD',origins=['Other engine cache'],
                    slotstream={'ready':True})
        item['backends']['rapidmlx'].update(nativeWeightBytes=10*GIB,mtpSidecarBytes=GIB)
        before=copy.deepcopy(item)
        estimates={}
        for acceleration in ('off','mtp','auto'):
            estimates[acceleration]=fixture.domain.launch_memory_estimate(
                request('rapidmlx',acceleration=acceleration),item,physical)
            estimate=estimates[acceleration]
            self.assertEqual(estimate['modelBytes'],10*GIB)
            self.assertEqual(estimate['parallelLanes'],1)
            self.assertEqual(estimate['kvCacheBytes'],2*8*8192*4*128*2)
            self.assertEqual(estimate['runtimeReserveBytes'],
                             fixture.domain.policy.session_runtime_base_reserve_bytes+round(10*GIB*0.08))
        self.assertEqual(estimates['off']['companionBytes'],0)
        for acceleration in ('mtp','auto'):
            self.assertEqual(estimates[acceleration]['companionBytes'],GIB)
            self.assertEqual(estimates[acceleration]['companionLabels'],['MTP sidecar'])
            self.assertEqual(estimates[acceleration]['estimatedWorkingSetBytes'],
                             estimates['off']['estimatedWorkingSetBytes']+GIB)
        self.assertEqual(item,before,'Memory planning must leave the shared model record intact')
        # An integrated head is already charged in the native target shards.
        item['backends']['rapidmlx']['mtpSidecarBytes']=0
        integrated=fixture.domain.launch_memory_estimate(request('rapidmlx',acceleration='mtp'),item,physical)
        self.assertEqual(integrated['modelBytes'],10*GIB)
        self.assertEqual(integrated['companionBytes'],0)

    def test_missing_physical_schema_bool_capacity_and_pressure_only_do_not_gain_ready(self):
        fixture=Fixture()
        for raw in [snapshot(0,99,False),{'memoryAvailable':True,'totalBytes':48*GIB,'freePercent':99},
                    {**snapshot(),'memorySemanticsVersion':1},{**snapshot(),'reclaimableBytes':True},
                    {**snapshot(),'reclaimableMemorySource':'pressure-percent'}]:
            public=self.compare(fixture,'public_session_resource',raw)
            self.assertFalse(public['memoryAvailable'])
            for backend in ('kolibri','splash','uzu'):
                current=request(backend);item=model(backend)
                result=self.compare(fixture,'session_memory_admission',current,[item],public,{'phase':'idle'},{'active':False})
                self.assertFalse(result['launchable'])

    def test_live_receipt_conflict_and_operation_changes_are_rechecked_per_call(self):
        fixture=Fixture();physical=self.compare(fixture,'public_session_resource',snapshot())
        values=request('uzu');item=model('uzu')
        ready=fixture.domain.session_memory_admission(values,[item],physical,{'phase':'idle'},{'active':False})
        self.assertEqual(ready['decision'],'ready');fixture.records['uzu']=None
        blocked=fixture.domain.session_memory_admission(values,[item],physical,{'phase':'idle'},{'active':False})
        self.assertEqual(blocked['decision'],'qualification')
        fixture.conflict={'detail':'Generated independent runtime active'}
        whallm=fixture.domain.session_memory_admission(request('whallm'),[model('whallm')],physical,{'phase':'idle'},{'active':False})
        self.assertFalse(whallm['launchable'])
        fixture.operation={'active':True,'kind':'ane','detail':'Different private operation'}
        with self.assertRaises(RuntimeError):fixture.domain.require_live_model_load_admission(request('omlx'),[model('omlx')],purpose='benchmark')
        self.assertGreater(fixture.calls['verified'],1);self.assertGreater(fixture.calls['conflict'],0)

    def test_complete12_engine_estimates_and_admissions_for_all5_surfaces_and_pressure_active_edges(self):
        fixture=Fixture();routes=('omlx','mtplx','lmstudio','kolibri','splash','whallm','llamacpp','uzu','freetoken','swiftlm','mference','slotstream')
        for backend in routes:
            item=model(backend)
            for client in ('pi','omp','chat','opencode','codex'):
                for amount,pressure,known in [(40*GIB,10,True),(16*GIB,99,True),(3*GIB,99,True),(0,99,False)]:
                    raw=snapshot(amount,pressure,known);physical=self.compare(fixture,'public_session_resource',raw)
                    current=request(backend,client,context=16384 if backend=='splash' else 8192)
                    self.compare(fixture,'launch_memory_estimate',current,item,physical)
                    for phase,active in [('idle',False),('running',False),('idle',True)]:
                        with self.subTest(backend=backend,client=client,headroom=amount,phase=phase,active=active):
                            result=self.compare(fixture,'session_memory_admission',current,[item],physical,{'phase':phase},{'active':active})
                            self.assertEqual(result['route']['context'],current['context'])
                            self.assertEqual(result['route']['kv'],current['options']['kv'])
    def test_context_kv_parallel_companions_and_fixed_native_precision_are_exact(self):
        fixture=Fixture();physical=self.compare(fixture,'public_session_resource',snapshot())
        for backend in ('omlx','mtplx','lmstudio','uzu','kolibri'):
            item=model(backend);item['mtpSidecarSize']=GIB
            item['backends'][backend]['aneTuning']={'recommendation':{'cpu_enabled':True}}
            for context in (8192,65536,131072):
                for kv in ('off','q8','q6','q4'):
                    for acceleration in ('off','mtp','dflash'):
                        values=request(backend,context=context,kv=kv,acceleration=acceleration,parallel=16,anePrefill='tuned',dflashVerify='ddtree')
                        with self.subTest(backend=backend,context=context,kv=kv,acceleration=acceleration):
                            estimate=self.compare(fixture,'launch_memory_estimate',values,item,physical)
                            if backend=='uzu':self.assertEqual(estimate['kvPrecision'],'BF16 · runtime fixed')
                            if backend=='omlx' and acceleration=='dflash':self.assertEqual(estimate['kvPrecision'],'off')
    def test_remote_shared_unknown_geometry_native_sizing_and_qwen_ple_paths_match(self):
        fixture=Fixture();physical=self.compare(fixture,'public_session_resource',snapshot())
        scenarios=[]
        remote=model('freetoken');remote['remote']=True;scenarios.append(('freetoken',remote))
        shared=model('whallm');shared.pop('nativeWhallm');shared['sharedServer']=True;scenarios.append(('whallm',shared))
        missing=model('omlx');missing['memoryGeometry']={};scenarios.append(('omlx',missing))
        native=model('freetoken');native['backends']['freetoken']['nativeContract']['sizing']['kv_cache_bytes_per_token']=True;scenarios.append(('freetoken',native))
        ple=model('omlx');ple['qwen4Ple']={'supported':True,'residentBytes':30*GIB,'checkpointBytes':40*GIB,'pleBytes':10*GIB}
        ple['memoryGeometry']={'ready':True,'qwen4Qsa':True,'fullBytesPerToken':65536,'qsaAllocationStepTokens':8192}
        scenarios.append(('omlx',ple))
        for backend,item in scenarios:
            for context in (8192,65536,131072):
                for guard in ('balanced','high'):
                    values=request(backend,context=context,memoryGuard=guard,maxBatchSize=4)
                    self.compare(fixture,'launch_memory_estimate',values,item,physical)
                    self.compare(fixture,'session_memory_admission',values,[item],physical,{'phase':'idle'},{'active':False})
    def test_receipt_capacity_qualification_staged128k_and_live_sampling_never_cache_eligibility(self):
        fixture=Fixture()
        for backend in ('uzu','llamacpp','kolibri','splash','omlx'):
            item=model(backend)
            for context in (8192,65536,131072):
                values=request(backend,context=context)
                for present in (True,False):
                    fixture.records[backend]={'id':'fresh-'+backend,'createdAt':'generated','peakMemoryBytes':24*GIB} if present else None
                    for amount in (40*GIB,3*GIB):
                        fixture.snapshot=snapshot(amount)
                        result=self.compare(fixture,'route_qualification_memory_admission',values,[item])
                        self.assertFalse(result['privacy']['startsRuntime'])
        self.assertGreater(fixture.calls['snapshot'],1)
        item=model('kolibri');values=request('kolibri');fixture.snapshot=snapshot(40*GIB)
        first=fixture.domain.route_qualification_memory_admission(values,[item]);fixture.snapshot=snapshot(2*GIB)
        second=fixture.domain.route_qualification_memory_admission(values,[item])
        self.assertEqual(first['decision'],'ready');self.assertEqual(second['decision'],'pressure')
    def test_uzu_capacity_output_reuse_keeps_saved_receipt_and_staged_ceiling_guards(self):
        fixture=Fixture();item=model('uzu');item['backends']['uzu']['localBenchmarks']=[{'configuredOutputLimit':4096,'measuredRequestMaxTokens':128}]
        fixture.records['uzu']={'id':'saved-chat-capacity','createdAt':'generated','peakMemoryBytes':24*GIB,'configuredOutputLimit':4096}
        fixture.verified_output=4096
        receipt=self.compare(fixture,'_uzu_qualified_session_record',request('uzu',output=1024),item)
        self.assertEqual(receipt['configuredOutputLimit'],4096,"Capacity reuse never rewrites the stored output contract")
        self.assertEqual(fixture.records['uzu']['configuredOutputLimit'],4096)
        physical=self.compare(fixture,'public_session_resource',snapshot())
        values=request('uzu',context=131072,output=1024)
        staged=self.compare(fixture,'uzu_128k_staged_qualification_proof',values,item,physical)
        self.assertTrue(staged['required']);self.assertEqual(staged['receiptId'],'saved-chat-capacity')
        fixture.records['uzu']['peakMemoryBytes']=40*GIB
        over=self.compare(fixture,'uzu_128k_staged_qualification_proof',values,item,physical)
        self.assertFalse(over['ready']);self.assertEqual(over['reason'],'projected-ceiling')
        fixture.records['uzu']=None
        missing=self.compare(fixture,'uzu_128k_staged_qualification_proof',values,item,physical)
        self.assertFalse(missing['ready']);self.assertEqual(missing['reason'],'missing-64k-receipt')
        for value in (True,None,35*GIB,36*GIB,policy().uzu_process_memory_ceiling_bytes,40*GIB):
            self.assertEqual(resource.uzu_qualification_memory_ceiling_supported(value,ceiling=policy().uzu_process_memory_ceiling_bytes),fixture.legacy['uzu_qualification_memory_ceiling_supported'](value))

    def test_immediate_preload_owner_acknowledgement_and_automated_no_review_contract(self):
        fixture=Fixture();item=model('omlx');values=request('omlx')
        for purpose in ('benchmark','runtime-promotion','route-check','ane-tune','route-qualification','session-set'):
            for amount in (40*GIB,2*GIB):
                fixture.snapshot=snapshot(amount);fixture.operation={'active':True,'kind':resource_policy_kind(purpose)}
                outcomes=[]
                for call in (fixture.domain.require_live_model_load_admission,fixture.legacy['require_live_model_load_admission']):
                    try:outcomes.append(('value',call(copy.deepcopy(values),[copy.deepcopy(item)],purpose=purpose)))
                    except (RuntimeError,ValueError) as error:outcomes.append(('error',type(error).__name__,str(error)))
                self.assertEqual(outcomes[0],outcomes[1])
        for approved in (False,True):
            receipt={'launchable':True,'requiresAcknowledgement':True,'contractId':'exact-request','label':'Review','detail':'Original values'}
            payload={'memoryAcknowledgement':'exact-request' if approved else 'different'}
            for call in (resource.require_session_launch_admission,fixture.legacy['require_session_launch_admission']):
                if approved:self.assertIs(call(payload,receipt),receipt)
                else:
                    with self.assertRaises(ValueError):call(payload,receipt)


class ResourceRootIntegrationTests(unittest.TestCase):
    def root_ports(self, fixture):
        stack = ExitStack()
        for name, callback in fixture.ports.items():
            stack.enter_context(mock.patch.object(launcher, name, new=callback))
        stack.enter_context(mock.patch.object(
            launcher.kolibri_runtime, "memory_plan", new=fixture.kolibri))
        stack.enter_context(mock.patch.object(
            launcher.splash_runtime, "memory_estimate", new=fixture.splash))
        stack.enter_context(mock.patch.object(
            launcher, "MANAGER", SimpleNamespace(hub_snapshot=fixture.read_hub)))
        stack.enter_context(mock.patch.object(launcher, "_RESOURCE_ADMISSION", None))
        stack.enter_context(mock.patch.object(launcher, "_RESOURCE_ADMISSION_INPUTS", None))
        stack.enter_context(mock.patch.object(resource, "datetime", FixedDateTime))
        return stack

    def test_public_signatures_direct_helpers_and_source_freshness_are_preserved(self):
        fixture = Fixture()
        for name in META["functions"]:
            with self.subTest(function=name):
                original = inspect.signature(fixture.legacy[name])
                current = inspect.signature(getattr(launcher, name))
                parameters = lambda signature: [
                    (item.name, item.kind, item.default)
                    for item in signature.parameters.values()
                ]
                self.assertEqual(parameters(current), parameters(original))
        self.assertIn(ROOT / "resource_admission.py", launcher.CONTROLLER_SOURCE_PATHS)
        ready = {"launchable": True, "decision": "ready", "requiresAcknowledgement": False}
        cases = {
            "qwen4_qsa_allocation_high_water_tokens": (8193, 8192),
            "dflash_quantized_fallback": ("omlx", {"kv": "q6", "acceleration": "dflash"}),
            "effective_kv_precision": ("omlx", {"kv": "q6", "acceleration": "dflash", "dflashVerify": "ddtree"}),
            "uzu_estimate_within_process_ceiling": ({"estimatedWorkingSetBytes": 24 * GIB},),
            "uzu_qualification_memory_ceiling_supported": (36 * GIB,),
            "strict_model_load_admission_ready": (ready,),
            "route_qualification_admission_ready": (ready,),
            "require_session_launch_admission": ({}, ready),
        }
        with mock.patch.object(launcher, "_resource_admission_service",
                               side_effect=AssertionError("stateless helper constructed wiring")):
            for name, arguments in cases.items():
                with self.subTest(direct_helper=name):
                    self.assertEqual(getattr(launcher, name)(*copy.deepcopy(arguments)),
                                     fixture.legacy[name](*copy.deepcopy(arguments)))

    def test_cached_wiring_is_detached_and_rebuilds_only_for_policy_changes(self):
        with (mock.patch.object(launcher, "_RESOURCE_ADMISSION", None),
              mock.patch.object(launcher, "_RESOURCE_ADMISSION_INPUTS", None)):
            original = launcher._resource_admission_service()
            self.assertIs(launcher._resource_admission_service(), original)
            old_label = original.policy.backend_labels["kolibri"]
            with mock.patch.dict(launcher.BACKEND_LABELS, {"kolibri": "Generated changed label"}):
                changed = launcher._resource_admission_service()
                self.assertIsNot(changed, original)
                self.assertEqual(original.policy.backend_labels["kolibri"], old_label)
                self.assertEqual(changed.policy.backend_labels["kolibri"], "Generated changed label")
                self.assertIs(launcher._resource_admission_service(), changed)
            restored = launcher._resource_admission_service()
            self.assertIsNot(restored, changed)
            self.assertEqual(restored.policy.backend_labels["kolibri"], old_label)
            self.assertIs(launcher._resource_admission_service(), restored)

    def test_all180_frozen_records_match_root_facades_with_actual_cached_wiring(self):
        cases = json.loads((ROOT / "tests/fixtures/resource_admission_records.json").read_text())["cases"]
        fixture = Fixture()
        with self.root_ports(fixture):
            wiring = launcher._resource_admission_service()
            for case in cases:
                with self.subTest(backend=case["request"]["backend"],
                                  client=case["request"]["client"], scenario=case["scenario"]):
                    arguments = (case["request"], case["model"], case["resource"])
                    self.assertEqual(launcher.launch_memory_estimate(*copy.deepcopy(arguments)), case["estimate"])
                    admission = launcher.session_memory_admission(
                        copy.deepcopy(case["request"]), [copy.deepcopy(case["model"])],
                        copy.deepcopy(case["resource"]), copy.deepcopy(case["hub"]),
                        copy.deepcopy(case["operation"]))
                    self.assertEqual(admission, case["admission"])
            self.assertIs(launcher._resource_admission_service(), wiring)

    def test_cached_wiring_uses_new_live_callbacks_and_does_not_cache_admission(self):
        fixture = Fixture()
        with self.root_ports(fixture):
            wiring = launcher._resource_admission_service()
            with mock.patch.object(launcher, "apple_resource_snapshot", side_effect=[
                    snapshot(40 * GIB), snapshot(2 * GIB)]) as fresh_snapshot:
                result = launcher.require_live_model_load_admission(
                    request("omlx"), [model("omlx")], purpose="benchmark")
                self.assertEqual(result["decision"], "ready")
                with self.assertRaisesRegex(RuntimeError, "Capacity changed"):
                    launcher.require_live_model_load_admission(
                        request("omlx"), [model("omlx")], purpose="benchmark")
                self.assertEqual(fresh_snapshot.call_count, 2)
            physical = launcher.public_session_resource(snapshot())
            ready = launcher.session_memory_admission(
                request("uzu"), [model("uzu")], physical, {"phase": "idle"}, {"active": False})
            self.assertEqual(ready["decision"], "ready")
            fixture.records["uzu"] = None
            missing = launcher.session_memory_admission(
                request("uzu"), [model("uzu")], physical, {"phase": "idle"}, {"active": False})
            self.assertEqual(missing["decision"], "qualification")
            self.assertIs(launcher._resource_admission_service(), wiring)

def resource_policy_kind(purpose):return policy().model_load_owner_kinds[purpose]

if __name__=='__main__':unittest.main()
