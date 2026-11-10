"""Explicit synthetic live ports for complete capacity/admission equivalence."""
from __future__ import annotations
import ast
import copy
from datetime import datetime,timezone
import hashlib,json,math,secrets
from pathlib import Path
from types import SimpleNamespace
import launcher
import resource_admission as admission

ROOT=Path(__file__).resolve().parents[2]
META=json.loads((ROOT/'tests/fixtures/resource_admission_legacy.json').read_text())
GIB=1024**3

class FixedDateTime(datetime):
    @classmethod
    def now(cls,tz=None):return cls(2026,10,7,0,0,0,tzinfo=tz)


def policy():
    values={name.lower():copy.deepcopy(getattr(launcher,name)) for name in META['constants']}
    values.update(memory_semantics_version=launcher.darwin_memory.MEMORY_SEMANTICS_VERSION,
        slotstream_default_memory_gb=launcher.slotstream_runtime.DEFAULT_MEMORY_GB,
        whallm_working_set_bytes=launcher.whallm_runtime.WORKING_SET_BYTES,
        whallm_slots=launcher.whallm_runtime.SLOTS,whallm_memory_bytes=launcher.whallm_runtime.MEMORY_BYTES)
    return admission.ResourcePolicy(**values)


def snapshot(headroom=40*GIB,pressure=89,available=True):
    return {'totalBytes':48*GIB,'memoryAvailable':True,'freePercent':pressure,'memorySource':'memorystatus_get_level',
        'memorySemanticsVersion':2,'physicalMemoryAvailable':available,'reclaimableBytes':headroom if available else None,
        'reclaimableMemorySource':'host_statistics64','thermalAvailable':True,'thermalState':0,'lowPowerMode':False,
        'metalWiredLimitBytes':44*GIB,'metalRecommendedWorkingSetBytes':40*GIB}


def model(backend):
    item={'id':'generated-'+backend,'name':'Generated original model','size':8*GIB,
          'memoryGeometry':{'ready':True,'fullAttentionLayers':8,'kvHeads':4,'headDimension':128},
          'backends':{backend:{'runnable':True,'mtp':True,'dflashDraftSize':GIB,'ssdProfile':{'weightBytes':50*GIB,'expertCount':128,'nativeExpertTopK':4}}}}
    if backend=='slotstream':item['slotstream']={'ready':True}
    if backend=='kolibri':item['size']=63_517_990_178;item['kolibri']={'identity':'original-q6'}
    if backend=='splash':item['splash']={'id':'generated/original-pack','weightBytes':16*GIB}
    if backend=='whallm':item['nativeWhallm']={'commonBytes':2*GIB}
    if backend=='freetoken':item['nativeFreetoken']=True;item['backends'][backend]['nativeContract']={'sizing':{'kv_cache_bytes_per_token':65536,'weight_bytes':8*GIB}}
    if backend=='uzu':item['uzuNative']=True
    return item


def request(backend,client='pi',context=8192,output=1024,**options):
    values={'acceleration':'off','depth':1,'kv':'off','memoryGB':12,'memoryMode':'fixed','prefillSize':64,'promptCacheGB':1}
    values.update(options)
    return {'backend':backend,'client':client,'modelId':'generated-'+backend,'project':'/generated/project',
            'context':context,'output':output,'reasoning':'off','mode':'custom','options':values}


