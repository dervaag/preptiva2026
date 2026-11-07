"""Conservative language gate; a retry does not become an assessed answer."""
import re
from fastapi import HTTPException
from langdetect import detect_langs, DetectorFactory, LangDetectException

DetectorFactory.seed = 0


def retry_message(language):
    return ('This interview is in English. Please answer the same question again in English. '
            'We will stay on this question.' if language == 'en' else
            'Wawancara ini menggunakan Bahasa Indonesia. Silakan ulangi jawaban untuk pertanyaan yang sama '
            'dalam Bahasa Indonesia. Kita tetap pada pertanyaan ini.')


def mismatched_language(text, expected):
    # Names, code fragments, numbers and very short answers cannot establish language reliably.
    words = re.findall(r"[^\W\d_]+", text.lower(), re.UNICODE)
    if expected not in ('id', 'en') or len(words) < 3:
        return False
    try:
        candidates = detect_langs(text)
    except LangDetectException:
        return False
    best = candidates[0]
    # Malay is often returned for Indonesian. Do not treat Malay as proof of English.
    detected = 'id' if best.lang in ('id', 'ms') else best.lang
    return detected in ('id', 'en') and detected != expected and best.prob >= .90


class AnswerLanguageMismatch(HTTPException):
    def __init__(self, session, question_id, transcript):
        language = session.script['settings']['language']
        self.payload = {'action':'language_retry', 'is_last':False, 'question_id':question_id,
            'transcript':transcript, 'response_text':retry_message(language), 'expected_language':language,
            'response_audio_url':f'/api/sessions/{session.uuid}/speech/language/{question_id}'}
        super().__init__(422, self.payload['response_text'])


def require_answer_language(session, question_id, transcript):
    if mismatched_language(transcript, session.script['settings']['language']):
        raise AnswerLanguageMismatch(session, question_id, transcript)
