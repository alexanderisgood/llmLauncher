import json
import unittest
from session_proxy import transform_chat_request, PI_SUMMARIZATION_SYSTEM_PROMPT

class SummaryMemory(unittest.TestCase):
    def request(self, text=PI_SUMMARIZATION_SYSTEM_PROMPT, client='pi', limit=13107, backend='omlx'):
        body={'model':'model','max_tokens':limit,'messages':[{'role':'system','content':text},{'role':'user','content':'Summarize this saved work.'}]}
        return json.loads(transform_chat_request(json.dumps(body).encode(), {'backend':backend,'servedModel':'model','reasoning':'xhigh','outputLimit':100000,'contextLimit':131072}, {'client':client}))
    def test_mtplx_native_summary_is_bounded_without_changing_task_reasoning(self):
        result=self.request(backend='mtplx')
        self.assertEqual(result['max_tokens'],4096)
        self.assertFalse(result['enable_thinking'])
        self.assertEqual(result['reasoning_effort'],'none')
        ordinary=self.request(backend='mtplx',text='Repair this implementation.')
        self.assertNotIn('enable_thinking',ordinary)
        self.assertEqual(ordinary['max_tokens'],13107)
    def test_summary_is_bounded_and_has_no_thinking_expansion(self):
        result=self.request()
        self.assertEqual(result['max_tokens'],4096)
        self.assertEqual(result['chat_template_kwargs'],{'enable_thinking':False})
        self.assertEqual(self.request(limit=1024)['max_tokens'],1024)
    def test_ordinary_turns_and_other_clients_are_unchanged(self):
        for result in [self.request(text='Help with my code.'),self.request(client='opencode')]:
            self.assertEqual(result['max_tokens'],13107)
            self.assertNotIn('chat_template_kwargs',result)
if __name__=='__main__':unittest.main()
