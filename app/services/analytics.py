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


def habit_heatmap(
    user_id: str | int,
    start: Optional[date] = None,
    end: Optional[date] = None
) -> Dict[str, Any]:
    """
    Group events into day-of-week × time-bucket counts.
    Useful for building a heatmap visualization (what times you succeed most).
    """
    with Session(engine) as session:
        tz = _user_tz(session, user_id)

        # Default window = last 30 days
        if start is None or end is None:
            today_local = datetime.now(timezone.utc).astimezone(tz).date()
            start = today_local - timedelta(days=30)
            end = today_local

        start_utc = _to_utc_bounds(start, tz, end_of_day=False)
        end_utc = _to_utc_bounds(end, tz, end_of_day=True)

        rows = session.execute(
            select(EventORM.occurred_at_utc)
            .join(HabitORM, EventORM.habit_id == HabitORM.id)
            .where(HabitORM.user_id == user_id)
            .where(EventORM.occurred_at_utc >= start_utc)
            .where(EventORM.occurred_at_utc <= end_utc)
        ).scalars().all()

        # Buckets
        dow_keys = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        buckets = ["morning", "afternoon", "evening"]
        counts = {d: {b: 0 for b in buckets} for d in dow_keys}

        def bucket_for_hour(h: int) -> str:
            if 5 <= h <= 11:
                return "morning"
            if 12 <= h <= 17:
                return "afternoon"
            return "evening"

        total = 0
        for ts in rows:
            ts = _ensure_aware(ts).astimezone(tz)
            dow = dow_keys[ts.weekday()]
            b = bucket_for_hour(ts.hour)
            counts[dow][b] += 1
            total += 1

        percent_of_dow = {}
        for d in dow_keys:
            day_total = sum(counts[d].values())
            percent_of_dow[d] = {
                b: (counts[d][b] / day_total if day_total else 0.0)
                for b in buckets
            }

        return {
            "user_id": str(user_id),
            "window": {"start": start.isoformat(), "end": end.isoformat()},
            "counts": counts,
            "percent_of_dow": percent_of_dow,  # <-- added to satisfy test
            "total_events": total,
        }


def slip_detector(
    user_id: str | int,
    window_7_days: int = 7,
    window_30_days: int = 30,
    slip_threshold: float = 0.15,
) -> Dict[str, Any]:
    with Session(engine) as session:
        tz = _user_tz(session, user_id)
        now = datetime.now(timezone.utc)
        w7_start = now - timedelta(days=window_7_days)
        w30_start = now - timedelta(days=window_30_days)

        # active habits
        if HabitStatus is not None and hasattr(HabitStatus, "ACTIVE"):
            habits = session.execute(
                select(HabitORM).where(
                    HabitORM.user_id == user_id,
                    HabitORM.status == HabitStatus.ACTIVE
                )
            ).scalars().all()
        else:
            habits = session.execute(
                select(HabitORM).where(HabitORM.user_id == user_id)
            ).scalars().all()

        if not habits:
            return {"user_id": str(user_id), "slipping": []}

        habit_map = {h.id: h for h in habits}

        # events in last 30 days, joined to habits to filter by user_id
        events = session.execute(
            select(EventORM.habit_id, EventORM.occurred_at_utc)
            .join(HabitORM, EventORM.habit_id == HabitORM.id)
            .where(HabitORM.user_id == user_id)
            .where(EventORM.occurred_at_utc >= w30_start)
            .where(EventORM.occurred_at_utc <= now)
        ).all()

        grouped: dict[str, list[datetime]] = {}
        for hid, ts in events:
            if hid in habit_map:
                grouped.setdefault(hid, []).append(_ensure_aware(ts))

        slipping = []
        for hid, ts_list in grouped.items():
            local_ts = [ts.astimezone(tz) for ts in ts_list]

            def distinct_days(since: datetime) -> int:
                return len({ts.date() for ts in local_ts if ts >= since.astimezone(tz)})

            days_7 = distinct_days(w7_start)
            days_30 = distinct_days(w30_start)

            pct_7 = days_7 / window_7_days
            pct_30 = days_30 / window_30_days
            delta = pct_7 - pct_30

            if (pct_30 - pct_7) >= slip_threshold:
                slipping.append({
                    "habit_id": hid,  # keep native type (int)
                    "name": habit_map[hid].name,
                    "pct_7d": round(pct_7, 3),
                    "pct_30d": round(pct_30, 3),
                    "delta": round(delta, 3),
                })

        slipping.sort(key=lambda r: r["delta"])
        return {"user_id": str(user_id), "slipping": slipping}
