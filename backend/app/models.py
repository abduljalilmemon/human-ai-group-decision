"""Database tables. These are the research record; never serialize them to clients (see protocol.py)."""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class ExperimentSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20))
    condition: Mapped[str] = mapped_column(String(30))
    config_snapshot: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _now()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # use_alter breaks the sessions <-> participants foreign-key cycle for create_all.
    decision_maker_id: Mapped[int | None] = mapped_column(
        ForeignKey("participants.id", use_alter=True, name="fk_sessions_decision_maker")
    )
    tie_break: Mapped[str | None] = mapped_column(String(10))  # none | round1 | random

    __table_args__ = (
        CheckConstraint("tie_break IN ('none', 'round1', 'random')", name="ck_sessions_tie_break"),
    )


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    label: Mapped[str] = mapped_column(String(50))
    kind: Mapped[str] = mapped_column(String(5))
    token: Mapped[str | None] = mapped_column(String(64), unique=True)  # null for AI participants
    joined_at: Mapped[datetime] = _now()

    __table_args__ = (
        CheckConstraint("kind IN ('human', 'ai')", name="ck_participants_kind"),
        UniqueConstraint("session_id", "label", name="uq_participants_session_label"),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"))
    round: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = _now()


class Vote(Base):
    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    round: Mapped[int]
    voter_id: Mapped[int] = mapped_column(ForeignKey("participants.id"))
    target_id: Mapped[int | None] = mapped_column(ForeignKey("participants.id"))  # null = abstain
    created_at: Mapped[datetime] = _now()

    __table_args__ = (
        UniqueConstraint("session_id", "round", "voter_id", name="uq_votes_one_per_round"),
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id"), index=True)
    type: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _now()
