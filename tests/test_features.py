# tests/test_features.py
import uuid
from datetime import datetime, timedelta, date
import pytest
import pytz
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Adjust these imports to your project structure if needed
from app.core.settings import settings
from app.services.features import build_daily_features
from app.db import HabitORM, EventORM, ContextORM  # assuming these exist
from app.db import Base  # your declarative Base


@pytest.fixture(scope="function")
def db_session(tmp_path):
    """Create an isolated in-memory (file-based) SQLite DB per test."""
    # File-based SQLite so APScheduler/background things won't collide with :memory:
    sqlite_url = f"sqlite:///{tmp_path/'test.db'}"
    engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _mk_user_id():
    # If you have a real UserORM you can insert it; otherwise we just use an id
    return str(uuid.uuid4())


# ---------- PATCHED HELPERS TO MATCH YOUR ORMs ----------

def _mk_habit(session, user_id, name="Test Habit"):
    """
    HabitORM uses:
      - id: Integer PK (autoincrement)
      - user_id: String (UUID)
      - name, name_canonical
      - difficulty, status (both enums with defaults)
    """
    h = HabitORM(
        user_id=user_id,
        name=name,
        name_canonical=name.lower(),
    )
    session.add(h)
    session.commit()
    session.refresh(h)
    return h


def _add_event(session, habit_id: int, ts_utc: datetime, note: str | None = None):
    """
    EventORM uses:
      - id: Integer PK (autoincrement)
      - habit_id: int
      - occurred_at_utc: datetime (UTC)
      - note: Optional[str]
    """
    e = EventORM(
        habit_id=habit_id,
        occurred_at_utc=ts_utc,  # stored in UTC per your ORM
        note=note,
    )
    session.add(e)
    session.commit()
    session.refresh(e)
    return e


# -----------------------------
# 1) slip_7d_flag trend test
# -----------------------------
def test_slip_flag_turns_true_on_third_decline_day(db_session, monkeypatch):
    """
    Seed 10 consecutive days with completions:
      1,1,1,0,0,0,0,0,0,0
    Expect slip_7d_flag becomes True on the 3rd day of the decline.
    """
    user_id = _mk_user_id()
    habit = _mk_habit(db_session, user_id)

    # Fix timezone to Phoenix for consistency (no DST)
    monkeypatch.setattr(settings, "TIMEZONE", "America/Phoenix")

    start = date(2025, 9, 1)  # Monday
    # completions for day i from start
    pattern = [1, 1, 1, 0, 0, 0, 0, 0, 0, 0]
    tz_utc = pytz.UTC

    # Put all events at 16:00Z for simplicity
    for i, done in enumerate(pattern):
        d = start + timedelta(days=i)
        if done:
            ts = datetime(d.year, d.month, d.day, 16, 0, 0, tzinfo=tz_utc)
            _add_event(db_session, habit.id, ts)  # <-- patched (removed user_id)

    # Build features for the visible window (we want exactly these 10 days)
    rows = build_daily_features(
        db=db_session,
        user_id=user_id,
        start=start,
        end=start + timedelta(days=len(pattern) - 1),
        tz_name="America/Phoenix",
    )
    # Filter to this habit only (defensive if your function returns multiple habits)
    rows = [r for r in rows if r.habit_id == habit.id]
    rows.sort(key=lambda r: r.day)

    # Decline starts at index 3 (first 0). Third day of decline is index 5.
    # We expect slip_7d_flag to be True for day index 5.
    assert rows[5].slip_7d_flag is True, "slip_7d_flag should flip by the 3rd decline day (index 5)"
    # Optional: before day 5 it should not yet be True
    assert all(r.slip_7d_flag is False for r in rows[:5]), "slip flag should be False before the 3rd decline day"


# --------------------------------------------------------
# 2) Local day + hour bucket from a 23:15Z Phoenix event
# --------------------------------------------------------
def test_hour_bucket_and_local_day_phoenix(db_session, monkeypatch):
    """
    Add one event at 23:15Z; in Phoenix (UTC-7 year-round), that's 16:15 local.
    With default TIME_BUCKETS = morning=5-11,afternoon=11-17,evening=17-22,night=22-5
    => hour 16 maps to 'afternoon'.
    """
    user_id = _mk_user_id()
    habit = _mk_habit(db_session, user_id)

    # Force settings
    monkeypatch.setattr(settings, "TIMEZONE", "America/Phoenix")
    monkeypatch.setattr(
        settings,
        "TIME_BUCKETS",
        "morning=5-11,afternoon=11-17,evening=17-22,night=22-5",
    )

    day = date(2025, 9, 10)
    # 23:15Z -> 16:15 local Phoenix on the same UTC date
    ts_utc = datetime(day.year, day.month, day.day, 23, 15, 0, tzinfo=pytz.UTC)
    _add_event(db_session, habit.id, ts_utc)  # <-- patched (removed user_id)

    rows = build_daily_features(
        db=db_session,
        user_id=user_id,
        start=day,
        end=day,
        tz_name="America/Phoenix",
    )
    rows = [r for r in rows if r.habit_id == habit.id]
    assert len(rows) == 1
    r = rows[0]

    # Local date should still be the same calendar day in Phoenix (23:15Z -> 16:15 local)
    assert r.day == day

    # The median completion hour == 16 => 'afternoon'
    assert r.hour_bucket == "afternoon"


# ---------------------------------------------------------
# 3) Changing TIME_BUCKETS changes the computed bucket
# ---------------------------------------------------------
def test_time_buckets_env_changes_bucket(db_session, monkeypatch):
    """
    Verify that redefining TIME_BUCKETS via settings changes the bucket
    without touching code. We push the same 16:15 local completion and expect
    a different bucket label after changing TIME_BUCKETS.
    """
    user_id = _mk_user_id()
    habit = _mk_habit(db_session, user_id)

    # First, with default buckets -> 'afternoon'
    monkeypatch.setattr(settings, "TIMEZONE", "America/Phoenix")
    monkeypatch.setattr(
        settings,
        "TIME_BUCKETS",
        "morning=5-11,afternoon=11-17,evening=17-22,night=22-5",
    )

    day = date(2025, 9, 12)
    ts_utc = datetime(day.year, day.month, day.day, 23, 15, 0, tzinfo=pytz.UTC)  # 16:15 local
    _add_event(db_session, habit.id, ts_utc)  # <-- patched (removed user_id)

    rows1 = build_daily_features(
        db=db_session,
        user_id=user_id,
        start=day,
        end=day,
        tz_name="America/Phoenix",
    )
    r1 = [r for r in rows1 if r.habit_id == habit.id][0]
    assert r1.hour_bucket == "afternoon"

    # Now redefine buckets so 16:15 maps to a different label (single wide bucket)
    monkeypatch.setattr(settings, "TIME_BUCKETS", "onlybucket=0-24")

    rows2 = build_daily_features(
        db=db_session,
        user_id=user_id,
        start=day,
        end=day,
        tz_name="America/Phoenix",
    )
    r2 = [r for r in rows2 if r.habit_id == habit.id][0]
    assert r2.hour_bucket == "onlybucket"
    # Ensure the bucket label actually changed
    assert r1.hour_bucket != r2.hour_bucket
