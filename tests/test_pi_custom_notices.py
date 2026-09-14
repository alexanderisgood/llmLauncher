import unittest
from unittest.mock import Mock
import launcher


class CustomNotices(unittest.TestCase):
    def test_visible_notice_survives_history_without_duplicate_or_tool_execution(self):
        console = launcher.AgentConsole(owner_run_id='fixture', plan=Mock(),
            process=Mock(), master_fd=-1, cols=100, rows=30, protocol='pi-rpc')
        message = {'role':'custom','display':True,'timestamp':1780000000000,
            'customType':'launcher-tool-format-recovery','content':'Retrying a real tool call.'}
        emit = lambda msg: launcher.pi_rpc_event_output(console,{'type':'message_end','message':msg})
        self.assertIn(b'Retrying a real tool call.',emit(message))
        self.assertEqual(emit(message),b'')
        launcher.pi_rpc_record_history(console,[message])
        items = list(console.rpc_timeline_items.values())
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['kind'],'notice')
        self.assertEqual(items[0]['title'],'Retrying tool call')
        hidden = {**message,'display':False,'timestamp':1780000000001}
        self.assertEqual(emit(hidden),b'')
        launcher.pi_rpc_record_history(console,[hidden])
        self.assertEqual(len(console.rpc_timeline_items),1)
