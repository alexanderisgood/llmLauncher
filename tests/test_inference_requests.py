"""Complete inference-domain equivalence with generated data and local fixtures.

No model, installed engine, user project or global configuration is used.
"""
import ast
import copy
from dataclasses import FrozenInstanceError, fields, replace
import hashlib
import importlib.util
import inspect
import io
import itertools
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

import inference_requests as inference
import launcher
from sampling_contract import build_sampling_contract
from tests.test_splash_native_metrics import frames as splash_frames


FIXTURES=Path(__file__).parent/'fixtures'
METADATA=json.loads((FIXTURES/'inference_requests_legacy.json').read_text())
spec=importlib.util.spec_from_file_location('frozen_inference_requests',FIXTURES/'inference_requests_legacy.py')
legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)


def policy():
    return inference.InferencePolicy(**{name.lower().lstrip('_'):getattr(launcher,name)
        for name in METADATA['constants']})


def service(*, observations=None):
    observations=[] if observations is None else observations
    return inference.InferenceRequests(policy(),inference.InferenceServices(
        inference.ValidationServices(
            lambda *args,**kwargs:launcher.validated_chat_messages(*args,**kwargs),
            lambda *args,**kwargs:launcher.sampling_contract_from_settings(*args,**kwargs),
            lambda *args,**kwargs:launcher.sampling_route_enforcement(*args,**kwargs)),
        inference.ResponseServices(lambda *args:launcher.deep_get(*args),
            lambda context,value:observations.append((context,copy.deepcopy(value))))),
        launcher.LaunchCancelled)


def plan(backend='omlx',client='chat',reasoning='off',**extra):
    sampling={'temperature':.2,'top_p':.8,'top_k':12,'seed':17}
    defaults={'defaultSampling':sampling,'id':'generated-model','name':'Generated model',
        'servedId':'generated-served','backends':{backend:{'customSampling':backend!='uzu',
            'implicitSamplingDefaultsVerified':backend=='uzu'}}}
    value=launcher.LaunchPlan('generated-inference',backend,client,defaults,'/private/tmp',8192,1024,
        reasoning,18887,'ar',{},client_port=18888,chat={'sampling':'model','systemPrompt':'Generated system'},
        secrets={'apiKey':'fixture-engine-key','clientApiKey':'fixture-surface-key'},
        client_env={'LLM_LAUNCHER_CODEX_API_KEY':'fixture-codex-key'})
    for name,item in extra.items():setattr(value,name,item)
    return value


def request_shape(value):
    return value.full_url,value.get_method(),value.data,dict(value.header_items())


class Projection(ast.NodeTransformer):
    def visit_Name(self,node):
        return ast.copy_location(ast.Name(id={'Plan':'LaunchPlan',
            'RouteCheckToolCallAssembler':'_RouteCheckToolCallAssembler'}.get(node.id,node.id),ctx=node.ctx),node)

    def visit_Call(self,node):
        if isinstance(node.func,ast.Name) and node.func.id=='RouteCheckToolCallAssembler':
            node.args=node.args[:1]
        return self.generic_visit(node)

    def visit_Expr(self,node):
        if isinstance(node.value,ast.Call) and ast.unparse(node.value.func)=='output.set_close_connection':
            return ast.Assign(targets=[ast.Attribute(value=ast.Name(id='self',ctx=ast.Load()),
                attr='close_connection',ctx=ast.Store())],value=node.value.args[0])
        return self.generic_visit(node)

    def visit_Attribute(self,node):
        spelling=ast.unparse(node)
        if spelling.startswith('self.policy.') and len(spelling.split('.'))==3:
            name=next(name for name in METADATA['constants'] if name.lower().lstrip('_')==node.attr)
            return ast.Name(id=name,ctx=ast.Load())
        if spelling=='self._tool_name':return ast.Name(id='ROUTE_CHECK_TOOL_NAME',ctx=ast.Load())
        if spelling.startswith('self.services.') and len(spelling.split('.'))==4:
            if node.attr=='record_chat_cache_observation':
                return ast.Attribute(value=ast.Name(id='MANAGER',ctx=ast.Load()),attr=node.attr,ctx=ast.Load())
            return ast.Name(id=node.attr,ctx=ast.Load())
        if spelling=='self.cancelled_error':return ast.Name(id='LaunchCancelled',ctx=ast.Load())
        if isinstance(node.value,ast.Name) and node.value.id=='self' and node.attr in METADATA['instanceMethods']:
            return ast.Name(id=node.attr,ctx=ast.Load())
        if isinstance(node.value,ast.Name) and node.value.id=='output':
            value=ast.Name(id='self',ctx=ast.Load())
            if node.attr in {'write','flush'}:value=ast.Attribute(value=value,attr='wfile',ctx=ast.Load())
            return ast.Attribute(value=value,attr=node.attr,ctx=node.ctx)
        return self.generic_visit(node)


