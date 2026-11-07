"""Revocable login sessions; a signed cookie alone never grants access."""
import asyncio
import hashlib
import re
import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import delete, or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.config import settings
from app.log import emit
from app.models import User, now
from app.security import password_size_ok, verify_password
from app.security_models import AuthSession
from app.services import login_limits


def presented_hash(request):
    token = request.session.get('auth_token')
    if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        return None
    return hashlib.sha256(token.encode()).hexdigest()


async def resolve_user(request, db, touch=True):
    token_hash = presented_hash(request)
    if token_hash is None:
        return None
    stamp = now()
    valid = (AuthSession.token_hash == token_hash, AuthSession.expires_at > stamp,
             AuthSession.idle_expires_at > stamp)
    if touch:
        # Conditional update cannot renew an expired, revoked or replaced token.
        idle = stamp + timedelta(seconds=settings.auth_idle_seconds)
        result = await db.execute(update(AuthSession).where(*valid).values(
            last_seen_at=stamp, idle_expires_at=idle).returning(AuthSession.user_id))
        user_id = result.scalar_one_or_none()
        await db.commit()
    else:
        user_id = await db.scalar(select(AuthSession.user_id).where(*valid))
    if user_id is None:
        return None
    user = await db.get(User, user_id)
    # Authentication reads never mutate the cookie. A delayed 401 for an older
    # token must not clear a newer token issued by a concurrent login response.
    return user


async def issue_session(request, user, db):
    await lock_credentials(db, user)
    stamp = now()
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    old_hash = presented_hash(request)
    values = {'user_id': user.id, 'token_hash': token_hash, 'created_at': stamp,
              'last_seen_at': stamp, 'expires_at': stamp + timedelta(seconds=settings.auth_absolute_seconds),
              'idle_expires_at': stamp + timedelta(seconds=settings.auth_idle_seconds)}
    insert = postgres_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
    statement = insert(AuthSession).values(**values).on_conflict_do_update(
        index_elements=[AuthSession.user_id], set_={key: value for key, value in values.items() if key != 'user_id'},
        where=or_(AuthSession.expires_at <= stamp, AuthSession.idle_expires_at <= stamp,
                  AuthSession.token_hash == (old_hash or ''))).returning(AuthSession.user_id)
    if (await db.execute(statement)).scalar_one_or_none() is None:
        emit('auth_login_rejected', reason='session_active')
        raise HTTPException(409, 'Akun masih aktif di browser atau perangkat lain. Keluar dari sesi tersebut, '
                            f'atau tunggu {settings.auth_idle_seconds // 60} menit tanpa aktivitas sebelum masuk kembali.')
    if old_hash:
        # Successful account switching must not leave this browser's previous
        # account locked until idle expiry. A rejected switch leaves it intact.
        await db.execute(delete(AuthSession).where(AuthSession.token_hash == old_hash, AuthSession.user_id != user.id))
    request.session.clear()
    request.session['auth_token'] = token
    # Compatibility metadata for page rendering only. resolve_user never trusts it.
    request.session['user_id'] = user.id


async def revoke_session(request, db):
    token_hash = presented_hash(request)
    if token_hash:
        await db.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash))
    request.session.clear()


async def require_password(request, user, password, db):
    # Independent transactions keep rejected attempts durable without committing
    # a caller's pending privacy/profile mutation.
    await login_limits.consume('reauth-ip', login_limits.peer_address(request), settings.auth_login_ip_max_attempts)
    await login_limits.consume('reauth-account', str(user.id), settings.auth_login_max_attempts)
    valid = password_size_ok(password)
    if not valid or not await asyncio.to_thread(verify_password, password, user.password_hash):
        emit('auth_reauthentication_failed', reason='invalid_credentials')
        raise HTTPException(403, 'Kata sandi saat ini tidak sesuai.')
    await login_limits.clear_bucket('reauth-account', str(user.id))


async def lock_credentials(db, user):
    """Fence credential verification against password changes/deletion.

    Unlike SELECT FOR UPDATE, this also takes a write lock in SQLite. Call after
    require_password (whose limiter uses separate transactions), before mutation.
    """
    locked = await db.execute(update(User).where(User.id == user.id,
        User.password_hash == user.password_hash).values(id=User.id).execution_options(synchronize_session=False))
    if locked.rowcount != 1:
        raise HTTPException(403, 'Kredensial akun sudah berubah. Silakan masuk kembali.')