class Fixture:
    def __init__(self):
        self.snapshot=snapshot();self.hub={'phase':'idle'};self.operation={'active':False};self.conflict={}
        self.records={backend:{'id':'fresh-'+backend,'createdAt':'2026-10-07T00:00:00Z','peakMemoryBytes':24*GIB} for backend in ('uzu','llamacpp')}
        self.specs={'uzu':{'backend':'uzu','id':'generated-uzu','routeLabel':'Generated Uzu'},'llamacpp':{'backend':'llamacpp','id':'generated-llamacpp'}}
        self.verified_output=None
        self.calls={'snapshot':0,'hub':0,'operation':0,'validation':[],'evidence':0,'verified':0,'conflict':0,'native':0}
        self.ports={
            'benchmark_resource_condition':launcher.benchmark_resource_condition,
            'active_launcher_operation':self.active,'apple_resource_snapshot':self.read_snapshot,'whallm_qualification_conflict':self.read_conflict,
            '_profile_integer':launcher._profile_integer,'bounded_integer':launcher.bounded_integer,
            'validated_launch_profile_request':self.validate,'validated_sampling_contract':lambda *_args:{'mode':'model'},
            'omlx_expert_offload_options':lambda item,options:item.get('generatedOffload'),
            'optimizer_evidence':self.evidence,'add_benchmark_engine_evidence':lambda *_args:None,
            'verified_route_qualification':self.verified,'route_qualification_metrics':lambda record,_spec:{'peakMemoryBytes':record['peakMemoryBytes']},
            'route_qualification_spec':lambda item,backend,_context=None:copy.deepcopy(self.specs.get(backend)),
            'route_qualification_sample_tokens':lambda _backend,output:min(128,output),'uzu_pi_transport_supported':lambda _cap:True,
        }
        fields={group:{} for group in ('validation','native','evidence','live')}
        for name,(group,field) in META['callbacks'].items():fields[group][field]=self.ports[name]
        fields['native'].update(kolibri_memory_plan=self.kolibri,splash_memory_estimate=self.splash)
        fields['live']['hub_snapshot']=self.read_hub
        self.services=admission.ResourceServices(admission.ValidationServices(**fields['validation']),admission.NativeEstimateServices(**fields['native']),
            admission.EvidenceServices(**fields['evidence']),admission.LiveResourceServices(**fields['live']))
        self.domain=admission.ResourceAdmission(policy(),self.services)
        namespace={'Any':object,'Path':Path,'copy':copy,'hashlib':hashlib,'json':json,'math':math,'secrets':secrets,
            'datetime':FixedDateTime,'timezone':timezone,**{name:copy.deepcopy(getattr(launcher,name)) for name in META['constants']},**self.ports,
            'MANAGER':SimpleNamespace(hub_snapshot=self.read_hub),
            'darwin_memory':SimpleNamespace(MEMORY_SEMANTICS_VERSION=2),
            'slotstream_runtime':SimpleNamespace(DEFAULT_MEMORY_GB=launcher.slotstream_runtime.DEFAULT_MEMORY_GB),
            'kolibri_runtime':SimpleNamespace(memory_plan=self.kolibri),'splash_runtime':SimpleNamespace(memory_estimate=self.splash),
            'whallm_runtime':SimpleNamespace(WORKING_SET_BYTES=launcher.whallm_runtime.WORKING_SET_BYTES,SLOTS=launcher.whallm_runtime.SLOTS,MEMORY_BYTES=launcher.whallm_runtime.MEMORY_BYTES)}
        exec(compile((ROOT/'tests/fixtures/resource_admission_legacy.py').read_text(),'frozen-resource-admission','exec'),namespace)
        self.legacy=namespace
    def validate(self,payload,models,**kwargs):self.calls['validation'].append(copy.deepcopy(kwargs));return copy.deepcopy(payload)
    def read_snapshot(self):self.calls['snapshot']+=1;return copy.deepcopy(self.snapshot)
    def read_hub(self):self.calls['hub']+=1;return copy.deepcopy(self.hub)
    def active(self,_hub):self.calls['operation']+=1;return copy.deepcopy(self.operation)
    def read_conflict(self,*_args,**_kwargs):self.calls['conflict']+=1;return copy.deepcopy(self.conflict)
    def evidence(self,item,context,output,client,reasoning,kv,chat,sampling):
        self.calls['evidence']+=1;return {'model':item['id'],'context':context,'output':output,'client':client,'reasoning':reasoning,'kv':kv}
    def verified(self,item,backend,evidence):
        self.calls['verified']+=1
        return copy.deepcopy(self.records.get(backend)) if self.verified_output is None or evidence.get('output')==self.verified_output else None
    def kolibri(self,info,context,options,resource):
        self.calls['native']+=1;working=options.get('memoryGB',12)*1_000_000_000
        return {'ready':resource.get('memoryAvailable') is True and resource.get('headroomBytes',0)>=working+5*GIB,
            'kv':options.get('kv','off'),'kvPrecision':'BF16' if options.get('kv','off')=='off' else options['kv'],
            'residentWeightBytes':8*GIB,'residentExpertsPerLayer':38,'prefillSize':options.get('prefillSize',64),
            'estimatedWorkingSetBytes':working,'osReserveBytes':5*GIB,'requiredHeadroomBytes':working+5*GIB,
            'contextTokens':context,'promptCacheGB':options.get('promptCacheGB',1)}
    def splash(self,pack,context):
        self.calls['native']+=1;working=pack['weightBytes']+context*32768+2*GIB
        return {'modelBytes':pack['weightBytes'],'runtimeReserveBytes':2*GIB,'estimatedWorkingSetBytes':working,
                'kvCacheBytes':context*32768,'kvPrecision':'native fixed','parallelLanes':1,'basis':'Generated exact packed context'}
