"""Transactional content removal, durable filesystem cleanup, and retention."""
import asyncio
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.db import SessionLocal
from app.log import emit
from app.models import User, InterviewSession, InterviewQuestion, InterviewAnswer, now
from app.privacy_models import DeletionReceipt, StorageCleanup
from app.services.locks import local_lock
from app.services.auth_sessions import lock_credentials
from app import storage


def policy():
    return {'audio_days': settings.retention_audio_days,
            'history_days': settings.retention_history_days,
            'receipt_days': settings.retention_receipt_days,
            'cv_retention': 'until_deleted', 'cv_scope': 'saved_profile_only',
            'retention_enabled': settings.retention_enabled,
            'limits': [
                'Hapus CV tersimpan hanya menghapus CV profil. Salinan CV di riwayat dihapus bersama riwayat atau akun.',
                'Hapus riwayat atau akun juga menghapus transkrip, hasil, checkpoint AI, dan audio tersimpan terkait.',
                'Tanda terima mencatat tindakan aplikasi; salinan pada penyedia AI atau backup terpisah mengikuti kebijakan penyedia/pengelola.',
            ]}


def public_receipt(receipt, pending=0):
    return {'id': receipt.id, 'scope': receipt.scope, 'status': receipt.status,
            'created_at': receipt.created_at.isoformat() + 'Z',
            'completed_at': receipt.completed_at.isoformat() + 'Z' if receipt.completed_at else None,
            'counts': receipt.counts, 'database_deleted': True, 'files_pending': pending}


async def receipt_view(db, receipt_id):
    receipt = await db.get(DeletionReceipt, receipt_id, populate_existing=True)
    if not receipt:
        return None
    pending = await db.scalar(select(func.count()).select_from(StorageCleanup).where(StorageCleanup.receipt_id == receipt_id))
    return public_receipt(receipt, pending)


async def cleanup_pending(receipt_id=None):
    """Journal rows are removed only after cleanup succeeded; exceptions stay private."""
    async with local_lock(('privacy-cleanup', 'all')):
        async with SessionLocal() as db:
            if db.bind.dialect.name == 'sqlite':
                await db.execute(text('BEGIN IMMEDIATE'))
            query = select(StorageCleanup).order_by(StorageCleanup.id)
            if receipt_id:
                query = query.where(StorageCleanup.receipt_id == receipt_id)
            jobs = (await db.scalars(query.with_for_update(skip_locked=True).limit(200))).all()
            touched = set()
            for job in jobs:
                touched.add(job.receipt_id)
                job.attempts += 1
                try:
                    removed = await asyncio.to_thread(storage.purge_session_files, job.session_uuid) if job.session_uuid else await asyncio.to_thread(storage.purge_legacy_caches)
                except (OSError, ValueError, RuntimeError) as exc:
                    emit('privacy_cleanup_failed', receipt_id=job.receipt_id, error_type=type(exc).__name__)
                    continue
                receipt = await db.scalar(select(DeletionReceipt).where(DeletionReceipt.id == job.receipt_id)
                                         .with_for_update().execution_options(populate_existing=True))
                receipt.counts = {**receipt.counts, 'files': receipt.counts.get('files', 0) + removed}
                await db.delete(job)
            await db.flush()
            for identifier in touched:
                remaining = await db.scalar(select(func.count()).select_from(StorageCleanup).where(StorageCleanup.receipt_id == identifier))
                if not remaining:
                    receipt = await db.get(DeletionReceipt, identifier)
                    receipt.status = 'complete'
                    receipt.completed_at = now()
            await db.commit()
            return {'processed': len(jobs), 'pending': await db.scalar(select(func.count()).select_from(StorageCleanup))}


