"""Compare paired external scores without converting them to Preptiva ratings."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from validation.kit import write_private


def ranks(values):
    ordered = sorted(set(values))
    result = {}
    offset = 0
    for value in ordered:
        count = values.count(value)
        result[value] = offset + (count + 1) / 2
        offset += count
    return [result[v] for v in values]


def compare_rows(rows):
    if len(rows) < 3:
        raise ValueError('At least three paired cases required; this minimum is not adequate validation.')
    if any(not r.get('case_id') or not r.get('participant_id') for r in rows):
        raise ValueError('Original case and participant IDs required.')
    if len({r['case_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate case IDs.')
    if len({r.get('target') for r in rows}) != 1 or not rows[0].get('target'):
        raise ValueError('Compare one documented target at a time.')
    if any(r.get('split') != 'test' for r in rows):
        raise ValueError('Only held-out test cases may be compared.')
    scores = []
    for field in ('human_score', 'ai_score'):
        values = [float(r[field]) for r in rows]
        if not all(math.isfinite(v) for v in values):
            raise ValueError('Scores must be finite; missing values must not become zero.')
        scores.append(ranks(values))
    a, b = scores
    da, db = [v-mean(a) for v in a], [v-mean(b) for v in b]
    denominator = math.sqrt(sum(v*v for v in da)*sum(v*v for v in db))
    rho = sum(x*y for x,y in zip(da,db))/denominator if denominator else None
    return {'validated': False, 'purpose': 'external rank association, not EM rubric validation',
        'target': rows[0]['target'], 'n_cases': len(rows),
        'n_participants': len({r['participant_id'] for r in rows}),
        'spearman_rho': rho,
        'limitations': ['Association is not score agreement or proof of validity.',
            'Repeated participants are dependent; no inferential confidence interval is computed.',
            'Human annotation protocol, target equivalence and split leakage require manual review.',
            'Original human scales are preserved; no conversion into Preptiva competency ratings.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scores', type=Path)
    parser.add_argument('--provenance', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        provenance = json.loads(args.provenance.read_text())
        required = ('source_url', 'source_revision', 'permission_reference', 'human_annotation_protocol',
                    'target_definition', 'human_scale', 'ai_scale', 'model', 'prompt_sha256', 'split_protocol')
        if any(not isinstance(provenance.get(k), str) or not provenance[k].strip() for k in required):
            raise ValueError('Complete source, permission, model, prompt and split provenance first.')
        if provenance.get('use_permitted') is not True or provenance.get('labels_hidden_from_ai') is not True:
            raise ValueError('Record permitted use and independent AI evaluation first.')
        with args.scores.open(newline='') as file:
            report = compare_rows(list(csv.DictReader(file)))
        report['provenance'] = provenance
        report['input_sha256'] = hashlib.sha256(args.scores.read_bytes()).hexdigest()
        write_private(args.output, json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))
    print(f'External comparison saved: {args.output}; validated=false')


if __name__ == '__main__':
    main()
