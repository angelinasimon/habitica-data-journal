# app/services/streaks.py
from __future__ import annotations
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
from typing import Optional, Set, List
from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID


# Adjust these imports to match your project:
from app.db import UserORM, HabitORM, EventORM  # assumes you have EventORM.occurred_at (UTC), .habit_id

class NotFound(Exception):
    pass

def _longest_run(sorted_dates: List[date]) -> int:
    """Longest consecutive sequence in an ascending list of unique dates."""
    if not sorted_dates:
        return 0
    longest = 1
    run = 1
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
            run += 1
            longest = max(longest, run)
        else:
            run = 1
    return longest

def _current_run(today: date, dates: set[date]) -> int:
    run = 0
    d = today
    while d in dates:
        run += 1
        d -= timedelta(days=1)
    return run

def compute_streaks(db: Session, habit_id: UUID, *, user_id: UUID, as_of: datetime | None = None) -> dict:
    as_of = as_of or datetime.now(timezone.utc)

    # Verify habit belongs to user and get tz
    tzname = db.execute(
        select(UserORM.timezone)
        .join(HabitORM, HabitORM.user_id == UserORM.id)
        .where(HabitORM.id == habit_id, HabitORM.user_id == user_id)
    ).scalar_one_or_none()
    if tzname is None:
        raise NotFound(f"Habit {habit_id} not found")

    tz = ZoneInfo(tzname or "UTC")

    events = db.execute(
        select(EventORM.occurred_at_utc)
        .where(EventORM.habit_id == habit_id, EventORM.occurred_at_utc <= as_of)
        .order_by(EventORM.occurred_at_utc.asc())
    ).all()

    local_dates = sorted({ row[0].astimezone(tz).date() for row in events })
    if not local_dates:
        return {"current": 0, "max": 0, "last_completed": None}

    dates_set = set(local_dates)
    today_local = as_of.astimezone(tz).date()
    current = _current_run(today_local, dates_set)
    max_run = _longest_run(local_dates)

    return {"current": current, "max": max_run, "last_completed": local_dates[-1]}
