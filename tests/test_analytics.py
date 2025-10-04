# tests/test_analytics.py
import os
from types import SimpleNamespace
from uuid import uuid4
from datetime import date, datetime, timezone, timedelta
import pytest

from fastapi.testclient import TestClient
from app.main import app
from zoneinfo import ZoneInfo

from app.auth import get_current_user as auth_get_current_user


@pytest.fixture(scope="function")
def client(db_session):
    os.environ["DISABLE_SCHEDULER"] = "1"
    with TestClient(app) as c:
        yield c

def _iso(dtstr):
    # dtstr like "2025-09-01T10:00:00Z"
    return dtstr

def test_weekly_completion_two_weeks(client):
    # 1) Create user
    r = client.post("/users", json={
        "email": f"weekly+{uuid4().hex[:8]}@example.com",
        "name": "Weekly User",
        "timezone": "America/Phoenix",
    })
    assert r.status_code in (200, 201), r.text
    user = r.json()
    user_id = user["id"]

    # 2) Override auth to return this user for analytics routes
    from app.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user_id)

    try:
        # 3) Create a daily habit (ensure ACTIVE via lowercase enum)
        r = client.post("/habits/", json={
            "user_id": user_id,
            "name": "Hydrate",
            "status": "active",
        })
        assert r.status_code in (200, 201), r.text
        habit = r.json()
        habit_id = habit["id"]

        # 4) Log events: 5 days in week starting 2025-09-01, 6 days in week starting 2025-09-08
        week1_days = ["2025-09-01","2025-09-02","2025-09-03","2025-09-04","2025-09-05"]      # 5/7
        week2_days = ["2025-09-08","2025-09-09","2025-09-10","2025-09-11","2025-09-12","2025-09-13"]  # 6/7

        for d in week1_days + week2_days:
            r = client.post("/events/", json={
                "habit_id": habit_id,
                "occurred_at": f"{d}T10:00:00Z"  # one event per day (UTC)
            })
            assert r.status_code in (200, 201), r.text

        # 5) Call analytics with explicit window (Mon 9/01 through Sun 9/14)
        r = client.get("/analytics/weekly", params={
            "start": "2025-09-01",
            "end":   "2025-09-14",
        })
        assert r.status_code == 200, r.text
        data = r.json()

        # 6) Assert structure & values
        assert isinstance(data, list) and len(data) >= 2
        assert data[0]["week_start"] == "2025-09-01"
        assert data[1]["week_start"] == "2025-09-08"

        # Allow tiny float error
        assert abs(data[0]["completion_pct"] - (5/7)) < 1e-6
        assert abs(data[1]["completion_pct"] - (6/7)) < 1e-6
    finally:
        app.dependency_overrides.clear()


PHX = ZoneInfo("America/Phoenix")

def _override_auth_with(user_obj):
    app.dependency_overrides[auth_get_current_user] = lambda: user_obj

def _clear_auth_override():
    app.dependency_overrides.pop(auth_get_current_user, None)


@pytest.mark.usefixtures("db_session")
def test_heatmap_buckets_real(client, db_session):
    """
    Seed 3 events in distinct Phoenix-local buckets:
      - Monday 08:00 (morning)
      - Monday 19:00 (evening)
      - Wednesday 13:00 (afternoon)
    Assert the corresponding counts.
    """
    # user
    r = client.post("/users", json={
        "email": f"heatmap+{uuid4().hex[:8]}@example.com",
        "name": "Heatmap User",
        "timezone": "America/Phoenix",
    })
    assert r.status_code in (200, 201), r.text
    user = r.json()
    _override_auth_with(SimpleNamespace(id=user["id"]))

    # habit
    r = client.post("/habits/", json={"user_id": user["id"], "name": "HM", "status": "active"})
    assert r.status_code in (200, 201), r.text
    habit_id = r.json()["id"]

    # find most recent Monday in PHX
    today_local = datetime.now(timezone.utc).astimezone(PHX).date()
    mon = today_local - timedelta(days=today_local.weekday())
    wed = mon + timedelta(days=2)

    # three events — send PHX-aware timestamps (with -07:00 offset)
    ts_morn_phx = datetime(mon.year, mon.month, mon.day, 8, 0, 0, tzinfo=PHX)    # 08:00 Mon PHX
    ts_even_phx = datetime(mon.year, mon.month, mon.day, 19, 0, 0, tzinfo=PHX)   # 19:00 Mon PHX
    ts_aftn_phx = datetime(wed.year, wed.month, wed.day, 13, 0, 0, tzinfo=PHX)   # 13:00 Wed PHX

    for ts_phx in (ts_morn_phx, ts_even_phx, ts_aftn_phx):
        r = client.post("/events/", json={
            "habit_id": habit_id,
            "occurred_at": ts_phx.isoformat()   # includes -07:00
        })
        assert r.status_code in (200, 201), r.text

    # Query a full Mon–Sun window
    r = client.get("/analytics/heatmap", params={
        "start": mon.isoformat(),
        "end":   (mon + timedelta(days=6)).isoformat(),
    })
    assert r.status_code == 200, r.text
    body = r.json()
    counts = body["counts"]

    assert counts["Mon"]["morning"] == 1
    assert counts["Mon"]["evening"] == 1
    assert counts["Mon"]["afternoon"] == 0
    assert counts["Wed"]["afternoon"] == 1

    # percentages exist and make sense (Mon has 2 events split 50/50)
    pod_mon = body["percent_of_dow"]["Mon"]
    assert abs(pod_mon["morning"] - 0.5) < 1e-6
    assert abs(pod_mon["evening"] - 0.5) < 1e-6
    assert abs(pod_mon["afternoon"] - 0.0) < 1e-6

    _clear_auth_override()


