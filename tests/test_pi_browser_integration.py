"""Real installed Pi calling the private browser tool; generated local SSE, no model."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

import launcher


@unittest.skipUnless(os.environ.get("LLM_LAUNCHER_PI_INTEGRATION") == "1", "opt-in Pi browser integration")
class PiBrowserIntegration(unittest.TestCase):
    def test_vision_screenshots_reach_native_provider_as_images(self):
        observed = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass

            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(b'''<title>Vision browser fixture</title>
                    <canvas id="stage" width="1800" height="400" style="display:block"></canvas>
                    <script>const ctx=document.querySelector('canvas').getContext('2d');
                    ctx.fillStyle='red';ctx.fillRect(0,0,900,400);
                    ctx.fillStyle='blue';ctx.fillRect(900,0,900,400);</script>''')

            def do_POST(self):
                observed.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                actions = [
                    {'action':'open', 'url':f'http://127.0.0.1:{self.server.server_port}/'},
                    {'action':'screenshot', 'selector':'#stage'},
                    {'action':'sequence', 'steps':[
                        {'action':'screenshot', 'selector':'#stage'}, {'action':'close'},
                    ]},
                ]
                step = len(observed)
                delta, finish = {'content':'Vision fixture completed.'}, 'stop'
                if step <= len(actions):
                    delta = {'tool_calls':[{'index':0, 'id':f'vision-{step}', 'type':'function',
                        'function':{'name':'browser_check', 'arguments':json.dumps(actions[step - 1])}}]}
                    finish = 'tool_calls'
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Connection', 'close')
                self.end_headers()
                self.close_connection = True
                for part, stop in [({'role':'assistant'}, None), (delta, None), ({}, finish)]:
                    frame = {'id':'vision-test', 'choices':[{'index':0,'delta':part,'finish_reason':stop}]}
                    self.wfile.write(('data: '+json.dumps(frame)+'\n\n').encode())
                self.wfile.write(b'data: [DONE]\n\n')

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory(prefix='pi-native-vision-') as directory:
                root = Path(directory)
                config = root / 'config'
                config.mkdir()
                plan = launcher.LaunchPlan(run_id='pi-vision-native', backend='mtplx', client='pi',
                    model={'name':'Vision fixture','id':'vision-fixture','backends':{}},
                    project=str(root), context=8192, output=2048, reasoning='medium',
                    port=server.server_port, mode='ar', options={}, agent_host='terminal')
                with mock.patch.dict(launcher.BINARIES, {'pi':shutil.which('pi')}):
                    launcher.build_pi_client(plan, launcher.ClientRoute('fixture','vision-fixture',
                        f'http://127.0.0.1:{server.server_port}/v1','fixture'))
                provider = json.loads(plan.client_env['LLM_LAUNCHER_PI_PROVIDER'])
                self.assertIn('browserTestModule', provider)
                provider['browserArtifactDir'] = str(root / 'screenshots')
                # This generated provider accepts images. Production capability
                # qualification is tested separately in test_model_modalities.
                provider['model']['input'] = ['text', 'image']
                plan.client_env['LLM_LAUNCHER_PI_PROVIDER'] = json.dumps(provider)
                command = plan.client_argv + ['--mode','json','--print','--no-session','--tools','browser_check',
                    '--no-extensions','--no-skills','--no-prompt-templates','--no-themes','--no-context-files',
                    '--no-approve','--offline','--system-prompt','Local generated vision fixture.', 'Inspect the fixture image.']
                result = subprocess.run(command, cwd=root, env={**os.environ, **plan.client_env,
                    'PI_CODING_AGENT_DIR':str(config), 'PI_CODING_AGENT_SESSION_DIR':str(root / 'sessions'),
                    'PI_OFFLINE':'1', 'PI_TELEMETRY':'0'}, capture_output=True, text=True, timeout=45)
                self.assertEqual(result.returncode, 0, result.stderr[-3000:])
                self.assertEqual(len(observed), 4, result.stdout[-3000:])
                def images(body):
                    return [part for message in body['messages']
                        if isinstance(message.get('content'), list)
                        for part in message['content'] if part.get('type') == 'image_url']
                self.assertFalse(images(observed[0]))
                self.assertEqual(len(images(observed[2])), 1,
                    'Native Pi must expose ctx.model.input and encode the tool image into the next provider request')
                self.assertEqual(len(images(observed[3])), 2,
                    'Sequence aggregation must preserve its screenshot image through native Pi conversion')
                for part in images(observed[3]):
                    self.assertTrue(part['image_url']['url'].startswith('data:image/jpeg;base64,'))
                    self.assertLess(len(part['image_url']['url']), 3 * 1024 ** 2)
                tool_messages = [message for message in observed[-1]['messages'] if message['role'] == 'tool']
                self.assertEqual(len(tool_messages), 3)
                self.assertEqual(json.loads(tool_messages[0]['content'])['evidence'],
                    {'kind':'runtime','imageDelivered':False})
                screenshot = json.loads(tool_messages[1]['content'].split('\n')[0])
                self.assertEqual(screenshot['visualFeedback'], 'image')
                self.assertEqual(screenshot['evidence'], {'kind':'visual-model','imageDelivered':True})
                self.assertEqual((screenshot['imageWidth'], screenshot['imageHeight']), (1280, 284))
                original = Path(screenshot['path']).read_bytes()
                self.assertEqual((int.from_bytes(original[16:20], 'big'), int.from_bytes(original[20:24], 'big')), (1800,400))
                vision_sequence = json.loads(tool_messages[2]['content'])
                self.assertEqual(vision_sequence['evidence'], {'kind':'sequence','imageDelivered':True})
                self.assertEqual(vision_sequence['results'][0]['evidence'],
                    {'kind':'visual-model','imageDelivered':True})
                self.assertEqual(vision_sequence['results'][1]['evidence'], {'kind':'runtime','imageDelivered':False})
                events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
                completed = [event['message'] for event in events
                    if event.get('type') == 'message_end' and event.get('message', {}).get('role') == 'toolResult']
                self.assertEqual([message['isError'] for message in completed], [False, False, False])
                self.assertEqual([block['type'] for block in completed[1]['content']], ['text','image'])
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_native_tool_schema_execution_and_shutdown(self):
        observed = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b'''<title>Native Pi browser</title><button onclick="requestAnimationFrame(()=>this.textContent='Measured')">Check</button>
                    <canvas id="stage" width="320" height="200" style="display:block"></canvas>
                    <script>
                    const art=document.querySelector('#stage').getContext('2d'); art.fillStyle='#48a8ee'; art.fillRect(0,0,320,200);
                    window.inputEvents=[]; window.position=0; window.jumps=0; window.running=false; window.rightHeld=false;
                    addEventListener('keydown', event => {
                        inputEvents.push({type:event.type,key:event.key,trusted:event.isTrusted});
                        if (event.key === 'Enter') requestAnimationFrame(()=>requestAnimationFrame(()=>{running=true;}));
                        if (event.key === 'ArrowRight') rightHeld=true;
                        if (event.key === ' ' && running) jumps++;
                    });
                    addEventListener('keyup', event => {
                        inputEvents.push({type:event.type,key:event.key,trusted:event.isTrusted});
                        if (event.key === 'ArrowRight') rightHeld=false;
                    });
                    setInterval(() => {
                        if (running && rightHeld) position++;
                        art.fillStyle='#48a8ee'; art.fillRect(0,0,320,200);
                        art.fillStyle='#e84838'; art.fillRect(10+position%290,jumps?100:150,16,24);
                    }, 10);
                    </script>''')

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                observed.append(body)
                step = len(observed)
                open_page = {"action":"open", "url":f"http://127.0.0.1:{self.server.server_port}/"}
                actions = [
                    open_page,
                    {"action":"evaluate", "script":"(() => { throw new Error('Deliberate browser assertion failure: ' + 'x'.repeat(12000)) })()"},
                    {"action":"click", "selector":"button", "wait_for":"document.querySelector('button').textContent === 'Measured'"},
                    {"action":"evaluate", "script":"({label:document.querySelector('button').textContent})"},
                    {"action":"close"},
                    {"action":"sequence", "steps":[
                        open_page,
                        {"action":"press", "key":"Enter", "wait_for":"running === true"},
                        {"action":"evaluate", "script":"({position,running,inputEvents})"},
                        {"action":"press", "key":"ArrowRight", "hold_ms":150},
                        {"action":"evaluate", "script":"({position,running,rightHeld,inputEvents})"},
                        {"action":"close"},
                    ]},
                    {"action":"sequence", "steps":[
                        open_page,
                        {"action":"evaluate", "script":"window.afterFailure=0"},
                        {"action":"evaluate", "script":"(() => { throw new Error('Deliberate sequence failure') })()"},
                        {"action":"evaluate", "script":"window.afterFailure=1"},
                    ]},
                    {"action":"evaluate", "script":"window.afterFailure"},
                    {"action":"sequence", "steps":[
                        {"action":"evaluate", "script":"window.afterFailure=99"},
                        {"action":"fill", "selector":"input"},
                    ]},
                    {"action":"evaluate", "script":"window.afterFailure"},
                    {"action":"sequence", "steps":[
                        {"action":"resize", "width":390, "height":844},
                        {"action":"evaluate", "script":"({width:innerWidth,height:innerHeight,mobile:matchMedia('(max-width: 400px)').matches})"},
                        {"action":"resize", "width":1280, "height":800},
                        {"action":"screenshot", "selector":"#stage"},
                    ]},
                    {"action":"sequence", "steps":[
                        open_page,
                        {"action":"press", "key":"Enter", "wait_for":"running === true"},
                        {"action":"evaluate", "script":"({position,jumps,running})"},
                        {"action":"press", "key":"ArrowRight", "hold_ms":150},
                        {"action":"press", "key":"Space", "hold_ms":50},
                        {"action":"evaluate", "script":"({position,jumps,running,inputEvents})"},
                        {"action":"screenshot", "selector":"#stage"},
                        {"action":"inspect"},
                        {"action":"close"},
                    ]},
                    {"action":"close"},
                ]
                delta = {"content":"Browser fixture completed."}
                finish = "stop"
                if step <= len(actions):
                    delta = {"tool_calls":[{"index":0,"id":f"browser-{step}","type":"function",
                        "function":{"name":"browser_check", "arguments":json.dumps(actions[step-1])}}]}
                    finish = "tool_calls"
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Connection', 'close')
                self.end_headers()
                self.close_connection = True
                for frame in ({'role':'assistant'}, delta):
                    data = {'id':'browser-test', 'choices':[{'index':0,'delta':frame,'finish_reason':None}]}
                    self.wfile.write(('data: '+json.dumps(data)+'\n\n').encode())
                self.wfile.write(('data: '+json.dumps({'id':'browser-test','choices':[{'index':0,'delta':{},'finish_reason':finish}]})+'\n\ndata: [DONE]\n\n').encode())

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory(prefix='pi-native-browser-') as directory:
                root = Path(directory)
                config = root / 'config'
                config.mkdir()
                plan = launcher.LaunchPlan(run_id='pi-browser-native', backend='omlx', client='pi',
                    model={'name':'Browser fixture','id':'browser-fixture','backends':{}},
                    project=str(root), context=8192, output=2048, reasoning='medium',
                    port=server.server_port, mode='ar', options={}, agent_host='terminal')
                with mock.patch.dict(launcher.BINARIES, {'pi':shutil.which('pi')}):
                    launcher.build_pi_client(plan, launcher.ClientRoute('fixture','browser-fixture',
                        f'http://127.0.0.1:{server.server_port}/v1','fixture'))
                provider = json.loads(plan.client_env['LLM_LAUNCHER_PI_PROVIDER'])
                self.assertIn('browserTestModule', provider)
                provider['browserArtifactDir'] = str(root / 'screenshots')
                plan.client_env['LLM_LAUNCHER_PI_PROVIDER'] = json.dumps(provider)
                command = plan.client_argv + ['--mode','json','--print','--no-session','--tools','browser_check',
                    '--no-extensions','--no-skills','--no-prompt-templates','--no-themes','--no-context-files',
                    '--no-approve','--offline','--system-prompt','Local generated browser fixture.', 'Run browser fixture.']
                result = subprocess.run(command, cwd=root, env={**os.environ, **plan.client_env,
                    'PI_CODING_AGENT_DIR':str(config), 'PI_CODING_AGENT_SESSION_DIR':str(root / 'sessions'),
                    'PI_OFFLINE':'1', 'PI_TELEMETRY':'0'}, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr[-3000:])
                self.assertEqual(len(observed), 14, result.stdout[-3000:])
                self.assertEqual([t['function']['name'] for t in observed[0]['tools']], ['browser_check'])
                browser_schema = observed[0]['tools'][0]['function']['parameters']
                self.assertIn('anyOf', browser_schema)
                self.assertIn('anyOf', browser_schema['properties']['steps']['items'])
                tool_messages = [m for m in observed[-1]['messages'] if m['role'] == 'tool']
                self.assertEqual(len(tool_messages), 13)
                opened = json.loads(tool_messages[0]['content'])
                self.assertEqual(opened['title'], 'Native Pi browser')
                self.assertEqual(opened['canvases'][0]['selector'], '#stage')
                self.assertEqual(opened['evidence'], {'kind':'runtime','imageDelivered':False})
                self.assertIn('Deliberate browser assertion failure', tool_messages[1]['content'])
                self.assertLessEqual(len(tool_messages[1]['content']), 2000)
                self.assertIn('[truncated]', tool_messages[1]['content'])
                measured = json.loads(tool_messages[3]['content'])
                self.assertEqual(measured['result'], {'label':'Measured'})
                self.assertEqual(measured['evidence'], {'kind':'runtime','imageDelivered':False})
                self.assertIn('pixel diagnostics do not verify visual appearance', measured['note'])
                self.assertEqual(json.loads(tool_messages[2]['content'])['postcondition'],'satisfied')
                self.assertTrue(json.loads(tool_messages[4]['content'])['closed'])
                sequence_payload = json.loads(tool_messages[5]['content'])
                self.assertEqual(sequence_payload['evidence'], {'kind':'sequence','imageDelivered':False})
                sequence = sequence_payload['results']
                self.assertEqual(len(sequence), 6)
                self.assertTrue(all(step['evidence']['kind'] == 'runtime' for step in sequence))
                self.assertEqual(sequence[2]['result'], {'position':0, 'running':True, 'inputEvents':[
                    {'type':'keydown', 'key':'Enter', 'trusted':True},
                    {'type':'keyup', 'key':'Enter', 'trusted':True},
                ]})
                self.assertGreater(sequence[4]['result']['position'], 0)
                self.assertFalse(sequence[4]['result']['rightHeld'])
                self.assertEqual(sequence[4]['result']['inputEvents'], [
                    {'type':'keydown', 'key':'Enter', 'trusted':True},
                    {'type':'keyup', 'key':'Enter', 'trusted':True},
                    {'type':'keydown', 'key':'ArrowRight', 'trusted':True},
                    {'type':'keyup', 'key':'ArrowRight', 'trusted':True},
                ])
                self.assertTrue(sequence[5]['closed'])
                self.assertIn('step 3 (evaluate) failed:', tool_messages[6]['content'])
                self.assertIn('Deliberate sequence failure', tool_messages[6]['content'])
                self.assertEqual(json.loads(tool_messages[7]['content'])['result'], 0,
                    'The failed sequence must not execute its later mutation')
                self.assertIn('Validation failed', tool_messages[8]['content'])
                self.assertIn('text', tool_messages[8]['content'])
                self.assertEqual(json.loads(tool_messages[9]['content'])['result'], 0,
                    'Pi must validate every sequence action before an earlier step mutates the page')
                responsive_payload = json.loads(tool_messages[10]['content'])
                self.assertEqual(responsive_payload['evidence'], {'kind':'sequence','imageDelivered':False})
                responsive = responsive_payload['results']
                self.assertEqual(responsive[0]['viewport'], {'width':390,'height':844,'devicePixelRatio':1})
                self.assertEqual(responsive[1]['result'], {'width':390,'height':844,'mobile':True})
                self.assertEqual(responsive[2]['viewport'], {'width':1280,'height':800,'devicePixelRatio':1})
                screenshot = responsive[3]
                self.assertTrue(screenshot['saved'])
                self.assertEqual(screenshot['evidence'], {'kind':'human-review','imageDelivered':False})
                self.assertIn('cannot see screenshot pixels', screenshot['note'])
                self.assertEqual(Path(screenshot['path']).parent, root / 'screenshots')
                png = Path(screenshot['path']).read_bytes()
                self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
                self.assertEqual((int.from_bytes(png[16:20], 'big'), int.from_bytes(png[20:24], 'big')), (320,200))
                gameplay_payload = json.loads(tool_messages[11]['content'])
                self.assertEqual(gameplay_payload['evidence'], {'kind':'sequence','imageDelivered':False})
                gameplay = gameplay_payload['results']
                self.assertEqual(len(gameplay),9)
                self.assertEqual(gameplay[1]['postcondition'],'satisfied')
                self.assertEqual(gameplay[2]['result'], {'position':0,'jumps':0,'running':True})
                self.assertGreater(gameplay[5]['result']['position'],0)
                self.assertEqual(gameplay[5]['result']['jumps'],1)
                self.assertTrue(gameplay[5]['result']['running'])
                self.assertEqual([(e['type'],e['key'],e['trusted']) for e in gameplay[5]['result']['inputEvents']], [
                    ('keydown','Enter',True),('keyup','Enter',True),
                    ('keydown','ArrowRight',True),('keyup','ArrowRight',True),
                    ('keydown',' ',True),('keyup',' ',True),
                ])
                self.assertTrue(Path(gameplay[6]['path']).is_file())
                self.assertEqual(gameplay[6]['evidence'], {'kind':'human-review','imageDelivered':False})
                self.assertEqual(gameplay[7]['canvases'][0]['selector'],'#stage')
                self.assertTrue(gameplay[8]['closed'])
                self.assertTrue(json.loads(tool_messages[12]['content'])['closed'])
                events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
                completed = [event['message'] for event in events
                    if event.get('type') == 'message_end' and event.get('message', {}).get('role') == 'toolResult']
                self.assertEqual([message['isError'] for message in completed], [False, True, False, False, False, False, True, False, True, False, False, False, False],
                    'Pi must record a failed assertion as an error while allowing subsequent checks')
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)
