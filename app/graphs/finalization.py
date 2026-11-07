"""Restartable finalization graph with independent, source-checked AI ratings."""
import hashlib
import json

from sqlalchemy import select

from app.ai import guidebook, orchestrator
from app.ai.job_rubric import evaluation_fields
from app.ai.scoring import verified_scores
from app.db import SessionLocal
from app.models import InterviewSession, InterviewQuestion, InterviewAnswer, SessionCompetency, now
from app.services.events import checkpoint, record
from app.graphs import panel_scoring


STARS = ('situation', 'task', 'action', 'result')


def _fingerprint(session, questions, answers):
    payload = {'assessment': session.script['assessment'],
               'policy': session.script['runtime']['aggregation_policy'],
               'roles': guidebook.panel_roles(session),
               'speaker_by_order': session.script.get('speaker_by_order', {}),
               'questions': [(q.id, q.kind, q.main_order, q.question_text, q.competencies) for q in questions],
               'answers': [(a.id, a.question_id, a.transcript, a.result_payload.get('skipped', False)) for a in answers]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


async def _load(sid, expected=None):
    async with SessionLocal() as db:
        session = await db.get(InterviewSession, sid)
        if session is None:
            raise ValueError('Sesi penilaian tidak ditemukan.')
        if session.status not in ('scoring', 'done'):
            raise ValueError('Sesi tidak sedang dalam penilaian.')
        if session.script.get('runtime', {}).get('aggregation_policy') != panel_scoring.policy_snapshot():
            raise ValueError('Versi kebijakan agregasi sesi tidak didukung.')
        questions = list((await db.scalars(select(InterviewQuestion).where(
            InterviewQuestion.session_id == sid).order_by(InterviewQuestion.main_order, InterviewQuestion.id))).all())
        answers = list((await db.scalars(select(InterviewAnswer).join(InterviewQuestion).where(
            InterviewQuestion.session_id == sid).order_by(InterviewAnswer.id))).all())
        if not questions or {q.id for q in questions} != {a.question_id for a in answers}:
            raise ValueError('Seluruh pertanyaan harus selesai atau dilewati sebelum penilaian.')
        fingerprint = _fingerprint(session, questions, answers)
        if expected is not None and fingerprint != expected:
            raise ValueError('Sumber penilaian berubah; hasil checkpoint tidak dapat diterapkan.')
        return session, questions, answers, fingerprint


def _source_turns(answers):
    return [{'turn_id': f'q{answer.question_id}', 'transcript': answer.transcript}
            for answer in answers if not answer.result_payload.get('skipped')]


def _rubric(assessment, competencies):
    allowed = set(competencies) | {'Kompetensi', '---'}
    return '\n'.join(line for line in assessment['rubric'].splitlines()
                     if not line.startswith('| ') or line.split('|')[1].strip() in allowed)


async def finalize(sid, *, allow_uncertain=False):
    """Execute a pinned graph; callers handle user-visible failure/retry status."""
    from app.graphs.runtime import execute
    async with SessionLocal() as db:
        previous = await db.get(InterviewSession, sid)
        if previous is None:
            return {'session_id': sid, 'status': 'missing'}
    session, questions, answers, source_hash = await _load(sid)
    roles = guidebook.panel_roles(session)
    policy = session.script['runtime']['aggregation_policy']

    async def load_sources(ctx):
        _, current_questions, current_answers, current_hash = await _load(sid, source_hash)
        return {'source_hash': current_hash, 'question_ids': [q.id for q in current_questions],
                'answer_ids': [a.id for a in current_answers], 'roles': roles}

    def initial_node(persona):
        async def rate(ctx):
            source = await ctx.result('load_sources')
            current_session, current_questions, current_answers, _ = await _load(sid, source['source_hash'])
            by_question = {answer.question_id: answer for answer in current_answers}
            units = []
            for main in (q for q in current_questions if q.kind == 'main'):
                group = [q for q in current_questions if q.main_order == main.main_order]
                group_answers = [by_question[q.id] for q in group]
                competencies = panel_scoring.persona_scope(current_session.script['assessment'], persona, main.competencies)
                skipped = all(answer.result_payload.get('skipped', False) for answer in group_answers)
                unit = {'question_id': main.id, 'answer_ids': [a.id for a in group_answers],
                        'competencies': competencies, 'skipped': skipped, 'scores': {},
                        'star': {key: False for key in STARS}, 'feedback': {}}
                if competencies and not skipped:
                    sources = _source_turns(group_answers)
                    transcript = '\n'.join(turn['transcript'] for turn in sources)
                    context = {**guidebook.context_for(current_session, persona),
                               **evaluation_fields(current_session.script['assessment'], competencies),
                               'question': main.question_text, 'transcript': transcript, 'source_turns': sources,
                               'competencies': competencies,
                               'rubric': _rubric(current_session.script['assessment'], competencies),
                               'job_role': current_session.job_role, 'level': current_session.level,
                               'language': current_session.script['settings']['language']}
                    async def evaluate(context=context, transcript=transcript, sources=sources,
                                       competencies=competencies):
                        raw = await orchestrator.evaluate(context)
                        scores = verified_scores(raw['competency_scores'], transcript, competencies,
                                                 sources, assessment=current_session.script['assessment'])
                        return {'scores': scores, 'star': {key: raw.get('star', {}).get(key) is True for key in STARS},
                                'feedback': raw.get('feedback', {})}
                    # No initial evaluator receives another persona's score or review.
                    evaluated = await ctx.operation(f'evaluate:{persona}:{main.id}',
                                                    {'source_hash': source_hash, 'persona': persona,
                                                     'question_id': main.id, 'competencies': competencies}, evaluate)
                    unit.update(evaluated)
                units.append(unit)
            return {'persona': persona, 'source_hash': source_hash, 'units': units}
        return rate

    async def initials(ctx):
        return [await ctx.result(f'initial_{persona}') for persona in roles]

    async def review(ctx):
        all_initial = await initials(ctx)
        differences = panel_scoring.disagreements(all_initial)
        if not differences:
            return {'triggered': False, 'differences': [], 'reviews': []}
        current_session, _, current_answers, _ = await _load(sid, source_hash)
        sources = _source_turns(current_answers)
        reviewed = await panel_scoring.review_differences(
            differences, sources, current_session.script['settings']['language'])
        return {'triggered': True, 'differences': differences, 'reviews': reviewed}

    async def aggregate(ctx):
        current_session, _, _, _ = await _load(sid, source_hash)
        return panel_scoring.aggregate_panel(await initials(ctx), current_session.script['assessment'])

    async def feedback(ctx):
        combined = await ctx.result('aggregate')
        all_initial = await initials(ctx)
        reviewed = await ctx.result('review_differences')
        current_session, _, _, _ = await _load(sid, source_hash)
        return await orchestrator.summarize({
            'evaluations': [{'persona': item['persona'], 'question_id': unit['question_id'],
                             'scores': unit['scores'], 'feedback': unit['feedback']}
                            for item in all_initial for unit in item['units'] if not unit['skipped']],
            'total_score': combined['total_score'], 'coverage': combined['coverage'],
            'aggregation_policy': policy, 'advisory_review': reviewed['reviews'],
            'job_role': current_session.job_role, 'language': current_session.script['settings']['language']})

    async def commit(ctx):
        combined = await ctx.result('aggregate')
        summary = await ctx.result('feedback')
        all_initial = await initials(ctx)
        reviewed = await ctx.result('review_differences')
        await ctx.assert_owned()
        async with SessionLocal() as db:
            current = await db.scalar(select(InterviewSession).where(InterviewSession.id == sid).with_for_update())
            if current.status == 'done':
                return {'session_id': sid, 'status': 'done', 'policy_version': policy['version']}
            if current.status != 'scoring':
                raise ValueError('Sesi tidak lagi dalam penilaian.')
            stored_questions = list((await db.scalars(select(InterviewQuestion).where(
                InterviewQuestion.session_id == sid).order_by(InterviewQuestion.main_order, InterviewQuestion.id))).all())
            stored_answers = list((await db.scalars(select(InterviewAnswer).join(InterviewQuestion).where(
                InterviewQuestion.session_id == sid).order_by(InterviewAnswer.id))).all())
            if _fingerprint(current, stored_questions, stored_answers) != source_hash:
                raise ValueError('Sumber penilaian berubah sebelum penyimpanan hasil.')
            by_answer = {answer.id: answer for answer in stored_answers}
            by_main = {question.id: question for question in stored_questions if question.kind == 'main'}
            stars = {key: False for key in STARS}
            for item in all_initial:
                for unit in item['units']:
                    main = by_main[unit['question_id']]
                    if guidebook.speaker(current, main.main_order) != item['persona']:
                        continue
                    for answer_id in unit['answer_ids']:
                        answer = by_answer[answer_id]
                        answer.eval_status = 'done'
                        answer.feedback = unit['feedback']
                        answer.star = unit['star']
                        answer.competency_scores = unit['scores'] if answer.question_id == main.id else {}
                        for key in STARS:
                            stars[key] |= unit['star'].get(key, False)
            for competency in combined['competencies']:
                stored = await db.get(SessionCompetency, (sid, competency['key']))
                if stored is None:
                    stored = SessionCompetency(session_id=sid, competency=competency['key'], weight=competency['weight'])
                    db.add(stored)
                stored.score = competency['score']
            current.total_score = combined['total_score']
            current.review = {**summary, 'panel_assessment': {
                'policy': policy, 'source_hash': source_hash, 'source_turn_ids': [turn['turn_id'] for turn in _source_turns(stored_answers)],
                'initial_evaluations': all_initial, 'disagreement_review': reviewed,
                'competencies': combined['competencies'], 'panel_results': combined['panel_results'],
                'human_validation': False}}
            current.star_summary = stars
            current.finished_at = now()
            current.error_message = None
            current.status = 'done'
            checkpoint(current, 'completed')
            await record(db, current, 'evaluation_completed', 'evaluation_completed', {
                'coverage': combined['coverage'], 'aggregation_policy': policy['version'], 'graph_thread_id': ctx.thread_id})
            await db.commit()
        return {'session_id': sid, 'status': 'done', 'policy_version': policy['version']}

    nodes = [('load_sources', load_sources)]
    nodes.extend((f'initial_{persona}', initial_node(persona)) for persona in roles)
    nodes.extend([('review_differences', review), ('aggregate', aggregate), ('feedback', feedback), ('commit', commit)])
    return await execute('finalize', sid, f'finalize:{sid}:v1', nodes,
                         input_data={'source_hash': source_hash, 'policy_version': policy['version']},
                         allow_uncertain=allow_uncertain, session_factory=SessionLocal)
