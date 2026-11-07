"""Deletion/retention proof using synthetic identities, a temporary DB and files."""
import test_system  # Isolate settings/database before application imports.

import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from sqlalchemy import func, select
from app import storage
from app.config import settings
from app.db import SessionLocal
from app.models import (User, InterviewSession, InterviewQuestion, InterviewAnswer,
                        InterviewEvent, GraphTurnInput, now)
from app.graphs.models import GraphExecution, GraphOperation, GraphCheckpoint, GraphWrite
from app.privacy_models import DeletionReceipt, StorageCleanup
from app.services import privacy


class PrivacyTests(unittest.IsolatedAsyncioTestCase):
    register = test_system.SystemTests.register
    form = test_system.SystemTests.form
    create = test_system.SystemTests.create
    ready_session = test_system.SystemTests.ready_session

    async def asyncSetUp(self):
        await test_system.SystemTests.asyncSetUp(self)
        self.files = tempfile.TemporaryDirectory()
        self.privacy_storage_patch = patch.object(storage, 'ROOT', Path(self.files.name))
        self.privacy_storage_patch.start()

    async def asyncTearDown(self):
        self.privacy_storage_patch.stop()
        self.files.cleanup()
        await test_system.SystemTests.asyncTearDown(self)

    async def remove(self, path, confirmation, password='test12345', client=None):
        return await (client or self.client).request('DELETE', path,
            json={'password': password, 'confirmation': confirmation})

    async def seed_content(self):
        sid, internal, state = await self.ready_session()
        qid = state['current_turn']['id']
        async with SessionLocal() as db:
            answer = InterviewAnswer(question_id=qid, transcript='PRIVATE-SYNTHETIC-ANSWER', duration_sec=10,
                response_action='next', response_text='Synthetic response')
            db.add(answer)
            db.add(GraphTurnInput(session_id=internal, question_id=qid, attempt='initial', input_hash='a' * 64,
                                  payload={'transcript': 'PRIVATE-SYNTHETIC-ANSWER'}))
            db.add(GraphExecution(thread_id='privacy-graph', session_id=internal, kind='turn', input_hash='a' * 64,
                                  plan_hash='b' * 64))
            await db.flush()
            db.add(GraphOperation(thread_id='privacy-graph', operation_key='model', input_hash='a' * 64,
                                  status='complete', output={'private': 'PRIVATE-SYNTHETIC-CV'}))
            db.add(GraphCheckpoint(thread_id='privacy-graph', namespace='', checkpoint_id='c1',
                                   checkpoint={'private': 'PRIVATE-SYNTHETIC-CV'}, meta={}))
            db.add(GraphWrite(thread_id='privacy-graph', namespace='', checkpoint_id='c1', task_id='t1',
                              position=1, channel='state', value={'private': 'PRIVATE-SYNTHETIC-CV'}))
            await db.commit()
        storage.write_session_audio(sid, 'q1.mp3', b'synthetic-audio')
        storage.write_session_audio(sid, 'cache1.mp3', b'synthetic-cache', cache=True)
        return sid, internal

    async def test_history_deletion_cascades_all_evidence_and_prevents_late_audio_writes(self):
        sid, internal = await self.seed_content()
        response = await self.remove(f'/api/sessions/{sid}', 'HAPUS')
        self.assertEqual(response.status_code, 200, response.text)
        receipt = response.json()['receipt']
        self.assertEqual(receipt['status'], 'complete')
        self.assertEqual(receipt['counts']['sessions'], 1)
        self.assertEqual(receipt['counts']['answers'], 1)
        self.assertEqual(receipt['counts']['files'], 2)
        self.assertEqual(receipt['files_pending'], 0)
        self.assertNotIn('PRIVATE', response.text)
        self.assertNotIn(sid, response.text)
        async with SessionLocal() as db:
            for model in (InterviewSession, InterviewQuestion, InterviewAnswer, InterviewEvent,
                          GraphTurnInput, GraphExecution, GraphOperation, GraphCheckpoint, GraphWrite):
                self.assertEqual(await db.scalar(select(func.count()).select_from(model)), 0, model.__name__)
        self.assertEqual((await self.client.get(f'/api/sessions/{sid}/state')).status_code, 404)
        self.assertIsNone(storage.safe_audio_path(sid, 'q1.mp3'))
        self.assertFalse((Path(self.files.name) / 'data/audio' / sid).exists())
        with self.assertRaises(storage.SessionStorageDeleted):
            storage.write_session_audio(sid, 'late.mp3', b'late-provider-result')
        source = "from pathlib import Path; import sys; from app import storage; storage.ROOT=Path(sys.argv[1]); storage.write_session_audio(sys.argv[2], 'late.mp3', b'late')"
        child = await asyncio.to_thread(subprocess.run, [sys.executable, '-c', source, self.files.name, sid],
                                        capture_output=True, text=True)
        self.assertNotEqual(child.returncode, 0)
        self.assertIn('SessionStorageDeleted', child.stderr)
        receipts = (await self.client.get('/api/privacy/receipts')).json()['items']
        self.assertEqual(receipts[0]['id'], receipt['id'])

    async def test_owner_password_confirmation_and_csrf_guard_deletion(self):
        sid, _ = await self.seed_content()
        self.assertEqual((await self.register(self.other, 'other-private@example.com')).status_code, 200)
        response = await self.remove(f'/api/sessions/{sid}', 'HAPUS', client=self.other)
        self.assertEqual(response.status_code, 404)
        self.assertEqual((await self.remove(f'/api/sessions/{sid}', 'WRONG')).status_code, 422)
        self.assertEqual((await self.remove(f'/api/sessions/{sid}', 'HAPUS', 'wrong12345')).status_code, 403)
        response = await self.client.request('DELETE', f'/api/sessions/{sid}',
            headers={'Origin': 'https://attacker.example'}, json={'password': 'test12345', 'confirmation': 'HAPUS'})
        self.assertEqual(response.status_code, 403)
        self.assertIsNotNone(storage.safe_audio_path(sid, 'q1.mp3'))
        self.assertEqual((await self.client.get(f'/api/sessions/{sid}/state')).status_code, 200)
        self.assertEqual((await self.other.get('/api/privacy/receipts')).json()['items'], [])

    async def test_account_removal_preserves_other_users_and_revokes_cookie_replay(self):
        sid, internal = await self.seed_content()
        self.assertEqual((await self.register(self.other, 'other-private@example.com')).status_code, 200)
        other_user = (await self.other.get('/api/me')).json()['id']
        cookie = self.client.cookies.get('isim_session')
        response = await self.remove('/api/profile', 'HAPUS AKUN')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['receipt']['status'], 'complete')
        self.assertEqual(response.json()['receipt']['counts']['accounts'], 1)
        self.assertEqual((await self.client.get('/api/me')).status_code, 401)
        self.client.cookies.set('isim_session', cookie)
        self.assertEqual((await self.client.get('/api/me')).status_code, 401)
        self.assertEqual((await self.other.get('/api/me')).json()['id'], other_user)
        async with SessionLocal() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(User)), 1)
            self.assertEqual(await db.scalar(select(func.count()).select_from(InterviewSession)), 0)
            receipt = await db.get(DeletionReceipt, response.json()['receipt']['id'])
            self.assertIsNone(receipt.user_id)
        self.assertEqual((await self.other.get('/api/privacy/receipts')).json()['items'], [])

    async def test_saved_cv_deletion_receipt_is_explicit_about_historical_snapshots(self):
        sid, internal = await self.seed_content()
        original = self.form()['cv_text'].strip()
        response = await self.remove('/api/profile/cv', 'HAPUS CV')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['receipt']['scope'], 'saved_cv')
        self.assertEqual(response.json()['receipt']['counts']['saved_cvs'], 1)
        self.assertFalse((await self.client.get('/api/me')).json()['has_cv'])
        async with SessionLocal() as db:
            stored = await db.get(InterviewSession, internal)
            self.assertEqual(stored.cv_text, original)
        self.assertEqual((await self.client.get('/api/privacy/policy')).json()['cv_scope'], 'saved_profile_only')
        response = await self.remove('/api/sessions', 'HAPUS RIWAYAT')
        self.assertEqual(response.status_code, 200)
        async with SessionLocal() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(InterviewSession)), 0)

    async def test_failed_filesystem_cleanup_has_pending_receipt_and_retry_finishes_it(self):
        sid, internal = await self.seed_content()
        with patch('app.storage.purge_session_files', side_effect=OSError('PRIVATE-FILESYSTEM-DETAIL')):
            response = await self.remove(f'/api/sessions/{sid}', 'HAPUS')
        self.assertEqual(response.status_code, 200, response.text)
        receipt = response.json()['receipt']
        self.assertEqual(receipt['status'], 'pending_files')
        self.assertTrue(receipt['database_deleted'])
        self.assertEqual(receipt['files_pending'], 1)
        self.assertIsNone(receipt['completed_at'])
        async with SessionLocal() as db:
            self.assertIsNone(await db.get(InterviewSession, internal))
        self.assertTrue((Path(self.files.name) / 'data/audio' / sid).exists())
        await privacy.cleanup_pending()
        items = (await self.client.get('/api/privacy/receipts')).json()['items']
        self.assertEqual(items[0]['status'], 'complete')
        self.assertEqual(items[0]['files_pending'], 0)
        self.assertFalse((Path(self.files.name) / 'data/audio' / sid).exists())

    async def test_database_rollback_does_not_delete_or_tombstone_audio(self):
        sid, internal = await self.seed_content()
        async with SessionLocal() as db:
            user = await db.scalar(select(User).where(User.email == 'budi@example.com'))
            with patch.object(db, 'commit', AsyncMock(side_effect=RuntimeError('synthetic commit failure'))):
                with self.assertRaises(RuntimeError):
                    await privacy.delete_data(db, user, 'session', sid=sid)
        async with SessionLocal() as db:
            self.assertIsNotNone(await db.get(InterviewSession, internal))
            self.assertEqual(await db.scalar(select(func.count()).select_from(DeletionReceipt)), 0)
            self.assertEqual(await db.scalar(select(func.count()).select_from(StorageCleanup)), 0)
        storage.write_session_audio(sid, 'still-live.mp3', b'allowed-after-rollback')
        self.assertEqual(storage.read_session_audio(sid, 'q1.mp3'), b'synthetic-audio')

    async def test_password_change_race_cannot_authorize_stale_deletion(self):
        from sqlalchemy import update
        from fastapi import HTTPException
        sid, internal = await self.seed_content()
        async with SessionLocal() as db:
            user = await db.scalar(select(User).where(User.email == 'budi@example.com'))
            async with SessionLocal() as other:
                await other.execute(update(User).where(User.id == user.id).values(password_hash='changed-elsewhere'))
                await other.commit()
            with self.assertRaises(HTTPException) as caught:
                await privacy.delete_data(db, user, 'session', sid=sid)
            self.assertEqual(caught.exception.status_code, 403)
        async with SessionLocal() as db:
            self.assertIsNotNone(await db.get(InterviewSession, internal))
            self.assertEqual(await db.scalar(select(func.count()).select_from(DeletionReceipt)), 0)
        self.assertIsNotNone(storage.safe_audio_path(sid, 'q1.mp3'))

    async def test_cv_saved_after_auth_snapshot_is_still_deleted(self):
        from sqlalchemy import update
        async with SessionLocal() as db:
            user = await db.scalar(select(User).where(User.email == 'budi@example.com'))
            self.assertIsNone(user.last_cv_text)
            async with SessionLocal() as other:
                await other.execute(update(User).where(User.id == user.id).values(last_cv_text='PRIVATE-CONCURRENT-CV'))
                await other.commit()
            receipt = await privacy.delete_saved_cv(db, user)
            self.assertEqual(receipt['counts']['saved_cvs'], 1)
            self.assertIsNone(user.last_cv_text)
        async with SessionLocal() as db:
            self.assertIsNone((await db.scalar(select(User).where(User.email == 'budi@example.com'))).last_cv_text)

    async def test_retention_dry_run_boundaries_idempotency_and_minimal_receipt_expiry(self):
        sid, internal, _ = await self.ready_session()
        recent_sid, recent_id, _ = await self.ready_session()
        fixed = datetime(2026, 11, 7, 12)
        async with SessionLocal() as db:
            old = await db.get(InterviewSession, internal)
            old.created_at = fixed - timedelta(days=91)
            old.finished_at = fixed - timedelta(days=91)
            recent = await db.get(InterviewSession, recent_id)
            recent.created_at = fixed - timedelta(days=91)
            recent.finished_at = fixed - timedelta(days=89)
            user = await db.get(User, recent.user_id)
            user.last_cv_text = 'CV kept until explicit deletion'
            db.add(DeletionReceipt(user_id=user.id, scope='saved_cv', status='complete',
                counts={}, created_at=fixed-timedelta(days=31), completed_at=fixed-timedelta(days=31)))
            await db.commit()
        old_file = storage.write_session_audio(recent_sid, 'old.mp3', b'old')
        edge_file = storage.write_session_audio(recent_sid, 'edge.mp3', b'edge', cache=True)
        stamp = (fixed - timedelta(days=7)).replace(tzinfo=timezone.utc).timestamp()
        os.utime(old_file, (stamp - 1, stamp - 1))
        os.utime(edge_file, (stamp, stamp))
        preview = await privacy.run_retention(at=fixed)
        self.assertTrue(preview['dry_run'])
        self.assertEqual(preview['expired_sessions'], 1)
        self.assertEqual(preview['expired_audio_files'], 1)
        self.assertTrue(old_file.exists())
        actual = await privacy.run_retention(dry_run=False, at=fixed)
        self.assertEqual(actual['expired_sessions'], 1)
        self.assertFalse(old_file.exists())
        self.assertTrue(edge_file.exists())
        async with SessionLocal() as db:
            self.assertIsNone(await db.get(InterviewSession, internal))
            self.assertIsNotNone(await db.get(InterviewSession, recent_id))
            self.assertEqual((await db.get(User, recent.user_id)).last_cv_text, 'CV kept until explicit deletion')
            self.assertEqual(await db.scalar(select(func.count()).select_from(DeletionReceipt)), 1)
        repeated = await privacy.run_retention(dry_run=False, at=fixed)
        self.assertEqual(repeated['expired_sessions'], 0)
        self.assertEqual(repeated['expired_audio_files'], 0)


