from datetime import datetime
from uuid import uuid4
from typing import Optional
from sqlalchemy import String, Text, ForeignKey, JSON, DateTime, Integer, Float, Boolean, Index, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.utcnow()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    __table_args__ = {'sqlite_autoincrement': True}
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(190), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120))
    gender: Mapped[Optional[str]] = mapped_column(String(10))
    age: Mapped[Optional[int]]
    last_cv_text: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=now)


class InterviewSession(Base):
    __tablename__ = 'interview_sessions'
    __table_args__ = (Index('idx_user_finished', 'user_id', 'status', 'finished_at'), {'sqlite_autoincrement': True})
    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, default=lambda: str(uuid4()))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    candidate_name: Mapped[str] = mapped_column(String(120))
    gender: Mapped[str] = mapped_column(String(10))
    age: Mapped[int]
    job_role: Mapped[str] = mapped_column(String(150))
    level: Mapped[str] = mapped_column(String(20))
    industry: Mapped[str] = mapped_column(String(80))
    company: Mapped[str] = mapped_column(String(150), default='')
    job_description: Mapped[str] = mapped_column(Text)
    cv_text: Mapped[str] = mapped_column(Text)
    interviewer: Mapped[str] = mapped_column(String(20))
    question_count: Mapped[int] = mapped_column(default=7)
    answer_seconds: Mapped[int] = mapped_column(default=120)
    max_followups: Mapped[int] = mapped_column(default=3)
    status: Mapped[str] = mapped_column(String(20), default='preparing')
    cv_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    jd_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    script: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[Optional[str]] = mapped_column(String(255))
    total_score: Mapped[Optional[float]]
    review: Mapped[dict] = mapped_column(JSON, default=dict)
    star_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=now)
    started_at: Mapped[Optional[datetime]]
    finished_at: Mapped[Optional[datetime]]
    updated_at: Mapped[datetime] = mapped_column(default=now, onupdate=now)


class SessionCompetency(Base):
    __tablename__ = 'session_competencies'
    session_id: Mapped[int] = mapped_column(ForeignKey('interview_sessions.id', ondelete='CASCADE'), primary_key=True)
    competency: Mapped[str] = mapped_column(String(30), primary_key=True)
    weight: Mapped[int]
    score: Mapped[Optional[float]]


class InterviewQuestion(Base):
    __tablename__ = 'interview_questions'
    __table_args__ = {'sqlite_autoincrement': True}
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('interview_sessions.id', ondelete='CASCADE'), index=True)
    kind: Mapped[str] = mapped_column(String(20), default='main')
    main_order: Mapped[int]
    parent_question_id: Mapped[Optional[int]] = mapped_column(ForeignKey('interview_questions.id', ondelete='CASCADE'))
    slot: Mapped[str] = mapped_column(String(30), default='')
    category: Mapped[str] = mapped_column(String(60), default='')
    question_text: Mapped[str] = mapped_column(Text)
    expected_points: Mapped[list] = mapped_column(JSON, default=list)
    competencies: Mapped[list] = mapped_column(JSON, default=list)
    audio_file: Mapped[Optional[str]] = mapped_column(String(100))


class InterviewAnswer(Base):
    __tablename__ = 'interview_answers'
    __table_args__ = {'sqlite_autoincrement': True}
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey('interview_questions.id', ondelete='CASCADE'), unique=True)
    transcript: Mapped[str] = mapped_column(Text)
    duration_sec: Mapped[float]
    wpm: Mapped[int] = mapped_column(default=0)
    filler_count: Mapped[int] = mapped_column(default=0)
    retry_count: Mapped[int] = mapped_column(default=0)
    timed_out: Mapped[bool] = mapped_column(Boolean, default=False)
    think_sec: Mapped[float] = mapped_column(default=0)
    response_action: Mapped[str] = mapped_column(String(20))
    response_text: Mapped[str] = mapped_column(Text)
    result_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    competency_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    star: Mapped[dict] = mapped_column(JSON, default=dict)
    feedback: Mapped[dict] = mapped_column(JSON, default=dict)
    eval_status: Mapped[str] = mapped_column(String(20), default='pending')


class InterviewEvent(Base):
    __tablename__ = 'interview_events'
    __table_args__ = (UniqueConstraint('session_id', 'event_key'), {'sqlite_autoincrement': True})
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('interview_sessions.id', ondelete='CASCADE'), index=True)
    event_key: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=now)


class GraphTurnInput(Base):
    """Accepted transcript for a graph attempt, separate from completed answers."""
    __tablename__ = 'graph_turn_inputs'
    __table_args__ = (UniqueConstraint('question_id', 'attempt'), {'sqlite_autoincrement': True})
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('interview_sessions.id', ondelete='CASCADE'), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey('interview_questions.id', ondelete='CASCADE'))
    attempt: Mapped[str] = mapped_column(String(100))
    input_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    created_at: Mapped[datetime] = mapped_column(default=now)
