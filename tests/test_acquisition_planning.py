"""Exact setup/acquisition previews and current downloaded-artifact verification."""
import ast
import copy
import dataclasses
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

import acquisition_planning as domain
import launcher
import owned_cli_capture
from tests.helpers.acquisition_planning_fixture import FIXTURE, METADATA, method, original, planner


class Projection(ast.NodeTransformer):
    def visit_Call(self, node):
        if (isinstance(node.func, ast.Attribute) and node.func.attr == 'descriptor_public'
                and ast.unparse(node.func.value) == 'self.services'):
            assert len(node.args) == 1 and not node.keywords and ast.unparse(node.args[0]) == 'descriptor.id'
            return ast.copy_location(ast.Call(ast.Attribute(ast.Name('descriptor',ast.Load()),'public',ast.Load()),[],[]),node)
        return self.generic_visit(node)
    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Attribute) and isinstance(node.value.value, ast.Name) and node.value.value.id == 'self':
            if node.value.attr == 'policy':return ast.copy_location(ast.Name(node.attr.upper(), ast.Load()), node)
            if node.value.attr == 'services':
                if node.attr == 'binary':return ast.copy_location(ast.Attribute(ast.Name('BINARIES', ast.Load()), 'get', ast.Load()), node)
                if node.attr == 'now':return ast.copy_location(ast.Attribute(ast.Name('datetime', ast.Load()), 'now', ast.Load()), node)
                if node.attr == 'cancelled':return ast.copy_location(ast.Name('LaunchCancelled', ast.Load()), node)
                name = next(value for value in METADATA['ports'] if value.lstrip('_') == node.attr)
                return ast.copy_location(ast.Name(name, ast.Load()), node)
        if isinstance(node.value, ast.Name) and node.value.id == 'self' and node.attr in METADATA['functions']:
            return ast.copy_location(ast.Name(node.attr, ast.Load()), node)
        return self.generic_visit(node)