class StorageSafetyTests(unittest.TestCase):
    def test_missing_reads_do_not_create_content_and_symlinks_cannot_escape_storage(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, 'ROOT', Path(directory)):
            self.assertIsNone(storage.safe_audio_path('session-test', 'none.mp3'))
            self.assertFalse((Path(directory) / 'data').exists())
            for session in ('../outside', '/tmp', '', 'a/b'):
                with self.subTest(session=session), self.assertRaises(ValueError):
                    storage.write_session_audio(session, 'a.mp3', b'content')
            outside = Path(directory) / 'outside'
            outside.mkdir()
            secret = outside / 'secret.mp3'
            secret.write_bytes(b'keep')
            base = Path(directory) / 'data/audio'
            base.mkdir(parents=True)
            (base / 'linked').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                storage.write_session_audio('linked', 'secret.mp3', b'overwrite')
            self.assertIsNone(storage.safe_audio_path('linked', 'secret.mp3'))
            storage.mark_session_deleted('linked')
            self.assertEqual(secret.read_bytes(), b'keep')
            self.assertFalse((base / 'linked').exists())

    def test_global_legacy_cache_is_removed_without_following_links(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, 'ROOT', Path(directory)):
            outside = Path(directory) / 'outside'
            outside.mkdir()
            secret = outside / 'keep.mp3'
            secret.write_bytes(b'keep')
            cache = Path(directory) / 'data/tts_cache'
            cache.mkdir(parents=True)
            (cache / 'old.mp3').write_bytes(b'personalized-legacy-speech')
            (cache / 'link').symlink_to(outside, target_is_directory=True)
            self.assertEqual(storage.purge_legacy_caches(), 2)
            self.assertFalse(cache.exists())
            self.assertEqual(secret.read_bytes(), b'keep')

    def test_audio_root_symlink_cannot_redirect_deletion(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, 'ROOT', Path(directory)):
            outside = Path(directory) / 'outside/session-test'
            outside.mkdir(parents=True)
            secret = outside / 'keep.mp3'
            secret.write_bytes(b'keep')
            base = Path(directory) / 'data'
            base.mkdir()
            (base / 'audio').symlink_to(outside.parent, target_is_directory=True)
            with self.assertRaises(ValueError):
                storage.mark_session_deleted('session-test')
            self.assertEqual(secret.read_bytes(), b'keep')


if __name__ == '__main__':
    unittest.main()
