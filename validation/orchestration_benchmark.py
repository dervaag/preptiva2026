"""Reproducible synthetic legacy/graph overhead comparison; never calls providers.

Run with Python 3.12: python validation/orchestration_benchmark.py --output /tmp/orchestration-benchmark.json
Each sample uses a fresh subprocess and temporary SQLite database. Provider latency,
token usage, monetary cost, speech quality and assessment accuracy are not measured.
"""
import argparse
import asyncio
from collections import Counter
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
from statistics import mean, median
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_VERSION = 'orchestration-synthetic-v1'
CV = 'Saya mengerjakan proyek kuliah sistem inventaris dan menjadi pengurus organisasi mahasiswa.'
JD = 'Mengembangkan produk, memeriksa kualitas hasil, dan bekerja bersama tim lintas fungsi.'
ANSWER = 'Saya membagi tugas dalam proyek kuliah, memeriksa hasil bersama tim, dan memperbaiki kesalahan berdasarkan masukan.'
QUESTION_WORDING = ['Bagaimana Anda membagi tugas dalam proyek kuliah itu?',
                    'Pemeriksaan apa yang memastikan hasil sistem inventaris benar?',
                    'Ceritakan keputusan ketika prioritas organisasi berubah.']


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


async def sample(engine_name, panel_size, directory):
    # Settings and DB are created only after this explicit isolation. An IDE .env
    # cannot route this benchmark to the user's database or paid providers.
    os.environ.update({'DATABASE_URL': f'sqlite+aiosqlite:///{directory}/benchmark.db',
        'APP_ENV': 'development', 'REDIS_URL': '', 'AI_MOCK': 'false', 'COOKIE_SECURE': 'false',
        'SECRET_KEY': 'isolated-synthetic-benchmark-only', 'PUBLIC_ORIGIN': '',
        'OPENAI_API_KEY': '', 'ELEVENLABS_API_KEY': '', 'REALTIME_VOICE_ENABLED': 'false',
        'ORCHESTRATION_ENGINE': engine_name})
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from unittest.mock import patch
    import httpx
    from sqlalchemy import select
    from app.ai import errors, guidebook, model_router, orchestrator, speech
    from app.ai.assessment import snapshot as assessment_snapshot
    from app.ai.blueprint import blueprint
    from app.api import sessions
    from app.db import init_db, SessionLocal, engine
    from app.graphs import panel_scoring, policy
    from app.graphs.models import GraphExecution, GraphOperation
    from app.models import InterviewSession, InterviewAnswer, SessionCompetency, User
    from app.services.interview import turns
    from app.worker.tasks import prepare_session, finalize_session

    calls = Counter()
    async def forbid_network(*args, **kwargs):
        raise AssertionError('External provider access is disabled in this synthetic benchmark.')
    async def parse(cv, jd):
        calls['document_extraction'] += 1
        return {'cv_summary': {'evidence': [{'kind': 'project', 'quote': cv}]},
                'jd_summary': {'responsibilities': [jd]}}
    async def questions(context, history):
        calls['question_generation'] += 1
        plan = blueprint(3, context['uuid'], context['panel'], context['guidebook'], context['assessment'])
        return {'intro': 'Selamat datang.', 'closing': 'Terima kasih.', 'plan': plan,
                'questions': [{'slot': slot['slot'], 'category': 'example', 'question_text': QUESTION_WORDING[i],
                               'competencies': slot['competencies'], 'expected_points': ['Tindakan pribadi'], 'anchor_id': 'cv1'}
                              for i, slot in enumerate(plan)]}
    async def respond(context):
        calls['response'] += 1
        return {'action': 'next', 'response_text': 'Terima kasih.', 'source_refs': []}
    async def adapt(context):
        calls['adaptation'] += 1
        fact = context['context_packet']['candidate_facts'][-1]
        return {**context['planned_question'], 'anchor_id': 'cv1',
                'source_refs': [{'turn_id': fact['source_turn_id'], 'quote': fact['quote']}]}
    async def evaluate(context):
        calls['evaluation'] += 1
        return {'competency_scores': {key: {'score': 4, 'evidence_sufficiency': 'sufficient',
                                          'evidence': [ANSWER], 'rationale': 'Synthetic software fixture.'}
                                      for key in context['competencies']},
                'feedback': {'strengths': ['Contoh tindakan tersedia.'], 'improvements': [], 'better_answer_tip': 'Jelaskan dampak.'},
                'star': {'situation': True, 'task': True, 'action': True, 'result': False}}
    async def summarize(context):
        calls['summary'] += 1
        return {'summary': 'Hasil sintetis untuk pemeriksaan perangkat lunak.', 'strengths': [],
                'improvements': [], 'study_recommendations': []}
    async def transcribe(*args, **kwargs):
        calls['stt'] += 1
        return ANSWER
    async def synthesize(text, persona, session_id, name, **kwargs):
        calls['tts'] += 1
        return f'/api/sessions/{session_id}/audio/{name}'
    async def differences(items, source_turns, language):
        calls['disagreement_review'] += 1
        return panel_scoring.validate_reviews({}, items, source_turns)

    try:
        with ExitStack() as patches:
            for module in (errors, model_router, speech):
                patches.enter_context(patch.object(module, 'provider_post', forbid_network))
            patches.enter_context(patch.object(httpx.AsyncClient, 'send', forbid_network))
            for name, callback in {'parse_documents': parse, 'build_questions': questions, 'respond': respond,
                                   'adapt_question': adapt, 'evaluate': evaluate, 'summarize': summarize}.items():
                patches.enter_context(patch.object(orchestrator, name, callback))
            patches.enter_context(patch.object(speech, 'transcribe', transcribe))
            patches.enter_context(patch.object(speech, 'optional_synthesize', synthesize))
            patches.enter_context(patch.object(speech, 'synthesize', synthesize))
            patches.enter_context(patch.object(panel_scoring, 'review_differences', differences))
            await init_db()
            roles = ['hr', 'user', 'manager'][:panel_size]
            assessment = assessment_snapshot('hr', roles)
            async with SessionLocal() as db:
                user = User(email='synthetic-benchmark@example.com', name='Synthetic Benchmark', password_hash='unused')
                db.add(user); await db.flush()
                session = InterviewSession(uuid='00000000-0000-4000-8000-000000000001', user_id=user.id,
                    candidate_name='Synthetic Benchmark', gender='male', age=22, job_role='Engineer', level='junior',
                    industry='Technology', company='', job_description=JD, cv_text=CV, interviewer='hr', question_count=3,
                    answer_seconds=90, max_followups=1, status='preparing',
                    script={'runtime': policy.snapshot(engine_name), 'assessment': assessment, 'guidebook': guidebook.snapshot(),
                            'settings': {'language': 'id', 'panel': roles, 'career_stage': 'fresh_graduate', 'retry_limit': 2,
                                         'dynamic_questions': True, 'streaming_voice': False, 'evidence_policy': '2026-11-07.2'}})
                db.add(session); await db.flush()
                for key, weight in assessment['weights'].items():
                    db.add(SessionCompetency(session_id=session.id, competency=key, weight=weight))
                await db.commit()
                sid, uuid, owner = session.id, session.uuid, user.id
            phases = {}
            started = time.perf_counter()
            await prepare_session({}, sid)
            phases['prepare_ms'] = (time.perf_counter() - started) * 1000
            async with SessionLocal() as db:
                session = await db.get(InterviewSession, sid)
                if session.status != 'ready':
                    raise RuntimeError(f'Synthetic preparation failed ({engine_name}, {panel_size}).')
                session.status = 'running'; await db.commit()
            phase_started = time.perf_counter()
            for index in range(3):
                async with SessionLocal() as db:
                    session = await db.get(InterviewSession, sid)
                    rows, answers = await turns(db, session)
                    answered = {answer.question_id for answer in answers}
                    current = next(question for question in rows if question.id not in answered)
                    question_id = current.id
                value = await sessions.process_answer(uuid, owner, question_id,
                    b'synthetic-audio' if index != 1 else b'', 'answer.wav', 1000, 0, 0, False,
                    text_answer=ANSWER if index == 1 else None)
                if value['action'] != 'next':
                    raise AssertionError('Fixture unexpectedly generated a follow-up.')
            phases['answer_turns_ms'] = (time.perf_counter() - phase_started) * 1000
            async with SessionLocal() as db:
                session = await db.get(InterviewSession, sid)
                session.status = 'scoring'; await db.commit()
            phase_started = time.perf_counter()
            await finalize_session({}, sid)
            phases['finalize_ms'] = (time.perf_counter() - phase_started) * 1000
            async with SessionLocal() as db:
                session = await db.get(InterviewSession, sid)
                if session.status != 'done':
                    raise RuntimeError(f'Synthetic finalization failed ({engine_name}, {panel_size}).')
                rows, answers = await turns(db, session)
                assert len(rows) == len(answers) == 3
                assert [answer.result_payload['input_mode'] for answer in answers] == ['audio', 'text', 'audio']
                executions = list((await db.scalars(select(GraphExecution))).all())
                operations = list((await db.scalars(select(GraphOperation))).all())
                traces = [{'thread': row.thread_id, 'operation': row.operation_key, 'status': row.status,
                           'attempts': row.attempts, 'duration_ms': row.duration_ms, 'telemetry': row.telemetry}
                          for row in operations]
                assert all(row.status == 'succeeded' for row in executions)
                result = {'engine': engine_name, 'panel_size': panel_size, 'ok': True,
                          'phases_ms': {key: round(value, 3) for key, value in phases.items()},
                          'total_ms': round(sum(phases.values()), 3), 'logical_provider_steps': dict(calls),
                          'graph_execution_count': len(executions), 'graph_operations': traces,
                          'answer_count': len(answers), 'total_score': session.total_score,
                          'aggregation_policy': policy.aggregation_version(session),
                          'provider_tokens': None, 'monetary_cost': None, 'actual_provider_requests': 0,
                          'real_audio_transport_measured': False}
            return result
    finally:
        await engine.dispose()


