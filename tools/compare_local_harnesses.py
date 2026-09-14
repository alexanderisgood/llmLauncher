#!/usr/bin/env python3
"""Bounded, serial CLI harness screening against an idle, already-loaded MTPLX.
No engine setting changes; every attempt gets a fresh disposable project/session.
Results are a small coding screen, not a general intelligence benchmark.
The legacy pi-hub argument means Pi CLI with launcher workflow guidance; it
does not exercise Hub RPC. Use verify_pi_hub.py for the actual Hub path.
"""
import argparse
import fcntl
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import launcher
import codex_proxy
import responses_bridge
import session_proxy

ROOT=Path(__file__).resolve().parents[1]
PROMPT='''Fix cache.cjs so TTLCache is a correct capacity-bounded LRU cache with expiry. Capacity must be a positive integer. TTL must be finite and nonnegative; invalid inputs must not mutate state. Expiry is inclusive, TTL zero removes an existing key, get refreshes recency without extending TTL, size excludes expired entries, and expired entries are purged before capacity eviction. Read cache.test.cjs and run node --test cache.test.cjs. Modify only cache.cjs. Preserve every test. Finish when the tests pass; report anything unresolved.'''


def get_status(base):
    return json.load(urllib.request.urlopen(base+'/api/status',timeout=10))


