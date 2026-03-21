from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class Jurisdiction(Base):
    __tablename__ = "jurisdictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    level: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(120))
    parent_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Agency(Base):
    __tablename__ = "agencies"
    __table_args__ = (UniqueConstraint("jurisdiction_id", "name", name="uq_agency_jurisdiction_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    jurisdiction_id: Mapped[int] = mapped_column(ForeignKey("jurisdictions.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    homepage_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    jurisdiction: Mapped[Jurisdiction] = relationship()


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(32), default="benefit")
    category: Mapped[str] = mapped_column(String(64), default="general")
    family: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    apply_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    documents_json: Mapped[Optional[list[dict]]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    jurisdiction_id: Mapped[int] = mapped_column(ForeignKey("jurisdictions.id"), index=True)
    agency_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agencies.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    jurisdiction: Mapped[Jurisdiction] = relationship()
    agency: Mapped[Optional[Agency]] = relationship()
    versions: Mapped[list["ProgramVersion"]] = relationship(back_populates="program", cascade="all, delete-orphan")
    sources: Mapped[list["Source"]] = relationship(back_populates="program", cascade="all, delete-orphan")


class ProgramVersion(Base):
    __tablename__ = "program_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id"), index=True)
    version_label: Mapped[str] = mapped_column(String(80))
    signature: Mapped[str] = mapped_column(String(64), index=True)
    publication_state: Mapped[str] = mapped_column(String(32), default="published")
    effective_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_freshness_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    program: Mapped[Program] = relationship(back_populates="versions")
    rules: Mapped[list["EligibilityRule"]] = relationship(back_populates="program_version", cascade="all, delete-orphan")
    amount_rules: Mapped[list["AmountRule"]] = relationship(back_populates="program_version", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    prompt: Mapped[str] = mapped_column(Text)
    hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    input_type: Mapped[str] = mapped_column(String(32))
    sensitivity_level: Mapped[str] = mapped_column(String(32), default="low")
    options_json: Mapped[Optional[list[dict]]] = mapped_column(JSON, nullable=True)
    sort_weight: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class QuestionVariant(Base):
    __tablename__ = "question_variants"
    __table_args__ = (
        UniqueConstraint("question_key", "depth_tier", name="uq_variant_key_tier"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    question_key: Mapped[str] = mapped_column(String(120), ForeignKey("questions.key"), index=True)
    depth_tier: Mapped[str] = mapped_column(String(16))  # "simple", "standard", "detailed"
    prompt: Mapped[str] = mapped_column(Text)
    hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    input_type: Mapped[str] = mapped_column(String(32))
    options_json: Mapped[Optional[list[dict]]] = mapped_column(JSON, nullable=True)
    normalizer: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class EligibilityRule(Base):
    __tablename__ = "eligibility_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_version_id: Mapped[int] = mapped_column(ForeignKey("program_versions.id"), index=True)
    question_key: Mapped[str] = mapped_column(String(120), index=True)
    operator: Mapped[str] = mapped_column(String(32), default="matches_any")
    expected_values_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    label: Mapped[str] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    source_key: Mapped[str] = mapped_column(String(120))
    source_citation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    program_version: Mapped[ProgramVersion] = relationship(back_populates="rules")


class AmountRule(Base):
    __tablename__ = "amount_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_version_id: Mapped[int] = mapped_column(ForeignKey("program_versions.id"), index=True)
    amount_type: Mapped[str] = mapped_column(String(32), default="unknown")
    display_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    formula_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    input_keys: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    min_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    period: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    source_key: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    program_version: Mapped[ProgramVersion] = relationship(back_populates="amount_rules")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    program_id: Mapped[Optional[int]] = mapped_column(ForeignKey("programs.id"), nullable=True)
    jurisdiction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("jurisdictions.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(64))
    authority_rank: Mapped[int] = mapped_column(Integer, default=75)
    parser_type: Mapped[str] = mapped_column(String(64), default="html")
    fetch_cadence: Mapped[str] = mapped_column(String(32), default="weekly")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    program: Mapped[Optional[Program]] = relationship(back_populates="sources")
    jurisdiction: Mapped[Optional[Jurisdiction]] = relationship()
    snapshots: Mapped[list["SourceSnapshot"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class SourceSnapshot(Base):
    __tablename__ = "source_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    raw_excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(32), default="parsed")

    source: Mapped[Source] = relationship(back_populates="snapshots")


class ChangeEvent(Base):
    __tablename__ = "change_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    previous_snapshot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("source_snapshots.id"), nullable=True)
    current_snapshot_id: Mapped[int] = mapped_column(ForeignKey("source_snapshots.id"))
    diff_type: Mapped[str] = mapped_column(String(64))
    materiality_score: Mapped[int] = mapped_column(Integer, default=50)
    review_required: Mapped[bool] = mapped_column(Boolean, default=True)
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    source: Mapped[Source] = relationship()


class ReviewTask(Base):
    __tablename__ = "review_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    change_event_id: Mapped[int] = mapped_column(ForeignKey("change_events.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="open")
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    change_event: Mapped[ChangeEvent] = relationship()


class ScreeningSession(Base):
    __tablename__ = "screening_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=lambda: str(uuid4()))
    scope: Mapped[str] = mapped_column(String(16), default="both")
    state_code: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    categories_json: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    depth_mode: Mapped[str] = mapped_column(String(16), default="standard")
    depth_value: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    answers: Mapped[list["SessionAnswer"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class SessionAnswer(Base):
    __tablename__ = "session_answers"
    __table_args__ = (UniqueConstraint("session_id", "question_key", name="uq_session_question"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("screening_sessions.id"), index=True)
    question_key: Mapped[str] = mapped_column(String(120), index=True)
    value_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    session: Mapped[ScreeningSession] = relationship(back_populates="answers")