@pytest.mark.usefixtures("db_session")
def test_slips_flags_recent_drop_real(client, db_session):
    """
    Create a habit with several completions 20–26 days ago (none in last 7).
    Expect it to appear in /analytics/slipping with pct_30d > pct_7d.
    """
    r = client.post("/users", json={
        "email": f"slip+{uuid4().hex[:8]}@example.com",
        "name": "Slip User",
        "timezone": "America/Phoenix",
    })
    assert r.status_code in (200, 201), r.text
    user = r.json()
    _override_auth_with(SimpleNamespace(id=user["id"]))

    r = client.post("/habits/", json={"user_id": user["id"], "name": "Read", "status": "active"})
    assert r.status_code in (200, 201), r.text
    habit_id = r.json()["id"]

    # Send PHX-aware wall times 20–26 days ago (with -07:00)
    now_phx = datetime.now(timezone.utc).astimezone(PHX)
    today_phx = now_phx.date()
    for d in [20, 21, 22, 23, 24, 26]:
        target_day = today_phx - timedelta(days=d)
        ts_phx = datetime(target_day.year, target_day.month, target_day.day, 18, 0, 0, tzinfo=PHX)
        r = client.post("/events/", json={
            "habit_id": habit_id,
            "occurred_at": ts_phx.isoformat()
        })
        assert r.status_code in (200, 201), r.text

    r = client.get("/analytics/slipping?threshold=0.15&w7=7&w30=30")
    assert r.status_code == 200, r.text
    body = r.json()
    slipping = body.get("slipping", [])
    assert isinstance(slipping, list) and len(slipping) >= 1
    assert any(s["habit_id"] == habit_id for s in slipping)

    me = next(s for s in slipping if s["habit_id"] == habit_id)
    assert me["pct_30d"] >= me["pct_7d"]

    _clear_auth_override()

def test_features_multiple_habits_two_rows_per_day(client):
    """
    Two habits for one user, both completed on the same day.
    Expect 2 rows (one per habit) for that day.
    """
    # user
    r = client.post("/users", json={
        "email": f"multi+{uuid4().hex[:8]}@example.com",
        "name": "Multi Habit User",
        "timezone": "America/Phoenix",
    })
    assert r.status_code in (200, 201), r.text
    user = r.json()
    user_id = user["id"]

    # override auth → this user
    from app.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user_id)

    # habits
    r = client.post("/habits/", json={"user_id": user_id, "name": "H1", "status": "active"})
    assert r.status_code in (200, 201), r.text
    h1 = r.json()["id"]

    r = client.post("/habits/", json={"user_id": user_id, "name": "H2", "status": "active"})
    assert r.status_code in (200, 201), r.text
    h2 = r.json()["id"]

    # same-day events for both
    day = "2025-09-10"
    for hid in (h1, h2):
        rr = client.post("/events/", json={
            "habit_id": hid,
            "occurred_at": f"{day}T10:00:00Z"
        })
        assert rr.status_code in (200, 201), rr.text

    # call features (single-day window -> should return 2 rows)
    r = client.get("/analytics/features", params={"start": day, "end": day})
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 2

    habit_ids = {row["habit_id"] for row in rows}
    assert habit_ids == {h1, h2}
    for row in rows:
        assert row["day"] == day
        # On the day we completed, these should be positive
        assert row["current_streak"] >= 1
        assert 0.0 <= row["last_7d_completion_rate"] <= 1.0
        assert 0.0 <= row["last_30d_completion_rate"] <= 1.0

