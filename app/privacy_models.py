"""Minimal deletion receipts and retryable storage cleanup, without content."""
from datetime import datetime
from typing import Optional
from uuid import uuid4
from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base, now


class DeletionReceipt(Base):
    __tablename__ = 'deletion_receipts'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), index=True)
    scope: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default='pending_files')
    counts: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=now, index=True)
    completed_at: Mapped[Optional[datetime]]


class StorageCleanup(Base):
    __tablename__ = 'storage_cleanup'
    __table_args__ = {'sqlite_autoincrement': True}
    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[str] = mapped_column(ForeignKey('deletion_receipts.id', ondelete='CASCADE'), index=True)
    session_uuid: Mapped[Optional[str]] = mapped_column(String(36))
    # NULL session_uuid means legacy global caches, whose ownership was not tracked.
    attempts: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=now)
