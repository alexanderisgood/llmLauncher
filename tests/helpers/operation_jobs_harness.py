"""Named generated ports for complete temporary-operation proofs; no model starts."""
from __future__ import annotations
import ast,copy,hashlib,json,math,os,re,shutil,signal,stat,subprocess,threading,time,types,urllib.error,urllib.request,uuid
from datetime import datetime,timezone,timedelta
from pathlib import Path
from dataclasses import dataclass
import __future__
import launcher
import route_check_jobs,ane_jobs,session_set_jobs
from operation_contracts import TemporaryRunOwner

class Cancelled(RuntimeError):pass
class FastEvent:
    def __init__(self):self.value=False
    def set(self):self.value=True
    def is_set(self):return self.value
    def wait(self,_timeout=None):return self.value
class InlineThread:
    def __init__(self,target,args=(),**_kwargs):self.target,self.args=target,args;self.ident=1
    def start(self):self.target(*self.args)
    def is_alive(self):return False
    def join(self,timeout=None):pass
FAKE_THREADS=types.SimpleNamespace(RLock=threading.RLock,Event=FastEvent,Thread=InlineThread,current_thread=threading.current_thread)
class FixedDateTime(datetime):
    @classmethod
    def now(cls,tz=None):return cls(2026,10,7,12,0,0,tzinfo=tz)
FAKE_TIME=types.SimpleNamespace(monotonic=lambda:0,time=lambda:1000,strftime=lambda fmt,*_args:'2026-10-07T12:00:00Z' if '%Y' in fmt else '12:00:00',gmtime=lambda:None,sleep=lambda _seconds:None)
FAKE_UUID=types.SimpleNamespace(uuid4=lambda:'generated-uuid')

@dataclass
class Plan:
    run_id:str='generated-run'
    backend:str='omlx'
    client:str='pi'
    context:int=8192
    output:int=256
    reasoning:str='auto'
    port:int=18888
    project:str='/generated/project'
    run_dir:Path|None=Path('/generated/run')
    model:dict|None=None
    options:dict|None=None
    secrets:dict|None=None
    def __post_init__(self):
        if self.model is None:self.model={'id':'generated-model','name':'Generated checkpoint','servedId':'served-generated'}
        if self.options is None:self.options={'acceleration':'off','kv':'off'}
        if self.secrets is None:self.secrets={'apiKey':'generated-secret'}

class Run:
    def __init__(self):self.plan=None;self.phase='idle';self.calls=[];self.epoch=object();self.accepted_plan=None;self.accepted_epoch=None
    def snapshot(self):return {'phase':self.phase,'message':'Generated owned runtime'}
    def start(self,plan):self.calls.append(('start',plan.run_id));self.plan=plan;self.phase='running';self.epoch=object();self.accepted_plan=plan;self.accepted_epoch=self.epoch
    def stop(self,**_kwargs):self.calls.append(('stop',self.plan.run_id if self.plan else None));self.plan=None;self.phase='idle'
    def port(self):
        def stop(*,expected_plan):
            if self.plan is expected_plan and self.epoch is self.accepted_epoch:self.stop()
        return TemporaryRunOwner(self.snapshot,self.start,lambda plan:self.plan is plan and self.epoch is self.accepted_epoch,stop,
            lambda plan:{'clean':self.phase=='idle','processExited':True,'processGroupExited':True,'managerIdle':self.phase=='idle','portsClosed':True,'checkedPorts':[plan.port],'closedPorts':[plan.port]},lambda plan:plan is self.accepted_plan,lambda *_a,**_kw:(_ for _ in ()).throw(AssertionError('Unexpected generated network request')))


class GeneratedTemporaryOwnerAdapter:
    """Pure controller-test owner port; no fabricated native process is exported.

    Its receipt describes this generated callback lifetime only. Actual Root
    kernel/epoch dispatch and cleanup authority are tested in operation_bridges.
    """
    def __init__(self, run):
        self.run, self.accepted, self.epoch, self.retired = run, None, None, False
    def start(self, plan):
        self.run.start(plan)
        if self.run.plan is not plan:
            raise AssertionError('Generated start did not admit the exact plan')
        self.accepted, self.epoch, self.retired = plan, object(), False
    def owns(self, plan):
        return self.accepted is plan and self.run.plan is plan and not self.retired
    def stop(self, *, expected_plan):
        if self.owns(expected_plan):
            self.run.stop()
            self.retired = self.run.plan is None
    def clean(self, plan):
        clean = self.accepted is plan and self.retired and self.run.plan is None and self.run.snapshot()['phase'] == 'idle'
        return {'clean':clean,'processExited':clean,'processGroupExited':clean,'managerIdle':clean,
                'portsClosed':clean,'checkedPorts':[plan.port],'closedPorts':[plan.port] if clean else []}
    def port(self):
        return TemporaryRunOwner(self.run.snapshot,self.start,self.owns,self.stop,self.clean,
            lambda plan:self.accepted is plan,
            lambda *_a,**_kw:(_ for _ in ()).throw(AssertionError('Unexpected generated network request')))

