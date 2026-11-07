import asyncio
import re
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.deps import current_user
from app.models import User
from app.security import hash_password, verify_password

router = APIRouter()


class Registration(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    password_confirm: str
    gender: Literal['male', 'female']
    age: int = Field(ge=15, le=80)
    agree: bool

    @model_validator(mode='after')
    def validate_password(self):
        if len(self.password.encode()) > 72 or not re.search(r'[A-Za-z]', self.password) or not re.search(r'\d', self.password):
            raise ValueError('Password harus mengandung huruf dan angka, maksimal 72 byte.')
        if self.password != self.password_confirm or not self.agree:
            raise ValueError('Konfirmasi password dan persetujuan diperlukan.')
        return self


class Login(BaseModel):
    email: str = Field(max_length=190)
    password: str = Field(max_length=72)


@router.post('/api/auth/register')
async def register(data: Registration, request: Request, db=Depends(get_db)):
    user = User(email=str(data.email).lower(), name=data.name.strip(), gender=data.gender, age=data.age,
                password_hash=await asyncio.to_thread(hash_password, data.password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, 'Email sudah terdaftar.')
    request.session.clear()
    request.session['user_id'] = user.id
    return {'id': user.id, 'name': user.name}


@router.post('/api/auth/login')
async def login(data: Login, request: Request, db=Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == data.email.strip().lower()))
    if not user or not await asyncio.to_thread(verify_password, data.password, user.password_hash):
        raise HTTPException(401, 'Email atau password salah.')
    request.session.clear()
    request.session['user_id'] = user.id
    return {'id': user.id, 'name': user.name}


@router.post('/api/auth/logout')
async def logout(request: Request):
    request.session.clear()
    return {'ok': True}


@router.get('/api/me')
async def me(user=Depends(current_user)):
    return {'id': user.id, 'email': user.email, 'name': user.name, 'gender': user.gender, 'age': user.age,
            'has_cv': bool(user.last_cv_text), 'cv_preview': (user.last_cv_text or '')[:300]}
