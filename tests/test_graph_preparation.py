"""Preparation graph integration with isolated DB and injected providers."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Initialize isolated app settings before app.db is imported during discovery.
import test_system as _isolated_system_fixture

from app.ai import guidebook
from app.ai.assessment import snapshot
from app.ai.blueprint import blueprint
from app.graphs import preparation, runtime
from app.graphs.models import GraphCheckpoint, GraphExecution, GraphOperation
from app.models import Base, InterviewEvent, InterviewQuestion, InterviewSession, User


class GraphPreparationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.engine = create_async_engine('sqlite+aiosqlite:///' + str(Path(self.temporary.name) / 'graph.db'))
        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.patches = [patch.object(preparation, 'SessionLocal', self.factory)]
        for patcher in self.patches:
            patcher.start()
        self.cv = 'Saya mengerjakan proyek kuliah sistem inventaris dan menjadi pengurus organisasi mahasiswa.'
        async with self.factory() as db:
            user = User(name='Synthetic', email='graph-prepare@example.com', password_hash='unused')
            db.add(user)
            await db.flush()
            session = InterviewSession(user_id=user.id, candidate_name='Synthetic', gender='male', age=22,
                job_role='Engineer', level='junior', industry='Technology', company='', job_description='Mengembangkan produk bersama tim.',
                cv_text=self.cv, interviewer='hr', question_count=3, answer_seconds=90, max_followups=1, status='preparing',
                script={'runtime': {'engine': 'langgraph', 'version': 'langgraph-v1'},
                        'settings': {'panel': ['hr', 'user', 'manager'], 'language': 'id', 'career_stage': 'fresh_graduate',
                                     'dynamic_questions': True, 'streaming_voice': False},
                        'assessment': snapshot('hr', ['hr', 'user', 'manager']), 'guidebook': guidebook.snapshot()})
            db.add(session)
            await db.commit()
            self.sid = session.id
        self.parse = AsyncMock(return_value={'cv_summary': {'evidence': [{'kind': 'project', 'quote': self.cv}]},
                                            'jd_summary': {'responsibilities': ['Mengembangkan produk bersama tim.']}})
        self.generate = AsyncMock(side_effect=self.generated)
        self.speech = AsyncMock(side_effect=lambda text, persona, uuid, name, **kw: f'/api/sessions/{uuid}/audio/{name}')
        for target, value in (('parse_documents', self.parse), ('build_questions', self.generate)):
            patcher = patch.object(preparation.orchestrator, target, value)
            patcher.start(); self.patches.append(patcher)
        patcher = patch.object(preparation.speech, 'optional_synthesize', self.speech)
        patcher.start(); self.patches.append(patcher)

    async def asyncTearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        await self.engine.dispose()
        self.temporary.cleanup()

    async def generated(self, context, history):
        slots = blueprint(context['question_count'], context['uuid'], context['panel'], context['guidebook'], context['assessment'])
        wording = ['Bagaimana Anda membagi tugas dalam proyek kuliah itu?',
                   'Pemeriksaan apa yang memastikan hasil sistem inventaris benar?',
                   'Ceritakan keputusan ketika prioritas organisasi berubah.']
        return {'intro': 'Selamat datang.', 'closing': 'Terima kasih.', 'plan': slots,
                'questions': [{'slot': slot['slot'], 'category': 'example', 'question_text': wording[i],
                               'competencies': slot['competencies'], 'expected_points': ['Tindakan pribadi'], 'anchor_id': 'cv1'}
                              for i, slot in enumerate(slots)]}

    async def test_preparation_commits_fresh_graduate_context_once_and_checkpoints_only_refs(self):
        self.assertEqual((await preparation.prepare(self.sid))['status'], 'ready')
        await preparation.prepare(self.sid)
        self.assertEqual(self.parse.await_count, 1)
        self.assertEqual(self.generate.await_count, 1)
        self.assertEqual(self.speech.await_count, 3)  # intro, closing, first dynamic question
        supplied = self.generate.await_args.args[0]
        self.assertEqual(supplied['candidate_profile']['career_stage'], 'fresh_graduate')
        self.assertEqual(supplied['candidate_profile']['anchors'][0]['quote'], self.cv)
        async with self.factory() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(InterviewQuestion)), 3)
            self.assertEqual(await db.scalar(select(func.count()).select_from(InterviewEvent).where(InterviewEvent.event_key == 'ready')), 1)
            session = await db.get(InterviewSession, self.sid)
            self.assertEqual(session.script['settings']['panel'], ['hr', 'user', 'manager'])
            self.assertFalse(session.script['assessment']['validated'])
            checkpoints = list((await db.scalars(select(GraphCheckpoint))).all())
            self.assertGreater(len(checkpoints), 3)
            for item in checkpoints:
                self.assertNotIn(self.cv, str(item.checkpoint))
                self.assertNotIn('cv_summary', str(item.checkpoint))
            execution = await db.get(GraphExecution, f'prepare:{self.sid}:v1')
            self.assertEqual(execution.status, 'succeeded')

    async def test_failed_question_node_resumes_without_repeating_document_provider(self):
        failed = True
        async def fail_once(context, history):
            nonlocal failed
            if failed:
                failed = False
                raise ValueError('Injected invalid provider output')
            return await self.generated(context, history)
        self.generate.side_effect = fail_once
        with self.assertRaises(ValueError):
            await preparation.prepare(self.sid)
        async with self.factory() as db:
            self.assertEqual((await db.get(InterviewSession, self.sid)).status, 'preparing')
            self.assertEqual(await db.scalar(select(func.count()).select_from(InterviewQuestion)), 0)
        self.assertEqual((await preparation.prepare(self.sid))['status'], 'ready')
        self.assertEqual(self.parse.await_count, 1)
        self.assertEqual(self.generate.await_count, 2)

    async def test_paid_audio_ambiguity_requires_explicit_retry_and_reuses_completed_audio(self):
        failed = True
        async def synthesize(text, persona, uuid, name, **kwargs):
            nonlocal failed
            if name == 'closing.mp3' and failed:
                failed = False
                raise RuntimeError('Injected lost provider result')
            return f'/api/sessions/{uuid}/audio/{name}'
        self.speech.side_effect = synthesize
        with self.assertRaises(runtime.GraphOperationUncertain):
            await preparation.prepare(self.sid)
        with self.assertRaises(runtime.GraphOperationUncertain):
            await preparation.prepare(self.sid)
        self.assertEqual(self.speech.await_count, 2)
        self.assertEqual((await preparation.prepare(self.sid, allow_uncertain=True))['status'], 'ready')
        self.assertEqual(self.speech.await_count, 4)
        self.assertEqual(self.parse.await_count, 1)
        self.assertEqual(self.generate.await_count, 1)

    async def test_app_commit_before_checkpoint_is_reconciled_without_duplicate_questions(self):
        original = runtime.RunContext.operation
        async def gap(context, name, inputs, callback, **kwargs):
            if name == 'commit' and kwargs.get('_node_output'):
                await callback()
                raise RuntimeError('Injected crash after application commit')
            return await original(context, name, inputs, callback, **kwargs)
        with patch.object(runtime.RunContext, 'operation', gap), self.assertRaises(RuntimeError):
            await preparation.prepare(self.sid)
        async with self.factory() as db:
            self.assertEqual((await db.get(InterviewSession, self.sid)).status, 'ready')
        self.assertEqual((await preparation.prepare(self.sid))['status'], 'ready')
        async with self.factory() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(InterviewQuestion)), 3)
            self.assertEqual((await db.get(GraphExecution, f'prepare:{self.sid}:v1')).status, 'succeeded')
        self.assertEqual((self.parse.await_count, self.generate.await_count, self.speech.await_count), (1, 1, 3))


if __name__ == '__main__':
    unittest.main()