class Fixture:
    def __init__(self):
        self.run=Run();self.disposed=[];self.records=[];self.probes=[];self.plan=Plan();self.job={'id':'generated-job','modelId':'generated-model','model':'Generated checkpoint','modelFingerprint':'a'*64,'runtimeVersion':'0.6.4','hardwareFingerprint':'generated-hardware','cpuAssist':False}
        self.basic={'protocol':'chat-completions','accepted':True,'streamed':True,'eventCount':3,'contentCharacters':5,'reasoningCharacters':0,
            'terminalState':'complete','terminalComplete':True,'usage':{'available':True,'promptTokens':12,'completionTokens':2},'firstOutputSeconds':.1,'totalSeconds':.2}
        self.tool={**self.basic,'contentCharacters':0,'toolContractValid':True,'toolCall':True,'toolCallCount':1,'toolContractDetail':'Exact synthetic schema passed'}
        self.report={'ready':True,'contractId':'generated-route-contract','request':{'backend':'omlx','client':'pi','modelId':'generated-model'},
            'checks':[{'id':id,'label':id,'status':'pending','detail':'Generated'} for id in ('surface','model','protocol','stream','tools','usage','reasoning')],
            'identity':{'id':'generated-identity','runtimeVersion':'0.6.4'}}
        self.policy=route_check_jobs.RouteCheckPolicy(launcher.ROUTE_CHECK_VERSION,launcher.ROUTE_CHECK_RECEIPT_VERSION,
            launcher.ROUTE_CHECK_RECEIPT_TTL_SECONDS,launcher.ROUTE_CHECK_MAX_TOKENS,launcher.ROUTE_CHECK_TOOL_NAME,launcher.ADAPTER_SCHEMA_VERSION,
            launcher.BACKEND_LABELS,launcher.CLIENT_LABELS,
            {key:route_check_jobs.ClientDescriptor(value.id,value.label,value.protocol,value.built_in) for key,value in launcher.CLIENT_ADAPTERS.items()},
            {key:route_check_jobs.EngineDescriptor(value.id,value.binary_key) for key,value in launcher.ENGINE_ADAPTERS.items()})
        self.services=route_check_jobs.RouteCheckServices(lambda *_a,**_kw:{},lambda _runtime:None,self.normalize,self.admission,self.payload,self.dispose,self.probe,Cancelled)
        self.ane_policy=ane_jobs.AnePolicy(launcher.ANE_TUNER_SEQUENCE_LENGTH,launcher.ANE_TUNER_REPEATS,launcher.ANE_TUNER_MINIMUM_SPEEDUP_PERCENT,launcher.ANE_TUNER_MINIMUM_RUNTIME,launcher.MAX_JSON)
        self.ane_services=ane_jobs.AneServices(
            ane_jobs.AneRuntimeServices(lambda _key:None,lambda _path:'0.6.4',lambda _path:None,launcher.omlx_version_at_least,lambda:'generated-hardware'),
            ane_jobs.AneArtifactServices(lambda *_a:{},lambda *_a:{},lambda *_a:{},lambda *_a:'a'*64,lambda *_a:(True,'Ready',128),lambda *_a:(True,{},[])),
            ane_jobs.AneIO(lambda _path:{},lambda *_a:'[benchmark-ane-profile] operations=42 configured_layers=4',str,lambda _path:10**12,lambda:Path('/generated/helper.py'),lambda:Path('/generated'),lambda *_a,**_kw:None,lambda:{},lambda *_a,**_kw:None),
            ane_jobs.AneJobServices(lambda *_a:(copy.deepcopy(self.plan.model),copy.deepcopy(self.plan),copy.deepcopy(self.job)),self.admission,self.payload,self.dispose,self.records.append,Cancelled))
        self.recommendation={'enabled':True,'gdn_enabled':False,'cpu_enabled':False,'cpu_shared_resource':False,'sequence_length':launcher.ANE_TUNER_SEQUENCE_LENGTH,
            'mlp_fraction':.4,'gdn_fraction':0,'cpu_fraction':0,'cpu_down_fraction':0,'cpu_gdn_fraction':0,'processing_tps':128,'speedup_percent':5,'cpu_threads':1}
        self.upstream={'tuning_id':'generated-tuning','status':'completed','phase':'completed','message':'Generated measured result','current':1,'total':1,'results':[],'recommendation':self.recommendation}
    def normalize(self,*_args,**_kwargs):return copy.deepcopy(self.plan)
    def admission(self,*_args,**_kwargs):return {'decision':'ready','launchable':True,'requiresAcknowledgement':False}
    def payload(self,plan):return {'backend':plan.backend,'client':plan.client,'modelId':plan.model['id'],'context':plan.context,'output':plan.output,'reasoning':plan.reasoning,'options':copy.deepcopy(plan.options)}
    def dispose(self,plan):self.disposed.append(plan.run_id)
    def probe(self,plan,_event,tool_probe=False,opener=None):self.probes.append(tool_probe);return copy.deepcopy(self.tool if tool_probe else self.basic)
    def route_manager(self):
        manager=route_check_jobs.RouteCheckManager(self.run.port(),self.policy,self.services)
        manager.planner.route_check_plan=lambda *_args,**_kwargs:copy.deepcopy(self.report)
        return manager
    def request(self,_plan,path,*_args,**_kwargs):return {'tuning_id':'generated-tuning'} if path.endswith('/start') else copy.deepcopy(self.upstream)
    def ane_manager(self):
        manager=ane_jobs.ANETunerManager(self.run.port(),self.ane_policy,self.ane_services,types.SimpleNamespace(_request_json=self.request))
        return manager
    def legacy(self,kind):
        namespace={'Any':object,'RunManager':Run,'LaunchPlan':Plan,'LaunchCancelled':Cancelled,'Path':Path,'copy':copy,'hashlib':hashlib,'json':json,'math':math,'os':os,'re':re,'shutil':shutil,'signal':signal,'stat':stat,'subprocess':subprocess,
            'datetime':FixedDateTime,'timezone':timezone,'timedelta':timedelta,'threading':FAKE_THREADS,'time':FAKE_TIME,'uuid':FAKE_UUID,'urllib':urllib,
            **{key:getattr(launcher,key) for key in ('BACKEND_LABELS','CLIENT_LABELS','CLIENT_ADAPTERS','ENGINE_ADAPTERS','ADAPTER_SCHEMA_VERSION','ROUTE_CHECK_RECEIPT_VERSION','ROUTE_CHECK_RECEIPT_TTL_SECONDS','ROUTE_CHECK_MAX_TOKENS','ROUTE_CHECK_TOOL_NAME','ROUTE_CHECK_VERSION','ANE_TUNER_SEQUENCE_LENGTH','ANE_TUNER_REPEATS','ANE_TUNER_MINIMUM_SPEEDUP_PERCENT','ANE_TUNER_MINIMUM_RUNTIME','MAX_JSON')},
            'BINARIES':{},'route_check_plan':lambda *_a,**_kw:copy.deepcopy(self.report),'normalized_request':self.normalize,'_session_set_plan_payload':self.payload,
            'require_live_model_load_admission':self.admission,'dispose_plan_secrets':self.dispose,'run_route_check_request':self.probe,
            'validated_ane_tuning_request':lambda *_a:(copy.deepcopy(self.plan.model),copy.deepcopy(self.plan),copy.deepcopy(self.job)),'save_ane_tuning_record':self.records.append,
            'read_log_tail':lambda *_a:'[benchmark-ane-profile] operations=42 configured_layers=4','hardware_fingerprint':lambda:'generated-hardware','omlx_version_at_least':launcher.omlx_version_at_least}
        fixture=Path(__file__).resolve().parents[1]/'fixtures'/f'{kind}_legacy.py'
        exec(compile(fixture.read_text(),str(fixture),'exec',flags=__future__.annotations.compiler_flag),namespace)
        if kind=='route_check_jobs':
            namespace['frozen_route_check_plan']=namespace['route_check_plan']
            namespace['route_check_plan']=lambda *_a,**_kw:copy.deepcopy(self.report)
        return namespace

