"""Signed short-lived transcription receipts, bound to owner/question/retry attempt."""
from itsdangerous import URLSafeTimedSerializer, BadData
from fastapi import HTTPException
from app.config import settings


def attempt(session):
    return session.script.get('checkpoint', {}).get('recovered_interruption_id') or 'initial'


def seal(session, question_id, transcript, duration_ms, item_ids):
    return URLSafeTimedSerializer(settings.secret_key, salt='voice-capture-v1').dumps({
        'sid': session.uuid, 'owner': session.user_id, 'question_id': question_id, 'attempt': attempt(session),
        'transcript': transcript, 'duration_ms': duration_ms, 'item_ids': item_ids, 'model': settings.stt_model})


def verify(token, session, question_id):
    try:
        result = URLSafeTimedSerializer(settings.secret_key, salt='voice-capture-v1').loads(token, max_age=600)
        if (result['sid'] != session.uuid or result['owner'] != session.user_id or result['question_id'] != question_id
                or result['attempt'] != attempt(session)):
            raise BadData('Wrong capture scope.')
        return result
    except (BadData, KeyError, TypeError):
        raise HTTPException(422, 'Transkrip realtime kedaluwarsa atau tidak cocok dengan pertanyaan. Rekam ulang.')
