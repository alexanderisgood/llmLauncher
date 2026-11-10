"""Rec request/assistant overlays on generated data; no server or model loads."""
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

import client_planning
import inference_requests as inference
import launch_contract
import session_proxy
from sampling_contract import build_sampling_contract


FIELDS = ['temperature', 'top_p', 'top_k', 'presence_penalty', 'frequency_penalty', 'repetition_penalty', 'seed']
SAMPLING = {'temperature':1.0, 'top_p':0.95, 'top_k':20, 'presence_penalty':0.2,
            'frequency_penalty':0.0, 'repetition_penalty':1.0, 'seed':17}


class RecProtocolTests(unittest.TestCase):
    def test_relay_clamps_output_preserves_tool_reasoning_and_native_sampling(self):
        history = [{'role':'user', 'content':'Inspect the fixture'},
            {'role':'assistant', 'content':'', 'reasoning_content':'I need the tool result.',
             'tool_calls':[{'id':'call-1', 'type':'function', 'function':{'name':'inspect', 'arguments':'{}'}}]},
            {'role':'tool', 'tool_call_id':'call-1', 'content':'ready'}]
        body = {'model':'flint', 'messages':history, 'max_completion_tokens':9000, 'stream':True,
                'tool_choice':'auto', 'parallel_tool_calls':True, 'reasoning_effort':'none',
                'chat_template_kwargs':{'enable_thinking':False}, **SAMPLING}
        config = {'backend':'rec', 'servedModel':'flint', 'reasoning':'auto', 'outputLimit':8192}
        rewritten = json.loads(session_proxy.transform_chat_request(json.dumps(body).encode(), config, {'client':'pi'}))
        self.assertEqual(rewritten['messages'], history)
        self.assertEqual(rewritten['max_tokens'], 8192)
        self.assertNotIn('max_completion_tokens', rewritten)
        self.assertNotIn('reasoning_effort', rewritten)
        self.assertNotIn('chat_template_kwargs', rewritten)
        self.assertEqual({key:rewritten[key] for key in SAMPLING}, SAMPLING)

    def test_unsupported_native_controls_fail_and_summary_keeps_reasoning_on(self):
        body = {'model':'flint', 'messages':[{'role':'user', 'content':'fixture'}]}
        config = {'backend':'rec', 'servedModel':'flint', 'reasoning':'auto', 'outputLimit':8192}
        for change, reason in [({'tool_choice':'required'}, 'tool_choice'),
                ({'tool_choice':{'type':'function', 'function':{'name':'inspect'}}}, 'tool_choice'),
                ({'tool_choice':None}, 'tool_choice'), ({'parallel_tool_calls':False}, 'parallel_tool_calls'),
                ({'parallel_tool_calls':None}, 'parallel_tool_calls'),
                ({'frequency_penalty':0.1}, 'frequency_penalty'),
                ({'repetition_penalty':1.1}, 'repetition_penalty')]:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, reason):
                session_proxy.transform_chat_request(json.dumps({**body, **change}).encode(), config)
        for reasoning in ['off', 'low', 'high']:
            with self.subTest(reasoning=reasoning), self.assertRaisesRegex(ValueError, 'always enables'):
                session_proxy.transform_chat_request(json.dumps(body).encode(), {**config, 'reasoning':reasoning})
        summary = {**body, 'messages':[{'role':'system', 'content':session_proxy.PI_SUMMARIZATION_SYSTEM_PROMPT},
                                      {'role':'user', 'content':'Summarize the fixture'}]}
        rewritten = json.loads(session_proxy.transform_chat_request(json.dumps(summary).encode(), config, {'client':'pi'}))
        self.assertEqual(rewritten['max_tokens'], 8192)
        self.assertNotIn('reasoning_effort', rewritten)
        self.assertNotIn('chat_template_kwargs', rewritten)

    def test_reasoning_alias_normalizes_without_fabrication_or_merging(self):
        body = {'messages':[{'role':'assistant', 'content':'done', 'reasoning':'real previous reasoning'}]}
        result = inference.apply_rec_chat_contract(body)
        self.assertEqual(result['messages'][0], {'role':'assistant', 'content':'done', 'reasoning_content':'real previous reasoning'})
        with self.assertRaisesRegex(ValueError, 'one reasoning field'):
            inference.apply_rec_chat_contract({'messages':[{'reasoning':'a', 'reasoning_content':'b'}]})

    def test_builtin_chat_and_benchmark_use_rec_fields_and_real_history(self):
        contract = build_sampling_contract('custom', custom=SAMPLING).as_dict()
        policy = SimpleNamespace(chat_reasoning_levels=frozenset({'auto', 'off', 'high'}))
        service = inference.InferenceRequests(policy, inference.InferenceServices(
            inference.ValidationServices(launch_contract.validated_chat_messages,
                lambda *_args:contract, lambda *_args, **_kwargs:{'representableFields':FIELDS, 'implicitModelDefaults':False}),
            inference.ResponseServices(lambda *_args:None, lambda *_args:None)))
        plan = SimpleNamespace(backend='rec', client='chat', reasoning='auto', context=32768,
            output=8192, model={'servedId':'flint', 'backends':{'rec':{}}}, options={},
            sampling_contract=contract, sampling_enforcement={'representableFields':FIELDS, 'implicitModelDefaults':False},
            chat={'sampling':'custom', 'systemPrompt':''}, client_port=18011, port=18010,
            secrets={'apiKey':'fixture-key'}, client_env={})
        history = [{'role':'user', 'content':'first'},
            {'role':'assistant', 'content':'answer', 'reasoning_content':'visible earlier thinking'},
            {'role':'user', 'content':'next'}]
        chat = json.loads(service.build_chat_completion_request(plan, {'messages':history}).data)
        self.assertEqual(chat['messages'], history)
        benchmark = json.loads(service.build_benchmark_completion_request(plan, 'fixture prompt', 512, SAMPLING).data)
        for body in [chat, benchmark]:
            self.assertEqual({key:body[key] for key in SAMPLING}, SAMPLING)
            self.assertNotIn('reasoning_effort', body)
        with self.assertRaisesRegex(ValueError, 'always enables'):
            service.apply_chat_reasoning_contract({'messages':history}, 'rec', 'off')

    def test_pi_omp_and_both_opencode_versions_keep_reasoning_history(self):
        with tempfile.TemporaryDirectory(prefix='rec-client-fixture-') as directory:
            root = Path(directory)
            versions = {'pi':'0.84.2', 'omp':'omp/18.6.3', 'opencode':'opencode/2.0'}
            services = client_planning.ClientServices(lambda key:key, lambda key:key,
                lambda key:versions.get(key, ''), lambda *_args:'fixture', lambda *_args:{},
                lambda value,_project:value, lambda *_args:None, lambda *_args:['text'], lambda _size:'fixture-key')
            planner = client_planning.ClientPlanner(client_planning.ClientPolicy('0.84.2'),
                client_planning.ClientPaths(lambda:root, lambda:root), services)
            plan = SimpleNamespace(run_id='fixture-rec', backend='rec', client='pi',
                model={'id':'fixture', 'name':'Flint INT4', 'servedId':'flint', 'backends':{'rec':{'agentReasoning':['auto']}}},
                project=str(root), context=32768, output=8192, reasoning='auto', port=18010, client_port=18011,
                agent_host='terminal', purpose='interactive', runtime_binary='rec', pi_session_file=None,
                run_dir=root, client_env={}, client_argv=[], secrets={'apiKey':'fixture-key'}, warnings=[])
            with mock.patch.object(planner, 'pi_browser_test_module', return_value=None):
                planner.build_client_plan(plan)
            pi = json.loads(plan.client_env['LLM_LAUNCHER_PI_PROVIDER'])
            self.assertEqual(pi['backend'], 'rec')
            self.assertTrue(pi['model']['compat']['requiresReasoningContentOnAssistantMessages'])
            self.assertNotIn('supportsReasoningEffort', pi['model'])
            plan.client='omp'
            planner.build_client_plan(plan)
            omp = json.loads(plan.client_env['LLM_LAUNCHER_OMP_PROVIDER'])
            self.assertTrue(omp['models'][0]['compat']['requiresReasoningContentForToolCalls'])
            self.assertFalse(omp['models'][0]['compat']['allowsSyntheticReasoningContentForToolCalls'])
            plan.client='opencode'
            planner.build_client_plan(plan)
            overlay = json.loads(plan.client_env['OPENCODE_CONFIG_CONTENT'])
            model = next(iter(next(iter(overlay['providers'].values()))['models'].values()))
            self.assertEqual(model['compatibility']['reasoningField'], 'reasoning_content')
            self.assertEqual(model['capabilities']['reasoning'], {'supported':True, 'toggle':False})
            versions['opencode']='opencode/1.2'
            planner.build_client_plan(plan)
            overlay = json.loads(plan.client_env['OPENCODE_CONFIG_CONTENT'])
            model = next(iter(next(iter(overlay['provider'].values()))['models'].values()))
            self.assertEqual(model['interleaved'], {'field':'reasoning_content'})
            plan.reasoning='off'
            with self.assertRaisesRegex(ValueError, 'always enables'):
                planner.build_client_plan(plan)
            plan.reasoning='auto'; plan.client='codex'
            with self.assertRaisesRegex(ValueError, 'Responses API'):
                planner.build_client_plan(plan)


if __name__ == '__main__':
    unittest.main()
