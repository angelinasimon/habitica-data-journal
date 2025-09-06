# app/db.py
from __future__ import annotations
# from sqlalchemy import create_engine, String, DateTime, func
# from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from typing import Optional
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy import (
    ForeignKey, Integer, Text,  Enum as SAEnum, JSON, Date, CheckConstraint, Index, create_engine, String, DateTime, func,  TypeDecorator, event
)
from enum import Enum 
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column, sessionmaker
from app.models.schemas import Difficulty
from datetime import date  # alongside datetime
from sqlalchemy.engine import Engine  # add this for the pragma listener

# Engine: SQLite file ./app.db
engine = create_engine("sqlite:///./app.db", future=True)

def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# Session factory and FastAPI dependency
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def init_db():
    # All models are in this file, so importing isn’t necessary.
    Base.metadata.create_all(engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
def utcnow() -> datetime:
    # Always use aware UTC
    return datetime.now(timezone.utc)


# ORM base + one model to start
class UTCDateTime(TypeDecorator):
    """Store datetimes as UTC, return as timezone-aware UTC datetimes."""
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            # treat naive as UTC; if you prefer to reject naive, raise instead
            value = value.replace(tzinfo=timezone.utc)
        # normalize to UTC before storing
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        # SQLite returns naive; attach UTC tz
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

class Base(DeclarativeBase):
    pass


HabitStatus = Enum("active", "paused", "archived", name="habit_status")
ContextKind = Enum("travel", "exam", "illness", "custom", name="context_kind")

class UserORM(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    timezone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)

    habits: Mapped[list["HabitORM"]] = relationship(
    back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    contexts: Mapped[list["ContextORM"]] = relationship(
    back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

class HabitORM(Base):
    __tablename__ = "habits"

    # ... your other columns ...

    difficulty: Mapped[Difficulty] = mapped_column(
    SAEnum(Difficulty, name="difficulty_enum", native_enum=False, validate_strings=True),
    nullable=False,
    server_default=Difficulty.medium.value,
    )

    status: Mapped[HabitStatus] = mapped_column(
        SAEnum(HabitStatus, name="habit_status_enum", native_enum=False, validate_strings=True),
        nullable=False,
        server_default=HabitStatus.active.value,
    )

        # ... rest unchanged ...
    __table_args__ = (
            # make sure the old int CHECK constraint is gone here
            Index("ix_habits_user_name_unique", "user_id", "name", unique=True),
        )
class EventORM(Base):
        __tablename__ = "events"

        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        habit_id: Mapped[int] = mapped_column(
            ForeignKey("habits.id", ondelete="CASCADE"), nullable=False, index=True
        )
        
        occurred_at_utc: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
        note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  
        created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

        habit: Mapped["HabitORM"] = relationship(back_populates="events")

        __table_args__ = (
            Index("ix_events_habit_ts_unique", "habit_id", "occurred_at_utc", unique=True),
    )
class ContextORM(Base):
    __tablename__ = "contexts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(ContextKind, nullable=False, server_default="custom")
    start_utc: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    end_utc: Mapped[Optional[datetime]] = mapped_column(UTCDateTime(), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


    user: Mapped["UserORM"] = relationship(back_populates="contexts")

    __table_args__ = (
        CheckConstraint(
            "(end_utc IS NULL) OR (end_utc > start_utc)",
            name="ck_contexts_end_after_start",
        ),
        Index("ix_contexts_user_window", "user_id", "start_utc", "end_utc"),
    )