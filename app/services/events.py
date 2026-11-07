"""Append-only domain events, committed with their session/answer changes."""
from sqlalchemy import select
from app.models import InterviewEvent, now


async def record(db, session, key, kind, payload=None):
    existing = await db.scalar(select(InterviewEvent).where(
        InterviewEvent.session_id == session.id, InterviewEvent.event_key == key))
    if existing:
        return existing
    event = InterviewEvent(session_id=session.id, event_key=key, kind=kind, payload=payload or {})
    db.add(event)
    return event


def checkpoint(session, phase, question=None, **details):
    previous = session.script.get('checkpoint', {})
    session.script = {**session.script, 'checkpoint': {
        **previous, 'phase': phase, 'question_id': question.id if question is not None else None,
        'updated_at': now().isoformat() + 'Z', **details}}