class AcquisitionPlanningTests(unittest.TestCase):
    def test_all_24_complete_bodies_and_public_call_shapes_match_frozen_source(self):
        old = {n.name:n for n in ast.parse(FIXTURE.read_text()).body if isinstance(n, ast.FunctionDef)}
        tree = ast.parse(Path(domain.__file__).read_text())
        new = {n.name:n for n in tree.body if isinstance(n, ast.FunctionDef)}
        owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AcquisitionPlanning')
        new.update({n.name:n for n in owner.body if isinstance(n, ast.FunctionDef)})
        current = planner(launcher)
        self.assertEqual(set(old), set(METADATA['functions']))
        for name in METADATA['functions']:
            with self.subTest(function=name):
                before = ast.Module(body=copy.deepcopy(old[name].body), type_ignores=[])
                if name == 'run_hf_json':
                    attempt = next(node for node in before.body if isinstance(node, ast.Try))
                    attempt.body[0].value = ast.parse('owned_cli_capture.capture_owned_cli([downloader, *arguments], timeout=timeout, max_bytes=32 * 1024**2, environment=_hf_public_environment())',mode='eval').body
                    guards = ast.parse('''
try:
    pass
except owned_cli_capture.CaptureLimitError as error:
    raise ValueError("The Hub returned more metadata than the launcher can inspect safely.") from error
except owned_cli_capture.CaptureOwnershipError as error:
    raise ValueError("The public Hugging Face metadata request could not finish safely.") from error
''').body[0].handlers
                    attempt.handlers[0:0] = guards
                    index = next(i for i,node in enumerate(before.body) if isinstance(node,ast.Assign)
                        and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='output')
                    before.body[index:index+1] = ast.parse('''
encoding = "utf-8" if sys.flags.utf8_mode else locale.getpreferredencoding(False)
output = (result.stdout or b"").decode(encoding).replace("\\r\\n", "\\n").replace("\\r", "\\n")
''').body
                after = Projection().visit(ast.Module(body=copy.deepcopy(new[name].body), type_ignores=[]))
                for body in (before.body, after.body):
                    if isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                        body[0].value.value = inspect.cleandoc(body[0].value.value)
                self.assertEqual(ast.dump(before, include_attributes=False), ast.dump(after, include_attributes=False))
                a,b = inspect.signature(getattr(launcher,name)), inspect.signature(method(current,name))
                self.assertEqual([(p.name,p.kind,p.default) for p in a.parameters.values()],
                                 [(p.name,p.kind,p.default) for p in b.parameters.values()])

    def test_import_needs_no_controller_queries_processes_or_writes(self):
        code = '''
import builtins,pathlib,subprocess,sys,urllib.request
sys.path.insert(0,sys.argv[1]);original=builtins.__import__
def only(name,*a,**k):
 if name in {'launcher','llm_launcher'}:raise AssertionError('controller import')
 return original(name,*a,**k)
def forbidden(*a,**k):raise AssertionError('import side effect')
builtins.__import__=only;subprocess.Popen=forbidden;urllib.request.urlopen=forbidden
pathlib.Path.write_text=forbidden;pathlib.Path.write_bytes=forbidden
import acquisition_planning
'''
        result = subprocess.run([sys.executable,'-c',code,str(Path(domain.__file__).parent)],
                                capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_query_path_and_artifact_ports_remain_live_with_detached_frozen_policy(self):
        current = planner(launcher)
        with self.assertRaises(dataclasses.FrozenInstanceError):current.policy.model_acquisition_schema_version = -1
        with self.assertRaises(TypeError):current.policy.engine_adapters['omlx'] = None
        with mock.patch.dict(launcher.BINARIES,{'hf':'/generated/current'}):
            self.assertEqual(current.services.binary('hf'),'/generated/current')
        with mock.patch.object(launcher,'physical_memory_bytes',return_value=17):
            self.assertEqual(current.services.physical_memory_bytes(),17)

    def test_controller_reuses_only_wiring_and_invalidates_current_policy(self):
        owner=launcher._acquisition_planning()
        self.assertIs(owner,launcher._acquisition_planning())
        with mock.patch.dict(launcher.BINARIES,{'hf':'/generated/new-query'}):
            self.assertIs(owner,launcher._acquisition_planning())
            self.assertEqual(owner.services.binary('hf'),'/generated/new-query')
        with mock.patch.object(launcher,'physical_memory_bytes',return_value=18):
            self.assertIs(owner,launcher._acquisition_planning())
            self.assertEqual(owner.services.physical_memory_bytes(),18)
        with mock.patch.object(launcher,'MODEL_ACQUISITION_SEARCH_LIMIT',launcher.MODEL_ACQUISITION_SEARCH_LIMIT+1):
            changed=launcher._acquisition_planning()
            self.assertIsNot(owner,changed)
            self.assertEqual(changed.policy.model_acquisition_search_limit,launcher.MODEL_ACQUISITION_SEARCH_LIMIT)
        self.assertEqual(owner.policy.model_acquisition_search_limit,launcher.MODEL_ACQUISITION_SEARCH_LIMIT)
        self.assertIn(Path(domain.__file__).resolve(),launcher.CONTROLLER_SOURCE_PATHS)
        self.assertIn(Path(owned_cli_capture.__file__).resolve(),launcher.CONTROLLER_SOURCE_PATHS)

    def test_pinned_variants_and_download_commands_match_without_network(self):
        current=planner(launcher);old=original(launcher)
        snapshot={'repoId':'generated/model','pinnedRevision':'a'*40,'requestedRevision':'main',
            'files':[{'path':'model-Q4_K_M.gguf','size':16,'role':'weight','sha256':'b'*64,'securitySafe':True},
                     {'path':'model-Q6_K.gguf','size':32,'role':'weight','sha256':'c'*64,'securitySafe':True}],
            'tags':['license:apache-2.0'],'license':'apache-2.0','gated':False,'private':False,'disabled':False}
        self.assertEqual(current.model_acquisition_variants(snapshot),old['model_acquisition_variants'](snapshot))
        for repo in ('owner/model',' bad ','owner/../bad','../model','owner/model/sub'):
            outcomes=[]
            for function in (domain.validated_hf_repo_id,old['validated_hf_repo_id']):
                try:outcomes.append(('value',function(repo)))
                except ValueError as error:outcomes.append(('error',str(error)))
            self.assertEqual(outcomes[0],outcomes[1])

    def test_complete_anonymous_search_and_pinned_snapshot_queries_match(self):
        current=planner(launcher);old=original(launcher)
        info={'id':'generated/model','sha':'a'*40,'gated':False,'private':False,'disabled':False,
              'tags':['gguf','license:apache-2.0'],'downloads':3,'likes':1,'cardData':{}}
        tree=[{'path':'model-Q4_K_M.gguf','size':16,'lfs':{'sha256':'b'*64},
               'security':{'safe':True,'status':'safe'}},
              {'path':'../escaping.gguf','size':20}, {'path':'README.md','size':8}]
        calls=[]
        def query(arguments,timeout=30):
            calls.append((arguments,timeout))
            return copy.deepcopy(info if arguments[1]=='info' else tree)
        old['run_hf_json']=query
        outcomes=[];queries=[]
        for frozen in (True,False):
            calls.clear()
            if frozen:value=old['fetch_model_acquisition_snapshot']('generated/model','main')
            else:
                with mock.patch.object(current,'run_hf_json',side_effect=query):
                    value=current.fetch_model_acquisition_snapshot('generated/model','main')
            outcomes.append(value);queries.append(copy.deepcopy(calls))
        self.assertEqual(outcomes[0],outcomes[1]);self.assertEqual(queries[0],queries[1])
        self.assertEqual(outcomes[1]['pinnedRevision'],'a'*40)
        self.assertFalse(any(item['path'].startswith('../') for item in outcomes[1]['files']))
        for name in ('HF_TOKEN','HUGGING_FACE_HUB_TOKEN'):
            with mock.patch.dict(domain.os.environ,{name:'generated-secret'},clear=True):
                self.assertEqual(domain._hf_public_environment(),old['_hf_public_environment']())
                self.assertFalse(name in domain._hf_public_environment(), 'Anonymous query retained a generated credential field')
                self.assertEqual(domain._hf_public_environment()['HF_HUB_DISABLE_IMPLICIT_TOKEN'],'1')

    def test_complete_private_destination_plans_match_for_variants_existing_files_and_collisions(self):
        fixed=launcher.datetime(2026,10,7,tzinfo=launcher.timezone.utc)
        class FixedClock(launcher.datetime):
            @classmethod
            def now(cls,zone=None):return fixed
        with tempfile.TemporaryDirectory(prefix='acquisition-plans-') as temporary, \
                mock.patch.object(Path,'home',return_value=Path(temporary)), \
                mock.patch.dict(launcher.BINARIES,{'hf':'/generated/hf'}), \
                mock.patch.object(launcher.shutil,'disk_usage',return_value=type('Disk',(),{'free':64*1024**3})()), \
                mock.patch.object(launcher,'physical_memory_bytes',return_value=64*1024**3), \
                mock.patch.object(launcher,'datetime',FixedClock):
            current=planner(launcher);old=original(launcher)
            snapshot={'repoId':'generated/model','pinnedRevision':'a'*40,'requestedRevision':'main',
                'files':[{'path':'model-Q4_K_M.gguf','size':16,'role':'weight','sha256':'b'*64,
                          'securitySafe':True,'securityStatus':'safe'},
                         {'path':'model-Q6_K.gguf','size':32,'role':'weight','sha256':'c'*64,
                          'securitySafe':True,'securityStatus':'safe'}],
                'tags':['license:apache-2.0'],'license':'apache-2.0','gated':False,'private':False,'disabled':False}
            variants=current.model_acquisition_variants(snapshot)
            self.assertEqual(len(variants),2)
            for location in domain.model_acquisition_roots():
                for variant in variants:
                    for collision in (False,True):
                        with self.subTest(destination=location['id'],variant=variant['id'],collision=collision):
                            destination=Path(location['path'])/'generated'/'model'
                            destination.mkdir(parents=True,exist_ok=True)
                            marker=destination/'unrelated.txt'
                            if collision:marker.write_text('Existing unrelated file')
                            outputs=[]
                            for function in (old['build_model_acquisition_plan'],current.build_model_acquisition_plan):
                                value=function(copy.deepcopy(snapshot),location['id'],variant['id'])
                                outputs.append(value)
                            self.assertEqual(outputs[0],outputs[1])
                            self.assertEqual(outputs[0]['destination']['path'],str(destination.resolve()))
                            if collision:self.assertTrue(marker.exists())
                            if marker.exists():marker.unlink()

    def test_current_gguf_checksum_sizes_cancel_and_changed_file_verdicts_match(self):
        current=planner(launcher);old=original(launcher)
        with tempfile.TemporaryDirectory(prefix='acquisition-proof-') as temporary:
            root=Path(temporary);file=root/'generated.gguf';body=b'GGUF'+b'generated fixture'
            file.write_bytes(body);checksum=hashlib.sha256(body).hexdigest()
            plan={'destination':{'path':str(root)},'selection':{'format':'gguf',
                'files':[{'path':file.name,'size':len(body),'role':'weight','sha256':checksum}]}}
            for corrupt,cancelled in ((False,False),(True,False),(False,True)):
                file.write_bytes(body if not corrupt else b'GGUF'+b'x'*(len(body)-4))
                event=threading.Event()
                if cancelled:event.set()
                outcomes=[]
                for function in (old['verify_model_acquisition'],current.verify_model_acquisition):
                    try:outcomes.append(('value',function(copy.deepcopy(plan),event)))
                    except (ValueError,launcher.LaunchCancelled) as error:outcomes.append((type(error).__name__,str(error)))
                self.assertEqual(outcomes[0],outcomes[1])
                if not corrupt and not cancelled:self.assertTrue(outcomes[0][1]['verified'])
                else:self.assertNotEqual(outcomes[0][0],'value')

    def test_complete_draft_setup_preview_and_safe_command_never_create_files(self):
        with tempfile.TemporaryDirectory(prefix='draft-preview-') as temporary, \
                mock.patch.dict(launcher.BINARIES,{'hf':'/generated/hf'}), \
                mock.patch.object(launcher.shutil,'disk_usage',return_value=type('Disk',(),{'free':32*1024**3})()):
            current=planner(launcher);old=original(launcher);destination=Path(temporary)/'draft;one argument'
            for installed in (False,True):
                for runtime in (False,True):
                    model={'id':'generated-target','name':'Generated Qwen target','backends':{'omlx':{
                        'dflashReadiness':{'targetCompatible':True,'targetReason':'Generated exact geometry',
                            'runtimeDetected':'generated-runtime','runtimeReady':runtime,'runtimeRecommended':runtime,
                            'minimumRuntime':launcher.DFLASH2_MINIMUM_RUNTIME,'recommendedRuntime':launcher.DFLASH2_RECOMMENDED_RUNTIME,
                            'draftInstalled':installed,'draftComplete':installed,'draftDetected':installed,
                            'draftStatus':'Generated status','draftPath':str(destination)}}}}
                    before=old['build_dflash2_setup_plan'](copy.deepcopy(model),Path(temporary))
                    after=current.build_dflash2_setup_plan(copy.deepcopy(model),Path(temporary))
                    self.assertEqual(before,after)
                    self.assertFalse(destination.exists())
                    self.assertTrue(after['safety']['requiresExplicitConsent'])
                    self.assertFalse(after['safety']['changesRuntime'])
                    self.assertEqual(old['build_dflash2_download_argv'](before),current.build_dflash2_download_argv(after))
                    self.assertIn(str(destination.resolve()),current.build_dflash2_download_argv(after))

    def test_bounded_query_preserves_output_errors_empty_arguments_and_anonymous_environment(self):
        with mock.patch.dict(launcher.BINARIES,{'hf':'/generated/hf'}), \
                mock.patch.dict(domain.os.environ,{'HF_TOKEN':'generated-secret','PATH':'/generated/path'},clear=True):
            current=planner(launcher);old=original(launcher)
            examples=[(0,'{"name":"café"}\r\n'),(0,'[1,2,3]'),(0,'not JSON'),
                      (1,'HTTP 401 gated repository'),(1,'HTTP 404 not found'),(1,'Generated command failure')]
            for code,text in examples:
                with self.subTest(code=code,outputKind='json' if code==0 else 'error'):
                    outputs=[]
                    before=subprocess.CompletedProcess(['/generated/hf'],code,text,None)
                    after=subprocess.CompletedProcess(['/generated/hf'],code,text.encode(),None)
                    with mock.patch.object(domain.subprocess,'run',return_value=before), \
                            mock.patch.object(domain.owned_cli_capture,'capture_owned_cli',return_value=after) as capture:
                        for function in (old['run_hf_json'],current.run_hf_json):
                            try:outputs.append(('value',function(['models','list','--query',''])))
                            except ValueError as error:outputs.append(('error',str(error)))
                    self.assertEqual(outputs[0],outputs[1])
                    self.assertEqual(capture.call_args.kwargs['max_bytes'],32*1024**2)
                    self.assertEqual(capture.call_args.args[0][-1],'')
                    self.assertFalse('HF_TOKEN' in capture.call_args.kwargs['environment'])
            for error,message in ((owned_cli_capture.CaptureLimitError('generated quota'),'more metadata'),
                                  (owned_cli_capture.CaptureOwnershipError('generated lost receipt'),'finish safely'),
                                  (subprocess.TimeoutExpired(['/generated/hf'],1),'did not complete')):
                with mock.patch.object(domain.owned_cli_capture,'capture_owned_cli',side_effect=error), \
                        self.assertRaisesRegex(ValueError,message):
                    current.run_hf_json(['models','list'])

    def test_query_character_quota_is_preserved_with_bounded_multibyte_output(self):
        with mock.patch.dict(launcher.BINARIES,{'hf':'/generated/hf'}):
            current=planner(launcher)
            for character,count in (('x',8*1024**2-2),('𐍈',3*1024**2)):
                encoded=json.dumps(character*count,ensure_ascii=False).encode('utf-8')
                self.assertLessEqual(len(encoded),32*1024**2)
                result=subprocess.CompletedProcess(['/generated/hf'],0,encoded,None)
                with mock.patch.object(domain.owned_cli_capture,'capture_owned_cli',return_value=result):
                    value=current.run_hf_json(['models','list'])
                self.assertEqual(len(value),count)
                self.assertEqual(value[0],character)
            result=subprocess.CompletedProcess(['/generated/hf'],0,b' '*(8*1024**2+1),None)
            with mock.patch.object(domain.owned_cli_capture,'capture_owned_cli',return_value=result), \
                    self.assertRaisesRegex(ValueError,'more metadata'):
                    current.run_hf_json(['models','list'])

    def test_controller_query_uses_owned_capture_with_private_generated_cli(self):
        with tempfile.TemporaryDirectory(prefix='public-query-cli-') as temporary:
            binary=Path(temporary)/'generated-hf'
            binary.write_text('#!'+sys.executable+'\n'+'''import json,os,sys
assert "HF_TOKEN" not in os.environ and "HUGGING_FACE_HUB_TOKEN" not in os.environ
assert os.environ.get("HF_HUB_DISABLE_IMPLICIT_TOKEN")=="1"
print(json.dumps({"fixture":True,"unicode":"café","arguments":sys.argv[1:]},ensure_ascii=False))
''')
            binary.chmod(0o700)
            with mock.patch.dict(launcher.BINARIES,{'hf':str(binary)}), \
                    mock.patch.dict(domain.os.environ,{'HF_TOKEN':'generated-secret','HUGGING_FACE_HUB_TOKEN':'generated-secret'}):
                value=launcher.run_hf_json(['models','list','--query',''])
            self.assertEqual(value,{'fixture':True,'unicode':'café','arguments':['models','list','--query','']})


if __name__ == '__main__':unittest.main()
