import re

KEYS = ['communication', 'problem_solving', 'technical', 'analytical', 'teamwork', 'adaptability', 'leadership']
WEIGHTS = dict(zip(['hr', 'user', 'manager'], [dict(zip(KEYS, row)) for row in [
    [25, 10, 0, 10, 25, 25, 5], [10, 25, 35, 15, 10, 5, 0], [15, 15, 10, 15, 10, 10, 25]]]))


def verified_scores(scores, transcript, allowed):
    normalized = ' '.join(re.findall(r'\w+', transcript.casefold()))
    result = {}
    for key, value in scores.items():
        if key not in allowed or key not in KEYS or not isinstance(value, dict):
            continue
        score = max(1, min(5, float(value['score'])))
        evidence = value.get('evidence', [])
        if isinstance(evidence, str):
            evidence = [evidence]
        evidence = [quote for quote in evidence if isinstance(quote, str) and len(quote.strip()) >= 8
                    and re.search(r'\w', quote) and ' '.join(re.findall(r'\w+', quote.casefold())) in normalized]
        result[key] = {'score': score if evidence else min(score, 2), 'evidence': evidence}
    return result


def aggregate(items, weights):
    competencies = []
    for key, weight in weights.items():
        entries = [item[key] for item in items if key in item]
        score = round(sum(v['score'] for v in entries) / len(entries), 2) if entries else None
        competencies.append({'key': key, 'name': key.replace('_', ' ').title(), 'weight': weight, 'score': score,
                             'evidence': list(dict.fromkeys(e for v in entries for e in v['evidence']))})
    measured = [c for c in competencies if c['score'] is not None and c['weight'] > 0]
    total = round(sum(c['score'] * c['weight'] for c in measured) / sum(c['weight'] for c in measured), 2) if measured else None
    return total, competencies


def label(score):
    if score is None:
        return 'Belum terukur'
    return 'Strong Match' if score * 20 >= 85 else 'Good' if score * 20 >= 70 else 'Needs Work' if score * 20 >= 55 else 'Not Ready'