def run_attempt(harness, status, report_dir, timeout, task="cache"):
    if harness == 'pi-hub':
        harness = 'pi-workflow'
    source_name=task+".cjs"; test_name=task+".test.cjs"
    prompt=PROMPT if task=="cache" else "Fix sumRange in range.cjs: sum both endpoints inclusively, including negative and single-value ranges. Descending ranges return zero. Preserve integer validation. Modify only range.cjs, preserve range.test.cjs, run node --test range.test.cjs, and finish when the tests pass."
    run=status['run']; key_path=(Path.home()/'Library/Application Support/LLM Launcher/runs')/run['runId']/'mtplx-api-key'
    # Do not log credentials or reuse the user's project/session.
    upstream_key=key_path.read_text().strip()
    client_key=secrets.token_urlsafe(24)
    stats=[]; errors=[]; affinity='harness-screen-'+secrets.token_hex(12)
    model_request=urllib.request.Request(f"http://127.0.0.1:{run['port']}/v1/models",headers={'Authorization':'Bearer '+upstream_key})
    served=json.load(urllib.request.urlopen(model_request,timeout=10))['data'][0]['id']
    cfg={'backend':'mtplx','servedModel':served,'outputLimit':8192,'reasoning':run['reasoning']}
    class Relay(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_POST(self):
            if self.headers.get('Authorization') != 'Bearer '+client_key:
                self.send_error(403); return
            connection=None
            try:
                if len(stats)>=20: raise ValueError('Screening limit: 20 model requests')
                data=self.rfile.read(int(self.headers['Content-Length']))
                bridge=None
                if self.path=='/v1/responses':
                    req=responses_bridge.translate_responses_request(codex_proxy.transform_response_request(data,cfg),cfg)
                    data=req.body; bridge=responses_bridge.ChatStreamBridge(req)
                else:
                    value=json.loads(data); value['model']=cfg['servedModel']; data=json.dumps(value).encode()
                    data=session_proxy.transform_chat_request(data,cfg)
                value=json.loads(data)
                value.update(temperature=1.0,top_p=.95,top_k=20)
                data,headers=session_proxy.mtplx_launcher_request(json.dumps(value).encode(),{
                    'Authorization':'Bearer '+upstream_key,'Content-Type':'application/json',
                    'x-mtplx-session-id':affinity})
                record={'usage':None,'toolCalls':0,'declaredTools':len(value.get('tools',[])),'answerTail':''}; stats.append(record); calls=set()
                connection=http.client.HTTPConnection('127.0.0.1',run['port'],timeout=timeout)
                connection.request('POST','/v1/chat/completions',data,headers)
                reply=connection.getresponse()
                self.send_response(reply.status);self.send_header('Content-Type',reply.getheader('Content-Type','text/event-stream'));self.end_headers()
                if reply.status!=200:
                    error=reply.read(4000).decode(errors='replace'); errors.append(error);self.wfile.write(error.encode());return
                while line:=reply.readline():
                    if line.startswith(b'data: ') and line.strip()!=b'data: [DONE]':
                        chunk=json.loads(line[6:])
                        if isinstance(chunk.get('usage'),dict):record['usage']=chunk['usage']
                        for choice in chunk.get('choices',[]):
                            record['answerTail']=(record['answerTail']+(choice.get('delta',{}).get('content') or ''))[-1200:]
                            for call in choice.get('delta',{}).get('tool_calls',[]):calls.add(call.get('index',0))
                    out=bridge.feed(line) if bridge else line
                    if out:self.wfile.write(out);self.wfile.flush()
                record['toolCalls']=len(calls)
                if bridge:self.wfile.write(bridge.finish());self.wfile.flush()
            except (BrokenPipeError,ConnectionResetError):pass
            except Exception as exc:
                errors.append(str(exc))
                try:self.send_error(400,str(exc))
                except OSError:pass
            finally:
                if connection:connection.close()
    server=ThreadingHTTPServer(('127.0.0.1',0),Relay); server.daemon_threads=True
    threading.Thread(target=server.serve_forever,daemon=True).start()
    started=time.monotonic(); timed_out=False
    try:
        with tempfile.TemporaryDirectory(prefix='launcher-harness-') as folder:
            root=Path(folder).resolve(); project=root/'project';project.mkdir(); (root/'tmp').mkdir()
            for name in [source_name,test_name]:shutil.copyfile(ROOT/'tests/fixtures/pi-coding'/name,project/name)
            before=hashlib.sha256((project/test_name).read_bytes()).hexdigest()
            env={k:v for k,v in os.environ.items() if k in {'PATH','HOME','USER','SHELL','TMPDIR'}}
            env.update({'XDG_CONFIG_HOME':str(root/'config'),'XDG_DATA_HOME':str(root/'data'),'XDG_CACHE_HOME':str(root/'cache'),
                        'TMPDIR':str(root/'tmp'),'PI_CODING_AGENT_DIR':str(root/'pi'),'PI_OFFLINE':'1','PI_TELEMETRY':'0'})
            model={'id':'screen-model','name':run['model'],'backends':{'mtplx':{'codexReasoning':[run['reasoning']]}}}
            plan=launcher.LaunchPlan(run_id=affinity,backend='mtplx',client='pi' if harness.startswith('pi') else harness,
                model=model,project=str(project),context=32768,output=8192,reasoning=run['reasoning'],port=run['port'],mode='mtp',options={},run_dir=root)
            route=launcher.ClientRoute('local-screen',cfg['servedModel'],f'http://127.0.0.1:{server.server_port}/v1',client_key)
            plan.secrets['clientApiKey']=client_key
            if harness.startswith('pi'):
                launcher.build_pi_client(plan,route)
                args=plan.client_argv+['--mode','json','--print','--no-session','--no-extensions','--no-skills','--no-prompt-templates','--no-themes','--no-context-files','--no-approve','--offline',prompt]
                if harness=='pi-plain':
                    index=args.index(str(ROOT/'pi-workflow.js'));del args[index-1:index+1]
            elif harness=='codex':
                launcher.build_codex_client(plan,route)
                args=[plan.client_argv[0],'exec',*plan.client_argv[1:],'--ignore-user-config','--ephemeral','--skip-git-repo-check','--json','-s','workspace-write',
                      '-c','features.apps=false','-c','features.multi_agent=false',prompt]
            else:
                launcher.build_opencode_client(plan,route)
                overlay=json.loads(plan.client_env['OPENCODE_CONFIG_CONTENT']);overlay.pop('plugin',None)
                overlay['permission']={'*':'deny','read':'allow','edit':'allow','bash':'allow','glob':'allow','grep':'allow','list':'allow'}
                overlay['autoupdate']=False
                plan.client_env['OPENCODE_CONFIG_CONTENT']=json.dumps(overlay)
                args=[launcher.BINARIES['opencode'],'run','--pure','--dir',str(project),'--model',f'{route.provider}/{route.served}','--format','json',prompt]
            env.update(plan.client_env)
            # Model-generated operations can write only their disposable fixture.
            profile=f'(version 1)(allow default)(deny file-write* (require-all (require-not (subpath {json.dumps(str(root))})) (require-not (subpath "/dev"))))(deny network-outbound (require-not (remote ip "localhost:*")))'
            # Codex already sandboxes its model-generated commands. Wrapping
            # its host as well blocks the app-server's own IPC/state startup.
            if harness != 'codex':
                args=['/usr/bin/sandbox-exec','-p',profile,*args]
            with (report_dir/'agent.jsonl').open('w') as output,(report_dir/'stderr.log').open('w') as stderr:
                process=subprocess.Popen(args,cwd=project,env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=stderr,start_new_session=True)
                try:code=process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    timed_out=True;os.killpg(process.pid,signal.SIGTERM)
                    try:code=process.wait(timeout=5)
                    except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);code=process.wait()
            unchanged=hashlib.sha256((project/test_name).read_bytes()).hexdigest()==before
            check=subprocess.run(['node','--test',test_name],cwd=project,capture_output=True,text=True,timeout=15)
            (report_dir/'verification.txt').write_text(check.stdout+check.stderr)
            shutil.copyfile(project/source_name,report_dir/source_name)
            usage=[s['usage'] for s in stats if s['usage'] is not None]
            tokens=sum(u.get('prompt_tokens',0) for u in usage)
            cached=sum((u.get('prompt_tokens_details') or {}).get('cached_tokens',0) for u in usage)
            result={'task':task,'harness':harness,'model':run['model'],'engineOptions':run['options'],'reasoning':run['reasoning'],'responseLimit':8192,'advertisedContext':32768,'elapsedSeconds':round(time.monotonic()-started,2),
                'exitCode':code,'timedOut':timed_out,'testsPassed':check.returncode==0,'testsUnchanged':unchanged,
                'completed':code==0 and not timed_out and check.returncode==0 and unchanged and not errors,
                'requests':len(stats),'requestsWithUsage':len(usage),'usageComplete':len(stats)==len(usage),'toolCalls':sum(s['toolCalls'] for s in stats),
                'inputTokens':tokens,'cachedInputTokens':cached,'freshInputTokens':tokens-cached,
                'outputTokens':sum(u.get('completion_tokens',0) for u in usage),'errors':errors}
            (report_dir/'requests.json').write_text(json.dumps(stats,indent=2))
            (report_dir/'result.json').write_text(json.dumps(result,indent=2))
            return result
    finally:server.shutdown();server.server_close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--controller',default='http://127.0.0.1:17344')
    parser.add_argument('--harnesses',nargs='+',choices=['pi-plain','pi-workflow','pi-hub','codex','opencode'],default=['pi-plain','pi-workflow','codex','opencode'],
        help='CLI harnesses; pi-hub is a legacy alias for pi-workflow, not a Hub RPC test')
    parser.add_argument('--task',choices=['cache','range'],default='cache')
    parser.add_argument('--repeat',type=int,default=1)
    parser.add_argument('--timeout',type=int,default=180)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    lock=open(Path(tempfile.gettempdir())/'llm-launcher-harness-screen.lock','a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('Another harness screen is running; only one may use the engine.')
    for attempt in range(args.repeat):
        for harness in args.harnesses:
            status=get_status(args.controller)
            if status.get('run',{}).get('backend')!='mtplx':raise SystemExit('Load MTPLX first.')
            if (status.get('activity') or {}).get('active') or any(c.get('streaming') or c.get('compacting') for c in status.get('agentConsoles',[])):
                raise SystemExit('Model is busy. Pause the current turn before screening; it stays saved.')
            path=args.output/f'{harness}-{attempt+1}';path.mkdir()
            print(json.dumps(run_attempt(harness,status,path,args.timeout,args.task)),flush=True)
if __name__=='__main__':main()
