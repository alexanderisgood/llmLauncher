import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import mtplx_reasoning as policy

class ReasoningTemplateTests(unittest.TestCase):
    def test_only_reviewed_qwopus_template_is_pinned_without_rewriting(self):
        template = '{%- set ns = namespace(multi_step_tool=true, last_query_index=0) %}old tracking{%- for message in messages %}{%- if loop.index0 > ns.last_query_index %}{{ message.reasoning_content }}{% endif %}{% endfor %}'
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'config.json').write_text(json.dumps({'mtplx_wrapper':{'source_model':policy.QWOPUS_SOURCE}})); (p/'chat_template.jinja').write_text(template)
            self.assertIsNone(policy.preserved_qwopus_template(p))
            with patch.object(policy,'QWOPUS_TEMPLATE_SHA256',hashlib.sha256(template.encode()).hexdigest()):
                changed=policy.preserved_qwopus_template(p)
                self.assertEqual(changed,template)
                self.assertIn('last_query_index',changed)
                self.assertIn('message.reasoning_content',changed)
                self.assertEqual((p/'chat_template.jinja').read_text(),template)
                (p/'config.json').write_text('{}')
                self.assertIsNone(policy.preserved_qwopus_template(p))