async def _stage_deletion(db, user, scope, sid=None, cutoff=None):
    # A no-op write serializes with session creation/credential changes on both
    # SQLite and PostgreSQL, before receipt foreign keys acquire their own locks.
    if user:
        await lock_credentials(db, user)
        # Authentication may have loaded this object before a concurrent profile
        # update. Refresh only after the credential fence, while its lock is held.
        await db.refresh(user, attribute_names=['email', 'last_cv_text'])
    receipt = DeletionReceipt(user_id=user.id if user else None, scope=scope,
                              counts={'sessions': 0, 'questions': 0, 'answers': 0, 'files': 0,
                                      'accounts': int(scope == 'account'),
                                      'saved_cvs': int(bool(user and user.last_cv_text) and scope in ('saved_cv', 'account'))})
    db.add(receipt)
    await db.flush()
    if scope == 'saved_cv':
        user.last_cv_text = None
    else:
        query = select(InterviewSession)
        if user:
            query = query.where(InterviewSession.user_id == user.id)
        if sid:
            query = query.where(InterviewSession.uuid == sid)
        if cutoff:
            query = query.where(func.coalesce(InterviewSession.finished_at, InterviewSession.created_at) < cutoff)
        sessions = (await db.scalars(query.with_for_update())).all()
        if sid and not sessions:
            raise HTTPException(404, 'Sesi tidak ditemukan.')
        identifiers = [session.id for session in sessions]
        if identifiers:
            questions = select(InterviewQuestion.id).where(InterviewQuestion.session_id.in_(identifiers))
            receipt.counts = {**receipt.counts, 'sessions': len(identifiers),
                'questions': await db.scalar(select(func.count()).select_from(InterviewQuestion).where(InterviewQuestion.session_id.in_(identifiers))),
                'answers': await db.scalar(select(func.count()).select_from(InterviewAnswer).where(InterviewAnswer.question_id.in_(questions))),
                'files': 0}
            for session in sessions:
                db.add(StorageCleanup(receipt_id=receipt.id, session_uuid=session.uuid))
            await db.execute(delete(InterviewSession).where(InterviewSession.id.in_(identifiers)), execution_options={'synchronize_session': False})
        if scope == 'account':
            # Do not leave older receipts attached to the deleted identity.
            from app.services.login_limits import delete_account_limits
            await delete_account_limits(user, db)
            await db.execute(delete(User).where(User.id == user.id), execution_options={'synchronize_session': False})
    # Legacy global caches may contain personalized speech but have no ownership
    # index. Clearing both is required before declaring any deletion complete.
    db.add(StorageCleanup(receipt_id=receipt.id, session_uuid=None))
    await db.commit()
    return receipt.id


async def delete_data(db, user, scope, sid=None):
    if scope not in ('saved_cv', 'session', 'history', 'account'):
        raise ValueError('Lingkup penghapusan tidak valid.')
    if scope == 'session' and not sid:
        raise ValueError('Identitas sesi wajib untuk penghapusan satu riwayat.')
    async with local_lock(('privacy-user', user.id)):
        try:
            identifier = await _stage_deletion(db, user, scope, sid=sid)
        except Exception:
            await db.rollback()
            raise
    try:
        await cleanup_pending(identifier)
    except SQLAlchemyError as exc:
        # Database content is already gone; preserve a truthful pending receipt
        # and let the durable journal retry rather than reporting false success.
        emit('privacy_cleanup_failed', receipt_id=identifier, error_type=type(exc).__name__)
    return await receipt_view(db, identifier)


async def delete_saved_cv(db, user):
    return await delete_data(db, user, 'saved_cv')


async def run_retention(*, dry_run=True, at=None):
    at = at or now()
    cutoff = at - timedelta(days=settings.retention_history_days)
    async with SessionLocal() as db:
        expired = await db.scalar(select(func.count()).select_from(InterviewSession).where(
            func.coalesce(InterviewSession.finished_at, InterviewSession.created_at) < cutoff))
        pending = await db.scalar(select(func.count()).select_from(StorageCleanup))
        audio = await asyncio.to_thread(storage.expire_audio, at - timedelta(days=settings.retention_audio_days), apply=not dry_run)
        if dry_run:
            return {'dry_run': True, 'expired_sessions': expired, 'expired_audio_files': audio, 'pending_cleanup': pending}
        receipt_id = None
        if expired:
            receipt_id = await _stage_deletion(db, None, 'retention', cutoff=cutoff)
            expired = (await db.get(DeletionReceipt, receipt_id)).counts['sessions']
        else:
            # Legacy caches are emptied on the first maintenance run and remain
            # empty because new writers use per-session storage.
            await asyncio.to_thread(storage.purge_legacy_caches)
        await db.execute(delete(DeletionReceipt).where(DeletionReceipt.status == 'complete',
            DeletionReceipt.created_at < at - timedelta(days=settings.retention_receipt_days)))
        from app.security_models import AuthSession, LoginLimit
        await db.execute(delete(LoginLimit).where(LoginLimit.expires_at <= at))
        await db.execute(delete(AuthSession).where((AuthSession.expires_at <= at) | (AuthSession.idle_expires_at <= at)))
        await db.commit()
    outcome = await cleanup_pending()
    emit('retention_completed', sessions=expired, audio_files=audio, pending_cleanup=outcome['pending'])
    return {'dry_run': False, 'expired_sessions': expired, 'expired_audio_files': audio,
            'pending_cleanup': outcome['pending'], 'receipt_id': receipt_id}


async def retention_cleanup(ctx):
    try:
        if not settings.retention_enabled:
            # Disabling scheduled retention does not cancel requested deletion.
            return await cleanup_pending()
        return await run_retention(dry_run=False)
    except Exception as exc:
        emit('retention_failed', error_type=type(exc).__name__)
        return {'ok': False, 'retry_pending': True}
