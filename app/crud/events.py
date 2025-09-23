# app/crud/events.py
from typing import Optional, List
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException, status

from app.db import EventORM, HabitORM
from app.models.schemas import HabitStatus


def _to_utc_for_user(input_dt: datetime, user_tz: ZoneInfo) -> datetime:
    """
    Convert an incoming 'occurred_at' to the correct UTC instant:
    - If input has tzinfo, convert to UTC.
    - If input is naive, interpret it as user-local (user_tz) then convert to UTC.
    """
    if input_dt.tzinfo is None:
        local = input_dt.replace(tzinfo=user_tz)  # localize first
        return local.astimezone(timezone.utc)
    return input_dt.astimezone(timezone.utc)


def create(
    db: Session,
    *,
    habit_id: int,
    occurred_at: datetime,
    user_tz: str,
) -> EventORM:
    """
    Insert an event only if another event for this habit on the same *local* day
    doesn't already exist. Converts the input datetime to UTC using the user's tz.
    """
    # Ensure habit exists and isn’t paused
    habit = db.get(HabitORM, habit_id)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    if habit.status == HabitStatus.paused:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Habit is paused; events not allowed",
        )

    tz = ZoneInfo(user_tz or "UTC")

    # Single source of truth for the UTC instant
    occurred_utc = _to_utc_for_user(occurred_at, tz)

    # Idempotence: one event per user-local calendar day
    # local_date = occurred_utc.astimezone(tz).date()
    # for ev in db.query(EventORM).filter(EventORM.habit_id == habit_id).all():
    #     if ev.occurred_at_utc.astimezone(tz).date() == local_date:
    #         return ev

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
    """Simple range query in pure UTC."""
    stmt = select(EventORM).where(EventORM.habit_id == habit_id)
    if start is not None:
        stmt = stmt.where(EventORM.occurred_at_utc >= start)
    if end is not None:
        stmt = stmt.where(EventORM.occurred_at_utc < end)
    stmt = stmt.order_by(EventORM.occurred_at_utc.desc()).offset(offset).limit(limit)
    return db.execute(stmt).scalars().all()
