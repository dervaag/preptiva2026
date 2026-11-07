"""Language mismatch must not consume a turn or an assessment unit."""
import json
import unittest
from unittest.mock import AsyncMock, patch
import test_system as fixture
from sqlalchemy import select, func
from app.ai.answer_language import mismatched_language
from app.graphs.policy import snapshot
from app.models import InterviewSession, InterviewAnswer, GraphTurnInput
from app.db import SessionLocal

ID_ANSWER = 'Saya menggunakan Postman untuk menguji API dan memastikan respons sesuai kebutuhan pengguna.'
EN_ANSWER = 'I used automated tests to check the response codes and verify error handling before deployment.'


class DetectionTests(unittest.TestCase):
    def test_both_directions_and_technical_terms(self):
        self.assertTrue(mismatched_language(ID_ANSWER, 'en'))
        self.assertTrue(mismatched_language(EN_ANSWER, 'id'))
        self.assertFalse(mismatched_language(ID_ANSWER, 'id'))
        self.assertFalse(mismatched_language(EN_ANSWER, 'en'))
        self.assertFalse(mismatched_language('Saya menggunakan unit test dan integration test untuk memeriksa API sebelum deployment.', 'id'))

    def test_short_uncertain_answers_are_not_rejected(self):
        for text in ('', 'Yes', 'Tidak', 'FastAPI', 'HTTP 200', 'Postman API'):
            for language in ('id', 'en'):
                self.assertFalse(mismatched_language(text, language))


class LanguageGateTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixture.SystemTests.asyncSetUp
    asyncTearDown = fixture.SystemTests.asyncTearDown
    register = fixture.SystemTests.register
    form = fixture.SystemTests.form
    create = fixture.SystemTests.create
    ready_session = fixture.SystemTests.ready_session

    async def check_gate(self, engine, language, stream, audio=False):
        sid, internal_id, state = await self.ready_session(language=language)
        async with SessionLocal() as db:
            session = await db.get(InterviewSession, internal_id)
            session.script = {**session.script, 'runtime': {**session.script.get('runtime', {}), **snapshot(engine)}}
            await db.commit()
        await self.client.post(f'/api/sessions/{sid}/start')
        qid = state['current_turn']['id']
        wrong, correct = (ID_ANSWER, EN_ANSWER) if language == 'en' else (EN_ANSWER, ID_ANSWER)
        data = {'question_id':qid, 'duration_ms':100}
        extras = {'files': {'audio': ('answer.webm', b'synthetic audio', 'audio/webm')}} if audio else {}
        if not audio:
            data['text_answer'] = wrong
        with patch('app.ai.orchestrator.respond', AsyncMock()) as response_model, \
             patch('app.ai.speech.transcribe', AsyncMock(return_value=wrong)):
            response = await self.client.post(f'/api/sessions/{sid}/answers' + ('?stream=true' if stream else ''),
                data=data, **extras)
        self.assertEqual(response.status_code, 200, response.text)
        result = next(json.loads(line) for line in response.text.splitlines() if json.loads(line).get('type') == 'result') if stream else response.json()
        self.assertEqual(result['action'], 'language_retry')
        self.assertEqual(result['question_id'], qid)
        self.assertFalse(result['is_last'])
        response_model.assert_not_called()
        latest = (await self.client.get(f'/api/sessions/{sid}/state')).json()
        self.assertEqual(latest['current_turn']['id'], qid)
        self.assertEqual(latest['status'], 'running')
        async with SessionLocal() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(InterviewAnswer)), 0)
            self.assertEqual(await db.scalar(select(func.count()).select_from(GraphTurnInput)), 0)
        # The same question accepts a corrected-language answer instead of being locked.
        with patch('app.ai.orchestrator.respond', AsyncMock(return_value={'action':'next', 'response_text':'Thank you.', 'source_refs':[]})), \
             patch('app.ai.speech.optional_synthesize', AsyncMock(return_value=None)):
            accepted = await self.client.post(f'/api/sessions/{sid}/answers',
                data={'question_id':qid, 'duration_ms':100, 'text_answer':correct})
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertIn('answer_id', accepted.json())

    async def test_legacy_english_stream(self):
        await self.check_gate('legacy', 'en', True)

    async def test_legacy_indonesian_json(self):
        await self.check_gate('legacy', 'id', False)

    async def test_graph_english_json(self):
        await self.check_gate('langgraph', 'en', False)

    async def test_graph_indonesian_stream(self):
        await self.check_gate('langgraph', 'id', True)

    async def test_graph_audio_uses_transcript_language_gate(self):
        await self.check_gate('langgraph', 'en', True, audio=True)
