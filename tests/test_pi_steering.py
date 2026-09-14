import unittest
from unittest.mock import Mock, patch
import launcher

class Steering(unittest.TestCase):
    def setUp(self):
        self.console=launcher.AgentConsole(owner_run_id='fixture',plan=Mock(),process=Mock(),master_fd=-1,cols=100,rows=30,protocol='pi-rpc')
        self.manager=launcher.RunManager()
    def test_steering_bypasses_follow_up_queue_and_acknowledges(self):
        self.console.rpc_streaming=True
        self.console.rpc_follow_up_queue=['later']
        with patch.object(self.manager,'_write_pi_rpc_command') as write, patch.object(self.console,'public',return_value={}):
            self.manager._write_pi_rpc_console(self.console,{'command':'steer','message':'Use blue instead'})
        command=write.call_args.args[1]
        self.assertEqual(command['type'],'prompt')
        self.assertEqual(command['streamingBehavior'],'steer')
        self.assertEqual(command['message'],'Use blue instead')
        self.assertEqual(self.console.rpc_follow_up_queue,['later'])
        launcher.pi_rpc_event_output(self.console,{'type':'response','command':'prompt','id':command['id'],'success':True})
        self.assertFalse(self.console.rpc_steer_ids)
        self.assertEqual(self.console.rpc_timeline_events[-1]['text'],'Use blue instead')
        self.assertIn('next agent step',self.console.rpc_timeline_events[-1]['title'])
    def test_idle_compaction_and_slash_rejected(self):
        for streaming,compacting,message in [(False,False,'hello'),(True,True,'hello'),(True,False,'/new')]:
            self.console.rpc_streaming=streaming;self.console.rpc_compacting=compacting
            with patch.object(self.manager,'_write_pi_rpc_command') as write:
                with self.assertRaises(ValueError): self.manager._write_pi_rpc_console(self.console,{'command':'steer','message':message})
                write.assert_not_called()
    def test_failed_write_keeps_no_pending_receipt(self):
        self.console.rpc_streaming=True
        with patch.object(self.manager,'_write_pi_rpc_command',side_effect=ValueError('closed')):
            with self.assertRaises(ValueError): self.manager._write_pi_rpc_console(self.console,{'command':'steer','message':'hello'})
        self.assertFalse(self.console.rpc_steer_ids)
    def test_steered_user_message_does_not_replace_original_prompt(self):
        launcher.pi_rpc_event_output(self.console, {'type':'agent_start'})
        for text in ['Build the level','Use blue instead']:
            launcher.pi_rpc_event_output(self.console, {'type':'message_start','message':{'role':'user','content':text}})
        users=[item['text'] for item in self.console.rpc_timeline_items.values() if item['kind']=='user']
        self.assertEqual(users,['Build the level','Use blue instead'])
if __name__=='__main__': unittest.main()
