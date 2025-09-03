# app/db.py
from __future__ import annotations
# from sqlalchemy import create_engine, String, DateTime, func
# from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from typing import Optional
from uuid import uuid4
from datetime import datetime 
from sqlalchemy import (
    ForeignKey, Integer, Text, Enum, JSON, Date, CheckConstraint, Index, create_engine, String, DateTime, func
)
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column, sessionmaker
from datetime import date  # alongside datetime

# Engine: SQLite file ./app.db
engine = create_engine("sqlite:///./app.db", future=True)

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

# ORM base + one model to start
class Base(DeclarativeBase):
    pass


HabitStatus = Enum("active", "paused", "archived", name="habit_status")
ContextKind = Enum("travel", "exam", "illness", "custom", name="context_kind")

class UserORM(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    timezone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)

    habits: Mapped[list["Habit"]] = relationship(
    back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    contexts: Mapped[list["Context"]] = relationship(
    back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

class Habit(Base):
    __tablename__ = "habits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    status: Mapped[str] = mapped_column(HabitStatus, nullable=False, server_default="active")
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="America/Phoenix"
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # relationships
    user: Mapped["UserORM"] = relationship(back_populates="habits")
    events: Mapped[list["Event"]] = relationship(
        back_populates="habit", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint("difficulty >= 1 AND difficulty <= 5", name="ck_habits_difficulty_1_5"),
        Index("ix_habits_user_name_unique", "user_id", "name", unique=True),
    )
class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    habit_id: Mapped[int] = mapped_column(
        ForeignKey("habits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    occurred_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    habit: Mapped["Habit"] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_events_habit_ts_unique", "habit_id", "occurred_at_utc", unique=True),
    )
class Context(Base):
    __tablename__ = "contexts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(ContextKind, nullable=False, server_default="custom")
    start_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_utc: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    metadata: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["UserORM"] = relationship(back_populates="contexts")

    __table_args__ = (
        CheckConstraint(
            "(end_utc IS NULL) OR (end_utc > start_utc)",
            name="ck_contexts_end_after_start",
        ),
        Index("ix_contexts_user_window", "user_id", "start_utc", "end_utc"),
    )