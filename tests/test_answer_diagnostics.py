"""Answer failures remain recoverable and diagnosable without logging private text."""
import test_system  # Establish the temporary database/environment before app imports.

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy import func, select

from app.api import sessions
from app.db import SessionLocal
from app.models import InterviewAnswer
from app import log


class AnswerDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    # Reuse fixtures without inheriting/re-running the entire system test suite.
    asyncSetUp = test_system.SystemTests.asyncSetUp
    asyncTearDown = test_system.SystemTests.asyncTearDown
    register = test_system.SystemTests.register
    form = test_system.SystemTests.form
    create = test_system.SystemTests.create
    ready_session = test_system.SystemTests.ready_session

    async def active(self):
        sid, _, state = await self.ready_session()
        self.assertEqual((await self.client.post(f'/api/sessions/{sid}/start')).status_code, 200)
        return sid, state['current_turn']['id']

    async def post_text(self, sid, qid, stream=False):
        return await self.client.post(f'/api/sessions/{sid}/answers' + ('?stream=true' if stream else ''),
            data={'question_id': qid, 'duration_ms': 100, 'text_answer': 'Belum.'})

    async def test_rejected_outputs_log_once_for_both_transports_and_retry_same_answer(self):
        sid, qid = await self.active()
        private = 'PRIVATE-MODEL-OUTPUT-DO-NOT-LOG'
        cases = [
            (True, {'action': 'follow_up', 'response_text': 'Apa rencana belajar Anda?',
                    'source_refs': [{'turn_id': f'q{qid}', 'quote': private}]}, 'reference_invalid'),
            (False, {'response_text': private}, 'schema_invalid'),
            (False, {'action': private, 'response_text': 'Terima kasih.'}, 'action_invalid'),
        ]
        for stream, output, reason in cases:
            with self.subTest(stream=stream, reason=reason), \
                    patch('app.ai.orchestrator.complete', AsyncMock(return_value=output)) as model, \
                    patch('app.api.sessions.speech.optional_synthesize', AsyncMock(return_value=None)), \
                    self.assertLogs('preptiva', level='INFO') as captured:
                response = await self.post_text(sid, qid, stream)
            self.assertEqual(response.status_code, 200 if stream else 502, response.text)
            if stream:
                events = [json.loads(line) for line in response.text.splitlines()]
                self.assertEqual(events[-1]['type'], 'error')
                self.assertFalse(any(event['type'] == 'result' for event in events))
            self.assertEqual(model.await_count, 2)
            records = [json.loads(record.getMessage()) for record in captured.records]
            failures = [row for row in records if row['event'] == 'answer_failed']
            rejected = [row for row in records if row['event'] == 'ai_output_rejected']
            self.assertEqual(len(failures), 1, records)
            self.assertEqual(len(rejected), 2, records)
            for row in failures + rejected:
                self.assertEqual(row['sid'], sid)
                self.assertEqual(row['question_id'], qid)
                self.assertEqual(row['rid'], response.headers['X-Request-ID'])
                self.assertEqual(row['stage'], 'respond')
                self.assertEqual(row['reason'], reason)
            frames = failures[0]['frames']
            self.assertTrue(any(frame['file'] == 'app/ai/orchestrator.py' for frame in frames), frames)
            self.assertNotIn(private, '\n'.join(captured.output))
            self.assertNotIn(private, response.text)
            self.assertIsNone(log.session_var.get())
            self.assertIsNone(log.question_var.get())
            current = (await self.client.get(f'/api/sessions/{sid}/state')).json()
            self.assertEqual(current['current_turn']['id'], qid)
            async with SessionLocal() as db:
                self.assertEqual(await db.scalar(select(func.count()).select_from(InterviewAnswer)), 0)

        with patch('app.ai.orchestrator.complete', AsyncMock(return_value={
                'action': 'next', 'response_text': 'Terima kasih.'})) as model, \
                patch('app.api.sessions.speech.optional_synthesize', AsyncMock(return_value=None)):
            first = await self.post_text(sid, qid)
            duplicate = await self.post_text(sid, qid)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json(), duplicate.json())
        self.assertEqual(model.await_count, 1)
        async with SessionLocal() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(InterviewAnswer)), 1)

    async def test_short_answer_literal_followup_is_accepted_end_to_end(self):
        sid, qid = await self.active()
        refs = [{'turn_id': f'q{qid}', 'quote': 'Belum.'}]
        with patch('app.ai.orchestrator.complete', AsyncMock(return_value={
                'action': 'follow_up', 'response_text': 'Apa langkah awal yang ingin Anda coba?',
                'source_refs': refs})) as model, \
                patch('app.api.sessions.speech.optional_synthesize', AsyncMock(return_value=None)):
            response = await self.post_text(sid, qid, stream=True)
        self.assertEqual(response.status_code, 200)
        result = [json.loads(line) for line in response.text.splitlines()][-1]
        self.assertEqual(result['type'], 'result', result)
        self.assertEqual(result['action'], 'follow_up')
        self.assertEqual(result['source_refs'], refs)
        self.assertEqual(model.await_count, 1)
        async with SessionLocal() as db:
            answer = await db.scalar(select(InterviewAnswer).where(InterviewAnswer.question_id == qid))
            self.assertEqual(answer.transcript, 'Belum.')

    async def test_unexpected_error_has_safe_http_body_and_diagnostic_frames(self):
        sid, qid = await self.active()
        private = 'PRIVATE-TRANSCRIPT-IN-EXCEPTION'
        with patch('app.ai.orchestrator.respond', AsyncMock(side_effect=ValueError(private))), \
                self.assertLogs('preptiva', level='INFO') as captured:
            response = await self.post_text(sid, qid)
        self.assertEqual(response.status_code, 500, response.text)
        records = [json.loads(record.getMessage()) for record in captured.records]
        failed = next(row for row in records if row['event'] == 'answer_failed')
        self.assertEqual(failed['error_type'], 'ValueError')
        self.assertTrue(failed['frames'])
        self.assertNotIn(private, '\n'.join(captured.output))
        self.assertNotIn(private, response.text)


class AnswerContextIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_failures_keep_context_separate_and_restore_parent(self):
        reached = 0
        both_started = asyncio.Event()

        async def fail(sid, owner_id, question_id, *args, **kwargs):
            nonlocal reached
            reached += 1
            if reached == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), 2)
            self.assertEqual(log.session_var.get(), sid)
            self.assertEqual(log.question_var.get(), question_id)
            raise ValueError('PRIVATE-CONCURRENT-ANSWER')

        session_token = log.session_var.set('outer-session')
        question_token = log.question_var.set(999)
        try:
            with patch('app.api.sessions._dispatch_answer', side_effect=fail), \
                    self.assertLogs('preptiva', level='INFO') as captured:
                results = await asyncio.gather(
                    sessions.process_answer('session-a', 1, 101),
                    sessions.process_answer('session-b', 2, 202), return_exceptions=True)
            self.assertTrue(all(isinstance(result, HTTPException) and result.status_code == 500 for result in results))
            records = [json.loads(record.getMessage()) for record in captured.records]
            failures = [row for row in records if row['event'] == 'answer_failed']
            self.assertEqual({(row['sid'], row['question_id']) for row in failures},
                             {('session-a', 101), ('session-b', 202)})
            self.assertEqual(len(failures), 2)
            self.assertNotIn('PRIVATE-CONCURRENT-ANSWER', '\n'.join(captured.output))
            self.assertEqual(log.session_var.get(), 'outer-session')
            self.assertEqual(log.question_var.get(), 999)
        finally:
            log.question_var.reset(question_token)
            log.session_var.reset(session_token)
