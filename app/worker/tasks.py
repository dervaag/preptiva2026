import asyncio
from sqlalchemy import select
from app.db import SessionLocal
from app.models import InterviewSession, InterviewQuestion, InterviewAnswer, SessionCompetency, now
from app.ai import orchestrator, speech
from app.ai import guidebook
from app.ai.feedback import feedback_language
from app.ai.blueprint import blueprint, PERSONAS
from app.ai.scoring import verified_scores, aggregate, coverage
from app.ai.job_rubric import evaluation_fields
from app.services.events import record, checkpoint
from app.services.locks import local_lock
from app.log import emit, session_var
from app.ai.errors import ProviderError
from app.config import settings
from app.graphs.policy import enabled as graph_enabled


async def fail(sid, stage, reason=None):
    async with SessionLocal() as db:
        session = await db.get(InterviewSession, sid)
        if session and session.status not in ('done', 'failed'):
            session.status = 'failed'
            session.error_message = (f'{stage} gagal. {reason}' if reason else f'{stage} gagal. Periksa konfigurasi provider dan log server, lalu buat sesi baru.')[:255]
            session.finished_at = now()
            await db.commit()


async def prepare_session(ctx, sid):
    async with SessionLocal() as db:
        session = await db.get(InterviewSession, sid)
        use_graph = session is not None and graph_enabled(session)
    if use_graph:
        from app.graphs.preparation import prepare
        return await _graph_job(sid, 'prepare', prepare)
    return await _prepare_legacy(ctx, sid)


async def _prepare_legacy(ctx, sid):
    token = session_var.set(sid)
    try:
        async with SessionLocal() as db:
            session = await db.get(InterviewSession, sid)
            if not session or session.status != 'preparing':
                return
            parsed = await orchestrator.parse_documents(session.cv_text, session.job_description)
            roles = guidebook.panel_roles(session)
            history = {p: [] for p in roles}
            previous = (await db.execute(select(InterviewQuestion, InterviewSession).join(InterviewSession).where(
                InterviewSession.user_id == session.user_id, InterviewSession.id != sid,
                InterviewQuestion.kind == 'main').order_by(InterviewQuestion.id.desc()).limit(140))).all()
            for q, old_session in previous:
                role = guidebook.speaker(old_session, q.main_order)
                if role in history and len(history[role]) < 35:
                    history[role].append(q.question_text)
            candidate_profile = guidebook.profile(parsed['cv_summary'], session.cv_text,
                session.script['settings'].get('career_stage', 'auto'))
            context = {**parsed, 'uuid': session.uuid, 'job_role': session.job_role, 'level': session.level,
                       'industry': session.industry, 'company': session.company, 'interviewer': session.interviewer,
                       'panel': roles, 'panel_members': [PERSONAS[p] for p in roles],
                       'candidate_profile': candidate_profile, 'guidebook': session.script.get('guidebook') or guidebook.snapshot(),
                       'question_count': session.question_count, 'assessment':session.script['assessment'],
                       'language': session.script['settings']['language']}
            prepared = await orchestrator.build_questions(context, history)
            plan = prepared.get('plan') or blueprint(session.question_count, session.uuid, roles, context['guidebook'], session.script['assessment'])
            speakers = {str(s['main_order']): s['interviewer'] for s in plan}
            closing_persona = speakers[str(session.question_count)]
            dynamic = session.script.get('settings', {}).get('dynamic_questions', False)
            utterances = [('intro.mp3', prepared['intro'], roles[0]), ('closing.mp3', prepared['closing'], closing_persona)]
            utterances += [(f'q{i}.mp3', q['question_text'], speakers[str(i)]) for i, q in enumerate(prepared['questions'], 1)
                           if not dynamic or i == 1]
            streaming = session.script['settings'].get('streaming_voice', False)
            urls = [None]*len(utterances) if streaming else await asyncio.gather(*(speech.optional_synthesize(text, persona, session.uuid, name,
                timeout=settings.tts_prepared_timeout_sec) for name, text, persona in utterances))
            if streaming:
                urls[0] = f'/api/sessions/{session.uuid}/speech/intro/0'
                urls[1] = f'/api/sessions/{session.uuid}/speech/closing/0'
            await db.refresh(session)
            if session.status != 'preparing':
                return
            session.cv_summary = parsed['cv_summary']
            session.jd_summary = parsed['jd_summary']
            session.script = {**session.script, 'intro': {'text': prepared['intro'], 'audio_url': urls[0], 'persona': PERSONAS[roles[0]]},
                'closing': {'text': prepared['closing'], 'audio_url': urls[1], 'persona': PERSONAS[closing_persona]}, 'fillers': [],
                'candidate_profile': candidate_profile, 'speaker_by_order': speakers,
                'question_plan': {str(s['main_order']): s for s in plan},
                'question_provenance': {str(i): {'anchor_id': q.get('anchor_id', ''), 'interviewer': speakers[str(i)],
                    'conversation_turns': 0} for i, q in enumerate(prepared['questions'], 1)}}
            for i, q in enumerate(prepared['questions'], 1):
                fields = {key: q[key] for key in ('slot', 'category', 'question_text', 'expected_points', 'competencies')}
                audio_url = dict(zip((u[0] for u in utterances), urls)).get(f'q{i}.mp3')
                db.add(InterviewQuestion(session_id=sid, main_order=i, audio_file=f'q{i}.mp3' if audio_url else None, **fields))
            checkpoint(session, 'ready', active_panelist=roles[0], remaining_seconds=session.answer_seconds)
            await record(db, session, 'ready', 'session_prepared', {'guidebook_version': context['guidebook']['version']})
            session.status = 'ready'
            await db.commit()
    except Exception as exc:
        emit('job_failed', job='prepare_session', error_type=type(exc).__name__)
        await fail(sid, 'Persiapan wawancara', str(exc) if isinstance(exc, ProviderError) else None)
    finally:
        session_var.reset(token)


