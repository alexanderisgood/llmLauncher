import json,os,re,subprocess,time,urllib.request,urllib.error,statistics,sys
from pathlib import Path
root=Path('/tmp/llm-launcher-slotstream-source');binary=root/'.build/release/slotstream';out=Path('/tmp/slotstream-perf-41gb');out.mkdir(exist_ok=True)
model=Path.home()/'.slotstream/models/qwen38-flash-next-mlx-4bit';port=18089
prompts=[
 'Write a comprehensive Python implementation of a bounded LRU cache with TTL, thread safety and detailed unit tests. Explain each design decision. Provide at least 150 lines of code.',
 'Write a comprehensive TypeScript implementation of a task queue with retry backoff, cancellation, concurrency limits and detailed tests. Explain each design decision. Provide at least 150 lines of code.',
 'Write a comprehensive Python implementation of a streaming JSON Lines parser with bounded memory, error recovery, Unicode handling and detailed tests. Explain each design decision. Provide at least 150 lines of code.'
]
def vm():
 text=subprocess.check_output(['vm_stat'],text=True)
 d={k:int(v) for k,v in re.findall(r'^([^:]+):\s+(\d+)\.',text,re.M)}
 return {'reclaimableBytes':sum(d.get(k,0) for k in ['Pages free','Pages purgeable','File-backed pages'])*16384,'swapins':d['Swapins'],'swapouts':d['Swapouts']}
def request(prompt,tokens):
 body={'model':'qwen3.8-flash-next:4bit','messages':[{'role':'user','content':prompt}], 'stream':True,'stream_options':{'include_usage':True},'temperature':0,'seed':42,'max_tokens':tokens,'reasoning_effort':'none'}
 req=urllib.request.Request(f'http://127.0.0.1:{port}/v1/chat/completions',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 events=[];first=None;before=vm();start=time.monotonic();content='';usage=None
 with urllib.request.urlopen(req,timeout=600) as r:
  for line in r:
   if not line.startswith(b'data: ') or line.strip()==b'data: [DONE]':continue
   v=json.loads(line[6:])
   if 'error' in v:raise RuntimeError(v['error'])
   if 'slotstream_metrics' in v:events.append({'at':time.monotonic()-start,'metrics':v['slotstream_metrics']})
   if 'usage' in v:usage=v['usage']
   for c in v.get('choices',[]):
    d=c.get('delta',{})
    if d.get('content') or d.get('reasoning_content'):
     if first is None:first=time.monotonic()-start
     content+=d.get('content','')+d.get('reasoning_content','')
 elapsed=time.monotonic()-start
 assert len(events)==2 and events[0]['metrics']['phase']=='prefilled' and events[1]['metrics']['phase']=='completed',events
 m=events[-1]['metrics'];assert m['decode_tokens']==usage['completion_tokens'];assert m['processed_tokens']+m['cached_tokens']==usage['prompt_tokens']
 assert events[0]['at']<=first and m['decode_tokens']>=128
 return {'events':events,'firstOutputSeconds':first,'seconds':elapsed,'usage':usage,'before':before,'after':vm(),'output':content}
results=json.loads((out/'rounds.json').read_text()) if (out/'rounds.json').exists() else []
try:
 for index,depth in enumerate([3,2]):
  if index < len(results):continue
  time.sleep(3)  # Let Metal release the previous process's allocations.
  assert not subprocess.run(['pgrep','-x','slotstream'],capture_output=True).stdout,'Another engine is running'
  before=vm();assert before['reclaimableBytes']>=30_000_000_000,before
  env={k:v for k,v in os.environ.items() if not k.startswith(('SLOTSTREAM_','MLX_','DYLD_'))};env['SLOTSTREAM_DRAFT_DEPTH']=str(depth)
  cmd=[str(binary),'serve','--model',str(model),'--port',str(port),'--max-ram-percent',str(41_000_000_000 / (os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')) * 100),'--max-context','131072','--mtp','on','--vision','off']
  check=subprocess.run([str(binary),'doctor','--model',str(model),'--max-ram-percent',str(41_000_000_000 / (os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')) * 100),'--max-context','131072','--mtp','on','--vision','off','--json'],env=env,capture_output=True,text=True)
  assert check.returncode==0,check.stderr
  planned=json.loads(check.stdout)
  print(json.dumps({'depth':depth,'ceilingGB':41,'nativeTargetGB':planned['target_gb'],'expertPoolGB':planned['pool_gb']}),flush=True)
  log=(out/f'run-{index}-depth-{depth}.log').open('w');proc=subprocess.Popen(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
  try:
   for _ in range(150):
    if proc.poll() is not None:raise RuntimeError('Native server failed: '+str(proc.returncode))
    try:
     with urllib.request.urlopen(f'http://127.0.0.1:{port}/v1/models',timeout=2) as r:catalog=json.load(r)
     break
    except (OSError,urllib.error.URLError):time.sleep(.2)
   else:raise RuntimeError('Server readiness timeout')
   prompt=prompts[index//2]
   warm=request(prompt,128)
   measured=request(prompt,384)
   row={'round':index//2,'depth':depth,'memoryCeilingGB':41,'plan':planned,'warm':warm,'measured':measured}
   results.append(row);(out/'rounds.json').write_text(json.dumps(results,indent=2))
   m=measured['events'][-1]['metrics'];print(json.dumps({'round':index//2,'depth':depth,'tps':m['decode_tokens']/m['decode_seconds'],'expertHitRate':m['expert_hit_rate'],'acceptance':m['accepted_drafts']/m['drafted_tokens'],'ioSeconds':m['decode_io_seconds'],'swapDelta':measured['after']['swapouts']-measured['before']['swapouts']}),flush=True)
  finally:
   proc.terminate()
   try:proc.wait(timeout=20)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
   log.close()
 for depth in [2,3]:
  samples=[r['measured']['events'][-1]['metrics'] for r in results if r['depth']==depth]
  print('MEDIAN',depth,statistics.median(m['decode_tokens']/m['decode_seconds'] for m in samples),flush=True)
finally:
 print('Benchmark finished; test model processes closed.',flush=True)
