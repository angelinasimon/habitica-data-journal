# tests/test_reminders_policy.py
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from starlette.testclient import TestClient
from fastapi import Depends
from app.main import app
from app.db import UserORM
from app.auth import get_current_user as auth_get_current_user

def _iso_utc_now_no_us():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

@pytest.fixture(scope="function")
def client(db_session):
    os.environ["DISABLE_SCHEDULER"] = "1"
    with TestClient(app) as c:
        yield c

def _install_user_override(db_session, name="Policy User", email=None, tz="America/Phoenix"):
    email = email or f"reminder-policy+{uuid4().hex[:8]}@example.com"
    u = UserORM(name=name, email=email, timezone=tz)
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

def _make_user(client):
    r = client.post("/users", json={
        "email": f"reminder-policy-api+{uuid4().hex[:8]}@example.com",
        "name": "API User",
        "timezone": "America/Phoenix",
    })
    assert r.status_code in (200, 201), r.text
    return r.json()

def _make_habit(client, user_id, name="Hydrate"):
    r = client.post("/habits/", json={
        "user_id": user_id,
        "name": f"{name} {uuid4().hex[:6]}",
        "difficulty": "medium",
        "status": "active",
    })
    assert r.status_code in (200, 201), r.text
    return r.json()

def test_reminders_excludes_paused_habit(client, db_session):
    now_iso = _iso_utc_now_no_us()

    # Create API user (owner id for the habit)
    user = _make_user(client)
    habit = _make_habit(client, user["id"], name="Pause Me")

    # Install auth override so owner-scoped PATCH works
    owner = _install_user_override(db_session, name="Override User", tz="America/Phoenix")
    # Make override user match the habit owner (ids must match)
    owner.id = user["id"]; db_session.add(owner); db_session.commit()

    # Pause
    r = client.patch(f"/habits/{habit['id']}", json={"status": "paused"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "paused"

    # Paused habits should be excluded
    r = client.get(f"/users/{user['id']}/reminders", params={"as_of": now_iso})
    assert r.status_code == 200, r.text
    due = r.json()
    assert all(item["habit_id"] != habit["id"] for item in due), f"Paused habit should be excluded: {due}"

    _remove_user_override()

def test_reminders_excludes_when_active_context(client, db_session):
    now_iso = _iso_utc_now_no_us()
    user = _make_user(client)
    habit = _make_habit(client, user["id"], name="Context Hide")

    # We only need auth override if we mutate owner-scoped state; here we create a context (not scoped to habit id),
    # but to be safe and consistent we'll install it too.
    owner = _install_user_override(db_session, name="Override User", tz="America/Phoenix")
    owner.id = user["id"]; db_session.add(owner); db_session.commit()

    # Create an active context overlapping 'now'
    now = datetime.fromisoformat(now_iso)
    start = (now - timedelta(days=1)).isoformat()
    end   = (now + timedelta(days=1)).isoformat()

    r_ctx = client.post("/contexts", json={
        "kind": "travel",
        "start": start,
        "end": end,
        "data": {"note": "trip that should mute reminders"},
    })
    assert r_ctx.status_code == 201, r_ctx.text

    r = client.get(f"/users/{user['id']}/reminders", params={"as_of": now_iso})
    assert r.status_code == 200, r.text
    due = r.json()
    assert all(item["habit_id"] != habit["id"] for item in due), f"Active context should exclude habit: {due}"

    _remove_user_override()
