"""Pin the reviewed Qwopus template without changing its reasoning contract."""
import hashlib
import json
from pathlib import Path

QWOPUS_SOURCE = 'Jackrong/Qwopus3.8-27B-Flash'
QWOPUS_TEMPLATE_SHA256 = 'f2e03cfdf930fb26e7c88ca83abc3a0c1e7c5b1fe68ee43ba81d0c47c8460ceb'


def preserved_qwopus_template(model_path):
    path = Path(model_path)
    try:
        config = json.loads((path / 'config.json').read_text())
        if config.get('mtplx_wrapper', {}).get('source_model') != QWOPUS_SOURCE:
            return None
        template = (path / 'chat_template.jinja').read_text()
    except (OSError, ValueError):
        return None
    if hashlib.sha256(template.encode()).hexdigest() != QWOPUS_TEMPLATE_SHA256:
        # A changed publisher template needs review, never a blind rewrite.
        return None
    # The rolling checkpoint is part of the publisher's conversation template,
    # not a compatibility defect. Removing it selected preserve-all in MTPLX
    # and carried completed rounds' reasoning into subsequent user turns.
    # Keep active assistant/tool reasoning and let MTPLX auto choose scoped.
    # The historical function name stays for callers; preservation now means
    # preserving the publisher template, not forcing all thinking into history.
    return template
