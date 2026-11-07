import hashlib
import re
from app.config import ROOT
from app.ai.scoring import WEIGHTS


def snapshot(persona, panel=None, job_role=None, use_job_rubric=False):
    if use_job_rubric:
        from app.ai.job_rubric import matches_scope, snapshot_profile
        if not matches_scope(job_role, persona, panel):
            raise ValueError('Rubrik draf hanya tersedia untuk Engineering Manager dengan interviewer tunggal Manager.')
        return snapshot_profile()
    text = (ROOT / 'docs/assessment-reference.md').read_text()
    rubric = text.split('<!-- rubric:start -->')[1].split('<!-- rubric:end -->')[0].strip()
    panel = panel or [persona]
    averages = {k: sum(WEIGHTS[p][k] for p in panel) / len(panel) for k in WEIGHTS[persona]}
    weights = {k: int(v) for k, v in averages.items()}
    for key in sorted(weights, key=lambda k: averages[k] - weights[k], reverse=True)[:100 - sum(weights.values())]:
        weights[key] += 1
    return {'version': '2026-11-05.2', 'sha256': hashlib.sha256(rubric.encode()).hexdigest(),
            'rubric': rubric, 'weights': weights, 'persona_weights': {p: WEIGHTS[p] for p in panel}, 'validated': False,
            'sources': re.findall(r'https://[^\s|)]+', text)}
