# app/crud/events.py
from typing import Optional, List
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from fastapi import HTTPException, status

from app.db import EventORM, HabitORM
from app.models.schemas import HabitStatus, EventCreate

def _local_day_bounds_utc(when_utc: datetime, tz_name: str) -> tuple[datetime, datetime]:
    """Given a UTC timestamp and an IANA tz, return the UTC bounds of that local day."""
    tz = ZoneInfo(tz_name)
    local = when_utc.astimezone(tz)
    start_local = datetime.combine(local.date(), time(0, 0), tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return (
        start_local.astimezone(timezone.utc),
        end_local.astimezone(timezone.utc),
    )

def create(db: Session, payload: EventCreate) -> EventORM:
    """Create one completion with 'one-per-local-day' idempotency in user's timezone."""
    habit = db.get(HabitORM, payload.habit_id)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    # Policy: paused habits reject completions
    if habit.status == HabitStatus.paused:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Habit is paused")

    # Payload.occurred_at is already UTC (validator). Compute the local-day window.
    tz_name = habit.user.timezone or "UTC"
    start_utc, end_utc = _local_day_bounds_utc(payload.occurred_at, tz_name)

    # One-per-local-day soft guard (idempotent)
    existing = (
        db.query(EventORM)
        .filter(
            and_(
                EventORM.habit_id == habit.id,
                EventORM.occurred_at_utc >= start_utc,
                EventORM.occurred_at_utc < end_utc,
            )
        )
        .first()
    )
    if existing:
        return existing

    # Create the event (store UTC)
    e = EventORM(habit_id=habit.id, occurred_at_utc=payload.occurred_at)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e

def list_for_habit(
    db: Session,
    habit_id: int,
    *,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[EventORM]:
    stmt = select(EventORM).where(EventORM.habit_id == habit_id)
    if start is not None:
        stmt = stmt.where(EventORM.occurred_at_utc >= start)
    if end is not None:
        stmt = stmt.where(EventORM.occurred_at_utc < end)
    stmt = stmt.order_by(EventORM.occurred_at_utc.desc()).offset(offset).limit(limit)
    return db.execute(stmt).scalars().all()