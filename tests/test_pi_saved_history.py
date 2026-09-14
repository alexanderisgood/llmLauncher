import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import launcher


class SavedHistory(unittest.TestCase):
    def test_selected_branch_includes_pre_compaction_messages_only(self):
        entries=[
            {'id':'u','parentId':None,'type':'message','message':{'role':'user','content':'Original request'}},
            {'id':'a','parentId':'u','type':'message','message':{'role':'assistant','content':'Original answer'}},
            {'id':'other','parentId':'u','type':'message','message':{'role':'assistant','content':'Abandoned branch'}},
            {'id':'c','parentId':'a','type':'compaction','summary':'Small model context'},
        ]
        messages=launcher.pi_rpc_saved_history({'entries':entries,'leafId':'c'})
        self.assertEqual([m['id'] for m in messages],['u','a','c'])
        console=launcher.AgentConsole(owner_run_id='fixture',plan=Mock(),process=Mock(),master_fd=-1,cols=100,rows=30,protocol='pi-rpc')
        launcher.pi_rpc_event_output(console,{'type':'response','command':'get_entries','success':True,
                                             'data':{'entries':entries,'leafId':'c'}})
        text=' '.join(x['text'] for x in console.rpc_timeline_items.values())
        self.assertIn('Original answer',text)
        self.assertNotIn('Abandoned branch',text)
        self.assertTrue(any(x['title']=='Context compacted' for x in console.rpc_timeline_items.values()))
        self.assertTrue(console.rpc_history_loaded)
        self.assertEqual(launcher.pi_rpc_saved_history({'entries':entries,'leafId':None}),[])
        with self.assertRaises(ValueError):
            launcher.pi_rpc_saved_history({'entries':entries,'leafId':'missing'})
        entries[0]['parentId']='a'
        with self.assertRaises(ValueError):
            launcher.pi_rpc_saved_history({'entries':entries,'leafId':'c'})

    def test_large_history_has_a_separate_bounded_transport_allowance(self):
        self.assertEqual(launcher.pi_rpc_line_limit(b'{"type":"response","command":"get_entries",'),16*1024*1024)
        self.assertEqual(launcher.pi_rpc_line_limit(b'{"type":"message_update",'),2*1024*1024)

    @unittest.skipUnless(os.environ.get('LLM_LAUNCHER_PI_INTEGRATION')=='1','installed Pi')
    def test_native_compacted_session_reloads_transcript_without_reinflating_model_context(self):
        manager=launcher.RunManager();console=None
        try:
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder);session=root/'saved.jsonl'
                entries=[{'type':'session','version':3,'id':'saved','cwd':str(root),'timestamp':'2026-01-01T00:00:00Z'}]
                def add(id,parent,type,**kwargs):
                    entries.append({'id':id,'parentId':parent,'type':type,'timestamp':'2026-01-01T00:00:00Z',**kwargs})
                add('u',None,'message',message={'role':'user','content':'Earlier question', 'timestamp':1})
                add('a','u','message',message={'role':'assistant','content':[{'type':'text','text':'Earlier answer retained'}],'stopReason':'stop','timestamp':2})
                add('big','a','message',message={'role':'user','content':'Archived text '+('x'*(2*1024*1024+1000)),'timestamp':3})
                add('end','big','message',message={'role':'assistant','content':[],'stopReason':'aborted','timestamp':4})
                add('c','end','compaction',summary='Compact handover only',firstKeptEntryId='end',tokensBefore=60000)
                session.write_text(''.join(json.dumps(e)+'\n' for e in entries))
                plan=launcher.LaunchPlan(run_id='history-fixture',backend='mtplx',client='pi',
                    model={'id':'fixture','name':'Fixture','backends':{}},project=str(root),context=131072,
                    output=1024,reasoning='off',port=18082,mode='ar',options={},agent_host='console',pi_session_file=str(session))
                with patch.dict(launcher.BINARIES,{'pi':shutil.which('pi')}):
                    launcher.build_pi_client(plan,launcher.ClientRoute('fixture','fixture','http://127.0.0.1:1/v1','fixture'))
                plan.client_argv+=['--no-tools','--no-extensions','--no-skills','--no-prompt-templates','--no-themes','--no-context-files','--offline','--no-approve']
                plan.client_env.update({'PI_CODING_AGENT_DIR':str(root/'config'),'PI_CODING_AGENT_SESSION_DIR':str(root/'sessions'),'PI_OFFLINE':'1','PI_TELEMETRY':'0'})
                manager.plan=plan;manager.state={'phase':'running','run':plan.public(),'events':[]}
                manager.attachments[plan.run_id]=launcher.SurfaceAttachment(owner_run_id=plan.run_id,plan=plan,primary=True)
                observed=[];original=launcher.pi_rpc_event_output
                def observe(c,event):
                    if event.get('command')=='get_messages':observed.append(event['data']['messages'])
                    return original(c,event)
                with patch.object(launcher,'pi_rpc_event_output',side_effect=observe):
                    with patch.dict(os.environ,{'PATH':os.environ['PATH']},clear=True):
                        console=manager._launch_agent_console(plan,manager.cancel_event)
                    deadline=time.monotonic()+15
                    while not console.rpc_history_loaded and time.monotonic()<deadline:time.sleep(.03)
                    self.assertTrue(console.rpc_history_loaded)
                    texts=[i['text'] for i in console.rpc_timeline_items.values()]
                    self.assertIn('Earlier question',texts)
                    self.assertIn('Earlier answer retained',texts)
                    manager._write_pi_rpc_command(console,{'id':'model-context-check','type':'get_messages'})
                    while not observed and time.monotonic()<deadline:time.sleep(.03)
                    self.assertTrue(observed)
                    self.assertIn('Compact handover only',json.dumps(observed))
                    self.assertNotIn('Earlier answer retained',json.dumps(observed))
        finally:
            if console is not None:manager._stop_agent_console_process(console)