class SessionFixture:
    def __init__(self,mode='launch'):
        from operation_contracts import SessionResidence,ResidenceSnapshot,SurfaceSnapshot,SessionLease
        self.run=Run();self.base={'backend':'omlx','client':'chat','agentHost':'launcher','modelId':'generated-model','project':'/generated/project','context':8192,'output':256,'reasoning':'auto','options':{'acceleration':'off','kv':'off'}}
        self.requests=[copy.deepcopy(self.base),{**copy.deepcopy(self.base),'client':'pi','agentHost':'console'}]
        self.record={'id':'generated-set','name':'Generated set','createdAt':'generated-created','updatedAt':'generated-updated','modelName':'Generated checkpoint','baseRequest':copy.deepcopy(self.base)}
        self.attachments=[];self.calls=[];self.opening=False;self.differences=[];self.leases={}
        self.hub={'phase':'idle','active':False}
        self.operation={'active':False,'kind':'idle'}
        if mode!='launch':
            self.run.start(Plan(client='chat'));self.hub={'phase':'running','active':True,'session':{'runId':self.run.plan.run_id}}
            self.operation={'active':True,'kind':'session'}
            self.attachments=[types.SimpleNamespace(plan=copy.deepcopy(self.run.plan),status='ready')]
            if mode=='already-open':self.attachments.append(types.SimpleNamespace(plan=Plan(client='pi'),status='running'))
            if mode=='restart':self.attachments.append(types.SimpleNamespace(plan=Plan(client='pi'),status='stopped'))
            if mode=='terminal':self.attachments.append(types.SimpleNamespace(plan=Plan(client='pi'),status='handoff'))
        def payload(plan):
            value={**copy.deepcopy(self.base),'client':plan.client,'agentHost':'launcher' if plan.client=='chat' else 'console'}
            if mode=='terminal' and plan.client=='pi':value['agentHost']='terminal'
            return value
        self.plan_payload=payload
        self.residence=SessionResidence(lambda:copy.deepcopy(self.hub),lambda *_a:{'differences':copy.deepcopy(self.differences),'engineResident':True},
            lambda:[SurfaceSnapshot(a.plan.run_id,self.plan_payload(a.plan),a.status) for a in self.attachments],lambda value:self.calls.append(('validate',copy.deepcopy(value))),
            self.run.start,lambda:ResidenceSnapshot(self.run.plan.run_id if self.run.plan else '',self.run.phase,'Generated resident owner'),self.attach,self.restart,
            self.acquire,self.leased_snapshot,self.attach_leased,self.restart_leased,lambda lease:self.leases.pop(lease.token,None),lambda plan:plan is self.run.accepted_plan)
        self.policy=session_set_jobs.SessionSetPolicy(launcher.SESSION_SET_STATUS_VERSION,launcher.SESSION_SET_PLAN_VERSION,launcher.SURFACE_ATTACHMENT_MAX,launcher.SESSION_SET_ENGINE_KEYS,launcher.BACKEND_LABELS,launcher.CLIENT_LABELS)
        def normal(value,models):return Plan(client=value['client'])
        self.services=session_set_jobs.SessionSetServices(lambda value:str(value),lambda:[copy.deepcopy(self.record)],lambda value,_models:copy.deepcopy(value),lambda *_a:copy.deepcopy(self.requests),self.surface_request,
            lambda value,_models:copy.deepcopy(value),lambda *_a,**_kw:{'admission':{'launchable':True,'requiresAcknowledgement':False,'contractId':'generated-memory'}},
            lambda _hub:copy.deepcopy(self.operation),lambda:self.opening,normal,lambda *_a,**_kw:{'decision':'ready','launchable':True,'requiresAcknowledgement':False},lambda _plan:None,Cancelled)
    def acquire(self,owner_id):
        from operation_contracts import SessionLease
        if self.run.plan is None or self.run.plan.run_id!=owner_id:raise Cancelled('The resident owner changed')
        lease=SessionLease(owner_id,object());self.leases[lease.token]=(self.run.plan,self.run.epoch);return lease
    def leased_snapshot(self,lease):
        from operation_contracts import ResidenceSnapshot
        plan,epoch=self.leases[lease.token]
        if self.run.plan is not plan or self.run.epoch is not epoch:raise Cancelled('The resident epoch changed')
        return ResidenceSnapshot(plan.run_id,self.run.phase,'Generated resident owner')
    def attach_leased(self,lease,value):self.leased_snapshot(lease);return self.attach(value)
    def restart_leased(self,lease,value):self.leased_snapshot(lease);return self.restart(value)
    def surface_request(self,value):return {key:copy.deepcopy(value[key]) for key in ('client','agentHost','project') if key in value}
    def attach(self,value):self.calls.append(('attach',copy.deepcopy(value)));return {'surfaceId':'attached-generated','ownerRunId':value['ownerRunId']}
    def restart(self,value):self.calls.append(('restart',copy.deepcopy(value)));return {'surfaceId':value['surfaceId'],'ownerRunId':value['ownerRunId']}
    def planner(self):return session_set_jobs.SessionSetPlanner(self.policy,self.services,self.residence)
    def runner(self):return session_set_jobs.SessionSetRunner(self.residence,self.policy,self.services)
    def legacy(self):
        fixture=Path(__file__).resolve().parents[1]/'fixtures'/'session_set_jobs_legacy.py'
        manager=types.SimpleNamespace(hub_snapshot=self.residence.hub_snapshot,warm_route_plan=self.residence.warm_route_plan,
            lock=threading.RLock(),attachments={str(i):a for i,a in enumerate(self.attachments)},plan=self.run.plan,
            _validated_attachment_target=self.residence.validate_target)
        self.run.hub_snapshot=self.residence.hub_snapshot
        self.run.lock=threading.RLock();self.run.state={'phase':self.run.phase,'message':'Generated resident owner'}
        self.run.attach_surface=self.attach;self.run.restart_agent_console=self.restart
        namespace={'Any':object,'RunManager':Run,'copy':copy,'hashlib':hashlib,'json':json,'secrets':__import__('secrets'),'time':FAKE_TIME,'threading':FAKE_THREADS,'uuid':FAKE_UUID,'LaunchCancelled':Cancelled,
            'MANAGER':manager,'SESSION_SETS':types.SimpleNamespace(is_active=lambda:self.opening),'SESSION_OPERATION_LOCK':threading.RLock(),
            **{key:getattr(launcher,key) for key in ('SESSION_SET_STATUS_VERSION','SESSION_SET_PLAN_VERSION','SURFACE_ATTACHMENT_MAX','SESSION_SET_ENGINE_KEYS','BACKEND_LABELS','CLIENT_LABELS')},
            '_profile_identifier':self.services.identifier,'load_session_sets':self.services.load_records,'validated_session_set_record':self.services.validate_record,
            'session_set_requests':self.services.requests,'_session_set_surface_from_request':self.services.surface_request,'_session_set_plan_payload':self.plan_payload,
            'validated_launch_profile_request':self.services.validate_launch_request,'session_dashboard_plan':self.services.dashboard_plan,'active_launcher_operation':self.services.active_operation,
            'normalized_request':self.services.normalized_request,'require_live_model_load_admission':self.services.require_live_admission,'dispose_plan_secrets':self.services.dispose_plan_secrets}
        exec(compile(fixture.read_text(),str(fixture),'exec',flags=__future__.annotations.compiler_flag),namespace)
        return namespace

