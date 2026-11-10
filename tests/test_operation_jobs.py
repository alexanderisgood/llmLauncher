"""Complete temporary-operation snapshots match frozen generated lifetimes."""
import copy
from contextlib import ExitStack
import unittest
from unittest import mock
import route_check_jobs,ane_jobs
from tests.helpers.operation_jobs_harness import Fixture,FixedDateTime,FAKE_THREADS,FAKE_TIME,FAKE_UUID


def environment(module):
    stack=ExitStack()
    for name,value in {'threading':FAKE_THREADS,'time':FAKE_TIME,'datetime':FixedDateTime,'uuid':FAKE_UUID}.items():
        if hasattr(module,name):stack.enter_context(mock.patch.object(module,name,value))
    return stack


class OperationJobsTests(unittest.TestCase):
    def test_complete_route_success_advisory_and_tool_failure_snapshots_match(self):
        for case in ('pass','missing-usage','tool-fail','chat','empty-response'):
            with self.subTest(case=case):
                snapshots=[]
                for implementation in ('old','new'):
                    fixture=Fixture()
                    if case=='missing-usage':fixture.basic['usage']={'available':False}
                    if case=='tool-fail':fixture.tool['toolContractValid']=False
                    if case=='chat':fixture.plan.client='chat';fixture.report['request']['client']='chat'
                    if case=='empty-response':fixture.basic['contentCharacters']=0
                    with environment(route_check_jobs):
                        manager=fixture.legacy('route_check_jobs')['RouteCheckManager'](fixture.run) if implementation=='old' else fixture.route_manager()
                        job=manager.start({'confirmation':fixture.report['contractId']},[fixture.plan.model])
                        snapshots.append((job,manager.snapshot(),fixture.run.calls,fixture.probes,fixture.disposed))
                self.assertEqual(snapshots[0],snapshots[1])

    def test_complete_ane_positive_untraced_cpu_and_failure_snapshots_match(self):
        for case in ('accepted','no-trace','bad-recommendation','upstream-failed'):
            with self.subTest(case=case):
                snapshots=[]
                for implementation in ('old','new'):
                    fixture=Fixture()
                    if case=='bad-recommendation':fixture.recommendation['speedup_percent']=1
                    if case=='upstream-failed':fixture.upstream['status']='error';fixture.upstream['error']='Generated upstream failure'
                    with environment(ane_jobs):
                        legacy=fixture.legacy('ane_jobs') if implementation=='old' else None
                        manager=legacy['ANETunerManager'](fixture.run) if legacy else fixture.ane_manager()
                        manager._request_json=fixture.request
                        if case=='no-trace':manager._read_engine_log=lambda _plan:'No positive operation trace'
                        job=manager.start({},[fixture.plan.model])
                        snapshots.append((job,manager.snapshot(),fixture.records,fixture.run.calls,fixture.disposed))
                self.assertEqual(snapshots[0],snapshots[1])

    def test_complete_session_set_launch_reuse_restart_terminal_and_already_open_match(self):
        import session_set_jobs
        from tests.helpers.operation_jobs_harness import SessionFixture
        for mode in ('launch','reuse','restart','terminal','already-open'):
            with self.subTest(mode=mode):
                snapshots=[]
                for implementation in ('old','new'):
                    fixture=SessionFixture(mode)
                    with environment(session_set_jobs):
                        old=fixture.legacy() if implementation=='old' else None
                        plan=old['build_session_set_open_plan']({'id':'generated-set'},[]) if old else fixture.planner().build_session_set_open_plan({'id':'generated-set'},[])
                        manager=old['SessionSetRunner'](fixture.run) if old else fixture.runner()
                        # Inline launch publishes the generated owner before its wait.
                        original_start=fixture.run.start
                        def start(owner_plan):
                            original_start(owner_plan)
                            if hasattr(fixture.run,'state'):fixture.run.state={'phase':'running','message':'Generated resident owner'}
                        fixture.run.start=start
                        if not old:
                            from dataclasses import replace
                            manager.residence=replace(manager.residence,start=start)
                        result=manager.start({'id':'generated-set','confirmation':plan['confirmation']},[])
                        snapshots.append((plan,result,fixture.calls,fixture.run.calls))
                self.assertEqual(snapshots[0],snapshots[1])

    def test_complete_clone_plan_state_argv_and_generated_tensor_io_match(self):
        import tempfile,shutil,types
        from pathlib import Path
        from tests.helpers.operation_jobs_harness import CloneFixture
        with tempfile.TemporaryDirectory(prefix='operation-clone-') as folder:
            results=[]
            # Both implementations inspect the exact same source and destination.
            for implementation in ('old','new'):
                fixture=CloneFixture(folder) if implementation=='old' else fixture
                fixture.probes.clear()
                with environment(ane_jobs),mock.patch.object(ane_jobs.shutil,'disk_usage',return_value=types.SimpleNamespace(free=10**12)),mock.patch.object(ane_jobs.subprocess,'Popen',side_effect=fixture.spawn):
                    old=fixture.clone_legacy() if implementation=='old' else None
                    manager=old['ANEFP16CloneManager'](fixture.run) if old else fixture.clone_manager()
                    plan=manager.plan({'modelId':'generated-model'},[fixture.plan.model])
                    accepted=manager.start({'approved':True,'planId':plan['planId'],'confirmation':plan['confirmation']},[fixture.plan.model])
                    final=manager.snapshot();destination=Path(plan['destination'])
                    files={item.name:item.read_bytes() for item in destination.iterdir()}
                    results.append((plan,accepted,final,files,copy.deepcopy(fixture.probes)))
                shutil.rmtree(destination)
            old_calls,new_calls=results[0][4],results[1][4]
            self.assertEqual(old_calls[0][0][:3],new_calls[0][0][:3])
            self.assertEqual(new_calls[0][0][-1],old_calls[0][0][-1]+'/checkpoint',
                'The sole approved argv projection is the private owned-wrapper child')
            projected=copy.deepcopy(results[1]);projected[4][0][0][-1]=old_calls[0][0][-1]
            self.assertEqual(results[0],projected)

    def test_constructor_refusal_clears_publication_and_disposes_only_unaccepted_plans(self):
        import tempfile,types,session_set_jobs
        from tests.helpers.operation_jobs_harness import CloneFixture,SessionFixture
        for kind in ('route','ane','clone','session'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory(prefix='operation-constructor-') as folder:
                fixture=CloneFixture(folder) if kind=='clone' else SessionFixture('reuse') if kind=='session' else Fixture()
                module=session_set_jobs if kind=='session' else route_check_jobs if kind=='route' else ane_jobs
                with environment(module),mock.patch.object(FAKE_THREADS,'Thread',side_effect=RuntimeError('Generated constructor refusal')):
                    if kind=='route':manager=fixture.route_manager();payload={'confirmation':fixture.report['contractId']}
                    elif kind=='ane':manager=fixture.ane_manager();payload={}
                    elif kind=='session':
                        manager=fixture.runner();plan=fixture.planner().build_session_set_open_plan({'id':'generated-set'},[]);payload={'id':'generated-set','confirmation':plan['confirmation']}
                    else:
                        manager=fixture.clone_manager();plan=manager.plan({'modelId':'generated-model'},[fixture.plan.model]);payload={'approved':True,'planId':plan['planId'],'confirmation':plan['confirmation']}
                    models=[] if kind=='session' else [fixture.plan.model]
                    with self.assertRaisesRegex(RuntimeError,'constructor refusal'):manager.start(payload,models)
                self.assertIsNone(manager.thread);self.assertEqual(manager.snapshot()['phase'],'failed');self.assertFalse(manager.is_active())
                if kind in ('route','ane'):self.assertEqual(fixture.disposed,['generated-run']);self.assertEqual(fixture.run.calls,[])
                if kind=='session':self.assertEqual(fixture.leases,{})

    def test_ane_cancellation_at_final_wait_cannot_commit_a_recommendation(self):
        from tests.helpers.operation_jobs_harness import FastEvent
        class FinalCancellation(FastEvent):
            def __init__(self):super().__init__();self.waits=0
            def wait(self,timeout=None):
                if timeout==.2:
                    self.waits+=1
                    if self.waits==2:self.set()
                return self.value
        for implementation in ('old','new'):
            fixture=Fixture()
            with environment(ane_jobs),mock.patch.object(FAKE_THREADS,'Event',FinalCancellation):
                manager=fixture.legacy('ane_jobs')['ANETunerManager'](fixture.run) if implementation=='old' else fixture.ane_manager()
                manager._request_json=fixture.request;manager.start({},[fixture.plan.model])
            if implementation=='old':self.assertEqual(len(fixture.records),1,'Frozen original reproduces the late-cancel save')
            else:self.assertEqual(fixture.records,[]);self.assertEqual(manager.snapshot()['phase'],'cancelled')
            self.assertEqual(fixture.run.phase,'idle')

    def test_failed_owned_unload_cannot_enable_route_receipt_or_ane_record(self):
        from dataclasses import replace
        for kind in ('route','ane'):
            with self.subTest(kind=kind):
                fixture=Fixture();module=route_check_jobs if kind=='route' else ane_jobs
                with environment(module):
                    manager=fixture.route_manager() if kind=='route' else fixture.ane_manager()
                    original=manager.owner.clean_unload
                    manager.owner=replace(manager.owner,clean_unload=lambda plan:{**original(plan),'processGroupExited':False,'clean':False})
                    manager.start({'confirmation':fixture.report['contractId']} if kind=='route' else {},[fixture.plan.model])
                self.assertEqual(manager.snapshot()['phase'],'failed')
                self.assertIn('did not unload cleanly',manager.snapshot()['message'])
                if kind=='route':self.assertFalse(manager.snapshot()['result']['receipt']['ready']);self.assertFalse(manager.snapshot()['result']['temporaryRouteStopped'])
                else:self.assertEqual(fixture.records,[])

    def test_same_plan_new_epoch_is_never_stopped_by_old_temporary_job(self):
        for kind in ('route','ane'):
            with self.subTest(kind=kind):
                fixture=Fixture();module=route_check_jobs if kind=='route' else ane_jobs
                with environment(module):
                    manager=fixture.route_manager() if kind=='route' else fixture.ane_manager()
                    if kind=='route':
                        original=fixture.probe
                        def probe(plan,event,tool_probe=False,opener=None):
                            result=original(plan,event,tool_probe)
                            if tool_probe:fixture.run.epoch=object()
                            return result
                        from dataclasses import replace
                        manager.services=replace(manager.services,run_route_check_request=probe)
                    else:
                        def request(plan,path,*args,**kwargs):
                            result=fixture.request(plan,path,*args,**kwargs)
                            if path.endswith('/results'):fixture.run.epoch=object()
                            return result
                        manager._request_json=request
                    manager.start({'confirmation':fixture.report['contractId']} if kind=='route' else {},[fixture.plan.model])
                self.assertEqual(fixture.run.phase,'running');self.assertFalse(any(call[0]=='stop' for call in fixture.run.calls))
                self.assertEqual(manager.snapshot()['phase'],'failed');self.assertEqual(fixture.records,[])

    def test_session_same_run_id_new_epoch_cannot_attach_remaining_surfaces(self):
        import session_set_jobs
        from tests.helpers.operation_jobs_harness import SessionFixture
        fixture=SessionFixture('reuse');manager=fixture.runner()
        lease=fixture.acquire(fixture.run.plan.run_id);fixture.run.epoch=object()
        manager.state.update(jobId='generated-job',mode='reuse')
        with environment(session_set_jobs):manager._worker('generated-job',fixture.run.plan.run_id,'reuse',lease,[],[fixture.requests[1]])
        self.assertEqual(manager.snapshot()['phase'],'cancelled');self.assertFalse(any(call[0]=='attach' for call in fixture.calls))
        self.assertEqual(fixture.run.phase,'running');self.assertEqual(fixture.leases,{})

    def test_clone_receipt_cancel_source_and_collision_failures_preserve_foreign_files(self):
        import tempfile,json,types,os,shutil
        from pathlib import Path
        from dataclasses import replace
        from tests.helpers.operation_jobs_harness import CloneFixture
        for case in ('omitted','malformed','child-replaced','wrapper-replaced','late-collision','cancel','source-changed','capture-error'):
            with self.subTest(case=case),tempfile.TemporaryDirectory(prefix='owned-clone-negative-') as folder:
                fixture=CloneFixture(folder);manager=fixture.clone_manager();foreign=None;created=None
                with environment(ane_jobs):
                    plan=manager.plan({'modelId':'generated-model'},[fixture.plan.model]);destination=Path(plan['destination'])
                    original=fixture.capture
                    def capture(argv,**kwargs):
                        nonlocal foreign,created
                        child=Path(argv[-1]);created=child.parent
                        if case=='capture-error':raise RuntimeError('Generated capture failure')
                        if case in ('omitted','malformed'):
                            fixture.spawn(argv,cwd=str(kwargs['cwd']),env=kwargs['environment'],text=True)
                            if case=='malformed':kwargs['on_bytes'](b'{"event":"staging-created","device":true,"inode":1,"uid":1}\n')
                            else:kwargs['on_bytes'](b'{"event":"completed"}\n')
                            return types.SimpleNamespace(returncode=0)
                        result=original(argv,**kwargs)
                        if case=='child-replaced':
                            child.rename(child.parent/'owned-moved');child.mkdir();foreign=child/'foreign.txt';foreign.write_text('preserve')
                        elif case=='wrapper-replaced':
                            child.parent.rename(child.parent.with_name(child.parent.name+'-owned-moved'));child.parent.mkdir();foreign=child.parent/'foreign.txt';foreign.write_text('preserve')
                        elif case=='late-collision':
                            destination.mkdir();foreign=destination
                        elif case=='cancel':manager.cancel_event.set()
                        elif case=='source-changed':(fixture.source/'tokenizer.json').write_text('{"changed":"source"}')
                        return result
                    manager.services=replace(manager.services,io=replace(manager.services.io,capture=capture))
                    manager.start({'approved':True,'planId':plan['planId'],'confirmation':plan['confirmation']},[fixture.plan.model])
                self.assertEqual(manager.snapshot()['phase'],'cancelled' if case=='cancel' else 'failed')
                self.assertIsNone(manager.snapshot()['result'])
                if foreign is not None:self.assertTrue(foreign.exists())
                else:self.assertFalse(destination.exists())
                if case in ('cancel','source-changed','capture-error'):self.assertFalse(created.exists())
                if case in ('omitted','malformed'):self.assertTrue(created.exists(),'Unreceipted child is not adopted for deletion')

    def test_clone_preexisting_wrapper_and_native_exclusive_target_are_preserved(self):
        import tempfile,types
        from pathlib import Path
        from tests.helpers.operation_jobs_harness import CloneFixture
        with tempfile.TemporaryDirectory(prefix='owned-clone-collision-') as folder:
            fixture=CloneFixture(folder);manager=fixture.clone_manager()
            with environment(ane_jobs):
                plan=manager.plan({'modelId':'generated-model'},[fixture.plan.model])
                wrapper=Path(plan['destination']).parent/'.llm-launcher-fp16-generated-uuid';wrapper.mkdir();marker=wrapper/'foreign.txt';marker.write_text('preserve')
                manager.start({'approved':True,'planId':plan['planId'],'confirmation':plan['confirmation']},[fixture.plan.model])
            self.assertEqual(marker.read_text(),'preserve');self.assertEqual(manager.snapshot()['phase'],'failed')

    def test_helper_retained_staging_directory_prevents_redirected_writes_and_restores_cwd(self):
        import ast,os,tempfile,types,json,shutil
        from pathlib import Path
        helper_source=Path('ane_fp16_clone.py').read_text()
        functions=[node for node in ast.parse(helper_source).body if isinstance(node,ast.FunctionDef) and node.name=='clone_model']
        for point in ('copy','shard','rename','exception'):
            with self.subTest(point=point),tempfile.TemporaryDirectory(prefix='helper-fd-anchor-') as folder:
                root=Path(folder);source=root/'source';source.mkdir();destination=root/'stage'
                (source/'config.json').write_text('{}');(source/'model.safetensors').write_bytes(b'generated source tensor');(source/'extra.txt').write_text('source extra')
                moved=root/'created-stage';events=[];current_cwd=Path.cwd()
                def replace_staging():
                    if moved.exists():return
                    destination.rename(moved);destination.mkdir();(destination/'foreign.txt').write_text('preserve')
                class Tensor:
                    def __init__(self,dtype):self.dtype=dtype
                    def astype(self,dtype):return Tensor(dtype)
                class Handle:
                    def __enter__(self):return self
                    def __exit__(self,*_args):pass
                    def metadata(self):return {'preserved':'metadata'}
                class MX:
                    bfloat16='BF16';float16='F16'
                    @staticmethod
                    def load(_path):return {'float':Tensor('BF16'),'packed':Tensor('U32')}
                    @staticmethod
                    def save_safetensors(path,tensors,metadata):
                        if point=='shard':replace_staging()
                        Path(path).write_text(json.dumps({'dtypes':{name:value.dtype for name,value in tensors.items()},'metadata':metadata}))
                        if point=='exception':raise RuntimeError('Generated write failure')
                    @staticmethod
                    def clear_cache():pass
                def config(_source,target):
                    if point=='copy':replace_staging()
                    target.write_text('{"preserved":"config"}')
                namespace={'Path':Path,'os':os,'shutil':shutil,'mx':MX,'safe_open':lambda *_a,**_kw:Handle(),
                    'reject_symlinks':lambda _source:None,'validate_conversion':lambda _shards:None,'clone_config':config,
                    'emit':lambda event,**fields:events.append((event,fields))}
                exec(compile(ast.Module(body=functions,type_ignores=[]),'actual-clone-helper-function','exec'),namespace)
                original_replace=Path.replace
                def replaced(path,target):
                    if point=='rename':replace_staging()
                    return original_replace(path,target)
                with mock.patch.object(Path,'replace',replaced):
                    if point=='exception':
                        with self.assertRaisesRegex(RuntimeError,'write failure'):namespace['clone_model'](source,destination)
                    else:namespace['clone_model'](source,destination)
                self.assertEqual(Path.cwd(),current_cwd)
                receipt=next(fields for event,fields in events if event=='staging-created')
                created=moved if moved.exists() else destination
                self.assertEqual((receipt['device'],receipt['inode'],receipt['uid']),(created.stat().st_dev,created.stat().st_ino,created.stat().st_uid))
                if moved.exists():
                    self.assertEqual({item.name for item in destination.iterdir()},{'foreign.txt'});self.assertEqual((destination/'foreign.txt').read_text(),'preserve')
                    self.assertTrue((moved/'extra.txt').exists())
                self.assertEqual((source/'extra.txt').read_text(),'source extra')

    def test_parent_directory_replacement_never_certifies_or_cleans_foreign_target(self):
        import tempfile,os
        from pathlib import Path
        with tempfile.TemporaryDirectory(prefix='clone-parent-') as folder:
            root=Path(folder);parent=root/'models';parent.mkdir();target=parent/'clone'
            stage=ane_jobs._OwnedCloneStaging(target,'generated-job');child=stage.checkpoint;child.mkdir();(child/'owned.txt').write_text('owned')
            details=child.stat();stage.admit_child({'device':details.st_dev,'inode':details.st_ino,'uid':details.st_uid})
            parent.rename(root/'original-models');parent.mkdir();foreign=parent/'clone';foreign.mkdir();marker=foreign/'foreign.txt';marker.write_text('preserve')
            with self.assertRaisesRegex(ValueError,'parent changed'):stage.publish()
            self.assertFalse(stage.published);stage.cleanup();self.assertEqual(marker.read_text(),'preserve')

    def test_plan_bound_admin_cookies_bounded_errors_and_owner_requests(self):
        import io,json,types,urllib.error
        from dataclasses import replace
        from tests.helpers.operation_jobs_harness import Plan
        class Response:
            def __init__(self,data,cookies=()):self.data=data;self.headers=types.SimpleNamespace(get_all=lambda _name:list(cookies));self.closed=False;self.reads=[]
            def read(self,size):self.reads.append(size);return self.data[:size]
            def __enter__(self):return self
            def __exit__(self,*_args):self.closed=True
        fixture=Fixture();calls=[];cookies={};errors=[]
        def opener(request,timeout):
            calls.append(request)
            if request.full_url.endswith('/login'):return Response(b'{}',['omlx_admin_session=opaque; Path=/'])
            if not request.get_header('Cookie'):
                error=urllib.error.HTTPError(request.full_url,401,'Auth',None,io.BytesIO(b'{"detail":"Admin authentication required"}'));errors.append(error);raise error
            return Response(b'{"status":"completed"}')
        admin=ane_jobs.AneAdminClient(fixture.ane_policy,cookies,opener)
        first=Plan();second=Plan(run_id='replacement',secrets={'apiKey':'different-key'})
        self.assertEqual(admin._request_json(first,'/admin/results'),{'status':'completed'})
        self.assertEqual(admin._request_json(first,'/admin/results'),{'status':'completed'})
        self.assertEqual(admin._request_json(second,'/admin/results'),{'status':'completed'})
        self.assertEqual(sum(request.full_url.endswith('/login') for request in calls),2)
        self.assertTrue(all(error.fp.closed for error in errors));self.assertEqual(len(cookies),2)
        quota=replace(fixture.ane_policy,max_json=8)
        too_large=Response(b'x'*20)
        with self.assertRaisesRegex(RuntimeError,'oversized'):ane_jobs.AneAdminClient(quota,{},lambda *_a,**_kw:too_large)._request_json(first,'/admin/results')
        self.assertEqual(too_large.reads,[9]);self.assertTrue(too_large.closed)
        fixture.run.start(first);manager=fixture.ane_manager();manager.active_plan=first;manager.upstream_tuning_id='generated';manager.state['phase']='running'
        fixture.run.epoch=object();requests=[];manager._request_json=lambda *_a,**_kw:requests.append(1)
        manager.cancel();self.assertEqual(requests,[]);self.assertFalse(any(call[0]=='stop' for call in fixture.run.calls))

    def test_epoch_dispatch_fences_replacement_and_releases_lock_before_response(self):
        import threading,types,urllib.request
        from operation_contracts import EpochRequestDispatcher
        from tests.helpers.operation_jobs_harness import Plan,Cancelled
        owner_lock=threading.RLock();current={'owned':True};sent=[];connections=[]
        class Response:
            status=200;reason='OK';headers={}
            def read(self,size=-1):return b'{}'
            def close(self):pass
        class Connection:
            def __init__(self,*_a,**kwargs):self.sock=types.SimpleNamespace(settimeout=lambda _timeout:None);self.closed=False;connections.append(self)
            def connect(self):
                if current.get('replaceDuringConnect'):current['owned']=False
            def request(self,method,path,**kwargs):sent.append((method,path,kwargs))
            def getresponse(self):
                admitted=[]
                def stop():
                    with owner_lock:admitted.append(True)
                thread=threading.Thread(target=stop);thread.start();thread.join(.5)
                if not admitted:raise AssertionError('Response read held the mutation lock')
                return Response()
            def close(self):self.closed=True
        dispatcher=EpochRequestDispatcher(owner_lock,lambda _plan:current['owned'],Cancelled,Connection)
        plan=Plan();request=urllib.request.Request('http://127.0.0.1:18888/admin/results',data=b'{"exact":true}',headers={'Authorization':'Bearer generated'},method='POST')
        with dispatcher.open(plan,request,900) as response:self.assertEqual(response.read(),b'{}')
        self.assertEqual(sent[0][2]['body'],b'{"exact":true}');self.assertEqual(sent[0][2]['headers']['Authorization'],'Bearer generated');self.assertTrue(connections[-1].closed)
        sent.clear();current['replaceDuringConnect']=True
        with self.assertRaisesRegex(Cancelled,'epoch changed'):dispatcher.open(plan,request,900)
        self.assertEqual(sent,[]);self.assertTrue(connections[-1].closed)

    def test_session_stop_during_reserved_normalization_cannot_be_reset(self):
        import session_set_jobs
        from dataclasses import replace
        from tests.helpers.operation_jobs_harness import SessionFixture,Cancelled
        fixture=SessionFixture('launch');manager=fixture.runner();disposed=[];reserved=[]
        def normalized(request,models):
            reserved.append(manager.cancel_event);manager.cancel();return fixture.services.normalized_request(request,models)
        manager.services=replace(manager.services,normalized_request=normalized,dispose_plan_secrets=lambda plan:disposed.append(plan.run_id))
        with environment(session_set_jobs):
            plan=fixture.planner().build_session_set_open_plan({'id':'generated-set'},[])
            with self.assertRaisesRegex(Cancelled,'before model start'):manager.start({'id':'generated-set','confirmation':plan['confirmation']},[])
        self.assertEqual(fixture.run.calls,[]);self.assertEqual(fixture.calls,[]);self.assertEqual(disposed,['generated-run'])
        self.assertIs(manager.cancel_event,reserved[0]);self.assertTrue(manager.cancel_event.is_set());self.assertEqual(manager.snapshot()['phase'],'cancelled')

    def test_session_rejected_start_disposes_only_never_admitted_plan(self):
        import session_set_jobs
        from dataclasses import replace
        from tests.helpers.operation_jobs_harness import SessionFixture
        for accepted in (False,True):
            with self.subTest(accepted=accepted):
                fixture=SessionFixture('launch');manager=fixture.runner();disposed=[]
                def start(plan):
                    if accepted:fixture.run.start(plan)
                    raise RuntimeError('Generated start refusal')
                manager.residence=replace(manager.residence,start=start)
                manager.services=replace(manager.services,dispose_plan_secrets=lambda plan:disposed.append(plan.run_id))
                with environment(session_set_jobs):
                    plan=fixture.planner().build_session_set_open_plan({'id':'generated-set'},[])
                    with self.assertRaisesRegex(RuntimeError,'start refusal'):manager.start({'id':'generated-set','confirmation':plan['confirmation']},[])
                self.assertEqual(disposed,[] if accepted else ['generated-run'])
                self.assertEqual(fixture.run.phase,'running' if accepted else 'idle')
                self.assertFalse(any(call[0]=='attach' for call in fixture.calls))
                self.assertFalse(manager.is_active())

    def test_concurrent_session_starts_have_an_atomic_second_guard(self):
        import threading,types,session_set_jobs
        from tests.helpers.operation_jobs_harness import SessionFixture
        fixture=SessionFixture('reuse');manager=fixture.runner();barrier=threading.Barrier(2)
        original=manager.planner.build_session_set_open_plan
        def planned(*args,**kwargs):
            value=original(*args,**kwargs);barrier.wait(timeout=2);return value
        manager.planner.build_session_set_open_plan=planned
        confirmation=original({'id':'generated-set'},[])['confirmation'];outcomes=[]
        class PendingWorker:
            def __init__(self,*args,**kwargs):self.ident=1
            def start(self):pass
            def is_alive(self):return True
        fake=types.SimpleNamespace(RLock=threading.RLock,Event=threading.Event,Thread=PendingWorker,current_thread=threading.current_thread)
        def started():
            try:manager.start({'id':'generated-set','confirmation':confirmation},[]);outcomes.append('accepted')
            except ValueError:outcomes.append('rejected')
        with mock.patch.object(session_set_jobs,'threading',fake):
            threads=[threading.Thread(target=started) for _ in range(2)]
            for thread in threads:thread.start()
            for thread in threads:thread.join(3)
        self.assertEqual(sorted(outcomes),['accepted','rejected']);self.assertEqual(len(fixture.leases),1)
        self.assertEqual(manager.snapshot()['phase'],'attaching');self.assertFalse(any(call[0]=='attach' for call in fixture.calls))

    def test_route_epoch_change_after_basic_never_issues_tool_probe(self):
        from dataclasses import replace
        fixture=Fixture();manager=fixture.route_manager()
        original=fixture.probe
        def probe(plan,event,tool_probe=False,opener=None):
            value=original(plan,event,tool_probe);fixture.run.epoch=object();return value
        manager.services=replace(manager.services,run_route_check_request=probe)
        with environment(route_check_jobs):manager.start({'confirmation':fixture.report['contractId']},[fixture.plan.model])
        self.assertEqual(fixture.probes,[False]);self.assertNotEqual(manager.snapshot()['phase'],'completed')
        self.assertFalse(any(call[0]=='stop' for call in fixture.run.calls))

    def test_complete_frozen_fixtures_and_public_helper_signatures_remain_bound(self):
        import ast,hashlib,inspect,json,session_set_jobs
        from pathlib import Path
        from tests.helpers.operation_jobs_harness import SessionFixture
        fixtures=Path(__file__).with_name('fixtures')
        expected={'route_check_jobs_legacy.py':'34031db0fefa7e532cf6e03e70546f93da57a994366aa0e17e42e8907d28222b',
            'ane_jobs_legacy.py':'097758d9900fef11a9f15cf7f42f2133b82bae0e495819aa9d21e75032c1f09e',
            'session_set_jobs_legacy.py':'ae4ae7b9c1925b039aab8a5e2db814364614d32c4b2f32854df2554722eac210'}
        for name,digest in expected.items():self.assertEqual(hashlib.sha256((fixtures/name).read_bytes()).hexdigest(),digest)
        fixture=Fixture();old_route=fixture.legacy('route_check_jobs');old_ane=fixture.legacy('ane_jobs');session=SessionFixture();old_set=session.legacy()
        bindings={'route_check_plan':fixture.route_manager().planner.route_check_plan,'route_verification_identity':fixture.route_manager().planner.route_verification_identity,
            'sanitize_ane_snapshot':ane_jobs.sanitize_ane_snapshot,'ane_execution_proof':ane_jobs.ane_execution_proof,'_finite_number':ane_jobs._finite_number,
            'ane_fp16_clone_destination':ane_jobs.ane_fp16_clone_destination,'regular_directory_inventory':ane_jobs.regular_directory_inventory,
            'valid_ane_recommendation':ane_jobs.AneProof(fixture.ane_policy,fixture.ane_services.runtime).valid_ane_recommendation,
            'verified_ane_tuning_record':ane_jobs.AneProof(fixture.ane_policy,fixture.ane_services.runtime).verified_ane_tuning_record,
            'matching_ane_tuning_record':ane_jobs.AneProof(fixture.ane_policy,fixture.ane_services.runtime).matching_ane_tuning_record,
            'build_session_set_open_plan':session.planner().build_session_set_open_plan,'_session_set_record_for_id':session.planner()._session_set_record_for_id,
            '_session_set_surface_signature':session.planner()._session_set_surface_signature,'public_session_set_open_plan':session_set_jobs.public_session_set_open_plan}
        for name,current in bindings.items():
            old=old_route.get(name) or old_ane.get(name) or old_set.get(name)
            # The route manager’s test planner stub is intentionally variadic; its real class is the API.
            if name=='route_check_plan':
                current=route_check_jobs.RouteCheckPlanner(fixture.policy,fixture.services).route_check_plan
                old=old_route['frozen_route_check_plan']
            self.assertEqual([(p.name,p.kind,p.default) for p in inspect.signature(old).parameters.values()],
                [(p.name,p.kind,p.default) for p in inspect.signature(current).parameters.values()],name)
        for module in (route_check_jobs,ane_jobs,session_set_jobs):
            imports=[alias.name for node in ast.parse(Path(module.__file__).read_text()).body if isinstance(node,ast.Import) for alias in node.names]
            self.assertNotIn('launcher',imports)

    def test_importing_operations_starts_no_process_network_or_file_mutation(self):
        import subprocess,sys
        from pathlib import Path
        code='''import builtins,pathlib,subprocess,sys,urllib.request
sys.path.insert(0,sys.argv[1]);original=builtins.__import__
def guarded(name,*a,**kw):
 if name=='launcher':raise AssertionError('controller import')
 return original(name,*a,**kw)
builtins.__import__=guarded
def forbidden(*a,**kw):raise AssertionError('import side effect')
subprocess.Popen=forbidden;urllib.request.urlopen=forbidden;pathlib.Path.write_text=forbidden;pathlib.Path.write_bytes=forbidden
import operation_contracts,route_check_jobs,ane_jobs,session_set_jobs
assert 'launcher' not in sys.modules
'''
        result=subprocess.run([sys.executable,'-I','-B','-c',code,str(Path(route_check_jobs.__file__).parent)],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
