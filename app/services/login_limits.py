"""Atomic fixed-window authentication limits shared by PostgreSQL/SQLite workers."""
import hashlib
import hmac
import math
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import case, delete, or_, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.config import settings
from app.db import SessionLocal
from app.log import emit
from app.models import now
from app.security_models import LoginLimit


def bucket_key(purpose, value):
    # A keyed digest prevents offline dictionary recovery of email/IP counters.
    return hmac.new(settings.secret_key.encode(),
                    ('preptiva-auth-limit-v1\0' + purpose + '\0' + value).encode(), hashlib.sha256).hexdigest()


def peer_address(request):
    # Only the ASGI peer address is used; never trust a submitted X-Forwarded-For.
    return request.client.host if request.client else 'unknown-peer'


async def consume(purpose, value, maximum):
    stamp = now()
    expires = stamp + timedelta(seconds=settings.auth_login_window_seconds)
    key = bucket_key(purpose, value)
    async with SessionLocal() as db:
        insert = postgres_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
        expired = LoginLimit.expires_at <= stamp
        statement = insert(LoginLimit).values(bucket_hash=key, attempts=1, expires_at=expires)
        statement = statement.on_conflict_do_update(index_elements=[LoginLimit.bucket_hash],
            set_={'attempts': case((expired, 1), else_=LoginLimit.attempts + 1),
                  'expires_at': case((expired, expires), else_=LoginLimit.expires_at)},
            where=or_(expired, LoginLimit.attempts < maximum)).returning(LoginLimit.expires_at)
        accepted = (await db.execute(statement)).scalar_one_or_none()
        if accepted is None:
            blocked_until = await db.scalar(select(LoginLimit.expires_at).where(LoginLimit.bucket_hash == key))
            await db.commit()
            retry = max(1, math.ceil((blocked_until - stamp).total_seconds()))
            emit('auth_rate_limited', reason='attempt_limit')
            raise HTTPException(429, 'Terlalu banyak percobaan. Tunggu sebentar lalu coba kembali.',
                                headers={'Retry-After': str(retry)})
        await db.commit()


async def reserve_login(request, email):
    # A blocked IP must not be able to consume another account's attempt budget.
    await consume('login-ip', peer_address(request), settings.auth_login_ip_max_attempts)
    await consume('login-account', email, settings.auth_login_max_attempts)


async def clear_bucket(purpose, value):
    async with SessionLocal() as db:
        await db.execute(delete(LoginLimit).where(LoginLimit.bucket_hash == bucket_key(purpose, value)))
        await db.commit()


async def clear_account(email):
    await clear_bucket('login-account', email)


async def delete_account_limits(user, db):
    """Join an account-deletion transaction; IP abuse budgets are not erased."""
    await db.execute(delete(LoginLimit).where(LoginLimit.bucket_hash.in_([
        bucket_key('login-account', user.email), bucket_key('reauth-account', str(user.id))])))
