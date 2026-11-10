from pathlib import Path
import json,struct,subprocess,tempfile
w=Path(__file__).resolve().parent

def string(s):
 b=s.encode();return struct.pack('<Q',len(b))+b

def write(path,number,count,total,tensors):
 kv=b''.join(string(k)+struct.pack('<IQ',10,v) for k,v in [('split.no',number),('split.count',count),('split.tensors.count',total)])
 headers=[];payload=bytearray()
 for name,seed in tensors:
  headers.append(string(name)+struct.pack('<IQQQIQ',3,256,1,512,12,len(payload)))
  payload.extend(bytes([seed%256])*73728)
 h=struct.pack('<4sIQQ',b'GGUF',3,len(tensors),3)+kv+b''.join(headers)
 h+=bytes((-len(h))%32);path.write_bytes(h+payload)

with tempfile.TemporaryDirectory(prefix='strata-split-check-') as tmp:
 d=Path(tmp);ps=[d/f'tiny-{i+1:05}-of-00003.gguf' for i in range(3)]
 names=[(f'blk.{layer}.ffn_{role}_exps.weight',layer*3+idx) for layer in range(48) for idx,role in enumerate(['gate','up','down'])]
 def restore():
  write(ps[0],0,3,144,[]);write(ps[1],1,3,144,names[:73]);write(ps[2],2,3,144,names[73:])
 def check(reject=False):
  p=subprocess.run([str(w/'strata-split-check'),str(ps[0]),*(['reject'] if reject else [])],capture_output=True,text=True,check=True)
  print(p.stdout.strip())
 restore();check()
 ps[2].unlink();check(True)
 restore();write(ps[2],1,3,144,names[73:]);check(True)
 restore();write(ps[2],2,3,144,[names[0],*names[74:]]);check(True)
 restore();write(ps[2],2,3,145,names[73:]);check(True)
 restore();ps[2].write_bytes(ps[2].read_bytes()[:-32]);check(True)
print('Split metadata, missing-shard, duplicate-tensor and truncated-payload rejection checks passed')
