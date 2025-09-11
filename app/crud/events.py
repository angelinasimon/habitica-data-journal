# app/crud/events.py
from typing import Optional, List
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException, status

from app.db import EventORM, HabitORM
from app.models.schemas import HabitStatus

def create(
    db: Session,
    *,
    habit_id: int,
    occurred_at: datetime,
    user_tz: str
) -> EventORM:
    """
    Insert an event only if another event for this habit on the same *local* day
    doesn't already exist. Works on SQLite & Postgres.
    """
    # ✅ Check habit exists and isn’t paused
    habit = db.get(HabitORM, habit_id)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    if habit.status == HabitStatus.paused:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Habit is paused; events not allowed",
        )

    # Always store UTC
    occurred_utc = occurred_at.astimezone(timezone.utc)

    # Determine the user’s local date for idempotence
    tz = ZoneInfo(user_tz)
    local_date = occurred_utc.astimezone(tz).date()

    # Fetch all events for that habit and compare local dates in Python
    for ev in db.query(EventORM).filter(EventORM.habit_id == habit_id).all():
        if ev.occurred_at_utc.astimezone(tz).date() == local_date:
            return ev  # already have one for that local calendar day

    ev = EventORM(habit_id=habit_id, occurred_at_utc=occurred_utc)
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def list_for_habit(
    db: Session,
    habit_id: int,
    *,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[EventORM]:
    """
    Simple range query in pure UTC.
    """
    stmt = select(EventORM).where(EventORM.habit_id == habit_id)
    if start is not None:
        stmt = stmt.where(EventORM.occurred_at_utc >= start)
    if end is not None:
        stmt = stmt.where(EventORM.occurred_at_utc < end)
    stmt = stmt.order_by(EventORM.occurred_at_utc.desc()).offset(offset).limit(limit)
    return db.execute(stmt).scalars().all()
