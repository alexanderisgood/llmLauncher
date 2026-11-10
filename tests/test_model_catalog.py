"""Complete catalog/doctor equivalence on isolated artifacts and explicit ports."""
import ast
import copy
from contextlib import ExitStack
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import launcher
import model_catalog
from tests.fixtures import model_catalog_legacy
from tests.helpers.model_catalog_fixture import make_catalog


FIXTURE = Path(__file__).with_name("fixtures") / "model-catalog-v1.json"


def write_header(path, tensors):
    offsets = 0
    entries = {}
    for name, shape in tensors.items():
        elements = 1
        for dimension in shape: elements *= dimension
        entries[name] = {"dtype":"BF16", "shape":shape, "data_offsets":[offsets,offsets+elements*2]}
        offsets += elements*2
    encoded = json.dumps(entries, separators=(",", ":")).encode()
    with path.open("wb") as stream:
        stream.write(len(encoded).to_bytes(8,"little"));stream.write(encoded)
        if offsets:stream.seek(8+len(encoded)+offsets-1);stream.write(b"\0")


class PrivateCatalogFixture:
    def __init__(self, folder):
        self.root = Path(folder).resolve()
        self.library = self.root / "models"
        self.library.mkdir()
        self.paths = {}
        for name, model_type in (("dense","qwen3_5"),("moe","qwen3_moe"),("kolibri","kolibri1"),("partial","qwen3_5")):
            path = self.library / name
            path.mkdir()
            config = {"model_type":model_type,"architectures":["Qwen3ForCausalLM"],
                "num_hidden_layers":2,"num_attention_heads":2,"num_key_value_heads":1,
                "head_dim":8,"hidden_size":16,"max_position_embeddings":32768,
                "quantization":{"bits":6,"group_size":64}}
            if model_type == "qwen3_moe":config.update(num_experts=4,num_experts_per_tok=2)
            (path/"config.json").write_text(json.dumps(config))
            (path/"generation_config.json").write_text('{"temperature":0.7,"top_p":0.9,"seed":17}')
            (path/"chat_template.jinja").write_text("{% if reasoning_effort in ['low', 'medium', 'xhigh'] %}{{ content }}{% endif %}")
            write_header(path/"model.safetensors", {"model.embed_tokens.weight":[4,16]})
            if name == "partial":(path/"model.part").write_bytes(b"partial")
            self.paths[name]=path
        self.paths["gguf"] = self.library / "gguf"
        self.paths["gguf"].mkdir()
        (self.paths["gguf"] / "model.gguf").write_bytes(b"GGUF"+b"\0"*1_000_001)
        self.alias = self.root / "model-alias"
        self.alias.symlink_to(self.library, target_is_directory=True)

    def native_record(self, backend):
        caps = {engine:{"runnable":engine==backend,"reason":"Generated exact native artifact" if engine==backend else "Different artifact",
            "mtp":False,"dflash":False,"kv":False,"preferredAcceleration":"off","fallbackAcceleration":"off",
            "depth":1,"depthMax":1,"agentReasoning":["auto"],"codexReasoning":["auto"],
            "runtimeVersion":"generated-runtime" if engine==backend else "Not applicable",
            "benchmarkModelFingerprint":"generated-"+backend,"localBenchmark":None,"localBenchmarks":[],"benchmarkHistoryCount":0}
            for engine in launcher.ENGINE_ADAPTERS}
        return {"id":"generated-"+backend,"name":"Generated "+backend,"path":str(self.paths["dense"]),
            "artifact":"generated-native-"+backend,"origins":["Generated native fixture"],"format":"native",
            "architecture":"Generated native architecture","modelType":"generated-native-"+backend,
            "nativeContext":32768,"quantization":"Pinned native precision","size":1024,"sizeLabel":"1.0 KiB",
            "ready":True,"status":"Ready","memoryGeometry":{"ready":False},"defaultSampling":{},
            "mtpSidecarSize":0,"templateReasoningEfforts":[],"backends":caps,
            **({"splash":{"draftCandidates":[]}} if backend=="splash" else {})}

    def patches(self, *, connected=False):
        stack=ExitStack()
        stack.enter_context(mock.patch.object(launcher.Path,"home",return_value=self.root))
        for name,value in {"STATE_DIR":self.root/"state","UZU_MODEL_CACHE_ROOT":self.root/"uzu-cache",
            "UZU_MODEL_REGISTRY_PATH":self.root/"uzu-registry.json","UZU_RESOLVED_MODELS_PATH":self.root/"uzu-resolved.json"}.items():
            stack.enter_context(mock.patch.object(launcher,name,value))
        binaries={name:"/generated/"+name for name in launcher.BINARIES}
        binaries["freetoken_native"]=None
        stack.enter_context(mock.patch.dict(launcher.BINARIES,binaries,clear=True))
        for name,value in {
            "model_roots":[("Generated",self.library),("Alias",self.alias)],
            "model_acquisition_roots":[{"path":str(self.library)}],
            "lmstudio_model_load_key_index":{},"load_benchmark_records":[],"load_ane_tuning_records":[],
            "physical_memory_bytes":48*1024**3,"lmstudio_runtime_packs":[],"runtime_app_status":{},
            "plist_version":"0.4.0","lmstudio_mtp_load_supported":True,
            "lmstudio_assistant_drafter_load_supported":False,"lmstudio_backend_preference":{},
            "lmstudio_gguf_catalog":[],"lmstudio_draft_compatibility_receipts":[],
            "omlx_qwen_kernel_status":{"ready":False,"reason":"Generated kernel unavailable"},
            "llamacpp_runtime_contract":{"ready":False,"reason":"Generated runtime missing"},
            "uzu_runtime_contract":{"ready":False,"reason":"Generated runtime missing"},
            "matching_benchmark_records":[],"matching_ane_tuning_record":None,
            "load_freetoken_connection":({"id":"generated-connection","endpoint":"https://fixture.invalid/v1","server":"Generated FreeToken","context":32768,"models":["remote-model"]} if connected else {}),
            "probe_whallm_endpoint":({"model":launcher.WHALLM_MODEL_ID,"revision":"generated-revision"} if connected else {}),
        }.items():stack.enter_context(mock.patch.object(launcher,name,return_value=copy.deepcopy(value)))
        stack.enter_context(mock.patch.object(launcher,"command_version",side_effect=lambda binary:"omlx 0.6.4" if binary and str(binary).endswith("omlx") else "generated-runtime"))
        for module,name,value in (
            (launcher.slotstream_runtime,"discover",{"ready":True,"modelPath":str(self.paths["dense"])}),
            (launcher.slotstream_runtime,"model_record",self.native_record("slotstream")),
            (launcher.splash_runtime,"inspect_install",{"ready":True,"packs":[{"id":"generated-pack"}]}),
            (launcher.splash_runtime,"source_candidates",[]),(launcher.splash_runtime,"installed_source_roots",[]),
            (launcher.splash_runtime,"inspect_sources",[]),(launcher.splash_runtime,"model_record",self.native_record("splash")),
            (launcher.whallm_runtime,"discover",{"ready":True}),(launcher.whallm_runtime,"model_record",self.native_record("whallm")),
            (launcher.kolibri_runtime,"inspect_runtime",{"identity":"generated-runtime","ready":True}),
        ):stack.enter_context(mock.patch.object(module,name,return_value=copy.deepcopy(value)))
        stack.enter_context(mock.patch.object(launcher.kolibri_runtime,"inspect_model",side_effect=lambda path:{"identity":"generated-kolibri","path":str(path)} if path==self.paths["kolibri"] else None))
        stack.enter_context(mock.patch.object(launcher.subprocess,"run",side_effect=AssertionError("Catalog fixture reached a real CLI")))
        return stack

    def catalog(self):
        result=make_catalog(launcher)
        # Two controller integration seams are owned inside the new domain;
        # production uses its full filesystem/CLI implementations.
        result.model_roots=lambda:[("Generated",self.library),("Alias",self.alias)]
        result.lmstudio_model_load_key_index=lambda:{}
        result.lmstudio_gguf_catalog=lambda *_a,**_k:[]
        result.lmstudio_draft_compatibility_receipts=lambda *_a,**_k:[]
        return result