async def finalize_session(ctx, sid):
    async with SessionLocal() as db:
        session = await db.get(InterviewSession, sid)
        use_graph = session is not None and graph_enabled(session)
    if use_graph:
        from app.graphs.finalization import finalize
        return await _graph_job(sid, 'finalize', finalize)
    async with local_lock(('evaluation', sid)):
        await _finalize_session(ctx, sid)


async def _graph_job(sid, kind, callback):
    token = session_var.set(sid)
    try:
        return await callback(sid)
    except Exception as exc:
        from app.graphs.runtime import GraphBusy, GraphOperationUncertain
        if isinstance(exc, GraphBusy):
            return  # Another worker owns this exact graph; do not fail its session.
        emit('job_failed', job='graph_' + kind, error_type=type(exc).__name__)
        async with SessionLocal() as db:
            session = await db.scalar(select(InterviewSession).where(InterviewSession.id == sid).with_for_update())
            expected = 'preparing' if kind == 'prepare' else 'scoring'
            if session and session.status == expected:
                session.status = 'preparation_failed' if kind == 'prepare' else 'evaluation_failed'
                session.error_message = ('Persiapan belum selesai. Data tersimpan; coba siapkan ulang.' if kind == 'prepare'
                    else 'Penilaian belum selesai. Jawaban tersimpan; coba nilai ulang.')
                if isinstance(exc, GraphOperationUncertain):
                    session.error_message = 'Status pemrosesan sebelumnya belum dapat dipastikan. Data tersimpan; hubungi pengelola untuk melanjutkan.'
                await record(db, session, f'graph_error:{kind}:{now().timestamp()}', 'graph_failed', {'kind': kind, 'error_type': type(exc).__name__})
                await db.commit()
    finally:
        session_var.reset(token)


async def resume_graph_turn(ctx, input_id):
    from app.graphs.turn import resume
    from app.graphs.runtime import GraphBusy
    try:
        return await resume(input_id)
    except GraphBusy:
        return
    except Exception as exc:
        emit('graph_recovery_failed', input_id=input_id, error_type=type(exc).__name__)


async def recover_graph_jobs(ctx):
    """Requeue abandoned work after a worker restart; never restart media capture."""
    from app.graphs.models import GraphExecution
    from app.models import GraphTurnInput
    from app.graphs.turn import thread_key
    from app.graphs.policy import UnsupportedGraphVersion
    async with SessionLocal() as db:
        sessions = list((await db.scalars(select(InterviewSession).where(
            InterviewSession.status.in_(['preparing', 'ready', 'scoring', 'running', 'done'])))).all())
        planned = set()
        for session in sessions:
            try:
                supported = graph_enabled(session)
            except UnsupportedGraphVersion:
                continue
            if not supported:
                continue
            executions = list((await db.scalars(select(GraphExecution).where(GraphExecution.session_id == session.id))).all())
            active = any(r.lease_until and r.lease_until > now() for r in executions)
            if active:
                continue
            if session.status in ('preparing', 'scoring'):
                planned.add(('prepare_session' if session.status == 'preparing' else 'finalize_session', session.id))
            for run in executions:
                if run.status == 'succeeded':
                    continue
                if run.kind == 'prepare' and session.status in ('ready', 'running', 'scoring', 'done'):
                    planned.add(('prepare_session', session.id))
                elif run.kind == 'finalize' and session.status == 'done':
                    planned.add(('finalize_session', session.id))
            inputs = list((await db.scalars(select(GraphTurnInput).where(GraphTurnInput.session_id == session.id,
                GraphTurnInput.status.in_(['pending', 'completed'])))).all())
            for item in inputs:
                key = thread_key(session.id, item.question_id, item.attempt, item.input_hash)
                run = next((r for r in executions if r.thread_id == key), None)
                if not run or run.status == 'succeeded':
                    continue
                can_resume = session.status == 'running' and session.script.get('checkpoint', {}).get('phase') != 'interrupted'
                if item.status == 'completed' or (can_resume and (run.status in ('running', 'pending') or run.error_type == 'CancelledError')):
                    planned.add(('resume_graph_turn', item.id))
    for name, identifier in sorted(planned):
        if ctx.get('redis'):
            await ctx['redis'].enqueue_job(name, identifier)
        else:
            await globals()[name](ctx, identifier)


