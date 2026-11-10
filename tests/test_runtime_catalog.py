"""Runtime inventory/plans retain exact contracts on private generated files."""
import ast
import copy
from contextlib import ExitStack
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import launcher
import runtime_catalog
from tests.fixtures import runtime_catalog_legacy as original
from tests.helpers.runtime_catalog_fixture import make_runtime_catalog

SOURCE_SHA = '5012d80d987e122e2c8d4d21db2aca5f349cba1f10710e690f5e1c75f18884a6'
NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
SPLASH_150_RELEASE = {
    'version':'1.5.0','displayVersion':'1.5.0','channel':'stable','releasedAt':'2026-10-28',
    'releaseUrl':'https://github.com/incoai/splash/releases/tag/1.5.0',
    'summary':'Qwen3.8 Flash-Next GGUF joins 27B and 35B-A3B, with automatic expert and PLE SSD streaming, active KV spill and matching DFlash2 drafts.',
    'highlights':[{'value':'DFlash 2','label':'matching draft'},
        {'value':'Flash-Next','label':'GGUF · including split files'},
        {'value':'256K','label':'native window'}],
    'workflow':[
        "Use Splash 1.5.0 for Flash-Next; the launcher verifies the engine's release hashes before loading.",
        'Rescan for compatible GGUF files, including split Flash-Next GGUFs. Flash-Next MLX is not supported; 27B and 35B-A3B also accept MLX affine Q4 checkpoints.',
        'Existing target weights are linked in place; the matching DFlash2 draft is downloaded only if no compatible local draft is available.',
        'Splash streams experts and PLE when needed, within a budget that leaves room for macOS and other apps. The native planner checks context and SSD capacity before loading.',
    ],
}
SPLASH_150_PLATFORM = 'Splash 1.5.0 · Flash-Next GGUF / 27B / 35B · macOS 26.4 · Apple silicon M3+'
SPLASH_150_MODEL_DETAIL = 'Flash-Next GGUF, including split files, with automatic expert/PLE SSD streaming and matching DFlash2 drafts. Flash-Next MLX is not supported.'


class PrivateRuntimeFixture:
    def __init__(self, folder, installed=True):
        self.root = Path(folder).resolve()
        self.home = self.root / 'home'
        self.home.mkdir()
        self.managed = self.root / 'runtimes'
        self.binary_paths = {}
        self.specs = {}
        self.versions = {}
        for runtime in launcher.RUNTIME_CANDIDATE_SPECS:
            binary = self.root / runtime / 'bin' / runtime
            if installed:
                binary.parent.mkdir(parents=True)
                binary.write_text('#!/bin/sh\nexit 0\n')
                binary.chmod(0o700)
            self.binary_paths[runtime] = str(binary) if installed else None
            self.specs[runtime] = (('generated',str(binary),'Generated '+runtime),)
            release = launcher.RUNTIME_RELEASE_CATALOG.get(runtime, {})
            self.versions[str(binary)] = str(release.get('version') or '1.2.3')
        for agent in ('pi','opencode','codex'):
            self.binary_paths[agent] = '/generated/'+agent if installed else None
            self.versions['/generated/'+agent] = '1.2.3'
        self.app_specs = {}
        for runtime, spec in launcher.RUNTIME_APP_SPECS.items():
            app = self.root / (spec['label']+'.app')
            if installed:
                (app/'Contents'/'MacOS').mkdir(parents=True)
                command = app/'Contents'/'MacOS'/'generated'
                command.write_text('#!/bin/sh\nexit 0\n');command.chmod(0o700)
                (app/'Contents'/'Info.plist').write_bytes(plistlib.dumps({
                    'CFBundleIdentifier':spec['bundleIds'][0],
                    'CFBundleExecutable':'generated','CFBundleShortVersionString':'0.4.0'}))
            self.app_specs[runtime] = {**spec,'paths':[str(app)]}
        self.pack_root = self.home/'.lmstudio'/'extensions'/'backends'
        if installed:
            (self.pack_root/'mlx-metal-1.2.3').mkdir(parents=True)
        self.probe_calls=[]

    def executable(self, requests):
        requested = str(requests[0])
        if requested in ('curl','/usr/bin/curl','git','/usr/bin/git','xcrun','/usr/bin/xcrun'):
            return '/generated/'+Path(requested).name
        candidate = Path(requested).expanduser()
        return str(candidate) if candidate.is_file() and os.access(candidate,os.X_OK) else None

    def run(self, argv, **kwargs):
        self.probe_calls.append(list(argv))
        if argv[1:] == ['-f','metal']:
            return SimpleNamespace(returncode=0,stdout='/generated/metal\n',stderr='')
        if '-c' in argv and 'native_kernel_status' in argv[-1]:
            return SimpleNamespace(returncode=0,stdout='__LLM_LAUNCHER_KERNEL__{"available":true}\n',stderr='')
        return SimpleNamespace(returncode=0,stdout='3.11.15\n3.11\n',stderr='')

    def patches(self):
        stack=ExitStack()
        for module in (launcher,original):
            for name,value in {'MANAGED_RUNTIMES_DIR':self.managed,
                'LLAMACPP_SERVER_PATH':Path(self.binary_paths.get('llamacpp') or self.root/'missing-llama'),
                'RUNTIME_CANDIDATE_SPECS':self.specs,'RUNTIME_APP_SPECS':self.app_specs,
                'SSD_STREAMING_RUNTIME_URLS':{**launcher.SSD_STREAMING_RUNTIME_URLS,'splash':launcher.RUNTIME_RELEASE_CATALOG['splash']['releaseUrl']}}.items():
                stack.enter_context(mock.patch.object(module,name,value))
        stack.enter_context(mock.patch.object(launcher.Path,'home',return_value=self.home))
        stack.enter_context(mock.patch.dict(launcher.BINARIES,self.binary_paths,clear=True))
        for name,value in {'lmstudio_mtp_load_supported':True,'lmstudio_assistant_drafter_load_supported':False,
            'lmstudio_assistant_drafter_runtime_contract':{'ready':False,'reason':'Generated drafter not qualified'},
            'uzu_runtime_contract':{'ready':False,'reason':'Generated native runtime not trusted','binaryIdentityPinned':False},
            'llamacpp_runtime_contract':{'ready':False,'reason':'Generated native runtime not trusted'},
            'disk_free_for':20*1024**3}.items():
            stack.enter_context(mock.patch.object(launcher,name,return_value=value))
        stack.enter_context(mock.patch.object(launcher,'executable',side_effect=self.executable))
        stack.enter_context(mock.patch.object(launcher,'command_version',side_effect=lambda binary:self.versions.get(str(binary),'Not installed' if not binary else '1.2.3')))
        stack.enter_context(mock.patch.object(launcher.subprocess,'run',side_effect=self.run))
        stack.enter_context(mock.patch.object(launcher.sys,'platform','darwin'))
        stack.enter_context(mock.patch.object(launcher.platform,'machine',return_value='arm64'))
        stack.enter_context(mock.patch.object(original.time,'strftime',return_value=NOW.strftime('%Y-%m-%dT%H:%M:%SZ')))
        original._RUNTIME_KERNEL_CACHE.clear()
        return stack

    def catalog(self):
        catalog=make_runtime_catalog(launcher)
        catalog.clock=runtime_catalog.RuntimeClock(checked_at=lambda:NOW.strftime('%Y-%m-%dT%H:%M:%SZ'),now=lambda:NOW,record_id=lambda:'generated-id')
        return catalog

    def snapshot(self):
        return {str(path.relative_to(self.root)):(path.lstat().st_mode,path.read_bytes() if path.is_file() and not path.is_symlink() else os.readlink(path) if path.is_symlink() else None)
            for path in self.root.rglob('*')}


