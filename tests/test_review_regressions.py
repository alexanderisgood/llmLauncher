"""Reproduce the September external review findings without loading models."""
import copy
import http.client
import json
import socket
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest import mock

import launcher
import session_proxy as relay
from sse_framing import ResponseOutcome
from responses_bridge import ChatStreamBridge


class OutcomeTests(unittest.TestCase):
    def test_split_frames_and_failure_dominance(self):
        for protocol, value in (
            ('chat-completions', {'choices':[{'finish_reason':'tool_calls'}]}),
            ('responses', {'type':'response.completed','response':{'status':'completed'}}),
        ):
            payload = b'data: ' + json.dumps(value).encode() + b'\r\n\r\ndata: [DONE]\r\n\r\n'
            for split in range(len(payload)+1):
                outcome=ResponseOutcome(protocol,True)
                outcome.feed(payload[:split]); outcome.feed(payload[split:])
                self.assertEqual(outcome.finish(),'completed',split)
            failed=ResponseOutcome(protocol,True)
            failed.feed(payload+b'data: {"error":{"message":"failed"}}\n\n')
            self.assertEqual(failed.finish(),'upstream-error')

    def test_responses_bridge_does_not_turn_done_or_eof_into_completion(self):
        for tail in (b'',b'data: [DONE]\n\n',b'data: [DONE]'):
            bridge=ChatStreamBridge(SimpleNamespace(model='model',output_limit=100,by_wire_name={}))
            wire=bridge.feed(b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'+tail)+bridge.finish()
            self.assertIn(b'response.failed',wire)
            self.assertNotIn(b'response.completed',wire)

    def test_eof_done_and_malformed_are_not_success(self):
        for payload in (b'data: [DONE]\n\n', b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n',
                        b'data: {"choices":[{"finish_reason":"stop"}]}',
                        b'data: broken\n\ndata: {"choices":[{"finish_reason":"stop"}]}\n\n'):
            outcome=ResponseOutcome('chat-completions',True)
            outcome.feed(payload)
            self.assertEqual(outcome.finish(),'incomplete-stream')

    def test_oversized_multiline_and_json(self):
        outcome=ResponseOutcome('chat-completions',True,100)
        for _ in range(20):
            outcome.feed(b'x'*100)
            self.assertLessEqual(len(outcome.buffer),100)
        outcome.feed(b'\n\ndata: {"choices":[{"finish_reason":"stop"}]}\n\n')
        self.assertEqual(outcome.finish(),'incomplete-stream')
        outcome=ResponseOutcome('chat-completions',True)
        outcome.feed(b'data: {"choices":\ndata: [{"finish_reason":"length"}]}\n\n')
        self.assertEqual(outcome.finish(),'truncated')
        outcome=ResponseOutcome('chat-completions',False)
        outcome.feed(b'{"choices":[{"finish_reason":"stop"}]}')
        self.assertEqual(outcome.finish(),'completed')


class WatchdogTests(unittest.TestCase):
    def test_every_owned_adapter_stops_on_telemetry_exception(self):
        for backend in ('slotstream','uzu','whallm'):
            for helper in ('darwin_process_group_physical_footprint','apple_memory_pressure_state'):
                with self.subTest(backend=backend,helper=helper):
                    manager=launcher.RunManager()
                    plan=SimpleNamespace(backend=backend,model={'nativeWhallm':backend=='whallm'})
                    process=mock.Mock(pid=999998); process.poll.return_value=None
                    manager.plan=plan;manager.process=process
                    cancel=threading.Event();order=[]
                    sample={'processGroupFootprintAvailable':True,'processGroupMemberCount':1,
                            'processGroupPhysicalFootprintBytes':1,'processGroupLifetimePeakPhysicalFootprintBytes':1}
                    with mock.patch.object(launcher.os,'getpgid',return_value=999998), \
                         mock.patch.object(launcher,'darwin_process_group_physical_footprint',return_value=sample), \
                         mock.patch.object(launcher,helper,side_effect=RuntimeError('telemetry')), \
                         mock.patch.object(manager,'_terminate_process',side_effect=lambda *_:order.append('engine')), \
                         mock.patch.object(manager,'_stop_owned',side_effect=lambda *_:order.append('cleanup')):
                        manager._guard_owned_memory(plan,process,cancel,backend,100)
                    self.assertEqual(order,['engine','cleanup'])
                    self.assertTrue(cancel.is_set());self.assertEqual(manager.state['phase'],'failed')

    def test_monitor_stops_engine_when_guard_disappears(self):
        manager=launcher.RunManager()
        plan=SimpleNamespace(backend='slotstream',model={},secrets={},purpose='session')
        process=mock.Mock();process.poll.return_value=None
        manager.plan=plan;manager.process=process;manager.state['phase']='running'
        cancel=mock.Mock();cancel.wait.return_value=False;cancel.is_set.return_value=False
        order=[]
        with mock.patch.object(manager,'_terminate_process',side_effect=lambda *_:order.append('engine')), \
             mock.patch.object(manager,'_stop_owned',side_effect=lambda *_:order.append('cleanup')):
            manager._monitor_run(plan,cancel)
        self.assertEqual(order,['engine','cleanup'])
        self.assertEqual(manager.state['phase'],'failed')
        cancel.set.assert_called_once()

    def test_stale_guard_cannot_stop_replacement(self):
        manager=launcher.RunManager();old=SimpleNamespace(model={})
        process=mock.Mock(pid=999998);process.poll.return_value=None
        manager.plan=object();manager.process=mock.Mock();cancel=threading.Event()
        with mock.patch.object(launcher.os,'getpgid',return_value=999998), \
             mock.patch.object(launcher,'darwin_process_group_physical_footprint',side_effect=RuntimeError()), \
             mock.patch.object(manager,'_terminate_process') as terminate, \
             mock.patch.object(manager,'_stop_owned') as stop:
            manager._guard_owned_memory(old,process,cancel,'Slotstream',100)
        terminate.assert_not_called();stop.assert_not_called();self.assertFalse(cancel.is_set())


class RelayIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.payload=b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
        self.calls=0
        owner=self
        class Upstream(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                owner.calls+=1
                self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
                self.wfile.write(owner.payload)
        self.upstream=ThreadingHTTPServer(('127.0.0.1',0),Upstream)
        self.server=relay.RelayHTTPServer(('127.0.0.1',0),relay.ProxyHandler)
        self.surface={'id':'f14f5d63-9df1-4693-9558-d4348a250f4f','client':'chat','key':'surface-key-for-tests'}
        self.surface.update(samplingContract={"schemaVersion":1,"controlled":True,"mode":"model","values":{}},
                            samplingEnforcement={"protocol":"chat-completions","representableFields":[],"implicitModelDefaults":False})
        self.server.config={'backend':'slotstream','upstreamPort':self.upstream.server_port,
                            'upstreamKey':'upstream-key-tests','controlKey':'control-key-for-tests',
                            'outputLimit':1024,'reasoning':'medium','servedModel':'model'}
        self.server.registry=relay.SurfaceRegistry([self.surface])
        self.server.scheduler=relay.RequestScheduler(1)
        self.server.scheduler.ingress=relay.IngressBudget(4096,2)
        self.threads=[]
        for server in (self.upstream,self.server):
            server.daemon_threads=True
            thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.02},daemon=True)
            thread.start();self.threads.append(thread)
        self.connections=[]

    def tearDown(self):
        for connection in self.connections:connection.close()
        for server in (self.server,self.upstream):server.shutdown();server.server_close()
        for thread in self.threads:thread.join(1)

    def request(self,body=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=2)
        self.connections.append(connection)
        connection.request('POST','/v1/chat/completions',body=body or json.dumps({
            'model':'model','messages':[{'role':'user','content':'hello'}],'stream':True,'max_tokens':100}),
            headers={'Authorization':'Bearer '+self.surface['key'],'Content-Type':'application/json'})
        response=connection.getresponse();payload=response.read()
        return response.status,payload

    def wait_for(self,predicate):
        deadline=time.monotonic()+2
        while not predicate() and time.monotonic()<deadline:time.sleep(.01)
        self.assertTrue(predicate())

    def test_partial_stream_not_recorded_success_and_valid_tools_still_work(self):
        self.assertEqual(self.request()[0],200)
        self.wait_for(lambda:bool(self.server.scheduler.recent))
        self.assertEqual(self.server.scheduler.recent[-1]['result'],'incomplete-stream')
        self.payload=b'data: {"choices":[{"finish_reason":"tool_calls"}]}\n\ndata: [DONE]\n\n'
        self.assertEqual(self.request()[0],200)
        self.wait_for(lambda:len(self.server.scheduler.recent)==2)
        self.assertEqual(self.server.scheduler.recent[-1]['result'],'completed')

    def test_body_lease_released_on_invalid_json_and_aggregate_refusal(self):
        budget=self.server.scheduler.ingress
        self.assertTrue(budget.acquire(4096))
        self.assertEqual(self.request()[0],429);self.assertEqual(self.calls,0)
        budget.release(4096)
        self.assertEqual(self.request('invalid-json')[0],400)
        self.wait_for(lambda:budget.requests==0)
        self.assertEqual(budget.bytes,0)
        self.assertEqual(self.request()[0],200)

    def test_slow_upload_has_absolute_deadline_and_releases_lease(self):
        with mock.patch.object(relay,'INPUT_DEADLINE_SECONDS',.15):
            client=socket.create_connection(('127.0.0.1',self.server.server_port),timeout=2)
            self.connections.append(client)
            client.sendall(b'POST /v1/chat/completions HTTP/1.0\r\nAuthorization: Bearer surface-key-for-tests\r\nContent-Length: 100\r\n\r\nx')
            self.assertIn(b'408',client.recv(4096))
            self.wait_for(lambda:self.server.scheduler.ingress.requests==0)
            self.assertEqual(self.calls,0)

    def test_concurrent_uploads_reject_before_allocating_another_body(self):
        clients=[]
        for _ in range(2):
            client=socket.create_connection(('127.0.0.1',self.server.server_port),timeout=2)
            self.connections.append(client);clients.append(client)
            client.sendall(b'POST /v1/chat/completions HTTP/1.0\r\nAuthorization: Bearer surface-key-for-tests\r\nContent-Length: 512\r\n\r\nx')
        self.wait_for(lambda:self.server.scheduler.ingress.requests==2)
        self.assertEqual(self.request()[0],429)
        self.assertEqual(self.server.scheduler.ingress.bytes,1024)
        for client in clients:client.close()
        self.wait_for(lambda:self.server.scheduler.ingress.requests==0)
        self.assertEqual(self.request()[0],200)

    def test_disconnected_queue_entry_reaped_before_lane_opens(self):
        scheduler=self.server.scheduler
        active=scheduler.begin(self.surface,'chat-completions');self.assertTrue(scheduler.await_turn(active))
        client=socket.create_connection(('127.0.0.1',self.server.server_port),timeout=2)
        self.connections.append(client)
        body=json.dumps({'model':'model','messages':[{'role':'user','content':'hello'}],'max_tokens':50}).encode()
        client.sendall(b'POST /v1/chat/completions HTTP/1.0\r\nAuthorization: Bearer surface-key-for-tests\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body)
        self.wait_for(lambda:len(scheduler.queue)==1)
        client.close()
        self.wait_for(lambda:len(scheduler.queue)==0 and scheduler.ingress.requests==0)
        self.assertEqual(self.calls,0)
        self.assertEqual(scheduler.recent[-1]['result'],'client-disconnected')
        scheduler.finish(active,'completed')
        self.assertEqual(self.request()[0],200)


class BenchmarkTimingTests(unittest.TestCase):
    def measure(self, events, ticks, content_type='text/event-stream'):
        class Response:
            headers={'Content-Type':content_type}
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def __iter__(self):return iter(events)
            def read(self,*_):return events[0]
        plan=SimpleNamespace(backend='slotstream',options={})
        with mock.patch.object(launcher.inference_requests.InferenceRequests,'build_benchmark_completion_request',return_value=object()), \
             mock.patch.object(launcher.urllib.request,'urlopen',return_value=Response()), \
             mock.patch.object(launcher.time,'monotonic',side_effect=ticks):
            return launcher.run_benchmark_completion(plan,'test',128,{},threading.Event())

    def test_json_and_single_burst_have_no_decode_score(self):
        data={'choices':[{'message':{'content':'hello'},'finish_reason':'stop'}],
              'usage':{'prompt_tokens':10,'completion_tokens':20}}
        sample=self.measure([json.dumps(data).encode()],[0,2,2.1],'application/json')
        self.assertIsNone(sample['ttftSeconds']);self.assertIsNone(sample['decodeTokensPerSecond'])
        data['choices'][0]['delta']=data['choices'][0].pop('message')
        sample=self.measure([b'data: '+json.dumps(data).encode()+b'\n'],[0,1,2])
        self.assertIsNone(sample['decodeTokensPerSecond'])
        self.assertEqual(sample['terminalState'],'complete')

    def test_real_event_interval_excludes_terminal_transport_delay(self):
        events=[b'data: {"choices":[{"delta":{"content":"a"}}]}\n',
                b'data: {"choices":[{"delta":{"content":"b"},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":21}}\n',
                b'data: [DONE]\n']
        sample=self.measure(events,[0,1,3,10])
        self.assertTrue(sample['decodeTimingValid']);self.assertEqual(sample['decodeTokensPerSecond'],10)
        self.assertEqual(sample['totalSeconds'],10)
        incomplete=[events[0],events[1].replace(b'"stop"',b'null')]
        sample=self.measure(incomplete,[0,1,3,4])
        self.assertFalse(sample['decodeTimingValid']);self.assertIsNone(sample['decodeTokensPerSecond'])
        self.assertEqual(sample['terminalState'],'incomplete')


if __name__=="__main__":unittest.main()
