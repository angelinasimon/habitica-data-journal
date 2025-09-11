# tests/test_integration_flows.py
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import Depends
from app.main import app
from app.db import UserORM
from app.auth import get_current_user as auth_get_current_user

def _install_user_override(client, db_session, name="I User", email=None, timezone_str="America/Phoenix"):
    email = email or f"i+{uuid.uuid4().hex}@example.com"
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


def test_flow_create_habit_context_events_streak_and_pause(client, db_session):
    user = _install_user_override(client, db_session)

    # Create habit
    h = client.post("/habits/", json={"name": "Code"}).json()
    assert isinstance(h["id"], int)

    # Add a context window (e.g., travel soon)
    now = datetime(2025, 2, 1, 12, 0, tzinfo=timezone.utc)
    ctx = client.post("/contexts", json={
        "kind": "travel",
        "start": (now + timedelta(days=1)).isoformat(),
        "end": (now + timedelta(days=4)).isoformat(),
        "metadata": {"note": "Weekend trip"}
    })
    assert ctx.status_code == 201

    # Log two days of events → streak 2
    tz = ZoneInfo("America/Phoenix")
    d1 = datetime(2025, 2, 1, 9, 0, tzinfo=tz)
    d2 = d1 + timedelta(days=1, hours=1)

    client.post("/events", json={"habit_id": h["id"], "occurred_at": d1.isoformat()})
    client.post("/events", json={"habit_id": h["id"], "occurred_at": d2.isoformat()})

    s = client.get(f"/habits/{h['id']}/streak").json()
    assert s["current"] == 2 and s["max"] >= 2

    # Pause the habit, then try to log again → 409
    client.patch(f"/habits/{h['id']}", json={"status": "paused"})
    r = client.post("/events", json={"habit_id": h["id"], "occurred_at": (d2 + timedelta(days=1)).isoformat()})
    assert r.status_code == 409

    # Resume and log → ok
    client.patch(f"/habits/{h['id']}", json={"status": "active"})
    r2 = client.post("/events", json={"habit_id": h["id"], "occurred_at": (d2 + timedelta(days=1)).isoformat()})
    assert r2.status_code in (200, 201)

    _remove_user_override()


def test_habit_patch_timezone_validation_and_rename_conflict(client, db_session):
    user = _install_user_override(client, db_session)

    h1 = client.post("/habits/", json={"name": "Yoga"}).json()
    h2 = client.post("/habits/", json={"name": "YOGA 2"}).json()

    # invalid timezone should 422 (HabitPatch validator)
    bad = client.patch(f"/habits/{h1['id']}", json={"timezone": "Not/AZone"})
    assert bad.status_code == 422

    # rename h2 to "yoga" (case-insensitive conflict) → 409
    conflict = client.patch(f"/habits/{h2['id']}", json={"name": "yoga"})
    assert conflict.status_code == 409

    _remove_user_override()


def test_events_same_exact_timestamp_are_idempotent(client, db_session):
    user = _install_user_override(client, db_session)
    h = client.post("/habits/", json={"name": "Walk"}).json()

    ts = datetime(2025, 3, 1, 15, 0, tzinfo=timezone.utc).isoformat()
    e1 = client.post("/events", json={"habit_id": h["id"], "occurred_at": ts})
    e2 = client.post("/events", json={"habit_id": h["id"], "occurred_at": ts})
    assert e1.status_code == 201
    assert e2.status_code in (200, 201)
    assert e1.json()["id"] == e2.json()["id"]

    _remove_user_override()