def source_manifest():
    paths = [*ROOT.glob('app/graphs/*.py'), ROOT / 'app/api/sessions.py', ROOT / 'app/worker/tasks.py',
             ROOT / 'app/ai/model_router.py', Path(__file__).resolve()]
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(paths)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(tempfile.gettempdir()) / 'preptiva-orchestration-benchmark.json')
    parser.add_argument('--repeats', type=int, default=3, choices=range(1, 11))
    parser.add_argument('--internal-case', choices=['legacy:1', 'legacy:3', 'langgraph:1', 'langgraph:3'], help=argparse.SUPPRESS)
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        parser.error('Use Python 3.12+, matching the deployment runtime.')
    if args.internal_case:
        engine_name, size = args.internal_case.split(':')
        with tempfile.TemporaryDirectory(prefix='preptiva-orchestration-') as directory:
            result = asyncio.run(sample(engine_name, int(size), directory))
        print(json.dumps(result, ensure_ascii=False))
        return
    manifest = source_manifest()
    samples = []
    # Alternate engines per repetition so order is visible and shared host load
    # does not consistently favor the baseline. Subprocess/import time is excluded.
    for index in range(args.repeats):
        for size in (1, 3):
            for engine_name in (('legacy', 'langgraph') if index % 2 == 0 else ('langgraph', 'legacy')):
                process = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--internal-case', f'{engine_name}:{size}'],
                                         capture_output=True, text=True, timeout=120, cwd=ROOT)
                if process.returncode:
                    # Child has sanitized env; keep the trace available for local diagnosis.
                    sys.stderr.write(process.stderr)
                    raise RuntimeError(f'Synthetic sample failed: {engine_name}, panel={size}.')
                samples.append({**json.loads(process.stdout), 'repetition': index + 1})
    comparisons = []
    for size in (1, 3):
        grouped = {engine_name: [row for row in samples if row['panel_size'] == size and row['engine'] == engine_name]
                   for engine_name in ('legacy', 'langgraph')}
        medians = {key: median(row['total_ms'] for row in rows) for key, rows in grouped.items()}
        comparisons.append({'panel_size': size, 'median_ms': medians,
                            'graph_minus_legacy_ms': round(medians['langgraph'] - medians['legacy'], 3),
                            'mean_ms': {key: round(mean(row['total_ms'] for row in rows), 3) for key, rows in grouped.items()},
                            'logical_provider_steps_per_sample': {key: rows[0]['logical_provider_steps'] for key, rows in grouped.items()}})
    if manifest != source_manifest():
        raise RuntimeError('Source changed during the benchmark; rerun after edits finish to compare one implementation.')
    report = {'fixture_version': FIXTURE_VERSION, 'created_at': datetime.now(timezone.utc).isoformat(),
              'fixture_sha256': digest({'cv': CV, 'jd': JD, 'answer': ANSWER, 'wording': QUESTION_WORDING}),
              'source_sha256': digest(manifest), 'source_files': manifest,
              'python': platform.python_version(), 'platform': platform.platform(), 'repeats': args.repeats,
              'process_per_sample': True, 'cold_graph_initialization_included': True,
              'synthetic': True, 'actual_provider_requests': 0, 'provider_tokens': None, 'monetary_cost': None,
              'quality_or_validity_claim': False,
              'measurement_scope': 'Application/graph/database overhead with immediate synthetic providers and cold graph initialization. Process startup and imports before stages are excluded; lazy imports inside stages remain included. Logical steps are orchestrator invocations, not actual model requests. Provider/network latency, token use, prices and audio transport are unmeasured.',
              'comparisons': comparisons, 'samples': samples}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(args.output), 'actual_provider_requests': 0, 'comparisons': comparisons}, indent=2))


if __name__ == '__main__':
    main()
