from sqlalchemy import select
from app.models import InterviewQuestion, InterviewAnswer
from app.ai.blueprint import PERSONAS
from app.ai.scoring import aggregate, label


def public_question(q, session):
    if q is None:
        return None
    return {'id': q.id, 'kind': q.kind, 'main_order': q.main_order, 'slot': q.slot, 'category': q.category,
            'question_text': q.question_text, 'audio_url': f'/api/sessions/{session.uuid}/audio/{q.audio_file}' if q.audio_file else None}


async def turns(db, session):
    questions = list((await db.scalars(select(InterviewQuestion).where(InterviewQuestion.session_id == session.id).order_by(InterviewQuestion.main_order, InterviewQuestion.id))).all())
    answers = list((await db.scalars(select(InterviewAnswer).join(InterviewQuestion).where(InterviewQuestion.session_id == session.id))).all())
    return questions, answers


async def state(db, session):
    questions, answers = await turns(db, session)
    answered = {a.question_id for a in answers}
    current = next((q for q in questions if q.id not in answered), None)
    return {'session_id': session.uuid, 'status': session.status, 'error': session.error_message,
            'interviewer': session.interviewer, 'persona': PERSONAS[session.interviewer],
            'job_role': session.job_role, 'level': session.level, 'question_count': session.question_count,
            'answer_seconds': session.answer_seconds, 'retry_limit': session.script.get('settings', {}).get('retry_limit', 2), 'max_followups': session.max_followups,
            'script': {k: session.script.get(k) for k in ('intro', 'closing', 'fillers', 'settings')},
            'questions': [public_question(q, session) for q in questions if q.kind == 'main'],
            'current_turn': public_question(current, session),
            'answered_mains': sum(q.kind == 'main' and q.id in answered for q in questions)}


def session_item(s):
    return {'id': s.uuid, 'job_role': s.job_role, 'level': s.level, 'interviewer': s.interviewer, 'company': s.company,
            'status': s.status, 'question_count': s.question_count, 'total_score': s.total_score, 'label': label(s.total_score),
            'created_at': s.created_at.isoformat() + 'Z', 'finished_at': s.finished_at.isoformat() + 'Z' if s.finished_at else None}
