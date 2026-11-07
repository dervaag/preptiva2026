"""Versioned persona guidance and CV-grounded context, independent of target level."""
import hashlib
import json
import re
from app.config import ROOT

STAGES = ('auto', 'student', 'fresh_graduate', 'experienced', 'career_switcher')


def snapshot():
    raw = (ROOT / 'docs/question-guidebook.json').read_bytes()
    return {**json.loads(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def profile(summary, cv, declared='auto'):
    normalized = ' '.join(cv.casefold().split())
    anchors = []
    for item in summary.get('evidence', []):
        if not isinstance(item, dict):
            continue
        quote = str(item.get('quote', '')).strip()
        if 12 <= len(quote) <= 700 and ' '.join(quote.casefold().split()) in normalized:
            if quote not in [a['quote'] for a in anchors]:
                anchors.append({'id': 'cv' + str(len(anchors) + 1), 'kind': item.get('kind', 'background'), 'quote': quote})
    if not anchors:
        # Actual document excerpts remain available even when extraction omits evidence.
        for part in re.split(r'\n+', cv):
            if len(part.strip()) >= 12:
                anchors.append({'id': 'cv' + str(len(anchors) + 1), 'kind': 'background', 'quote': part.strip()[:600]})
            if len(anchors) >= 12:
                break
    stage, evidence = 'unknown', ''
    candidates = summary.get('career_stage_candidates', [{'stage': summary.get('career_stage'), 'quote': summary.get('career_stage_evidence', '')}])
    verified = [(c.get('stage'), str(c.get('quote') or '').strip()) for c in candidates if isinstance(c, dict)]
    verified = [(p, q) for p, q in verified if p in STAGES[1:] and len(q) >= 8 and ' '.join(q.casefold().split()) in normalized]
    if len({p for p, q in verified}) == 1:
        stage, evidence = verified[0]
    if declared in STAGES[1:]:
        stage, evidence = declared, 'candidate-selected background'
    return {'career_stage': stage, 'stage_evidence': evidence, 'anchors': anchors[:24]}


def role_context(context, persona):
    guide = context['guidebook']
    # HR does not receive skills/technical requirements or another panel member's rubric.
    data = {key: context[key] for key in ('job_role', 'level', 'industry', 'company', 'language', 'candidate_profile', 'panel_members') if key in context}
    data['interviewer'] = persona
    data['guidance'] = {'scope': guide['roles'][persona]['scope'], 'rules': guide['rules']}
    data['job_context'] = (context.get('jd_summary', {}).get('responsibilities', []) if persona == 'hr'
                           else context.get('jd_summary', {}))
    assessment = context.get('assessment', {})
    if assessment.get('profile_id') and persona == 'manager':
        data['job_competencies'] = {key:{'name':item['name'],'definition':item['definition']}
                                    for key,item in assessment['competency_definitions'].items()}
    if persona != 'hr':
        data['cv_summary'] = context.get('cv_summary', {})
    return data


def panel_roles(session):
    return session.script.get('settings', {}).get('panel', [session.interviewer])


def speaker(session, order):
    roles = panel_roles(session)
    return session.script.get('speaker_by_order', {}).get(str(order), roles[(order - 1) % len(roles)])


def context_for(session, persona):
    context = {'job_role': session.job_role, 'level': session.level, 'industry': session.industry,
               'company': session.company, 'language': session.script['settings']['language'],
               'cv_summary': session.cv_summary, 'jd_summary': session.jd_summary,
               'candidate_profile': session.script.get('candidate_profile', {}),
               'guidebook': session.script.get('guidebook') or snapshot(), 'assessment':session.script.get('assessment', {})}
    return role_context(context, persona)
