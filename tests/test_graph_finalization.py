"""Synthetic graph finalization regressions; no provider or human validation."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Establish the existing suite's temporary app database before importing app.db.
# Each graph test below additionally owns a separate database/session factory.
import test_system as _isolated_system_fixture

from app.ai.assessment import snapshot
from app.ai.guidebook import snapshot as guide_snapshot
from app.config import settings
from app.graphs import finalization, panel_scoring, runtime
from app.graphs.models import GraphCheckpoint, GraphExecution, GraphOperation
from app.models import Base, InterviewAnswer, InterviewEvent, InterviewQuestion, InterviewSession, User


class PanelPolicyTests(unittest.TestCase):
    def test_personas_have_equal_weight_after_unit_means_and_insufficient_is_excluded(self):
        def unit(qid, score, status='measured'):
            return {'question_id': qid, 'skipped': False,
                    'scores': {'communication': {'score': score, 'status': status, 'evidence': [], 'source_refs': []}}}
        initial = [{'persona': 'hr', 'units': [unit(1, 5), unit(2, 3)]},
                   {'persona': 'user', 'units': [unit(1, 1), unit(2, 2, 'insufficient')]}]
        combined = panel_scoring.aggregate_panel(initial, snapshot('hr', ['hr', 'user']))
        self.assertEqual(combined['total_score'], 2.5)  # Mean of HR=4 and User=1, not (5+3+1)/3.
        communication = next(c for c in combined['competencies'] if c['key'] == 'communication')
        self.assertEqual(communication['measured_units'], 2)
        self.assertIsNone(next(c for c in combined['competencies'] if c['key'] == 'technical')['score'])
        self.assertFalse(panel_scoring.policy_snapshot()['human_validation'])

    def test_review_quotes_must_belong_to_original_rating_turn_and_cannot_change_scores(self):
        quote = 'Saya menyampaikan hasil penelitian kepada seluruh tim.'
        original = [{'question_id': 4, 'competency': 'communication', 'reason': 'score_gap',
                     'ratings': [{'source_refs': [{'turn_id': 'q4', 'quote': quote}]}]}]
        def review(turn='q4', text=quote):
            return {'reviews': [{'question_id': 4, 'competency': 'communication',
                                 'status': 'different_interpretation', 'rationale': 'Perbedaan tafsir bukti.',
                                 'replacement_score': 5, 'source_refs': [{'turn_id': turn, 'quote': text}]}]}
        sources = [{'turn_id': 'q4', 'transcript': quote}, {'turn_id': 'q5', 'transcript': quote}]
        for value in (review('q5'), review(text='Kutipan yang tidak pernah diucapkan.')):
            item = panel_scoring.validate_reviews(value, original, sources)[0]
            self.assertEqual(item['status'], 'unresolved')
            self.assertFalse(item['evidence_verified'])
        valid = panel_scoring.validate_reviews(review(), original, sources)[0]
        self.assertTrue(valid['evidence_verified'])
        self.assertNotIn('replacement_score', valid)
        self.assertFalse(valid['score_changes_applied'])


class GraphFinalizationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.engine = create_async_engine('sqlite+aiosqlite:///' + str(Path(self.temporary.name) / 'graph.db'))
        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.patches = [patch.object(finalization, 'SessionLocal', self.factory),
                        patch.object(settings, 'openai_api_key', '')]
        for item in self.patches:
            item.start()
        self.quote = 'Saya menyampaikan hasil penelitian kepada seluruh tim.'
        self.technical_quote = 'Saya menguji perubahan secara bertahap dan mengukur dampaknya.'

    async def asyncTearDown(self):
        for item in reversed(self.patches):
            item.stop()
        await self.engine.dispose()
        self.temporary.cleanup()

    async def seed(self, *, panel=None, em=False, all_skipped=False):
        panel = panel or ['hr', 'user']
        assessment = snapshot(panel[0], panel, job_role='Engineering Manager', use_job_rubric=em)
        async with self.factory() as db:
            user = User(name='Synthetic candidate', email='graph@example.test', password_hash='unused')
            db.add(user)
            await db.flush()
            session = InterviewSession(user_id=user.id, candidate_name=user.name, gender='male', age=28,
                job_role='Engineering Manager' if em else 'Product Designer', level='manager' if em else 'middle',
                industry='Technology', company='', cv_text='Synthetic CV, not sent to scoring.',
                job_description='Synthetic job.', interviewer=panel[0], status='scoring', question_count=3,
                script={'settings': {'language': 'id', 'panel': panel, 'evidence_policy': 'synthetic'},
                        'assessment': assessment, 'guidebook': guide_snapshot(),
                        'runtime': {'engine': 'langgraph-v1', 'aggregation_policy': panel_scoring.policy_snapshot()},
                        'speaker_by_order': {str(i): panel[(i - 1) % len(panel)] for i in range(1, 4)}})
            db.add(session)
            await db.flush()
            qids = []
            for order, (competency, transcript) in enumerate([
                    ('communication', self.quote), ('technical', self.technical_quote), ('teamwork', '')], 1):
                # HR-only fixture has no technical scope.
                if panel == ['hr'] and competency == 'technical':
                    competency = 'problem_solving'
                question = InterviewQuestion(session_id=session.id, main_order=order, kind='main',
                    slot='behavior', category='Synthetic', question_text=f'Ceritakan contoh pengalaman {order}?',
                    competencies=[competency], expected_points=['contribution'])
                db.add(question)
                await db.flush()
                skipped = all_skipped or order == 3
                db.add(InterviewAnswer(question_id=question.id, transcript='' if skipped else transcript,
                    duration_sec=0 if skipped else 10, response_action='next', response_text='',
                    result_payload={'skipped': skipped, 'input_mode': 'skipped' if skipped else 'text'}))
                qids.append(question.id)
            await db.commit()
            return session.id, qids

    async def evaluate(self, context):
        key = context['competencies'][0]
        score = 5 if context['interviewer'] == 'hr' else 1 if key == 'communication' else 4
        return {'competency_scores': {key: {'score': score, 'evidence': [context['source_turns'][0]['transcript']],
                    'evidence_sufficiency': 'sufficient', 'rationale': 'Synthetic evidence.'}},
                'feedback': {'strengths': ['Synthetic strength.'], 'improvements': []},
                'star': {'situation': True, 'task': True, 'action': True, 'result': False}}

    async def test_independent_scoped_ratings_resume_and_result_policy(self):
        sid, qids = await self.seed()
        seen = []
        async def evaluate(context):
            seen.append(deepcopy(context))
            self.assertNotIn('scores', context)
            self.assertNotIn('initial_evaluations', context)
            if context['interviewer'] == 'hr':
                self.assertNotIn('technical', context['competencies'])
                self.assertNotIn('| technical |', context['rubric'])
                self.assertNotIn('cv_summary', context)
            return await self.evaluate(context)
        async def review_call(system, context, **kwargs):
            async with self.factory() as db:
                operations = (await db.scalars(select(GraphOperation).where(
                    GraphOperation.thread_id == f'finalize:{sid}:v1', GraphOperation.status == 'succeeded'))).all()
                self.assertTrue({'node:initial_hr', 'node:initial_user'} <= {item.operation_key for item in operations})
            return {'reviews': [{'question_id': qids[0], 'competency': 'communication',
                                 'status': 'different_interpretation', 'rationale': 'Makna bukti masih berbeda.',
                                 'source_refs': [{'turn_id': f'q{qids[0]}', 'quote': self.quote}]}]}
        summary = {'summary': 'Synthetic review.', 'strengths': [], 'improvements': [], 'study_recommendations': []}
        with patch.object(finalization.orchestrator, 'evaluate', side_effect=evaluate) as evaluator, \
             patch('app.ai.model_router.complete', side_effect=review_call) as reviewer, \
             patch.object(finalization.orchestrator, 'summarize', side_effect=[RuntimeError('synthetic summary failure'), summary]):
            with self.assertRaises(RuntimeError):
                await finalization.finalize(sid)
            self.assertEqual(evaluator.await_count, 3)
            self.assertEqual(reviewer.await_count, 1)
            await self.engine.dispose()  # Resume from saved database/checkpoint, not live connections.
            result = await finalization.finalize(sid)
            self.assertEqual(result['status'], 'done')
            self.assertEqual(evaluator.await_count, 3)
            self.assertEqual(reviewer.await_count, 1)
            await finalization.finalize(sid)
            self.assertEqual(evaluator.await_count, 3)
        hr_context = next(item for item in seen if item['interviewer'] == 'hr')
        user_context = next(item for item in seen if item['interviewer'] == 'user' and item['competencies'] == ['communication'])
        self.assertEqual(hr_context['source_turns'], user_context['source_turns'])
        async with self.factory() as db:
            session = await db.get(InterviewSession, sid)
            output = panel_scoring.result_data(session)
            scores = {c['key']: c['score'] for c in output['competencies']}
            self.assertEqual(scores['communication'], 3)
            self.assertEqual(scores['technical'], 4)
            self.assertIsNone(scores['teamwork'])
            self.assertFalse(session.script['assessment']['validated'])
            self.assertFalse(session.review['panel_assessment']['human_validation'])
            self.assertTrue(session.review['panel_assessment']['disagreement_review']['triggered'])
            originals = session.review['panel_assessment']['initial_evaluations']
            self.assertEqual([p['units'][0]['scores']['communication']['score'] for p in originals], [5, 1])
            answers = (await db.scalars(select(InterviewAnswer).order_by(InterviewAnswer.id))).all()
            self.assertEqual(answers[0].competency_scores['communication']['score'], 5)
            self.assertEqual(answers[2].competency_scores, {})
            self.assertEqual({a.eval_status for a in answers}, {'done'})
            self.assertEqual(await db.scalar(select(func.count()).select_from(InterviewEvent).where(
                InterviewEvent.event_key == 'evaluation_completed')), 1)
            checkpoints = (await db.scalars(select(GraphCheckpoint))).all()
            raw = json.dumps([row.checkpoint for row in checkpoints])
            self.assertNotIn(self.quote, raw)
            self.assertNotIn('Synthetic CV', raw)
            execution = await db.get(GraphExecution, f'finalize:{sid}:v1')
            self.assertEqual(execution.status, 'succeeded')

    async def test_restart_after_app_commit_reconciles_without_rescoring(self):
        sid, _ = await self.seed(panel=['hr'])
        original = runtime.RunContext.operation
        injected = False
        async def checkpoint_gap(context, name, inputs, callback, **kwargs):
            nonlocal injected
            output = await original(context, name, inputs, callback, **kwargs)
            if name == 'commit' and kwargs.get('_node_output') and not injected:
                injected = True
                raise RuntimeError('Synthetic checkpoint gap after committed result')
            return output
        with patch.object(finalization.orchestrator, 'evaluate', side_effect=self.evaluate) as evaluator, \
             patch.object(finalization.orchestrator, 'summarize', AsyncMock(return_value={'summary': 'Saved.'})):
            with patch.object(runtime.RunContext, 'operation', checkpoint_gap), self.assertRaises(RuntimeError):
                await finalization.finalize(sid)
            async with self.factory() as db:
                self.assertEqual((await db.get(InterviewSession, sid)).status, 'done')
            calls = evaluator.await_count
            await self.engine.dispose()
            await finalization.finalize(sid)
            self.assertEqual(evaluator.await_count, calls)
            async with self.factory() as db:
                self.assertEqual(await db.scalar(select(func.count()).select_from(InterviewEvent).where(
                    InterviewEvent.event_key == 'evaluation_completed')), 1)

    async def test_changed_sources_reject_cached_ratings(self):
        sid, _ = await self.seed(panel=['hr'])
        with patch.object(finalization.orchestrator, 'evaluate', side_effect=self.evaluate) as evaluator, \
             patch.object(finalization.orchestrator, 'summarize', AsyncMock(side_effect=RuntimeError('stop'))):
            with self.assertRaises(RuntimeError):
                await finalization.finalize(sid)
            count = evaluator.await_count
            async with self.factory() as db:
                answer = await db.scalar(select(InterviewAnswer).order_by(InterviewAnswer.id))
                answer.transcript = 'A changed answer cannot reuse the earlier rating.'
                await db.commit()
            with self.assertRaises(runtime.GraphInputMismatch):
                await finalization.finalize(sid)
            self.assertEqual(evaluator.await_count, count)

    async def test_skipped_session_finishes_without_invented_scores_or_rating_calls(self):
        sid, _ = await self.seed(all_skipped=True)
        with patch.object(finalization.orchestrator, 'evaluate', AsyncMock()) as evaluator, \
             patch('app.ai.model_router.complete', AsyncMock()) as reviewer, \
             patch.object(finalization.orchestrator, 'summarize', AsyncMock(return_value={'summary': 'Belum ada bukti.'})) as summary:
            await finalization.finalize(sid)
            evaluator.assert_not_awaited()
            reviewer.assert_not_awaited()
            self.assertEqual(summary.call_args.args[0]['coverage']['weighted_percent'], 0)
        async with self.factory() as db:
            session = await db.get(InterviewSession, sid)
            self.assertIsNone(session.total_score)
            self.assertTrue(all(c['status'] == 'not_assessed' for c in panel_scoring.result_data(session)['competencies']))

    async def test_em_indicators_stay_bound_to_snapshot_and_original_turn(self):
        sid, _ = await self.seed(panel=['manager'], em=True)
        async def evaluate(context):
            key = context['competencies'][0]
            self.assertEqual(set(context['competency_definitions']), {key})
            anchor = context['competency_definitions'][key]['levels']['4']
            quote = context['source_turns'][0]['transcript'] if key == 'communication' else 'Invented technical quotation.'
            return {'competency_scores': {key: {'score': 4, 'evidence': [quote], 'evidence_sufficiency': 'sufficient',
                'indicators_met': [anchor['id']], 'indicator_evidence': [{'indicator_id': anchor['id'],
                    'turn_id': context['source_turns'][0]['turn_id'], 'quote': quote}],
                'next_level_gap': 'Hasil tindak lanjut belum dijelaskan.', 'rationale': 'Synthetic.'}},
                'star': {}, 'feedback': {}}
        with patch.object(finalization.orchestrator, 'evaluate', side_effect=evaluate), \
             patch.object(finalization.orchestrator, 'summarize', AsyncMock(return_value={'summary': 'Draf EM.'})):
            await finalization.finalize(sid)
        async with self.factory() as db:
            session = await db.get(InterviewSession, sid)
            self.assertEqual(session.total_score, 4)
            competencies = {item['key']: item for item in panel_scoring.result_data(session)['competencies']}
            self.assertEqual(competencies['technical']['status'], 'insufficient')
            self.assertIsNone(competencies['technical']['score'])
            answer = await db.scalar(select(InterviewAnswer).order_by(InterviewAnswer.id))
            detail = answer.competency_scores['communication']
            self.assertEqual(detail['indicator_validation'], 'verified')
            self.assertTrue(detail['sources'])
            self.assertFalse(session.script['assessment']['validated'])


if __name__ == '__main__':
    unittest.main()