class InferenceSourceTests(unittest.TestCase):
    def test_all_controller_facades_keep_public_call_shapes_and_bind_complete_domain(self):
        self.assertIsInstance(launcher._inference_request_service(),inference.InferenceRequests)
        for name in METADATA['functions']:
            with self.subTest(function=name):
                before=inspect.signature(getattr(legacy,name));after=inspect.signature(getattr(launcher,name))
                current=list(after.parameters.values())
                if name=='run_route_check_request':
                    self.assertEqual((current[-1].name,current[-1].kind,current[-1].default),
                                     ('opener',inspect.Parameter.KEYWORD_ONLY,None))
                    current=current[:-1]
                self.assertEqual([(p.name,p.kind,p.default) for p in before.parameters.values()],
                                 [(p.name,p.kind,p.default) for p in current])
        before=inspect.signature(legacy._RouteCheckToolCallAssembler)
        after=inspect.signature(launcher._RouteCheckToolCallAssembler)
        self.assertEqual([(p.name,p.kind,p.default) for p in before.parameters.values()],
                         [(p.name,p.kind,p.default) for p in after.parameters.values()])
        self.assertTrue(issubclass(launcher._RouteCheckToolCallAssembler,inference.RouteCheckToolCallAssembler))
        self.assertIn(Path(inference.__file__).resolve(),launcher.CONTROLLER_SOURCE_PATHS)

    def test_all_21_functions_11_tool_methods_and_complete_chat_relay_match_frozen_source(self):
        text=(FIXTURES/'inference_requests_legacy.py').read_text()
        self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),METADATA['fixtureDigest'])
        old=ast.parse(text);new=ast.parse(Path(inference.__file__).read_text())
        old_functions={n.name:n for n in old.body if isinstance(n,ast.FunctionDef)}
        new_functions={n.name:n for n in new.body if isinstance(n,ast.FunctionDef)}
        requests=next(n for n in new.body if isinstance(n,ast.ClassDef) and n.name=='InferenceRequests')
        new_functions.update({n.name:n for n in requests.body if isinstance(n,ast.FunctionDef)})
        def compare(left,right):
            self.assertEqual(ast.dump(Projection().visit(ast.Module(body=copy.deepcopy(left),type_ignores=[])),include_attributes=False),
                ast.dump(Projection().visit(ast.Module(body=copy.deepcopy(right),type_ignores=[])),include_attributes=False))
        def close_http_errors(nodes):
            expected=copy.deepcopy(nodes);found=0
            for handler in ast.walk(ast.Module(body=expected,type_ignores=[])):
                if isinstance(handler,ast.ExceptHandler) and ast.unparse(handler.type)=='urllib.error.HTTPError':
                    self.assertEqual(handler.name,'error')
                    handler.body=[ast.With(items=[ast.withitem(context_expr=ast.Name(id='error',ctx=ast.Load()),optional_vars=None)],body=handler.body)]
                    found+=1
            self.assertEqual(found,1)
            return expected
        for name in METADATA['functions']:
            expected=old_functions[name].body
            if name in {'run_benchmark_completion','run_route_check_request'}:expected=close_http_errors(expected)
            actual=copy.deepcopy(new_functions[name].body)
            if name in {'apply_chat_reasoning_contract', 'build_chat_completion_request', 'build_benchmark_completion_request'}:
                # Rec is a new native contract, covered by test_rec_protocol.
                # Keep the frozen comparison exact for every existing engine.
                condition = "backend == 'rec'" if name == 'apply_chat_reasoning_contract' else "plan.backend == 'rec'"
                added=[node for node in actual if isinstance(node,ast.If) and ast.unparse(node.test)==condition]
                self.assertEqual(len(added),1)
                actual.remove(added[0])
            if name=='apply_chat_reasoning_contract':
                # The Splash branch now adds the native thinking budget. Its
                # explicit behavior is tested below; all other AST stays exact.
                changed=[node for node in actual if isinstance(node,ast.If) and ast.unparse(node.test)=="backend == 'splash'"]
                original=[node for node in expected if isinstance(node,ast.If) and ast.unparse(node.test)=="backend == 'splash'"]
                self.assertEqual(len(changed),1);self.assertEqual(len(original),1)
                changed[0].body=copy.deepcopy(original[0].body)
            if name=='build_benchmark_completion_request':
                # Modern Splash permits top_k=0. Only this exact legacy guard
                # gains a capability check; retain its body and every sibling.
                changed=[node for statement in actual for node in ast.walk(statement) if isinstance(node,ast.If)
                         and ast.unparse(node.test).startswith("plan.backend == 'splash' and body.get('top_k') == 0")]
                original=[node for statement in expected for node in ast.walk(statement) if isinstance(node,ast.If)
                          and ast.unparse(node.test)=="plan.backend == 'splash' and body.get('top_k') == 0"]
                self.assertEqual(len(changed),1);self.assertEqual(len(original),1)
                self.assertEqual(ast.unparse(changed[0].test),"plan.backend == 'splash' and body.get('top_k') == 0 and ('frequency_penalty' not in enforcement['representableFields'])")
                changed[0].test=copy.deepcopy(original[0].test)
            if name=='run_route_check_request':
                calls=[node for statement in actual for node in ast.walk(statement)
                       if isinstance(node,ast.Call) and isinstance(node.func,ast.IfExp)]
                self.assertEqual(len(calls),1)
                self.assertEqual(ast.unparse(calls[0].func),'urllib.request.urlopen if opener is None else opener')
                self.assertEqual(ast.unparse(calls[0]),'(urllib.request.urlopen if opener is None else opener)(request, timeout=900)')
                calls[0].func=ast.parse('urllib.request.urlopen',mode='eval').body
            with self.subTest(function=name):compare(actual,expected)
        old_tool=next(n for n in old.body if isinstance(n,ast.ClassDef) and n.name=='_RouteCheckToolCallAssembler')
        new_tool=next(n for n in new.body if isinstance(n,ast.ClassDef) and n.name=='RouteCheckToolCallAssembler')
        old_methods={n.name:n for n in old_tool.body if isinstance(n,ast.FunctionDef)}
        new_methods={n.name:n for n in new_tool.body if isinstance(n,ast.FunctionDef)}
        self.assertEqual(set(old_methods),set(new_methods))
        for name in old_methods:
            with self.subTest(toolMethod=name):
                body=new_methods[name].body
                if name=='__init__':
                    self.assertEqual(ast.unparse(body[0]),'self._tool_name = tool_name');body=body[1:]
                compare(body,old_methods[name].body)
        old_relay=next(n for n in old.body if isinstance(n,ast.ClassDef) and n.name=='FrozenChatRelay').body[0]
        # The one deliberate change protects an early browser-header failure.
        # Project that exact ownership repair onto the frozen relay, then retain
        # the complete body comparison for every other statement.
        body=close_http_errors(old_relay.body)
        header_start=next(i for i,n in enumerate(body) if isinstance(n,ast.Expr)
            and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute)
            and n.value.func.attr=='send_response')
        outer=body[header_start+6]
        self.assertIsInstance(outer,ast.Try)
        response_scope=outer.body[0]
        self.assertIsInstance(response_scope,ast.With)
        header_guard=ast.parse('try:\n    pass\nexcept (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):\n    browser_interrupted = True').body[0]
        header_guard.body=body[header_start:header_start+6]
        del body[header_start:header_start+6]
        response_scope.body[0].test=ast.parse('not browser_interrupted',mode='eval').body
        response_scope.body.insert(0,header_guard)
        # The second explicit repair observes one bounded non-SSE document only
        # after complete EOF. All original byte relay and terminal/cache code
        # remains in this full-body comparison; no method is excluded.
        variables=ast.parse("json_buffer = bytearray()\njson_oversized = False\njson_last_byte_at: float | None = None\nclean_eof = False\njson_metadata_known = False").body
        after_browser=next(i for i,n in enumerate(body) if isinstance(n,ast.Assign)
            and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='browser_interrupted')+1
        body[after_browser:after_browser]=variables
        loop=response_scope.body[1]
        self.assertIsInstance(loop,ast.While)
        eof=next(n for n in loop.body if isinstance(n,ast.If) and ast.unparse(n.test)=='not line')
        eof.body.insert(0,ast.parse('clean_eof = True').body[0])
        parse_at=next(i for i,n in enumerate(loop.body) if isinstance(n,ast.Try)
            and isinstance(n.body[0],ast.Assign) and ast.unparse(n.body[0].targets[0])=='decoded')
        collector=ast.parse("""
if not is_sse:
    json_last_byte_at = time.monotonic() - started
    if not json_oversized:
        if len(json_buffer) + len(line) > self.policy.max_json:
            json_oversized = True
            json_buffer.clear()
        else:
            json_buffer.extend(line)
    continue
""").body[0]
        loop.body.insert(parse_at,collector)
        final_at=next(i for i,n in enumerate(body) if isinstance(n,ast.Assign)
            and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='final_terminal_state')
        buffered=ast.parse("""
if not is_sse and clean_eof and not browser_interrupted and not upstream_interrupted and not json_oversized:
    try:
        event = json.loads(json_buffer)
        if isinstance(event, dict):
            json_metadata_known = True
            terminal_state = self.chat_stream_terminal_state(event)
            facts = chat_cache_observation_event(event)
            output_observed = facts.get("outputObserved") is True
            first_output_at = json_last_byte_at if output_observed else None
            if isinstance(facts.get("usage"), dict):
                last_usage = facts["usage"]
    except (TypeError, ValueError, UnicodeError):
        pass
""").body[0]
        final=body[final_at]
        final.value=ast.IfExp(test=ast.parse('is_sse or json_metadata_known',mode='eval').body,body=final.value,orelse=ast.Constant(value=''))
        body.insert(final_at,buffered)
        compare(new_functions['stream_chat'].body,body)

    def test_import_needs_no_controller_and_performs_no_requests_processes_or_writes(self):
        code="""
import builtins,pathlib,subprocess,sys,urllib.request
sys.path.insert(0,sys.argv[1]); original=builtins.__import__
def import_only(name,*a,**k):
 if name=='launcher': raise AssertionError('controller import')
 return original(name,*a,**k)
builtins.__import__=import_only
def forbidden(*a,**k):raise AssertionError('side effect on import')
subprocess.Popen=forbidden;urllib.request.urlopen=forbidden;pathlib.Path.write_text=forbidden
import inference_requests
assert 'launcher' not in sys.modules
"""
        result=subprocess.run([sys.executable,'-I','-B','-c',code,str(Path(inference.__file__).parent)],
            stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_policy_is_immutable_and_probe_deepcopy_remains_detached_json(self):
        value=policy();copied=copy.deepcopy(value.benchmark_probe_contract['sampling'])
        copied['seed']=999
        self.assertEqual(value.benchmark_probe_contract['sampling']['seed'],17)
        self.assertIsInstance(json.dumps(copied),str)
        with self.assertRaises(TypeError):value.benchmark_probe_contract['sampling']['seed']=999
        with self.assertRaises(FrozenInstanceError):value.max_json=1
        with self.assertRaises(FrozenInstanceError):value.client_adapters['chat'].protocol='other'


class InferenceBuilderTests(unittest.TestCase):
    def setUp(self):
        original=legacy.apply_chat_reasoning_contract
        def expected(body,backend,reasoning):
            value=original(body,backend,reasoning)
            if backend=='splash':
                # Add the one new wire field at the same construction point,
                # leaving all legacy fields and other engines byte-for-byte.
                ceiling={'auto':32768,'off':0,'low':1024,'medium':4096,'xhigh':32768}[reasoning]
                value['thinking_token_budget']=min(ceiling,value.get('max_tokens',8192)//2)
            return value
        patch=mock.patch.object(legacy,'apply_chat_reasoning_contract',side_effect=expected)
        patch.start();self.addCleanup(patch.stop)

    def test_chat_benchmark_and_both_route_requests_preserve_all_12_engine_wire_contracts(self):
        domain=service()
        for backend in launcher.ENGINE_ADAPTERS:
            if backend == 'rec': continue  # Added after the frozen 12-engine contract.
            for client in ('chat','pi','omp','codex'):
                with self.subTest(backend=backend,client=client):
                    item=plan(backend,client)
                    if client=='chat':
                        payload={'messages':[{'role':'user','content':'Generated fixture message'}]}
                        expected=request_shape(legacy.build_chat_completion_request(item,payload))
                        self.assertEqual(request_shape(domain.build_chat_completion_request(item,payload)),expected)
                        self.assertEqual(request_shape(launcher.build_chat_completion_request(item,payload)),expected)
                        self.assertEqual(request_shape(domain.build_benchmark_completion_request(item,'Generated benchmark',64,{})),
                            request_shape(legacy.build_benchmark_completion_request(item,'Generated benchmark',64,{})))
                    for tool_probe in (False,True):
                        self.assertEqual(request_shape(domain.build_route_check_request(item,tool_probe=tool_probe)),
                            request_shape(legacy.build_route_check_request(item,tool_probe=tool_probe)))

    def test_reasoning_modes_and_invalid_modes_match_frozen(self):
        domain=service()
        for backend in launcher.ENGINE_ADAPTERS:
            if backend == 'rec': continue  # Its auto-only native contract has separate tests.
            for reasoning in (*sorted(launcher.CHAT_REASONING_LEVELS),'invalid'):
                outcomes=[]
                for apply in (legacy.apply_chat_reasoning_contract,domain.apply_chat_reasoning_contract):
                    body={'reasoning_effort':'inherited','thinking_mode':'inherited','think':True,
                        'chat_template_kwargs':{'enable_thinking':True}}
                    try:outcomes.append(apply(body,backend,reasoning))
                    except ValueError as error:outcomes.append(('error',str(error)))
                self.assertEqual(outcomes[0],outcomes[1],(backend,reasoning))

    def test_sampling_fixed_probe_and_reasoning_boundary_exact_fields(self):
        domain=service();sampling=copy.deepcopy(launcher.BENCHMARK_PROBE_CONTRACT['sampling'])
        for backend in ('omlx','mtplx','splash','kolibri','uzu','llamacpp'):
            for greedy in (False,True):
                with self.subTest(backend=backend,greedy=greedy):
                    outcomes=[]
                    for builder in (legacy.build_benchmark_completion_request,domain.build_benchmark_completion_request):
                        try:outcomes.append(request_shape(builder(plan(backend), 'Generated probe',64,sampling,greedy_probe=greedy)))
                        except ValueError as error:outcomes.append(('error',str(error)))
                    self.assertEqual(outcomes[0],outcomes[1])
        item=plan('llamacpp',options={'_qualificationThinkingBudgetTokens':launcher.ROUTE_QUALIFICATION_THINKING_TOKENS})
        for budget in (0,32,-1,True,launcher.ROUTE_QUALIFICATION_MAX_TOKENS):
            outcomes=[]
            for builder in (legacy.build_benchmark_completion_request,domain.build_benchmark_completion_request):
                try:outcomes.append(request_shape(builder(item,'Generated boundary',launcher.ROUTE_QUALIFICATION_MAX_TOKENS,
                    sampling,reasoning_budget_tokens=budget,greedy_probe=True)))
                except ValueError as error:outcomes.append(('error',str(error)))
            self.assertEqual(outcomes[0],outcomes[1])

    def test_validation_callbacks_remain_live_and_output_uses_private_surface_credentials(self):
        domain=service();item=plan()
        with mock.patch.object(launcher,'validated_chat_messages',return_value=[{'role':'user','content':'Late generated fields'}]) as validate:
            request=domain.build_chat_completion_request(item,{'messages':[]})
        validate.assert_called_once();self.assertEqual(json.loads(request.data)['messages'][0]['content'],'Late generated fields')
        self.assertEqual(request.get_header('Authorization'),'Bearer fixture-surface-key')
        self.assertIn(':18888/',request.full_url)
        with self.assertRaisesRegex(ValueError,'not a built-in chat'):
            domain.build_chat_completion_request(plan(client='pi'),{})


class SplashNativeThinkingContractTests(unittest.TestCase):
    def test_efforts_pin_native_budgets_and_auto_uses_route_default(self):
        domain=service()
        for effort,budget in (('off',0),('low',1024),('medium',4096),('xhigh',32768),('auto',32768)):
            with self.subTest(effort=effort):
                body={'max_tokens':100000,'reasoning_effort':'low','think':True}
                result=domain.apply_chat_reasoning_contract(body,'splash',effort)
                self.assertIs(result,body)
                self.assertEqual(result['thinking_token_budget'],budget)
                self.assertNotIn('think',result)
                if effort=='auto':self.assertNotIn('reasoning_effort',result)
                else:self.assertEqual(result['reasoning_effort'],'none' if effort=='off' else effort)

    def test_thinking_cannot_take_more_than_half_output_even_for_unlimited_request(self):
        domain=service()
        for effort in ('low','medium','xhigh','auto'):
            for requested in (None,-1,100000):
                with self.subTest(effort=effort,requested=requested):
                    body={'max_tokens':257,'thinking_token_budget':requested}
                    result=domain.apply_chat_reasoning_contract(body,'splash',effort)
                    self.assertEqual(result['thinking_token_budget'],128)

    def test_callers_may_lower_budget_but_cannot_bypass_the_route_ceiling(self):
        domain=service()
        for native,alias,expected in ((7,20,7),(200000,3,3),(200000,200000,4096),(0,None,0),(-1,5,5)):
            with self.subTest(native=native,alias=alias):
                body={'max_tokens':100000,'thinking_token_budget':native}
                if alias is not None:body['thinking_budget_tokens']=alias
                result=domain.apply_chat_reasoning_contract(body,'splash','medium')
                self.assertEqual(result['thinking_token_budget'],expected)
                if alias is not None:self.assertEqual(result['thinking_budget_tokens'],expected)

    def test_noninteger_and_negative_budgets_are_rejected(self):
        domain=service()
        for key in ('thinking_token_budget','thinking_budget_tokens'):
            values=(True,False,1.5,'10',-2) + ((-1,) if key=='thinking_budget_tokens' else ())
            for value in values:
                with self.subTest(key=key,value=value),self.assertRaisesRegex(ValueError,key):
                    domain.apply_chat_reasoning_contract({'max_tokens':8192,key:value},'splash','medium')

    def test_native_field_does_not_leak_into_other_engine_contracts(self):
        domain=service()
        for backend in launcher.ENGINE_ADAPTERS:
            if backend in {'splash', 'rec'}:continue
            with self.subTest(backend=backend):
                result=domain.apply_chat_reasoning_contract({'max_tokens':8192},backend,'off')
                self.assertNotIn('thinking_token_budget',result)

    def test_modern_benchmark_keeps_unlimited_top_k_and_legacy_uses_minimum(self):
        domain=service();sampling=copy.deepcopy(launcher.BENCHMARK_PROBE_CONTRACT['sampling'])
        for modern in (False,True):
            with self.subTest(modern=modern):
                item=plan('splash')
                fields=['temperature','top_p','top_k','seed']
                if modern:fields+=['presence_penalty','frequency_penalty','repetition_penalty']
                item.model['backends']['splash']['samplingFields']=fields
                request=domain.build_benchmark_completion_request(item,'Generated probe',64,sampling,greedy_probe=True)
                self.assertEqual(json.loads(request.data)['top_k'],0 if modern else 1)


class Response:
    def __init__(self,values=(),*,content_type='text/event-stream',done=True,raw=None,read_error=False):
        self.headers={'Content-Type':content_type};self.closed=False
        self.raw=raw if raw is not None else b''.join(b'data: '+json.dumps(v).encode()+b'\n\n' for v in values)+(b'data: [DONE]\n\n' if done else b'')
        self.handle=io.BytesIO(self.raw);self.read_error=read_error
    def __enter__(self):return self
    def __exit__(self,*_):self.closed=True
    def __iter__(self):return iter(self.handle.readlines())
    def read(self,size):return self.handle.read(size)
    def readline(self):
        line=self.handle.readline()
        if not line and self.read_error:raise OSError('generated disconnect')
        return line


def timed(function,response,*args,**kwargs):
    ticks=itertools.count(0,.25)
    with mock.patch.object(inference.urllib.request,'urlopen',return_value=response), \
            mock.patch.object(inference.time,'monotonic',side_effect=lambda:next(ticks)):
        return function(*args,**kwargs)


def chat_events(*,terminal='stop',usage=None):
    return [{'choices':[{'index':0,'delta':{'reasoning_content':'Generated reason','content':'First '}}]},
        {'choices':[{'index':0,'delta':{'content':'answer'},'finish_reason':terminal}],
         'usage':usage or {'prompt_tokens':120,'completion_tokens':32,'prompt_tokens_details':{'cached_tokens':80}}}]


class InferenceCompletionTests(unittest.TestCase):
    def test_benchmark_usage_terminal_cancellation_errors_and_observer_match_frozen(self):
        domain=service()
        cases=[chat_events(),chat_events(terminal='length'),chat_events(terminal=None),
            chat_events(usage={'prompt_tokens':True,'completion_tokens':32}),
            [{'error':{'message':'Generated runtime error'}}]]
        for values in cases:
            outcomes=[]
            for run in (legacy.run_benchmark_completion,domain.run_benchmark_completion):
                replies=[]
                try:outcomes.append((timed(run,Response(values),plan(),'Generated benchmark',64,{},threading.Event(),reply_observer=replies.append),replies))
                except RuntimeError as error:outcomes.append(('error',str(error)))
            self.assertEqual(outcomes[0],outcomes[1])
        cancelled=threading.Event();cancelled.set()
        with self.assertRaises(launcher.LaunchCancelled):
            timed(domain.run_benchmark_completion,Response(chat_events()),plan(),'Generated benchmark',64,{},cancelled)
        response=Response(raw=b'data: invalid-json\n\n')
        with self.assertRaisesRegex(RuntimeError,'malformed JSON'):
            item=plan('llamacpp',options={'_qualificationThinkingBudgetTokens':launcher.ROUTE_QUALIFICATION_THINKING_TOKENS})
            timed(domain.run_benchmark_completion,response,item,'Generated boundary',64,{},threading.Event())
        self.assertTrue(response.closed)

    def test_native_kolibri_and_splash_proofs_match_and_buffered_delivery_never_fabricates_tps(self):
        domain=service()
        usage={'prompt_tokens':120,'completion_tokens':32,'total_tokens':152,'generation_duration':10.,'generation_tokens_per_second':3.2,
            'prompt_eval_duration':2.,'prompt_tokens_details':{'cached_tokens':80},
            'kolibri_native_stats':{'version':1,'prompt_tokens':120,'processed_prompt_tokens':40,
                'cached_prompt_tokens':80,'generation_tokens':32}}
        terminal,splash=splash_frames(completion=48,decoded=40,start_ms=100,decode_ms=5000,queue_ms=0)
        terminal['choices'][0]['finish_reason']='stop'
        cases=[('kolibri',chat_events(usage=usage)),('splash',[*chat_events()[:1],
            {'choices':[{'delta':{'content':'second'}}]},terminal,splash]),('splash',chat_events())]
        for backend,values in cases:
            outcomes=[timed(run,Response(values),plan(backend),'Generated native metadata',64,{},threading.Event())
                for run in (legacy.run_benchmark_completion,domain.run_benchmark_completion)]
            self.assertEqual(outcomes[0],outcomes[1])
            if backend=='kolibri':self.assertEqual(outcomes[1]['decodeTokensPerSecond'],3.2)
            elif values[-1] is splash:self.assertEqual(outcomes[1]['decodeTokensPerSecond'],8)
            else:self.assertIsNone(outcomes[1]['decodeTokensPerSecond'])

    def test_route_terminal_tool_identity_malformed_and_cross_choice_failures_match_frozen(self):
        domain=service()
        valid=[{'choices':[{'index':0,'delta':{'tool_calls':[{'index':0,'id':'generated-call','type':'function',
            'function':{'name':launcher.ROUTE_CHECK_TOOL_NAME,'arguments':'{"status":'}}]}}]},
            {'choices':[{'index':0,'delta':{'tool_calls':[{'index':0,'function':{'arguments':'"ready"}'}}]},'finish_reason':'tool_calls'}]}]
        cases=[valid,valid[:-1],chat_events(),
            [valid[0],{'choices':[{'index':1,'delta':{},'finish_reason':'tool_calls'}]}],
            [{'choices':[{'index':0,'message':{'tool_calls':[{'id':'generated-call','type':'function','function':{
                'name':launcher.ROUTE_CHECK_TOOL_NAME,'arguments':'{"status":"ready","status":"ready"}'}}]},'finish_reason':'tool_calls'}]}]]
        for values in cases:
            outcomes=[timed(run,Response(values),plan(client='pi'),threading.Event(),tool_probe=True)
                for run in (legacy.run_route_check_request,domain.run_route_check_request)]
            self.assertEqual(outcomes[0],outcomes[1])
        self.assertTrue(timed(domain.run_route_check_request,Response(valid),plan(client='pi'),threading.Event(),tool_probe=True)['toolContractValid'])
        for raw in (b'data: invalid\n',b'data: [DONE]\ndata: {}\n'):
            with self.assertRaisesRegex(RuntimeError,'malformed|after its terminal'):
                timed(domain.run_route_check_request,Response(raw=raw),plan(client='pi'),threading.Event())

    def test_responses_tool_replay_and_final_identity_are_complete_and_detached(self):
        domain=service();call={'type':'function_call','id':'generated-item','call_id':'generated-call',
            'name':launcher.ROUTE_CHECK_TOOL_NAME,'arguments':'{"status":"ready"}'}
        values=[{'type':'response.output_item.added','output_index':0,'item':{**call,'arguments':''}},
            {'type':'response.function_call_arguments.delta','output_index':0,'item_id':'generated-item','delta':'{"status":'},
            {'type':'response.function_call_arguments.done','output_index':0,'item_id':'generated-item','arguments':call['arguments']},
            {'type':'response.output_item.done','output_index':0,'item':call},
            {'type':'response.completed','response':{'status':'completed','output':[call],'usage':{'input_tokens':120,'output_tokens':32}}}]
        results=[timed(run,Response(values,done=False),plan(client='codex'),threading.Event(),tool_probe=True)
            for run in (legacy.run_route_check_request,domain.run_route_check_request)]
        self.assertEqual(results[0],results[1]);self.assertTrue(results[1]['toolContractValid'])
        self.assertNotIn('arguments',results[1]);self.assertNotIn('generated-call',json.dumps(results[1]))
        values[-1]['type']='response.incomplete';values[-1]['response']['status']='incomplete'
        self.assertFalse(timed(domain.run_route_check_request,Response(values),plan(client='codex'),threading.Event(),tool_probe=True)['toolContractValid'])


class Output:
    def __init__(self,*,disconnect=False):
        self.status=None;self.headers=[];self.closed=False;self.bytes=bytearray();self.wfile=self
        self.disconnect=disconnect
    def send_response(self,value):self.status=value
    def send_header(self,key,value):self.headers.append((key,value))
    def end_headers(self):pass
    def set_close_connection(self,value):self.closed=value
    def write(self,value):
        if self.disconnect:raise BrokenPipeError('generated browser disconnect')
        self.bytes.extend(value)
    def flush(self):pass
    def port(self):return inference.ResponseOutput(self.send_response,self.send_header,self.end_headers,
        self.set_close_connection,self.write,self.flush)


class HTTPErrorOwnershipTests(unittest.TestCase):
    def test_all_three_request_methods_close_bounded_http_errors_even_when_read_fails(self):
        class FailingBody(io.BytesIO):
            def read(self,*args):raise OSError("Generated HTTP error read failure")
        for method in ("stream_chat","run_benchmark_completion","run_route_check_request"):
            for read_fails in (False,True):
                with self.subTest(method=method,read_fails=read_fails):
                    body=FailingBody() if read_fails else io.BytesIO(b'{"error":{"message":"Generated rejected request"}}'+b' '*20000)
                    error=inference.urllib.error.HTTPError("http://127.0.0.1:18887/generated",401,"Generated rejection",{},body)
                    domain=service();item=plan()
                    with mock.patch.object(inference.urllib.request,"urlopen",side_effect=error),self.assertRaises((RuntimeError,OSError)):
                        if method=="stream_chat":domain.stream_chat(launcher.urllib.request.Request(error.url),Output().port())
                        elif method=="run_benchmark_completion":domain.run_benchmark_completion(item,"Generated",64,{},threading.Event())
                        else:domain.run_route_check_request(item,threading.Event())
                    self.assertTrue(body.closed,"An acquired HTTP error body must be closed on every exit")


class ChatRelayTests(unittest.TestCase):
    def test_buffered_json_compact_pretty_unicode_and_fragmented_observation_match(self):
        payload={"choices":[{"message":{"content":"Generated answer 🙂\nsecond line"},"finish_reason":"stop"}],
                 "usage":{"prompt_tokens":120,"completion_tokens":32,"prompt_tokens_details":{"cached_tokens":80}}}
        for indent in (None,2):
            for fragmented in (False,True):
                with self.subTest(indent=indent,fragmented=fragmented):
                    wire=json.dumps(payload,ensure_ascii=False,indent=indent).encode();records=[];domain=service(observations=records)
                    response=Response(content_type="application/json; charset=utf-8",raw=wire);output=Output()
                    if fragmented:
                        pieces=iter([wire[i:i+3] for i in range(0,len(wire),3)]+[b""])
                        response.readline=lambda:next(pieces)
                    request=launcher.urllib.request.Request("http://127.0.0.1:18887/generated")
                    context={"ownerRunId":"generated-owner","attachmentId":"generated-surface"};request._launcher_cache_context=context
                    with mock.patch.object(inference.json,"loads",wraps=json.loads) as loads:
                        timed(domain.stream_chat,response,request,output.port())
                    self.assertEqual(loads.call_count,1,"Non-SSE metadata is decoded exactly once after complete EOF")
                    self.assertEqual(output.bytes,wire);self.assertTrue(response.closed);self.assertEqual(len(records),1);self.assertEqual(records[0][0],context)
                    result=records[0][1]
                    self.assertTrue(result["completed"]);self.assertFalse(result["interrupted"]);self.assertTrue(result["outputObserved"])
                    self.assertEqual((result["promptTokens"],result["completionTokens"],result["cachedPromptTokens"]),(120,32,80))
                    self.assertIsNotNone(result["ttftSeconds"]);self.assertNotIn("decodeTokensPerSecond",result)
                    self.assertNotIn("Generated answer",json.dumps(result))

    def test_pretty_json_output_timing_is_last_delivered_byte_not_opening_brace(self):
        wire=json.dumps({"choices":[{"message":{"content":"Generated delayed answer"},"finish_reason":"stop"}],
                         "usage":{"prompt_tokens":120,"completion_tokens":32}},indent=2).encode()
        # The first JSON syntax chunk arrives long before the answer/document.
        pieces=iter([wire[:2],wire[2:-2],wire[-2:],b""])
        response=Response(content_type="application/json",raw=wire);response.readline=lambda:next(pieces)
        records=[];domain=service(observations=records);output=Output()
        with mock.patch.object(inference.urllib.request,"urlopen",return_value=response),mock.patch.object(inference.time,"monotonic",side_effect=[100,101,107,110,111]):
            domain.stream_chat(launcher.urllib.request.Request("http://127.0.0.1:18887/generated"),output.port())
        result=records[0][1]
        self.assertEqual(result["ttftSeconds"],10,"Buffered JSON output is only evidenced by the complete delivered document")
        self.assertEqual(result["totalSeconds"],11);self.assertTrue(result["completed"]);self.assertEqual(output.bytes,wire)
        self.assertNotIn("decodeTokensPerSecond",result)

    def test_buffered_json_bounds_malformed_and_partial_disconnect_never_credit_partial_metadata(self):
        payload={"choices":[{"message":{"content":"Generated"},"finish_reason":"stop"}],"usage":{"prompt_tokens":120,"completion_tokens":32}}
        valid=json.dumps(payload).encode()
        for kind in ("exact-bound","oversized","malformed","invalid-utf8","upstream-interrupted","browser-disconnected","valid-prefix-extra"):
            with self.subTest(kind=kind):
                wire=b'{"bad":' if kind=="malformed" else b'{"bad":"\xff"}' if kind=="invalid-utf8" else valid+b'\nextra' if kind=="valid-prefix-extra" else valid
                records=[];domain=service(observations=records)
                domain.policy=replace(domain.policy,max_json=len(valid)-1 if kind=="oversized" else len(wire))
                response=Response(content_type="application/json",raw=wire,read_error=kind=="upstream-interrupted");output=Output(disconnect=kind=="browser-disconnected")
                with mock.patch.object(inference.json,"loads",wraps=json.loads) as loads:
                    timed(domain.stream_chat,response,launcher.urllib.request.Request("http://127.0.0.1:18887/generated"),output.port())
                self.assertTrue(response.closed);self.assertEqual(len(records),1)
                result=records[0][1]
                if kind=="exact-bound":self.assertTrue(result["completed"]);self.assertEqual(result["completionTokens"],32)
                else:
                    self.assertFalse(result["completed"]);self.assertFalse(result["outputObserved"]);self.assertIsNone(result["promptTokens"])
                    self.assertIsNone(result["completionTokens"]);self.assertIsNone(result["ttftSeconds"])
                    self.assertEqual(result["interrupted"],kind in {"upstream-interrupted","browser-disconnected"})
                if kind in {"oversized","upstream-interrupted","browser-disconnected"}:self.assertEqual(loads.call_count,0)
                if kind!="browser-disconnected":self.assertEqual(output.bytes,wire)
                self.assertNotIn(b"launcher.stream_error",output.bytes,"Non-SSE response bytes stay authoritative")

    def test_browser_header_disconnect_closes_upstream_without_reading_and_records_interruption(self):
        request=launcher.urllib.request.Request('http://127.0.0.1:18887/fixture')
        context={'ownerRunId':'generated-owner','attachmentId':'generated-surface'}
        request._launcher_cache_context=context
        for name in ('send_response','send_header','end_headers','set_close_connection'):
            with self.subTest(output=name):
                records=[];domain=service(observations=records)
                response=Response(chat_events());out=Output()
                with mock.patch.object(out,name,side_effect=BrokenPipeError('generated early disconnect')), \
                        mock.patch.object(response,'readline',side_effect=AssertionError('Disconnected browser must not drain upstream')):
                    timed(domain.stream_chat,response,request,out.port())
                self.assertTrue(response.closed)
                self.assertEqual(out.bytes,b'')
                self.assertEqual(len(records),1)
                self.assertEqual(records[0][0],context)
                observation=records[0][1]
                self.assertFalse(observation['completed'])
                self.assertTrue(observation['interrupted'])
                self.assertFalse(observation['outputObserved'])
                self.assertIsNone(observation['completionTokens'])

    def test_full_relay_preserves_bytes_headers_observations_and_disconnect_states(self):
        request=launcher.urllib.request.Request('http://127.0.0.1:18887/fixture')
        request._launcher_cache_context={'ownerRunId':'generated-owner','attachmentId':'generated-surface'}
        for kind in ('complete','truncated','unexpected-eof','upstream-error','browser-disconnect','json'):
            with self.subTest(kind=kind):
                records=[];domain=service(observations=records);outputs=[];observations=[]
                terminal='length' if kind=='truncated' else None if kind in {'unexpected-eof','upstream-error'} else 'stop'
                for frozen in (True,False):
                    out=Output(disconnect=kind=='browser-disconnect')
                    if kind=='json':
                        response=Response(content_type='application/json',raw=json.dumps({'choices':[{'message':{'content':'Generated answer'},'finish_reason':'stop'}],
                            'usage':{'prompt_tokens':120,'completion_tokens':32}}).encode())
                    else:response=Response(chat_events(terminal=terminal),read_error=kind=='upstream-error')
                    if frozen:
                        receiver=legacy.FrozenChatRelay()
                        for name in ('send_response','send_header','end_headers','wfile'):setattr(receiver,name,getattr(out,name))
                        recorder=mock.Mock()
                        with mock.patch.object(legacy,'MANAGER',recorder):timed(receiver.stream_chat,response,request)
                        observations.append(recorder.record_chat_cache_observation.call_args.args)
                        out.closed=receiver.close_connection
                    else:
                        timed(domain.stream_chat,response,request,out.port());observations.append(records[-1])
                    self.assertTrue(response.closed);outputs.append((out.status,out.headers,bytes(out.bytes),out.closed))
                self.assertEqual(outputs[0],outputs[1]);self.assertEqual(observations[0],observations[1])
                if kind in {'unexpected-eof','upstream-error'}:self.assertIn(b'launcher.stream_error',outputs[1][2])
                else:self.assertNotIn(b'launcher.stream_error',outputs[1][2])
                if kind=='complete':self.assertTrue(observations[1][1]['completed'])


SERVER=r'''
import json,sys
from http.server import BaseHTTPRequestHandler,HTTPServer
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_POST(self):
  body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  if self.headers.get('Authorization')!='Bearer fixture-engine-key' or body.get('model')!='generated-served':
   self.send_error(401);return
  if any(message.get('content')=='Generated pretty JSON fixture' for message in body.get('messages',[])):
   value={'choices':[{'message':{'content':'Generated buffered answer'},'finish_reason':'stop'}],
          'usage':{'prompt_tokens':120,'completion_tokens':32,'prompt_tokens_details':{'cached_tokens':80}}}
   wire=json.dumps(value,indent=2).encode()
   self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(wire)));self.end_headers()
   self.wfile.write(wire);self.wfile.flush();return
  self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
  tool=bool(body.get('tools'))
  usage={'prompt_tokens':120,'completion_tokens':32}
  if tool:
   output={'tool_calls':[{'index':0,'id':'generated-call','type':'function','function':{
     'name':'launcher_route_check','arguments':'{"status":"ready"}'}}]}
  else:output={'content':'Generated answer'}
  values=[{'choices':[{'index':0,'delta':output}]},{'choices':[{'index':0,'delta':{},'finish_reason':'tool_calls' if tool else 'stop'}],'usage':usage}]
  for value in values:self.wfile.write(b'data: '+json.dumps(value).encode()+b'\n\n');self.wfile.flush()
  self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
server=HTTPServer(('127.0.0.1',0),Handler)
print(server.server_port,flush=True);server.serve_forever()
'''


class LiveGeneratedHTTPTests(unittest.TestCase):
    def test_real_http_chat_benchmark_and_tool_probe_use_only_fixture_owned_server(self):
        with tempfile.TemporaryDirectory(prefix='inference-http-fixture-') as directory:
            script=Path(directory)/'server.py';script.write_text(SERVER)
            child=subprocess.Popen([sys.executable,'-u',str(script)],start_new_session=True,
                stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                self.assertTrue(select.select([child.stdout],[],[],5)[0],'Fixture did not announce readiness')
                line=child.stdout.readline()
                if not line: self.fail('Generated localhost fixture failed: '+child.stderr.read(1000))
                port=int(line);domain=service();item=plan(port=port,client_port=None)
                item.secrets.pop('clientApiKey')
                benchmark=domain.run_benchmark_completion(item,'Generated fixture',64,{},threading.Event())
                self.assertEqual(benchmark['completionTokens'],32);self.assertTrue(benchmark['terminalComplete'])
                item.client='pi'
                tool=domain.run_route_check_request(item,threading.Event(),tool_probe=True)
                self.assertTrue(tool['toolContractValid']);self.assertTrue(tool['terminalComplete'])
                item.client='chat';observations=[];domain=service(observations=observations)
                request=domain.build_chat_completion_request(item,{'messages':[{'role':'user','content':'Generated fixture'}]})
                request._launcher_cache_context={'ownerRunId':'generated-owner','attachmentId':'generated-surface'}
                output=Output();domain.stream_chat(request,output.port())
                self.assertEqual(int(output.status),200);self.assertIn(b'Generated answer',output.bytes)
                self.assertTrue(observations[-1][1]['completed']);self.assertEqual(observations[-1][1]['completionTokens'],32)
                request=domain.build_chat_completion_request(item,{'messages':[{'role':'user','content':'Generated pretty JSON fixture'}]})
                request._launcher_cache_context={'ownerRunId':'generated-owner','attachmentId':'generated-surface'}
                buffered=Output();domain.stream_chat(request,buffered.port())
                self.assertEqual(json.loads(buffered.bytes)['choices'][0]['message']['content'],'Generated buffered answer')
                self.assertIn(b'\n',buffered.bytes)
                self.assertTrue(observations[-1][1]['completed']);self.assertFalse(observations[-1][1]['interrupted'])
                self.assertEqual(observations[-1][1]['cachedPromptTokens'],80)
            finally:
                # Exactly this captured fresh fixture session is eligible.
                if child.poll() is None:
                    os.killpg(child.pid,signal.SIGTERM)
                    try:child.wait(timeout=3)
                    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=3)
                child.stdout.close();child.stderr.close()


if __name__=='__main__':unittest.main()

class OwnedRouteOpenerTests(unittest.TestCase):
    def test_default_and_injected_route_opener_preserve_wire_arguments_closure_and_proof(self):
        class Response(io.BytesIO):
            def __init__(self):
                super().__init__(json.dumps({'id':'generated-response','choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':'Generated complete reply'}}],
                    'usage':{'prompt_tokens':12,'completion_tokens':4}}).encode())
                self.headers={'Content-Type':'application/json'}
        results=[];calls=[]
        for injected in (False,True):
            response=Response();value=plan();requests=service()
            def opener(request,timeout):calls.append((request_shape(request),timeout));return response
            with mock.patch.object(inference.urllib.request,'urlopen',side_effect=AssertionError('Injected opener bypassed') if injected else opener):
                result=requests.run_route_check_request(value,threading.Event(),opener=opener if injected else None)
            self.assertTrue(response.closed);self.assertTrue(result['terminalComplete']);self.assertTrue(result['usage']['available'])
            self.assertEqual(result['usage']['completionTokens'],4);results.append(result)
        self.assertEqual(calls[0],calls[1]);self.assertEqual(calls[0][1],900)
        self.assertEqual(calls[0][0][3]['Authorization'],'Bearer fixture-engine-key')
        for result in results:
            result.pop('firstOutputSeconds',None);result.pop('totalSeconds',None)
        self.assertEqual(results[0],results[1])
