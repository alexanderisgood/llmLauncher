"""Exact full work-surface overlays and identity; private generated paths only."""
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest import mock

import client_planning
import launcher
import omp_runtime


class ClientPlanningTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix="client-planning-")
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.binaries={key:f"/generated/{key}" for key in ("pi","omp","opencode","codex","mtplx")}
        self.versions={"/generated/pi":"0.84.2","/generated/omp":"omp/18.6.3","/generated/opencode":"opencode/2.0","/generated/mtplx":"2.11.2"}
        self.services=client_planning.ClientServices(lambda key:self.binaries.get(key),lambda key:self.binaries[key],
            lambda binary:self.versions.get(binary,"generated-version"),lambda *_args:"a"*64,
            lambda _path:{},lambda value,_project:value,lambda *_args:None,lambda *_args:["text"],lambda _size:"generated-client-key")
        self.planner=client_planning.ClientPlanner(client_planning.ClientPolicy("0.84.2"),
            client_planning.ClientPaths(lambda:self.root,lambda:self.root/"state"),self.services)

    def plan(self,client,backend="kolibri",host="terminal",reasoning="off"):
        directory=self.root/f"{client}-{backend}-{host}";directory.mkdir(exist_ok=True)
        return launcher.LaunchPlan("11111111-1111-4111-8111-111111111111",backend,client,
            {"name":"Generated model","id":"generated-model","servedId":"served-original",
             "backends":{backend:{"agentReasoning":["off","medium"],"codexReasoning":["off","medium","auto"]}}},
            str(self.root),8192,1024,reasoning,18810,"custom",{},agent_host=host,run_dir=directory,
            client_port=18811,secrets={"clientApiKey":"generated-client-key"})

    def legacy(self):
        fixture=Path(__file__).with_name("fixtures")/"client_planning_legacy.py"
        source=fixture.read_text().split("\n\n",1)[1].rstrip("\n")
        self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),json.loads(fixture.with_suffix(".json").read_text())["sourceSha256"])
        namespace={"Any":object,"LaunchPlan":launcher.LaunchPlan,"ClientRoute":client_planning.ClientRoute,
            "Path":Path,"hashlib":hashlib,"json":json,"re":__import__("re"),"secrets":secrets,
            "BINARIES":self.binaries,"APP_DIR":self.root,"STATE_DIR":self.root/"state","UZU_PI_TESTED_VERSION":"0.84.2",
            "model_artifact_fingerprint":self.services.artifact_fingerprint,"read_json":self.services.read_json,
            "command_version":self.services.command_version,"validated_pi_session_file":self.services.validated_pi_session_file,
            "prepare_mtplx_image_processor":self.services.prepare_mtplx_image_processor,"pi_model_inputs":self.services.pi_model_inputs,
            "omp_runtime":omp_runtime}
        exec(compile(fixture.read_text(),str(fixture),"exec"),namespace)
        namespace["CLIENT_BUILDERS"]={key:namespace[f"build_{key}_client"] for key in ("pi","omp","opencode","codex","chat")}
        return namespace

    def test_complete_legacy_commands_envs_files_warnings_match_all_surfaces_and_engine_routes(self):
        old=self.legacy()
        for backend in ("omlx","mtplx","lmstudio","kolibri","splash","whallm","llamacpp","uzu","freetoken","swiftlm","mference","slotstream"):
            for client in ("pi","omp","opencode","codex","chat"):
                for host in ("terminal","console"):
                    with self.subTest(backend=backend,client=client,host=host):
                        baseline=self.plan(client,backend,host);current=copy.deepcopy(baseline)
                        with mock.patch.object(secrets,"token_urlsafe",return_value="generated-client-key"):
                            old["build_client_plan"](baseline)
                            before={str(path.relative_to(baseline.run_dir)):path.read_bytes() for path in baseline.run_dir.rglob("*") if path.is_file()}
                            for name in before:
                                (baseline.run_dir/name).unlink()
                            self.planner.build_client_plan(current)
                        after={str(path.relative_to(current.run_dir)):path.read_bytes() for path in current.run_dir.rglob("*") if path.is_file()}
                        self.assertEqual(current.client_argv,baseline.client_argv)
                        self.assertEqual(current.client_env,baseline.client_env)
                        self.assertEqual(current.warnings,baseline.warnings)
                        self.assertEqual(current.secrets,baseline.secrets)
                        self.assertEqual(after,before)
                        for path in current.run_dir.rglob("*"):
                            if path.is_file():self.assertEqual(path.stat().st_mode & 0o777,0o600)

    def test_provider_identity_survives_port_and_run_restart_but_changes_with_model(self):
        first=self.plan("pi");second=copy.deepcopy(first);second.run_id="22222222";second.port+=10
        self.assertEqual(self.planner.pi_model_identity(first),self.planner.pi_model_identity(second))
        second.model["id"]="different-source"
        self.assertNotEqual(self.planner.pi_model_identity(first),self.planner.pi_model_identity(second))

    def test_exact_pi_omp_limits_reasoning_helper_roles_and_mtplx_headers_are_preserved(self):
        for client in ("pi","omp"):
            with self.subTest(client=client):
                plan=self.plan(client,"mtplx","console","medium")
                self.planner.build_client_plan(plan)
                if client=="pi":
                    overlay=json.loads(plan.client_env["LLM_LAUNCHER_PI_PROVIDER"])
                    self.assertEqual(overlay["model"]["contextWindow"],8192)
                    self.assertEqual(overlay["model"]["maxTokens"],1024)
                    self.assertTrue(overlay["model"]["reasoning"])
                    self.assertEqual(overlay["headers"],{"x-mtplx-client":"pi"})
                    self.assertIn("rpc",plan.client_argv)
                else:
                    settings=json.loads((plan.run_dir/"omp-settings.json").read_text())
                    self.assertFalse(settings["retry"]["modelFallback"])
                    self.assertFalse(settings["contextPromotion"]["enabled"])
                    self.assertEqual(len(set(settings["modelRoles"].values())),1)
                    self.assertEqual(set(settings["modelRoles"].values()),set(settings["enabledModels"]))

    def test_unknown_console_version_and_codex_reasoning_or_output_fail_before_overlay(self):
        plan=self.plan("omp","kolibri","console")
        self.versions["/generated/omp"]="omp/18.6.2"
        with self.assertRaisesRegex(ValueError,"Choose Terminal"):self.planner.build_client_plan(plan)
        self.assertFalse((plan.run_dir/"omp-settings.json").exists())
        plan=self.plan("codex");plan.output=512
        with self.assertRaisesRegex(ValueError,"at least 1,024"):self.planner.build_client_plan(plan)
        self.assertEqual(plan.client_argv,[])
        plan=self.plan("codex",reasoning="xhigh")
        with self.assertRaisesRegex(ValueError,"reasoning choices"):self.planner.build_client_plan(plan)

    def test_live_binary_selection_is_not_captured_in_a_controller_namespace(self):
        plan=self.plan("pi");self.planner.build_client_plan(plan)
        self.binaries["pi"]="/generated/new-pi"
        self.versions["/generated/new-pi"]="0.85.1"
        self.planner.build_client_plan(plan)
        self.assertEqual(plan.client_argv[0],"/generated/new-pi")
        self.assertNotIn("launcher",self.planner.__dict__)

    def test_splash_native_mlx_vision_reaches_each_agent_configuration(self):
        for client in ('pi', 'omp', 'opencode'):
            for major in (1, 2) if client == 'opencode' else (2,):
                for vision_format, runnable, expected in (
                        ('safetensors', True, ['text', 'image']),
                        ('gguf', True, ['text', 'image']),
                        ('none', True, ['text']),
                        ('safetensors', False, ['text'])):
                    with self.subTest(client=client, major=major, format=vision_format, runnable=runnable):
                        self.versions['/generated/opencode'] = f'opencode/{major}.0'
                        plan = self.plan(client, 'splash')
                        plan.run_dir = plan.run_dir / f'{major}-{vision_format}-{runnable}'
                        plan.run_dir.mkdir()
                        plan.model['splash'] = {'visionFormat': vision_format}
                        plan.model['backends']['splash'].update(
                            runnable=runnable, input=['text', 'image'])
                        self.planner.build_client_plan(plan)
                        if client == 'pi':
                            inputs = json.loads(plan.client_env['LLM_LAUNCHER_PI_PROVIDER'])['model']['input']
                        elif client == 'omp':
                            inputs = json.loads(plan.client_env['LLM_LAUNCHER_OMP_PROVIDER'])['models'][0]['input']
                        else:
                            cfg = json.loads(plan.client_env['OPENCODE_CONFIG_CONTENT'])
                            provider = next(iter(cfg['providers' if major == 2 else 'provider'].values()))
                            model = next(iter(provider['models'].values()))
                            inputs = model['capabilities' if major == 2 else 'modalities']['input']
                        self.assertEqual(inputs, expected)

    def test_flash_vision_is_advertised_to_all_supported_agent_clients(self):
        self.planner = client_planning.ClientPlanner(self.planner.policy, self.planner.paths,
            replace(self.services, pi_model_inputs=lambda *_args: ['text', 'image']))
        for backend in ('strata', 'splash', 'lmstudio'):
            for client in ('pi', 'omp', 'opencode'):
                for major in (1, 2) if client == 'opencode' else (2,):
                    with self.subTest(backend=backend, client=client, major=major):
                        self.versions['/generated/opencode'] = f'opencode/{major}.0'
                        plan = self.plan(client, backend)
                        self.planner.build_client_plan(plan)
                        if client == 'pi':
                            inputs = json.loads(plan.client_env['LLM_LAUNCHER_PI_PROVIDER'])['model']['input']
                        elif client == 'omp':
                            inputs = json.loads(plan.client_env['LLM_LAUNCHER_OMP_PROVIDER'])['models'][0]['input']
                        else:
                            cfg = json.loads(plan.client_env['OPENCODE_CONFIG_CONTENT'])
                            provider = next(iter(cfg['providers' if major == 2 else 'provider'].values()))
                            model = next(iter(provider['models'].values()))
                            inputs = model['capabilities' if major == 2 else 'modalities']['input']
                        self.assertEqual(inputs, ['text', 'image'])


if __name__=="__main__":unittest.main()
