from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Iterable, Set, List
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session

from app.db import EventORM, UserORM

def _local_date(dt_utc: datetime, tz: ZoneInfo) -> datetime.date:
    return dt_utc.astimezone(tz).date()


class NotFound(Exception):
    """Raised when a requested entity doesn’t exist."""
    pass

def compute_streaks(
    db: Session,
    habit_id: int,
    *,
    user_id: int,
    as_of: datetime | None = None,
) -> Dict[str, Any]:
    """
    Compute current and max streaks for a habit.

    Rules:
    - Collapse multiple events on the same *local* calendar day.
    - When as_of is None, compute streaks as of the most recent event day (not real 'now').
    - last_completed = most recent completed local date <= as_of_local.date()
    """

    # Load user to get timezone
    user: UserORM | None = db.get(UserORM, user_id)
    tz = ZoneInfo(user.timezone if user and user.timezone else "UTC")

    # Fetch all events for this habit
    events: List[EventORM] = (
        db.query(EventORM)
          .filter(EventORM.habit_id == habit_id)
          .order_by(EventORM.occurred_at_utc.asc())
          .all()
    )
    if not events:
        return {"current": 0, "max": 0, "last_completed": None}

    # Default as_of to the latest event timestamp if not provided
    if as_of is None:
        as_of = events[-1].occurred_at_utc
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    as_of_local = as_of.astimezone(tz)
    as_of_local_day = as_of_local.date()

    # Collapse to unique local days, *only up to as_of_local_day*
    unique_days: Set[datetime.date] = set()
    for ev in events:
        d = _local_date(ev.occurred_at_utc, tz)
        if d <= as_of_local_day:
            unique_days.add(d)

    if not unique_days:
        # No completed days on/before as_of
        return {"current": 0, "max": 0, "last_completed": None}

    days_sorted = sorted(unique_days)
    last_completed = days_sorted[-1]

    # Compute max streak across the history seen so far
    max_streak = 1
    cur_run = 1
    for i in range(1, len(days_sorted)):
        if (days_sorted[i] - days_sorted[i - 1]).days == 1:
            cur_run += 1
        else:
            if cur_run > max_streak:
                max_streak = cur_run
            cur_run = 1
    if cur_run > max_streak:
        max_streak = cur_run

    # Compute current streak as of as_of_local_day
    days_set = set(days_sorted)
    current = 0
    d = as_of_local_day
    while d in days_set:
        current += 1
        d = d - timedelta(days=1)

    return {
        "current": current,
        "max": max_streak,
        "last_completed": last_completed,
    }
