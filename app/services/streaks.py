# app/services/streaks.py
from __future__ import annotations
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
from typing import Optional, Set, List
from sqlalchemy.orm import Session

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

def _current_run(today: date, dates: Set[date]) -> int:
    """Consecutive days ending at 'today' contained in dates."""
    run = 0
    d = today
    while d in dates:
        run += 1
        d -= timedelta(days=1)
    return run

def compute_streaks(
    db: Session,
    habit_id: int,
    as_of: Optional[datetime] = None,
) -> dict:
    """
    Return {'current', 'max', 'last_completed'} for a habit.

    All event times are stored in UTC (recommended). We translate to the habit's local
    timezone to determine calendar days.
    """
    as_of = as_of or datetime.now(timezone.utc)

    # 1) Get timezone for the habit (from the owning user, or a habit field if you have one).
    row = (
        db.query(HabitORM.id, UserORM.timezone)
        .join(UserORM, HabitORM.user_id == UserORM.id)
        .filter(HabitORM.id == habit_id)
        .first()
    )
    if not row:
        raise NotFound(f"Habit {habit_id} not found")
    tz = ZoneInfo(row.timezone)

    # 2) Pull events up to as_of (UTC).
    #    Only fetch the one column you need for performance.
    events = (
        db.query(EventORM.occurred_at)
        .filter(
            EventORM.habit_id == habit_id,
            EventORM.occurred_at <= as_of,
        )
        .order_by(EventORM.occurred_at.asc())
        .all()
    )

    # 3) Convert each event UTC -> local date and collapse duplicates.
    local_dates = sorted({
        ev.occurred_at.astimezone(tz).date()
        for (ev,) in events  # ev is a row with one column
    })

    if not local_dates:
        return {"current": 0, "max": 0, "last_completed": None}

    dates_set = set(local_dates)
    today_local = as_of.astimezone(tz).date()

    current = _current_run(today_local, dates_set)
    max_run = _longest_run(local_dates)
    last_completed = max(local_dates)

    return {
        "current": current,
        "max": max_run,
        "last_completed": last_completed,
    }