def write_tensor_file(path,dtype='BF16',shape=(2,2)):
    import struct
    widths={'BF16':2,'F16':2,'U32':4};data={};offset=0
    for name,kind,dimensions in [('norm.weight',dtype,list(shape)),('packed.weight','U32',[2,2])]:
        count=math.prod(dimensions)*widths[kind];data[name]={'dtype':kind,'shape':dimensions,'data_offsets':[offset,offset+count]};offset+=count
    header=json.dumps(data,separators=(',',':')).encode();path.write_bytes(struct.pack('<Q',len(header))+header+b'\0'*offset)

class CloneFixture(Fixture):
    def __init__(self,folder):
        super().__init__();self.root=Path(folder);self.source=self.root/'Generated-q4';self.source.mkdir()
        self.helper=self.root/'generated_clone_helper.py';self.helper.write_text('Generated helper identity\n')
        self.config={'model_type':'generated-dense','quantization':{'bits':4,'group_size':64}}
        (self.source/'config.json').write_text(json.dumps(self.config));(self.source/'tokenizer.json').write_text('{"preserved":"tokenizer"}')
        write_tensor_file(self.source/'model.safetensors')
        self.plan.model={'id':'generated-model','name':'Generated checkpoint','path':str(self.source),'format':'mlx','ready':True,
            'backends':{'omlx':{'runnable':True,'benchmarkModelFingerprint':self.fingerprint(self.source,self.config)}}}
        self.clone_policy=ane_jobs.ClonePolicy(launcher.ANE_FP16_CLONE_DISK_RESERVE_BYTES,launcher.ANE_FP16_CLONE_PLAN_TTL_SECONDS,launcher.ANE_FP16_CLONE_SOURCE_URL,launcher.ANE_TUNER_MINIMUM_RUNTIME)
        from dataclasses import replace
        self.ane_services=replace(self.ane_services,
            runtime=replace(self.ane_services.runtime,selected_binary=lambda _key:'/generated/omlx',runtime_python=lambda _binary:'/generated/python'),
            artifacts=replace(self.ane_services.artifacts,clone_source_profile=self.source_profile,cpu_sharing_profile=self.cpu_profile,
                quantization_profile=lambda _cfg:{'compatible':True},model_fingerprint=self.fingerprint,weight_completeness=lambda *_a:(True,'Ready',128),tensor_inventory=launcher.safetensors_inventory),
            io=replace(self.ane_services.io,read_json=lambda path:json.loads(path.read_text()),helper_path=lambda:self.helper,app_directory=lambda:self.root,spawn=self.spawn,capture=self.capture))
    def fingerprint(self,path,_config):return hashlib.sha256(b''.join(name.encode()+item.read_bytes() for name,item in sorted((p.name,p) for p in path.iterdir() if p.is_file()))).hexdigest()
    def cpu_profile(self,path):
        valid,tensors,_files=launcher.safetensors_inventory(path);floats=sorted({v['dtype'] for v in tensors.values() if v['dtype'] in ('F16','BF16')})
        return {'eligible':valid and floats==['F16'],'profileFingerprint':hashlib.sha256(json.dumps(tensors,sort_keys=True).encode()).hexdigest(),'floatDtypes':floats,'gateUpScalePairs':2}
    def source_profile(self,path,_config,_weight):
        profile=self.cpu_profile(path)
        return {'eligible':True,'sourceTensorFingerprint':profile['profileFingerprint'],'floatDtypes':profile['floatDtypes'],'gateUpScalePairs':2}
    def spawn(self,argv,**kwargs):
        self.probes.append((list(argv),copy.deepcopy(kwargs)))
        destination=Path(argv[-1]);destination.mkdir()
        for item in self.source.iterdir():
            if item.name!='model.safetensors':shutil.copyfile(item,destination/item.name)
        write_tensor_file(destination/'model.safetensors','F16')
        import io
        return types.SimpleNamespace(stdout=io.StringIO('{"event":"validated","current":1,"total":1,"file":"model.safetensors"}\n{"event":"converted","current":1,"total":1,"file":"model.safetensors"}\n'),wait=lambda:0,poll=lambda:0)
    def capture(self,argv,**kwargs):
        import io
        result=self.spawn(argv,cwd=str(kwargs['cwd']),env=kwargs['environment'],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True,bufsize=1)
        details=Path(argv[-1]).stat()
        created=json.dumps({'event':'staging-created','device':details.st_dev,'inode':details.st_ino,'uid':details.st_uid})+'\n'
        data=created.encode()+result.stdout.read().encode();kwargs['on_bytes'](data)
        return subprocess.CompletedProcess(argv,0,data)
    def clone_manager(self):return ane_jobs.ANEFP16CloneManager(self.run.snapshot,self.clone_policy,self.ane_services)
    def clone_legacy(self):
        values=self.legacy('ane_jobs')
        values.update({'ANE_FP16_CLONE_DISK_RESERVE_BYTES':launcher.ANE_FP16_CLONE_DISK_RESERVE_BYTES,'ANE_FP16_CLONE_PLAN_TTL_SECONDS':launcher.ANE_FP16_CLONE_PLAN_TTL_SECONDS,
            'ANE_FP16_CLONE_SOURCE_URL':launcher.ANE_FP16_CLONE_SOURCE_URL,'ANE_FP16_CLONE_HELPER':self.helper,'APP_DIR':self.root,'BINARIES':{'omlx':'/generated/omlx'},
            'command_version':self.ane_services.runtime.command_version,'omlx_runtime_python':self.ane_services.runtime.runtime_python,'read_json':self.ane_services.io.read_json,
            'ane_fp16_clone_source_profile':self.source_profile,'ane_cpu_sharing_profile':self.cpu_profile,'ane_quantization_profile':self.ane_services.artifacts.quantization_profile,
            'model_artifact_fingerprint':self.fingerprint,'weight_completeness':self.ane_services.artifacts.weight_completeness,'safetensors_inventory':launcher.safetensors_inventory,
            'display_size':str,'_hf_public_environment':lambda:{}})
        return values
