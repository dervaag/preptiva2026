import asyncio
from sqlalchemy import select
from app.db import SessionLocal
from app.models import InterviewSession, InterviewQuestion, InterviewAnswer, SessionCompetency, now
from app.ai import orchestrator, speech
from app.ai.scoring import verified_scores, aggregate
from app.log import emit, session_var
from app.ai.errors import ProviderError


async def fail(sid, stage, reason=None):
    async with SessionLocal() as db:
        session = await db.get(InterviewSession, sid)
        if session and session.status not in ('done', 'failed'):
            session.status = 'failed'
            session.error_message = (f'{stage} gagal. {reason}' if reason else f'{stage} gagal. Periksa konfigurasi provider dan log server, lalu buat sesi baru.')[:255]
            session.finished_at = now()
            await db.commit()


async def prepare_session(ctx, sid):
    token = session_var.set(sid)
    try:
        async with SessionLocal() as db:
            session = await db.get(InterviewSession, sid)
            if not session or session.status != 'preparing':
                return
            parsed = await orchestrator.parse_documents(session.cv_text, session.job_description)
            history = list((await db.scalars(select(InterviewQuestion.question_text).join(InterviewSession).where(
                InterviewSession.user_id == session.user_id, InterviewSession.interviewer == session.interviewer,
                InterviewQuestion.kind == 'main').order_by(InterviewQuestion.id.desc()).limit(35))).all())
            context = {**parsed, 'uuid': session.uuid, 'job_role': session.job_role, 'level': session.level,
                       'industry': session.industry, 'interviewer': session.interviewer, 'question_count': session.question_count,
                       'language': session.script['settings']['language']}
            prepared = await orchestrator.build_questions(context, history)
            utterances = [('intro.mp3', prepared['intro']), ('closing.mp3', prepared['closing'])]
            utterances += [(f'q{i}.mp3', q['question_text']) for i, q in enumerate(prepared['questions'], 1)]
            urls = await asyncio.gather(*(speech.synthesize(text, session.interviewer, session.uuid, name) for name, text in utterances))
            await db.refresh(session)
            if session.status != 'preparing':
                return
            session.cv_summary = parsed['cv_summary']
            session.jd_summary = parsed['jd_summary']
            session.script = {**session.script, 'intro': {'text': prepared['intro'], 'audio_url': urls[0]},
                              'closing': {'text': prepared['closing'], 'audio_url': urls[1]}, 'fillers': []}
            for i, q in enumerate(prepared['questions'], 1):
                db.add(InterviewQuestion(session_id=sid, main_order=i, audio_file=f'q{i}.mp3', **q))
            session.status = 'ready'
            await db.commit()
    except Exception as exc:
        emit('job_failed', job='prepare_session', error_type=type(exc).__name__)
        await fail(sid, 'Persiapan wawancara', str(exc) if isinstance(exc, ProviderError) else None)
    finally:
        session_var.reset(token)


async def finalize_session(ctx, sid):
    token = session_var.set(sid)
    try:
        async with SessionLocal() as db:
            session = await db.get(InterviewSession, sid)
            if not session or session.status != 'scoring':
                return
            questions = list((await db.scalars(select(InterviewQuestion).where(InterviewQuestion.session_id == sid).order_by(InterviewQuestion.main_order, InterviewQuestion.id))).all())
            answers = list((await db.scalars(select(InterviewAnswer).join(InterviewQuestion).where(InterviewQuestion.session_id == sid))).all())
            by_question = {a.question_id: a for a in answers}
            evaluations = []
            stars = {k: False for k in ('situation', 'task', 'action', 'result')}
            for main in (q for q in questions if q.kind == 'main'):
                group = [q for q in questions if q.main_order == main.main_order]
                group_answers = [by_question[q.id] for q in group if q.id in by_question]
                transcript = '\n'.join(a.transcript for a in group_answers)
                evaluation = await orchestrator.evaluate({'question': main.question_text, 'transcript': transcript,
                    'competencies': main.competencies, 'rubric': session.script['assessment']['rubric'],
                    'job_role': session.job_role, 'level': session.level, 'language': session.script['settings']['language']})
                scores = verified_scores(evaluation['competency_scores'], transcript, main.competencies)
                evaluations.append(scores)
                for a in group_answers:
                    a.eval_status = 'done'
                    a.feedback = evaluation.get('feedback', {})
                    a.star = {key: evaluation.get('star', {}).get(key) is True for key in stars}
                    if a.question_id == main.id:
                        a.competency_scores = scores
                    for key in stars:
                        stars[key] |= a.star[key]
                await db.commit()
            total, competencies = aggregate(evaluations, session.script['assessment']['weights'])
            review = await orchestrator.summarize({'evaluations': [{'scores': a.competency_scores, 'feedback': a.feedback} for a in answers],
                'total_score': total, 'job_role': session.job_role, 'language': session.script['settings']['language']})
            for c in competencies:
                stored = await db.get(SessionCompetency, (sid, c['key']))
                stored.score = c['score']
            session.total_score = total
            session.review = review
            session.star_summary = stars
            session.finished_at = now()
            session.status = 'done'
            await db.commit()
    except Exception as exc:
        emit('job_failed', job='finalize_session', error_type=type(exc).__name__)
        await fail(sid, 'Penilaian wawancara', str(exc) if isinstance(exc, ProviderError) else None)
    finally:
        session_var.reset(token)
