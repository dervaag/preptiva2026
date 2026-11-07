"""Server-side login state; tokens, addresses and IPs are never stored in clear."""
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, now


class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    # The primary key enforces one current login even across server processes.
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=now)
    last_seen_at: Mapped[datetime]
    expires_at: Mapped[datetime] = mapped_column(index=True)
    idle_expires_at: Mapped[datetime] = mapped_column(index=True)


class LoginLimit(Base):
    __tablename__ = 'login_limits'
    bucket_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int]
    expires_at: Mapped[datetime] = mapped_column(index=True)