class ModelCatalogTests(unittest.TestCase):
    def test_frozen_classifier_receipt_and_complete_doctor_outputs_match(self):
        fixture=json.loads(FIXTURE.read_text())
        self.assertEqual(fixture["preExtractionDefinitionsSha256"],"ac3957f06b7394917fee363e16916e2892fb9eb10cac9a1f72f0f7baae29a26e")
        self.assertEqual(len(fixture["cases"]),47)
        for case in fixture["cases"]:
            with self.subTest(method=case["method"]),mock.patch.dict(launcher.BINARIES,case.get("binaryAvailability",{})):
                catalog=make_catalog(launcher)
                # Preserve the frozen registry for these legacy cases. Rec and
                # Rapid discovery and their routes are covered independently.
                catalog.policy=replace(catalog.policy,engines={key:value for key,value in catalog.policy.engines.items() if key not in {'rec','rapidmlx','strata'}})
                result=getattr(catalog,case["method"])(*copy.deepcopy(case["args"]),**copy.deepcopy(case["kwargs"]))
                if isinstance(result,set):result=sorted(result)
                self.assertEqual(json.loads(json.dumps(result,allow_nan=False)),case["expected"])

    def test_full_scan_and_doctor_match_original_on_same_isolated_filesystem(self):
        for connected in (False,True):
            with self.subTest(connected=connected),tempfile.TemporaryDirectory(prefix="catalog-equivalence-") as folder:
                generated=PrivateCatalogFixture(folder)
                with generated.patches(connected=connected):
                    catalog=generated.catalog()
                    expected=model_catalog_legacy.scan_models()
                    actual=catalog.scan_models()
                    # The old scanner cannot compute the new Rapid route. Keep
                    # every other field exact and verify its new status apart.
                    for record in actual:
                        self.assertIn('rapidmlx',record['backends'])
                        self.assertFalse(record['backends']['rapidmlx']['runnable'])
                        self.assertEqual(record['backends']['rapidmlx']['runtimeVersion'],'Not installed')
                    actual_legacy=copy.deepcopy(actual)
                    expected_legacy=copy.deepcopy(expected)
                    for record in actual_legacy+expected_legacy:
                        record['backends'].pop('rapidmlx',None)
                    # Sharing a checkpoint with Slotstream no longer replaces
                    # every other engine's independently computed capability.
                    # Restore only the exact fields that the frozen scanner
                    # clobbered, using a scan without that origin registration.
                    with mock.patch.object(launcher.slotstream_runtime,'discover',return_value=None):
                        independent=catalog.scan_models()
                    for record in expected_legacy:
                        if record['name']!='Qwen3.8 Flash-Next · oMLX · SSD experts':
                            continue
                        self.assertEqual(record['path'],str(generated.paths['dense']))
                        plain=next(item for item in independent if item['id']==record['id'])
                        record['name']='Qwen3.8 Flash-Next · MLX 4-bit'
                        for backend,capability in record['backends'].items():
                            if capability.get('reason')!='Use the separate Slotstream route for this engine.':
                                continue
                            original=plain['backends'][backend]
                            for field in ('runnable','reason'):
                                capability[field]=original[field]
                            for field in ('state','tier','label','detail'):
                                capability['hostSupport'][field]=original['hostSupport'][field]
                    self.assertEqual(actual_legacy,expected_legacy)
                    self.assertEqual(catalog.model_library_inventory(actual_legacy),model_catalog_legacy.model_library_inventory(expected_legacy))
                    self.assertEqual({engine for record in actual for engine in record["backends"]},set(launcher.ENGINE_ADAPTERS))
                    dense=next(record for record in actual if record["path"]==str(generated.paths["dense"]) and "Generated" in record["origins"])
                    self.assertEqual(dense["origins"],["Generated","Alias"])
                    self.assertEqual(dense["defaultSampling"],{"temperature":0.7,"top_p":0.9,"seed":17})
                    self.assertEqual(len([record for record in actual if record["path"]==str(generated.paths["dense"]) and "Generated" in record["origins"]]),1)
                    self.assertEqual(catalog.state.atomic_current_process_proofs,{})

    def test_shared_checkpoint_keeps_engine_independent_capabilities_and_label(self):
        with tempfile.TemporaryDirectory(prefix='catalog-shared-origin-') as folder:
            generated=PrivateCatalogFixture(folder)
            (generated.paths['dense']/'tokenizer.json').write_text('{}')
            runtime={'ready':True,'version':'0.16.9','identity':'generated-rapid-runtime',
                     'modelTypes':['qwen3_5']}
            with generated.patches(), \
                    mock.patch.object(launcher.rapidmlx_runtime,'inspect_runtime',return_value=runtime), \
                    mock.patch.object(launcher.rapidmlx_runtime.platform,'system',return_value='Darwin'), \
                    mock.patch.object(launcher.rapidmlx_runtime.platform,'machine',return_value='arm64'):
                catalog=generated.catalog()
                shared=next(item for item in catalog.scan_models()
                            if item['path']==str(generated.paths['dense']) and 'Generated' in item['origins'])
                with mock.patch.object(launcher.slotstream_runtime,'discover',return_value=None):
                    independent=next(item for item in catalog.scan_models() if item['id']==shared['id'])
                self.assertEqual(shared['name'],'Qwen3.8 Flash-Next · MLX 4-bit')
                self.assertEqual(shared['origins'],['Generated','Alias'])
                self.assertTrue(shared['backends']['rapidmlx']['runnable'])
                self.assertTrue(shared['backends']['mtplx']['runnable'])
                for backend,capability in shared['backends'].items():
                    if backend!='omlx':
                        self.assertEqual(capability,independent['backends'][backend],backend)
                # An engine's own descriptive format/origin must not mask an
                # otherwise identical native checkpoint from Rapid discovery.
                relabelled={**shared,'format':'Slotstream MLX 4-bit + SSD',
                            'origins':['Slotstream cache']}
                cap=launcher.rapidmlx_runtime.capability(relabelled,runtime)
                self.assertTrue(cap['runnable'])
                self.assertEqual(cap['modelIdentity'],shared['backends']['rapidmlx']['modelIdentity'])

    def test_registry_is_copied_frozen_data_and_keeps_binary_status_live(self):
        catalog=make_catalog(launcher)
        self.assertTrue(all(isinstance(item,model_catalog.CatalogDescriptor) for item in catalog.policy.engines.values()))
        with self.assertRaises(TypeError):catalog.policy.engines["unknown"]=None
        with self.assertRaises(FrozenInstanceError):catalog.policy.engines["omlx"].label="changed"
        with mock.patch.dict(launcher.BINARIES,{"omlx":None}):
            self.assertFalse(catalog.model_library_inventory([])["engines"][0]["installed"])
        with mock.patch.dict(launcher.BINARIES,{"omlx":"/generated/new-binary"}):
            self.assertTrue(catalog.model_library_inventory([])["engines"][0]["installed"])

    def test_geometry_facade_is_stateless_and_reads_current_qwen_predicate_and_policy(self):
        config={"num_hidden_layers":2,"num_attention_heads":2,"num_key_value_heads":1,
            "head_dim":8,"hidden_size":16,"indexer_head_dim":16,"indexer_compress_ratio":4}
        with mock.patch.object(launcher,"_model_catalog",side_effect=AssertionError("Pure geometry rebuilt catalog wiring")), \
                mock.patch.object(launcher,"is_qwen4_exp_config",return_value=True) as predicate, \
                mock.patch.object(launcher,"OMLX_QWEN4_QSA_ALLOCATION_STEP_TOKENS",16):
            first=launcher.model_memory_geometry(config)
            self.assertTrue(first["qwen4Qsa"])
            self.assertEqual(first["qsaAllocationStepTokens"],16)
            predicate.assert_called_once_with(config)
        with mock.patch.object(launcher,"_model_catalog",side_effect=AssertionError("Pure geometry rebuilt catalog wiring")), \
                mock.patch.object(launcher,"is_qwen4_exp_config",return_value=True), \
                mock.patch.object(launcher,"OMLX_QWEN4_QSA_ALLOCATION_STEP_TOKENS",2):
            self.assertNotIn("qwen4Qsa",launcher.model_memory_geometry(config))
        with mock.patch.object(launcher,"_model_catalog",side_effect=AssertionError("Pure geometry rebuilt catalog wiring")), \
                mock.patch.object(launcher,"is_qwen4_exp_config",return_value=False), \
                mock.patch.object(launcher,"OMLX_QWEN4_QSA_ALLOCATION_STEP_TOKENS",16):
            self.assertNotIn("qwen4Qsa",launcher.model_memory_geometry(config))

    def test_module_uses_no_controller_namespace_or_launch_process_manager(self):
        tree=ast.parse(Path(model_catalog.__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Name):self.assertNotIn(node.id,{"BINARIES","RunManager","LaunchPlan"})
            if isinstance(node,ast.ImportFrom):self.assertNotEqual(node.module,"launcher")
            if isinstance(node,ast.Import):self.assertNotIn("launcher",{item.name for item in node.names})
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):self.assertNotIn(node.func.id,{"exec","eval","globals","free_port"})

    def test_native_mtplx_probe_reuses_raw_receipt_but_rechecks_every_capability_flag(self):
        with tempfile.TemporaryDirectory(prefix="catalog-native-probe-") as folder:
            generated=PrivateCatalogFixture(folder)
            binary=generated.root/"mtplx"
            binary.write_text("generated native inspector")
            binary.chmod(0o700)
            path=generated.paths["dense"]
            receipt={"model_dir":str(path),"mtp_supported":"yes","unverified_model":False,
                "mtp":{"passes_tensor_gate":True},"compatibility":{"can_run":True}}
            catalog=make_catalog(launcher)
            run=mock.Mock(return_value=SimpleNamespace(returncode=0,stdout=json.dumps(receipt)))
            catalog.io=replace(catalog.io,run_catalog_cli=run)
            for _ in range(2):self.assertTrue(catalog._mtplx_native_mtp_inspection(str(binary),str(path),"fixed-fingerprint",1))
            self.assertEqual(run.call_count,1)
            self.assertTrue(all(isinstance(value,tuple) and isinstance(value[1],str) for value in catalog.state.mtplx_inspection_cache.values()))
            key=next(iter(catalog.state.mtplx_inspection_cache))
            # A reused observation is still validated, not an admission boolean.
            receipt["mtp"]["passes_tensor_gate"]=False
            catalog.state.mtplx_inspection_cache[key]=(0,json.dumps(receipt))
            self.assertFalse(catalog._mtplx_native_mtp_inspection(str(binary),str(path),"fixed-fingerprint",1))
            self.assertEqual(run.call_count,1)

    def test_native_probe_cache_detects_replacement_in_place_and_named_link_changes(self):
        for change in ("replacement","in-place","link","model-header"):
            with self.subTest(change=change),tempfile.TemporaryDirectory(prefix="catalog-probe-replacement-") as folder:
                generated=PrivateCatalogFixture(folder)
                target=generated.root/"runtime"
                target.write_text("first runtime");target.chmod(0o700)
                binary=generated.root/"runtime-link"
                binary.symlink_to(target)
                path=generated.paths["dense"]
                receipt={"model_dir":str(path),"mtp_supported":"yes","unverified_model":False,
                    "mtp":{"passes_tensor_gate":True},"compatibility":{"can_run":True}}
                catalog=make_catalog(launcher)
                run=mock.Mock(return_value=SimpleNamespace(returncode=0,stdout=json.dumps(receipt)))
                catalog.io=replace(catalog.io,run_catalog_cli=run)
                before=target.stat()
                self.assertTrue(catalog._mtplx_native_mtp_inspection(str(binary),str(path),"same-fingerprint",before.st_mtime_ns))
                if change=="replacement":
                    other=target.with_name("replacement");other.write_text("other runtime");other.chmod(0o700)
                    os.utime(other,ns=(before.st_atime_ns,before.st_mtime_ns));other.replace(target)
                elif change=="in-place":
                    target.write_text("other runtime");os.utime(target,ns=(before.st_atime_ns,before.st_mtime_ns))
                elif change=="link":
                    other=target.with_name("other");other.write_text("other runtime");other.chmod(0o700)
                    os.utime(other,ns=(before.st_atime_ns,before.st_mtime_ns));binary.unlink();binary.symlink_to(other)
                else:
                    shard=path/"model.safetensors";details=shard.stat();raw=shard.read_bytes()
                    shard.write_bytes(raw[:-1]+b"x");os.utime(shard,ns=(details.st_atime_ns,details.st_mtime_ns))
                receipt["mtp"]["passes_tensor_gate"]=False
                run.return_value.stdout=json.dumps(receipt)
                self.assertFalse(catalog._mtplx_native_mtp_inspection(str(binary),str(path),"same-fingerprint",before.st_mtime_ns))
                self.assertEqual(run.call_count,2)

    def test_runtime_mutation_during_native_probe_cannot_publish_positive_receipt(self):
        with tempfile.TemporaryDirectory(prefix="catalog-probe-race-") as folder:
            generated=PrivateCatalogFixture(folder)
            binary=generated.root/"runtime";binary.write_text("first runtime");binary.chmod(0o700)
            path=generated.paths["dense"]
            receipt={"model_dir":str(path),"mtp_supported":"yes","unverified_model":False,
                "mtp":{"passes_tensor_gate":True},"compatibility":{"can_run":True}}
            catalog=make_catalog(launcher)
            def changed(*_a,**_k):
                binary.write_text("other runtime")
                return SimpleNamespace(returncode=0,stdout=json.dumps(receipt))
            catalog.io=replace(catalog.io,run_catalog_cli=changed)
            self.assertFalse(catalog._mtplx_native_mtp_inspection(str(binary),str(path),"fixture",1))
            self.assertEqual(catalog.state.mtplx_inspection_cache,{})

    def test_freetoken_raw_receipt_cache_is_identity_bound_and_validation_is_fresh(self):
        # Existing exact capability fixture supplies every required schema,
        # qualification and local-only constraint; no native program is run.
        from tests.test_launcher import native_freetoken_contract
        with tempfile.TemporaryDirectory(prefix="catalog-freetoken-probe-") as folder:
            generated=PrivateCatalogFixture(folder)
            binary=generated.root/"ft";binary.write_text("first runtime");binary.chmod(0o700)
            path=generated.paths["moe"]
            receipt=native_freetoken_contract(path)
            catalog=make_catalog(launcher)
            catalog.runtime=replace(catalog.runtime,selected_binary=lambda _key:str(binary),native_freetoken_host_supported=lambda:True)
            run=mock.Mock(return_value=SimpleNamespace(returncode=0,stdout=json.dumps(receipt)))
            catalog.io=replace(catalog.io,run_catalog_cli=run)
            first=catalog.inspect_native_freetoken_model(path,8192,"fixed-fingerprint")
            first["support"]["tools"]=True
            self.assertFalse(catalog.inspect_native_freetoken_model(path,8192,"fixed-fingerprint")["support"]["tools"])
            self.assertEqual(run.call_count,1)
            self.assertTrue(all(isinstance(item,tuple) and isinstance(item[1],str) for item in catalog.state.native_inspection_cache.values()))
            before=binary.stat();other=binary.with_name("replacement")
            other.write_text("other runtime");other.chmod(0o700)
            os.utime(other,ns=(before.st_atime_ns,before.st_mtime_ns));other.replace(binary)
            catalog.inspect_native_freetoken_model(path,8192,"fixed-fingerprint")
            self.assertEqual(run.call_count,2)
            catalog.inspect_native_freetoken_model(path,8192,"fixed-fingerprint",force=True)
            self.assertEqual(run.call_count,3)
            key=next(reversed(catalog.state.native_inspection_cache))
            bad=copy.deepcopy(receipt);bad["security"]["network_downloads"]=True
            catalog.state.native_inspection_cache[key]=(0,json.dumps(bad))
            with self.assertRaisesRegex(ValueError,"local-only"):
                catalog.inspect_native_freetoken_model(path,8192,"fixed-fingerprint")

    def test_uzu_catalog_receipts_bytes_and_model_records_match_original_without_runtime_calls(self):
        from tests import test_uzu_backend
        owner=test_uzu_backend.launcher
        private=test_uzu_backend.UzuBackendTests("runTest")
        private.setUp()
        try:
            with private.patched_cache_globals():
                private.write_registry();private.write_cache()
                catalog=make_catalog(owner)
                expected=owner._uzu_model_cache_contract()
                self.assertTrue(expected["ready"])
                self.assertEqual(catalog._uzu_model_cache_contract(),expected)
                runtime={"ready":True,"binaryIdentityPinned":True,"nativeBearerAuthentication":True,
                    "oneUseApiKeyFile":True,"nativeContextLimit":True,"nativeOutputLimit":True,
                    "boundedContextReady":True,"nativeBoundaryContractId":owner.UZU_NATIVE_BOUNDARY_CONTRACT_ID}
                with mock.patch.object(owner,"uzu_runtime_contract",return_value=runtime), \
                        mock.patch.object(owner,"uzu_listener_protection_ready",return_value=True), \
                        mock.patch.object(owner,"command_version",return_value="Uzu generated-runtime"), \
                        mock.patch.object(owner,"physical_memory_bytes",return_value=48*1024**3):
                    self.assertEqual(catalog.uzu_model_records([]),owner.uzu_model_records([]))
                    records=catalog.uzu_model_records([])
                    self.assertEqual(records[0]["architectureNativeContext"],262144)
                    self.assertEqual(records[0]["backends"]["uzu"]["contextWindows"],list(launcher.UZU_SAFE_CONTEXT_WINDOWS))
                    self.assertFalse(records[0]["backends"]["uzu"]["customSampling"])
                target=private.model_path/"model.safetensors"
                details=target.stat();before=target.read_bytes()
                target.write_bytes(b"x"+before[1:]);os.utime(target,ns=(details.st_atime_ns,details.st_mtime_ns))
                self.assertFalse(catalog._uzu_model_cache_contract()["ready"])
        finally:
            private.tearDown();private.doCleanups()

    def test_atomic_current_process_proof_and_snapshot_never_inherit_authority(self):
        with tempfile.TemporaryDirectory(prefix="catalog-atomic-proof-") as folder:
            root=Path(folder).resolve()
            target=root/launcher.LLAMACPP_ATOMIC_VARIANT
            target.mkdir()
            payload=b"GGUF"+b"x"*128
            checksum=hashlib.sha256(payload).hexdigest()
            files=[]
            for index in range(1,launcher.LLAMACPP_ATOMIC_SHARDS+1):
                relative=launcher.llamacpp_atomic_shard_relative(index)
                (target/Path(relative).name).write_bytes(payload)
                files.append({"path":relative,"size":len(payload),"sha256":checksum})
            total=len(payload)*launcher.LLAMACPP_ATOMIC_SHARDS
            marker={"schemaVersion":launcher.MODEL_ACQUISITION_SCHEMA_VERSION,
                "repoId":launcher.LLAMACPP_ATOMIC_REPO,"pinnedRevision":launcher.LLAMACPP_ATOMIC_REVISION,
                "variantId":launcher.LLAMACPP_ATOMIC_VARIANT_ID,"format":"gguf","files":files,"status":"verified",
                "verification":{"verified":True,"format":"gguf","checkedFiles":len(files),"weightBytes":total}}
            (root/launcher.MODEL_ACQUISITION_MARKER).write_text(json.dumps(marker))
            manifest=tuple((row["path"],row["size"],row["sha256"]) for row in files)
            with mock.patch.object(launcher,"LLAMACPP_ATOMIC_FILE_MANIFEST",manifest), \
                    mock.patch.object(launcher,"LLAMACPP_ATOMIC_TOTAL_BYTES",total), \
                    mock.patch.object(launcher,"STATE_DIR",root/"state"):
                catalog=make_catalog(launcher)
                structural=catalog._llamacpp_atomic_structural_contract(target)
                self.assertTrue(structural["_structurallyReady"])
                self.assertIsNone(catalog._atomic_current_process_contract(structural))
                self.assertTrue(catalog._write_atomic_presentation_snapshot(structural))
                self.assertTrue(catalog._load_atomic_presentation_snapshot(structural))
                self.assertIsNone(catalog._atomic_current_process_contract(structural),"Saved presentation cannot confer process proof")
                hash_call=catalog.artifacts.cached_regular_file_sha256_matches
                hashed=mock.Mock(side_effect=hash_call)
                catalog.artifacts=replace(catalog.artifacts,cached_regular_file_sha256_matches=hashed)
                proof=catalog.llamacpp_atomic_artifact_contract(target)
                self.assertTrue(proof["currentProcessVerified"])
                self.assertEqual(proof["verificationGeneration"],1)
                self.assertEqual(hashed.call_count,len(files))
                self.assertTrue(catalog.llamacpp_atomic_artifact_contract(target)["ready"])
                self.assertEqual(hashed.call_count,len(files))
                changed=target/Path(files[0]["path"]).name
                changed.write_bytes(b"GGUF"+b"y"*128)
                self.assertFalse(catalog.llamacpp_atomic_artifact_contract(target)["ready"])
                self.assertNotIn(str(target),catalog.state.atomic_current_process_proofs)

    def test_mference_actual_bundle_and_changed_payload_match_current_contract(self):
        from tests.test_launcher import LauncherTests
        with tempfile.TemporaryDirectory(prefix="catalog-mference-") as folder:
            # Existing independent generator writes only the given temp tree.
            generated=SimpleNamespace(temp=SimpleNamespace(name=folder))
            path=LauncherTests.write_mference_bundle(generated)
            catalog=make_catalog(launcher)
            expected=launcher.mference_bundle_validation(path)
            self.assertTrue(expected[0])
            self.assertEqual(catalog.mference_bundle_validation(path),expected)
            self.assertEqual(catalog.weight_completeness(path,{}),launcher.weight_completeness(path,{}))
            manifest=json.loads((path/"manifest.json").read_text())
            profile=catalog.ssd_streaming_model_profile(path,manifest,100*1024**3,48*1024**3)
            self.assertTrue(profile["candidate"])
            self.assertTrue(profile["recommended"])
            self.assertTrue(profile["crossFormatComparisonReady"])
            self.assertEqual(profile,launcher.ssd_streaming_model_profile(path,manifest,100*1024**3,48*1024**3))
            (path/"model_weights.bin").write_bytes(b"changed-size")
            self.assertFalse(catalog.mference_bundle_validation(path)[0])
            self.assertEqual(catalog.mference_bundle_validation(path),launcher.mference_bundle_validation(path))

    def test_complete_dflash_header_structure_pairing_and_malformed_shapes_are_exact(self):
        fixture=json.loads(FIXTURE.read_text())
        config=next(case["args"][0] for case in fixture["cases"] if case["method"]=="dflash2_draft_shape" and case["expected"] is not None)
        with tempfile.TemporaryDirectory(prefix="catalog-draft-") as folder:
            path=Path(folder).resolve()
            (path/"config.json").write_text(json.dumps(config))
            shapes=launcher.dflash2_expected_tensor_shapes(config)
            shapes.update({"candidate_selector.predecessor_codebook.weight":[config["vocab_size"],config["dflash_config"]["selector_rank"]],
                "candidate_selector.successor_codebook.weight":[config["vocab_size"],config["dflash_config"]["selector_rank"]]})
            write_header(path/"model.safetensors",shapes)
            catalog=make_catalog(launcher)
            self.assertTrue(launcher.dflash2_draft_complete(path,config))
            self.assertTrue(catalog.dflash2_draft_complete(path,config))
            self.assertEqual(catalog.model_artifact_fingerprint(path,config),launcher.model_artifact_fingerprint(path,config))
            self.assertEqual(catalog.dflash2_pair_fingerprint(path,config,path,config),launcher.dflash2_pair_fingerprint(path,config,path,config))
            shape_name=next(iter(shapes))
            shapes[shape_name]=[1]
            write_header(path/"model.safetensors",shapes)
            self.assertFalse(catalog.dflash2_draft_complete(path,config))
            self.assertEqual(catalog.dflash2_draft_complete(path,config),launcher.dflash2_draft_complete(path,config))

    def test_background_atomic_worker_cannot_publish_after_its_job_epoch_changes(self):
        catalog=make_catalog(launcher)
        pending=[]
        class DeferredThread:
            def __init__(self,*,target,**_kwargs):self.target=target;pending.append(self)
            def start(self):pass
            def is_alive(self):return True
        structural={"_root":"/generated/private-atomic","_identityKey":"first-filesystem-identity"}
        catalog.io=replace(catalog.io,token_hex=lambda _count:"first-job")
        with mock.patch.object(model_catalog.threading,"Thread",DeferredThread), \
                mock.patch.object(catalog,"llamacpp_atomic_artifact_contract",return_value={"ready":True}), \
                mock.patch.object(catalog,"_llamacpp_atomic_structural_contract",return_value=structural), \
                mock.patch.object(catalog,"_atomic_current_process_contract",return_value={"ready":True}), \
                mock.patch.object(catalog,"_write_atomic_presentation_snapshot",return_value=True):
            catalog._start_atomic_background_verification(structural)
            catalog.state.atomic_verification_states[structural["_root"]]={"jobId":"replacement-job","phase":"checking","identityKey":"second-filesystem-identity"}
            pending[0].target()
        self.assertEqual(catalog.state.atomic_verification_states[structural["_root"]],
            {"jobId":"replacement-job","phase":"checking","identityKey":"second-filesystem-identity"})

    def test_atomic_verifier_start_failure_is_readable_fail_closed_and_retryable(self):
        for failure in ("constructor","start"):
            with self.subTest(failure=failure):
                catalog=make_catalog(launcher)
                structural={"_root":"/generated/private-atomic","_identityKey":"exact-current-files",
                    "_structurallyReady":True,"ready":False}
                attempts=[]
                class ControlledThread:
                    def __init__(self,*,target,**_kwargs):
                        attempts.append(self)
                        self.target=target;self.alive=False
                        if failure=="constructor" and len(attempts)==1:
                            raise RuntimeError("generated constructor failure " + "x"*1000)
                    def start(self):
                        if failure=="start" and len(attempts)==1:
                            raise RuntimeError("generated start failure " + "x"*1000)
                        self.alive=True
                    def is_alive(self):return self.alive
                catalog.io=replace(catalog.io,token_hex=mock.Mock(side_effect=["failed-job","retry-job"]))
                with mock.patch.object(model_catalog.threading,"Thread",ControlledThread), \
                        mock.patch.object(catalog,"_llamacpp_atomic_structural_contract",return_value=structural), \
                        mock.patch.object(catalog,"_atomic_current_process_contract",return_value=None) as proof, \
                        mock.patch.object(catalog,"_load_atomic_presentation_snapshot",return_value=True), \
                        mock.patch.object(catalog,"llamacpp_atomic_artifact_contract",return_value={"ready":True}) as verify, \
                        mock.patch.object(catalog,"_write_atomic_presentation_snapshot",return_value=True) as snapshot:
                    failed=catalog.llamacpp_atomic_scan_contract(Path(structural["_root"]))
                    self.assertFalse(failed["ready"])
                    self.assertFalse(failed["currentProcessVerified"])
                    self.assertEqual(failed["verificationState"],"failed")
                    self.assertIn("could not start",failed["reason"])
                    self.assertLessEqual(len(failed["reason"]),500)
                    self.assertEqual(failed["verifiedShards"],0)
                    self.assertNotIn(structural["_root"],catalog.state.atomic_verification_threads)
                    state=catalog._atomic_verification_status(structural["_root"])
                    self.assertTrue(state["retryable"])
                    self.assertFalse(state["snapshotSaved"])
                    self.assertEqual(state["jobId"],"failed-job")
                    self.assertEqual(state["identityKey"],structural["_identityKey"])
                    self.assertEqual(catalog.state.atomic_current_process_proofs,{})
                    verify.assert_not_called();snapshot.assert_not_called()
                    retry=catalog.llamacpp_atomic_scan_contract(Path(structural["_root"]))
                    self.assertFalse(retry["ready"])
                    self.assertEqual(retry["verificationState"],"checking")
                    self.assertIs(catalog.state.atomic_verification_threads[structural["_root"]],attempts[-1])
                    self.assertEqual(catalog._atomic_verification_status(structural["_root"])["jobId"],"retry-job")
                    proof.return_value={"ready":True}
                    attempts[-1].target()
                    self.assertEqual(catalog._atomic_verification_status(structural["_root"])["phase"],"verified")
                    verify.assert_called_once();snapshot.assert_called_once()

    def test_atomic_start_failure_cannot_clear_a_superseding_job_or_thread(self):
        catalog=make_catalog(launcher)
        path="/generated/private-atomic"
        structural={"_root":path,"_identityKey":"first-filesystem-identity"}
        replacement=SimpleNamespace(is_alive=lambda:True)
        replacement_state={"jobId":"replacement-job","phase":"checking","identityKey":"new-filesystem-identity"}
        class SupersededThread:
            def __init__(self,**_kwargs):pass
            def is_alive(self):return False
            def start(self):
                catalog.state.atomic_verification_states[path]=copy.deepcopy(replacement_state)
                catalog.state.atomic_verification_threads[path]=replacement
                raise RuntimeError("generated failure from superseded start")
        with mock.patch.object(model_catalog.threading,"Thread",SupersededThread):
            state=catalog._start_atomic_background_verification(structural)
        self.assertEqual(state,replacement_state)
        self.assertIs(catalog.state.atomic_verification_threads[path],replacement)
        self.assertEqual(catalog.state.atomic_current_process_proofs,{})


if __name__=="__main__":unittest.main()
