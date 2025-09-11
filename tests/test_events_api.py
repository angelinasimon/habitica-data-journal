# tests/test_events_api.py
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import Depends
from app.main import app
from app.db import UserORM
from app.auth import get_current_user as auth_get_current_user

# --- auth override helper (same pattern as your habits tests) ---
def _install_user_override(client, db_session, name="E User", email=None, timezone_str="America/Phoenix"):
    email = email or f"e+{uuid.uuid4().hex}@example.com"
    u = UserORM(name=name, email=email, timezone=timezone_str)
    db_session.add(u); db_session.commit(); db_session.refresh(u)

    def override():
        return u
    app.dependency_overrides[auth_get_current_user] = override
    return u

def _remove_user_override():
    try:
        del app.dependency_overrides[auth_get_current_user]
    except KeyError:
        pass


def test_log_event_idempotent_same_local_day(client, db_session):
    # Create user + habit
    user = _install_user_override(client, db_session)
    h = client.post("/habits/", json={"name": "Hydrate"}).json()

    # pick a Phoenix local datetime (same local day)
    tz = ZoneInfo("America/Phoenix")
    day_local = datetime(2025, 1, 2, 9, 0, tzinfo=tz)
    later_same_day = day_local.replace(hour=22)

    # send as ISO with tz; EventCreate should normalize to UTC
    r1 = client.post("/events", json={"habit_id": h["id"], "occurred_at": day_local.isoformat()})
    assert r1.status_code == 201, r1.text
    ev1 = r1.json()

    r2 = client.post("/events", json={"habit_id": h["id"], "occurred_at": later_same_day.isoformat()})
    # policy: idempotent per local day → should return same (or at least not create a duplicate)
    # If your endpoint returns 201 both times but the second returns the existing row, that's fine.
    assert r2.status_code in (200, 201), r2.text
    ev2 = r2.json()

    # Must refer to the same stored day; simplest check: same id
    assert ev1["id"] == ev2["id"]

    # streak should be current=1, max=1
    s = client.get(f"/habits/{h['id']}/streak").json()
    assert s["current"] == 1
    assert s["max"] == 1
    assert s["last_completed"] is not None

    _remove_user_override()


def test_streak_two_consecutive_local_days(client, db_session):
    user = _install_user_override(client, db_session)
    h = client.post("/habits/", json={"name": "Read"}).json()

    tz = ZoneInfo("America/Phoenix")
    d1_local = datetime(2025, 1, 3, 9, 0, tzinfo=tz)
    d2_local = d1_local + timedelta(days=1, hours=1)

    client.post("/events", json={"habit_id": h["id"], "occurred_at": d1_local.isoformat()})
    client.post("/events", json={"habit_id": h["id"], "occurred_at": d2_local.isoformat()})

    s = client.get(f"/habits/{h['id']}/streak").json()
    assert s["current"] == 2
    assert s["max"] == 2

    _remove_user_override()


def test_paused_habit_rejects_events(client, db_session):
    user = _install_user_override(client, db_session)
    h = client.post("/habits/", json={"name": "Journal"}).json()

    # pause the habit
    r = client.patch(f"/habits/{h['id']}", json={"status": "paused"})
    assert r.status_code == 200
    assert r.json()["status"] == "paused"

    now_utc = datetime.now(timezone.utc)
    bad = client.post("/events", json={"habit_id": h["id"], "occurred_at": now_utc.isoformat()})
    assert bad.status_code == 409  # policy: paused rejects

    _remove_user_override()


def test_list_events_by_range(client, db_session):
    user = _install_user_override(client, db_session)
    h = client.post("/habits/", json={"name": "Stretch"}).json()

    now = datetime(2025, 1, 4, 12, 0, tzinfo=timezone.utc)
    earlier = now - timedelta(days=2)
    between = now - timedelta(days=1)
    later = now + timedelta(hours=1)

    # three events across a small window
    client.post("/events", json={"habit_id": h["id"], "occurred_at": earlier.isoformat()})
    client.post("/events", json={"habit_id": h["id"], "occurred_at": between.isoformat()})
    client.post("/events", json={"habit_id": h["id"], "occurred_at": later.isoformat()})

    # filter to [between, later)
    r = client.get(f"/events/habits/{h['id']}", params={
        "start": between.isoformat(),
        "end": later.isoformat()
    })
    assert r.status_code == 200, r.text
    items = r.json()
    # should only include the "between" event
    assert len(items) == 1

    _remove_user_override()