class RuntimeCatalogTests(unittest.TestCase):
    def without_new_optional_inventory(self, inventory):
        """Preserve the frozen-engine comparison while checking added rows."""
        current = copy.deepcopy(inventory)
        rec = next(row for row in current['runtimes'] if row['id'] == 'rec')
        self.assertEqual(rec['label'], 'Rec')
        self.assertEqual(rec['update']['docsUrl'], 'https://github.com/recursive-oss/rec')
        checks = {check['label']:check for check in rec['checks']}
        self.assertIn('Flint INT4', checks['Exact model contract']['detail'])
        self.assertIn('Local model server', checks)
        self.assertNotIn('SSD-streaming server', checks)
        self.assertIn('262,144', checks['Exact model contract']['detail'])
        self.assertIn('48 GB', checks['Platform']['detail'])
        rapid = next(row for row in current['runtimes'] if row['id'] == 'rapidmlx')
        self.assertEqual(rapid['label'], 'Rapid MLX')
        self.assertEqual(rapid['update']['docsUrl'], 'https://github.com/raullenchai/Rapid-MLX')
        self.assertNotIn('SSD', str(rapid))
        rows = current['runtimes']
        installed = sum(bool(row.get('selected')) for row in rows)
        advisories = sum(row['level'] != 'ready' for row in rows)
        self.assertEqual(current['summary']['total'], len(rows))
        self.assertEqual(current['summary']['installed'], installed)
        self.assertEqual(current['summary']['advisories'], advisories)
        rows.remove(rec)
        rows.remove(rapid)
        strata = next(row for row in rows if row['id'] == 'strata')
        self.assertEqual(strata['label'], 'Strata')
        self.assertEqual(strata['update']['docsUrl'], 'https://github.com/Niko1221/Strata')
        self.assertIn('BF16', str(strata))
        rows.remove(strata)
        installed = sum(bool(row.get('selected')) for row in rows)
        advisories = sum(row['level'] != 'ready' for row in rows)
        message = (
            'All runtimes are installed; one or more advanced checks still need review.'
            if installed == len(rows) and advisories else
            'All selected runtimes passed their local checks.' if installed == len(rows) else
            f'{installed} of {len(rows)} runtimes are installed; missing engines remain optional.'
        )
        current['summary'] = {'installed':installed, 'total':len(rows), 'advisories':advisories, 'message':message}
        return current

    def splash_150_inventory_expected(self,inventory):
        expected=copy.deepcopy(inventory)
        splash=next(row for row in expected['runtimes'] if row['id']=='splash')
        checks={check['label']:check for check in splash['checks']}
        self.assertEqual(checks['Exact model contract']['detail'],
            'Qwen 27B and 35B-A3B execution with local GGUF / MLX Q4 weights and a matching DFlash2 draft.')
        self.assertEqual(checks['Platform']['detail'],
            'Splash 1.2.1 · GGUF / MLX Q4 · macOS 26.4 · Apple silicon M3+ · 36 GB+')
        # Only these two Splash descriptions changed. Every remaining field,
        # every other engine and the complete inventory envelope stay exact.
        checks['Exact model contract']['detail']=SPLASH_150_MODEL_DETAIL
        checks['Platform']['detail']=SPLASH_150_PLATFORM
        return expected

    def test_full_inventory_and_candidates_match_frozen_original(self):
        for installed in (False,True):
            with self.subTest(installed=installed),tempfile.TemporaryDirectory(prefix='runtime-catalog-') as folder:
                generated=PrivateRuntimeFixture(folder,installed)
                inspector = SimpleNamespace(inspect_runtime=lambda path:{
                    'binary':path, 'python':'/generated/python3', 'version':'0.16.9',
                    'ready':True, 'identity':{'generated':True}, 'reason':'Generated verified metadata'})
                with generated.patches(), mock.patch.dict(sys.modules, {'rapidmlx_runtime':inspector}):
                    before=generated.snapshot();catalog=generated.catalog()
                    self.assertEqual(self.without_new_optional_inventory(catalog.runtime_inventory()),self.splash_150_inventory_expected(original.runtime_inventory()))
                    for runtime in launcher.RUNTIME_CANDIDATE_SPECS:
                        self.assertEqual(catalog.runtime_candidates(runtime),original.runtime_candidates(runtime))
                        if runtime != 'rapidmlx':
                            self.assertEqual(catalog.runtime_candidate_details(runtime),original.runtime_candidate_details(runtime))
                    self.assertEqual(generated.snapshot(),before)
                    self.assertEqual(launcher.BINARIES,generated.binary_paths)

    def test_update_install_and_blocked_plans_match_without_writes(self):
        with tempfile.TemporaryDirectory(prefix='runtime-plan-') as folder:
            generated=PrivateRuntimeFixture(folder)
            with generated.patches():
                catalog=generated.catalog()
                for channel in ('stable','preview'):
                    with self.subTest(channel=channel):
                        before=generated.snapshot()
                        self.assertEqual(catalog.build_runtime_update_plan(channel),original.build_runtime_update_plan(channel))
                        self.assertEqual(generated.snapshot(),before)
                        release=launcher.RUNTIME_UPDATE_CATALOG[channel]
                        destination=generated.managed/('omlx-'+release['version'])
                        destination.mkdir(parents=True)
                        self.assertEqual(catalog.build_runtime_update_plan(channel),original.build_runtime_update_plan(channel))
                        self.assertEqual(catalog.build_runtime_update_plan(channel)['action'],'blocked')
                self.assertEqual(catalog.runtime_update_overview(),original.runtime_update_overview())
                self.assertEqual(launcher.BINARIES,generated.binary_paths)

    def test_adoption_checks_current_hash_and_version_every_time(self):
        with tempfile.TemporaryDirectory(prefix='runtime-adoption-') as folder:
            generated=PrivateRuntimeFixture(folder)
            release=launcher.RUNTIME_UPDATE_CATALOG['preview']
            target=generated.managed/('omlx-'+release['version']);binary=target/'bin'/'omlx'
            binary.parent.mkdir(parents=True);binary.write_text('#!/bin/sh\nexit 0\n');binary.chmod(0o700)
            direct=target/'lib'/'python3.11'/'site-packages'/('omlx-'+release['version']+'.dist-info')/'direct_url.json'
            direct.parent.mkdir(parents=True)
            direct.write_text(json.dumps({'archive_info':{'hashes':{'sha256':release['sha256']}}}))
            generated.versions[str(binary)]='oMLX '+release['version']
            with generated.patches():
                catalog=generated.catalog()
                self.assertEqual(catalog.managed_runtime_verification(str(binary)),original.managed_runtime_verification(str(binary)))
                plan=catalog.build_runtime_update_plan('preview')
                self.assertEqual(plan,original.build_runtime_update_plan('preview'))
                self.assertTrue(plan['canStart']);self.assertEqual(plan['action'],'verify')
                direct.write_text(json.dumps({'archive_info':{'hashes':{'sha256':'0'*64}}}))
                rejected=catalog.build_runtime_update_plan('preview')
                self.assertEqual(rejected,original.build_runtime_update_plan('preview'))
                self.assertFalse(rejected['canStart'])
                generated.versions[str(binary)]='oMLX 9.9.9'
                self.assertEqual(catalog.managed_runtime_verification(str(binary)),original.managed_runtime_verification(str(binary)))
                self.assertFalse(catalog.managed_runtime_verification(str(binary))['verified'])

    def test_import_has_no_file_process_network_or_controller_activity(self):
        source=Path(runtime_catalog.__file__).read_text()
        tree=ast.parse(source)
        imports={n.module for n in tree.body if isinstance(n,ast.ImportFrom)}|{a.name for n in tree.body if isinstance(n,ast.Import) for a in n.names}
        self.assertNotIn('launcher',imports);self.assertNotIn('runtime_update_jobs',imports)
        spec=importlib.util.spec_from_file_location('_runtime_catalog_no_io',runtime_catalog.__file__)
        module=importlib.util.module_from_spec(spec)
        with mock.patch('builtins.open',side_effect=AssertionError('import opened a file')),mock.patch.object(runtime_catalog.subprocess,'run',side_effect=AssertionError('import ran a process')):
            sys.modules[spec.name]=module
            try:spec.loader.exec_module(module)
            finally:sys.modules.pop(spec.name,None)

    def test_policy_detaches_metadata_and_selection_remains_live(self):
        with tempfile.TemporaryDirectory(prefix='runtime-policy-') as folder:
            generated=PrivateRuntimeFixture(folder)
            with generated.patches():
                catalog=generated.catalog()
                old=catalog.policy.releases.runtime_update_catalog['preview']['version']
                with mock.patch.dict(launcher.RUNTIME_UPDATE_CATALOG['preview'],{'version':'9.9.9'}):
                    self.assertEqual(catalog._runtime_update_release('preview')['version'],old)
                release=catalog._runtime_update_release('preview');release['directSources'][0]['commit']='bad'
                self.assertNotEqual(catalog._runtime_update_release('preview')['directSources'][0]['commit'],'bad')
                with self.assertRaises(TypeError):catalog.policy.releases.runtime_update_catalog['preview']['version']='bad'
                before=catalog.runtime_candidate_details('omlx')[0]
                self.assertTrue(before['selected'])
                launcher.BINARIES['omlx']=None
                self.assertFalse(catalog.runtime_candidate_details('omlx')[0]['selected'])

    def test_missing_splash_docs_link_uses_actual_audited_release(self):
        with tempfile.TemporaryDirectory(prefix='runtime-splash-link-') as folder:
            generated=PrivateRuntimeFixture(folder)
            with generated.patches():
                catalog=generated.catalog()
                catalog.policy=replace(catalog.policy,links=replace(catalog.policy.links,
                    ssd_streaming_runtime_urls={key:value for key,value in catalog.policy.links.ssd_streaming_runtime_urls.items() if key!='splash'}))
                inventory=catalog.runtime_inventory()
                splash=next(row for row in inventory['runtimes'] if row['id']=='splash')
                self.assertEqual(splash['update']['docsUrl'],launcher.RUNTIME_RELEASE_CATALOG['splash']['releaseUrl'])
                self.assertEqual(len(inventory['runtimes']),12)
                with mock.patch.object(launcher,'SSD_STREAMING_RUNTIME_URLS',dict(catalog.policy.links.ssd_streaming_runtime_urls)):
                    self.assertEqual(inventory,launcher.runtime_inventory())

    def test_installed_lmstudio_pack_and_preference_current_file_contract(self):
        with tempfile.TemporaryDirectory(prefix='runtime-pack-') as folder:
            generated=PrivateRuntimeFixture(folder)
            pack=generated.pack_root/'llama.cpp-metal-1.2.3';pack.mkdir(parents=True)
            binary=pack/'bin'/'server';binary.parent.mkdir();binary.write_bytes(b'generated-native');binary.chmod(0o700)
            library=pack/'lib'/'native.dylib';library.parent.mkdir();library.write_bytes(b'library')
            link=pack/'lib'/'alias.dylib';link.symlink_to('native.dylib')
            manifest={'engine':'llama.cpp','extension_type':'engine','version':'1.2.3','name':'llama.cpp-metal',
                'supported_model_formats':['gguf'],'engine_protocol_server':{'runtime_kind':'llama-server','executable_relative_path':'bin/server'},
                'target_libraries':[{'name':'lib/native.dylib'},{'name':'lib/alias.dylib'}]}
            inventory={'schema_version':1,'runtime_kind':'llama-server','executable_relative_path':'bin/server',
                'files':[{'relative_path':'bin/server','executable':True}]}
            (pack/'backend-manifest.json').write_text(json.dumps(manifest))
            (pack/'engine-protocol-server-artifacts.json').write_text(json.dumps(inventory))
            preference=generated.home/'.lmstudio'/'.internal'/'backend-preferences-v1.json'
            preference.parent.mkdir();preference.write_text(json.dumps([{'model_format':'gguf','name':'llama.cpp-metal','version':'1.2.3'}]))
            with generated.patches():
                catalog=generated.catalog()
                initial=catalog.lmstudio_runtime_packs()
                self.assertEqual(initial,original.lmstudio_runtime_packs())
                self.assertTrue(next(row for row in initial if row['kind']=='llama.cpp')['manifestContractVerified'])
                self.assertEqual(catalog.lmstudio_backend_preference(),original.lmstudio_backend_preference())
                for mutation in ('replace','link-escape','manifest-change','duplicate-files'):
                    with self.subTest(mutation=mutation):
                        if mutation=='replace':
                            replacement=pack/'replacement';replacement.write_bytes(b'generated-native');replacement.chmod(0o700)
                            old=binary.stat();os.utime(replacement,ns=(old.st_atime_ns,old.st_mtime_ns));os.replace(replacement,binary)
                            changed=catalog.lmstudio_runtime_packs()
                            self.assertEqual(changed,original.lmstudio_runtime_packs())
                            self.assertNotEqual(initial,changed)
                        elif mutation=='link-escape':
                            link.unlink();link.symlink_to('/outside/native.dylib')
                        elif mutation=='manifest-change':
                            manifest['version']='9.9.9';(pack/'backend-manifest.json').write_text(json.dumps(manifest))
                        else:
                            inventory['files']*=2;(pack/'engine-protocol-server-artifacts.json').write_text(json.dumps(inventory))
                        if mutation!='replace':
                            changed=catalog.lmstudio_runtime_packs();self.assertEqual(changed,original.lmstudio_runtime_packs())
                            self.assertFalse(next(row for row in changed if row['kind']=='llama.cpp')['manifestContractVerified'])
                preference.write_text(json.dumps([{'model_format':'gguf','name':'a','version':'1.0.0'},{'model_format':'gguf','name':'b','version':'1.0.0'}]))
                self.assertFalse(catalog.lmstudio_backend_preference()['ready'])

    def test_frozen_audited_release_and_version_outputs(self):
        fixture=json.loads(Path(__file__).with_name('fixtures').joinpath('runtime-catalog-v1.json').read_text())
        self.assertEqual(fixture['preExtractionDefinitionsSha256'],SOURCE_SHA)
        self.assertGreaterEqual(len(fixture['cases']),70)
        catalog=make_runtime_catalog(launcher)
        for case in fixture['cases']:
            with self.subTest(method=case['method'],args=case['args']):
                result=getattr(catalog,case['method'])(*copy.deepcopy(case['args']))
                expected=copy.deepcopy(case['expected'])
                if case['method']=='audited_runtime_release' and case['args'][0]=='splash':
                    # Extend only Splash's audited release snapshot; all other
                    # frozen runtime/version records remain byte-for-byte.
                    expected.update(copy.deepcopy(SPLASH_150_RELEASE))
                    expected['detail']=expected['detail'].replace('1.2.1','1.5.0')
                    if case['args'][1]=='1.2.1':
                        expected.update(state='update-available',label='Update available',
                            detail='Audited upstream release 1.5.0 is newer than the selected 1.2.1.',
                            updateAvailable=True,catalogCurrent=False,needsReview=True)
                self.assertEqual(json.loads(json.dumps(result)),expected)

    def test_splash_150_release_current_and_outdated_dispositions(self):
        catalog=make_runtime_catalog(launcher)
        self.assertEqual(launcher.RUNTIME_RELEASE_CATALOG['splash'],SPLASH_150_RELEASE)
        for installed,state,current,update,review in (
            ('','not-installed',False,False,True),
            ('1.2.1','update-available',False,True,True),
            ('1.3.2','update-available',False,True,True),
            ('1.5.0','current',True,False,False),
            ('1.5.1','newer-unreviewed',False,False,True),
            ('unknown','unknown-local-version',False,False,True),
        ):
            with self.subTest(installed=installed):
                result=catalog.audited_runtime_release('splash',installed)
                for field,value in SPLASH_150_RELEASE.items():self.assertEqual(result[field],value)
                self.assertEqual((result['state'],result['catalogCurrent'],result['updateAvailable'],result['needsReview']),
                    (state,current,update,review))
                self.assertEqual(result['installedVersion'],installed or None)

    def test_splash_bf16_fix_is_preferred_with_official_releases_available_for_rollback(self):
        specs=launcher.RUNTIME_CANDIDATE_SPECS['splash']
        expected=['launcher-1.5.0-bf16-r1','launcher-1.6.0-m5-pro-r1',
                  'launcher-1.4.0-bf16-r1','launcher-1.4.0','launcher-1.2.1']
        self.assertEqual([row[0] for row in specs[:len(expected)]],expected)
        self.assertEqual(Path(specs[0][1]).relative_to(launcher.APP_DIR).as_posix(),
            'bench/runtimes/splash-1.5.0-llm-launcher-bf16-r1/engine/splash')
        with tempfile.TemporaryDirectory(prefix='runtime-splash-preferred-') as folder:
            generated=PrivateRuntimeFixture(folder)
            private_specs=[]
            for channel,_path,label in specs[:len(expected)]:
                binary=generated.root/channel/'engine'/'splash'
                binary.parent.mkdir(parents=True);binary.write_text('#!/bin/sh\nexit 0\n');binary.chmod(0o700)
                private_specs.append((channel,str(binary),label))
            generated.specs['splash']=tuple(private_specs)
            with generated.patches(),mock.patch.object(launcher,'read_json',return_value={'selections':{}}):
                candidates=launcher.runtime_candidates('splash')
                self.assertEqual([row['channel'] for row in candidates],expected)
                self.assertEqual(launcher.preferred_runtime_binary('splash'),private_specs[0][1])
                with mock.patch.object(launcher,'read_json',return_value={'selections':{'splash':candidates[1]['id']}}):
                    self.assertEqual(launcher.preferred_runtime_binary('splash'),private_specs[1][1])

    def test_promotion_plan_full_contract_and_live_admission_match_original(self):
        with tempfile.TemporaryDirectory(prefix='runtime-promotion-') as folder:
            generated=PrivateRuntimeFixture(folder)
            paths=[generated.root/'selected'/'omlx',generated.root/'candidate'/'omlx']
            for path in paths:path.parent.mkdir();path.write_bytes(b'generated runtime');path.chmod(0o700)
            details=[{'id':role,'path':str(path),'resolvedPath':str(path),'channelLabel':role,
                'version':'0.6.4' if role=='selected' else '0.7.0.dev2','selected':role=='selected',
                'managedVerification':{'verified':True,'artifactSha256':('1' if role=='selected' else '2')*64}}
                for role,path in zip(('selected','candidate'),paths)]
            job={'backend':'omlx','modelId':'generated-model','modelFingerprint':'a'*64,'model':{'name':'Generated model'},
                'project':str(generated.root),'context':8192,'output':128,'reasoning':'low','client':'chat','chat':{},
                'suiteName':'quick','suite':{'label':'Generated quick suite','promptTokens':[512,2048],'repeats':1},
                'workloadKind':'throughput','evidence':{'samplingFingerprint':'s'*64}}
            payload={'candidateId':'candidate','backend':'mtplx','options':{'acceleration':'mtp','kv':'turbo','anePrefill':'cpu','burst':'fast'},'scope':'ignored','suite':'quick'}
            original_payload=copy.deepcopy(payload);admission={'decision':'ready','label':'Ready','detail':'Generated current physical memory'}
            with generated.patches(),mock.patch.object(launcher,'validated_benchmark_request',side_effect=lambda *_a,**_kw:copy.deepcopy(job)) as validator,mock.patch.object(launcher,'route_qualification_memory_admission',side_effect=lambda *_a,**_kw:copy.deepcopy(admission)) as resource,mock.patch.object(launcher,'strict_model_load_admission_ready',side_effect=lambda value:value['decision']=='ready'),mock.patch.object(launcher,'hardware_fingerprint',return_value='generated-mac'),mock.patch.object(launcher,'load_runtime_promotion_records',return_value=[]):
                catalog=generated.catalog();catalog.runtime_candidate_details=lambda _runtime:copy.deepcopy(details)
                with mock.patch.object(original,'runtime_candidate_details',side_effect=lambda _runtime:copy.deepcopy(details)):
                    before=generated.snapshot();plan=catalog.build_runtime_promotion_plan(payload,[job['model']],resource_snapshot={'generated':True})
                    self.assertEqual(plan,original.build_runtime_promotion_plan(payload,[job['model']],resource_snapshot={'generated':True}))
                    self.assertEqual(catalog.runtime_promotion_public_plan(plan),original.runtime_promotion_public_plan(plan))
                    self.assertEqual(plan['executionOrder'],['selected','candidate'])
                    self.assertEqual(plan['_job']['modes'],['ar'])
                    self.assertEqual(validator.call_args.args[0]['options'],{'acceleration':'off','kv':'off','anePrefill':'off','burst':'balanced'})
                    self.assertNotIn('scope',validator.call_args.args[0]);self.assertTrue(validator.call_args.kwargs['allow_baseline_only'])
                    self.assertEqual(resource.call_args.kwargs,{'resource_snapshot':{'generated':True}})
                    self.assertEqual(payload,original_payload);self.assertEqual(generated.snapshot(),before)
                    admission['decision']='blocked'
                    blocked=catalog.build_runtime_promotion_plan(payload,[job['model']])
                    self.assertEqual(blocked['id'],plan['id']);self.assertFalse(blocked['canStart'])
                    prior={'contractId':plan['contractId'],'createdAt':'2026-10-06','executionOrder':['selected','candidate']}
                    with mock.patch.object(launcher,'load_runtime_promotion_records',return_value=[prior]):
                        alternated=catalog.build_runtime_promotion_plan(payload,[job['model']])
                        self.assertEqual(alternated,original.build_runtime_promotion_plan(payload,[job['model']]))
                        self.assertEqual(alternated['executionOrder'],['candidate','selected'])
                    details[1]['managedVerification']['verified']=False
                    with self.assertRaisesRegex(ValueError,'official wheel checksum'):catalog.build_runtime_promotion_plan(payload,[job['model']])
                    self.assertEqual(launcher.BINARIES,generated.binary_paths)

    def test_promotion_complete_results_keep_quality_speed_physical_and_thermal_gates(self):
        from tests.memory_fixtures import physical_telemetry
        def result(speed,cooldown):
            return {'qualityHash':'a'*64,'qualityCompletionTokens':64,
                'samples':[{'promptTokens':prompt,'completionTokens':128,'targetPromptTokens':prompt,'repetition':1,
                    'totalSeconds':128/speed,'ttftSeconds':0.5,'endToEndTokensPerSecond':speed} for prompt in (512,2048)],
                'resourceCooldown':{'status':cooldown},'resourceTelemetry':physical_telemetry({
                    'version':1,'memoryAvailable':True,'peakPressureDeltaBytes':256*1024**2,'baselineHeadroomPercent':60.0,
                    'minimumHeadroomPercent':55.0,'totalMemoryBytes':64*1024**3,'thermalAvailable':True,
                    'thermalStartValue':0,'thermalWorstValue':0,'lowPowerMode':False})}
        catalog=make_runtime_catalog(launcher)
        catalog.clock=runtime_catalog.RuntimeClock(checked_at=lambda:'fixed',now=lambda:NOW,record_id=lambda:'generated-id')
        job={'modelFingerprint':'a'*64,'suiteName':'quick','suite':{'scenarios':[]},'workloadKind':'throughput','client':'chat',
            'reasoning':'low','context':8192,'output':128,'evidence':{'samplingFingerprint':'s'*64}}
        plan={'id':'plan','contractId':'contract','_job':job,'model':{'id':'model','fingerprint':'a'*64},'workload':{},
            'selected':{'id':'selected','version':'0.6.4'},'candidate':{'id':'candidate','version':'0.7.0.dev2'},'executionOrder':['selected','candidate']}
        with mock.patch.object(launcher,'hardware_fingerprint',return_value='generated-mac'),mock.patch.object(original.uuid,'uuid4',return_value='generated-id'),mock.patch.object(original,'datetime') as clock:
            clock.now.return_value=NOW
            for case in ('valid','quality','slow','memory','thermal','missing-physical','incomplete'):
                with self.subTest(case=case):
                    results={'selected':result(100,'reference-ready'),'candidate':result(110,'ready')}
                    target=results['candidate']
                    if case=='quality':target['qualityHash']='b'*64
                    if case=='slow':target['samples'][0]['endToEndTokensPerSecond']=99
                    if case=='memory':
                        target['resourceTelemetry']['peakReclaimableDeltaBytes']=2*1024**3
                        target['resourceTelemetry']['minimumHeadroomBytes']=target['resourceTelemetry']['baselineHeadroomBytes']-2*1024**3
                    if case=='thermal':target['resourceTelemetry']['thermalWorstValue']=1
                    if case=='missing-physical':target['resourceTelemetry'].pop('memorySemanticsVersion')
                    if case=='incomplete':results.pop('candidate')
                    if case=='incomplete':
                        with self.assertRaisesRegex(RuntimeError,'both exact routes'):catalog.build_runtime_promotion_result(plan,results)
                        continue
                    actual=catalog.build_runtime_promotion_result(plan,results)
                    self.assertEqual(actual,original.build_runtime_promotion_result(plan,results))
                    self.assertEqual(actual['canPromote'],case=='valid')
                    self.assertFalse(actual['selectionChanged']);self.assertIsNone(actual['promotedAt'])
                    self.assertNotIn('signature',actual['measurements']['candidate'])

    def kernel_fixture(self, generated):
        binary=Path(generated.binary_paths['omlx'])
        python=binary.parent/'python';python.write_bytes(b'generated python');python.chmod(0o700)
        package=binary.parent.parent/'lib'/'python3.11'/'site-packages'/'omlx'
        artifacts=package/'custom_kernels'/'qwen35_prefill';artifacts.mkdir(parents=True)
        artifact=artifacts/'_ext.generated.so';artifact.write_bytes(b'generated kernel')
        source=package/'custom_kernels'/'__init__.py';source.write_text('generated source\n')
        bytecode=source.parent/'__pycache__';bytecode.mkdir();(bytecode/'__init__.generated.pyc').write_bytes(b'generated bytecode')
        mlx=package.parent/'mlx';mlx.mkdir();(mlx/'__init__.py').write_text('generated dependency\n')
        return binary,python,artifact,source

    def test_kernel_ready_positive_raw_cache_matches_original_without_repeated_cli(self):
        with tempfile.TemporaryDirectory(prefix='kernel-equivalence-') as folder:
            generated=PrivateRuntimeFixture(folder);binary,python,artifact,source=self.kernel_fixture(generated)
            with generated.patches():
                catalog=generated.catalog()
                first=catalog.omlx_qwen_kernel_status(str(binary))
                self.assertEqual(first,original.omlx_qwen_kernel_status(str(binary)))
                calls=len(generated.probe_calls)
                second=catalog.omlx_qwen_kernel_status(str(binary));second['ready']=False
                self.assertTrue(catalog.omlx_qwen_kernel_status(str(binary))['ready'])
                self.assertEqual(len(generated.probe_calls),calls)
                self.assertEqual(len(catalog.state.kernel_probes),1)
                self.assertTrue(all(isinstance(raw,tuple) and type(raw[0]) is int and isinstance(raw[1],str)
                    for raw in catalog.state.kernel_probes.values()))

    def test_original_kernel_cache_preserved_mtime_replacement_repro_new_domain_rechecks(self):
        with tempfile.TemporaryDirectory(prefix='kernel-old-stale-') as folder:
            generated=PrivateRuntimeFixture(folder);binary,python,artifact,source=self.kernel_fixture(generated)
            with generated.patches():
                catalog=generated.catalog()
                self.assertTrue(catalog.omlx_qwen_kernel_status(str(binary))['ready'])
                self.assertTrue(original.omlx_qwen_kernel_status(str(binary))['ready'])
                details=artifact.stat();replacement=artifact.with_suffix('.replacement');replacement.write_bytes(b'different kernel')
                os.utime(replacement,ns=(details.st_atime_ns,details.st_mtime_ns));os.replace(replacement,artifact)
                generated.run=lambda *_a,**_kw:SimpleNamespace(returncode=0,stdout='__LLM_LAUNCHER_KERNEL__{"available":false}\n',stderr='')
                with mock.patch.object(launcher.subprocess,'run',side_effect=generated.run):
                    self.assertTrue(original.omlx_qwen_kernel_status(str(binary))['ready'],'Frozen original reproduces stale ready')
                    self.assertFalse(catalog.omlx_qwen_kernel_status(str(binary))['ready'])

    def test_kernel_entrypoint_interpreter_artifact_source_and_symlink_changes_are_fresh(self):
        for changed in ('binary','python','artifact','source','bytecode','dependency','in-place','symlink'):
            with self.subTest(changed=changed),tempfile.TemporaryDirectory(prefix='kernel-fresh-') as folder:
                generated=PrivateRuntimeFixture(folder);binary,python,artifact,source=self.kernel_fixture(generated)
                with generated.patches():
                    catalog=generated.catalog();self.assertTrue(catalog.omlx_qwen_kernel_status(str(binary))['ready'])
                    old_calls=len(generated.probe_calls)
                    path={'binary':binary,'python':python,'artifact':artifact,'source':source,
                        'bytecode':source.parent/'__pycache__'/'__init__.generated.pyc',
                        'dependency':source.parents[1].parent/'mlx'/'__init__.py','in-place':artifact,'symlink':artifact}[changed]
                    details=path.stat()
                    if changed=='in-place':
                        path.write_bytes(b'changed in place');os.utime(path,ns=(details.st_atime_ns,details.st_mtime_ns))
                    elif changed=='symlink':
                        target=path.with_suffix('.other.so');target.write_bytes(b'changed link target')
                        os.utime(target,ns=(details.st_atime_ns,details.st_mtime_ns));path.unlink();path.symlink_to(target.name)
                    else:
                        replacement=path.with_suffix('.replacement');replacement.write_bytes(b'changed replacement')
                        replacement.chmod(details.st_mode & 0o777);os.utime(replacement,ns=(details.st_atime_ns,details.st_mtime_ns));os.replace(replacement,path)
                    self.assertTrue(catalog.omlx_qwen_kernel_status(str(binary))['ready'])
                    self.assertGreater(len(generated.probe_calls),old_calls)

    def test_kernel_change_during_probe_and_failed_outputs_never_accept_or_cache(self):
        for case in ('raced','exit-error','oversize','invalid','nonboolean'):
            with self.subTest(case=case),tempfile.TemporaryDirectory(prefix='kernel-race-') as folder:
                generated=PrivateRuntimeFixture(folder);binary,python,artifact,source=self.kernel_fixture(generated)
                with generated.patches():
                    catalog=generated.catalog()
                    def run(*_a,**_kw):
                        if case=='raced':source.write_text('changed during check\n')
                        stdout={'oversize':'x'*131_073,'invalid':'__LLM_LAUNCHER_KERNEL__not-json',
                            'nonboolean':'__LLM_LAUNCHER_KERNEL__{"available":1}'}.get(case,'__LLM_LAUNCHER_KERNEL__{"available":true}')
                        return SimpleNamespace(returncode=1 if case=='exit-error' else 0,stdout=stdout,stderr='')
                    catalog.probes=replace(catalog.probes,run_capture=run)
                    response=catalog.omlx_qwen_kernel_status(str(binary))
                    self.assertFalse(response['ready'])
                    if case in {'raced','exit-error','oversize'}:self.assertEqual(catalog.state.kernel_probes,{})
                    catalog.probes=replace(catalog.probes,run_capture=generated.run)
                    self.assertTrue(catalog.omlx_qwen_kernel_status(str(binary))['ready'])

    def test_root_wiring_reuse_invalidates_changed_policy_and_keeps_live_paths_callbacks(self):
        with tempfile.TemporaryDirectory(prefix='runtime-wiring-') as folder:
            generated=PrivateRuntimeFixture(folder)
            with generated.patches():
                first=launcher._runtime_catalog()
                self.assertIs(first,launcher._runtime_catalog())
                with mock.patch.dict(launcher.RUNTIME_RELEASE_CATALOG['omlx'],{'displayVersion':'changed current policy'}):
                    updated=launcher._runtime_catalog()
                    self.assertIsNot(first,updated)
                    self.assertEqual(updated.audited_runtime_release('omlx','')['displayVersion'],'changed current policy')
                    self.assertIs(updated,launcher._runtime_catalog())
                restored=launcher._runtime_catalog()
                self.assertIsNot(updated,restored)
                with mock.patch.object(launcher,'MANAGED_RUNTIMES_DIR',generated.root/'changed-managed'):
                    self.assertIs(restored,launcher._runtime_catalog())
                    self.assertEqual(restored._runtime_update_target(restored._runtime_update_release('stable')).parent,generated.root/'changed-managed')
                with mock.patch.object(launcher,'command_version',return_value='9.9.9'):
                    self.assertIs(restored,launcher._runtime_catalog())
                    self.assertEqual(restored.runtime_candidate_details('omlx')[0]['version'],'9.9.9')
                launcher.BINARIES['omlx']=None
                self.assertFalse(restored.runtime_candidate_details('omlx')[0]['selected'])
                self.assertIs(launcher._RUNTIME_KERNEL_CACHE,restored.state.kernel_probes)

    def test_pure_root_facades_skip_full_wiring_and_preserve_current_policy(self):
        with mock.patch.object(launcher,'_runtime_catalog',side_effect=AssertionError('pure helper built full runtime wiring')):
            for version in ('omlx 0.6.4','0.7.0.dev2','unknown'):
                self.assertEqual(launcher.parsed_omlx_version(version),original.parsed_omlx_version(version))
                self.assertEqual(launcher.semantic_version_key(version),original.semantic_version_key(version))
            with mock.patch.object(launcher,'DFLASH2_MINIMUM_RUNTIME','9.9.9'):
                self.assertFalse(launcher.omlx_supports_dflash2('0.7.0'))
            self.assertEqual(launcher.lmstudio_runtime_identity('cli','app',[]),original.lmstudio_runtime_identity('cli','app',[]))

    def test_kernel_failed_check_retries_and_raw_receipts_remain_bounded(self):
        with tempfile.TemporaryDirectory(prefix='kernel-bounds-') as folder:
            generated=PrivateRuntimeFixture(folder);binary,python,artifact,source=self.kernel_fixture(generated)
            with generated.patches():
                catalog=generated.catalog();calls=[]
                def unavailable(*_a,**_kw):
                    calls.append(1)
                    return SimpleNamespace(returncode=0,stdout='__LLM_LAUNCHER_KERNEL__{"available":false}',stderr='')
                catalog.probes=replace(catalog.probes,run_capture=unavailable)
                self.assertFalse(catalog.omlx_qwen_kernel_status(str(binary))['ready'])
                self.assertFalse(catalog.omlx_qwen_kernel_status(str(binary))['ready'])
                self.assertEqual(len(calls),2);self.assertEqual(catalog.state.kernel_probes,{})
                catalog.probes=replace(catalog.probes,run_capture=generated.run)
                for index in range(36):
                    source.write_text('generation '+str(index))
                    self.assertTrue(catalog.omlx_qwen_kernel_status(str(binary))['ready'])
                self.assertEqual(len(catalog.state.kernel_probes),32)

    def test_frozen_source_and_integrated_public_signatures_stay_exact(self):
        fixture=json.loads(Path(__file__).with_name('fixtures').joinpath('runtime-catalog-v1.json').read_text())
        original_source=Path(original.__file__).read_text();old={node.name:node for node in ast.parse(original_source).body if isinstance(node,ast.FunctionDef)}
        source='\n\n'.join(ast.get_source_segment(original_source,old[name]) for name in fixture['extractedFunctions'])
        self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),SOURCE_SHA)
        current={node.name:node for node in ast.parse(Path(launcher.__file__).read_text()).body if isinstance(node,ast.FunctionDef)}
        for name in fixture['extractedFunctions']:
            with self.subTest(name=name):
                self.assertEqual(ast.dump(current[name].args),ast.dump(old[name].args))
                self.assertEqual(ast.dump(current[name].returns),ast.dump(old[name].returns))

    def test_kernel_package_walk_is_bounded_and_external_subtrees_are_not_followed(self):
        with tempfile.TemporaryDirectory(prefix='kernel-tree-bounds-') as folder:
            generated=PrivateRuntimeFixture(folder);binary,python,artifact,source=self.kernel_fixture(generated)
            with generated.patches():
                catalog=generated.catalog()
                with mock.patch.object(runtime_catalog,'KERNEL_PACKAGE_MAX_ENTRIES',2):
                    self.assertFalse(catalog.omlx_qwen_kernel_status(str(binary))['ready'])
                self.assertEqual(generated.probe_calls,[])
                outside=generated.root/'outside';outside.mkdir();(outside/'unknown.py').write_text('outside')
                (source.parent/'external').symlink_to(outside,target_is_directory=True)
                self.assertFalse(catalog.omlx_qwen_kernel_status(str(binary))['ready'])
                self.assertEqual(generated.probe_calls,[])
                self.assertEqual(catalog.state.kernel_probes,{})

    def test_actual_private_python_selfcheck_is_read_only_on_first_import(self):
        # This executes only a generated status function: no MLX/native library/model.
        import subprocess
        real_run=subprocess.run
        with tempfile.TemporaryDirectory(prefix='kernel-readonly-') as folder:
            generated=PrivateRuntimeFixture(folder);binary,python,artifact,source=self.kernel_fixture(generated)
            python.unlink();python.symlink_to(sys.executable)
            (source.parents[1]/'__init__.py').write_text('')
            source.write_text("def native_kernel_status():\n    return {'qwen35_prefill': {'available': True}}\n")
            with generated.patches(),mock.patch.dict(os.environ,{'PYTHONPATH':str(source.parents[2])},clear=False):
                catalog=generated.catalog();catalog.probes=replace(catalog.probes,run_capture=real_run)
                before=generated.snapshot();environment=dict(os.environ)
                self.assertTrue(catalog.omlx_qwen_kernel_status(str(binary))['ready'])
                self.assertEqual(generated.snapshot(),before,'Inspection must not generate Python bytecode')
                self.assertEqual(dict(os.environ),environment,'Only child environment may change')
                self.assertTrue(catalog.omlx_qwen_kernel_status(str(binary))['ready'])
                self.assertEqual(generated.snapshot(),before)
