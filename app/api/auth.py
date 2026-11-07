import asyncio
import re
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.deps import current_user
from app.models import User
from app.security import hash_password, verify_password
from app.config import settings
from app.log import emit
from app.security_models import AuthSession
from app.services.auth_sessions import issue_session, revoke_session, require_password, presented_hash, lock_credentials
from app.services import login_limits

router = APIRouter()
# This is never an account password; unknown accounts still perform bcrypt work.
_DUMMY_HASH = hash_password('preptiva-non-account-timing-placeholder-19')


def check_new_password(value):
    if not 8 <= len(value) <= 72 or len(value.encode()) > 72 or not re.search(r'[A-Za-z]', value) or not re.search(r'\d', value):
        raise ValueError('Password harus mengandung huruf dan angka, minimal 8 karakter dan maksimal 72 byte.')
    return value


class Registration(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr = Field(max_length=190)
    password: str = Field(min_length=8, max_length=72)
    password_confirm: str = Field(max_length=72)
    gender: Literal['male', 'female']
    age: int = Field(ge=15, le=80)
    agree: bool

    @model_validator(mode='after')
    def validate_password(self):
        check_new_password(self.password)
        if len(self.name.strip()) < 2:
            raise ValueError('Nama minimal 2 karakter.')
        if self.password != self.password_confirm or not self.agree:
            raise ValueError('Konfirmasi password dan persetujuan diperlukan.')
        return self


class Login(BaseModel):
    email: str = Field(max_length=190)
    password: str = Field(max_length=72)

    @field_validator('password')
    @classmethod
    def password_bytes(cls, value):
        if len(value.encode()) > 72:
            raise ValueError('Password maksimal 72 byte.')
        return value


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)
    password_confirm: str = Field(min_length=8, max_length=72)

    @model_validator(mode='after')
    def validate_password(self):
        check_new_password(self.new_password)
        if len(self.current_password.encode()) > 72 or self.password_confirm != self.new_password:
            raise ValueError('Konfirmasi password tidak sesuai atau password saat ini melebihi batas byte.')
        return self


@router.post('/api/auth/register')
async def register(data: Registration, request: Request, db=Depends(get_db)):
    await login_limits.consume('register-ip', login_limits.peer_address(request), settings.auth_login_ip_max_attempts)
    user = User(email=str(data.email).lower(), name=data.name.strip(), gender=data.gender, age=data.age,
                password_hash=await asyncio.to_thread(hash_password, data.password))
    db.add(user)
    try:
        await db.flush()
        await issue_session(request, user, db)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, 'Email sudah terdaftar.')
    emit('auth_registered')
    return {'id': user.id, 'name': user.name}


@router.post('/api/auth/login')
async def login(data: Login, request: Request, db=Depends(get_db)):
    email = data.email.strip().lower()
    await login_limits.reserve_login(request, email)
    # Row locking also orders login against password changes and account deletion.
    user = await db.scalar(select(User).where(User.email == email).with_for_update())
    valid = await asyncio.to_thread(verify_password, data.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not valid:
        emit('auth_login_failed', reason='invalid_credentials')
        raise HTTPException(401, 'Email atau password salah.')
    await issue_session(request, user, db)
    await db.commit()
    await login_limits.clear_account(email)
    emit('auth_logged_in')
    return {'id': user.id, 'name': user.name}


@router.post('/api/auth/logout')
async def logout(request: Request, db=Depends(get_db)):
    await revoke_session(request, db)
    await db.commit()
    emit('auth_logged_out')
    return {'ok': True}


@router.get('/api/auth/session')
async def login_session(request: Request, user=Depends(current_user), db=Depends(get_db)):
    session = await db.scalar(select(AuthSession).where(AuthSession.user_id == user.id,
        AuthSession.token_hash == presented_hash(request)))
    if not session:
        raise HTTPException(401, 'Silakan masuk terlebih dahulu.')
    return {'single_session': True, 'idle_timeout_seconds': settings.auth_idle_seconds,
            'absolute_timeout_seconds': settings.auth_absolute_seconds,
            'expires_at': session.expires_at.isoformat() + 'Z',
            'idle_expires_at': min(session.idle_expires_at, session.expires_at).isoformat() + 'Z'}


@router.post('/api/auth/password')
async def change_password(data: PasswordChange, request: Request, user=Depends(current_user), db=Depends(get_db)):
    await require_password(request, user, data.current_password, db)
    await lock_credentials(db, user)
    user.password_hash = await asyncio.to_thread(hash_password, data.new_password)
    await db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    await db.commit()
    request.session.clear()
    emit('auth_password_changed')
    return {'ok': True, 'reauthenticate': True}


@router.get('/api/me')
async def me(user=Depends(current_user)):
    return {'id': user.id, 'email': user.email, 'name': user.name, 'gender': user.gender, 'age': user.age,
            'has_cv': bool(user.last_cv_text), 'cv_preview': (user.last_cv_text or '')[:300]}
