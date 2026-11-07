"""Compare supplied independent human ratings with AI runs; never enables validated.

Usage: python validation/compare.py private-dataset.json --output report.json
Input data stays outside the repository. See docs/assessor-validation.md.
"""
import argparse
import itertools
import json
from pathlib import Path
from statistics import mean


def kappa(a, b):
    if len(a) != len(b) or not a:
        raise ValueError('Rating vectors must have equal nonzero length.')
    observed = mean((x-y)**2 for x,y in zip(a,b))
    expected = mean((x-y)**2 for x in a for y in b)
    return None if expected == 0 else round(1-observed/expected, 4)


def compare(dataset):
    cases = dataset.get('cases', [])
    if len(cases) < 2:
        raise ValueError('Provide at least two cases; a small sample is not validation.')
    raters = sorted(cases[0].get('human_ratings', {}))
    if len(raters) < 3:
        raise ValueError('Diperlukan skor independen minimal tiga asesor manusia pada setiap kasus.')
    ids = set()
    for c in cases:
        if c['id'] in ids:
            raise ValueError('Duplicate case IDs.')
        ids.add(c['id'])
        if sorted(c.get('human_ratings', {})) != raters:
            raise ValueError('Each case must be rated independently by the same assessors.')
        values = list(c['human_ratings'].values()) + [c.get('consensus_score')] + c.get('ai_runs', [])
        if len(c.get('ai_runs', [])) < 5:
            raise ValueError('Provide at least five independent AI runs per case.')
        if any(type(v) is not int or v not in range(1,6) for v in values):
            raise ValueError('All ratings and agreed consensus scores must be integer 1–5.')
        if c.get('split') != 'test':
            raise ValueError('Only held-out test cases may be compared; exclude calibration cases.')
        if not c.get('transcript') or not c.get('competency'):
            raise ValueError('Every case needs original transcript and competency.')
        if not isinstance(c.get('ai_quotes'), list):
            raise ValueError('ai_quotes is required, including an empty list when no evidence was cited.')
    pairs = [{'raters': [a,b], 'quadratic_weighted_kappa': kappa(
        [c['human_ratings'][a] for c in cases], [c['human_ratings'][b] for c in cases])} for a,b in itertools.combinations(raters,2)]
    consensus = [c['consensus_score'] for c in cases]
    first = [c['ai_runs'][0] for c in cases]
    quotes = [(quote, c['transcript']) for c in cases for quote in c['ai_quotes']]
    valid_quotes = sum(isinstance(q,str) and len(q.strip()) >= 8 and q in text for q,text in quotes)
    groups = {}
    for language in sorted({c.get('language','unknown') for c in cases}):
        group = [c for c in cases if c.get('language','unknown') == language]
        groups[language] = {'n': len(group), 'mean_absolute_error': round(mean(abs(c['ai_runs'][0]-c['consensus_score']) for c in group),4)}
    return {'validated': False, 'purpose': 'descriptive assessor comparison; no automatic selection-validity claim',
        'rubric_version': dataset.get('rubric_version'), 'rubric_sha256': dataset.get('rubric_sha256'),
        'model': dataset.get('model'), 'n': len(cases), 'human_pairs': pairs,
        'ai_vs_consensus_kappa': kappa(first,consensus),
        'within_one_point_percent': round(100*mean(abs(a-b)<=1 for a,b in zip(first,consensus)),2),
        'stable_range_at_most_one_percent': round(100*mean(max(c['ai_runs'])-min(c['ai_runs'])<=1 for c in cases),2),
        'verbatim_quote_percent': round(100*valid_quotes/len(quotes),2) if quotes else None,
        'quote_count': len(quotes), 'language_groups': groups,
        'pending_human_review': ['quote relevance to indicator', 'job relevance', 'sample coverage', 'fairness and STT sensitivity']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args=parser.parse_args()
    try:
        report=compare(json.loads(args.dataset.read_text()))
    except (ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(f'Report saved: {args.output}; validated remains false.')

if __name__ == '__main__':
    main()
