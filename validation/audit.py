"""Audit dataset integrity and readiness; never certifies an assessment."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from validation.kit import digest, require_independent_ratings, write_private
from validation.compare import compare


def audit(dataset):
    dataset_hash = digest(dataset)  # Reject altered snapshots before reporting.
    assessment = dataset.get('assessment', {})
    definitions = assessment.get('competency_definitions', {})
    sources = {s['id'] for s in assessment.get('sources', [])}
    issues = []
    anchors = 0
    for key, definition in definitions.items():
        levels = definition['levels']
        if set(levels) != {'1', '2', '3', '4', '5'}:
            issues.append(f'{key}: incomplete scale')
        for anchor in levels.values():
            anchors += 1
            if not anchor.get('source_ids') or set(anchor['source_ids']) - sources:
                issues.append(f'{anchor["id"]}: missing source mapping')
    cases = dataset['cases']
    test = [c for c in cases if c['split'] == 'test']
    blockers = []
    if not dataset.get('job_reviewed_by_human') or not assessment.get('job_reviewed_by_human'):
        blockers.append('Tinjauan ahli pekerjaan belum tercatat; kompetensi, bobot dan indikator perlu ditinjau.')
    try:
        raters = require_independent_ratings(dataset)
        ratings_error = None
    except (ValueError, KeyError, TypeError) as exc:
        raters = []
        ratings_error = str(exc)
        blockers.append('Penilaian lengkap dari minimal tiga asesor independen belum lolos pemeriksaan: ' + ratings_error)
    comparison = None
    try:
        comparison = compare(dataset)
        comparison_error = None
    except (ValueError, KeyError, TypeError) as exc:
        comparison_error = str(exc)
        blockers.append('Perbandingan AI–konsensus belum dapat dihitung: ' + comparison_error)
    blockers.extend([
        'Kualifikasi, identitas dan independensi asesor harus diverifikasi koordinator.',
        'Kecukupan sampel, relevansi kutipan, fairness dan sensitivitas STT perlu tinjauan terpisah.',
    ])
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'purpose': 'technical integrity and study readiness; not validation of scoring accuracy',
        'validated': False,
        'status': 'comparison_available_pending_expert_interpretation' if comparison else 'pending_human_evidence',
        'dataset_id': dataset['dataset_id'], 'dataset_hash': dataset_hash,
        'rubric_version': dataset['rubric_version'], 'rubric_sha256': dataset['rubric_sha256'],
        'synthetic': dataset.get('synthetic', False),
        'technical_checks': {'snapshot_integrity': 'passed',
            'competency_count': len(definitions), 'anchor_count': anchors,
            'source_mapping_issues': issues,
            'source_mapping_note': 'ID linkage only; does not verify source content or semantic relevance.'},
        'coverage': {'total': len(cases), 'calibration': len(cases)-len(test), 'test': len(test),
            'test_by_competency': dict(Counter(c['competency'] for c in test)),
            'test_by_language': dict(Counter(c['language'] for c in test)),
            'note': 'Counts are descriptive; this pilot is not an adequate validation sample.'},
        'human_evidence': {'complete_raters': raters, 'error': ratings_error,
            'rating_entries': sum(len(c.get('human_ratings', {})) for c in cases)},
        'ai_evidence': {'run_entries': sum(len(c.get('ai_runs', [])) for c in cases)},
        'comparison': comparison, 'comparison_error': comparison_error,
        'pending_requirements': blockers,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = audit(json.loads(args.dataset.read_text()))
        write_private(args.output, json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))
    print(f'Audit: {report["status"]}; validated=false; {args.output}')


if __name__ == '__main__':
    main()
