# app/services/features.py
from __future__ import annotations
from collections import deque, defaultdict
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from statistics import median
from typing import Dict, Iterable, List, Optional, Tuple

import pytz
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db import HabitORM, EventORM, ContextORM


# ---------- Helpers: time-bucket parsing ----------



def _parse_time_buckets(spec: str) -> List[Tuple[str, int, int]]:
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    out: List[Tuple[str, int, int]] = []
    for p in parts:
        name, rng = p.split("=")
        s, e = rng.split("-")
        out.append((name.strip(), int(s), int(e)))
    return out


def hour_to_bucket(hour: int, buckets: List[Tuple[str, int, int]]) -> Optional[str]:
    for name, start_h, end_h in buckets:
        if start_h < end_h:
            if start_h <= hour < end_h:
                return name
        else:  # wrap-around like 22-5
            if hour >= start_h or hour < end_h:
                return name
    return None


# ---------- Feature rows ----------

@dataclass
class FeatureRow:
    user_id: str
    habit_id: int
    day: date
    last_7d_rate: float
    last_30d_rate: float
    current_streak: int
    dow: int                        # 0=Mon .. 6=Sun
    hour_bucket: Optional[str]      # derived from median completion hour
    difficulty: Optional[str]
    active: bool
    is_travel: bool
    is_exam: bool
    is_illness: bool
    slip_7d_flag: bool              # True if 3 consecutive misses up to 'day'


# ---------- Core utilities ----------

def _daterange(start: date, end: date) -> Iterable[date]:
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _to_local_day(ts_utc: datetime, tz: pytz.BaseTzInfo) -> date:
    return ts_utc.replace(tzinfo=pytz.UTC).astimezone(tz).date()


def _median_completion_hour(event_ts_list: List[datetime], tz: pytz.BaseTzInfo) -> Optional[int]:
    if not event_ts_list:
        return None
    hours = []
    for ts in event_ts_list:
        local = ts.replace(tzinfo=pytz.UTC).astimezone(tz)
        hours.append(local.hour)
    return int(median(hours)) if hours else None


# ---------- Public: build_daily_features ----------

def build_daily_features(
    db: Session,
    user_id: str,
    start: date,
    end: date,
    tz_name: Optional[str] = None,
) -> List[FeatureRow]:
    """
    Build one row per (habit, day) in [start, end], using a single bulk query
    for events (with 30d backfill) and one for contexts. Features are computed
    in Python for portability and performance.
    """
    assert start <= end, "start must be <= end"

    tz = pytz.timezone(tz_name or settings.TIMEZONE)
    buckets = _parse_time_buckets(settings.TIME_BUCKETS)  # dynamic (respects monkeypatch/.env)

    # Backfill to support last_7d and last_30d rolling stats
    backfill_start = start - timedelta(days=30)

    # ---- Bulk load habits for the user
    habits: List[HabitORM] = (
        db.query(HabitORM)
        .filter(HabitORM.user_id == user_id)
        .all()
    )
    habit_ids = [h.id for h in habits]
    if not habit_ids:
        return []

    # ---- Bulk load events within [backfill_start, end + 1 day)
    events: List[EventORM] = (
        db.query(EventORM)
        .filter(EventORM.habit_id.in_(habit_ids))
        .filter(EventORM.occurred_at_utc >= datetime.combine(backfill_start, datetime.min.time()))
        .filter(EventORM.occurred_at_utc < datetime.combine(end + timedelta(days=1), datetime.min.time()))
        .all()
    )

    # Collapse to per-(habit, local_day) completion flag and collect completion hours
    per_day_completed: Dict[Tuple[int, date], bool] = {}
    completion_ts_by_habit: Dict[int, List[datetime]] = defaultdict(list)

    for ev in events:
        # Presence of an event == completed for that local day
        local_day = _to_local_day(ev.occurred_at_utc, tz)
        key = (ev.habit_id, local_day)
        per_day_completed[key] = True
        completion_ts_by_habit[ev.habit_id].append(ev.occurred_at_utc)

    # ---- Bulk load contexts for the user (UTC → local-day flags)
    contexts: List[ContextORM] = (
        db.query(ContextORM)
        .filter(ContextORM.user_id == user_id)
        .all()
    )

    context_flags_by_day: Dict[date, Dict[str, bool]] = defaultdict(
        lambda: {"travel": False, "exam": False, "illness": False}
    )
    for c in contexts:
        if c.start_utc is None:
            continue
        c_start_local = c.start_utc.replace(tzinfo=pytz.UTC).astimezone(tz).date()
        c_end_local = (
            c.end_utc.replace(tzinfo=pytz.UTC).astimezone(tz).date()
            if c.end_utc is not None else None
        )
        win_start = max(start, c_start_local)
        win_end = min(end, c_end_local) if c_end_local is not None else end
        if win_start > win_end:
            continue

        kind_name = str(getattr(c.kind, "value", c.kind)).lower()
        key = "travel" if "travel" in kind_name else \
              "exam" if "exam" in kind_name else \
              "illness" if "illness" in kind_name else None
        if key:
            for d in _daterange(win_start, win_end):
                context_flags_by_day[d][key] = True

    # Compute per-habit observed median completion hour (last 30d window)
    median_hour_by_habit: Dict[int, Optional[int]] = {}
    for h in habits:
        mh = _median_completion_hour(completion_ts_by_habit.get(h.id, []), tz)
        median_hour_by_habit[h.id] = mh

    # Build rows
    rows: List[FeatureRow] = []

    for h in habits:
        win7: deque[int] = deque([], maxlen=7)
        win30: deque[int] = deque([], maxlen=30)
        current_streak = 0

        mhour = median_hour_by_habit[h.id]
        hbkt = hour_to_bucket(mhour, buckets) if mhour is not None else None

        # 1) Warm-up: seed windows & current_streak ONLY
        for d in _daterange(backfill_start, start - timedelta(days=1)):
            completed = 1 if per_day_completed.get((h.id, d), False) else 0
            win7.append(completed)
            win30.append(completed)
            # keep streak historically so day-1 streak is correct
            current_streak = current_streak + 1 if completed else 0

        # Reset miss streak at the start of the requested window
        miss_streak = 0

        # 2) Emit rows for [start..end]
        for d in _daterange(start, end):
            completed = 1 if per_day_completed.get((h.id, d), False) else 0

            win7.append(completed)
            win30.append(completed)
            last7 = sum(win7) / len(win7)
            last30 = sum(win30) / len(win30)

            current_streak = current_streak + 1 if completed else 0
            miss_streak = 0 if completed else (miss_streak + 1)
            slip_flag = miss_streak >= 3

            flags = context_flags_by_day[d]
            status_str = str(getattr(getattr(h, "status", None), "value", getattr(h, "status", None)) or "").lower()
            active_val = status_str == "active"
            diff_val = getattr(h, "difficulty", None)
            difficulty_str = str(getattr(diff_val, "value", diff_val)) if diff_val is not None else None

            rows.append(FeatureRow(
                user_id=user_id,
                habit_id=h.id,
                day=d,
                last_7d_rate=round(last7, 4),
                last_30d_rate=round(last30, 4),
                current_streak=current_streak,
                dow=d.weekday(),
                hour_bucket=hbkt,
                difficulty=difficulty_str,
                active=active_val,
                is_travel=flags["travel"],
                is_exam=flags["exam"],
                is_illness=flags["illness"],
                slip_7d_flag=slip_flag,
            ))

    return rows
