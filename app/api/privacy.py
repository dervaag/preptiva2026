from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.db import get_db
from app.deps import current_user
from app.privacy_models import DeletionReceipt
from app.services.auth_sessions import require_password
from app.services import privacy

router = APIRouter()


class DeletionRequest(BaseModel):
    password: str = Field(min_length=1, max_length=72)
    confirmation: str = Field(max_length=30)


async def authorize(data, expected, request, user, db):
    if data.confirmation != expected:
        raise HTTPException(422, 'Konfirmasi penghapusan tidak sesuai.')
    await require_password(request, user, data.password, db)


@router.get('/api/privacy/policy')
async def privacy_policy(user=Depends(current_user)):
    return privacy.policy()


@router.get('/api/privacy/receipts')
async def receipts(user=Depends(current_user), db=Depends(get_db)):
    items = (await db.scalars(select(DeletionReceipt).where(DeletionReceipt.user_id == user.id)
        .order_by(DeletionReceipt.created_at.desc()).limit(20))).all()
    return {'items': [await privacy.receipt_view(db, receipt.id) for receipt in items]}


@router.delete('/api/sessions/{sid}')
async def delete_session(sid: str, data: DeletionRequest, request: Request,
                         user=Depends(current_user), db=Depends(get_db)):
    await authorize(data, 'HAPUS', request, user, db)
    return {'receipt': await privacy.delete_data(db, user, 'session', sid=sid)}


@router.delete('/api/sessions')
async def delete_history(data: DeletionRequest, request: Request,
                         user=Depends(current_user), db=Depends(get_db)):
    await authorize(data, 'HAPUS RIWAYAT', request, user, db)
    return {'receipt': await privacy.delete_data(db, user, 'history')}


@router.delete('/api/profile')
async def delete_account(data: DeletionRequest, request: Request,
                         user=Depends(current_user), db=Depends(get_db)):
    await authorize(data, 'HAPUS AKUN', request, user, db)
    receipt = await privacy.delete_data(db, user, 'account')
    request.session.clear()
    return {'receipt': receipt}