def test_features_no_events_single_day_defaults(client):
    """
    No events for the day → defaults:
      - last_7d / last_30d = 0.0
      - current_streak = 0
      - median_completion_bucket = None
      - context flags false
      - slip = False (only one miss day in-window)
    """
    r = client.post("/users", json={
        "email": f"noev+{uuid4().hex[:8]}@example.com",
        "name": "No Events User",
        "timezone": "America/Phoenix",
    })
    assert r.status_code in (200, 201), r.text
    user = r.json()
    user_id = user["id"]

    from app.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user_id)

    # one active habit but no events
    r = client.post("/habits/", json={"user_id": user_id, "name": "Empty", "status": "active"})
    assert r.status_code in (200, 201), r.text
    habit_id = r.json()["id"]

    day = "2025-09-15"
    r = client.get("/analytics/features", params={"start": day, "end": day})
    assert r.status_code == 200, r.text
    rows = r.json()

    # one row for the habit/day
    assert len(rows) == 1
    row = rows[0]
    assert row["habit_id"] == habit_id
    assert row["day"] == day

    assert row["last_7d_completion_rate"] == 0.0
    assert row["last_30d_completion_rate"] == 0.0
    assert row["current_streak"] == 0
    assert row["median_completion_bucket"] is None
    assert row["context"] == {"travel": False, "exam": False, "illness": False}
    assert row["slip"] is False

def test_features_slip_flag_toggles_on_three_misses_then_resets(client):
    """
    Build a sequence over 5 days:
      D1: complete
      D2: miss
      D3: miss
      D4: miss  -> slip True
      D5: complete -> slip False (reset)
    Assert slip progression [False, False, True, False] across D2..D5 rows.
    """
    r = client.post("/users", json={
        "email": f"slip+{uuid4().hex[:8]}@example.com",
        "name": "Slip Toggle User",
        "timezone": "America/Phoenix",
    })
    assert r.status_code in (200, 201), r.text
    user = r.json()
    user_id = user["id"]

    from app.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user_id)

    r = client.post("/habits/", json={"user_id": user_id, "name": "Read", "status": "active"})
    assert r.status_code in (200, 201), r.text
    habit_id = r.json()["id"]

    # Define a 5-day window
    start_day = date(2025, 9, 1)
    days = [start_day + timedelta(days=i) for i in range(5)]

    # D1 complete only
    r = client.post("/events/", json={
        "habit_id": habit_id,
        "occurred_at": f"{days[0].isoformat()}T18:00:00Z"
    })
    assert r.status_code in (200, 201), r.text

    # D5 complete to reset slip after 3 misses
    # (We’ll post this after we fetch once to verify the True day too)
    # Actually post it now; evaluation is per-row within the window
    r = client.post("/events/", json={
        "habit_id": habit_id,
        "occurred_at": f"{days[4].isoformat()}T18:00:00Z"
    })
    assert r.status_code in (200, 201), r.text

    # Query full window
    r = client.get("/analytics/features", params={
        "start": days[0].isoformat(),
        "end":   days[-1].isoformat(),
    })
    assert r.status_code == 200, r.text
    rows = [row for row in r.json() if row["habit_id"] == habit_id]
    assert len(rows) == 5

    # Map by day for clarity
    by_day = {row["day"]: row for row in rows}
    d1, d2, d3, d4, d5 = [by_day[d.isoformat()] for d in days]

    # Sanity: D1 and D5 completed → current_streak >= 1 those days
    assert d1["current_streak"] >= 1
    assert d5["current_streak"] >= 1

    # Slip progression across misses:
    # D2 miss -> miss_streak=1 -> slip False
    # D3 miss -> miss_streak=2 -> slip False
    # D4 miss -> miss_streak=3 -> slip True
    # D5 complete -> resets -> slip False
    assert d2["slip"] is False
    assert d3["slip"] is False
    assert d4["slip"] is True
    assert d5["slip"] is False
