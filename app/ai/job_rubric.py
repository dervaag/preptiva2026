"""Versioned job rubrics; opt-in drafts never imply expert approval."""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
PROFILE_ID = 'engineering_manager_manager'


def snapshot_hash(value):
    payload = {key: item for key, item in value.items() if key != 'sha256'}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def load_profile():
    text = (ROOT / 'docs/engineering-manager-rubric.md').read_text()
    raw = text.split('<!-- em-rubric:start -->')[1].split('<!-- em-rubric:end -->')[0].strip()
    profile = json.loads(raw)
    expected = {'problem_solving', 'teamwork', 'leadership', 'communication', 'technical'}
    if (profile['id'] != PROFILE_ID or profile['validated'] is not False
            or profile['job_reviewed_by_human'] is not False or profile['status'] != 'draft_pending_expert_review'
            or set(profile['weights']) != expected or set(profile['competencies']) != expected
            or any(type(v) is not int or v <= 0 for v in profile['weights'].values())
            or sum(profile['weights'].values()) != 100):
        raise ValueError('Rubrik draf EM tidak valid.')
    sources = {s['id']: s for s in profile['sources']}
    if len(sources) != len(profile['sources']):
        raise ValueError('ID sumber rubrik ganda.')
    for source in sources.values():
        parsed = urlsplit(source['url'])
        if parsed.scheme != 'https' or not parsed.netloc or parsed.username or not source['locator']:
            raise ValueError('Sumber rubrik memerlukan HTTPS dan lokasi bagian yang jelas.')
    ids = set()
    for key, competency in profile['competencies'].items():
        if set(competency['levels']) != {'1','2','3','4','5'}:
            raise ValueError('Rubrik harus memiliki lima tingkat.')
        for level, indicator in competency['levels'].items():
            if (indicator['id'] != f'em.{key}.l{level}' or indicator['id'] in ids
                    or indicator['origin'] not in ('internal','adapted','taken') or not indicator['behavior']
                    or not indicator['application'] or not indicator['source_ids']
                    or set(indicator['source_ids']) - set(sources)):
                raise ValueError('Indikator atau rujukan rubrik tidak valid.')
            ids.add(indicator['id'])
    return profile


def matches_scope(job_role, persona, panel=None):
    return (' '.join((job_role or '').casefold().split()) == 'engineering manager'
            and persona == 'manager' and (panel or [persona]) == ['manager'])


def snapshot_profile():
    profile = load_profile()
    policy = ('Rubrik draf internal khusus Engineering Manager/persona Manager; belum ditinjau ahli atau divalidasi. '
              'Nilai hanya bukti perilaku yang relevan, bukan usia, gender, aksen, bahasa campuran atau perpindahan tab. '
              'Pengalaman proyek/perkuliahan/relawan dapat digunakan tanpa mengarang pengalaman kerja. '
              'Bukti kurang bukan kemampuan rendah. Skor 1–2 memerlukan bukti eksplisit perilaku pada jangkar itu. '
              'Tingkat adalah jangkar alternatif, bukan kewajiban memenuhi perilaku tingkat rendah. '
              'Gunakan indikator pada tingkat skor yang sama dan kutipan asli satu giliran untuk setiap indikator. '
              'Tanpa bukti terverifikasi, jangan beri status sufficient. Jangan menghukum kesalahan STT.\n')
    table = ['| Kompetensi | 1 | 2 | 3 | 4 | 5 |', '| --- | --- | --- | --- | --- | --- |']
    for key, competency in profile['competencies'].items():
        cells = [competency['levels'][str(level)]['behavior'].replace('|','/') for level in range(1,6)]
        table.append('| ' + ' | '.join([key] + cells) + ' |')
    result = {'version':profile['version'], 'profile_id':profile['id'], 'title':profile['title'],
              'scope':profile['scope'], 'status':profile['status'], 'validated':False, 'job_reviewed_by_human':False,
              'weights':profile['weights'], 'persona_weights':{'manager':profile['weights']},
              'competency_definitions':profile['competencies'], 'sources':profile['sources'],
              'job_analysis':profile['job_analysis'], 'scoring_rules':profile.get('scoring_rules', []),
              'source_checked_at':profile.get('source_checked_at'), 'weight_origin':profile.get('weight_origin'),
              'rubric':policy + '\n'.join(table)}
    result['sha256'] = snapshot_hash(result)
    return result


def evaluation_fields(assessment, allowed):
    if not assessment.get('profile_id'):
        return {}
    return {'assessment_profile':assessment['profile_id'],
            'competency_definitions':{key:value for key,value in assessment['competency_definitions'].items() if key in allowed},
            'scoring_rules':assessment.get('scoring_rules', []),
            'indicator_policy':'Use the anchor at the EXACT scored level, not a cumulative list of lower levels.'}


def verify_indicators(value, key, score, assessment, source_turns):
    """Verify identifiers/quotes; semantic relevance still needs expert review."""
    definition = assessment.get('competency_definitions', {}).get(key, {})
    levels = definition.get('levels', {})
    level = int(score) if isinstance(score, (int,float)) and float(score).is_integer() else 0
    anchor = levels.get(str(level))
    claimed = value.get('indicators_met', [])
    valid = (anchor is not None and isinstance(claimed,list) and claimed == [anchor['id']]
             and type(value.get('score')) in (int,float) and value['score'] == level)
    linked = []
    for evidence in value.get('indicator_evidence', []) if isinstance(value.get('indicator_evidence'),list) else []:
        if not isinstance(evidence,dict) or not anchor or evidence.get('indicator_id') != anchor['id']:
            valid = False
            continue
        quote = evidence.get('quote')
        if not isinstance(quote,str) or len(quote.strip()) < 8 or not re.search(r'\w', quote):
            valid = False
            continue
        matches = []
        for turn in source_turns:
            if evidence.get('turn_id') is not None and evidence['turn_id'] != turn['turn_id']:
                continue
            start = turn['transcript'].find(quote)
            if start >= 0:
                matches.append({'indicator_id':anchor['id'], 'quote':quote, 'turn_id':turn['turn_id'],
                                'start':start,'end':start+len(quote),'behavior':anchor['behavior'],'level':level})
        if not matches:
            valid = False
        linked.extend(item for item in matches if item not in linked)
    valid = bool(valid and linked)
    next_anchor = levels.get(str(level+1)) if valid else None
    gap = str(value.get('next_level_gap') or '').strip()[:1500] if next_anchor else ''
    if next_anchor and not gap:
        gap = 'Untuk meninjau tingkat berikutnya, periksa bukti: ' + next_anchor['behavior']
    sources = []
    if valid:
        by_id = {s['id']:s for s in assessment['sources']}
        for source_id in anchor['source_ids']:
            source = by_id[source_id]
            sources.append({'indicator_id':anchor['id'], 'origin':anchor['origin'],
                'source_title':source['title'], 'source_edition':source.get('edition',''), 'source_locator':source['locator'],
                'source_excerpt':source.get('excerpt',''), 'url':source['url'], 'application':anchor['application']})
    return {'indicators_met':[anchor['id']] if valid else [], 'indicator_evidence':linked if valid else [],
            'next_level_gap':gap, 'next_level_indicators':[{'id':next_anchor['id'],'behavior':next_anchor['behavior'],'level':level+1}] if next_anchor else [],
            'sources':sources, 'indicator_validation':'verified' if valid else 'insufficient'}, valid
