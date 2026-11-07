"""Download, prepare and evaluate a separate reference-based Mohler benchmark."""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import mean
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from validation.kit import canonical_hash, write_private
from validation.external_compare import ranks

REPO = 'nkazi/MohlerASAG'
REVISION = 'dac06732b42d01a5169f543f6d272f1476cced3e'
PROMPT = '''Grade the correctness and completeness of a computer science short answer against the supplied instructor answer. Use a continuous 0–5 scale: 0 incorrect or no meaningful answer; 1 minimal correct content; 2 substantial errors or omissions; 3 partially correct with important omissions; 4 mostly correct with minor omissions; 5 fully correct. Accept equivalent wording and other technically correct answers. Do not reward length or infer leadership/personality. Return JSON with score (number 0–5), rationale (string), evidence (literal substring of student_answer, or empty for a blank answer). This is an external academic answer-grading benchmark, not an interview competency rubric.'''


def save_json(path, value):
    write_private(path, json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def normalize(row):
    case_id = row['id']
    if not re.fullmatch(r'E\d{2}\.Q\d{2}\.A\d{2}', case_id):
        raise ValueError('Unexpected source ID.')
    exercise = int(case_id[1:3])
    maximum = 10 if exercise in (11, 12) else 5
    scores = [float(row[k]) for k in ('score_grader_1', 'score_grader_2')]
    avg = float(row['score_avg'])
    if any(not math.isfinite(s) or not 0 <= s <= maximum for s in scores):
        raise ValueError(f'Invalid original grader score: {case_id}')
    if not math.isfinite(avg) or not 0 <= avg <= 5:
        raise ValueError(f'Invalid source average: {case_id}')
    average_matches = math.isclose(avg, mean(scores)*5/maximum, abs_tol=1e-5)
    return {'id': case_id, 'question_id': case_id.rsplit('.', 1)[0],
        'question': row['question'], 'instructor_answer': row['instructor_answer'],
        'student_answer': row['student_answer'],
        'original_grader_scores': scores, 'original_scale_max': maximum, 'human_score_0_5': avg,
        'average_matches_normalized_graders': average_matches}


def download(output):
    import httpx
    output = Path(output)
    if output.exists():
        raise ValueError('Output directory already exists; choose a new directory.')
    files = []
    rows = []
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        # Download before writing metadata, so a failed fetch does not claim completion.
        for name in ('README.md', 'data/raw-oe-00001.parquet', 'data/raw-ce-00001.parquet'):
            url = f'https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{name}'
            response = client.get(url)
            response.raise_for_status()
            path = output / 'source' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as file:
                path.chmod(0o600)
                file.write(response.content)
            files.append({'file': name, 'url': url, 'sha256': hashlib.sha256(response.content).hexdigest()})
    import pyarrow.parquet as pq
    for name, split in [('raw-oe-00001.parquet', 'open_ended'), ('raw-ce-00001.parquet', 'close_ended')]:
        batch = pq.read_table(output / 'source/data' / name).to_pylist()
        rows.extend({**normalize(row), 'source_split': split} for row in batch)
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate IDs in source.')
    save_json(output / 'dataset.json', {'source': REPO, 'revision': REVISION, 'validated': False, 'cases': rows})
    save_json(output / 'manifest.json', {'downloaded_at': datetime.now(timezone.utc).isoformat(),
        'source': f'https://huggingface.co/datasets/{REPO}', 'revision': REVISION,
        'license_declared_by_distributor': 'CC BY 4.0',
        'attribution': 'Michael Mohler, Razvan Bunescu and Rada Mihalcea (2011), Learning to Grade Short Answer Questions using Semantic Similarity Measures and Dependency Graph Alignments. Hugging Face conversion: nkazi/MohlerASAG.',
        'paper': 'https://aclanthology.org/P11-1076/',
        'license_url': 'https://creativecommons.org/licenses/by/4.0/',
        'files': files, 'counts': dict(Counter(r['source_split'] for r in rows)),
        'average_discrepancy_count': sum(not r['average_matches_normalized_graders'] for r in rows),
        'changes': 'Preserved raw texts and grader scores; added question ID and original scale metadata. Existing source score_avg retained on 0–5 scale.',
        'participant_ids': 'Not supplied. AXX is an answer index, not a verified participant identity.',
        'validated': False})
    print(f'Downloaded {len(rows)} human-rated answers to {output}')


def prepare(dataset_path, output, limit):
    dataset = json.loads(Path(dataset_path).read_text())
    rows = [r for r in dataset['cases'] if r['source_split'] == 'open_ended' and r['average_matches_normalized_graders']]
    # Fixed content-ID ordering, independent of human labels; do not cherry-pick by AI outcome.
    rows.sort(key=lambda r: hashlib.sha256(r['id'].encode()).hexdigest())
    if not 3 <= limit <= len(rows):
        raise ValueError('Limit must be between 3 and available open-ended answers.')
    rows = rows[:limit]
    output = Path(output)
    if output.exists():
        raise ValueError('Output directory already exists.')
    blind = {'source': dataset['source'], 'revision': dataset['revision'],
        'selection': 'Exclude source averages inconsistent with normalized graders; then SHA256(case ID) ascending, open-ended only. No AI-outcome-based selection.',
        'cases': [{k: r[k] for k in ('id', 'question_id', 'question', 'instructor_answer', 'student_answer')} for r in rows]}
    save_json(output / 'inputs.json', blind)
    save_json(output / 'labels.json', {'inputs_sha256': canonical_hash(blind),
        'cases': [{k: r[k] for k in ('id', 'human_score_0_5', 'original_grader_scores', 'original_scale_max')} for r in rows]})
    print(f'Prepared {limit} blind inputs and separate original human labels in {output}')


async def run(inputs_path, output):
    from app.ai.model_router import complete
    from app.config import settings
    inputs = json.loads(Path(inputs_path).read_text())
    output = Path(output)
    if output.exists():
        raise ValueError('Results directory already exists; choose a new run.')
    output.mkdir(parents=True)
    save_json(output / 'run.json', {'inputs_sha256': canonical_hash(inputs), 'model': settings.model_deep,
        'prompt_sha256': hashlib.sha256(PROMPT.encode()).hexdigest(), 'prompt': PROMPT,
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'started_at': datetime.now(timezone.utc).isoformat(), 'human_scores_in_prompt': False,
        'evaluator': 'separate reference-based benchmark using app.ai.model_router.complete; not production interview evaluator',
        'validated': False})
    for case in inputs['cases']:
        raw = await complete(PROMPT, {k: case[k] for k in ('question', 'instructor_answer', 'student_answer')}, deep=True, tokens=500)
        score = raw.get('score')
        if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 5:
            raise ValueError(f'Invalid model score: {case["id"]}')
        quote = raw.get('evidence')
        if not isinstance(quote, str) or (case['student_answer'].strip() and not quote.strip()) or quote not in case['student_answer']:
            raise ValueError(f'Invalid evidence: {case["id"]}')
        if not isinstance(raw.get('rationale'), str) or not raw['rationale'].strip():
            raise ValueError('Missing model rationale.')
        save_json(output / f'{case["id"]}.json', {'id': case['id'], **raw})
        print('Scored:', case['id'], flush=True)


def report(inputs_path, labels_path, run_dir, output):
    inputs = json.loads(Path(inputs_path).read_text())
    labels = json.loads(Path(labels_path).read_text())
    run_dir = Path(run_dir)
    run_meta = json.loads((run_dir / 'run.json').read_text())
    if labels['inputs_sha256'] != canonical_hash(inputs) or run_meta['inputs_sha256'] != canonical_hash(inputs):
        raise ValueError('Input/labels/run hash mismatch.')
    by_id = {r['id']: r for r in labels['cases']}
    pairs = []
    for case in inputs['cases']:
        result = json.loads((run_dir / f'{case["id"]}.json').read_text())
        if result['id'] != case['id']:
            raise ValueError('Prediction ID mismatch.')
        human, ai = by_id[case['id']]['human_score_0_5'], result['score']
        if any(type(s) not in (int, float) or not math.isfinite(s) or not 0 <= s <= 5 for s in (human, ai)):
            raise ValueError('Invalid paired scores.')
        pairs.append({'id': case['id'], 'human_score': human, 'ai_score': ai, 'absolute_error': abs(human-ai)})
    if len(pairs) < 3:
        raise ValueError('At least three completed cases required.')
    a, b = ranks([p['human_score'] for p in pairs]), ranks([p['ai_score'] for p in pairs])
    da, db = [v-mean(a) for v in a], [v-mean(b) for v in b]
    den = math.sqrt(sum(v*v for v in da)*sum(v*v for v in db))
    save_json(output, {'validated': False, 'n': len(pairs), 'model': run_meta['model'],
        'spearman_rho': sum(x*y for x,y in zip(da, db))/den if den else None,
        'mae_0_5': mean(p['absolute_error'] for p in pairs),
        'within_one_point_percent': 100*mean(p['absolute_error'] <= 1 for p in pairs),
        'run': run_meta, 'pairs': pairs,
        'limitations': ['Separate reference-based scorer, not validation of production interview evaluator.',
            'English computer-science educational answers only; not leadership/non-IT validation.',
            'Participant identity unavailable; no participant-disjoint split claim.',
            'Public data may be present in model training. Pilot has no inferential validity claim.']})
    print('Report saved:', output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('download'); p.add_argument('--output', type=Path, required=True)
    p = commands.add_parser('prepare'); p.add_argument('dataset', type=Path); p.add_argument('--output', type=Path, required=True); p.add_argument('--limit', type=int, default=50)
    p = commands.add_parser('run'); p.add_argument('inputs', type=Path); p.add_argument('--output', type=Path, required=True); p.add_argument('--run-paid', action='store_true')
    p = commands.add_parser('report'); p.add_argument('inputs', type=Path); p.add_argument('labels', type=Path); p.add_argument('run_dir', type=Path); p.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'download': download(args.output)
        elif args.command == 'prepare': prepare(args.dataset, args.output, args.limit)
        elif args.command == 'run':
            if not args.run_paid: parser.error('API credits required; explicitly pass --run-paid.')
            asyncio.run(run(args.inputs, args.output))
        else: report(args.inputs, args.labels, args.run_dir, args.output)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
