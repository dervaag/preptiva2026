import asyncio
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Request
from pydantic import EmailStr, BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.db import get_db
from app.deps import current_user
from app.services.text import extract_pdf, validate_text
from app.services.auth_sessions import require_password, lock_credentials
from app.services.privacy import delete_saved_cv

router = APIRouter()


def profile_data(user):
    return {'id': user.id, 'name': user.name, 'email': user.email, 'gender': user.gender,
            'age': user.age, 'has_cv': bool(user.last_cv_text), 'cv_text': user.last_cv_text or ''}


@router.get('/api/profile')
async def get_profile(user=Depends(current_user)):
    return profile_data(user)


@router.patch('/api/profile')
async def update_profile(request: Request, name: Optional[str] = Form(None, min_length=2, max_length=120),
    email: Optional[EmailStr] = Form(None), gender: Optional[Literal['male', 'female']] = Form(None),
    age: Optional[int] = Form(None, ge=15, le=80), cv_text: Optional[str] = Form(None, max_length=60000),
    current_password: Optional[str] = Form(None, max_length=72),
    cv_pdf: Optional[UploadFile] = File(None), user=Depends(current_user), db=Depends(get_db)):
    changes = {}
    if name is not None:
        if len(name.strip()) < 2:
            raise HTTPException(422, 'Nama minimal 2 karakter.')
        changes['name'] = name.strip()
    if email is not None:
        address = str(email).strip().lower()
        if len(address) > 190:
            raise HTTPException(422, 'Email maksimal 190 karakter.')
        if address != user.email:
            await require_password(request, user, current_password or '', db)
            await lock_credentials(db, user)
        changes['email'] = address
    if gender is not None:
        changes['gender'] = gender
    if age is not None:
        changes['age'] = age
    if cv_pdf and cv_pdf.filename:
        changes['last_cv_text'] = await asyncio.to_thread(extract_pdf, await cv_pdf.read(5 * 1024 * 1024 + 1))
    elif cv_text is not None:
        changes['last_cv_text'] = validate_text(cv_text, 'CV')
    if not changes:
        raise HTTPException(422, 'Tidak ada perubahan untuk disimpan.')
    for key, value in changes.items():
        setattr(user, key, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, 'Email sudah terdaftar.')
    await db.refresh(user)
    return profile_data(user)


class DeleteSavedCV(BaseModel):
    password: str = Field(min_length=1, max_length=72)
    confirmation: Literal['HAPUS CV']


@router.delete('/api/profile/cv')
async def delete_cv(data: DeleteSavedCV, request: Request, user=Depends(current_user), db=Depends(get_db)):
    await require_password(request, user, data.password, db)
    receipt = await delete_saved_cv(db, user)
    return {**profile_data(user), 'receipt': receipt}
