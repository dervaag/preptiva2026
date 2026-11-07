from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from app.db import get_db
from app.models import User, InterviewSession


async def current_user(request: Request, db=Depends(get_db)):
    user = await db.get(User, request.session.get('user_id', -1))
    if not user:
        raise HTTPException(401, 'Silakan masuk terlebih dahulu.')
    return user


async def owned_session(sid: str, user=Depends(current_user), db=Depends(get_db)):
    session = await db.scalar(select(InterviewSession).where(InterviewSession.uuid == sid, InterviewSession.user_id == user.id))
    if not session:
        raise HTTPException(404, 'Sesi tidak ditemukan.')
    return session
