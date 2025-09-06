# tests/test_streaks.py
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.services.streaks import compute_streaks

PHX = ZoneInfo("America/Phoenix")

def _utc(dt):
    """Convert any aware datetime to UTC; if naive, assume it's already UTC."""
    return dt if dt.tzinfo is None else dt.astimezone(timezone.utc)

def eod_local(dt):
    """End-of-day helper in the given local tz-aware datetime's timezone."""
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)

def test_streaks_no_events_returns_zeroes(db_session, user_factory, habit_factory):
    user = user_factory(timezone="America/Phoenix")
    habit = habit_factory(user_id=user.id)

    as_of_local = datetime(2025, 3, 5, 12, 0, tzinfo=PHX)
    out = compute_streaks(db_session, habit.id, user_id=user.id, as_of=_utc(as_of_local))
    assert out["current"] == 0
    assert out["max"] == 0
    assert out["last_completed"] is None

def test_collapse_duplicates_and_current_streak_today(db_session, user_factory, habit_factory, event_factory):
    """Two events on same local day collapse to one; yesterday + today => current=2, max=2."""
    user = user_factory(timezone="America/Phoenix")
    habit = habit_factory(user_id=user.id)

    today_local = datetime(2025, 3, 6, 8, 0, tzinfo=PHX)
    yday_local = today_local - timedelta(days=1)

    # today (two events -> collapse)
    event_factory(habit_id=habit.id, occurred_at_utc=_utc(today_local.replace(hour=8, minute=0)))
    event_factory(habit_id=habit.id, occurred_at_utc=_utc(today_local.replace(hour=20, minute=30)))
    # yesterday
    event_factory(habit_id=habit.id, occurred_at_utc=_utc(yday_local.replace(hour=9, minute=0)))

    as_of_local = eod_local(today_local)
    out = compute_streaks(db_session, habit.id, user_id=user.id, as_of=_utc(as_of_local))
    assert out["current"] == 2
    assert out["max"] == 2
    assert out["last_completed"] == today_local.date()

def test_gap_breaks_current_streak_and_max_over_history(db_session, user_factory, habit_factory, event_factory):
    """Gap on previous day means current=1; max streak still computed from history."""
    user = user_factory(timezone="America/Phoenix")
    habit = habit_factory(user_id=user.id)

    anchor = datetime(2025, 3, 10, 9, 0, tzinfo=PHX)  # treat as 'today'

    # earlier 2-day streak: D-5, D-4
    event_factory(habit_id=habit.id, occurred_at_utc=_utc((anchor - timedelta(days=5)).replace(hour=8)))
    event_factory(habit_id=habit.id, occurred_at_utc=_utc((anchor - timedelta(days=4)).replace(hour=8)))
    # gap on D-1, only today present
    event_factory(habit_id=habit.id, occurred_at_utc=_utc(anchor.replace(hour=7)))

    as_of_local = eod_local(anchor)
    out = compute_streaks(db_session, habit.id, user_id=user.id, as_of=_utc(as_of_local))
    assert out["current"] == 1
    assert out["max"] == 2
    assert out["last_completed"] == anchor.date()

def test_timezone_boundary_midnight_handling(db_session, user_factory, habit_factory, event_factory):
    """Around 07:00 UTC ↔ midnight Phoenix; events straddling it should form consecutive local days."""
    user = user_factory(timezone="America/Phoenix")
    habit = habit_factory(user_id=user.id)

    utc_day = datetime(2025, 4, 2, tzinfo=timezone.utc)
    ev1 = utc_day.replace(hour=6, minute=59)  # local: previous day 23:59
    ev2 = utc_day.replace(hour=7, minute=1)   # local: current day 00:01

    event_factory(habit_id=habit.id, occurred_at_utc=ev1)
    event_factory(habit_id=habit.id, occurred_at_utc=ev2)

    as_of_local = eod_local(ev2.astimezone(PHX))
    out = compute_streaks(db_session, habit.id, user_id=user.id, as_of=_utc(as_of_local))
    assert out["current"] == 2
    assert out["max"] == 2
    assert out["last_completed"] == as_of_local.date()

def test_as_of_in_the_past_time_travel(db_session, user_factory, habit_factory, event_factory):
    """If as_of is noon on D-1 local, streak is only through D-1 (ignores D)."""
    user = user_factory(timezone="America/Phoenix")
    habit = habit_factory(user_id=user.id)

    D = datetime(2025, 5, 15, 8, 0, tzinfo=PHX)

    for delta in (2, 1, 0):  # D-2, D-1, D at 08:00 local
        event_factory(habit_id=habit.id, occurred_at_utc=_utc((D - timedelta(days=delta)).replace(hour=8)))

    as_of_local = (D - timedelta(days=1)).replace(hour=12, minute=0)  # noon on D-1
    out = compute_streaks(db_session, habit.id, user_id=user.id, as_of=_utc(as_of_local))
    assert out["current"] == 2
    assert out["max"] == 2
    assert out["last_completed"] == as_of_local.date()
