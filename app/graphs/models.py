"""Additive application-owned execution records and reference-only checkpoints."""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, now


class GraphExecution(Base):
    __tablename__ = 'graph_executions'
    thread_id: Mapped[str] = mapped_column(String(190), primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('interview_sessions.id', ondelete='CASCADE'), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    input_hash: Mapped[str] = mapped_column(String(64))
    plan_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default='pending')
    attempts: Mapped[int] = mapped_column(default=0)
    lease_owner: Mapped[Optional[str]] = mapped_column(String(36))
    lease_until: Mapped[Optional[datetime]] = mapped_column(DateTime)
    error_type: Mapped[Optional[str]] = mapped_column(String(100))
    allow_uncertain_once: Mapped[bool] = mapped_column(default=False)
    retry_authorizations: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(default=now)
    updated_at: Mapped[datetime] = mapped_column(default=now, onupdate=now)


class GraphOperation(Base):
    __tablename__ = 'graph_operations'
    thread_id: Mapped[str] = mapped_column(ForeignKey('graph_executions.thread_id', ondelete='CASCADE'), primary_key=True)
    operation_key: Mapped[str] = mapped_column(String(190), primary_key=True)
    input_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24))
    paid: Mapped[bool] = mapped_column(default=False)
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    telemetry: Mapped[dict] = mapped_column(JSON, default=dict)
    attempts: Mapped[int] = mapped_column(default=0)
    error_type: Mapped[Optional[str]] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(default=now)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_ms: Mapped[int] = mapped_column(default=0)


class GraphCheckpoint(Base):
    __tablename__ = 'graph_checkpoints'
    thread_id: Mapped[str] = mapped_column(ForeignKey('graph_executions.thread_id', ondelete='CASCADE'), primary_key=True)
    namespace: Mapped[str] = mapped_column(String(190), primary_key=True, default='')
    checkpoint_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    parent_id: Mapped[Optional[str]] = mapped_column(String(100))
    checkpoint: Mapped[dict] = mapped_column(JSON)
    meta: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=now)


class GraphWrite(Base):
    __tablename__ = 'graph_checkpoint_writes'
    thread_id: Mapped[str] = mapped_column(ForeignKey('graph_executions.thread_id', ondelete='CASCADE'), primary_key=True)
    namespace: Mapped[str] = mapped_column(String(190), primary_key=True, default='')
    checkpoint_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel: Mapped[str] = mapped_column(String(190))
    value: Mapped[dict] = mapped_column(JSON)
    task_path: Mapped[str] = mapped_column(String(500), default='')