async def _finalize_session(ctx, sid):
    token = session_var.set(sid)
    try:
        async with SessionLocal() as db:
            session = await db.scalar(select(InterviewSession).where(InterviewSession.id == sid).with_for_update())
            if not session or session.status != 'scoring':
                return
            questions = list((await db.scalars(select(InterviewQuestion).where(InterviewQuestion.session_id == sid).order_by(InterviewQuestion.main_order, InterviewQuestion.id))).all())
            answers = list((await db.scalars(select(InterviewAnswer).join(InterviewQuestion).where(InterviewQuestion.session_id == sid))).all())
            by_question = {a.question_id: a for a in answers}
            evaluations = []
            stars = {k: False for k in ('situation', 'task', 'action', 'result')}
            for main in (q for q in questions if q.kind == 'main'):
                persona = guidebook.speaker(session, main.main_order)
                group = [q for q in questions if q.main_order == main.main_order]
                group_answers = [by_question[q.id] for q in group if q.id in by_question]
                transcript = '\n'.join(a.transcript for a in group_answers)
                source_turns = [{'turn_id': f'q{a.question_id}', 'transcript': a.transcript} for a in group_answers]
                if group_answers and all(a.result_payload.get('skipped') for a in group_answers):
                    for a in group_answers:
                        a.eval_status = 'done'
                    continue
                main_answer = by_question.get(main.id)
                if main_answer and main_answer.eval_status == 'done':
                    evaluations.append(main_answer.competency_scores)
                    for a in group_answers:
                        for key in stars:
                            stars[key] |= a.star.get(key, False)
                    continue
                # Do not give HR the technical rubric rows or another panelist's scores.
                rubric = '\n'.join(line for line in session.script['assessment']['rubric'].splitlines()
                    if not line.startswith('| ') or line.split('|')[1].strip() in set(main.competencies) | {'Kompetensi', '---'})
                evaluation = await orchestrator.evaluate({**guidebook.context_for(session, persona),
                    **evaluation_fields(session.script['assessment'], main.competencies),
                    'question': main.question_text, 'transcript': transcript, 'source_turns': source_turns,
                    'competencies': main.competencies, 'rubric': rubric,
                    'job_role': session.job_role, 'level': session.level, 'language': session.script['settings']['language'],
                    'feedback_language': feedback_language(session)})
                scores = verified_scores(evaluation['competency_scores'], transcript, main.competencies, source_turns, assessment=session.script['assessment'])
                evaluations.append(scores)
                for a in group_answers:
                    a.eval_status = 'done'
                    a.feedback = evaluation.get('feedback', {})
                    a.star = {key: evaluation.get('star', {}).get(key) is True for key in stars}
                    if a.question_id == main.id:
                        a.competency_scores = scores
                    for key in stars:
                        stars[key] |= a.star[key]
                await record(db, session, f'evidence:{main.id}', 'evidence_extracted', {'question_id': main.id,
                             'answer_turn_ids': [t['turn_id'] for t in source_turns], 'competencies': list(scores)})
            total, competencies = aggregate(evaluations, session.script['assessment']['weights'], session.script['assessment'])
            review = await orchestrator.summarize({'evaluations': [{'scores': a.competency_scores, 'feedback': a.feedback} for a in answers],
                'total_score': total, 'coverage': coverage(competencies), 'job_role': session.job_role, 'language': feedback_language(session)})
            for c in competencies:
                stored = await db.get(SessionCompetency, (sid, c['key']))
                stored.score = c['score']
            session.total_score = total
            session.review = review
            session.star_summary = stars
            session.finished_at = now()
            session.status = 'done'
            checkpoint(session, 'completed')
            await record(db, session, 'evaluation_completed', 'evaluation_completed', {'coverage': coverage(competencies)})
            await db.commit()
    except Exception as exc:
        emit('job_failed', job='finalize_session', error_type=type(exc).__name__)
        async with SessionLocal() as db:
            session = await db.get(InterviewSession, sid)
            if session and session.status == 'scoring':
                session.status = 'evaluation_failed'
                session.error_message = 'Penilaian belum selesai. Jawaban tersimpan; coba nilai ulang.'
                await record(db, session, 'evaluation_failed:' + str(now().timestamp()), 'evaluation_failed', {'error_type': type(exc).__name__})
                await db.commit()
    finally:
        session_var.reset(token)
