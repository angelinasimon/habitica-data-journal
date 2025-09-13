from datetime import datetime, timezone
from uuid import uuid4
import os
import pytest

from starlette.testclient import TestClient
from app.main import app

def _iso_utc_now_no_us():
    # single source of truth for “today” in the test (no microseconds to avoid boundary flake)
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

@pytest.fixture(scope="function")  # function-scope to avoid cross-test leakage
def client():
    os.environ["DISABLE_SCHEDULER"] = "1"
    with TestClient(app) as c:
        yield c

def test_user_reminders_happy_path(client):
    # 0) freeze 'now'
    now_iso = _iso_utc_now_no_us()

    # 1) Create user
    r = client.post(
        "/users",
        json={
            "email": f"reminder-test+{uuid4().hex[:8]}@example.com",
            "name": "Reminder Test",
            "timezone": "America/Phoenix",
        },
    )
    assert r.status_code in (200, 201), r.text
    user = r.json()
    user_id = user["id"]

    # 2) Create a UNIQUE habit for that user to avoid 409 on reruns
    habit_name = f"Drink Water {uuid4().hex[:6]}"
    r = client.post("/habits/", json={
        "user_id": user_id,
        "name": habit_name,
        "difficulty": "medium",
        "status": "active",
    })
    assert r.status_code in (200, 201), r.text
    habit = r.json()
    habit_id = habit["id"]

    # 2a) Sanity: ensure the habit is actually owned by this user
    # If this fails, the reminders endpoint will (correctly) return [].
    r = client.get(f"/habits/{habit_id}")
    assert r.status_code == 200, r.text
    fetched = r.json()
    assert fetched.get("user_id") == user_id, f"habit not linked to user: {fetched}"

    # 3) Reminders should include this habit (no event yet today)
    r = client.get(f"/users/{user_id}/reminders", params={"as_of": now_iso})
    assert r.status_code == 200, r.text
    due_list = r.json()
    assert any(item["habit_id"] == habit_id for item in due_list), \
        f"Expected {habit_id} in {due_list}"

    # 4) Log an event for 'now' → should remove it from due list
    r = client.post("/events", json={
        "habit_id": habit_id,
        "occurred_at_utc": now_iso,
    })
    assert r.status_code in (200, 201), r.text

    # 5) Now reminders should be empty for this habit (same 'as_of')
    r = client.get(f"/users/{user_id}/reminders", params={"as_of": now_iso})
    assert r.status_code == 200, r.text
    due_list_after = r.json()
    assert all(item["habit_id"] != habit_id for item in due_list_after), \
        f"Did not expect {habit_id} in {due_list_after}"
