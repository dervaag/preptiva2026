"""End-to-end API/worker regressions for graph and pinned legacy sessions."""
import asyncio
from datetime import timedelta
import hashlib
import json
import unittest
from unittest.mock import AsyncMock, patch

import test_system as fixture  # Initializes the existing suite's temporary app database first.
from sqlalchemy import func, select

from app.ai import orchestrator
from app.ai.blueprint import blueprint
from app.config import settings
from app.db import SessionLocal
from app.graphs.models import GraphExecution
from app.models import GraphTurnInput, InterviewAnswer, InterviewEvent, InterviewQuestion, InterviewSession, now
from app.services.voice_capture import seal
from app.worker.tasks import finalize_session, prepare_session


class GraphFlowTests(unittest.IsolatedAsyncioTestCase):
    register = fixture.SystemTests.register
    form = fixture.SystemTests.form
    create = fixture.SystemTests.create

    async def asyncSetUp(self):
        await fixture.SystemTests.asyncSetUp(self)
        for name, value in [('orchestration_engine', 'langgraph'), ('realtime_voice_enabled', True), ('openai_api_key', '')]:
            setting = patch.object(settings, name, value)
            setting.start()
            self.addCleanup(setting.stop)
        self.quote = 'Saya mengukur hasil eksperimen dan meningkatkan hasil tim sebesar 35 persen.'
        self.provider_patches = [patch('app.ai.speech.optional_synthesize', AsyncMock(return_value=None)),
                                 patch.object(orchestrator, 'respond', AsyncMock(return_value={'action': 'next', 'response_text': 'Terima kasih.'}))]
        for item in self.provider_patches:
            item.start()
            self.addCleanup(item.stop)

    async def asyncTearDown(self):
        await fixture.SystemTests.asyncTearDown(self)

    async def generated_questions(self, context, history):
        plan = blueprint(context['question_count'], context['uuid'], context['panel'], context['guidebook'], context['assessment'])
        texts = ['Ceritakan cara Anda menyampaikan hasil proyek kepada rekan?',
                 'Bagaimana Anda menentukan langkah ketika rencana berubah?',
                 'Apa yang Anda pelajari setelah menerima umpan balik?']
        if any(history.values()):
            texts = ['Saat menerima pekerjaan baru, bagaimana Anda memahami kebutuhan tim?',
                     'Bagikan contoh saat prioritas organisasi menuntut perubahan pendekatan?',
                     'Dengan cara apa Anda mempelajari keterampilan yang belum dikuasai?']
        return {'plan': plan, 'intro': 'Selamat datang.', 'closing': 'Terima kasih. Sesi selesai.',
                'questions': [{'slot': slot['slot'], 'category': 'Synthetic test',
                    'question_text': texts[index], 'competencies': slot['competencies'],
                    'expected_points': ['personal contribution'], 'anchor_id': context['candidate_profile']['anchors'][0]['id']}
                    for index, slot in enumerate(plan)]}

    async def ready(self, **changes):
        created = await self.create(**changes)
        self.assertEqual(created.status_code, 200, created.text)
        sid = created.json()['session_id']
        async with SessionLocal() as db:
            session = await db.scalar(select(InterviewSession).where(InterviewSession.uuid == sid))
            internal_id = session.id
        with patch.object(orchestrator, 'parse_documents', AsyncMock(return_value={'cv_summary': {}, 'jd_summary': {}})), \
             patch.object(orchestrator, 'build_questions', side_effect=self.generated_questions):
            await prepare_session({}, internal_id)
        state = (await self.client.get(f'/api/sessions/{sid}/state')).json()
        self.assertEqual(state['status'], 'ready', state)
        self.assertEqual((await self.client.post(f'/api/sessions/{sid}/start')).status_code, 200)
        return sid, internal_id, state

    async def text(self, sid, qid, value=None, *, stream=False):
        return await self.client.post(f'/api/sessions/{sid}/answers' + ('?stream=true' if stream else ''),
                                      data={'question_id': qid, 'text_answer': value or self.quote, 'duration_ms': 1000})

    async def evaluate(self, context):
        return {'competency_scores': {key: {'score': 4, 'evidence': [context['source_turns'][0]['transcript']],
                    'evidence_sufficiency': 'sufficient', 'rationale': 'Synthetic supported evidence.'}
                    for key in context['competencies']},
                'star': {'situation': True, 'task': True, 'action': True, 'result': True},
                'feedback': {'strengths': ['Synthetic evidence.'], 'improvements': []}}

    async def finish(self, sid, internal_id):
        with patch('app.api.sessions.enqueue', AsyncMock()) as enqueue:
            response = await self.client.post(f'/api/sessions/{sid}/finish')
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['status'], 'scoring')
            enqueue.assert_awaited_once_with('finalize_session', internal_id)
        with patch.object(orchestrator, 'evaluate', side_effect=self.evaluate), \
             patch.object(orchestrator, 'summarize', AsyncMock(return_value={'summary': 'Synthetic result.', 'strengths': [], 'improvements': []})):
            await finalize_session({}, internal_id)
        response = await self.client.get(f'/api/sessions/{sid}/result')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def test_panel_audio_text_realtime_finishes_and_engine_is_pinned(self):
        sid, internal_id, state = await self.ready(panel=['hr', 'user', 'manager'])
        settings.orchestration_engine = 'legacy'  # A settings change must not migrate this session.
        qid = state['current_turn']['id']
        with patch('app.ai.speech.transcribe', AsyncMock(return_value=self.quote)) as stt:
            response = await self.client.post(f'/api/sessions/{sid}/answers',
                data={'question_id': qid, 'duration_ms': 12000}, files={'audio': ('answer.webm', b'synthetic audio', 'audio/webm')})
        self.assertEqual(response.status_code, 200, response.text)
        stt.assert_awaited_once()
        self.assertEqual(response.json()['input_mode'], 'audio')
        self.assertEqual(response.json()['response_interviewer'], 'hr')
        next_q = response.json()['next_question']
        response = await self.text(sid, next_q['id'], stream=True)
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(events[0]['type'], 'transcript')
        result = events[-1]
        self.assertEqual(result['type'], 'result')
        self.assertEqual(result['input_mode'], 'text')
        self.assertEqual(result['response_interviewer'], 'user')
        duplicate = await self.text(sid, next_q['id'])
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        self.assertEqual(duplicate.json()['answer_id'], result['answer_id'])
        final_q = result['next_question']
        corrected = self.quote + ' Koreksi transkrip sesuai ucapan asli.'
        async with SessionLocal() as db:
            session = await db.get(InterviewSession, internal_id)
            self.assertEqual(session.script['runtime']['engine'], 'langgraph')
            token = seal(session, final_q['id'], self.quote, 15000, ['synthetic-stt-item'])
        response = await self.client.post(f'/api/sessions/{sid}/answers', data={
            'question_id': final_q['id'], 'duration_ms': 15000, 'capture_token': token, 'corrected_transcript': corrected})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['input_mode'], 'realtime')
        self.assertEqual(response.json()['original_transcript'], self.quote)
        self.assertTrue(response.json()['transcript_corrected'])
        self.assertTrue(response.json()['is_last'])
        result = await self.finish(sid, internal_id)
        self.assertEqual(result['total_score'], 4)
        self.assertEqual(len(result['panel_results']), 3)
        self.assertEqual([item['input_mode'] for item in result['items']], ['audio', 'text', 'realtime'])
        self.assertEqual(result['review']['panel_assessment']['policy']['version'], 'panel-evidence-equal-persona-v1')
        self.assertFalse(result['assessment']['validated'])
        async with SessionLocal() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(GraphTurnInput).where(
                GraphTurnInput.session_id == internal_id)), 3)
            self.assertEqual(await db.scalar(select(func.count()).select_from(GraphExecution).where(
                GraphExecution.session_id == internal_id, GraphExecution.status == 'succeeded')), 5)
        from app.graphs.manage import inspect
        metadata = await inspect(sid)
        self.assertEqual(len(metadata['executions']), 5)
        self.assertTrue(all(run['plan_matches'] for run in metadata['executions']))

    async def test_accepted_transcript_survives_model_failure_and_duplicate_resume(self):
        sid, internal_id, state = await self.ready()
        qid = state['current_turn']['id']
        with patch.object(orchestrator, 'respond', AsyncMock(side_effect=asyncio.TimeoutError)):
            response = await self.text(sid, qid)
        self.assertEqual(response.status_code, 504, response.text)
        async with SessionLocal() as db:
            saved = await db.scalar(select(GraphTurnInput).where(GraphTurnInput.session_id == internal_id))
            self.assertEqual(saved.payload['transcript'], self.quote)
            self.assertEqual(saved.status, 'pending')
            self.assertEqual(await db.scalar(select(func.count()).select_from(InterviewAnswer)), 0)
        self.assertEqual((await self.client.get(f'/api/sessions/{sid}/state')).json()['current_turn']['id'], qid)
        changed = await self.text(sid, qid, 'Changed payload must not replace an accepted answer.')
        self.assertEqual(changed.status_code, 409, changed.text)
        with patch.object(orchestrator, 'respond', AsyncMock(return_value={'action': 'next', 'response_text': 'Terima kasih.'})) as respond:
            first, duplicate = await asyncio.gather(self.text(sid, qid), self.text(sid, qid))
            self.assertEqual(first.status_code, 200, first.text)
            self.assertEqual(duplicate.status_code, 200, duplicate.text)
            self.assertEqual(first.json()['answer_id'], duplicate.json()['answer_id'])
            self.assertEqual(respond.await_count, 1)
        async with SessionLocal() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(InterviewAnswer)), 1)
            self.assertEqual(await db.scalar(select(func.count()).select_from(GraphTurnInput)), 1)

    async def test_simultaneous_different_payload_does_not_reuse_other_answer_silently(self):
        sid, _, state = await self.ready()
        qid = state['current_turn']['id']
        from app.graphs import turn
        execute = turn.execute
        waiting, both_ready = 0, asyncio.Event()
        async def simultaneous(*args, **kwargs):
            nonlocal waiting
            waiting += 1
            if waiting == 2:
                both_ready.set()
            await asyncio.wait_for(both_ready.wait(), 5)
            return await execute(*args, **kwargs)
        with patch.object(turn, 'execute', side_effect=simultaneous):
            first, second = await asyncio.gather(
                self.text(sid, qid, self.quote),
                self.text(sid, qid, 'Ini jawaban berbeda yang dikirim pada saat bersamaan.'))
        self.assertEqual(sorted([first.status_code, second.status_code]), [200, 409], (first.text, second.text))
        async with SessionLocal() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(InterviewAnswer)), 1)
            self.assertEqual(await db.scalar(select(func.count()).select_from(GraphTurnInput)), 1)

    async def test_empty_transcription_allows_new_recording_without_replaying_old_stt(self):
        sid, _, state = await self.ready()
        qid = state['current_turn']['id']
        async def upload(payload):
            return await self.client.post(f'/api/sessions/{sid}/answers', data={'question_id': qid, 'duration_ms': 12000},
                files={'audio': ('answer.webm', payload, 'audio/webm')})
        with patch('app.ai.speech.transcribe', AsyncMock(side_effect=['', self.quote])) as stt:
            empty = await upload(b'first recording without speech')
            self.assertEqual(empty.status_code, 422, empty.text)
            async with SessionLocal() as db:
                self.assertEqual(await db.scalar(select(func.count()).select_from(GraphTurnInput)), 0)
            accepted = await upload(b'new recording with speech')
            self.assertEqual(accepted.status_code, 200, accepted.text)
            self.assertEqual(accepted.json()['transcript'], self.quote)
            duplicate = await upload(b'new recording with speech')
            self.assertEqual(duplicate.status_code, 200, duplicate.text)
            self.assertEqual(duplicate.json()['answer_id'], accepted.json()['answer_id'])
            self.assertEqual(stt.await_count, 2)

    async def test_interruption_during_provider_work_discards_stale_commit_and_retry_next(self):
        sid, internal_id, state = await self.ready(panel=['hr', 'user'])
        qid = state['current_turn']['id']
        entered, release = asyncio.Event(), asyncio.Event()
        async def slow_response(context):
            entered.set()
            await release.wait()
            return {'action': 'next', 'response_text': 'Terima kasih.'}
        with patch.object(orchestrator, 'respond', side_effect=slow_response):
            request = asyncio.create_task(self.text(sid, qid))
            await asyncio.wait_for(entered.wait(), 5)
            interrupted = await self.client.post(f'/api/sessions/{sid}/interrupt', json={'question_id': qid, 'reason': 'offline'})
            self.assertEqual(interrupted.status_code, 200, interrupted.text)
            point = interrupted.json()['state']['checkpoint']
            self.assertEqual(point['remaining_seconds'], 0)
            release.set()
            rejected = await asyncio.wait_for(request, 5)
        self.assertEqual(rejected.status_code, 409, rejected.text)
        async with SessionLocal() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(InterviewAnswer)), 0)
            saved_id = await db.scalar(select(GraphTurnInput.id))
        reloaded = (await self.client.get(f'/api/sessions/{sid}/state')).json()
        self.assertEqual(reloaded['checkpoint']['phase'], 'interrupted')
        retry = await self.client.post(f'/api/sessions/{sid}/recover', json={
            'question_id': qid, 'interruption_id': point['interruption_id'], 'action': 'retry'})
        self.assertEqual(retry.status_code, 200, retry.text)
        self.assertEqual(retry.json()['checkpoint']['remaining_seconds'], state['answer_seconds'])
        from app.graphs.turn import resume
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            await resume(saved_id)
        accepted = await self.text(sid, qid, self.quote + ' Jawaban percobaan baru.')
        self.assertEqual(accepted.status_code, 200, accepted.text)
        next_q = accepted.json()['next_question']
        interrupted = await self.client.post(f'/api/sessions/{sid}/interrupt', json={'question_id': next_q['id'], 'reason': 'tab_hidden'})
        event = interrupted.json()['state']['checkpoint']['interruption_id']
        with patch.object(orchestrator, 'respond', AsyncMock(side_effect=AssertionError('Skip must not call AI'))):
            skipped = await self.client.post(f'/api/sessions/{sid}/recover', json={
                'question_id': next_q['id'], 'interruption_id': event, 'action': 'next'})
        self.assertEqual(skipped.status_code, 200, skipped.text)
        self.assertTrue(skipped.json()['skipped'])
        self.assertEqual(skipped.json()['transcript'], '')
        last = await self.text(sid, skipped.json()['next_question']['id'])
        self.assertEqual(last.status_code, 200, last.text)
        result = await self.finish(sid, internal_id)
        skipped_item = next(item for item in result['items'] if item['skipped'])
        self.assertEqual(skipped_item['competency_scores'], {})

    async def test_preparation_retry_keeps_parsed_output_and_enforces_ownership_csrf(self):
        response = await self.create()
        sid = response.json()['session_id']
        async with SessionLocal() as db:
            internal_id = await db.scalar(select(InterviewSession.id).where(InterviewSession.uuid == sid))
        with patch.object(orchestrator, 'parse_documents', AsyncMock(return_value={'cv_summary': {}, 'jd_summary': {}})) as parse, \
             patch.object(orchestrator, 'build_questions', AsyncMock(side_effect=RuntimeError('synthetic build failure'))):
            await prepare_session({}, internal_id)
            self.assertEqual((await self.client.get(f'/api/sessions/{sid}/state')).json()['status'], 'preparation_failed')
            parse.assert_awaited_once()
        await self.register(self.other, 'other-graph@example.com')
        self.assertEqual((await self.other.post(f'/api/sessions/{sid}/retry-preparation')).status_code, 404)
        self.assertEqual((await self.client.post(f'/api/sessions/{sid}/retry-preparation',
            headers={'Origin': 'https://attacker.example'})).status_code, 403)
        with patch('app.api.sessions.enqueue', AsyncMock()) as enqueue:
            retried = await self.client.post(f'/api/sessions/{sid}/retry-preparation')
            self.assertEqual(retried.status_code, 200, retried.text)
            enqueue.assert_awaited_once_with('prepare_session', internal_id)
        with patch.object(orchestrator, 'parse_documents', AsyncMock(side_effect=AssertionError('Completed parse must be reused'))), \
             patch.object(orchestrator, 'build_questions', side_effect=self.generated_questions):
            await prepare_session({}, internal_id)
            await prepare_session({}, internal_id)
        self.assertEqual((await self.client.get(f'/api/sessions/{sid}/state')).json()['status'], 'ready')
        async with SessionLocal() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(InterviewQuestion).where(
                InterviewQuestion.session_id == internal_id)), 3)
            self.assertEqual(await db.scalar(select(func.count()).select_from(InterviewEvent).where(
                InterviewEvent.session_id == internal_id, InterviewEvent.event_key == 'ready')), 1)

    async def test_followup_keeps_owner_and_cannot_exceed_snapshotted_limit(self):
        sid, internal_id, state = await self.ready(panel=['hr', 'user', 'manager'])
        main = state['current_turn']
        async def followup(context):
            current = context['context_packet']['recent_turns'][-1]
            return {'action': 'follow_up', 'response_text': 'Apa hasil konkret dari kontribusi pribadi Anda?',
                    'interviewer': 'manager', 'next_persona': 'manager',
                    'source_refs': [{'turn_id': current['turn_id'], 'quote': self.quote}]}
        with patch.object(orchestrator, 'respond', side_effect=followup):
            first = await self.text(sid, main['id'])
            self.assertEqual(first.status_code, 200, first.text)
            follow = first.json()['follow_up_question']
            self.assertIsNotNone(follow)
            self.assertEqual(follow['interviewer'], 'hr')
            self.assertEqual(first.json()['response_interviewer'], 'hr')
            self.assertEqual(follow['main_order'], main['main_order'])
            second = await self.text(sid, follow['id'])
            self.assertEqual(second.status_code, 200, second.text)
            self.assertEqual(second.json()['action'], 'next')
            self.assertIsNone(second.json()['follow_up_question'])
            second_main = second.json()['next_question']
            self.assertEqual(second_main['interviewer'], 'user')
            third = await self.text(sid, second_main['id'])
            self.assertEqual(third.status_code, 200, third.text)
            self.assertEqual(third.json()['action'], 'next')
            self.assertIsNone(third.json()['follow_up_question'])
            last = await self.text(sid, third.json()['next_question']['id'])
            self.assertEqual(last.status_code, 200, last.text)
            self.assertTrue(last.json()['is_last'])
        async with SessionLocal() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(InterviewQuestion).where(
                InterviewQuestion.session_id == internal_id, InterviewQuestion.kind == 'main')), 3)
            self.assertEqual(await db.scalar(select(func.count()).select_from(InterviewQuestion).where(
                InterviewQuestion.session_id == internal_id, InterviewQuestion.kind == 'follow_up')), 1)
        result = await self.finish(sid, internal_id)
        self.assertEqual(len(result['items']), 4)

    async def test_legacy_session_stays_legacy_after_graph_flag_enabled(self):
        settings.orchestration_engine = 'legacy'
        sid, internal_id, state = await self.ready()
        settings.orchestration_engine = 'langgraph'
        for _ in range(3):
            response = await self.text(sid, state['current_turn']['id'])
            self.assertEqual(response.status_code, 200, response.text)
            state = (await self.client.get(f'/api/sessions/{sid}/state')).json()
        result = await self.finish(sid, internal_id)
        self.assertNotIn('panel_assessment', result['review'])
        async with SessionLocal() as db:
            session = await db.get(InterviewSession, internal_id)
            self.assertEqual(session.script['runtime']['engine'], 'legacy')
            self.assertEqual(await db.scalar(select(func.count()).select_from(GraphExecution).where(
                GraphExecution.session_id == internal_id)), 0)

    async def test_finalization_failure_retries_via_api_without_losing_or_rescoring_answers(self):
        sid, internal_id, state = await self.ready(panel=['hr', 'user'])
        for _ in range(3):
            response = await self.text(sid, state['current_turn']['id'])
            self.assertEqual(response.status_code, 200, response.text)
            state = (await self.client.get(f'/api/sessions/{sid}/state')).json()
        with patch('app.api.sessions.enqueue', AsyncMock()):
            self.assertEqual((await self.client.post(f'/api/sessions/{sid}/finish')).status_code, 200)
        with patch.object(orchestrator, 'evaluate', side_effect=self.evaluate) as evaluate, \
             patch.object(orchestrator, 'summarize', AsyncMock(side_effect=asyncio.TimeoutError)):
            await finalize_session({}, internal_id)
            original_calls = evaluate.await_count
            self.assertGreater(original_calls, 0)
        failed = (await self.client.get(f'/api/sessions/{sid}/state')).json()
        self.assertEqual(failed['status'], 'evaluation_failed')
        self.assertEqual(failed['answered_mains'], 3)
        self.assertEqual((await self.client.get(f'/api/sessions/{sid}/result')).status_code, 409)
        with patch('app.api.sessions.enqueue', AsyncMock()) as enqueue:
            self.assertEqual((await self.client.post(f'/api/sessions/{sid}/finish')).status_code, 200)
            enqueue.assert_awaited_once_with('finalize_session', internal_id)
        with patch.object(orchestrator, 'evaluate', AsyncMock(side_effect=AssertionError('Initial ratings must be reused'))), \
             patch.object(orchestrator, 'summarize', AsyncMock(return_value={'summary': 'Recovered feedback.'})):
            await finalize_session({}, internal_id)
        result = await self.client.get(f'/api/sessions/{sid}/result')
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(len(result.json()['items']), 3)
        self.assertEqual(result.json()['review']['summary'], 'Recovered feedback.')

    async def test_unknown_graph_version_returns_503_without_legacy_or_provider_fallback(self):
        sid, internal_id, state = await self.ready()
        async with SessionLocal() as db:
            session = await db.get(InterviewSession, internal_id)
            session.script = {**session.script, 'runtime': {**session.script['runtime'], 'graph_version': 'langgraph-unknown'}}
            await db.commit()
        with patch('app.api.sessions._process_answer', AsyncMock(side_effect=AssertionError('Legacy fallback forbidden'))) as legacy, \
             patch.object(orchestrator, 'respond', AsyncMock(side_effect=AssertionError('Provider must not run'))) as respond:
            response = await self.text(sid, state['current_turn']['id'])
            self.assertEqual(response.status_code, 503, response.text)
            self.assertIn('Versi sesi', response.json()['detail'])
            legacy.assert_not_awaited()
            respond.assert_not_awaited()
        from app.graphs.policy import UnsupportedGraphVersion
        with patch('app.worker.tasks._prepare_legacy', AsyncMock()) as prepare_legacy, \
             patch('app.worker.tasks._finalize_session', AsyncMock()) as finalize_legacy:
            with self.assertRaises(UnsupportedGraphVersion):
                await prepare_session({}, internal_id)
            with self.assertRaises(UnsupportedGraphVersion):
                await finalize_session({}, internal_id)
            prepare_legacy.assert_not_awaited()
            finalize_legacy.assert_not_awaited()

    async def test_worker_requeues_abandoned_and_committed_graphs_without_reviving_interrupted_questions(self):
        from app.graphs.turn import thread_key
        from app.worker.tasks import recover_graph_jobs
        cases = [
            ('new_prepare', 'preparing', None, None),
            ('new_finalize', 'scoring', None, None),
            ('committed_prepare', 'ready', 'prepare', None),
            ('committed_finalize', 'done', 'finalize', None),
            ('pending_turn', 'running', 'turn', 'pending'),
            ('committed_turn', 'done', 'turn', 'completed'),
            ('interrupted_turn', 'running', 'turn', 'pending'),
            ('closed_turn', 'failed', 'turn', 'pending'),
            ('leased_prepare', 'preparing', 'prepare', None),
            ('unknown_prepare', 'preparing', None, None),
            ('legacy_prepare', 'preparing', None, None),
        ]
        expected = set()
        with patch.object(settings, 'max_sessions_per_hour', 100):
            for label, status, kind, input_status in cases:
                created = await self.create()
                self.assertEqual(created.status_code, 200, created.text)
                async with SessionLocal() as db:
                    session = await db.scalar(select(InterviewSession).where(InterviewSession.uuid == created.json()['session_id']))
                    session.status = status
                    script = {**session.script, 'checkpoint': {'phase': 'interrupted' if label == 'interrupted_turn' else 'question_ready'}}
                    if label == 'unknown_prepare':
                        script['runtime'] = {**script['runtime'], 'graph_version': 'future-version'}
                    if label == 'legacy_prepare':
                        script['runtime'] = {'engine': 'legacy'}
                    session.script = script
                    if kind:
                        if kind == 'turn':
                            question = InterviewQuestion(session_id=session.id, main_order=1, kind='main',
                                question_text='Synthetic pending turn?', competencies=['communication'], expected_points=[])
                            db.add(question)
                            await db.flush()
                            digest = hashlib.sha256(label.encode()).hexdigest()
                            accepted = GraphTurnInput(session_id=session.id, question_id=question.id, attempt='initial',
                                input_hash=digest, payload={'transcript': self.quote, 'skip': False}, status=input_status)
                            db.add(accepted)
                            await db.flush()
                            key = thread_key(session.id, question.id, 'initial', digest)
                            if label in ('pending_turn', 'committed_turn'):
                                expected.add(('resume_graph_turn', accepted.id))
                        else:
                            key = f'{kind}:{session.id}:v1'
                        db.add(GraphExecution(thread_id=key, session_id=session.id, kind=kind,
                            input_hash='0' * 64, plan_hash='1' * 64, status='running' if input_status == 'pending' else 'failed',
                            lease_owner='synthetic-live-worker' if label == 'leased_prepare' else None,
                            lease_until=now() + timedelta(minutes=5) if label == 'leased_prepare' else None))
                    if label in ('new_prepare', 'committed_prepare'):
                        expected.add(('prepare_session', session.id))
                    if label in ('new_finalize', 'committed_finalize'):
                        expected.add(('finalize_session', session.id))
                    await db.commit()
        class Queue:
            def __init__(self):
                self.calls = []
            async def enqueue_job(self, name, identifier):
                self.calls.append((name, identifier))
        queue = Queue()
        with patch.object(orchestrator, 'respond', AsyncMock(side_effect=AssertionError('Recovery scan must only queue'))) as respond:
            await recover_graph_jobs({'redis': queue})
            respond.assert_not_awaited()
        self.assertEqual(set(queue.calls), expected)
        self.assertEqual(len(queue.calls), len(expected))

    async def test_close_and_interrupt_before_commit_cannot_be_overwritten_by_graph(self):
        from app.graphs import turn
        real_execute = turn.execute
        for action in ('close', 'interrupt'):
            with self.subTest(action=action):
                sid, internal_id, state = await self.ready()
                qid = state['current_turn']['id']
                entered, release = asyncio.Event(), asyncio.Event()
                async def delayed_commit(kind, session_id, run_key, nodes, *args, **kwargs):
                    replaced = []
                    for name, callback in nodes:
                        if name == 'commit':
                            async def hold(ctx, callback=callback):
                                entered.set()
                                await release.wait()
                                return await callback(ctx)
                            replaced.append((name, hold))
                        else:
                            replaced.append((name, callback))
                    return await real_execute(kind, session_id, run_key, replaced, *args, **kwargs)
                with patch.object(turn, 'execute', side_effect=delayed_commit):
                    request = asyncio.create_task(self.text(sid, qid))
                    await asyncio.wait_for(entered.wait(), 5)
                    response = await self.client.post(f'/api/sessions/{sid}/' + action,
                        json={'question_id': qid, 'reason': 'device_lost'} if action == 'interrupt' else None)
                    self.assertEqual(response.status_code, 200, response.text)
                    release.set()
                    stale = await asyncio.wait_for(request, 5)
                self.assertEqual(stale.status_code, 409, stale.text)
                state = (await self.client.get(f'/api/sessions/{sid}/state')).json()
                self.assertEqual(state['status'], 'failed' if action == 'close' else 'running')
                if action == 'interrupt':
                    self.assertEqual(state['checkpoint']['phase'], 'interrupted')
                    self.assertEqual(state['checkpoint']['remaining_seconds'], 0)
                async with SessionLocal() as db:
                    self.assertEqual(await db.scalar(select(func.count()).select_from(InterviewAnswer).join(InterviewQuestion).where(
                        InterviewQuestion.session_id == internal_id)), 0)

    async def test_operator_acknowledgement_allows_one_same_audio_resubmission_after_ambiguous_stt(self):
        from app.graphs import manage
        sid, internal_id, state = await self.ready()
        qid = state['current_turn']['id']
        async def upload():
            return await self.client.post(f'/api/sessions/{sid}/answers',
                data={'question_id': qid, 'duration_ms': 12000},
                files={'audio': ('answer.webm', b'private-synthetic-audio-payload', 'audio/webm')})
        with patch('app.ai.speech.transcribe', AsyncMock(side_effect=[asyncio.TimeoutError('synthetic lost response'), self.quote])) as stt:
            uncertain = await upload()
            self.assertEqual(uncertain.status_code, 409, uncertain.text)
            async with SessionLocal() as db:
                self.assertEqual(await db.scalar(select(func.count()).select_from(GraphTurnInput)), 0)
                run = await db.scalar(select(GraphExecution).where(GraphExecution.session_id == internal_id, GraphExecution.kind == 'turn'))
                thread = run.thread_id
                self.assertEqual(run.status, 'uncertain')
            duplicate = await upload()
            self.assertEqual(duplicate.status_code, 409, duplicate.text)
            self.assertEqual(stt.await_count, 1)
            with self.assertRaises(ValueError):
                await manage.retry(sid, thread)
            another = await self.create()
            with self.assertRaises(ValueError):
                await manage.retry(another.json()['session_id'], thread, acknowledge=True)
            grant = await manage.retry(sid, thread, acknowledge=True)
            self.assertTrue(grant['awaiting_same_audio_resubmission'])
            self.assertEqual(stt.await_count, 1)  # Operator recovery cannot restart microphone/STT itself.
            diagnostics = json.dumps(await manage.inspect(sid))
            self.assertNotIn('private-synthetic-audio-payload', diagnostics)
            self.assertNotIn(self.quote, diagnostics)
            async with SessionLocal() as db:
                run = await db.get(GraphExecution, thread)
                self.assertTrue(run.allow_uncertain_once)
                self.assertEqual(len(run.retry_authorizations), 1)
                self.assertIsNone(run.retry_authorizations[0]['consumed_at'])
            success = await upload()
            self.assertEqual(success.status_code, 200, success.text)
            self.assertEqual(success.json()['transcript'], self.quote)
            self.assertEqual(stt.await_count, 2)
            repeated = await upload()
            self.assertEqual(repeated.status_code, 200, repeated.text)
            self.assertEqual(repeated.json()['answer_id'], success.json()['answer_id'])
            self.assertEqual(stt.await_count, 2)
        async with SessionLocal() as db:
            run = await db.get(GraphExecution, thread)
            self.assertFalse(run.allow_uncertain_once)
            self.assertIsNotNone(run.retry_authorizations[0]['consumed_at'])
            self.assertEqual(run.status, 'succeeded')


if __name__ == '__main__':
    unittest.main()
