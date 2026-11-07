import math
import re

KEYS = ['communication', 'problem_solving', 'technical', 'analytical', 'teamwork', 'adaptability', 'leadership']
WEIGHTS = dict(zip(['hr', 'user', 'manager'], [dict(zip(KEYS, row)) for row in [
    [25, 10, 0, 10, 25, 25, 5], [10, 25, 35, 15, 10, 5, 0], [15, 15, 10, 15, 10, 10, 25]]]))


def verified_scores(scores, transcript, allowed, source_turns=None):
    result = {}
    for key in allowed:
        if key not in KEYS:
            continue
        value = scores.get(key, {})
        if not isinstance(value, dict):
            value = {}
        invalid_score = False
        try:
            score = float(value.get('score', 2))
            invalid_score = not math.isfinite(score) or not 1 <= score <= 5 or 'score' not in value
            score = max(1, min(5, score)) if math.isfinite(score) else 2
        except (ValueError, TypeError):
            invalid_score = True
            score = 2
        evidence = value.get('evidence', [])
        if isinstance(evidence, str):
            evidence = [evidence]
        sources = source_turns if source_turns is not None else [{'turn_id': None, 'transcript': transcript}]
        refs = []
        for quote in evidence if isinstance(evidence, list) else []:
            if not isinstance(quote, str) or len(quote.strip()) < 8 or not re.search(r'\w', quote):
                continue
            for turn in sources:
                start = turn['transcript'].find(quote)
                if start >= 0:
                    ref = {'turn_id': turn['turn_id'], 'quote': quote, 'start': start, 'end': start + len(quote)}
                    if ref not in refs:
                        refs.append(ref)
        sufficiency = value.get('evidence_sufficiency', 'sufficient' if refs else 'none')
        if sufficiency not in ('sufficient', 'partial', 'none'):
            sufficiency = 'partial'
        if not refs:
            sufficiency = 'none'
        elif invalid_score:
            sufficiency = 'partial'
        quality = 'unusable' if not re.search(r'\w', transcript) else 'unknown'
        status = 'unusable_transcript' if quality == 'unusable' else 'measured' if sufficiency == 'sufficient' else 'insufficient'
        result[key] = {'score': score if refs else min(score, 2), 'evidence': list(dict.fromkeys(r['quote'] for r in refs)),
            'source_refs': refs, 'status': status, 'score_status': 'supported' if status == 'measured' else 'provisional',
            'evidence_sufficiency': sufficiency, 'transcript_quality': quality,
            'rationale': str(value.get('rationale', ''))[:1500]}
    return result


def aggregate(items, weights):
    competencies = []
    for key, weight in weights.items():
        entries = [item[key] for item in items if key in item]
        measured = [v for v in entries if v.get('status', 'measured') == 'measured' and v.get('score') is not None]
        score = round(sum(v['score'] for v in measured) / len(measured), 2) if measured else None
        status = ('measured' if measured else 'insufficient' if any(v.get('status') == 'insufficient' for v in entries)
                  else 'unusable_transcript' if any(v.get('status') == 'unusable_transcript' for v in entries) else 'not_assessed')
        competencies.append({'key': key, 'name': key.replace('_', ' ').title(), 'weight': weight, 'score': score,
            'status': status, 'measured_units': len(measured), 'assessed_units': len(entries),
            'evidence': list(dict.fromkeys(e for v in measured for e in v.get('evidence', []))),
            'source_refs': [ref for v in measured for ref in v.get('source_refs', [])]})
    measured = [c for c in competencies if c['score'] is not None and c['weight'] > 0]
    total = round(sum(c['score'] * c['weight'] for c in measured) / sum(c['weight'] for c in measured), 2) if measured else None
    return total, competencies


def coverage(competencies):
    active = [c for c in competencies if c['weight'] > 0]
    weight = sum(c['weight'] for c in active)
    return {'measured': sum(c['status'] == 'measured' for c in active), 'total': len(active),
            'weighted_percent': round(100 * sum(c['weight'] for c in active if c['status'] == 'measured') / weight) if weight else 0,
            **{s: sum(c['status'] == s for c in active) for s in ('insufficient', 'not_assessed', 'unusable_transcript')}}


def label(score):
    if score is None:
        return 'Belum terukur'
    return 'Strong Match' if score * 20 >= 85 else 'Good' if score * 20 >= 70 else 'Needs Work' if score * 20 >= 55 else 'Not Ready'
