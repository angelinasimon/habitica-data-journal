# app/services/analytics.py
from __future__ import annotations
from datetime import datetime, date, timedelta, timezone
from typing import Optional, List, Dict, Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine, EventORM, HabitORM

# If your DB exposes these; otherwise we gracefully fall back.
try:
    from app.db import UserORM, HabitStatus  # type: ignore
except Exception:
    UserORM = None
    HabitStatus = None


# ---------- helpers ----------

def _monday_of(d: date) -> date:
    """Return the Monday of the week containing d."""
    return d - timedelta(days=d.weekday())

def _user_tz(session: Session, user_id: str | int) -> ZoneInfo:
    """Look up user's timezone; default to America/Phoenix if missing/invalid."""
    if UserORM is not None:
        u = session.get(UserORM, user_id)
        tz_str = getattr(u, "timezone", None)
        if tz_str:
            try:
                return ZoneInfo(tz_str)
            except Exception:
                pass
    return ZoneInfo("America/Phoenix")

def _to_utc_bounds(local_d: date, tz: ZoneInfo, end_of_day: bool) -> datetime:
    """Convert a local date boundary to UTC datetime for querying."""
    if end_of_day:
        dt_local = datetime(local_d.year, local_d.month, local_d.day, 23, 59, 59, 999_999, tzinfo=tz)
    else:
        dt_local = datetime(local_d.year, local_d.month, local_d.day, 0, 0, 0, 0, tzinfo=tz)
    return dt_local.astimezone(timezone.utc)

def _ensure_aware(dt: datetime) -> datetime:
    """Cope with naive timestamps by assuming UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


# ---------- analytics ----------

def weekly_completion(
    user_id: str | int,
    start: Optional[date] = None,
    end: Optional[date] = None
) -> List[Dict[str, Any]]:
    """
    Compute weekly completion% across all *active* habits for the user.

    - Weeks are Monday-based and timezone-aware (uses user's tz).
    - Dedup multiple events per (habit, local calendar day).
    - Denominator = (# active habits) × (# days in that week intersecting [start, end]).
    - If start/end not provided, defaults to the current week + previous week.
    """
    with Session(engine) as session:
        tz = _user_tz(session, user_id)

        # Default window: previous week + current week (2 weeks total)
        if start is None or end is None:
            today_local = datetime.now(timezone.utc).astimezone(tz).date()
            end_week_start = _monday_of(today_local)
            start = end_week_start - timedelta(days=7)
            end = end_week_start + timedelta(days=6)

        # Query window in UTC
        start_utc = _to_utc_bounds(start, tz, end_of_day=False)
        end_utc = _to_utc_bounds(end, tz, end_of_day=True)

        # 1) Fetch events for this user in the window
        rows = session.execute(
            select(EventORM.habit_id, EventORM.occurred_at_utc)
            .join(HabitORM, EventORM.habit_id == HabitORM.id)
            .where(HabitORM.user_id == user_id)
            .where(EventORM.occurred_at_utc >= start_utc)
            .where(EventORM.occurred_at_utc <= end_utc)
        ).all()

        # 2) Dedup to one hit per (habit, local_date), bucket by week start (local Monday)
        hits_by_week: dict[date, set[tuple[str | int, date]]] = {}
        for habit_id, occurred_at in rows:
            occurred_at = _ensure_aware(occurred_at)
            local_day = occurred_at.astimezone(tz).date()
            week = _monday_of(local_day)
            hits_by_week.setdefault(week, set()).add((habit_id, local_day))

        # 3) Count active habits (fallback to *all* if no status enum)
        if HabitStatus is not None and hasattr(HabitStatus, "ACTIVE"):
            active_habits = session.execute(
                select(HabitORM.id).where(
                    HabitORM.user_id == user_id,
                    HabitORM.status == HabitStatus.ACTIVE
                )
            ).all()
        else:
            active_habits = session.execute(
                select(HabitORM.id).where(HabitORM.user_id == user_id)
            ).all()
        active_count = len(active_habits)

        # 4) Build weekly results across the requested range
        results: List[Dict[str, Any]] = []
        week_cursor = _monday_of(start)
        last_week = _monday_of(end)

        while week_cursor <= last_week:
            # Days of this week that intersect [start, end]
            days_in_week = [week_cursor + timedelta(days=i) for i in range(7)]
            days_in_range = [d for d in days_in_week if start <= d <= end]

            opportunities = active_count * len(days_in_range)
            completions = len(hits_by_week.get(week_cursor, set()))
            pct = (completions / opportunities) if opportunities else 0.0

            results.append({
                "week_start": week_cursor.isoformat(),
                "completion_pct": pct,
            })
            week_cursor += timedelta(days=7)

        return results


def habit_heatmap(user_id: str | int, start: Optional[date] = None, end: Optional[date] = None) -> Dict[str, Any]:
    """
    Stub: return a date->count mapping suitable for a calendar heatmap.
    """
    return {
        "user_id": str(user_id),
        "window": {"start": start.isoformat() if start else None, "end": end.isoformat() if end else None},
        "dates": {
            "2025-09-10": 2,
            "2025-09-11": 1,
            "2025-09-12": 0,
            "2025-09-13": 3,
        },
        "status": "stub"
    }


def slip_detector(user_id: str | int) -> Dict[str, Any]:
    """
    Stub: highlight habits with recent missed streaks or downward trends.
    """
    return {
        "user_id": str(user_id),
        "slips": [
            {"habit_id": "stub-2", "name": "Read", "misses_in_last_7_days": 4, "note": "Falling behind vs. last week"},
        ],
        "status": "stub"
    }
