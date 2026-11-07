import hashlib
import re
from app.config import ROOT
from app.ai.scoring import WEIGHTS


def snapshot(persona):
    text = (ROOT / 'docs/assessment-reference.md').read_text()
    rubric = text.split('<!-- rubric:start -->')[1].split('<!-- rubric:end -->')[0].strip()
    return {'version': '2026-11-05.2', 'sha256': hashlib.sha256(rubric.encode()).hexdigest(),
            'rubric': rubric, 'weights': WEIGHTS[persona], 'validated': False,
            'sources': re.findall(r'https://[^\s|)]+', text)}
