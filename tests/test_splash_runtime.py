"""Unit coverage for the Splash runtime module (no engine launch)."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import tempfile
import types
import unittest
from unittest import mock

import splash_runtime
import launcher
import session_proxy


def write_pack(root: pathlib.Path, *, model: str = "Qwen3.8-27B", owner: str = "incoai", repo: str = "Qwen3.8-27B-Splash") -> pathlib.Path:
    pack = root / owner / repo
    for name in ("target", "draft", "tokenizer", "vision"):
        (pack / name).mkdir(parents=True, exist_ok=True)
    (pack / "target" / "layer-0.bin").write_bytes(b"t" * 32)
    (pack / "draft" / "model.bin").write_bytes(b"d" * 16)
    (pack / "vision" / "model.bin").write_bytes(b"v" * 8)
    (pack / "tokenizer" / "tokenizer.json").write_bytes(b"null")
    (pack / "manifest.json").write_text(json.dumps({
        "artifact_set_sha256": "a" * 64,
        "model": model,
        "execution_geometry": {"prefill_token_budget": 2048, "maximum_batch_width": 4},
        "artifacts": [
            {"path": "target/layer-0.bin", "size": 32, "sha256": "b" * 64},
            {"path": "draft/model.bin", "size": 16, "sha256": "c" * 64},
            {"path": "vision/model.bin", "size": 8, "sha256": "d" * 64},
            {"path": "tokenizer/tokenizer.json", "size": 4, "sha256": "e" * 64},
        ],
    }), encoding="utf-8")
    return pack


def write_install(root: pathlib.Path) -> pathlib.Path:
    libexec = root / "libexec"
    (libexec / "engine").mkdir(parents=True)
    (libexec / "server").mkdir()
    (libexec / "python" / "bin").mkdir(parents=True)
    (libexec / "engine" / "splash").write_bytes(b"engine-binary")
    (libexec / "engine" / "splash.metallib").write_bytes(b"metallib")
    (libexec / "server" / "server.py").write_text("# server\n", encoding="utf-8")
    (libexec / "python" / "bin" / "python3").write_text("#!/bin/sh\n", encoding="utf-8")
    (libexec / "python" / "bin" / "python3").chmod(0o700)
    (libexec / "engine" / "splash").chmod(0o700)
    (libexec / "release.json").write_text(json.dumps({
        "version": "1.0",
        "binary_sha256": hashlib.sha256(b"engine-binary").hexdigest(),
        "metallib_sha256": hashlib.sha256(b"metallib").hexdigest(),
    }), encoding="utf-8")
    return libexec


class SplashRuntimeTests(unittest.TestCase):
    def test_14_mlx_candidates_include_installed_27b_six_bit_and_new_quantization_metadata(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw).resolve()
            checkpoints = [root / "Qwen3.8-27B-MLX-6bit", root / "Qwen3.8-27B-nvfp4"]
            configurations = [{"quantization": {"bits": 6, "group_size": 64}},
                              {"quantization_config": {"quant_method": "nvfp4"}}]
            for path, config in zip(checkpoints, configurations):
                path.mkdir()
                (path / "config.json").write_text(json.dumps(config))
            self.assertEqual(splash_runtime.source_candidates(checkpoints, install={"version": "1.4.0"}),
                             [str(path) for path in checkpoints])
            self.assertEqual(splash_runtime.source_candidates(checkpoints, install={"version": "1.2.1"}), [])

    def test_split_candidates_keep_snapshot_leaf_and_only_first_shard(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw).resolve()
            snapshot = root / "snapshots" / "revision"
            snapshot.mkdir(parents=True)
            blobs = root / "blobs"
            blobs.mkdir()
            for part in (1, 2):
                (blobs / str(part)).write_bytes(b"GGUF")
                (snapshot / f"Flash-Q4_K_M-{part:05}-of-00002.gguf").symlink_to(blobs / str(part))
            first = snapshot / "Flash-Q4_K_M-00001-of-00002.gguf"
            self.assertEqual(splash_runtime.source_candidates([snapshot]), [str(first)])
            self.assertEqual(splash_runtime.source_candidates([first]), [str(first)])

    def test_14_server_uses_native_budget_and_prepared_model_without_tokenizer(self):
        install = {'version': '1.4.0', 'python': '/runtime/python', 'server': '/runtime/server/server.py',
                   'engineBinary': '/runtime/engine/splash', 'libexec': '/runtime'}
        source = {'kind': 'source', 'id': 'local/Flash-Q4', 'path': '/models/source.gguf'}
        argv = splash_runtime.planning_arguments(install, source, 131072, port=18791,
                                                max_memory='30000000000', model_root='/prepared/model')
        self.assertIn('/prepared/model', argv)
        self.assertNotIn('--tokenizer', argv)
        self.assertFalse(any('splash_reasoning.py' in item for item in argv))
        self.assertEqual(argv[argv.index('--thinking-token-budget') + 1], '4096')
        self.assertEqual(argv[argv.index('--max-memory') + 1], '30000000000')
        self.assertEqual(argv[argv.index('--port') + 1], '18791')
        with self.assertRaisesRegex(ValueError, 'original GGUF or MLX'):
            splash_runtime.planning_arguments(install, {**source, 'kind': 'pack'}, 131072, port=18791)

    def test_14_hides_unsupported_legacy_packs_and_verifies_current_hashes(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            libexec = write_install(root)
            release = json.loads((libexec / 'release.json').read_text())
            release['version'] = '1.4.0'
            (libexec / 'release.json').write_text(json.dumps(release))
            with mock.patch.object(splash_runtime, 'discover_packs') as discover:
                install = splash_runtime.inspect_install(libexec=libexec)
            self.assertTrue(install['ready'])
            self.assertEqual(install['packs'], [])
            discover.assert_not_called()
            self.assertIsNone(splash_runtime.inspect_model(install, {'kind': 'pack', 'path': '/old'}))
            (libexec / 'engine/splash.metallib').write_bytes(b'changed')
            self.assertFalse(splash_runtime.inspect_install(libexec=libexec)['ready'])

    def test_runtime_version_uses_verified_release_without_unsupported_cli_probe(self):
        with tempfile.TemporaryDirectory() as raw:
            libexec = write_install(pathlib.Path(raw))
            with mock.patch.object(launcher.subprocess, 'run') as run:
                self.assertEqual(launcher.command_version(str(libexec / 'engine/splash')), 'Splash 1.0')
                run.assert_not_called()
            (libexec / 'engine/splash').write_bytes(b'changed')
            self.assertEqual(launcher.command_version(str(libexec / 'engine/splash')),
                             'Installed (unverified Splash release)')

    def test_flash_record_admits_ssd_budget_and_keeps_family_and_variant(self):
        source = {'kind': 'source', 'id': 'local/Flash-Q4_K_M', 'name': 'Flash-Q4_K_M',
                  'path': '/model/first.gguf', 'format': 'gguf', 'quantization': 'Q4_K',
                  'identity': 'a' * 64, 'targetBytes': 119_599_030_080,
                  'family': 'Qwen3.8-Flash-Next', 'hiddenSize': 4096, 'expertCount': 512,
                  'plePrecision': 'BF16',
                  'layers': 48, 'kvHeads': 2, 'headDim': 256, 'nativeContext': 262144}
        with mock.patch.object(splash_runtime, 'host_support', return_value=(True, '')):
            record = splash_runtime.model_record({'ready': True, 'version': '1.4.0'}, source,
                                                [('splash', 'Splash')], 48 * 1024**3)
        self.assertTrue(record['backends']['splash']['runnable'])
        self.assertEqual(record['modelType'], 'splash-qwen38-flash-next')
        self.assertEqual(record['name'], 'Flash-Q4_K_M · Splash')
        self.assertEqual(record['quantization'], 'Q4_K · BF16 PLE')
        estimate = splash_runtime.memory_estimate(record['splash'], 131072)
        self.assertTrue(estimate['ssdStreaming'])
        self.assertEqual(estimate['ssdWeightBytes'], record['size'])
        self.assertLess(estimate['estimatedWorkingSetBytes'], record['size'])

    def test_source_candidates_keep_each_quant_and_skip_mlx_q6_projectors_and_aliases(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw).resolve()
            ggufs = root / 'ggufs'
            ggufs.mkdir()
            for name in ('Q4_K_M', 'Q6_K', 'Q8_0', 'mmproj-Q8_0'):
                (ggufs / (name + '.gguf')).write_bytes(b'GGUF')
            alias = root / 'alias'
            alias.symlink_to(ggufs, target_is_directory=True)
            for bits in (4, 6):
                model = root / f'mlx-{bits}'
                model.mkdir()
                (model / 'config.json').write_text(json.dumps({'quantization':{'bits':bits,'group_size':64}}))
            candidates = splash_runtime.source_candidates([ggufs, alias, root/'mlx-4', root/'mlx-6'])
            self.assertCountEqual(candidates, [str(ggufs/f'{q}.gguf') for q in ('Q4_K_M', 'Q6_K', 'Q8_0')] + [str(root/'mlx-4')])

    def test_source_inspection_excludes_rejected_headers_and_old_runtimes(self):
        install = {'ready':True, 'version':'1.2.1', 'python':'python3', 'libexec':'/tmp/splash'}
        result = types.SimpleNamespace(returncode=0, stdout=json.dumps([
            {'path':'q6.gguf','source':{'kind':'source','quantization':'Q6_K'}},
            {'path':'other.gguf','error':'no supported model has this architecture'},
        ]))
        with mock.patch.object(splash_runtime.subprocess, 'run', return_value=result) as run:
            self.assertEqual(len(splash_runtime.inspect_sources(install, ['q6.gguf','other.gguf'])), 1)
            run.assert_called_once()
            run.reset_mock()
            self.assertEqual(splash_runtime.inspect_sources({**install,'version':'1.0'}, ['q6.gguf']), [])
            run.assert_not_called()

    def test_modern_model_directory_cli_omits_removed_output_option(self):
        with tempfile.TemporaryDirectory() as raw:
            install = splash_runtime.inspect_install(libexec=write_install(pathlib.Path(raw)))
            source = {'kind':'source','id':'local/Qwen-Q6','path':'/models/target.gguf'}
            with self.assertRaisesRegex(ValueError, 'Update Splash'):
                splash_runtime.planning_arguments(install, source, 131072, port=8011)
            argv = splash_runtime.planning_arguments({**install,'version':'1.2.1'}, source,
                                                     131072, port=8011, model_root='/models/assembly')
            self.assertEqual(argv[4], '/models/assembly')
            self.assertEqual(argv[5], '--tokenizer')
            self.assertNotIn('--max-new-tokens', argv)
            self.assertEqual(argv[argv.index('--model')+1], 'local/Qwen-Q6')

    def test_native_moe_record_keeps_q6_and_uses_its_kv_geometry(self):
        source = {'kind':'source','id':'local/Qwen-Q6','name':'Qwen3.8-35B-A3B-Q6_K',
                  'identity':'a'*64,'path':'/models/q6.gguf','format':'gguf','quantization':'Q6_K',
                  'targetBytes':29_208_731_296,'family':'Qwen3.6-35B-A3B','hiddenSize':2048,
                  'layers':40,'kvHeads':2,'headDim':256,'nativeContext':262144}
        with mock.patch.object(splash_runtime, 'host_support', return_value=(True,'')):
            record = splash_runtime.model_record({'version':'1.2.1','ready':True}, source,
                                                 [('splash','Splash'),('lmstudio','LM Studio')],48*1024**3)
        self.assertTrue(record['backends']['splash']['runnable'])
        self.assertFalse(record['backends']['lmstudio']['runnable'])
        self.assertEqual(record['quantization'], 'Q6_K')
        estimate = splash_runtime.memory_estimate(record['splash'], 131072)
        self.assertEqual(estimate['kvCacheBytes'],131072*10*2*256*2*65//64)
        self.assertIn('frequency_penalty',record['backends']['splash']['samplingFields'])

    def test_relay_keeps_modern_unrestricted_top_k_and_legacy_minimum(self):
        body = json.dumps({'model':'local/Qwen-Q6','messages':[{'role':'user','content':'hi'}]})
        contract = launcher.build_sampling_contract('custom', custom={'temperature':0.7,'top_k':0})
        for modern in (False, True):
            fields = ['temperature','top_p','top_k','seed']
            if modern:
                fields += ['presence_penalty','frequency_penalty','repetition_penalty']
            config = {'backend':'splash','servedModel':'local/Qwen-Q6','reasoning':'off','outputLimit':1024,
                      'samplingContract':contract.as_dict(),
                      'samplingEnforcement':{'protocol':'chat-completions',
                          'representableFields':fields,'implicitModelDefaults':False}}
            rewritten = json.loads(session_proxy.transform_chat_request(body.encode(),config))
            self.assertEqual(rewritten['top_k'],0 if modern else 1)

    def test_catalog_keeps_distinct_packs_with_the_same_model_name(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            install = splash_runtime.inspect_install(libexec=write_install(root))
            packs = [splash_runtime.inspect_pack(write_pack(root / "models", owner=owner))
                     for owner in ("one", "two")]
            records = [splash_runtime.model_record(install, pack, [("splash", "Splash")], 48 * 1024**3)
                       for pack in packs]
            self.assertEqual(len({record["id"]: record for record in records}), 2)

    def test_pack_rejects_missing_wrong_size_and_escaping_artifacts(self):
        with tempfile.TemporaryDirectory() as raw:
            root = write_pack(pathlib.Path(raw))
            artifact = root / "target/layer-0.bin"
            artifact.write_bytes(b"short")
            self.assertIsNone(splash_runtime.inspect_pack(root))
            artifact.unlink()
            self.assertIsNone(splash_runtime.inspect_pack(root))
            outside = pathlib.Path(raw) / "outside"
            outside.write_bytes(b"t" * 32)
            artifact.symlink_to(outside)
            self.assertIsNone(splash_runtime.inspect_pack(root))

    def test_inspect_pack_reads_geometry_and_weight_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            pack = write_pack(pathlib.Path(raw))
            description = splash_runtime.inspect_pack(pack)
            self.assertIsNotNone(description)
            assert description is not None
            self.assertEqual(description["id"], "incoai/Qwen3.8-27B-Splash")
            self.assertEqual(description["weightBytes"], 56)
            self.assertEqual(description["geometry"]["maximum_batch_width"], 4)

    def test_inspect_pack_fails_closed_on_incomplete_tree(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            pack = write_pack(pathlib.Path(raw))
            (pack / "draft" / "model.bin").unlink()
            (pack / "draft").rmdir()
            self.assertIsNone(splash_runtime.inspect_pack(pack))

    def test_discover_packs_only_accepts_owner_repo_layout(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            models = pathlib.Path(raw)
            write_pack(models)
            write_pack(models, owner="owner", repo="pack")
            (models / "loose-pack").mkdir()
            self.assertEqual(
                [pack["id"] for pack in splash_runtime.discover_packs(models)],
                ["incoai/Qwen3.8-27B-Splash", "owner/pack"],
            )

    def test_inspect_install_verifies_release_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            libexec = write_install(pathlib.Path(raw))
            install = splash_runtime.inspect_install(libexec=str(libexec))
            self.assertIsNotNone(install)
            assert install is not None
            self.assertTrue(install["ready"])
            self.assertEqual(install["runtimeVersion"], "Splash 1.0")
            (libexec / "engine" / "splash").write_bytes(b"tampered")
            tampered = splash_runtime.inspect_install(libexec=str(libexec))
            assert tampered is not None
            self.assertFalse(tampered["ready"])

    def test_m5_pro_patch_requires_the_pinned_binary_and_library(self):
        with tempfile.TemporaryDirectory() as raw:
            libexec = write_install(pathlib.Path(raw))
            manifest = libexec / "release.json"
            record = json.loads(manifest.read_text())
            record.update(version="1.6.0", launcher_patch=splash_runtime.M5_PRO_DECODE_PATCH)
            manifest.write_text(json.dumps(record))
            with mock.patch.multiple(
                splash_runtime,
                M5_PRO_DECODE_ENGINE_SHA256=record["binary_sha256"],
                M5_PRO_DECODE_METALLIB_SHA256=record["metallib_sha256"],
            ):
                self.assertTrue(splash_runtime.inspect_install(libexec=libexec)["ready"])
                binary = libexec / "engine/splash"
                binary.write_bytes(b"changed-engine")
                record["binary_sha256"] = splash_runtime.digest(binary)
                manifest.write_text(json.dumps(record))
                self.assertFalse(splash_runtime.inspect_install(libexec=libexec)["ready"])

    def test_planning_arguments_pin_the_server_contract(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            libexec = write_install(root)
            pack_path = write_pack(root / "models")
            install = splash_runtime.inspect_install(libexec=str(libexec))
            pack = splash_runtime.inspect_pack(pack_path)
            assert install is not None and pack is not None
            argv = splash_runtime.planning_arguments(install, pack, 131072, port=8011)
            self.assertEqual(argv[0], str(libexec / "python" / "bin" / "python3"))
            self.assertEqual(pathlib.Path(argv[2]).name, "splash_reasoning.py")
            self.assertEqual(argv[3], str(libexec / "server" / "server.py"))
            self.assertEqual(argv[4], str(pack_path / "target"))
            self.assertEqual(argv[5], str(pack_path / "draft"))
            self.assertIn("--tokenizer", argv)
            self.assertEqual(argv[argv.index("--model") + 1], "incoai/Qwen3.8-27B-Splash")
            self.assertEqual(argv[argv.index("--max-context") + 1], "131072")
            self.assertEqual(argv[argv.index("--port") + 1], "8011")
            self.assertIn("--no-webui", argv)
            with self.assertRaises(ValueError):
                splash_runtime.planning_arguments(install, pack, 131072, port=8011, served_id="not-a-repo")

    def test_clean_environment_strips_foreign_knobs_but_keeps_api_key(self) -> None:
        cleaned = splash_runtime.clean_environment({
            "PATH": "/usr/bin", "SPLASH_API_KEY": "local", "SPLASH_FOO": "1",
            "MLX_METAL_DEBUG": "1", "MTPLX_COMPILED_VERIFY_MAX_CONTEXT": "32768",
            "SLOTSTREAM_OPT_WORKSPACE_TILE": "4096",
        })
        self.assertEqual(cleaned, {"PATH": "/usr/bin", "SPLASH_API_KEY": "local"})

    def test_dspine_is_an_explicit_local_splash_option(self):
        install = {
            "version": "1.6.0", "ready": True, "release": {"launcherPatch": splash_runtime.DSPINE_PATCH},
            "python": "/runtime/python", "server": "/runtime/server/server.py",
            "engineBinary": "/runtime/engine/splash", "libexec": "/runtime",
        }
        source = {"kind": "source", "id": "local/qwen27b", "path": "/models/27b"}
        options = {"acceleration": "dspine"}
        parsed = launcher.validated_profile_options("splash", {}, {"dspine": True}, options)
        self.assertEqual(parsed, {"acceleration": "dspine", "depth": 1, "kv": "off"})
        with self.assertRaisesRegex(ValueError, "Qwen3.8-27B"):
            launcher.validated_profile_options("splash", {}, {}, options)
        request = {"backend": "splash", "options": options}
        model = {"nativeContext": 262_144}
        self.assertEqual(launcher.validated_limits(model, request), (262_144, 4096))
        self.assertEqual(launcher.validated_limits({}, {**request, "context": 2048, "output": 512}), (2048, 512))
        with self.assertRaisesRegex(ValueError, "fixed context windows up to 256K"):
            launcher.validated_limits(model, {**request, "context": 262_145})
        splash_runtime.doctor(install, 262_144, options)
        argv = splash_runtime.planning_arguments(install, source, 262_144, port=18091, output=4096, **options)
        self.assertEqual(argv[argv.index("--queue-size") + 1], "1")
        self.assertEqual(argv[argv.index("--thinking-token-budget") + 1], "2048")
        self.assertIn("--disable-ane", argv)
        estimate = splash_runtime.memory_estimate(
            {"weightBytes": 16 * 1024**3, "targetBytes": 14 * 1024**3}, 262_144, **options)
        self.assertEqual(estimate["parallelLanes"], 1)
        self.assertEqual(estimate["modelBytes"], 14 * 1024**3)
        self.assertEqual(estimate["runtimeReserveBytes"], 2 * 1024**3)
        self.assertEqual(estimate["companionBytes"], splash_runtime.DSPINE_COMPACT_MEMORY_BYTES)

    def test_memory_estimate_counts_pack_weights_and_context_kv(self) -> None:
        pack = {"weightBytes": 16 * 1024**3}
        estimate = splash_runtime.memory_estimate(pack, 131072)
        self.assertEqual(estimate["modelBytes"], 16 * 1024**3)
        self.assertEqual(estimate["kvCacheBytes"], 131072 * splash_runtime.KV_BYTES_PER_TOKEN)
        self.assertGreater(estimate["estimatedWorkingSetBytes"], 16 * 1024**3)
        self.assertTrue(estimate["geometry"]["splash"])

    def test_model_record_exposes_a_runnable_splash_backend(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            libexec = write_install(pathlib.Path(raw))
            pack = splash_runtime.inspect_pack(write_pack(pathlib.Path(raw) / "models"))
            install = splash_runtime.inspect_install(libexec=str(libexec))
            assert pack is not None and install is not None
            record = splash_runtime.model_record(
                install, pack, [("splash", "Splash"), ("omlx", "oMLX")], 48 * 1024**3,
            )
            capability = record["backends"]["splash"]
            self.assertTrue(record["id"].startswith("splash-incoai-qwen3-8-27b-splash-"))
            self.assertEqual(capability["kvChoices"], ["off"])
            self.assertEqual(capability["contextWindows"], list(splash_runtime.CONTEXTS))
            self.assertFalse(record["backends"]["omlx"]["runnable"])
            self.assertEqual(record["splash"]["id"], "incoai/Qwen3.8-27B-Splash")

    def test_doctor_rejects_an_unsupported_context(self) -> None:
        install = {"ready": True, "packs": [], "engineBinary": "/tmp/splash"}
        with self.assertRaises(ValueError):
            splash_runtime.doctor(install, 100_000)
        plan = splash_runtime.doctor(install, 131_072)
        self.assertEqual(plan["context"], 131_072)

    def test_validate_served_catalog_checks_the_model_id(self) -> None:
        splash_runtime.validate_served_catalog(
            {"data": [{"id": "incoai/Qwen3.8-27B-Splash"}]}, "incoai/Qwen3.8-27B-Splash",
        )
        with self.assertRaises(ValueError):
            splash_runtime.validate_served_catalog(
                {"data": [{"id": "other/model"}]}, "incoai/Qwen3.8-27B-Splash",
            )


class SplashLaunchPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        self.libexec = write_install(self.root)
        self.pack_path = write_pack(self.root / "models")
        self.pack = splash_runtime.inspect_pack(self.pack_path)
        self.install = splash_runtime.inspect_install(libexec=str(self.libexec))
        assert self.pack is not None and self.install is not None
        self.record = splash_runtime.model_record(
            self.install, self.pack, [("splash", "Splash")], 48 * 1024**3,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def plan(self) -> launcher.LaunchPlan:
        run_dir = self.root / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        return launcher.LaunchPlan(
            run_id="splash-fixture",
            backend="splash",
            client="chat",
            model=json.loads(json.dumps(self.record)),
            project=str(self.root),
            context=131_072,
            output=1_024,
            reasoning="medium",
            port=18_081,
            mode="custom",
            options={},
            purpose="benchmark",
            run_dir=run_dir,
        )

    def test_build_splash_plans_the_verified_wrapper(self) -> None:
        plan = self.plan()
        with mock.patch.dict(launcher.BINARIES, {"splash": str(self.libexec / "engine" / "splash")}):
            launcher.build_splash(plan, plan.model["backends"]["splash"])
        self.assertEqual(plan.engine_argv[0], sys.executable)
        self.assertTrue(plan.engine_argv[-2].endswith("splash_runtime.py"))
        config_path = pathlib.Path(plan.engine_argv[-1])
        self.assertTrue(config_path.is_file())
        config = json.loads(config_path.read_text())
        self.assertEqual(config["context"], 131_072)
        self.assertEqual(config["output"], plan.output)
        self.assertEqual(config["port"], 18_081)
        self.assertEqual(config["servedId"], "incoai/Qwen3.8-27B-Splash")
        self.assertEqual(plan.model["servedId"], "incoai/Qwen3.8-27B-Splash")
        self.assertEqual(plan.engine_env, {"SPLASH_API_KEY": plan.secrets["apiKey"]})
        self.assertTrue(plan.secrets.get("apiKey"))
        self.assertNotIn(plan.secrets["apiKey"], json.dumps(plan.public()))

    def test_large_output_survives_catalog_plan_pi_and_relay(self) -> None:
        for output in (65_536, 131_072):
            with self.subTest(output=output):
                plan = self.plan()
                plan.context, plan.output = launcher.validated_limits(
                    self.record, {"context": 262_144, "output": output},
                )
                plan.client, plan.reasoning = "pi", "xhigh"
                with mock.patch.dict(launcher.BINARIES, {
                    "splash": str(self.libexec / "engine" / "splash"), "pi": "pi",
                }):
                    launcher.build_splash(plan, plan.model["backends"]["splash"])
                    launcher.build_pi_client(plan, launcher.ClientRoute(
                        "fixture", plan.model["servedId"], "http://127.0.0.1:18081/v1", "fixture",
                    ))
                config_path = pathlib.Path(plan.engine_argv[-1])
                # Exercise the final exec wrapper, not just its plan.
                with mock.patch.dict(splash_runtime.os.environ, plan.engine_env), \
                        mock.patch.object(splash_runtime, "inspect_install", return_value=self.install), \
                        mock.patch.object(splash_runtime.os, "execve") as execute:
                    splash_runtime.run_verified(config_path)
                argv = execute.call_args.args[1]
                self.assertEqual(execute.call_args.args[2]["SPLASH_API_KEY"], plan.secrets["apiKey"])
                self.assertEqual(int(argv[argv.index("--max-new-tokens") + 1]), output)
                self.assertGreater(int(argv[argv.index("--request-timeout") + 1]), output / 10)
                provider = json.loads(plan.client_env["LLM_LAUNCHER_PI_PROVIDER"])
                self.assertEqual(provider["model"]["maxTokens"], output)
                self.assertEqual(provider["model"]["thinkingLevelMap"]["xhigh"], "xhigh")
                self.assertIsNone(provider["model"]["thinkingLevelMap"]["high"])
                self.assertTrue(provider["compactionRecovery"])
                request = {"model": plan.model["servedId"], "max_tokens": output,
                           "messages": [{"role": "user", "content": "hi"}]}
                relayed = json.loads(session_proxy.transform_chat_request(
                    json.dumps(request).encode(), {"backend": "splash", "servedModel": plan.model["servedId"],
                                                   "outputLimit": output, "reasoning": "xhigh"}, {"client": "pi"},
                ))
                self.assertEqual(relayed["max_tokens"], output)
                self.assertEqual(relayed["reasoning_effort"], "xhigh")

    def test_output_must_leave_prompt_room_at_every_context_tier(self) -> None:
        for context in splash_runtime.CONTEXTS:
            self.assertEqual(launcher.validated_limits(self.record, {
                "context": context, "output": context - 1024,
            }), (context, context - 1024))
            for output in (context - 1023, context, True):
                with self.subTest(context=context, output=output):
                    with self.assertRaises(ValueError):
                        launcher.validated_limits(self.record, {"context": context, "output": output})
                    with self.assertRaises(ValueError):
                        splash_runtime.planning_arguments(self.install, self.pack, context, port=8011, output=output)

    def test_pi_summary_is_bounded_and_disables_splash_thinking(self) -> None:
        request = {"model": "fixture", "max_tokens": 65_536, "reasoning_effort": "xhigh",
                   "messages": [{"role": "system", "content": session_proxy.PI_SUMMARIZATION_SYSTEM_PROMPT},
                                {"role": "user", "content": "Summarize confirmed work."}]}
        config = {"backend": "splash", "servedModel": "fixture", "reasoning": "xhigh", "outputLimit": 65_536}
        summary = json.loads(session_proxy.transform_chat_request(json.dumps(request).encode(), config, {"client": "pi"}))
        self.assertEqual(summary["max_tokens"], 4096)
        self.assertEqual(summary["reasoning_effort"], "none")
        self.assertNotIn("chat_template_kwargs", summary)
        request["messages"][0]["content"] = "Ordinary agent turn"
        ordinary = json.loads(session_proxy.transform_chat_request(json.dumps(request).encode(), config, {"client": "pi"}))
        self.assertEqual(ordinary["max_tokens"], 65_536)
        self.assertEqual(ordinary["reasoning_effort"], "xhigh")

    def test_build_splash_fails_closed_when_the_pack_changes(self) -> None:
        plan = self.plan()
        fixture = self.pack_path / "manifest.json"
        document = json.loads(fixture.read_text())
        document["artifact_set_sha256"] = "f" * 64
        fixture.write_text(json.dumps(document))
        with mock.patch.dict(launcher.BINARIES, {"splash": str(self.libexec / "engine" / "splash")}):
            with self.assertRaises(ValueError):
                launcher.build_splash(plan, plan.model["backends"]["splash"])

    def test_build_splash_rejects_a_changed_release(self) -> None:
        plan = self.plan()
        (self.libexec / "engine" / "splash").write_bytes(b"tampered")
        with mock.patch.dict(launcher.BINARIES, {"splash": str(self.libexec / "engine" / "splash")}):
            with self.assertRaises(ValueError):
                launcher.build_splash(plan, plan.model["backends"]["splash"])

    def test_wrapper_rejects_pack_change_after_planning(self):
        plan = self.plan()
        with mock.patch.dict(launcher.BINARIES, {"splash": str(self.libexec / "engine/splash")}):
            launcher.build_splash(plan, plan.model["backends"]["splash"])
        (self.pack_path / "draft/model.bin").unlink()
        with mock.patch.object(splash_runtime.os, "execve") as execute:
            with self.assertRaisesRegex(ValueError, "model changed"):
                splash_runtime.run_verified(pathlib.Path(plan.engine_argv[-1]))
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
